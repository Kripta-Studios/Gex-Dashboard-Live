"""Three bounded fits with sealed causal policy rollouts; no oracle targets.

Default stage prepares identity samples only. All outcome-consuming stages
require a hash-bound implementation review. Existing producers stay unchanged.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import fields
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

for _key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '1'

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import lightgbm as lgb  # noqa: E402
import psutil  # noqa: E402

import train_models as base  # noqa: E402
import causal_rollout as rollout  # noqa: E402
import rollout_sampling as sampling  # noqa: E402

ROOT = Path('D:/GexResearchArtifacts/level_oracle_20261018')
MODELS = ('net_control', 'causal_residual')
THRESHOLDS = (0., 5., 10.)
TICKERS = ('SPXW', 'SPY', 'QQQ')
VERSION = 'CAUSAL_FIXED_POLICY_ROLLOUT_V1'
CONFIG = dict(objective='regression', n_estimators=200, num_leaves=31, max_depth=6,
              min_child_samples=100, learning_rate=.04, reg_lambda=10., max_bin=63,
              random_state=20261018, n_jobs=4, deterministic=True,
              force_col_wise=True, verbosity=-1)
DEPENDENCIES = ('train_causal_rollout.py', 'causal_rollout.py', 'rollout_sampling.py',
                'CAUSAL_ROLLOUT_LEARNER_PLAN.md', 'train_models.py', 'features.py',
                'build_cache.py', 'level_engine.py', 'run_engine_dataset.py')


def sha(path):
    return base.sha(path)


def durable_replace(temporary, path):
    temporary, path = Path(temporary), Path(path)
    with temporary.open('r+b') as handle:
        os.fsync(handle.fileno())
    digest = sha(temporary)
    os.replace(temporary, path)
    if sha(path) != digest:
        raise IOError('Published artifact hash differs from staged bytes')
    if os.name != 'nt':
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def atomic_json(path, value, *, replace=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise FileExistsError(path)
    temporary = path.with_name(path.name + '.partial-' + uuid.uuid4().hex)
    with temporary.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(value, indent=2, allow_nan=False))
        handle.flush()
        os.fsync(handle.fileno())
    durable_replace(temporary, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


@contextmanager
def exclusive_lock(path):
    """OS lock releases on process death; file presence is never the lock."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    try:
        if path.stat().st_size == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        handle.close()
        raise RuntimeError('Another process holds the rollout output lock') from None
    try:
        yield
    finally:
        handle.seek(0)
        if os.name == 'nt':
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


