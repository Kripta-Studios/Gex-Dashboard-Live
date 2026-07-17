#!/usr/bin/env python3
"""Independently audit the outcome-free cross-venue calendar-RR data gate."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa.build_cross_venue_calendar_rr_leader_v1 import (  # noqa: E402
    DATA_GATE_CONTRACT,
    DEFAULT_OUTPUT as DEFAULT_DATA_GATE_DIR,
    DEFAULT_SIDECAR_ROOT,
    EXPECTED_CAPTURES,
    EXPECTED_SESSIONS,
    SENSOR_MAP,
    TICKERS,
    dataframe_digest,
    evaluate_data_gate,
    sha256_file,
    tracked_clean,
    validate_full_capture_seal,
)


PROJECT_ROOT = SCRIPT_REPO_ROOT
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "tmp/cross_venue_calendar_rr_leader_v1_data_gate_202401_202512_v1_audit"
)
DATA_GATE_BUILDER = PROJECT_ROOT / (
    "neural/jepa/build_cross_venue_calendar_rr_leader_v1.py"
)
OUTPUT_FILES = (
    "cross_venue_calendar_rr_features.parquet",
    "session_audit.csv",
    "capture_revalidation.csv",
    "source_inventory.csv",
    "coverage.csv",
    "distinctness.csv",
    "monthly_capacity.csv",
    "errors.csv",
)
FORBIDDEN_OUTCOME_COLUMNS = frozenset(
    {
        "entry_open",
        "exit_open",
        "underlying_return_bps",
        "gross_bps",
        "net_bps",
        "pnl",
        "label",
        "target",
        "outcome",
        "win",
    }
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


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON object required: {path}")
    return value


def assert_outcome_free_schema(features: pd.DataFrame) -> None:
    lowered = {str(column).lower() for column in features.columns}
    exact = sorted(lowered.intersection(FORBIDDEN_OUTCOME_COLUMNS))
    derived = sorted(
        column
        for column in lowered
        if column.startswith("future_")
        or column.endswith("_label")
        or "profit_loss" in column
        or "10:36" in column
        or "13:36" in column
    )
    if exact or derived:
        raise AssertionError(f"outcome-like columns found: {sorted(set(exact + derived))}")


def verify_mapping_parity(features: pd.DataFrame) -> pd.DataFrame:
    required = {
        "ticker",
        "trade_date",
        "calendar_rr_pressure",
        "local_feature_valid",
        "sensor_ticker",
        "signal_pressure",
        "signal_action",
        "mapped_feature_valid",
    }
    missing = sorted(required.difference(features.columns))
    if missing:
        raise KeyError(f"mapping audit lacks fields: {missing}")
    local = features[
        ["ticker", "trade_date", "calendar_rr_pressure", "local_feature_valid"]
    ].rename(
        columns={
            "ticker": "sensor_ticker_expected",
            "calendar_rr_pressure": "sensor_pressure_expected",
            "local_feature_valid": "sensor_valid_expected",
        }
    )
    work = features.merge(
        local,
        left_on=["sensor_ticker", "trade_date"],
        right_on=["sensor_ticker_expected", "trade_date"],
        how="left",
        validate="many_to_one",
    )
    work["expected_sensor"] = work["ticker"].map(SENSOR_MAP)
    if (
        len(work) != len(features)
        or not work["sensor_ticker"].eq(work["expected_sensor"]).all()
        or work[["sensor_ticker_expected", "sensor_valid_expected"]].isna().any().any()
    ):
        raise AssertionError("cross-venue exact-date sensor join changed")
    valid = work["mapped_feature_valid"].astype(bool)
    expected_valid = work["local_feature_valid"].astype(bool) & work[
        "sensor_valid_expected"
    ].astype(bool)
    pressure = pd.to_numeric(work["signal_pressure"], errors="coerce")
    sensor_pressure = pd.to_numeric(work["sensor_pressure_expected"], errors="coerce")
    differences = (pressure - sensor_pressure).abs()
    expected_action = np.sign(pressure.loc[valid]).astype(np.int64)
    actions = pd.to_numeric(work["signal_action"], errors="raise").astype(np.int64)
    if (
        not valid.eq(expected_valid).all()
        or not np.isfinite(pressure.loc[valid].to_numpy(dtype=float)).all()
        or not differences.loc[valid].eq(0.0).all()
        or not actions.loc[valid].eq(expected_action).all()
        or not actions.loc[~valid].eq(0).all()
    ):
        raise AssertionError("frozen cross-venue mapping parity failed")
    rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        selected = work.loc[work["ticker"].eq(ticker)]
        selected_valid = selected.loc[selected["mapped_feature_valid"].astype(bool)]
        rows.append(
            {
                "ticker": ticker,
                "sensor_ticker": SENSOR_MAP[ticker],
                "rows": int(len(selected)),
                "valid_rows": int(len(selected_valid)),
                "maximum_abs_pressure_difference": float(
                    (
                        pd.to_numeric(selected_valid["signal_pressure"])
                        - pd.to_numeric(selected_valid["sensor_pressure_expected"])
                    )
                    .abs()
                    .max()
                )
                if len(selected_valid)
                else 0.0,
                "action_mismatches": 0,
            }
        )
    return pd.DataFrame(rows)


def rehash_source_inventory(inventory: pd.DataFrame, workers: int) -> pd.DataFrame:
    required = {"path", "size_bytes", "sha256", "ticker", "trade_date", "kind"}
    missing = sorted(required.difference(inventory.columns))
    if missing:
        raise KeyError(f"source inventory lacks fields: {missing}")
    output = inventory.copy()
    output["path"] = output["path"].astype(str)
    output["size_bytes"] = pd.to_numeric(output["size_bytes"], errors="raise").astype(
        np.int64
    )
    output["sha256"] = output["sha256"].astype(str)
    if output["path"].duplicated().any():
        raise AssertionError("source inventory paths are not unique")
    audits: dict[str, dict[str, Any]] = {}

    def audit_one(path_value: str) -> dict[str, Any]:
        path = Path(path_value)
        if not path.is_file():
            raise FileNotFoundError(path)
        return {
            "actual_size_bytes": int(path.stat().st_size),
            "actual_sha256": sha256_file(path),
        }

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(audit_one, path): path for path in output["path"]}
        for future in as_completed(futures):
            audits[futures[future]] = future.result()
    output["actual_size_bytes"] = output["path"].map(
        lambda path: audits[path]["actual_size_bytes"]
    )
    output["actual_sha256"] = output["path"].map(
        lambda path: audits[path]["actual_sha256"]
    )
    output["size_match"] = output["size_bytes"].eq(output["actual_size_bytes"])
    output["hash_match"] = output["sha256"].eq(output["actual_sha256"])
    if not output["size_match"].all() or not output["hash_match"].all():
        raise AssertionError("data-gate source inventory changed")
    return output


def _canonical_compare(actual: pd.DataFrame, stored: pd.DataFrame, keys: list[str]) -> None:
    actual_ordered = actual.sort_values(keys, kind="stable").reset_index(drop=True)
    stored_ordered = stored.sort_values(keys, kind="stable").reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(actual_ordered, stored_ordered, check_dtype=False)
    except AssertionError as exc:
        raise AssertionError(f"stored data-gate table differs: {keys}") from exc


def run(
    data_gate_dir: Path,
    sidecar_root: Path,
    output_dir: Path,
    workers: int,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    if workers < 1:
        raise ValueError("workers must be positive")
    for path, label in (
        (Path(__file__).resolve(), "data-gate auditor"),
        (DATA_GATE_BUILDER, "data-gate builder"),
        (DATA_GATE_CONTRACT, "data-gate contract"),
    ):
        tracked_clean(path, label)
    manifest_path = data_gate_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = _read_json(manifest_path)
    if (
        manifest.get("schema")
        != "cross_venue_calendar_rr_leader_v1_outcome_free_data_gate"
        or manifest.get("status") != "PASS_DATA_GATE"
        or manifest.get("data_gate", {}).get("passed") is not True
        or manifest.get("outcome_accessed") is not False
        or manifest.get("underlying_outcome_clocks_read") is not False
        or manifest.get("outer_2024_opened") is not False
        or manifest.get("outer_2025_opened") is not False
        or manifest.get("holdout_2026_opened") is not False
        or manifest.get("production_modified") is not False
        or int(manifest.get("rows", -1)) != EXPECTED_SESSIONS
        or int(manifest.get("scope", {}).get("captures", -1)) != EXPECTED_CAPTURES
    ):
        raise AssertionError("data gate is not an outcome-free PASS")
    for name in OUTPUT_FILES:
        path = data_gate_dir / name
        expected = manifest.get("output_sha256", {}).get(name)
        if not path.is_file() or not isinstance(expected, str) or sha256_file(path) != expected:
            raise AssertionError(f"data-gate output hash mismatch: {name}")
    _, seal, sealed_index = validate_full_capture_seal(sidecar_root)
    if (
        sha256_file(sidecar_root / "_seal/seal.json")
        != manifest.get("full_capture_seal_sha256")
        or sha256_file(sidecar_root / "_seal/capture_index.csv")
        != manifest.get("full_capture_index_sha256")
    ):
        raise AssertionError("data gate no longer points to the full capture seal")

    features = pd.read_parquet(data_gate_dir / "cross_venue_calendar_rr_features.parquet")
    assert_outcome_free_schema(features)
    mapping = verify_mapping_parity(features)
    coverage, distinctness, monthly, gate = evaluate_data_gate(features)
    if gate != manifest.get("data_gate"):
        raise AssertionError("independently recomputed data gate differs from manifest")
    _canonical_compare(
        coverage,
        pd.read_csv(data_gate_dir / "coverage.csv", dtype={"year": str}),
        ["ticker", "year"],
    )
    _canonical_compare(
        distinctness,
        pd.read_csv(data_gate_dir / "distinctness.csv", dtype={"year": str}),
        ["ticker", "year"],
    )
    _canonical_compare(
        monthly,
        pd.read_csv(data_gate_dir / "monthly_capacity.csv", dtype={"month": str}),
        ["ticker", "month"],
    )
    capture_revalidation = pd.read_csv(data_gate_dir / "capture_revalidation.csv")
    expected_columns = list(sealed_index.columns)
    if sorted(capture_revalidation.columns) != sorted(expected_columns):
        raise AssertionError("data-gate capture revalidation schema changed")
    capture_revalidation = capture_revalidation.loc[:, expected_columns].copy()
    for column in expected_columns:
        if pd.api.types.is_integer_dtype(sealed_index[column]):
            capture_revalidation[column] = pd.to_numeric(
                capture_revalidation[column], errors="raise"
            ).astype(np.int64)
        else:
            capture_revalidation[column] = capture_revalidation[column].astype(str)
    capture_revalidation = capture_revalidation.sort_values(
        ["ticker", "trade_date", "role"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(capture_revalidation) != EXPECTED_CAPTURES
        or capture_revalidation["capture_id"].duplicated().any()
    ):
        raise AssertionError("data-gate capture revalidation is incomplete")
    try:
        pd.testing.assert_frame_equal(
            capture_revalidation, sealed_index, check_dtype=True
        )
    except AssertionError as exc:
        raise AssertionError(
            "data-gate capture revalidation differs from sealed index"
        ) from exc
    inventory = pd.read_csv(
        data_gate_dir / "source_inventory.csv",
        dtype={"trade_date": str, "sha256": str},
    )
    expected_inventory_rows = EXPECTED_SESSIONS + EXPECTED_CAPTURES * 5
    if (
        len(inventory) != expected_inventory_rows
        or len(inventory) != int(manifest.get("source_inventory_rows", -1))
    ):
        raise AssertionError("source inventory row count differs from manifest")
    source_audit = rehash_source_inventory(inventory, workers)
    feature_digest = dataframe_digest(
        features.drop(columns=["local_invalid_reason", "mapped_invalid_reason"])
    )
    if feature_digest != manifest.get("feature_view_sha256"):
        raise AssertionError("feature-view canonical digest changed")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        coverage.to_csv(staging / "coverage_recomputed.csv", index=False)
        distinctness.to_csv(staging / "distinctness_recomputed.csv", index=False)
        monthly.to_csv(staging / "monthly_recomputed.csv", index=False)
        mapping.to_csv(staging / "mapping_parity.csv", index=False)
        shutil.copyfile(manifest_path, staging / "data_gate_manifest.json")
        output_names = (
            "coverage_recomputed.csv",
            "distinctness_recomputed.csv",
            "monthly_recomputed.csv",
            "mapping_parity.csv",
            "data_gate_manifest.json",
        )
        summary = {
            "schema": "cross_venue_calendar_rr_leader_v1_data_gate_audit_v1",
            "status": "PASS_INDEPENDENT_DATA_GATE_AUDIT",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "audit_commit": current_git_commit(),
            "data_gate_commit": manifest["git_commit"],
            "capture_seal_created_at_utc": seal["created_at_utc"],
            "rows": int(len(features)),
            "captures": int(len(capture_revalidation)),
            "source_inventory_rows": int(len(source_audit)),
            "source_hash_mismatches": int((~source_audit["hash_match"]).sum()),
            "source_size_mismatches": int((~source_audit["size_match"]).sum()),
            "mapping_parity_pass": True,
            "data_gate": gate,
            "feature_view_sha256": feature_digest,
            "mapping_parity_sha256": dataframe_digest(mapping),
            "source_inventory_audit_sha256": dataframe_digest(source_audit),
            "data_gate_manifest_sha256": sha256_file(manifest_path),
            "auditor_sha256": sha256_file(Path(__file__).resolve()),
            "output_sha256": {
                name: sha256_file(staging / name) for name in output_names
            },
            "outcome_accessed": False,
            "underlying_values_read": False,
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
    parser.add_argument("--data-gate-dir", type=Path, default=DEFAULT_DATA_GATE_DIR)
    parser.add_argument("--sidecar-root", type=Path, default=DEFAULT_SIDECAR_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(
        args.data_gate_dir.resolve(),
        args.sidecar_root.resolve(),
        args.output_dir.resolve(),
        args.workers,
    )
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
