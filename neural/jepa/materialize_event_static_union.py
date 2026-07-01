from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


def parse_named_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Expected NAME=PATH, got {value!r}")
    name, raw_path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"Empty source name in {value!r}")
    return name, Path(raw_path.strip())


def parse_month_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, float) and math.isnan(value):
        return []
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    return [part.strip() for part in text.replace('"', "").split(",") if part.strip()]


def source_fold_path(path: Path) -> str:
    if path.name == "event_option_gate_trades.csv":
        candidate = path.with_name("fold_configs.csv")
    elif path.name == "stream_selector_trades.csv":
        candidate = path.with_name("stream_selector_folds.csv")
    elif path.name == "trade_union_topk_regressor_trades.csv":
        candidate = path.with_name("trade_union_topk_regressor_folds.csv")
    elif path.name == "intraday_circuit_trades.csv":
        candidate = path.with_name("intraday_circuit_folds.csv")
    elif path.name == "daily_source_router_trades.csv":
        candidate = path.with_name("daily_source_router_folds.csv")
    elif path.name == "static_union_trades.csv":
        candidate = path.with_name("static_union_folds.csv")
    else:
        candidate = path.with_name("fold_configs.csv")
    return str(candidate) if candidate.exists() else ""


def minute_from_time(values: pd.Series) -> pd.Series:
    parts = values.astype(str).str.extract(r"(?P<h>\d{1,2}):(?P<m>\d{2})")
    hour = pd.to_numeric(parts["h"], errors="coerce")
    minute = pd.to_numeric(parts["m"], errors="coerce")
    return hour * 60 + minute


def normalized_minutes(frame: pd.DataFrame) -> pd.Series:
    for col in ("entry_minute", "minute", "minute_x", "minute_y", "known_minute"):
        if col in frame.columns:
            values = pd.to_numeric(frame[col], errors="coerce")
            if values.notna().any():
                return values
    if "time" in frame.columns:
        values = minute_from_time(frame["time"])
        if values.notna().any():
            return values
    return pd.Series(np.arange(len(frame), dtype=np.int64), index=frame.index)


def normalized_score(frame: pd.DataFrame) -> pd.Series:
    for col in ("score", "action_score_mean", "action_score_max", "pred_score", "edge_score", "select_score"):
        if col in frame.columns:
            values = pd.to_numeric(frame[col], errors="coerce")
            if values.notna().any():
                return values.fillna(0.0)
    return pd.Series(np.zeros(len(frame), dtype=float), index=frame.index)


