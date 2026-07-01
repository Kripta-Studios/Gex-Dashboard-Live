from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range


TRADE_FILE_CANDIDATES = (
    "combined_trades.csv",
    "trade_union_topk_regressor_trades.csv",
    "intraday_circuit_trades.csv",
    "event_option_gate_trades.csv",
    "stream_selector_trades.csv",
    "selected_trades.csv",
)


def parse_source(value: str) -> tuple[str, str, Path]:
    if ":" not in value or "=" not in value:
        raise ValueError(f"Expected TICKER:NAME=PATH, got {value!r}")
    ticker, rest = value.split(":", 1)
    name, raw_path = rest.split("=", 1)
    ticker = ticker.strip().upper()
    name = name.strip()
    if not ticker or not name:
        raise ValueError(f"Expected non-empty ticker/name in {value!r}")
    return ticker, name, Path(raw_path.strip())


def resolve_trade_file(path: Path) -> Path:
    if path.is_file():
        return path
    for candidate in TRADE_FILE_CANDIDATES:
        item = path / candidate
        if item.exists():
            return item
    raise FileNotFoundError(path)


def derive_minute(frame: pd.DataFrame) -> pd.Series:
    out = pd.Series(np.nan, index=frame.index, dtype=float)
    for col in ("minute", "entry_minute", "minute_x", "minute_y", "known_minute"):
        if col in frame.columns:
            out = out.fillna(pd.to_numeric(frame[col], errors="coerce"))
    if "time" in frame.columns:
        parsed = pd.to_datetime(frame["time"].astype(str), format="%H:%M", errors="coerce")
        out = out.fillna(parsed.dt.hour * 60 + parsed.dt.minute)
    return out.fillna(0).astype(int)


def load_source(ticker: str, name: str, path: Path) -> pd.DataFrame:
    trade_file = resolve_trade_file(path)
    frame = pd.read_csv(
        trade_file,
        dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str},
        low_memory=False,
    )
    if "ticker" in frame.columns:
        frame = frame[frame["ticker"].astype(str).str.upper().eq(ticker)].copy()
    if "test_month" not in frame.columns and "month" in frame.columns:
        frame["test_month"] = frame["month"].astype(str)
    if "month" not in frame.columns and "test_month" in frame.columns:
        frame["month"] = frame["test_month"].astype(str)
    if "date" not in frame.columns:
        raise ValueError(f"{trade_file} needs a date column")
    frame["ticker"] = ticker
    frame["source_name"] = name
    frame["source_path"] = str(path)
    frame["month"] = frame["month"].astype(str)
    frame["test_month"] = frame["test_month"].astype(str)
    frame["_minute"] = derive_minute(frame)
    frame["_score"] = pd.to_numeric(frame.get("score"), errors="coerce").fillna(0.0)
    frame["_return"] = pd.to_numeric(frame["realized_return"], errors="coerce").fillna(0.0)
    return frame


def cap_trades(frame: pd.DataFrame, months: list[str], cap: int, order: str) -> pd.DataFrame:
    work = frame[frame["test_month"].astype(str).isin(months) | frame["month"].astype(str).isin(months)].copy()
    if work.empty:
        return work
    if order == "score_desc":
        work = work.sort_values(["date", "_score", "_minute"], ascending=[True, False, True])
    elif order == "time_asc":
        work = work.sort_values(["date", "_minute", "_score"], ascending=[True, True, False])
    else:
        raise ValueError(f"Unknown order {order!r}")
    return work.groupby("date", group_keys=False).head(int(cap)).copy()


