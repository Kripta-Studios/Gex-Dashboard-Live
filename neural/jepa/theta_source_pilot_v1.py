"""Six immutable, predeclared source-only requests; no payoff or model imports."""
import argparse
import hashlib
import io
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

import numpy as np
import pandas as pd

BASE = 'http://91.99.90.39:25503/v3'
DAY = '2022-08-01'
LIMIT = 128 * 1024**2


def requests():
    result = []
    for kind in ('greeks', 'oi'):
        for ticker in ('SPXW', 'SPY', 'QQQ'):
            params = dict(symbol=ticker, expiration='20220801', date='20220801', strike='*', right='both', format='csv')
            endpoint = '/option/history/open_interest'
            if kind == 'greeks':
                endpoint = '/option/history/greeks/first_order'
                params.update(interval='1s', start_time='09:30:00', end_time='09:31:00', version='1')
            result.append(dict(kind=kind, ticker=ticker, endpoint=endpoint, params=params))
    return result


def summarize(payload, kind, ticker):
    frame = pd.read_csv(io.BytesIO(payload), dtype=str)
    required = {'symbol', 'expiration', 'strike', 'right', 'timestamp'}
    required |= {'underlying_timestamp', 'underlying_price', 'bid', 'ask', 'implied_vol', 'delta'} if kind == 'greeks' else {'open_interest'}
    if frame.empty or not required <= set(frame):
        raise ValueError('SOURCE_PILOT: missing schema/rows')

    def clock(column):
        values = pd.to_datetime(frame[column], format='mixed', errors='raise')
        if values.isna().any():
            raise ValueError('SOURCE_PILOT: missing timestamp')
        return values.dt.tz_localize('America/New_York') if values.dt.tz is None else values.dt.tz_convert('America/New_York')

    when = clock('timestamp')
    expiry = pd.to_datetime(frame['expiration'], errors='raise').dt.date.astype(str)
    strike = pd.to_numeric(frame['strike'], errors='raise')
    right = frame['right'].str.upper().replace({'C': 'CALL', 'P': 'PUT'})
    identity_bad = ((frame.symbol != ticker) | (expiry != DAY) | ~right.isin(('CALL', 'PUT'))
                    | ~np.isfinite(strike) | (strike <= 0))
    keys = pd.DataFrame(dict(symbol=frame.symbol, expiration=expiry, right=right, strike=strike))
    contracts = len(keys.drop_duplicates())
    if kind == 'greeks':
        keys['timestamp'] = when
    duplicates = int(keys.duplicated(keep=False).sum())
    opening = pd.Timestamp(DAY + ' 09:30', tz='America/New_York')
    result = dict(rows=len(frame), contracts=contracts, duplicate_rows=duplicates,
                  invalid_identity_rows=int(identity_bad.sum()), first_timestamp=when.min().isoformat(),
                  last_timestamp=when.max().isoformat())
    if kind == 'greeks':
        underlying = clock('underlying_timestamp')
        price = pd.to_numeric(frame['underlying_price'], errors='coerce')
        valid_price = np.isfinite(price) & (price > 0)
        invalid_time = (when < opening) | (when > opening + pd.Timedelta(minutes=1))
        future = underlying > when
        result.update(outside_request_rows=int(invalid_time.sum()), future_underlying_rows=int(future.sum()),
                      zero_or_invalid_underlying_rows=int((~valid_price).sum()),
                      first_positive_quote_timestamp=when[valid_price].min().isoformat() if valid_price.any() else None,
                      maximum_underlying_age_ms=float((when - underlying).dt.total_seconds().max() * 1000))
        valid = not (identity_bad.any() or duplicates or invalid_time.any() or future.any())
    else:
        interest = pd.to_numeric(frame['open_interest'], errors='coerce')
        bad = ~np.isfinite(interest) | (interest < 0) | (interest % 1 != 0)
        late = (when > opening) | (when < opening.normalize())
        result.update(oi_not_premarket_rows=int(late.sum()), invalid_oi_rows=int(bad.sum()),
                      documented_as_of='PREVIOUS_TRADING_SESSION_CLOSE', original_reception_observed=False)
        valid = not (identity_bad.any() or duplicates or late.any() or bad.any())
    result['status'] = 'PASS_REPORTED_CLOCK_CHECKS' if valid else 'FAILED_REPORTED_CLOCK_CHECKS'
    return result


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def capture(destination, specification):
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, root / 'producer_source.py')
    audit_path = Path(__file__).with_name('audit_theta_source_pilot_v1.py')
    shutil.copyfile(audit_path, root / 'auditor_source.py')
    spec_hash = hashlib.sha256(Path(specification).read_bytes()).hexdigest()
    opener = build_opener(NoRedirect)
    reports = []
    for i, request in enumerate(requests()):
        folder = root / f'{i:02d}_{request["ticker"]}_{request["kind"]}'
        folder.mkdir()
        metadata = dict(request, specification_sha256=spec_hash, started_at=datetime.now(timezone.utc).isoformat(),
                        url=BASE + request['endpoint'] + '?' + urlencode(request['params']))
        try:
            try:
                response = opener.open(Request(metadata['url'], method='GET'), timeout=60)
            except HTTPError as error:
                response = error
            with response:
                payload = response.read(LIMIT + 1)
                metadata.update(http_status=response.status,
                                headers={key: response.headers.get(key) for key in ('Content-Type', 'Date', 'Content-Length')})
            with (folder / 'response.bin').open('xb') as stream:
                stream.write(payload)
            metadata.update(received_at=datetime.now(timezone.utc).isoformat(), bytes=len(payload),
                            sha256=hashlib.sha256(payload).hexdigest(), complete=len(payload) <= LIMIT)
            if metadata['http_status'] == 200 and metadata['complete']:
                try:
                    metadata['analysis'] = summarize(payload, request['kind'], request['ticker'])
                except (ValueError, KeyError, TypeError) as error:
                    metadata['analysis'] = dict(status='FAILED_SCHEMA', error_type=type(error).__name__)
            else:
                metadata['analysis'] = dict(status='FAILED_HTTP_OR_INCOMPLETE')
        except (URLError, OSError, TimeoutError) as error:
            metadata['analysis'] = dict(status='FAILED_TRANSPORT', error_type=type(error).__name__)
        (folder / 'manifest.json').write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding='utf-8')
        reports.append(dict(directory=folder.name, **metadata['analysis']))
        print(json.dumps(dict(ticker=request['ticker'], kind=request['kind'], **metadata['analysis'])), flush=True)
    from .audit_theta_source_pilot_v1 import audit
    result = audit(root)
    summary = dict(status='SOURCE_PILOT_REVIEWED', requests=reports, audit=result, source_values_opened=True,
                   read_scope='20220801 opening minute Greeks plus daily prior-close OI',
                   historical_economics='NOT_EVALUATED', historical_admission_granted=False, promotion_approved=False,
                   specification_sha256=spec_hash,
                   code_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (root / 'producer_source.py', root / 'auditor_source.py')})
    (root / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--specification', required=True)
    args = parser.parse_args()
    print(json.dumps(capture(args.root, args.specification), indent=2), flush=True)
