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

from neural.jepa.research_hybrid_option_selector import fixed_candidate_per_signal, infer_features, make_matrix
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


def add_fixed_excess_labels(frame: pd.DataFrame, fixed_delta: float) -> pd.DataFrame:
    fixed = fixed_candidate_per_signal(frame, fixed_delta)
    fixed_cols = [
        "signal_id",
        "candidate_id",
        "rule_pnl_dollars",
        "rule_return_on_risk",
        "actual_delta_abs",
    ]
    fixed = fixed[fixed_cols].rename(
        columns={
            "candidate_id": "_fixed_candidate_id",
            "rule_pnl_dollars": "_fixed_rule_pnl_dollars",
            "rule_return_on_risk": "_fixed_rule_return_on_risk",
            "actual_delta_abs": "_fixed_delta_abs",
        }
    )
    out = frame.merge(fixed, on="signal_id", how="left")
    out["excess_rule_pnl_dollars"] = out["rule_pnl_dollars"].astype(float) - out["_fixed_rule_pnl_dollars"].astype(float)
    out["excess_rule_return_on_risk"] = out["rule_return_on_risk"].astype(float) - out["_fixed_rule_return_on_risk"].astype(float)
    out["beats_fixed_rule"] = (out["excess_rule_pnl_dollars"].astype(float) > 0.0).astype(int)
    best_value = out.groupby("signal_id")["rule_pnl_dollars"].transform("max")
    out["is_oracle_hard_best"] = (out["rule_pnl_dollars"].astype(float) >= best_value.astype(float) - 1e-9).astype(int)
    out["is_fixed_candidate"] = (out["candidate_id"].astype(int) == out["_fixed_candidate_id"].astype(int)).astype(int)
    return out


def fit_models(train: pd.DataFrame, features: list[str], seed: int, n_estimators: int, n_jobs: int) -> dict:
    x, medians = make_matrix(train, features)
    y_excess = train["excess_rule_pnl_dollars"].astype(float).clip(-2500.0, 5000.0)
    y_beat = train["beats_fixed_rule"].astype(int)
    y_best = train["is_oracle_hard_best"].astype(int)

    reg = lgb.LGBMRegressor(
        objective="huber",
        alpha=0.85,
        n_estimators=int(n_estimators),
        learning_rate=0.035,
        num_leaves=31,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_samples=25,
        reg_alpha=0.05,
        reg_lambda=0.75,
        random_state=int(seed),
        n_jobs=int(n_jobs),
        verbose=-1,
    )
    beat_cls = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=int(n_estimators),
        learning_rate=0.035,
        num_leaves=31,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_samples=25,
        reg_alpha=0.05,
        reg_lambda=0.75,
        class_weight="balanced",
        random_state=int(seed) + 11,
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
        reg_lambda=0.75,
        class_weight="balanced",
        random_state=int(seed) + 17,
        n_jobs=int(n_jobs),
        verbose=-1,
    )
    reg.fit(x, y_excess)
    beat_cls.fit(x, y_beat)
    best_cls.fit(x, y_best)
    return {"reg": reg, "beat_cls": beat_cls, "best_cls": best_cls, "medians": medians, "features": features}


