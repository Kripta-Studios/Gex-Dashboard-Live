from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.train_backtest_option_policy import (  # noqa: E402
    _load_daily_greeks,
    load_path_frame,
    normalize_date,
    normalize_ticker,
    time_to_minutes,
    trade_metrics,
)


def log(message: str) -> None:
    print(message, flush=True)


def month_key(date: str) -> str:
    return normalize_date(date)[:6]


def right_name(value: str) -> str:
    text = str(value).upper()
    return "CALL" if text.startswith("C") else "PUT"


def config_key(config: dict) -> str:
    mode = "lvl" if config["use_level_exit"] else "cap"
    return (
        f"{config['spread_type']}_sd{config['short_delta']:.2f}_ld{config['long_delta']:.2f}_"
        f"hs{config['hard_stop']:.2f}_cap{config['profit_capture']:.2f}_{mode}"
    )


def metrics_score(metrics: dict, min_trades: int, min_long_rate: float, max_long_rate: float) -> float:
    trades = int(metrics.get("trades", 0))
    pnl = float(metrics.get("pnl_dollars", 0.0))
    pf = float(metrics.get("profit_factor", 0.0))
    wr = float(metrics.get("win_rate", 0.0))
    long_rate = float(metrics.get("long_rate", 0.5))
    dd = abs(float(metrics.get("max_drawdown", 0.0)))
    if (
        trades < int(min_trades)
        or pnl <= 0.0
        or not np.isfinite(pf)
        or pf <= 1.0
        or long_rate < min_long_rate
        or long_rate > max_long_rate
    ):
        return -1e9 + pnl
    return pnl / 1000.0 + 100.0 * np.log(max(pf, 1e-6)) + 25.0 * wr + trades / 30.0 - dd / 2500.0


def normalize_signal_frame(candidates: pd.DataFrame, train_start_date: str) -> pd.DataFrame:
    work = candidates.copy()
    work["date"] = work["date"].astype(str).map(normalize_date)
    work["ticker"] = work["ticker"].map(normalize_ticker)
    if "month" not in work.columns:
        work["month"] = work["date"].str.slice(0, 6)
    signal_cols = [
        "signal_id",
        "ticker",
        "date",
        "month",
        "time",
        "side",
        "spot_price",
        "level_target_bps",
        "level_stop_bps",
        "level_config",
        "entry_minute",
    ]
    signal_cols = [c for c in signal_cols if c in work.columns]
    signals = work[signal_cols].drop_duplicates("signal_id", keep="first").copy()
    signals = signals[signals["date"].astype(str) >= normalize_date(train_start_date)].copy()
    if "entry_minute" not in signals.columns:
        signals["entry_minute"] = signals["time"].astype(str).map(time_to_minutes)
    signals["month"] = signals["date"].astype(str).str.slice(0, 6)
    signals["side"] = signals["side"].astype(str).str.upper()
    signals = signals.sort_values(["date", "time", "ticker", "signal_id"]).reset_index(drop=True)
    return signals


def build_price_lookup(df_greeks: pd.DataFrame) -> dict[tuple[str, float, str], dict[str, float]]:
    lookup: dict[tuple[str, float, str], dict[str, float]] = {}
    valid = df_greeks.copy()
    valid["right_norm"] = valid["right_upper"].map(right_name)
    bid = valid["bid"].fillna(0.0).astype(float)
    ask = valid["ask"].fillna(0.0).astype(float)
    mid = ((bid + ask) / 2.0).where((bid > 0.0) | (ask > 0.0), 0.0)
    valid = valid[(bid > 0.0) | (ask > 0.0)].copy()
    for row, bid_v, ask_v, mid_v in zip(valid.itertuples(index=False), bid.loc[valid.index], ask.loc[valid.index], mid.loc[valid.index]):
        lookup[(str(row.time_str), float(row.strike), str(row.right_norm))] = {
            "bid": float(bid_v),
            "ask": float(ask_v),
            "mid": float(mid_v),
        }
    return lookup


