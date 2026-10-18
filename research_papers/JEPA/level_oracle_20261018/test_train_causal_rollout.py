"""Synthetic runner admission, resume, schema and causal scheduling checks."""
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import train_causal_rollout as t


def artifacts(tmp_path):
    return t.Artifacts(tmp_path, 'synthetic-binding')


def test_complete_artifact_rejects_tampering_and_orphan(tmp_path):
    a = artifacts(tmp_path)
    path = a.save_npz('day', {'x': np.array([1., 2.])})
    np.testing.assert_array_equal(a.load_npz('day')['x'], [1., 2.])
    with path.open('ab') as handle:
        handle.write(b'changed')
    with pytest.raises(ValueError, match='changed artifact'):
        a.load_npz('day')
    (tmp_path / 'orphan.npz').write_bytes(b'preserve')
    with pytest.raises(RuntimeError, match='Orphan'):
        a.save_npz('orphan', {'x': np.array([3.])})
    assert (tmp_path / 'orphan.npz').read_bytes() == b'preserve'


def test_os_lock_excludes_second_runner_and_releases(tmp_path):
    path = tmp_path / 'lock'
    with t.exclusive_lock(path):
        with pytest.raises(RuntimeError, match='Another process'):
            with t.exclusive_lock(path):
                pass
    with t.exclusive_lock(path):
        pass


def test_feature_store_rejects_coherent_pack_metadata_replacement(tmp_path, monkeypatch):
    feature_dir = tmp_path / 'input'
    feature_dir.mkdir()
    for name in ('states.npz', 'states.json', 'actions.npz', 'actions.json'):
        (feature_dir / name).write_text('first')
    day = SimpleNamespace(features=feature_dir / 'states.npz')
    store = object.__new__(t.VerifiedFeatureStore)
    store.cache, store.days, store.artifacts = {}, {'SPY/20240102': day}, artifacts(tmp_path / 'output')
    monkeypatch.setattr(t.base.FeatureStore, 'get', lambda self, key: {'synthetic': True})
    assert store.get('SPY/20240102')['synthetic']
    store.get('SPY/20240102')
    (feature_dir / 'states.npz').write_text('changed consistently')
    (feature_dir / 'states.json').write_text('changed consistently')
    with pytest.raises(ValueError, match='changed since first use'):
        store.get('SPY/20240102')


def test_prepare_reads_only_identities_and_reconstructs_global_topk(tmp_path):
    a = artifacts(tmp_path)
    days = [t.base.Day('SPY', date, Path(date), Path('unused')) for date in ('20230103', '20230705')]
    class Seal:
        extra = False
        def read(self, day, filename, columns):
            assert filename == 'actions.parquet'
            assert columns == ['action_id', 'state_i']
            n = 80 + int(self.extra)
            return pd.DataFrame({'action_id': np.arange(n), 'state_i': np.full(n, 60)})
    seal = Seal()
    t.prepare_samples(days, seal, a)
    teacher, final = a.load_npz('samples/teacher'), a.load_npz('samples/final')
    assert len(teacher['action_id']) == 32 and len(final['action_id']) == 64
    assert 'has_filled_today' not in teacher
    np.testing.assert_array_equal(final['has_filled_today'], np.tile([0, 1], 32))
    assert teacher['weight'].sum() == pytest.approx(1.)
    t.prepare_samples(days, seal, a)
    seal.extra = True
    with pytest.raises(ValueError, match='full-population sampling differs'):
        t.prepare_samples(days, seal, a)


def test_feature_schema_adds_only_observed_flag(monkeypatch):
    class Store:
        def rows(self, key, ids):
            return {}, np.arange(len(ids)), np.arange(len(ids))
    monkeypatch.setattr(t.base, 'flatten_gbt', lambda p, ai, si: np.ones((len(ai), 1954), np.float32))
    x = t.feature_rows(Store(), 'SPY/20240102', np.array([2, 2]), np.array([0, 1]))
    assert x.shape == (2, 1955) and x.dtype == np.float32
    np.testing.assert_array_equal(x[:, :1954], 1)
    np.testing.assert_array_equal(x[:, -1], [0, 1])
    with pytest.raises(ValueError, match='has_filled'):
        t.feature_rows(Store(), 'key', np.array([1]), np.array([2]))
    monkeypatch.setattr(t.base, 'flatten_gbt', lambda p, ai, si: np.ones((len(ai), 1934), np.float32))
    with pytest.raises(ValueError, match='1954'):
        t.feature_rows(Store(), 'key', np.array([1]))


