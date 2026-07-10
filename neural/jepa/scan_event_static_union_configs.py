from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics, position_exit_minute, score_metrics


_WORKER_FRAME: pd.DataFrame | None = None
_WORKER_ARGS: argparse.Namespace | None = None


def parse_named_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Expected NAME=PATH, got {value!r}")
    name, raw = value.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"Empty source name in {value!r}")
    return name, Path(raw.strip())


def resolve_trade_file(path: Path) -> Path:
    if path.is_file():
        return path
    for name in (
        "event_option_gate_trades.csv",
        "static_union_trades.csv",
        "daily_source_router_trades.csv",
        "monthly_volume_backfill_trades.csv",
        "nested_volume_backfill_trades.csv",
        "intraday_circuit_trades.csv",
        "selected_trades.csv",
        "combined_trades.csv",
    ):
        candidate = path / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(path)


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


def derive_minute(df: pd.DataFrame) -> pd.Series:
    out = pd.Series(np.nan, index=df.index, dtype=float)
    for col in ("entry_minute", "minute", "minute_x", "minute_y"):
        if col in df.columns:
            cand = pd.to_numeric(df[col], errors="coerce")
            out = out.where(out.notna(), cand)
    missing = out.isna()
    if missing.any() and "time" in df.columns:
        parsed = pd.to_datetime(df.loc[missing, "time"].astype(str), format="%H:%M", errors="coerce")
        out.loc[missing] = parsed.dt.hour * 60 + parsed.dt.minute
    return out.fillna(0).astype(int)


def load_source(spec: str, priority: int, months: set[str], tickers: set[str]) -> pd.DataFrame:
    name, path = parse_named_path(spec)
    trade_file = resolve_trade_file(path)
    df = pd.read_csv(trade_file, dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str}, low_memory=False)
    required = {"ticker", "date", "time", "action", "realized_return"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{trade_file} missing required columns {missing}")
    if "test_month" not in df.columns:
        df["test_month"] = df["month"].astype(str)
    if "month" not in df.columns:
        df["month"] = df["test_month"].astype(str)
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df["month"] = df["test_month"].astype(str)
    df["test_month"] = df["test_month"].astype(str)
    df = df[df["ticker"].isin(tickers) & df["test_month"].isin(months)].copy()
    if df.empty:
        return df
    df["date"] = df["date"].astype(str)
    df["time"] = df["time"].astype(str)
    df["action"] = df["action"].astype(str).str.upper()
    df["expiry_mode"] = df["expiry_mode"].astype(str) if "expiry_mode" in df.columns else ""
    df["realized_return"] = pd.to_numeric(df["realized_return"], errors="coerce").fillna(0.0)
    df["entry_minute"] = derive_minute(df)
    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0.0) if "score" in df.columns else 0.0
    df["union_source"] = name
    df["union_source_priority"] = int(priority)
    df["union_source_file"] = str(trade_file)
    df["_source_order"] = np.arange(len(df), dtype=np.int64)
    return df.reset_index(drop=True)


