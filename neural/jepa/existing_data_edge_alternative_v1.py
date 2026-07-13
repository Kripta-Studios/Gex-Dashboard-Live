"""Frozen alternative economic head for EXISTING_DATA_EXECUTABLE_UTILITY_V1.

This module deliberately contains no outer-period runner.  It defines the one
materially different model formulation that may accompany the primary hurdle
model: direct robust regression of each side's complete executable return.

The caller owns the chronological split.  All fitted state (including feature
medians and utility percentile values) is derived from the supplied training
frame only.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Sequence

import lightgbm as lgb
import numpy as np
import pandas as pd


MODEL_FAMILY = "direct_huber_executable_return_v1"
UTILITY_THRESHOLD_PERCENTILES = (50, 60, 70, 80, 85, 90, 95)
SIDE_MARGIN_PERCENTILES = (0, 10, 20, 30, 40, 50)
CALL_SEED_OFFSET = 5_101
PUT_SEED_OFFSET = 5_102

# Pairwise V1 tree capacity is preserved.  ``huber`` with a frozen alpha is a
# different return-distribution formulation, not a parameter sweep of the
# primary hurdle model.  Targets are the complete, unclipped ask-to-bid returns.
FROZEN_HUBER_PARAMS: dict[str, Any] = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "n_jobs": 28,
    "verbose": -1,
    "objective": "huber",
    "alpha": 0.90,
    "importance_type": "gain",
    "deterministic": True,
    "force_col_wise": True,
}


def frozen_spec() -> dict[str, Any]:
    """Return the complete canonical alternative-model specification."""

    return {
        "schema": "existing_data_executable_utility_alternative_v1",
        "family": MODEL_FAMILY,
        "targets": {
            "CALL": "complete executable CALL return, entry ask to exit bid",
            "PUT": "complete executable PUT return, entry ask to exit bid",
        },
        "utility": "side-specific LightGBM Huber conditional-return prediction",
        "target_clipping": None,
        "target_missing_policy": "fit each side only on its finite training outcomes; never fill; inner/outer require both sides",
        "imputation": "per-feature median fitted on train only; all-missing train columns become 0",
        "scaling": None,
        "lightgbm": dict(FROZEN_HUBER_PARAMS),
        "seed_offsets": {"CALL": CALL_SEED_OFFSET, "PUT": PUT_SEED_OFFSET},
        "utility_threshold_percentiles": list(UTILITY_THRESHOLD_PERCENTILES),
        "side_margin_percentiles": list(SIDE_MARGIN_PERCENTILES),
        "percentile_source": "predictions on training rows only",
        "tie_policy": "ABSTAIN on exact utility tie",
        "feature_policy": "same frozen E0/E1 ordered allowlists as primary hurdle model",
        "outer_period_forbidden_during_development": "2024-01-01 onward",
    }


def frozen_spec_sha256() -> str:
    payload = json.dumps(frozen_spec(), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assert_development_only(frame: pd.DataFrame) -> None:
    """Fail closed if a development call contains 2024+ rows."""

    if "trade_date" not in frame.columns:
        raise KeyError("development frame requires trade_date")
    dates = frame["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    if dates.eq("").any() or not dates.str.fullmatch(r"\d{8}").all():
        raise ValueError("development frame contains invalid trade_date")
    if dates.ge("20240101").any():
        raise AssertionError("2024/2025/2026 rows are sealed during development")


def _training_matrix(frame: pd.DataFrame, feature_cols: Sequence[str]) -> tuple[pd.DataFrame, pd.Series]:
    cols = list(feature_cols)
    if not cols or len(cols) != len(set(cols)):
        raise ValueError("feature allowlist must be non-empty and unique")
    if frame.columns.duplicated().any():
        raise AssertionError("training frame contains duplicate column names")
    missing = [col for col in cols if col not in frame.columns]
    if missing:
        raise KeyError(f"training frame missing features: {missing[:10]}")
    raw = frame.loc[:, cols].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    medians = raw.median(axis=0, skipna=True).fillna(0.0)
    matrix = raw.fillna(medians)
    if not np.isfinite(matrix.to_numpy(dtype=float)).all():
        raise AssertionError("non-finite training feature after train-only imputation")
    return matrix, medians


def _transform_matrix(
    frame: pd.DataFrame,
    feature_cols: Sequence[str],
    medians: pd.Series,
) -> pd.DataFrame:
    cols = list(feature_cols)
    if frame.columns.duplicated().any():
        raise AssertionError("scoring frame contains duplicate column names")
    missing = [col for col in cols if col not in frame.columns]
    if missing:
        raise KeyError(f"scoring frame missing features: {missing[:10]}")
    if list(medians.index) != cols:
        raise AssertionError("imputer state does not match ordered feature allowlist")
    matrix = (
        frame.loc[:, cols]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(medians)
    )
    if not np.isfinite(matrix.to_numpy(dtype=float)).all():
        raise AssertionError("non-finite scoring feature after frozen train imputation")
    return matrix


def _model_params(seed: int) -> dict[str, Any]:
    return {
        **FROZEN_HUBER_PARAMS,
        "random_state": int(seed),
        "bagging_seed": int(seed),
        "feature_fraction_seed": int(seed),
        "data_random_seed": int(seed),
    }


@dataclass
class FittedRobustUtility:
    feature_cols: tuple[str, ...]
    medians: pd.Series
    call_model: lgb.LGBMRegressor
    put_model: lgb.LGBMRegressor
    base_seed: int

    def score(self, frame: pd.DataFrame) -> pd.DataFrame:
        matrix = _transform_matrix(frame, self.feature_cols, self.medians)
        out = frame.copy()
        out["utility_call"] = self.call_model.predict(matrix).astype(float)
        out["utility_put"] = self.put_model.predict(matrix).astype(float)
        values = out[["utility_call", "utility_put"]].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise AssertionError("robust utility model produced non-finite predictions")
        out["utility_max"] = np.max(values, axis=1)
        out["side_margin_raw"] = np.abs(values[:, 0] - values[:, 1])
        return out


def fit_robust_utility(
    train: pd.DataFrame,
    feature_cols: Sequence[str],
    *,
    call_return_col: str,
    put_return_col: str,
    base_seed: int,
) -> FittedRobustUtility:
    """Fit the two frozen robust return heads on training rows only."""

    matrix, medians = _training_matrix(train, feature_cols)
    missing = [col for col in (call_return_col, put_return_col) if col not in train.columns]
    if missing:
        raise KeyError(f"training frame missing executable targets: {missing}")
    call_target = pd.to_numeric(train[call_return_col], errors="coerce").to_numpy(dtype=float)
    put_target = pd.to_numeric(train[put_return_col], errors="coerce").to_numpy(dtype=float)
    call_finite = np.isfinite(call_target)
    put_finite = np.isfinite(put_target)
    if int(call_finite.sum()) < 2 or int(put_finite.sum()) < 2:
        raise AssertionError("robust utility requires sufficient finite executable returns per side")
    call_model = lgb.LGBMRegressor(**_model_params(int(base_seed) + CALL_SEED_OFFSET))
    put_model = lgb.LGBMRegressor(**_model_params(int(base_seed) + PUT_SEED_OFFSET))
    call_model.fit(matrix.loc[call_finite], call_target[call_finite])
    put_model.fit(matrix.loc[put_finite], put_target[put_finite])
    return FittedRobustUtility(
        feature_cols=tuple(feature_cols),
        medians=medians.reindex(list(feature_cols)),
        call_model=call_model,
        put_model=put_model,
        base_seed=int(base_seed),
    )


def training_percentile_grid(training_scores: pd.DataFrame) -> list[dict[str, float | int]]:
    """Materialize the frozen 7x6 grid from training predictions only."""

    required = ["utility_max", "side_margin_raw"]
    missing = [col for col in required if col not in training_scores.columns]
    if missing:
        raise KeyError(f"training scores missing: {missing}")
    utility = pd.to_numeric(training_scores["utility_max"], errors="coerce").to_numpy(dtype=float)
    margin = pd.to_numeric(training_scores["side_margin_raw"], errors="coerce").to_numpy(dtype=float)
    if len(utility) == 0 or not np.isfinite(utility).all() or not np.isfinite(margin).all():
        raise AssertionError("training percentile source must be non-empty and finite")
    thresholds = {
        percentile: float(np.percentile(utility, percentile))
        for percentile in UTILITY_THRESHOLD_PERCENTILES
    }
    margins = {
        percentile: float(np.percentile(margin, percentile))
        for percentile in SIDE_MARGIN_PERCENTILES
    }
    return [
        {
            "utility_percentile": utility_pct,
            "margin_percentile": margin_pct,
            "utility_threshold": thresholds[utility_pct],
            "side_margin": margins[margin_pct],
        }
        for utility_pct in UTILITY_THRESHOLD_PERCENTILES
        for margin_pct in SIDE_MARGIN_PERCENTILES
    ]


def apply_utility_policy(
    scored: pd.DataFrame,
    *,
    utility_threshold: float,
    side_margin: float,
) -> pd.DataFrame:
    """Map robust side utilities to CALL/PUT/abstain without reading outcomes."""

    call = pd.to_numeric(scored["utility_call"], errors="coerce")
    put = pd.to_numeric(scored["utility_put"], errors="coerce")
    finite = np.isfinite(call) & np.isfinite(put)
    maximum = np.maximum(call, put)
    gap = np.abs(call - put)
    not_tied = call.ne(put)
    active = finite & not_tied & maximum.ge(float(utility_threshold)) & gap.ge(float(side_margin))
    out = scored.loc[active].copy()
    out_call = pd.to_numeric(out["utility_call"], errors="coerce")
    out_put = pd.to_numeric(out["utility_put"], errors="coerce")
    out["action"] = np.where(out_call.gt(out_put), "CALL", "PUT")
    out["score"] = np.maximum(out_call, out_put)
    out["utility_threshold"] = float(utility_threshold)
    out["side_margin"] = float(side_margin)
    return out
