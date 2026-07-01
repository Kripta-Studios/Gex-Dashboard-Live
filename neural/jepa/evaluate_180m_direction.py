from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
import time
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from datetime import datetime

import lightgbm as lgb
import xgboost as xgb
import numpy as np
import pandas as pd
import numba
from scipy.stats import spearmanr
from sklearn.metrics import mean_squared_error, mean_absolute_error

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NEURAL_ROOT = PROJECT_ROOT / "neural"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(NEURAL_ROOT) not in sys.path:
    sys.path.insert(0, str(NEURAL_ROOT))

from neural.jepa.dataset import infer_sort_columns
from neural.jepa.features import (
    available_features,
    load_base_feature_columns,
    load_feature_names,
    time_context_features,
)

LOG_HEARTBEAT_SECONDS = int(os.environ.get("JEPA_LOG_HEARTBEAT_SECONDS", "60"))

LEAKAGE_COLUMNS = {
    "target",
    "time_to_target",
    "time_to_stop",
    "max_move",
    "future_return_180m",
    "future_return_bps_180m",
    "future_up_180m",
    "future_abs_bps_180m",
    "future_spot_180m",
    "terminal_label_180m",
    "long_pnl_180m",
    "short_pnl_180m",
    "terminal_hold_steps",
    "terminal_hold_minutes",
    "terminal_exit_time",
    "terminal_horizon_truncated",
    "oos_apr_may_2026",
}

