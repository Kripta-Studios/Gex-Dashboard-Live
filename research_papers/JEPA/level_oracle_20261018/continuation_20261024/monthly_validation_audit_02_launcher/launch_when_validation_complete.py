"""One-shot, local-only 2025 audit correction attempt 02. Import does no work.

Only --watch starts waiting or launches a process. No training, retry, or 2026.
The existing scientific lock is held without writing its bytes during audit.
The V2 implementation review needs an external SHA; no authority is inferred.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from datetime import date, datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psutil

REPO = Path(r"C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live")
HERE = REPO / "research_papers/JEPA/level_oracle_20261018"
ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018")
SCIENCE = ROOT / "monthly_walk_forward_v1"
RUNTIME = ROOT / "monthly_resource_overlay_resume_20261023_01"
MONITOR = ROOT / "monthly_resume_20261023_01_logs"
OUTPUT = ROOT / "monthly_walk_forward_validation_audit_20261024_02"
PREVIOUS = ROOT / "monthly_validation_audit_launch_20261023_01"
PREVIOUS_OUTPUT = ROOT / "monthly_walk_forward_validation_audit_20261023_01"
LAUNCH_ROOT = Path(__file__).resolve().parent
CANONICAL_LAUNCH_ROOT = ROOT / "monthly_validation_audit_launch_20261024_02"
SOURCE_AUDIT = ROOT / "session_clock_dataset_v1_audit/audit.json"
ORIGINAL_AUDITOR = HERE / "audit_monthly_walk_forward.py"
ORIGINAL_REVIEW = HERE / "MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDITOR_REVIEW.json"
AUDITOR = HERE / "audit_monthly_walk_forward_index_v2.py"
REVIEW = HERE / "MONTHLY_WALK_FORWARD_INDEX_AUDIT_V2_REVIEW_20261024.json"
V2_TESTS = HERE / "test_audit_monthly_walk_forward_index_v2.py"
V2_SPEC = HERE / "MONTHLY_WALK_FORWARD_INDEX_AUDIT_V2_SPEC_20261024.md"
V2_REVIEW_STATUS = "PASS_MONTHLY_INDEX_V2_AUDITOR_IMPLEMENTATION_REVIEW"
PYTHON = Path(r"C:\Program Files\Python314\python.exe")
PID = 11852
CREATED = 1792784053.9282398
MIN_FREE = 2_000_000_000
CONTRACT_SHA = "7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f"
ORIGINAL_AUDITOR_SHA = "e4a3be1c19b7f0af1226e71255c81116bd71a6a300aef36f61c688deb908df1f"
AUDIT_STATUS = "PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES"
PINS = {
    ORIGINAL_AUDITOR: ORIGINAL_AUDITOR_SHA,
    ORIGINAL_REVIEW: "db323959e6a894d6d6fb51bde764af0c96db0cb0bba2f1711bbe0807425d10ca",
    HERE / "test_audit_monthly_walk_forward.py": "8c47e89951506553bfb1295c6e390501828b8fe6f77bcae5d566e98c2039ef87",
    HERE / "MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDIT_CONTRACT.md": "cabdd117fc4dc713fbca085a48e38ac8c8f609555f42f10a05321c01623ff8e7",
    HERE / "MONTHLY_RESOURCE_OVERLAY_REVIEW.json": "b48f30431c9ddd40b57a2aa61e20f6786c1fda746ae41cc03ee2812ba034b1b9",
    SOURCE_AUDIT: "678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9",
    SCIENCE / "run_contract.json": CONTRACT_SHA,
    RUNTIME / "launch.json": "22b1119e08f814a2b76c016d119bc8db9abe6aaa1eb13edb9af54dfd0c5fa69b",
    MONITOR / "process_monitor_binding.json": "21588f13e2fac83e4522eb848753a2431c509fb5e6a1b0627221c6d60b1714eb",
    MONITOR / "monitor_open.json": "3ee627e3200e6488dadf6882d61f013021dbd270f90ac4a8613e4674d29faef5",
    MONITOR / "monitor_existing_process_20261023.py": "96189a5f805113ab9d94ddc72b075a683048b79a13da8f680cbb80b4935b602b",
    MONITOR / "process.json": "056a155c06153e6dce6c9686b27cd2ed47f59ad93e2e228c81bcd0a1ac8ca8c2",
    MONITOR / "monitored_exit.json": "918964c6474df52067db5fb6eecb1c07339cb9bca262e8cab560f22ba3b00e93",
    RUNTIME / "completion.json": "ccce687bfa850d894606ff29ef6014add9e39a142fd84c3dd0d76e2a2a5c185b",
    PREVIOUS / "launch_when_validation_complete.py": "ccbecce5e10f03de302dbe19a448a1db138ed807b9c18bca266e43c377d10866",
    PREVIOUS / "process.json": "1255df01d0984278459ab711d317ecc57c4cb6470b8277a0ebb0a5056d6e58df",
    PREVIOUS / "exit.json": "d5e4fdf711e6965a56b8c60100788c2143aecbc7da450a93efe74736b9eadccb",
    PREVIOUS / "failure.json": "51cba5dd88423cdd2a9fdb05fa3c705f1944f21e8308144e386d76c2faaac019",
    PREVIOUS / "stderr.log": "f36e54b7e9bf94f8e4adc9b95068a013f5f9ea1b94db376a5b83d602be72b3c1",
    PREVIOUS / "attempt.json": "4e8060644e1f4431e4faafefe440961aabb3b000e0ed26dff962e309d03aa98a",
    PREVIOUS / "admission.json": "1fcdf8659eb5d6da26ddc485922b972cce8a4c2ca228187b22246becd5fea8e8",
    PREVIOUS / "root_launch_review.json": "ef385d8e30935d699755b8c22ee3bebf90008010c36390960f55578517dda64c",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_new(path, value):
    # Exclusive create is deliberate: a previous attempt is never adopted.
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())


def verify(files):
    for path, expected in files.items():
        require(sha(path) == expected, "Evidence hash differs: " + str(path))


def require_own_bytes(expected):
    require(sha(__file__) == expected, "Launcher changed after watch start")


def digest_string(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def v2_authority(expected_review_sha):
    require(digest_string(expected_review_sha), "An external lowercase SHA256 of the real V2 review is required")
    verify({REVIEW: expected_review_sha})
    review = read(REVIEW)
    require(review.get("status") == V2_REVIEW_STATUS
            and review.get("original_auditor_sha256") == ORIGINAL_AUDITOR_SHA
            and review.get("original_review_sha256") == PINS[ORIGINAL_REVIEW]
            and review.get("original_contract_sha256") == PINS[HERE / "MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDIT_CONTRACT.md"],
            "V2 review must bind the exact original implementation and contract")
    files = {REVIEW: expected_review_sha}
    for path, field in ((AUDITOR, "auditor_sha256"), (V2_TESTS, "tests_sha256"), (V2_SPEC, "contract_sha256")):
        require(digest_string(review.get(field)), "Incomplete V2 review file binding: " + field)
        files[path] = review[field]
    verify(files)
    return files


def previous_failure():
    require(not PREVIOUS_OUTPUT.exists(), "Failed attempt 01 output must remain absent")
    process = read(PREVIOUS / "process.json")
    exited = read(PREVIOUS / "exit.json")
    failure = read(PREVIOUS / "failure.json")
    attempt = read(PREVIOUS / "attempt.json")
    require(process.get("status") == "AUDITOR_PROCESS_STARTED"
            and process.get("pid") == 6840 and process.get("creation_time") == 1792797439.9007168
            and process.get("identity_source") == "GetProcessTimes on retained Popen handle"
            and process.get("command") == [str(PYTHON), "-u", str(ORIGINAL_AUDITOR),
                "--monthly-root", str(SCIENCE), "--source-audit", str(SOURCE_AUDIT),
                "--implementation-review", str(ORIGINAL_REVIEW), "--output", str(PREVIOUS_OUTPUT)],
            "Failed attempt 01 process identity or command differs")
    require(exited.get("status") == "AUDITOR_EXIT_OBSERVED_BY_POPEN_HANDLE"
            and exited.get("pid") == process["pid"] and exited.get("creation_time") == process["creation_time"]
            and type(exited.get("exit_code")) is int and exited["exit_code"] == 1
            and exited.get("process_receipt_sha256") == PINS[PREVIOUS / "process.json"]
            and failure.get("status") == "FAILED_PRESERVED_NO_RETRY"
            and stamp(process["started_utc"]) < stamp(exited["observed_utc"]) <= stamp(failure["utc"]),
            "Failed attempt 01 retained exit/failure chain differs")
    require(attempt.get("command") == process["command"] and attempt.get("retry_allowed") is False
            and attempt.get("admission_sha256") == PINS[PREVIOUS / "admission.json"]
            and attempt.get("script_sha256") == PINS[PREVIOUS / "launch_when_validation_complete.py"],
            "Failed attempt 01 admission or script binding differs")
    return dict(process_sha256=PINS[PREVIOUS / "process.json"],
                exit_sha256=PINS[PREVIOUS / "exit.json"], failure_sha256=PINS[PREVIOUS / "failure.json"],
                stderr_sha256=PINS[PREVIOUS / "stderr.log"], audit_output_absent=True)


def stamp(value):
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None, "Naive receipt timestamp")
    return result.astimezone(timezone.utc)


def free_commit():
    class Performance(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD)] + [(key, ctypes.c_size_t) for key in (
            "CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal", "PhysicalAvailable",
            "SystemCache", "KernelTotal", "KernelPaged", "KernelNonpaged", "PageSize"
        )] + [(key, wintypes.DWORD) for key in ("HandleCount", "ProcessCount", "ThreadCount")]
    info = Performance()
    info.cb = ctypes.sizeof(info)
    require(ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb),
            "Cannot measure Windows commit headroom")
    return (info.CommitLimit - info.CommitTotal) * info.PageSize


def observation():
    return dict(utc=utc(), available_ram_bytes=psutil.virtual_memory().available,
                free_commit_bytes=free_commit())


def ready(value):
    return value["available_ram_bytes"] >= MIN_FREE and value["free_commit_bytes"] >= MIN_FREE


def static_checks(expected_review_sha):
    require(os.name == "nt", "Windows handle and lock contract required")
    verify(PINS)
    v2_authority(expected_review_sha)
    previous_failure()
    contract, launch = read(SCIENCE / "run_contract.json"), read(RUNTIME / "launch.json")
    authority = launch["authority"]
    require(launch["pid"] == PID and authority["scope"] == "validation"
            and authority["original_run_contract_sha256"] == CONTRACT_SHA
            and authority["scientific_inputs_changed"] is False
            and authority["threshold_bytes"] == MIN_FREE, "Pinned validation launch differs")
    require(contract["dependencies"] == authority["original_dependencies"]
            and len(contract["dependencies"]) == 11, "Eleven scientific dependencies required")
    for name, digest in contract["dependencies"].items():
        require(Path(name).name == name, "Unsafe dependency path")
        verify({HERE / name: digest, SCIENCE / "executed_code" / name: digest})
    for name, digest in authority["files"].items():
        verify({HERE / name: digest})
    verify(launch["snapshots"])
    review = read(ORIGINAL_REVIEW)
    require(review["status"] == "PASS_MONTHLY_SEALED_SCORE_AUDITOR_IMPLEMENTATION_REVIEW"
            and review["auditor_sha256"] == ORIGINAL_AUDITOR_SHA, "Original auditor review differs")
    return launch


def process_binding():
    binding, opened = read(MONITOR / "process_monitor_binding.json"), read(MONITOR / "monitor_open.json")
    for value in (binding, opened):
        require(value["pid"] == PID and value["creation_time"] == CREATED, "Validation process identity differs")
    require(opened["status"] == "PROCESS_HANDLE_RETAINED"
            and opened["process_receipt_sha256"] == PINS[MONITOR / "process_monitor_binding.json"]
            and opened["monitor_code_sha256"] == PINS[MONITOR / "monitor_existing_process_20261023.py"]
            and opened["command"] == binding["command"], "Retained monitor binding differs")
    require(binding["source_launch_receipt_sha256"] == PINS[MONITOR / "process.json"]
            and binding["normalized_from_existing_receipt_with_live_command_and_creation_check"] is True,
            "Normalized launch provenance differs")
    return binding, opened


def validate_exit(binding, opened, exited):
    require(exited["status"] == "PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE"
            and exited["pid"] == PID and exited["creation_time"] == CREATED
            and exited["process_receipt_sha256"] == PINS[MONITOR / "process_monitor_binding.json"]
            and type(exited["exit_code"]) is int and exited["exit_code"] == 0
            and stamp(exited["observed_utc"]) >= stamp(opened["monitor_started_utc"]),
            "Validation requires retained-handle exit zero")
    require(binding["command"] == opened["command"], "Process command differs")


def wait_validation():
    binding, opened = process_binding()
    while True:
        if (MONITOR / "monitored_exit.json").exists():
            exited = read(MONITOR / "monitored_exit.json")
            validate_exit(binding, opened, exited)
            require(not psutil.pid_exists(PID), "Validation PID still exists or was reused")
            return exited
        if psutil.pid_exists(PID):
            process = psutil.Process(PID)
            require(process.create_time() == CREATED and process.cmdline() == binding["command"],
                    "Observed validation identity changed")
        # The pinned monitor owns the handle. Absence is never interpreted as success.
        require(psutil.pid_exists(opened["monitor_pid"]), "Monitor vanished without an exit receipt")
        print(json.dumps(dict(status="WAITING_VALIDATION_RETAINED_EXIT", utc=utc(), pid=PID)), flush=True)
        time.sleep(30)


@contextmanager
def scientific_lock():
    import msvcrt
    path = SCIENCE / "run.lock"
    before = sha(path)
    try:
        with path.open("r+b") as handle:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        require(sha(path) == before, "Scientific lock bytes changed")


@contextmanager
def operational_lock():
    import msvcrt
    with (LAUNCH_ROOT / "supervisor.lock").open("a+b") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"1")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def handle_creation_time(handle):
    """Read creation from the same retained Popen handle even if child already exited."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    creation, exit_time, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
    require(kernel.GetProcessTimes(int(handle), ctypes.byref(creation), ctypes.byref(exit_time),
                                  ctypes.byref(kernel_time), ctypes.byref(user_time)),
            "Cannot obtain child creation time from retained handle")
    ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
    return ticks / 10_000_000 - 11_644_473_600