def select_leg(df_slice: pd.DataFrame, right: str, delta_target: float, strike_filter=None) -> dict | None:
    opt = df_slice[df_slice["right_upper"].map(right_name).eq(right)].copy()
    if strike_filter is not None:
        opt = opt[strike_filter(opt["strike"].astype(float))]
    if opt.empty:
        return None
    opt = opt[(opt["bid"].astype(float) > 0.0) & (opt["ask"].astype(float) > 0.0)]
    opt = opt[opt["delta_abs"].astype(float) > 0.005]
    if opt.empty:
        return None
    opt["delta_diff"] = (opt["delta_abs"].astype(float) - float(delta_target)).abs()
    row = opt.loc[opt["delta_diff"].idxmin()]
    return {
        "strike": float(row["strike"]),
        "bid": float(row["bid"]),
        "ask": float(row["ask"]),
        "mid": float(row.get("mid", (float(row["bid"]) + float(row["ask"])) / 2.0)),
        "delta_abs": abs(float(row.get("delta", delta_target))),
        "right": right,
    }


def select_vertical_spread(
    entry_slice: pd.DataFrame,
    side: str,
    spread_type: str,
    short_delta: float,
    long_delta: float,
) -> dict | None:
    spread_type = str(spread_type).lower()
    if spread_type == "credit" and side == "LONG":
        right = "PUT"
        short_leg = select_leg(entry_slice, right, short_delta)
        if short_leg is None:
            return None
        long_leg = select_leg(
            entry_slice,
            right,
            long_delta,
            strike_filter=lambda strike: strike < float(short_leg["strike"]),
        )
    elif spread_type == "credit":
        right = "CALL"
        short_leg = select_leg(entry_slice, right, short_delta)
        if short_leg is None:
            return None
        long_leg = select_leg(
            entry_slice,
            right,
            long_delta,
            strike_filter=lambda strike: strike > float(short_leg["strike"]),
        )
    elif side == "LONG":
        right = "CALL"
        long_leg = select_leg(entry_slice, right, long_delta)
        if long_leg is None:
            return None
        short_leg = select_leg(
            entry_slice,
            right,
            short_delta,
            strike_filter=lambda strike: strike > float(long_leg["strike"]),
        )
    else:
        right = "PUT"
        long_leg = select_leg(entry_slice, right, long_delta)
        if long_leg is None:
            return None
        short_leg = select_leg(
            entry_slice,
            right,
            short_delta,
            strike_filter=lambda strike: strike < float(long_leg["strike"]),
        )
    if short_leg is None or long_leg is None:
        return None
    width = abs(float(long_leg["strike"]) - float(short_leg["strike"]))
    if width <= 0.0:
        return None
    if spread_type == "credit":
        entry_net = float(short_leg["bid"]) - float(long_leg["ask"])
        if entry_net <= 0.0 or entry_net >= width:
            return None
        max_loss = width - entry_net
        max_profit = entry_net
    else:
        entry_net = float(long_leg["ask"]) - float(short_leg["bid"])
        if entry_net <= 0.0 or entry_net >= width:
            return None
        max_loss = entry_net
        max_profit = width - entry_net
    return {
        "spread_type": spread_type,
        "right": right,
        "short_strike": float(short_leg["strike"]),
        "long_strike": float(long_leg["strike"]),
        "short_delta_abs": float(short_leg["delta_abs"]),
        "long_delta_abs": float(long_leg["delta_abs"]),
        "width": float(width),
        "entry_net": float(entry_net),
        "max_loss_per_spread": float(max_loss),
        "max_profit_per_spread": float(max_profit),
    }


