from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.backtest_jepa_180m import apply_cooldown, time_to_minutes
from neural.jepa.evaluate_180m_direction import build_terminal_180m_frame, trade_metrics
from neural.jepa.jepa_180m_signal import Jepa180mSignalModel, normalize_ticker


def normalize_date(value) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else str(value)


def fmt_float(value: float, digits: int = 3) -> str:
    return "nan" if value is None or not np.isfinite(value) else f"{float(value):.{digits}f}"


def fmt_pct(value: float) -> str:
    return "nan" if value is None or not np.isfinite(value) else f"{100.0 * float(value):.1f}%"


def fmt_money(value: float) -> str:
    return "nan" if value is None or not np.isfinite(value) else f"{float(value):+,.0f}"


def time_plus_minutes(value: object, minutes: int) -> str:
    try:
        hour, minute = [int(part) for part in str(value)[:5].split(":")]
    except Exception:
        return str(value)[:5]
    total = hour * 60 + minute + int(minutes)
    return f"{total // 60:02d}:{total % 60:02d}"


def prepare_raw_frame(data_path: Path) -> pd.DataFrame:
    raw = pd.read_parquet(data_path)
    raw["ticker"] = raw["ticker"].map(normalize_ticker)
    raw["date"] = raw["date"].map(normalize_date)
    raw = raw.sort_values(["ticker", "date", "time"]).reset_index(drop=True)
    raw["pos_in_day"] = raw.groupby(["ticker", "date"], sort=False).cumcount()
    return raw


def selected_signals(
    data_path: Path,
    model_dir: Path,
    mode: str,
    start_date: str,
    end_date: str | None,
    tickers: list[str],
    horizon_steps: int,
    cooldown_steps: int,
    min_entry_minute: int | None,
    max_entry_minute: int | None,
) -> pd.DataFrame:
    frame = build_terminal_180m_frame(data_path, horizon_steps, min_abs_bps=0.0)
    frame["ticker"] = frame["ticker"].map(normalize_ticker)
    frame["date"] = frame["date"].map(normalize_date)
    frame = frame[frame["date"] >= normalize_date(start_date)].copy()
    if end_date:
        frame = frame[frame["date"] <= normalize_date(end_date)].copy()
    if tickers:
        allowed = {normalize_ticker(t) for t in tickers}
        frame = frame[frame["ticker"].isin(allowed)].copy()
    if min_entry_minute is not None or max_entry_minute is not None:
        minutes = frame["time"].map(time_to_minutes)
        if min_entry_minute is not None:
            frame = frame[minutes >= int(min_entry_minute)].copy()
            minutes = frame["time"].map(time_to_minutes)
        if max_entry_minute is not None:
            frame = frame[minutes <= int(max_entry_minute)].copy()
    model = Jepa180mSignalModel(model_dir, mode, tickers=tickers)
    scored = model.predict_frame(frame)
    signals = scored[scored["jepa180_direction"].astype(int) != 0].copy()
    signals = apply_cooldown(signals, cooldown_steps)
    signals = signals.sort_values(["ticker", "date", "pos_in_day"]).reset_index(drop=True)
    signals["trade_id"] = np.arange(len(signals), dtype=np.int64)
    return signals


