from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from neural.jepa.build_king_gex_manage30_v1 import ACTION_IDS, M0_FEATURES
from neural.jepa.evaluate_king_gex_manage30_v1 import (
    ACTION_FEATURES,
    ARMS,
    DEVELOPMENT_MONTHS,
    MODEL_PARAMS,
    _attach_selected_outcome,
    _expand_actions,
    _read_fold_checkpoint,
    _run_fold,
    _score_events,
    _write_fold_checkpoint,
    protocol,
    user_gate_pass,
)


def _event(*, decision_available: int = 1) -> pd.DataFrame:
    row: dict[str, object] = {
        "ticker": "QQQ",
        "trade_date": "20230103",
        "minute": 680,
        "month": "202301",
        "action": "CALL",
        **{name: 0.0 for name in M0_FEATURES},
    }
    row["decision_state_available"] = decision_available
    for action in ACTION_IDS:
        realized_return = 0.10
        if action == "S30":
            realized_return = -0.20
        elif action == "E30":
            realized_return = 0.35
        row[f"outcome_{action}_realized_return"] = realized_return
        row[f"outcome_{action}_exit_minutes"] = 30 if action == "E30" else 60
        row[f"outcome_{action}_status"] = int(realized_return > 0.0)
        row[f"outcome_{action}_exit_reason"] = "decision" if action == "E30" else "horizon"
    return pd.DataFrame([row])


class _E30Model:
    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return frame["manage_is_e30"].to_numpy(dtype=float) * 0.50 - 0.10


class _NegativeModel:
    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return np.full(len(frame), -0.10, dtype=float)


def test_protocol_freezes_development_before_outer_and_2026() -> None:
    payload = protocol()
    assert ARMS == ("M0_PATH", "M1_SYNTH_GREEKS")
    assert DEVELOPMENT_MONTHS == tuple(f"2023{month:02d}" for month in range(1, 13))
    assert payload["initial_train"] == "202201..202212"
    assert payload["outer_2024_2025_opened"] is False
    assert payload["holdout_2026_opened"] is False
    assert len(payload["snapshot_clarification_sha256"]) == 64
    assert MODEL_PARAMS["objective"] == "huber"
    assert MODEL_PARAMS["n_estimators"] == 300


def test_feature_contract_has_no_outcome_fields() -> None:
    forbidden = ("outcome", "exit_reason", "realized_return", "future", "oracle")
    model_fields = [*M0_FEATURES, *ACTION_FEATURES]
    assert not [name for name in model_fields if any(token in name for token in forbidden)]


def test_expand_actions_keeps_counterfactuals_together_and_relative_to_b00() -> None:
    expanded = _expand_actions(_event(), M0_FEATURES, include_target=True)
    assert len(expanded) == 17
    assert expanded[["ticker", "trade_date", "minute"]].drop_duplicates().shape[0] == 1
    targets = expanded.set_index("manage_action")["target_advantage"]
    assert targets["B00"] == 0.0
    assert np.isclose(targets["S30"], -0.30)
    assert np.isclose(targets["E30"], 0.25)
    assert expanded["sample_weight"].eq(1.0 / 17.0).all()


def test_score_selects_positive_e30_but_defaults_to_b00_without_state() -> None:
    medians = pd.Series(0.0, index=[*M0_FEATURES, *ACTION_FEATURES])
    selected = _score_events(_event(), M0_FEATURES, _E30Model(), medians)
    assert selected.iloc[0]["manage_action"] == "E30"
    assert selected.iloc[0]["predicted_advantage"] == 0.40

    unavailable = _score_events(
        _event(decision_available=0), M0_FEATURES, _E30Model(), medians
    )
    assert unavailable.iloc[0]["manage_action"] == "B00"
    assert unavailable.iloc[0]["predicted_advantage"] == 0.0

    negative = _score_events(_event(), M0_FEATURES, _NegativeModel(), medians)
    assert negative.iloc[0]["manage_action"] == "B00"


def test_inference_action_availability_never_reads_future_outcomes() -> None:
    event = _event()
    for action in ACTION_IDS:
        event[f"outcome_{action}_realized_return"] = np.nan
    expanded = _expand_actions(event, M0_FEATURES, include_target=False)
    assert set(expanded["manage_action"]) == set(ACTION_IDS)

    event["decision_state_available"] = 0
    unavailable = _expand_actions(event, M0_FEATURES, include_target=False)
    assert unavailable["manage_action"].tolist() == ["B00"]


def test_attach_selected_outcome_uses_only_chosen_management_action() -> None:
    scored = _event()
    scored["manage_action"] = "E30"
    scored["predicted_advantage"] = 0.25
    attached = _attach_selected_outcome(scored)
    assert attached.iloc[0]["realized_return"] == 0.35
    assert attached.iloc[0]["exit_minutes"] == 30
    assert attached.iloc[0]["exit_reason"] == "decision"


def test_user_gates_are_strict_at_pf_wr_trades_and_pnl_boundaries() -> None:
    passing = {
        "profit_factor": 1.300001,
        "win_rate": 0.450001,
        "trades": 13,
        "pnl": 0.000001,
        "minimum_hold": 30.0,
    }
    assert user_gate_pass(passing)
    for key, boundary in (
        ("profit_factor", 1.30),
        ("win_rate", 0.45),
        ("trades", 12),
        ("pnl", 0.0),
        ("minimum_hold", 29.999),
    ):
        failing = {**passing, key: boundary}
        assert not user_gate_pass(failing)


def test_real_lightgbm_fold_scheduler_and_checkpoint_smoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows: list[dict[str, object]] = []
    for year, count in ((2022, 60), (2023, 20)):
        for index in range(count):
            day = index // 2 + 1
            row = _event().iloc[0].to_dict()
            row["trade_date"] = f"{year}01{day:02d}"
            row["month"] = f"{year}01"
            row["minute"] = 680 + (index % 2) * 120
            row["action"] = "CALL" if index % 2 == 0 else "PUT"
            for offset, feature in enumerate(M0_FEATURES):
                row[feature] = float((index + offset) % 11) / 10.0
            row["decision_state_available"] = 1
            baseline = 0.10 if index % 3 == 0 else -0.05
            for action in ACTION_IDS:
                realized = baseline
                if action == "E30":
                    realized += 0.20 if index % 2 == 0 else -0.20
                elif action != "B00":
                    realized -= 0.02
                row[f"outcome_{action}_realized_return"] = realized
                row[f"outcome_{action}_exit_minutes"] = 30 if action == "E30" else 60
                row[f"outcome_{action}_status"] = int(np.sign(realized))
                row[f"outcome_{action}_exit_reason"] = (
                    "decision" if action == "E30" else "horizon"
                )
            rows.append(row)
    data = pd.DataFrame(rows)
    monkeypatch.setitem(MODEL_PARAMS, "n_estimators", 3)
    monkeypatch.setitem(MODEL_PARAMS, "min_child_samples", 5)
    model, medians, predictions, trades, metrics = _run_fold(
        data, "202301", "QQQ", "M0_PATH", 1
    )
    assert len(predictions) == 20
    assert len(trades) == 20
    assert len(metrics) == 1
    assert metrics.iloc[0]["train_events"] == 60
    identity = {"schema": "test_fold", "month": "202301"}
    _write_fold_checkpoint(
        tmp_path, identity, model, medians, predictions, trades, metrics
    )
    cached = _read_fold_checkpoint(tmp_path, identity)
    assert cached is not None
    assert [len(frame) for frame in cached] == [20, 20, 1]
