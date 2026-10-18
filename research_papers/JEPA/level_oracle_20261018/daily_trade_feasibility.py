"""Read-only calendar/entry-availability and existing-ledger coverage diagnostic."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

INDEX_COLUMNS = ('ticker', 'date', 'split', 'status', 'day_root', 'actions_count', 'no_fill_actions',
                 'states_sha256', 'actions_sha256', 'labels_sha256')
LABEL_COLUMNS = ('action_id', 'status', 'missing_exit')
ACTION_COLUMNS = ('action_id', 'state_i', 'entry_i')
STATE_COLUMNS = ('state_i', 'eligible')
POLICIES = tuple(f'{model}__{threshold}' for model in ('gbt_net', 'gbt_advantage', 'tcn_teacher') for threshold in (0, 5, 10))


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(part)
    return value.hexdigest()


def maximum_zero_streak(values):
    """Expected-session order: an unknown/missing day breaks an observed streak."""
    longest = current = 0
    for value in values:
        current = current + 1 if value is not None and value == 0 else 0
        longest = max(longest, current)
    return longest


def arrays(path, columns):
    table = pq.read_table(path, columns=list(columns))
    return {name: table[name].to_numpy() for name in columns}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('D:/GexResearchArtifacts/level_oracle_20261018'))
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    output = args.out or args.root / 'daily_trade_feasibility_v1'
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    index_path = args.root / 'engine_v1/index.parquet'
    index = pq.read_table(index_path, columns=list(INDEX_COLUMNS)).to_pandas()
    calendar_path = args.root / 'learners_v1/expected_full_calendar.csv'
    calendar = pd.read_csv(calendar_path, dtype={'date': str}).date.tolist()
    expected = {(ticker, date) for ticker in ('QQQ', 'SPXW', 'SPY') for date in calendar}
    if len(calendar) != 867 or set(zip(index.ticker, index.date)) != expected or len(index) != 2601:
        raise ValueError('Frozen calendar/index coverage differs')
    if Counter(index.status) != {'COMPLETE': 2595, 'MISSING_SOURCE': 6}:
        raise ValueError('Source status counts differ')
    records = []
    for row in index.sort_values(['ticker', 'date']).itertuples(index=False):
        result = dict(ticker=row.ticker, date=row.date, split=row.split, source_status=row.status,
                      eligibility_first_state=None, action_first_state=None, filled_first_state_hindsight=None,
                      filled_first_entry_hindsight=None, eligible_states=None, actions=None, filled_entries=None,
                      filled_entries_with_observed_exit=None, states_sha256_reported=row.states_sha256,
                      actions_sha256_reported=row.actions_sha256, labels_sha256_reported=row.labels_sha256)
        if row.status != 'COMPLETE':
            result['feasibility'] = 'NO_EVALUABLE_MISSING_SOURCE'
        else:
            root = Path(row.day_root)
            states = arrays(root / 'states.parquet', STATE_COLUMNS)
            actions = arrays(root / 'actions.parquet', ACTION_COLUMNS)
            labels = arrays(root / 'labels.parquet', LABEL_COLUMNS)
            ai, li = np.argsort(actions['action_id']), np.argsort(labels['action_id'])
            if len(np.unique(actions['action_id'])) != len(ai) or not np.array_equal(actions['action_id'][ai], labels['action_id'][li]):
                raise ValueError('Action/label identity mismatch')
            filled = labels['status'][li] == 'FILLED'
            if not np.isin(labels['status'], ['FILLED', 'NO_FILL']).all():
                raise ValueError('Unknown execution status')
            if len(ai) != row.actions_count or int((~filled).sum()) != int(row.no_fill_actions):
                raise ValueError('Audited index execution counts differ')
            eligible = states['state_i'][states['eligible']]
            result.update(eligible_states=len(eligible), actions=len(ai), filled_entries=int(filled.sum()),
                          filled_entries_with_observed_exit=int((filled & ~labels['missing_exit'][li]).sum()),
                          eligibility_first_state=int(eligible.min()) if len(eligible) else None,
                          action_first_state=int(actions['state_i'].min()) if len(ai) else None,
                          filled_first_state_hindsight=int(actions['state_i'][ai][filled].min()) if filled.any() else None,
                          filled_first_entry_hindsight=int(actions['entry_i'][ai][filled].min()) if filled.any() else None)
            result['feasibility'] = ('OBSERVED_FILLED_ENTRY_AVAILABLE' if filled.any() else
                                     'OBSERVED_ACTIONS_NO_FILLED_ENTRY' if len(ai) else 'OBSERVED_NO_CAUSAL_ACTION')
        records.append(result)
        if len(records) % 250 == 0:
            print(json.dumps(dict(days_checked=len(records))), flush=True)
    availability = pd.DataFrame(records)
    availability.to_csv(output / 'daily_action_availability.csv', index=False)
    audit_path = args.root / 'learners_v1_economic_audit/audit.json'
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    hashes = audit['verified_economic_outputs']
    policy_rows, policy_days, verified_ledgers = [], [], {}
    for split, year in (('validation', '2025'), ('test', '2026')):
        dates = [date for date in calendar if date.startswith(year)]
        available_keys = {(row.ticker, row.date) for row in index.itertuples() if row.status == 'COMPLETE'}
        for policy in POLICIES:
            relative = f'{split}\\{policy}_ledger.parquet'
            path = args.root / 'learners_v1' / split / f'{policy}_ledger.parquet'
            digest = sha(path)
            if digest != hashes[relative]:
                raise ValueError('Original policy ledger hash differs: ' + relative)
            verified_ledgers[relative] = digest
            ledger = pq.read_table(path, columns=['ticker', 'date', 'status']).to_pandas()
            if not ledger.status.eq('FILLED').all():
                raise ValueError('Canonical ledger contains a non-filled row')
            if any((row.ticker, row.date) not in available_keys or row.date not in dates for row in ledger.itertuples()):
                raise ValueError('Ledger date outside available split calendar')
            counts = Counter(zip(ledger.ticker, ledger.date))
            for ticker in ('QQQ', 'SPXW', 'SPY'):
                daily = [counts[(ticker, date)] if (ticker, date) in available_keys else None for date in dates]
                observed = np.asarray([count for count in daily if count is not None], dtype=int)
                for date, count in zip(dates, daily):
                    policy_days.append(dict(policy=policy, split=split, ticker=ticker, date=date,
                                            status='NO_EVALUABLE_MISSING_SOURCE' if count is None else 'OBSERVED', fills=count))
                policy_rows.append(dict(policy=policy, split=split, year=int(year), ticker=ticker,
                                        expected_days=len(dates), available_days=len(observed),
                                        missing_source_days=sum(count is None for count in daily),
                                        days_with_fills=int((observed > 0).sum()), observed_zero_trade_days=int((observed == 0).sum()),
                                        min_fills=int(observed.min()), p10_fills=float(np.quantile(observed, .1)),
                                        median_fills=float(np.median(observed)), max_fills=int(observed.max()),
                                        max_consecutive_observed_zero_sessions=maximum_zero_streak(daily),
                                        meets_new_gate_all_available=bool((observed > 0).all()),
                                        full_calendar_gate='NO_EVALUABLE_MISSING_SOURCE' if any(count is None for count in daily)
                                        else 'PASS' if (observed > 0).all() else 'FAIL_ZERO_TRADE_DAY'))
    pd.DataFrame(policy_rows).to_csv(output / 'original_policy_coverage.csv', index=False)
    pd.DataFrame(policy_days).to_csv(output / 'original_policy_daily_counts.csv', index=False)
    summary = dict(status='DAILY_TRADE_FEASIBILITY_DIAGNOSTIC_COMPLETE', expected_days_per_ticker=len(calendar),
                   expected_ticker_days=len(index), feasibility_counts=dict(Counter(availability.feasibility)),
                   filled_entry_actions=int(availability.filled_entries.sum()),
                   no_filled_entry_available_days=availability.loc[availability.feasibility.isin(
                       ['OBSERVED_ACTIONS_NO_FILLED_ENTRY', 'OBSERVED_NO_CAUSAL_ACTION']), ['ticker', 'date', 'feasibility']].to_dict('records'),
                   by_ticker={ticker: dict(Counter(availability.loc[availability.ticker == ticker, 'feasibility'])) for ticker in ('QQQ', 'SPXW', 'SPY')},
                   original_policies=9, policy_ticker_split_rows=len(policy_rows), verified_ledger_hashes=verified_ledgers,
                   policies_passing_available_daily_gate_all_six_ticker_splits=[policy for policy in POLICIES if all(
                       row['meets_new_gate_all_available'] for row in policy_rows if row['policy'] == policy)],
                   index_sha256=sha(index_path), calendar_sha256=sha(calendar_path), ledger_audit_sha256=sha(audit_path),
                   code_sha256=sha(Path(__file__)), source_artifact_hashes='Reported by audited index; not rehashed in this diagnostic',
                   columns=dict(index=list(INDEX_COLUMNS), labels=list(LABEL_COLUMNS), actions=list(ACTION_COLUMNS), states=list(STATE_COLUMNS),
                                ledgers=['ticker', 'date', 'status']),
                   pnl_columns_read=False, policy_changed=False, post_result_new_gate=True,
                   entry_existence_is_hindsight_feasibility_not_a_policy=True,
                   completed_utc=datetime.now(timezone.utc).isoformat(), wall_seconds=time.perf_counter() - started)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (output / 'daily_trade_feasibility.executed.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    assert maximum_zero_streak([0, 0, None, 0, 1, 0]) == 2
    main()
