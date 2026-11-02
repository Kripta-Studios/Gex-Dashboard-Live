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
PRODUCER = BASE / "h2_daily_adaptation_01"
PRODUCER_MANIFEST = PRODUCER / "manifest.json"
PRODUCER_EXIT = BASE / "h2_daily_adaptation_observer_01" / "exit.json"
ROOT_RECEIPT = BASE / "h2_daily_adaptation_closure_01" / "root_metadata_receipt.json"
OUTPUT = BASE / "h2_daily_adaptation_audit_01"
OBSERVER = BASE / "h2_daily_adaptation_audit_observer_01"
BRANCH = "research/multiscale-v1r1-net-usd"

AUDITOR = WEEK / "audit_weekly_daily_adaptation.py"
TESTS = WEEK / "test_audit_weekly_daily_adaptation.py"
BINDING = WEEK / "DAILY_ADAPTATION_AUDIT_RUNTIME_BINDING_20261102.md"
LAUNCHER = WEEK / "launch_daily_adaptation_audit_20261102.ps1"
GATE_HELPER = LEVEL / "launch_monthly_test_index_v2_audit_20261024.py"

PRODUCER_MANIFEST_SHA256 = "7decb3e2baf360d807fd849604013728f5fe05c48dcd3302c0b270a1440d2206"
PRODUCER_EXIT_SHA256 = "54021b954d522e0c9535b237de45a63da14a39e91e12e71fe90546d351f9f0d0"
ROOT_RECEIPT_SHA256 = "2b59260b4019f7e04199a6353b58bdcb8fd995c671e23cb6485ab6fa67533a2d"
GATE_HELPER_SHA256 = "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"

REPO_PINS = {
    "audit_weekly_daily_adaptation.py": "ccd4cf685b0b3975c4340c372758ac7a5ffc47d046905853a8b01f92a175e7d9",
    "test_audit_weekly_daily_adaptation.py": "f2eeb1e871705c9a00305c6f8ecc439177cff36a30b9ffad9610996e41977130",
    "DAILY_ADAPTATION_CONTRACT_20261101.md": "5d388e484435c8fe23d40476c02928887c6ab5487af62197e5e74f08c1fe0047",
    "DAILY_ADAPTATION_CONTRACT_REVIEW_20261101.md": "bd0f514610c6d93167924aef651a2edf66e2d31c281e4be1fe0325ccd87eb841",
    "DAILY_ADAPTATION_AUDITOR_FINAL_REVIEW_20261102.md": "fbeba418c42baa86f8be4464383dccd33dee4442a121d4476824d293273be573",
    "daily_adaptation_audit_checks_archive_01/archive_receipt.json": "ace119b93266a3a594bdeef4e78b7c99b60e414f635100baf3e2a30f1e56c871",
    "daily_adaptation_audit_checks_archive_01/attempt02/receipt.json": "7e2354c56b3488cad6986c60430cd170bde492370ca11773e2dc3008a1ccc4b0",
    "audit_weekly_context_adaptation_v4.py": "0723696ae01dcc86af7c2af8e8fdc2e3b281ba913987a65d95bd4703c959aa9c",
    "audit_weekly_context_models.py": "3eb6b9795ad260971435259858f86d3c00111bcc141973faf986411d4a68ad99",
    "DAILY_ADAPTATION_AUDIT_RUNTIME_BINDING_20261102.md": "b0e580b0001b5571b9f239a776085e942a0464e73c3cd3d363d9a4bdeb623e69",
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


def repo_path(name):
    return WEEK / Path(name)


def git_bytes(commit, relative):
    return subprocess.check_output(
        ["git", "show", f"{commit}:{relative.as_posix()}"], cwd=REPO
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
        if git_bytes(commit, path.relative_to(REPO)) != path.read_bytes():
            raise RuntimeError(f"Published bytes differ: {name}")
    if not LAUNCHER.is_file() or LAUNCHER.is_symlink():
        raise RuntimeError("Audit launcher missing or linked")
    if git_bytes(commit, LAUNCHER.relative_to(REPO)) != LAUNCHER.read_bytes():
        raise RuntimeError("Audit launcher is not byte-exact at published HEAD")
    return commit


def verify_producer_closure():
    fixed = {
        PRODUCER_MANIFEST: PRODUCER_MANIFEST_SHA256,
        PRODUCER_EXIT: PRODUCER_EXIT_SHA256,
        ROOT_RECEIPT: ROOT_RECEIPT_SHA256,
        GATE_HELPER: GATE_HELPER_SHA256,
    }
    for path, expected in fixed.items():
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise RuntimeError(f"Producer/authority pin mismatch: {path}")
    manifest = json.loads(PRODUCER_MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "weekly_daily_adaptation_manifest_v1"
        or manifest.get("status") != "COMPLETE_SEEN_DEVELOPMENT_NOT_PROMOTED"
        or len(manifest.get("inputs", {})) != 45
        or len(manifest.get("outputs", {})) != 152
    ):
        raise RuntimeError("Producer manifest metadata mismatch")
    exit_value = json.loads(PRODUCER_EXIT.read_text(encoding="utf-8"))
    if not (
        exit_value.get("exit_code") == 0
        and exit_value.get("scientific_child_exit_code") == 0
        and exit_value.get("metadata_error") is None
        and exit_value.get("changed_pins") == []
        and exit_value.get("cpu_affinity") == [0]
    ):
        raise RuntimeError("Producer retained exit metadata mismatch")


def snapshot_pins():
    values = {}
    for name in REPO_PINS:
        path = repo_path(name)
        values[str(path)] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    for path in (LAUNCHER, PRODUCER_MANIFEST, PRODUCER_EXIT, ROOT_RECEIPT, GATE_HELPER):
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
    verify_producer_closure()
    if OUTPUT.exists() or OBSERVER.exists():
        raise RuntimeError("Contracted audit output or observer root already exists")
    before = snapshot_pins()
    OBSERVER.mkdir(parents=False, exist_ok=False)

    specification = importlib.util.spec_from_file_location(
        "daily_audit_official_resource_gate", GATE_HELPER
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("Could not import official resource helper")
    gate_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    resources = gate_module.observation()
    write_json(
        OBSERVER / "resource_observation.json",
        {
            "utc": utc_now(),
            "resources": resources,
            "cpu_affinity": psutil.Process().cpu_affinity(),
            "thread_variables": {key: os.environ[key] for key in THREAD_ENV},
            "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
            "publication_commit": commit,
            "pins": before,
        },
    )
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
        "--producer-root",
        str(PRODUCER),
        "--producer-manifest-sha256",
        PRODUCER_MANIFEST_SHA256,
        "--producer-exit",
        str(PRODUCER_EXIT),
        "--producer-exit-sha256",
        PRODUCER_EXIT_SHA256,
        "--auditor-sha256",
        REPO_PINS["audit_weekly_daily_adaptation.py"],
        "--tests-sha256",
        REPO_PINS["test_audit_weekly_daily_adaptation.py"],
        "--output",
        str(OUTPUT),
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
    result = None
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
                    raise RuntimeError(f"Audit child affinity is not CPU[0]: {child_affinity}")
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
        write_json(
            OBSERVER / "failure_receipt.json",
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
                    "status": "AUDIT_LAUNCHER_FAILED_CLOSED",
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
