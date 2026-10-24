"""One-shot OOF FULL_H1 audit supervision; default metadata check, no science imports."""

from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

CODE = Path(__file__).resolve().parent
REPO = CODE.parents[2]
BASE = Path("D:/GexResearchArtifacts/level_oracle_20261018")
NAME = Path(__file__).name
AUDITOR = "audit_oof_calibrated_policy.py"
AUDIT_REVIEW = "OOF_ECONOMIC_AUDITOR_IMPLEMENTATION_REVIEW_20261023.json"
AUDIT_REVIEW_SHA = "cf7a0659b495ad9bab484839d71c1f4377fb25c5c9df60d772cf0b7667c4d653"
PIPELINE_REVIEW = "OOF_PIPELINE_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json"
PIPELINE_REVIEW_SHA = "a78c2ef9019111a1ca98fa6e2517a4db8ce1ef9877596e5807734ce4c843ec95"
NEW_FILES = (
    NAME,
    "test_launch_oof_economic_audit_20261024.py",
    "OOF_ECONOMIC_AUDIT_LAUNCH_DESIGN_20261024.md",
)
REVIEW_NAME = "OOF_ECONOMIC_AUDIT_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json"
REVIEW_STATUS = "PASS_OOF_ECONOMIC_AUDIT_LAUNCH_IMPLEMENTATION_REVIEW"
BINDING_STATUS = "PASS_OOF_ECONOMIC_AUDIT_LAUNCH_RUNTIME_BINDING"
MONTHS = [f"2026{m:02d}" for m in range(1, 7)]
MIN_FREE = 2_000_000_000
ADAPTER_NAMES = (
    "monthly_oof_calibration_adapter.py",
    "oof_maximum_calibration.py",
    "rolling_monthly_schedule.py",
    "MONTHLY_OOF_CALIBRATION_ADAPTER_SPEC.md",
    "PREQUENTIAL_MAX_CALIBRATION_DESIGN.md",
    "OOF_MAXIMUM_CALIBRATION_INTEGRATION.md",
)
REPLAY_NAMES = (
    *ADAPTER_NAMES,
    "evaluate_oof_calibrated_policy.py",
    "OOF_CALIBRATED_POLICY_EVALUATION_SPEC.md",
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value):
    require(
        isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value),
        "SHA256 required",
    )
    return value


def utc():
    return datetime.now(timezone.utc).isoformat()


def stamp(value):
    result = datetime.fromisoformat(value)
    require(
        result.tzinfo is not None and result.utcoffset().total_seconds() == 0,
        "UTC timezone required",
    )
    return result


def path(value):
    p = Path(value)
    require(p.is_absolute() and ".." not in p.parts, "Absolute path required")
    for part in (p, *p.parents):
        require(
            not part.is_symlink() and not part.is_junction(),
            "Links/junctions forbidden",
        )
    return p.resolve()


def disjoint(left, right):
    return not left.is_relative_to(right) and not right.is_relative_to(left)


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def verify(files):
    for p, expected in files.items():
        require(sha(path(p)) == digest(expected), "Pinned bytes changed: " + str(p))


class Evidence:
    def __init__(self, roots):
        self.roots = tuple(path(p) for p in roots)
        require(
            self.roots and len(set(self.roots)) == len(self.roots),
            "Read roots required/unique",
        )
        require(
            all(
                p.is_dir()
                and p != Path(p.anchor)
                and not BASE.resolve().is_relative_to(p)
                for p in self.roots
            ),
            "Bounded read roots required",
        )
        self.files = {}

    def file(self, p, expected):
        p = path(p)
        require(
            any(p.is_relative_to(r) for r in self.roots), "Authority outside read roots"
        )
        expected = digest(expected)
        require(
            str(p) not in self.files or self.files[str(p)] == expected,
            "Conflicting pin",
        )
        require(sha(p) == expected, "Authority bytes differ")
        self.files[str(p)] = expected
        return p

    def json(self, p, expected):
        p = self.file(p, expected)
        value = read(p)
        require(sha(p) == expected, "Authority changed during read")
        return value

    def ref(self, value):
        require(set(value) == {"path", "sha256"}, "Authority reference schema")
        return self.json(value["path"], value["sha256"])


