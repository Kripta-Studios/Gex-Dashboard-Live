"""Synthetic parity, temporal boundaries and prefix causality; no market files."""

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import build_cache as frozen_cache
import features as frozen_features
import level_engine as frozen_engine
import session_cache
import session_features as features
import session_level_engine as engine
from session_clock import FULL, SHORT, SessionClock
from test_level_engine import action, make_cache


def short_cache():
    cache = make_cache()
    return {
        key: value[:211].copy()
        if key
        in (
            "time_ns",
            "spot",
            "spot_valid",
            "bid",
            "ask",
            "delta",
            "iv",
            "vega",
            "theta",
            "row_flags",
        )
        else value.copy()
        for key, value in cache.items()
    }


def frames():
    raw = make_cache()
    times = pd.to_datetime(raw["time_ns"])
    rows = []
    for i in range(391):
        for ci in range(len(raw["strike"])):
            rows.append(
                dict(
                    symbol="SPY",
                    trade_date="2023-01-03",
                    expiration="2023-01-03",
                    strike=raw["strike"][ci],
                    right="C" if raw["right"][ci] == 0 else "P",
                    timestamp=str(times[i]),
                    underlying_timestamp=str(times[i]),
                    underlying_price=raw["spot"][i],
                    bid=raw["bid"][i, ci],
                    ask=raw["ask"][i, ci],
                    delta=raw["delta"][i, ci],
                    implied_vol=raw["iv"][i, ci],
                    vega=raw["vega"][i, ci],
                    theta=raw["theta"][i, ci],
                )
            )
    greek = pd.DataFrame(rows)
    oi = greek.iloc[:6][
        ["symbol", "trade_date", "expiration", "strike", "right", "timestamp"]
    ].copy()
    oi["open_interest"] = np.arange(6) + 10
    return greek, oi


def equal_arrays(left, right):
    assert left.keys() == right.keys()
    for key in left:
        assert left[key].dtype == right[key].dtype, key
        np.testing.assert_array_equal(left[key], right[key], err_msg=key)


def equal_day(left, right):
    for name in ("states", "levels", "actions"):
        pd.testing.assert_frame_equal(
            getattr(left, name), getattr(right, name), check_exact=True
        )
    assert left.coverage == right.coverage
    assert left.metadata == right.metadata


def test_clock_immutable_and_only_two_explicit_schedules():
    assert (SHORT.n_slots, SHORT.last_state, SHORT.eod_i) == (211, 195, 205)
    assert (FULL.n_slots, FULL.last_state, FULL.eod_i) == (391, 375, 385)
    with pytest.raises(FrozenInstanceError):
        SHORT.close_i = 390
    for invalid in (209, 211, 390.0, True):
        with pytest.raises(ValueError):
            SessionClock(invalid)


def test_full_cache_bitexact_including_metadata():
    greek, oi = frames()
    actual, meta = session_cache.normalize_day(greek, oi, "SPY", "20230103", FULL)
    expected, oldmeta = frozen_cache.normalize_day(greek, oi, "SPY", "20230103")
    equal_arrays(actual, expected)
    assert meta == oldmeta


def test_full_engine_labels_dp_scheduler_bitexact():
    raw = make_cache()
    old = frozen_engine.build_day(raw)
    actual = engine.build_day(raw, clock=FULL)
    equal_day(actual, old)
    labels = engine.evaluate_actions(raw, actual.actions, FULL)
    expected = frozen_engine.evaluate_actions(raw, old.actions)
    pd.testing.assert_frame_equal(labels, expected, check_exact=True)
    for a, b in [
        (
            engine.solve_oracle(actual.actions, labels, FULL),
            frozen_engine.solve_oracle(old.actions, expected),
        )
    ]:
        np.testing.assert_array_equal(a.value, b.value)
        pd.testing.assert_frame_equal(a.trajectory, b.trajectory, check_exact=True)
        pd.testing.assert_frame_equal(a.advantages, b.advantages, check_exact=True)
        assert a.summary == b.summary
    scores = np.ones(len(actual.actions))
    a = engine.evaluate_policy(actual.actions, labels, scores, clock=FULL)
    b = frozen_engine.evaluate_policy(old.actions, expected, scores)
    pd.testing.assert_frame_equal(a.attempts, b.attempts, check_exact=True)
    assert a.summary == b.summary


