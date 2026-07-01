from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range


def metric_frame(frame: pd.DataFrame, months: list[str]) -> dict[str, float]:
    if frame.empty:
        return {
            "trades": 0,
            "win_rate": float("nan"),
            "profit_factor": float("nan"),
            "pnl_return": 0.0,
            "min_month_trades": 0,
            "positive_months": 0,
            "call_rate": float("nan"),
        }
    returns = pd.to_numeric(frame["realized_return"], errors="coerce").fillna(0.0)
    gross_profit = float(returns[returns > 0.0].sum())
    gross_loss = float(-returns[returns < 0.0].sum())
    month_counts = frame.assign(_ret=returns).groupby("month").size().reindex(months, fill_value=0)
    month_pnl = frame.assign(_ret=returns).groupby("month")["_ret"].sum().reindex(months, fill_value=0.0)
    action = frame["action"].astype(str).str.upper() if "action" in frame.columns else pd.Series(dtype=str)
    return {
        "trades": int(len(frame)),
        "win_rate": float((returns > 0.0).mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf"),
        "pnl_return": float(returns.sum()),
        "min_month_trades": int(month_counts.min()),
        "positive_months": int((month_pnl > 0.0).sum()),
        "call_rate": float((action == "CALL").mean()) if len(action) else float("nan"),
    }


def gate_pass(row: dict[str, float], args: argparse.Namespace) -> bool:
    return bool(
        float(row["win_rate"]) >= float(args.min_win_rate)
        and float(row["profit_factor"]) >= float(args.min_profit_factor)
        and int(row["min_month_trades"]) >= int(args.min_month_trades)
        and float(args.min_call_rate) <= float(row["call_rate"]) <= float(args.max_call_rate)
    )


def normalize_months(frame: pd.DataFrame) -> pd.DataFrame:
    if "test_month" not in frame.columns and "month" in frame.columns:
        frame["test_month"] = frame["month"].astype(str)
    if "month" not in frame.columns and "test_month" in frame.columns:
        frame["month"] = frame["test_month"].astype(str)
    frame["month"] = frame["month"].astype(str)
    frame["test_month"] = frame["test_month"].astype(str)
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute source transfer metrics for declared select/test months.")
    parser.add_argument("--input-scan", required=True, help="CSV with path/ticker columns.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--select-window", action="append", required=True, help="NAME:START:END")
    parser.add_argument("--test-start-month", required=True)
    parser.add_argument("--test-end-month", required=True)
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    args = parser.parse_args()

    input_scan = pd.read_csv(args.input_scan)
    if not {"path", "ticker"}.issubset(input_scan.columns):
        raise ValueError("--input-scan needs path and ticker columns")
    test_months = month_range(str(args.test_start_month), str(args.test_end_month))
    select_windows: list[tuple[str, list[str]]] = []
    for raw in args.select_window:
        name, start, end = str(raw).split(":", 2)
        select_windows.append((name, month_range(start, end)))

    rows: list[dict[str, object]] = []
    seen = input_scan[["path", "dir", "file", "ticker"] if {"dir", "file"}.issubset(input_scan.columns) else ["path", "ticker"]]
    seen = seen.drop_duplicates().reset_index(drop=True)
    cache: dict[str, pd.DataFrame] = {}
    for item in seen.to_dict("records"):
        path = Path(str(item["path"]))
        ticker = str(item["ticker"]).upper()
        if not path.exists():
            continue
        if str(path) not in cache:
            try:
                cache[str(path)] = pd.read_csv(
                    path,
                    dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str},
                    low_memory=False,
                )
            except Exception:
                continue
        frame = cache[str(path)].copy()
        if "ticker" in frame.columns:
            frame = frame[frame["ticker"].astype(str).str.upper().eq(ticker)].copy()
        if frame.empty or "realized_return" not in frame.columns:
            continue
        frame = normalize_months(frame)
        for window_name, select_months in select_windows:
            select = frame[frame["test_month"].isin(select_months) | frame["month"].isin(select_months)].copy()
            test = frame[frame["test_month"].isin(test_months) | frame["month"].isin(test_months)].copy()
            sm = metric_frame(select, select_months)
            tm = metric_frame(test, test_months)
            rows.append(
                {
                    "path": str(path),
                    "dir": str(item.get("dir", path.parent.name)),
                    "file": str(item.get("file", path.name)),
                    "ticker": ticker,
                    "select_window": window_name,
                    "select_pass": gate_pass(sm, args),
                    "test_pass": gate_pass(tm, args),
                    "pass_both": gate_pass(sm, args) and gate_pass(tm, args),
                    **{f"select_{key}": value for key, value in sm.items()},
                    **{f"test_{key}": value for key, value in tm.items()},
                }
            )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(rows)
    out.to_csv(output, index=False)
    print(out.to_string(index=False))
    print(f"\nWrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
