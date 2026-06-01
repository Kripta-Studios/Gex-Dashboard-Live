from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.backtest_jepa_180m import apply_cooldown, time_to_minutes
from neural.jepa.evaluate_180m_direction import build_terminal_180m_frame, fmt_float, fmt_money, fmt_pct, trade_metrics
from neural.jepa.jepa_180m_signal import Jepa180mSignalModel, normalize_ticker


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
}

BASE_STATE_FEATURES = [
    "ticker_code",
    "direction",
    "is_long",
    "is_short",
    "hold_norm",
    "hold_minutes",
    "minutes_remaining",
    "entry_prob_up",
    "entry_confidence",
    "current_prob_up",
    "current_confidence",
    "prob_delta",
    "prob_delta_signed",
    "confidence_delta",
    "current_net_bps",
    "current_pnl_dollars",
    "peak_net_bps",
    "mae_net_bps",
    "mfe_net_bps",
    "drawdown_from_peak_bps",
    "runup_from_trough_bps",
    "spot_return_bps",
    "abs_spot_return_bps",
]


@dataclass(frozen=True)
class FitResult:
    model: object
    features: list[str]
    medians: pd.Series
    scope: str
    target: str
    ticker: str | None = None


def normalize_date(value) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else str(value)


def time_plus_minutes(value: object, minutes: int) -> str:
    try:
        hour, minute = [int(part) for part in str(value)[:5].split(":")]
    except Exception:
        return str(value)[:5]
    total = hour * 60 + int(minute) + int(minutes)
    return f"{total // 60:02d}:{total % 60:02d}"


def month_add(month: str, delta: int) -> str:
    year = int(str(month)[:4])
    mon = int(str(month)[4:6])
    idx = year * 12 + mon - 1 + int(delta)
    return f"{idx // 12:04d}{idx % 12 + 1:02d}"


def prepare_raw_frame(data_path: Path) -> pd.DataFrame:
    raw = pd.read_parquet(data_path)
    raw["ticker"] = raw["ticker"].map(normalize_ticker)
    raw["date"] = raw["date"].map(normalize_date)
    raw = raw.sort_values(["ticker", "date", "time"]).reset_index(drop=True)
    raw["pos_in_day"] = raw.groupby(["ticker", "date"], sort=False).cumcount()
    return raw


def selected_signals(
    data_path: Path,
    model_dir: Path,
    mode: str,
    start_date: str,
    end_date: str | None,
    tickers: list[str],
    horizon_steps: int,
    cooldown_steps: int,
    min_entry_minute: int | None,
    max_entry_minute: int | None,
) -> pd.DataFrame:
    frame = build_terminal_180m_frame(data_path, horizon_steps, min_abs_bps=0.0)
    frame["ticker"] = frame["ticker"].map(normalize_ticker)
    frame["date"] = frame["date"].map(normalize_date)
    frame = frame[frame["date"] >= normalize_date(start_date)].copy()
    if end_date:
        frame = frame[frame["date"] <= normalize_date(end_date)].copy()
    if tickers:
        allowed = {normalize_ticker(t) for t in tickers}
        frame = frame[frame["ticker"].isin(allowed)].copy()
    if min_entry_minute is not None or max_entry_minute is not None:
        minutes = frame["time"].map(time_to_minutes)
        if min_entry_minute is not None:
            frame = frame[minutes >= int(min_entry_minute)].copy()
            minutes = frame["time"].map(time_to_minutes)
        if max_entry_minute is not None:
            frame = frame[minutes <= int(max_entry_minute)].copy()

    model = Jepa180mSignalModel(model_dir, mode, tickers=tickers)
    scored = model.predict_frame(frame)
    signals = scored[scored["jepa180_direction"].astype(int) != 0].copy()
    signals = apply_cooldown(signals, cooldown_steps)
    signals = signals.sort_values(["ticker", "date", "pos_in_day"]).reset_index(drop=True)
    signals["trade_id"] = np.arange(len(signals), dtype=np.int64)
    signals["month"] = signals["date"].astype(str).str[:6]
    return signals


def numeric_feature_names(raw: pd.DataFrame, model: Jepa180mSignalModel) -> list[str]:
    names = []
    for name in model.required_features():
        if name in LEAKAGE_COLUMNS or name not in raw.columns:
            continue
        if pd.api.types.is_numeric_dtype(raw[name]):
            names.append(name)
    return names


