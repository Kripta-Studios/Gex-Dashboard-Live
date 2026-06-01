import os
import pandas as pd
import numpy as np
import glob

def process_file(file_path):
    try:
        df = pd.read_parquet(file_path)
        if 'close' not in df.columns:
            return []
        
        ticker = "QQQ" if "QQQ" in file_path else "SPX"
        prices = df['close'].values
        n = len(prices)
        
        results = []
        
        for i in range(n - 10):
            end_idx = min(n, i + 181)
            future_prices = prices[i+1:end_idx]
            max_p = np.max(future_prices)
            min_p = np.min(future_prices)
            p = prices[i]
            
            mfe_long = (max_p - p) / p
            mae_long = (p - min_p) / p
            mfe_short = (p - min_p) / p
            mae_short = (max_p - p) / p
            
            results.append((ticker, mfe_long, mae_long, mfe_short, mae_short))
            
        return results
    except Exception as e:
        print("Error:", e)
        return []

def main():
    folder = r"c:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\data_training_input"
    files = glob.glob(os.path.join(folder, "*.parquet"))
    # Take a sample of 20 days of QQQ and 20 days of SPX
    qqq_files = [f for f in files if "QQQ" in f][:20]
    spx_files = [f for f in files if "SPXW" in f][:20]
    
    files_to_process = qqq_files + spx_files
    print(f"Processing {len(files_to_process)} days...")
    
    all_res = []
    for f in files_to_process:
        all_res.extend(process_file(f))
            
    df = pd.DataFrame(all_res, columns=["ticker", "mfe_long", "mae_long", "mfe_short", "mae_short"])
    
    tp_grid = [0.005, 0.006, 0.008, 0.010, 0.012]
    sl_grid = [0.002, 0.0025, 0.003, 0.0035, 0.004]
    
    print("\n" + "="*50)
    print("NATURAL MARKET EXCURSIONS (MFE vs MAE)")
    print("Assumes random entry to find market bias.")
    print("="*50)
    
    for ticker in ["QQQ", "SPX"]:
        print(f"\n=== {ticker} ===")
        t_df = df[df["ticker"] == ticker]
        
        best_pf = 0
        best_tp, best_sl = 0, 0
        
        for tp in tp_grid:
            for sl in sl_grid:
                # Long
                clean_win_l = len(t_df[(t_df['mfe_long'] >= tp) & (t_df['mae_long'] < sl)])
                clean_loss_l = len(t_df[(t_df['mfe_long'] < tp) & (t_df['mae_long'] >= sl)])
                messy_l = len(t_df[(t_df['mfe_long'] >= tp) & (t_df['mae_long'] >= sl)])
                
                # Assume 75% of messy hits SL first
                wins_l = clean_win_l + int(messy_l * 0.25)
                losses_l = clean_loss_l + int(messy_l * 0.75)
                
                # Short
                clean_win_s = len(t_df[(t_df['mfe_short'] >= tp) & (t_df['mae_short'] < sl)])
                clean_loss_s = len(t_df[(t_df['mfe_short'] < tp) & (t_df['mae_short'] >= sl)])
                messy_s = len(t_df[(t_df['mfe_short'] >= tp) & (t_df['mae_short'] >= sl)])
                
                wins_s = clean_win_s + int(messy_s * 0.25)
                losses_s = clean_loss_s + int(messy_s * 0.75)
                
                wins = wins_l + wins_s
                losses = losses_l + losses_s
                
                pf = (wins * tp) / max((losses * sl), 0.0001)
                win_rate = wins / max((wins + losses), 1)
                
                print(f"TP: {tp*100:.1f}% | SL: {sl*100:.2f}% -> PF: {pf:.2f} (WR: {win_rate*100:.1f}%) | Trades: {wins+losses}")
                if pf > best_pf:
                    best_pf = pf
                    best_tp = tp
                    best_sl = sl
        print(f"-> BEST {ticker} NATURAL RATIO: TP={best_tp*100:.1f}%, SL={best_sl*100:.2f}% (PF={best_pf:.2f})")

if __name__ == '__main__':
    main()
