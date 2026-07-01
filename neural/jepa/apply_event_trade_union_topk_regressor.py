from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apply_event_trade_union_meta_gate import (
    apply_cooldown,
    enrich_features,
    load_trade_sources,
)
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


def fit_topk_model(train: pd.DataFrame, feature_cols: list[str], args: argparse.Namespace) -> tuple[lgb.LGBMRegressor, pd.Series]:
    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    y_train = pd.to_numeric(train["realized_return"], errors="coerce").fillna(0.0).clip(
        lower=-float(args.clip_target), upper=float(args.clip_target)
    )
    weights = 1.0 + np.minimum(pd.to_numeric(train["realized_return"], errors="coerce").fillna(0.0).abs().to_numpy(), 2.0)
    model = lgb.LGBMRegressor(
        objective=str(args.objective),
        n_estimators=int(args.n_estimators),
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
    return model, medians


def score_with_topk_model(
    model: lgb.LGBMRegressor,
    medians: pd.Series,
    score_frame: pd.DataFrame,
    feature_cols: list[str],
) -> pd.DataFrame:
    out = score_frame.copy()
    x_score = out[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    out["topk_pred_return"] = model.predict(x_score)
    return out


def fit_regressor(train: pd.DataFrame, score_frame: pd.DataFrame, feature_cols: list[str], args: argparse.Namespace) -> pd.DataFrame:
    model, medians = fit_topk_model(train, feature_cols, args)
    return score_with_topk_model(model, medians, score_frame, feature_cols)


def select_topk(frame: pd.DataFrame, topk: int, score_col: str = "topk_pred_return") -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    if int(topk) >= 999:
        return frame.copy()
    parts: list[pd.DataFrame] = []
    for (_ticker, _month), group in frame.groupby(["ticker", "test_month"], sort=False):
        sort_cols = [score_col]
        ascending = [False]
        if score_col != "score" and "score" in group.columns:
            sort_cols.append("score")
            ascending.append(False)
        parts.append(group.sort_values(sort_cols, ascending=ascending).head(int(topk)))
    return pd.concat(parts, ignore_index=True) if parts else frame.iloc[0:0].copy()


def select_threshold(frame: pd.DataFrame, threshold: float, score_col: str = "topk_pred_return") -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    if not np.isfinite(float(threshold)):
        return frame.copy()
    return frame[pd.to_numeric(frame[score_col], errors="coerce").fillna(float("-inf")) >= float(threshold)].copy()


def score_row(row: dict, args: argparse.Namespace) -> float:
    if int(row.get("min_month_trades", 0)) < int(args.min_select_month_trades):
        return -1e18
    pf = float(row.get("profit_factor", 0.0))
    wr = float(row.get("win_rate", 0.0))
    call_rate = float(row.get("call_rate", float("nan")))
    pnl_return = float(row.get("pnl_return", 0.0))
    positive_month_rate = float(row.get("positive_month_rate", 0.0))
    min_month = float(row.get("min_month_trades", 0.0))
    if not np.isfinite(call_rate) or call_rate < float(args.min_select_call_rate) or call_rate > float(args.max_select_call_rate):
        return -1e18
    return (
        min(pf, float(args.score_pf_cap)) * float(args.score_pf_weight)
        + wr * float(args.score_win_weight)
        + pnl_return * float(args.score_return_weight)
        + positive_month_rate * float(args.score_positive_month_weight)
        + min(min_month, 40.0) * float(args.score_volume_weight)
    )


def unique_thresholds(scored_select: pd.DataFrame, args: argparse.Namespace, score_col: str) -> list[float]:
    thresholds: list[float] = [float("-inf")]
    thresholds.extend(float(x) for x in getattr(args, "score_threshold_grid", []))
    finite = pd.to_numeric(scored_select[score_col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(finite):
        quantiles = [float(q) for q in getattr(args, "score_threshold_quantiles", [])]
        if quantiles:
            thresholds.extend(float(x) for x in finite.quantile(quantiles).to_numpy())

    out: list[float] = []
    seen: set[str] = set()
    for raw in thresholds:
        value = float(raw)
        key = "-inf" if not np.isfinite(value) and value < 0 else f"{value:.8f}"
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return sorted(out)


def choose_threshold(
    scored_select: pd.DataFrame,
    select_months: list[str],
    args: argparse.Namespace,
    score_col: str = "topk_pred_return",
) -> tuple[float, dict, float]:
    best_threshold = float("-inf")
    best_metrics = metrics(select_threshold(scored_select, best_threshold, score_col), select_months)
    best_score = score_row(best_metrics, args)
    for threshold in unique_thresholds(scored_select, args, score_col):
        row = metrics(select_threshold(scored_select, threshold, score_col), select_months)
        score = score_row(row, args)
        if score > best_score:
            best_threshold = float(threshold)
            best_metrics = row
            best_score = score
    return best_threshold, best_metrics, float(best_score)


def choose_topk(
    scored_select: pd.DataFrame,
    select_months: list[str],
    args: argparse.Namespace,
    score_col: str = "topk_pred_return",
) -> tuple[int, dict, float]:
    best_k = int(args.topk_grid[0])
    best_metrics = metrics(select_topk(scored_select, best_k, score_col), select_months)
    best_score = score_row(best_metrics, args)
    for raw_k in args.topk_grid[1:]:
        k = int(raw_k)
        row = metrics(select_topk(scored_select, k, score_col), select_months)
        score = score_row(row, args)
        if score > best_score:
            best_k = k
            best_metrics = row
            best_score = score
    return best_k, best_metrics, float(best_score)


def choose_and_apply_selection(
    scored_select: pd.DataFrame,
    scored_test: pd.DataFrame,
    select_months: list[str],
    args: argparse.Namespace,
    score_col: str = "topk_pred_return",
) -> tuple[pd.DataFrame, dict]:
    mode = str(getattr(args, "selection_mode", "topk")).lower()
    if mode == "threshold":
        threshold, select_metrics, select_score = choose_threshold(scored_select, select_months, args, score_col)
        out = select_threshold(scored_test, threshold, score_col)
        if not out.empty:
            out["topk_mode"] = "THRESHOLD_REGRESSOR" if score_col == "topk_pred_return" else "PRIOR_SCORE_THRESHOLD"
            out["topk_selected_k"] = 999
            out["topk_score_threshold"] = float(threshold)
        return out, {
            "selection_mode": "threshold",
            "topk": 999,
            "threshold": float(threshold),
            "select_metrics": select_metrics,
            "select_score": float(select_score),
        }

    topk, select_metrics, select_score = choose_topk(scored_select, select_months, args, score_col)
    out = select_topk(scored_test, topk, score_col)
    if not out.empty:
        out["topk_mode"] = "TOPK_REGRESSOR" if score_col == "topk_pred_return" else "PRIOR_SCORE_TOPK"
        out["topk_selected_k"] = int(topk)
        out["topk_score_threshold"] = np.nan
    return out, {
        "selection_mode": "topk",
        "topk": int(topk),
        "threshold": float("nan"),
        "select_metrics": select_metrics,
        "select_score": float(select_score),
    }


def startup_score_fallback(
    trades: pd.DataFrame,
    test: pd.DataFrame,
    previous: list[str],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame | None, dict | None]:
    if not bool(args.startup_score_fallback):
        return None, None
    if "score" not in trades.columns:
        return None, None
    if len(previous) < int(args.startup_min_select_months):
        return None, None
    select_n = min(int(args.select_months), len(previous))
    select_months = previous[-select_n:]
    select = trades[trades["test_month"].astype(str).isin(select_months)].copy()
    if len(select) < int(args.startup_min_select_trades):
        return None, None
    scored_select = select.copy()
    scored_test = test.copy()
    scored_select["topk_pred_return"] = pd.to_numeric(scored_select["score"], errors="coerce").fillna(0.0)
    scored_test["topk_pred_return"] = pd.to_numeric(scored_test["score"], errors="coerce").fillna(0.0)
    out, selection = choose_and_apply_selection(scored_select, scored_test, select_months, args, "topk_pred_return")
    train_months = [m for m in previous if m not in select_months]
    return out, {
        "month": str(test["test_month"].iloc[0]) if not test.empty else "",
        "mode": "PRIOR_SCORE_THRESHOLD" if selection["selection_mode"] == "threshold" else "PRIOR_SCORE_TOPK",
        "topk": int(selection["topk"]),
        "threshold": float(selection["threshold"]),
        "train_months": ",".join(train_months),
        "select_months": ",".join(select_months),
        "select_score": float(selection["select_score"]),
        "select_metrics": selection["select_metrics"],
        "test_metrics": metrics(out, [str(test["test_month"].iloc[0])] if not test.empty else []),
    }


def run_fold(trades: pd.DataFrame, feature_cols: list[str], test_month: str, all_months: list[str], args: argparse.Namespace) -> tuple[pd.DataFrame, dict]:
    previous = [m for m in all_months if m < str(test_month)]
    test = trades[trades["test_month"].astype(str) == str(test_month)].copy()
    if test.empty:
        return test, {"month": str(test_month), "mode": "EMPTY", "topk": 0, "test_metrics": metrics(test, [str(test_month)])}
    select_n = int(args.select_months)
    if len(previous) <= select_n:
        fallback, fold = startup_score_fallback(trades, test, previous, args)
        if fallback is not None and fold is not None:
            return fallback, fold
        out = test.copy()
        out["topk_mode"] = "NO_HISTORY"
        out["topk_selected_k"] = 999
        out["topk_pred_return"] = np.nan
        return out, {"month": str(test_month), "mode": "NO_HISTORY", "topk": 999, "test_metrics": metrics(out, [str(test_month)])}
    train_months = previous[:-select_n]
    select_months = previous[-select_n:]
    train = trades[trades["test_month"].astype(str).isin(train_months)].copy()
    select = trades[trades["test_month"].astype(str).isin(select_months)].copy()
    if len(train) < int(args.min_train_trades) or len(select) < int(args.min_select_trades):
        fallback, fold = startup_score_fallback(trades, test, previous, args)
        if fallback is not None and fold is not None:
            return fallback, fold
        out = test.copy()
        out["topk_mode"] = "INSUFFICIENT_ROWS"
        out["topk_selected_k"] = 999
        out["topk_pred_return"] = np.nan
        return out, {
            "month": str(test_month),
            "mode": "INSUFFICIENT_ROWS",
            "topk": 999,
            "train_months": ",".join(train_months),
            "select_months": ",".join(select_months),
            "select_metrics": metrics(select, select_months),
            "test_metrics": metrics(out, [str(test_month)]),
        }
    if (pd.to_numeric(train["realized_return"], errors="coerce").fillna(0.0) > 0.0).nunique() < 2:
        out = test.copy()
        out["topk_mode"] = "SINGLE_CLASS_TRAIN"
        out["topk_selected_k"] = 999
        out["topk_pred_return"] = np.nan
        return out, {
            "month": str(test_month),
            "mode": "SINGLE_CLASS_TRAIN",
            "topk": 999,
            "train_months": ",".join(train_months),
            "select_months": ",".join(select_months),
            "select_metrics": metrics(select, select_months),
            "test_metrics": metrics(out, [str(test_month)]),
        }

    model, medians = fit_topk_model(train, feature_cols, args)
    scored_select = score_with_topk_model(model, medians, select, feature_cols)
    scored_test = score_with_topk_model(model, medians, test, feature_cols)
    out, selection = choose_and_apply_selection(scored_select, scored_test, select_months, args)
    return out, {
        "month": str(test_month),
        "mode": "THRESHOLD_REGRESSOR" if selection["selection_mode"] == "threshold" else "TOPK_REGRESSOR",
        "topk": int(selection["topk"]),
        "threshold": float(selection["threshold"]),
        "train_months": ",".join(train_months),
        "select_months": ",".join(select_months),
        "select_score": float(selection["select_score"]),
        "select_metrics": selection["select_metrics"],
        "test_metrics": metrics(out, [str(test_month)]),
    }


def flatten(prefix: str, row: dict | None) -> dict:
    row = row or {}
    return {f"{prefix}_{key}": value for key, value in row.items()}


def write_plot(output_dir: Path, trades: pd.DataFrame, risk_capital: float) -> None:
    if trades.empty:
        return
    work = trades.copy()
    work["dt"] = pd.to_datetime(work["date"].astype(str), format="%Y%m%d", errors="coerce")
    work["pnl"] = pd.to_numeric(work["realized_return"], errors="coerce").fillna(0.0) * float(risk_capital)
    daily = work.groupby("dt")["pnl"].sum().sort_index()
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    daily = daily.reindex(idx).fillna(0.0)
    pd.DataFrame({"date": idx.strftime("%Y%m%d"), "daily_pnl": daily.values, "cum_pnl": daily.cumsum().values}).to_csv(
        output_dir / "topk_regressor_daily_total.csv", index=False
    )
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(idx, daily.cumsum().values, color="#111827", linewidth=2.4)
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Trade Union Top-K Regressor Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(idx, daily.values, color=np.where(daily.values >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "topk_regressor_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, args: argparse.Namespace) -> None:
    expected = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, expected)
    by_ticker = {ticker: metrics(part, expected) for ticker, part in trades.groupby("ticker", sort=True)} if not trades.empty else {}
    payload = {
        "overall": overall,
        "by_ticker": by_ticker,
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "risk_capital": float(args.risk_capital),
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Trade Union Top-K Regressor",
        "",
        "This result combines precomputed causal trade streams, applies deterministic cooldown/max-day, then trains a monthly return regressor using only earlier OOS months. Selection is chosen on trailing prior months and applied to the test month.",
        "",
        f"- Selection mode: `{str(args.selection_mode)}`",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        "## By Ticker",
        "",
        "```json",
        json.dumps(by_ticker, indent=2, allow_nan=True),
        "```",
        "",
        f"- Risk capital: ${float(args.risk_capital):,.0f}",
        f"- Net PnL: ${payload['net_pnl']:,.0f}",
        "",
        "## Folds",
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


def export_deploy_model(
    output_dir: Path,
    enriched: pd.DataFrame,
    feature_cols: list[str],
    all_months: list[str],
    args: argparse.Namespace,
) -> None:
    deploy_month = str(args.deploy_month)
    deploy_select_end_month = str(args.deploy_select_end_month).strip()
    if deploy_select_end_month:
        if deploy_select_end_month >= deploy_month:
            raise RuntimeError(
                f"--deploy-select-end-month {deploy_select_end_month} must be earlier than deploy month {deploy_month}"
            )
        previous = [m for m in all_months if m < deploy_month and m <= deploy_select_end_month]
    else:
        previous = [m for m in all_months if m < deploy_month]
    select_n = int(args.select_months)
    if len(previous) <= select_n:
        raise RuntimeError(f"Not enough prior months to export deploy model for {deploy_month}: {previous}")
    train_months = previous[:-select_n]
    select_months = previous[-select_n:]
    train = enriched[enriched["test_month"].astype(str).isin(train_months)].copy()
    select = enriched[enriched["test_month"].astype(str).isin(select_months)].copy()
    if len(train) < int(args.min_train_trades):
        raise RuntimeError(f"Deploy train rows {len(train)} < min_train_trades {args.min_train_trades}")
    if len(select) < int(args.min_select_trades):
        raise RuntimeError(f"Deploy select rows {len(select)} < min_select_trades {args.min_select_trades}")
    if (pd.to_numeric(train["realized_return"], errors="coerce").fillna(0.0) > 0.0).nunique() < 2:
        raise RuntimeError("Deploy train rows have a single realized-return class")

    model, medians = fit_topk_model(train, feature_cols, args)
    scored_select = score_with_topk_model(model, medians, select, feature_cols)
    empty_test = select.iloc[0:0].copy()
    _, selection = choose_and_apply_selection(scored_select, empty_test, select_months, args)
    topk = int(selection["topk"])
    threshold = float(selection["threshold"])
    select_metrics = selection["select_metrics"]
    select_score = float(selection["select_score"])
    if float(select_score) <= -1e17 and not bool(args.allow_invalid_deploy_selection):
        raise RuntimeError(
            "Deploy selection failed validation for "
            f"{deploy_month} using select_months={select_months}; "
            "pass --allow-invalid-deploy-selection only for diagnostics."
        )
    selected_sources = (
        sorted(enriched["source_variant"].astype(str).dropna().unique().tolist())
        if "source_variant" in enriched.columns
        else []
    )
    payload = {
        "schema_version": 1,
        "component": "event_trade_union_topk_regressor",
        "ticker": str(args.ticker).upper(),
        "deploy_month": deploy_month,
        "deploy_select_end_month": deploy_select_end_month or None,
        "train_months": train_months,
        "select_months": select_months,
        "selection_mode": str(args.selection_mode),
        "selected_topk": int(topk),
        "selected_score_threshold": None if not np.isfinite(threshold) else float(threshold),
        "select_score": float(select_score),
        "select_metrics": select_metrics,
        "feature_cols": feature_cols,
        "feature_medians": {str(k): float(v) if np.isfinite(float(v)) else 0.0 for k, v in medians.fillna(0.0).items()},
        "source_variants": selected_sources,
        "args": vars(args),
    }
    deploy_dir = output_dir / "deploy_model"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    with (deploy_dir / "topk_regressor_model.pkl").open("wb") as fh:
        pickle.dump({"model": model, "medians": medians, "feature_cols": feature_cols, "metadata": payload}, fh)
    (deploy_dir / "topk_regressor_model.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    if str(args.selection_mode).lower() == "threshold":
        selected = select_threshold(scored_select, threshold)
    else:
        selected = select_topk(scored_select, topk)
    if not selected.empty:
        selected.to_csv(deploy_dir / "deploy_select_month_scored_trades.csv", index=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a causal top-K return regressor to a union of precomputed event-option trade streams.")
    parser.add_argument("--trade-source", action="append", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--history-start-month", default="202507")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--max-day", type=int, default=8)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--include-latent-vectors", action="store_true")
    parser.add_argument("--select-months", type=int, default=3)
    parser.add_argument("--min-train-trades", type=int, default=80)
    parser.add_argument("--min-select-trades", type=int, default=54)
    parser.add_argument("--min-select-month-trades", type=int, default=19)
    parser.add_argument("--min-select-call-rate", type=float, default=0.0)
    parser.add_argument("--max-select-call-rate", type=float, default=1.0)
    parser.add_argument("--selection-mode", choices=["topk", "threshold"], default="topk")
    parser.add_argument("--topk-grid", nargs="+", type=int, default=[19, 20, 21, 22, 24, 26, 28, 30, 35, 40, 45, 50, 60, 70, 999])
    parser.add_argument("--score-threshold-grid", nargs="+", type=float, default=[])
    parser.add_argument("--score-threshold-quantiles", nargs="+", type=float, default=[0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95])
    parser.add_argument("--score-pf-weight", type=float, default=3.0)
    parser.add_argument("--score-pf-cap", type=float, default=4.0)
    parser.add_argument("--score-win-weight", type=float, default=20.0)
    parser.add_argument("--score-return-weight", type=float, default=0.10)
    parser.add_argument("--score-positive-month-weight", type=float, default=4.0)
    parser.add_argument("--score-volume-weight", type=float, default=0.10)
    parser.add_argument("--clip-target", type=float, default=2.5)
    parser.add_argument("--objective", default="regression_l1")
    parser.add_argument("--n-estimators", type=int, default=260)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--num-leaves", type=int, default=15)
    parser.add_argument("--min-child-samples", type=int, default=16)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.80)
    parser.add_argument("--reg-lambda", type=float, default=8.0)
    parser.add_argument("--lgb-jobs", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20260619)
    parser.add_argument(
        "--startup-score-fallback",
        action="store_true",
        help="For early folds without enough training rows, choose top-K on prior OOS source scores instead of passing all trades.",
    )
    parser.add_argument("--startup-min-select-months", type=int, default=1)
    parser.add_argument("--startup-min-select-trades", type=int, default=19)
    parser.add_argument(
        "--deploy-month",
        default="",
        help="Optional future YYYYMM. When set with --export-deploy-model, fit and serialize the model/config for that month.",
    )
    parser.add_argument(
        "--deploy-select-end-month",
        default="",
        help="Optional latest completed YYYYMM allowed for deploy top-k selection. Use this to exclude partial months.",
    )
    parser.add_argument("--export-deploy-model", action="store_true")
    parser.add_argument("--allow-invalid-deploy-selection", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    base_trades = load_trade_sources(args.trade_source, args.ticker)
    if base_trades.empty:
        raise RuntimeError("No input trades after ticker filtering.")
    base_trades = base_trades[
        (base_trades["test_month"].astype(str) >= str(args.history_start_month))
        & (base_trades["test_month"].astype(str) <= str(args.end_month))
    ].copy()
    union = apply_cooldown(base_trades, int(args.max_day), int(args.cooldown_minutes))
    enriched, feature_cols = enrich_features(union, Path(args.data), args.ticker, bool(args.include_latent_vectors))
    all_months = sorted(enriched["test_month"].astype(str).unique())
    out_parts: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    for month in month_range(str(args.start_month), str(args.end_month)):
        selected, fold = run_fold(enriched, feature_cols, str(month), all_months, args)
        if not selected.empty:
            out_parts.append(selected)
        row = {
            "ticker": str(args.ticker).upper(),
            "month": str(month),
            "mode": fold.get("mode", ""),
            "topk": fold.get("topk", 0),
            "threshold": fold.get("threshold", float("nan")),
            "train_months": fold.get("train_months", ""),
            "select_months": fold.get("select_months", ""),
            "select_score": fold.get("select_score", float("nan")),
            "feature_count": len(feature_cols),
        }
        row.update(flatten("select", fold.get("select_metrics")))
        row.update(flatten("test", fold.get("test_metrics")))
        fold_rows.append(row)
    trades = pd.concat(out_parts, ignore_index=True) if out_parts else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    if not trades.empty:
        trades.to_csv(output_dir / "trade_union_topk_regressor_trades.csv", index=False)
    folds.to_csv(output_dir / "trade_union_topk_regressor_folds.csv", index=False)
    if bool(args.export_deploy_model):
        if not str(args.deploy_month).strip():
            raise RuntimeError("--export-deploy-model requires --deploy-month")
        export_deploy_model(output_dir, enriched, feature_cols, all_months, args)
    write_plot(output_dir, trades, float(args.risk_capital))
    write_summary(output_dir, trades, folds, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
