$ErrorActionPreference = 'Stop'

$Python = 'C:\Program Files\Python314\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Pinned Python interpreter is absent: $Python"
}

$Runner = @'
import os
import sys

THREAD_ENV = {
    "ARROW_NUM_THREADS": "1", "BLIS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
    "POLARS_MAX_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
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
FAILURE_EXIT = BASE / "h2_daily_adaptation_audit_observer_01" / "exit.json"
FAILURE_RECEIPT = BASE / "h2_daily_adaptation_audit_observer_01" / "failure_receipt.json"
OUTPUT = BASE / "h2_daily_adaptation_audit_02"
OBSERVER = BASE / "h2_daily_adaptation_audit_observer_02"
BRANCH = "research/multiscale-v1r1-net-usd"

AUDITOR = WEEK / "audit_weekly_daily_adaptation_v2.py"
TESTS = WEEK / "test_audit_weekly_daily_adaptation_v2.py"
LAUNCHER = WEEK / "launch_daily_adaptation_audit_v2_20261102.ps1"
GATE_HELPER = LEVEL / "launch_monthly_test_index_v2_audit_20261024.py"

PRODUCER_MANIFEST_SHA256 = "7decb3e2baf360d807fd849604013728f5fe05c48dcd3302c0b270a1440d2206"
PRODUCER_EXIT_SHA256 = "54021b954d522e0c9535b237de45a63da14a39e91e12e71fe90546d351f9f0d0"
ROOT_RECEIPT_SHA256 = "2b59260b4019f7e04199a6353b58bdcb8fd995c671e23cb6485ab6fa67533a2d"
FAILURE_EXIT_SHA256 = "0f623e6c80b767ab86d2bcd8b2ecf3031bbdb56a63657ba9713d50b292bcbfa8"
FAILURE_RECEIPT_SHA256 = "cf060674a646f1d5fefe5087e80d1b4a287dce3366fb7ea5ef7967971fa879a4"
GATE_HELPER_SHA256 = "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"

REPO_PINS = {
    "audit_weekly_daily_adaptation_v2.py": "d8813052412dbff001bae192f0d3c680808c78da458f1de54674e4331ef625a9",
    "test_audit_weekly_daily_adaptation_v2.py": "6bc6d92dcbba460fa809527c41197c94a1d7409f85f2937a926efe08925d39d6",
    "DAILY_ADAPTATION_CONTRACT_20261101.md": "5d388e484435c8fe23d40476c02928887c6ab5487af62197e5e74f08c1fe0047",
    "DAILY_ADAPTATION_AUDIT_FAILURE_AND_V2_CONTRACT_20261102.md": "bfd90a0610ab0ef90a06b9a16da246a0e205139887ab51312141ba3866ddab90",
    "DAILY_ADAPTATION_AUDIT_V2_CONTRACT_REVIEW_20261102.md": "0c69a4c7486da02f8abcfcc533d354203a5f569aa4f085647a5b58e24482a4dc",
    "daily_adaptation_audit_failure_archive_01/archive_receipt.json": "13e1973842ce444a47fbfcc05759e573e94000e7174ed694b579d7ebded357f7",
    "audit_weekly_context_adaptation_v4.py": "0723696ae01dcc86af7c2af8e8fdc2e3b281ba913987a65d95bd4703c959aa9c",
    "audit_weekly_context_models.py": "3eb6b9795ad260971435259858f86d3c00111bcc141973faf986411d4a68ad99",
    "launch_daily_adaptation_audit_v2_checks_20261102.py": "265795a141781599f285224351a7d28eb69c6da8b33a3df9d19ae510eef54405",
    "DAILY_ADAPTATION_AUDITOR_V2_STATIC_REVIEW_20261102.md": "fc75d98a76dbbba7f7b10990cb3dc77ec2977246423fc1fc98ea771e0abdb446",
    "daily_adaptation_audit_v2_preparation_archive_01/receipt.json": "37824cce19d742bf5c13427ec5ac9f12ddcd25a22cc208fd29f7e803d4e9eafe",
    "daily_adaptation_audit_v2_preparation_archive_01/archive_receipt.json": "4daab7c1ee7cd26538b252a1cebda93106d6656c0d22687b067ac1c03556d701",
    "DAILY_ADAPTATION_AUDITOR_V2_FINAL_REVIEW_20261102.md": "507374a02b59b618c290c73ad28f86876d850992a321a78688d9fc796fb9733c",
    "DAILY_ADAPTATION_AUDIT_V2_RUNTIME_BINDING_20261102.md": "fb05be5ee70269546e8ab1c63f577806dace816ce5de566b4f8c2253727f3ce9",
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
    return subprocess.check_output(
        ["git", "show", f"{commit}:{path.relative_to(REPO).as_posix()}"], cwd=REPO
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
    if commit != remote:
        raise RuntimeError("Local HEAD is not the published remote HEAD")
    for name, expected in REPO_PINS.items():
        path = WEEK / Path(name)
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise RuntimeError(f"Repository pin mismatch: {name}")
        if git_bytes(commit, path) != path.read_bytes():
            raise RuntimeError(f"Published bytes differ: {name}")
    if not LAUNCHER.is_file() or LAUNCHER.is_symlink():
        raise RuntimeError("V2 launcher missing or linked")
    if git_bytes(commit, LAUNCHER) != LAUNCHER.read_bytes():
        raise RuntimeError("V2 launcher is not byte-exact at published HEAD")
    return commit


def verify_external():
    fixed = {
        PRODUCER_MANIFEST: PRODUCER_MANIFEST_SHA256,
        PRODUCER_EXIT: PRODUCER_EXIT_SHA256,
        ROOT_RECEIPT: ROOT_RECEIPT_SHA256,
        FAILURE_EXIT: FAILURE_EXIT_SHA256,
        FAILURE_RECEIPT: FAILURE_RECEIPT_SHA256,
        GATE_HELPER: GATE_HELPER_SHA256,
    }
    for path, expected in fixed.items():
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise RuntimeError(f"External pin mismatch: {path}")
    producer_exit = json.loads(PRODUCER_EXIT.read_text(encoding="utf-8"))
    if producer_exit.get("exit_code") != 0:
        raise RuntimeError("Producer did not close exit0")
    failed_exit = json.loads(FAILURE_EXIT.read_text(encoding="utf-8"))
    if failed_exit.get("exit_code") != 1 or failed_exit.get("audit_child_exit_code") != 1:
        raise RuntimeError("Auditor01 failure identity mismatch")
    if (BASE / "h2_daily_adaptation_audit_01").exists():
        raise RuntimeError("Auditor01 output must remain absent")


def snapshots():
    paths = [WEEK / Path(name) for name in REPO_PINS]
    paths += [LAUNCHER, PRODUCER_MANIFEST, PRODUCER_EXIT, ROOT_RECEIPT,
              FAILURE_EXIT, FAILURE_RECEIPT, GATE_HELPER]
    return {str(path): {"bytes": path.stat().st_size, "sha256": sha256(path)} for path in paths}


def changed(before):
    differences = []
    for name, expected in before.items():
        path = Path(name)
        actual = {"bytes": path.stat().st_size if path.is_file() else None,
                  "sha256": sha256(path) if path.is_file() else None}
        if actual != expected:
            differences.append({"path": name, "before": expected, "after": actual})
    return differences


def main():
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"Unexpected Python interpreter: {sys.executable}")
    psutil.Process().cpu_affinity([0])
    if psutil.Process().cpu_affinity() != [0]:
        raise RuntimeError("Parent affinity is not CPU[0]")
    commit = verify_publication()
    verify_external()
    if OUTPUT.exists() or OBSERVER.exists():
        raise RuntimeError("V2 output or observer root already exists")
    before = snapshots()
    OBSERVER.mkdir(parents=False, exist_ok=False)

    specification = importlib.util.spec_from_file_location("v2_resource_gate", GATE_HELPER)
    if specification is None or specification.loader is None:
        raise RuntimeError("Could not import official resource helper")
    gate_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    resources = gate_module.observation()
    write_json(OBSERVER / "resource_observation.json", {
        "utc": utc_now(), "resources": resources,
        "cpu_affinity": psutil.Process().cpu_affinity(),
        "thread_variables": {key: os.environ[key] for key in THREAD_ENV},
        "publication_commit": commit, "pins": before,
    })
    try:
        gate_module.gate(resources)
    except Exception as error:
        write_json(OBSERVER / "failure_receipt.json", {
            "status": "RESOURCE_GATE_REJECTED_BEFORE_AUDIT_V2_CHILD",
            "utc": utc_now(), "error": f"{type(error).__name__}: {error}",
            "child_created": False, "retry": False,
        })
        raise

    args = [str(PYTHON), "-X", "utf8", "-u", str(AUDITOR),
            "--execute-reviewed-audit", "--producer-root", str(PRODUCER),
            "--producer-manifest-sha256", PRODUCER_MANIFEST_SHA256,
            "--producer-exit", str(PRODUCER_EXIT),
            "--producer-exit-sha256", PRODUCER_EXIT_SHA256,
            "--auditor-sha256", REPO_PINS["audit_weekly_daily_adaptation_v2.py"],
            "--tests-sha256", REPO_PINS["test_audit_weekly_daily_adaptation_v2.py"],
            "--output", str(OUTPUT)]
    write_json(OBSERVER / "admission.json", {
        "utc": utc_now(), "command": args, "publication_commit": commit,
        "resources": resources, "cpu_affinity": psutil.Process().cpu_affinity(),
        "thread_variables": {key: os.environ[key] for key in THREAD_ENV},
        "pins": before, "output": str(OUTPUT), "observer": str(OBSERVER),
    })

    process = None; metadata_error = None; creation_time = None
    child_affinity = None; result = None; started = time.monotonic(); started_utc = utc_now()
    with (OBSERVER / "stdout.log").open("wb") as stdout, (OBSERVER / "stderr.log").open("wb") as stderr:
        process = subprocess.Popen(args, cwd=str(WEEK), env=os.environ.copy(),
            stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            try:
                child = psutil.Process(process.pid)
                creation_time = child.create_time(); child_affinity = child.cpu_affinity()
                if child_affinity != [0]:
                    raise RuntimeError(f"V2 child affinity is not CPU[0]: {child_affinity}")
            except Exception as error:
                metadata_error = f"{type(error).__name__}: {error}"
            try:
                write_json(OBSERVER / "process.json", {
                    "pid": process.pid, "creation_time": creation_time,
                    "utc": started_utc, "command": args,
                    "cpu_affinity": child_affinity, "metadata_error": metadata_error,
                    "handle_retained": True, "wait_pending": True,
                })
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else f"{metadata_error}; {detail}"
        finally:
            result = process.wait()

    differences = changed(before); effective = result
    if metadata_error is not None and effective == 0: effective = 3
    if differences and effective == 0: effective = 4
    files = {}
    for name in ("resource_observation.json", "admission.json", "process.json", "stdout.log", "stderr.log"):
        path = OBSERVER / name
        if path.is_file(): files[str(path)] = sha256(path)
    write_json(OBSERVER / "exit.json", {
        "exit_code": effective, "audit_v2_child_exit_code": result,
        "utc": utc_now(), "source": "subprocess.Popen.wait_retained_handle",
        "elapsed_seconds": time.monotonic() - started, "pid": process.pid,
        "creation_time": creation_time, "cpu_affinity": child_affinity,
        "metadata_error": metadata_error, "changed_pins": differences,
        "files": files, "retry": False,
    })
    if effective != 0:
        write_json(OBSERVER / "failure_receipt.json", {
            "status": "AUDIT_V2_CHILD_OR_CLOSURE_FAILED", "utc": utc_now(),
            "exit_code": effective, "audit_v2_child_exit_code": result,
            "metadata_error": metadata_error, "changed_pins": differences,
            "retry": False, "partial_output_not_authorized_for_adoption": True,
        })
    print(json.dumps({"pid": process.pid, "exit_code": effective,
        "observer": str(OBSERVER), "output": str(OUTPUT)}, sort_keys=True))
    return int(effective)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        if OBSERVER.is_dir() and not (OBSERVER / "failure_receipt.json").exists():
            write_json(OBSERVER / "failure_receipt.json", {
                "status": "AUDIT_V2_LAUNCHER_FAILED_CLOSED", "utc": utc_now(),
                "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(), "retry": False,
            })
        raise
'@

& $Python -X utf8 -u -c $Runner
exit $LASTEXITCODE
