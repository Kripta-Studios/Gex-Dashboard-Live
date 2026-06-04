#!/usr/bin/env python3
"""Audit live JEPA feature parity for rt_data/YYYYMMDD/ml_features_* files.

Checks that rows with xjepa_context_valid=1 also have live historical context
features populated.  Optionally compares live zero-heavy features against each
model artifact's training medians and feature importances.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

CRITICAL_FEATURES = [
    "vix_5d_mean",
    "vix_5d_std",
    "atr_5d_norm",
    "signal_persistence_5m",
]


def _safe_float(value, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if np.isfinite(out) else default
    except Exception:
        return default


def audit_ticker(rt_day_dir: Path, model_dir: Path, ticker: str, entry_cutoff: str, zero_pct_min: float) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    feature_path = rt_day_dir / f"ml_features_{ticker}_latest.parquet"
    artifact_path = model_dir / "base_jepa" / f"{ticker}.joblib"

    if not feature_path.exists():
        print(f"[{ticker}] MISSING live feature file: {feature_path}")
        return pd.DataFrame(), pd.DataFrame(), False
    if not artifact_path.exists():
        print(f"[{ticker}] MISSING model artifact: {artifact_path}")
        return pd.DataFrame(), pd.DataFrame(), False

    df = pd.read_parquet(feature_path)
    if "xjepa_context_valid" in df.columns:
        valid = df[df["xjepa_context_valid"] > 0].copy()
    else:
        valid = pd.DataFrame()
    if not valid.empty and "time" in valid.columns:
        valid = valid[valid["time"].astype(str).str[:5] <= entry_cutoff].copy()

    print("\n" + "=" * 100)
    print(ticker)
    print("=" * 100)
    print(f"rows={len(df)} valid_rows<={entry_cutoff}={len(valid)} file={feature_path}")

    ok = True
    if valid.empty:
        print(f"[{ticker}] No xjepa-valid rows to audit yet.")
        return pd.DataFrame(), pd.DataFrame(), True

    latest = valid.tail(1).iloc[0]
    cols = ["date", "time", "minutes_since_open", "spot_price", "xjepa_context_valid", "live_feature_context_valid"] + CRITICAL_FEATURES
    cols = [c for c in cols if c in valid.columns]
    print("\nLatest valid row:")
    print(valid[cols].tail(5).to_string(index=False))

    bad_critical = []
    for col in ["live_feature_context_valid"] + CRITICAL_FEATURES:
        if col not in valid.columns:
            bad_critical.append(f"{col}=MISSING")
            ok = False
            continue
        val = _safe_float(latest.get(col), 0.0)
        if col == "signal_persistence_5m":
            # Signal persistence can be zero on the very first observation after a reset,
            # but should quickly become positive.  Treat missing as fatal, zero as warning.
            if val <= 0.0:
                bad_critical.append(f"{col}={val:g} (warning)")
        elif val <= 0.0:
            bad_critical.append(f"{col}={val:g}")
            ok = False

    if bad_critical:
        print("\nCRITICAL/WARNING:", ", ".join(bad_critical))
    else:
        print("\nCritical live context features: OK")

    obj = joblib.load(artifact_path)
    model = obj["model"]
    features = list(obj["features"])
    medians = dict(obj["medians"])
    gain = model.booster_.feature_importance(importance_type="gain")
    split = model.booster_.feature_importance(importance_type="split")

    rows = []
    for i, feat in enumerate(features):
        median = _safe_float(medians.get(feat, np.nan), np.nan)
        if feat not in valid.columns:
            rows.append({
                "ticker": ticker,
                "feature": feat,
                "status": "MISSING_IN_LIVE",
                "gain": float(gain[i]),
                "split": int(split[i]),
                "zero_pct": np.nan,
                "live_mean": np.nan,
                "live_min": np.nan,
                "live_max": np.nan,
                "train_median": median,
                "suspect": True,
                "reason": "model feature missing in live parquet",
            })
            ok = False
            continue
        s = pd.to_numeric(valid[feat], errors="coerce")
        zero_pct = float((s == 0).mean())
        live_mean = float(s.mean()) if not s.dropna().empty else np.nan
        suspect = bool(zero_pct >= zero_pct_min and np.isfinite(median) and abs(median) > 1e-9)
        rows.append({
            "ticker": ticker,
            "feature": feat,
            "status": "OK",
            "gain": float(gain[i]),
            "split": int(split[i]),
            "zero_pct": zero_pct,
            "live_mean": live_mean,
            "live_min": float(s.min()) if not s.dropna().empty else np.nan,
            "live_max": float(s.max()) if not s.dropna().empty else np.nan,
            "train_median": median,
            "suspect": suspect,
            "reason": "live mostly zero but train median non-zero" if suspect else "",
        })

    audit = pd.DataFrame(rows)
    suspects = audit[audit["suspect"]].sort_values("gain", ascending=False)
    print("\nTop suspects by model gain:")
    if suspects.empty:
        print("None")
    else:
        print(suspects[["feature", "gain", "split", "zero_pct", "live_mean", "train_median", "reason"]].head(30).to_string(index=False))
    return audit, suspects, ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit live JEPA feature files for zero-filled context features.")
    parser.add_argument("--date", required=True, help="Trading date, e.g. 20260604")
    parser.add_argument("--rt-data-dir", default="rt_data", help="Base rt_data directory")
    parser.add_argument("--model-dir", default="neural/models/jepa/jepa_production_final_180m")
    parser.add_argument("--tickers", nargs="+", default=["SPX", "QQQ", "SPY"])
    parser.add_argument("--entry-cutoff", default="14:30")
    parser.add_argument("--zero-pct-min", type=float, default=0.95)
    parser.add_argument("--out-dir", default="/tmp")
    args = parser.parse_args()

    rt_day_dir = Path(args.rt_data_dir) / args.date
    model_dir = Path(args.model_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    audits = []
    suspects = []
    overall_ok = True
    for ticker in args.tickers:
        audit, suspect, ok = audit_ticker(rt_day_dir, model_dir, ticker.upper(), args.entry_cutoff, args.zero_pct_min)
        if not audit.empty:
            audits.append(audit)
        if not suspect.empty:
            suspects.append(suspect)
        overall_ok = overall_ok and ok

    if audits:
        all_audit = pd.concat(audits, ignore_index=True)
        audit_path = out_dir / f"live_jepa_feature_audit_{args.date}.csv"
        all_audit.to_csv(audit_path, index=False)
        print(f"\nSaved full audit: {audit_path}")
    if suspects:
        all_suspects = pd.concat(suspects, ignore_index=True).sort_values(["ticker", "gain"], ascending=[True, False])
        suspect_path = out_dir / f"live_jepa_feature_suspects_{args.date}.csv"
        all_suspects.to_csv(suspect_path, index=False)
        print(f"Saved suspects: {suspect_path}")

    if not overall_ok:
        print("\nAUDIT FAILED: live context is not safe for new entries.")
        return 2
    print("\nAUDIT PASSED: critical live context features look safe.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