def predict_models(models: dict, frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    x, _ = make_matrix(out, models["features"], models["medians"])
    out["_pred_excess_pnl"] = models["reg"].predict(x).astype(float)
    out["_pred_beats_fixed_prob"] = models["beat_cls"].predict_proba(x)[:, 1].astype(float)
    out["_pred_best_prob"] = models["best_cls"].predict_proba(x)[:, 1].astype(float)
    return out


def select_excess(frame: pd.DataFrame, config: dict, policy_name: str) -> pd.DataFrame:
    work = frame.copy()
    work["_excess_score"] = (
        work["_pred_excess_pnl"].astype(float)
        + float(config["beat_weight"]) * (work["_pred_beats_fixed_prob"].astype(float) - 0.50) * 1000.0
        + float(config["best_weight"]) * work["_pred_best_prob"].astype(float) * 1000.0
        + float(config["delta_bias"]) * (work["actual_delta_abs"].astype(float) - 0.70) * 1000.0
    )
    fixed = fixed_candidate_per_signal(work, float(config["fixed_delta"]))
    fixed = fixed[["signal_id", "candidate_id", "_excess_score"]].rename(
        columns={"candidate_id": "_fixed_candidate_id", "_excess_score": "_fixed_score"}
    )
    allowed = work[work["actual_delta_abs"].astype(float) >= float(config["delta_floor"])].copy()
    best = allowed.sort_values(["signal_id", "_excess_score"]).groupby("signal_id", sort=False).tail(1)
    best = best.drop(columns=["_fixed_candidate_id", "_fixed_score"], errors="ignore")
    selected = best.merge(fixed, on="signal_id", how="left")
    selected["_score_edge_vs_fixed"] = selected["_excess_score"].astype(float) - selected["_fixed_score"].astype(float)
    override = selected["_score_edge_vs_fixed"].astype(float) >= float(config["margin"])
    fallback_ids = selected.loc[~override, "_fixed_candidate_id"].dropna().astype(int).tolist()
    keep = selected.loc[override].copy()
    if fallback_ids:
        fallback = work[work["candidate_id"].astype(int).isin(fallback_ids)].copy()
        fallback["_score_edge_vs_fixed"] = 0.0
        fallback["_fixed_candidate_id"] = fallback["candidate_id"].astype(int)
        keep = pd.concat([keep, fallback], ignore_index=True, sort=False)
    keep["selector_source"] = np.where(
        keep["candidate_id"].astype(int) == keep["_fixed_candidate_id"].astype(int),
        "fixed_070",
        "excess_override",
    )
    keep["policy"] = policy_name
    return keep.sort_values(["ticker", "date", "time"]).reset_index(drop=True)


def evaluate_config(frame: pd.DataFrame, config: dict, min_trades: int) -> tuple[pd.DataFrame, dict, float]:
    selected = select_excess(frame, config, "excess_vs_fixed_selector")
    trades = candidate_trades_from_selection(selected, "rule", "excess_vs_fixed_selector")
    metrics = trade_metrics(trades)
    return trades, metrics, score_metrics(metrics, min_trades)


def validation_grid(val_pred: pd.DataFrame, fixed_delta: float, min_trades: int) -> pd.DataFrame:
    rows = []
    bases = []
    for delta_floor in [0.10, 0.30, 0.40, 0.50, 0.60]:
        for beat_weight in [0.0, 0.25, 0.50, 1.00, 1.50]:
            for best_weight in [0.0, 0.25, 0.50, 1.00]:
                for delta_bias in [-0.25, 0.0, 0.10, 0.25, 0.50]:
                    bases.append(
                        {
                            "fixed_delta": float(fixed_delta),
                            "delta_floor": float(delta_floor),
                            "beat_weight": float(beat_weight),
                            "best_weight": float(best_weight),
                            "delta_bias": float(delta_bias),
                        }
                    )
    for base in bases:
        temp = val_pred.copy()
        temp["_excess_score"] = (
            temp["_pred_excess_pnl"].astype(float)
            + float(base["beat_weight"]) * (temp["_pred_beats_fixed_prob"].astype(float) - 0.50) * 1000.0
            + float(base["best_weight"]) * temp["_pred_best_prob"].astype(float) * 1000.0
            + float(base["delta_bias"]) * (temp["actual_delta_abs"].astype(float) - 0.70) * 1000.0
        )
        fixed = fixed_candidate_per_signal(temp, fixed_delta)[["signal_id", "_excess_score"]].rename(
            columns={"_excess_score": "_fixed_score"}
        )
        allowed = temp[temp["actual_delta_abs"].astype(float) >= float(base["delta_floor"])].copy()
        best = allowed.sort_values(["signal_id", "_excess_score"]).groupby("signal_id", sort=False).tail(1)
        edges = best.merge(fixed, on="signal_id", how="left")
        edge_values = (
            edges["_excess_score"].astype(float) - edges["_fixed_score"].astype(float)
        ).replace([np.inf, -np.inf], np.nan).dropna()
        margins = [-1e9, 0.0, 100.0, 250.0, 500.0, 750.0, 1000.0]
        if len(edge_values):
            margins += [float(x) for x in np.quantile(edge_values, [0.50, 0.60, 0.70, 0.80, 0.90])]
        for margin in sorted(set(margins)):
            config = dict(base)
            config["margin"] = float(margin)
            trades, metrics, score = evaluate_config(val_pred, config, min_trades)
            rows.append({"score": float(score), **config, **metrics})
    return pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)


def summarize_trades(name: str, trades: pd.DataFrame) -> dict:
    metrics = trade_metrics(trades)
    metrics["policy"] = name
    metrics["avg_delta_abs"] = float(trades["actual_delta_abs"].astype(float).mean()) if "actual_delta_abs" in trades and not trades.empty else float("nan")
    metrics["avg_hold_minutes"] = float(trades["hold_minutes"].astype(float).mean()) if "hold_minutes" in trades and not trades.empty else float("nan")
    return metrics


