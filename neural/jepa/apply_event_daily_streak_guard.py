from __future__ import annotations

import argparse
import json
from pathlib import Path
from shutil import copyfile
from typing import Any

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


def resolve_trade_file(result_dir: Path) -> Path:
    for name in ("combined_trades.csv", "static_union_trades.csv", "trade_union_window_meta_selector_trades.csv"):
        path = result_dir / name
        if path.exists():
            return path
    raise FileNotFoundError(result_dir / "combined_trades.csv")


def resolve_fold_file(result_dir: Path) -> Path | None:
    for name in ("combined_folds.csv", "static_union_folds.csv", "trade_union_window_meta_selector_folds.csv"):
        path = result_dir / name
        if path.exists():
            return path
    return None


def load_trades(path: Path, months: list[str]) -> pd.DataFrame:
    trades = pd.read_csv(path, dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str}, low_memory=False)
    required = {"ticker", "date", "month", "time", "action", "realized_return"}
    missing = sorted(required.difference(trades.columns))
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")
    trades = trades.copy()
    trades["ticker"] = trades["ticker"].astype(str).str.upper()
    trades["date"] = trades["date"].astype(str)
    trades["month"] = trades["month"].astype(str)
    if "test_month" not in trades.columns:
        trades["test_month"] = trades["month"]
    trades["test_month"] = trades["test_month"].astype(str)
    trades["time"] = trades["time"].astype(str)
    trades["realized_return"] = pd.to_numeric(trades["realized_return"], errors="coerce").fillna(0.0)
    trades = trades[trades["month"].isin(months)].copy()
    trades["_guard_original_row"] = np.arange(len(trades), dtype=np.int64)
    return trades.sort_values(["ticker", "date", "time", "_guard_original_row"], kind="stable").reset_index(drop=True)


def business_day_position(month: str, date: str) -> tuple[int, int]:
    start = pd.Timestamp(year=int(month[:4]), month=int(month[4:6]), day=1)
    end = start + pd.offsets.MonthEnd(0)
    days = pd.bdate_range(start, end)
    current = pd.to_datetime(date, format="%Y%m%d", errors="coerce")
    if pd.isna(current):
        return 1, max(1, len(days))
    elapsed = int((days <= current).sum())
    return max(1, elapsed), max(1, len(days))


def required_count_by_date(month: str, date: str, target: int) -> int:
    elapsed, total = business_day_position(month, date)
    return int(np.ceil(float(target) * float(elapsed) / float(total)))


def should_volume_protect(month_counts: dict[str, int], month: str, date: str, target: int) -> tuple[bool, int, int]:
    if int(target) <= 0:
        return False, int(month_counts.get(month, 0)), 0
    count_before = int(month_counts.get(month, 0))
    required = required_count_by_date(month, date, int(target))
    return bool(count_before < required), count_before, required


