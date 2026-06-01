"""
Shared feature computation module — used by both training and live bot.

Centralizes Greek exposure calculations from raw options chain data
so that training (collect_training_data_parquet.py) and live execution
(tradingbot_wrapper_rl.py) produce identical features.
"""

import numpy as np
import pandas as pd
import sys, os
import math
import calendar
from datetime import datetime
from collections import deque
from scipy.signal import hilbert as scipy_hilbert

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from training_data.stats import (
    calc_dp_cdf_pdf, calc_gamma_ex, calc_vanna_ex, calc_charm_ex,
    calc_vega_ex, calc_vomma_ex, calc_zomma_ex, calc_delta_ex,
    calc_delta_adjusted_gex,
)

R_RATE = 0.0325
Q_DIV = 0.0150
BPS_CLIP = 300.0
LEVEL_PROXIMITY_THRESHOLD = 0.0025 # 25 bps


def calculate_exact_t(series_dt):
    """Time-to-expiry fraction of year, assuming 16:00 close."""
    if hasattr(series_dt, 'dt'):
        # PD Series
        target_close = series_dt.dt.normalize() + pd.Timedelta(hours=16)
        seconds_left = (target_close - series_dt).dt.total_seconds()
    else:
        # Scalar (datetime or pd.Timestamp)
        # Ensure it has normalize method
        if not hasattr(series_dt, 'normalize'):
            series_dt = pd.Timestamp(series_dt)
        target_close = series_dt.normalize() + pd.Timedelta(hours=16)
        seconds_left = (target_close - series_dt).total_seconds()
    
    seconds_left = np.where(seconds_left < 60, 60, seconds_left)
    return seconds_left / (3600 * 24 * 365.25)


def compute_wonham_filter(prices: list,
                          lambda1: float = 0.5, lambda2: float = 0.5,
                          mu1: float = 0.002, mu2: float = -0.003,
                          sigma: float = 0.01, dt: float = 1.0/390.0,
                          p_start: float = 0.5) -> list:
    """
    Discrete Wonham Filter for regime detection.
    Computes p_t = P(trending regime) recursively.
    If p_start is provided, uses it as the initial probability.
    """
    n = len(prices)
    if n < 2:
        return [p_start] * n
    
    p = [p_start]
    mu_diff = mu1 - mu2
    sigma2 = sigma ** 2
    snr_scale = mu_diff / sigma2 if sigma2 > 0 else 0.0
    
    for t in range(n - 1):
        pt = p[t]
        if prices[t] > 0 and prices[t + 1] > 0:
            log_ret = np.log(prices[t + 1] / prices[t])
        else:
            log_ret = 0.0
        f_p = (-(lambda1 + lambda2) * pt + lambda2
               - snr_scale * pt * (1 - pt) * (mu_diff * pt + mu2 - sigma2 / 2))
        innovation = snr_scale * pt * (1 - pt) * log_ret
        p_next = pt + f_p * dt + innovation
        p_next = min(max(p_next, 0.0), 1.0)
        p.append(p_next)
    
    return p


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
    if df_clean.empty and not df.empty:
        pass

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
        "_df": df_clean  # Add this for gamma_speed
    }

def safe_log(x):
    """Safe pseudo-log for Greeks: sign(x) * log1p(abs(x))."""
    if x is None: return 0.0
    return float(np.sign(x) * np.log1p(np.abs(x)))


def inverse_safe_log(y):
    """Inverse of safe_log: sign(y) * (exp(|y|) - 1)."""
    if y is None or not np.isfinite(y):
        return 0.0
    y = float(y)
    return float(np.sign(y) * np.expm1(np.abs(y)))


def invert_delta_filtered_pcr(x):
    """Approximate raw PCR from its normalized feature representation."""
    if x is None or not np.isfinite(x):
        return 0.5
    x = float(np.clip(x, 0.0, 1.0))
    return float(np.expm1(x * np.log1p(5.0)))

def dist_bps(spot, level):
    """Distance in basis points: (spot - level) / spot * 10000."""
    if spot <= 0 or level <= 0: return 0.0
    return float((spot - level) / spot * 10000.0)

def is_near_level(spot, level, threshold_bps=15.0):
    """Check if spot is within threshold basis points of level."""
    if spot <= 0 or level <= 0: return False
    return abs(dist_bps(spot, level)) <= threshold_bps

def rbf_confluence(level1, level2, spot, sigma=0.003):
    """Gaussian confluence between two levels: exp(-(l1-l2)^2 / (2 * sigma^2 * spot^2))."""
    if level1 <= 0 or level2 <= 0 or spot <= 0: return 0.0
    diff = (level1 - level2) / spot
    return float(np.exp(-(diff**2) / (2 * sigma**2)))

def classify_gamma_regime(net_gamma):
    """Classify gamma regime: 0=Short, 1=Stable, 2=Long."""
    if net_gamma < -1.0: return 0.0
    if net_gamma > 1.0: return 2.0
    return 1.0

def sign_divergence(val1, val2):
    """1 if signs differ, else 0."""
    if (val1 > 0 and val2 < 0) or (val1 < 0 and val2 > 0): return 1.0
    return 0.0

