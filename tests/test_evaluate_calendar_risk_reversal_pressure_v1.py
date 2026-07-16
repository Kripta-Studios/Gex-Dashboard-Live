from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa import evaluate_calendar_risk_reversal_pressure_v1 as subject


def test_sign_and_exact_fixed_hold_payoff() -> None:
    row = subject.make_trade_row(
        ticker="QQQ",
        trade_date="20230103",
        pressure=0.01,
        entry_open=100.0,
        exit_open=101.0,
    )
    gross = math.log(101.0 / 100.0) * 10_000.0
    assert row["action"] == "LONG"
    assert row["side"] == 1
    assert row["gross_bps"] == pytest.approx(gross)
    assert row["net_bps"] == pytest.approx(gross - 1.0)
    assert row["inverse_sign_control_net_bps"] == pytest.approx(-gross - 1.0)
    assert row["hold_minutes"] == 180

    short = subject.make_trade_row(
        ticker="SPY",
        trade_date="20230103",
        pressure=-0.01,
        entry_open=100.0,
        exit_open=99.0,
    )
    assert short["side"] == -1
    assert short["net_bps"] == pytest.approx(-math.log(99.0 / 100.0) * 10_000.0 - 1.0)


def test_zero_pressure_does_not_trade_or_pay_primary_cost() -> None:
    row = subject.make_trade_row(
        ticker="SPXW",
        trade_date="20230103",
        pressure=0.0,
        entry_open=4000.0,
        exit_open=4010.0,
    )
    assert row["action"] == "NO_TRADE_ZERO_PRESSURE"
    assert row["trade_executed"] is False
    assert row["cost_bps"] == 0.0
    assert row["net_bps"] == 0.0


def _ledger(january_trades: int = 19) -> pd.DataFrame:
    rows: list[dict] = []
    for ticker in subject.TICKERS:
        for month_number in range(1, 13):
            count = january_trades if month_number == 1 else 19
            for index in range(count):
                rows.append(
                    {
                        "ticker": ticker,
                        "month": f"2023{month_number:02d}",
                        "trade_executed": True,
                        "net_bps": 2.0 if index % 2 == 0 else -1.0,
                    }
                )
    return pd.DataFrame(rows)


def test_monthly_gate_is_strict_and_complete() -> None:
    passing = subject.summarize_monthly(_ledger())
    assert len(passing) == 36
    assert passing["month_pass"].all()

    failing = subject.summarize_monthly(_ledger(january_trades=12))
    january = failing.loc[failing["month"].eq("202301")]
    assert january["trades"].eq(12).all()
    assert not january["frequency_pass"].any()


@pytest.mark.parametrize(
    ("development_pass", "profit_factors", "expected"),
    [
        (True, [0.8, 0.8, 0.8], "PASS_DEVELOPMENT_GATE_OUTER_NOT_OPENED"),
        (False, [1.1, 1.01, 1.2], "INCREMENTAL_EDGE_ALL_TICKERS_ONLY"),
        (False, [1.1, 0.9, 0.8], "PARTIAL_INCREMENTAL_EDGE_ONLY"),
        (False, [1.0, 0.9, 0.8], "NO_AGGREGATE_EDGE"),
    ],
)
def test_status_separates_incremental_pf_from_full_gate(
    development_pass: bool, profit_factors: list[float], expected: str
) -> None:
    summary = pd.DataFrame({"profit_factor": profit_factors})
    assert subject.classify_status(development_pass, summary) == expected


def test_committed_data_gate_selects_only_valid_normal_2023() -> None:
    features, inventory, manifest = subject.validate_data_gate()
    assert manifest["status"] == "PASS_DATA_GATE"
    assert len(features) == 741
    assert len(inventory) == 741
    assert features["trade_date"].str.startswith("2023").all()
    assert inventory["trade_date"].str.startswith("2023").all()
    assert not features["calendar_half_day"].any()
    assert features.groupby(["ticker", "month"], observed=True).size().min() > 12


def test_cli_does_not_expose_mutable_policy_or_scope() -> None:
    args = subject.parse_args([])
    for name in ("start_date", "end_date", "entry_time", "exit_time", "cost_bps"):
        assert not hasattr(args, name)
    with pytest.raises(SystemExit):
        subject.parse_args(["--end-date", "20251231"])


def test_direct_cli_imports() -> None:
    script = Path(subject.__file__).resolve()
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=script.parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--frozen-manifest" in completed.stdout
