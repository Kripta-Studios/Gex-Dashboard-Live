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
OUTPUT = BASE / "weekly_zone_event_source_plan_01"
OBSERVER = BASE / "weekly_zone_event_source_plan_observer_01"
BRANCH = "research/multiscale-v1r1-net-usd"

BUILDER = WEEK / "build_weekly_zone_event_source_plan.py"
TESTS = WEEK / "test_build_weekly_zone_event_source_plan.py"
CONTRACT = WEEK / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_CONTRACT_20261102.md"
BINDING = WEEK / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_RUNTIME_BINDING_20261102.md"
LAUNCHER = WEEK / "launch_weekly_zone_event_source_plan_20261102.ps1"
GATE_HELPER = LEVEL / "launch_monthly_test_index_v2_audit_20261024.py"

REPO_PINS = {
    BUILDER: "9a412a3ad4b1ae6d527c92c7b1307dfceecb2aec1b4d81cfff70acf8e71c1270",
    TESTS: "ed4de57a2e4ff53f4f5f490377aa2a1338dba8aaf9b2939a028e9fad902e4121",
    CONTRACT: "c1891e794cab794d5f6570f99d838a888663a48b8ccededd4d96d27a63173d65",
    WEEK / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_CONTRACT_REVIEW_20261102.md": "e7c0b2a2ec27afa79bab63776eefb767a5db912289ebffb1879887ab5fa19167",
    WEEK / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_FINAL_REVIEW_20261102.md": "6446555cd13e6c6ea8a00db47fba757fc43acf6c1419265521f933a3140901c1",
    WEEK / "weekly_zone_event_source_plan_preparation_archive_01" / "receipt.json": "5e56ec66c3f12e29635e4d3fe95709aa70a03cd59c4b0f80b6650344a7120ea3",
    WEEK / "weekly_zone_event_source_plan_preparation_archive_01" / "archive_receipt.json": "45fcfee275ea0a4b787cf3313dbe3663d0c10f90ed62099b1ae1848b13c29855",
    BINDING: "8681f70dcd66d580c28ce774f75440396954f5ac6d9aa6e1b3da9f2d51fe27c0",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
}

EXTERNAL_PINS = {
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
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"Unexpected Python interpreter: {sys.executable}")
    psutil.Process().cpu_affinity([0])
    if psutil.Process().cpu_affinity() != [0]:
        raise RuntimeError("Parent affinity is not CPU[0]")
    commit = verify_publication()
    verify_external()
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
                "status": "RESOURCE_GATE_REJECTED_BEFORE_PLANNER_CHILD",
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
        str(BUILDER),
        "--execute-reviewed-plan",
        "--builder-sha256",
        REPO_PINS[BUILDER],
        "--tests-sha256",
        REPO_PINS[TESTS],
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
            "planner_child_exit_code": result,
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
                    "status": "PLANNER_CHILD_OR_CLOSURE_FAILED",
                    "utc": utc_now(),
                    "exit_code": effective_result,
                    "planner_child_exit_code": result,
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
