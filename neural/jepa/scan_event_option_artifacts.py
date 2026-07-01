from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range


TRADE_FILE_CANDIDATES = (
    "combined_trades.csv",
    "trade_union_topk_regressor_trades.csv",
    "nested_volume_backfill_trades.csv",
    "intraday_circuit_trades.csv",
    "event_option_gate_trades.csv",
    "volume_backfill_trades.csv",
    "selected_trades.csv",
)


def month_column(frame: pd.DataFrame) -> str | None:
    if "test_month" in frame.columns:
        return "test_month"
    if "month" in frame.columns:
        return "month"
    return None


def first_trade_file(directory: Path) -> Path | None:
    for name in TRADE_FILE_CANDIDATES:
        path = directory / name
        if path.exists():
            return path
    return None


def summarize_trades(frame: pd.DataFrame, months: list[str]) -> dict[str, float] | None:
    month_col = month_column(frame)
    if frame.empty or month_col is None or "realized_return" not in frame.columns:
        return None

    returns = pd.to_numeric(frame["realized_return"], errors="coerce").fillna(0.0)
    gross_profit = returns[returns > 0.0].sum()
    gross_loss = -returns[returns < 0.0].sum()
    if gross_loss > 0.0:
        profit_factor = float(gross_profit / gross_loss)
    else:
        profit_factor = float("inf") if gross_profit > 0.0 else 0.0

    month_counts = frame.groupby(month_col).size().reindex(months, fill_value=0)
    month_pnl = frame.assign(_return=returns).groupby(month_col)["_return"].sum().reindex(months, fill_value=0.0)
    daily = frame.assign(_return=returns).groupby("date")["_return"].sum().sort_index()
    pnl_return = float(returns.sum())
    top5_return = float(daily.nlargest(min(5, len(daily))).sum()) if len(daily) else 0.0

    action = frame["action"].astype(str).str.upper() if "action" in frame.columns else pd.Series(dtype=str)
    return {
        "trades": int(len(frame)),
        "win_rate": float((returns > 0.0).mean()),
        "profit_factor": profit_factor,
        "pnl_return": pnl_return,
        "min_month_trades": int(month_counts.min()),
        "positive_months": int((month_pnl > 0.0).sum()),
        "call_rate": float((action == "CALL").mean()) if len(action) else float("nan"),
        "top5_share": top5_return / pnl_return if pnl_return > 0.0 else float("nan"),
        "first_2_month_share": float(month_pnl.iloc[:2].sum()) / pnl_return if pnl_return > 0.0 else float("nan"),
        "first_3_month_share": float(month_pnl.iloc[:3].sum()) / pnl_return if pnl_return > 0.0 else float("nan"),
        "first_4_month_share": float(month_pnl.iloc[:4].sum()) / pnl_return if pnl_return > 0.0 else float("nan"),
    }


def scan_ticker(results_root: Path, ticker: str, months: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    pattern = f"event_option_{ticker.lower()}*"
    for directory in sorted(results_root.glob(pattern)):
        if not directory.is_dir():
            continue
        trade_file = first_trade_file(directory)
        if trade_file is None:
            continue
        try:
            frame = pd.read_csv(
                trade_file,
                dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str},
            )
        except Exception as exc:
            rows.append({"ticker": ticker, "artifact": directory.name, "file": trade_file.name, "error": str(exc)})
            continue
        if "ticker" in frame.columns:
            frame = frame[frame["ticker"].astype(str).str.upper().eq(ticker.upper())].copy()
        month_col = month_column(frame)
        if month_col is None:
            continue
        frame[month_col] = frame[month_col].astype(str)
        frame = frame[frame[month_col].isin(months)].copy()
        metrics = summarize_trades(frame, months)
        if metrics is None:
            continue
        rows.append({"ticker": ticker, "artifact": directory.name, "file": trade_file.name, **metrics})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["passes_basic"] = (
        (out["win_rate"] >= 0.45)
        & (out["profit_factor"] >= 1.30)
        & (out["min_month_trades"] > 18)
        & (out["call_rate"].between(0.20, 0.80))
    )
    out["passes_curve"] = (
        out["passes_basic"]
        & (out["positive_months"] >= len(months))
        & (out["top5_share"] <= 0.80)
        & (out["first_2_month_share"] >= 0.10)
        & (out["first_3_month_share"] >= 0.20)
    )
    return out.sort_values(
        ["passes_curve", "passes_basic", "profit_factor", "pnl_return"],
        ascending=[False, False, False, False],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan event-option result artifacts for basic and curve-health gates.")
    parser.add_argument("--results-root", default="research_papers/JEPA/results")
    parser.add_argument("--output", default="research_papers/JEPA/results/_diagnostics/event_option_artifact_scan.csv")
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    args = parser.parse_args()

    months = month_range(str(args.start_month), str(args.end_month))
    root = Path(args.results_root)
    parts = [scan_ticker(root, ticker.upper(), months) for ticker in args.tickers]
    parts = [part for part in parts if not part.empty]
    if not parts:
        raise RuntimeError("No scannable artifacts found.")

    out = pd.concat(parts, ignore_index=True)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    print(out.to_string(index=False))
    print(f"\nWrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
