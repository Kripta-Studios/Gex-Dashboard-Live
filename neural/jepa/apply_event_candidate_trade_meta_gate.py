from __future__ import annotations

import argparse
import json
from pathlib import Path

import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics, score_metrics


LEAKY_PATTERNS = (
    "future",
    "spot_long",
    "spot_short",
    "spot_best",
    "_opt_win",
    "_opt_status",
    "_opt_exit_ret",
    "_opt_exit_minutes",
    "_opt_max_ret",
    "_opt_min_ret",
)

DEFAULT_VECTOR_PREFIXES = (
    "tdvp_z_",
    "tdvp_dz_",
    "tdvp_phys_",
    "tdvp_phys_delta_",
    "ptdj_z_",
    "ptdj_dz_",
    "ptdj_phys_",
    "ptdj_phys_delta_",
)


def parse_clock_minutes(value: object) -> float:
    text = str(value)
    if ":" not in text:
        return float("nan")
    try:
        hour, minute = text.split(":", 1)
        return float(int(hour) * 60 + int(minute[:2]))
    except ValueError:
        return float("nan")


def first_valid_numeric(frame: pd.DataFrame, names: list[str]) -> pd.Series:
    out = pd.Series(np.nan, index=frame.index, dtype=float)
    for name in names:
        if name not in frame.columns:
            continue
        values = pd.to_numeric(frame[name], errors="coerce")
        out = out.where(out.notna(), values)
    return out


def load_candidate_trades(path: Path, tickers: list[str]) -> pd.DataFrame:
    trades = pd.read_csv(path, dtype={"date": str, "month": str, "test_month": str, "time": str})
    trades["ticker"] = trades["ticker"].astype(str).str.upper()
    if tickers:
        allowed = {str(t).upper() for t in tickers}
        trades = trades[trades["ticker"].isin(allowed)].copy()
    if "test_month" not in trades.columns:
        trades["test_month"] = trades["month"].astype(str)
    trades["test_month"] = trades["test_month"].astype(str)
    trades["month"] = trades["test_month"]
    trades["date"] = trades["date"].astype(str)
    trades["time"] = trades["time"].astype(str)
    trades["expiry_mode"] = trades["expiry_mode"].astype(str)
    trades["realized_return"] = pd.to_numeric(trades["realized_return"], errors="coerce").fillna(0.0)

    minute = first_valid_numeric(trades, ["minute", "minute_x", "minute_y", "entry_minute"])
    parsed = trades["time"].map(parse_clock_minutes)
    trades["entry_minute"] = minute.where(minute.notna(), parsed).fillna(0.0).astype(int)
    trades["action_is_call"] = (trades["action"].astype(str).str.upper() == "CALL").astype(float)
    trades["score"] = pd.to_numeric(trades.get("score"), errors="coerce")
    trades["pred_call_return"] = pd.to_numeric(trades.get("pred_call_return"), errors="coerce")
    trades["pred_put_return"] = pd.to_numeric(trades.get("pred_put_return"), errors="coerce")
    trades["score_margin"] = (trades["pred_call_return"] - trades["pred_put_return"]).abs()
    if "meta_score" in trades.columns:
        trades["prior_meta_score"] = pd.to_numeric(trades["meta_score"], errors="coerce")
    trades["weekday"] = pd.to_datetime(trades["date"], format="%Y%m%d", errors="coerce").dt.weekday.astype(float)
    trades = trades.sort_values(["ticker", "date", "entry_minute", "score"], ascending=[True, True, True, False])
    trades["candidate_seq_in_day"] = trades.groupby(["ticker", "date"]).cumcount().astype(float)
    return trades.reset_index(drop=True)


def feature_columns_from_parquet(raw: pd.DataFrame, args: argparse.Namespace) -> list[str]:
    include_prefixes = tuple(str(x).lower() for x in args.feature_prefixes if str(x).strip())
    exclude_prefixes = tuple(str(x).lower() for x in args.feature_exclude_prefixes if str(x).strip())
    vector_prefixes = tuple(str(x).lower() for x in DEFAULT_VECTOR_PREFIXES)
    cols: list[str] = []
    for col in raw.columns:
        low = str(col).lower()
        if col in {"trade_date", "date", "expiration", "timestamp", "time", "underlying_ticker", "ticker", "expiry_mode", "nearest_level_name"}:
            continue
        if any(pattern in low for pattern in LEAKY_PATTERNS):
            continue
        if include_prefixes and not low.startswith(include_prefixes):
            continue
        if exclude_prefixes and low.startswith(exclude_prefixes):
            continue
        if not bool(args.include_latent_vectors) and low.startswith(vector_prefixes):
            continue
        if not bool(args.include_physics_projection) and (low.startswith("tdvp_phys_") or low.startswith("ptdj_phys_")):
            continue
        if pd.api.types.is_numeric_dtype(raw[col]):
            cols.append(col)
    return cols


