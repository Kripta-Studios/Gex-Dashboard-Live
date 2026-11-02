"""Run one reviewed formal fixture suite for the DAILY V2 independent auditor."""

from __future__ import annotations

import os
import sys


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
CODE = WEEK / "audit_weekly_daily_adaptation_v2.py"
TESTS = WEEK / "test_audit_weekly_daily_adaptation_v2.py"
CONTRACT = WEEK / "DAILY_ADAPTATION_AUDIT_FAILURE_AND_V2_CONTRACT_20261102.md"
REVIEW = WEEK / "DAILY_ADAPTATION_AUDIT_V2_CONTRACT_REVIEW_20261102.md"
LAUNCHER = Path(__file__).resolve()
GATE_HELPER = (
    REPO
    / "research_papers"
    / "JEPA"
    / "level_oracle_20261018"
    / "launch_monthly_test_index_v2_audit_20261024.py"
)
PREPARATION = Path(
    r"D:\GexResearchArtifacts\weekly_multiday_20261101\daily_adaptation_audit_v2_preparation_01"
)
ATTEMPT = PREPARATION / "attempt01"
EXPECTED = {
    CODE: "d8813052412dbff001bae192f0d3c680808c78da458f1de54674e4331ef625a9",
    TESTS: "6bc6d92dcbba460fa809527c41197c94a1d7409f85f2937a926efe08925d39d6",
    CONTRACT: "bfd90a0610ab0ef90a06b9a16da246a0e205139887ab51312141ba3866ddab90",
    REVIEW: "0c69a4c7486da02f8abcfcc533d354203a5f569aa4f085647a5b58e24482a4dc",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def affinity_mask(handle: int) -> int:
    process_mask = ctypes.c_size_t()
    system_mask = ctypes.c_size_t()
    if not KERNEL32.GetProcessAffinityMask(
        ctypes.c_void_p(handle), ctypes.byref(process_mask), ctypes.byref(system_mask)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return process_mask.value


def run_child(name: str, args: list[str]) -> dict[str, object]:
    started = utc_now()
    process = None
    metadata_error = None
    child_mask = None
    creation_epoch = None
    with (ATTEMPT / f"{name}_stdout.txt").open("wb") as stdout, (
        ATTEMPT / f"{name}_stderr.txt"
    ).open("wb") as stderr:
        process = subprocess.Popen(
            args,
            cwd=str(WEEK),
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            try:
                import psutil

                child = psutil.Process(process.pid)
                creation_epoch = child.create_time()
                child_mask = affinity_mask(int(process._handle))
                if child_mask != 1:
                    raise RuntimeError(f"child affinity mask {child_mask}, expected 1")
            except Exception as error:
                metadata_error = f"{type(error).__name__}: {error}"
            write_json(
                ATTEMPT / f"{name}_process.json",
                {
                    "pid": process.pid,
                    "creation_epoch": creation_epoch,
                    "start_utc": started,
                    "command": args,
                    "cpu_affinity_mask": child_mask,
                    "metadata_error": metadata_error,
                    "handle_retained": True,
                    "wait_pending": True,
                },
            )
        finally:
            exit_code = process.wait()
    result = {
        "pid": process.pid,
        "creation_epoch": creation_epoch,
        "start_utc": started,
        "end_utc": utc_now(),
        "command": args,
        "cpu_affinity_mask": child_mask,
        "metadata_error": metadata_error,
        "exit_code": exit_code,
        "handle_retained": True,
    }
    write_json(ATTEMPT / f"{name}_exit.json", result)
    if metadata_error is not None:
        raise RuntimeError(metadata_error)
    return result


def failure(status: str, **extra: object) -> None:
    value = {
        "status": status,
        "attempt": "attempt01",
        "retry": False,
        "scientific_runtime_executed": False,
        "recorded_utc": utc_now(),
        **extra,
    }
    write_json(ATTEMPT / "failure_receipt.json", value)


def main() -> int:
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"unexpected Python: {sys.executable}")
    if PREPARATION.exists() or ATTEMPT.exists():
        raise RuntimeError("V2 audit preparation root already exists")
    for path, expected in EXPECTED.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"pin mismatch: {path}")
    if affinity_mask(int(CURRENT_PROCESS)) != 1:
        raise RuntimeError("parent affinity is not CPU[0]")

    PREPARATION.mkdir(parents=False, exist_ok=False)
    ATTEMPT.mkdir(parents=False, exist_ok=False)
    for source in (CODE, TESTS, CONTRACT, REVIEW, LAUNCHER):
        shutil.copyfile(source, ATTEMPT / f"{source.name}.before_test")

    specification = importlib.util.spec_from_file_location("official_gate", GATE_HELPER)
    if specification is None or specification.loader is None:
        raise RuntimeError("official gate import unavailable")
    gate_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    resources = gate_module.observation()
    preflight = {
        "observed_utc": utc_now(),
        "resources": resources,
        "parent_pid": os.getpid(),
        "parent_cpu_affinity_mask": 1,
        "thread_variables": THREAD_ENV,
        "cuda_visible_devices": "-1",
        "pins": {
            str(path): {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in (*EXPECTED, LAUNCHER)
        },
        "scope": "formal synthetic auditor fixtures only; no fit/raw/real audit",
    }
    write_json(ATTEMPT / "preflight_observation.json", preflight)
    try:
        gate_module.gate(resources)
    except Exception as error:
        failure(
            "RESOURCE_GATE_REJECTED_BEFORE_FIXTURES",
            error=f"{type(error).__name__}: {error}",
            resources=resources,
            stages_executed=[],
        )
        return 2
    write_json(
        ATTEMPT / "preflight_gate_pass.json",
        {"status": "PASS_RESOURCE_GATE", "resources": resources, "utc": utc_now()},
    )

    commands = [
        ("compile", [str(PYTHON), "-X", "utf8", "-m", "py_compile", str(CODE), str(TESTS)]),
        ("ruff", [str(PYTHON), "-X", "utf8", "-m", "ruff", "check", str(CODE), str(TESTS)]),
        ("pytest", [str(PYTHON), "-X", "utf8", "-m", "pytest", "-q", str(TESTS)]),
    ]
    completed = []
    for name, command in commands:
        try:
            result = run_child(name, command)
        except Exception as error:
            failure(
                "CHILD_LAUNCH_OR_OBSERVATION_FAILED",
                stage=name,
                completed=completed,
                error=f"{type(error).__name__}: {error}",
                traceback=traceback.format_exc(),
            )
            return 3
        completed.append({"stage": name, "exit_code": result["exit_code"]})
        if result["exit_code"] != 0:
            failure(
                "FORMAL_FIXTURE_STAGE_FAILED",
                stage=name,
                completed=completed,
                exit_code=result["exit_code"],
            )
            return int(result["exit_code"]) or 1

    closing = {str(path): sha256(path) for path in (*EXPECTED, LAUNCHER)}
    for path, expected in EXPECTED.items():
        if closing[str(path)] != expected:
            failure("CLOSING_PIN_MISMATCH", closing=closing)
            return 4
    receipt = {
        "status": "PASS_FORMAL_SYNTHETIC_DAILY_ADAPTATION_AUDIT_V2_FIXTURES",
        "attempt": "attempt01",
        "stages": completed,
        "closing_sha256": closing,
        "scientific_runtime_executed": False,
        "fit_performed": False,
        "raw_read": False,
        "api_read": False,
        "broker_read": False,
        "retry": False,
        "closed_utc": utc_now(),
    }
    write_json(ATTEMPT / "receipt.json", receipt)
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
