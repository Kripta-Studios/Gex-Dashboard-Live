import sys
import os
import glob
import re
import argparse
import calendar
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
from collections import deque
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from scipy.signal import hilbert as scipy_hilbert
import math
import time
import psutil

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from training_data.stats import *

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

def get_env_path(key: str, default: str) -> str:
    value = os.getenv(key, default)
    if value.startswith('"') and value.endswith('"'): value = value[1:-1]
    if value.startswith("'") and value.endswith("'"): value = value[1:-1]
    return value.strip()

# Configuration
THETADATA_DIR = get_env_path("THETADATA_DIR", r"D:\ThetaData")
OPTIONS_DIR = os.path.join(THETADATA_DIR, "data_options")
IB_CHARTS_DIR = get_env_path("IB_CHARTS_DIR", os.path.join(PROJECT_ROOT, "trading_data", "ib_backtest"))
IB_BACKTEST_DIR = get_env_path("IB_BACKTEST_DIR", os.path.join(PROJECT_ROOT, "trading_data", "ib_backtest"))
FOURIER_DIR = get_env_path("FOURIER_DIR", os.path.join(PROJECT_ROOT, "trading_data", "fourier"))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "training_data")

TICKERS = ["SPX", "QQQ"]
R_RATE, Q_DIV = 0.0325, 0.0150
LEVEL_PROXIMITY_THRESHOLD = 0.0015   # ±0.15% — widened to capture S/R bounces at IB/fib levels
                                     # Was 0.0008 (±4pts SPX) — too tight, missed 0.10-0.15% reactions
                                     # With 0.0015 = ±6pts in SPX@4100, ±0.45pts in QQQ@300
LOOKAHEAD_MINUTES = 180
FIXED_PROFIT_PCT = 0.003             # 0.3% — target for LONG/SHORT (captures typical S/R bounces)
FIXED_STOP_PCT   = 0.003             # 0.3% — stop for both directions → 1:1 R/R
                                     # Previous: 0.6% profit / 0.3% stop → missed 0.3-0.5% moves
BPS_CLIP = 500                        # clamp distances at ±500 bps (±5%)

def classify_gamma_regime(net_gamma: float, threshold: float = 1e8) -> int:
    if net_gamma > threshold: return 2
    elif net_gamma < -threshold: return 0
    return 1

def is_near_level(price: float, level: float, threshold: float = LEVEL_PROXIMITY_THRESHOLD) -> bool:
    if level is None or level == 0 or price == 0: return False
    return abs(price - level) / price <= threshold

def safe_log(x: float) -> float:
    """Sign-preserving log-transform: sign(x) * log1p(|x|).
    Compresses extreme greek values (10^8-10^11) to manageable range (~20-26)
    while preserving sign and monotonicity."""
    return float(np.sign(x) * np.log1p(abs(x)))

def dist_bps(spot: float, level: float) -> float:
    """Percentage distance from spot to level in basis points, clamped."""
    if level is None or level == 0 or spot == 0:
        return 0.0
    return float(np.clip((spot - level) / spot * 10000.0, -BPS_CLIP, BPS_CLIP))

def proximity_gate(spot: float, levels: list, threshold: float = LEVEL_PROXIMITY_THRESHOLD) -> bool:
    """Return True if spot is within ±threshold% of ANY level in the list."""
    for level in levels:
        if is_near_level(spot, level, threshold):
            return True
    return False

def calculate_fibonacci_levels(ib_high: float, ib_low: float):
    ib_range = ib_high - ib_low
    return {
        "fib_127_up": ib_low + (ib_range * 1.272),
        "fib_161_up": ib_low + (ib_range * 1.618),
        "fib_200_up": ib_low + (ib_range * 2.0),
        "fib_127_dn": ib_low + (ib_range * -0.272),
        "fib_161_dn": ib_low + (ib_range * -0.618),
        "fib_200_dn": ib_low + (ib_range * -1.0),
    }

# ═══════════════════════════════════════════════════════════════
# LEVEL IDENTITY — encodes WHICH level price is touching
# The model needs this to learn "touching fib_127_up with positive
# gamma" vs "touching ib_high with positive gamma" separately.
# ═══════════════════════════════════════════════════════════════
LEVEL_IDENTITY_MAP = {
    "ib_high":    0,
    "ib_low":     1,
    "fib_127_up": 2,
    "fib_161_up": 3,
    "fib_200_up": 4,
    "fib_127_dn": 5,
    "fib_161_dn": 6,
    "fib_200_dn": 7,
    "none":       8,
}
N_LEVEL_TYPES = len(LEVEL_IDENTITY_MAP)  # 9

def get_nearest_level_identity(spot: float, levels_dict: dict,
                                threshold: float = LEVEL_PROXIMITY_THRESHOLD) -> tuple:
    """
    Returns (level_id: int, dist_bps: float) for the closest named level
    within ±threshold of spot.  level_id = 8 ("none") when no level is near.
    """
    best_name, best_dist = "none", float('inf')
    for name, level in levels_dict.items():
        if level is None or level == 0:
            continue
        d = abs(spot - level) / spot
        if d < threshold and d < best_dist:
            best_dist = d
            best_name = name
    dist_val = float(np.clip(best_dist * 10000.0, 0.0, BPS_CLIP)) if best_name != "none" else float(BPS_CLIP)
    return LEVEL_IDENTITY_MAP[best_name], dist_val


def simple_rsi(prices: list, period: int = 14) -> float:
    if len(prices) < period + 1: return 50.0
    deltas = np.diff(prices[-period-1:])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))

def sign_divergence(a: float, b: float) -> float:
    if abs(a) < 0.01 or abs(b) < 0.01: return 0.5
    if (a > 0) != (b > 0): return 1.0
    return 0.0

def rbf_confluence(level_a: float, level_b: float, spot_price: float, sigma: float = 0.05) -> float:
    if level_a is None or level_b is None or spot_price is None: return 0.0
    if spot_price <= 0: return 0.0
    dist_a = abs(spot_price - level_a) / spot_price
    dist_b = abs(spot_price - level_b) / spot_price
    overlap_dist = abs(level_a - level_b) / spot_price
    return float(np.exp(-0.5 * (dist_a/sigma)**2) * np.exp(-0.5 * (dist_b/sigma)**2) * np.exp(-0.5 * (overlap_dist/(2*sigma))**2))


def compute_wonham_filter(prices: list,
                          lambda1: float = 0.5, lambda2: float = 0.5,
                          mu1: float = 0.002, mu2: float = -0.003,
                          sigma: float = 0.01, dt: float = 1.0/390.0) -> list:
    """
    Discrete Wonham Filter for regime detection.
    
    From "A Stochastic Approximation Approach for Trend-Following Trading"
    (Nguyen, Yin, Zhang). Computes p_t = P(trending regime) recursively.
    
    Discretized SDE:
        p_{t+1} = clip( p_t + f(p_t)*dt + ((mu1-mu2)/sigma^2)*p_t*(1-p_t)*log(S_{t+1}/S_t), 0, 1 )
    
    Where f(p) = -(lambda1+lambda2)*p + lambda2 - ((mu1-mu2)/sigma^2)*p*(1-p)*((mu1-mu2)*p + mu2 - sigma^2/2)
    """
    n = len(prices)
    if n < 2:
        return [0.5] * n
    
    p = [0.5]  # Start with equal prior
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

def load_ohlc_data(ticker: str, date_str: str) -> dict:
    underlying_ticker = "SPXW" if ticker == "SPX" else ticker
    year, month = date_str[:4], date_str[4:6]
    filepath = Path(THETADATA_DIR) / "data_underlying_derived" / underlying_ticker / year / month / f"{underlying_ticker}_{date_str}.parquet"
    if not filepath.exists(): return None
    
    try:
        df = pd.read_parquet(filepath)
        df['dt'] = pd.to_datetime(df['timestamp'])
        df = df[(df['dt'].dt.time >= dt_time(8, 0)) & (df['dt'].dt.time <= dt_time(17, 0))]
        if df.empty: return None
        
        start_time = df['dt'].min()
        ib_end = start_time + pd.Timedelta(minutes=60)
        df_ib = df[df['dt'] < ib_end]
        
        ib_high = df_ib['high'].max() if not df_ib.empty else df['high'].max()
        ib_low = df_ib['low'].min() if not df_ib.empty else df['low'].min()
        
        total_volume = df['tick_count'].sum() if 'tick_count' in df.columns else df['volume'].sum() if 'volume' in df.columns else 1
        
        series = []
        for _, row in df.iterrows():
            series.append({
                "time": row['dt'].strftime("%H:%M"),
                "price": float(row['close']),
                "volume": float(row['tick_count']) if 'tick_count' in row else 1.0
            })
            
        return {
            "ib_high": float(ib_high),
            "ib_low": float(ib_low),
            "total_volume": float(total_volume),
            "series": series
        }
    except Exception as e:
        print(f"Error loading OHLC {ticker}: {e}")
        return None


MIN_FORWARD_MINUTES = 10  # Minimum bars needed for labeling (vs full LOOKAHEAD)

def calculate_target_label(series: list, current_idx: int, profit_pct: float, stop_pct: float, lookahead: int = LOOKAHEAD_MINUTES) -> tuple:
    """Asymmetric labeling dynamically scaled by ATR.
    Label LONG/SHORT only when profit target is hit *before* stop."""
    remaining = len(series) - current_idx - 1
    if remaining < MIN_FORWARD_MINUTES: return (0, 0, 0, 0.0)
    current_price = series[current_idx].get("price", 0)
    if current_price == 0: return (0, 0, 0, 0.0)
    max_price, min_price = current_price, current_price
    long_profit_time, long_stop_time = 0, 0
    short_profit_time, short_stop_time = 0, 0
    for i in range(current_idx + 1, min(current_idx + lookahead + 1, len(series))):
        price = series[i].get("price", current_price)
        minutes_elapsed = i - current_idx
        if price > max_price: max_price = price
        if price < min_price: min_price = price
        up_pct = (price - current_price) / current_price
        down_pct = (current_price - price) / current_price
        if long_profit_time == 0 and up_pct >= profit_pct: long_profit_time = minutes_elapsed
        if long_stop_time == 0 and down_pct >= stop_pct: long_stop_time = minutes_elapsed
        if short_profit_time == 0 and down_pct >= profit_pct: short_profit_time = minutes_elapsed
        if short_stop_time == 0 and up_pct >= stop_pct: short_stop_time = minutes_elapsed
    up_move = (max_price - current_price) / current_price
    down_move = (current_price - min_price) / current_price
    long_valid = long_profit_time > 0 and (long_stop_time == 0 or long_profit_time < long_stop_time)
    short_valid = short_profit_time > 0 and (short_stop_time == 0 or short_profit_time < short_stop_time)
    if long_valid and short_valid:
        if long_profit_time < short_profit_time:
            return (1, long_profit_time, long_stop_time, up_move)
        else:
            return (-1, short_profit_time, short_stop_time, down_move)
    elif long_valid:
        return (1, long_profit_time, long_stop_time, up_move)
    elif short_valid:
        return (-1, short_profit_time, short_stop_time, down_move)
    return (0, 0, 0, 0.0)


