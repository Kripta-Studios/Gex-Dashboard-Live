"""Observed synthetic cross-implementation fixture harness; no real D/B/C work."""
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
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
BRANCH = "research/multiscale-v1r1-net-usd"
MINIMUM_BYTES = 2_000_000_000
ROOT = BASE / "weekly_zone_revisit_integration_fixtures_01"
OBSERVER = BASE / "weekly_zone_revisit_integration_fixtures_observer_01"
PRODUCER = WEEK / "weekly_zone_revisit_mechanics.py"
AUDITOR = WEEK / "audit_weekly_zone_revisit_mechanics.py"
ACCOUNTING = WEEK / "weekly_zone_revisit_accounting.py"
INTEGRATION_TEST = WEEK / "test_weekly_zone_revisit_mechanics_integration.py"
HARNESS = Path(os.path.abspath(__file__))
RESOURCE_HELPER = REPO / "research_papers" / "JEPA" / "level_oracle_20261018" / "launch_monthly_test_index_v2_audit_20261024.py"
MECHANICAL_DRAFT = WEEK / "WEEKLY_ZONE_REVISIT_MECHANICAL_REPLAY_DRAFT_20261102.md"
ADDENDUM = WEEK / "WEEKLY_ZONE_REVISIT_D_OPERATIONAL_ADDENDUM_DRAFT_20261102.md"
PARALLEL_AMENDMENT = WEEK / "D_REVISIT_PARALLEL_MECHANICS_PREPARATION_AMENDMENT_20261102.md"
RECORD_INTERFACE = WEEK / "D_REVISIT_MECHANICS_RECORD_INTERFACE_20261102.md"
CAUSAL_CLARIFICATION = WEEK / "D_REVISIT_CAUSAL_TERMINAL_CLARIFICATION_20261102.md"
TRACE_CLARIFICATION = WEEK / "D_REVISIT_TRACE_CLARIFICATION_20261102.md"
MECHANICS_REVIEW = WEEK / "D_REVISIT_MECHANICS_FINAL_IMPLEMENTATION_REVIEW_20261102.md"
ACCOUNTING_REVIEW = WEEK / "D_REVISIT_ACCOUNTING_FINAL_IMPLEMENTATION_REVIEW_20261102.md"
AUDITOR_REVIEW = WEEK / "D_REVISIT_AUDITOR_FINAL_IMPLEMENTATION_REVIEW_20261102.md"
INTEGRATION_STATIC_REVIEW = WEEK / "D_REVISIT_INTEGRATION_STATIC_REVIEW_20261102.md"
MECHANICS_RECEIPT = WEEK / "REANUDACION_20261102" / "d_mechanics_fixtures02" / "formal_receipt.json"
MECHANICS_EXIT = WEEK / "REANUDACION_20261102" / "d_mechanics_fixtures02" / "pytest_retained_exit.json"
AUDITOR_RECEIPT = WEEK / "REANUDACION_20261102" / "d_auditor_fixtures03" / "formal_receipt.json"
AUDITOR_EXIT = WEEK / "REANUDACION_20261102" / "d_auditor_fixtures03" / "pytest_retained_exit.json"
THREAD_ENV = {
    name: "1"
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "BLIS_NUM_THREADS",
        "ARROW_NUM_THREADS",
        "POLARS_MAX_THREADS",
        "TBB_NUM_THREADS",
        "NUMBA_NUM_THREADS",
    )
}
FROZEN = {
    PRODUCER: (38317, "6c8677453d08699825c4c5cc2439af6eb0f48e7433dab6dea7d812c8c07c34a7"),
    AUDITOR: (68119, "c6c77b1e12b166796c06335621b606b03006617e3dc0a374a2bc2d489ec554d7"),
    ACCOUNTING: (18783, "9bcc4f834745806289550d2119f7d35ad0281c2fe151ac36c87be24aa72594fb"),
    INTEGRATION_TEST: (10675, "ee549203a778545ac0ed07546135a67526b1b65fe92bb758caaad38b914c8ead"),
    RESOURCE_HELPER: (31463, "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"),
    MECHANICAL_DRAFT: (14258, "4ea0fe7b149c04f8859ea1e3b7fa1058a2d826569b6b054fbefab10c5ba16dc7"),
    ADDENDUM: (38704, "c567116055faefa2310dd574a77ca07efc8970314ff0d6b6a8131b773699388a"),
    PARALLEL_AMENDMENT: (7109, "d5a6be66d4a47ad4a4eca4957bccf96049838eabe1b176904c3d16f04ef37f7f"),
    RECORD_INTERFACE: (19358, "662147864f8cf446b39fc07e17f8ef7650ffd920dea75bc75d6411b791ddcc1d"),
    CAUSAL_CLARIFICATION: (6230, "de8fb6b43ecf39c22c1e57a3e9cf3893aee442e4a299a1fcf10aaa0dca140f22"),
    TRACE_CLARIFICATION: (4288, "27c5e083afde5bfa8d262f3db4280074039b8b04e6147fc648522e401a9fe820"),
    MECHANICS_REVIEW: (2933, "02794cf9d3f9eac04ddf4ab0ce9aa81a196b0cc7da1db97aa65994e05a6980db"),
    ACCOUNTING_REVIEW: (2811, "0d9048369299e3086aadd7eb24574bd4fe0e645e454e34e3cec154e74a4b9fed"),
    AUDITOR_REVIEW: (3414, "42cd7809932b73a9f7b97da3ac839bac1dee5b5b679715d99a2b55bd870b69d7"),
    INTEGRATION_STATIC_REVIEW: (2234, "03f7a401c906103419621882e2bd737922cdab98f5be8be6c2022862bb516460"),
    MECHANICS_RECEIPT: (1208, "da70bd857bca2ad948d53f2737aef28a19e80b0f72f761e0d6171849da5cdc33"),
    MECHANICS_EXIT: (118, "5f289ca3a9c6ed332b7eb9f48e820b4364b223d42a6a023ecb1b509c6120841a"),
    AUDITOR_RECEIPT: (933, "8719d472681f3a95125a4b7676f34794b9e5d8f588fcd79a1cf0647c7f9cab87"),
    AUDITOR_EXIT: (118, "b26bf28e42755dc02a6e6741886f07516139037cff5f48b8e7fcfc7e42f40c12"),
}
PUBLIC_REVIEW_REQUIREMENTS = {
    MECHANICS_REVIEW: (
        "CLEAR_FINAL_IMPLEMENTATION_D_MECHANICS_FIXTURES_ONLY",
        FROZEN[PRODUCER][1],
        FROZEN[ACCOUNTING][1],
    ),
    ACCOUNTING_REVIEW: (
        "CLEAR_FINAL_IMPLEMENTATION_ACCOUNTING_FIXTURES_ONLY",
        FROZEN[ACCOUNTING][1],
    ),
    AUDITOR_REVIEW: (
        "CLEAR_FINAL_IMPLEMENTATION_D_AUDITOR_FIXTURES_ONLY",
        FROZEN[AUDITOR][1],
    ),
    INTEGRATION_STATIC_REVIEW: ("CLEAR_STATIC_PRE_SUITE_D_REVISIT_INTEGRATION_CONDITIONAL", FROZEN[INTEGRATION_TEST][1]),
}
FINAL_REVIEW_MARKER = "CLEAR_D_REVISIT_INTEGRATION_FIXTURE_HARNESS"
FINAL_REVIEW_SOURCE_HASHES = tuple(FROZEN[path][1] for path in (PRODUCER, AUDITOR, ACCOUNTING, INTEGRATION_TEST))


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


