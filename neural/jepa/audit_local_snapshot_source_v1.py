"""Independent semantic oracle for the local, outcome-free snapshot pilot."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq

from neural.jepa.local_snapshot_schema_v1 import (
    AVAILABILITY_BASIS,
    DAY,
    GREEK_COLUMNS,
    OI_COLUMNS,
    OI_FIELDS,
    SAMPLE_FIELDS,
    TICKERS,
)


ET = ZoneInfo('America/New_York')
OPEN = datetime(2023, 1, 3, 9, 30, tzinfo=ET)
END = OPEN + timedelta(hours=1)
RIGHT_ORDER = {'CALL': 0, 'PUT': 1}
SOURCE_CLOCK = re.compile(r'^2023-01-03T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?$')
PARSED_CLOCK = re.compile(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)?$')


def _fail(reason: str):
    raise ValueError('AUDIT_LOCAL_SOURCE: ' + reason)


def _day(value) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    if len(text) == 8 and text.isdecimal():
        text = f'{text[:4]}-{text[4:6]}-{text[6:]}'
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        _fail('invalid date')


def _instant(value) -> datetime:
    if value is None:
        _fail('missing timestamp')
    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            text = str(value)
            if PARSED_CLOCK.fullmatch(text) is None:
                _fail('invalid timestamp format')
            parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
        return (parsed.replace(tzinfo=ET) if parsed.tzinfo is None else parsed.astimezone(ET))
    except ValueError:
        _fail('invalid timestamp')


def _strike(value) -> Decimal:
    try:
        number = Decimal(str(value))
        if number.is_finite() and number > 0:
            return number
    except (InvalidOperation, TypeError):
        pass
    _fail('invalid strike')


def _decimal_text(number: Decimal) -> str:
    text = format(number, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def _age_ms(older: datetime, newer: datetime) -> str:
    delta = newer - older
    micros = (delta.days * 86_400_000_000 + delta.seconds * 1_000_000
              + delta.microseconds)
    return _decimal_text(Decimal(micros) / Decimal(1000))


def _right(value) -> str:
    spelling = str(value).upper()
    right = {'C': 'CALL', 'P': 'PUT'}.get(spelling, spelling)
    if right not in RIGHT_ORDER:
        _fail('invalid right')
    return right


def _identity(row: dict, ticker: str, kind: str) -> tuple[str, Decimal]:
    if row.get('symbol') != ticker or _day(row.get('trade_date')) != DAY or _day(row.get('expiration')) != DAY:
        _fail(kind + ' file identity mismatch')
    if row.get('interval_used') != ('1m' if kind == 'greeks' else 'daily'):
        _fail(kind + ' interval mismatch')
    return _right(row.get('right')), _strike(row.get('strike'))


def reconstruct(greek_rows, oi_rows, ticker, source_hashes):
    """Rebuild the fixed 60-minute diagnostic without producer calculations."""
    if ticker not in TICKERS:
        _fail('unexpected ticker')
    if set(source_hashes) != {'greeks', 'oi'} or any(
            not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None
            for value in source_hashes.values()):
        _fail('source hash format')
    minutes: dict[datetime, list[tuple[Decimal | None, datetime]]] = {}
    greek_contracts: set[tuple[str, Decimal]] = set()
    native_quotes: set[tuple[str, Decimal, datetime]] = set()
    greek_count = 0
    for row in greek_rows:
        if set(row) != set(GREEK_COLUMNS):
            _fail('Greek projection changed')
        contract = _identity(row, ticker, 'greeks')
        quote_time = _instant(row.get('timestamp'))
        if not OPEN <= quote_time < END or quote_time.second or quote_time.microsecond:
            _fail('Greek timestamp outside fixed minute grid')
        native_key = (*contract, quote_time)
        if native_key in native_quotes:
            _fail('duplicate native Greek quote')
        native_quotes.add(native_key)
        underlying_time = _instant(row.get('underlying_timestamp'))
        if underlying_time > quote_time:
            _fail('future underlying dependency')
        try:
            value = Decimal(str(row.get('underlying_price')))
            price = value if value.is_finite() and value > 0 else None
        except (InvalidOperation, TypeError):
            price = None
        minutes.setdefault(quote_time, []).append((price, underlying_time))
        greek_contracts.add(contract)
        greek_count += 1

    samples = []
    for minute_offset in range(60):
        quote_time = OPEN + timedelta(minutes=minute_offset)
        records = minutes.get(quote_time, [])
        reason = None
        if not records:
            reason = 'MISSING_SAMPLE'
        elif any(price is None for price, _ in records):
            reason = 'INVALID_PRICE'
        elif len(set(records)) != 1:
            reason = 'CROSS_CONTRACT_DISAGREEMENT'
        price, underlying_time = records[0] if reason is None else (None, None)
        values = (
            quote_time.isoformat(),
            (quote_time + timedelta(minutes=1)).isoformat(),
            reason is None,
            reason,
            _decimal_text(price) if price is not None else None,
            underlying_time.isoformat() if underlying_time is not None else None,
            _age_ms(underlying_time, quote_time) if underlying_time is not None else None,
            len(records),
        )
        samples.append(dict(zip(SAMPLE_FIELDS, values, strict=True)))

    oi_by_contract: dict[tuple[str, Decimal], dict] = {}
    for row in oi_rows:
        if set(row) != set(OI_COLUMNS):
            _fail('OI projection changed')
        contract = _identity(row, ticker, 'oi')
        if contract in oi_by_contract:
            _fail('duplicate OI contract')
        timestamp = _instant(row.get('timestamp'))
        if timestamp.date().isoformat() != DAY:
            _fail('OI timestamp outside session')
        raw_amount = row.get('open_interest')
        if isinstance(raw_amount, bool):
            _fail('invalid open_interest')
        try:
            amount_decimal = Decimal(str(raw_amount))
            if (not amount_decimal.is_finite() or amount_decimal < 0
                    or amount_decimal != amount_decimal.to_integral_value()):
                _fail('invalid open_interest')
        except (InvalidOperation, TypeError):
            _fail('invalid open_interest')
        amount = int(amount_decimal)
        late = timestamp > OPEN
        zero = amount == 0
        classification = 'AFTER_OPEN' if late else 'ZERO_OI' if zero else 'ELIGIBLE_REPORTED_PREOPEN'
        values = (contract[0], _decimal_text(contract[1]), int(amount), timestamp.isoformat(),
                  zero, late, classification)
        oi_by_contract[contract] = dict(zip(OI_FIELDS, values, strict=True))

    def sorted_contracts(contracts):
        return sorted(contracts, key=lambda key: (RIGHT_ORDER[key[0]], key[1]))

    def pair(key):
        return {'right': key[0], 'strike': _decimal_text(key[1])}

    return {
        'ticker': ticker,
        'trade_date': DAY,
        'greek_row_count': greek_count,
        'oi_row_count': len(oi_by_contract),
        'samples': samples,
        'oi': [oi_by_contract[key] for key in sorted_contracts(oi_by_contract)],
        'missing_oi_contracts': [pair(key) for key in sorted_contracts(greek_contracts - oi_by_contract.keys())],
        'ineligible_oi_contracts': [pair(key) for key in sorted_contracts(
            key for key in greek_contracts & oi_by_contract.keys()
            if oi_by_contract[key]['classification'] != 'ELIGIBLE_REPORTED_PREOPEN')],
        'availability_basis': AVAILABILITY_BASIS,
        'prior_close_semantics_verified': False,
        'sources': source_hashes,
    }


def _sealed_file(root: Path, item: dict) -> Path:
    ticker, kind = item.get('ticker'), item.get('kind')
    if ticker not in TICKERS or kind not in ('greeks', 'oi'):
        _fail('unexpected source identity')
    expected = f'D:/ThetaData/data_options/{ticker}/{kind}/2023/01/{ticker}_20230103_20230103_{kind}.parquet'
    if item.get('source_path', '').replace('\\', '/') != expected:
        _fail('source path outside fixed allowlist')
    if (not isinstance(item.get('bytes'), int) or not 0 < item['bytes'] <= 64 * 1024**2
            or not isinstance(item.get('sha256'), str)
            or re.fullmatch(r'[0-9a-f]{64}', item['sha256']) is None):
        _fail('source size or hash format mismatch')
    candidate = (root / item['snapshot_path']).resolve()
    if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
        _fail('snapshot path outside root or absent')
    blob = candidate.read_bytes()
    if len(blob) != item.get('bytes') or hashlib.sha256(blob).hexdigest() != item.get('sha256'):
        _fail('sealed source hash/size mismatch')
    return candidate


def _project(path: Path, kind: str):
    columns = GREEK_COLUMNS if kind == 'greeks' else OI_COLUMNS
    footer = pq.read_metadata(path)
    schema = footer.schema.to_arrow_schema()
    if any(name not in schema.names for name in columns) or schema.field('timestamp').type != pa.large_string():
        _fail('source schema mismatch')
    clock_rows = pq.read_table(path, columns=['timestamp']).column('timestamp').to_pylist()
    if any(not isinstance(value, str) or SOURCE_CLOCK.fullmatch(value) is None for value in clock_rows):
        _fail('native source clock format mismatch')
    filters = [('timestamp', '>=', DAY + 'T09:30:00'), ('timestamp', '<', DAY + 'T10:30:00')]
    table = pq.read_table(path, columns=list(columns), filters=filters if kind == 'greeks' else None)
    return table.to_pylist()


def audit_directory(root):
    """Re-read six sealed snapshots and compare the producer diagnostic exactly."""
    root = Path(root).resolve()
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    sources = manifest.get('sources')
    if not isinstance(sources, list) or len(sources) != 6:
        _fail('manifest must contain exactly six sources')
    source_map = {(item.get('ticker'), item.get('kind')): item for item in sources}
    if len(source_map) != 6 or set(source_map) != {(ticker, kind) for ticker in TICKERS for kind in ('greeks', 'oi')}:
        _fail('missing or duplicate source identity')
    files = {key: _sealed_file(root, item) for key, item in source_map.items()}
    actual = json.loads((root / 'source_diagnostic.json').read_text(encoding='utf-8'))
    if actual.get('trade_date') != DAY or set(actual.get('tickers', {})) != set(TICKERS):
        _fail('diagnostic scope mismatch')
    for ticker in TICKERS:
        source_hashes = {'greeks': source_map[ticker, 'greeks']['sha256'], 'oi': source_map[ticker, 'oi']['sha256']}
        expected = reconstruct(_project(files[ticker, 'greeks'], 'greeks'),
                               _project(files[ticker, 'oi'], 'oi'), ticker, source_hashes)
        if actual['tickers'][ticker] != expected:
            _fail(ticker + ' diagnostic mismatch')
    return {'status': 'PASS_LOCAL_SOURCE_DIAGNOSTIC_AUDIT', 'source_count': 6, 'mismatch_count': 0}
