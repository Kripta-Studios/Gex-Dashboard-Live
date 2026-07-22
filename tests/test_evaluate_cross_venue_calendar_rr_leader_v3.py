from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v3 as module


def test_mapping_and_threshold_are_frozen() -> None:
    assert module.SENSOR_MAP == {"QQQ": "QQQ", "SPXW": "SPY", "SPY": "SPY"}
    assert module.ORIENTATION_THRESHOLD == 0.5
    assert module.orientation_from_hit_rate(0.5) == 1
    assert module.orientation_from_hit_rate(0.499999) == -1


def test_invalid_hit_rate_fails_closed() -> None:
    for value in (-0.1, 1.1, float("nan")):
        with pytest.raises(ValueError, match="hit rate"):
            module.orientation_from_hit_rate(value)


def test_monthly_state_uses_only_immediately_prior_month() -> None:
    rows = []
    for month, hit in (("202312", True), ("202401", False)):
        for ticker in module.TICKERS:
            for day in range(13):
                rows.append(
                    {
                        "ticker": ticker,
                        "month": month,
                        "trade_executed": True,
                        "direct_win": hit,
                        "day": day,
                    }
                )
    history = pd.DataFrame(rows)
    with pytest.raises(AssertionError, match="prior-month frequency"):
        module.build_monthly_states(history)


def test_cli_cannot_select_window_threshold_or_model() -> None:
    args = module.parse_args([])
    for forbidden in ("window", "threshold", "model", "ticker", "year", "cost"):
        assert not hasattr(args, forbidden)


def test_direct_cli_imports() -> None:
    script = Path(module.__file__).resolve()
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=module.PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--output-dir" in completed.stdout
