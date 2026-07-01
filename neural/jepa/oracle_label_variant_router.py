from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier

from rolling_variant_meta_router import (
    build_candidate_frame,
    load_inputs,
    month_range,
    recover_variant,
    summarize_metrics,
    trade_metrics,
)


def build_oracle_labels(
    variants: list[str],
    trade_cache: dict[tuple[str, str, str], pd.DataFrame],
    tickers: list[str],
    months: list[str],
    min_trades: int,
) -> pd.DataFrame:
    rows: list[dict] = []
    for ticker in tickers:
        for month in months:
            best: dict | None = None
            for variant in variants:
                trades = trade_cache.get((variant, ticker, month))
                if trades is None or len(trades) < int(min_trades):
                    continue
                returns = trades["realized_return"].astype(float)
                wins = returns[returns > 0.0].sum()
                losses = -returns[returns < 0.0].sum()
                pf = float(wins / losses) if losses > 0.0 else (float("inf") if wins > 0.0 else 0.0)
                row = {
                    "ticker": ticker,
                    "month": month,
                    "variant": variant,
                    "oracle_R": float(returns.sum()),
                    "oracle_pf": pf,
                    "oracle_wr": float((returns > 0.0).mean()),
                    "oracle_trades": int(len(trades)),
                }
                if best is None or row["oracle_R"] > float(best["oracle_R"]):
                    best = row
            if best is not None:
                rows.append(best)
    return pd.DataFrame(rows)


def make_model(kind: str, args: argparse.Namespace):
    if kind == "lgbm":
        return lgb.LGBMClassifier(
            objective="multiclass",
            n_estimators=int(args.n_estimators),
            learning_rate=float(args.learning_rate),
            num_leaves=int(args.num_leaves),
            min_child_samples=int(args.min_child_samples),
            subsample=float(args.subsample),
            colsample_bytree=float(args.colsample_bytree),
            reg_lambda=float(args.reg_lambda),
            n_jobs=int(args.jobs),
            verbosity=-1,
            random_state=int(args.seed),
        )
    if kind == "rf":
        return RandomForestClassifier(
            n_estimators=int(args.rf_trees),
            max_depth=int(args.tree_max_depth),
            min_samples_leaf=int(args.tree_min_leaf),
            class_weight="balanced_subsample",
            random_state=int(args.seed),
            n_jobs=int(args.jobs),
        )
    if kind == "et":
        return ExtraTreesClassifier(
            n_estimators=int(args.rf_trees),
            max_depth=int(args.tree_max_depth),
            min_samples_leaf=int(args.tree_min_leaf),
            class_weight="balanced",
            random_state=int(args.seed),
            n_jobs=int(args.jobs),
        )
    raise ValueError(kind)


