"""CPU learner launcher, resource observation only; no selection or model changes."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import psutil
from launch_learners import digest, resources, utc, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    args.runtime.mkdir(parents=True, exist_ok=False)
    sources = {}
    for name in (
        "launch_episode_pathfix.py",
        "resume_episode_pathfix.py",
        "train_episode_model.py",
        "episode_policy.py",
        "EPISODE_LEARNER_PLAN.md",
    ):
        path = Path(__file__).with_name(name)
        sources[name] = digest(path)
        (args.runtime / name).write_bytes(path.read_bytes())
    write(
        args.runtime / "identity.json",
        {"sources": sources, "new_fit_budget": 1, "device": "cpu", "threads": 4},
    )
    while True:
        available = resources()
        ready = (
            available["available_ram_bytes"] >= 10 * 1024**3
            and available["available_commit_bytes"] >= 12 * 1024**3
        )
        write(
            args.runtime / "preflight.json",
            {"utc": utc(), "status": "READY" if ready else "WAIT_MEMORY", **available},
        )
        if ready:
            break
        time.sleep(30)
    if any(
        digest(Path(__file__).with_name(name)) != expected
        for name, expected in sources.items()
    ):
        raise ValueError("Episode producer changed during resource wait")
    command = [
        sys.executable,
        "-u",
        str(Path(__file__).with_name("resume_episode_pathfix.py")),
        "--root",
        str(args.root),
        "--output",
        str(args.output),
    ]
    if args.resume:
        command.append("--resume")
    env = os.environ.copy()
    for name in (
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "OMP_NUM_THREADS",
    ):
        env[name] = "1"
    started = time.monotonic()
    state = {"stage": "IMPORT_AND_AUTHORITY", "started": started}
    stages = []
    peak_private = peak_rss = 0
    with (args.runtime / "stdout.log").open("w", encoding="utf-8") as log:
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
        tracked = psutil.Process(process.pid)
        write(
            args.runtime / "started.json",
            {
                "utc": utc(),
                "pid": process.pid,
                "create_time": tracked.create_time(),
                "command": command,
                "resources": available,
            },
        )

        def collect():
            for line in process.stdout:
                log.write(line)
                log.flush()
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if (
                    isinstance(item, dict)
                    and "stage" in item
                    and item["stage"] != state["stage"]
                ):
                    now = time.monotonic()
                    stages.append(
                        {"stage": state["stage"], "seconds": now - state["started"]}
                    )
                    state.update(stage=item["stage"], started=now)

        reader = threading.Thread(target=collect, daemon=True)
        reader.start()
        with (args.runtime / "resources.jsonl").open("w", encoding="utf-8") as records:
            while process.poll() is None:
                private = rss = 0
                try:
                    info = tracked.memory_info()
                    private, rss = getattr(info, "private", info.vms), info.rss
                except psutil.Error:
                    pass
                peak_private, peak_rss = max(peak_private, private), max(peak_rss, rss)
                record = {
                    "utc": utc(),
                    "stage": state["stage"],
                    "seconds": time.monotonic() - started,
                    "private_bytes": private,
                    "rss_bytes": rss,
                    "peak_private_bytes": peak_private,
                    "peak_rss_bytes": peak_rss,
                    **resources(),
                }
                records.write(json.dumps(record) + "\n")
                records.flush()
                write(args.runtime / "progress.json", record)
                time.sleep(10)
        reader.join()
    stages.append(
        {"stage": state["stage"], "seconds": time.monotonic() - state["started"]}
    )
    result = {
        "status": "COMPLETE" if process.returncode == 0 else "FAILED",
        "exit_code": process.returncode,
        "finished_utc": utc(),
        "wall_seconds": time.monotonic() - started,
        "peak_private_bytes": peak_private,
        "peak_rss_bytes": peak_rss,
        "stages": stages,
        "sources": sources,
        "final_sources_match": all(
            digest(Path(__file__).with_name(n)) == h for n, h in sources.items()
        ),
    }
    repair_root = args.output / "technical_repairs" / "source_path_v1"
    result["technical_repair_files"] = {
        str(p.resolve()): digest(p)
        for p in (repair_root / "repair.json", repair_root / "completion.json")
        if p.exists()
    }
    write(args.runtime / "completion.json", result)
    print(json.dumps(result), flush=True)
    raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
