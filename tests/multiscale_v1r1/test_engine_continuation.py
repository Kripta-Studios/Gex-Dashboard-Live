import ast
import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from neural.jepa.multiscale_v1r1.artifacts import digest
from neural.jepa.multiscale_v1r1.bootstrap import paired_bootstrap
from neural.jepa.multiscale_v1r1.contract import ContractError
from neural.jepa.multiscale_v1r1.checkpoint import save_checkpoint, verify_resume
from neural.jepa.multiscale_v1r1.interactions import build_event
from neural.jepa.multiscale_v1r1.payoff import simulate_action
from neural.jepa.multiscale_v1r1.scenarios import run_scenarios
from neural.jepa.multiscale_v1r1.synthetic_engine import SyntheticOutcomes
from neural.jepa.multiscale_v1r1.synthetic_fixtures import action_quotes, month_events, source_fixture
from neural.jepa.multiscale_v1r1_audit.engine import expected_action, reconstruct_ledger
from neural.jepa.multiscale_v1r1_audit.tensor import audit_tensor_fixture


def test_integrated_edge_scenarios(tmp_path):
    result = run_scenarios(tmp_path / 'scenarios')
    assert result['status'] == 'PASS_SYNTHETIC_SCENARIOS'
    assert result['broker_submission'] is False
    capture = [json.loads(line) for line in (tmp_path / 'scenarios/offline_capture.jsonl').read_text().splitlines()]
    assert [r['revision'] for r in capture] == [0, 1]
    assert capture[1]['supersedes_sha256'] == capture[0]['record_sha256']


def test_synthetic_outcomes_cannot_precede_freeze(tmp_path):
    store = SyntheticOutcomes(tmp_path, '1' * 64)
    store.begin_fold('202501')
    with pytest.raises(ContractError, match='before freeze'):
        store.month('202501')
    with pytest.raises(ContractError, match='future'):
        store.month('202502')
    assert not list(tmp_path.glob('*.json'))


def test_checkpoint_requires_exact_code_and_every_dependency(tmp_path):
    code = tmp_path / 'code.py'
    code.write_bytes(b'original code')
    source = tmp_path / 'sealed.bin'
    source.write_bytes(b'original data')
    save_checkpoint(tmp_path, '202501', [code], '1' * 64)
    assert verify_resume(tmp_path, '1' * 64)['month'] == '202501'
    source.write_bytes(b'changed data')
    with pytest.raises(ContractError, match='dependency changed'):
        verify_resume(tmp_path, '1' * 64)
    source.write_bytes(b'original data')
    code.write_bytes(b'changed code')
    with pytest.raises(ContractError, match='code changed'):
        verify_resume(tmp_path, '1' * 64)


def test_independent_execution_detects_semantic_strike_cost_deadline_and_overlap():
    event = month_events('202501')[0]
    quotes = action_quotes(event)
    actual = simulate_action(quotes, event['ticker'], event['trade_date'], event['decision_timestamp'], 0)
    expected = expected_action(event, 0, quotes)
    assert actual == expected
    strike = deepcopy(actual)
    strike['contract_identity'][-1] = '126.0'
    assert strike != expected and strike['base'] == expected['base']
    commission = deepcopy(actual)
    commission['base']['net_dollar_pnl'] = str(float(commission['base']['net_dollar_pnl']) + 1.3)
    assert commission != expected
    late = deepcopy(actual)
    late['actual_exit_timestamp'] = (pd.Timestamp(late['deadline']) + pd.Timedelta(seconds=1)).isoformat()
    assert late != expected
    decision = {k: event[k] for k in ('event_id', 'ticker', 'month', 'trade_date', 'decision_timestamp')}
    decision['action_id'] = 0
    following = dict(decision, event_id='second', decision_timestamp=(pd.Timestamp(event['decision_timestamp']) + pd.Timedelta(minutes=1)).isoformat())
    ledger = reconstruct_ledger([decision, following], {event['event_id']: {'0': actual}})
    assert ledger[1]['reason'] == 'REJECT_OPEN_POSITION'


def test_paired_bootstrap_includes_zero_days_and_identical_policies():
    calendar = {'202501': ['2025-01-02', '2025-01-03', '2025-01-06', '2025-01-07', '2025-01-08', '2025-01-09']}
    daily = {('SPXW', '2025-01-02'): [2., 3., 1., 1., 2.]}
    result = paired_bootstrap(daily, daily, calendar)
    assert result['admitted_days'] == 6
    assert result['metrics']['paired_difference']['pnl']['SPXW']['finite_only_interval'] == [0., 0.]
    assert result['metrics']['primary']['pf']['SPY']['undefined_draws'] == 10000


def test_independent_full_tensor_and_slot_tampering(tmp_path):
    frame, greek, oi, prior = source_fixture()
    event = build_event(frame, prior, greek, oi, 'SPXW', '2025-01-10',
                        pd.Timestamp('2025-01-10 11:35', tz='America/New_York'), 99.8)
    frame.to_parquet(tmp_path / 'bars.parquet', index=False)
    greek.to_parquet(tmp_path / 'greeks.parquet', index=False)
    oi.to_parquet(tmp_path / 'oi.parquet', index=False)
    for day, source in prior.items():
        source.to_parquet(tmp_path / f'ib_{day}.parquet')
    for key in ('x5', 'm5', 'x15', 'm15', 'static'):
        np.save(tmp_path / f'{key}.npy', event[key])
    (tmp_path / 'identity.json').write_text(json.dumps(dict(day='2025-01-10', ticker='SPXW', decision='2025-01-10T11:35:00-05:00', prior_close=99.8)))
    assert audit_tensor_fixture(tmp_path)['numeric_components'] == 46020
    event['x5'][0, 5, 0] += 1
    np.save(tmp_path / 'x5.npy', event['x5'])
    # Even a newly computed content hash cannot make wrong geometry pass.
    assert digest(tmp_path / 'x5.npy')
    with pytest.raises(ValueError, match='tensor mismatch'):
        audit_tensor_fixture(tmp_path)


def test_all_independent_auditors_have_no_evaluator_calculation_imports():
    root = Path(__file__).resolve().parents[2] / 'neural/jepa/multiscale_v1r1_audit'
    for path in root.glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and 'multiscale_v1r1' in node.module:
                assert node.module == 'neural.jepa.multiscale_v1r1.contract', path
            if isinstance(node, ast.Import):
                assert all('multiscale_v1r1.' not in alias.name for alias in node.names), path
