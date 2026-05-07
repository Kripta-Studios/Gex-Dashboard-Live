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
from services.compute_features import (
    extract_feature_vector, calculate_exact_t, 
    calculate_fibonacci_levels, get_nearest_level_identity,
    safe_log, dist_bps, is_near_level, classify_gamma_regime,
    sign_divergence, simple_rsi, rbf_confluence,
    compute_wonham_filter
)
from neural.hybrid_model import FEATURE_COLUMNS

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

TICKERS = ["SPX", "QQQ", "SPY"]
R_RATE, Q_DIV = 0.0325, 0.0150
LEVEL_PROXIMITY_THRESHOLD = 0.0015   # ±0.15% — widened to capture S/R bounces at IB/fib levels
                                     # Was 0.0008 (±4pts SPX) — too tight, missed 0.10-0.15% reactions
                                     # With 0.0015 = ±6pts in SPX@4100, ±0.45pts in QQQ@300
LOOKAHEAD_MINUTES = 180
FIXED_PROFIT_PCT = 0.003             # 0.3% — target for LONG/SHORT (captures typical S/R bounces)
FIXED_STOP_PCT   = 0.003             # 0.3% — stop for both directions → 1:1 R/R
                                     # Previous: 0.6% profit / 0.3% stop → missed 0.3-0.5% moves
BPS_CLIP = 500                        # clamp distances at ±500 bps (±5%)

# Column Optimization for Memory
GREEKS_COLUMNS = ['strike', 'right', 'underlying_price', 'underlying_timestamp', 'implied_vol', 'implied_volatility']
OI_COLUMNS = ['strike', 'right', 'open_interest']
IV_COLUMNS = ['strike', 'implied_vol', 'underlying_timestamp']
OHLC_COLUMNS = ['strike', 'right', 'volume', 'timestamp']

def safe_read_parquet(filepath, columns=None):
    """
    Robust parquet reader that handles missing columns and renames 
    'implied_volatility' to 'implied_vol' if needed.
    """
    if not os.path.exists(filepath):
        return pd.DataFrame()
    try:
        import pyarrow.parquet as pq
        parquet_file = pq.ParquetFile(filepath)
        available_cols = parquet_file.schema.names
        
        if columns is None:
            request_cols = available_cols
        else:
            request_cols = [c for c in columns if c in available_cols]
            
        df = pd.read_parquet(filepath, columns=request_cols)
        
        # Consistent Greek naming
        if 'implied_vol' not in df.columns and 'implied_volatility' in df.columns:
            df['implied_vol'] = df['implied_volatility']
        elif 'implied_volatility' not in df.columns and 'implied_vol' in df.columns:
            df['implied_volatility'] = df['implied_vol']
            
        return df
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return pd.DataFrame()

def proximity_gate(spot: float, levels: list, threshold: float = LEVEL_PROXIMITY_THRESHOLD) -> bool:
    """Return True if spot is within ±threshold% of ANY level in the list."""
    for level in levels:
        if is_near_level(spot, level, threshold):
            return True
    return False

# REDUNDANT FUNCTIONS REMOVED (now in services.compute_features)


# compute_wonham_filter removed — now using unified version from services.compute_features

