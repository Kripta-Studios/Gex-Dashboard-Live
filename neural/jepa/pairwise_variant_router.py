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


def add_ids(frame: pd.DataFrame, variants: list[str], tickers: list[str]) -> pd.DataFrame:
    out = frame.copy()
    out["_variant"] = [recover_variant(row, variants) for _, row in out.iterrows()]
    ticker_cols = [f"ticker_{ticker}" for ticker in tickers if f"ticker_{ticker}" in out.columns]
    if not ticker_cols:
        raise RuntimeError("No ticker one-hot columns found in candidate frame.")
    out["_ticker"] = out[ticker_cols].idxmax(axis=1).str.replace("ticker_", "", regex=False)
    return out


def make_pair_feature_cols(feature_cols: list[str], pair_feature_mode: str) -> list[str]:
    diff_cols = [f"diff_{col}" for col in feature_cols]
    if str(pair_feature_mode) == "diff":
        return diff_cols
    if str(pair_feature_mode) == "diff_abs":
        return diff_cols + [f"a_{col}" for col in feature_cols] + [f"b_{col}" for col in feature_cols]
    raise ValueError(f"Unsupported pair feature mode: {pair_feature_mode}")


def make_pair_feature_record(row_a: pd.Series, row_b: pd.Series, feature_cols: list[str], pair_feature_mode: str) -> dict[str, float]:
    rec: dict[str, float] = {}
    for src in feature_cols:
        a_value = float(row_a.get(src, 0.0))
        b_value = float(row_b.get(src, 0.0))
        rec[f"diff_{src}"] = a_value - b_value
        if str(pair_feature_mode) == "diff_abs":
            rec[f"a_{src}"] = a_value
            rec[f"b_{src}"] = b_value
    return rec


