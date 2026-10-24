"""Recorded synthetic wrapper checks only; no economic runtime entry point."""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psutil

BASE = Path("D:/GexResearchArtifacts/level_oracle_20261018")
REPO = Path("C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live")
HERE = REPO / "research_papers/JEPA/level_oracle_20261018"
FILES = ("run_oof_calibrated_pipeline_v2.py", "test_run_oof_calibrated_pipeline_v2.py",
         "OOF_TRANSITIVE_SOURCE_V2_IMPLEMENTATION_CONTRACT_20261024.md",
         "OOF_TRANSITIVE_SOURCE_V2_DESIGN_20261024.md", "OOF_TRANSITIVE_SOURCE_FAILURE_DIAGNOSIS_20261024.md")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False)
        f.write("\n")


class Memory(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
        (name, ctypes.c_ulonglong) for name in (
            "total_phys", "avail_phys", "total_page", "avail_page", "total_virtual",
            "avail_virtual", "avail_extended")]


def resources():
    info = Memory()
    info.length = ctypes.sizeof(info)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info)):
        raise RuntimeError("Memory API failed")
    return dict(available_ram_bytes=info.avail_phys, free_commit_bytes=info.avail_page)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--attempt", required=True)
    p.add_argument("--only", default=None)
    args = p.parse_args()
    out = BASE / args.attempt
    if out.parent != BASE or out.exists():
        raise ValueError("New direct-child attempt required")
    out.mkdir()
    pins = {name: sha(HERE / name) for name in FILES}
    (out / "source_snapshot").mkdir()
    for name, digest in pins.items():
        shutil.copyfile(HERE / name, out / "source_snapshot" / name)
        if sha(out / "source_snapshot" / name) != digest:
            raise RuntimeError("Source snapshot changed")
    originals = json.loads((BASE / "oof_pipeline_runtime_20261024_01/request.json").read_text())["code"]
    if not all(sha(HERE / name) == digest for name, digest in originals.items()):
        raise RuntimeError("Original dependency changed")
    free = resources()
    if min(free.values()) < 2_000_000_000:
        write(out / "blocked.json", dict(status="BLOCKED_RESOURCES", resources=free, pins=pins))
        return 1
    affinity = [min(psutil.Process().cpu_affinity())]
    psutil.Process().cpu_affinity(affinity)
    env = dict(os.environ)
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[name] = "1"
    commands = [
        [sys.executable, "-m", "ruff", "check", *FILES[:2]],
        [sys.executable, "-m", "pytest", FILES[1], "-q", "--basetemp", str(out / "pytest_tmp")],
    ]
    if args.only:
        commands[1].extend(["-k", args.only])
    write(out / "admission.json", dict(scope="SYNTHETIC_ONLY", utc=datetime.now(timezone.utc).isoformat(),
          publication_commit="4b2ab2a1931684f7127ad0728498d4ac60157e81", pins=pins,
          original_dependencies=originals, commands=commands, resources=free, cpu_affinity=affinity,
          threads=1, runtime_market_authorized=False, launcher_sha256=sha(__file__)))
    steps = []
    for i, command in enumerate(commands):
        began = time.monotonic()
        with (out / f"step_{i}_stdout.txt").open("xb") as stdout, (out / f"step_{i}_stderr.txt").open("xb") as stderr:
            child = subprocess.Popen(command, cwd=HERE, env=env, stdin=subprocess.DEVNULL,
                                     stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
            write(out / f"step_{i}_process.json", dict(pid=child.pid, command=command,
                  creation_time=psutil.Process(child.pid).create_time()))
            code = child.wait()
        steps.append(dict(command=command, exit_code=code, wall_seconds=time.monotonic()-began,
                          stdout_sha256=sha(out / f"step_{i}_stdout.txt"),
                          stderr_sha256=sha(out / f"step_{i}_stderr.txt")))
        if code:
            break
    unchanged = all(sha(HERE / n) == h for n, h in pins.items())
    old_unchanged = all(sha(HERE / n) == h for n, h in originals.items())
    result = dict(status="PASS" if all(s["exit_code"] == 0 for s in steps) and len(steps) == 2
                  and unchanged and old_unchanged else "FAILED_PRESERVED", steps=steps,
                  pins_unchanged=unchanged, original_dependencies_unchanged=old_unchanged,
                  runtime_market_authorized=False)
    write(out / "result.json", result)
    print(json.dumps(result), flush=True)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
