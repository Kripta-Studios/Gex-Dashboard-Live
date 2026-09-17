import json
from types import SimpleNamespace

import exchange_calendars as xcals
import pandas as pd
import pytest

from neural.jepa.multiscale_v1r1.artifacts import content_digest, digest
from neural.jepa.multiscale_v1r1.contract import ContractError
from neural.jepa.multiscale_v1r1.data_gate import build
from neural.jepa.multiscale_v1r1.inventory import build_inventory
from neural.jepa.multiscale_v1r1.source_reader import FeatureReader
from neural.jepa.multiscale_v1r1_audit.verify import audit


@pytest.fixture
def admission(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    day = '2025-01-02'
    for ticker in ('SPXW', 'SPY', 'QQQ'):
        folder = source / 'data_underlying_derived' / ticker
        folder.mkdir(parents=True)
        frame = pd.DataFrame({'timestamp': pd.date_range(day + ' 09:30', periods=391, freq='min'),
                              'open': 100., 'high': 101., 'low': 99., 'close': 100., 'tick_count': 10})
        frame.to_parquet(folder / f'{ticker}_20250102.parquet', index=False)
    # A later log proves nothing about the historical fixture's repairs.
    (source / 'data_underlying_derived/descarga_SPXW.log').write_text(
        '2026-07-02 01:00 [INFO] [CORRECCIÓN FILA] SPXW | 2026-07-01 09:30:00 | Ceros rellenados.\n'
        '2026-07-02 01:00 [INFO] ✓ SPXW_20260701 guardado y corregido usando Exp objetivo 20260701\n', encoding='utf-8')
    schedule = pd.DataFrame({'open': [pd.Timestamp(day + ' 14:30', tz='UTC')],
                              'close': [pd.Timestamp(day + ' 21:00', tz='UTC')]},
                             index=pd.DatetimeIndex([day], name='session'))
    monkeypatch.setattr(xcals, 'get_calendar', lambda *a, **k: SimpleNamespace(schedule=schedule))
    root = tmp_path / 'artifacts'
    root.mkdir()
    contract = tmp_path / 'contract.md'
    contract.write_text('synthetic contract')
    inv = root / 'inventory'
    gate = root / 'data_gate'
    build_inventory(source, inv, digest(contract), root / 'access_log.jsonl')
    build(inv, gate, digest(contract), root / 'access_log.jsonl')
    return source, root, inv, gate, contract


def test_DATA_001_metadata_is_not_admission(admission):
    _, _, inv, gate, contract = admission
    result = audit(inv, gate, contract)
    assert result['status'] == 'PASS_INDEPENDENT_AUDIT_OF_BLOCKED_SOURCE_ADMISSION'
    assert result['sources_rehashed'] == 3
    summary = json.loads((gate / 'data_gate_summary.json').read_text(encoding='utf-8'))
    assert summary['economic_evidence_state'] == 'BLOCKED_DATA'
    assert summary['feature_gate_executed'] is False


@pytest.mark.parametrize('mutation', ['admitted', 'reason', 'timestamp', 'provenance', 'outcome_access'])
def test_AUDIT_001_semantic_tampering_detected_after_rehash(admission, mutation):
    _, root, inv, gate, contract = admission
    summary_path = gate / 'data_gate_summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    if mutation == 'outcome_access':
        path = root / 'access_log.jsonl'
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        rows[-1]['stage'] = 'payoff_test'
        rows[-1].pop('record_sha256')
        rows[-1]['record_sha256'] = content_digest(rows[-1])
        path.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
    elif mutation == 'provenance':
        path = inv / 'provenance.json'
        evidence = json.loads(path.read_text(encoding='utf-8'))
        evidence['records'][0]['trade_date'] = '2025-01-02'
        path.write_text(json.dumps(evidence))
        inventory_path = inv / 'inventory_summary.json'
        inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
        inventory['provenance_sha256'] = digest(path)
        inventory_path.write_text(json.dumps(inventory))
        summary['inventory_summary_sha256'] = digest(inventory_path)
    else:
        path = gate / 'coverage.parquet'
        coverage = pd.read_parquet(path)
        if mutation == 'admitted':
            coverage.loc[0, 'feature_gate_admitted'] = True
        elif mutation == 'reason':
            coverage.loc[0, 'source_reason'] = 'ADMITTED'
        else:
            coverage.loc[0, 'trade_date'] = '2025-01-03'
        coverage.to_parquet(path, index=False)
        summary['coverage_sha256'] = digest(path)
        summary['coverage_content_sha256'] = content_digest(coverage.to_dict('records'))
    summary_path.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match='FAILED_AUDIT'):
        audit(inv, gate, contract)


def test_DATA_002_restricted_columns_and_native_cutoff(admission, tmp_path):
    source, _, inv, _, _ = admission
    manifest = pd.read_parquet(inv / 'source_manifest.parquet').to_dict('records')
    reader = FeatureReader(manifest, source, tmp_path / 'reader_access.jsonl')
    key = manifest[0]['source_id']
    start, end = '2025-01-02T09:30:00-05:00', '2025-01-02T11:30:00-05:00'
    with pytest.raises(ContractError, match='forbidden columns'):
        reader.read(key, ['timestamp', 'net_pnl'], start, end, 'feature_bar_prefix')
    frame = reader.read(key, ['timestamp', 'open'], start, end, 'feature_bar_prefix')
    assert len(frame) == 120
    assert frame.timestamp.max() < pd.Timestamp(end)


@pytest.mark.parametrize('new_day,accepted', [('20260914', True), ('20250602', False), ('20220729', False)])
def test_AUDIT_001_directory_growth_respects_fixed_period(admission, new_day, accepted):
    source, _, inv, gate, contract = admission
    original = source / 'data_underlying_derived/SPXW/SPXW_20250102.parquet'
    # File content is intentionally invalid: post-period additions must not be read.
    additional = original.with_name(f'SPXW_{new_day}.parquet')
    additional.write_bytes(b'not a parquet; metadata name only')
    if accepted:
        report = audit(inv, gate, contract)
        assert report['added_post_period_files_at_audit_start'] == [str(additional.resolve())]
        assert report['sources_rehashed'] == 3
    else:
        with pytest.raises(ValueError, match='new source inside or before'):
            audit(inv, gate, contract)


def test_AUDIT_001_missing_sealed_source_still_fails(admission):
    source, _, inv, gate, contract = admission
    (source / 'data_underlying_derived/SPXW/SPXW_20250102.parquet').unlink()
    with pytest.raises(ValueError, match='sealed inventory file disappeared'):
        audit(inv, gate, contract)


def test_TIME_002_XNYS_holiday_halfday_and_DST():
    schedule = xcals.get_calendar('XNYS', start='2025-01-01', end='2025-12-31').schedule
    assert pd.Timestamp('2025-01-01') not in schedule.index
    assert schedule.loc['2025-11-28', 'close'].tz_convert('America/New_York').hour == 13
    assert schedule.loc['2025-03-07', 'open'].hour == 14
    assert schedule.loc['2025-03-10', 'open'].hour == 13
