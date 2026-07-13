"""Freeze the one-shot H-IBQDYN1 executable-quote economic translation."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from neural.jepa.build_wall_quote_tick_dynamics_sidecar import sha256_file
from neural.jepa.evaluate_h_ibqdyn1_economic import (
    CODE_CLOSURE,
    GATES,
    PROJECT_ROOT,
    verify_build_summary,
)


def tracked_clean(path: Path, label: str) -> None:
    relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    subprocess.run(["git", "ls-files", "--error-unmatch", relative], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "--", relative], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True).stdout.strip()
    if dirty:
        raise AssertionError(f"{label} must be committed and clean: {dirty}")


def build_payload(inputs: dict[str, Path], physical_dir: Path) -> dict:
    for name in ("physical_manifest", "physical_summary", "physical_model_hashes"):
        tracked_clean(inputs[name], name)
    for relative in CODE_CLOSURE:
        tracked_clean(PROJECT_ROOT / relative, "economic code/protocol")
    verify_build_summary(inputs["event_build_summary"])
    physical = json.loads(inputs["physical_manifest"].read_text(encoding="utf-8"))
    summary = json.loads(inputs["physical_summary"].read_text(encoding="utf-8"))
    if (
        physical.get("schema") != "h_ibqdyn1_physical_evaluation_v1"
        or physical.get("summary", {}).get("physical_mechanism_pass") is not True
        or physical.get("summary", {}).get("research_payoff_authorized") is not True
        or summary.get("physical_mechanism_pass") is not True
        or summary.get("research_payoff_authorized") is not True
        or physical.get("holdout_2026_used") is not False
        or physical.get("production_modified") is not False
    ):
        raise AssertionError("cannot freeze economic runner without physical PASS")
    model_hashes = pd.read_csv(inputs["physical_model_hashes"])
    for year in ("2024", "2025"):
        for ticker in ("SPXW", "QQQ", "SPY"):
            cell = f"lr_{year}_{ticker}_60m"
            match = model_hashes[
                model_hashes["cell_id"].astype(str).eq(cell)
                & model_hashes["family"].astype(str).eq("lr")
                & model_hashes["arm"].astype(str).eq("F1")
            ]
            if len(match) != 1:
                raise AssertionError(f"missing economic source model {cell}")
            row = match.iloc[0]
            if sha256_file(physical_dir / str(row["path"])) != str(row["sha256"]):
                raise AssertionError(f"economic source model hash mismatch {cell}")
    return {
        "schema": "h_ibqdyn1_frozen_economic_runner_v1",
        "status": "PREEXECUTION_FROZEN",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True).stdout.strip(),
        "code_hashes": {relative: sha256_file(PROJECT_ROOT / relative) for relative in CODE_CLOSURE},
        "inputs": {name: {"path": str(path), "sha256": sha256_file(path)} for name, path in inputs.items()},
        "policy": {"physical_family": "lr", "physical_arm": "F1", "horizon_minutes": 60, "decision_boundary": 0.5, "scheduler": "chronological_reject_while_open"},
        "execution": {"entry": "ask", "exit": "bid", "stop_pct": -0.60, "take_profit_pct": 10.0, "trail_activation_pct": 0.50, "trail_drawdown_pct": 0.25, "minimum_hold_minutes": 30, "maximum_hold_minutes": 180},
        "gate_spec": GATES,
        "holdout_2026_opened": False,
        "production_modified": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--event-build-summary", required=True)
    parser.add_argument("--physical-dir", required=True)
    parser.add_argument("--physical-manifest", required=True)
    parser.add_argument("--physical-summary", required=True)
    parser.add_argument("--physical-model-hashes", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError("economic frozen manifest exists")
    inputs = {name: Path(getattr(args, name)) for name in ("dataset", "events", "event_build_summary", "physical_manifest", "physical_summary", "physical_model_hashes")}
    payload = build_payload(inputs, Path(args.physical_dir))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
