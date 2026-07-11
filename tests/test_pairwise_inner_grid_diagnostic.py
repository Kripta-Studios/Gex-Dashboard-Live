from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "neural" / "jepa"))

from diagnose_pairwise_inner_grid_v1 import evaluate_inner_configuration
from walkforward_pairwise_opportunity_side import apply_pairwise_policy


def _scored(returns: list[float], exit_minute: int = 680) -> pd.DataFrame:
    n = len(returns)
    return pd.DataFrame({
        "ticker": ["QQQ"] * n,
        "date": [f"202301{i + 2:02d}" for i in range(n)],
        "month": ["202301"] * n,
        "minute": [640] * n,
        "p_trade": [0.8] * n,
        "p_call": [0.8] * n,
        "call_return": returns,
        "put_return": [-0.1] * n,
        "call_d35_opt_exit_minutes": [exit_minute] * n,
        "put_d35_opt_exit_minutes": [exit_minute] * n,
    })


def test_gate_decomposition_records_individual_passes():
    scored = _scored([0.1] * 10 + [-0.02] * 8)
    result = evaluate_inner_configuration(
        scored, ["202301"], {"max_trades_per_day": 2, "cooldown_minutes": 30},
        35, 0.5, 0.0, apply_pairwise_policy,
    )
    assert result["all_months_pf_pass"] is True
    assert result["all_months_wr_pass"] is True
    assert result["all_months_trades_pass"] is True
    assert result["all_months_pnl_pass"] is True
    assert result["all_months_hold_pass"] is True
    assert result["all_gates_pass"] is True


def test_short_hold_fails_only_hold_gate():
    scored = _scored([0.1] * 10 + [-0.02] * 8, exit_minute=669)
    result = evaluate_inner_configuration(
        scored, ["202301"], {"max_trades_per_day": 2, "cooldown_minutes": 30},
        35, 0.5, 0.0, apply_pairwise_policy,
    )
    assert result["gate_pass_count"] == 4
    assert result["failure_signature"] == "hold"


def test_missing_inner_month_fails_frequency_and_economic_gates():
    result = evaluate_inner_configuration(
        _scored([0.1] * 18), ["202301", "202302"],
        {"max_trades_per_day": 2, "cooldown_minutes": 30},
        35, 0.5, 0.0, apply_pairwise_policy,
    )
    assert result["all_months_trades_pass"] is False
    assert result["all_months_pf_pass"] is False
    assert result["all_months_wr_pass"] is False
    assert result["all_months_pnl_pass"] is False
    assert result["all_gates_pass"] is False
