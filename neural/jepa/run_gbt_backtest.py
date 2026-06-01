from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NEURAL_ROOT = PROJECT_ROOT / "neural"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(NEURAL_ROOT) not in sys.path:
    sys.path.insert(0, str(NEURAL_ROOT))

from backtest.backtest_gbt_parquet import TradeSimulator, calculate_metrics, print_by_ticker, print_metrics
from hybrid_model import FEATURE_COLUMNS, get_device, load_ensemble_model, load_hybrid_model
from neural.jepa.features import load_feature_names
from neural.signal_policy import get_independent_signals


def build_feature_matrix(df: pd.DataFrame, feature_names: list[str]) -> np.ndarray:
    x = np.zeros((len(df), len(feature_names)), dtype=np.float32)
    for i, col in enumerate(feature_names):
        if col in df.columns:
            x[:, i] = df[col].values.astype(np.float32, copy=False)
    return np.nan_to_num(x, nan=0.0, posinf=5.0, neginf=-5.0)


def apply_group_permutation(
    df: pd.DataFrame,
    feature_names: list[str],
    seed: int,
    group_by_ticker: bool = True,
) -> pd.DataFrame:
    cols = [c for c in feature_names if c in df.columns]
    if not cols:
        return df
    out = df.copy()
    rng = np.random.default_rng(seed)
    if group_by_ticker and "ticker" in out.columns:
        for _, idx in out.groupby("ticker").groups.items():
            idx = np.asarray(list(idx))
            shuffled = idx.copy()
            rng.shuffle(shuffled)
            out.loc[idx, cols] = out.loc[shuffled, cols].to_numpy()
    else:
        idx = np.arange(len(out))
        shuffled = idx.copy()
        rng.shuffle(shuffled)
        out.loc[:, cols] = out.iloc[shuffled][cols].to_numpy()
    return out


def load_models(model_path: str, normalizer_path: str, model_size: str, ensemble: bool):
    device = get_device()
    ticker_models = {}
    ticker_normalizers = {}
    tickers = ["SPX", "QQQ", "SPY"]
    for ticker in tickers:
        if "_history.joblib" in model_path:
            t_model_path = model_path.replace("_history.joblib", f"_{ticker}_history.joblib")
        else:
            t_model_path = model_path.replace(".joblib", f"_{ticker}.joblib")
        t_norm_path = normalizer_path.replace(".npz", f"_{ticker}.npz")
        if os.path.exists(t_model_path) and os.path.exists(t_norm_path):
            if ensemble:
                t_model, t_norm = load_ensemble_model(t_model_path, t_norm_path, model_size, device)
            else:
                t_model, t_norm = load_hybrid_model(t_model_path, t_norm_path, model_size, device)
            ticker_models[ticker] = t_model
            ticker_normalizers[ticker] = t_norm

    if ticker_models:
        return ticker_models, ticker_normalizers, True

    if ensemble:
        model, norm = load_ensemble_model(model_path, normalizer_path, model_size, device)
    else:
        model, norm = load_hybrid_model(model_path, normalizer_path, model_size, device)
    return model, norm, False


