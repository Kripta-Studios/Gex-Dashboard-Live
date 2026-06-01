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
    predict_proba,
    select_features,
    simulate_hold180,
    summarize_predictions,
    trade_metrics,
    train_model,
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


def run_production_mode(df: pd.DataFrame, args, mode: str, model_dir: Path) -> ModeResult:
    features = select_features(df, mode, args.jepa_feature_names)
    train_end = normalize_date(args.train_end_date)
    eligible = df[df["date"] <= train_end].copy()
    if eligible.empty:
        raise ValueError(f"No eligible rows for production training cutoff <= {train_end}")

    predictions = []
    trades = []
    windows = []
    max_data_date = str(eligible["date"].max())
    min_data_date = str(eligible["date"].min())

    for ticker in sorted(eligible["ticker"].astype(str).unique().tolist()):
        ticker_df = eligible[eligible["ticker"].astype(str) == ticker].copy()
        if ticker_df.empty or ticker_df["future_up_180m"].nunique() < 2:
            print(f"[JEPA_180M_PRODUCTION] skip mode={mode} ticker={ticker} insufficient classes", flush=True)
            continue

        months = sorted(ticker_df["month"].unique().tolist())
        val_keys = months[-args.val_months :] if args.val_months > 0 else months[-1:]
        fit = ticker_df[~ticker_df["month"].isin(val_keys)].copy()
        val = ticker_df[ticker_df["month"].isin(val_keys)].copy()
        if fit.empty or fit["future_up_180m"].nunique() < 2 or val.empty:
            fit = ticker_df.copy()
            val = ticker_df.tail(min(len(ticker_df), max(200, len(ticker_df) // 5))).copy()

        print(
            f"[JEPA_180M_PRODUCTION] mode={mode} ticker={ticker} "
            f"rows={len(ticker_df)} fit_rows={len(fit)} val_rows={len(val)} "
            f"data={min_data_date}..{max_data_date}",
            flush=True,
        )

        val_model, val_medians = train_model(fit, features, args.seed, args.n_estimators, args.n_jobs)
        val_prob = predict_proba(val_model, val, features, val_medians)
        thresholds = choose_thresholds(
            val,
            val_prob,
            args.cost_bps,
            args.cooldown_steps,
            args.notional,
            args.min_val_trades,
        )

        model, medians = train_model(ticker_df, features, args.seed, args.n_estimators, args.n_jobs)
        prob = predict_proba(model, ticker_df, features, medians)
        pred_frame = ticker_df[
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
        pred_frame["feature_mode"] = mode
        pred_frame["prob_up"] = prob
        pred_frame["pred_up"] = (prob >= 0.5).astype(np.int8)
        predictions.append(pred_frame)

        mode_trades = simulate_hold180(
            ticker_df,
            prob,
            thresholds["long_threshold"],
            thresholds["short_threshold"],
            args.cost_bps,
            args.cooldown_steps,
            args.notional,
        )
        if not mode_trades.empty:
            mode_trades["feature_mode"] = mode
            mode_trades["production_diagnostic"] = True
            trades.append(mode_trades)

        meta = {
            "mode": mode,
            "ticker": ticker,
            "production_train": True,
            "oos_valid": False,
            "warning": "Final production artifact trained on all eligible rows; metrics are model-history diagnostics, not OOS validation.",
            "train_end_date": train_end,
            "min_data_date": min_data_date,
            "max_data_date": max_data_date,
            "feature_count": len(features),
            "horizon_steps": args.horizon_steps,
            "horizon_minutes": args.horizon_steps * 5,
            "cost_bps": args.cost_bps,
            "cooldown_steps": args.cooldown_steps,
            "notional": args.notional,
            "threshold_validation_months": val_keys,
        }
        save_model_artifact(model_dir / mode / f"{ticker}.joblib", model, medians, features, thresholds, meta)
        windows.append(
            {
                "feature_mode": mode,
                "ticker": ticker,
                "production_train": True,
                "oos_valid": False,
                "train_end_date": train_end,
                "min_data_date": min_data_date,
                "max_data_date": max_data_date,
                "train_rows": int(len(ticker_df)),
                "fit_rows": int(len(fit)),
                "threshold_val_rows": int(len(val)),
                "threshold_val_months": ",".join(str(x) for x in val_keys),
                "feature_count": int(len(features)),
                **thresholds,
            }
        )

    pred_all = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    trade_all = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    if not pred_all.empty:
        pred_all.attrs["trades"] = trade_all
    return ModeResult(mode, pred_all, windows, features)


def write_mode_outputs(result: ModeResult, output_dir: Path, args) -> dict:
    trades = result.predictions.attrs.get("trades", pd.DataFrame())
    result.predictions.to_csv(output_dir / f"{result.feature_mode}_production_predictions.csv", index=False)
    trades.to_csv(output_dir / f"{result.feature_mode}_production_trades.csv", index=False)
    pd.DataFrame(result.windows).to_csv(output_dir / f"{result.feature_mode}_production_windows.csv", index=False)
    (output_dir / f"{result.feature_mode}_production_features.json").write_text(
        json.dumps(
            {
                "feature_mode": result.feature_mode,
                "feature_count": len(result.features),
                "feature_names": result.features,
                "production_train": True,
                "oos_valid": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    summary = summarize_predictions(result.predictions, trades, "99999999")
    summary.update(
        {
            "feature_mode": result.feature_mode,
            "feature_count": len(result.features),
            "cost_bps": args.cost_bps,
            "cooldown_steps": args.cooldown_steps,
            "notional": args.notional,
            "production_train": True,
            "oos_valid": False,
            "windows": result.windows,
        }
    )
    (output_dir / f"{result.feature_mode}_production_metrics.json").write_text(
        json.dumps(summary, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    return summary


def cost_sensitivity(output_dir: Path, modes: list[str], base_cost_bps: float, notional: float) -> pd.DataFrame:
    rows = []
    for total_cost in [1.0, 3.0, 5.0, 10.0]:
        extra_cost = total_cost - base_cost_bps
        for mode in modes:
            path = output_dir / f"{mode}_production_trades.csv"
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
    out.to_csv(output_dir / "production_cost_sensitivity.csv", index=False)
    return out


def pred_row(label: str, summary: dict) -> str:
    metric = next((x for x in summary["prediction_metrics"] if x["segment"] == "overall" and x["ticker"] == "ALL"), {})
    return (
        f"| {label} | {metric.get('rows', 0)} | {fmt_pct(metric.get('future_up_rate', float('nan')))} | "
        f"{fmt_pct(metric.get('pred_up_rate', float('nan')))} | {fmt_float(metric.get('auc', float('nan')))} | "
        f"{fmt_pct(metric.get('accuracy', float('nan')))} | {fmt_pct(metric.get('balanced_accuracy', float('nan')))} | "
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
    lines = [
        "# Production Base+JEPA 180m Artifacts",
        "",
        f"Data: `{args.data}`",
        f"Rows after exact 180m label construction: {valid_rows:,} from {raw_rows:,}",
        f"Production cutoff: `{normalize_date(args.train_end_date)}`",
        f"Label: `spot_price(t+{args.horizon_steps * 5}m) > spot_price(t)`",
        f"Backtest diagnostic: fixed 180m hold, cooldown `{args.cooldown_steps}` samples, base cost `{args.cost_bps}` bps, notional `${args.notional:,.0f}`.",
        "",
        "## Important",
        "",
        "- These are final production artifacts trained on all eligible rows up to the cutoff.",
        "- The metrics below are model-history diagnostics only. They are not OOS validation and must not be used as a promotion claim.",
        "- The OOS evidence remains the locked research pipeline that trained through March 2026 and tested April/May 2026.",
        "- `future_return_180m` and derived columns are labels/outcomes only and are excluded from model features.",
        "",
        "## Prediction Diagnostics",
        "",
        "| Mode | Rows | Future Up | Pred Up | AUC | Acc | Bal Acc | Spearman Ret | Top Q Ret bps | Bottom Q Ret bps |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode, summary in summaries.items():
        lines.append(pred_row(mode, summary))

    lines += [
        "",
        "## Fixed-Hold 180m Diagnostic",
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
        "## Artifacts",
        "",
        f"- Model directory: `{args.model_dir}`",
        f"- Modes: `{', '.join(args.modes)}`",
        "- Live bot uses the `base_jepa` mode.",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Train final production 180m direction artifacts on all eligible data.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--jepa-feature-names", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--modes", nargs="+", default=["base", "jepa_only", "base_jepa"])
    parser.add_argument("--train-end-date", default="20261230")
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--min-abs-bps", type=float, default=0.0)
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--cost-bps", type=float, default=1.0)
    parser.add_argument("--cooldown-steps", type=int, default=36)
    parser.add_argument("--notional", type=float, default=100000.0)
    parser.add_argument("--min-val-trades", type=int, default=4)
    parser.add_argument("--seed", type=int, default=777)
    parser.add_argument("--n-estimators", type=int, default=180)
    parser.add_argument("--n-jobs", type=int, default=1)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = len(pd.read_parquet(args.data, columns=["ticker"]))
    df = build_terminal_180m_frame(args.data, args.horizon_steps, args.min_abs_bps)
    train_end = normalize_date(args.train_end_date)
    df = df[df["date"] <= train_end].copy()
    if df.empty:
        raise ValueError(f"No rows remain after production train cutoff <= {train_end}")

    summaries = {}
    for mode in args.modes:
        result = run_production_mode(df, args, mode, model_dir)
        summaries[mode] = write_mode_outputs(result, output_dir, args)

    cost_df = cost_sensitivity(output_dir, args.modes, args.cost_bps, args.notional)
    payload = {
        "config": vars(args),
        "raw_rows": raw_rows,
        "valid_rows": int(len(df)),
        "production_train": True,
        "oos_valid": False,
        "summaries": summaries,
        "cost_sensitivity": cost_df.to_dict(orient="records"),
    }
    (output_dir / "production_metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(output_dir, summaries, cost_df, args, raw_rows, len(df))
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
