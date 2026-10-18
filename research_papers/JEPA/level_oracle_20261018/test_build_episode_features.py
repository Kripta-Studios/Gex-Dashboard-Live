"""Synthetic publication/resume/projection checks for prepared episode exports."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import build_episode_features as b
from test_episode_features import fixture


def source(tmp_path):
    states, levels = fixture([100.] * 316)
    states['future_outcome_never_projected'] = 999999.
    levels['future_label_never_projected'] = -999999.
    day = tmp_path / 'causal'
    day.mkdir()
    states.to_parquet(day / 'states.parquet', index=False)
    levels.to_parquet(day / 'levels.parquet', index=False)
    row = dict(ticker='QQQ', date='20230103', split='SYNTHETIC', day_root=str(day),
               states_sha256=b.sha(day / 'states.parquet'), levels_sha256=b.sha(day / 'levels.parquet'))
    return row, tmp_path / 'outputs', dict(test='SYNTHETIC_ONLY')


def test_projection_roundtrip_and_exact_verified_resume(tmp_path, monkeypatch):
    row, output, contract = source(tmp_path)
    original = b.pq.read_table
    projections = []

    def projected(path, *, columns):
        projections.append(columns)
        return original(path, columns=columns)

    monkeypatch.setattr(b.pq, 'read_table', projected)
    first = b.process_day(row, output, contract)
    target = output / 'QQQ/20230103/episodes.npz'
    initial = target.read_bytes()
    second = b.process_day(row, output, contract)
    assert first['status'] == 'BUILT' and second['status'] == 'VERIFIED_EXISTING'
    assert projections == [list(b.STATE_COLUMNS), list(b.LEVEL_COLUMNS)]
    assert target.read_bytes() == initial
    with np.load(target, allow_pickle=False) as stored:
        assert set(stored.files) == {'state_i', 'values', 'valid'}
        assert stored['values'].shape == (316, 35)
        assert stored['values'].dtype == np.float64
        assert stored['valid'].dtype == bool
    assert not any(name.endswith('_id') for name in b.ef.FEATURE_NAMES)


def test_partial_preserved_before_build(tmp_path):
    row, output, contract = source(tmp_path)
    target = output / 'QQQ/20230103/episodes.npz'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'INTERRUPTED_SYNTHETIC_NPZ')
    orphan_hash = b.sha(target)
    assert b.process_day(row, output, contract)['status'] == 'BUILT'
    manifests = list((output / '_preserved_partials').glob('*/manifest.json'))
    assert len(manifests) == 1
    preserved = b.read_json(manifests[0])['files'][0]
    assert preserved['sha256'] == orphan_hash
    assert Path(preserved['preserved']).read_bytes() == b'INTERRUPTED_SYNTHETIC_NPZ'


def test_complete_corruption_and_binding_change_fail_without_overwrite(tmp_path):
    row, output, contract = source(tmp_path)
    b.process_day(row, output, contract)
    target = output / 'QQQ/20230103/episodes.npz'
    before = target.read_bytes()
    with pytest.raises(ValueError, match='binding'):
        b.process_day(row, output, dict(test='OTHER'))
    assert target.read_bytes() == before
    target.write_bytes(before + b'CORRUPTION')
    with pytest.raises(ValueError, match='hash'):
        b.process_day(row, output, contract)
    assert target.read_bytes() == before + b'CORRUPTION'
