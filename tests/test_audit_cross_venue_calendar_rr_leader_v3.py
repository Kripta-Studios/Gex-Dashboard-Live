from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from neural.jepa import audit_cross_venue_calendar_rr_leader_v3 as module


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


def test_cli_has_no_scientific_overrides() -> None:
    args = module.parse_args([])
    for forbidden in ("threshold", "window", "model", "year", "cost", "ticker"):
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
    assert "--input-dir" in completed.stdout
