from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FilterConfig:
    min_side_score: float
    min_confidence: float
    max_entropy: float
    max_err_180m: float
    require_context: bool

    @property
    def name(self) -> str:
        ctx = "ctx" if self.require_context else "all"
        err = "inf" if self.max_err_180m >= 90 else f"{self.max_err_180m:.2f}"
        ent = "inf" if self.max_entropy >= 90 else f"{self.max_entropy:.2f}"
        return (
            f"{ctx}_side{self.min_side_score:.2f}_conf{self.min_confidence:.2f}"
            f"_ent{ent}_err{err}"
        )


def normalize_date(value) -> str:
    return str(value).replace("-", "")[:8]


def time_to_minutes(value) -> int:
    text = str(value)
    if " " in text:
        text = text.split(" ")[-1]
    try:
        return int(text[:2]) * 60 + int(text[3:5])
    except Exception:
        return 0


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


def month_range(start_month: str, end_month: str) -> list[str]:
    out: list[str] = []
    current = str(start_month)
    while current <= str(end_month):
        out.append(current)
        current = month_add(current, 1)
    return out


def metrics(trades: pd.DataFrame, expected_months: list[str] | None = None) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": float("nan"),
            "profit_factor": float("nan"),
            "pnl_dollars": 0.0,
            "max_drawdown": 0.0,
            "avg_pnl": float("nan"),
            "avg_hold_minutes": float("nan"),
            "long_rate": float("nan"),
            "min_month_trades": 0,
            "positive_month_rate": float("nan"),
        }
    pnl = trades["pnl_dollars"].astype(float).to_numpy()
    wins = pnl[pnl > 0.0]
    losses = pnl[pnl < 0.0]
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    equity = np.cumsum(pnl)
    peak = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
    by_month = trades.groupby("month")["pnl_dollars"].agg(["count", "sum"])
    if expected_months is not None:
        by_month = by_month.reindex([str(m) for m in expected_months], fill_value=0)
    return {
        "trades": int(len(trades)),
        "win_rate": float((pnl > 0.0).mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf"),
        "pnl_dollars": float(pnl.sum()),
        "max_drawdown": float((equity - peak).min()) if len(equity) else 0.0,
        "avg_pnl": float(pnl.mean()),
        "avg_hold_minutes": float(trades["hold_minutes"].astype(float).mean()),
        "long_rate": float((trades["side"].astype(str) == "LONG").mean()),
        "min_month_trades": int(by_month["count"].min()) if not by_month.empty else 0,
        "positive_month_rate": float((by_month["sum"] > 0.0).mean()) if not by_month.empty else float("nan"),
    }


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
    pf_capped = min(max(pf, 0.0), 5.0)
    return (
        3.0 * math.log1p(pf_capped)
        + 0.75 * math.log1p(trades)
        + pnl / 20_000.0
        - dd / 25_000.0
        + positive_month_rate
    )


def filter_rows(frame: pd.DataFrame, config: FilterConfig) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    work = frame.copy()
    direction = work["jepa180_direction"].astype(int).to_numpy()
    side_score = np.where(
        direction > 0,
        work["xjepa_direction_score"].astype(float).to_numpy(),
        -work["xjepa_direction_score"].astype(float).to_numpy(),
    )
    mask = (
        (side_score >= float(config.min_side_score))
        & (work["xjepa_trade_confidence"].astype(float).to_numpy() >= float(config.min_confidence))
        & (work["xjepa_entropy"].astype(float).to_numpy() <= float(config.max_entropy))
        & (work["xjepa_lagged_pred_180m_err"].astype(float).to_numpy() <= float(config.max_err_180m))
    )
    if config.require_context:
        mask &= work["xjepa_context_valid"].astype(float).to_numpy() > 0.0
    return work.loc[mask].copy()


def apply_cooldown(signals: pd.DataFrame, cooldown_minutes: int) -> pd.DataFrame:
    if signals.empty or int(cooldown_minutes) <= 0:
        return signals.copy()
    kept: list[dict] = []
    for _, day in signals.sort_values(["ticker", "date", "minute"]).groupby(["ticker", "date"], sort=False):
        next_allowed = -1
        for row in day.itertuples(index=False):
            minute = int(row.minute)
            if minute < next_allowed:
                continue
            kept.append(row._asdict())
            next_allowed = minute + int(cooldown_minutes)
    return pd.DataFrame(kept) if kept else signals.iloc[0:0].copy()


def simulate_return(
    prices: np.ndarray,
    pos: int,
    side: str,
    target_bps: float,
    stop_bps: float,
    horizon_steps: int,
) -> tuple[float, int, str]:
    entry = float(prices[pos])
    end = min(len(prices) - 1, pos + int(horizon_steps))
    if not np.isfinite(entry) or entry <= 0.0 or end <= pos:
        return float("nan"), 0, "invalid"
    target = float(target_bps) / 10_000.0
    stop = float(stop_bps) / 10_000.0
    for i in range(pos + 1, end + 1):
        raw = float(prices[i]) / entry - 1.0
        signed = raw if side == "LONG" else -raw
        if signed <= -stop:
            return -stop, i - pos, "stop"
        if signed >= target:
            return target, i - pos, "target"
    raw = float(prices[end]) / entry - 1.0
    return (raw if side == "LONG" else -raw), end - pos, "horizon"


def build_price_cache(price_df: pd.DataFrame) -> tuple[dict[tuple[str, str], np.ndarray], dict[tuple[str, str], np.ndarray]]:
    prices_by_day = {
        (str(ticker), str(date)): day.sort_values("minute")["spot_price"].astype(float).to_numpy()
        for (ticker, date), day in price_df.groupby(["ticker", "date"], sort=False)
    }
    minutes_by_day = {
        (str(ticker), str(date)): day.sort_values("minute").astype({"minute": int})["minute"].to_numpy()
        for (ticker, date), day in price_df.groupby(["ticker", "date"], sort=False)
    }
    return prices_by_day, minutes_by_day


def simulate_trades(
    signals: pd.DataFrame,
    price_cache: tuple[dict[tuple[str, str], np.ndarray], dict[tuple[str, str], np.ndarray]],
    args: argparse.Namespace,
) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame()
    selected = apply_cooldown(signals, int(args.cooldown_minutes))
    if selected.empty:
        return pd.DataFrame()
    prices_by_day, minutes_by_day = price_cache
    rows: list[dict] = []
    for row in selected.itertuples(index=False):
        key = (str(row.ticker), str(row.date))
        prices = prices_by_day.get(key)
        minutes = minutes_by_day.get(key)
        if prices is None or minutes is None:
            continue
        matches = np.flatnonzero(minutes == int(row.minute))
        if len(matches) == 0:
            continue
        side = "LONG" if int(row.jepa180_direction) > 0 else "SHORT"
        ret, hold_steps, exit_reason = simulate_return(
            prices,
            int(matches[0]),
            side,
            float(row.level_target_bps),
            float(row.level_stop_bps),
            int(args.horizon_steps),
        )
        if not np.isfinite(ret):
            continue
        rows.append(
            {
                "ticker": str(row.ticker),
                "date": str(row.date),
                "month": str(row.month),
                "time": str(row.time),
                "side": side,
                "level_target_bps": float(row.level_target_bps),
                "level_stop_bps": float(row.level_stop_bps),
                "level_config": str(row.level_config),
                "filter_config": str(row.filter_config),
                "xjepa_direction_score": float(row.xjepa_direction_score),
                "xjepa_trade_confidence": float(row.xjepa_trade_confidence),
                "xjepa_entropy": float(row.xjepa_entropy),
                "xjepa_lagged_pred_180m_err": float(row.xjepa_lagged_pred_180m_err),
                "exit_reason": exit_reason,
                "hold_minutes": int(hold_steps) * 5,
                "return": float(ret),
                "pnl_dollars": float(ret) * float(args.notional),
            }
        )
    return pd.DataFrame(rows)


def build_grid(profile: str = "fast") -> list[FilterConfig]:
    grid = [FilterConfig(-99.0, 0.0, 99.0, 99.0, False)]
    if str(profile).lower() == "full":
        side_scores = [-0.25, 0.0, 0.05, 0.10, 0.20, 0.30]
        confidences = [0.0, 0.35, 0.45, 0.55, 0.65]
        entropies = [99.0, 1.05, 0.95, 0.85, 0.70]
        errors = [99.0, 2.50, 1.50, 1.00, 0.70]
    else:
        side_scores = [-0.25, 0.0, 0.10, 0.20, 0.30]
        confidences = [0.0, 0.45, 0.55]
        entropies = [99.0, 0.95, 0.85]
        errors = [99.0, 1.50]
    for min_side_score in side_scores:
        for min_confidence in confidences:
            for max_entropy in entropies:
                for max_err_180m in errors:
                    grid.append(
                        FilterConfig(
                            float(min_side_score),
                            float(min_confidence),
                            float(max_entropy),
                            float(max_err_180m),
                            True,
                        )
                    )
    return grid


def load_checkpoint(output_dir: Path, resume: bool) -> tuple[list[pd.DataFrame], list[dict], set[tuple[str, str]]]:
    if not resume:
        return [], [], set()
    trades_path = output_dir / "xinput_level_filter_trades.csv"
    folds_path = output_dir / "fold_configs.csv"
    existing_trades: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    done: set[tuple[str, str]] = set()
    if folds_path.exists():
        folds = pd.read_csv(folds_path, dtype={"month": str})
        fold_rows = folds.to_dict("records")
        for row in fold_rows:
            done.add((str(row.get("ticker", "")).upper(), str(row.get("month", ""))))
    if trades_path.exists():
        trades = pd.read_csv(trades_path, dtype={"date": str, "month": str, "test_month": str})
        if not trades.empty:
            existing_trades.append(trades)
    return existing_trades, fold_rows, done


def checkpoint(output_dir: Path, trades_list: list[pd.DataFrame], fold_rows: list[dict], metadata: dict) -> None:
    trades = pd.concat(trades_list, ignore_index=True) if trades_list else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    args_meta = metadata.get("args", {})
    expected_months = month_range(str(args_meta.get("start_month", "")), str(args_meta.get("end_month", ""))) if args_meta.get("start_month") and args_meta.get("end_month") else None
    if not trades.empty:
        trades.to_csv(output_dir / "xinput_level_filter_trades.csv", index=False)
    if not folds.empty:
        folds.to_csv(output_dir / "fold_configs.csv", index=False)
    (output_dir / "metrics.json").write_text(
        json.dumps({"overall": metrics(trades, expected_months), "metadata": metadata}, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    write_summary(output_dir, metadata, trades, folds)


def load_inputs(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    signals = pd.read_parquet(args.signals)
    signals["ticker"] = signals["ticker"].astype(str).str.upper()
    signals["date"] = signals["date"].map(normalize_date)
    signals["month"] = signals["date"].str[:6]
    signals["minute"] = signals["time"].map(time_to_minutes).astype(int)
    signals = signals[signals["jepa180_direction"].astype(int) != 0].copy()

    feature_cols = [
        "ticker",
        "date",
        "time",
        "xjepa_context_valid",
        "xjepa_direction_score",
        "xjepa_trade_confidence",
        "xjepa_entropy",
        "xjepa_lagged_pred_180m_err",
    ]
    features = pd.read_parquet(args.features, columns=feature_cols)
    features["ticker"] = features["ticker"].astype(str).str.upper()
    features["date"] = features["date"].map(normalize_date)
    features["time"] = features["time"].astype(str).str[:5]
    signals["time"] = signals["time"].astype(str).str[:5]
    features = features.drop_duplicates(["ticker", "date", "time"])
    merged = signals.merge(features, on=["ticker", "date", "time"], how="left")
    for col in feature_cols[3:]:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0)

    prices = pd.read_parquet(args.data, columns=["ticker", "date", "time", "spot_price"])
    prices["ticker"] = prices["ticker"].astype(str).str.upper()
    prices["date"] = prices["date"].map(normalize_date)
    prices["time"] = prices["time"].astype(str).str[:5]
    prices["minute"] = prices["time"].map(time_to_minutes).astype(int)
    prices = prices.sort_values(["ticker", "date", "minute"]).reset_index(drop=True)
    return merged, prices


def write_summary(output_dir: Path, metadata: dict, trades: pd.DataFrame, folds: pd.DataFrame) -> None:
    args_meta = metadata.get("args", {})
    expected_months = month_range(str(args_meta.get("start_month", "")), str(args_meta.get("end_month", ""))) if args_meta.get("start_month") and args_meta.get("end_month") else None
    overall = metrics(trades, expected_months)
    per_ticker = {
        str(ticker): metrics(frame, expected_months)
        for ticker, frame in trades.groupby("ticker", sort=True)
    } if not trades.empty else {}
    lines = [
        "# XInput Filter On Level Signals",
        "",
        "Warning: if `features` is a globally trained xinput parquet, this is diagnostic only, not deployable proof.",
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


def evaluate_fold(
    ticker: str,
    test_month: str,
    t_signals: pd.DataFrame,
    price_cache: tuple[dict[tuple[str, str], np.ndarray], dict[tuple[str, str], np.ndarray]],
    args: argparse.Namespace,
    grid: list[FilterConfig],
) -> tuple[tuple[str, str], pd.DataFrame, dict, str] | None:
    val_months = [month_add(test_month, -i) for i in range(int(args.val_months), 0, -1)]
    val = t_signals[t_signals["month"].isin(val_months)].copy()
    test = t_signals[t_signals["month"] == test_month].copy()
    if val.empty or test.empty:
        return None

    best_cfg = grid[0]
    best_score = -1e18
    best_metrics: dict = {}
    for cfg in grid:
        val_filtered = filter_rows(val, cfg)
        if not val_filtered.empty:
            val_filtered["filter_config"] = cfg.name
        val_trades = simulate_trades(val_filtered, price_cache, args)
        row = metrics(val_trades, val_months)
        score = score_metrics(row, int(args.min_val_trades), int(args.min_month_trades))
        if score > best_score:
            best_cfg = cfg
            best_score = score
            best_metrics = row

    test_filtered = filter_rows(test, best_cfg)
    if not test_filtered.empty:
        test_filtered["filter_config"] = best_cfg.name
    test_trades = simulate_trades(test_filtered, price_cache, args)
    test_metrics = metrics(test_trades, [str(test_month)])
    if not test_trades.empty:
        test_trades["test_month"] = test_month
    fold_row = {
        "ticker": ticker,
        "month": test_month,
        "filter_config": best_cfg.name,
        "val_months": ",".join(val_months),
        "val_score": float(best_score),
        **{f"val_{k}": v for k, v in best_metrics.items()},
        **{f"test_{k}": v for k, v in test_metrics.items()},
    }
    log_line = (
        f"[XINPUT_FILTER] {ticker} {test_month} cfg={best_cfg.name} "
        f"val_pf={best_metrics.get('profit_factor', float('nan')):.3f} "
        f"test_trades={test_metrics.get('trades', 0)} "
        f"test_pf={test_metrics.get('profit_factor', float('nan')):.3f} "
        f"test_pnl={test_metrics.get('pnl_dollars', 0.0):.0f}"
    )
    return (ticker, str(test_month)), test_trades, fold_row, log_line


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward xinput filter over causal level-rule signals.")
    parser.add_argument("--data", default="training_data/training_data_spx_qqq_spy.parquet")
    parser.add_argument("--signals", required=True)
    parser.add_argument("--features", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202507")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-val-trades", type=int, default=45)
    parser.add_argument("--min-month-trades", type=int, default=15)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--notional", type=float, default=100000.0)
    parser.add_argument("--grid-profile", choices=["fast", "full"], default="fast")
    parser.add_argument("--workers", type=int, default=1, help="Parallel fold workers. Uses threads to share loaded data.")
    parser.add_argument("--no-resume", action="store_true", help="Ignore existing fold/trade checkpoints in output-dir.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    signals, prices = load_inputs(args)
    tickers = [str(t).upper() for t in args.tickers]
    signals = signals[
        signals["ticker"].isin(tickers)
        & (signals["month"] <= str(args.end_month))
    ].copy()
    prices = prices[prices["ticker"].isin(tickers)].copy()
    grid = build_grid(args.grid_profile)
    metadata = {"args": vars(args), "grid_size": len(grid), "filters": [asdict(cfg) for cfg in grid]}

    all_trades, fold_rows, done_folds = load_checkpoint(output_dir, resume=not args.no_resume)
    months = [m for m in sorted(signals["month"].unique()) if str(args.start_month) <= str(m) <= str(args.end_month)]
    tasks: list[tuple[str, str, pd.DataFrame, tuple[dict[tuple[str, str], np.ndarray], dict[tuple[str, str], np.ndarray]]]] = []
    for ticker in tickers:
        t_signals = signals[signals["ticker"] == ticker].copy()
        t_prices = prices[prices["ticker"] == ticker].copy()
        price_cache = build_price_cache(t_prices)
        for test_month in months:
            fold_key = (ticker, str(test_month))
            if fold_key in done_folds:
                print(f"[XINPUT_FILTER] skip checkpointed {ticker} {test_month}", flush=True)
                continue
            tasks.append((ticker, str(test_month), t_signals, price_cache))

    def handle_result(result: tuple[tuple[str, str], pd.DataFrame, dict, str] | None) -> None:
        if result is None:
            return
        fold_key, test_trades, fold_row, log_line = result
        if not test_trades.empty:
            all_trades.append(test_trades)
        fold_rows.append(fold_row)
        done_folds.add(fold_key)
        print(log_line, flush=True)
        checkpoint(output_dir, all_trades, fold_rows, metadata)

    workers = max(1, int(args.workers))
    if workers == 1 or len(tasks) <= 1:
        for ticker, test_month, t_signals, price_cache in tasks:
            handle_result(evaluate_fold(ticker, test_month, t_signals, price_cache, args, grid))
    else:
        print(f"[XINPUT_FILTER] running {len(tasks)} folds with {workers} workers", flush=True)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(evaluate_fold, ticker, test_month, t_signals, price_cache, args, grid)
                for ticker, test_month, t_signals, price_cache in tasks
            ]
            for future in as_completed(futures):
                handle_result(future.result())

    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    checkpoint(output_dir, all_trades, fold_rows, metadata)
    print(json.dumps(metrics(trades, month_range(str(args.start_month), str(args.end_month))), indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
