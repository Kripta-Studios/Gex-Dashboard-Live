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

from neural.jepa.train_backtest_option_policy import (
    candidate_trades_from_selection,
    fixed_delta_policy,
    fmt_float,
    fmt_money,
    fmt_pct,
    normalize_date,
    oracle_policy,
    score_metrics,
    trade_metrics,
)


OUTCOME_PREFIXES = ("rule_", "hold180_", "oracle_")
DROP_COLUMNS = {
    "candidate_id",
    "signal_id",
    "date",
    "month",
    "time",
    "ticker",
    "side",
    "path_points",
}
LEAKY_SUBSTRINGS = (
    "pnl",
    "return_on_risk",
    "exit_time",
    "exit_reason",
    "hold_minutes",
)


def infer_features(frame: pd.DataFrame) -> list[str]:
    features = []
    for col in frame.columns:
        if col in DROP_COLUMNS:
            continue
        if col.startswith(OUTCOME_PREFIXES):
            continue
        if any(part in col for part in LEAKY_SUBSTRINGS):
            continue
        if pd.api.types.is_numeric_dtype(frame[col]):
            features.append(col)
    if not features:
        raise RuntimeError("No numeric non-leaky features inferred.")
    return features


def make_matrix(frame: pd.DataFrame, features: list[str], medians: pd.Series | None = None) -> tuple[pd.DataFrame, pd.Series]:
    x = frame.reindex(columns=features).apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if medians is None:
        medians = x.median(axis=0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    x = x.fillna(medians).fillna(0.0)
    return x.astype(np.float32), medians


def fit_models(train: pd.DataFrame, features: list[str], seed: int, n_estimators: int, n_jobs: int) -> dict:
    x, medians = make_matrix(train, features)
    y_return = train["rule_return_on_risk"].astype(float).clip(-2.0, 5.0)
    best_value = train.groupby("signal_id")["rule_pnl_dollars"].transform("max")
    y_best = (train["rule_pnl_dollars"].astype(float) >= best_value.astype(float) - 1e-9).astype(int)
    y_win = (train["rule_pnl_dollars"].astype(float) > 0.0).astype(int)

    reg = lgb.LGBMRegressor(
        objective="huber",
        alpha=0.90,
        n_estimators=int(n_estimators),
        learning_rate=0.035,
        num_leaves=31,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_samples=25,
        reg_alpha=0.05,
        reg_lambda=0.50,
        random_state=int(seed),
        n_jobs=int(n_jobs),
        verbose=-1,
    )
    best_cls = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=int(n_estimators),
        learning_rate=0.035,
        num_leaves=31,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_samples=25,
        reg_alpha=0.05,
        reg_lambda=0.50,
        class_weight="balanced",
        random_state=int(seed) + 1,
        n_jobs=int(n_jobs),
        verbose=-1,
    )
    win_cls = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=int(n_estimators),
        learning_rate=0.035,
        num_leaves=31,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_samples=25,
        reg_alpha=0.05,
        reg_lambda=0.50,
        class_weight="balanced",
        random_state=int(seed) + 2,
        n_jobs=int(n_jobs),
        verbose=-1,
    )
    reg.fit(x, y_return)
    best_cls.fit(x, y_best)
    win_cls.fit(x, y_win)
    return {"reg": reg, "best_cls": best_cls, "win_cls": win_cls, "medians": medians, "features": features}


