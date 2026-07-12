"""Frozen physical evaluator for the predeclared H-QSIZE1 mechanism.

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
from neural.jepa.build_wall_surface_flow_dataset import (  # noqa: E402
    EXPECTED_SESSION_KEY_SHA256,
    session_key_hash,
)
from neural.jepa.surface_flow_features import (  # noqa: E402
    CONTROL_FEATURES,
    END_DATE,
    FLOW_FEATURES,
    WALL_SPECS,
)
from neural.jepa.quote_size_pressure_features import (  # noqa: E402
    QSIZE_FEATURES,
    QSIZE_QUALITY_FIELDS,
)
from neural.jepa.iv_surface_deformation_features import IV_SURFACE_ALLOWLIST  # noqa: E402
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402

SEED = 20260712
ENVIRONMENT_LOCK = (
    PROJECT_ROOT / "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
)
PREDECLARATION = (
    PROJECT_ROOT
    / "research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_PREDECLARATION.md"
)
BUILD_CODE_CLOSURE = (
    "neural/jepa/build_wall_quote_size_pressure_dataset.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    "neural/jepa/build_wall_quote_size_complement_sidecar.py",
    "neural/jepa/build_wall_surface_flow_dataset.py",
    "neural/jepa/quote_size_pressure_features.py",
    "neural/jepa/surface_flow_features.py",
    "neural/jepa/wall_surface_flow_environment.py",
)
CODE_CLOSURE = (
    *BUILD_CODE_CLOSURE,
    "neural/jepa/evaluate_wall_quote_size_pressure_at_touch_v1.py",
    "neural/jepa/freeze_wall_quote_size_pressure_runner_v1.py",
    "neural/jepa/evaluate_wall_surface_flow_at_touch_v1.py",
    "neural/jepa/iv_surface_deformation_features.py",
)
PROTOCOL_CLOSURE = (
    "research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_PREDECLARATION.md",
    "research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_CAUSAL_AMENDMENT.md",
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
    "maximum_wilcoxon_one_sided_p": 0.0167,
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
    "expected_primary_month_cells": 144,
}


def raw_feature_names(arm: str) -> list[str]:
    if arm == "F0":
        return list(CONTROL_FEATURES)
    if arm == "F1":
        return [*CONTROL_FEATURES, *QSIZE_FEATURES]
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


def assert_qsize_source_inventory(frame: pd.DataFrame) -> None:
    required = {
        "ticker",
        "trade_date",
        "origin",
        "greeks_sha256",
        "quotes_sha256",
        "raw_response_sha256",
        "session_manifest_sha256",
        "rows",
    }
    if required.difference(frame.columns):
        raise AssertionError("H-QSIZE1 source inventory schema is incomplete")
    work = frame.copy()
    work["ticker"] = work["ticker"].astype(str).str.upper()
    work["trade_date"] = (
        work["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    )
    origin_counts = work["origin"].astype(str).value_counts().to_dict()
    hash_columns = [name for name in required if name.endswith("sha256")]
    hashes_valid = all(
        work[column]
        .astype(str)
        .str.fullmatch(r"[0-9a-f]{64}", case=False)
        .all()
        for column in hash_columns
    )
    if (
        len(work) != 2519
        or work.duplicated(["ticker", "trade_date"]).any()
        or not work["ticker"].isin(["SPXW", "QQQ", "SPY"]).all()
        or work["trade_date"].ge("20260101").any()
        or session_key_hash(work) != EXPECTED_SESSION_KEY_SHA256
        or origin_counts != {"fallback": 1441, "complement": 1078}
        or not hashes_valid
        or pd.to_numeric(work["rows"], errors="coerce").fillna(0).le(0).any()
    ):
        raise AssertionError("H-QSIZE1 source inventory exact contract failed")


def assert_no_closed_features(columns: list[str] | tuple[str, ...]) -> None:
    forbidden = sorted(set(columns).intersection((*FLOW_FEATURES, *IV_SURFACE_ALLOWLIST)))
    if forbidden:
        raise AssertionError(f"closed H-FLOW/H-IVSURF features entered H-QSIZE1: {forbidden[:10]}")


def model_frame(frame: pd.DataFrame, arm: str) -> pd.DataFrame:
    names = raw_feature_names(arm)
    missing = sorted(set(names) - set(frame.columns))
    if missing:
        raise AssertionError(f"missing frozen {arm} features: {missing}")
    assert_no_closed_features(names)
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
                    strategy="median", add_indicator=False, keep_empty_features=True
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
        imputer = SimpleImputer(
            strategy="median", add_indicator=False, keep_empty_features=True
        )
        x_train = pd.DataFrame(
            imputer.fit_transform(x_train), columns=x_train.columns, index=x_train.index
        )
        x_test = pd.DataFrame(
            imputer.transform(x_test), columns=x_test.columns, index=x_test.index
        )
        model = lgb.LGBMClassifier(**LGBM_PARAMS)
        model.fit(x_train, y_train, sample_weight=weights)
        probability = model.predict_proba(x_test)[:, 1]
        model.booster_.save_model(str(path))
        imputer_path = path.with_suffix(path.suffix + ".imputer.joblib")
        joblib.dump(imputer, imputer_path)
        result["imputer_path"] = str(imputer_path)
        result["imputer_sha256"] = sha256_file(imputer_path)
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
                ticker_df = labeled[
                    labeled["ticker"].eq(ticker)
                    & labeled["qsize_both_valid"].eq(True)  # noqa: E712
                ]
                if not np.isfinite(
                    ticker_df[list(QSIZE_FEATURES)]
                    .apply(pd.to_numeric, errors="coerce")
                    .to_numpy(dtype=float)
                ).all():
                    raise AssertionError("H-QSIZE1 both-valid row has missing measurements")
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
                                    "preprocessor_path": result.get("imputer_path"),
                                    "preprocessor_sha256": result.get("imputer_sha256"),
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
            data["valid_cells"] == GATE_SPEC["planned_paired_cells"] // 3
            and data["wins"] >= GATE_SPEC["ticker_minimum_wins"]
            and data["median_auc_delta"] > 0
            and data["median_f1_auc"] >= GATE_SPEC["ticker_minimum_median_f1_auc"]
            and data["primary_valid_cells"] == len(FOLDS) * len(
                GATE_SPEC["primary_horizons"]
            )
            and data["primary_wins"] >= GATE_SPEC["ticker_primary_minimum_wins"]
            and data["primary_median_auc_delta"] > 0
            and data["primary_median_f1_auc"]
            >= GATE_SPEC["ticker_minimum_median_f1_auc"]
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
        len(primary_months) == GATE_SPEC["expected_primary_month_cells"]
        and primary_months.resolved_episodes.ge(
            GATE_SPEC["minimum_monthly_resolved_episodes"]
        ).all()
        and primary_months.both_classes.all()
    )
    primary_pass = bool(
        primary["valid_paired_cells"] == GATE_SPEC["planned_paired_cells"]
        and primary["wins"] >= GATE_SPEC["minimum_auc_wins"]
        and primary["median_auc_delta"] >= GATE_SPEC["minimum_median_auc_delta"]
        and primary["wilcoxon_one_sided_p"]
        < GATE_SPEC["maximum_wilcoxon_one_sided_p"]
        and primary["ticker_pass"]
        and primary["joint_average_precision_logloss_losses"]
        <= GATE_SPEC["maximum_joint_ap_logloss_losses"]
        and frequency
    )
    sensitivity_pass = bool(
        sensitivity["valid_paired_cells"] == GATE_SPEC["planned_paired_cells"]
        and sensitivity["wins"] >= GATE_SPEC["sensitivity_minimum_wins"]
        and (
            sensitivity["median_auc_delta"] > 0
            if GATE_SPEC["sensitivity_requires_positive_median_auc_delta"]
            else True
        )
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
        "complete_case_pairing": "qsize_both_valid",
    }


def verify_freeze(
    path: Path,
    dataset: Path,
    label_source_hashes: Path,
    qsize_source_hashes: Path,
    data_manifest: Path,
) -> dict[str, Any]:
    freeze = json.loads(path.read_text(encoding="utf-8"))
    manifest = json.loads(data_manifest.read_text(encoding="utf-8"))
    if (
        freeze.get("schema") != "wall_quote_size_pressure_at_touch_frozen_runner_v1"
        or freeze.get("status") != "PREEXECUTION_FROZEN"
    ):
        raise AssertionError("wrong H-QSIZE1 frozen manifest")
    for key, actual in (
        ("dataset", dataset),
        ("label_source_hashes", label_source_hashes),
        ("qsize_source_hashes", qsize_source_hashes),
        ("data_manifest", data_manifest),
    ):
        if freeze["inputs"][key]["sha256"] != sha256_file(actual):
            raise AssertionError(f"frozen {key} hash mismatch")
    if (
        manifest.get("schema") != "wall_quote_size_pressure_at_touch_dataset_v1"
        or manifest.get("status") != "PASS_DATA_GATE"
        or manifest.get("outcome_free") is not True
        or manifest.get("holdout_2026_used") is not False
        or manifest.get("production_modified") is not False
        or manifest.get("errors") != []
        or int(manifest.get("rows", -1)) != 10683
        or manifest.get("candidate_sha256")
        != "6d27fdeb44422daa95aa79f777044e68276a2fe374c9bd847cd475d9dccfdb5b"
        or manifest.get("dataset_sha256") != sha256_file(dataset)
    ):
        raise AssertionError("H-QSIZE1 data gate/hash is not PASS")
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
            "H-QSIZE1 PASS manifest has non-strict data-gate booleans"
        )
    if manifest.get("source_inventory_sha256") != sha256_file(qsize_source_hashes):
        raise AssertionError("H-QSIZE1 source inventory differs from data manifest")
    if freeze.get("feature_names") != {
        "F0": feature_names("F0"),
        "F1": feature_names("F1"),
    }:
        raise AssertionError("frozen feature allowlist mismatch")
    if (
        freeze.get("qsize_model_allowlist") != list(QSIZE_FEATURES)
        or freeze.get("qsize_quality_fields") != list(QSIZE_QUALITY_FIELDS)
        or freeze.get("physical_sample_filter") != "qsize_both_valid == True"
    ):
        raise AssertionError("frozen H-QSIZE1 measurement/quality contract mismatch")
    active_code = {p: sha256_file(PROJECT_ROOT / p) for p in CODE_CLOSURE}
    active_protocol = {p: sha256_file(PROJECT_ROOT / p) for p in PROTOCOL_CLOSURE}
    if (
        freeze.get("code_hashes") != active_code
        or freeze.get("protocol_hashes") != active_protocol
    ):
        raise AssertionError(
            "active code/protocol differs from frozen H-QSIZE1 closure"
        )
    expected_build_hashes = {
        **{path: active_code[path] for path in BUILD_CODE_CLOSURE},
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
        or manifest.get("qsize_feature_hash") != hash_list(QSIZE_FEATURES)
        or manifest.get("qsize_quality_hash") != hash_list(QSIZE_QUALITY_FIELDS)
        or manifest.get("predeclaration_sha256")
        != active_protocol[
            "research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_PREDECLARATION.md"
        ]
        or manifest.get("causal_amendment_sha256")
        != active_protocol[
            "research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_CAUSAL_AMENDMENT.md"
        ]
    ):
        raise AssertionError("data manifest feature/protocol hashes differ from freeze")
    if freeze.get("primary_model") != {
        "family": "logistic_regression",
        "params": LR_PARAMS,
        "preprocessing": [
            "train_only_median_imputation",
            "no_missing_indicators",
            "train_only_standardization",
        ],
    }:
        raise AssertionError("primary LR contract differs from freeze")
    if freeze.get("sensitivity_model") != {
        "family": "lightgbm",
        "params": LGBM_PARAMS,
        "preprocessing": [
            "train_only_median_imputation",
            "no_native_missing_branches",
        ],
        "can_rescue_primary": False,
    }:
        raise AssertionError("LightGBM sensitivity contract differs from freeze")
    if freeze.get("gate_spec") != GATE_SPEC or freeze.get("label_spec") != LABEL_SPEC:
        raise AssertionError("physical labels/gates differ from freeze")
    if freeze.get("runtime_lock_sha256") != sha256_file(ENVIRONMENT_LOCK):
        raise AssertionError("runtime lock differs from freeze")
    sidecar = manifest.get("sidecar_provenance")
    if freeze.get("sidecar_provenance") != sidecar:
        raise AssertionError("sealed H-QSIZE1 sidecar provenance differs from freeze")
    if (
        not isinstance(sidecar, dict)
        or int(sidecar.get("sessions", -1)) != 2519
        or int(sidecar.get("fallback_sessions", -1)) != 1441
        or int(sidecar.get("complement_sessions", -1)) != 1078
        or sidecar.get("session_key_sha256") != EXPECTED_SESSION_KEY_SHA256
        or sidecar.get("historical_provenance")
        != "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION"
    ):
        raise AssertionError("H-QSIZE1 sidecar provenance is incomplete")
    if (
        freeze.get("historical_timestamp_provenance_status") != "CONDITIONAL"
        or freeze.get("live_feature_parity_status") != "BLOCKED"
    ):
        raise AssertionError("H-QSIZE1 provenance/live parity was promoted without evidence")
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
    p.add_argument("--qsize-source-hashes", required=True)
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
        (Path(a.qsize_source_hashes), "qsize source inventory"),
        (Path(a.data_manifest), "data manifest"),
    ):
        assert_tracked_clean(path, label)
    freeze = verify_freeze(
        Path(a.frozen_manifest),
        Path(a.dataset),
        Path(a.source_hashes),
        Path(a.qsize_source_hashes),
        Path(a.data_manifest),
    )
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    data = pd.read_parquet(a.dataset)
    assert_no_closed_features(list(data.columns))
    missing_columns = sorted(
        set([*KEY_COLUMNS, "wall_identity", *raw_feature_names("F1")])
        - set(data.columns)
    )
    if missing_columns:
        raise AssertionError(
            f"H-QSIZE1 dataset missing frozen columns: {missing_columns}"
        )
    if (
        data.trade_date.astype(str).str.startswith("2026").any()
        or str(data.trade_date.max()) > END_DATE
    ):
        raise AssertionError("2026/post-cutoff entered H-QSIZE1")
    source = pd.read_csv(a.source_hashes, dtype={"trade_date": str})
    assert_source_inventory(source)
    qsize_source = pd.read_csv(a.qsize_source_hashes, dtype={"trade_date": str})
    assert_qsize_source_inventory(qsize_source)
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
    if "preprocessor_path" in models:
        models["preprocessor_path"] = models["preprocessor_path"].map(
            lambda value: (
                f"models/{Path(str(value)).name}"
                if pd.notna(value) and str(value)
                else value
            )
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
        "schema": "wall_quote_size_pressure_at_touch_physical_evaluation_v1",
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
            hash_list(
                [
                    value
                    for row in models[["sha256", "preprocessor_sha256"]]
                    .fillna("")
                    .astype(str)
                    .itertuples(index=False, name=None)
                    for value in row
                ]
            )
            if len(models)
            else None
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
