import subprocess
import itertools
import time
import pandas as pd
import re

def modify_ps1(pf_floor, train_months, conf):
    with open('neural/tuner_pipeline.ps1', 'r', encoding='utf-8') as f:
        code = f.read()
    
    code = re.sub(r'\$GbtTrainMonths = \d+', f'$GbtTrainMonths = {train_months}', code)
    code = re.sub(r'\$GbtMinPfFloorArg = "\d+\.\d+"', f'$GbtMinPfFloorArg = "{pf_floor:.2f}"', code)
    code = re.sub(r'\$BacktestBaseConfidenceArg = "\d+\.\d+"', f'$BacktestBaseConfidenceArg = "{conf:.3f}"', code)
    code = re.sub(r'\$GbtSelectionBaseConfidenceArg = \$BacktestBaseConfidenceArg', f'$GbtSelectionBaseConfidenceArg = "{conf:.3f}"', code)

    with open('neural/tuner_pipeline.ps1', 'w', encoding='utf-8') as f:
        f.write(code)

def evaluate():
    try:
        df = pd.read_csv('training_data/backtest_trades.csv')
        df['real_date'] = pd.to_datetime(df['date'].astype(str), format='%Y%m%d')
        
        total_trades = len(df)
        wins = len(df[df['pnl'] > 0])
        wr = wins / total_trades if total_trades > 0 else 0
        
        # PnL per ticker globally
        ticker_pnl = df.groupby('ticker')['pnl'].sum()
        all_profitable_globally = all(pnl > 0 for pnl in ticker_pnl)
        
        # April and May 2026 trades
        apr = df[df['real_date'].dt.strftime('%Y-%m') == '2026-04']
        may = df[df['real_date'].dt.strftime('%Y-%m') == '2026-05']
        
        apr_counts = apr.groupby('ticker').size()
        may_counts = may.groupby('ticker').size()
        
        apr_pnl = apr.groupby('ticker')['pnl'].sum()
        may_pnl = may.groupby('ticker')['pnl'].sum()
        
        passed = True
        
        if total_trades <= 1800: passed = False
        if wr <= 0.40: passed = False
        if not all_profitable_globally: passed = False
        
        for t in ['SPX', 'SPY', 'QQQ']:
            if apr_counts.get(t, 0) <= 12 or apr_pnl.get(t, -1) <= 0: passed = False
            if may_counts.get(t, 0) <= 12 or may_pnl.get(t, -1) <= 0: passed = False
            
        print(f"EVAL: Trades={total_trades}, WR={wr:.1%}, Passed={passed}")
        print(f"Apr Counts: {apr_counts.to_dict()}")
        print(f"May Counts: {may_counts.to_dict()}")
        print(f"Apr PnL: {apr_pnl.to_dict()}")
        print(f"May PnL: {may_pnl.to_dict()}")
        
        return passed, total_trades, wr, apr_counts.to_dict(), may_counts.to_dict()
    except Exception as e:
        print(f"EVAL ERROR: {e}")
        return False, 0, 0, {}, {}

def main():
    # Grid of configurations to try
    # We want to lower pf_floor and decrease train_months to adapt to May 2026
    # and adjust threshold around 0.43 to 0.46
    
    pf_floors = [0.95, 0.90, 1.00]
    train_months = [9, 6, 12]
    confs = [0.45, 0.44, 0.43, 0.46]
    
    for (pf, tm, c) in itertools.product(pf_floors, train_months, confs):
        print(f"\\n{'='*50}")
        print(f"TESTING: pf_floor={pf}, train_months={tm}, conf={c}")
        print(f"{'='*50}")
        
        modify_ps1(pf, tm, c)
        
        subprocess.run(["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "neural/tuner_pipeline.ps1", "-gbt"], check=True)
        
        passed, total, wr, apr, may = evaluate()
        
        if passed:
            print("SUCCESS! Found a configuration that meets all constraints.")
            break
        else:
            print("Failed. Trying next configuration...")

if __name__ == "__main__":
    main()
