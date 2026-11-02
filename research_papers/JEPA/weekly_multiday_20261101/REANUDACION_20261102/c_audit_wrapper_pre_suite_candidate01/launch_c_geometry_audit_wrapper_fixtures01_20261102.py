"""Observed, wrapper-only formal fixture harness. It never runs C geometry or B."""
from __future__ import annotations

import argparse
import ctypes
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
ROOT = BASE / "weekly_zone_geometry_1030_audit_wrapper_fixtures_01"
OBSERVER = BASE / "weekly_zone_geometry_1030_audit_wrapper_fixtures_observer_01"
LAUNCHER = WEEK / "launch_weekly_zone_geometry_1030_audit_20261102.py"
TESTS = WEEK / "test_launch_weekly_zone_geometry_1030_audit_20261102.py"
CONTRACT = WEEK / "C_GEOMETRY_1030_AUDITOR_LAUNCH_CONTRACT_20261102.md"
PRODUCER_WRAPPER = WEEK / "launch_weekly_zone_geometry_1030_producer_20261102.py"
PRODUCER = WEEK / "build_weekly_zone_geometry_1030.py"
AUDITOR = WEEK / "audit_weekly_zone_geometry_1030.py"
HARNESS = Path(__file__).resolve()
HELPER = LEVEL / "launch_monthly_test_index_v2_audit_20261024.py"
THREAD_ENV = {name: "1" for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS", "ARROW_NUM_THREADS", "POLARS_MAX_THREADS", "TBB_NUM_THREADS", "NUMBA_NUM_THREADS")}
FROZEN = {
    LAUNCHER: (29480, "44efe3f7cd02abb8970d502bf2ce61d3d258cdf3c8b2f22ca82e204dbb7165f3"),
    TESTS: (14546, "bb91afcb64ffb339b289bb6d71bad0913492998a636075583ae4c65badb43326"),
    CONTRACT: (6148, "52bca4508587de08867e0c68c118a97a01f01ada5a170d20795f3043fe6fe1f5"),
    PRODUCER_WRAPPER: (49697, "9a7410432da2a495e8fb161c4ba83fd5f6b1f290798f9f154d61a2ffb11482f5"),
    PRODUCER: (73030, "ebe7c8984e2e7eb3806193e7c891dbbb0d0449b19e13e0657d0b68cdbe0d1b01"),
    AUDITOR: (93663, "f2d17a789bacf813be3b56652eab98fb4388afea8aaa4d691080e563cdc8b01e"),
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


def plain_exact(path: Path, expected_bytes: int, expected_sha256: str) -> dict[str, Any]:
    if path != Path(os.path.abspath(path)) or not PureWindowsPath(str(path)).is_absolute() or not path.is_file() or path.is_symlink():
        raise FixtureError("plain absolute file: " + str(path))
    current = path
    while True:
        info = os.lstat(current)
        if getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise FixtureError("reparse path: " + str(current))
        if current.parent == current:
            break
        current = current.parent
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != expected_bytes or sha256(path) != expected_sha256:
        raise FixtureError("pin mismatch: " + str(path))
    return {"path": str(path), "bytes": info.st_size, "sha256": expected_sha256}


def kernel32() -> Any:
    if os.name != "nt":
        raise FixtureError("Windows-only fixture harness")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetCurrentProcess.restype = ctypes.c_void_p
    api.SetProcessAffinityMask.argtypes, api.SetProcessAffinityMask.restype = [ctypes.c_void_p, ctypes.c_size_t], ctypes.c_int
    api.GetProcessAffinityMask.argtypes, api.GetProcessAffinityMask.restype = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)], ctypes.c_int
    api.GetProcessTimes.argtypes, api.GetProcessTimes.restype = [ctypes.c_void_p, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)], ctypes.c_int
    return api


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
    result = {"creation_epoch": epoch(creation), "exit_epoch": epoch(exited), "kernel_seconds": ticks(kernel_time) / 10_000_000.0, "user_seconds": ticks(user) / 10_000_000.0}
    if result["creation_epoch"] is None or not math.isfinite(result["creation_epoch"]):
        raise FixtureError("retained creation time")
    return result


