from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa.analyze_adajepa_payoff_separability import (
    decompose_ticker_month,
    fast_export_live_adapter_features,
)
from neural.jepa.evaluate_adajepa_shadow_adapter import export_live_adapter_features


def _transition_frame() -> pd.DataFrame:
    rows = []
    for index, minute in enumerate((630, 635, 640)):
        row = {
            "ticker": "SPY",
            "trade_date": "20260102",
            "expiration": "20260102",
            "expiry_mode": "zero_dte",
            "timestamp": pd.Timestamp("2026-01-02 10:30") + pd.Timedelta(minutes=5 * index),
            "target_timestamp": pd.Timestamp("2026-01-02 10:35") + pd.Timedelta(minutes=5 * index),
            "target_available_after_timestamp": pd.Timestamp("2026-01-02 10:35") + pd.Timedelta(minutes=5 * index),
            "time": f"{10 + (30 + 5 * index) // 60:02d}:{(30 + 5 * index) % 60:02d}:00",
            "minute": minute,
        }
        for dimension in range(32):
            row[f"z_t_{dimension:02d}"] = 0.01 * (dimension + index)
            row[f"pred_z_{dimension:02d}"] = row[f"z_t_{dimension:02d}"] + 0.02
            row[f"target_z_{dimension:02d}"] = row[f"z_t_{dimension:02d}"] + 0.03 + 0.001 * index
        rows.append(row)
    return pd.DataFrame(rows)


def test_fast_adapter_export_matches_torch_reference() -> None:
    frame = _transition_frame()
    fast = fast_export_live_adapter_features(
        frame, learning_rate=0.05, grad_clip=1.0, max_parameter_norm=0.5
    )
    reference = export_live_adapter_features(
        frame, learning_rate=0.05, grad_clip=1.0, max_parameter_norm=0.5, device="cpu"
    )
    vector_cols = [column for column in fast if column.startswith("ada_")]
    assert vector_cols == [column for column in reference if column.startswith("ada_")]
    assert np.allclose(fast[vector_cols], reference[vector_cols], atol=2e-7, rtol=2e-6)
    assert fast["updates_before_prediction"].tolist() == reference["updates_before_prediction"].tolist()
    assert fast["rollbacks_before_prediction"].tolist() == reference["rollbacks_before_prediction"].tolist()


def test_payoff_decomposition_separates_head_constant_and_oracle() -> None:
    actions = pd.DataFrame(
        {
            "event_id": [1, 1, 2, 2],
            "ticker": ["SPY"] * 4,
            "date": ["20260102"] * 4,
            "minute": [630, 630, 635, 635],
            "action": ["CALL", "PUT", "CALL", "PUT"],
            "pred_return": [0.4, 0.1, 0.3, 0.2],
            "target_return": [0.5, -0.2, -0.4, 0.6],
            "exit_minutes": [30.0] * 4,
        }
    )
    result = decompose_ticker_month(actions, "SPY", "202601", "PUT", "frozen")
    assert result["events"] == 2
    assert result["head_side_accuracy"] == 0.5
    assert result["constant_side_accuracy"] == 0.5
    assert result["head_mean_return"] == 0.05 - 1e-17 or np.isclose(result["head_mean_return"], 0.05)
    assert np.isclose(result["constant_mean_return"], 0.2)
    assert np.isclose(result["oracle_side_mean_return"], 0.55)


def test_fast_export_rejects_june() -> None:
    frame = _transition_frame()
    frame["trade_date"] = "20260601"
    try:
        fast_export_live_adapter_features(
            frame, learning_rate=0.05, grad_clip=1.0, max_parameter_norm=0.5
        )
    except ValueError as exc:
        assert "June 2026" in str(exc)
    else:
        raise AssertionError("June data was not rejected")
