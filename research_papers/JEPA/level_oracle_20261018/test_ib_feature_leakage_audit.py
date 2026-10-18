"""Independent synthetic IB boundary/prefix audit; no market or outcome files."""
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import features as f
import level_engine as e

EXPECTED_RATIOS = np.array([-1., -.618, -.272, 0., .236, .382, .5, .618,
                            .786, 1., 1.272, 1.618, 2.])


def synthetic_cache():
    """Known first-hour extrema, deliberately unrelated to later day extrema."""
    times = np.datetime64('2023-01-03T09:30', 'ns').astype(np.int64) + np.arange(391) * 60_000_000_000
    spot = np.full(391, 100.)
    spot[:60] = 100. + np.sin(np.arange(60) / 7.)
    spot[17], spot[59] = 98., 102.
    side = np.tile(np.array([0, 1], dtype=np.int8), 3)
    return dict(time_ns=times, strike=np.repeat([98., 100., 102.], 2), right=side,
                spot=spot, spot_valid=np.ones(391, dtype=bool),
                bid=np.ones((391, 6)), ask=np.full((391, 6), 1.1),
                delta=np.tile(np.where(side == 0, .5, -.5), (391, 1)),
                iv=np.full((391, 6), .25), vega=np.full((391, 6), .05),
                theta=np.full((391, 6), -.03), row_flags=np.full((391, 6), 7, dtype=np.uint8),
                oi_contract_idx=np.arange(6, dtype=np.int32), oi_value=np.arange(1, 7, dtype=np.int64),
                oi_available_ns=np.full(6, times[0] - 60_000_000_000, dtype=np.int64),
                oi_valid=np.ones(6, dtype=bool))


def clone(raw):
    return {key: value.copy() for key, value in raw.items()}


def fib_components(raw, minute):
    low, high, _ = e.ib_bounds(raw)
    oi = e.available_oi_matrix(raw)[minute]
    band = max(.05 * (high - low), .0001 * raw['spot'][minute])
    levels = e.causal_levels(raw, oi, minute, low, high, band)
    fibs = [part for level in levels for part in json.loads(level['components_json'])
            if part['source_mask'] == e.FIB]
    return np.asarray(sorted((part['ratio'], part['center']) for part in fibs))


def assert_exact_arrays(left, right):
    assert set(left) == set(right)
    for name in left:
        assert left[name].dtype == right[name].dtype, name
        assert left[name].shape == right[name].shape, name
        assert left[name].tobytes() == right[name].tobytes(), name


def test_first_hour_bounds_ratios_and_boundary_guard():
    raw = synthetic_cache()
    np.testing.assert_array_equal(e.RATIOS, EXPECTED_RATIOS)
    assert e.ib_bounds(raw) == (98., 102., 60)
    cache = f.build_day_feature_cache(raw)
    assert (cache.ib_low, cache.ib_high, cache.ib_count) == (98., 102., 60)
    with pytest.raises(ValueError, match='60..375'):
        f.encode_state(cache, 59)
    for minute in (60, 61):
        encoded = f.encode_state(cache, minute)
        assert encoded['state_valid']
        assert encoded['bar_end_i'].max() == 59
        assert np.all(encoded['bar_end_i'][encoded['bar_mask']] < minute)
    assert np.datetime64(int(raw['time_ns'][59]), 'ns') == np.datetime64('2023-01-03T10:29')
    assert np.datetime64(int(raw['time_ns'][60]), 'ns') == np.datetime64('2023-01-03T10:30')
    day = e.build_day(raw)
    assert day.states.state_i.min() == 60 and day.actions.state_i.min() == 60
    assert np.array_equal(day.actions.entry_i.to_numpy(), day.actions.state_i.to_numpy() + 1)
    early_actions = day.actions.loc[day.actions.state_i == 60]
    assert len(early_actions)
    with pytest.raises(ValueError, match='decision range'):
        f.action_features(raw, early_actions.assign(state_i=59))


