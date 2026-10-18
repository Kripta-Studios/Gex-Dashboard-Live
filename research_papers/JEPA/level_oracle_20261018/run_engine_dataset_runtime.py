"""Scheduling-only continuation of the frozen four-worker dataset driver.

The historical dataset contract and engine remain byte-identical. This wrapper
records the actual worker override separately and binds it into final completion.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import shutil
import sys

import psutil

import run_engine_dataset as original


def pool_factory(workers):
    def create(*, max_workers, initializer):
        if max_workers != 4:
            raise ValueError("Only the historical four-worker contract is supported")
        return ProcessPoolExecutor(max_workers=workers, initializer=initializer)

    return create


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", type=Path, default=original.CACHE_ROOT)
    parser.add_argument("--output", type=Path, default=original.OUTPUT_ROOT)
    parser.add_argument("--workers", type=int, choices=(4, 8), default=4)
    args = parser.parse_args()
    if args.workers == 8 and not (args.cache_root / "full_summary.json").exists():
        raise RuntimeError(
            "Wait for the cache producer to finish before adding workers"
        )
    free_memory = psutil.virtual_memory().available
    if free_memory < 3 * 1024**3:
        raise RuntimeError("Less than 3 GiB available RAM before continuation")
    root = args.output
    contract_path = root / "dataset_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract["workers"] != 4:
        raise ValueError("Unexpected historical contract worker count")
    if original.engine.file_sha(original.__file__) != contract["runner_sha256"]:
        raise ValueError("Historical driver changed")
    if original.engine.file_sha(original.engine.__file__) != contract["engine_sha256"]:
        raise ValueError("Frozen engine changed")
    if (root / "completion.json").exists():
        raise ValueError("Completed datasets cannot be continued")
    runtime_root = root / "runtime_02"
    runtime_root.mkdir(exist_ok=False)
    for name in ("index.parquet", "index.csv", "progress.json"):
        shutil.copy2(root / name, runtime_root / ("prior_" + name))
    shutil.copy2(__file__, runtime_root / Path(__file__).name)
    execution = {
        "kind": "SCHEDULING_ONLY_CONTINUATION",
        "started_utc": original.utc_now(),
        "historical_contract_sha256": original.engine.file_sha(contract_path),
        "historical_runner_sha256": contract["runner_sha256"],
        "runtime_wrapper_sha256": original.engine.file_sha(__file__),
        "engine_sha256": contract["engine_sha256"],
        "historical_workers": 4,
        "actual_workers": args.workers,
        "bounded_inflight": 8,
        "native_threads_per_worker": 1,
        "available_ram_before_bytes": free_memory,
        "cache_full_summary_sha256": (
            original.engine.file_sha(args.cache_root / "full_summary.json")
            if (args.cache_root / "full_summary.json").exists()
            else None
        ),
        "economic_or_feature_change": False,
        "existing_complete_days": "Verified by unchanged original resume function",
    }
    execution_path = runtime_root / "runtime_execution.json"
    original.atomic_json(execution_path, execution)
    execution_hash = original.engine.file_sha(execution_path)
    original.ProcessPoolExecutor = pool_factory(args.workers)
    old_final_summary = original.final_summary

    def final_summary(*summary_args):
        result = old_final_summary(*summary_args)
        completion_path = root / "completion.json"
        completion = json.loads(completion_path.read_text(encoding="utf-8"))
        completion.update(
            {
                "runtime_execution_path": str(execution_path.resolve()),
                "runtime_execution_sha256": execution_hash,
                "actual_workers": args.workers,
                "historical_contract_workers": 4,
            }
        )
        original.atomic_json(completion_path, completion)
        original.atomic_json(
            runtime_root / "runtime_completion.json",
            {
                "status": result["status"],
                "finished_utc": original.utc_now(),
                "runtime_execution_sha256": execution_hash,
                "completion_sha256": original.engine.file_sha(completion_path),
            },
        )
        return result

    original.final_summary = final_summary
    sys.argv = [
        original.__file__,
        "--cache-root",
        str(args.cache_root),
        "--output",
        str(root),
        "--workers",
        "4",
    ]
    original.main()


if __name__ == "__main__":
    main()
