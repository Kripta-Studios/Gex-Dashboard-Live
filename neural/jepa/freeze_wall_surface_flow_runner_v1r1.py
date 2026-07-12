"""Create the immutable pre-execution manifest for wall-flow physical V1R1."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.evaluate_wall_surface_flow_at_touch_v1 import (  # noqa: E402
    ENVIRONMENT_LOCK,
    GATE_SPEC,
    LABEL_SPEC,
    MODEL_PARAMS,
    hash_list,
    model_feature_names,
    sha256_file,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def assert_code_committed_clean(path: Path) -> str:
    relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", relative],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise AssertionError(f"freeze requires committed clean code: {relative}: {dirty}")
    return relative


def evidence_payload(status: str, path_value: str | None, label: str) -> dict[str, Any] | None:
    if status != "PASS":
        if path_value:
            raise ValueError(f"{label} evidence is only accepted when status=PASS")
        return None
    if not path_value:
        raise ValueError(f"{label} status PASS requires evidence path")
    path = Path(path_value).resolve()
    relative = assert_code_committed_clean(path)
    return {"path": relative, "sha256": sha256_file(path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flow", required=True)
    parser.add_argument("--source-hashes", required=True)
    parser.add_argument("--data-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--historical-timestamp-provenance-status",
        choices=("PASS", "CONDITIONAL", "BLOCKED"),
        default="CONDITIONAL",
    )
    parser.add_argument("--timestamp-provenance-evidence")
    parser.add_argument(
        "--live-feature-parity-status",
        choices=("PASS", "BLOCKED"),
        default="BLOCKED",
    )
    parser.add_argument("--live-parity-evidence")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"frozen runner manifest already exists: {output}")
    runner = Path(__file__).with_name("evaluate_wall_surface_flow_at_touch_v1.py")
    feature_module = Path(__file__).with_name("surface_flow_features.py")
    freeze_script = Path(__file__)
    environment_module = Path(__file__).with_name("wall_surface_flow_environment.py")
    for path in (runner, feature_module, freeze_script, environment_module, ENVIRONMENT_LOCK):
        assert_code_committed_clean(path)
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    flow = Path(args.flow)
    source_hashes = Path(args.source_hashes)
    data_manifest_path = Path(args.data_manifest)
    data_manifest = json.loads(data_manifest_path.read_text(encoding="utf-8"))
    if data_manifest.get("status") != "PASS_DATA_GATE":
        raise AssertionError(f"cannot freeze failed data gate: {data_manifest.get('status')}")
    if sha256_file(flow) != str(data_manifest.get("dataset_sha256")):
        raise AssertionError("flow dataset does not match data manifest")
    if sha256_file(source_hashes) != str(data_manifest.get("source_file_hashes_sha256")):
        raise AssertionError("source hash inventory does not match data manifest")
    timestamp_evidence = evidence_payload(
        str(args.historical_timestamp_provenance_status),
        args.timestamp_provenance_evidence,
        "timestamp provenance",
    )
    live_evidence = evidence_payload(
        str(args.live_feature_parity_status),
        args.live_parity_evidence,
        "live parity",
    )
    payload: dict[str, Any] = {
        "schema": "wall_surface_flow_at_touch_frozen_runner_v1r1",
        "status": "PREEXECUTION_FROZEN",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner_commit": git_commit(),
        "runner_sha256": sha256_file(runner),
        "feature_module_sha256": sha256_file(feature_module),
        "freeze_script_sha256": sha256_file(freeze_script),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "inputs": {
            "flow_dataset": {"path": str(flow), "sha256": sha256_file(flow)},
            "source_file_hashes": {"path": str(source_hashes), "sha256": sha256_file(source_hashes)},
            "data_manifest": {"path": str(data_manifest_path), "sha256": sha256_file(data_manifest_path)},
        },
        "model_params": MODEL_PARAMS,
        "label_spec": LABEL_SPEC,
        "gate_spec": GATE_SPEC,
        "model_feature_hashes": {
            "F0": hash_list(model_feature_names("F0")),
            "F1": hash_list(model_feature_names("F1")),
        },
        "model_feature_names": {
            "F0": model_feature_names("F0"),
            "F1": model_feature_names("F1"),
        },
        "historical_timestamp_provenance_status": str(args.historical_timestamp_provenance_status),
        "live_feature_parity_status": str(args.live_feature_parity_status),
        "timestamp_provenance_evidence": timestamp_evidence,
        "live_parity_evidence": live_evidence,
        "holdout_2026_opened": False,
        "production_modified": False,
        "payoff_authorized_at_freeze": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
