$ErrorActionPreference = 'Stop'

$Python = 'C:\Program Files\Python314\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Pinned Python interpreter is absent: $Python"
}

$Runner = @'
import os
import sys

# Establish the constrained runtime before importing the official gate or any
# project/test module.  Standard-library imports below do not load NumPy,
# scikit-learn, or scientific code.
THREAD_ENV = {
    "ARROW_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "POLARS_MAX_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}
os.environ.update(THREAD_ENV)
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import ctypes

KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
KERNEL32.GetCurrentProcess.restype = ctypes.c_void_p
KERNEL32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
KERNEL32.SetProcessAffinityMask.restype = ctypes.c_int
KERNEL32.GetProcessAffinityMask.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_size_t),
    ctypes.POINTER(ctypes.c_size_t),
]
KERNEL32.GetProcessAffinityMask.restype = ctypes.c_int
CURRENT_PROCESS = KERNEL32.GetCurrentProcess()
if not KERNEL32.SetProcessAffinityMask(CURRENT_PROCESS, ctypes.c_size_t(1)):
    raise ctypes.WinError(ctypes.get_last_error())
process_mask = ctypes.c_size_t()
system_mask = ctypes.c_size_t()
if not KERNEL32.GetProcessAffinityMask(
    CURRENT_PROCESS, ctypes.byref(process_mask), ctypes.byref(system_mask)
):
    raise ctypes.WinError(ctypes.get_last_error())
if process_mask.value != 1:
    raise RuntimeError(f"CPU affinity is not CPU[0]: mask={process_mask.value}")

import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import traceback

PYTHON = Path(r"C:\Program Files\Python314\python.exe")
REPO = Path(r"C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live")
WEEK = REPO / "research_papers" / "JEPA" / "weekly_multiday_20261101"
CODE = WEEK / "evaluate_weekly_daily_adaptation.py"
TESTS = WEEK / "test_evaluate_weekly_daily_adaptation.py"
GATE_HELPER = (
    REPO
    / "research_papers"
    / "JEPA"
    / "level_oracle_20261018"
    / "launch_monthly_test_index_v2_audit_20261024.py"
)
PREPARATION = Path(
    r"D:\GexResearchArtifacts\weekly_multiday_20261101\daily_adaptation_preparation_01"
)
ATTEMPT01 = PREPARATION / "attempt01"
ATTEMPT = PREPARATION / "attempt02"
LAUNCHER = PREPARATION / "launch_attempt02_v2.ps1"
DRAFT = PREPARATION / "launch_attempt02.attempt02_draft.ps1"

EXPECTED = {
    CODE: "536a581d8295362b3374dd8c5db2224095f8afe66c5b0e9ae895cf08b18d4f2e",
    TESTS: "fa199a2a6339cf73911cc6f818c73f655cce1931e222733c041bff82b23e661e",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
    DRAFT: "2cf625559ec35501a40c6514ce3cc3b268907f91a7886521fd86e38764e57915",
}


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


class FILETIME(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


KERNEL32.GetProcessTimes.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
]
KERNEL32.GetProcessTimes.restype = ctypes.c_int


