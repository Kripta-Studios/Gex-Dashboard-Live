import pandas as pd

def filter_may():
    # Load old parquet
    df = pd.read_parquet(r"c:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy.parquet")
    
    # Convert date to datetime if not already
    df['date_dt'] = pd.to_datetime(df['date'], format='%Y%m%d')
    
    # Filter for May 2026 and labeled trades (target != 0)
    # The user says "solo por los trades marcados, labeled, en mayo de 2026"
    df_may = df[(df['date_dt'] >= '2026-05-01') & (df['date_dt'] <= '2026-05-31') & (df['target'] != 0)].copy()
    
    # Drop temp column
    df_may.drop(columns=['date_dt'], inplace=True)
    
    # Save
    out_path = r"c:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_only_may.parquet"
    df_may.to_parquet(out_path, index=False)
    
    print(f"Old May Trades: {len(df_may)}")
    print(df_may['target'].value_counts())

if __name__ == "__main__":
    filter_may()
