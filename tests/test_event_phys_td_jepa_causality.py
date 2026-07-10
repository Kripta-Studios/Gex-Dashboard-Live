from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa.event_option_component_live import LIVE_INCONSISTENT_INTRADAY_STATE_FEATURES
from neural.jepa.walkforward_event_phys_td_jepa_oof import (
    EventPhysTDJEPADataset,
    build_contexts,
    filter_frame_to_month_cutoff,
    select_feature_columns,
)


class _IdentityNormalizer:
    def transform_frame(self, frame: pd.DataFrame) -> np.ndarray:
        return frame[["feature"]].to_numpy(dtype=np.float32)


def test_phys_td_feature_selection_rejects_live_inconsistent_state() -> None:
    frame = pd.DataFrame(
        {
            "safe_feature": [1.0],
            "dist_ib_high_bps": [2.0],
            "future_outcome": [3.0],
            **{name: [float(index)] for index, name in enumerate(LIVE_INCONSISTENT_INTRADAY_STATE_FEATURES)},
        }
    )

    selected = select_feature_columns(frame, entry_start_minute_et=630)

    assert "safe_feature" in selected
    assert "dist_ib_high_bps" in selected
    assert "future_outcome" not in selected
    assert not (set(selected) & LIVE_INCONSISTENT_INTRADAY_STATE_FEATURES)


def test_phys_td_feature_selection_rejects_initial_balance_before_completion() -> None:
    frame = pd.DataFrame({"safe_feature": [1.0], "dist_ib_high_bps": [2.0]})

    selected = select_feature_columns(frame, entry_start_minute_et=600)

    assert selected == ["safe_feature"]


def test_phys_td_dataset_never_bridges_missing_five_minute_bars() -> None:
    frame = pd.DataFrame(
        {
            "ticker": ["SPY"] * 6,
            "date": ["20260102"] * 6,
            "minute": [630, 635, 640, 650, 655, 660],
            "feature": np.arange(6, dtype=np.float32),
        }
    )
    dataset = EventPhysTDJEPADataset(
        frame,
        ["feature"],
        ["feature"],
        _IdentityNormalizer(),
        context_len=2,
        horizons=[1],
        group_cols=["ticker", "date"],
        expected_step_minutes=5,
    )

    assert len(dataset) == 2
    first_ctx = dataset[0][0].numpy().reshape(-1).tolist()
    second_ctx = dataset[1][0].numpy().reshape(-1).tolist()
    assert first_ctx == [0.0, 1.0]
    assert second_ctx == [3.0, 4.0]


def test_export_contexts_require_exact_five_minute_continuity() -> None:
    arr = np.arange(6, dtype=np.float32).reshape(-1, 1)

    _ctx, _delta, positions = build_contexts(
        arr,
        context_len=3,
        minutes=[630, 635, 640, 650, 655, 660],
        expected_step_minutes=5,
    )

    assert positions == [2, 5]


def test_month_cutoff_physically_removes_sealed_holdout() -> None:
    frame = pd.DataFrame(
        {
            "trade_date": [20260529, 20260601, 20260630],
            "value": [1.0, 2.0, 3.0],
        }
    )

    filtered = filter_frame_to_month_cutoff(frame, "202605")

    assert filtered["trade_date"].tolist() == [20260529]
