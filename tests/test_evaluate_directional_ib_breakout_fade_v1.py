from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa import evaluate_directional_ib_breakout_fade_v1 as subject


def _frame(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    timestamps = pd.date_range("2025-01-02 10:31", periods=len(rows), freq="min")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=timestamps)


def test_same_bar_stop_has_conservative_priority() -> None:
    frame = _frame([(100.0, 101.0, 99.0, 100.0)] * 31)
    result = subject.simulate_trade(
        frame,
        frame.index[0],
        frame.index[-1],
        side=1,
        ib_width=2.0,
        mode="BREAKOUT",
    )
    assert result["exit_reason"] == "STOP"
    assert result["exit_spot"] == 100.0 - subject.BREAKOUT_STOP_R * 2.0


def test_target_cannot_fill_before_thirty_minutes() -> None:
    rows = [(100.0, 100.0, 100.0, 100.0)] * 31
    rows[1] = (100.0, 102.0, 100.0, 101.0)
    rows[30] = (100.0, 102.0, 100.0, 101.0)
    frame = _frame(rows)
    result = subject.simulate_trade(
        frame,
        frame.index[0],
        frame.index[-1],
        side=1,
        ib_width=2.0,
        mode="BREAKOUT",
    )
    assert result["exit_reason"] == "TARGET"
    assert result["hold_minutes"] == 30


def test_feature_contract_contains_no_outcome_names() -> None:
    source = subject.PREDECLARATION.read_text(encoding="utf-8")
    assert "2026 no puede abrirse" in source
    forbidden = ("future", "outcome", "pnl", "exit", "target", "label")
    synthetic_names = [
        "trigger_up",
        "window_w2",
        "qqq_aligned_ret_5m",
        "panel_break_confirm_fraction",
    ]
    assert not [name for name in synthetic_names if any(token in name for token in forbidden)]


def test_profit_factor_gate_is_strict() -> None:
    rows = []
    months = [f"2025{month:02d}" for month in range(1, 13)]
    for ticker in ("QQQ", "SPX", "SPY"):
        for month in months:
            for trade in range(13):
                rows.append(
                    {
                        "ticker": ticker,
                        "month": month,
                        "net_bps": 2.0 if trade < 7 else -1.0,
                    }
                )
    trades = pd.DataFrame(rows)
    gate = subject.evaluate_gate(trades, months, development=True)
    assert gate["joint_gate_pass"]
    assert np.isclose(gate["ticker_metrics"]["SPX"]["win_rate"], 7.0 / 13.0)
