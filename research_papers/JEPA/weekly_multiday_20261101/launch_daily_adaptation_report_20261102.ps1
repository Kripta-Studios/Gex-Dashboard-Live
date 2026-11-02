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
PRODUCER = BASE / "h2_daily_adaptation_01"
PRODUCER_MANIFEST = PRODUCER / "manifest.json"
PRODUCER_EXIT = BASE / "h2_daily_adaptation_observer_01" / "exit.json"
ROOT_RECEIPT = BASE / "h2_daily_adaptation_closure_01" / "root_metadata_receipt.json"
AUDIT_JSON = BASE / "h2_daily_adaptation_audit_02" / "audit.json"
AUDIT_MANIFEST = BASE / "h2_daily_adaptation_audit_02" / "manifest.json"
AUDIT_EXIT = BASE / "h2_daily_adaptation_audit_observer_02" / "exit.json"
OUTPUT = BASE / "h2_daily_adaptation_report_01"
OBSERVER = BASE / "h2_daily_adaptation_report_observer_01"
BRANCH = "research/multiscale-v1r1-net-usd"

REPORTER = WEEK / "render_weekly_daily_adaptation_result.py"
BINDING = WEEK / "DAILY_ADAPTATION_REPORT_RUNTIME_BINDING_20261102.md"
LAUNCHER = WEEK / "launch_daily_adaptation_report_20261102.ps1"
FORMAL_RECEIPT = BASE / "daily_adaptation_renderer_preparation_01" / "attempt01" / "receipt.json"
GATE_HELPER = LEVEL / "launch_monthly_test_index_v2_audit_20261024.py"

PRODUCER_MANIFEST_SHA256 = "7decb3e2baf360d807fd849604013728f5fe05c48dcd3302c0b270a1440d2206"
PRODUCER_EXIT_SHA256 = "54021b954d522e0c9535b237de45a63da14a39e91e12e71fe90546d351f9f0d0"
ROOT_RECEIPT_SHA256 = "2b59260b4019f7e04199a6353b58bdcb8fd995c671e23cb6485ab6fa67533a2d"
AUDIT_SHA256 = "383edce65b16b316dcf71f2197a716d71501495f704040e858cea9354511b2b9"
AUDIT_MANIFEST_SHA256 = "ddda352f21b7b94b35db2a79c750048dd691c337672fbb3e31b35c3b9c4497d0"
AUDIT_EXIT_SHA256 = "6c9e236906de004c9da015021424e690b1dc8d1ed06514533fdcbfc4c3a524e8"
FORMAL_RECEIPT_SHA256 = "bef04941a5590ca374b6c87730be8509c295bfa58d444a6bf094937ae1aed2ef"
GATE_HELPER_SHA256 = "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"
BINDING_SHA256 = "1468906443c6e7dea91a2b40ff7bebae8ab0e059ea64200926f0d2b6312bfd2a"

