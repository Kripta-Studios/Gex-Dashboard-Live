from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor


def month_range(start: str, end: str) -> list[str]:
    year = int(str(start)[:4])
    month = int(str(start)[4:6])
    out: list[str] = []
    while True:
        current = f"{year:04d}{month:02d}"
        out.append(current)
        if current == str(end):
            return out
        month += 1
        if month == 13:
            year += 1
            month = 1


def parse_variant(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        path = Path(spec)
        return path.name, path
    name, raw = spec.split("=", 1)
    return name.strip(), Path(raw.strip())


def parse_deploy_config(value: object) -> tuple[float, float]:
    text = str(value)
    threshold = float("nan")
    max_day = float("nan")
    if text.startswith("thr"):
        try:
            threshold = float(text.split("_", 1)[0].replace("thr", ""))
        except ValueError:
            pass
    if "maxday" in text:
        raw = text.split("maxday")[-1]
        max_day = 999.0 if raw == "all" else float(pd.to_numeric(raw, errors="coerce"))
    return threshold, max_day


def load_inputs(variant_specs: list[str]) -> tuple[list[str], pd.DataFrame, dict[tuple[str, str, str], pd.DataFrame]]:
    variants: list[str] = []
    fold_parts: list[pd.DataFrame] = []
    trade_cache: dict[tuple[str, str, str], pd.DataFrame] = {}
    for spec in variant_specs:
        name, path = parse_variant(spec)
        variants.append(name)
        fold_file = path / "fold_configs.csv"
        trade_file = path / "event_option_gate_trades.csv"
        if not fold_file.exists() or not trade_file.exists():
            raise FileNotFoundError(f"Missing fold/trade files for {name}: {path}")
        folds = pd.read_csv(fold_file, dtype={"month": str, "ticker": str})
        folds["variant"] = name
        fold_parts.append(folds)
        trades = pd.read_csv(trade_file, dtype={"test_month": str, "month": str, "date": str, "ticker": str})
        trades["variant"] = name
        trades["ticker"] = trades["ticker"].astype(str).str.upper()
        trades["test_month"] = trades["test_month"].astype(str)
        for (ticker, month), part in trades.groupby(["ticker", "test_month"]):
            trade_cache[(name, str(ticker).upper(), str(month))] = part.copy()
    folds = pd.concat(fold_parts, ignore_index=True)
    folds["ticker"] = folds["ticker"].astype(str).str.upper()
    folds["month"] = folds["month"].astype(str)
    for col in folds.columns:
        if col.startswith(("val_", "test_", "meta_select_")):
            folds[col] = pd.to_numeric(folds[col], errors="coerce")
    parsed = folds["deploy_config"].map(parse_deploy_config)
    folds["deploy_thr"] = [item[0] for item in parsed]
    folds["deploy_maxday"] = [item[1] for item in parsed]
    return variants, folds, trade_cache


def hist_features(rows: pd.DataFrame) -> dict[str, float]:
    if rows.empty:
        return {
            "trades": 0.0,
            "R_sum": 0.0,
            "R_mean": 0.0,
            "R_last": 0.0,
            "R_min": 0.0,
            "R_max": 0.0,
            "pf_mean": 0.0,
            "wr_mean": 0.0,
            "pos_rate": 0.0,
            "min_trades": 0.0,
        }
    returns = pd.to_numeric(rows["test_pnl_return"], errors="coerce").fillna(0.0)
    return {
        "trades": float(pd.to_numeric(rows["test_trades"], errors="coerce").fillna(0.0).sum()),
        "R_sum": float(returns.sum()),
        "R_mean": float(returns.mean()),
        "R_last": float(returns.iloc[-1]),
        "R_min": float(returns.min()),
        "R_max": float(returns.max()),
        "pf_mean": float(
            pd.to_numeric(rows["test_profit_factor"], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .mean()
        ),
        "wr_mean": float(pd.to_numeric(rows["test_win_rate"], errors="coerce").fillna(0.0).mean()),
        "pos_rate": float((returns > 0.0).mean()),
        "min_trades": float(pd.to_numeric(rows["test_trades"], errors="coerce").fillna(0.0).min()),
    }


def build_candidate_frame(folds: pd.DataFrame, windows: list[int]) -> tuple[pd.DataFrame, list[str]]:
    val_cols = [col for col in folds.columns if col.startswith("val_")]
    metric_defaults = {
        "test_trades": np.nan,
        "test_win_rate": np.nan,
        "test_profit_factor": np.nan,
        "test_pnl_return": 0.0,
        "test_avg_return": np.nan,
        "test_max_drawdown": 0.0,
        "test_call_rate": np.nan,
        "test_daily_win_rate": np.nan,
        "test_median_daily_return": np.nan,
        "test_daily_max_drawdown": 0.0,
        "test_top5_share_of_pnl": np.nan,
        "test_min_month_trades": np.nan,
        "test_positive_month_rate": np.nan,
    }
    for col, default in metric_defaults.items():
        if col not in folds.columns:
            folds[col] = default
    rows: list[dict] = []
    ordered = folds.sort_values(["month", "ticker", "variant"], kind="stable").reset_index(drop=True)
    for _, row in ordered.iterrows():
        rec = {
            "ticker": str(row["ticker"]),
            "month": str(row["month"]),
            "variant": str(row["variant"]),
            "deploy_config": row.get("deploy_config", ""),
            "month_num": int(str(row["month"])[4:6]),
            "target_R": float(row.get("test_pnl_return", 0.0) if pd.notna(row.get("test_pnl_return", 0.0)) else 0.0),
            "target_pf": float(
                row.get("test_profit_factor", 0.0)
                if pd.notna(row.get("test_profit_factor", 0.0)) and np.isfinite(float(row.get("test_profit_factor", 0.0)))
                else 0.0
            ),
            "target_trades": float(row.get("test_trades", 0.0) if pd.notna(row.get("test_trades", 0.0)) else 0.0),
        }
        for col in val_cols + ["deploy_thr", "deploy_maxday"]:
            rec[col] = row.get(col, np.nan)
        for window in windows:
            prior = ordered[
                (ordered["variant"].astype(str) == str(row["variant"]))
                & (ordered["ticker"].astype(str) == str(row["ticker"]))
                & (ordered["month"].astype(str) < str(row["month"]))
            ].tail(window)
            for key, value in hist_features(prior).items():
                rec[f"h{window}_{key}"] = value
            prior_pool = ordered[
                (ordered["variant"].astype(str) == str(row["variant"]))
                & (ordered["month"].astype(str) < str(row["month"]))
            ].tail(window * 3)
            for key, value in hist_features(prior_pool).items():
                rec[f"h{window}_pool_{key}"] = value
        rows.append(rec)
    frame = pd.DataFrame(rows)
    frame = pd.get_dummies(frame, columns=["ticker", "variant"], dtype=float)
    blocked = {"month", "deploy_config", "target_R", "target_pf", "target_trades"}
    feature_cols = [col for col in frame.columns if col not in blocked and not col.startswith("target_")]
    frame[feature_cols] = frame[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return frame, feature_cols


def trade_metrics(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty:
        return {"trades": 0, "wr": float("nan"), "pf": float("nan"), "R": 0.0, "min_month": 0, "pos_month_rate": float("nan")}
    returns = trades["realized_return"].astype(float)
    wins = returns[returns > 0.0].sum()
    losses = -returns[returns < 0.0].sum()
    pf = float(wins / losses) if losses > 0.0 else (float("inf") if wins > 0.0 else 0.0)
    monthly = trades.groupby(["ticker", "test_month"])["realized_return"].agg(["count", "sum"])
    return {
        "trades": int(len(trades)),
        "wr": float((returns > 0.0).mean()),
        "pf": pf,
        "R": float(returns.sum()),
        "min_month": int(monthly["count"].min()) if len(monthly) else 0,
        "pos_month_rate": float((monthly["sum"] > 0.0).mean()) if len(monthly) else float("nan"),
    }


def make_model(kind: str, target: str, args: argparse.Namespace):
    if kind == "lgbm":
        common = {
            "n_estimators": int(args.n_estimators),
            "learning_rate": float(args.learning_rate),
            "num_leaves": int(args.num_leaves),
            "min_child_samples": int(args.min_child_samples),
            "subsample": float(args.subsample),
            "colsample_bytree": float(args.colsample_bytree),
            "reg_lambda": float(args.reg_lambda),
            "n_jobs": int(args.lgb_jobs),
            "verbosity": -1,
            "random_state": int(args.seed),
        }
        if target == "cls":
            return lgb.LGBMClassifier(objective="binary", **common)
        return lgb.LGBMRegressor(objective=str(args.objective), **common)
    if kind == "rf":
        return RandomForestRegressor(
            n_estimators=int(args.rf_trees),
            max_depth=int(args.tree_max_depth),
            min_samples_leaf=int(args.tree_min_leaf),
            random_state=int(args.seed),
            n_jobs=int(args.lgb_jobs),
        )
    if kind == "et":
        return ExtraTreesRegressor(
            n_estimators=int(args.rf_trees),
            max_depth=int(args.tree_max_depth),
            min_samples_leaf=int(args.tree_min_leaf),
            random_state=int(args.seed),
            n_jobs=int(args.lgb_jobs),
        )
    raise ValueError(kind)


def recover_variant(row: pd.Series, variants: list[str]) -> str:
    for variant in variants:
        if float(row.get(f"variant_{variant}", 0.0)) == 1.0:
            return variant
    raise RuntimeError("Could not recover variant from selected row.")


def evaluate_config(
    candidates: pd.DataFrame,
    feature_cols: list[str],
    variants: list[str],
    trade_cache: dict[tuple[str, str, str], pd.DataFrame],
    args: argparse.Namespace,
    *,
    start_month: str,
    end_month: str,
    model_kind: str,
    target: str,
    val_min_trades: int,
    val_min_month_trades: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]:
    selected_rows: list[dict] = []
    trade_parts: list[pd.DataFrame] = []
    tickers = [str(t).upper() for t in args.tickers]
    for month in month_range(start_month, end_month):
        train = candidates[candidates["month"].astype(str) < str(month)].copy()
        if int(val_min_trades) > 0 and "val_trades" in train.columns:
            train = train[pd.to_numeric(train["val_trades"], errors="coerce").fillna(0.0) >= int(val_min_trades)]
        if int(val_min_month_trades) > 0 and "val_min_month_trades" in train.columns:
            train = train[pd.to_numeric(train["val_min_month_trades"], errors="coerce").fillna(0.0) >= int(val_min_month_trades)]
        if train["month"].nunique() < int(args.min_train_months) or len(train) < int(args.min_train_rows):
            continue
        y = train["target_R"].clip(-float(args.clip_target), float(args.clip_target))
        if target == "cls":
            y = (train["target_R"].astype(float) > 0.0).astype(int)
            if y.nunique() < 2:
                continue
        model = make_model(model_kind, target, args)
        model.fit(train[feature_cols], y)
        score = candidates[candidates["month"].astype(str) == str(month)].copy()
        if int(val_min_trades) > 0 and "val_trades" in score.columns:
            score = score[pd.to_numeric(score["val_trades"], errors="coerce").fillna(0.0) >= int(val_min_trades)]
        if int(val_min_month_trades) > 0 and "val_min_month_trades" in score.columns:
            score = score[pd.to_numeric(score["val_min_month_trades"], errors="coerce").fillna(0.0) >= int(val_min_month_trades)]
        if score.empty:
            continue
        if target == "cls" and hasattr(model, "predict_proba"):
            score["meta_pred"] = model.predict_proba(score[feature_cols])[:, 1]
        else:
            score["meta_pred"] = model.predict(score[feature_cols])
        for ticker in tickers:
            ticker_col = f"ticker_{ticker}"
            if ticker_col not in score.columns:
                continue
            sub = score[score[ticker_col].astype(float) == 1.0].copy()
            if sub.empty:
                continue
            sort_cols = ["meta_pred"]
            ascending = [False]
            for col in ("h6_R_sum", "val_pnl_return", "h3_R_sum"):
                if col in sub.columns:
                    sort_cols.append(col)
                    ascending.append(False)
            best = sub.sort_values(sort_cols, ascending=ascending).iloc[0]
            variant = recover_variant(best, variants)
            selected_rows.append(
                {
                    "ticker": ticker,
                    "month": str(month),
                    "variant": variant,
                    "meta_pred": float(best["meta_pred"]),
                    "target_R": float(best["target_R"]),
                    "target_trades": float(best["target_trades"]),
                    "deploy_config": best.get("deploy_config", ""),
                }
            )
            trades = trade_cache.get((variant, ticker, str(month)))
            if trades is not None and not trades.empty:
                part = trades.copy()
                part["selected_variant"] = variant
                part["meta_pred"] = float(best["meta_pred"])
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
    pf_min = min(float(per_ticker[ticker]["pf"]) if math.isfinite(float(per_ticker[ticker]["pf"])) else 99.0 for ticker in per_ticker)
    min_month = min(int(per_ticker[ticker]["min_month"]) for ticker in per_ticker)
    pos_min = min(
        float(per_ticker[ticker]["pos_month_rate"]) if math.isfinite(float(per_ticker[ticker]["pos_month_rate"])) else 0.0
        for ticker in per_ticker
    )
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


def summarize_metrics(overall: dict, per_ticker: dict, monthly: pd.DataFrame) -> dict:
    return {
        "overall": overall,
        "per_ticker": per_ticker,
        "pf_min": min(float(value["pf"]) if math.isfinite(float(value["pf"])) else 99.0 for value in per_ticker.values()),
        "wr_min": min(float(value["wr"]) if math.isfinite(float(value["wr"])) else 0.0 for value in per_ticker.values()),
        "min_month_ticker": min(int(value["min_month"]) for value in per_ticker.values()),
        "pos_min": min(
            float(value["pos_month_rate"]) if math.isfinite(float(value["pos_month_rate"])) else 0.0
            for value in per_ticker.values()
        ),
        "losing_ticker_months": int((monthly["R"].astype(float) < 0.0).sum()) if not monthly.empty else 99,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Rolling causal meta-router over precomputed event-option variants.")
    parser.add_argument("--variant", action="append", required=True, help="NAME=variant_result_dir. Repeatable.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--selection-start-month", default="202507")
    parser.add_argument("--selection-end-month", default="202512")
    parser.add_argument("--test-start-month", default="202601")
    parser.add_argument("--test-end-month", default="202606")
    parser.add_argument("--windows", nargs="+", type=int, default=[1, 2, 3, 6, 12])
    parser.add_argument("--model-kinds", nargs="+", default=["lgbm", "rf", "et"])
    parser.add_argument("--targets", nargs="+", default=["R", "cls"])
    parser.add_argument("--val-min-trades-grid", nargs="+", type=int, default=[0, 20, 40])
    parser.add_argument("--val-min-month-trades-grid", nargs="+", type=int, default=[0, 8, 12])
    parser.add_argument("--min-train-months", type=int, default=4)
    parser.add_argument("--min-train-rows", type=int, default=40)
    parser.add_argument("--clip-target", type=float, default=5.0)
    parser.add_argument("--objective", default="regression_l1")
    parser.add_argument("--n-estimators", type=int, default=140)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=7)
    parser.add_argument("--min-child-samples", type=int, default=12)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.75)
    parser.add_argument("--reg-lambda", type=float, default=8.0)
    parser.add_argument("--rf-trees", type=int, default=300)
    parser.add_argument("--tree-max-depth", type=int, default=4)
    parser.add_argument("--tree-min-leaf", type=int, default=6)
    parser.add_argument("--lgb-jobs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260623)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--gate-min-month-trades", type=int, default=12)
    parser.add_argument("--gate-min-pf", type=float, default=1.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    variants, folds, trade_cache = load_inputs(args.variant)
    candidates, feature_cols = build_candidate_frame(folds, [int(w) for w in args.windows])
    candidates.to_parquet(output_dir / "candidate_features.parquet", index=False)
    pd.DataFrame({"feature": feature_cols}).to_csv(output_dir / "feature_cols.csv", index=False)

    configs: list[dict] = []
    for model_kind in args.model_kinds:
        for target in args.targets:
            if str(target) == "cls" and str(model_kind) != "lgbm":
                continue
            for val_min_trades in args.val_min_trades_grid:
                for val_min_month in args.val_min_month_trades_grid:
                    configs.append(
                        {
                            "model_kind": str(model_kind),
                            "target": str(target),
                            "val_min_trades": int(val_min_trades),
                            "val_min_month_trades": int(val_min_month),
                        }
                    )

    ranked_rows: list[dict] = []
    selection_payloads: dict[int, tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]] = {}
    for idx, cfg in enumerate(configs):
        payload = evaluate_config(
            candidates,
            feature_cols,
            variants,
            trade_cache,
            args,
            start_month=str(args.selection_start_month),
            end_month=str(args.selection_end_month),
            **cfg,
        )
        trades, selected, monthly, overall, per_ticker = payload
        selection_payloads[idx] = payload
        summary = summarize_metrics(overall, per_ticker, monthly)
        ranked_rows.append(
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
    ranked = pd.DataFrame(ranked_rows).sort_values("score_selection", ascending=False)
    ranked.to_csv(output_dir / "config_rank_selection.csv", index=False)

    test_rows: list[dict] = []
    for _, ranked_row in ranked.head(int(args.top_k)).iterrows():
        cfg = {
            "model_kind": str(ranked_row["model_kind"]),
            "target": str(ranked_row["target"]),
            "val_min_trades": int(ranked_row["val_min_trades"]),
            "val_min_month_trades": int(ranked_row["val_min_month_trades"]),
        }
        payload = evaluate_config(
            candidates,
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
        label = f"{cfg['model_kind']}_{cfg['target']}_vt{cfg['val_min_trades']}_vmm{cfg['val_min_month_trades']}"
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
    if not test.empty:
        cols = [
            "idx",
            "score_selection",
            "model_kind",
            "target",
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