def simple_rsi(prices, period=14):
    """Simple RSI implementation for a list of prices."""
    if len(prices) < period + 1: return 50.0
    deltas = np.diff(prices)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    if down == 0: return 100.0
    rs = up / down
    res = np.zeros_like(prices)
    res[:period] = 100. - 100. / (1. + rs)

    for i in range(period, len(deltas)):
        delta = deltas[i]
        if delta > 0:
            upval, downval = delta, 0.
        else:
            upval, downval = 0., -delta
        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up / down if down > 0 else 100.0
        res[i] = 100. - 100. / (1. + rs)
    return float(res[-1])

def calculate_fibonacci_levels(ib_high, ib_low):
    """Calculate Fibonacci extensions from IB range."""
    rng = ib_high - ib_low
    if rng <= 0:
        return {k: ib_high for k in ["fib_127_up", "fib_161_up", "fib_200_up", "fib_127_dn", "fib_161_dn", "fib_200_dn"]}
    return {
        "fib_127_up": ib_high + 0.272 * rng,
        "fib_161_up": ib_high + 0.618 * rng,
        "fib_200_up": ib_high + 1.000 * rng,
        "fib_127_dn": ib_low - 0.272 * rng,
        "fib_161_dn": ib_low - 0.618 * rng,
        "fib_200_dn": ib_low - 1.000 * rng,
    }

def get_nearest_level_identity(spot, named_levels, threshold_bps=25.0):
    """Identify the nearest level and its distance."""
    LEVEL_IDENTITY_MAP = {
        "ib_high": 0, "ib_low": 1,
        "fib_127_up": 2, "fib_161_up": 3, "fib_200_up": 4,
        "fib_127_dn": 5, "fib_161_dn": 6, "fib_200_dn": 7,
        "none": 8,
    }
    best_name, best_dist = "none", float('inf')
    for name, level in named_levels.items():
        if level <= 0: continue
        d = abs(spot - level) / spot
        if d < (threshold_bps / 10000.0) and d < best_dist:
            best_dist = d
            best_name = name
    return float(LEVEL_IDENTITY_MAP[best_name]), best_dist


def compute_gamma_speed(df_pq, spot, day_atr):
    """Compute normalized gamma speed (change in gamma per point of spot)."""
    if df_pq is None or df_pq.empty:
        # print("[DEBUG] compute_gamma_speed: df_pq is None/empty")
        return 0.0
    
    delta_s = 5.0 if spot > 1000 else 1.0
    g_by_strike = df_pq.groupby('strike')['pq_net_gamma'].sum()
    strikes = g_by_strike.index.values
    if len(strikes) < 2:
        # print(f"[DEBUG] compute_gamma_speed: not enough strikes: {len(strikes)}")
        return 0.0
        
    idx_upper = int(np.argmin(np.abs(strikes - (spot + delta_s))))
    idx_lower = int(np.argmin(np.abs(strikes - (spot - delta_s))))
    
    if idx_upper == idx_lower:
        # print(f"[DEBUG] compute_gamma_speed: idx_upper == idx_lower == {idx_upper} for spot {spot}")
        return 0.0
        
    gamma_upper = float(g_by_strike.iloc[idx_upper])
    gamma_lower = float(g_by_strike.iloc[idx_lower])
    speed_raw = (gamma_upper - gamma_lower) / (2.0 * delta_s)
    speed_scaled = speed_raw * (day_atr ** 2)
    speed_norm = float(np.sign(speed_scaled) * np.log1p(np.abs(speed_scaled)))
    return float(np.clip(speed_norm, -20.0, 20.0))


