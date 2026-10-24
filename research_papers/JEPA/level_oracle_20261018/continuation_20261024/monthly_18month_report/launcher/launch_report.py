"""One-shot operational launcher; execute only after root reviews this exact file."""

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil


REPO = Path("C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live")
HERE = REPO / "research_papers/JEPA/level_oracle_20261018"
BASE = Path("D:/GexResearchArtifacts/level_oracle_20261018")
OUT = BASE / "monthly_18month_consolidated_report_20261024_01"
LOGS = BASE / "monthly_18month_consolidated_report_20261024_01_logs"
AUDIT = BASE / "monthly_walk_forward_test_audit_20261024_01/audit.json"
COMPLETION = BASE / "monthly_test_index_v2_audit_launch_20261024_01/completion.json"
AUDIT_SHA = "87bfea586be13e02fd7fd0fe59c819195c62a430f34c867f9ec661812569fd4e"
COMPLETION_SHA = "1045866ea9fdf7d926a51a221e9e5f453ead5146d835197ec99fabe3466b0165"
COMMIT = "02cb4f7404abab0564c567d17eeaccd887b22a24"
PINS = {
    "report_monthly_walk_forward_audited.py": "1968aefcba4abf650d5e13cd16435ac74067cfee78ce5752fde6427e5a941146",
    "test_report_monthly_walk_forward_audited.py": "6b5463a4dbad2872cf1c4eea902dbacfaeefdb66b39b62c3a48a871aa00fa244",
    "MONTHLY_WALK_FORWARD_AUDITED_REPORT_SPEC_20261024.md": "9cf8ad4f8b77dd5086fa3b5d9becfdd49b5d3c39d51bbb59bfeffc92d384fc40",
    "MONTHLY_WALK_FORWARD_REPORT_IMPLEMENTATION_REVIEW_20261024.json": "d7fa9f3be717d913c1e1dc3f622ad30d323e3690706b7714395ca5df68479c75",
}
GATE = 2_000_000_000


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    with (LOGS / name).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


class Memory(ctypes.Structure):
    _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in (
            "total_phys", "avail_phys", "total_page", "avail_page",
            "total_virtual", "avail_virtual", "avail_extended",
        )
    ]


KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)
KERNEL.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(Memory)]
KERNEL.GlobalMemoryStatusEx.restype = wintypes.BOOL
KERNEL.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
KERNEL.GetProcessTimes.restype = wintypes.BOOL
KERNEL.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
KERNEL.GetExitCodeProcess.restype = wintypes.BOOL


def resources():
    value = Memory()
    value.length = ctypes.sizeof(value)
    require(KERNEL.GlobalMemoryStatusEx(ctypes.byref(value)), "Memory API failed")
    return {"available_ram_bytes": value.avail_phys, "free_commit_bytes": value.avail_page}


def creation_time(child):
    values = [wintypes.FILETIME() for _ in range(4)]
    require(KERNEL.GetProcessTimes(int(child._handle), *[ctypes.byref(v) for v in values]),
            "GetProcessTimes failed")
    return ((values[0].dwHighDateTime << 32) + values[0].dwLowDateTime) / 1e7 - 11644473600


