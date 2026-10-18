"""Resource-aware launcher/recorder; never selects models or changes fit settings."""

from __future__ import annotations

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
import threading
import time

import psutil


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def write(path, value):
    temporary = path.with_suffix(".temporary")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def resources():
    memory = psutil.virtual_memory()

    class PerformanceInformation(ctypes.Structure):
        _fields_ = (
            [("cb", ctypes.c_ulong)]
            + [
                (name, ctypes.c_size_t)
                for name in (
                    "CommitTotal",
                    "CommitLimit",
                    "CommitPeak",
                    "PhysicalTotal",
                    "PhysicalAvailable",
                    "SystemCache",
                    "KernelTotal",
                    "KernelPaged",
                    "KernelNonpaged",
                    "PageSize",
                )
            ]
            + [
                (name, ctypes.c_ulong)
                for name in ("HandleCount", "ProcessCount", "ThreadCount")
            ]
        )

    performance = PerformanceInformation()
    performance.cb = ctypes.sizeof(performance)
    if not ctypes.windll.psapi.GetPerformanceInfo(
        ctypes.byref(performance), performance.cb
    ):
        raise ctypes.WinError()
    commit_free = (
        performance.CommitLimit - performance.CommitTotal
    ) * performance.PageSize
    gpu = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return {
        "available_ram_bytes": memory.available,
        "available_commit_bytes": commit_free,
        "gpu_free_mib": int(gpu.stdout.strip().splitlines()[0]),
    }