def load_source(name: str, path: Path, ticker: str, months: list[str], priority: int) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, dtype={"ticker": str, "date": str, "month": str, "time": str, "test_month": str})
    required = {"ticker", "date", "month", "time", "action", "realized_return"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")
    frame = frame.copy()
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["month"] = frame["month"].astype(str)
    if "test_month" not in frame.columns:
        frame["test_month"] = frame["month"]
    frame["test_month"] = frame["test_month"].astype(str)
    frame = frame[frame["ticker"].eq(ticker) & frame["month"].isin(months)].copy()
    frame["realized_return"] = pd.to_numeric(frame["realized_return"], errors="coerce").fillna(0.0)
    if "candidate_id" not in frame.columns:
        frame["candidate_id"] = np.arange(len(frame), dtype=np.int64)
    if "expiry_mode" not in frame.columns:
        frame["expiry_mode"] = ""
    frame["static_union_source"] = name
    frame["static_union_source_path"] = str(path)
    frame["static_union_source_fold_path"] = source_fold_path(path)
    frame["_source_priority"] = int(priority)
    frame["_source_row"] = np.arange(len(frame), dtype=np.int64)
    frame["_minute"] = normalized_minutes(frame).fillna(999999).astype(float)
    frame["_score"] = normalized_score(frame).fillna(0.0).astype(float)
    return frame


def materialize_union(
    frame: pd.DataFrame,
    max_trades_per_day: int,
    min_score: float,
    daily_order: str,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    work = frame[pd.to_numeric(frame["_score"], errors="coerce").fillna(0.0) >= float(min_score)].copy()
    if daily_order == "score_desc":
        sort_cols = ["date", "_score", "_minute", "_source_priority", "_source_row"]
        ascending = [True, False, True, True, True]
    else:
        sort_cols = ["date", "_minute", "_source_priority", "_score", "_source_row"]
        ascending = [True, True, True, False, True]
    work = work.sort_values(sort_cols, ascending=ascending, kind="stable")
    dedupe_cols = [col for col in ("date", "time", "action", "expiry_mode") if col in work.columns]
    if dedupe_cols:
        work = work.drop_duplicates(dedupe_cols, keep="first")
    if int(max_trades_per_day) > 0 and int(max_trades_per_day) < 999:
        work = work.groupby("date", group_keys=False).head(int(max_trades_per_day))
    return work.reset_index(drop=True)


def monthly_metrics(trades: pd.DataFrame, months: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for month in months:
        item = metrics(trades[trades["month"].astype(str).eq(month)].copy(), [month])
        item["month"] = month
        rows.append(item)
    return rows


def source_contribution_rows(
    selected: pd.DataFrame,
    source_specs: dict[str, Path],
    ticker: str,
    test_months: list[str],
    select_months: list[str],
    config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if selected.empty:
        return pd.DataFrame()
    select_text = ",".join(select_months)
    union_sources = ",".join(config["sources_order"])
    for month in test_months:
        month_part = selected[selected["month"].astype(str).eq(month)].copy()
        for source in config["sources_order"]:
            part = month_part[month_part["static_union_source"].astype(str).eq(source)].copy()
            if part.empty:
                continue
            source_path = source_specs[source]
            row = metrics(part, [month])
            rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "test_month": month,
                    "mode": "STATIC_UNION_SELECTED_PRETEST",
                    "selected_source": source,
                    "source_path": str(source_path),
                    "source_fold_path": source_fold_path(source_path),
                    "source_priority": int(config["sources_order"].index(source)),
                    "union_sources": union_sources,
                    "select_months": select_text,
                    "max_trades_per_day": int(config["max_trades_per_day"]),
                    "min_score": float(config["min_score"]),
                    "daily_order": str(config["daily_order"]),
                    "contrib_trades": int(row["trades"]),
                    "contrib_win_rate": float(row["win_rate"]),
                    "contrib_profit_factor": float(row["profit_factor"]),
                    "contrib_pnl_return": float(row["pnl_return"]),
                    "contrib_call_rate": float(row["call_rate"]),
                }
            )
    return pd.DataFrame(rows)


def write_summary(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Static Event Option Union",
        "",
        "This artifact applies a fixed, predeclared source order to existing OOS event-option streams. It does not train a model.",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(payload["config"], indent=2, allow_nan=True),
        "```",
        "",
        "## Select Window",
        "",
        "```json",
        json.dumps(payload["select_metrics"], indent=2, allow_nan=True),
        "```",
        "",
        "## Test Window",
        "",
        "```json",
        json.dumps(payload["test_metrics"], indent=2, allow_nan=True),
        "```",
        "",
        "## Monthly Test Metrics",
        "",
        "| Month | Trades | WR | PF | PnL Return | Call Rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["test_monthly"]:
        lines.append(
            f"| {row['month']} | {int(row['trades'])} | {float(row['win_rate']):.2%} | "
            f"{float(row['profit_factor']):.3f} | {float(row['pnl_return']):.3f} | "
            f"{float(row['call_rate']):.2%} |"
        )
    lines += [
        "",
        "## Source Contributions",
        "",
        "```json",
        json.dumps(payload["source_contributions"], indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize a fixed static union of event-option trade streams.")
    parser.add_argument("--source", action="append", required=True, help="NAME=path/to/trades.csv")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--select-start-month", required=True)
    parser.add_argument("--select-end-month", required=True)
    parser.add_argument("--test-start-month", required=True)
    parser.add_argument("--test-end-month", required=True)
    parser.add_argument("--sources-order", nargs="+", default=[])
    parser.add_argument("--max-trades-per-day", type=int, default=999)
    parser.add_argument("--min-score", type=float, default=-999999.0)
    parser.add_argument("--daily-order", choices=["time_asc", "score_desc"], default="time_asc")
    args = parser.parse_args()

    ticker = str(args.ticker).upper()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    select_months = month_range(str(args.select_start_month), str(args.select_end_month))
    test_months = month_range(str(args.test_start_month), str(args.test_end_month))
    all_months = list(dict.fromkeys(select_months + test_months))

    parsed = [parse_named_path(item) for item in args.source]
    source_specs = {name: path for name, path in parsed}
    sources_order = [str(item) for item in (args.sources_order or [name for name, _ in parsed])]
    missing_order = sorted(set(sources_order).difference(source_specs))
    if missing_order:
        raise ValueError(f"--sources-order contains unknown source(s): {missing_order}")

    frames = [
        load_source(name, source_specs[name], ticker, all_months, priority)
        for priority, name in enumerate(sources_order)
    ]
    loaded = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    selected = materialize_union(loaded, int(args.max_trades_per_day), float(args.min_score), str(args.daily_order))
    select_trades = selected[selected["month"].astype(str).isin(select_months)].copy()
    test_trades = selected[selected["month"].astype(str).isin(test_months)].copy()

    drop_internal = [col for col in selected.columns if str(col).startswith("_")]
    selected.drop(columns=drop_internal, errors="ignore").to_csv(output_dir / "static_union_all_trades.csv", index=False)
    select_trades.drop(columns=drop_internal, errors="ignore").to_csv(output_dir / "static_union_select_trades.csv", index=False)
    test_out = test_trades.drop(columns=drop_internal, errors="ignore")
    test_out.to_csv(output_dir / "static_union_trades.csv", index=False)
    test_out.to_csv(output_dir / "combined_trades.csv", index=False)

    config = {
        "ticker": ticker,
        "sources": {name: str(path) for name, path in source_specs.items()},
        "source_fold_paths": {name: source_fold_path(path) for name, path in source_specs.items()},
        "sources_order": sources_order,
        "select_months": select_months,
        "test_months": test_months,
        "max_trades_per_day": int(args.max_trades_per_day),
        "min_score": float(args.min_score),
        "daily_order": str(args.daily_order),
    }
    folds = source_contribution_rows(test_trades, source_specs, ticker, test_months, select_months, config)
    folds.to_csv(output_dir / "static_union_folds.csv", index=False)
    folds.to_csv(output_dir / "combined_folds.csv", index=False)

    source_contrib = (
        test_trades.groupby(["month", "static_union_source"]).size().rename("trades").reset_index().to_dict(orient="records")
        if not test_trades.empty
        else []
    )
    payload = {
        "config": config,
        "loaded_rows": int(len(loaded)),
        "selected_rows": int(len(selected)),
        "select_metrics": metrics(select_trades, select_months),
        "test_metrics": metrics(test_trades, test_months),
        "select_monthly": monthly_metrics(select_trades, select_months),
        "test_monthly": monthly_metrics(test_trades, test_months),
        "source_contributions": source_contrib,
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(output_dir, payload)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
