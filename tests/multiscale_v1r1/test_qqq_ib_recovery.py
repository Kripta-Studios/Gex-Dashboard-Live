"""Offline transport and admission tests for the single QQQ recovery request."""

from collections import namedtuple
import io

import pytest

from neural.jepa import theta_ib_source_v1 as source
from neural.jepa import theta_qqq_ib_recovery_v1 as recovery


class Response(io.BytesIO):
    status = 200


class Transport:
    def __init__(self, response=b'synthetic', error=None):
        self.response = response
        self.error = error
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request.full_url, request.get_method(), timeout))
        if self.error:
            raise self.error
        return Response(self.response)


@pytest.fixture
def rig(tmp_path, monkeypatch):
    root = tmp_path / 'qqq_ib_recovery_20260919_01'
    transport = Transport()
    monkeypatch.setattr(recovery, 'ROOT', root)
    monkeypatch.setattr(recovery, 'published_sources', lambda: ('published-head', {
        'neural/jepa/theta_qqq_ib_recovery_v1.py': b'published-code',
    }))
    disk = namedtuple('Disk', 'total used free')
    monkeypatch.setattr(recovery.shutil, 'disk_usage', lambda _: disk(100*1024**3, 0, 100*1024**3))
    monkeypatch.setattr(source, 'build_opener', lambda *_: transport)
    monkeypatch.setattr(source, 'build_hour', lambda body, ticker: {'source': body.decode(), 'ticker': ticker})
    monkeypatch.setattr(recovery.auditor, 'reconstruct',
                        lambda body, ticker: {'source': body.decode(), 'ticker': ticker})
    return root, transport


def test_single_qqq_get_and_independent_reconstruction(rig):
    root, transport = rig
    result = recovery.run(root, 'user-authorization-20260919')
    assert result['status'] == 'PASS_RECONSTRUCTED_QQQ_IB_COMPONENT'
    assert result['original_vintage_verified'] is False
    assert result['historical_economic_admission'] is False
    assert result['economic_evidence_state'] == 'NOT_EVALUATED'
    assert result['promotion_approved'] is False
    assert len(transport.calls) == 1
    url, method, timeout = transport.calls[0]
    assert '/v3/option/history/greeks/first_order?' in url
    assert 'symbol=QQQ' in url and 'date=20220801' in url
    assert method == 'GET' and timeout == 120
    assert (root / 'QQQ' / 'response.bin').read_bytes() == b'synthetic'
    assert (root / 'QQQ' / 'initial_balance.json').is_file()
    assert (root / 'run_manifest.json').is_file()
    assert (root / 'code_snapshot' / 'theta_qqq_ib_recovery_v1.py').is_file()


def test_transport_error_is_terminal_without_retry(rig):
    root, transport = rig
    transport.error = OSError('transport failure')
    result = recovery.run(root, 'user-authorization-20260919')
    assert result['status'] == 'BLOCKED_QQQ_IB_CAPTURE'
    assert len(transport.calls) == 1
    assert (root / 'QQQ' / 'manifest.json').is_file()
    assert not (root / 'QQQ' / 'initial_balance.json').exists()


def test_existing_root_blocks_before_transport(rig):
    root, transport = rig
    root.mkdir()
    with pytest.raises(ValueError, match='already exists'):
        recovery.run(root, 'user-authorization-20260919')
    assert not transport.calls


@pytest.mark.parametrize('reference', ['', ' ', 'pending', 'none'])
def test_missing_authorization_blocks_before_transport(rig, reference):
    root, transport = rig
    with pytest.raises(ValueError, match='authorization reference'):
        recovery.run(root, reference)
    assert not root.exists()
    assert not transport.calls


def test_changed_body_hash_rejected(rig, monkeypatch):
    root, transport = rig
    original = source.capture_one

    def changed_capture(destination, ticker):
        metadata = original(destination, ticker)
        (destination / 'response.bin').write_bytes(b'altered!!')
        return metadata

    monkeypatch.setattr(source, 'capture_one', changed_capture)
    result = recovery.run(root, 'user-authorization-20260919')
    assert result['status'] == 'BLOCKED_QQQ_IB_RECONSTRUCTION'
    assert 'source changed' in result['reason']
    assert len(transport.calls) == 1
    assert not (root / 'QQQ' / 'initial_balance.json').exists()


def test_independent_mismatch_rejected(rig, monkeypatch):
    root, transport = rig
    monkeypatch.setattr(recovery.auditor, 'reconstruct', lambda *_: {'wrong': True})
    result = recovery.run(root, 'user-authorization-20260919')
    assert result['status'] == 'BLOCKED_QQQ_IB_RECONSTRUCTION'
    assert 'independent reconstruction mismatch' in result['reason']
    assert len(transport.calls) == 1
    assert not (root / 'QQQ' / 'initial_balance.json').exists()


def test_unpublished_changed_source_rejected(monkeypatch, tmp_path):
    path = tmp_path / 'source.py'
    path.write_bytes(b'changed')
    monkeypatch.setattr(recovery, 'REPOSITORY', tmp_path)
    monkeypatch.setattr(recovery, 'SNAPSHOTS', ('source.py',))

    def git_output(command, **_):
        if command[1:3] == ['branch', '--show-current']:
            return recovery.BRANCH
        if command[1:3] == ['rev-parse', 'HEAD']:
            return 'published-head'
        if command[1] == 'ls-remote':
            return 'published-head\trefs/heads/' + recovery.BRANCH
        if command[1] == 'show':
            return b'published'
        raise AssertionError(command)

    monkeypatch.setattr(recovery.subprocess, 'check_output', git_output)
    with pytest.raises(ValueError, match='unpublished or changed source'):
        recovery.published_sources()


def test_request_definition_stays_qqq_and_source_cap():
    params = source.request_definition('QQQ')
    assert params['date'] == params['expiration'] == '20220801'
    assert params['interval'] == '1s'
    assert params['start_time'] == '09:30:00' and params['end_time'] == '10:30:00'
    assert source.LIMIT == 512 * 1024**2 and source.DEADLINE == 1200
