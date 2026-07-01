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
from walkforward_event_option_profile_selector import prepare_profile, load_raw
from apply_event_profile_regime_gate import (
    BASE_REGIME_FEATURES,
    fit_and_score_fold,
    profile_from_row,
    parse_train_tickers,
)


META_EXTRA_FEATURES = [
    "action_is_call",
    "abs_ret_1m_bps",
    "abs_ret_5m_bps",
    "abs_ret_15m_bps",
    "abs_ret_30m_bps",
    "fib_up_min_abs_bps",
    "fib_dn_min_abs_bps",
    "ib_edge_min_abs_bps",
]


def enrich_meta_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["action_is_call"] = (out["action"].astype(str) == "CALL").astype(float)
    for col in ["ret_1m_bps", "ret_5m_bps", "ret_15m_bps", "ret_30m_bps"]:
        if col in out:
            out[f"abs_{col}"] = pd.to_numeric(out[col], errors="coerce").abs()
    up_cols = [c for c in ["dist_fib_127_up_bps", "dist_fib_161_up_bps", "dist_fib_200_up_bps"] if c in out]
    dn_cols = [c for c in ["dist_fib_127_dn_bps", "dist_fib_161_dn_bps", "dist_fib_200_dn_bps"] if c in out]
    ib_cols = [c for c in ["dist_ib_high_bps", "dist_ib_low_bps"] if c in out]
    if up_cols:
        out["fib_up_min_abs_bps"] = out[up_cols].apply(pd.to_numeric, errors="coerce").abs().min(axis=1)
    if dn_cols:
        out["fib_dn_min_abs_bps"] = out[dn_cols].apply(pd.to_numeric, errors="coerce").abs().min(axis=1)
    if ib_cols:
        out["ib_edge_min_abs_bps"] = out[ib_cols].apply(pd.to_numeric, errors="coerce").abs().min(axis=1)
    return out


def meta_feature_cols(df: pd.DataFrame) -> list[str]:
    candidates = list(dict.fromkeys(BASE_REGIME_FEATURES + META_EXTRA_FEATURES))
    cols = []
    for col in candidates:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            cols.append(col)
    return cols


