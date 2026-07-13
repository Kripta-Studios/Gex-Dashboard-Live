import pandas as pd

from neural.jepa.evaluate_existing_data_executable_utility_v1 import (
    _gate_pass,
    economic_metrics,
    month_add,
    runner_protocol_sha256,
)


def test_month_add_across_year_boundary() -> None:
    assert month_add("202401", -1) == "202312"
    assert month_add("202412", 1) == "202501"


def test_economic_gate_is_strict_on_pnl_and_frequency() -> None:
    passing = {
        "profit_factor": 1.3, "win_rate": 0.5, "trades": 18,
        "pnl": 0.01, "minimum_hold": 30.0,
    }
    assert _gate_pass(passing)
    assert not _gate_pass({**passing, "trades": 17})
    assert not _gate_pass({**passing, "pnl": 0.0})


def test_metrics_use_chronological_drawdown_and_side_balance() -> None:
    trades = pd.DataFrame({
        "trade_date": ["20230103", "20230103", "20230104"],
        "minute": [635, 700, 640], "ticker": ["QQQ"] * 3,
        "realized_return": [1.0, -0.5, 0.25], "exit_minutes": [30, 60, 45],
        "action": ["CALL", "PUT", "CALL"],
    })
    metric = economic_metrics(trades)
    assert metric["trades"] == 3
    assert metric["profit_factor"] == 2.5
    assert metric["max_drawdown"] == 0.5
    assert metric["call_rate"] == 2 / 3


def test_runner_protocol_hash_is_stable_shape() -> None:
    assert len(runner_protocol_sha256()) == 64
