from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_add, month_range


DYNAMIC_FEATURES = [
    "hold_minutes",
    "premium_ratio",
    "current_pnl_pct",
    "current_return_on_risk",
    "peak_pnl_pct",
    "mae_pnl_pct",
    "drawdown_from_peak",
    "current_delta",
    "current_delta_abs",
    "current_iv",
    "current_gamma",
    "spot_return_bps",
    "signed_spot_return_bps",
    "minutes_to_close_path",
    "delta_target",
    "actual_delta_abs_entry",
    "entry_premium",
]

STATIC_FEATURE_CANDIDATES = [
    "spot_price",
    "level_target_bps",
    "level_stop_bps",
    "ticker_SPX",
    "ticker_QQQ",
    "ticker_SPY",
    "side_LONG",
    "side_SHORT",
    "jepa180_prob_up",
    "jepa180_confidence",
    "jepa180_direction",
    "jepa180_edge",
    "entry_minute",
    "pos_in_day",
    "minutes_to_close",
    "actual_delta",
    "actual_delta_abs",
    "entry_premium",
    "premium_to_spot_bps",
    "strike_distance_bps",
    "actual_iv",
    "actual_theta",
    "actual_gamma",
    "theta_over_premium",
    "gamma_notional",
    "entry_spread_pct",
    "net_gamma",
    "net_vanna",
    "net_charm",
    "net_dgex",
    "net_zomma",
    "net_delta",
    "signal_persistence_5m",
    "gamma_regime",
    "vanna_bullish",
    "charm_bullish",
    "dgex_sticky",
    "zomma_stabilizing",
    "dist_to_max_gamma",
    "dist_to_min_gamma",
    "dist_to_min_vanna",
    "dist_to_zero_gamma",
    "dist_to_max_dgex",
    "dist_to_min_dgex",
    "wk_net_gamma",
    "wk_net_vanna",
    "wk_net_charm",
    "wk_net_dgex",
    "wk_net_delta",
    "gamma_0dte_vs_wk",
    "vanna_0dte_vs_wk",
    "dgex_0dte_vs_wk",
    "delta_0dte_vs_wk",
    "vix_5d_mean",
    "vix_5d_std",
    "atr_5d_norm",
    "price_vs_ib_high",
    "price_vs_ib_low",
    "ib_range_pct",
    "near_ib_high",
    "near_ib_low",
    "above_ib",
    "below_ib",
    "in_ib_range",
    "dist_fib_127_up",
    "dist_fib_161_up",
    "dist_fib_200_up",
    "dist_fib_127_dn",
    "dist_fib_161_dn",
    "dist_fib_200_dn",
    "atm_iv",
    "iv_zscore",
    "iv_percentile",
    "vix_spot",
    "vix_gamma",
    "vix_regime",
    "rsi",
    "gamma_vanna_ratio",
    "dgex_gamma_ratio",
    "charm_vanna_ratio",
    "delta_gamma_ratio",
    "vega_gamma_ratio",
    "vomma_vega_ratio",
    "gamma_change",
    "vanna_change",
    "dgex_change",
    "delta_change",
    "spot_change",
    "gamma_momentum",
    "price_vs_dgex_magnet",
    "rvol_iv_log",
    "rvol_trend",
    "rvol_regime",
    "ret_1m_vol_adj",
    "ret_5m_vol_adj",
    "ret_15m_vol_adj",
    "time_sin",
    "time_cos",
    "dow_sin",
    "dow_cos",
    "ib_range_percentile",
    "gap_pct",
    "gap_direction",
    "overnight_vs_ib_ratio",
    "days_to_opex_norm",
    "is_opex_week",
    "charm_accel_weighted",
    "gamma_speed",
    "delta_filtered_pcr",
    "pcr_derivative_5m",
    "tlt_ret_1m",
    "tlt_ret_5m",
    "tlt_ret_15m",
    "nearest_level_dist",
    "level_cluster_density",
    "momentum_5m_bps",
    "rejection_bullish",
    "rejection_bearish",
    "trend_grind_up",
    "trend_flush_down",
    "bouncing_from_support",
    "rejecting_resistance",
    "wall_at_fib",
    "wall_at_ib",
    "is_touching_fib",
    "is_touching_max_gamma",
    "is_touching_min_gamma",
    "gamma_x_near_fib_up",
    "gamma_x_near_fib_dn",
    "gamma_x_near_ib",
    "delta_x_near_fib_up",
    "delta_x_near_fib_dn",
    "delta_x_near_ib_high",
    "delta_x_near_ib_low",
    "vanna_x_near_fib_up",
    "vanna_x_near_fib_dn",
    "vanna_x_near_ib",
]


