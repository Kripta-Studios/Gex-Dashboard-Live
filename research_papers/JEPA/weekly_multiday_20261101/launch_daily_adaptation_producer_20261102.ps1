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
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "POLARS_MAX_THREADS": "1",
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
OUTPUT = BASE / "h2_daily_adaptation_01"
OBSERVER = BASE / "h2_daily_adaptation_observer_01"
BRANCH = "research/multiscale-v1r1-net-usd"

CODE = WEEK / "evaluate_weekly_daily_adaptation.py"
TESTS = WEEK / "test_evaluate_weekly_daily_adaptation.py"
CONTRACT = WEEK / "DAILY_ADAPTATION_CONTRACT_20261101.md"
CONTRACT_REVIEW = WEEK / "DAILY_ADAPTATION_CONTRACT_REVIEW_20261101.md"
BINDING = WEEK / "DAILY_ADAPTATION_PRODUCER_RUNTIME_BINDING_20261102.md"
LAUNCHER = WEEK / "launch_daily_adaptation_producer_20261102.ps1"
GATE_HELPER = LEVEL / "launch_monthly_test_index_v2_audit_20261024.py"

REPO_PINS = {
    "evaluate_weekly_daily_adaptation.py": "536a581d8295362b3374dd8c5db2224095f8afe66c5b0e9ae895cf08b18d4f2e",
    "test_evaluate_weekly_daily_adaptation.py": "fa199a2a6339cf73911cc6f818c73f655cce1931e222733c041bff82b23e661e",
    "DAILY_ADAPTATION_CONTRACT_20261101.md": "5d388e484435c8fe23d40476c02928887c6ab5487af62197e5e74f08c1fe0047",
    "DAILY_ADAPTATION_CONTRACT_REVIEW_20261101.md": "bd0f514610c6d93167924aef651a2edf66e2d31c281e4be1fe0325ccd87eb841",
    "DAILY_ADAPTATION_PRODUCER_FINAL_REVIEW_20261102.md": "776ff783139386cee75fa6aa3bb4e0f75d74743c605fefb9d2aa373d5b720326",
    "daily_adaptation_preparation_archive_02/archive_receipt.json": "9eea35e9a13ad47653d714fd67059473341b5de2a656a71fd0415012b979f6e8",
    "daily_adaptation_preparation_archive_02/receipt.json": "0dbd6c8600037fb2f9b1054f19c2ec67a1eb65ec1f8f2ce3134c768b72d9bbfd",
    "evaluate_weekly_context_adaptation.py": "d03494bf68e281bc7c9e68f385aa111567eac4206cf5b44133e17bb480ed5df8",
    "evaluate_weekly_context_models.py": "bdc6534f059ade7acc58f23952a88ed2068c7a712518b04f438945a583a07a2f",
    "evaluate_weekly_h2_ev_v2.py": "8a9e75855d542a12662e5c812583f2ef86042f5c3ae1bbbad73c16042e063476",
    "replay_equal_risk_frozen.py": "e4f42a9fa65120939cf5e131911c8f2990a9cd33d21ae036fa98d9eb816d5b9d",
    "USER_MONTHLY_PROFITABILITY_ACCEPTANCE_20261101.md": "806f7728a2ad434bc08929d3715f307455bd37862ae4c19a2cd2cc1d64a5ee5b",
    "DAILY_ADAPTATION_PRODUCER_RUNTIME_BINDING_20261102.md": "39df4611f79842134313eb4c1468bdd8193a71f21e473656040cc29ded08d0bf",
}

