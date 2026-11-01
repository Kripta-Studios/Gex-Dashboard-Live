"""One-shot, resource-gated synthetic checks for CONTEXT182 adaptation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import psutil


PRODUCER_SHA256 = "d03494bf68e281bc7c9e68f385aa111567eac4206cf5b44133e17bb480ed5df8"
TEST_SHA256 = "2f44f17d459cd7cb43c5c3842fb4b2d72c689278f797426a75ac006f0d5db43f"
HELPER_SHA256 = "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"
MINIMUM = 2_000_000_000


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command(name: str, argv: list[str], evidence: Path, env: dict[str, str]) -> dict[str, object]:
    stdout, stderr = evidence / f"{name}_stdout.log", evidence / f"{name}_stderr.log"
    started = datetime.now(timezone.utc).isoformat()
    with stdout.open("xb") as out, stderr.open("xb") as err:
        result = subprocess.run(argv, cwd=Path(__file__).resolve().parents[4], env=env, stdout=out, stderr=err, check=False)
    return {
        "name": name, "command": argv, "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(), "exit_code": result.returncode,
        "stdout": {"bytes": stdout.stat().st_size, "sha256": sha(stdout)},
        "stderr": {"bytes": stderr.stat().st_size, "sha256": sha(stderr)},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args()
    evidence = Path(os.path.abspath(args.evidence_dir))
    if evidence.exists():
        raise RuntimeError("immutable evidence exists")
    week = Path(__file__).resolve().parents[1]
    repo = Path(__file__).resolve().parents[4]
    producer, tests = week / "evaluate_weekly_context_adaptation.py", week / "test_evaluate_weekly_context_adaptation.py"
    helper = repo / "research_papers/JEPA/level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py"
    if sha(producer) != PRODUCER_SHA256 or sha(tests) != TEST_SHA256 or sha(helper) != HELPER_SHA256:
        raise RuntimeError("source/helper snapshot mismatch")
    spec = importlib.util.spec_from_file_location("frozen_global_memory_helper", helper)
    if spec is None or spec.loader is None:
        raise RuntimeError("helper import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if sha(helper) != HELPER_SHA256:
        raise RuntimeError("helper changed during import")
    process = psutil.Process()
    process.cpu_affinity([0])
    observed = module.observation()
    module.gate(observed)
    evidence.mkdir(parents=True)
    for path in (producer, tests, helper, Path(__file__)):
        shutil.copy2(path, evidence / path.name)
    threads = {
        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1", "BLIS_NUM_THREADS": "1",
    }
    env = dict(os.environ)
    env.update(threads)
    write(evidence / "resource_gate.json", {
        "utc": datetime.now(timezone.utc).isoformat(), "cpu_affinity": process.cpu_affinity(),
        **observed, "minimum_each_bytes": MINIMUM, "threads": threads,
        "helper": {"path": str(helper), "bytes": helper.stat().st_size, "sha256": HELPER_SHA256},
        "source_snapshot": {producer.name: PRODUCER_SHA256, tests.name: TEST_SHA256, Path(__file__).name: sha(Path(__file__))},
        "real_data_or_outcomes_opened": False,
    })
    commands = [
        ("versions", [sys.executable, "-c", "import sklearn, numpy, pytest; print(sklearn.__version__, numpy.__version__, pytest.__version__)"]),
        ("compile", [sys.executable, "-m", "py_compile", str(producer), str(tests)]),
        ("ruff", [sys.executable, "-m", "ruff", "check", str(producer), str(tests)]),
        ("pytest", [sys.executable, "-m", "pytest", "-q", str(tests)]),
    ]
    receipts = [command(name, argv, evidence, env) for name, argv in commands]
    write(evidence / "commands.json", receipts)
    outputs = {path.name: {"bytes": path.stat().st_size, "sha256": sha(path)} for path in sorted(evidence.iterdir()) if path.is_file()}
    write(evidence / "manifest.json", {"schema": "weekly_context_adaptation_implementation_checks_v1", "outputs_before_manifest": outputs, "all_exit_zero": all(item["exit_code"] == 0 for item in receipts), "real_data_or_outcomes_opened": False})
    if sha(producer) != PRODUCER_SHA256 or sha(tests) != TEST_SHA256 or sha(helper) != HELPER_SHA256:
        raise RuntimeError("closing snapshot mismatch")
    return 0 if all(item["exit_code"] == 0 for item in receipts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
