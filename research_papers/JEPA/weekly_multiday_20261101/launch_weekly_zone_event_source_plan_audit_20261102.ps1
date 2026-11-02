$ErrorActionPreference = 'Stop'

$Python = 'C:\Program Files\Python314\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Pinned Python interpreter is absent: $Python"
}

$Runner = @'
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

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import traceback
from datetime import datetime, timezone

import psutil


PYTHON = Path(r"C:\Program Files\Python314\python.exe")
REPO = Path(r"C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live")
WEEK = REPO / "research_papers" / "JEPA" / "weekly_multiday_20261101"
LEVEL = REPO / "research_papers" / "JEPA" / "level_oracle_20261018"
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
PRODUCER = BASE / "weekly_zone_event_source_plan_01"
PRODUCER_MANIFEST = PRODUCER / "manifest.json"
PRODUCER_EXIT = BASE / "weekly_zone_event_source_plan_observer_01" / "exit.json"
OUTPUT = BASE / "weekly_zone_event_source_plan_audit_01"
OBSERVER = BASE / "weekly_zone_event_source_plan_audit_observer_01"
BRANCH = "research/multiscale-v1r1-net-usd"

AUDITOR = WEEK / "audit_weekly_zone_event_source_plan.py"
AUDITOR_TESTS = WEEK / "test_audit_weekly_zone_event_source_plan.py"
PRODUCER_BUILDER = WEEK / "build_weekly_zone_event_source_plan.py"
PRODUCER_TESTS = WEEK / "test_build_weekly_zone_event_source_plan.py"
CONTRACT = WEEK / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_CONTRACT_20261102.md"
BINDING = WEEK / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_AUDIT_RUNTIME_BINDING_20261102.md"
LAUNCHER = WEEK / "launch_weekly_zone_event_source_plan_audit_20261102.ps1"
GATE_HELPER = LEVEL / "launch_monthly_test_index_v2_audit_20261024.py"

REPO_PINS = {
    AUDITOR: "118a349f4ca44e25f5764e7082e0775010fdf6f6a35fe3876c972af223d2762c",
    AUDITOR_TESTS: "289b00ca94cb4414b3f6db2cba70c1b7641e9e55a9f87f9b5a0ceb925a3da58e",
    PRODUCER_BUILDER: "9a412a3ad4b1ae6d527c92c7b1307dfceecb2aec1b4d81cfff70acf8e71c1270",
    PRODUCER_TESTS: "ed4de57a2e4ff53f4f5f490377aa2a1338dba8aaf9b2939a028e9fad902e4121",
    CONTRACT: "c1891e794cab794d5f6570f99d838a888663a48b8ccededd4d96d27a63173d65",
    WEEK / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_CONTRACT_REVIEW_20261102.md": "e7c0b2a2ec27afa79bab63776eefb767a5db912289ebffb1879887ab5fa19167",
    WEEK / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_AUDITOR_STATIC_REVIEW_20261102.md": "eb9f696cb85a02a62ab9caf9cd7335b25f621c7dfca37e6a3356365e125d2ca1",
    WEEK / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_AUDITOR_FINAL_REVIEW_20261102.md": "71ad8641711e0ed4264866e454a325fb6c7d6842ffa397c84f692110bc25f905",
    WEEK / "launch_weekly_zone_event_source_plan_audit_checks_20261102.py": "f11b40cff26d030635d1898665d74b8d8ff3fa1ccffe07793d28c66862f8c76f",
    WEEK / "weekly_zone_event_source_plan_audit_preparation_archive_01" / "receipt.json": "6a0f90d5e01cf37f9a7e9bf20dd119cfe7dbc2e8d0efd64a1af6e1ca95d14bf9",
    WEEK / "weekly_zone_event_source_plan_audit_preparation_archive_01" / "archive_receipt.json": "89805f2b782cf6ca7e3a527447f06faf647840db4b53385f6827a1241f31d57a",
    BINDING: "4a504a7bcc24b62638f0738353a3b5bc55059fabe5f9b37b0d566b9df5da24de",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
}

