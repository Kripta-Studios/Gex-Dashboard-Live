"""Frozen physical F0/F1 evaluator for H-QDYN1R1.

The statistical implementation is deliberately shared with the audited
H-QSIZE1 evaluator.  This adapter changes only the predeclared measurement
block, complete-case filter and sequential family-wise gate.  Outcomes remain
inaccessible until a separately committed frozen manifest verifies the sealed
PASS_DATA_GATE dataset and all input hashes.
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
from neural.jepa.build_wall_quote_tick_dynamics_dataset import (
    AUTHORITATIVE_CODE as BUILD_CODE_CLOSURE,
    CAPTURE_CLARIFICATION,
    QDYN_FEATURES,
    QDYN_QUALITY_FIELDS,
)
from neural.jepa.build_wall_quote_tick_dynamics_sidecar import (
    EXPECTED_CANDIDATES,
    EXPECTED_CANDIDATE_SHA256,
    sha256_file,
)
from neural.jepa.surface_flow_features import CONTROL_FEATURES, END_DATE, WALL_SPECS
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED = 20260712
ENVIRONMENT_LOCK = (
    PROJECT_ROOT / "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
)
PREDECLARATION = (
    "research_papers/JEPA/WALL_QUOTE_TICK_DYNAMICS_AT_TOUCH_V1_PREDECLARATION.md"
)
CAUSAL_AMENDMENT = (
    "research_papers/JEPA/"
    "WALL_QUOTE_TICK_DYNAMICS_AT_TOUCH_V1R1_CAUSAL_AMENDMENT.md"
)
CODE_CLOSURE = (
    *BUILD_CODE_CLOSURE,
    "neural/jepa/evaluate_wall_quote_tick_dynamics_at_touch_v1.py",
    "neural/jepa/freeze_wall_quote_tick_dynamics_runner_v1.py",
    "neural/jepa/evaluate_wall_quote_size_pressure_at_touch_v1.py",
    "neural/jepa/evaluate_wall_surface_flow_at_touch_v1.py",
)
PROTOCOL_CLOSURE = (
    PREDECLARATION,
    CAUSAL_AMENDMENT,
    CAPTURE_CLARIFICATION,
    "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
)
LR_PARAMS = dict(shared.LR_PARAMS)
LGBM_PARAMS = dict(shared.LGBM_PARAMS)
GATE_SPEC = {
    **shared.GATE_SPEC,
    "maximum_wilcoxon_one_sided_p": 0.0125,
}
_SHARED_ASSERT_NO_CLOSED_FEATURES = shared.assert_no_closed_features


def raw_feature_names(arm: str) -> list[str]:
    if arm == "F0":
        return list(CONTROL_FEATURES)
    if arm == "F1":
        return [*CONTROL_FEATURES, *QDYN_FEATURES]
    raise ValueError(f"unknown arm: {arm}")


def feature_names(arm: str) -> list[str]:
    return [*raw_feature_names(arm),
            *(f"identity_{identity}" for identity in sorted(WALL_SPECS))]


def assert_no_closed_features(columns: list[str] | tuple[str, ...]) -> None:
    _SHARED_ASSERT_NO_CLOSED_FEATURES(columns)
    forbidden = sorted(set(columns).intersection(shared.QSIZE_FEATURES))
    if forbidden:
        raise AssertionError(f"closed H-QSIZE features entered H-QDYN1: {forbidden[:10]}")


def assert_qdyn_source_inventory(frame: pd.DataFrame, manifest: dict[str, Any]) -> None:
    required = {"event_id", "ticker", "trade_date", "raw_path", "raw_sha256",
                "parquet_path", "parquet_sha256", "manifest_path",
                "manifest_sha256", "rows"}
    if required.difference(frame.columns):
        raise AssertionError("H-QDYN1 source inventory schema is incomplete")
    hashes = [name for name in required if name.endswith("sha256")]
    if (len(frame) != int(manifest.get("eligible_events", -1))
            or frame["event_id"].astype(str).duplicated().any()
            or frame["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8].ge("20260101").any()
            or not frame["ticker"].astype(str).str.upper().isin(["SPXW", "QQQ", "SPY"]).all()
            or any(not frame[name].astype(str).str.fullmatch(r"[0-9a-f]{64}", case=False).all()
                   for name in hashes)
            or pd.to_numeric(frame["rows"], errors="coerce").fillna(-1).lt(0).any()):
        raise AssertionError("H-QDYN1 source inventory exact contract failed")


@contextmanager
def _shared_contract() -> Iterator[None]:
    """Bind the already-audited engine to the frozen H-QDYN contract."""
    old = (shared.QSIZE_FEATURES, shared.GATE_SPEC,
           shared.raw_feature_names, shared.feature_names,
           shared.assert_no_closed_features)
    shared.QSIZE_FEATURES = QDYN_FEATURES
    shared.GATE_SPEC = GATE_SPEC
    shared.raw_feature_names = raw_feature_names
    shared.feature_names = feature_names
    shared.assert_no_closed_features = assert_no_closed_features
    try:
        yield
    finally:
        (shared.QSIZE_FEATURES, shared.GATE_SPEC, shared.raw_feature_names,
         shared.feature_names, shared.assert_no_closed_features) = old


def evaluate_cells(labeled: pd.DataFrame, model_dir: Path):
    if "qdyn_both_valid" not in labeled:
        raise AssertionError("missing frozen qdyn_both_valid complete-case flag")
    work = labeled.copy()
    work["qsize_both_valid"] = work["qdyn_both_valid"]
    with _shared_contract():
        return shared.evaluate_cells(work, model_dir)


def summarize_gate(cells: pd.DataFrame, paired: pd.DataFrame,
                   monthly: pd.DataFrame, provenance_status: str,
                   live_parity_status: str) -> dict[str, Any]:
    with _shared_contract():
        result = shared.summarize_gate(cells, paired, monthly,
                                       provenance_status, live_parity_status)
    result["complete_case_pairing"] = "qdyn_both_valid"
    return result


def verify_freeze(path: Path, dataset: Path, label_source: Path,
                  qdyn_source: Path, data_manifest: Path) -> dict[str, Any]:
    freeze = json.loads(path.read_text(encoding="utf-8"))
    manifest = json.loads(data_manifest.read_text(encoding="utf-8"))
    if (freeze.get("schema") != "wall_quote_tick_dynamics_at_touch_frozen_runner_v1r1r1"
            or freeze.get("status") != "PREEXECUTION_FROZEN"):
        raise AssertionError("wrong H-QDYN1 frozen manifest")
    actual_inputs = {"dataset": dataset, "label_source_hashes": label_source,
                     "qdyn_source_hashes": qdyn_source, "data_manifest": data_manifest}
    for name, actual in actual_inputs.items():
        if freeze.get("inputs", {}).get(name, {}).get("sha256") != sha256_file(actual):
            raise AssertionError(f"frozen {name} hash mismatch")
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
            or not isinstance(gate, dict)
            or gate.get("coverage_pass") is not True
            or gate.get("distinctness_pass") is not True
            or gate.get("passed") is not True):
        raise AssertionError("H-QDYN1 data gate/hash is not PASS")
    if (manifest.get("source_inventory_sha256") != sha256_file(qdyn_source)
            or freeze.get("feature_names") != {"F0": feature_names("F0"),
                                                "F1": feature_names("F1")}
            or freeze.get("qdyn_model_allowlist") != list(QDYN_FEATURES)
            or freeze.get("qdyn_quality_fields") != list(QDYN_QUALITY_FIELDS)
            or freeze.get("physical_sample_filter") != "qdyn_both_valid == True"
            or freeze.get("gate_spec") != GATE_SPEC
            or freeze.get("label_spec") != shared.LABEL_SPEC):
        raise AssertionError("frozen H-QDYN1 feature/label/gate contract mismatch")
    active_code = {name: sha256_file(PROJECT_ROOT / name) for name in CODE_CLOSURE}
    active_protocol = {name: sha256_file(PROJECT_ROOT / name) for name in PROTOCOL_CLOSURE}
    if freeze.get("code_hashes") != active_code or freeze.get("protocol_hashes") != active_protocol:
        raise AssertionError("active code/protocol differs from frozen H-QDYN1 closure")
    if (manifest.get("code_hashes") != {name: sha256_file(PROJECT_ROOT / name)
                                        for name in BUILD_CODE_CLOSURE}
            or manifest.get("control_feature_hash") != shared.hash_list(CONTROL_FEATURES)
            or manifest.get("qdyn_feature_hash") != shared.hash_list(QDYN_FEATURES)
            or manifest.get("qdyn_quality_hash") != shared.hash_list(QDYN_QUALITY_FIELDS)
            or manifest.get("predeclaration_sha256") != active_protocol[PREDECLARATION]
            or manifest.get("causal_amendment_sha256") != active_protocol[CAUSAL_AMENDMENT]):
        raise AssertionError("H-QDYN1 data build closure differs from freeze")
    if manifest.get("capture_clarification_sha256") != active_protocol[CAPTURE_CLARIFICATION]:
        raise AssertionError("H-QDYN1 capture clarification differs from freeze")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    if (freeze.get("runtime_lock_sha256") != runtime["lock_sha256"]
            or manifest.get("runtime_lock_sha256") != runtime["lock_sha256"]
            or manifest.get("runtime_environment_sha256") != runtime["environment_sha256"]
            or freeze.get("historical_timestamp_provenance_status") != "CONDITIONAL"
            or freeze.get("live_feature_parity_status") != "BLOCKED"
            or freeze.get("holdout_2026_opened") is not False
            or freeze.get("production_modified") is not False):
        raise AssertionError("H-QDYN1 runtime/provenance contract mismatch")
    assert_qdyn_source_inventory(pd.read_csv(qdyn_source, dtype={"trade_date": str}), freeze)
    return freeze


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--source-hashes", required=True)
    parser.add_argument("--qdyn-source-hashes", required=True)
    parser.add_argument("--data-manifest", required=True)
    parser.add_argument("--frozen-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = Path(args.output_dir)
    if out.exists() or out.with_name(out.name + ".staging").exists():
        raise FileExistsError("immutable H-QDYN1 output/staging already exists")
    for relative in (*CODE_CLOSURE, *PROTOCOL_CLOSURE):
        shared.assert_tracked_clean(PROJECT_ROOT / relative, "frozen code/protocol")
    for value, label in ((args.frozen_manifest, "frozen manifest"),
                         (args.source_hashes, "label source inventory"),
                         (args.qdyn_source_hashes, "qdyn source inventory"),
                         (args.data_manifest, "data manifest")):
        shared.assert_tracked_clean(Path(value), label)
    freeze = verify_freeze(Path(args.frozen_manifest), Path(args.dataset),
                           Path(args.source_hashes), Path(args.qdyn_source_hashes),
                           Path(args.data_manifest))
    data = pd.read_parquet(args.dataset)
    assert_no_closed_features(list(data.columns))
    missing = sorted(set([*shared.KEY_COLUMNS, "wall_identity", "qdyn_both_valid",
                          *raw_feature_names("F1")]).difference(data.columns))
    if missing or data.trade_date.astype(str).str.startswith("2026").any() or str(data.trade_date.max()) > END_DATE:
        raise AssertionError(f"H-QDYN1 dataset columns/cutoff invalid: {missing}")
    valid = data["qdyn_both_valid"].eq(True)
    if not np.isfinite(data.loc[valid, list(QDYN_FEATURES)].apply(
            pd.to_numeric, errors="coerce").to_numpy(dtype=float)).all():
        raise AssertionError("H-QDYN1 complete cases contain missing measurements")
    # The first outcome access occurs only after every immutable check above.
    staging = out.with_name(out.name + ".staging")
    staging.mkdir(parents=True)
    source = pd.read_csv(args.source_hashes, dtype={"trade_date": str})
    shared.assert_source_inventory(source)
    labeled, errors = shared.add_future_labels(data, source, args.workers)
    if errors or len(labeled) != len(data) or labeled.duplicated(list(shared.KEY_COLUMNS)).any():
        raise AssertionError(f"physical label parity failed: {errors[:5]}")
    labeled.to_parquet(staging / "labeled_physical_episodes.parquet", index=False)
    cells, paired, monthly, predictions, calibration, models = evaluate_cells(
        labeled, staging / "models")
    summary = summarize_gate(cells, paired, monthly,
                             freeze["historical_timestamp_provenance_status"],
                             freeze["live_feature_parity_status"])
    paths = {"cells": staging / "cells.csv", "paired_cells": staging / "paired_cells.csv",
             "monthly_coverage": staging / "monthly_coverage.csv",
             "predictions": staging / "predictions.parquet",
             "calibration": staging / "calibration.csv",
             "model_hashes": staging / "model_hashes.csv", "summary": staging / "summary.json"}
    cells.to_csv(paths["cells"], index=False)
    paired.to_csv(paths["paired_cells"], index=False)
    monthly.to_csv(paths["monthly_coverage"], index=False)
    predictions.to_parquet(paths["predictions"], index=False)
    calibration.to_csv(paths["calibration"], index=False)
    models.to_csv(paths["model_hashes"], index=False)
    paths["summary"].write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    evaluation = {"schema": "wall_quote_tick_dynamics_at_touch_physical_evaluation_v1r1r1",
                  "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
                                                check=True, capture_output=True, text=True).stdout.strip(),
                  "production_modified": False, "holdout_2026_used": False, "seed": SEED,
                  "dataset_sha256": sha256_file(args.dataset),
                  "frozen_manifest_sha256": sha256_file(args.frozen_manifest),
                  "artifact_hashes": {name: sha256_file(path) for name, path in paths.items()},
                  "model_count": len(models), "summary": summary}
    (staging / "manifest.json").write_text(json.dumps(evaluation, indent=2, allow_nan=False), encoding="utf-8")
    staging.rename(out)
    print(json.dumps(evaluation, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
