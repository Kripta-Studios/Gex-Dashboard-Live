#!/usr/bin/env python3
"""Independently audit V4R1 retry responses and the outcome-free 2026 gate."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa import (  # noqa: E402
    build_cross_venue_calendar_rr_leader_v4r1_2026_data_gate as builder,
)
from neural.jepa import (  # noqa: E402
    capture_cross_venue_calendar_rr_leader_v4r1_2026_source_retry as capture,
)
from neural.jepa import (  # noqa: E402
    cross_venue_calendar_rr_leader_v4r1_2026_common as common,
)
from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v2 as v2  # noqa: E402
from neural.jepa.build_calendar_risk_reversal_pressure_v1 import (  # noqa: E402
    tracked_clean,
)


PROJECT_ROOT = SCRIPT_REPO_ROOT
DEFAULT_RETRY_ROOT = common.RETRY_ROOT
DEFAULT_INPUT = builder.DEFAULT_OUTPUT
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v4r1_data_gate_202601_20260724_v1_audit"
)
AUDIT_OUTPUT_FILES = ("feature_counts_recomputed.csv", "source_rehash.csv")


def compare_frames(
    recomputed: pd.DataFrame,
    stored: pd.DataFrame,
    keys: list[str],
    label: str,
) -> None:
    left = recomputed.sort_values(keys, kind="stable").reset_index(drop=True)
    right = stored.sort_values(keys, kind="stable").reset_index(drop=True)
    for column in left.columns:
        if column in right.columns and pd.api.types.is_bool_dtype(left[column]):
            right[column] = right[column].map(
                lambda value: str(value).strip().lower() in {"true", "1"}
            )
    try:
        pd.testing.assert_frame_equal(
            left,
            right[left.columns],
            check_dtype=False,
            rtol=1e-12,
            atol=1e-12,
        )
    except AssertionError as error:
        raise AssertionError(f"V4R1 stored {label} differs from audit") from error


def verify_tracked() -> None:
    for path in (
        Path(__file__).resolve(),
        Path(builder.__file__).resolve(),
        Path(capture.__file__).resolve(),
        Path(common.__file__).resolve(),
        common.PREDECLARATION,
    ):
        tracked_clean(path, f"V4R1 auditor closure {path.name}")


def audit_retry_root(retry_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    pair_gate, exclusions, seal = builder.load_retry_gate(retry_root)
    request_index = pd.read_csv(
        retry_root / "request_index.csv",
        dtype={
            "capture_id": str,
            "ticker": str,
            "trade_date": str,
            "expiration": str,
        },
    )
    specs = common.retry_specs(common.discover_universe())
    if (
        len(request_index) != 10
        or request_index.duplicated(["capture_id", "kind"]).any()
    ):
        raise AssertionError("V4R1 retry request index changed")
    spec_lookup = {
        str(row["capture_id"]): row for row in specs.to_dict(orient="records")
    }
    for row in request_index.to_dict(orient="records"):
        directory = Path(str(row["directory"]))
        manifest_path = directory / "manifest.json"
        raw_path = directory / "response.json"
        audit_path = directory / "request_audit.csv"
        if (
            not manifest_path.is_file()
            or not raw_path.is_file()
            or not audit_path.is_file()
            or common.sha256_file(manifest_path) != str(row["manifest_sha256"])
        ):
            raise AssertionError("V4R1 retry request file closure changed")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            common.sha256_file(raw_path) != manifest.get("raw_sha256")
            or common.sha256_file(audit_path) != manifest.get("request_audit_sha256")
            or manifest.get("outcome_free") is not True
            or manifest.get("outcome_2026_accessed") is not False
        ):
            raise AssertionError("V4R1 retry manifest changed")
        if str(row["status"]) == "PASS_NORMALIZED_RESPONSE":
            normalized_path = Path(str(row["normalized_path"]))
            rebuilt = common.normalize_response(
                json.loads(raw_path.read_bytes()),
                spec_lookup[str(row["capture_id"])],
                str(row["kind"]),
                str(row["interval_used"]),
            )
            stored = pd.read_parquet(normalized_path)
            pd.testing.assert_frame_equal(rebuilt, stored, check_dtype=True)
            if common.sha256_file(normalized_path) != manifest.get(
                "normalized_sha256"
            ):
                raise AssertionError("V4R1 normalized retry hash changed")
    recomputed_pairs, recomputed_exclusions = capture.build_pair_gate(
        request_index, specs
    )
    compare_frames(
        recomputed_pairs,
        pair_gate,
        ["capture_id"],
        "retry pair gate",
    )
    compare_frames(
        recomputed_exclusions,
        exclusions,
        ["sensor_ticker", "trade_date"],
        "retry exclusions",
    )
    return pair_gate, exclusions, seal


def validate_gate_hashes(summary: dict[str, Any], input_dir: Path) -> None:
    expected = summary.get("output_sha256")
    if not isinstance(expected, dict) or set(expected) != set(builder.OUTPUT_FILES):
        raise AssertionError("V4R1 data-gate output hash closure changed")
    for name in builder.OUTPUT_FILES:
        if common.sha256_file(input_dir / name) != expected[name]:
            raise AssertionError(f"V4R1 data-gate output hash mismatch: {name}")


def run(
    retry_root: Path,
    input_dir: Path,
    output_dir: Path,
    workers: int,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V4R1 audit exists: {output_dir}")
    if not 1 <= workers <= 16:
        raise ValueError("workers must be in [1, 16]")
    verify_tracked()
    pair_gate, exclusions, retry_seal = audit_retry_root(retry_root)
    summary = json.loads((input_dir / "SUMMARY.json").read_text(encoding="utf-8"))
    if (
        summary.get("schema")
        != "cross_venue_calendar_rr_leader_v4r1_2026_data_gate_v1"
        or summary.get("status") != "PASS_OUTCOME_FREE_DATA_GATE"
        or summary.get("date_sha256") != common.DATE_SHA256
        or summary.get("capture_id_sha256") != common.CAPTURE_ID_SHA256
        or summary.get("predeclaration_sha256") != common.PREDECLARATION_SHA256
        or summary.get("outcome_clock_read") is not False
        or summary.get("open_1036_read") is not False
        or summary.get("open_1336_read") is not False
        or summary.get("outcome_2026_accessed") is not False
        or summary.get("production_modified") is not False
        or summary.get("retry_usable_pairs") != int(retry_seal["usable_pairs"])
        or summary.get("excluded_sensor_dates") != len(exclusions)
    ):
        raise AssertionError("V4R1 data-gate summary contract changed")
    validate_gate_hashes(summary, input_dir)

    universe = common.discover_universe()
    sensor_features, sensor_audit, sensor_inventory = builder.build_sensor_features(
        universe, pair_gate, exclusions, workers
    )
    targets = builder.map_targets(sensor_features)
    feature_view, cash_audit, cash_inventory = builder.attach_cash_features(
        targets, workers
    )
    feature_view = feature_view[
        ["ticker", "trade_date", "month", "sensor_ticker", *v2.FEATURE_COLUMNS]
    ].copy()
    counts = builder.feature_counts(feature_view)
    inventory = pd.concat(
        [sensor_inventory, cash_inventory], ignore_index=True
    ).drop_duplicates("path").sort_values(
        ["kind", "ticker", "trade_date", "role"], kind="stable"
    ).reset_index(drop=True)
    stored_universe = pd.read_csv(
        input_dir / "universe.csv",
        dtype={
            "ticker": str,
            "trade_date": str,
            "month": str,
            "front_expiration": str,
            "back_expiration": str,
        },
    )
    compare_frames(universe, stored_universe, ["ticker", "trade_date"], "universe")
    compare_frames(
        sensor_features,
        pd.read_parquet(input_dir / "sensor_features.parquet"),
        ["ticker", "trade_date"],
        "sensor features",
    )
    compare_frames(
        feature_view,
        pd.read_parquet(input_dir / "feature_view.parquet"),
        ["ticker", "trade_date"],
        "feature view",
    )
    compare_frames(
        counts,
        pd.read_csv(
            input_dir / "feature_counts.csv", dtype={"ticker": str, "month": str}
        ),
        ["ticker", "month"],
        "feature counts",
    )
    compare_frames(
        sensor_audit,
        pd.read_csv(
            input_dir / "sensor_feature_audit.csv",
            dtype={"ticker": str, "trade_date": str},
        ),
        ["ticker", "trade_date"],
        "sensor audit",
    )
    compare_frames(
        cash_audit,
        pd.read_csv(
            input_dir / "cash_source_audit.csv",
            dtype={"ticker": str, "trade_date": str},
        ),
        ["ticker", "trade_date"],
        "cash audit",
    )
    compare_frames(
        inventory,
        pd.read_csv(
            input_dir / "source_inventory.csv",
            dtype={"ticker": str, "trade_date": str},
        ),
        ["kind", "ticker", "trade_date", "role"],
        "source inventory",
    )
    rehash = inventory[["kind", "ticker", "trade_date", "path", "sha256"]].copy()
    rehash["actual_sha256"] = rehash["path"].map(common.sha256_file)
    rehash["match"] = rehash["sha256"].eq(rehash["actual_sha256"])
    if (
        not rehash["match"].all()
        or summary.get("source_files_rehashed") != len(inventory)
        or summary.get("feature_view_recomputed_sha256")
        != builder.dataframe_digest(feature_view)
        or summary.get("feature_counts_recomputed_sha256")
        != builder.dataframe_digest(counts)
        or summary.get("source_inventory_recomputed_sha256")
        != builder.dataframe_digest(inventory)
        or not np.isfinite(
            feature_view[list(v2.FEATURE_COLUMNS)].to_numpy(dtype=float)
        ).all()
    ):
        raise AssertionError("V4R1 independently recomputed gate changed")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        counts.to_csv(
            staging / AUDIT_OUTPUT_FILES[0], index=False, lineterminator="\n"
        )
        rehash.to_csv(
            staging / AUDIT_OUTPUT_FILES[1], index=False, lineterminator="\n"
        )
        audit = {
            "schema": "cross_venue_calendar_rr_leader_v4r1_2026_data_gate_audit_v1",
            "status": "PASS_INDEPENDENT_OUTCOME_FREE_DATA_GATE_AUDIT",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "evaluation_commit": summary["execution_commit"],
            "audit_commit": builder.current_git_commit(),
            "retry_requests_reparsed": 10,
            "retry_usable_pairs": int(retry_seal["usable_pairs"]),
            "excluded_sensor_dates": int(len(exclusions)),
            "source_files_rehashed": int(len(rehash)),
            "source_hash_mismatches": 0,
            "sensor_feature_rows": int(len(sensor_features)),
            "target_feature_rows": int(len(feature_view)),
            "monthly_cells": int(len(counts)),
            "feature_view_exact": True,
            "feature_count": len(v2.FEATURE_COLUMNS),
            "outcome_clock_read": False,
            "open_1036_read": False,
            "open_1336_read": False,
            "outcome_2026_accessed": False,
            "production_modified": False,
            "live_or_systemd_modified": False,
            "evaluation_summary_sha256": common.sha256_file(
                input_dir / "SUMMARY.json"
            ),
            "feature_view_recomputed_sha256": builder.dataframe_digest(
                feature_view
            ),
            "feature_counts_recomputed_sha256": builder.dataframe_digest(counts),
            "source_inventory_recomputed_sha256": builder.dataframe_digest(
                inventory
            ),
            "output_sha256": {
                name: common.sha256_file(staging / name)
                for name in AUDIT_OUTPUT_FILES
            },
        }
        (staging / "audit_summary.json").write_text(
            json.dumps(audit, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return audit


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retry-root", type=Path, default=DEFAULT_RETRY_ROOT)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    audit = run(
        args.retry_root.resolve(),
        args.input_dir.resolve(),
        args.output_dir.resolve(),
        args.workers,
    )
    print(json.dumps(audit, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
