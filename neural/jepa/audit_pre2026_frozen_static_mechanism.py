from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from .event_option_live_scorer import apply_scored_trade_filter
    from .walkforward_event_option_gate import (
        DeployConfig,
        build_features,
        deploy,
        fit_direction_models,
        metrics,
        prepare_frame,
        score_direction_models,
    )
else:
    from event_option_live_scorer import apply_scored_trade_filter
    from walkforward_event_option_gate import (
        DeployConfig,
        build_features,
        deploy,
        fit_direction_models,
        metrics,
        prepare_frame,
        score_direction_models,
    )


TRAIN_MONTHS = [f"2025{month:02d}" for month in range(1, 10)]
SELECT_MONTHS = ["202510", "202511", "202512"]

# Frozen verbatim from the committed 202607 static-union components. These
# rules were originally selected on 2026, so this is a reverse stability audit,
# not clean evidence that the rule family was chosen before the audit months.
POLICIES = {
    "QQQ": {
        "delta_bucket": 35,
        "min_score": 0.0,
        "max_day": 2,
        "cooldown_minutes": 45,
        "filter": {
            "near_level_abs_bps_max": 20.0,
            "min_entry_time_et": "12:30",
            "max_entry_time_et": "14:30",
            "allowed_actions": ["CALL", "PUT"],
            "momentum_filter": "SELF_COUNTER_5M",
        },
    },
    "SPXW": {
        "delta_bucket": 25,
        "min_score": 0.0,
        "max_day": 1,
        "cooldown_minutes": 30,
        "filter": {
            "near_level_abs_bps_max": 20.0,
            "min_entry_time_et": "10:30",
            "max_entry_time_et": "14:30",
            "allowed_actions": ["CALL", "PUT"],
            "min_edge_abs": 0.05,
            "momentum_filter": "NONE",
        },
    },
    "SPY": {
        "delta_bucket": 35,
        "min_score": -0.1,
        "max_day": 4,
        "cooldown_minutes": 30,
        "filter": {
            "near_level_abs_bps_max": 20.0,
            "min_entry_time_et": "12:00",
            "max_entry_time_et": "14:30",
            "allowed_actions": ["PUT"],
            "min_edge_abs": 0.1,
            "momentum_filter": "SPX_COUNTER_5M",
        },
    },
}


def passes_gate(summary: dict, trades: pd.DataFrame) -> bool:
    holds = pd.to_numeric(trades.get("exit_minutes", pd.Series(dtype=float)), errors="coerce")
    return bool(
        int(summary.get("min_month_trades", 0)) >= 18
        and float(summary.get("win_rate", float("nan"))) >= 0.50
        and float(summary.get("profit_factor", float("nan"))) >= 1.30
        and float(summary.get("positive_month_rate", float("nan"))) >= 1.0
        and not trades.empty
        and holds.notna().all()
        and holds.ge(30).all()
    )


def model_args(delta_bucket: int, jobs: int, seed: int) -> argparse.Namespace:
    return argparse.Namespace(
        delta_bucket=int(delta_bucket),
        expiry_modes=["zero_dte"],
        entry_time_min_et="10:30",
        feature_include_prefixes=[],
        feature_exclude_prefixes=[],
        live_observable_features_only=True,
        label_mode="return",
        clip_return=5.0,
        n_estimators=160,
        learning_rate=0.035,
        num_leaves=31,
        min_child_samples=60,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=5.0,
        seed=int(seed),
        lgb_jobs=int(jobs),
        lgb_device_type="cpu",
        objective="regression_l1",
    )


def run_ticker(data: Path, ticker: str, policy: dict, jobs: int, seed: int) -> tuple[pd.DataFrame, dict]:
    args = model_args(int(policy["delta_bucket"]), jobs, seed)
    raw = prepare_frame(data, args)
    raw = raw[raw["ticker"].astype(str).eq(ticker)].copy()
    frame, feature_cols = build_features(raw, args)
    train = frame[frame["month"].astype(str).isin(TRAIN_MONTHS)].copy()
    select = frame[frame["month"].astype(str).isin(SELECT_MONTHS)].copy()
    if train.empty or select.empty:
        raise RuntimeError(f"{ticker}: missing train/select rows")
    call_model, put_model, medians = fit_direction_models(
        train,
        feature_cols,
        args,
        seed_offset=1_000 + int(policy["delta_bucket"]),
    )
    scored = score_direction_models(select, feature_cols, args, call_model, put_model, medians)
    scored = scored[pd.to_numeric(scored["score"], errors="coerce") >= float(policy["min_score"])].copy()
    issues: list[str] = []
    filtered = apply_scored_trade_filter(
        scored,
        policy["filter"],
        label=f"pre2026.{ticker}",
        issues=issues,
    )
    if issues:
        raise RuntimeError(f"{ticker}: filter issues: {issues}")
    selected = deploy(
        filtered,
        DeployConfig(float("-inf"), int(policy["max_day"])),
        int(policy["cooldown_minutes"]),
    )
    summary = metrics(selected, SELECT_MONTHS)
    holds = pd.to_numeric(selected.get("exit_minutes", pd.Series(dtype=float)), errors="coerce")
    summary.update(
        {
            "ticker": ticker,
            "train_rows": int(len(train)),
            "select_rows": int(len(select)),
            "scored_pass_min_score_rows": int(len(scored)),
            "filtered_candidate_rows": int(len(filtered)),
            "feature_count": int(len(feature_cols)),
            "min_hold_minutes": float(holds.min()) if not holds.empty else None,
            "passes_full_gate": passes_gate(summary, selected),
        }
    )
    return selected, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Reverse-audit 2026-selected frozen static rules on late 2025.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--jobs", type=int, default=28)
    parser.add_argument("--seed", type=int, default=20260617)
    args = parser.parse_args()
    output = Path(args.output_dir)
    if output.exists():
        raise FileExistsError(f"Refusing to reuse output: {output}")
    output.mkdir(parents=True)
    all_trades: list[pd.DataFrame] = []
    summaries: dict[str, dict] = {}
    for ticker, policy in POLICIES.items():
        trades, summary = run_ticker(Path(args.data), ticker, policy, int(args.jobs), int(args.seed))
        all_trades.append(trades)
        summaries[ticker] = summary
        print(
            f"[PRE2026_STATIC] {ticker} trades={summary['trades']} "
            f"wr={summary['win_rate']:.3f} pf={summary['profit_factor']:.3f} "
            f"min_month={summary['min_month_trades']} pass={summary['passes_full_gate']}",
            flush=True,
        )
    combined = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    combined.to_csv(output / "pre2026_static_selected_trades.csv", index=False)
    payload = {
        "schema_version": 1,
        "audit": "reverse_pre2026_stability_of_2026_selected_static_rules",
        "data": str(args.data),
        "train_months": TRAIN_MONTHS,
        "select_months": SELECT_MONTHS,
        "policies": POLICIES,
        "tickers": summaries,
        "all_tickers_pass_full_gate": all(row["passes_full_gate"] for row in summaries.values()),
        "production_live_ready": False,
        "selection_caveat": (
            "Rules were copied from policies selected on 202601..202606. Passing late 2025 is a reverse "
            "stability check, not proof that the rule family was selected without 2026 hindsight."
        ),
    }
    (output / "audit.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
