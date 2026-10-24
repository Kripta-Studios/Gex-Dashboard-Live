"""Local-only, non-economic daily option-chain cache for level research.

No raw source is modified. Arrays preserve missingness and stored prices in
float64; availability assumptions live in metadata rather than fabricated raw
clock fields. Existing caches resume only after checking code, raw and NPZ hashes.
"""
from __future__ import annotations

# Native thread limits must be set before importing NumPy/Arrow in spawned workers.
# ruff: noqa: E402

import os

for _thread_var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                    'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[_thread_var] = '1'

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import uuid

import exchange_calendars as xc
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path('D:/ThetaData/data_options')
OUT = Path('D:/GexResearchArtifacts/level_oracle_20261018/cache_v1')
TICKERS = ('SPXW', 'SPY', 'QQQ')
VERSION = 'LEVEL_DAILY_CACHE_V1'
PRICES = ('bid', 'ask', 'delta', 'iv', 'vega', 'theta')
GREEK_COLUMNS = ('symbol', 'expiration', 'trade_date', 'strike', 'right',
                 'timestamp', 'underlying_timestamp', 'underlying_price',
                 'bid', 'ask', 'delta', 'implied_vol', 'vega', 'theta')
OI_COLUMNS = ('symbol', 'expiration', 'trade_date', 'strike', 'right',
              'timestamp', 'open_interest')
NAT = np.iinfo(np.int64).min


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict | list) -> None:
    temporary = path.with_name(path.name + '.partial-' + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)


def parse_time(values: pd.Series) -> pd.Series:
    result = pd.to_datetime(values, format='ISO8601', errors='coerce')
    if not pd.api.types.is_datetime64_any_dtype(result.dtype) or result.dt.tz is not None:
        raise ValueError('Expected naive source clocks interpreted as America/New_York')
    return result.astype('datetime64[ns]')


def identity(frame: pd.DataFrame, ticker: str, day: pd.Timestamp) -> tuple[pd.DataFrame, int]:
    result = frame.copy()
    result['_right'] = result.right.astype(str).str.upper().replace({'C': 'CALL', 'P': 'PUT'}).map({'CALL': 0, 'PUT': 1})
    result['strike'] = pd.to_numeric(result.strike, errors='coerce')
    expiration = parse_time(result.expiration.astype(str)).dt.normalize()
    trade_date = parse_time(result.trade_date.astype(str)).dt.normalize()
    valid = ((result.symbol == ticker) & (expiration == day) & (trade_date == day)
             & result._right.notna() & np.isfinite(result.strike) & (result.strike > 0))
    result = result.loc[valid].copy()
    result['_right'] = result._right.astype(np.int8)
    return result, int((~valid).sum())