def build_state_rows(
    signals: pd.DataFrame,
    raw: pd.DataFrame,
    model: Jepa180mSignalModel,
    horizon_steps: int,
    cost_bps: float,
    notional: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scored_raw = model.predict_frame(raw)
    raw_by_key = {
        (str(ticker), str(date)): group.sort_values("pos_in_day").reset_index(drop=True)
        for (ticker, date), group in scored_raw.groupby(["ticker", "date"], sort=False)
    }
    state_rows: list[dict] = []
    fixed_trades: list[dict] = []
    for signal in signals.itertuples(index=False):
        key = (str(signal.ticker), str(signal.date))
        day = raw_by_key.get(key)
        if day is None:
            continue
        pos = int(signal.pos_in_day)
        end_pos = pos + int(horizon_steps)
        if pos < 0 or end_pos >= len(day):
            continue
        entry_spot = float(signal.spot_price)
        direction = int(signal.jepa180_direction)
        side = "LONG" if direction > 0 else "SHORT"
        path = day.iloc[pos + 1 : end_pos + 1].copy()
        pnl_values = []
        peak_bps = -1e18
        trough_bps = 1e18
        for step_idx, row in enumerate(path.itertuples(index=False), start=1):
            hold_minutes = int(step_idx * 5)
            spot = float(row.spot_price)
            gross_bps = direction * (spot / entry_spot - 1.0) * 10000.0
            net_bps = gross_bps - float(cost_bps)
            pnl_dollars = net_bps / 10000.0 * float(notional)
            pnl_values.append(pnl_dollars)
            peak_bps = max(peak_bps, net_bps)
            trough_bps = min(trough_bps, net_bps)
            state_rows.append(
                {
                    "trade_id": int(signal.trade_id),
                    "ticker": str(signal.ticker),
                    "date": str(signal.date),
                    "entry_time": str(signal.time),
                    "path_time": str(row.time),
                    "side": side,
                    "direction": direction,
                    "entry_spot": entry_spot,
                    "current_spot": spot,
                    "hold_minutes": hold_minutes,
                    "hold_norm": hold_minutes / float(horizon_steps * 5),
                    "minutes_remaining": float(max(0, horizon_steps - step_idx) * 5),
                    "entry_prob_up": float(signal.jepa180_prob_up),
                    "entry_confidence": float(signal.jepa180_confidence),
                    "current_prob_up": float(getattr(row, "jepa180_prob_up", np.nan)),
                    "current_confidence": float(getattr(row, "jepa180_confidence", np.nan)),
                    "current_net_bps": net_bps,
                    "current_pnl_dollars": pnl_dollars,
                    "peak_net_bps": peak_bps,
                    "drawdown_from_peak_bps": max(0.0, peak_bps - net_bps),
                    "mae_net_bps": trough_bps,
                }
            )
        if not pnl_values:
            continue
        fixed_pnl = float(pnl_values[-1])
        fixed_bps = fixed_pnl / float(notional) * 10000.0
        fixed_trades.append(
            {
                "trade_id": int(signal.trade_id),
                "ticker": str(signal.ticker),
                "date": str(signal.date),
                "time": str(signal.time),
                "entry_time": str(signal.time),
                "exit_time": time_plus_minutes(signal.time, horizon_steps * 5),
                "side": side,
                "spot_price": entry_spot,
                "net_bps": fixed_bps,
                "pnl_dollars": fixed_pnl,
                "hold_minutes": int(horizon_steps * 5),
                "exit_reason": "fixed_180m",
            }
        )
    states = pd.DataFrame(state_rows)
    fixed = pd.DataFrame(fixed_trades)
    if not states.empty:
        states["future_best_pnl_dollars"] = states.groupby("trade_id", sort=False)["current_pnl_dollars"].transform(
            lambda s: np.maximum.accumulate(s.astype(float).to_numpy()[::-1])[::-1]
        )
        states["terminal_pnl_dollars"] = states.groupby("trade_id", sort=False)["current_pnl_dollars"].transform("last")
    return states, fixed


EXIT_FEATURES = [
    "hold_norm",
    "minutes_remaining",
    "entry_prob_up",
    "entry_confidence",
    "current_prob_up",
    "current_confidence",
    "current_net_bps",
    "peak_net_bps",
    "drawdown_from_peak_bps",
    "mae_net_bps",
    "direction",
]


def fit_exit_model(train_states: pd.DataFrame, seed: int, n_estimators: int, n_jobs: int):
    features = [f for f in EXIT_FEATURES if f in train_states.columns]
    x = train_states[features].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    medians = x.median(axis=0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    x = x.fillna(medians).fillna(0.0)
    y = train_states["future_best_pnl_dollars"].astype(float)
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=int(n_estimators),
        learning_rate=0.035,
        num_leaves=31,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_samples=60,
        reg_alpha=0.05,
        reg_lambda=0.50,
        random_state=int(seed),
        n_jobs=int(n_jobs),
        verbose=-1,
    )
    model.fit(x, y)
    return model, features, medians


def predict_exit(model, features: list[str], medians: pd.Series, states: pd.DataFrame) -> np.ndarray:
    x = states[features].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    x = x.fillna(medians).fillna(0.0)
    return model.predict(x)


def simulate_exit(
    states: pd.DataFrame,
    model,
    features: list[str],
    medians: pd.Series,
    margin_dollars: float,
    min_hold_minutes: int,
    policy_name: str,
) -> pd.DataFrame:
    trades: list[dict] = []
    for trade_id, path in states.groupby("trade_id", sort=False):
        path = path.sort_values("hold_minutes").reset_index(drop=True)
        pred = predict_exit(model, features, medians, path)
        exit_row = path.iloc[-1]
        exit_reason = "max_time"
        for idx, row in path.iterrows():
            if int(row["hold_minutes"]) < int(min_hold_minutes):
                continue
            expected_best = float(pred[idx])
            current_pnl = float(row["current_pnl_dollars"])
            if expected_best <= current_pnl + float(margin_dollars):
                exit_row = row
                exit_reason = "learned_exit"
                break
        net_bps = float(exit_row["current_pnl_dollars"]) / 100000.0 * 10000.0
        trades.append(
            {
                "trade_id": int(trade_id),
                "ticker": str(exit_row["ticker"]),
                "date": str(exit_row["date"]),
                "time": str(exit_row["entry_time"]),
                "entry_time": str(exit_row["entry_time"]),
                "exit_time": str(exit_row["path_time"]),
                "side": str(exit_row["side"]),
                "spot_price": float(exit_row["entry_spot"]),
                "net_bps": net_bps,
                "pnl_dollars": float(exit_row["current_pnl_dollars"]),
                "hold_minutes": int(exit_row["hold_minutes"]),
                "exit_reason": exit_reason,
                "policy": policy_name,
            }
        )
    return pd.DataFrame(trades)


def oracle_exit(states: pd.DataFrame) -> pd.DataFrame:
    trades: list[dict] = []
    for trade_id, path in states.groupby("trade_id", sort=False):
        path = path.sort_values("hold_minutes").reset_index(drop=True)
        idx = path["current_pnl_dollars"].astype(float).idxmax()
        row = path.loc[idx]
        net_bps = float(row["current_pnl_dollars"]) / 100000.0 * 10000.0
        trades.append(
            {
                "trade_id": int(trade_id),
                "ticker": str(row["ticker"]),
                "date": str(row["date"]),
                "time": str(row["entry_time"]),
                "entry_time": str(row["entry_time"]),
                "exit_time": str(row["path_time"]),
                "side": str(row["side"]),
                "spot_price": float(row["entry_spot"]),
                "net_bps": net_bps,
                "pnl_dollars": float(row["current_pnl_dollars"]),
                "hold_minutes": int(row["hold_minutes"]),
                "exit_reason": "oracle_best_path",
                "policy": "oracle_exit",
            }
        )
    return pd.DataFrame(trades)


def choose_margin(val_states: pd.DataFrame, model, features: list[str], medians: pd.Series, min_hold_minutes: int) -> tuple[float, pd.DataFrame]:
    rows = []
    best_margin = 0.0
    best_score = -1e18
    for margin in [-750, -500, -250, -100, 0, 100, 250, 500, 750]:
        trades = simulate_exit(val_states, model, features, medians, margin, min_hold_minutes, "validation_learned_exit")
        m = trade_metrics(trades)
        pf = float(m.get("profit_factor", 0.0))
        pnl = float(m.get("pnl_dollars", 0.0))
        dd = abs(float(m.get("max_drawdown", 0.0)))
        score = pf * np.log1p(float(m.get("trades", 0))) + pnl / 10000.0 - dd / 5000.0
        rows.append({"margin_dollars": margin, "score": score, **m})
        if score > best_score:
            best_score = score
            best_margin = float(margin)
    return best_margin, pd.DataFrame(rows)


def metrics_row(label: str, frame: pd.DataFrame) -> str:
    m = trade_metrics(frame)
    avg_hold = frame["hold_minutes"].astype(float).mean() if not frame.empty and "hold_minutes" in frame else float("nan")
    return (
        f"| {label} | {m.get('trades', 0)} | {fmt_pct(m.get('win_rate', float('nan')))} | "
        f"{fmt_float(m.get('profit_factor', float('nan')))} | {fmt_float(m.get('avg_net_bps', float('nan')), 2)} | "
        f"{fmt_money(m.get('pnl_dollars', 0.0))} | {fmt_money(m.get('max_drawdown', 0.0))} | "
        f"{fmt_float(avg_hold, 1)} |"
    )


def write_summary(output_dir: Path, args, margin: float, val_grid: pd.DataFrame, results: dict[str, pd.DataFrame]) -> None:
    lines = [
        "# GBT+JEPA 180m Learned Exit Diagnostic",
        "",
        f"Data: `{args.data}`",
        f"Model dir: `{args.model_dir}`",
        f"Train cutoff: `{args.train_end_date}`",
        f"Test start: `{args.test_start_date}`",
        f"Selected margin: `${margin:.0f}`",
        "",
        "## OOS Results",
        "",
        "| Policy | Trades | WR | PF | Avg bps | PnL | Max DD | Avg Hold |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, frame in results.items():
        lines.append(metrics_row(label, frame))
    lines += [
        "",
        "## Validation Margin Grid",
        "",
        "| Margin $ | Trades | WR | PF | PnL | Max DD | Score |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in val_grid.iterrows():
        lines.append(
            f"| {row['margin_dollars']:.0f} | {int(row['trades'])} | {fmt_pct(row['win_rate'])} | "
            f"{fmt_float(row['profit_factor'])} | {fmt_money(row['pnl_dollars'])} | "
            f"{fmt_money(row['max_drawdown'])} | {fmt_float(row['score'])} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- `fixed_180m` is the promoted GBT+JEPA 180m contract.",
        "- `learned_exit` is diagnostic only; it is not promoted unless it beats fixed hold OOS without increasing drawdown materially.",
        "- `oracle_exit` is the non-deployable ceiling showing the maximum possible benefit of perfect exit timing.",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Test a learned 5m exit for GBT+JEPA 180m spot/proxy trades.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--mode", default="base_jepa")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--train-start-date", default="20220801")
    parser.add_argument("--train-end-date", default="20260331")
    parser.add_argument("--test-start-date", default="20260401")
    parser.add_argument("--test-end-date", default="")
    parser.add_argument("--tickers", nargs="*", default=["SPX", "QQQ", "SPY"])
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--cooldown-minutes", type=int, default=180)
    parser.add_argument("--cost-bps", type=float, default=1.0)
    parser.add_argument("--notional", type=float, default=100000.0)
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-hold-minutes", type=int, default=15)
    parser.add_argument("--n-estimators", type=int, default=180)
    parser.add_argument("--n-jobs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=3307)
    parser.add_argument("--min-entry-minute", type=int, default=None)
    parser.add_argument("--max-entry-minute", type=int, default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = Path(args.data)
    model_dir = Path(args.model_dir)
    cooldown_steps = max(0, int(round(float(args.cooldown_minutes) / 5.0)))

    raw = prepare_raw_frame(data_path)
    all_signals = selected_signals(
        data_path,
        model_dir,
        args.mode,
        args.train_start_date,
        args.test_end_date or None,
        args.tickers,
        int(args.horizon_steps),
        cooldown_steps,
        args.min_entry_minute,
        args.max_entry_minute,
    )
    model = Jepa180mSignalModel(model_dir, args.mode, tickers=args.tickers)
    states, fixed = build_state_rows(all_signals, raw, model, int(args.horizon_steps), float(args.cost_bps), float(args.notional))
    if states.empty or fixed.empty:
        raise RuntimeError("No state rows/trades were built.")

    fixed["date"] = fixed["date"].astype(str).map(normalize_date)
    states["date"] = states["date"].astype(str).map(normalize_date)
    fixed["month"] = fixed["date"].str[:6]
    states["month"] = states["date"].str[:6]

    train_fixed = fixed[fixed["date"] <= normalize_date(args.train_end_date)].copy()
    test_fixed = fixed[fixed["date"] >= normalize_date(args.test_start_date)].copy()
    train_months = sorted(train_fixed["month"].unique().tolist())
    val_months = set(train_months[-int(args.val_months) :]) if train_months else set()
    fit_ids = set(train_fixed[~train_fixed["month"].isin(val_months)]["trade_id"].astype(int))
    val_ids = set(train_fixed[train_fixed["month"].isin(val_months)]["trade_id"].astype(int))
    test_ids = set(test_fixed["trade_id"].astype(int))
    if not fit_ids or not val_ids or not test_ids:
        raise RuntimeError("Train/val/test split produced an empty trade set.")

    fit_states = states[states["trade_id"].astype(int).isin(fit_ids)].copy()
    val_states = states[states["trade_id"].astype(int).isin(val_ids)].copy()
    test_states = states[states["trade_id"].astype(int).isin(test_ids)].copy()

    exit_model, features, medians = fit_exit_model(fit_states, int(args.seed), int(args.n_estimators), int(args.n_jobs))
    margin, val_grid = choose_margin(val_states, exit_model, features, medians, int(args.min_hold_minutes))
    learned_test = simulate_exit(test_states, exit_model, features, medians, margin, int(args.min_hold_minutes), "learned_exit")
    oracle_test = oracle_exit(test_states)

    results = {
        "fixed_180m": test_fixed,
        "learned_exit": learned_test,
        "oracle_exit": oracle_test,
    }
    for name, frame in results.items():
        frame.to_csv(output_dir / f"{name}_trades.csv", index=False)
    val_grid.to_csv(output_dir / "validation_margin_grid.csv", index=False)
    metadata = {
        "args": vars(args),
        "signals": int(len(all_signals)),
        "fixed_trades": int(len(fixed)),
        "train_trades": int(len(train_fixed)),
        "test_trades": int(len(test_fixed)),
        "val_months": sorted(val_months),
        "exit_features": features,
        "selected_margin_dollars": margin,
        "metrics": {name: trade_metrics(frame) for name, frame in results.items()},
    }
    (output_dir / "metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(output_dir, args, margin, val_grid, results)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
