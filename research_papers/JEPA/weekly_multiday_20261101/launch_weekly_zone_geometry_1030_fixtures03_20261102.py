"""Run the reviewed corrective synthetic fixture suite for weekly zone geometry at 10:30."""

from __future__ import annotations

import os
import sys

THREAD_ENV = {name: "1" for name in (
    "ARROW_NUM_THREADS", "BLIS_NUM_THREADS", "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS", "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS", "POLARS_MAX_THREADS", "TBB_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)}
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
GATE_HELPER = REPO / "research_papers" / "JEPA" / "level_oracle_20261018" / "launch_monthly_test_index_v2_audit_20261024.py"
HARNESS = Path(__file__).resolve()
MINIMUM_BYTES = 2_000_000_000
BRANCH = "research/multiscale-v1r1-net-usd"
GEOMETRY_BUILDER = WEEK / "build_weekly_zone_geometry_1030.py"
GEOMETRY_BUILDER_TESTS = WEEK / "test_build_weekly_zone_geometry_1030.py"
GEOMETRY_AUDITOR = WEEK / "audit_weekly_zone_geometry_1030.py"
GEOMETRY_AUDITOR_TESTS = WEEK / "test_audit_weekly_zone_geometry_1030.py"
GEOMETRY_CONTRACT = WEEK / "C_GEOMETRY_1030_ADMISSION_CONTRACT_20261102.md"
GEOMETRY_OPERATIONAL = WEEK / "C_GEOMETRY_1030_OPERATIONAL_DRAFT_20261102.md"
GEOMETRY_BINDING = WEEK / "C_GEOMETRY_1030_BINDING_FEASIBILITY_20261102.md"
GEOMETRY_WINDOWS = WEEK / "C_GEOMETRY_WINDOWS_PUBLICATION_FEASIBILITY_20261102.md"
GEOMETRY_AMENDMENT = WEEK / "C_GEOMETRY_PARALLEL_PREPARATION_AMENDMENT_20261102.md"
GEOMETRY_AMENDMENT_REVIEW = WEEK / "C_GEOMETRY_PARALLEL_PREPARATION_REVIEW_20261102.md"
ENGINE_ROOT = REPO / "research_papers" / "JEPA" / "level_oracle_20261018"
LEVEL_ENGINE = ENGINE_ROOT / "level_engine.py"
SESSION_LEVEL_ENGINE = ENGINE_ROOT / "session_level_engine.py"
SESSION_CLOCK = ENGINE_ROOT / "session_clock.py"
SESSION_CACHE = ENGINE_ROOT / "session_cache.py"
BUILD_CACHE = ENGINE_ROOT / "build_cache.py"
BUILDER_STATIC_REVIEW = WEEK / "C_GEOMETRY_PRODUCER_STATIC_REVIEW_20261102.md"
AUDITOR_STATIC_REVIEW = WEEK / "C_GEOMETRY_AUDITOR_STATIC_REVIEW_20261102.md"
LINT_CORRECTION_REVIEW = WEEK / "C_GEOMETRY_FIXTURE_LINT_CORRECTION_REVIEW_20261102.md"
PREPARATION = BASE / "weekly_zone_geometry_1030_fixtures_03"
ATTEMPT = PREPARATION / "attempt01"

PINS = {
    GEOMETRY_BUILDER: "ebe7c8984e2e7eb3806193e7c891dbbb0d0449b19e13e0657d0b68cdbe0d1b01",
    GEOMETRY_BUILDER_TESTS: "ec6aebc5c74d8dcc62e3a10a6ee2d4e722b1e6f58f84c4f56436abbd294dbcd5",
    GEOMETRY_AUDITOR: "f2d17a789bacf813be3b56652eab98fb4388afea8aaa4d691080e563cdc8b01e",
    GEOMETRY_AUDITOR_TESTS: "e010c83e6891cf600b5ee6cee16cc5e2eb9a269b6bbd27270ffc3cdaa0f53848",
    GEOMETRY_CONTRACT: "c28572543c1658ab87b1083d60bfdfbdc059c57960c5240c54f98bef5cdd8027",
    GEOMETRY_OPERATIONAL: "88f76551957e73e37c5dd816b00ec17d035132186df5071be10a5c534368cb3f",
    GEOMETRY_BINDING: "149fb9f9ddd3a01be24af1fd5f461a9ed7e0abad84d417837f11aff562d2f88a",
    GEOMETRY_WINDOWS: "f16d1a1c418fb51b5c5b180719c7a762ba338817a183c6006d472bc34ce13f31",
    GEOMETRY_AMENDMENT: "f32d3bb23a830c9c67197926ab9defa847e5b347422b90fcf1d54d5bdb09b237",
    GEOMETRY_AMENDMENT_REVIEW: "b3b056d2d447e407902a99d8567b437479ce1ee99e7efc7f62146e47c1fa2580",
    LEVEL_ENGINE: "70cc5d20990d971d16299fd008ff8e05ac99f99a6a2917a202fcb9a5f413b7c6",
    SESSION_LEVEL_ENGINE: "f93d3be334a2326dbec5d742e217bce63449e1beaf46b35fa46be83f25548883",
    SESSION_CLOCK: "1e63cf2d314caea14dd8b0b8f025f647d67bf8df58f246613975891a256f51e9",
    SESSION_CACHE: "6300a7f8e5c6c99101d32d642081f4b8dec170d3c40f2751c27f1642d55466f1",
    BUILD_CACHE: "985e87dcbd1e73289b58e4576445e47e73a6edea13e5ac73dde3ad629180d69f",
    BUILDER_STATIC_REVIEW: "226123c6da553ecffbf14744d036d50d71e09c8a641c9a79f22c4cc283a1f1b6",
    AUDITOR_STATIC_REVIEW: "b0985eb963eac2cd21d9562b28afe1153322664609d86c405e2b6704f8f13b5c",
    LINT_CORRECTION_REVIEW: "49c5c63ce7303c3305b8d3e01b41838e7e54f937844e26c63bed191ee159b8d9",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
}
PIN_BYTES = {
    GEOMETRY_BUILDER: 73030, GEOMETRY_BUILDER_TESTS: 35739,
    GEOMETRY_AUDITOR: 93663, GEOMETRY_AUDITOR_TESTS: 55343,
    GEOMETRY_CONTRACT: 14617, GEOMETRY_OPERATIONAL: 20544,
    GEOMETRY_BINDING: 8652, GEOMETRY_WINDOWS: 5695,
    GEOMETRY_AMENDMENT: 3761, GEOMETRY_AMENDMENT_REVIEW: 1212,
    LEVEL_ENGINE: 27435, SESSION_LEVEL_ENGINE: 21874, SESSION_CLOCK: 1046,
    SESSION_CACHE: 2371, BUILD_CACHE: 18248,
    BUILDER_STATIC_REVIEW: 2679, AUDITOR_STATIC_REVIEW: 2720,
    LINT_CORRECTION_REVIEW: 2176,
    GATE_HELPER: 31463,
}
EXPECTATION_CORRECTION_REVIEW = WEEK / "C_GEOMETRY_FIXTURE_EXPECTATION_CORRECTION_REVIEW_20261102.md"
PINS[EXPECTATION_CORRECTION_REVIEW] = "fd71bd638dc952275e2a8872fc9b88f10ac92d1d98f755bdbc59824d7bad3c1e"
PIN_BYTES[EXPECTATION_CORRECTION_REVIEW] = 2207
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
    process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
    if not KERNEL32.GetProcessAffinityMask(ctypes.c_void_p(handle), ctypes.byref(process_mask), ctypes.byref(system_mask)):
        raise ctypes.WinError(ctypes.get_last_error())
    return process_mask.value


def actual_process_state() -> dict[str, object]:
    affinity = affinity_mask(int(CURRENT_PROCESS))
    threads = {name: os.environ.get(name) for name in THREAD_ENV}
    cuda = os.environ.get("CUDA_VISIBLE_DEVICES")
    if affinity != 1 or any(value != "1" for value in threads.values()) or cuda != "-1":
        raise RuntimeError(f"parent process state drift: affinity={affinity}, threads={threads}, cuda={cuda}")
    return {"cpu_affinity_mask": affinity, "thread_variables": threads, "cuda_visible_devices": cuda}


def assert_plain_exact(path: Path, expected_bytes: int, expected_sha256: str) -> dict[str, object]:
    if path != Path(os.path.abspath(path)) or not path.is_file() or path.is_symlink():
        raise RuntimeError(f"pin absent, linked, or aliased: {path}")
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
        raise RuntimeError(f"ambiguous pin: {path}")
    digest = sha256(path)
    if info.st_size != expected_bytes or digest != expected_sha256:
        raise RuntimeError(f"pin mismatch: {path}")
    return {"bytes": info.st_size, "sha256": digest}


def require_finalized(harness_sha256: str) -> dict[Path, tuple[int, str]]:
    expected = {path: (PIN_BYTES[path], digest) for path, digest in PINS.items()}
    expected[HARNESS] = (HARNESS.stat().st_size, harness_sha256.lower())
    for expected_bytes, digest in expected.values():
        if not isinstance(expected_bytes, int) or expected_bytes < 1:
            raise RuntimeError("geometry fixture harness requires finalized byte pins")
        if len(digest) != 64 or digest != digest.lower() or any(character not in "0123456789abcdef" for character in digest):
            raise RuntimeError("geometry fixture harness requires finalized lowercase SHA-256 pins")
    return expected


def snapshot(expected: dict[Path, tuple[int, str]]) -> dict[str, dict[str, object]]:
    return {str(path): assert_plain_exact(path, size, digest) for path, (size, digest) in expected.items()}


def verify_publication(expected: dict[Path, tuple[int, str]]) -> str:
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip()
    if branch != BRANCH:
        raise RuntimeError(f"unexpected branch: {branch}")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    remote = subprocess.check_output(["git", "ls-remote", "origin", f"refs/heads/{BRANCH}"], cwd=REPO, text=True).split()[0]
    if commit != remote:
        raise RuntimeError("local HEAD is not published remote HEAD")
    for path in expected:
        try:
            relative = path.relative_to(REPO).as_posix()
        except ValueError:
            continue
        published = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=REPO)
        if published != path.read_bytes():
            raise RuntimeError(f"publication mismatch: {path}")
    return commit


def best_effort_diff(expected: dict[Path, tuple[int, str]]) -> list[dict[str, object]]:
    differences = []
    for path, (size, digest) in expected.items():
        try:
            actual = assert_plain_exact(path, size, digest)
        except Exception as error:
            differences.append({"path": str(path), "expected": {"bytes": size, "sha256": digest}, "actual": {"error": f"{type(error).__name__}: {error}"}})
    return differences


def observe_and_gate(gate_module: object, stage: str, expected: dict[Path, tuple[int, str]]) -> None:
    pins = snapshot(expected)
    state = actual_process_state()
    resources = gate_module.observation()
    disk_free = shutil.disk_usage(BASE).free
    record = {"utc": utc_now(), "stage": stage, **state, "resources": resources,
        "disk_free_bytes": disk_free, "minimum_bytes": MINIMUM_BYTES, "pins": pins, "child_created": False}
    write_json(ATTEMPT / f"{stage}_resource_observation.json", record)
    gate_module.gate(resources)
    if disk_free < MINIMUM_BYTES:
        raise RuntimeError(f"D: free bytes {disk_free} below {MINIMUM_BYTES}")


def run_child(name: str, command: list[str]) -> dict[str, object]:
    started, metadata_error, creation_epoch, child_mask = utc_now(), None, None, None
    with (ATTEMPT / f"{name}_stdout.txt").open("wb") as stdout, (ATTEMPT / f"{name}_stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(command, cwd=str(WEEK), env=os.environ.copy(), stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
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
                write_json(ATTEMPT / f"{name}_process.json", {"pid": process.pid, "creation_epoch": creation_epoch,
                    "start_utc": started, "command": command, "cpu_affinity_mask": child_mask,
                    "metadata_error": metadata_error, "handle_retained": True, "wait_pending": True})
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else f"{metadata_error}; {detail}"
        finally:
            exit_code = process.wait()
    result = {"pid": process.pid, "creation_epoch": creation_epoch, "start_utc": started, "end_utc": utc_now(),
        "command": command, "cpu_affinity_mask": child_mask, "metadata_error": metadata_error,
        "exit_code": exit_code, "handle_retained": True}
    write_json(ATTEMPT / f"{name}_exit.json", result)
    if metadata_error is not None:
        raise RuntimeError(metadata_error)
    return result


def failure(status: str, **extra: object) -> None:
    write_json(ATTEMPT / "failure_receipt.json", {"status": status, "attempt": "attempt01", "retry": False,
        "real_geometry_runtime_executed": False, "utc": utc_now(), "closing_pin_differences": best_effort_diff(ACTIVE_EXPECTED), **extra})


def main() -> int:
    global ACTIVE_EXPECTED
    parser = argparse.ArgumentParser(description="Run reviewed weekly-zone geometry synthetic fixtures")
    parser.add_argument("--harness-sha256", required=True)
    args = parser.parse_args()
    expected = require_finalized(args.harness_sha256)
    ACTIVE_EXPECTED = expected
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"unexpected Python: {sys.executable}")
    if PREPARATION.exists() or ATTEMPT.exists():
        raise RuntimeError("geometry fixture root already exists")
    snapshot(expected)
    publication_commit = verify_publication(expected)
    PREPARATION.mkdir(parents=False, exist_ok=False)
    ATTEMPT.mkdir(parents=False, exist_ok=False)
    for source, (_size, digest) in expected.items():
        shutil.copyfile(source, ATTEMPT / f"{digest}_{source.name}.before_test")
    write_json(ATTEMPT / "publication.json", {"commit": publication_commit, "branch": BRANCH, "verified_utc": utc_now()})

    specification = importlib.util.spec_from_file_location("official_gate", GATE_HELPER)
    if specification is None or specification.loader is None:
        raise RuntimeError("official gate import unavailable")
    gate_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    try:
        observe_and_gate(gate_module, "preflight", expected)
    except Exception as error:
        failure("RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_GEOMETRY_FIXTURES", error=f"{type(error).__name__}: {error}", completed=[])
        return 2

    suite_files = [str(GEOMETRY_BUILDER), str(GEOMETRY_BUILDER_TESTS), str(GEOMETRY_AUDITOR), str(GEOMETRY_AUDITOR_TESTS)]
    commands = [
        ("compile", [str(PYTHON), "-X", "utf8", "-m", "py_compile", *suite_files]),
        ("ruff", [str(PYTHON), "-X", "utf8", "-m", "ruff", "check", *suite_files]),
        ("pytest", [str(PYTHON), "-X", "utf8", "-m", "pytest", "-q", str(GEOMETRY_BUILDER_TESTS), str(GEOMETRY_AUDITOR_TESTS)]),
    ]
    completed: list[dict[str, object]] = []
    for name, command in commands:
        try:
            observe_and_gate(gate_module, name, expected)
        except Exception as error:
            failure("RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_GEOMETRY_FIXTURE_CHILD", stage=name, completed=completed, error=f"{type(error).__name__}: {error}", child_created=False)
            return 2
        try:
            result = run_child(name, command)
        except Exception as error:
            failure("GEOMETRY_FIXTURE_CHILD_LAUNCH_OR_OBSERVATION_FAILED", stage=name, completed=completed, error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
            return 3
        completed.append({"stage": name, "exit_code": result["exit_code"]})
        if result["exit_code"] != 0:
            failure("FORMAL_GEOMETRY_FIXTURE_STAGE_FAILED", stage=name, completed=completed, exit_code=result["exit_code"])
            return int(result["exit_code"]) or 1
    closing = snapshot(expected)
    receipt = {"status": "PASS_FORMAL_SYNTHETIC_WEEKLY_ZONE_GEOMETRY_1030_FIXTURES03", "attempt": "attempt01",
        "stages": completed, "closing_sha256": closing, "real_geometry_runtime_executed": False,
        "fit_performed": False, "raw_market_data_read": False, "real_dataset_read": False,
        "api_read": False, "broker_read": False, "retry": False, "closed_utc": utc_now()}
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
            failure("GEOMETRY_FIXTURE_HARNESS_FAILED_CLOSED", error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
        raise