def plain_exact(path: Path, size: int, digest: str) -> dict[str, Any]:
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
    actual = sha256(path)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size or actual != digest:
        raise FixtureError("pin mismatch: " + str(path))
    return {"path": str(path), "bytes": info.st_size, "sha256": actual}


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
    created, exited, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
    if not api.GetProcessTimes(ctypes.c_void_p(handle), ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
        raise ctypes.WinError(ctypes.get_last_error())

    def ticks(value: FILETIME) -> int:
        return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)

    def epoch(value: FILETIME) -> float | None:
        raw = ticks(value)
        return None if raw == 0 else (raw - 116_444_736_000_000_000) / 10_000_000.0

    result = {
        "creation_epoch": epoch(created),
        "exit_epoch": epoch(exited),
        "kernel_seconds": ticks(kernel) / 10_000_000.0,
        "user_seconds": ticks(user) / 10_000_000.0,
    }
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
    plain_exact(RESOURCE_HELPER, *FROZEN[RESOURCE_HELPER])
    scope: dict[str, Any] = {"__name__": "integration_fixture_gate", "__file__": str(RESOURCE_HELPER)}
    exec(compile(RESOURCE_HELPER.read_bytes(), str(RESOURCE_HELPER), "exec"), scope, scope)
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


def git_bytes_match(commit: str, paths: Sequence[Path]) -> None:
    for path in paths:
        relative = path.relative_to(REPO).as_posix()
        if subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=REPO) != path.read_bytes():
            raise FixtureError("Git byte mismatch: " + str(path))