class Artifacts:
    """Complete markers bind every consumed artifact; orphan files are preserved."""
    def __init__(self, root, binding):
        self.root, self.binding = Path(root), binding

    def marker(self, name):
        return self.root / (name + '.complete.json')

    def complete(self, name):
        marker = self.marker(name)
        if not marker.exists():
            return False
        record = read_json(marker)
        if record.get('binding') != self.binding or record.get('status') != 'COMPLETE':
            raise ValueError('Artifact binding mismatch: ' + name)
        for relative, digest in record['files'].items():
            path = self.root / relative
            if not path.exists() or sha(path) != digest:
                raise ValueError('Incomplete/changed artifact: ' + str(path))
        return True

    def finish(self, name, paths, extra=None):
        atomic_json(self.marker(name), dict(status='COMPLETE', binding=self.binding,
                    files={str(Path(p).relative_to(self.root)): sha(p) for p in paths},
                    extra=extra or {}, completed_utc=datetime.now(timezone.utc).isoformat()))

    def save_npz(self, name, arrays):
        path = self.root / (name + '.npz')
        if self.complete(name):
            return path
        if path.exists():
            raise RuntimeError('Orphan NPZ preserved; no silent adoption: ' + str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.partial-' + uuid.uuid4().hex)
        with temporary.open('xb') as handle:
            np.savez_compressed(handle, **arrays)
            handle.flush()
            os.fsync(handle.fileno())
        durable_replace(temporary, path)
        self.finish(name, [path])
        return path

    def load_npz(self, name):
        if not self.complete(name):
            raise ValueError('Required checkpoint is incomplete: ' + name)
        with np.load(self.root / (name + '.npz'), allow_pickle=False) as stored:
            return {key: stored[key] for key in stored.files}


def dependency_hashes():
    return {name: sha(Path(__file__).with_name(name)) for name in DEPENDENCIES}


def require_review(path, dependencies):
    review = read_json(path)
    if review.get('status') != 'PASS_CAUSAL_ROLLOUT_IMPLEMENTATION_REVIEW':
        raise ValueError('Implementation review has not passed')
    if review.get('dependencies') != dependencies:
        raise ValueError('Implementation review does not bind this exact code/plan')


class SourceSeal:
    """Projection deliberately excludes oracle metrics, values and advantages."""
    def __init__(self, root):
        self.root = Path(root)
        columns = ['ticker', 'date', 'status', 'day_root', 'cache_npz_sha256',
                   'cache_meta_sha256', 'actions_sha256', 'labels_sha256']
        frame = pd.read_parquet(self.root / 'index.parquet', columns=columns)
        frame['date'] = frame.date.astype(str)
        self.index = frame.set_index(['ticker', 'date'], verify_integrity=True)
        self.hashes = {}

    def check(self, day, filename):
        if filename not in ('actions.parquet', 'labels.parquet'):
            raise ValueError('Only causal actions and realized transition labels are allowed')
        row = self.index.loc[(day.ticker, day.date)]
        path = day.oracle / filename
        if row.status != 'COMPLETE' or Path(row.day_root).resolve() != day.oracle.resolve():
            raise ValueError('Unaudited day root')
        digest = sha(path)
        if digest != row[Path(filename).stem + '_sha256']:
            raise ValueError('Source hash mismatch: ' + str(path))
        self.hashes[str(path)] = digest
        return digest

    def read(self, day, filename, columns=None):
        before = self.check(day, filename)
        frame = pd.read_parquet(day.oracle / filename, columns=columns)
        if self.check(day, filename) != before:
            raise ValueError('Source changed while reading')
        return frame


class VerifiedFeatureStore(base.FeatureStore):
    """Persist first-use pack/metadata hashes, rejecting coherent replacement."""
    def __init__(self, days, artifacts, seal):
        super().__init__(days, capacity=2, seal=seal)
        self.artifacts = artifacts

    def get(self, key):
        cached = key in self.cache
        pack = super().get(key)
        if not cached:
            path = self.days[key].features
            action_path = path.with_name('actions.npz')
            paths = (path, path.with_suffix('.json'), action_path, action_path.with_suffix('.json'))
            hashes = {str(source.resolve()): sha(source) for source in paths}
            name = 'feature_inputs/' + key
            record = self.artifacts.root / (name + '.json')
            if self.artifacts.complete(name):
                if read_json(record) != hashes:
                    raise ValueError('Feature pack/metadata changed since first use')
            else:
                atomic_json(record, hashes)
                self.artifacts.finish(name, [record])
        return pack


def require_source_audit(path, root, seal):
    audit = read_json(path)
    if audit.get('status') != 'PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT':
        raise ValueError('Independent full engine audit required')
    binding = audit['binding']
    root = Path(root).resolve()
    if Path(binding['engine_root']).resolve() != root:
        raise ValueError('Audit belongs to another engine root')
    contract = read_json(root / 'dataset_contract.json')
    completion = read_json(root / 'completion.json')
    if completion['status'] != 'COMPLETE':
        raise ValueError('Source is not complete')
    cache = Path(contract['cache_root'])
    paths = {'completion_sha256': root / 'completion.json',
             'index_sha256': root / 'index.parquet',
             'dataset_contract_sha256': root / 'dataset_contract.json',
             'cache_contract_sha256': cache / 'cache_contract.json',
             'cache_full_summary_sha256': cache / 'full_summary.json',
             'engine_sha256': Path(__file__).with_name('level_engine.py'),
             'engine_runner_sha256': Path(__file__).with_name('run_engine_dataset.py')}
    for name, source in paths.items():
        if sha(source) != binding.get(name):
            raise ValueError('Audit binding mismatch: ' + name)
    if len(seal.index) != 2601 or seal.index.status.value_counts().to_dict() != {'COMPLETE': 2595, 'MISSING_SOURCE': 6}:
        raise ValueError('Coverage must retain all 2601 expected ticker-days')
    return {'audit_sha256': sha(path), 'binding': binding}


def check_calendar(days):
    import exchange_calendars as xc
    calendar = xc.get_calendar('XNYS').schedule.loc['2023-01-03':'2026-06-30']
    dates = calendar.loc[(calendar.close - calendar.open) == pd.Timedelta(hours=6, minutes=30)].index.strftime('%Y%m%d').tolist()
    missing = {(ticker, date) for ticker in ('SPY', 'QQQ') for date in ('20260401', '20260409', '20260415')}
    expected = {(ticker, date) for ticker in TICKERS for date in dates}
    actual = {(day.ticker, day.date) for day in days}
    if len(dates) != 867 or len(days) != len(actual) or actual != expected - missing:
        raise ValueError('Declared full calendar/source universe differs')
    return dates


def progress(out, stage, completed, total, start):
    elapsed = max(time.monotonic() - start, .001)
    process = psutil.Process()
    memory = process.memory_info()
    value = dict(stage=stage, completed=int(completed), total=int(total),
                 elapsed_seconds=elapsed, eta_seconds=(total - completed) * elapsed / max(completed, 1),
                 private_bytes=int(getattr(memory, 'private', memory.rss)), rss_bytes=int(memory.rss),
                 utc=datetime.now(timezone.utc).isoformat())
    atomic_json(Path(out) / 'progress.json', value, replace=True)
    print(json.dumps(value), flush=True)


def fit_sample_arrays(sample):
    return {field.name: np.asarray(value) for field in fields(sample)
            if (value := getattr(sample, field.name)) is not None}


def prepare_samples(days, seal, artifacts):
    for role in ('teacher', 'final'):
        name = 'samples/' + role
        existing = artifacts.load_npz(name) if artifacts.complete(name) else None
        selected = [day for day in days if ('20230101' <= day.date <= '20230630' if role == 'teacher' else '20230701' <= day.date <= '20241231')]
        samples = []
        start = time.monotonic()
        for i, day in enumerate(selected, 1):
            actions = seal.read(day, 'actions.parquet', ['action_id', 'state_i'])
            samples.append(sampling.sample_day(day.ticker, day.date,
                           actions.action_id.to_numpy(), actions.state_i.to_numpy()))
            if i % 50 == 0 or i == len(selected):
                progress(artifacts.root, 'sampling_' + role, i, len(selected), start)
        arrays = fit_sample_arrays(sampling.prepare_fit_rows(samples, role=role))
        arrays.update(population_ticker=np.array([s.ticker for s in samples]),
                      population_date=np.array([s.date for s in samples]),
                      population_by_band=np.stack([s.population_by_band for s in samples]),
                      selected_by_band=np.stack([s.selected_by_band for s in samples]))
        if existing is not None:
            if set(existing) != set(arrays) or any(not np.array_equal(existing[k], v) for k, v in arrays.items()):
                raise ValueError('Reconstructed full-population sampling differs: ' + role)
        else:
            artifacts.save_npz(name, arrays)


def sample_groups(sample):
    keys = np.char.add(np.char.add(sample['ticker'], '/'), sample['date'])
    return [(str(key), np.flatnonzero(keys == key)) for key in np.unique(keys)]


def feature_rows(store, day_key, ids, h=None):
    pack, ai, si = store.rows(day_key, ids)
    x = base.flatten_gbt(pack, ai, si)
    if x.shape != (len(ids), 1954) or not np.isfinite(x).all():
        raise ValueError('Existing GBT input must have 1954 finite columns')
    if h is not None:
        h = np.asarray(h)
        if h.shape != (len(ids),) or not np.isin(h, [0, 1]).all():
            raise ValueError('Invalid has_filled_today vector')
        x = np.column_stack((x, h.astype(np.float32)))
    return x


def outcome_rows(labels):
    return rollout.OutcomeRows(labels.action_id.to_numpy(), labels.status.to_numpy(),
                               labels.exit_i.to_numpy(), labels.net_base.to_numpy(float))


def action_rows(actions):
    return rollout.ActionRows(actions.action_id.to_numpy(), actions.state_i.to_numpy())


def score_actions(model, store, day, actions, scale, *, teacher=False):
    expected = 1954 if teacher else 1955
    if model.num_feature() != expected:
        raise ValueError('Model input schema mismatch')
    scores = np.empty((len(actions), 2), dtype=np.float64)
    for start in range(0, len(actions), 256):
        ids = actions.action_id.iloc[start:start + 256].to_numpy()
        x = feature_rows(store, day.key, ids)
        if teacher:
            score = model.predict(x, num_threads=4) * scale
            scores[start:start + len(ids)] = score[:, None]
        else:
            for h in (0, 1):
                batch = np.column_stack((x, np.full(len(x), h, dtype=np.float32)))
                scores[start:start + len(ids), h] = model.predict(batch, num_threads=4) * scale
    if not np.isfinite(scores).all():
        raise ValueError('Nonfinite causal scores')
    return scores


def evaluate_flag_policy(actions, labels, scores, threshold):
    """Irrevocable decisions precede outcome lookup; no-fill preserves h."""
    keys, outcomes = action_rows(actions), outcome_rows(labels)
    rollout.validate_engine_outcomes(keys, outcomes)
    choices = rollout.freeze_choices(keys, scores, threshold=threshold)
    indexed = labels.set_index('action_id').loc[actions.action_id].reset_index()
    lookup = {int(key): i for i, key in enumerate(actions.action_id)}
    selected, flags, chosen_scores = [], [], []
    minute, h = 60, 0
    while minute <= 375:
        key = int(choices[minute - 60, h])
        if key == -1:
            minute += 1
            continue
        row = lookup[key]
        selected.append(row)
        flags.append(h)
        chosen_scores.append(float(scores[row, h]))
        result = indexed.iloc[row]
        if result.status == 'FILLED':
            h = 1
            minute = int(result.exit_i) + 1
        else:
            minute += 1
    attempts = actions.iloc[selected].merge(indexed.iloc[selected], on='action_id', validate='one_to_one')
    attempts['has_filled_before'] = flags
    attempts['score'] = chosen_scores
    return attempts, attempts.loc[attempts.status == 'FILLED'].copy()


def free_commit_bytes():
    if os.name != 'nt':
        return psutil.virtual_memory().available + psutil.swap_memory().free
    import ctypes
    from ctypes import wintypes
    class Performance(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD)] + [(key, ctypes.c_size_t) for key in
            ('CommitTotal', 'CommitLimit', 'CommitPeak', 'PhysicalTotal', 'PhysicalAvailable',
             'SystemCache', 'KernelTotal', 'KernelPaged', 'KernelNonpaged', 'PageSize')] + [
             (key, wintypes.DWORD) for key in ('HandleCount', 'ProcessCount', 'ThreadCount')]
    info = Performance()
    info.cb = ctypes.sizeof(info)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb):
        raise OSError('Cannot measure Windows commit headroom')
    return (info.CommitLimit - info.CommitTotal) * info.PageSize


