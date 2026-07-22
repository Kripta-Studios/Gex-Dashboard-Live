#!/usr/bin/env python3
"""Revalidate and seal the immutable 3,008 V1 + 4 V1R1 capture composite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa import (  # noqa: E402
    capture_cross_venue_calendar_rr_native_clock_full as full,
)
from neural.jepa import (  # noqa: E402
    capture_cross_venue_calendar_rr_native_clock_preflight as pre,
)
from neural.jepa import (  # noqa: E402
    capture_cross_venue_calendar_rr_native_clock_repairs_v1r1 as repair,
)

DEFAULT_V1_ROOT = repair.DEFAULT_V1_ROOT
DEFAULT_REPAIR_ROOT = repair.DEFAULT_OUTPUT
DEFAULT_OUTPUT = Path(
    "D:/ThetaData/cross_venue_calendar_rr_native_clock_2024_2025_v1r1_composite"
)
COMPACT_REPAIR_SEAL = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_native_clock_repairs_2024_2025_v1r1/seal.json"
)
EXPECTED_COMPACT_REPAIR_SEAL_SHA256 = (
    "81ded7dd288eea7e040c8823776e10c5a6f0df886131d37679e32c8f1072bd9d"
)
EXPECTED_REPAIR_CONTRACT_SHA256 = (
    "2183608c5e91ec7107a2f1a1835d12b6d6ee30aa1181cf5cfd8eea644a9c8d74"
)
EXPECTED_REPAIR_SPECS_SHA256 = (
    "2fc9d3c9c3b6657c606f1962a60bafadde316419e9f3abd0dafa9e87286d8b44"
)
EXPECTED_REPAIR_SEAL_SHA256 = EXPECTED_COMPACT_REPAIR_SEAL_SHA256
EXPECTED_CAPTURES = 3_012
EXPECTED_SESSIONS = 1_506
EXPECTED_V1_CAPTURES = 3_008
EXPECTED_REPAIR_CAPTURES = 4
CODE_CLOSURE = (
    "neural/jepa/seal_cross_venue_calendar_rr_native_clock_composite_v1r1.py",
    "neural/jepa/capture_cross_venue_calendar_rr_native_clock_repairs_v1r1.py",
    "neural/jepa/capture_cross_venue_calendar_rr_native_clock_full.py",
    "neural/jepa/capture_cross_venue_calendar_rr_native_clock_preflight.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    "neural/jepa/wall_surface_flow_environment.py",
    "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_V1R1_KEY_INTERSECTION_REPAIR_PREDECLARATION.md",
    "research_papers/JEPA/results/_diagnostics/cross_venue_calendar_rr_native_clock_repairs_2024_2025_v1r1/seal.json",
    "research_papers/JEPA/results/_diagnostics/cross_venue_calendar_rr_native_clock_repairs_2024_2025_v1r1/capture_index.csv",
    "research_papers/JEPA/results/_diagnostics/cross_venue_calendar_rr_native_clock_repairs_2024_2025_v1r1/unilateral_vintage_keys.csv",
    "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
)


def dataframe_sha256(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON object required: {path}")
    return value


def validate_repair_root(repair_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    contract_path = repair_root / "_state/capture_contract.json"
    specs_path = repair_root / "_state/repair_specs.csv"
    seal_path = repair_root / "_seal/seal.json"
    index_path = repair_root / "_seal/capture_index.csv"
    unilateral_path = repair_root / "_seal/unilateral_vintage_keys.csv"
    required = (contract_path, specs_path, seal_path, index_path, unilateral_path)
    if not all(path.is_file() for path in required):
        raise FileNotFoundError("V1R1 repair root is incomplete")
    if (
        pre.sha256_file(contract_path) != EXPECTED_REPAIR_CONTRACT_SHA256
        or pre.sha256_file(specs_path) != EXPECTED_REPAIR_SPECS_SHA256
        or pre.sha256_file(seal_path) != EXPECTED_REPAIR_SEAL_SHA256
        or pre.sha256_file(COMPACT_REPAIR_SEAL)
        != EXPECTED_COMPACT_REPAIR_SEAL_SHA256
        or seal_path.read_bytes() != COMPACT_REPAIR_SEAL.read_bytes()
    ):
        raise AssertionError("V1R1 repair contract/seal changed")
    contract = _read_json(contract_path)
    seal = _read_json(seal_path)
    required_contract = {
        "schema": "cross_venue_calendar_rr_native_clock_repairs_v1r1_contract",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
    }
    required_seal = {
        "schema": "cross_venue_calendar_rr_native_clock_repairs_v1r1_seal",
        "status": "PASS_CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_REPAIRS_V1R1",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "captures": EXPECTED_REPAIR_CAPTURES,
        "shared_key_rows": 2_828,
        "unilateral_key_rows": 8,
        "missing_shared_key_rows": 0,
    }
    if any(contract.get(key) != value for key, value in required_contract.items()):
        raise AssertionError("V1R1 repair contract identity changed")
    if any(seal.get(key) != value for key, value in required_seal.items()):
        raise AssertionError("V1R1 repair seal is not a PASS")
    if (
        seal.get("git_commit") != contract.get("git_commit")
        or seal.get("code_hashes") != contract.get("code_hashes")
        or seal.get("source_provenance") != contract.get("source_provenance")
        or seal.get("capture_index_sha256") != pre.sha256_file(index_path)
        or seal.get("unilateral_keys_sha256") != pre.sha256_file(unilateral_path)
    ):
        raise AssertionError("V1R1 repair provenance changed")
    index = pd.read_csv(index_path, dtype={"capture_id": str, "trade_date": str})
    if len(index) != 4 or set(index["capture_id"]) != repair.EXPECTED_REPAIR_IDS:
        raise AssertionError("V1R1 repair index scope changed")
    return contract, seal


def normalize_composite_row(
    row: dict[str, Any], *, generation: str, storage_root: Path
) -> dict[str, Any]:
    greek_rows = int(row["greek_rows"])
    return {
        "capture_id": str(row["capture_id"]),
        "ticker": str(row["ticker"]),
        "trade_date": str(row["trade_date"]),
        "role": str(row["role"]),
        "expiration": str(row["expiration"]),
        "storage_generation": generation,
        "storage_root": str(storage_root),
        "rows": int(row["rows"]),
        "raw_bytes": int(row["raw_bytes"]),
        "parquet_bytes": int(row["parquet_bytes"]),
        "greek_rows": greek_rows,
        "iv_rows": int(row.get("iv_rows", greek_rows)),
        "shared_key_rows": int(row.get("shared_key_rows", greek_rows)),
        "greek_only_key_rows": int(row.get("greek_only_key_rows", 0)),
        "iv_only_key_rows": int(row.get("iv_only_key_rows", 0)),
        "missing_shared_key_rows": int(row.get("missing_shared_key_rows", 0)),
        "native_extra_target_key_rows": int(row["native_extra_target_key_rows"]),
        "revised_bid_ask_rows": int(row["revised_bid_ask_rows"]),
        "crossed_native_rows": int(row["crossed_native_rows"]),
        "raw_sha256": str(row["raw_sha256"]),
        "parquet_sha256": str(row["parquet_sha256"]),
        "manifest_sha256": str(row["manifest_sha256"]),
    }


def _revalidate_one(
    spec: dict[str, Any],
    *,
    v1_root: Path,
    repair_root: Path,
    v1_contract: dict[str, Any],
    repair_contract: dict[str, Any],
) -> dict[str, Any]:
    prepared = full.prepare_spec(spec)
    capture_id = str(prepared["capture_id"])
    if capture_id in repair.EXPECTED_REPAIR_IDS:
        row = repair.validate_existing_repair(
            prepared,
            output=repair_root,
            runtime={
                "lock_sha256": repair_contract["runtime_lock_sha256"],
                "environment_sha256": repair_contract["runtime_environment_sha256"],
            },
            code_hashes=dict(repair_contract["code_hashes"]),
            provenance=dict(repair_contract["source_provenance"]),
        )
        return normalize_composite_row(
            row, generation="V1R1_REPAIR", storage_root=repair_root
        )
    row = pre.validate_existing_capture(
        prepared,
        staging=v1_root,
        capture_code_hashes=dict(v1_contract["code_hashes"]),
        runtime={
            "lock_sha256": v1_contract["runtime_lock_sha256"],
            "environment_sha256": v1_contract["runtime_environment_sha256"],
        },
    )
    return normalize_composite_row(row, generation="V1", storage_root=v1_root)


def revalidate_composite(
    specs: pd.DataFrame,
    *,
    v1_root: Path,
    repair_root: Path,
    v1_contract: dict[str, Any],
    repair_contract: dict[str, Any],
    workers: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                _revalidate_one,
                spec,
                v1_root=v1_root,
                repair_root=repair_root,
                v1_contract=v1_contract,
                repair_contract=repair_contract,
            ): str(spec["capture_id"])
            for spec in specs.to_dict("records")
        }
        for future in as_completed(futures):
            rows.append(future.result())
    index = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date", "role"], kind="stable"
    ).reset_index(drop=True)
    generation_counts = index["storage_generation"].value_counts().to_dict()
    session_counts = (
        index.groupby("ticker", observed=True)["trade_date"].nunique().to_dict()
    )
    if (
        len(index) != EXPECTED_CAPTURES
        or index["capture_id"].duplicated().any()
        or index.duplicated(["ticker", "trade_date", "role"]).any()
        or generation_counts
        != {"V1": EXPECTED_V1_CAPTURES, "V1R1_REPAIR": EXPECTED_REPAIR_CAPTURES}
        or session_counts != {ticker: 502 for ticker in pre.TICKERS}
        or int(index["missing_shared_key_rows"].sum()) != 0
    ):
        raise AssertionError("composite capture scope/revalidation changed")
    return index


def summarize(index: pd.DataFrame) -> pd.DataFrame:
    work = index.copy()
    work["year"] = work["trade_date"].str[:4]
    summary = (
        work.groupby(["ticker", "year", "storage_generation"], observed=True)
        .agg(
            captures=("capture_id", "size"),
            sessions=("trade_date", "nunique"),
            rows=("rows", "sum"),
            shared_key_rows=("shared_key_rows", "sum"),
            greek_only_key_rows=("greek_only_key_rows", "sum"),
            iv_only_key_rows=("iv_only_key_rows", "sum"),
            native_extra_target_key_rows=("native_extra_target_key_rows", "sum"),
            revised_bid_ask_rows=("revised_bid_ask_rows", "sum"),
            crossed_native_rows=("crossed_native_rows", "sum"),
        )
        .reset_index()
        .sort_values(["ticker", "year", "storage_generation"], kind="stable")
        .reset_index(drop=True)
    )
    summary["unilateral_key_rows"] = (
        summary["greek_only_key_rows"] + summary["iv_only_key_rows"]
    )
    return summary


def run(v1_root: Path, repair_root: Path, output: Path, workers: int) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"immutable composite output exists: {output}")
    if workers < 1:
        raise ValueError("workers must be positive")
    commit, code_hashes = pre.committed_code_state(CODE_CLOSURE)
    repair.validate_v1_materialization(v1_root)
    repair_contract, repair_seal = validate_repair_root(repair_root)
    v1_contract = _read_json(v1_root / "_state/capture_contract.json")
    specs, universe_audit = full.discover_full_specs()
    index = revalidate_composite(
        specs,
        v1_root=v1_root,
        repair_root=repair_root,
        v1_contract=v1_contract,
        repair_contract=repair_contract,
        workers=workers,
    )
    ticker_year = summarize(index)
    staging = output.with_name(f".{output.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    (staging / "_state").mkdir(parents=True)
    (staging / "_seal").mkdir()
    try:
        universe_path = staging / "_state/universe.csv"
        shutil.copyfile(v1_root / "_state/universe.csv", universe_path)
        contract = {
            "schema": "cross_venue_calendar_rr_native_clock_composite_v1r1_contract",
            "status": "PASS_COMPOSITE_REVALIDATION",
            "outcome_free": True,
            "holdout_2026_used": False,
            "production_modified": False,
            "git_commit": commit,
            "code_hashes": code_hashes,
            "v1_root": str(v1_root),
            "v1_state_sha256": repair.EXPECTED_V1_STATE_SHA256,
            "repair_root": str(repair_root),
            "repair_contract_sha256": EXPECTED_REPAIR_CONTRACT_SHA256,
            "repair_seal_sha256": EXPECTED_REPAIR_SEAL_SHA256,
            "universe_audit": universe_audit,
            "universe_sha256": pre.sha256_file(universe_path),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        contract_path = staging / "_state/composite_contract.json"
        contract_path.write_bytes(pre.canonical_bytes(contract))
        index_path = staging / "_seal/capture_index.csv"
        summary_path = staging / "_seal/ticker_year_summary.csv"
        index.to_csv(index_path, index=False, lineterminator="\n")
        ticker_year.to_csv(summary_path, index=False, lineterminator="\n")
        unilateral_total = int(
            index["greek_only_key_rows"].sum() + index["iv_only_key_rows"].sum()
        )
        seal = {
            "schema": "cross_venue_calendar_rr_native_clock_composite_v1r1_seal",
            "status": "PASS_CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_COMPOSITE_V1R1",
            "outcome_free": True,
            "holdout_2026_used": False,
            "production_modified": False,
            "git_commit": commit,
            "code_hashes": code_hashes,
            "sessions": EXPECTED_SESSIONS,
            "captures": EXPECTED_CAPTURES,
            "v1_captures": EXPECTED_V1_CAPTURES,
            "repair_captures": EXPECTED_REPAIR_CAPTURES,
            "rows": int(index["rows"].sum()),
            "shared_key_rows": int(index["shared_key_rows"].sum()),
            "unilateral_key_rows": unilateral_total,
            "missing_shared_key_rows": int(index["missing_shared_key_rows"].sum()),
            "native_extra_target_key_rows": int(
                index["native_extra_target_key_rows"].sum()
            ),
            "revised_bid_ask_rows": int(index["revised_bid_ask_rows"].sum()),
            "crossed_native_rows": int(index["crossed_native_rows"].sum()),
            "capture_index_sha256": pre.sha256_file(index_path),
            "ticker_year_summary_sha256": pre.sha256_file(summary_path),
            "composite_contract_sha256": pre.sha256_file(contract_path),
            "universe_sha256": pre.sha256_file(universe_path),
            "v1_contract_sha256": repair.EXPECTED_V1_STATE_SHA256[
                "capture_contract.json"
            ],
            "v1_errors_sha256": repair.EXPECTED_V1_STATE_SHA256["errors.json"],
            "repair_seal_sha256": EXPECTED_REPAIR_SEAL_SHA256,
            "repair_capture_index_sha256": repair_seal["capture_index_sha256"],
            "repair_unilateral_keys_sha256": repair_seal[
                "unilateral_keys_sha256"
            ],
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        (staging / "_seal/seal.json").write_bytes(pre.canonical_bytes(seal))
        staging.rename(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return seal


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1-root", type=Path, default=DEFAULT_V1_ROOT)
    parser.add_argument("--repair-root", type=Path, default=DEFAULT_REPAIR_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    seal = run(
        args.v1_root.resolve(),
        args.repair_root.resolve(),
        args.output_root.resolve(),
        args.workers,
    )
    print(json.dumps(seal, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
