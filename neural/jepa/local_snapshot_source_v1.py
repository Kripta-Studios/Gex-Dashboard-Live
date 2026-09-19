"""Fixed, local-only 2023-01-03 option snapshot source diagnostic."""

import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq

from neural.jepa.local_snapshot_schema_v1 import (
    AVAILABILITY_BASIS,
    DAY,
    GREEK_COLUMNS,
    OI_COLUMNS,
    TICKERS,
)
from neural.jepa.multiscale_v1r1.artifacts import stage, write_json
from neural.jepa.multiscale_v1r1.provenance import coherent_read_handles


AUTHORIZATION = 'USER_LOCAL_SNAPSHOT_RESEARCH_20260919'
OUTPUT = Path('D:/GexResearchArtifacts/local_snapshot_v1/source_pilot_20260919_01')
SOURCE = Path('D:/ThetaData/data_options')
SPEC = Path('research_papers/JEPA/local_snapshot_v1/00_SOURCE_PILOT_CONTRACT.md')
MAX_FILE_BYTES = 64 * 1024**2
MIN_FREE_BYTES = 2 * 1024**3
NY = ZoneInfo('America/New_York')
START = datetime(2023, 1, 3, 9, 30, tzinfo=NY)
STOP = START + timedelta(hours=1)
ISO_START = '2023-01-03T09:30:00'
ISO_STOP = '2023-01-03T10:30:00'
TIMESTAMP = re.compile(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)?$')
NATIVE_TIMESTAMP = re.compile(
    r'^2023-01-03T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?$')
CODE_PATHS = (
    Path('neural/jepa/local_snapshot_source_v1.py'),
    Path('neural/jepa/audit_local_snapshot_source_v1.py'),
    Path('neural/jepa/local_snapshot_schema_v1.py'),
    Path('neural/jepa/multiscale_v1r1/artifacts.py'),
    Path('neural/jepa/multiscale_v1r1/provenance.py'),
    Path('tests/multiscale_v1r1/test_local_snapshot_source.py'),
    Path('tests/multiscale_v1r1/test_local_snapshot_audit.py'),
    SPEC,
)


def require(condition, message):
    if not condition:
        raise ValueError('LSP: ' + message)


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def decimal_text(value):
    number = Decimal(str(value))
    require(number.is_finite(), 'nonfinite decimal')
    result = format(number, 'f')
    return result.rstrip('0').rstrip('.') if '.' in result else result


def _decimal(value, *, positive, field):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError) as error:
        raise ValueError(f'LSP: malformed {field}') from error
    require(number.is_finite() and (number > 0 if positive else number >= 0),
            f'invalid {field}')
    return number


def _day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    require(isinstance(value, str), 'date type')
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError('LSP: malformed date') from error


def _clock(value):
    require(isinstance(value, str) and TIMESTAMP.fullmatch(value) is not None,
            'missing or non-ISO timestamp')
    fractional = re.search(r'\.(\d+)', value)
    require(fractional is None or len(fractional.group(1)) <= 6,
            'submicrosecond timestamp outside pilot')
    instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return instant.replace(tzinfo=NY) if instant.tzinfo is None else instant.astimezone(NY)


def _right(value):
    side = {'C': 'CALL', 'P': 'PUT'}.get(str(value).upper(), str(value).upper())
    require(side in ('CALL', 'PUT'), 'invalid option right')
    return side


def _identity(row, ticker, interval):
    require(row['symbol'] == ticker and _day(row['trade_date']) == date(2023, 1, 3)
            and _day(row['expiration']) == date(2023, 1, 3), 'file identity')
    require(row['interval_used'] == interval, 'source interval')
    side = _right(row['right'])
    strike = _decimal(row['strike'], positive=True, field='strike')
    return side, strike


def _oi_value(value):
    require(not isinstance(value, bool), 'malformed OI')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError) as error:
        raise ValueError('LSP: malformed OI') from error
    require(number.is_finite() and number >= 0 and number == number.to_integral_value(),
            'malformed OI')
    return int(number)


