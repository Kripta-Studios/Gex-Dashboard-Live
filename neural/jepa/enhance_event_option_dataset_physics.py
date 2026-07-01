from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_DELTAS = (15, 25, 35, 50, 65, 80)
INDEX_TICKERS = ("SPXW", "SPY", "QQQ")


def safe_num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce").astype(float)


def ratio_skew(left: pd.Series, right: pd.Series) -> pd.Series:
    denom = left.abs() + right.abs() + 1e-9
    return (left - right) / denom


def add_option_physics(df: pd.DataFrame, deltas: tuple[int, ...]) -> pd.DataFrame:
    out = df.copy()
    call_vols = []
    put_vols = []
    call_ois = []
    put_ois = []
    call_ivs = []
    put_ivs = []
    call_mids = []
    put_mids = []

    for delta in deltas:
        prefix = f"d{int(delta):02d}"
        call_iv = safe_num(out, f"call_{prefix}_iv")
        put_iv = safe_num(out, f"put_{prefix}_iv")
        call_vol = safe_num(out, f"call_{prefix}_volume")
        put_vol = safe_num(out, f"put_{prefix}_volume")
        call_oi = safe_num(out, f"call_{prefix}_oi")
        put_oi = safe_num(out, f"put_{prefix}_oi")
        call_mid = safe_num(out, f"call_{prefix}_mid_bps")
        put_mid = safe_num(out, f"put_{prefix}_mid_bps")
        call_spread = safe_num(out, f"call_{prefix}_spread_pct")
        put_spread = safe_num(out, f"put_{prefix}_spread_pct")
        call_theta = safe_num(out, f"call_{prefix}_theta_over_mid")
        put_theta = safe_num(out, f"put_{prefix}_theta_over_mid")
        call_vega = safe_num(out, f"call_{prefix}_vega")
        put_vega = safe_num(out, f"put_{prefix}_vega")
        call_abs_delta = safe_num(out, f"call_{prefix}_abs_delta")
        put_abs_delta = safe_num(out, f"put_{prefix}_abs_delta")

        out[f"phys_{prefix}_iv_skew_put_minus_call"] = put_iv - call_iv
        out[f"phys_{prefix}_iv_mean"] = (put_iv + call_iv) / 2.0
        out[f"phys_{prefix}_volume_skew_call_minus_put"] = ratio_skew(call_vol, put_vol)
        out[f"phys_{prefix}_oi_skew_call_minus_put"] = ratio_skew(call_oi, put_oi)
        out[f"phys_{prefix}_mid_skew_call_minus_put"] = ratio_skew(call_mid, put_mid)
        out[f"phys_{prefix}_spread_mean"] = (call_spread + put_spread) / 2.0
        out[f"phys_{prefix}_theta_skew_call_minus_put"] = call_theta - put_theta
        out[f"phys_{prefix}_vega_skew_call_minus_put"] = ratio_skew(call_vega, put_vega)
        out[f"phys_{prefix}_abs_delta_gap"] = call_abs_delta - put_abs_delta
        out[f"phys_{prefix}_liquidity_score"] = np.log1p(call_vol.fillna(0.0) + put_vol.fillna(0.0)) + np.log1p(call_oi.fillna(0.0) + put_oi.fillna(0.0))

        call_vols.append(call_vol)
        put_vols.append(put_vol)
        call_ois.append(call_oi)
        put_ois.append(put_oi)
        call_ivs.append(call_iv)
        put_ivs.append(put_iv)
        call_mids.append(call_mid)
        put_mids.append(put_mid)

    if call_vols:
        total_call_vol = pd.concat(call_vols, axis=1).sum(axis=1, skipna=True)
        total_put_vol = pd.concat(put_vols, axis=1).sum(axis=1, skipna=True)
        total_call_oi = pd.concat(call_ois, axis=1).sum(axis=1, skipna=True)
        total_put_oi = pd.concat(put_ois, axis=1).sum(axis=1, skipna=True)
        out["phys_total_volume_skew_call_minus_put"] = ratio_skew(total_call_vol, total_put_vol)
        out["phys_total_oi_skew_call_minus_put"] = ratio_skew(total_call_oi, total_put_oi)
        out["phys_total_option_volume_log"] = np.log1p(total_call_vol.fillna(0.0) + total_put_vol.fillna(0.0))
        out["phys_total_option_oi_log"] = np.log1p(total_call_oi.fillna(0.0) + total_put_oi.fillna(0.0))

    if len(deltas) >= 2:
        low = int(min(deltas))
        high = int(max(deltas))
        out["phys_call_iv_slope_low_to_high"] = safe_num(out, f"call_d{high:02d}_iv") - safe_num(out, f"call_d{low:02d}_iv")
        out["phys_put_iv_slope_low_to_high"] = safe_num(out, f"put_d{high:02d}_iv") - safe_num(out, f"put_d{low:02d}_iv")
        out["phys_call_mid_slope_low_to_high"] = safe_num(out, f"call_d{high:02d}_mid_bps") - safe_num(out, f"call_d{low:02d}_mid_bps")
        out["phys_put_mid_slope_low_to_high"] = safe_num(out, f"put_d{high:02d}_mid_bps") - safe_num(out, f"put_d{low:02d}_mid_bps")

    return out


