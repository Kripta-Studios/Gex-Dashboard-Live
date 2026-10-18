"""Read-only process/output observer; never starts, stops or modifies a producer."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

import psutil


def write(path, value):
    temporary = path.with_suffix(".partial")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    process = psutil.Process(args.pid)
    created = process.create_time()
    command = process.cmdline()
    if not any(Path(part).name == "diagnose_oracle_model.py" for part in command):
        raise ValueError("Observer target is not this diagnostic")
    peak_private = peak_rss = 0
    write(
        args.runtime / "observed_process.json",
        dict(
            pid=args.pid,
            create_time=created,
            command=command,
            observed_from_utc=datetime.now(timezone.utc).isoformat(),
        ),
    )
    record = {}
    with (args.runtime / "resources.jsonl").open("x", encoding="utf-8") as log:
        while True:
            try:
                if process.create_time() != created or not process.is_running():
                    break
                memory = process.memory_info()
                private = getattr(memory, "private", memory.vms)
                peak_private, peak_rss = (
                    max(private, peak_private),
                    max(memory.rss, peak_rss),
                )
                record = dict(
                    utc=datetime.now(timezone.utc).isoformat(),
                    elapsed_from_process_start=time.time() - created,
                    pid=args.pid,
                    private_bytes=private,
                    rss_bytes=memory.rss,
                    peak_private_since_observer_start=peak_private,
                    peak_rss_since_observer_start=peak_rss,
                    available_ram_bytes=psutil.virtual_memory().available,
                    cpu=process.cpu_times()._asdict(),
                    io=process.io_counters()._asdict(),
                    completed_days={
                        split: len(list((args.output / split).glob("*.complete.json")))
                        for split in ("validation", "train")
                    },
                )
                write(args.runtime / "progress.json", record)
                log.write(json.dumps(record) + "\n")
                log.flush()
            except psutil.NoSuchProcess:
                break
            time.sleep(30)
    summary = args.output / "summary.json"
    result = dict(
        status="PROCESS_EXITED",
        final_record=record,
        summary_sha256=sha(summary) if summary.exists() else None,
    )
    if summary.exists():
        result["producer_status"] = json.loads(summary.read_text(encoding="utf-8"))[
            "status"
        ]
    write(args.runtime / "observed_completion.json", result)


if __name__ == "__main__":
    main()
