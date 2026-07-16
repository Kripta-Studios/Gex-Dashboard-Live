#!/usr/bin/env python3
"""Freeze calendar-RR before its single 2023 outcome read."""

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

from neural.jepa import evaluate_calendar_risk_reversal_pressure_v1 as evaluate  # noqa: E402


PROJECT_ROOT = SCRIPT_REPO_ROOT
CODE_CLOSURE = (
    Path("neural/jepa/evaluate_calendar_risk_reversal_pressure_v1.py"),
    Path("neural/jepa/freeze_calendar_risk_reversal_pressure_v1_runner.py"),
    Path("research_papers/JEPA/CALENDAR_RISK_REVERSAL_PRESSURE_V1_PREDECLARATION.md"),
    Path("research_papers/JEPA/CALENDAR_RISK_REVERSAL_PRESSURE_V1_DATA_GATE_RESULT.md"),
)


def build_payload() -> dict[str, Any]:
    for relative in CODE_CLOSURE:
        evaluate.tracked_clean(PROJECT_ROOT / relative, "runner code/protocol")
    for name in evaluate.EXPECTED_DATA_GATE_HASHES:
        evaluate.tracked_clean(evaluate.DATA_GATE_DIR / name, "data-gate input")
    features, inventory, manifest = evaluate.validate_data_gate()
    return {
        "schema": "calendar_risk_reversal_pressure_v1_frozen_development_runner",
        "status": "PREEXECUTION_FROZEN",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner_commit": evaluate.current_git_commit(),
        "phase": "development_2023",
        "scope": {
            "start_date": evaluate.DEVELOPMENT_START,
            "end_date": evaluate.DEVELOPMENT_END,
            "tickers": list(evaluate.TICKERS),
            "eligible_events": int(len(features)),
            "underlying_sources": int(len(inventory)),
            "excluded_half_days": sorted(evaluate.HALF_DAYS),
        },
        "policy": evaluate.POLICY,
        "gate_spec": evaluate.GATE_SPEC,
        "code_hashes": {
            relative.as_posix(): evaluate.sha256_file(PROJECT_ROOT / relative)
            for relative in CODE_CLOSURE
        },
        "data_gate_inputs": {
            name: {
                "path": (evaluate.DATA_GATE_DIR / name).relative_to(PROJECT_ROOT).as_posix(),
                "sha256": evaluate.sha256_file(evaluate.DATA_GATE_DIR / name),
            }
            for name in evaluate.EXPECTED_DATA_GATE_HASHES
        },
        "data_gate_source_commit": manifest["git_commit"],
        "outcome_accessed": False,
        "execution_started": False,
        "outer_2024_2025_opened": False,
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
    temporary.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, output)
    print(json.dumps(payload, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
