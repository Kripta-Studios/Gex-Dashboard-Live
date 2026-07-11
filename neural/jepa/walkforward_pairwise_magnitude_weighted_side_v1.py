"""P1 unweighted side classifier vs W1 magnitude-weighted side classifier."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walkforward_event_option_gate import DeployConfig, deploy, metrics
from walkforward_pairwise_opportunity_side import (
    FIRST_TEST_MONTH, FROZEN_SEED, HEAD_OFFSET_P1_OPP, HEAD_OFFSET_P1_SIDE,
    LAST_TEST_MONTH, SIDE_TIE_THRESHOLD_TRAINING, TICKER_CONFIG,
    apply_pairwise_policy, build_diff_features, build_labels,
    compute_economic_criteria, compute_feature_hash, compute_scientific_criteria,
    compute_scientific_side_metrics, generate_folds, make_lgb_params,
    select_best_config_p1, sha256_file,
)

EXPECTED_DATASET_SHA256 = "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408"


def magnitude_weights(side_advantage: pd.Series, quantile: float = 0.95) -> tuple[np.ndarray, float]:
    """Train-only absolute advantage weights, q95-clipped and mean-normalized."""
    advantage = pd.to_numeric(side_advantage, errors="coerce").abs().to_numpy(dtype=float)
    if not np.isfinite(advantage).all() or (advantage <= 0).any():
        raise ValueError("Side advantages must be finite and non-zero")
    cap = float(np.quantile(advantage, quantile))
    clipped = np.minimum(advantage, cap)
    weights = clipped / clipped.mean()
    return weights, cap


def physics_side_feature_cols(columns: list[str], base_features: list[str]) -> list[str]:
    """Predeclared current-time physics/context side block."""
    excluded = {
        "phys_event_seq_in_day", "phys_event_frac_in_day", "phys_minutes_since_first_event",
        "phys_spot_ret_from_first_event_bps", "phys_same_day_event_count",
    }
    extras = [
        col for col in columns
        if (col.startswith("phys_") and col not in excluded)
        or (col.startswith("ctx_") and not col.endswith("_spot"))
    ]
    result = list(dict.fromkeys(base_features + extras))
    if any("future" in col or "opt_exit" in col or "_opt_win" in col for col in result):
        raise ValueError("Outcome/future column entered physics side features")
    return result


def run_fold(
    ticker: str,
    fold: dict[str, Any],
    prepared: pd.DataFrame,
    features: list[str],
    variant: str = "weighted",
) -> dict[str, Any]:
    config = TICKER_CONFIG[ticker]
    bucket = int(config["bucket"])
    work = prepared.copy()
    work["month"] = work["trade_date"].astype(str).str[:6]
    work["date"] = work["trade_date"].astype(str)
    train = work[work["month"].isin(fold["train_months"])].copy()
    inner = work[work["month"].isin(fold["inner_months"])].copy()
    outer = work[work["month"] == fold["test_month"]].copy()
    medians = train[features].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)

    def x(frame: pd.DataFrame) -> pd.DataFrame:
        return frame[features].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)

    rich_features = physics_side_feature_cols(list(prepared.columns), features)
    rich_medians = train[rich_features].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)

    def x_rich(frame: pd.DataFrame) -> pd.DataFrame:
        return frame[rich_features].replace([np.inf, -np.inf], np.nan).fillna(rich_medians).fillna(0.0)

    x_train, x_inner, x_outer = x(train), x(inner), x(outer)
    side_mask = (
        (train["opportunity_label"] == 1)
        & (train["side_advantage"].astype(float).abs() > SIDE_TIE_THRESHOLD_TRAINING)
    )
    x_side = x(train[side_mask])
    y_side = train.loc[side_mask, "side_label"].astype(int)
    weights, weight_cap = magnitude_weights(train.loc[side_mask, "side_advantage"])
    base_seed = FROZEN_SEED + int(fold["test_month"]) + int(config["ticker_offset"])

    opportunity = lgb.LGBMClassifier(**make_lgb_params(base_seed, HEAD_OFFSET_P1_OPP))
    side_control = lgb.LGBMClassifier(**make_lgb_params(base_seed, HEAD_OFFSET_P1_SIDE))
    side_variant = lgb.LGBMClassifier(**make_lgb_params(base_seed, HEAD_OFFSET_P1_SIDE))
    opportunity.fit(x_train, train["opportunity_label"].astype(int))
    side_control.fit(x_side, y_side)
    if variant == "weighted":
        side_variant.fit(x_side, y_side, sample_weight=weights)
    elif variant == "physics":
        side_variant.fit(x_rich(train[side_mask]), y_side)
    else:
        raise ValueError(f"Unknown variant: {variant}")

    frames = {}
    for name, frame, matrix in (("inner", inner, x_inner), ("outer", outer, x_outer)):
        base = frame.copy()
        base["p_trade"] = opportunity.predict_proba(matrix)[:, 1]
        control = base.copy()
        variant_frame = base.copy()
        control["p_call"] = side_control.predict_proba(matrix)[:, 1]
        variant_matrix = matrix if variant == "weighted" else x_rich(frame)
        variant_frame["p_call"] = side_variant.predict_proba(variant_matrix)[:, 1]
        frames[(name, "control")] = control
        frames[(name, "variant")] = variant_frame

    result: dict[str, Any] = {
        "status": "completed", "ticker": ticker, "test_month": fold["test_month"],
        "train_months": ",".join(fold["train_months"]),
        "inner_months": ",".join(fold["inner_months"]),
        "feature_hash": compute_feature_hash(features),
        "weight_cap_q95_train": weight_cap,
        "weight_mean": float(weights.mean()),
        "variant": variant,
        "variant_side_feature_count": len(features) if variant == "weighted" else len(rich_features),
    }
    trade_records = {}
    for arm in ("control", "variant"):
        threshold, margin, valid, details = select_best_config_p1(
            frames[("inner", arm)], fold["inner_months"], config, bucket,
        )
        if valid:
            candidates = apply_pairwise_policy(frames[("outer", arm)], threshold, margin, bucket)
            traded = deploy(
                candidates, DeployConfig(threshold=0.0, max_trades_per_day=config["max_trades_per_day"]),
                config["cooldown_minutes"],
            ) if not candidates.empty else candidates
        else:
            traded = pd.DataFrame()
        test_metrics = metrics(traded, [fold["test_month"]])
        returns = traded["realized_return"].astype(float).to_numpy() if len(traded) else np.array([])
        wins, losses = returns[returns > 0], returns[returns < 0]
        diagnostics = {
            "pnl": float(returns.sum()) if len(returns) else 0.0,
            "min_hold_minutes": float(pd.to_numeric(traded["exit_minutes"], errors="coerce").min()) if len(traded) else float("nan"),
            "gross_profit": float(wins.sum()) if len(wins) else 0.0,
            "gross_loss": float(-losses.sum()) if len(losses) else 0.0,
            "outer_trade_records": [
                {"date": str(row.date), "minute": int(row.minute), "ticker": ticker, "realized_return": float(row.realized_return)}
                for row in traded.itertuples()
            ],
        }
        result[arm] = {
            "valid_inner": valid, "trade_threshold": threshold, "side_margin": margin,
            "selection_details": details, "test_metrics": test_metrics, "diagnostics": diagnostics,
        }
        trade_records[arm] = traded

    outer = frames[("outer", "control")]
    science = compute_scientific_side_metrics(
        outer["call_return"].to_numpy(), outer["put_return"].to_numpy(),
        2.0 * frames[("outer", "control")]["p_call"].to_numpy() - 1.0,
        2.0 * frames[("outer", "variant")]["p_call"].to_numpy() - 1.0,
    )
    result.update(science)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--variant", choices=("weighted", "physics"), default="weighted")
    args = parser.parse_args()
    dataset_path, output = Path(args.dataset), Path(args.output_dir)
    if output.exists():
        raise FileExistsError(output)
    if sha256_file(dataset_path) != EXPECTED_DATASET_SHA256:
        raise RuntimeError("Dataset hash mismatch")
    data = pd.read_parquet(dataset_path)
    data["trade_date"] = data["trade_date"].astype(str)
    if (data["trade_date"] >= "20260101").any():
        raise RuntimeError("2026 forbidden")
    output.mkdir(parents=True)

    results = []
    feature_hash = None
    for ticker, config in TICKER_CONFIG.items():
        bucket = int(config["bucket"])
        prepared = data[(data.ticker == ticker) & (pd.to_numeric(data.minute, errors="coerce") > 630)].copy()
        prepared, feature_cols = build_diff_features(prepared, ticker, bucket)
        prepared = build_labels(prepared, bucket)
        current_hash = compute_feature_hash(feature_cols)
        feature_hash = feature_hash or current_hash
        if current_hash != feature_hash:
            raise RuntimeError("Feature mismatch")
        for fold in generate_folds(FIRST_TEST_MONTH, LAST_TEST_MONTH):
            print(f"[{ticker} {fold['test_month']}]", flush=True)
            results.append(run_fold(ticker, fold, prepared, feature_cols, variant=args.variant))

    # Reuse audited criteria by mapping control -> c0 and weighted -> p1.
    mapped = [{**r, "c0": r["control"], "p1": r["variant"]} for r in results]
    science = compute_scientific_criteria(results)
    raw_economic = compute_economic_criteria(mapped)
    economic = {
        key.replace("c0_", "control_").replace("p1_", f"{args.variant}_"): value
        for key, value in raw_economic.items()
    }
    pd.json_normalize(results, sep="_").to_csv(output / "all_folds.csv", index=False)
    trades = []
    for r in results:
        for arm in ("control", "variant"):
            for record in r[arm]["diagnostics"]["outer_trade_records"]:
                label = "control" if arm == "control" else args.variant
                trades.append({"arm": label, "test_month": r["test_month"], **record})
    pd.DataFrame(trades).to_csv(output / "outer_trades.csv", index=False)
    summary = {
        "dataset_sha256": EXPECTED_DATASET_SHA256, "feature_hash": feature_hash,
        "cells": len(results), "science_control": "P1 unweighted",
        "science_variant": "W1 magnitude-weighted" if args.variant == "weighted" else "S1 physics/context side skip",
        "scientific_criteria": science, "economic_criteria": economic,
        "adaptive_reuse_not_promotable": True, "contains_2026": False, "production_modified": False,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    (output / "REPORT.md").write_text(
        "# Magnitude-weighted pairwise side V1\n\n"
        f"- Cells: `{len(results)}`\n- Scientific pass: `{science['scientific_pass']}`\n"
        f"- Control valid folds: `{sum(r['control']['valid_inner'] for r in results)}`\n"
        f"- Variant: `{args.variant}`\n- Variant valid folds: `{sum(r['variant']['valid_inner'] for r in results)}`\n"
        "- Adaptive reuse; not promotable without a new holdout.\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
