"""Root log/handle wrapper for the frozen economic supervisor; no science here."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil

CODE = Path(__file__).resolve().parents[1]
REPO = CODE.parents[2]
OBSERVER = Path('D:/GexResearchArtifacts/level_oracle_20261018/oof_economic_audit_user_stop_continuation_observer_20261101_01')
SUPERVISOR = CODE / 'launch_oof_economic_audit_user_stop_continuation_20261029.py'
REQUEST = CODE / 'OOF_ECONOMIC_AUDIT_USER_STOP_REQUEST_20261101_01.json'
BINDING = CODE / 'OOF_ECONOMIC_AUDIT_USER_STOP_BINDING_20261101_01.json'
REVIEW_SHA = '0c4edfd7c74b74f1573f8ce7133c79d7339cf4da06c243edc36699164622403b'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--binding-sha256', required=True)
    parser.add_argument('--publication-commit', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if Path(sys.executable).resolve() != Path('C:/Program Files/Python314/python.exe').resolve():
        raise RuntimeError('Expected Python314')
    pins = {REQUEST: args.request_sha256, BINDING: args.binding_sha256,
            SUPERVISOR: '48169acfe736a55855f742a26af53cc262a0450b57cc7bea3ce43a623ac7bfa7',
            CODE/'OOF_ECONOMIC_AUDIT_USER_STOP_IMPLEMENTATION_REVIEW_20261029.json': REVIEW_SHA,
            Path(__file__).resolve(): sha(__file__)}
    for path, expected in pins.items():
        if sha(path) != expected:
            raise RuntimeError('Authority pin differs: ' + str(path))
        blob = subprocess.check_output(['git', 'show', args.publication_commit + ':' + path.relative_to(REPO).as_posix()], cwd=REPO)
        if hashlib.sha256(blob).hexdigest() != expected:
            raise RuntimeError('Published bytes differ: ' + str(path))
    ops_path = CODE/'launch_monthly_test_index_v2_audit_20261024.py'
    if sha(ops_path) != '3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046':
        raise RuntimeError('Resource helper differs')
    spec = importlib.util.spec_from_file_location('resource_observation', ops_path)
    ops = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ops)
    psutil.Process().cpu_affinity([0])
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    resources = ops.observation()
    ops.gate(resources)
    out = OBSERVER/('execute_01' if args.execute else 'preflight_01')
    out.mkdir(parents=True, exist_ok=False)

    def publish(name, data):
        with (out/name).open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')

    command = [sys.executable, '-X', 'utf8', '-u', str(SUPERVISOR),
               '--request', str(REQUEST), '--request-sha256', args.request_sha256,
               '--runtime-binding', str(BINDING), '--runtime-binding-sha256', args.binding_sha256,
               '--implementation-review-sha256', REVIEW_SHA, '--publication-commit', args.publication_commit]
    if args.execute:
        command.append('--execute-reviewed-audit')
    publish('admission.json', dict(utc=utc(),command=command,resources=resources,
        cpu_affinity=psutil.Process().cpu_affinity(),pins={str(p):h for p,h in pins.items()},
        mode='EXECUTE' if args.execute else 'DEFAULT_METADATA_ONLY',scientific_auditor_started=False))
    started = time.monotonic()
    with (out/'stdout.log').open('xb') as stdout, (out/'stderr.log').open('xb') as stderr:
        child = subprocess.Popen(command,cwd=REPO,env=env,stdin=subprocess.DEVNULL,
            stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            publish('process.json', dict(status='ROOT_ECONOMIC_CLI_HANDLE_RETAINED',pid=child.pid,
                creation_time=psutil.Process(child.pid).create_time(),creation_time_source='psutil.Process.create_time',
                command=command,observed_utc=utc(),scientific_auditor_started=False))
            print(json.dumps(dict(pid=child.pid,mode='EXECUTE' if args.execute else 'DEFAULT',observer=str(out))),flush=True)
        finally:
            exit_code = child.wait()
    publish('exit.json', dict(exit_code=exit_code,observed_utc=utc(),elapsed_seconds=time.monotonic()-started,
        exit_source='subprocess.Popen.wait_retained_handle',files={str(out/n):sha(out/n) for n in ('admission.json','process.json','stdout.log','stderr.log')}))
    print(json.dumps(dict(exit_code=exit_code,observer=str(out))),flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
