import csv
import io

import pytest

from neural.jepa.theta_source_pilot_v1 import requests, summarize
from neural.jepa.audit_theta_source_pilot_v1 import summarize_independent


def payload(kind, **overrides):
    row = dict(symbol='SPXW', expiration='2022-08-01', strike='4000', right='call',
               timestamp='2022-08-01T09:30:00.000')
    if kind == 'greeks':
        row.update(underlying_timestamp='2022-08-01T09:30:00.000', underlying_price='4100',
                   bid='1', ask='1.1', implied_vol='.2', delta='.5')
    else:
        row.update(timestamp='2022-08-01T06:30:00.000', open_interest='100')
    row.update(overrides)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    return out.getvalue().encode()


def test_pilot_is_six_bounded_requests_with_no_future_price_period():
    items = requests()
    assert len(items) == 6
    assert {item['ticker'] for item in items} == {'SPXW', 'SPY', 'QQQ'}
    for item in items:
        assert item['params']['date'] == item['params']['expiration'] == '20220801'
        if item['kind'] == 'greeks':
            assert item['params']['start_time'] == '09:30:00'
            assert item['params']['end_time'] == '09:31:00'
            assert item['params']['interval'] == '1s'


@pytest.mark.parametrize('kind', ['greeks', 'oi'])
def test_independent_source_clock_reproduction(kind):
    raw = payload(kind)
    actual = summarize(raw, kind, 'SPXW')
    assert actual == summarize_independent(raw, kind, 'SPXW')
    assert actual['status'] == 'PASS_REPORTED_CLOCK_CHECKS'


@pytest.mark.parametrize('kind,change', [
    ('greeks', {'underlying_timestamp': '2022-08-01T09:30:01.000'}),
    ('greeks', {'symbol': 'SPY'}),
    ('greeks', {'timestamp': '2022-08-01T11:30:00.000'}),
    ('oi', {'timestamp': '2022-08-01T10:00:00.000'}),
    ('oi', {'open_interest': '-1'}),
])
def test_source_future_identity_and_oi_fail_without_repair(kind, change):
    raw = payload(kind, **change)
    result = summarize(raw, kind, 'SPXW')
    assert result == summarize_independent(raw, kind, 'SPXW')
    assert result['status'] == 'FAILED_REPORTED_CLOCK_CHECKS'


def test_initial_zero_is_reported_without_inventing_replacement():
    raw = payload('greeks', underlying_price='0')
    result = summarize(raw, 'greeks', 'SPXW')
    assert result == summarize_independent(raw, 'greeks', 'SPXW')
    assert result['zero_or_invalid_underlying_rows'] == 1
    assert result['first_positive_quote_timestamp'] is None


@pytest.mark.parametrize('kind', ['greeks', 'oi'])
def test_native_duplicates_fail_and_are_preserved(kind):
    raw = payload(kind)
    raw += raw.splitlines(keepends=True)[1]
    result = summarize(raw, kind, 'SPXW')
    assert result == summarize_independent(raw, kind, 'SPXW')
    assert result['rows'] == 2 and result['duplicate_rows'] == 2
    assert result['status'] == 'FAILED_REPORTED_CLOCK_CHECKS'
