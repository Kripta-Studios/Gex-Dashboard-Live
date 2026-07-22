#!/usr/bin/env python3
"""Independently audit cross-venue monthly-orientation V3 development."""

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

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v3 as evaluate  # noqa: E402


PROJECT_ROOT = SCRIPT_REPO_ROOT
DEFAULT_INPUT = evaluate.DEFAULT_OUTPUT
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "tmp/cross_venue_calendar_rr_leader_v3_development_2024_v1_audit"
)
OUTPUT_HASH_FILES = (
    "monthly_orientation_states.csv",
    "trades.csv",
    "monthly_metrics.csv",
    "ticker_summary.csv",
    "cost_sensitivity.csv",
)
REQUIRED_FILES = (*OUTPUT_HASH_FILES, "SUMMARY.json", "SUMMARY.md")


def validate_output_hashes(summary: dict[str, Any], input_dir: Path) -> None:
    expected = summary.get("output_sha256")
    if not isinstance(expected, dict) or set(expected) != set(OUTPUT_HASH_FILES):
        raise AssertionError("V3 audit output hash closure changed")
    for name in OUTPUT_HASH_FILES:
        if expected[name] != evaluate.sha256_file(input_dir / name):
            raise AssertionError(f"V3 audit output hash mismatch: {name}")


def _compare(
    recomputed: pd.DataFrame, stored: pd.DataFrame, keys: list[str], label: str
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
        raise AssertionError(f"V3 stored {label} differs from audit") from exc


def run(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V3 audit output exists: {output_dir}")
    evaluate.tracked_clean(Path(__file__).resolve(), "V3 independent auditor")
    for name in REQUIRED_FILES:
        if not (input_dir / name).is_file():
            raise FileNotFoundError(input_dir / name)
    summary = json.loads((input_dir / "SUMMARY.json").read_text(encoding="utf-8"))
    if (
        summary.get("schema")
        != "cross_venue_calendar_rr_leader_v3_development_2024_v1"
        or summary.get("status")
        != "PASS_DEVELOPMENT_INCREMENTAL_2025_NOT_FROZEN"
        or summary.get("advance_to_2025_freeze") is not True
        or summary.get("objective_gate_pass") is not False
        or summary.get("outer_2025_opened") is not False
        or summary.get("holdout_2026_opened") is not False
        or summary.get("production_modified") is not False
        or summary.get("mapping") != evaluate.SENSOR_MAP
        or summary.get("evaluator_sha256")
        != evaluate.sha256_file(Path(evaluate.__file__).resolve())
    ):
        raise AssertionError("V3 audit summary contract changed")
    validate_output_hashes(summary, input_dir)

    history_2023 = evaluate.load_2023_mapped_history()
    history_2024 = evaluate.load_2024_history()
    history = pd.concat([history_2023, history_2024], ignore_index=True)
    states = evaluate.build_monthly_states(history)
    ledger = evaluate.build_ledger(history_2024, states)
    monthly = evaluate.summarize_monthly(ledger)
    tickers = evaluate.summarize_tickers(ledger, monthly)
    sensitivity = evaluate.summarize_sensitivity(ledger)
    _compare(
        states,
        pd.read_csv(input_dir / "monthly_orientation_states.csv", dtype={"month": str, "prior_month": str}),
        ["month"],
        "orientation states",
    )
    _compare(
        ledger,
        pd.read_csv(input_dir / "trades.csv", dtype={"trade_date": str, "month": str}),
        ["ticker", "trade_date"],
        "trades",
    )
    _compare(
        monthly,
        pd.read_csv(input_dir / "monthly_metrics.csv", dtype={"month": str}),
        ["ticker", "month"],
        "monthly metrics",
    )
    _compare(
        tickers,
        pd.read_csv(input_dir / "ticker_summary.csv"),
        ["ticker"],
        "ticker summary",
    )
    _compare(
        sensitivity,
        pd.read_csv(input_dir / "cost_sensitivity.csv"),
        ["scope", "cost_bps"],
        "cost sensitivity",
    )
    if (
        not tickers["incremental_gate_pass"].all()
        or tickers["objective_gate_pass"].any()
        or states["orientation"].tolist() != [1, 1, *([-1] * 10)]
    ):
        raise AssertionError("V3 independently recomputed gates/state changed")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        states.to_csv(staging / "states_recomputed.csv", index=False)
        tickers.to_csv(staging / "ticker_summary_recomputed.csv", index=False)
        sensitivity.to_csv(staging / "cost_sensitivity_recomputed.csv", index=False)
        output_names = (
            "states_recomputed.csv",
            "ticker_summary_recomputed.csv",
            "cost_sensitivity_recomputed.csv",
        )
        audit = {
            "schema": "cross_venue_calendar_rr_leader_v3_development_audit_v1",
            "status": "PASS_INDEPENDENT_V3_DEVELOPMENT_AUDIT",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "evaluation_commit": summary["execution_commit"],
            "audit_commit": evaluate.current_git_commit(),
            "development_trades": int(len(ledger)),
            "orientation_states": int(len(states)),
            "incremental_gate_pass": True,
            "objective_gate_pass": False,
            "advance_to_2025_freeze": True,
            "outer_2025_opened": False,
            "holdout_2026_opened": False,
            "production_modified": False,
            "evaluation_summary_sha256": evaluate.sha256_file(input_dir / "SUMMARY.json"),
            "states_recomputed_sha256": evaluate.dataframe_digest(states),
            "trades_recomputed_sha256": evaluate.dataframe_digest(ledger),
            "monthly_recomputed_sha256": evaluate.dataframe_digest(monthly),
            "ticker_summary_recomputed_sha256": evaluate.dataframe_digest(tickers),
            "cost_sensitivity_recomputed_sha256": evaluate.dataframe_digest(sensitivity),
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    audit = run(args.input_dir.resolve(), args.output_dir.resolve())
    print(json.dumps(audit, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