def load_entry_features(data_path: Path, tickers: list[str], args: argparse.Namespace) -> tuple[pd.DataFrame, list[str]]:
    raw = pd.read_parquet(data_path)
    raw["ticker"] = raw["ticker"].astype(str).str.upper()
    if tickers:
        allowed = {str(t).upper() for t in tickers}
        raw = raw[raw["ticker"].isin(allowed)].copy()
    raw["date"] = raw["trade_date"].astype(str)
    raw["time"] = raw["time"].astype(str)
    raw["expiry_mode"] = raw["expiry_mode"].astype(str)
    keys = ["ticker", "date", "time", "expiry_mode"]
    feature_cols = feature_columns_from_parquet(raw, args)
    features = raw[keys + feature_cols].drop_duplicates(keys, keep="first")
    return features, feature_cols


def enrich_trades(trades: pd.DataFrame, features: pd.DataFrame, raw_feature_cols: list[str], args: argparse.Namespace) -> tuple[pd.DataFrame, list[str]]:
    keys = ["ticker", "date", "time", "expiry_mode"]
    work = trades.copy()
    overlap = [c for c in raw_feature_cols if c in work.columns]
    if overlap:
        work = work.drop(columns=overlap)
    work = work.merge(features, on=keys, how="left")

    cat_cols = [c for c in ["expiry_mode", "action", "source_variant", "selected_model", "deploy_config"] if c in work.columns]
    if cat_cols:
        work = pd.concat([work, pd.get_dummies(work[cat_cols].fillna("NA").astype(str), prefix=cat_cols, dtype=float)], axis=1)

    base_cols = [
        "score",
        "pred_call_return",
        "pred_put_return",
        "score_margin",
        "entry_minute",
        "weekday",
        "candidate_seq_in_day",
        "action_is_call",
        "prior_meta_score",
    ]
    dummy_cols = [c for c in work.columns if any(c.startswith(f"{cat}_") for cat in cat_cols)]
    selected: list[str] = []
    for col in dict.fromkeys(base_cols + dummy_cols + raw_feature_cols):
        if col not in work.columns or not pd.api.types.is_numeric_dtype(work[col]):
            continue
        values = pd.to_numeric(work[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        if values.notna().sum() >= int(args.min_feature_non_null) and values.nunique(dropna=True) > 1:
            selected.append(col)
    return work, selected


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


def fit_month_gate(trades: pd.DataFrame, feature_cols: list[str], ticker: str, month: str, all_months: list[str], args: argparse.Namespace) -> tuple[pd.DataFrame, dict]:
    test = trades[(trades["ticker"].astype(str) == ticker) & (trades["test_month"].astype(str) == str(month))].copy()
    previous = [m for m in all_months if m < str(month)]
    select_n = int(args.select_months)
    if test.empty:
        return test, {"ticker": ticker, "month": str(month), "mode": "NO_TEST_ROWS", "threshold": float("nan"), "test_metrics": metrics(test, [str(month)])}
    if len(previous) <= select_n:
        test["trade_meta_mode"] = "NO_HISTORY"
        test["trade_meta_threshold"] = float("-inf")
        return test, {"ticker": ticker, "month": str(month), "mode": "NO_HISTORY", "threshold": float("-inf"), "test_metrics": metrics(test, [str(month)])}

    train_months = previous[:-select_n]
    select_months = previous[-select_n:]
    train = trades[(trades["ticker"].astype(str) == ticker) & (trades["test_month"].astype(str).isin(train_months))].copy()
    select = trades[(trades["ticker"].astype(str) == ticker) & (trades["test_month"].astype(str).isin(select_months))].copy()
    if len(train) < int(args.min_train_trades) or len(select) < int(args.min_select_trades):
        test["trade_meta_mode"] = "INSUFFICIENT_ROWS"
        test["trade_meta_threshold"] = float("-inf")
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

    y_train = (pd.to_numeric(train["realized_return"], errors="coerce").fillna(0.0) > 0.0).astype(int)
    if y_train.nunique() < 2:
        test["trade_meta_mode"] = "SINGLE_CLASS_TRAIN"
        test["trade_meta_threshold"] = float("-inf")
        return test, {
            "ticker": ticker,
            "month": str(month),
            "mode": "SINGLE_CLASS_TRAIN",
            "threshold": float("-inf"),
            "train_months": ",".join(train_months),
            "select_months": ",".join(select_months),
            "select_metrics": metrics(select, select_months),
            "test_metrics": metrics(test, [str(month)]),
        }

    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    weights = 1.0 + np.minimum(pd.to_numeric(train["realized_return"], errors="coerce").fillna(0.0).abs().to_numpy(), float(args.max_abs_weight_return))
    model = lgb.LGBMClassifier(
        objective="binary",
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
        out["trade_meta_score"] = model.predict_proba(x)[:, 1]
        return out

    scored_select = add_score(select)
    scored_test = add_score(test)
    thresholds = [float("-inf")] + [float(x) for x in args.threshold_grid]
    finite = pd.to_numeric(scored_select["trade_meta_score"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(finite):
        thresholds.extend(float(x) for x in finite.quantile([float(q) for q in args.threshold_quantiles]).to_numpy())

    best = {"score": -1e18, "threshold": float("-inf"), "metrics": metrics(scored_select, select_months)}
    for threshold in sorted(set(round(float(x), 8) for x in thresholds if np.isfinite(float(x)) or x == float("-inf"))):
        filtered = scored_select if threshold == float("-inf") else scored_select[scored_select["trade_meta_score"].astype(float) >= threshold]
        row = metrics(filtered, select_months)
        score = score_selection(row, args)
        if score > float(best["score"]):
            best = {"score": float(score), "threshold": float(threshold), "metrics": row}

    threshold = float(best["threshold"])
    gated = scored_test if threshold == float("-inf") else scored_test[scored_test["trade_meta_score"].astype(float) >= threshold].copy()
    gated["trade_meta_mode"] = "NO_GATE" if threshold == float("-inf") else "TRADE_META_SCORE"
    gated["trade_meta_threshold"] = threshold
    return gated, {
        "ticker": ticker,
        "month": str(month),
        "mode": "NO_GATE" if threshold == float("-inf") else "TRADE_META_SCORE",
        "threshold": threshold,
        "train_months": ",".join(train_months),
        "select_months": ",".join(select_months),
        "feature_count": len(feature_cols),
        "meta_score": float(best["score"]),
        "select_metrics": best["metrics"],
        "test_metrics": metrics(gated, [str(month)]),
    }


def flatten(prefix: str, row: dict) -> dict:
    return {f"{prefix}_{k}": v for k, v in row.items()}


def write_plot(output_dir: Path, trades: pd.DataFrame, risk_capital: float) -> None:
    if trades.empty:
        return
    work = trades.copy()
    work["dt"] = pd.to_datetime(work["date"].astype(str), format="%Y%m%d", errors="coerce")
    work["pnl"] = pd.to_numeric(work["realized_return"], errors="coerce").fillna(0.0) * float(risk_capital)
    daily = work.groupby("dt")["pnl"].sum().sort_index()
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    daily = daily.reindex(idx).fillna(0.0)
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(daily.index, daily.cumsum(), color="#111827", linewidth=2.4, label="TOTAL")
    for ticker, part in work.groupby("ticker"):
        curve = part.groupby("dt")["pnl"].sum().sort_index().reindex(idx).fillna(0.0).cumsum()
        axes[0].plot(curve.index, curve.values, linewidth=1.6, label=str(ticker))
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Candidate Trade Meta Gate Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(daily.index, daily.values, color=np.where(daily >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "candidate_trade_meta_daily_net_pnl.png", dpi=160)
    plt.close(fig)


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
        "# Event Candidate Trade Meta Gate",
        "",
        "This result reads an already-built OOS candidate trade file and applies a per-ticker, per-month trade-level meta-gate. For month M, both model training and threshold selection use only earlier OOS months.",
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
    parser = argparse.ArgumentParser(description="Apply a causal trade-level meta-gate to an already-combined event-option candidate file.")
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
    parser.add_argument("--estimators", type=int, default=120)
    parser.add_argument("--learning-rate", type=float, default=0.04)
    parser.add_argument("--num-leaves", type=int, default=7)
    parser.add_argument("--min-child-samples", type=int, default=16)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.75)
    parser.add_argument("--reg-lambda", type=float, default=10.0)
    parser.add_argument("--max-abs-weight-return", type=float, default=2.0)
    parser.add_argument("--threshold-grid", nargs="+", type=float, default=[0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75])
    parser.add_argument("--threshold-quantiles", nargs="+", type=float, default=[0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90])
    parser.add_argument("--lgb-jobs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260619)
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
        gated_trades.to_csv(output_dir / "candidate_trade_meta_trades.csv", index=False)
    folds.to_csv(output_dir / "candidate_trade_meta_folds.csv", index=False)
    pd.Series(feature_cols, name="feature").to_csv(output_dir / "candidate_trade_meta_features.csv", index=False)
    write_plot(output_dir, gated_trades, float(args.risk_capital))
    write_summary(output_dir, gated_trades, folds, feature_cols, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
