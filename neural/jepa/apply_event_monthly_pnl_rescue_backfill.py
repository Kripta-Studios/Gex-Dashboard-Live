from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from apply_event_monthly_volume_backfill import (
    is_partial_month,
    load_trades,
    required_count_by_date,
    target_count_for_month,
    write_plot,
)
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


def read_config_csv(path: Path) -> dict[str, str]:
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError(f"empty config: {path}")
    row = frame.iloc[0].to_dict()
    return {
        "ticker": str(row["ticker"]).upper(),
        "primary_trades": str(row["primary_trades"]),
        "fallback_trades": str(row["fallback_trades"]),
        "primary_name": str(row.get("primary_name", "primary")),
        "fallback_name": str(row.get("fallback_name", "fallback")),
    }


def business_day_index(month: str, date: str) -> int:
    start = pd.Timestamp(year=int(str(month)[:4]), month=int(str(month)[4:6]), day=1)
    end = start + pd.offsets.MonthEnd(0)
    days = pd.bdate_range(start, end)
    current = pd.to_datetime(str(date), format="%Y%m%d", errors="coerce")
    if pd.isna(current):
        return 1
    return max(1, int((days <= current).sum()))


def apply_pnl_rescue_backfill(primary: pd.DataFrame, fallback: pd.DataFrame, args: argparse.Namespace | SimpleNamespace) -> pd.DataFrame:
    months = month_range(str(args.start_month), str(args.end_month))
    frames: list[pd.DataFrame] = []
    primary = primary[primary["month"].astype(str).isin(months)].copy()
    fallback = fallback[fallback["month"].astype(str).isin(months)].copy()
    tickers = sorted(set(primary["ticker"].astype(str).unique()) | set(fallback["ticker"].astype(str).unique()))
    cooldown = int(args.cooldown_minutes)
    max_day = int(args.max_day)
    rescue_threshold = float(args.rescue_pnl_threshold)
    rescue_start_bday = int(args.rescue_start_bday)

    for ticker in tickers:
        p_ticker = primary[primary["ticker"].astype(str).eq(ticker)].copy()
        f_ticker = fallback[fallback["ticker"].astype(str).eq(ticker)].copy()
        for month in months:
            p_month = p_ticker[p_ticker["month"].astype(str).eq(month)].copy()
            f_month = f_ticker[f_ticker["month"].astype(str).eq(month)].copy()
            if p_month.empty and f_month.empty:
                continue

            combined = pd.concat([p_month, f_month], ignore_index=True, sort=False)
            target = target_count_for_month(month, combined["date"], args)
            partial_month = is_partial_month(month, combined["date"])
            combined["_priority"] = np.where(combined["source_stream"].astype(str).eq(str(args.primary_name)), 0, 1)
            combined = combined.sort_values(
                ["date", "entry_minute", "_priority", "score", "_source_order"],
                ascending=[True, True, True, False, True],
                kind="stable",
            )

            selected: list[pd.Series] = []
            selected_keys: set[tuple[str, str, str, str]] = set()
            selected_count = 0
            selected_pnl_closed = 0.0
            current_date = ""
            current_day_pnl = 0.0
            day_counts: dict[str, int] = {}
            next_allowed_by_day: dict[str, int] = {}

            for _, row in combined.iterrows():
                date = str(row["date"])
                if current_date and date != current_date:
                    selected_pnl_closed += current_day_pnl
                    current_day_pnl = 0.0
                if date != current_date:
                    current_date = date

                time = str(row["time"])
                action = str(row["action"])
                expiry_mode = str(row.get("expiry_mode", ""))
                key = (date, time, action, expiry_mode)
                if key in selected_keys:
                    continue
                day_taken = int(day_counts.get(date, 0))
                if day_taken >= max_day:
                    continue
                minute = int(row["entry_minute"])
                if minute < int(next_allowed_by_day.get(date, -1)):
                    continue

                is_primary = str(row["source_stream"]) == str(args.primary_name)
                required = required_count_by_date(month, date, target)
                volume_allowed = selected_count < required
                if bool(getattr(args, "backfill_only_partial_months", False)) and not partial_month:
                    volume_allowed = False
                pnl_rescue_allowed = (
                    business_day_index(month, date) >= rescue_start_bday
                    and selected_pnl_closed <= rescue_threshold
                )
                if (not is_primary) and not (volume_allowed or pnl_rescue_allowed):
                    continue

                out = row.copy()
                out["backfill_required_count"] = required
                out["backfill_count_before"] = selected_count
                out["backfill_month_target"] = target
                out["backfill_partial_month"] = partial_month
                out["pnl_rescue_mtd_return_before"] = float(selected_pnl_closed)
                out["pnl_rescue_threshold"] = float(rescue_threshold)
                out["pnl_rescue_start_bday"] = int(rescue_start_bday)
                if is_primary:
                    mode = "primary"
                elif volume_allowed and pnl_rescue_allowed:
                    mode = "fallback_volume_pace_and_pnl_rescue"
                elif volume_allowed:
                    mode = "fallback_volume_pace"
                else:
                    mode = "fallback_pnl_rescue"
                out["backfill_mode"] = mode
                selected.append(out)
                selected_keys.add(key)
                selected_count += 1
                current_day_pnl += float(row["realized_return"])
                day_counts[date] = day_taken + 1
                next_allowed_by_day[date] = minute + cooldown
            if selected:
                frames.append(pd.DataFrame(selected))

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    return out.sort_values(["date", "entry_minute", "ticker", "source_stream"], kind="stable").reset_index(drop=True)


