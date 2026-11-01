import ctypes
import os
import psutil
import subprocess
import sys

class Memory(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(name, ctypes.c_ulonglong) for name in ("total", "ram", "total_commit", "commit", "v", "fv", "ex")]

value = Memory()
value.length = ctypes.sizeof(value)
assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value))
assert min(value.ram, value.commit) >= 2_000_000_000
psutil.Process().cpu_affinity([0])
env = os.environ.copy()
env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONUTF8="1")
command = [sys.executable, "-m", "pytest", "-q", "research_papers/JEPA/level_oracle_20261018/test_prepare_oof_continuation_audit_package_20261101.py"]
print({"gate": {"available_ram_bytes": value.ram, "free_commit_bytes": value.commit}, "cpu_affinity": [0], "threads": 1, "command": command}, flush=True)
raise SystemExit(subprocess.run(command, env=env).returncode)
