"""Synthetic contract tests; never open the ThetaData archive."""

from copy import deepcopy
import hashlib
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from neural.jepa.local_snapshot_schema_v1 import GREEK_COLUMNS, OI_COLUMNS
from neural.jepa.local_snapshot_source_v1 import (
    AUTHORIZATION,
    diagnose,
    read_projected,
    run,
    sample_asof,
    source_path,
)


HASHES = {'greeks': 'a'*64, 'oi': 'b'*64}


def greek(**overrides):
    row = dict(symbol='SPXW', expiration='2023-01-03', trade_date='2023-01-03',
               right='C', strike='100.0', interval_used='1m',
               timestamp='2023-01-03T09:30:00',
               underlying_timestamp='2023-01-03T09:29:59.999999',
               underlying_price='100.5000')
    row.update(overrides)
    return row


def oi(**overrides):
    row = dict(symbol='SPXW', expiration='2023-01-03', trade_date='2023-01-03',
               right='CALL', strike='100', interval_used='daily',
               timestamp='2023-01-03T09:00:00', open_interest=12)
    row.update(overrides)
    return row


def result(greeks=None, oi_rows=None):
    return diagnose([greek()] if greeks is None else greeks,
                    [oi()] if oi_rows is None else oi_rows, 'SPXW', HASHES)


def test_exact_sample_grid_age_and_oi_format():
    value = result()
    assert value['greek_row_count'] == value['oi_row_count'] == 1
    assert len(value['samples']) == 60
    first = value['samples'][0]
    assert first == dict(quote_timestamp='2023-01-03T09:30:00-05:00',
                         research_available_at='2023-01-03T09:31:00-05:00',
                         mask=True, reason=None, price='100.5',
                         underlying_timestamp='2023-01-03T09:29:59.999999-05:00',
                         underlying_age_ms='0.001', source_rows=1)
    assert value['samples'][1]['reason'] == 'MISSING_SAMPLE'
    assert value['samples'][1]['source_rows'] == 0
    assert value['oi'][0]['classification'] == 'ELIGIBLE_REPORTED_PREOPEN'
    assert value['missing_oi_contracts'] == value['ineligible_oi_contracts'] == []
    assert value['prior_close_semantics_verified'] is False


@pytest.mark.parametrize('fault', [
    {'timestamp': None},
    {'interval_used': '30s'},
    {'interval_used': '5m'},
    {'symbol': 'SPY'},
    {'expiration': '2023-01-04'},
    {'trade_date': '2023-01-04'},
    {'underlying_timestamp': '2023-01-03T09:30:01'},
    {'timestamp': '2023-01-03T09:30:30'},
    {'timestamp': '2023-01-03T10:30:00'},
    {'timestamp': '2023-01-03T09:30:00.0000001'},
])
def test_invalid_greek_row_fails_closed(fault):
    with pytest.raises(ValueError):
        result([greek(**fault)])


@pytest.mark.parametrize('second', [
    {'strike': '100.00'},
    {'timestamp': '2023-01-03T14:30:00+00:00'},
])
def test_duplicate_contract_numeric_or_timezone(second):
    with pytest.raises(ValueError, match='duplicate'):
        result([greek(), greek(**second)])


def test_invalid_price_precedes_cross_contract_disagreement():
    rows = [greek(underlying_price='0'), greek(right='PUT', strike='101',
                                                 underlying_price='101')]
    sample = result(rows, [])['samples'][0]
    assert sample['reason'] == 'INVALID_PRICE'
    assert sample['source_rows'] == 2
    assert sample['price'] is sample['underlying_timestamp'] is sample['underlying_age_ms'] is None
    rows[0]['underlying_price'] = 'NaN'
    assert result(rows, [])['samples'][0]['reason'] == 'INVALID_PRICE'


def test_cross_contract_disagreement_masks_without_selection():
    sample = result([greek(), greek(right='P', strike='101', underlying_price='101')], [])['samples'][0]
    assert sample['reason'] == 'CROSS_CONTRACT_DISAGREEMENT'
    assert sample['mask'] is False and sample['price'] is None


def test_oi_order_flags_and_missing_contracts():
    rows = [greek(strike='200', right='P'), greek(strike='100', right='C'),
            greek(strike='150', right='C')]
    ledger = [oi(strike='100', open_interest=0),
              oi(right='PUT', strike='200.0', open_interest=0,
                 timestamp='2023-01-03T09:31:00'),
              oi(right='PUT', strike='50', open_interest=5)]
    value = result(rows, ledger)
    assert [(item['right'], item['strike']) for item in value['oi']] == [
        ('CALL', '100'), ('PUT', '50'), ('PUT', '200')]
    assert value['oi'][-1]['classification'] == 'AFTER_OPEN'
    assert value['oi'][-1]['zero'] and value['oi'][-1]['after_open']
    assert value['missing_oi_contracts'] == [{'right': 'CALL', 'strike': '150'}]
    assert value['ineligible_oi_contracts'] == [
        {'right': 'CALL', 'strike': '100'}, {'right': 'PUT', 'strike': '200'}]


