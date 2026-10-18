"""Independent oracle-auditor fixtures; no market-data access."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location(
    "audit_engine_fixture", Path(__file__).with_name("audit_engine.py")
)
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def action(state, action_id, contract=0, side=0, target=102.0, stop=98.0, band=0.1):
    return {
        "action_id": action_id, "state_i": state, "entry_i": state + 1,
        "contract_i": contract, "right": side, "strike": 100.0,
        "selected_delta": 0.5, "delta_bucket": 0.5,
        "target_level_id": 2, "target_center": target, "target_source_mask": 1,
        "stop_level_id": 0, "stop_center": stop, "stop_source_mask": 1,
        "band": band, "entry_level_id": 1,
    }


def label(action_id, state, exit_i, reward, status="FILLED"):
    return {
        "action_id": action_id, "status": status,
        "trigger_i": exit_i - 1 if status == "FILLED" else -1,
        "exit_i": exit_i, "reason": "TARGET" if status == "FILLED" else "NO_FILL",
        "entry_ask": 1.0 if status == "FILLED" else np.nan,
        "exit_bid": 2.0 if status == "FILLED" else np.nan,
        "missing_exit": False, "missing_spot_count": 0,
        "net_base": reward if status == "FILLED" else 0.0,
        "net_adverse": reward - 2 if status == "FILLED" else 0.0,
        "hold_minutes": exit_i - (state + 1) if status == "FILLED" else 0,
    }


def cache_fixture():
    time = pd.date_range("2023-01-03 09:30", periods=391, freq="min").asi8
    spot = np.full(391, 100.0)
    spot[:60] = np.linspace(99.0, 101.0, 60)
    return {
        "time_ns": time, "strike": np.array([100.0]), "right": np.array([0], np.int8),
        "spot": spot, "spot_valid": np.ones(391, bool),
        "bid": np.ones((391, 1)), "ask": np.full((391, 1), 1.1),
        "delta": np.full((391, 1), 0.5), "iv": np.full((391, 1), 0.2),
        "vega": np.ones((391, 1)), "theta": np.full((391, 1), -0.1),
        "row_flags": np.full((391, 1), 7, np.uint8),
        "oi_contract_idx": np.array([0], np.int32), "oi_value": np.array([10], np.int64),
        "oi_available_ns": np.array([time[0]], np.int64), "oi_valid": np.array([True]),
    }


def test_independent_dp_matches_literal_bruteforce_and_tie_rules():
    states = [60, 61, 62, 64, 65]
    exits = [66, 63, 64, 66, 67]
    rewards = [8.0, 5.0, 20.0, 9.0, 3.0]
    actions = pd.DataFrame([action(state, i) for i, state in enumerate(states)])
    labels = pd.DataFrame([
        label(i, state, exit_i, reward)
        for i, (state, exit_i, reward) in enumerate(zip(states, exits, rewards, strict=True))
    ])
    value, ledger, _ = audit.independent_dp(actions, labels)
    assert value[audit.FIRST_STATE] == audit.brute_force_value(actions, labels) == 23.0
    assert ledger.action_id.tolist() == [2, 4]
    labels["net_base"] = -1.0
    labels.loc[0, "net_base"] = 0.0
    value, ledger, advantages = audit.independent_dp(actions, labels)
    assert value[audit.FIRST_STATE] == 0.0 and ledger.empty
    assert not advantages.state_optimal_action.any()  # WAIT wins exact zero tie.


def test_independent_execution_ignores_intermediates_and_uses_stop_priority():
    cache = cache_fixture()
    cache["spot"][61:64] = [100.5, 101.0, 102.1]
    actions = pd.DataFrame([action(60, 0)])
    row = audit.reconstruct_labels(cache, actions).iloc[0]
    assert row.reason == "TARGET" and row.trigger_i == 63 and row.exit_i == 64
    cache["spot"][61] = 100.0
    both = pd.DataFrame([action(60, 0, target=100.0, stop=100.0)])
    row = audit.reconstruct_labels(cache, both).iloc[0]
    assert row.reason == "STOP" and row.exit_i == 62


def test_no_fill_is_zero_without_rescue_and_missing_exit_is_zero_liquidation():
    cache = cache_fixture()
    actions = pd.DataFrame([action(60, 0)])
    cache["ask"][61, 0] = np.nan
    row = audit.reconstruct_labels(cache, actions).iloc[0]
    assert row.status == "NO_FILL" and row.net_base == 0 and row.exit_i == 61
    cache["ask"][61, 0] = 1.1
    cache["spot"][61] = 103.0
    cache["bid"][62, 0] = np.nan
    row = audit.reconstruct_labels(cache, actions).iloc[0]
    assert row.status == "FILLED" and row.missing_exit and row.exit_bid == 0
    assert row.net_base == pytest.approx(-113.6)
    assert row.net_adverse == pytest.approx(-114.6)


def test_known_contract_and_oi_are_causal_under_future_append():
    cache = cache_fixture()
    known, oi = audit.independent_known_and_oi(cache)
    changed = {name: value.copy() for name, value in cache.items()}
    changed["strike"] = np.append(changed["strike"], 110.0)
    changed["right"] = np.append(changed["right"], 1).astype(np.int8)
    for name in ("bid", "ask", "delta", "iv", "vega", "theta", "row_flags"):
        fill = 0 if name == "row_flags" else np.nan
        changed[name] = np.column_stack([changed[name], np.full(391, fill)])
    changed["row_flags"][200:, 1] = 7
    changed["oi_contract_idx"] = np.append(changed["oi_contract_idx"], 1)
    changed["oi_value"] = np.append(changed["oi_value"], 999)
    changed["oi_available_ns"] = np.append(changed["oi_available_ns"], changed["time_ns"][200])
    changed["oi_valid"] = np.append(changed["oi_valid"], True)
    other_known, other_oi = audit.independent_known_and_oi(changed)
    assert np.array_equal(known[:200], other_known[:200, :1])
    assert np.all(~other_known[:200, 1]) and np.isnan(other_oi[:200, 1]).all()
    assert other_known[200, 1] and other_oi[200, 1] == 999
    assert oi[199, 0] == other_oi[199, 0] == 10


def test_future_path_changes_labels_but_not_frozen_action_definition():
    cache = cache_fixture()
    actions = pd.DataFrame([action(60, 0)])
    before = actions.copy(deep=True)
    first = audit.reconstruct_labels(cache, actions)
    changed = {name: value.copy() for name, value in cache.items()}
    changed["spot"][61:] = 103.0
    changed["bid"][62:, 0] = 4.0
    second = audit.reconstruct_labels(changed, actions)
    pd.testing.assert_frame_equal(actions, before)
    assert first.reason.iloc[0] == "EOD"
    assert second.reason.iloc[0] == "TARGET"
    assert first.net_base.iloc[0] != second.net_base.iloc[0]


def test_action_geometry_accepts_nonempty_numpy_contract_indices():
    """Regression: ndarray truth testing crashed the first full-audit attempt."""
    cache = cache_fixture()
    states = pd.DataFrame([{
        "state_i": 60, "eligible": True, "spot": 100.0, "ib_range": 10.0,
        "band": 0.1, "entry_level_id": 1, "known_contract_count": 1,
        "oi_known_count": 1, "oi_missing_count": 0,
    }])
    levels = pd.DataFrame([
        {"state_i": 60, "level_id": 0, "center": 98.0, "source_mask": 1},
        {"state_i": 60, "level_id": 1, "center": 100.0, "source_mask": 1},
        {"state_i": 60, "level_id": 2, "center": 102.0, "source_mask": 1},
    ])
    actions = pd.DataFrame([action(60, 0)])
    actions.loc[0, "delta_bucket"] = audit.DELTA_BUCKETS[0]
    assert audit.validate_action_geometry(cache, states, levels, actions) == 1


def test_raw_fill_distinguishes_present_invalid_exit_from_valid_zero_bid():
    cache = cache_fixture()
    times = pd.to_datetime(cache["time_ns"][[61, 62, 63]])
    raw = pd.DataFrame([
        {"strike": 100.0, "right": "CALL", "timestamp": times[0],
         "bid": 0.9, "ask": 1.0},
        {"strike": 100.0, "right": "CALL", "timestamp": times[1],
         "bid": 0.2, "ask": 0.0},  # Present, but invalid ask/crossed quote.
        {"strike": 100.0, "right": "CALL", "timestamp": times[2],
         "bid": 0.0, "ask": 1.0},  # Zero bid remains a valid liquidation quote.
    ]).set_index(["strike", "right", "timestamp"])
    ledger = pd.DataFrame([
        {"right": 0, "strike": 100.0, "entry_i": 61, "entry_ask": 1.0,
         "exit_i": 62, "exit_bid": 0.0, "missing_exit": True},
        {"right": 0, "strike": 100.0, "entry_i": 61, "entry_ask": 1.0,
         "exit_i": 63, "exit_bid": 0.0, "missing_exit": False},
    ])
    assert audit.validate_raw_ledger_fills(raw, cache, ledger) == 2


def test_binary_float_accounting_controls_exact_dp_tie_identity():
    # Decimal economics are equal, while the frozen binary-float protocol has a
    # representational difference that must preserve the action identity.
    low_id_reward = audit.canonical_float_net(10.3, 10.7)
    high_id_reward = audit.canonical_float_net(7.0, 7.4)
    assert audit.decimal_net(10.3, 10.7) == audit.decimal_net(7.0, 7.4) == 35.4
    assert low_id_reward < high_id_reward
    actions = pd.DataFrame([action(60, 10), action(60, 11)])
    labels = pd.DataFrame([
        label(10, 60, 62, low_id_reward), label(11, 60, 62, high_id_reward)
    ])
    _, ledger, advantages = audit.independent_dp(actions, labels)
    assert ledger.action_id.tolist() == [11]
    assert advantages.loc[advantages.action_id == 11, "state_optimal_action"].item()


def test_stop_boundary_uses_frozen_subtract_then_compare_order():
    spot = 4278.24
    band = 0.8800000000000182
    centers = np.array([4280.0, 4282.263599999999])
    # Reassociation would exclude 4280 because spot + 2*band rounds to 4280.
    assert spot + 2 * band == 4280.0
    assert -1 * (centers[0] - spot) < -2 * band
    assert audit.expected_opposite_stop(centers, spot, band, -1) == 4280.0
