"""One-shot retained-handle launcher for reviewed monthly test; default check only."""

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
import traceback

import run_monthly_test_resource_overlay as overlay

SCRIPT = Path(__file__).resolve()
CODE = SCRIPT.parent
REPO = CODE.parents[2]
WRAPPER = CODE / "run_monthly_test_resource_overlay.py"
REVIEW = CODE / "MONTHLY_TEST_RESOURCE_OVERLAY_REVIEW_20261023.json"
SCIENTIFIC_REVIEW = CODE / "MONTHLY_WALK_FORWARD_IMPLEMENTATION_REVIEW.json"
WRAPPER_SHA = "f2b0490cdec916f98c09fc77a6533d0eab8c4f2711331753f7d5c998d81253c1"
REVIEW_SHA = "49a3590504c74c06dc5a9b830bcf71b7472dbecae2ab267218aaa22aa2dd0280"
NEW_FILES = (
    "launch_monthly_test_20261023.py",
    "test_launch_monthly_test_20261023.py",
    "MONTHLY_TEST_LAUNCH_SPEC_20261023.md",
)
MIN_FREE = 2_000_000_000
LAUNCH_REVIEW_NAME = "MONTHLY_TEST_LAUNCH_IMPLEMENTATION_REVIEW_20261023.json"


def require(ok, message):
    if not bool(ok):
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(value):
    require(
        isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value),
        "External SHA256 required",
    )
    return value


def verify_pins(files):
    for path, expected in files.items():
        require(sha(path) == digest(expected), "Pinned file changed: " + str(path))


def publication_files(launcher_review=None):
    names = set(NEW_FILES) | set(overlay.review_expectations()["files"])
    names |= set(overlay.review_expectations()["original_dependencies"])
    names |= {REVIEW.name, SCIENTIFIC_REVIEW.name}
    launcher_review = (
        CODE / LAUNCH_REVIEW_NAME if launcher_review is None else launcher_review
    )
    require(
        launcher_review.parent == CODE, "Launcher review must be published beside code"
    )
    names.add(launcher_review.name)
    require(
        all(Path(n).name == n and "/" not in n and "\\" not in n for n in names),
        "Published members must be basenames",
    )
    return {name: sha(CODE / name) for name in sorted(names)}