def publication(commit, files):
    require(
        isinstance(commit, str) and re.fullmatch("[0-9a-f]{40}", commit),
        "Full publication commit required",
    )
    for name, expected in files.items():
        p = path(name)
        require(p.is_relative_to(REPO), "Publication outside repository")
        result = subprocess.run(
            ["git", "show", commit + ":" + p.relative_to(REPO).as_posix()],
            cwd=REPO,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        require(
            hashlib.sha256(result.stdout).hexdigest() == digest(expected),
            "Git bytes differ",
        )


def review_files(evidence):
    science = evidence.json(CODE / AUDIT_REVIEW, AUDIT_REVIEW_SHA)
    require(
        science["status"] == "PASS_OOF_ECONOMIC_AUDITOR_IMPLEMENTATION_REVIEW"
        and science["scope"] == "IMPLEMENTATION_ONLY"
        and science["runtime_authorized"] is False,
        "Auditor review scope",
    )
    frozen = {}
    for field in (
        "reviewed_implementation",
        "frozen_producers",
        "reviewed_design_and_authorities",
    ):
        for name, value in science["binding"][field].items():
            require(
                Path(name).name == name
                and (name not in frozen or frozen[name] == value),
                "Review pin conflict",
            )
            frozen[name] = value
    require(len(frozen) == 13, "Thirteen scientific review pins required")
    previous = evidence.json(CODE / PIPELINE_REVIEW, PIPELINE_REVIEW_SHA)
    require(
        previous["status"] == "PASS_OOF_PIPELINE_LAUNCH_IMPLEMENTATION_REVIEW"
        and previous["decision"] == "CLEAR"
        and len(previous["files"]) == 48,
        "Pipeline review required",
    )
    for name, value in previous["files"].items():
        require(
            Path(name).name == name and (name not in frozen or frozen[name] == value),
            "Previous code pin conflict",
        )
        frozen[name] = value
    for name in NEW_FILES:
        frozen[name] = sha(CODE / name)
    # No repository-local imports are permitted: copied operational primitives only.
    for node in ast.walk(ast.parse((CODE / NAME).read_text(encoding="utf-8"))):
        modules = (
            [a.name for a in node.names]
            if isinstance(node, ast.Import)
            else ([node.module or ""] if isinstance(node, ast.ImportFrom) else [])
        )
        require(
            not any((CODE / (m.split(".")[0] + ".py")).is_file() for m in modules),
            "Local science/helper import forbidden",
        )
    for name, value in frozen.items():
        evidence.file(CODE / name, value)
    return frozen


def command(request, request_sha, output):
    return [
        sys.executable,
        "-u",
        str(CODE / AUDITOR),
        "--request",
        str(request),
        "--request-sha256",
        request_sha,
        "--output",
        str(output),
    ]


def destinations(request, binding, source_request):
    roots = [path(binding[k]) for k in ("output_root", "logs_root")]
    protected = [
        CODE,
        *[path(p) for p in binding["allowed_read_roots"]],
        path(source_request["pipeline_root"]),
        path(source_request["coordination_lock"]),
        BASE / "oof_economic_audit_launch.lock",
        BASE / "oof_pipeline_runtime.lock",
    ]
    protected.extend(
        path(request[k])
        for k in (
            "monthly_root",
            "session_root",
            "correction_root",
            "monthly_audit",
            "session_audit",
        )
    )
    protected.extend(path(m["evaluation_root"]) for m in request["months"])
    require(
        disjoint(*roots)
        and all(
            not r.exists() and all(disjoint(r, p) for p in protected) for r in roots
        ),
        "Fresh disjoint outputs required",
    )
    require(
        all(r.parent == BASE.resolve() for r in roots),
        "Outputs must be direct artifact children",
    )
    return roots


def upstream(request, binding, evidence):
    refs = binding["upstream"]
    require(
        set(refs)
        == {
            "pipeline_request",
            "pipeline_binding",
            "preflight",
            "process",
            "exit",
            "supervisor_completion",
            "pipeline_completion",
        },
        "Upstream reference membership",
    )
    source = evidence.ref(refs["pipeline_request"])
    source_sha = refs["pipeline_request"]["sha256"]
    runtime = evidence.ref(refs["pipeline_binding"])
    pre, opened, ended, finished = (
        evidence.ref(refs[n])
        for n in ("preflight", "process", "exit", "supervisor_completion")
    )
    require(
        source["version"] == "OOF_PIPELINE_RUNTIME_REQUEST_V1"
        and source["status"] == "REVIEWED_OOF_PIPELINE_RUNTIME_REQUEST"
        and source["runtime_authorized"] is True
        and source["months"] == MONTHS
        and len(source["code"]) == 17,
        "Pipeline request schema",
    )
    require(
        runtime["status"] == "PASS_OOF_PIPELINE_LAUNCH_RUNTIME_BINDING"
        and runtime["request"] == refs["pipeline_request"]
        and runtime["implementation_review"]
        == {"path": str(CODE / PIPELINE_REVIEW), "sha256": PIPELINE_REVIEW_SHA},
        "Pipeline runtime authority",
    )
    for name, value in source["code"].items():
        require(
            evidence.files.get(str(CODE / name)) == value, "Pipeline code17 differs"
        )
    previous_review = evidence.json(CODE / PIPELINE_REVIEW, PIPELINE_REVIEW_SHA)
    require(
        source["code"] == previous_review["dependency_sets"]["oof_request"],
        "Exact OOF request17 membership",
    )
    logs = path(runtime["logs_root"])
    for key, filename in (
        ("preflight", "preflight.json"),
        ("process", "process.json"),
        ("exit", "exit.json"),
        ("supervisor_completion", "completion.json"),
    ):
        require(path(refs[key]["path"]) == logs / filename, "Upstream receipt location")
    require(
        pre["status"] == "PASS_OOF_LAUNCH_PREFLIGHT_NOT_EXECUTED"
        and pre["executed"] is False
        and pre["request_sha256"] == source_sha
        and pre["runtime_binding_sha256"] == refs["pipeline_binding"]["sha256"]
        and pre["implementation_review_sha256"] == PIPELINE_REVIEW_SHA,
        "Upstream preflight binding",
    )
    expected_cmd = [
        sys.executable,
        "-u",
        str(CODE / "run_oof_calibrated_pipeline.py"),
        "--request",
        str(path(refs["pipeline_request"]["path"])),
        "--request-sha256",
        source_sha,
    ]
    require(
        pre["command"] == opened["command"] == expected_cmd, "Upstream fixed command"
    )
    require(
        opened["status"] == "PROCESS_HANDLE_RETAINED"
        and ended["status"] == "PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE"
        and opened["creation_time_source"] == "GetProcessTimes_retained_Popen_handle"
        and ended["exit_code_source"] == "GetExitCodeProcess_retained_Popen_handle",
        "Upstream retained handle required",
    )
    require(
        type(opened["pid"]) is int
        and opened["pid"] > 0
        and type(opened["creation_time"]) in (int, float)
        and math.isfinite(opened["creation_time"])
        and opened["creation_time"] > 0
        and type(ended["pid"]) is int
        and type(ended["creation_time"]) in (int, float)
        and ended["pid"] == opened["pid"]
        and ended["creation_time"] == opened["creation_time"]
        and type(ended["exit_code"]) is int
        and ended["exit_code"] == 0,
        "Upstream process identity/exit",
    )
    authority = {
        "request_sha256": source_sha,
        "runtime_binding_sha256": refs["pipeline_binding"]["sha256"],
        "implementation_review_sha256": PIPELINE_REVIEW_SHA,
        "publication_commit": pre["publication_commit"],
        "preflight_sha256": refs["preflight"]["sha256"],
        "monitor_code_sha256": evidence.files[
            str(CODE / "launch_oof_pipeline_20261024.py")
        ],
    }
    require(
        all(opened[k] == v and ended[k] == v for k, v in authority.items())
        and ended["process_receipt_sha256"] == refs["process"]["sha256"],
        "Upstream process chain",
    )
    require(
        finished["status"]
        == "COMPLETE_OOF_PIPELINE_SUPERVISION_PENDING_INDEPENDENT_AUDIT"
        and type(finished["exit_code"]) is int
        and finished["exit_code"] == 0
        and finished["process_files"]
        == {
            str(path(refs[k]["path"])): refs[k]["sha256"]
            for k in ("preflight", "process", "exit")
        }
        and all(
            finished[k] == authority[k]
            for k in (
                "request_sha256",
                "runtime_binding_sha256",
                "implementation_review_sha256",
                "publication_commit",
            )
        )
        and all(
            finished[k] is False
            for k in (
                "auditor_executed",
                "technical_ready",
                "promotion_approved",
                "retry",
            )
        ),
        "Upstream supervision incomplete",
    )
    require(
        stamp(opened["monitor_started_utc"])
        <= stamp(ended["observed_utc"])
        <= stamp(finished["completed_utc"]),
        "Upstream chronology",
    )
    pipeline = path(source["pipeline_root"])
    require(
        path(source["coordination_lock"]) == BASE / "oof_pipeline_runtime.lock",
        "Pipeline global lock differs",
    )
    require(
        path(refs["pipeline_completion"]["path"]) == pipeline / "completion.json",
        "Pipeline completion location",
    )
    complete = evidence.ref(refs["pipeline_completion"])
    compact = finished["pipeline_closure"]["compact_files"]
    expected = {
        str(pipeline / n) for n in ("request.json", "contract.json", "completion.json")
    }
    expected.update(
        str(pipeline / f"{folder}/{i:02d}.json")
        for folder in ("starts", "receipts")
        for i in range(12)
    )
    expected.update(
        str(path(source["correction_root"]) / f"{m}.complete.json") for m in MONTHS
    )
    expected.update(
        str(path(source["evaluation_roots"][m]) / n)
        for m in MONTHS
        for n in ("completion.json", "run_contract.json")
    )
    require(
        set(compact) == expected
        and compact[str(pipeline / "completion.json")]
        == refs["pipeline_completion"]["sha256"],
        "Upstream compact membership",
    )
    values = {p: evidence.json(p, h) for p, h in compact.items()}
    require(
        values[str(pipeline / "request.json")] == source
        and values[str(pipeline / "contract.json")]
        == dict(
            version="OOF_PIPELINE_V1",
            request_sha256=source_sha,
            code=source["code"],
            correction_layout="SHARED_CUMULATIVE",
        ),
        "Pipeline stored request/contract",
    )
    previous, pairs, last_inventory = None, {}, {}
    for i, (month, stage) in enumerate(
        (m, s) for m in MONTHS for s in ("correction", "replay")
    ):
        started = values[str(pipeline / f"starts/{i:02d}.json")]
        receipt = values[str(pipeline / f"receipts/{i:02d}.json")]
        require(
            receipt["status"] == "COMPLETE_OOF_PIPELINE_PHASE"
            and receipt["winner_selected"] is None
            and receipt["independent_audit_pending"] is True
            and receipt["start_sha256"]
            == compact[str(pipeline / f"starts/{i:02d}.json")]
            and all(
                v["request_sha256"] == source_sha
                and v["phase"] == [month, stage]
                and v["previous_receipt_sha256"] == previous
                for v in (started, receipt)
            ),
            "Twelve-phase chain",
        )
        previous = compact[str(pipeline / f"receipts/{i:02d}.json")]
        root = path(
            source["correction_root"]
            if stage == "correction"
            else source["evaluation_roots"][month]
        )
        target = root / (
            f"{month}.complete.json" if stage == "correction" else "completion.json"
        )
        closed = values[str(target)]
        require(
            receipt["completion_sha256"] == compact[str(target)]
            and closed["target_month"] == month
            and closed["winner_selected"] is None,
            "Monthly closure binding",
        )
        names = ADAPTER_NAMES if stage == "correction" else REPLAY_NAMES
        require(
            closed["dependencies"] == {n: source["code"][n] for n in names},
            "Monthly closure dependencies",
        )
        if stage == "correction":
            require(
                closed["status"] == "COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS"
                and closed["monthly_audit_sha256"] == source["monthly_audit"]["sha256"]
                and closed["target_labels_read"] is False
                and closed["base_models_refitted"] is False
                and closed["development_seen"] is True,
                "Correction closure",
            )
            pairs[month] = {"correction_completion_sha256": compact[str(target)]}
        else:
            require(
                closed["status"] == "COMPLETE_FIXED_OOF_POLICY_MONTH", "Replay closure"
            )
            pairs[month]["evaluation_completion_sha256"] = compact[str(target)]
            require(
                values[str(root / "run_contract.json")]
                == dict(
                    version="OOF_POLICY_REPLAY_V1",
                    dependencies=closed["dependencies"],
                    monthly_audit_sha256=source["monthly_audit"]["sha256"],
                    correction_completion_sha256=pairs[month][
                        "correction_completion_sha256"
                    ],
                    target_month=month,
                    threshold=0,
                    winner_selected=None,
                ),
                "Replay authority contract",
            )
        inventory = receipt["output_inventory"]
        roots = [
            path(source["correction_root"]),
            *(path(v) for v in source["evaluation_roots"].values()),
        ]
        require(
            all(
                str(path(p)) == p
                and any(path(p).is_relative_to(r) and path(p) != r for r in roots)
                and digest(h)
                for p, h in inventory.items()
            ),
            "Declared inventory path/pin",
        )
        require(
            all(inventory.get(p) == h for p, h in last_inventory.items())
            and inventory.get(str(target)) == compact[str(target)],
            "Declared inventory progression",
        )
        last_inventory = inventory
    require(
        complete
        == dict(
            status="PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT",
            request_sha256=source_sha,
            last_receipt_sha256=previous,
            months=pairs,
            winner_selected=None,
            technical_ready=False,
            promotion_approved=False,
            auditor_executed=False,
        ),
        "Pipeline final closure",
    )
    inventory_sha = hashlib.sha256(
        json.dumps(last_inventory, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    require(
        finished["pipeline_closure"]["output_count"] == len(last_inventory)
        and finished["pipeline_closure"]["output_inventory_sha256"] == inventory_sha,
        "Declared final inventory binding",
    )
    require(
        request["monthly_root"] == source["monthly_root"]
        and request["session_root"] == source["session_root"]
        and request["correction_root"] == source["correction_root"]
        and request["monthly_audit"] == source["monthly_audit"]["path"]
        and request["monthly_audit_sha256"] == source["monthly_audit"]["sha256"]
        and request["session_audit"] == source["session_audit"]["path"]
        and request["months"]
        == [
            {"month": m, "evaluation_root": source["evaluation_roots"][m], **pairs[m]}
            for m in MONTHS
        ],
        "New audit request differs from closed pipeline",
    )
    evidence.file(request["monthly_audit"], request["monthly_audit_sha256"])
    evidence.file(request["session_audit"], source["session_audit"]["sha256"])
    for root in (
        logs,
        pipeline,
        path(source["correction_root"]),
        *(path(v) for v in source["evaluation_roots"].values()),
    ):
        require(
            not any(
                p.name in ("failure.json", "audit_failure.json")
                or p.name.endswith(".partial")
                for p in root.iterdir()
            ),
            "Upstream failure/partial present",
        )
    controls = {
        str(pipeline / n) for n in ("request.json", "contract.json", "completion.json")
    }
    controls.update(
        str(pipeline / f"{folder}/{i:02d}.json")
        for folder in ("starts", "receipts")
        for i in range(12)
    )
    require(
        {str(path(p)) for p in pipeline.rglob("*") if p.is_file()} == controls,
        "Unexpected pipeline control artifact",
    )
    return source


def preflight(request_path, request_sha, binding_path, binding_sha, review_sha, commit):
    request_path, binding_path = path(request_path), path(binding_path)
    verify({request_path: request_sha, binding_path: binding_sha})
    binding = read(binding_path)
    evidence = Evidence(binding["allowed_read_roots"])
    request = evidence.json(request_path, request_sha)
    evidence.json(binding_path, binding_sha)
    require(
        binding["status"] == BINDING_STATUS
        and binding["request"] == {"path": str(request_path), "sha256": request_sha},
        "Runtime binding/request",
    )
    require(
        set(request)
        == {
            "version",
            "scope",
            "monthly_root",
            "monthly_audit",
            "monthly_audit_sha256",
            "session_root",
            "session_audit",
            "correction_root",
            "months",
        }
        and request["version"] == "OOF_ECONOMIC_AUDIT_REQUEST_V1"
        and request["scope"] == "FULL_H1"
        and [m["month"] for m in request["months"]] == MONTHS,
        "FULL_H1 request required",
    )
    files = review_files(evidence)
    require(
        binding["implementation_review"]
        == {"path": str(CODE / REVIEW_NAME), "sha256": review_sha},
        "External supervisor review pin",
    )
    review = evidence.json(CODE / REVIEW_NAME, review_sha)
    require(
        review["status"] == REVIEW_STATUS
        and review["decision"] == "CLEAR"
        and review["scope"] == "IMPLEMENTATION_ONLY"
        and review["runtime_authorized"] is False
        and review["files"] == files,
        "Supervisor implementation review",
    )
    source = upstream(request, binding, evidence)
    outputs = destinations(request, binding, source)
    published = {str(CODE / n): h for n, h in files.items()}
    published.update(
        {
            str(CODE / AUDIT_REVIEW): AUDIT_REVIEW_SHA,
            str(CODE / PIPELINE_REVIEW): PIPELINE_REVIEW_SHA,
            str(CODE / REVIEW_NAME): review_sha,
            str(request_path): request_sha,
        }
    )
    for key in ("pipeline_request", "pipeline_binding"):
        ref = binding["upstream"][key]
        published[str(path(ref["path"]))] = ref["sha256"]
    require(binding["published_files"] == published, "Exact publication membership")
    published[str(binding_path)] = binding_sha
    publication(commit, published)
    verify(evidence.files)
    return dict(
        status="PASS_OOF_AUDIT_PREFLIGHT_NOT_EXECUTED",
        executed=False,
        request_path=str(request_path),
        request_sha256=request_sha,
        binding_path=str(binding_path),
        binding_sha256=binding_sha,
        implementation_review_sha256=review_sha,
        publication_commit=commit,
        files=evidence.files,
        publication_files=published,
        output_root=str(outputs[0]),
        logs_root=str(outputs[1]),
        command=command(request_path, request_sha, outputs[0]),
        retry=False,
    )


# Operational primitives adapted from published monthly/OOF supervisors. No local imports.
def observation():
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (n, ctypes.c_ulonglong)
            for n in ("total", "ram", "total_commit", "commit", "v", "fv", "ex")
        ]

    value = Memory()
    value.length = ctypes.sizeof(value)
    require(
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)),
        "Windows memory observation failed",
    )
    return dict(available_ram_bytes=value.ram, free_commit_bytes=value.commit)


