from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import metrics, month_range
from walkforward_level_side_config_signal import (
    Config,
    apply_cooldown,
    build_price_cache,
    build_raw_cache,
    build_trade_cache,
    config_grid,
    load_frame,
    score_metrics,
    score_side_metrics,
    write_signal_parquet,
)


WORKER_FRAME: pd.DataFrame | None = None


@dataclass(frozen=True)
class EnsembleConfig:
    long_count: int
    short_count: int
    max_trades_per_day: int

    @property
    def name(self) -> str:
        max_day = "all" if self.max_trades_per_day >= 999 else str(self.max_trades_per_day)
        return f"L{self.long_count}_S{self.short_count}_maxday{max_day}"


def init_worker(data_path: str, args_dict: dict) -> None:
    global WORKER_FRAME
    WORKER_FRAME = load_frame(data_path, argparse.Namespace(**args_dict))


def month_add(yyyymm: str, delta: int) -> str:
    value = int(yyyymm)
    year = value // 100
    month = value % 100 + int(delta)
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return f"{year:04d}{month:02d}"


def robust_side_score(train_row: dict, val_row: dict, args: argparse.Namespace) -> float:
    train_score = score_side_metrics(
        train_row,
        int(args.min_train_side_trades),
        int(args.min_train_side_month_trades),
    )
    val_score = score_side_metrics(
        val_row,
        int(args.min_val_side_trades),
        int(args.min_val_side_month_trades),
    )
    if train_score <= -1e17 or val_score <= -1e17:
        return -1e18 + min(int(train_row.get("trades", 0)), int(val_row.get("trades", 0)))

    train_pf = float(train_row.get("profit_factor", 0.0))
    val_pf = float(val_row.get("profit_factor", 0.0))
    train_pnl = float(train_row.get("pnl_dollars", 0.0))
    val_pnl = float(val_row.get("pnl_dollars", 0.0))
    pf_gap = abs(math.log(max(train_pf, 0.05)) - math.log(max(val_pf, 0.05)))
    stability = min(math.log1p(max(train_pf, 0.0)), math.log1p(max(val_pf, 0.0)))
    return (
        0.35 * train_score
        + 0.65 * val_score
        + 2.0 * stability
        + (train_pnl + 2.0 * val_pnl) / 30_000.0
        - 1.25 * pf_gap
    )


def side_rankings(
    train_cache: dict[tuple[str, str], pd.DataFrame],
    val_cache: dict[tuple[str, str], pd.DataFrame],
    grid: list[Config],
    train_months: list[str],
    val_months: list[str],
    args: argparse.Namespace,
) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {"LONG": [], "SHORT": []}
    for side in ("LONG", "SHORT"):
        for config in grid:
            train_trades = apply_cooldown(train_cache.get((side, config.name), pd.DataFrame()), int(args.cooldown_minutes))
            val_trades = apply_cooldown(val_cache.get((side, config.name), pd.DataFrame()), int(args.cooldown_minutes))
            train_row = metrics(train_trades, train_months)
            val_row = metrics(val_trades, val_months)
            score = robust_side_score(train_row, val_row, args)
            out[side].append(
                {
                    "side": side,
                    "config": config,
                    "score": float(score),
                    "train": train_row,
                    "val": val_row,
                }
            )
        out[side] = sorted(out[side], key=lambda row: row["score"], reverse=True)
    return out


def selected_config_names(ranking: list[dict], count: int) -> list[str]:
    valid = [row for row in ranking if float(row.get("score", -1e18)) > -1e17]
    source = valid if valid else ranking
    return [str(row["config"].name) for row in source[: max(1, int(count))]]


