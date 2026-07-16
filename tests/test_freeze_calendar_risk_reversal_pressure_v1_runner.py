from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from neural.jepa import evaluate_calendar_risk_reversal_pressure_v1 as evaluate
from neural.jepa import freeze_calendar_risk_reversal_pressure_v1_runner as freeze


def test_freeze_payload_is_2023_only_and_preexecution(monkeypatch) -> None:
    monkeypatch.setattr(evaluate, "tracked_clean", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(evaluate, "current_git_commit", lambda: "a" * 40)
    payload = freeze.build_payload()
    assert payload["status"] == "PREEXECUTION_FROZEN"
    assert payload["phase"] == "development_2023"
    assert payload["scope"]["eligible_events"] == 741
    assert payload["scope"]["underlying_sources"] == 741
    assert payload["outcome_accessed"] is False
    assert payload["execution_started"] is False
    assert payload["outer_2024_2025_opened"] is False
    assert payload["holdout_2026_opened"] is False
    assert payload["policy"] == evaluate.POLICY
    assert payload["gate_spec"] == evaluate.GATE_SPEC


def test_direct_freezer_cli_imports() -> None:
    script = Path(freeze.__file__).resolve()
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=script.parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--output" in completed.stdout
