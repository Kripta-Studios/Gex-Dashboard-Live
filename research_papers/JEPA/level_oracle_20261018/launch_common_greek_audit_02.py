"""Explicit audit02 launch after externally pinned V2 review and publication.

No scientific parameters are changed. Without --execute-reviewed-audit-02 this
entry point prints a preflight receipt only and never creates a process/output.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

CODE = Path(__file__).resolve().parent
REPO = CODE.parents[2]
ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018")
COMPARISON = ROOT / "common_greek_comparison_v1"
OUT = ROOT / "common_greek_comparison_v1_economic_audit_02"
LOGS = ROOT / "common_greek_comparison_v1_economic_audit_02_logs"
V2 = CODE / "audit_common_greek_comparison_paths_v2.py"
V2_REVIEW = CODE / "COMMON_GREEK_COMPARISON_PATH_AUDIT_V2_REVIEW_20261023.json"
ORIGINAL_REVIEW = CODE / "COMMON_GREEK_COMPARISON_IMPLEMENTATION_REVIEW.json"
ORIGINAL_AUDITOR_SHA = "3898ef3c8ae634a65a2a136c75f2e14a46d5ac6fcad4bcc28bdb77742f3dca70"
ORIGINAL_REVIEW_SHA = "6270e38baa5fded3fd0a12d5b16b7969347e3a43b6c1cc068b95783c7efbb540"
REVIEW_STATUS = "PASS_COMMON_GREEK_COMPARISON_PATH_AUDIT_V2_IMPLEMENTATION_REVIEW"
MIN_FREE = 2_000_000_000
CORE_PINS = {
    "completion.json": "40cfdf576885eecd10785946687e5cf87cce228c1483e3ddd43cbd911207c824",
    "comparison.complete.json": "ad916c5695e165693c9843d206329732dde1d9149fc8ee0f9354818caf399d6d",
    "freeze.json": "b2609c562a319004a3517575def64305f11dce9521daeec347e45901be37ec08",
    "period2025.json": "b69569c62db5072e4bfb11b905b32d738c7f104159a57bb7c573ee38ef143de9",
    "period2026.json": "a3ed43d019a692e844e0ea45318c9c8d58c15787e313cc1a881a2f5a17776f80",
    "period2025.complete.json": "0ca5a342278988c5cb20669ff9d03cf0b314354bce7d754cd50fb56f36c661fb",
    "period2026.complete.json": "420d8cc706185a23e5c396c424d70950079f3f3d86bbcab124963ffabe0d5c91",
    "test_freeze.json": "bddcedb2c89b37608464c248caff2b5c6d1632f605aa350c11cca48f91c3d824",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resources():
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong)
            for name in ("total_phys", "avail_phys", "total_page", "avail_page",
                         "total_virtual", "avail_virtual", "avail_extended")
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    require(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)),
            "Memory status unavailable")
    return {"available_ram_bytes": status.avail_phys,
            "free_commit_bytes": status.avail_page}


def resource_gate(observed):
    require(set(observed) == {"available_ram_bytes", "free_commit_bytes"},
            "Incomplete resource observation")
    require(min(observed.values()) >= MIN_FREE, "2GB RAM/commit admission gate unmet")


def verify_pins(pins):
    for path, expected in pins.items():
        require(re.fullmatch(r"[0-9a-f]{64}", expected) is not None, "Invalid SHA pin")
        require(sha(path) == expected, "Pinned artifact changed: " + str(path))


def validate_v2_review(review):
    require(review.get("status") == REVIEW_STATUS and review.get("decision") == "CLEAR"
            and review.get("scope") == "IMPLEMENTATION_ONLY"
            and review.get("runtime_authorized") is False, "V2 implementation review not CLEAR")
    binding = review["binding"]
    require(binding["original_auditor"] == {
        "audit_common_greek_comparison.py": ORIGINAL_AUDITOR_SHA}, "Original auditor identity")
    reviewed = binding["reviewed_implementation"]
    require({"audit_common_greek_comparison_paths_v2.py",
             "test_audit_common_greek_comparison_paths_v2.py",
             "COMMON_GREEK_COMPARISON_PATH_AUDIT_V2_SPEC_20261023.md"} == set(reviewed),
            "Incomplete V2 review membership")
    for name, expected in reviewed.items():
        require(Path(name).name == name and "/" not in name and "\\" not in name,
                "Review member must be a basename")
        require(re.fullmatch(r"[0-9a-f]{64}", expected) is not None, "Invalid review SHA")
    return reviewed


def review_reference_pins(review):
    binding = review["binding"]
    author = binding["author_validation_receipt"]
    maps = [binding["reviewed_implementation"], binding["dependencies"],
            binding["failure01_evidence"], {author["path"]: author["sha256"]}]
    require(set(binding["dependencies"]) == {
        "test_audit_common_greek_comparison.py", "COMMON_GREEK_COMPARISON_ECONOMIC_AUDIT_SPEC.md"},
        "V2 review legacy dependencies incomplete")
    pins = {}
    for source_map in maps:
        for name, expected in source_map.items():
            relative = Path(name)
            path = (CODE / relative).resolve()
            require(not relative.is_absolute() and ".." not in relative.parts
                    and path.is_relative_to(CODE), "Unsafe V2 review reference")
            require(path not in pins or pins[path] == expected, "Conflicting review references")
            pins[path] = expected
    return pins


def handle_creation_time(child):
    """Read the actual retained Popen process handle, including after fast exit."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get_times = kernel.GetProcessTimes
    get_times.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    get_times.restype = wintypes.BOOL
    created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
    if not get_times(wintypes.HANDLE(int(child._handle)), ctypes.byref(created),
                     ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time)):
        raise ctypes.WinError(ctypes.get_last_error())
    ticks = (created.dwHighDateTime << 32) | created.dwLowDateTime
    return (ticks - 116444736000000000) / 10_000_000


