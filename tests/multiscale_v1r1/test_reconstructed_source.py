import ast
from copy import deepcopy
import csv
from datetime import datetime, timedelta
import io
from pathlib import Path

import pytest

from neural.jepa import audit_theta_reconstructed_source_v1 as independent
from neural.jepa.theta_reconstructed_source_v1 import classify_oi, reconstruct_bar


def encoded(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def greek_rows(ticker='SPXW'):
    result = []
    begin = datetime(2022, 8, 1, 9, 30)
    for i in range(61):
        when = (begin + timedelta(seconds=i)).isoformat()
        for right in ('CALL', 'PUT'):
            result.append(dict(symbol=ticker, expiration='2022-08-01', strike='100', right=right,
                               timestamp=when, underlying_timestamp=when,
                               underlying_price='0' if i == 0 and ticker == 'SPXW' else str(100 + i / 100)))
    return result


def oi_rows(ticker='SPXW'):
    return [dict(symbol=ticker, expiration='2022-08-01', strike=str(100+i), right='CALL',
                 timestamp='2022-08-01T' + when, open_interest=str(value))
            for i, (when, value) in enumerate((('06:30:00', 20), ('09:30:00', 10),
                                             ('16:00:00', 0), ('16:00:00', 15), ('06:30:00', 0)))]


def test_first_zero_bar_has_exact_close_dependency_and_delayed_availability():
    raw = encoded(greek_rows())
    value = reconstruct_bar(raw, 'SPXW', '2022-08-01', '2022-08-01 09:31')
    assert value == independent.expected_bar(raw, 'SPXW', '2022-08-01', '2022-08-01 09:31')
    assert value['repair']['repaired_fields'] == ['open', 'low']
    assert value['repair']['replacement_quote_timestamp'] == '2022-08-01T09:30:59-04:00'
    assert value['repair']['replacement_source_rows'] == [118, 119]
    assert value['tick_count'] == 120 and value['ohlc']['open'] == '100.59'
    for function in (reconstruct_bar, independent.expected_bar):
        with pytest.raises(ValueError, match='unavailable'):
            function(raw, 'SPXW', '2022-08-01', '2022-08-01 09:30:59')


@pytest.mark.parametrize('failure', ['duplicate', 'missing_second', 'subsecond', 'future_underlying', 'disagreement', 'later_zero', 'other_ticker_zero'])
def test_bad_bar_inputs_rejected_independently(failure):
    ticker = 'SPY' if failure == 'other_ticker_zero' else 'SPXW'
    rows = greek_rows(ticker)
    if failure == 'duplicate':
        rows.append(dict(rows[10]))
    elif failure == 'missing_second':
        rows = rows[:10] + rows[12:]
    elif failure == 'subsecond':
        rows[10]['timestamp'] += '.500'
    elif failure == 'future_underlying':
        rows[10]['underlying_timestamp'] = '2022-08-01T09:31:00'
    elif failure == 'disagreement':
        rows[10]['underlying_price'] = '123'
    elif failure == 'later_zero':
        rows[10]['underlying_price'] = '0'
    else:
        rows[0]['underlying_price'] = '0'
    for function in (reconstruct_bar, independent.expected_bar):
        with pytest.raises(ValueError):
            function(encoded(rows), ticker, '2022-08-01', '2022-08-01 09:31')


def test_values_after_bar_do_not_change_ohlc_or_dependencies():
    rows = greek_rows()
    before = reconstruct_bar(encoded(rows), 'SPXW', '2022-08-01', '2022-08-01 09:31')
    rows[-1]['underlying_price'] = 'nonsense in a future row'
    after = reconstruct_bar(encoded(rows), 'SPXW', '2022-08-01', '2022-08-01 09:31')
    before.pop('source_sha256')
    after.pop('source_sha256')
    assert before == after


def test_oi_classification_does_not_move_late_zero_or_positive():
    raw = encoded(oi_rows())
    past = '2022-07-29T16:00:00-04:00'
    result = classify_oi(raw, 'SPXW', '2022-08-01', past)
    assert result == independent.expected_oi(raw, 'SPXW', '2022-08-01', past)
    assert [r['reason'] for r in result] == ['ELIGIBLE_PREMARKET_POSITIVE'] * 2 + ['AFTER_OPEN'] * 2 + ['ZERO_OI']
    assert sum(r['eligible'] for r in result) == 2
    rows = oi_rows()
    rows.append(dict(rows[0]))
    for function in (classify_oi, independent.expected_oi):
        with pytest.raises(ValueError, match='duplicate'):
            function(encoded(rows), 'SPXW', '2022-08-01', past)


@pytest.mark.parametrize('field', ['repair', 'oi'])
def test_semantic_tampering_rejected_without_relying_on_output_hash(field):
    greek = {t: encoded(greek_rows(t)) for t in ('SPXW', 'SPY', 'QQQ')}
    oi = {t: encoded(oi_rows(t)) for t in greek}
    past = '2022-07-29T16:00:00-04:00'
    bars = {t: reconstruct_bar(raw, t, '2022-08-01', '2022-08-01 09:31') for t, raw in greek.items()}
    positions = {t: classify_oi(raw, t, '2022-08-01', past) for t, raw in oi.items()}
    independent.compare_components(greek, oi, bars, positions, past)
    if field == 'repair':
        bars = deepcopy(bars)
        bars['SPXW']['repair']['effective_available_at'] = '2022-08-01T09:30:00-04:00'
    else:
        positions['SPXW'][3]['eligible'] = True
    with pytest.raises(ValueError, match='mismatch'):
        independent.compare_components(greek, oi, bars, positions, past)


def test_independent_auditor_has_no_producer_import():
    source = Path(independent.__file__).read_text(encoding='utf-8')
    modules = [node.module or '' for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)]
    modules += [alias.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import) for alias in node.names]
    assert not any('theta_reconstructed_source_v1' in name or 'multiscale_v1r1' in name for name in modules)
