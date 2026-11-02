"""Observed, wrapper-only formal fixture harness.  It never runs C geometry or B."""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path, PureWindowsPath
from typing import Any, Mapping, Sequence


PYTHON = Path(r"C:\Program Files\Python314\python.exe")
REPO = Path(r"C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live")
WEEK = REPO / "research_papers" / "JEPA" / "weekly_multiday_20261101"
LEVEL = REPO / "research_papers" / "JEPA" / "level_oracle_20261018"
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
BRANCH = "research/multiscale-v1r1-net-usd"
MINIMUM_BYTES = 2_000_000_000
ROOT = BASE / "weekly_zone_geometry_1030_wrapper_fixtures_01"
OBSERVER = BASE / "weekly_zone_geometry_1030_wrapper_fixtures_observer_01"
LAUNCHER = WEEK / "launch_weekly_zone_geometry_1030_producer_20261102.py"
TESTS = WEEK / "test_launch_weekly_zone_geometry_1030_producer_20261102.py"
CONTRACT = WEEK / "C_GEOMETRY_1030_PRODUCER_LAUNCH_CONTRACT_20261102.md"
C_FINAL_REVIEW = WEEK / "C_GEOMETRY_FINAL_IMPLEMENTATION_REVIEW_20261102.md"
HARNESS = Path(__file__).resolve()
HELPER = LEVEL / "launch_monthly_test_index_v2_audit_20261024.py"
THREAD_ENV = {name: "1" for name in (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS", "ARROW_NUM_THREADS", "POLARS_MAX_THREADS",
    "TBB_NUM_THREADS", "NUMBA_NUM_THREADS",
)}
FROZEN = {
    LAUNCHER: (49697, "9a7410432da2a495e8fb161c4ba83fd5f6b1f290798f9f154d61a2ffb11482f5"),
    TESTS: (20058, "bbc40d8a56eb3ae460f1e1d4b002acd24abd9878e76c13e71355da538928b4d7"),
    CONTRACT: (10359, "f63fe6507addd94831e8ea28831b5ff6f30d63723cb65222fb49079e62aeccf1"),
    C_FINAL_REVIEW: (2160, "3e306e8bebc95686fd2e6dd4fa3496d834fdf9b07882f4b15922fedc7f679fc7"),
    HELPER: (31463, "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"),
}


class FixtureError(RuntimeError):
    pass


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def plain_exact(path: Path, expected_bytes: int, expected_sha256: str) -> dict[str, Any]:
    if path != Path(os.path.abspath(path)) or not PureWindowsPath(str(path)).is_absolute() or not path.is_file() or path.is_symlink():
        raise FixtureError(f"plain absolute file required: {path}")
    current = path
    while True:
        info = os.lstat(current)
        if getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise FixtureError(f"reparse path: {current}")
        if current.parent == current:
            break
        current = current.parent
    info = path.stat()
    actual = sha256(path)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != expected_bytes or actual != expected_sha256:
        raise FixtureError(f"pin mismatch: {path}")
    return {"path": str(path), "bytes": info.st_size, "sha256": actual}


def git_bytes(commit: str, path: Path) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path.relative_to(REPO).as_posix()}"], cwd=REPO)


def verify_publication(review: Path, review_sha256: str) -> dict[str, dict[str, Any]]:
    if not review.is_relative_to(REPO) or len(review_sha256) != 64:
        raise FixtureError("final review must be a published repository member with SHA-256")
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    remote = subprocess.check_output(["git", "ls-remote", "origin", f"refs/heads/{BRANCH}"], cwd=REPO, text=True).split()
    if branch != BRANCH or not remote or remote[0] != commit:
        raise FixtureError("wrapper fixture sources are not published at remote HEAD")
    pins = {str(path): plain_exact(path, size, digest) for path, (size, digest) in FROZEN.items()}
    review_pin = plain_exact(review, review.stat().st_size, review_sha256)
    review_text = review.read_text(encoding="utf-8")
    required_review_tokens = ["CLEAR_STATIC_PRE_SUITE_C_PRODUCER_WRAPPER", FROZEN[LAUNCHER][1], FROZEN[TESTS][1], FROZEN[CONTRACT][1]]
    if any(token not in review_text for token in required_review_tokens):
        raise FixtureError("wrapper fixture review marker/source pins")
    pins[str(review)] = review_pin
    pins[str(HARNESS)] = plain_exact(HARNESS, HARNESS.stat().st_size, sha256(HARNESS))
    for raw in pins:
        path = Path(raw)
        if git_bytes(commit, path) != path.read_bytes():
            raise FixtureError(f"Git byte mismatch: {path}")
    return pins


def kernel32() -> Any:
    if os.name != "nt":
        raise FixtureError("Windows-only fixture harness")
    value = ctypes.WinDLL("kernel32", use_last_error=True)
    value.GetCurrentProcess.restype = ctypes.c_void_p
    value.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    value.SetProcessAffinityMask.restype = ctypes.c_int
    value.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
    value.GetProcessAffinityMask.restype = ctypes.c_int
    value.GetProcessTimes.argtypes = [ctypes.c_void_p, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)]
    value.GetProcessTimes.restype = ctypes.c_int
    return value


