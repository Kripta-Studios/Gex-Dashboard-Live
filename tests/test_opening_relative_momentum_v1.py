from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from neural.jepa import evaluate_opening_relative_momentum_v1 as opening


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


def _markets(day: str) -> dict[str, pd.DataFrame]:
    return {ticker: _frame(ticker, day, 100.0) for ticker in opening.SOURCE_TICKERS}


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


def test_momentum_signal_and_exact_spread_payoff() -> None:
    day = "20230103"
    frames = _markets(day)
    _set(frames["QQQ"], day, "10:34", "close", 102.0)
    _set(frames["QQQ"], day, "10:35", "close", 50.0)
    _set(frames["QQQ"], day, opening.ENTRY_TIME, "open", 100.0)
    _set(frames["QQQ"], day, opening.EXIT_TIME, "open", 101.0)
    _set(frames["SPY"], day, opening.ENTRY_TIME, "open", 100.0)
    _set(frames["SPY"], day, opening.EXIT_TIME, "open", 99.0)

    row = opening.build_trade_row(day, frames)

    assert row["action"] == "LONG_QQQ_SHORT_SPY"
    expected = math.log(101.0 / 100.0) * 10_000.0 - math.log(99.0 / 100.0) * 10_000.0
    assert row["gross_bps"] == pytest.approx(expected)
    assert row["net_bps"] == pytest.approx(expected - 2.0)
    assert row["hold_minutes"] == 180


def test_signal_does_not_depend_on_prior_close_or_overnight() -> None:
    day = "20230103"
    frames = _markets(day)
    _set(frames["QQQ"], day, "09:30", "open", 200.0)
    _set(frames["QQQ"], day, "10:34", "close", 198.0)

    row = opening.build_trade_row(day, frames)

    assert row["qqq_opening_move_bps"] == pytest.approx(math.log(198.0 / 200.0) * 10_000.0)
    assert row["action"] == "SHORT_QQQ_LONG_SPY"
    assert "previous_trade_date" not in row
    assert all("cross_session" not in key for key in row)


def test_first_day_is_eligible_but_half_and_invalid_days_are_not() -> None:
    dates = ["20220103", "20221125", "20230605", "20230606"]
    sessions = {day: _markets(day) for day in dates}

    ledger, excluded = opening.build_development_ledger(sessions)

    assert ledger["trade_date"].tolist() == ["20220103", "20230606"]
    reasons = dict(zip(excluded["trade_date"], excluded["reason"], strict=True))
    assert reasons["20221125"] == "CURRENT_HALF_DAY"
    assert reasons["20230605"] == "KNOWN_INVALID_SIGNAL_WINDOW"


@pytest.mark.parametrize(
    ("development_pass", "profit_factor", "expected"),
    [
        (True, 0.5, "PASS_DEVELOPMENT_GATE_OUTER_NOT_OPENED"),
        (False, 1.000001, "INCREMENTAL_EDGE_ONLY"),
        (False, 1.0, "NO_AGGREGATE_EDGE"),
    ],
)
def test_status_does_not_confuse_incremental_edge_with_full_pass(
    development_pass: bool, profit_factor: float, expected: str
) -> None:
    assert opening.classify_status(development_pass, profit_factor) == expected


def test_cli_does_not_expose_mutable_cutoff() -> None:
    args = opening.parse_args([])
    assert not hasattr(args, "end_date")
    with pytest.raises(SystemExit):
        opening.parse_args(["--end-date", "20251231"])
