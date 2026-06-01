import pandas as pd
import numpy as np
import sys

def main():
    print("Loading dataset...")
    df = pd.read_parquet(r"c:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy.parquet")
    
    print("\n--- Basic Label Distribution ---")
    for tck in ["QQQ", "SPX", "SPY"]:
        sub = df[df['ticker'] == tck]
        counts = sub['target'].value_counts(normalize=True)
        print(f"\n[{tck}]")
        print(counts)
        
        # What is the average expected profit for a long trade vs a short trade?
        # The 'target' is just 1 or -1. 
        # But we also have 'ret_15m_vol_adj' or we can check the 'price_vs_ib_high' etc.
        # Let's check how many times the model's actual targets would have been hit.
        longs = sub[sub['target'] == 1]
        shorts = sub[sub['target'] == -1]
        
        print(f"Total Longs: {len(longs)}, Total Shorts: {len(shorts)}")

if __name__ == "__main__":
    main()
