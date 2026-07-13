"""Frozen physical F0/F1 evaluator for H-IBQDYN1.

No outcome is read until a committed runner manifest has verified a strict
PASS_DATA_GATE, every active code/protocol hash and the exact source inventories.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd

from neural.jepa import evaluate_wall_quote_size_pressure_at_touch_v1 as shared
from neural.jepa.build_h_ibqdyn1_dataset import (
    ALPHA_FIELDS,
    AUTHORITATIVE_CODE as BUILD_CODE_CLOSURE,
    CONTROL_FEATURES,
    DATA_GATE_CONTRACT,
    EXPECTED_EVENTS,
    FEATURE_CLARIFICATION,
    PREDECLARATION,
    QUALITY_FIELDS,
)
from neural.jepa.build_wall_quote_tick_dynamics_dataset import (
    QDYN_FEATURES as CLOSED_QDYN_FEATURES,
)
from neural.jepa.evaluate_wall_surface_flow_at_touch_v1 import (
    LABEL_SPEC as SHARED_LABEL_SPEC,
    add_future_labels,
    assert_source_inventory,
    hash_list,
    sha256_file,
)
from neural.jepa.iv_surface_deformation_features import IV_SURFACE_ALLOWLIST
from neural.jepa.quote_size_pressure_features import QSIZE_FEATURES
from neural.jepa.surface_flow_features import FLOW_FEATURES
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT_LOCK = (
    PROJECT_ROOT / "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
)
SEED = 20260713
LEVEL_IDENTITIES = (
    "fib_127_dn",
    "fib_127_up",
    "fib_161_dn",
    "fib_161_up",
    "fib_200_dn",
    "fib_200_up",
    "ib_high",
    "ib_low",
)
IDENTITY_SPECS = {identity: identity for identity in LEVEL_IDENTITIES}
LR_PARAMS: dict[str, Any] = {**shared.LR_PARAMS, "random_state": SEED}
LGBM_PARAMS: dict[str, Any] = {**shared.LGBM_PARAMS, "random_state": SEED}
GATE_SPEC = {
    **shared.GATE_SPEC,
    "maximum_wilcoxon_one_sided_p": 0.0125,
}
LABEL_SPEC = {
    **SHARED_LABEL_SPEC,
    "touch_universe_bps": 20.0,
    "event_universe": "first executable event in each frozen 30-minute clock block",
}
FINAL_FIT_AMENDMENT = "research_papers/JEPA/H_IBQDYN1_2026_FINAL_FIT_AMENDMENT.md"
RUNTIME_LOCK = "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
PROTOCOL_CLOSURE = (
    PREDECLARATION,
    FEATURE_CLARIFICATION,
    DATA_GATE_CONTRACT,
    FINAL_FIT_AMENDMENT,
    RUNTIME_LOCK,
)
CODE_CLOSURE = (
    *BUILD_CODE_CLOSURE,
    "neural/jepa/evaluate_h_ibqdyn1_physical.py",
    "neural/jepa/freeze_h_ibqdyn1_physical_runner.py",
    "neural/jepa/evaluate_wall_quote_size_pressure_at_touch_v1.py",
    "neural/jepa/evaluate_wall_surface_flow_at_touch_v1.py",
    "neural/jepa/iv_surface_deformation_features.py",
    "neural/jepa/quote_size_pressure_features.py",
)


def raw_feature_names(arm: str) -> list[str]:
    if arm == "F0":
        return list(CONTROL_FEATURES)
    if arm == "F1":
        return [*CONTROL_FEATURES, *ALPHA_FIELDS]
    raise ValueError(f"unknown H-IBQDYN1 arm: {arm}")


def feature_names(arm: str) -> list[str]:
    return [
        *raw_feature_names(arm),
        *(f"identity_{identity}" for identity in LEVEL_IDENTITIES),
    ]


def assert_no_closed_features(columns: list[str] | tuple[str, ...]) -> None:
    closed = set(
        (
            *FLOW_FEATURES,
            *IV_SURFACE_ALLOWLIST,
            *QSIZE_FEATURES,
            *CLOSED_QDYN_FEATURES,
        )
    )
    forbidden = sorted(set(columns).intersection(closed))
    if forbidden:
        raise AssertionError(f"closed features entered H-IBQDYN1: {forbidden[:10]}")


def assert_contract_source_inventory(frame: pd.DataFrame) -> None:
    required = {
        "contract_id",
        "event_id",
        "ticker",
        "trade_date",
        "right",
        "raw_path",
        "raw_sha256",
        "parquet_path",
        "parquet_sha256",
        "manifest_path",
        "manifest_sha256",
        "rows",
    }
    if required.difference(frame.columns):
        raise AssertionError("H-IBQDYN1 contract source inventory is incomplete")
    hashes = [field for field in required if field.endswith("sha256")]
    rights = frame.groupby("event_id", observed=True)["right"].agg(
        lambda values: sorted(values.astype(str).str.upper().tolist())
    )
    if (
        len(frame) != 33_704
        or frame["contract_id"].astype(str).duplicated().any()
        or frame["event_id"].astype(str).nunique() != 16_852
        or not rights.map(lambda values: values == ["CALL", "PUT"]).all()
        or frame["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8].ge("20260101").any()
        or not frame["ticker"].astype(str).str.upper().isin(["SPXW", "QQQ", "SPY"]).all()
        or any(
            not frame[field].astype(str).str.fullmatch(r"[0-9a-f]{64}", case=False).all()
            for field in hashes
        )
        or pd.to_numeric(frame["rows"], errors="coerce").fillna(-1).lt(0).any()
    ):
        raise AssertionError("H-IBQDYN1 contract source inventory contract failed")


@contextmanager
def _shared_contract() -> Iterator[None]:
    names = (
        "QSIZE_FEATURES",
        "GATE_SPEC",
        "LR_PARAMS",
        "LGBM_PARAMS",
        "SEED",
        "WALL_SPECS",
        "raw_feature_names",
        "feature_names",
        "assert_no_closed_features",
    )
    old = {name: getattr(shared, name) for name in names}
    shared.QSIZE_FEATURES = ALPHA_FIELDS
    shared.GATE_SPEC = GATE_SPEC
    shared.LR_PARAMS = LR_PARAMS
    shared.LGBM_PARAMS = LGBM_PARAMS
    shared.SEED = SEED
    shared.WALL_SPECS = IDENTITY_SPECS
    shared.raw_feature_names = raw_feature_names
    shared.feature_names = feature_names
    shared.assert_no_closed_features = assert_no_closed_features
    try:
        yield
    finally:
        for name, value in old.items():
            setattr(shared, name, value)


def evaluate_cells(labeled: pd.DataFrame, model_dir: Path):
    if "ibqdyn_both_valid" not in labeled:
        raise AssertionError("missing frozen ibqdyn_both_valid complete-case flag")
    work = labeled.copy()
    work["qsize_both_valid"] = work["ibqdyn_both_valid"]
    with _shared_contract():
        return shared.evaluate_cells(work, model_dir)


def summarize_gate(
    cells: pd.DataFrame,
    paired: pd.DataFrame,
    monthly: pd.DataFrame,
    provenance_status: str,
    live_parity_status: str,
) -> dict[str, Any]:
    with _shared_contract():
        result = shared.summarize_gate(
            cells, paired, monthly, provenance_status, live_parity_status
        )
    physical = bool(result["physical_mechanism_pass"])
    result["complete_case_pairing"] = "ibqdyn_both_valid"
    result["research_payoff_authorized"] = physical
    result["advance_to_option_payoff"] = physical
    result["production_live_ready"] = False
    return result


def _strict_data_manifest(
    manifest: dict[str, Any], dataset: Path, source_inventory: Path
) -> None:
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
        or int(manifest.get("eligible_events", -1)) != 16_852
        or manifest.get("dataset_sha256") != sha256_file(dataset)
        or manifest.get("source_inventory_sha256") != sha256_file(source_inventory)
        or not isinstance(gate, dict)
        or any(gate.get(field) is not True for field in required_gate)
    ):
        raise AssertionError("H-IBQDYN1 data gate/hash is not strict PASS")


def verify_freeze(
    path: Path,
    dataset: Path,
    label_source: Path,
    contract_source: Path,
    data_manifest: Path,
) -> dict[str, Any]:
    freeze = json.loads(path.read_text(encoding="utf-8"))
    manifest = json.loads(data_manifest.read_text(encoding="utf-8"))
    if (
        freeze.get("schema") != "h_ibqdyn1_frozen_physical_runner_v1"
        or freeze.get("status") != "PREEXECUTION_FROZEN"
    ):
        raise AssertionError("wrong H-IBQDYN1 frozen runner manifest")
    inputs = {
        "dataset": dataset,
        "label_source_hashes": label_source,
        "contract_source_hashes": contract_source,
        "data_manifest": data_manifest,
    }
    for name, actual in inputs.items():
        if freeze.get("inputs", {}).get(name, {}).get("sha256") != sha256_file(actual):
            raise AssertionError(f"frozen H-IBQDYN1 {name} hash mismatch")
    _strict_data_manifest(manifest, dataset, contract_source)
    active_code = {relative: sha256_file(PROJECT_ROOT / relative) for relative in CODE_CLOSURE}
    active_protocol = {
        relative: sha256_file(PROJECT_ROOT / relative) for relative in PROTOCOL_CLOSURE
    }
    if freeze.get("code_hashes") != active_code or freeze.get("protocol_hashes") != active_protocol:
        raise AssertionError("active code/protocol differs from frozen H-IBQDYN1 runner")
    expected_build = {
        relative: sha256_file(PROJECT_ROOT / relative) for relative in BUILD_CODE_CLOSURE
    }
    if manifest.get("code_hashes") != expected_build:
        raise AssertionError("H-IBQDYN1 data-build closure differs from frozen runner")
    if (
        freeze.get("feature_names") != {"F0": feature_names("F0"), "F1": feature_names("F1")}
        or freeze.get("alpha_model_allowlist") != list(ALPHA_FIELDS)
        or freeze.get("quality_fields") != list(QUALITY_FIELDS)
        or freeze.get("physical_sample_filter") != "ibqdyn_both_valid == True"
        or freeze.get("primary_model")
        != {
            "family": "logistic_regression",
            "params": LR_PARAMS,
            "preprocessing": [
                "train_only_median_imputation",
                "no_missing_indicators",
                "train_only_standardization",
            ],
        }
        or freeze.get("sensitivity_model")
        != {
            "family": "lightgbm",
            "params": LGBM_PARAMS,
            "preprocessing": [
                "train_only_median_imputation",
                "no_native_missing_branches",
            ],
            "can_rescue_primary": False,
        }
        or freeze.get("label_spec") != LABEL_SPEC
        or freeze.get("gate_spec") != GATE_SPEC
    ):
        raise AssertionError("H-IBQDYN1 frozen model/feature/gate contract mismatch")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    if (
        freeze.get("runtime_lock_sha256") != runtime["lock_sha256"]
        or freeze.get("runtime_environment_sha256") != runtime["environment_sha256"]
        or manifest.get("runtime_lock_sha256") != runtime["lock_sha256"]
        or manifest.get("runtime_environment_sha256") != runtime["environment_sha256"]
        or manifest.get("control_feature_hash") != hash_list(CONTROL_FEATURES)
        or manifest.get("alpha_feature_hash") != hash_list(ALPHA_FIELDS)
        or manifest.get("quality_field_hash") != hash_list(QUALITY_FIELDS)
        or freeze.get("historical_timestamp_provenance_status") != "CONDITIONAL"
        or freeze.get("live_feature_parity_status") != "BLOCKED"
        or freeze.get("holdout_2026_opened") is not False
        or freeze.get("production_modified") is not False
    ):
        raise AssertionError("H-IBQDYN1 runtime/provenance contract mismatch")
    label_frame = pd.read_csv(label_source, dtype={"trade_date": str})
    assert_source_inventory(label_frame)
    source_frame = pd.read_csv(contract_source, dtype={"trade_date": str})
    assert_contract_source_inventory(source_frame)
    return freeze


def assert_tracked_clean(path: Path, label: str) -> None:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--label-source-hashes", required=True)
    parser.add_argument("--contract-source-hashes", required=True)
    parser.add_argument("--data-manifest", required=True)
    parser.add_argument("--frozen-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=16)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = Path(args.output_dir)
    staging = output.with_name(output.name + ".staging")
    if output.exists() or staging.exists():
        raise FileExistsError("immutable H-IBQDYN1 physical output exists")
    frozen = Path(args.frozen_manifest)
    label_source = Path(args.label_source_hashes)
    contract_source = Path(args.contract_source_hashes)
    data_manifest = Path(args.data_manifest)
    dataset_path = Path(args.dataset)
    for path, label in (
        (frozen, "frozen runner"),
        (label_source, "label source inventory"),
        (contract_source, "contract source inventory"),
        (data_manifest, "data manifest"),
    ):
        assert_tracked_clean(path, label)
    for relative in (*CODE_CLOSURE, *PROTOCOL_CLOSURE):
        assert_tracked_clean(PROJECT_ROOT / relative, "frozen code/protocol")
    freeze = verify_freeze(
        frozen, dataset_path, label_source, contract_source, data_manifest
    )
    data = pd.read_parquet(dataset_path)
    assert_no_closed_features(list(data.columns))
    required = {
        "event_id",
        "ticker",
        "trade_date",
        "minute",
        "wall_identity",
        "wall_role",
        "candidate_wall_strike",
        "episode_id",
        "ibqdyn_both_valid",
        *raw_feature_names("F1"),
    }
    valid = data["ibqdyn_both_valid"].astype(bool)
    if (
        required.difference(data.columns)
        or len(data) != EXPECTED_EVENTS
        or data["event_id"].duplicated().any()
        or data["trade_date"].astype(str).str.startswith("2026").any()
        or not np.isfinite(
            data.loc[valid, list(raw_feature_names("F1"))]
            .apply(pd.to_numeric, errors="coerce")
            .to_numpy(dtype=float)
        ).all()
    ):
        raise AssertionError("H-IBQDYN1 physical input contract failed")
    # The first outcome access occurs only after all immutable checks above.
    staging.mkdir(parents=True, exist_ok=False)
    label_hashes = pd.read_csv(label_source, dtype={"trade_date": str})
    labeled, errors = add_future_labels(data, label_hashes, int(args.workers))
    if errors or len(labeled) != len(data) or labeled["event_id"].duplicated().any():
        raise AssertionError(f"H-IBQDYN1 physical label parity failed: {errors[:5]}")
    labeled_path = staging / "labeled_physical_events.parquet"
    labeled.to_parquet(labeled_path, index=False)
    cells, paired, monthly, predictions, calibration, models = evaluate_cells(
        labeled, staging / "models"
    )
    summary = summarize_gate(
        cells,
        paired,
        monthly,
        freeze["historical_timestamp_provenance_status"],
        freeze["live_feature_parity_status"],
    )
    paths = {
        "cells": staging / "cells.csv",
        "paired_cells": staging / "paired_cells.csv",
        "monthly_coverage": staging / "monthly_coverage.csv",
        "predictions": staging / "predictions.parquet",
        "calibration": staging / "calibration.csv",
        "model_hashes": staging / "model_hashes.csv",
        "summary": staging / "summary.json",
    }
    cells.to_csv(paths["cells"], index=False)
    paired.to_csv(paths["paired_cells"], index=False)
    monthly.to_csv(paths["monthly_coverage"], index=False)
    predictions.to_parquet(paths["predictions"], index=False)
    calibration.to_csv(paths["calibration"], index=False)
    models.to_csv(paths["model_hashes"], index=False)
    paths["summary"].write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
    )
    evaluation = {
        "schema": "h_ibqdyn1_physical_evaluation_v1",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "production_modified": False,
        "holdout_2026_used": False,
        "seed": SEED,
        "dataset_sha256": sha256_file(dataset_path),
        "frozen_manifest_sha256": sha256_file(frozen),
        "labeled_dataset_sha256": sha256_file(labeled_path),
        "artifact_hashes": {name: sha256_file(path) for name, path in paths.items()},
        "model_count": int(len(models)),
        "summary": summary,
    }
    (staging / "manifest.json").write_text(
        json.dumps(evaluation, indent=2, allow_nan=False), encoding="utf-8"
    )
    staging.rename(output)
    print(json.dumps(evaluation, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
