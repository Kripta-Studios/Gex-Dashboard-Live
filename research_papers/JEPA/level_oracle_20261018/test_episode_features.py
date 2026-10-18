"""Synthetic prefix-only tests; no local market files or outcomes are opened."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import episode_features as ef


def fixture(spots, *, centers=None, sources=None, good=None, minutes=None):
    n = len(spots)
    centers = [100.] * n if centers is None else centers
    sources = [1] * n if sources is None else sources
    good = [True] * n if good is None else good
    minutes = list(range(60, 60 + n)) if minutes is None else minutes
    states, levels = [], []
    for i, (spot, center, source, observed, minute) in enumerate(zip(spots, centers, sources, good, minutes)):
        eligible = observed and abs(spot - center) <= 1
        states.append(dict(state_i=minute, state_valid=observed, spot=spot, band=1.,
                           eligible=eligible, entry_level_id=i + 20 if eligible else -1,
                           ib_low=95., ib_range=10.))
        if observed:
            levels.append(dict(state_i=minute, level_id=i + 20, center=center,
                               source_mask=source, n_components=1,
                               components_json=f'[{source}]'))
    return pd.DataFrame(states), pd.DataFrame(levels, columns=[
        'state_i', 'level_id', 'center', 'source_mask', 'n_components', 'components_json'])


def result(spots, **kwargs):
    return ef.build_episode_features(*fixture(spots, **kwargs))


def channel(output, name):
    i = output.names.index(name)
    return output.values[:, i], output.valid[:, i]


def test_equal_ohlc_different_contact_order():
    a = [100., 101.5, 100., 101.5, 100.]
    b = [100., 100., 101.5, 101.5, 100.]
    assert (a[0], max(a), min(a), a[-1]) == (b[0], max(b), min(b), b[-1])
    left, right = result(a), result(b)
    assert channel(left, 'contacts')[0][-1] == 3
    assert channel(right, 'contacts')[0][-1] == 2


@pytest.mark.parametrize('cutoff', [0, 2, 5, 8])
def test_prefix_truncation_and_future_perturbation(cutoff):
    states, levels = fixture([100., 101.5, 100., 99., 98.5, 100., 100.2, 100.4, 100., 101.])
    whole = ef.build_episode_features(states, levels)
    changed_states, changed_levels = states.copy(), levels.copy()
    future = changed_states.state_i > states.state_i.iloc[cutoff]
    changed_states.loc[future, 'spot'] += 200
    changed_levels.loc[changed_levels.state_i > states.state_i.iloc[cutoff], 'center'] += 200
    changed = ef.build_episode_features(changed_states, changed_levels)
    prefix = ef.build_episode_features(states.iloc[:cutoff + 1], levels.loc[levels.state_i <= states.state_i.iloc[cutoff]])
    for candidate in (changed, prefix):
        np.testing.assert_array_equal(whole.values[:cutoff + 1], candidate.values[:cutoff + 1])
        np.testing.assert_array_equal(whole.valid[:cutoff + 1], candidate.valid[:cutoff + 1])


def test_anchor_persists_when_current_zone_migrates():
    output = result([100., 101., 102.], centers=[100., 101., 102.], sources=[1, 2, 16])
    np.testing.assert_array_equal(output.trace.anchor_center, [100., 100., 100.])
    np.testing.assert_array_equal(channel(output, 'current_center_minus_anchor')[0], [0., 1., 2.])
    np.testing.assert_array_equal(channel(output, 'anchor_fib')[0], [1., 1., 1.])
    np.testing.assert_array_equal(channel(output, 'current_put_gamma')[0], [0., 0., 1.])
    assert output.trace.anchor_components_json.tolist() == ['[1]'] * 3


def test_strict_close_and_no_same_minute_reopen():
    output = result([100., 102., 102., 102.1, 103., 103.], centers=[100., 100., 100., 100., 103., 103.])
    np.testing.assert_array_equal(channel(output, 'episode_open')[0], [1., 1., 1., 1., 0., 1.])
    assert output.trace.closed.tolist() == [False, False, False, False, True, False]
    assert output.trace.episode_id.tolist() == [1, 1, 1, 1, -1, 2]
    assert output.trace.anchor_center.iloc[-1] == 103.
    assert not channel(output, 'age_minutes')[1][4]
    assert channel(output, 'current_zone_valid')[0][4] == 1


@pytest.mark.parametrize('omit', [False, True])
def test_gap_breaks_closure_reentry_cross_and_lags(omit):
    states, levels = fixture([100., 102.5, 999., 99.5, 98.5, 100., 101.], good=[True, True, False, True, True, True, True])
    if omit:
        states = states.drop(index=2)
    output = ef.build_episode_features(states, levels)
    after_gap = int(np.flatnonzero(output.state_i == 63)[0])
    assert channel(output, 'episode_open')[0][after_gap] == 1
    assert channel(output, 'contacts')[0][after_gap] == 1
    assert channel(output, 'exterior_crossings')[0][after_gap] == 0
    assert not channel(output, 'spot_change_1m')[1][after_gap]
    assert not channel(output, 'spot_change_5m')[1][-1]
    assert channel(output, 'contacts')[0][-1] == 2
    assert channel(output, 'observed_fraction')[0][-1] == 6 / 7


def test_gap_breaks_two_observation_closure():
    output = result([100., 102.5, np.nan, 103., 103.], good=[True, True, False, True, True])
    np.testing.assert_array_equal(channel(output, 'episode_open')[0], [1., 1., 1., 1., 0.])
    assert channel(output, 'age_minutes')[1][2]
    assert not channel(output, 'distance_anchor')[1][2]


def test_crosses_exterior_through_inside_and_recovers():
    output = result([100., 101.5, 100., 98.5, 100.])
    assert channel(output, 'exterior_crossings')[0][-1] == 1
    assert channel(output, 'max_upper_penetration')[0][-1] == .5
    assert channel(output, 'max_lower_penetration')[0][-1] == .5
    assert channel(output, 'upper_recovery')[0][-1] == 1.5
    assert channel(output, 'lower_recovery')[0][-1] == 1.5


def test_exact_lags_arrival_and_unknown_masks():
    output = result([102., 100., 100.1, 100.2, 100.3, 100.4, 100.5])
    assert not channel(output, 'anchor_center_ib')[1][0]
    assert channel(output, 'arrival_side')[0][-1] == 1
    assert channel(output, 'spot_change_5m')[1][-1]
    assert channel(output, 'spot_change_5m')[0][-1] == .5
    assert not channel(output, 'spot_change_5m')[1][-2]
    assert np.all(output.values[~output.valid] == 0)


def test_identity_renumbering_does_not_change_numeric_inputs():
    states, levels = fixture([100., 101., 100.])
    first = ef.build_episode_features(states, levels)
    states.entry_level_id += 1000
    levels.level_id += 1000
    levels.components_json = '["different diagnostic identity"]'
    second = ef.build_episode_features(states, levels)
    np.testing.assert_array_equal(first.values, second.values)
    np.testing.assert_array_equal(first.valid, second.valid)
    assert not any('id' in name for name in first.names if name.endswith('_id'))


def test_motor_tie_break_is_checked():
    states, levels = fixture([100.], centers=[99.5])
    extra = levels.iloc[0].copy()
    extra['center'], extra['level_id'] = 100.5, 999
    levels = pd.concat([levels, pd.DataFrame([extra])], ignore_index=True)
    ef.build_episode_features(states, levels)
    states.loc[0, 'entry_level_id'] = 999
    with pytest.raises(ValueError, match='tie break'):
        ef.build_episode_features(states, levels)


def test_no_current_zone_does_not_carry_current_types():
    output = result([100., 101.5])
    assert channel(output, 'anchor_fib')[1][-1]
    assert not channel(output, 'current_fib')[1][-1]
    assert channel(output, 'current_zone_valid')[0][-1] == 0


def test_unsorted_minute_rejected():
    with pytest.raises(ValueError, match='strictly increasing'):
        result([100., 100.], minutes=[60, 60])


@pytest.mark.parametrize('observed,spot', [(False, 100.), (True, 102.)])
def test_entry_identity_requires_sentinel_without_valid_zone(observed, spot):
    states, levels = fixture([spot], good=[observed])
    ef.build_episode_features(states, levels)
    states.loc[0, 'entry_level_id'] = 7
    with pytest.raises(ValueError, match='entry_level_id=-1'):
        ef.build_episode_features(states, levels)


def test_recovery_is_known_zero_until_that_side_is_penetrated():
    output = result([100., 100.5, 99.5, 101.5, np.nan], good=[True, True, True, True, False])
    for name in ('upper_recovery', 'lower_recovery'):
        values, valid = channel(output, name)
        np.testing.assert_array_equal(values[:3], [0., 0., 0.])
        assert valid[:3].all()
        assert not valid[-1]
    assert channel(output, 'lower_recovery')[0][3] == 0
    assert channel(output, 'lower_recovery')[1][3]