def assemble_trades(
    trade_cache: dict[tuple[str, str], pd.DataFrame],
    rankings: dict[str, list[dict]],
    cfg: EnsembleConfig,
    args: argparse.Namespace,
) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for side, count in (("LONG", cfg.long_count), ("SHORT", cfg.short_count)):
        names = selected_config_names(rankings[side], int(count))
        rank_by_name = {name: i for i, name in enumerate(names)}
        for name in names:
            part = trade_cache.get((side, name), pd.DataFrame())
            if part.empty:
                continue
            tmp = part.copy()
            tmp["ensemble_rank"] = int(rank_by_name[name])
            tmp["ensemble_side_count"] = int(count)
            pieces.append(tmp)
    if not pieces:
        return pd.DataFrame()

    combined = pd.concat(pieces, ignore_index=True)
    combined = combined.sort_values(["date", "minute", "side", "ensemble_rank", "target_bps"])
    combined = combined.drop_duplicates(["date", "minute", "side"], keep="first")
    combined = apply_cooldown(combined, int(args.cooldown_minutes))
    max_day = int(cfg.max_trades_per_day)
    if max_day < 999 and not combined.empty:
        kept: list[dict] = []
        for _, day in combined.sort_values(["date", "minute", "ensemble_rank"]).groupby("date", sort=False):
            kept.extend([row._asdict() for row in day.itertuples(index=False)][:max_day])
        combined = pd.DataFrame(kept) if kept else combined.iloc[0:0].copy()
    if not combined.empty:
        combined["ensemble_config"] = cfg.name
        combined["long_count"] = int(cfg.long_count)
        combined["short_count"] = int(cfg.short_count)
        combined["max_trades_per_day"] = int(cfg.max_trades_per_day)
    return combined


def build_fold_caches(
    frame: pd.DataFrame,
    grid: list[Config],
    args: argparse.Namespace,
) -> tuple[dict[tuple[str, str], pd.DataFrame], dict[tuple[str, str], pd.DataFrame]]:
    raw_cache = build_raw_cache(frame, grid)
    prices_by_day, minutes_by_day = build_price_cache(frame)
    trade_cache = build_trade_cache(raw_cache, prices_by_day, minutes_by_day, args)
    return raw_cache, trade_cache


def build_ensemble_grid(args: argparse.Namespace) -> list[EnsembleConfig]:
    out: list[EnsembleConfig] = []
    for long_count in args.ensemble_counts:
        for short_count in args.ensemble_counts:
            for max_day in args.max_day_grid:
                out.append(EnsembleConfig(int(long_count), int(short_count), int(max_day)))
    return out


def run_fold(
    frame: pd.DataFrame,
    ticker: str,
    test_month: str,
    args: argparse.Namespace,
    grid: list[Config],
    ensemble_grid: list[EnsembleConfig],
) -> tuple[pd.DataFrame, dict] | None:
    tdf = frame[frame["ticker"].astype(str) == str(ticker)].sort_values(["date", "minute"]).copy()
    prior = tdf[tdf["month"].astype(str) < str(test_month)].copy()
    test = tdf[tdf["month"].astype(str) == str(test_month)].copy()
    val_months = sorted(prior["month"].astype(str).unique())[-int(args.val_months):]
    train = prior[~prior["month"].astype(str).isin(val_months)].copy()
    val = prior[prior["month"].astype(str).isin(val_months)].copy()
    train_months = sorted(train["month"].astype(str).unique())
    if (
        len(val_months) < int(args.val_months)
        or len(train_months) < int(args.min_train_months)
        or train.empty
        or val.empty
        or test.empty
    ):
        return None

    _, train_cache = build_fold_caches(train, grid, args)
    _, val_cache = build_fold_caches(val, grid, args)
    rankings = side_rankings(train_cache, val_cache, grid, train_months, val_months, args)

    best_cfg = ensemble_grid[0]
    best_score = -1e18
    best_metrics: dict = {}
    for cfg in ensemble_grid:
        val_trades = assemble_trades(val_cache, rankings, cfg, args)
        row = metrics(val_trades, val_months)
        score = score_metrics(row, int(args.min_val_trades), int(args.min_month_trades))
        if score > best_score:
            best_cfg = cfg
            best_score = score
            best_metrics = row

    if best_score <= -1e17 and not bool(args.allow_invalid_val_deploy):
        fold_row = {
            "ticker": ticker,
            "month": str(test_month),
            "ensemble_config": "ABSTAIN_INVALID_VAL",
            "val_months": ",".join(val_months),
            "train_months": ",".join(train_months),
            "val_score": float(best_score),
            "abstained_invalid_val": True,
            **{f"val_{k}": v for k, v in best_metrics.items()},
            **{f"test_{k}": v for k, v in metrics(pd.DataFrame(), [str(test_month)]).items()},
        }
        print(f"[STABLE_ENSEMBLE] {ticker} {test_month} abstain invalid_val score={best_score:.1f}", flush=True)
        return pd.DataFrame(), fold_row

    _, test_cache = build_fold_caches(test, grid, args)
    test_trades = assemble_trades(test_cache, rankings, best_cfg, args)
    test_metrics = metrics(test_trades, [str(test_month)])
    if not test_trades.empty:
        test_trades["test_month"] = str(test_month)
        test_trades["top_long_configs"] = ",".join(selected_config_names(rankings["LONG"], best_cfg.long_count))
        test_trades["top_short_configs"] = ",".join(selected_config_names(rankings["SHORT"], best_cfg.short_count))
    fold_row = {
        "ticker": ticker,
        "month": str(test_month),
        "ensemble_config": best_cfg.name,
        "val_months": ",".join(val_months),
        "train_months": ",".join(train_months),
        "val_score": float(best_score),
        "abstained_invalid_val": False,
        "top_long_configs": ",".join(selected_config_names(rankings["LONG"], best_cfg.long_count)),
        "top_short_configs": ",".join(selected_config_names(rankings["SHORT"], best_cfg.short_count)),
        "top_long_score": float(rankings["LONG"][0]["score"]) if rankings["LONG"] else float("nan"),
        "top_short_score": float(rankings["SHORT"][0]["score"]) if rankings["SHORT"] else float("nan"),
        **{f"val_{k}": v for k, v in best_metrics.items()},
        **{f"test_{k}": v for k, v in test_metrics.items()},
    }
    print(
        f"[STABLE_ENSEMBLE] {ticker} {test_month} cfg={best_cfg.name} "
        f"val_pf={best_metrics.get('profit_factor', float('nan')):.3f} "
        f"test_trades={test_metrics.get('trades', 0)} "
        f"test_pf={test_metrics.get('profit_factor', float('nan')):.3f} "
        f"test_pnl={test_metrics.get('pnl_dollars', 0.0):.0f}",
        flush=True,
    )
    return test_trades, fold_row


