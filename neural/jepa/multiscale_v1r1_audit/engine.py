"""Independent synthetic fold reconstruction, with no evaluator imports."""
import hashlib
import json
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

import numpy as np
import pandas as pd

from neural.jepa.multiscale_v1r1.contract import ACTIONS, TICKERS


def read(path):
    return json.loads(Path(path).read_bytes())


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError('AUDIT: ' + reason)


def cash(ask, bid, adverse=False, missing=False):
    with localcontext() as context:
        context.prec = 34
        slip = Decimal('0.02' if adverse else '0.01')
        debit = (Decimal(str(ask)) + slip) * 100 + Decimal('1.30')
        credit = (Decimal(0) if missing else max(Decimal(str(bid)) - slip, Decimal(0))) * 100 - Decimal('1.30')
        pnl = credit - debit
        return dict(entry_cash=str(debit), exit_cash=str(credit), net_dollar_pnl=str(pnl), net_return=str(pnl / debit))


def expected_action(event, action_id, quote_rows):
    action = ACTIONS[action_id]
    decision = pd.Timestamp(event['decision_timestamp'])
    rows = [q for q in quote_rows if q['ticker'] == event['ticker'] and q['trade_date'] == event['trade_date']]
    # Reconstruct native identity independently of the producer's string key.
    identities = {(q['ticker'], q['trade_date'], q['expiration'], q['right'],
                   Decimal(str(q['strike'])), pd.Timestamp(q['timestamp'])) for q in rows}
    require(len(identities) == len(rows), 'duplicate native quote key')

    def valid(q, entry=False):
        try:
            bid, ask, strike = (Decimal(str(q[field])) for field in ('bid', 'ask', 'strike'))
            return (bid.is_finite() and ask.is_finite() and strike.is_finite()
                    and ask > 0 and 0 <= bid <= ask and strike > 0
                    and q['expiration'] == q['trade_date']
                    and pd.Timestamp(q['timestamp']).tzinfo is not None
                    and (not entry or Decimal(str(q['delta'])).is_finite()))
        except (KeyError, ValueError, TypeError, InvalidOperation):
            return False

    entries = [q for q in rows if q['right'] == action.right and valid(q, entry=True)
               and decision <= pd.Timestamp(q['timestamp']) <= decision + pd.Timedelta(seconds=60)]
    if not entries:
        return dict(action_available=False, unavailable_reason='NO_ENTRY', action_id=action_id)
    first = min(pd.Timestamp(q['timestamp']) for q in entries)
    candidates = [q for q in entries if pd.Timestamp(q['timestamp']) == first]
    chosen = min(candidates, key=lambda q: (
        abs(abs(Decimal(str(q['delta']))) - Decimal(action.delta) / 100),
        (Decimal(str(q['ask'])) - Decimal(str(q['bid']))) / Decimal(str(q['ask'])), Decimal(str(q['strike'])),
        (q['ticker'], q['trade_date'], q['expiration'], q['right'], str(q['strike']))))
    scheduled = first + pd.Timedelta(minutes=action.hold_minutes)
    deadline = min(scheduled + pd.Timedelta(minutes=5), pd.Timestamp(event['trade_date'] + ' 16:00', tz='America/New_York'))
    exits = [q for q in rows if q['expiration'] == chosen['expiration']
             and q['right'] == chosen['right'] and Decimal(str(q['strike'])) == Decimal(str(chosen['strike']))
             and valid(q) and scheduled <= pd.Timestamp(q['timestamp']) <= deadline]
    exit_row = min(exits, key=lambda q: pd.Timestamp(q['timestamp'])) if exits else None
    exit_time = pd.Timestamp(exit_row['timestamp']) if exit_row else deadline
    bid = exit_row['bid'] if exit_row else 0
    return dict(action_id=action_id, action_available=True, unavailable_reason=None,
                contract_identity=[event['ticker'], event['trade_date'], chosen['expiration'], chosen['right'], str(chosen['strike'])],
                target_delta=action.delta, observed_entry_delta=str(chosen['delta']), decision_timestamp=decision.isoformat(),
                entry_quote_timestamp=first.isoformat(), actual_entry_timestamp=first.isoformat(),
                scheduled_exit_timestamp=scheduled.isoformat(), deadline=deadline.isoformat(),
                exit_quote_timestamp=exit_time.isoformat() if exit_row else None, actual_exit_timestamp=exit_time.isoformat(),
                entry_ask=str(chosen['ask']), exit_bid=str(bid), exit_status='OBSERVED_QUOTE' if exit_row else 'MISSING_EXIT_PENALTY',
                base=cash(chosen['ask'], bid, missing=exit_row is None), adverse=cash(chosen['ask'], bid, True, exit_row is None))


