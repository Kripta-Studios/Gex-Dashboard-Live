"""Synthetic causal/action/execution/DP fixtures, with no real source access."""

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location(
    "level_engine_fixture", Path(__file__).with_name("level_engine.py")
)
engine = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = engine
SPEC.loader.exec_module(engine)


def make_cache():
    contracts = 6
    times = pd.date_range("2023-01-03 09:30", periods=391, freq="min").asi8
    spot = np.full(391, 100.0)
    spot[:60] = np.linspace(99.0, 101.0, 60)
    return {
        "time_ns": times,
        "strike": np.array([98.0, 98.0, 100.0, 100.0, 102.0, 102.0]),
        "right": np.array([0, 1, 0, 1, 0, 1], np.int8),
        "spot": spot,
        "spot_valid": np.ones(391, bool),
        "bid": np.ones((391, contracts)),
        "ask": np.full((391, contracts), 1.1),
        "delta": np.tile([0.65, -0.35, 0.5, -0.5, 0.35, -0.65], (391, 1)),
        "iv": np.full((391, contracts), 0.2),
        "vega": np.ones((391, contracts)),
        "theta": np.full((391, contracts), -0.1),
        "row_flags": np.full((391, contracts), 7, np.uint8),
        "oi_contract_idx": np.arange(contracts, dtype=np.int32),
        "oi_value": np.arange(contracts, dtype=np.int64) + 10,
        "oi_available_ns": np.full(contracts, times[0], np.int64),
        "oi_valid": np.ones(contracts, bool),
    }


def action(
    state=60, contract=2, side=0, target=102.0, stop=98.0, band=0.1, action_id=0
):
    return {
        "action_id": action_id,
        "state_i": state,
        "entry_i": state + 1,
        "contract_i": contract,
        "right": side,
        "strike": 100.0,
        "selected_delta": 0.5 if side == 0 else -0.5,
        "delta_bucket": 0.5,
        "target_level_id": 2,
        "target_center": target,
        "target_source_mask": 1,
        "stop_level_id": 0,
        "stop_center": stop,
        "stop_source_mask": 1,
        "band": band,
        "entry_level_id": 1,
    }


def test_ib_requires_complete_57_samples_and_does_not_fill_zero():
    cache = make_cache()
    cache["spot"][:3] = 0
    cache["spot_valid"][:3] = False
    assert engine.ib_bounds(cache)[2] == 57
    cache["spot_valid"][3] = False
    assert engine.ib_bounds(cache) is None


def test_dedup_bounded_diameter_not_transitive_chain():
    raw = [
        {"center": value, "source_mask": mask, "name": str(mask)}
        for value, mask in [(100.0, 1), (100.19, 2), (100.38, 4)]
    ]
    levels = engine.deduplicate_levels(raw, 0.1)
    assert len(levels) == 2
    assert levels[0]["center"] == pytest.approx(100.095)
    assert levels[0]["source_mask"] == 3
    assert levels[1]["center"] == 100.38


def test_future_oi_unavailable_and_new_invalid_report_invalidates_prior():
    cache = make_cache()
    cache["oi_contract_idx"] = np.array([2, 2, 2], np.int32)
    cache["oi_value"] = np.array([10, 900, 999], np.int64)
    cache["oi_available_ns"] = cache["time_ns"][[0, 100, 120]]
    cache["oi_valid"] = np.array([True, True, False])
    oi = engine.available_oi_matrix(cache)
    assert oi[99, 2] == 10 and oi[100, 2] == 900
    assert np.isnan(oi[120, 2]) and np.isnan(oi[100, 0])


def test_future_source_perturbation_cannot_change_past_actions_states_levels():
    cache = make_cache()
    baseline = engine.build_day(cache)
    changed = {name: value.copy() for name, value in cache.items()}
    changed["spot"][101:] = 999.0
    changed["bid"][101:] = 500.0
    changed["ask"][101:] = 600.0
    changed["delta"][101:] = 0.01
    changed["iv"][101:] = 4.0
    changed["oi_contract_idx"] = np.append(changed["oi_contract_idx"], 2)
    changed["oi_value"] = np.append(changed["oi_value"], 1_000_000)
    changed["oi_available_ns"] = np.append(
        changed["oi_available_ns"], changed["time_ns"][101]
    )
    changed["oi_valid"] = np.append(changed["oi_valid"], True)
    other = engine.build_day(changed)
    for name in ("states", "levels", "actions"):
        old, new = getattr(baseline, name), getattr(other, name)
        pd.testing.assert_frame_equal(
            old.loc[old.state_i <= 100].reset_index(drop=True),
            new.loc[new.state_i <= 100].reset_index(drop=True),
        )
    assert "net_base" not in baseline.actions and "exit_i" not in baseline.actions