def run_fold_worker(task: tuple[str, str, dict]) -> tuple[pd.DataFrame, dict] | None:
    if WORKER_FRAME is None:
        raise RuntimeError("Worker frame is not initialized")
    ticker, test_month, args_dict = task
    args = argparse.Namespace(**args_dict)
    grid = config_grid(args)
    ensemble_grid = build_ensemble_grid(args)
    return run_fold(WORKER_FRAME, str(ticker), str(test_month), args, grid, ensemble_grid)


def write_summary(output_dir: Path, metadata: dict, trades: pd.DataFrame, folds: pd.DataFrame) -> None:
    args_meta = metadata.get("args", {})
    expected_months = month_range(str(args_meta.get("start_month")), str(args_meta.get("end_month")))
    overall = metrics(trades, expected_months)
    per_ticker = {
        str(ticker): metrics(frame, expected_months)
        for ticker, frame in trades.groupby("ticker", sort=True)
    } if not trades.empty else {}
    lines = [
        "# Level Stability Ensemble Walk-Forward",
        "",
        "Causal diagnostic: for each ticker/month, level configs are ranked by train+validation stability, validation chooses how many LONG/SHORT configs to ensemble, and test uses only that prior selection.",
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
    (output_dir / "metrics.json").write_text(
        json.dumps({"overall": overall, "per_ticker": per_ticker, "metadata": metadata}, indent=2, allow_nan=True),
        encoding="utf-8",
    )


def checkpoint(output_dir: Path, trades: list[pd.DataFrame], folds: list[dict], metadata: dict) -> None:
    trade_df = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    fold_df = pd.DataFrame(folds)
    if not trade_df.empty:
        trade_df.to_csv(output_dir / "level_stability_ensemble_trades.csv", index=False)
        signal_cols = [
            "ticker",
            "date",
            "time",
            "side",
            "target_bps",
            "stop_bps",
            "config",
        ]
        signals = trade_df[[c for c in signal_cols if c in trade_df.columns]].drop_duplicates(
            ["ticker", "date", "time", "side"],
            keep="first",
        )
        signals.to_csv(output_dir / "selected_stability_signals.csv", index=False)
        write_signal_parquet(signals, output_dir)
    if not fold_df.empty:
        fold_df.to_csv(output_dir / "fold_configs.csv", index=False)
    write_summary(output_dir, metadata, trade_df, fold_df)


def load_checkpoint(output_dir: Path, resume: bool) -> tuple[list[pd.DataFrame], list[dict], set[tuple[str, str]]]:
    if not resume:
        return [], [], set()
    trades_path = output_dir / "level_stability_ensemble_trades.csv"
    folds_path = output_dir / "fold_configs.csv"
    trades: list[pd.DataFrame] = []
    folds: list[dict] = []
    done: set[tuple[str, str]] = set()
    if trades_path.exists():
        trades.append(pd.read_csv(trades_path, dtype={"date": str, "month": str, "test_month": str}))
    if folds_path.exists():
        fold_df = pd.read_csv(folds_path, dtype={"month": str})
        folds = fold_df.to_dict("records")
        for row in folds:
            done.add((str(row["ticker"]).upper(), str(row["month"])))
    return trades, folds, done


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward stable ensemble of level-rule configs.")
    parser.add_argument("--data", default="training_data/training_data_spx_qqq_spy.parquet")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--train-start-date", default="20250101")
    parser.add_argument("--start-month", default="202507")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-train-months", type=int, default=3)
    parser.add_argument("--min-train-side-trades", type=int, default=30)
    parser.add_argument("--min-train-side-month-trades", type=int, default=5)
    parser.add_argument("--min-val-side-trades", type=int, default=18)
    parser.add_argument("--min-val-side-month-trades", type=int, default=3)
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
    parser.add_argument("--ensemble-counts", nargs="+", type=int, default=[1, 2, 3, 5, 8])
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[999, 12, 8, 4])
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--allow-invalid-val-deploy", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    df = load_frame(args.data, args)
    tickers = [str(t).upper() for t in args.tickers]
    grid = config_grid(args)
    ensemble_grid = build_ensemble_grid(args)
    metadata = {
        "args": vars(args),
        "grid_size": len(grid),
        "ensemble_grid_size": len(ensemble_grid),
        "grid": [asdict(cfg) for cfg in grid],
        "ensemble_grid": [asdict(cfg) for cfg in ensemble_grid],
    }
    all_trades, fold_rows, done = load_checkpoint(output_dir, resume=not args.no_resume)
    tasks: list[tuple[str, str]] = []
    for ticker in tickers:
        tdf = df[df["ticker"].astype(str) == ticker]
        months = [m for m in sorted(tdf["month"].astype(str).unique()) if str(args.start_month) <= m <= str(args.end_month)]
        for month in months:
            key = (ticker, str(month))
            if key in done:
                print(f"[STABLE_ENSEMBLE] skip checkpointed {ticker} {month}", flush=True)
                continue
            tasks.append(key)

    def record(result: tuple[pd.DataFrame, dict] | None) -> None:
        if result is None:
            return
        trades, fold = result
        if not trades.empty:
            all_trades.append(trades)
        fold_rows.append(fold)
        done.add((str(fold["ticker"]).upper(), str(fold["month"])))
        checkpoint(output_dir, all_trades, fold_rows, metadata)

    if int(args.workers) <= 1 or len(tasks) <= 1:
        for ticker, month in tasks:
            record(run_fold(df, ticker, month, args, grid, ensemble_grid))
    else:
        worker_count = min(int(args.workers), len(tasks))
        task_payloads = [(ticker, month, vars(args)) for ticker, month in tasks]
        print(f"[STABLE_ENSEMBLE] running {len(task_payloads)} folds with {worker_count} workers", flush=True)
        with ProcessPoolExecutor(
            max_workers=worker_count,
            initializer=init_worker,
            initargs=(str(args.data), vars(args)),
        ) as executor:
            futures = [executor.submit(run_fold_worker, task) for task in task_payloads]
            for future in as_completed(futures):
                record(future.result())

    checkpoint(output_dir, all_trades, fold_rows, metadata)
    trade_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    print(json.dumps(metrics(trade_df, month_range(str(args.start_month), str(args.end_month))), indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