def reconstruct_ledger(decisions, payoffs):
    releases, result, identities = {}, [], set()
    for decision in sorted(decisions, key=lambda r: (pd.Timestamp(r['decision_timestamp']), r['ticker'])):
        require(decision['event_id'] not in identities, 'duplicate event')
        identities.add(decision['event_id'])
        now = pd.Timestamp(decision['decision_timestamp'])
        ticker = decision['ticker']
        row = dict(decision)
        if ticker in releases and now < releases[ticker]:
            row['reason'] = 'REJECT_OPEN_POSITION'
        elif decision['action_id'] is None:
            row['reason'] = 'NO_TRADE_THRESHOLD'
        else:
            payoff = payoffs[decision['event_id']][str(decision['action_id'])]
            if not payoff['action_available']:
                row['reason'] = 'REJECT_NO_ENTRY'
            else:
                require(pd.Timestamp(payoff['actual_entry_timestamp']) >= now, 'entry before decision')
                releases[ticker] = pd.Timestamp(payoff['actual_exit_timestamp'])
                row.update(reason='EXECUTED', payoff=payoff)
        result.append(row)
    return result


def statistics(ledger, months, scenario='base'):
    result = {}
    for ticker in TICKERS:
        trades = [r for r in ledger if r['ticker'] == ticker and r['reason'] == 'EXECUTED']
        pnl = [Decimal(r['payoff'][scenario]['net_dollar_pnl']) for r in trades]
        positive = sum((p for p in pnl if p > 0), Decimal(0))
        negative = -sum((p for p in pnl if p < 0), Decimal(0))
        monthly = {m: sum((p for p, row in zip(pnl, trades, strict=True) if row['month'] == m), Decimal(0)) for m in months}
        positive_months = [p for p in monthly.values() if p > 0]
        result[ticker] = dict(trades=len(pnl), wr=sum(p > 0 for p in pnl) / len(pnl) if pnl else None,
                              pf=float(positive / negative) if negative else 'Infinity' if positive else None,
                              net_dollar_pnl=str(sum(pnl, Decimal(0))), gross_gains=str(positive), gross_losses=str(negative),
                              monthly_pnl={m: str(p) for m, p in monthly.items()},
                              monthly_counts={m: sum(r['month'] == m for r in trades) for m in months},
                              positive_months=len(positive_months),
                              concentration=float(max(positive_months) / sum(positive_months)) if positive_months else None)
    return result