def test_future_only_contract_identity_does_not_leak_into_past_counts_or_actions():
    cache = make_cache()
    baseline = engine.build_day(cache)
    changed = {key: value.copy() for key, value in cache.items()}
    changed["strike"] = np.append(changed["strike"], 150.0)
    changed["right"] = np.append(changed["right"], 0)
    for field in ("bid", "ask", "delta", "iv", "vega", "theta"):
        extra = np.full((391, 1), np.nan)
        extra[101:] = {
            "bid": 1.0,
            "ask": 1.1,
            "delta": 0.5,
            "iv": 0.2,
            "vega": 1.0,
            "theta": -0.1,
        }[field]
        changed[field] = np.concatenate([changed[field], extra], axis=1)
    extra_flags = np.zeros((391, 1), np.uint8)
    extra_flags[101:] = 7
    changed["row_flags"] = np.concatenate([changed["row_flags"], extra_flags], axis=1)
    changed["oi_contract_idx"] = np.append(changed["oi_contract_idx"], 6)
    changed["oi_value"] = np.append(changed["oi_value"], 1_000_000)
    changed["oi_available_ns"] = np.append(
        changed["oi_available_ns"], changed["time_ns"][101]
    )
    changed["oi_valid"] = np.append(changed["oi_valid"], True)
    other = engine.build_day(changed)
    for name in ("states", "levels", "actions"):
        old, new = getattr(baseline, name), getattr(other, name)
        pd.testing.assert_frame_equal(
            old.loc[old.state_i <= 100].reset_index(drop=True),
            new.loc[new.state_i <= 100].reset_index(drop=True),
        )
    known = engine.known_contract_matrix(changed)
    assert not known[100, 6] and known[101, 6]


def test_every_offered_target_and_stop_are_causal_and_spaced():
    cache = make_cache()
    day = engine.build_day(cache)
    assert len(day.actions) > 0
    merged = day.actions.merge(
        day.states[["state_i", "spot", "ib_range", "eligible"]], on="state_i"
    )
    direction = np.where(merged.right == 0, 1.0, -1.0)
    assert merged.eligible.all()
    assert (direction * (merged.target_center - merged.spot) > 2 * merged.band).all()
    assert (
        direction * (merged.target_center - merged.spot) <= 3 * merged.ib_range
    ).all()
    assert (direction * (merged.stop_center - merged.spot) < -2 * merged.band).all()
    assert day.actions.groupby(["state_i", "contract_i"]).size().max() > 1


def test_contract_delta_tie_strike_and_duplicate_bucket_removal():
    cache = make_cache()
    cache["delta"][60, [0, 2, 4]] = 0.5
    assert engine.selected_contracts(cache, 60, 0) == [(0, 0.35)]
    cache["ask"][61, 0] = np.nan
    assert engine.selected_contracts(cache, 60, 0) == [(0, 0.35)]


def test_intermediate_levels_do_not_close_chosen_target():
    cache = make_cache()
    cache["spot"][61:64] = [100.5, 101.0, 102.1]
    labels = engine.evaluate_actions(cache, pd.DataFrame([action()]))
    row = labels.iloc[0]
    assert row.reason == "TARGET" and row.trigger_i == 63 and row.exit_i == 64
    assert row.hold_minutes == 3


def test_gap_at_entry_cannot_cancel_committed_fill_and_earliest_exit_next_minute():
    cache = make_cache()
    cache["spot"][61] = 103.0
    cache["ask"][61, 2] = 2.0
    cache["bid"][62, 2] = 0.5
    row = engine.evaluate_actions(cache, pd.DataFrame([action()])).iloc[0]
    assert row.status == "FILLED" and row.entry_ask == 2.0
    assert row.exit_i == 62 and row.trigger_i == 61 and row.reason == "TARGET"
    assert row.net_base == pytest.approx(-154.6)


def test_put_target_and_stop_priority_when_both_conditions_hold():
    cache = make_cache()
    cache["spot"][61] = 97.0
    row = engine.evaluate_actions(
        cache, pd.DataFrame([action(contract=3, side=1, target=98.0, stop=102.0)])
    ).iloc[0]
    assert row.reason == "TARGET" and row.exit_i == 62
    cache["spot"][61] = 100.0
    trigger, exit_i, reason, _ = engine.exit_trigger(
        cache["spot"], cache["spot_valid"], 60, 0, 100.0, 100.0, 0.1
    )
    assert reason == "STOP" and trigger == 61 and exit_i == 62


def test_missing_spot_delays_trigger_without_claiming_a_touch():
    cache = make_cache()
    cache["spot"][61:64] = [105.0, np.nan, 103.0]
    cache["spot_valid"][61:63] = False
    row = engine.evaluate_actions(cache, pd.DataFrame([action()])).iloc[0]
    assert row.trigger_i == 63 and row.exit_i == 64
    assert row.missing_spot_count == 2


