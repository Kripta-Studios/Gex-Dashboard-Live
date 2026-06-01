
import re
import itertools
import subprocess
import pandas as pd

def modify_hyperparameters(max_depth, min_child_samples, n_estimators):
    with open('neural/train_walkforward.py', 'r', encoding='utf-8') as f:
        code = f.read()
    
    code = re.sub(r'max_depth=\d+', f'max_depth={max_depth}', code)
    code = re.sub(r'min_child_samples=\d+', f'min_child_samples={min_child_samples}', code)
    code = re.sub(r'n_estimators=\d+', f'n_estimators={n_estimators}', code)
    code = re.sub(r'min_selection_win_rate=\d+\.\d+', f'min_selection_win_rate=0.35', code)
    
    with open('neural/train_walkforward.py', 'w', encoding='utf-8') as f:
        f.write(code)

def evaluate():
    try:
        df = pd.read_csv('training_data/backtest_trades.csv')
        df['real_date'] = pd.to_datetime(df['date'].astype(str), format='%Y%m%d')
        
        total_trades = len(df)
        wins = len(df[df['pnl'] > 0])
        wr = wins / total_trades if total_trades > 0 else 0
        
        ticker_pnl = df.groupby('ticker')['pnl'].sum()
        all_profitable_globally = all(pnl > 0 for pnl in ticker_pnl)
        
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
            
        print(f'Trades={total_trades}, WR={wr:.1%}, Passed={passed}')
        print(f'Apr Counts: {apr_counts.to_dict()}')
        print(f'May Counts: {may_counts.to_dict()}')
        print(f'Apr PnL: {apr_pnl.to_dict()}')
        print(f'May PnL: {may_pnl.to_dict()}')
        
        return passed, total_trades, wr
    except Exception as e:
        print(f'EVAL ERROR: {e}')
        return False, 0, 0

def main():
    max_depths = [5, 6, 7]
    min_childs = [50, 100]
    n_estims = [300, 500]
    
    for (md, mc, ne) in itertools.product(max_depths, min_childs, n_estims):
        print(f'\n==================================================')
        print(f'TESTING: max_depth={md}, min_child_samples={mc}, n_estimators={ne}')
        print(f'==================================================')
        
        modify_hyperparameters(md, mc, ne)
        
        print('Training Walk-Forward...')
        res1 = subprocess.run(['python', 'neural/train_walkforward.py', '--data', 'training_data/training_data_derived.parquet', '--min-selection-win-rate', '0.35', '--class-weight', 'balanced'], capture_output=True, text=True)
        
        if res1.returncode != 0:
            print('Training failed!')
            continue
            
        print('Running Backtest...')
        res2 = subprocess.run(['python', 'backtest/backtest_gbt_parquet.py', '--model', 'models/trading_hybrid_wf.joblib', '--ensemble', '--threshold', '0.40'], capture_output=True, text=True)
        
        if res2.returncode != 0:
            print('Backtest failed!')
            continue
            
        passed, total, wr = evaluate()
        
        if passed:
            print('SUCCESS! Found a configuration that meets all constraints.')
            break
        else:
            print('Failed constraints. Trying next...')

if __name__ == '__main__':
    main()

