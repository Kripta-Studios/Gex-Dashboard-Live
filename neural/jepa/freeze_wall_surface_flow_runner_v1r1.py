"""Create the immutable pre-execution manifest for wall-flow physical V1R1."""

from __future__ import annotations

import argparse
import copy
import json
import re
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


CODE_CLOSURE = (
    "neural/jepa/evaluate_wall_surface_flow_at_touch_v1.py",
    "neural/jepa/surface_flow_features.py",
    "neural/jepa/freeze_wall_surface_flow_runner_v1r1.py",
    "neural/jepa/wall_surface_flow_environment.py",
    "neural/jepa/build_wall_surface_flow_dataset.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    "neural/jepa/build_wall_exact_greek_repair_sidecar.py",
    "neural/jepa/build_wall_exact_greek_repair_artifacts.py",
    "neural/jepa/wall_state_features.py",
)
PROTOCOL_CLOSURE = (
    "research_papers/JEPA/WALL_SURFACE_FLOW_AT_TOUCH_PREDECLARATION_V1.md",
    "research_papers/JEPA/WALL_SURFACE_FLOW_AT_TOUCH_V1R1_CAUSAL_AMENDMENT.md",
    "research_papers/JEPA/WALL_SURFACE_FLOW_V1R2_EXACT_SPOT_REPAIR_PREDECLARATION.md",
    "research_papers/JEPA/WALL_SURFACE_FLOW_V1R2_DATA_GATE_CLARIFICATION.md",
    "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
)
EXACT_REPAIR_REQUIRED_HASH_FIELDS = (
    "manifest_sha256",
    "wall_repair_sha256",
    "event_control_repair_sha256",
    "event_target_key_sha256",
    "builder_sha256",
    "sidecar_builder_sha256",
    "wall_feature_module_sha256",
    "predeclaration_sha256",
    "runtime_lock_sha256",
    "runtime_environment_sha256",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


def committed_hash_inventory(relative_paths: tuple[str, ...]) -> dict[str, str]:
    inventory: dict[str, str] = {}
    for relative in relative_paths:
        path = PROJECT_ROOT / relative
        observed_relative = assert_code_committed_clean(path)
        if observed_relative != relative:
            raise AssertionError(
                f"hash closure path normalization mismatch: {observed_relative} != {relative}"
            )
        inventory[relative] = sha256_file(path)
    return inventory


def validate_exact_greek_repair_provenance(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssertionError("PASS data manifest requires exact_greek_repair_provenance")
    if value.get("schema") != "wall_exact_greek_repair_artifacts_v1r2":
        raise AssertionError("exact Greek repair provenance schema mismatch")
    if value.get("status") != "PASS_EXACT_GREEK_REPAIR_ARTIFACTS":
        raise AssertionError("exact Greek repair provenance is not PASS")
    if value.get("frozen_hashes_match") is not True:
        raise AssertionError("exact Greek repair frozen hashes did not match")
    if value.get("historical_provenance") != "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION":
        raise AssertionError("exact Greek repair historical provenance mismatch")
    expected_sessions = [
        {"ticker": "QQQ", "trade_date": "20221230"},
        {"ticker": "SPY", "trade_date": "20221230"},
    ]
    if value.get("target_sessions") != expected_sessions:
        raise AssertionError("exact Greek repair target sessions mismatch")
    expected_counts = {
        "wall_target_rows": 96,
        "full_control_grid_rows": 96,
        "event_target_rows": 47,
    }
    for field, expected in expected_counts.items():
        if int(value.get(field, -1)) != expected:
            raise AssertionError(f"exact Greek repair {field} mismatch")
    if value.get("event_target_rows_by_ticker") != {"QQQ": 27, "SPY": 20}:
        raise AssertionError("exact Greek repair per-ticker event rows mismatch")
    for field in EXACT_REPAIR_REQUIRED_HASH_FIELDS:
        if not SHA256_RE.fullmatch(str(value.get(field, ""))):
            raise AssertionError(f"exact Greek repair missing valid {field}")
    for path_field, hash_field in (
        ("manifest_path", "manifest_sha256"),
        ("wall_repair_path", "wall_repair_sha256"),
        ("event_control_repair_path", "event_control_repair_sha256"),
    ):
        raw_path = value.get(path_field)
        if not isinstance(raw_path, str) or not raw_path:
            raise AssertionError(f"exact Greek repair missing {path_field}")
        path = PROJECT_ROOT / Path(raw_path)
        assert_code_committed_clean(path)
        if sha256_file(path) != value[hash_field]:
            raise AssertionError(f"exact Greek repair artifact hash mismatch: {path_field}")
    return copy.deepcopy(value)


def validate_historical_provenance_status(
    exact_greek_repair_provenance: dict[str, Any], requested_status: str
) -> None:
    repair_status = exact_greek_repair_provenance["historical_provenance"]
    if repair_status == "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION" and requested_status == "PASS":
        raise AssertionError(
            "historical timestamp provenance cannot be PASS while exact Greek repair "
            "provenance is conditional"
        )


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
    code_hashes = committed_hash_inventory(CODE_CLOSURE)
    protocol_hashes = committed_hash_inventory(PROTOCOL_CLOSURE)
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
    exact_greek_repair_provenance = validate_exact_greek_repair_provenance(
        data_manifest.get("exact_greek_repair_provenance")
    )
    validate_historical_provenance_status(
        exact_greek_repair_provenance,
        str(args.historical_timestamp_provenance_status),
    )
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
        "code_hashes": code_hashes,
        "protocol_hashes": protocol_hashes,
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
        "exact_greek_repair_provenance": exact_greek_repair_provenance,
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
