"""Freeze H-QSIZE1 inputs, allowlists, models and gates before outcomes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.evaluate_wall_quote_size_pressure_at_touch_v1 import (  # noqa: E402
    ENVIRONMENT_LOCK,
    EXPECTED_SESSION_KEY_SHA256,
    BUILD_CODE_CLOSURE,
    assert_qsize_source_inventory,
    assert_source_inventory,
    GATE_SPEC,
    QSIZE_FEATURES,
    QSIZE_QUALITY_FIELDS,
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
    "neural/jepa/build_wall_quote_size_pressure_dataset.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    "neural/jepa/build_wall_quote_size_complement_sidecar.py",
    "neural/jepa/build_wall_surface_flow_dataset.py",
    "neural/jepa/evaluate_wall_quote_size_pressure_at_touch_v1.py",
    "neural/jepa/freeze_wall_quote_size_pressure_runner_v1.py",
    "neural/jepa/evaluate_wall_surface_flow_at_touch_v1.py",
    "neural/jepa/surface_flow_features.py",
    "neural/jepa/quote_size_pressure_features.py",
    "neural/jepa/iv_surface_deformation_features.py",
    "neural/jepa/wall_surface_flow_environment.py",
)
PROTOCOL_CLOSURE = (
    "research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_PREDECLARATION.md",
    "research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_CAUSAL_AMENDMENT.md",
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
    p.add_argument("--qsize-source-hashes", required=True)
    p.add_argument("--data-manifest", required=True)
    p.add_argument("--output", required=True)
    return p.parse_args()


def main() -> int:
    a = parse_args()
    output = Path(a.output)
    if output.exists():
        raise FileExistsError(f"frozen manifest exists: {output}")
    dataset, label_source, qsize_source, manifest_path = (
        Path(a.dataset),
        Path(a.source_hashes),
        Path(a.qsize_source_hashes),
        Path(a.data_manifest),
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tracked_artifact(label_source, "label source inventory")
    tracked_artifact(qsize_source, "qsize source inventory")
    tracked_artifact(manifest_path, "data manifest")
    assert_source_inventory(pd.read_csv(label_source, dtype={"trade_date": str}))
    assert_qsize_source_inventory(
        pd.read_csv(qsize_source, dtype={"trade_date": str})
    )
    if (
        manifest.get("schema") != "wall_quote_size_pressure_at_touch_dataset_v1"
        or manifest.get("status") != "PASS_DATA_GATE"
        or manifest.get("outcome_free") is not True
        or manifest.get("holdout_2026_used") is not False
        or manifest.get("production_modified") is not False
        or manifest.get("errors") != []
        or int(manifest.get("rows", -1)) != 10683
    ):
        raise AssertionError("cannot freeze a failed H-QSIZE1 data gate")
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
        raise AssertionError("cannot freeze non-strict H-QSIZE1 data-gate booleans")
    if manifest.get("dataset_sha256") != sha256_file(dataset):
        raise AssertionError("H-QSIZE1 dataset hash differs from data manifest")
    if manifest.get("source_inventory_sha256") != sha256_file(qsize_source):
        raise AssertionError("qsize source inventory hash differs from data manifest")
    sidecar = manifest.get("sidecar_provenance")
    required_sidecar_fields = (
        "fallback_seal_sha256",
        "fallback_index_sha256",
        "complement_seal_sha256",
        "complement_index_sha256",
        "session_key_sha256",
    )
    if (
        not isinstance(sidecar, dict)
        or int(sidecar.get("sessions", -1)) != 2519
        or int(sidecar.get("fallback_sessions", -1)) != 1441
        or int(sidecar.get("complement_sessions", -1)) != 1078
        or sidecar.get("session_key_sha256") != EXPECTED_SESSION_KEY_SHA256
        or sidecar.get("historical_provenance")
        != "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION"
        or any(
            not isinstance(sidecar.get(field), str)
            or len(sidecar.get(field, "")) != 64
            for field in required_sidecar_fields
        )
    ):
        raise AssertionError("sealed H-QSIZE1 sidecar provenance is incomplete")
    code_hashes = {p: tracked_clean(p) for p in CODE_CLOSURE}
    protocol_hashes = {p: tracked_clean(p) for p in PROTOCOL_CLOSURE}
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    build_hashes = manifest.get("code_hashes")
    expected_build_hashes = {path: code_hashes[path] for path in BUILD_CODE_CLOSURE}
    expected_build_hashes.update(
        {
            path: protocol_hashes[path]
            for path in PROTOCOL_CLOSURE
        }
    )
    if build_hashes != expected_build_hashes:
        raise AssertionError("H-QSIZE1 build code/protocol hashes differ from freeze")
    if (
        manifest.get("runtime_lock_sha256") != runtime["lock_sha256"]
        or manifest.get("runtime_environment") != runtime["environment"]
        or manifest.get("runtime_environment_sha256") != runtime["environment_sha256"]
    ):
        raise AssertionError("H-QSIZE1 build runtime differs from freeze")
    if (
        manifest.get("control_feature_hash") != hash_list(CONTROL_FEATURES)
        or manifest.get("qsize_feature_hash") != hash_list(QSIZE_FEATURES)
        or manifest.get("qsize_quality_hash") != hash_list(QSIZE_QUALITY_FIELDS)
        or manifest.get("predeclaration_sha256")
        != protocol_hashes["research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_PREDECLARATION.md"]
        or manifest.get("causal_amendment_sha256")
        != protocol_hashes["research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_CAUSAL_AMENDMENT.md"]
    ):
        raise AssertionError("H-QSIZE1 build feature/protocol hashes differ from freeze")
    payload = {
        "schema": "wall_quote_size_pressure_at_touch_frozen_runner_v1",
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
            "label_source_hashes": {
                "path": str(label_source),
                "sha256": sha256_file(label_source),
            },
            "qsize_source_hashes": {
                "path": str(qsize_source),
                "sha256": sha256_file(qsize_source),
            },
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
        "qsize_model_allowlist": list(QSIZE_FEATURES),
        "qsize_quality_fields": list(QSIZE_QUALITY_FIELDS),
        "physical_sample_filter": "qsize_both_valid == True",
        "primary_model": {
            "family": "logistic_regression",
            "params": LR_PARAMS,
            "preprocessing": [
                "train_only_median_imputation",
                "no_missing_indicators",
                "train_only_standardization",
            ],
        },
        "sensitivity_model": {
            "family": "lightgbm",
            "params": LGBM_PARAMS,
            "preprocessing": [
                "train_only_median_imputation",
                "no_native_missing_branches",
            ],
            "can_rescue_primary": False,
        },
        "label_spec": LABEL_SPEC,
        "gate_spec": GATE_SPEC,
        "sidecar_provenance": sidecar,
        "historical_timestamp_provenance_status": "CONDITIONAL",
        "live_feature_parity_status": "BLOCKED",
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
