"""Synthetic semantic and Parquet I/O checks for the independent local oracle."""

import hashlib
import json
from copy import deepcopy

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from neural.jepa.audit_local_snapshot_source_v1 import audit_directory, reconstruct
from neural.jepa.local_snapshot_schema_v1 import DAY, GREEK_COLUMNS, TICKERS
from neural.jepa.local_snapshot_source_v1 import diagnose


def greek(ticker='SPXW', minute='09:30:00', strike='100', price='0', right='C', **changes):
    row = dict(symbol=ticker, expiration=DAY, trade_date=DAY, right=right,
               strike=strike, interval_used='1m', timestamp=DAY + 'T' + minute,
               underlying_timestamp=DAY + 'T' + minute, underlying_price=price)
    row.update(changes)
    return row


def oi(ticker='SPXW', strike='100', right='C', amount=10, time='08:00:00', **changes):
    row = dict(symbol=ticker, expiration=DAY, trade_date=DAY, right=right,
               strike=strike, interval_used='daily', timestamp=DAY + 'T' + time,
               open_interest=amount)
    row.update(changes)
    return row


def test_reconstruct_mask_precedence_missing_minutes_and_oi_classes():
    rows = [greek(price='0'), greek(minute='09:31:00', price='101'),
            greek(minute='09:31:00', strike='101', price='102'),
            greek(minute='09:33:00', price='100.5000',
                  underlying_timestamp=DAY + 'T09:32:59.999999')]
    records = [oi(amount=0), oi(strike='101', amount=12, time='09:31:00'),
               oi(strike='102', right='P', amount=4)]
    result = reconstruct(rows, records, 'SPXW', {'greeks': '0' * 64, 'oi': '1' * 64})
    assert len(result['samples']) == 60
    assert [(s['mask'], s['reason'], s['source_rows']) for s in result['samples'][:4]] == [
        (False, 'INVALID_PRICE', 1), (False, 'CROSS_CONTRACT_DISAGREEMENT', 2),
        (False, 'MISSING_SAMPLE', 0), (True, None, 1)]
    assert result['samples'][3]['price'] == '100.5'
    assert result['samples'][3]['underlying_age_ms'] == '0.001'
    assert result['samples'][0]['price'] is None
    assert result['oi'][0]['classification'] == 'ZERO_OI'
    assert result['oi'][1]['classification'] == 'AFTER_OPEN'
    assert result['oi'][2]['classification'] == 'ELIGIBLE_REPORTED_PREOPEN'
    assert result['ineligible_oi_contracts'] == [
        {'right': 'CALL', 'strike': '100'}, {'right': 'CALL', 'strike': '101'}]
    assert result['missing_oi_contracts'] == []
    assert result['prior_close_semantics_verified'] is False


def test_oi_integral_decimal_representation_is_valid():
    result = reconstruct([], [oi(amount='10.0')], 'SPXW', {'greeks': '0' * 64, 'oi': '1' * 64})
    assert result['oi'][0]['open_interest'] == 10


def test_invalid_price_precedes_cross_contract_disagreement():
    rows = [greek(price='NaN'), greek(right='P', price='105')]
    result = reconstruct(rows, [], 'SPXW', {'greeks': '0' * 64, 'oi': '1' * 64})
    assert result['samples'][0]['reason'] == 'INVALID_PRICE'
    assert result['samples'][0]['source_rows'] == 2


def test_oracle_and_producer_match_on_synthetic_source_rows():
    rows = [greek(price='0'), greek(right='P', strike='101.0', price='100.25',
                                    minute='09:31:00',
                                    underlying_timestamp=DAY + 'T09:30:59.999999')]
    oi_rows = [oi(amount=0), oi(right='P', strike='101', amount='8.0', time='09:31:00')]
    hashes = {'greeks': '0' * 64, 'oi': '1' * 64}
    assert reconstruct(rows, oi_rows, 'SPXW', hashes) == diagnose(rows, oi_rows, 'SPXW', hashes)


def test_missing_oi_preserves_contract_coverage():
    result = reconstruct([greek(price='100', right='P', strike='1E+2')], [], 'SPXW',
                         {'greeks': '0' * 64, 'oi': '1' * 64})
    assert result['missing_oi_contracts'] == [{'right': 'PUT', 'strike': '100'}]


def test_missing_underlying_clock_fails_closed():
    with pytest.raises(ValueError, match='missing timestamp'):
        reconstruct([greek(price='100', underlying_timestamp=None)], [], 'SPXW',
                    {'greeks': '0' * 64, 'oi': '1' * 64})


@pytest.mark.parametrize('mutated,expected', [
    ({'timestamp': DAY + 'T09:30:30'}, 'minute grid'),
    ({'interval_used': '5m'}, 'interval'),
    ({'symbol': 'SPY'}, 'identity'),
    ({'underlying_timestamp': DAY + 'T09:31:00'}, 'future'),
])
def test_greek_hard_contract_failures(mutated, expected):
    with pytest.raises(ValueError, match=expected):
        reconstruct([greek(price='100', **mutated)], [], 'SPXW', {'greeks': '0' * 64, 'oi': '1' * 64})


def test_duplicate_contract_numeric_and_timezone_alias():
    rows = [greek(price='100'), greek(strike='100.0', price='100',
                                     timestamp=DAY + 'T14:30:00+00:00')]
    with pytest.raises(ValueError, match='duplicate'):
        reconstruct(rows, [], 'SPXW', {'greeks': '0' * 64, 'oi': '1' * 64})


