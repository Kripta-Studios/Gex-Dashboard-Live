"""Failure decomposition for the closed Pairwise V1 inner grids.

This diagnostic retrains the frozen V1 heads but never scores the outer month.
It persists all 63 threshold/margin configurations per arm and fold so the
economic starvation can be attributed to specific inner gates.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walkforward_event_option_gate import DeployConfig, deploy
from walkforward_pairwise_opportunity_side import (
    C0_TIE_THRESHOLD_EXECUTION,
    DIFF_METRICS,
    FIRST_TEST_MONTH,
    HEAD_OFFSET_C0_CALL,
    HEAD_OFFSET_C0_PUT,
    HEAD_OFFSET_P1_OPP,
    HEAD_OFFSET_P1_SIDE,
    INNER_MIN_HOLD_MINUTES,
    INNER_MIN_PF,
    INNER_MIN_TRADES_PER_MONTH,
    INNER_MIN_WR,
    LAST_TEST_MONTH,
    SIDE_MARGINS,
    SIDE_TIE_THRESHOLD_TRAINING,
    TICKER_CONFIG,
    TRADE_THRESHOLDS,
    apply_c0_policy,
    apply_pairwise_policy,
    build_diff_features,
    build_labels,
    compute_feature_hash,
    generate_folds,
    make_lgb_params,
    sha256_file,
)

EXPECTED_DATASET_SHA256 = "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408"


def evaluate_inner_configuration(
    scored: pd.DataFrame,
    inner_months: list[str],
    ticker_config: dict[str, Any],
    bucket: int,
    trade_threshold: float,
    side_margin: float,
    apply_policy: Callable[..., pd.DataFrame],
) -> dict[str, Any]:
    """Evaluate every gate separately for one frozen inner configuration."""
    applied = apply_policy(scored, trade_threshold, side_margin, bucket)
    if applied.empty:
        traded = applied
    else:
        cfg = DeployConfig(threshold=0.0, max_trades_per_day=ticker_config["max_trades_per_day"])
        traded = deploy(applied, cfg, ticker_config["cooldown_minutes"])

    month_rows = []
    for month in inner_months:
        month_trades = traded[traded["month"].astype(str) == month] if not traded.empty else traded
        returns = month_trades["realized_return"].astype(float).to_numpy() if len(month_trades) else np.array([])
        wins = returns[returns > 0.0]
        losses = returns[returns < 0.0]
        trades = int(len(returns))
        pf = float(wins.sum() / (-losses.sum())) if len(losses) else (float("inf") if trades else float("nan"))
        wr = float((returns > 0.0).mean()) if trades else float("nan")
        pnl = float(returns.sum()) if trades else 0.0
        if trades and "exit_minutes" in month_trades.columns:
            hold = pd.to_numeric(month_trades["exit_minutes"], errors="coerce")
            min_hold = float(hold.min())
        else:
            min_hold = float("nan")
        month_rows.append({
            "month": month,
            "trades": trades,
            "pf": pf,
            "wr": wr,
            "pnl": pnl,
            "min_hold": min_hold,
            "pf_pass": bool(trades and pf >= INNER_MIN_PF),
            "wr_pass": bool(trades and wr >= INNER_MIN_WR),
            "trades_pass": bool(trades >= INNER_MIN_TRADES_PER_MONTH),
            "pnl_pass": bool(pnl > 0.0),
            "hold_pass": bool(trades and np.isfinite(min_hold) and min_hold >= INNER_MIN_HOLD_MINUTES),
        })

    gate_names = ("pf", "wr", "trades", "pnl", "hold")
    gate_pass = {name: all(row[f"{name}_pass"] for row in month_rows) for name in gate_names}
    failing = [name for name in gate_names if not gate_pass[name]]
    return {
        "trade_threshold": trade_threshold,
        "side_margin": side_margin,
        "total_trades": int(sum(row["trades"] for row in month_rows)),
        "total_pnl": float(sum(row["pnl"] for row in month_rows)),
        "min_month_trades": int(min(row["trades"] for row in month_rows)),
        "min_month_pnl": float(min(row["pnl"] for row in month_rows)),
        "min_month_pf": float(min((row["pf"] if np.isfinite(row["pf"]) else 0.0) for row in month_rows)),
        "min_month_wr": float(min((row["wr"] if np.isfinite(row["wr"]) else 0.0) for row in month_rows)),
        **{f"all_months_{name}_pass": value for name, value in gate_pass.items()},
        "all_gates_pass": not failing,
        "gate_pass_count": int(sum(gate_pass.values())),
        "failure_signature": "+".join(failing) if failing else "PASS",
        "month_details": json.dumps(month_rows, sort_keys=True, default=str),
    }


def fit_frozen_inner_scores(
    prepared: pd.DataFrame,
    feature_cols: list[str],
    fold: dict[str, Any],
    ticker_config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit the four V1 heads using train only and return inner scores only."""
    work = prepared.copy()
    work["month"] = work["trade_date"].astype(str).str[:6]
    work["date"] = work["trade_date"].astype(str)
    train = work[work["month"].isin(fold["train_months"])].copy()
    inner = work[work["month"].isin(fold["inner_months"])].copy()
    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)

    def features(frame: pd.DataFrame) -> pd.DataFrame:
        return frame[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)

    x_train = features(train)
    x_inner = features(inner)
    base_seed = 42 + int(fold["test_month"]) + int(ticker_config["ticker_offset"])

    call = lgb.LGBMClassifier(**make_lgb_params(base_seed, HEAD_OFFSET_C0_CALL))
    put = lgb.LGBMClassifier(**make_lgb_params(base_seed, HEAD_OFFSET_C0_PUT))
    opportunity = lgb.LGBMClassifier(**make_lgb_params(base_seed, HEAD_OFFSET_P1_OPP))
    side = lgb.LGBMClassifier(**make_lgb_params(base_seed, HEAD_OFFSET_P1_SIDE))
    call.fit(x_train, train["call_win_label"].astype(int))
    put.fit(x_train, train["put_win_label"].astype(int))
    opportunity.fit(x_train, train["opportunity_label"].astype(int))
    side_mask = (
        (train["opportunity_label"] == 1)
        & (train["side_advantage"].astype(float).abs() > SIDE_TIE_THRESHOLD_TRAINING)
    )
    side.fit(features(train[side_mask]), train.loc[side_mask, "side_label"].astype(int))

    c0 = inner.copy()
    c0["p_call_win"] = call.predict_proba(x_inner)[:, 1]
    c0["p_put_win"] = put.predict_proba(x_inner)[:, 1]
    p1 = inner.copy()
    p1["p_trade"] = opportunity.predict_proba(x_inner)[:, 1]
    p1["p_call"] = side.predict_proba(x_inner)[:, 1]
    return c0, p1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    if sha256_file(dataset_path) != EXPECTED_DATASET_SHA256:
        raise RuntimeError("Dataset hash mismatch")

    data = pd.read_parquet(dataset_path)
    data["trade_date"] = data["trade_date"].astype(str)
    if (data["trade_date"] >= "20260101").any():
        raise RuntimeError("2026 is forbidden")
    output_dir.mkdir(parents=True)

    all_rows = []
    feature_hash = None
    folds = generate_folds(FIRST_TEST_MONTH, LAST_TEST_MONTH)
    for ticker, ticker_config in TICKER_CONFIG.items():
        bucket = int(ticker_config["bucket"])
        prepared = data[(data["ticker"] == ticker) & (pd.to_numeric(data["minute"], errors="coerce") > 630)].copy()
        prepared, feature_cols = build_diff_features(prepared, ticker, bucket)
        prepared = build_labels(prepared, bucket)
        current_hash = compute_feature_hash(feature_cols)
        feature_hash = feature_hash or current_hash
        if current_hash != feature_hash:
            raise RuntimeError("Feature hash mismatch across tickers")

        for index, fold in enumerate(folds, start=1):
            print(f"[{ticker} {fold['test_month']}] {index}/33", flush=True)
            c0_scores, p1_scores = fit_frozen_inner_scores(prepared, feature_cols, fold, ticker_config)
            for arm, scored, apply_policy in (
                ("C0", c0_scores, apply_c0_policy),
                ("P1", p1_scores, apply_pairwise_policy),
            ):
                for threshold in TRADE_THRESHOLDS:
                    for margin in SIDE_MARGINS:
                        row = evaluate_inner_configuration(
                            scored, fold["inner_months"], ticker_config, bucket,
                            threshold, margin, apply_policy,
                        )
                        all_rows.append({
                            "ticker": ticker,
                            "outer_month_identity_only": fold["test_month"],
                            "train_months": ",".join(fold["train_months"]),
                            "inner_months": ",".join(fold["inner_months"]),
                            "arm": arm,
                            **row,
                        })

    grid = pd.DataFrame(all_rows)
    grid.to_csv(output_dir / "inner_grid_all.csv", index=False)
    summary = (
        grid.groupby(["arm", "ticker"], as_index=False)
        .agg(
            configurations=("all_gates_pass", "size"),
            all_gates_pass=("all_gates_pass", "sum"),
            pf_pass=("all_months_pf_pass", "sum"),
            wr_pass=("all_months_wr_pass", "sum"),
            trades_pass=("all_months_trades_pass", "sum"),
            pnl_pass=("all_months_pnl_pass", "sum"),
            hold_pass=("all_months_hold_pass", "sum"),
        )
    )
    summary.to_csv(output_dir / "gate_failure_summary.csv", index=False)
    near = (
        grid.sort_values(
            ["arm", "ticker", "outer_month_identity_only", "gate_pass_count", "min_month_pnl", "total_pnl"],
            ascending=[True, True, True, False, False, False],
        )
        .groupby(["arm", "ticker", "outer_month_identity_only"], as_index=False)
        .head(1)
    )
    near.to_csv(output_dir / "fold_near_miss.csv", index=False)
    manifest = {
        "diagnostic": "PAIRWISE_INNER_GRID_FAILURE_DECOMPOSITION_V1",
        "dataset_sha256": EXPECTED_DATASET_SHA256,
        "feature_hash": feature_hash,
        "outer_labels_scored": False,
        "full_grid_rows": int(len(grid)),
        "expected_grid_rows": 99 * 2 * 63,
        "all_gates_pass_rows": int(grid["all_gates_pass"].sum()),
        "contains_2026": False,
        "production_modified": False,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