def load_ohlc_data(ticker: str, date_str: str) -> dict:
    underlying_ticker = "SPXW" if ticker == "SPX" else ticker
    year, month = date_str[:4], date_str[4:6]
    filepath = Path(THETADATA_DIR) / "data_underlying_derived" / underlying_ticker / year / month / f"{underlying_ticker}_{date_str}.parquet"
    if not filepath.exists(): return None
    
    try:
        request_cols = ['timestamp', 'open', 'high', 'low', 'close', 'tick_count', 'volume']
        df = safe_read_parquet(filepath, columns=request_cols)
        if df.empty: return None
        
        df['dt'] = pd.to_datetime(df['timestamp'])
        
        # Downcast for memory
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                df[col] = df[col].astype(np.float32)
        
        df = df[(df['dt'].dt.time >= dt_time(8, 0)) & (df['dt'].dt.time <= dt_time(17, 0))]
        if df.empty: return None
        
        # Fix IB window: Strictly 9:30-10:30 ET (RTH)
        df_rth = df[df['dt'].dt.time >= dt_time(9, 30)]
        if df_rth.empty:
            ib_high = float(df['high'].max())
            ib_low = float(df['low'].min())
        else:
            first_rth = df_rth['dt'].min()
            ib_end = first_rth + pd.Timedelta(minutes=60)
            df_ib = df_rth[df_rth['dt'] < ib_end]
            ib_high = float(df_ib['high'].max() if not df_ib.empty else df_rth['high'].max())
            ib_low = float(df_ib['low'].min() if not df_ib.empty else df_rth['low'].min())
        
        total_volume = float(df['tick_count'].sum() if 'tick_count' in df.columns else df['volume'].sum() if 'volume' in df.columns else 1)
        
        # Select and downcast for memory efficiency
        if 'tick_count' in df.columns:
            df['volume'] = df['tick_count'].astype(np.float32)
        elif 'volume' in df.columns:
            df['volume'] = df['volume'].astype(np.float32)
        else:
            df['volume'] = 1.0
            
        df['close'] = df['close'].astype(np.float32)
        
        series = []
        for _, row in df.iterrows():
            series.append({
                "time": row['dt'].strftime("%H:%M"),
                "price": float(row['close']),
                "volume": float(row['volume'])
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

# calculate_exact_t is imported from services.compute_features

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
        "zero_gamma": zero_gamma_strike,
        "_df": df_clean
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
            # Optimize: Load only close for VIX spot
            df_vix = safe_read_parquet(vix_ohlc_path, columns=['close'])
            if not df_vix.empty:
                vix_spot = float(df_vix['close'].iloc[-1])
        except: pass

    vix_gamma = 0
    weekly_file = get_parquet_file("VIX", date_str, is_0dte=False)
    if weekly_file:
        try:
            # Optimize: Greeks columns
            df_g = safe_read_parquet(weekly_file, columns=GREEKS_COLUMNS)
            if not df_g.empty:
                year, month = date_str[:4], date_str[4:6]
                oi_file = Path(OPTIONS_DIR) / "VIX" / "oi" / year / month / weekly_file.name.replace("greeks.parquet", "oi.parquet")
                if oi_file.exists():
                    df_oi = safe_read_parquet(oi_file, columns=OI_COLUMNS)
                    if not df_oi.empty:
                        df_oi_agg = df_oi.groupby(['strike', 'right'], observed=True).agg({'open_interest': 'max'}).reset_index()
                        df_g['dt'] = pd.to_datetime(df_g['underlying_timestamp'])
                        target_dt = pd.to_datetime(f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} 15:00:00")
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
            # Optimize: Selective columns for historical IB
            df = safe_read_parquet(filepath, columns=['timestamp', 'high', 'low', 'close'])
            if df.empty:
                results.append(None)
                continue
                
            df['dt'] = pd.to_datetime(df['timestamp'])
            # Downcast
            for col in ['high', 'low', 'close']:
                if col in df.columns:
                    df[col] = df[col].astype(np.float32)
            df = df[(df['dt'].dt.time >= dt_time(9, 30)) & (df['dt'].dt.time <= dt_time(16, 0))]
            if df.empty:
                results.append(None)
                continue
            
            # IB window: first 60 minutes of RTH
            rth_start = df['dt'].dt.normalize().iloc[0] + pd.Timedelta(hours=9, minutes=30)
            ib_end = rth_start + pd.Timedelta(minutes=60)
            df_ib = df[(df['dt'] >= rth_start) & (df['dt'] < ib_end)]
            
            ib_high = float(df_ib['high'].max()) if not df_ib.empty else float(df['high'].max())
            ib_low = float(df_ib['low'].min()) if not df_ib.empty else float(df['low'].min())
            close_before_4 = df[df['dt'].dt.time <= dt_time(16, 0)]
            close_price = float(close_before_4['close'].iloc[-1]) if not close_before_4.empty else float(df['close'].iloc[-1])
            results.append({
                "ib_high": ib_high, "ib_low": ib_low,
                "daily_high": float(df['high'].max()),
                "daily_low": float(df['low'].min()),
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
        # Optimize: TLT loading
        df = safe_read_parquet(tlt_path, columns=['timestamp', 'close'])
        if df.empty: return pd.DataFrame()
        df['dt'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('dt')
        df = df[(df['dt'].dt.time >= dt_time(8, 0)) & (df['dt'].dt.time <= dt_time(17, 0))]
        df['close'] = df['close'].ffill().astype(np.float32)
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


def process_ticker_date(args: tuple) -> tuple:
    ticker, target_date = args
    if ticker not in ["SPX", "QQQ", "SPY"]:
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
        
    # Aligned with realtime_feed: Reading IV from Greeks exclusively
    iv_history = deque(maxlen=60)
    df_iv = None # Removed loading logic to align with realtime_feed
    if False: # if iv_file:
        try:
            # Optimize: Load only necessary columns for IV
            df_iv = safe_read_parquet(iv_file, columns=['strike', 'implied_vol', 'underlying_timestamp'])
            if not df_iv.empty:
                df_iv['dt'] = pd.to_datetime(df_iv['underlying_timestamp'])
                # Downcast
                df_iv['strike'] = df_iv['strike'].astype(np.float32)
                df_iv['implied_vol'] = df_iv['implied_vol'].astype(np.float32)
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
        
        if not daily_file:
            # Check if this is a known market gap (before daily exp launch)
            day_of_week = target_date.strftime("%a") # Mon, Tue, Wed, Thu, Fri
            is_market_gap = False
            if ticker == "SPX":
                if day_of_week == "Tue" and target_date < datetime(2022, 4, 18).date(): is_market_gap = True
                if day_of_week == "Thu" and target_date < datetime(2022, 5, 11).date(): is_market_gap = True
            elif ticker == "QQQ":
                if day_of_week in ["Tue", "Thu"] and target_date < datetime(2022, 10, 3).date(): is_market_gap = True
                # QQQ Monday/Wednesday also had gaps in early 2022
                if day_of_week in ["Mon", "Wed"] and target_date < datetime(2022, 5, 23).date(): is_market_gap = True
            elif ticker == "SPY":
                # SPY 0DTE launched ~Feb 2023 for Mon/Wed/Fri, Tue/Thu added later
                if day_of_week in ["Tue", "Thu"] and target_date < datetime(2022, 5, 1).date(): is_market_gap = True
                if day_of_week in ["Mon", "Wed"] and target_date < datetime(2022, 2, 13).date(): is_market_gap = True
            elif ticker == "IWM":
                # IWM 0DTE: Mon/Wed/Fri from ~Oct 2022, Tue/Thu added ~May 2024
                if target_date < datetime(2022, 10, 1).date(): is_market_gap = True
                elif day_of_week in ["Tue", "Thu"] and target_date < datetime(2024, 5, 1).date(): is_market_gap = True

            if is_market_gap:
                print(f"[DEBUG {ticker} {date_str}] SALTADO: No existe expiración 0DTE (lanzamiento oficial posterior).")
            else:
                print(f"[DEBUG {ticker} {date_str}] ABORTADO: Falta daily_file (0DTE).")
            return []

        if not weekly_file:
            print(f"[DEBUG {ticker} {date_str}] ABORTADO: Falta weekly_file.")
            return []
        
        # Optimize: Selective column loading for greeks
        df_daily = safe_read_parquet(daily_file, columns=GREEKS_COLUMNS)
        df_weekly = safe_read_parquet(weekly_file, columns=GREEKS_COLUMNS)
        
        if df_daily.empty or df_weekly.empty:
            print(f"[DEBUG {ticker} {date_str}] ABORTADO: Data de Greeks vacía en daily_file o weekly_file.")
            return []
        
        oi_daily_file = Path(OPTIONS_DIR) / greek_ticker / "oi" / year / month / daily_file.name.replace("greeks.parquet", "oi.parquet")
        oi_weekly_file = Path(OPTIONS_DIR) / greek_ticker / "oi" / year / month / weekly_file.name.replace("greeks.parquet", "oi.parquet")
        
        if not oi_daily_file.exists() or not oi_weekly_file.exists(): 
            print(f"[DEBUG {ticker} {date_str}] ABORTADO: Faltan archivos Open Interest (OI) diarios o semanales.")
            return []

        df_oi_daily = safe_read_parquet(oi_daily_file, columns=OI_COLUMNS)
        df_oi_weekly = safe_read_parquet(oi_weekly_file, columns=OI_COLUMNS)
        
        if df_oi_daily.empty or df_oi_weekly.empty:
            print(f"[DEBUG {ticker} {date_str}] ABORTADO: Data de OI vacía.")
            return []
        
        # Downcast for memory
        for df in [df_daily, df_weekly, df_oi_daily, df_oi_weekly]:
            for col in df.select_dtypes(include=['float64']).columns:
                df[col] = df[col].astype(np.float32)
            if 'strike' in df.columns:
                df['strike'] = df['strike'].astype(np.float32)

        df_oi_daily_agg = df_oi_daily.groupby(['strike', 'right'], observed=True).agg({'open_interest': 'max'}).reset_index()
        df_oi_weekly_agg = df_oi_weekly.groupby(['strike', 'right'], observed=True).agg({'open_interest': 'max'}).reset_index()
        
        df_daily['dt'] = pd.to_datetime(df_daily['underlying_timestamp'])
        df_weekly['dt'] = pd.to_datetime(df_weekly['underlying_timestamp'])
        
        # Optimize: Fill underlying_price once for the entire day before grouping
        # This avoids .copy() and .loc in every iteration of the loop
        price_map = {candle.get("time"): candle.get("price", 0) for candle in series}
        
        def fill_missing_prices(df):
            df['time_key'] = df['dt'].dt.strftime("%H:%M")
            # Only fill if underlying_price is <= 0 or NaN
            mask = (df['underlying_price'] <= 0) | (df['underlying_price'].isna())
            if mask.any():
                # Map time_key to price
                df.loc[mask, 'underlying_price'] = df.loc[mask, 'time_key'].map(price_map).astype(np.float32)
            return df

        df_daily = fill_missing_prices(df_daily)
        df_weekly = fill_missing_prices(df_weekly)

        df_daily = df_daily[(df_daily['dt'].dt.time >= dt_time(8, 0)) & (df_daily['dt'].dt.time <= dt_time(17, 0))]
        
        df_pq_daily_all = pd.merge(df_daily, df_oi_daily_agg, on=['strike', 'right'], how='inner')
        df_pq_weekly_all = pd.merge(df_weekly, df_oi_weekly_agg, on=['strike', 'right'], how='inner')
        
        # Categorical optimization
        df_pq_daily_all['right'] = df_pq_daily_all['right'].astype('category')
        df_pq_weekly_all['right'] = df_pq_weekly_all['right'].astype('category')

        groups_daily = df_pq_daily_all.groupby('dt', observed=True)
        groups_weekly = df_pq_weekly_all.groupby('dt', observed=True)
        
        timestamps = sorted(df_daily['dt'].unique())
        prev_vals = None

        daily_ohlc_file = get_parquet_file(greek_ticker, date_str, is_0dte=True, folder="ohlc", suffix="ohlc")
        df_ohlc_daily = None
        if daily_ohlc_file:
            try:
                # Optimize: Selective OHLC loading
                import pyarrow.parquet as pq
                parquet_file = pq.ParquetFile(daily_ohlc_file)
                available_ohlc_cols = parquet_file.schema.names
                request_ohlc_cols = [c for c in OHLC_COLUMNS if c in available_ohlc_cols]
                
                df_ohlc_daily = pd.read_parquet(daily_ohlc_file, columns=request_ohlc_cols)
                if 'timestamp' in df_ohlc_daily.columns:
                    df_ohlc_daily['dt'] = pd.to_datetime(df_ohlc_daily['timestamp'])
                # Downcast
                df_ohlc_daily['strike'] = df_ohlc_daily['strike'].astype(np.float32)
                df_ohlc_daily['volume'] = df_ohlc_daily['volume'].astype(np.float32)
                df_ohlc_daily['right'] = df_ohlc_daily['right'].astype('category')
            except:
                df_ohlc_daily = None

        historical_ibs = load_historical_ib_levels(greek_ticker, date_str, n_days=10)
        tlt_df = load_tlt_intraday(date_str)

        gap_features = compute_gap_features(series, historical_ibs, ib_high, ib_low)
        opex_features = compute_opex_proximity(date_str)
        ib_range_percentile_val = compute_ib_range_percentile(ib_high - ib_low, historical_ibs)

        atm_iv_open = 0.15
        if True: # Aligned: Extracting from Greeks (df_daily)
            try:
                df_iv_open = df_daily[df_daily['dt'].dt.time >= dt_time(9, 30)].sort_values('dt')
                if not df_iv_open.empty:
                    ts_open = df_iv_open['dt'].iloc[0]
                    spot_open_approx = series[0].get('price', 5000)
                    mask = df_iv_open['dt'] == ts_open
                    if mask.any():
                        closest_idx = (df_iv_open[mask]['strike'] - spot_open_approx).abs().idxmin()
                        iv_col = 'implied_vol' if 'implied_vol' in df_iv_open.columns else 'implied_volatility'
                        atm_iv_open_raw = float(df_iv_open.loc[closest_idx, iv_col])
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
        iv_history = deque(maxlen=32)
        pcr_history = deque(maxlen=32)
        net_gamma_window = deque(maxlen=60)
        net_charm_history = deque(maxlen=32)
        prev_features = None
        
        # Persistence tracking
        current_regime = None
        regime_persistence = 0
        # --- Aligned ATR Calculation (15-day Daily Range) ---
        day_atr = 70.0  # Default for SPX
        try:
            # Load last 15 days of OHLC to get ATR
            hist_ohlc = load_historical_ib_levels(greek_ticker, date_str, n_days=15)
            ranges = [h['daily_high'] - h['daily_low'] for h in hist_ohlc if h is not None]
            if len(ranges) >= 1:
                day_atr = float(np.mean(ranges))
        except Exception as e:
            print(f"[DEBUG {ticker} {date_str}] Error calculating ATR: {e}")
        
        net_gamma_window = deque(maxlen=60)
        session_length = 390.0
        daily_atrs = []
        
        # Initial Balance tracking
        running_ib_high = 0.0
        running_ib_low = 0.0
        
        for ts_np in timestamps:
            ts = pd.to_datetime(ts_np)
            time_key = ts.strftime("%H:%M")
            if time_key not in price_by_time: continue
            series_idx, series_price = price_by_time[time_key]
            
            # --- Aligned IB and ATR Calculation ---
            minutes_since_open = max(0, (ts.hour * 60 + ts.minute) - (9 * 60 + 30))
            
            # Update running IB during the first hour (9:30 - 10:30)
            if 0 <= minutes_since_open <= 60:
                if running_ib_high == 0:
                    running_ib_high = series_price
                    running_ib_low = series_price
                else:
                    running_ib_high = max(running_ib_high, series_price)
                    running_ib_low = min(running_ib_low, series_price)

            # ELIMINATE LOOKAHEAD BIAS:
            # During the first 60 minutes, use the IB formed SO FAR.
            # After 60 minutes, use the FINAL RTH IB (9:30-10:30).
            if minutes_since_open < 60:
                cur_ib_high = running_ib_high
                cur_ib_low = running_ib_low
            else:
                cur_ib_high = ib_high
                cur_ib_low = ib_low
            cur_fib_levels = calculate_fibonacci_levels(cur_ib_high, cur_ib_low)
            
            # --- ATR Alignment ---
            # Instead of rolling minute moves, use the 15-day daily range ATR.
            # We pre-calculated this at the start of the function (see below).
            target_label, time_to_target, time_to_stop, max_move = 0, 0, 0, 0.0
            
            wk_exp = None
            if ts in groups_weekly.groups:
                # Use group directly, no .copy()
                df_pq_wk = groups_weekly.get_group(ts)
                if not df_pq_wk.empty:
                    # Note: underlying_price was already filled above
                    df_pq_wk_with_T = df_pq_wk.assign(T=calculate_exact_t(ts))
                    wk_exp = get_net_exposures_from_parquet(df_pq_wk_with_T)
            
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
            df_pq = groups_daily.get_group(ts)
            if df_pq.empty: continue
            
            # Use assign instead of .loc/copy
            df_pq_with_T = df_pq.assign(T=calculate_exact_t(ts))
            exp = get_net_exposures_from_parquet(df_pq_with_T)
            if not exp: continue
            
            spot = exp["spot_price"]
            
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
            net_gamma_window.append(exp["net_gamma"])
            net_charm_history.append(exp["net_charm"]) # This one is actually updated twice in original, let's stick to once for now or match original if critical
            
            # ── TLT Rate of Change (Raw) ──
            tlt_now = 0.0
            if not tlt_df.empty:
                past_rows = tlt_df[tlt_df['dt'] <= ts]
                if not past_rows.empty:
                    tlt_now = float(past_rows.iloc[-1]['close'])
                    tlt_price_history.append((minutes_since_open, tlt_now))
            
            # ── ATM IV ──
            atm_iv = 0.0
            iv_zscore = 0.0
            iv_pct = 0.5
            if True: # Aligned: Reading from Greeks (df_pq)
                # Reading from df_pq (merged greeks) instead of df_iv
                if not df_pq.empty:
                    closest_idx = (df_pq['strike'] - spot).abs().idxmin()
                    iv_col = 'implied_vol' if 'implied_vol' in df_pq.columns else 'implied_volatility'
                    atm_iv_raw = float(df_pq.loc[closest_idx, iv_col])
                    atm_iv = atm_iv_raw / 100.0 if atm_iv_raw > 1.0 else atm_iv_raw
            if atm_iv > 0:
                iv_history.append(atm_iv)
            else:
                atm_iv = float(iv_history[-1]) if len(iv_history) > 0 else 0.0
            
            # --- Persistence Tracking ---
            regime = classify_gamma_regime(exp["net_gamma"])
            if regime == current_regime:
                regime_persistence += 1
            else:
                current_regime = regime
                regime_persistence = 1
            # Normalize persistence (cap at 12 bars = 60 mins)
            persistence_val = float(np.clip(regime_persistence / 12.0, 0.0, 1.0))
            
            # ── PCR Proxy (Raw) ──
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
                    pcr_history.append(delta_filtered_pcr_raw)
                
            # ── Proximity-Gated Labeling ──
            key_levels = [
                exp["max_gamma_strike"], exp["min_gamma_strike"],
                exp["min_vanna_strike"], exp["zero_gamma"],
                exp["max_dgex_strike"], exp["min_dgex_strike"],
                exp.get("max_vega_strike", 0), exp.get("min_vega_strike", 0),
                exp.get("max_vomma_strike", 0), exp.get("min_vomma_strike", 0),
                cur_ib_high, cur_ib_low,
                cur_fib_levels["fib_127_up"], cur_fib_levels["fib_161_up"], cur_fib_levels["fib_200_up"],
                cur_fib_levels["fib_127_dn"], cur_fib_levels["fib_161_dn"], cur_fib_levels["fib_200_dn"],
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
            
            # Pass vix_gamma into exp_0dte or as extra arg
            exp["vix_gamma"] = vix_data.get("vix_gamma", 0.0)
            exp["signal_persistence_5m"] = persistence_val

            features_dict = extract_feature_vector(
                exp_0dte=exp,
                exp_weekly=wk_exp,
                spot=spot,
                atm_iv=atm_iv,
                vix_spot=vix_spot,
                tlt_spot=tlt_now,
                ib_high=cur_ib_high,
                ib_low=cur_ib_low,
                historical_ibs=historical_ibs,
                price_history=price_history,
                tlt_price_history=tlt_price_history,
                iv_history=iv_history,
                pcr_history=pcr_history,
                net_gamma_window=net_gamma_window,
                net_charm_history=net_charm_history,
                prev_features=prev_features,
                minutes_since_open=minutes_since_open,
                day_atr=day_atr,
                now_et=ts,
                FEATURE_COLUMNS=None,  # Return dictionary for training
                wonham_prob=wonham_by_time.get(time_key, 0.5)
            )

            # --- Target Labeling & Sampling ---
            sample = {
                "ticker": ticker, "date": date_str, "time": time_key, "timestamp": ts,
                "spot_price": spot, "target": target_label, "time_to_target": time_to_target,
                "time_to_stop": time_to_stop, "max_move": max_move,
                **features_dict
            }
            
            # Additional training-specific logic (not in feature vector but saved)
            # Add gap and opex features if they are not already in features_dict (they should be)
            # But the training script used to merge them here.

            prev_features = features_dict
            prev_features["spot"] = spot  # Ensure spot is available for temporal deltas
            
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
        num_workers = min(multiprocessing.cpu_count(), 30)
    
    all_symbols = [t for t in tickers if t in ["SPX", "QQQ", "SPY"]]
    if not all_symbols:
        print("ADVERTENCIA: No se encontraron tickers válidos (SPX, QQQ, SPY soportados). Usando SPX y QQQ.")
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
    start_dt = datetime.strptime(start_date, "%Y%m%d").date() if start_date else None
    end_dt = datetime.strptime(end_date, "%Y%m%d").date() if end_date else None

    if start_dt and end_dt and start_dt > end_dt:
        raise ValueError(f"Invalid date range: start_date {start_date} > end_date {end_date}")

    if start_dt is not None or end_dt is not None:
        trading_days = [
            d for d in sorted_dates
            if (start_dt is None or d >= start_dt) and (end_dt is None or d <= end_dt)
        ]
    else:
        trading_days = sorted_dates[-num_days:] if len(sorted_dates) > num_days else sorted_dates

    if not trading_days:
        print("No trading days matched the requested date range.")
        return pd.DataFrame()
    
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
    
    def _dedupe_samples(samples: list) -> list:
        seen = set()
        deduped_samples = []
        for sample in samples:
            time_str = sample.get("time", "")
            try:
                minutes = int(str(time_str)[3:5])
                rounded_minutes = (minutes // 5) * 5
                bucket_time = f"{str(time_str)[:3]}{rounded_minutes:02d}"
            except Exception:
                bucket_time = str(time_str)[:4]

            level_type = str(sample.get("nearest_level_id", 8))
            key = (level_type, bucket_time)
            if key in seen:
                continue
            seen.add(key)
            deduped_samples.append(sample)
        return deduped_samples

    def _count_targets(samples: list) -> tuple[int, int, int]:
        longs = shorts = holds = 0
        for sample in samples:
            if sample["target"] == 1:
                longs += 1
            elif sample["target"] == -1:
                shorts += 1
            else:
                holds += 1
        return longs, shorts, holds

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
                    deduped_samples = _dedupe_samples(samples)
                    all_samples.extend(deduped_samples)
                    longs, shorts, holds = _count_targets(deduped_samples)

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
                        deduped_samples = _dedupe_samples(samples)
                        all_samples.extend(deduped_samples)
                        longs, shorts, holds = _count_targets(deduped_samples)
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