def require_review_tokens(path: Path, tokens: Sequence[str]) -> None:
    content = path.read_text(encoding="utf-8")
    if any(token not in content for token in tokens):
        raise FixtureError("review markers/source pins: " + str(path))


def verify_publication(review: Path, review_sha256: str) -> dict[str, dict[str, Any]]:
    if not review.is_relative_to(REPO) or len(review_sha256) != 64 or not review.is_file() or review.is_symlink():
        raise FixtureError("combined review input")
    review_pin = plain_exact(review, review.stat().st_size, review_sha256)
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    remote = subprocess.check_output(["git", "ls-remote", "origin", f"refs/heads/{BRANCH}"], cwd=REPO, text=True).split()
    if branch != BRANCH or not remote or remote[0] != commit:
        raise FixtureError("not published remote HEAD")
    pins = {str(path): plain_exact(path, size, digest) for path, (size, digest) in FROZEN.items()}
    pins[str(review)] = review_pin
    pins[str(HARNESS)] = plain_exact(HARNESS, HARNESS.stat().st_size, sha256(HARNESS))
    for path, tokens in PUBLIC_REVIEW_REQUIREMENTS.items():
        require_review_tokens(path, tokens)
    require_review_tokens(review, (FINAL_REVIEW_MARKER, *FINAL_REVIEW_SOURCE_HASHES, pins[str(HARNESS)]["sha256"]))
    git_bytes_match(commit, [*FROZEN, review, HARNESS])
    return pins


def json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FixtureError("closure JSON: " + str(path)) from error
    if not isinstance(value, dict):
        raise FixtureError("closure object: " + str(path))
    return value


def require_source_pin(receipt: Mapping[str, Any], field: str, path: Path) -> None:
    expected_size, expected_hash = FROZEN[path]
    pin = receipt.get(field)
    if not isinstance(pin, Mapping) or pin.get("path") != str(path) or pin.get("bytes") != expected_size or pin.get("sha256") != expected_hash:
        raise FixtureError("closed source pin: " + field)


def validate_closed_fixture(receipt_path: Path, exit_path: Path, schema: str, source_fields: Mapping[str, Path]) -> dict[str, Any]:
    receipt, retained_exit = json_object(receipt_path), json_object(exit_path)
    if receipt.get("schema") != schema or receipt.get("status") != "PASS_CLOSED":
        raise FixtureError("closed receipt status: " + str(receipt_path))
    for field in ("compile_exit_code", "ruff_exit_code", "pytest_exit_code"):
        if receipt.get(field) != 0 or type(receipt.get(field)) is not int:
            raise FixtureError("closed receipt exit: " + field)
    for field, path in source_fields.items():
        require_source_pin(receipt, field, path)
    retained_pin = receipt.get("pytest_exit")
    exit_size, exit_hash = FROZEN[exit_path]
    if not isinstance(retained_pin, Mapping) or retained_pin.get("bytes") != exit_size or retained_pin.get("sha256") != exit_hash:
        raise FixtureError("closed receipt retained exit pin")
    if not isinstance(retained_pin.get("path"), str) or not PureWindowsPath(retained_pin["path"]).is_absolute():
        raise FixtureError("closed receipt retained exit path")
    if retained_exit.get("exit_code") != 0 or type(retained_exit.get("exit_code")) is not int:
        raise FixtureError("closed retained exit code")
    if retained_exit.get("metadata_error") is not None or retained_exit.get("changed_pins") != [] or retained_exit.get("retry") is not False:
        raise FixtureError("closed retained exit metadata")
    return {"receipt": str(receipt_path), "schema": schema, "status": "PASS_CLOSED", "retained_exit": str(exit_path)}


def validate_closed_components() -> dict[str, dict[str, Any]]:
    return {
        "mechanics": validate_closed_fixture(
            MECHANICS_RECEIPT,
            MECHANICS_EXIT,
            "d_revisit_mechanics_fixture_closure_v1",
            {"producer": PRODUCER, "accounting_helper": ACCOUNTING},
        ),
        "auditor": validate_closed_fixture(
            AUDITOR_RECEIPT,
            AUDITOR_EXIT,
            "d_revisit_auditor_fixture_closure_v1",
            {"auditor": AUDITOR},
        ),
    }


