from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd

from train_backtest_option_policy import (
    _get_premium_at_time,
    _load_daily_greeks,
    normalize_date,
    normalize_ticker,
    time_to_minutes,
)


def load_underlying_paths(data_path: str | Path, candidates: pd.DataFrame) -> dict[tuple[str, str], pd.DataFrame]:
    dates = set(candidates["date"].astype(str).map(normalize_date))
    tickers = set(candidates["ticker"].astype(str).map(normalize_ticker))
    frame = pd.read_parquet(data_path, columns=["ticker", "date", "time", "spot_price"])
    frame["ticker"] = frame["ticker"].map(normalize_ticker)
    frame["date"] = frame["date"].map(normalize_date)
    frame = frame[frame["ticker"].isin(tickers) & frame["date"].isin(dates)].copy()
    frame["minutes"] = frame["time"].map(time_to_minutes).astype(np.int16)
    return {
        (str(ticker), str(date)): day.sort_values("minutes").reset_index(drop=True)
        for (ticker, date), day in frame.groupby(["ticker", "date"], sort=False)
    }


def build_one_day(task: tuple[str, str, pd.DataFrame, pd.DataFrame, str, int, float]) -> dict:
    ticker, date, candidates, day_rows, chunk_path, max_hold_minutes, risk_capital = task
    chunk = Path(chunk_path)
    if candidates.empty or day_rows.empty:
        return {"ticker": ticker, "date": date, "candidates": int(len(candidates)), "states": 0, "status": "empty"}

    _, premium_lookup, greeks_lookup = _load_daily_greeks(date, ticker)
    if premium_lookup is None or greeks_lookup is None:
        return {"ticker": ticker, "date": date, "candidates": int(len(candidates)), "states": 0, "status": "missing_greeks"}

    rows: list[dict] = []
    day_rows = day_rows.sort_values("minutes").reset_index(drop=True)
    for candidate in candidates.itertuples(index=False):
        entry_time = str(candidate.time)
        entry_minute = int(getattr(candidate, "entry_minute", time_to_minutes(entry_time)))
        future = day_rows[
            (day_rows["minutes"].astype(int) > entry_minute)
            & (day_rows["minutes"].astype(int) <= entry_minute + int(max_hold_minutes))
        ]
        if future.empty:
            continue

        side = str(candidate.side)
        right = "CALL" if side == "LONG" else "PUT"
        entry_premium = float(candidate.entry_premium)
        if not np.isfinite(entry_premium) or entry_premium <= 0.0:
            continue
        contracts = int(candidate.contracts)
        strike = float(candidate.actual_strike)
        entry_spot = float(candidate.spot_price)
        side_sign = 1.0 if side == "LONG" else -1.0
        peak = -np.inf
        mae = np.inf
        candidate_start = len(rows)

        for point in future.itertuples(index=False):
            hold_minutes = int(point.minutes) - entry_minute
            premium = _get_premium_at_time(premium_lookup, strike, right, str(point.time))
            if premium is None or premium <= 0.0:
                continue
            pnl_pct = float(np.clip((float(premium) - entry_premium) / entry_premium, -1.0, 10.0))
            pnl_dollars = float(premium - entry_premium) * 100.0 * contracts
            gross_cost = max(1e-9, contracts * entry_premium * 100.0)
            pnl_on_cost = pnl_dollars / gross_cost
            pnl_on_risk = pnl_dollars / float(max(float(risk_capital), 1e-9))
            right_key = right.upper()
            alt_key = right_key[0]
            greeks = (
                greeks_lookup.get((str(point.time), strike, right_key))
                or greeks_lookup.get((str(point.time), strike, alt_key))
                or {}
            )
            spot = float(greeks.get("spot", getattr(point, "spot_price", entry_spot)) or getattr(point, "spot_price", entry_spot))
            spot_return_bps = (spot / entry_spot - 1.0) * 10000.0 if entry_spot > 0.0 else 0.0
            peak = max(peak, pnl_pct)
            mae = min(mae, pnl_pct)
            rows.append(
                {
                    "candidate_id": int(candidate.candidate_id),
                    "signal_id": int(candidate.signal_id),
                    "ticker": ticker,
                    "date": date,
                    "month": str(date)[:6],
                    "entry_time": entry_time,
                    "path_time": str(point.time),
                    "hold_minutes": int(hold_minutes),
                    "side": side,
                    "delta_target": float(candidate.delta_target),
                    "actual_delta_abs_entry": float(candidate.actual_delta_abs),
                    "actual_strike": strike,
                    "entry_premium": entry_premium,
                    "contracts": contracts,
                    "current_premium": float(premium),
                    "premium_ratio": float(premium) / entry_premium,
                    "current_pnl_pct": pnl_pct,
                    "current_pnl_dollars": pnl_dollars,
                    "current_return_on_cost": pnl_on_cost,
                    "current_return_on_risk": pnl_on_risk,
                    "peak_pnl_pct": float(peak),
                    "mae_pnl_pct": float(mae),
                    "drawdown_from_peak": float(max(0.0, peak - pnl_pct)),
                    "current_delta": float(greeks.get("delta", 0.0)),
                    "current_delta_abs": abs(float(greeks.get("delta", 0.0))),
                    "current_iv": float(greeks.get("iv", 0.15)),
                    "current_gamma": float(greeks.get("gamma", 0.0)),
                    "spot_price_path": spot,
                    "spot_return_bps": float(spot_return_bps),
                    "signed_spot_return_bps": float(side_sign * spot_return_bps),
                    "minutes_to_close_path": float(max(0, 960 - int(point.minutes))),
                }
            )

        if len(rows) > candidate_start:
            end = len(rows)
            future_best = np.maximum.accumulate(
                np.asarray([rows[i]["current_return_on_risk"] for i in range(candidate_start, end)], dtype=np.float64)[::-1]
            )[::-1]
            future_best_pct = np.maximum.accumulate(
                np.asarray([rows[i]["current_pnl_pct"] for i in range(candidate_start, end)], dtype=np.float64)[::-1]
            )[::-1]
            for offset, row_i in enumerate(range(candidate_start, end)):
                rows[row_i]["future_best_return_on_risk"] = float(future_best[offset])
                rows[row_i]["future_best_pnl_pct"] = float(future_best_pct[offset])
                rows[row_i]["future_edge_return_on_risk"] = float(future_best[offset] - rows[row_i]["current_return_on_risk"])

    if not rows:
        return {"ticker": ticker, "date": date, "candidates": int(len(candidates)), "states": 0, "status": "no_paths"}
    out = pd.DataFrame(rows)
    chunk.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(chunk, index=False)
    return {"ticker": ticker, "date": date, "candidates": int(len(candidates)), "states": int(len(out)), "status": "ok"}