EXTERNAL_PINS = {
    PRODUCER_MANIFEST: "a0a9d330992d7f5768550c5b60401a701e1c1b02caec4a0967de50b7c7f13161",
    PRODUCER_EXIT: "b8f34b02dccf570f0f3ebaaa4a120fbaded81e5d76645ac7f1f68de688bf1a9b",
    BASE / "h2_dataset_v2_01" / "inventory.json": "099dcf065a62705cbd88f2c1b90b2e4a9b99ff4d994ad703634101920c934b12",
    BASE / "h2_dataset_v2_01" / "inventory_manifest.json": "c417e67f3499522d4ebd4a21bf28d1cba8ce249ef2d38a1352001216714bb899",
    BASE / "h2_dataset_v2_01" / "manifest.json": "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8",
    BASE / "h2_dataset_v2_extension_2026q3_partial_01" / "inventory.json": "f633d0ee192f28650698a4033ee7f6d2dc00dad07aa38239c40e9e2b5092ea5c",
    BASE / "h2_dataset_v2_extension_2026q3_partial_01" / "inventory_manifest.json": "5b39e0796599fa72b5d74d029885a24fd57fada207f12989576737aa46d75b2f",
    BASE / "h2_dataset_v2_extension_2026q3_partial_01" / "manifest.json": "b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b",
    BASE / "h2_boundary_bridge_01" / "inventory.json": "599ca400fecae12ce4098187a45af3ee0cf8c1b070e060d8c84e422ce92c6161",
    BASE / "h2_boundary_bridge_01" / "inventory_manifest.json": "0a7a5fab0f932d23fdf9a3140027f99eb85ccd958b79ef55152c53ab5ced70f2",
    BASE / "h2_boundary_bridge_01" / "manifest.json": "9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86",
    BASE / "h2_boundary_bridge_01" / "unified_calendar.json": "be622bb24aca35448594743dfeb5236e6b2d08a4410109b20302891f8c1fa7d6",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def git_bytes(commit, path):
    relative = Path(path).relative_to(REPO).as_posix()
    return subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=REPO)


def require_finalized():
    pending = {
        str(path): expected
        for path, expected in (*REPO_PINS.items(), *EXTERNAL_PINS.items())
        if expected.startswith("PENDING_")
    }
    if pending:
        raise RuntimeError(
            f"source-plan audit launcher draft is not executable; pending pins: {sorted(pending)}"
        )


def verify_publication():
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=REPO, text=True
    ).strip()
    if branch != BRANCH:
        raise RuntimeError(f"Unexpected branch: {branch}")
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
    ).strip()
    remote = subprocess.check_output(
        ["git", "ls-remote", "origin", f"refs/heads/{BRANCH}"], cwd=REPO, text=True
    ).split()[0]
    if remote != commit:
        raise RuntimeError("Local HEAD is not the published remote HEAD")
    for path, expected in REPO_PINS.items():
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise RuntimeError(f"Repository pin mismatch: {path}")
        if git_bytes(commit, path) != path.read_bytes():
            raise RuntimeError(f"Published bytes differ: {path}")
    if not LAUNCHER.is_file() or LAUNCHER.is_symlink():
        raise RuntimeError("Launcher is absent or linked")
    if git_bytes(commit, LAUNCHER) != LAUNCHER.read_bytes():
        raise RuntimeError("Launcher is not byte-exact at published HEAD")
    return commit


def verify_external():
    for path, expected in EXTERNAL_PINS.items():
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise RuntimeError(f"External compact authority mismatch: {path}")


