"""Independent standard-library reconstruction of the limited Theta source scope."""
import csv
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import io
import importlib.metadata
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

import exchange_calendars

NY = ZoneInfo('America/New_York')


def check(condition, reason):
    if not condition:
        raise ValueError('AUDIT: ' + reason)


def date_time(value):
    parsed = datetime.fromisoformat(str(value))
    return parsed.replace(tzinfo=NY) if parsed.tzinfo is None else parsed.astimezone(NY)


def decimal(value):
    number = Decimal(value)
    return number if number.is_finite() else None


def formatted(value):
    return None if value is None else format(value.normalize(), 'f')


def key(row, ticker, day):
    amount = decimal(row['strike'])
    side = {'C': 'CALL', 'P': 'PUT'}.get(row['right'].upper(), row['right'].upper())
    check(row['symbol'] == ticker and date_time(row['expiration']).date().isoformat() == day
          and side in ('CALL', 'PUT') and amount is not None and amount > 0, 'contract identity')
    return '|'.join([ticker, day, side, formatted(amount)])


def expected_bar(payload, ticker, day, endpoint):
    rows = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
    start = date_time(day + ' 09:30:00')
    stop = start + timedelta(minutes=1)
    check(date_time(endpoint) >= stop, 'bar unavailable')
    seconds, seen, selected = {}, set(), []
    for row_id, row in enumerate(rows):
        instant = date_time(row['timestamp'])
        if not start <= instant < stop:
            continue
        identity = key(row, ticker, day)
        check((identity, instant) not in seen, 'duplicate quote')
        seen.add((identity, instant))
        source_time = date_time(row['underlying_timestamp'])
        check(source_time <= instant, 'future underlying')
        price = decimal(row['underlying_price'])
        check(price is not None and price > 0 or ticker == 'SPXW' and instant == start, 'invalid price outside exception')
        observation = (formatted(price), source_time)
        if instant in seconds:
            check(seconds[instant] == observation, 'cross-contract disagreement')
        seconds[instant] = observation
        selected.append((row_id, identity, instant, source_time))
    required = [start + timedelta(seconds=i) for i in range(60)]
    check(set(seconds) == set(required), 'missing/subsecond observations')
    values = [None if seconds[t][0] is None else Decimal(seconds[t][0]) for t in required]
    finite = [x for x in values if x is not None]
    check(finite, 'no prices')
    old = dict(open=values[0], high=max(finite), low=min(finite) if len(finite) == 60 else None, close=values[-1])
    new = dict(old)
    fields = [k for k in ('open', 'high', 'low', 'close') if old[k] is None or old[k] <= 0]
    repair = None
    if fields:
        check(ticker == 'SPXW' and old['close'] is not None and old['close'] > 0, 'invalid repair')
        new.update({k: old['close'] for k in fields})
        last = required[-1]
        repair = dict(repair_kind='SPXW_INITIAL_ZERO_BAR', repaired_fields=fields,
                      replacement_quote_timestamp=last.isoformat(),
                      replacement_underlying_timestamp=seconds[last][1].isoformat(),
                      replacement_source_rows=[i for i, _, t, _ in selected if t == last],
                      effective_available_at=stop.isoformat())
    check(new['low'] <= min(new.values()) and new['high'] >= max(new.values()), 'inconsistent OHLC')
    return dict(ticker=ticker, trade_date=day, timestamp=start.isoformat(),
                reported_available_at=stop.isoformat(), source_sha256=hashlib.sha256(payload).hexdigest(),
                original_ohlc={k: formatted(v) for k, v in old.items()}, ohlc={k: formatted(v) for k, v in new.items()},
                tick_count=len(selected), seconds=60, contracts=len({k for _, k, _, _ in selected}),
                repair=repair, original_vintage_verified=False)


def expected_oi(payload, ticker, day, previous_close):
    opening = date_time(day + ' 09:30:00')
    past_close = date_time(previous_close)
    check(past_close < date_time(day + ' 00:00:00'), 'prior close')
    rows, seen = [], set()
    for index, row in enumerate(csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))):
        identity = key(row, ticker, day)
        check(identity not in seen, 'duplicate OI')
        seen.add(identity)
        value, instant = decimal(row['open_interest']), date_time(row['timestamp'])
        check(value is not None and value >= 0 and value == int(value) and instant.date().isoformat() == day, 'invalid OI')
        reason = 'AFTER_OPEN' if instant > opening else 'ZERO_OI' if value == 0 else 'ELIGIBLE_PREMARKET_POSITIVE'
        rows.append(dict(contract_key=identity, source_row=index, open_interest=int(value),
                         provider_event_timestamp=instant.isoformat(), reported_available_at=instant.isoformat(),
                         as_of=past_close.isoformat(), reason=reason, eligible=reason == 'ELIGIBLE_PREMARKET_POSITIVE',
                         source_sha256=hashlib.sha256(payload).hexdigest(), original_reception_observed=False))
    return rows