def extract_feature_vector(
    exp_0dte, exp_weekly, spot, atm_iv, vix_spot, tlt_spot,
    ib_high, ib_low, historical_ibs, 
    price_history, tlt_price_history, iv_history, pcr_history,
    net_gamma_window, net_charm_history, prev_features,
    minutes_since_open: int, day_atr: float, now_et: datetime, 
    FEATURE_COLUMNS: list = None, wonham_prob: float = 0.5
):
    """
    Construct the final 163-feature vector. 
    This is the SINGLE SOURCE OF TRUTH for feature engineering.
    """
    features = {}

    # 1. Greeks (0DTE)
    features["net_gamma"] = safe_log(exp_0dte["net_gamma"])
    features["net_vanna"] = safe_log(exp_0dte["net_vanna"])
    features["net_charm"] = safe_log(exp_0dte["net_charm"])
    features["net_dgex"]  = safe_log(exp_0dte["net_dgex"])
    features["net_zomma"] = safe_log(exp_0dte["net_zomma"])
    features["net_delta"] = safe_log(exp_0dte.get("net_delta", 0.0))
    features["net_vega"]  = safe_log(exp_0dte.get("net_vega", 0.0))
    features["net_vomma"] = safe_log(exp_0dte.get("net_vomma", 0.0))

    # 2. Signals
    features["signal_persistence_5m"] = float(exp_0dte.get("signal_persistence_5m", 0.0))
    features["gamma_regime"] = classify_gamma_regime(exp_0dte["net_gamma"]) / 2.0
    if prev_features and "target" in prev_features:
        # If target is same as before, increment persistence (placeholder for now as target is not usually in prev_features)
        # We will handle this in collect_training_data_spx_qqq.py directly
        pass
    
    features["vanna_bullish"] = 1 if exp_0dte["net_vanna"] > 0.1 else 0
    features["charm_bullish"] = 1 if exp_0dte["net_charm"] > 0.1 else 0
    features["dgex_sticky"]   = 1 if exp_0dte["net_dgex"]  > 0.1 else 0
    features["zomma_stabilizing"] = 1 if exp_0dte["net_zomma"] > 0.1 else 0
    features["vega_elevated"] = 1 if abs(exp_0dte.get("net_vega", 0.0)) > 0.1 else 0

    # 3. Distances
    features["dist_to_max_gamma"] = dist_bps(spot, exp_0dte["max_gamma_strike"])
    features["dist_to_min_gamma"] = dist_bps(spot, exp_0dte["min_gamma_strike"])
    features["dist_to_min_vanna"] = dist_bps(spot, exp_0dte["min_vanna_strike"])
    features["dist_to_zero_gamma"] = dist_bps(spot, exp_0dte["zero_gamma"])
    features["dist_to_max_dgex"]  = dist_bps(spot, exp_0dte["max_dgex_strike"])
    features["dist_to_min_dgex"]  = dist_bps(spot, exp_0dte["min_dgex_strike"])
    features["dist_to_max_vega"]  = dist_bps(spot, exp_0dte.get("max_vega_strike", 0))
    features["dist_to_min_vega"]  = dist_bps(spot, exp_0dte.get("min_vega_strike", 0))
    features["dist_to_max_vomma"] = dist_bps(spot, exp_0dte.get("max_vomma_strike", 0))
    features["dist_to_min_vomma"] = dist_bps(spot, exp_0dte.get("min_vomma_strike", 0))

    features["near_min_vanna"] = 1 if is_near_level(spot, exp_0dte["min_vanna_strike"]) else 0

    # 4. Weekly Greeks
    wk_defaults = {
        "wk_net_gamma": 0.0, "wk_net_vanna": 0.0, "wk_net_charm": 0.0,
        "wk_net_dgex": 0.0, "wk_net_zomma": 0.0, "wk_net_delta": 0.0,
        "wk_net_vega": 0.0, "wk_net_vomma": 0.0,
        "wk_gamma_regime": 0.5, "wk_vanna_bullish": 0,
        "wk_dgex_sticky": 0, "wk_zomma_stabilizing": 0,
    }
    if exp_weekly:
        wk_defaults.update({
            "wk_net_gamma": safe_log(exp_weekly["net_gamma"]),
            "wk_net_vanna": safe_log(exp_weekly["net_vanna"]),
            "wk_net_charm": safe_log(exp_weekly["net_charm"]),
            "wk_net_dgex":  safe_log(exp_weekly["net_dgex"]),
            "wk_net_zomma": safe_log(exp_weekly["net_zomma"]),
            "wk_net_delta": safe_log(exp_weekly.get("net_delta", 0.0)),
            "wk_net_vega":  safe_log(exp_weekly.get("net_vega", 0.0)),
            "wk_net_vomma": safe_log(exp_weekly.get("net_vomma", 0.0)),
            "wk_gamma_regime": classify_gamma_regime(exp_weekly["net_gamma"]) / 2.0,
            "wk_vanna_bullish": 1 if exp_weekly["net_vanna"] > 0.1 else 0,
            "wk_dgex_sticky":   1 if exp_weekly["net_dgex"]  > 0.1 else 0,
            "wk_zomma_stabilizing": 1 if exp_weekly["net_zomma"] > 0.1 else 0,
        })
    features.update(wk_defaults)

    # 5. Divergence (Log Ratios)
    def safe_diff_ratio(v1, v2):
        # We use log1p(abs) difference as a safe ratio proxy to avoid division by zero or sign issues
        return float(safe_log(v1) - safe_log(v2 if v2 is not None else 0))

    features["gamma_0dte_vs_wk"] = safe_diff_ratio(exp_0dte["net_gamma"], exp_weekly["net_gamma"] if exp_weekly else 0)
    features["vanna_0dte_vs_wk"] = safe_diff_ratio(exp_0dte["net_vanna"], exp_weekly["net_vanna"] if exp_weekly else 0)
    features["dgex_0dte_vs_wk"]  = safe_diff_ratio(exp_0dte["net_dgex"],  exp_weekly["net_dgex"]  if exp_weekly else 0)
    features["delta_0dte_vs_wk"] = safe_diff_ratio(exp_0dte.get("net_delta", 0), exp_weekly.get("net_delta", 0) if exp_weekly else 0)
    features["vega_0dte_vs_wk"]  = safe_diff_ratio(exp_0dte.get("net_vega", 0),  exp_weekly.get("net_vega", 0)  if exp_weekly else 0)
    features["vomma_0dte_vs_wk"] = safe_diff_ratio(exp_0dte.get("net_vomma", 0), exp_weekly.get("net_vomma", 0) if exp_weekly else 0)

    # 6. IB & Fibs
    rng = max(ib_high - ib_low, 0.01)
    features["price_vs_ib_high"] = dist_bps(spot, ib_high)
    features["price_vs_ib_low"]  = dist_bps(spot, ib_low)
    features["ib_range_pct"] = rng / spot if spot > 0 else 0
    features["near_ib_high"] = 1 if is_near_level(spot, ib_high) else 0
    features["near_ib_low"]  = 1 if is_near_level(spot, ib_low) else 0
    features["above_ib"] = 1 if spot > ib_high else 0
    features["below_ib"] = 1 if spot < ib_low else 0
    features["in_ib_range"] = 1 if ib_low <= spot <= ib_high else 0

    fibs = calculate_fibonacci_levels(ib_high, ib_low)
    for k, v in fibs.items():
        features[f"dist_{k}"] = dist_bps(spot, v)

    # 6.5 S/R Level Interactions (Price Action)
    # Recopilar todos los niveles importantes
    all_levels = [
        ib_high, ib_low,
        exp_0dte["max_gamma_strike"], exp_0dte["min_gamma_strike"],
        exp_0dte["max_dgex_strike"], exp_0dte["min_dgex_strike"]
    ] + list(fibs.values())
    if exp_weekly:
        all_levels.extend([exp_weekly.get("max_gamma_strike", 0), exp_weekly.get("min_gamma_strike", 0)])
    
    valid_levels = [l for l in all_levels if l is not None and l > 0]
    
    # Nearest level dist
    if valid_levels:
        min_dist = min(abs(spot - l) / spot for l in valid_levels)
        features["nearest_level_dist"] = float(np.clip(min_dist * 10000, 0, 500)) # in bps, capped at 500
    else:
        features["nearest_level_dist"] = 500.0

    # Cluster Density (cuántos niveles hay cerca del spot)
    cluster_threshold = 0.0015 # 0.15% (e.g. ~7 points on 5000)
    density = sum(1 for l in valid_levels if abs(spot - l)/spot < cluster_threshold)
    features["level_cluster_density"] = float(np.clip(density / 10.0, 0, 1.0)) # Capped at 1.0 (10 levels)

    # Momentum and Rejection Tails (using price history)
    prices_list = [p for _, p in price_history]
    if len(prices_list) >= 5:
        last_5_prices = prices_list[-5:]
        max_5 = max(last_5_prices)
        min_5 = min(last_5_prices)
        p_now = prices_list[-1]
        p_past = prices_list[-5]
        momentum_5m = (p_now - p_past) / p_past
        
        # Momentum into level (speed of approach)
        features["momentum_5m_bps"] = float(np.clip(momentum_5m * 10000, -200, 200))
        
        # Rejection tail logic: Did it pierce a level and close back inside?
        # e.g., if it dropped below a level (min_5 < level) but is now above it (p_now > level)
        rejection_bullish = 0
        rejection_bearish = 0
        for l in valid_levels:
            if min_5 < l and p_now > l + (l * 0.0002): # pierced down, bounced up
                rejection_bullish += 1
            if max_5 > l and p_now < l - (l * 0.0002): # pierced up, rejected down
                rejection_bearish += 1
                
        features["rejection_bullish"] = float(np.clip(rejection_bullish / 5.0, 0, 1.0))
        features["rejection_bearish"] = float(np.clip(rejection_bearish / 5.0, 0, 1.0))
    else:
        features["momentum_5m_bps"] = 0.0
        features["rejection_bullish"] = 0.0
        features["rejection_bearish"] = 0.0

    # Trend context (Grind vs Flush)
    if len(prices_list) >= 30:
        last_30 = prices_list[-30:]
        trend_30m = (prices_list[-1] - prices_list[-30]) / prices_list[-30]
        volatility_30m = np.std(last_30) / prices_list[-30] if len(last_30) > 1 else 0
        
        # Grind up: steady uptrend with low volatility
        features["trend_grind_up"] = 1.0 if trend_30m > 0.001 and volatility_30m < 0.001 else 0.0
        # Flush down: sharp downtrend with high volatility
        features["trend_flush_down"] = 1.0 if trend_30m < -0.002 and volatility_30m > 0.001 else 0.0
    else:
        features["trend_grind_up"] = 0.0
        features["trend_flush_down"] = 0.0

    # 7. IV / VIX
    atm_iv_norm = atm_iv / 100.0 if atm_iv > 1 else atm_iv
    iv_history_list = list(iv_history)
    iv_mean = np.mean(iv_history_list) if iv_history_list else 0.15
    iv_std = np.std(iv_history_list) if len(iv_history_list) > 1 else 0
    iv_zscore = (atm_iv_norm - iv_mean) / iv_std if iv_std > 0 else 0
    iv_min = min(iv_history_list) if iv_history_list else 0.1
    iv_max = max(iv_history_list) if iv_history_list else 0.2
    iv_pct = (atm_iv_norm - iv_min) / (iv_max - iv_min) if iv_max > iv_min else 0.5
    
    features["atm_iv"] = atm_iv_norm
    features["iv_zscore"] = np.clip(iv_zscore, -3.0, 3.0) / 3.0
    features["iv_percentile"] = float(iv_pct)
    features["vix_spot"] = vix_spot / 50.0 if vix_spot > 0 else 0
    # vix_gamma passed from load_vix_data
    vix_gamma_val = exp_0dte.get("vix_gamma", 0.0)
    features["vix_gamma"] = safe_log(vix_gamma_val)
    features["vix_regime"] = (2 if vix_spot > 25 else (1 if vix_spot > 18 else 0)) / 2.0

    # 8. Technicals
    prices_list = [p for _, p in price_history]
    features["rsi"] = simple_rsi(prices_list) / 100.0
    features["vol_relative"] = 0.2 # Default or based on volume

    # 9. Ratios
    eps = 1e-6
    features["gamma_vanna_ratio"] = safe_log(exp_0dte["net_gamma"] / (abs(exp_0dte["net_vanna"]) + eps))
    features["dgex_gamma_ratio"]  = safe_log(exp_0dte["net_dgex"] / (abs(exp_0dte["net_gamma"]) + eps))
    features["charm_vanna_ratio"] = safe_log(exp_0dte["net_charm"] / (abs(exp_0dte["net_vanna"]) + eps))
    features["delta_gamma_ratio"] = safe_log(exp_0dte.get("net_delta", 0) / (abs(exp_0dte["net_gamma"]) + eps))
    features["vega_gamma_ratio"]  = safe_log(exp_0dte.get("net_vega", 0) / (abs(exp_0dte["net_gamma"]) + eps))
    features["vomma_vega_ratio"]  = safe_log(exp_0dte.get("net_vomma", 0) / (abs(exp_0dte.get("net_vega", 0)) + eps))

    # 10. Temporal Deltas
    if prev_features:
        features["gamma_change"] = safe_log(exp_0dte["net_gamma"] - prev_features["net_gamma"])
        features["vanna_change"] = safe_log(exp_0dte["net_vanna"] - prev_features["net_vanna"])
        features["dgex_change"]  = safe_log(exp_0dte["net_dgex"] - prev_features["net_dgex"])
        features["delta_change"] = safe_log(exp_0dte.get("net_delta", 0) - prev_features.get("net_delta", 0))
        features["vega_change"]  = safe_log(exp_0dte.get("net_vega", 0) - prev_features.get("net_vega", 0))
        features["vomma_change"] = safe_log(exp_0dte.get("net_vomma", 0) - prev_features.get("net_vomma", 0))
        features["spot_change"]  = (spot - prev_features["spot"]) / prev_features["spot"] * 10000.0 if prev_features["spot"] > 0 else 0
        features["gamma_momentum"] = safe_log((exp_0dte["net_gamma"] - prev_features["net_gamma"]) * np.sign(exp_0dte["net_gamma"]))
        features["price_vs_dgex_magnet"] = features["spot_change"] * np.sign((spot - exp_0dte["max_dgex_strike"]) / spot) if exp_0dte["max_dgex_strike"] else 0
    else:
        for f in ["gamma_change", "vanna_change", "dgex_change", "delta_change", "vega_change", "vomma_change", "spot_change", "gamma_momentum", "price_vs_dgex_magnet"]:
            features[f] = 0.0

    # 11. TLT
    for label, lb in [("1m", 1), ("5m", 5), ("15m", 15)]:
        past_tlt = get_price_n_minutes_ago(tlt_price_history, minutes_since_open, lb)
        if past_tlt and tlt_spot > 0:
            norm = 0.05 * np.sqrt(lb)
            features[f"tlt_ret_{label}"] = float(np.clip((tlt_spot - past_tlt) / (norm + 1e-8), -3, 3))
        else:
            features[f"tlt_ret_{label}"] = 0.0

    # 12. Historical IB
    for i in range(5):
        d = i + 1
        hist = historical_ibs[i] if i < len(historical_ibs) else None
        if hist:
            h_h, h_l, p_c = hist['ib_high'], hist['ib_low'], hist['close_price']
            features[f"dist_ib_high_D{d}"] = dist_bps(spot, h_h)
            features[f"dist_ib_low_D{d}"]  = dist_bps(spot, h_l)
            features[f"prev_close_vs_ib_D{d}"] = float(np.clip((p_c - (h_h+h_l)/2) / (h_h-h_l+1e-6), -2, 2))
        else:
            features[f"dist_ib_high_D{d}"] = 0.0
            features[f"dist_ib_low_D{d}"]  = 0.0
            features[f"prev_close_vs_ib_D{d}"] = 0.0

    # 13. Vol-Adjusted Returns
    for label, lb in [("1m", 1), ("5m", 5), ("15m", 15)]:
        past_p = get_price_n_minutes_ago(price_history, minutes_since_open, lb)
        if past_p:
            raw_ret = (spot - past_p) / past_p
            vol_norm = atm_iv_norm * np.sqrt(lb / (252.0 * 390.0)) + 1e-8
            features[f"ret_{label}_vol_adj"] = float(np.clip(raw_ret / vol_norm, -5, 5))
        else:
            features[f"ret_{label}_vol_adj"] = 0.0

    # 14. Time
    features["time_sin"] = float(np.sin(2 * np.pi * minutes_since_open / 390))
    features["time_cos"] = float(np.cos(2 * np.pi * minutes_since_open / 390))
    features["minutes_to_close_norm"] = max(0, 390 - minutes_since_open) / 390.0
    features["dow_sin"] = float(np.sin(2 * np.pi * now_et.weekday() / 5))
    features["dow_cos"] = float(np.cos(2 * np.pi * now_et.weekday() / 5))

    # 15. IB Context & Gap
    if historical_ibs and historical_ibs[0]:
        d1_close = historical_ibs[0]['close_price']
        today_open = price_history[0][1] if price_history else spot
        gap_pct = np.clip((today_open - d1_close) / d1_close, -0.02, 0.02)
        features["gap_pct"] = float(gap_pct)
        features["gap_direction"] = 1.0 if gap_pct > 0.001 else (-1.0 if gap_pct < -0.001 else 0.0)
        features["overnight_vs_ib_ratio"] = float(np.clip(abs(today_open - d1_close) / rng, 0.0, 3.0))
        past_ranges = [h['ib_high'] - h['ib_low'] for h in historical_ibs if h]
        features["ib_range_percentile"] = sum(r < rng for r in past_ranges) / len(past_ranges) if past_ranges else 0.5
    else:
        features["gap_pct"] = 0.0
        features["gap_direction"] = 0.0
        features["overnight_vs_ib_ratio"] = 0.0
        features["ib_range_percentile"] = 0.5

    # 16. OpEx
    y, m = now_et.year, now_et.month
    fridays = [d for d in calendar.Calendar().itermonthdays2(y, m) if d[0] != 0 and d[1] == 4]
    third_friday = fridays[2][0] if len(fridays) >= 3 else fridays[-1][0]
    opex_date = datetime(y, m, third_friday)
    days_to_opex = (opex_date.date() - now_et.date()).days
    if days_to_opex < 0:
        nm, ny = (m + 1, y) if m < 12 else (1, y + 1)
        fridays_next = [d for d in calendar.Calendar().itermonthdays2(ny, nm) if d[0] != 0 and d[1] == 4]
        third_friday_next = fridays_next[2][0] if len(fridays_next) >= 3 else fridays_next[-1][0]
        days_to_opex = (datetime(ny, nm, third_friday_next).date() - now_et.date()).days
    features["days_to_opex_norm"] = float(np.clip(days_to_opex / 21.0, 0.0, 1.0))
    features["is_opex_week"] = 1.0 if abs(days_to_opex) <= 5 else 0.0
    features["is_quarterly_opex_week"] = 1.0 if abs(days_to_opex) <= 5 and m in (3, 6, 9, 12) else 0.0

    # 17. Greek Dynamics
    gamma_speed_val = compute_gamma_speed(exp_0dte.get('_df'), spot, day_atr)
    features["gamma_speed"] = safe_log(gamma_speed_val)
    
    net_charm_history_list = list(net_charm_history)
    charm_accel_weighted = 0.0
    if len(net_charm_history_list) >= 3:
        charm_arr = np.array(net_charm_history_list[-3:])
        charm_accel = charm_arr[-1] - 2.0 * charm_arr[-2] + charm_arr[-3]
        charm_accel_norm = float(np.clip(charm_accel / (atm_iv_norm + 1e-6), -5.0, 5.0))
        close_weight = 1.0 + np.exp(-max(0, 390 - minutes_since_open) / 60.0)
        charm_accel_weighted = float(np.clip(charm_accel_norm * close_weight, -10.0, 10.0))
    features["charm_accel_weighted"] = charm_accel_weighted

    # 18. Hilbert
    gamma_win = list(net_gamma_window)
    if len(gamma_win) >= 30:
        try:
            ga = np.array(gamma_win)
            ga_n = (ga - np.mean(ga)) / (np.std(ga) + 1e-8)
            pad = max(1, len(ga_n)//4)
            p_ga = np.concatenate([ga_n[pad:0:-1], ga_n, ga_n[-2:-(pad+2):-1]])
            ana = scipy_hilbert(p_ga)[pad:pad+len(ga_n)]
            amp, phase = np.abs(ana), np.angle(ana)
            rel_amp = float(np.clip(amp[-1] / (np.mean(amp) + 1e-8), 0, 3))
            qual = 1.0 if rel_amp > 0.5 else 0.0
            features["gamma_phase_sin"] = float(np.sin(phase[-1])) * qual
            features["gamma_phase_cos"] = float(np.cos(phase[-1])) * qual
            features["gamma_amplitude_ratio"] = rel_amp
            unw = np.unwrap(phase)
            features["gamma_phase_delta"] = float(np.clip((unw[-1]-unw[-2])/np.pi, -1, 1)) * qual if len(unw) >= 2 else 0.0
        except: pass
    else:
        for f in ["gamma_phase_sin", "gamma_phase_cos", "gamma_amplitude_ratio", "gamma_phase_delta"]: features[f] = 0.0

    # 19. Option Flow proxy (PCR)
    pcr_list = list(pcr_history)
    if pcr_list:
        latest_pcr_raw = pcr_list[-1]
        features["delta_filtered_pcr"] = float(np.clip(np.log1p(latest_pcr_raw) / np.log1p(5.0), 0.0, 1.0))
        if len(pcr_list) >= 5:
            features["pcr_derivative_5m"] = float(np.clip((pcr_list[-1] - pcr_list[-5]) / 5.0, -1.0, 1.0))
        else:
            features["pcr_derivative_5m"] = 0.0
    else:
        features["delta_filtered_pcr"] = 0.1
        features["pcr_derivative_5m"] = 0.0
    # PCR logic usually needs full OHLC or ticks which are harder in this flat vector. 
    # For now we'll match the bot's simplified proxy if provided in arguments.

    # 20. Confluences
    sigma_bps = 0.003
    features["confluence_ib_high_max_gamma"] = rbf_confluence(ib_high, exp_0dte["max_gamma_strike"], spot, sigma=sigma_bps)
    features["confluence_ib_low_min_gamma"]  = rbf_confluence(ib_low, exp_0dte["min_gamma_strike"], spot, sigma=sigma_bps)
    features["confluence_ib_high_max_vega"]  = rbf_confluence(ib_high, exp_0dte.get("max_vega_strike", 0), spot, sigma=sigma_bps)
    features["confluence_ib_low_max_dgex"]   = rbf_confluence(ib_low, exp_0dte["max_dgex_strike"], spot, sigma=sigma_bps)
    features["confluence_fib127_bull_max_gamma"] = rbf_confluence(fibs["fib_127_up"], exp_0dte["max_gamma_strike"], spot, sigma=sigma_bps)
    features["confluence_fib161_bull_max_vega"]  = rbf_confluence(fibs["fib_161_up"], exp_0dte.get("max_vega_strike", 0), spot, sigma=sigma_bps)
    features["confluence_fib127_bear_min_gamma"] = rbf_confluence(fibs["fib_127_dn"], exp_0dte["min_gamma_strike"], spot, sigma=sigma_bps)
    features["confluence_fib161_bear_max_vomma"] = rbf_confluence(fibs["fib_161_dn"], exp_0dte.get("max_vomma_strike", 0), spot, sigma=sigma_bps)
    features["confluence_fib161_bull_max_vomma"] = rbf_confluence(fibs["fib_161_up"], exp_0dte.get("max_vomma_strike", 0), spot, sigma=sigma_bps)
    features["confluence_fib127_bear_min_vomma"] = rbf_confluence(fibs["fib_127_dn"], exp_0dte.get("min_vomma_strike", 0), spot, sigma=sigma_bps)
    features["confluence_fib127_bull_max_dgex"]  = rbf_confluence(fibs["fib_127_up"], exp_0dte["max_dgex_strike"], spot, sigma=sigma_bps)
    features["confluence_fib127_bear_min_dgex"]  = rbf_confluence(fibs["fib_127_dn"], exp_0dte["min_dgex_strike"], spot, sigma=sigma_bps)
    features["confluence_fib161_bull_max_dgex"]  = rbf_confluence(fibs["fib_161_up"], exp_0dte["max_dgex_strike"], spot, sigma=sigma_bps)
    features["confluence_fib161_bear_min_dgex"]  = rbf_confluence(fibs["fib_161_dn"], exp_0dte["min_dgex_strike"], spot, sigma=sigma_bps)

    if historical_ibs and historical_ibs[0]:
        d1h, d1l = historical_ibs[0]['ib_high'], historical_ibs[0]['ib_low']
        features["confluence_d1ibh_max_gamma"] = rbf_confluence(d1h, exp_0dte["max_gamma_strike"], spot, sigma=sigma_bps)
        features["confluence_d1ibl_min_gamma"] = rbf_confluence(d1l, exp_0dte["min_gamma_strike"], spot, sigma=sigma_bps)
        features["confluence_d1ibh_max_dgex"]  = rbf_confluence(d1h, exp_0dte["max_dgex_strike"], spot, sigma=sigma_bps)
        features["confluence_d1ibl_min_dgex"]  = rbf_confluence(d1l, exp_0dte["min_dgex_strike"], spot, sigma=sigma_bps)
        features["confluence_d1ibh_max_vomma"] = rbf_confluence(d1h, exp_0dte.get("max_vomma_strike", 0), spot, sigma=sigma_bps)
        features["confluence_d1ibh_ibh_today"] = rbf_confluence(d1h, ib_high, spot, sigma=sigma_bps)
        features["confluence_d1ibl_ibl_today"] = rbf_confluence(d1l, ib_low, spot, sigma=sigma_bps)
    else:
        for f in ["confluence_d1ibh_max_gamma", "confluence_d1ibl_min_gamma", "confluence_d1ibh_max_dgex", "confluence_d1ibl_min_dgex", "confluence_d1ibh_max_vomma", "confluence_d1ibh_ibh_today", "confluence_d1ibl_ibl_today"]:
            features[f] = 0.0

    # 21. VRP Regime
    closes = [h['close_price'] for h in historical_ibs if h and h.get('close_price', 0) > 0]
    if len(closes) >= 5:
        log_rets = np.diff(np.log(closes[::-1]))
        rvol = float(np.std(log_rets) * np.sqrt(252))
        ratio = rvol / (atm_iv_norm + 1e-6)
        features["rvol_iv_log"] = float(np.clip(np.log(max(ratio, 1e-6)), -1.5, 1.5))
        rvol_5d = float(np.std(log_rets[-5:]) * np.sqrt(252))
        features["rvol_trend"] = float(np.clip((rvol_5d - rvol) / (atm_iv_norm + 1e-6), -1, 1))
        features["rvol_regime"] = 0.0 if ratio < 0.85 else (2.0 if ratio > 1.15 else 1.0)
    else:
        features["rvol_iv_log"], features["rvol_trend"], features["rvol_regime"] = 0.0, 0.0, 1.0

    # 22. Interactions
    near_fib_up = any(is_near_level(spot, v) for k, v in fibs.items() if "up" in k)
    near_fib_dn = any(is_near_level(spot, v) for k, v in fibs.items() if "dn" in k)
    near_ib = bool(features["near_ib_high"] or features["near_ib_low"])
    
    g_sl, d_sl, v_sl = features["net_gamma"], features["net_delta"], features["net_vanna"]
    features["gamma_x_near_fib_up"]  = g_sl * float(near_fib_up)
    features["gamma_x_near_fib_dn"]  = g_sl * float(near_fib_dn)
    features["gamma_x_near_ib"]      = g_sl * float(near_ib)
    features["delta_x_near_fib_up"]  = d_sl * float(near_fib_up)
    features["delta_x_near_fib_dn"]  = d_sl * float(near_fib_dn)
    features["delta_x_near_ib_high"] = d_sl * float(features["near_ib_high"])
    features["delta_x_near_ib_low"]  = d_sl * float(features["near_ib_low"])
    features["vanna_x_near_fib_up"]  = v_sl * float(near_fib_up)
    features["vanna_x_near_fib_dn"]  = v_sl * float(near_fib_dn)
    features["vanna_x_near_ib"]      = v_sl * float(near_ib)

    features["speed_x_near_ib_high"] = gamma_speed_val * float(features["near_ib_high"])
    features["speed_x_near_ib_low"]  = gamma_speed_val * float(features["near_ib_low"])
    features["charm_accel_x_near_ib_high"] = charm_accel_weighted * float(features["near_ib_high"])
    features["charm_accel_x_near_ib_low"]  = charm_accel_weighted * float(features["near_ib_low"])
    
    # Synthetic Binary Bounce/Wall Features
    near_max_gamma = is_near_level(spot, exp_0dte["max_gamma_strike"])
    near_min_gamma = is_near_level(spot, exp_0dte["min_gamma_strike"])
    near_max_dgex = is_near_level(spot, exp_0dte["max_dgex_strike"])
    near_min_vanna = is_near_level(spot, exp_0dte["min_vanna_strike"])
    
    features["is_touching_fib"] = 1.0 if (near_fib_up or near_fib_dn) else 0.0
    features["is_touching_max_gamma"] = 1.0 if near_max_gamma else 0.0
    features["is_touching_min_gamma"] = 1.0 if near_min_gamma else 0.0
    features["is_touching_max_dgex"] = 1.0 if near_max_dgex else 0.0
    
    # Combined confluences (e.g. Fib + Greek Wall)
    features["wall_at_fib"] = 1.0 if (features["is_touching_fib"] and (near_max_gamma or near_min_gamma or near_max_dgex)) else 0.0
    features["wall_at_ib"] = 1.0 if (near_ib and (near_max_gamma or near_min_gamma or near_max_dgex)) else 0.0
    
    # Bounce proxy: Price is near a wall and spot_change is moving away from it
    if features["spot_change"] > 0:
        # Price is going UP. If we are near min_gamma (support) or Fib DN (support), it's a bounce.
        features["bouncing_from_support"] = 1.0 if (near_min_gamma or near_fib_dn or features["near_ib_low"]) else 0.0
        features["rejecting_resistance"] = 0.0
    elif features["spot_change"] < 0:
        # Price is going DOWN. If we are near max_gamma (resistance) or Fib UP, it's a rejection.
        features["rejecting_resistance"] = 1.0 if (near_max_gamma or near_fib_up or features["near_ib_high"]) else 0.0
        features["bouncing_from_support"] = 0.0
    else:
        features["bouncing_from_support"] = 0.0
        features["rejecting_resistance"] = 0.0

    # 23. Level Identity
    named_levels = {
        "ib_high": ib_high, "ib_low": ib_low,
        "fib_127_up": fibs["fib_127_up"], "fib_161_up": fibs["fib_161_up"],
        "fib_200_up": fibs["fib_200_up"], "fib_127_dn": fibs["fib_127_dn"],
        "fib_161_dn": fibs["fib_161_dn"], "fib_200_dn": fibs["fib_200_dn"],
    }
    id_val, dist_bps_val = get_nearest_level_identity(spot, named_levels)
    features["nearest_level_id"] = id_val
    features["nearest_level_dist_bps"] = float(np.clip(dist_bps_val * 10000.0, 0, BPS_CLIP))

    features["wonham_trend_prob"] = float(wonham_prob)

    # Final build
    if FEATURE_COLUMNS is None:
        return features
    return np.array([features.get(col, 0.0) for col in FEATURE_COLUMNS], dtype=np.float32)


def get_price_n_minutes_ago(history, current_min, n_min):
    """Retrieve price from N minutes ago from history deque of (min, price)."""
    if not history: return None
    target_min = current_min - n_min
    best_p, best_diff = None, float('inf')
    for (m, p) in history:
        diff = abs(m - target_min)
        if diff < best_diff:
            best_diff, best_p = diff, p
    return best_p if best_diff <= 2 else None
