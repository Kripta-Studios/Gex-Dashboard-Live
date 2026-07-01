from __future__ import annotations

import argparse
import itertools
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd

from apply_event_monthly_pnl_rescue_backfill import apply_pnl_rescue_backfill
from apply_event_monthly_volume_backfill import load_trades
from evaluate_xinput_level_filter import month_range
from scan_event_daily_streak_guard import finite_float, health_summary, window_summary

_CONFIGS: list[dict[str, Any]] = []
_SOURCES: dict[str, pd.DataFrame] = {}
_TICKERS: list[str] = []
_SELECT_MONTHS: list[str] = []
_VALID_MONTHS: list[str] = []
_ALL_MONTHS: list[str] = []


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


def read_configs(paths: list[str]) -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []
    for path in paths:
        frame = pd.read_csv(path)
        if frame.empty:
            raise ValueError(f"empty config: {path}")
        row = frame.iloc[0].to_dict()
        configs.append(
            {
                "ticker": str(row["ticker"]).upper(),
                "primary_trades": str(row["primary_trades"]),
                "fallback_trades": str(row["fallback_trades"]),
                "primary_name": str(row.get("primary_name", "primary")),
                "fallback_name": str(row.get("fallback_name", "fallback")),
            }
        )
    return configs


def init_worker(configs: list[dict[str, Any]], months: list[str], tickers: list[str], select_months: list[str], valid_months: list[str]) -> None:
    global _CONFIGS, _SOURCES, _TICKERS, _SELECT_MONTHS, _VALID_MONTHS, _ALL_MONTHS
    _CONFIGS = list(configs)
    _SOURCES = {}
    _TICKERS = [str(t).upper() for t in tickers]
    _SELECT_MONTHS = list(select_months)
    _VALID_MONTHS = list(valid_months)
    _ALL_MONTHS = list(months)
    for config in _CONFIGS:
        p_key = f"{config['ticker']}:primary"
        f_key = f"{config['ticker']}:fallback"
        _SOURCES[p_key] = load_trades(Path(config["primary_trades"]), str(config["primary_name"]))
        _SOURCES[f_key] = load_trades(Path(config["fallback_trades"]), str(config["fallback_name"]))


def pass_count(row: dict[str, Any], prefix: str, tickers: list[str]) -> int:
    return int(sum(bool(row.get(f"{prefix}_{ticker.lower()}_pass", False)) for ticker in tickers))