def gate(value):
    require(
        all(
            type(value.get(k)) is int and value[k] >= MIN_FREE
            for k in ("available_ram_bytes", "free_commit_bytes")
        ),
        "2GB RAM/commit required",
    )


@contextmanager
def lock(p, create):
    import msvcrt

    p = path(p)
    if not create:
        require(p.is_file() and p.stat().st_size > 0, "Existing global lock required")
    before = None if create else sha(p)
    with p.open("a+b" if create else "r+b") as handle:
        if create and p.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    require(before is None or sha(p) == before, "Global lock bytes changed")


def publish(p, value):
    p = Path(p)
    temporary = p.with_suffix(p.suffix + ".partial")
    require(not p.exists() and not temporary.exists(), "Preserve existing receipt")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.rename(p)
    return sha(p)


class RetainedProcess:
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
        require(
            self.kernel.GetProcessTimes(
                self.handle,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ),
            "GetProcessTimes failed",
        )
        return (
            ((created.dwHighDateTime << 32) | created.dwLowDateTime)
            - 116444736000000000
        ) / 10_000_000

    def wait_exit(self):
        observed = self.kernel.WaitForSingleObject(self.handle, 1000)
        if observed == 258:
            return None
        require(observed == 0, "WaitForSingleObject failed")
        value = wintypes.DWORD()
        require(
            self.kernel.GetExitCodeProcess(self.handle, ctypes.byref(value)),
            "GetExitCodeProcess failed",
        )
        self.child.returncode = int(value.value)
        return int(value.value)


