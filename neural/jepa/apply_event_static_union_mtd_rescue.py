from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from apply_event_static_union_cooldown import (
    apply_static_union,
    audit_folds,
    load_fold_file,
    load_trade_source,
    write_plot,
)
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


def add_base_prior_mtd(all_trades: pd.DataFrame, base_selected: pd.DataFrame) -> pd.DataFrame:
    work = all_trades.copy()
    if base_selected.empty:
        work["base_prior_mtd_return"] = 0.0
        return work

    daily = (
        base_selected.assign(month=base_selected["month"].astype(str), date=base_selected["date"].astype(str))
        .groupby(["month", "date"], as_index=False)["realized_return"]
        .sum()
        .sort_values(["month", "date"], kind="stable")
    )
    by_month = {month: group for month, group in daily.groupby("month", sort=False)}

    def prior_mtd(month: str, date: str) -> float:
        group = by_month.get(str(month))
        if group is None:
            return 0.0
        prev = group[group["date"].astype(str) < str(date)]
        if prev.empty:
            return 0.0
        return float(prev["realized_return"].sum())

    work["base_prior_mtd_return"] = [
        prior_mtd(month, date)
        for month, date in zip(work["month"].astype(str), work["date"].astype(str), strict=False)
    ]
    return work


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, args: argparse.Namespace) -> None:
    months = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, months)
    monthly_rows: list[dict] = []
    for month in months:
        row = metrics(trades[trades["month"].astype(str).eq(month)].copy(), [month])
        row["month"] = month
        row["pnl_dollars"] = float(row["pnl_return"]) * float(args.risk_capital)
        monthly_rows.append(row)

    payload = {
        "overall": overall,
        "monthly": monthly_rows,
        "risk_capital": float(args.risk_capital),
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "integrity": audit_folds(folds, months),
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")

    lines = [
        "# Event Static Union MTD Rescue",
        "",
        "This artifact combines base causal OOS streams with fixed priority, then enables rescue streams only when the base stream's prior completed-day month-to-date return is below or equal to the configured threshold. It does not rank a completed evaluation month.",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        f"- Risk capital: ${float(args.risk_capital):,.0f}",
        f"- Net PnL: ${payload['net_pnl']:,.0f}",
        f"- Rescue trigger: base prior completed-day MTD <= {float(args.trigger_threshold):.3f}R",
        "",
        "## Monthly",
        "",
        "| Month | Trades | WR | PF | PnL Return | PnL $ |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in monthly_rows:
        lines.append(
            f"| {row['month']} | {int(row['trades'])} | {float(row['win_rate']):.1%} | "
            f"{float(row['profit_factor']):.3f} | {float(row['pnl_return']):.3f} | "
            f"{float(row['pnl_dollars']):,.0f} |"
        )
    lines += [
        "",
        "## Integrity",
        "",
        "```json",
        json.dumps(payload["integrity"], indent=2, allow_nan=True),
        "```",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(vars(args), indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply a fixed-priority static union with prior-MTD rescue sources."
    )
    parser.add_argument("--base-source", action="append", required=True, help="NAME=trade_csv_or_result_dir. Repeatable; order defines base priority.")
    parser.add_argument("--rescue-source", action="append", required=True, help="NAME=trade_csv_or_result_dir. Repeatable; order defines rescue priority after base.")
    parser.add_argument("--fold-file", action="append", default=[], help="NAME=fold_csv. Repeatable, used only for integrity audit.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--max-day", type=int, default=4)
    parser.add_argument("--cooldown-minutes", type=int, default=45)
    parser.add_argument("--trigger-threshold", type=float, default=0.0)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    months = month_range(str(args.start_month), str(args.end_month))

    base_parts = [
        load_trade_source(item, str(args.ticker), idx)
        for idx, item in enumerate(args.base_source)
    ]
    rescue_offset = len(base_parts)
    rescue_parts = [
        load_trade_source(item, str(args.ticker), rescue_offset + idx)
        for idx, item in enumerate(args.rescue_source)
    ]
    base_parts = [part for part in base_parts if not part.empty]
    rescue_parts = [part for part in rescue_parts if not part.empty]
    if not base_parts:
        raise RuntimeError("No base trades after ticker filtering.")
    if not rescue_parts:
        raise RuntimeError("No rescue trades after ticker filtering.")

    base_trades = pd.concat(base_parts, ignore_index=True, sort=False)
    rescue_trades = pd.concat(rescue_parts, ignore_index=True, sort=False)
    base_trades = base_trades[base_trades["month"].astype(str).isin(months)].copy()
    rescue_trades = rescue_trades[rescue_trades["month"].astype(str).isin(months)].copy()
    base_selected = apply_static_union(base_trades, int(args.max_day), int(args.cooldown_minutes))

    all_trades = pd.concat([base_trades, rescue_trades], ignore_index=True, sort=False)
    all_trades = add_base_prior_mtd(all_trades, base_selected)
    base_names = set(base_trades["static_source"].astype(str).unique())
    all_trades["mtd_rescue_active"] = all_trades["base_prior_mtd_return"] <= float(args.trigger_threshold)
    keep = all_trades["static_source"].astype(str).isin(base_names) | all_trades["mtd_rescue_active"]
    selected = apply_static_union(all_trades[keep].copy(), int(args.max_day), int(args.cooldown_minutes))
    selected["mtd_rescue_trigger_threshold"] = float(args.trigger_threshold)
    selected = selected.sort_values(["date", "entry_minute", "ticker", "static_source"], kind="stable").reset_index(drop=True)
    selected.to_csv(output_dir / "mtd_rescue_trades.csv", index=False)
    selected.to_csv(output_dir / "combined_trades.csv", index=False)

    folds = pd.concat([load_fold_file(item) for item in args.fold_file], ignore_index=True, sort=False) if args.fold_file else pd.DataFrame()
    if not folds.empty:
        folds.to_csv(output_dir / "mtd_rescue_folds.csv", index=False)
        folds.to_csv(output_dir / "combined_folds.csv", index=False)
    write_plot(output_dir, selected, float(args.risk_capital))
    write_summary(output_dir, selected, folds, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
