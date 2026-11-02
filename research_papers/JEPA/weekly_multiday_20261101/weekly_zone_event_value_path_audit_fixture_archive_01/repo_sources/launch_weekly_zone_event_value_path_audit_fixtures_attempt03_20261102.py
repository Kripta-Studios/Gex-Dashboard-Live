"""Run the one reviewed third synthetic suite for the value-path auditor."""

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
AUDITOR = WEEK / "audit_weekly_zone_event_value_paths.py"
AUDITOR_TESTS = WEEK / "test_audit_weekly_zone_event_value_paths.py"
CONTRACT = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md"
CONTRACT_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_REVIEW_20261102.md"
AUDITOR_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_AUDITOR_IMPLEMENTATION_REVIEW_20261102.md"
HARNESS = Path(__file__).resolve()
GATE_HELPER = (
    REPO / "research_papers" / "JEPA" / "level_oracle_20261018"
    / "launch_monthly_test_index_v2_audit_20261024.py"
)
PREPARATION = BASE / "weekly_zone_event_value_path_audit_fixtures_01"
ATTEMPT01 = PREPARATION / "attempt01"
ATTEMPT02 = PREPARATION / "attempt02"
ATTEMPT = PREPARATION / "attempt03"
ROOT_CONTROL = BASE / "weekly_zone_event_value_path_root_control_01"
ROOT_CONTROL_RECEIPT = ROOT_CONTROL / "audit_attempt02_cli_rejection_01.json"
MINIMUM_BYTES = 2_000_000_000

PINS = {
    AUDITOR: "ce068748eafe74fa65ee8173cad82aef833f85cdee0dd27f856abc32377aefc9",
    AUDITOR_TESTS: "9a9a7aca9a05365c892d36be3dc5681e789c0df44daaed7294ea7b5da3da437f",
    CONTRACT: "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9",
    CONTRACT_REVIEW: "ad118946f30d0681770c25840a4f40d89941030688882b74e23350d098b6b185",
    AUDITOR_REVIEW: "b68373ba1726813410ba689c009e71468dfed7d822d3ecce3397d4af91623af0",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
}
PIN_BYTES = {
    AUDITOR: 96_030,
    AUDITOR_TESTS: 21_237,
    CONTRACT: 36_466,
    CONTRACT_REVIEW: 2_340,
    AUDITOR_REVIEW: 2_845,
    GATE_HELPER: 31_463,
}