def _price(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None
    return number if number.is_finite() and number > 0 else None


def _age_ms(later, earlier):
    delta = later - earlier
    microseconds = ((delta.days*86400 + delta.seconds)*1000000
                    + delta.microseconds)
    return decimal_text(Decimal(microseconds) / Decimal(1000))


def sample_asof(sample, at):
    """Reject access before the assumed research availability clock."""
    at = _clock(at) if isinstance(at, str) else at
    require(at.tzinfo is not None, 'naive access clock')
    require(at >= _clock(sample['research_available_at']), 'early sample access')
    return sample if sample['mask'] else None


def diagnose(greek_rows, oi_rows, ticker, source_hashes):
    require(ticker in TICKERS, 'ticker outside pilot')
    require(set(source_hashes) == {'greeks', 'oi'}, 'source hash keys')
    for digest in source_hashes.values():
        require(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest),
                'source hash format')
    groups = {START + timedelta(minutes=minute): [] for minute in range(60)}
    keys = set()
    greek_contracts = set()
    greek_count = 0
    for row in greek_rows:
        require(set(row) == set(GREEK_COLUMNS), 'Greek projection changed')
        side, strike = _identity(row, ticker, '1m')
        instant = _clock(row['timestamp'])
        require(START <= instant < STOP and instant.second == 0
                and instant.microsecond == 0, 'Greek timestamp outside minute grid')
        underlying = _clock(row['underlying_timestamp'])
        require(underlying <= instant, 'future underlying timestamp')
        key = side, strike, instant
        require(key not in keys, 'duplicate contract/timestamp')
        keys.add(key)
        greek_contracts.add((side, strike))
        price = _price(row['underlying_price'])
        groups[instant].append((price, underlying))
        greek_count += 1
    samples = []
    for instant, observations in groups.items():
        count = len(observations)
        invalid = any(price is None or price <= 0 for price, _ in observations)
        disagreement = (len({(price, underlying) for price, underlying in observations}) > 1
                        if observations and not invalid else False)
        valid = count > 0 and not invalid and not disagreement
        reason = (None if valid else 'MISSING_SAMPLE' if count == 0 else
                  'INVALID_PRICE' if invalid else 'CROSS_CONTRACT_DISAGREEMENT')
        price, underlying = observations[0] if valid else (None, None)
        samples.append(dict(quote_timestamp=instant.isoformat(),
                            research_available_at=(instant + timedelta(minutes=1)).isoformat(),
                            mask=valid, reason=reason,
                            price=decimal_text(price) if valid else None,
                            underlying_timestamp=underlying.isoformat() if valid else None,
                            underlying_age_ms=_age_ms(instant, underlying)
                            if valid else None, source_rows=count))
    oi_entries = {}
    for row in oi_rows:
        require(set(row) == set(OI_COLUMNS), 'OI projection changed')
        side, strike = _identity(row, ticker, 'daily')
        key = side, strike
        require(key not in oi_entries, 'duplicate OI contract')
        instant = _clock(row['timestamp'])
        require(instant.date() == date(2023, 1, 3), 'OI timestamp date')
        value = _oi_value(row['open_interest'])
        after_open = instant > START
        zero = value == 0
        classification = ('AFTER_OPEN' if after_open else 'ZERO_OI' if zero
                          else 'ELIGIBLE_REPORTED_PREOPEN')
        oi_entries[key] = dict(right=side, strike=decimal_text(strike),
                               open_interest=value, timestamp=instant.isoformat(),
                               zero=zero, after_open=after_open,
                               classification=classification)
    def order(key):
        return (0 if key[0] == 'CALL' else 1, key[1])

    missing = sorted(greek_contracts - oi_entries.keys(), key=order)
    ineligible = sorted((key for key in greek_contracts & oi_entries.keys()
                         if oi_entries[key]['classification'] != 'ELIGIBLE_REPORTED_PREOPEN'),
                        key=order)
    def key_record(key):
        return dict(right=key[0], strike=decimal_text(key[1]))
    return dict(ticker=ticker, trade_date=DAY, greek_row_count=greek_count,
                oi_row_count=len(oi_entries), samples=samples,
                oi=[oi_entries[key] for key in sorted(oi_entries, key=order)],
                missing_oi_contracts=[key_record(key) for key in missing],
                ineligible_oi_contracts=[key_record(key) for key in ineligible],
                availability_basis=AVAILABILITY_BASIS,
                prior_close_semantics_verified=False, sources=source_hashes)


