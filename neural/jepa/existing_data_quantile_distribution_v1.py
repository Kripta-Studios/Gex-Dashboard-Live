"""Frozen quantile-distribution economic head for existing executable labels.

The caller owns chronological splitting and scheduler replay.  This module only
fits side-specific conditional quantiles, converts them to an auditable robust
utility and maps scores to CALL/PUT/ABSTAIN.  Every fitted value is derived from
the supplied training frame; scoring never reads an outcome column.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Sequence

import lightgbm as lgb
import numpy as np
import pandas as pd


MODEL_FAMILY = "lightgbm_quantile_distribution_utility_v1"
QUANTILE_ALPHAS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
UTILITY_WEIGHTS = (0.15, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.15)
UTILITY_THRESHOLD_PERCENTILES = (50, 60, 70, 80, 85, 90, 95)
SIDE_MARGIN_PERCENTILES = (0, 10, 20, 30, 40, 50)
MINIMUM_PREDICTED_WIN_PROBABILITY = 0.50
MINIMUM_FINITE_TARGET_ROWS = 100

TICKER_OFFSETS = {"SPXW": 100, "QQQ": 200, "SPY": 300}
SIDE_OFFSETS = {"CALL": 10_000, "PUT": 20_000}

FROZEN_QUANTILE_PARAMS: dict[str, Any] = {
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
    "objective": "quantile",
    "importance_type": "gain",
    "deterministic": True,
    "force_col_wise": True,
}


def frozen_spec() -> dict[str, Any]:
    """Return the canonical pre-execution model specification."""

    return {
        "schema": "existing_data_executable_quantile_distribution_v1",
        "family": MODEL_FAMILY,
        "targets": {
            "CALL": "complete executable CALL return, entry ask to exit bid",
            "PUT": "complete executable PUT return, entry ask to exit bid",
        },
        "quantile_alphas": list(QUANTILE_ALPHAS),
        "loss": "LightGBM quantile pinball independently per side and alpha",
        "quantile_crossing": (
            "row-wise increasing rearrangement before any distributional functional"
        ),
        "utility": (
            "integral of piecewise-linear rearranged quantile function with constant "
            "q10/q90 tails; weights 0.15*q10 + 0.10*sum(q20..q80) + 0.15*q90"
        ),
        "win_probability": (
            "1 minus piecewise-linear CDF at zero, capped to [0.1,0.9]; "
            "right-continuous conservative handling of duplicate quantiles"
        ),
        "eligibility": "selected side predicted win probability >= 0.50",
        "target_clipping": None,
        "target_missing_policy": (
            "fit each side-alpha only on finite training outcomes; never fill; "
            "inner/outer require both sides"
        ),
        "imputation": "per-feature training median; all-missing training columns become 0",
        "lightgbm": dict(FROZEN_QUANTILE_PARAMS),
        "seed_rule": "42 + outer_yyyymm + ticker_offset + side_offset + quantile_index",
        "ticker_offsets": dict(TICKER_OFFSETS),
        "side_offsets": dict(SIDE_OFFSETS),
        "quantile_index": "1..9 in ascending alpha order",
        "feature_policy": (
            "same frozen E0/E1 ordered allowlists; E0 control, E1 sole candidate"
        ),
        "utility_threshold_percentiles": list(UTILITY_THRESHOLD_PERCENTILES),
        "side_margin_percentiles": list(SIDE_MARGIN_PERCENTILES),
        "percentile_source": "predictions on training rows only",
        "policy": (
            "higher utility side; exact tie abstain; threshold and margin gates plus "
            "selected-side win probability gate"
        ),
        "inner": (
            "three immediately preceding calendar months; one pair must pass every month"
        ),
        "inner_gates": {
            "profit_factor": 1.3,
            "win_rate": 0.5,
            "trades": 18,
            "pnl_strictly_positive": True,
            "minimum_hold_minutes": 30,
        },
        "passing_grid_rank_desc": [
            "worst_inner_month_pnl",
            "worst_inner_month_pf",
            "worst_inner_month_wr",
            "minimum_inner_month_trades",
            "pooled_inner_pnl",
            "pooled_inner_pf",
            "utility_percentile",
            "margin_percentile",
        ],
        "no_passing_grid": "ABSTAIN_OUTER",
        "outer": "one month; 2024-01 through 2025-12 only after freeze",
        "execution": (
            "existing ask-to-bid 30..180m trailing contract and live-equivalent scheduler"
        ),
        "development_seal": "2024-01-01 onward forbidden before freeze",
    }


def frozen_spec_sha256() -> str:
    payload = json.dumps(frozen_spec(), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assert_development_only(frame: pd.DataFrame) -> None:
    """Fail closed if an unfrozen development call includes 2024 or later."""

    if "trade_date" not in frame.columns:
        raise KeyError("development frame requires trade_date")
    dates = frame["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    if dates.eq("").any() or not dates.str.fullmatch(r"\d{8}").all():
        raise ValueError("development frame contains invalid trade_date")
    if dates.ge("20240101").any():
        raise AssertionError("2024/2025/2026 rows are sealed during development")


def _training_matrix(
    frame: pd.DataFrame,
    feature_cols: Sequence[str],
) -> tuple[pd.DataFrame, pd.Series]:
    columns = list(feature_cols)
    if not columns or len(columns) != len(set(columns)):
        raise ValueError("feature allowlist must be non-empty and unique")
    if frame.columns.duplicated().any():
        raise AssertionError("training frame contains duplicate column names")
    missing = [column for column in columns if column not in frame]
    if missing:
        raise KeyError(f"training frame missing features: {missing[:10]}")
    raw = frame.loc[:, columns].apply(pd.to_numeric, errors="coerce")
    raw = raw.replace([np.inf, -np.inf], np.nan)
    medians = raw.median(axis=0, skipna=True).fillna(0.0).reindex(columns)
    matrix = raw.fillna(medians)
    if not np.isfinite(matrix.to_numpy(dtype=float)).all():
        raise AssertionError("non-finite feature after train-only imputation")
    return matrix, medians


def _transform_matrix(
    frame: pd.DataFrame,
    feature_cols: Sequence[str],
    medians: pd.Series,
) -> pd.DataFrame:
    columns = list(feature_cols)
    if frame.columns.duplicated().any():
        raise AssertionError("scoring frame contains duplicate column names")
    missing = [column for column in columns if column not in frame]
    if missing:
        raise KeyError(f"scoring frame missing features: {missing[:10]}")
    if list(medians.index) != columns:
        raise AssertionError("imputer state does not match ordered feature allowlist")
    matrix = (
        frame.loc[:, columns]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(medians)
    )
    if not np.isfinite(matrix.to_numpy(dtype=float)).all():
        raise AssertionError("non-finite scoring feature after frozen imputation")
    return matrix


def _model_params(seed: int, alpha: float) -> dict[str, Any]:
    return {
        **FROZEN_QUANTILE_PARAMS,
        "alpha": float(alpha),
        "random_state": int(seed),
        "bagging_seed": int(seed),
        "feature_fraction_seed": int(seed),
        "data_random_seed": int(seed),
    }


def summarize_quantiles(raw_quantiles: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rearrange quantiles and return robust utility and predicted P(return>0)."""

    raw = np.asarray(raw_quantiles, dtype=float)
    if raw.ndim != 2 or raw.shape[1] != len(QUANTILE_ALPHAS):
        raise ValueError(f"quantile matrix must have shape (n, {len(QUANTILE_ALPHAS)})")
    if not np.isfinite(raw).all():
        raise AssertionError("quantile predictions must be finite")
    quantiles = np.sort(raw, axis=1)
    utility = quantiles @ np.asarray(UTILITY_WEIGHTS, dtype=float)
    pwin = np.empty(len(quantiles), dtype=float)
    alphas = np.asarray(QUANTILE_ALPHAS, dtype=float)
    for row_number, row in enumerate(quantiles):
        if 0.0 < row[0]:
            cdf_zero = alphas[0]
        elif 0.0 >= row[-1]:
            cdf_zero = alphas[-1]
        else:
            lower_index = int(np.flatnonzero(row <= 0.0)[-1])
            upper_index = lower_index + 1
            lower_value = row[lower_index]
            upper_value = row[upper_index]
            if not upper_value > lower_value:
                raise AssertionError("rearranged CDF interpolation interval is not increasing")
            fraction = (0.0 - lower_value) / (upper_value - lower_value)
            cdf_zero = alphas[lower_index] + fraction * (
                alphas[upper_index] - alphas[lower_index]
            )
        pwin[row_number] = 1.0 - float(cdf_zero)
    pwin = np.clip(pwin, 0.1, 0.9)
    return quantiles, utility, pwin


