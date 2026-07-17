#!/usr/bin/env python3
"""Audit and compact the sealed full cross-venue native-clock capture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa.build_cross_venue_calendar_rr_leader_v1 import (  # noqa: E402
    DEFAULT_OPTIONS_ROOT,
    DEFAULT_SIDECAR_ROOT,
    revalidate_all_captures,
    sha256_file,
    tracked_clean,
    validate_full_capture_seal,
)
from neural.jepa.capture_cross_venue_calendar_rr_native_clock_full import (  # noqa: E402
    EXPECTED_CAPTURES,
    EXPECTED_SESSIONS,
    discover_full_specs,
)


PROJECT_ROOT = SCRIPT_REPO_ROOT
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "tmp/cross_venue_calendar_rr_native_clock_full_2024_2025_v1_audit"
)
DATA_GATE_CONTRACT = PROJECT_ROOT / (
    "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_LEADER_V1_DATA_GATE_CONTRACT.md"
)
DATA_GATE_BUILDER = PROJECT_ROOT / (
    "neural/jepa/build_cross_venue_calendar_rr_leader_v1.py"
)


def current_git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def dataframe_digest(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def summarize_capture_index(index: pd.DataFrame) -> pd.DataFrame:
    frame = index.copy()
    frame["year"] = frame["trade_date"].astype(str).str[:4]
    numeric = (
        "rows",
        "raw_bytes",
        "parquet_bytes",
        "native_extra_target_key_rows",
        "revised_bid_ask_rows",
        "crossed_native_rows",
    )
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    summary = (
        frame.groupby(["ticker", "year"], observed=True)
        .agg(
            captures=("capture_id", "size"),
            sessions=("trade_date", "nunique"),
            rows=("rows", "sum"),
            raw_bytes=("raw_bytes", "sum"),
            parquet_bytes=("parquet_bytes", "sum"),
            native_extra_target_key_rows=("native_extra_target_key_rows", "sum"),
            revised_bid_ask_rows=("revised_bid_ask_rows", "sum"),
            crossed_native_rows=("crossed_native_rows", "sum"),
        )
        .reset_index()
        .sort_values(["ticker", "year"], kind="stable")
        .reset_index(drop=True)
    )
    return summary


def source_hash_inventory(prepared_specs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in prepared_specs.to_dict(orient="records"):
        for kind in ("greeks", "iv"):
            path = Path(str(record[f"{kind}_path"]))
            rows.append(
                {
                    "capture_id": str(record["capture_id"]),
                    "ticker": str(record["ticker"]),
                    "trade_date": str(record["trade_date"]),
                    "role": str(record["role"]),
                    "expiration": str(record["expiration"]),
                    "kind": kind,
                    "path": str(path),
                    "size_bytes": int(path.stat().st_size),
                    "sha256": str(record[f"{kind}_sha256"]),
                }
            )
    output = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date", "role", "kind"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(output) != EXPECTED_CAPTURES * 2
        or output["path"].duplicated().any()
        or output["sha256"].isna().any()
    ):
        raise AssertionError("vintage source hash inventory is incomplete")
    return output


def run(
    options_root: Path,
    sidecar_root: Path,
    output_dir: Path,
    workers: int,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    if workers < 1:
        raise ValueError("workers must be positive")
    for path, label in (
        (Path(__file__).resolve(), "full capture auditor"),
        (DATA_GATE_BUILDER, "capture revalidation builder"),
        (DATA_GATE_CONTRACT, "data gate contract"),
    ):
        tracked_clean(path, label)
    contract, seal, index = validate_full_capture_seal(sidecar_root)
    specs, universe_audit = discover_full_specs(options_root)
    prepared, revalidated = revalidate_all_captures(
        specs,
        sidecar_root=sidecar_root,
        contract=contract,
        expected_index=index,
        workers=workers,
    )
    sources = source_hash_inventory(prepared)
    aggregate = summarize_capture_index(revalidated)
    if (
        len(revalidated) != EXPECTED_CAPTURES
        or revalidated["capture_id"].duplicated().any()
        or int(aggregate["captures"].sum()) != EXPECTED_CAPTURES
        or int(aggregate["sessions"].sum()) != EXPECTED_SESSIONS
    ):
        raise AssertionError("revalidated capture aggregate changed")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        revalidated.to_csv(staging / "capture_revalidation.csv", index=False)
        aggregate.to_csv(staging / "ticker_year_summary.csv", index=False)
        sources.to_csv(staging / "vintage_source_inventory.csv", index=False)
        shutil.copyfile(sidecar_root / "_seal/seal.json", staging / "seal.json")
        shutil.copyfile(
            sidecar_root / "_seal/capture_index.csv", staging / "capture_index.csv"
        )
        shutil.copyfile(
            sidecar_root / "_state/capture_contract.json",
            staging / "capture_contract.json",
        )
        shutil.copyfile(sidecar_root / "_state/universe.csv", staging / "universe.csv")
        output_names = (
            "capture_revalidation.csv",
            "ticker_year_summary.csv",
            "vintage_source_inventory.csv",
            "seal.json",
            "capture_index.csv",
            "capture_contract.json",
            "universe.csv",
        )
        summary = {
            "schema": "cross_venue_calendar_rr_native_clock_full_audit_v1",
            "status": "PASS_FULL_CAPTURE_AUDIT",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "audit_commit": current_git_commit(),
            "capture_commit": contract["git_commit"],
            "capture_seal_created_at_utc": seal["created_at_utc"],
            "sessions": EXPECTED_SESSIONS,
            "captures": EXPECTED_CAPTURES,
            "rows": int(revalidated["rows"].sum()),
            "raw_bytes": int(revalidated["raw_bytes"].sum()),
            "parquet_bytes": int(revalidated["parquet_bytes"].sum()),
            "missing_vintage_key_rows": 0,
            "native_extra_target_key_rows": int(
                revalidated["native_extra_target_key_rows"].sum()
            ),
            "revised_bid_ask_rows": int(revalidated["revised_bid_ask_rows"].sum()),
            "crossed_native_rows": int(revalidated["crossed_native_rows"].sum()),
            "universe_audit": universe_audit,
            "capture_revalidation_sha256": dataframe_digest(revalidated),
            "ticker_year_summary_sha256": dataframe_digest(aggregate),
            "vintage_source_inventory_sha256": dataframe_digest(sources),
            "data_gate_contract_sha256": sha256_file(DATA_GATE_CONTRACT),
            "data_gate_builder_sha256": sha256_file(DATA_GATE_BUILDER),
            "auditor_sha256": sha256_file(Path(__file__).resolve()),
            "output_sha256": {
                name: sha256_file(staging / name) for name in output_names
            },
            "outcome_accessed": False,
            "underlying_accessed": False,
            "outer_2024_opened": False,
            "outer_2025_opened": False,
            "holdout_2026_opened": False,
            "production_modified": False,
        }
        (staging / "audit_summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--options-root", type=Path, default=DEFAULT_OPTIONS_ROOT)
    parser.add_argument("--sidecar-root", type=Path, default=DEFAULT_SIDECAR_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(
        args.options_root.resolve(),
        args.sidecar_root.resolve(),
        args.output_dir.resolve(),
        args.workers,
    )
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