def source_path(base, ticker, kind):
    require(ticker in TICKERS and kind in ('greeks', 'oi'), 'source outside allowlist')
    return base / ticker / kind / '2023' / '01' / f'{ticker}_20230103_20230103_{kind}.parquet'


def read_projected(snapshot, kind, on_access=None):
    columns = GREEK_COLUMNS if kind == 'greeks' else OI_COLUMNS
    parquet = pq.ParquetFile(snapshot)
    fields = parquet.schema_arrow
    require(all(name in fields.names for name in columns), 'required Parquet field missing')
    require(fields.field('timestamp').type == pa.large_string(), 'timestamp is not large_string')
    if on_access is not None:
        on_access('SOURCE_CLOCK_VALIDATION', ['timestamp'], None, None)
    native_clocks = pq.read_table(snapshot, columns=['timestamp'])['timestamp'].to_pylist()
    require(all(isinstance(value, str) and NATIVE_TIMESTAMP.fullmatch(value)
                for value in native_clocks), 'native timestamp grammar')
    filters = [('timestamp', '>=', ISO_START), ('timestamp', '<', ISO_STOP)] if kind == 'greeks' else None
    if on_access is not None:
        on_access('PROJECTED_SOURCE_READ', list(columns),
                  ISO_START if kind == 'greeks' else None,
                  ISO_STOP if kind == 'greeks' else None)
    table = pq.read_table(snapshot, columns=list(columns), filters=filters)
    require(table.column_names == list(columns), 'Parquet projection mismatch')
    rows = table.to_pylist()
    require(all(set(row) == set(columns) for row in rows), 'forbidden column projected')
    return rows


def _publication():
    repo = Path(__file__).resolve().parents[2]
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
    head = git('rev-parse', 'HEAD')
    branch = git('branch', '--show-current')
    advertised = git('ls-remote', 'origin', f'refs/heads/{branch}').split()
    require(advertised and advertised[0] == head, 'unpublished HEAD')
    for path in CODE_PATHS:
        relative = path.as_posix()
        require(not git('status', '--porcelain', '--', relative),
                f'uncommitted code: {relative}')
        require(git('ls-files', '--error-unmatch', '--', relative),
                f'untracked code: {relative}')
        frozen = subprocess.check_output(['git', '-C', str(repo), 'show',
                                          f'HEAD:{relative}'])
        require(frozen.replace(b'\r\n', b'\n')
                == path.read_bytes().replace(b'\r\n', b'\n'),
                f'working bytes differ from HEAD: {relative}')
    return head


def _copy_sources(paths, staging):
    records = []
    folder = staging / 'snapshot'
    folder.mkdir()
    with coherent_read_handles([source for _, _, source in paths]) as streams:
        for (ticker, kind, source), stream in zip(paths, streams, strict=True):
            relative = f'snapshot/{ticker}_{kind}.parquet'
            target = staging / relative
            digest = hashlib.sha256()
            size = 0
            with target.open('xb') as output:
                for block in iter(lambda: stream.read(1024**2), b''):
                    size += len(block)
                    require(size <= MAX_FILE_BYTES, 'source exceeds file cap')
                    output.write(block)
                    digest.update(block)
                output.flush()
                os.fsync(output.fileno())
            records.append(dict(ticker=ticker, kind=kind, snapshot_path=relative,
                                source_path=str(source), sha256=digest.hexdigest(), bytes=size))
    return records


