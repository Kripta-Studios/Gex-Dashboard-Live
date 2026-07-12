from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neural.jepa.evaluate_wall_surface_flow_at_touch_v1 import (  # noqa: E402
    HORIZONS,
    label_candidate_session,
    paired_day_bootstrap,
    summarize_gate,
)


def _candidate(
    *,
    role: str = "support",
    spot: float = 101.0,
    ticker: str = "SPY",
    trade_date: str = "20240102",
    decision: str = "2024-01-02 10:00:00",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": [ticker],
            "trade_date": [trade_date],
            "minute": [pd.Timestamp(decision).hour * 60 + pd.Timestamp(decision).minute],
            "decision_dt": [pd.Timestamp(decision)],
            "wall_identity": ["put_gamma" if role == "support" else "call_gamma"],
            "wall_role": [role],
            "candidate_wall_strike": [100.0],
            "spot": [spot],
        }
    )


def _underlying() -> pd.DataFrame:
    times = pd.date_range("2024-01-02 10:00:00", "2024-01-02 13:00:00", freq="1min")
    frame = pd.DataFrame(
        {
            "bar_start": times,
            "open": 101.0,
            "high": 101.5,
            "low": 100.5,
            "close": 101.0,
        }
    )
    return frame


def test_label_includes_bar_t_excludes_bar_t_plus_h_and_requires_pierce() -> None:
    underlying = _underlying()
    underlying.loc[underlying["bar_start"].eq(pd.Timestamp("2024-01-02 10:00:00")), "low"] = 99.0
    # This extreme belongs to [t+h,t+h+1) and must not enter the 30m label.
    underlying.loc[underlying["bar_start"].eq(pd.Timestamp("2024-01-02 10:30:00")), ["open", "high", "low", "close"]] = [50.0, 50.0, 50.0, 50.0]
    labeled = label_candidate_session(_candidate(), underlying)
    assert labeled["path_complete_30m"].iloc[0] == 1
    assert labeled["pierced_30m"].iloc[0] == 1.0
    assert labeled["true_rejection_30m"].iloc[0] == 1.0
    assert labeled["accepted_break_30m"].iloc[0] == 0.0
    assert labeled["resolved_rejection_30m"].iloc[0] == 1.0


def test_defended_terminal_without_actual_pierce_is_unresolved() -> None:
    labeled = label_candidate_session(_candidate(), _underlying())
    assert labeled["pierced_30m"].iloc[0] == 0.0
    assert labeled["true_rejection_30m"].iloc[0] == 0.0
    assert labeled["accepted_break_30m"].iloc[0] == 0.0
    assert np.isnan(labeled["resolved_rejection_30m"].iloc[0])


def test_candidate_already_beyond_wall_counts_as_pierced() -> None:
    underlying = _underlying()
    labeled = label_candidate_session(_candidate(role="resistance", spot=100.1), underlying)
    assert labeled["pierced_30m"].iloc[0] == 1.0
    assert labeled["accepted_break_30m"].iloc[0] == 1.0
    assert labeled["resolved_rejection_30m"].iloc[0] == 0.0


def test_missing_minute_invalidates_complete_horizon() -> None:
    underlying = _underlying()
    underlying = underlying[underlying["bar_start"].ne(pd.Timestamp("2024-01-02 10:12:00"))]
    labeled = label_candidate_session(_candidate(), underlying)
    assert labeled["path_complete_30m"].iloc[0] == 0
    assert np.isnan(labeled["resolved_rejection_30m"].iloc[0])


