"""Primary hurdle expected-utility model for the existing-data edge sprint.

The caller owns chronological splitting.  This module fits every imputer,
winsorization limit, model, and policy percentile from the supplied training
rows only.  It never selects a threshold and never reads an outer outcome while
mapping predictions to CALL/PUT/ABSTAIN.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Sequence

import lightgbm as lgb
import numpy as np
import pandas as pd

from neural.jepa.existing_data_edge_alternative_v1 import (
    SIDE_MARGIN_PERCENTILES,
    UTILITY_THRESHOLD_PERCENTILES,
    apply_utility_policy,
    training_percentile_grid,
)


MODEL_FAMILY = "lightgbm_hurdle_expected_utility_v1"
WINSOR_LOWER_QUANTILE = 0.01
WINSOR_UPPER_QUANTILE = 0.99

FROZEN_TREE_PARAMS: dict[str, Any] = {
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
    "importance_type": "gain",
    "deterministic": True,
    "force_col_wise": True,
}

SEED_OFFSETS = {
    "call_probability": 1_001,
    "call_gain": 1_002,
    "call_loss": 1_003,
    "put_probability": 1_004,
    "put_gain": 1_005,
    "put_loss": 1_006,
}


def frozen_spec() -> dict[str, Any]:
    return {
        "schema": "existing_data_executable_utility_hurdle_v1",
        "family": MODEL_FAMILY,
        "side_models": {
            "probability": "P(executable_return > 0), LightGBM binary",
            "gain": "E[winsorized positive executable return | return > 0], LightGBM L2",
            "loss": "E[winsorized absolute executable loss | return <= 0], LightGBM L2",
        },
        "utility": "p * gain - (1 - p) * loss",
        "winsor_quantiles": [WINSOR_LOWER_QUANTILE, WINSOR_UPPER_QUANTILE],
        "winsor_source": "each side and conditional branch, training rows only",
        "prediction_bounds": "conditional training winsor limits",
        "target_missing_policy": "fit each side only on its finite training outcomes; never fill; inner/outer require both sides",
        "imputation": "per-feature training median; all-missing training columns become 0",
        "scaling": None,
        "tree_params": dict(FROZEN_TREE_PARAMS),
        "seed_offsets": dict(SEED_OFFSETS),
        "utility_threshold_percentiles": list(UTILITY_THRESHOLD_PERCENTILES),
        "side_margin_percentiles": list(SIDE_MARGIN_PERCENTILES),
        "percentile_source": "predictions on training rows only",
        "tie_policy": "ABSTAIN on exact utility tie",
    }


def frozen_spec_sha256() -> str:
    payload = json.dumps(frozen_spec(), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _matrix_and_medians(
    frame: pd.DataFrame,
    feature_cols: Sequence[str],
) -> tuple[pd.DataFrame, pd.Series]:
    columns = list(feature_cols)
    if not columns or len(columns) != len(set(columns)):
        raise ValueError("feature allowlist must be non-empty and unique")
    missing = [column for column in columns if column not in frame]
    if missing:
        raise KeyError(f"training frame missing features: {missing[:10]}")
    raw = frame[columns].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    medians = raw.median(axis=0, skipna=True).fillna(0.0).reindex(columns)
    matrix = raw.fillna(medians)
    if not np.isfinite(matrix.to_numpy(dtype=float)).all():
        raise AssertionError("non-finite feature after train-only imputation")
    return matrix, medians


def _transform(
    frame: pd.DataFrame,
    feature_cols: Sequence[str],
    medians: pd.Series,
) -> pd.DataFrame:
    columns = list(feature_cols)
    if list(medians.index) != columns:
        raise AssertionError("imputer state does not match ordered feature allowlist")
    missing = [column for column in columns if column not in frame]
    if missing:
        raise KeyError(f"scoring frame missing features: {missing[:10]}")
    matrix = (
        frame[columns]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(medians)
    )
    if not np.isfinite(matrix.to_numpy(dtype=float)).all():
        raise AssertionError("non-finite scoring feature after frozen imputation")
    return matrix


def _params(seed: int, objective: str) -> dict[str, Any]:
    return {
        **FROZEN_TREE_PARAMS,
        "objective": objective,
        "random_state": int(seed),
        "bagging_seed": int(seed),
        "feature_fraction_seed": int(seed),
        "data_random_seed": int(seed),
    }


@dataclass
class ConditionalMagnitude:
    model: lgb.LGBMRegressor
    lower: float
    upper: float

    def predict(self, matrix: pd.DataFrame) -> np.ndarray:
        values = np.asarray(self.model.predict(matrix), dtype=float)
        return np.clip(values, self.lower, self.upper)


@dataclass
class SideHurdle:
    probability: lgb.LGBMClassifier
    gain: ConditionalMagnitude
    loss: ConditionalMagnitude

    def predict(self, matrix: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        probability = np.asarray(self.probability.predict_proba(matrix)[:, 1], dtype=float)
        gain = self.gain.predict(matrix)
        loss = self.loss.predict(matrix)
        utility = probability * gain - (1.0 - probability) * loss
        return probability, gain, loss, utility


@dataclass
class FittedHurdleUtility:
    feature_cols: tuple[str, ...]
    medians: pd.Series
    call: SideHurdle
    put: SideHurdle
    base_seed: int

    def score(self, frame: pd.DataFrame) -> pd.DataFrame:
        matrix = _transform(frame, self.feature_cols, self.medians)
        call_p, call_gain, call_loss, call_utility = self.call.predict(matrix)
        put_p, put_gain, put_loss, put_utility = self.put.predict(matrix)
        out = frame.copy()
        out["p_call_positive"] = call_p
        out["pred_call_gain"] = call_gain
        out["pred_call_loss"] = call_loss
        out["utility_call"] = call_utility
        out["p_put_positive"] = put_p
        out["pred_put_gain"] = put_gain
        out["pred_put_loss"] = put_loss
        out["utility_put"] = put_utility
        values = out[["utility_call", "utility_put"]].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise AssertionError("hurdle utility produced non-finite predictions")
        out["utility_max"] = np.max(values, axis=1)
        out["side_margin_raw"] = np.abs(values[:, 0] - values[:, 1])
        return out


def _fit_magnitude(
    matrix: pd.DataFrame,
    magnitudes: np.ndarray,
    mask: np.ndarray,
    seed: int,
) -> ConditionalMagnitude:
    selected = np.asarray(magnitudes[mask], dtype=float)
    if len(selected) < 20 or not np.isfinite(selected).all():
        raise AssertionError("conditional hurdle branch has insufficient finite training rows")
    lower, upper = np.quantile(selected, [WINSOR_LOWER_QUANTILE, WINSOR_UPPER_QUANTILE])
    lower = max(0.0, float(lower))
    upper = max(lower, float(upper))
    target = np.clip(selected, lower, upper)
    model = lgb.LGBMRegressor(**_params(seed, "regression"))
    model.fit(matrix.loc[mask], target)
    return ConditionalMagnitude(model=model, lower=lower, upper=upper)


def _fit_side(matrix: pd.DataFrame, returns: np.ndarray, base_seed: int, prefix: str) -> SideHurdle:
    finite = np.isfinite(returns)
    if int(finite.sum()) < 100:
        raise AssertionError("hurdle side has insufficient finite executable returns")
    matrix = matrix.loc[finite]
    returns = returns[finite]
    positive = returns > 0.0
    if np.unique(positive).size != 2:
        raise AssertionError("hurdle probability target requires both classes")
    probability = lgb.LGBMClassifier(**_params(base_seed + SEED_OFFSETS[f"{prefix}_probability"], "binary"))
    probability.fit(matrix, positive.astype(int))
    gain = _fit_magnitude(
        matrix,
        np.maximum(returns, 0.0),
        positive,
        base_seed + SEED_OFFSETS[f"{prefix}_gain"],
    )
    nonpositive = ~positive
    loss = _fit_magnitude(
        matrix,
        np.abs(np.minimum(returns, 0.0)),
        nonpositive,
        base_seed + SEED_OFFSETS[f"{prefix}_loss"],
    )
    return SideHurdle(probability=probability, gain=gain, loss=loss)


def fit_hurdle_utility(
    train: pd.DataFrame,
    feature_cols: Sequence[str],
    *,
    call_return_col: str,
    put_return_col: str,
    base_seed: int,
) -> FittedHurdleUtility:
    matrix, medians = _matrix_and_medians(train, feature_cols)
    missing = [column for column in (call_return_col, put_return_col) if column not in train]
    if missing:
        raise KeyError(f"training frame missing executable targets: {missing}")
    call_returns = pd.to_numeric(train[call_return_col], errors="coerce").to_numpy(dtype=float)
    put_returns = pd.to_numeric(train[put_return_col], errors="coerce").to_numpy(dtype=float)
    return FittedHurdleUtility(
        feature_cols=tuple(feature_cols),
        medians=medians,
        call=_fit_side(matrix, call_returns, int(base_seed), "call"),
        put=_fit_side(matrix, put_returns, int(base_seed), "put"),
        base_seed=int(base_seed),
    )


__all__ = [
    "FROZEN_TREE_PARAMS",
    "MODEL_FAMILY",
    "SIDE_MARGIN_PERCENTILES",
    "UTILITY_THRESHOLD_PERCENTILES",
    "apply_utility_policy",
    "fit_hurdle_utility",
    "frozen_spec",
    "frozen_spec_sha256",
    "training_percentile_grid",
]
