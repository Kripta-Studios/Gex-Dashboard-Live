import ast
import csv
from datetime import datetime, timedelta
import io
from pathlib import Path

import pytest

from neural.jepa import audit_theta_ib_source_v1 as auditor
from neural.jepa.theta_ib_source_v1 import build_hour, request_definition


def payload(fault=None, ticker='SPXW'):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['symbol', 'expiration', 'right', 'strike', 'timestamp', 'underlying_timestamp', 'underlying_price'])
    begin = datetime(2022, 8, 1, 9, 30)
    for i in range(3601):
        if fault == 'missing' and i == 90:
            continue
        when = (begin+timedelta(seconds=i)).isoformat()
        underlying = when if fault != 'future' or i != 90 else '2022-08-01T10:31:00'
        price = '0' if i == 0 and ticker == 'SPXW' else str(100+i/1000)
        if fault == 'later_zero' and i == 90:
            price = '0'
        if fault == 'nan_first' and i == 0:
            price = 'NaN'
        if i == 3600:
            price = 'a future value not used'
        row = [ticker, '2022-08-01', 'CALL', '100', when, underlying, price]
        writer.writerow(row)
        if fault == 'duplicate' and i == 90:
            writer.writerow(row)
    return out.getvalue().encode()


@pytest.mark.parametrize('ticker,fault', [('SPXW', None), ('SPY', None), ('QQQ', None), ('SPXW', 'nan_first')])
def test_hour_exact_reconstruction_and_fibonacci(ticker, fault):
    raw = payload(fault, ticker)
    actual = build_hour(raw, ticker)
    assert actual == auditor.reconstruct(raw, ticker)
    assert len(actual['bars']) == 60
    assert sum(b['tick_count'] for b in actual['bars']) == 3600
    assert actual['available_at'] == '2022-08-01T10:30:00-04:00'
    assert actual['ib']['ibh'] == '103.599'
    actual['ib']['upper_1618'] = '99999'
    with pytest.raises(ValueError, match='level mismatch'):
        auditor.verify_record(raw, ticker, actual)


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'future', 'later_zero'])
def test_invalid_hour_rejected_by_both(fault):
    for builder in (build_hour, auditor.reconstruct):
        with pytest.raises(ValueError):
            builder(payload(fault), 'SPXW')


def test_request_scope_fixed_and_auditor_independent():
    params = request_definition('SPXW')
    assert params['date'] == params['expiration'] == '20220801'
    assert params['end_time'] == '10:30:00' and params['interval'] == '1s'
    with pytest.raises(ValueError):
        request_definition('OTHER')
    tree = ast.parse(Path(auditor.__file__).read_text(encoding='utf-8'))
    imports = [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    imports += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not any('theta_ib_source_v1' in n or 'multiscale_v1r1' in n for n in imports)
