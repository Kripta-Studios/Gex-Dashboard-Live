from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.evaluate_180m_direction import (
    build_terminal_180m_frame,
    fmt_float,
    fmt_money,
    fmt_pct,
    trade_metrics,
)
from neural.jepa.jepa_180m_signal import Jepa180mSignalModel, normalize_ticker


def normalize_date(value) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else str(value)


def time_to_minutes(value) -> int:
    try:
        text = str(value)[:5]
        hour, minute = text.split(":")
        return int(hour) * 60 + int(minute)
    except Exception:
        return 0


def apply_cooldown(signals: pd.DataFrame, cooldown_steps: int) -> pd.DataFrame:
    if signals.empty:
        return signals
    signals = signals.sort_values(["ticker", "date", "pos_in_day"]).reset_index(drop=True)
    kept = []
    next_allowed: dict[tuple[str, str], int] = {}
    for row in signals.itertuples(index=False):
        key = (str(row.ticker), str(row.date))
        pos = int(row.pos_in_day)
        if cooldown_steps > 0 and pos < next_allowed.get(key, -1):
            continue
        kept.append(row._asdict())
        next_allowed[key] = pos + int(cooldown_steps)
    return pd.DataFrame(kept)


def build_trades(predictions: pd.DataFrame, cost_bps: float, cooldown_steps: int, notional: float) -> pd.DataFrame:
    signals = predictions[predictions["jepa180_direction"].astype(int) != 0].copy()
    signals = apply_cooldown(signals, cooldown_steps)
    if signals.empty:
        return pd.DataFrame()
    signals["side"] = np.where(signals["jepa180_direction"].astype(int) > 0, "LONG", "SHORT")
    signals["gross_bps"] = signals["jepa180_direction"].astype(float) * signals["future_return_bps_180m"].astype(float)
    signals["net_bps"] = signals["gross_bps"] - float(cost_bps)
    signals["pnl_dollars"] = signals["net_bps"] / 10000.0 * float(notional)
    keep = [
        "ticker",
        "date",
        "time",
        "side",
        "jepa180_prob_up",
        "jepa180_confidence",
        "jepa180_long_threshold",
        "jepa180_short_threshold",
        "spot_price",
        "future_return_bps_180m",
        "gross_bps",
        "net_bps",
        "pnl_dollars",
    ]
    return signals[keep].rename(columns={"future_return_bps_180m": "future_return_bps"})


def per_ticker_metrics(trades: pd.DataFrame) -> dict[str, dict]:
    if trades.empty:
        return {}
    return {str(ticker): trade_metrics(frame) for ticker, frame in trades.groupby("ticker", sort=True)}


def cost_sensitivity(trades: pd.DataFrame, base_cost_bps: float, notional: float) -> list[dict]:
    rows = []
    if trades.empty:
        return rows
    for total_cost in [1.0, 3.0, 5.0, 10.0]:
        adjusted = trades.copy()
        adjusted["net_bps"] = adjusted["net_bps"].astype(float) - (float(total_cost) - float(base_cost_bps))
        adjusted["pnl_dollars"] = adjusted["net_bps"] / 10000.0 * float(notional)
        metrics = trade_metrics(adjusted)
        metrics["cost_bps"] = float(total_cost)
        rows.append(metrics)
    return rows


def metrics_row(label: str, metrics: dict) -> str:
    return (
        f"| {label} | {metrics.get('trades', 0)} | {fmt_pct(metrics.get('win_rate', float('nan')))} | "
        f"{fmt_float(metrics.get('profit_factor', float('nan')))} | "
        f"{fmt_float(metrics.get('avg_net_bps', float('nan')), 2)} | "
        f"{fmt_money(metrics.get('pnl_dollars', 0.0))} | "
        f"{fmt_money(metrics.get('max_drawdown', 0.0))} | "
        f"{fmt_pct(metrics.get('long_rate', float('nan')))} |"
    )