def drain(child):
    while True:
        try:
            child.wait()
            return
        except KeyboardInterrupt:
            continue


def monitor(child, receipt, preflight_sha):
    import psutil

    logs = Path(receipt["logs_root"])
    ended, samples, errors = False, 0, []
    peak_rss = peak_private = minimum = None
    started = time.monotonic()
    try:
        retained = RetainedProcess(child)
        created = retained.creation_time()
        authority = dict(
            monitor_code_sha256=receipt["files"][str(CODE / NAME)],
            request_sha256=receipt["request_sha256"],
            binding_sha256=receipt["binding_sha256"],
            implementation_review_sha256=receipt["implementation_review_sha256"],
            publication_commit=receipt["publication_commit"],
            preflight_sha256=preflight_sha,
        )
        process_sha = publish(
            logs / "process.json",
            dict(
                status="PROCESS_HANDLE_RETAINED",
                pid=child.pid,
                creation_time=created,
                creation_time_source="GetProcessTimes_retained_Popen_handle",
                command=receipt["command"],
                monitor_started_utc=utc(),
                **authority,
            ),
        )
        try:
            process = psutil.Process(child.pid)
            require(
                abs(process.create_time() - created) < 0.001, "PID identity differs"
            )
        except (psutil.Error, ValueError) as exc:
            process = None
            errors.append(repr(exc))
        while True:
            code = retained.wait_exit()
            if code is not None:
                ended = True
                break
            try:
                if process is not None:
                    memory = process.memory_info()
                    samples += 1
                    peak_rss, peak_private = (
                        max(peak_rss or 0, memory.rss),
                        max(peak_private or 0, memory.private),
                    )
                current = observation()
                minimum = (
                    current
                    if minimum is None
                    else {k: min(minimum[k], v) for k, v in current.items()}
                )
            except (psutil.Error, OSError, ValueError) as exc:
                errors.append(repr(exc))
        exit_sha = publish(
            logs / "exit.json",
            dict(
                status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE",
                pid=child.pid,
                creation_time=created,
                exit_code=code,
                exit_code_source="GetExitCodeProcess_retained_Popen_handle",
                observed_utc=utc(),
                process_receipt_sha256=process_sha,
                monitor_seconds=time.monotonic() - started,
                sample_count=samples,
                peak_sampled_rss_bytes=peak_rss,
                peak_sampled_private_bytes=peak_private,
                minimum_free_observed=minimum,
                monitor_errors=errors,
                retry=False,
                **authority,
            ),
        )
        return code, {
            str(logs / "process.json"): process_sha,
            str(logs / "exit.json"): exit_sha,
            str(logs / "preflight.json"): preflight_sha,
        }
    finally:
        if not ended:
            drain(child)


