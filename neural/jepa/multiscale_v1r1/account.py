"""Offline indivisible-contract account replay; no order transport exists."""
import json
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .artifacts import append_access, content_digest
from .contract import ContractError


class PaperAccount:
    def __init__(self, journal, initial_cash):
        self.journal = Path(journal)
        self.initial_cash = Decimal(str(initial_cash))
        if not self.initial_cash.is_finite() or self.initial_cash <= 0:
            raise ContractError('ACCOUNT: invalid synthetic cash')
        self.cash = self.initial_cash
        self.pending, self.positions = {}, {}
        self.last_clock = None
        self.max_committed_cash = Decimal(0)
        if self.journal.exists():
            previous = '0' * 64
            for i, line in enumerate(self.journal.read_text(encoding='utf-8').splitlines()):
                row = json.loads(line)
                checksum = row.pop('record_sha256')
                if (row['sequence'] != i or row['previous_sha256'] != previous
                        or content_digest(row) != checksum):
                    raise ContractError('ACCOUNT: corrupted restart journal')
                if i == 0 and (row['kind'] != 'INITIALIZE' or Decimal(row['cash']) != self.initial_cash):
                    raise ContractError('ACCOUNT: initial cash mismatch')
                self._apply(row)
                previous = checksum
        else:
            self._record(dict(kind='INITIALIZE', cash=str(self.initial_cash), timestamp=None))

    def _apply(self, row):
        if row['broker_submission'] is not False:
            raise ContractError('ACCOUNT: broker transport forbidden')
        if row['timestamp'] is not None:
            now = pd.Timestamp(row['timestamp'])
            if now.tzinfo is None or self.last_clock is not None and now < self.last_clock:
                raise ContractError('ACCOUNT: nonchronological journal')
            self.last_clock = now
        kind = row['kind']
        if kind == 'INTENT':
            key, cost = row['ticker'], Decimal(row['entry_cash'])
            if key in self.pending or key in self.positions or cost <= 0 or cost > self.cash:
                raise ContractError('ACCOUNT: invalid intent replay')
            self.cash -= cost
            self.pending[key] = row
        elif kind == 'SIMULATED_ENTRY':
            key = row['ticker']
            if key not in self.pending or self.pending[key]['intent_id'] != row['intent_id']:
                raise ContractError('ACCOUNT: entry without matching intent')
            self.positions[key] = self.pending.pop(key)
        elif kind == 'SIMULATED_EXIT':
            key = row['ticker']
            if key not in self.positions or self.positions[key]['intent_id'] != row['intent_id']:
                raise ContractError('ACCOUNT: exit without position')
            self.positions.pop(key)
            self.cash += Decimal(row['exit_cash'])
        elif kind == 'CANCEL_INTENT':
            key = row['ticker']
            if key not in self.pending or self.pending[key]['intent_id'] != row['intent_id']:
                raise ContractError('ACCOUNT: cancel without matching intent')
            self.cash += Decimal(self.pending.pop(key)['entry_cash'])
        elif kind not in ('INITIALIZE', 'REJECTION'):
            raise ContractError('ACCOUNT: unknown journal event')
        committed = sum((Decimal(r['entry_cash']) for r in [*self.pending.values(), *self.positions.values()]), Decimal(0))
        self.max_committed_cash = max(self.max_committed_cash, committed)

    def _record(self, row):
        row = dict(row, broker_submission=False, environment='SYNTHETIC_ONLY')
        # Validate on a reconstructed state before committing append-only evidence.
        self._apply(row)
        append_access(self.journal, **row)
        return row

    def intent(self, intent_id, ticker, timestamp, entry_cash, quantity=1):
        if quantity != 1 or isinstance(quantity, bool):
            raise ContractError('ACCOUNT: exactly one indivisible contract required')
        cost = Decimal(str(entry_cash))
        if not cost.is_finite() or cost <= 0:
            raise ContractError('ACCOUNT: invalid entry cash')
        reason = ('REJECT_OPEN_POSITION' if ticker in self.pending or ticker in self.positions else
                  'REJECT_INSUFFICIENT_CAPITAL' if cost > self.cash else None)
        common = dict(intent_id=intent_id, ticker=ticker, timestamp=pd.Timestamp(timestamp).isoformat())
        return self._record(dict(**common, kind='REJECTION', reason=reason)) if reason else self._record(
            dict(**common, kind='INTENT', entry_cash=str(cost), quantity=1))

    def entry(self, intent_id, ticker, timestamp):
        return self._record(dict(kind='SIMULATED_ENTRY', intent_id=intent_id, ticker=ticker,
                                 timestamp=pd.Timestamp(timestamp).isoformat()))

    def exit(self, intent_id, ticker, timestamp, exit_cash):
        cash = Decimal(str(exit_cash))
        if not cash.is_finite():
            raise ContractError('ACCOUNT: invalid exit cash')
        return self._record(dict(kind='SIMULATED_EXIT', intent_id=intent_id, ticker=ticker,
                                 timestamp=pd.Timestamp(timestamp).isoformat(), exit_cash=str(cash)))

    def submit_order(self, *_args, **_kwargs):
        raise ContractError('ACCOUNT: broker submission is permanently disabled in this adapter')


def replay_account(ledger, journal, initial_cash):
    """Use frozen intents, schedule simulated entries/exits on the actual clocks."""
    account = PaperAccount(journal, initial_cash)
    events = []
    for row in ledger:
        if row['reason'] != 'EXECUTED':
            continue
        facts = row['payoff']
        events.extend([(pd.Timestamp(row['decision_timestamp']), 1, 'intent', row),
                       (pd.Timestamp(facts['actual_entry_timestamp']), 2, 'entry', row),
                       (pd.Timestamp(facts['actual_exit_timestamp']), 0, 'exit', row)])
    accepted = set()
    for when, _, kind, row in sorted(events, key=lambda value: (value[0], value[1], value[3]['ticker'])):
        key, ticker = row['event_id'], row['ticker']
        money = row['payoff']['base']
        if kind == 'intent':
            if account.intent(key, ticker, when, money['entry_cash'])['kind'] == 'INTENT':
                accepted.add(key)
        elif key in accepted:
            if kind == 'entry':
                account.entry(key, ticker, when)
            else:
                account.exit(key, ticker, when, money['exit_cash'])
    return dict(final_cash=str(account.cash), initial_cash=str(account.initial_cash),
                accepted_intents=len(accepted), max_simultaneous_disbursement=str(account.max_committed_cash),
                broker_submission=False, environment='SYNTHETIC_ONLY')