def apply_union(
    frame: pd.DataFrame,
    order: tuple[str, ...],
    max_day: int,
    cooldown: int,
    min_score: float,
    daily_order: str,
    *,
    allow_overlapping_positions: bool = False,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    priority = {name: idx for idx, name in enumerate(order)}
    work = frame[frame["union_source"].isin(priority)].copy()
    if np.isfinite(float(min_score)):
        work = work[pd.to_numeric(work["score"], errors="coerce").fillna(float("-inf")) >= float(min_score)].copy()
    if work.empty:
        return work
    if not bool(allow_overlapping_positions) and "exit_minutes" not in work.columns:
        raise ValueError(
            "static union selection requires exit_minutes for live-equivalent one-position replay; "
            "use allow_overlapping_positions=True only for research diagnostics"
        )
    work["config_priority"] = work["union_source"].map(priority).astype(int)
    if str(daily_order) == "score_desc":
        ordered = work.sort_values(
            ["ticker", "date", "score", "entry_minute", "config_priority", "_source_order"],
            ascending=[True, True, False, True, True, True],
            kind="stable",
        )
    elif str(daily_order) == "time_asc":
        ordered = work.sort_values(
            ["ticker", "date", "entry_minute", "config_priority", "score", "_source_order"],
            ascending=[True, True, True, True, False, True],
            kind="stable",
        )
    else:
        raise ValueError(f"Unknown daily_order {daily_order!r}")
    rows: list[dict] = []
    for (_, date), day in ordered.groupby(["ticker", "date"], sort=False):
        next_allowed = -1
        selected_minutes: list[int] = []
        selected_intervals: list[tuple[int, int]] = []
        taken = 0
        seen: set[tuple[str, str, str]] = set()
        for row in day.itertuples(index=False):
            minute = int(row.entry_minute)
            if taken >= int(max_day):
                break
            key = (str(row.time), str(row.action), str(row.expiry_mode))
            if key in seen:
                continue
            if str(daily_order) == "score_desc":
                if int(cooldown) > 0 and any(abs(minute - seen_minute) < int(cooldown) for seen_minute in selected_minutes):
                    continue
            elif minute < next_allowed:
                continue
            rec = row._asdict()
            position_until = position_exit_minute(
                minute,
                rec.get("exit_minutes"),
                allow_overlapping_positions=bool(allow_overlapping_positions),
            )
            if not bool(allow_overlapping_positions) and any(
                minute < prior_end and position_until > prior_start
                for prior_start, prior_end in selected_intervals
            ):
                continue
            rec["union_config_sources"] = ",".join(order)
            rec["union_config_max_day"] = int(max_day)
            rec["union_config_cooldown"] = int(cooldown)
            rec["union_config_min_score"] = float(min_score)
            rec["union_config_daily_order"] = str(daily_order)
            rec["union_config_position_exit_minute"] = int(position_until)
            rows.append(rec)
            seen.add(key)
            selected_minutes.append(minute)
            selected_intervals.append((minute, position_until))
            taken += 1
            next_allowed = max(minute + int(cooldown), position_until)
    return pd.DataFrame(rows) if rows else work.iloc[0:0].copy()


def metric_prefix(row: dict, prefix: str) -> dict[str, float]:
    return {f"{prefix}_{key}": value for key, value in row.items()}


def passes(row: dict, min_wr: float, min_pf: float, min_month_trades: int) -> bool:
    return (
        int(row.get("trades", 0)) > 0
        and float(row.get("pnl_return", 0.0)) > 0.0
        and np.isfinite(float(row.get("win_rate", float("nan"))))
        and np.isfinite(float(row.get("profit_factor", float("nan"))))
        and float(row["win_rate"]) >= float(min_wr)
        and float(row["profit_factor"]) >= float(min_pf)
        and int(row.get("min_month_trades", 0)) >= int(min_month_trades)
    )


def score_select(row: dict, args: argparse.Namespace) -> float:
    strict = score_metrics(
        row,
        int(args.min_select_trades),
        int(args.min_month_trades),
        float(args.min_profit_factor),
        float(args.min_win_rate),
        float(args.min_call_rate),
        float(args.max_call_rate),
    )
    if str(args.rank_mode) == "strict":
        return strict

    trades = float(row.get("trades", 0.0) or 0.0)
    wr = float(row.get("win_rate", 0.0) or 0.0)
    pf = float(row.get("profit_factor", 0.0) or 0.0)
    pnl = float(row.get("pnl_return", 0.0) or 0.0)
    min_month = float(row.get("min_month_trades", 0.0) or 0.0)
    call_rate = float(row.get("call_rate", 0.0) or 0.0)
    pos_month = float(row.get("positive_month_rate", 0.0) or 0.0)
    if not np.isfinite(pf):
        pf = 3.0 if trades > 0.0 and pnl > 0.0 else 0.0
    if not np.isfinite(wr):
        wr = 0.0
    if not np.isfinite(call_rate):
        call_rate = 0.0
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


def candidate_configs(source_names: list[str], args: argparse.Namespace) -> list[tuple[tuple[str, ...], int, int, float, str]]:
    configs: list[tuple[tuple[str, ...], int, int, float, str]] = []
    min_sources = max(1, int(args.min_sources))
    max_sources = min(len(source_names), int(args.max_sources))
    for size in range(min_sources, max_sources + 1):
        for subset in itertools.combinations(source_names, size):
            orders = itertools.permutations(subset) if bool(args.permute_sources) else [tuple(subset)]
            for order in orders:
                for max_day in [int(x) for x in args.max_day_grid]:
                    for cooldown in [int(x) for x in args.cooldown_grid]:
                        for min_score in [float(x) for x in args.min_score_grid]:
                            for daily_order in [str(x) for x in args.daily_order_grid]:
                                configs.append((tuple(order), int(max_day), int(cooldown), float(min_score), str(daily_order)))
    return configs


def scan_candidate(
    frame: pd.DataFrame,
    ticker: str,
    config: tuple[tuple[str, ...], int, int, float, str],
    args: argparse.Namespace,
) -> dict:
    select_months = month_range(str(args.select_start_month), str(args.select_end_month))
    test1_months = month_range(str(args.test1_start_month), str(args.test1_end_month))
    test2_months = month_range(str(args.test2_start_month), str(args.test2_end_month))
    order, max_day, cooldown, min_score, daily_order = config
    selected = apply_union(
        frame,
        tuple(order),
        int(max_day),
        int(cooldown),
        float(min_score),
        str(daily_order),
        allow_overlapping_positions=bool(args.allow_overlapping_positions),
    )
    select = selected[selected["test_month"].astype(str).isin(select_months)].copy()
    test1 = selected[selected["test_month"].astype(str).isin(test1_months)].copy()
    test2 = selected[selected["test_month"].astype(str).isin(test2_months)].copy()
    m_select = metrics(select, select_months)
    m_test1 = metrics(test1, test1_months)
    m_test2 = metrics(test2, test2_months)
    select_score = score_select(m_select, args)
    row = {
        "ticker": ticker,
        "sources": ",".join(order),
        "source_count": len(order),
        "max_day": int(max_day),
        "cooldown": int(cooldown),
        "min_score": float(min_score),
        "daily_order": str(daily_order),
        "select_score": float(select_score),
        "select_pass": passes(m_select, float(args.min_win_rate), float(args.min_profit_factor), int(args.min_month_trades)),
        "test1_pass": passes(m_test1, float(args.min_win_rate), float(args.min_profit_factor), int(args.min_month_trades)),
        "test2_pass": passes(m_test2, float(args.min_win_rate), float(args.min_profit_factor), int(args.min_month_trades)),
    }
    row.update(metric_prefix(m_select, "select"))
    row.update(metric_prefix(m_test1, "test1"))
    row.update(metric_prefix(m_test2, "test2"))
    return row


def init_worker(frame: pd.DataFrame, args_dict: dict) -> None:
    global _WORKER_FRAME, _WORKER_ARGS
    _WORKER_FRAME = frame
    _WORKER_ARGS = argparse.Namespace(**args_dict)


def scan_candidate_worker(item: tuple[str, tuple[tuple[str, ...], int, int, float, str]]) -> dict:
    if _WORKER_FRAME is None or _WORKER_ARGS is None:
        raise RuntimeError("Worker not initialized.")
    ticker, config = item
    return scan_candidate(_WORKER_FRAME, str(ticker), config, _WORKER_ARGS)


def scan_ticker(ticker: str, frame: pd.DataFrame, source_names: list[str], args: argparse.Namespace) -> pd.DataFrame:
    configs = candidate_configs(source_names, args)
    if not configs:
        return pd.DataFrame()
    workers = max(1, min(int(args.workers), len(configs)))
    if workers <= 1:
        rows = [scan_candidate(frame, ticker, config, args) for config in configs]
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=init_worker,
            initargs=(frame, vars(args)),
        ) as executor:
            rows = list(
                executor.map(
                    scan_candidate_worker,
                    [(ticker, config) for config in configs],
                    chunksize=max(1, int(args.chunksize)),
                )
            )

    ranked = pd.DataFrame(rows).sort_values(
        ["select_pass", "select_score", "select_profit_factor", "select_pnl_return"],
        ascending=[False, False, False, False],
        kind="stable",
    )
    return ranked