def fixture_actions():
    actions = pd.DataFrame({'action_id': [0, 1, 2, 3, 4], 'state_i': [60, 60, 61, 64, 64]})
    labels = pd.DataFrame({'action_id': [0, 1, 2, 3, 4],
        'status': ['NO_FILL', 'FILLED', 'FILLED', 'FILLED', 'FILLED'],
        'exit_i': [61, 62, 63, 66, 66], 'net_base': [0., 500., -2., 100., -3.],
        'net_adverse': [0., 498., -4., 98., -5.], 'reason': ['NO_FILL', 'TARGET', 'STOP', 'TARGET', 'STOP'],
        'hold_minutes': [0, 1, 1, 1, 1]})
    return actions, labels


def test_flag_scheduler_loss_fill_switches_h_and_no_fill_never_replaces():
    actions, labels = fixture_actions()
    scores = np.array([[10., 10.], [9., 9.], [8., 8.], [20., -5.], [-1., 7.]])
    attempts, ledger = t.evaluate_flag_policy(actions, labels, scores, 0.)
    assert attempts.action_id.tolist() == [0, 2, 4]
    assert attempts.has_filled_before.tolist() == [0, 0, 1]
    assert ledger.action_id.tolist() == [2, 4]
    assert ledger.net_base.sum() == -5  # no terminal penalty in economic return
    assert labels.net_base.tolist() == [0., 500., -2., 100., -3.]


def test_validation_constraint_rejects_profitable_zero_day_and_null():
    candidates = {}
    for model in t.MODELS:
        for threshold in t.THRESHOLDS:
            candidates[t.policy_id(model, threshold)] = dict(zero_fill_expected_days=1,
                tickers={ticker: {'net_base': 1e9} for ticker in t.TICKERS})
    scales = {ticker: 100. for ticker in t.TICKERS}
    result = t.select_validation(candidates, scales)
    assert result['selected_policy'] is None and len(result['frozen_candidates']) == 6
    for key in ('net_control__0', 'causal_residual__0'):
        candidates[key] = dict(zero_fill_expected_days=0,
            tickers={ticker: {'net_base': -10.} for ticker in t.TICKERS})
    result = t.select_validation(candidates, scales)
    assert result['selected_policy']['policy'] == 'net_control__0'
    assert result['selected_policy']['score'] < 0  # never a profitability claim


def test_review_binds_exact_implementation(tmp_path):
    path = tmp_path / 'review.json'
    t.atomic_json(path, dict(status='PASS_CAUSAL_ROLLOUT_IMPLEMENTATION_REVIEW', dependencies={'runner': 'a'}))
    t.require_review(path, {'runner': 'a'})
    with pytest.raises(ValueError, match='exact code'):
        t.require_review(path, {'runner': 'b'})


def test_interrupted_fit_cannot_automatically_refit(tmp_path, monkeypatch):
    a = artifacts(tmp_path)
    monkeypatch.setattr(t, 'wait_resources', lambda out: None)
    calls = []
    class BrokenModel:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def fit(self, *args, **kwargs):
            raise MemoryError('fixture interruption')
    monkeypatch.setattr(t.lgb, 'LGBMRegressor', BrokenModel)
    x, y, w = np.zeros((2, 1954), np.float32), np.zeros(2), np.ones(2)
    with pytest.raises(MemoryError):
        t.fit_once('teacher', x, y, w, a)
    with pytest.raises(RuntimeError, match='automatic refit prohibited'):
        t.fit_once('teacher', x, y, w, a)
    assert len(calls) == 1 and (tmp_path / 'models/teacher.fit_started.json').exists()


def test_matrix_assembly_requires_complete_identity_chunks(tmp_path):
    a = artifacts(tmp_path)
    sample = {'ticker': np.array(['SPY', 'SPY']), 'date': np.array(['20240102', '20240102']), 'action_id': np.array([1, 1])}
    a.save_npz('chunks/final/SPY/20240102', {'positions': np.array([0, 1]), 'x': np.ones((2, 1955), np.float32)})
    x = t.assemble_matrix('final', sample, a, 1955)
    assert x.shape == (2, 1955)
    del x
    resumed = t.assemble_matrix('final', sample, a, 1955)
    np.testing.assert_array_equal(resumed, 1.)


