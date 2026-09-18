"""Offline, scope-limited reconstruction from the six published source responses."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import uuid

import exchange_calendars as xcals
import pandas as pd

from neural.jepa.multiscale_v1r1.provenance import coherent_read_handles

TICKERS = ('SPXW', 'SPY', 'QQQ')
DAY = '2022-08-01'
NY = 'America/New_York'
PUBLISHED = '600c959b1421eaf98d47398fca88a2e2bed42848'
CATALOG = 'research_papers/JEPA/multiscale_v1r1/api_intake_evidence/api_artifact_catalog.json'
SPEC = 'research_papers/JEPA/multiscale_v1r1/22_RECONSTRUCTED_SOURCE_CONTRACT.md'


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def clock(value):
    timestamp = pd.Timestamp(value)
    require(not pd.isna(timestamp), 'SRC-002: missing clock')
    return timestamp.tz_localize(NY) if timestamp.tzinfo is None else timestamp.tz_convert(NY)


def number(value):
    parsed = Decimal(str(value))
    return parsed if parsed.is_finite() else None


def text(value):
    return None if value is None else format(value.normalize(), 'f')


def identities(frame, ticker, day):
    keys = []
    for row in frame.to_dict('records'):
        strike = number(row['strike'])
        right = row['right'].upper()
        right = {'C': 'CALL', 'P': 'PUT'}.get(right, right)
        require(row['symbol'] == ticker and str(pd.Timestamp(row['expiration']).date()) == day
                and right in ('CALL', 'PUT') and strike is not None and strike > 0, 'SRC-001: contract identity')
        keys.append(f'{ticker}|{day}|{right}|{text(strike)}')
    return keys


def reconstruct_bar(payload, ticker, day, endpoint):
    frame = pd.read_csv(io.BytesIO(payload), dtype=str, keep_default_na=False)
    require({'timestamp', 'underlying_timestamp', 'underlying_price', 'symbol', 'expiration', 'right', 'strike'} <= set(frame), 'BAR-001: schema')
    begin = clock(day + ' 09:30')
    end = begin + pd.Timedelta(minutes=1)
    timestamps = frame.timestamp.map(clock)
    frame = frame.loc[(timestamps >= begin) & (timestamps < end)].copy()
    frame['source_row'] = frame.index
    frame['when'] = timestamps.loc[frame.index]
    frame['key'] = identities(frame, ticker, day)
    require(not frame.duplicated(['key', 'when'], keep=False).any(), 'BAR-001: duplicate native key')
    expected = list(pd.date_range(begin, end, freq='s', inclusive='left'))
    require(sorted(frame.when.unique()) == expected, 'BAR-001: missing/subsecond clock')
    frame['underlying_when'] = frame.underlying_timestamp.map(clock)
    require((frame.underlying_when <= frame.when).all(), 'BAR-002: future underlying dependency')
    frame['price'] = frame.underlying_price.map(number)
    observations = []
    for instant, group in frame.groupby('when', sort=True):
        prices = {text(p) for p in group.price}
        require(len(prices) == 1 and group.underlying_when.nunique() == 1, 'BAR-001: cross-contract disagreement')
        value = group.price.iloc[0]
        require(value is not None and value > 0 or ticker == 'SPXW' and instant == begin, 'BAR-003: invalid later/other-ticker price')
        observations.append((instant, value))
    values = [p for _, p in observations]
    finite = [p for p in values if p is not None]
    require(finite, 'BAR-003: no finite prices')
    original = dict(open=values[0], high=max(finite), low=min(finite) if len(finite) == len(values) else None, close=values[-1])
    repaired = dict(original)
    invalid = [name for name, value in original.items() if value is None or value <= 0]
    close_rows = frame.loc[frame.when == expected[-1]]
    repair = None
    if invalid:
        require(ticker == 'SPXW' and original['close'] is not None and original['close'] > 0, 'BAR-003: unauthorized repair')
        for name in invalid:
            repaired[name] = original['close']
        repair = dict(repair_kind='SPXW_INITIAL_ZERO_BAR', repaired_fields=invalid,
                      replacement_quote_timestamp=expected[-1].isoformat(),
                      replacement_underlying_timestamp=close_rows.underlying_when.iloc[0].isoformat(),
                      replacement_source_rows=[int(i) for i in close_rows.source_row],
                      effective_available_at=end.isoformat())
    require(repaired['high'] >= max(repaired.values()) and repaired['low'] <= min(repaired.values()), 'BAR-003: inconsistent repaired OHLC')
    require(clock(endpoint) >= end, 'BAR-002: bar unavailable at endpoint')
    return dict(ticker=ticker, trade_date=day, timestamp=begin.isoformat(),
                reported_available_at=end.isoformat(), source_sha256=sha(payload),
                original_ohlc={k: text(v) for k, v in original.items()},
                ohlc={k: text(v) for k, v in repaired.items()}, tick_count=len(frame),
                seconds=60, contracts=frame.key.nunique(), repair=repair,
                original_vintage_verified=False)


def classify_oi(payload, ticker, day, previous_close):
    frame = pd.read_csv(io.BytesIO(payload), dtype=str, keep_default_na=False)
    require({'timestamp', 'open_interest', 'symbol', 'expiration', 'right', 'strike'} <= set(frame), 'OI-001: schema')
    keys = identities(frame, ticker, day)
    require(len(set(keys)) == len(keys), 'OI-001: duplicate key')
    opening = clock(day + ' 09:30')
    result = []
    for index, row in enumerate(frame.to_dict('records')):
        when = clock(row['timestamp'])
        value = number(row['open_interest'])
        require(when.date().isoformat() == day and value is not None and value >= 0 and value == value.to_integral_value(), 'OI-001: invalid OI')
        require(clock(previous_close) < opening.normalize(), 'OI-001: prior-close clock')
        reason = 'AFTER_OPEN' if when > opening else 'ZERO_OI' if value == 0 else 'ELIGIBLE_PREMARKET_POSITIVE'
        result.append(dict(contract_key=keys[index], source_row=index, open_interest=int(value),
                           provider_event_timestamp=when.isoformat(), reported_available_at=when.isoformat(),
                           as_of=clock(previous_close).isoformat(), reason=reason,
                           eligible=reason == 'ELIGIBLE_PREMARKET_POSITIVE', source_sha256=sha(payload),
                           original_reception_observed=False))
    return result


def run(destination):
    catalog_bytes = subprocess.check_output(['git', 'show', f'{PUBLISHED}:{CATALOG}'])
    require(Path(CATALOG).read_bytes() == catalog_bytes, 'SRC-003: published catalog changed')
    code = [Path(__file__), Path(__file__).with_name('audit_theta_reconstructed_source_v1.py'), Path(SPEC),
            Path('neural/jepa/multiscale_v1r1/provenance.py')]
    require(importlib.metadata.version('exchange_calendars') == '4.12', 'SRC-003: calendar runtime changed')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    remote = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/research/multiscale-v1r1-net-usd'], text=True).split()[0]
    require(head == remote, 'SRC-003: code must be published')
    for path in code:
        relative = path.resolve().relative_to(Path.cwd()).as_posix()
        require(subprocess.check_output(['git', 'show', f'HEAD:{relative}']).replace(b'\r\n', b'\n') == path.read_bytes().replace(b'\r\n', b'\n'), 'SRC-003: unpublished code/spec')
    directory = Path(destination).resolve()
    require(not directory.exists(), 'SRC-003: destination exists')
    staging = directory.with_name(directory.name + '.staging-' + uuid.uuid4().hex)
    staging.mkdir(parents=True)
    inputs = staging / 'inputs'
    inputs.mkdir()
    entries = [e for e in json.loads(catalog_bytes)['artifacts']
               if Path(e['path']).parent.parent.name == 'theta_source_pilot_20260918_01'
               and Path(e['path']).name in ('response.bin', 'manifest.json')]
    require(len(entries) == 12, 'SRC-001: exact input set required')
    records, captured_bytes = [], {}
    with coherent_read_handles([e['path'] for e in entries]) as streams:
        for entry, stream in zip(entries, streams, strict=True):
            payload = stream.read()
            require(sha(payload) == entry['sha256'] and len(payload) == entry['bytes'], 'SRC-003: input changed')
            source = Path(entry['path'])
            name = source.parent.name + '_' + source.name
            (inputs / name).write_bytes(payload)
            captured_bytes[name] = payload
            records.append(dict(original_path=str(source), copy=name, sha256=sha(payload), bytes=len(payload)))
    captured = datetime.now(timezone.utc).isoformat()
    cal = xcals.get_calendar('XNYS')
    previous = cal.previous_session(DAY)
    previous_close = cal.session_close(previous).tz_convert(NY).isoformat()
    provenance = dict(contract='THETA_RECONSTRUCTED_SOURCE_V1', code_head=head,
                      code={p.name: sha(p.read_bytes()) for p in code},
                      captured_at=captured, inputs=records, calendar='XNYS',
                      previous_session=str(previous.date()), previous_close=previous_close,
                      original_vintage_verified=False, historical_economic_admission=False)
    save(staging / 'manifest.json', provenance)
    for path in code:
        shutil.copyfile(path, staging / path.name)
    try:
        bars, interest, lineage, missing = {}, {}, {}, {}
        for i, ticker in enumerate(TICKERS):
            greek = captured_bytes[f'{i:02d}_{ticker}_greeks_response.bin']
            oi = captured_bytes[f'{i + 3:02d}_{ticker}_oi_response.bin']
            for index, kind in ((i, 'greeks'), (i + 3, 'oi')):
                meta = json.loads(captured_bytes[f'{index:02d}_{ticker}_{kind}_manifest.json'])
                expected = dict(symbol=ticker, expiration='20220801', date='20220801', strike='*', right='both', format='csv')
                if kind == 'greeks':
                    expected.update(interval='1s', start_time='09:30:00', end_time='09:31:00', version='1')
                require(meta['params'] == expected and meta['http_status'] == 200 and meta['complete']
                        and meta['ticker'] == ticker and meta['kind'] == kind, 'SRC-001: request scope')
                lineage[f'{ticker}_{kind}'] = dict(source_sha256=meta['sha256'],
                    received_at=meta['received_at'], source_materialized_at=None,
                    source_materialization_basis='not separately logged; persisted after receipt',
                    reconstruction_started_at=captured, original_reception_observed=False,
                    reported_clock_basis='provider response; original historical vintage unknown',
                    as_of_basis='https://docs.thetadata.us/operations/option_history_open_interest.html' if kind == 'oi' else None)
            bars[ticker] = reconstruct_bar(greek, ticker, DAY, DAY + ' 09:31')
            interest[ticker] = classify_oi(oi, ticker, DAY, previous_close)
            quote_frame = pd.read_csv(io.BytesIO(greek), dtype=str, keep_default_na=False)
            times = quote_frame.timestamp.map(clock)
            quote_frame = quote_frame.loc[(times >= clock(DAY + ' 09:30')) & (times < clock(DAY + ' 09:31'))]
            absent = set(identities(quote_frame, ticker, DAY)) - {r['contract_key'] for r in interest[ticker]}
            missing[ticker] = [dict(contract_key=key, reason='MISSING_OI', eligible=False) for key in sorted(absent)]
        save(staging / 'first_bars.json', bars)
        save(staging / 'oi_eligibility.json', interest)
        save(staging / 'lineage.json', lineage)
        save(staging / 'missing_oi.json', missing)
        from neural.jepa.audit_theta_reconstructed_source_v1 import audit
        verified = audit(staging)
        save(staging / 'audit.json', verified)
        result = dict(status='PASS_RECONSTRUCTED_SOURCE_COMPONENTS', audit=verified,
                      scope='three first-minute bars and per-record OI only',
                      original_vintage_verified=False, historical_economic_admission=False,
                      economic_evidence_state='NOT_EVALUATED', promotion_approved=False)
    except Exception as error:
        result = dict(status='BLOCKED_SOURCE_COMPONENTS', reason=f'{type(error).__name__}: {error}',
                      original_vintage_verified=False, historical_economic_admission=False,
                      economic_evidence_state='NOT_EVALUATED', promotion_approved=False)
    save(staging / 'summary.json', result)
    staging.rename(directory)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.root), indent=2))
