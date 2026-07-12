"""Frozen physical evaluator for the predeclared H-IVSURF1 mechanism.

This program reuses the sealed wall-touch universe and the physical labels from
H-FLOW1, but it never includes an H-FLOW feature.  Logistic regression is the
primary arm; LightGBM is reported only as a non-rescuing sensitivity analysis.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.evaluate_wall_surface_flow_at_touch_v1 import (  # noqa: E402
    BOOTSTRAP_REPLICATES,
    FOLDS,
    HORIZONS,
    KEY_COLUMNS,
    LABEL_SPEC,
    add_future_labels,
    assert_source_inventory,
    hash_list,
    monthly_coverage,
    paired_day_bootstrap,
    probability_metrics,
    sha256_file,
)
from neural.jepa.surface_flow_features import (  # noqa: E402
    CONTROL_FEATURES,
    END_DATE,
    FLOW_FEATURES,
    WALL_SPECS,
)
from neural.jepa.iv_surface_deformation_features import (  # noqa: E402
    IV_SURFACE_ALLOWLIST,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402

SEED = 20260712
ENVIRONMENT_LOCK = (
    PROJECT_ROOT / "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
)
PREDECLARATION = (
    PROJECT_ROOT
    / "research_papers/JEPA/WALL_IV_SURFACE_DEFORMATION_AT_TOUCH_V1_PREDECLARATION.md"
)
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
LR_PARAMS: dict[str, Any] = {
    "C": 1.0,
    "penalty": "l2",
    "solver": "lbfgs",
    "max_iter": 5000,
    "random_state": SEED,
}
LGBM_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "n_estimators": 300,
    "learning_rate": 0.03,
    "num_leaves": 15,
    "min_child_samples": 100,
    "colsample_bytree": 0.8,
    "subsample": 0.8,
    "subsample_freq": 1,
    "reg_alpha": 0.0,
    "reg_lambda": 1.0,
    "random_state": SEED,
    "n_jobs": 28,
    "deterministic": True,
    "force_col_wise": True,
    "verbosity": -1,
}
GATE_SPEC = {
    "planned_paired_cells": 24,
    "minimum_auc_wins": 16,
    "minimum_median_auc_delta": 0.010,
    "maximum_wilcoxon_one_sided_p": 0.025,
    "paired_test_unit": "ticker_fold_median_across_horizons",
    "ticker_minimum_wins": 5,
    "ticker_minimum_median_f1_auc": 0.55,
    "primary_horizons": [30, 60],
    "ticker_primary_minimum_wins": 3,
    "minimum_monthly_resolved_episodes": 18,
    "maximum_joint_ap_logloss_losses": 12,
    "sensitivity_minimum_wins": 13,
    "sensitivity_requires_positive_median_auc_delta": True,
    "sensitivity_can_rescue_primary": False,
}


def raw_feature_names(arm: str) -> list[str]:
    if arm == "F0":
        return list(CONTROL_FEATURES)
    if arm == "F1":
        return [*CONTROL_FEATURES, *IV_SURFACE_ALLOWLIST]
    raise ValueError(f"unknown arm: {arm}")


def feature_names(arm: str) -> list[str]:
    return [
        *raw_feature_names(arm),
        *(f"identity_{identity}" for identity in sorted(WALL_SPECS)),
    ]


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
        raise AssertionError(
            f"{label} must be committed and clean: {relative}: {dirty}"
        )


def assert_no_flow_features(columns: list[str] | tuple[str, ...]) -> None:
    forbidden = sorted(set(columns).intersection(FLOW_FEATURES))
    if forbidden:
        raise AssertionError(f"H-FLOW features entered H-IVSURF1: {forbidden[:10]}")


def model_frame(frame: pd.DataFrame, arm: str) -> pd.DataFrame:
    names = raw_feature_names(arm)
    missing = sorted(set(names) - set(frame.columns))
    if missing:
        raise AssertionError(f"missing frozen {arm} features: {missing}")
    assert_no_flow_features(names)
    if "wall_identity" not in frame:
        raise AssertionError("missing frozen wall_identity encoding source")
    matrix = frame[names].apply(pd.to_numeric, errors="coerce").reset_index(drop=True)
    identities = frame["wall_identity"].astype(str).str.split("+")
    for identity in sorted(WALL_SPECS):
        matrix[f"identity_{identity}"] = identities.map(
            lambda values: float(identity in values)
        ).to_numpy()
    return matrix[feature_names(arm)].replace([np.inf, -np.inf], np.nan)


def class_weights(y: np.ndarray) -> np.ndarray:
    positive = max(int((y == 1).sum()), 1)
    negative = max(int((y == 0).sum()), 1)
    return np.where(y == 1, len(y) / (2.0 * positive), len(y) / (2.0 * negative))


def make_lr_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "imputer",
                SimpleImputer(
                    strategy="median", add_indicator=True, keep_empty_features=True
                ),
            ),
            ("standardizer", StandardScaler()),
            ("classifier", LogisticRegression(**LR_PARAMS)),
        ]
    )


def fit_model(
    train: pd.DataFrame,
    test: pd.DataFrame,
    target: str,
    arm: str,
    family: str,
    path: Path,
) -> tuple[dict[str, Any], np.ndarray | None, list[dict[str, Any]]]:
    y_train = train[target].astype(int).to_numpy()
    y_test = test[target].astype(int).to_numpy()
    result: dict[str, Any] = {
        "arm": arm,
        "family": family,
        "train_rows": len(train),
        "test_rows": len(test),
        "valid": False,
    }
    if (
        not len(train)
        or not len(test)
        or len(np.unique(y_train)) < 2
        or len(np.unique(y_test)) < 2
    ):
        return result, None, []
    x_train, x_test = model_frame(train, arm), model_frame(test, arm)
    weights = class_weights(y_train)
    path.parent.mkdir(parents=True, exist_ok=True)
    if family == "lr":
        model = make_lr_pipeline()
        model.fit(x_train, y_train, classifier__sample_weight=weights)
        probability = model.predict_proba(x_test)[:, 1]
        joblib.dump(model, path)
    elif family == "lgbm_sensitivity":
        model = lgb.LGBMClassifier(**LGBM_PARAMS)
        model.fit(x_train, y_train, sample_weight=weights)
        probability = model.predict_proba(x_test)[:, 1]
        model.booster_.save_model(str(path))
    else:
        raise ValueError(f"unknown family: {family}")
    metrics, calibration = probability_metrics(y_test, probability)
    result.update(
        {
            "valid": True,
            **metrics,
            "model_path": str(path),
            "model_sha256": sha256_file(path),
            "model_feature_hash": hash_list(feature_names(arm)),
        }
    )
    return result, probability, calibration


def evaluate_cells(labeled: pd.DataFrame, model_dir: Path):
    cells, pairs, months, predictions, calibrations, models = [], [], [], [], [], []
    offsets = {"SPXW": 1000, "QQQ": 2000, "SPY": 3000}
    for family, suffix in (("lr", "joblib"), ("lgbm_sensitivity", "txt")):
        for fold_spec in FOLDS:
            fold = str(fold_spec["fold"])
            for ticker in ("SPXW", "QQQ", "SPY"):
                ticker_df = labeled[labeled["ticker"].eq(ticker)]
                train_base = ticker_df[
                    ticker_df["trade_date"].le(fold_spec["train_end"])
                ]
                test_base = ticker_df[
                    ticker_df["trade_date"].between(
                        fold_spec["test_start"], fold_spec["test_end"]
                    )
                ]
                for horizon in HORIZONS:
                    target = f"resolved_rejection_{horizon}m"
                    train = train_base[
                        pd.to_numeric(train_base[target], errors="coerce").notna()
                    ].copy()
                    test = test_base[
                        pd.to_numeric(test_base[target], errors="coerce").notna()
                    ].copy()
                    if family == "lr":
                        months.extend(
                            monthly_coverage(test_base, target, fold, ticker, horizon)
                        )
                    cell_id = f"{family}_{fold}_{ticker}_{horizon}m"
                    arm_results, probabilities = {}, {}
                    for arm in ("F0", "F1"):
                        path = model_dir / f"{cell_id}_{arm}.{suffix}"
                        result, probability, calibration = fit_model(
                            train, test, target, arm, family, path
                        )
                        row = {
                            "cell_id": cell_id,
                            "fold": fold,
                            "ticker": ticker,
                            "horizon": horizon,
                            "target": target,
                            **result,
                        }
                        cells.append(row)
                        arm_results[arm] = row
                        probabilities[arm] = probability
                        if result["valid"]:
                            models.append(
                                {
                                    "cell_id": cell_id,
                                    "family": family,
                                    "arm": arm,
                                    "path": str(path),
                                    "sha256": result["model_sha256"],
                                    "feature_hash": result["model_feature_hash"],
                                    "seed": SEED,
                                }
                            )
                        calibrations.extend(
                            {
                                "cell_id": cell_id,
                                "family": family,
                                "arm": arm,
                                "fold": fold,
                                "ticker": ticker,
                                "horizon": horizon,
                                **r,
                            }
                            for r in calibration
                        )
                    valid = bool(
                        arm_results["F0"].get("valid")
                        and arm_results["F1"].get("valid")
                    )
                    pair = {
                        "cell_id": cell_id,
                        "family": family,
                        "fold": fold,
                        "ticker": ticker,
                        "horizon": horizon,
                        "valid_pair": valid,
                    }
                    metric_outputs = {
                        "auc_delta": "roc_auc",
                        "average_precision_delta": "average_precision",
                        "log_loss_delta": "log_loss",
                        "brier_delta": "brier",
                        "balanced_accuracy_delta": "balanced_accuracy_05",
                        "spearman_delta": "spearman",
                        "ece_delta": "ece_10",
                    }
                    for output_name, metric in metric_outputs.items():
                        pair[output_name] = (
                            float(arm_results["F1"][metric] - arm_results["F0"][metric])
                            if valid
                            else None
                        )
                    if valid:
                        pair.update(
                            paired_day_bootstrap(
                                test,
                                test[target].astype(int).to_numpy(),
                                probabilities["F0"],
                                probabilities["F1"],
                                seed=SEED + int(fold) + offsets[ticker] + horizon,
                            )
                        )
                        pred = test[
                            [
                                *KEY_COLUMNS,
                                "episode_id",
                                "wall_role",
                                "candidate_wall_strike",
                            ]
                        ].copy()
                        pred["family"], pred["fold"], pred["horizon"] = (
                            family,
                            fold,
                            horizon,
                        )
                        pred["target"] = test[target].astype(int).to_numpy()
                        pred["probability_f0"], pred["probability_f1"] = (
                            probabilities["F0"],
                            probabilities["F1"],
                        )
                        predictions.append(pred)
                    pairs.append(pair)
    return tuple(
        pd.DataFrame(x)
        for x in (
            cells,
            pairs,
            months,
        )
    ) + (
        pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame(),
        pd.DataFrame(calibrations),
        pd.DataFrame(models),
    )


def _family_gate(
    cells: pd.DataFrame, paired: pd.DataFrame, family: str
) -> dict[str, Any]:
    p = paired[paired["family"].eq(family)].copy()
    c = cells[cells["family"].eq(family)]
    valid = p["valid_pair"].astype(bool)
    deltas = pd.to_numeric(p.loc[valid, "auc_delta"], errors="coerce").dropna()
    clusters = p.loc[valid].groupby(["ticker", "fold"])["auc_delta"].median().dropna()
    pvalue = (
        float(wilcoxon(clusters, alternative="greater").pvalue)
        if len(clusters) == 6 and not np.allclose(clusters, 0)
        else 1.0
    )
    wins = int((pd.to_numeric(p["auc_delta"], errors="coerce") > 0).sum())
    ticker_summary, ticker_pass = {}, True
    f1 = c[c["arm"].eq("F1")].set_index("cell_id")
    for ticker, part in p.groupby("ticker", sort=True):
        part = part[part["valid_pair"]]
        primary = part[part["horizon"].isin(GATE_SPEC["primary_horizons"])]
        auc = (
            pd.to_numeric(f1.loc[part.cell_id, "roc_auc"], errors="coerce")
            if len(part)
            else pd.Series(dtype=float)
        )
        primary_auc = (
            pd.to_numeric(f1.loc[primary.cell_id, "roc_auc"], errors="coerce")
            if len(primary)
            else pd.Series(dtype=float)
        )
        data = {
            "valid_cells": len(part),
            "wins": int((part.auc_delta > 0).sum()),
            "median_auc_delta": float(part.auc_delta.median()) if len(part) else None,
            "median_f1_auc": float(auc.median()) if len(auc) else None,
            "primary_valid_cells": len(primary),
            "primary_wins": int((primary.auc_delta > 0).sum()),
            "primary_median_auc_delta": float(primary.auc_delta.median())
            if len(primary)
            else None,
            "primary_median_f1_auc": float(primary_auc.median())
            if len(primary_auc)
            else None,
        }
        data["passed"] = bool(
            data["valid_cells"] == 8
            and data["wins"] >= 5
            and data["median_auc_delta"] > 0
            and data["median_f1_auc"] >= 0.55
            and data["primary_valid_cells"] == 4
            and data["primary_wins"] >= 3
            and data["primary_median_auc_delta"] > 0
            and data["primary_median_f1_auc"] >= 0.55
        )
        ticker_pass &= data["passed"]
        ticker_summary[ticker] = data
    ap = pd.to_numeric(p.average_precision_delta, errors="coerce")
    ll = pd.to_numeric(p.log_loss_delta, errors="coerce")
    return {
        "valid_paired_cells": int(valid.sum()),
        "wins": wins,
        "median_auc_delta": float(deltas.median()) if len(deltas) else None,
        "wilcoxon_one_sided_p": pvalue,
        "ticker_summary": ticker_summary,
        "ticker_pass": bool(ticker_pass),
        "joint_average_precision_logloss_losses": int(
            (~valid | ((ap < 0) & (ll > 0))).sum()
        ),
    }


def summarize_gate(
    cells: pd.DataFrame,
    paired: pd.DataFrame,
    monthly: pd.DataFrame,
    provenance_status: str,
    live_parity_status: str,
) -> dict[str, Any]:
    primary = _family_gate(cells, paired, "lr")
    sensitivity = _family_gate(cells, paired, "lgbm_sensitivity")
    primary_months = monthly[monthly["horizon"].isin(GATE_SPEC["primary_horizons"])]
    frequency = bool(
        len(primary_months) == 144
        and primary_months.resolved_episodes.ge(18).all()
        and primary_months.both_classes.all()
    )
    primary_pass = bool(
        primary["valid_paired_cells"] == 24
        and primary["wins"] >= 16
        and primary["median_auc_delta"] >= 0.010
        and primary["wilcoxon_one_sided_p"] < 0.025
        and primary["ticker_pass"]
        and primary["joint_average_precision_logloss_losses"] <= 12
        and frequency
    )
    sensitivity_pass = bool(
        sensitivity["valid_paired_cells"] == 24
        and sensitivity["wins"] >= 13
        and sensitivity["median_auc_delta"] > 0
    )
    physical = bool(primary_pass and sensitivity_pass)
    return {
        "gate_spec": GATE_SPEC,
        "primary_lr": primary,
        "lgbm_sensitivity": sensitivity,
        "frequency_pass": frequency,
        "primary_physical_pass": primary_pass,
        "sensitivity_pass": sensitivity_pass,
        "physical_mechanism_pass": physical,
        "sensitivity_can_rescue_primary": False,
        "historical_timestamp_provenance_status": provenance_status,
        "live_feature_parity_status": live_parity_status,
        "authoritative_physical_success": bool(
            physical and provenance_status == "PASS"
        ),
        "advance_to_option_payoff": bool(
            physical and provenance_status == "PASS" and live_parity_status == "PASS"
        ),
        "production_live_ready": False,
    }


def verify_freeze(
    path: Path, dataset: Path, source_hashes: Path, data_manifest: Path
) -> dict[str, Any]:
    freeze = json.loads(path.read_text(encoding="utf-8"))
    manifest = json.loads(data_manifest.read_text(encoding="utf-8"))
    if (
        freeze.get("schema") != "wall_iv_surface_at_touch_frozen_runner_v1"
        or freeze.get("status") != "PREEXECUTION_FROZEN"
    ):
        raise AssertionError("wrong H-IVSURF1 frozen manifest")
    for key, actual in (
        ("dataset", dataset),
        ("source_file_hashes", source_hashes),
        ("data_manifest", data_manifest),
    ):
        if freeze["inputs"][key]["sha256"] != sha256_file(actual):
            raise AssertionError(f"frozen {key} hash mismatch")
    if manifest.get("status") != "PASS_DATA_GATE" or manifest.get(
        "dataset_sha256"
    ) != sha256_file(dataset):
        raise AssertionError("H-IVSURF1 data gate/hash is not PASS")
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
        raise AssertionError(
            "H-IVSURF1 PASS manifest has non-strict data-gate booleans"
        )
    if manifest.get("source_file_hashes_sha256") != sha256_file(source_hashes):
        raise AssertionError("H-IVSURF1 source inventory differs from data manifest")
    if freeze.get("feature_names") != {
        "F0": feature_names("F0"),
        "F1": feature_names("F1"),
    }:
        raise AssertionError("frozen feature allowlist mismatch")
    active_code = {p: sha256_file(PROJECT_ROOT / p) for p in CODE_CLOSURE}
    active_protocol = {p: sha256_file(PROJECT_ROOT / p) for p in PROTOCOL_CLOSURE}
    if (
        freeze.get("code_hashes") != active_code
        or freeze.get("protocol_hashes") != active_protocol
    ):
        raise AssertionError(
            "active code/protocol differs from frozen H-IVSURF1 closure"
        )
    expected_build_hashes = {
        "neural/jepa/build_wall_iv_surface_deformation_dataset.py": active_code[
            "neural/jepa/build_wall_iv_surface_deformation_dataset.py"
        ],
        "neural/jepa/iv_surface_deformation_features.py": active_code[
            "neural/jepa/iv_surface_deformation_features.py"
        ],
        **active_protocol,
    }
    if manifest.get("code_hashes") != expected_build_hashes:
        raise AssertionError("data manifest build code/protocol hash closure mismatch")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    if (
        manifest.get("runtime_lock_sha256") != runtime["lock_sha256"]
        or manifest.get("runtime_environment") != runtime["environment"]
        or manifest.get("runtime_environment_sha256") != runtime["environment_sha256"]
    ):
        raise AssertionError("data manifest runtime differs from frozen runtime")
    if (
        manifest.get("control_feature_hash") != hash_list(CONTROL_FEATURES)
        or manifest.get("iv_surface_feature_hash") != hash_list(IV_SURFACE_ALLOWLIST)
        or manifest.get("predeclaration_sha256")
        != active_protocol[
            "research_papers/JEPA/WALL_IV_SURFACE_DEFORMATION_AT_TOUCH_V1_PREDECLARATION.md"
        ]
    ):
        raise AssertionError("data manifest feature/protocol hashes differ from freeze")
    if freeze.get("primary_model") != {
        "family": "logistic_regression",
        "params": LR_PARAMS,
        "preprocessing": [
            "train_only_median_imputation",
            "missing_indicators",
            "train_only_standardization",
        ],
    }:
        raise AssertionError("primary LR contract differs from freeze")
    if freeze.get("sensitivity_model") != {
        "family": "lightgbm",
        "params": LGBM_PARAMS,
        "can_rescue_primary": False,
    }:
        raise AssertionError("LightGBM sensitivity contract differs from freeze")
    if freeze.get("gate_spec") != GATE_SPEC or freeze.get("label_spec") != LABEL_SPEC:
        raise AssertionError("physical labels/gates differ from freeze")
    if freeze.get("runtime_lock_sha256") != sha256_file(ENVIRONMENT_LOCK):
        raise AssertionError("runtime lock differs from freeze")
    native, exact = (
        manifest.get("native_quote_provenance"),
        manifest.get("exact_greek_repair_provenance"),
    )
    if (
        freeze.get("native_quote_provenance") != native
        or freeze.get("exact_greek_repair_provenance") != exact
    ):
        raise AssertionError("sealed quote/exact-Greek provenance differs from freeze")
    if not isinstance(native, dict) or int(native.get("sessions", -1)) != 1441:
        raise AssertionError("native quote provenance is incomplete")
    if (
        not isinstance(exact, dict)
        or exact.get("status") != "PASS_EXACT_GREEK_REPAIR_ARTIFACTS"
        or exact.get("frozen_hashes_match") is not True
        or exact.get("historical_provenance")
        != "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION"
    ):
        raise AssertionError("exact-Greek repair provenance is incomplete")
    if freeze.get("historical_timestamp_provenance_status") == "PASS":
        raise AssertionError("conditional reconstruction cannot be authoritative PASS")
    if (
        freeze.get("holdout_2026_opened") is not False
        or freeze.get("production_modified") is not False
    ):
        raise AssertionError("freeze does not attest untouched 2026/production")
    return freeze


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", required=True)
    p.add_argument("--source-hashes", required=True)
    p.add_argument("--data-manifest", required=True)
    p.add_argument("--frozen-manifest", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--workers", type=int, default=16)
    return p.parse_args()


def main() -> int:
    a = parse_args()
    out = Path(a.output_dir)
    if out.exists():
        raise FileExistsError(f"immutable evaluation output exists: {out}")
    staging = out.with_name(out.name + ".staging")
    if staging.exists():
        raise FileExistsError(f"staging exists: {staging}")
    for relative in (*CODE_CLOSURE, *PROTOCOL_CLOSURE):
        assert_tracked_clean(PROJECT_ROOT / relative, "frozen code/protocol")
    for path, label in (
        (Path(a.frozen_manifest), "frozen manifest"),
        (Path(a.source_hashes), "source inventory"),
        (Path(a.data_manifest), "data manifest"),
    ):
        assert_tracked_clean(path, label)
    freeze = verify_freeze(
        Path(a.frozen_manifest),
        Path(a.dataset),
        Path(a.source_hashes),
        Path(a.data_manifest),
    )
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    data = pd.read_parquet(a.dataset)
    assert_no_flow_features(list(data.columns))
    missing_columns = sorted(
        set([*KEY_COLUMNS, "wall_identity", *raw_feature_names("F1")])
        - set(data.columns)
    )
    if missing_columns:
        raise AssertionError(
            f"H-IVSURF1 dataset missing frozen columns: {missing_columns}"
        )
    if (
        data.trade_date.astype(str).str.startswith("2026").any()
        or str(data.trade_date.max()) > END_DATE
    ):
        raise AssertionError("2026/post-cutoff entered H-IVSURF1")
    source = pd.read_csv(a.source_hashes, dtype={"trade_date": str})
    assert_source_inventory(source)
    staging.mkdir(parents=True)
    labeled, errors = add_future_labels(data, source, a.workers)
    if (
        errors
        or len(labeled) != len(data)
        or labeled.duplicated(list(KEY_COLUMNS)).any()
    ):
        raise AssertionError(f"physical label parity failed: errors={errors[:5]}")
    labeled.to_parquet(staging / "labeled_physical_episodes.parquet", index=False)
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
    if "model_path" in cells:
        cells["model_path"] = cells["model_path"].map(
            lambda value: (
                f"models/{Path(str(value)).name}"
                if pd.notna(value) and str(value)
                else value
            )
        )
    if "path" in models:
        models["path"] = models["path"].map(
            lambda value: f"models/{Path(str(value)).name}"
        )
    paths = {
        "labels": staging / "labeled_physical_episodes.parquet",
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
    manifest = {
        "schema": "wall_iv_surface_at_touch_physical_evaluation_v1",
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
        "dataset_sha256": sha256_file(a.dataset),
        "frozen_manifest_sha256": sha256_file(a.frozen_manifest),
        "runner_sha256": sha256_file(__file__),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "labeled_rows": len(labeled),
        "labeled_rows_by_ticker": labeled.groupby("ticker", observed=True)
        .size()
        .astype(int)
        .to_dict(),
        "label_errors": errors,
        "artifact_hashes": {name: sha256_file(path) for name, path in paths.items()},
        "model_count": len(models),
        "model_set_sha256": (
            hash_list(models.sha256.astype(str).tolist()) if len(models) else None
        ),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "summary": summary,
    }
    (staging / "manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8"
    )
    staging.rename(out)
    print(json.dumps(manifest, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