def verify_publication(commit, paths):
    """Verify exact local Git objects at the externally supplied publication commit.

    Remote publication verification belongs to root; this function makes no network
    call and does not claim a fresh GitHub check.
    """
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "Full publication commit required")
    for path, expected in paths.items():
        relative = Path(path).resolve().relative_to(REPO).as_posix()
        result = subprocess.run(["git", "show", commit + ":" + relative], cwd=REPO,
                                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        require(hashlib.sha256(result.stdout).hexdigest() == expected,
                "Published Git object differs: " + relative)


def command():
    return [sys.executable, "-u", str(V2), "--root", str(COMPARISON),
            "--session-root", str(ROOT / "session_clock_dataset_v1"),
            "--session-audit", str(ROOT / "session_clock_dataset_v1_audit/audit.json"),
            "--baseline-root", str(ROOT / "market_cue_comparison_v1"),
            "--baseline-audit", str(ROOT / "market_cue_comparison_v1_economic_audit_v3/audit.json"),
            "--cue-root", str(ROOT / "market_cue_control_v1"),
            "--greek-root", str(ROOT / "common_greek_control_resource_v1"),
            "--review", str(ORIGINAL_REVIEW), "--output", str(OUT)]


def preflight(review_sha, publication_commit):
    require(not OUT.exists() and not LOGS.exists(), "Fresh audit02 and log roots required")
    require(re.fullmatch(r"[0-9a-f]{64}", review_sha) is not None, "External review SHA required")
    require(sha(V2_REVIEW) == review_sha, "External V2 review pin differs")
    v2_review = read_json(V2_REVIEW)
    validate_v2_review(v2_review)
    code_pins = review_reference_pins(v2_review)
    code_pins.update({V2_REVIEW: review_sha, Path(__file__).resolve(): sha(__file__),
                     CODE / "audit_common_greek_comparison.py": ORIGINAL_AUDITOR_SHA,
                     ORIGINAL_REVIEW: ORIGINAL_REVIEW_SHA})
    verify_pins(code_pins)
    verify_publication(publication_commit, code_pins)
    scientific_review = read_json(ORIGINAL_REVIEW)
    pins = {**code_pins, **{COMPARISON / name: value for name, value in CORE_PINS.items()},
            **{CODE / name: value for name, value in scientific_review["dependencies"].items()}}
    authority_paths = {
        "cue_comparison_audit_sha256": ROOT / "market_cue_comparison_v1_economic_audit_v3/audit.json",
        "session_audit_sha256": ROOT / "session_clock_dataset_v1_audit/audit.json",
        "cue_contract_sha256": ROOT / "market_cue_control_v1/run_contract.json",
        "cue_model_completion_sha256": ROOT / "market_cue_control_v1/model.complete.json",
        "greek_contract_sha256": ROOT / "common_greek_control_resource_v1/run_contract.json",
        "greek_model_completion_sha256": ROOT / "common_greek_control_resource_v1/model.complete.json",
    }
    require(set(scientific_review["authorities"]) == set(authority_paths), "Scientific authorities")
    pins.update({path: scientific_review["authorities"][field]
                 for field, path in authority_paths.items()})
    verify_pins(pins)
    complete = read_json(COMPARISON / "comparison.complete.json")
    require(complete["status"] == "COMPLETE" and complete["binding"] == CORE_PINS["freeze.json"],
            "Producer global binding")
    for name, expected in CORE_PINS.items():
        if name != "comparison.complete.json":
            require(complete["files"].get(name) == expected, "Producer core membership: " + name)
    observed = resources()
    resource_gate(observed)
    return {"status": "PASS_OPERATIONAL_PREFLIGHT_ONLY_NOT_EXECUTED",
            "utc": datetime.now(timezone.utc).isoformat(), "minimum_free_bytes": MIN_FREE,
            "resources": observed, "files": {str(path): value for path, value in pins.items()},
            "publication_commit": publication_commit,
            "publication_scope": "Exact local Git objects; remote verification supplied by root",
            "v2_review_sha256": review_sha, "scientific_review_sha256": ORIGINAL_REVIEW_SHA,
            "command": command(), "no_fit": True, "no_prediction_inference": True,
            "retry": False, "sampling_seconds": 1}


def publish(name, value):
    path = LOGS / name
    temporary = path.with_suffix(path.suffix + ".partial")
    require(not path.exists(), "Immutable operational receipt already exists")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.rename(path)


def launch(receipt):
    import psutil

    require(not OUT.exists() and not LOGS.exists(), "Fresh audit02 and log roots required")
    verify_pins(receipt["files"])
    resource_gate(resources())
    LOGS.mkdir()
    publish("preflight.json", receipt)
    env = os.environ.copy()
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        env[key] = "1"
    verify_pins(receipt["files"])
    observed = resources()
    resource_gate(observed)
    publish("admission.json", {"utc": datetime.now(timezone.utc).isoformat(), **observed,
                              "minimum_free_bytes": MIN_FREE,
                              "threads": {key: env[key] for key in
                                          ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}})
    started = time.monotonic()
    minimum = observed.copy()
    peak_rss = peak_private = None
    sample_count, system_sample_count = 0, 1
    monitor_errors = []
    with (LOGS / "stdout.log").open("xb") as stdout, (LOGS / "stderr.log").open("xb") as stderr:
        child = subprocess.Popen(receipt["command"], cwd=REPO, env=env, stdout=stdout,
                                 stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        creation_time = handle_creation_time(child)
        try:
            process = psutil.Process(child.pid)
            if abs(process.create_time() - creation_time) > 0.00001:
                monitor_errors.append({"stage": "process_identity", "error": "PID creation mismatch"})
                process = None
        except psutil.Error as error:
            process = None
            monitor_errors.append({"stage": "process_identity", "error": repr(error)})
        record = {"pid": child.pid, "creation_time": creation_time,
                  "creation_time_source": "GetProcessTimes_retained_Popen_handle",
                  "wrapper_pid": os.getpid(), "command": receipt["command"],
                  "started_utc": datetime.now(timezone.utc).isoformat()}
        publish("process.json", record)
        print(json.dumps(record), flush=True)
        while child.poll() is None:
            try:
                if process is not None:
                    memory = process.memory_info()
                    sample_count += 1
                    peak_rss = max(peak_rss or 0, memory.rss)
                    peak_private = max(peak_private or 0, getattr(memory, "private", 0))
            except psutil.Error as error:
                if not isinstance(error, psutil.NoSuchProcess):
                    monitor_errors.append({"stage": "process_memory", "error": repr(error)})
            try:
                for name, value in resources().items():
                    minimum[name] = min(minimum[name], value)
                system_sample_count += 1
            except (OSError, RuntimeError) as error:
                monitor_errors.append({"stage": "system_memory", "error": repr(error)})
            time.sleep(1)
    result = {"exit_code": child.returncode, "wall_seconds": time.monotonic() - started,
              "finished_utc": datetime.now(timezone.utc).isoformat(),
              "peak_sampled_rss_bytes": peak_rss, "peak_sampled_private_bytes": peak_private,
              "minimum_free_observed": minimum, "sampling_seconds": 1, "retry": False,
              "sample_count": sample_count, "system_sample_count_including_admission": system_sample_count,
              "monitor_errors": monitor_errors}
    publish("exit.json", result)
    print(json.dumps(result), flush=True)
    return child.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v2-review-sha256", required=True)
    parser.add_argument("--publication-commit", required=True)
    parser.add_argument("--execute-reviewed-audit-02", action="store_true")
    args = parser.parse_args()
    receipt = preflight(args.v2_review_sha256, args.publication_commit)
    if not args.execute_reviewed_audit_02:
        print(json.dumps(receipt, indent=2))
        return 0
    return launch(receipt)


if __name__ == "__main__":
    raise SystemExit(main())
