import os
import sys
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to sys.path to import local modules
SCRIPT_DIR = pd.Series(os.path.abspath(__file__)).iloc[0] # Using pd series for cleaner path handling if needed, but os.path is fine
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from training_data.stats import calc_dp_cdf_pdf, calc_gamma_ex

# Configuration - aligned with collect_training_data_spx_qqq.py
THETADATA_DIR = r"D:\ThetaData"
OPTIONS_DIR = os.path.join(THETADATA_DIR, "data_options")
R_RATE, Q_DIV = 0.0325, 0.0150

def load_data(date_str, ticker="SPXW"):
    """
    Load 0DTE greeks and OI for a specific date.
    date_str format: YYYYMMDD
    """
    year = date_str[:4]
    month = date_str[4:6]
    
    # Greeks file: D:\ThetaData\data_options\SPXW\greeks\YYYY\MM\SPXW_YYYYMMDD_YYYYMMDD_greeks.parquet
    greeks_path = Path(OPTIONS_DIR) / ticker / "greeks" / year / month / f"{ticker}_{date_str}_{date_str}_greeks.parquet"
    # OI file: D:\ThetaData\data_options\SPXW\oi\YYYY\MM\SPXW_YYYYMMDD_YYYYMMDD_oi.parquet
    oi_path = Path(OPTIONS_DIR) / ticker / "oi" / year / month / f"{ticker}_{date_str}_{date_str}_oi.parquet"
    
    if not greeks_path.exists():
        print(f"Error: Greeks file not found: {greeks_path}")
        return None, None
    if not oi_path.exists():
        print(f"Error: OI file not found: {oi_path}")
        return None, None
        
    print(f"Loading greeks from {greeks_path.name}...")
    df_g = pd.read_parquet(greeks_path)
    
    # Consistent Greek naming
    if 'implied_vol' not in df_g.columns and 'implied_volatility' in df_g.columns:
        df_g['implied_vol'] = df_g['implied_volatility']
    elif 'implied_volatility' not in df_g.columns and 'implied_vol' in df_g.columns:
        df_g['implied_volatility'] = df_g['implied_vol']
        
    print(f"Loading OI from {oi_path.name}...")
    df_oi = pd.read_parquet(oi_path)
    
    return df_g, df_oi

def get_snapshot(df_g, df_oi, target_time_est):
    """
    Filter data for the closest minute to target_time_est (HHMM).
    """
    # Convert underlying_timestamp to datetime
    df_g['dt'] = pd.to_datetime(df_g['underlying_timestamp'])
    
    # target_time_est is HHMM string
    date_part = df_g['dt'].iloc[0].strftime("%Y-%m-%d")
    target_dt = pd.to_datetime(f"{date_part} {target_time_est[:2]}:{target_time_est[2:4]}:00")
    
    # Find nearest timestamp
    available_ts = df_g['dt'].unique()
    if len(available_ts) == 0:
        return None
        
    nearest_ts = available_ts[np.abs(available_ts - target_dt.to_datetime64()).argmin()]
    print(f"Target time: {target_dt}, Nearest available: {nearest_ts}")
    
    df_snap = df_g[df_g['dt'] == nearest_ts].copy()
    
    # Merge with OI
    # OI file might have multiple entries per strike/right if it was updated during the day
    # Take the max OI or the most recent? collect_training_data uses max.
    df_oi_agg = df_oi.groupby(['strike', 'right']).agg({'open_interest': 'max'}).reset_index()
    
    df_merged = pd.merge(df_snap, df_oi_agg, on=['strike', 'right'], how='inner')
    
    if df_merged.empty:
        print("Warning: Merged dataframe is empty. Check strike/right alignment.")
        return None
        
    return df_merged

def calculate_net_gamma(df):
    """
    Calculate dollar gamma exposure per strike.
    """
    S = df['underlying_price'].values.astype(np.float64)
    K = df['strike'].values.astype(np.float64)
    vol = np.where(df['implied_volatility'].values <= 0, 0.0001, df['implied_volatility'].values).astype(np.float64)
    oi = df['open_interest'].values.astype(np.float64)
    
    # T is time to expiration in years. For 0DTE, we compute it from the timestamp.
    # In collect_training_data, they use calculate_exact_t
    # I'll implement a simple version or import it.
    ts = pd.to_datetime(df['underlying_timestamp'].iloc[0])
    # Expiration for 0DTE is the market close of that day (16:00 EST)
    expiration = ts.replace(hour=16, minute=0, second=0, microsecond=0)
    time_diff = expiration - ts
    T = max(time_diff.total_seconds(), 60) / (365 * 24 * 3600)
    
    dp, cdf_dp, pdf_dp = calc_dp_cdf_pdf(S, K, vol, T, R_RATE, Q_DIV)
    g_vals = calc_gamma_ex(S, vol, T, Q_DIV, oi, pdf_dp)
    
    is_put = (df['right'].str.upper() == 'PUT').values
    df['net_gamma'] = np.where(is_put, -g_vals, g_vals)
    
    return df

def plot_gamma(df, date_str, time_str):
    """
    Create the histogram of strikes vs net gamma.
    """
    spot = df['underlying_price'].iloc[0]
    gamma_profile = df.groupby('strike')['net_gamma'].sum().sort_index()
    
    plt.figure(figsize=(15, 8))
    
    # Color bars based on sign
    colors = ['green' if x >= 0 else 'red' for x in gamma_profile.values]
    plt.bar(gamma_profile.index, gamma_profile.values, color=colors, width=1.0, alpha=0.7)
    
    # Mark spot price
    plt.axvline(x=spot, color='blue', linestyle='--', label=f'Spot: {spot:.2f}')
    
    # Visual improvements
    plt.title(f"SPX 0DTE Gamma Exposure Snapshot - {date_str} {time_str} EST", fontsize=16)
    plt.xlabel("Strike", fontsize=14)
    plt.ylabel("Net Gamma Exposure ($)", fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    # Focus on strikes near spot
    plt.xlim(spot * 0.98, spot * 1.02)
    
    output_filename = f"gamma_snapshot_{date_str}_{time_str}.png"
    plt.savefig(output_filename, dpi=150)
    print(f"Plot saved to: {output_filename}")
    plt.close()

def main():
    parser = argparse.ArgumentParser(description="Visualize SPX 0DTE Gamma Exposure")
    parser.add_argument("--date", type=str, required=True, help="Date in YYYYMMDD format")
    parser.add_argument("--time", type=str, required=True, help="Time in HHMM format (EST)")
    args = parser.parse_args()
    
    df_g, df_oi = load_data(args.date)
    if df_g is None:
        return
        
    df_snap = get_snapshot(df_g, df_oi, args.time)
    if df_snap is None:
        return
        
    df_gamma = calculate_net_gamma(df_snap)
    plot_gamma(df_gamma, args.date, args.time)

if __name__ == "__main__":
    main()