def write_summary(output_dir: Path, trades: pd.DataFrame, args: argparse.Namespace) -> None:
    months = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, months)
    by_ticker = {ticker: metrics(part, months) for ticker, part in trades.groupby("ticker", sort=True)} if not trades.empty else {}
    by_mode = {mode: metrics(part, months) for mode, part in trades.groupby("backfill_mode", sort=True)} if not trades.empty else {}
    monthly_rows = []
    for ticker, part in trades.groupby("ticker", sort=True):
        for month in months:
            row = metrics(part[part["month"].astype(str).eq(month)].copy(), [month])
            row["ticker"] = ticker
            row["month"] = month
            row["pnl_dollars"] = float(row["pnl_return"]) * float(args.risk_capital)
            monthly_rows.append(row)
    payload: dict[str, Any] = {
        "overall": overall,
        "by_ticker": by_ticker,
        "by_mode": by_mode,
        "monthly": monthly_rows,
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "risk_capital": float(args.risk_capital),
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Monthly PnL Rescue Backfill",
        "",
        "This result adds fallback trades when the month-to-date selected count is behind the deterministic volume pace or when prior completed-day month-to-date return is below a fixed threshold.",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        "## By Ticker",
        "",
        "```json",
        json.dumps(by_ticker, indent=2, allow_nan=True),
        "```",
        "",
        "## By Mode",
        "",
        "```json",
        json.dumps(by_mode, indent=2, allow_nan=True),
        "```",
        "",
        "## Monthly",
        "",
        "| Ticker | Month | Trades | WR | PF | PnL Return | PnL $ |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in monthly_rows:
        lines.append(
            f"| {row['ticker']} | {row['month']} | {int(row['trades'])} | "
            f"{float(row['win_rate']):.1%} | {float(row['profit_factor']):.3f} | "
            f"{float(row['pnl_return']):.3f} | {float(row['pnl_dollars']):,.0f} |"
        )
    lines += [
        "",
        "## Config",
        "",
        "```json",
        json.dumps(vars(args), indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal month-to-date volume + PnL rescue backfill.")
    parser.add_argument("--config-csv", action="append", default=[], help="monthly_volume_backfill_config.csv. Repeat for multi-ticker output.")
    parser.add_argument("--primary-trades", default="")
    parser.add_argument("--fallback-trades", default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--primary-name", default="primary")
    parser.add_argument("--fallback-name", default="fallback")
    parser.add_argument("--ticker", default="")
    parser.add_argument("--start-month", default="202301")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--auto-partial-month-target", action="store_true")
    parser.add_argument("--partial-month-observed-floor", type=int, default=0)
    parser.add_argument("--backfill-only-partial-months", action="store_true")
    parser.add_argument("--max-day", type=int, default=3)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--min-entry-minute", type=int, default=0)
    parser.add_argument("--rescue-pnl-threshold", type=float, default=-1.0)
    parser.add_argument("--rescue-start-bday", type=int, default=5)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_parts: list[pd.DataFrame] = []
    if args.config_csv:
        for item in args.config_csv:
            config = read_config_csv(Path(item))
            local_args = SimpleNamespace(**vars(args))
            local_args.primary_name = config["primary_name"]
            local_args.fallback_name = config["fallback_name"]
            local_args.ticker = config["ticker"]
            primary = load_trades(Path(config["primary_trades"]), config["primary_name"])
            fallback = load_trades(Path(config["fallback_trades"]), config["fallback_name"])
            primary = primary[primary["ticker"].astype(str).str.upper().eq(config["ticker"])].copy()
            fallback = fallback[fallback["ticker"].astype(str).str.upper().eq(config["ticker"])].copy()
            if int(args.min_entry_minute) > 0:
                primary = primary[primary["entry_minute"] >= int(args.min_entry_minute)].copy()
                fallback = fallback[fallback["entry_minute"] >= int(args.min_entry_minute)].copy()
            selected_parts.append(apply_pnl_rescue_backfill(primary, fallback, local_args))
    else:
        if not str(args.primary_trades).strip() or not str(args.fallback_trades).strip():
            raise ValueError("--primary-trades and --fallback-trades are required unless --config-csv is supplied")
        primary = load_trades(Path(args.primary_trades), str(args.primary_name))
        fallback = load_trades(Path(args.fallback_trades), str(args.fallback_name))
        if str(args.ticker).strip():
            ticker = str(args.ticker).upper()
            primary = primary[primary["ticker"].astype(str).str.upper().eq(ticker)].copy()
            fallback = fallback[fallback["ticker"].astype(str).str.upper().eq(ticker)].copy()
        if int(args.min_entry_minute) > 0:
            primary = primary[primary["entry_minute"] >= int(args.min_entry_minute)].copy()
            fallback = fallback[fallback["entry_minute"] >= int(args.min_entry_minute)].copy()
        selected_parts.append(apply_pnl_rescue_backfill(primary, fallback, args))
    selected = pd.concat(selected_parts, ignore_index=True, sort=False) if selected_parts else pd.DataFrame()
    if not selected.empty:
        selected = selected.sort_values(["date", "entry_minute", "ticker", "source_stream"], kind="stable").reset_index(drop=True)
    selected.to_csv(output_dir / "monthly_pnl_rescue_backfill_trades.csv", index=False)
    selected.to_csv(output_dir / "combined_trades.csv", index=False)
    pd.DataFrame([vars(args)]).to_csv(output_dir / "monthly_pnl_rescue_backfill_config.csv", index=False)
    write_plot(output_dir, selected, float(args.risk_capital))
    write_summary(output_dir, selected, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
