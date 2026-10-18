"""Project frozen causal actions into feature vectors; never read outcome files."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import time

for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '1'

import pyarrow.parquet as pq  # noqa: E402

try:
    from . import features as f
except ImportError:
    import features as f


def process_day(task):
    actions_path, source, target = map(Path, task)
    freeze_path = actions_path.with_name('causal_freeze.json')
    identity_path = actions_path.with_name('identity.json')
    freeze = json.loads(freeze_path.read_text(encoding='utf-8'))
    digest = f._sha(actions_path)
    if digest != freeze['actions.parquet']:
        raise ValueError(f'Causal action freeze/hash mismatch: {actions_path}')
    identity = json.loads(identity_path.read_text(encoding='utf-8'))
    if identity['engine_sha256'] != f._dependencies()['level_engine.py']:
        raise ValueError('Action engine code differs from frozen feature dependency')
    source_metadata = f.build_cache.read_day_metadata(source)
    if identity['metadata']['sha256'] != source_metadata['sha256']:
        raise ValueError('Action source cache identity mismatch')
    columns = ['action_id', *f.ACTION_INPUT_NAMES]
    actions = pq.read_table(actions_path, columns=columns).to_pandas()
    if actions.action_id.duplicated().any():
        raise ValueError('Duplicate action IDs')
    result = f.write_action_feature_cache(source, actions, target)
    if f._sha(actions_path) != digest:
        raise ValueError('Action input changed during projection')
    provenance = target.with_name('actions.provenance.json')
    if not provenance.exists():
        f.build_cache.write_json(provenance, dict(actions_path=str(actions_path.resolve()), actions_sha256=digest,
                                 causal_freeze_sha256=f._sha(freeze_path), raw_cache_sha256=source_metadata['sha256'],
                                 projected_columns=columns, producer_sha256=f._sha(Path(__file__)), outcomes_read=False))
    else:
        existing = json.loads(provenance.read_text(encoding='utf-8'))
        if existing['actions_sha256'] != digest or existing['raw_cache_sha256'] != source_metadata['sha256']:
            raise ValueError('Prior action-feature provenance differs')
    return dict(ticker=source_metadata['ticker'], date=source_metadata['date'], bytes=target.stat().st_size, **result)


def main():
    parser = argparse.ArgumentParser()
    root = Path('D:/GexResearchArtifacts/level_oracle_20261018')
    parser.add_argument('--cache-root', type=Path, default=root / 'cache_v1')
    parser.add_argument('--engine-root', type=Path, default=root / 'engine_v1')
    parser.add_argument('--out', type=Path, default=root / 'features_v1')
    parser.add_argument('--workers', type=int, choices=(1, 2, 3, 4), default=2)
    parser.add_argument('--date')
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--completion-marker', default='completion.json')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    contract = dict(producer_sha256=f._sha(Path(__file__)), dependencies=f._dependencies(),
                    action_names=list(f.ACTION_NAMES), projected_columns=['action_id', *f.ACTION_INPUT_NAMES],
                    cache_root=str(args.cache_root.resolve()), outcomes_read=False)
    contract_path = args.out / 'action_feature_contract.json'
    if contract_path.exists():
        if json.loads(contract_path.read_text(encoding='utf-8')) != contract:
            raise ValueError('Action feature producer/binding changed; choose a new output root')
    else:
        f.build_cache.write_json(contract_path, contract)
        shutil.copy2(Path(__file__), args.out / 'build_action_features.executed.py')
    seen, records = set(), []
    while True:
        ready = sorted(path for path in args.engine_root.glob('*/*/actions.parquet')
                       if path.with_name('causal_freeze.json').exists() and path.with_name('identity.json').exists()
                       and (not args.date or path.parent.name == args.date))
        tasks = []
        for path in ready:
            if str(path) in seen:
                continue
            ticker, date = path.parent.parent.name, path.parent.name
            source = args.cache_root / ticker / f'{date}.npz'
            if source.exists() and source.with_suffix('.json').exists():
                tasks.append((str(path), str(source), str(args.out / ticker / date / 'actions.npz')))
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            for record in executor.map(process_day, tasks, chunksize=1):
                records.append(record)
                if len(records) % 25 == 0:
                    progress = dict(status='RUNNING', processed=len(records), actions=sum(x['actions'] for x in records), last=record)
                    f.build_cache.write_json(args.out / 'action_progress.json', progress)
                    print(json.dumps(progress), flush=True)
        seen.update(task[0] for task in tasks)
        complete = (args.engine_root / args.completion_marker).exists()
        if not args.watch or args.date or complete:
            remaining = [path for path in args.engine_root.glob('*/*/actions.parquet')
                         if path.with_name('causal_freeze.json').exists() and str(path) not in seen]
            if args.watch and not args.date and remaining:
                continue
            break
        time.sleep(15)
    summary = dict(status='COMPLETE_AVAILABLE', processed=len(records), actions=sum(x['actions'] for x in records),
                   compressed_bytes=sum(x['bytes'] for x in records), engine_complete_marker=complete,
                   engine_root=str(args.engine_root.resolve()), outcomes_read=False,
                   completed_utc=datetime.now(timezone.utc).isoformat())
    f.build_cache.write_json(args.out / 'action_progress.json', summary)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    f.build_cache.write_json(args.out / f'{stamp}_action_summary.json', summary)
    f.build_cache.write_json(args.out / f'{stamp}_action_coverage.json', records)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