def write_report(
    output_dir: Path,
    args,
    model: Jepa180mSignalModel,
    predictions: pd.DataFrame,
    trades: pd.DataFrame,
    summary: dict,
) -> None:
    lines = [
        "# JEPA 180m Standalone Backtest",
        "",
        f"Data: `{args.data}`",
        f"Model dir: `{args.model_dir}`",
        f"Mode: `{args.mode}`",
        f"Rows scored: {len(predictions):,}",
        f"Execution: fixed `{args.horizon_steps * 5}`m hold, cooldown `{args.cooldown_minutes}`m, cost `{args.cost_bps}` bps, notional `${args.notional:,.0f}`.",
        "",
        "## Overall",
        "",
        "| Scope | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        metrics_row("all", summary["overall"]),
        "",
        "## Per Ticker",
        "",
        "| Ticker | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for ticker, metrics in summary["per_ticker"].items():
        lines.append(metrics_row(ticker, metrics))

    lines += [
        "",
        "## Cost Sensitivity",
        "",
        "| Cost | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for metrics in summary["cost_sensitivity"]:
        lines.append(
            f"| {fmt_float(metrics['cost_bps'], 0)} bps | {metrics.get('trades', 0)} | "
            f"{fmt_pct(metrics.get('win_rate', float('nan')))} | "
            f"{fmt_float(metrics.get('profit_factor', float('nan')))} | "
            f"{fmt_float(metrics.get('avg_net_bps', float('nan')), 2)} | "
            f"{fmt_money(metrics.get('pnl_dollars', 0.0))} | "
            f"{fmt_money(metrics.get('max_drawdown', 0.0))} | "
            f"{fmt_pct(metrics.get('long_rate', float('nan')))} |"
        )

    lines += [
        "",
        "## Model Thresholds",
        "",
        "```json",
        json.dumps(model.metadata()["tickers"], indent=2, allow_nan=True),
        "```",
        "",
        "## Cooldown Note",
        "",
        "- The default cooldown is 180m because the label and execution horizon are 180m.",
        "- This prevents stacking many overlapping 5-minute entries that mostly bet on the same future window.",
        "- The value is configurable with `--cooldown-minutes` for sensitivity testing.",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Standalone backtest for frozen JEPA 180m signal artifacts.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--mode", default="base_jepa")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-date", default="20260401")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--tickers", nargs="*", default=["SPX", "QQQ", "SPY"])
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--cooldown-minutes", type=int, default=180)
    parser.add_argument("--cost-bps", type=float, default=1.0)
    parser.add_argument("--notional", type=float, default=100000.0)
    parser.add_argument("--min-entry-minute", type=int, default=None)
    parser.add_argument("--max-entry-minute", type=int, default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cooldown_steps = max(0, int(round(args.cooldown_minutes / 5.0)))

    df = build_terminal_180m_frame(args.data, args.horizon_steps, min_abs_bps=0.0)
    df["ticker"] = df["ticker"].map(normalize_ticker)
    df["date"] = df["date"].map(normalize_date)
    if args.start_date:
        df = df[df["date"] >= normalize_date(args.start_date)].copy()
    if args.end_date:
        df = df[df["date"] <= normalize_date(args.end_date)].copy()
    if args.tickers:
        allowed = {normalize_ticker(t) for t in args.tickers}
        df = df[df["ticker"].isin(allowed)].copy()
    if args.min_entry_minute is not None or args.max_entry_minute is not None:
        minutes = df["time"].map(time_to_minutes)
        if args.min_entry_minute is not None:
            df = df[minutes >= int(args.min_entry_minute)].copy()
            minutes = df["time"].map(time_to_minutes)
        if args.max_entry_minute is not None:
            df = df[minutes <= int(args.max_entry_minute)].copy()

    model = Jepa180mSignalModel(args.model_dir, args.mode, tickers=args.tickers)
    predictions = model.predict_frame(df)
    trades = build_trades(predictions, args.cost_bps, cooldown_steps, args.notional)
    summary = {
        "config": vars(args) | {"cooldown_steps": cooldown_steps},
        "overall": trade_metrics(trades),
        "per_ticker": per_ticker_metrics(trades),
        "cost_sensitivity": cost_sensitivity(trades, args.cost_bps, args.notional),
        "model_metadata": model.metadata(),
    }

    predictions.to_csv(output_dir / "predictions.csv", index=False)
    trades.to_csv(output_dir / "trades.csv", index=False)
    (output_dir / "metrics.json").write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")
    write_report(output_dir, args, model, predictions, trades, summary)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