def combine_chunks(chunks_dir: Path, output_path: Path) -> tuple[int, int]:
    chunks = sorted(chunks_dir.glob("*.parquet"))
    if not chunks:
        return 0, 0
    parts = [pd.read_parquet(path) for path in chunks]
    out = pd.concat(parts, ignore_index=True)
    out = out.sort_values(["ticker", "date", "entry_time", "candidate_id", "hold_minutes"]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output_path, index=False)
    return len(chunks), len(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build option premium path-state rows for prebuilt candidates.")
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--data", default="training_data/training_data_spx_qqq_spy.parquet")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202507")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--max-hold-minutes", type=int, default=180)
    parser.add_argument("--risk-capital", type=float, default=1000.0)
    parser.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1))
    parser.add_argument("--backend", choices=["auto", "process", "thread"], default="auto")
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--combine-only", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    chunks_dir = output_dir / "option_path_state_chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "option_path_states.parquet"

    if not bool(args.combine_only):
        candidates = pd.read_parquet(args.candidate_labels)
        candidates["ticker"] = candidates["ticker"].astype(str).map(normalize_ticker)
        candidates["date"] = candidates["date"].map(normalize_date)
        candidates["month"] = candidates["date"].str[:6]
        candidates["entry_minute"] = candidates["time"].map(time_to_minutes).astype(int)
        tickers = {normalize_ticker(t) for t in args.tickers}
        candidates = candidates[
            candidates["ticker"].isin(tickers)
            & (candidates["month"].astype(str) >= str(args.start_month))
            & (candidates["month"].astype(str) <= str(args.end_month))
        ].copy()
        needed = [
            "candidate_id",
            "signal_id",
            "ticker",
            "date",
            "month",
            "time",
            "entry_minute",
            "side",
            "spot_price",
            "delta_target",
            "actual_strike",
            "actual_delta_abs",
            "entry_premium",
            "contracts",
        ]
        candidates = candidates[needed].copy()
        path_groups = load_underlying_paths(args.data, candidates)

        tasks = []
        for (ticker, date), group in candidates.groupby(["ticker", "date"], sort=True):
            chunk = chunks_dir / f"{ticker}_{date}.parquet"
            if chunk.exists() and not bool(args.no_resume):
                continue
            day_rows = path_groups.get((str(ticker), str(date)), pd.DataFrame())
            tasks.append(
                (
                    str(ticker),
                    str(date),
                    group.reset_index(drop=True),
                    day_rows,
                    str(chunk),
                    int(args.max_hold_minutes),
                    float(args.risk_capital),
                )
            )

        start = time.time()
        print(f"[PATH_STATES] tasks={len(tasks)} workers={min(int(args.workers), max(1, len(tasks)))}", flush=True)
        results: list[dict] = []
        if int(args.workers) <= 1 or len(tasks) <= 1:
            for task in tasks:
                result = build_one_day(task)
                results.append(result)
                if len(results) % int(args.progress_every) == 0:
                    print(f"[PATH_STATES] done={len(results)}/{len(tasks)} states={sum(r['states'] for r in results):,}", flush=True)
        else:
            worker_count = min(int(args.workers), len(tasks))
            executor_cls = ProcessPoolExecutor if str(args.backend) in {"auto", "process"} else ThreadPoolExecutor
            try:
                executor = executor_cls(max_workers=worker_count)
            except (PermissionError, OSError) as exc:
                if str(args.backend) == "process":
                    raise
                print(f"[PATH_STATES] process backend unavailable ({exc}); falling back to threads", flush=True)
                executor = ThreadPoolExecutor(max_workers=worker_count)
            with executor:
                futures = [executor.submit(build_one_day, task) for task in tasks]
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    if len(results) % int(args.progress_every) == 0:
                        print(f"[PATH_STATES] done={len(results)}/{len(tasks)} states={sum(r['states'] for r in results):,}", flush=True)

        summary = {
            "args": vars(args),
            "tasks": int(len(tasks)),
            "results": results,
            "states_written_this_run": int(sum(r["states"] for r in results)),
            "elapsed_seconds": float(time.time() - start),
        }
        (output_dir / "path_state_build_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    chunks, rows = combine_chunks(chunks_dir, output_path)
    summary2 = {"chunks": int(chunks), "rows": int(rows), "output": str(output_path)}
    (output_dir / "path_state_combine_summary.json").write_text(json.dumps(summary2, indent=2), encoding="utf-8")
    print(json.dumps(summary2, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
