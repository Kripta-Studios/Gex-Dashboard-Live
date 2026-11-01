"""One-shot synthetic check launcher for the independent H2 auditor."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import psutil


AUDITOR_SHA256 = "d87678f661f8fbb369b2bd595b0cbefeb69b0782a63393c3aa64a84acc631ed0"
TEST_SHA256 = "1a8162be504d87b81b4e424fd9a9cf84b81d97fe9474a6fa6f27f27b6833d38b"
MIN_AVAILABLE = 2_000_000_000


class PerformanceInformation(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("CommitTotal", ctypes.c_size_t),
        ("CommitLimit", ctypes.c_size_t),
        ("CommitPeak", ctypes.c_size_t),
        ("PhysicalTotal", ctypes.c_size_t),
        ("PhysicalAvailable", ctypes.c_size_t),
        ("SystemCache", ctypes.c_size_t),
        ("KernelTotal", ctypes.c_size_t),
        ("KernelPaged", ctypes.c_size_t),
        ("KernelNonpaged", ctypes.c_size_t),
        ("PageSize", ctypes.c_size_t),
        ("HandleCount", wintypes.DWORD),
        ("ProcessCount", wintypes.DWORD),
        ("ThreadCount", wintypes.DWORD),
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def commit_free_bytes() -> int:
    info = PerformanceInformation()
    info.cb = ctypes.sizeof(info)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb):
        raise OSError(ctypes.get_last_error(), "GetPerformanceInfo failed")
    return int((info.CommitLimit - info.CommitTotal) * info.PageSize)


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def run_command(
    name: str, command: list[str], evidence: Path, env: dict[str, str]
) -> dict:
    stdout_path = evidence / f"{name}_stdout.log"
    stderr_path = evidence / f"{name}_stderr.log"
    started = datetime.now(timezone.utc).isoformat()
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        completed = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[3],
            env=env,
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    return {
        "name": name,
        "command": command,
        "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "exit_code": completed.returncode,
        "stdout": {
            "bytes": stdout_path.stat().st_size,
            "sha256": sha256_file(stdout_path),
        },
        "stderr": {
            "bytes": stderr_path.stat().st_size,
            "sha256": sha256_file(stderr_path),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args()
    evidence = Path(os.path.abspath(args.evidence_dir))
    if evidence.exists():
        raise RuntimeError("evidence directory already exists")
    source_dir = Path(__file__).resolve().parent
    auditor = source_dir / "audit_weekly_h2_ev_v2_independent.py"
    tests = source_dir / "test_audit_weekly_h2_ev_v2_independent.py"
    if sha256_file(auditor) != AUDITOR_SHA256 or sha256_file(tests) != TEST_SHA256:
        raise RuntimeError("pretest source snapshot mismatch")
    process = psutil.Process()
    process.cpu_affinity([0])
    available_ram = psutil.virtual_memory().available
    free_commit = commit_free_bytes()
    if available_ram < MIN_AVAILABLE or free_commit < MIN_AVAILABLE:
        raise RuntimeError("resource gate failed")
    evidence.mkdir(parents=True)
    shutil.copy2(auditor, evidence / auditor.name)
    shutil.copy2(tests, evidence / tests.name)
    shutil.copy2(Path(__file__), evidence / Path(__file__).name)
    threads = {
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
    env = dict(os.environ)
    env.update(threads)
    gate = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "cpu_affinity": process.cpu_affinity(),
        "available_ram_bytes": available_ram,
        "free_commit_bytes": free_commit,
        "minimum_each_bytes": MIN_AVAILABLE,
        "threads": threads,
        "source_snapshot": {
            auditor.name: AUDITOR_SHA256,
            tests.name: TEST_SHA256,
            Path(__file__).name: sha256_file(Path(__file__)),
        },
        "market_data_accessed": False,
    }
    write_json(evidence / "resource_gate.json", gate)
    commands = [
        (
            "compile",
            [sys.executable, "-m", "py_compile", str(auditor), str(tests)],
        ),
        (
            "ruff",
            [sys.executable, "-m", "ruff", "check", str(auditor), str(tests)],
        ),
        (
            "pytest",
            [sys.executable, "-m", "pytest", "-q", str(tests)],
        ),
    ]
    receipts = [run_command(name, command, evidence, env) for name, command in commands]
    write_json(evidence / "commands.json", receipts)
    outputs = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(evidence.iterdir())
        if path.is_file()
    }
    write_json(
        evidence / "manifest.json",
        {
            "schema": "weekly_h2_independent_auditor_checks_v1",
            "outputs_before_manifest": outputs,
            "all_exit_zero": all(item["exit_code"] == 0 for item in receipts),
            "real_dataset_or_evaluation_opened": False,
        },
    )
    return 0 if all(item["exit_code"] == 0 for item in receipts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
