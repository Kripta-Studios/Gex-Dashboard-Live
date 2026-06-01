from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, log_loss, roc_auc_score

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


@dataclass
class ModeResult:
    feature_mode: str
    predictions: pd.DataFrame
    windows: list[dict]
    features: list[str]


def normalize_date(value) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else str(value)


def month_key(value) -> str:
    return normalize_date(value)[:6]


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


def build_terminal_180m_frame(data_path: str | Path, horizon_steps: int, min_abs_bps: float) -> pd.DataFrame:
    df = pd.read_parquet(data_path)
    required = {"ticker", "date", "time", "spot_price"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Missing required columns: {sorted(missing)}")

    work = df.copy()
    work["date"] = work["date"].map(normalize_date)
    work = work.sort_values(infer_sort_columns(work)).reset_index(drop=True)
    work["_orig_pos"] = np.arange(len(work), dtype=np.int64)
    work["pos_in_day"] = work.groupby(["ticker", "date"], sort=False).cumcount()

    future_spot = np.full(len(work), np.nan, dtype=np.float64)
    for _, idx in work.groupby(["ticker", "date"], sort=False).groups.items():
        positions = np.asarray(list(idx), dtype=np.int64)
        if len(positions) <= horizon_steps:
            continue
        spot = work.loc[positions, "spot_price"].to_numpy(dtype=np.float64)
        future = np.full(len(positions), np.nan, dtype=np.float64)
        future[:-horizon_steps] = spot[horizon_steps:]
        future_spot[positions] = future

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
    work["month"] = work["date"].str[:6]
    work["oos_apr_may_2026"] = work["date"] >= "20260401"
    work = work.loc[valid].copy()
    if min_abs_bps > 0:
        work = work[work["future_abs_bps_180m"] >= float(min_abs_bps)].copy()
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


def train_model(
    train: pd.DataFrame,
    features: list[str],
    seed: int,
    n_estimators: int,
    n_jobs: int,
) -> tuple[lgb.LGBMClassifier, pd.Series]:
    x_train, medians = make_matrix(train, features)
    y_train = train["future_up_180m"].astype(int).to_numpy()
    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=int(n_estimators),
        learning_rate=0.035,
        num_leaves=31,
        max_depth=-1,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_samples=40,
        reg_alpha=0.05,
        reg_lambda=0.50,
        class_weight="balanced",
        random_state=seed,
        n_jobs=int(n_jobs),
        verbose=-1,
    )
    model.fit(x_train, y_train)
    return model, medians


def predict_proba(model: lgb.LGBMClassifier, frame: pd.DataFrame, features: list[str], medians: pd.Series) -> np.ndarray:
    x, _ = make_matrix(frame, features, medians)
    proba = model.predict_proba(x)
    if proba.shape[1] == 1:
        return np.full(len(frame), float(model.classes_[0]), dtype=np.float64)
    pos_idx = list(model.classes_).index(1)
    return proba[:, pos_idx].astype(np.float64)


