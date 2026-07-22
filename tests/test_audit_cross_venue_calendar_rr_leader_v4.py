from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa import audit_cross_venue_calendar_rr_leader_v4 as module


def test_output_hashes_bind_exact_bytes(tmp_path: Path) -> None:
    expected: dict[str, str] = {}
    for name in module.OUTPUT_HASH_FILES:
        path = tmp_path / name
        path.write_bytes(f"{name}\n".encode())
        expected[name] = module.evaluate.sha256_file(path)
    module.validate_output_hashes({"output_sha256": expected}, tmp_path)
    (tmp_path / "trades.csv").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="trades.csv"):
        module.validate_output_hashes({"output_sha256": expected}, tmp_path)


def test_frame_comparison_detects_economic_change() -> None:
    expected = pd.DataFrame({"ticker": ["QQQ"], "net_bps": [1.0]})
    changed = pd.DataFrame({"ticker": ["QQQ"], "net_bps": [2.0]})
    with pytest.raises(AssertionError, match="differs"):
        module.compare_frames(expected, changed, ["ticker"], "test")


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
