"""Standalone bounded fifth synthetic suite for the value-path auditor."""

from __future__ import annotations

import os
import sys


THREAD_ENV = {
    "ARROW_NUM_THREADS": "1", "BLIS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1", "NUMBA_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1", "POLARS_MAX_THREADS": "1", "TBB_NUM_THREADS": "1",
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
KERNEL32.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
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
AUDITOR = WEEK / "audit_weekly_zone_event_value_paths.py"
AUDITOR_TESTS = WEEK / "test_audit_weekly_zone_event_value_paths.py"
CONTRACT = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md"
CONTRACT_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_REVIEW_20261102.md"
AUDITOR_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_AUDITOR_IMPLEMENTATION_REVIEW_20261102.md"
FAILED05_HARNESS = WEEK / "launch_weekly_zone_event_value_path_audit_fixtures_attempt05_20261102.py"
HARNESS = Path(__file__).resolve()
GATE_HELPER = REPO / "research_papers" / "JEPA" / "level_oracle_20261018" / "launch_monthly_test_index_v2_audit_20261024.py"
PREPARATION = BASE / "weekly_zone_event_value_path_audit_fixtures_01"
ATTEMPTS = {number: PREPARATION / f"attempt{number:02d}" for number in (1, 2, 3, 4)}
FAILED_ATTEMPT = PREPARATION / "attempt05"
ATTEMPT = PREPARATION / "attempt05b"
ROOT_CONTROL = BASE / "weekly_zone_event_value_path_root_control_01"
CLI_RECEIPT = ROOT_CONTROL / "audit_attempt02_cli_rejection_01.json"
FAILED05_RECEIPT = ROOT_CONTROL / "audit_attempt05_preflight_pin_rejection_01.json"
MINIMUM_BYTES = 2_000_000_000

PINS = {
    AUDITOR: "d927bca9cd64d51792d68a425a021d9fff9c5cb1ff5dfef79f02dcdcc3c2d2e7",
    AUDITOR_TESTS: "ac5d0fbee457396e8d9e15d217089a17927f1ba73953d681ffa02f2fc4840deb",
    CONTRACT: "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9",
    CONTRACT_REVIEW: "ad118946f30d0681770c25840a4f40d89941030688882b74e23350d098b6b185",
    AUDITOR_REVIEW: "53e3e7bdfd830278effd32efbe34841f41d2414bb0001b089841031758779b9c",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
    FAILED05_HARNESS: "68ccf006b83e47556dd9660961348ed8ddf9f43df852da107790a039faff6b6c",
    FAILED05_RECEIPT: "26f0dd6afce492eb6cb9dd8476148966d1725c541053197aa8b50d7b8a58020a",
}
PIN_BYTES = {AUDITOR: 96078, AUDITOR_TESTS: 21539, CONTRACT: 36466, CONTRACT_REVIEW: 2340, AUDITOR_REVIEW: 3811, GATE_HELPER: 31463, FAILED05_HARNESS: 14821, FAILED05_RECEIPT: 1052}

ATTEMPT04_PINS = {
    "audit_weekly_zone_event_value_paths.py.before_test": (96078, "d927bca9cd64d51792d68a425a021d9fff9c5cb1ff5dfef79f02dcdcc3c2d2e7"),
    "compile_exit.json": (743, "89567b760f7c4611a9d391fc491e4605db176686c24442c4b9d7e5cda7f1d2e1"),
    "compile_process.json": (699, "f964113a439b11442d482bb917aa5958d2d41ccfff59af2de20dee608cbe7832"),
    "compile_resource_observation.json": (13733, "ad5c7e3231d51d7e3b36c06c800ff748bbf78f64ab832c0ee35abb2de936b37d"),
    "compile_stderr.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "compile_stdout.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "failure_receipt.json": (481, "bede2ca8409e7fccc4668572fe1fff51622555767a54767a8efc422b8a26856f"),
    "launch_monthly_test_index_v2_audit_20261024.py.before_test": (31463, "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"),
    "launch_weekly_zone_event_value_path_audit_fixtures_attempt04_20261102.py.before_test": (24709, "c7b39c95f23c0cfd7ea12392d36df7e481b61197a65692402dd38ce5005da830"),
    "preflight_resource_observation.json": (13735, "ac839e0e7e43cdbbdd1469be20851cfbe0fe2d4970d47e75be2f918d7c4872cb"),
    "preserved_prior_evidence_snapshot.json": (10353, "1598ddd40d4e445c25b506bde494e617f7ac75e5000b426c49276c65022d2add"),
    "pytest_exit.json": (576, "d18e02c48fd4970eab1a2f1519c2bf6dce985fc7d81f3d09bac63f4eee338d00"),
    "pytest_process.json": (532, "8936e289b4eb6aecd0ca14211992822f0450f041513ed15fbdfbef4533e6473d"),
    "pytest_resource_observation.json": (13732, "5c121f8002b45b2118a92fddf017e8b75c9e8819fb88d8a9f69beae97186e99f"),
    "pytest_stderr.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "pytest_stdout.txt": (5708, "1deb84aa88329d13a8a8d4b9903c90c58b4ac628ca27e1a130e79930f57d2244"),
    "ruff_exit.json": (751, "e427d728d5c95df76b3b225ad46ffe72a15522e16ead7d485d36204d448d9c32"),
    "ruff_process.json": (707, "27faa0f6b2f56d874dd6f5cefc401e38f5ab6860773212726e42061f45722436"),
    "ruff_resource_observation.json": (13730, "9db2dc69a98fba414c930d13ba5eda268ec198eb19e7d3119b87ae74e64e85d9"),
    "ruff_stderr.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "ruff_stdout.txt": (19, "82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18"),
    "test_audit_weekly_zone_event_value_paths.py.before_test": (21461, "b427ea0b6e73c9811ffc7cf18b00575f456000e95c904635f77ab38b90f842f5"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_AUDITOR_IMPLEMENTATION_REVIEW_20261102.md.before_test": (3407, "17ed9716132e6e9b4fe57c04793de39bc82809229f95565b1d8f3aa52efa4fe0"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md.before_test": (36466, "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_REVIEW_20261102.md.before_test": (2340, "ad118946f30d0681770c25840a4f40d89941030688882b74e23350d098b6b185"),
}
CLI_PIN = (780, "28628cc1909f6d75248271807f54da2ce31d404418b24783d4fd9e0e1f58e7ef")
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


def valid_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and value == value.lower() and all(character in "0123456789abcdef" for character in value)


def affinity_mask(handle: int) -> int:
    process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
    if not KERNEL32.GetProcessAffinityMask(ctypes.c_void_p(handle), ctypes.byref(process_mask), ctypes.byref(system_mask)):
        raise ctypes.WinError(ctypes.get_last_error())
    return process_mask.value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run reviewed standalone attempt05b auditor fixtures")
    parser.add_argument("--harness-sha256", required=True)
    return parser.parse_args()


def validate_pin_definitions() -> None:
    for path, digest in PINS.items():
        size = PIN_BYTES.get(path)
        if not isinstance(size, int) or isinstance(size, bool) or size < 1 or not valid_digest(digest):
            raise RuntimeError(f"active pin definition invalid: {path}")
    for name, (size, digest) in ATTEMPT04_PINS.items():
        if not isinstance(size, int) or isinstance(size, bool) or size < 0 or not valid_digest(digest):
            raise RuntimeError(f"attempt04 pin definition invalid: {name}")
    if CLI_PIN[0] < 1 or not valid_digest(CLI_PIN[1]):
        raise RuntimeError("CLI receipt pin definition invalid")


def require_finalized(harness_sha256: str) -> dict[Path, tuple[int, str]]:
    validate_pin_definitions()
    if not valid_digest(harness_sha256.lower()):
        raise RuntimeError("harness SHA-256 pin invalid")
    expected = {path: (PIN_BYTES[path], digest) for path, digest in PINS.items()}
    expected[HARNESS] = (HARNESS.stat().st_size, harness_sha256.lower())
    return expected


def actual_process_state() -> dict[str, object]:
    affinity = affinity_mask(int(CURRENT_PROCESS))
    threads = {name: os.environ.get(name) for name in THREAD_ENV}
    cuda = os.environ.get("CUDA_VISIBLE_DEVICES")
    if affinity != 1 or any(value != "1" for value in threads.values()) or cuda != "-1":
        raise RuntimeError(f"process state drift: affinity={affinity}, threads={threads}, cuda={cuda}")
    return {"cpu_affinity_mask": affinity, "thread_variables": threads, "cuda_visible_devices": cuda}


def assert_plain_directory(path: Path) -> None:
    if path != Path(os.path.abspath(path)) or not path.is_dir() or path.is_symlink():
        raise RuntimeError(f"directory absent/linked/aliased: {path}")
    current = path
    while True:
        info = os.lstat(current)
        if getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise RuntimeError(f"reparse directory path: {current}")
        if current.parent == current:
            break
        current = current.parent


def assert_plain_exact(path: Path, size: int, digest: str) -> dict[str, object]:
    if path != Path(os.path.abspath(path)) or not path.is_file() or path.is_symlink():
        raise RuntimeError(f"pin path absent/linked/aliased: {path}")
    current = path
    while True:
        info = os.lstat(current)
        if getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise RuntimeError(f"reparse pin path: {current}")
        if current.parent == current:
            break
        current = current.parent
    info = path.stat()
    actual = sha256(path)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size or actual != digest:
        raise RuntimeError(f"pin mismatch: {path}")
    return {"bytes": info.st_size, "sha256": actual}


def exact_snapshot(expected: dict[Path, tuple[int, str]]) -> dict[str, dict[str, object]]:
    return {str(path): assert_plain_exact(path, *pin) for path, pin in expected.items()}


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def snapshot_directory(path: Path, pins: dict[str, tuple[int, str]]) -> dict[str, dict[str, object]]:
    assert_plain_directory(path)
    if {item.name for item in path.iterdir()} != set(pins):
        raise RuntimeError(f"member set mismatch: {path}")
    return {name: assert_plain_exact(path / name, *pin) for name, pin in pins.items()}


def validate_prior_evidence(*, allow_attempt05b: bool = False) -> dict[str, object]:
    assert_plain_directory(PREPARATION)
    if FAILED_ATTEMPT.exists():
        raise RuntimeError("failed attempt05 unexpectedly exists")
    if (ATTEMPT.exists() and not allow_attempt05b) or (PREPARATION / "receipt.json").exists():
        raise RuntimeError("attempt05b or parent receipt already exists")
    attempt04 = snapshot_directory(ATTEMPTS[4], ATTEMPT04_PINS)
    prior_snapshot_path = ATTEMPTS[4] / "preserved_prior_evidence_snapshot.json"
    prior_snapshot = read_object(prior_snapshot_path)
    snapshots = prior_snapshot.get("snapshots")
    artifact_counts = prior_snapshot.get("artifact_counts")
    if not isinstance(snapshots, dict) or artifact_counts != {"attempt01": 14, "attempt02": 20, "attempt03": 25}:
        raise RuntimeError("sealed A1-A3 snapshot schema/count mismatch")
    all_snapshots: dict[str, object] = {}
    for number in (1, 2, 3):
        label = f"attempt{number:02d}"
        values = snapshots.get(label)
        if not isinstance(values, dict) or len(values) != artifact_counts[label]:
            raise RuntimeError(f"sealed {label} snapshot count mismatch")
        pins: dict[str, tuple[int, str]] = {}
        for name, pin in values.items():
            if not isinstance(name, str) or not isinstance(pin, dict):
                raise RuntimeError(f"sealed {label} pin schema")
            size, digest = pin.get("bytes"), pin.get("sha256")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0 or not valid_digest(digest):
                raise RuntimeError(f"sealed {label} pin invalid")
            pins[name] = (size, digest)
        all_snapshots[label] = snapshot_directory(ATTEMPTS[number], pins)
    all_snapshots["attempt04"] = attempt04

    expected = {1: ("compile", {"compile": 1}), 2: ("ruff", {"compile": 0, "ruff": 1}), 3: ("pytest", {"compile": 0, "ruff": 0, "pytest": 1}), 4: ("pytest", {"compile": 0, "ruff": 0, "pytest": 1})}
    for number, (failed_stage, exits) in expected.items():
        directory = ATTEMPTS[number]
        failure = read_object(directory / "failure_receipt.json")
        if failure.get("status") != "FORMAL_AUDIT_FIXTURE_STAGE_FAILED" or failure.get("stage") != failed_stage or failure.get("exit_code") != 1 or failure.get("retry") is not False:
            raise RuntimeError(f"attempt{number:02d} failure semantics")
        for stage, exit_code in exits.items():
            closure = read_object(directory / f"{stage}_exit.json")
            if closure.get("exit_code") != exit_code or closure.get("metadata_error") is not None:
                raise RuntimeError(f"attempt{number:02d} {stage} closure")
    if "Found 6 errors." not in (ATTEMPTS[2] / "ruff_stdout.txt").read_text(encoding="utf-8"):
        raise RuntimeError("attempt02 lint summary")
    if "3 failed, 52 passed" not in (ATTEMPTS[3] / "pytest_stdout.txt").read_text(encoding="utf-8"):
        raise RuntimeError("attempt03 pytest summary")
    if "1 failed, 55 passed" not in (ATTEMPTS[4] / "pytest_stdout.txt").read_text(encoding="utf-8"):
        raise RuntimeError("attempt04 pytest summary")
    cli = assert_plain_exact(CLI_RECEIPT, *CLI_PIN)
    failed05 = assert_plain_exact(FAILED05_RECEIPT, PIN_BYTES[FAILED05_RECEIPT], PINS[FAILED05_RECEIPT])
    failed_value = read_object(FAILED05_RECEIPT)
    if failed_value.get("phase") != "PREFLIGHT_EXACT_SNAPSHOT_BEFORE_ATTEMPT_CREATION" or failed_value.get("attempt_directory_created") is not False or failed_value.get("scientific_child_created") is not False:
        raise RuntimeError("failed attempt05 receipt semantics")
    return {"artifact_counts": {**artifact_counts, "attempt04": len(ATTEMPT04_PINS)}, "snapshots": all_snapshots, "cli_control": cli, "failed_attempt05": failed05}


def best_effort_diff(expected: dict[Path, tuple[int, str]]) -> list[dict[str, object]]:
    differences = []
    for path, (size, digest) in expected.items():
        try:
            actual = {"bytes": path.stat().st_size, "sha256": sha256(path)} if path.is_file() else {"bytes": None, "sha256": None}
        except Exception as error:
            actual = {"error": f"{type(error).__name__}: {error}"}
        wanted = {"bytes": size, "sha256": digest}
        if actual != wanted:
            differences.append({"path": str(path), "expected": wanted, "actual": actual})
    return differences


def observe_and_gate(gate_module: object, stage: str, expected: dict[Path, tuple[int, str]]) -> None:
    pins = exact_snapshot(expected)
    prior = validate_prior_evidence(allow_attempt05b=True)
    process_state = actual_process_state()
    resources = gate_module.observation()
    disk_free = shutil.disk_usage(BASE).free
    write_json(ATTEMPT / f"{stage}_resource_observation.json", {"observed_utc": utc_now(), "stage": stage, "resources": resources, "disk_free_bytes": disk_free, "minimum_bytes": MINIMUM_BYTES, **process_state, "pins": pins, "preserved_prior_evidence": prior, "child_created": False})
    gate_module.gate(resources)
    if disk_free < MINIMUM_BYTES:
        raise RuntimeError(f"D: free bytes {disk_free} below {MINIMUM_BYTES}")


def run_child(name: str, command: list[str]) -> dict[str, object]:
    started, metadata_error, child_mask, creation_epoch = utc_now(), None, None, None
    with (ATTEMPT / f"{name}_stdout.txt").open("wb") as stdout, (ATTEMPT / f"{name}_stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(command, cwd=str(WEEK), env=os.environ.copy(), stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            try:
                import psutil
                child = psutil.Process(process.pid)
                creation_epoch, child_mask = child.create_time(), affinity_mask(int(process._handle))
                if child_mask != 1:
                    raise RuntimeError(f"child affinity {child_mask}")
            except Exception as error:
                metadata_error = f"{type(error).__name__}: {error}"
            write_json(ATTEMPT / f"{name}_process.json", {"pid": process.pid, "creation_epoch": creation_epoch, "start_utc": started, "command": command, "cpu_affinity_mask": child_mask, "metadata_error": metadata_error, "handle_retained": True, "wait_pending": True})
        finally:
            exit_code = process.wait()
    result = {"pid": process.pid, "creation_epoch": creation_epoch, "start_utc": started, "end_utc": utc_now(), "command": command, "cpu_affinity_mask": child_mask, "metadata_error": metadata_error, "exit_code": exit_code, "handle_retained": True}
    write_json(ATTEMPT / f"{name}_exit.json", result)
    if metadata_error is not None:
        raise RuntimeError(metadata_error)
    return result


def failure(status: str, **extra: object) -> None:
    write_json(ATTEMPT / "failure_receipt.json", {"status": status, "attempt": "attempt05b", "retry": False, "real_value_audit_executed": False, "recorded_utc": utc_now(), "closing_pin_differences": best_effort_diff(ACTIVE_EXPECTED), **extra})


def main() -> int:
    global ACTIVE_EXPECTED
    args = parse_args()
    expected = require_finalized(args.harness_sha256)
    ACTIVE_EXPECTED = expected
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"unexpected Python: {sys.executable}")
    exact_snapshot(expected)
    prior = validate_prior_evidence()
    ATTEMPT.mkdir(parents=False, exist_ok=False)
    for source in expected:
        shutil.copyfile(source, ATTEMPT / f"{source.name}.before_test")
    write_json(ATTEMPT / "preserved_prior_evidence_snapshot.json", prior)
    actual_process_state()
    specification = importlib.util.spec_from_file_location("official_gate", GATE_HELPER)
    if specification is None or specification.loader is None:
        raise RuntimeError("official gate unavailable")
    gate_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    try:
        observe_and_gate(gate_module, "preflight", expected)
    except Exception as error:
        failure("RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_AUDIT_FIXTURES", error=f"{type(error).__name__}: {error}", stages_executed=[])
        return 2
    files = [str(AUDITOR), str(AUDITOR_TESTS)]
    commands = [("compile", [str(PYTHON), "-X", "utf8", "-m", "py_compile", *files]), ("ruff", [str(PYTHON), "-X", "utf8", "-m", "ruff", "check", *files]), ("pytest", [str(PYTHON), "-X", "utf8", "-m", "pytest", "-q", str(AUDITOR_TESTS)])]
    completed: list[dict[str, object]] = []
    for name, command in commands:
        try:
            observe_and_gate(gate_module, name, expected)
        except Exception as error:
            failure("RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_AUDIT_FIXTURE_CHILD", stage=name, completed=completed, error=f"{type(error).__name__}: {error}", child_created=False)
            return 2
        try:
            result = run_child(name, command)
        except Exception as error:
            failure("AUDIT_FIXTURE_CHILD_LAUNCH_OR_OBSERVATION_FAILED", stage=name, completed=completed, error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
            return 3
        completed.append({"stage": name, "exit_code": result["exit_code"]})
        if result["exit_code"] != 0:
            failure("FORMAL_AUDIT_FIXTURE_STAGE_FAILED", stage=name, completed=completed, exit_code=result["exit_code"])
            return int(result["exit_code"]) or 1
    closing = exact_snapshot(expected)
    final_prior = validate_prior_evidence(allow_attempt05b=True)
    write_json(ATTEMPT / "receipt.json", {"status": "PASS_FORMAL_SYNTHETIC_WEEKLY_ZONE_EVENT_VALUE_PATH_AUDITOR_FIXTURES", "attempt": "attempt05b", "prior_artifact_counts": final_prior["artifact_counts"], "failed_attempt05_receipt_sha256": PINS[FAILED05_RECEIPT], "stages": completed, "closing_sha256": closing, "real_value_audit_executed": False, "fit_performed": False, "api_read": False, "broker_read": False, "retry": False, "closed_utc": utc_now()})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        if ATTEMPT.is_dir():
            failure("AUDIT_FIXTURE_HARNESS_FAILED_CLOSED", error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
        raise
