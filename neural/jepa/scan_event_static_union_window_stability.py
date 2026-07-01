from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from materialize_event_static_union import load_source, materialize_union
from walkforward_event_option_gate import metrics, score_metrics


def parse_named_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Expected NAME=PATH, got {value!r}")
    name, raw = value.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"Empty source name in {value!r}")
    return name, Path(raw.strip())


def finite_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def pass_basic(row: dict[str, Any], args: argparse.Namespace) -> bool:
    return (
        int(row.get("trades", 0) or 0) > 0
        and finite_float(row.get("pnl_return"), 0.0) > 0.0
        and finite_float(row.get("win_rate"), 0.0) >= float(args.min_win_rate)
        and finite_float(row.get("profit_factor"), 0.0) >= float(args.min_profit_factor)
        and int(row.get("min_month_trades", 0) or 0) >= int(args.min_month_trades)
    )


def pass_user(row: dict[str, Any], args: argparse.Namespace) -> bool:
    if not pass_basic(row, args):
        return False
    call_rate = finite_float(row.get("call_rate"), -1.0)
    return float(args.min_call_rate) <= call_rate <= float(args.max_call_rate)


def stability_score(row: dict[str, Any], args: argparse.Namespace) -> float:
    strict = score_metrics(
        row,
        int(args.min_select_trades),
        int(args.min_month_trades),
        float(args.min_profit_factor),
        float(args.min_win_rate),
        float(args.min_call_rate),
        float(args.max_call_rate),
    )
    if math.isfinite(float(strict)) and float(strict) > -1e12:
        return float(strict)
    trades = finite_float(row.get("trades"), 0.0)
    wr = finite_float(row.get("win_rate"), 0.0)
    pf = finite_float(row.get("profit_factor"), 0.0)
    pnl = finite_float(row.get("pnl_return"), 0.0)
    min_month = finite_float(row.get("min_month_trades"), 0.0)
    call_rate = finite_float(row.get("call_rate"), 0.0)
    pos_month = finite_float(row.get("positive_month_rate"), 0.0)
    score = (
        8.0 * min(max(pf, 0.0), 3.0)
        + 18.0 * wr
        + 0.020 * min(trades, 1200.0)
        + 0.25 * pnl
        + 2.0 * pos_month
    )
    score -= 1.50 * max(float(args.min_month_trades) - min_month, 0.0)
    score -= 4.0 * max(float(args.min_profit_factor) - pf, 0.0)
    score -= 12.0 * max(float(args.min_win_rate) - wr, 0.0)
    if trades < float(args.min_select_trades):
        score -= 0.02 * (float(args.min_select_trades) - trades)
    if call_rate < float(args.min_call_rate):
        score -= 20.0 * (float(args.min_call_rate) - call_rate)
    if call_rate > float(args.max_call_rate):
        score -= 20.0 * (call_rate - float(args.max_call_rate))
    if pnl <= 0.0:
        score -= 10.0 + abs(pnl)
    return float(score)


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


def window_metrics(selected: pd.DataFrame, months: list[str]) -> dict[str, Any]:
    if selected.empty:
        return metrics(selected, months)
    return metrics(selected[selected["month"].astype(str).isin(months)].copy(), months)


