"""Walk-forward out-of-fold (OOF) GBT predictions for unbiased candidate generation.

Generates per-minute ``jepa180_pred_bps`` values where every prediction is
genuinely out-of-sample for the GBT that produced it.  The output parquet
replaces the frozen-model inference in Step 5 of ``run_pipeline.ps1`` and
removes the lookahead bias caused by applying a single frozen GBT (trained
up to ``TrainEndDate``) to its own training period.

Usage (standalone)::

    python walkforward_gbt_oof.py \
        --data  training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet \
        --jepa-feature-names  models/jepa/xinput_v3_pipeline/jepa_feature_names.json \
        --output  results/oof_gbt_predictions.parquet

When plugged into the pipeline the output path is passed to Step 5 via
``--oof-predictions``, which merges the OOF predictions instead of calling
``Jepa180mSignalModel.predict_frame()``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NEURAL_ROOT = PROJECT_ROOT / "neural"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(NEURAL_ROOT) not in sys.path:
    sys.path.insert(0, str(NEURAL_ROOT))

from neural.jepa.evaluate_180m_direction import (
    build_terminal_180m_frame,
    choose_thresholds,
    fmt_float,
    fmt_money,
    fmt_pct,
    logged_phase,
    predict_returns,
    select_features,
    simulate_hold180,
    trade_metrics,
    train_model,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_ticker(value: str) -> str:
    return str(value).replace("/", "").upper()


def simulate_oof_trades(
    oof_df: pd.DataFrame,
    cost_bps: float,
    cooldown_steps: int,
    notional: float,
) -> pd.DataFrame:
    if oof_df.empty:
        return pd.DataFrame()
    cols = ["ticker", "date", "time", "pos_in_day", "spot_price", "future_return_180m", "future_return_bps_180m", "long_pnl_180m", "short_pnl_180m"]
    for optional in ["terminal_exit_time", "terminal_hold_minutes", "terminal_horizon_truncated", "month"]:
        if optional in oof_df.columns:
            cols.append(optional)
    work = oof_df[cols].copy()
    work["pred_bps"] = oof_df["jepa180_pred_bps"]
    work["side"] = oof_df["jepa180_direction"].astype(int)
    work = work[work["side"] != 0].sort_values(["ticker", "date", "pos_in_day"]).reset_index(drop=True)
    trades = []
    next_allowed: dict[tuple[str, str], int] = {}
    for row in work.itertuples(index=False):
        key = (str(row.ticker), str(row.date))
        pos = int(row.pos_in_day)
        if pos < next_allowed.get(key, -1):
            continue
        gross_bps = float(row.long_pnl_180m) if row.side > 0 else float(row.short_pnl_180m)
        net_bps = gross_bps - float(cost_bps)
        trades.append(
            {
                "ticker": str(row.ticker),
                "date": str(row.date),
                "time": str(row.time),
                "month": str(getattr(row, "month", "")),
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


def trade_row_md(label: str, metrics: dict, ticker: str = "ALL") -> str:
    return (
        f"| {label} | {fmt_money(metrics.get('pnl_dollars', 0.0))} | "
        f"{fmt_money(metrics.get('max_drawdown', 0.0))} | {fmt_pct(metrics.get('win_rate', float('nan')))} | "
        f"{fmt_float(metrics.get('profit_factor', float('nan')))} | {ticker} | "
        f"{metrics.get('trades', 0)} |"
    )


def _write_summary(
    output_dir: Path,
    args,
    windows: list[dict],
    oof_df: pd.DataFrame,
    trades: pd.DataFrame,
) -> None:
    lines = [
        "# Walk-Forward OOF GBT Predictions & Trading",
        "",
        f"Data: `{args.data}`",
        f"Mode: `{args.mode}`",
        f"Tickers: `{args.tickers}`",
        f"Min train months: `{args.min_train_months}`",
        f"Val months: `{args.val_months}`",
        f"N-estimators: `{args.n_estimators}`",
        "",
        "## Summary",
        "",
        f"- Total OOF rows: **{len(oof_df):,}**",
        f"- Total signals (direction ≠ 0): **{int((oof_df['jepa180_direction'] != 0).sum()):,}**",
        f"- Trades executed (after cooldown): **{len(trades):,}**",
        f"- Folds: **{len(windows)}**",
        "",
        "## Trading Performance (180m Fixed Hold)",
        "",
        "| Month/Segment | PnL | Max Drawdown | Win Rate | Profit Factor | Ticker | Trades |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    
    overall = trade_metrics(trades)
    lines.append(trade_row_md("Overall OOF", overall, "ALL"))
    
    if not trades.empty:
        for ticker, frame in trades.groupby("ticker", sort=True):
            tm = trade_metrics(frame)
            lines.append(trade_row_md(f"Overall {ticker}", tm, ticker))
            
    if not trades.empty:
        for month, frame in trades.groupby("month", sort=True):
            tm = trade_metrics(frame)
            lines.append(trade_row_md(month, tm, "ALL"))
            
    lines += [
        "",
        "## Per-Ticker Fold Windows",
        "",
        "| Ticker | Month | Train Months | Train Rows | Test Rows | Long Threshold | Short Threshold | Val Score |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for w in windows:
        lines.append(
            f"| {w['ticker']} | {w['test_month']} | {w['train_months_count']} | "
            f"{w['train_rows']:,} | {w['test_rows']:,} | "
            f"{fmt_float(w['long_threshold'])} | {fmt_float(w['short_threshold'])} | "
            f"{fmt_float(w.get('val_score', float('nan')))} |"
        )
    lines.append("")
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    
    print("\n" + "="*85)
    print(" OOF GBT TRADING PERFORMANCE (180m Fixed Hold)")
    print("="*85)
    print(f"{'Segment':<15} | {'PnL':>10} | {'Max DD':>10} | {'Win Rate':>8} | {'PF':>6} | {'Ticker':<6} | {'Trades':>6}")
    print("-" * 85)
    
    def print_row(label, tm, tck="ALL"):
        pnl = fmt_money(tm.get('pnl_dollars', 0.0))
        dd = fmt_money(tm.get('max_drawdown', 0.0))
        wr = fmt_pct(tm.get('win_rate', float('nan')))
        pf = fmt_float(tm.get('profit_factor', float('nan')))
        trds = tm.get('trades', 0)
        print(f"{label:<15} | {pnl:>10} | {dd:>10} | {wr:>8} | {pf:>6} | {tck:<6} | {trds:>6}")

    print_row("Overall OOF", overall, "ALL")
    if not trades.empty:
        print("-" * 85)
        for ticker, frame in trades.groupby("ticker", sort=True):
            print_row(f"Overall {ticker}", trade_metrics(frame), ticker)
        print("-" * 85)
        for month, frame in trades.groupby("month", sort=True):
            print_row(month, trade_metrics(frame), "ALL")
    print("="*85 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate walk-forward out-of-fold (OOF) GBT predictions "
            "for unbiased candidate generation in the JEPA option pipeline."
        ),
    )
    parser.add_argument("--data", required=True, help="JEPA-enriched parquet.")
    parser.add_argument("--jepa-feature-names", required=True, help="JEPA feature names JSON.")
    parser.add_argument("--output", required=True, help="Output parquet with OOF predictions.")
    parser.add_argument("--output-dir", default="", help="Optional directory for summary/metrics (defaults to parent of --output).")
    parser.add_argument("--mode", default="base_jepa", help="Feature mode (base, jepa_only, base_jepa).")
    parser.add_argument("--tickers", nargs="+", default=["SPX", "QQQ", "SPY"])
    parser.add_argument("--min-train-months", type=int, default=12)
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--truncate-eod-horizon", action="store_true")
    parser.add_argument("--min-abs-bps", type=float, default=0.0)
    parser.add_argument("--cost-bps", type=float, default=1.0)
    parser.add_argument("--cooldown-steps", type=int, default=36)
    parser.add_argument("--notional", type=float, default=100000.0)
    parser.add_argument("--min-val-trades", type=int, default=4)
    parser.add_argument("--n-estimators", type=int, default=250)
    parser.add_argument("--n-jobs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=777)
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_dir = Path(args.output_dir) if args.output_dir else output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Load and prepare data
    # ------------------------------------------------------------------
    with logged_phase(f"load data from {args.data}"):
        df = build_terminal_180m_frame(
            args.data,
            args.horizon_steps,
            args.min_abs_bps,
            truncate_to_eod=args.truncate_eod_horizon,
        )

    features_orig = select_features(df, args.mode, args.jepa_feature_names)
    tickers = [normalize_ticker(t) for t in args.tickers]
    df["ticker"] = df["ticker"].map(normalize_ticker)

    print(
        f"[OOF_GBT] rows={len(df):,} features={len(features_orig)} mode={args.mode} "
        f"tickers={tickers} min_train_months={args.min_train_months}",
        flush=True,
    )

    # ------------------------------------------------------------------
    # 2. Walk-forward per ticker
    # ------------------------------------------------------------------
    all_predictions: list[pd.DataFrame] = []
    all_windows: list[dict] = []
    global_start = time.time()

    for ticker in tickers:
        ticker_df = df[df["ticker"] == ticker].copy()
        if ticker_df.empty:
            print(f"[OOF_GBT] skipping {ticker}: no data", flush=True)
            continue
        ticker_months = sorted(ticker_df["month"].unique().tolist())
        eligible_months = ticker_months[args.min_train_months:]
        print(
            f"[OOF_GBT] ticker={ticker} months={len(ticker_months)} "
            f"eligible_folds={len(eligible_months)}",
            flush=True,
        )

        for test_month in eligible_months:
            train_months = [m for m in ticker_months if m < test_month]
            train_all = ticker_df[ticker_df["month"].isin(train_months)].copy()
            test = ticker_df[ticker_df["month"] == test_month].copy()
            if test.empty or train_all.empty:
                continue

            # Validation split for threshold selection and early stopping
            val_keys = train_months[-args.val_months:] if args.val_months > 0 else train_months[-1:]
            fit = train_all[~train_all["month"].isin(val_keys)].copy()
            val = train_all[train_all["month"].isin(val_keys)].copy()
            if fit.empty or val.empty:
                fit = train_all.copy()
                val = train_all.tail(min(len(train_all), max(200, len(train_all) // 5))).copy()

            # Train a validation model to choose thresholds
            val_model, val_medians, val_features = train_model(fit, features_orig, args.seed, args.n_estimators, args.n_jobs, ticker=ticker)
            val_pred = predict_returns(val_model, val, val_features, val_medians)
            thresholds = choose_thresholds(
                val, val_pred, args.cost_bps, args.cooldown_steps, args.notional, max(2, args.min_val_trades // 2), ticker=ticker
            )

            # Retrain on ALL training months for the OOF test prediction
            model, medians, final_features = train_model(train_all, features_orig, args.seed, args.n_estimators, args.n_jobs, ticker=ticker)
            test_pred = predict_returns(model, test, final_features, medians)

            # Build prediction frame
            keep_cols = ["ticker", "date", "time", "month", "pos_in_day", "spot_price", "future_return_180m", "future_return_bps_180m", "long_pnl_180m", "short_pnl_180m"]
            for opt_col in ["terminal_exit_time", "terminal_hold_minutes", "terminal_horizon_truncated"]:
                if opt_col in test.columns:
                    keep_cols.append(opt_col)
            pred = test[keep_cols].copy()
            pred["jepa180_pred_bps"] = test_pred
            pred["jepa180_long_threshold"] = float(thresholds["long_threshold"])
            pred["jepa180_short_threshold"] = float(thresholds["short_threshold"])
            all_predictions.append(pred)

            window = {
                "ticker": ticker,
                "test_month": test_month,
                "train_months_count": len(train_months),
                "train_rows": len(train_all),
                "test_rows": len(test),
                "long_threshold": float(thresholds["long_threshold"]),
                "short_threshold": float(thresholds["short_threshold"]),
                "val_score": float(thresholds.get("val_score", float("nan"))),
            }
            all_windows.append(window)

            elapsed = time.time() - global_start
            print(
                f"[OOF_GBT] ticker={ticker} month={test_month} "
                f"train={len(train_all):,} test={len(test):,} "
                f"long_threshold={thresholds['long_threshold']:.3f} "
                f"short_threshold={thresholds['short_threshold']:.3f} "
                f"elapsed={elapsed:.0f}s",
                flush=True,
            )

    # ------------------------------------------------------------------
    # 3. Assemble and save
    # ------------------------------------------------------------------
    if not all_predictions:
        raise RuntimeError("No OOF predictions generated. Check --min-train-months and data coverage.")

    oof_df = pd.concat(all_predictions, ignore_index=True)

    # Add derived columns matching Jepa180mSignalModel.predict_frame() output
    pred_bps = oof_df["jepa180_pred_bps"].astype(np.float64)
    oof_df["jepa180_prob_up"] = pred_bps
    oof_df["jepa180_confidence"] = pred_bps.abs() # Not technically a probability anymore, just the magnitude
    oof_df["jepa180_edge"] = pred_bps.abs()
    oof_df["jepa180_direction"] = 0
    oof_df["jepa180_signal"] = "HOLD"

    long_mask = pred_bps >= oof_df["jepa180_long_threshold"].astype(np.float64)
    short_mask = pred_bps <= -oof_df["jepa180_short_threshold"].astype(np.float64)
    oof_df.loc[long_mask, "jepa180_direction"] = 1
    oof_df.loc[long_mask, "jepa180_signal"] = "LONG"
    oof_df.loc[short_mask, "jepa180_direction"] = -1
    oof_df.loc[short_mask, "jepa180_signal"] = "SHORT"

    with logged_phase(f"write OOF parquet rows={len(oof_df):,} to {output_path}"):
        oof_df.to_parquet(output_path, index=False)

    # Summary stats
    signal_count = int((oof_df["jepa180_direction"] != 0).sum())
    long_count = int((oof_df["jepa180_direction"] == 1).sum())
    short_count = int((oof_df["jepa180_direction"] == -1).sum())

    trades = simulate_oof_trades(oof_df, args.cost_bps, args.cooldown_steps, args.notional)
    if not trades.empty:
        trades.to_csv(output_dir / "oof_gbt_trades.csv", index=False)

    metadata = {
        "config": vars(args),
        "total_rows": len(oof_df),
        "signal_rows": signal_count,
        "long_signals": long_count,
        "short_signals": short_count,
        "feature_count": len(features_orig),
        "features": features_orig,
        "windows": all_windows,
    }
    (output_dir / "oof_gbt_metrics.json").write_text(
        json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8",
    )

    windows_df = pd.DataFrame(all_windows)
    if not windows_df.empty:
        windows_df.to_csv(output_dir / "oof_gbt_windows.csv", index=False)

    _write_summary(output_dir, args, all_windows, oof_df, trades)

    elapsed = time.time() - global_start
    print(
        f"\n[OOF_GBT] DONE rows={len(oof_df):,} signals={signal_count:,} "
        f"(long={long_count:,} short={short_count:,}) "
        f"folds={len(all_windows)} elapsed={elapsed:.0f}s\n"
        f"[OOF_GBT] Output: {output_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