def calculate_target_label_asymmetric(series: list, current_idx: int,
                                      long_profit_pct: float, short_profit_pct: float,
                                      stop_pct: float = None,
                                      long_stop_pct: float = None,
                                      short_stop_pct: float = None,
                                      lookahead: int = LOOKAHEAD_MINUTES) -> tuple:
    """
    Versión asimétrica de calculate_target_label para el caso SR (near_sr).
    Soporta stop_pct por dirección (long_stop_pct / short_stop_pct).
    Si solo se pasa stop_pct, se usa para ambas direcciones.
    """
    # Backward compat: si solo se pasa stop_pct, usarlo para ambos
    if long_stop_pct is None:
        long_stop_pct = stop_pct if stop_pct is not None else FIXED_STOP_PCT
    if short_stop_pct is None:
        short_stop_pct = stop_pct if stop_pct is not None else FIXED_STOP_PCT

    remaining = len(series) - current_idx - 1
    if remaining < MIN_FORWARD_MINUTES: return (0, 0, 0, 0.0)
    current_price = series[current_idx].get("price", 0)
    if current_price == 0: return (0, 0, 0, 0.0)

    max_price, min_price = current_price, current_price
    long_profit_time, long_stop_time   = 0, 0
    short_profit_time, short_stop_time = 0, 0

    for i in range(current_idx + 1, min(current_idx + lookahead + 1, len(series))):
        price = series[i].get("price", current_price)
        minutes_elapsed = i - current_idx
        if price > max_price: max_price = price
        if price < min_price: min_price = price
        up_pct   = (price - current_price) / current_price
        down_pct = (current_price - price) / current_price

        if long_profit_time == 0 and up_pct   >= long_profit_pct:  long_profit_time  = minutes_elapsed
        if long_stop_time   == 0 and down_pct >= long_stop_pct:    long_stop_time    = minutes_elapsed
        if short_profit_time == 0 and down_pct >= short_profit_pct: short_profit_time = minutes_elapsed
        if short_stop_time   == 0 and up_pct   >= short_stop_pct:   short_stop_time   = minutes_elapsed

    up_move   = (max_price - current_price) / current_price
    down_move = (current_price - min_price) / current_price

    long_valid  = long_profit_time  > 0 and (long_stop_time  == 0 or long_profit_time  < long_stop_time)
    short_valid = short_profit_time > 0 and (short_stop_time == 0 or short_profit_time < short_stop_time)

    if long_valid and short_valid:
        if long_profit_time < short_profit_time:
            return (1,  long_profit_time,  long_stop_time,  up_move)
        else:
            return (-1, short_profit_time, short_stop_time, down_move)
    elif long_valid:
        return (1,  long_profit_time,  long_stop_time,  up_move)
    elif short_valid:
        return (-1, short_profit_time, short_stop_time, down_move)
    return (0, 0, 0, 0.0)

def calculate_exact_t(series_dt):
    if hasattr(series_dt, 'dt'):
        target_close = series_dt.dt.normalize() + pd.Timedelta(hours=16)
        seconds_left = (target_close - series_dt).dt.total_seconds()
    else:
        target_close = series_dt.normalize() + pd.Timedelta(hours=16)
        seconds_left = (target_close - series_dt).total_seconds()
    seconds_left = np.where(seconds_left < 60, 60, seconds_left)
    return seconds_left / (3600 * 24 * 365.25)

def get_net_exposures_from_parquet(df, spot_col='underlying_price'):
    if df.empty: return None
    
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
    c_vals_put = calc_charm_ex(S, vol, T_arr, R_RATE, Q_DIV, "put", oi, dp, cdf_dp, pdf_dp)
    c_vals = np.where(is_put, c_vals_put, c_vals_call)
    
    d_vals_call = calc_delta_ex(S, T_arr, Q_DIV, "call", oi, cdf_dp)
    d_vals_put = calc_delta_ex(S, T_arr, Q_DIV, "put", oi, cdf_dp)
    d_vals = np.where(is_put, d_vals_put, d_vals_call)
    
    dgex_call = calc_delta_adjusted_gex(g_vals, cdf_dp, T_arr, Q_DIV, "call")
    dgex_put = calc_delta_adjusted_gex(g_vals, cdf_dp, T_arr, Q_DIV, "put")
    dgex_vals = np.where(is_put, -dgex_put, dgex_call)
    
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
        if grouped.empty: return 0.0, 0.0
        return float(grouped.idxmax()), float(grouped.idxmin())
    
    max_gamma, min_gamma = get_max_min_strike('pq_net_gamma')
    max_vanna, min_vanna = get_max_min_strike('pq_net_vanna')
    max_dgex, min_dgex = get_max_min_strike('pq_net_dgex')
    max_zomma, min_zomma = get_max_min_strike('pq_net_zomma')
    max_vega, min_vega = get_max_min_strike('pq_net_vega')
    max_vomma, min_vomma = get_max_min_strike('pq_net_vomma')
    
    gamma_profile = df_clean.groupby('strike')['pq_net_gamma'].sum().sort_index()
    valid_gamma = gamma_profile[gamma_profile != 0]
    zero_gamma_strike = spot

    if not valid_gamma.empty:
        lower_bound = min(min_gamma, max_gamma)
        upper_bound = max(min_gamma, max_gamma)
        conflict_zone = valid_gamma.loc[lower_bound:upper_bound]
        
        if len(conflict_zone) > 1:
            signs = np.sign(conflict_zone.values)
            sign_flips = np.where(np.diff(signs) != 0)[0]
            if len(sign_flips) > 0:
                crossing_strikes = conflict_zone.index[sign_flips].values
                zero_gamma_strike = float(crossing_strikes[np.abs(crossing_strikes - spot).argmin()])
            else:
                zero_gamma_strike = spot

    return {
        "spot_price": spot,
        "net_gamma": df_clean['pq_net_gamma'].sum(),
        "net_vanna": df_clean['pq_net_vanna'].sum(),
        "net_charm": df_clean['pq_net_charm'].sum(),
        "net_dgex": df_clean['pq_net_dgex'].sum(),
        "net_zomma": df_clean['pq_net_zomma'].sum(),
        "net_delta": df_clean['pq_net_delta'].sum(),
        "net_vega": df_clean['pq_net_vega'].sum(),
        "net_vomma": df_clean['pq_net_vomma'].sum(),
        "max_gamma_strike": max_gamma, "min_gamma_strike": min_gamma,
        "max_vanna_strike": max_vanna, "min_vanna_strike": min_vanna,
        "max_dgex_strike": max_dgex, "min_dgex_strike": min_dgex,
        "max_zomma_strike": max_zomma, "min_zomma_strike": min_zomma,
        "max_vega_strike": max_vega, "min_vega_strike": min_vega,
        "max_vomma_strike": max_vomma, "min_vomma_strike": min_vomma,
        "zero_gamma": zero_gamma_strike
    }

def get_parquet_file(ticker, trade_date_str, is_0dte=True, folder="greeks", suffix="greeks"):
    file_ticker = "SPXW" if ticker == "SPX" else ticker
    year, month = trade_date_str[:4], trade_date_str[4:6]
    search_dir = Path(OPTIONS_DIR) / file_ticker / folder / year / month
    if not search_dir.exists(): return None
    files = list(search_dir.glob(f"{file_ticker}_*_{trade_date_str}_{suffix}.parquet"))
    if not files: return None
    if is_0dte:
        for f in files:
            exp = f.name.split('_')[1]
            if exp == trade_date_str: return f
        return None
    else:
        trade_date = datetime.strptime(trade_date_str, "%Y%m%d")
        days_to_friday = (4 - trade_date.weekday()) % 7
        if days_to_friday == 0:
            days_to_friday = 7
        weekly_day = trade_date + timedelta(days=days_to_friday)
        best_file = None
        min_diff = 999
        for f in files:
            exp_str = f.name.split('_')[1]
            exp_date = datetime.strptime(exp_str, "%Y%m%d")
            if exp_date <= trade_date:
                continue
            diff = abs((exp_date - weekly_day).days)
            if diff < min_diff:
                min_diff = diff
                best_file = f
        return best_file

def load_fourier_data(ticker: str, date_str: str) -> dict:
    pass

def load_vix_data(date_str: str) -> dict:
    vix_spot = 0
    year, month = date_str[:4], date_str[4:6]
    vix_ohlc_path = Path(THETADATA_DIR) / "data_underlying_derived" / "VIX" / year / month / f"VIX_{date_str}.parquet"
    if vix_ohlc_path.exists():
        try:
            df_vix = pd.read_parquet(vix_ohlc_path)
            if not df_vix.empty:
                vix_spot = float(df_vix['close'].iloc[-1])
        except: pass

    vix_gamma = 0
    weekly_file = get_parquet_file("VIX", date_str, is_0dte=False)
    if weekly_file:
        try:
            df_g = pd.read_parquet(weekly_file)
            year, month = date_str[:4], date_str[4:6]
            oi_file = Path(OPTIONS_DIR) / "VIX" / "oi" / year / month / weekly_file.name.replace("greeks.parquet", "oi.parquet")
            if oi_file.exists():
                df_oi = pd.read_parquet(oi_file)
                df_oi_agg = df_oi.groupby(['strike', 'right']).agg({'open_interest': 'max'}).reset_index()
                df_g['dt'] = pd.to_datetime(df_g['underlying_timestamp'])
                target_dt = pd.to_datetime(f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} 15:00:00")
                if not df_g.empty:
                    nearest_ts = df_g['dt'].unique()[np.abs(df_g['dt'].unique() - target_dt.to_datetime64()).argmin()]
                    df_min = df_g[df_g['dt'] == nearest_ts].copy()
                    df_pq = pd.merge(df_min, df_oi_agg, on=['strike', 'right'], how='inner')
                    if not df_pq.empty:
                        df_pq['T'] = calculate_exact_t(pd.to_datetime(nearest_ts))
                        exposures = get_net_exposures_from_parquet(df_pq)
                        if exposures: vix_gamma = exposures["net_gamma"]
                        if vix_spot == 0: vix_spot = float(df_pq['underlying_price'].iloc[0])
        except Exception as e: print(f"Error loading VIX weekly data: {e}")

    vix_regime = 2 if vix_spot > 25 else (1 if vix_spot > 18 else 0)
    return {"vix_spot": vix_spot, "vix_gamma": vix_gamma, "vix_regime": vix_regime}