def test_rollout_choices_committed_before_labels(tmp_path, monkeypatch):
    a = artifacts(tmp_path)
    model_path = tmp_path / 'models/teacher.txt'
    model_path.parent.mkdir()
    model_path.write_text('synthetic')
    a.finish('models/teacher', [model_path])
    t.atomic_json(tmp_path / 'risk_scales.json', {ticker: 10. for ticker in t.TICKERS})
    a.finish('risk_scales', [tmp_path / 'risk_scales.json'])
    sample = dict(ticker=np.array(['SPY', 'SPY']), date=np.array(['20240102', '20240102']),
        action_id=np.array([0, 0]), has_filled_today=np.array([0, 1], np.int8))
    a.save_npz('samples/final', sample)
    day = t.base.Day('SPY', '20240102', Path('unused'), Path('unused'))
    actions = pd.DataFrame({'action_id': [0], 'state_i': [60]})
    labels = pd.DataFrame({'action_id': [0], 'status': ['FILLED'], 'exit_i': [62], 'net_base': [-2.]})
    reads = []
    class Seal:
        def read(self, day, filename, columns=None):
            reads.append(filename)
            if filename == 'labels.parquet':
                assert a.complete('teacher_choices/' + day.key)
                return labels
            return actions
        def check(self, *args):
            return 'fixture'
    monkeypatch.setattr(t.lgb, 'Booster', lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(t, 'score_actions', lambda *args, **kwargs: np.array([[-1., -1.]]))
    t.rollout_stage([day], SimpleNamespace(get=lambda key: {}), Seal(), a)
    target = a.load_npz('rollouts/' + day.key)
    np.testing.assert_array_equal(target['residual'], [8., -2.])
    reads.clear()
    t.rollout_stage([day], SimpleNamespace(get=lambda key: {}), Seal(), a)
    assert 'labels.parquet' not in reads


def test_test_stage_requires_selection_or_null_freeze(tmp_path):
    with pytest.raises(ValueError, match='must be frozen before test'):
        t.evaluate_stage('test', [], [], None, None, artifacts(tmp_path))


def test_validation_cannot_rebuild_authority_after_test_evidence(tmp_path):
    (tmp_path / 'test').mkdir()
    (tmp_path / 'test/partial').write_text('preserved')
    with pytest.raises(ValueError, match='cannot rebuild authority'):
        t.evaluate_stage('validation', [], [], None, None, artifacts(tmp_path))


def test_exhaustive_rollout_identities_reject_corrupt_targets():
    keys = t.rollout.ActionRows(np.array([0, 1]), np.array([60, 61]))
    outcomes = t.rollout.OutcomeRows(np.array([0, 1]), np.array(['FILLED', 'NO_FILL']),
        np.array([62, 62]), np.array([-2., 0.]))
    choices = t.rollout.freeze_choices(keys, -np.ones((2, 2)))
    values = t.rollout.fixed_policy_values(keys, outcomes, choices, 10.)
    residual = t.rollout.residual_targets(keys, outcomes, values)
    assert t.verify_rollout_identities(keys, outcomes, values, residual, 10.)['filled'] == 1
    broken = residual.copy()
    broken[0, 0] += 1
    with pytest.raises(ValueError, match='Residual h identity'):
        t.verify_rollout_identities(keys, outcomes, values, broken, 10.)
    broken = residual.copy()
    broken[1, :] = 1
    with pytest.raises(ValueError, match='NO_FILL'):
        t.verify_rollout_identities(keys, outcomes, values, broken, 10.)


@pytest.mark.parametrize('stage', ['final', 'validation'])
def test_final_consumers_reject_mutated_risk_scales(tmp_path, stage):
    a = artifacts(tmp_path)
    path = tmp_path / 'risk_scales.json'
    t.atomic_json(path, {'SPY': 10.})
    a.finish('risk_scales', [path])
    path.write_text('{"SPY": 1000.}')
    with pytest.raises(ValueError, match='changed artifact'):
        if stage == 'final':
            t.final_fit_stage([], None, a)
        else:
            t.evaluate_stage('validation', [], [], None, None, a)


def test_final_stage_two_targets_share_matrix_weights_and_resume_without_refit(tmp_path, monkeypatch):
    a = artifacts(tmp_path)
    t.atomic_json(tmp_path / 'risk_scales.json', {ticker: 10. for ticker in t.TICKERS})
    a.finish('risk_scales', [tmp_path / 'risk_scales.json'])
    sample = dict(ticker=np.repeat(np.array(t.TICKERS), 2), date=np.full(6, '20240102'),
        action_id=np.zeros(6, np.int64), has_filled_today=np.tile([0, 1], 3), fit_weight=np.ones(6))
    a.save_npz('samples/final', sample)
    for key, rows in t.sample_groups(sample):
        choice = a.save_npz('teacher_choices/' + key, dict(choices=np.zeros((316, 2), np.int64)))
        a.save_npz('rollouts/' + key, dict(positions=rows, net=np.array([-2., -2.]), residual=np.array([8., -2.]),
            choice_sha256=np.array(t.sha(choice)),
            identities_checked=np.array('{"status":"PASS_EXHAUSTIVE_FIXED_TEACHER_IDENTITIES"}')))
    monkeypatch.setattr(t, 'feature_rows', lambda store, key, ids, h: np.column_stack((np.ones((len(ids), 1954), np.float32), np.asarray(h, np.float32))))
    monkeypatch.setattr(t, 'wait_resources', lambda out: None)
    calls = []
    class FakeRegressor:
        def __init__(self, **kwargs):
            self.booster_ = SimpleNamespace(save_model=lambda path: Path(path).write_text('synthetic-model'))
        def fit(self, x, y, sample_weight):
            calls.append((id(x), id(sample_weight), y.copy(), sample_weight.copy(), x.shape))
    monkeypatch.setattr(t.lgb, 'LGBMRegressor', FakeRegressor)
    monkeypatch.setattr(t.lgb, 'Booster', lambda **kwargs: SimpleNamespace())
    store = SimpleNamespace(get=lambda key: {})
    t.final_fit_stage([], store, a)
    assert len(calls) == 2 and calls[0][:2] == calls[1][:2]
    assert calls[0][4] == (6, 1955)
    np.testing.assert_array_equal(calls[0][2], np.full(6, -.2))
    np.testing.assert_array_equal(calls[1][2], np.tile([.8, -.2], 3))
    t.final_fit_stage([], store, a)
    assert len(calls) == 2


def test_evaluation_integration_six_policies_null_freeze_test_and_resume(tmp_path, monkeypatch):
    a = artifacts(tmp_path)
    t.atomic_json(tmp_path / 'risk_scales.json', {ticker: 10. for ticker in t.TICKERS})
    a.finish('risk_scales', [tmp_path / 'risk_scales.json'])
    for name in t.MODELS:
        path = tmp_path / ('models/' + name + '.txt')
        path.parent.mkdir(exist_ok=True)
        path.write_text('fixture-' + name)
        a.finish('models/' + name, [path])
    days = [t.base.Day(ticker, date, Path('unused'), Path('unused')) for date in ('20250102', '20260102') for ticker in t.TICKERS]
    dates = ['20250102', '20250103', '20260102']
    actions, labels = fixture_actions()
    scores = np.array([[10., 10.], [9., 9.], [8., 8.], [20., -5.], [-1., 7.]])
    score_calls, label_reads = [], []
    def score(*args, **kwargs):
        score_calls.append(args[2].key)
        return scores.copy()
    class Seal:
        def read(self, day, filename, columns=None):
            if filename == 'actions.parquet':
                return actions
            period = 'validation' if day.date.startswith('2025') else 'test'
            assert a.complete(period + '/predictions/' + day.key)
            if period == 'test':
                assert a.complete('validation_freeze')
            label_reads.append(day.key)
            return labels
        def check(self, *args):
            return 'fixture'
    monkeypatch.setattr(t.lgb, 'Booster', lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(t, 'score_actions', score)
    result = t.evaluate_stage('validation', days, dates, SimpleNamespace(get=lambda key: {}), Seal(), a)
    assert len(result) == 6
    freeze = t.read_json(tmp_path / 'validation_freeze.json')
    assert freeze['selected_policy'] is None and len(freeze['frozen_candidates']) == 6
    ledger = pd.read_parquet(tmp_path / 'validation/daily/SPY/20250102_ledger.parquet')
    selected = ledger.loc[ledger.policy == 'net_control__0']
    assert selected.action_id.tolist() == [2, 4]
    assert selected.has_filled_before.tolist() == [0, 1]
    assert selected.net_base.sum() == -5
    counts = (len(score_calls), len(label_reads))
    t.evaluate_stage('validation', days, dates, SimpleNamespace(get=lambda key: {}), Seal(), a)
    assert counts == (len(score_calls), len(label_reads))
    t.evaluate_stage('test', days, dates, SimpleNamespace(get=lambda key: {}), Seal(), a)
    assert len(score_calls) == 12 and len(label_reads) == 6
    t.evaluate_stage('test', days, dates, SimpleNamespace(get=lambda key: {}), Seal(), a)
    assert len(score_calls) == 12 and len(label_reads) == 6
