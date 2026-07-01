from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from apply_event_monthly_volume_backfill import apply_backfill
from evaluate_xinput_level_filter import month_range
from materialize_event_static_union import load_source, materialize_union, normalized_minutes
from walkforward_event_option_gate import metrics, score_metrics

_WORKER_LOADED_SOURCES: dict[str, pd.DataFrame] = {}
_WORKER_RAW_SOURCES: dict[str, pd.DataFrame] = {}
_WORKER_PRIMARY_CACHE: dict[tuple[str, float, int, str], pd.DataFrame] = {}
_WORKER_TICKER = ""
_WORKER_MONTHS: list[str] = []


def parse_named_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Expected NAME=PATH, got {value!r}")
    name, raw = value.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"Empty source name in {value!r}")
    return name, Path(raw.strip())


def prefilter_source_path(name: str, path: Path, ticker: str, months: list[str], cache_dir: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    stat = path.stat()
    digest_raw = f"{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|{ticker}|{','.join(months)}"
    digest = hashlib.sha1(digest_raw.encode("utf-8", errors="ignore")).hexdigest()[:12]
    out = cache_dir / f"{ticker.upper()}_{min(months)}_{max(months)}_{name}_{digest}.csv"
    if out.exists():
        return out
    df = pd.read_csv(path, dtype={"ticker": str, "date": str, "month": str, "time": str, "test_month": str})
    if "ticker" not in df.columns or "month" not in df.columns:
        raise ValueError(f"{path} missing ticker/month columns")
    filtered = df[
        df["ticker"].astype(str).str.upper().eq(str(ticker).upper())
        & df["month"].astype(str).isin(months)
    ].copy()
    filtered.to_csv(out, index=False)
    return out


def finite_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def as_bool(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def pass_user(row: dict[str, Any], min_wr: float, min_pf: float, min_month: int, min_call: float, max_call: float) -> bool:
    call_rate = finite_float(row.get("call_rate"), -1.0)
    return (
        int(row.get("trades", 0) or 0) > 0
        and finite_float(row.get("pnl_return"), 0.0) > 0.0
        and finite_float(row.get("win_rate"), 0.0) >= float(min_wr)
        and finite_float(row.get("profit_factor"), 0.0) >= float(min_pf)
        and int(row.get("min_month_trades", 0) or 0) >= int(min_month)
        and float(min_call) <= call_rate <= float(max_call)
    )


def stable_score(row: dict[str, Any], args: argparse.Namespace) -> float:
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
    pf = finite_float(row.get("profit_factor"), 0.0)
    wr = finite_float(row.get("win_rate"), 0.0)
    pnl = finite_float(row.get("pnl_return"), 0.0)
    min_month = finite_float(row.get("min_month_trades"), 0.0)
    call_rate = finite_float(row.get("call_rate"), 0.0)
    pos_month = finite_float(row.get("positive_month_rate"), 0.0)
    score = 8.0 * min(max(pf, 0.0), 3.0) + 18.0 * wr + 0.20 * pnl + 2.0 * pos_month
    score += 0.10 * min(min_month, 60.0)
    score -= 18.0 * max(float(args.min_profit_factor) - pf, 0.0)
    score -= 18.0 * max(float(args.min_win_rate) - wr, 0.0)
    score -= 2.0 * max(float(args.min_month_trades) - min_month, 0.0)
    score -= 12.0 * max(float(args.min_call_rate) - call_rate, 0.0)
    score -= 12.0 * max(call_rate - float(args.max_call_rate), 0.0)
    if pnl <= 0.0:
        score -= 20.0 + abs(pnl)
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


def init_worker(source_specs: dict[str, str], ticker: str, months: list[str]) -> None:
    global _WORKER_LOADED_SOURCES, _WORKER_RAW_SOURCES, _WORKER_PRIMARY_CACHE, _WORKER_TICKER, _WORKER_MONTHS
    _WORKER_TICKER = str(ticker).upper()
    _WORKER_MONTHS = list(months)
    _WORKER_LOADED_SOURCES = {}
    _WORKER_RAW_SOURCES = {}
    _WORKER_PRIMARY_CACHE = {}
    for priority, (name, raw_path) in enumerate(source_specs.items()):
        path = Path(raw_path)
        loaded = load_source(name, path, _WORKER_TICKER, _WORKER_MONTHS, priority)
        _WORKER_LOADED_SOURCES[name] = loaded
        raw = loaded.copy()
        if "entry_minute" not in raw.columns:
            raw["entry_minute"] = normalized_minutes(raw).fillna(0).astype(int)
        raw["source_stream"] = name
        raw["source_file"] = str(path)
        raw["_source_order"] = np.arange(len(raw), dtype=np.int64)
        if "score" in raw.columns:
            raw["score"] = pd.to_numeric(raw["score"], errors="coerce").fillna(0.0)
        elif "_score" in raw.columns:
            raw["score"] = pd.to_numeric(raw["_score"], errors="coerce").fillna(0.0)
        else:
            raw["score"] = 0.0
        _WORKER_RAW_SOURCES[name] = raw


def primary_from_candidate(candidate: dict[str, Any]) -> pd.DataFrame:
    order = tuple(part.strip() for part in str(candidate["sources"]).split(",") if part.strip())
    key = (
        ",".join(order),
        float(candidate.get("min_score", -999999.0)),
        int(candidate.get("max_trades_per_day", 999)),
        str(candidate.get("daily_order", "time_asc")),
    )
    cached = _WORKER_PRIMARY_CACHE.get(key)
    if cached is not None:
        return cached
    frame = pd.concat([_WORKER_LOADED_SOURCES[name].copy() for name in order], ignore_index=True, sort=False)
    frame["_source_priority"] = frame["static_union_source"].map({name: idx for idx, name in enumerate(order)}).astype(int)
    primary = materialize_union(frame, int(key[2]), float(key[1]), str(key[3]))
    if primary.empty:
        _WORKER_PRIMARY_CACHE[key] = primary
        return primary
    primary = primary.copy()
    if "entry_minute" not in primary.columns:
        primary["entry_minute"] = normalized_minutes(primary).fillna(0).astype(int)
    primary["source_stream"] = "primary_static"
    primary["source_file"] = "in_memory_static_union"
    primary["_source_order"] = np.arange(len(primary), dtype=np.int64)
    if "score" in primary.columns:
        primary["score"] = pd.to_numeric(primary["score"], errors="coerce").fillna(0.0)
    elif "_score" in primary.columns:
        primary["score"] = pd.to_numeric(primary["_score"], errors="coerce").fillna(0.0)
    else:
        primary["score"] = 0.0
    _WORKER_PRIMARY_CACHE[key] = primary
    return primary


def evaluate_task(task: dict[str, Any]) -> dict[str, Any]:
    candidate = task["candidate"]
    fallback_name = str(task["fallback"])
    target = int(task["target_month_trades"])
    max_day = int(task["backfill_max_day"])
    cooldown = int(task["cooldown_minutes"])
    primary = primary_from_candidate(candidate)
    fallback = _WORKER_RAW_SOURCES[fallback_name]
    args = SimpleNamespace(
        start_month=str(task["all_start_month"]),
        end_month=str(task["all_end_month"]),
        min_month_trades=target,
        auto_partial_month_target=False,
        partial_month_observed_floor=0,
        backfill_only_partial_months=False,
        max_day=max_day,
        cooldown_minutes=cooldown,
        primary_name="primary_static",
        fallback_name=fallback_name,
        risk_capital=float(task["risk_capital"]),
    )
    selected = apply_backfill(primary, fallback, args)
    select_months = task["select_months"]
    valid_months = task["valid_months"]
    fwd_months = task["forward_months"]
    select = metrics(selected[selected["month"].astype(str).isin(select_months)].copy(), select_months)
    valid = metrics(selected[selected["month"].astype(str).isin(valid_months)].copy(), valid_months)
    fwd = metrics(selected[selected["month"].astype(str).isin(fwd_months)].copy(), fwd_months)
    min_wr = float(task["min_win_rate"])
    min_pf = float(task["min_profit_factor"])
    min_month = int(task["min_month_trades"])
    min_call = float(task["min_call_rate"])
    max_call = float(task["max_call_rate"])
    row: dict[str, Any] = {
        "ticker": _WORKER_TICKER,
        "sources": str(candidate["sources"]),
        "primary_min_score": float(candidate.get("min_score", -999999.0)),
        "primary_max_trades_per_day": int(candidate.get("max_trades_per_day", 999)),
        "primary_daily_order": str(candidate.get("daily_order", "time_asc")),
        "fallback": fallback_name,
        "target_month_trades": target,
        "backfill_max_day": max_day,
        "cooldown_minutes": cooldown,
        "select_user_pass": pass_user(select, min_wr, min_pf, min_month, min_call, max_call),
        "valid_user_pass": pass_user(valid, min_wr, min_pf, min_month, min_call, max_call),
        "forward_user_pass": pass_user(fwd, min_wr, min_pf, min_month, min_call, max_call),
    }
    row["pretest_user_pass"] = bool(row["select_user_pass"] and row["valid_user_pass"])
    row["all_user_pass"] = bool(row["pretest_user_pass"] and row["forward_user_pass"])
    row["select_score"] = stable_score(select, task["score_args"])
    row["valid_score"] = stable_score(valid, task["score_args"])
    row["pretest_score"] = min(float(row["select_score"]), float(row["valid_score"]))
    row.update(metric_fields("sel", select))
    row.update(metric_fields("val", valid))
    row.update(metric_fields("fwd", fwd))
    return row


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


def load_candidates(args: argparse.Namespace) -> pd.DataFrame:
    df = pd.read_csv(args.candidate_csv)
    if bool(args.primary_only_pretest_pass) and "pretest_user_pass" in df.columns:
        df = df[df["pretest_user_pass"].map(as_bool)].copy()
    if bool(args.dedupe_source_sets):
        df["_source_set"] = df["sources"].astype(str).map(lambda s: ",".join(sorted(part.strip() for part in s.split(",") if part.strip())))
        sort_cols = [col for col in ("stability_score", "select_score", "valid_score") if col in df.columns]
        if sort_cols:
            df = df.sort_values(sort_cols + ["sources"], ascending=[False] * len(sort_cols) + [True], kind="stable")
        df = df.drop_duplicates(["_source_set", "min_score", "max_trades_per_day", "daily_order"], keep="first")
    sort_cols = [col for col in ("stability_score", "select_score", "valid_score") if col in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=[False] * len(sort_cols), kind="stable")
    return df.reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Parallel scan for static-union monthly backfill using pretest-only candidate ranking.")
    parser.add_argument("--source", action="append", required=True, help="NAME=path/to/event_option_gate_trades.csv")
    parser.add_argument("--candidate-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--select-start-month", required=True)
    parser.add_argument("--select-end-month", required=True)
    parser.add_argument("--valid-start-month", required=True)
    parser.add_argument("--valid-end-month", required=True)
    parser.add_argument("--forward-start-month", required=True)
    parser.add_argument("--forward-end-month", required=True)
    parser.add_argument("--fallback-name", action="append", default=[])
    parser.add_argument("--target-month-trades-grid", nargs="*", default=[])
    parser.add_argument("--backfill-max-day-grid", nargs="*", default=[])
    parser.add_argument("--cooldown-grid", nargs="*", default=[])
    parser.add_argument("--max-primary-candidates", type=int, default=24)
    parser.add_argument("--workers", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 1)))
    parser.add_argument("--chunksize", type=int, default=32)
    parser.add_argument("--prefilter-source-cache-dir", default="")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-select-trades", type=int, default=100)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--primary-only-pretest-pass", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dedupe-source-sets", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    source_specs = dict(parse_named_path(spec) for spec in args.source)
    candidates = load_candidates(args)
    available_sources = set(source_specs.keys())
    candidate_source_sets = candidates["sources"].astype(str).map(
        lambda value: {part.strip() for part in value.split(",") if part.strip()}
    )
    source_mask = candidate_source_sets.map(lambda names: names.issubset(available_sources))
    dropped = int((~source_mask).sum())
    if dropped:
        print(json.dumps({"dropped_candidates_missing_sources": dropped}, indent=2))
    candidates = candidates[source_mask].copy()
    if int(args.max_primary_candidates) > 0:
        candidates = candidates.head(int(args.max_primary_candidates)).copy()
    if candidates.empty:
        raise ValueError("No primary candidates left after filtering")
    fallback_names = list(args.fallback_name) if args.fallback_name else list(source_specs.keys())
    missing = sorted(set(fallback_names).difference(source_specs.keys()))
    if missing:
        raise ValueError(f"Unknown fallback names: {missing}")
    target_grid = parse_int_grid(args.target_month_trades_grid, [18, 19, 20])
    max_day_grid = parse_int_grid(args.backfill_max_day_grid, [1, 2, 3, 4])
    cooldown_grid = parse_int_grid(args.cooldown_grid, [0, 15, 30])
    select_months = month_range(str(args.select_start_month), str(args.select_end_month))
    valid_months = month_range(str(args.valid_start_month), str(args.valid_end_month))
    forward_months = month_range(str(args.forward_start_month), str(args.forward_end_month))
    all_months = list(dict.fromkeys(select_months + valid_months + forward_months))
    if str(args.prefilter_source_cache_dir).strip():
        cache_dir = Path(str(args.prefilter_source_cache_dir))
        source_specs_str = {
            name: str(prefilter_source_path(name, path, str(args.ticker), all_months, cache_dir))
            for name, path in source_specs.items()
        }
    else:
        source_specs_str = {name: str(path) for name, path in source_specs.items()}
    score_args = SimpleNamespace(
        min_select_trades=int(args.min_select_trades),
        min_month_trades=int(args.min_month_trades),
        min_profit_factor=float(args.min_profit_factor),
        min_win_rate=float(args.min_win_rate),
        min_call_rate=float(args.min_call_rate),
        max_call_rate=float(args.max_call_rate),
    )
    tasks: list[dict[str, Any]] = []
    for candidate in candidates.to_dict(orient="records"):
        for fallback, target, max_day, cooldown in itertools.product(fallback_names, target_grid, max_day_grid, cooldown_grid):
            tasks.append(
                {
                    "candidate": candidate,
                    "fallback": fallback,
                    "target_month_trades": int(target),
                    "backfill_max_day": int(max_day),
                    "cooldown_minutes": int(cooldown),
                    "select_months": select_months,
                    "valid_months": valid_months,
                    "forward_months": forward_months,
                    "all_start_month": min(all_months),
                    "all_end_month": max(all_months),
                    "risk_capital": float(args.risk_capital),
                    "min_win_rate": float(args.min_win_rate),
                    "min_profit_factor": float(args.min_profit_factor),
                    "min_month_trades": int(args.min_month_trades),
                    "min_call_rate": float(args.min_call_rate),
                    "max_call_rate": float(args.max_call_rate),
                    "score_args": score_args,
                }
            )
    print(json.dumps({"candidates": int(len(candidates)), "tasks": int(len(tasks)), "workers": int(args.workers)}, indent=2))

    rows: list[dict[str, Any]] = []
    workers = max(1, int(args.workers))
    if workers == 1:
        init_worker(source_specs_str, str(args.ticker), all_months)
        for idx, task in enumerate(tasks, start=1):
            rows.append(evaluate_task(task))
            if idx % 250 == 0:
                print(f"completed {idx}/{len(tasks)}")
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=init_worker,
            initargs=(source_specs_str, str(args.ticker), all_months),
        ) as executor:
            for idx, row in enumerate(executor.map(evaluate_task, tasks, chunksize=max(1, int(args.chunksize))), start=1):
                rows.append(row)
                if idx % 250 == 0 or idx == len(tasks):
                    print(f"completed {idx}/{len(tasks)}")
    out = pd.DataFrame(rows)
    out = out.sort_values(
        ["pretest_user_pass", "pretest_score", "all_user_pass", "forward_user_pass", "fwd_profit_factor", "fwd_min_month_trades"],
        ascending=[False, False, False, False, False, False],
        kind="stable",
    )
    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False)
    summary = {
        "output_csv": str(output_csv),
        "rows": int(len(out)),
        "pretest_user_pass": int(out["pretest_user_pass"].sum()),
        "forward_user_pass": int(out["forward_user_pass"].sum()),
        "all_user_pass": int(out["all_user_pass"].sum()),
        "top_pretest": out.head(10).to_dict(orient="records"),
        "top_all_pass": out[out["all_user_pass"]].head(10).to_dict(orient="records"),
    }
    print(json.dumps(summary, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