def wait_resources(out):
    while psutil.virtual_memory().available < 12 * 1024**3 or free_commit_bytes() < 16 * 1024**3:
        value = dict(stage='WAITING_RESOURCES', available_ram=psutil.virtual_memory().available,
                     free_commit=free_commit_bytes(), utc=datetime.now(timezone.utc).isoformat())
        atomic_json(Path(out) / 'progress.json', value, replace=True)
        print(json.dumps(value), flush=True)
        time.sleep(30)


def fit_once(name, x, y, weights, artifacts):
    key = 'models/' + name
    path = artifacts.root / (key + '.txt')
    signature = dict(binding=artifacts.binding, config=CONFIG, shape=list(x.shape),
        matrix_sha256=sha(x.filename) if isinstance(x, np.memmap) else hashlib.sha256(x.tobytes()).hexdigest(),
        target_sha256=hashlib.sha256(y.tobytes()).hexdigest(),
        weight_sha256=hashlib.sha256(weights.tobytes()).hexdigest())
    started = artifacts.root / (key + '.fit_started.json')
    if artifacts.complete(key):
        prior = read_json(started)
        if any(prior.get(field) != value for field, value in signature.items()):
            raise ValueError('Completed fit inputs differ; no silent reuse')
        return lgb.Booster(model_file=str(path))
    if started.exists() or path.exists():
        raise RuntimeError('Interrupted/orphan fit preserved; automatic refit prohibited: ' + name)
    if y.shape != (len(x),) or weights.shape != y.shape or not np.isfinite(y).all() or not np.isfinite(weights).all() or np.any(weights <= 0):
        raise ValueError('Invalid fit targets/weights')
    wait_resources(artifacts.root)
    atomic_json(started, dict(**signature, started_utc=datetime.now(timezone.utc).isoformat()))
    model = lgb.LGBMRegressor(**CONFIG)
    print(json.dumps(dict(stage='FIT_STARTED', model=name, rows=len(x), columns=x.shape[1])), flush=True)
    model.fit(x, y, sample_weight=weights)
    temporary = path.with_name(path.name + '.partial-' + uuid.uuid4().hex)
    model.booster_.save_model(str(temporary))
    durable_replace(temporary, path)
    artifacts.finish(key, [path, started], dict(config=CONFIG, columns=x.shape[1], rows=len(x)))
    return model.booster_