def validate_audit(receipt):
    output = path(receipt["output_root"])
    require(
        {p.name for p in output.iterdir()} == {"audit.json"},
        "Unexpected audit output/failure/partial",
    )
    audit_path = path(output / "audit.json")
    audit_sha = sha(audit_path)
    result = read(audit_path)
    require(sha(audit_path) == audit_sha, "Audit changed while reading")
    request = read(receipt["request_path"])
    require(
        result["status"] == "PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_FULL_H1"
        and result["scope"]
        == "OOF_OFFSETS_AND_ECONOMIC_EXECUTION_GIVEN_AUDITED_BASE_SCORES"
        and result["binding"]
        == dict(
            request_sha256=receipt["request_sha256"],
            monthly_audit_sha256=request["monthly_audit_sha256"],
            audited_months=MONTHS,
            correction_root=str(path(request["correction_root"])),
        )
        and [m["target_month"] for m in result["months"]] == MONTHS,
        "Audit FULL_H1 binding",
    )
    require(
        result["winner_selected"] is None
        and result["development_seen"] is True
        and all(
            result[k] is False
            for k in (
                "base_fit_reproduced",
                "base_inference_reproduced",
                "raw_quote_replay",
                "technical_ready",
                "promotion_approved",
            )
        ),
        "Audit interpretation flags",
    )
    require(
        set(result["policies"])
        == {
            m + s
            for m in ("static", "expanding", "rolling12")
            for s in ("__control", "__corrected")
        },
        "Six policies required",
    )
    expected = {
        receipt["request_path"]: receipt["request_sha256"],
        request["monthly_audit"]: request["monthly_audit_sha256"],
        request["session_audit"]: receipt["files"][str(path(request["session_audit"]))],
    }
    for name in (
        AUDITOR,
        "test_audit_oof_calibrated_policy.py",
        "OOF_ECONOMIC_AUDITOR_SPEC_20261023.md",
        "OOF_ECONOMIC_AUDITOR_DESIGN_20261023.md",
        *REPLAY_NAMES,
    ):
        expected[str(CODE / name)] = receipt["files"][str(CODE / name)]
    for m in request["months"]:
        expected[
            str(path(request["correction_root"]) / (m["month"] + ".complete.json"))
        ] = m["correction_completion_sha256"]
        expected[str(path(m["evaluation_root"]) / "completion.json")] = m[
            "evaluation_completion_sha256"
        ]
    require(
        all(
            result["verified_files"].get(str(path(p))) == h for p, h in expected.items()
        ),
        "Audit required evidence membership",
    )
    # Do not rehash economic payloads from verified_files; the frozen child did so.
    return {str(audit_path): audit_sha}


