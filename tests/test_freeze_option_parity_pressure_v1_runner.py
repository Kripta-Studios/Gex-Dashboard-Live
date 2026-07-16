from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from neural.jepa import evaluate_option_parity_pressure_v1 as evaluate
from neural.jepa import freeze_option_parity_pressure_v1_runner as freeze


def test_freeze_payload_is_preexecution_and_2023_only(monkeypatch) -> None:
    monkeypatch.setattr(evaluate, "tracked_clean", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(evaluate, "current_git_commit", lambda: "f" * 40)

    payload = freeze.build_payload()

    assert payload["status"] == "PREEXECUTION_FROZEN"
    assert payload["phase"] == "development_2023"
    assert payload["scope"]["start_date"] == "20230101"
    assert payload["scope"]["end_date"] == "20231231"
    assert payload["outcome_accessed"] is False
    assert payload["execution_started"] is False
    assert payload["outer_2024_2025_opened"] is False
    assert payload["holdout_2026_opened"] is False
    assert payload["policy"] == evaluate.POLICY
    assert payload["gate_spec"] == evaluate.GATE_SPEC


def test_direct_freezer_cli_imports_from_repo_root() -> None:
    script = Path(freeze.__file__).resolve()
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=script.parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--output" in completed.stdout
