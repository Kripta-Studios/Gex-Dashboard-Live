from __future__ import annotations

import argparse
import itertools
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from analyze_event_option_curve_health import build_daily, health_flags, summarize_ticker
from apply_event_daily_streak_guard import apply_guard_to_ticker, load_trades, resolve_trade_file
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics

_WORKER_TRADES = pd.DataFrame()
_WORKER_TICKERS: list[str] = []
_WORKER_SELECT_MONTHS: list[str] = []
_WORKER_VALID_MONTHS: list[str] = []
_WORKER_FORWARD_MONTHS: list[str] = []


def parse_int_grid(values: list[str] | None, default: list[int]) -> list[int]:
    if not values:
        return default
    out: list[int] = []
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                out.append(int(part))
    return out


def parse_float_grid(values: list[str] | None, default: list[float]) -> list[float]:
    if not values:
        return default
    out: list[float] = []
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                out.append(float(part))
    return out


def finite_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def pass_metrics(row: dict[str, Any], task: dict[str, Any]) -> bool:
    call_rate = finite_float(row.get("call_rate"), -1.0)
    return (
        int(row.get("trades", 0) or 0) > 0
        and finite_float(row.get("pnl_return"), 0.0) > 0.0
        and finite_float(row.get("win_rate"), 0.0) >= float(task["min_win_rate"])
        and finite_float(row.get("profit_factor"), 0.0) >= float(task["min_profit_factor"])
        and int(row.get("min_month_trades", 0) or 0) >= int(task["min_month_trades"])
        and float(task["min_call_rate"]) <= call_rate <= float(task["max_call_rate"])
    )


def metric_fields(prefix: str, row: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "trades",
        "win_rate",
        "profit_factor",
        "pnl_return",
        "avg_return",
        "max_drawdown",
        "call_rate",
        "days_with_trades",
        "daily_win_rate",
        "daily_max_drawdown",
        "top5_share_of_pnl",
        "min_month_trades",
        "positive_month_rate",
    )
    return {f"{prefix}_{key}": row.get(key) for key in keep}


def window_summary(trades: pd.DataFrame, months: list[str], tickers: list[str], task: dict[str, Any], prefix: str) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    passes: list[bool] = []
    pf_values: list[float] = []
    wr_values: list[float] = []
    min_month_values: list[int] = []
    for ticker in tickers:
        part = trades[trades["ticker"].astype(str).str.upper().eq(ticker)].copy()
        item = metrics(part[part["month"].astype(str).isin(months)].copy(), months)
        rows.update(metric_fields(f"{prefix}_{ticker.lower()}", item))
        ok = pass_metrics(item, task)
        rows[f"{prefix}_{ticker.lower()}_pass"] = ok
        passes.append(ok)
        pf_values.append(finite_float(item.get("profit_factor"), 0.0))
        wr_values.append(finite_float(item.get("win_rate"), 0.0))
        min_month_values.append(int(item.get("min_month_trades", 0) or 0))
    overall = metrics(trades[trades["month"].astype(str).isin(months)].copy(), months)
    rows.update(metric_fields(f"{prefix}_overall", overall))
    rows[f"{prefix}_pass"] = bool(all(passes))
    rows[f"{prefix}_pf_min"] = float(min(pf_values)) if pf_values else 0.0
    rows[f"{prefix}_wr_min"] = float(min(wr_values)) if wr_values else 0.0
    rows[f"{prefix}_min_month_min"] = int(min(min_month_values)) if min_month_values else 0
    return rows


def health_summary(trades: pd.DataFrame, months: list[str], tickers: list[str], task: dict[str, Any], prefix: str) -> dict[str, Any]:
    if not months:
        return {}
    args = SimpleNamespace(
        max_top1_share=float(task["max_top1_share"]),
        max_top5_share=float(task["max_top5_share"]),
        max_drawdown_to_pnl=float(task["max_drawdown_to_pnl"]),
        max_month_pnl_share=float(task["max_month_pnl_share"]),
        max_negative_streak=int(task["max_negative_streak"]),
        min_first_two_month_share=float(task["min_first_two_month_share"]),
        min_first_three_month_share=float(task["min_first_three_month_share"]),
    )
    daily = build_daily(trades, float(task["risk_capital"]), months)
    flag_counts: list[int] = []
    negative_months: list[int] = []
    negative_streaks: list[int] = []
    dd_to_pnl: list[float] = []
    flags_by_ticker: dict[str, str] = {}
    for ticker in tickers:
        item = summarize_ticker(daily, trades, ticker, months, float(task["risk_capital"]))
        flags = health_flags(item, args)
        flags_by_ticker[ticker] = ";".join(flags)
        flag_counts.append(len(flags))
        negative_months.append(int(item.get("negative_months", 0)))
        negative_streaks.append(int(item.get("max_negative_day_streak", 0)))
        dd_to_pnl.append(finite_float(item.get("max_drawdown_to_pnl"), float("inf")))
    return {
        f"{prefix}_health_flag_count": int(sum(flag_counts)),
        f"{prefix}_negative_months": int(sum(negative_months)),
        f"{prefix}_max_negative_day_streak": int(max(negative_streaks)) if negative_streaks else 0,
        f"{prefix}_max_dd_to_pnl": float(max(dd_to_pnl)) if dd_to_pnl else 0.0,
        f"{prefix}_flags_json": json.dumps(flags_by_ticker, sort_keys=True),
    }


