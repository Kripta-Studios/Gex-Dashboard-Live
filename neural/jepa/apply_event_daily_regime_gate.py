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


def load_trades(path: Path) -> pd.DataFrame:
    trades = pd.read_csv(path, dtype={"date": str, "month": str, "test_month": str, "time": str})
    trades["ticker"] = trades["ticker"].astype(str).str.upper()
    if "test_month" not in trades:
        trades["test_month"] = trades["month"].astype(str)
    trades["test_month"] = trades["test_month"].astype(str)
    trades["date"] = trades["date"].astype(str)
    trades["time"] = trades["time"].astype(str)
    trades["expiry_mode"] = trades["expiry_mode"].astype(str)
    trades["minute"] = pd.to_numeric(trades["minute"], errors="coerce").fillna(0).astype(int)
    trades["realized_return"] = pd.to_numeric(trades["realized_return"], errors="coerce").fillna(0.0)
    return trades


def load_features(data_path: Path, include_ptdj_scalars: bool) -> tuple[pd.DataFrame, list[str]]:
    raw = pd.read_parquet(data_path)
    raw["ticker"] = raw["ticker"].astype(str).str.upper()
    raw["date"] = raw["trade_date"].astype(str)
    raw["time"] = raw["time"].astype(str)
    raw["expiry_mode"] = raw["expiry_mode"].astype(str)
    keys = ["ticker", "date", "time", "expiry_mode"]
    cols: list[str] = []
    for col in raw.columns:
        low = str(col).lower()
        if col in {"trade_date", "date", "expiration", "timestamp", "time", "underlying_ticker", "ticker", "expiry_mode", "nearest_level_name"}:
            continue
        if any(pattern in low for pattern in LEAKY_PATTERNS):
            continue
        if col.startswith("ptdj_z_") or col.startswith("ptdj_dz_") or col.startswith("ptdj_phys_") or col.startswith("ptdj_phys_delta_"):
            continue
        if col.startswith("ptdj_") and not include_ptdj_scalars:
            continue
        if pd.api.types.is_numeric_dtype(raw[col]):
            cols.append(col)
    return raw[keys + cols].drop_duplicates(keys, keep="first"), cols