EXTERNAL_PINS = {
    BASE / "h2_context_adaptation_01" / "manifest.json": "e8cf5cd4a001cd98cdf29e54cf47bbdf3c34d6652abf34ef7c71fffa0bd97f23",
    BASE / "h2_context_adaptation_audit_04" / "audit.json": "9a487fba18504ae4faff2c1dba17d1c000eb237436a09a7fe22747e328cb307a",
    BASE / "h2_context_adaptation_audit_observer_04" / "exit.json": "5d59d1a3978d8d9aa31c7c3fab567d1ae7e901494aa8efb12377ca65f91de420",
    BASE / "h2_boundary_bridge_01" / "manifest.json": "9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86",
    BASE / "h2_boundary_bridge_audit_01" / "audit.json": "83c9ade0b6b7205484dd275df8593107238f94468d8564f7351e9481a475033c",
}

GATE_HELPER_SHA256 = "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"


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


def git_bytes(commit, relative):
    return subprocess.check_output(
        ["git", "show", f"{commit}:{relative.as_posix()}"], cwd=REPO
    )


def repo_path(name):
    if "/" in name:
        return WEEK / Path(name)
    return WEEK / name


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
        ["git", "ls-remote", "origin", f"refs/heads/{BRANCH}"],
        cwd=REPO,
        text=True,
    ).split()[0]
    if remote != commit:
        raise RuntimeError("Local HEAD is not the published remote HEAD")
    for name, expected in REPO_PINS.items():
        path = repo_path(name)
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise RuntimeError(f"Repository pin mismatch: {name}")
        relative = path.relative_to(REPO)
        if git_bytes(commit, relative) != path.read_bytes():
            raise RuntimeError(f"Published bytes differ: {name}")
    for path in (LAUNCHER,):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"Missing launcher: {path}")
        if git_bytes(commit, path.relative_to(REPO)) != path.read_bytes():
            raise RuntimeError("Launcher is not byte-exact at published HEAD")
    return commit


def verify_external():
    for path, expected in EXTERNAL_PINS.items():
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise RuntimeError(f"External authority mismatch: {path}")
    upstream_exit = json.loads(
        (BASE / "h2_context_adaptation_audit_observer_04" / "exit.json").read_text(
            encoding="utf-8"
        )
    )
    if upstream_exit.get("exit_code") != 0:
        raise RuntimeError("Upstream audit did not close exit0")
    if not GATE_HELPER.is_file() or sha256(GATE_HELPER) != GATE_HELPER_SHA256:
        raise RuntimeError("Official resource helper mismatch")


def snapshot_pins():
    values = {}
    for name in REPO_PINS:
        path = repo_path(name)
        values[str(path)] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    values[str(LAUNCHER)] = {
        "bytes": LAUNCHER.stat().st_size,
        "sha256": sha256(LAUNCHER),
    }
    values[str(GATE_HELPER)] = {
        "bytes": GATE_HELPER.stat().st_size,
        "sha256": sha256(GATE_HELPER),
    }
    for path in EXTERNAL_PINS:
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
        "daily_official_resource_gate", GATE_HELPER
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
                "status": "RESOURCE_GATE_REJECTED_BEFORE_SCIENTIFIC_CHILD",
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
        str(CODE),
        "--execute-reviewed-daily-adaptation",
        "--output",
        str(OUTPUT),
        "--contract-sha256",
        REPO_PINS["DAILY_ADAPTATION_CONTRACT_20261101.md"],
        "--implementation-sha256",
        REPO_PINS["evaluate_weekly_daily_adaptation.py"],
        "--tests-sha256",
        REPO_PINS["test_evaluate_weekly_daily_adaptation.py"],
        "--review-sha256",
        REPO_PINS["DAILY_ADAPTATION_CONTRACT_REVIEW_20261101.md"],
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
    metadata_error = None
    creation_time = None
    child_affinity = None
    started = time.monotonic()
    started_utc = utc_now()
    result = None
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
                metadata_error = (
                    detail if metadata_error is None else f"{metadata_error}; {detail}"
                )
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
            "scientific_child_exit_code": result,
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
                    "status": "SCIENTIFIC_CHILD_OR_CLOSURE_FAILED",
                    "utc": utc_now(),
                    "exit_code": effective_result,
                    "scientific_child_exit_code": result,
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
