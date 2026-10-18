"""Build the prepared 35-channel episode variant from audited causal tables only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid

for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '1'

import numpy as np  # noqa: E402
import psutil  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

try:
    from . import episode_features as ef
except ImportError:
    import episode_features as ef

VERSION = 'PREPARED_CAUSAL_EPISODES_V1'
EPISODE_SHA = '437530a63c2ef412414101552120b8a04e74e63375c65c6b409293bb7fd4d5a4'
INDEX_SHA = '8d0c6e27bdaf7d47ef2a9888505294b8f3186da3a6927e780ce9e517e660e8e5'
AUDIT_SHA = 'cbbe61d0a3fa7619447b7301d4c4b2fd52c487e11450d4904efee381fc3bf22d'
INDEX_COLUMNS = ('ticker', 'date', 'split', 'status', 'day_root', 'states_sha256', 'levels_sha256')
STATE_COLUMNS = ('state_i', 'state_valid', 'spot', 'band', 'eligible', 'entry_level_id', 'ib_low', 'ib_range')
LEVEL_COLUMNS = ('state_i', 'level_id', 'center', 'source_mask', 'n_components', 'components_json')


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(part)
    return result.hexdigest()


def write_json(path, value):
    temporary = path.with_name(path.name + '.partial-' + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def metadata_string(raw, key):
    # Consume only metadata string fields of an audit document that also has
    # economic fields; those fields are neither decoded nor exposed here.
    match = re.search(r'"' + re.escape(key) + r'"\s*:\s*("(?:[^"\\]|\\.)*")', raw)
    if match is None:
        raise ValueError('Missing authority metadata: ' + key)
    return json.loads(match.group(1))


def validate_arrays(arrays):
    if set(arrays) != {'state_i', 'values', 'valid'}:
        raise ValueError('Episode array names differ')
    if arrays['state_i'].dtype != np.int64 or not np.array_equal(arrays['state_i'], np.arange(60, 376)):
        raise ValueError('Episode decision keys differ')
    if arrays['values'].shape != (316, 35) or arrays['values'].dtype != np.float64:
        raise ValueError('Episode numeric schema differs')
    if arrays['valid'].shape != (316, 35) or arrays['valid'].dtype != bool:
        raise ValueError('Episode mask schema differs')
    if not np.isfinite(arrays['values']).all() or np.any(arrays['values'][~arrays['valid']] != 0):
        raise ValueError('Episode finiteness/placeholder invariant failed')
    if not arrays['valid'][:, :2].all():
        raise ValueError('Episode/current-zone availability must always be observed')


def verify_day(target, binding):
    metadata = read_json(target.with_suffix('.json'))
    if metadata['binding'] != binding or metadata['version'] != VERSION or metadata['names'] != list(ef.FEATURE_NAMES):
        raise ValueError('Episode output binding/schema differs')
    if sha(target) != metadata['sha256']:
        raise ValueError('Episode output hash differs')
    with np.load(target, allow_pickle=False) as stored:
        arrays = {name: stored[name] for name in stored.files}
    validate_arrays(arrays)
    descriptors = {name: dict(shape=list(value.shape), dtype=str(value.dtype)) for name, value in arrays.items()}
    if metadata['array_schema'] != descriptors or metadata['states'] != len(arrays['state_i']):
        raise ValueError('Episode manifest shape/count differs')
    if metadata['observed_values'] != int(arrays['valid'].sum()) or metadata['episode_open_rows'] != int(arrays['values'][:, 0].sum()):
        raise ValueError('Episode manifest technical counters differ')
    return metadata


def preserve_partial(day, output):
    target, metadata = day / 'episodes.npz', day / 'episodes.json'
    partials = list(day.glob('episodes.*.partial-*')) if day.exists() else []
    if target.exists() != metadata.exists():
        partials += [path for path in (target, metadata) if path.exists()]
    if not partials:
        return
    archive = output / '_preserved_partials' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '_' + uuid.uuid4().hex)
    archive.mkdir(parents=True)
    moves = []
    for path in partials:
        resolved = path.resolve()
        if not resolved.is_relative_to(output.resolve()):
            raise ValueError('Partial is outside the output root')
        destination = archive / resolved.relative_to(output.resolve())
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = sha(resolved)
        os.replace(resolved, destination)
        moves.append(dict(original=str(resolved), preserved=str(destination), sha256=digest))
    write_json(archive / 'manifest.json', dict(reason='INCOMPLETE_PUBLICATION_PRESERVED_BEFORE_RESUME', files=moves))


def process_day(row, output, contract):
    ticker, date = row['ticker'], row['date']
    if ticker not in ('QQQ', 'SPXW', 'SPY') or not re.fullmatch(r'\d{8}', date):
        raise ValueError('Unexpected ticker/date key')
    source = Path(row['day_root'])
    for name in ('states', 'levels'):
        if sha(source / f'{name}.parquet') != row[name + '_sha256']:
            raise ValueError('Causal source hash differs: ' + name)
    binding = dict(contract=contract, ticker=ticker, date=date, split=row['split'],
                   source_root=str(source.resolve()), states_sha256=row['states_sha256'], levels_sha256=row['levels_sha256'])
    day = output / ticker / date
    target = day / 'episodes.npz'
    preserve_partial(day, output)
    if target.exists() and target.with_suffix('.json').exists():
        metadata = verify_day(target, binding)
        status = 'VERIFIED_EXISTING'
    else:
        states = pq.read_table(source / 'states.parquet', columns=list(STATE_COLUMNS)).to_pandas()
        levels = pq.read_table(source / 'levels.parquet', columns=list(LEVEL_COLUMNS)).to_pandas()
        result = ef.build_episode_features(states, levels)
        arrays = dict(state_i=result.state_i, values=result.values, valid=result.valid)
        validate_arrays(arrays)
        for name in ('states', 'levels'):
            if sha(source / f'{name}.parquet') != row[name + '_sha256']:
                raise ValueError('Causal source changed during episode computation')
        day.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.partial-' + uuid.uuid4().hex)
        with temporary.open('wb') as handle:
            np.savez_compressed(handle, **arrays)
        os.replace(temporary, target)
        metadata = dict(version=VERSION, binding=binding, names=list(ef.FEATURE_NAMES), sha256=sha(target),
                        array_schema={name: dict(shape=list(value.shape), dtype=str(value.dtype)) for name, value in arrays.items()},
                        states=316, observed_values=int(result.valid.sum()), episode_open_rows=int(result.values[:, 0].sum()),
                        outcomes_read=False, trained=False)
        write_json(target.with_suffix('.json'), metadata)
        verify_day(target, binding)
        status = 'BUILT'
    return dict(ticker=ticker, date=date, split=row['split'], status=status, sha256=metadata['sha256'],
                bytes=target.stat().st_size, states=metadata['states'], observed_values=metadata['observed_values'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('D:/GexResearchArtifacts/level_oracle_20261018'))
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    output = args.out or args.root / 'episode_features_v1'
    index = args.root / 'engine_v1' / 'index.parquet'
    audit = args.root / 'engine_v1_audit_v4' / 'audit.json'
    code_root = Path(__file__).parent
    if sha(index) != INDEX_SHA or sha(audit) != AUDIT_SHA or sha(Path(ef.__file__)) != EPISODE_SHA:
        raise ValueError('Frozen source authority or episode implementation changed')
    authority = audit.read_text(encoding='utf-8')
    if metadata_string(authority, 'status') != 'PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT' or metadata_string(authority, 'index_sha256') != INDEX_SHA:
        raise ValueError('Independent oracle metadata authority differs')
    rows = pq.read_table(index, columns=list(INDEX_COLUMNS)).to_pylist()
    complete = [row for row in rows if row['status'] == 'COMPLETE']
    missing = [dict(ticker=row['ticker'], date=row['date'], split=row['split'], status=row['status'])
               for row in rows if row['status'] == 'MISSING_SOURCE']
    if len(complete) != 2595 or len(missing) != 6 or len(rows) != 2601:
        raise ValueError('Frozen universe differs')
    expected_keys = {(row['ticker'], row['date']) for row in complete}
    if len(expected_keys) != len(complete):
        raise ValueError('Duplicate source keys')
    for row in complete:
        if Path(row['day_root']).resolve() != (args.root / 'engine_v1' / row['ticker'] / row['date']).resolve():
            raise ValueError('Indexed causal path differs from the frozen root')
    files = [Path(__file__), Path(ef.__file__), code_root / 'EPISODE_FEATURE_SPEC.md', code_root / 'EPISODE_BUILD_SPEC.md']
    contract = dict(version=VERSION, index_sha256=INDEX_SHA, audit_sha256=AUDIT_SHA,
                    dependencies={path.name: sha(path) for path in files}, names=list(ef.FEATURE_NAMES),
                    index_columns=list(INDEX_COLUMNS), state_columns=list(STATE_COLUMNS), level_columns=list(LEVEL_COLUMNS),
                    complete_days=2595, missing_days=6, trained=False, outcomes_read=False)
    output.mkdir(parents=True, exist_ok=True)
    lock = output / 'writer.lock'
    with lock.open('x', encoding='utf-8') as handle:
        json.dump(dict(pid=os.getpid()), handle)
    started, cpu_started = time.perf_counter(), time.process_time()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    records = []
    try:
        contract_path = output / 'contract.json'
        if contract_path.exists():
            if read_json(contract_path) != contract:
                raise ValueError('Output root belongs to a different frozen episode build')
        else:
            write_json(contract_path, contract)
            for path in files:
                shutil.copy2(path, output / (path.stem + '.executed' + path.suffix))
        write_json(output / 'missing_source_days.json', missing)
        for row in sorted(complete, key=lambda item: (item['ticker'], item['date'])):
            records.append(process_day(row, output, contract))
            if len(records) % 100 == 0:
                memory = psutil.Process().memory_info()
                progress = dict(status='BUILDING', days=len(records), wall_seconds=time.perf_counter() - started,
                                rss_bytes=memory.rss, private_bytes=getattr(memory, 'private', memory.vms))
                write_json(output / 'progress.json', progress)
                print(json.dumps(progress), flush=True)
        # Independent pass over every published output hash and structural schema.
        for row in complete:
            target = output / row['ticker'] / row['date'] / 'episodes.npz'
            binding = dict(contract=contract, ticker=row['ticker'], date=row['date'], split=row['split'],
                           source_root=str(Path(row['day_root']).resolve()), states_sha256=row['states_sha256'], levels_sha256=row['levels_sha256'])
            verify_day(target, binding)
        actual_keys = {(ticker, path.parent.name) for ticker in ('QQQ', 'SPXW', 'SPY')
                       for path in (output / ticker).glob('*/episodes.npz')}
        if actual_keys != expected_keys:
            raise ValueError('Final episode output coverage differs')
        write_json(output / 'index.json', records)
        memory = psutil.Process().memory_info()
        summary = dict(status='PASS_PREPARED_CAUSAL_EPISODE_BUILD', days=len(records), missing_days=len(missing),
                       states=sum(row['states'] for row in records), feature_dim=35, mask_dim=35,
                       by_ticker={ticker: sum(row['ticker'] == ticker for row in records) for ticker in ('QQQ', 'SPXW', 'SPY')},
                       compressed_bytes=sum(row['bytes'] for row in records), verified_output_hashes=len(records),
                       verified_source_hashes=2 * len(records), wall_seconds=time.perf_counter() - started,
                       cpu_seconds=time.process_time() - cpu_started, peak_rss_bytes=getattr(memory, 'peak_wset', memory.rss),
                       peak_private_bytes=getattr(memory, 'peak_pagefile', None), workers=1,
                       index_sha256=sha(output / 'index.json'), contract_sha256=sha(contract_path),
                       outcomes_read=False, trained=False, model_selection_started=False,
                       completed_utc=datetime.now(timezone.utc).isoformat())
        write_json(output / 'summary.json', summary)
        write_json(output / (stamp + '_summary.json'), summary)
        write_json(output / 'progress.json', summary)
        print(json.dumps(summary), flush=True)
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
