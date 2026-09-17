"""Metadata-only recovery report; never reads market value columns."""
import hashlib
import json
import re
import shutil
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from .artifacts import digest, stage, write_json
from .contract import TICKERS
from .provenance import capture_documents


def recover(old_root, source_root, destination):
    old_root, source_root = Path(old_root), Path(source_root)
    evidence = json.loads((old_root / 'inventory/provenance.json').read_bytes())
    coverage = pd.read_parquet(old_root / 'data_gate/coverage.parquet')
    manifest = pd.read_parquet(old_root / 'inventory/source_manifest.parquet')
    repo = Path(__file__).resolve().parents[3]
    sealed_catalog = json.loads((repo / 'research_papers/JEPA/multiscale_v1r1/evidence/artifact_catalog.json').read_bytes())
    expected_hashes = {str(Path(r['path']).resolve()): r['sha256'] for r in sealed_catalog['artifacts']}
    # Fixed search by names/extensions, never by any price or economic outcome.
    candidates, counts = [], {}
    for tree in ('data_options', 'data_underlying_derived'):
        directory = source_root / tree
        for path in directory.rglob('*'):
            if not path.is_file():
                continue
            relative = path.relative_to(directory)
            if len(relative.parts) > 1 and relative.parts[0] not in TICKERS:
                continue
            if len(relative.parts) == 1 and not any(re.search(r'(?:_|\b)' + t + r'(?:_|\.|\b)', path.name) for t in TICKERS):
                continue
            counts[(tree, path.suffix)] = counts.get((tree, path.suffix), 0) + 1
            if path.suffix.lower() in ('.log', '.bak', '.old', '.gz', '.zip', '.json', '.jsonl', '.csv'):
                candidates.append(path)
    with stage(destination) as output:
        preserved = output / 'previous_attempt'
        preserved.mkdir()
        old_files = [old_root / rel for rel in (
            'inventory/inventory_summary.json', 'inventory/provenance.json', 'inventory/source_manifest.parquet',
            'data_gate/data_gate_summary.json', 'data_gate/coverage.parquet', 'closure/evaluation_summary.json',
            'closure/audit_summary.json', 'audit_attempt_01.json', 'audit_attempt_02.json', 'audit_attempt_03.json')]
        copies = []
        for i, path in enumerate(old_files):
            checksum = digest(path)
            if expected_hashes.get(str(path.resolve())) != checksum:
                raise ValueError('Recovery: original terminal artifact does not match published catalog')
            target = preserved / f'{i:02d}_{path.name}'
            shutil.copyfile(path, target)
            if digest(target) != checksum or digest(path) != checksum:
                raise ValueError('Recovery: terminal artifact changed during preservation')
            copies.append(dict(original=str(path), preserved=str(target.relative_to(output)), sha256=checksum))
        records = []
        for source in evidence['scripts'] + evidence['logs']:
            original = Path(source['path'])
            observed = digest(original) if original.exists() else None
            match = original if observed == source['sha256'] else None
            examined = []
            if match is None:
                # Only plausible log rotations/backups of this specific source.
                for candidate in candidates:
                    if candidate == original or original.stem not in candidate.name:
                        continue
                    checksum = digest(candidate)
                    examined.append(dict(path=str(candidate), sha256=checksum))
                    if checksum == source['sha256']:
                        match = candidate
                        break
            prefix_size = source.get('bytes', source.get('file_size'))
            method = 'EXACT_FILE_SHA256' if match else 'LOCAL_ROTATION_SEARCH'
            if match is None and prefix_size is not None and original.exists():
                with original.open('rb') as handle:
                    prefix = handle.read(prefix_size)
                if len(prefix) == prefix_size and hashlib.sha256(prefix).hexdigest() == source['sha256']:
                    recovered = output / f'recovered_{original.name}'
                    recovered.write_bytes(prefix)
                    match, method = recovered, 'SEALED_SIZE_PREFIX_EXACT_SHA256'
            records.append(dict(artifact=source['path'], expected_sha256=source['sha256'],
                                observed_sha256=observed, method=method,
                                result='ORIGINAL_BYTES_RECOVERED' if match else 'ORIGINAL_EVIDENCE_NOT_RECOVERED',
                                recovered_path=str(match) if match else None, examined_candidates=examined,
                                original_size_available=prefix_size is not None,
                                limitation='No prefix inference without sealed size; no reconstruction from recognized keys.'))
        snapshot_status = 'NOT_CAPTURED'
        one_second_documentary_matches = []
        # Snapshot current documentary sources, explicitly NOT recovery of old bytes.
        documentary = [p for p in candidates if p.suffix.lower() in ('.log', '.json', '.csv')]
        try:
            captured = capture_documents(documentary, output / 'current_documents')
            from neural.jepa.multiscale_v1r1_audit.snapshot import verify_snapshot
            texts = verify_snapshot(captured.parent, digest(captured))
            one_second_documentary_matches = [name for name, text in texts.items()
                                               if re.search(r'interval[=: ]+1s\b', text)]
            snapshot_status = 'NEW_DOCUMENTARY_SNAPSHOT_VERIFIED'
        except ValueError as error:
            snapshot_status = str(error)
        missing = []
        lineage = []
        for row in coverage.itertuples():
            for item in json.loads(row.missing_sources):
                if row.full_session:
                    ticker, kind, *_ = item.split('/')
                    missing.append(dict(trade_date=row.trade_date, month=row.month, ticker=ticker, source_kind=kind,
                                        expected_expiration=row.trade_date if kind != 'underlying' else None))
            for ticker in TICKERS:
                rows = manifest[(manifest.trade_date == row.trade_date) & (manifest.ticker == ticker)]
                underlying = rows[rows.source_kind == 'underlying']
                lineage.append(dict(ticker=ticker, trade_date=row.trade_date, month=row.month,
                                    full_session=bool(row.full_session),
                                    classification='UNVERIFIABLE_FOR_CAUSAL_REPLAY' if len(underlying) else 'MISSING_SOURCE',
                                    reason='No recovered per-bar transformation/availability witness',
                                    input_sha256=underlying.sha256.tolist(),
                                    input_paths=underlying.absolute_path.tolist(), transformation_sha256=None,
                                    transformation_parameters=None, event_interval=row.trade_date + ' RTH',
                                    available_at=None, availability_bound=None, received_at=None,
                                    materialized_at=None, repair_kind=None, repair_dependency=None,
                                    evidence='Original source inventory; documentary inspection only'))
        intervals = {}
        spxw = manifest[(manifest.ticker == 'SPXW') & (manifest.source_kind == 'greeks')]
        for record in spxw.itertuples():
            metadata = pq.read_metadata(record.absolute_path)
            observed = set()
            for group in range(metadata.num_row_groups):
                block = metadata.row_group(group)
                for column in range(block.num_columns):
                    chunk = block.column(column)
                    if chunk.path_in_schema == 'interval_used' and chunk.statistics and chunk.statistics.has_min_max:
                        observed.update((str(chunk.statistics.min), str(chunk.statistics.max)))
            key = '|'.join(sorted(observed)) or 'FOOTER_STATISTICS_UNAVAILABLE'
            intervals[key] = intervals.get(key, 0) + 1
        pd.DataFrame(lineage).to_parquet(output / 'lineage.parquet', index=False)
        monthly = pd.DataFrame(lineage).groupby(['ticker', 'month', 'classification']).size().reset_index(name='sessions')
        monthly.to_parquet(output / 'lineage_coverage.parquet', index=False)
        write_json(output / 'missing_sources.json', dict(full_dates=len({r['trade_date'] for r in missing}),
                                                        missing_source_records=missing, counts_overlap_provenance_block=True))
        report = dict(status='RECOVERY_EXAMINED', evidence_recovery=records, preserved_artifacts=copies,
                      new_snapshot=snapshot_status,
                      name_inventory={tree + '/' + suffix: count for (tree, suffix), count in counts.items()},
                      spxw_greek_interval_footer_statistics=intervals,
                      exact_interval_1s_matches_in_captured_documents=one_second_documentary_matches,
                      market_value_columns_read=[], historical_economics='NOT_EVALUATED',
                      original_attempt_state='INVALIDATED/FAILED_AUDIT', promotion_approved=False)
        write_json(output / 'evidence_recovery.json', report)
    return report
