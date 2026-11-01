"""Frozen one-shot synthetic check launcher for the Q3 partial scorer."""

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


SCORER_SHA256 = "fcc1a41b4716d5562987d5c8bcab88d5420abb3739d92688eea3caf70f0aaa97"
TEST_SHA256 = "ec622c1ea8a6a4f12b397ea7ebc6bfaf902a9d2ab7d71c055541ea6bb852eb6f"
MINIMUM = 2_000_000_000


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


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def commit_free() -> int:
    info = PerformanceInformation()
    info.cb = ctypes.sizeof(info)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb):
        raise OSError(ctypes.get_last_error())
    return int((info.CommitLimit - info.CommitTotal) * info.PageSize)


def write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def command(name: str, argv: list[str], evidence: Path, env: dict[str, str]) -> dict:
    stdout = evidence / f"{name}_stdout.log"
    stderr = evidence / f"{name}_stderr.log"
    started = datetime.now(timezone.utc).isoformat()
    with stdout.open("wb") as out, stderr.open("wb") as err:
        result = subprocess.run(
            argv,
            cwd=Path(__file__).resolve().parents[3],
            env=env,
            stdout=out,
            stderr=err,
            check=False,
        )
    return {
        "name": name,
        "command": argv,
        "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "exit_code": result.returncode,
        "stdout": {"bytes": stdout.stat().st_size, "sha256": sha(stdout)},
        "stderr": {"bytes": stderr.stat().st_size, "sha256": sha(stderr)},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args()
    evidence = Path(os.path.abspath(args.evidence_dir))
    if evidence.exists():
        raise RuntimeError("evidence exists")
    root = Path(__file__).resolve().parent
    scorer = root / "score_weekly_h2_q3_partial_frozen.py"
    tests = root / "test_score_weekly_h2_q3_partial_frozen.py"
    if sha(scorer) != SCORER_SHA256 or sha(tests) != TEST_SHA256:
        raise RuntimeError("source snapshot mismatch")
    process = psutil.Process()
    process.cpu_affinity([0])
    ram = psutil.virtual_memory().available
    commit = commit_free()
    if min(ram, commit) < MINIMUM:
        raise RuntimeError("resource gate")
    evidence.mkdir(parents=True)
    shutil.copy2(scorer, evidence / scorer.name)
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
    write(
        evidence / "resource_gate.json",
        {
            "utc": datetime.now(timezone.utc).isoformat(),
            "cpu_affinity": process.cpu_affinity(),
            "available_ram_bytes": ram,
            "free_commit_bytes": commit,
            "minimum_each_bytes": MINIMUM,
            "threads": threads,
            "source_snapshot": {
                scorer.name: SCORER_SHA256,
                tests.name: TEST_SHA256,
                Path(__file__).name: sha(Path(__file__)),
            },
            "real_q3_dataset_or_outcomes_opened": False,
        },
    )
    commands = [
        ("compile", [sys.executable, "-m", "py_compile", str(scorer), str(tests)]),
        ("ruff", [sys.executable, "-m", "ruff", "check", str(scorer), str(tests)]),
        ("pytest", [sys.executable, "-m", "pytest", "-q", str(tests)]),
    ]
    receipts = [command(name, argv, evidence, env) for name, argv in commands]
    write(evidence / "commands.json", receipts)
    outputs = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(evidence.iterdir())
        if path.is_file()
    }
    write(
        evidence / "manifest.json",
        {
            "schema": "weekly_h2_q3_partial_frozen_scorer_checks_v1",
            "outputs_before_manifest": outputs,
            "all_exit_zero": all(item["exit_code"] == 0 for item in receipts),
            "real_q3_dataset_or_outcomes_opened": False,
        },
    )
    return 0 if all(item["exit_code"] == 0 for item in receipts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
