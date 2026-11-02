"""Run the one reviewed corrective synthetic suite for value-path code."""

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
ATTEMPT01 = PREPARATION / "attempt01"
ATTEMPT = PREPARATION / "attempt02"
MINIMUM_BYTES = 2_000_000_000

PINS = {
    BUILDER: "b6528622bd9d39fd3a132b6665e7e7cee2e1b0208cd7d854a270093c95398afe",
    SPOT: "0953d344b28992da4b92c561daa7663bb48fe89ea309f6323f53b39c6a0dbd38",
    BUILDER_TESTS: "db5084abe4a751e77def095df7bc5fc92a78eae8c49f048892b6187bcae7499c",
    SPOT_TESTS: "80d91442dafbf8b2beace31b46eb117913e410a1ccb820ee467f2d0c24d9d3eb",
    CONTRACT: "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9",
    CONTRACT_REVIEW: "ad118946f30d0681770c25840a4f40d89941030688882b74e23350d098b6b185",
    BUILDER_REVIEW: "3c71635d40a322811dc1e1041320af79fac102e444ba30a6ebb793b61b4ebb5f",
    SPOT_REVIEW: "bb5d0e1223aabf357eba37ab7b380cc3f380757a3a7d691d3803bc5bdf035ebc",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
}
PIN_BYTES = {
    BUILDER: 83817,
    SPOT: 40814,
    BUILDER_TESTS: 28367,
    SPOT_TESTS: 33144,
    CONTRACT: 36466,
    CONTRACT_REVIEW: 2340,
    BUILDER_REVIEW: 2404,
    SPOT_REVIEW: 2365,
    GATE_HELPER: 31463,
}

