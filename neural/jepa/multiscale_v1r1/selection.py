"""FOLD-001: pooled selection using executed ledgers and one shared winner."""
from decimal import Decimal

from .contract import THRESHOLDS_USD, TICKERS
from .metrics import pf_value, summarize_pnl
from .models import choose_action
from .scheduler import replay


def decisions_from_scores(events, scores, threshold):
    return [dict(event_id=e['event_id'], ticker=e['ticker'], month=e['month'], trade_date=e['trade_date'],
                 decision_timestamp=e['decision_timestamp'], action_id=choose_action(row, threshold))
            for e, row in zip(events, scores, strict=True)]


def ledger_metrics(ledger, months, scenario='base'):
    return {ticker: summarize_pnl(
        [r['payoff'][scenario]['net_dollar_pnl'] for r in ledger if r['ticker'] == ticker and r['reason'] == 'EXECUTED'],
        [r['month'] for r in ledger if r['ticker'] == ticker and r['reason'] == 'EXECUTED'], months)
        for ticker in TICKERS}


def select_winner(events, scores_by_config, get_payoff, months):
    candidates = []
    for config_index, config in enumerate(('A', 'B')):
        for threshold_index, threshold in enumerate(THRESHOLDS_USD):
            decisions = decisions_from_scores(events, scores_by_config[config], threshold)
            ledger = replay(decisions, get_payoff)
            metrics = ledger_metrics(ledger, months)
            eligible = all(min(m['monthly_counts'].values()) >= 13 for m in metrics.values())
            rank = (min(pf_value(m) for m in metrics.values()), min(m['wr'] or 0 for m in metrics.values()),
                    min(Decimal(m['net_dollar_pnl']) for m in metrics.values()), -config_index, -threshold_index)
            candidates.append(dict(config=config, threshold=threshold, eligible=eligible, metrics=metrics, _rank=rank))
    eligible = [c for c in candidates if c['eligible']]
    winner = max(eligible, key=lambda c: c['_rank']) if eligible else None
    report = [{key: value for key, value in c.items() if key != '_rank'} for c in candidates]
    return (None if winner is None else dict(config=winner['config'], threshold=winner['threshold'])), report
