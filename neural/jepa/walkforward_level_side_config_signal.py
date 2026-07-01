from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import metrics, month_range
from walkforward_level_target_signal import (
    Config,
    DOWN_LEVEL_COLS,
    UP_LEVEL_COLS,
    config_grid,
    gate_sides,
    month_from_date,
    normalize_date,
    simulate_return,
    target_bps,
    time_to_minutes,
)


GATE_COLS = [
    "near_ib_high",
    "near_ib_low",
    "above_ib",
    "below_ib",
    "bouncing_from_support",
    "rejecting_resistance",
    "trend_grind_up",
    "trend_flush_down",
    "is_touching_fib",
    "wall_at_fib",
    "is_touching_max_gamma",
    "is_touching_min_gamma",
]

BASE_COLS = ["ticker", "date", "time", "spot_price"]
NEEDED_COLS = list(dict.fromkeys([*BASE_COLS, *UP_LEVEL_COLS, *DOWN_LEVEL_COLS, *GATE_COLS]))
WORKER_FRAME: pd.DataFrame | None = None


@dataclass(frozen=True)
class SidePair:
    long_config: Config
    short_config: Config

    @property
    def name(self) -> str:
        return f"L[{self.long_config.name}]__S[{self.short_config.name}]"


def score_metrics(row: dict, min_trades: int, min_month_trades: int) -> float:
    trades = int(row.get("trades", 0))
    pf = float(row.get("profit_factor", 0.0))
    pnl = float(row.get("pnl_dollars", 0.0))
    long_rate = float(row.get("long_rate", float("nan")))
    min_month = int(row.get("min_month_trades", 0))
    if trades < int(min_trades) or min_month < int(min_month_trades):
        return -1e18 + trades
    if not np.isfinite(pf) or not np.isfinite(long_rate):
        return -1e18 + trades
    if long_rate < 0.20 or long_rate > 0.80:
        return -1e18 + trades
    dd = abs(float(row.get("max_drawdown", 0.0)))
    positive_month_rate = float(row.get("positive_month_rate", 0.0))
    return (
        3.0 * math.log1p(min(max(pf, 0.0), 5.0))
        + 0.70 * math.log1p(trades)
        + pnl / 20_000.0
        - dd / 25_000.0
        + positive_month_rate
    )


def score_side_metrics(row: dict, min_trades: int, min_month_trades: int) -> float:
    trades = int(row.get("trades", 0))
    pf = float(row.get("profit_factor", 0.0))
    pnl = float(row.get("pnl_dollars", 0.0))
    min_month = int(row.get("min_month_trades", 0))
    if trades < int(min_trades) or min_month < int(min_month_trades):
        return -1e18 + trades
    if not np.isfinite(pf):
        return -1e18 + trades
    dd = abs(float(row.get("max_drawdown", 0.0)))
    positive_month_rate = float(row.get("positive_month_rate", 0.0))
    return (
        3.0 * math.log1p(min(max(pf, 0.0), 5.0))
        + 0.70 * math.log1p(trades)
        + pnl / 20_000.0
        - dd / 25_000.0
        + positive_month_rate
    )


def available_columns(path: str | Path) -> list[str]:
    try:
        import pyarrow.parquet as pq

        return list(pq.ParquetFile(path).schema.names)
    except Exception:
        return []


def load_frame(path: str | Path, args: argparse.Namespace) -> pd.DataFrame:
    available = set(available_columns(path))
    columns = [col for col in NEEDED_COLS if not available or col in available]
    df = pd.read_parquet(path, columns=columns if columns else None)
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df["date"] = df["date"].map(normalize_date)
    df["month"] = df["date"].map(month_from_date)
    df["minute"] = df["time"].map(time_to_minutes).astype(int)
    tickers = [str(t).upper() for t in args.tickers]
    df = df[
        df["ticker"].isin(tickers)
        & (df["date"] >= normalize_date(args.train_start_date))
        & (df["month"] <= str(args.end_month))
    ].copy()
    numeric_cols = [col for col in df.columns if col not in {"ticker", "date", "time", "month"}]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(np.float32)
    df["minute"] = df["minute"].astype(np.int16)
    return df


