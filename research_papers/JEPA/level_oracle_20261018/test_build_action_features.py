"""Action projection consumes only pre-outcome columns and checks their seal."""
from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import build_action_features as runner
import features as f
from test_features import action, fixture, write_source


def test_projected_columns_and_action_freeze(tmp_path, monkeypatch):
    raw = fixture()
    source = tmp_path / 'source.npz'
    write_source(source, raw)
    source_meta = f.build_cache.read_day_metadata(source)
    day = tmp_path / 'engine'
    day.mkdir()
    actions_path = day / 'actions.parquet'
    pd.DataFrame([{**action(), 'FORBIDDEN_FUTURE_LABEL': 123456.}]).to_parquet(actions_path, index=False)
    f.build_cache.write_json(day / 'causal_freeze.json', {'actions.parquet': f._sha(actions_path)})
    f.build_cache.write_json(day / 'identity.json', dict(engine_sha256=f._dependencies()['level_engine.py'], metadata=source_meta))
    original = runner.pq.read_table
    calls = []
    def projected(path, columns):
        calls.append((Path(path).name, columns))
        assert columns == ['action_id', *f.ACTION_INPUT_NAMES]
        return original(path, columns=columns)
    monkeypatch.setattr(runner.pq, 'read_table', projected)
    target = tmp_path / 'actions.npz'
    assert runner.process_day((actions_path, source, target))['status'] == 'BUILT'
    assert runner.process_day((actions_path, source, target))['status'] == 'VERIFIED_EXISTING'
    assert len(calls) == 2
    with actions_path.open('ab') as stream:
        stream.write(b'tamper')
    with pytest.raises(ValueError, match='freeze/hash mismatch'):
        runner.process_day((actions_path, source, target))
    assert len(calls) == 2
