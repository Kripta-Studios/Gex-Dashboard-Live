#!/usr/bin/env python3
"""Freeze the final V4R2 model, predictions, events, and sources before outcomes."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa import (  # noqa: E402
    cross_venue_calendar_rr_leader_v4r2_2026_outer_common as common,
)
from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v2 as v2  # noqa: E402


DEFAULT_OUTPUT = common.FROZEN_MANIFEST


def build_frozen_components() -> tuple[pd.DataFrame, dict[str, object]]:
    common.validate_frozen_inputs()
    training = common.load_final_training()
    features = common.load_feature_view()
    events = common.load_event_sources(features)
    model = v2.make_model()
    model.fit(training[list(common.FEATURE_COLUMNS)], training["direct_win"])
    probabilities = model.predict_proba(events[list(common.FEATURE_COLUMNS)])[:, 1]
    events["base_side"] = np.sign(events["signal_pressure"]).astype(np.int64)
    events["direct_probability"] = probabilities
    events["orientation"] = np.where(probabilities >= 0.5, 1, -1).astype(np.int64)
    events["side"] = events["base_side"] * events["orientation"]
    columns = [
        "ticker",
        "trade_date",
        "month",
        "sensor_ticker",
        *common.FEATURE_COLUMNS,
        "base_side",
        "direct_probability",
        "orientation",
        "side",
        "source_path",
        "source_size_bytes",
        "source_sha256",
    ]
    events = events[columns].sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(events) != 394
        or not events["base_side"].isin([-1, 1]).all()
        or not events["orientation"].isin([-1, 1]).all()
        or not events["side"].isin([-1, 1]).all()
        or not np.isfinite(events["direct_probability"]).all()
    ):
        raise AssertionError("V4R2 frozen event predictions changed")
    return events, common.serialize_model(model, training)


def run(output_path: Path) -> dict[str, object]:
    output_dir = output_path.parent
    if output_dir.exists():
        raise FileExistsError(f"immutable V4R2 frozen output exists: {output_dir}")
    common.tracked_worktree_clean()
    events, model_payload = build_frozen_components()
    event_ids = [f"{row.ticker}|{row.trade_date}" for row in events.itertuples()]
    monthly_counts = (
        events.groupby(["ticker", "month"], observed=True)
        .size()
        .rename("events")
        .reset_index()
    )
    code_hashes = {
        relative.as_posix(): common.sha256_file(common.PROJECT_ROOT / relative)
        for relative in common.RUNNER_CODE_PATHS
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        events.to_parquet(staging / "events.parquet", index=False)
        (staging / "model.json").write_text(
            json.dumps(model_payload, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        manifest: dict[str, object] = {
            "schema": "cross_venue_calendar_rr_leader_v4r2_outer_2026_frozen_v1",
            "status": "PREEXECUTION_FROZEN",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "runner_commit": common.current_git_commit(),
            "mapping": common.SENSOR_MAP,
            "model": {
                "family": "pooled_logistic_l2",
                "train_rows": 2_217,
                "train_period": "2023-01-01..2025-12-31",
                "C": 0.1,
                "threshold": 0.5,
                "refit_during_2026": False,
            },
            "economics": {
                "entry": "open_10:36:00",
                "exit": "open_13:36:00",
                "hold_minutes": 180,
                "primary_cost_bps": 1.0,
                "sensitivity_costs_bps": list(common.COSTS_BPS),
                "positions_per_ticker_day": 1,
                "overlap": False,
            },
            "objective_gate": {
                "closed_months": list(common.CLOSED_MONTHS),
                "profit_factor_strictly_greater_than": 1.20,
                "win_rate_strictly_greater_than": 0.45,
                "net_bps_strictly_greater_than": 0.0,
                "minimum_trades_per_closed_month": 13,
                "all_closed_months_positive": True,
                "july_mtd_net_positive": True,
                "all_tickers_required": True,
            },
            "input_hashes": {
                str(path.relative_to(common.PROJECT_ROOT)).replace("\\", "/"): value
                for path, value in common.INPUT_HASHES.items()
            },
            "code_hashes": code_hashes,
            "events": int(len(events)),
            "event_id_sha256": common.ordered_hash(event_ids),
            "events_recomputed_sha256": common.dataframe_digest(events),
            "monthly_counts": monthly_counts.to_dict(orient="records"),
            "events_sha256": common.sha256_file(staging / "events.parquet"),
            "model_sha256": common.sha256_file(staging / "model.json"),
            "feature_clock_last": "10:35:00",
            "outcome_accessed": False,
            "execution_started": False,
            "open_1036_read": False,
            "open_1336_read": False,
            "outer_2026_opened": False,
            "production_modified": False,
            "live_or_systemd_modified": False,
        }
        (staging / output_path.name).write_text(
            json.dumps(manifest, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = run(args.output.resolve())
    print(json.dumps(manifest, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