def spread_close_value(
    price_lookup: dict[tuple[str, float, str], dict[str, float]],
    time_str: str,
    spread: dict,
) -> float | None:
    right = str(spread["right"])
    short_quote = price_lookup.get((str(time_str), float(spread["short_strike"]), right))
    long_quote = price_lookup.get((str(time_str), float(spread["long_strike"]), right))
    if short_quote is None or long_quote is None:
        return None
    short_ask = float(short_quote.get("ask", 0.0))
    long_bid = float(long_quote.get("bid", 0.0))
    if short_ask <= 0.0:
        short_ask = float(short_quote.get("mid", 0.0))
    if long_bid <= 0.0:
        long_bid = float(long_quote.get("mid", 0.0))
    if short_ask <= 0.0:
        return None
    if str(spread.get("spread_type", "credit")) == "credit":
        return max(0.0, short_ask - max(0.0, long_bid))
    return max(0.0, max(0.0, long_bid) - short_ask)


def spread_pairs(args) -> list[tuple[float, float]]:
    if str(args.spread_type).lower() == "credit":
        return [(float(s), float(l)) for s in args.short_deltas for l in args.long_deltas if float(l) < float(s)]
    return [(float(s), float(l)) for s in args.short_deltas for l in args.long_deltas if float(l) > float(s)]