def test_full_feature_arrays_bitexact():
    raw = make_cache()
    old = frozen_features.build_day_feature_cache(raw)
    new = features.build_day_feature_cache(raw, FULL)
    equal_arrays(features.encode_states(new), frozen_features.encode_states(old))
    actions = frozen_engine.build_day(raw).actions
    np.testing.assert_array_equal(
        features.action_features(raw, actions, clock=FULL),
        frozen_features.action_features(raw, actions),
    )


@pytest.mark.parametrize("native", [True, False])
def test_postclose_filter_before_universe_and_duplicate_validation(native):
    greek, oi = frames()
    # A contract existing only after 13:00 must not enter the normalized axis.
    future = greek.iloc[[-1]].copy()
    future["strike"] = 12345.0
    greek = pd.concat([greek, future, future], ignore_index=True)
    future_oi = oi.iloc[[0]].copy()
    future_oi["strike"] = 99999.0
    future_oi["timestamp"] = "2023-01-03 13:01:00"
    oi = pd.concat([oi, future_oi], ignore_index=True)
    if not native:
        greek = greek.drop(columns="timestamp")
    actual, meta = session_cache.normalize_day(greek, oi, "SPY", "20230103", SHORT)
    bounded = greek.loc[
        pd.to_datetime(greek.underlying_timestamp) <= pd.Timestamp("2023-01-03 13:00")
    ]
    expected, _ = session_cache.normalize_day(
        bounded, oi.iloc[:6], "SPY", "20230103", SHORT
    )
    equal_arrays(actual, expected)
    assert actual["bid"].shape == (211, 6)
    assert meta["post_close_removed"] == {"greek": 1082, "oi": 1}
    changed = greek.copy()
    tail = pd.to_datetime(changed.underlying_timestamp) > pd.Timestamp(
        "2023-01-03 13:00"
    )
    changed.loc[tail, ["underlying_price", "bid", "ask", "delta", "implied_vol"]] = 1e9
    perturbed, _ = session_cache.normalize_day(changed, oi, "SPY", "20230103", SHORT)
    equal_arrays(actual, perturbed)


def test_short_states_features_and_physical_time_units():
    raw = short_cache()
    day = engine.build_day(raw, clock=SHORT)
    assert day.states.state_i.tolist() == list(range(60, 196))
    assert day.actions.state_i.max() == 195
    packed = features.build_day_feature_cache(raw, SHORT)
    encoded = features.encode_states(packed)
    assert encoded["base"].shape == (136, 81)
    assert encoded["tokens"].shape == (136, 20, 45)
    assert encoded["maps"].shape == (136, 20, 5, 64)
    assert np.all(encoded["bar_end_i"] < encoded["state_i"][:, None])
    assert encoded["base"][-1, 0] == np.float32(195 / 390)
    assert encoded["base"][-1, 1] == np.float32(15 / 390)
    assert features.action_features(raw, day.actions, clock=SHORT).shape[1] == 33
    for invalid in (59, 196, 205):
        with pytest.raises(ValueError):
            features.encode_state(packed, invalid)
    with pytest.raises(ValueError):
        engine.build_day(make_cache(), clock=SHORT)