def launch(receipt):
    require(
        receipt["status"] == "PASS_OOF_AUDIT_PREFLIGHT_NOT_EXECUTED",
        "Reviewed preflight required",
    )
    verify(receipt["files"])
    # A late optional monitoring dependency cannot silently change admitted pins.
    import psutil  # noqa: F401

    verify(receipt["files"])
    request, binding = read(receipt["request_path"]), read(receipt["binding_path"])
    with (
        lock(BASE / "oof_economic_audit_launch.lock", True),
        lock(BASE / "oof_pipeline_runtime.lock", False),
    ):
        publication(receipt["publication_commit"], receipt["publication_files"])
        evidence = Evidence(binding["allowed_read_roots"])
        evidence.files.update(receipt["files"])
        source = upstream(request, binding, evidence)
        verify(receipt["files"])
        output, logs = destinations(request, binding, source)
        require(
            str(output) == receipt["output_root"]
            and str(logs) == receipt["logs_root"]
            and receipt["command"]
            == command(
                Path(receipt["request_path"]), receipt["request_sha256"], output
            ),
            "Admitted command/roots changed",
        )
        logs.mkdir(exist_ok=False)
        preflight_sha = publish(logs / "preflight.json", receipt)
        snapshots = {}
        for name in NEW_FILES:
            source_file = CODE / name
            target = logs / name
            target.write_bytes(source_file.read_bytes())
            require(
                sha(target) == receipt["files"][str(source_file)],
                "Operational snapshot differs",
            )
            snapshots[str(target)] = sha(target)
        launch_sha = publish(
            logs / "launch.json",
            dict(
                status="OOF_ECONOMIC_AUDIT_SUPERVISOR_ADMITTED_NOT_SPAWNED",
                request_sha256=receipt["request_sha256"],
                binding_sha256=receipt["binding_sha256"],
                preflight_sha256=preflight_sha,
                snapshots=snapshots,
                command=receipt["command"],
                utc=utc(),
            ),
        )
        snapshots[str(logs / "launch.json")] = launch_sha
        env = os.environ.copy()
        env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        try:
            with (
                (logs / "stdout.log").open("xb") as stdout,
                (logs / "stderr.log").open("xb") as stderr,
            ):
                verify(receipt["files"])
                resources = observation()
                gate(resources)
                child = subprocess.Popen(
                    receipt["command"],
                    cwd=REPO,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                try:
                    publish(
                        logs / "admission.json",
                        dict(**resources, minimum_free_bytes=MIN_FREE, utc=utc()),
                    )
                    code, process_files = monitor(child, receipt, preflight_sha)
                finally:
                    drain(child)
            require(code == 0, "Audit child exit must be zero")
            verify(process_files)
            verify(snapshots)
            verify(receipt["files"])
            path(logs)
            closed = validate_audit(receipt)
            verify(process_files)
            verify(receipt["files"])
            verify(closed)
            publish(
                logs / "completion.json",
                dict(
                    status="COMPLETE_OOF_ECONOMIC_AUDIT_SUPERVISION",
                    exit_code=0,
                    request_sha256=receipt["request_sha256"],
                    binding_sha256=receipt["binding_sha256"],
                    implementation_review_sha256=receipt[
                        "implementation_review_sha256"
                    ],
                    publication_commit=receipt["publication_commit"],
                    closure_files={**process_files, **snapshots, **closed},
                    completed_utc=utc(),
                    technical_ready=False,
                    promotion_approved=False,
                    retry=False,
                ),
            )
            return 0
        except BaseException as exc:
            publish(
                logs / "failure.json",
                dict(
                    status="FAILED_OR_INTERRUPTED_PRESERVED",
                    error=repr(exc),
                    utc=utc(),
                    retry=False,
                ),
            )
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "request",
        "request-sha256",
        "runtime-binding",
        "runtime-binding-sha256",
        "implementation-review-sha256",
        "publication-commit",
    ):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--execute-reviewed-audit", action="store_true")
    args = parser.parse_args()
    receipt = preflight(
        args.request,
        args.request_sha256,
        args.runtime_binding,
        args.runtime_binding_sha256,
        args.implementation_review_sha256,
        args.publication_commit,
    )
    if args.execute_reviewed_audit:
        return launch(receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
