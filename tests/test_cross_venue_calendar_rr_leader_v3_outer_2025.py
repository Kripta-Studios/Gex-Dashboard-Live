from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v3_outer_2025 as outer
from neural.jepa import freeze_cross_venue_calendar_rr_leader_v3_runner as freezer


def test_state_from_direct_rows_uses_pooled_physical_hits() -> None:
    rows = []
    for ticker in outer.TICKERS:
        for index in range(13):
            rows.append(
                {
                    "ticker": ticker,
                    "month": "202412",
                    "base_gross_bps": 1.0 if index < 7 else -1.0,
                }
            )
    state = outer.state_from_direct_rows(pd.DataFrame(rows), "202412")
    assert state["prior_pooled_trades"] == 39
    assert state["prior_direct_hits"] == 21
    assert state["orientation"] == 1


def test_outer_cli_has_no_scientific_overrides() -> None:
    args = outer.parse_args([])
    for forbidden in ("threshold", "window", "model", "year", "cost", "ticker"):
        assert not hasattr(args, forbidden)


def test_freezer_cli_has_no_scientific_overrides() -> None:
    args = freezer.parse_args([])
    for forbidden in ("threshold", "window", "model", "year", "cost", "ticker"):
        assert not hasattr(args, forbidden)


def test_freezer_atomically_creates_new_output(
    tmp_path: Path, monkeypatch: object
) -> None:
    features = pd.DataFrame(
        {
            "ticker": ["QQQ", "SPXW", "SPY"],
            "month": ["202501", "202501", "202501"],
        }
    )
    events = pd.DataFrame(
        {
            "ticker": ["QQQ", "SPXW", "SPY"],
            "trade_date": ["20250102", "20250102", "20250102"],
            "month": ["202501", "202501", "202501"],
            "path": ["q", "x", "s"],
        }
    )
    monkeypatch.setattr(freezer, "tracked_worktree_clean", lambda: None)
    monkeypatch.setattr(outer, "validate_frozen_inputs", lambda: None)
    monkeypatch.setattr(outer, "load_2025_inputs", lambda: (features, events))
    monkeypatch.setattr(
        outer,
        "initial_state_from_development",
        lambda: {"prior_month": "202412", "orientation": -1},
    )
    output = tmp_path / "frozen" / "manifest.json"
    payload = freezer.run(output)
    assert output.is_file()
    assert payload["events"] == 3


def test_both_direct_clis_import() -> None:
    for module in (outer, freezer):
        completed = subprocess.run(
            [sys.executable, str(Path(module.__file__).resolve()), "--help"],
            cwd=outer.PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