def init_worker(trades_path: str, months: list[str], tickers: list[str], select_months: list[str], valid_months: list[str], forward_months: list[str]) -> None:
    global _WORKER_TRADES, _WORKER_TICKERS, _WORKER_SELECT_MONTHS, _WORKER_VALID_MONTHS, _WORKER_FORWARD_MONTHS
    _WORKER_TRADES = load_trades(Path(trades_path), months)
    _WORKER_TICKERS = [ticker.upper() for ticker in tickers]
    _WORKER_SELECT_MONTHS = list(select_months)
    _WORKER_VALID_MONTHS = list(valid_months)
    _WORKER_FORWARD_MONTHS = list(forward_months)


def evaluate_task(task: dict[str, Any]) -> dict[str, Any]:
    args = SimpleNamespace(
        trigger_losses=int(task["trigger_losses"]),
        pause_days=int(task["pause_days"]),
        loss_threshold=float(task["loss_threshold"]),
        rolling_sum_window=int(task["rolling_sum_window"]),
        rolling_sum_threshold=float(task["rolling_sum_threshold"]),
        volume_protect_monthly_target=int(task["volume_protect_monthly_target"]),
    )
    guarded_parts: list[pd.DataFrame] = []
    decision_parts: list[pd.DataFrame] = []
    for ticker, part in _WORKER_TRADES.groupby("ticker", sort=True):
        guarded, decisions = apply_guard_to_ticker(part.copy(), args)
        guarded_parts.append(guarded)
        decision_parts.append(decisions)
    guarded = pd.concat(guarded_parts, ignore_index=True, sort=False) if guarded_parts else _WORKER_TRADES.iloc[0:0].copy()
    decisions = pd.concat(decision_parts, ignore_index=True, sort=False) if decision_parts else pd.DataFrame()
    row: dict[str, Any] = {
        "trigger_losses": int(task["trigger_losses"]),
        "pause_days": int(task["pause_days"]),
        "loss_threshold": float(task["loss_threshold"]),
        "rolling_sum_window": int(task["rolling_sum_window"]),
        "rolling_sum_threshold": float(task["rolling_sum_threshold"]),
        "volume_protect_monthly_target": int(task["volume_protect_monthly_target"]),
        "skipped_days": int(decisions["decision"].astype(str).eq("SKIP_PAUSED").sum()) if not decisions.empty else 0,
        "volume_protected_days": int(decisions.get("volume_protected", pd.Series(dtype=bool)).astype(str).str.lower().eq("true").sum()) if not decisions.empty else 0,
    }
    row.update(window_summary(guarded, _WORKER_SELECT_MONTHS, _WORKER_TICKERS, task, "select"))
    row.update(window_summary(guarded, _WORKER_VALID_MONTHS, _WORKER_TICKERS, task, "valid"))
    row["pretest_pass"] = bool(row.get("select_pass") and row.get("valid_pass"))
    pretest_months = list(dict.fromkeys(_WORKER_SELECT_MONTHS + _WORKER_VALID_MONTHS))
    row.update(health_summary(guarded, pretest_months, _WORKER_TICKERS, task, "pretest"))
    if _WORKER_FORWARD_MONTHS:
        row.update(window_summary(guarded, _WORKER_FORWARD_MONTHS, _WORKER_TICKERS, task, "forward"))
        row.update(health_summary(guarded, _WORKER_FORWARD_MONTHS, _WORKER_TICKERS, task, "forward"))
    row["selection_score"] = (
        -10.0 * int(row.get("pretest_health_flag_count", 0))
        -2.0 * int(row.get("pretest_max_negative_day_streak", 0))
        -1.5 * int(row.get("pretest_negative_months", 0))
        +0.75 * int(row.get("valid_min_month_min", 0))
        +4.0 * finite_float(row.get("valid_pf_min"), 0.0)
        +2.0 * finite_float(row.get("valid_wr_min"), 0.0)
        +0.15 * finite_float(row.get("valid_overall_pnl_return"), 0.0)
    )
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Parallel scan for causal daily streak guard parameters.")
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--select-start-month", required=True)
    parser.add_argument("--select-end-month", required=True)
    parser.add_argument("--valid-start-month", required=True)
    parser.add_argument("--valid-end-month", required=True)
    parser.add_argument("--forward-start-month", default="")
    parser.add_argument("--forward-end-month", default="")
    parser.add_argument("--trigger-losses-grid", nargs="*", default=[])
    parser.add_argument("--pause-days-grid", nargs="*", default=[])
    parser.add_argument("--loss-threshold-grid", nargs="*", default=[])
    parser.add_argument("--rolling-sum-window-grid", nargs="*", default=[])
    parser.add_argument("--rolling-sum-threshold-grid", nargs="*", default=[])
    parser.add_argument("--volume-protect-monthly-target-grid", nargs="*", default=[])
    parser.add_argument("--workers", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 1)))
    parser.add_argument("--chunksize", type=int, default=16)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-call-rate", type=float, default=0.0)
    parser.add_argument("--max-call-rate", type=float, default=1.0)
    parser.add_argument("--max-top1-share", type=float, default=0.45)
    parser.add_argument("--max-top5-share", type=float, default=0.80)
    parser.add_argument("--max-drawdown-to-pnl", type=float, default=0.45)
    parser.add_argument("--max-month-pnl-share", type=float, default=0.65)
    parser.add_argument("--max-negative-streak", type=int, default=4)
    parser.add_argument("--min-first-two-month-share", type=float, default=0.10)
    parser.add_argument("--min-first-three-month-share", type=float, default=0.20)
    args = parser.parse_args()

    select_months = month_range(str(args.select_start_month), str(args.select_end_month))
    valid_months = month_range(str(args.valid_start_month), str(args.valid_end_month))
    forward_months = month_range(str(args.forward_start_month), str(args.forward_end_month)) if args.forward_start_month and args.forward_end_month else []
    all_months = list(dict.fromkeys(select_months + valid_months + forward_months))
    trades_path = resolve_trade_file(Path(args.result_dir))
    tasks: list[dict[str, Any]] = []
    for trigger, pause, loss_threshold, roll_window, roll_threshold, volume_target in itertools.product(
        parse_int_grid(args.trigger_losses_grid, [0, 3, 4, 5, 6, 7]),
        parse_int_grid(args.pause_days_grid, [0, 1, 2, 3, 4, 5]),
        parse_float_grid(args.loss_threshold_grid, [0.0]),
        parse_int_grid(args.rolling_sum_window_grid, [0, 3, 5]),
        parse_float_grid(args.rolling_sum_threshold_grid, [0.0, -0.5, -1.0, -2.0]),
        parse_int_grid(args.volume_protect_monthly_target_grid, [0, 18]),
    ):
        if int(trigger) <= 0 and int(roll_window) <= 0:
            pause = 0
        if int(roll_window) <= 0 and float(roll_threshold) != 0.0:
            continue
        tasks.append(
            {
                "trigger_losses": int(trigger),
                "pause_days": int(pause),
                "loss_threshold": float(loss_threshold),
                "rolling_sum_window": int(roll_window),
                "rolling_sum_threshold": float(roll_threshold),
                "volume_protect_monthly_target": int(volume_target),
                "risk_capital": float(args.risk_capital),
                "min_win_rate": float(args.min_win_rate),
                "min_profit_factor": float(args.min_profit_factor),
                "min_month_trades": int(args.min_month_trades),
                "min_call_rate": float(args.min_call_rate),
                "max_call_rate": float(args.max_call_rate),
                "max_top1_share": float(args.max_top1_share),
                "max_top5_share": float(args.max_top5_share),
                "max_drawdown_to_pnl": float(args.max_drawdown_to_pnl),
                "max_month_pnl_share": float(args.max_month_pnl_share),
                "max_negative_streak": int(args.max_negative_streak),
                "min_first_two_month_share": float(args.min_first_two_month_share),
                "min_first_three_month_share": float(args.min_first_three_month_share),
            }
        )
    print(json.dumps({"trades_path": str(trades_path), "tasks": len(tasks), "workers": int(args.workers)}, indent=2))

    rows: list[dict[str, Any]] = []
    workers = max(1, int(args.workers))
    if workers == 1:
        init_worker(str(trades_path), all_months, list(args.tickers), select_months, valid_months, forward_months)
        for idx, task in enumerate(tasks, start=1):
            rows.append(evaluate_task(task))
            if idx % 100 == 0:
                print(f"completed {idx}/{len(tasks)}")
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=init_worker,
            initargs=(str(trades_path), all_months, list(args.tickers), select_months, valid_months, forward_months),
        ) as executor:
            futures = [executor.submit(evaluate_task, task) for task in tasks]
            for idx, future in enumerate(as_completed(futures), start=1):
                rows.append(future.result())
                if idx % 100 == 0 or idx == len(futures):
                    print(f"completed {idx}/{len(futures)}")
    out = pd.DataFrame(rows)
    out = out.sort_values(
        [
            "pretest_pass",
            "pretest_health_flag_count",
            "pretest_max_negative_day_streak",
            "pretest_negative_months",
            "valid_min_month_min",
            "selection_score",
        ],
        ascending=[False, True, True, True, False, False],
        kind="stable",
    )
    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False)
    summary = {
        "output_csv": str(output_csv),
        "rows": int(len(out)),
        "pretest_pass": int(out["pretest_pass"].sum()),
        "top": out.head(10).to_dict(orient="records"),
    }
    print(json.dumps(summary, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
