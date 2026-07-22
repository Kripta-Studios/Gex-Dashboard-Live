#!/usr/bin/env python3
"""Freeze the sequential cross-venue V3 outer-2025 runner before outcomes."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v3_outer_2025 as outer  # noqa: E402


PROJECT_ROOT = SCRIPT_REPO_ROOT
DEFAULT_OUTPUT = outer.DEFAULT_FROZEN_MANIFEST


def tracked_worktree_clean() -> None:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if completed.stdout.strip():
        raise AssertionError("V3 freezer requires a clean tracked worktree")


def run(output_path: Path) -> dict[str, object]:
    output_dir = output_path.parent
    if output_dir.exists():
        raise FileExistsError(f"immutable V3 frozen output exists: {output_dir}")
    tracked_worktree_clean()
    outer.validate_frozen_inputs()
    features, events = outer.load_2025_inputs()
    initial = outer.initial_state_from_development()
    event_ids = [f"{row.ticker}|{row.trade_date}" for row in events.itertuples()]
    code_hashes = {
        relative.as_posix(): outer.sha256_file(PROJECT_ROOT / relative)
        for relative in outer.RUNNER_CODE_PATHS
    }
    monthly_counts = (
        features.groupby(["ticker", "month"], observed=True)
        .size()
        .rename("events")
        .reset_index()
    )
    payload: dict[str, object] = {
        "schema": "cross_venue_calendar_rr_leader_v3_outer_2025_frozen_runner",
        "status": "PREEXECUTION_FROZEN",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner_commit": outer.current_git_commit(),
        "year": outer.OUTER_YEAR,
        "mapping": outer.SENSOR_MAP,
        "rule": {
            "state_source": "immediately_previous_calendar_month",
            "statistic": "pooled_physical_trade_direct_hit_rate",
            "threshold": 0.5,
            "tie": "DIRECT",
            "zero_pressure": "NO_TRADE",
            "state_constant_within_month": True,
        },
        "economics": {
            "entry": "open_10:36:00",
            "exit": "open_13:36:00",
            "hold_minutes": 180,
            "primary_cost_bps": 1.0,
            "sensitivity_costs_bps": list(outer.COSTS_BPS),
            "positions_per_ticker_day": 1,
            "overlap": False,
        },
        "objective_gate": {
            "profit_factor_strictly_greater_than": 1.20,
            "win_rate_strictly_greater_than": 0.45,
            "trades_per_month_strictly_greater_than": 12,
            "monthly_net_bps_strictly_greater_than": 0.0,
            "all_tickers_required": True,
        },
        "data_gate_hashes": outer.DATA_GATE_HASHES,
        "development_hashes": {
            str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): expected
            for path, expected in outer.DEVELOPMENT_HASHES.items()
        },
        "code_hashes": code_hashes,
        "initial_state": initial,
        "events": int(len(events)),
        "event_id_sha256": outer.ordered_hash(event_ids),
        "source_inventory_sha256": outer.dataframe_digest(events),
        "monthly_counts": monthly_counts.to_dict(orient="records"),
        "outcome_accessed": False,
        "execution_started": False,
        "outer_2025_opened": False,
        "holdout_2026_opened": False,
        "production_modified": False,
        "live_or_systemd_modified": False,
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        (staging / output_path.name).write_text(
            json.dumps(payload, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run(args.output.resolve())
    print(json.dumps(payload, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
