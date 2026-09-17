import json
import os
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from neural.jepa.multiscale_v1r1.artifacts import digest
from neural.jepa.multiscale_v1r1.contract import ContractError
from neural.jepa.multiscale_v1r1.features import ablation, flatten
from neural.jepa.multiscale_v1r1.interactions import build_event, scale_tensor, state_path
from neural.jepa.multiscale_v1r1.levels import aggregate_walls, initial_balance, wall_snapshot
from neural.jepa.multiscale_v1r1.provenance import capture_documents, coherent_read_handles, read_document
from neural.jepa.multiscale_v1r1_audit.snapshot import verify_snapshot


def source_fixture(day='2025-01-10'):
    clock = pd.date_range(f'{day} 09:30', periods=240, freq='min', tz='America/New_York')
    close = 100 + np.sin(np.arange(240) / 13) * .25 + np.arange(240) * .001
    bars = pd.DataFrame(dict(timestamp=clock, open=close - .01, high=close + .04,
                             low=close - .04, close=close, tick_count=20))
    quotes, positions = [], []
    for strike in (99., 100., 101.):
        for right in ('CALL', 'PUT'):
            key = dict(ticker='SPXW', trade_date=day, expiration=day, right=right, strike=strike)
            positions.append(dict(**key, open_interest=100, as_of=pd.Timestamp(day, tz='America/New_York') - pd.Timedelta(hours=8),
                                  available_at=pd.Timestamp(f'{day} 06:30', tz='America/New_York'), provenance_ref='fixture'))
            for timestamp in clock:
                quotes.append(dict(**key, timestamp=timestamp, implied_vol=.2, ask=1.1, bid=1., delta=.5))
    return bars, pd.DataFrame(quotes), pd.DataFrame(positions)


def prior_sessions(frame, day):
    return {str(d.date()): frame.set_index('timestamp').set_axis(
        frame.timestamp - pd.Timedelta(days=(pd.Timestamp(day) - d).days))
        for d in pd.bdate_range(end=pd.Timestamp(day) - pd.Timedelta(days=1), periods=5)}


def test_ib_extensions_and_d_aligned_tensor_future_invariance():
    day = '2025-01-10'
    frame, quotes, positions = source_fixture(day)
    prior = prior_sessions(frame, day)
    decision = pd.Timestamp(day + ' 11:35', tz='America/New_York')
    event = build_event(frame, prior, quotes, positions, 'SPXW', day, decision, 99.8)
    ib = initial_balance(frame.set_index('timestamp'), day)
    high, low = ib['d0_ibh'].price, ib['d0_ibl'].price
    assert ib['d0_upper_1618'].price == pytest.approx(low + 1.618 * (high - low))
    assert ib['d0_lower_1272'].price == pytest.approx(high - 1.272 * (high - low))
    assert flatten(*(event[k] for k in ('x5', 'm5', 'x15', 'm15', 'static'))).shape == (92048,)
    assert ablation(*(event[k] for k in ('x5', 'm5', 'x15', 'm15', 'static'))).shape == (488,)
    frame.loc[frame.timestamp >= decision, ['open', 'high', 'low', 'close']] = -1000
    quotes.loc[quotes.timestamp > decision, ['ask', 'bid', 'implied_vol']] = np.nan
    again = build_event(frame, prior, quotes, positions, 'SPXW', day, decision, 99.8)
    for key in ('x5', 'm5', 'x15', 'm15', 'static'):
        np.testing.assert_array_equal(event[key], again[key])
    changed = {name: replace(level, price=None if name.startswith(('max_', 'min_', 'call_', 'put_', 'zero_')) else level.price)
               for name, level in event['levels'].items()}
    prefix = frame.loc[frame.timestamp < decision].set_index('timestamp')
    a, b = scale_tensor(prefix, decision, 5, 12, changed, event['snapshots'], 99.8)
    c, d = scale_tensor(prefix, decision, 15, 8, changed, event['snapshots'], 99.8)
    np.testing.assert_array_equal(ablation(a, b, c, d, event['static']),
                                  ablation(*(event[k] for k in ('x5', 'm5', 'x15', 'm15', 'static'))))


