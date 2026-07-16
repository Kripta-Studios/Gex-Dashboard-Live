from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa import capture_yahoo_futures_60m_v1 as capture
from neural.jepa import evaluate_directional_globex_cross_asset_v1 as module


def synthetic_frames() -> dict[str, pd.DataFrame]:
    index = pd.date_range(
        "2025-01-05 13:00", "2025-01-06 15:00", freq="h", tz="America/New_York"
    )
    output = {}
    for symbol_index, symbol in enumerate(capture.SYMBOLS):
        base = 100.0 + symbol_index * 10.0
        trend = np.arange(len(index), dtype=float) * 0.01
        open_ = base + trend
        output[symbol] = pd.DataFrame(
            {
                "open": open_,
                "high": open_ + 0.1,
                "low": open_ - 0.1,
                "close": open_ + 0.02,
                "volume": np.arange(len(index), dtype=float) + 100.0,
            },
            index=index,
        )
    return output


def test_futures_features_are_unchanged_by_postdecision_mutation() -> None:
    frames = synthetic_frames()
    before, reason = module.extract_futures_features(frames, "20250106", "W1")
    assert reason is None and before is not None
    changed = {symbol: frame.copy() for symbol, frame in frames.items()}
    future_timestamp = pd.Timestamp("2025-01-06 14:00", tz="America/New_York")
    changed["ES=F"].loc[future_timestamp, ["open", "high", "low", "close"]] = 9999.0
    after, reason = module.extract_futures_features(changed, "20250106", "W1")
    assert reason is None
    assert before == after


def test_missing_hour_in_one_future_drops_entire_decision() -> None:
    frames = synthetic_frames()
    missing = pd.Timestamp("2025-01-06 09:00", tz="America/New_York")
    frames["ZN=F"] = frames["ZN=F"].drop(index=missing)
    features, reason = module.extract_futures_features(frames, "20250106", "W1")
    assert features is None
    assert reason == "ZN=F:missing_recent_hour"


def test_frozen_feature_names_include_all_seven_futures_and_spreads() -> None:
    features, reason = module.extract_futures_features(
        synthetic_frames(), "20250106", "W2"
    )
    assert reason is None and features is not None
    assert all(
        f"{prefix}_ret_6h" in features for prefix in module.SYMBOL_PREFIX.values()
    )
    assert "spread_es_nq_6h" in features
    assert "spread_cl_zn_6h" in features
    assert len(features) == 103


def test_evaluation_gate_requires_every_month_positive() -> None:
    months = [f"2026{month:02d}" for month in range(1, 8)]
    rows = []
    for ticker in ("QQQ", "SPX", "SPY"):
        for month in months:
            for index in range(13):
                rows.append(
                    {
                        "ticker": ticker,
                        "profile_id": module.GLOBEX_PROFILE,
                        "month": month,
                        "net_bps": 2.0 if index < 8 else -1.0,
                    }
                )
    trades = pd.DataFrame(rows)
    passed = module.evaluation_gate(trades, months)
    assert passed["joint_gate_pass"]
    trades.loc[
        (trades["ticker"].eq("SPY")) & trades["month"].eq("202603"), "net_bps"
    ] = -1.0
    failed = module.evaluation_gate(trades, months)
    assert not failed["joint_gate_pass"]
    assert failed["ticker_metrics"]["SPY"]["positive_months"] == 6