def test_integral_float_oi_is_an_integer():
    assert result(oi_rows=[oi(open_interest=12.0)])['oi'][0]['open_interest'] == 12


@pytest.mark.parametrize('second', [
    {'strike': '100.0'},
    {'open_interest': '-1', 'strike': '101'},
    {'open_interest': 'NaN', 'strike': '101'},
    {'open_interest': 1.5, 'strike': '101'},
    {'interval_used': '1m', 'strike': '101'},
    {'timestamp': '2023-01-04T06:30:00', 'strike': '101'},
])
def test_bad_oi_fails_closed(second):
    with pytest.raises(ValueError):
        result([greek()], [oi(), oi(**second)])


def test_asof_rejects_early_and_masked():
    sample = result()['samples'][0]
    with pytest.raises(ValueError, match='early'):
        sample_asof(sample, '2023-01-03T09:30:59.999999-05:00')
    assert sample_asof(sample, '2023-01-03T09:31:00-05:00') == sample
    assert sample_asof(result([])['samples'][0], '2023-01-03T09:31:00-05:00') is None


def test_greek_projection_native_filter_excludes_forbidden_and_future(tmp_path):
    rows = [greek(), greek(timestamp='2023-01-03T10:30:00', underlying_price='999')]
    table = pa.Table.from_pylist([dict(row, bid='SECRET_BID', delta=123, iv=555)
                                 for row in rows])
    table = table.set_column(table.schema.get_field_index('timestamp'), 'timestamp',
                             table['timestamp'].cast(pa.large_string()))
    path = tmp_path / 'greeks.parquet'
    pq.write_table(table, path)
    projected = read_projected(path, 'greeks')
    assert len(projected) == 1
    assert set(projected[0]) == set(GREEK_COLUMNS)
    assert projected[0]['underlying_price'] == '100.5000'


@pytest.mark.parametrize('bad_clock', [
    '2023-01-03 11:00:00', '2023-01-03T11:00:00-05:00',
    '2023-01-03T11:00:00.1234567', '2023-01-04T11:00:00',
])
def test_native_clock_gate_scans_rows_outside_first_hour(tmp_path, bad_clock):
    table = pa.Table.from_pylist([dict(greek(), bid='SECRET'),
                                  dict(greek(timestamp=bad_clock), bid='SECRET')])
    table = table.set_column(table.schema.get_field_index('timestamp'), 'timestamp',
                             table['timestamp'].cast(pa.large_string()))
    path = tmp_path / 'greeks.parquet'
    pq.write_table(table, path)
    with pytest.raises(ValueError, match='native timestamp grammar'):
        read_projected(path, 'greeks')


def test_oi_projection_retains_late_zero(tmp_path):
    table = pa.Table.from_pylist([dict(oi(), bid='FORBIDDEN'),
                                  dict(oi(strike='101', open_interest=0,
                                          timestamp='2023-01-03T11:00:00'), bid='FORBIDDEN')])
    table = table.set_column(table.schema.get_field_index('timestamp'), 'timestamp',
                             table['timestamp'].cast(pa.large_string()))
    path = tmp_path / 'oi.parquet'
    pq.write_table(table, path)
    rows = read_projected(path, 'oi')
    assert len(rows) == 2 and all(set(row) == set(OI_COLUMNS) for row in rows)


def test_source_allowlist_and_existing_output(tmp_path):
    expected = tmp_path / 'SPXW/greeks/2023/01/SPXW_20230103_20230103_greeks.parquet'
    assert source_path(tmp_path, 'SPXW', 'greeks') == expected
    with pytest.raises(ValueError, match='allowlist'):
        source_path(tmp_path, 'SPY', 'bidask')
    destination = tmp_path / 'output'
    destination.mkdir()
    marker = destination / 'sentinel'
    marker.write_bytes(b'keep')
    with pytest.raises(Exception, match='already exists'):
        run(destination, AUTHORIZATION, source_base=tmp_path,
            verify_publication=False)
    assert marker.read_bytes() == b'keep'


def _six_synthetic_parquets(base):
    for ticker in ('SPXW', 'SPY', 'QQQ'):
        for kind in ('greeks', 'oi'):
            row = greek(symbol=ticker) if kind == 'greeks' else oi(symbol=ticker)
            table = pa.Table.from_pylist([row])
            table = table.set_column(table.schema.get_field_index('timestamp'), 'timestamp',
                                     table['timestamp'].cast(pa.large_string()))
            path = source_path(base, ticker, kind)
            path.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(table, path)


