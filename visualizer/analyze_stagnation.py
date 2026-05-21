import pandas as pd
import numpy as np
import os
from pathlib import Path

def analyze_stagnation():
    print("--- 2024 Stagnation Analysis ---")
    
    # 1. Load Data
    data_path = Path("training_data/training_data_spx_qqq_spy.parquet")
    gbt_path = Path("backtest_results/gbt_only_20260520_170625.csv")
    rl_path = Path("backtest_results/gbt_rl_20260520_170625.csv")
    
    print(f"Loading market data from {data_path}...")
    df_market = pd.read_parquet(data_path)
    df_market['date'] = pd.to_datetime(df_market['date'])
    df_market['year_month'] = df_market['date'].dt.to_period('M')
    df_market['year'] = df_market['date'].dt.year
    
    # Calculate daily volatility proxy (High - Low) / Open if available, or just ATR
    if 'atr' in df_market.columns:
        vol_metric = df_market.groupby('year_month')['atr'].mean()
        print("\nMonthly Average ATR:")
        print(vol_metric.tail(30))
    elif 'vix' in df_market.columns:
        vol_metric = df_market.groupby('year_month')['vix'].mean()
        print("\nMonthly Average VIX:")
        print(vol_metric.tail(30))
    else:
        # Try to infer volatility from price changes if OHLC is present
        # Assuming we have open/high/low/close or similar
        print("\nAvailable market data columns:", df_market.columns.tolist())
        
        # Calculate daily range if possible, or just look at target_long/short distribution
        if 'target_long' in df_market.columns:
             print("\nAverage target_long (volatility proxy) by year:")
             print(df_market.groupby('year')['target_long'].mean())
             print(df_market.groupby('year')['target_short'].mean())
             
             # Monthly breakdown for 2023 vs 2024
             df_market['period'] = np.where(df_market['year'] >= 2024, '2024+', 'Pre-2024')
             print("\nPre-2024 vs 2024+ Volatility:")
             print(df_market.groupby('period')[['target_long', 'target_short']].mean())

    print("\nLoading GBT-Only Trades...")
    df_gbt = pd.read_csv(gbt_path)
    df_gbt['date'] = pd.to_datetime(df_gbt['date'].astype(str), format='%Y%m%d')
    df_gbt['year'] = df_gbt['date'].dt.year
    df_gbt['period'] = np.where(df_gbt['year'] >= 2024, '2024+', 'Pre-2024')
    df_gbt['is_win'] = df_gbt['pnl_dollars'] > 0
    
    print("\nGBT-Only Performance (Pre-2024 vs 2024+):")
    gbt_stats = df_gbt.groupby('period').agg(
        trades=('pnl_dollars', 'count'),
        win_rate=('is_win', 'mean'),
        total_pnl=('pnl_dollars', 'sum'),
        avg_hold=('hold_minutes', 'mean')
    )
    # Add PF
    for period in ['Pre-2024', '2024+']:
        wins = df_gbt[(df_gbt['period'] == period) & (df_gbt['pnl_dollars'] > 0)]['pnl_dollars'].sum()
        losses = abs(df_gbt[(df_gbt['period'] == period) & (df_gbt['pnl_dollars'] <= 0)]['pnl_dollars'].sum())
        pf = wins / losses if losses != 0 else np.nan
        gbt_stats.loc[period, 'PF'] = pf
    print(gbt_stats)
    
    print("\nGBT-Only Directional Breakdown:")
    print(df_gbt.groupby(['period', 'direction']).agg(
        trades=('pnl_dollars', 'count'),
        win_rate=('is_win', 'mean'),
        total_pnl=('pnl_dollars', 'sum')
    ))

    print("\nLoading RL Trades...")
    df_rl = pd.read_csv(rl_path)
    df_rl['date'] = pd.to_datetime(df_rl['date'].astype(str), format='%Y%m%d')
    df_rl['year'] = df_rl['date'].dt.year
    df_rl['period'] = np.where(df_rl['year'] >= 2024, '2024+', 'Pre-2024')
    df_rl['is_win'] = df_rl['pnl_dollars'] > 0
    
    print("\nRL Performance (Pre-2024 vs 2024+):")
    rl_stats = df_rl.groupby('period').agg(
        trades=('pnl_dollars', 'count'),
        win_rate=('is_win', 'mean'),
        total_pnl=('pnl_dollars', 'sum'),
        avg_hold=('hold_minutes', 'mean')
    )
    for period in ['Pre-2024', '2024+']:
        wins = df_rl[(df_rl['period'] == period) & (df_rl['pnl_dollars'] > 0)]['pnl_dollars'].sum()
        losses = abs(df_rl[(df_rl['period'] == period) & (df_rl['pnl_dollars'] <= 0)]['pnl_dollars'].sum())
        pf = wins / losses if losses != 0 else np.nan
        rl_stats.loc[period, 'PF'] = pf
    print(rl_stats)
    
    print("\nRL Directional Breakdown:")
    print(df_rl.groupby(['period', 'direction']).agg(
        trades=('pnl_dollars', 'count'),
        win_rate=('is_win', 'mean'),
        total_pnl=('pnl_dollars', 'sum')
    ))

    if 'exit_reason' in df_rl.columns:
        print("\nRL Exit Reasons (Pre-2024 vs 2024+):")
        print(df_rl.groupby(['period', 'exit_reason'])['pnl_dollars'].count().unstack().fillna(0))

if __name__ == '__main__':
    analyze_stagnation()
