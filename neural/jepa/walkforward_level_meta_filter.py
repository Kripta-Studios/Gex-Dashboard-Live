from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import (
    build_price_cache,
    metrics,
    month_add,
    month_range,
    normalize_date,
    simulate_return,
    time_to_minutes,
)


LEAKY_PATTERNS = (
    "target",
    "time_to",
    "future",
    "pnl",
    "return",
    "label",
    "outcome",
    "max_move",
    "hit",
    "exit",
)


@dataclass(frozen=True)
class DeployConfig:
    threshold: float
    max_trades_per_day: int

    @property
    def name(self) -> str:
        max_day = "all" if self.max_trades_per_day >= 999 else str(self.max_trades_per_day)
        return f"thr{self.threshold:.2f}_maxday{max_day}"


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


def select_feature_columns(columns: list[str]) -> list[str]:
    selected = []
    for col in columns:
        low = str(col).lower()
        if col in {"ticker", "date", "time", "timestamp"}:
            continue
        if any(pattern in low for pattern in LEAKY_PATTERNS):
            continue
        selected.append(col)
    return selected


def load_labeled_signals(args: argparse.Namespace) -> tuple[pd.DataFrame, list[str]]:
    signals = pd.read_parquet(args.signals)
    signals["ticker"] = signals["ticker"].astype(str).str.upper()
    signals["date"] = signals["date"].map(normalize_date)
    signals["time"] = signals["time"].astype(str).str[:5]
    signals["month"] = signals["date"].str[:6]
    signals["minute"] = signals["time"].map(time_to_minutes).astype(int)
    signals = signals[signals["jepa180_direction"].astype(int) != 0].copy()
    signals["side"] = np.where(signals["jepa180_direction"].astype(int) > 0, "LONG", "SHORT")
    signals["side_sign"] = np.where(signals["side"].eq("LONG"), 1.0, -1.0)

    data = pd.read_parquet(args.data)
    data["ticker"] = data["ticker"].astype(str).str.upper()
    data["date"] = data["date"].map(normalize_date)
    data["time"] = data["time"].astype(str).str[:5]
    feature_cols = select_feature_columns(data.columns.tolist())
    data = data[["ticker", "date", "time", *feature_cols]].drop_duplicates(["ticker", "date", "time"])

    merged = signals.merge(data, on=["ticker", "date", "time"], how="left")
    config_dummies = pd.get_dummies(merged["level_config"].astype(str), prefix="cfg", dtype=float)
    merged = pd.concat([merged, config_dummies], axis=1)

    signal_features = [
        "jepa180_prob_up",
        "jepa180_pred_bps",
        "jepa180_confidence",
        "jepa180_edge",
        "level_target_bps",
        "level_stop_bps",
        "minute",
        "side_sign",
    ]
    model_features = [
        col
        for col in [*feature_cols, *signal_features, *config_dummies.columns.tolist()]
        if col in merged.columns and pd.api.types.is_numeric_dtype(merged[col])
    ]

    prices = pd.read_parquet(args.data, columns=["ticker", "date", "time", "spot_price"])
    prices["ticker"] = prices["ticker"].astype(str).str.upper()
    prices["date"] = prices["date"].map(normalize_date)
    prices["time"] = prices["time"].astype(str).str[:5]
    prices["minute"] = prices["time"].map(time_to_minutes).astype(int)
    prices = prices.sort_values(["ticker", "date", "minute"]).reset_index(drop=True)
    price_cache = build_price_cache(prices)
    prices_by_day, minutes_by_day = price_cache

    rows: list[dict] = []
    for values in merged.to_dict("records"):
        key = (str(values["ticker"]), str(values["date"]))
        day_prices = prices_by_day.get(key)
        day_minutes = minutes_by_day.get(key)
        if day_prices is None or day_minutes is None:
            continue
        matches = np.flatnonzero(day_minutes == int(values["minute"]))
        if len(matches) == 0:
            continue
        ret, hold_steps, exit_reason = simulate_return(
            day_prices,
            int(matches[0]),
            str(values["side"]),
            float(values["level_target_bps"]),
            float(values["level_stop_bps"]),
            int(args.horizon_steps),
        )
        if not np.isfinite(ret):
            continue
        values["return"] = float(ret)
        values["pnl_dollars"] = float(ret) * float(args.notional)
        values["hold_minutes"] = int(hold_steps) * 5
        values["exit_reason"] = exit_reason
        values["win"] = 1 if float(ret) > 0.0 else 0
        rows.append(values)
    labeled = pd.DataFrame(rows)
    return labeled, model_features


def deploy_trades(frame: pd.DataFrame, cfg: DeployConfig, cooldown_minutes: int) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    candidates = frame[frame["meta_score"].astype(float) >= float(cfg.threshold)].copy()
    if candidates.empty:
        return candidates
    rows: list[dict] = []
    cooldown = int(cooldown_minutes)
    max_day = int(cfg.max_trades_per_day)
    for _, day in candidates.sort_values(["date", "minute"]).groupby("date", sort=False):
        next_allowed = -1
        taken = 0
        for row in day.itertuples(index=False):
            minute = int(row.minute)
            if minute < next_allowed:
                continue
            if taken >= max_day:
                break
            values = row._asdict()
            values["deploy_config"] = cfg.name
            rows.append(values)
            taken += 1
            next_allowed = minute + cooldown
    return pd.DataFrame(rows) if rows else candidates.iloc[0:0].copy()


