"""Synthetic operational recovery tests: no fit and no market data."""
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import run_causal_rollout_resource_recovery as recovery

r = recovery.runner


def prepared(tmp_path):
    a = r.Artifacts(tmp_path / 'out', 'fixture')
    days, sources = [], {}
    for role, date in [('teacher', '20230103'), ('final', '20230705')]:
        folder = tmp_path / date
        folder.mkdir()
        path = folder / 'actions.parquet'
        path.write_bytes(b'full source includes selected AND unselected actions')
        day = r.base.Day('SPY', date, folder, folder / 'states.npz')
        days.append(day)
        sources[str(path)] = r.sha(path)
        a.save_npz('samples/' + role, dict(n_days=np.array(1), action_id=np.array([0]), fit_weight=np.array([1.])))
    a.finish('prepare', [a.root / 'samples/teacher.npz', a.root / 'samples/final.npz'], dict(source_action_hashes=sources))
    pins = dict(binding='fixture', prepare=r.sha(a.marker('prepare')),
        teacher=r.sha(a.root / 'samples/teacher.npz'), final=r.sha(a.root / 'samples/final.npz'))
    seal = SimpleNamespace(check=lambda day, filename: r.sha(day.oracle / filename))
    return a, days, seal, pins


def test_full_input_hash_resume_and_changed_unselected_source(tmp_path):
    a, days, seal, pins = prepared(tmp_path)
    counts = {'teacher': (1, 1), 'final': (1, 1)}
    recovery.fast_prepare(days, seal, a, pins=pins, counts=counts)
    (days[0].oracle / 'actions.parquet').write_bytes(b'only an unselected action changes')
    with pytest.raises(ValueError, match='including unselected'):
        recovery.fast_prepare(days, seal, a, pins=pins, counts=counts)


@pytest.mark.parametrize('changed', ['prepare', 'sample', 'population'])
def test_fast_resume_rejects_checkpoint_or_population_change(tmp_path, changed):
    a, days, seal, pins = prepared(tmp_path)
    if changed == 'prepare':
        with a.marker('prepare').open('ab') as f:
            f.write(b' ')
    elif changed == 'sample':
        with (a.root / 'samples/final.npz').open('ab') as f:
            f.write(b' ')
    else:
        days = days[:1]
    with pytest.raises(ValueError):
        recovery.fast_prepare(days, seal, a, pins=pins, counts={'teacher': (1, 1), 'final': (1, 1)})


def test_hash_only_features_reject_metadata_replacement_and_no_build(tmp_path):
    a, days, _, _ = prepared(tmp_path)
    day = days[0]
    paths = [day.features, day.features.with_suffix('.json'), day.features.with_name('actions.npz'), day.features.with_name('actions.json')]
    for path in paths:
        path.write_bytes(b'first-use verified fixture')
    manifest = a.root / ('feature_inputs/' + day.key + '.json')
    r.atomic_json(manifest, {str(p.resolve()): r.sha(p) for p in paths})
    a.finish('feature_inputs/' + day.key, [manifest])
    store = recovery.HashOnlyTeacherStore(days, a)
    assert store.get(day.key) is None
    with pytest.raises(RuntimeError, match='cannot build'):
        store.rows(day.key, [0])
    paths[1].write_bytes(b'coherent replacement metadata')
    with pytest.raises(ValueError, match='metadata changed'):
        store.get(day.key)


def test_missing_teacher_chunk_fails_before_stage(tmp_path):
    _, days, seal, _ = prepared(tmp_path)
    # A separate fixture artifact supplies the minimal full teacher keys.
    b = r.Artifacts(tmp_path / 'second', 'fixture')
    b.save_npz('samples/teacher', dict(ticker=np.array(['SPY']), date=np.array(['20230103']), action_id=np.array([0])))
    for name in ('matrices/teacher', 'risk_scales'):
        b.save_npz(name, {'x': np.array([1])})
    with pytest.raises(ValueError, match='Incomplete teacher chunk'):
        recovery.cached_teacher(lambda *args: pytest.fail('stage must not run'), days, None, seal, b)


def test_teacher_gate_scope_restored_before_final_and_after_exception(monkeypatch):
    original_wait = r.wait_resources
    calls = []
    def original(name, *args, **kwargs):
        calls.append((name, r.wait_resources))
        if name == 'teacher':
            raise RuntimeError('fixture gate wait, no estimator')
    with pytest.raises(RuntimeError):
        recovery.scoped_fit(original, 'teacher')
    assert r.wait_resources is original_wait
    recovery.scoped_fit(original, 'net_control')
    recovery.scoped_fit(original, 'causal_residual')
    assert calls == [('teacher', recovery.teacher_wait), ('net_control', original_wait), ('causal_residual', original_wait)]


def test_interrupted_fit_still_cannot_retry(tmp_path):
    a = r.Artifacts(tmp_path, 'fixture')
    r.atomic_json(tmp_path / 'models/teacher.fit_started.json', {'preserved': True})
    with pytest.raises(RuntimeError, match='automatic refit prohibited'):
        recovery.scoped_fit(r.fit_once, 'teacher', np.zeros((2, 1954), np.float32), np.zeros(2), np.ones(2), a)


def test_resource_gate_precedes_estimator(monkeypatch):
    called = []
    monkeypatch.setattr(recovery, 'teacher_wait', lambda out: (_ for _ in ()).throw(RuntimeError('waiting')))
    def original(name):
        r.wait_resources(Path('unused'))
        called.append('estimator')
    with pytest.raises(RuntimeError, match='waiting'):
        recovery.scoped_fit(original, 'teacher')
    assert called == []
