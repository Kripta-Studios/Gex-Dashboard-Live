import pandas as pd
import json
import os
import numpy as np

def load_data():
    print("Loading data...")
    df = pd.read_parquet('../../training_data/training_data_spx_qqq_spy.parquet')
    df = df[(df['ticker'] == 'SPX') & (df['time'] == '09:30')].copy()
    print(f"Loaded {len(df)} SPX days at 09:30.")
    return df

def map_features(df):
    """Map continuous features to binary High/Low, Pos/Neg"""
    print("Mapping features...")
    
    # IV: we'll use vix_spot > 18 as High.
    # Optionally we could use atm_iv or something else, but vix_spot is standard.
    # Excel specifies "High" or "Low"
    df['f_IV'] = np.where(df['vix_spot'] > 18.0, 'High', 'Low')
    
    # Greeks are Pos or Neg
    df['f_Gamma'] = np.where(df['net_gamma'] > 0, 'Pos', 'Neg')
    df['f_Zomma'] = np.where(df['net_zomma'] > 0, 'Pos', 'Neg')
    df['f_Delta'] = np.where(df['net_delta'] > 0, 'Pos', 'Neg')
    
    # Vex is Delta-Adjusted Gamma Exposure (DGEX)
    df['f_Vex'] = np.where(df['net_dgex'] > 0, 'Pos', 'Neg')
    
    df['f_Vega'] = np.where(df['net_vega'] > 0, 'Pos', 'Neg')
    df['f_Vomma'] = np.where(df['net_vomma'] > 0, 'Pos', 'Neg')
    df['f_Speed'] = np.where(df['gamma_speed'] > 0, 'Pos', 'Neg')
    
    return df

def verify_regimes():
    with open('../../regimes.json', 'r', encoding='utf-8') as f:
        regimes_data = json.load(f)
        
    df = load_data()
    df = map_features(df)
    
    # We will build a report
    lines = []
    lines.append("# Market Regimes Verification Report")
    lines.append(f"Total Trading Days Analyzed (SPX at 09:30): {len(df)}\n")
    
    for idx, regime in enumerate(regimes_data):
        iv_val = regime.get('Unnamed: 0', '').strip()
        g_val = regime.get('Unnamed: 1', '').strip()
        z_val = regime.get('Unnamed: 2', '').strip()
        d_val = regime.get('Unnamed: 3', '').strip()
        vex_val = regime.get('Unnamed: 4', '').strip()
        vega_val = regime.get('Unnamed: 5', '').strip()
        vomma_val = regime.get('Unnamed: 6', '').strip()
        s_val = regime.get('Unnamed: 7', '').strip()
        
        phenom = regime.get('Unnamed: 8', 'Unknown')
        action = regime.get('Unnamed: 11', '')
        tilt = regime.get('Unnamed: 13', '')
        
        # Filter df
        mask = (df['f_IV'] == iv_val) & \
               (df['f_Gamma'] == g_val) & \
               (df['f_Zomma'] == z_val) & \
               (df['f_Delta'] == d_val) & \
               (df['f_Vex'] == vex_val) & \
               (df['f_Vega'] == vega_val) & \
               (df['f_Vomma'] == vomma_val) & \
               (df['f_Speed'] == s_val)
               
        regime_df = df[mask]
        count = len(regime_df)
        
        lines.append(f"## Regime {idx+1}: {phenom}")
        lines.append(f"**Conditions**: IV={iv_val}, Gamma={g_val}, Zomma={z_val}, Delta={d_val}, Vex={vex_val}, Vega={vega_val}, Vomma={vomma_val}, Speed={s_val}")
        lines.append(f"**Expected Action**: {action}")
        lines.append(f"**Expected Tilt**: {tilt}\n")
        
        lines.append(f"**Occurrences**: {count} days")
        
        if count > 0:
            long_days = len(regime_df[regime_df['target'] == 1])
            short_days = len(regime_df[regime_df['target'] == -1])
            chop_days = len(regime_df[regime_df['target'] == 0])
            
            long_rate = (long_days / count) * 100
            short_rate = (short_days / count) * 100
            chop_rate = (chop_days / count) * 100
            
            avg_move = regime_df['max_move'].mean() * 100 # percentage
            
            lines.append(f"- **Win Rate (Long)**: {long_rate:.1f}%")
            lines.append(f"- **Win Rate (Short)**: {short_rate:.1f}%")
            lines.append(f"- **Chop / No-Trade**: {chop_rate:.1f}%")
            lines.append(f"- **Avg Max Move**: {avg_move:.2f}%")
            
            # Additional analysis logic
            is_bullish = long_rate > short_rate * 1.5
            is_bearish = short_rate > long_rate * 1.5
            
            lines.append("\n**Statistical Reality Check**:")
            if is_bullish:
                lines.append("> Data strongly supports a **Bullish** lean.")
            elif is_bearish:
                lines.append("> Data strongly supports a **Bearish** lean.")
            else:
                lines.append("> Data is relatively **Balanced / Neutral** or Mean-Reverting.")
                
            if avg_move > 1.0:
                lines.append("> Move size suggests **Trend / High Volatility** days.")
            elif avg_move < 0.5:
                lines.append("> Move size suggests **Tight Compression / Low Volatility**.")
        else:
            lines.append("> *No occurrences found in the last 3 years matching these exact criteria.*")
            
        lines.append("\n---\n")
        
    with open('regime_verification_report.md', 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
        
    print("Report generated: regime_verification_report.md")

if __name__ == "__main__":
    verify_regimes()