def normalize_day(greek: pd.DataFrame, oi: pd.DataFrame, ticker: str, date: str):
    """Pure transformation; all minute rows and all valid OI identities retained."""
    day = pd.Timestamp(date).normalize()
    time = pd.date_range(day + pd.Timedelta(hours=9, minutes=30), periods=391, freq='min')
    time_ns = time.as_unit('ns').asi8
    g, bad_g_identity = identity(greek, ticker, day)
    o, bad_o_identity = identity(oi, ticker, day)
    native_clock = 'timestamp' in g.columns
    g['_time'] = parse_time(g.timestamp if native_clock else g.underlying_timestamp)
    g['_underlying_time'] = parse_time(g.underlying_timestamp)
    valid_time = ((g._time.dt.normalize() == day) & (g._time == g._time.dt.floor('min'))
                  & g._time.between(time[0], time[-1]))
    bad_g_clock = int((~valid_time).sum())
    g = g.loc[valid_time].copy()
    if g.duplicated(['strike', '_right', '_time'], keep=False).any():
        raise ValueError('Ambiguous duplicate Greek contract/timestamp; no deduplication')
    if g.empty:
        raise ValueError('No valid Greek identity/clock rows')
    native_oi_clock = 'timestamp' in o.columns
    o['_available'] = parse_time(o.timestamp) if native_oi_clock else time[0]
    keys = sorted(set(zip(g.strike, g._right)) | set(zip(o.strike, o._right)))
    key_index = {key: idx for idx, key in enumerate(keys)}
    contract = np.fromiter((key_index[key] for key in zip(g.strike, g._right)), dtype=np.int32)
    minute = ((g._time.astype('int64').to_numpy() - time_ns[0]) // 60_000_000_000).astype(np.int32)
    shape = (391, len(keys))
    arrays = {'time_ns': time_ns, 'strike': np.array([k[0] for k in keys], dtype=np.float64),
              'right': np.array([k[1] for k in keys], dtype=np.int8)}
    for name in PRICES:
        matrix = np.full(shape, np.nan, dtype=np.float64)
        source_column = 'implied_vol' if name == 'iv' else name
        matrix[minute, contract] = pd.to_numeric(g[source_column], errors='coerce').to_numpy(dtype=np.float64)
        arrays[name] = matrix
    flags = np.zeros(shape, dtype=np.uint8)
    flags[minute, contract] = 1
    bid, ask = arrays['bid'][minute, contract], arrays['ask'][minute, contract]
    quote_valid = np.isfinite(bid) & np.isfinite(ask) & (bid >= 0) & (ask > 0) & (bid <= ask)
    flags[minute[quote_valid], contract[quote_valid]] |= 2
    ages = (g._time - g._underlying_time).dt.total_seconds().to_numpy(dtype=np.float64) * 1000
    raw_spot = pd.to_numeric(g.underlying_price, errors='coerce').to_numpy(dtype=np.float64)
    good_spot = np.isfinite(raw_spot) & (raw_spot > 0) & np.isfinite(ages) & (ages >= 0) & (ages <= 60000)
    flags[minute[good_spot], contract[good_spot]] |= 4
    arrays['row_flags'] = flags
    low = np.full(391, np.inf)
    high = np.full(391, -np.inf)
    np.minimum.at(low, minute[good_spot], raw_spot[good_spot])
    np.maximum.at(high, minute[good_spot], raw_spot[good_spot])
    spot_valid = np.isfinite(low) & (low == high)
    arrays['spot'] = np.where(spot_valid, low, np.nan).astype(np.float64)
    arrays['spot_valid'] = spot_valid
    if not np.all(ages == 0):
        age_matrix = np.full(shape, np.nan, dtype=np.float64)
        age_matrix[minute, contract] = ages
        arrays['underlying_age_ms'] = age_matrix
    o = o.sort_values(['_available', 'strike', '_right'], kind='stable', na_position='last')
    oi_values = pd.to_numeric(o.open_interest, errors='coerce').to_numpy(dtype=np.float64)
    numeric_oi_valid = (np.isfinite(oi_values) & (oi_values >= 0) & (oi_values < 2**63)
                        & (oi_values == np.floor(oi_values)))
    oi_valid = numeric_oi_valid & (o._available.dt.normalize() == day).to_numpy()
    duplicate_oi = o.duplicated(['strike', '_right', '_available'], keep=False).to_numpy()
    oi_valid &= ~duplicate_oi
    arrays['oi_contract_idx'] = np.fromiter((key_index[key] for key in zip(o.strike, o._right)), dtype=np.int32)
    arrays['oi_value'] = np.where(numeric_oi_valid, oi_values, -1).astype(np.int64)
    arrays['oi_available_ns'] = o._available.astype('int64').to_numpy(dtype=np.int64)
    arrays['oi_valid'] = oi_valid.astype(bool)
    counters = {'source_greek_rows': len(greek), 'source_oi_rows': len(oi),
                'valid_identity_clock_greek_rows': len(g), 'invalid_greek_identity_rows': bad_g_identity,
                'invalid_greek_clock_rows': bad_g_clock, 'invalid_oi_identity_rows': bad_o_identity,
                'retained_oi_records': len(o), 'invalid_oi_records': int((~oi_valid).sum()),
                'duplicate_oi_records': int(duplicate_oi.sum()), 'invalid_quote_rows': int((~quote_valid).sum()),
                'invalid_spot_rows': int((~good_spot).sum()), 'valid_spot_minutes': int(spot_valid.sum()),
                'inconsistent_spot_minutes': int((np.isfinite(low) & (low != high)).sum()),
                'absent_cells': int(np.count_nonzero(flags == 0)), 'contracts': len(keys),
                'paired_clock_mismatch_rows': int(np.count_nonzero(ages != 0)) if native_clock else None}
    metadata = {'version': VERSION, 'ticker': ticker, 'date': date, 'timezone_convention': 'America/New_York naive',
                'clock_basis': 'NATIVE_STORED_TIMESTAMP' if native_clock else 'ASSUMED_UNDERLYING_SNAPSHOT_CLOCK',
                'oi_clock_basis': 'NATIVE_STORED_TIMESTAMP' if native_oi_clock else 'ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT',
                'oi_assumed_availability': None if native_oi_clock else str(time[0]),
                'clock_delay_applied': False, 'contract_order': 'union Greek+OI, sorted(strike,right), CALL=0 PUT=1',
                'row_flags': {'present': 1, 'valid_quote': 2, 'valid_spot_row': 4},
                'spot_rule': 'consensus of finite positive source rows with underlying age between 0 and 60 seconds; no fill',
                'feature_float_precision': 'float64; no downcast', 'counters': counters,
                'uncompressed_array_bytes': sum(value.nbytes for value in arrays.values()),
                'array_schema': {key: {'shape': list(value.shape), 'dtype': str(value.dtype)} for key, value in arrays.items()}}
    return arrays, metadata


def read_day_metadata(path: Path) -> dict:
    return json.loads(Path(path).with_suffix('.json').read_text(encoding='utf-8'))


def load_day_cache(path: Path) -> dict[str, np.ndarray]:
    path = Path(path)
    metadata = read_day_metadata(path)
    if metadata['version'] != VERSION or sha256(path) != metadata['sha256']:
        raise ValueError(f'Cache version/hash mismatch: {path}')
    with np.load(path, allow_pickle=False) as stored:
        arrays = {key: stored[key] for key in stored.files}
    if set(arrays) != set(metadata['array_schema']):
        raise ValueError(f'Cache array names mismatch: {path}')
    for key, array in arrays.items():
        descriptor = metadata['array_schema'][key]
        if list(array.shape) != descriptor['shape'] or str(array.dtype) != descriptor['dtype']:
            raise ValueError(f'Cache array shape/dtype mismatch: {path}:{key}')
    return arrays


def source_path(root: Path, ticker: str, date: str, kind: str) -> Path:
    return root / ticker / kind / date[:4] / date[4:6] / f'{ticker}_{date}_{date}_{kind}.parquet'


def source_record(path: Path) -> dict:
    before = path.stat()
    digest = sha256(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f'Source changed during hashing: {path}')
    return {'sha256': digest, 'bytes': after.st_size, 'mtime_ns': after.st_mtime_ns}


def build_day(task: dict) -> dict:
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    root, out = Path(task['source_root']), Path(task['out'])
    ticker, date, producer = task['ticker'], task['date'], task['producer_sha256']
    greek_path, oi_path = (source_path(root, ticker, date, kind) for kind in ('greeks', 'oi'))
    record = {'ticker': ticker, 'date': date, 'greek_exists': greek_path.exists(), 'oi_exists': oi_path.exists()}
    if not record['greek_exists'] or not record['oi_exists']:
        return {**record, 'status': 'MISSING_SOURCE', 'npz_bytes': 0}
    target = out / ticker / f'{date}.npz'
    metadata_path = target.with_suffix('.json')
    sources = {str(path): source_record(path) for path in (greek_path, oi_path)}
    if target.exists() or metadata_path.exists():
        if not target.exists() or not metadata_path.exists():
            raise ValueError(f'Incomplete cache pair; not trusted for resume: {target}')
        metadata = read_day_metadata(target)
        if metadata['producer_sha256'] != producer or metadata['source_hashes'] != sources:
            raise ValueError(f'Code/raw metadata mismatch during resume: {target}')
        load_day_cache(target)
        return {**record, 'status': 'VERIFIED_EXISTING', 'npz_bytes': target.stat().st_size,
                'uncompressed_array_bytes': metadata['uncompressed_array_bytes'], 'sha256': metadata['sha256']}
    frames = []
    for path, requested in ((greek_path, GREEK_COLUMNS), (oi_path, OI_COLUMNS)):
        schema = pq.read_schema(path)
        required = set(requested) - {'timestamp'}
        if required - set(schema.names):
            raise ValueError(f'Missing required columns in {path}: {sorted(required - set(schema.names))}')
        frames.append(pq.read_table(path, columns=[name for name in requested if name in schema.names], use_threads=False).to_pandas(use_threads=False))
    arrays, metadata = normalize_day(frames[0], frames[1], ticker, date)
    del frames
    # Rehash after projected reading: the cache cannot silently mix changed raw.
    for path in (greek_path, oi_path):
        if source_record(path) != sources[str(path)]:
            raise ValueError(f'Source changed during read: {path}')
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.partial-' + uuid.uuid4().hex)
    with temporary.open('xb') as handle:
        np.savez_compressed(handle, **arrays)
    digest = sha256(temporary)
    metadata.update({'source_hashes': sources, 'producer_sha256': producer,
                     'sha256': digest, 'npz_bytes': temporary.stat().st_size,
                     'calendar': task.get('calendar', {}),
                     'created_at_utc': datetime.now(timezone.utc).isoformat()})
    os.replace(temporary, target)
    write_json(metadata_path, metadata)
    return {**record, 'status': 'BUILT', 'npz_bytes': target.stat().st_size,
            'uncompressed_array_bytes': metadata['uncompressed_array_bytes'], 'sha256': digest,
            'clock_basis': metadata['clock_basis'], 'oi_clock_basis': metadata['oi_clock_basis']}


def session_calendar() -> pd.DataFrame:
    calendar = xc.get_calendar('XNYS').schedule.loc['2023-01-03':'2026-06-30'].copy()
    calendar['date'] = calendar.index.strftime('%Y%m%d')
    calendar['full_session'] = (calendar['close'] - calendar['open']) == pd.Timedelta(hours=6, minutes=30)
    return calendar


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--mode', choices=['pilot', 'full'], default='pilot')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    parser.add_argument('--max-gib', type=float, default=20)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    producer_path = Path(__file__).resolve()
    producer = sha256(producer_path)
    contract_path = args.out / 'cache_contract.json'
    contract = {'version': VERSION, 'producer_sha256': producer, 'source_root': str(args.source_root.resolve()),
                'start': '20230103', 'end': '20260630', 'tickers': list(TICKERS),
                'max_gib': args.max_gib, 'calendar_library': xc.__version__,
                'thread_limit_per_worker': 1, 'models_or_outcomes_generated': False}
    if contract_path.exists():
        if json.loads(contract_path.read_text(encoding='utf-8')) != contract:
            raise ValueError('Existing cache contract/code differs; use a new output root')
    else:
        write_json(contract_path, contract)
        shutil.copy2(producer_path, args.out / 'build_cache.executed.py')
    if sha256(args.out / 'build_cache.executed.py') != producer:
        raise ValueError('Executed producer snapshot hash mismatch')
    calendar = session_calendar()
    calendar.to_csv(args.out / 'expected_calendar.csv', index=False)
    full = calendar.loc[calendar.full_session]
    if len(full) != 867:
        raise ValueError(f'Expected 867 full sessions, got {len(full)}')
    selected = full.iloc[:1] if args.mode == 'pilot' else full
    tasks = [{'ticker': ticker, 'date': row.date, 'producer_sha256': producer,
              'source_root': str(args.source_root), 'out': str(args.out),
              'calendar': {'open_utc': str(row.open), 'close_utc': str(row.close), 'full_session': True}}
             for ticker in TICKERS for row in selected.itertuples()]
    if shutil.disk_usage(args.out).free < 2 * 1024**3:
        raise ValueError('Less than 2 GiB free disk space')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
    run_dir = args.out / 'runs'
    run_dir.mkdir(exist_ok=True)
    records = []
    size = 0
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        for idx, record in enumerate(executor.map(build_day, tasks, chunksize=1)):
            records.append(record)
            size += record['npz_bytes']
            if size > args.max_gib * 1024**3:
                raise ValueError('Compressed cache exceeds declared disk budget')
            if idx % 25 == 0 or idx == len(tasks) - 1:
                progress = {'run_id': run_id, 'mode': args.mode, 'completed': len(records), 'expected': len(tasks),
                            'compressed_bytes': size, 'last': record, 'status': 'RUNNING'}
                write_json(args.out / 'progress.json', progress)
                print(json.dumps(progress), flush=True)
    coverage = pd.DataFrame(records)
    coverage.to_csv(run_dir / f'{run_id}_coverage.csv', index=False)
    coverage.to_csv(args.out / f'{args.mode}_coverage.csv', index=False)
    summary = {'run_id': run_id, 'mode': args.mode, 'status': 'COMPLETE', 'expected': len(tasks),
               'built': int((coverage.status == 'BUILT').sum()),
               'verified_existing': int((coverage.status == 'VERIFIED_EXISTING').sum()),
               'missing_sources': int((coverage.status == 'MISSING_SOURCE').sum()),
               'compressed_bytes': size, 'uncompressed_array_bytes': sum(r.get('uncompressed_array_bytes', 0) for r in records),
               'producer_sha256': producer, 'models_or_outcomes_generated': False}
    write_json(run_dir / f'{run_id}_summary.json', summary)
    write_json(args.out / f'{args.mode}_summary.json', summary)
    write_json(args.out / 'progress.json', summary)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