ATTEMPT01_PINS = {
    "audit_weekly_zone_event_value_paths.py.before_test": (96050, "c5d522b8503af5b297564be6397481bae570320078f79cdfb917d52583ace4f3"),
    "compile_exit.json": (742, "5b2a1dadcb85887f9cf08299dabbc467621871902ae4a6b0d5bc28c4e9f7d23c"),
    "compile_process.json": (698, "c933c8d873c510b3bcec412da6240b0845ba8dfc032a8be9f19e76a48a842be8"),
    "compile_resource_observation.json": (2832, "e10c47ceaee31e8365e74f9fe172321a8cda9e1b6a76c663cb206febc2d09a12"),
    "compile_stderr.txt": (349, "ec3bb4df35e599fb17e2622b1e0c9b94b1233a2ecdc5f524d4082e073fe43020"),
    "compile_stdout.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "failure_receipt.json": (358, "cac2f01b56f9d25b44af0a1122604404a2beebe05640585aa44e1dd5e1e07b97"),
    "launch_monthly_test_index_v2_audit_20261024.py.before_test": (31463, "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"),
    "launch_weekly_zone_event_value_path_audit_fixtures_20261102.py.before_test": (15491, "450dd7fd077038c728aa123972a5cc0683eec29470c708c35e8f70aef11f2d6c"),
    "preflight_resource_observation.json": (2834, "cb14c5873ec6ed50c2ff33098433c85c87d48a1f643f3690f3e083832a46052d"),
    "test_audit_weekly_zone_event_value_paths.py.before_test": (21221, "c7c8f79d0dc8359550ce0269ec79f1e6c21d302fe4047c2c0a7d0e5a305b3f2c"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_AUDITOR_IMPLEMENTATION_REVIEW_20261102.md.before_test": (1934, "de482951e3424b852dff3c422cbcc84e34faa9ccdab85e855b3a107523e00001"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md.before_test": (36466, "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_REVIEW_20261102.md.before_test": (2340, "ad118946f30d0681770c25840a4f40d89941030688882b74e23350d098b6b185"),
}
ATTEMPT02_PINS = {
    "audit_weekly_zone_event_value_paths.py.before_test": (96049, "0cb2a86bc3fb4de259798b874b0717dba9d6a0990738518fee814a338e446be7"),
    "compile_exit.json": (743, "9c553b7511bc9a50351ba228ec4e0a0f79242b783448661a8f0ed8fe966cef86"),
    "compile_process.json": (699, "5effcefa5bfe7470d6c2be5719556c3338f85c53d0e9eb45e40f1e26dd7be3ba"),
    "compile_resource_observation.json": (5232, "f8a0ece72996e6dac1234217a6882bc0b0022236dd766bd2dd8cb96d170783d8"),
    "compile_stderr.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "compile_stdout.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "failure_receipt.json": (416, "fb254c4e0b83e19cc0f8378ca6145afa92c43f24add0f03c5fa561efb2448023"),
    "launch_monthly_test_index_v2_audit_20261024.py.before_test": (31463, "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"),
    "launch_weekly_zone_event_value_path_audit_fixtures_attempt02_20261102.py.before_test": (20152, "377323b9e8c52595dafd0b5ffc1b30cb6f9a5458e412e938150741889c8db7f9"),
    "preflight_resource_observation.json": (5234, "d75a08955e30863779a0e4fdb313a39d403d120b9dc9473d959cbdd297295cb5"),
    "preserved_attempt01_snapshot.json": (2250, "a9397955b061a626ed016d598c2d813e91990a715d6b3b528d5468aacc40cbd3"),
    "ruff_exit.json": (750, "4d558f8fa8b277fb91dd154d813d7dd7db62da6c05e4a3ba5a8c44c84bd4246e"),
    "ruff_process.json": (706, "c02d919a2cb6458a16520b273f993c5bde484257eac53ffbdc4a689047d58ea0"),
    "ruff_resource_observation.json": (5229, "5c8010f865b0bf1d4e0515a1b0ab14ae5d23d7e0ecde1a1cadbce45ea70eb19f"),
    "ruff_stderr.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "ruff_stdout.txt": (2617, "9b9e36ed967a2d0e90c6e4576df3acbb5b2d46c46923610dde39ce02354d0ea5"),
    "test_audit_weekly_zone_event_value_paths.py.before_test": (21221, "c7c8f79d0dc8359550ce0269ec79f1e6c21d302fe4047c2c0a7d0e5a305b3f2c"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_AUDITOR_IMPLEMENTATION_REVIEW_20261102.md.before_test": (2373, "46515298e4b7930105f3235b2cd86a8ed5eb38ba2692537e4a07221a7d96ab42"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md.before_test": (36466, "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_REVIEW_20261102.md.before_test": (2340, "ad118946f30d0681770c25840a4f40d89941030688882b74e23350d098b6b185"),
}
ROOT_CONTROL_PIN = (780, "28628cc1909f6d75248271807f54da2ce31d404418b24783d4fd9e0e1f58e7ef")
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
    parser = argparse.ArgumentParser(description="Run reviewed third synthetic value-path auditor fixtures")
    parser.add_argument("--harness-sha256", required=True)
    return parser.parse_args()


def require_finalized(harness_sha256: str) -> dict[Path, tuple[int, str]]:
    expected = {path: (PIN_BYTES[path], digest) for path, digest in PINS.items()}
    expected[HARNESS] = (HARNESS.stat().st_size, harness_sha256.lower())
    for expected_bytes, digest in expected.values():
        if not isinstance(expected_bytes, int) or isinstance(expected_bytes, bool) or expected_bytes < 1:
            raise RuntimeError("audit fixture harness requires finalized byte pins")
        if len(digest) != 64 or digest != digest.lower() or any(character not in "0123456789abcdef" for character in digest):
            raise RuntimeError("audit fixture harness requires finalized lowercase SHA-256 pins")
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
    return {str(path): assert_plain_exact(path, size, digest) for path, (size, digest) in expected.items()}


def _snapshot_directory(path: Path, pins: dict[str, tuple[int, str]]) -> dict[str, dict[str, object]]:
    assert_plain_directory(path)
    if {item.name for item in path.iterdir()} != set(pins):
        raise RuntimeError(f"preserved member set mismatch: {path}")
    return {name: assert_plain_exact(path / name, size, digest) for name, (size, digest) in pins.items()}


def validate_prior_evidence(*, allow_attempt03: bool = False) -> dict[str, object]:
    assert_plain_directory(PREPARATION)
    if (ATTEMPT.exists() and not allow_attempt03) or (PREPARATION / "receipt.json").exists():
        raise RuntimeError("attempt03 or parent receipt already exists")
    attempt01 = _snapshot_directory(ATTEMPT01, ATTEMPT01_PINS)
    attempt02 = _snapshot_directory(ATTEMPT02, ATTEMPT02_PINS)
    assert_plain_directory(ROOT_CONTROL)
    root_control = assert_plain_exact(ROOT_CONTROL_RECEIPT, *ROOT_CONTROL_PIN)

    compile01 = json.loads((ATTEMPT01 / "compile_exit.json").read_text(encoding="utf-8"))
    failure01 = json.loads((ATTEMPT01 / "failure_receipt.json").read_text(encoding="utf-8"))
    if compile01.get("exit_code") != 1 or compile01.get("metadata_error") is not None:
        raise RuntimeError("attempt01 compile closure mismatch")
    if failure01.get("status") != "FORMAL_AUDIT_FIXTURE_STAGE_FAILED" or failure01.get("stage") != "compile" or failure01.get("exit_code") != 1:
        raise RuntimeError("attempt01 failure semantics mismatch")

    compile02 = json.loads((ATTEMPT02 / "compile_exit.json").read_text(encoding="utf-8"))
    ruff02 = json.loads((ATTEMPT02 / "ruff_exit.json").read_text(encoding="utf-8"))
    failure02 = json.loads((ATTEMPT02 / "failure_receipt.json").read_text(encoding="utf-8"))
    ruff_stdout = (ATTEMPT02 / "ruff_stdout.txt").read_text(encoding="utf-8")
    if compile02.get("exit_code") != 0 or compile02.get("metadata_error") is not None:
        raise RuntimeError("attempt02 compile closure mismatch")
    if ruff02.get("exit_code") != 1 or ruff02.get("metadata_error") is not None:
        raise RuntimeError("attempt02 Ruff closure mismatch")
    if failure02.get("status") != "FORMAL_AUDIT_FIXTURE_STAGE_FAILED" or failure02.get("stage") != "ruff" or failure02.get("exit_code") != 1:
        raise RuntimeError("attempt02 failure semantics mismatch")
    if "Found 6 errors." not in ruff_stdout:
        raise RuntimeError("attempt02 six-lint evidence mismatch")
    for directory in (ATTEMPT01, ATTEMPT02):
        if any((directory / f"pytest_{suffix}").exists() for suffix in ("exit.json", "process.json", "stdout.txt", "stderr.txt", "resource_observation.json")):
            raise RuntimeError(f"preserved pytest evidence unexpectedly exists: {directory}")

    control_value = json.loads(ROOT_CONTROL_RECEIPT.read_text(encoding="utf-8"))
    if control_value.get("phase") != "ARGPARSE_BEFORE_ATTEMPT_CREATION" or control_value.get("attempt02_observed_absent") is not True or control_value.get("tool_reported_exit_code") != 1:
        raise RuntimeError("root-control CLI receipt mismatch")
    return {"attempt01": attempt01, "attempt02": attempt02, "root_control": root_control}


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


def observe_and_gate(gate_module: object, stage: str, expected: dict[Path, tuple[int, str]]) -> dict[str, object]:
    pins = exact_snapshot(expected)
    prior = validate_prior_evidence(allow_attempt03=True)
    process_state = actual_process_state()
    resources = gate_module.observation()
    disk_free = shutil.disk_usage(BASE).free
    record = {"observed_utc": utc_now(), "stage": stage, "resources": resources, "disk_free_bytes": disk_free, "minimum_bytes": MINIMUM_BYTES, **process_state, "pins": pins, "preserved_prior_evidence": prior, "child_created": False}
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
    write_json(ATTEMPT / "failure_receipt.json", {"status": status, "attempt": "attempt03", "retry": False, "real_value_audit_executed": False, "recorded_utc": utc_now(), "closing_pin_differences": best_effort_diff(ACTIVE_EXPECTED), **extra})


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
        raise RuntimeError("official gate import unavailable")
    gate_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    try:
        observe_and_gate(gate_module, "preflight", expected)
    except Exception as error:
        failure("RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_AUDIT_FIXTURES", error=f"{type(error).__name__}: {error}", stages_executed=[])
        return 2

    files = [str(AUDITOR), str(AUDITOR_TESTS)]
    commands = [
        ("compile", [str(PYTHON), "-X", "utf8", "-m", "py_compile", *files]),
        ("ruff", [str(PYTHON), "-X", "utf8", "-m", "ruff", "check", *files]),
        ("pytest", [str(PYTHON), "-X", "utf8", "-m", "pytest", "-q", str(AUDITOR_TESTS)]),
    ]
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
    validate_prior_evidence(allow_attempt03=True)
    receipt = {"status": "PASS_FORMAL_SYNTHETIC_WEEKLY_ZONE_EVENT_VALUE_PATH_AUDITOR_FIXTURES", "attempt": "attempt03", "preserved_attempt01_failure_sha256": ATTEMPT01_PINS["failure_receipt.json"][1], "preserved_attempt02_failure_sha256": ATTEMPT02_PINS["failure_receipt.json"][1], "root_control_receipt_sha256": ROOT_CONTROL_PIN[1], "stages": completed, "closing_sha256": closing, "real_value_audit_executed": False, "fit_performed": False, "api_read": False, "broker_read": False, "retry": False, "closed_utc": utc_now()}
    write_json(ATTEMPT / "receipt.json", receipt)
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
