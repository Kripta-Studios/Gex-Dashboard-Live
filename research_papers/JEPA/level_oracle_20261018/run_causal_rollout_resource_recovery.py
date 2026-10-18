"""Reviewed operational recovery only; no estimator or scientific changes."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

import train_causal_rollout as runner

np = runner.np


PINS = {
    'binding': '66ef48eca5aadca70726b1c66997c93dd513ebf7a32283e07e26fc7e3c129a9d',
    'prepare': '681447d60f6e1b39c9f484e550c2573f33c0bbe7e1e556e21776ebfaf09767a8',
    'teacher': '3659955947ed2b603af78aa562b1526dea674f266a44b1583c81baf691bc0e19',
    'final': '6811c520993c0c0baa4f3dd38e45612d92298631dc991141b62313b6ca55ed7a',
    'runner': 'd031eca08c71ad89324619e096dcc9be3966ddea23d52061019018ff6ff58a43',
}
COUNTS = {'teacher': (372, 47430), 'final': (1119, 285286)}


def fast_prepare(days, seal, artifacts, *, pins=PINS, counts=COUNTS):
    """Identical full source bytes + pinned deterministic outputs, not subset proof."""
    if artifacts.binding != pins['binding'] or runner.sha(artifacts.marker('prepare')) != pins['prepare']:
        raise ValueError('Pinned full preparation differs')
    if not artifacts.complete('prepare'):
        raise ValueError('Complete full preparation required')
    record = runner.read_json(artifacts.marker('prepare'))
    source_map = {str(Path(p).resolve()): digest for p, digest in record['extra']['source_action_hashes'].items()}
    selected = [day for day in days if '20230101' <= day.date <= '20241231']
    observed_paths = {str((day.oracle / 'actions.parquet').resolve()) for day in selected}
    if len(selected) != sum(n for n, _ in counts.values()) or observed_paths != set(source_map):
        raise ValueError('Full source population differs')
    start = time.monotonic()
    for number, day in enumerate(selected, 1):
        path = day.oracle / 'actions.parquet'
        if seal.check(day, 'actions.parquet') != source_map[str(path.resolve())]:
            raise ValueError('Full action source changed, including unselected rows')
        if number % 100 == 0 or number == len(selected):
            runner.progress(artifacts.root, 'recovery_full_source_hashes', number, len(selected), start)
    for role, (n_days, n_rows) in counts.items():
        path = artifacts.root / ('samples/' + role + '.npz')
        if runner.sha(path) != pins[role]:
            raise ValueError('Pinned sample bytes differ')
        sample = artifacts.load_npz('samples/' + role)
        if int(sample['n_days']) != n_days or len(sample['action_id']) != n_rows:
            raise ValueError('Pinned sample counts differ')
        if not np.isfinite(sample['fit_weight']).all() or np.any(sample['fit_weight'] <= 0):
            raise ValueError('Invalid sealed sample weights')


class HashOnlyTeacherStore:
    def __init__(self, days, artifacts):
        self.days, self.artifacts = {day.key: day for day in days}, artifacts

    def get(self, key):
        name = 'feature_inputs/' + key
        if not self.artifacts.complete(name):
            raise ValueError('Teacher first-use feature manifest missing')
        manifest = runner.read_json(self.artifacts.root / (name + '.json'))
        path = self.days[key].features
        action = path.with_name('actions.npz')
        expected = {str(p.resolve()) for p in (path, path.with_suffix('.json'), action, action.with_suffix('.json'))}
        if set(manifest) != expected:
            raise ValueError('Teacher feature manifest paths differ')
        for source, digest in manifest.items():
            if runner.sha(Path(source)) != digest:
                raise ValueError('Cached teacher feature/metadata changed')
        return None

    def rows(self, *args, **kwargs):
        raise RuntimeError('Recovery cannot build new teacher features')


def cached_teacher(original, days, store, seal, artifacts):
    sample = artifacts.load_npz('samples/teacher')
    for name in ('matrices/teacher', 'risk_scales'):
        if not artifacts.complete(name):
            raise ValueError('Completed teacher matrix and scales required')
    for key, _ in runner.sample_groups(sample):
        if not artifacts.complete('chunks/teacher/' + key):
            raise ValueError('Incomplete teacher chunk; recovery cannot rebuild')
    return original(days, HashOnlyTeacherStore(days, artifacts), seal, artifacts)


def teacher_wait(out):
    while runner.psutil.virtual_memory().available < 8 * 1024**3 or runner.free_commit_bytes() < 10 * 1024**3:
        value = dict(stage='WAITING_TEACHER_RESOURCES_8_10',
            available_ram=runner.psutil.virtual_memory().available,
            free_commit=runner.free_commit_bytes(), utc=datetime.now(timezone.utc).isoformat())
        runner.atomic_json(Path(out) / 'progress.json', value, replace=True)
        print(value, flush=True)
        time.sleep(30)


def scoped_fit(original, name, *args, **kwargs):
    if name != 'teacher':
        return original(name, *args, **kwargs)
    prior = runner.wait_resources
    runner.wait_resources = teacher_wait
    try:
        return original(name, *args, **kwargs)
    finally:
        runner.wait_resources = prior


@contextmanager
def operational_adapters():
    prepare, teacher, fit = runner.prepare_samples, runner.teacher_stage, runner.fit_once
    runner.prepare_samples = fast_prepare
    runner.teacher_stage = lambda *args, **kwargs: cached_teacher(teacher, *args, **kwargs)
    runner.fit_once = lambda name, *args, **kwargs: scoped_fit(fit, name, *args, **kwargs)
    try:
        yield
    finally:
        runner.prepare_samples, runner.teacher_stage, runner.fit_once = prepare, teacher, fit


def require_runtime_review(path):
    review = runner.read_json(path)
    expected = {
        'wrapper_sha256': runner.sha(Path(__file__)),
        'proposal_sha256': runner.sha(Path(__file__).with_name('CAUSAL_ROLLOUT_RUNTIME_RECOVERY_PROPOSAL.md')),
        'dependencies': runner.dependency_hashes(),
        'pins': PINS,
    }
    if review.get('status') != 'PASS_CAUSAL_ROLLOUT_RUNTIME_RECOVERY_REVIEW' or any(review.get(k) != v for k, v in expected.items()):
        raise ValueError('Exact operational recovery review required')
    if expected['dependencies']['train_causal_rollout.py'] != PINS['runner']:
        raise ValueError('Frozen scientific producer changed')
    return expected


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--runtime-review', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=runner.ROOT / 'causal_rollout_v1')
    parser.add_argument('--stage', choices=('all',), default='all')
    args, remaining = parser.parse_known_args()
    if args.out.resolve() != (runner.ROOT / 'causal_rollout_v1').resolve():
        raise ValueError('Recovery is bound to the existing output directory')
    remaining += ['--out', str(args.out), '--stage', args.stage]
    authority = require_runtime_review(args.runtime_review)
    receipt = runner.ROOT / 'causal_rollout_runtime_v1' / ('recovery_launch_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    runner.atomic_json(receipt, dict(authority=authority, argv=remaining,
        new_pid=runner.os.getpid(), original_pid=38048,
        review_sha256=runner.sha(args.runtime_review), teacher_resource_gate_gib=[8, 10],
        final_resource_gate_gib=[12, 16], scientific_parameters_changed=False))
    sys.argv = [str(Path(runner.__file__)), *remaining]
    with operational_adapters():
        runner.main()


if __name__ == '__main__':
    main()
