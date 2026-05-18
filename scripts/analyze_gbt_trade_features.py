import argparse
from pathlib import Path

import numpy as np
import pandas as pd


FEATURES = [
    "ret_1m_vol_adj",
    "ret_5m_vol_adj",
    "ret_15m_vol_adj",
    "rsi",
    "wonham_trend_prob",
    "price_vs_ib_high",
    "price_vs_ib_low",
    "above_ib",
    "below_ib",
    "in_ib_range",
    "vix_spot",
    "vix_regime",
    "rvol_trend",
    "minutes_to_close_norm",
]


def _month_stats(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["month"] = out["date"].astype(str).str[:6]
    return out.groupby(["month", "direction"]).agg(
        trades=("pnl_dollars", "size"),
        wr=("pnl_dollars", lambda s: (s > 0).mean()),
        pnl=("pnl_dollars", "sum"),
        avg_conf=("confidence", "mean"),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trades", required=True)
    parser.add_argument("--data", default="training_data/training_data_spx_qqq_spy.parquet")
    parser.add_argument("--start-date", default="20260301")
    parser.add_argument("--end-date", default="20260531")
    args = parser.parse_args()

    trades = pd.read_csv(args.trades)
    trades["date"] = trades["date"].astype(str)
    trades = trades[(trades["date"] >= args.start_date) & (trades["date"] <= args.end_date)].copy()
    trades["entry_key"] = (
        trades["date"].astype(str)
        + "|"
        + trades["ticker"].astype(str)
        + "|"
        + trades["entry_time"].astype(str)
    )

    cols = ["date", "ticker", "time"] + [f for f in FEATURES if f]
    data = pd.read_parquet(args.data, columns=[c for c in cols if c != "time"] + ["time"])
    data["date"] = data["date"].astype(str)
    data = data[(data["date"] >= args.start_date) & (data["date"] <= args.end_date)].copy()
    data["entry_key"] = data["date"].astype(str) + "|" + data["ticker"].astype(str) + "|" + data["time"].astype(str)

    merged = trades.merge(
        data.drop_duplicates("entry_key"),
        on="entry_key",
        how="left",
        suffixes=("", "_row"),
    )

    print(f"trades={len(trades)} merged={merged[FEATURES].notna().any(axis=1).sum()}")
    print("\nMONTH/DIRECTION")
    print(_month_stats(merged).round(3).to_string())

    print("\nFEATURE MEANS BY WIN/LOSS")
    merged["win"] = merged["pnl_dollars"] > 0
    for direction in ["LONG", "SHORT"]:
        sub = merged[merged["direction"] == direction]
        if sub.empty:
            continue
        print(f"\n{direction}")
        rows = []
        for feat in FEATURES:
            if feat not in sub.columns:
                continue
            vals = pd.to_numeric(sub[feat], errors="coerce")
            if vals.notna().sum() < 10:
                continue
            w = vals[sub["win"]].dropna()
            l = vals[~sub["win"]].dropna()
            if w.empty or l.empty:
                continue
            rows.append({
                "feature": feat,
                "win_mean": w.mean(),
                "loss_mean": l.mean(),
                "diff": w.mean() - l.mean(),
                "win_q25": w.quantile(0.25),
                "loss_q25": l.quantile(0.25),
                "win_q75": w.quantile(0.75),
                "loss_q75": l.quantile(0.75),
            })
        print(pd.DataFrame(rows).sort_values("diff", key=np.abs, ascending=False).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
