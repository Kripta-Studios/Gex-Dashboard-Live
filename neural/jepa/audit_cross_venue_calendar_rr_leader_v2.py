#!/usr/bin/env python3
"""Independently audit the completed cross-venue V2R1 development ledger."""

from __future__ import annotations

import argparse
import json
import os
import shutil
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

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v2 as evaluate  # noqa: E402


PROJECT_ROOT = SCRIPT_REPO_ROOT
DEFAULT_INPUT = evaluate.DEFAULT_OUTPUT
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "tmp/cross_venue_calendar_rr_leader_v2_development_202301_202412_v1_audit"
)
OUTPUT_HASH_FILES = (
    "development_dataset.parquet",
    "source_audit.csv",
    "trades.csv",
    "monthly_metrics.csv",
    "block_ticker_summary.csv",
    "cost_sensitivity.csv",
    "models.json",
)
REQUIRED_FILES = (*OUTPUT_HASH_FILES, "SUMMARY.json", "SUMMARY.md")


def validate_output_hashes(summary: dict[str, Any], input_dir: Path) -> None:
    expected = summary.get("output_sha256")
    if not isinstance(expected, dict) or set(expected) != set(OUTPUT_HASH_FILES):
        raise AssertionError("V2 audit output hash closure changed")
    for name in OUTPUT_HASH_FILES:
        if expected[name] != evaluate.sha256_file(input_dir / name):
            raise AssertionError(f"V2 audit output hash mismatch: {name}")


def _compare_frames(
    expected: pd.DataFrame, stored: pd.DataFrame, keys: list[str], label: str
) -> None:
    left = expected.sort_values(keys, kind="stable").reset_index(drop=True)
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
    except AssertionError as exc:
        raise AssertionError(f"V2 stored {label} differs from audit") from exc


def validate_dataset(dataset: pd.DataFrame, summary: dict[str, Any]) -> pd.DataFrame:
    required = {
        "ticker",
        "trade_date",
        "month",
        "sensor_ticker",
        *evaluate.FEATURE_COLUMNS,
        "base_side",
        "underlying_return_bps",
        "base_gross_bps",
        "direct_win",
    }
    missing = sorted(required.difference(dataset.columns))
    if missing:
        raise KeyError(f"V2 audit dataset lacks fields: {missing}")
    output = dataset.copy()
    output["trade_date"] = output["trade_date"].astype(str)
    output["month"] = output["trade_date"].str[:6]
    output["ticker"] = output["ticker"].astype(str)
    output["sensor_ticker"] = output["sensor_ticker"].astype(str)
    if (
        len(output) != 1_482
        or int(output["month"].str.startswith("2023").sum()) != 739
        or int(output["month"].str.startswith("2024").sum()) != 743
        or output["month"].str.startswith("2025").any()
        or output.duplicated(["ticker", "trade_date"]).any()
        or not output["sensor_ticker"].eq(output["ticker"].map(evaluate.SENSOR_MAP)).all()
        or not np.isfinite(output[list(evaluate.FEATURE_COLUMNS)].to_numpy()).all()
        or not output["base_side"].isin([-1, 1]).all()
        or not output["direct_win"].isin([0, 1]).all()
        or int(summary.get("train_rows_2023", -1)) != 739
        or int(summary.get("development_trades_2024", -1)) != 743
    ):
        raise AssertionError("V2 audit dataset identity failed")
    gross = output["base_side"].to_numpy(dtype=float) * output[
        "underlying_return_bps"
    ].to_numpy(dtype=float)
    if not np.allclose(
        gross,
        output["base_gross_bps"].to_numpy(dtype=float),
        rtol=0.0,
        atol=1e-12,
    ):
        raise AssertionError("V2 audit base economics changed")
    expected_win = (gross > 0.0).astype(np.int64)
    if not np.array_equal(expected_win, output["direct_win"].to_numpy(dtype=np.int64)):
        raise AssertionError("V2 audit target changed")
    return output


