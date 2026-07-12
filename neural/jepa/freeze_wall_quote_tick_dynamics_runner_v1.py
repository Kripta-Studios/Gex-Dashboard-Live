"""Freeze H-QDYN1R1 inputs, features, models and gates before outcomes."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from neural.jepa.evaluate_wall_quote_tick_dynamics_at_touch_v1 import (
    BUILD_CODE_CLOSURE,
    CAPTURE_CLARIFICATION,
    CAUSAL_AMENDMENT,
    CODE_CLOSURE,
    CONTROL_FEATURES,
    ENVIRONMENT_LOCK,
    EXPECTED_CANDIDATES,
    EXPECTED_CANDIDATE_SHA256,
    GATE_SPEC,
    LGBM_PARAMS,
    LR_PARAMS,
    PREDECLARATION,
    PROJECT_ROOT,
    PROTOCOL_CLOSURE,
    QDYN_FEATURES,
    QDYN_QUALITY_FIELDS,
    assert_qdyn_source_inventory,
    feature_names,
    sha256_file,
    shared,
)
from neural.jepa.build_wall_quote_tick_dynamics_sidecar import (
    EXPECTED_WALL_STATE_SHA256,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock


def tracked_clean(relative: str) -> str:
    subprocess.run(["git", "ls-files", "--error-unmatch", relative],
                   cwd=PROJECT_ROOT, check=True, capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "--", relative],
                           cwd=PROJECT_ROOT, check=True, capture_output=True,
                           text=True).stdout.strip()
    if dirty:
        raise AssertionError(f"freeze requires committed clean file: {relative}: {dirty}")
    return sha256_file(PROJECT_ROOT / relative)


def tracked_artifact(path: Path, label: str) -> str:
    try:
        relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError as exc:
        raise AssertionError(f"{label} must be a committed repository artifact") from exc
    return tracked_clean(relative)


def build_frozen_payload(dataset: Path, label_source: Path, qdyn_source: Path,
                         data_manifest: Path) -> dict:
    manifest = json.loads(data_manifest.read_text(encoding="utf-8"))
    for path, label in ((label_source, "label source inventory"),
                        (qdyn_source, "qdyn source inventory"),
                        (data_manifest, "data manifest")):
        tracked_artifact(path, label)
    shared.assert_source_inventory(pd.read_csv(label_source, dtype={"trade_date": str}))
    source = pd.read_csv(qdyn_source, dtype={"trade_date": str})
    gate = manifest.get("data_gate")
    if (manifest.get("schema") != "wall_quote_tick_dynamics_at_touch_dataset_v1r1r1"
            or manifest.get("status") != "PASS_DATA_GATE"
            or manifest.get("outcome_free") is not True
            or manifest.get("holdout_2026_used") is not False
            or manifest.get("production_modified") is not False
            or manifest.get("errors") != []
            or int(manifest.get("rows", -1)) != EXPECTED_CANDIDATES
            or manifest.get("candidate_sha256") != EXPECTED_CANDIDATE_SHA256
            or manifest.get("dataset_sha256") != sha256_file(dataset)
            or manifest.get("source_inventory_sha256") != sha256_file(qdyn_source)
            or not isinstance(gate, dict)
            or gate.get("coverage_pass") is not True
            or gate.get("distinctness_pass") is not True
            or gate.get("passed") is not True):
        raise AssertionError("cannot freeze a failed H-QDYN1 data gate")
    eligible_events = len(source)
    provisional = {"eligible_events": eligible_events}
    assert_qdyn_source_inventory(source, provisional)
    code_hashes = {name: tracked_clean(name) for name in CODE_CLOSURE}
    protocol_hashes = {name: tracked_clean(name) for name in PROTOCOL_CLOSURE}
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    expected_build = {name: sha256_file(PROJECT_ROOT / name)
                      for name in BUILD_CODE_CLOSURE}
    if (manifest.get("code_hashes") != expected_build
            or manifest.get("runtime_lock_sha256") != runtime["lock_sha256"]
            or manifest.get("runtime_environment_sha256") != runtime["environment_sha256"]
            or manifest.get("control_feature_hash") != shared.hash_list(CONTROL_FEATURES)
            or manifest.get("qdyn_feature_hash") != shared.hash_list(QDYN_FEATURES)
            or manifest.get("qdyn_quality_hash") != shared.hash_list(QDYN_QUALITY_FIELDS)
            or manifest.get("predeclaration_sha256") != protocol_hashes[PREDECLARATION]
            or manifest.get("causal_amendment_sha256") != protocol_hashes[CAUSAL_AMENDMENT]
            or manifest.get("capture_clarification_sha256")
            != protocol_hashes[CAPTURE_CLARIFICATION]
            or manifest.get("historical_provenance") != "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION"
            or manifest.get("live_parity") != "BLOCKED"
            or not isinstance(manifest.get("sidecar_index_sha256"), str)
            or not isinstance(manifest.get("sidecar_seal_sha256"), str)
            or not isinstance(manifest.get("subscription_proof_sha256"), str)
            or not isinstance(manifest.get("subscription_proof_manifest_sha256"), str)
            or manifest.get("eligible_event_id_sha256") is None):
        raise AssertionError("H-QDYN1 build/runtime/provenance closure mismatch")
    return {
        "schema": "wall_quote_tick_dynamics_at_touch_frozen_runner_v1r1r1",
        "status": "PREEXECUTION_FROZEN",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
                                        check=True, capture_output=True, text=True).stdout.strip(),
        "code_hashes": code_hashes, "protocol_hashes": protocol_hashes,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "inputs": {
            "dataset": {"path": str(dataset), "sha256": sha256_file(dataset)},
            "label_source_hashes": {"path": str(label_source), "sha256": sha256_file(label_source)},
            "qdyn_source_hashes": {"path": str(qdyn_source), "sha256": sha256_file(qdyn_source)},
            "data_manifest": {"path": str(data_manifest), "sha256": sha256_file(data_manifest)},
        },
        "feature_names": {"F0": feature_names("F0"), "F1": feature_names("F1")},
        "feature_hashes": {"F0": shared.hash_list(feature_names("F0")),
                           "F1": shared.hash_list(feature_names("F1"))},
        "qdyn_model_allowlist": list(QDYN_FEATURES),
        "qdyn_quality_fields": list(QDYN_QUALITY_FIELDS),
        "physical_sample_filter": "qdyn_both_valid == True",
        "primary_model": {"family": "logistic_regression", "params": LR_PARAMS,
                          "preprocessing": ["train_only_median_imputation",
                                            "no_missing_indicators",
                                            "train_only_standardization"]},
        "sensitivity_model": {"family": "lightgbm", "params": LGBM_PARAMS,
                              "preprocessing": ["train_only_median_imputation",
                                                "no_native_missing_branches"],
                              "can_rescue_primary": False},
        "label_spec": shared.LABEL_SPEC, "gate_spec": GATE_SPEC,
        "folds": shared.FOLDS, "horizons": shared.HORIZONS,
        "eligible_events": eligible_events,
        "candidate_sha256": EXPECTED_CANDIDATE_SHA256,
        "wall_state_sha256": EXPECTED_WALL_STATE_SHA256,
        "sidecar_index_sha256": manifest["sidecar_index_sha256"],
        "sidecar_seal_sha256": manifest["sidecar_seal_sha256"],
        "subscription_proof_sha256": manifest["subscription_proof_sha256"],
        "subscription_proof_manifest_sha256": manifest["subscription_proof_manifest_sha256"],
        "eligible_event_id_sha256": manifest["eligible_event_id_sha256"],
        "historical_timestamp_provenance_status": "CONDITIONAL",
        "live_feature_parity_status": "BLOCKED",
        "holdout_2026_opened": False, "production_modified": False,
        "payoff_authorized_at_freeze": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--source-hashes", required=True)
    parser.add_argument("--qdyn-source-hashes", required=True)
    parser.add_argument("--data-manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"frozen manifest exists: {output}")
    payload = build_frozen_payload(Path(args.dataset), Path(args.source_hashes),
                                   Path(args.qdyn_source_hashes), Path(args.data_manifest))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