def evaluate(
    candidates: pd.DataFrame,
    labels: pd.DataFrame,
    feature_cols: list[str],
    variants: list[str],
    trade_cache: dict[tuple[str, str, str], pd.DataFrame],
    args: argparse.Namespace,
    *,
    start_month: str,
    end_month: str,
    model_kind: str,
    val_min_trades: int,
    val_min_month_trades: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]:
    class_to_variant = {idx: variant for idx, variant in enumerate(variants)}
    variant_to_class = {variant: idx for idx, variant in class_to_variant.items()}
    tickers = [str(t).upper() for t in args.tickers]
    label_map = labels.set_index(["ticker", "month"])["variant"].to_dict()
    selected_rows: list[dict] = []
    trade_parts: list[pd.DataFrame] = []
    for month in month_range(start_month, end_month):
        train = candidates[candidates["month"].astype(str) < str(month)].copy()
        train["_label_variant"] = [
            label_map.get((ticker, str(row_month)))
            for ticker, row_month in zip(
                train[[f"ticker_{ticker}" for ticker in tickers if f"ticker_{ticker}" in train.columns]].idxmax(axis=1).str.replace("ticker_", "", regex=False),
                train["month"].astype(str),
            )
        ]
        train = train[train["_label_variant"].isin(variant_to_class)].copy()
        if int(val_min_trades) > 0 and "val_trades" in train.columns:
            train = train[pd.to_numeric(train["val_trades"], errors="coerce").fillna(0.0) >= int(val_min_trades)]
        if int(val_min_month_trades) > 0 and "val_min_month_trades" in train.columns:
            train = train[pd.to_numeric(train["val_min_month_trades"], errors="coerce").fillna(0.0) >= int(val_min_month_trades)]
        if train["month"].nunique() < int(args.min_train_months) or len(train) < int(args.min_train_rows):
            continue
        y = train["_label_variant"].map(variant_to_class).astype(int)
        if y.nunique() < 2:
            continue
        model = make_model(model_kind, args)
        model.fit(train[feature_cols], y)
        score = candidates[candidates["month"].astype(str) == str(month)].copy()
        if int(val_min_trades) > 0 and "val_trades" in score.columns:
            score = score[pd.to_numeric(score["val_trades"], errors="coerce").fillna(0.0) >= int(val_min_trades)]
        if int(val_min_month_trades) > 0 and "val_min_month_trades" in score.columns:
            score = score[pd.to_numeric(score["val_min_month_trades"], errors="coerce").fillna(0.0) >= int(val_min_month_trades)]
        if score.empty:
            continue
        proba = model.predict_proba(score[feature_cols])
        classes = [int(c) for c in model.classes_]
        for class_idx, variant in class_to_variant.items():
            if class_idx in classes:
                score[f"p_{variant}"] = proba[:, classes.index(class_idx)]
            else:
                score[f"p_{variant}"] = 0.0
        for ticker in tickers:
            ticker_col = f"ticker_{ticker}"
            if ticker_col not in score.columns:
                continue
            sub = score[score[ticker_col].astype(float) == 1.0].copy()
            if sub.empty:
                continue
            sub["_row_variant"] = [recover_variant(row, variants) for _, row in sub.iterrows()]
            sub["_pred"] = [float(row.get(f"p_{row['_row_variant']}", 0.0)) for _, row in sub.iterrows()]
            for col in ("h6_R_sum", "val_pnl_return", "h3_R_sum"):
                if col not in sub.columns:
                    sub[col] = 0.0
            best = sub.sort_values(["_pred", "h6_R_sum", "val_pnl_return"], ascending=[False, False, False]).iloc[0]
            variant = str(best["_row_variant"])
            selected_rows.append(
                {
                    "ticker": ticker,
                    "month": str(month),
                    "variant": variant,
                    "pred_prob": float(best["_pred"]),
                    "oracle_label": label_map.get((ticker, str(month))),
                    "deploy_config": best.get("deploy_config", ""),
                }
            )
            trades = trade_cache.get((variant, ticker, str(month)))
            if trades is not None and not trades.empty:
                part = trades.copy()
                part["selected_variant"] = variant
                part["pred_prob"] = float(best["_pred"])
                trade_parts.append(part)
    selected = pd.DataFrame(selected_rows)
    trades = pd.concat(trade_parts, ignore_index=True) if trade_parts else pd.DataFrame()
    monthly_rows: list[dict] = []
    if not trades.empty:
        for (ticker, month), part in trades.groupby(["ticker", "test_month"]):
            monthly_rows.append(
                {
                    "ticker": str(ticker),
                    "month": str(month),
                    "trades": int(len(part)),
                    "R": float(part["realized_return"].astype(float).sum()),
                    "variant": str(part["selected_variant"].mode().iat[0]),
                }
            )
    monthly = pd.DataFrame(monthly_rows)
    overall = trade_metrics(trades)
    per_ticker = {
        ticker: trade_metrics(trades[trades["ticker"].astype(str).str.upper() == ticker]) if not trades.empty else trade_metrics(pd.DataFrame())
        for ticker in tickers
    }
    return trades, selected, monthly, overall, per_ticker