def test_post_ib_daily_extrema_never_redefine_ib_or_fibonacci_components():
    raw = synthetic_cache()
    changed = clone(raw)
    changed['spot'][60:] = np.where(np.arange(331) % 2, .001, 1_000_000.)
    before, after = f.build_day_feature_cache(raw), f.build_day_feature_cache(changed)
    assert e.ib_bounds(raw) == e.ib_bounds(changed) == (98., 102., 60)
    assert (before.ib_low, before.ib_high, before.ib_count) == (after.ib_low, after.ib_high, after.ib_count)
    expected = np.column_stack((EXPECTED_RATIOS, 98. + EXPECTED_RATIOS * 4.))
    for minute in (60, 61, 120, 375):
        np.testing.assert_array_equal(fib_components(raw, minute), expected)
        np.testing.assert_array_equal(fib_components(changed, minute), expected)
    # These candles are fully observed before the extreme decision snapshot.
    np.testing.assert_array_equal(before.bars[5][11]['ohlc'], after.bars[5][11]['ohlc'])
    np.testing.assert_array_equal(before.bars[5][11]['maps'], after.bars[5][11]['maps'])


@pytest.mark.parametrize('cutoff', [60, 61, 120, 375])
def test_future_extremes_leave_entire_decision_prefix_bitwise_identical(cutoff):
    raw = synthetic_cache()
    changed = clone(raw)
    changed['spot'][cutoff + 1:] = np.where(np.arange(390 - cutoff) % 2, .001, 1_000_000.)
    for name, value in (('bid', .01), ('ask', 999.), ('delta', .01), ('iv', 4.), ('vega', 500.), ('theta', -500.)):
        changed[name][cutoff + 1:] = value
    for key, value in (('oi_contract_idx', 0), ('oi_value', 10**9),
                       ('oi_available_ns', raw['time_ns'][cutoff + 1]), ('oi_valid', True)):
        changed[key] = np.append(changed[key], value).astype(raw[key].dtype)
    assert e.ib_bounds(raw) == e.ib_bounds(changed)
    left, right = f.build_day_feature_cache(raw), f.build_day_feature_cache(changed)
    assert_exact_arrays(f.encode_states(left, range(60, cutoff + 1)),
                        f.encode_states(right, range(60, cutoff + 1)))
    day_a, day_b = e.build_day(raw), e.build_day(changed)
    for name in ('states', 'levels', 'actions'):
        a, b = getattr(day_a, name), getattr(day_b, name)
        pd.testing.assert_frame_equal(a.loc[a.state_i <= cutoff].reset_index(drop=True),
                                      b.loc[b.state_i <= cutoff].reset_index(drop=True), check_exact=True)
    actions = day_a.actions.loc[day_a.actions.state_i <= cutoff]
    assert f.action_features(raw, actions).tobytes() == f.action_features(changed, actions).tobytes()


def test_last_ib_observation_is_included_positive_control():
    raw = synthetic_cache()
    changed = clone(raw)
    changed['spot'][59] = 104.
    assert e.ib_bounds(changed) == (98., 104., 60)
    np.testing.assert_array_equal(fib_components(changed, 60)[:, 1], 98. + EXPECTED_RATIOS * 6.)
    first, second = f.build_day_feature_cache(raw), f.build_day_feature_cache(changed)
    assert f.encode_state(first, 60)['tokens'].tobytes() != f.encode_state(second, 60)['tokens'].tobytes()


def test_retroactive_chart_coordinates_are_only_emitted_after_ib_closes():
    raw = synthetic_cache()
    cache = f.build_day_feature_cache(raw)
    encoded = f.encode_state(cache, 60)
    # Reconstruct an early 09:30..09:34 bar using the IB known at 10:30.
    values = raw['spot'][:5]
    ohlc = np.array([values[0], values.max(), values.min(), values[-1]])
    expected_geometry = ((ohlc - raw['spot'][60]) / 4.).astype(np.float32)
    np.testing.assert_array_equal(encoded['tokens'][0, :4], expected_geometry)
    assert encoded['bar_end_i'][0] == 4
    expected_map = np.exp(-.5 * ((f.GRID[None, :] - EXPECTED_RATIOS[:, None]) / .08) ** 2).sum(axis=0)
    expected_map /= expected_map.max()
    np.testing.assert_allclose(encoded['maps'][0, 0], expected_map.astype(np.float32), rtol=1e-7, atol=1e-7)
    with pytest.raises(ValueError):
        f.encode_state(cache, 4)