def verify_producer_closure():
    manifest = json.loads(PRODUCER_MANIFEST.read_text(encoding="utf-8"))
    authority_paths = [
        path
        for path in EXTERNAL_PINS
        if path not in (PRODUCER_MANIFEST, PRODUCER_EXIT)
    ]
    admitted_inputs = {
        path.relative_to(BASE).as_posix(): {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": EXTERNAL_PINS[path],
        }
        for path in authority_paths
    }
    expected_flags = {
        "raw_values_read": False,
        "raw_files_hashed": False,
        "parquet_footers_read": False,
        "arrays_read": False,
        "outcomes_read": False,
        "fit_performed": False,
        "inference_performed": False,
        "replay_performed": False,
        "selected_policy": None,
        "technical_ready": False,
        "promotion_approved": False,
    }
    if not (
        manifest.get("schema") == "weekly_zone_event_source_plan_manifest_v1"
        and manifest.get("status") == "SOURCE_PLAN_NOT_VALUE_ADMISSION"
        and manifest.get("inputs") == admitted_inputs
        and set(manifest.get("outputs", {}))
        == {"entry_plan.jsonl", "weekly_sources.jsonl", "summary.json"}
        and set(manifest.get("implementation_pins", {}))
        == {"builder", "tests", "contract"}
        and manifest.get("flags") == expected_flags
    ):
        raise RuntimeError("Producer manifest admission metadata mismatch")
    implementations = manifest["implementation_pins"]
    if not (
        implementations["builder"].get("sha256") == REPO_PINS[PRODUCER_BUILDER]
        and implementations["tests"].get("sha256") == REPO_PINS[PRODUCER_TESTS]
        and implementations["contract"].get("sha256") == REPO_PINS[CONTRACT]
    ):
        raise RuntimeError("Producer implementation pins mismatch")
    for name, expected in manifest["outputs"].items():
        path = PRODUCER / name
        actual = {
            "path": str(path),
            "bytes": path.stat().st_size if path.is_file() else None,
            "sha256": sha256(path) if path.is_file() else None,
        }
        if expected != actual:
            raise RuntimeError(f"Producer output pin mismatch: {name}")
    exit_value = json.loads(PRODUCER_EXIT.read_text(encoding="utf-8"))
    if not (
        exit_value.get("exit_code") == 0
        and exit_value.get("planner_child_exit_code") == 0
        and exit_value.get("metadata_error") is None
        and exit_value.get("changed_pins") == []
        and exit_value.get("cpu_affinity") == [0]
        and exit_value.get("retry") is False
    ):
        raise RuntimeError("Producer retained exit metadata mismatch")


def snapshot_pins():
    values = {}
    for path in (*REPO_PINS, *EXTERNAL_PINS, LAUNCHER):
        values[str(path)] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    return values


def verify_closing(before):
    changed = []
    for name, expected in before.items():
        path = Path(name)
        actual = {
            "bytes": path.stat().st_size if path.is_file() else None,
            "sha256": sha256(path) if path.is_file() else None,
        }
        if actual != expected:
            changed.append({"path": name, "before": expected, "after": actual})
    return changed


