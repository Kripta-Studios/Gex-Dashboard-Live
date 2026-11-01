"""Root evidence helper: invoke the reviewed CLI once and retain its real exit."""
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
OBSERVER = Path('D:/GexResearchArtifacts/level_oracle_20261018/oof_pipeline_user_stop_continuation_observer_20261029_01')
OUT = OBSERVER / 'execute_20261101_01'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def publish(name, data):
    with (OUT / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    if Path(sys.executable).resolve() != Path('C:/Program Files/Python314/python.exe').resolve():
        raise RuntimeError('Expected Python314')
    source = OBSERVER / 'preflight_01/process.json'
    if sha(source) != 'd04c3911b411863d9a7e245f9f0f42bb359608654680d6430fd7e99f2caf92f0':
        raise RuntimeError('Historical CLI receipt pin differs')
    previous = json.loads(source.read_text(encoding='utf-8'))
    command = previous['command'] + ['--execute-reviewed-continuation']
    if command.count('--execute-reviewed-continuation') != 1:
        raise RuntimeError('Exactly one execution flag required')
    supervisor = CODE / 'launch_oof_pipeline_user_stop_continuation_20261029.py'
    if sha(supervisor) != '599f6d5c347ebdc3801bbe8cc21de55603a80a46858a8bad1d20729d307eee11':
        raise RuntimeError('Supervisor pin differs')
    if command[4] != str(supervisor):
        raise RuntimeError('Expected reviewed supervisor command')
    ops_path = CODE / 'launch_monthly_test_index_v2_audit_20261024.py'
    if sha(ops_path) != '3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046':
        raise RuntimeError('Resource helper pin differs')
    spec = importlib.util.spec_from_file_location('resource_observation', ops_path)
    ops = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ops)
    psutil.Process().cpu_affinity([0])
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    resources = ops.observation()
    ops.gate(resources)
    OUT.mkdir(exist_ok=False)
    publish('admission.json', dict(utc=utc(),command=command,resources=resources,
        cpu_affinity=psutil.Process().cpu_affinity(),helper_sha256=sha(__file__),
        previous_process_receipt_sha256=sha(source),
        authorization_sha256=sha(CODE / 'RESUMPTION_20261101.md'),
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        scientific_pipeline_started=False))
    started = time.monotonic()
    with (OUT/'stdout.log').open('xb') as stdout, (OUT/'stderr.log').open('xb') as stderr:
        child = subprocess.Popen(command,cwd=REPO,env=env,stdin=subprocess.DEVNULL,
            stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            publish('process.json',dict(status='ROOT_CONTINUATION_CLI_HANDLE_RETAINED',
                pid=child.pid,creation_time=psutil.Process(child.pid).create_time(),
                creation_time_source='psutil.Process.create_time',observed_utc=utc(),
                command=command,cpu_affinity=psutil.Process(child.pid).cpu_affinity(),
                scientific_pipeline_started=False))
            print(json.dumps(dict(cli_pid=child.pid,observer=str(OUT),status='CLI_STARTED_ADMISSION_PENDING')),flush=True)
        finally:
            exit_code = child.wait()
    publish('exit.json',dict(exit_code=exit_code,observed_utc=utc(),
        exit_source='subprocess.Popen.wait_retained_handle',elapsed_seconds=time.monotonic()-started,
        files={str(OUT/name):sha(OUT/name) for name in ('admission.json','process.json','stdout.log','stderr.log')}))
    print(json.dumps(dict(cli_exit_code=exit_code,observer=str(OUT))),flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