def test_wall_native_predecessor_limits_and_duplicate_oi():
    frame, quotes, oi = source_fixture()
    end = pd.Timestamp('2025-01-10 11:30', tz='America/New_York')
    snapshot = wall_snapshot(quotes, oi, frame.set_index('timestamp'), 'SPXW', '2025-01-10', end)
    assert set(snapshot.members.timestamp) == {end}
    assert (snapshot.members.spot_bar_end <= snapshot.members.timestamp).all()
    old = quotes.loc[quotes.timestamp <= end - pd.Timedelta(seconds=60)]
    with pytest.raises(ContractError, match='insufficient'):
        wall_snapshot(old, oi, frame.set_index('timestamp'), 'SPXW', '2025-01-10', end)
    with pytest.raises(ContractError, match='duplicate native'):
        wall_snapshot(pd.concat([quotes, quotes.loc[quotes.timestamp == end]]), oi,
                      frame.set_index('timestamp'), 'SPXW', '2025-01-10', end)
    with pytest.raises(ContractError, match='insufficient'):
        wall_snapshot(quotes, pd.concat([oi, oi]), frame.set_index('timestamp'), 'SPXW', '2025-01-10', end)


def test_wall_root_selection_ties_and_absent_slots():
    g = pd.DataFrame(dict(Gn=[1., -1., 1.], Xn=[0., 0., 0.], Dn=[1., 0., -1.],
                          Gc=[2., 2., 2.], Gp=[1., 3., 1.], Dc=[2., 1., 1.], Dp=[1., 1., 2.]), index=[99., 100., 101.])
    levels = aggregate_walls(g, 100., pd.Timestamp('2025-01-10 11:30', tz='America/New_York'), '2025-01-10')
    assert levels['zero_gamma'].price == 99.5
    assert levels['call_gamma'].price == 99.
    assert levels['max_dgex'].price is None
    assert levels['put_gamma'].strength < 0


def test_state_no_approach_and_full_history_retest():
    constant = np.tile([100., 100.1, 99.9, 100., 1.], (10, 1))
    path = state_path(constant, 100, 100, 'resistance', 5)
    assert not any(p['first_touch'] or p['rejection'] or p['pierce'] for p in path)
    assert path[-1]['prior_touches'] == 9
    # Approach, break, two closes above resistance, then retest from above.
    values = np.array([[99.5, 99.6, 99.4, 99.5, 1], [99.6, 99.7, 99.5, 99.6, 1],
                       [99.7, 99.8, 99.6, 99.7, 1], [99.8, 100.1, 99.8, 100.06, 1],
                       [100.06, 100.2, 100.06, 100.1, 1], [100.1, 100.2, 100.0, 100.1, 1]])
    path = state_path(values, 100, 100, 'resistance', 5)
    assert path[-1]['retest'] == 1 and path[-1]['acceptance'] == 0
    assert path[-1]['prior_touches'] >= 1


@pytest.mark.skipif(os.name != 'nt', reason='Win32 coherent snapshot mechanism')
def test_snapshot_is_independent_of_live_log_and_detects_mutation(tmp_path):
    source = tmp_path / 'live.log'
    source.write_bytes(b'original\n')
    root = tmp_path / 'snapshot'
    manifest = capture_documents([source], root)
    checksum = digest(manifest)
    name = json.loads(manifest.read_bytes())['documents'][0]['snapshot_path']
    source.write_bytes(b'original\nnew activity\n')
    assert read_document(root, name, checksum) == 'original\n'
    assert verify_snapshot(root, checksum)[name] == 'original\n'
    (root / name).write_bytes(b'altered\n')
    with pytest.raises(ContractError, match='changed'):
        read_document(root, name, checksum)
    with pytest.raises(ValueError, match='byte mismatch'):
        verify_snapshot(root, checksum)


@pytest.mark.skipif(os.name != 'nt', reason='Win32 coherent snapshot mechanism')
def test_snapshot_excludes_concurrent_writers_on_all_handles(tmp_path):
    paths = [tmp_path / 'a.log', tmp_path / 'b.log']
    for p in paths:
        p.write_bytes(b'original')
    with coherent_read_handles(paths) as handles:
        for p in paths:
            with pytest.raises(PermissionError):
                p.open('wb')
        assert [h.read() for h in handles] == [b'original', b'original']
    with paths[1].open('ab'):
        with pytest.raises(ContractError, match='cannot exclude writers'):
            capture_documents(paths, tmp_path / 'failed')
    assert not (tmp_path / 'failed/manifest.json').exists()