def verify_rollout_identities(keys, outcomes, values, residual, penalty):
    """Exhaustive teacher-independent-h identities, not performance selection."""
    filled, _, _ = outcomes.aligned(keys)
    gap = values[:, 1] - values[:, 0]
    tolerance = 1e-9 * max(1., penalty, float(np.max(np.abs(values))))
    if not np.all(np.minimum(np.abs(gap), np.abs(gap - penalty)) <= tolerance):
        raise ValueError('Fixed teacher h-value gap is neither zero nor penalty')
    expected = gap[keys.state_i + 1 - 60]
    if not np.allclose(residual[filled, 0] - residual[filled, 1], expected[filled], rtol=0, atol=tolerance):
        raise ValueError('Residual h identity violated')
    if np.any(residual[~filled] != 0) or np.any(expected < -tolerance):
        raise ValueError('NO_FILL/monotonic target identity violated')
    return dict(actions=len(filled), filled=int(filled.sum()), tolerance=tolerance,
                status='PASS_EXHAUSTIVE_FIXED_TEACHER_IDENTITIES')


def assemble_matrix(role, sample, artifacts, columns):
    name = 'matrices/' + role
    path = artifacts.root / (name + '.npy')
    if artifacts.complete(name):
        x = np.load(path, mmap_mode='r', allow_pickle=False)
        if x.shape != (len(sample['action_id']), columns) or x.dtype != np.float32:
            raise ValueError('Matrix shape/precision differs')
        return x
    if path.exists():
        raise RuntimeError('Orphan matrix preserved: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial-' + uuid.uuid4().hex)
    x = np.lib.format.open_memmap(temporary, mode='w+', dtype=np.float32,
                                 shape=(len(sample['action_id']), columns))
    for key, rows in sample_groups(sample):
        chunk = artifacts.load_npz('chunks/' + role + '/' + key)
        if not np.array_equal(chunk['positions'], rows) or chunk['x'].shape != (len(rows), columns):
            raise ValueError('Chunk identity/shape mismatch')
        if not np.isfinite(chunk['x']).all():
            raise ValueError('Nonfinite feature chunk')
        x[rows] = chunk['x']
    x.flush()
    del x
    durable_replace(temporary, path)
    artifacts.finish(name, [path])
    return np.load(path, mmap_mode='r', allow_pickle=False)


def teacher_stage(days, store, seal, artifacts):
    sample = artifacts.load_npz('samples/teacher')
    by_key = {day.key: day for day in days}
    groups = sample_groups(sample)
    start = time.monotonic()
    for i, (key, rows) in enumerate(groups, 1):
        name = 'chunks/teacher/' + key
        store.get(key)
        seal.check(by_key[key], 'labels.parquet')
        if not artifacts.complete(name):
            day = by_key[key]
            labels = seal.read(day, 'labels.parquet', ['action_id', 'status', 'net_base', 'entry_ask'])
            if labels.action_id.duplicated().any():
                raise ValueError('Duplicate labels')
            selected = labels.set_index('action_id').loc[sample['action_id'][rows]]
            x = feature_rows(store, key, sample['action_id'][rows])
            artifacts.save_npz(name, dict(positions=rows, x=x,
                net=selected.net_base.to_numpy(float), premium=selected.entry_ask.to_numpy(float) * 100,
                filled=(selected.status == 'FILLED').to_numpy()))
        if i % 25 == 0 or i == len(groups):
            progress(artifacts.root, 'teacher_chunks', i, len(groups), start)
    net = np.empty(len(sample['action_id']), float)
    premium, filled = np.empty_like(net), np.empty(len(net), bool)
    for key, rows in groups:
        chunk = artifacts.load_npz('chunks/teacher/' + key)
        net[rows], premium[rows], filled[rows] = chunk['net'], chunk['premium'], chunk['filled']
    scales = {}
    for ticker in TICKERS:
        mask = (sample['ticker'] == ticker) & filled
        scales[ticker] = base.weighted_median(premium[mask], sample['weight'][mask])
    scale_path = artifacts.root / 'risk_scales.json'
    if artifacts.complete('risk_scales'):
        if read_json(scale_path) != scales:
            raise ValueError('Reconstructed H1 risk scale differs')
    else:
        atomic_json(scale_path, scales)
        artifacts.finish('risk_scales', [scale_path])
    x = assemble_matrix('teacher', sample, artifacts, 1954)
    divisor = np.array([scales[t] for t in sample['ticker']])
    model = fit_once('teacher', x, net / divisor, sample['fit_weight'], artifacts)
    del x
    return model, scales


