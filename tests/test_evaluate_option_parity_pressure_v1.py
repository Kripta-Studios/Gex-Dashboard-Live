from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa import evaluate_option_parity_pressure_v1 as parity


def test_sign_action_and_fixed_spot_proxy_payoff() -> None:
    long_row = parity.make_trade_row(
        ticker="QQQ",
        trade_date="20230103",
        parity_pressure=0.25,
        entry_open=100.0,
        exit_open=101.0,
    )
    expected_return = math.log(101.0 / 100.0) * 10_000.0
    assert long_row["side"] == 1
    assert long_row["action"] == "LONG"
    assert long_row["gross_bps"] == pytest.approx(expected_return)
    assert long_row["net_bps"] == pytest.approx(expected_return - 1.0)
    assert long_row["inverse_sign_control_net_bps"] == pytest.approx(-expected_return - 1.0)
    assert long_row["hold_minutes"] == 180

    short_row = parity.make_trade_row(
        ticker="SPY",
        trade_date="20230103",
        parity_pressure=-0.5,
        entry_open=100.0,
        exit_open=99.0,
    )
    expected_short = -math.log(99.0 / 100.0) * 10_000.0
    assert short_row["side"] == -1
    assert short_row["net_bps"] == pytest.approx(expected_short - 1.0)


def test_zero_pressure_is_no_trade_without_primary_cost() -> None:
    row = parity.make_trade_row(
        ticker="SPXW",
        trade_date="20230103",
        parity_pressure=0.0,
        entry_open=4000.0,
        exit_open=4020.0,
    )
    assert row["side"] == 0
    assert row["action"] == "NO_TRADE_ZERO_PRESSURE"
    assert row["trade_executed"] is False
    assert row["gross_bps"] == 0.0
    assert row["cost_bps"] == 0.0
    assert row["net_bps"] == 0.0
    assert row["always_long_control_net_bps"] != 0.0


def _monthly_ledger(trades_in_january: int = 19) -> pd.DataFrame:
    rows: list[dict] = []
    for ticker in parity.TICKERS:
        for month_number in range(1, 13):
            month = f"2023{month_number:02d}"
            count = trades_in_january if month_number == 1 else 19
            for index in range(count):
                rows.append(
                    {
                        "ticker": ticker,
                        "month": month,
                        "trade_executed": True,
                        "net_bps": 2.0 if index % 2 == 0 else -1.0,
                    }
                )
    return pd.DataFrame(rows)


def test_monthly_gate_is_strict_and_has_all_36_cells() -> None:
    passing = parity.summarize_monthly(_monthly_ledger())
    assert len(passing) == 36
    assert passing["month_pass"].all()

    strict_frequency_failure = parity.summarize_monthly(_monthly_ledger(trades_in_january=12))
    january = strict_frequency_failure.loc[strict_frequency_failure["month"].eq("202301")]
    assert january["trades"].eq(12).all()
    assert not january["frequency_pass"].any()
    assert not january["month_pass"].any()


@pytest.mark.parametrize(
    ("development_pass", "ticker_pfs", "expected"),
    [
        (True, [0.5, 0.5, 0.5], "PASS_DEVELOPMENT_GATE_OUTER_NOT_OPENED"),
        (False, [1.1, 1.2, 1.3], "INCREMENTAL_EDGE_ALL_TICKERS_ONLY"),
        (False, [1.1, 0.9, 1.2], "PARTIAL_INCREMENTAL_EDGE_ONLY"),
        (False, [1.0, 0.9, 0.8], "NO_AGGREGATE_EDGE"),
    ],
)
def test_status_never_confuses_incremental_pf_with_monthly_pass(
    development_pass: bool, ticker_pfs: list[float], expected: str
) -> None:
    ticker_summary = pd.DataFrame({"profit_factor": ticker_pfs})
    assert parity.classify_status(development_pass, ticker_summary) == expected


def test_committed_data_gate_selects_only_2023_normal_sessions() -> None:
    features, manifest = parity.validate_data_gate()
    assert manifest["status"] == "PASS_DATA_GATE"
    assert features["trade_date"].str.startswith("2023").all()
    assert not features["calendar_half_day"].any()
    assert set(features["ticker"]) == set(parity.TICKERS)
    assert len(features.groupby(["ticker", "month"], observed=True)) == 36


def test_source_inventory_rejects_non_development_outcome_before_path_read(tmp_path: Path) -> None:
    features = pd.DataFrame(
        [{"ticker": "QQQ", "trade_date": "20240102", "parity_pressure": 1.0}]
    )
    with pytest.raises(AssertionError, match="outside development 2023"):
        parity.build_source_inventory(features, tmp_path)


def test_cli_does_not_expose_mutable_scope_or_policy() -> None:
    args = parity.parse_args([])
    for attribute in ("start_date", "end_date", "cost_bps", "entry_time", "exit_time"):
        assert not hasattr(args, attribute)
    with pytest.raises(SystemExit):
        parity.parse_args(["--end-date", "20251231"])


def test_direct_script_cli_imports_from_repo_root() -> None:
    script = Path(parity.__file__).resolve()
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=script.parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--frozen-manifest" in completed.stdout
