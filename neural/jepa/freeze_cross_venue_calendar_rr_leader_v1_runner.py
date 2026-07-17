#!/usr/bin/env python3
"""Freeze CROSS_VENUE_CALENDAR_RR_LEADER_V1 before its one-shot 2024 read."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v1 as evaluate  # noqa: E402


PROJECT_ROOT = SCRIPT_REPO_ROOT


def build_payload() -> dict[str, Any]:
    for relative in evaluate.RUNNER_CODE_PATHS:
        evaluate.tracked_clean(PROJECT_ROOT / relative, "runner code/protocol")
    for name in evaluate.DATA_GATE_FILES:
        evaluate.tracked_clean(evaluate.DATA_GATE_DIR / name, "data-gate input")
    features, inventory, manifest = evaluate.validate_data_gate()
    event_ids = [f"{row.ticker}|{row.trade_date}" for row in features.itertuples()]
    monthly = (
        features.groupby(["ticker", "month"], observed=True)
        .size()
        .rename("events")
        .reset_index()
    )
    return {
        "schema": "cross_venue_calendar_rr_leader_v1_frozen_outer_2024_runner",
        "status": "PREEXECUTION_FROZEN",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner_commit": evaluate.current_git_commit(),
        "phase": "outer_2024",
        "scope": {
            "start_date": evaluate.OUTER_START,
            "end_date": evaluate.OUTER_END,
            "tickers": list(evaluate.TICKERS),
            "eligible_events": int(len(features)),
            "underlying_sources": int(len(inventory)),
            "excluded_half_days": sorted(evaluate.HALF_DAYS),
            "monthly_counts": monthly.to_dict(orient="records"),
        },
        "event_id_sha256": evaluate.ordered_hash(event_ids),
        "policy": evaluate.POLICY,
        "incremental_gate_spec": evaluate.INCREMENTAL_GATE_SPEC,
        "promotion_gate_spec": evaluate.PROMOTION_GATE_SPEC,
        "code_hashes": {
            relative.as_posix(): evaluate.sha256_file(PROJECT_ROOT / relative)
            for relative in evaluate.RUNNER_CODE_PATHS
        },
        "data_gate_inputs": {
            name: {
                "path": (evaluate.DATA_GATE_DIR / name)
                .relative_to(PROJECT_ROOT)
                .as_posix(),
                "sha256": evaluate.sha256_file(evaluate.DATA_GATE_DIR / name),
            }
            for name in evaluate.DATA_GATE_FILES
        },
        "data_gate_source_commit": manifest["git_commit"],
        "outcome_accessed": False,
        "execution_started": False,
        "outer_2024_opened": False,
        "outer_2025_opened": False,
        "holdout_2026_opened": False,
        "production_modified": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=evaluate.DEFAULT_FROZEN_MANIFEST)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    output = parse_args(argv).output.resolve()
    if output.exists():
        raise FileExistsError(f"frozen manifest already exists: {output}")
    payload = build_payload()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, output)
    print(json.dumps(payload, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
