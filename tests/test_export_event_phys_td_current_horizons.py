from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from neural.jepa.dataset import RobustNormalizer
from neural.jepa.export_event_phys_td_current_horizons import export_current_horizon_features
from neural.jepa.walkforward_event_phys_td_jepa_oof import EventPhysTDJEPA, EventPhysTDJEPAConfig


def _model() -> tuple[EventPhysTDJEPA, RobustNormalizer]:
    torch.manual_seed(7)
    config = EventPhysTDJEPAConfig(
        input_dim=1,
        q_dim=1,
        context_len=2,
        horizons=[1, 6],
        z_dim=4,
        phys_dim=1,
        delta_dim=2,
        horizon_dim=2,
        hidden_dim=8,
        num_layers=1,
        dropout=0.0,
    )
    model = EventPhysTDJEPA(config).eval()
    normalizer = RobustNormalizer.fit(pd.DataFrame({"feature": [0.0, 7.0]}), ["feature"])
    return model, normalizer


def _frame() -> pd.DataFrame:
    minutes = np.arange(630, 670, 5)
    return pd.DataFrame(
        {
            "ticker": ["SPY"] * len(minutes),
            "date": ["20260102"] * len(minutes),
            "trade_date": ["20260102"] * len(minutes),
            "expiration": ["20260102"] * len(minutes),
            "expiry_mode": ["zero_dte"] * len(minutes),
            "timestamp": pd.date_range("2026-01-02 10:30", periods=len(minutes), freq="5min"),
            "time": [f"10:{30 + 5 * index:02d}" for index in range(len(minutes))],
            "minute": minutes,
            "feature": np.arange(len(minutes), dtype=np.float32),
        }
    )


def test_current_horizon_export_has_same_rows_for_h1_and_h6_without_future_target() -> None:
    model, normalizer = _model()
    output = export_current_horizon_features(
        model,
        normalizer,
        _frame(),
        SimpleNamespace(expected_step_minutes=5, infer_batch_size=16, group_expiry_mode=True),
        torch.device("cpu"),
        horizons=[1, 6],
    )
    assert output["minute"].tolist() == [635, 640, 645, 650, 655, 660, 665]
    assert len([column for column in output if column.startswith("horizon_pred_h1_")]) == 4
    assert len([column for column in output if column.startswith("horizon_pred_h6_")]) == 4
    assert not any("target" in column for column in output)


def test_future_mutation_cannot_change_prior_horizon_predictions() -> None:
    model, normalizer = _model()
    args = SimpleNamespace(expected_step_minutes=5, infer_batch_size=16, group_expiry_mode=True)
    original = export_current_horizon_features(
        model, normalizer, _frame(), args, torch.device("cpu"), horizons=[1, 6]
    )
    changed_frame = _frame()
    changed_frame.loc[changed_frame["minute"].ge(655), "feature"] += 1000.0
    changed = export_current_horizon_features(
        model, normalizer, changed_frame, args, torch.device("cpu"), horizons=[1, 6]
    )
    columns = [column for column in original if column.startswith("horizon_")]
    assert np.allclose(
        original.loc[original["minute"].lt(655), columns],
        changed.loc[changed["minute"].lt(655), columns],
    )


def test_export_rejects_untrained_horizon() -> None:
    model, normalizer = _model()
    with pytest.raises(ValueError, match="not in checkpoint"):
        export_current_horizon_features(
            model,
            normalizer,
            _frame(),
            SimpleNamespace(expected_step_minutes=5, infer_batch_size=16, group_expiry_mode=True),
            torch.device("cpu"),
            horizons=[12],
        )
