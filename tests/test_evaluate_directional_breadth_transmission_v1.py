from __future__ import annotations

import math

import numpy as np
import pandas as pd

from neural.jepa import evaluate_directional_breadth_transmission_v1 as module
from neural.jepa import evaluate_directional_semantic_jepa_v1 as base


def make_frame(ticker: str, day: str, slope: float = 1.0) -> pd.DataFrame:
    timestamp = pd.date_range(
        pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=30), periods=391, freq="min"
    )
    base_price = 100.0 + np.arange(len(timestamp), dtype=float) * slope / 390.0
    frame = pd.DataFrame(
        {
            "symbol": ticker,
            "date": pd.Timestamp(day).date().isoformat(),
            "timestamp": timestamp,
            "open": base_price,
            "high": base_price + 0.05,
            "low": base_price - 0.05,
            "close": base_price + 0.01,
            "tick_count": 50.0,
        }
    )
    return base.validate_bar_frame(frame, ticker, pd.Timestamp(day).strftime("%Y%m%d"))


def make_panel(day: str) -> dict[str, pd.DataFrame]:
    return {
        ticker: make_frame(ticker, day, 1.0 + index * 0.1)
        for index, ticker in enumerate(module.ALL_TICKERS)
    }


def test_frozen_component_panel_uses_all_local_sources() -> None:
    assert module.COMPONENTS == (
        "AAPL",
        "AMZN",
        "GOOGL",
        "META",
        "MSFT",
        "NFLX",
        "NVDA",
        "TSLA",
        "IWM",
        "TLT",
        "GLD",
        "SLV",
    )
    assert "SLV" in module.ALL_TICKERS
    assert "VIX" not in module.ALL_TICKERS
    assert len(module.SOURCE_MISSING_DAYS) == 28
    assert module.PANEL_INVALID_DAYS == frozenset({"20230605", "20240603"})


def test_two_windows_are_non_overlapping_and_make_july_frequency_possible() -> None:
    first = module.WINDOWS["W1"]
    second = module.WINDOWS["W2"]
    assert first["exit_time"] < second["entry_time"]
    assert first["hold_minutes"] == 180
    assert second["hold_minutes"] == 177
    assert 10 * len(module.WINDOWS) > 12


def test_w1_features_do_not_change_when_future_is_mutated() -> None:
    previous = make_panel("2025-06-09")
    current = make_panel("2025-06-10")
    baseline, target_features, breadth_features = module.build_row(
        "20250610", current, "20250609", previous, "QQQ", "W1"
    )
    mutated = {ticker: frame.copy() for ticker, frame in current.items()}
    for ticker, frame in mutated.items():
        future = frame["timestamp"].dt.strftime("%H:%M") > "10:00"
        frame.loc[future, ["open", "high", "low", "close"]] *= 1.05
        mutated[ticker] = frame
    mutated["QQQ"].loc[pd.Timestamp("2025-06-10 13:01"), "open"] *= 1.02
    changed, observed_target, observed_breadth = module.build_row(
        "20250610", mutated, "20250609", previous, "QQQ", "W1"
    )
    assert target_features == observed_target
    assert breadth_features == observed_breadth
    for feature in target_features + breadth_features:
        assert baseline[feature] == changed[feature]
    assert baseline["future_return_bps"] != changed["future_return_bps"]


def test_labels_use_exact_next_open_and_declared_exit() -> None:
    previous = make_panel("2025-06-09")
    current = make_panel("2025-06-10")
    qqq = current["QQQ"].copy()
    qqq.loc[pd.Timestamp("2025-06-10 13:02"), "open"] = 100.0
    qqq.loc[pd.Timestamp("2025-06-10 15:59"), "open"] = 101.0
    current["QQQ"] = qqq
    row, _, _ = module.build_row(
        "20250610", current, "20250609", previous, "QQQ", "W2"
    )
    assert row["entry_spot"] == 100.0
    assert row["exit_spot"] == 101.0
    assert row["hold_minutes"] == 177
    assert math.isclose(row["future_return_bps"], math.log(1.01) * 10000.0)


def test_magnitude_weights_are_clipped_and_median_normalized() -> None:
    weights = module.magnitude_weights([-1.0, 10.0, 1000.0])
    assert np.allclose(weights, np.array([0.5, 1.0, 15.0]))


def test_gate_requires_all_seven_months_for_every_ticker() -> None:
    rows = []
    months = [f"2026{month:02d}" for month in range(1, 8)]
    for ticker in ("QQQ", "SPX", "SPY"):
        for month in months:
            for _ in range(13):
                rows.append(
                    {
                        "ticker": ticker,
                        "profile_id": module.BREADTH_PROFILE,
                        "month": month,
                        "net_bps": 2.0,
                    }
                )
    result = module.evaluate_gate(pd.DataFrame(rows), months)
    assert result["joint_gate_pass"] is True
    assert all(item["positive_months"] == 7 for item in result["ticker_metrics"].values())