def prerequisite_status(args):
    audit_path = args.oracle_audit
    if not audit_path.exists():
        return "WAIT_FULL_AUDIT_FILE"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("status") != "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT":
        raise ValueError(
            "Explicit audit failed or is not a FULL PASS; no alternate root is selected"
        )
    if Path(audit["binding"]["engine_root"]).resolve() != args.oracle_root.resolve():
        raise ValueError("Explicit audit belongs to another engine root")
    completion = args.oracle_root / "completion.json"
    if not completion.exists():
        return "WAIT_ENGINE_COMPLETION"
    if digest(completion) != audit["binding"]["completion_sha256"]:
        raise ValueError("Explicit full-audit completion binding changed")
    import pyarrow.parquet as pq

    index_path = args.oracle_root / "index.parquet"
    if digest(index_path) != audit["binding"]["index_sha256"]:
        raise ValueError("Explicit full-audit index binding changed")
    index = pq.read_table(index_path, columns=["ticker", "date", "status"]).to_pylist()
    expected = {
        (row["ticker"], str(row["date"]))
        for row in index
        if row["status"] == "COMPLETE"
    }
    if len(expected) != 2595:
        raise ValueError("Audited expected feature key count differs")
    excluded = []
    for name in ("features.npz", "features.json", "actions.npz", "actions.json"):
        found = set()
        for path in args.feature_root.glob("*/*/" + name):
            ticker, date = path.parent.parent.name, path.parent.name
            if (
                ticker not in ("SPXW", "SPY", "QQQ")
                or len(date) != 8
                or not date.isdigit()
            ):
                excluded.append(str(path))
                continue
            found.add((ticker, date))
        if found - expected:
            raise ValueError(
                "Unexpected in-layout feature keys: " + repr(sorted(found - expected))
            )
        if found != expected:
            return f"WAIT_FEATURE_COVERAGE:{name}:{len(found)}/2595"
    write(
        args.runtime / "feature_key_check.json",
        {
            "status": "PASS_EXACT_AUDITED_KEYS",
            "expected_keys": 2595,
            "index_sha256": audit["binding"]["index_sha256"],
            "excluded_outside_ticker_date_layout": excluded,
        },
    )
    return "READY"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle-root", type=Path, required=True)
    parser.add_argument("--feature-root", type=Path, required=True)
    parser.add_argument("--oracle-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--resume-tcn", type=Path)
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    args.runtime.mkdir(parents=True, exist_ok=False)
    producer = Path(__file__).with_name("train_models.py")
    env = os.environ.copy()
    for name in (
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "OMP_NUM_THREADS",
    ):
        env[name] = "1"
        os.environ[name] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    command = [
        sys.executable,
        "-u",
        str(producer),
        "--oracle-root",
        str(args.oracle_root),
        "--feature-root",
        str(args.feature_root),
        "--oracle-audit",
        str(args.oracle_audit),
        "--output",
        str(args.output),
        "--device",
        "cuda",
    ]
    if args.resume_tcn:
        command.extend(["--resume-tcn", str(args.resume_tcn)])
    names = (
        "launch_learners.py",
        "train_models.py",
        "run_policy.py",
        "LEARNER_PLAN.md",
        "features.py",
        "build_cache.py",
        "level_engine.py",
        "run_engine_dataset.py",
        "PROTOCOL.md",
    )
    sources = {name: digest(Path(__file__).with_name(name)) for name in names}
    for name in names:
        shutil.copy2(Path(__file__).with_name(name), args.runtime / name)
    identity = {
        "created_utc": utc(),
        "command": command,
        "sources": sources,
        "thread_environment": {
            name: env[name]
            for name in (
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
                "OMP_NUM_THREADS",
            )
        },
        "lightgbm_explicit_threads": 4,
        "torch_explicit_cpu_threads": 4,
        "minimum_available_ram_gib": 10,
        "minimum_available_commit_gib": 12,
        "minimum_gpu_free_mib": 3072,
    }
    write(args.runtime / "identity.json", identity)
    while True:
        status = prerequisite_status(args)
        available = resources()
        ready_memory = (
            available["available_ram_bytes"] >= 10 * 1024**3
            and available["available_commit_bytes"] >= 12 * 1024**3
            and available["gpu_free_mib"] >= 3072
        )
        event = {
            "utc": utc(),
            "stage": status
            if status != "READY"
            else ("READY" if ready_memory else "WAIT_RESOURCE_HEADROOM"),
            **available,
        }
        with (args.runtime / "preflight.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
        print(json.dumps(event), flush=True)
        if status == "READY" and ready_memory:
            break
        if not args.wait:
            raise RuntimeError(
                "Prerequisites/resource headroom are not ready; no learner launched"
            )
        time.sleep(30)
    for name, expected in sources.items():
        if digest(Path(__file__).with_name(name)) != expected:
            raise ValueError(
                "Producer changed during resource wait; preserve runtime and start new snapshot"
            )
    started = time.monotonic()
    state = {"stage": "IMPORT_AND_PREFLIGHT", "stage_started": started}
    stage_records = []
    stage_peaks = {}
    with (args.runtime / "stdout.log").open("w", encoding="utf-8") as stdout:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        write(
            args.runtime / "started.json",
            {
                "utc": utc(),
                "pid": process.pid,
                "audit_path": str(args.oracle_audit),
                "audit_sha256": digest(args.oracle_audit),
                "resources": available,
            },
        )

        def read_output():
            for line in process.stdout:
                stdout.write(line)
                stdout.flush()
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, dict) and "stage" in value:
                    stage = value["stage"] + (
                        ":" + value["model"] if "model" in value else ""
                    )
                    if stage != state["stage"]:
                        now = time.monotonic()
                        stage_records.append(
                            {
                                "stage": state["stage"],
                                "wall_seconds": now - state["stage_started"],
                            }
                        )
                        state.update(stage=stage, stage_started=now)

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        peak_private = peak_rss = 0
        with (args.runtime / "resources.jsonl").open("a", encoding="utf-8") as stream:
            while process.poll() is None:
                private = rss = threads = 0
                try:
                    parent = psutil.Process(process.pid)
                    for child in [parent, *parent.children(recursive=True)]:
                        info = child.memory_info()
                        private += getattr(info, "private", info.vms)
                        rss += info.rss
                        threads += child.num_threads()
                except psutil.Error:
                    pass
                peak_private, peak_rss = max(peak_private, private), max(peak_rss, rss)
                stage = state["stage"]
                stage_peaks[stage] = max(stage_peaks.get(stage, 0), private)
                record = {
                    "utc": utc(),
                    "elapsed_seconds": time.monotonic() - started,
                    "stage": stage,
                    "private_bytes": private,
                    "rss_bytes": rss,
                    "threads": threads,
                    **resources(),
                }
                stream.write(json.dumps(record) + "\n")
                stream.flush()
                write(
                    args.runtime / "progress.json",
                    {
                        **record,
                        "peak_private_bytes": peak_private,
                        "peak_rss_bytes": peak_rss,
                    },
                )
                time.sleep(10)
        reader.join(timeout=10)
        stage_records.append(
            {
                "stage": state["stage"],
                "wall_seconds": time.monotonic() - state["stage_started"],
            }
        )
    summary = {
        "status": "COMPLETE" if process.returncode == 0 else "FAILED_PRESERVED",
        "exit_code": process.returncode,
        "finished_utc": utc(),
        "wall_seconds": time.monotonic() - started,
        "peak_private_bytes": peak_private,
        "peak_rss_bytes": peak_rss,
        "stages": stage_records,
        "stage_peak_private_bytes": stage_peaks,
        "sources": sources,
        "final_sources_match": all(
            digest(Path(__file__).with_name(name)) == value
            for name, value in sources.items()
        ),
    }
    write(args.runtime / "completion.json", summary)
    print(json.dumps(summary), flush=True)
    raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