def configure() -> dict[str, Any]:
    for name, value in THREAD_ENV.items():
        os.environ[name] = value
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    api = kernel32()
    if not api.SetProcessAffinityMask(api.GetCurrentProcess(), 1) or affinity() != 1:
        raise FixtureError("CPU0 affinity")
    return {"cpu_affinity_mask": 1, "thread_variables": dict(THREAD_ENV), "cuda_visible_devices": "-1"}


def gate() -> dict[str, Any]:
    plain_exact(HELPER, *FROZEN[HELPER])
    scope: dict[str, Any] = {"__name__": "audit_fixture_gate", "__file__": str(HELPER)}
    exec(compile(HELPER.read_bytes(), str(HELPER), "exec"), scope, scope)
    observation = scope["observation"]()
    scope["gate"](observation)
    resources = {"available_ram_bytes": observation.get("available_ram_bytes"), "free_commit_bytes": observation.get("free_commit_bytes")}
    disk = shutil.disk_usage(BASE).free
    if any(type(value) is not int or value < MINIMUM_BYTES for value in resources.values()) or disk < MINIMUM_BYTES:
        raise FixtureError("official 2GB RAM/commit/disk gate")
    return {"resources": resources, "disk_free_bytes": disk, "minimum_bytes": MINIMUM_BYTES}