def recompute_models_and_trades(
    dataset: pd.DataFrame, stored_models: dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[pd.DataFrame] = []
    models: dict[str, Any] = {}
    for block, scope in evaluate.BLOCKS.items():
        train = dataset.loc[
            dataset["month"].between(scope["train_start"], scope["train_end"])
        ].copy()
        test = dataset.loc[
            dataset["month"].between(scope["test_start"], scope["test_end"])
        ].copy()
        model = evaluate.make_model()
        model.fit(train[list(evaluate.FEATURE_COLUMNS)], train["direct_win"])
        probability = model.predict_proba(test[list(evaluate.FEATURE_COLUMNS)])[:, 1]
        orientation = np.where(
            probability >= evaluate.MODEL_THRESHOLD, 1, -1
        ).astype(np.int64)
        output = test[
            [
                "ticker",
                "trade_date",
                "month",
                "sensor_ticker",
                "signal_pressure",
                "base_side",
                "underlying_return_bps",
                "base_gross_bps",
                "direct_win",
            ]
        ].copy()
        output.insert(0, "block", block)
        output["direct_probability"] = probability
        output["orientation"] = orientation
        output["side"] = output["base_side"] * orientation
        output["gross_bps"] = output["side"] * output["underlying_return_bps"]
        for cost in evaluate.COSTS_BPS:
            output[f"net_bps_{int(cost)}bp"] = output["gross_bps"] - cost
        output["net_bps"] = output["net_bps_1bp"]
        rows.append(output)
        models[block] = evaluate._serialize_model(model, block, train)
        expected_model = stored_models.get(block)
        if not isinstance(expected_model, dict):
            raise AssertionError(f"V2 stored model missing: {block}")
        for field in (
            "feature_columns",
            "train_rows",
            "train_start",
            "train_end",
            "classes",
            "n_iter",
        ):
            if models[block][field] != expected_model.get(field):
                raise AssertionError(f"V2 stored model metadata changed: {block}/{field}")
        for field in (
            "imputer_statistics",
            "scaler_mean",
            "scaler_scale",
            "coefficient",
            "intercept",
        ):
            if not np.allclose(
                models[block][field],
                expected_model.get(field),
                rtol=0.0,
                atol=1e-12,
            ):
                raise AssertionError(f"V2 stored model values changed: {block}/{field}")
    ledger = pd.concat(rows, ignore_index=True).sort_values(
        ["block", "ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    return ledger, models


def rehash_sources(source_audit: pd.DataFrame, workers: int) -> pd.DataFrame:
    required = {"ticker", "trade_date", "path", "size_bytes", "sha256"}
    missing = sorted(required.difference(source_audit.columns))
    if missing:
        raise KeyError(f"V2 source audit lacks fields: {missing}")
    output = source_audit.copy()

    def one(path_text: str) -> tuple[int, str]:
        path = Path(path_text)
        if not path.is_file():
            raise FileNotFoundError(path)
        return path.stat().st_size, evaluate.sha256_file(path)

    actual: dict[str, tuple[int, str]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(one, str(path)): str(path) for path in output["path"]}
        for future in as_completed(futures):
            actual[futures[future]] = future.result()
    output["actual_size_bytes"] = output["path"].map(lambda path: actual[str(path)][0])
    output["actual_sha256"] = output["path"].map(lambda path: actual[str(path)][1])
    output["size_match"] = output["size_bytes"].eq(output["actual_size_bytes"])
    output["hash_match"] = output["sha256"].eq(output["actual_sha256"])
    if not output["size_match"].all() or not output["hash_match"].all():
        raise AssertionError("V2 underlying source changed")
    evaluate.validate_original_invalid_census(output)
    return output


def run(input_dir: Path, output_dir: Path, workers: int) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V2 audit output exists: {output_dir}")
    if workers < 1:
        raise ValueError("workers must be positive")
    evaluate.tracked_clean(Path(__file__).resolve(), "V2 independent auditor")
    for name in REQUIRED_FILES:
        if not (input_dir / name).is_file():
            raise FileNotFoundError(input_dir / name)
    summary = json.loads((input_dir / "SUMMARY.json").read_text(encoding="utf-8"))
    if (
        summary.get("schema") != "cross_venue_calendar_rr_leader_v2_development_v1"
        or summary.get("status") != "PARTIAL_DEVELOPMENT_EDGE_2025_CLOSED"
        or summary.get("advance_to_2025_freeze") is not False
        or summary.get("outer_2025_opened") is not False
        or summary.get("holdout_2026_opened") is not False
        or summary.get("production_modified") is not False
        or summary.get("mapping") != evaluate.SENSOR_MAP
        or summary.get("feature_columns") != list(evaluate.FEATURE_COLUMNS)
        or summary.get("evaluator_sha256")
        != evaluate.sha256_file(Path(evaluate.__file__).resolve())
    ):
        raise AssertionError("V2 audit summary contract changed")
    validate_output_hashes(summary, input_dir)
    dataset = validate_dataset(
        pd.read_parquet(input_dir / "development_dataset.parquet"), summary
    )
    stored_models = json.loads((input_dir / "models.json").read_text(encoding="utf-8"))
    ledger, models = recompute_models_and_trades(dataset, stored_models)
    stored_trades = pd.read_csv(
        input_dir / "trades.csv", dtype={"trade_date": str, "month": str}
    )
    _compare_frames(ledger, stored_trades, ["block", "ticker", "trade_date"], "trades")
    monthly = evaluate.summarize_monthly(ledger)
    blocks = evaluate.summarize_blocks(ledger, monthly)
    sensitivity = evaluate.summarize_sensitivity(ledger)
    _compare_frames(
        monthly,
        pd.read_csv(input_dir / "monthly_metrics.csv", dtype={"month": str}),
        ["block", "ticker", "month"],
        "monthly metrics",
    )
    _compare_frames(
        blocks,
        pd.read_csv(input_dir / "block_ticker_summary.csv"),
        ["block", "ticker"],
        "block summary",
    )
    _compare_frames(
        sensitivity,
        pd.read_csv(input_dir / "cost_sensitivity.csv"),
        ["block", "scope", "cost_bps"],
        "cost sensitivity",
    )
    if bool(blocks["incremental_gate_pass"].all()):
        raise AssertionError("V2 audit unexpectedly advances to 2025")
    source_audit = pd.read_csv(
        input_dir / "source_audit.csv", dtype={"trade_date": str, "sha256": str}
    )
    if len(source_audit) != int(summary.get("source_rows_revalidated", -1)):
        raise AssertionError("V2 audit source count changed")
    source_rehash = rehash_sources(source_audit, workers)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        monthly.to_csv(staging / "monthly_recomputed.csv", index=False)
        blocks.to_csv(staging / "block_summary_recomputed.csv", index=False)
        sensitivity.to_csv(staging / "cost_sensitivity_recomputed.csv", index=False)
        output_names = (
            "monthly_recomputed.csv",
            "block_summary_recomputed.csv",
            "cost_sensitivity_recomputed.csv",
        )
        audit = {
            "schema": "cross_venue_calendar_rr_leader_v2_development_audit_v1",
            "status": "PASS_INDEPENDENT_V2_DEVELOPMENT_AUDIT",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "evaluation_status": summary["status"],
            "evaluation_commit": summary["execution_commit"],
            "audit_commit": evaluate.current_git_commit(),
            "development_trades": int(len(ledger)),
            "source_rows_rehashed": int(len(source_rehash)),
            "source_hash_mismatches": int((~source_rehash["hash_match"]).sum()),
            "source_size_mismatches": int((~source_rehash["size_match"]).sum()),
            "advance_to_2025_freeze": False,
            "outer_2025_opened": False,
            "holdout_2026_opened": False,
            "production_modified": False,
            "evaluation_summary_sha256": evaluate.sha256_file(input_dir / "SUMMARY.json"),
            "trades_recomputed_sha256": evaluate.dataframe_digest(ledger),
            "models_recomputed_sha256": evaluate.dataframe_digest(
                pd.DataFrame(
                    [
                        {"block": block, "payload": json.dumps(payload, sort_keys=True)}
                        for block, payload in models.items()
                    ]
                )
            ),
            "source_rehash_sha256": evaluate.dataframe_digest(source_rehash),
            "output_sha256": {
                name: evaluate.sha256_file(staging / name) for name in output_names
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
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    audit = run(args.input_dir.resolve(), args.output_dir.resolve(), args.workers)
    print(json.dumps(audit, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
