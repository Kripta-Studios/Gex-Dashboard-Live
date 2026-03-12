import os
import glob
import pandas as pd
from datetime import datetime

PROJECT_ROOT = r"c:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live"
RESULTS_DIR = os.path.join(PROJECT_ROOT, "backtest_results")

def analyze_csv(filepath, name):
    print(f"\n{'='*60}")
    print(f" Analizando: {name}")
    print(f" Archivo: {os.path.basename(filepath)}")
    print(f"{'='*60}")
    
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Error reading file: {e}")
        return
        
    if df.empty or 'date' not in df.columns:
        print("El CSV está vacío o no tiene columna 'date'.")
        return

    # Convert date (assumed YYYYMMDD string or int) to datetime
    df['date_dt'] = pd.to_datetime(df['date'].astype(str), format='%Y%m%d', errors='coerce')
    df = df.dropna(subset=['date_dt']).sort_values('date_dt')
    
    if df.empty:
        print("No se pudieron extraer fechas válidas.")
        return

    # Calculate trades per month
    df['year_month'] = df['date_dt'].dt.to_period('M')
    monthly_counts = df['year_month'].value_counts().sort_index()
    
    # Print Trades per Month
    print("\n[ Trades por Mes ]")
    print(monthly_counts.to_string())
    
    # Calculate Gaps
    # We want to see if any month in the range has 0 trades
    min_month = df['year_month'].min()
    max_month = df['year_month'].max()
    all_months = pd.period_range(min_month, max_month, freq='M')
    
    missing_months = []
    low_trade_months = []
    
    for m in all_months:
        count = monthly_counts.get(m, 0)
        if count == 0:
            missing_months.append(str(m))
        elif count < 10:
            low_trade_months.append((str(m), count))
            
    print("\n[ Análisis de Gaps Mensuales ]")
    if missing_months:
        print(f"[!] MESES SIN TRADES ({len(missing_months)}): {', '.join(missing_months)}")
    else:
        print("[OK] No hay meses vacíos en el rango.")
        
    if low_trade_months:
        print(f"[!] MESES CON MUY POCOS TRADES (< 10):")
        for m, c in low_trade_months:
            print(f"   - {m}: {c} trades")
    else:
        print("[OK] Todos los meses activos tienen buena densidad de trades (>= 10).")

    # Calculate Max Days Without Trades
    df['prev_date'] = df['date_dt'].shift(1)
    df['days_gap'] = (df['date_dt'] - df['prev_date']).dt.days
    
    max_gap_row = df.loc[df['days_gap'].idxmax()]
    max_gap_days = max_gap_row['days_gap']
    
    if pd.notna(max_gap_days) and max_gap_days > 7:
        print(f"\n[ Brecha Máxima (Días seguidos sin operar) ]")
        start_gap = max_gap_row['prev_date'].strftime('%Y-%m-%d')
        end_gap = max_gap_row['date_dt'].strftime('%Y-%m-%d')
        print(f"[!] {int(max_gap_days)} DÍAS SIN TRADES: desde {start_gap} hasta {end_gap}")
    elif pd.notna(max_gap_days):
        print(f"\n[ Brecha Máxima ]")
        print(f"[OK] La brecha continua más larga fue de solo {int(max_gap_days)} días (normal).")

def main():
    if not os.path.exists(RESULTS_DIR):
        print(f"El directorio no existe: {RESULTS_DIR}")
        return

    # Find the most recent GBT_ONLY and GBT_RL csv files
    gbt_only_files = glob.glob(os.path.join(RESULTS_DIR, "gbt_only_*.csv"))
    gbt_rl_files = glob.glob(os.path.join(RESULTS_DIR, "gbt_rl_*.csv"))
    
    if gbt_only_files:
        latest_gbt = max(gbt_only_files, key=os.path.getmtime)
        analyze_csv(latest_gbt, "GBT-Only")
    else:
        print("No se encontraron archivos gbt_only*.csv")
        
    if gbt_rl_files:
        latest_rl = max(gbt_rl_files, key=os.path.getmtime)
        analyze_csv(latest_rl, "GBT + RL")
    else:
        print("No se encontraron archivos gbt_rl*.csv")

if __name__ == "__main__":
    main()
