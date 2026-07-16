from __future__ import annotations

import math

import numpy as np
import pandas as pd

from neural.jepa import evaluate_directional_breadth_transmission_v1 as panel
from neural.jepa import evaluate_directional_intraday_pooled_v1 as module
from neural.jepa import evaluate_directional_semantic_jepa_v1 as base


def make_frame(ticker: str, day: str, slope: float = 1.0) -> pd.DataFrame:
    timestamp = pd.date_range(pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=30), periods=391, freq="min")
    price = 100.0 + np.arange(len(timestamp), dtype=float) * slope / 390.0
    frame = pd.DataFrame(
        {
            "symbol": ticker,
            "date": pd.Timestamp(day).date().isoformat(),
            "timestamp": timestamp,
            "open": price,
            "high": price + 0.05,
            "low": price - 0.05,
            "close": price + 0.01,
            "tick_count": 50.0,
        }
    )
    return base.validate_bar_frame(frame, ticker, pd.Timestamp(day).strftime("%Y%m%d"))


def make_panel(day: str) -> dict[str, pd.DataFrame]:
    return {
        ticker: make_frame(ticker, day, 1.0 + index * 0.1)
        for index, ticker in enumerate(panel.ALL_TICKERS)
    }


def test_windows_are_non_overlapping_and_july_frequency_is_possible() -> None:
    windows = list(module.WINDOWS.values())
    assert len(windows) == 6
    assert all(left["exit_time"] < right["entry_time"] for left, right in zip(windows, windows[1:]))
    assert min(window["hold_minutes"] for window in windows) >= 30
    assert 10 * len(windows) > 12


def test_h3_features_are_unchanged_by_future_mutation() -> None:
    previous = make_panel("2025-06-09")
    current = make_panel("2025-06-10")
    baseline, target_features, breadth_features = module.build_row(
        "20250610", current, "20250609", previous, "QQQ", "H3"
    )
    mutated = {ticker: frame.copy() for ticker, frame in current.items()}
    for ticker, frame in mutated.items():
        mask = frame["timestamp"].dt.strftime("%H:%M") > "12:02"
        frame.loc[mask, ["open", "high", "low", "close"]] *= 1.05
        mutated[ticker] = frame
    mutated["QQQ"].loc[pd.Timestamp("2025-06-10 13:03"), "open"] *= 1.01
    changed, observed_target, observed_breadth = module.build_row(
        "20250610", mutated, "20250609", previous, "QQQ", "H3"
    )
    assert target_features == observed_target
    assert breadth_features == observed_breadth
    for feature in target_features + breadth_features:
        assert baseline[feature] == changed[feature]
    assert baseline["future_return_bps"] != changed["future_return_bps"]


def test_exact_entry_and_exit_open_define_label() -> None:
    previous = make_panel("2025-06-09")
    current = make_panel("2025-06-10")
    qqq = current["QQQ"].copy()
    qqq.loc[pd.Timestamp("2025-06-10 14:05"), "open"] = 100.0
    qqq.loc[pd.Timestamp("2025-06-10 15:05"), "open"] = 101.0
    current["QQQ"] = qqq
    row, _, _ = module.build_row("20250610", current, "20250609", previous, "QQQ", "H5")
    assert row["entry_spot"] == 100.0
    assert row["exit_spot"] == 101.0
    assert math.isclose(row["future_return_bps"], math.log(1.01) * 10000.0)


def test_ticker_one_hot_is_in_target_contract() -> None:
    row, target_features, _ = module.build_row(
        "20250610", make_panel("2025-06-10"), "20250609", make_panel("2025-06-09"), "SPXW", "H1"
    )
    assert set(module.TICKER_FEATURES).issubset(target_features)
    assert row["ticker_spx"] == 1.0
    assert row["ticker_qqq"] == 0.0
    assert row["ticker_spy"] == 0.0


def test_gate_requires_every_month_for_every_ticker() -> None:
    months = [f"2026{month:02d}" for month in range(1, 8)]
    rows = []
    for ticker in ("QQQ", "SPX", "SPY"):
        for month in months:
            for _ in range(13):
                rows.append({"ticker": ticker, "profile_id": module.BREADTH_PROFILE, "month": month, "net_bps": 2.0})
    result = module.evaluate_gate(pd.DataFrame(rows), months)
    assert result["joint_gate_pass"] is True
