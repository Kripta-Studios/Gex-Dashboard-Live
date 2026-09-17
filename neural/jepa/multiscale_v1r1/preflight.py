"""RESOURCE-001: actual full-width synthetic fit and capacity estimate."""
import importlib.metadata as metadata
import platform
import shutil
import sys
import threading
import time
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import psutil

from .artifacts import content_digest, digest, stage, write_json
from .contract import BLOCK_SIZE, DISK_RESERVE, PRIMARY_DIM, PROCESS_LIMIT, SEED
from .features import schema
from .models import parameters


def runtime(repo):
    repo = Path(repo)
    code = {}
    for folder in ('neural/jepa/multiscale_v1r1', 'neural/jepa/multiscale_v1r1_audit'):
        for path in sorted((repo / folder).rglob('*.py')):
            code[path.relative_to(repo).as_posix()] = digest(path)
    packages = ('numpy', 'pandas', 'pyarrow', 'lightgbm', 'torch', 'exchange_calendars', 'psutil')
    return {'python': platform.python_version(), 'executable': sys.executable,
            'platform': platform.platform(), 'versions': {p: metadata.version(p) for p in packages},
            'code': code, 'seed': SEED, 'parameters': {c: parameters(c) for c in ('A', 'B')}}


def capacity(rows, free_disk, rss=0, train_rows=None):
    # Persisted tensors: 46020 numeric components and masks plus eight statics.
    tensors = rows * (46020 * 5 + 8 * 4)
    scratch = rows * PRIMARY_DIM * 4
    # One fully dense uint16 binned matrix is a conservative upper storage bound.
    bins = rows * PRIMARY_DIM * 2
    disk = tensors + scratch + bins + 8 * 1024**3  # models, sidecars, logs, staging
    # Include full scratch residency, bins, pool, predictions and fixed runtime reserve.
    train_rows = rows if train_rows is None else train_rows
    # Fixed LightGBM 4.6 default max_bin=255 fits uint8; max train is M=202606.
    memory = train_rows * PRIMARY_DIM * 5 + 1024**3 + BLOCK_SIZE * PRIMARY_DIM * 4 + 2 * 1024**3
    return {'max_events': rows, 'estimated_artifact_bytes': disk,
            'estimated_process_bytes': memory, 'observed_peak_rss': rss,
            'free_disk_bytes': free_disk, 'reserve_bytes': DISK_RESERVE,
            'process_limit_bytes': PROCESS_LIMIT,
            'fits_budget': max(memory, rss) <= PROCESS_LIMIT and disk + DISK_RESERVE <= free_disk,
            'max_train_events': train_rows,
            'assumptions': 'resident float32 train scratch + uint8 bins (fixed max_bin255) + 1GiB histogram + block256 + 2GiB overhead; no simultaneous fits; disk uint16 upper bound'}


def run(repo, root, contract):
    from lightgbm import LGBMRegressor
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    environment = runtime(repo)
    required = {'numpy': '2.3.5', 'pandas': '2.3.3', 'pyarrow': '23.0.1',
                'lightgbm': '4.6.0', 'torch': '2.10.0+cu128', 'exchange_calendars': '4.12'}
    mismatch = {k: [v, environment['versions'].get(k)] for k, v in required.items()
                if environment['versions'].get(k) != v}
    if environment['python'] != '3.14.2':
        mismatch['python'] = ['3.14.2', environment['python']]
    with stage(root / 'preflight') as directory:
        if mismatch:
            result = {'status': 'BLOCKED_DEPENDENCY', 'mismatches': mismatch, 'outcomes_opened': False}
        else:
            schedule = xcals.get_calendar('XNYS', start='2022-08-01', end='2026-06-30').schedule
            schedule = schedule.loc['2022-08-01':'2026-06-30']
            normal = schedule['close'].dt.tz_convert('America/New_York').dt.strftime('%H:%M:%S') == '16:00:00'
            count = int(normal.sum()) * 3 * 18
            train_count = int(normal.loc[:'2025-11-30'].sum()) * 3 * 18
            estimate = capacity(count, shutil.disk_usage(root).free, train_rows=train_count)
            started = time.perf_counter()
            peak = [psutil.Process().memory_info().rss]
            stop = threading.Event()

            def observe():
                while not stop.wait(.02):
                    peak[0] = max(peak[0], psutil.Process().memory_info().rss)

            monitor = threading.Thread(target=observe, daemon=True)
            monitor.start()
            try:
                rng = np.random.default_rng(SEED)
                # Exact dimension. No real market values and no changes to production dependencies.
                x = rng.standard_normal((600, PRIMARY_DIM), dtype=np.float32)
                y = rng.standard_normal(600)
                model = LGBMRegressor(**parameters('A')).fit(x, y)
                predictions = model.predict(x[:BLOCK_SIZE])
                parameter_text = model.booster_.model_to_string().split('parameters:', 1)[-1]
                (directory / 'lightgbm_effective_defaults.txt').write_text(parameter_text, encoding='utf-8')
                del predictions, model, y, x
            finally:
                peak[0] = max(peak[0], psutil.Process().memory_info().rss)
                stop.set()
                monitor.join()
            estimate = capacity(count, shutil.disk_usage(root).free, peak[0], train_count)
            result = {'status': 'PASS_SYNTHETIC_PREFLIGHT' if estimate['fits_budget'] else 'BLOCKED_RESOURCE',
                      'elapsed_seconds': time.perf_counter() - started, 'synthetic_fit_rows': 600,
                      'synthetic_fit_columns': PRIMARY_DIM, 'capacity': estimate,
                      'initial_sessions': len(schedule), 'full_sessions': int(normal.sum()),
                      'half_sessions': int((~normal).sum()), 'outcomes_opened': False,
                      'source_values_opened': False, 'contract_sha256': digest(contract)}
        write_json(directory / 'feature_schema.json', schema())
        write_json(directory / 'runtime_manifest.json', environment)
        result['runtime_sha256'] = content_digest(environment)
        write_json(directory / 'preflight_summary.json', result)
    return result
