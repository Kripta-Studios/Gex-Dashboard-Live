"""Independent aggregate, paired-bootstrap and synthetic account reconstruction."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import numpy as np

from .engine import require, statistics


def audit_summary(root):
    root = Path(root)
    months = [p.name for p in sorted((root / 'folds').iterdir())]
    all_rows = {name: [] for name in ('primary', 'ablation', 'baseline')}
    for month in months:
        rows = json.loads((root / 'folds' / month / 'ledger.json').read_bytes())
        for name, ledger in rows.items():
            all_rows[name] += ledger
    actual_metrics = json.loads((root / 'metrics.json').read_bytes())
    for name, rows in all_rows.items():
        for scenario in ('base', 'adverse'):
            require(statistics(rows, months, scenario) == actual_metrics[name][scenario], 'aggregate scenario metrics')
    cash = Decimal('350.00')
    pending, positions, accepted = {}, {}, 0
    maximum = Decimal(0)
    previous = '0' * 64
    for i, line in enumerate((root / 'paper_account.jsonl').read_text(encoding='utf-8').splitlines()):
        row = json.loads(line)
        checksum = row.pop('record_sha256')
        data = json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
        require(row['sequence'] == i and row['previous_sha256'] == previous and hashlib.sha256(data).hexdigest() == checksum,
                'account journal chain')
        previous = checksum
        require(row['broker_submission'] is False, 'broker submission')
        key = row.get('ticker')
        if row['kind'] == 'INTENT':
            debit = Decimal(row['entry_cash'])
            require(row['quantity'] == 1 and key not in pending and key not in positions and debit <= cash, 'capital/quantity/overlap')
            cash -= debit
            pending[key] = row
            accepted += 1
        elif row['kind'] == 'SIMULATED_ENTRY':
            require(key in pending and pending[key]['intent_id'] == row['intent_id'], 'entry identity')
            positions[key] = pending.pop(key)
        elif row['kind'] == 'SIMULATED_EXIT':
            require(key in positions and positions[key]['intent_id'] == row['intent_id'], 'exit identity')
            position = positions.pop(key)
            original = next(r for r in all_rows['primary'] if r['event_id'] == position['intent_id'])
            require(row['exit_cash'] == original['payoff']['base']['exit_cash'], 'account exit cost')
            cash += Decimal(row['exit_cash'])
        elif row['kind'] == 'REJECTION':
            reason = 'REJECT_OPEN_POSITION' if key in positions or key in pending else 'REJECT_INSUFFICIENT_CAPITAL'
            require(row['reason'] == reason, 'account rejection')
        elif row['kind'] != 'INITIALIZE':
            raise ValueError('AUDIT: unknown account transition')
        maximum = max(maximum, sum((Decimal(r['entry_cash']) for r in [*pending.values(), *positions.values()]), Decimal(0)))
    require(not positions and not pending, 'unreleased account position')
    account = json.loads((root / 'account_summary.json').read_bytes())
    require(account['final_cash'] == str(cash) and account['max_simultaneous_disbursement'] == str(maximum)
            and account['accepted_intents'] == accepted, 'account summary')
    expected_bootstrap = rebuild_bootstrap(all_rows, months)
    require(expected_bootstrap == json.loads((root / 'bootstrap.json').read_bytes()), 'paired bootstrap')
    return dict(status='PASS_INDEPENDENT_SYNTHETIC_SUMMARY', months=len(months), metrics_scenarios=6,
                bootstrap_draws=10000, paired_calendar=True, account_journal_reproduced=True,
                broker_submission=False, historical_economics='NOT_EVALUATED')


def rebuild_bootstrap(ledgers, months):
    """Independent daily reductions and circular block sampling, including no-trade days."""
    tickers = ('SPXW', 'SPY', 'QQQ')
    rng = np.random.default_rng(20260802)
    totals = {name: np.zeros((10000, 3, 5)) for name in ('primary', 'ablation')}
    admitted = 0
    for month in months:
        # Decisions retain every fixture day, including days without trades.
        days = sorted({r['trade_date'] for r in ledgers['primary'] if r['month'] == month})
        admitted += len(days)
        starts = rng.integers(len(days), size=(10000, (len(days) + 4) // 5))
        indices = np.concatenate([(starts + offset)[..., None] for offset in range(5)], axis=2)
        indices = (indices.reshape(10000, -1)[:, :len(days)] % len(days))
        for name in totals:
            daily = np.zeros((len(days), 3, 5))
            for row in ledgers[name]:
                if row['month'] != month or row['reason'] != 'EXECUTED':
                    continue
                pnl = float(row['payoff']['base']['net_dollar_pnl'])
                daily[days.index(row['trade_date']), tickers.index(row['ticker'])] += [pnl, max(0, pnl), max(0, -pnl), int(pnl > 0), 1]
            totals[name] += daily[indices].sum(axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        values = {name: dict(pnl=a[:, :, 0], pf=a[:, :, 1] / a[:, :, 2], wr=a[:, :, 3] / a[:, :, 4]) for name, a in totals.items()}
        values['paired_difference'] = {k: values['primary'][k] - values['ablation'][k] for k in ('pnl', 'pf', 'wr')}
    metrics = {}
    for name, group in values.items():
        metrics[name] = {}
        for metric, matrix in group.items():
            metrics[name][metric] = {}
            for i, ticker in enumerate(tickers):
                a = matrix[:, i]
                finite = a[np.isfinite(a)]
                metrics[name][metric][ticker] = dict(finite_draws=len(finite), undefined_draws=int(np.isnan(a).sum()),
                                                    positive_infinite_draws=int(np.isposinf(a).sum()),
                                                    negative_infinite_draws=int(np.isneginf(a).sum()),
                                                    finite_only_interval=np.quantile(finite, [.025, .975]).tolist() if len(finite) else None)
    return dict(draws=10000, block_days=5, seed=20260802, admitted_days=admitted,
                shared_indices_across_tickers_and_policies=True, diagnostic_only=True, metrics=metrics)
