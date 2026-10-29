"""One-shot independent test evidence recorder, CPU0 and threads1."""
from pathlib import Path
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import psutil

root = Path(__file__).parent
code = Path(sys.argv[1]).resolve()
attempt = root / sys.argv[2]
attempt.mkdir(exist_ok=False)
psutil.Process().cpu_affinity([0])
assert psutil.Process().cpu_affinity() == [0]
class Memory(ctypes.Structure):
    _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in ('total', 'ram', 'total_commit', 'commit', 'v', 'fv', 'ex')]
memory = Memory(); memory.length = ctypes.sizeof(memory)
assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
assert memory.ram >= 2_000_000_000 and memory.commit >= 2_000_000_000
files = {}
for source in [code / n for n in ('launch_oof_economic_audit_user_stop_continuation_20261029.py', 'test_launch_oof_economic_audit_user_stop_continuation_20261029.py', 'launch_oof_pipeline_user_stop_continuation_20261029.py', 'test_launch_oof_pipeline_user_stop_continuation_20261029.py')] + [Path(__file__), root / 'test_independent_audit_review.py']:
    shutil.copyfile(source, attempt / source.name)
    files[str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
env = os.environ.copy()
env.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(code))
command = [sys.executable, '-m', 'pytest', str(root / 'test_independent_audit_review.py'), '-q', '-p', 'no:cacheprovider', '--basetemp', str(attempt / 'fixtures'), *sys.argv[3:]]
started = time.time()
with (attempt / 'stdout.log').open('xb') as out, (attempt / 'stderr.log').open('xb') as err:
    child = subprocess.Popen(command, cwd=code, env=env, stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
    status = child.wait()
result = dict(status='INDEPENDENT_ARTIFICIAL_TEST_ATTEMPT', command=command, exit_code=status, pid=child.pid, started_epoch=started, finished_epoch=time.time(), cpu_affinity=[0], threads=1, available_ram_bytes=memory.ram, free_commit_bytes=memory.commit, files=files, scientific_execution=False)
result['logs'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (attempt / 'stdout.log', attempt / 'stderr.log')}
(attempt / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
print((attempt / 'stdout.log').read_text(encoding='utf-8'))
print((attempt / 'stderr.log').read_text(encoding='utf-8'))
sys.exit(status)