def score_selection(overall: dict, per_ticker: dict, monthly: pd.DataFrame, args: argparse.Namespace) -> float:
    pf_min = min(float(v["pf"]) if math.isfinite(float(v["pf"])) else 99.0 for v in per_ticker.values())
    min_month = min(int(v["min_month"]) for v in per_ticker.values())
    pos_min = min(float(v["pos_month_rate"]) if math.isfinite(float(v["pos_month_rate"])) else 0.0 for v in per_ticker.values())
    losing = int((monthly["R"].astype(float) < 0.0).sum()) if not monthly.empty else 99
    score = (
        2.0 * min(float(overall["pf"]) if math.isfinite(float(overall["pf"])) else 3.0, 3.0)
        + 1.5 * pf_min
        + 0.10 * float(overall["R"])
        + pos_min
        - 0.30 * losing
        + 0.02 * min_month
    )
    if min_month < int(args.gate_min_month_trades) or pf_min < float(args.gate_min_pf) or float(overall["R"]) <= 0.0:
        score -= 100.0
    return float(score)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rolling classifier that distills the monthly variant oracle without using the test month.")
    parser.add_argument("--variant", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--selection-start-month", default="202401")
    parser.add_argument("--selection-end-month", default="202512")
    parser.add_argument("--test-start-month", default="202601")
    parser.add_argument("--test-end-month", default="202606")
    parser.add_argument("--windows", nargs="+", type=int, default=[1, 2, 3, 6, 12])
    parser.add_argument("--model-kinds", nargs="+", default=["lgbm", "rf", "et"])
    parser.add_argument("--val-min-trades-grid", nargs="+", type=int, default=[0, 20, 40])
    parser.add_argument("--val-min-month-trades-grid", nargs="+", type=int, default=[0, 8, 12])
    parser.add_argument("--oracle-min-trades", type=int, default=18)
    parser.add_argument("--min-train-months", type=int, default=6)
    parser.add_argument("--min-train-rows", type=int, default=80)
    parser.add_argument("--n-estimators", type=int, default=160)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=7)
    parser.add_argument("--min-child-samples", type=int, default=12)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.75)
    parser.add_argument("--reg-lambda", type=float, default=8.0)
    parser.add_argument("--rf-trees", type=int, default=400)
    parser.add_argument("--tree-max-depth", type=int, default=5)
    parser.add_argument("--tree-min-leaf", type=int, default=4)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260623)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--gate-min-month-trades", type=int, default=12)
    parser.add_argument("--gate-min-pf", type=float, default=1.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    variants, folds, trade_cache = load_inputs(args.variant)
    candidates, feature_cols = build_candidate_frame(folds, [int(w) for w in args.windows])
    all_months = sorted(folds["month"].astype(str).unique())
    labels = build_oracle_labels(
        variants,
        trade_cache,
        [str(t).upper() for t in args.tickers],
        all_months,
        int(args.oracle_min_trades),
    )
    labels.to_csv(output_dir / "oracle_labels.csv", index=False)
    candidates.to_parquet(output_dir / "candidate_features.parquet", index=False)
    rows: list[dict] = []
    payloads: dict[int, tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]] = {}
    configs = [
        {"model_kind": kind, "val_min_trades": int(vt), "val_min_month_trades": int(vmm)}
        for kind in args.model_kinds
        for vt in args.val_min_trades_grid
        for vmm in args.val_min_month_trades_grid
    ]
    for idx, cfg in enumerate(configs):
        payload = evaluate(
            candidates,
            labels,
            feature_cols,
            variants,
            trade_cache,
            args,
            start_month=str(args.selection_start_month),
            end_month=str(args.selection_end_month),
            **cfg,
        )
        payloads[idx] = payload
        trades, selected, monthly, overall, per_ticker = payload
        summary = summarize_metrics(overall, per_ticker, monthly)
        rows.append(
            {
                "idx": idx,
                "score_selection": score_selection(overall, per_ticker, monthly, args),
                **cfg,
                **{f"{key}_selection": value for key, value in overall.items()},
                "pf_min_selection": summary["pf_min"],
                "wr_min_selection": summary["wr_min"],
                "min_month_ticker_selection": summary["min_month_ticker"],
                "pos_min_selection": summary["pos_min"],
                "losing_ticker_months_selection": summary["losing_ticker_months"],
            }
        )
    ranked = pd.DataFrame(rows).sort_values("score_selection", ascending=False)
    ranked.to_csv(output_dir / "config_rank_selection.csv", index=False)
    test_rows: list[dict] = []
    for _, ranked_row in ranked.head(int(args.top_k)).iterrows():
        cfg = {
            "model_kind": str(ranked_row["model_kind"]),
            "val_min_trades": int(ranked_row["val_min_trades"]),
            "val_min_month_trades": int(ranked_row["val_min_month_trades"]),
        }
        payload = evaluate(
            candidates,
            labels,
            feature_cols,
            variants,
            trade_cache,
            args,
            start_month=str(args.test_start_month),
            end_month=str(args.test_end_month),
            **cfg,
        )
        trades, selected, monthly, overall, per_ticker = payload
        summary = summarize_metrics(overall, per_ticker, monthly)
        label = f"{cfg['model_kind']}_vt{cfg['val_min_trades']}_vmm{cfg['val_min_month_trades']}"
        subdir = output_dir / label
        subdir.mkdir(parents=True, exist_ok=True)
        trades.to_csv(subdir / "selected_variant_trades.csv", index=False)
        selected.to_csv(subdir / "selected_folds.csv", index=False)
        monthly.to_csv(subdir / "monthly.csv", index=False)
        (subdir / "metrics.json").write_text(
            json.dumps({"overall": overall, "per_ticker": per_ticker, "selection_row": ranked_row.to_dict()}, indent=2, allow_nan=True),
            encoding="utf-8",
        )
        test_rows.append(
            {
                **ranked_row.to_dict(),
                **{f"{key}_test": value for key, value in overall.items()},
                "pf_min_test": summary["pf_min"],
                "wr_min_test": summary["wr_min"],
                "min_month_ticker_test": summary["min_month_ticker"],
                "pos_min_test": summary["pos_min"],
                "losing_ticker_months_test": summary["losing_ticker_months"],
                "artifact_dir": str(subdir),
            }
        )
    test = pd.DataFrame(test_rows)
    test.to_csv(output_dir / "top_selection_then_test.csv", index=False)
    cols = [
        "idx",
        "score_selection",
        "model_kind",
        "val_min_trades",
        "val_min_month_trades",
        "pf_selection",
        "R_selection",
        "pf_min_selection",
        "min_month_ticker_selection",
        "pos_min_selection",
        "losing_ticker_months_selection",
        "pf_test",
        "wr_test",
        "R_test",
        "pf_min_test",
        "wr_min_test",
        "min_month_ticker_test",
        "pos_min_test",
        "losing_ticker_months_test",
        "artifact_dir",
    ]
    print(test[[c for c in cols if c in test.columns]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
