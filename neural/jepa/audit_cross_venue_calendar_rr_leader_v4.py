#!/usr/bin/env python3
"""Independently audit cross-venue V4 post-outcome development 2025."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v4 as evaluate  # noqa: E402
from neural.jepa.build_calendar_risk_reversal_pressure_v1 import (  # noqa: E402
    tracked_clean,
)


PROJECT_ROOT = SCRIPT_REPO_ROOT
DEFAULT_INPUT = evaluate.DEFAULT_OUTPUT
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v4_development_2025_v1_audit"
)
OUTPUT_HASH_FILES = (
    "development_dataset.parquet",
    "source_audit.csv",
    "trades.csv",
    "monthly_metrics.csv",
    "ticker_summary.csv",
    "cost_sensitivity.csv",
    "model.json",
    "SUMMARY.md",
)
REQUIRED_FILES = (*OUTPUT_HASH_FILES, "SUMMARY.json")


def validate_output_hashes(summary: dict[str, Any], input_dir: Path) -> None:
    expected = summary.get("output_sha256")
    if not isinstance(expected, dict) or set(expected) != set(OUTPUT_HASH_FILES):
        raise AssertionError("V4 audit output hash closure changed")
    for name in OUTPUT_HASH_FILES:
        if expected[name] != evaluate.sha256_file(input_dir / name):
            raise AssertionError(f"V4 output hash mismatch: {name}")


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
    except AssertionError as exc:
        raise AssertionError(f"V4 stored {label} differs from audit") from exc


def run(input_dir: Path, output_dir: Path, workers: int) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V4 audit output exists: {output_dir}")
    tracked_clean(Path(__file__).resolve(), "V4 independent auditor")
    for name in REQUIRED_FILES:
        if not (input_dir / name).is_file():
            raise FileNotFoundError(input_dir / name)
    summary = json.loads((input_dir / "SUMMARY.json").read_text(encoding="utf-8"))
    if (
        summary.get("schema")
        != "cross_venue_calendar_rr_leader_v4_development_2025_v1"
        or summary.get("status")
        != "PASS_INCREMENTAL_DEVELOPMENT_2026_DATA_NOT_OPENED"
        or summary.get("incremental_gate_pass") is not True
        or summary.get("objective_gate_pass") is not False
        or summary.get("advance_to_2026_data_gate") is not True
        or summary.get("development_2025_post_outcome") is not True
        or summary.get("features_2026_opened") is not False
        or summary.get("outcomes_2026_opened") is not False
        or summary.get("production_modified") is not False
        or summary.get("live_or_systemd_modified") is not False
        or summary.get("input_sha256")
        != {
            str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): expected
            for path, expected in evaluate.INPUT_HASHES.items()
        }
    ):
        raise AssertionError("V4 audit summary contract changed")
    validate_output_hashes(summary, input_dir)

    training = evaluate.load_training()
    development = evaluate.load_development_rows()
    inventory = evaluate.load_underlying_inventory_2025()
    cache, source_audit = evaluate.load_cash_cache(development, inventory, workers)
    development = evaluate.v2.attach_cash_features(development, cache)
    model = evaluate.v2.make_model()
    model.fit(training[list(evaluate.FEATURE_COLUMNS)], training["direct_win"])
    probabilities = model.predict_proba(
        development[list(evaluate.FEATURE_COLUMNS)]
    )[:, 1]
    ledger = evaluate.make_ledger(development, probabilities)
    monthly = evaluate.summarize_monthly(ledger)
    tickers = evaluate.summarize_tickers(ledger, monthly)
    sensitivity = evaluate.summarize_sensitivity(ledger)
    dataset_columns = [
        "ticker",
        "trade_date",
        "month",
        "sensor_ticker",
        *evaluate.FEATURE_COLUMNS,
        "base_side",
        "underlying_return_bps",
        "base_gross_bps",
        "direct_win",
    ]
    compare_frames(
        development[dataset_columns],
        pd.read_parquet(input_dir / "development_dataset.parquet"),
        ["ticker", "trade_date"],
        "development dataset",
    )
    compare_frames(
        source_audit,
        pd.read_csv(input_dir / "source_audit.csv", dtype={"trade_date": str}),
        ["ticker", "trade_date"],
        "source audit",
    )
    compare_frames(
        ledger,
        pd.read_csv(
            input_dir / "trades.csv", dtype={"trade_date": str, "month": str}
        ),
        ["ticker", "trade_date"],
        "trades",
    )
    compare_frames(
        monthly,
        pd.read_csv(input_dir / "monthly_metrics.csv", dtype={"month": str}),
        ["ticker", "month"],
        "monthly metrics",
    )
    compare_frames(
        tickers,
        pd.read_csv(input_dir / "ticker_summary.csv"),
        ["ticker"],
        "ticker summary",
    )
    compare_frames(
        sensitivity,
        pd.read_csv(input_dir / "cost_sensitivity.csv"),
        ["scope", "cost_bps"],
        "cost sensitivity",
    )
    stored_model = json.loads((input_dir / "model.json").read_text(encoding="utf-8"))
    if stored_model != evaluate.serialize_model(model, training):
        raise AssertionError("V4 stored model differs from independent refit")
    expected_pf = {"QQQ": 1.204351428046685, "SPXW": 1.2479453537482896, "SPY": 1.3463415562391026}
    actual_pf = tickers.set_index("ticker")["profit_factor"].to_dict()
    if (
        not tickers["incremental_gate_pass"].all()
        or tickers["objective_gate_pass"].any()
        or tickers.set_index("ticker")["positive_months"].to_dict()
        != {"QQQ": 7, "SPXW": 8, "SPY": 8}
        or any(abs(actual_pf[ticker] - value) > 1e-12 for ticker, value in expected_pf.items())
        or int(len(source_audit)) != 738
    ):
        raise AssertionError("V4 independently recomputed checkpoint changed")
    digest_checks = {
        "dataset_recomputed_sha256": evaluate.dataframe_digest(
            development[dataset_columns]
        ),
        "trades_recomputed_sha256": evaluate.dataframe_digest(ledger),
        "monthly_recomputed_sha256": evaluate.dataframe_digest(monthly),
        "ticker_summary_recomputed_sha256": evaluate.dataframe_digest(tickers),
        "cost_sensitivity_recomputed_sha256": evaluate.dataframe_digest(sensitivity),
    }
    if any(summary.get(field) != value for field, value in digest_checks.items()):
        raise AssertionError("V4 summary semantic digest changed")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        tickers.to_csv(staging / "ticker_summary_recomputed.csv", index=False)
        sensitivity.to_csv(staging / "cost_sensitivity_recomputed.csv", index=False)
        names = ("ticker_summary_recomputed.csv", "cost_sensitivity_recomputed.csv")
        audit = {
            "schema": "cross_venue_calendar_rr_leader_v4_development_audit_v1",
            "status": "PASS_INDEPENDENT_V4_DEVELOPMENT_AUDIT",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "evaluation_commit": summary["execution_commit"],
            "audit_commit": evaluate.current_git_commit(),
            "training_rows": int(len(training)),
            "development_rows": int(len(development)),
            "source_files_rehashed": int(len(source_audit)),
            "source_mismatches": 0,
            "model_refit_exact": True,
            "incremental_gate_pass": True,
            "objective_gate_pass": False,
            "advance_to_2026_data_gate": True,
            "features_2026_opened": False,
            "outcomes_2026_opened": False,
            "production_modified": False,
            "live_or_systemd_modified": False,
            "evaluation_summary_sha256": evaluate.sha256_file(
                input_dir / "SUMMARY.json"
            ),
            **digest_checks,
            "output_sha256": {
                name: evaluate.sha256_file(staging / name) for name in names
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
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 1 <= args.workers <= 16:
        raise ValueError("workers must be in [1, 16]")
    audit = run(args.input_dir.resolve(), args.output_dir.resolve(), args.workers)
    print(json.dumps(audit, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
