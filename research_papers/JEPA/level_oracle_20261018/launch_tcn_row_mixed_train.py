"""One CUDA launch of the frozen row-mixed producer; operational resource gate."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psutil

import train_market_cue_control as helper

GATE = 2_000_000_000
CACHE_SHA = "2671fda58cb1f26df2b6f440749e43b644de84196dd14c7bac526d1a91272c3d"
RUNNER_SHA = "5c4adfe01e2a51f3eb0f16c96479edb326e2f06ea1f66b3721313ccaa9ab7ab2"


def gpu_snapshot():
    result = subprocess.run(
        [
            "nvidia-smi",
            "--id=0",
            "--query-gpu=memory.free,memory.total,memory.used",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        text=True,
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    free, total, used = [
        int(v.strip()) * 1024**2 for v in result.stdout.strip().split(",")
    ]
    return dict(free_vram=free, total_vram=total, used_vram=used)


def eligible(ram, commit, vram):
    return min(ram, commit, vram) >= GATE


def own_tcn_processes(directory):
    found = []
    roots = [
        directory.resolve(),
        Path("D:/GexResearchArtifacts/level_oracle_20261018/learners_v1").resolve(),
    ]
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        if (
            process.pid == os.getpid()
            or "python" not in (process.info["name"] or "").lower()
        ):
            continue
        cmd = process.info["cmdline"] or []
        if not any(str(v).startswith("cuda") for v in cmd):
            continue
        for arg in cmd:
            if Path(arg).name not in {
                "run_tcn_flags.py",
                "run_tcn_row_mixed.py",
                "train_models.py",
            }:
                continue
            try:
                path = (
                    Path(arg) if Path(arg).is_absolute() else Path(process.cwd()) / arg
                )
                if path.resolve().parent in roots:
                    found.append(process.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    return sorted(set(found))


def command_for(directory, cache, flags_root):
    return [
        sys.executable,
        "-u",
        str(directory / "run_tcn_row_mixed.py"),
        "--stage",
        "train",
        "--flags-root",
        str(flags_root),
        "--output",
        str(cache),
        "--device",
        "cuda",
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--review-sha", required=True)
    parser.add_argument("--logs", type=Path, required=True)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    cache = Path("D:/GexResearchArtifacts/level_oracle_20261018/tcn_row_mixed_v1")
    helper.require(helper.sha(args.review) == args.review_sha, "Runtime review changed")
    review = helper.read_json(args.review)
    helper.require(
        review["status"] == "PASS_TCN_ROW_MIXED_TRAIN_RUNTIME_REVIEW"
        and review["gate_bytes"] == GATE
        and review["cache_sha256"] == CACHE_SHA
        and review["runner_sha256"] == RUNNER_SHA,
        "Wrong runtime authority",
    )
    required = set(helper.DEPENDENCIES) | {
        Path(__file__).name,
        "TCN_ROW_MIXED_TRAIN_RUNTIME_SPEC.md",
    }
    helper.require(required.issubset(review["files"]), "Missing runtime dependency")
    for name, digest in review["files"].items():
        helper.require(helper.sha(directory / name) == digest, "Reviewed code changed")
    helper.require(
        helper.sha(cache / "cache_complete.json") == CACHE_SHA, "Cache manifest changed"
    )
    helper.require(
        helper.sha(directory / "run_tcn_row_mixed.py") == RUNNER_SHA, "Runner changed"
    )
    manifest = helper.read_json(cache / "cache_complete.json")
    code = {
        p: h for p, h in manifest["files"].items() if Path(p).suffix in (".py", ".md")
    }
    for path, digest in code.items():
        helper.require(helper.sha(path) == digest, "Cache code dependency changed")
    helper.require(
        not (cache / "training_complete.json").exists()
        and not list(cache.glob("tcn_epoch*.pt")),
        "Existing training attempt requires separate continuation",
    )
    helper.require(
        not own_tcn_processes(directory), "Another own CUDA TCN producer is active"
    )
    args.logs.mkdir(parents=True, exist_ok=False)
    for name in review["files"]:
        shutil.copyfile(directory / name, args.logs / (name + ".snapshot"))
    command = command_for(directory, cache, Path(manifest["flags_root"]))
    env = os.environ.copy()
    for key in (
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OMP_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        env[key] = "1"
    env["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    known = set()
    with (args.logs / "resources.jsonl").open("x") as history:

        def record(stage, process=None):
            ram, commit = helper.resource_snapshot()
            try:
                gpu = gpu_snapshot()
            except (subprocess.SubprocessError, OSError, ValueError) as error:
                gpu = dict(free_vram=None, gpu_monitor_error=repr(error))
            value = dict(
                utc=datetime.now(timezone.utc).isoformat(),
                stage=stage,
                available_ram=ram,
                free_commit=commit,
                **gpu,
            )
            if process is not None:
                try:
                    p = psutil.Process(process.pid)
                    mem = p.memory_info()
                    value.update(
                        pid=p.pid, private=getattr(mem, "private", mem.rss), rss=mem.rss
                    )
                except psutil.NoSuchProcess:
                    pass
            history.write(json.dumps(value) + "\n")
            history.flush()
            return value["free_vram"] is not None and eligible(
                ram, commit, value["free_vram"]
            )

        while not record("PREFLIGHT"):
            print("WAITING_RESOURCES_USER_2GB", flush=True)
            time.sleep(1)
        helper.require(
            not own_tcn_processes(directory), "Another own CUDA producer started"
        )
        with (
            (args.logs / "stdout.log").open("x") as stdout,
            (args.logs / "stderr.log").open("x") as stderr,
        ):
            process = subprocess.Popen(
                command,
                cwd=directory.parents[2],
                env=env,
                stdout=stdout,
                stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            helper.atomic_json(
                args.logs / "runtime.json",
                dict(
                    pid=process.pid,
                    command=command,
                    started_utc=datetime.now(timezone.utc).isoformat(),
                    gate_bytes=GATE,
                    review_sha256=args.review_sha,
                    cache_sha256=CACHE_SHA,
                    runner_sha256=RUNNER_SHA,
                    launcher_sha256=helper.sha(__file__),
                    code_dependencies=code,
                    blas_threads=1,
                    torch_threads=4,
                ),
            )
            print("ROW_MIXED_PROCESS_STARTED", process.pid, flush=True)
            while process.poll() is None:
                record("RUNNING", process)
                for metadata in sorted(cache.glob("tcn_epoch*.json")):
                    model = metadata.with_suffix(".pt")
                    if metadata.name not in known and model.exists():
                        helper.atomic_json(
                            args.logs / (metadata.stem + ".observed.json"),
                            dict(
                                observed_utc=datetime.now(timezone.utc).isoformat(),
                                metadata_sha256=helper.sha(metadata),
                                model_sha256=helper.sha(model),
                            ),
                        )
                        known.add(metadata.name)
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
        completion = cache / "training_complete.json"
        helper.atomic_json(
            args.logs / "process_exit.json",
            dict(
                pid=process.pid,
                exit_code=process.returncode,
                finished_utc=datetime.now(timezone.utc).isoformat(),
                training_completion_sha256=helper.sha(completion)
                if completion.exists()
                else None,
            ),
        )
        print("ROW_MIXED_PROCESS_EXIT", process.returncode, flush=True)
        return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
