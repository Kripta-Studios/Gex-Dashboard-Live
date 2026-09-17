"""TIME-003 admission precondition, before raw features or economic artifacts.

A negative provenance conclusion is sufficient to stop. This module deliberately
does not issue a full feature/data-gate PASS from filenames or metadata.
"""
import json
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

from .artifacts import append_access, content_digest, digest, stage, write_json
from .contract import END, START, TICKERS, ContractError


def source_admission(manifest, provenance):
    schedule = xcals.get_calendar('XNYS', start=START, end=END).schedule.loc[START:END]
    days = []
    by_source = {(r.ticker, r.source_kind, r.trade_date, r.expiration): r
                 for r in manifest.itertuples()}
    generation = {(r['ticker'], r['trade_date']) for r in provenance['records'] if r['kind'] == 'generation'}
    repairs = {(r['ticker'], r['trade_date']) for r in provenance['records'] if r['kind'] in ('row_repair', 'gap_repair')}
    for day, row in schedule.iterrows():
        day = str(day.date())
        full = row['close'].tz_convert('America/New_York').strftime('%H:%M:%S') == '16:00:00'
        missing, uncertain = [], []
        for ticker in TICKERS:
            underlying = manifest[(manifest.ticker == ticker) & (manifest.source_kind == 'underlying')
                                  & (manifest.trade_date == day)]
            if len(underlying) != 1:
                missing.append(f'{ticker}/underlying')
            for kind in ('greeks', 'oi'):
                if (ticker, kind, day, day) not in by_source:
                    missing.append(f'{ticker}/{kind}/0DTE')
            # A script capable of in-place bfill cannot attest unrepaired vs repaired
            # rows, or bound replacement availability without a retained session record.
            if len(underlying) == 1 and (ticker, day) not in generation and (ticker, day) not in repairs:
                uncertain.append(ticker)
        reason = 'HALF_SESSION' if not full else ('MISSING_SOURCE' if missing else
                  ('UNDERLYING_PROVENANCE_UNRESOLVED' if uncertain else 'PROVENANCE_RECORD_REQUIRES_REVIEW'))
        # A recognized log is evidence to review, not automatic proof of all source invariants.
        days.append({'trade_date': day, 'month': day[:7].replace('-', ''),
                     'full_session': full, 'missing_sources': json.dumps(missing),
                     'unresolved_underlying_provenance': json.dumps(uncertain),
                     'source_reason': reason, 'feature_gate_admitted': False,
                     'expected_events_if_admitted': 54 if full else 0, 'events_constructed': 0})
    return pd.DataFrame(days), schedule


def build(inventory_dir, destination, contract_sha256, access_path):
    inventory_dir = Path(inventory_dir)
    summary = json.loads((inventory_dir / 'inventory_summary.json').read_text(encoding='utf-8'))
    if summary['contract_sha256'] != contract_sha256:
        raise ContractError('IO-001: inventory contract mismatch')
    for name, key in (('source_manifest.parquet', 'manifest_sha256'), ('provenance.json', 'provenance_sha256')):
        if digest(inventory_dir / name) != summary[key]:
            raise ContractError(f'IO-001: inventory hash mismatch: {name}')
    manifest = pd.read_parquet(inventory_dir / 'source_manifest.parquet')
    evidence = json.loads((inventory_dir / 'provenance.json').read_text(encoding='utf-8'))
    coverage, schedule = source_admission(manifest, evidence)
    unresolved = coverage[(coverage.full_session) & (coverage.unresolved_underlying_provenance != '[]')]
    missing = coverage[(coverage.full_session) & (coverage.missing_sources != '[]')]
    all_uncertain = len(unresolved) == int(coverage.full_session.sum())
    if not all_uncertain:
        # No generic PASS path: successful provenance alone cannot certify tensors.
        raise ContractError('Source provenance is not uniformly blocked; full semantic gate implementation required')
    with stage(destination) as directory:
        coverage.to_parquet(directory / 'coverage.parquet', index=False)
        schedule.reset_index().to_parquet(directory / 'calendar.parquet', index=False)
        monthly = []
        for month, group in coverage.groupby('month'):
            monthly.append({'month': month, 'initial_sessions': len(group),
                            'half_sessions': int((~group.full_session).sum()),
                            'missing_source_sessions': int(((group.missing_sources != '[]') & group.full_session).sum()),
                            'provenance_unresolved_sessions': int(((group.unresolved_underlying_provenance != '[]') & group.full_session).sum()),
                            'admitted_sessions': 0, 'events_constructed': 0,
                            'events_expected_before_source_admission': int(group.expected_events_if_admitted.sum())})
        result = {'execution_state': 'BLOCKED', 'economic_evidence_state': 'BLOCKED_DATA',
                  'reason': 'UNDERLYING_REPAIR_PROVENANCE_UNRESOLVED',
                  'gate_scope': 'source_provenance_precondition_only',
                  'feature_gate_executed': False, 'feature_gate_pass': False,
                  'contract_sha256': contract_sha256, 'inventory_summary_sha256': digest(inventory_dir / 'inventory_summary.json'),
                  'coverage_sha256': digest(directory / 'coverage.parquet'),
                  'coverage_content_sha256': content_digest(coverage.to_dict('records')),
                  'calendar_sha256': digest(directory / 'calendar.parquet'),
                  'initial_sessions': len(coverage), 'full_sessions': int(coverage.full_session.sum()),
                  'provenance_unresolved_full_sessions': len(unresolved),
                  'missing_source_full_sessions': len(missing), 'monthly': monthly,
                  'outcomes_opened': False, 'source_value_columns_read': [],
                  'technical_ready': False, 'promotion_approved': False,
                  'prospective_validation_state': 'NOT_STARTED',
                  'limitation': 'No repair is inferred from missing logs. Stored prices cannot establish their availability; no raw OHLC/Greek values were read.'}
        write_json(directory / 'data_gate_summary.json', result)
    append_access(access_path, stage='source_admission', purpose='provenance_precondition',
                  columns=[], time_range=[START, END], status='BLOCKED_DATA')
    return result
