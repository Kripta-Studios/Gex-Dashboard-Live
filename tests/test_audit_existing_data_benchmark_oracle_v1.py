from __future__ import annotations

import pandas as pd

from neural.jepa.audit_existing_data_benchmark_oracle_v1 import (
    oracle_schedule_day,
    overlap_violations,
    trade_metrics,
)


def _day() -> pd.DataFrame:
    return pd.DataFrame({
        "ticker": ["QQQ"] * 4,
        "trade_date": ["20230103"] * 4,
        "month": ["202301"] * 4,
        "minute": [630, 660, 690, 720],
        "call_return": [1.0, 4.0, 2.0, -1.0],
        "put_return": [-1.0, 1.0, 3.0, 0.5],
        "call_exit_minutes": [60, 30, 30, 30],
        "put_exit_minutes": [30, 30, 30, 30],
    })


def test_oracle_scheduler_optimizes_side_and_non_overlap() -> None:
    chosen = oracle_schedule_day(
        _day(), allowed_actions=("CALL", "PUT"), max_trades=2, cooldown_minutes=30
    )
    assert chosen[["minute", "action"]].to_dict("records") == [
        {"minute": 660, "action": "CALL"},
        {"minute": 690, "action": "PUT"},
    ]
    assert chosen["realized_return"].sum() == 7.0
    assert overlap_violations(chosen) == []


def test_oracle_scheduler_equal_exit_and_entry_is_allowed() -> None:
    day = _day().iloc[[0, 1]].reset_index(drop=True)
    day.loc[0, "put_return"] = 0.5
    chosen = oracle_schedule_day(
        day,
        allowed_actions=("CALL", "PUT"), max_trades=2, cooldown_minutes=30,
    )
    assert chosen["minute"].tolist() == [630, 660]
    assert chosen["action"].tolist() == ["PUT", "CALL"]


def test_oracle_scheduler_zero_return_does_not_inflate_frequency() -> None:
    day = _day().iloc[[3]].copy()
    day["call_return"] = 0.0
    day["put_return"] = 0.0
    chosen = oracle_schedule_day(day, allowed_actions=("CALL", "PUT"), max_trades=2, cooldown_minutes=0)
    assert chosen.empty


def test_trade_metrics_reports_ask_to_bid_economics() -> None:
    frame = pd.DataFrame({
        "trade_date": ["20230103", "20230104", "20230105"],
        "minute": [630, 630, 630],
        "action": ["CALL", "PUT", "PUT"],
        "realized_return": [1.0, -0.5, 0.25],
        "exit_minutes": [30, 60, 180],
    })
    result = trade_metrics(frame, denominator=10)
    assert result["trades"] == 3
    assert result["profit_factor"] == 2.5
    assert result["pnl_return"] == 0.75
    assert result["pnl_dollars"] == 3750.0
    assert result["minimum_hold_minutes"] == 30.0
    assert result["maximum_hold_minutes"] == 180.0
    assert result["abstention_rate"] == 0.7
