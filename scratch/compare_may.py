import pandas as pd

def compare():
    old_path = r"c:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_only_may.parquet"
    new_path = r"c:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\new_training_data_spx_qqq_spy_only_may.parquet"
    
    df_old = pd.read_parquet(old_path)
    df_new = pd.read_parquet(new_path)
    
    print("=== COMPARISON ===")
    print(f"OLD May Trades: {len(df_old)}")
    print(f"NEW May TOTAL Samples: {len(df_new)}")
    
    df_new_trades = df_new[df_new['target'] != 0]
    print(f"NEW May Trades: {len(df_new_trades)}")
    
    print("\nOLD Target Distribution:")
    print(df_old['target'].value_counts())
    
    print("\nNEW Target Distribution:")
    print(df_new['target'].value_counts())
    
    # Calculate some stats for the trades
    print("\n--- OLD Trades Stats ---")
    if 'max_move' in df_old.columns:
        print(f"Mean Max Move %: {df_old['max_move'].mean() * 100:.3f}%")
    if 'time_to_target' in df_old.columns:
        print(f"Mean Time to Target: {df_old['time_to_target'].mean():.1f} min")
        
    print("\n--- NEW Trades Stats ---")
    if 'max_move' in df_new_trades.columns:
        print(f"Mean Max Move %: {df_new_trades['max_move'].mean() * 100:.3f}%")
    if 'time_to_target' in df_new_trades.columns:
        print(f"Mean Time to Target: {df_new_trades['time_to_target'].mean():.1f} min")

if __name__ == "__main__":
    compare()
