from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import LEAKY_PATTERNS, metrics, score_metrics
from walkforward_event_option_profile_selector import prepare_profile, load_raw
from apply_event_profile_regime_gate import fit_and_score_fold, profile_from_row


GROUP_PREFIXES = {
    "core": (
        "score",
        "score_margin",
        "minute",
        "dte_days",
        "ib_range_bps",
        "nearest_level_abs_bps",
        "ret_",
        "dist_ib_",
        "dist_fib_",
        "action_",
    ),
    "physics": ("phys_", "ctx_", "ret_", "dist_", "ib_range_bps", "nearest_level_abs_bps"),
    "ptdj_state": ("ptdj_z_", "ptdj_dz_", "ptdj_latent_", "ptdj_input_", "ptdj_motion_", "ptdj_pred_", "ptdj_lagged_"),
    "ptdj_phys": ("ptdj_phys_", "ptdj_phys_delta_", "ptdj_context_valid", "ptdj_phys_transition_"),
}


EXCLUDE_PATTERNS = tuple(LEAKY_PATTERNS) + (
    "_return",
    "realized_return",
    "call_return",
    "put_return",
    "opt_",
    "future",
    "status",
    "win",
)


def usable_numeric_columns(df: pd.DataFrame, group: str, max_features: int) -> list[str]:
    prefixes = GROUP_PREFIXES[group]
    cols: list[str] = []
    for col in df.columns:
        low = str(col).lower()
        if any(p in low for p in EXCLUDE_PATTERNS):
            continue
        if not any(str(col).startswith(prefix) or str(col) == prefix for prefix in prefixes):
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            cols.append(str(col))
    if not cols:
        return []
    work = df[cols].replace([np.inf, -np.inf], np.nan)
    mad = (work - work.median(numeric_only=True)).abs().median(numeric_only=True).fillna(0.0)
    ranked = sorted(cols, key=lambda c: (float(mad.get(c, 0.0)), c), reverse=True)
    return ranked[: int(max_features)]


def robust_matrix(df: pd.DataFrame, cols: list[str], med: pd.Series, scale: pd.Series) -> np.ndarray:
    if not cols:
        return np.zeros((len(df), 0), dtype=np.float32)
    x = df[cols].replace([np.inf, -np.inf], np.nan).fillna(med).fillna(0.0)
    arr = ((x - med) / scale).to_numpy(dtype=np.float32, copy=False)
    return np.clip(arr, -10.0, 10.0)


def nearest_mean_distance(ref: np.ndarray, x: np.ndarray, k: int) -> np.ndarray:
    if ref.size == 0 or x.size == 0:
        return np.full(len(x), np.nan, dtype=np.float32)
    k = max(1, min(int(k), len(ref)))
    out = np.empty(len(x), dtype=np.float32)
    for i in range(len(x)):
        diff = ref - x[i]
        dist = np.sqrt(np.mean(diff * diff, axis=1))
        if k == 1:
            out[i] = float(np.min(dist))
        else:
            out[i] = float(np.partition(dist, k - 1)[:k].mean())
    return out


def add_ood_scores(ref: pd.DataFrame, target: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, dict]:
    out = target.copy()
    detail: dict[str, dict] = {}
    for group in GROUP_PREFIXES:
        cols = usable_numeric_columns(ref, group, int(args.max_ood_features))
        if not cols:
            continue
        ref_work = ref[cols].replace([np.inf, -np.inf], np.nan)
        med = ref_work.median(numeric_only=True).fillna(0.0)
        q75 = ref_work.quantile(0.75, numeric_only=True)
        q25 = ref_work.quantile(0.25, numeric_only=True)
        scale = (q75 - q25).replace(0.0, np.nan).fillna(ref_work.std(numeric_only=True)).replace(0.0, np.nan).fillna(1.0)
        ref_z = robust_matrix(ref, cols, med, scale)
        tgt_z = robust_matrix(target, cols, med, scale)
        abs_z = np.abs(tgt_z)
        out[f"ood_{group}_mean_abs_z"] = abs_z.mean(axis=1) if abs_z.size else np.nan
        out[f"ood_{group}_p90_abs_z"] = np.quantile(abs_z, 0.90, axis=1) if abs_z.size else np.nan
        out[f"ood_{group}_max_abs_z"] = abs_z.max(axis=1) if abs_z.size else np.nan
        out[f"ood_{group}_knn"] = nearest_mean_distance(ref_z, tgt_z, int(args.knn_k))
        detail[group] = {"feature_count": len(cols), "features": cols}
    return out, detail


