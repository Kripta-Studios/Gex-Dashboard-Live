from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


UP_LEVEL_COLS = [
    "price_vs_ib_high",
    "dist_fib_127_up",
    "dist_fib_161_up",
    "dist_fib_200_up",
    "dist_to_max_gamma",
    "dist_to_max_dgex",
]
DOWN_LEVEL_COLS = [
    "price_vs_ib_low",
    "dist_fib_127_dn",
    "dist_fib_161_dn",
    "dist_fib_200_dn",
    "dist_to_min_gamma",
    "dist_to_min_vanna",
    "dist_to_min_dgex",
]


@dataclass(frozen=True)
class Config:
    gate: str
    min_target_bps: float
    max_target_bps: float
    stop_bps: float
    start_minute: int

    @property
    def name(self) -> str:
        return (
            f"{self.gate}_t{self.min_target_bps:.0f}-{self.max_target_bps:.0f}"
            f"_s{self.stop_bps:.0f}_m{self.start_minute}"
        )


def normalize_date(value) -> str:
    return str(value).replace("-", "")[:8]


def time_to_minutes(value) -> int:
    text = str(value)
    try:
        return int(text[:2]) * 60 + int(text[3:5])
    except Exception:
        return 0


def month_from_date(value) -> str:
    return normalize_date(value)[:6]


def metrics(trades: pd.DataFrame) -> dict:
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


def score_metrics(row: dict, min_trades: int) -> float:
    trades = int(row.get("trades", 0))
    pnl = float(row.get("pnl_dollars", 0.0))
    pf = float(row.get("profit_factor", 0.0))
    long_rate = float(row.get("long_rate", float("nan")))
    if trades < int(min_trades) or not np.isfinite(pf) or not np.isfinite(long_rate):
        return -1e18
    if long_rate < 0.10 or long_rate > 0.90:
        return -1e18
    dd = abs(float(row.get("max_drawdown", 0.0)))
    return pf * math.log1p(trades) + pnl / 10_000.0 - dd / 20_000.0


def target_bps(row: pd.Series, side: str, config: Config) -> float:
    values: list[float] = []
    if side == "LONG":
        for col in UP_LEVEL_COLS:
            value = row.get(col, np.nan)
            if pd.notna(value) and float(value) < -float(config.min_target_bps):
                values.append(-float(value))
    else:
        for col in DOWN_LEVEL_COLS:
            value = row.get(col, np.nan)
            if pd.notna(value) and float(value) > float(config.min_target_bps):
                values.append(float(value))
    values = [v for v in values if float(config.min_target_bps) <= v <= float(config.max_target_bps)]
    return float(min(values)) if values else float("nan")


def gate_sides(row: pd.Series, gate: str) -> list[str]:
    near_hi = float(row.get("near_ib_high", 0.0) or 0.0) > 0.0
    near_lo = float(row.get("near_ib_low", 0.0) or 0.0) > 0.0
    above = float(row.get("above_ib", 0.0) or 0.0) > 0.0
    below = float(row.get("below_ib", 0.0) or 0.0) > 0.0
    bounce = float(row.get("bouncing_from_support", 0.0) or 0.0) > 0.0
    reject = float(row.get("rejecting_resistance", 0.0) or 0.0) > 0.0
    trend_up = float(row.get("trend_grind_up", 0.0) or 0.0) > 0.0
    trend_down = float(row.get("trend_flush_down", 0.0) or 0.0) > 0.0
    touch_fib = float(row.get("is_touching_fib", 0.0) or 0.0) > 0.0
    wall_fib = float(row.get("wall_at_fib", 0.0) or 0.0) > 0.0
    touch_max_gamma = float(row.get("is_touching_max_gamma", 0.0) or 0.0) > 0.0
    touch_min_gamma = float(row.get("is_touching_min_gamma", 0.0) or 0.0) > 0.0

    sides: list[str] = []
    if gate == "ib_reversal":
        if near_lo or below or bounce:
            sides.append("LONG")
        if near_hi or above or reject:
            sides.append("SHORT")
    elif gate == "breakout":
        if near_hi or above or trend_up:
            sides.append("LONG")
        if near_lo or below or trend_down:
            sides.append("SHORT")
    elif gate == "sr_combo":
        if near_lo or bounce or touch_min_gamma:
            sides.append("LONG")
        if near_hi or reject or touch_max_gamma:
            sides.append("SHORT")
    elif gate == "fib_wall":
        if touch_fib or wall_fib:
            sides.extend(["LONG", "SHORT"])
    else:
        sides.extend(["LONG", "SHORT"])
    return sides