def verify_publication(commit, files):
    require(
        isinstance(commit, str) and re.fullmatch("[0-9a-f]{40}", commit),
        "Full publication commit required",
    )
    for path, expected in files.items():
        path = Path(path).resolve()
        require(path.is_relative_to(REPO), "Published input outside repository")
        relative = path.relative_to(REPO).as_posix()
        result = subprocess.run(
            ["git", "show", commit + ":" + relative],
            cwd=REPO,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        require(
            hashlib.sha256(result.stdout).hexdigest() == expected,
            "Published Git object differs: " + relative,
        )


def resources():
    return overlay.resource_observation()


def gate(observation):
    require(
        all(
            type(observation.get(k)) is int and observation[k] >= MIN_FREE
            for k in ("available_ram_bytes", "free_commit_bytes")
        ),
        "2GB RAM/commit gate unmet",
    )


def command(runtime_root, runtime_review, audit_sha):
    return [
        sys.executable,
        "-u",
        str(WRAPPER),
        "--runtime-root",
        str(runtime_root),
        "--implementation-review",
        str(REVIEW),
        "--runtime-review",
        str(runtime_review),
        "--expected-validation-audit-sha256",
        audit_sha,
    ]


def fresh_roots(runtime_root, logs_root, runtime_review):
    overlay.guard_runtime_root(runtime_root)
    require(not logs_root.exists(), "Fresh logs root required")
    protected = (
        runtime_root,
        overlay.SCIENTIFIC_ROOT.resolve(),
        (overlay.ROOT / "session_clock_dataset_v1").resolve(),
        CODE,
        runtime_review,
        REVIEW,
        SCIENTIFIC_REVIEW,
    )
    require(
        all(
            not logs_root.is_relative_to(p) and not p.is_relative_to(logs_root)
            for p in protected
        ),
        "Logs overlap protected root/authority",
    )
    require(
        not runtime_review.is_relative_to(runtime_root),
        "Runtime authority inside output",
    )


def closed_validation(runtime):
    roots = tuple(overlay.absolute(p) for p in runtime["allowed_read_roots"])
    authorities = overlay.Authorities(roots)
    return overlay.verify_process_chain(
        runtime["validation"],
        authorities,
        overlay.absolute(runtime["validation"]["runtime_root"]),
        validation=True,
    )


def preflight(runtime_review_path, runtime_review_sha, audit_sha, publication_commit):
    require(os.name == "nt", "Windows retained process handle required")
    require(
        sys.flags.optimize == 0 and not os.environ.get("PYTHONOPTIMIZE"),
        "Unoptimized Python required",
    )
    runtime_review_path = overlay.absolute(str(runtime_review_path))
    verify_pins(
        {
            runtime_review_path: digest(runtime_review_sha),
            REVIEW: REVIEW_SHA,
            WRAPPER: WRAPPER_SHA,
        }
    )
    runtime = read(runtime_review_path)
    binding = runtime["launch_binding"]
    require(
        binding["status"] == "REVIEWED_MONTHLY_TEST_ONE_SHOT_LAUNCH",
        "Concrete reviewed launch binding required",
    )
    runtime_root = overlay.absolute(binding["runtime_root"])
    logs_root = overlay.absolute(binding["logs_root"])
    require(
        runtime_root != Path(runtime_root.anchor)
        and logs_root != Path(logs_root.anchor),
        "Volume output forbidden",
    )
    fresh_roots(runtime_root, logs_root, runtime_review_path)
    launcher_review = binding["launcher_review"]
    require(
        set(launcher_review) == {"path", "sha256"},
        "Exact launcher review authority required",
    )
    launcher_review_path = overlay.absolute(launcher_review["path"])
    require(
        launcher_review_path == CODE / LAUNCH_REVIEW_NAME,
        "Fixed launcher review path required",
    )
    verify_pins({launcher_review_path: digest(launcher_review["sha256"])})
    reviewed = read(launcher_review_path)
    require(
        reviewed.get("status") == "PASS_MONTHLY_TEST_LAUNCH_IMPLEMENTATION_REVIEW"
        and reviewed.get("decision") == "CLEAR"
        and reviewed.get("scope") == "IMPLEMENTATION_ONLY"
        and reviewed.get("runtime_authorized") is False
        and reviewed.get("files") == {name: sha(CODE / name) for name in NEW_FILES},
        "Exact independent launcher review required",
    )
    code = publication_files(launcher_review_path)
    require(binding["published_files"] == code, "Published code binding differs")
    pins = {str(CODE / name): value for name, value in code.items()}
    pins[str(runtime_review_path)] = runtime_review_sha
    verify_pins(pins)
    verify_publication(publication_commit, pins)
    require(
        runtime["validation"]["audit"]["sha256"] == digest(audit_sha),
        "External audit2025 SHA differs",
    )
    observed = resources()
    gate(observed)
    admitted = overlay.admit(REVIEW, runtime_review_path, audit_sha)
    # Shared admission verifies the complete real chain, including observed exit0.
    launch, exited = closed_validation(runtime)
    for mapping in (admitted["authorities"].files, admitted["preserved"]):
        for path, expected in mapping.items():
            require(
                path not in pins or pins[path] == expected, "Conflicting authority pin"
            )
            pins[path] = expected
    verify_pins(pins)
    gate(resources())
    return dict(
        status="PASS_MONTHLY_TEST_OPERATIONAL_PREFLIGHT_ONLY_NOT_EXECUTED",
        checked_utc=utc(),
        runtime_review=str(runtime_review_path),
        runtime_review_sha256=runtime_review_sha,
        validation_audit_sha256=audit_sha,
        runtime_root=str(runtime_root),
        logs_root=str(logs_root),
        publication_commit=publication_commit,
        files=pins,
        publication_files={str(CODE / n): h for n, h in code.items()},
        publication_scope="Exact local Git objects; root verifies remote publication separately",
        command=command(runtime_root, runtime_review_path, audit_sha),
        minimum_free_bytes=MIN_FREE,
        validation_pid=launch["pid"],
        validation_exit_code=exited["exit_code"],
        selected_mode=admitted["freeze"]["selected_mode"],
        retry=False,
        scientific_inputs_changed=False,
        executed=False,
    )


def publish(root, name, value):
    path = root / name
    temporary = path.with_suffix(path.suffix + ".partial")
    require(
        not path.exists() and not temporary.exists(), "Preserve operational artifact"
    )
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.rename(path)
    return sha(path)


class RetainedProcess:
    """All identity/wait/exit observations use the original Popen process handle."""

    def __init__(self, child):
        self.child = child
        self.handle = wintypes.HANDLE(int(child._handle))
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            *([ctypes.POINTER(wintypes.FILETIME)] * 4),
        ]
        self.kernel.GetProcessTimes.restype = wintypes.BOOL
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.kernel.GetExitCodeProcess.restype = wintypes.BOOL

    def creation_time(self):
        created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not self.kernel.GetProcessTimes(
            self.handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return (
            ((created.dwHighDateTime << 32) | created.dwLowDateTime)
            - 116444736000000000
        ) / 10_000_000

    def wait_exit(self):
        observed = self.kernel.WaitForSingleObject(self.handle, 1000)
        if observed == 258:
            return None
        if observed != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        value = wintypes.DWORD()
        if not self.kernel.GetExitCodeProcess(self.handle, ctypes.byref(value)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.child.returncode = int(value.value)
        return int(value.value)


def observe_exit(retained, logs):
    while True:
        try:
            code = retained.wait_exit()
            if code is not None:
                return code
        except KeyboardInterrupt:
            try:
                publish(
                    logs,
                    "interruption_" + str(time.time_ns()) + ".json",
                    dict(
                        status="INTERRUPTED_OBSERVER_HANDLE_STILL_RETAINED",
                        utc=utc(),
                        retry=False,
                    ),
                )
            except BaseException:
                # A failed observer log must not abandon a live retained handle.
                continue


def drain_child(child):
    """Safety fallback only; never fabricate retained-handle observation receipts."""
    while True:
        try:
            child.wait()
            return
        except KeyboardInterrupt:
            continue


def monitor(child, receipt, logs):
    completed = False
    try:
        retained = RetainedProcess(child)
        monitor_sha = receipt["publication_files"][str(SCRIPT)]
        require(
            receipt["files"].get(str(SCRIPT)) == monitor_sha,
            "Monitor publication binding differs",
        )
        verify_pins({SCRIPT: monitor_sha})
        created = retained.creation_time()
        binding = dict(
            pid=child.pid,
            creation_time=created,
            command=receipt["command"],
            started_utc=utc(),
            creation_time_source="GetProcessTimes_retained_Popen_handle",
            launcher_pid=os.getpid(),
            preflight_sha256=sha(logs / "preflight.json"),
        )
        binding_sha = publish(logs, "process_binding.json", binding)
        opened_sha = publish(
            logs,
            "monitor_open.json",
            dict(
                status="PROCESS_HANDLE_RETAINED",
                pid=child.pid,
                creation_time=created,
                command=receipt["command"],
                monitor_started_utc=utc(),
                process_receipt_sha256=binding_sha,
                monitor_code_sha256=monitor_sha,
            ),
        )
        code = observe_exit(retained, logs)
        completed = True
        verify_pins(
            {
                SCRIPT: monitor_sha,
                logs / "process_binding.json": binding_sha,
                logs / "monitor_open.json": opened_sha,
            }
        )
        publish(
            logs,
            "monitored_exit.json",
            dict(
                status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE",
                pid=child.pid,
                creation_time=created,
                exit_code=code,
                observed_utc=utc(),
                process_receipt_sha256=binding_sha,
                exit_code_source="GetExitCodeProcess_retained_Popen_handle",
                retry=False,
                scientific_completion_certified=False,
            ),
        )
        members = {
            name: dict(path=str(logs / filename), sha256=sha(logs / filename))
            for name, filename in (
                ("process_binding", "process_binding.json"),
                ("monitor_open", "monitor_open.json"),
                ("monitored_exit", "monitored_exit.json"),
            )
        }
        members["monitor_code"] = dict(path=str(SCRIPT), sha256=monitor_sha)
        launch_path = Path(receipt["runtime_root"]) / "launch.json"
        if launch_path.exists() and read(launch_path).get("pid") == child.pid:
            members["runtime_launch"] = dict(
                path=str(launch_path), sha256=sha(launch_path)
            )
        publish(
            logs,
            "process_chain.json",
            dict(
                status="PROCESS_CHAIN_RECORDED"
                if "runtime_launch" in members
                else "RUNTIME_LAUNCH_MISSING_OR_INVALID",
                runtime_root=receipt["runtime_root"],
                members=members,
                independent_audit_pending=True,
            ),
        )
        return code
    except BaseException as exc:
        try:
            publish(
                logs,
                "monitor_failure.json",
                dict(
                    status="MONITOR_FAILURE_PRESERVED",
                    pid=child.pid,
                    error=repr(exc),
                    traceback=traceback.format_exc(),
                    utc=utc(),
                    retry=False,
                ),
            )
        except BaseException:
            pass
        finally:
            if not completed:
                # Never abandon a live child because an observer receipt failed.
                drain_child(child)
        raise


def launch(receipt):
    require(
        receipt["status"]
        == "PASS_MONTHLY_TEST_OPERATIONAL_PREFLIGHT_ONLY_NOT_EXECUTED",
        "Preflight required",
    )
    runtime_review = overlay.absolute(receipt["runtime_review"])
    runtime_root, logs = (
        overlay.absolute(receipt["runtime_root"]),
        overlay.absolute(receipt["logs_root"]),
    )
    require(
        receipt["command"]
        == command(runtime_root, runtime_review, receipt["validation_audit_sha256"]),
        "Fixed wrapper command differs",
    )
    verify_pins(receipt["files"])
    verify_publication(
        receipt["publication_commit"],
        {
            **receipt["publication_files"],
            str(runtime_review): receipt["runtime_review_sha256"],
        },
    )
    runtime = read(runtime_review)
    require(
        overlay.absolute(runtime["launch_binding"]["runtime_root"]) == runtime_root
        and overlay.absolute(runtime["launch_binding"]["logs_root"]) == logs,
        "Runtime destinations differ",
    )
    fresh_roots(runtime_root, logs, runtime_review)
    closed_validation(runtime)
    logs.mkdir(parents=True, exist_ok=False)
    publish(logs, "preflight.json", receipt)
    env = os.environ.copy()
    with (
        (logs / "stdout.log").open("xb") as stdout,
        (logs / "stderr.log").open("xb") as stderr,
    ):
        verify_pins(receipt["files"])
        closed_validation(runtime)
        observed = resources()
        gate(observed)
        # No publication, polling, sleep or alternate command between gate and Popen.
        child = subprocess.Popen(
            receipt["command"],
            cwd=REPO,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # The handle is retained by child; monitor owns it until observed termination.
        try:
            publish(
                logs,
                "admission.json",
                dict(**observed, minimum_free_bytes=MIN_FREE, utc_published=utc()),
            )
        except BaseException:
            drain_child(child)
            raise
        return monitor(child, receipt, logs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-review", type=Path, required=True)
    parser.add_argument("--runtime-review-sha256", required=True)
    parser.add_argument("--expected-validation-audit-sha256", required=True)
    parser.add_argument("--publication-commit", required=True)
    parser.add_argument("--execute-reviewed-monthly-test", action="store_true")
    args = parser.parse_args()
    receipt = preflight(
        args.runtime_review,
        args.runtime_review_sha256,
        args.expected_validation_audit_sha256,
        args.publication_commit,
    )
    if not args.execute_reviewed_monthly_test:
        print(json.dumps(receipt, indent=2))
        return 0
    return launch(receipt)


if __name__ == "__main__":
    raise SystemExit(main())