def wait_resources():
    ordinal = len(list(LAUNCH_ROOT.glob("resource_*.json")))
    while True:
        resources = observation()
        write_new(LAUNCH_ROOT / f"resource_{ordinal:05d}.json", resources)
        ordinal += 1
        if ready(resources):
            return resources
        print(json.dumps(dict(status="WAITING_AUDIT_RESOURCES", **resources)), flush=True)
        time.sleep(30)


def load_auditor():
    spec = importlib.util.spec_from_file_location("monthly_validation_independent_auditor", AUDITOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def admit(exited, expected_review_sha):
    launch = static_checks(expected_review_sha)
    require(not (RUNTIME / "failure.json").exists(), "Validation has a failure receipt")
    require(not OUTPUT.exists(), "Audit output already exists; no retry")
    require(not list(SCIENCE.glob("completion*.json")), "Global test closure is outside validation scope")
    for folder in ("predictions", "months", "ledgers", "reports"):
        require(not list((SCIENCE / folder).glob("2026*")), "2026 economic evidence is outside this launcher")
    completion = read(RUNTIME / "completion.json")
    require(completion["status"] == "COMPLETE_MONTHLY_RESOURCE_OVERLAY_VALIDATION"
            and completion["original_run_contract_sha256"] == CONTRACT_SHA
            and completion["scientific_inputs_changed"] is False
            and completion["runtime_review_sha256"] == launch["runtime_review_sha256"]
            and completion["preserved_checkpoints"] == launch["preserved_checkpoints"]
            and stamp(launch["started_utc"]) < stamp(completion["completed_utc"]) <= stamp(exited["observed_utc"]),
            "Validation runtime closure differs")
    require(completion["runtime_members"].get(str((RUNTIME / "launch.json").resolve())) == PINS[RUNTIME / "launch.json"],
            "Launch missing from runtime closure")
    for key in ("runtime_members", "preserved_checkpoints", "final_checkpoints"):
        verify(completion[key])
    auditor = load_auditor()  # Independent primitives only; no producer/scheduler import.
    verifier = auditor.Verifier()
    evidence = auditor.Evidence(SCIENCE, verifier, CONTRACT_SHA)
    expected = {auditor.window(mode, date(2025, month, 1))[2]
                for month in range(1, 13) for mode in auditor.MODES}
    require(len(expected) == 24, "Expected validation fit count differs")
    for suffix in (".txt", ".fit_started.json", ".complete.json"):
        actual = {p.name.removesuffix(suffix) for p in (SCIENCE / "models").glob("*" + suffix)}
        require(actual == expected, "Exactly 24 complete validation models required")
    for name in sorted(expected):
        for suffix in (".txt", ".fit_started.json"):
            evidence.member("models/" + name, SCIENCE / ("models/" + name + suffix))
        for suffix in (".txt", ".fit_started.json", ".complete.json"):
            path = SCIENCE / ("models/" + name + suffix)
            require(completion["final_checkpoints"].get(str(path.resolve())) == sha(path),
                    "Model missing from validation closure")
    for month in range(1, 13):
        prefix = f"months/2025{month:02d}/"
        evidence.marker(prefix + "predictions")
        for name in ("daily", "economics"):
            evidence.member(prefix + name, SCIENCE / (prefix + name + ".json"))
    evidence.member("validation_freeze", SCIENCE / "validation_freeze.json")
    evidence.member("reports/2025", SCIENCE / "reports/2025.json")
    freeze = read(SCIENCE / "validation_freeze.json")
    mode = freeze["selected_mode"]
    require((mode is None or mode in auditor.MODES) and freeze["status"] == (
        "FAIL_NO_DAILY_COMPLIANT_MODE" if mode is None else "SELECTED_RESEARCH_MODE")
        and freeze["approved"] is False and freeze["selection_period"] == "2025"
        and freeze["outcomes_2026_used_for_mode_selection"] is False, "Freeze including null must be preserved")
    verifier.recheck()
    files = {str(p.resolve()): digest for p, digest in PINS.items()}
    files.update({str(p.resolve()): digest for p, digest in v2_authority(expected_review_sha).items()})
    files.update({str((RUNTIME / "completion.json").resolve()): sha(RUNTIME / "completion.json"),
                  str((MONITOR / "monitored_exit.json").resolve()): sha(MONITOR / "monitored_exit.json"),
                  str((SCIENCE / "validation_freeze.json").resolve()): sha(SCIENCE / "validation_freeze.json")})
    files.update(completion["final_checkpoints"])
    files.update(verifier._flat)
    return dict(status="READY_FOR_ONE_INDEPENDENT_VALIDATION_AUDIT", utc=utc(),
                files=files, selected_mode=mode, model_count=24, month_count=12,
                validation_exit=exited, promotion_approved=False,
                correction_attempt=2, prior_failure=previous_failure(),
                implementation_review_sha256=expected_review_sha)


def audit_command(expected_review_sha):
    require(digest_string(expected_review_sha), "External V2 review SHA required in child command")
    return [str(PYTHON), "-u", str(AUDITOR), "--monthly-root", str(SCIENCE),
            "--source-audit", str(SOURCE_AUDIT), "--implementation-review", str(REVIEW),
            "--implementation-review-sha256", expected_review_sha,
            "--output", str(OUTPUT)]


def audit_result(expected_auditor_sha, expected_review_sha):
    result = read(OUTPUT / "audit.json")
    binding, audited = result["binding"], result["audited"]
    require(result["status"] == AUDIT_STATUS and result["audit_script_sha256"] == expected_auditor_sha
            and Path(binding["monthly_root"]).resolve() == SCIENCE.resolve()
            and binding["run_contract_sha256"] == CONTRACT_SHA
            and binding["session_audit_sha256"] == PINS[SOURCE_AUDIT]
            and binding["completed_months"] == [f"2025{month:02d}" for month in range(1, 13)]
            and audited["months"] == 12 and audited["unique_fit_windows"] == 24
            and audited["calendar_ticker_days"] == 750 and audited["modes"] == ["static", "expanding", "rolling12"]
            and audited["validation_selection_reconstructed"] is True
            and audited["validation_period_report_reconstructed"] is True
            and result["promotion_approved"] is False, "Independent audit closure differs")
    roots = result.get("verified_files", {}).get("root", {})
    lineage = {REVIEW: expected_review_sha, ORIGINAL_AUDITOR: ORIGINAL_AUDITOR_SHA,
               ORIGINAL_REVIEW: PINS[ORIGINAL_REVIEW],
               HERE / "MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDIT_CONTRACT.md":
                   PINS[HERE / "MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDIT_CONTRACT.md"]}
    require(all(roots.get(str(path.resolve())) == digest for path, digest in lineage.items()),
            "Independent audit is missing reviewed V2/original lineage")
    return result


def watch(expected_review_sha):
    require(LAUNCH_ROOT.resolve() == CANONICAL_LAUNCH_ROOT.resolve(), "Execute only the canonical external attempt 02 copy")
    script_digest = sha(__file__)
    own_files = {str(path.resolve()): sha(path) for path in
                 (Path(__file__), LAUNCH_ROOT / "test_launcher.py", LAUNCH_ROOT / "SPEC.md")}
    static_checks(expected_review_sha)
    reviewed_files = v2_authority(expected_review_sha)
    require(not OUTPUT.exists(), "Existing audit output cannot be reused")
    write_new(LAUNCH_ROOT / "watch_started.json", dict(status="WATCH_STARTED", utc=utc(),
              pid=os.getpid(), creation_time=psutil.Process().create_time(), script_sha256=script_digest,
              command=sys.argv, validation_pid=PID, validation_creation_time=CREATED,
              correction_attempt=2, implementation_review_sha256=expected_review_sha,
              prior_failure=previous_failure(), own_files=own_files))
    try:
        exited = wait_validation()
        with scientific_lock():
            # An immutable observation log, separate from all scientific artifacts.
            wait_resources()
            require_own_bytes(script_digest)
            verify(own_files)
            admission = admit(exited, expected_review_sha)
            write_new(LAUNCH_ROOT / "admission.json", admission)
            code = LAUNCH_ROOT / "executed_code"
            code.mkdir(exist_ok=False)
            for source in (Path(__file__), LAUNCH_ROOT / "test_launcher.py", LAUNCH_ROOT / "SPEC.md",
                           AUDITOR, REVIEW, V2_TESTS, V2_SPEC, ORIGINAL_AUDITOR,
                           ORIGINAL_REVIEW, HERE / "test_audit_monthly_walk_forward.py",
                           HERE / "MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDIT_CONTRACT.md"):
                destination = code / source.name
                shutil.copyfile(source, destination)
                require(sha(source) == sha(destination), "Snapshot changed during copy")
            require_own_bytes(script_digest)
            command = audit_command(expected_review_sha)
            write_new(LAUNCH_ROOT / "attempt.json", dict(status="ONE_AUDIT_ATTEMPT", utc=utc(), command=command,
                      cwd=str(REPO), admission_sha256=sha(LAUNCH_ROOT / "admission.json"),
                      script_sha256=script_digest, retry_allowed=False,
                      correction_attempt=2, prior_failure=previous_failure(),
                      implementation_review_sha256=expected_review_sha))
            env = os.environ.copy()
            env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
            wait_resources()
            verify(PINS)
            verify(reviewed_files)
            verify(own_files)
            require_own_bytes(script_digest)
            with (LAUNCH_ROOT / "stdout.log").open("xb") as stdout, (LAUNCH_ROOT / "stderr.log").open("xb") as stderr:
                started = time.monotonic()
                child = subprocess.Popen(command, cwd=REPO, env=env, stdout=stdout, stderr=stderr,
                                         creationflags=subprocess.CREATE_NO_WINDOW)
                # Popen retains the process handle until its exit is obtained.
                receipt = dict(status="AUDITOR_PROCESS_STARTED", pid=child.pid,
                               creation_time=handle_creation_time(child._handle), command=command,
                               identity_source="GetProcessTimes on retained Popen handle", started_utc=utc())
                write_new(LAUNCH_ROOT / "process.json", receipt)
                peak_rss, samples, last_notice = None, 0, time.monotonic()
                while True:
                    try:
                        rss = psutil.Process(child.pid).memory_info().rss
                        peak_rss = max(peak_rss or 0, rss)
                        samples += 1
                    except psutil.NoSuchProcess:
                        pass
                    try:
                        code_value = child.wait(timeout=1)
                        break
                    except subprocess.TimeoutExpired:
                        if time.monotonic() - last_notice >= 30:
                            print(json.dumps(dict(status="AUDITOR_RUNNING", pid=child.pid, utc=utc())), flush=True)
                            last_notice = time.monotonic()
                write_new(LAUNCH_ROOT / "exit.json", dict(status="AUDITOR_EXIT_OBSERVED_BY_POPEN_HANDLE",
                          pid=child.pid, creation_time=receipt["creation_time"], exit_code=code_value,
                          observed_utc=utc(), process_receipt_sha256=sha(LAUNCH_ROOT / "process.json"),
                          wall_seconds_since_launch=time.monotonic() - started, memory_samples=samples,
                          peak_rss_sampled_bytes=peak_rss, sampling_seconds=1,
                          memory_scope="Maximum observed RSS only; not an exact lifetime peak."))
            require(code_value == 0, "Independent auditor exited nonzero; no retry")
            audit_result(reviewed_files[AUDITOR], expected_review_sha)
            verify(admission["files"])
            verify(own_files)
            require_own_bytes(script_digest)
            write_new(LAUNCH_ROOT / "completion.json", dict(status="COMPLETE_VALIDATION_AUDIT_EXIT_ZERO_AND_PASS",
                      utc=utc(), audit_json=str(OUTPUT / "audit.json"), audit_sha256=sha(OUTPUT / "audit.json"),
                      exit_receipt_sha256=sha(LAUNCH_ROOT / "exit.json"),
                      admission_sha256=sha(LAUNCH_ROOT / "admission.json"),
                      script_sha256=script_digest,
                      correction_attempt=2, prior_failure=previous_failure(),
                      implementation_review_sha256=expected_review_sha,
                      selected_mode=admission["selected_mode"], promotion_approved=False,
                      limitation="Conditional on sealed scores; no model refit or inference reproduction."))
    except BaseException as exc:
        write_new(LAUNCH_ROOT / "failure.json", dict(status="FAILED_PRESERVED_NO_RETRY", utc=utc(), error=repr(exc)))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-static", action="store_true", help="Read-only pins; never wait or launch")
    modes.add_argument("--watch", action="store_true", help="One attempt after retained exit and complete validation")
    parser.add_argument("--v2-review-sha256", required=True,
                        help="External SHA256 of the reviewed and published V2 authority; no default")
    args = parser.parse_args()
    if args.check_static:
        static_checks(args.v2_review_sha256)
        process_binding()
        print(json.dumps(dict(status="STATIC_PINS_MATCH", pins=len(PINS) + 4,
                              command=audit_command(args.v2_review_sha256))))
    else:
        require(LAUNCH_ROOT.resolve() == CANONICAL_LAUNCH_ROOT.resolve(),
                "Execute only the canonical external attempt 02 copy")
        with operational_lock():
            watch(args.v2_review_sha256)


if __name__ == "__main__":
    main()