def main():
    require_finalized()
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"Unexpected Python interpreter: {sys.executable}")
    psutil.Process().cpu_affinity([0])
    if psutil.Process().cpu_affinity() != [0]:
        raise RuntimeError("Parent affinity is not CPU[0]")
    commit = verify_publication()
    verify_external()
    verify_producer_closure()
    if OUTPUT.exists() or OBSERVER.exists():
        raise RuntimeError("Contracted output or observer root already exists")
    before = snapshot_pins()
    OBSERVER.mkdir(parents=False, exist_ok=False)

    specification = importlib.util.spec_from_file_location(
        "weekly_zone_source_plan_official_gate", GATE_HELPER
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("Could not import official resource helper")
    gate_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    resources = gate_module.observation()
    resource_record = {
        "utc": utc_now(),
        "resources": resources,
        "cpu_affinity": psutil.Process().cpu_affinity(),
        "thread_variables": {key: os.environ[key] for key in THREAD_ENV},
        "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
        "minimum_free_commit_bytes": 2_000_000_000,
        "publication_commit": commit,
        "pins": before,
    }
    write_json(OBSERVER / "resource_observation.json", resource_record)
    try:
        gate_module.gate(resources)
    except Exception as error:
        write_json(
            OBSERVER / "failure_receipt.json",
            {
                "status": "RESOURCE_GATE_REJECTED_BEFORE_AUDIT_CHILD",
                "utc": utc_now(),
                "error": f"{type(error).__name__}: {error}",
                "resources": resources,
                "child_created": False,
                "retry": False,
            },
        )
        raise

    args = [
        str(PYTHON),
        "-X",
        "utf8",
        "-u",
        str(AUDITOR),
        "--execute-reviewed-audit",
        "--producer-manifest-sha256",
        EXTERNAL_PINS[PRODUCER_MANIFEST],
        "--producer-exit-path",
        str(PRODUCER_EXIT),
        "--producer-exit-sha256",
        EXTERNAL_PINS[PRODUCER_EXIT],
        "--producer-builder-sha256",
        REPO_PINS[PRODUCER_BUILDER],
        "--producer-tests-sha256",
        REPO_PINS[PRODUCER_TESTS],
        "--auditor-sha256",
        REPO_PINS[AUDITOR],
        "--auditor-tests-sha256",
        REPO_PINS[AUDITOR_TESTS],
        "--contract-sha256",
        REPO_PINS[CONTRACT],
    ]
    write_json(
        OBSERVER / "admission.json",
        {
            "utc": utc_now(),
            "command": args,
            "publication_commit": commit,
            "resources": resources,
            "cpu_affinity": psutil.Process().cpu_affinity(),
            "thread_variables": {key: os.environ[key] for key in THREAD_ENV},
            "pins": before,
            "output": str(OUTPUT),
            "observer": str(OBSERVER),
        },
    )

    process = None
    result = None
    metadata_error = None
    creation_time = None
    child_affinity = None
    started = time.monotonic()
    started_utc = utc_now()
    with (OBSERVER / "stdout.log").open("wb") as stdout, (
        OBSERVER / "stderr.log"
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
                child = psutil.Process(process.pid)
                creation_time = child.create_time()
                child_affinity = child.cpu_affinity()
                if child_affinity != [0]:
                    raise RuntimeError(f"Child affinity is not CPU[0]: {child_affinity}")
            except Exception as error:
                metadata_error = f"{type(error).__name__}: {error}"
            try:
                write_json(
                    OBSERVER / "process.json",
                    {
                        "pid": process.pid,
                        "creation_time": creation_time,
                        "utc": started_utc,
                        "command": args,
                        "cpu_affinity": child_affinity,
                        "metadata_error": metadata_error,
                        "handle_retained": True,
                        "wait_pending": True,
                    },
                )
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else f"{metadata_error}; {detail}"
        finally:
            result = process.wait()

    changed = verify_closing(before)
    effective_result = result
    if metadata_error is not None and effective_result == 0:
        effective_result = 3
    if changed and effective_result == 0:
        effective_result = 4
    observed_files = {}
    for name in (
        "resource_observation.json",
        "admission.json",
        "process.json",
        "stdout.log",
        "stderr.log",
    ):
        path = OBSERVER / name
        if path.is_file():
            observed_files[str(path)] = sha256(path)
    write_json(
        OBSERVER / "exit.json",
        {
            "exit_code": effective_result,
            "audit_child_exit_code": result,
            "utc": utc_now(),
            "source": "subprocess.Popen.wait_retained_handle",
            "elapsed_seconds": time.monotonic() - started,
            "pid": process.pid,
            "creation_time": creation_time,
            "cpu_affinity": child_affinity,
            "metadata_error": metadata_error,
            "changed_pins": changed,
            "files": observed_files,
            "retry": False,
        },
    )
    if effective_result != 0:
        failure = OBSERVER / "failure_receipt.json"
        if not failure.exists():
            write_json(
                failure,
                {
                    "status": "AUDIT_CHILD_OR_CLOSURE_FAILED",
                    "utc": utc_now(),
                    "exit_code": effective_result,
                    "audit_child_exit_code": result,
                    "metadata_error": metadata_error,
                    "changed_pins": changed,
                    "retry": False,
                    "partial_output_not_authorized_for_adoption": True,
                },
            )
    print(
        json.dumps(
            {
                "pid": process.pid,
                "exit_code": effective_result,
                "observer": str(OBSERVER),
                "output": str(OUTPUT),
            },
            sort_keys=True,
        )
    )
    return int(effective_result)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        if OBSERVER.is_dir() and not (OBSERVER / "failure_receipt.json").exists():
            write_json(
                OBSERVER / "failure_receipt.json",
                {
                    "status": "LAUNCHER_FAILED_CLOSED",
                    "utc": utc_now(),
                    "error": f"{type(error).__name__}: {error}",
                    "traceback": traceback.format_exc(),
                    "retry": False,
                },
            )
        raise
'@

& $Python -X utf8 -u -c $Runner
exit $LASTEXITCODE
