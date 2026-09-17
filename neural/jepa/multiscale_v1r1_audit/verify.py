"""Separate reconstruction of filenames, footer metadata, lineage and coverage.

This auditor certifies a failed source-admission precondition only. It does not
certify a feature dataset, model, economic result, or historical/live parity.
"""
import hashlib
import json
import re
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd
import pyarrow.parquet as pq


def sha(path):
    accumulator = hashlib.sha256()
    with Path(path).open('rb') as file:
        while chunk := file.read(4 * 1024**2):
            accumulator.update(chunk)
    return accumulator.hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError('FAILED_AUDIT: ' + message)


def reconstruct_logs(root):
    entries = []
    for file in sorted((Path(root) / 'data_underlying_derived').rglob('*.log')):
        ticker = next((t for t in ('SPXW', 'SPY', 'QQQ') if re.search(r'(?:_|\b)' + t + r'(?:_|\.|\b)', file.name)), None)
        if ticker is None:
            continue
        checksum = sha(file)
        for index, line in enumerate(file.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            date, kind, bar = None, None, None
            if f'{ticker}_' in line and 'guardado' in line and 'Exp' in line:
                candidates = re.findall(ticker + r'_(\d{8})', line)
                if candidates:
                    date = pd.Timestamp(candidates[0]).strftime('%Y-%m-%d')
                    kind = 'generation'
            elif '[CORRECCI' in line or '[REPARACI' in line:
                match = re.search(r'\|\s*(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})', line)
                if match and ('N FILA]' in line or 'N GAP]' in line):
                    date = match[1]
                    bar = date + ' ' + match[2]
                    kind = 'gap_repair' if 'GAP]' in line else 'row_repair'
            if kind:
                entries.append({'kind': kind, 'trade_date': date, 'bar_timestamp': bar,
                                'ticker': ticker, 'path': str(file.resolve()), 'sha256': checksum, 'line': index})
    return entries


def audit(inventory_directory, gate_directory, contract, verify_sources=True):
    inv, gate = Path(inventory_directory), Path(gate_directory)
    inventory = json.loads((inv / 'inventory_summary.json').read_text(encoding='utf-8'))
    conclusion = json.loads((gate / 'data_gate_summary.json').read_text(encoding='utf-8'))
    require(inventory['contract_sha256'] == conclusion['contract_sha256'] == sha(contract), 'contract mismatch')
    require(sha(inv / 'source_manifest.parquet') == inventory['manifest_sha256'], 'manifest hash')
    require(sha(inv / 'provenance.json') == inventory['provenance_sha256'], 'provenance hash')
    require(sha(inv / 'inventory_summary.json') == conclusion['inventory_summary_sha256'], 'inventory summary hash')
    require(sha(gate / 'coverage.parquet') == conclusion['coverage_sha256'], 'coverage hash')
    require(sha(gate / 'calendar.parquet') == conclusion['calendar_sha256'], 'calendar hash')
    frame = pd.read_parquet(inv / 'source_manifest.parquet')
    require(canonical_sha(frame.to_dict('records')) == inventory['manifest_content_sha256'], 'manifest content hash')
    evidence = json.loads((inv / 'provenance.json').read_text(encoding='utf-8'))
    root = Path(inventory['source_root'])
    entries = reconstruct_logs(root)
    require(entries == evidence['records'], 'source log semantic reconstruction')
    for record in evidence['scripts'] + evidence['logs']:
        require(sha(record['path']) == record['sha256'], 'provenance source changed')
    paths, date_keys = set(), set()
    for ticker in ('SPXW', 'SPY', 'QQQ'):
        for kind in ('underlying', 'greeks', 'iv', 'ohlc', 'oi'):
            directory = (root / 'data_underlying_derived' / ticker if kind == 'underlying'
                         else root / 'data_options' / ticker / kind)
            for path in directory.rglob('*.parquet'):
                paths.add(str(path.resolve()))
    require(paths == set(frame.absolute_path), 'inventory missing or additional files')
    require(len(frame) == len(paths) == inventory['files'], 'inventory count/duplicate')
    for index, record in enumerate(frame.to_dict('records')):
        path = Path(record['absolute_path'])
        parts = path.stem.split('_')
        underlying = record['source_kind'] == 'underlying'
        expected_day = pd.Timestamp(parts[1] if underlying else parts[2]).strftime('%Y-%m-%d')
        expected_expiry = None if underlying else pd.Timestamp(parts[1]).strftime('%Y-%m-%d')
        require(parts[0] == record['ticker'] and expected_day == record['trade_date'], 'filename/session identity')
        require(expected_expiry == record['expiration'], 'expiration confused with trade date')
        if not underlying:
            require(parts[3] == record['source_kind'], 'source kind mismatch')
        date_keys.add((record['ticker'], record['source_kind'], expected_day, expected_expiry))
        expected_refs = [f"{r['sha256']}:{r['line']}" for r in entries
                         if r['ticker'] == record['ticker'] and r['trade_date'] == expected_day] if underlying else []
        require(json.loads(record['provenance_refs']) == expected_refs, 'lineage reference mismatch')
        if verify_sources:
            require(sha(path) == record['sha256'], 'raw byte hash changed')
            parquet = pq.ParquetFile(path)
            fields = [[field.name, str(field.type), field.nullable] for field in parquet.schema_arrow]
            require(fields == json.loads(record['schema_fields']), 'schema fields')
            require(canonical_sha(fields) == record['schema_fingerprint'], 'schema fingerprint')
            require(parquet.metadata.num_rows == record['row_count'], 'footer count')
            require(path.stat().st_size == record['file_size'], 'file size')
        if (index + 1) % 1000 == 0:
            print(f'audit sources={index + 1}', flush=True)
    require(int(frame.file_size.sum()) == inventory['bytes'], 'total byte count')
    schedule = xcals.get_calendar('XNYS', start='2022-08-01', end='2026-06-30').schedule.loc['2022-08-01':'2026-06-30']
    observed_schedule = pd.read_parquet(gate / 'calendar.parquet')
    pd.testing.assert_frame_equal(observed_schedule, schedule.reset_index())
    recorded_sessions = {(r['ticker'], r['trade_date']) for r in entries}
    expected = []
    for date, clocks in schedule.iterrows():
        day = date.strftime('%Y-%m-%d')
        full = clocks['close'].tz_convert('America/New_York').hour == 16
        missing, uncertain = [], []
        for ticker in ('SPXW', 'SPY', 'QQQ'):
            if (ticker, 'underlying', day, None) not in date_keys:
                missing.append(ticker + '/underlying')
            elif (ticker, day) not in recorded_sessions:
                uncertain.append(ticker)
            for kind in ('greeks', 'oi'):
                if (ticker, kind, day, day) not in date_keys:
                    missing.append(f'{ticker}/{kind}/0DTE')
        reason = ('HALF_SESSION' if not full else 'MISSING_SOURCE' if missing else
                  'UNDERLYING_PROVENANCE_UNRESOLVED' if uncertain else 'PROVENANCE_RECORD_REQUIRES_REVIEW')
        expected.append(dict(trade_date=day, month=day[:7].replace('-', ''), full_session=full,
                             missing_sources=json.dumps(missing), unresolved_underlying_provenance=json.dumps(uncertain),
                             source_reason=reason, feature_gate_admitted=False,
                             expected_events_if_admitted=54 if full else 0, events_constructed=0))
    actual = pd.read_parquet(gate / 'coverage.parquet')
    require(actual.to_dict('records') == expected, 'coverage semantic reconstruction')
    require(canonical_sha(expected) == conclusion['coverage_content_sha256'], 'coverage content')
    full_count = sum(r['full_session'] for r in expected)
    unresolved = sum(r['full_session'] and r['unresolved_underlying_provenance'] != '[]' for r in expected)
    require(full_count == unresolved == conclusion['provenance_unresolved_full_sessions'], 'blocker not universal')
    require(conclusion['full_sessions'] == full_count and conclusion['initial_sessions'] == len(expected), 'summary session counts')
    require(conclusion['economic_evidence_state'] == 'BLOCKED_DATA'
            and conclusion['reason'] == 'UNDERLYING_REPAIR_PROVENANCE_UNRESOLVED', 'wrong terminal classification')
    require(conclusion['feature_gate_executed'] is False and conclusion['promotion_approved'] is False
            and conclusion['outcomes_opened'] is False, 'overstated gate/economic state')
    # Validate reader access sequence itself rather than trusting summary flags alone.
    log = inv.parent / 'access_log.jsonl'
    previous = '0' * 64
    stages = []
    for index, line in enumerate(log.read_text(encoding='utf-8').splitlines()):
        event = json.loads(line)
        checksum = event.pop('record_sha256')
        require(event['sequence'] == index and event['previous_sha256'] == previous, 'access order')
        require(canonical_sha(event) == checksum, 'access chain')
        require(event['columns'] == [] and event['stage'] in ('inventory', 'source_admission'), 'premature value/outcome access')
        previous = checksum
        stages.append(event['stage'])
    require(stages == ['inventory', 'source_admission'], 'unexpected admission transitions')
    return {'status': 'PASS_INDEPENDENT_AUDIT_OF_BLOCKED_SOURCE_ADMISSION',
            'scope': 'negative source-provenance precondition only; no feature or economic audit',
            'sources_rehashed': len(frame) if verify_sources else 0,
            'source_values_read': False, 'outcomes_opened': False,
            'coverage_sessions_reconstructed': len(expected), 'mismatches': 0,
            'gate_summary_sha256': sha(gate / 'data_gate_summary.json'),
            'access_log_sha256': sha(log), 'promotion_approved': False}