def run():
    require(not OUT.exists() and not LOGS.exists(), "Output/log root already exists")
    LOGS.mkdir()
    child = None
    created = None
    try:
        wrapper_sha = sha(__file__)
        require(sha(AUDIT) == AUDIT_SHA and sha(COMPLETION) == COMPLETION_SHA,
                "Audit/completion pin mismatch")
        audit = json.loads(AUDIT.read_text())
        completion = json.loads(COMPLETION.read_text())
        require(audit["status"] == "PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES"
                and audit["scope"] == "VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1",
                "Composite authority scope/status")
        require(completion["status"] == "COMPLETE_MONTHLY_TEST_INDEX_V2_AUDIT_SUPERVISION"
                and completion["exit_code"] == 0 and completion["audit_sha256"] == AUDIT_SHA,
                "Incomplete supervisor")
        for path, digest in completion["closure_files"].items():
            require(sha(path) == digest, f"Closure mismatch: {path}")
        source_exit = json.loads((COMPLETION.parent / "exit.json").read_text())
        require(source_exit["exit_code"] == 0 and source_exit["monitor_errors"] == [],
                "Audit process failed")
        for name, digest in PINS.items():
            require(sha(HERE / name) == digest, f"Working pin mismatch: {name}")
            relative = (HERE / name).relative_to(REPO).as_posix()
            blob = subprocess.check_output(["git", "show", f"{COMMIT}:{relative}"], cwd=REPO)
            require(hashlib.sha256(blob).hexdigest() == digest, f"Published pin mismatch: {name}")
        review = json.loads((HERE / "MONTHLY_WALK_FORWARD_REPORT_IMPLEMENTATION_REVIEW_20261024.json").read_text())
        require(review["decision"] == "CLEAR", "Reporter review not CLEAR")
        command = [sys.executable, "-u", str(HERE / "report_monthly_walk_forward_audited.py"),
                   "--monthly-root", str(BASE / "monthly_walk_forward_v1"), "--audit", str(AUDIT),
                   "--audit-sha256", AUDIT_SHA, "--out", str(OUT)]
        free = resources()
        require(min(free.values()) >= GATE, "Resource gate failed; no reporter launched")
        affinity = [min(psutil.Process().cpu_affinity())]
        psutil.Process().cpu_affinity(affinity)
        write("admission.json", dict(status="ADMITTED_SINGLE_REPORTER_EXECUTION", utc=utc(),
              authorized_by="root GO after review of exact launcher", command=command,
              available_resources_before_child=free, gate_bytes=GATE, threads=1,
              cpu_affinity=affinity, no_retry=True, out=str(OUT),
              pins={str(HERE / k): v for k, v in PINS.items()},
              external_audit_sha256=AUDIT_SHA, supervisor_completion_sha256=COMPLETION_SHA,
              publication_commit=COMMIT, local_git_objects_verified=True, launcher_sha256=wrapper_sha))
        env = dict(os.environ)
        for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            env[key] = "1"
        started = time.monotonic()
        with (LOGS / "stdout.txt").open("xb") as stdout, (LOGS / "stderr.txt").open("xb") as stderr:
            child = subprocess.Popen(command, cwd=HERE, env=env, stdin=subprocess.DEVNULL,
                                     stdout=stdout, stderr=stderr,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            created = creation_time(child)
            write("process.json", dict(command=command, pid=child.pid, creation_time=created,
                  creation_source="GetProcessTimes retained Popen handle", utc=utc(), wrapper_pid=os.getpid()))
            samples, monitor_error = [], None
            while child.poll() is None:
                try:
                    sample = dict(utc=utc(), **resources())
                    sample["rss_bytes"] = psutil.Process(child.pid).memory_info().rss
                    samples.append(sample)
                except psutil.NoSuchProcess:
                    pass
                except Exception as exc:
                    monitor_error = repr(exc)
                time.sleep(1)
            code = wintypes.DWORD()
            require(KERNEL.GetExitCodeProcess(int(child._handle), ctypes.byref(code)), "Exit API failed")
            require(code.value == child.returncode, "Retained exit differs from Popen")
        write("resources.json", dict(samples=samples, sample_count=len(samples), monitor_error=monitor_error))
        pins_unchanged = sha(__file__) == wrapper_sha and all(sha(HERE / k) == v for k, v in PINS.items())
        audit_unchanged = sha(AUDIT) == AUDIT_SHA and sha(COMPLETION) == COMPLETION_SHA
        record = dict(status="PROCESS_EXIT_OBSERVED", utc=utc(), pid=child.pid, creation_time=created,
                      exit_code=code.value, exit_code_source="GetExitCodeProcess retained Popen handle",
                      wall_seconds=time.monotonic() - started, monitor_error=monitor_error,
                      pins_unchanged=pins_unchanged, audit_unchanged=audit_unchanged,
                      sample_count=len(samples), peak_rss_bytes=max((s["rss_bytes"] for s in samples), default=0),
                      min_available_ram_bytes=min((s["available_ram_bytes"] for s in samples), default=free["available_ram_bytes"]),
                      min_free_commit_bytes=min((s["free_commit_bytes"] for s in samples), default=free["free_commit_bytes"]),
                      stdout_sha256=sha(LOGS / "stdout.txt"), stderr_sha256=sha(LOGS / "stderr.txt"))
        write("exit.json", record)
        print(json.dumps(record), flush=True)
        require(code.value == 0 and monitor_error is None and pins_unchanged and audit_unchanged,
                "Reporter execution did not close cleanly")
        manifest = json.loads((OUT / "output_manifest.json").read_text())
        require(manifest["status"] == "COMPLETE" and manifest["audit_sha256"] == AUDIT_SHA,
                "Reporter manifest incomplete")
    except BaseException as exc:
        original_error = repr(exc)
        child_exit = None
        closure_errors = []
        if child is not None:
            # The child's inherited stdout/stderr handles remain open even if
            # the parent's with-block closed its copies during exception unwind.
            # Do not abandon, kill or restart the already launched reporter.
            while True:
                try:
                    waited_code = child.wait()
                    break
                except KeyboardInterrupt as wait_error:
                    closure_errors.append(repr(wait_error))
            code = wintypes.DWORD()
            exit_api_ok = bool(KERNEL.GetExitCodeProcess(int(child._handle), ctypes.byref(code)))
            child_exit = dict(
                status="PROCESS_EXIT_OBSERVED_AFTER_LAUNCHER_EXCEPTION",
                utc=utc(), pid=child.pid, creation_time=created,
                exit_code=code.value if exit_api_ok else waited_code,
                exit_code_source=("GetExitCodeProcess retained Popen handle" if exit_api_ok
                                  else "Popen.wait retained process handle"),
                get_exit_code_process_succeeded=exit_api_ok,
                popen_wait_exit_code=waited_code, original_error=original_error,
                monitor_error=original_error, closure_errors=closure_errors,
            )
            if not exit_api_ok:
                child_exit["get_exit_code_process_error"] = ctypes.get_last_error()
            if exit_api_ok and code.value != waited_code:
                closure_errors.append("Retained exit differs from Popen.wait")
            write("exception_child_exit.json", child_exit)
        write("failure.json", dict(status="FAILED_SINGLE_ATTEMPT_NO_RETRY", utc=utc(),
              error=original_error, child_pid=child.pid if child else None,
              child_returncode=child.returncode if child else None,
              child_exit=child_exit, closure_errors=closure_errors))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", required=True)
    parser.parse_args()
    run()
