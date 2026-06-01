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

from neural.jepa.evaluate_180m_direction import build_terminal_180m_frame, fmt_float, fmt_money, fmt_pct, trade_metrics


def normalize_date(value) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else str(value)


def normalize_time(value) -> str:
    text = str(value)
    if " " in text:
        text = text.split()[-1]
    return text[:5]


def side_sign(value: str) -> int:
    text = str(value).upper()
    if "LONG" in text:
        return 1
    if "SHORT" in text:
        return -1
    return 0


def apply_180m_cooldown(trades: pd.DataFrame, cooldown_steps: int) -> pd.DataFrame:
    if trades.empty:
        return trades
    trades = trades.sort_values(["ticker", "date", "pos_in_day"]).reset_index(drop=True)
    kept = []
    next_allowed: dict[tuple[str, str], int] = {}
    for row in trades.itertuples(index=False):
        key = (str(row.ticker), str(row.date))
        pos = int(row.pos_in_day)
        if pos < next_allowed.get(key, -1):
            continue
        kept.append(row._asdict())
        next_allowed[key] = pos + int(cooldown_steps)
    return pd.DataFrame(kept)


def recompute_hold180(
    labels: pd.DataFrame,
    trade_path: Path,
    label: str,
    cost_bps: float,
    cooldown_steps: int,
    notional: float,
) -> tuple[pd.DataFrame, dict]:
    trades = pd.read_csv(trade_path)
    if trades.empty:
        return trades, {"label": label, "missing_rate": 1.0, **trade_metrics(pd.DataFrame())}

    row_features = labels[
        ["ticker", "date", "time", "pos_in_day", "spot_price", "future_return_bps_180m"]
    ].copy()
    row_features["_date_key"] = row_features["date"].map(normalize_date)
    row_features["_time_key"] = row_features["time"].map(normalize_time)
    row_features["_ticker_key"] = row_features["ticker"].astype(str)

    trades["_date_key"] = trades["date"].map(normalize_date)
    trades["_time_key"] = trades["entry_time"].map(normalize_time)
    trades["_ticker_key"] = trades["ticker"].astype(str)
    merged = trades.merge(row_features, on=["_ticker_key", "_date_key", "_time_key"], how="left", suffixes=("", "_row"))
    missing_rate = float(merged["future_return_bps_180m"].isna().mean())
    merged = merged.dropna(subset=["future_return_bps_180m", "pos_in_day"]).copy()
    merged["side_sign"] = merged["direction"].map(side_sign)
    merged = merged[merged["side_sign"] != 0].copy()
    merged["ticker"] = merged["_ticker_key"]
    merged["date"] = merged["_date_key"]
    merged["time"] = merged["_time_key"]
    merged["gross_bps"] = merged["side_sign"].astype(float) * merged["future_return_bps_180m"].astype(float)
    merged["net_bps"] = merged["gross_bps"] - float(cost_bps)
    merged["pnl_dollars"] = merged["net_bps"] / 10000.0 * float(notional)
    merged["side"] = np.where(merged["side_sign"] > 0, "LONG", "SHORT")
    merged = apply_180m_cooldown(merged, cooldown_steps)
    metrics = trade_metrics(merged)
    metrics.update({"label": label, "missing_rate": missing_rate, "input_trades": int(len(trades))})
    return merged, metrics


def sensitivity_rows(base_trades: dict[str, pd.DataFrame], base_cost_bps: float, notional: float) -> list[dict]:
    rows = []
    for total_cost in [1.0, 3.0, 5.0, 10.0]:
        extra = total_cost - base_cost_bps
        for label, trades in base_trades.items():
            if trades.empty:
                continue
            adjusted = trades.copy()
            adjusted["net_bps"] = adjusted["net_bps"].astype(float) - extra
            adjusted["pnl_dollars"] = adjusted["net_bps"] / 10000.0 * notional
            m = trade_metrics(adjusted)
            m.update({"label": label, "cost_bps": total_cost})
            rows.append(m)
    return rows


def row_md(label: str, metrics: dict) -> str:
    return (
        f"| {label} | {metrics.get('input_trades', 0)} | {metrics.get('trades', 0)} | "
        f"{fmt_pct(metrics.get('win_rate', float('nan')))} | {fmt_float(metrics.get('profit_factor', float('nan')))} | "
        f"{fmt_float(metrics.get('avg_net_bps', float('nan')), 2)} | {fmt_money(metrics.get('pnl_dollars', 0.0))} | "
        f"{fmt_money(metrics.get('max_drawdown', 0.0))} | {fmt_pct(metrics.get('long_rate', float('nan')))} |"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute existing entry signals under fixed 180m hold.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--trades", nargs="+", required=True, help="label=path pairs")
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--cost-bps", type=float, default=1.0)
    parser.add_argument("--cooldown-steps", type=int, default=36)
    parser.add_argument("--notional", type=float, default=100000.0)
    args = parser.parse_args()

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    labels = build_terminal_180m_frame(args.data, args.horizon_steps, min_abs_bps=0.0)
    metrics = []
    trade_frames = {}
    for item in args.trades:
        if "=" not in item:
            raise ValueError(f"Expected label=path, got {item!r}")
        label, raw_path = item.split("=", 1)
        frame, m = recompute_hold180(labels, Path(raw_path), label, args.cost_bps, args.cooldown_steps, args.notional)
        frame.to_csv(output / f"{label}_fixed180_trades.csv", index=False)
        metrics.append(m)
        trade_frames[label] = frame

    sensitivity = sensitivity_rows(trade_frames, args.cost_bps, args.notional)
    pd.DataFrame(metrics).to_csv(output / "existing_signal_fixed180_metrics.csv", index=False)
    pd.DataFrame(sensitivity).to_csv(output / "existing_signal_cost_sensitivity.csv", index=False)

    lines = [
        "# Existing Signals Under Fixed 180m Hold",
        "",
        f"Data: `{args.data}`",
        f"Backtest: fixed 180m hold, cooldown `{args.cooldown_steps}` samples, cost `{args.cost_bps}` bps, notional `${args.notional:,.0f}`.",
        "",
        "| Signal | Input Trades | Fixed-180 Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for m in metrics:
        lines.append(row_md(m["label"], m))

    lines += [
        "",
        "## Cost Sensitivity",
        "",
        "| Cost | Signal | Trades | WR | PF | Avg bps | PnL | Max DD |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sensitivity:
        lines.append(
            f"| {fmt_float(row['cost_bps'], 0)} bps | {row['label']} | {row['trades']} | "
            f"{fmt_pct(row['win_rate'])} | {fmt_float(row['profit_factor'])} | "
            f"{fmt_float(row['avg_net_bps'], 2)} | {fmt_money(row['pnl_dollars'])} | {fmt_money(row['max_drawdown'])} |"
        )
    lines.append("")
    (output / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (output / "metrics.json").write_text(
        json.dumps({"metrics": metrics, "cost_sensitivity": sensitivity}, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    print((output / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
