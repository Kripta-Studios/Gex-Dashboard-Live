"""Run one reviewed synthetic suite for weekly zone-event value-path code."""

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
import stat
import subprocess
import traceback


PYTHON = Path(r"C:\Program Files\Python314\python.exe")
REPO = Path(r"C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live")
WEEK = REPO / "research_papers" / "JEPA" / "weekly_multiday_20261101"
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
BUILDER = WEEK / "build_weekly_zone_event_value_paths.py"
SPOT = WEEK / "weekly_zone_event_spot_paths.py"
BUILDER_TESTS = WEEK / "test_build_weekly_zone_event_value_paths.py"
SPOT_TESTS = WEEK / "test_weekly_zone_event_spot_paths.py"
CONTRACT = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md"
CONTRACT_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_REVIEW_20261102.md"
BUILDER_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_BUILDER_IMPLEMENTATION_REVIEW_20261102.md"
SPOT_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_SPOT_PATH_IMPLEMENTATION_REVIEW_20261102.md"
HARNESS = Path(__file__).resolve()
GATE_HELPER = REPO / "research_papers" / "JEPA" / "level_oracle_20261018" / "launch_monthly_test_index_v2_audit_20261024.py"
PREPARATION = BASE / "weekly_zone_event_value_path_fixtures_01"
ATTEMPT = PREPARATION / "attempt01"
MINIMUM_BYTES = 2_000_000_000

PINS = {
    BUILDER: "b6528622bd9d39fd3a132b6665e7e7cee2e1b0208cd7d854a270093c95398afe",
    SPOT: "0953d344b28992da4b92c561daa7663bb48fe89ea309f6323f53b39c6a0dbd38",
    BUILDER_TESTS: "0f563473a615a835534f9f239ba15214aba4dd691a9644e0659cfc16259a6585",
    SPOT_TESTS: "80d91442dafbf8b2beace31b46eb117913e410a1ccb820ee467f2d0c24d9d3eb",
    CONTRACT: "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9",
    CONTRACT_REVIEW: "ad118946f30d0681770c25840a4f40d89941030688882b74e23350d098b6b185",
    BUILDER_REVIEW: "d1ce6dae270fb6169ce52791612ee6c27dc455c141fb40032b4f47500363c77e",
    SPOT_REVIEW: "bb5d0e1223aabf357eba37ab7b380cc3f380757a3a7d691d3803bc5bdf035ebc",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
}
PIN_BYTES = {
    BUILDER: 83817,
    SPOT: 40814,
    BUILDER_TESTS: 28377,
    SPOT_TESTS: 33144,
    CONTRACT: 36466,
    CONTRACT_REVIEW: 2340,
    BUILDER_REVIEW: 2001,
    SPOT_REVIEW: 2365,
    GATE_HELPER: 31463,
}
ACTIVE_EXPECTED: dict[Path, tuple[int, str]] = {}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def affinity_mask(handle: int) -> int:
    process_mask = ctypes.c_size_t()
    system_mask = ctypes.c_size_t()
    if not KERNEL32.GetProcessAffinityMask(ctypes.c_void_p(handle), ctypes.byref(process_mask), ctypes.byref(system_mask)):
        raise ctypes.WinError(ctypes.get_last_error())
    return process_mask.value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run reviewed synthetic value-path fixtures")
    parser.add_argument("--harness-sha256", required=True)
    return parser.parse_args()


def require_finalized(harness_sha256: str) -> dict[Path, tuple[int, str]]:
    expected = {
        path: (PIN_BYTES[path], digest) for path, digest in PINS.items()
    }
    expected[HARNESS] = (HARNESS.stat().st_size, harness_sha256.lower())
    for expected_bytes, value in expected.values():
        if not isinstance(expected_bytes, int) or expected_bytes < 1:
            raise RuntimeError("fixture harness requires finalized byte pins")
        if len(value) != 64 or value != value.lower() or any(character not in "0123456789abcdef" for character in value):
            raise RuntimeError("fixture harness requires finalized lowercase SHA-256 pins")
    return expected


def actual_process_state() -> dict[str, object]:
    affinity = affinity_mask(int(CURRENT_PROCESS))
    threads = {name: os.environ.get(name) for name in THREAD_ENV}
    cuda = os.environ.get("CUDA_VISIBLE_DEVICES")
    if affinity != 1 or any(value != "1" for value in threads.values()) or cuda != "-1":
        raise RuntimeError(
            f"parent process state drift: affinity={affinity}, threads={threads}, cuda={cuda}"
        )
    return {"cpu_affinity_mask": affinity, "thread_variables": threads, "cuda_visible_devices": cuda}


def assert_plain_exact(path: Path, expected_bytes: int, expected_sha256: str) -> dict[str, object]:
    absolute = Path(os.path.abspath(path))
    if path != absolute or not path.is_file() or path.is_symlink():
        raise RuntimeError(f"pin path is absent, linked, or aliased: {path}")
    current = path
    while True:
        info = os.lstat(current)
        if getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise RuntimeError(f"reparse point in pin path: {current}")
        if current.parent == current:
            break
        current = current.parent
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RuntimeError(f"pin is not an unambiguous regular file: {path}")
    actual_sha256 = sha256(path)
    if info.st_size != expected_bytes or actual_sha256 != expected_sha256:
        raise RuntimeError(f"pin bytes/hash mismatch: {path}")
    return {"bytes": info.st_size, "sha256": actual_sha256}