@dataclass
class FittedQuantileDistribution:
    feature_cols: tuple[str, ...]
    medians: pd.Series
    call_models: tuple[lgb.LGBMRegressor, ...]
    put_models: tuple[lgb.LGBMRegressor, ...]
    base_seed: int

    def score(self, frame: pd.DataFrame) -> pd.DataFrame:
        matrix = _transform_matrix(frame, self.feature_cols, self.medians)
        out = frame.copy()
        for side, models in (("call", self.call_models), ("put", self.put_models)):
            raw = np.column_stack(
                [np.asarray(model.predict(matrix), dtype=float) for model in models]
            )
            quantiles, utility, pwin = summarize_quantiles(raw)
            for index, alpha in enumerate(QUANTILE_ALPHAS):
                label = int(round(alpha * 100))
                out[f"raw_q_{side}_{label:02d}"] = raw[:, index]
                out[f"q_{side}_{label:02d}"] = quantiles[:, index]
            out[f"utility_{side}"] = utility
            out[f"pwin_{side}"] = pwin
        utilities = out[["utility_call", "utility_put"]].to_numpy(dtype=float)
        if not np.isfinite(utilities).all():
            raise AssertionError("quantile utility produced non-finite predictions")
        out["utility_max"] = np.max(utilities, axis=1)
        out["side_margin_raw"] = np.abs(utilities[:, 0] - utilities[:, 1])
        return out