def rollout_stage(days, store, seal, artifacts):
    if not artifacts.complete('models/teacher') or not artifacts.complete('risk_scales'):
        raise ValueError('Frozen teacher and H1 scales required before rollout labels')
    model = lgb.Booster(model_file=str(artifacts.root / 'models/teacher.txt'))
    scales = read_json(artifacts.root / 'risk_scales.json')
    sample = artifacts.load_npz('samples/final')
    groups = dict(sample_groups(sample))
    selected_days = [day for day in days if '20230701' <= day.date <= '20241231']
    start = time.monotonic()
    for number, day in enumerate(selected_days, 1):
        store.get(day.key)
        causal_name, target_name = 'teacher_choices/' + day.key, 'rollouts/' + day.key
        actions = seal.read(day, 'actions.parquet')
        keys = action_rows(actions)
        if not artifacts.complete(causal_name):
            scores = score_actions(model, store, day, actions, scales[day.ticker], teacher=True)
            choices = rollout.freeze_choices(keys, scores)
            if not np.array_equal(choices[:, 0], choices[:, 1]):
                raise ValueError('Teacher must be independent of h')
            artifacts.save_npz(causal_name, dict(action_id=keys.action_id, state_i=keys.state_i,
                scores=scores, choices=choices,
                teacher_sha256=np.array(sha(artifacts.root / 'models/teacher.txt')),
                scale_sha256=np.array(sha(artifacts.root / 'risk_scales.json'))))
        causal = artifacts.load_npz(causal_name)  # Committed before any label read.
        if str(causal['teacher_sha256']) != sha(artifacts.root / 'models/teacher.txt') or str(causal['scale_sha256']) != sha(artifacts.root / 'risk_scales.json'):
            raise ValueError('Teacher choice producer binding differs')
        if not np.array_equal(causal['action_id'], keys.action_id) or not np.array_equal(causal['state_i'], keys.state_i):
            raise ValueError('Teacher causal identities changed')
        if not artifacts.complete(target_name):
            labels = seal.read(day, 'labels.parquet', ['action_id', 'status', 'exit_i', 'net_base'])
            outcomes = outcome_rows(labels)
            rollout.validate_engine_outcomes(keys, outcomes)
            values = rollout.fixed_policy_values(keys, outcomes, causal['choices'], scales[day.ticker])
            residual = rollout.residual_targets(keys, outcomes, values)
            diagnostic = verify_rollout_identities(keys, outcomes, values, residual, scales[day.ticker])
            rows = groups[day.key]
            index = pd.Index(keys.action_id).get_indexer(sample['action_id'][rows])
            if np.any(index < 0):
                raise ValueError('Sampled action disappeared')
            _, _, net = outcomes.aligned(keys)
            artifacts.save_npz(target_name, dict(positions=rows, values=values,
                net=net[index], residual=residual[index, sample['has_filled_today'][rows]],
                identities_checked=np.array(json.dumps(diagnostic)),
                choice_sha256=np.array(sha(artifacts.root / (causal_name + '.npz')))))
        else:
            seal.check(day, 'labels.parquet')
        if number % 25 == 0 or number == len(selected_days):
            progress(artifacts.root, 'policy_rollouts', number, len(selected_days), start)


def final_fit_stage(days, store, artifacts):
    if not artifacts.complete('risk_scales'):
        raise ValueError('Verified H1 risk scales required')
    sample = artifacts.load_npz('samples/final')
    groups = sample_groups(sample)
    scales = read_json(artifacts.root / 'risk_scales.json')
    net, residual = np.empty(len(sample['action_id'])), np.empty(len(sample['action_id']))
    start = time.monotonic()
    for number, (key, rows) in enumerate(groups, 1):
        store.get(key)
        target = artifacts.load_npz('rollouts/' + key)
        if str(target['choice_sha256']) != sha(artifacts.root / ('teacher_choices/' + key + '.npz')):
            raise ValueError('Rollout targets bind different frozen choices')
        if json.loads(str(target['identities_checked']))['status'] != 'PASS_EXHAUSTIVE_FIXED_TEACHER_IDENTITIES':
            raise ValueError('Required exhaustive target identities missing')
        if not np.array_equal(target['positions'], rows):
            raise ValueError('Rollout/sample alignment differs')
        net[rows], residual[rows] = target['net'], target['residual']
        name = 'chunks/final/' + key
        if not artifacts.complete(name):
            x = feature_rows(store, key, sample['action_id'][rows], sample['has_filled_today'][rows])
            artifacts.save_npz(name, dict(positions=rows, x=x))
        if number % 25 == 0 or number == len(groups):
            progress(artifacts.root, 'final_matrix_chunks', number, len(groups), start)
    x = assemble_matrix('final', sample, artifacts, 1955)
    divisor = np.array([scales[t] for t in sample['ticker']])
    artifacts.save_npz('final_targets', dict(net=net, residual=residual, divisor=divisor,
                       fit_weight=sample['fit_weight']))
    for name, target in zip(MODELS, (net, residual)):
        fit_once(name, x, target / divisor, sample['fit_weight'], artifacts)
    del x