def add_level_physics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    up_cols = [c for c in ["dist_fib_127_up_bps", "dist_fib_161_up_bps", "dist_fib_200_up_bps"] if c in out]
    dn_cols = [c for c in ["dist_fib_127_dn_bps", "dist_fib_161_dn_bps", "dist_fib_200_dn_bps"] if c in out]
    ib_cols = [c for c in ["dist_ib_high_bps", "dist_ib_low_bps"] if c in out]

    if up_cols:
        up = out[up_cols].apply(pd.to_numeric, errors="coerce")
        out["phys_fib_up_min_abs_bps"] = up.abs().min(axis=1)
        out["phys_fib_up_mean_signed_bps"] = up.mean(axis=1)
    if dn_cols:
        dn = out[dn_cols].apply(pd.to_numeric, errors="coerce")
        out["phys_fib_dn_min_abs_bps"] = dn.abs().min(axis=1)
        out["phys_fib_dn_mean_signed_bps"] = dn.mean(axis=1)
    if up_cols and dn_cols:
        all_fib = out[up_cols + dn_cols].apply(pd.to_numeric, errors="coerce")
        out["phys_fib_any_min_abs_bps"] = all_fib.abs().min(axis=1)
    if ib_cols:
        ib = out[ib_cols].apply(pd.to_numeric, errors="coerce")
        out["phys_ib_edge_min_abs_bps"] = ib.abs().min(axis=1)
        if {"dist_ib_high_bps", "dist_ib_low_bps"}.issubset(out.columns):
            high = safe_num(out, "dist_ib_high_bps")
            low = safe_num(out, "dist_ib_low_bps")
            out["phys_ib_balance"] = (high + low) / (high.abs() + low.abs() + 1e-9)
    if "nearest_level_abs_bps" in out.columns and "ib_range_bps" in out.columns:
        out["phys_nearest_level_vs_ib_range"] = safe_num(out, "nearest_level_abs_bps") / (safe_num(out, "ib_range_bps").abs() + 1e-9)

    for short, long in [("ret_1m_bps", "ret_5m_bps"), ("ret_5m_bps", "ret_15m_bps"), ("ret_15m_bps", "ret_30m_bps")]:
        if short in out.columns and long in out.columns:
            out[f"phys_momentum_accel_{short}_minus_{long}"] = safe_num(out, short) - safe_num(out, long)
            out[f"phys_abs_{short}"] = safe_num(out, short).abs()
    if "ret_30m_bps" in out.columns:
        out["phys_abs_ret_30m_bps"] = safe_num(out, "ret_30m_bps").abs()
    return out


