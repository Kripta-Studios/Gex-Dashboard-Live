from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from typing import Any

import lightgbm as lgb
from numba import njit, prange
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from neural.jepa.evaluate_xinput_level_filter import month_add
from neural.jepa.walkforward_event_option_gate import LEAKY_PATTERNS
from neural.jepa.walkforward_event_option_profile_selector import build_features


SOURCE_PATH = Path(
    "tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/"
    "event_option_dataset.parquet"
)
OUTPUT_DIR = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "event_option_execquote_full_nested_monthly_overlay_v1_202601_202606"
)
CONTRACT_PATH = Path(
    "research_papers/JEPA/"
    "EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1_PREDECLARATION.md"
)
AUDITOR_PATH = Path("neural/jepa/audit_event_option_execquote_full_nested_overlay_v1.py")

SOURCE_SHA256 = "e6a19efba1edb055c733aab4967843f7a4b5f1d2c8238a7a243fc5bbc2251903"
SOURCE_BYTES = 74_638_331
SOURCE_ROWS = 44_169
FEATURE_COUNT = 289
FEATURES_SHA256 = "b4f038f75cb029c4ba2d1e4e4aab5266a45d86e9c2d86ac527a69be521c852ca"

TICKERS = ("QQQ", "SPXW", "SPY")
TEST_MONTHS = ("202601", "202602", "202603", "202604", "202605", "202606")
DELTA_BY_TICKER = {"QQQ": 35, "SPXW": 25, "SPY": 35}
PROFILE_BY_TICKER = {
    "QQQ": "target_zero_dte_d35_return",
    "SPXW": "target_zero_dte_d25_return",
    "SPY": "target_zero_dte_d35_return",
}

THRESHOLDS = (-0.10, 0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40)
EDGES = (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40)
ACTIONS = ("BOTH", "CALL", "PUT")
TIME_WINDOWS = (
    (630, 870),
    (630, 840),
    (630, 810),
    (660, 870),
    (660, 840),
    (660, 810),
    (690, 870),
    (690, 840),
    (690, 810),
    (690, 780),
    (720, 870),
    (720, 840),
    (720, 810),
    (750, 870),
    (750, 840),
    (750, 810),
)
NEAR_VALUES = (10.0, 15.0, 20.0)
MOMENTUM = (
    "NONE",
    "SELF_COUNTER_5M",
    "SELF_SAME_5M",
    "SPX_COUNTER_5M",
    "SPX_SAME_5M",
    "QQQ_COUNTER_5M",
    "QQQ_SAME_5M",
)
MAX_DAYS = (1, 2, 3, 4)
COOLDOWNS = (0, 15, 30, 45)

BASE_CONFIGS = (
    len(THRESHOLDS)
    * len(EDGES)
    * len(ACTIONS)
    * len(TIME_WINDOWS)
    * len(NEAR_VALUES)
    * len(MOMENTUM)
)
FULL_CONFIGS = BASE_CONFIGS * len(MAX_DAYS) * len(COOLDOWNS)
MIN_MONTH_TRADES = 13

MODEL_PARAMS = {
    "objective": "regression_l1",
    "n_estimators": 160,
    "learning_rate": 0.035,
    "num_leaves": 31,
    "min_child_samples": 60,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "reg_lambda": 5.0,
    "seed": 20260617,
    "clip_return": 5.0,
}


