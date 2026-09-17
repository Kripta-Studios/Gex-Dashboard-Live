"""SCHED-001: chronological decisions, release before equality, no fallback."""
import pandas as pd

from .contract import ContractError


def replay(decisions, get_payoff):
    output, release, seen = [], {}, set()
    for row in sorted(decisions, key=lambda r: (pd.Timestamp(r['decision_timestamp']), r['ticker'])):
        if row['event_id'] in seen:
            raise ContractError('SCHED-001: duplicate decision')
        seen.add(row['event_id'])
        when = pd.Timestamp(row['decision_timestamp'])
        ticker = row['ticker']
        result = dict(row)
        if ticker in release and when < release[ticker]:
            result['reason'] = 'REJECT_OPEN_POSITION'
        elif row['action_id'] is None:
            result['reason'] = 'NO_TRADE_THRESHOLD'
        else:
            payoff = get_payoff(row['event_id'], row['action_id'])
            if payoff['action_id'] != row['action_id']:
                raise ContractError('SCHED-001: action identity mismatch')
            if not payoff['action_available']:
                result['reason'] = 'REJECT_NO_ENTRY'
            else:
                entry = pd.Timestamp(payoff['actual_entry_timestamp'])
                exit_time = pd.Timestamp(payoff['actual_exit_timestamp'])
                if not when <= entry <= when + pd.Timedelta(seconds=60) or exit_time <= entry:
                    raise ContractError('SCHED-001: invalid execution clock')
                release[ticker] = exit_time
                result.update(reason='EXECUTED', payoff=payoff)
        output.append(result)
    return output