def simulate_hold180(
    frame: pd.DataFrame,
    prob: np.ndarray,
    long_threshold: float,
    short_threshold: float,
    cost_bps: float,
    cooldown_steps: int,
    notional: float,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    work = frame[["ticker", "date", "time", "pos_in_day", "spot_price", "future_return_180m", "future_return_bps_180m"]].copy()
    work["prob_up"] = prob
    work["side"] = np.where(work["prob_up"] >= long_threshold, 1, np.where(work["prob_up"] <= short_threshold, -1, 0))
    work = work[work["side"] != 0].sort_values(["ticker", "date", "pos_in_day"]).reset_index(drop=True)
    trades = []
    next_allowed: dict[tuple[str, str], int] = {}
    for row in work.itertuples(index=False):
        key = (str(row.ticker), str(row.date))
        pos = int(row.pos_in_day)
        if pos < next_allowed.get(key, -1):
            continue
        gross_bps = float(row.side) * float(row.future_return_bps_180m)
        net_bps = gross_bps - float(cost_bps)
        trades.append(
            {
                "ticker": str(row.ticker),
                "date": str(row.date),
                "time": str(row.time),
                "side": "LONG" if row.side > 0 else "SHORT",
                "prob_up": float(row.prob_up),
                "spot_price": float(row.spot_price),
                "future_return_bps": float(row.future_return_bps_180m),
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


def choose_thresholds(
    val_frame: pd.DataFrame,
    val_prob: np.ndarray,
    cost_bps: float,
    cooldown_steps: int,
    notional: float,
    min_val_trades: int,
) -> dict:
    candidates = [0.52, 0.55, 0.57, 0.60, 0.62, 0.65, 0.70]
    best = None
    for t in candidates:
        trades = simulate_hold180(val_frame, val_prob, t, 1.0 - t, cost_bps, cooldown_steps, notional)
        metrics = trade_metrics(trades)
        if metrics["trades"] < min_val_trades:
            score = -1e18 + metrics["trades"]
        else:
            score = metrics["pnl_dollars"] - abs(metrics["max_drawdown"]) * 0.25
        item = {
            "long_threshold": float(t),
            "short_threshold": float(1.0 - t),
            "val_score": float(score),
            **{f"val_{k}": v for k, v in metrics.items()},
        }
        if best is None or item["val_score"] > best["val_score"]:
            best = item
    return best or {"long_threshold": 0.55, "short_threshold": 0.45, "val_score": float("nan")}


def metric_block(frame: pd.DataFrame, segment: str, ticker: str = "ALL") -> dict:
    if frame.empty:
        return {
            "segment": segment,
            "ticker": ticker,
            "rows": 0,
            "auc": float("nan"),
            "accuracy": float("nan"),
            "balanced_accuracy": float("nan"),
            "brier": float("nan"),
            "logloss": float("nan"),
            "spearman_return": float("nan"),
            "future_up_rate": float("nan"),
            "pred_up_rate": float("nan"),
            "mean_future_return_bps": float("nan"),
            "top_quintile_return_bps": float("nan"),
            "bottom_quintile_return_bps": float("nan"),
        }
    y = frame["future_up_180m"].astype(int).to_numpy()
    p = np.clip(frame["prob_up"].astype(float).to_numpy(), 1e-6, 1.0 - 1e-6)
    pred = p >= 0.5
    if len(np.unique(y)) < 2:
        auc = float("nan")
        ll = float("nan")
    else:
        auc = float(roc_auc_score(y, p))
        ll = float(log_loss(y, p, labels=[0, 1]))
    corr = spearmanr(p, frame["future_return_bps_180m"].astype(float).to_numpy(), nan_policy="omit")
    q80 = frame["prob_up"].quantile(0.80)
    q20 = frame["prob_up"].quantile(0.20)
    return {
        "segment": segment,
        "ticker": ticker,
        "rows": int(len(frame)),
        "auc": auc,
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "brier": float(brier_score_loss(y, p)),
        "logloss": ll,
        "spearman_return": safe_float(corr.statistic),
        "future_up_rate": float(y.mean()),
        "pred_up_rate": float(pred.mean()),
        "mean_future_return_bps": float(frame["future_return_bps_180m"].mean()),
        "top_quintile_return_bps": float(frame.loc[frame["prob_up"] >= q80, "future_return_bps_180m"].mean()),
        "bottom_quintile_return_bps": float(frame.loc[frame["prob_up"] <= q20, "future_return_bps_180m"].mean()),
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
    features = select_features(df, feature_mode, jepa_feature_names)
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
            if test.empty or train_all["future_up_180m"].nunique() < 2:
                continue
            val_keys = train_months[-val_months:] if val_months > 0 else train_months[-1:]
            fit = train_all[~train_all["month"].isin(val_keys)].copy()
            val = train_all[train_all["month"].isin(val_keys)].copy()
            if fit.empty or fit["future_up_180m"].nunique() < 2 or val.empty:
                fit = train_all.copy()
                val = train_all.tail(min(len(train_all), max(200, len(train_all) // 5))).copy()

            val_model, val_medians = train_model(fit, features, seed, n_estimators, n_jobs)
            val_prob = predict_proba(val_model, val, features, val_medians)
            thresholds = choose_thresholds(val, val_prob, cost_bps, cooldown_steps, notional, min_val_trades)

            model, medians = train_model(train_all, features, seed, n_estimators, n_jobs)
            test_prob = predict_proba(model, test, features, medians)
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
                    "future_up_180m",
                ]
            ].copy()
            pred_frame["feature_mode"] = feature_mode
            pred_frame["prob_up"] = test_prob
            pred_frame["pred_up"] = (test_prob >= 0.5).astype(np.int8)
            predictions.append(pred_frame)
            test_trades = simulate_hold180(
                test,
                test_prob,
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
                    "feature_count": int(len(features)),
                    **thresholds,
                }
            )

    pred_all = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    trade_all = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    if not pred_all.empty:
        pred_all.attrs["trades"] = trade_all
    return ModeResult(feature_mode=feature_mode, predictions=pred_all, windows=windows, features=features)


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
        f"| {label} | {metric.get('rows', 0)} | {fmt_pct(metric.get('future_up_rate', float('nan')))} | "
        f"{fmt_pct(metric.get('pred_up_rate', float('nan')))} | {fmt_float(metric.get('auc', float('nan')))} | "
        f"{fmt_pct(metric.get('accuracy', float('nan')))} | {fmt_pct(metric.get('balanced_accuracy', float('nan')))} | "
        f"{fmt_float(metric.get('spearman_return', float('nan')))} | {fmt_float(metric.get('top_quintile_return_bps', float('nan')), 2)} | "
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
    lines = [
        "# JEPA 180m Direction Experiment",
        "",
        f"Data: `{args.data}`",
        f"Rows after exact 180m label construction: {valid_rows:,} from {dataset_rows:,}",
        f"Label: `spot_price(t+{args.horizon_steps * 5}m) > spot_price(t)`",
        f"Test months: `{test_window}`",
        f"OOS split: dates >= `{args.oos_start}`",
        f"Backtest: fixed 180m hold, cooldown `{args.cooldown_steps}` samples, cost `{args.cost_bps}` bps, notional `${args.notional:,.0f}` per trade.",
        "",
        "## Prediction Metrics",
        "",
        "| Mode | Rows | Future Up | Pred Up | AUC | Acc | Bal Acc | Spearman Ret | Top Q Ret bps | Bottom Q Ret bps |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
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
        "- This is a terminal 180m direction experiment, not the original target/stop 0DTE label.",
        "- The future return is used only as the label and backtest outcome; feature columns explicitly exclude future/target columns.",
        "- OOS metrics are the important decision point because previous XInputJEPA evidence was unstable in Apr/May 2026.",
        "- A promotable 180m module should beat the base feature model OOS on AUC and fixed-hold PnL, with enough trades after the 180m cooldown.",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward test for exact 180m terminal direction.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--jepa-feature-names", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--modes", nargs="+", default=["base", "jepa_only", "base_jepa"])
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--min-abs-bps", type=float, default=0.0)
    parser.add_argument("--min-train-months", type=int, default=12)
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--cost-bps", type=float, default=1.0)
    parser.add_argument("--cooldown-steps", type=int, default=36)
    parser.add_argument("--notional", type=float, default=100000.0)
    parser.add_argument("--min-val-trades", type=int, default=4)
    parser.add_argument("--oos-start", default="20260401")
    parser.add_argument("--seed", type=int, default=777)
    parser.add_argument("--n-estimators", type=int, default=160)
    parser.add_argument("--n-jobs", type=int, default=1)
    parser.add_argument("--test-start-month", default=None)
    parser.add_argument("--test-end-month", default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = len(pd.read_parquet(args.data, columns=["ticker"]))
    df = build_terminal_180m_frame(args.data, args.horizon_steps, args.min_abs_bps)
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
