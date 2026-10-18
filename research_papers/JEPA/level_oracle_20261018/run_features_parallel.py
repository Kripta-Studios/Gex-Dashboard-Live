"""Bounded scheduling of the unchanged frozen feature producer; no new features."""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import time

try:
    from . import features as f
except ImportError:
    import features as f


def main():
    parser = argparse.ArgumentParser()
    root = Path('D:/GexResearchArtifacts/level_oracle_20261018')
    parser.add_argument('--cache-root', type=Path, default=root / 'cache_v1')
    parser.add_argument('--out', type=Path, default=root / 'features_v1')
    parser.add_argument('--workers', type=int, choices=(1, 2, 4, 6), default=6)
    args = parser.parse_args()
    dependencies = f._dependencies()
    contract = json.loads((args.out / 'feature_contract.json').read_text(encoding='utf-8'))
    if contract['dependencies'] != dependencies or contract['schema'] != f.feature_schema():
        raise ValueError('Frozen feature code/schema identity mismatch')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    runs = args.out / 'runs'
    runs.mkdir(exist_ok=True)
    lock = args.out / 'parallel_writer.lock'
    with lock.open('x', encoding='utf-8') as handle:
        json.dump(dict(pid=os.getpid(), started_utc=stamp), handle)
    record_start = dict(runner_sha256=f._sha(Path(__file__)), dependencies=dependencies,
                        workers=args.workers, feature_representation_changed=False, outcomes_read=False,
                        cache_root=str(args.cache_root.resolve()), pid=os.getpid())
    f.build_cache.write_json(runs / f'{stamp}_parallel_start.json', record_start)
    shutil.copy2(Path(__file__), runs / f'{stamp}_run_features_parallel.executed.py')
    seen, records, last_progress = set(), [], 0.
    available, last_scan = [], 0.
    stop_file = args.out / 'STOP_FEATURE_WRITER'
    status = 'RUNNING'
    try:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            pending = {}
            while True:
                stop = stop_file.exists()
                if not pending or time.monotonic() - last_scan >= 5:
                    available = sorted(path for path in args.cache_root.glob('*/*.npz') if path.with_suffix('.json').exists())
                    last_scan = time.monotonic()
                if not stop:
                    for source in available:
                        if str(source) in seen:
                            continue
                        if len(pending) >= 2 * args.workers:
                            break
                        target = args.out / source.parent.name / source.stem / 'features.npz'
                        task = (str(source), str(target), dependencies)
                        future = executor.submit(f._worker, task)
                        pending[future] = str(source)
                        seen.add(str(source))
                if pending:
                    completed, _ = wait(pending, timeout=5, return_when=FIRST_COMPLETED)
                    for future in completed:
                        pending.pop(future)
                        records.append(future.result())
                now = time.monotonic()
                if now - last_progress >= 10:
                    progress = dict(status='STOPPING' if stop else 'RUNNING', processed=len(records),
                                    built=sum(x['status'] == 'BUILT' for x in records),
                                    verified_existing=sum(x['status'] == 'VERIFIED_EXISTING' for x in records),
                                    available=len(available), pending=len(pending), workers=args.workers,
                                    compressed_bytes=sum(x['bytes'] for x in records))
                    f.build_cache.write_json(args.out / 'progress.json', progress)
                    print(json.dumps(progress), flush=True)
                    last_progress = now
                source_complete = (args.cache_root / 'full_summary.json').exists()
                if not pending and stop:
                    status = 'STOPPED_AT_DAY_BOUNDARY'
                    break
                if not pending and source_complete and all(str(path) in seen for path in available):
                    final_available = [path for path in args.cache_root.glob('*/*.npz') if path.with_suffix('.json').exists()]
                    if all(str(path) in seen for path in final_available):
                        status = 'COMPLETE_AVAILABLE'
                        break
                if not pending:
                    time.sleep(5)
        summary = dict(status=status, processed=len(records), workers=args.workers,
                       built=sum(x['status'] == 'BUILT' for x in records),
                       verified_existing=sum(x['status'] == 'VERIFIED_EXISTING' for x in records),
                       compressed_bytes=sum(x['bytes'] for x in records), source_full_summary_exists=source_complete,
                       outcomes_read=False, dependencies=dependencies,
                       completed_utc=datetime.now(timezone.utc).isoformat())
        f.build_cache.write_json(args.out / 'progress.json', summary)
        f.build_cache.write_json(runs / f'{stamp}_parallel_summary.json', summary)
        f.build_cache.write_json(runs / f'{stamp}_parallel_coverage.json', records)
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
