from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from neural.jepa import evaluate_cross_session_relative_value_v1 as rv


def _frame(ticker: str, day: str, price: float) -> pd.DataFrame:
    timestamps = pd.date_range(
        pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} 09:30"),
        pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} 16:00"),
        freq="min",
    )
    values = np.full(len(timestamps), price, dtype=np.float64)
    return pd.DataFrame(
        {
            "symbol": ticker,
            "date": day,
            "timestamp": timestamps,
            "open": values,
            "high": values,
            "low": values,
            "close": values,
            "tick_count": 60,
        }
    ).set_index("timestamp", drop=False)


def _markets(day: str, prices: dict[str, float]) -> dict[str, pd.DataFrame]:
    return {ticker: _frame(ticker, day, prices[ticker]) for ticker in rv.SOURCE_TICKERS}


def _set(frame: pd.DataFrame, day: str, clock: str, column: str, value: float) -> None:
    timestamp = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {clock}")
    frame.loc[timestamp, column] = value
    if column in {"open", "close"}:
        frame.loc[timestamp, "high"] = max(
            float(frame.loc[timestamp, "open"]), float(frame.loc[timestamp, "close"])
        )
        frame.loc[timestamp, "low"] = min(
            float(frame.loc[timestamp, "open"]), float(frame.loc[timestamp, "close"])
        )


def test_trade_uses_1034_signal_and_exact_spread_payoff() -> None:
    previous_day = "20230103"
    day = "20230104"
    previous = _markets(previous_day, {"QQQ": 100.0, "SPXW": 100.0, "SPY": 100.0})
    current = _markets(day, {"QQQ": 100.0, "SPXW": 100.0, "SPY": 100.0})
    _set(current["QQQ"], day, "10:34", "close", 102.0)
    _set(current["QQQ"], day, "10:35", "close", 50.0)
    _set(current["QQQ"], day, rv.ENTRY_TIME, "open", 100.0)
    _set(current["QQQ"], day, rv.EXIT_TIME, "open", 99.0)
    _set(current["SPY"], day, rv.ENTRY_TIME, "open", 100.0)
    _set(current["SPY"], day, rv.EXIT_TIME, "open", 101.0)

    row = rv.build_trade_row(day, current, previous_day, previous)

    assert row["action"] == "SHORT_QQQ_LONG_SPY"
    assert row["qqq_position"] == -1
    assert row["spy_position"] == 1
    expected = -math.log(99.0 / 100.0) * 10_000.0 + math.log(101.0 / 100.0) * 10_000.0
    assert row["gross_bps"] == pytest.approx(expected)
    assert row["net_bps"] == pytest.approx(expected - 2.0)
    assert row["hold_minutes"] == 180


def test_previous_half_day_uses_1300_close() -> None:
    previous_day = "20221125"
    day = "20221128"
    previous = _markets(previous_day, {"QQQ": 100.0, "SPXW": 100.0, "SPY": 100.0})
    current = _markets(day, {"QQQ": 100.0, "SPXW": 100.0, "SPY": 100.0})
    for ticker in rv.SOURCE_TICKERS:
        _set(previous[ticker], previous_day, "13:00", "close", 80.0)
        _set(previous[ticker], previous_day, "16:00", "close", 200.0)
    _set(current["QQQ"], day, "10:34", "close", 88.0)
    _set(current["SPXW"], day, "10:34", "close", 80.0)
    _set(current["SPY"], day, "10:34", "close", 80.0)

    row = rv.build_trade_row(day, current, previous_day, previous)

    assert row["qqq_cross_session_bps"] == pytest.approx(math.log(88.0 / 80.0) * 10_000.0)
    assert row["relative_shock_bps"] > 0.0


def test_current_half_day_and_invalid_day_are_excluded() -> None:
    dates = ["20221123", "20221125", "20230605", "20230606"]
    sessions = {
        day: _markets(day, {"QQQ": 100.0, "SPXW": 100.0, "SPY": 100.0}) for day in dates
    }

    ledger, excluded = rv.build_development_ledger(sessions)

    reasons = dict(zip(excluded["trade_date"], excluded["reason"], strict=True))
    assert reasons["20221123"] == "NO_PRIOR_SESSION_IN_SCOPE"
    assert reasons["20221125"] == "CURRENT_HALF_DAY"
    assert reasons["20230605"] == "KNOWN_INVALID_SIGNAL_WINDOW"
    assert ledger["trade_date"].tolist() == ["20230606"]


def test_month_gate_is_strict_and_includes_zero_months() -> None:
    rows = []
    for index in range(13):
        rows.append(
            {
                "trade_date": f"202201{index + 3:02d}",
                "month": "202201",
                "trade_executed": True,
                "net_bps": 1.0 if index < 5 else -1.0,
            }
        )
    monthly = rv.summarize_monthly(pd.DataFrame(rows))
    january = monthly.loc[monthly["month"].eq("202201")].iloc[0]
    february = monthly.loc[monthly["month"].eq("202202")].iloc[0]

    assert bool(january["frequency_pass"])
    assert not bool(january["win_rate_pass"])
    assert not bool(january["pnl_pass"])
    assert int(february["trades"]) == 0
    assert not bool(february["month_pass"])


def test_validate_bar_frame_rejects_future_or_incomplete_grid() -> None:
    day = "20230103"
    frame = _frame("QQQ", day, 100.0).reset_index(drop=True)
    validated = rv.validate_bar_frame(frame, "QQQ", day)
    assert len(validated) == 391

    incomplete = frame.iloc[:-1].copy()
    with pytest.raises(AssertionError, match="grid is not exact"):
        rv.validate_bar_frame(incomplete, "QQQ", day)


def test_known_spy_envelope_exception_is_exact_and_not_expandable() -> None:
    day = "20230605"
    frame = _frame("SPY", day, 100.0).reset_index(drop=True)
    for clock in ("09:54", "09:55", "09:56"):
        row = frame["timestamp"].eq(pd.Timestamp(f"2023-06-05 {clock}"))
        frame.loc[row, ["open", "high", "low", "close"]] = [100.0, 99.0, 101.0, 100.0]
    validated = rv.validate_bar_frame(frame, "SPY", day)
    assert len(validated) == 391

    extra = frame.copy()
    row = extra["timestamp"].eq(pd.Timestamp("2023-06-05 09:57"))
    extra.loc[row, ["open", "high", "low", "close"]] = [100.0, 99.0, 101.0, 100.0]
    with pytest.raises(AssertionError, match="09:57"):
        rv.validate_bar_frame(extra, "SPY", day)
