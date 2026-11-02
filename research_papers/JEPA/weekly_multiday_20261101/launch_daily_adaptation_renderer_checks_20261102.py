"""Run one technical compile/Ruff check for the reviewed DAILY renderer."""

from __future__ import annotations

import os
import sys


THREAD_ENV = {
    "ARROW_NUM_THREADS": "1", "BLIS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
    "POLARS_MAX_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
}
os.environ.update(THREAD_ENV)
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import ctypes


KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
KERNEL32.GetCurrentProcess.restype = ctypes.c_void_p
KERNEL32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
KERNEL32.SetProcessAffinityMask.restype = ctypes.c_int
KERNEL32.GetProcessAffinityMask.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t),
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
RENDERER = WEEK / "render_weekly_daily_adaptation_result.py"
CONTRACT = WEEK / "DAILY_ADAPTATION_CONTRACT_20261101.md"
REVIEW = WEEK / "DAILY_ADAPTATION_RENDERER_STATIC_REVIEW_20261101.md"
LAUNCHER = Path(__file__).resolve()
GATE_HELPER = REPO / "research_papers" / "JEPA" / "level_oracle_20261018" / "launch_monthly_test_index_v2_audit_20261024.py"
OUTPUT = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101\daily_adaptation_renderer_preparation_01")
ATTEMPT = OUTPUT / "attempt01"
EXPECTED = {
    RENDERER: "d0672f7d4723fa96f7df4745a0f7e922833e22b0b17deae2528c15b09fed3698",
    CONTRACT: "5d388e484435c8fe23d40476c02928887c6ab5487af62197e5e74f08c1fe0047",
    REVIEW: "0735773e90f04ccf8c045b8c079daf264389c039a1e43503d92328befbfae921",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def get_affinity(handle: int) -> int:
    process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
    if not KERNEL32.GetProcessAffinityMask(
        ctypes.c_void_p(handle), ctypes.byref(process_mask), ctypes.byref(system_mask)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return process_mask.value


def run_child(name: str, args: list[str]) -> dict[str, object]:
    started = now()
    metadata_error = None
    child_mask = None
    creation_time = None
    with (ATTEMPT / f"{name}_stdout.txt").open("wb") as stdout, (ATTEMPT / f"{name}_stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(
            args, cwd=str(WEEK), env=os.environ.copy(), stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            try:
                import psutil

                creation_time = psutil.Process(process.pid).create_time()
                child_mask = get_affinity(int(process._handle))
                if child_mask != 1:
                    raise RuntimeError(f"child affinity mask {child_mask}")
            except Exception as error:
                metadata_error = f"{type(error).__name__}: {error}"
            write_json(ATTEMPT / f"{name}_process.json", {
                "pid": process.pid, "creation_time": creation_time,
                "start_utc": started, "command": args,
                "cpu_affinity_mask": child_mask, "metadata_error": metadata_error,
                "handle_retained": True, "wait_pending": True,
            })
        finally:
            exit_code = process.wait()
    result = {
        "pid": process.pid, "creation_time": creation_time,
        "start_utc": started, "end_utc": now(), "command": args,
        "cpu_affinity_mask": child_mask, "metadata_error": metadata_error,
        "exit_code": exit_code, "handle_retained": True,
    }
    write_json(ATTEMPT / f"{name}_exit.json", result)
    if metadata_error is not None:
        raise RuntimeError(metadata_error)
    return result


def fail(status: str, **extra: object) -> None:
    write_json(ATTEMPT / "failure_receipt.json", {
        "status": status, "retry": False, "report_rendered": False,
        "inference_run": False, "recorded_utc": now(), **extra,
    })


def main() -> int:
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"unexpected Python {sys.executable}")
    if OUTPUT.exists():
        raise RuntimeError("renderer preparation root already exists")
    for path, expected in EXPECTED.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"pin mismatch {path}")
    if get_affinity(int(CURRENT_PROCESS)) != 1:
        raise RuntimeError("parent affinity is not CPU[0]")
    OUTPUT.mkdir(parents=False, exist_ok=False)
    ATTEMPT.mkdir(parents=False, exist_ok=False)
    for path in (RENDERER, CONTRACT, REVIEW, LAUNCHER):
        shutil.copyfile(path, ATTEMPT / f"{path.name}.before_check")

    spec = importlib.util.spec_from_file_location("official_gate", GATE_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("official gate import unavailable")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    resources = gate.observation()
    write_json(ATTEMPT / "preflight_observation.json", {
        "observed_utc": now(), "resources": resources,
        "parent_pid": os.getpid(), "parent_cpu_affinity_mask": 1,
        "thread_variables": THREAD_ENV, "cuda_visible_devices": "-1",
        "pins": {str(path): {"bytes": path.stat().st_size, "sha256": sha256(path)} for path in (*EXPECTED, LAUNCHER)},
        "scope": "compile and Ruff only; no report, inference, replay or outcomes",
    })
    try:
        gate.gate(resources)
    except Exception as error:
        fail("RESOURCE_GATE_REJECTED_BEFORE_CHECKS", error=f"{type(error).__name__}: {error}", resources=resources)
        return 2
    write_json(ATTEMPT / "preflight_gate_pass.json", {"status": "PASS_RESOURCE_GATE", "resources": resources, "utc": now()})

    commands = [
        ("compile", [str(PYTHON), "-X", "utf8", "-m", "py_compile", str(RENDERER)]),
        ("ruff", [str(PYTHON), "-X", "utf8", "-m", "ruff", "check", str(RENDERER)]),
    ]
    completed = []
    for name, command in commands:
        try:
            result = run_child(name, command)
        except Exception as error:
            fail("CHILD_LAUNCH_OR_OBSERVATION_FAILED", stage=name, completed=completed, error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
            return 3
        completed.append({"stage": name, "exit_code": result["exit_code"]})
        if result["exit_code"] != 0:
            fail("TECHNICAL_CHECK_FAILED", stage=name, completed=completed, exit_code=result["exit_code"])
            return int(result["exit_code"]) or 1

    closing = {str(path): sha256(path) for path in (*EXPECTED, LAUNCHER)}
    if any(closing[str(path)] != digest for path, digest in EXPECTED.items()):
        fail("CLOSING_PIN_MISMATCH", closing=closing)
        return 4
    write_json(ATTEMPT / "receipt.json", {
        "status": "PASS_DAILY_ADAPTATION_RENDERER_TECHNICAL_CHECKS",
        "stages": completed, "closing_sha256": closing,
        "report_rendered": False, "inference_run": False,
        "replay_run": False, "outcomes_read": False,
        "retry": False, "closed_utc": now(),
    })
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        if ATTEMPT.is_dir():
            fail("LAUNCHER_FAILED_CLOSED", error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
        raise
