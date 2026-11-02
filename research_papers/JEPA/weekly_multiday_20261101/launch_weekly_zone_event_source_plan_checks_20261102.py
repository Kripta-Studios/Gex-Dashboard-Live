"""Run one reviewed fixture suite for the weekly zone-event source planner."""

from __future__ import annotations

import os
import sys


THREAD_ENV = {
    "ARROW_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "NUMBA_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "POLARS_MAX_THREADS": "1",
    "TBB_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}
os.environ.update(THREAD_ENV)
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import argparse
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
CODE = WEEK / "build_weekly_zone_event_source_plan.py"
TESTS = WEEK / "test_build_weekly_zone_event_source_plan.py"
CONTRACT = WEEK / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_CONTRACT_20261102.md"
REVIEW = WEEK / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_CONTRACT_REVIEW_20261102.md"
STATIC_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_IMPLEMENTATION_REVIEW_20261102.md"
HARNESS = Path(__file__).resolve()
GATE_HELPER = (
    REPO
    / "research_papers"
    / "JEPA"
    / "level_oracle_20261018"
    / "launch_monthly_test_index_v2_audit_20261024.py"
)
PREPARATION = Path(
    r"D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_source_plan_preparation_01"
)
ATTEMPT = PREPARATION / "attempt01"

CODE_SHA256 = "9a412a3ad4b1ae6d527c92c7b1307dfceecb2aec1b4d81cfff70acf8e71c1270"
TESTS_SHA256 = "dd497fc87548b5009c54d43603e13b099756a69183eff519920b6bd0446f4dbf"
CONTRACT_SHA256 = "c1891e794cab794d5f6570f99d838a888663a48b8ccededd4d96d27a63173d65"
REVIEW_SHA256 = "e7c0b2a2ec27afa79bab63776eefb767a5db912289ebffb1879887ab5fa19167"
GATE_HELPER_SHA256 = "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"
STATIC_CLEAR_SHA256 = "3f1b7f7e46051ce1b80a653638f60512d1c0623dd7e430c23f80445687dbaaf4"


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the reviewed weekly zone-event planner fixture suite"
    )
    parser.add_argument("--builder-sha256", required=True)
    parser.add_argument("--tests-sha256", required=True)
    parser.add_argument("--harness-sha256", required=True)
    return parser.parse_args()


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
            try:
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
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else f"{metadata_error}; {detail}"
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
        "planner_runtime_executed": False,
        "recorded_utc": utc_now(),
        **extra,
    }
    write_json(ATTEMPT / "failure_receipt.json", value)


def main() -> int:
    args = parse_args()
    pinned_hex = {
        "builder": CODE_SHA256,
        "tests": TESTS_SHA256,
        "contract": CONTRACT_SHA256,
        "contract_review": REVIEW_SHA256,
        "static_review": STATIC_CLEAR_SHA256,
        "gate_helper": GATE_HELPER_SHA256,
        "harness_argument": args.harness_sha256,
    }
    if any(
        len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
        for value in pinned_hex.values()
    ):
        raise RuntimeError("fixture harness requires finalized lowercase SHA-256 pins")
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"unexpected Python: {sys.executable}")
    if PREPARATION.exists() or ATTEMPT.exists():
        raise RuntimeError("weekly source-plan preparation root already exists")
    if args.builder_sha256.lower() != CODE_SHA256:
        raise RuntimeError("builder argument SHA-256 mismatch")
    if args.tests_sha256.lower() != TESTS_SHA256:
        raise RuntimeError("tests argument SHA-256 mismatch")
    if args.harness_sha256.lower() != sha256(HARNESS):
        raise RuntimeError("harness argument SHA-256 mismatch")
    expected = {
        CODE: CODE_SHA256,
        TESTS: TESTS_SHA256,
        CONTRACT: CONTRACT_SHA256,
        REVIEW: REVIEW_SHA256,
        STATIC_REVIEW: STATIC_CLEAR_SHA256,
        GATE_HELPER: GATE_HELPER_SHA256,
        HARNESS: args.harness_sha256.lower(),
    }
    for path, expected_sha in expected.items():
        if not path.is_file() or path.is_symlink() or sha256(path) != expected_sha:
            raise RuntimeError(f"pin mismatch: {path}")
    if affinity_mask(int(CURRENT_PROCESS)) != 1:
        raise RuntimeError("parent affinity is not CPU[0]")

    PREPARATION.mkdir(parents=False, exist_ok=False)
    ATTEMPT.mkdir(parents=False, exist_ok=False)
    for source in expected:
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
        "minimum_free_commit_bytes": 2_000_000_000,
        "parent_pid": os.getpid(),
        "parent_cpu_affinity_mask": 1,
        "thread_variables": THREAD_ENV,
        "cuda_visible_devices": "-1",
        "pins": {
            str(path): {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in expected
        },
        "scope": "formal synthetic source-plan fixtures only; no raw/NPZ/planner runtime",
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
        (
            "compile",
            [str(PYTHON), "-X", "utf8", "-m", "py_compile", str(CODE), str(TESTS)],
        ),
        (
            "ruff",
            [str(PYTHON), "-X", "utf8", "-m", "ruff", "check", str(CODE), str(TESTS)],
        ),
        (
            "pytest",
            [str(PYTHON), "-X", "utf8", "-m", "pytest", "-q", str(TESTS)],
        ),
    ]
    completed = []
    for name, command in commands:
        stage_resources = gate_module.observation()
        write_json(
            ATTEMPT / f"{name}_resource_observation.json",
            {
                "observed_utc": utc_now(),
                "stage": name,
                "resources": stage_resources,
                "minimum_free_commit_bytes": 2_000_000_000,
                "parent_cpu_affinity_mask": affinity_mask(int(CURRENT_PROCESS)),
                "thread_variables": THREAD_ENV,
                "pins": {
                    str(path): {"bytes": path.stat().st_size, "sha256": sha256(path)}
                    for path in expected
                },
                "child_created": False,
            },
        )
        try:
            gate_module.gate(stage_resources)
        except Exception as error:
            failure(
                "RESOURCE_GATE_REJECTED_BEFORE_FIXTURE_CHILD",
                stage=name,
                completed=completed,
                error=f"{type(error).__name__}: {error}",
                resources=stage_resources,
                child_created=False,
            )
            return 2
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

    closing = {str(path): sha256(path) for path in expected}
    for path, expected_sha in expected.items():
        if closing[str(path)] != expected_sha:
            failure("CLOSING_PIN_MISMATCH", closing=closing)
            return 4
    receipt = {
        "status": "PASS_FORMAL_SYNTHETIC_WEEKLY_ZONE_EVENT_SOURCE_PLAN_FIXTURES",
        "attempt": "attempt01",
        "stages": completed,
        "closing_sha256": closing,
        "planner_runtime_executed": False,
        "fit_performed": False,
        "raw_market_files_opened": False,
        "parquet_footers_read": False,
        "arrays_read": False,
        "outcomes_read": False,
        "api_read": False,
        "broker_read": False,
        "retry": False,
        "closed_utc": utc_now(),
    }
    write_json(ATTEMPT / "receipt.json", receipt)
    write_json(PREPARATION / "receipt.json", receipt)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        if ATTEMPT.is_dir():
            failure(
                "HARNESS_FAILED_CLOSED",
                error=f"{type(error).__name__}: {error}",
                traceback=traceback.format_exc(),
            )
        raise