def predict_probs(
    df: pd.DataFrame,
    loaded_model,
    loaded_norm,
    is_ticker_specific: bool,
    strict_wf: bool,
) -> np.ndarray:
    probs = np.zeros((len(df), 3), dtype=np.float32)
    if is_ticker_specific:
        for ticker in df["ticker"].unique():
            if ticker not in loaded_model:
                print(f"[WARN] no model for ticker={ticker}; rows left HOLD")
                probs[df["ticker"] == ticker, 1] = 1.0
                continue
            mask = df["ticker"] == ticker
            idx_all = np.where(mask)[0]
            model = loaded_model[ticker]
            norm = loaded_norm[ticker]
            expected_cols = (
                norm.feature_names
                if getattr(norm, "feature_names", None) is not None and len(norm.feature_names) > 0
                else FEATURE_COLUMNS
            )
            if strict_wf:
                for date_str in sorted(df.loc[mask, "date"].unique()):
                    d_mask = mask & (df["date"] == date_str)
                    idx = np.where(d_mask)[0]
                    x = build_feature_matrix(df.iloc[idx], expected_cols)
                    probs[idx] = model.predict_proba(x, date=str(date_str))
            else:
                x = build_feature_matrix(df.iloc[idx_all], expected_cols)
                probs[idx_all] = model.predict_proba(x)
    else:
        expected_cols = (
            loaded_norm.feature_names
            if getattr(loaded_norm, "feature_names", None) is not None and len(loaded_norm.feature_names) > 0
            else FEATURE_COLUMNS
        )
        if strict_wf:
            for date_str in sorted(df["date"].unique()):
                idx = np.where(df["date"] == date_str)[0]
                x = build_feature_matrix(df.iloc[idx], expected_cols)
                probs[idx] = loaded_model.predict_proba(x, date=str(date_str))
        else:
            x = build_feature_matrix(df, expected_cols)
            probs = loaded_model.predict_proba(x)
    return probs


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest GBT models without writing shared training_data/backtest_trades.csv.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--normalizer", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--model-size", default="small")
    parser.add_argument("--threshold", type=float, default=0.40)
    parser.add_argument("--cooldown", type=int, default=8)
    parser.add_argument("--risk-capital", type=float, default=1000.0)
    parser.add_argument("--position-size", type=float, default=1.0)
    parser.add_argument("--target_long", type=float, default=0.010)
    parser.add_argument("--target_short", type=float, default=0.010)
    parser.add_argument("--stop", type=float, default=0.0025)
    parser.add_argument("--spx-target", type=float, default=0.010)
    parser.add_argument("--etf-target", type=float, default=0.006)
    parser.add_argument("--spx-stop", type=float, default=0.0025)
    parser.add_argument("--etf-stop", type=float, default=0.0030)
    parser.add_argument("--qqq-target", type=float, default=0.006)
    parser.add_argument("--spy-target", type=float, default=0.006)
    parser.add_argument("--qqq-stop", type=float, default=0.0030)
    parser.add_argument("--spy-stop", type=float, default=0.0035)
    parser.add_argument("--max-time", type=int, default=180)
    parser.add_argument("--min-entry-minute", type=int, default=580)
    parser.add_argument("--min-short-entry-minute", type=int, default=615)
    parser.add_argument("--min-short-price-vs-ib-high", type=float, default=-150.0)
    parser.add_argument("--ensemble", action="store_true")
    parser.add_argument("--strict-wf", action="store_true")
    parser.add_argument("--tickers", nargs="+", default=["SPX", "QQQ", "SPY"])
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--permute-feature-names", default=None)
    parser.add_argument("--permute-seed", type=int, default=123)
    args = parser.parse_args()

    model_path = str(Path(args.model).resolve())
    if args.strict_wf and model_path.endswith(".joblib") and not model_path.endswith("_history.joblib"):
        model_path = model_path.replace(".joblib", "_history.joblib")
    normalizer_path = str(Path(args.normalizer).resolve())
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(args.data)
    df["date"] = df["date"].astype(str)
    if args.start_date:
        df = df[df["date"] >= str(args.start_date)].copy()
    if args.end_date:
        df = df[df["date"] <= str(args.end_date)].copy()
    if args.tickers:
        df = df[df["ticker"].isin(args.tickers)].copy()
    if df.empty:
        raise ValueError("No rows after date/ticker filters")
    if args.permute_feature_names:
        perm_cols = load_feature_names(args.permute_feature_names)
        df = apply_group_permutation(df, perm_cols, args.permute_seed, group_by_ticker=True)
        print(f"[PERMUTE] columns={len(perm_cols)} seed={args.permute_seed}")

    loaded_model, loaded_norm, is_ticker_specific = load_models(
        model_path,
        normalizer_path,
        args.model_size,
        args.ensemble,
    )
    probs = predict_probs(df, loaded_model, loaded_norm, is_ticker_specific, args.strict_wf)
    predictions, _ = get_independent_signals(probs, base_confidence=args.threshold)
    print(f"[PRED] SHORT={(predictions == 0).sum():,} HOLD={(predictions == 1).sum():,} LONG={(predictions == 2).sum():,}")

    simulator = TradeSimulator(
        threshold=args.threshold,
        position_size=args.position_size,
        cooldown_minutes=args.cooldown,
        target_long=args.target_long,
        target_short=args.target_short,
        stop_pct=args.stop,
        max_time=args.max_time,
        min_iv_pct=0.0,
        discord_enabled=False,
        risk_capital=args.risk_capital,
        min_entry_minute=args.min_entry_minute,
        min_short_entry_minute=args.min_short_entry_minute,
        min_short_price_vs_ib_high=args.min_short_price_vs_ib_high,
        spx_target=args.spx_target,
        etf_target=args.etf_target,
        spx_stop=args.spx_stop,
        etf_stop=args.etf_stop,
        qqq_target=args.qqq_target,
        spy_target=args.spy_target,
        qqq_stop=args.qqq_stop,
        spy_stop=args.spy_stop,
    )
    trades_df = simulator.simulate(df, predictions, probs)
    metrics = calculate_metrics(trades_df)
    per_ticker = {}
    if not trades_df.empty:
        for ticker, tdf in trades_df.groupby("ticker"):
            per_ticker[str(ticker)] = calculate_metrics(tdf)

    print_metrics(metrics, f"{args.label} BACKTEST RESULTS")
    if not trades_df.empty:
        print_by_ticker(trades_df)

    metrics_payload = {
        "label": args.label,
        "data": args.data,
        "model": model_path,
        "normalizer": normalizer_path,
        "threshold": args.threshold,
        "strict_wf": bool(args.strict_wf),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "permuted_features": args.permute_feature_names,
        "metrics": metrics,
        "per_ticker": per_ticker,
    }
    metrics_path = out_dir / f"{args.label}_metrics.json"
    trades_path = out_dir / f"{args.label}_trades.csv"
    metrics_path.write_text(json.dumps(metrics_payload, indent=2, default=float), encoding="utf-8")
    trades_df.to_csv(trades_path, index=False)
    print(f"[WRITE] metrics={metrics_path}")
    print(f"[WRITE] trades={trades_path} rows={len(trades_df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