def init_worker(data_path: str, args_dict: dict) -> None:
    global WORKER_FRAME
    WORKER_FRAME = load_frame(data_path, argparse.Namespace(**args_dict))


def eligible_side_signals(frame: pd.DataFrame, config: Config, side: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    work = frame[frame["minute"].astype(int) >= int(config.start_minute)].copy()
    if work.empty:
        return pd.DataFrame()

    def flag(col: str) -> np.ndarray:
        if col not in work.columns:
            return np.zeros(len(work), dtype=bool)
        return work[col].fillna(0.0).astype(float).to_numpy() > 0.0

    near_hi = flag("near_ib_high")
    near_lo = flag("near_ib_low")
    above = flag("above_ib")
    below = flag("below_ib")
    bounce = flag("bouncing_from_support")
    reject = flag("rejecting_resistance")
    trend_up = flag("trend_grind_up")
    trend_down = flag("trend_flush_down")
    touch_fib = flag("is_touching_fib")
    wall_fib = flag("wall_at_fib")
    touch_max_gamma = flag("is_touching_max_gamma")
    touch_min_gamma = flag("is_touching_min_gamma")

    if config.gate == "ib_reversal":
        side_mask = (near_lo | below | bounce) if side == "LONG" else (near_hi | above | reject)
    elif config.gate == "breakout":
        side_mask = (near_hi | above | trend_up) if side == "LONG" else (near_lo | below | trend_down)
    elif config.gate == "sr_combo":
        side_mask = (near_lo | bounce | touch_min_gamma) if side == "LONG" else (near_hi | reject | touch_max_gamma)
    elif config.gate == "fib_wall":
        side_mask = touch_fib | wall_fib
    else:
        side_mask = np.ones(len(work), dtype=bool)

    level_cols = UP_LEVEL_COLS if side == "LONG" else DOWN_LEVEL_COLS
    available = [col for col in level_cols if col in work.columns]
    if not available:
        return pd.DataFrame()
    values = work[available].astype(float).to_numpy()
    targets = -values if side == "LONG" else values
    valid_targets = (targets > float(config.min_target_bps)) & (targets <= float(config.max_target_bps))
    target_values = np.where(valid_targets, targets, np.inf).min(axis=1)
    target_values = np.where(np.isfinite(target_values), target_values, np.nan)
    mask = side_mask & np.isfinite(target_values)
    if not bool(mask.any()):
        return pd.DataFrame()

    out = work.loc[mask, ["ticker", "date", "time", "month", "minute"]].copy()
    out["side"] = side
    out["target_bps"] = target_values[mask].astype(float)
    out["stop_bps"] = float(config.stop_bps)
    out["config"] = config.name
    return out


def apply_cooldown(signals: pd.DataFrame, cooldown_minutes: int) -> pd.DataFrame:
    if signals.empty or int(cooldown_minutes) <= 0:
        return signals.copy()
    kept: list[dict] = []
    for _, day in signals.sort_values(["date", "minute", "target_bps", "side"]).groupby("date", sort=False):
        next_allowed = -1
        for row in day.itertuples(index=False):
            minute = int(row.minute)
            if minute < next_allowed:
                continue
            kept.append(row._asdict())
            next_allowed = minute + int(cooldown_minutes)
    return pd.DataFrame(kept) if kept else signals.iloc[0:0].copy()


def build_price_cache(frame: pd.DataFrame) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    prices_by_day = {
        str(date): day.sort_values("minute")["spot_price"].astype(float).to_numpy()
        for date, day in frame.groupby("date", sort=False)
    }
    minutes_by_day = {
        str(date): day.sort_values("minute")["minute"].astype(int).to_numpy()
        for date, day in frame.groupby("date", sort=False)
    }
    return prices_by_day, minutes_by_day


def simulate_signals(
    signals: pd.DataFrame,
    prices_by_day: dict[str, np.ndarray],
    minutes_by_day: dict[str, np.ndarray],
    horizon_steps: int,
    notional: float,
) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame()
    rows: list[dict] = []
    for row in signals.itertuples(index=False):
        prices = prices_by_day.get(str(row.date))
        minutes = minutes_by_day.get(str(row.date))
        if prices is None or minutes is None:
            continue
        matches = np.flatnonzero(minutes == int(row.minute))
        if len(matches) == 0:
            continue
        ret, hold_steps = simulate_return(
            prices,
            int(matches[0]),
            str(row.side),
            float(row.target_bps),
            float(row.stop_bps),
            int(horizon_steps),
        )
        if not np.isfinite(ret):
            continue
        rows.append(
            {
                "ticker": str(row.ticker),
                "date": str(row.date),
                "month": str(row.month),
                "time": str(row.time),
                "minute": int(row.minute),
                "side": str(row.side),
                "target_bps": float(row.target_bps),
                "stop_bps": float(row.stop_bps),
                "hold_minutes": int(hold_steps) * 5,
                "return": float(ret),
                "pnl_dollars": float(ret) * float(notional),
                "config": str(row.config),
            }
        )
    return pd.DataFrame(rows)


def pair_raw_signals(raw_by_side_config: dict[tuple[str, str], pd.DataFrame], pair: SidePair) -> pd.DataFrame:
    parts = [
        raw_by_side_config.get(("LONG", pair.long_config.name), pd.DataFrame()),
        raw_by_side_config.get(("SHORT", pair.short_config.name), pd.DataFrame()),
    ]
    parts = [p for p in parts if not p.empty]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def build_trade_cache(
    raw_by_side_config: dict[tuple[str, str], pd.DataFrame],
    prices_by_day: dict[str, np.ndarray],
    minutes_by_day: dict[str, np.ndarray],
    args: argparse.Namespace,
) -> dict[tuple[str, str], pd.DataFrame]:
    out: dict[tuple[str, str], pd.DataFrame] = {}
    for key, raw in raw_by_side_config.items():
        if raw.empty:
            continue
        trades = simulate_signals(raw, prices_by_day, minutes_by_day, int(args.horizon_steps), float(args.notional))
        if not trades.empty:
            out[key] = trades
    return out


def pair_cached_trades(trade_cache: dict[tuple[str, str], pd.DataFrame], pair: SidePair) -> pd.DataFrame:
    parts = [
        trade_cache.get(("LONG", pair.long_config.name), pd.DataFrame()),
        trade_cache.get(("SHORT", pair.short_config.name), pd.DataFrame()),
    ]
    parts = [p for p in parts if not p.empty]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def evaluate_pair(
    raw_by_side_config: dict[tuple[str, str], pd.DataFrame],
    pair: SidePair,
    prices_by_day: dict[str, np.ndarray],
    minutes_by_day: dict[str, np.ndarray],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, dict]:
    raw = pair_raw_signals(raw_by_side_config, pair)
    selected = apply_cooldown(raw, int(args.cooldown_minutes))
    trades = simulate_signals(selected, prices_by_day, minutes_by_day, int(args.horizon_steps), float(args.notional))
    return trades, metrics(trades)


def evaluate_cached_pair(trade_cache: dict[tuple[str, str], pd.DataFrame], pair: SidePair, args: argparse.Namespace) -> tuple[pd.DataFrame, dict]:
    raw_trades = pair_cached_trades(trade_cache, pair)
    selected = apply_cooldown(raw_trades, int(args.cooldown_minutes))
    return selected, metrics(selected)


def build_raw_cache(frame: pd.DataFrame, grid: list[Config]) -> dict[tuple[str, str], pd.DataFrame]:
    out: dict[tuple[str, str], pd.DataFrame] = {}
    for config in grid:
        for side in ("LONG", "SHORT"):
            raw = eligible_side_signals(frame, config, side)
            if not raw.empty:
                out[(side, config.name)] = raw
    return out


def select_pair(
    val: pd.DataFrame,
    grid: list[Config],
    val_months: list[str],
    args: argparse.Namespace,
) -> tuple[SidePair, dict, float]:
    raw_cache = build_raw_cache(val, grid)
    prices_by_day, minutes_by_day = build_price_cache(val)
    trade_cache = build_trade_cache(raw_cache, prices_by_day, minutes_by_day, args)
    long_grid = grid
    short_grid = grid
    if int(args.top_side_configs) > 0:
        side_min_trades = max(1, int(math.ceil(float(args.min_val_trades) * float(args.side_min_trade_fraction))))
        side_min_month = max(1, int(math.floor(float(args.min_month_trades) * float(args.side_min_month_fraction))))
        ranked: dict[str, list[tuple[float, Config]]] = {"LONG": [], "SHORT": []}
        for side in ("LONG", "SHORT"):
            for config in grid:
                trades = trade_cache.get((side, config.name), pd.DataFrame())
                selected = apply_cooldown(trades, int(args.cooldown_minutes))
                row = metrics(selected, val_months)
                score = score_side_metrics(row, side_min_trades, side_min_month)
                ranked[side].append((score, config))
        long_grid = [config for _, config in sorted(ranked["LONG"], key=lambda item: item[0], reverse=True)[: int(args.top_side_configs)]]
        short_grid = [config for _, config in sorted(ranked["SHORT"], key=lambda item: item[0], reverse=True)[: int(args.top_side_configs)]]
    best_pair = SidePair(grid[0], grid[0])
    best_metrics: dict = {}
    best_score = -1e18
    for long_config in long_grid:
        for short_config in short_grid:
            pair = SidePair(long_config, short_config)
            trades, _ = evaluate_cached_pair(trade_cache, pair, args)
            row = metrics(trades, val_months)
            score = score_metrics(row, int(args.min_val_trades), int(args.min_month_trades))
            if score > best_score:
                best_pair = pair
                best_metrics = row
                best_score = score
    return best_pair, best_metrics, best_score


def deploy_pair(test: pd.DataFrame, pair: SidePair, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_cache = build_raw_cache(test, [pair.long_config, pair.short_config])
    raw = pair_raw_signals(raw_cache, pair)
    selected = apply_cooldown(raw, int(args.cooldown_minutes))
    prices_by_day, minutes_by_day = build_price_cache(test)
    trades = simulate_signals(selected, prices_by_day, minutes_by_day, int(args.horizon_steps), float(args.notional))
    if not trades.empty:
        trades["side_pair"] = pair.name
        trades["long_config"] = pair.long_config.name
        trades["short_config"] = pair.short_config.name
    if not selected.empty:
        selected["side_pair"] = pair.name
        selected["long_config"] = pair.long_config.name
        selected["short_config"] = pair.short_config.name
    return trades, selected


def run_fold(frame: pd.DataFrame, ticker: str, test_month: str, args: argparse.Namespace, grid: list[Config]) -> tuple[pd.DataFrame, pd.DataFrame, dict] | None:
    tdf = frame[frame["ticker"] == ticker].sort_values(["date", "minute"]).copy()
    prior = tdf[tdf["month"] < test_month].copy()
    test = tdf[tdf["month"] == test_month].copy()
    val_months = sorted(prior["month"].unique())[-int(args.val_months):]
    val = prior[prior["month"].isin(val_months)].copy()
    if len(val_months) < int(args.val_months) or val.empty or test.empty:
        return None
    best_pair, best_val_metrics, best_score = select_pair(val, grid, [str(m) for m in val_months], args)
    test_trades, test_signals = deploy_pair(test, best_pair, args)
    test_metrics = metrics(test_trades, [str(test_month)])
    fold_row = {
        "ticker": ticker,
        "month": str(test_month),
        "side_pair": best_pair.name,
        "long_config": best_pair.long_config.name,
        "short_config": best_pair.short_config.name,
        "val_months": ",".join([str(m) for m in val_months]),
        "val_score": float(best_score),
        **{f"val_{k}": v for k, v in best_val_metrics.items()},
        **{f"test_{k}": v for k, v in test_metrics.items()},
    }
    if not test_trades.empty:
        test_trades["test_month"] = str(test_month)
    if not test_signals.empty:
        test_signals["test_month"] = str(test_month)
    return test_trades, test_signals, fold_row


def run_fold_worker(task: tuple[str, str, dict]) -> tuple[pd.DataFrame, pd.DataFrame, dict] | None:
    if WORKER_FRAME is None:
        raise RuntimeError("Worker frame is not initialized")
    ticker, test_month, args_dict = task
    args = argparse.Namespace(**args_dict)
    grid = config_grid(args)
    return run_fold(WORKER_FRAME, str(ticker), str(test_month), args, grid)


def write_signal_parquet(signals: pd.DataFrame, output_dir: Path) -> None:
    if signals.empty:
        return
    direction = np.where(signals["side"].astype(str) == "LONG", 1, -1).astype(np.int8)
    confidence = np.clip(signals["target_bps"].astype(float) / 100.0, 0.05, 0.95)
    out = signals[["ticker", "date", "time"]].copy()
    out["jepa180_prob_up"] = np.where(direction > 0, confidence, 1.0 - confidence)
    out["jepa180_pred_bps"] = np.where(direction > 0, signals["target_bps"], -signals["target_bps"])
    out["jepa180_long_threshold"] = 0.0
    out["jepa180_short_threshold"] = 0.0
    out["jepa180_confidence"] = confidence
    out["jepa180_edge"] = confidence
    out["jepa180_direction"] = direction
    out["jepa180_signal"] = True
    out["level_target_bps"] = signals["target_bps"].astype(float).to_numpy()
    out["level_stop_bps"] = signals["stop_bps"].astype(float).to_numpy()
    out["level_config"] = signals["config"].astype(str).to_numpy()
    out.to_parquet(output_dir / "oof_rule_signals.parquet", index=False)


def write_summary(output_dir: Path, metadata: dict, trades: pd.DataFrame, folds: pd.DataFrame) -> None:
    args_meta = metadata.get("args", {})
    expected_months = month_range(str(args_meta.get("start_month")), str(args_meta.get("end_month")))
    overall = metrics(trades, expected_months)
    per_ticker = {
        str(ticker): metrics(frame, expected_months)
        for ticker, frame in trades.groupby("ticker", sort=True)
    } if not trades.empty else {}
    lines = [
        "# Level Target Side-Pair Walk-Forward",
        "",
        "Causal rule diagnostic: for each ticker/month, LONG and SHORT level-rule configs are selected as a pair using only prior validation months.",
        "",
        "## Overall",
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
        "## Fold Configs",
        "",
        "```csv",
        folds.to_csv(index=False),
        "```",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(metadata, indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def checkpoint(
    output_dir: Path,
    trades: list[pd.DataFrame],
    signals: list[pd.DataFrame],
    folds: list[dict],
    metadata: dict,
) -> None:
    trade_df = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    signal_df = pd.concat(signals, ignore_index=True) if signals else pd.DataFrame()
    fold_df = pd.DataFrame(folds)
    if not trade_df.empty:
        trade_df.to_csv(output_dir / "level_side_config_wf_trades.csv", index=False)
    if not signal_df.empty:
        signal_df.to_csv(output_dir / "selected_side_pair_signals.csv", index=False)
        write_signal_parquet(signal_df, output_dir)
    if not fold_df.empty:
        fold_df.to_csv(output_dir / "fold_configs.csv", index=False)
    args_meta = metadata.get("args", {})
    expected_months = month_range(str(args_meta.get("start_month")), str(args_meta.get("end_month")))
    (output_dir / "metrics.json").write_text(
        json.dumps({"overall": metrics(trade_df, expected_months), "metadata": metadata}, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    write_summary(output_dir, metadata, trade_df, fold_df)


def load_checkpoint(output_dir: Path, resume: bool) -> tuple[list[pd.DataFrame], list[pd.DataFrame], list[dict], set[tuple[str, str]]]:
    if not resume:
        return [], [], [], set()
    trades_path = output_dir / "level_side_config_wf_trades.csv"
    signals_path = output_dir / "selected_side_pair_signals.csv"
    folds_path = output_dir / "fold_configs.csv"
    trades: list[pd.DataFrame] = []
    signals: list[pd.DataFrame] = []
    folds: list[dict] = []
    done: set[tuple[str, str]] = set()
    if trades_path.exists():
        trades.append(pd.read_csv(trades_path, dtype={"date": str, "month": str}))
    if signals_path.exists():
        signals.append(pd.read_csv(signals_path, dtype={"date": str, "month": str}))
    if folds_path.exists():
        fold_df = pd.read_csv(folds_path, dtype={"month": str})
        folds = fold_df.to_dict("records")
        for row in folds:
            done.add((str(row["ticker"]).upper(), str(row["month"])))
    return trades, signals, folds, done


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward level signal with separate LONG/SHORT config pair selection.")
    parser.add_argument("--data", default="training_data/training_data_spx_qqq_spy.parquet")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--train-start-date", default="20250101")
    parser.add_argument("--start-month", default="202507")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-val-trades", type=int, default=45)
    parser.add_argument("--min-month-trades", type=int, default=15)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--notional", type=float, default=100000.0)
    parser.add_argument("--gates", nargs="+", default=["fib_wall", "sr_combo", "ib_reversal"])
    parser.add_argument("--min-target-bps", nargs="+", type=float, default=[15.0, 25.0])
    parser.add_argument("--max-target-bps", nargs="+", type=float, default=[100.0, 150.0, 250.0])
    parser.add_argument("--stop-bps", nargs="+", type=float, default=[20.0, 30.0])
    parser.add_argument("--start-minutes", nargs="+", type=int, default=[570, 630])
    parser.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1))
    parser.add_argument("--top-side-configs", type=int, default=0, help="If >0, rank configs per side on validation and evaluate only top N long x top N short pairs.")
    parser.add_argument("--side-min-trade-fraction", type=float, default=0.30)
    parser.add_argument("--side-min-month-fraction", type=float, default=0.40)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    df = load_frame(args.data, args)
    tickers = [str(t).upper() for t in args.tickers]

    grid = config_grid(args)
    metadata = {
        "args": vars(args),
        "grid_size": len(grid),
        "grid": [asdict(cfg) for cfg in grid],
    }
    all_trades, all_signals, fold_rows, done = load_checkpoint(output_dir, resume=not args.no_resume)
    tasks: list[tuple[str, str]] = []
    for ticker in tickers:
        tdf = df[df["ticker"] == ticker].sort_values(["date", "minute"]).copy()
        months = [m for m in sorted(tdf["month"].unique()) if str(args.start_month) <= str(m) <= str(args.end_month)]
        for test_month in months:
            fold_key = (ticker, str(test_month))
            if fold_key in done:
                print(f"[LEVEL_SIDE] skip checkpointed {ticker} {test_month}", flush=True)
                continue
            tasks.append((ticker, str(test_month)))

    def record_result(result: tuple[pd.DataFrame, pd.DataFrame, dict] | None) -> None:
        if result is None:
            return
        test_trades, test_signals, fold_row = result
        ticker = str(fold_row["ticker"])
        test_month = str(fold_row["month"])
        if not test_trades.empty:
            all_trades.append(test_trades)
        if not test_signals.empty:
            all_signals.append(test_signals)
        fold_rows.append(fold_row)
        done.add((ticker, test_month))
        print(
            f"[LEVEL_SIDE] {ticker} {test_month} "
            f"L={fold_row['long_config']} S={fold_row['short_config']} "
            f"val_pf={float(fold_row.get('val_profit_factor', float('nan'))):.3f} "
            f"test_trades={int(fold_row.get('test_trades', 0))} "
            f"test_pf={float(fold_row.get('test_profit_factor', float('nan'))):.3f} "
            f"test_pnl={float(fold_row.get('test_pnl_dollars', 0.0)):.0f}",
            flush=True,
        )
        checkpoint(output_dir, all_trades, all_signals, fold_rows, metadata)

    if int(args.workers) <= 1 or len(tasks) <= 1:
        for ticker, test_month in tasks:
            result = run_fold(df, ticker, test_month, args, grid)
            record_result(result)
    else:
        worker_count = min(int(args.workers), len(tasks))
        task_payloads = [(ticker, test_month, vars(args)) for ticker, test_month in tasks]
        print(f"[LEVEL_SIDE] running {len(task_payloads)} folds with {worker_count} workers", flush=True)
        with ProcessPoolExecutor(
            max_workers=worker_count,
            initializer=init_worker,
            initargs=(str(args.data), vars(args)),
        ) as executor:
            futures = [executor.submit(run_fold_worker, task) for task in task_payloads]
            for future in as_completed(futures):
                record_result(future.result())

    checkpoint(output_dir, all_trades, all_signals, fold_rows, metadata)
    trade_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    print(json.dumps(metrics(trade_df, month_range(str(args.start_month), str(args.end_month))), indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