def evaluate_task(task: dict[str, Any]) -> dict[str, Any]:
    parts: list[pd.DataFrame] = []
    for config in _CONFIGS:
        ticker = str(config["ticker"]).upper()
        local_args = SimpleNamespace(
            start_month=_ALL_MONTHS[0],
            end_month=_ALL_MONTHS[-1],
            min_month_trades=int(task["min_month_trades"]),
            auto_partial_month_target=False,
            partial_month_observed_floor=0,
            backfill_only_partial_months=False,
            max_day=int(task["max_day"]),
            cooldown_minutes=int(task["cooldown_minutes"]),
            min_entry_minute=int(task["min_entry_minute"]),
            primary_name=str(config["primary_name"]),
            fallback_name=str(config["fallback_name"]),
            rescue_pnl_threshold=float(task["rescue_pnl_threshold"]),
            rescue_start_bday=int(task["rescue_start_bday"]),
            risk_capital=float(task["risk_capital"]),
        )
        selected = apply_pnl_rescue_backfill(_SOURCES[f"{ticker}:primary"], _SOURCES[f"{ticker}:fallback"], local_args)
        parts.append(selected)
    trades = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    row: dict[str, Any] = {
        "max_day": int(task["max_day"]),
        "cooldown_minutes": int(task["cooldown_minutes"]),
        "min_entry_minute": int(task["min_entry_minute"]),
        "rescue_pnl_threshold": float(task["rescue_pnl_threshold"]),
        "rescue_start_bday": int(task["rescue_start_bday"]),
        "min_month_trades": int(task["min_month_trades"]),
    }
    row.update(window_summary(trades, _SELECT_MONTHS, _TICKERS, task, "select"))
    row.update(window_summary(trades, _VALID_MONTHS, _TICKERS, task, "valid"))
    pretest_months = list(dict.fromkeys(_SELECT_MONTHS + _VALID_MONTHS))
    row.update(health_summary(trades, pretest_months, _TICKERS, task, "pretest"))
    row["select_pass_count"] = pass_count(row, "select", _TICKERS)
    row["valid_pass_count"] = pass_count(row, "valid", _TICKERS)
    row["pretest_pass"] = bool(row.get("select_pass") and row.get("valid_pass"))
    row["selection_score"] = (
        100.0 * int(row["pretest_pass"])
        + 12.0 * int(row["valid_pass_count"])
        + 8.0 * int(row["select_pass_count"])
        - 4.0 * int(row.get("pretest_health_flag_count", 0))
        - 1.5 * int(row.get("pretest_negative_months", 0))
        - 2.0 * int(row.get("pretest_max_negative_day_streak", 0))
        + 5.0 * finite_float(row.get("valid_pf_min"), 0.0)
        + 3.0 * finite_float(row.get("valid_wr_min"), 0.0)
        + 0.08 * finite_float(row.get("valid_overall_pnl_return"), 0.0)
    )
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan monthly PnL rescue backfill parameters.")
    parser.add_argument("--config-csv", action="append", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--select-start-month", required=True)
    parser.add_argument("--select-end-month", required=True)
    parser.add_argument("--valid-start-month", required=True)
    parser.add_argument("--valid-end-month", required=True)
    parser.add_argument("--max-day-grid", nargs="*", default=[])
    parser.add_argument("--cooldown-minutes-grid", nargs="*", default=[])
    parser.add_argument("--min-entry-minute-grid", nargs="*", default=[])
    parser.add_argument("--rescue-pnl-threshold-grid", nargs="*", default=[])
    parser.add_argument("--rescue-start-bday-grid", nargs="*", default=[])
    parser.add_argument("--workers", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 1)))
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--max-top1-share", type=float, default=0.45)
    parser.add_argument("--max-top5-share", type=float, default=0.80)
    parser.add_argument("--max-drawdown-to-pnl", type=float, default=0.45)
    parser.add_argument("--max-month-pnl-share", type=float, default=0.65)
    parser.add_argument("--max-negative-streak", type=int, default=4)
    parser.add_argument("--min-first-two-month-share", type=float, default=0.10)
    parser.add_argument("--min-first-three-month-share", type=float, default=0.20)
    args = parser.parse_args()

    configs = read_configs(list(args.config_csv))
    select_months = month_range(str(args.select_start_month), str(args.select_end_month))
    valid_months = month_range(str(args.valid_start_month), str(args.valid_end_month))
    all_months = list(dict.fromkeys(select_months + valid_months))
    tasks: list[dict[str, Any]] = []
    for max_day, cooldown, min_entry, threshold, start_bday in itertools.product(
        parse_int_grid(args.max_day_grid, [3, 4, 5]),
        parse_int_grid(args.cooldown_minutes_grid, [15, 30, 45]),
        parse_int_grid(args.min_entry_minute_grid, [0]),
        parse_float_grid(args.rescue_pnl_threshold_grid, [-3.0, -2.0, -1.0, 0.0, 1.0]),
        parse_int_grid(args.rescue_start_bday_grid, [1, 5, 10]),
    ):
        tasks.append(
            {
                "max_day": int(max_day),
                "cooldown_minutes": int(cooldown),
                "min_entry_minute": int(min_entry),
                "rescue_pnl_threshold": float(threshold),
                "rescue_start_bday": int(start_bday),
                "min_month_trades": int(args.min_month_trades),
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
    print(json.dumps({"configs": configs, "tasks": len(tasks), "workers": int(args.workers)}, indent=2))

    rows: list[dict[str, Any]] = []
    workers = max(1, int(args.workers))
    if workers == 1:
        init_worker(configs, all_months, list(args.tickers), select_months, valid_months)
        for idx, task in enumerate(tasks, start=1):
            rows.append(evaluate_task(task))
            if idx % 50 == 0 or idx == len(tasks):
                print(f"completed {idx}/{len(tasks)}")
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=init_worker,
            initargs=(configs, all_months, list(args.tickers), select_months, valid_months),
        ) as executor:
            futures = [executor.submit(evaluate_task, task) for task in tasks]
            for idx, future in enumerate(as_completed(futures), start=1):
                rows.append(future.result())
                if idx % 50 == 0 or idx == len(futures):
                    print(f"completed {idx}/{len(futures)}")
    out = pd.DataFrame(rows)
    out = out.sort_values(
        [
            "pretest_pass",
            "valid_pass_count",
            "select_pass_count",
            "pretest_health_flag_count",
            "pretest_negative_months",
            "selection_score",
        ],
        ascending=[False, False, False, True, True, False],
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