def process_creation_epoch(process):
    creation = FILETIME()
    exit_time = FILETIME()
    kernel = FILETIME()
    user = FILETIME()
    if not KERNEL32.GetProcessTimes(
        ctypes.c_void_p(int(process._handle)),
        ctypes.byref(creation),
        ctypes.byref(exit_time),
        ctypes.byref(kernel),
        ctypes.byref(user),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    ticks = (creation.high << 32) | creation.low
    return ticks / 10_000_000 - 11_644_473_600


def child_affinity(process):
    child_mask = ctypes.c_size_t()
    child_system = ctypes.c_size_t()
    if not KERNEL32.GetProcessAffinityMask(
        ctypes.c_void_p(int(process._handle)),
        ctypes.byref(child_mask),
        ctypes.byref(child_system),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return child_mask.value


RETAINED_PROCESSES = []


def run_child(name, args):
    stdout_path = ATTEMPT / f"{name}_stdout.txt"
    stderr_path = ATTEMPT / f"{name}_stderr.txt"
    started = utc_now()
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            args,
            cwd=str(WEEK),
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        RETAINED_PROCESSES.append(process)
        creation_epoch = process_creation_epoch(process)
        affinity_mask = child_affinity(process)
        exit_code = process.wait()
    ended = utc_now()
    write_json(
        ATTEMPT / f"{name}_exit.json",
        {
            "name": name,
            "pid": process.pid,
            "creation_epoch": creation_epoch,
            "start_utc": started,
            "end_utc": ended,
            "exit_code": exit_code,
            "command": args,
            "cpu_affinity_mask": affinity_mask,
            "cpu_affinity": [0] if affinity_mask == 1 else [],
            "handle_retained": True,
        },
    )
    return exit_code


def failure(status, **extra):
    payload = {
        "status": status,
        "attempt": "attempt02",
        "retry": False,
        "real_runtime_executed": False,
        "recorded_utc": utc_now(),
    }
    payload.update(extra)
    write_json(ATTEMPT / "failure_receipt.json", payload)


def main():
    if sys.executable.lower() != str(PYTHON).lower():
        raise RuntimeError(f"Unexpected Python interpreter: {sys.executable}")
    if not ATTEMPT01.is_dir():
        raise RuntimeError("Preserved attempt01 is required")
    if ATTEMPT.exists():
        raise RuntimeError("attempt02 exists; retry/adoption is forbidden")
    for path, expected in EXPECTED.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"Pinned bytes differ: {path}")

    ATTEMPT.mkdir(parents=False, exist_ok=False)
    shutil.copyfile(CODE, ATTEMPT / f"{CODE.name}.before_test")
    shutil.copyfile(TESTS, ATTEMPT / f"{TESTS.name}.before_test")
    shutil.copyfile(LAUNCHER, ATTEMPT / "launch_attempt02_v2.ps1.snapshot")
    shutil.copyfile(DRAFT, ATTEMPT / DRAFT.name)

    # Persist the official observation before applying its admission gate.
    specification = importlib.util.spec_from_file_location("official_gate", GATE_HELPER)
    if specification is None or specification.loader is None:
        raise RuntimeError("Could not load official gate helper")
    gate_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    resources = gate_module.observation()
    preflight = {
        "observed_utc": utc_now(),
        "resources": resources,
        "gate_helper": {
            "path": str(GATE_HELPER),
            "bytes": GATE_HELPER.stat().st_size,
            "sha256": EXPECTED[GATE_HELPER],
        },
        "python": str(PYTHON),
        "parent_pid": os.getpid(),
        "parent_cpu_affinity_mask": process_mask.value,
        "parent_cpu_affinity": [0],
        "cuda_visible_devices": "-1",
        "thread_variables": THREAD_ENV,
        "pins": {
            "code": {
                "path": str(CODE),
                "bytes": CODE.stat().st_size,
                "sha256": EXPECTED[CODE],
            },
            "tests": {
                "path": str(TESTS),
                "bytes": TESTS.stat().st_size,
                "sha256": EXPECTED[TESTS],
            },
            "launcher": {
                "path": str(LAUNCHER),
                "bytes": LAUNCHER.stat().st_size,
                "sha256": sha256(LAUNCHER),
            },
            "draft": {
                "path": str(DRAFT),
                "bytes": DRAFT.stat().st_size,
                "sha256": EXPECTED[DRAFT],
            },
        },
    }
    write_json(ATTEMPT / "preflight_observation.json", preflight)
    try:
        gate_module.gate(resources)
    except Exception as error:
        failure(
            "RESOURCE_GATE_REJECTED_BEFORE_FIXTURES",
            resources=resources,
            error=f"{type(error).__name__}: {error}",
            compile_executed=False,
            ruff_executed=False,
            pytest_executed=False,
        )
        return 2
    write_json(
        ATTEMPT / "preflight_gate_pass.json",
        {"status": "PASS_RESOURCE_GATE", "resources": resources, "utc": utc_now()},
    )

    commands = [
        (
            "compile",
            [str(PYTHON), "-m", "py_compile", str(CODE), str(TESTS)],
        ),
        (
            "ruff",
            [str(PYTHON), "-m", "ruff", "check", str(CODE), str(TESTS)],
        ),
        (
            "pytest",
            [str(PYTHON), "-m", "pytest", "-q", str(TESTS)],
        ),
    ]
    completed = []
    for name, command in commands:
        try:
            exit_code = run_child(name, command)
        except Exception as error:
            failure(
                "CHILD_LAUNCH_OR_OBSERVATION_FAILED",
                stage=name,
                completed=completed,
                command=command,
                error=f"{type(error).__name__}: {error}",
                traceback=traceback.format_exc(),
            )
            return 3
        completed.append({"stage": name, "exit_code": exit_code})
        if exit_code != 0:
            failure(
                "FORMAL_FIXTURE_STAGE_FAILED",
                stage=name,
                exit_code=exit_code,
                completed=completed,
            )
            return exit_code if 0 < exit_code < 256 else 1

    closing = {"code": sha256(CODE), "tests": sha256(TESTS)}
    if closing["code"] != EXPECTED[CODE] or closing["tests"] != EXPECTED[TESTS]:
        failure("CLOSING_IMPLEMENTATION_PIN_MISMATCH", closing=closing)
        return 4
    write_json(
        ATTEMPT / "receipt.json",
        {
            "status": "PASS_FORMAL_SYNTHETIC_DAILY_ADAPTATION_FIXTURES",
            "attempt": "attempt02",
            "code_sha256": closing["code"],
            "tests_sha256": closing["tests"],
            "gate_helper_sha256": EXPECTED[GATE_HELPER],
            "launcher_sha256": sha256(LAUNCHER),
            "stages": completed,
            "child_pids": [process.pid for process in RETAINED_PROCESSES],
            "child_handles_retained_until_launcher_exit": True,
            "attempt01_preserved": True,
            "retry": False,
            "real_runtime_executed": False,
            "closed_utc": utc_now(),
        },
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        if ATTEMPT.is_dir():
            failure(
                "LAUNCHER_FAILED_CLOSED",
                error=f"{type(error).__name__}: {error}",
                traceback=traceback.format_exc(),
            )
        raise
'@

& $Python -c $Runner
exit $LASTEXITCODE
