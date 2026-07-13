"""Freeze H-IBQDYN1 physical inputs, features, models and gates."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from neural.jepa.build_h_ibqdyn1_dataset import (
    ALPHA_FIELDS,
    AUTHORITATIVE_CODE as BUILD_CODE_CLOSURE,
    CONTROL_FEATURES,
    EXPECTED_EVENTS,
    QUALITY_FIELDS,
)
from neural.jepa.evaluate_h_ibqdyn1_physical import (
    CODE_CLOSURE,
    ENVIRONMENT_LOCK,
    GATE_SPEC,
    LABEL_SPEC,
    LGBM_PARAMS,
    LR_PARAMS,
    PROJECT_ROOT,
    PROTOCOL_CLOSURE,
    assert_contract_source_inventory,
    assert_source_inventory,
    feature_names,
    hash_list,
    sha256_file,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock


def tracked_clean(path: Path, label: str) -> str:
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
        raise AssertionError(f"{label} must be committed and clean: {dirty}")
    return sha256_file(path)


def build_frozen_payload(
    dataset: Path,
    label_source: Path,
    contract_source: Path,
    data_manifest: Path,
) -> dict:
    manifest = json.loads(data_manifest.read_text(encoding="utf-8"))
    for path, label in (
        (label_source, "label source inventory"),
        (contract_source, "contract source inventory"),
        (data_manifest, "data manifest"),
    ):
        tracked_clean(path, label)
    assert_source_inventory(pd.read_csv(label_source, dtype={"trade_date": str}))
    assert_contract_source_inventory(
        pd.read_csv(contract_source, dtype={"trade_date": str})
    )
    gate = manifest.get("data_gate")
    required_gate = (
        "rows_preserved",
        "coverage_pass",
        "distinctness_pass",
        "control_coverage_pass",
        "identical_complete_case_pass",
        "passed",
    )
    if (
        manifest.get("schema") != "h_ibqdyn1_outcome_free_dataset_v1"
        or manifest.get("status") != "PASS_DATA_GATE"
        or manifest.get("outcome_free") is not True
        or manifest.get("holdout_2026_used") is not False
        or manifest.get("production_modified") is not False
        or manifest.get("errors") != []
        or int(manifest.get("rows", -1)) != EXPECTED_EVENTS
        or manifest.get("dataset_sha256") != sha256_file(dataset)
        or manifest.get("source_inventory_sha256") != sha256_file(contract_source)
        or not isinstance(gate, dict)
        or any(gate.get(field) is not True for field in required_gate)
    ):
        raise AssertionError("cannot freeze a failed H-IBQDYN1 data gate")
    code_hashes = {
        relative: tracked_clean(PROJECT_ROOT / relative, "physical code")
        for relative in CODE_CLOSURE
    }
    protocol_hashes = {
        relative: tracked_clean(PROJECT_ROOT / relative, "physical protocol")
        for relative in PROTOCOL_CLOSURE
    }
    expected_build = {
        relative: sha256_file(PROJECT_ROOT / relative) for relative in BUILD_CODE_CLOSURE
    }
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    if (
        manifest.get("code_hashes") != expected_build
        or manifest.get("runtime_lock_sha256") != runtime["lock_sha256"]
        or manifest.get("runtime_environment_sha256") != runtime["environment_sha256"]
        or manifest.get("control_feature_hash") != hash_list(CONTROL_FEATURES)
        or manifest.get("alpha_feature_hash") != hash_list(ALPHA_FIELDS)
        or manifest.get("quality_field_hash") != hash_list(QUALITY_FIELDS)
        or manifest.get("historical_provenance")
        != "CONDITIONAL_REMOTE_TERMINAL_RECONSTRUCTION"
        or manifest.get("live_parity") != "BLOCKED"
    ):
        raise AssertionError("H-IBQDYN1 build/runtime/provenance closure mismatch")
    return {
        "schema": "h_ibqdyn1_frozen_physical_runner_v1",
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
            "contract_source_hashes": {
                "path": str(contract_source),
                "sha256": sha256_file(contract_source),
            },
            "data_manifest": {
                "path": str(data_manifest),
                "sha256": sha256_file(data_manifest),
            },
        },
        "feature_names": {"F0": feature_names("F0"), "F1": feature_names("F1")},
        "feature_hashes": {
            "F0": hash_list(feature_names("F0")),
            "F1": hash_list(feature_names("F1")),
        },
        "alpha_model_allowlist": list(ALPHA_FIELDS),
        "quality_fields": list(QUALITY_FIELDS),
        "physical_sample_filter": "ibqdyn_both_valid == True",
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
        "folds": shared_folds(),
        "horizons": list(shared_horizons()),
        "historical_timestamp_provenance_status": "CONDITIONAL",
        "live_feature_parity_status": "BLOCKED",
        "holdout_2026_opened": False,
        "production_modified": False,
        "payoff_authorized_at_freeze": False,
    }


def shared_folds() -> list[dict]:
    from neural.jepa.evaluate_wall_surface_flow_at_touch_v1 import FOLDS

    return [dict(value) for value in FOLDS]


def shared_horizons() -> tuple[int, ...]:
    from neural.jepa.evaluate_wall_surface_flow_at_touch_v1 import HORIZONS

    return tuple(HORIZONS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--label-source-hashes", required=True)
    parser.add_argument("--contract-source-hashes", required=True)
    parser.add_argument("--data-manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError("frozen H-IBQDYN1 runner already exists")
    payload = build_frozen_payload(
        Path(args.dataset),
        Path(args.label_source_hashes),
        Path(args.contract_source_hashes),
        Path(args.data_manifest),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
