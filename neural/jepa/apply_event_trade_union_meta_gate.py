from __future__ import annotations

import argparse
import json
import pickle
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


def parse_trade_source(spec: str, priority: int) -> tuple[str, Path, int]:
    if "=" not in spec:
        path = Path(spec)
        return path.stem, path, priority
    name, raw_path = spec.split("=", 1)
    return name.strip(), Path(raw_path.strip()), priority


def load_trade_sources(specs: list[str], ticker: str) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for priority, spec in enumerate(specs):
        name, path, source_priority = parse_trade_source(spec, priority)
        if path.is_dir():
            path = path / "event_option_gate_trades.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        frame = pd.read_csv(path, dtype={"date": str, "month": str, "test_month": str, "time": str})
        frame = frame[frame["ticker"].astype(str).str.upper() == str(ticker).upper()].copy()
        if frame.empty:
            continue
        if "test_month" not in frame:
            frame["test_month"] = frame["month"].astype(str)
        frame["date"] = frame["date"].astype(str)
        frame["time"] = frame["time"].astype(str)
        frame["expiry_mode"] = frame["expiry_mode"].astype(str)
        frame["source_variant"] = name
        frame["source_priority"] = int(source_priority)
        parts.append(frame)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    out["score"] = pd.to_numeric(out["score"], errors="coerce")
    out["minute"] = pd.to_numeric(out["minute"], errors="coerce").fillna(0).astype(int)
    out = out.sort_values(["date", "minute", "source_priority", "score"], ascending=[True, True, True, False])
    out = out.drop_duplicates(["date", "minute", "action"], keep="first").reset_index(drop=True)
    return out


def apply_cooldown(trades: pd.DataFrame, max_day: int, cooldown_minutes: int) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    rows: list[dict] = []
    ordered = trades.sort_values(["date", "minute", "source_priority", "score"], ascending=[True, True, True, False])
    for _, day in ordered.groupby("date", sort=False):
        next_allowed = -1
        taken = 0
        for row in day.itertuples(index=False):
            minute = int(row.minute)
            if minute < next_allowed:
                continue
            if taken >= int(max_day):
                break
            rows.append(row._asdict())
            taken += 1
            next_allowed = minute + int(cooldown_minutes)
    return pd.DataFrame(rows) if rows else trades.iloc[0:0].copy()


def raw_feature_frame(data_path: Path, ticker: str, include_latent_vectors: bool) -> tuple[pd.DataFrame, list[str]]:
    raw = pd.read_parquet(data_path)
    raw = raw[raw["ticker"].astype(str).str.upper() == str(ticker).upper()].copy()
    raw["ticker"] = raw["ticker"].astype(str).str.upper()
    raw["date"] = raw["trade_date"].astype(str)
    raw["time"] = raw["time"].astype(str)
    raw["expiry_mode"] = raw["expiry_mode"].astype(str)
    keys = ["ticker", "date", "time", "expiry_mode"]
    feature_cols: list[str] = []
    for col in raw.columns:
        low = str(col).lower()
        if col in {"trade_date", "date", "expiration", "timestamp", "time", "underlying_ticker", "ticker", "expiry_mode", "nearest_level_name"}:
            continue
        if any(pattern in low for pattern in LEAKY_PATTERNS):
            continue
        if not include_latent_vectors and (
            col.startswith("ptdj_z_")
            or col.startswith("ptdj_dz_")
            or col.startswith("ptdj_phys_")
            or col.startswith("ptdj_phys_delta_")
        ):
            continue
        if pd.api.types.is_numeric_dtype(raw[col]):
            feature_cols.append(col)
    return raw[keys + feature_cols].drop_duplicates(keys, keep="first"), feature_cols


