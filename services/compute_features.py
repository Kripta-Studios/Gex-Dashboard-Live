"""
Shared feature computation module — used by both training and live bot.

Centralizes Greek exposure calculations from raw options chain data
so that training (collect_training_data_parquet.py) and live execution
(tradingbot_wrapper_rl.py) produce identical features.
"""

import numpy as np
import pandas as pd
import sys, os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from training_data.stats import (
    calc_dp_cdf_pdf, calc_gamma_ex, calc_vanna_ex, calc_charm_ex,
    calc_vega_ex, calc_vomma_ex, calc_zomma_ex, calc_delta_ex,
    calc_delta_adjusted_gex,
)

R_RATE = 0.0325
Q_DIV = 0.0150


def calculate_exact_t(series_dt):
    """Time-to-expiry fraction of year, assuming 16:00 close."""
    if hasattr(series_dt, 'dt'):
        target_close = series_dt.dt.normalize() + pd.Timedelta(hours=16)
        seconds_left = (target_close - series_dt).dt.total_seconds()
    else:
        target_close = series_dt.normalize() + pd.Timedelta(hours=16)
        seconds_left = (target_close - series_dt).total_seconds()
    seconds_left = np.where(seconds_left < 60, 60, seconds_left)
    return seconds_left / (3600 * 24 * 365.25)


def get_net_exposures_from_parquet(df, spot_col='underlying_price'):
    """
    Compute net Greek exposures from a per-strike DataFrame.

    Expected df columns: underlying_price, strike, implied_vol, open_interest,
                         right (CALL/PUT), T (time-to-expiry from calculate_exact_t).

    Returns dict with net_gamma, net_vanna, etc. + max/min strike levels.
    """
    if df.empty:
        return None

    spot = df[spot_col].iloc[0]
    S = df['underlying_price'].values.astype(np.float64)
    K = df['strike'].values.astype(np.float64)
    vol = np.where(df['implied_vol'].values <= 0, 0.0001, df['implied_vol'].values).astype(np.float64)
    oi = df['open_interest'].values.astype(np.float64)
    T_arr = df['T'].values.astype(np.float64)

    is_put = (df['right'].str.upper() == 'PUT').values

    dp, cdf_dp, pdf_dp = calc_dp_cdf_pdf(S, K, vol, T_arr, R_RATE, Q_DIV)

    g_vals = calc_gamma_ex(S, vol, T_arr, Q_DIV, oi, pdf_dp)
    v_vals = calc_vanna_ex(S, vol, T_arr, Q_DIV, oi, dp, pdf_dp)
    vega_vals = calc_vega_ex(S, vol, T_arr, Q_DIV, oi, pdf_dp)
    vomma_vals = calc_vomma_ex(vega_vals, dp, vol, T_arr)
    zomma_vals = calc_zomma_ex(g_vals, dp, vol, T_arr)

    c_vals_call = calc_charm_ex(S, vol, T_arr, R_RATE, Q_DIV, "call", oi, dp, cdf_dp, pdf_dp)
    c_vals_put  = calc_charm_ex(S, vol, T_arr, R_RATE, Q_DIV, "put",  oi, dp, cdf_dp, pdf_dp)
    c_vals = np.where(is_put, c_vals_put, c_vals_call)

    d_vals_call = calc_delta_ex(S, T_arr, Q_DIV, "call", oi, cdf_dp)
    d_vals_put  = calc_delta_ex(S, T_arr, Q_DIV, "put",  oi, cdf_dp)
    d_vals = np.where(is_put, d_vals_put, d_vals_call)

    dgex_call = calc_delta_adjusted_gex(g_vals, cdf_dp, T_arr, Q_DIV, "call")
    dgex_put  = calc_delta_adjusted_gex(g_vals, cdf_dp, T_arr, Q_DIV, "put")
    dgex_vals = np.where(is_put, -dgex_put, dgex_call)

    # Per-strike net (sign convention)
    df = df.copy()
    df['pq_net_gamma'] = np.where(is_put, -g_vals, g_vals)
    df['pq_net_vanna'] = v_vals
    df['pq_net_charm'] = c_vals
    df['pq_net_vega']  = vega_vals
    df['pq_net_vomma'] = vomma_vals
    df['pq_net_zomma'] = np.where(is_put, -zomma_vals, zomma_vals)
    df['pq_net_delta'] = d_vals
    df['pq_net_dgex']  = dgex_vals

    df_clean = df[(df['implied_vol'] < 2.0) & (df['open_interest'] > 0)].copy()

    def get_max_min_strike(col):
        grouped = df_clean.groupby('strike')[col].sum()
        if grouped.empty:
            return 0.0, 0.0
        return float(grouped.idxmax()), float(grouped.idxmin())

    max_gamma, min_gamma = get_max_min_strike('pq_net_gamma')
    max_vanna, min_vanna = get_max_min_strike('pq_net_vanna')
    max_dgex,  min_dgex  = get_max_min_strike('pq_net_dgex')
    max_zomma, min_zomma = get_max_min_strike('pq_net_zomma')
    max_vega,  min_vega  = get_max_min_strike('pq_net_vega')
    max_vomma, min_vomma = get_max_min_strike('pq_net_vomma')

    gamma_by_strike = df_clean.groupby('strike')['pq_net_gamma'].sum()
    zero_gamma_strike = float(gamma_by_strike.abs().idxmin()) if not gamma_by_strike.empty else 0.0

    return {
        "spot_price": spot,
        "net_gamma":  df['pq_net_gamma'].sum(),
        "net_vanna":  df['pq_net_vanna'].sum(),
        "net_charm":  df['pq_net_charm'].sum(),
        "net_dgex":   df['pq_net_dgex'].sum(),
        "net_zomma":  df['pq_net_zomma'].sum(),
        "net_delta":  df['pq_net_delta'].sum(),
        "net_vega":   df['pq_net_vega'].sum(),
        "net_vomma":  df['pq_net_vomma'].sum(),

        "max_gamma_strike": max_gamma,  "min_gamma_strike": min_gamma,
        "max_vanna_strike": max_vanna,  "min_vanna_strike": min_vanna,
        "max_dgex_strike":  max_dgex,   "min_dgex_strike":  min_dgex,
        "max_zomma_strike": max_zomma,  "min_zomma_strike": min_zomma,
        "max_vega_strike":  max_vega,   "min_vega_strike":  min_vega,
        "max_vomma_strike": max_vomma,  "min_vomma_strike": min_vomma,
        "zero_gamma": zero_gamma_strike,
        # Keep the annotated df for callers that need per-strike data
        "_df": df,
    }
