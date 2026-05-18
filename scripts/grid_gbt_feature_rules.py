import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "neural"))
sys.path.insert(0, str(ROOT / "backtest"))

from hybrid_model import FEATURE_COLUMNS, load_ensemble_model
from backtest_rl import calculate_metrics, simulate_mlp_only


def _month_stats(trades: pd.DataFrame) -> dict[str, dict]:
    out = {}
    if trades.empty:
        return out
    work = trades.copy()
    work["month"] = work["date"].astype(str).str[:6]
    for month, g in work.groupby("month"):
        pnl = g["pnl_dollars"].astype(float)
        gp = pnl[pnl > 0].sum()
        gl = -pnl[pnl < 0].sum()
        pf = gp / gl if gl > 0 else (999.0 if gp > 0 else 0.0)
        out[month] = {
            "n": int(len(g)),
            "wr": float((pnl > 0).mean() * 100),
            "pf": float(pf),
            "pnl": float(pnl.sum()),
        }
    return out


def _week_min(trades: pd.DataFrame) -> int:
    if trades.empty:
        return 0
    dates = pd.to_datetime(trades["date"].astype(str), format="%Y%m%d")
    iso = dates.dt.isocalendar()
    weeks = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    return int(weeks.value_counts().min()) if len(weeks) else 0


def _apply_rule(df: pd.DataFrame, preds: np.ndarray, rule: str) -> np.ndarray:
    out = preds.copy()
    direction = np.where(out == 0, "SHORT", np.where(out == 2, "LONG", "HOLD"))

    if rule == "none":
        return out

    if rule == "trend5":
        bad = ((direction == "LONG") & (df["ret_5m_vol_adj"] < 0.0)) | (
            (direction == "SHORT") & (df["ret_5m_vol_adj"] > 0.0)
        )
    elif rule == "trend15":
        bad = ((direction == "LONG") & (df["ret_15m_vol_adj"] < 0.0)) | (
            (direction == "SHORT") & (df["ret_15m_vol_adj"] > 0.0)
        )
    elif rule == "trend5_soft":
        bad = ((direction == "LONG") & (df["ret_5m_vol_adj"] < -0.25)) | (
            (direction == "SHORT") & (df["ret_5m_vol_adj"] > 0.25)
        )
    elif rule == "short_trend5":
        bad = (direction == "SHORT") & (df["ret_5m_vol_adj"] > 0.0)
    elif rule == "short_trend5_soft":
        bad = (direction == "SHORT") & (df["ret_5m_vol_adj"] > 0.25)
    elif rule == "short_ib_high_-80":
        bad = (direction == "SHORT") & (df["price_vs_ib_high"] < -80.0)
    elif rule == "short_ib_high_-60":
        bad = (direction == "SHORT") & (df["price_vs_ib_high"] < -60.0)
    elif rule == "short_ib_high_-40":
        bad = (direction == "SHORT") & (df["price_vs_ib_high"] < -40.0)
    elif rule == "short_trend5_soft_ib_-80":
        bad = (direction == "SHORT") & (
            (df["ret_5m_vol_adj"] > 0.25) | (df["price_vs_ib_high"] < -80.0)
        )
    elif rule == "short_trend5_soft_ib_-60":
        bad = (direction == "SHORT") & (
            (df["ret_5m_vol_adj"] > 0.25) | (df["price_vs_ib_high"] < -60.0)
        )
    elif rule == "ib_context":
        bad = ((direction == "LONG") & (df["price_vs_ib_low"] > 25.0)) | (
            (direction == "SHORT") & (df["price_vs_ib_high"] < -80.0)
        )
    else:
        raise ValueError(f"unknown rule {rule}")

    out[np.asarray(bad.fillna(False), dtype=bool)] = 1
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ROOT / "training_data" / "training_data_spx_qqq_spy.parquet"))
    parser.add_argument("--model", default=str(ROOT / "neural" / "models" / "codex_exp" / "gbt_18m_econ_pf150_minsel10_avail_history.joblib"))
    parser.add_argument("--normalizer", default=str(ROOT / "neural" / "models" / "codex_exp" / "gbt_18m_econ_pf150_minsel10_avail_norm.npz"))
    parser.add_argument("--start-date", default="20260301")
    parser.add_argument("--end-date", default="20260531")
    parser.add_argument("--threshold", type=float, default=0.475)
    parser.add_argument("--target-long", type=float, default=0.010)
    parser.add_argument("--target-short", type=float, default=0.010)
    parser.add_argument("--stop", type=float, default=0.003)
    parser.add_argument("--min-entry-minute", type=int, default=580)
    parser.add_argument("--min-short-entry-minute", type=int, default=615)
    parser.add_argument("--rules", nargs="+", default=[
        "none",
        "trend5",
        "trend15",
        "trend5_soft",
        "short_trend5",
        "short_trend5_soft",
        "short_ib_high_-80",
        "short_ib_high_-60",
        "short_ib_high_-40",
        "short_trend5_soft_ib_-80",
        "short_trend5_soft_ib_-60",
        "ib_context",
    ])
    args = parser.parse_args()

    df = pd.read_parquet(args.data)
    df["date"] = df["date"].astype(str)
    df = df[(df["date"] >= args.start_date) & (df["date"] <= args.end_date)].copy()
    df = df[df["ticker"].isin(["SPX", "QQQ", "SPY"])].reset_index(drop=True)

    model, normalizer = load_ensemble_model(args.model, args.normalizer, "small")
    features = np.zeros((len(df), len(FEATURE_COLUMNS)), dtype=np.float32)
    for i, col in enumerate(FEATURE_COLUMNS):
        if col in df.columns:
            features[:, i] = df[col].astype(np.float32).values
    features = np.nan_to_num(features, nan=0.0, posinf=5.0, neginf=-5.0)

    probs = np.zeros((len(df), 3), dtype=np.float32)
    for d_str in sorted(df["date"].unique()):
        idx = np.where(df["date"].values == d_str)[0]
        probs[idx] = model.predict_proba(features[idx], date=str(d_str))
    raw_preds = probs.argmax(axis=1)

    print(f"data={len(df):,} days={df['date'].nunique()} threshold={args.threshold}")
    for rule in args.rules:
        preds = _apply_rule(df, raw_preds, rule)
        trades = simulate_mlp_only(
            df,
            preds,
            probs,
            threshold=args.threshold,
            target_long=args.target_long,
            target_short=args.target_short,
            stop_pct=args.stop,
            max_time=180,
            cooldown=15,
            risk_capital=1000.0,
            min_entry_minute=args.min_entry_minute,
            min_short_entry_minute=args.min_short_entry_minute,
        )
        metrics = calculate_metrics(trades)
        if "error" in metrics:
            print(f"{rule}: no trades")
            continue
        months = _month_stats(trades)
        apr = months.get("202604", {})
        may = months.get("202605", {})
        print(
            f"{rule}: n={metrics['total']} WR={metrics['win_rate']:.1f} "
            f"PF={metrics['pf']:.3f} pnl={metrics['total_pnl']:+.0f} "
            f"minw={_week_min(trades)} | "
            f"Apr n={apr.get('n',0)} WR={apr.get('wr',0):.1f} PF={apr.get('pf',0):.3f} pnl={apr.get('pnl',0):+.0f} | "
            f"May n={may.get('n',0)} WR={may.get('wr',0):.1f} PF={may.get('pf',0):.3f} pnl={may.get('pnl',0):+.0f}"
        )


if __name__ == "__main__":
    main()