ATTEMPT01_PINS = {
    "build_weekly_zone_event_value_paths.py.before_test": (83817, "b6528622bd9d39fd3a132b6665e7e7cee2e1b0208cd7d854a270093c95398afe"),
    "compile_exit.json": (1082, "af48057b371ba735605815f1633efe04ecf94e9d9fea0fa0b179989f48471433"),
    "compile_process.json": (1038, "de87b01e6804854d5526a63a3d77b06035688244237b6248795160bf60e57f9f"),
    "compile_resource_observation.json": (3712, "6895683eea05e432c4b86bdee695097897d3a443533542126970cc6678bb7769"),
    "compile_stderr.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "compile_stdout.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "failure_receipt.json": (412, "f00ee544fb4dfd2956300f9656c08ab97af3a7e970c0d8286bb8bd13b0c3abaf"),
    "launch_monthly_test_index_v2_audit_20261024.py.before_test": (31463, "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"),
    "launch_weekly_zone_event_value_path_fixtures_20261102.py.before_test": (14566, "f684ac9d364d6eebc5e5130a791760edc3d51b2439fdbde492c7a07ee81bfc96"),
    "preflight_resource_observation.json": (3714, "4e646b03a45be5d235ac842f7807397b4ccb46c2f624d95a0b628bc3ad0b2d74"),
    "ruff_exit.json": (1090, "dfffca5ad74d02bcb31904319d1cda2a36b97f3e23626a99321cbbc09c2270f4"),
    "ruff_process.json": (1046, "18db1f0e795a9be0eab8abfd4585303f9ab84c706c2d7a1c1e01d75740bb7af6"),
    "ruff_resource_observation.json": (3709, "c3fc73448232db86d8bf4911bd404a2ea47fdf4d126b48b82602104b16e8b5f8"),
    "ruff_stderr.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "ruff_stdout.txt": (437, "6cc615e1dc5f707f9dbdf3a0109a712e70437051a05c7749e85ae07e1d0ee2b4"),
    "test_build_weekly_zone_event_value_paths.py.before_test": (28377, "0f563473a615a835534f9f239ba15214aba4dd691a9644e0659cfc16259a6585"),
    "test_weekly_zone_event_spot_paths.py.before_test": (33144, "80d91442dafbf8b2beace31b46eb117913e410a1ccb820ee467f2d0c24d9d3eb"),
    "WEEKLY_ZONE_EVENT_SPOT_PATH_IMPLEMENTATION_REVIEW_20261102.md.before_test": (2365, "bb5d0e1223aabf357eba37ab7b380cc3f380757a3a7d691d3803bc5bdf035ebc"),
    "weekly_zone_event_spot_paths.py.before_test": (40814, "0953d344b28992da4b92c561daa7663bb48fe89ea309f6323f53b39c6a0dbd38"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_BUILDER_IMPLEMENTATION_REVIEW_20261102.md.before_test": (2001, "d1ce6dae270fb6169ce52791612ee6c27dc455c141fb40032b4f47500363c77e"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md.before_test": (36466, "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_REVIEW_20261102.md.before_test": (2340, "ad118946f30d0681770c25840a4f40d89941030688882b74e23350d098b6b185"),
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
    parser = argparse.ArgumentParser(description="Run reviewed corrective synthetic value-path fixtures")
    parser.add_argument("--harness-sha256", required=True)
    return parser.parse_args()


def require_finalized(harness_sha256: str) -> dict[Path, tuple[int, str]]:
    expected = {path: (PIN_BYTES[path], digest) for path, digest in PINS.items()}
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
        raise RuntimeError(f"parent process state drift: affinity={affinity}, threads={threads}, cuda={cuda}")
    return {"cpu_affinity_mask": affinity, "thread_variables": threads, "cuda_visible_devices": cuda}


def assert_plain_directory(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    if path != absolute or not path.is_dir() or path.is_symlink():
        raise RuntimeError(f"directory is absent, linked, or aliased: {path}")
    current = path
    while True:
        info = os.lstat(current)
        if getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise RuntimeError(f"reparse point in directory path: {current}")
        if current.parent == current:
            break
        current = current.parent


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
    return {str(path): assert_plain_exact(path, expected_bytes, expected_sha256) for path, (expected_bytes, expected_sha256) in expected.items()}


def validate_attempt01(*, allow_attempt02: bool = False) -> dict[str, dict[str, object]]:
    assert_plain_directory(PREPARATION)
    assert_plain_directory(ATTEMPT01)
    if (ATTEMPT.exists() and not allow_attempt02) or (PREPARATION / "receipt.json").exists():
        raise RuntimeError("attempt02 or parent receipt already exists")
    actual_names = {path.name for path in ATTEMPT01.iterdir()}
    if actual_names != set(ATTEMPT01_PINS):
        raise RuntimeError("preserved attempt01 member set mismatch")
    snapshot = {
        name: assert_plain_exact(ATTEMPT01 / name, expected_bytes, expected_sha256)
        for name, (expected_bytes, expected_sha256) in ATTEMPT01_PINS.items()
    }
    compile_exit = json.loads((ATTEMPT01 / "compile_exit.json").read_text(encoding="utf-8"))
    ruff_exit = json.loads((ATTEMPT01 / "ruff_exit.json").read_text(encoding="utf-8"))
    failure_receipt = json.loads((ATTEMPT01 / "failure_receipt.json").read_text(encoding="utf-8"))
    if compile_exit.get("exit_code") != 0 or compile_exit.get("metadata_error") is not None:
        raise RuntimeError("preserved attempt01 compile closure mismatch")
    if ruff_exit.get("exit_code") != 1 or ruff_exit.get("metadata_error") is not None:
        raise RuntimeError("preserved attempt01 Ruff closure mismatch")
    if failure_receipt.get("status") != "FORMAL_FIXTURE_STAGE_FAILED" or failure_receipt.get("attempt") != "attempt01" or failure_receipt.get("stage") != "ruff" or failure_receipt.get("exit_code") != 1 or failure_receipt.get("retry") is not False:
        raise RuntimeError("preserved attempt01 failure receipt mismatch")
    if any((ATTEMPT01 / f"pytest_{suffix}").exists() for suffix in ("exit.json", "process.json", "stdout.txt", "stderr.txt", "resource_observation.json")):
        raise RuntimeError("preserved attempt01 unexpectedly contains pytest evidence")
    return snapshot


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
    attempt01 = validate_attempt01(allow_attempt02=True)
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
        "preserved_attempt01": attempt01,
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
        process = subprocess.Popen(command, cwd=str(WEEK), env=os.environ.copy(), stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
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
                write_json(ATTEMPT / f"{name}_process.json", {"pid": process.pid, "creation_epoch": creation_epoch, "start_utc": started, "command": command, "cpu_affinity_mask": child_mask, "metadata_error": metadata_error, "handle_retained": True, "wait_pending": True})
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else f"{metadata_error}; {detail}"
        finally:
            exit_code = process.wait()
    result = {"pid": process.pid, "creation_epoch": creation_epoch, "start_utc": started, "end_utc": utc_now(), "command": command, "cpu_affinity_mask": child_mask, "metadata_error": metadata_error, "exit_code": exit_code, "handle_retained": True}
    write_json(ATTEMPT / f"{name}_exit.json", result)
    if metadata_error is not None:
        raise RuntimeError(metadata_error)
    return result


def failure(status: str, **extra: object) -> None:
    write_json(ATTEMPT / "failure_receipt.json", {"status": status, "attempt": "attempt02", "retry": False, "real_value_runtime_executed": False, "recorded_utc": utc_now(), "closing_pin_differences": best_effort_diff(ACTIVE_EXPECTED), **extra})


def main() -> int:
    global ACTIVE_EXPECTED
    args = parse_args()
    expected = require_finalized(args.harness_sha256)
    ACTIVE_EXPECTED = expected
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"unexpected Python: {sys.executable}")
    exact_snapshot(expected)
    preserved_attempt01 = validate_attempt01()

    ATTEMPT.mkdir(parents=False, exist_ok=False)
    for source in expected:
        shutil.copyfile(source, ATTEMPT / f"{source.name}.before_test")
    write_json(ATTEMPT / "preserved_attempt01_snapshot.json", preserved_attempt01)
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
    validate_attempt01(allow_attempt02=True)
    receipt = {
        "status": "PASS_FORMAL_SYNTHETIC_WEEKLY_ZONE_EVENT_VALUE_PATH_FIXTURES",
        "attempt": "attempt02",
        "preserved_attempt01_failure_sha256": ATTEMPT01_PINS["failure_receipt.json"][1],
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