def build_pair_rows(
    candidates: pd.DataFrame,
    feature_cols: list[str],
    variants: list[str],
    *,
    pair_feature_mode: str,
    max_abs_return: float,
    min_abs_edge: float,
    min_trades: int,
) -> tuple[pd.DataFrame, list[str]]:
    rows: list[dict] = []
    pair_feature_cols = make_pair_feature_cols(feature_cols, pair_feature_mode)
    grouped = candidates.groupby(["_ticker", "month"], sort=True)
    for (ticker, month), group in grouped:
        by_variant = {str(row["_variant"]): row for _, row in group.iterrows()}
        for i, variant_a in enumerate(variants):
            row_a = by_variant.get(variant_a)
            if row_a is None:
                continue
            for variant_b in variants[i + 1 :]:
                row_b = by_variant.get(variant_b)
                if row_b is None:
                    continue
                trades_a = float(row_a.get("target_trades", 0.0))
                trades_b = float(row_b.get("target_trades", 0.0))
                if trades_a < int(min_trades) and trades_b < int(min_trades):
                    continue
                ret_a = float(np.clip(row_a.get("target_R", 0.0), -max_abs_return, max_abs_return))
                ret_b = float(np.clip(row_b.get("target_R", 0.0), -max_abs_return, max_abs_return))
                edge = ret_a - ret_b
                if abs(edge) < float(min_abs_edge):
                    continue
                rec = {
                    "_ticker": str(ticker),
                    "month": str(month),
                    "variant_a": variant_a,
                    "variant_b": variant_b,
                    "y_a_wins": int(edge > 0.0),
                    "edge": float(edge),
                    "target_R_a": float(row_a.get("target_R", 0.0)),
                    "target_R_b": float(row_b.get("target_R", 0.0)),
                    "target_trades_a": trades_a,
                    "target_trades_b": trades_b,
                }
                rec.update(make_pair_feature_record(row_a, row_b, feature_cols, pair_feature_mode))
                rows.append(rec)
    pairs = pd.DataFrame(rows)
    if not pairs.empty:
        pairs[pair_feature_cols] = pairs[pair_feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return pairs, pair_feature_cols


def make_model(kind: str, args: argparse.Namespace):
    if kind == "lgbm":
        return lgb.LGBMClassifier(
            objective="binary",
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
    pairs: pd.DataFrame,
    feature_cols: list[str],
    pair_feature_cols: list[str],
    variants: list[str],
    trade_cache: dict[tuple[str, str, str], pd.DataFrame],
    args: argparse.Namespace,
    *,
    pair_feature_mode: str,
    start_month: str,
    end_month: str,
    model_kind: str,
    vote_mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]:
    selected_rows: list[dict] = []
    trade_parts: list[pd.DataFrame] = []
    tickers = [str(t).upper() for t in args.tickers]
    for month in month_range(start_month, end_month):
        train = pairs[pairs["month"].astype(str) < str(month)].copy()
        if train["month"].nunique() < int(args.min_train_months) or len(train) < int(args.min_train_pairs):
            continue
        y = train["y_a_wins"].astype(int)
        if y.nunique() < 2:
            continue
        model = make_model(model_kind, args)
        model.fit(train[pair_feature_cols], y)
        month_candidates = candidates[candidates["month"].astype(str) == str(month)].copy()
        for ticker in tickers:
            group = month_candidates[month_candidates["_ticker"].astype(str) == ticker].copy()
            if group.empty:
                continue
            by_variant = {str(row["_variant"]): row for _, row in group.iterrows()}
            scores = {variant: 0.0 for variant in variants}
            comparisons = 0
            for i, variant_a in enumerate(variants):
                row_a = by_variant.get(variant_a)
                if row_a is None:
                    continue
                for variant_b in variants[i + 1 :]:
                    row_b = by_variant.get(variant_b)
                    if row_b is None:
                        continue
                    rec = make_pair_feature_record(row_a, row_b, feature_cols, pair_feature_mode)
                    x = pd.DataFrame([rec], columns=pair_feature_cols).replace([np.inf, -np.inf], np.nan).fillna(0.0)
                    prob_a = float(model.predict_proba(x)[0, 1])
                    if str(vote_mode) == "hard":
                        if prob_a >= 0.5:
                            scores[variant_a] += 1.0
                        else:
                            scores[variant_b] += 1.0
                    else:
                        scores[variant_a] += prob_a
                        scores[variant_b] += 1.0 - prob_a
                    comparisons += 1
            if comparisons == 0:
                continue
            # Stable tie-breaker: score, then recent six-month return, then validation return.
            scored_rows = []
            for variant, score in scores.items():
                row = by_variant.get(variant)
                if row is None:
                    continue
                scored_rows.append(
                    {
                        "variant": variant,
                        "pair_score": float(score),
                        "h6_R_sum": float(row.get("h6_R_sum", 0.0)),
                        "val_pnl_return": float(row.get("val_pnl_return", 0.0)),
                        "deploy_config": row.get("deploy_config", ""),
                    }
                )
            best = pd.DataFrame(scored_rows).sort_values(
                ["pair_score", "h6_R_sum", "val_pnl_return"], ascending=[False, False, False]
            ).iloc[0]
            variant = str(best["variant"])
            selected_rows.append(
                {
                    "ticker": ticker,
                    "month": str(month),
                    "variant": variant,
                    "pair_score": float(best["pair_score"]),
                    "deploy_config": best.get("deploy_config", ""),
                }
            )
            trades = trade_cache.get((variant, ticker, str(month)))
            if trades is not None and not trades.empty:
                part = trades.copy()
                part["selected_variant"] = variant
                part["pair_score"] = float(best["pair_score"])
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
    parser = argparse.ArgumentParser(description="Rolling pairwise/listwise router over precomputed event-option variants.")
    parser.add_argument("--variant", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--selection-start-month", default="202401")
    parser.add_argument("--selection-end-month", default="202512")
    parser.add_argument("--test-start-month", default="202601")
    parser.add_argument("--test-end-month", default="202606")
    parser.add_argument("--windows", nargs="+", type=int, default=[1, 2, 3, 6, 12])
    parser.add_argument("--model-kinds", nargs="+", default=["lgbm", "rf", "et"])
    parser.add_argument("--vote-modes", nargs="+", default=["soft", "hard"])
    parser.add_argument("--pair-feature-modes", nargs="+", default=["diff"], choices=["diff", "diff_abs"])
    parser.add_argument("--pair-min-trades-grid", nargs="+", type=int, default=[0, 12, 18])
    parser.add_argument("--pair-min-edge-grid", nargs="+", type=float, default=[0.0, 0.25, 0.50])
    parser.add_argument("--min-train-months", type=int, default=6)
    parser.add_argument("--min-train-pairs", type=int, default=80)
    parser.add_argument("--max-abs-return", type=float, default=6.0)
    parser.add_argument("--n-estimators", type=int, default=180)
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
    tickers = [str(t).upper() for t in args.tickers]
    candidates, feature_cols = build_candidate_frame(folds, [int(w) for w in args.windows])
    candidates = add_ids(candidates, variants, tickers)
    candidates.to_parquet(output_dir / "candidate_features.parquet", index=False)

    configs = [
        {
            "model_kind": kind,
            "vote_mode": vote,
            "pair_feature_mode": str(pair_feature_mode),
            "min_trades": int(min_trades),
            "min_abs_edge": float(min_edge),
        }
        for kind in args.model_kinds
        for vote in args.vote_modes
        for pair_feature_mode in args.pair_feature_modes
        for min_trades in args.pair_min_trades_grid
        for min_edge in args.pair_min_edge_grid
    ]
    rows: list[dict] = []
    pair_cache: dict[tuple[str, int, float], tuple[pd.DataFrame, list[str]]] = {}
    for idx, cfg in enumerate(configs):
        pair_key = (str(cfg["pair_feature_mode"]), int(cfg["min_trades"]), float(cfg["min_abs_edge"]))
        if pair_key not in pair_cache:
            pair_cache[pair_key] = build_pair_rows(
                candidates,
                feature_cols,
                variants,
                pair_feature_mode=str(cfg["pair_feature_mode"]),
                max_abs_return=float(args.max_abs_return),
                min_abs_edge=float(cfg["min_abs_edge"]),
                min_trades=int(cfg["min_trades"]),
            )
        pairs, pair_feature_cols = pair_cache[pair_key]
        if pairs.empty:
            continue
        payload = evaluate(
            candidates,
            pairs,
            feature_cols,
            pair_feature_cols,
            variants,
            trade_cache,
            args,
            pair_feature_mode=str(cfg["pair_feature_mode"]),
            start_month=str(args.selection_start_month),
            end_month=str(args.selection_end_month),
            model_kind=str(cfg["model_kind"]),
            vote_mode=str(cfg["vote_mode"]),
        )
        trades, selected, monthly, overall, per_ticker = payload
        summary = summarize_metrics(overall, per_ticker, monthly)
        rows.append(
            {
                "idx": idx,
                "score_selection": score_selection(overall, per_ticker, monthly, args),
                "pair_rows": int(len(pairs)),
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
        pair_key = (str(ranked_row["pair_feature_mode"]), int(ranked_row["min_trades"]), float(ranked_row["min_abs_edge"]))
        pairs, pair_feature_cols = pair_cache[pair_key]
        payload = evaluate(
            candidates,
            pairs,
            feature_cols,
            pair_feature_cols,
            variants,
            trade_cache,
            args,
            pair_feature_mode=str(ranked_row["pair_feature_mode"]),
            start_month=str(args.test_start_month),
            end_month=str(args.test_end_month),
            model_kind=str(ranked_row["model_kind"]),
            vote_mode=str(ranked_row["vote_mode"]),
        )
        trades, selected, monthly, overall, per_ticker = payload
        summary = summarize_metrics(overall, per_ticker, monthly)
        label = (
            f"{ranked_row['model_kind']}_{ranked_row['vote_mode']}"
            f"_{ranked_row['pair_feature_mode']}"
            f"_mt{int(ranked_row['min_trades'])}_me{str(ranked_row['min_abs_edge']).replace('.', 'p')}"
        )
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
        "vote_mode",
        "pair_feature_mode",
        "min_trades",
        "min_abs_edge",
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
