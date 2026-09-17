"""Independent CSV source-clock audit. No capture/evaluator imports or networking."""
import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def summarize_independent(payload, kind, ticker):
    rows = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
    required = {'symbol', 'expiration', 'strike', 'right', 'timestamp'}
    required |= {'underlying_timestamp', 'underlying_price', 'bid', 'ask', 'implied_vol', 'delta'} if kind == 'greeks' else {'open_interest'}
    if not rows or not required <= set(rows[0]):
        raise ValueError('missing schema/rows')
    eastern = ZoneInfo('America/New_York')

    def clock(text):
        value = datetime.fromisoformat(text)
        return value.replace(tzinfo=eastern) if value.tzinfo is None else value.astimezone(eastern)

    opening = clock('2022-08-01T09:30:00')
    stop = clock('2022-08-01T09:31:00')
    times, contracts, keys, invalid, extra, valid_times, ages = [], [], [], 0, Counter(), [], []
    for row in rows:
        when = clock(row['timestamp'])
        times.append(when)
        right = {'C': 'CALL', 'P': 'PUT'}.get(row['right'].upper(), row['right'].upper())
        expiry, strike = datetime.fromisoformat(row['expiration']).date().isoformat(), float(row['strike'])
        key = (row['symbol'], expiry, right, strike)
        contracts.append(key)
        keys.append((*key, when) if kind == 'greeks' else key)
        invalid += int(row['symbol'] != ticker or expiry != '2022-08-01' or right not in ('CALL', 'PUT') or not math.isfinite(strike) or strike <= 0)
        if kind == 'greeks':
            underlying = clock(row['underlying_timestamp'])
            try:
                price = float(row['underlying_price'])
            except (ValueError, TypeError):
                price = float('nan')
            valid = math.isfinite(price) and price > 0
            extra['outside_request_rows'] += int(not opening <= when <= stop)
            extra['future_underlying_rows'] += int(underlying > when)
            extra['zero_or_invalid_underlying_rows'] += int(not valid)
            if valid:
                valid_times.append(when)
            ages.append((when - underlying).total_seconds() * 1000)
        else:
            try:
                interest = float(row['open_interest'])
            except (ValueError, TypeError):
                interest = float('nan')
            extra['oi_not_premarket_rows'] += int(when.date() != opening.date() or when > opening)
            extra['invalid_oi_rows'] += int(not math.isfinite(interest) or interest < 0 or not interest.is_integer())
    duplicates = sum(count for count in Counter(keys).values() if count > 1)
    result = dict(rows=len(rows), contracts=len(set(contracts)), duplicate_rows=duplicates, invalid_identity_rows=invalid,
                  first_timestamp=min(times).isoformat(), last_timestamp=max(times).isoformat(), **extra)
    if kind == 'greeks':
        result.update(first_positive_quote_timestamp=min(valid_times).isoformat() if valid_times else None,
                      maximum_underlying_age_ms=max(ages))
        bad = invalid + duplicates + extra['outside_request_rows'] + extra['future_underlying_rows']
    else:
        result.update(documented_as_of='PREVIOUS_TRADING_SESSION_CLOSE', original_reception_observed=False)
        bad = invalid + duplicates + extra['oi_not_premarket_rows'] + extra['invalid_oi_rows']
    result['status'] = 'FAILED_REPORTED_CLOCK_CHECKS' if bad else 'PASS_REPORTED_CLOCK_CHECKS'
    return result


def audit(directory):
    root = Path(directory)
    checked = 0
    for i, (kind, ticker) in enumerate((k, t) for k in ('greeks', 'oi') for t in ('SPXW', 'SPY', 'QQQ')):
        folder = root / f'{i:02d}_{ticker}_{kind}'
        manifest = json.loads((folder / 'manifest.json').read_bytes())
        if manifest['ticker'] != ticker or manifest['kind'] != kind:
            raise ValueError('source identity')
        params = manifest['params']
        expected = dict(symbol=ticker, expiration='20220801', date='20220801', strike='*', right='both', format='csv')
        if kind == 'greeks':
            expected.update(interval='1s', start_time='09:30:00', end_time='09:31:00', version='1')
        if params != expected:
            raise ValueError('source request scope')
        if (folder / 'response.bin').exists():
            payload = (folder / 'response.bin').read_bytes()
            if hashlib.sha256(payload).hexdigest() != manifest['sha256'] or len(payload) != manifest['bytes']:
                raise ValueError('source payload mutation')
            if manifest['http_status'] == 200 and manifest['complete']:
                try:
                    result = summarize_independent(payload, kind, ticker)
                except (ValueError, KeyError, TypeError):
                    if manifest['analysis']['status'] != 'FAILED_SCHEMA':
                        raise ValueError('independent schema mismatch') from None
                else:
                    if result != manifest['analysis']:
                        raise ValueError('independent clock/identity mismatch')
            elif manifest['analysis']['status'] != 'FAILED_HTTP_OR_INCOMPLETE':
                raise ValueError('HTTP failure mislabeled')
        elif manifest['analysis']['status'] != 'FAILED_TRANSPORT':
            raise ValueError('missing sealed source')
        checked += 1
    return dict(status='PASS_INDEPENDENT_SOURCE_PILOT_AUDIT', sources_checked=checked,
                scope='reproduce source diagnostics; not historical economic admission', promotion_approved=False)