def build_spread_paths_for_group(payload: tuple[tuple[str, str], pd.DataFrame, pd.DataFrame, dict]) -> list[dict]:
    (ticker, date), signal_group, day_rows, args_dict = payload
    args = argparse.Namespace(**args_dict)
    rows: list[dict] = []
    ticker = normalize_ticker(ticker)
    date = normalize_date(date)
    df_greeks, _, _ = _load_daily_greeks(date, ticker)
    if df_greeks is None or df_greeks.empty:
        return rows
    price_lookup = build_price_lookup(df_greeks)
    pairs = spread_pairs(args)
    day_rows = day_rows.sort_values("minutes").reset_index(drop=True)

    for signal in signal_group.itertuples(index=False):
        ticker = normalize_ticker(getattr(signal, "ticker"))
        date = normalize_date(getattr(signal, "date"))
        side = str(getattr(signal, "side")).upper()
        entry_time = str(getattr(signal, "time"))
        entry_minute = int(getattr(signal, "entry_minute", time_to_minutes(entry_time)))
        entry_spot = float(getattr(signal, "spot_price", 0.0) or 0.0)
        signal_id = int(getattr(signal, "signal_id"))
        future_rows = day_rows[
            (day_rows["minutes"].astype(int) > entry_minute)
            & (day_rows["minutes"].astype(int) <= entry_minute + int(args.max_hold_minutes))
        ].copy()
        if future_rows.empty:
            continue

        entry_slice = df_greeks[df_greeks["time_str"] == entry_time].copy()
        if entry_slice.empty:
            continue
        if "mid" not in entry_slice.columns:
            entry_slice["mid"] = (entry_slice["bid"].fillna(0.0).astype(float) + entry_slice["ask"].fillna(0.0).astype(float)) / 2.0

        for short_delta, long_delta in pairs:
            spread = select_vertical_spread(entry_slice, side, args.spread_type, short_delta, long_delta)
            if spread is None:
                continue
            max_loss_dollars = float(spread["max_loss_per_spread"]) * 100.0
            if max_loss_dollars <= 0.0 or max_loss_dollars > float(args.risk_capital) * float(args.max_loss_mult):
                continue
            contracts = max(1, int(float(args.risk_capital) // max_loss_dollars))
            max_loss_total = max_loss_dollars * contracts
            max_profit_total = float(spread["max_profit_per_spread"]) * 100.0 * contracts
            side_sign = 1.0 if side == "LONG" else -1.0
            path_points = []
            for future in future_rows.itertuples(index=False):
                future_time = str(future.time)
                close_value = spread_close_value(price_lookup, future_time, spread)
                if close_value is None:
                    continue
                if str(args.spread_type).lower() == "credit":
                    pnl = (float(spread["entry_net"]) - float(close_value)) * 100.0 * contracts
                else:
                    pnl = (float(close_value) - float(spread["entry_net"])) * 100.0 * contracts
                spot = float(getattr(future, "spot_price", entry_spot) or entry_spot)
                spot_bps = (spot / entry_spot - 1.0) * 10000.0 if entry_spot > 0.0 else 0.0
                path_points.append(
                    {
                        "time": future_time,
                        "hold_minutes": int(getattr(future, "minutes")) - entry_minute,
                        "close_value": float(close_value),
                        "pnl_dollars": float(pnl),
                        "return_on_max_loss": float(pnl) / max(max_loss_total, 1e-9),
                        "credit_capture": float(pnl) / max(max_profit_total, 1e-9),
                        "signed_spot_return_bps": float(side_sign * spot_bps),
                    }
                )
            if not path_points:
                continue
            rows.append(
                {
                    "spread_id": -1,
                    "signal_id": signal_id,
                    "ticker": ticker,
                    "date": date,
                    "month": month_key(date),
                    "time": entry_time,
                    "side": side,
                    "spread_type": str(args.spread_type).lower(),
                    "spot_price": entry_spot,
                    "short_delta_target": float(short_delta),
                    "long_delta_target": float(long_delta),
                    "short_delta_abs": float(spread["short_delta_abs"]),
                    "long_delta_abs": float(spread["long_delta_abs"]),
                    "right": str(spread["right"]),
                    "short_strike": float(spread["short_strike"]),
                    "long_strike": float(spread["long_strike"]),
                    "width": float(spread["width"]),
                    "entry_net": float(spread["entry_net"]),
                    "max_loss_dollars": float(max_loss_total),
                    "max_profit_dollars": float(max_profit_total),
                    "contracts": int(contracts),
                    "level_target_bps": float(getattr(signal, "level_target_bps", np.nan)),
                    "level_stop_bps": float(getattr(signal, "level_stop_bps", np.nan)),
                    "level_config": str(getattr(signal, "level_config", "")),
                    "path": path_points,
                }
            )
    return rows


def load_checkpoint_chunks(checkpoint_dir: Path) -> tuple[list[pd.DataFrame], set[tuple[str, str]]]:
    chunks: list[pd.DataFrame] = []
    completed: set[tuple[str, str]] = set()
    if not checkpoint_dir.exists():
        return chunks, completed
    for path in sorted(checkpoint_dir.glob("paths_chunk_*.parquet")):
        chunk = pd.read_parquet(path)
        if not chunk.empty:
            chunks.append(chunk)
            keys = chunk[["ticker", "date"]].drop_duplicates()
            completed.update((normalize_ticker(row.ticker), normalize_date(row.date)) for row in keys.itertuples(index=False))
    return chunks, completed


def flush_path_chunk(rows: list[dict], checkpoint_dir: Path, chunk_index: int) -> int:
    if not rows:
        return chunk_index
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_dir / f"paths_chunk_{chunk_index:05d}.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)
    log(f"[CREDIT_SPREAD] checkpoint {path.name} rows={len(rows):,}")
    rows.clear()
    return chunk_index + 1


def build_spread_paths(signals: pd.DataFrame, path_frame: pd.DataFrame, args, checkpoint_dir: Path | None = None) -> pd.DataFrame:
    path_groups = {
        (normalize_ticker(key[0]), normalize_date(key[1])): group.sort_values("minutes").reset_index(drop=True)
        for key, group in path_frame.groupby(["ticker", "date"], sort=False)
    }
    signal_groups = {
        (normalize_ticker(key[0]), normalize_date(key[1])): group.reset_index(drop=True)
        for key, group in signals.groupby(["ticker", "date"], sort=False)
    }
    existing_chunks: list[pd.DataFrame] = []
    completed: set[tuple[str, str]] = set()
    if checkpoint_dir is not None:
        existing_chunks, completed = load_checkpoint_chunks(checkpoint_dir)
        if completed:
            log(f"[CREDIT_SPREAD] resume path checkpoints groups={len(completed):,} chunks={len(existing_chunks):,}")

    tasks = []
    args_dict = vars(args).copy()
    for key, group in signal_groups.items():
        if key in completed:
            continue
        day_rows = path_groups.get(key)
        if day_rows is None or day_rows.empty:
            continue
        tasks.append((key, group, day_rows, args_dict))

    start = time.time()
    pending_rows: list[dict] = []
    chunk_index = len(existing_chunks)
    workers = int(getattr(args, "workers", 1) or 1)
    checkpoint_groups = max(1, int(getattr(args, "checkpoint_groups", 50) or 50))
    completed_now = 0
    if workers <= 1:
        for payload in tasks:
            pending_rows.extend(build_spread_paths_for_group(payload))
            completed_now += 1
            if checkpoint_dir is not None and completed_now % checkpoint_groups == 0:
                chunk_index = flush_path_chunk(pending_rows, checkpoint_dir, chunk_index)
            if completed_now % int(args.progress_every) == 0:
                log(
                    f"[CREDIT_SPREAD] groups={completed_now:,}/{len(tasks):,} "
                    f"pending_rows={len(pending_rows):,} elapsed={(time.time() - start) / 60.0:.1f}m"
                )
    else:
        executor_cls = ThreadPoolExecutor if str(getattr(args, "worker_backend", "thread")).lower() == "thread" else ProcessPoolExecutor
        with executor_cls(max_workers=workers) as pool:
            futures = [pool.submit(build_spread_paths_for_group, payload) for payload in tasks]
            for future in as_completed(futures):
                pending_rows.extend(future.result())
                completed_now += 1
                if checkpoint_dir is not None and completed_now % checkpoint_groups == 0:
                    chunk_index = flush_path_chunk(pending_rows, checkpoint_dir, chunk_index)
                if completed_now % int(args.progress_every) == 0:
                    log(
                        f"[CREDIT_SPREAD] groups={completed_now:,}/{len(tasks):,} "
                        f"pending_rows={len(pending_rows):,} elapsed={(time.time() - start) / 60.0:.1f}m"
                    )
    if checkpoint_dir is not None:
        chunk_index = flush_path_chunk(pending_rows, checkpoint_dir, chunk_index)
        existing_chunks, _ = load_checkpoint_chunks(checkpoint_dir)
        spreads = pd.concat(existing_chunks, ignore_index=True) if existing_chunks else pd.DataFrame()
    else:
        spreads = pd.DataFrame(pending_rows)
    if not spreads.empty:
        spreads = spreads.sort_values(["date", "time", "ticker", "signal_id", "short_delta_target", "long_delta_target"]).reset_index(drop=True)
        spreads["spread_id"] = np.arange(len(spreads), dtype=np.int64)
    return spreads


def simulate_spread(base: pd.Series, config: dict) -> dict:
    target_bps = float(base.get("level_target_bps", np.nan))
    stop_bps = float(base.get("level_stop_bps", np.nan))
    has_target = np.isfinite(target_bps) and target_bps > 0.0
    has_stop = np.isfinite(stop_bps) and stop_bps > 0.0
    exit_point = base["path"][-1]
    exit_reason = "max_time"
    for point in base["path"]:
        if float(point["return_on_max_loss"]) <= float(config["hard_stop"]):
            exit_point = point
            exit_reason = "hard_stop"
            break
        if has_stop and float(point["signed_spot_return_bps"]) <= -stop_bps:
            exit_point = point
            exit_reason = "level_spot_stop"
            break
        if float(point["credit_capture"]) >= float(config["profit_capture"]):
            exit_point = point
            exit_reason = "profit_capture"
            break
        if bool(config["use_level_exit"]) and has_target and float(point["signed_spot_return_bps"]) >= target_bps:
            exit_point = point
            exit_reason = "level_spot_target"
            break
    return {
        "policy": config_key(config),
        "config_key": config_key(config),
        "spread_id": int(base["spread_id"]),
        "signal_id": int(base["signal_id"]),
        "ticker": str(base["ticker"]),
        "date": str(base["date"]),
        "month": str(base["month"]),
        "time": str(base["time"]),
        "side": str(base["side"]),
        "spread_type": str(base.get("spread_type", config["spread_type"])),
        "right": str(base["right"]),
        "short_delta_target": float(base["short_delta_target"]),
        "long_delta_target": float(base["long_delta_target"]),
        "short_delta_abs": float(base["short_delta_abs"]),
        "long_delta_abs": float(base["long_delta_abs"]),
        "short_strike": float(base["short_strike"]),
        "long_strike": float(base["long_strike"]),
        "width": float(base["width"]),
        "entry_net": float(base["entry_net"]),
        "max_loss_dollars": float(base["max_loss_dollars"]),
        "max_profit_dollars": float(base["max_profit_dollars"]),
        "contracts": int(base["contracts"]),
        "exit_reason": exit_reason,
        "exit_time": str(exit_point["time"]),
        "hold_minutes": int(exit_point["hold_minutes"]),
        "pnl_dollars": float(exit_point["pnl_dollars"]),
        "return_on_max_loss": float(exit_point["return_on_max_loss"]),
        "credit_capture": float(exit_point["credit_capture"]),
        "hard_stop": float(config["hard_stop"]),
        "profit_capture": float(config["profit_capture"]),
        "use_level_exit": bool(config["use_level_exit"]),
    }


def build_grid(args) -> list[dict]:
    grid = []
    for short_delta in args.short_deltas:
        for long_delta in args.long_deltas:
            if str(args.spread_type).lower() == "credit" and float(long_delta) >= float(short_delta):
                continue
            if str(args.spread_type).lower() == "debit" and float(long_delta) <= float(short_delta):
                continue
            for hard_stop in args.hard_stops:
                for capture in args.profit_captures:
                    for use_level in args.use_level_exit:
                        grid.append(
                            {
                                "spread_type": str(args.spread_type).lower(),
                                "short_delta": float(short_delta),
                                "long_delta": float(long_delta),
                                "hard_stop": float(hard_stop),
                                "profit_capture": float(capture),
                                "use_level_exit": bool(int(use_level)),
                            }
                        )
    return grid


def simulate_grid(spreads: pd.DataFrame, grid: list[dict]) -> pd.DataFrame:
    rows: list[dict] = []
    grouped = {
        (float(key[0]), float(key[1])): group.reset_index(drop=True)
        for key, group in spreads.groupby(["short_delta_target", "long_delta_target"], sort=False)
    }
    start = time.time()
    for idx, config in enumerate(grid, start=1):
        group = grouped.get((float(config["short_delta"]), float(config["long_delta"])))
        if group is None or group.empty:
            continue
        for base in group.itertuples(index=False):
            rows.append(simulate_spread(pd.Series(base._asdict()), config))
        if idx % 25 == 0:
            log(f"[CREDIT_SPREAD] simulated configs={idx:,}/{len(grid):,} rows={len(rows):,} elapsed={(time.time() - start) / 60.0:.1f}m")
    return pd.DataFrame(rows)


def select_walkforward(all_trades: pd.DataFrame, args, per_ticker: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    months = sorted(all_trades["month"].astype(str).unique().tolist())
    test_months = [m for m in months if m >= str(args.start_month) and m <= str(args.end_month)]
    selected: list[pd.DataFrame] = []
    folds: list[dict] = []
    tickers = sorted(all_trades["ticker"].astype(str).unique().tolist()) if per_ticker else ["ALL"]
    for month in test_months:
        prior = [m for m in months if m < month]
        val_months = prior[-int(args.val_months) :]
        if len(val_months) < int(args.val_months):
            continue
        for ticker in tickers:
            val = all_trades[all_trades["month"].isin(val_months)].copy()
            test = all_trades[all_trades["month"].astype(str).eq(month)].copy()
            if per_ticker:
                val = val[val["ticker"].astype(str).eq(ticker)].copy()
                test = test[test["ticker"].astype(str).eq(ticker)].copy()
            if val.empty or test.empty:
                continue
            best_config = ""
            best_score = -float("inf")
            best_metrics = {}
            for key, group in val.groupby("config_key", sort=False):
                metrics = trade_metrics(group)
                score = metrics_score(metrics, int(args.min_val_trades), float(args.min_long_rate), float(args.max_long_rate))
                if score > best_score:
                    best_score = score
                    best_config = str(key)
                    best_metrics = metrics
            picked = test[test["config_key"].astype(str).eq(best_config)].copy()
            test_metrics = trade_metrics(picked)
            selected.append(picked)
            folds.append(
                {
                    "month": month,
                    "ticker": ticker,
                    "config_key": best_config,
                    "val_months": ",".join(val_months),
                    "val_score": float(best_score),
                    **{f"val_{k}": v for k, v in best_metrics.items()},
                    **{f"test_{k}": v for k, v in test_metrics.items()},
                }
            )
            log(
                f"[CREDIT_SPREAD] {month} {ticker} config={best_config} "
                f"val_pf={best_metrics.get('profit_factor', float('nan')):.3f} "
                f"test_trades={test_metrics.get('trades', 0)} "
                f"test_pf={test_metrics.get('profit_factor', float('nan')):.3f} "
                f"test_pnl={test_metrics.get('pnl_dollars', 0.0):.0f}"
            )
    trades = pd.concat(selected, ignore_index=True) if selected else pd.DataFrame()
    return trades, pd.DataFrame(folds)


def summarize(output_dir: Path, all_trades: pd.DataFrame, wf: pd.DataFrame, folds: pd.DataFrame, args, label: str) -> None:
    overall = trade_metrics(wf)
    per_ticker = {ticker: trade_metrics(group) for ticker, group in wf.groupby("ticker", sort=True)} if "ticker" in wf.columns else {}
    per_side = {side: trade_metrics(group) for side, group in wf.groupby("side", sort=True)} if "side" in wf.columns else {}
    hindsight_rows = []
    test = all_trades[(all_trades["month"].astype(str) >= str(args.start_month)) & (all_trades["month"].astype(str) <= str(args.end_month))]
    for ticker, group in test.groupby("ticker", sort=True):
        best_key = None
        best_score = -float("inf")
        best_metrics = {}
        for key, cfg_group in group.groupby("config_key", sort=False):
            metrics = trade_metrics(cfg_group)
            score = metrics_score(metrics, int(args.min_val_trades), float(args.min_long_rate), float(args.max_long_rate))
            if score > best_score:
                best_score = score
                best_key = str(key)
                best_metrics = metrics
        hindsight_rows.append({"ticker": ticker, "config_key": best_key, "score": best_score, **best_metrics})
    metadata = {
        "args": vars(args),
        "label": label,
        "all_trade_rows": int(len(all_trades)),
        "walkforward": overall,
        "per_ticker": per_ticker,
        "per_side": per_side,
        "hindsight_best_by_ticker": hindsight_rows,
    }
    (output_dir / f"{label}_metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    wf.to_csv(output_dir / f"{label}_trades.csv", index=False)
    folds.to_csv(output_dir / f"{label}_folds.csv", index=False)
    lines = [
        "# Level Signal Credit Spread Backtest",
        "",
        f"Selection: `{label}`",
        "",
        "## Walk-Forward",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        "## Per Ticker",
        "",
        "```json",
        json.dumps(per_ticker, indent=2, allow_nan=True),
        "```",
        "",
        "## Per Side",
        "",
        "```json",
        json.dumps(per_side, indent=2, allow_nan=True),
        "```",
        "",
        "## Hindsight Best By Ticker (Non-Deployable)",
        "",
        "```json",
        json.dumps(hindsight_rows, indent=2, allow_nan=True),
        "```",
        "",
    ]
    (output_dir / f"{label}_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest directional 0DTE credit spreads on causal level signals.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--train-start-date", default="20250101")
    parser.add_argument("--start-month", default="202507")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-val-trades", type=int, default=45)
    parser.add_argument("--risk-capital", type=float, default=1000.0)
    parser.add_argument("--max-loss-mult", type=float, default=1.5)
    parser.add_argument("--max-hold-minutes", type=int, default=180)
    parser.add_argument("--spread-type", choices=["credit", "debit"], default="credit")
    parser.add_argument("--short-deltas", nargs="+", type=float, default=[0.15, 0.20, 0.25, 0.30])
    parser.add_argument("--long-deltas", nargs="+", type=float, default=[0.05, 0.10, 0.15])
    parser.add_argument("--hard-stops", nargs="+", type=float, default=[-0.35, -0.50, -0.75, -1.00])
    parser.add_argument("--profit-captures", nargs="+", type=float, default=[0.35, 0.50, 0.70, 0.90])
    parser.add_argument("--use-level-exit", nargs="+", default=["0", "1"], help="0/1 grid values.")
    parser.add_argument("--min-long-rate", type=float, default=0.25)
    parser.add_argument("--max-long-rate", type=float, default=0.75)
    parser.add_argument("--greeks-cache-size", type=int, default=60)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    parser.add_argument("--worker-backend", choices=["thread", "process"], default="thread")
    parser.add_argument("--checkpoint-groups", type=int, default=50)
    parser.add_argument("--progress-every", type=int, default=50)
    parser.add_argument("--reuse-all-trades", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    spread_type = str(args.spread_type).lower()
    all_trades_path = output_dir / f"all_{spread_type}_spread_trades.parquet"
    if args.reuse_all_trades and all_trades_path.exists():
        all_trades = pd.read_parquet(all_trades_path)
        log(f"[CREDIT_SPREAD] reused all trades rows={len(all_trades):,}")
    else:
        base_path = output_dir / f"base_{spread_type}_spread_paths.parquet"
        if base_path.exists():
            spreads = pd.read_parquet(base_path)
            log(f"[CREDIT_SPREAD] reused base spreads={len(spreads):,}")
        else:
            candidates = pd.read_parquet(args.candidate_labels)
            signals = normalize_signal_frame(candidates, args.train_start_date)
            path_frame = load_path_frame(args.data, min_date=args.train_start_date)
            log(f"[CREDIT_SPREAD] signals={len(signals):,} path_rows={len(path_frame):,}")
            checkpoint_dir = output_dir / f"{spread_type}_path_chunks"
            spreads = build_spread_paths(signals, path_frame, args, checkpoint_dir=checkpoint_dir)
            spreads.to_parquet(base_path, index=False)
        log(f"[CREDIT_SPREAD] base spreads={len(spreads):,}")
        grid = build_grid(args)
        log(f"[CREDIT_SPREAD] grid={len(grid):,}")
        all_trades = simulate_grid(spreads, grid)
        all_trades.to_parquet(all_trades_path, index=False)
        log(f"[CREDIT_SPREAD] all trades rows={len(all_trades):,}")

    wf_all, folds_all = select_walkforward(all_trades, args, per_ticker=False)
    summarize(output_dir, all_trades, wf_all, folds_all, args, "combined_config")
    wf_ticker, folds_ticker = select_walkforward(all_trades, args, per_ticker=True)
    summarize(output_dir, all_trades, wf_ticker, folds_ticker, args, "per_ticker_config")
    print((output_dir / "combined_config_SUMMARY.md").read_text(encoding="utf-8"))
    print((output_dir / "per_ticker_config_SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
