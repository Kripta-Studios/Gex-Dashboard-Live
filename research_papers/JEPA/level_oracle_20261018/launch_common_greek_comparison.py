"""Operational launcher only: frozen 424 comparison, explicit 2GB admission gate."""

import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psutil

CODE = Path(__file__).resolve().parent
REPO = CODE.parents[2]
ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018")
OUT = ROOT / "common_greek_comparison_v1"
LAUNCH = ROOT / "common_greek_comparison_v1_launch"
REVIEW = CODE / "COMMON_GREEK_COMPARISON_IMPLEMENTATION_REVIEW.json"
REVIEW_SHA = "6270e38baa5fded3fd0a12d5b16b7969347e3a43b6c1cc068b95783c7efbb540"
AUDITOR_SHA = "3898ef3c8ae634a65a2a136c75f2e14a46d5ac6fcad4bcc28bdb77742f3dca70"
MIN_FREE = 2_000_000_000


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def publish(name, value):
    path = LAUNCH / name
    temporary = path.with_suffix(path.suffix + ".partial")
    assert not path.exists() and not temporary.exists()
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def resources():
    class Status(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong)
            for name in (
                "total_phys",
                "avail_phys",
                "total_page",
                "avail_page",
                "total_virtual",
                "avail_virtual",
                "avail_extended",
            )
        ]

    status = Status()
    status.length = ctypes.sizeof(Status)
    assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return dict(
        available_ram_bytes=status.avail_phys, free_commit_bytes=status.avail_page
    )


def main():
    # Running this entry point is an explicit operational action, never automatic.
    assert len(sys.argv) == 2 and sys.argv[1] == "--authorized-stage-all"
    assert not LAUNCH.exists() and not OUT.exists(), (
        "Fresh launch and output roots required"
    )
    LAUNCH.mkdir()
    assert sha(REVIEW) == REVIEW_SHA
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    assert review["status"] == "PASS_COMMON_GREEK_COMPARISON_IMPLEMENTATION_REVIEW"
    auditor = CODE / "audit_common_greek_comparison.py"
    assert sha(auditor) == AUDITOR_SHA
    authorities = {
        "cue_comparison_audit_sha256": ROOT
        / "market_cue_comparison_v1_economic_audit_v3/audit.json",
        "session_audit_sha256": ROOT / "session_clock_dataset_v1_audit/audit.json",
        "cue_contract_sha256": ROOT / "market_cue_control_v1/run_contract.json",
        "cue_model_completion_sha256": ROOT
        / "market_cue_control_v1/model.complete.json",
        "greek_contract_sha256": ROOT
        / "common_greek_control_resource_v1/run_contract.json",
        "greek_model_completion_sha256": ROOT
        / "common_greek_control_resource_v1/model.complete.json",
    }
    pins = {str(CODE / name): digest for name, digest in review["dependencies"].items()}
    assert review["authorities"] == {
        field: sha(path) for field, path in authorities.items()
    }
    pins.update(
        {str(path): review["authorities"][field] for field, path in authorities.items()}
    )
    pins.update(
        {
            str(REVIEW): REVIEW_SHA,
            str(auditor): AUDITOR_SHA,
            str(Path(__file__)): sha(__file__),
        }
    )
    snapshots = LAUNCH / "reviewed_sources"
    snapshots.mkdir()
    for i, (path, digest) in enumerate(pins.items()):
        assert sha(path) == digest
        destination = snapshots / (str(i) + "_" + Path(path).name)
        shutil.copy2(path, destination)
        assert sha(destination) == digest
    publish(
        "inputs.json",
        dict(files=pins, minimum_free_bytes=MIN_FREE, no_fit=True, threads=4),
    )
    while True:
        available = resources()
        if min(available.values()) >= MIN_FREE:
            break
        print(
            json.dumps(dict(status="WAITING_FOR_USER_2GB_GATE", **available)),
            flush=True,
        )
        time.sleep(15)
    for path, digest in pins.items():
        assert sha(path) == digest, "Authority changed while waiting"
    publish(
        "preflight.json",
        dict(
            status="PASS_FIXED_424_COMPARISON_PREFLIGHT",
            **available,
            review_sha256=REVIEW_SHA,
            auditor_sha256=AUDITOR_SHA,
        ),
    )
    command = [
        sys.executable,
        "-u",
        str(CODE / "evaluate_common_greek_control.py"),
        "--greek-root",
        str(ROOT / "common_greek_control_resource_v1"),
        "--cue-root",
        str(ROOT / "market_cue_control_v1"),
        "--cue-comparison-root",
        str(ROOT / "market_cue_comparison_v1"),
        "--cue-comparison-audit",
        str(authorities["cue_comparison_audit_sha256"]),
        "--session-root",
        str(ROOT / "session_clock_dataset_v1"),
        "--session-audit",
        str(authorities["session_audit_sha256"]),
        "--review",
        str(REVIEW),
        "--out",
        str(OUT),
        "--stage",
        "all",
    ]
    started = time.time()
    peak_rss = peak_private = 0
    minimum = available.copy()
    with (
        (LAUNCH / "stdout.log").open("xb") as stdout,
        (LAUNCH / "stderr.log").open("xb") as stderr,
    ):
        child = subprocess.Popen(command, cwd=REPO, stdout=stdout, stderr=stderr)
        process = psutil.Process(child.pid)
        publish(
            "process.json",
            dict(
                pid=child.pid,
                creation_time=process.create_time(),
                launcher_pid=os.getpid(),
                command=command,
                started_unix=started,
            ),
        )
        while child.poll() is None:
            try:
                memory = process.memory_info()
                peak_rss = max(peak_rss, memory.rss, getattr(memory, "peak_wset", 0))
                peak_private = max(peak_private, getattr(memory, "private", 0))
                for name, value in resources().items():
                    minimum[name] = min(minimum[name], value)
            except psutil.NoSuchProcess:
                pass
            time.sleep(1)
    publish(
        "exit.json",
        dict(
            exit_code=child.returncode,
            stage_wall_seconds=time.time() - started,
            peak_rss_bytes=peak_rss,
            peak_private_bytes=peak_private,
            minimum_free_observed=minimum,
            no_fit=True,
            sampling_seconds=1,
        ),
    )
    assert child.returncode == 0, "Comparison failed; preserve evidence"


if __name__ == "__main__":
    main()