def load_historical_ib_levels(greek_ticker: str, current_date_str: str, n_days: int = 10) -> list:
    """Load D-1 to D-N IB high/low/close from underlying parquet files."""
    current_date = datetime.strptime(current_date_str, "%Y%m%d").date()
    underlying_ticker = greek_ticker
    base_dir = Path(THETADATA_DIR) / "data_underlying_derived" / underlying_ticker
    if not base_dir.exists():
        return [None] * n_days

    available = []
    for f in base_dir.rglob("*.parquet"):
        try:
            parts = f.stem.split('_')
            date_str = parts[1] if len(parts) >= 2 else parts[0]
            d = datetime.strptime(date_str, "%Y%m%d").date()
            if d < current_date:
                available.append((d, f))
        except:
            continue

    available.sort(key=lambda x: x[0], reverse=True)
    results = []
    for d, filepath in available[:n_days]:
        try:
            df = pd.read_parquet(filepath)
            df['dt'] = pd.to_datetime(df['timestamp'])
            df = df[(df['dt'].dt.time >= dt_time(8, 0)) & (df['dt'].dt.time <= dt_time(17, 0))]
            if df.empty:
                results.append(None)
                print(f"No data for {greek_ticker} on {d}")
                continue
            start_time = df['dt'].min()
            ib_end = start_time + pd.Timedelta(minutes=60)
            df_ib = df[df['dt'] < ib_end]
            ib_high = float(df_ib['high'].max()) if not df_ib.empty else float(df['high'].max())
            ib_low = float(df_ib['low'].min()) if not df_ib.empty else float(df['low'].min())
            close_before_4 = df[df['dt'].dt.time <= dt_time(16, 0)]
            close_price = float(close_before_4['close'].iloc[-1]) if not close_before_4.empty else float(df['close'].iloc[-1])
            results.append({
                "ib_high": ib_high, "ib_low": ib_low,
                "close_price": close_price, "date_str": d.strftime("%Y%m%d")
            })
        except:
            results.append(None)
            print(f"Error loading data for {greek_ticker} on {d}")

    while len(results) < n_days:
        results.append(None)
        
    return results