def affinity(handle: int | None = None) -> int:
    api = kernel32()
    process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
    target = api.GetCurrentProcess() if handle is None else ctypes.c_void_p(handle)
    if not api.GetProcessAffinityMask(target, ctypes.byref(process_mask), ctypes.byref(system_mask)):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(process_mask.value)


def process_times(handle: int) -> dict[str, float | None]:
    api = kernel32()
    creation, exited, kernel_time, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
    if not api.GetProcessTimes(ctypes.c_void_p(handle), ctypes.byref(creation), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user)):
        raise ctypes.WinError(ctypes.get_last_error())
    def ticks(value: FILETIME) -> int:
        return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)

    def epoch(value: FILETIME) -> float | None:
        raw = ticks(value)
        return None if raw == 0 else (raw - 116_444_736_000_000_000) / 10_000_000.0
    result = {"creation_epoch": epoch(creation), "exit_epoch": epoch(exited),
              "kernel_seconds": ticks(kernel_time) / 10_000_000.0, "user_seconds": ticks(user) / 10_000_000.0}
    if result["creation_epoch"] is None or not math.isfinite(result["creation_epoch"]):
        raise FixtureError("retained handle creation time")
    return result


def configure() -> dict[str, Any]:
    for name, value in THREAD_ENV.items():
        os.environ[name] = value
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    api = kernel32()
    if not api.SetProcessAffinityMask(api.GetCurrentProcess(), 1) or affinity() != 1:
        raise FixtureError("CPU0 affinity")
    return {"cpu_affinity_mask": 1, "thread_variables": dict(THREAD_ENV), "cuda_visible_devices": "-1"}


def load_gate() -> Any:
    plain_exact(HELPER, *FROZEN[HELPER])
    scope: dict[str, Any] = {"__name__": "wrapper_fixture_gate", "__file__": str(HELPER)}
    exec(compile(HELPER.read_bytes(), str(HELPER), "exec"), scope, scope)
    if not callable(scope.get("observation")) or not callable(scope.get("gate")):
        raise FixtureError("official gate interface")
    return type("Gate", (), scope)


def gate(gate_module: Any) -> dict[str, Any]:
    observation = gate_module.observation()
    gate_module.gate(observation)
    resources = {"available_ram_bytes": observation.get("available_ram_bytes"), "free_commit_bytes": observation.get("free_commit_bytes")}
    disk_free = shutil.disk_usage(BASE).free
    if any(type(value) is not int or value < MINIMUM_BYTES for value in resources.values()) or disk_free < MINIMUM_BYTES:
        raise FixtureError("official 2GB RAM/commit/disk gate")
    return {"resources": resources, "disk_free_bytes": disk_free, "minimum_bytes": MINIMUM_BYTES}


