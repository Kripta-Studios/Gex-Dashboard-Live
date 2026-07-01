# -*- coding: utf-8 -*-
"""
Causal high-precision signal probe.

This script trains one-vs-rest LightGBM heads for LONG and SHORT, then selects
deployment thresholds on the immediately preceding validation months before
testing the next month. It is a research tool: outputs trades and fold configs
so any apparent WR/PF improvement can be audited month by month.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
NEURAL_DIR = PROJECT_ROOT / "neural"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(NEURAL_DIR))

from hybrid_model import FEATURE_COLUMNS  # noqa: E402


REWARD_R = {
    "SPX": 0.010 / 0.0025,
    "QQQ": 0.006 / 0.0025,
    "SPY": 0.006 / 0.0035,
}


@dataclass(frozen=True)
class GateConfig:
    threshold: float
    margin: float
    max_level_dist: float
    start_minute: int
    end_minute: int
    max_trades_per_day: int
    side_mode: str


def parse_minute(value) -> int:
    text = str(value)
    if " " in text:
        text = text.split(" ")[-1]
    hh, mm = text.split(":")[:2]
    return int(hh) * 60 + int(mm)


def month_add(yyyymm: int, delta: int) -> int:
    year = yyyymm // 100
    month = yyyymm % 100
    month += delta
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year * 100 + month


def month_range(start: int, end: int) -> list[int]:
    out = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur = month_add(cur, 1)
    return out


def load_dataset(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["date"] = df["date"].astype(str)
    df["month"] = df["date"].str[:6].astype(int)
    df["minute"] = df["time"].map(parse_minute)
    return df


def feature_frame(df: pd.DataFrame, medians: pd.Series | None = None) -> tuple[pd.DataFrame, pd.Series]:
    cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    X = df[cols].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if medians is None:
        medians = X.median(axis=0).fillna(0.0)
    X = X.fillna(medians).astype(np.float32)
    return X, medians


def fit_heads(train_df: pd.DataFrame, seed: int, n_estimators: int) -> tuple[lgb.LGBMClassifier, lgb.LGBMClassifier, pd.Series]:
    X_train, medians = feature_frame(train_df)
    y_long = (train_df["target"].astype(int).values == 1).astype(np.int8)
    y_short = (train_df["target"].astype(int).values == -1).astype(np.int8)

    params = dict(
        n_estimators=n_estimators,
        max_depth=5,
        learning_rate=0.025,
        subsample=0.65,
        colsample_bytree=0.65,
        min_child_samples=80,
        reg_alpha=2.0,
        reg_lambda=8.0,
        objective="binary",
        class_weight="balanced",
        random_state=seed,
        n_jobs=-1,
        verbosity=-1,
    )
    long_head = lgb.LGBMClassifier(**params)
    short_head = lgb.LGBMClassifier(**params)
    long_head.fit(X_train, y_long)
    short_head.fit(X_train, y_short)
    return long_head, short_head, medians


def score_heads(
    df: pd.DataFrame,
    long_head: lgb.LGBMClassifier,
    short_head: lgb.LGBMClassifier,
    medians: pd.Series,
) -> pd.DataFrame:
    X, _ = feature_frame(df, medians)
    out = df[[
        "ticker", "date", "time", "month", "minute", "target",
        "time_to_target", "time_to_stop", "nearest_level_dist",
        "nearest_level_dist_bps", "spot_price",
    ]].copy()
    out["p_long"] = long_head.predict_proba(X)[:, 1]
    out["p_short"] = short_head.predict_proba(X)[:, 1]
    out["margin"] = (out["p_long"] - out["p_short"]).abs()
    return out


def row_level_dist(row) -> float:
    for col in ("nearest_level_dist", "nearest_level_dist_bps"):
        try:
            val = float(getattr(row, col))
        except (TypeError, ValueError, AttributeError):
            continue
        if np.isfinite(val):
            return val
    return 999.0


def simulate(scored: pd.DataFrame, cfg: GateConfig, risk: float = 1.0, max_hold: int = 180) -> tuple[dict, pd.DataFrame]:
    if scored.empty:
        return empty_metrics(), pd.DataFrame()

    work = scored.copy()
    long_ok = (
        (work["p_long"].values >= cfg.threshold)
        & ((work["p_long"].values - work["p_short"].values) >= cfg.margin)
    )
    short_ok = (
        (work["p_short"].values >= cfg.threshold)
        & ((work["p_short"].values - work["p_long"].values) >= cfg.margin)
    )
    if cfg.side_mode == "long":
        short_ok[:] = False
    elif cfg.side_mode == "short":
        long_ok[:] = False

    level = pd.to_numeric(work["nearest_level_dist"], errors="coerce")
    fallback_level = pd.to_numeric(work["nearest_level_dist_bps"], errors="coerce")
    level = level.where(level.notna(), fallback_level).fillna(999.0)
    mask = (
        (work["minute"].values >= cfg.start_minute)
        & (work["minute"].values < cfg.end_minute)
        & (level.values <= cfg.max_level_dist)
        & (long_ok | short_ok)
    )
    if not mask.any():
        return empty_metrics(), pd.DataFrame()

    candidates = work.loc[mask].copy()
    candidates["direction"] = np.where(
        long_ok[mask] & (work.loc[mask, "p_long"].values >= work.loc[mask, "p_short"].values),
        "LONG",
        "SHORT",
    )
    candidates["confidence"] = np.where(
        candidates["direction"].values == "LONG",
        candidates["p_long"].values,
        candidates["p_short"].values,
    )
    candidates = candidates.sort_values(["ticker", "date", "minute", "confidence"], ascending=[True, True, True, False])

    trades = []
    last_trade: dict[tuple[str, str], int] = {}
    open_until: dict[tuple[str, str], int] = {}
    trades_per_day: dict[tuple[str, str], int] = {}

    for row in candidates.itertuples(index=False):
        key = (str(row.ticker), str(row.date))
        minute = int(row.minute)
        if minute < open_until.get(key, -999999):
            continue
        if minute - last_trade.get(key, -999999) < 8:
            continue
        if trades_per_day.get(key, 0) >= cfg.max_trades_per_day:
            continue

        side_val = 1 if row.direction == "LONG" else -1
        win = int(row.target) == side_val
        reward_r = float(REWARD_R.get(str(row.ticker), 2.0))
        pnl_r = reward_r * risk if win else -risk
        hold = int(row.time_to_target) if win and int(row.time_to_target) > 0 else int(row.time_to_stop)
        if hold <= 0:
            hold = max_hold
        hold = max(1, min(max_hold, hold))

        trades.append({
            "ticker": str(row.ticker),
            "date": str(row.date),
            "time": str(row.time),
            "month": int(row.month),
            "minute": minute,
            "direction": row.direction,
            "target": int(row.target),
            "p_long": float(row.p_long),
            "p_short": float(row.p_short),
            "confidence": float(row.confidence),
            "pnl_r": float(pnl_r),
            "win": bool(win),
            "hold_minutes_proxy": int(hold),
        })
        open_until[key] = minute + hold
        last_trade[key] = minute
        trades_per_day[key] = trades_per_day.get(key, 0) + 1

    trades_df = pd.DataFrame(trades)
    return metrics_from_trades(trades_df), trades_df


def empty_metrics() -> dict:
    return {"trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "pnl_r": 0.0}


def metrics_from_trades(trades_df: pd.DataFrame) -> dict:
    if trades_df.empty:
        return empty_metrics()
    pnl = trades_df["pnl_r"].astype(float).values
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gp = float(wins.sum()) if len(wins) else 0.0
    gl = float(-losses.sum()) if len(losses) else 0.0
    pf = gp / gl if gl > 0 else (math.inf if gp > 0 else 0.0)
    return {
        "trades": int(len(pnl)),
        "win_rate": float((pnl > 0).mean()),
        "profit_factor": float(pf),
        "pnl_r": float(pnl.sum()),
    }


def candidate_grid() -> list[GateConfig]:
    thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
    margins = [0.00, 0.05, 0.10, 0.15, 0.20]
    level_dists = [10.0, 15.0, 25.0, 999.0]
    windows = [(580, 660), (580, 720), (580, 780), (600, 780), (630, 900), (580, 960)]
    max_per_day = [1, 2, 3, 99]
    side_modes = ["both", "long", "short"]
    return [
        GateConfig(t, m, d, start, end, mpd, side)
        for t in thresholds
        for m in margins
        for d in level_dists
        for start, end in windows
        for mpd in max_per_day
        for side in side_modes
    ]


def config_score(metrics: dict, min_trades: int, target_wr: float, target_pf: float) -> float:
    n = metrics["trades"]
    wr = metrics["win_rate"]
    pf = metrics["profit_factor"]
    pnl = metrics["pnl_r"]
    if n < min_trades:
        return -1000.0 + n
    pf_capped = min(pf, 10.0) if np.isfinite(pf) else 10.0
    score = 10.0 * wr + math.log1p(max(pf_capped, 0.0)) + 0.01 * pnl + min(n, 150) / 150.0
    if wr < target_wr:
        score -= 15.0 * (target_wr - wr)
    if pf < target_pf:
        score -= 2.0 * (target_pf - pf)
    return float(score)


def run(args: argparse.Namespace) -> None:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = load_dataset(args.data)
    if args.tickers:
        df = df[df["ticker"].isin(args.tickers)].copy()
    months = month_range(args.start_month, args.end_month)
    grid = candidate_grid()

    all_trades = []
    fold_rows = []
    validation_rows = []

    for test_month in months:
        val_start = month_add(test_month, -args.val_months)
        train_end = month_add(val_start, -1)
        train_start = month_add(train_end, -(args.train_months - 1))
        for ticker in sorted(df["ticker"].unique()):
            train_df = df[
                (df["ticker"] == ticker)
                & (df["month"] >= train_start)
                & (df["month"] <= train_end)
            ].copy()
            val_df = df[
                (df["ticker"] == ticker)
                & (df["month"] >= val_start)
                & (df["month"] < test_month)
            ].copy()
            test_df = df[(df["ticker"] == ticker) & (df["month"] == test_month)].copy()
            if len(train_df) < args.min_train_rows or len(val_df) < args.min_val_rows or test_df.empty:
                continue

            print(
                f"[Fold] {ticker} test={test_month} train={train_start}-{train_end} "
                f"val={val_start}-{month_add(test_month, -1)} rows={len(train_df)}/{len(val_df)}/{len(test_df)}",
                flush=True,
            )
            long_head, short_head, medians = fit_heads(train_df, seed=args.seed + test_month, n_estimators=args.n_estimators)
            val_scored = score_heads(val_df, long_head, short_head, medians)
            test_scored = score_heads(test_df, long_head, short_head, medians)

            best_cfg = None
            best_metrics = None
            best_score = -1e18
            for cfg in grid:
                metrics, _ = simulate(val_scored, cfg)
                score = config_score(metrics, args.min_val_trades, args.target_wr, args.target_pf)
                if score > best_score:
                    best_score = score
                    best_cfg = cfg
                    best_metrics = metrics
            assert best_cfg is not None and best_metrics is not None

            test_metrics, test_trades = simulate(test_scored, best_cfg)
            if not test_trades.empty:
                test_trades["test_month"] = test_month
                test_trades["selected_threshold"] = best_cfg.threshold
                test_trades["selected_margin"] = best_cfg.margin
                test_trades["selected_side_mode"] = best_cfg.side_mode
                all_trades.append(test_trades)

            fold_rows.append({
                "ticker": ticker,
                "test_month": test_month,
                "train_start": train_start,
                "train_end": train_end,
                "val_start": val_start,
                "val_end": month_add(test_month, -1),
                **{f"cfg_{k}": getattr(best_cfg, k) for k in best_cfg.__dataclass_fields__},
                **{f"val_{k}": v for k, v in best_metrics.items()},
                **{f"test_{k}": v for k, v in test_metrics.items()},
                "score": best_score,
            })
            validation_rows.append({**fold_rows[-1]})
            print(
                f"  selected {best_cfg} | val WR={best_metrics['win_rate']:.1%} "
                f"PF={best_metrics['profit_factor']:.2f} n={best_metrics['trades']} "
                f"-> test WR={test_metrics['win_rate']:.1%} PF={test_metrics['profit_factor']:.2f} "
                f"n={test_metrics['trades']}",
                flush=True,
            )

    trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    folds_df = pd.DataFrame(fold_rows)
    trades_df.to_csv(out_dir / "trades.csv", index=False)
    folds_df.to_csv(out_dir / "fold_configs.csv", index=False)

    summary = metrics_from_trades(trades_df)
    by_ticker = (
        trades_df.groupby("ticker").apply(metrics_from_trades).to_dict()
        if not trades_df.empty else {}
    )
    payload = {
        "data": args.data,
        "start_month": args.start_month,
        "end_month": args.end_month,
        "train_months": args.train_months,
        "val_months": args.val_months,
        "target_wr": args.target_wr,
        "target_pf": args.target_pf,
        "overall": summary,
        "by_ticker": by_ticker,
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("\n[SUMMARY]")
    print(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", default="research_papers/JEPA/results/high_precision_signal_wf")
    parser.add_argument("--tickers", nargs="*", default=["SPX", "QQQ", "SPY"])
    parser.add_argument("--start-month", type=int, default=202507)
    parser.add_argument("--end-month", type=int, default=202606)
    parser.add_argument("--train-months", type=int, default=24)
    parser.add_argument("--val-months", type=int, default=6)
    parser.add_argument("--min-train-rows", type=int, default=5000)
    parser.add_argument("--min-val-rows", type=int, default=1000)
    parser.add_argument("--min-val-trades", type=int, default=18)
    parser.add_argument("--target-wr", type=float, default=0.65)
    parser.add_argument("--target-pf", type=float, default=1.30)
    parser.add_argument("--n-estimators", type=int, default=260)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