def write_json(path: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": str(path), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def verify_publication(review: Path, review_sha256: str) -> dict[str, dict[str, Any]]:
    if not review.is_relative_to(REPO) or len(review_sha256) != 64:
        raise FixtureError("review publication input")
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    remote = subprocess.check_output(["git", "ls-remote", "origin", f"refs/heads/{BRANCH}"], cwd=REPO, text=True).split()
    if branch != BRANCH or not remote or remote[0] != commit:
        raise FixtureError("not published remote HEAD")
    pins = {str(path): plain_exact(path, size, digest) for path, (size, digest) in FROZEN.items()}
    pins[str(review)] = plain_exact(review, review.stat().st_size, review_sha256)
    pins[str(HARNESS)] = plain_exact(HARNESS, HARNESS.stat().st_size, sha256(HARNESS))
    text = review.read_text(encoding="utf-8")
    if any(token not in text for token in ("CLEAR_STATIC_PRE_SUITE_C_AUDITOR_WRAPPER", FROZEN[LAUNCHER][1], FROZEN[TESTS][1], FROZEN[CONTRACT][1])):
        raise FixtureError("review marker/source pins")
    for raw in pins:
        source = Path(raw)
        if subprocess.check_output(["git", "show", f"{commit}:{source.relative_to(REPO).as_posix()}"], cwd=REPO) != source.read_bytes():
            raise FixtureError("Git byte mismatch: " + str(source))
    return pins


def closing(pins: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    changed: list[dict[str, Any]] = []
    for raw, old in pins.items():
        try:
            actual = plain_exact(Path(raw), int(old["bytes"]), str(old["sha256"]))
        except Exception as error:
            actual = {"error": f"{type(error).__name__}: {error}"}
        if actual != dict(old):
            changed.append({"path": raw, "before": dict(old), "after": actual})
    return changed


def snapshot(pins: Mapping[str, Mapping[str, Any]], destination: Path) -> dict[str, Any]:
    destination.mkdir(exist_ok=False)
    records: dict[str, Any] = {}
    for ordinal, raw in enumerate(sorted(pins)):
        source = Path(raw)
        target = destination / f"{ordinal:02d}_{source.name}"
        with source.open("rb") as reader, target.open("xb") as writer:
            shutil.copyfileobj(reader, writer, 1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        records[raw] = {"source": dict(pins[raw]), "snapshot": plain_exact(target, int(pins[raw]["bytes"]), str(pins[raw]["sha256"]))}
    return records


def run_child(label: str, command: list[str], temporary: Path, pins: Mapping[str, Mapping[str, Any]]) -> tuple[int, dict[str, Any]]:
    evidence = gate()
    environment = os.environ.copy()
    environment["TMP"] = str(temporary)
    environment["TEMP"] = str(temporary)
    started = time.monotonic()
    with (OBSERVER / f"{label}.stdout.log").open("xb") as stdout, (OBSERVER / f"{label}.stderr.log").open("xb") as stderr:
        process = subprocess.Popen(command, cwd=str(WEEK), env=environment, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        metadata_error: str | None = None
        initial: dict[str, float | None] | None = None
        final: dict[str, float | None] | None = None
        child_affinity: int | None = None
        try:
            initial = process_times(int(process._handle))
            child_affinity = affinity(int(process._handle))
            if child_affinity != 1:
                raise FixtureError("child CPU affinity")
        except Exception as error:
            metadata_error = f"{type(error).__name__}: {error}"
        finally:
            child_exit = process.wait()
            try:
                final = process_times(int(process._handle))
                if initial is None or final["creation_epoch"] != initial["creation_epoch"] or final["exit_epoch"] is None:
                    raise FixtureError("retained child closure")
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else metadata_error + "; " + detail
    changed = closing(pins)
    effective = int(child_exit)
    if metadata_error is not None and effective == 0:
        effective = 3
    if changed and effective == 0:
        effective = 4
    record = {"exit_code": effective, "child_exit_code": int(child_exit), "pid": process.pid,
              "creation_epoch": initial["creation_epoch"] if initial else None, "cpu_affinity": child_affinity,
              "process_times": final, "elapsed_seconds": time.monotonic() - started,
              "metadata_error": metadata_error, "changed_pins": changed, "retry": False, "gate": evidence}
    write_json(OBSERVER / f"{label}.exit.json", record)
    return effective, record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-review-path", type=Path, required=True)
    parser.add_argument("--final-review-sha256", required=True)
    args = parser.parse_args(argv)
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise FixtureError("unexpected Python")
    state = configure()
    if os.path.lexists(ROOT) or os.path.lexists(OBSERVER):
        raise FixtureError("exclusive fixture roots already exist")
    pins = verify_publication(args.final_review_path, args.final_review_sha256)
    initial = gate()
    ROOT.mkdir(parents=False, exist_ok=False)
    OBSERVER.mkdir(parents=False, exist_ok=False)
    temporary = ROOT / "synthetic_tmp"
    temporary.mkdir(exist_ok=False)
    copies = snapshot(pins, ROOT / "source_snapshots")
    write_json(OBSERVER / "admission.json", {"state": state, "initial_gate": initial, "pins": pins, "source_snapshots": copies, "scope": "WRAPPER_ONLY_SYNTHETIC"})
    commands = [("compile", [str(PYTHON), "-m", "py_compile", str(LAUNCHER), str(TESTS), str(HARNESS)]), ("ruff", ["ruff", "check", str(LAUNCHER), str(TESTS), str(HARNESS)]), ("pytest", [str(PYTHON), "-m", "pytest", "-q", str(TESTS)])]
    results: dict[str, dict[str, Any]] = {}
    for label, child in commands:
        try:
            exit_code, record = run_child(label, child, temporary, pins)
        except Exception as error:
            write_json(OBSERVER / "failure.json", {"stage": label, "error": f"{type(error).__name__}: {error}", "retry": False, "closing_pins": closing(pins)})
            return 2
        results[label] = record
        if exit_code != 0:
            write_json(OBSERVER / "failure.json", {"stage": label, "record": record, "retry": False, "closing_pins": closing(pins)})
            return exit_code
    changed = closing(pins)
    if changed:
        write_json(OBSERVER / "failure.json", {"stage": "closing", "changed_pins": changed, "retry": False})
        return 4
    pytest_pin = write_json(OBSERVER / "pytest_retained_exit.json", {key: results["pytest"][key] for key in ("exit_code", "pid", "creation_epoch", "metadata_error", "changed_pins", "retry")})
    receipt = {"schema": "c_geometry_1030_audit_launcher_fixture_closure_v1", "status": "PASS_CLOSED", "launcher": pins[str(LAUNCHER)], "tests": pins[str(TESTS)], "compile_exit_code": 0, "ruff_exit_code": 0, "pytest_exit_code": 0, "pytest_exit": pytest_pin}
    write_json(OBSERVER / "formal_receipt.json", receipt)
    write_json(OBSERVER / "closure.json", {"status": "PASS_CLOSED", "source_snapshots": copies, "closing_pins": pins, "changed_pins": [], "compile": results["compile"], "ruff": results["ruff"], "pytest": results["pytest"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