def _fit_side(
    matrix: pd.DataFrame,
    target: np.ndarray,
    *,
    base_seed: int,
    side: str,
) -> tuple[lgb.LGBMRegressor, ...]:
    side_upper = side.upper()
    if side_upper not in SIDE_OFFSETS:
        raise KeyError(f"unknown side: {side}")
    finite = np.isfinite(target)
    if int(finite.sum()) < MINIMUM_FINITE_TARGET_ROWS:
        raise AssertionError("quantile side has insufficient finite executable returns")
    selected_matrix = matrix.loc[finite]
    selected_target = target[finite]
    models: list[lgb.LGBMRegressor] = []
    for quantile_index, alpha in enumerate(QUANTILE_ALPHAS, start=1):
        seed = int(base_seed) + SIDE_OFFSETS[side_upper] + quantile_index
        model = lgb.LGBMRegressor(**_model_params(seed, alpha))
        model.fit(selected_matrix, selected_target)
        models.append(model)
    return tuple(models)


def fit_quantile_distribution(
    train: pd.DataFrame,
    feature_cols: Sequence[str],
    *,
    call_return_col: str,
    put_return_col: str,
    base_seed: int,
) -> FittedQuantileDistribution:
    """Fit all eighteen quantile heads using only the supplied training rows."""

    matrix, medians = _training_matrix(train, feature_cols)
    missing = [column for column in (call_return_col, put_return_col) if column not in train]
    if missing:
        raise KeyError(f"training frame missing executable targets: {missing}")
    call_target = pd.to_numeric(train[call_return_col], errors="coerce").to_numpy(dtype=float)
    put_target = pd.to_numeric(train[put_return_col], errors="coerce").to_numpy(dtype=float)
    return FittedQuantileDistribution(
        feature_cols=tuple(feature_cols),
        medians=medians,
        call_models=_fit_side(matrix, call_target, base_seed=int(base_seed), side="CALL"),
        put_models=_fit_side(matrix, put_target, base_seed=int(base_seed), side="PUT"),
        base_seed=int(base_seed),
    )


