import pandas as pd
import numpy as np
from training_data.stats import calc_dp_cdf_pdf, calc_gamma_ex, calc_vanna_ex, calc_charm_ex, calc_vega_ex, calc_vomma_ex, calc_zomma_ex, calc_delta_adjusted_gex

R_RATE, Q_DIV = 0.0325, 0.0150

def calculate_exact_t(current_dt):
    target_close = current_dt.replace(hour=16, minute=0, second=0, microsecond=0)
    seconds_left = (target_close - current_dt).total_seconds()
    return max(seconds_left, 60) / (3600 * 24 * 365.25)

def main():
    print("Loading parquets...")
    greeks_file = r"D:\ThetaData\data_options\SPXW\greeks\2026\02\SPXW_20260218_20260218_greeks.parquet"
    oi_file = r"D:\ThetaData\data_options\SPXW\oi\2026\02\SPXW_20260218_20260218_oi.parquet"
    
    df_g = pd.read_parquet(greeks_file)
    df_oi = pd.read_parquet(oi_file)
    
    df_g['dt'] = pd.to_datetime(df_g['underlying_timestamp'])
    target_dt = pd.to_datetime("2026-02-18 13:02:00")
    nearest_ts = df_g['dt'].unique()[np.abs(df_g['dt'].unique() - target_dt.to_datetime64()).argmin()]
    nearest_ts_pd = pd.to_datetime(nearest_ts)
    print(f"Nearest timestamp: {nearest_ts_pd}")
    
    df_min = df_g[df_g['dt'] == nearest_ts].copy()
    
    df_oi_agg = df_oi.groupby(['strike', 'right']).agg({'open_interest': 'max'}).reset_index()
    
    df_pq = pd.merge(df_min, df_oi_agg, on=['strike', 'right'], how='inner')
    print(f"Merged shape: {df_pq.shape}")
    
    S = df_pq['underlying_price'].values.astype(np.float64)
    K = df_pq['strike'].values.astype(np.float64)
    vol = np.where(df_pq['implied_vol'].values <= 0, 0.0001, df_pq['implied_vol'].values).astype(np.float64)
    oi = df_pq['open_interest'].values.astype(np.float64)
    T = np.full(len(K), calculate_exact_t(nearest_ts_pd), dtype=np.float64)
    
    is_put = (df_pq['right'].str.upper() == 'PUT').values
    
    print("Calculating DP CDF PDF...")
    dp, cdf_dp, pdf_dp = calc_dp_cdf_pdf(S, K, vol, T, R_RATE, Q_DIV)
    
    print("Calculating Exposures...")
    g_vals = calc_gamma_ex(S, vol, T, Q_DIV, oi, pdf_dp)
    v_vals = calc_vanna_ex(S, vol, T, Q_DIV, oi, dp, pdf_dp)
    
    df_pq['pq_net_gex'] = np.where(is_put, -g_vals, g_vals)
    df_pq['pq_net_vanna'] = v_vals # Vanna es misma fórmula para calls y puts, sin multiplicar por -1
    
    gex_by_strike = df_pq.groupby('strike')['pq_net_gex'].sum()
    print("Gamma max strike:", gex_by_strike.idxmax())
    print("Gamma max val:", gex_by_strike.max())
    print("Net Gamma:", df_pq['pq_net_gex'].sum())

if __name__ == '__main__':
    main()