@dataclass(frozen=True)
class OverlayConfig:
    threshold: float
    edge: float
    action: str
    time_min: int
    time_max: int
    near_bps: float
    momentum: str
    max_day: int
    cooldown: int
    grid_index: int

    @property
    def name(self) -> str:
        return (
            f"thr{self.threshold:g}_edge{self.edge:g}_{self.action}_"
            f"t{self.time_min}-{self.time_max}_near{self.near_bps:g}_"
            f"{self.momentum}_cap{self.max_day}_cd{self.cooldown}"
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_ready(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def dataframe_sha(frame: pd.DataFrame, columns: list[str], sort_columns: list[str]) -> str:
    work = frame.loc[:, columns].copy()
    if sort_columns:
        work = work.sort_values(sort_columns, kind="stable").reset_index(drop=True)
    raw = work.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
        encoding="utf-8",
    ).strip()


def selection_months(test_month: str) -> list[str]:
    return [month_add(test_month, -offset) for offset in range(6, 0, -1)]


def training_months(test_month: str) -> list[str]:
    first_selection = selection_months(test_month)[0]
    out: list[str] = []
    month = "202501"
    while month < first_selection:
        out.append(month)
        month = month_add(month, 1)
    return out


def next_month(month: str) -> str:
    return month_add(month, 1)


def month_start(month: str) -> str:
    return f"{month}01"


def validate_source(path: Path) -> pq.ParquetFile:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != SOURCE_BYTES:
        raise RuntimeError(f"source byte mismatch: {path.stat().st_size} != {SOURCE_BYTES}")
    actual_sha = sha256_file(path)
    if actual_sha != SOURCE_SHA256:
        raise RuntimeError(f"source SHA mismatch: {actual_sha} != {SOURCE_SHA256}")
    parquet = pq.ParquetFile(path)
    if parquet.metadata.num_rows != SOURCE_ROWS:
        raise RuntimeError(f"source row mismatch: {parquet.metadata.num_rows} != {SOURCE_ROWS}")
    return parquet


def load_feature_view(path: Path, parquet: pq.ParquetFile) -> tuple[pd.DataFrame, list[str]]:
    source_columns = [
        name
        for name in parquet.schema_arrow.names
        if not any(pattern in name.lower() for pattern in LEAKY_PATTERNS)
    ]
    raw = pd.read_parquet(path, columns=source_columns)
    raw["ticker"] = raw["ticker"].astype(str).str.upper()
    raw["trade_date"] = raw["trade_date"].astype(str)
    raw["date"] = raw["trade_date"]
    raw["month"] = raw["trade_date"].str[:6]
    if set(raw["ticker"]) != set(TICKERS):
        raise RuntimeError(f"unexpected ticker universe: {sorted(set(raw['ticker']))}")
    if set(raw["option_price_mode"].astype(str).str.lower()) != {"executable_quote"}:
        raise RuntimeError("source is not uniformly option_price_mode=executable_quote")
    if set(raw["expiry_mode"].astype(str)) != {"zero_dte"}:
        raise RuntimeError("source is not uniformly zero_dte")
    frame, feature_columns = build_features(
        raw,
        live_observable_features_only=True,
        entry_start_minute_et=630,
        feature_exclude_prefixes=(),
    )
    feature_sha = canonical_json_sha(feature_columns)
    if len(feature_columns) != FEATURE_COUNT or feature_sha != FEATURES_SHA256:
        raise RuntimeError(
            f"feature contract mismatch: count={len(feature_columns)} sha={feature_sha}"
        )
    keys = ["ticker", "trade_date", "minute"]
    if frame.duplicated(keys).any():
        raise RuntimeError("feature view has duplicate ticker/date/minute keys")
    return frame.reset_index(drop=True), feature_columns


def outcome_columns(delta: int) -> list[str]:
    prefix_call = f"call_d{delta:02d}"
    prefix_put = f"put_d{delta:02d}"
    return [
        "ticker",
        "trade_date",
        "minute",
        f"{prefix_call}_opt_exit_ret",
        f"{prefix_put}_opt_exit_ret",
        f"{prefix_call}_opt_exit_minutes",
        f"{prefix_put}_opt_exit_minutes",
        f"{prefix_call}_opt_status",
        f"{prefix_put}_opt_status",
    ]


def load_outcomes(
    path: Path,
    ticker: str,
    start_month: str,
    end_month_exclusive: str,
    delta: int,
) -> pd.DataFrame:
    filters = [
        ("ticker", "==", ticker),
        ("trade_date", ">=", month_start(start_month)),
        ("trade_date", "<", month_start(end_month_exclusive)),
    ]
    out = pd.read_parquet(path, columns=outcome_columns(delta), filters=filters)
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["trade_date"] = out["trade_date"].astype(str)
    if out.duplicated(["ticker", "trade_date", "minute"]).any():
        raise RuntimeError(f"duplicate outcomes for {ticker} {start_month}:{end_month_exclusive}")
    return out


def eligible_feature_rows(frame: pd.DataFrame, ticker: str, delta: int) -> pd.DataFrame:
    call_available = f"call_d{delta:02d}_available"
    put_available = f"put_d{delta:02d}_available"
    mask = (
        frame["ticker"].astype(str).eq(ticker)
        & frame["expiry_mode"].astype(str).eq("zero_dte")
        & pd.to_numeric(frame[call_available], errors="coerce").fillna(0.0).gt(0.0)
        & pd.to_numeric(frame[put_available], errors="coerce").fillna(0.0).gt(0.0)
    )
    return frame.loc[mask].copy()


def merge_outcomes(features: pd.DataFrame, outcomes: pd.DataFrame, delta: int) -> pd.DataFrame:
    keys = ["ticker", "trade_date", "minute"]
    merged = features.merge(outcomes, on=keys, how="left", validate="one_to_one")
    call_prefix = f"call_d{delta:02d}"
    put_prefix = f"put_d{delta:02d}"
    merged["call_return"] = pd.to_numeric(
        merged[f"{call_prefix}_opt_exit_ret"], errors="coerce"
    )
    merged["put_return"] = pd.to_numeric(
        merged[f"{put_prefix}_opt_exit_ret"], errors="coerce"
    )
    finite = np.isfinite(merged["call_return"]) & np.isfinite(merged["put_return"])
    if not finite.all():
        missing = merged.loc[~finite, keys].head(10).to_dict("records")
        raise RuntimeError(f"missing executable outcomes after key merge: {missing}")
    return merged


def fit_models(
    train: pd.DataFrame,
    feature_columns: list[str],
    test_month: str,
    lgb_jobs: int,
) -> tuple[lgb.LGBMRegressor, lgb.LGBMRegressor, pd.Series]:
    medians = (
        train[feature_columns]
        .replace([np.inf, -np.inf], np.nan)
        .median(numeric_only=True)
        .reindex(feature_columns)
        .fillna(0.0)
    )
    x_train = (
        train[feature_columns]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(medians)
        .fillna(0.0)
    )
    clip = float(MODEL_PARAMS["clip_return"])
    y_call = train["call_return"].astype(float).clip(-clip, clip)
    y_put = train["put_return"].astype(float).clip(-clip, clip)
    params = {
        "objective": MODEL_PARAMS["objective"],
        "n_estimators": int(MODEL_PARAMS["n_estimators"]),
        "learning_rate": float(MODEL_PARAMS["learning_rate"]),
        "num_leaves": int(MODEL_PARAMS["num_leaves"]),
        "min_child_samples": int(MODEL_PARAMS["min_child_samples"]),
        "subsample": float(MODEL_PARAMS["subsample"]),
        "colsample_bytree": float(MODEL_PARAMS["colsample_bytree"]),
        "reg_lambda": float(MODEL_PARAMS["reg_lambda"]),
        "random_state": int(MODEL_PARAMS["seed"]) + int(test_month[-2:]),
        "n_jobs": int(lgb_jobs),
        "verbose": -1,
        "deterministic": True,
        "force_col_wise": True,
    }
    call_model = lgb.LGBMRegressor(**params)
    put_model = lgb.LGBMRegressor(
        **{**params, "random_state": int(params["random_state"]) + 10_000}
    )
    call_model.fit(x_train, y_call)
    put_model.fit(x_train, y_put)
    return call_model, put_model, medians


def predict_scores(
    frame: pd.DataFrame,
    feature_columns: list[str],
    call_model: lgb.LGBMRegressor,
    put_model: lgb.LGBMRegressor,
    medians: pd.Series,
) -> pd.DataFrame:
    x = (
        frame[feature_columns]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(medians)
        .fillna(0.0)
    )
    out = frame.copy()
    out["pred_call_return"] = call_model.predict(x)
    out["pred_put_return"] = put_model.predict(x)
    call_action = out["pred_call_return"].astype(float) >= out[
        "pred_put_return"
    ].astype(float)
    out["action"] = np.where(call_action, "CALL", "PUT")
    out["score"] = np.where(
        call_action,
        out["pred_call_return"],
        out["pred_put_return"],
    )
    out["edge_abs"] = (
        out["pred_call_return"].astype(float) - out["pred_put_return"].astype(float)
    ).abs()
    return out


def bind_physical_outcome(scored: pd.DataFrame, delta: int) -> pd.DataFrame:
    out = scored.copy()
    call_action = out["action"].astype(str).eq("CALL")
    call_prefix = f"call_d{delta:02d}"
    put_prefix = f"put_d{delta:02d}"
    out["realized_return"] = np.where(
        call_action,
        out[f"{call_prefix}_opt_exit_ret"],
        out[f"{put_prefix}_opt_exit_ret"],
    )
    out["exit_minutes"] = np.where(
        call_action,
        out[f"{call_prefix}_opt_exit_minutes"],
        out[f"{put_prefix}_opt_exit_minutes"],
    )
    out["exit_status"] = np.where(
        call_action,
        out[f"{call_prefix}_opt_status"],
        out[f"{put_prefix}_opt_status"],
    )
    holds = pd.to_numeric(out["exit_minutes"], errors="coerce")
    if not np.isfinite(holds).all() or not holds.between(30, 180).all():
        bad = out.loc[~holds.between(30, 180), ["ticker", "trade_date", "minute"]]
        raise RuntimeError(f"physical hold outside 30..180: {bad.head(10).to_dict('records')}")
    returns = pd.to_numeric(out["realized_return"], errors="coerce")
    if not np.isfinite(returns).all():
        raise RuntimeError("non-finite physical return")
    return out


def momentum_bits(scored: pd.DataFrame) -> np.ndarray:
    action_call = scored["action"].astype(str).eq("CALL").to_numpy()
    action_put = ~action_call
    bits = np.ones(len(scored), dtype=np.int16)

    def add(bit: int, column: str, same: bool) -> None:
        values = pd.to_numeric(scored[column], errors="coerce").to_numpy(dtype=float)
        if same:
            mask = (
                (action_call & (values >= 0.0))
                | (action_put & (values <= 0.0))
            ) & np.isfinite(values)
        else:
            mask = (
                (action_call & (values <= 0.0))
                | (action_put & (values >= 0.0))
            ) & np.isfinite(values)
        bits[mask] |= np.int16(1 << bit)

    add(1, "ret_5m_bps", False)
    add(2, "ret_5m_bps", True)
    add(3, "ctx_spx_ret_5m_bps", False)
    add(4, "ctx_spx_ret_5m_bps", True)
    add(5, "ctx_qqq_ret_5m_bps", False)
    add(6, "ctx_qqq_ret_5m_bps", True)
    return bits


def base_grid_arrays() -> tuple[np.ndarray, ...]:
    rows: list[tuple[float, float, int, int, int, float, int]] = []
    for threshold in THRESHOLDS:
        for edge in EDGES:
            for action_index, _action in enumerate(ACTIONS):
                for time_min, time_max in TIME_WINDOWS:
                    for near in NEAR_VALUES:
                        for momentum_index, _momentum in enumerate(MOMENTUM):
                            rows.append(
                                (
                                    float(threshold),
                                    float(edge),
                                    int(action_index),
                                    int(time_min),
                                    int(time_max),
                                    float(near),
                                    int(momentum_index),
                                )
                            )
    if len(rows) != BASE_CONFIGS:
        raise AssertionError(f"base grid mismatch: {len(rows)} != {BASE_CONFIGS}")
    array = np.asarray(rows, dtype=np.float64)
    return (
        array[:, 0].astype(np.float64),
        array[:, 1].astype(np.float64),
        array[:, 2].astype(np.int8),
        array[:, 3].astype(np.int16),
        array[:, 4].astype(np.int16),
        array[:, 5].astype(np.float64),
        array[:, 6].astype(np.int8),
    )


@njit(cache=True, parallel=True)
def _scan_grid_core(
    score: np.ndarray,
    edge: np.ndarray,
    minute: np.ndarray,
    near: np.ndarray,
    realized_return: np.ndarray,
    action_code: np.ndarray,
    date_code: np.ndarray,
    month_index: np.ndarray,
    exit_status: np.ndarray,
    exit_minutes: np.ndarray,
    momentum_mask: np.ndarray,
    grid_threshold: np.ndarray,
    grid_edge: np.ndarray,
    grid_action: np.ndarray,
    grid_tmin: np.ndarray,
    grid_tmax: np.ndarray,
    grid_near: np.ndarray,
    grid_momentum: np.ndarray,
    is_spxw: bool,
    min_month_trades: int,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    base_count = len(grid_threshold)
    valid = np.zeros(base_count, dtype=np.int8)
    best_positive_months = np.full(base_count, -1, dtype=np.int8)
    best_worst_pnl = np.full(base_count, -np.inf, dtype=np.float64)
    best_pf = np.full(base_count, -np.inf, dtype=np.float64)
    best_pnl = np.full(base_count, -np.inf, dtype=np.float64)
    best_wr = np.full(base_count, -np.inf, dtype=np.float64)
    best_min_trades = np.zeros(base_count, dtype=np.int16)
    best_max_day = np.zeros(base_count, dtype=np.int8)
    best_cooldown = np.zeros(base_count, dtype=np.int16)
    best_grid_index = np.full(base_count, -1, dtype=np.int64)

    for base_index in prange(base_count):
        counts = np.zeros((2, 4, 6), dtype=np.int32)
        pnls = np.zeros((2, 4, 6), dtype=np.float64)
        gross_profit = np.zeros((2, 4), dtype=np.float64)
        gross_loss = np.zeros((2, 4), dtype=np.float64)
        wins = np.zeros((2, 4), dtype=np.int32)
        totals = np.zeros((2, 4), dtype=np.int32)
        current_date = np.full(2, -1, dtype=np.int64)
        taken = np.zeros(2, dtype=np.int8)
        next_allowed = np.full(2, -1, dtype=np.int16)
        pause_minute = np.full(2, -1, dtype=np.int16)

        for row_index in range(len(score)):
            row_score = score[row_index]
            if not np.isfinite(row_score) or row_score < grid_threshold[base_index]:
                continue
            row_edge = edge[row_index]
            if not np.isfinite(row_edge) or row_edge < grid_edge[base_index]:
                continue
            row_minute = minute[row_index]
            if (
                row_minute < grid_tmin[base_index]
                or row_minute > grid_tmax[base_index]
            ):
                continue
            row_near = near[row_index]
            if not np.isfinite(row_near) or row_near > grid_near[base_index]:
                continue
            action_filter = grid_action[base_index]
            if action_filter == 1 and action_code[row_index] != 1:
                continue
            if action_filter == 2 and action_code[row_index] != 2:
                continue
            momentum_index = grid_momentum[base_index]
            if (momentum_mask[row_index] & (1 << momentum_index)) == 0:
                continue

            row_date = date_code[row_index]
            row_month = month_index[row_index]
            row_return = realized_return[row_index]
            row_exit = exit_minutes[row_index]
            for cooldown_mode in range(2):
                if current_date[cooldown_mode] != row_date:
                    current_date[cooldown_mode] = row_date
                    taken[cooldown_mode] = 0
                    next_allowed[cooldown_mode] = -1
                    pause_minute[cooldown_mode] = -1
                if (
                    is_spxw
                    and pause_minute[cooldown_mode] >= 0
                    and row_minute >= pause_minute[cooldown_mode]
                ):
                    continue
                if row_minute < next_allowed[cooldown_mode]:
                    continue
                if taken[cooldown_mode] >= 4:
                    continue

                order_in_day = taken[cooldown_mode]
                taken[cooldown_mode] += 1
                for cap_index in range(order_in_day, 4):
                    counts[cooldown_mode, cap_index, row_month] += 1
                    pnls[cooldown_mode, cap_index, row_month] += row_return
                    totals[cooldown_mode, cap_index] += 1
                    if row_return > 0.0:
                        gross_profit[cooldown_mode, cap_index] += row_return
                        wins[cooldown_mode, cap_index] += 1
                    elif row_return < 0.0:
                        gross_loss[cooldown_mode, cap_index] += -row_return

                cooldown = 0 if cooldown_mode == 0 else 45
                cooldown_until = row_minute + cooldown
                position_until = row_minute + int(math.ceil(row_exit))
                next_allowed[cooldown_mode] = max(cooldown_until, position_until)
                if is_spxw and (
                    exit_status[row_index] < 0.0 or row_return <= -0.599
                ):
                    pause_minute[cooldown_mode] = position_until

        local_valid = False
        local_positive = -1
        local_worst = -np.inf
        local_pf = -np.inf
        local_pnl = -np.inf
        local_wr = -np.inf
        local_min_trades = 0
        local_max_day = 0
        local_cooldown = 0
        local_grid_index = -1

        for cooldown_mode in range(2):
            cooldown = 0 if cooldown_mode == 0 else 45
            cooldown_index = 0 if cooldown_mode == 0 else 3
            for cap_index in range(4):
                minimum = counts[cooldown_mode, cap_index, 0]
                positive_months = 0
                worst = pnls[cooldown_mode, cap_index, 0]
                pnl = 0.0
                for month_index_value in range(6):
                    count = counts[cooldown_mode, cap_index, month_index_value]
                    if count < minimum:
                        minimum = count
                    month_pnl = pnls[cooldown_mode, cap_index, month_index_value]
                    if month_pnl > 0.0:
                        positive_months += 1
                    if month_pnl < worst:
                        worst = month_pnl
                    pnl += month_pnl
                if minimum < min_month_trades:
                    continue
                loss = gross_loss[cooldown_mode, cap_index]
                pf = (
                    gross_profit[cooldown_mode, cap_index] / loss
                    if loss > 0.0
                    else np.inf
                )
                total = totals[cooldown_mode, cap_index]
                wr = (
                    wins[cooldown_mode, cap_index] / total
                    if total > 0
                    else -np.inf
                )
                grid_index = (
                    base_index * 16 + cap_index * 4 + cooldown_index
                )
                better = False
                if not local_valid:
                    better = True
                elif positive_months != local_positive:
                    better = positive_months > local_positive
                elif worst != local_worst:
                    better = worst > local_worst
                elif pf != local_pf:
                    better = pf > local_pf
                elif pnl != local_pnl:
                    better = pnl > local_pnl
                elif wr != local_wr:
                    better = wr > local_wr
                elif minimum != local_min_trades:
                    better = minimum > local_min_trades
                elif grid_index != local_grid_index:
                    better = grid_index < local_grid_index
                if better:
                    local_valid = True
                    local_positive = positive_months
                    local_worst = worst
                    local_pf = pf
                    local_pnl = pnl
                    local_wr = wr
                    local_min_trades = minimum
                    local_max_day = cap_index + 1
                    local_cooldown = cooldown
                    local_grid_index = grid_index

        if local_valid:
            valid[base_index] = 1
            best_positive_months[base_index] = local_positive
            best_worst_pnl[base_index] = local_worst
            best_pf[base_index] = local_pf
            best_pnl[base_index] = local_pnl
            best_wr[base_index] = local_wr
            best_min_trades[base_index] = local_min_trades
            best_max_day[base_index] = local_max_day
            best_cooldown[base_index] = local_cooldown
            best_grid_index[base_index] = local_grid_index

    return (
        valid,
        best_positive_months,
        best_worst_pnl,
        best_pf,
        best_pnl,
        best_wr,
        best_min_trades,
        best_max_day,
        best_cooldown,
        best_grid_index,
    )


def _sorted_scored(scored: pd.DataFrame) -> pd.DataFrame:
    return scored.sort_values(
        ["trade_date", "minute", "score"],
        ascending=[True, True, False],
        kind="stable",
    ).reset_index(drop=True)


def scan_grid(scored_selection: pd.DataFrame, ticker: str) -> tuple[OverlayConfig | None, dict]:
    ordered = _sorted_scored(scored_selection)
    month_values = selection_months(str(ordered["test_month"].iloc[0]))
    month_map = {month: index for index, month in enumerate(month_values)}
    ordered["selection_month_index"] = (
        ordered["month"].astype(str).map(month_map).astype(int)
    )
    action_code = np.where(ordered["action"].astype(str).eq("CALL"), 1, 2).astype(
        np.int8
    )
    arrays = base_grid_arrays()
    result = _scan_grid_core(
        pd.to_numeric(ordered["score"], errors="coerce").to_numpy(dtype=float),
        pd.to_numeric(ordered["edge_abs"], errors="coerce").to_numpy(dtype=float),
        pd.to_numeric(ordered["minute"], errors="raise").to_numpy(dtype=np.int16),
        pd.to_numeric(ordered["nearest_level_abs_bps"], errors="coerce")
        .abs()
        .to_numpy(dtype=float),
        pd.to_numeric(ordered["realized_return"], errors="raise").to_numpy(dtype=float),
        action_code,
        pd.to_numeric(ordered["trade_date"], errors="raise").to_numpy(dtype=np.int64),
        ordered["selection_month_index"].to_numpy(dtype=np.int8),
        pd.to_numeric(ordered["exit_status"], errors="raise").to_numpy(dtype=float),
        pd.to_numeric(ordered["exit_minutes"], errors="raise").to_numpy(dtype=float),
        momentum_bits(ordered),
        *arrays,
        ticker == "SPXW",
        MIN_MONTH_TRADES,
    )
    (
        valid,
        positive_months,
        worst_pnl,
        profit_factor,
        pnl,
        win_rate,
        min_trades,
        max_day,
        cooldown,
        grid_index,
    ) = result
    eligible_base = np.flatnonzero(valid)
    if not len(eligible_base):
        return None, {
            "evaluated_configurations": FULL_CONFIGS,
            "base_configurations": BASE_CONFIGS,
            "frequency_eligible_base_winners": 0,
            "status": "ABSTAIN_NO_FREQUENCY_ELIGIBLE",
        }

    def key(index: int) -> tuple:
        return (
            int(positive_months[index]),
            float(worst_pnl[index]),
            float(profit_factor[index]),
            float(pnl[index]),
            float(win_rate[index]),
            int(min_trades[index]),
            -int(grid_index[index]),
        )

    best_base = max((int(index) for index in eligible_base), key=key)
    base_index = int(grid_index[best_base]) // 16
    threshold, edge, action, time_min, time_max, near, momentum = (
        values[base_index] for values in arrays
    )
    config = OverlayConfig(
        threshold=float(threshold),
        edge=float(edge),
        action=ACTIONS[int(action)],
        time_min=int(time_min),
        time_max=int(time_max),
        near_bps=float(near),
        momentum=MOMENTUM[int(momentum)],
        max_day=int(max_day[best_base]),
        cooldown=int(cooldown[best_base]),
        grid_index=int(grid_index[best_base]),
    )
    return config, {
        "evaluated_configurations": FULL_CONFIGS,
        "base_configurations": BASE_CONFIGS,
        "frequency_eligible_base_winners": int(len(eligible_base)),
        "status": "WINNER_FROZEN",
        "rank": {
            "positive_months": int(positive_months[best_base]),
            "worst_month_pnl": float(worst_pnl[best_base]),
            "profit_factor": float(profit_factor[best_base]),
            "pnl_return": float(pnl[best_base]),
            "win_rate": float(win_rate[best_base]),
            "min_month_trades": int(min_trades[best_base]),
            "grid_index": int(grid_index[best_base]),
        },
    }


def config_mask(scored: pd.DataFrame, config: OverlayConfig) -> np.ndarray:
    action = scored["action"].astype(str)
    bits = momentum_bits(scored)
    mask = (
        np.isfinite(pd.to_numeric(scored["score"], errors="coerce"))
        & (pd.to_numeric(scored["score"], errors="coerce") >= config.threshold)
        & np.isfinite(pd.to_numeric(scored["edge_abs"], errors="coerce"))
        & (pd.to_numeric(scored["edge_abs"], errors="coerce") >= config.edge)
        & (pd.to_numeric(scored["minute"], errors="coerce") >= config.time_min)
        & (pd.to_numeric(scored["minute"], errors="coerce") <= config.time_max)
        & np.isfinite(pd.to_numeric(scored["nearest_level_abs_bps"], errors="coerce"))
        & (
            pd.to_numeric(scored["nearest_level_abs_bps"], errors="coerce").abs()
            <= config.near_bps
        )
        & ((bits & (1 << MOMENTUM.index(config.momentum))) != 0)
    )
    if config.action == "CALL":
        mask &= action.eq("CALL").to_numpy()
    elif config.action == "PUT":
        mask &= action.eq("PUT").to_numpy()
    return np.asarray(mask, dtype=bool)


def replay_config(
    scored: pd.DataFrame,
    config: OverlayConfig,
    ticker: str,
) -> pd.DataFrame:
    candidates = _sorted_scored(scored.loc[config_mask(scored, config)].copy())
    selected: list[int] = []
    current_date = ""
    taken = 0
    next_allowed = -1
    pause_minute = -1
    for index, row in candidates.iterrows():
        date = str(row["trade_date"])
        minute = int(row["minute"])
        if date != current_date:
            current_date = date
            taken = 0
            next_allowed = -1
            pause_minute = -1
        if ticker == "SPXW" and pause_minute >= 0 and minute >= pause_minute:
            continue
        if minute < next_allowed or taken >= config.max_day:
            continue
        hold = float(row["exit_minutes"])
        if not math.isfinite(hold) or not 30.0 <= hold <= 180.0:
            raise RuntimeError(f"invalid hold selected at {ticker} {date} {minute}: {hold}")
        selected.append(int(index))
        taken += 1
        position_until = minute + int(math.ceil(hold))
        next_allowed = max(minute + config.cooldown, position_until)
        if ticker == "SPXW" and (
            float(row["exit_status"]) < 0.0
            or float(row["realized_return"]) <= -0.599
        ):
            pause_minute = position_until
    if not selected:
        return candidates.iloc[0:0].copy()
    out = candidates.loc[selected].copy()
    out["deploy_config"] = config.name
    out["grid_index"] = config.grid_index
    return out.reset_index(drop=True)


def economic_metrics(trades: pd.DataFrame, months: list[str]) -> dict:
    work = trades.copy()
    if work.empty:
        monthly = {
            month: {"trades": 0, "pnl_return": 0.0} for month in months
        }
        return {
            "trades": 0,
            "win_rate": None,
            "profit_factor": None,
            "pnl_return": 0.0,
            "min_month_trades": 0,
            "positive_months": 0,
            "monthly": monthly,
        }
    returns = pd.to_numeric(work["realized_return"], errors="raise").to_numpy(dtype=float)
    gross_profit = float(returns[returns > 0.0].sum())
    gross_loss = float(-returns[returns < 0.0].sum())
    monthly: dict[str, dict] = {}
    for month in months:
        part = work.loc[work["month"].astype(str).eq(month)]
        monthly[month] = {
            "trades": int(len(part)),
            "pnl_return": float(
                pd.to_numeric(part["realized_return"], errors="raise").sum()
            ),
        }
    return {
        "trades": int(len(work)),
        "win_rate": float((returns > 0.0).mean()),
        "profit_factor": (
            float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf")
        ),
        "pnl_return": float(returns.sum()),
        "min_month_trades": min(item["trades"] for item in monthly.values()),
        "positive_months": sum(item["pnl_return"] > 0.0 for item in monthly.values()),
        "monthly": monthly,
    }


def passes_final_gates(metrics: dict) -> bool:
    pf = metrics.get("profit_factor")
    wr = metrics.get("win_rate")
    return bool(
        pf is not None
        and float(pf) > 1.20
        and wr is not None
        and float(wr) > 0.45
        and float(metrics["pnl_return"]) > 0.0
        and int(metrics["min_month_trades"]) >= 13
        and int(metrics["positive_months"]) == 6
    )


def save_model_artifacts(
    artifact_dir: Path,
    call_model: lgb.LGBMRegressor,
    put_model: lgb.LGBMRegressor,
    medians: pd.Series,
    feature_columns: list[str],
) -> dict:
    artifact_dir.mkdir(parents=True, exist_ok=False)
    call_path = artifact_dir / "call_model.txt"
    put_path = artifact_dir / "put_model.txt"
    median_path = artifact_dir / "medians.csv"
    feature_path = artifact_dir / "feature_columns.json"
    call_path.write_bytes(call_model.booster_.model_to_string().encode("utf-8"))
    put_path.write_bytes(put_model.booster_.model_to_string().encode("utf-8"))
    medians.rename("median").to_csv(median_path, index_label="feature", lineterminator="\n")
    write_json(feature_path, feature_columns)
    return {
        "call_model": {"path": call_path.name, "sha256": sha256_file(call_path)},
        "put_model": {"path": put_path.name, "sha256": sha256_file(put_path)},
        "medians": {"path": median_path.name, "sha256": sha256_file(median_path)},
        "features": {"path": feature_path.name, "sha256": sha256_file(feature_path)},
    }


def run(args: argparse.Namespace) -> dict:
    source = Path(args.source)
    output = Path(args.output_dir)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing result: {output}")
    stager = output.with_name(f"{output.name}.staging_{os.getpid()}")
    if stager.exists():
        raise FileExistsError(f"stager already exists: {stager}")

    parquet = validate_source(source)
    feature_view, feature_columns = load_feature_view(source, parquet)
    contract_sha = sha256_file(CONTRACT_PATH)
    evaluator_sha = sha256_file(Path(__file__))
    auditor_sha = sha256_file(AUDITOR_PATH)
    head = git_head()

    stager.mkdir(parents=True)
    policies_dir = stager / "fold_policy_artifacts"
    policies_dir.mkdir()
    all_test_trades: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    policy_index: list[dict] = []

    for test_month in TEST_MONTHS:
        val_months = selection_months(test_month)
        train_month_list = training_months(test_month)
        first_val = val_months[0]
        for ticker in TICKERS:
            print(
                f"[FULL_NESTED] start ticker={ticker} test={test_month} "
                f"train={train_month_list[0]}..{train_month_list[-1]} "
                f"select={val_months[0]}..{val_months[-1]}",
                flush=True,
            )
            delta = DELTA_BY_TICKER[ticker]
            ticker_features = eligible_feature_rows(feature_view, ticker, delta)
            past_features = ticker_features.loc[
                ticker_features["month"].astype(str).lt(test_month)
            ].copy()
            past_outcomes = load_outcomes(
                source,
                ticker,
                "202501",
                test_month,
                delta,
            )
            past = merge_outcomes(past_features, past_outcomes, delta)
            train = past.loc[past["month"].astype(str).lt(first_val)].copy()
            selection = past.loc[
                past["month"].astype(str).isin(val_months)
            ].copy()
            observed_train_months = sorted(train["month"].astype(str).unique())
            observed_selection_months = sorted(selection["month"].astype(str).unique())
            if observed_train_months != train_month_list:
                raise RuntimeError(
                    f"training month mismatch {ticker} {test_month}: "
                    f"{observed_train_months} != {train_month_list}"
                )
            if observed_selection_months != val_months:
                raise RuntimeError(
                    f"selection month mismatch {ticker} {test_month}: "
                    f"{observed_selection_months} != {val_months}"
                )
            call_model, put_model, medians = fit_models(
                train,
                feature_columns,
                test_month,
                int(args.lgb_jobs),
            )
            selection_scored = bind_physical_outcome(
                predict_scores(
                    selection,
                    feature_columns,
                    call_model,
                    put_model,
                    medians,
                ),
                delta,
            )
            selection_scored["test_month"] = test_month
            config, scan = scan_grid(selection_scored, ticker)
            artifact_dir = policies_dir / f"{ticker}_{test_month}"
            artifacts = save_model_artifacts(
                artifact_dir,
                call_model,
                put_model,
                medians,
                feature_columns,
            )
            selection_prediction_columns = [
                "ticker",
                "trade_date",
                "minute",
                "pred_call_return",
                "pred_put_return",
                "action",
                "score",
            ]
            selection_prediction_sha = dataframe_sha(
                selection_scored,
                selection_prediction_columns,
                ["ticker", "trade_date", "minute"],
            )
            if config is None:
                selection_trades = selection_scored.iloc[0:0].copy()
                selection_metrics = economic_metrics(selection_trades, val_months)
            else:
                selection_trades = replay_config(selection_scored, config, ticker)
                selection_metrics = economic_metrics(selection_trades, val_months)
                rank = scan["rank"]
                if (
                    int(selection_metrics["positive_months"])
                    != int(rank["positive_months"])
                    or int(selection_metrics["min_month_trades"])
                    != int(rank["min_month_trades"])
                    or not math.isclose(
                        float(selection_metrics["pnl_return"]),
                        float(rank["pnl_return"]),
                        rel_tol=0.0,
                        abs_tol=1e-10,
                    )
                ):
                    raise RuntimeError(
                        f"Numba/Python winner replay mismatch {ticker} {test_month}"
                    )

            policy = {
                "schema_version": 1,
                "family": "EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1",
                "git_head": head,
                "ticker": ticker,
                "test_month": test_month,
                "training_months": train_month_list,
                "selection_months": val_months,
                "profile": PROFILE_BY_TICKER[ticker],
                "delta": delta,
                "source_sha256": SOURCE_SHA256,
                "contract_sha256": contract_sha,
                "evaluator_sha256": evaluator_sha,
                "auditor_sha256": auditor_sha,
                "feature_count": FEATURE_COUNT,
                "features_sha256": FEATURES_SHA256,
                "model_params": MODEL_PARAMS,
                "train_rows": int(len(train)),
                "selection_rows": int(len(selection)),
                "selection_prediction_sha256": selection_prediction_sha,
                "scan": scan,
                "winner": asdict(config) if config is not None else None,
                "winner_name": config.name if config is not None else scan["status"],
                "selection_metrics": selection_metrics,
                "artifacts": artifacts,
                "policy_frozen_before_test_outcome_read": True,
            }
            policy_path = artifact_dir / "fold_policy.json"
            write_json(policy_path, policy)
            policy_sha = sha256_file(policy_path)

            # The fold policy is now physically materialized. Only now may the
            # runner score test features and open this month's outcome columns.
            test_features = ticker_features.loc[
                ticker_features["month"].astype(str).eq(test_month)
            ].copy()
            test_feature_scored = predict_scores(
                test_features,
                feature_columns,
                call_model,
                put_model,
                medians,
            )
            test_outcomes = load_outcomes(
                source,
                ticker,
                test_month,
                next_month(test_month),
                delta,
            )
            test_scored = bind_physical_outcome(
                merge_outcomes(test_feature_scored, test_outcomes, delta),
                delta,
            )
            test_scored["test_month"] = test_month
            if config is None:
                test_trades = test_scored.iloc[0:0].copy()
            else:
                test_trades = replay_config(test_scored, config, ticker)
            if not test_trades.empty:
                test_trades["test_month"] = test_month
                test_trades["profile"] = PROFILE_BY_TICKER[ticker]
                test_trades["delta_bucket"] = delta
                test_trades["policy_sha256"] = policy_sha
                all_test_trades.append(test_trades)
            test_metrics = economic_metrics(test_trades, [test_month])
            test_prediction_sha = dataframe_sha(
                test_scored,
                selection_prediction_columns,
                ["ticker", "trade_date", "minute"],
            )
            fold_rows.append(
                {
                    "ticker": ticker,
                    "test_month": test_month,
                    "training_months": ",".join(train_month_list),
                    "selection_months": ",".join(val_months),
                    "profile": PROFILE_BY_TICKER[ticker],
                    "delta": delta,
                    "train_rows": int(len(train)),
                    "selection_rows": int(len(selection)),
                    "test_rows": int(len(test_scored)),
                    "winner_name": config.name if config is not None else scan["status"],
                    "grid_index": config.grid_index if config is not None else -1,
                    "policy_sha256": policy_sha,
                    "selection_prediction_sha256": selection_prediction_sha,
                    "test_prediction_sha256": test_prediction_sha,
                    "selection_trades": selection_metrics["trades"],
                    "selection_pf": selection_metrics["profit_factor"],
                    "selection_pnl": selection_metrics["pnl_return"],
                    "selection_positive_months": selection_metrics["positive_months"],
                    "selection_min_month_trades": selection_metrics["min_month_trades"],
                    "test_trades": test_metrics["trades"],
                    "test_win_rate": test_metrics["win_rate"],
                    "test_pf": test_metrics["profit_factor"],
                    "test_pnl": test_metrics["pnl_return"],
                }
            )
            policy_index.append(
                {
                    "ticker": ticker,
                    "test_month": test_month,
                    "path": str(policy_path.relative_to(stager)).replace("\\", "/"),
                    "sha256": policy_sha,
                }
            )
            print(
                f"[FULL_NESTED] frozen ticker={ticker} test={test_month} "
                f"winner={config.name if config is not None else scan['status']} "
                f"test_trades={test_metrics['trades']} "
                f"test_pf={test_metrics['profit_factor']} "
                f"test_pnl={test_metrics['pnl_return']:.6f}",
                flush=True,
            )

    trades = (
        pd.concat(all_test_trades, ignore_index=True)
        if all_test_trades
        else pd.DataFrame(
            columns=[
                "ticker",
                "trade_date",
                "month",
                "minute",
                "action",
                "realized_return",
                "exit_minutes",
            ]
        )
    )
    trades = trades.sort_values(
        ["test_month", "ticker", "trade_date", "minute"],
        kind="stable",
    ).reset_index(drop=True)
    fold_frame = pd.DataFrame(fold_rows).sort_values(
        ["test_month", "ticker"], kind="stable"
    )
    keep_trade_columns = [
        "ticker",
        "trade_date",
        "date",
        "month",
        "time",
        "minute",
        "expiry_mode",
        "option_price_mode",
        "profile",
        "delta_bucket",
        "action",
        "score",
        "pred_call_return",
        "pred_put_return",
        "edge_abs",
        "realized_return",
        "exit_minutes",
        "exit_status",
        "nearest_level_name",
        "nearest_level_abs_bps",
        "ret_5m_bps",
        "ctx_spx_ret_5m_bps",
        "ctx_qqq_ret_5m_bps",
        "deploy_config",
        "grid_index",
        "test_month",
        "policy_sha256",
    ]
    keep_trade_columns = [column for column in keep_trade_columns if column in trades.columns]
    trades = trades.loc[:, keep_trade_columns]
    trades_path = stager / "test_only_trades.parquet"
    folds_path = stager / "fold_results.csv"
    policies_path = stager / "policy_index.json"
    trades.to_parquet(trades_path, index=False)
    fold_frame.to_csv(folds_path, index=False, lineterminator="\n")
    write_json(policies_path, policy_index)

    ticker_metrics = {
        ticker: economic_metrics(
            trades.loc[trades["ticker"].astype(str).eq(ticker)].copy(),
            list(TEST_MONTHS),
        )
        for ticker in TICKERS
    }
    ticker_pass = {
        ticker: passes_final_gates(ticker_metrics[ticker]) for ticker in TICKERS
    }
    all_pass = all(ticker_pass.values())
    summary = {
        "schema_version": 1,
        "family": "EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1",
        "status": (
            "PASS_DEVELOPMENT_REQUIRES_FUTURE_SHADOW"
            if all_pass
            else "FAILED_DEVELOPMENT_FULL_GATES"
        ),
        "promotable": False,
        "reason_not_promotable": "2026 was already seen before this family was declared",
        "git_head": head,
        "source": {
            "path": str(source).replace("\\", "/"),
            "bytes": SOURCE_BYTES,
            "rows": SOURCE_ROWS,
            "sha256": SOURCE_SHA256,
            "option_price_mode": "executable_quote",
        },
        "contract_sha256": contract_sha,
        "evaluator_sha256": evaluator_sha,
        "auditor_sha256": auditor_sha,
        "feature_count": FEATURE_COUNT,
        "features_sha256": FEATURES_SHA256,
        "test_months": list(TEST_MONTHS),
        "folds": int(len(fold_frame)),
        "configurations_per_ticker_fold": FULL_CONFIGS,
        "total_logical_configurations": FULL_CONFIGS * len(TICKERS) * len(TEST_MONTHS),
        "test_only_ledger": True,
        "policy_frozen_before_test_outcome_read": True,
        "ticker_metrics": ticker_metrics,
        "ticker_pass": ticker_pass,
        "all_tickers_pass": all_pass,
        "artifacts": {
            "test_only_trades": {
                "path": trades_path.name,
                "rows": int(len(trades)),
                "sha256": sha256_file(trades_path),
            },
            "fold_results": {
                "path": folds_path.name,
                "rows": int(len(fold_frame)),
                "sha256": sha256_file(folds_path),
            },
            "policy_index": {
                "path": policies_path.name,
                "rows": int(len(policy_index)),
                "sha256": sha256_file(policies_path),
            },
        },
        "outcome_access": {
            "selection_outcomes_before_fold_freeze": True,
            "test_outcomes_before_fold_freeze": False,
            "test_outcomes_after_fold_freeze": True,
        },
        "live_modified": False,
    }
    summary_path = stager / "evaluation_summary.json"
    write_json(summary_path, summary)
    os.replace(stager, output)
    print(json.dumps(_json_ready(summary), indent=2, sort_keys=True), flush=True)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full nested monthly executable-quote overlay development evaluation"
    )
    parser.add_argument("--source", default=str(SOURCE_PATH))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--lgb-jobs", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    run(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
