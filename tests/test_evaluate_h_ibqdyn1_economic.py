from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import neural.jepa.evaluate_h_ibqdyn1_economic as mod


def test_build_summary_requires_exact_executable_quote_contract(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    args = {
        "start_minute": 630,
        "end_minute": 870,
        "near_level_only": True,
        "near_level_bps": 20.0,
        "horizon_minutes": 180,
        "option_tp_pct": 10.0,
        "option_sl_pct": 0.6,
        "option_price_mode": "executable_quote",
        "option_exit_mode": "trailing",
        "option_min_hold_minutes": 30,
        "option_trail_activation_pct": 0.5,
        "option_trail_drawdown_pct": 0.25,
        "require_open_interest": True,
    }
    path.write_text(json.dumps({"args": args}), encoding="utf-8")
    mod.verify_build_summary(path)
    args["option_min_hold_minutes"] = 0
    path.write_text(json.dumps({"args": args}), encoding="utf-8")
    with pytest.raises(AssertionError, match="build contract"):
        mod.verify_build_summary(path)


def test_physical_mapping_is_role_symmetric() -> None:
    scored = pd.DataFrame(
        {
            "ticker": ["SPY"] * 4,
            "action": ["CALL", "PUT", "CALL", "PUT"],
            "call_d35_opt_exit_ret": [0.1] * 4,
            "put_d35_opt_exit_ret": [-0.2] * 4,
            "call_d35_opt_exit_minutes": [30] * 4,
            "put_d35_opt_exit_minutes": [60] * 4,
        }
    )
    out = mod.attach_selected_payoff(scored)
    assert out["realized_return"].tolist() == [0.1, -0.2, 0.1, -0.2]
    assert out["exit_minutes"].tolist() == [30.0, 60.0, 30.0, 60.0]


def test_causal_replay_rejects_overlap_and_enforces_daily_caps() -> None:
    start = pd.Timestamp("2024-01-02 10:35:00")
    rows = []
    for index, minutes in enumerate((0, 30, 60, 90, 120)):
        rows.append(
            {
                "ticker": "QQQ",
                "trade_date": "20240102",
                "decision_dt": start + pd.Timedelta(minutes=minutes),
                "exit_minutes": 60,
                "realized_return": 0.1,
                "event_id": str(index),
            }
        )
    trades = mod.causal_replay(pd.DataFrame(rows))
    assert trades["event_id"].tolist() == ["0", "2"]
    assert len(trades) == mod.CAPS["QQQ"]


def test_monthly_gate_requires_every_month_positive_and_18_trades() -> None:
    rows = []
    for ticker in mod.BUCKETS:
        for year in (2024, 2025):
            for month in range(1, 13):
                day = f"{year}{month:02d}02"
                for index in range(18):
                    rows.append(
                        {
                            "ticker": ticker,
                            "trade_date": day,
                            "realized_return": 0.10 if index < 12 else -0.05,
                            "exit_minutes": 30,
                        }
                    )
    trades = pd.DataFrame(rows)
    monthly, summary = mod.summarize(trades)
    assert len(monthly) == 72
    assert summary["all_tickers_passed"]
    reduced = trades.drop(trades[(trades.ticker == "SPY") & (trades.trade_date == "20240102")].index[:1])
    _, failed = mod.summarize(reduced)
    assert not failed["all_tickers_passed"]


def test_selected_payoff_rejects_sub_30_minute_hold() -> None:
    frame = pd.DataFrame(
        {
            "ticker": ["SPXW"],
            "action": ["CALL"],
            "call_d25_opt_exit_ret": [0.1],
            "put_d25_opt_exit_ret": [-0.1],
            "call_d25_opt_exit_minutes": [29],
            "put_d25_opt_exit_minutes": [30],
        }
    )
    with pytest.raises(AssertionError, match="hold contract"):
        mod.attach_selected_payoff(frame)