def add_intraday_state(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out = out.sort_values(["ticker", "trade_date", "minute"]).reset_index(drop=True)
    group = out.groupby(["ticker", "trade_date"], sort=False)
    out["phys_event_seq_in_day"] = group.cumcount().astype(float)
    counts = group["minute"].transform("count").astype(float)
    out["phys_event_frac_in_day"] = out["phys_event_seq_in_day"] / (counts - 1.0).replace(0.0, np.nan)
    first_minute = group["minute"].transform("min")
    out["phys_minutes_since_first_event"] = safe_num(out, "minute") - pd.to_numeric(first_minute, errors="coerce")
    first_spot = group["spot"].transform("first") if "spot" in out.columns else np.nan
    out["phys_spot_ret_from_first_event_bps"] = np.log(safe_num(out, "spot") / pd.to_numeric(first_spot, errors="coerce").replace(0.0, np.nan)) * 10000.0
    out["phys_same_day_event_count"] = counts
    return out


def add_cross_index_context(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    keys = ["trade_date", "minute"]
    context_cols = [
        "spot",
        "ret_1m_bps",
        "ret_5m_bps",
        "ret_15m_bps",
        "ret_30m_bps",
        "ib_range_bps",
        "nearest_level_abs_bps",
        "phys_d35_iv_skew_put_minus_call",
        "phys_total_volume_skew_call_minus_put",
        "phys_total_oi_skew_call_minus_put",
    ]
    available = [c for c in context_cols if c in out.columns]
    base_index = out.set_index(keys)
    for ticker in INDEX_TICKERS:
        part = out[out["ticker"].astype(str).str.upper() == ticker].set_index(keys)
        if part.empty:
            continue
        part = part[available].apply(pd.to_numeric, errors="coerce")
        part = part[~part.index.duplicated(keep="first")]
        prefix = ticker.lower().replace("spxw", "spx")
        for col in available:
            mapped = base_index.index.map(part[col].to_dict())
            out[f"ctx_{prefix}_{col}"] = np.asarray(mapped, dtype=float)
            if col.startswith("ret_") and col in out.columns:
                out[f"ctx_{prefix}_{col}_minus_self"] = out[f"ctx_{prefix}_{col}"] - safe_num(out, col)
    if {"ctx_spy_ret_5m_bps", "ctx_qqq_ret_5m_bps"}.issubset(out.columns):
        out["ctx_spy_qqq_ret_5m_spread"] = safe_num(out, "ctx_spy_ret_5m_bps") - safe_num(out, "ctx_qqq_ret_5m_bps")
    if {"ctx_spx_ret_5m_bps", "ctx_spy_ret_5m_bps"}.issubset(out.columns):
        out["ctx_spx_spy_ret_5m_spread"] = safe_num(out, "ctx_spx_ret_5m_bps") - safe_num(out, "ctx_spy_ret_5m_bps")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Add causal physical and cross-index features to an event option dataset.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--deltas", nargs="+", type=int, default=list(DEFAULT_DELTAS))
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(input_path)
    before_cols = set(df.columns)
    out = add_option_physics(df, tuple(int(d) for d in args.deltas))
    out = add_level_physics(out)
    out = add_intraday_state(out)
    out = add_cross_index_context(out)
    new_cols = [c for c in out.columns if c not in before_cols]
    leaky_new = [c for c in new_cols if any(token in c.lower() for token in ["future", "opt_exit", "opt_max", "opt_min", "opt_win", "status"])]
    if leaky_new:
        raise RuntimeError(f"new feature columns look leaky: {leaky_new}")
    out.to_parquet(output_path, index=False)
    summary = {
        "input": str(input_path),
        "output": str(output_path),
        "rows": int(len(out)),
        "columns_before": int(len(before_cols)),
        "columns_after": int(len(out.columns)),
        "new_columns": new_cols,
        "leaky_new_columns": leaky_new,
        "tickers": sorted(out["ticker"].astype(str).unique().tolist()) if "ticker" in out.columns else [],
        "date_min": str(out["trade_date"].min()) if "trade_date" in out.columns else "",
        "date_max": str(out["trade_date"].max()) if "trade_date" in out.columns else "",
    }
    summary_path = Path(args.summary) if args.summary else output_path.with_name("physics_feature_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
