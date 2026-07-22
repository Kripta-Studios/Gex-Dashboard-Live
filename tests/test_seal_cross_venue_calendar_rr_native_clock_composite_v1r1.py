from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa import (
    seal_cross_venue_calendar_rr_native_clock_composite_v1r1 as module,
)


def _row(capture_id: str, generation: str) -> dict[str, object]:
    return {
        "capture_id": capture_id,
        "ticker": "QQQ",
        "trade_date": "20240102",
        "role": "front",
        "expiration": "20240102",
        "storage_generation": generation,
        "storage_root": "root",
        "rows": 10,
        "raw_bytes": 100,
        "parquet_bytes": 20,
        "greek_rows": 4,
        "iv_rows": 4,
        "shared_key_rows": 4,
        "greek_only_key_rows": 0,
        "iv_only_key_rows": 0,
        "missing_shared_key_rows": 0,
        "native_extra_target_key_rows": 0,
        "revised_bid_ask_rows": 0,
        "crossed_native_rows": 0,
        "raw_sha256": "r",
        "parquet_sha256": "p",
        "manifest_sha256": "m",
    }


def test_real_repair_root_and_scope_are_frozen() -> None:
    contract, seal = module.validate_repair_root(module.DEFAULT_REPAIR_ROOT)
    assert contract["git_commit"].startswith("0b7cc6dd")
    assert seal["captures"] == 4
    specs, audit = module.full.discover_full_specs()
    assert len(specs) == 3_012
    assert audit["sessions"] == 1_506
    assert set(specs.loc[specs["capture_id"].isin(module.repair.EXPECTED_REPAIR_IDS), "capture_id"]) == module.repair.EXPECTED_REPAIR_IDS


def test_normalize_v1_row_sets_zero_unilateral_counts(tmp_path: Path) -> None:
    raw = {
        "capture_id": "x",
        "ticker": "QQQ",
        "trade_date": "20240102",
        "role": "front",
        "expiration": "20240102",
        "rows": 10,
        "raw_bytes": 100,
        "parquet_bytes": 20,
        "greek_rows": 4,
        "native_extra_target_key_rows": 1,
        "revised_bid_ask_rows": 0,
        "crossed_native_rows": 0,
        "raw_sha256": "r",
        "parquet_sha256": "p",
        "manifest_sha256": "m",
    }
    row = module.normalize_composite_row(
        raw, generation="V1", storage_root=tmp_path
    )
    assert row["iv_rows"] == 4
    assert row["shared_key_rows"] == 4
    assert row["greek_only_key_rows"] == 0
    assert row["iv_only_key_rows"] == 0


def test_summary_preserves_generation(tmp_path: Path) -> None:
    first = _row("a", "V1")
    second = _row("b", "V1R1_REPAIR")
    second["role"] = "back"
    second["greek_only_key_rows"] = 2
    second["iv_only_key_rows"] = 3
    summary = module.summarize(pd.DataFrame([first, second]))
    assert set(summary["storage_generation"]) == {"V1", "V1R1_REPAIR"}
    assert summary["captures"].sum() == 2
    assert summary["unilateral_key_rows"].sum() == 5


def test_run_refuses_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError, match="immutable composite"):
        module.run(tmp_path, tmp_path, output, 1)


def test_cli_cannot_change_capture_scope_or_open_outcomes() -> None:
    args = module.parse_args([])
    for forbidden in ("capture_id", "allow", "year", "outcome", "label"):
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
    assert "--v1-root" in completed.stdout
    assert "--repair-root" in completed.stdout
