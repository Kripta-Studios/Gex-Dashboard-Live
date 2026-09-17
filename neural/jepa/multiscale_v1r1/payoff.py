"""COST-001 and native-quote execution primitives. No file access."""
from decimal import Decimal, localcontext

import pandas as pd

from .contract import ACTIONS, ContractError


def accounting(ask, bid, adverse=False, missing_exit=False):
    with localcontext() as ctx:
        ctx.prec = 34
        ask, bid = Decimal(str(ask)), Decimal(str(bid))
        if not ask.is_finite() or not bid.is_finite() or ask <= 0 or bid < 0:
            raise ContractError('COST-001: invalid price')
        slip = Decimal('.02' if adverse else '.01')
        entry = Decimal(100) * (ask + slip) + Decimal('1.30')
        fill = Decimal(0) if missing_exit else max(bid - slip, Decimal(0))
        exit_cash = Decimal(100) * fill - Decimal('1.30')
        pnl = exit_cash - entry
        return {'entry_cash': str(entry), 'exit_cash': str(exit_cash),
                'net_dollar_pnl': str(pnl), 'net_return': str(pnl / entry)}


def valid_quote(row, require_delta=False):
    try:
        ask, bid, strike = (Decimal(str(row[k])) for k in ('ask', 'bid', 'strike'))
        if not all(v.is_finite() for v in (ask, bid, strike)):
            return False
        valid = (ask > 0 and 0 <= bid <= ask and strike > 0
                 and row['right'] in ('CALL', 'PUT') and row['expiration'] == row['trade_date']
                 and pd.Timestamp(row['timestamp']).tzinfo is not None)
        return valid and (not require_delta or Decimal(str(row['delta'])).is_finite())
    except (KeyError, ValueError, TypeError):
        return False


def simulate_action(quotes, ticker, day, decision, action_id):
    """Caller must already hold a verified access permit. Uses one selected action."""
    action = ACTIONS[action_id]
    decision = pd.Timestamp(decision)
    if decision.tzinfo is None:
        raise ContractError('TIME-005: decision must be timezone-aware')
    records = [dict(r) for r in quotes if r['ticker'] == ticker and r['trade_date'] == day]
    keys = [(r['ticker'], r['trade_date'], r['expiration'], r['right'], str(r['strike']),
             str(r['timestamp'])) for r in records]
    if len(set(keys)) != len(keys):
        raise ContractError('TIME-005: duplicate native quote key')
    entries = [r for r in records if r['right'] == action.right and valid_quote(r, True)
               and decision <= pd.Timestamp(r['timestamp']) <= decision + pd.Timedelta(seconds=60)]
    if not entries:
        return {'action_available': False, 'unavailable_reason': 'NO_ENTRY', 'action_id': action_id}
    first = min(pd.Timestamp(r['timestamp']) for r in entries)
    candidates = [r for r in entries if pd.Timestamp(r['timestamp']) == first]

    def key(r):
        a, b = Decimal(str(r['ask'])), Decimal(str(r['bid']))
        return (abs(abs(Decimal(str(r['delta']))) - Decimal(action.delta) / 100),
                (a - b) / a, Decimal(str(r['strike'])),
                (ticker, day, r['expiration'], r['right'], str(r['strike'])))

    chosen = min(candidates, key=key)
    scheduled = first + pd.Timedelta(minutes=action.hold_minutes)
    deadline = min(scheduled + pd.Timedelta(minutes=5),
                   pd.Timestamp(f'{day} 16:00', tz='America/New_York'))
    if scheduled > deadline:
        raise ContractError('TIME-005: hold extends beyond close')
    exits = [r for r in records if r['expiration'] == chosen['expiration']
             and r['right'] == chosen['right'] and Decimal(str(r['strike'])) == Decimal(str(chosen['strike']))
             and valid_quote(r) and scheduled <= pd.Timestamp(r['timestamp']) <= deadline]
    exit_row = min(exits, key=lambda r: pd.Timestamp(r['timestamp'])) if exits else None
    bid = exit_row['bid'] if exit_row else 0
    exit_time = pd.Timestamp(exit_row['timestamp']) if exit_row else deadline
    return {'action_id': action_id, 'action_available': True, 'unavailable_reason': None,
            'contract_identity': [ticker, day, chosen['expiration'], action.right, str(chosen['strike'])],
            'target_delta': action.delta, 'observed_entry_delta': str(chosen['delta']),
            'decision_timestamp': decision.isoformat(), 'entry_quote_timestamp': first.isoformat(),
            'actual_entry_timestamp': first.isoformat(), 'scheduled_exit_timestamp': scheduled.isoformat(),
            'deadline': deadline.isoformat(), 'exit_quote_timestamp': exit_time.isoformat() if exit_row else None,
            'actual_exit_timestamp': exit_time.isoformat(), 'entry_ask': str(chosen['ask']),
            'exit_bid': str(bid), 'exit_status': 'OBSERVED_QUOTE' if exit_row else 'MISSING_EXIT_PENALTY',
            'base': accounting(chosen['ask'], bid, missing_exit=exit_row is None),
            'adverse': accounting(chosen['ask'], bid, adverse=True, missing_exit=exit_row is None)}
