"""Synthetic, offline checks of the interrupted IB pilot closure."""

import csv
from datetime import datetime, timedelta
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlencode

import pytest

from neural.jepa.audit_theta_ib_source_v1 import reconstruct
from neural.jepa.review_theta_ib_interrupted_v1 import (
    BASE,
    CODE_NAMES,
    PILOT_HEAD,
    parameters,
    run,
)


def save(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def encoded(value):
    return json.dumps(value, indent=2).encode('utf-8')


def raw_hour(ticker):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['symbol', 'expiration', 'right', 'strike', 'timestamp',
                     'underlying_timestamp', 'underlying_price'])
    start = datetime(2022, 8, 1, 9, 30)
    for second in range(3600):
        clock = (start + timedelta(seconds=second)).isoformat()
        price = '0' if ticker == 'SPXW' and second == 0 else str(100 + second / 1000)
        writer.writerow([ticker, '2022-08-01', 'CALL', '100', clock, clock, price])
    return output.getvalue().encode()


@pytest.fixture
def pilot(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    code = {}
    frozen_paths = {
        'theta_ib_source_v1.py': Path('neural/jepa/theta_ib_source_v1.py'),
        'audit_theta_ib_source_v1.py': Path('neural/jepa/audit_theta_ib_source_v1.py'),
        '23_INITIAL_BALANCE_SOURCE_PILOT.md': Path(
            'research_papers/JEPA/multiscale_v1r1/23_INITIAL_BALANCE_SOURCE_PILOT.md'),
        'provenance.py': Path('neural/jepa/multiscale_v1r1/provenance.py'),
    }
    for name in CODE_NAMES:
        payload = frozen_paths[name].read_bytes()
        save(source / name, payload)
        code[name] = hashlib.sha256(payload).hexdigest()
    save(source / 'run_manifest.json', encoded(dict(
        head=PILOT_HEAD, code=code, economic_evidence_state='NOT_EVALUATED',
        promotion_approved=False)))
    for ticker in ('SPXW', 'SPY'):
        payload = raw_hour(ticker)
        save(source / ticker / 'response.bin', payload)
        save(source / ticker / 'initial_balance.json', encoded(reconstruct(payload, ticker)))
        params = parameters(ticker)
        save(source / ticker / 'manifest.json', encoded(dict(
            ticker=ticker, params=params, url=BASE + '?' + urlencode(params),
            complete=True, http_status=200, bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest())))
    save(source / 'QQQ' / 'response.bin', b'not csv; body may be partial')
    spec = tmp_path / '24_spec.md'
    save(spec, b'Offline interrupted review specification\n')
    return source, spec, tmp_path


def launch(pilot, name='review'):
    source, spec, parent = pilot
    destination = parent / name
    summary = run(source, destination, spec)
    audit = json.loads((destination / 'audit.json').read_text(encoding='utf-8'))
    catalog = json.loads((destination / 'catalog.json').read_text(encoding='utf-8'))
    return summary, audit, catalog


def test_partial_pilot_two_sealed_one_unsealed(pilot, monkeypatch):
    import neural.jepa.review_theta_ib_interrupted_v1 as review

    genuine = review.audit_theta_ib_source_v1.reconstruct

    def guarded(payload, ticker):
        assert ticker in ('SPXW', 'SPY')
        return genuine(payload, ticker)

    monkeypatch.setattr(review.audit_theta_ib_source_v1, 'reconstruct', guarded)
    summary, audit, catalog = launch(pilot)
    assert summary['status'] == 'INCOMPLETE_IB_PILOT'
    assert summary['historical_economic_admission'] is False
    assert summary['promotion_approved'] is False
    assert summary['requests_performed'] == 0
    assert audit['status'] == 'PASS_SEALED_COMPONENTS_ONLY'
    assert [audit['tickers'][ticker]['bars'] for ticker in ('SPXW', 'SPY')] == [60, 60]
    assert audit['tickers']['QQQ']['status'] == 'UNSEALED_BODY_COMPLETENESS_UNKNOWN'
    assert audit['tickers']['QQQ']['parsed'] is False
    assert len(catalog['documents']) == 13
    assert not (pilot[0] / 'summary.json').exists()


@pytest.mark.parametrize('fault', ['hash', 'params', 'incomplete', 'missing_manifest',
                                    'code', 'forged_code_and_manifest', 'head', 'semantic'])
def test_tampering_fails_closed(pilot, fault):
    source = pilot[0]
    if fault == 'hash':
        path = source / 'SPY' / 'response.bin'
        path.write_bytes(path.read_bytes() + b'alteration')
    elif fault in ('params', 'incomplete'):
        path = source / 'SPY' / 'manifest.json'
        value = json.loads(path.read_text(encoding='utf-8'))
        if fault == 'params':
            value['params']['interval'] = '1m'
        else:
            value['complete'] = False
        path.write_bytes(encoded(value))
    elif fault == 'missing_manifest':
        (source / 'SPY' / 'manifest.json').unlink()
    elif fault == 'code':
        (source / 'provenance.py').write_bytes(b'changed code')
    elif fault == 'forged_code_and_manifest':
        payload = b'forged provenance and matching run manifest'
        (source / 'provenance.py').write_bytes(payload)
        path = source / 'run_manifest.json'
        value = json.loads(path.read_text(encoding='utf-8'))
        value['code']['provenance.py'] = hashlib.sha256(payload).hexdigest()
        path.write_bytes(encoded(value))
    elif fault == 'head':
        path = source / 'run_manifest.json'
        value = json.loads(path.read_text(encoding='utf-8'))
        value['head'] = 'another commit'
        path.write_bytes(encoded(value))
    else:
        path = source / 'SPY' / 'initial_balance.json'
        value = json.loads(path.read_text(encoding='utf-8'))
        value['bars'][0]['ohlc']['high'] = '999'
        path.write_bytes(encoded(value))
    summary, audit, _ = launch(pilot)
    assert summary['status'] == 'INCOMPLETE_IB_PILOT'
    assert audit['status'] == 'FAILED_AUDIT'
    assert 'reason' in audit


def test_existing_output_refused_without_change(pilot):
    source, spec, parent = pilot
    destination = parent / 'review'
    destination.mkdir()
    sentinel = destination / 'preserve.txt'
    sentinel.write_text('original', encoding='utf-8')
    with pytest.raises(Exception, match='already exists'):
        run(source, destination, spec)
    assert sentinel.read_text(encoding='utf-8') == 'original'


def test_qqq_manifest_changes_scope_and_is_not_parsed(pilot):
    source, spec, parent = pilot
    save(source / 'QQQ' / 'manifest.json', b'{}')
    summary = run(source, parent / 'review', spec)
    audit = json.loads((parent / 'review' / 'audit.json').read_text(encoding='utf-8'))
    assert summary['status'] == 'INCOMPLETE_IB_PILOT'
    assert audit['status'] == 'FAILED_AUDIT'
    assert 'unexpected source files' in audit['reason']
