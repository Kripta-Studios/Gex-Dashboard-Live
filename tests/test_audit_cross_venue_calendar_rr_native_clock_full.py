from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from neural.jepa import audit_cross_venue_calendar_rr_native_clock_full as module


def test_ticker_year_summary_preserves_capture_totals() -> None:
    index = pd.DataFrame(
        [
            {
                "capture_id": "a",
                "ticker": "QQQ",
                "trade_date": "20240102",
                "storage_generation": "V1",
                "rows": 10,
                "raw_bytes": 100,
                "parquet_bytes": 20,
                "shared_key_rows": 4,
                "greek_only_key_rows": 0,
                "iv_only_key_rows": 0,
                "missing_shared_key_rows": 0,
                "native_extra_target_key_rows": 1,
                "revised_bid_ask_rows": 2,
                "crossed_native_rows": 3,
            },
            {
                "capture_id": "b",
                "ticker": "QQQ",
                "trade_date": "20240102",
                "storage_generation": "V1R1_REPAIR",
                "rows": 11,
                "raw_bytes": 110,
                "parquet_bytes": 21,
                "shared_key_rows": 3,
                "greek_only_key_rows": 0,
                "iv_only_key_rows": 2,
                "missing_shared_key_rows": 0,
                "native_extra_target_key_rows": 4,
                "revised_bid_ask_rows": 5,
                "crossed_native_rows": 6,
            },
            {
                "capture_id": "c",
                "ticker": "QQQ",
                "trade_date": "20250102",
                "storage_generation": "V1",
                "rows": 12,
                "raw_bytes": 120,
                "parquet_bytes": 22,
                "shared_key_rows": 4,
                "greek_only_key_rows": 0,
                "iv_only_key_rows": 0,
                "missing_shared_key_rows": 0,
                "native_extra_target_key_rows": 7,
                "revised_bid_ask_rows": 8,
                "crossed_native_rows": 9,
            },
        ]
    )
    summary = module.summarize_capture_index(index)
    rows_2024 = summary.loc[summary["year"].eq("2024")]
    assert rows_2024["captures"].sum() == 2
    assert set(rows_2024["storage_generation"]) == {"V1", "V1R1_REPAIR"}
    assert rows_2024["rows"].sum() == 21
    assert rows_2024["iv_only_key_rows"].sum() == 2
    assert rows_2024["native_extra_target_key_rows"].sum() == 5
    assert summary["captures"].sum() == 3


def test_cli_cannot_open_outcomes_or_change_scope() -> None:
    args = module.parse_args([])
    for forbidden in ("outcome", "label", "year", "start_date", "end_date"):
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
    assert "--sidecar-root" in completed.stdout
    assert "--workers" in completed.stdout
