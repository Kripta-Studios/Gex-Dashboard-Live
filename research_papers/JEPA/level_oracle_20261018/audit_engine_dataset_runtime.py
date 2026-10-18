"""Scheduling-only eight-worker launcher for the frozen full oracle auditor."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

for variable in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "ARROW_IO_THREADS",
):
    os.environ[variable] = "1"

import audit_engine_dataset as runner  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    if "--output" not in sys.argv:
        raise ValueError("--output is required")
    output = Path(sys.argv[sys.argv.index("--output") + 1])
    original_parse = runner.argparse.ArgumentParser.parse_args

    def parse_with_runtime_workers(parser, *args, **kwargs):
        parsed = original_parse(parser, *args, **kwargs)
        if parsed.workers != 4:
            raise ValueError("Runtime launcher requires the frozen --workers 4 interface")
        parsed.workers = 8
        return parsed

    runner.argparse.ArgumentParser.parse_args = parse_with_runtime_workers
    identity = {
        "status": "STARTED",
        "started_at_utc": now(),
        "actual_workers": 8,
        "threads_per_worker": 1,
        "scientific_core_changed": False,
        "audit_engine_sha256": digest(Path(__file__).with_name("audit_engine.py")),
        "audit_runner_sha256": digest(Path(__file__).with_name("audit_engine_dataset.py")),
        "runtime_wrapper_sha256": digest(__file__),
    }
    runtime_path = output / "runtime_workers8.json"
    if runtime_path.exists():
        raise FileExistsError(runtime_path)
    runtime_path.write_text(json.dumps(identity, indent=2), encoding="utf-8")
    try:
        runner.main()
    except BaseException:
        (output / "runtime_workers8_failure.json").write_text(
            json.dumps({**identity, "status": "FAILED", "finished_at_utc": now(),
                        "traceback": traceback.format_exc()}, indent=2), encoding="utf-8"
        )
        raise
    (output / "runtime_workers8_completion.json").write_text(
        json.dumps({**identity, "status": "COMPLETE", "finished_at_utc": now()}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
