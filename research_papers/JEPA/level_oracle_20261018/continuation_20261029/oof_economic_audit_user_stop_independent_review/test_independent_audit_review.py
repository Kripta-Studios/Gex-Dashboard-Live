"""Independent artificial probes; no scientific or original-runtime execution."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest
import test_launch_oof_economic_audit_user_stop_continuation_20261029 as author

case = author.case


def snapshot_args(case):
    s = case.s
    upstream = case.binding['upstream']
    return (copy.deepcopy(case.operational),
            s.read(upstream['continuation_binding']['path']),
            s.read(upstream['preflight']['path']), author.prepared_upstream(case))


def test_positive_admission_is_metadata_read_only(case, monkeypatch):
    before = {str(p): case.s.sha(p) for p in case.base.rglob('*') if p.is_file()}
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('Popen forbidden'))
    receipt = author.admit(case)
    assert receipt['executed'] is False and receipt['retry'] is False
    assert not Path(receipt['logs_root']).exists() and not Path(receipt['output_root']).exists()
    assert before == {str(p): case.s.sha(p) for p in case.base.rglob('*') if p.is_file()}


@pytest.mark.parametrize('fault', ['source_result', 'phase_order', 'claim_adopted', 'exit_bool'])
def test_independent_review_identity_semantics(case, fault):
    s = case.s
    review = s.read(case.operational['independent_prefix_review']['path'])
    if fault == 'source_result':
        author.rewrite(review['review_result_source'], {'status': 'PASS_STOPPED_PREFIX_METADATA_AND_HASHES_ONLY', 'failed_checks': 1})
    elif fault == 'phase_order':
        review['reviewed_phases'][0]['index'] = 1
    elif fault == 'claim_adopted':
        review['adoption_authorized_by_this_review'] = True
    else:
        review['original_exit_code'] = True
    with pytest.raises(ValueError):
        s.validate_prefix_review(review, case.operational, author.prepared_upstream(case))


@pytest.mark.parametrize('fault', ['one_copy', 'duplicate_copy', 'size', 'foreign_original'])
def test_snapshot_copies_cannot_be_substituted(case, fault):
    s = case.s
    operational, runtime, pre, evidence = snapshot_args(case)
    snapshot = s.read(operational['snapshot_manifest']['path'])
    if fault == 'one_copy':
        snapshot['copies'].pop()
    elif fault == 'duplicate_copy':
        snapshot['copies'].append(snapshot['copies'][0])
    elif fault == 'size':
        snapshot['copies'][0]['size'] += 1
    else:
        p = Path(runtime['snapshot_root']) / 'foreign.json'
        p.write_text('{}', encoding='utf-8')
        snapshot['original_files'][str(p)] = s.sha(p)
    author.rewrite(operational['snapshot_manifest'], snapshot)
    Path(runtime['snapshot_root'], 'snapshot_manifest.json').write_bytes(Path(operational['snapshot_manifest']['path']).read_bytes())
    with pytest.raises(ValueError):
        s.validate_snapshot(operational, runtime, pre, evidence)


def test_same_hash_failure_at_different_path_is_rejected(case):
    old = Path(case.operational['stopped_launch']['failure']['path'])
    duplicate = case.new_logs / 'nested' / 'failure.json'
    duplicate.parent.mkdir()
    duplicate.write_bytes(old.read_bytes())
    with pytest.raises(ValueError, match='Unknown upstream failure'):
        case.s.no_unknown_failures([case.new_logs], case.operational['stopped_launch']['failure'], author.prepared_upstream(case))


@pytest.mark.parametrize('fault', ['wrong_pid', 'retained_creation_delta', 'bool_exit'])
def test_retained_identity_cannot_use_observer_tolerance(case, fault):
    s = case.s
    refs = case.binding['upstream']
    pre, proc, ended = (s.read(refs[k]['path']) for k in ('preflight', 'process', 'exit'))
    authority = {k: proc[k] for k in ('monitor_code_sha256', 'request_sha256', 'runtime_binding_sha256', 'implementation_review_sha256', 'publication_commit', 'preflight_sha256')}
    if fault == 'wrong_pid': ended['pid'] += 1
    elif fault == 'retained_creation_delta': ended['creation_time'] += 0.0000005
    else: ended['exit_code'] = False
    with pytest.raises(ValueError, match='identity/exit'):
        s.process_chain(pre, proc, ended, refs, authority, pre['command'], 0)


def test_publication_requires_both_cpu_evidence_files(case):
    ref = case.s.read(case.review['path'])['cpu0_inheritance_test']['evidence']
    case.binding['published_files'].pop(ref['path'])
    author.rewrite(case.binding_ref, case.binding)
    with pytest.raises(ValueError, match='publication membership'):
        author.admit(case)


def test_drift_after_admission_prevents_popen(case, monkeypatch):
    receipt = author.admit(case)
    target = Path(case.operational['snapshot_manifest']['path'])
    target.write_bytes(target.read_bytes() + b' ')
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('Popen forbidden'))
    with pytest.raises(ValueError, match='Pinned bytes changed'):
        case.s.launch(receipt)
    assert not Path(receipt['logs_root']).exists()


def test_busy_runtime_lock_prevents_popen(case, monkeypatch):
    receipt = author.admit(case)
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('Popen forbidden'))
    with case.s.lock(case.base / 'oof_pipeline_runtime.lock', False):
        with pytest.raises(OSError):
            case.s.launch(receipt)
    assert not Path(receipt['logs_root']).exists()


def test_native_child_observes_inherited_affinity_before_psutil(case):
    s = case.s
    s.gate(s.observation())
    parent = s.establish_cpu0()
    probe = '''import ctypes, os, json
k = ctypes.WinDLL('kernel32', use_last_error=True)
k.GetCurrentProcess.argtypes = []; k.GetCurrentProcess.restype = ctypes.c_void_p
k.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
k.GetProcessAffinityMask.restype = ctypes.c_int
a = ctypes.c_size_t(); b = ctypes.c_size_t()
assert k.GetProcessAffinityMask(k.GetCurrentProcess(), ctypes.byref(a), ctypes.byref(b))
print(json.dumps({'mask': a.value, 'threads': [os.environ[n] for n in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')]}))
'''
    result = subprocess.run([sys.executable, '-c', probe], env=s.child_environment(), capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    assert parent['parent_cpu_affinity'] == [0] and result.returncode == 0
    assert not result.stderr
    assert json.loads(result.stdout) == {'mask': 1, 'threads': ['1', '1', '1']}


def test_monitor_psutil_failure_preserves_handle_exit(case, monkeypatch):
    author.test_harmless_child_lifecycle_and_durable_retry_block(case, monkeypatch, 'monitor_psutil')
