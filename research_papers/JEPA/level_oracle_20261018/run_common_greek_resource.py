"""Explicit resource-only entrypoint; unchanged reviewed TRAIN fit implementation."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import threading
import time
import uuid

import psutil

import train_common_greek_control as trainer

helper = trainer.original
GATE_BYTES = 2_000_000_000
BASE_REVIEW_SHA = "79fc3d9ef28268083f014274b2371622b0003004c66b434daef1b439b515e61d"
TRAINER_SHA = "bba356f55467048c5f115d8fd7c580afcaa4a5c6cb2c532220df511319f3ce44"


def wait_resources(snapshot=helper.resource_snapshot, sleeper=time.sleep):
    while True:
        ram, commit = snapshot()
        if ram >= GATE_BYTES and commit >= GATE_BYTES:
            return
        print(
            json.dumps(
                dict(
                    stage="WAITING_RESOURCES_USER_2GB",
                    ram=ram,
                    commit=commit,
                    gate_bytes=GATE_BYTES,
                )
            ),
            flush=True,
        )
        sleeper(1)


@contextmanager
def memory_monitor(logs):
    logs.mkdir(parents=True, exist_ok=False)
    stop = threading.Event()
    p = psutil.Process()

    def monitor():
        with (logs / "resources.jsonl").open("x", encoding="utf-8") as handle:
            while not stop.is_set():
                ram, commit = helper.resource_snapshot()
                m = p.memory_info()
                handle.write(
                    json.dumps(
                        dict(
                            utc=datetime.now(timezone.utc).isoformat(),
                            pid=p.pid,
                            rss=m.rss,
                            private=getattr(m, "private", m.rss),
                            available_ram=ram,
                            free_commit=commit,
                        )
                    )
                    + "\n"
                )
                handle.flush()
                stop.wait(1)

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()


def fit_with_explicit_gate(source, evidence, fit=trainer.fit_once):
    return fit(source, evidence, resource_gate=wait_resources)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "features",
        "cue",
        "learner",
        "base-review",
        "runtime-review",
        "out",
        "logs",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    helper.require(
        all(
            os.environ.get(key) == "1"
            for key in (
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "OMP_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        ),
        "Launcher must set BLAS/OMP/NUMEXPR threads to1",
    )
    trainer.separate(args.out, [args.features, args.cue, args.learner, args.logs])
    trainer.separate(args.logs, [args.features, args.cue, args.learner])
    helper.require(
        helper.sha(args.base_review) == BASE_REVIEW_SHA, "Base review differs"
    )
    helper.require(helper.sha(trainer.__file__) == TRAINER_SHA, "Trainer changed")
    base = helper.read_json(args.base_review)
    runtime_sha = helper.sha(args.runtime_review)
    runtime = helper.read_json(args.runtime_review)
    helper.require(
        helper.sha(args.runtime_review) == runtime_sha
        and runtime["status"] == "PASS_COMMON_GREEK_RESOURCE_RUNTIME_REVIEW"
        and runtime["base_review_sha256"] == BASE_REVIEW_SHA
        and runtime["gate_bytes"] == GATE_BYTES,
        "Runtime review differs",
    )
    helper.require(
        set(runtime["files"])
        == {Path(__file__).name, "COMMON_GREEK_RESOURCE_RUNTIME_SPEC.md"},
        "Runtime review file set differs",
    )
    files = dict(base["files"])
    for name, digest in runtime["files"].items():
        helper.require(name not in files, "Runtime replaces frozen dependency")
        files[name] = digest
    for name, digest in files.items():
        helper.require(
            helper.sha(Path(__file__).with_name(name)) == digest,
            "Implementation changed: " + name,
        )
    with memory_monitor(args.logs):
        helper.atomic_json(
            args.logs / "runtime.json",
            dict(
                pid=os.getpid(),
                started_utc=datetime.now(timezone.utc).isoformat(),
                gate_bytes=GATE_BYTES,
                base_review_sha256=BASE_REVIEW_SHA,
                runtime_review_sha256=runtime_sha,
                entrypoint_sha256=helper.sha(__file__),
                blas_threads=1,
                lightgbm_threads=4,
            ),
        )
        try:
            wait_resources()
            with helper.output_lock(args.out):
                source = trainer.TrainingInputs(
                    args.features, args.cue, args.learner, base["authorities"]
                )
                source.verify(args.base_review, BASE_REVIEW_SHA)
                source.verify(args.runtime_review, runtime_sha)
                helper.bind_code_snapshots(source, args.out, files)
                contract = dict(
                    sources=source.hashes,
                    config=helper.CONFIG,
                    scales=source.scales,
                    schema=dict(column_names=source.columns),
                    rows=len(source.y),
                    train_only=True,
                    control_model_refitted=False,
                    resource_runtime=dict(
                        gate_bytes=GATE_BYTES,
                        monitor_interval_seconds=1,
                        user_requested=True,
                        base_review_sha256=BASE_REVIEW_SHA,
                        runtime_review_sha256=runtime_sha,
                    ),
                    packages={
                        p: importlib.metadata.version(p)
                        for p in ("numpy", "pandas", "lightgbm")
                    },
                )
                path = args.out / "run_contract.json"
                if path.exists():
                    helper.require(
                        helper.read_json(path) == contract, "Run contract changed"
                    )
                else:
                    helper.atomic_json(path, contract)
                evidence = helper.Checkpoints(args.out, helper.sha(path))
                fit_with_explicit_gate(source, evidence)
            helper.atomic_json(
                args.logs / "process_exit.json",
                dict(
                    exit_code=0,
                    pid=os.getpid(),
                    finished_utc=datetime.now(timezone.utc).isoformat(),
                    model_completion_sha256=helper.sha(
                        args.out / "model.complete.json"
                    ),
                ),
            )
            print("COMPLETE_COMMON_GREEK_RESOURCE_TRAIN", flush=True)
        except BaseException as error:
            helper.atomic_json(
                args.logs / ("failure_" + uuid.uuid4().hex + ".json"),
                dict(
                    error=repr(error),
                    pid=os.getpid(),
                    utc=datetime.now(timezone.utc).isoformat(),
                ),
            )
            raise


if __name__ == "__main__":
    main()