def compare_components(greek_payloads, oi_payloads, bars, interest, previous_close):
    for ticker in ('SPXW', 'SPY', 'QQQ'):
        check(expected_bar(greek_payloads[ticker], ticker, '2022-08-01', '2022-08-01 09:31') == bars[ticker], 'bar/repair/availability mismatch')
        check(expected_oi(oi_payloads[ticker], ticker, '2022-08-01', previous_close) == interest[ticker], 'OI classification mismatch')


def audit(directory):
    root = Path(directory)
    manifest = json.loads((root / 'manifest.json').read_bytes())
    check(manifest['contract'] == 'THETA_RECONSTRUCTED_SOURCE_V1' and manifest['original_vintage_verified'] is False
          and manifest['historical_economic_admission'] is False, 'scope/vintage')
    catalog = json.loads(subprocess.check_output(['git', 'show', '600c959b1421eaf98d47398fca88a2e2bed42848:research_papers/JEPA/multiscale_v1r1/api_intake_evidence/api_artifact_catalog.json']))
    sealed = {e['path']: e for e in catalog['artifacts'] if Path(e['path']).parent.parent.name == 'theta_source_pilot_20260918_01'
              and Path(e['path']).name in ('manifest.json', 'response.bin')}
    check(len(manifest['inputs']) == 12 and {e['original_path'] for e in manifest['inputs']} == set(sealed), 'input universe')
    captured = {}
    for item in manifest['inputs']:
        original = sealed[item['original_path']]
        source = Path(item['original_path'])
        check(item['copy'] == source.parent.name + '_' + source.name, 'input copy path')
        raw = (root / 'inputs' / item['copy']).read_bytes()
        check(hashlib.sha256(raw).hexdigest() == item['sha256'] == original['sha256']
              and len(raw) == item['bytes'] == original['bytes'], 'sealed dependency changed')
        captured[item['copy']] = raw
    for name, digest in manifest['code'].items():
        check(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, 'code copy changed')
    check(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == manifest['code'][Path(__file__).name], 'auditor runtime code changed')
    check(importlib.metadata.version('exchange_calendars') == '4.12', 'calendar runtime changed')
    cal = exchange_calendars.get_calendar('XNYS')
    session = cal.previous_session('2022-08-01')
    expected_close = cal.session_close(session).tz_convert('America/New_York').isoformat()
    check(manifest['previous_session'] == str(session.date()) and manifest['previous_close'] == expected_close, 'calendar prior close')
    greek, oi = {}, {}
    lineage = json.loads((root / 'lineage.json').read_bytes())
    check(set(lineage) == {f'{t}_{k}' for t in ('SPXW', 'SPY', 'QQQ') for k in ('greeks', 'oi')}, 'lineage universe')
    for i, ticker in enumerate(('SPXW', 'SPY', 'QQQ')):
        greek[ticker] = captured[f'{i:02d}_{ticker}_greeks_response.bin']
        oi[ticker] = captured[f'{i+3:02d}_{ticker}_oi_response.bin']
        for index, kind in ((i, 'greeks'), (i+3, 'oi')):
            meta = json.loads(captured[f'{index:02d}_{ticker}_{kind}_manifest.json'])
            record = lineage[f'{ticker}_{kind}']
            expected_lineage = dict(source_sha256=meta['sha256'], received_at=meta['received_at'],
                source_materialized_at=None, source_materialization_basis='not separately logged; persisted after receipt',
                reconstruction_started_at=manifest['captured_at'], original_reception_observed=False,
                reported_clock_basis='provider response; original historical vintage unknown',
                as_of_basis='https://docs.thetadata.us/operations/option_history_open_interest.html' if kind == 'oi' else None)
            check(record == expected_lineage, 'lineage/receipt/materialization mismatch')
    bars = json.loads((root / 'first_bars.json').read_bytes())
    interest = json.loads((root / 'oi_eligibility.json').read_bytes())
    compare_components(greek, oi, bars, interest, expected_close)
    missing = json.loads((root / 'missing_oi.json').read_bytes())
    for ticker in greek:
        quoted = {key(row, ticker, '2022-08-01') for row in csv.DictReader(io.StringIO(greek[ticker].decode('utf-8-sig')))
                  if date_time('2022-08-01 09:30') <= date_time(row['timestamp']) < date_time('2022-08-01 09:31')}
        absent = quoted - {row['contract_key'] for row in interest[ticker]}
        check(missing[ticker] == [dict(contract_key=k, reason='MISSING_OI', eligible=False) for k in sorted(absent)], 'missing OI mismatch')
    return dict(status='PASS_INDEPENDENT_RECONSTRUCTED_COMPONENT_AUDIT', bars=3,
                oi_rows=sum(len(rows) for rows in interest.values()),
                eligible_oi={t: sum(r['eligible'] for r in rows) for t, rows in interest.items()},
                repairs=sum(b['repair'] is not None for b in bars.values()), mismatches=0,
                missing_oi={t: len(rows) for t, rows in missing.items()},
                original_vintage_verified=False, historical_economic_admission=False, promotion_approved=False)
