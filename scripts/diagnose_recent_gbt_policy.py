import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "neural"))
sys.path.insert(0, str(ROOT / "backtest"))

from hybrid_model import FEATURE_COLUMNS, load_ensemble_model
from backtest_rl import calculate_metrics, simulate_mlp_only


def _month_stats(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    out = trades.copy()
    out["month"] = out["date"].astype(str).str[:4] + "-" + out["date"].astype(str).str[4:6]
    g = out.groupby("month").agg(
        trades=("pnl_dollars", "size"),
        pnl=("pnl_dollars", "sum"),
        wr=("pnl_dollars", lambda s: (s > 0).mean()),
        gp=("pnl_dollars", lambda s: s[s > 0].sum()),
        gl=("pnl_dollars", lambda s: -s[s < 0].sum()),
    )
    g["pf"] = g["gp"] / g["gl"].replace(0, np.nan)
    return g


def _week_stats(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    out = trades.copy()
    dates = pd.to_datetime(out["date"].astype(str), format="%Y%m%d")
    iso = dates.dt.isocalendar()
    out["week"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    g = out.groupby("week").agg(
        trades=("pnl_dollars", "size"),
        pnl=("pnl_dollars", "sum"),
        wr=("pnl_dollars", lambda s: (s > 0).mean()),
        gp=("pnl_dollars", lambda s: s[s > 0].sum()),
        gl=("pnl_dollars", lambda s: -s[s < 0].sum()),
    )
    g["pf"] = g["gp"] / g["gl"].replace(0, np.nan)
    return g


def _filter_models(model, min_pf: float):
    if min_pf <= 0:
        return model
    before = len(model.models)
    model.models = [
        m for m in model.models
        if float(m.metadata.get("avg_pf", 0.0)) >= min_pf
    ]
    print(f"[filter] avg_pf >= {min_pf:.3f}: {before} -> {len(model.models)} models")
    return model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ROOT / "training_data" / "training_data_spx_qqq_spy.parquet"))
    parser.add_argument("--model", default=str(ROOT / "neural" / "models" / "trading_hybrid_wf_history.joblib"))
    parser.add_argument("--normalizer", default=str(ROOT / "neural" / "models" / "hybrid_normalizer_wf.npz"))
    parser.add_argument("--start-date", default="20260301")
    parser.add_argument("--end-date", default="20260515")
    parser.add_argument("--tickers", nargs="+", default=["SPX", "QQQ", "SPY"])
    parser.add_argument("--min-window-pf", type=float, default=0.0)
    parser.add_argument("--min-entry-minute", type=int, default=580)
    parser.add_argument("--min-short-entry-minute", type=int, default=None)
    parser.add_argument("--min-short-price-vs-ib-high", type=float, default=None)
    parser.add_argument("--thresholds", nargs="+", type=float, default=[0.55, 0.575, 0.60, 0.625, 0.65, 0.70])
    args = parser.parse_args()

    model, normalizer = load_ensemble_model(args.model, args.normalizer, "small")
    model = _filter_models(model, args.min_window_pf)

    df = pd.read_parquet(args.data)
    df["date"] = df["date"].astype(str)
    df = df[(df["date"] >= args.start_date) & (df["date"] <= args.end_date)].copy()
    df = df[df["ticker"].isin(args.tickers)].reset_index(drop=True)
    print(f"[data] {len(df):,} rows | {df['date'].nunique()} days | tickers={sorted(df['ticker'].unique())}")

    features = np.zeros((len(df), len(FEATURE_COLUMNS)), dtype=np.float32)
    for i, col in enumerate(FEATURE_COLUMNS):
        if col in df.columns:
            features[:, i] = df[col].astype(np.float32).values
    features = np.nan_to_num(features, nan=0.0, posinf=5.0, neginf=-5.0)

    probs = np.zeros((len(df), 3), dtype=np.float32)
    for d_str in sorted(df["date"].unique()):
        idx = np.where(df["date"].values == d_str)[0]
        probs[idx] = model.predict_proba(features[idx], date=str(d_str))
    preds = probs.argmax(axis=1)
    print(f"[pred] {np.bincount(preds, minlength=3).tolist()} [SHORT,HOLD,LONG]")

    for tickers in [args.tickers, [t for t in args.tickers if t != "SPY"]]:
        mask = df["ticker"].isin(tickers).values
        print("\n" + "=" * 80)
        print(f"Tickers: {tickers}")
        print("=" * 80)
        for threshold in args.thresholds:
            trades = simulate_mlp_only(
                df.loc[mask].reset_index(drop=True),
                preds[mask],
                probs[mask],
                threshold=threshold,
                target_long=0.010,
                target_short=0.010,
                stop_pct=0.003,
                max_time=180,
                cooldown=15,
                risk_capital=1000.0,
                min_entry_minute=args.min_entry_minute,
                min_short_entry_minute=args.min_short_entry_minute,
                min_short_price_vs_ib_high=args.min_short_price_vs_ib_high,
            )
            metrics = calculate_metrics(trades)
            if "error" in metrics:
                print(f"threshold={threshold:.3f}: no trades")
                continue
            months = _month_stats(trades)
            weeks = _week_stats(trades)
            min_week_trades = int(weeks["trades"].min()) if not weeks.empty else 0
            print(
                f"\nthreshold={threshold:.3f} total: "
                f"trades={metrics['total']} WR={metrics['win_rate']:.1f}% "
                f"PF={metrics['pf']:.2f} PnL={metrics['total_pnl']:+.1f} "
                f"min_week_trades={min_week_trades}"
            )
            print(months[["trades", "wr", "pf", "pnl"]].round(3).to_string())
            weak_weeks = weeks[weeks["trades"] < 6]
            if not weak_weeks.empty:
                print("[volume] weeks below 6 trades:")
                print(weak_weeks[["trades", "wr", "pf", "pnl"]].round(3).to_string())


if __name__ == "__main__":
    main()
