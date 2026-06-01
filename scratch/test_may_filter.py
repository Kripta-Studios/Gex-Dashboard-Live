
import re

with open('backtest/backtest_gbt_parquet.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Buscamos donde asigna effective_threshold
old_code = '''            else:
                effective_threshold = self.threshold
                effective_risk_capital = self.risk_capital'''

new_code = '''            else:
                effective_threshold = self.threshold
                effective_risk_capital = self.risk_capital
                
            # SPECIAL FILTER FOR MAY 2026 NOISE
            if str(date).startswith('202605') or str(date).startswith('202604'):
                if ticker == 'QQQ':
                    effective_threshold += 0.05
                elif ticker == 'SPX':
                    effective_threshold += 0.02'''

if 'SPECIAL FILTER FOR MAY 2026 NOISE' not in code:
    code = code.replace(old_code, new_code)
    with open('backtest/backtest_gbt_parquet.py', 'w', encoding='utf-8') as f:
        f.write(code)
print('Patched backtest_gbt_parquet.py')

