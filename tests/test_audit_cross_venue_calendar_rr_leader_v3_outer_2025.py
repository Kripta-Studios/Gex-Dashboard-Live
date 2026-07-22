from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa import audit_cross_venue_calendar_rr_leader_v3_outer_2025 as audit


def test_state_uses_pooled_physical_rows() -> None:
    rows = []
    for ticker in audit.outer.TICKERS:
        for index in range(13):
            rows.append(
                {
                    "ticker": ticker,
                    "base_gross_bps": 1.0 if index < 7 else -1.0,
                }
            )
    state = audit.state_from_month(pd.DataFrame(rows), "202501")
    assert state["prior_pooled_trades"] == 39
    assert state["prior_direct_hits"] == 21
    assert state["orientation"] == 1


def test_profit_factor_is_independently_recomputed() -> None:
    assert audit.profit_factor([2.0, -1.0, 4.0, -2.0]) == pytest.approx(2.0)
    expected = math.exp(0.01)
    assert float(np_log(expected)) == pytest.approx(0.01)


def np_log(value: float) -> float:
    return math.log(value)


def test_cli_has_no_scientific_overrides() -> None:
    args = audit.parse_args([])
    for forbidden in ("threshold", "window", "model", "year", "cost", "ticker"):
        assert not hasattr(args, forbidden)


def test_direct_cli_imports() -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(audit.__file__).resolve()), "--help"],
        cwd=audit.PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
