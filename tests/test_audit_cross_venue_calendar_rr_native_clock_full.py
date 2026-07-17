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
                "rows": 10,
                "raw_bytes": 100,
                "parquet_bytes": 20,
                "native_extra_target_key_rows": 1,
                "revised_bid_ask_rows": 2,
                "crossed_native_rows": 3,
            },
            {
                "capture_id": "b",
                "ticker": "QQQ",
                "trade_date": "20240102",
                "rows": 11,
                "raw_bytes": 110,
                "parquet_bytes": 21,
                "native_extra_target_key_rows": 4,
                "revised_bid_ask_rows": 5,
                "crossed_native_rows": 6,
            },
            {
                "capture_id": "c",
                "ticker": "QQQ",
                "trade_date": "20250102",
                "rows": 12,
                "raw_bytes": 120,
                "parquet_bytes": 22,
                "native_extra_target_key_rows": 7,
                "revised_bid_ask_rows": 8,
                "crossed_native_rows": 9,
            },
        ]
    )
    summary = module.summarize_capture_index(index)
    row_2024 = summary.loc[summary["year"].eq("2024")].iloc[0]
    assert row_2024["captures"] == 2
    assert row_2024["sessions"] == 1
    assert row_2024["rows"] == 21
    assert row_2024["native_extra_target_key_rows"] == 5
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