def fit_predict_fold(
    ticker: str,
    test_month: str,
    frame: pd.DataFrame,
    feature_cols: list[str],
    args: argparse.Namespace,
    grid: list[DeployConfig],
) -> tuple[pd.DataFrame, dict] | None:
    val_months = [month_add(test_month, -i) for i in range(int(args.val_months), 0, -1)]
    first_val = val_months[0]
    train = frame[frame["month"].astype(str) < first_val].copy()
    val = frame[frame["month"].astype(str).isin(val_months)].copy()
    test = frame[frame["month"].astype(str) == str(test_month)].copy()
    if len(train) < int(args.min_train_rows) or len(val) < int(args.min_val_trades) or test.empty:
        return None
    needs_classifier = str(args.model_kind) in {"classifier", "hybrid"}
    needs_regressor = str(args.model_kind) in {"return", "hybrid"}
    if needs_classifier and train["win"].nunique() < 2:
        return None

    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    classifier = None
    regressor = None
    if needs_classifier:
        y_train = train["win"].astype(int)
        classifier = lgb.LGBMClassifier(
            objective="binary",
            n_estimators=int(args.n_estimators),
            learning_rate=float(args.learning_rate),
            num_leaves=int(args.num_leaves),
            min_child_samples=int(args.min_child_samples),
            subsample=float(args.subsample),
            colsample_bytree=float(args.colsample_bytree),
            reg_lambda=float(args.reg_lambda),
            class_weight="balanced",
            random_state=int(args.seed) + int(test_month[-2:]),
            n_jobs=int(args.lgb_jobs),
            verbose=-1,
        )
        classifier.fit(x_train, y_train)
    if needs_regressor:
        y_return = train["return"].astype(float)
        regressor = lgb.LGBMRegressor(
            objective=str(args.regression_objective),
            n_estimators=int(args.n_estimators),
            learning_rate=float(args.learning_rate),
            num_leaves=int(args.num_leaves),
            min_child_samples=int(args.min_child_samples),
            subsample=float(args.subsample),
            colsample_bytree=float(args.colsample_bytree),
            reg_lambda=float(args.reg_lambda),
            random_state=int(args.seed) + int(test_month[-2:]) + 10_000,
            n_jobs=int(args.lgb_jobs),
            verbose=-1,
        )
        regressor.fit(x_train, y_return)

    def with_score(part: pd.DataFrame) -> pd.DataFrame:
        if part.empty:
            return part.copy()
        x_part = part[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
        out = part.copy()
        if classifier is not None:
            out["meta_prob"] = classifier.predict_proba(x_part)[:, 1]
        else:
            out["meta_prob"] = np.nan
        if regressor is not None:
            out["meta_ev"] = regressor.predict(x_part)
        else:
            out["meta_ev"] = np.nan
        if str(args.model_kind) == "classifier":
            out["meta_score"] = out["meta_prob"].astype(float)
        elif str(args.model_kind) == "return":
            out["meta_score"] = out["meta_ev"].astype(float)
        else:
            # Keep the return model in native bps/return scale, with probability only
            # as a weak tie-breaker. Threshold grids remain interpretable as EV cuts.
            out["meta_score"] = out["meta_ev"].astype(float) + (out["meta_prob"].astype(float) - 0.5) * float(args.hybrid_prob_weight)
        return out

    val_scored = with_score(val)
    test_scored = with_score(test)
    best_cfg = grid[0]
    best_score = -1e18
    best_metrics: dict = {}
    for cfg in grid:
        val_trades = deploy_trades(val_scored, cfg, int(args.cooldown_minutes))
        row = metrics(val_trades, val_months)
        score = score_metrics(row, int(args.min_val_trades), int(args.min_month_trades))
        if score > best_score:
            best_cfg = cfg
            best_score = score
            best_metrics = row

    test_trades = deploy_trades(test_scored, best_cfg, int(args.cooldown_minutes))
    test_metrics = metrics(test_trades, [str(test_month)])
    if not test_trades.empty:
        test_trades["test_month"] = test_month
    fold_row = {
        "ticker": ticker,
        "month": test_month,
        "deploy_config": best_cfg.name,
        "val_months": ",".join(val_months),
        "train_rows": int(len(train)),
        "val_rows": int(len(val)),
        "test_rows": int(len(test)),
        "model_kind": str(args.model_kind),
        "val_score": float(best_score),
        **{f"val_{k}": v for k, v in best_metrics.items()},
        **{f"test_{k}": v for k, v in test_metrics.items()},
    }
    print(
        f"[LEVEL_META] {ticker} {test_month} cfg={best_cfg.name} "
        f"val_pf={best_metrics.get('profit_factor', float('nan')):.3f} "
        f"test_trades={test_metrics.get('trades', 0)} "
        f"test_pf={test_metrics.get('profit_factor', float('nan')):.3f} "
        f"test_pnl={test_metrics.get('pnl_dollars', 0.0):.0f}",
        flush=True,
    )
    return test_trades, fold_row


def write_summary(output_dir: Path, metadata: dict, trades: pd.DataFrame, folds: pd.DataFrame) -> None:
    args_meta = metadata.get("args", {})
    expected_months = month_range(str(args_meta.get("start_month", "")), str(args_meta.get("end_month", ""))) if args_meta.get("start_month") and args_meta.get("end_month") else None
    overall = metrics(trades, expected_months)
    per_ticker = {
        str(ticker): metrics(frame, expected_months)
        for ticker, frame in trades.groupby("ticker", sort=True)
    } if not trades.empty else {}
    lines = [
        "# Level Signal Meta Filter",
        "",
        "Causal diagnostic: each test month is scored by LightGBM models trained before the validation window; threshold/max-day are selected on prior validation months only.",
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


def checkpoint(output_dir: Path, trades: list[pd.DataFrame], folds: list[dict], metadata: dict) -> None:
    trade_df = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    fold_df = pd.DataFrame(folds)
    args_meta = metadata.get("args", {})
    expected_months = month_range(str(args_meta.get("start_month", "")), str(args_meta.get("end_month", ""))) if args_meta.get("start_month") and args_meta.get("end_month") else None
    if not trade_df.empty:
        trade_df.to_csv(output_dir / "level_meta_filter_trades.csv", index=False)
    if not fold_df.empty:
        fold_df.to_csv(output_dir / "fold_configs.csv", index=False)
    (output_dir / "metrics.json").write_text(
        json.dumps({"overall": metrics(trade_df, expected_months), "metadata": metadata}, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    write_summary(output_dir, metadata, trade_df, fold_df)


def load_checkpoint(output_dir: Path, resume: bool) -> tuple[list[pd.DataFrame], list[dict], set[tuple[str, str]]]:
    if not resume:
        return [], [], set()
    trades_path = output_dir / "level_meta_filter_trades.csv"
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


def build_grid(thresholds: list[float], max_days: list[int]) -> list[DeployConfig]:
    return [DeployConfig(float(thr), int(max_day)) for thr in thresholds for max_day in max_days]


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal LightGBM meta-filter over level-rule signals.")
    parser.add_argument("--data", default="training_data/training_data_spx_qqq_spy.parquet")
    parser.add_argument("--signals", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202507")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-train-rows", type=int, default=250)
    parser.add_argument("--min-val-trades", type=int, default=45)
    parser.add_argument("--min-month-trades", type=int, default=15)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--notional", type=float, default=100000.0)
    parser.add_argument("--n-estimators", type=int, default=250)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--num-leaves", type=int, default=31)
    parser.add_argument("--min-child-samples", type=int, default=80)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.85)
    parser.add_argument("--reg-lambda", type=float, default=5.0)
    parser.add_argument("--model-kind", choices=["classifier", "return", "hybrid"], default="classifier")
    parser.add_argument("--regression-objective", default="regression_l1")
    parser.add_argument("--hybrid-prob-weight", type=float, default=0.0005)
    parser.add_argument("--lgb-jobs", type=int, default=8)
    parser.add_argument("--threshold-grid", nargs="+", type=float, default=[0.0, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70])
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[999, 4, 2, 1])
    parser.add_argument("--seed", type=int, default=20260616)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    labeled, feature_cols = load_labeled_signals(args)
    tickers = [str(t).upper() for t in args.tickers]
    labeled = labeled[
        labeled["ticker"].isin(tickers)
        & (labeled["month"].astype(str) <= str(args.end_month))
    ].copy()
    grid = build_grid(args.threshold_grid, args.max_day_grid)
    metadata = {
        "args": vars(args),
        "feature_count": len(feature_cols),
        "features": feature_cols,
        "grid": [asdict(cfg) for cfg in grid],
    }
    all_trades, fold_rows, done = load_checkpoint(output_dir, resume=not args.no_resume)
    months = [m for m in sorted(labeled["month"].astype(str).unique()) if str(args.start_month) <= m <= str(args.end_month)]
    for ticker in tickers:
        frame = labeled[labeled["ticker"].astype(str) == ticker].copy()
        for test_month in months:
            fold_key = (ticker, str(test_month))
            if fold_key in done:
                print(f"[LEVEL_META] skip checkpointed {ticker} {test_month}", flush=True)
                continue
            result = fit_predict_fold(ticker, str(test_month), frame, feature_cols, args, grid)
            if result is None:
                continue
            test_trades, fold_row = result
            if not test_trades.empty:
                all_trades.append(test_trades)
            fold_rows.append(fold_row)
            done.add(fold_key)
            checkpoint(output_dir, all_trades, fold_rows, metadata)

    checkpoint(output_dir, all_trades, fold_rows, metadata)
    trade_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    print(json.dumps(metrics(trade_df, month_range(str(args.start_month), str(args.end_month))), indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