def test_eod_close_not_fixed_hold_and_last_possible_trigger():
    cache = make_cache()
    row = engine.evaluate_actions(
        cache, pd.DataFrame([action(state=375, target=150.0, stop=50.0)])
    ).iloc[0]
    assert row.reason == "EOD" and row.exit_i == 385 and row.hold_minutes == 9
    cache["spot"][384] = 151.0
    row = engine.evaluate_actions(
        cache, pd.DataFrame([action(state=375, target=150.0, stop=50.0)])
    ).iloc[0]
    assert row.reason == "TARGET" and row.trigger_i == 384 and row.exit_i == 385


def test_missing_entry_no_fill_no_substitute_and_missing_exit_zero():
    cache = make_cache()
    actions = pd.DataFrame([action()])
    cache["ask"][61, 2] = np.nan
    row = engine.evaluate_actions(cache, actions).iloc[0]
    assert row.status == "NO_FILL" and row.net_base == 0 and row.hold_minutes == 0
    cache["ask"][61, 2] = 1.1
    cache["spot"][61] = 103.0
    cache["bid"][62, 2] = np.nan
    row = engine.evaluate_actions(cache, actions).iloc[0]
    assert row.status == "FILLED" and row.missing_exit and row.exit_bid == 0.0
    assert row.net_base == pytest.approx(-113.6)
    assert row.net_adverse == pytest.approx(-114.6)


def dp_fixture():
    actions = pd.DataFrame(
        [action(state=i, action_id=k) for k, i in enumerate([60, 61, 62, 64, 65])]
    )
    labels = pd.DataFrame(
        [
            {
                "action_id": k,
                "status": "FILLED",
                "trigger_i": ex - 1,
                "exit_i": ex,
                "reason": "TARGET",
                "entry_ask": 1.0,
                "exit_bid": 2.0,
                "missing_exit": False,
                "missing_spot_count": 0,
                "net_base": reward,
                "net_adverse": reward - 2.0,
                "hold_minutes": ex - (i + 1),
            }
            for k, (i, ex, reward) in enumerate(
                [
                    (60, 66, 8.0),
                    (61, 63, 5.0),
                    (62, 64, 20.0),
                    (64, 66, 9.0),
                    (65, 67, 3.0),
                ]
            )
        ]
    )
    return actions, labels


def brute_value(actions, labels, minute):
    if minute > engine.LAST_STATE:
        return 0.0
    available = actions.loc[actions.state_i >= minute]
    best = 0.0
    for row in available.itertuples(index=False):
        label = labels.loc[labels.action_id == row.action_id].iloc[0]
        if label.status == "FILLED":
            best = max(
                best, label.net_base + brute_value(actions, labels, label.exit_i + 1)
            )
    return best


def test_dp_matches_bruteforce_and_conservative_next_state():
    actions, labels = dp_fixture()
    result = engine.solve_oracle(actions, labels)
    assert result.value[60] == brute_value(actions, labels, 60) == 23.0
    assert result.trajectory.action_id.tolist() == [2, 4]
    assert result.summary["net_adverse"] == 19.0
    assert result.summary["adverse_reoptimized"] is False
    assert result.trajectory.iloc[1].state_i > result.trajectory.iloc[0].exit_i
    assert len(result.advantages) == len(actions)


def test_wait_wins_zero_reward_and_cash_always_available():
    actions, labels = dp_fixture()
    labels["net_base"] = -1.0
    labels.loc[0, "net_base"] = 0.0
    result = engine.solve_oracle(actions, labels)
    assert result.summary["net_base"] == 0.0 and result.trajectory.empty
    assert not result.advantages.state_optimal_action.any()


def test_policy_never_rescues_missing_chosen_fill_and_respects_exit():
    actions, labels = dp_fixture()
    policy = engine.evaluate_policy(
        actions, labels, np.array([10.0, 100.0, 50.0, 30.0, 20.0])
    )
    assert policy.ledger.action_id.tolist() == [0]
    labels.loc[0, ["status", "net_base", "net_adverse", "exit_i"]] = [
        "NO_FILL",
        0.0,
        0.0,
        61,
    ]
    policy = engine.evaluate_policy(
        actions, labels, np.array([10.0, 100.0, 50.0, 30.0, 20.0])
    )
    assert policy.attempts.action_id.tolist() == [0, 1, 3]
    assert policy.ledger.action_id.tolist() == [1, 3]
    assert policy.summary["no_fill_attempts"] == 1


def test_empty_causal_universe_has_zero_oracle_value():
    cache = make_cache()
    cache["spot_valid"][:60] = False
    data = engine.build_day(cache)
    assert data.actions.empty and len(data.states) == 316
    labels = engine.evaluate_actions(cache, data.actions)
    result = engine.solve_oracle(data.actions, labels)
    assert result.trajectory.empty and result.value[60] == 0.0
