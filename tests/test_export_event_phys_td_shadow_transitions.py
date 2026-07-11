from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from neural.jepa.dataset import RobustNormalizer
from neural.jepa.export_event_phys_td_shadow_transitions import export_from_checkpoint, prepare_frame
from neural.jepa.walkforward_event_phys_td_jepa_oof import EventPhysTDJEPA, EventPhysTDJEPAConfig


def _checkpoint(path: Path) -> None:
    config = EventPhysTDJEPAConfig(
        input_dim=1,
        q_dim=1,
        context_len=2,
        horizons=[1],
        z_dim=4,
        phys_dim=1,
        delta_dim=2,
        horizon_dim=2,
        hidden_dim=8,
        num_layers=1,
        dropout=0.0,
    )
    model = EventPhysTDJEPA(config)
    normalizer = RobustNormalizer.fit(pd.DataFrame({"feature": [0.0, 1.0]}), ["feature"])
    torch.save(
        {
            "component": "event_phys_td_jepa_encoder",
            "model_state_dict": model.state_dict(),
            "config": config.to_dict(),
            "feature_cols": ["feature"],
            "physical_cols": ["feature"],
            "feature_names": [],
            "normalizer": normalizer.to_dict(),
            "metadata": {
                "deploy_month": "202602",
                "train_months": ["202501", "202502"],
                "args": {"expected_step_minutes": 5, "infer_batch_size": 16, "group_expiry_mode": True},
            },
        },
        path,
    )


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["SPY"] * 4,
            "trade_date": ["20260102"] * 4,
            "expiration": ["20260102"] * 4,
            "expiry_mode": ["zero_dte"] * 4,
            "option_price_mode": ["executable_quote"] * 4,
            "timestamp": pd.to_datetime(["2026-01-02 10:30", "2026-01-02 10:35", "2026-01-02 10:40", "2026-01-02 10:45"]),
            "time": ["10:30", "10:35", "10:40", "10:45"],
            "minute": [630, 635, 640, 645],
            "feature": np.arange(4, dtype=np.float32),
        }
    )


def test_checkpoint_export_proves_cutoff_and_target_availability(tmp_path: Path) -> None:
    model_path = tmp_path / "encoder.pt"
    _checkpoint(model_path)
    transitions, metadata = export_from_checkpoint(
        model_path,
        _frame(),
        start_month="202601",
        end_month="202601",
        device="cpu",
    )
    assert len(transitions) == 2
    assert metadata["encoder_deploy_month"] == "202602"
    assert metadata["target_z_live_feature"] is False
    assert metadata["target_available_only_at_target_timestamp"] is True
    assert transitions["minute"].tolist() == [635, 640]
    assert transitions["target_minute"].tolist() == [640, 645]


def test_prepare_frame_rejects_june_even_when_requested_explicitly() -> None:
    with pytest.raises(ValueError, match="June 2026 is sealed"):
        prepare_frame(_frame(), ["feature"], "202601", "202606")
