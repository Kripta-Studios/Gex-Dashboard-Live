from __future__ import annotations

import math

import numpy as np
import pandas as pd
import torch

from neural.jepa import evaluate_directional_semantic_jepa_v1 as module


def make_frame(ticker: str, day: str, offset: float = 0.0) -> pd.DataFrame:
    timestamp = pd.date_range(pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=30), periods=391, freq="min")
    base = 100.0 + offset + np.linspace(0.0, 1.5, len(timestamp))
    frame = pd.DataFrame(
        {
            "symbol": ticker,
            "date": pd.Timestamp(day).date().isoformat(),
            "timestamp": timestamp,
            "open": base,
            "high": base + 0.05,
            "low": base - 0.05,
            "close": base + 0.01,
            "tick_count": 60,
        }
    )
    return module.validate_bar_frame(frame, ticker, pd.Timestamp(day).strftime("%Y%m%d"))


def make_cross_market(day: str) -> dict[str, pd.DataFrame]:
    return {ticker: make_frame(ticker, day, index * 20.0) for index, ticker in enumerate(module.SOURCE_TICKERS)}


def test_validate_bar_frame_and_raw_array_contract() -> None:
    frames = make_cross_market("2025-06-10")
    array = module.raw_market_array(frames)
    assert array.shape == (391, module.RAW_CHANNELS)
    assert np.isfinite(array).all()
    assert array[0, 0] == 0.0


def test_technical_features_do_not_change_when_future_is_mutated() -> None:
    previous = make_cross_market("2025-06-09")
    current = make_cross_market("2025-06-10")
    baseline, features = module.build_technical_row(
        "20250610", current, "20250609", previous, "QQQ"
    )
    mutated = {ticker: frame.copy() for ticker, frame in current.items()}
    future = mutated["QQQ"]["timestamp"].dt.strftime("%H:%M") > module.DECISION_TIME
    mutated["QQQ"].loc[future, ["open", "high", "low", "close"]] *= 1.05
    changed, observed_features = module.build_technical_row(
        "20250610", mutated, "20250609", previous, "QQQ"
    )
    assert observed_features == features
    assert [baseline[name] for name in features] == [changed[name] for name in features]
    assert baseline["future_return_bps"] != changed["future_return_bps"]


def test_label_uses_next_minute_open_and_exact_180_minute_exit() -> None:
    previous = make_cross_market("2025-06-09")
    current = make_cross_market("2025-06-10")
    qqq = current["QQQ"].copy()
    entry = pd.Timestamp("2025-06-10 10:36")
    exit_ = pd.Timestamp("2025-06-10 13:36")
    qqq.loc[entry, ["open", "high", "low", "close"]] = [100.0, 100.1, 99.9, 100.0]
    qqq.loc[exit_, ["open", "high", "low", "close"]] = [101.0, 101.1, 100.9, 101.0]
    current["QQQ"] = qqq
    row, _ = module.build_technical_row("20250610", current, "20250609", previous, "QQQ")
    assert row["entry_spot"] == 100.0
    assert row["exit_spot"] == 101.0
    assert row["hold_minutes"] == 180
    assert math.isclose(row["future_return_bps"], math.log(1.01) * 10000.0)


def test_market_window_dataset_has_only_context_and_future_teacher_windows() -> None:
    array = module.raw_market_array(make_cross_market("2025-06-10"))
    normalizer = module.fit_normalizer([array])
    dataset = module.MarketWindowDataset([array], [(0, 65)], normalizer)
    context, targets = dataset[0]
    assert context.shape == (module.CONTEXT_LENGTH, module.MODEL_INPUT_CHANNELS)
    assert targets.shape == (len(module.HORIZONS), module.CONTEXT_LENGTH, module.MODEL_INPUT_CHANNELS)
    assert torch.count_nonzero(context[:, module.RAW_CHANNELS :]) == 0


def test_corruption_marks_a_temporal_block_and_preserves_shape() -> None:
    torch.manual_seed(7)
    context = torch.ones((4, module.CONTEXT_LENGTH, module.MODEL_INPUT_CHANNELS))
    context[:, :, module.RAW_CHANNELS :] = 0.0
    corrupted = module.corrupt_student_context(context)
    assert corrupted.shape == context.shape
    assert (corrupted[:, :, module.RAW_CHANNELS] == 1.0).any(dim=1).all()
    assert (corrupted[:, :, : module.RAW_CHANNELS] == 0.0).any()


def test_predictions_to_trades_charges_cost_and_uses_prediction_sign() -> None:
    test = pd.DataFrame(
        {
            "ticker": ["QQQ", "QQQ"],
            "source_ticker": ["QQQ", "QQQ"],
            "trade_date": ["20250102", "20250103"],
            "month": ["202501", "202501"],
            "decision_time": ["10:35", "10:35"],
            "entry_time": ["10:36", "10:36"],
            "exit_time": ["13:36", "13:36"],
            "hold_minutes": [180, 180],
            "entry_spot": [100.0, 100.0],
            "exit_spot": [101.0, 99.0],
            "future_return_bps": [10.0, -12.0],
        }
    )
    trades = module.predictions_to_trades(test, np.array([1.0, -1.0]), module.TECH_PROFILE)
    assert trades["side"].tolist() == ["LONG", "SHORT"]
    assert trades["net_bps"].tolist() == [9.0, 11.0]


def test_profile_selection_is_deterministic_and_uses_only_selectable_profiles() -> None:
    rows = []
    for ticker in ("QQQ", "SPX", "SPY"):
        for month_number in range(1, 13):
            month = f"2025{month_number:02d}"
            for profile in module.SELECTABLE_PROFILES:
                for trade in range(13):
                    positive = profile == module.SEMANTIC_PROFILE or month_number <= 6
                    rows.append(
                        {
                            "ticker": ticker,
                            "profile_id": profile,
                            "month": month,
                            "net_bps": 2.0 if positive else -3.0,
                        }
                    )
    selections, ranking = module.select_profiles(pd.DataFrame(rows))
    assert selections == {ticker: module.SEMANTIC_PROFILE for ticker in ("QQQ", "SPX", "SPY")}
    assert ranking.groupby("ticker")["selected"].sum().eq(1).all()


def test_complete_month_gate_requires_every_ticker_month() -> None:
    rows = []
    months = [f"2026{month:02d}" for month in range(1, 7)]
    for ticker in ("QQQ", "SPX", "SPY"):
        for month in months:
            for trade in range(13):
                rows.append(
                    {
                        "ticker": ticker,
                        "profile_id": module.SEMANTIC_PROFILE,
                        "month": month,
                        "net_bps": 2.0,
                    }
                )
    result = module.evaluate_complete_month_gate(pd.DataFrame(rows), months)
    assert result["joint_gate_pass"] is True
    assert all(metrics["min_month_trades"] == 13 for metrics in result["ticker_metrics"].values())