def policy_id(model, threshold):
    return model + '__' + str(int(threshold))


def economic_summary(ledger):
    result = {'trades': len(ledger)}
    for field in ('net_base', 'net_adverse'):
        values = ledger[field].to_numpy(float) if len(ledger) else np.array([], float)
        if not np.isfinite(values).all():
            raise ValueError('Nonfinite economic reward')
        gains, losses = float(values[values > 0].sum()), float(-values[values < 0].sum())
        curve = np.r_[0., np.cumsum(values)]
        result[field] = float(values.sum())
        result[field + '_pf'] = gains / losses if losses else None
        result[field + '_pf_infinite'] = gains > 0 and losses == 0
        result[field + '_win_rate'] = float((values > 0).mean()) if len(values) else None
        result[field + '_max_drawdown'] = float(np.max(np.maximum.accumulate(curve) - curve))
    result['holding_minutes'] = {key: (float(getattr(ledger.hold_minutes, key)()) if len(ledger) else None)
                                 for key in ('min', 'median', 'max')}
    result['exit_reasons'] = {reason: {'trades': int((ledger.reason == reason).sum()),
        'net_base': float(ledger.loc[ledger.reason == reason, 'net_base'].sum()),
        'net_adverse': float(ledger.loc[ledger.reason == reason, 'net_adverse'].sum())}
        for reason in ('TARGET', 'STOP', 'EOD')} if len(ledger) else {}
    return result


def select_validation(candidates, scales):
    """Hard daily constraint; never substitute the least infeasible candidate."""
    eligible = []
    for model in MODELS:
        for threshold in THRESHOLDS:
            key = policy_id(model, threshold)
            stats = candidates[key]
            if stats['zero_fill_expected_days'] == 0:
                score = sum(stats['tickers'][t]['net_base'] / scales[t] for t in TICKERS)
                eligible.append(dict(policy=key, score=float(score), model=model, threshold=threshold))
    winner = max(eligible, key=lambda value: value['score']) if eligible else None
    return dict(status='SELECTED' if winner else 'FAILED_DAILY_REQUIREMENT_VALIDATION',
                selected_policy=winner, eligible=eligible,
                frozen_candidates=[policy_id(m, t) for m in MODELS for t in THRESHOLDS],
                cash='REFERENCE_ONLY_FAILS_DAILY_REQUIREMENT')


def save_parquet(path, frame):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError('Orphan parquet preserved: ' + str(path))
    temporary = path.with_name(path.name + '.partial-' + uuid.uuid4().hex)
    frame.to_parquet(temporary, index=False)
    durable_replace(temporary, path)