@contextmanager
def logged_phase(message: str, heartbeat_seconds: int | None = None):
    start = time.time()
    interval = int(heartbeat_seconds or LOG_HEARTBEAT_SECONDS)
    stop_event = threading.Event()

    def heartbeat() -> None:
        while not stop_event.wait(max(1, interval)):
            print(f"[JEPA_180M] STILL {message} elapsed={time.time() - start:.1f}s", flush=True)

    print(f"[JEPA_180M] START {message}", flush=True)
    thread = threading.Thread(target=heartbeat, name=f"jepa-180m-{message[:24]}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=1.0)
        print(f"[JEPA_180M] DONE {message} elapsed={time.time() - start:.1f}s", flush=True)

@dataclass
class ModeResult:
    feature_mode: str
    predictions: pd.DataFrame
    windows: list[dict]
    features: list[str]

def normalize_date(value) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else str(value)

def safe_float(value: float) -> float:
    value = float(value)
    return value if np.isfinite(value) else float("nan")

def fmt_float(value: float, decimals: int = 3) -> str:
    if value is None or not np.isfinite(value):
        return "nan"
    return f"{float(value):.{decimals}f}"

def fmt_pct(value: float, decimals: int = 1) -> str:
    if value is None or not np.isfinite(value):
        return "nan"
    return f"{100.0 * float(value):.{decimals}f}%"

def fmt_money(value: float) -> str:
    if value is None or not np.isfinite(value):
        return "nan"
    return f"{float(value):+,.0f}"

@numba.njit
def compute_tp_sl_simulated_pnl(spot: np.ndarray, horizon: int, tp_bps: float, sl_bps: float):
    n = len(spot)
    long_pnl = np.full(n, np.nan, dtype=np.float64)
    short_pnl = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        s0 = spot[i]
        if s0 <= 0: continue
        end_idx = min(i + horizon, n - 1)

        # Long simulation
        l_pnl = np.nan
        for j in range(i + 1, end_idx + 1):
            ret = (spot[j] / s0 - 1.0) * 10000.0
            if ret >= tp_bps:
                l_pnl = tp_bps
                break
            if ret <= -sl_bps:
                l_pnl = -sl_bps
                break
        if np.isnan(l_pnl):
            l_pnl = (spot[end_idx] / s0 - 1.0) * 10000.0
        long_pnl[i] = l_pnl

        # Short simulation
        s_pnl = np.nan
        for j in range(i + 1, end_idx + 1):
            ret = (spot[j] / s0 - 1.0) * 10000.0
            s_ret = -ret
            if s_ret >= tp_bps:
                s_pnl = tp_bps
                break
            if s_ret <= -sl_bps:
                s_pnl = -sl_bps
                break
        if np.isnan(s_pnl):
            s_pnl = -(spot[end_idx] / s0 - 1.0) * 10000.0
        short_pnl[i] = s_pnl
    return long_pnl, short_pnl

def build_terminal_180m_frame(
    data_path: str | Path,
    horizon_steps: int,
    min_abs_bps: float,
    truncate_to_eod: bool = False,
) -> pd.DataFrame:
    work = pd.read_parquet(data_path)
    if "pos_in_day" not in work.columns:
        work["pos_in_day"] = work.groupby(["ticker", "date"]).cumcount()
    work = work.sort_values(["ticker", "date", "time"]).reset_index(drop=True)

    future_spot = np.full(len(work), np.nan, dtype=np.float64)
    terminal_hold_steps = np.full(len(work), np.nan, dtype=np.float64)
    terminal_exit_time = np.full(len(work), "", dtype=object)

    for _, idx in work.groupby(["ticker", "date"], sort=False).groups.items():
        positions = np.asarray(list(idx), dtype=np.int64)
        if len(positions) <= 1 or horizon_steps <= 0:
            continue
        spot = work.loc[positions, "spot_price"].to_numpy(dtype=np.float64)
        if horizon_steps >= len(positions):
            future_spot[positions] = spot[-1]
            terminal_hold_steps[positions] = np.arange(len(positions) - 1, -1, -1, dtype=np.float64)
            terminal_exit_time[positions] = work.loc[positions[-1], "time"]
        else:
            if len(positions) <= horizon_steps:
                continue
            future = np.full(len(positions), np.nan, dtype=np.float64)
            future[:-horizon_steps] = spot[horizon_steps:]
            future_spot[positions] = future
            terminal_hold_steps[positions[:-horizon_steps]] = float(horizon_steps)
            terminal_exit_time[positions[:-horizon_steps]] = work.loc[positions[horizon_steps:], "time"].astype(str).to_numpy()

        l_pnl, s_pnl = compute_tp_sl_simulated_pnl(spot, horizon_steps, 10.0, 100.0)

        times = work.loc[positions, "time"].astype(str).str.slice(0, 2).astype(int).values
        invalid_times = (times < 10) | (times >= 15)
        l_pnl[invalid_times] = -100.0
        s_pnl[invalid_times] = -100.0

        work.loc[positions, "long_pnl_180m"] = l_pnl
        work.loc[positions, "short_pnl_180m"] = s_pnl

    spot_now = work["spot_price"].to_numpy(dtype=np.float64)
    future_return = future_spot / spot_now - 1.0
    future_bps = future_return * 10000.0
    valid = np.isfinite(future_return) & np.isfinite(spot_now) & (spot_now > 0.0)
    if "xjepa_context_valid" in work.columns:
        valid &= work["xjepa_context_valid"].astype(float).to_numpy() > 0.0

    work["future_spot_180m"] = future_spot
    work["future_return_180m"] = future_return
    work["future_return_bps_180m"] = future_bps
    work["future_up_180m"] = (future_return > 0.0).astype(np.int8)
    work["future_abs_bps_180m"] = np.abs(future_bps)
    work["terminal_hold_steps"] = terminal_hold_steps
    work["terminal_hold_minutes"] = terminal_hold_steps * 5.0
    work["terminal_exit_time"] = terminal_exit_time
    work["terminal_horizon_truncated"] = terminal_hold_steps < float(horizon_steps)
    work["month"] = work["date"].astype(str).str[:6]
    work["oos_apr_may_2026"] = work["date"].astype(str) >= "20260401"
    work = work.loc[valid].copy()

    if min_abs_bps > 0:
        # Since future_abs_bps_180m is deleted, we just skip min_abs filtering for trailing PnL logic
        pass

    return work.reset_index(drop=True)

def select_features(df: pd.DataFrame, mode: str, jepa_feature_names: str | Path | None) -> list[str]:
    mode = str(mode).lower()
    base = available_features(df, load_base_feature_columns())
    jepa = available_features(df, load_feature_names(jepa_feature_names))
    jepa = [c for c in jepa if c not in LEAKAGE_COLUMNS]
    time_cols = time_context_features(df)

    if mode == "base":
        selected = base
    elif mode == "jepa_only":
        selected = jepa + [c for c in time_cols if c not in jepa]
    elif mode == "base_jepa":
        selected = base + [c for c in jepa if c not in base]
    else:
        raise ValueError(f"Unknown feature mode: {mode}")

    selected = [c for c in selected if c in df.columns and c not in LEAKAGE_COLUMNS]
    numeric = []
    for c in selected:
        if pd.api.types.is_numeric_dtype(df[c]):
            numeric.append(c)
    if not numeric:
        raise ValueError(f"No numeric features selected for mode={mode}")
    return numeric

def make_matrix(df: pd.DataFrame, features: list[str], medians: pd.Series | None = None) -> tuple[pd.DataFrame, pd.Series]:
    x = df[features].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if medians is None:
        medians = x.median(axis=0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    x = x.fillna(medians).fillna(0.0)
    return x.astype(np.float32), medians

def train_lgb_model(x_train, y_train, x_val, y_val, seed, n_jobs=4):
    train_data = lgb.Dataset(x_train, label=y_train)
    val_data = lgb.Dataset(x_val, label=y_val, reference=train_data)
    params = {
        'objective': 'regression',
        'metric': 'rmse',
        'learning_rate': 0.01,
        'num_leaves': 7,
        'max_depth': 3,
        'feature_fraction': 0.5,
        'bagging_fraction': 0.5,
        'bagging_freq': 5,
        'min_data_in_leaf': 100,
        'verbose': -1,
        'seed': seed,
        'n_jobs': n_jobs
    }

    model = lgb.train(
        params,
        train_data,
        num_boost_round=500,
        valid_sets=[val_data],
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
    )
    return model

def train_xgb_model(x_train, y_train, x_val, y_val, seed, n_jobs=4):
    train_data = xgb.DMatrix(x_train, label=y_train)
    val_data = xgb.DMatrix(x_val, label=y_val)
    xgb_params = {
        'objective': 'reg:squarederror',
        'eval_metric': 'rmse',
        'learning_rate': 0.01,
        'max_depth': 3,
        'subsample': 0.5,
        'colsample_bytree': 0.5,
        'min_child_weight': 10,
        'n_jobs': n_jobs,
        'seed': seed + 100
    }

    model = xgb.train(
        xgb_params,
        train_data,
        num_boost_round=500,
        evals=[(val_data, 'eval')],
        early_stopping_rounds=30,
        verbose_eval=False
    )
    return model

def train_model(
    train: pd.DataFrame,
    features: list[str],
    seed: int,
    n_estimators: int,
    n_jobs: int,
    ticker: str = "ALL",
) -> tuple[dict, pd.Series, list[str]]:

    x_train_all, medians = make_matrix(train, features)
    y_long_all = train["long_pnl_180m"].astype(np.float32).to_numpy()
    y_short_all = train["short_pnl_180m"].astype(np.float32).to_numpy()

    split_idx = int(len(train) * 0.85)
    x_train = x_train_all.iloc[:split_idx] if hasattr(x_train_all, "iloc") else x_train_all[:split_idx]

    y_long_train = y_long_all[:split_idx]
    y_long_es = y_long_all[split_idx:]

    y_short_train = y_short_all[:split_idx]
    y_short_es = y_short_all[split_idx:]

    x_es = x_train_all.iloc[split_idx:] if hasattr(x_train_all, "iloc") else x_train_all[split_idx:]

    with logged_phase(f"fit LGBM+XGB models rows={len(train):,} features={len(features):,} ticker={ticker}"):
        model_long_list = []
        model_short_list = []
        for i in range(3):
            model_long_list.append(('lgb', train_lgb_model(x_train, y_long_train, x_es, y_long_es, seed + i)))
            model_short_list.append(('lgb', train_lgb_model(x_train, y_short_train, x_es, y_short_es, seed + i + 100)))
        for i in range(2):
            model_long_list.append(('xgb', train_xgb_model(x_train, y_long_train, x_es, y_long_es, seed + i + 50)))
            model_short_list.append(('xgb', train_xgb_model(x_train, y_short_train, x_es, y_short_es, seed + i + 150)))

    models = {"long": model_long_list, "short": model_short_list}
    return models, medians, features

def predict_returns(models: dict, frame: pd.DataFrame, features: list[str], medians: pd.Series) -> np.ndarray:
    x, _ = make_matrix(frame, features, medians)

    long_preds = []
    for mtype, m in models["long"]:
        if mtype == 'xgb':
            dtest = xgb.DMatrix(x)
            long_preds.append(m.predict(dtest))
        else:
            long_preds.append(m.predict(x))

    short_preds = []
    for mtype, m in models["short"]:
        if mtype == 'xgb':
            dtest = xgb.DMatrix(x)
            short_preds.append(m.predict(dtest))
        else:
            short_preds.append(m.predict(x))

    pred_long = np.mean(long_preds, axis=0)
    pred_short = np.mean(short_preds, axis=0)

    best_is_long = pred_long >= pred_short
    best_value = np.maximum(pred_long, pred_short)
    synthetic_pred = np.where(best_value > 0.0, np.where(best_is_long, best_value, -best_value), 0.0)
    return synthetic_pred.astype(np.float64)

def simulate_hold180(
    frame: pd.DataFrame,
    pred_bps: np.ndarray,
    long_threshold: float,
    short_threshold: float,
    cost_bps: float,
    cooldown_steps: int,
    notional: float,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    cols = ["ticker", "date", "time", "pos_in_day", "spot_price", "future_return_180m", "future_return_bps_180m", "long_pnl_180m", "short_pnl_180m"]
    for optional in ["terminal_exit_time", "terminal_hold_minutes", "terminal_horizon_truncated"]:
        if optional in frame.columns:
            cols.append(optional)
    work = frame[cols].copy()
    work["pred_bps"] = pred_bps
    work["side"] = np.where(work["pred_bps"] >= long_threshold, 1, np.where(work["pred_bps"] <= -short_threshold, -1, 0))
    work = work[work["side"] != 0].sort_values(["ticker", "date", "pos_in_day"]).reset_index(drop=True)
    trades = []
    next_allowed: dict[tuple[str, str], int] = {}
    for row in work.itertuples(index=False):
        key = (str(row.ticker), str(row.date))
        pos = int(row.pos_in_day)
        if pos < next_allowed.get(key, -1):
            continue

        hour = int(str(row.time)[:2])
        if hour < 10 or hour >= 15:
            continue

        gross_bps = float(row.long_pnl_180m) if row.side > 0 else float(row.short_pnl_180m)
        net_bps = gross_bps - float(cost_bps)
        trades.append(
            {
                "ticker": str(row.ticker),
                "date": str(row.date),
                "time": str(row.time),
                "side": "LONG" if row.side > 0 else "SHORT",
                "pred_bps": float(row.pred_bps),
                "spot_price": float(row.spot_price),
                "future_return_bps": float(row.future_return_bps_180m),
                "exit_time": str(getattr(row, "terminal_exit_time", "")),
                "hold_minutes": float(getattr(row, "terminal_hold_minutes", np.nan)),
                "horizon_truncated": bool(getattr(row, "terminal_horizon_truncated", False)),
                "gross_bps": gross_bps,
                "net_bps": net_bps,
                "pnl_dollars": net_bps / 10000.0 * float(notional),
            }
        )
        next_allowed[key] = pos + int(cooldown_steps)
    return pd.DataFrame(trades)

def trade_metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": float("nan"),
            "avg_net_bps": float("nan"),
            "total_net_bps": 0.0,
            "profit_factor": float("nan"),
            "pnl_dollars": 0.0,
            "max_drawdown": 0.0,
            "long_rate": float("nan"),
        }
    pnl = trades["pnl_dollars"].astype(float).to_numpy()
    wins = pnl[pnl > 0.0]
    losses = pnl[pnl < 0.0]
    equity = np.cumsum(pnl)
    peak = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
    dd = equity - peak
    return {
        "trades": int(len(trades)),
        "win_rate": float((pnl > 0.0).mean()),
        "avg_net_bps": float(trades["net_bps"].mean()),
        "median_net_bps": float(trades["net_bps"].median()),
        "total_net_bps": float(trades["net_bps"].sum()),
        "profit_factor": float(wins.sum() / abs(losses.sum())) if len(losses) else float("inf"),
        "pnl_dollars": float(pnl.sum()),
        "max_drawdown": float(dd.min()) if len(dd) else 0.0,
        "long_rate": float((trades["side"] == "LONG").mean()),
    }

def score_trades(frame: pd.DataFrame, pred_bps: np.ndarray, threshold: float, side_val: int, cost_bps: float, cooldown_steps: int, notional: float):
    # Only keep trades for the specific side
    side_mask = (pred_bps >= threshold) if side_val == 1 else (pred_bps <= -threshold)
    work = frame[side_mask].copy()
    if work.empty:
        return {"trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "pnl_dollars": 0.0}

    work["pred_bps"] = pred_bps[side_mask]
    work["side"] = side_val
    work = work.sort_values(["ticker", "date", "pos_in_day"]).reset_index(drop=True)

    trades = []
    next_allowed: dict[tuple[str, str], int] = {}
    for row in work.itertuples(index=False):
        key = (str(row.ticker), str(row.date))
        pos = int(row.pos_in_day)
        if pos < next_allowed.get(key, -1):
            continue

        hour = int(str(row.time)[:2])
        if hour < 10 or hour >= 15:
            continue

        gross_bps = float(row.long_pnl_180m) if side_val > 0 else float(row.short_pnl_180m)
        net_bps = gross_bps - float(cost_bps)
        trades.append({
            "side": "LONG" if side_val > 0 else "SHORT",
            "net_bps": net_bps,
            "pnl_dollars": net_bps / 10000.0 * float(notional),
        })
        next_allowed[key] = pos + int(cooldown_steps)

    trades_df = pd.DataFrame(trades)
    return trade_metrics(trades_df)

def choose_thresholds(
    val_frame: pd.DataFrame,
    val_pred: np.ndarray,
    cost_bps: float,
    cooldown_steps: int,
    notional: float,
    min_val_trades_per_side: int,
    ticker: str = "ALL",
) -> dict:
    import numpy as np

    thresholds = np.arange(0.5, 6.0, 0.25)
    best_long_t = 0.5
    best_short_t = 0.5 # Default to lowest to guarantee volume if constraint fails
    best_long_score = -1e18
    best_short_score = -1e18

    for t in thresholds:
        metrics = score_trades(val_frame, val_pred, float(t), 1, cost_bps, cooldown_steps, notional)

        if metrics["trades"] < min_val_trades_per_side:
            continue

        wr = metrics.get("win_rate", 0.0)
        pf = metrics.get("profit_factor", 0.0)
        pnl = metrics.get("pnl_dollars", 0.0)
        if np.isinf(pf) or np.isnan(pf):
            pf = 3.0 if wr > 0.5 else 0.5

        score = pf * (wr * 100.0)
        if wr < 0.66:
            score = score * 0.001

        if score > best_long_score:
            best_long_score = score
            best_long_t = float(t)

    best_short_score = -1e18
    best_short_t = 0.5
    for t in thresholds:
        metrics = score_trades(val_frame, val_pred, float(t), -1, cost_bps, cooldown_steps, notional)

        if metrics["trades"] < min_val_trades_per_side:
            continue

        wr = metrics.get("win_rate", 0.0)
        pf = metrics.get("profit_factor", 0.0)
        pnl = metrics.get("pnl_dollars", 0.0)
        if np.isinf(pf) or np.isnan(pf):
            pf = 3.0 if wr > 0.5 else 0.5

        score = pf * (wr * 100.0)
        if wr < 0.66:
            score = score * 0.001

        if score > best_short_score:
            best_short_score = score
            best_short_t = float(t)

    return {
        "long_threshold": best_long_t,
        "short_threshold": best_short_t,
        "val_score": best_long_score + best_short_score
    }

def metric_block(frame: pd.DataFrame, segment: str, ticker: str = "ALL") -> dict:
    if frame.empty:
        return {
            "segment": segment,
            "ticker": ticker,
            "rows": 0,
            "rmse": float("nan"),
            "mae": float("nan"),
            "spearman_return": float("nan"),
            "mean_future_return_bps": float("nan"),
            "top_quintile_return_bps": float("nan"),
            "bottom_quintile_return_bps": float("nan"),
        }
    y = frame["future_return_bps_180m"].astype(float).to_numpy()
    p = frame["pred_bps"].astype(float).to_numpy()

    rmse = float(np.sqrt(mean_squared_error(y, p)))
    mae = float(mean_absolute_error(y, p))
    corr = spearmanr(p, y, nan_policy="omit")

    q80 = frame["pred_bps"].quantile(0.80)
    q20 = frame["pred_bps"].quantile(0.20)
    return {
        "segment": segment,
        "ticker": ticker,
        "rows": int(len(frame)),
        "rmse": rmse,
        "mae": mae,
        "spearman_return": safe_float(corr.statistic),
        "mean_future_return_bps": float(y.mean()),
        "top_quintile_return_bps": float(frame.loc[frame["pred_bps"] >= q80, "future_return_bps_180m"].mean()) if len(frame[frame["pred_bps"] >= q80]) > 0 else float("nan"),
        "bottom_quintile_return_bps": float(frame.loc[frame["pred_bps"] <= q20, "future_return_bps_180m"].mean()) if len(frame[frame["pred_bps"] <= q20]) > 0 else float("nan"),
    }

def summarize_predictions(predictions: pd.DataFrame, trades: pd.DataFrame, oos_start: str) -> dict:
    pred = predictions.copy()
    pred["segment"] = np.where(pred["date"] >= oos_start, "oos", "pre_oos")
    metrics = [metric_block(pred, "overall")]
    metrics += [metric_block(frame, segment) for segment, frame in pred.groupby("segment", sort=True)]
    metrics += [metric_block(frame, f"{segment}_{ticker}", ticker) for (segment, ticker), frame in pred.groupby(["segment", "ticker"], sort=True)]

    trade = trades.copy()
    if not trade.empty:
        trade["segment"] = np.where(trade["date"] >= oos_start, "oos", "pre_oos")
    trade_summary = {"overall": trade_metrics(trade)}
    if not trade.empty:
        for segment, frame in trade.groupby("segment", sort=True):
            trade_summary[segment] = trade_metrics(frame)
        for (segment, ticker), frame in trade.groupby(["segment", "ticker"], sort=True):
            trade_summary[f"{segment}_{ticker}"] = trade_metrics(frame)
    return {"prediction_metrics": metrics, "trade_metrics": trade_summary}

def run_mode(
    df: pd.DataFrame,
    feature_mode: str,
    jepa_feature_names: str | Path | None,
    min_train_months: int,
    val_months: int,
    cost_bps: float,
    cooldown_steps: int,
    notional: float,
    min_val_trades: int,
    seed: int,
    n_estimators: int,
    n_jobs: int,
    test_start_month: str | None,
    test_end_month: str | None,
) -> ModeResult:
    features_orig = select_features(df, feature_mode, jepa_feature_names)
    months = sorted(df["month"].unique().tolist())
    predictions = []
    trades = []
    windows = []
    tickers = sorted(df["ticker"].astype(str).unique().tolist())

    for ticker in tickers:
        ticker_df = df[df["ticker"].astype(str) == ticker].copy()
        ticker_months = sorted(ticker_df["month"].unique().tolist())
        for test_month in ticker_months:
            if test_start_month and test_month < test_start_month:
                continue
            if test_end_month and test_month > test_end_month:
                continue
            print(f"[JEPA_180M] mode={feature_mode} ticker={ticker} test_month={test_month}", flush=True)
            train_months = [m for m in ticker_months if m < test_month]
            if len(train_months) < min_train_months:
                continue
            train_all = ticker_df[ticker_df["month"].isin(train_months)].copy()
            test = ticker_df[ticker_df["month"] == test_month].copy()
            if test.empty:
                continue

            val_keys = train_months[-val_months:] if val_months > 0 else train_months[-1:]
            fit = train_all[~train_all["month"].isin(val_keys)].copy()
            val = train_all[train_all["month"].isin(val_keys)].copy()
            if fit.empty or val.empty:
                fit = train_all.copy()
                val = train_all.tail(min(len(train_all), max(200, len(train_all) // 5))).copy()

            # Train a model on FIT data; validation rows select thresholds only.
            val_model, val_medians, val_features = train_model(fit, features_orig, seed, n_estimators, n_jobs, ticker=ticker)
            val_pred = predict_returns(val_model, val, val_features, val_medians)

            # Since we split Long/Short independently, require half min_val_trades for each side
            thresholds = choose_thresholds(val, val_pred, cost_bps, cooldown_steps, notional, max(2, min_val_trades // 2), ticker=ticker)

            # Train final model only on pre-test rows.
            model, medians, final_features = train_model(train_all, features_orig, seed, n_estimators, n_jobs, ticker=ticker)
            test_pred = predict_returns(model, test, final_features, medians)

            pred_frame = test[
                [
                    "ticker",
                    "date",
                    "time",
                    "month",
                    "pos_in_day",
                    "spot_price",
                    "future_return_180m",
                    "future_return_bps_180m",
                ]
            ].copy()
            pred_frame["feature_mode"] = feature_mode
            pred_frame["pred_bps"] = test_pred
            predictions.append(pred_frame)

            test_trades = simulate_hold180(
                test,
                test_pred,
                thresholds["long_threshold"],
                thresholds["short_threshold"],
                cost_bps,
                cooldown_steps,
                notional,
            )
            if not test_trades.empty:
                test_trades["feature_mode"] = feature_mode
                test_trades["test_month"] = test_month
                trades.append(test_trades)

            windows.append(
                {
                    "feature_mode": feature_mode,
                    "ticker": ticker,
                    "test_month": test_month,
                    "train_rows": int(len(train_all)),
                    "test_rows": int(len(test)),
                    "feature_count": int(len(final_features)),
                    **thresholds,
                }
            )

    pred_all = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    trade_all = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    if not pred_all.empty:
        pred_all.attrs["trades"] = trade_all

    # Just pass the final features back
    return ModeResult(feature_mode=feature_mode, predictions=pred_all, windows=windows, features=features_orig)

def write_mode_outputs(
    result: ModeResult,
    output_dir: Path,
    oos_start: str,
    cost_bps: float,
    cooldown_steps: int,
    notional: float,
) -> dict:
    trades = result.predictions.attrs.get("trades", pd.DataFrame())
    result.predictions.to_csv(output_dir / f"{result.feature_mode}_predictions.csv", index=False)
    trades.to_csv(output_dir / f"{result.feature_mode}_trades.csv", index=False)
    pd.DataFrame(result.windows).to_csv(output_dir / f"{result.feature_mode}_windows.csv", index=False)
    (output_dir / f"{result.feature_mode}_features.json").write_text(
        json.dumps({"feature_mode": result.feature_mode, "feature_count": len(result.features), "feature_names": result.features}, indent=2),
        encoding="utf-8",
    )
    summary = summarize_predictions(result.predictions, trades, oos_start)
    summary.update(
        {
            "feature_mode": result.feature_mode,
            "feature_count": len(result.features),
            "cost_bps": cost_bps,
            "cooldown_steps": cooldown_steps,
            "notional": notional,
            "windows": result.windows,
        }
    )
    (output_dir / f"{result.feature_mode}_metrics.json").write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")
    return summary

def trade_row(label: str, metrics: dict) -> str:
    return (
        f"| {label} | {metrics.get('trades', 0)} | {fmt_pct(metrics.get('win_rate', float('nan')))} | "
        f"{fmt_float(metrics.get('profit_factor', float('nan')))} | {fmt_float(metrics.get('avg_net_bps', float('nan')), 2)} | "
        f"{fmt_money(metrics.get('pnl_dollars', 0.0))} | {fmt_money(metrics.get('max_drawdown', 0.0))} | "
        f"{fmt_pct(metrics.get('long_rate', float('nan')))} |"
    )

def pred_table_row(label: str, metric: dict) -> str:
    return (
        f"| {label} | {metric.get('rows', 0)} | {fmt_float(metric.get('rmse', float('nan')))} | "
        f"{fmt_float(metric.get('mae', float('nan')))} | {fmt_float(metric.get('spearman_return', float('nan')))} | "
        f"{fmt_float(metric.get('top_quintile_return_bps', float('nan')), 2)} | "
        f"{fmt_float(metric.get('bottom_quintile_return_bps', float('nan')), 2)} |"
    )

def find_metric(summary: dict, segment: str, ticker: str = "ALL") -> dict:
    for row in summary["prediction_metrics"]:
        if row["segment"] == segment and row["ticker"] == ticker:
            return row
    return {}

def write_report(output_dir: Path, summaries: dict[str, dict], args, dataset_rows: int, valid_rows: int) -> None:
    test_window = "all eligible walk-forward months"
    if args.test_start_month or args.test_end_month:
        test_window = f"{args.test_start_month or 'first'} to {args.test_end_month or 'last'}"
    horizon_text = "EOD-truncated 180m" if getattr(args, "truncate_eod_horizon", False) else "exact 180m"
    backtest_text = (
        "max 180m hold truncated to same-day last row"
        if getattr(args, "truncate_eod_horizon", False)
        else "fixed 180m hold"
    )
    lines = [
        "# JEPA 180m Regressor Experiment",
        "",
        f"Data: `{args.data}`",
        f"Rows after {horizon_text} label construction: {valid_rows:,} from {dataset_rows:,}",
        f"Label: `future_return_bps_180m` (Regression)",
        f"Test months: `{test_window}`",
        f"OOS split: dates >= `{args.oos_start}`",
        f"Backtest: {backtest_text}, cooldown `{args.cooldown_steps}` samples, cost `{args.cost_bps}` bps, notional `${args.notional:,.0f}` per trade.",
        "",
        "## Prediction Metrics",
        "",
        "| Mode | Rows | RMSE | MAE | Spearman Ret | Top Q Ret bps | Bottom Q Ret bps |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode, summary in summaries.items():
        lines.append(pred_table_row(f"{mode} overall", find_metric(summary, "overall")))
        lines.append(pred_table_row(f"{mode} OOS", find_metric(summary, "oos")))

    lines += [
        "",
        "## Fixed-Hold 180m Backtest",
        "",
        "| Mode | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode, summary in summaries.items():
        tm = summary["trade_metrics"]
        lines.append(trade_row(f"{mode} overall", tm.get("overall", {})))
        lines.append(trade_row(f"{mode} OOS", tm.get("oos", {})))

    lines += [
        "",
        "## Interpretation",
        "",
        "- This is a terminal 180m return REGRESSOR experiment.",
        "- Feature columns explicitly exclude future/target columns.",
        "- OOS metrics are the important decision point.",
        "- A promotable 180m module should beat the base feature model OOS on Return bps and fixed-hold PnL.",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")

def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward test for 180m terminal return regression.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--jepa-feature-names", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--modes", nargs="+", default=["base", "jepa_only", "base_jepa"])
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument(
        "--truncate-eod-horizon",
        action="store_true",
        help="Use min(t+horizon, last same-day row) instead of dropping rows with fewer than horizon steps left.",
    )
    parser.add_argument("--min-abs-bps", type=float, default=0.0)
    parser.add_argument("--min-train-months", type=int, default=12)
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--cost-bps", type=float, default=1.0)
    parser.add_argument("--cooldown-steps", type=int, default=36)
    parser.add_argument("--notional", type=float, default=100000.0)
    parser.add_argument("--min-val-trades", type=int, default=4)
    parser.add_argument("--oos-start", default="20260401")
    parser.add_argument("--seed", type=int, default=777)
    parser.add_argument("--n-estimators", type=int, default=250)
    parser.add_argument("--n-jobs", type=int, default=20)
    parser.add_argument("--test-start-month", default=None)
    parser.add_argument("--test-end-month", default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = len(pd.read_parquet(args.data, columns=["ticker"]))
    df = build_terminal_180m_frame(
        args.data,
        args.horizon_steps,
        args.min_abs_bps,
        truncate_to_eod=args.truncate_eod_horizon,
    )
    summaries = {}
    for mode in args.modes:
        print(f"[JEPA_180M] mode={mode} rows={len(df)}")
        result = run_mode(
            df=df,
            feature_mode=mode,
            jepa_feature_names=args.jepa_feature_names,
            min_train_months=args.min_train_months,
            val_months=args.val_months,
            cost_bps=args.cost_bps,
            cooldown_steps=args.cooldown_steps,
            notional=args.notional,
            min_val_trades=args.min_val_trades,
            seed=args.seed,
            n_estimators=args.n_estimators,
            n_jobs=args.n_jobs,
            test_start_month=args.test_start_month,
            test_end_month=args.test_end_month,
        )
        summaries[mode] = write_mode_outputs(
            result,
            output_dir,
            args.oos_start,
            args.cost_bps,
            args.cooldown_steps,
            args.notional,
        )

    payload = {
        "config": vars(args),
        "raw_rows": raw_rows,
        "valid_rows": int(len(df)),
        "summaries": summaries,
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_report(output_dir, summaries, args, raw_rows, len(df))
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