def choose_threshold(scored_select: pd.DataFrame, select_months: list[str], args: argparse.Namespace) -> dict:
    none_metrics = metrics(scored_select, select_months)
    best = {
        "threshold": float("-inf"),
        "score": score_metrics(
            none_metrics,
            int(args.meta_min_select_trades),
            int(args.meta_min_select_month_trades),
            float(args.meta_min_select_pf),
            float(args.meta_min_select_win_rate),
            float(args.min_call_rate),
            float(args.max_call_rate),
        ),
        "metrics": none_metrics,
        "mode": "NO_GATE",
    }
    scores = pd.to_numeric(scored_select["meta_score"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    thresholds = [float(v) for v in args.meta_threshold_grid]
    if len(scores):
        thresholds.extend(float(scores.quantile(q)) for q in args.meta_threshold_quantiles)
    thresholds = sorted(set(round(v, 8) for v in thresholds if np.isfinite(v)))
    for threshold in thresholds:
        filtered = scored_select[scored_select["meta_score"].astype(float) >= float(threshold)].copy()
        row = metrics(filtered, select_months)
        score = score_metrics(
            row,
            int(args.meta_min_select_trades),
            int(args.meta_min_select_month_trades),
            float(args.meta_min_select_pf),
            float(args.meta_min_select_win_rate),
            float(args.min_call_rate),
            float(args.max_call_rate),
        )
        if np.isfinite(float(row.get("daily_win_rate", float("nan")))):
            score += float(args.daily_win_weight) * float(row["daily_win_rate"])
        if score > float(best["score"]):
            best = {
                "threshold": float(threshold),
                "score": float(score),
                "metrics": row,
                "mode": "META_SCORE",
            }
    return best


def fit_meta_gate(val_trades: pd.DataFrame, test_trades: pd.DataFrame, val_months: list[str], args: argparse.Namespace) -> tuple[pd.DataFrame, dict]:
    if val_trades.empty or test_trades.empty:
        empty_metrics = metrics(pd.DataFrame(), [])
        return test_trades.iloc[0:0].copy(), {"mode": "EMPTY", "threshold": float("nan"), "score": -1e18, "metrics": empty_metrics}
    select_n = max(1, min(int(args.meta_select_months), len(val_months) - 1))
    train_months = val_months[:-select_n]
    select_months = val_months[-select_n:]
    val_work = enrich_meta_features(val_trades)
    test_work = enrich_meta_features(test_trades)
    meta_train = val_work[val_work["month"].astype(str).isin(train_months)].copy()
    meta_select = val_work[val_work["month"].astype(str).isin(select_months)].copy()
    if len(meta_train) < int(args.meta_min_train_trades) or len(meta_select) < int(args.meta_min_select_trades):
        no_gate = test_work.copy()
        no_gate["meta_gate_mode"] = "INSUFFICIENT_META_ROWS"
        return no_gate, {
            "mode": "INSUFFICIENT_META_ROWS",
            "threshold": float("-inf"),
            "score": -1e18,
            "metrics": metrics(meta_select, select_months),
            "meta_train_months": ",".join(train_months),
            "meta_select_months": ",".join(select_months),
            "feature_count": 0,
        }
    y_train = (meta_train["realized_return"].astype(float) > 0.0).astype(int)
    if y_train.nunique() < 2:
        no_gate = test_work.copy()
        no_gate["meta_gate_mode"] = "SINGLE_CLASS_META_TRAIN"
        return no_gate, {
            "mode": "SINGLE_CLASS_META_TRAIN",
            "threshold": float("-inf"),
            "score": -1e18,
            "metrics": metrics(meta_select, select_months),
            "meta_train_months": ",".join(train_months),
            "meta_select_months": ",".join(select_months),
            "feature_count": 0,
        }
    cols = meta_feature_cols(meta_train)
    medians = meta_train[cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = meta_train[cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    weights = 1.0 + np.minimum(meta_train["realized_return"].astype(float).abs().to_numpy(), 2.0)
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

    def score(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        x = out[cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
        out["meta_score"] = model.predict_proba(x)[:, 1]
        return out

    scored_select = score(meta_select)
    scored_test = score(test_work)
    gate = choose_threshold(scored_select, select_months, args)
    if gate["mode"] == "META_SCORE":
        gated_test = scored_test[scored_test["meta_score"].astype(float) >= float(gate["threshold"])].copy()
    else:
        gated_test = scored_test.copy()
    gated_test["meta_gate_mode"] = str(gate["mode"])
    gated_test["meta_gate_threshold"] = float(gate["threshold"])
    gate.update(
        {
            "meta_train_months": ",".join(train_months),
            "meta_select_months": ",".join(select_months),
            "feature_count": len(cols),
            "features": cols,
        }
    )
    return gated_test, gate


def write_plot(output_dir: Path, trades: pd.DataFrame, risk_capital: float) -> None:
    if trades.empty:
        return
    work = trades.copy()
    work["dt"] = pd.to_datetime(work["date"].astype(str), format="%Y%m%d", errors="coerce")
    work["pnl"] = work["realized_return"].astype(float) * float(risk_capital)
    daily = work.groupby("dt")["pnl"].sum().sort_index()
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    daily = daily.reindex(idx).fillna(0.0)
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(daily.index, daily.cumsum(), color="#111827", linewidth=2.4, label="TOTAL")
    for ticker, part in work.groupby("ticker"):
        curve = part.groupby("dt")["pnl"].sum().sort_index().reindex(idx).fillna(0.0).cumsum()
        axes[0].plot(curve.index, curve.values, linewidth=1.6, label=str(ticker))
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Selected Event Profiles + Meta Gate, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.25)
    colors = np.where(daily >= 0.0, "#16a34a", "#dc2626")
    axes[1].bar(daily.index, daily.values, color=colors, width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "meta_gate_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, metadata: dict) -> None:
    expected = month_range(str(metadata["args"]["start_month"]), str(metadata["args"]["end_month"]))
    overall = metrics(trades, expected)
    per_ticker = {
        str(ticker): metrics(part, expected)
        for ticker, part in trades.groupby("ticker", sort=True)
    } if not trades.empty else {}
    payload = {"overall": overall, "per_ticker": per_ticker, "metadata": metadata}
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Profile Meta Gate",
        "",
        "For each selected profile fold, the base option model/profile/threshold are fixed from prior validation. This script trains a multivariate meta-gate on early validation trades, selects the meta threshold on later validation trades, then applies it to the test month.",
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
        "## Folds",
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a causal multivariate meta-gate to selected event profile folds.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--selected-folds", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--clip-return", type=float, default=2.0)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--objective", default="regression_l1")
    parser.add_argument("--n-estimators", type=int, default=220)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=31)
    parser.add_argument("--min-child-samples", type=int, default=80)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.85)
    parser.add_argument("--reg-lambda", type=float, default=5.0)
    parser.add_argument("--lgb-jobs", type=int, default=8)
    parser.add_argument("--meta-select-months", type=int, default=1)
    parser.add_argument("--meta-min-train-trades", type=int, default=40)
    parser.add_argument("--meta-min-select-trades", type=int, default=12)
    parser.add_argument("--meta-min-select-month-trades", type=int, default=8)
    parser.add_argument("--meta-min-select-pf", type=float, default=1.05)
    parser.add_argument("--meta-min-select-win-rate", type=float, default=0.40)
    parser.add_argument("--meta-threshold-grid", nargs="+", type=float, default=[0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65])
    parser.add_argument("--meta-threshold-quantiles", nargs="+", type=float, default=[0.40, 0.50, 0.60, 0.70, 0.80, 0.90])
    parser.add_argument("--meta-estimators", type=int, default=80)
    parser.add_argument("--meta-learning-rate", type=float, default=0.05)
    parser.add_argument("--meta-num-leaves", type=int, default=7)
    parser.add_argument("--meta-min-child-samples", type=int, default=12)
    parser.add_argument("--meta-subsample", type=float, default=0.90)
    parser.add_argument("--meta-colsample-bytree", type=float, default=0.90)
    parser.add_argument("--meta-reg-lambda", type=float, default=10.0)
    parser.add_argument("--min-call-rate", type=float, default=0.15)
    parser.add_argument("--max-call-rate", type=float, default=0.85)
    parser.add_argument("--daily-win-weight", type=float, default=0.25)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--seed", type=int, default=20260618)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = pd.read_csv(args.selected_folds)
    selected = selected[(selected["month"].astype(str) >= str(args.start_month)) & (selected["month"].astype(str) <= str(args.end_month))].copy()
    all_tickers = sorted({t for raw in selected["train_tickers"].astype(str) for t in raw.split(",") if t} | set(selected["ticker"].astype(str)))
    raw = load_raw(args.data, all_tickers)
    prepared_cache: dict[str, object] = {}
    all_trades: list[pd.DataFrame] = []
    fold_rows: list[dict] = []

    for _, row in selected.iterrows():
        profile = profile_from_row(row)
        if profile.name not in prepared_cache:
            prepared_cache[profile.name] = prepare_profile(raw, profile, float(args.clip_return))
        val_trades, test_trades = fit_and_score_fold(prepared_cache[profile.name], row, args)
        val_months = [part for part in str(row["val_months"]).split(",") if part]
        gated_test, gate = fit_meta_gate(val_trades, test_trades, val_months, args)
        test_metrics = metrics(gated_test, [str(row["month"])])
        if not gated_test.empty:
            all_trades.append(gated_test)
        fold = {
            "ticker": str(row["ticker"]),
            "month": str(row["month"]),
            "profile": profile.name,
            "deploy_config": str(row["deploy_config"]),
            "val_months": str(row["val_months"]),
            "meta_mode": str(gate["mode"]),
            "meta_threshold": float(gate["threshold"]),
            "meta_score": float(gate["score"]),
            "meta_train_months": str(gate.get("meta_train_months", "")),
            "meta_select_months": str(gate.get("meta_select_months", "")),
            "meta_feature_count": int(gate.get("feature_count", 0)),
            **{f"meta_select_{k}": v for k, v in dict(gate["metrics"]).items()},
            **{f"test_{k}": v for k, v in test_metrics.items()},
        }
        fold_rows.append(fold)
        print(
            f"[META_GATE] {fold['ticker']} {fold['month']} profile={profile.name} "
            f"mode={fold['meta_mode']} thr={fold['meta_threshold']:.3f} "
            f"test_trades={fold['test_trades']} test_pf={fold['test_profit_factor']:.3f} "
            f"test_ret={fold['test_pnl_return']:.2f}",
            flush=True,
        )

    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    if not trades.empty:
        trades.to_csv(output_dir / "meta_gate_trades.csv", index=False)
        write_plot(output_dir, trades, float(args.risk_capital))
    folds.to_csv(output_dir / "meta_gate_folds.csv", index=False)
    metadata = {"args": vars(args), "selected_folds_rows": int(len(selected)), "profiles": sorted(prepared_cache.keys())}
    write_summary(output_dir, trades, folds, metadata)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
