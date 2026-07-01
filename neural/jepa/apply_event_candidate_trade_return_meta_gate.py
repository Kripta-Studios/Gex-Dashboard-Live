from __future__ import annotations

import argparse
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from apply_event_candidate_trade_meta_gate import (
    enrich_trades,
    flatten,
    load_candidate_trades,
    load_entry_features,
    write_plot,
)
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics, score_metrics


def score_selection(row: dict, args: argparse.Namespace) -> float:
    score = score_metrics(
        row,
        int(args.min_select_trades),
        int(args.min_select_month_trades),
        float(args.min_select_pf),
        float(args.min_select_win_rate),
        float(args.min_call_rate),
        float(args.max_call_rate),
    )
    if score <= -1e17:
        return float(score)
    daily_wr = row.get("daily_win_rate", float("nan"))
    if np.isfinite(float(daily_wr)):
        score += float(args.daily_win_weight) * float(daily_wr)
    top5_share = row.get("top5_share_of_pnl", float("nan"))
    if np.isfinite(float(top5_share)):
        score -= float(args.top5_share_penalty) * max(float(top5_share) - 1.0, 0.0)
    return float(score)


def fit_month_gate(
    trades: pd.DataFrame,
    feature_cols: list[str],
    ticker: str,
    month: str,
    all_months: list[str],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, dict]:
    test = trades[(trades["ticker"].astype(str) == ticker) & (trades["test_month"].astype(str) == str(month))].copy()
    previous = [m for m in all_months if m < str(month)]
    select_n = int(args.select_months)
    if test.empty:
        return test, {"ticker": ticker, "month": str(month), "mode": "NO_TEST_ROWS", "threshold": float("nan"), "test_metrics": metrics(test, [str(month)])}
    if len(previous) <= select_n:
        test["return_meta_mode"] = "NO_HISTORY"
        test["return_meta_threshold"] = float("-inf")
        return test, {"ticker": ticker, "month": str(month), "mode": "NO_HISTORY", "threshold": float("-inf"), "test_metrics": metrics(test, [str(month)])}

    train_months = previous[:-select_n]
    select_months = previous[-select_n:]
    train = trades[(trades["ticker"].astype(str) == ticker) & (trades["test_month"].astype(str).isin(train_months))].copy()
    select = trades[(trades["ticker"].astype(str) == ticker) & (trades["test_month"].astype(str).isin(select_months))].copy()
    if len(train) < int(args.min_train_trades) or len(select) < int(args.min_select_trades):
        test["return_meta_mode"] = "INSUFFICIENT_ROWS"
        test["return_meta_threshold"] = float("-inf")
        return test, {
            "ticker": ticker,
            "month": str(month),
            "mode": "INSUFFICIENT_ROWS",
            "threshold": float("-inf"),
            "train_months": ",".join(train_months),
            "select_months": ",".join(select_months),
            "select_metrics": metrics(select, select_months),
            "test_metrics": metrics(test, [str(month)]),
        }

    y_train = pd.to_numeric(train["realized_return"], errors="coerce").fillna(0.0).clip(
        lower=-float(args.max_abs_target_return),
        upper=float(args.max_abs_target_return),
    )
    if y_train.nunique(dropna=True) < 3:
        test["return_meta_mode"] = "LOW_TARGET_VARIANCE"
        test["return_meta_threshold"] = float("-inf")
        return test, {
            "ticker": ticker,
            "month": str(month),
            "mode": "LOW_TARGET_VARIANCE",
            "threshold": float("-inf"),
            "train_months": ",".join(train_months),
            "select_months": ",".join(select_months),
            "select_metrics": metrics(select, select_months),
            "test_metrics": metrics(test, [str(month)]),
        }

    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    weights = 1.0 + np.minimum(
        pd.to_numeric(train["realized_return"], errors="coerce").fillna(0.0).abs().to_numpy(),
        float(args.max_abs_weight_return),
    )
    model = lgb.LGBMRegressor(
        objective=str(args.objective),
        n_estimators=int(args.estimators),
        learning_rate=float(args.learning_rate),
        num_leaves=int(args.num_leaves),
        min_child_samples=int(args.min_child_samples),
        subsample=float(args.subsample),
        colsample_bytree=float(args.colsample_bytree),
        reg_lambda=float(args.reg_lambda),
        random_state=int(args.seed),
        n_jobs=int(args.lgb_jobs),
        verbose=-1,
    )
    model.fit(x_train, y_train, sample_weight=weights)

    def add_score(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        x = out[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
        out["return_meta_score"] = model.predict(x)
        return out

    scored_select = add_score(select)
    scored_test = add_score(test)
    thresholds = [float("-inf")] + [float(x) for x in args.threshold_grid]
    finite = pd.to_numeric(scored_select["return_meta_score"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(finite):
        thresholds.extend(float(x) for x in finite.quantile([float(q) for q in args.threshold_quantiles]).to_numpy())

    best = {"score": -1e18, "threshold": float("-inf"), "metrics": metrics(scored_select, select_months)}
    for threshold in sorted(set(round(float(x), 8) for x in thresholds if np.isfinite(float(x)) or x == float("-inf"))):
        filtered = scored_select if threshold == float("-inf") else scored_select[scored_select["return_meta_score"].astype(float) >= threshold]
        row = metrics(filtered, select_months)
        score = score_selection(row, args)
        if score > float(best["score"]):
            best = {"score": float(score), "threshold": float(threshold), "metrics": row}

    threshold = float(best["threshold"])
    gated = scored_test if threshold == float("-inf") else scored_test[scored_test["return_meta_score"].astype(float) >= threshold].copy()
    gated["return_meta_mode"] = "NO_GATE" if threshold == float("-inf") else "RETURN_META_SCORE"
    gated["return_meta_threshold"] = threshold
    return gated, {
        "ticker": ticker,
        "month": str(month),
        "mode": "NO_GATE" if threshold == float("-inf") else "RETURN_META_SCORE",
        "threshold": threshold,
        "train_months": ",".join(train_months),
        "select_months": ",".join(select_months),
        "feature_count": len(feature_cols),
        "meta_score": float(best["score"]),
        "select_metrics": best["metrics"],
        "test_metrics": metrics(gated, [str(month)]),
    }


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, feature_cols: list[str], args: argparse.Namespace) -> None:
    expected = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, expected)
    risk_capital = float(args.risk_capital)
    per_ticker = {ticker: metrics(part, expected) for ticker, part in trades.groupby("ticker")}
    payload = {
        "overall": overall,
        "per_ticker": per_ticker,
        "net_pnl": float(overall["pnl_return"]) * risk_capital,
        "risk_capital": risk_capital,
        "feature_count": len(feature_cols),
        "feature_cols": feature_cols,
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Candidate Trade Return Meta Gate",
        "",
        "This result reads an already-built OOS candidate trade file and applies a per-ticker, per-month return-regression meta-gate. For month M, both model training and threshold selection use only earlier OOS months.",
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
        f"- Risk capital: ${risk_capital:,.0f}",
        f"- Net PnL: ${payload['net_pnl']:,.0f}",
        f"- Feature count: {len(feature_cols)}",
        "",
        "## Fold Audit",
        "",
        "```csv",
        folds.to_csv(index=False),
        "```",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(vars(args), indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a causal trade-level return-regression meta-gate to an event-option candidate file.")
    parser.add_argument("--trades", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--history-start-month", default="202601")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--feature-prefixes", nargs="+", default=["tdvp_"])
    parser.add_argument("--feature-exclude-prefixes", nargs="+", default=[])
    parser.add_argument("--include-latent-vectors", action="store_true")
    parser.add_argument("--include-physics-projection", action="store_true")
    parser.add_argument("--min-feature-non-null", type=int, default=30)
    parser.add_argument("--select-months", type=int, default=2)
    parser.add_argument("--min-train-trades", type=int, default=70)
    parser.add_argument("--min-select-trades", type=int, default=18)
    parser.add_argument("--min-select-month-trades", type=int, default=8)
    parser.add_argument("--min-select-pf", type=float, default=0.0)
    parser.add_argument("--min-select-win-rate", type=float, default=0.0)
    parser.add_argument("--min-call-rate", type=float, default=0.05)
    parser.add_argument("--max-call-rate", type=float, default=0.95)
    parser.add_argument("--daily-win-weight", type=float, default=0.50)
    parser.add_argument("--top5-share-penalty", type=float, default=0.25)
    parser.add_argument("--objective", default="regression_l1")
    parser.add_argument("--estimators", type=int, default=160)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=7)
    parser.add_argument("--min-child-samples", type=int, default=16)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.75)
    parser.add_argument("--reg-lambda", type=float, default=12.0)
    parser.add_argument("--max-abs-weight-return", type=float, default=2.0)
    parser.add_argument("--max-abs-target-return", type=float, default=3.0)
    parser.add_argument("--threshold-grid", nargs="+", type=float, default=[-0.20, -0.10, -0.05, 0.0, 0.03, 0.06, 0.10, 0.15, 0.20])
    parser.add_argument("--threshold-quantiles", nargs="+", type=float, default=[0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90])
    parser.add_argument("--lgb-jobs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260620)
    args = parser.parse_args()

    tickers = [str(t).upper() for t in args.tickers]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    trades = load_candidate_trades(Path(args.trades), tickers)
    trades = trades[
        (trades["test_month"].astype(str) >= str(args.history_start_month))
        & (trades["test_month"].astype(str) <= str(args.end_month))
    ].copy()
    features, raw_feature_cols = load_entry_features(Path(args.data), tickers, args)
    enriched, feature_cols = enrich_trades(trades, features, raw_feature_cols, args)
    all_months = sorted(enriched["test_month"].astype(str).unique())

    out_parts: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    for ticker in tickers:
        for month in month_range(str(args.start_month), str(args.end_month)):
            gated, fold = fit_month_gate(enriched, feature_cols, ticker, str(month), all_months, args)
            if not gated.empty:
                out_parts.append(gated)
            train_months = str(fold.get("train_months", ""))
            select_months = str(fold.get("select_months", ""))
            row = {
                "ticker": ticker,
                "month": str(month),
                "mode": fold.get("mode", ""),
                "threshold": fold.get("threshold", float("nan")),
                "train_months": train_months,
                "select_months": select_months,
                "feature_count": fold.get("feature_count", len(feature_cols)),
                "meta_score": fold.get("meta_score", float("nan")),
                "leak_ok": all((not x or x < str(month)) for x in (train_months.split(",") + select_months.split(","))),
            }
            row.update(flatten("select", fold.get("select_metrics", metrics(pd.DataFrame(), []))))
            row.update(flatten("test", fold.get("test_metrics", metrics(pd.DataFrame(), [str(month)]))))
            fold_rows.append(row)

    gated_trades = pd.concat(out_parts, ignore_index=True) if out_parts else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    if not gated_trades.empty:
        gated_trades.to_csv(output_dir / "candidate_trade_return_meta_trades.csv", index=False)
    folds.to_csv(output_dir / "candidate_trade_return_meta_folds.csv", index=False)
    pd.Series(feature_cols, name="feature").to_csv(output_dir / "candidate_trade_return_meta_features.csv", index=False)
    write_plot(output_dir, gated_trades, float(args.risk_capital))
    write_summary(output_dir, gated_trades, folds, feature_cols, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