def test_synthetic_orchestration_seals_before_projection(tmp_path, monkeypatch):
    import json
    from neural.jepa import audit_local_snapshot_source_v1 as auditor

    source = tmp_path / 'source'
    _six_synthetic_parquets(source)

    def synthetic_audit(staging):
        manifest = json.loads((staging / 'manifest.json').read_text(encoding='utf-8'))
        assert len(manifest['sources']) == 6
        for item in manifest['sources']:
            path = staging / item['snapshot_path']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']
        return {'status': 'PASS_LOCAL_SOURCE_DIAGNOSTIC_AUDIT', 'mismatch_count': 0}

    monkeypatch.setattr(auditor, 'audit_directory', synthetic_audit)
    destination = tmp_path / 'diagnostic'
    summary = run(destination, AUTHORIZATION, source_base=source,
                  verify_publication=False)
    assert summary['status'] == 'LOCAL_SOURCE_DIAGNOSTIC_COMPLETE'
    assert summary['promotion_approved'] is False
    ledger = json.loads((destination / 'source_diagnostic.json').read_text(encoding='utf-8'))
    assert set(ledger['tickers']) == {'SPXW', 'SPY', 'QQQ'}
    events = [json.loads(line) for line in (destination / 'access_log.jsonl').read_text().splitlines()]
    assert events[0]['event'] == 'MANIFEST_SEALED_BEFORE_VALUES'
    assert [event['event'] for event in events].count('SOURCE_CLOCK_VALIDATION') == 6
    assert [event['event'] for event in events].count('PROJECTED_SOURCE_READ') == 6


def test_full_synthetic_run_uses_independent_oracle(tmp_path, monkeypatch):
    import json
    from neural.jepa import audit_local_snapshot_source_v1 as auditor

    source = tmp_path / 'source'
    _six_synthetic_parquets(source)

    def fixture_sealed(root, item):
        path = root / item['snapshot_path']
        payload = path.read_bytes()
        assert hashlib.sha256(payload).hexdigest() == item['sha256']
        assert len(payload) == item['bytes']
        return path

    monkeypatch.setattr(auditor, '_sealed_file', fixture_sealed)
    destination = tmp_path / 'diagnostic'
    summary = run(destination, AUTHORIZATION, source_base=source,
                  verify_publication=False)
    assert summary['status'] == 'LOCAL_SOURCE_DIAGNOSTIC_COMPLETE'
    audit = json.loads((destination / 'audit.json').read_text(encoding='utf-8'))
    assert audit['status'] == 'PASS_LOCAL_SOURCE_DIAGNOSTIC_AUDIT'
    assert audit['mismatch_count'] == 0


def test_auditor_exception_is_explicit_failed_audit(tmp_path, monkeypatch):
    import json
    from neural.jepa import audit_local_snapshot_source_v1 as auditor

    source = tmp_path / 'source'
    _six_synthetic_parquets(source)

    def fail_audit(_staging):
        raise ValueError('independent mismatch')

    monkeypatch.setattr(auditor, 'audit_directory', fail_audit)
    destination = tmp_path / 'diagnostic'
    summary = run(destination, AUTHORIZATION, source_base=source,
                  verify_publication=False)
    audit = json.loads((destination / 'audit.json').read_text(encoding='utf-8'))
    assert summary['status'] == audit['status'] == 'FAILED_AUDIT'
    assert 'independent mismatch' in audit['reason']


def test_structural_source_error_retains_blocked_report(tmp_path):
    destination = tmp_path / 'diagnostic'
    summary = run(destination, AUTHORIZATION, source_base=tmp_path / 'empty',
                  verify_publication=False)
    assert summary['status'] == 'BLOCKED_LOCAL_SOURCE'
    assert (destination / 'manifest.json').exists()
    assert (destination / 'summary.json').exists()
    assert summary['historical_economic_admission'] is False


def test_clock_failure_logs_no_price_projection(tmp_path):
    import json

    source = tmp_path / 'source'
    _six_synthetic_parquets(source)
    table = pa.Table.from_pylist([
        dict(greek(), bid='SECRET'),
        dict(greek(timestamp='2023-01-03 11:00:00', underlying_price='999'),
             bid='SECRET'),
    ])
    table = table.set_column(table.schema.get_field_index('timestamp'), 'timestamp',
                             table['timestamp'].cast(pa.large_string()))
    pq.write_table(table, source_path(source, 'SPXW', 'greeks'))
    destination = tmp_path / 'diagnostic'
    summary = run(destination, AUTHORIZATION, source_base=source,
                  verify_publication=False)
    events = [json.loads(line) for line in (destination / 'access_log.jsonl').read_text().splitlines()]
    assert summary['status'] == 'BLOCKED_LOCAL_SOURCE'
    assert [event['event'] for event in events] == [
        'MANIFEST_SEALED_BEFORE_VALUES', 'SOURCE_CLOCK_VALIDATION']
    assert events[1]['columns'] == ['timestamp']
    assert not any(event['event'] == 'PROJECTED_SOURCE_READ' for event in events)


def test_code_does_not_import_market_downloader_or_read_forbidden_source():
    text = Path('neural/jepa/local_snapshot_source_v1.py').read_text(encoding='utf-8')
    assert 'options_bulk' not in text and 'download_spot' not in text
    assert 'data_training_input' not in text
    assert hashlib.sha256(text.encode()).hexdigest()


def test_mutating_input_is_not_used_as_output_reference():
    greek_row = greek()
    first = result([greek_row])
    second = deepcopy(first)
    second['samples'][0]['price'] = '999'
    assert first['samples'][0]['price'] == '100.5'