def add_prefixed_features(
    row: dict,
    prefix: str,
    source,
    feature_names: list[str],
) -> None:
    for name in feature_names:
        value = getattr(source, name, np.nan)
        try:
            row[f"{prefix}{name}"] = float(value)
        except Exception:
            row[f"{prefix}{name}"] = np.nan


def add_delta_features(row: dict, entry, current, feature_names: list[str]) -> None:
    for name in feature_names:
        try:
            entry_value = float(getattr(entry, name, np.nan))
            current_value = float(getattr(current, name, np.nan))
            row[f"delta_{name}"] = current_value - entry_value
        except Exception:
            row[f"delta_{name}"] = np.nan


def build_state_rows(
    signals: pd.DataFrame,
    raw: pd.DataFrame,
    model: Jepa180mSignalModel,
    horizon_steps: int,
    cost_bps: float,
    notional: float,
    include_entry_features: bool,
    include_current_features: bool,
    include_feature_deltas: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    scored_raw = model.predict_frame(raw)
    feature_names = numeric_feature_names(scored_raw, model)
    ticker_codes = {ticker: idx for idx, ticker in enumerate(sorted(scored_raw["ticker"].unique()))}
    raw_by_key = {
        (str(ticker), str(date)): group.sort_values("pos_in_day").reset_index(drop=True)
        for (ticker, date), group in scored_raw.groupby(["ticker", "date"], sort=False)
    }

    state_rows: list[dict] = []
    fixed_trades: list[dict] = []
    for signal in signals.itertuples(index=False):
        key = (str(signal.ticker), str(signal.date))
        day = raw_by_key.get(key)
        if day is None:
            continue
        pos = int(signal.pos_in_day)
        end_pos = pos + int(horizon_steps)
        if pos < 0 or end_pos >= len(day):
            continue

        entry_row = day.iloc[pos]
        entry_spot = float(signal.spot_price)
        direction = int(signal.jepa180_direction)
        side = "LONG" if direction > 0 else "SHORT"
        entry_prob = float(signal.jepa180_prob_up)
        entry_conf = float(signal.jepa180_confidence)
        peak_bps = -1e18
        trough_bps = 1e18
        pnl_values: list[float] = []

        path = day.iloc[pos + 1 : end_pos + 1].copy()
        for step_idx, row in enumerate(path.itertuples(index=False), start=1):
            hold_minutes = int(step_idx * 5)
            current_spot = float(row.spot_price)
            gross_bps = direction * (current_spot / entry_spot - 1.0) * 10000.0
            net_bps = gross_bps - float(cost_bps)
            pnl_dollars = net_bps / 10000.0 * float(notional)
            pnl_values.append(pnl_dollars)
            peak_bps = max(peak_bps, net_bps)
            trough_bps = min(trough_bps, net_bps)

            current_prob = float(getattr(row, "jepa180_prob_up", np.nan))
            current_conf = float(getattr(row, "jepa180_confidence", np.nan))
            state = {
                "trade_id": int(signal.trade_id),
                "ticker": str(signal.ticker),
                "ticker_code": float(ticker_codes.get(str(signal.ticker), -1)),
                "date": str(signal.date),
                "month": str(signal.date)[:6],
                "entry_time": str(signal.time),
                "path_time": str(row.time),
                "side": side,
                "direction": direction,
                "is_long": 1.0 if direction > 0 else 0.0,
                "is_short": 1.0 if direction < 0 else 0.0,
                "entry_spot": entry_spot,
                "current_spot": current_spot,
                "hold_minutes": float(hold_minutes),
                "hold_norm": hold_minutes / float(horizon_steps * 5),
                "minutes_remaining": float(max(0, horizon_steps - step_idx) * 5),
                "entry_prob_up": entry_prob,
                "entry_confidence": entry_conf,
                "current_prob_up": current_prob,
                "current_confidence": current_conf,
                "prob_delta": current_prob - entry_prob,
                "prob_delta_signed": direction * (current_prob - entry_prob),
                "confidence_delta": current_conf - entry_conf,
                "current_net_bps": net_bps,
                "current_pnl_dollars": pnl_dollars,
                "peak_net_bps": peak_bps,
                "mfe_net_bps": peak_bps,
                "mae_net_bps": trough_bps,
                "drawdown_from_peak_bps": max(0.0, peak_bps - net_bps),
                "runup_from_trough_bps": max(0.0, net_bps - trough_bps),
                "spot_return_bps": (current_spot / entry_spot - 1.0) * 10000.0,
                "abs_spot_return_bps": abs((current_spot / entry_spot - 1.0) * 10000.0),
            }
            if include_entry_features:
                add_prefixed_features(state, "entry_", entry_row, feature_names)
            if include_current_features:
                add_prefixed_features(state, "current_", row, feature_names)
            if include_feature_deltas:
                add_delta_features(state, entry_row, row, feature_names)
            state_rows.append(state)

        if pnl_values:
            fixed_pnl = float(pnl_values[-1])
            fixed_trades.append(
                {
                    "trade_id": int(signal.trade_id),
                    "ticker": str(signal.ticker),
                    "date": str(signal.date),
                    "month": str(signal.date)[:6],
                    "time": str(signal.time),
                    "entry_time": str(signal.time),
                    "exit_time": time_plus_minutes(signal.time, horizon_steps * 5),
                    "side": side,
                    "spot_price": entry_spot,
                    "net_bps": fixed_pnl / float(notional) * 10000.0,
                    "pnl_dollars": fixed_pnl,
                    "hold_minutes": int(horizon_steps * 5),
                    "exit_reason": "fixed_180m",
                    "policy": "fixed_180m",
                }
            )

    states = pd.DataFrame(state_rows)
    fixed = pd.DataFrame(fixed_trades)
    if states.empty:
        return states, fixed, feature_names

    def add_future_labels(path: pd.DataFrame) -> pd.DataFrame:
        values = path["current_pnl_dollars"].astype(float).to_numpy()
        future_best = np.maximum.accumulate(values[::-1])[::-1]
        terminal = np.full(len(values), values[-1], dtype=np.float64)
        path = path.copy()
        path["exit_now_value"] = values
        path["continue_value"] = future_best
        path["terminal_value"] = terminal
        path["continue_edge"] = future_best - values
        path["terminal_edge"] = terminal - values
        path["oracle_is_now"] = (path["continue_edge"].astype(float) <= 1e-9).astype(np.int8)
        return path

    parts = []
    for _, path in states.sort_values(["trade_id", "hold_minutes"]).groupby("trade_id", sort=False):
        parts.append(add_future_labels(path))
    states = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return states, fixed, feature_names


def all_model_features(states: pd.DataFrame) -> list[str]:
    blocked = {
        "trade_id",
        "ticker",
        "date",
        "month",
        "entry_time",
        "path_time",
        "side",
        "entry_spot",
        "current_spot",
        "exit_now_value",
        "continue_value",
        "terminal_value",
        "continue_edge",
        "terminal_edge",
        "oracle_is_now",
    }
    features = []
    for col in states.columns:
        if col in blocked:
            continue
        if pd.api.types.is_numeric_dtype(states[col]):
            features.append(col)
    return features


def make_matrix(frame: pd.DataFrame, features: list[str], medians: pd.Series | None = None) -> tuple[pd.DataFrame, pd.Series]:
    x = frame.reindex(columns=features)
    x = x.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if medians is None:
        medians = x.median(axis=0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    x = x.fillna(medians).fillna(0.0)
    return x.astype(np.float32), medians


def fit_one_model(
    train_states: pd.DataFrame,
    features: list[str],
    target: str,
    scope: str,
    ticker: str | None,
    seed: int,
    n_estimators: int,
    n_jobs: int,
) -> FitResult:
    x_train, medians = make_matrix(train_states, features)

    params = dict(
        n_estimators=int(n_estimators),
        learning_rate=0.035,
        num_leaves=31,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_samples=50,
        reg_alpha=0.10,
        reg_lambda=0.75,
        random_state=int(seed),
        n_jobs=int(n_jobs),
        verbose=-1,
    )
    if target == "continue_edge_q75":
        model = lgb.LGBMRegressor(objective="quantile", alpha=0.75, **params)
        y_train = train_states["continue_edge"].astype(float).clip(lower=0.0).to_numpy()
    elif target == "continue_edge_q90":
        model = lgb.LGBMRegressor(objective="quantile", alpha=0.90, **params)
        y_train = train_states["continue_edge"].astype(float).clip(lower=0.0).to_numpy()
    elif target == "continue_edge_l1":
        model = lgb.LGBMRegressor(objective="regression_l1", **params)
        y_train = train_states["continue_edge"].astype(float).clip(lower=0.0).to_numpy()
    else:
        model = lgb.LGBMRegressor(objective="huber", alpha=0.90, **params)
        y_train = train_states["continue_edge"].astype(float).clip(lower=0.0).to_numpy()
    model.fit(x_train, y_train)
    return FitResult(model=model, features=features, medians=medians, scope=scope, target=target, ticker=ticker)


def fit_models(
    train_states: pd.DataFrame,
    features: list[str],
    policy: str,
    seed: int,
    n_estimators: int,
    n_jobs: int,
) -> dict[str, FitResult]:
    if policy.startswith("per_ticker_"):
        target = policy.removeprefix("per_ticker_")
        models = {}
        for ticker, part in train_states.groupby("ticker", sort=True):
            if len(part) < 500:
                continue
            models[str(ticker)] = fit_one_model(part, features, target, "per_ticker", str(ticker), seed, n_estimators, n_jobs)
        return models
    target = policy.removeprefix("pooled_")
    return {"__pooled__": fit_one_model(train_states, features, target, "pooled", None, seed, n_estimators, n_jobs)}


def predict_edge(models: dict[str, FitResult], states: pd.DataFrame) -> np.ndarray:
    out = np.full(len(states), np.nan, dtype=np.float64)
    if "__pooled__" in models:
        fit = models["__pooled__"]
        x, _ = make_matrix(states, fit.features, fit.medians)
        out[:] = fit.model.predict(x)
        return np.maximum(out, 0.0)

    for ticker, fit in models.items():
        mask = states["ticker"].astype(str).to_numpy() == str(ticker)
        if not mask.any():
            continue
        x, _ = make_matrix(states.loc[mask], fit.features, fit.medians)
        out[np.flatnonzero(mask)] = fit.model.predict(x)
    return np.maximum(np.nan_to_num(out, nan=1e9), 0.0)


def simulate_exit(
    states: pd.DataFrame,
    models: dict[str, FitResult],
    margin_dollars: float,
    min_hold_minutes: int,
    policy_name: str,
    notional: float,
) -> pd.DataFrame:
    trades: list[dict] = []
    for trade_id, path in states.groupby("trade_id", sort=False):
        path = path.sort_values("hold_minutes").reset_index(drop=True)
        pred_edge = predict_edge(models, path)
        exit_row = path.iloc[-1]
        exit_reason = "max_time"
        for idx, row in path.iterrows():
            if int(row["hold_minutes"]) < int(min_hold_minutes):
                continue
            if float(pred_edge[idx]) <= float(margin_dollars):
                exit_row = row
                exit_reason = "continuation_exit"
                break
        pnl = float(exit_row["current_pnl_dollars"])
        trades.append(
            {
                "trade_id": int(trade_id),
                "ticker": str(exit_row["ticker"]),
                "date": str(exit_row["date"]),
                "month": str(exit_row["month"]),
                "time": str(exit_row["entry_time"]),
                "entry_time": str(exit_row["entry_time"]),
                "exit_time": str(exit_row["path_time"]),
                "side": str(exit_row["side"]),
                "spot_price": float(exit_row["entry_spot"]),
                "net_bps": pnl / float(notional) * 10000.0,
                "pnl_dollars": pnl,
                "hold_minutes": int(exit_row["hold_minutes"]),
                "exit_reason": exit_reason,
                "policy": policy_name,
                "predicted_continue_edge": float(pred_edge[min(len(pred_edge) - 1, int(exit_row.name))])
                if len(pred_edge)
                else np.nan,
            }
        )
    return pd.DataFrame(trades)


def oracle_exit(states: pd.DataFrame, notional: float) -> pd.DataFrame:
    trades: list[dict] = []
    for trade_id, path in states.groupby("trade_id", sort=False):
        path = path.sort_values("hold_minutes").reset_index(drop=True)
        idx = path["current_pnl_dollars"].astype(float).idxmax()
        row = path.loc[idx]
        pnl = float(row["current_pnl_dollars"])
        trades.append(
            {
                "trade_id": int(trade_id),
                "ticker": str(row["ticker"]),
                "date": str(row["date"]),
                "month": str(row["month"]),
                "time": str(row["entry_time"]),
                "entry_time": str(row["entry_time"]),
                "exit_time": str(row["path_time"]),
                "side": str(row["side"]),
                "spot_price": float(row["entry_spot"]),
                "net_bps": pnl / float(notional) * 10000.0,
                "pnl_dollars": pnl,
                "hold_minutes": int(row["hold_minutes"]),
                "exit_reason": "oracle_best_path",
                "policy": "oracle_exit",
            }
        )
    return pd.DataFrame(trades)


def score_metrics(metrics: dict, min_trades: int, fixed_metrics: dict | None = None) -> float:
    trades = int(metrics.get("trades", 0))
    pnl = float(metrics.get("pnl_dollars", 0.0))
    pf = float(metrics.get("profit_factor", 0.0))
    dd = abs(float(metrics.get("max_drawdown", 0.0)))
    if trades < int(min_trades) or not np.isfinite(pf):
        return -1e18
    score = pf * np.log1p(trades) + pnl / 10000.0 - dd / 5000.0
    if fixed_metrics is not None:
        fixed_pnl = float(fixed_metrics.get("pnl_dollars", 0.0))
        fixed_pf = float(fixed_metrics.get("profit_factor", 0.0))
        fixed_dd = abs(float(fixed_metrics.get("max_drawdown", 0.0)))
        if pnl < fixed_pnl:
            score -= (fixed_pnl - pnl) / 1000.0
        if pf < fixed_pf:
            score -= (fixed_pf - pf) * 10.0
        if dd > fixed_dd:
            score -= (dd - fixed_dd) / 1000.0
    return float(score)


def choose_margin(
    val_states: pd.DataFrame,
    val_fixed: pd.DataFrame,
    models: dict[str, FitResult],
    margins: list[float],
    min_hold_minutes: int,
    min_val_trades: int,
    notional: float,
) -> tuple[float, pd.DataFrame]:
    fixed_metrics = metrics_for(val_fixed)
    rows = []
    best_margin = float(margins[0])
    best_score = -1e18
    for margin in margins:
        trades = simulate_exit(val_states, models, margin, min_hold_minutes, "validation_continuation_exit", notional)
        metrics = metrics_for(trades)
        score = score_metrics(metrics, min_val_trades, fixed_metrics)
        rows.append({"margin_dollars": float(margin), "score": score, **metrics})
        if score > best_score:
            best_score = score
            best_margin = float(margin)
    return best_margin, pd.DataFrame(rows)


def filter_trade_ids(states: pd.DataFrame, ids: set[int]) -> pd.DataFrame:
    return states[states["trade_id"].astype(int).isin(ids)].copy()


def fold_months(states: pd.DataFrame, start_month: str, end_month: str | None) -> list[str]:
    months = sorted(states["month"].astype(str).unique().tolist())
    months = [m for m in months if m >= str(start_month)]
    if end_month:
        months = [m for m in months if m <= str(end_month)]
    return months


def order_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades
    cols = [c for c in ["date", "time", "ticker", "trade_id"] if c in trades.columns]
    return trades.sort_values(cols).reset_index(drop=True) if cols else trades.reset_index(drop=True)


def metrics_for(trades: pd.DataFrame) -> dict:
    return trade_metrics(order_trades(trades))


def evaluate_policy_walkforward(
    states: pd.DataFrame,
    fixed: pd.DataFrame,
    policy: str,
    features: list[str],
    margins: list[float],
    start_month: str,
    end_month: str | None,
    val_months: int,
    min_fit_trades: int,
    min_val_trades: int,
    min_hold_minutes: int,
    seed: int,
    n_estimators: int,
    n_jobs: int,
    notional: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    fold_rows = []
    trade_parts = []
    for test_month in fold_months(states, start_month, end_month):
        train_cutoff = month_add(test_month, -1)
        train_ids = set(fixed[fixed["month"].astype(str) <= train_cutoff]["trade_id"].astype(int))
        test_ids = set(fixed[fixed["month"].astype(str) == test_month]["trade_id"].astype(int))
        if not test_ids:
            continue

        available_months = sorted(fixed[fixed["month"].astype(str) <= train_cutoff]["month"].astype(str).unique())
        if len(available_months) <= int(val_months):
            continue
        val_set = set(available_months[-int(val_months) :])
        fit_ids = set(
            fixed[
                (fixed["month"].astype(str) <= train_cutoff)
                & (~fixed["month"].astype(str).isin(val_set))
            ]["trade_id"].astype(int)
        )
        val_ids = set(
            fixed[
                (fixed["month"].astype(str) <= train_cutoff)
                & (fixed["month"].astype(str).isin(val_set))
            ]["trade_id"].astype(int)
        )
        if len(fit_ids) < int(min_fit_trades) or len(val_ids) < int(min_val_trades):
            continue

        fit_states = filter_trade_ids(states, fit_ids)
        val_states = filter_trade_ids(states, val_ids)
        test_states = filter_trade_ids(states, test_ids)
        val_fixed = fixed[fixed["trade_id"].astype(int).isin(val_ids)].copy()
        test_fixed = fixed[fixed["trade_id"].astype(int).isin(test_ids)].copy()

        models = fit_models(
            fit_states,
            features,
            policy,
            seed + int(test_month),
            n_estimators,
            n_jobs,
        )
        if not models:
            continue
        margin, grid = choose_margin(
            val_states,
            val_fixed,
            models,
            margins,
            min_hold_minutes,
            min_val_trades,
            notional,
        )
        test_trades = simulate_exit(
            test_states,
            models,
            margin,
            min_hold_minutes,
            policy,
            notional,
        )
        test_trades["fold_month"] = test_month
        test_trades["selected_margin_dollars"] = margin
        test_trades["val_months"] = ",".join(sorted(val_set))
        trade_parts.append(test_trades)

        learned_metrics = metrics_for(test_trades)
        fixed_metrics = metrics_for(test_fixed)
        oracle_metrics = metrics_for(oracle_exit(test_states, notional))
        fold_rows.append(
            {
                "policy": policy,
                "fold_month": test_month,
                "fit_trades": len(fit_ids),
                "val_trades": len(val_ids),
                "test_trades": len(test_ids),
                "selected_margin_dollars": margin,
                "val_months": ",".join(sorted(val_set)),
                "val_grid": grid.to_dict(orient="records"),
                **{f"learned_{k}": v for k, v in learned_metrics.items()},
                **{f"fixed_{k}": v for k, v in fixed_metrics.items()},
                **{f"oracle_{k}": v for k, v in oracle_metrics.items()},
            }
        )
    trades = pd.concat(trade_parts, ignore_index=True) if trade_parts else pd.DataFrame()
    return trades, pd.DataFrame(fold_rows)


def metrics_row(label: str, frame: pd.DataFrame) -> str:
    frame = order_trades(frame)
    metrics = metrics_for(frame)
    avg_hold = frame["hold_minutes"].astype(float).mean() if not frame.empty and "hold_minutes" in frame else float("nan")
    return (
        f"| {label} | {metrics.get('trades', 0)} | {fmt_pct(metrics.get('win_rate', float('nan')))} | "
        f"{fmt_float(metrics.get('profit_factor', float('nan')))} | "
        f"{fmt_float(metrics.get('avg_net_bps', float('nan')), 2)} | "
        f"{fmt_money(metrics.get('pnl_dollars', 0.0))} | "
        f"{fmt_money(metrics.get('max_drawdown', 0.0))} | {fmt_float(avg_hold, 1)} |"
    )


def promotion_gate(fixed: pd.DataFrame, learned: pd.DataFrame) -> dict:
    fixed_m = metrics_for(fixed)
    learned_m = metrics_for(learned)
    checks = {
        "pf": float(learned_m.get("profit_factor", 0.0)) > float(fixed_m.get("profit_factor", 0.0)) + 1e-9,
        "pnl": float(learned_m.get("pnl_dollars", 0.0)) > float(fixed_m.get("pnl_dollars", 0.0)) + 1e-9,
        "drawdown": float(learned_m.get("max_drawdown", -1e18)) > float(fixed_m.get("max_drawdown", -1e18)) + 1e-9,
        "trades": int(learned_m.get("trades", 0)) == int(fixed_m.get("trades", 0)),
    }
    return {"passed": bool(all(checks.values())), "checks": checks, "fixed": fixed_m, "learned": learned_m}


def write_summary(
    output_dir: Path,
    args,
    fixed_test: pd.DataFrame,
    oracle_test: pd.DataFrame,
    policy_trades: dict[str, pd.DataFrame],
    fold_tables: dict[str, pd.DataFrame],
    gate_results: dict[str, dict],
    feature_count: int,
) -> None:
    lines = [
        "# GBT+JEPA 180m Continuation-Exit Walk-Forward",
        "",
        f"Data: `{args.data}`",
        f"Model dir: `{args.model_dir}`",
        f"Signal mode: `{args.mode}`",
        f"Test months: `{args.test_start_month}` to `{args.test_end_month or 'latest'}`",
        f"State rows use every 5m point until `{args.horizon_steps * 5}`m.",
        f"Model features: `{feature_count}` numeric entry/current/delta features.",
        "",
        "## OOS Aggregate",
        "",
        "| Policy | Trades | WR | PF | Avg bps | PnL | Max DD | Avg Hold |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        metrics_row("fixed_180m", fixed_test),
    ]
    for policy, trades in policy_trades.items():
        lines.append(metrics_row(policy, trades))
    lines.append(metrics_row("oracle_exit", oracle_test))

    lines += [
        "",
        "## Promotion Gate",
        "",
        "A learned exit is promotable only if it beats fixed 180m on PF, PnL, and max drawdown without changing entries.",
        "",
        "| Policy | Passed | PF | PnL | DD | Same Trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for policy, gate in gate_results.items():
        checks = gate["checks"]
        lines.append(
            f"| {policy} | {str(gate['passed'])} | {str(checks['pf'])} | "
            f"{str(checks['pnl'])} | {str(checks['drawdown'])} | {str(checks['trades'])} |"
        )

    lines += [
        "",
        "## Monthly Folds",
        "",
        "| Policy | Month | Trades | Margin $ | Fixed PF | Learned PF | Fixed PnL | Learned PnL | Fixed DD | Learned DD |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for policy, table in fold_tables.items():
        if table.empty:
            continue
        for _, row in table.iterrows():
            lines.append(
                f"| {policy} | {row['fold_month']} | {int(row['test_trades'])} | "
                f"{float(row['selected_margin_dollars']):.0f} | "
                f"{fmt_float(row.get('fixed_profit_factor', float('nan')))} | "
                f"{fmt_float(row.get('learned_profit_factor', float('nan')))} | "
                f"{fmt_money(row.get('fixed_pnl_dollars', 0.0))} | "
                f"{fmt_money(row.get('learned_pnl_dollars', 0.0))} | "
                f"{fmt_money(row.get('fixed_max_drawdown', 0.0))} | "
                f"{fmt_money(row.get('learned_max_drawdown', 0.0))} |"
            )

    lines += [
        "",
        "## Interpretation",
        "",
        "- `oracle_exit` is not deployable. It chooses the best point after seeing the future path.",
        "- The learned policies only see information available at each 5m state: entry features, current features, JEPA probability changes, PnL path statistics, and time remaining.",
        "- Future best/terminal values are labels only and are not included as model features.",
        "- If every learned policy fails the promotion gate, fixed 180m remains the correct GBT+JEPA exit contract.",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward continuation-exit test for GBT+JEPA 180m trades.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--mode", default="base_jepa")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--train-start-date", default="20220801")
    parser.add_argument("--test-start-month", default="202604")
    parser.add_argument("--test-end-month", default="")
    parser.add_argument("--tickers", nargs="*", default=["SPX", "QQQ", "SPY"])
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--cooldown-minutes", type=int, default=180)
    parser.add_argument("--cost-bps", type=float, default=1.0)
    parser.add_argument("--notional", type=float, default=100000.0)
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-fit-trades", type=int, default=100)
    parser.add_argument("--min-val-trades", type=int, default=25)
    parser.add_argument("--min-hold-minutes", type=int, default=15)
    parser.add_argument("--n-estimators", type=int, default=220)
    parser.add_argument("--n-jobs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=4477)
    parser.add_argument("--min-entry-minute", type=int, default=None)
    parser.add_argument("--max-entry-minute", type=int, default=None)
    parser.add_argument("--policies", nargs="+", default=["pooled_continue_edge_l1", "pooled_continue_edge_q75", "per_ticker_continue_edge_l1"])
    parser.add_argument(
        "--margins",
        nargs="+",
        type=float,
        default=[-250, -100, 0, 50, 100, 150, 200, 300, 500, 750, 1000, 1500],
    )
    parser.add_argument("--no-entry-features", action="store_true")
    parser.add_argument("--no-current-features", action="store_true")
    parser.add_argument("--no-feature-deltas", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = Path(args.data)
    model_dir = Path(args.model_dir)
    cooldown_steps = max(0, int(round(float(args.cooldown_minutes) / 5.0)))

    raw = prepare_raw_frame(data_path)
    all_signals = selected_signals(
        data_path,
        model_dir,
        args.mode,
        args.train_start_date,
        None,
        args.tickers,
        int(args.horizon_steps),
        cooldown_steps,
        args.min_entry_minute,
        args.max_entry_minute,
    )
    model = Jepa180mSignalModel(model_dir, args.mode, tickers=args.tickers)
    states, fixed, base_features = build_state_rows(
        all_signals,
        raw,
        model,
        int(args.horizon_steps),
        float(args.cost_bps),
        float(args.notional),
        include_entry_features=not args.no_entry_features,
        include_current_features=not args.no_current_features,
        include_feature_deltas=not args.no_feature_deltas,
    )
    if states.empty or fixed.empty:
        raise RuntimeError("No state rows/trades were built.")

    features = all_model_features(states)
    test_end_month = args.test_end_month or None
    test_months = fold_months(states, args.test_start_month, test_end_month)
    test_ids = set(fixed[fixed["month"].astype(str).isin(test_months)]["trade_id"].astype(int))
    fixed_test = order_trades(fixed[fixed["trade_id"].astype(int).isin(test_ids)].copy())
    test_states = filter_trade_ids(states, test_ids)
    oracle_test = order_trades(oracle_exit(test_states, float(args.notional)))

    states.to_parquet(output_dir / "trade_state_rows.parquet", index=False)
    fixed.to_csv(output_dir / "fixed_180m_all_trades.csv", index=False)
    fixed_test.to_csv(output_dir / "fixed_180m_trades.csv", index=False)
    oracle_test.to_csv(output_dir / "oracle_exit_trades.csv", index=False)

    policy_trades: dict[str, pd.DataFrame] = {}
    fold_tables: dict[str, pd.DataFrame] = {}
    gate_results: dict[str, dict] = {}
    for policy in args.policies:
        trades, folds = evaluate_policy_walkforward(
            states,
            fixed,
            policy,
            features,
            [float(x) for x in args.margins],
            str(args.test_start_month),
            test_end_month,
            int(args.val_months),
            int(args.min_fit_trades),
            int(args.min_val_trades),
            int(args.min_hold_minutes),
            int(args.seed),
            int(args.n_estimators),
            int(args.n_jobs),
            float(args.notional),
        )
        trades = order_trades(trades)
        policy_trades[policy] = trades
        fold_tables[policy] = folds
        gate_results[policy] = promotion_gate(fixed_test, trades)
        trades.to_csv(output_dir / f"{policy}_trades.csv", index=False)
        folds.to_json(output_dir / f"{policy}_folds.json", orient="records", indent=2)
        folds.drop(columns=["val_grid"], errors="ignore").to_csv(output_dir / f"{policy}_folds.csv", index=False)

    metadata = {
        "args": vars(args),
        "signals": int(len(all_signals)),
        "state_rows": int(len(states)),
        "fixed_trades": int(len(fixed)),
        "test_trades": int(len(fixed_test)),
        "test_months": test_months,
        "base_feature_count": int(len(base_features)),
        "model_feature_count": int(len(features)),
        "metrics": {
            "fixed_180m": metrics_for(fixed_test),
            "oracle_exit": metrics_for(oracle_test),
            **{policy: metrics_for(trades) for policy, trades in policy_trades.items()},
        },
        "promotion_gate": gate_results,
    }
    (output_dir / "metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(output_dir, args, fixed_test, oracle_test, policy_trades, fold_tables, gate_results, len(features))
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