@pytest.mark.parametrize("minute", [60, 119, 195])
def test_short_future_values_and_future_identity_leave_prefix_bitexact(minute):
    raw = short_cache()
    mutated = {k: v.copy() for k, v in raw.items()}
    mutated["spot"][minute + 1 :] = 20000
    for key in ("bid", "ask", "delta", "iv", "vega", "theta"):
        mutated[key][minute + 1 :] = 77
        extra = np.full((211, 1), np.nan)
        extra[minute + 1 :] = 33
        mutated[key] = np.concatenate([mutated[key], extra], axis=1)
    flags = np.zeros((211, 1), np.uint8)
    flags[minute + 1 :] = 7
    mutated["row_flags"] = np.concatenate([mutated["row_flags"], flags], axis=1)
    mutated["strike"] = np.r_[mutated["strike"], 12345.0]
    mutated["right"] = np.r_[mutated["right"], np.int8(0)]
    mutated["oi_contract_idx"] = np.r_[mutated["oi_contract_idx"], np.int32(6)]
    mutated["oi_value"] = np.r_[mutated["oi_value"], np.int64(100000)]
    mutated["oi_available_ns"] = np.r_[
        mutated["oi_available_ns"], mutated["time_ns"][minute + 1]
    ]
    mutated["oi_valid"] = np.r_[mutated["oi_valid"], True]
    before = engine.build_day(raw, clock=SHORT)
    after = engine.build_day(mutated, clock=SHORT)
    for name in ("states", "levels", "actions"):
        a, b = getattr(before, name), getattr(after, name)
        pd.testing.assert_frame_equal(
            a.loc[a.state_i <= minute].reset_index(drop=True),
            b.loc[b.state_i <= minute].reset_index(drop=True),
            check_exact=True,
        )
    a = features.encode_states(
        features.build_day_feature_cache(raw, SHORT), range(60, minute + 1)
    )
    b = features.encode_states(
        features.build_day_feature_cache(mutated, SHORT), range(60, minute + 1)
    )
    equal_arrays(a, b)


def test_gamma_uses_actual_remaining_minutes_and_expires_at_close():
    raw = short_cache()
    oi = engine.available_oi_matrix(raw, SHORT)
    actual = engine.bs_gamma_density(raw, 195, oi[195], SHORT)
    # Synthetic ATM contract, independent Black-Scholes scalar expression.
    tau = 15 * 60 / (365 * 86400)
    spot, sigma = 100.0, 0.2
    d1 = 0.5 * sigma * np.sqrt(tau)
    expected = (
        np.exp(-0.5 * d1 * d1)
        / (np.sqrt(2 * np.pi) * spot * sigma * np.sqrt(tau))
        * 12
        * 100
        * spot
        * spot
        * 0.01
    )
    assert actual[2] == pytest.approx(expected, rel=1e-14)
    assert np.isnan(engine.bs_gamma_density(raw, 210, oi[210], SHORT)).all()
    full_gamma = frozen_engine.bs_gamma_density(make_cache(), 195, oi[195])
    assert actual[2] != full_gamma[2]


def test_last_trigger204_exit205_and_close205_is_eod_not_trigger():
    raw = short_cache()
    raw["spot"][204] = 103
    assert engine.exit_trigger(
        raw["spot"], raw["spot_valid"], 195, 0, 102, 98, 0.1, SHORT
    )[:3] == (204, 205, "TARGET")
    raw["spot"][204] = 100
    raw["spot"][205:] = 103
    assert engine.exit_trigger(
        raw["spot"], raw["spot_valid"], 195, 0, 102, 98, 0.1, SHORT
    )[:3] == (-1, 205, "EOD")
    actions = pd.DataFrame([action(state=195)])
    labels = engine.evaluate_actions(raw, actions, SHORT)
    assert labels.exit_i.tolist() == [205]
    result = engine.solve_oracle(actions, labels, SHORT)
    assert result.value.shape == (207,)
    assert np.all(result.value[196:] == 0)


def test_no_fill_no_same_minute_rescue_and_invalid_new_oi():
    raw = short_cache()
    raw["row_flags"][61, 2] = 0
    actions = pd.DataFrame(
        [
            action(action_id=0),
            action(contract=4, action_id=1),
            action(state=61, contract=4, action_id=2),
        ]
    )
    labels = engine.evaluate_actions(raw, actions, SHORT)
    result = engine.evaluate_policy(actions, labels, [3.0, 2.0, 1.0], clock=SHORT)
    assert result.attempts.action_id.tolist() == [0, 2]
    assert result.attempts.status.tolist() == ["NO_FILL", "FILLED"]
    raw["oi_contract_idx"] = np.r_[raw["oi_contract_idx"], np.int32(2)]
    raw["oi_value"] = np.r_[raw["oi_value"], np.int64(-1)]
    raw["oi_available_ns"] = np.r_[raw["oi_available_ns"], raw["time_ns"][100]]
    raw["oi_valid"] = np.r_[raw["oi_valid"], False]
    oi = engine.available_oi_matrix(raw, SHORT)
    assert oi[99, 2] == 12
    assert np.isnan(oi[100:, 2]).all()
