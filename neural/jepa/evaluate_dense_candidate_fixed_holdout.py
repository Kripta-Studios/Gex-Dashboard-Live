from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.apply_event_monthly_volume_backfill import apply_backfill
from neural.jepa.evaluate_xinput_level_filter import month_add, month_range
from neural.jepa.walkforward_event_option_gate import (
    build_features,
    choose_deploy_config,
    deploy,
    fit_direction_models,
    metrics,
    prepare_frame,
    score_direction_models,
)


FEATURE_PREFIXES = [
    "phys_",
    "ctx_",
    "ret_",
    "dist_",
    "nearest",
    "ib_range",
    "minute",
    "dte_days",
    "underlying_volume",
    "spot",
]


def role_args(args: argparse.Namespace, role: str) -> SimpleNamespace:
    base: dict[str, Any] = {
        "data": "",
        "output_dir": str(args.output_dir),
        "tickers": ["SPXW", "SPY", "QQQ"],
        "train_tickers": ["SPXW", "SPY", "QQQ"],
        "expiry_modes": ["zero_dte"],
        "start_month": str(args.start_month),
        "end_month": str(args.end_month),
        "val_months": int(args.select_months),
        "pooled_train": True,
        "clip_return": 2.0,
        "min_train_rows": 500,
        "min_val_rows": 30,
        "min_val_positive_month_rate": 0.0,
        "min_val_daily_win_rate": 0.0,
        "min_val_median_daily_return": float("-inf"),
        "max_val_top5_share": float("inf"),
        "max_val_daily_drawdown": float("inf"),
        "cooldown_minutes": 30,
        "objective": "regression_l1",
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "threshold_quantiles": [],
        "feature_include_prefixes": FEATURE_PREFIXES,
        "feature_exclude_prefixes": [],
        "live_observable_features_only": not bool(args.allow_live_inconsistent_features),
        "entry_time_min_et": str(args.entry_time_min_et),
        "allow_invalid_val_deploy": False,
        "deploy_month": str(args.deploy_month),
        "deploy_select_end_month": str(args.select_end_month),
        "export_deploy_model": False,
        "skip_walkforward": False,
        "resume": False,
        "seed": int(args.seed),
    }
    if role == "primary":
        base.update(
            {
                "delta_bucket": 25,
                "label_mode": "win",
                "min_val_trades": 72,
                "min_month_trades": 12,
                "min_val_pf": 1.2,
                "min_val_win_rate": 0.45,
                "min_call_rate": 0.05,
                "max_call_rate": 0.85,
                "n_estimators": 180,
                "learning_rate": 0.03,
                "num_leaves": 31,
                "min_child_samples": 100,
                "reg_lambda": 8.0,
                "lgb_jobs": int(args.lgb_jobs),
                "threshold_grid": [-999.0, 0.48, 0.5, 0.52, 0.55, 0.58, 0.6, 0.62, 0.65, 0.68, 0.7, 0.75],
                "threshold_quantiles": [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.93, 0.95],
                "max_day_grid": [1, 2, 3],
            }
        )
    else:
        base.update(
            {
                "delta_bucket": 50,
                "label_mode": "return",
                "min_val_trades": 1,
                "min_month_trades": 1,
                "min_val_pf": 0.0,
                "min_val_win_rate": 0.0,
                "min_call_rate": 0.0,
                "max_call_rate": 1.0,
                "n_estimators": 140,
                "learning_rate": 0.035,
                "num_leaves": 31,
                "min_child_samples": 80,
                "reg_lambda": 5.0,
                "lgb_jobs": int(args.lgb_jobs),
                "threshold_grid": [-999.0],
                "max_day_grid": [3],
            }
        )
    return SimpleNamespace(**base)


def load_dense_frames(paths: list[str], args: argparse.Namespace, role: str) -> tuple[pd.DataFrame, list[str], SimpleNamespace]:
    role_ns = role_args(args, role)
    parts: list[pd.DataFrame] = []
    for raw in paths:
        part = prepare_frame(raw, role_ns)
        parts.append(part)
    raw_frame = pd.concat(parts, ignore_index=True, sort=False)
    keys = [col for col in ["ticker", "trade_date", "time", "expiry_mode"] if col in raw_frame.columns]
    if keys:
        raw_frame = raw_frame.drop_duplicates(keys, keep="last").reset_index(drop=True)
    tickers = {str(t).upper() for t in args.tickers}
    raw_frame = raw_frame[raw_frame["ticker"].astype(str).str.upper().isin(tickers)].copy()
    frame, features = build_features(raw_frame, role_ns)
    return frame, features, role_ns