def training_percentile_grid(training_scores: pd.DataFrame) -> list[dict[str, float | int]]:
    """Materialize the frozen 7x6 grid from training predictions only."""

    required = ["utility_max", "side_margin_raw"]
    missing = [column for column in required if column not in training_scores]
    if missing:
        raise KeyError(f"training scores missing: {missing}")
    utility = pd.to_numeric(training_scores["utility_max"], errors="coerce").to_numpy(float)
    margin = pd.to_numeric(training_scores["side_margin_raw"], errors="coerce").to_numpy(float)
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
            "utility_percentile": utility_percentile,
            "margin_percentile": margin_percentile,
            "utility_threshold": thresholds[utility_percentile],
            "side_margin": margins[margin_percentile],
        }
        for utility_percentile in UTILITY_THRESHOLD_PERCENTILES
        for margin_percentile in SIDE_MARGIN_PERCENTILES
    ]


def apply_quantile_policy(
    scored: pd.DataFrame,
    *,
    utility_threshold: float,
    side_margin: float,
) -> pd.DataFrame:
    """Map distributional scores to trades without consulting realized outcomes."""

    required = ["utility_call", "utility_put", "pwin_call", "pwin_put"]
    missing = [column for column in required if column not in scored]
    if missing:
        raise KeyError(f"quantile policy scores missing: {missing}")
    call_utility = pd.to_numeric(scored["utility_call"], errors="coerce")
    put_utility = pd.to_numeric(scored["utility_put"], errors="coerce")
    call_pwin = pd.to_numeric(scored["pwin_call"], errors="coerce")
    put_pwin = pd.to_numeric(scored["pwin_put"], errors="coerce")
    finite = (
        np.isfinite(call_utility)
        & np.isfinite(put_utility)
        & np.isfinite(call_pwin)
        & np.isfinite(put_pwin)
    )
    call_wins = call_utility.gt(put_utility)
    put_wins = put_utility.gt(call_utility)
    maximum = np.maximum(call_utility, put_utility)
    margin = np.abs(call_utility - put_utility)
    selected_pwin = np.where(call_wins, call_pwin, put_pwin)
    active = (
        finite
        & (call_wins | put_wins)
        & maximum.ge(float(utility_threshold))
        & margin.ge(float(side_margin))
        & (selected_pwin >= MINIMUM_PREDICTED_WIN_PROBABILITY)
    )
    out = scored.loc[active].copy()
    out_call = pd.to_numeric(out["utility_call"], errors="coerce")
    out_put = pd.to_numeric(out["utility_put"], errors="coerce")
    out["action"] = np.where(out_call.gt(out_put), "CALL", "PUT")
    out["score"] = np.maximum(out_call, out_put)
    out["selected_pwin"] = np.where(
        out["action"].eq("CALL"),
        pd.to_numeric(out["pwin_call"], errors="coerce"),
        pd.to_numeric(out["pwin_put"], errors="coerce"),
    )
    out["utility_threshold"] = float(utility_threshold)
    out["side_margin"] = float(side_margin)
    return out


__all__ = [
    "FROZEN_QUANTILE_PARAMS",
    "MINIMUM_PREDICTED_WIN_PROBABILITY",
    "MODEL_FAMILY",
    "QUANTILE_ALPHAS",
    "SIDE_MARGIN_PERCENTILES",
    "UTILITY_THRESHOLD_PERCENTILES",
    "UTILITY_WEIGHTS",
    "FittedQuantileDistribution",
    "apply_quantile_policy",
    "assert_development_only",
    "fit_quantile_distribution",
    "frozen_spec",
    "frozen_spec_sha256",
    "summarize_quantiles",
    "training_percentile_grid",
]