def write_summary(output_dir: Path, selected: pd.DataFrame, combined: pd.DataFrame, args: argparse.Namespace) -> None:
    test1_months = month_range(str(args.test1_start_month), str(args.test1_end_month))
    test2_months = month_range(str(args.test2_start_month), str(args.test2_end_month))
    selected_rows = []
    for ticker, part in combined.groupby("ticker", sort=True):
        selected_rows.append(
            {
                "ticker": ticker,
                **metric_prefix(metrics(part[part["test_month"].astype(str).isin(test1_months)], test1_months), "test1"),
                **metric_prefix(metrics(part[part["test_month"].astype(str).isin(test2_months)], test2_months), "test2"),
            }
        )
    payload = {
        "selected_configs": selected.to_dict(orient="records"),
        "per_ticker_forward": selected_rows,
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Static Union Config Scan",
        "",
        "Scans fixed-priority unions of precomputed OOS event-option streams. Configs are ranked by the select window only; test windows are reported forward.",
        "",
        "## Selected Configs",
        "",
        "```csv",
        selected.to_csv(index=False),
        "```",
        "",
        "## Per Ticker Forward",
        "",
        "```json",
        json.dumps(selected_rows, indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def selected_folds(selected: pd.DataFrame, source_files: dict[str, Path], args: argparse.Namespace) -> pd.DataFrame:
    rows: list[dict] = []
    if selected.empty:
        return pd.DataFrame()
    select_months = month_range(str(args.select_start_month), str(args.select_end_month))
    test_months = month_range(str(args.test1_start_month), str(args.test1_end_month))
    for cfg in selected.to_dict(orient="records"):
        sources = [part.strip() for part in str(cfg.get("sources", "")).split(",") if part.strip()]
        paths = [source_files[name] for name in sources if name in source_files]
        for month in test_months:
            rows.append(
                {
                    "ticker": str(cfg.get("ticker", "")).upper(),
                    "month": str(month),
                    "test_month": str(month),
                    "mode": "STATIC_UNION_CONFIG_SCAN_SELECTED",
                    "selected_source": ",".join(sources),
                    "source_stream": "event_static_union_config_scan",
                    "source_path": "|".join(str(path) for path in paths),
                    "source_fold_path": "|".join(source_fold_path(path) for path in paths if source_fold_path(path)),
                    "select_months": ",".join(select_months),
                    "max_day": int(cfg.get("max_day", 0)),
                    "cooldown": int(cfg.get("cooldown", 0)),
                    "min_score": float(cfg.get("min_score", float("nan"))),
                    "daily_order": str(cfg.get("daily_order", "")),
                    "select_score": float(cfg.get("select_score", float("nan"))),
                    "select_trades": cfg.get("select_trades", ""),
                    "select_win_rate": cfg.get("select_win_rate", ""),
                    "select_profit_factor": cfg.get("select_profit_factor", ""),
                    "select_pnl_return": cfg.get("select_pnl_return", ""),
                }
            )
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal select-window scan of fixed static unions over OOS event-option streams.")
    parser.add_argument("--source", action="append", required=True, help="NAME=trade_csv_or_result_dir")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--select-start-month", default="202401")
    parser.add_argument("--select-end-month", default="202412")
    parser.add_argument("--test1-start-month", default="202501")
    parser.add_argument("--test1-end-month", default="202512")
    parser.add_argument("--test2-start-month", default="202601")
    parser.add_argument("--test2-end-month", default="202606")
    parser.add_argument("--max-sources", type=int, default=2)
    parser.add_argument("--min-sources", type=int, default=1)
    parser.add_argument("--permute-sources", action="store_true")
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[2, 3, 4, 6, 999])
    parser.add_argument("--cooldown-grid", nargs="+", type=int, default=[0, 15, 30, 45])
    parser.add_argument("--min-score-grid", nargs="+", type=float, default=[float("-inf"), 0.0, 0.10, 0.20, 0.30, 0.40])
    parser.add_argument("--daily-order-grid", nargs="+", default=["time_asc"], choices=["time_asc", "score_desc"])
    parser.add_argument(
        "--allow-overlapping-positions",
        action="store_true",
        help="Research diagnostics only: ignore exit_minutes and permit overlapping same-ticker positions.",
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--chunksize", type=int, default=8)
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-select-trades", type=int, default=216)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--rank-mode", choices=["strict", "continuous"], default="strict")
    parser.add_argument("--top-n", type=int, default=25)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tickers = {str(t).upper() for t in args.tickers}
    months = set(
        month_range(str(args.select_start_month), str(args.select_end_month))
        + month_range(str(args.test1_start_month), str(args.test1_end_month))
        + month_range(str(args.test2_start_month), str(args.test2_end_month))
    )
    parsed_sources = [parse_named_path(spec) for spec in args.source]
    source_files = {name: resolve_trade_file(path) for name, path in parsed_sources}
    parts = [load_source(spec, idx, months, tickers) for idx, spec in enumerate(args.source)]
    parts = [part for part in parts if not part.empty]
    if not parts:
        raise RuntimeError("No source trades loaded.")
    all_trades = pd.concat(parts, ignore_index=True, sort=False)
    source_names = [parse_named_path(spec)[0] for spec in args.source]
    all_trades.to_parquet(output_dir / "loaded_source_trades.parquet", index=False)

    selected_config_rows: list[pd.DataFrame] = []
    combined_parts: list[pd.DataFrame] = []
    for ticker in sorted(tickers):
        ticker_frame = all_trades[all_trades["ticker"].astype(str).eq(ticker)].copy()
        ranked = scan_ticker(ticker, ticker_frame, source_names, args)
        ranked.to_csv(output_dir / f"{ticker.lower()}_config_scan.csv", index=False)
        ranked.head(int(args.top_n)).to_csv(output_dir / f"{ticker.lower()}_top_configs.csv", index=False)
        if not ranked.empty:
            selected_row = ranked.head(1).copy()
            selected_config_rows.append(selected_row)
            cfg = selected_row.iloc[0]
            selected_trades = apply_union(
                ticker_frame,
                tuple(str(cfg["sources"]).split(",")),
                int(cfg["max_day"]),
                int(cfg["cooldown"]),
                float(cfg["min_score"]),
                str(cfg["daily_order"]),
                allow_overlapping_positions=bool(args.allow_overlapping_positions),
            )
            selected_trades["selected_by"] = "ranked_select_window"
            combined_parts.append(selected_trades)

    selected = pd.concat(selected_config_rows, ignore_index=True, sort=False) if selected_config_rows else pd.DataFrame()
    combined = pd.concat(combined_parts, ignore_index=True, sort=False) if combined_parts else pd.DataFrame()
    selected.to_csv(output_dir / "selected_by_2024_configs.csv", index=False)
    combined.to_csv(output_dir / "selected_by_2024_trades.csv", index=False)
    folds = selected_folds(selected, source_files, args)
    if not folds.empty:
        folds.to_csv(output_dir / "selected_config_folds.csv", index=False)
    write_summary(output_dir, selected, combined, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
