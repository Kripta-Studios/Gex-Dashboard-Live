"""Causal tensors, complete histories, masks and resumable feature artifacts."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import features as f


def fixture():
    n, c = 391, 6
    times = np.datetime64('2023-01-03T09:30', 'ns').astype(np.int64) + np.arange(n) * 60_000_000_000
    spot = 100 + .003 * np.arange(n) + .1 * np.sin(np.arange(n) / 5)
    side = np.array([0, 1, 0, 1, 0, 1], dtype=np.int8)
    return dict(time_ns=times, strike=np.array([98., 99., 100., 101., 102., 105.]), right=side,
                spot=spot, spot_valid=np.ones(n, dtype=bool),
                bid=np.full((n, c), 1.), ask=np.full((n, c), 1.1),
                delta=np.tile(np.where(side == 0, .5, -.5), (n, 1)),
                iv=np.full((n, c), .2), vega=np.full((n, c), .05), theta=np.full((n, c), -.03),
                row_flags=np.full((n, c), 7, dtype=np.uint8),
                oi_contract_idx=np.arange(c, dtype=np.int32), oi_value=np.arange(1, c + 1, dtype=np.int64) * 10,
                oi_available_ns=np.full(c, times[0] - 3 * 3600_000_000_000, dtype=np.int64),
                oi_valid=np.ones(c, dtype=bool))


def copy(raw):
    return {name: array.copy() for name, array in raw.items()}


def assert_equal(left, right):
    assert set(left) == set(right)
    for name in left:
        assert np.array_equal(left[name], right[name]), name


@pytest.mark.parametrize('cutoff', [60, 64, 120, 241, 375])
def test_future_perturbation_bitwise_equivalence(cutoff):
    raw = fixture()
    changed = copy(raw)
    changed['spot'][cutoff + 1:] = 10000 + np.arange(390 - cutoff)
    for name in ('bid', 'ask', 'delta', 'iv', 'vega', 'theta'):
        changed[name][cutoff + 1:] = {'bid': .1, 'ask': 999., 'delta': .1, 'iv': 4., 'vega': 500., 'theta': -500.}[name]
    changed['oi_contract_idx'] = np.append(changed['oi_contract_idx'], np.int32(0))
    changed['oi_value'] = np.append(changed['oi_value'], np.int64(10**9))
    changed['oi_available_ns'] = np.append(changed['oi_available_ns'], raw['time_ns'][cutoff + 1])
    changed['oi_valid'] = np.append(changed['oi_valid'], True)
    assert_equal(f.encode_state(f.build_day_feature_cache(raw), cutoff),
                 f.encode_state(f.build_day_feature_cache(changed), cutoff))


@pytest.mark.parametrize('cutoff', [60, 120, 375])
def test_future_only_contract_universe_does_not_change_earlier_features(cutoff):
    raw = fixture()
    changed = copy(raw)
    contract = len(raw['strike'])
    changed['strike'] = np.append(changed['strike'], 999.)
    changed['right'] = np.append(changed['right'], np.int8(0))
    for name in ('bid', 'ask', 'delta', 'iv', 'vega', 'theta'):
        extra = np.full((391, 1), np.nan)
        extra[cutoff + 1:] = {'bid': 1., 'ask': 2., 'delta': .5, 'iv': .2, 'vega': .1, 'theta': -.1}[name]
        changed[name] = np.concatenate([changed[name], extra], axis=1)
    extra_flags = np.zeros((391, 1), dtype=np.uint8)
    extra_flags[cutoff + 1:] = 7
    changed['row_flags'] = np.concatenate([changed['row_flags'], extra_flags], axis=1)
    changed['oi_contract_idx'] = np.append(changed['oi_contract_idx'], np.int32(contract))
    changed['oi_value'] = np.append(changed['oi_value'], np.int64(99999))
    changed['oi_available_ns'] = np.append(changed['oi_available_ns'], raw['time_ns'][cutoff + 1])
    changed['oi_valid'] = np.append(changed['oi_valid'], True)
    assert_equal(f.encode_states(f.build_day_feature_cache(raw), [60, cutoff]),
                 f.encode_states(f.build_day_feature_cache(changed), [60, cutoff]))


def test_all_twenty_bars_anchored_and_unknown_history_masked():
    cache = f.build_day_feature_cache(fixture())
    early = f.encode_state(cache, 60)
    assert early['tokens'].shape == (20, len(f.TOKEN_NAMES))
    assert early['maps'].shape == (20, 5, 64)
    assert early['bar_end_i'].tolist() == list(range(4, 60, 5)) + [-1] * 4 + [14, 29, 44, 59]
    for name in ('tokens', 'maps', 'map_mask'):
        assert not early[name][12:16].any()
    assert not early['bar_mask'][12:16].any()
    assert not early['token_mask'][12:16].any()
    later = f.encode_state(cache, 120)
    assert later['bar_end_i'].tolist() == list(range(64, 120, 5)) + list(range(14, 120, 15))
    assert later['bar_mask'].all()
    assert len(np.unique(later['tokens'][:12, f.TOKEN_NAMES.index('close_ib')])) == 12
    assert later['tokens'].dtype == later['maps'].dtype == later['base'].dtype == np.float32
    assert f.flatten_state_features(later).shape == (f.feature_schema()['gbt_state_dim'],)


def test_incomplete_bar_never_enters_candle_or_map_history():
    raw = fixture()
    changed = copy(raw)
    changed['spot'][60:64] = 1000.
    changed['iv'][60:64] = 4.
    a, b = f.build_day_feature_cache(raw), f.build_day_feature_cache(changed)
    for name in ('tokens', 'maps', 'map_mask', 'bar_end_i'):
        assert np.array_equal(f.encode_state(a, 64)[name], f.encode_state(b, 64)[name])
    assert not np.array_equal(f.encode_state(a, 65)['tokens'], f.encode_state(b, 65)['tokens'])


def test_ib_uses_only_first_sixty_snapshots_and_requires_fifty_seven():
    raw = fixture()
    changed = copy(raw)
    changed['spot'][60:] = 10**6
    a, b = f.build_day_feature_cache(raw), f.build_day_feature_cache(changed)
    assert (a.ib_low, a.ib_high, a.ib_count) == (b.ib_low, b.ib_high, b.ib_count)
    raw['spot_valid'][:4] = False
    invalid = f.build_day_feature_cache(raw)
    assert not invalid.ib_valid
    assert not f.encode_state(invalid, 60)['state_valid']
    assert np.isfinite(f.encode_state(invalid, 60)['base']).all()


def test_maps_normalize_with_own_past_and_expose_outside_mass():
    cache = f.build_day_feature_cache(fixture())
    encoded = f.encode_state(cache, 120)
    assert np.min(encoded['maps']) >= 0 and np.max(encoded['maps']) <= 1
    maxima = encoded['maps'].max(axis=-1)
    assert np.all((maxima == 0) | (maxima == 1))
    assert np.array_equal(encoded['maps'], f.encode_state(cache, 121)['maps'])
    outside = f.BASE_NAMES.index('current_call_oi_outside_fraction')
    assert encoded['base'][outside] > 0


def test_late_oi_and_invalidating_oi_preserve_history_masks():
    raw = fixture()
    raw['oi_available_ns'][:] = raw['time_ns'][80]
    raw['oi_contract_idx'] = np.concatenate([raw['oi_contract_idx'], raw['oi_contract_idx']])
    raw['oi_value'] = np.concatenate([raw['oi_value'], raw['oi_value']])
    raw['oi_available_ns'] = np.concatenate([raw['oi_available_ns'], np.full(6, raw['time_ns'][100])])
    raw['oi_valid'] = np.concatenate([raw['oi_valid'], np.zeros(6, dtype=bool)])
    cache = f.build_day_feature_cache(raw)
    assert not f.encode_state(cache, 80)['map_mask'][:, 1:].any()
    assert f.encode_state(cache, 100)['map_mask'][11, 1:].all()
    assert not f.encode_state(cache, 105)['map_mask'][11, 1:].any()


def action():
    return dict(action_id=123, state_i=120, contract_i=2, right=0, strike=100., selected_delta=.5,
                delta_bucket=.5, target_center=101., target_source_mask=3,
                stop_center=99., stop_source_mask=20, band=.05)


def test_action_whitelist_ignores_ids_labels_and_future_fill_quotes():
    raw = fixture()
    altered = copy(raw)
    altered['ask'][121:] = 10**6
    altered['bid'][121:] = 10**5
    first = action()
    second = {**first, 'action_id': 999, 'net_base': 999999, 'entry_ask': 0., 'exit_i': 121,
              'hold_minutes': 1, 'teacher_best': True}
    assert np.array_equal(f.action_features(raw, pd.DataFrame([first])),
                          f.encode_actions(altered, None, pd.DataFrame([second])))
    assert not {'action_id', 'contract_i', 'state_i'} & set(f.ACTION_NAMES)


def test_valid_zero_and_missing_greek_have_distinct_field_masks():
    raw = fixture()
    raw['vega'][120] = 0.
    raw['theta'][120] = 0.
    raw['delta'][120] = 0.
    known = f.encode_state(f.build_day_feature_cache(raw), 120)
    known_action = f.action_features(raw, [action()])
    for name in ('vega', 'theta', 'delta'):
        raw[name][120] = np.nan
    missing = f.encode_state(f.build_day_feature_cache(raw), 120)
    missing_action = f.action_features(raw, [action()])
    for field in ('vega', 'theta', 'delta'):
        index = f.BASE_NAMES.index(f'current_call_{field}_valid_fraction')
        assert known['base'][index] == 1 and missing['base'][index] == 0
        index = f.ACTION_NAMES.index(field + '_valid')
        assert known_action[0, index] == 1 and missing_action[0, index] == 0


def write_source(path, raw):
    with path.open('wb') as stream:
        np.savez_compressed(stream, **raw)
    f.build_cache.write_json(path.with_suffix('.json'), dict(version=f.build_cache.VERSION,
                            sha256=f._sha(path), ticker='SPY', date='20230103', clock_basis='NATIVE',
                            oi_clock_basis='NATIVE', array_schema={name: dict(shape=list(a.shape), dtype=str(a.dtype))
                                                                  for name, a in raw.items()}))


def test_feature_roundtrip_resume_and_tamper_detection(tmp_path):
    source, target = tmp_path / 'source.npz', tmp_path / 'features.npz'
    write_source(source, fixture())
    assert f.write_day_features(source, target)['status'] == 'BUILT'
    assert f.write_day_features(source, target)['status'] == 'VERIFIED_EXISTING'
    arrays = f.load_day_features(target)
    assert arrays['state_i'].tolist() == list(range(60, 376))
    assert arrays['tokens'].shape == (316, 20, len(f.TOKEN_NAMES))
    assert all(np.isfinite(arrays[name]).all() for name in ('base', 'tokens', 'maps', 'map_mask'))
    with target.open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        f.load_day_features(target)


def test_action_cache_preserves_order_and_rejects_changed_causal_inputs(tmp_path):
    source, target = tmp_path / 'source.npz', tmp_path / 'actions.npz'
    write_source(source, fixture())
    actions = pd.DataFrame([action(), {**action(), 'action_id': 17, 'target_center': 102.}])
    assert f.write_action_feature_cache(source, actions, target)['status'] == 'BUILT'
    assert f.write_action_feature_cache(source, actions, target)['status'] == 'VERIFIED_EXISTING'
    with np.load(target, allow_pickle=False) as stored:
        assert stored['action_id'].tolist() == [123, 17]
        assert stored['action_features'].shape == (2, len(f.ACTION_NAMES))
    actions.loc[0, 'target_center'] = 102.
    with pytest.raises(ValueError, match='identity mismatch'):
        f.write_action_feature_cache(source, actions, target)