def metrics(trades: pd.DataFrame, months: list[str]) -> dict[str, float]:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": float("nan"),
            "profit_factor": float("nan"),
            "pnl_return": 0.0,
            "min_month_trades": 0,
            "call_rate": float("nan"),
            "positive_months": 0,
            "top5_share_of_pnl": float("nan"),
            "drawdown_to_pnl": float("inf"),
            "first_3_month_share": float("nan"),
        }
    returns = trades["_return"].astype(float)
    gross_profit = float(returns[returns > 0.0].sum())
    gross_loss = float(-returns[returns < 0.0].sum())
    month_counts = trades.groupby("month").size().reindex(months, fill_value=0)
    month_pnl = trades.groupby("month")["_return"].sum().reindex(months, fill_value=0.0)
    daily = trades.groupby("date")["_return"].sum().sort_index()
    pnl = float(returns.sum())
    equity = daily.cumsum()
    drawdown = float((equity - equity.cummax()).min()) if len(equity) else 0.0
    top5 = float(daily.nlargest(min(5, len(daily))).sum()) if len(daily) else 0.0
    action = trades["action"].astype(str).str.upper() if "action" in trades.columns else pd.Series(dtype=str)
    return {
        "trades": int(len(trades)),
        "win_rate": float((returns > 0.0).mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf"),
        "pnl_return": pnl,
        "min_month_trades": int(month_counts.min()),
        "call_rate": float((action == "CALL").mean()) if len(action) else float("nan"),
        "positive_months": int((month_pnl > 0.0).sum()),
        "top5_share_of_pnl": float(top5 / pnl) if pnl > 0.0 else float("nan"),
        "drawdown_to_pnl": float(abs(drawdown) / pnl) if pnl > 0.0 else float("inf"),
        "first_3_month_share": float(month_pnl.iloc[:3].sum() / pnl) if pnl > 0.0 else float("nan"),
    }


def gate_pass(row: dict[str, float], args: argparse.Namespace) -> bool:
    return bool(
        float(row["win_rate"]) >= float(args.min_win_rate)
        and float(row["profit_factor"]) >= float(args.min_profit_factor)
        and int(row["min_month_trades"]) >= int(args.min_month_trades)
        and float(args.min_call_rate) <= float(row["call_rate"]) <= float(args.max_call_rate)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan deterministic daily caps over event-option trade streams.")
    parser.add_argument("--source", action="append", required=True, help="TICKER:NAME=path")
    parser.add_argument("--output", required=True)
    parser.add_argument("--select-start-month", required=True)
    parser.add_argument("--select-end-month", required=True)
    parser.add_argument("--test-start-month", required=True)
    parser.add_argument("--test-end-month", required=True)
    parser.add_argument("--cap-grid", nargs="+", type=int, default=[1, 2, 3, 4, 5, 6, 7, 8])
    parser.add_argument("--orders", nargs="+", default=["score_desc", "time_asc"])
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    args = parser.parse_args()

    select_months = month_range(str(args.select_start_month), str(args.select_end_month))
    test_months = month_range(str(args.test_start_month), str(args.test_end_month))
    rows: list[dict[str, object]] = []
    for spec in args.source:
        ticker, name, path = parse_source(spec)
        frame = load_source(ticker, name, path)
        for order in args.orders:
            for cap in args.cap_grid:
                select_trades = cap_trades(frame, select_months, int(cap), str(order))
                test_trades = cap_trades(frame, test_months, int(cap), str(order))
                select_metrics = metrics(select_trades, select_months)
                test_metrics = metrics(test_trades, test_months)
                rows.append(
                    {
                        "ticker": ticker,
                        "source_name": name,
                        "source_path": str(path),
                        "order": order,
                        "daily_cap": int(cap),
                        "select_pass": gate_pass(select_metrics, args),
                        "test_pass": gate_pass(test_metrics, args),
                        **{f"select_{key}": value for key, value in select_metrics.items()},
                        **{f"test_{key}": value for key, value in test_metrics.items()},
                    }
                )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(rows)
    out.to_csv(output, index=False)
    summary = {
        "output": str(output),
        "rows": int(len(out)),
        "select_months": select_months,
        "test_months": test_months,
        "args": vars(args),
        "select_pass_counts": out.groupby("ticker")["select_pass"].sum().to_dict() if not out.empty else {},
        "test_pass_counts": out.groupby("ticker")["test_pass"].sum().to_dict() if not out.empty else {},
    }
    (output.parent / f"{output.stem}.json").write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")
    print(out.to_string(index=False))
    print(f"\nWrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