def enrich_features(trades: pd.DataFrame, data_path: Path, ticker: str, include_latent_vectors: bool) -> tuple[pd.DataFrame, list[str]]:
    features, raw_cols = raw_feature_frame(data_path, ticker, include_latent_vectors)
    keys = ["ticker", "date", "time", "expiry_mode"]
    work = trades.copy()
    work["ticker"] = work["ticker"].astype(str).str.upper()
    overlap = [col for col in features.columns if col in work.columns and col not in keys]
    if overlap:
        work = work.drop(columns=overlap)
    work = work.merge(features, on=keys, how="left")
    work["action_is_call"] = (work["action"].astype(str) == "CALL").astype(float)
    for variant in sorted(work["source_variant"].astype(str).unique()):
        work[f"variant_{variant}"] = (work["source_variant"].astype(str) == variant).astype(float)
    work["score_margin"] = (
        pd.to_numeric(work.get("pred_call_return"), errors="coerce")
        - pd.to_numeric(work.get("pred_put_return"), errors="coerce")
    ).abs()
    base_cols = ["score", "pred_call_return", "pred_put_return", "score_margin", "minute", "action_is_call"]
    variant_cols = [c for c in work.columns if c.startswith("variant_")]
    cols: list[str] = []
    for col in dict.fromkeys(base_cols + variant_cols + raw_cols):
        if col in work.columns and pd.api.types.is_numeric_dtype(work[col]):
            finite = pd.to_numeric(work[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
            if finite.notna().sum() >= 50 and finite.nunique(dropna=True) > 1:
                cols.append(col)
    return work, cols


def score_selection(row: dict, args: argparse.Namespace) -> float:
    score = score_metrics(
        row,
        int(args.meta_min_select_trades),
        int(args.meta_min_select_month_trades),
        float(args.meta_min_select_pf),
        float(args.meta_min_select_win_rate),
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


def fit_month_gate(trades: pd.DataFrame, feature_cols: list[str], test_month: str, all_months: list[str], args: argparse.Namespace) -> tuple[pd.DataFrame, dict]:
    previous = [m for m in all_months if m < str(test_month)]
    select_n = int(args.meta_select_months)
    test = trades[trades["test_month"].astype(str) == str(test_month)].copy()
    if len(previous) <= select_n or test.empty:
        test["meta_mode"] = "NO_HISTORY"
        return test, {"month": str(test_month), "meta_mode": "NO_HISTORY", "threshold": float("-inf"), "test_metrics": metrics(test, [str(test_month)])}
    train_months = previous[:-select_n]
    select_months = previous[-select_n:]
    train = trades[trades["test_month"].astype(str).isin(train_months)].copy()
    select = trades[trades["test_month"].astype(str).isin(select_months)].copy()
    if len(train) < int(args.meta_min_train_trades) or len(select) < int(args.meta_min_select_trades):
        test["meta_mode"] = "INSUFFICIENT_META_ROWS"
        return test, {
            "month": str(test_month),
            "meta_mode": "INSUFFICIENT_META_ROWS",
            "threshold": float("-inf"),
            "meta_train_months": ",".join(train_months),
            "meta_select_months": ",".join(select_months),
            "select_metrics": metrics(select, select_months),
            "test_metrics": metrics(test, [str(test_month)]),
        }
    y_train = (pd.to_numeric(train["realized_return"], errors="coerce").fillna(0.0) > 0.0).astype(int)
    if y_train.nunique() < 2:
        test["meta_mode"] = "SINGLE_CLASS_META_TRAIN"
        return test, {
            "month": str(test_month),
            "meta_mode": "SINGLE_CLASS_META_TRAIN",
            "threshold": float("-inf"),
            "meta_train_months": ",".join(train_months),
            "meta_select_months": ",".join(select_months),
            "select_metrics": metrics(select, select_months),
            "test_metrics": metrics(test, [str(test_month)]),
        }
    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    weights = 1.0 + np.minimum(pd.to_numeric(train["realized_return"], errors="coerce").fillna(0.0).abs().to_numpy(), 2.0)
    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=int(args.meta_estimators),
        learning_rate=float(args.meta_learning_rate),
        num_leaves=int(args.meta_num_leaves),
        min_child_samples=int(args.meta_min_child_samples),
        subsample=float(args.meta_subsample),
        colsample_bytree=float(args.meta_colsample_bytree),
        reg_lambda=float(args.meta_reg_lambda),
        random_state=int(args.seed),
        n_jobs=int(args.lgb_jobs),
        verbose=-1,
    )
    model.fit(x_train, y_train, sample_weight=weights)

    def add_score(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        x = out[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
        out["meta_score"] = model.predict_proba(x)[:, 1]
        return out

    scored_select = add_score(select)
    scored_test = add_score(test)
    finite = pd.to_numeric(scored_select["meta_score"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    thresholds = [float("-inf")] + [float(x) for x in args.meta_threshold_grid]
    if len(finite):
        thresholds.extend(float(x) for x in finite.quantile([float(q) for q in args.meta_threshold_quantiles]).to_numpy())
    best = {"score": -1e18, "threshold": float("-inf"), "metrics": metrics(scored_select, select_months)}
    for threshold in sorted(set(round(float(x), 8) for x in thresholds if np.isfinite(float(x)) or x == float("-inf"))):
        filtered = scored_select if threshold == float("-inf") else scored_select[scored_select["meta_score"].astype(float) >= float(threshold)]
        row = metrics(filtered, select_months)
        score = score_selection(row, args)
        if score > float(best["score"]):
            best = {"score": float(score), "threshold": float(threshold), "metrics": row}
    threshold = float(best["threshold"])
    gated = scored_test if threshold == float("-inf") else scored_test[scored_test["meta_score"].astype(float) >= threshold].copy()
    gated["meta_mode"] = "NO_GATE" if threshold == float("-inf") else "META_SCORE"
    gated["meta_threshold"] = threshold
    return gated, {
        "month": str(test_month),
        "meta_mode": "NO_GATE" if threshold == float("-inf") else "META_SCORE",
        "threshold": threshold,
        "meta_train_months": ",".join(train_months),
        "meta_select_months": ",".join(select_months),
        "meta_score": float(best["score"]),
        "feature_count": len(feature_cols),
        "select_metrics": best["metrics"],
        "test_metrics": metrics(gated, [str(test_month)]),
    }


def export_deploy_model(
    output_dir: Path,
    enriched: pd.DataFrame,
    feature_cols: list[str],
    all_months: list[str],
    args: argparse.Namespace,
) -> None:
    deploy_month = str(args.deploy_month).strip()
    if not deploy_month:
        raise RuntimeError("--export-deploy-model requires --deploy-month")
    deploy_select_end_month = str(args.deploy_select_end_month).strip()
    if deploy_select_end_month and deploy_select_end_month >= deploy_month:
        raise RuntimeError(
            f"--deploy-select-end-month {deploy_select_end_month} must be earlier than deploy month {deploy_month}"
        )

    previous = [
        month
        for month in all_months
        if month < deploy_month and (not deploy_select_end_month or month <= deploy_select_end_month)
    ]
    select_n = int(args.meta_select_months)
    if len(previous) <= select_n:
        raise RuntimeError(f"Not enough prior months to export deploy meta gate for {deploy_month}: {previous}")
    train_months = previous[:-select_n]
    select_months = previous[-select_n:]
    train = enriched[enriched["test_month"].astype(str).isin(train_months)].copy()
    select = enriched[enriched["test_month"].astype(str).isin(select_months)].copy()
    if len(train) < int(args.meta_min_train_trades):
        raise RuntimeError(f"Deploy meta train rows {len(train)} < meta_min_train_trades {args.meta_min_train_trades}")
    if len(select) < int(args.meta_min_select_trades):
        raise RuntimeError(f"Deploy meta select rows {len(select)} < meta_min_select_trades {args.meta_min_select_trades}")
    y_train = (pd.to_numeric(train["realized_return"], errors="coerce").fillna(0.0) > 0.0).astype(int)
    if y_train.nunique() < 2:
        raise RuntimeError("Deploy meta train rows have a single realized-return class")

    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    weights = 1.0 + np.minimum(pd.to_numeric(train["realized_return"], errors="coerce").fillna(0.0).abs().to_numpy(), 2.0)
    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=int(args.meta_estimators),
        learning_rate=float(args.meta_learning_rate),
        num_leaves=int(args.meta_num_leaves),
        min_child_samples=int(args.meta_min_child_samples),
        subsample=float(args.meta_subsample),
        colsample_bytree=float(args.meta_colsample_bytree),
        reg_lambda=float(args.meta_reg_lambda),
        random_state=int(args.seed),
        n_jobs=int(args.lgb_jobs),
        verbose=-1,
    )
    model.fit(x_train, y_train, sample_weight=weights)

    scored_select = select.copy()
    x_select = scored_select[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    scored_select["meta_score"] = model.predict_proba(x_select)[:, 1]
    finite = pd.to_numeric(scored_select["meta_score"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    thresholds = [float("-inf")] + [float(x) for x in args.meta_threshold_grid]
    if len(finite):
        thresholds.extend(float(x) for x in finite.quantile([float(q) for q in args.meta_threshold_quantiles]).to_numpy())

    best = {"score": -1e18, "threshold": float("-inf"), "metrics": metrics(scored_select, select_months)}
    for threshold in sorted(set(round(float(x), 8) for x in thresholds if np.isfinite(float(x)) or x == float("-inf"))):
        filtered = scored_select if threshold == float("-inf") else scored_select[scored_select["meta_score"].astype(float) >= float(threshold)]
        row = metrics(filtered, select_months)
        score = score_selection(row, args)
        if score > float(best["score"]):
            best = {"score": float(score), "threshold": float(threshold), "metrics": row}

    select_score = float(best["score"])
    if select_score <= -1e17 and not bool(args.allow_invalid_deploy_selection):
        raise RuntimeError(
            "Deploy meta-gate selection failed validation for "
            f"{deploy_month} using select_months={select_months}; "
            "pass --allow-invalid-deploy-selection only for diagnostics."
        )
    selected_sources = (
        sorted(enriched["source_variant"].astype(str).dropna().unique().tolist())
        if "source_variant" in enriched.columns
        else []
    )
    threshold = float(best["threshold"])
    payload = {
        "schema_version": 1,
        "component": "event_trade_union_meta_gate",
        "ticker": str(args.ticker).upper(),
        "deploy_month": deploy_month,
        "deploy_select_end_month": deploy_select_end_month or None,
        "train_months": train_months,
        "select_months": select_months,
        "selected_threshold": None if not np.isfinite(threshold) else float(threshold),
        "select_score": select_score,
        "select_metrics": best["metrics"],
        "feature_cols": feature_cols,
        "feature_medians": {str(k): float(v) if np.isfinite(float(v)) else 0.0 for k, v in medians.fillna(0.0).items()},
        "source_variants": selected_sources,
        "args": vars(args),
    }
    deploy_dir = output_dir / "deploy_model"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    with (deploy_dir / "meta_gate_model.pkl").open("wb") as fh:
        pickle.dump({"model": model, "medians": medians, "feature_cols": feature_cols, "metadata": payload}, fh)
    (deploy_dir / "meta_gate_model.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    selected = scored_select if threshold == float("-inf") else scored_select[scored_select["meta_score"].astype(float) >= threshold].copy()
    if not selected.empty:
        selected.to_csv(deploy_dir / "deploy_select_scored_trades.csv", index=False)


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
    axes[0].plot(daily.index, daily.cumsum(), color="#111827", linewidth=2.4)
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Trade Union Meta Gate Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(daily.index, daily.values, color=np.where(daily >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "trade_union_meta_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def flatten(prefix: str, row: dict) -> dict:
    return {f"{prefix}_{k}": v for k, v in row.items()}


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, args: argparse.Namespace) -> None:
    expected = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, expected)
    risk_capital = float(args.risk_capital)
    payload = {
        "overall": overall,
        "net_pnl": float(overall["pnl_return"]) * risk_capital,
        "risk_capital": risk_capital,
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Trade Union Meta Gate",
        "",
        "This result combines precomputed causal trade streams, applies a deterministic cooldown/max-day rule, then trains a meta-gate for each test month using only earlier out-of-sample months.",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        f"- Risk capital: ${risk_capital:,.0f}",
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a causal meta-gate to a union of precomputed event-option trade streams.")
    parser.add_argument("--trade-source", action="append", required=True, help="NAME=folder_or_event_option_gate_trades.csv. Repeatable; order defines priority.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--history-start-month", default="202507")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--max-day", type=int, default=8)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--include-latent-vectors", action="store_true")
    parser.add_argument("--meta-select-months", type=int, default=1)
    parser.add_argument("--meta-min-train-trades", type=int, default=80)
    parser.add_argument("--meta-min-select-trades", type=int, default=18)
    parser.add_argument("--meta-min-select-month-trades", type=int, default=18)
    parser.add_argument("--meta-min-select-pf", type=float, default=1.0)
    parser.add_argument("--meta-min-select-win-rate", type=float, default=0.40)
    parser.add_argument("--min-call-rate", type=float, default=0.15)
    parser.add_argument("--max-call-rate", type=float, default=0.85)
    parser.add_argument("--daily-win-weight", type=float, default=0.50)
    parser.add_argument("--top5-share-penalty", type=float, default=0.25)
    parser.add_argument("--meta-estimators", type=int, default=120)
    parser.add_argument("--meta-learning-rate", type=float, default=0.04)
    parser.add_argument("--meta-num-leaves", type=int, default=7)
    parser.add_argument("--meta-min-child-samples", type=int, default=18)
    parser.add_argument("--meta-subsample", type=float, default=0.85)
    parser.add_argument("--meta-colsample-bytree", type=float, default=0.75)
    parser.add_argument("--meta-reg-lambda", type=float, default=8.0)
    parser.add_argument("--meta-threshold-grid", nargs="+", type=float, default=[0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75])
    parser.add_argument("--meta-threshold-quantiles", nargs="+", type=float, default=[0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90])
    parser.add_argument("--lgb-jobs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260618)
    parser.add_argument("--deploy-month", default="")
    parser.add_argument(
        "--deploy-select-end-month",
        default="",
        help="Optional latest completed YYYYMM allowed for deploy meta selection. Use this to exclude partial months.",
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
        gated, fold = fit_month_gate(enriched, feature_cols, str(month), all_months, args)
        if not gated.empty:
            out_parts.append(gated)
        row = {
            "ticker": str(args.ticker).upper(),
            "month": str(month),
            "meta_mode": fold.get("meta_mode", ""),
            "threshold": fold.get("threshold", float("nan")),
            "meta_train_months": fold.get("meta_train_months", ""),
            "meta_select_months": fold.get("meta_select_months", ""),
            "meta_score": fold.get("meta_score", float("nan")),
            "feature_count": fold.get("feature_count", len(feature_cols)),
        }
        row.update(flatten("select", fold.get("select_metrics", metrics(pd.DataFrame(), []))))
        row.update(flatten("test", fold.get("test_metrics", metrics(pd.DataFrame(), [str(month)]))))
        fold_rows.append(row)
    trades = pd.concat(out_parts, ignore_index=True) if out_parts else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    if not trades.empty:
        trades.to_csv(output_dir / "trade_union_meta_trades.csv", index=False)
    folds.to_csv(output_dir / "trade_union_meta_folds.csv", index=False)
    if bool(args.export_deploy_model):
        export_deploy_model(output_dir, enriched, feature_cols, all_months, args)
    write_plot(output_dir, trades, float(args.risk_capital))
    write_summary(output_dir, trades, folds, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