def audit_fold(folder, root, bank_expected=True):
    folder, root = Path(folder), Path(root)
    month = folder.name
    frozen = read(folder / 'frozen/freeze_manifest.json')
    require(frozen['month'] == month, 'freeze month')
    for files in frozen['artifacts'].values():
        require(bool(files), 'empty freeze group')
        for entry in files:
            require(checksum(entry['path']) == entry['sha256'], 'frozen artifact changed')
    inputs = read(folder / 'inputs.json')
    for key, value in inputs['payoff_hashes'].items():
        require(key < month and checksum(root / 'payoffs' / f'{key}.json') == value, 'future/changed historical payoff')
    for name, value in inputs['fixture_hashes'].items():
        require(checksum(root / name) == value, 'feature fixture changed')
    for name, value in read(folder / 'code.json').items():
        require(checksum(name) == value, 'code changed')
    selection = read(folder / 'selection.json')
    p = pd.Period(month, freq='M')
    require(inputs['selection'] == [(p - i).strftime('%Y%m') for i in range(6, 0, -1)], 'selection calendar')
    require(inputs['train'][-1] == (p - 7).strftime('%Y%m') and inputs['train'][0] == '202208', 'train calendar')
    require(selection['fold']['month'] == month, 'fold identity')
    bank = {}
    for directory in (root / 'feature_fixtures').iterdir():
        identity = read(directory / 'identity.json')
        x = np.load(directory / 'x5.npy')
        bank[(identity['ticker'], identity['signal'])] = (float(x[0, 0, 3]), float(x[0, 0, 5]))

    def events_for(m):
        # Independent fixture calendar; never import the producer's generator.
        records = []
        for i, date in enumerate(pd.bdate_range(pd.Timestamp(m + '01'), periods=13)):
            day = str(date.date())
            for ticker in TICKERS:
                for clock in ('11:30', '11:35'):
                    when = pd.Timestamp(day + ' ' + clock, tz='America/New_York') + pd.Timedelta(milliseconds=1)
                    records.append(dict(event_id=f'{ticker}:{day}:{clock}:SYNTHETIC', ticker=ticker, trade_date=day,
                                        month=m, decision_timestamp=when.isoformat(), signal=1 if i % 2 == 0 else -1))
        return records

    histories = {m: read(root / 'payoffs' / f'{m}.json') for m in inputs['train'] + inputs['selection']}
    models = read(folder / 'models.json')
    comparator = read(folder / 'ablation_models.json')
    event_cache = {m: events_for(m) for m in inputs['train'] + inputs['selection'] + [month]}
    refits = 0
    for collection, projection in [(models['A'], 0), (models['B'], 0), (comparator, 1)]:
        for action_id, model in enumerate(collection):
            groups, labels = {}, []
            for m in inputs['train']:
                for event in event_cache[m]:
                    x = str(bank[(event['ticker'], event['signal'])][projection])
                    y = float(histories[m][event['event_id']][str(action_id)]['base']['net_dollar_pnl'])
                    groups.setdefault(x, []).append(y)
                    labels.append(y)
            require(model['means'] == {x: float(np.mean(y)) for x, y in groups.items()}, 'test-double refit mismatch')
            require(model['fallback'] == float(np.mean(labels)), 'test-double fallback mismatch')
            refits += 1

    def predict(collection, events, projection):
        return np.asarray([[model['means'].get(str(bank[(e['ticker'], e['signal'])][projection]), model['fallback'])
                            for model in collection] for e in events])

    def decide(events, scores, threshold):
        rows = []
        for event, values in zip(events, scores, strict=True):
            index = int(np.argmax(values))
            action = index if values[index] > 0 and values[index] >= threshold else None
            rows.append({**{k: event[k] for k in ('event_id', 'ticker', 'month', 'trade_date', 'decision_timestamp')}, 'action_id': action})
        return rows

    selection_events = [e for m in inputs['selection'] for e in event_cache[m]]
    selection_payoffs = {key: value for m in inputs['selection'] for key, value in histories[m].items()}
    candidates = []
    for ci, config in enumerate(('A', 'B')):
        for ti, threshold in enumerate((0., 5.)):
            ledger = reconstruct_ledger(decide(selection_events, predict(models[config], selection_events, 0), threshold), selection_payoffs)
            metrics = statistics(ledger, inputs['selection'])
            require(metrics == selection['candidates'][ci * 2 + ti]['metrics'], 'selection metrics mismatch')
            if all(min(m['monthly_counts'].values()) >= 13 for m in metrics.values()):
                rank = (min(float(m['pf']) if m['pf'] is not None else float('-inf') for m in metrics.values()),
                        min(m['wr'] or 0 for m in metrics.values()), min(Decimal(m['net_dollar_pnl']) for m in metrics.values()), -ci, -ti)
                candidates.append((rank, {'config': config, 'threshold': threshold}))
    require(bool(candidates), 'no frequency-eligible winner')
    winner = max(candidates, key=lambda item: item[0])[1]
    require(winner == selection['winner'], 'pooled winner mismatch')
    events = event_cache[month]
    require(pd.read_parquet(folder / 'events.parquet').to_dict('records') == events, 'test event identities')
    decisions = read(folder / 'decisions.json')
    payoff = read(root / 'payoffs' / f'{month}.json')
    for event in events:
        entry = pd.Timestamp(event['decision_timestamp']).ceil('min')
        quote_rows = []
        for right in ('CALL', 'PUT'):
            for delta in (25, 35, 50):
                key = dict(ticker=event['ticker'], trade_date=event['trade_date'], expiration=event['trade_date'],
                           right=right, strike=float(100 + delta), delta=delta / 100 * (1 if right == 'CALL' else -1))
                quote_rows.append(dict(**key, timestamp=entry.isoformat(), bid=.98, ask=1.))
                bid = (1.55 if (right == 'CALL') == (event['signal'] == 1) else .55) - (delta - 25) * .001
                for hold in (60, 90, 120, 180):
                    quote_rows.append(dict(**key, timestamp=(entry + pd.Timedelta(minutes=hold)).isoformat(), bid=bid, ask=bid + .02))
        for action in ACTIONS:
            require(expected_action(event, action.action_id, quote_rows) == payoff[event['event_id']][str(action.action_id)],
                    'contract/native quote/deadline/cost payoff mismatch')
    ledgers = read(folder / 'ledger.json')
    for name, collection, projection in [('primary', models[winner['config']], 0), ('ablation', comparator, 1)]:
        scores = predict(collection, events, projection)
        require(np.array_equal(scores, np.load(folder / f'{name}_scores.npy')), 'prediction mismatch')
        require(decide(events, scores, winner['threshold']) == decisions[name], 'action/threshold mismatch')
    for name in decisions:
        require(reconstruct_ledger(decisions[name], payoff) == ledgers[name], 'scheduler/rejection/overlap mismatch')
    access = [json.loads(line) for line in (root / 'access_log.jsonl').read_text(encoding='utf-8').splitlines()]
    opened = [i for i, e in enumerate(access) if e['stage'] == 'synthetic_outcome_created' and e['month'] == month]
    freezes = [i for i, e in enumerate(access) if e['stage'] == 'freeze_verified' and e['month'] == month]
    require(len(opened) == len(freezes) == 1 and freezes[0] < opened[0], 'test payoff before freeze')
    require(access[freezes[0]]['freeze_sha256'] == checksum(folder / 'frozen/freeze_manifest.json'), 'freeze publication hash')
    return dict(status='PASS_INDEPENDENT_SYNTHETIC_FOLD_AUDIT', month=month, test_double_refits=refits,
                models_are_test_doubles=True, winners_reproduced=1, prediction_vectors=2,
                ledger_rows=sum(map(len, ledgers.values())), action_payoffs_rebuilt=len(events) * 24, mismatches=0,
                scope='Synthetic model/calendar/selection/freeze/replay/contract/cost; raw fixture feature audit recorded separately')