def build_source_frame(args: argparse.Namespace, months: list[str]) -> tuple[pd.DataFrame, list[str]]:
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    for priority, spec in enumerate(args.source):
        name, path = parse_named_path(spec)
        names.append(name)
        frame = load_source(name, path, str(args.ticker).upper(), months, priority)
        if not frame.empty:
            frames.append(frame)
    if not frames:
        raise ValueError("No source rows loaded for requested ticker/months")
    return pd.concat(frames, ignore_index=True), names


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan static-union configs across pre-test stability windows.")
    parser.add_argument("--source", action="append", required=True, help="NAME=path/to/event_option_gate_trades.csv")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--select-start-month", required=True)
    parser.add_argument("--select-end-month", required=True)
    parser.add_argument("--valid-start-month", required=True)
    parser.add_argument("--valid-end-month", required=True)
    parser.add_argument("--test1-start-month", required=True)
    parser.add_argument("--test1-end-month", required=True)
    parser.add_argument("--test2-start-month", required=True)
    parser.add_argument("--test2-end-month", required=True)
    parser.add_argument("--max-sources", type=int, default=3)
    parser.add_argument("--permute-sources", action="store_true")
    parser.add_argument("--max-trades-per-day", type=int, default=999)
    parser.add_argument("--daily-order", choices=["time_asc", "score_desc"], default="time_asc")
    parser.add_argument("--min-score-grid", nargs="+", type=float, default=[-999999.0, 0.0])
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-select-trades", type=int, default=100)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    args = parser.parse_args()

    select_months = month_range(str(args.select_start_month), str(args.select_end_month))
    valid_months = month_range(str(args.valid_start_month), str(args.valid_end_month))
    test1_months = month_range(str(args.test1_start_month), str(args.test1_end_month))
    test2_months = month_range(str(args.test2_start_month), str(args.test2_end_month))
    all_months = list(dict.fromkeys(select_months + valid_months + test1_months + test2_months))
    frame, source_names = build_source_frame(args, all_months)

    rows: list[dict[str, Any]] = []
    for size in range(1, int(args.max_sources) + 1):
        for subset in itertools.combinations(source_names, size):
            orders = itertools.permutations(subset) if bool(args.permute_sources) else [tuple(subset)]
            for order in orders:
                ordered = frame[frame["static_union_source"].isin(order)].copy()
                ordered["_source_priority"] = ordered["static_union_source"].map({name: idx for idx, name in enumerate(order)}).astype(int)
                for min_score in [float(value) for value in args.min_score_grid]:
                    selected = materialize_union(
                        ordered,
                        int(args.max_trades_per_day),
                        float(min_score),
                        str(args.daily_order),
                    )
                    select = window_metrics(selected, select_months)
                    valid = window_metrics(selected, valid_months)
                    test1 = window_metrics(selected, test1_months)
                    test2 = window_metrics(selected, test2_months)
                    row: dict[str, Any] = {
                        "ticker": str(args.ticker).upper(),
                        "sources": ",".join(order),
                        "source_count": len(order),
                        "max_trades_per_day": int(args.max_trades_per_day),
                        "daily_order": str(args.daily_order),
                        "min_score": float(min_score),
                        "select_score": stability_score(select, args),
                        "valid_score": stability_score(valid, args),
                        "select_basic_pass": pass_basic(select, args),
                        "valid_basic_pass": pass_basic(valid, args),
                        "test1_basic_pass": pass_basic(test1, args),
                        "test2_basic_pass": pass_basic(test2, args),
                        "select_user_pass": pass_user(select, args),
                        "valid_user_pass": pass_user(valid, args),
                        "test1_user_pass": pass_user(test1, args),
                        "test2_user_pass": pass_user(test2, args),
                    }
                    row["pretest_basic_pass"] = bool(row["select_basic_pass"] and row["valid_basic_pass"])
                    row["pretest_user_pass"] = bool(row["select_user_pass"] and row["valid_user_pass"])
                    row["all_basic_pass"] = bool(row["pretest_basic_pass"] and row["test1_basic_pass"] and row["test2_basic_pass"])
                    row["all_user_pass"] = bool(row["pretest_user_pass"] and row["test1_user_pass"] and row["test2_user_pass"])
                    row["stability_score"] = min(float(row["select_score"]), float(row["valid_score"]))
                    row.update(metric_fields("sel", select))
                    row.update(metric_fields("val", valid))
                    row.update(metric_fields("t1", test1))
                    row.update(metric_fields("t2", test2))
                    rows.append(row)

    out = pd.DataFrame(rows).sort_values(
        ["pretest_user_pass", "pretest_basic_pass", "stability_score", "select_score", "valid_score", "source_count"],
        ascending=[False, False, False, False, False, True],
        kind="stable",
    )
    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False)
    summary = {
        "output_csv": str(output_csv),
        "rows": int(len(out)),
        "pretest_user_pass": int(out["pretest_user_pass"].sum()),
        "pretest_basic_pass": int(out["pretest_basic_pass"].sum()),
        "all_user_pass": int(out["all_user_pass"].sum()),
        "all_basic_pass": int(out["all_basic_pass"].sum()),
        "top": out.head(10).to_dict(orient="records"),
    }
    print(json.dumps(summary, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())