@pytest.mark.parametrize('rows,expected', [
    ([oi(), oi(strike='100.0')], 'duplicate'),
    ([oi(amount='NaN')], 'invalid open_interest'),
    ([oi(amount='1.5')], 'invalid open_interest'),
    ([oi(time='2023-01-04T08:00:00')], 'invalid timestamp'),
])
def test_oi_hard_contract_failures(rows, expected):
    with pytest.raises(ValueError, match=expected):
        reconstruct([], rows, 'SPXW', {'greeks': '0' * 64, 'oi': '1' * 64})


def _write_snapshot(root, ticker, kind, records):
    source_dir = root / 'snapshots'
    source_dir.mkdir(exist_ok=True)
    path = source_dir / f'{ticker}_{kind}.parquet'
    table = pa.Table.from_pylist(records)
    timestamp_index = table.schema.get_field_index('timestamp')
    table = table.set_column(timestamp_index, 'timestamp',
                             table.column('timestamp').cast(pa.large_string()))
    pq.write_table(table, path)
    blob = path.read_bytes()
    return dict(ticker=ticker, kind=kind, snapshot_path=str(path.relative_to(root)),
                source_path=f'D:/ThetaData/data_options/{ticker}/{kind}/2023/01/'
                            f'{ticker}_20230103_20230103_{kind}.parquet',
                sha256=hashlib.sha256(blob).hexdigest(), bytes=len(blob))


def _directory(root):
    sources, diagnostic = [], {'trade_date': DAY, 'tickers': {}}
    for ticker in TICKERS:
        rows = [greek(ticker=ticker, price='100', underlying_timestamp=DAY + 'T09:29:59',
                      bid='FORBIDDEN'),
                greek(ticker=ticker, minute='10:30:00', price='999', bid='FORBIDDEN')]
        oi_rows = [oi(ticker=ticker)]
        sources.append(_write_snapshot(root, ticker, 'greeks', rows))
        sources.append(_write_snapshot(root, ticker, 'oi', oi_rows))
        hashes = {item['kind']: item['sha256'] for item in sources if item['ticker'] == ticker}
        projected = [{name: rows[0][name] for name in GREEK_COLUMNS}]
        diagnostic['tickers'][ticker] = reconstruct(projected, oi_rows, ticker, hashes)
    (root / 'manifest.json').write_text(json.dumps({'sources': sources, 'head': 'fixed'}), encoding='utf-8')
    (root / 'source_diagnostic.json').write_text(json.dumps(diagnostic), encoding='utf-8')
    return sources, diagnostic


def test_audit_directory_projects_columns_filters_future_and_detects_tampering(tmp_path):
    sources, diagnostic = _directory(tmp_path)
    assert audit_directory(tmp_path) == {
        'status': 'PASS_LOCAL_SOURCE_DIAGNOSTIC_AUDIT', 'source_count': 6, 'mismatch_count': 0}
    changed = deepcopy(diagnostic)
    changed['tickers']['SPXW']['samples'][0]['price'] = '101'
    (tmp_path / 'source_diagnostic.json').write_text(json.dumps(changed), encoding='utf-8')
    with pytest.raises(ValueError, match='diagnostic mismatch'):
        audit_directory(tmp_path)
    (tmp_path / 'source_diagnostic.json').write_text(json.dumps(diagnostic), encoding='utf-8')
    path = tmp_path / sources[0]['snapshot_path']
    path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='hash/size mismatch'):
        audit_directory(tmp_path)


def test_audit_directory_rejects_path_escape_and_wrong_original(tmp_path):
    sources, _ = _directory(tmp_path)
    sources[0]['source_path'] = 'D:/ThetaData/another.parquet'
    (tmp_path / 'manifest.json').write_text(json.dumps({'sources': sources}), encoding='utf-8')
    with pytest.raises(ValueError, match='allowlist'):
        audit_directory(tmp_path)
    sources[0]['source_path'] = ('D:/ThetaData/data_options/SPXW/greeks/2023/01/'
                                'SPXW_20230103_20230103_greeks.parquet')
    sources[0]['snapshot_path'] = '../outside.parquet'
    (tmp_path / 'manifest.json').write_text(json.dumps({'sources': sources}), encoding='utf-8')
    with pytest.raises(ValueError, match='outside root'):
        audit_directory(tmp_path)


def test_audit_directory_checks_full_clock_before_price_projection(tmp_path, monkeypatch):
    sources, _ = _directory(tmp_path)
    changed_path = tmp_path / sources[0]['snapshot_path']
    table = pq.read_table(changed_path)
    values = table.column('timestamp').to_pylist()
    values[-1] = DAY + 'T15:30:00+00:00'
    index = table.schema.get_field_index('timestamp')
    pq.write_table(table.set_column(index, 'timestamp', pa.array(values, type=pa.large_string())), changed_path)
    blob = changed_path.read_bytes()
    sources[0]['sha256'] = hashlib.sha256(blob).hexdigest()
    sources[0]['bytes'] = len(blob)
    (tmp_path / 'manifest.json').write_text(json.dumps({'sources': sources}), encoding='utf-8')
    imported = __import__('neural.jepa.audit_local_snapshot_source_v1', fromlist=['pq'])
    original = imported.pq.read_table
    seen = []

    def recorded_read(*args, **kwargs):
        seen.append(kwargs.get('columns'))
        return original(*args, **kwargs)

    monkeypatch.setattr(imported.pq, 'read_table', recorded_read)
    with pytest.raises(ValueError, match='clock format'):
        audit_directory(tmp_path)
    assert seen == [['timestamp']]
