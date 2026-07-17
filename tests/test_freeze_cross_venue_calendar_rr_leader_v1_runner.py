from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from neural.jepa import freeze_cross_venue_calendar_rr_leader_v1_runner as module


def test_freezer_has_no_mutable_scope_arguments() -> None:
    args = module.parse_args([])
    assert hasattr(args, "output")
    for forbidden in ("year", "outcome", "policy", "cost", "sensor"):
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
    assert "--output" in completed.stdout
