"""Freeze H-IVSURF1 inputs, allowlists, models and gates before outcomes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.evaluate_wall_iv_surface_at_touch_v1 import (  # noqa: E402
    ENVIRONMENT_LOCK,
    GATE_SPEC,
    IV_SURFACE_ALLOWLIST,
    CONTROL_FEATURES,
    LABEL_SPEC,
    LGBM_PARAMS,
    LR_PARAMS,
    feature_names,
    hash_list,
    sha256_file,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402

CODE_CLOSURE = (
    "neural/jepa/build_wall_iv_surface_deformation_dataset.py",
    "neural/jepa/evaluate_wall_iv_surface_at_touch_v1.py",
    "neural/jepa/freeze_wall_iv_surface_runner_v1.py",
    "neural/jepa/evaluate_wall_surface_flow_at_touch_v1.py",
    "neural/jepa/surface_flow_features.py",
    "neural/jepa/iv_surface_deformation_features.py",
    "neural/jepa/wall_surface_flow_environment.py",
)
PROTOCOL_CLOSURE = (
    "research_papers/JEPA/WALL_IV_SURFACE_DEFORMATION_AT_TOUCH_V1_PREDECLARATION.md",
    "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
)


def tracked_clean(relative: str) -> str:
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
        raise AssertionError(
            f"freeze requires committed clean file: {relative}: {dirty}"
        )
    return sha256_file(PROJECT_ROOT / relative)


def tracked_artifact(path: Path, label: str) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError as exc:
        raise AssertionError(f"{label} must be a committed repository artifact") from exc
    return tracked_clean(relative)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", required=True)
    p.add_argument("--source-hashes", required=True)
    p.add_argument("--data-manifest", required=True)
    p.add_argument("--output", required=True)
    p.add_argument(
        "--historical-timestamp-provenance-status",
        choices=("PASS", "CONDITIONAL", "BLOCKED"),
        default="CONDITIONAL",
    )
    p.add_argument(
        "--live-feature-parity-status", choices=("PASS", "BLOCKED"), default="BLOCKED"
    )
    return p.parse_args()


def main() -> int:
    a = parse_args()
    output = Path(a.output)
    if output.exists():
        raise FileExistsError(f"frozen manifest exists: {output}")
    dataset, source, manifest_path = (
        Path(a.dataset),
        Path(a.source_hashes),
        Path(a.data_manifest),
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tracked_artifact(source, "source inventory")
    tracked_artifact(manifest_path, "data manifest")
    if manifest.get("status") != "PASS_DATA_GATE":
        raise AssertionError("cannot freeze a failed H-IVSURF1 data gate")
    gate = manifest.get("data_gate")
    required_gate_bools = (
        "authoritative_inputs",
        "authoritative_code",
        "coverage_pass",
        "distinctness_pass",
        "control_coverage_pass",
        "passed",
    )
    if not isinstance(gate, dict) or any(
        gate.get(name) is not True for name in required_gate_bools
    ):
        raise AssertionError("cannot freeze non-strict H-IVSURF1 data-gate booleans")
    if manifest.get("dataset_sha256") != sha256_file(dataset):
        raise AssertionError("H-IVSURF1 dataset hash differs from data manifest")
    if manifest.get("source_file_hashes_sha256") != sha256_file(source):
        raise AssertionError("source inventory hash differs from data manifest")
    if (
        manifest.get("holdout_2026_used") is True
        or manifest.get("production_modified") is True
    ):
        raise AssertionError("data manifest reports forbidden 2026/production use")
    native = manifest.get("native_quote_provenance")
    exact = manifest.get("exact_greek_repair_provenance")
    if not isinstance(native, dict) or int(native.get("sessions", -1)) != 1441:
        raise AssertionError("sealed native quote provenance is missing/incomplete")
    if (
        not isinstance(exact, dict)
        or exact.get("status") != "PASS_EXACT_GREEK_REPAIR_ARTIFACTS"
        or exact.get("frozen_hashes_match") is not True
        or exact.get("historical_provenance")
        != "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION"
    ):
        raise AssertionError(
            "sealed exact-Greek repair provenance is missing/inconsistent"
        )
    if a.historical_timestamp_provenance_status == "PASS":
        raise AssertionError(
            "conditional exact-Greek reconstruction forbids authoritative PASS provenance"
        )
    code_hashes = {p: tracked_clean(p) for p in CODE_CLOSURE}
    protocol_hashes = {p: tracked_clean(p) for p in PROTOCOL_CLOSURE}
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    build_hashes = manifest.get("code_hashes")
    expected_build_hashes = {
        path: code_hashes[path]
        for path in (
            "neural/jepa/build_wall_iv_surface_deformation_dataset.py",
            "neural/jepa/iv_surface_deformation_features.py",
        )
    }
    expected_build_hashes.update(
        {
            path: protocol_hashes[path]
            for path in PROTOCOL_CLOSURE
        }
    )
    if build_hashes != expected_build_hashes:
        raise AssertionError("H-IVSURF1 build code/protocol hashes differ from freeze")
    if (
        manifest.get("runtime_lock_sha256") != runtime["lock_sha256"]
        or manifest.get("runtime_environment") != runtime["environment"]
        or manifest.get("runtime_environment_sha256") != runtime["environment_sha256"]
    ):
        raise AssertionError("H-IVSURF1 build runtime differs from freeze")
    if (
        manifest.get("control_feature_hash") != hash_list(CONTROL_FEATURES)
        or manifest.get("iv_surface_feature_hash") != hash_list(IV_SURFACE_ALLOWLIST)
        or manifest.get("predeclaration_sha256")
        != protocol_hashes["research_papers/JEPA/WALL_IV_SURFACE_DEFORMATION_AT_TOUCH_V1_PREDECLARATION.md"]
    ):
        raise AssertionError("H-IVSURF1 build feature/protocol hashes differ from freeze")
    payload = {
        "schema": "wall_iv_surface_at_touch_frozen_runner_v1",
        "status": "PREEXECUTION_FROZEN",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "code_hashes": code_hashes,
        "protocol_hashes": protocol_hashes,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "inputs": {
            "dataset": {"path": str(dataset), "sha256": sha256_file(dataset)},
            "source_file_hashes": {"path": str(source), "sha256": sha256_file(source)},
            "data_manifest": {
                "path": str(manifest_path),
                "sha256": sha256_file(manifest_path),
            },
        },
        "feature_names": {"F0": feature_names("F0"), "F1": feature_names("F1")},
        "feature_hashes": {
            "F0": hash_list(feature_names("F0")),
            "F1": hash_list(feature_names("F1")),
        },
        "iv_surface_allowlist": list(IV_SURFACE_ALLOWLIST),
        "primary_model": {
            "family": "logistic_regression",
            "params": LR_PARAMS,
            "preprocessing": [
                "train_only_median_imputation",
                "missing_indicators",
                "train_only_standardization",
            ],
        },
        "sensitivity_model": {
            "family": "lightgbm",
            "params": LGBM_PARAMS,
            "can_rescue_primary": False,
        },
        "label_spec": LABEL_SPEC,
        "gate_spec": GATE_SPEC,
        "native_quote_provenance": native,
        "exact_greek_repair_provenance": exact,
        "historical_timestamp_provenance_status": a.historical_timestamp_provenance_status,
        "live_feature_parity_status": a.live_feature_parity_status,
        "holdout_2026_opened": False,
        "production_modified": False,
        "payoff_authorized_at_freeze": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