def evaluate_stage(period, days, dates, store, seal, artifacts):
    test_root = artifacts.root / 'test'
    if test_root.exists() and any(p.is_file() for p in test_root.rglob('*')) and not artifacts.complete('validation_freeze'):
        raise ValueError('Test evidence exists without valid selection freeze; cannot rebuild authority')
    if period == 'test' and not artifacts.complete('validation_freeze'):
        raise ValueError('Validation selection/null and all six IDs must be frozen before test')
    if not artifacts.complete('risk_scales'):
        raise ValueError('Verified H1 risk scales required')
    for name in MODELS:
        if not artifacts.complete('models/' + name):
            raise ValueError('Both completed final models are required')
    models = {name: lgb.Booster(model_file=str(artifacts.root / ('models/' + name + '.txt'))) for name in MODELS}
    model_hashes = {name: sha(artifacts.root / ('models/' + name + '.txt')) for name in MODELS}
    scales = read_json(artifacts.root / 'risk_scales.json')
    if period == 'test':
        freeze = read_json(artifacts.root / 'validation_freeze.json')
        if freeze['model_hashes'] != model_hashes or freeze['risk_scales_sha256'] != sha(artifacts.root / 'risk_scales.json') or freeze['validation_summary_sha256'] != sha(artifacts.root / 'validation/summary.json'):
            raise ValueError('Validation freeze producer binding differs')
    start_date, stop_date = ('20250101', '20260101') if period == 'validation' else ('20260101', '20260701')
    selected_days = [day for day in days if start_date <= day.date < stop_date]
    start = time.monotonic()
    for number, day in enumerate(selected_days, 1):
        store.get(day.key)
        predictions = period + '/predictions/' + day.key
        daily = period + '/daily/' + day.key
        actions = seal.read(day, 'actions.parquet')
        keys = action_rows(actions)
        if not artifacts.complete(predictions):
            packed = dict(action_id=keys.action_id, state_i=keys.state_i)
            for name, model in models.items():
                packed[name] = score_actions(model, store, day, actions, scales[day.ticker])
                packed[name + '_sha256'] = np.array(model_hashes[name])
            artifacts.save_npz(predictions, packed)
        packed = artifacts.load_npz(predictions)  # Scores committed before labels.
        if not np.array_equal(packed['action_id'], keys.action_id) or not np.array_equal(packed['state_i'], keys.state_i):
            raise ValueError('Prediction/action identity mismatch')
        if any(str(packed[name + '_sha256']) != model_hashes[name] for name in MODELS):
            raise ValueError('Prediction producer changed')
        if not artifacts.complete(daily):
            labels = seal.read(day, 'labels.parquet')
            attempts, ledgers = [], []
            for name in MODELS:
                for threshold in THRESHOLDS:
                    attempted, ledger = evaluate_flag_policy(actions, labels, packed[name], threshold)
                    for frame in (attempted, ledger):
                        frame['ticker'], frame['date'] = day.ticker, day.date
                        frame['policy'] = policy_id(name, threshold)
                    attempts.append(attempted)
                    ledgers.append(ledger)
            a_path = artifacts.root / (daily + '_attempts.parquet')
            l_path = artifacts.root / (daily + '_ledger.parquet')
            save_parquet(a_path, pd.concat(attempts, ignore_index=True))
            save_parquet(l_path, pd.concat(ledgers, ignore_index=True))
            artifacts.finish(daily, [a_path, l_path], dict(prediction_sha256=sha(artifacts.root / (predictions + '.npz'))))
        else:
            seal.check(day, 'labels.parquet')
        if number % 25 == 0 or number == len(selected_days):
            progress(artifacts.root, period, number, len(selected_days), start)
    summary_name = period + '/summary'
    if artifacts.complete(summary_name):
        result = read_json(artifacts.root / (summary_name + '.json'))
    else:
        all_ledgers = pd.concat([pd.read_parquet(artifacts.root / (period + '/daily/' + day.key + '_ledger.parquet')) for day in selected_days], ignore_index=True)
        all_attempts = pd.concat([pd.read_parquet(artifacts.root / (period + '/daily/' + day.key + '_attempts.parquet')) for day in selected_days], ignore_index=True)
        expected = [(ticker, date) for ticker in TICKERS for date in dates if start_date <= date < stop_date]
        available = {(day.ticker, day.date) for day in selected_days}
        day_rows, result = [], {}
        for model in MODELS:
            for threshold in THRESHOLDS:
                key = policy_id(model, threshold)
                ledger = all_ledgers.loc[all_ledgers.policy == key].sort_values(['date', 'exit_i', 'ticker'], kind='stable')
                attempted = all_attempts.loc[all_attempts.policy == key]
                counts = ledger.groupby(['ticker', 'date']).size().to_dict()
                day_counts = {pair: int(counts.get(pair, 0)) for pair in expected}
                stats = economic_summary(ledger)
                stats.update(attempts=len(attempted), no_fill_attempts=int((attempted.status == 'NO_FILL').sum()),
                    expected_ticker_days=len(expected), observable_ticker_days=len(available),
                    zero_fill_expected_days=sum(value == 0 for value in day_counts.values()),
                    zero_fill_observable_days=sum(day_counts[pair] == 0 for pair in available),
                    missing_source_days=len(expected) - len(available))
                stats['tickers'] = {}
                for ticker in TICKERS:
                    sub = ledger.loc[ledger.ticker == ticker]
                    ticker_stats = economic_summary(sub)
                    months = sorted({date[:6] for t, date in expected if t == ticker})
                    monthly = {month: economic_summary(sub.loc[sub.date.str.startswith(month)]) for month in months}
                    ticker_stats['months'] = monthly
                    ticker_stats['positive_months'] = sum(v['net_base'] > 0 for v in monthly.values())
                    ticker_stats['economic_gate'] = bool(ticker_stats['net_base'] > 0 and ticker_stats['net_adverse'] > 0 and
                        ((ticker_stats['net_base_pf'] or 0) >= 1.2 or ticker_stats['net_base_pf_infinite']) and
                        len(sub) >= 60 and ticker_stats['positive_months'] >= 3)
                    stats['tickers'][ticker] = ticker_stats
                stats['economic_gate_all_tickers'] = all(v['economic_gate'] for v in stats['tickers'].values())
                result[key] = stats
                for (ticker, date), count in day_counts.items():
                    sub = ledger.loc[(ledger.ticker == ticker) & (ledger.date == date)]
                    day_rows.append(dict(policy=key, ticker=ticker, date=date, trades=count,
                        source_available=(ticker, date) in available,
                        net_base=float(sub.net_base.sum()), net_adverse=float(sub.net_adverse.sum())))
        summary_path = artifacts.root / (summary_name + '.json')
        daily_path = artifacts.root / (period + '/daily_calendar.parquet')
        atomic_json(summary_path, result)
        save_parquet(daily_path, pd.DataFrame(day_rows))
        artifacts.finish(summary_name, [summary_path, daily_path])
    diagnostic_name = period + '/score_h_diagnostic'
    if not artifacts.complete(diagnostic_name):
        diagnostic = {model: dict(actions=0, score_h0_lt_h1=0) for model in MODELS}
        for day in selected_days:
            packed = artifacts.load_npz(period + '/predictions/' + day.key)
            for model in MODELS:
                diagnostic[model]['actions'] += len(packed[model])
                diagnostic[model]['score_h0_lt_h1'] += int((packed[model][:, 0] < packed[model][:, 1]).sum())
        path = artifacts.root / (diagnostic_name + '.json')
        atomic_json(path, dict(models=diagnostic, adjustment='NONE_DIAGNOSTIC_ONLY',
            interpretation='Residual true target h0>=h1; net target equal for both h. Predicted order is not enforced.'))
        artifacts.finish(diagnostic_name, [path])
    if period == 'validation' and not artifacts.complete('validation_freeze'):
        freeze_path = artifacts.root / 'validation_freeze.json'
        selection = select_validation(result, scales)
        selection.update(model_hashes=model_hashes, risk_scales_sha256=sha(artifacts.root / 'risk_scales.json'),
                         validation_summary_sha256=sha(artifacts.root / 'validation/summary.json'))
        atomic_json(freeze_path, selection)
        artifacts.finish('validation_freeze', [freeze_path])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine-root', type=Path, default=ROOT / 'engine_v1')
    parser.add_argument('--feature-root', type=Path, default=ROOT / 'features_v1')
    parser.add_argument('--out', type=Path, default=ROOT / 'causal_rollout_v1')
    parser.add_argument('--source-audit', type=Path, required=True)
    parser.add_argument('--implementation-review', type=Path)
    parser.add_argument('--stage', choices=('prepare', 'teacher', 'rollouts', 'final', 'validation', 'test', 'all'), default='prepare')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(args.out / 'runner.lock'):
        dependencies = dependency_hashes()
        if args.stage != 'prepare':
            if args.implementation_review is None:
                raise ValueError('Hash-bound implementation review is required before outcome-consuming stages')
            require_review(args.implementation_review, dependencies)
        seal = SourceSeal(args.engine_root)
        source_audit = require_source_audit(args.source_audit, args.engine_root, seal)
        days = sorted(base.discover_days(args.engine_root, args.feature_root), key=lambda day: (day.ticker, day.date))
        dates = check_calendar(days)
        contract = dict(version=VERSION, dependencies=dependencies, source_audit=source_audit,
            engine_root=str(args.engine_root.resolve()), feature_root=str(args.feature_root.resolve()),
            config=CONFIG, seed=20261018, expected_calendar=2601, available_days=2595,
            teacher_features=1954, learner_features=1955, training_penalty_risk_units=1.,
            feature_contract_sha256=sha(args.feature_root / 'feature_contract.json'),
            software=dict(numpy=np.__version__, pandas=pd.__version__, lightgbm=lgb.__version__))
        contract_path = args.out / 'run_contract.json'
        if contract_path.exists():
            if read_json(contract_path) != contract:
                raise ValueError('Existing run contract differs; no mixing code/source/software versions')
        else:
            atomic_json(contract_path, contract)
        for name, digest in dependencies.items():
            snapshot = args.out / 'executed_code' / name
            if snapshot.exists():
                if sha(snapshot) != digest:
                    raise ValueError('Executed source snapshot changed: ' + name)
            else:
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                temporary = snapshot.with_name(snapshot.name + '.partial-' + uuid.uuid4().hex)
                temporary.write_bytes(Path(__file__).with_name(name).read_bytes())
                if sha(temporary) != digest:
                    raise ValueError('Source changed during snapshot copy')
                durable_replace(temporary, snapshot)
        artifacts = Artifacts(args.out, sha(contract_path))
        prepare_start = time.monotonic()
        prepare_samples(days, seal, artifacts)  # Reconstruct top-K from all source identities on every admission/resume.
        if dependency_hashes() != dependencies:
            raise ValueError('Dependencies changed during preparation')
        if require_source_audit(args.source_audit, args.engine_root, seal) != source_audit:
            raise ValueError('Source audit changed during preparation')
        prepared = {role: artifacts.load_npz('samples/' + role) for role in ('teacher', 'final')}
        if any(int(prepared[role]['n_days']) != count for role, count in (('teacher', 372), ('final', 1119))):
            raise ValueError('Training calendar counts differ')
        if not artifacts.complete('prepare'):
            artifacts.finish('prepare', [args.out / 'samples/teacher.npz', args.out / 'samples/final.npz'],
                dict(status='OUTCOME_FREE_PREPARE_COMPLETE', elapsed_seconds=time.monotonic() - prepare_start,
                     samples={role: dict(days=int(value['n_days']), rows=len(value['action_id'])) for role, value in prepared.items()},
                     source_action_files=len(seal.hashes), source_action_hashes=seal.hashes,
                     labels_read=False, features_read=False))
        if args.stage == 'prepare':
            print(json.dumps(dict(status='OUTCOME_FREE_PREPARE_COMPLETE', binding=artifacts.binding)), flush=True)
            return
        store = VerifiedFeatureStore(days, artifacts, seal)
        stages = ('teacher', 'rollouts', 'final', 'validation', 'test') if args.stage == 'all' else (args.stage,)
        for stage in stages:
            require_review(args.implementation_review, dependency_hashes())
            if stage == 'teacher':
                teacher_stage(days, store, seal, artifacts)
            elif stage == 'rollouts':
                rollout_stage(days, store, seal, artifacts)
            elif stage == 'final':
                final_fit_stage(days, store, artifacts)
            else:
                evaluate_stage(stage, days, dates, store, seal, artifacts)
            require_source_audit(args.source_audit, args.engine_root, seal)
            progress(args.out, stage + '_COMPLETE', 1, 1, time.monotonic())
        print(json.dumps(dict(status='REQUESTED_STAGES_COMPLETE', stages=stages)), flush=True)


if __name__ == '__main__':
    main()
