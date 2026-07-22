from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v4 as module


def test_required_cash_keys_preserve_spxw_target_source() -> None:
    rows = pd.DataFrame(
        {
            "ticker": ["QQQ", "SPXW", "SPY"],
            "trade_date": ["20250102", "20250102", "20250102"],
        }
    )
    assert module.required_cash_keys(rows) == {
        ("QQQ", "20250102"),
        ("SPY", "20250102"),
        ("SPXW", "20250102"),
    }


def test_ticker_summary_keeps_incremental_and_objective_separate() -> None:
    rows = []
    for ticker in module.TICKERS:
        for month in pd.period_range("2025-01", "2025-12", freq="M").strftime(
            "%Y%m"
        ):
            for index in range(13):
                rows.append(
                    {
                        "ticker": ticker,
                        "month": month,
                        "net_bps": 2.0 if index < 8 else -1.0,
                    }
                )
    ledger = pd.DataFrame(rows)
    monthly = module.summarize_monthly(ledger)
    tickers = module.summarize_tickers(ledger, monthly)
    assert tickers["incremental_gate_pass"].all()
    assert tickers["objective_gate_pass"].all()


def test_cli_has_no_scientific_overrides() -> None:
    args = module.parse_args([])
    for forbidden in ("year", "model", "C", "threshold", "feature", "ticker"):
        assert not hasattr(args, forbidden)


def test_direct_cli_imports() -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(module.__file__).resolve()), "--help"],
        cwd=module.PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