def test_half_day_and_regular_day_labels_cannot_cross_underlying_close() -> None:
    half_times = pd.date_range("2024-07-03 12:55:00", "2024-07-03 15:55:00", freq="1min")
    half = pd.DataFrame(
        {"bar_start": half_times, "open": 101.0, "high": 101.5, "low": 99.0, "close": 101.0}
    )
    half_labeled = label_candidate_session(
        _candidate(trade_date="20240703", decision="2024-07-03 12:55:00"),
        half,
    )
    assert half_labeled["path_complete_30m"].iloc[0] == 0
    regular_times = pd.date_range("2024-01-02 14:30:00", "2024-01-02 17:30:00", freq="1min")
    regular = pd.DataFrame(
        {"bar_start": regular_times, "open": 101.0, "high": 101.5, "low": 99.0, "close": 101.0}
    )
    regular_labeled = label_candidate_session(
        _candidate(decision="2024-01-02 14:30:00"),
        regular,
    )
    assert regular_labeled["path_complete_30m"].iloc[0] == 1
    assert regular_labeled["path_complete_60m"].iloc[0] == 1
    assert regular_labeled["path_complete_120m"].iloc[0] == 0
    assert regular_labeled["path_complete_180m"].iloc[0] == 0


def test_candidate_decision_calendar_date_mismatch_fails_closed() -> None:
    candidate = _candidate()
    candidate["trade_date"] = "20240103"
    with pytest.raises(AssertionError, match="timestamp/date mismatch"):
        label_candidate_session(candidate, _underlying())


def test_ticker_day_bootstrap_is_deterministic() -> None:
    test = pd.DataFrame({"trade_date": ["20240102"] * 3 + ["20240103"] * 3})
    y = np.array([0, 1, 0, 1, 0, 1])
    f0 = np.array([0.8, 0.2, 0.7, 0.2, 0.8, 0.3])
    f1 = np.array([0.2, 0.8, 0.3, 0.8, 0.2, 0.7])
    left = paired_day_bootstrap(test, y, f0, f1, seed=17, replicates=100)
    right = paired_day_bootstrap(test, y, f0, f1, seed=17, replicates=100)
    assert left == right
    assert left["bootstrap_valid"] > 0
    assert left["bootstrap_favorable_share"] > 0.5


def _gate_frames(joint_losses: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cell_rows = []
    paired_rows = []
    monthly_rows = []
    index = 0
    for fold in ("2024", "2025"):
        for ticker in ("SPXW", "QQQ", "SPY"):
            for horizon in HORIZONS:
                cell_id = f"{fold}_{ticker}_{horizon}m"
                for arm, auc in (("F0", 0.56), ("F1", 0.58)):
                    cell_rows.append({"cell_id": cell_id, "fold": fold, "ticker": ticker, "horizon": horizon, "arm": arm, "roc_auc": auc})
                loses_both = index < joint_losses
                paired_rows.append(
                    {
                        "cell_id": cell_id,
                        "fold": fold,
                        "ticker": ticker,
                        "horizon": horizon,
                        "valid_pair": True,
                        "auc_delta": 0.02,
                        "average_precision_delta": -0.01 if loses_both else 0.01,
                        "log_loss_delta": 0.01 if loses_both else -0.01,
                    }
                )
                if horizon in (30, 60):
                    for month in range(1, 13):
                        monthly_rows.append(
                            {
                                "fold": fold,
                                "ticker": ticker,
                                "horizon": horizon,
                                "month": f"{fold}{month:02d}",
                                "resolved_episodes": 18,
                                "both_classes": True,
                            }
                        )
                index += 1
    return pd.DataFrame(cell_rows), pd.DataFrame(paired_rows), pd.DataFrame(monthly_rows)


def test_joint_ap_logloss_gate_allows_twelve_not_thirteen_losses() -> None:
    cells, paired, monthly = _gate_frames(12)
    passed = summarize_gate(cells, paired, monthly, provenance_status="PASS", live_parity_status="PASS")
    assert passed["calibration_pass"] is True
    assert passed["physical_mechanism_pass"] is True
    cells, paired, monthly = _gate_frames(13)
    failed = summarize_gate(cells, paired, monthly, provenance_status="PASS", live_parity_status="PASS")
    assert failed["calibration_pass"] is False
    assert failed["physical_mechanism_pass"] is False
