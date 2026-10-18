"""Small fixtures exercise cache identity, causality/missingness and resume hashes."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import build_cache as cache


def fixtures():
    base = {'symbol': 'SPY', 'expiration': '2023-01-03', 'trade_date': '2023-01-03',
            'strike': 380.0, 'right': 'C', 'timestamp': '2023-01-03T09:30:00',
            'underlying_timestamp': '2023-01-03T09:30:00', 'underlying_price': 380.25,
            'bid': 1.12500000001, 'ask': 1.25000000001, 'delta': .50000000001,
            'implied_vol': .20000000001, 'vega': .00100000001, 'theta': -.10000000001}
    greek = pd.DataFrame([base, {**base, 'timestamp': '2023-01-03T09:31:00',
                                'underlying_timestamp': '2023-01-03T09:31:00', 'bid': 0.0},
                          {**base, 'right': 'P', 'timestamp': '2023-01-03T09:31:00',
                           'underlying_timestamp': '2023-01-03T09:31:00'}])
    oi_base = {key: base[key] for key in ['symbol', 'expiration', 'trade_date', 'strike', 'right']}
    oi = pd.DataFrame([{**oi_base, 'timestamp': '2023-01-03T06:30:00', 'open_interest': 20},
                       {**oi_base, 'timestamp': '2023-01-03T10:00:00', 'open_interest': 21},
                       {**oi_base, 'strike': 390.0, 'right': 'P', 'timestamp': '2023-01-03T06:30:00', 'open_interest': 12}])
    return greek, oi


def test_exact_float64_sparse_union_and_causal_oi_history():
    greek, oi = fixtures()
    arrays, metadata = cache.normalize_day(greek, oi, 'SPY', '20230103')
    assert arrays['bid'].shape == (391, 3)
    assert arrays['strike'].tolist() == [380, 380, 390]
    assert arrays['right'].tolist() == [0, 1, 1]
    assert arrays['bid'][0, 0] == greek.bid.iloc[0]
    for key in cache.PRICES:
        assert arrays[key].dtype == np.float64
    assert arrays['row_flags'][1, 0] == 7  # zero bid is valid, positive ask.
    assert arrays['row_flags'][0, 1] == 0 and np.isnan(arrays['bid'][0, 1])
    assert arrays['oi_contract_idx'].tolist() == [0, 2, 0]
    assert arrays['oi_value'].tolist() == [20, 12, 21]
    assert arrays['oi_valid'].all()
    assert not arrays['spot_valid'][2] and np.isnan(arrays['spot'][2])
    assert 'underlying_age_ms' not in arrays
    assert metadata['clock_basis'] == 'NATIVE_STORED_TIMESTAMP'


def test_fallback_disagreement_stale_clock_and_duplicate_fail_closed():
    greek, oi = fixtures()
    proxy, proxy_metadata = cache.normalize_day(greek.drop(columns='timestamp'), oi.drop(columns='timestamp').iloc[[0, 2]], 'SPY', '20230103')
    assert proxy_metadata['clock_basis'] == 'ASSUMED_UNDERLYING_SNAPSHOT_CLOCK'
    assert proxy_metadata['oi_clock_basis'] == 'ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT'
    assert (proxy['oi_available_ns'] == proxy['time_ns'][0]).all()
    greek.loc[0, 'underlying_timestamp'] = '2023-01-03T09:31:00'
    greek.loc[2, 'underlying_price'] = 381.0
    arrays, metadata = cache.normalize_day(greek, oi, 'SPY', '20230103')
    assert not arrays['spot_valid'][:2].any()
    assert arrays['row_flags'][0, 0] == 3
    assert arrays['underlying_age_ms'][0, 0] == -60000
    assert metadata['counters']['inconsistent_spot_minutes'] == 1
    with pytest.raises(ValueError, match='duplicate Greek'):
        cache.normalize_day(pd.concat([greek, greek.iloc[[0]]]), oi, 'SPY', '20230103')


def test_disk_roundtrip_verified_resume_and_corruption_rejection(tmp_path):
    greek, oi = fixtures()
    source_root, out = tmp_path / 'raw', tmp_path / 'out'
    for kind, frame in [('greeks', greek), ('oi', oi)]:
        path = cache.source_path(source_root, 'SPY', '20230103', kind)
        path.parent.mkdir(parents=True)
        frame.to_parquet(path, index=False)
    task = {'ticker': 'SPY', 'date': '20230103', 'source_root': str(source_root),
            'out': str(out), 'producer_sha256': 'fixture-producer'}
    assert cache.build_day(task)['status'] == 'BUILT'
    path = out / 'SPY/20230103.npz'
    assert cache.load_day_cache(path)['bid'][0, 0] == greek.bid.iloc[0]
    assert cache.build_day(task)['status'] == 'VERIFIED_EXISTING'
    with path.open('ab') as handle:
        handle.write(b'corruption')
    with pytest.raises(ValueError, match='hash mismatch'):
        cache.load_day_cache(path)
    with pytest.raises(ValueError, match='hash mismatch'):
        cache.build_day(task)
    assert cache.build_day({**task, 'date': '20230104'})['status'] == 'MISSING_SOURCE'