def simulate_return(prices: np.ndarray, pos: int, side: str, target_bps_value: float, stop_bps: float, horizon_steps: int) -> tuple[float, int]:
    entry = float(prices[pos])
    end = min(len(prices) - 1, pos + int(horizon_steps))
    if not np.isfinite(entry) or entry <= 0.0 or end <= pos or not np.isfinite(target_bps_value):
        return float("nan"), 0
    target = float(target_bps_value) / 10_000.0
    stop = float(stop_bps) / 10_000.0
    for i in range(pos + 1, end + 1):
        raw = float(prices[i]) / entry - 1.0
        signed = raw if side == "LONG" else -raw
        if signed <= -stop:
            return -stop, i - pos
        if signed >= target:
            return target, i - pos
    raw = float(prices[end]) / entry - 1.0
    return (raw if side == "LONG" else -raw), end - pos


def eligible_signal_rows(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    rows: list[dict] = []
    work = frame[frame["minute"].astype(int) >= int(config.start_minute)].copy()
    for row in work.itertuples(index=False):
        series = pd.Series(row._asdict())
        candidates = []
        for side in gate_sides(series, config.gate):
            tgt = target_bps(series, side, config)
            if np.isfinite(tgt):
                candidates.append((side, tgt))
        if not candidates:
            continue
        side, tgt = min(candidates, key=lambda item: item[1])
        rows.append(
            {
                "ticker": str(series["ticker"]),
                "date": str(series["date"]),
                "time": str(series["time"]),
                "month": str(series["month"]),
                "minute": int(series["minute"]),
                "side": side,
                "target_bps": float(tgt),
            }
        )
    return pd.DataFrame(rows)


def apply_cooldown(signals: pd.DataFrame, cooldown_steps: int) -> pd.DataFrame:
    if signals.empty or int(cooldown_steps) <= 0:
        return signals.copy()
    kept: list[pd.Series] = []
    for _, day in signals.sort_values(["date", "minute"]).groupby("date", sort=False):
        next_allowed = -1
        for row in day.itertuples(index=False):
            minute = int(row.minute)
            if minute < next_allowed:
                continue
            kept.append(pd.Series(row._asdict()))
            next_allowed = minute + int(cooldown_steps) * 5
    return pd.DataFrame(kept) if kept else signals.iloc[0:0].copy()


def trades_for_config(frame: pd.DataFrame, config: Config, args) -> pd.DataFrame:
    signals = eligible_signal_rows(frame, config)
    signals = apply_cooldown(signals, int(round(float(args.cooldown_minutes) / 5.0)))
    if signals.empty:
        return pd.DataFrame()
    by_day_prices = {
        str(date): day.sort_values("minute")["spot_price"].astype(float).to_numpy()
        for date, day in frame.groupby("date", sort=False)
    }
    by_day_minutes = {
        str(date): day.sort_values("minute")["minute"].astype(int).to_numpy()
        for date, day in frame.groupby("date", sort=False)
    }
    rows: list[dict] = []
    for row in signals.itertuples(index=False):
        prices = by_day_prices.get(str(row.date))
        minutes = by_day_minutes.get(str(row.date))
        if prices is None or minutes is None:
            continue
        matches = np.flatnonzero(minutes == int(row.minute))
        if len(matches) == 0:
            continue
        ret, hold_steps = simulate_return(prices, int(matches[0]), str(row.side), float(row.target_bps), float(config.stop_bps), int(args.horizon_steps))
        if not np.isfinite(ret):
            continue
        rows.append(
            {
                "ticker": str(row.ticker),
                "date": str(row.date),
                "month": str(row.month),
                "time": str(row.time),
                "side": str(row.side),
                "target_bps": float(row.target_bps),
                "stop_bps": float(config.stop_bps),
                "hold_minutes": int(hold_steps) * 5,
                "return": float(ret),
                "pnl_dollars": float(ret) * float(args.notional),
                "config": config.name,
            }
        )
    return pd.DataFrame(rows)


def config_grid(args) -> list[Config]:
    out: list[Config] = []
    for gate in args.gates:
        for min_target in args.min_target_bps:
            for max_target in args.max_target_bps:
                if float(min_target) >= float(max_target):
                    continue
                for stop in args.stop_bps:
                    for start in args.start_minutes:
                        out.append(Config(str(gate), float(min_target), float(max_target), float(stop), int(start)))
    return out


def write_summary(output_dir: Path, metadata: dict, trades: pd.DataFrame, folds: pd.DataFrame) -> None:
    overall = metrics(trades)
    lines = [
        "# Level Target Signal Walk-Forward",
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
        json.dumps({ticker: metrics(frame) for ticker, frame in trades.groupby("ticker", sort=True)}, indent=2, allow_nan=True),
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward rule signal with dynamic level targets.")
    parser.add_argument("--data", default="training_data/training_data_spx_qqq_spy.parquet")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--train-start-date", default="20250101")
    parser.add_argument("--start-month", default="202507")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-val-trades", type=int, default=45)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--notional", type=float, default=100000.0)
    parser.add_argument("--gates", nargs="+", default=["fib_wall", "sr_combo", "ib_reversal"])
    parser.add_argument("--min-target-bps", nargs="+", type=float, default=[15.0, 25.0])
    parser.add_argument("--max-target-bps", nargs="+", type=float, default=[100.0, 150.0, 250.0])
    parser.add_argument("--stop-bps", nargs="+", type=float, default=[20.0, 30.0])
    parser.add_argument("--start-minutes", nargs="+", type=int, default=[570, 630])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(args.data)
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
    for col in set(UP_LEVEL_COLS + DOWN_LEVEL_COLS):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    grid = config_grid(args)
    all_trades: list[pd.DataFrame] = []
    all_signals: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    for ticker in tickers:
        tdf = df[df["ticker"] == ticker].sort_values(["date", "minute"]).copy()
        months = [
            m for m in sorted(tdf["month"].unique())
            if str(args.start_month) <= str(m) <= str(args.end_month)
        ]
        for test_month in months:
            prior = tdf[tdf["month"] < test_month].copy()
            test = tdf[tdf["month"] == test_month].copy()
            val_months = sorted(prior["month"].unique())[-int(args.val_months):]
            val = prior[prior["month"].isin(val_months)].copy()
            if val.empty or test.empty:
                continue
            best_config = grid[0]
            best_score = -1e18
            best_metrics: dict = {}
            for config in grid:
                val_trades = trades_for_config(val, config, args)
                row = metrics(val_trades)
                score = score_metrics(row, int(args.min_val_trades))
                if score > best_score:
                    best_score = score
                    best_config = config
                    best_metrics = row
            test_trades = trades_for_config(test, best_config, args)
            if not test_trades.empty:
                all_trades.append(test_trades)
            raw_signals = eligible_signal_rows(test, best_config)
            if not raw_signals.empty:
                raw_signals["config"] = best_config.name
                raw_signals["level_stop_bps"] = float(best_config.stop_bps)
                all_signals.append(raw_signals)
            test_metrics = metrics(test_trades)
            fold_rows.append(
                {
                    "ticker": ticker,
                    "month": test_month,
                    "config": best_config.name,
                    "val_months": ",".join(val_months),
                    **{f"val_{k}": v for k, v in best_metrics.items()},
                    **{f"test_{k}": v for k, v in test_metrics.items()},
                }
            )
            print(
                f"[LEVEL_WF] {ticker} {test_month} config={best_config.name} "
                f"val_pf={best_metrics.get('profit_factor', float('nan')):.3f} "
                f"test_trades={test_metrics.get('trades', 0)} "
                f"test_pf={test_metrics.get('profit_factor', float('nan')):.3f} "
                f"test_pnl={test_metrics.get('pnl_dollars', 0.0):.0f}"
            )

    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    signals = pd.concat(all_signals, ignore_index=True) if all_signals else pd.DataFrame()
    if not signals.empty:
        direction = np.where(signals["side"].astype(str) == "LONG", 1, -1).astype(np.int8)
        confidence = np.clip(signals["target_bps"].astype(float) / 100.0, 0.05, 0.95)
        signal_out = signals[["ticker", "date", "time"]].copy()
        signal_out["jepa180_prob_up"] = np.where(direction > 0, confidence, 1.0 - confidence)
        signal_out["jepa180_pred_bps"] = np.where(direction > 0, signals["target_bps"], -signals["target_bps"])
        signal_out["jepa180_long_threshold"] = 0.0
        signal_out["jepa180_short_threshold"] = 0.0
        signal_out["jepa180_confidence"] = confidence
        signal_out["jepa180_edge"] = confidence
        signal_out["jepa180_direction"] = direction
        signal_out["jepa180_signal"] = True
        signal_out["level_target_bps"] = signals["target_bps"].astype(float).to_numpy()
        signal_out["level_stop_bps"] = signals["level_stop_bps"].astype(float).to_numpy()
        signal_out["level_config"] = signals["config"].astype(str).to_numpy()
        signal_out.to_parquet(output_dir / "oof_rule_signals.parquet", index=False)
    trades.to_csv(output_dir / "level_target_wf_trades.csv", index=False)
    folds.to_csv(output_dir / "fold_configs.csv", index=False)
    metadata = {"args": vars(args), "grid_size": len(grid), "overall": metrics(trades)}
    (output_dir / "metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(output_dir, metadata, trades, folds)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