def load_tlt_intraday(date_str: str) -> pd.DataFrame:
    """Load TLT 1-min OHLCV for given date. Returns empty DataFrame if not found."""
    year, month = date_str[:4], date_str[4:6]
    tlt_path = Path(THETADATA_DIR) / "data_underlying_derived" / "TLT" / year / month / f"TLT_{date_str}.parquet"
    if not tlt_path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(tlt_path)
        df['dt'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('dt')
        df = df[(df['dt'].dt.time >= dt_time(8, 0)) & (df['dt'].dt.time <= dt_time(17, 0))]
        df['close'] = df['close'].ffill()
        return df[['dt', 'close']].reset_index(drop=True)
    except:
        return pd.DataFrame()


def compute_ib_range_percentile(current_ib_range: float, historical_ibs: list) -> float:
    """Percentile rank of today's IB range vs past N days. 0=tightest, 1=widest."""
    past_ranges = [h['ib_high'] - h['ib_low'] for h in historical_ibs if h is not None]
    if not past_ranges:
        return 0.5
    return sum(r < current_ib_range for r in past_ranges) / len(past_ranges)

def compute_gap_features(series: list, historical_ibs: list, ib_high: float, ib_low: float) -> dict:
    """Compute overnight gap features. Returns dict with 3 keys."""
    if not historical_ibs or historical_ibs[0] is None or not series:
        return {"gap_pct": 0.0, "gap_direction": 0.0, "overnight_vs_ib_ratio": 0.0}
    d1_close = historical_ibs[0]['close_price']
    today_open = series[0].get('price', 0)
    if d1_close <= 0 or today_open <= 0:
        return {"gap_pct": 0.0, "gap_direction": 0.0, "overnight_vs_ib_ratio": 0.0}
    gap_pct = np.clip((today_open - d1_close) / d1_close, -0.02, 0.02)
    gap_direction = 1.0 if gap_pct > 0.001 else (-1.0 if gap_pct < -0.001 else 0.0)
    ib_range = ib_high - ib_low + 1e-6
    overnight_vs_ib_ratio = np.clip(abs(today_open - d1_close) / ib_range, 0.0, 3.0)
    return {"gap_pct": float(gap_pct), "gap_direction": float(gap_direction),
            "overnight_vs_ib_ratio": float(overnight_vs_ib_ratio)}

def compute_opex_proximity(date_str: str) -> dict:
    """Compute OpEx proximity features using calendar module."""
    dt = datetime.strptime(date_str, "%Y%m%d")
    year, month = dt.year, dt.month
    cal = calendar.Calendar(firstweekday=0)
    fridays = [d for d in cal.itermonthdays2(year, month) if d[0] != 0 and d[1] == 4]
    third_friday = fridays[2][0] if len(fridays) >= 3 else fridays[-1][0]
    opex_date = datetime(year, month, third_friday)
    days_to_opex = (opex_date - dt).days
    if days_to_opex < 0:
        nm = month + 1 if month < 12 else 1
        ny = year if month < 12 else year + 1
        fridays_next = [d for d in calendar.Calendar().itermonthdays2(ny, nm) if d[0] != 0 and d[1] == 4]
        third_friday_next = fridays_next[2][0] if len(fridays_next) >= 3 else fridays_next[-1][0]
        opex_date = datetime(ny, nm, third_friday_next)
        days_to_opex = (opex_date - dt).days
    is_quarterly = opex_date.month in (3, 6, 9, 12)
    return {
        "days_to_opex_norm": float(np.clip(days_to_opex / 21.0, 0.0, 1.0)),
        "is_opex_week": 1.0 if abs(days_to_opex) <= 5 else 0.0,
        "is_quarterly_opex_week": 1.0 if abs(days_to_opex) <= 5 and is_quarterly else 0.0
    }

def compute_daily_rvol_iv_ratio(historical_ibs: list, atm_iv_open: float) -> dict:
    """Compute Volatility Risk Premium regime from daily close-to-close returns vs ATM IV."""
    fallback = {"rvol_iv_log": 0.0, "rvol_trend": 0.0, "rvol_regime": 1.0}
    closes = [h['close_price'] for h in historical_ibs if h is not None and h.get('close_price', 0) > 0]
    if len(closes) < 5:
        return fallback
    closes_arr = np.array(closes[::-1])
    log_rets = np.diff(np.log(closes_arr))
    if len(log_rets) < 5:
        return fallback
    rvol_full = float(np.std(log_rets) * np.sqrt(252))
    ratio = rvol_full / (atm_iv_open + 1e-6)
    rvol_iv_log = float(np.clip(np.log(max(ratio, 1e-6)), -1.5, 1.5))
    rvol_5d = float(np.std(log_rets[-5:]) * np.sqrt(252))
    rvol_trend = float(np.clip((rvol_5d - rvol_full) / (atm_iv_open + 1e-6), -1.0, 1.0))
    rvol_regime = 0.0 if ratio < 0.85 else (2.0 if ratio > 1.15 else 1.0)
    return {"rvol_iv_log": rvol_iv_log, "rvol_trend": rvol_trend, "rvol_regime": rvol_regime}

def get_price_n_minutes_ago(price_history: deque, current_min: float, n_min: int):
    """Strictly backward-looking price retrieval from deque of (minutes_since_open, price)."""
    target_min = current_min - n_min
    best_price = None
    best_diff = float('inf')
    for (t, p) in price_history:
        if t > current_min:
            continue
        diff = abs(t - target_min)
        if diff < best_diff:
            best_diff = diff
            best_price = p
    if best_diff > 2.0:
        return None
    return best_price

def compute_gamma_speed(df_pq, spot: float, day_atr: float, delta_s: float = None) -> float:
    """Approximate Speed = ∂Gamma/∂Spot from strike-level gamma data."""
    if 'pq_net_gamma' not in df_pq.columns or df_pq.empty:
        return 0.0
    
    # Adaptive delta_s based on spot scale if not provided
    if delta_s is None:
        delta_s = 5.0 if spot > 1000 else 1.0
        
    g_by_strike = df_pq.groupby('strike')['pq_net_gamma'].sum()
    strikes = g_by_strike.index.values
    if len(strikes) < 2:
        return 0.0
    idx_upper = int(np.argmin(np.abs(strikes - (spot + delta_s))))
    idx_lower = int(np.argmin(np.abs(strikes - (spot - delta_s))))
    if idx_upper == idx_lower:
        return 0.0
    gamma_upper = float(g_by_strike.iloc[idx_upper])
    gamma_lower = float(g_by_strike.iloc[idx_lower])
    speed_raw = (gamma_upper - gamma_lower) / (2.0 * delta_s)
    # Scale by ATR, but avoid hard clipping which collapses QQQ to ~constant.
    # Use a signed log compression so extreme values remain distinguishable.
    speed_scaled = speed_raw * (day_atr ** 2)
    speed_norm = np.sign(speed_scaled) * np.log1p(np.abs(speed_scaled))
    speed_norm = np.clip(speed_norm, -20.0, 20.0)
    return float(speed_norm)

# Añadir esta función helper antes de process_ticker_date()
def get_trend_context(series: list, current_idx: int, lookback: int = 30) -> float:
    """
    Retorna el slope normalizado de los últimos N minutos.
    Positivo = tendencia alcista, Negativo = bajista.
    Rango aprox: -1.0 a +1.0
    """
    start = max(0, current_idx - lookback)
    prices = [series[i].get("price", 0) for i in range(start, current_idx + 1)]
    prices = [p for p in prices if p > 0]
    if len(prices) < 5:
        return 0.0
    x = np.arange(len(prices), dtype=float)
    slope = np.polyfit(x, prices, 1)[0]
    # Normalizar por precio
    return float(np.clip(slope / (prices[-1] * 0.0001), -1.0, 1.0))


def process_ticker_date(args: tuple) -> list:
    ticker, target_date = args
    if ticker not in ["SPX", "QQQ"]:
        return [], 0.0, 0, 0, 0

    greek_ticker = "SPXW" if ticker == "SPX" else ticker
    date_str = target_date.strftime("%Y%m%d")
    year, month = date_str[:4], date_str[4:6]
    samples = []
    
    ib_data = load_ohlc_data(ticker, date_str)
    if not ib_data: 
        print(f"[DEBUG {ticker} {date_str}] ABORTADO: No se encontró data OHLC de IB.")
        return []
    ib_high, ib_low, series = ib_data["ib_high"], ib_data["ib_low"], ib_data["series"]
    if not series: 
        print(f"[DEBUG {ticker} {date_str}] ABORTADO: La serie de precios está vacía.")
        return []
    
    if ib_high == 0 or ib_low == 0 or (ib_high - ib_low) / ib_low > 0.05 or len(series) < 390: 
        print(f"[DEBUG {ticker} {date_str}] ABORTADO: IB High o IB Low es 0 o spread muy ancho (>5%). Datos corruptos.")
        return []
    
    fib_levels = calculate_fibonacci_levels(ib_high, ib_low)
    
    price_by_time = {}
    for i, candle in enumerate(series):
        time_str = candle.get("time", "")
        price_by_time[time_str] = (i, candle.get("price", 0))
        
    iv_file = get_parquet_file(greek_ticker, date_str, is_0dte=True, folder="iv", suffix="iv")
    df_iv = None
    if iv_file:
        try:
            df_iv = pd.read_parquet(iv_file)
            df_iv['dt'] = pd.to_datetime(df_iv['underlying_timestamp'])
        except Exception as e: 
            print(f"[DEBUG {ticker} {date_str}] ERROR leyendo IV: {e}")
    else:
        print(f"[DEBUG {ticker} {date_str}] ADVERTENCIA: No se encontró archivo IV.")
    iv_history = deque(maxlen=60)
        
    vix_data = load_vix_data(date_str)
    vix_spot, vix_gamma, vix_regime = vix_data["vix_spot"], vix_data["vix_gamma"], vix_data["vix_regime"]
    
    if vix_spot == 0 or vix_gamma == 0:
        print(f"[DEBUG {ticker} {date_str}] ADVERTENCIA: VIX Spot o Gamma es 0. Continuando con VIX nulo.")
        # Se permite continuar aunque no haya VIX, usará valores neutros
        
    weekly_features = {
        "wk_net_gamma": 0.0, "wk_net_vanna": 0.0, "wk_net_charm": 0.0,
        "wk_net_dgex": 0.0, "wk_net_zomma": 0.0, "wk_net_delta": 0.0,
        "wk_net_vega": 0.0, "wk_net_vomma": 0.0,
        # NOTE: wk_dist_to_* removed — tautological with target (r≈-0.59)
        "wk_gamma_regime": 0.5, "wk_vanna_bullish": 0,
        "wk_dgex_sticky": 0, "wk_zomma_stabilizing": 0,
    }

    wk_exp_cache = {}

    try:
        daily_file = get_parquet_file(greek_ticker, date_str, is_0dte=True)
        weekly_file = get_parquet_file(greek_ticker, date_str, is_0dte=False)
        
        if not daily_file or not weekly_file: 
            print(f"[DEBUG {ticker} {date_str}] ABORTADO: Faltan archivos daily_file ({bool(daily_file)}) o weekly_file ({bool(weekly_file)}).")
            return []
        
        df_daily = pd.read_parquet(daily_file)
        df_weekly = pd.read_parquet(weekly_file)
        
        oi_daily_file = Path(OPTIONS_DIR) / greek_ticker / "oi" / year / month / daily_file.name.replace("greeks.parquet", "oi.parquet")
        oi_weekly_file = Path(OPTIONS_DIR) / greek_ticker / "oi" / year / month / weekly_file.name.replace("greeks.parquet", "oi.parquet")
        
        if not oi_daily_file.exists() or not oi_weekly_file.exists(): 
            print(f"[DEBUG {ticker} {date_str}] ABORTADO: Faltan archivos Open Interest (OI) diarios o semanales.")
            return []

        df_oi_daily = pd.read_parquet(oi_daily_file)
        df_oi_weekly = pd.read_parquet(oi_weekly_file)
        
        df_oi_daily_agg = df_oi_daily.groupby(['strike', 'right']).agg({'open_interest': 'max'}).reset_index()
        df_oi_weekly_agg = df_oi_weekly.groupby(['strike', 'right']).agg({'open_interest': 'max'}).reset_index()
        
        df_daily['dt'] = pd.to_datetime(df_daily['underlying_timestamp'])
        df_weekly['dt'] = pd.to_datetime(df_weekly['underlying_timestamp'])
        
        df_daily = df_daily[(df_daily['dt'].dt.time >= dt_time(8, 0)) & (df_daily['dt'].dt.time <= dt_time(17, 0))]
        
        df_pq_daily_all = pd.merge(df_daily, df_oi_daily_agg, on=['strike', 'right'], how='inner')
        df_pq_weekly_all = pd.merge(df_weekly, df_oi_weekly_agg, on=['strike', 'right'], how='inner')
        
        groups_daily = df_pq_daily_all.groupby('dt')
        groups_weekly = df_pq_weekly_all.groupby('dt')
        
        timestamps = sorted(df_daily['dt'].unique())
        prev_vals = None

        daily_ohlc_file = get_parquet_file(greek_ticker, date_str, is_0dte=True, folder="ohlc", suffix="ohlc")
        df_ohlc_daily = None
        if daily_ohlc_file:
            try:
                df_ohlc_daily = pd.read_parquet(daily_ohlc_file)
                if 'timestamp' in df_ohlc_daily.columns:
                    df_ohlc_daily['dt'] = pd.to_datetime(df_ohlc_daily['timestamp'])
            except:
                df_ohlc_daily = None

        historical_ibs = load_historical_ib_levels(greek_ticker, date_str, n_days=10)
        tlt_df = load_tlt_intraday(date_str)

        gap_features = compute_gap_features(series, historical_ibs, ib_high, ib_low)
        opex_features = compute_opex_proximity(date_str)
        ib_range_percentile_val = compute_ib_range_percentile(ib_high - ib_low, historical_ibs)

        atm_iv_open = 0.15
        if df_iv is not None and not df_iv.empty:
            try:
                df_iv_open = df_iv[df_iv['dt'].dt.time >= dt_time(9, 30)].sort_values('dt')
                if not df_iv_open.empty:
                    ts_open = df_iv_open['dt'].iloc[0]
                    spot_open_approx = series[0].get('price', 5000)
                    mask = df_iv_open['dt'] == ts_open
                    if mask.any():
                        closest_idx = (df_iv_open[mask]['strike'] - spot_open_approx).abs().idxmin()
                        atm_iv_open_raw = float(df_iv_open.loc[closest_idx, 'implied_vol'])
                        atm_iv_open = atm_iv_open_raw / 100.0 if atm_iv_open_raw > 1.0 else atm_iv_open_raw
                        atm_iv_open = max(atm_iv_open, 0.05)
            except:
                pass
        vrp_features = compute_daily_rvol_iv_ratio(historical_ibs, atm_iv_open)

        day_prices = [c.get("price", 0) for c in series if c.get("price", 0) > 0]
        wonham_probs = compute_wonham_filter(day_prices)
        wonham_by_time = {}
        wonham_idx = 0
        for c in series:
            if c.get("price", 0) > 0:
                time_key_w = c.get("time", "")
                if wonham_idx < len(wonham_probs):
                    wonham_by_time[time_key_w] = wonham_probs[wonham_idx]
                    wonham_idx += 1

        price_window_for_atr = deque(maxlen=16)
        price_history = deque(maxlen=35)
        tlt_price_history = deque(maxlen=35)
        pcr_history = deque(maxlen=32)
        net_charm_history = deque(maxlen=5)
        net_gamma_window = deque(maxlen=60)
        day_atr = 1.0
        session_length = 390.0
        daily_atrs = []
        
        for ts_np in timestamps:
            ts = pd.to_datetime(ts_np)
            time_key = ts.strftime("%H:%M")
            if time_key not in price_by_time: continue
            series_idx, series_price = price_by_time[time_key]
            target_label, time_to_target, time_to_stop, max_move = 0, 0, 0, 0.0
            
            wk_exp = None
            if ts in groups_weekly.groups:
                df_pq_wk = groups_weekly.get_group(ts).copy()
                if not df_pq_wk.empty:
                    df_pq_wk.loc[df_pq_wk['underlying_price'] <= 0, 'underlying_price'] = series_price
                    df_pq_wk['T'] = calculate_exact_t(ts)
                    wk_exp = get_net_exposures_from_parquet(df_pq_wk)
            
            # ── FIX: Update weekly_features DYNAMICALLY at each timestamp ──
            # Previously, weekly greeks were fetched once from 15:45 PM (end-of-day)
            # for every minute of the day — massive lookahead bias (p < 10^-200).
            # Now we evaluate weekly greeks at the CURRENT timestamp `ts`.
            if wk_exp:
                weekly_features = {
                    "wk_net_gamma":         safe_log(wk_exp["net_gamma"]),
                    "wk_net_vanna":         safe_log(wk_exp["net_vanna"]),
                    "wk_net_charm":         safe_log(wk_exp["net_charm"]),
                    "wk_net_dgex":          safe_log(wk_exp["net_dgex"]),
                    "wk_net_zomma":         safe_log(wk_exp["net_zomma"]),
                    "wk_net_delta":         safe_log(wk_exp["net_delta"]),
                    "wk_net_vega":          safe_log(wk_exp["net_vega"]),
                    "wk_net_vomma":         safe_log(wk_exp["net_vomma"]),
                    "wk_gamma_regime":      classify_gamma_regime(wk_exp["net_gamma"]) / 2.0,
                    "wk_vanna_bullish":     1 if wk_exp["net_vanna"] > 0.1 else 0,
                    "wk_dgex_sticky":       1 if wk_exp["net_dgex"] > 0.1 else 0,
                    "wk_zomma_stabilizing": 1 if wk_exp["net_zomma"] > 0.1 else 0,
                }
                wk_exp_cache = {
                    "max_gamma_strike": wk_exp["max_gamma_strike"],
                    "min_gamma_strike": wk_exp["min_gamma_strike"],
                    "max_dgex_strike":  wk_exp["max_dgex_strike"],
                    "min_dgex_strike":  wk_exp["min_dgex_strike"],
                    "max_vega_strike":  wk_exp.get("max_vega_strike", 0.0),
                    "min_vega_strike":  wk_exp.get("min_vega_strike", 0.0),
                    "max_vomma_strike": wk_exp.get("max_vomma_strike", 0.0),
                    "min_vomma_strike": wk_exp.get("min_vomma_strike", 0.0),
                }

            if ts not in groups_daily.groups: continue
            df_pq = groups_daily.get_group(ts).copy()
            if df_pq.empty: continue
            
            df_pq.loc[df_pq['underlying_price'] <= 0, 'underlying_price'] = series_price
            df_pq['T'] = calculate_exact_t(ts)
            exp = get_net_exposures_from_parquet(df_pq)
            if not exp: continue
            spot = exp["spot_price"]
            
            # ── Rolling ATR (causal, 15-bar) ──
            price_window_for_atr.append(spot)
            if len(price_window_for_atr) >= 3:
                prices_arr = np.array(price_window_for_atr)
                abs_returns = np.abs(np.diff(prices_arr))
                if len(abs_returns) >= 2:
                    day_atr = float(np.mean(abs_returns[:-1]))
                    day_atr = max(day_atr, 0.5)

            atr_denom = day_atr + 1e-6

            # ── Weekly guard ──
            if not wk_exp_cache:
                # No weekly data seen yet at this timestamp — skip until first weekly snapshot arrives
                continue
            daily_atrs.append(day_atr)

            # ── Time encoding ──
            minutes_since_open = max(0, (ts.hour * 60 + ts.minute) - (9 * 60 + 30))
            time_sin = float(np.sin(2 * np.pi * minutes_since_open / session_length))
            time_cos = float(np.cos(2 * np.pi * minutes_since_open / session_length))
            minutes_to_close = max(0.0, session_length - minutes_since_open)
            minutes_to_close_norm = minutes_to_close / session_length
            dow = ts.dayofweek
            dow_sin = float(np.sin(2 * np.pi * dow / 5))
            dow_cos = float(np.cos(2 * np.pi * dow / 5))

            price_history.append((minutes_since_open, spot))
            
            # ── ATM IV ──
            atm_iv = 0.0
            iv_zscore = 0.0
            iv_pct = 0.5
            if df_iv is not None and not df_iv.empty:
                df_iv_min = df_iv[df_iv['dt'] == ts_np]
                if not df_iv_min.empty:
                    closest_idx = (df_iv_min['strike'] - spot).abs().idxmin()
                    closest_strike = df_iv_min.loc[closest_idx, 'strike']
                    atm_iv = float(df_iv_min[df_iv_min['strike'] == closest_strike]['implied_vol'].mean())
            if atm_iv > 0:
                iv_history.append(atm_iv)
                iv_mean = np.mean(iv_history)
                iv_std = np.std(iv_history) if len(iv_history) > 1 else 0
                iv_zscore = float((atm_iv - iv_mean) / iv_std) if iv_std > 0 else 0.0
                iv_min, iv_max = min(iv_history), max(iv_history)
                iv_pct = float((atm_iv - iv_min) / (iv_max - iv_min)) if iv_max > iv_min else 0.5
            else:
                atm_iv = float(iv_history[-1]) if len(iv_history) > 0 else 0.0
                
            # ── Proximity-Gated Labeling ──
            key_levels = [
                exp["max_gamma_strike"], exp["min_gamma_strike"],
                exp["min_vanna_strike"], exp["zero_gamma"],
                exp["max_dgex_strike"], exp["min_dgex_strike"],
                exp.get("max_vega_strike", 0), exp.get("min_vega_strike", 0),
                exp.get("max_vomma_strike", 0), exp.get("min_vomma_strike", 0),
                ib_high, ib_low,
                fib_levels["fib_127_up"], fib_levels["fib_161_up"], fib_levels["fib_200_up"],
                fib_levels["fib_127_dn"], fib_levels["fib_161_dn"], fib_levels["fib_200_dn"],
            ]
            for hi in historical_ibs[:5]:
                if hi is not None:
                    key_levels.extend([hi["ib_high"], hi["ib_low"]])
            if wk_exp_cache:
                key_levels.extend([
                    wk_exp_cache.get("max_gamma_strike", 0), wk_exp_cache.get("min_gamma_strike", 0),
                    wk_exp_cache.get("max_dgex_strike", 0), wk_exp_cache.get("min_dgex_strike", 0),
                ])
                if wk_exp_cache.get("max_gamma_strike") == 0 or wk_exp_cache.get("min_gamma_strike") == 0 or wk_exp_cache.get("max_dgex_strike") == 0 or wk_exp_cache.get("min_dgex_strike") == 0:
                    print(f"[DEBUG {ticker} {date_str}] ABORTADO: Weekly Greek levels son 0.")
                    continue  # skip este timestamp, no abortar el día entero
            key_levels = [l for l in key_levels if l is not None and l > 0]
            near_sr = proximity_gate(spot, key_levels, LEVEL_PROXIMITY_THRESHOLD)

            # ── Vanna Magnet ──
            min_vanna = exp.get("min_vanna_strike", 0)
            vanna_touched_today = False
            if min_vanna > 0:
                prices_so_far = [s.get("price", spot) for s in series[:series_idx + 1]]
                high_so_far = max(prices_so_far)
                low_so_far = min(prices_so_far)
                buffer = min_vanna * LEVEL_PROXIMITY_THRESHOLD
                if (low_so_far - buffer) <= min_vanna <= (high_so_far + buffer):
                    vanna_touched_today = True
            dist_to_vanna_pct = abs(spot - min_vanna) / spot if min_vanna > 0 else 0
            magnet_active = (not vanna_touched_today) and (0.0015 < dist_to_vanna_pct < 0.015)

            if near_sr or magnet_active:
                if atm_iv > 0.001:
                    implied_move_pct = atm_iv * np.sqrt(LOOKAHEAD_MINUTES / (252 * 390))
                else:
                    implied_move_pct = 0.004
                implied_move_pct = float(np.clip(implied_move_pct, 0.0015, 0.01))

                # ── Contexto de tendencia para ajustar asimetría ──
                trend = get_trend_context(series, series_idx, lookback=30)
                # En tendencia fuerte, el lado contrario a la tendencia es más difícil
                # trend > 0.3 → mercado alcista → exigir más al SHORT, facilitar LONG
                # trend < -0.3 → mercado bajista → exigir más al LONG, facilitar SHORT

                if magnet_active:
                    dynamic_profit_pct = dist_to_vanna_pct
                    noise_floor_pct = (day_atr * 2) / spot
                    dynamic_stop_pct = max(dist_to_vanna_pct / 3.0, noise_floor_pct)
                    target_label, time_to_target, time_to_stop, max_move = calculate_target_label(
                        series, series_idx,
                        profit_pct=dynamic_profit_pct,
                        stop_pct=dynamic_stop_pct,
                        lookahead=LOOKAHEAD_MINUTES
                    )
                else:
                    target_label, time_to_target, time_to_stop, max_move = calculate_target_label_asymmetric(
                        series, series_idx,
                        long_profit_pct=FIXED_PROFIT_PCT,
                        short_profit_pct=FIXED_PROFIT_PCT,
                        long_stop_pct=FIXED_STOP_PCT,
                        short_stop_pct=FIXED_STOP_PCT,
                        lookahead=LOOKAHEAD_MINUTES
                    )
            else:
                target_label, time_to_target, time_to_stop, max_move = 0, 0, 0, 0.0
            
            gamma_regime = classify_gamma_regime(exp["net_gamma"])
            vanna_bullish = 1 if exp["net_vanna"] > 0.1 else 0
            charm_bullish = 1 if exp["net_charm"] > 0.1 else 0
            dgex_sticky = 1 if exp["net_dgex"] > 0.1 else 0
            zomma_stabilizing = 1 if exp["net_zomma"] > 0.1 else 0
            vega_elevated = 1 if abs(exp["net_vega"]) > 0.1 else 0
            
            price_vs_ib_high = dist_bps(spot, ib_high)
            price_vs_ib_low = dist_bps(spot, ib_low)
            ib_range_pct = (ib_high - ib_low) / spot if spot > 0 else 0
            
            near_min_vanna = 1 if is_near_level(spot, exp["min_vanna_strike"]) else 0
            near_ib_high = 1 if is_near_level(spot, ib_high) else 0
            near_ib_low = 1 if is_near_level(spot, ib_low) else 0
            above_ib = 1 if spot > ib_high else 0
            below_ib = 1 if spot < ib_low else 0
            in_ib_range = 1 if ib_low <= spot <= ib_high else 0
            
            prices_before = [series[i].get("price", 0) for i in range(max(0, series_idx - 15), series_idx + 1)]
            rsi = simple_rsi(prices_before)
            total_vol = ib_data.get("total_volume", 1)
            current_vol = series[series_idx].get("volume", 0) if series_idx < len(series) else 0
            vol_relative = current_vol / (total_vol / len(series)) if total_vol > 0 and len(series) > 0 else 1.0

            # ── Volatility-adjusted returns ──
            atm_iv_current = atm_iv if atm_iv > 0.001 else 0.15
            ret_features = {}
            for label, lb in [("1m", 1), ("5m", 5), ("15m", 15)]:
                past_price = get_price_n_minutes_ago(price_history, minutes_since_open, lb)
                if past_price is not None and past_price > 0:
                    raw_return = (spot - past_price) / past_price
                    vol_norm = atm_iv_current * np.sqrt(lb / (252.0 * 390.0)) + 1e-8
                    ret_features[f"ret_{label}_vol_adj"] = float(np.clip(raw_return / vol_norm, -5.0, 5.0))
                else:
                    ret_features[f"ret_{label}_vol_adj"] = 0.0

            # ── Delta-filtered PCR proxy ──
            delta_filtered_pcr_norm = 0.0
            pcr_derivative_5m_clipped = 0.0
            if df_ohlc_daily is not None and 'dt' in df_ohlc_daily.columns:
                df_ohlc_min = df_ohlc_daily[df_ohlc_daily['dt'] == ts_np]
                if not df_ohlc_min.empty and 'volume' in df_ohlc_min.columns:
                    otm_range = 1.5 * day_atr
                    df_calls_otm = df_ohlc_min[
                        (df_ohlc_min['right'].str.upper() == 'CALL') &
                        (df_ohlc_min['strike'].between(spot, spot + otm_range))
                    ]
                    df_puts_otm = df_ohlc_min[
                        (df_ohlc_min['right'].str.upper() == 'PUT') &
                        (df_ohlc_min['strike'].between(spot - otm_range, spot))
                    ]
                    call_vol = float(df_calls_otm['volume'].sum())
                    put_vol = float(df_puts_otm['volume'].sum())
                    delta_filtered_pcr_raw = put_vol / (call_vol + 1e-6)
                    delta_filtered_pcr_norm = float(np.clip(np.log1p(delta_filtered_pcr_raw) / np.log1p(5.0), 0.0, 1.0))
                    pcr_history.append(delta_filtered_pcr_raw)
                    if len(pcr_history) >= 5:
                        pcr_derivative_5m_clipped = float(np.clip(
                            (list(pcr_history)[-1] - list(pcr_history)[-5]) / 5.0, -1.0, 1.0))

            # ── Charm acceleration ──
            net_charm_history.append(exp["net_charm"])
            charm_accel_weighted = 0.0
            if len(net_charm_history) >= 3:
                charm_arr = np.array(list(net_charm_history)[-3:])
                charm_accel = charm_arr[-1] - 2.0 * charm_arr[-2] + charm_arr[-3]
                charm_accel_norm = float(np.clip(charm_accel / (atm_iv_current + 1e-6), -5.0, 5.0))
                close_weight = 1.0 + np.exp(-minutes_to_close / 60.0)
                charm_accel_weighted = float(np.clip(charm_accel_norm * close_weight, -10.0, 10.0))

            # NOTE: delta_s must be adaptive by spot scale (SPX vs QQQ).
            # Passing a fixed 5.0 was suppressing QQQ signal because QQQ strike spacing is ~1.
            gamma_speed_val = compute_gamma_speed(df_pq, spot, day_atr)

            # ── Hilbert phase of net gamma ──
            net_gamma_window.append(exp["net_gamma"])
            hilbert_features = {"gamma_phase_sin": 0.0, "gamma_phase_cos": 0.0,
                                "gamma_amplitude_ratio": 0.0, "gamma_phase_delta": 0.0}
            if len(net_gamma_window) >= 30:
                try:
                    gamma_arr = np.array(net_gamma_window)
                    gamma_detrended = gamma_arr - np.mean(gamma_arr)
                    gamma_std = np.std(gamma_detrended) + 1e-8
                    gamma_normalized = gamma_detrended / gamma_std
                    pad_len = max(1, len(gamma_normalized) // 4)
                    left_pad = gamma_normalized[pad_len:0:-1]
                    right_pad = gamma_normalized[-2:-(pad_len + 2):-1]
                    padded_gamma = np.concatenate([left_pad, gamma_normalized, right_pad])
                    analytic_padded = scipy_hilbert(padded_gamma)
                    analytic_signal = analytic_padded[len(left_pad):len(left_pad) + len(gamma_normalized)]
                    amplitude_envelope = np.abs(analytic_signal)
                    instant_phase = np.angle(analytic_signal)
                    current_phase = float(instant_phase[-1])
                    current_amplitude = float(amplitude_envelope[-1])
                    mean_amplitude = float(np.mean(amplitude_envelope))
                    amplitude_ratio = float(np.clip(current_amplitude / (mean_amplitude + 1e-8), 0.0, 3.0))
                    phase_delta_norm = 0.0
                    if len(net_gamma_window) >= 2:
                        unwrapped = np.unwrap(instant_phase)
                        phase_delta_norm = float(np.clip((unwrapped[-1] - unwrapped[-2]) / np.pi, -1.0, 1.0))
                    signal_quality = 1.0 if amplitude_ratio > 0.5 else 0.0
                    hilbert_features = {
                        "gamma_phase_sin": float(np.sin(current_phase)) * signal_quality,
                        "gamma_phase_cos": float(np.cos(current_phase)) * signal_quality,
                        "gamma_amplitude_ratio": amplitude_ratio,
                        "gamma_phase_delta": phase_delta_norm * signal_quality,
                    }
                except:
                    pass

            # ── Signal Persistence ──
            net_charm_history.append(math.copysign(1.0, exp["net_charm"]))
            signal_persistence_5m = 0
            if len(net_charm_history) > 0:
                current_bias = net_charm_history[-1]
                for x in reversed(net_charm_history):
                    if x == current_bias: signal_persistence_5m += current_bias
                    else: break

            # ── TLT rate of change ──
            tlt_features = {"tlt_ret_1m": 0.0, "tlt_ret_5m": 0.0, "tlt_ret_15m": 0.0}
            if not tlt_df.empty:
                past_rows = tlt_df[tlt_df['dt'] <= ts]
                tlt_now = float(past_rows.iloc[-1]['close']) if not past_rows.empty else None
                if tlt_now is not None:
                    tlt_price_history.append((minutes_since_open, tlt_now))
                    tlt_norm_base = 0.05
                    for label, lb in [("1m", 1), ("5m", 5), ("15m", 15)]:
                        tlt_past = get_price_n_minutes_ago(tlt_price_history, minutes_since_open, lb)
                        if tlt_past is not None and tlt_past > 0:
                            tlt_norm = tlt_norm_base * np.sqrt(lb)
                            tlt_features[f"tlt_ret_{label}"] = float(np.clip(
                                (tlt_now - tlt_past) / (tlt_norm + 1e-8), -3.0, 3.0))

            # ── Historical IB distance features (D-1 to D-5) ──
            hist_ib_features = {}
            for i in range(5):
                d = i + 1
                hist = historical_ibs[i] if i < len(historical_ibs) else None
                if hist is not None:
                    ib_h = hist['ib_high']
                    ib_l = hist['ib_low']
                    prev_close = hist['close_price']
                    ib_mid = (ib_h + ib_l) / 2.0
                    ib_width = ib_h - ib_l + 1e-6
                    hist_ib_features[f"dist_ib_high_D{d}"] = dist_bps(spot, ib_h)
                    hist_ib_features[f"dist_ib_low_D{d}"] = dist_bps(spot, ib_l)
                    hist_ib_features[f"prev_close_vs_ib_D{d}"] = float(np.clip((prev_close - ib_mid) / ib_width, -2.0, 2.0))
                else:
                    hist_ib_features[f"dist_ib_high_D{d}"] = 0.0
                    hist_ib_features[f"dist_ib_low_D{d}"] = 0.0
                    hist_ib_features[f"prev_close_vs_ib_D{d}"] = 0.0

            # ── D-1 IB confluences ──
            d1_confluence = {}
            spx_sigma = max((ib_high - ib_low) / (spot + 1e-6) * 0.5, 0.005)
            if len(historical_ibs) >= 1 and historical_ibs[0] is not None:
                d1_ib_high = historical_ibs[0]['ib_high']
                d1_ib_low = historical_ibs[0]['ib_low']
                d1_confluence["confluence_d1ibh_max_gamma"] = rbf_confluence(d1_ib_high, exp["max_gamma_strike"], spot, sigma=spx_sigma)
                d1_confluence["confluence_d1ibl_min_gamma"] = rbf_confluence(d1_ib_low, exp["min_gamma_strike"], spot, sigma=spx_sigma)
                d1_confluence["confluence_d1ibh_max_dgex"] = rbf_confluence(d1_ib_high, exp["max_dgex_strike"], spot, sigma=spx_sigma)
                d1_confluence["confluence_d1ibl_min_dgex"] = rbf_confluence(d1_ib_low, exp["min_dgex_strike"], spot, sigma=spx_sigma)
                d1_confluence["confluence_d1ibh_max_vomma"] = rbf_confluence(d1_ib_high, exp.get("max_vomma_strike"), spot, sigma=spx_sigma)
                d1_confluence["confluence_d1ibh_ibh_today"] = rbf_confluence(d1_ib_high, ib_high, spot, sigma=spx_sigma)
                d1_confluence["confluence_d1ibl_ibl_today"] = rbf_confluence(d1_ib_low, ib_low, spot, sigma=spx_sigma)
            else:
                for key in ["confluence_d1ibh_max_gamma", "confluence_d1ibl_min_gamma",
                            "confluence_d1ibh_max_dgex", "confluence_d1ibl_min_dgex",
                            "confluence_d1ibh_max_vomma", "confluence_d1ibh_ibh_today",
                            "confluence_d1ibl_ibl_today"]:
                    d1_confluence[key] = 0.0

            # ══════════════════════════════════════════════════════
            #  LEVEL IDENTITY + GREEK × LEVEL INTERACTIONS
            #
            #  These encode YOUR trading hypothesis directly:
            #  "net_delta>0 AND net_gamma>0 AND vanna<0 AT a fib
            #   extension of the IB → LONG"
            #
            #  Without explicit interaction terms, the model must
            #  discover these conjunctions from the full feature
            #  product space, which requires far more data.
            # ══════════════════════════════════════════════════════

            # Named IB + Fib levels for identity lookup
            named_levels = {
                "ib_high":    ib_high,
                "ib_low":     ib_low,
                "fib_127_up": fib_levels["fib_127_up"],
                "fib_161_up": fib_levels["fib_161_up"],
                "fib_200_up": fib_levels["fib_200_up"],
                "fib_127_dn": fib_levels["fib_127_dn"],
                "fib_161_dn": fib_levels["fib_161_dn"],
                "fib_200_dn": fib_levels["fib_200_dn"],
            }
            nearest_level_id, nearest_level_dist_bps = get_nearest_level_identity(spot, named_levels)

            # Boolean proximity flags (raw, for interactions)
            near_any_fib_up = (
                is_near_level(spot, fib_levels["fib_127_up"]) or
                is_near_level(spot, fib_levels["fib_161_up"]) or
                is_near_level(spot, fib_levels["fib_200_up"])
            )
            near_any_fib_dn = (
                is_near_level(spot, fib_levels["fib_127_dn"]) or
                is_near_level(spot, fib_levels["fib_161_dn"]) or
                is_near_level(spot, fib_levels["fib_200_dn"])
            )
            near_ib = bool(near_ib_high or near_ib_low)

            net_delta_val  = exp.get("net_delta", 0.0)
            net_gamma_val  = exp["net_gamma"]
            net_vanna_val  = exp["net_vanna"]

            # ── Greek × Level interaction scalars ──────────────────────────
            # These are the direct feature-products the FiLM / attention
            # architecture would otherwise need thousands of samples to infer.

            gamma_x_near_fib_up  = safe_log(net_gamma_val) * float(near_any_fib_up)
            gamma_x_near_fib_dn  = safe_log(net_gamma_val) * float(near_any_fib_dn)
            gamma_x_near_ib      = safe_log(net_gamma_val) * float(near_ib)

            delta_x_near_fib_up  = safe_log(net_delta_val) * float(near_any_fib_up)
            delta_x_near_fib_dn  = safe_log(net_delta_val) * float(near_any_fib_dn)
            delta_x_near_ib_high = safe_log(net_delta_val) * float(near_ib_high)
            delta_x_near_ib_low  = safe_log(net_delta_val) * float(near_ib_low)

            vanna_x_near_fib_up  = safe_log(net_vanna_val) * float(near_any_fib_up)
            vanna_x_near_fib_dn  = safe_log(net_vanna_val) * float(near_any_fib_dn)
            vanna_x_near_ib      = safe_log(net_vanna_val) * float(near_ib)

            # ── Composite setup flags REMOVED ────────────────────────────
            # bull/bear_greek_setup had ~0.2% prevalence in train (55/26k rows)
            # and WR=0%. The underlying interaction features (gamma_x_near_*,
            # delta_x_near_*, vanna_x_near_*) already encode the signal.

            # ══════════════════════════════════════════════════════
            #  BUILD SAMPLE DICTIONARY — ALL FEATURES
            # ══════════════════════════════════════════════════════
            sample = {
                "ticker": ticker, "date": date_str, "time": time_key, "timestamp": ts,
                "spot_price": spot, "target": target_label, "time_to_target": time_to_target,
                "time_to_stop": time_to_stop, "max_move": max_move,
                # ── 0DTE Greek exposures ──
                "net_gamma": safe_log(exp["net_gamma"]),
                "net_vanna": safe_log(exp["net_vanna"]),
                "net_charm": safe_log(exp["net_charm"]),
                "net_dgex":  safe_log(exp["net_dgex"]),
                "net_zomma": safe_log(exp["net_zomma"]),
                "net_delta": safe_log(exp.get("net_delta", 0.0)),
                "signal_persistence_5m": float(signal_persistence_5m),
                "gamma_regime": gamma_regime, "vanna_bullish": vanna_bullish,
                "charm_bullish": charm_bullish, "dgex_sticky": dgex_sticky,
                "zomma_stabilizing": zomma_stabilizing,
                # ── Distance features in basis points ──
                "dist_to_max_gamma": dist_bps(spot, exp["max_gamma_strike"]),
                "dist_to_min_gamma": dist_bps(spot, exp["min_gamma_strike"]),
                "dist_to_min_vanna": dist_bps(spot, exp["min_vanna_strike"]),
                "dist_to_zero_gamma": dist_bps(spot, exp["zero_gamma"]),
                "dist_to_max_dgex": dist_bps(spot, exp["max_dgex_strike"]),
                "dist_to_min_dgex": dist_bps(spot, exp["min_dgex_strike"]),
                "near_min_vanna": near_min_vanna,
                # ── Weekly features ──
                **weekly_features,
                "gamma_0dte_vs_wk": sign_divergence(exp["net_gamma"], weekly_features["wk_net_gamma"]),
                "vanna_0dte_vs_wk": sign_divergence(exp["net_vanna"], weekly_features["wk_net_vanna"]),
                "dgex_0dte_vs_wk": sign_divergence(exp["net_dgex"], weekly_features["wk_net_dgex"]),
                "delta_0dte_vs_wk": sign_divergence(exp.get("net_delta", 0), weekly_features["wk_net_delta"]),
                "vega_0dte_vs_wk": sign_divergence(exp.get("net_vega", 0), weekly_features.get("wk_net_vega", 0)),
                "vomma_0dte_vs_wk": sign_divergence(exp.get("net_vomma", 0), weekly_features.get("wk_net_vomma", 0)),
                # ── IB features ──
                "price_vs_ib_high": price_vs_ib_high, "price_vs_ib_low": price_vs_ib_low,
                "ib_range_pct": ib_range_pct, "near_ib_high": near_ib_high, "near_ib_low": near_ib_low,
                "above_ib": above_ib, "below_ib": below_ib, "in_ib_range": in_ib_range,
                # ── Fibonacci distances SPX ──
                "dist_fib_127_up": dist_bps(spot, fib_levels["fib_127_up"]),
                "dist_fib_161_up": dist_bps(spot, fib_levels["fib_161_up"]),
                "dist_fib_200_up": dist_bps(spot, fib_levels["fib_200_up"]),
                "dist_fib_127_dn": dist_bps(spot, fib_levels["fib_127_dn"]),
                "dist_fib_161_dn": dist_bps(spot, fib_levels["fib_161_dn"]),
                "dist_fib_200_dn": dist_bps(spot, fib_levels["fib_200_dn"]),
                # ── IV / VIX context ──
                "atm_iv": atm_iv / 100.0 if atm_iv > 1 else atm_iv,
                "iv_zscore": np.clip(iv_zscore, -3, 3) / 3.0,
                "iv_percentile": iv_pct,
                "vix_spot": vix_spot / 50.0 if vix_spot > 0 else 0,
                "vix_gamma": safe_log(vix_gamma), "vix_regime": vix_regime / 2.0,
                "rsi": rsi / 100.0, "vol_relative": min(vol_relative, 5.0) / 5.0,
                # ── Greek ratios ──
                "gamma_vanna_ratio": safe_log(exp["net_gamma"] / (abs(exp["net_vanna"]) + 1e-6)),
                "dgex_gamma_ratio":  safe_log(exp["net_dgex"] / (abs(exp["net_gamma"]) + 1e-6)),
                "charm_vanna_ratio": safe_log(exp["net_charm"] / (abs(exp["net_vanna"]) + 1e-6)),
                "delta_gamma_ratio": safe_log(exp.get("net_delta", 0) / (abs(exp["net_gamma"]) + 1e-6)),
                "vega_gamma_ratio":  safe_log(exp.get("net_vega", 0) / (abs(exp["net_gamma"]) + 1e-6)),
                "vomma_vega_ratio":  safe_log(exp.get("net_vomma", 0) / (abs(exp.get("net_vega", 0)) + 1e-6)),
                # ── Temporal deltas ──
                "gamma_change": safe_log(exp["net_gamma"] - prev_vals["net_gamma"]) if prev_vals else 0.0,
                "vanna_change": safe_log(exp["net_vanna"] - prev_vals["net_vanna"]) if prev_vals else 0.0,
                "dgex_change":  safe_log(exp["net_dgex"] - prev_vals["net_dgex"]) if prev_vals else 0.0,
                "delta_change": safe_log(exp.get("net_delta", 0) - prev_vals.get("net_delta", 0)) if prev_vals else 0.0,
                "vega_change":  safe_log(exp.get("net_vega", 0) - prev_vals.get("net_vega", 0)) if prev_vals else 0.0,
                "vomma_change": safe_log(exp.get("net_vomma", 0) - prev_vals.get("net_vomma", 0)) if prev_vals else 0.0,
                "spot_change": ((spot - prev_vals["spot"])/prev_vals["spot"] * 10000.0) if prev_vals and prev_vals["spot"] > 0 else 0.0,
                "gamma_momentum": safe_log((exp["net_gamma"] - prev_vals["net_gamma"]) * np.sign(exp["net_gamma"])) if prev_vals else 0.0,
                "price_vs_dgex_magnet": (((spot - prev_vals["spot"])/prev_vals["spot"] * 10000.0)) * np.sign((spot - exp["max_dgex_strike"])/spot) if prev_vals and prev_vals["spot"] > 0 and exp["max_dgex_strike"] else 0.0,
                # ── 0DTE Vega/Vomma ──
                "net_vega":  safe_log(exp.get("net_vega", 0.0)),
                "net_vomma": safe_log(exp.get("net_vomma", 0.0)),
                "vega_elevated": vega_elevated,
                "dist_to_max_vega": dist_bps(spot, exp.get("max_vega_strike", 0)),
                "dist_to_min_vega": dist_bps(spot, exp.get("min_vega_strike", 0)),
                "dist_to_max_vomma": dist_bps(spot, exp.get("max_vomma_strike", 0)),
                "dist_to_min_vomma": dist_bps(spot, exp.get("min_vomma_strike", 0)),
                # ── Original SPX confluences ──
                "confluence_ib_high_max_gamma": rbf_confluence(ib_high, exp["max_gamma_strike"], spot, sigma=spx_sigma),
                "confluence_ib_low_min_gamma": rbf_confluence(ib_low, exp["min_gamma_strike"], spot, sigma=spx_sigma),
                "confluence_ib_high_max_vega": rbf_confluence(ib_high, exp.get("max_vega_strike"), spot, sigma=spx_sigma),
                "confluence_ib_low_max_dgex": rbf_confluence(ib_low, exp["max_dgex_strike"], spot, sigma=spx_sigma),
                "confluence_fib127_bull_max_gamma": rbf_confluence(fib_levels["fib_127_up"], exp["max_gamma_strike"], spot, sigma=spx_sigma),
                "confluence_fib161_bull_max_vega": rbf_confluence(fib_levels["fib_161_up"], exp.get("max_vega_strike"), spot, sigma=spx_sigma),
                "confluence_fib127_bear_min_gamma": rbf_confluence(fib_levels["fib_127_dn"], exp["min_gamma_strike"], spot, sigma=spx_sigma),
                "confluence_fib161_bear_max_vomma": rbf_confluence(fib_levels["fib_161_dn"], exp.get("max_vomma_strike"), spot, sigma=spx_sigma),
                "confluence_fib161_bull_max_vomma": rbf_confluence(fib_levels["fib_161_up"], exp.get("max_vomma_strike"), spot, sigma=spx_sigma),
                "confluence_fib127_bear_min_vomma": rbf_confluence(fib_levels["fib_127_dn"], exp.get("min_vomma_strike"), spot, sigma=spx_sigma),
                "confluence_fib127_bull_max_dgex": rbf_confluence(fib_levels["fib_127_up"], exp["max_dgex_strike"], spot, sigma=spx_sigma),
                "confluence_fib127_bear_min_dgex": rbf_confluence(fib_levels["fib_127_dn"], exp["min_dgex_strike"], spot, sigma=spx_sigma),
                "confluence_fib161_bull_max_dgex": rbf_confluence(fib_levels["fib_161_up"], exp["max_dgex_strike"], spot, sigma=spx_sigma),
                "confluence_fib161_bear_min_dgex": rbf_confluence(fib_levels["fib_161_dn"], exp["min_dgex_strike"], spot, sigma=spx_sigma),
                # ── VRP regime ──
                **vrp_features,
                # ── Historical IB D-1 to D-5 ──
                **hist_ib_features,
                # ── Vol-adjusted returns ──
                **ret_features,
                # ── Time encoding ──
                "time_sin": time_sin, "time_cos": time_cos,
                "minutes_to_close_norm": minutes_to_close_norm,
                "dow_sin": dow_sin, "dow_cos": dow_cos,
                # ── IB structure context ──
                "ib_range_percentile": ib_range_percentile_val,
                **gap_features,
                # ── OpEx ──
                **opex_features,
                # ── Greek dynamics ──
                "charm_accel_weighted": charm_accel_weighted,
                "gamma_speed": safe_log(gamma_speed_val),
                # ── Hilbert phase ──
                **hilbert_features,
                # ── Option flow ──
                "delta_filtered_pcr": delta_filtered_pcr_norm,
                "pcr_derivative_5m": pcr_derivative_5m_clipped,
                # ── TLT proxy ──
                **tlt_features,
                # ── D-1 IB confluences ──
                **d1_confluence,
                # ── Interaction features ──
                "speed_x_near_ib_high": gamma_speed_val * near_ib_high,
                "speed_x_near_ib_low": gamma_speed_val * near_ib_low,
                "charm_accel_x_near_ib_high": charm_accel_weighted * near_ib_high,
                "charm_accel_x_near_ib_low": charm_accel_weighted * near_ib_low,
                # ── Wonham Filter ──
                "wonham_trend_prob": wonham_by_time.get(time_key, 0.5),
                # ── Level identity (2) ──
                # nearest_level_id: 0=ib_high,1=ib_low,2=fib_127_up,...,8=none
                # Explicit token for WHICH structural level is currently being touched.
                "nearest_level_id":       float(nearest_level_id),
                "nearest_level_dist_bps": nearest_level_dist_bps,
                # ── Greek × Level interaction scalars (10) ──
                # Pre-computed feature-products so the model doesn't need to
                # discover these conjunctions from scratch.
                "gamma_x_near_fib_up":  gamma_x_near_fib_up,
                "gamma_x_near_fib_dn":  gamma_x_near_fib_dn,
                "gamma_x_near_ib":      gamma_x_near_ib,
                "delta_x_near_fib_up":  delta_x_near_fib_up,
                "delta_x_near_fib_dn":  delta_x_near_fib_dn,
                "delta_x_near_ib_high": delta_x_near_ib_high,
                "delta_x_near_ib_low":  delta_x_near_ib_low,
                "vanna_x_near_fib_up":  vanna_x_near_fib_up,
                "vanna_x_near_fib_dn":  vanna_x_near_fib_dn,
                "vanna_x_near_ib":      vanna_x_near_ib,
                # ── Composite setup flags REMOVED (see comment above) ──
            }
            
            prev_vals = {
                "spot": spot, "net_gamma": exp["net_gamma"], "net_vanna": exp["net_vanna"],
                "net_dgex": exp["net_dgex"], "net_delta": exp.get("net_delta", 0),
                "net_vega": exp.get("net_vega", 0), "net_vomma": exp.get("net_vomma", 0)
            }
            # ── 5-minute temporal downsampling ──
            # Reduces target autocorrelation from r=0.77 (1-min, 179/180 shared bars)
            # to ~r=0.35 (5-min, 175/180 shared bars). Fewer but more independent samples.
            if minutes_since_open % 5 == 0:
                samples.append(sample)
            
        avg_atr = float(np.mean(daily_atrs)) if len(daily_atrs) > 0 else 0.0
        
        longs, shorts, holds = 0, 0, 0
        for s in samples:
            if s["target"] == 1: longs += 1
            elif s["target"] == -1: shorts += 1
            else: holds += 1
        
        return samples, avg_atr, longs, shorts, holds

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[DEBUG {ticker} {date_str}] CRASH: Error procesando 0DTE: {e}")
        return [], 0.0, 0, 0, 0

def collect_training_data(tickers: list, num_days: int = 365, num_workers: int = None, start_date=None, end_date=None) -> pd.DataFrame:
    if num_workers is None:
        num_workers = min(multiprocessing.cpu_count(), 20)
    
    all_symbols = [t for t in tickers if t in ["SPX", "QQQ"]]
    if not all_symbols:
        print("ADVERTENCIA: No se encontraron tickers válidos (SPX, QQQ soportados). Usando SPX y QQQ.")
        all_symbols = ["SPX", "QQQ"]

    available_dates = set()
    
    for ticker in all_symbols:
        underlying_ticker = "SPXW" if ticker == "SPX" else ticker
        search_dir = Path(THETADATA_DIR) / "data_underlying_derived" / underlying_ticker
        if search_dir.exists():
            for f in search_dir.rglob(f"{underlying_ticker}_*.parquet"):
                try:
                    date_str = f.stem.split('_')[1]
                    available_dates.add(datetime.strptime(date_str, "%Y%m%d").date())
                except: pass
                    
    if not available_dates:
        print("No data underlying files found! Check THETADATA_DIR paths.")
        return pd.DataFrame()
        
    sorted_dates = sorted(available_dates)
    trading_days = sorted_dates[-num_days:] if len(sorted_dates) > num_days else sorted_dates
    
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y%m%d").date()
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y%m%d").date()
        trading_days = sorted([d for d in available_dates if start_dt <= d <= end_dt])
    
    task_args = []
    for ticker in all_symbols:
        for target_date in trading_days:
            task_args.append((ticker, target_date))
            
    total_tasks = len(task_args)
    print(f"Found {len(available_dates)} unique dates with data")
    print(f"Processing {len(trading_days)} trading days (from {trading_days[0]} to {trading_days[-1]})")
    print(f"Processing {len(all_symbols)} symbols × {len(trading_days)} days = {total_tasks} tasks")
    print(f"Using {num_workers} parallel workers...\n")
    
    all_samples = []
    completed = 0
    total_longs, total_shorts, total_holds = 0, 0, 0
    total_atr_sum = 0.0
    valid_atr_days = 0
    start_time_all = time.time()
    
    if num_workers == 1:
        for args in task_args:
            completed += 1
            try:
                res = process_ticker_date(args)
                if len(res) == 5:
                    samples, day_atr, longs, shorts, holds = res
                else:
                    samples, day_atr, longs, shorts, holds = res, 0.0, 0, 0, 0
                    
                if samples:
                    # --- Deduplicate Samples (Fix for Bug #5 Clustering) ---
                    seen = set()
                    deduped_samples = []
                    for s in samples:
                        # Key: (level_type, HH:MM rounded down to 5 min intervals)
                        time_str = s['time']
                        try:
                            minutes = int(time_str[3:5])
                            rounded_minutes = (minutes // 5) * 5
                            bucket_time = f"{time_str[:3]}{rounded_minutes:02d}"
                        except:
                            bucket_time = time_str[:4] # fallback
                        
                        # Deduplication using nearest level ID
                        level_type = str(s.get('nearest_level_id', 8))
                            
                        key = (level_type, bucket_time)
                        if key not in seen:
                            seen.add(key)
                            deduped_samples.append(s)
                            
                    all_samples.extend(deduped_samples)
                    
                    # Recalculate longs, shorts, holds based on deduped samples
                    longs, shorts, holds = 0, 0, 0
                    for s_deduped in deduped_samples:
                        if s_deduped["target"] == 1: longs += 1
                        elif s_deduped["target"] == -1: shorts += 1
                        else: holds += 1

                    total_longs += longs
                    total_shorts += shorts
                    total_holds += holds
                    if day_atr > 0:
                        total_atr_sum += day_atr
                        valid_atr_days += 1
                        
                    avg_atr = total_atr_sum / valid_atr_days if valid_atr_days > 0 else 0.0
                    process = psutil.Process()
                    mem_mb = process.memory_info().rss / (1024 * 1024)
                    pct = completed / total_tasks * 100
                    elapsed = time.time() - start_time_all
                    eta_str = f"{elapsed / completed * (total_tasks - completed) / 60:.1f}min" if completed > 1 else "..."
                    bar_len = 25
                    filled = int(bar_len * completed / total_tasks)
                    # ASCII bar to avoid Windows console encoding issues (cp1252)
                    bar = "=" * filled + "." * (bar_len - filled)
                    print(f"\r  [{bar}] {pct:5.1f}% | {completed}/{total_tasks} | "
                          f"{len(all_samples):,} samples | ATR: {avg_atr:.1f} | "
                          f"L:{total_longs} S:{total_shorts} H:{total_holds} | "
                          f"Mem: {mem_mb:.0f}MB | ETA: {eta_str}   ", end="", flush=True)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[{args[0]} {args[1]}] ERROR: {e}")
    else:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(process_ticker_date, args): args for args in task_args}
            for future in as_completed(futures):
                ticker, target_date = futures[future]
                completed += 1
                try:
                    res = future.result()
                    if len(res) == 5:
                        samples, day_atr, longs, shorts, holds = res
                    else:
                        samples, day_atr, longs, shorts, holds = res, 0.0, 0, 0, 0
                        
                    if samples:
                        all_samples.extend(samples)
                        total_longs += longs
                        total_shorts += shorts
                        total_holds += holds
                        if day_atr > 0:
                            total_atr_sum += day_atr
                            valid_atr_days += 1
                            
                        if completed % 10 == 0 or completed == total_tasks:
                            avg_atr = total_atr_sum / valid_atr_days if valid_atr_days > 0 else 0.0
                            process = psutil.Process()
                            mem_mb = process.memory_info().rss / (1024 * 1024)
                            pct = completed / total_tasks * 100
                            elapsed = time.time() - start_time_all
                            eta_str = f"{elapsed / completed * (total_tasks - completed) / 60:.1f}min" if completed > 1 else "..."
                            bar_len = 25
                            filled = int(bar_len * completed / total_tasks)
                            # ASCII bar to avoid Windows console encoding issues (cp1252)
                            bar = "=" * filled + "." * (bar_len - filled)
                            print(f"\r  [{bar}] {pct:5.1f}% | {completed}/{total_tasks} | "
                                  f"{len(all_samples):,} samples | ATR: {avg_atr:.1f} | "
                                  f"L:{total_longs} S:{total_shorts} H:{total_holds} | "
                                  f"Mem: {mem_mb:.0f}MB | ETA: {eta_str}   ", end="", flush=True)
                except Exception as e:
                    print(f"[{ticker} {target_date}] ERROR: {e}")
                
    print()
    df = pd.DataFrame(all_samples)
    print(f"\nTotal samples collected: {len(df)}")
    return df

def main():
    parser = argparse.ArgumentParser(description="Collect training data for PyTorch trading bot using Parquets")
    parser.add_argument("--output", default="training_data_derived.parquet", help="Output Parquet filename")
    parser.add_argument("--days", type=int, default=365, help="Max trading days to process")
    parser.add_argument("--tickers", nargs="+", default=["SPX", "QQQ"], help="Tickers a procesar")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers")
    parser.add_argument("--start", type=str, default=None, help="Start date YYYYMMDD")
    parser.add_argument("--end", type=str, default=None, help="End date YYYYMMDD")
    parser.add_argument("--gui", action="store_true", help="Launch trade annotation GUI (skips data collection)")
    parser.add_argument("--port", type=int, default=8501, help="GUI server port (only with --gui)")
    args = parser.parse_args()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, args.output)

    # ── GUI mode: launch annotator server ──
    if args.gui:
        from tools.trade_annotator.server import launch_gui
        launch_gui(output_path=output_path, port=args.port)
        return

    df = collect_training_data(args.tickers, args.days, args.workers, args.start, args.end)
    
    if df.empty:
        print("No data collected!")
        return
        
    df.to_parquet(output_path, index=False)
    print(f"\nSaved to: {output_path}")
    
    print("\n=== Dataset Summary ===")
    print(f"Total samples: {len(df)}")
    print(f"Tickers: {df['ticker'].unique().tolist()}")
    print(f"Dates: {df['date'].nunique()} unique days")
    print(f"\nTarget distribution:")
    print(df['target'].value_counts().sort_index())
    
if __name__ == "__main__":
    main()