def metrics(trades: pd.DataFrame, expected_months: list[str] | None = None) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": float("nan"),
            "profit_factor": float("nan"),
            "pnl_dollars": 0.0,
            "return_on_risk": 0.0,
            "max_drawdown": 0.0,
            "avg_pnl": float("nan"),
            "avg_hold_minutes": float("nan"),
            "long_rate": float("nan"),
            "min_month_trades": 0,
            "positive_month_rate": float("nan"),
        }
    pnl = trades["pnl_dollars"].astype(float).to_numpy()
    wins = pnl[pnl > 0.0]
    losses = pnl[pnl < 0.0]
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    equity = np.cumsum(pnl)
    peak = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
    by_month = trades.groupby("month")["pnl_dollars"].agg(["count", "sum"])
    if expected_months is not None:
        by_month = by_month.reindex([str(m) for m in expected_months], fill_value=0)
    return {
        "trades": int(len(trades)),
        "win_rate": float((pnl > 0.0).mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf"),
        "pnl_dollars": float(pnl.sum()),
        "return_on_risk": float(trades["return_on_risk"].astype(float).sum()),
        "max_drawdown": float((equity - peak).min()) if len(equity) else 0.0,
        "avg_pnl": float(pnl.mean()),
        "avg_hold_minutes": float(trades["hold_minutes"].astype(float).mean()),
        "long_rate": float((trades["side"].astype(str) == "LONG").mean()),
        "min_month_trades": int(by_month["count"].min()) if not by_month.empty else 0,
        "positive_month_rate": float((by_month["sum"] > 0.0).mean()) if not by_month.empty else float("nan"),
    }


def score_metrics(row: dict, args: argparse.Namespace) -> float:
    trades = int(row.get("trades", 0))
    min_month = int(row.get("min_month_trades", 0))
    pf = float(row.get("profit_factor", 0.0))
    long_rate = float(row.get("long_rate", float("nan")))
    pnl = float(row.get("pnl_dollars", 0.0))
    if trades < int(args.min_val_trades) or min_month < int(args.min_month_trades):
        return -1e18 + trades
    if not np.isfinite(pf) or pf < float(args.min_val_pf):
        return -1e18 + trades
    if pnl <= float(args.min_val_pnl):
        return -1e18 + trades
    if not np.isfinite(long_rate) or long_rate < 0.20 or long_rate > 0.80:
        return -1e18 + trades
    dd = abs(float(row.get("max_drawdown", 0.0)))
    positive_month_rate = float(row.get("positive_month_rate", 0.0))
    return (
        4.0 * math.log1p(min(max(pf, 0.0), 10.0))
        + 0.35 * math.log1p(trades)
        + pnl / 20_000.0
        - dd / 15_000.0
        + positive_month_rate
    )


def load_frames(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    states = pd.read_parquet(args.path_states)
    states["ticker"] = states["ticker"].astype(str).str.upper()
    states["month"] = states["month"].astype(str)
    states = states[
        states["ticker"].isin([str(t).upper() for t in args.tickers])
        & (states["month"] >= str(args.data_start_month))
        & (states["month"] <= str(args.end_month))
    ].copy()
    target = states["future_edge_return_on_risk"].astype(float).clip(0.0, float(args.clip_target))
    states["target_future_edge"] = target

    candidates = pd.read_parquet(args.candidate_labels)
    candidates["ticker"] = candidates["ticker"].astype(str).str.upper()
    candidates["month"] = candidates["date"].astype(str).str.replace("-", "", regex=False).str[:6]
    static_cols = ["candidate_id", *[c for c in STATIC_FEATURE_CANDIDATES if c in candidates.columns]]
    static = candidates[static_cols].copy()
    merged = states.merge(static, on="candidate_id", how="left", suffixes=("", "_static"))
    for col in ["date", "month", "ticker", "side"]:
        if col in merged.columns:
            merged[col] = merged[col].astype(str)
    feature_cols = []
    for col in [*DYNAMIC_FEATURES, *[c for c in STATIC_FEATURE_CANDIDATES if c in merged.columns]]:
        if col in merged.columns and col not in feature_cols and pd.api.types.is_numeric_dtype(merged[col]):
            feature_cols.append(col)
    return merged, candidates, feature_cols


def fit_model(train_states: pd.DataFrame, features: list[str], args: argparse.Namespace):
    train = train_states
    if int(args.max_train_rows) > 0 and len(train) > int(args.max_train_rows):
        train = train.sample(int(args.max_train_rows), random_state=int(args.seed))
    medians = train[features].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x = train[features].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    y = train["target_future_edge"].astype(float)
    model = lgb.LGBMRegressor(
        objective=str(args.objective),
        n_estimators=int(args.n_estimators),
        learning_rate=float(args.learning_rate),
        num_leaves=int(args.num_leaves),
        min_child_samples=int(args.min_child_samples),
        subsample=float(args.subsample),
        colsample_bytree=float(args.colsample_bytree),
        reg_lambda=float(args.reg_lambda),
        random_state=int(args.seed),
        n_jobs=int(args.lgb_jobs),
        verbose=-1,
    )
    model.fit(x, y)
    return model, medians


def score_states(states: pd.DataFrame, features: list[str], model, medians: pd.Series) -> pd.DataFrame:
    if states.empty:
        return states.copy()
    x = states[features].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    out = states.copy()
    out["pred_future_edge"] = model.predict(x).astype(float)
    return out


def apply_max_day(trades: pd.DataFrame, max_day: int) -> pd.DataFrame:
    if trades.empty or int(max_day) >= 999:
        return trades.copy()
    rows: list[dict] = []
    for _, day in trades.sort_values(["date", "entry_time"]).groupby("date", sort=False):
        rows.extend([row._asdict() for row in day.itertuples(index=False)][: int(max_day)])
    return pd.DataFrame(rows) if rows else trades.iloc[0:0].copy()


def simulate(scored_states: pd.DataFrame, delta: float, threshold: float, min_hold: int, max_day: int, hard_stop: float) -> pd.DataFrame:
    if scored_states.empty:
        return pd.DataFrame()
    x = scored_states[np.isclose(scored_states["delta_target"].astype(float), float(delta))].copy()
    if x.empty:
        return pd.DataFrame()
    x = x.sort_values(["candidate_id", "hold_minutes"]).reset_index(drop=True)
    hard = x["current_pnl_pct"].astype(float) <= float(hard_stop)
    model_exit = (x["hold_minutes"].astype(int) >= int(min_hold)) & (x["pred_future_edge"].astype(float) <= float(threshold))
    triggered = x[hard | model_exit].copy()
    if not triggered.empty:
        triggered["exit_reason"] = np.where(
            triggered["current_pnl_pct"].astype(float) <= float(hard_stop),
            "hard_stop",
            "model_exit",
        )
        first = triggered.groupby("candidate_id", sort=False).head(1)
    else:
        first = x.iloc[0:0].copy()
    missing = pd.Index(x["candidate_id"].unique()).difference(first["candidate_id"] if not first.empty else [])
    if len(missing):
        last = x[x["candidate_id"].isin(missing)].groupby("candidate_id", sort=False).tail(1).copy()
        last["exit_reason"] = "max_time"
        exits = pd.concat([first, last], ignore_index=True)
    else:
        exits = first
    if exits.empty:
        return pd.DataFrame()
    trades = pd.DataFrame(
        {
            "candidate_id": exits["candidate_id"].astype(int),
            "signal_id": exits["signal_id"].astype(int),
            "ticker": exits["ticker"].astype(str),
            "date": exits["date"].astype(str),
            "month": exits["month"].astype(str),
            "entry_time": exits["entry_time"].astype(str),
            "exit_time": exits["path_time"].astype(str),
            "side": exits["side"].astype(str),
            "delta_target": exits["delta_target"].astype(float),
            "actual_delta_abs": exits["actual_delta_abs_entry"].astype(float),
            "actual_strike": exits["actual_strike"].astype(float),
            "entry_premium": exits["entry_premium"].astype(float),
            "contracts": exits["contracts"].astype(int),
            "exit_reason": exits["exit_reason"].astype(str),
            "hold_minutes": exits["hold_minutes"].astype(int),
            "pnl_pct": exits["current_pnl_pct"].astype(float),
            "pnl_dollars": exits["current_pnl_dollars"].astype(float),
            "return_on_risk": exits["current_return_on_risk"].astype(float),
            "pred_future_edge": exits["pred_future_edge"].astype(float),
            "peak_pnl_pct": exits["peak_pnl_pct"].astype(float),
            "mae_pnl_pct": exits["mae_pnl_pct"].astype(float),
        }
    ).sort_values(["date", "entry_time", "candidate_id"])
    return apply_max_day(trades, int(max_day))


def run_fold(ticker: str, test_month: str, states: pd.DataFrame, features: list[str], args: argparse.Namespace) -> tuple[pd.DataFrame, dict] | None:
    val_months = [month_add(str(test_month), -i) for i in range(int(args.val_months), 0, -1)]
    first_val = val_months[0]
    if bool(args.pooled_train):
        train = states[states["month"].astype(str) < first_val].copy()
    else:
        train = states[(states["ticker"].astype(str) == ticker) & (states["month"].astype(str) < first_val)].copy()
    val = states[(states["ticker"].astype(str) == ticker) & (states["month"].astype(str).isin(val_months))].copy()
    test = states[(states["ticker"].astype(str) == ticker) & (states["month"].astype(str) == str(test_month))].copy()
    if len(train) < int(args.min_train_rows) or len(val) < int(args.min_val_rows) or test.empty:
        return None
    model, medians = fit_model(train, features, args)
    val_scored = score_states(val, features, model, medians)
    test_scored = score_states(test, features, model, medians)

    threshold_grid = sorted(set([float(x) for x in args.exit_thresholds]))
    finite = val_scored["pred_future_edge"].replace([np.inf, -np.inf], np.nan).dropna()
    if len(finite):
        threshold_grid = sorted(set([*threshold_grid, *[float(x) for x in np.quantile(finite, [0.05, 0.10, 0.20, 0.30, 0.40])]]))

    best = None
    best_row: dict = {}
    best_score = -1e18
    for delta in args.delta_targets:
        for threshold in threshold_grid:
            for min_hold in args.min_hold_grid:
                for max_day in args.max_day_grid:
                    trades = simulate(val_scored, float(delta), float(threshold), int(min_hold), int(max_day), float(args.hard_stop_pct))
                    row = metrics(trades, val_months)
                    cfg_score = score_metrics(row, args)
                    if cfg_score > best_score:
                        best_score = cfg_score
                        best = (float(delta), float(threshold), int(min_hold), int(max_day))
                        best_row = row

    if best is None or (best_score <= -1e17 and not bool(args.allow_invalid_val_deploy)):
        test_trades = pd.DataFrame()
        test_row = metrics(test_trades, [str(test_month)])
        cfg_name = "ABSTAIN_INVALID_VAL"
        abstained = True
    else:
        delta, threshold, min_hold, max_day = best
        test_trades = simulate(test_scored, delta, threshold, min_hold, max_day, float(args.hard_stop_pct))
        test_row = metrics(test_trades, [str(test_month)])
        cfg_name = f"d{delta:.2f}_thr{threshold:.4f}_hold{min_hold}_maxday{max_day if max_day < 999 else 'all'}"
        abstained = False
        if not test_trades.empty:
            test_trades["test_month"] = str(test_month)
            test_trades["deploy_config"] = cfg_name

    fold = {
        "ticker": ticker,
        "month": str(test_month),
        "deploy_config": cfg_name,
        "val_months": ",".join(val_months),
        "train_rows": int(len(train)),
        "val_rows": int(len(val)),
        "test_rows": int(len(test)),
        "feature_count": int(len(features)),
        "val_score": float(best_score),
        "abstained_invalid_val": bool(abstained),
        **{f"val_{k}": v for k, v in best_row.items()},
        **{f"test_{k}": v for k, v in test_row.items()},
    }
    print(
        f"[PATH_EXIT] {ticker} {test_month} cfg={cfg_name} "
        f"val_pf={best_row.get('profit_factor', float('nan')):.3f} "
        f"test_trades={test_row.get('trades', 0)} "
        f"test_pf={test_row.get('profit_factor', float('nan')):.3f} "
        f"test_pnl={test_row.get('pnl_dollars', 0.0):.0f}",
        flush=True,
    )
    return test_trades, fold


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, metadata: dict) -> None:
    args_meta = metadata.get("args", {})
    expected = month_range(str(args_meta.get("start_month")), str(args_meta.get("end_month")))
    overall = metrics(trades, expected)
    per_ticker = {
        str(ticker): metrics(part, expected)
        for ticker, part in trades.groupby("ticker", sort=True)
    } if not trades.empty else {}
    lines = [
        "# Option Path Exit Model Walk-Forward",
        "",
        "Causal diagnostic: train a premium-path future-edge model on prior months; validation chooses delta, exit threshold, min hold and max trades/day.",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        "## Per Ticker",
        "",
        "```json",
        json.dumps(per_ticker, indent=2, allow_nan=True),
        "```",
        "",
        "## Fold Configs",
        "",
        "```csv",
        folds.to_csv(index=False),
        "```",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(metadata, indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (output_dir / "metrics.json").write_text(
        json.dumps({"overall": overall, "per_ticker": per_ticker, "metadata": metadata}, indent=2, allow_nan=True),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward dynamic option path exit model.")
    parser.add_argument("--path-states", required=True)
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--data-start-month", default="202507")
    parser.add_argument("--start-month", default="202510")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--val-months", type=int, default=2)
    parser.add_argument("--pooled-train", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--min-train-rows", type=int, default=50000)
    parser.add_argument("--min-val-rows", type=int, default=5000)
    parser.add_argument("--min-val-trades", type=int, default=30)
    parser.add_argument("--min-month-trades", type=int, default=10)
    parser.add_argument("--min-val-pf", type=float, default=1.0)
    parser.add_argument("--min-val-pnl", type=float, default=0.0)
    parser.add_argument("--delta-targets", nargs="+", type=float, default=[0.50, 0.60, 0.70])
    parser.add_argument("--exit-thresholds", nargs="+", type=float, default=[0.0, 0.02, 0.05, 0.10, 0.20, 0.35])
    parser.add_argument("--min-hold-grid", nargs="+", type=int, default=[5, 15, 30])
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[999, 12, 8, 4, 2, 1])
    parser.add_argument("--hard-stop-pct", type=float, default=-0.60)
    parser.add_argument("--clip-target", type=float, default=2.5)
    parser.add_argument("--max-train-rows", type=int, default=500000)
    parser.add_argument("--objective", default="regression_l1")
    parser.add_argument("--n-estimators", type=int, default=180)
    parser.add_argument("--learning-rate", type=float, default=0.04)
    parser.add_argument("--num-leaves", type=int, default=63)
    parser.add_argument("--min-child-samples", type=int, default=250)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.85)
    parser.add_argument("--reg-lambda", type=float, default=10.0)
    parser.add_argument("--lgb-jobs", type=int, default=32)
    parser.add_argument("--allow-invalid-val-deploy", action="store_true")
    parser.add_argument("--seed", type=int, default=20260617)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    states, _, features = load_frames(args)
    metadata = {"args": vars(args), "feature_count": len(features), "features": features, "state_rows": int(len(states))}
    months = [m for m in sorted(states["month"].astype(str).unique()) if str(args.start_month) <= m <= str(args.end_month)]
    all_trades: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    for ticker in [str(t).upper() for t in args.tickers]:
        for month in months:
            result = run_fold(ticker, str(month), states, features, args)
            if result is None:
                continue
            trades, fold = result
            if not trades.empty:
                all_trades.append(trades)
            fold_rows.append(fold)
            trade_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
            fold_df = pd.DataFrame(fold_rows)
            if not trade_df.empty:
                trade_df.to_csv(output_dir / "option_path_exit_model_trades.csv", index=False)
            fold_df.to_csv(output_dir / "fold_configs.csv", index=False)
            write_summary(output_dir, trade_df, fold_df, metadata)

    trade_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    fold_df = pd.DataFrame(fold_rows)
    if not trade_df.empty:
        trade_df.to_csv(output_dir / "option_path_exit_model_trades.csv", index=False)
    fold_df.to_csv(output_dir / "fold_configs.csv", index=False)
    write_summary(output_dir, trade_df, fold_df, metadata)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
