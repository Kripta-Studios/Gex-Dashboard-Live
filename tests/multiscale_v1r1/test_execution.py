from decimal import Decimal

import pandas as pd
import pytest

from neural.jepa.multiscale_v1r1.metrics import summarize_pnl, terminal_gate
from neural.jepa.multiscale_v1r1.payoff import accounting, simulate_action
from neural.jepa.multiscale_v1r1.scheduler import replay


DAY = '2025-01-02'
DECISION = pd.Timestamp(DAY + ' 11:30:00.001', tz='America/New_York')


def quote(time, strike=100, delta=.25, bid='1.00', ask='1.01', right='CALL'):
    return dict(ticker='QQQ', trade_date=DAY, expiration=DAY, timestamp=DAY + 'T' + time + '-05:00',
                strike=strike, delta=delta, bid=bid, ask=ask, right=right)


def test_COST_002_scenario_signs_and_commissions():
    base, adverse = accounting('1', '1.06'), accounting('1', '1.06', adverse=True)
    assert Decimal(base['net_dollar_pnl']) == Decimal('1.40')
    assert Decimal(adverse['net_dollar_pnl']) == Decimal('-.60')
    assert Decimal(accounting('1', '0', missing_exit=True)['net_dollar_pnl']) == Decimal('-103.60')
    assert Decimal(accounting('1', '.001')['exit_cash']) == Decimal('-1.30')
    assert summarize_pnl([base['net_dollar_pnl']], ['202501'], ['202501'])['wr'] == 1
    assert summarize_pnl([adverse['net_dollar_pnl']], ['202501'], ['202501'])['wr'] == 0


def test_ENTRY_first_q_not_best_later_delta():
    facts = simulate_action([quote('11:31:00', 101, .25), quote('11:30:01', 100, .6),
                             quote('12:30:01', 100, .5, bid='1.06', ask='1.07')], 'QQQ', DAY, DECISION, 0)
    assert facts['contract_identity'][-1] == '100'
    assert facts['entry_quote_timestamp'].endswith('11:30:01-05:00')
    assert facts['exit_status'] == 'OBSERVED_QUOTE'


def test_ENTRY_tie_uses_spread_then_strike():
    quotes = [quote('11:30:01', 100, .25, bid='1', ask='1.2'),
              quote('11:30:01', 101, .25, bid='1', ask='1.1'),
              quote('11:30:01', 102, .25, bid='1', ask='1.1')]
    assert simulate_action(quotes, 'QQQ', DAY, DECISION, 0)['contract_identity'][-1] == '101'


@pytest.mark.parametrize('exit_time,expected', [('12:35:01', 'OBSERVED_QUOTE'),
                                             ('12:35:02', 'MISSING_EXIT_PENALTY')])
def test_EXIT_deadline_inclusive(exit_time, expected):
    facts = simulate_action([quote('11:30:01'), quote(exit_time)], 'QQQ', DAY, DECISION, 0)
    assert facts['exit_status'] == expected


def test_EXIT_never_changes_contract():
    facts = simulate_action([quote('11:30:01'), quote('12:30:01', 101)], 'QQQ', DAY, DECISION, 0)
    assert facts['exit_status'] == 'MISSING_EXIT_PENALTY'
    assert facts['exit_quote_timestamp'] is None


def test_SCHED_001_reject_at_decision_and_release_equality():
    times = ['11:30:00.001', '12:30:00', '12:30:01', '12:30:02']
    decisions = [dict(event_id=str(i), ticker='QQQ', action_id=0,
                      decision_timestamp=DAY + 'T' + time + '-05:00') for i, time in enumerate(times)]
    facts = simulate_action([quote('11:30:01'), quote('12:30:01')], 'QQQ', DAY, DECISION, 0)
    calls = []

    def payoff(event, action):
        calls.append(event)
        return facts if event == '0' else {'action_id': 0, 'action_available': False}

    results = replay(decisions, payoff)
    assert [r['reason'] for r in results] == ['EXECUTED', 'REJECT_OPEN_POSITION', 'REJECT_NO_ENTRY', 'REJECT_NO_ENTRY']
    assert calls == ['0', '2', '3']


@pytest.mark.parametrize('values,pf,wr', [([], None, None), ([0], None, 0), ([1, 2], 'Infinity', 1), ([-1], 0, 0)])
def test_METRIC_undefined_zero_infinite(values, pf, wr):
    result = summarize_pnl(values, ['202501'] * len(values), ['202501'])
    assert (result['pf'], result['wr']) == (pf, wr)


def test_GATE_incremental_and_strict_boundaries():
    months = [f'2025{i:02d}' for i in range(1, 13)] + [f'2026{i:02d}' for i in range(1, 7)]
    values = ([2] * 7 + [-1] * 6) * 18
    tags = [m for m in months for _ in range(13)]
    good = summarize_pnl(values, tags, months)
    assert terminal_gate(good, good, good) == 'FAILED_INCREMENTAL'
    weak = dict(good, net_dollar_pnl='1')
    assert terminal_gate(good, good, weak) == 'DEVELOPMENT_PASS_REQUIRES_SHADOW'
    for changed in (dict(good, pf=1.2), dict(good, wr=.45)):
        assert terminal_gate(changed, good, weak) == 'FAILED_ECONOMIC'
    missing = dict(good, monthly_counts={**good['monthly_counts'], months[0]: 12})
    assert terminal_gate(missing, good, weak) == 'FAILED_FREQUENCY'
