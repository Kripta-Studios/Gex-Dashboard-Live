"""Retain one artificial review attempt, its real output and exact source versions."""
from pathlib import Path
from datetime import datetime, timezone
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

import psutil

ROOT = Path(__file__).resolve().parent
CODE = Path("C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/research_papers/JEPA/level_oracle_20261018")
REPO = CODE.parents[2]


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


class Memory(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
        ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
        ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong),
        ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
        ("avail_extended", ctypes.c_ulonglong)]


def main():
    name = sys.argv[1]
    assert name.startswith("attempt_") and name.removeprefix("attempt_").isdigit()
    attempt = ROOT / name
    attempt.mkdir(exist_ok=False)
    snap = attempt / "sources"
    snap.mkdir()
    preflight_only = len(sys.argv) > 2 and sys.argv[2] == "preflight"
    files = [CODE / "launch_oof_pipeline_user_stop_continuation_20261029.py",
        CODE / "test_launch_oof_pipeline_user_stop_continuation_20261029.py",
        ROOT / "test_independent_boundaries.py", Path(__file__).resolve()]
    if preflight_only:
        files.append(ROOT / "test_independent_preflight.py")
    pins = {str(p): sha(p) for p in files}
    for p in files:
        shutil.copyfile(p, snap / p.name)
        assert sha(snap / p.name) == pins[str(p)]
    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise ctypes.WinError(ctypes.get_last_error())
    assert memory.avail_phys >= 2_000_000_000 and memory.avail_page >= 2_000_000_000
    parent = psutil.Process()
    parent.cpu_affinity([0])
    assert parent.cpu_affinity() == [0]
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(CODE), OOF_REVIEW_ATTEMPT_DIR=str(attempt))
    selection = [str(ROOT / "test_independent_preflight.py")] if preflight_only else [str(ROOT / "test_independent_boundaries.py"),
        str(CODE / "test_launch_oof_pipeline_user_stop_continuation_20261029.py") + "::test_prefix_metadata_accepts_eight_without_economic_parsing",
        str(CODE / "test_launch_oof_pipeline_user_stop_continuation_20261029.py") + "::test_frozen_wrapper_resume_only_four_artificial_producers"]
    command = [sys.executable, "-m", "pytest", "--rootdir", str(CODE), "-q", "-p", "no:cacheprovider",
        "--basetemp", str(attempt / "tmp"), "--junitxml", str(attempt / "junit.xml"), *selection]
    if preflight_only and len(sys.argv) > 3 and sys.argv[3] == "affected":
        command += ["-k", "None or prefix_schema or publication_omits_cpu or publication_extra"]
    admission = dict(status="ARTIFICIAL_FOCAL_REVIEW_ADMISSION", utc=utc(), command=command, files=pins,
        available_ram_bytes=memory.avail_phys, free_commit_bytes=memory.avail_page, minimum_free_bytes=2_000_000_000,
        parent_cpu_affinity=parent.cpu_affinity(), threads1=True, runtime_authorized=False, real_producers=False)
    write(attempt / "admission.json", admission)
    started = time.monotonic()
    with (attempt / "stdout.log").open("xb") as stdout, (attempt / "stderr.log").open("xb") as stderr:
        child = subprocess.Popen(command, cwd=REPO, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW)
        write(attempt / "process.json", dict(status="ARTIFICIAL_TEST_PROCESS_STARTED", pid=child.pid, utc=utc(),
            command=command, parent_pid=os.getpid(), handle_retained=True))
        code = child.wait()
    drift = [p for p, expected in pins.items() if sha(p) != expected]
    result = dict(status="ARTIFICIAL_FOCAL_REVIEW_EXIT_OBSERVED", exit_code=code,
        exit_code_source="subprocess.Popen.wait_retained_handle", pid=child.pid, observed_utc=utc(),
        elapsed_seconds=time.monotonic() - started, source_drift=drift,
        files={str(p): sha(p) for p in attempt.iterdir() if p.is_file()}, runtime_authorized=False)
    write(attempt / "exit.json", result)
    print(json.dumps(result, indent=2))
    print((attempt / "stdout.log").read_text(encoding="utf-8"))
    print((attempt / "stderr.log").read_text(encoding="utf-8"))
    return code if code else (1 if drift else 0)


if __name__ == "__main__":
    raise SystemExit(main())
