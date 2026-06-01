import pandas as pd
import numpy as np
import sys
from itertools import product
from concurrent.futures import ProcessPoolExecutor

# We will simulate the same logic as evaluate_predictions
def _time_to_minutes(t) -> int:
    try:
        text = str(t)
        hh, mm = text.split(":")[:2]
        return int(hh) * 60 + int(mm)
    except:
        return 570

def simulate_day(day_df_tuple):
    # day_df_tuple is (date, ticker, df)
    date_str, ticker, df = day_df_tuple
    df = df.reset_index(drop=True)
    
    # We will track the MFE (Max Favorable Excursion) and MAE (Max Adverse Excursion) 
    # for each entry signal.
    # To save time, we will only take rows where target == 1 or target == -1 
    # (assuming perfect predictions, to see what the natural market mechanics allow).
    
    results = []
    
    for row_pos, row in df.iterrows():
        target_val = row['target']
        if target_val == 0:
            continue
            
        direction = "LONG" if target_val == 1 else "SHORT"
        entry_price = float(row.get("spot_price", 0.0))
        if entry_price <= 0:
            continue
            
        peak_price = entry_price
        trough_price = entry_price
        
        future_rows = df.iloc[row_pos + 1: row_pos + 181] # Up to 180 mins
        for _, future_row in future_rows.iterrows():
            price = float(future_row.get("spot_price", entry_price))
            if price <= 0: continue
            
            if price > peak_price: peak_price = price
            if price < trough_price: trough_price = price
                
        # Calculate excursions as % of entry price
        if direction == "LONG":
            mfe = (peak_price - entry_price) / entry_price
            mae = (entry_price - trough_price) / entry_price
        else:
            mfe = (entry_price - trough_price) / entry_price
            mae = (peak_price - entry_price) / entry_price
            
        results.append({
            'ticker': ticker,
            'direction': direction,
            'mfe': mfe,
            'mae': mae
        })
        
    return results

def main():
    path = r"c:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy.parquet"
    print("Loading data...")
    df = pd.read_parquet(path)
    # Take a 20% sample of days to speed up
    unique_dates = df['date'].unique()
    np.random.seed(42)
    sample_dates = np.random.choice(unique_dates, size=int(len(unique_dates)*0.2), replace=False)
    
    df_sample = df[df['date'].isin(sample_dates)].copy()
    
    if 'minutes' not in df_sample.columns:
        df_sample['minutes'] = df_sample['time'].apply(_time_to_minutes)
        
    df_sample = df_sample.sort_values(["date", "ticker", "minutes"])
    
    grouped = list(df_sample.groupby(["date", "ticker"]))
    print(f"Processing {len(grouped)} day-ticker groups...")
    
    all_res = []
    with ProcessPoolExecutor(max_workers=8) as exc:
        for res in exc.map(simulate_day, [(g[0][0], g[0][1], g[1]) for g in grouped]):
            all_res.extend(res)
            
    res_df = pd.DataFrame(all_res)
    
    # Now simulate different TP/SL pairs
    tp_grid = [0.005, 0.006, 0.008, 0.010, 0.012]
    sl_grid = [0.002, 0.0025, 0.003, 0.0035, 0.004]
    
    print("\n=== OPTIMIZATION RESULTS (Profit Factor based on perfect signals) ===")
    
    for ticker in ["QQQ", "SPX"]:
        print(f"\n--- {ticker} ---")
        t_df = res_df[res_df['ticker'] == ticker]
        if len(t_df) == 0: continue
        
        best_pf = 0
        best_pair = None
        
        for tp in tp_grid:
            for sl in sl_grid:
                # Win: MFE >= tp AND MAE < sl (Assuming it hits TP before SL... 
                # This is an approximation since we don't know which hit first in this fast script,
                # but MFE >= tp and MAE < sl is a DEFINITE clean win.
                # If both MFE>=tp and MAE>=sl, we assume it's a 50/50 chance or a stop out. Let's be pessimistic:
                
                # Clean Win: hit TP, never hit SL
                clean_wins = len(t_df[(t_df['mfe'] >= tp) & (t_df['mae'] < sl)])
                # Clean Loss: hit SL, never hit TP
                clean_losses = len(t_df[(t_df['mfe'] < tp) & (t_df['mae'] >= sl)])
                # Messy: hit both. Assume 70% of the time it hits SL first because SL is usually smaller than TP.
                messy = len(t_df[(t_df['mfe'] >= tp) & (t_df['mae'] >= sl)])
                
                wins = clean_wins + int(messy * 0.3)
                losses = clean_losses + int(messy * 0.7)
                
                # Neither: timed out
                neither = len(t_df[(t_df['mfe'] < tp) & (t_df['mae'] < sl)])
                
                pf = (wins * tp) / max((losses * sl), 0.0001)
                
                if pf > best_pf:
                    best_pf = pf
                    best_pair = (tp, sl)
                    
                print(f"TP: {tp:.3f} | SL: {sl:.4f} => PF: {pf:.2f} (W:{wins} L:{losses} T:{neither})")
                
        print(f"BEST -> TP: {best_pair[0]}, SL: {best_pair[1]} with PF={best_pf:.2f}")

if __name__ == "__main__":
    main()