def closing(pins: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    changed = []
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
    records = {}
    for ordinal, raw in enumerate(sorted(pins)):
        source, target = Path(raw), destination / f"{ordinal:02d}_{Path(raw).name}"
        with source.open("rb") as reader, target.open("xb") as writer:
            shutil.copyfileobj(reader, writer, 1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        records[raw] = {"source": dict(pins[raw]), "snapshot": plain_exact(target, int(pins[raw]["bytes"]), str(pins[raw]["sha256"]))}
    return records


def run_child(label: str, command: list[str], temporary: Path, pins: Mapping[str, Mapping[str, Any]]) -> tuple[int, dict[str, Any]]:
    evidence = gate()
    environment = os.environ.copy()
    environment["TMP"], environment["TEMP"] = str(temporary), str(temporary)
    started = time.monotonic()
    with (OBSERVER / f"{label}.stdout.log").open("xb") as stdout, (OBSERVER / f"{label}.stderr.log").open("xb") as stderr:
        process = subprocess.Popen(command, cwd=str(WEEK), env=environment, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        metadata_error, initial, final, child_affinity = None, None, None, None
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
    changed, effective = closing(pins), int(child_exit)
    if metadata_error is not None and effective == 0:
        effective = 3
    if changed and effective == 0:
        effective = 4
    record = {
        "exit_code": effective,
        "child_exit_code": int(child_exit),
        "pid": process.pid,
        "creation_epoch": initial["creation_epoch"] if initial else None,
        "cpu_affinity": child_affinity,
        "process_times": final,
        "elapsed_seconds": time.monotonic() - started,
        "metadata_error": metadata_error,
        "changed_pins": changed,
        "retry": False,
        "gate": evidence,
    }
    write_json(OBSERVER / f"{label}.exit.json", record)
    return effective, record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-review-path", type=Path, required=True)
    parser.add_argument("--final-review-sha256", required=True)
    args = parser.parse_args(argv)
    state = configure()
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise FixtureError("unexpected Python")
    if os.path.lexists(ROOT) or os.path.lexists(OBSERVER):
        raise FixtureError("exclusive fixture roots already exist")
    pins = verify_publication(args.final_review_path, args.final_review_sha256)
    closed_components = validate_closed_components()
    initial = gate()
    ROOT.mkdir(parents=False, exist_ok=False)
    OBSERVER.mkdir(parents=False, exist_ok=False)
    temporary = ROOT / "synthetic_tmp"
    temporary.mkdir(exist_ok=False)
    copies = snapshot(pins, ROOT / "source_snapshots")
    write_json(
        OBSERVER / "admission.json",
        {
            "state": state,
            "initial_gate": initial,
            "closed_components": closed_components,
            "pins": pins,
            "source_snapshots": copies,
            "scope": "SYNTHETIC_CROSS_IMPLEMENTATION_AGREEMENT_ONLY",
        },
    )
    commands = [
        ("compile", [str(PYTHON), "-m", "py_compile", str(INTEGRATION_TEST), str(HARNESS)]),
        ("ruff", ["ruff", "check", str(INTEGRATION_TEST), str(HARNESS)]),
        ("pytest", [str(PYTHON), "-m", "pytest", "-q", str(INTEGRATION_TEST)]),
    ]
    results = {}
    for label, command in commands:
        try:
            exit_code, record = run_child(label, command, temporary, pins)
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
    pytest_exit = write_json(
        OBSERVER / "pytest_retained_exit.json",
        {key: results["pytest"][key] for key in ("exit_code", "pid", "creation_epoch", "metadata_error", "changed_pins", "retry")},
    )
    receipt = {
        "schema": "d_revisit_integration_fixture_closure_v1",
        "status": "PASS_CLOSED",
        "producer": pins[str(PRODUCER)],
        "auditor": pins[str(AUDITOR)],
        "accounting_helper": pins[str(ACCOUNTING)],
        "integration_tests": pins[str(INTEGRATION_TEST)],
        "compile_exit_code": 0,
        "ruff_exit_code": 0,
        "pytest_exit_code": 0,
        "pytest_exit": pytest_exit,
    }
    write_json(OBSERVER / "formal_receipt.json", receipt)
    write_json(
        OBSERVER / "closure.json",
        {
            "status": "PASS_CLOSED",
            "source_snapshots": copies,
            "closing_pins": pins,
            "changed_pins": [],
            "compile": results["compile"],
            "ruff": results["ruff"],
            "pytest": results["pytest"],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
