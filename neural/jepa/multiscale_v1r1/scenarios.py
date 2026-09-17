"""Integrated edge cases with generated quotes and independent accounting audit."""
from copy import deepcopy
from decimal import Decimal

import pandas as pd

from .account import PaperAccount
from .admission import inspect_lineage
from .artifacts import digest, write_json
from .contract import ContractError
from .payoff import simulate_action
from .prospective import record_reception
from .scheduler import replay
from .selection import ledger_metrics
from .synthetic_fixtures import action_quotes, month_events


def run_scenarios(root):
    root.mkdir()
    event = month_events('202501')[0]
    decision = {k: event[k] for k in ('event_id', 'ticker', 'month', 'trade_date', 'decision_timestamp')}
    decision['action_id'] = 0
    scenarios = {}
    from neural.jepa.multiscale_v1r1_audit.engine import expected_action, statistics
    for name in ('signal', 'flat', 'random', 'cost_flip', 'missing_exit'):
        quotes = action_quotes(event, name)
        facts = simulate_action(quotes, event['ticker'], event['trade_date'], event['decision_timestamp'], 0)
        assert facts == expected_action(event, 0, quotes)
        ledger = replay([decision], lambda _e, _a: facts)
        metrics = {case: ledger_metrics(ledger, ['202501'], case) for case in ('base', 'adverse')}
        for case in metrics:
            assert metrics[case] == statistics(ledger, ['202501'], case)
        if name == 'flat':
            assert float(facts['base']['net_dollar_pnl']) < 0
            abstention = replay([dict(decision, action_id=None)], lambda *_: (_ for _ in ()).throw(AssertionError('outcome read for abstention')))
            assert abstention[0]['reason'] == 'NO_TRADE_THRESHOLD'
        if name == 'cost_flip':
            assert float(facts['base']['net_dollar_pnl']) == 1.4
            assert float(facts['adverse']['net_dollar_pnl']) == -.6
            assert metrics['base']['SPXW']['wr'] == 1 and metrics['adverse']['SPXW']['wr'] == 0
        if name == 'missing_exit':
            assert facts['exit_status'] == 'MISSING_EXIT_PENALTY' and facts['action_available']
        scenarios[name] = dict(quotes=quotes, ledger=ledger, metrics=metrics, synthetic_only=True)
        write_json(root / f'{name}.json', scenarios[name])
    journal = root / 'restart_account.jsonl'
    clock = pd.Timestamp(event['decision_timestamp'])
    account = PaperAccount(journal, '150')
    assert account.intent('first', 'SPXW', clock, '102.30')['kind'] == 'INTENT'
    restarted = PaperAccount(journal, '150')
    assert restarted.intent('second', 'SPXW', clock, '102.30')['reason'] == 'REJECT_OPEN_POSITION'
    assert restarted.intent('third', 'SPY', clock, '102.30')['reason'] == 'REJECT_INSUFFICIENT_CAPITAL'
    for quantity in (.5, 2, 0):
        try:
            restarted.intent('invalid', 'QQQ', clock, '1', quantity)
        except ContractError:
            pass
        else:
            raise AssertionError('fractional/multiple contract accepted')
    restarted.entry('first', 'SPXW', clock + pd.Timedelta(seconds=30))
    reopened = PaperAccount(journal, '150')
    assert 'SPXW' in reopened.positions
    reopened.exit('first', 'SPXW', clock + pd.Timedelta(minutes=61), '103.70')
    assert reopened.cash == Decimal('151.40')
    try:
        reopened.submit_order({})
    except ContractError:
        pass
    else:
        raise AssertionError('broker path enabled')
    lineage = dict(source_id='fixture', input_hashes=[digest(root / 'signal.json')],
                   transformation_sha256=digest(__file__), parameters={'synthetic': True},
                   event_timestamp=clock.isoformat(), available_at=clock.isoformat(), received_at=None,
                   materialized_at='2026-09-17T12:00:00Z', repair=None, evidence='generated fixture', environment='SYNTHETIC_FIXTURE')
    assert inspect_lineage(lineage, clock) == 'PROVENANCE_SUPPORTED'
    future = deepcopy(lineage)
    future['available_at'] = (clock + pd.Timedelta(seconds=1)).isoformat()
    assert inspect_lineage(future, clock) == 'REJECTED_CAUSALITY'
    reception = dict(event_id='offline-1', market_timestamp=clock.isoformat(), received_at=clock.isoformat(),
                     feature_started_at=clock.isoformat(), feature_completed_at=clock.isoformat(),
                     decision_at=clock.isoformat(), intent_at=clock.isoformat(), quote_age_ms=0., processing_latency_ms=0.,
                     policy_sha256='0' * 64, feature_sha256='1' * 64, decision_reason='NO_TRADE_THRESHOLD')
    record_reception(root / 'offline_capture.jsonl', reception)
    record_reception(root / 'offline_capture.jsonl', dict(reception, decision_reason='REVISED_OFFLINE_FIXTURE'))
    result = dict(status='PASS_SYNTHETIC_SCENARIOS', quote_scenarios=list(scenarios),
                  account_restart=True, pending_intent_restart=True, capital_rejection=True,
                  indivisible_contracts=True, positive_fixture_admission=True, future_dependency_rejected=True,
                  offline_capture_revisions=2, broker_submission=False, historical_economics='NOT_EVALUATED')
    write_json(root / 'summary.json', result)
    return result