def exact_snapshot(expected: dict[Path, tuple[int, str]]) -> dict[str, dict[str, object]]:
    return {
        str(path): assert_plain_exact(path, expected_bytes, expected_sha256)
        for path, (expected_bytes, expected_sha256) in expected.items()
    }


def best_effort_diff(expected: dict[Path, tuple[int, str]]) -> list[dict[str, object]]:
    differences = []
    for path, (expected_bytes, expected_sha256) in expected.items():
        try:
            actual = {"bytes": path.stat().st_size, "sha256": sha256(path)} if path.is_file() else {"bytes": None, "sha256": None}
        except Exception as error:
            actual = {"error": f"{type(error).__name__}: {error}"}
        wanted = {"bytes": expected_bytes, "sha256": expected_sha256}
        if actual != wanted:
            differences.append({"path": str(path), "expected": wanted, "actual": actual})
    return differences


def observe_and_gate(gate_module: object, stage: str, expected: dict[Path, tuple[int, str]]) -> dict[str, object]:
    pins = exact_snapshot(expected)
    process_state = actual_process_state()
    resources = gate_module.observation()
    disk_free = shutil.disk_usage(BASE).free
    record = {
        "observed_utc": utc_now(),
        "stage": stage,
        "resources": resources,
        "disk_free_bytes": disk_free,
        "minimum_bytes": MINIMUM_BYTES,
        **process_state,
        "pins": pins,
        "child_created": False,
    }
    write_json(ATTEMPT / f"{stage}_resource_observation.json", record)
    gate_module.gate(resources)
    if disk_free < MINIMUM_BYTES:
        raise RuntimeError(f"D: free bytes {disk_free} below {MINIMUM_BYTES}")
    return record


def run_child(name: str, command: list[str]) -> dict[str, object]:
    started = utc_now()
    metadata_error = None
    child_mask = None
    creation_epoch = None
    with (ATTEMPT / f"{name}_stdout.txt").open("wb") as stdout, (ATTEMPT / f"{name}_stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(
            command,
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
                        "command": command,
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
        "command": command,
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
    write_json(
        ATTEMPT / "failure_receipt.json",
        {
            "status": status,
            "attempt": "attempt01",
            "retry": False,
            "real_value_runtime_executed": False,
            "recorded_utc": utc_now(),
            "closing_pin_differences": best_effort_diff(ACTIVE_EXPECTED),
            **extra,
        },
    )


def main() -> int:
    global ACTIVE_EXPECTED
    args = parse_args()
    expected = require_finalized(args.harness_sha256)
    ACTIVE_EXPECTED = expected
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"unexpected Python: {sys.executable}")
    if PREPARATION.exists() or ATTEMPT.exists():
        raise RuntimeError("value-path fixture root already exists")
    exact_snapshot(expected)

    PREPARATION.mkdir(parents=False, exist_ok=False)
    ATTEMPT.mkdir(parents=False, exist_ok=False)
    for source in expected:
        shutil.copyfile(source, ATTEMPT / f"{source.name}.before_test")
    actual_process_state()

    specification = importlib.util.spec_from_file_location("official_gate", GATE_HELPER)
    if specification is None or specification.loader is None:
        raise RuntimeError("official gate import unavailable")
    gate_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    try:
        observe_and_gate(gate_module, "preflight", expected)
    except Exception as error:
        failure("RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_FIXTURES", error=f"{type(error).__name__}: {error}", stages_executed=[])
        return 2

    files = [str(BUILDER), str(SPOT), str(BUILDER_TESTS), str(SPOT_TESTS)]
    commands = [
        ("compile", [str(PYTHON), "-X", "utf8", "-m", "py_compile", *files]),
        ("ruff", [str(PYTHON), "-X", "utf8", "-m", "ruff", "check", *files]),
        ("pytest", [str(PYTHON), "-X", "utf8", "-m", "pytest", "-q", str(BUILDER_TESTS), str(SPOT_TESTS)]),
    ]
    completed: list[dict[str, object]] = []
    for name, command in commands:
        try:
            observe_and_gate(gate_module, name, expected)
        except Exception as error:
            failure("RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_FIXTURE_CHILD", stage=name, completed=completed, error=f"{type(error).__name__}: {error}", child_created=False)
            return 2
        try:
            result = run_child(name, command)
        except Exception as error:
            failure("CHILD_LAUNCH_OR_OBSERVATION_FAILED", stage=name, completed=completed, error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
            return 3
        completed.append({"stage": name, "exit_code": result["exit_code"]})
        if result["exit_code"] != 0:
            failure("FORMAL_FIXTURE_STAGE_FAILED", stage=name, completed=completed, exit_code=result["exit_code"])
            return int(result["exit_code"]) or 1

    closing = exact_snapshot(expected)
    receipt = {
        "status": "PASS_FORMAL_SYNTHETIC_WEEKLY_ZONE_EVENT_VALUE_PATH_FIXTURES",
        "attempt": "attempt01",
        "stages": completed,
        "closing_sha256": closing,
        "real_value_runtime_executed": False,
        "fit_performed": False,
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
            failure("HARNESS_FAILED_CLOSED", error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
        raise