def previous_month(month: str) -> str:
    return month_add(str(month), -1)


def fit_score_role(
    frame: pd.DataFrame,
    features: list[str],
    role_ns: SimpleNamespace,
    args: argparse.Namespace,
    role: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    deploy_month = str(args.deploy_month)
    select_end = str(args.select_end_month)
    available = sorted(m for m in frame["month"].astype(str).unique() if m < deploy_month and m <= select_end)
    if len(available) <= int(args.select_months):
        raise RuntimeError(f"Not enough prior months for deploy_month={deploy_month}, select_end={select_end}: {available}")
    select_months = available[-int(args.select_months) :]
    train_months = available[: -int(args.select_months)]
    holdout_months = month_range(str(args.start_month), str(args.end_month))
    rows: list[pd.DataFrame] = []
    fold_rows: list[dict[str, Any]] = []
    source_name = "win_valthr_strict_d25" if role == "primary" else "forcedmax3_d50"
    source_priority = 0 if role == "primary" else 1
    order = 0 if role == "primary" else 1_000_000

    train_tickers = [str(t).upper() for t in getattr(role_ns, "train_tickers", [])]
    train = frame[
        frame["month"].astype(str).isin(train_months)
        & frame["ticker"].astype(str).str.upper().isin(train_tickers)
    ].copy()
    if len(train) < int(role_ns.min_train_rows):
        raise RuntimeError(f"{role} train rows {len(train)} < {role_ns.min_train_rows}")

    for ticker in [str(t).upper() for t in args.tickers]:
        select = frame[
            frame["month"].astype(str).isin(select_months)
            & frame["ticker"].astype(str).str.upper().eq(ticker)
        ].copy()
        if len(select) < int(role_ns.min_val_rows):
            raise RuntimeError(f"{role} {ticker} select rows {len(select)} < {role_ns.min_val_rows}")
        call_model, put_model, medians = fit_direction_models(
            train,
            features,
            role_ns,
            seed_offset=int(deploy_month[-2:]) + 1000 * source_priority,
        )
        scored_select = score_direction_models(select, features, role_ns, call_model, put_model, medians)
        cfg, select_metrics, select_score = choose_deploy_config(scored_select, select_months, role_ns)
        if float(select_score) <= -1e17:
            raise RuntimeError(f"{role} {ticker} invalid selection score for {deploy_month}: {select_score}")

        for test_month in holdout_months:
            test = frame[
                frame["month"].astype(str).eq(test_month)
                & frame["ticker"].astype(str).str.upper().eq(ticker)
            ].copy()
            scored_test = score_direction_models(test, features, role_ns, call_model, put_model, medians)
            trades = deploy(scored_test, cfg, int(role_ns.cooldown_minutes))
            test_metrics = metrics(trades, [test_month])
            if not trades.empty:
                trades = trades.copy()
                trades["test_month"] = test_month
                trades["source_stream"] = source_name
                trades["monthly_backfill_role"] = role
                trades["source_priority"] = source_priority
                trades["entry_minute"] = pd.to_numeric(trades["minute"], errors="coerce").fillna(0).astype(int)
                trades["_source_order"] = np.arange(order, order + len(trades), dtype=np.int64)
                order += len(trades)
                rows.append(trades)
            fold_rows.append(
                {
                    "ticker": ticker,
                    "source_stream": source_name,
                    "role": role,
                    "deploy_month": deploy_month,
                    "select_end_month": select_end,
                    "test_month": test_month,
                    "train_months": ",".join(train_months),
                    "select_months": ",".join(select_months),
                    "implied_train_end_month": previous_month(select_months[0]),
                    "deploy_config": cfg.name,
                    "train_rows": int(len(train)),
                    "select_rows": int(len(select)),
                    "test_rows": int(len(test)),
                    "select_score": float(select_score),
                    **{f"select_{k}": v for k, v in select_metrics.items()},
                    **{f"test_{k}": v for k, v in test_metrics.items()},
                }
            )
    out = pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()
    return out, fold_rows


def summarize(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, args: argparse.Namespace) -> None:
    months = month_range(str(args.start_month), str(args.end_month))
    payload = {
        "diagnostic": "dense_candidate_fixed_holdout",
        "official_forward_evidence": False,
        "reason_not_official": "Holdout diagnostic may include an incomplete month; it is not a forward-frozen production evaluation.",
        "deploy_month": str(args.deploy_month),
        "select_end_month": str(args.select_end_month),
        "months": months,
        "data": args.data,
        "overall": metrics(trades, months),
        "by_ticker": {
            ticker: metrics(part, months)
            for ticker, part in trades.groupby("ticker", sort=True)
        }
        if not trades.empty
        else {},
        "by_source": {
            source: metrics(part, months)
            for source, part in trades.groupby("source_stream", sort=True)
        }
        if not trades.empty
        else {},
        "folds": folds.to_dict("records"),
        "args": vars(args),
    }
    (output_dir / "fixed_holdout_evaluation.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Dense Candidate Fixed Holdout Evaluation",
        "",
        "Diagnostic only. Components are fit/selected with data available before the holdout window, then applied to the requested holdout months.",
        "",
        f"- Official forward evidence: `{payload['official_forward_evidence']}`",
        f"- Deploy month: `{args.deploy_month}`",
        f"- Select end month: `{args.select_end_month}`",
        f"- Holdout months: `{','.join(months)}`",
        f"- Selected rows: `{len(trades)}`",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(payload["overall"], indent=2, allow_nan=True),
        "```",
        "",
        "## By Ticker",
        "",
        "```json",
        json.dumps(payload["by_ticker"], indent=2, allow_nan=True),
        "```",
        "",
        "## By Source",
        "",
        "```json",
        json.dumps(payload["by_source"], indent=2, allow_nan=True),
        "```",
        "",
        "## Fold Lineage",
        "",
        "```csv",
        folds.to_csv(index=False),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate dense15 candidate logic on a fixed completed-data holdout.")
    parser.add_argument("--data", nargs="+", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--deploy-month", default="202605")
    parser.add_argument("--select-end-month", default="202604")
    parser.add_argument("--start-month", default="202605")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--select-months", type=int, default=6)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--lgb-jobs", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260617)
    parser.add_argument(
        "--entry-time-min-et",
        default="10:00",
        help="Earliest live entry time used to filter non-observable features.",
    )
    parser.add_argument(
        "--allow-live-inconsistent-features",
        action="store_true",
        help="Diagnostic escape hatch: do not drop features unavailable in live at entry time.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    primary_frame, primary_features, primary_args = load_dense_frames([str(item) for item in args.data], args, "primary")
    fallback_frame, fallback_features, fallback_args = load_dense_frames([str(item) for item in args.data], args, "fallback")
    primary, primary_folds = fit_score_role(primary_frame, primary_features, primary_args, args, "primary")
    fallback, fallback_folds = fit_score_role(fallback_frame, fallback_features, fallback_args, args, "fallback")

    primary.to_csv(output_dir / "primary_candidates.csv", index=False)
    fallback.to_csv(output_dir / "fallback_candidates.csv", index=False)
    backfill_args = SimpleNamespace(
        start_month=str(args.start_month),
        end_month=str(args.end_month),
        min_month_trades=int(args.min_month_trades),
        auto_partial_month_target=False,
        partial_month_observed_floor=0,
        backfill_only_partial_months=False,
        max_day=3,
        cooldown_minutes=30,
        primary_name="win_valthr_strict_d25",
        fallback_name="forcedmax3_d50",
        risk_capital=float(args.risk_capital),
    )
    selected = apply_backfill(primary, fallback, backfill_args)
    if not selected.empty:
        selected["pnl"] = pd.to_numeric(selected["realized_return"], errors="coerce").fillna(0.0) * float(args.risk_capital)
    selected.to_csv(output_dir / "combined_trades.csv", index=False)
    folds = pd.DataFrame(primary_folds + fallback_folds)
    folds.to_csv(output_dir / "combined_folds.csv", index=False)
    summarize(output_dir, selected, folds, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
