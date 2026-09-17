"""Predeclared offline counts on the six sealed pilot responses; no features."""
import csv
import hashlib
import io
import json
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path('D:/GexResearchArtifacts/multiscale_v1r1/theta_source_pilot_20260918_01')
OUT = Path('D:/GexResearchArtifacts/multiscale_v1r1/theta_oi_diagnostic_20260918_01')
KEY = ['symbol', 'expiration', 'strike', 'right']


def sealed(folder):
    manifest = json.loads((folder / 'manifest.json').read_bytes())
    payload = (folder / 'response.bin').read_bytes()
    assert hashlib.sha256(payload).hexdigest() == manifest['sha256'] and len(payload) == manifest['bytes']
    return payload, manifest['sha256']


def producer(g, o):
    greek, oi = pd.read_csv(io.BytesIO(g)), pd.read_csv(io.BytesIO(o))
    for frame in (greek, oi):
        frame['expiration'] = pd.to_datetime(frame.expiration).dt.strftime('%Y-%m-%d')
        frame['right'] = frame.right.str.upper().replace({'C': 'CALL', 'P': 'PUT'})
    assert not oi.duplicated(KEY).any()
    valid = (greek.implied_vol.between(0, 2, inclusive='neither') & (greek.bid >= 0)
             & (greek.ask > 0) & (greek.ask >= greek.bid)
             & np.isfinite(greek[['implied_vol', 'bid', 'ask', 'strike']]).all(axis=1))
    present = {tuple(row) for row in greek[KEY].to_numpy()}
    usable = {tuple(row) for row in greek.loc[valid, KEY].to_numpy()}
    times = pd.to_datetime(oi.timestamp, format='mixed').dt.tz_localize('America/New_York')
    late = times > pd.Timestamp('2022-08-01 09:30', tz='America/New_York')
    positive = oi.open_interest > 0
    is_present = np.array([tuple(r) in present for r in oi[KEY].to_numpy()])
    is_usable = np.array([tuple(r) in usable for r in oi[KEY].to_numpy()])
    return dict(oi_rows=len(oi), late_oi_rows=int(late.sum()), late_oi_positive=int((late & positive).sum()),
                late_oi_zero=int((late & (oi.open_interest == 0)).sum()),
                late_oi_present_in_greeks=int((late & is_present).sum()),
                late_oi_with_valid_greek=int((late & is_usable).sum()),
                late_positive_oi_with_valid_greek=int((late & positive & is_usable).sum()),
                early_positive_oi_with_valid_greek=int((~late & positive & is_usable).sum()),
                greek_contracts=len(present), greek_valid_contracts=len(usable),
                greek_valid_without_oi=len(usable - {tuple(r) for r in oi[KEY].to_numpy()}))


def auditor(g, o):
    greek = list(csv.DictReader(io.StringIO(g.decode('utf-8-sig'))))
    positions = list(csv.DictReader(io.StringIO(o.decode('utf-8-sig'))))
    def key(row):
        return (row['symbol'], datetime.fromisoformat(row['expiration']).date().isoformat(), Decimal(row['strike']),
                {'C': 'CALL', 'P': 'PUT'}.get(row['right'].upper(), row['right'].upper()))
    present, valid = set(), set()
    for row in greek:
        k = key(row)
        present.add(k)
        iv, bid, ask, strike = [Decimal(row[n]) for n in ('implied_vol', 'bid', 'ask', 'strike')]
        if all(v.is_finite() for v in (iv, bid, ask, strike)) and 0 < iv < 2 and 0 <= bid <= ask and ask > 0:
            valid.add(k)
    result = dict(oi_rows=len(positions), late_oi_rows=0, late_oi_positive=0, late_oi_zero=0,
                  late_oi_present_in_greeks=0, late_oi_with_valid_greek=0, late_positive_oi_with_valid_greek=0,
                  early_positive_oi_with_valid_greek=0, greek_contracts=len(present), greek_valid_contracts=len(valid))
    opening = datetime(2022, 8, 1, 9, 30, tzinfo=ZoneInfo('America/New_York'))
    seen = set()
    for row in positions:
        k = key(row)
        assert k not in seen
        seen.add(k)
        when = datetime.fromisoformat(row['timestamp'])
        when = when.replace(tzinfo=opening.tzinfo) if when.tzinfo is None else when.astimezone(opening.tzinfo)
        late, positive = when > opening, Decimal(row['open_interest']) > 0
        result['late_oi_rows'] += late
        result['late_oi_positive'] += late and positive
        result['late_oi_zero'] += late and Decimal(row['open_interest']) == 0
        result['late_oi_present_in_greeks'] += late and k in present
        result['late_oi_with_valid_greek'] += late and k in valid
        result['late_positive_oi_with_valid_greek'] += late and positive and k in valid
        result['early_positive_oi_with_valid_greek'] += not late and positive and k in valid
    result['greek_valid_without_oi'] = len(valid - seen)
    return result


def run():
    OUT.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, OUT / 'diagnostic_source.py')
    results, hashes = {}, {}
    for i, ticker in enumerate(('SPXW', 'SPY', 'QQQ')):
        g, gh = sealed(ROOT / f'{i:02d}_{ticker}_greeks')
        o, oh = sealed(ROOT / f'{i + 3:02d}_{ticker}_oi')
        result, independent = producer(g, o), auditor(g, o)
        assert result == independent, ticker
        results[ticker] = result
        hashes[ticker] = dict(greeks=gh, oi=oh)
    summary = dict(status='PASS_INDEPENDENT_OFFLINE_OI_DIAGNOSTIC', results=results, source_sha256=hashes,
                   historical_admission_granted=False, historical_economics='NOT_EVALUATED', promotion_approved=False)
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    run()
