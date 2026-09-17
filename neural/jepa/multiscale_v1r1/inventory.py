"""DATA-001: names, hashes, parquet footers, and local provenance text only."""
import re
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from .artifacts import append_access, content_digest, digest, stage, write_json
from .contract import TICKERS, ContractError

SOURCE_ROOT = Path('D:/ThetaData')
OPTION_NAME = re.compile(r'(SPXW|SPY|QQQ)_(\d{8})_(\d{8})_(greeks|iv|ohlc|oi)\.parquet')
UNDERLYING_NAME = re.compile(r'(SPXW|SPY|QQQ)_(\d{8})\.parquet')


def parse_name(path, kind):
    match = (UNDERLYING_NAME if kind == 'underlying' else OPTION_NAME).fullmatch(Path(path).name)
    if not match:
        raise ContractError(f'DATA-001: unrecognized name {Path(path).name}')
    if kind == 'underlying':
        ticker, day = match.groups()
        expiry = None
    else:
        ticker, expiry, day, named_kind = match.groups()
        if named_kind != kind:
            raise ContractError('DATA-001: directory/name kind mismatch')
        expiry = pd.Timestamp(expiry).date().isoformat()
    return ticker, pd.Timestamp(day).date().isoformat(), expiry


def source_paths(root):
    root = Path(root).resolve()
    for ticker in TICKERS:
        folders = [('underlying', root / 'data_underlying_derived' / ticker)]
        folders += [(k, root / 'data_options' / ticker / k) for k in ('greeks', 'iv', 'ohlc', 'oi')]
        for kind, folder in folders:
            for path in sorted(folder.rglob('*.parquet')):
                if not path.resolve().is_relative_to(folder.resolve()):
                    raise ContractError('DATA-001: source path escapes root')
                yield ticker, kind, path


def provenance(root):
    """Search all local names for retained underlying logs, never credentials/raw values.

    Text reads stay restricted to provenance filenames in the derived source root.
    Other potentially relevant log names are recorded for review, not silently used.
    """
    root = Path(root)
    scripts = []
    for name in ('script4_underlying_from_options.py', 'download_spot.py', 'script8_corrector.py', 'options_bulk.py'):
        path = root / name
        if path.is_file():
            scripts.append({'path': str(path.resolve()), 'sha256': digest(path)})
    logs, records = [], []
    for path in sorted((root / 'data_underlying_derived').rglob('*.log')):
        matches = [t for t in TICKERS if re.search(rf'(?:_|\b){t}(?:_|\.|\b)', path.name)]
        if not matches:
            continue
        ticker = matches[0]
        file_hash = digest(path)
        line_dates = []
        for number, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            # Only recognized generation/repair messages support any provenance claim.
            generation = re.search(rf'{ticker}_(\d{{8}}).*guardado.*Exp', line)
            repair = re.search(r'\[(CORRECCI.N FILA|REPARACI.N GAP)\].*?\|\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})', line)
            if generation:
                day = pd.Timestamp(generation[1]).date().isoformat()
                record = {'kind': 'generation', 'trade_date': day, 'bar_timestamp': None}
            elif repair:
                day = repair[2]
                record = {'kind': 'gap_repair' if 'GAP' in repair[1] else 'row_repair',
                          'trade_date': day, 'bar_timestamp': f'{day} {repair[3]}'}
            else:
                continue
            line_dates.append(day)
            record.update(ticker=ticker, path=str(path.resolve()), sha256=file_hash, line=number)
            records.append(record)
        logs.append({'path': str(path.resolve()), 'sha256': file_hash, 'ticker': ticker,
                     'recognized_records': len(line_dates),
                     'first_trade_date': min(line_dates) if line_dates else None,
                     'last_trade_date': max(line_dates) if line_dates else None})
    return {'scripts': scripts, 'logs': logs, 'records': records,
            'scope': 'all *.log under admitted derived root for SPXW/SPY/QQQ; explicit four scripts',
            'limitation': 'absence of a log does not prove a repair; current script is not historical lineage'}


def build_inventory(root, destination, contract_sha256, access_path):
    evidence = provenance(root)
    rows = []
    for ticker, kind, path in source_paths(root):
        named_ticker, day, expiry = parse_name(path, kind)
        if ticker != named_ticker:
            raise ContractError('DATA-001: ticker mismatch')
        before = path.stat()
        file_hash = digest(path)
        metadata = pq.ParquetFile(path)
        arrow_schema = metadata.schema_arrow
        schema_fields = [(f.name, str(f.type), f.nullable) for f in arrow_schema]
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ContractError('IO-001: source changed during inventory')
        refs = [f"{r['sha256']}:{r['line']}" for r in evidence['records']
                if r['ticker'] == ticker and r['trade_date'] == day] if kind == 'underlying' else []
        rows.append({'source_id': content_digest([ticker, kind, day, expiry, str(path.resolve())]),
                     'absolute_path': str(path.resolve()), 'source_kind': kind, 'ticker': ticker,
                     'trade_date': day, 'expiration': expiry, 'file_size': before.st_size,
                     'sha256': file_hash, 'schema_fingerprint': content_digest(schema_fields),
                     'schema_fields': schema_fields, 'row_count': metadata.metadata.num_rows,
                     'timestamp_storage_type': {f.name: str(f.type) for f in arrow_schema
                                                if 'timestamp' in f.name}, 'provenance_refs': refs})
        if len(rows) % 1000 == 0:
            print(f'inventory files={len(rows)}', flush=True)
    # Store nested metadata as canonical JSON strings so the parquet schema stays stable.
    from .artifacts import canonical
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ContractError('BLOCKED_DATA: no local source files')
    for column in ('schema_fields', 'timestamp_storage_type', 'provenance_refs'):
        frame[column] = frame[column].map(lambda v: canonical(v).decode('utf-8'))
    with stage(destination) as directory:
        frame.to_parquet(directory / 'source_manifest.parquet', index=False)
        write_json(directory / 'provenance.json', evidence)
        summary = {'status': 'INVENTORIED_NOT_ADMITTED', 'contract_sha256': contract_sha256,
                   'source_root': str(Path(root).resolve()), 'files': len(frame),
                   'bytes': int(frame.file_size.sum()), 'max_trade_date': frame.trade_date.max(),
                   'counts': {f'{t}/{k}': int(n) for (t, k), n in frame.groupby(['ticker', 'source_kind']).size().items()},
                   'manifest_sha256': digest(directory / 'source_manifest.parquet'),
                   'manifest_content_sha256': content_digest(frame.to_dict('records')),
                   'provenance_sha256': digest(directory / 'provenance.json'),
                   'logical_value_columns_read': [], 'outcomes_opened': False}
        write_json(directory / 'inventory_summary.json', summary)
    append_access(access_path, stage='inventory', purpose='names_hashes_footers_provenance',
                  columns=[], time_range=None, source_manifest_sha256=summary['manifest_sha256'])
    return summary