def apply_guard_to_ticker(trades: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    if trades.empty:
        return trades.copy(), pd.DataFrame()
    kept: list[pd.DataFrame] = []
    decisions: list[dict[str, Any]] = []
    pause_remaining = 0
    loss_streak = 0
    daily_history: list[float] = []
    month_counts: dict[str, int] = {}
    for date, day in trades.groupby("date", sort=True):
        ticker = str(day["ticker"].iloc[0])
        month = str(day["month"].iloc[0])
        if pause_remaining > 0:
            protected, count_before, required = should_volume_protect(
                month_counts,
                month,
                str(date),
                int(getattr(args, "volume_protect_monthly_target", 0) or 0),
            )
            if not protected:
                decisions.append(
                    {
                        "ticker": ticker,
                        "date": str(date),
                        "month": month,
                        "decision": "SKIP_PAUSED",
                        "pause_remaining_before": int(pause_remaining),
                        "loss_streak_before": int(loss_streak),
                        "day_trades": int(len(day)),
                        "day_pnl_return": float(day["realized_return"].sum()),
                        "month_count_before": int(count_before),
                        "month_required_by_date": int(required),
                    }
                )
                pause_remaining -= 1
                continue
            pause_remaining -= 1
            volume_protected = True
        else:
            volume_protected = False

        kept.append(day)
        month_counts[month] = int(month_counts.get(month, 0)) + int(len(day))
        day_pnl = float(day["realized_return"].sum())
        daily_history.append(day_pnl)
        loss_streak_before = loss_streak
        if day_pnl < float(args.loss_threshold):
            loss_streak += 1
        elif day_pnl > 0.0:
            loss_streak = 0

        trigger_reasons: list[str] = []
        if int(args.trigger_losses) > 0 and loss_streak >= int(args.trigger_losses):
            trigger_reasons.append(f"loss_streak>={int(args.trigger_losses)}")
        if int(args.rolling_sum_window) > 0 and len(daily_history) >= int(args.rolling_sum_window):
            rolling_sum = float(sum(daily_history[-int(args.rolling_sum_window) :]))
            if rolling_sum <= float(args.rolling_sum_threshold):
                trigger_reasons.append(f"rolling_sum_{int(args.rolling_sum_window)}<={float(args.rolling_sum_threshold):g}")
        decision = "TRADE_VOLUME_PROTECT" if volume_protected else "TRADE"
        if trigger_reasons:
            pause_remaining = int(args.pause_days)
            loss_streak = 0
            decision = "TRADE_VOLUME_PROTECT_THEN_PAUSE" if volume_protected else "TRADE_THEN_PAUSE"
        protected, count_before, required = should_volume_protect(
            month_counts,
            month,
            str(date),
            int(getattr(args, "volume_protect_monthly_target", 0) or 0),
        )
        decisions.append(
            {
                "ticker": ticker,
                "date": str(date),
                "month": month,
                "decision": decision,
                "trigger_reasons": ",".join(trigger_reasons),
                "pause_days_set": int(pause_remaining),
                "loss_streak_before": int(loss_streak_before),
                "loss_streak_after": int(loss_streak),
                "day_trades": int(len(day)),
                "day_pnl_return": day_pnl,
                "volume_protected": bool(volume_protected),
                "month_count_after": int(month_counts.get(month, 0)),
                "month_count_before_guard_check": int(count_before),
                "month_required_by_date": int(required),
            }
        )
    kept_trades = pd.concat(kept, ignore_index=True, sort=False) if kept else trades.iloc[0:0].copy()
    return kept_trades, pd.DataFrame(decisions)


def monthly_rows(trades: pd.DataFrame, months: list[str], risk_capital: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticker, part in trades.groupby("ticker", sort=True):
        for month in months:
            item = metrics(part[part["month"].astype(str).eq(month)].copy(), [month])
            rows.append({"ticker": ticker, "month": month, **item, "pnl_dollars": float(item["pnl_return"]) * risk_capital})
    return rows


def write_summary(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Event Option Daily Streak Guard",
        "",
        "This artifact applies a causal day-level pause rule to an existing event-option result. The rule only uses realized PnL from prior completed trading days for each ticker.",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(payload["config"], indent=2, allow_nan=True),
        "```",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(payload["overall"], indent=2, allow_nan=True),
        "```",
        "",
        "## By Ticker",
        "",
        "```json",
        json.dumps(payload["by_ticker"], indent=2, allow_nan=True),
        "```",
        "",
        "## Monthly",
        "",
        "| Ticker | Month | Trades | WR | PF | PnL Return | PnL $ |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["monthly"]:
        lines.append(
            f"| {row['ticker']} | {row['month']} | {int(row['trades'])} | "
            f"{float(row['win_rate']):.1%} | {float(row['profit_factor']):.3f} | "
            f"{float(row['pnl_return']):.3f} | {float(row['pnl_dollars']):,.0f} |"
        )
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a causal daily PnL streak guard to event-option trades.")
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-month", required=True)
    parser.add_argument("--end-month", required=True)
    parser.add_argument("--trigger-losses", type=int, default=5)
    parser.add_argument("--pause-days", type=int, default=2)
    parser.add_argument("--loss-threshold", type=float, default=0.0)
    parser.add_argument("--rolling-sum-window", type=int, default=0)
    parser.add_argument("--rolling-sum-threshold", type=float, default=0.0)
    parser.add_argument(
        "--volume-protect-monthly-target",
        type=int,
        default=0,
        help="If >0, paused days are traded when the ticker is behind this monthly trade-count pace.",
    )
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    months = month_range(str(args.start_month), str(args.end_month))
    source_trade_file = resolve_trade_file(result_dir)
    trades = load_trades(source_trade_file, months)

    guarded_parts: list[pd.DataFrame] = []
    decision_parts: list[pd.DataFrame] = []
    for ticker, part in trades.groupby("ticker", sort=True):
        guarded, decisions = apply_guard_to_ticker(part.copy(), args)
        guarded_parts.append(guarded)
        decision_parts.append(decisions)
    guarded_trades = pd.concat(guarded_parts, ignore_index=True, sort=False) if guarded_parts else trades.iloc[0:0].copy()
    decisions = pd.concat(decision_parts, ignore_index=True, sort=False) if decision_parts else pd.DataFrame()
    guarded_trades = guarded_trades.sort_values(["date", "time", "ticker", "_guard_original_row"], kind="stable").reset_index(drop=True)
    guarded_trades.drop(columns=["_guard_original_row"], errors="ignore").to_csv(output_dir / "combined_trades.csv", index=False)
    decisions.to_csv(output_dir / "daily_streak_guard_decisions.csv", index=False)

    source_fold_file = resolve_fold_file(result_dir)
    if source_fold_file is not None:
        copyfile(source_fold_file, output_dir / "combined_folds.csv")

    by_ticker = {ticker: metrics(part, months) for ticker, part in guarded_trades.groupby("ticker", sort=True)}
    payload = {
        "config": {
            **vars(args),
            "source_trade_file": str(source_trade_file),
            "source_fold_file": str(source_fold_file) if source_fold_file is not None else "",
            "months": months,
        },
        "overall": metrics(guarded_trades, months),
        "by_ticker": by_ticker,
        "monthly": monthly_rows(guarded_trades, months, float(args.risk_capital)),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(output_dir, payload)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