REPO_PINS = {
    "render_weekly_daily_adaptation_result.py": "d0672f7d4723fa96f7df4745a0f7e922833e22b0b17deae2528c15b09fed3698",
    "DAILY_ADAPTATION_RENDERER_STATIC_REVIEW_20261101.md": "0735773e90f04ccf8c045b8c079daf264389c039a1e43503d92328befbfae921",
    "DAILY_ADAPTATION_CONTRACT_20261101.md": "5d388e484435c8fe23d40476c02928887c6ab5487af62197e5e74f08c1fe0047",
    "daily_adaptation_renderer_checks_archive_01/archive_receipt.json": "51fff001da361aa956aa9d4bdb2c2c50d19400fc113599ff00839417b30387cc",
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


def require_concrete_hash(value, label):
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise RuntimeError(f"Pending or invalid {label}; finalize and publish the binding first")


def verify_publication():
    for value, label in (
        (AUDIT_SHA256, "audit SHA256"),
        (AUDIT_EXIT_SHA256, "audit exit SHA256"),
        (BINDING_SHA256, "binding SHA256"),
    ):
        require_concrete_hash(value, label)
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
    pins = {WEEK / name: expected for name, expected in REPO_PINS.items()}
    pins[BINDING] = BINDING_SHA256
    for path, expected in pins.items():
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise RuntimeError(f"Repository pin mismatch: {path}")
        if git_bytes(commit, path) != path.read_bytes():
            raise RuntimeError(f"Published bytes differ: {path}")
    if not LAUNCHER.is_file() or LAUNCHER.is_symlink():
        raise RuntimeError("Report launcher missing or linked")
    if git_bytes(commit, LAUNCHER) != LAUNCHER.read_bytes():
        raise RuntimeError("Report launcher is not byte-exact at published HEAD")
    return commit


def verify_upstream_closure():
    fixed = {
        PRODUCER_MANIFEST: PRODUCER_MANIFEST_SHA256,
        PRODUCER_EXIT: PRODUCER_EXIT_SHA256,
        ROOT_RECEIPT: ROOT_RECEIPT_SHA256,
        AUDIT_JSON: AUDIT_SHA256,
        AUDIT_MANIFEST: AUDIT_MANIFEST_SHA256,
        AUDIT_EXIT: AUDIT_EXIT_SHA256,
        FORMAL_RECEIPT: FORMAL_RECEIPT_SHA256,
        GATE_HELPER: GATE_HELPER_SHA256,
    }
    for path, expected in fixed.items():
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise RuntimeError(f"Upstream/authority pin mismatch: {path}")
    producer_exit = json.loads(PRODUCER_EXIT.read_text(encoding="utf-8"))
    if not (
        producer_exit.get("exit_code") == 0
        and producer_exit.get("scientific_child_exit_code") == 0
        and producer_exit.get("metadata_error") is None
        and producer_exit.get("changed_pins") == []
        and producer_exit.get("cpu_affinity") == [0]
    ):
        raise RuntimeError("Producer retained exit metadata mismatch")
    audit_exit = json.loads(AUDIT_EXIT.read_text(encoding="utf-8"))
    if not (
        audit_exit.get("exit_code") == 0
        and audit_exit.get("audit_v2_child_exit_code") == 0
        and audit_exit.get("metadata_error") is None
        and audit_exit.get("changed_pins") == []
        and audit_exit.get("cpu_affinity") == [0]
    ):
        raise RuntimeError("Audit V2 retained exit metadata mismatch")
    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    if audit.get("status") != "PASS_INDEPENDENT_DAILY_ADAPTATION_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT":
        raise RuntimeError("Audit V2 does not carry the contracted PASS status")
    audit_manifest = json.loads(AUDIT_MANIFEST.read_text(encoding="utf-8"))
    if not (
        audit_manifest.get("schema") == "weekly_daily_adaptation_audit_manifest_v1"
        and audit_manifest.get("status") == "PASS_INDEPENDENT_DAILY_ADAPTATION_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT"
        and audit_manifest.get("audit.json") == {"bytes": 2983, "sha256": AUDIT_SHA256}
    ):
        raise RuntimeError("Audit V2 manifest metadata mismatch")
    receipt = json.loads(FORMAL_RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("status") != "PASS_DAILY_ADAPTATION_RENDERER_TECHNICAL_CHECKS":
        raise RuntimeError("Renderer formal receipt status mismatch")


def snapshot_pins():
    paths = [
        *(WEEK / name for name in REPO_PINS), BINDING, LAUNCHER,
        PRODUCER_MANIFEST, PRODUCER_EXIT, ROOT_RECEIPT, AUDIT_JSON, AUDIT_MANIFEST, AUDIT_EXIT,
        FORMAL_RECEIPT, GATE_HELPER,
    ]
    return {
        str(path): {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in paths
    }


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
    verify_upstream_closure()
    if OUTPUT.exists() or OBSERVER.exists():
        raise RuntimeError("Contracted report output or observer root already exists")
    before = snapshot_pins()
    OBSERVER.mkdir(parents=False, exist_ok=False)

    specification = importlib.util.spec_from_file_location(
        "daily_report_official_resource_gate", GATE_HELPER
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("Could not import official resource helper")
    gate_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    resources = gate_module.observation()
    write_json(OBSERVER / "resource_observation.json", {
        "utc": utc_now(), "resources": resources,
        "cpu_affinity": psutil.Process().cpu_affinity(),
        "thread_variables": {key: os.environ[key] for key in THREAD_ENV},
        "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
        "publication_commit": commit, "pins": before,
    })
    try:
        gate_module.gate(resources)
    except Exception as error:
        write_json(OBSERVER / "failure_receipt.json", {
            "status": "RESOURCE_GATE_REJECTED_BEFORE_REPORT_CHILD",
            "utc": utc_now(), "error": f"{type(error).__name__}: {error}",
            "resources": resources, "child_created": False, "retry": False,
        })
        raise

    args = [
        str(PYTHON), "-X", "utf8", "-u", str(REPORTER),
        "--execute-reviewed-report",
        "--producer-root", str(PRODUCER),
        "--producer-manifest-sha256", PRODUCER_MANIFEST_SHA256,
        "--audit-json", str(AUDIT_JSON),
        "--audit-sha256", AUDIT_SHA256,
        "--audit-exit-json", str(AUDIT_EXIT),
        "--audit-exit-sha256", AUDIT_EXIT_SHA256,
        "--reporter-sha256", REPO_PINS["render_weekly_daily_adaptation_result.py"],
        "--output", str(OUTPUT),
    ]
    write_json(OBSERVER / "admission.json", {
        "utc": utc_now(), "command": args, "publication_commit": commit,
        "resources": resources, "cpu_affinity": psutil.Process().cpu_affinity(),
        "thread_variables": {key: os.environ[key] for key in THREAD_ENV},
        "pins": before, "output": str(OUTPUT), "observer": str(OBSERVER),
    })

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
            args, cwd=str(WEEK), env=os.environ.copy(), stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            try:
                child = psutil.Process(process.pid)
                creation_time = child.create_time()
                child_affinity = child.cpu_affinity()
                if child_affinity != [0]:
                    raise RuntimeError(f"Report child affinity is not CPU[0]: {child_affinity}")
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

    changed = verify_closing(before)
    effective_result = result
    if metadata_error is not None and effective_result == 0:
        effective_result = 3
    if changed and effective_result == 0:
        effective_result = 4
    observed_files = {}
    for name in ("resource_observation.json", "admission.json", "process.json", "stdout.log", "stderr.log"):
        path = OBSERVER / name
        if path.is_file():
            observed_files[str(path)] = sha256(path)
    write_json(OBSERVER / "exit.json", {
        "exit_code": effective_result, "report_child_exit_code": result,
        "utc": utc_now(), "source": "subprocess.Popen.wait_retained_handle",
        "elapsed_seconds": time.monotonic() - started, "pid": process.pid,
        "creation_time": creation_time, "cpu_affinity": child_affinity,
        "metadata_error": metadata_error, "changed_pins": changed,
        "files": observed_files, "retry": False,
    })
    if effective_result != 0:
        write_json(OBSERVER / "failure_receipt.json", {
            "status": "REPORT_CHILD_OR_CLOSURE_FAILED", "utc": utc_now(),
            "exit_code": effective_result, "report_child_exit_code": result,
            "metadata_error": metadata_error, "changed_pins": changed,
            "retry": False, "partial_output_not_authorized_for_adoption": True,
        })
    print(json.dumps({
        "pid": process.pid, "exit_code": effective_result,
        "observer": str(OBSERVER), "output": str(OUTPUT),
    }, sort_keys=True))
    return int(effective_result)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        if OBSERVER.is_dir() and not (OBSERVER / "failure_receipt.json").exists():
            write_json(OBSERVER / "failure_receipt.json", {
                "status": "REPORT_LAUNCHER_FAILED_CLOSED", "utc": utc_now(),
                "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(), "retry": False,
            })
        raise
'@

& $Python -X utf8 -u -c $Runner
exit $LASTEXITCODE