def _log(staging, record):
    path = staging / 'access_log.jsonl'
    with path.open('ab') as stream:
        stream.write(json.dumps(record, sort_keys=True).encode() + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def run(root, authorization_reference, *, source_base=SOURCE, verify_publication=True):
    root = Path(root).resolve()
    base = Path(source_base).resolve()
    require(authorization_reference == AUTHORIZATION, 'authorization reference')
    if verify_publication:
        require(root == OUTPUT.resolve() and base == SOURCE.resolve(), 'fixed CLI scope')
        head = _publication()
    else:
        head = 'SYNTHETIC_TEST_ONLY'
    paths = [(ticker, kind, source_path(base, ticker, kind))
             for ticker in TICKERS for kind in ('greeks', 'oi')]
    with stage(root) as staging:
        status = 'BLOCKED_LOCAL_SOURCE'
        reason = None
        audit = dict(status='NOT_RUN')
        audit_started = False
        source_diagnostic = dict(trade_date=DAY, tickers={})
        manifest = dict(head=head, authorization_reference=authorization_reference,
                        snapshot_created_at=datetime.now(timezone.utc).isoformat(),
                        sources=[], code={}, runtime=dict(python=sys.version.split()[0],
                                                        pyarrow=pa.__version__,
                                                        platform=platform.platform()))
        try:
            require(shutil.disk_usage(root.parent).free >= MIN_FREE_BYTES + 6*MAX_FILE_BYTES,
                    'insufficient disk reserve')
            for _, _, path in paths:
                require(path.is_file(), f'missing source: {path}')
                require(path.stat().st_size <= MAX_FILE_BYTES, f'source exceeds cap: {path}')
            manifest['code'] = {path.as_posix(): checksum(path) for path in CODE_PATHS}
            manifest['sources'] = _copy_sources(paths, staging)
            write_json(staging / 'manifest.json', manifest)
            _log(staging, dict(event='MANIFEST_SEALED_BEFORE_VALUES',
                               source_count=len(manifest['sources'])))
            for ticker in TICKERS:
                rows = {}
                hashes = {}
                for kind in ('greeks', 'oi'):
                    record = next(item for item in manifest['sources']
                                  if item['ticker'] == ticker and item['kind'] == kind)
                    snapshot = staging / record['snapshot_path']
                    require(checksum(snapshot) == record['sha256'], 'snapshot hash changed')
                    def log_access(event, columns, lower, upper):
                        _log(staging, dict(event=event, ticker=ticker, kind=kind,
                                           columns=columns, time_lower=lower,
                                           time_upper_exclusive=upper))

                    rows[kind] = read_projected(snapshot, kind, on_access=log_access)
                    hashes[kind] = record['sha256']
                source_diagnostic['tickers'][ticker] = diagnose(rows['greeks'], rows['oi'], ticker, hashes)
            write_json(staging / 'source_diagnostic.json', source_diagnostic)
            from neural.jepa.audit_local_snapshot_source_v1 import audit_directory
            audit_started = True
            audit = audit_directory(staging)
            require(audit.get('status') == 'PASS_LOCAL_SOURCE_DIAGNOSTIC_AUDIT',
                    'independent audit failed')
            status = 'LOCAL_SOURCE_DIAGNOSTIC_COMPLETE'
        except Exception as error:
            reason = f'{type(error).__name__}: {error}'
            if audit_started:
                status = 'FAILED_AUDIT'
                if audit.get('status') != 'FAILED_AUDIT':
                    audit = dict(status='FAILED_AUDIT', reason=reason)
        if not (staging / 'manifest.json').exists():
            write_json(staging / 'manifest.json', manifest)
        if not (staging / 'source_diagnostic.json').exists():
            write_json(staging / 'source_diagnostic.json', source_diagnostic)
        if not (staging / 'access_log.jsonl').exists():
            (staging / 'access_log.jsonl').open('xb').close()
        write_json(staging / 'audit.json', audit)
        summary = dict(status=status, reason=reason, audit_status=audit.get('status'),
                       historical_economic_admission=False, original_vintage_verified=False,
                       economic_evidence_state='NOT_EVALUATED',
                       prospective_validation_state='NOT_STARTED', technical_ready=False,
                       promotion_approved=False, sources=len(manifest['sources']),
                       head=head, authorization_reference=authorization_reference)
        write_json(staging / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--authorization-reference', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.authorization_reference), indent=2))


if __name__ == '__main__':
    main()