def write_json(path: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": str(path), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def closing_differences(pins: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    changed: list[dict[str, Any]] = []
    for raw_path, pin in pins.items():
        try:
            actual = plain_exact(Path(raw_path), int(pin["bytes"]), str(pin["sha256"]))
        except Exception as error:
            actual = {"error": f"{type(error).__name__}: {error}"}
        if actual != dict(pin):
            changed.append({"path": raw_path, "before": dict(pin), "after": actual})
    return changed


def snapshot_sources(pins: Mapping[str, Mapping[str, Any]], destination: Path) -> dict[str, dict[str, Any]]:
    destination.mkdir(exist_ok=False)
    snapshots: dict[str, dict[str, Any]] = {}
    for ordinal, raw_path in enumerate(sorted(pins)):
        source = Path(raw_path)
        target = destination / f"{ordinal:02d}_{source.name}"
        with source.open("rb") as read_stream, target.open("xb") as write_stream:
            shutil.copyfileobj(read_stream, write_stream, 1024 * 1024)
            write_stream.flush()
            os.fsync(write_stream.fileno())
        snapshots[raw_path] = {"source": dict(pins[raw_path]), "snapshot": plain_exact(target, int(pins[raw_path]["bytes"]), str(pins[raw_path]["sha256"]))}
    return snapshots


def run_child(label: str, command: list[str], gate_module: Any, temp_dir: Path, observer: Path,
              pins: Mapping[str, Mapping[str, Any]]) -> tuple[int, dict[str, Any]]:
    gate_evidence = gate(gate_module)
    environment = os.environ.copy()
    environment["TMP"] = str(temp_dir)
    environment["TEMP"] = str(temp_dir)
    started = time.monotonic()
    with (observer / f"{label}.stdout.log").open("xb") as stdout, (observer / f"{label}.stderr.log").open("xb") as stderr:
        process = subprocess.Popen(command, cwd=str(WEEK), env=environment, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        handle = int(process._handle)
        initial: dict[str, float | None] | None = None
        final: dict[str, float | None] | None = None
        child_affinity: int | None = None
        metadata_error: str | None = None
        try:
            try:
                initial = process_times(handle)
                child_affinity = affinity(handle)
                if child_affinity != 1:
                    raise FixtureError(f"{label}: child affinity {child_affinity}")
            except Exception as error:
                metadata_error = f"{type(error).__name__}: {error}"
        finally:
            child_exit = process.wait()  # Always wait the retained handle, including metadata failure.
            try:
                final = process_times(handle)
                if initial is None or final["creation_epoch"] != initial["creation_epoch"] or final["exit_epoch"] is None:
                    raise FixtureError("retained handle identity/exit closure")
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else metadata_error + "; " + detail
    changed = closing_differences(pins)
    effective_exit = int(child_exit)
    if metadata_error is not None and effective_exit == 0:
        effective_exit = 3
    if changed and effective_exit == 0:
        effective_exit = 4
    record = {"exit_code": effective_exit, "child_exit_code": int(child_exit), "pid": process.pid,
              "creation_epoch": initial["creation_epoch"] if initial is not None else None,
              "metadata_error": metadata_error, "changed_pins": changed, "retry": False, "gate": gate_evidence,
              "cpu_affinity": child_affinity, "elapsed_seconds": time.monotonic() - started, "process_times": final}
    write_json(observer / f"{label}.exit.json", record)
    return effective_exit, record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-review-path", type=Path, required=True)
    parser.add_argument("--final-review-sha256", required=True)
    args = parser.parse_args(argv)
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise FixtureError(f"unexpected Python: {sys.executable}")
    state = configure()
    if os.path.lexists(ROOT) or os.path.lexists(OBSERVER):
        raise FixtureError("exclusive wrapper fixture roots already exist")
    pins = verify_publication(args.final_review_path, args.final_review_sha256)
    gate_module = load_gate()
    initial_resources = gate(gate_module)  # Before every runtime fixture root.
    ROOT.mkdir(parents=False, exist_ok=False)
    OBSERVER.mkdir(parents=False, exist_ok=False)
    temporary = ROOT / "synthetic_tmp"
    temporary.mkdir(exist_ok=False)
    snapshots = snapshot_sources(pins, ROOT / "source_snapshots")
    write_json(OBSERVER / "admission.json", {"utc": utc_now(), "state": state, "initial_resources": initial_resources,
                                               "pins": pins, "snapshots": snapshots, "tmp": str(temporary), "scope": "WRAPPER_ONLY_SYNTHETIC"})

    def fail(stage: str, exit_code: int, record: Mapping[str, Any]) -> int:
        write_json(OBSERVER / "failure.json", {"status": "WRAPPER_FIXTURE_CHILD_FAILED", "stage": stage,
                                                 "exit_code": exit_code, "record": dict(record),
                                                 "closing_pins": closing_differences(pins), "retry": False})
        return exit_code

    try:
        compile_exit, compile_record = run_child("compile", [str(PYTHON), "-m", "py_compile", str(LAUNCHER), str(TESTS), str(HARNESS)], gate_module, temporary, OBSERVER, pins)
    except Exception as error:
        return fail("compile_admission_or_observation", 2, {"error": f"{type(error).__name__}: {error}"})
    if compile_exit != 0:
        return fail("compile", compile_exit, compile_record)
    try:
        ruff_exit, ruff_record = run_child("ruff", ["ruff", "check", str(LAUNCHER), str(TESTS), str(HARNESS)], gate_module, temporary, OBSERVER, pins)
    except Exception as error:
        return fail("ruff_admission_or_observation", 2, {"error": f"{type(error).__name__}: {error}"})
    if ruff_exit != 0:
        return fail("ruff", ruff_exit, ruff_record)
    try:
        pytest_exit, pytest_record = run_child("pytest", [str(PYTHON), "-m", "pytest", "-q", str(TESTS)], gate_module, temporary, OBSERVER, pins)
    except Exception as error:
        return fail("pytest_admission_or_observation", 2, {"error": f"{type(error).__name__}: {error}"})
    if pytest_exit != 0:
        return fail("pytest", pytest_exit, pytest_record)
    final_changed = closing_differences(pins)
    if final_changed:
        return fail("final_closing", 4, {"changed_pins": final_changed})
    write_json(OBSERVER / "closure.json", {"status": "PASS_CLOSED", "source_snapshots": snapshots,
                                             "closing_pins": pins, "changed_pins": [], "compile": compile_record,
                                             "ruff": ruff_record, "pytest": pytest_record})
    pytest_pin = write_json(OBSERVER / "pytest_retained_exit.json", {
        "exit_code": pytest_exit, "pid": pytest_record["pid"], "creation_epoch": pytest_record["creation_epoch"],
        "metadata_error": pytest_record["metadata_error"], "changed_pins": pytest_record["changed_pins"], "retry": False,
    })
    receipt = {"schema": "c_geometry_1030_producer_launcher_fixture_closure_v1", "status": "PASS_CLOSED",
               "launcher": pins[str(LAUNCHER)], "tests": pins[str(TESTS)], "compile_exit_code": 0,
               "ruff_exit_code": 0, "pytest_exit_code": 0, "pytest_exit": pytest_pin}
    write_json(OBSERVER / "formal_receipt.json", receipt)
    print(json.dumps({"status": "PASS_CLOSED", "pytest_pid": pytest_record["pid"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