def choose_ood_gate(scored_select: pd.DataFrame, select_months: list[str], args: argparse.Namespace) -> dict:
    none_metrics = metrics(scored_select, select_months)
    best = {
        "feature": "NONE",
        "threshold": float("inf"),
        "direction": "none",
        "score": score_metrics(
            none_metrics,
            int(args.ood_min_select_trades),
            int(args.ood_min_select_month_trades),
            float(args.ood_min_select_pf),
            float(args.ood_min_select_win_rate),
            float(args.min_call_rate),
            float(args.max_call_rate),
        ),
        "metrics": none_metrics,
    }
    ood_cols = [c for c in scored_select.columns if str(c).startswith("ood_")]
    quantiles = [float(q) for q in args.ood_quantiles]
    for feature in ood_cols:
        values = pd.to_numeric(scored_select[feature], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if values.nunique() < 4:
            continue
        thresholds = sorted(set(float(values.quantile(q)) for q in quantiles if 0.0 <= q <= 1.0))
        for threshold in thresholds:
            for direction in ("lte", "gte") if bool(args.allow_high_ood_gate) else ("lte",):
                if direction == "lte":
                    filtered = scored_select[pd.to_numeric(scored_select[feature], errors="coerce") <= threshold].copy()
                else:
                    filtered = scored_select[pd.to_numeric(scored_select[feature], errors="coerce") >= threshold].copy()
                row = metrics(filtered, select_months)
                score = score_metrics(
                    row,
                    int(args.ood_min_select_trades),
                    int(args.ood_min_select_month_trades),
                    float(args.ood_min_select_pf),
                    float(args.ood_min_select_win_rate),
                    float(args.min_call_rate),
                    float(args.max_call_rate),
                )
                if np.isfinite(float(row.get("daily_win_rate", float("nan")))):
                    score += float(args.daily_win_weight) * float(row["daily_win_rate"])
                if np.isfinite(float(row.get("top5_share_of_pnl", float("nan")))):
                    score -= float(args.top5_share_penalty) * max(float(row["top5_share_of_pnl"]) - 1.0, 0.0)
                if float(score) > float(best["score"]):
                    best = {
                        "feature": feature,
                        "threshold": float(threshold),
                        "direction": direction,
                        "score": float(score),
                        "metrics": row,
                    }
    return best


def apply_gate(df: pd.DataFrame, gate: dict) -> pd.DataFrame:
    if df.empty or str(gate.get("feature")) == "NONE":
        out = df.copy()
    else:
        feature = str(gate["feature"])
        threshold = float(gate["threshold"])
        values = pd.to_numeric(df[feature], errors="coerce")
        if str(gate.get("direction")) == "gte":
            out = df[values >= threshold].copy()
        else:
            out = df[values <= threshold].copy()
    out["ood_gate_feature"] = str(gate.get("feature", "NONE"))
    out["ood_gate_threshold"] = float(gate.get("threshold", float("nan")))
    out["ood_gate_direction"] = str(gate.get("direction", "none"))
    return out


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
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Selected Event Profiles + OOD Gate, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].grid(True, alpha=0.25)
    colors = np.where(daily >= 0.0, "#16a34a", "#dc2626")
    axes[1].bar(daily.index, daily.values, color=colors, width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "ood_gate_daily_net_pnl.png", dpi=160)
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
        "# Event Profile OOD Gate",
        "",
        "For each selected profile fold, the base option model/profile/threshold are fixed from prior validation. This script fits unsupervised OOD scores on early validation trades, selects an OOD threshold only on later validation trades, then applies it to the test month.",
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
    parser = argparse.ArgumentParser(description="Apply causal validation-only OOD gates to selected event profile folds.")
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
    parser.add_argument("--ood-select-months", type=int, default=1)
    parser.add_argument("--ood-min-ref-trades", type=int, default=25)
    parser.add_argument("--ood-min-select-trades", type=int, default=10)
    parser.add_argument("--ood-min-select-month-trades", type=int, default=8)
    parser.add_argument("--ood-min-select-pf", type=float, default=1.05)
    parser.add_argument("--ood-min-select-win-rate", type=float, default=0.40)
    parser.add_argument("--ood-quantiles", nargs="+", type=float, default=[0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90])
    parser.add_argument("--allow-high-ood-gate", action="store_true")
    parser.add_argument("--max-ood-features", type=int, default=48)
    parser.add_argument("--knn-k", type=int, default=5)
    parser.add_argument("--min-call-rate", type=float, default=0.15)
    parser.add_argument("--max-call-rate", type=float, default=0.85)
    parser.add_argument("--daily-win-weight", type=float, default=0.25)
    parser.add_argument("--top5-share-penalty", type=float, default=0.10)
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
    feature_details: dict[str, dict] = {}

    for _, row in selected.iterrows():
        profile = profile_from_row(row)
        if profile.name not in prepared_cache:
            prepared_cache[profile.name] = prepare_profile(raw, profile, float(args.clip_return))
        val_trades, test_trades = fit_and_score_fold(prepared_cache[profile.name], row, args)
        val_months = [part for part in str(row["val_months"]).split(",") if part]
        select_n = max(1, min(int(args.ood_select_months), len(val_months) - 1))
        ref_months = val_months[:-select_n]
        select_months = val_months[-select_n:]
        ref = val_trades[val_trades["month"].astype(str).isin(ref_months)].copy()
        select = val_trades[val_trades["month"].astype(str).isin(select_months)].copy()
        if len(ref) < int(args.ood_min_ref_trades) or select.empty:
            gate = {"feature": "NONE", "threshold": float("inf"), "direction": "none", "score": -1e18, "metrics": metrics(select, select_months)}
            gated_test = apply_gate(test_trades, gate)
            details = {}
        else:
            scored_select, details = add_ood_scores(ref, select, args)
            scored_test, _ = add_ood_scores(ref, test_trades, args)
            gate = choose_ood_gate(scored_select, select_months, args)
            gated_test = apply_gate(scored_test, gate)
        feature_details[f"{row['ticker']}_{row['month']}_{profile.name}"] = details
        test_metrics = metrics(gated_test, [str(row["month"])])
        if not gated_test.empty:
            all_trades.append(gated_test)
        fold = {
            "ticker": str(row["ticker"]),
            "month": str(row["month"]),
            "profile": profile.name,
            "deploy_config": str(row["deploy_config"]),
            "val_months": str(row["val_months"]),
            "ref_months": ",".join(ref_months),
            "select_months": ",".join(select_months),
            "ood_feature": str(gate["feature"]),
            "ood_threshold": float(gate["threshold"]),
            "ood_direction": str(gate["direction"]),
            "ood_score": float(gate["score"]),
            **{f"ood_select_{k}": v for k, v in dict(gate["metrics"]).items()},
            **{f"test_{k}": v for k, v in test_metrics.items()},
        }
        fold_rows.append(fold)
        print(
            f"[OOD_GATE] {fold['ticker']} {fold['month']} profile={profile.name} "
            f"feature={fold['ood_feature']} dir={fold['ood_direction']} "
            f"thr={fold['ood_threshold']:.3f} test_trades={fold['test_trades']} "
            f"test_pf={fold['test_profit_factor']:.3f} test_ret={fold['test_pnl_return']:.2f}",
            flush=True,
        )

    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    if not trades.empty:
        trades.to_csv(output_dir / "ood_gate_trades.csv", index=False)
        write_plot(output_dir, trades, float(args.risk_capital))
    folds.to_csv(output_dir / "ood_gate_folds.csv", index=False)
    metadata = {
        "args": vars(args),
        "selected_folds_rows": int(len(selected)),
        "profiles": sorted(prepared_cache.keys()),
        "feature_details": feature_details,
    }
    write_summary(output_dir, trades, folds, metadata)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
