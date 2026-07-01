"""
Export strict-WF GBT probabilities as an OOF signal parquet for option-policy tests.

This is a bridge between the high-volume GBT alert search and
train_backtest_option_policy.py. It intentionally exports row-level predictions
only; the option layer must still validate strike/delta/exit profitability.
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backtest"))
sys.path.insert(0, str(PROJECT_ROOT / "neural"))

warnings.filterwarnings(
    "ignore",
    message="X does not have valid feature names",
    category=UserWarning,
)

from backtest_gbt_parquet import (  # noqa: E402
    _row_nearest_level_dist_bps,
    deployment_context_allowed,
    direction_from_prediction,
    get_independent_signals,
)
from neural.jepa.search_ticker_volume_profiles import (  # noqa: E402
    load_frame,
    load_ticker_models,
    strict_wf_probabilities,
)
from neural.jepa.jepa_180m_signal import normalize_ticker  # noqa: E402


def normalize_date(value) -> str:
    text = str(value).replace("-", "")
    return text[:8]


def time_to_minutes(value) -> int:
    try:
        hh, mm = str(value).split(":")[:2]
        return int(hh) * 60 + int(mm)
    except Exception:
        return 0


def load_probs(args, df: pd.DataFrame) -> np.ndarray:
    if args.probabilities_cache:
        cache = pd.read_parquet(args.probabilities_cache)
        cache["ticker"] = cache["ticker"].map(normalize_ticker)
        cache["date"] = cache["date"].map(normalize_date)
        cache = cache[(cache["date"] >= args.start_date) & (cache["date"] <= args.end_date)].copy()
        if args.tickers:
            cache = cache[cache["ticker"].isin(args.tickers)].copy()
        key_cols = ["ticker", "date", "time"]
        merged = df[key_cols].merge(cache[key_cols + ["p_short", "p_hold", "p_long"]], on=key_cols, how="left")
        if merged[["p_short", "p_hold", "p_long"]].isna().any().any():
            missing = int(merged[["p_short", "p_hold", "p_long"]].isna().any(axis=1).sum())
            raise RuntimeError(f"Probability cache is missing {missing:,} rows")
        return merged[["p_short", "p_hold", "p_long"]].to_numpy(dtype=np.float32)

    from backtest_gbt_parquet import get_device  # local import avoids CUDA init when using cache

    device = get_device()
    models, normalizers = load_ticker_models(Path(args.model), Path(args.normalizer), args.model_size, device)
    print(f"[model] loaded={sorted(models.keys())}")
    return strict_wf_probabilities(df, models, normalizers)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="training_data/training_data_spx_qqq_spy.parquet")
    parser.add_argument("--model", default="neural/models/codex_exp/gbt_candidate_top2_rec1_march2026.joblib")
    parser.add_argument("--normalizer", default="neural/models/codex_exp/gbt_candidate_top2_rec1_march2026_norm.npz")
    parser.add_argument("--model-size", default="small")
    parser.add_argument("--probabilities-cache", default="")
    parser.add_argument("--start-date", default="20250101")
    parser.add_argument("--end-date", default="20260605")
    parser.add_argument("--tickers", nargs="+", default=["SPY"])
    parser.add_argument("--threshold", type=float, default=0.30)
    parser.add_argument("--side-mode", choices=["long", "short", "both"], default="short")
    parser.add_argument("--min-entry-minute", type=int, default=580)
    parser.add_argument("--max-level-dist-bps", type=float, default=15.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    os.environ.setdefault("GBT_STRICT_MIN_VALIDATION_TRADES", "12")
    os.environ.setdefault("GBT_STRICT_MIN_AVG_PF", "1.25")
    os.environ.setdefault("GBT_STRICT_TOP_N_WINDOWS", "3")
    os.environ.setdefault("GBT_STRICT_RECENCY_POWER", "2.0")
    os.environ.setdefault("GBT_TICKER_STRICT_MIN_AVG_PF", "QQQ:1.25")
    os.environ.setdefault("GBT_TICKER_STRICT_TOP_N_WINDOWS", "QQQ:2")
    os.environ.setdefault("GBT_TICKER_STRICT_RECENCY_POWER", "QQQ:0.5")
    os.environ.setdefault("DEPLOYMENT_TICKER_MAX_VIX_SPOT", "SPY:0.4108")

    df = load_frame(Path(args.data), args.start_date, args.end_date, args.tickers)
    df["ticker"] = df["ticker"].map(normalize_ticker)
    df["date"] = df["date"].map(normalize_date)
    probs = load_probs(args, df)
    preds, _ = get_independent_signals(probs, base_confidence=float(args.threshold))
    if args.side_mode == "long":
        preds[preds == 0] = 1
    elif args.side_mode == "short":
        preds[preds == 2] = 1

    directions = np.array([
        1 if direction_from_prediction(pred) == "LONG" else -1 if direction_from_prediction(pred) == "SHORT" else 0
        for pred in preds
    ], dtype=np.int8)

    minutes = df["time"].map(time_to_minutes).astype(int)
    eligible = minutes >= int(args.min_entry_minute)
    context_ok = np.array([
        bool(deployment_context_allowed(row, direction=direction_from_prediction(pred)))
        if directions[i] != 0 else False
        for i, (pred, row) in enumerate(zip(preds, df.to_dict("records")))
    ], dtype=bool)
    level_ok = np.array([
        float(_row_nearest_level_dist_bps(row)) <= float(args.max_level_dist_bps)
        for row in df.to_dict("records")
    ], dtype=bool)
    final_dir = np.where(eligible.to_numpy() & context_ok & level_ok, directions, 0).astype(np.int8)

    p_short = probs[:, 0].astype(float)
    p_hold = probs[:, 1].astype(float)
    p_long = probs[:, 2].astype(float)
    signed_edge = p_long - p_short
    confidence = np.where(final_dir > 0, p_long, np.where(final_dir < 0, p_short, np.maximum(p_long, p_short)))

    out = df[["ticker", "date", "time"]].copy()
    out["p_short"] = p_short
    out["p_hold"] = p_hold
    out["p_long"] = p_long
    out["jepa180_prob_up"] = p_long
    out["jepa180_pred_bps"] = signed_edge * 10000.0
    out["jepa180_long_threshold"] = float(args.threshold)
    out["jepa180_short_threshold"] = float(args.threshold)
    out["jepa180_confidence"] = confidence
    out["jepa180_edge"] = np.abs(signed_edge)
    out["jepa180_direction"] = final_dir
    out["jepa180_signal"] = final_dir != 0

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output, index=False)
    sig = out[out["jepa180_direction"].astype(int) != 0].copy()
    sig["month"] = sig["date"].str.slice(0, 6)
    print(f"[export] rows={len(out):,} signals={len(sig):,} output={output}")
    if not sig.empty:
        monthly = sig.groupby(["ticker", "month"]).size().reset_index(name="signals")
        print(monthly.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