def build_day_rows(trades: pd.DataFrame, features: pd.DataFrame, feature_cols: list[str]) -> tuple[pd.DataFrame, list[str]]:
    ordered = trades.sort_values(["ticker", "date", "minute"], kind="stable")
    first = ordered.groupby(["ticker", "date"], sort=False).head(1).copy()
    keys = ["ticker", "date", "time", "expiry_mode"]
    overlap = [c for c in features.columns if c in first.columns and c not in keys]
    if overlap:
        first = first.drop(columns=overlap)
    first = first.merge(features, on=keys, how="left")
    daily = trades.groupby(["ticker", "date", "test_month"], as_index=False).agg(
        day_return=("realized_return", "sum"),
        day_trades=("realized_return", "size"),
        day_call_rate=("action", lambda s: float((s.astype(str) == "CALL").mean())),
    )
    first = first.merge(daily, on=["ticker", "date", "test_month"], how="left")
    first["first_action_is_call"] = (first["action"].astype(str) == "CALL").astype(float)
    first["first_score_margin"] = (
        pd.to_numeric(first.get("pred_call_return"), errors="coerce")
        - pd.to_numeric(first.get("pred_put_return"), errors="coerce")
    ).abs()
    first["weekday"] = pd.to_datetime(first["date"], format="%Y%m%d", errors="coerce").dt.weekday.astype(float)
    base_cols = [
        "minute",
        "score",
        "pred_call_return",
        "pred_put_return",
        "first_score_margin",
        "first_action_is_call",
        "weekday",
    ]
    cols: list[str] = []
    for col in dict.fromkeys(base_cols + feature_cols):
        if col in first.columns and pd.api.types.is_numeric_dtype(first[col]):
            finite = pd.to_numeric(first[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
            if finite.notna().sum() >= 20 and finite.nunique(dropna=True) > 1:
                cols.append(col)
    return first, cols


def select_threshold(scored: pd.DataFrame, select_months: list[str], args: argparse.Namespace) -> dict:
    best = {
        "threshold": float("-inf"),
        "score": score_metrics(
            metrics(pd.DataFrame(), select_months),
            int(args.min_select_trades),
            int(args.min_select_month_trades),
            float(args.min_select_pf),
            float(args.min_select_win_rate),
            float(args.min_call_rate),
            float(args.max_call_rate),
        ),
        "passed": False,
        "metrics": metrics(pd.DataFrame(), select_months),
    }
    thresholds = [float("-inf")] + [float(x) for x in args.threshold_grid]
    finite = pd.to_numeric(scored["day_score"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(finite):
        thresholds.extend(float(x) for x in finite.quantile([float(q) for q in args.threshold_quantiles]).to_numpy())
    for threshold in sorted(set(round(float(x), 8) for x in thresholds if np.isfinite(float(x)) or x == float("-inf"))):
        kept_days = scored if threshold == float("-inf") else scored[scored["day_score"].astype(float) >= float(threshold)]
        trades = kept_days.attrs.get("trades")
        if trades is None:
            raise RuntimeError("Missing trades attr")
        kept = trades.merge(kept_days[["ticker", "date"]], on=["ticker", "date"], how="inner")
        row = metrics(kept, select_months)
        score = score_metrics(
            row,
            int(args.min_select_trades),
            int(args.min_select_month_trades),
            float(args.min_select_pf),
            float(args.min_select_win_rate),
            float(args.min_call_rate),
            float(args.max_call_rate),
        )
        passed = bool(score > -1e17)
        if np.isfinite(float(row.get("daily_win_rate", float("nan")))):
            score += float(args.daily_win_weight) * float(row["daily_win_rate"])
        if np.isfinite(float(row.get("top5_share_of_pnl", float("nan")))):
            score -= float(args.top5_share_penalty) * max(float(row["top5_share_of_pnl"]) - 1.0, 0.0)
        if score > float(best["score"]):
            best = {"threshold": float(threshold), "score": float(score), "passed": passed, "metrics": row}
    return best


def apply_gate(trades: pd.DataFrame, day_rows: pd.DataFrame, feature_cols: list[str], args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    out_parts: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    all_months = sorted(day_rows["test_month"].astype(str).unique())
    months = month_range(str(args.start_month), str(args.end_month))
    for ticker in [str(t).upper() for t in args.tickers]:
        tdays = day_rows[day_rows["ticker"].astype(str) == ticker].copy()
        ttrades = trades[trades["ticker"].astype(str) == ticker].copy()
        for month in months:
            previous = [m for m in all_months if m < str(month)]
            test_days = tdays[tdays["test_month"].astype(str) == str(month)].copy()
            if test_days.empty:
                continue
            select_passed = False
            select_n = int(args.select_months)
            if len(previous) <= select_n:
                kept_days = test_days.copy()
                kept_days["day_gate_mode"] = "NO_HISTORY"
                if bool(args.fail_closed_on_select_fail):
                    kept_days = kept_days.iloc[0:0].copy()
                threshold = float("-inf")
                select_metrics = metrics(pd.DataFrame(), [])
                train_months: list[str] = []
                select_months: list[str] = []
            else:
                train_months = previous[:-select_n]
                select_months = previous[-select_n:]
                train_days = tdays[tdays["test_month"].astype(str).isin(train_months)].copy()
                select_days = tdays[tdays["test_month"].astype(str).isin(select_months)].copy()
                if len(train_days) < int(args.min_train_days) or len(select_days) < int(args.min_select_days):
                    kept_days = test_days.copy()
                    kept_days["day_gate_mode"] = "INSUFFICIENT_ROWS"
                    if bool(args.fail_closed_on_select_fail):
                        kept_days = kept_days.iloc[0:0].copy()
                    threshold = float("-inf")
                    select_metrics = metrics(ttrades[ttrades["test_month"].astype(str).isin(select_months)], select_months)
                else:
                    y = (pd.to_numeric(train_days["day_return"], errors="coerce").fillna(0.0) > 0.0).astype(int)
                    if y.nunique() < 2:
                        kept_days = test_days.copy()
                        kept_days["day_gate_mode"] = "SINGLE_CLASS"
                        if bool(args.fail_closed_on_select_fail):
                            kept_days = kept_days.iloc[0:0].copy()
                        threshold = float("-inf")
                        select_metrics = metrics(ttrades[ttrades["test_month"].astype(str).isin(select_months)], select_months)
                    else:
                        med = train_days[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
                        x_train = train_days[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(med).fillna(0.0)
                        weights = 1.0 + np.minimum(pd.to_numeric(train_days["day_return"], errors="coerce").fillna(0.0).abs().to_numpy(), 4.0)
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
                        model.fit(x_train, y, sample_weight=weights)

                        def score_days(frame: pd.DataFrame) -> pd.DataFrame:
                            out = frame.copy()
                            x = out[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(med).fillna(0.0)
                            out["day_score"] = model.predict_proba(x)[:, 1]
                            return out

                        scored_select = score_days(select_days)
                        select_trades = ttrades[ttrades["test_month"].astype(str).isin(select_months)].copy()
                        scored_select.attrs["trades"] = select_trades
                        gate = select_threshold(scored_select, select_months, args)
                        threshold = float(gate["threshold"])
                        select_passed = bool(gate.get("passed", False))
                        select_metrics = gate["metrics"]
                        scored_test = score_days(test_days)
                        if bool(args.fail_closed_on_select_fail) and not select_passed:
                            kept_days = scored_test.iloc[0:0].copy()
                            kept_days["day_gate_mode"] = "SELECT_FAIL"
                        else:
                            kept_days = scored_test if threshold == float("-inf") else scored_test[scored_test["day_score"].astype(float) >= threshold].copy()
                            kept_days["day_gate_mode"] = "NO_GATE" if threshold == float("-inf") else "DAY_SCORE"
                        kept_days["day_gate_threshold"] = threshold
            test_trades = ttrades[ttrades["test_month"].astype(str) == str(month)].copy()
            kept_trades = test_trades.merge(kept_days[["ticker", "date", "day_gate_mode"]], on=["ticker", "date"], how="inner")
            if not kept_trades.empty:
                out_parts.append(kept_trades)
            test_metrics = metrics(kept_trades, [str(month)])
            row = {
                "ticker": ticker,
                "month": str(month),
                "threshold": threshold,
                "train_months": ",".join(train_months),
                "select_months": ",".join(select_months),
                "select_passed": bool(select_passed),
                "kept_days": int(kept_days[["ticker", "date"]].drop_duplicates().shape[0]),
                "test_days": int(test_days[["ticker", "date"]].drop_duplicates().shape[0]),
                "feature_count": len(feature_cols),
            }
            row.update({f"select_{k}": v for k, v in select_metrics.items()})
            row.update({f"test_{k}": v for k, v in test_metrics.items()})
            fold_rows.append(row)
    return (pd.concat(out_parts, ignore_index=True) if out_parts else pd.DataFrame(), pd.DataFrame(fold_rows))


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
    axes[0].set_title(f"Daily Regime Gate Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(daily.index, daily.values, color=np.where(daily >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "daily_regime_gate_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, args: argparse.Namespace) -> None:
    expected = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, expected)
    per_ticker = {str(t): metrics(part, expected) for t, part in trades.groupby("ticker", sort=True)} if not trades.empty else {}
    payload = {
        "overall": overall,
        "per_ticker": per_ticker,
        "risk_capital": float(args.risk_capital),
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Daily Regime Gate",
        "",
        "Uses only the first accepted event of each ticker/day to decide whether to keep that ticker's trades for the day. Models and thresholds are trained/selected on prior months only.",
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
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal first-event daily regime gate for event-option trades.")
    parser.add_argument("--trades", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--include-ptdj-scalars", action="store_true")
    parser.add_argument("--select-months", type=int, default=2)
    parser.add_argument("--min-train-days", type=int, default=30)
    parser.add_argument("--min-select-days", type=int, default=5)
    parser.add_argument("--min-select-trades", type=int, default=18)
    parser.add_argument("--min-select-month-trades", type=int, default=8)
    parser.add_argument("--min-select-pf", type=float, default=0.0)
    parser.add_argument("--min-select-win-rate", type=float, default=0.0)
    parser.add_argument("--min-call-rate", type=float, default=0.10)
    parser.add_argument("--max-call-rate", type=float, default=0.90)
    parser.add_argument("--daily-win-weight", type=float, default=0.50)
    parser.add_argument("--top5-share-penalty", type=float, default=0.25)
    parser.add_argument("--threshold-grid", nargs="+", type=float, default=[0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80])
    parser.add_argument("--threshold-quantiles", nargs="+", type=float, default=[0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90])
    parser.add_argument("--fail-closed-on-select-fail", action="store_true")
    parser.add_argument("--estimators", type=int, default=120)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=7)
    parser.add_argument("--min-child-samples", type=int, default=8)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.75)
    parser.add_argument("--reg-lambda", type=float, default=8.0)
    parser.add_argument("--lgb-jobs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260618)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    trades = load_trades(Path(args.trades))
    features, raw_cols = load_features(Path(args.data), bool(args.include_ptdj_scalars))
    day_rows, feature_cols = build_day_rows(trades, features, raw_cols)
    gated, folds = apply_gate(trades, day_rows, feature_cols, args)
    if not gated.empty:
        gated["pnl"] = pd.to_numeric(gated["realized_return"], errors="coerce").fillna(0.0) * float(args.risk_capital)
        gated.to_csv(output_dir / "daily_regime_gate_trades.csv", index=False)
    folds.to_csv(output_dir / "daily_regime_gate_folds.csv", index=False)
    write_plot(output_dir, gated, float(args.risk_capital))
    write_summary(output_dir, gated, folds, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