def write_summary(output_dir: Path, args, best_config: dict, metrics_rows: list[dict], per_ticker: pd.DataFrame, grid: pd.DataFrame) -> None:
    lines = [
        "# Excess-Vs-Fixed Option Selector Research",
        "",
        f"Candidate labels: `{args.candidate_labels}`",
        f"Train cutoff: `{args.train_end_date}`",
        f"Test start: `{args.test_start_date}`",
        "",
        "This selector directly predicts candidate excess PnL versus the fixed 0.70 delta candidate for the same signal. It falls back to fixed 0.70 unless validation-selected predicted edge clears the margin.",
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
        "| Rank | Score | Floor | BeatW | BestW | DeltaBias | Margin | Trades | WR | PF | PnL |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, (_, row) in enumerate(grid.head(15).iterrows(), start=1):
        lines.append(
            f"| {rank} | {fmt_float(row['score'])} | {row['delta_floor']:.2f} | {row['beat_weight']:.2f} | "
            f"{row['best_weight']:.2f} | {row['delta_bias']:.2f} | {row['margin']:.1f} | "
            f"{int(row['trades'])} | {fmt_pct(row['win_rate'])} | {fmt_float(row['profit_factor'])} | "
            f"{fmt_money(row['pnl_dollars'])} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- This is a reversible research layer and does not modify production artifacts.",
        "- Promotion requires beating fixed 0.70 OOS and in rolling walk-forward.",
        "- If validation selects a high margin or fixed-only behavior, that means the model did not find robust override alpha.",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Research selector trained on excess PnL versus fixed 0.70 delta.")
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--train-start-date", default="20220801")
    parser.add_argument("--train-end-date", default="20260331")
    parser.add_argument("--test-start-date", default="20260401")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--fixed-delta", type=float, default=0.70)
    parser.add_argument("--n-estimators", type=int, default=260)
    parser.add_argument("--n-jobs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=5521)
    parser.add_argument("--min-val-trades", type=int, default=12)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = pd.read_parquet(args.candidate_labels)
    candidates["date"] = candidates["date"].astype(str).map(normalize_date)
    candidates["month"] = candidates["date"].str[:6]
    candidates = candidates[candidates["date"] >= normalize_date(args.train_start_date)].copy()
    candidates = add_fixed_excess_labels(candidates, float(args.fixed_delta))

    train = candidates[candidates["date"] <= normalize_date(args.train_end_date)].copy()
    test = candidates[candidates["date"] >= normalize_date(args.test_start_date)].copy()
    train_months = sorted(train["month"].unique().tolist())
    val_months = set(train_months[-int(args.val_months) :])
    fit = train[~train["month"].isin(val_months)].copy()
    val = train[train["month"].isin(val_months)].copy()
    if fit.empty or val.empty or test.empty:
        raise RuntimeError("Empty fit/val/test split.")

    features = infer_features(candidates)
    features = [f for f in features if f not in {"beats_fixed_rule", "is_oracle_hard_best", "is_fixed_candidate"} and not f.startswith("_fixed")]
    models = fit_models(fit, features, int(args.seed), int(args.n_estimators), int(args.n_jobs))
    val_pred = predict_models(models, val)
    grid = validation_grid(val_pred, float(args.fixed_delta), int(args.min_val_trades))
    best_config = {
        key: float(grid.iloc[0][key])
        for key in ["fixed_delta", "delta_floor", "beat_weight", "best_weight", "delta_bias", "margin"]
    }

    final_models = fit_models(train, features, int(args.seed), int(args.n_estimators), int(args.n_jobs))
    test_pred = predict_models(final_models, test)
    selected = select_excess(test_pred, best_config, "excess_vs_fixed_selector")
    excess_trades = candidate_trades_from_selection(selected, "rule", "excess_vs_fixed_selector")

    fixed_070 = fixed_delta_policy(test, float(args.fixed_delta), "rule", "fixed_delta_0.70_hard")
    oracle_hard = oracle_policy(test, "rule_pnl_dollars", "rule", "oracle_best_delta_hard")
    oracle_exit = oracle_policy(test, "oracle_pnl_dollars", "oracle", "oracle_best_delta_oracle_exit")

    outputs = {
        "fixed_delta_0.70_hard": fixed_070,
        "excess_vs_fixed_selector": excess_trades,
        "oracle_best_delta_hard": oracle_hard,
        "oracle_best_delta_oracle_exit": oracle_exit,
    }
    for name, trades in outputs.items():
        trades.to_csv(output_dir / f"{name}_trades.csv", index=False)
    selected.to_csv(output_dir / "selected_candidates.csv", index=False)
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