def predict_models(models: dict, frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    x, _ = make_matrix(out, models["features"], models["medians"])
    out["_pred_return"] = models["reg"].predict(x).astype(float)
    out["_pred_best_prob"] = models["best_cls"].predict_proba(x)[:, 1].astype(float)
    out["_pred_win_prob"] = models["win_cls"].predict_proba(x)[:, 1].astype(float)
    return out


def fixed_candidate_per_signal(frame: pd.DataFrame, delta: float = 0.70) -> pd.DataFrame:
    work = frame.copy()
    work["_delta_gap_fixed"] = (work["delta_target"].astype(float) - float(delta)).abs()
    return (
        work.sort_values(["signal_id", "_delta_gap_fixed", "delta_target"])
        .groupby("signal_id", sort=False)
        .head(1)
        .drop(columns=["_delta_gap_fixed"])
        .reset_index(drop=True)
    )


def hybrid_select(frame: pd.DataFrame, config: dict, policy_name: str) -> pd.DataFrame:
    work = frame.copy()
    work["_hybrid_score"] = (
        work["_pred_return"].astype(float)
        + float(config["best_weight"]) * work["_pred_best_prob"].astype(float)
        + float(config["win_weight"]) * work["_pred_win_prob"].astype(float)
        + float(config["delta_bias"]) * work["actual_delta_abs"].astype(float)
    )
    fixed = fixed_candidate_per_signal(work, 0.70)
    fixed = fixed[["signal_id", "candidate_id", "_hybrid_score"]].rename(
        columns={"candidate_id": "_fixed_candidate_id", "_hybrid_score": "_fixed_score"}
    )
    allowed = work[work["actual_delta_abs"].astype(float) >= float(config["delta_floor"])].copy()
    best = allowed.sort_values(["signal_id", "_hybrid_score"]).groupby("signal_id", sort=False).tail(1)
    selected = best.merge(fixed, on="signal_id", how="left")
    selected["_score_edge"] = selected["_hybrid_score"].astype(float) - selected["_fixed_score"].astype(float)
    override_mask = selected["_score_edge"].astype(float) >= float(config["margin"])
    fallback_ids = selected.loc[~override_mask, "_fixed_candidate_id"].astype(int).tolist()
    keep = selected.loc[override_mask].copy()
    if fallback_ids:
        fallback = work[work["candidate_id"].astype(int).isin(fallback_ids)].copy()
        fallback["_score_edge"] = 0.0
        fallback["_fixed_candidate_id"] = fallback["candidate_id"].astype(int)
        keep = pd.concat([keep, fallback], ignore_index=True, sort=False)
    keep["selector_source"] = np.where(keep["candidate_id"].astype(int) == keep["_fixed_candidate_id"].astype(int), "fixed_070", "override")
    keep["policy"] = policy_name
    return keep.sort_values(["ticker", "date", "time"]).reset_index(drop=True)


def evaluate_config(frame: pd.DataFrame, config: dict, min_trades: int) -> tuple[pd.DataFrame, dict, float]:
    selected = hybrid_select(frame, config, "hybrid_selector")
    trades = candidate_trades_from_selection(selected, "rule", "hybrid_selector")
    metrics = trade_metrics(trades)
    return trades, metrics, score_metrics(metrics, min_trades)


def validation_grid(val_pred: pd.DataFrame, min_trades: int) -> pd.DataFrame:
    rows = []
    base_configs = []
    for delta_floor in [0.10, 0.30, 0.40, 0.50, 0.60]:
        for best_weight in [0.0, 0.50, 1.00, 1.50]:
            for win_weight in [0.0, 0.50, 1.00]:
                for delta_bias in [0.0, 0.10, 0.25, 0.50]:
                    base_configs.append(
                        {
                            "delta_floor": delta_floor,
                            "best_weight": best_weight,
                            "win_weight": win_weight,
                            "delta_bias": delta_bias,
                        }
                    )
    for base in base_configs:
        temp = val_pred.copy()
        temp["_hybrid_score"] = (
            temp["_pred_return"].astype(float)
            + float(base["best_weight"]) * temp["_pred_best_prob"].astype(float)
            + float(base["win_weight"]) * temp["_pred_win_prob"].astype(float)
            + float(base["delta_bias"]) * temp["actual_delta_abs"].astype(float)
        )
        fixed = fixed_candidate_per_signal(temp, 0.70)[["signal_id", "_hybrid_score"]].rename(columns={"_hybrid_score": "_fixed_score"})
        allowed = temp[temp["actual_delta_abs"].astype(float) >= float(base["delta_floor"])].copy()
        best = allowed.sort_values(["signal_id", "_hybrid_score"]).groupby("signal_id", sort=False).tail(1)
        edges = best.merge(fixed, on="signal_id", how="left")
        edges = (edges["_hybrid_score"].astype(float) - edges["_fixed_score"].astype(float)).replace([np.inf, -np.inf], np.nan).dropna()
        margins = [-1e9, 0.0]
        if len(edges):
            margins += [float(x) for x in np.quantile(edges, [0.25, 0.50, 0.60, 0.70, 0.80, 0.90])]
        for margin in sorted(set(margins)):
            config = dict(base)
            config["margin"] = float(margin)
            trades, metrics, score = evaluate_config(val_pred, config, min_trades)
            rows.append({"score": score, **config, **metrics})
    return pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)


