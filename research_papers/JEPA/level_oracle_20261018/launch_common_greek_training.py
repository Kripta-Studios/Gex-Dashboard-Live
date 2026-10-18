"""Operational single-attempt launcher; requires exact final review SHA argument."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil

import train_market_cue_control as helper


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-sha", required=True)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    repo = directory.parents[2]
    review = directory / "COMMON_GREEK_TRAINER_REVIEW.json"
    if helper.sha(review) != args.review_sha:
        raise ValueError("Final review SHA differs")
    if helper.read_json(review)["status"] != "PASS_COMMON_GREEK_TRAINER_REVIEW":
        raise ValueError("Final review not approved")
    artifact = Path("D:/GexResearchArtifacts/level_oracle_20261018")
    out = artifact / "common_greek_control_v1"
    logs = artifact / "common_greek_control_v1_logs"
    if out.exists():
        raise FileExistsError(
            "Existing attempt preserved; use separately reviewed continuation"
        )
    logs.mkdir(exist_ok=False)
    command = [
        sys.executable,
        "-u",
        str(directory / "train_common_greek_control.py"),
        "--features",
        str(artifact / "common_greek_train_v1"),
        "--cue",
        str(artifact / "market_cue_control_v1"),
        "--learner",
        str(artifact / "learners_v1"),
        "--review",
        str(review),
        "--out",
        str(out),
    ]
    env = os.environ.copy()
    for key in (
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OMP_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        env[key] = "1"
    with (logs / "resources.jsonl").open("x", encoding="utf-8") as history:

        def record(stage, process=None):
            ram, commit = helper.resource_snapshot()
            value = dict(
                utc=datetime.now(timezone.utc).isoformat(),
                stage=stage,
                available_ram=ram,
                free_commit=commit,
            )
            if process is not None:
                try:
                    p = psutil.Process(process.pid)
                    value.update(
                        pid=p.pid,
                        rss=p.memory_info().rss,
                        private=p.memory_info().private,
                        cpu_user=p.cpu_times().user,
                    )
                except psutil.NoSuchProcess:
                    pass
            history.write(json.dumps(value) + "\n")
            history.flush()
            return ram, commit

        while True:
            ram, commit = record("PREFLIGHT")
            if ram >= 12 * 1024**3 and commit >= 16 * 1024**3:
                break
            print("WAITING_RESOURCES 12GiB RAM / 16GiB commit", flush=True)
            time.sleep(30)
        with (
            (logs / "stdout.log").open("x") as stdout,
            (logs / "stderr.log").open("x") as stderr,
        ):
            p = subprocess.Popen(
                command,
                cwd=repo,
                env=env,
                stdout=stdout,
                stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            helper.atomic_json(
                logs / "runtime.json",
                dict(
                    pid=p.pid,
                    command=command,
                    started_utc=datetime.now(timezone.utc).isoformat(),
                    review_sha256=args.review_sha,
                    launcher_sha256=helper.sha(__file__),
                    blas_threads=1,
                    lightgbm_threads=4,
                ),
            )
            print("TRAIN_PROCESS_STARTED", p.pid, flush=True)
            while p.poll() is None:
                record("RUNNING", p)
                try:
                    p.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    pass
        helper.atomic_json(
            logs / "process_exit.json",
            dict(
                pid=p.pid,
                exit_code=p.returncode,
                finished_utc=datetime.now(timezone.utc).isoformat(),
                model_completion_exists=(out / "model.complete.json").exists(),
            ),
        )
        print("TRAIN_PROCESS_EXIT", p.returncode, flush=True)
        return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
