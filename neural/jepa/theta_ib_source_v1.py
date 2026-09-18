"""Fixed three-request Initial Balance source pilot, without economic access."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import gc
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

import pandas as pd
import psutil

from neural.jepa.multiscale_v1r1.provenance import coherent_read_handles

SPEC = Path('research_papers/JEPA/multiscale_v1r1/23_INITIAL_BALANCE_SOURCE_PILOT.md')
BASE = 'http://91.99.90.39:25503/v3/option/history/greeks/first_order'
LIMIT = 512 * 1024**2
DEADLINE = 1200
DAY = '2022-08-01'
TICKERS = ('SPXW', 'SPY', 'QQQ')


def check(condition, reason):
    if not condition:
        raise ValueError(reason)


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def decimal_text(value):
    return None if value is None else format(value.normalize(), 'f')


def build_hour(payload, ticker):
    start = pd.Timestamp(DAY + ' 09:30', tz='America/New_York')
    stop = start + pd.Timedelta(hours=1)
    expected = pd.date_range(start, stop, freq='s', inclusive='left')
    seen, observations = set(), {}
    fields = ['symbol', 'expiration', 'right', 'strike', 'timestamp', 'underlying_timestamp', 'underlying_price']
    source_offset = 0
    for frame in pd.read_csv(io.BytesIO(payload), usecols=fields, dtype=str, keep_default_na=False, chunksize=50000):
        indices = list(range(source_offset, source_offset + len(frame)))
        source_offset += len(frame)
        timestamps = pd.to_datetime(frame.timestamp, format='mixed', errors='raise')
        timestamps = timestamps.dt.tz_localize('America/New_York') if timestamps.dt.tz is None else timestamps.dt.tz_convert('America/New_York')
        frame['source_row'] = indices
        frame['when'] = timestamps
        frame = frame.loc[(timestamps >= start) & (timestamps < stop)].copy()
        underlying = pd.to_datetime(frame.underlying_timestamp, format='mixed', errors='raise')
        underlying = underlying.dt.tz_localize('America/New_York') if underlying.dt.tz is None else underlying.dt.tz_convert('America/New_York')
        frame['source_when'] = underlying
        for row in frame.to_dict('records'):
            when = row['when']
            check(when.microsecond == 0 and when.nanosecond == 0, 'IBSRC-003: subsecond quote')
            strike, price = Decimal(row['strike']), Decimal(row['underlying_price'])
            price = price if price.is_finite() else None
            right = {'C': 'CALL', 'P': 'PUT'}.get(row['right'].upper(), row['right'].upper())
            check(row['symbol'] == ticker and row['expiration'][:10] == DAY and strike.is_finite()
                  and strike > 0 and right in ('CALL', 'PUT'), 'IBSRC-003: identity')
            identity = (right, strike, when)
            check(identity not in seen, 'IBSRC-003: duplicate native quote')
            seen.add(identity)
            check(row['source_when'] <= when, 'IBSRC-003: future underlying')
            check(price is not None and price > 0 or ticker == 'SPXW' and when == start,
                  'IBSRC-003: invalid price outside zero exception')
            if when in observations:
                previous = observations[when]
                check(previous['price'] == price and previous['source_when'] == row['source_when'], 'IBSRC-003: cross-contract disagreement')
                previous['count'] += 1
                if when.second == 59:
                    previous['close_rows'].append(int(row['source_row']))
            else:
                observations[when] = dict(price=price, source_when=row['source_when'], count=1,
                    close_rows=[int(row['source_row'])] if when.second == 59 else [])
        check(psutil.Process().memory_info().rss < 24 * 1024**3, 'BLOCKED_RESOURCE: process budget')
    check(sorted(observations) == list(expected), 'IBSRC-003: incomplete second grid')
    bars = []
    for minute in range(60):
        ticks = expected[minute*60:(minute+1)*60]
        values = [observations[t]['price'] for t in ticks]
        finite = [v for v in values if v is not None]
        check(finite, 'IBSRC-003: no finite prices')
        original = dict(open=values[0], high=max(finite), low=min(finite) if len(finite) == 60 else None, close=values[-1])
        current = dict(original)
        changed = [k for k, v in original.items() if v is None or v <= 0]
        repair = None
        if changed:
            check(ticker == 'SPXW' and minute == 0 and original['close'] is not None and original['close'] > 0, 'IBSRC-003: forbidden repair')
            current.update({k: original['close'] for k in changed})
            repair = dict(kind='SPXW_INITIAL_ZERO_BAR', fields=changed, source_rows=observations[ticks[-1]]['close_rows'],
                          quote_timestamp=ticks[-1].isoformat(), underlying_timestamp=observations[ticks[-1]]['source_when'].isoformat())
        bars.append(dict(timestamp=ticks[0].isoformat(), available_at=(ticks[0] + pd.Timedelta(minutes=1)).isoformat(),
                         original_ohlc={k: decimal_text(v) for k, v in original.items()},
                         ohlc={k: decimal_text(v) for k, v in current.items()},
                         tick_count=sum(observations[t]['count'] for t in ticks), repair=repair))
    high = max(Decimal(b['ohlc']['high']) for b in bars)
    low = min(Decimal(b['ohlc']['low']) for b in bars)
    check(high > low > 0, 'IBSRC-004: nonpositive IB range')
    levels = dict(ibh=decimal_text(high), ibl=decimal_text(low))
    for name, ratio in (('1272', '1.272'), ('1618', '1.618'), ('2000', '2')):
        levels[f'upper_{name}'] = decimal_text(low + Decimal(ratio) * (high-low))
        levels[f'lower_{name}'] = decimal_text(high - Decimal(ratio) * (high-low))
    return dict(ticker=ticker, trade_date=DAY, source_sha256=hashlib.sha256(payload).hexdigest(),
                bars=bars, ib=levels, available_at=stop.isoformat(), original_vintage_verified=False)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_definition(ticker):
    check(ticker in TICKERS, 'IBSRC-001: ticker')
    return dict(symbol=ticker, expiration='20220801', date='20220801', strike='*', right='both',
                interval='1s', start_time='09:30:00', end_time='10:30:00', version='1', format='csv')


def capture_one(root, ticker):
    root.mkdir(exist_ok=False)
    parameters = request_definition(ticker)
    started = time.monotonic()
    metadata = dict(ticker=ticker, params=parameters, started_at=datetime.now(timezone.utc).isoformat(),
                    url=BASE + '?' + urlencode(parameters), complete=False)
    digest, size = hashlib.sha256(), 0
    try:
        opener = build_opener(NoRedirect)
        try:
            response = opener.open(Request(metadata['url'], method='GET'), timeout=120)
        except HTTPError as error:
            response = error
        with response, (root / 'response.bin').open('xb') as output:
            metadata.update(http_status=response.status, first_response_at=datetime.now(timezone.utc).isoformat(),
                            materialization_started_at=datetime.now(timezone.utc).isoformat())
            while True:
                check(time.monotonic() - started <= DEADLINE, 'IBSRC-001: wall-clock request deadline')
                block = response.read(min(1024**2, LIMIT + 1 - size))
                check(time.monotonic() - started <= DEADLINE, 'IBSRC-001: response exceeded request deadline')
                if not block:
                    break
                output.write(block)
                digest.update(block)
                size += len(block)
                check(size <= LIMIT, 'IBSRC-001: body exceeds cap')
            metadata.update(received_at=datetime.now(timezone.utc).isoformat(), complete=True)
        metadata['materialized_at'] = datetime.now(timezone.utc).isoformat()
    except Exception as error:
        metadata['error'] = f'{type(error).__name__}: {error}'
    metadata.update(bytes=size, sha256=digest.hexdigest(), elapsed_seconds=time.monotonic()-started)
    write(root / 'manifest.json', metadata)
    return metadata


def run(destination):
    root = Path(destination).resolve()
    check(not root.exists(), 'IBSRC-001: existing output')
    root.parent.mkdir(parents=True, exist_ok=True)
    check(shutil.disk_usage(root.parent).free >= 20*1024**3 + 3*LIMIT, 'BLOCKED_RESOURCE: disk reserve')
    code = [Path(__file__), Path(__file__).with_name('audit_theta_ib_source_v1.py'), SPEC,
            Path('neural/jepa/multiscale_v1r1/provenance.py')]
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    remote = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/research/multiscale-v1r1-net-usd'], text=True).split()[0]
    check(head == remote, 'IBSRC-001: unpublished HEAD')
    for path in code:
        name = path.resolve().relative_to(Path.cwd()).as_posix()
        check(subprocess.check_output(['git', 'show', f'HEAD:{name}']).replace(b'\r\n', b'\n') == path.read_bytes().replace(b'\r\n', b'\n'), 'IBSRC-001: unpublished code')
    root.mkdir()
    write(root / 'run_manifest.json', dict(head=head, code={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in code},
                                         economic_evidence_state='NOT_EVALUATED', promotion_approved=False))
    for path in code:
        shutil.copyfile(path, root / path.name)
    process, peak, stop = psutil.Process(), [0], threading.Event()
    def monitor():
        while not stop.wait(.05):
            peak[0] = max(peak[0], process.memory_info().rss)
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    start = time.perf_counter()
    results = {}
    try:
        for ticker in TICKERS:
            print(f'Capturing fixed IB source {ticker}', flush=True)
            meta = capture_one(root / ticker, ticker)
            if not meta['complete'] or meta.get('http_status') != 200:
                results[ticker] = dict(status='FAILED_CAPTURE', metadata=meta)
                continue
            try:
                with coherent_read_handles([root / ticker / 'response.bin']) as streams:
                    payload = streams[0].read()
                check(hashlib.sha256(payload).hexdigest() == meta['sha256'], 'IBSRC-002: captured source changed')
                beginning = time.perf_counter()
                result = build_hour(payload, ticker)
                build_seconds = time.perf_counter() - beginning
                from neural.jepa.audit_theta_ib_source_v1 import reconstruct
                beginning = time.perf_counter()
                audited = reconstruct(payload, ticker)
                check(result == audited, 'IBSRC-004: independent reconstruction mismatch')
                audit_seconds = time.perf_counter()-beginning
                write(root / ticker / 'initial_balance.json', result)
                results[ticker] = dict(status='PASS_RECONSTRUCTED_IB', bars=60, build_seconds=build_seconds,
                    audit_seconds=audit_seconds, source_bytes=meta['bytes'], capture_seconds=meta['elapsed_seconds'])
                del payload
                gc.collect()
            except Exception as error:
                results[ticker] = dict(status='FAILED_RECONSTRUCTION', reason=f'{type(error).__name__}: {error}')
            print(json.dumps({ticker: results[ticker]}), flush=True)
        result = dict(status='PASS_RECONSTRUCTED_IB_SOURCE_PILOT' if all(r['status'] == 'PASS_RECONSTRUCTED_IB' for r in results.values()) else 'BLOCKED_IB_SOURCE_PILOT',
                      tickers=results, elapsed_seconds=time.perf_counter()-start, peak_rss_bytes=peak[0],
                      original_vintage_verified=False, historical_economic_admission=False,
                      economic_evidence_state='NOT_EVALUATED', promotion_approved=False)
        write(root / 'summary.json', result)
        return result
    finally:
        stop.set()
        thread.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.root), indent=2))
