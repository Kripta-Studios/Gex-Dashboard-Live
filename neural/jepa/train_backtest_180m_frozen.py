from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.evaluate_180m_direction import (
    ModeResult,
    build_terminal_180m_frame,
    choose_thresholds,
    fmt_float,
    fmt_money,
    fmt_pct,
    predict_returns,
    select_features,
    simulate_hold180,
    summarize_predictions,
    trade_metrics,
    train_model,
    write_mode_outputs,
)


def normalize_date(value) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else str(value)


def save_model_artifact(
    path: Path,
    model,
    medians: pd.Series,
    features: list[str],
    thresholds: dict,
    meta: dict,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "medians": medians.to_dict(),
            "features": features,
            "thresholds": thresholds,
            "meta": meta,
        },
        path,
    )


def run_frozen_mode(df: pd.DataFrame, args, mode: str, model_dir: Path) -> ModeResult:
    features = select_features(df, mode, args.jepa_feature_names)
    predictions = []
    trades = []
    windows = []
    train_end = normalize_date(args.train_end_date)
    test_start = normalize_date(args.test_start_date)
    test_end = normalize_date(args.test_end_date) if args.test_end_date else None

    for ticker in sorted(df["ticker"].astype(str).unique().tolist()):
        ticker_df = df[df["ticker"].astype(str) == ticker].copy()
        train_all = ticker_df[ticker_df["date"] <= train_end].copy()
        test = ticker_df[ticker_df["date"] >= test_start].copy()
        if test_end:
            test = test[test["date"] <= test_end].copy()
        if train_all.empty or test.empty:
            continue
        if train_all["future_up_180m"].nunique() < 2:
            continue

        train_months = sorted(train_all["month"].unique().tolist())
        val_keys = train_months[-args.val_months :] if args.val_months > 0 else train_months[-1:]
        fit = train_all[~train_all["month"].isin(val_keys)].copy()
        val = train_all[train_all["month"].isin(val_keys)].copy()
        if fit.empty or fit["future_up_180m"].nunique() < 2 or val.empty:
            fit = train_all.copy()
            val = train_all.tail(min(len(train_all), max(200, len(train_all) // 5))).copy()

        print(
            f"[JEPA_180M_FROZEN] mode={mode} ticker={ticker} "
            f"train_rows={len(train_all)} val_rows={len(val)} test_rows={len(test)}",
            flush=True,
        )

        val_model, val_medians, val_features = train_model(fit, features, args.seed, args.n_estimators, args.n_jobs, ticker=ticker)
        val_pred = predict_returns(val_model, val, val_features, val_medians)
        thresholds = choose_thresholds(
            val,
            val_pred,
            args.cost_bps,
            args.cooldown_steps,
            args.notional,
            max(2, args.min_val_trades // 2),
            ticker=ticker,
        )

        model, medians, final_features = train_model(train_all, features, args.seed, args.n_estimators, args.n_jobs, ticker=ticker)
        test_pred = predict_returns(model, test, final_features, medians)
        pred_cols = [
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
        pred_cols += [c for c in ["terminal_exit_time", "terminal_hold_minutes", "terminal_horizon_truncated"] if c in test.columns]
        pred_frame = test[pred_cols].copy()
        pred_frame["feature_mode"] = mode
        pred_frame["pred_bps"] = test_pred
        predictions.append(pred_frame)

        test_trades = simulate_hold180(
            test,
            test_pred,
            thresholds["long_threshold"],
            thresholds["short_threshold"],
            args.cost_bps,
            args.cooldown_steps,
            args.notional,
        )
        if not test_trades.empty:
            test_trades["feature_mode"] = mode
            test_trades["train_end_date"] = train_end
            trades.append(test_trades)

        meta = {
            "mode": mode,
            "ticker": ticker,
            "train_end_date": train_end,
            "test_start_date": test_start,
            "test_end_date": test_end,
            "feature_count": len(final_features),
            "horizon_steps": args.horizon_steps,
            "horizon_minutes": args.horizon_steps * 5,
            "truncate_eod_horizon": bool(args.truncate_eod_horizon),
            "cost_bps": args.cost_bps,
            "cooldown_steps": args.cooldown_steps,
            "notional": args.notional,
        }
        save_model_artifact(model_dir / mode / f"{ticker}.joblib", model, medians, final_features, thresholds, meta)
        windows.append(
            {
                "feature_mode": mode,
                "ticker": ticker,
                "train_end_date": train_end,
                "test_start_date": test_start,
                "test_end_date": test_end,
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
    return ModeResult(mode, pred_all, windows, features)


def cost_sensitivity(output_dir: Path, modes: list[str], base_cost_bps: float, notional: float) -> pd.DataFrame:
    rows = []
    for total_cost in [1.0, 3.0, 5.0, 10.0]:
        extra_cost = total_cost - base_cost_bps
        for mode in modes:
            path = output_dir / f"{mode}_trades.csv"
            if not path.exists():
                continue
            trades = pd.read_csv(path)
            if trades.empty:
                continue
            adj_net_bps = trades["net_bps"].astype(float) - extra_cost
            pnl = adj_net_bps / 10000.0 * notional
            wins = pnl[pnl > 0.0].sum()
            losses = -pnl[pnl < 0.0].sum()
            equity = pnl.cumsum()
            drawdown = equity - equity.cummax()
            rows.append(
                {
                    "cost_bps": total_cost,
                    "mode": mode,
                    "trades": int(len(trades)),
                    "win_rate": float((pnl > 0.0).mean()),
                    "profit_factor": float(wins / losses) if losses > 0 else float("inf"),
                    "avg_net_bps": float(adj_net_bps.mean()),
                    "pnl_dollars": float(pnl.sum()),
                    "max_drawdown": float(drawdown.min()) if len(drawdown) else 0.0,
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(output_dir / "cost_sensitivity.csv", index=False)
    return out


def pred_row(label: str, summary: dict) -> str:
    metric = next((x for x in summary["prediction_metrics"] if x["segment"] == "overall" and x["ticker"] == "ALL"), {})
    return (
        f"| {label} | {metric.get('rows', 0)} | "
        f"{fmt_float(metric.get('rmse', float('nan')))} | {fmt_float(metric.get('mae', float('nan')))} | "
        f"{fmt_float(metric.get('spearman_return', float('nan')))} | "
        f"{fmt_float(metric.get('top_quintile_return_bps', float('nan')), 2)} | "
        f"{fmt_float(metric.get('bottom_quintile_return_bps', float('nan')), 2)} |"
    )


def trade_row(label: str, summary: dict) -> str:
    metric = summary["trade_metrics"].get("overall", {})
    return (
        f"| {label} | {metric.get('trades', 0)} | {fmt_pct(metric.get('win_rate', float('nan')))} | "
        f"{fmt_float(metric.get('profit_factor', float('nan')))} | "
        f"{fmt_float(metric.get('avg_net_bps', float('nan')), 2)} | "
        f"{fmt_money(metric.get('pnl_dollars', 0.0))} | "
        f"{fmt_money(metric.get('max_drawdown', 0.0))} | "
        f"{fmt_pct(metric.get('long_rate', float('nan')))} |"
    )


def write_summary(output_dir: Path, summaries: dict[str, dict], cost_df: pd.DataFrame, args, raw_rows: int, valid_rows: int) -> None:
    label_text = (
        f"spot_price(min(t+{args.horizon_steps * 5}m, same-day last row)) > spot_price(t)"
        if args.truncate_eod_horizon
        else f"spot_price(t+{args.horizon_steps * 5}m) > spot_price(t)"
    )
    row_text = "max/EOD-truncated 180m" if args.truncate_eod_horizon else "exact 180m"
    backtest_text = "max 180m hold truncated to same-day last row" if args.truncate_eod_horizon else "fixed 180m hold"
    lines = [
        "# Frozen Base+JEPA 180m Candidate",
        "",
        f"Data: `{args.data}`",
        f"Rows after {row_text} label construction: {valid_rows:,} from {raw_rows:,}",
        f"Train cutoff: `{normalize_date(args.train_end_date)}`",
        f"Test start: `{normalize_date(args.test_start_date)}`",
        f"Label: `{label_text}`",
        f"Backtest: {backtest_text}, cooldown `{args.cooldown_steps}` samples, base cost `{args.cost_bps}` bps, notional `${args.notional:,.0f}`.",
        "",
        "## Prediction Metrics",
        "",
        "| Mode | Rows | RMSE | MAE | Spearman Ret | Top Q Ret bps | Bottom Q Ret bps |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode, summary in summaries.items():
        lines.append(pred_row(mode, summary))

    lines += [
        "",
        "## Fixed-Hold 180m Backtest",
        "",
        "| Mode | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode, summary in summaries.items():
        lines.append(trade_row(mode, summary))

    lines += [
        "",
        "## Cost Sensitivity",
        "",
        "| Cost | Mode | Trades | WR | PF | Avg bps | PnL | Max DD |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in cost_df.itertuples(index=False):
        lines.append(
            f"| {fmt_float(row.cost_bps, 0)} bps | {row.mode} | {row.trades} | "
            f"{fmt_pct(row.win_rate)} | {fmt_float(row.profit_factor)} | "
            f"{fmt_float(row.avg_net_bps, 2)} | {fmt_money(row.pnl_dollars)} | {fmt_money(row.max_drawdown)} |"
        )

    lines += [
        "",
        "## Decision",
        "",
        "- This is the strict frozen-candidate test: all OOS predictions use models trained only through the cutoff.",
        "- `future_return_180m` is used only for labels/backtest outcome and is excluded from features.",
        "- If `base_jepa` beats `base` here, it is a credible replacement candidate for the current 180m entry model; if it fails, the monthly-retrained result was too optimistic.",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Train frozen 180m direction models and backtest after cutoff.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--jepa-feature-names", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--modes", nargs="+", default=["base", "jepa_only", "base_jepa"])
    parser.add_argument("--train-end-date", default="20260331")
    parser.add_argument("--test-start-date", default="20260401")
    parser.add_argument("--test-end-date", default=None)
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--min-abs-bps", type=float, default=0.0)
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--cost-bps", type=float, default=1.0)
    parser.add_argument("--cooldown-steps", type=int, default=36)
    parser.add_argument("--notional", type=float, default=100000.0)
    parser.add_argument("--min-val-trades", type=int, default=4)
    parser.add_argument("--seed", type=int, default=777)
    parser.add_argument("--n-estimators", type=int, default=180)
    parser.add_argument("--n-jobs", type=int, default=20)
    parser.add_argument(
        "--truncate-eod-horizon",
        action="store_true",
        help="Use min(entry + horizon, last same-day row) as labels/outcomes, matching live EOD cleanup.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = len(pd.read_parquet(args.data, columns=["ticker"]))
    df = build_terminal_180m_frame(
        args.data,
        args.horizon_steps,
        args.min_abs_bps,
        truncate_to_eod=args.truncate_eod_horizon,
    )
    summaries = {}
    for mode in args.modes:
        result = run_frozen_mode(df, args, mode, model_dir)
        summaries[mode] = write_mode_outputs(
            result,
            output_dir,
            normalize_date(args.test_start_date),
            args.cost_bps,
            args.cooldown_steps,
            args.notional,
        )
    cost_df = cost_sensitivity(output_dir, args.modes, args.cost_bps, args.notional)
    payload = {
        "config": vars(args),
        "raw_rows": raw_rows,
        "valid_rows": int(len(df)),
        "summaries": summaries,
        "cost_sensitivity": cost_df.to_dict(orient="records"),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(output_dir, summaries, cost_df, args, raw_rows, len(df))
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