def summarize_trades(name: str, trades: pd.DataFrame) -> dict:
    m = trade_metrics(trades)
    m["policy"] = name
    m["avg_delta_abs"] = float(trades["actual_delta_abs"].astype(float).mean()) if "actual_delta_abs" in trades and not trades.empty else float("nan")
    m["avg_hold_minutes"] = float(trades["hold_minutes"].astype(float).mean()) if "hold_minutes" in trades and not trades.empty else float("nan")
    return m


def write_summary(output_dir: Path, args, best_config: dict, metrics_rows: list[dict], per_ticker: pd.DataFrame, grid: pd.DataFrame) -> None:
    lines = [
        "# Hybrid Option Selector Research",
        "",
        f"Candidate labels: `{args.candidate_labels}`",
        f"Train cutoff: `{args.train_end_date}`",
        f"Test start: `{args.test_start_date}`",
        "",
        "## Best Validation Config",
        "",
        "```json",
        json.dumps(best_config, indent=2),
        "```",
        "",
        "## OOS Results",
        "",
        "| Policy | Trades | WR | PF | PnL | Max DD | Avg Delta | Avg Hold |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in metrics_rows:
        lines.append(
            f"| {row['policy']} | {int(row['trades'])} | {fmt_pct(row['win_rate'])} | "
            f"{fmt_float(row['profit_factor'])} | {fmt_money(row['pnl_dollars'])} | "
            f"{fmt_money(row['max_drawdown'])} | {fmt_float(row.get('avg_delta_abs', float('nan')))} | "
            f"{fmt_float(row.get('avg_hold_minutes', float('nan')), 1)} |"
        )
    lines += [
        "",
        "## Per Ticker OOS",
        "",
        "| Policy | Ticker | Trades | WR | PF | PnL | Avg Delta |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in per_ticker.iterrows():
        lines.append(
            f"| {row['policy']} | {row['ticker']} | {int(row['trades'])} | {fmt_pct(row['win_rate'])} | "
            f"{fmt_float(row['profit_factor'])} | {fmt_money(row['pnl_dollars'])} | {fmt_float(row['avg_delta_abs'])} |"
        )
    lines += [
        "",
        "## Top Validation Rows",
        "",
        "| Rank | Score | Floor | BestW | WinW | DeltaBias | Margin | Trades | WR | PF | PnL |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, (_, row) in enumerate(grid.head(15).iterrows(), start=1):
        lines.append(
            f"| {rank} | {fmt_float(row['score'])} | {row['delta_floor']:.2f} | {row['best_weight']:.2f} | "
            f"{row['win_weight']:.2f} | {row['delta_bias']:.2f} | {row['margin']:.3f} | "
            f"{int(row['trades'])} | {fmt_pct(row['win_rate'])} | {fmt_float(row['profit_factor'])} | "
            f"{fmt_money(row['pnl_dollars'])} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- This is a reversible research layer on top of candidate labels; it does not modify production artifacts.",
        "- The selector falls back to fixed 0.70 unless validation finds enough predicted edge to override it.",
        "- Promotion requires beating fixed 0.70 OOS and in rolling walk-forward, not just this split.",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Research hybrid option selector against fixed delta and oracle.")
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--train-start-date", default="20220801")
    parser.add_argument("--train-end-date", default="20260331")
    parser.add_argument("--test-start-date", default="20260401")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--n-estimators", type=int, default=260)
    parser.add_argument("--n-jobs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=4441)
    parser.add_argument("--min-val-trades", type=int, default=12)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = pd.read_parquet(args.candidate_labels)
    candidates["date"] = candidates["date"].astype(str).map(normalize_date)
    candidates["month"] = candidates["date"].str[:6]
    candidates = candidates[candidates["date"] >= normalize_date(args.train_start_date)].copy()
    train = candidates[candidates["date"] <= normalize_date(args.train_end_date)].copy()
    test = candidates[candidates["date"] >= normalize_date(args.test_start_date)].copy()
    train_months = sorted(train["month"].unique().tolist())
    val_months = set(train_months[-int(args.val_months) :])
    fit = train[~train["month"].isin(val_months)].copy()
    val = train[train["month"].isin(val_months)].copy()
    if fit.empty or val.empty or test.empty:
        raise RuntimeError("Empty fit/val/test split.")

    features = infer_features(candidates)
    models = fit_models(fit, features, int(args.seed), int(args.n_estimators), int(args.n_jobs))
    val_pred = predict_models(models, val)
    grid = validation_grid(val_pred, int(args.min_val_trades))
    best_config = {
        key: float(grid.iloc[0][key])
        for key in ["delta_floor", "best_weight", "win_weight", "delta_bias", "margin"]
    }

    final_models = fit_models(train, features, int(args.seed), int(args.n_estimators), int(args.n_jobs))
    test_pred = predict_models(final_models, test)
    hybrid_selected = hybrid_select(test_pred, best_config, "hybrid_override_070")
    hybrid_trades = candidate_trades_from_selection(hybrid_selected, "rule", "hybrid_override_070")

    fixed_070 = fixed_delta_policy(test, 0.70, "rule", "fixed_delta_0.70_hard")
    oracle_hard = oracle_policy(test, "rule_pnl_dollars", "rule", "oracle_best_delta_hard")
    oracle_exit = oracle_policy(test, "oracle_pnl_dollars", "oracle", "oracle_best_delta_oracle_exit")

    outputs = {
        "fixed_delta_0.70_hard": fixed_070,
        "hybrid_override_070": hybrid_trades,
        "oracle_best_delta_hard": oracle_hard,
        "oracle_best_delta_oracle_exit": oracle_exit,
    }
    for name, trades in outputs.items():
        trades.to_csv(output_dir / f"{name}_trades.csv", index=False)
    hybrid_selected.to_csv(output_dir / "hybrid_selected_candidates.csv", index=False)
    grid.to_csv(output_dir / "validation_grid.csv", index=False)

    metrics_rows = [summarize_trades(name, trades) for name, trades in outputs.items()]
    per_rows = []
    for name, trades in outputs.items():
        for ticker, group in trades.groupby("ticker", sort=True):
            row = summarize_trades(name, group)
            row["ticker"] = str(ticker)
            per_rows.append(row)
    per_ticker = pd.DataFrame(per_rows)
    pd.DataFrame(metrics_rows).to_csv(output_dir / "overall_metrics.csv", index=False)
    per_ticker.to_csv(output_dir / "per_ticker_metrics.csv", index=False)
    metadata = {
        "args": vars(args),
        "features": features,
        "feature_count": len(features),
        "best_config": best_config,
        "metrics": metrics_rows,
    }
    (output_dir / "metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(output_dir, args, best_config, metrics_rows, per_ticker, grid)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
