"""One-shot FULL_H1 audit supervisor for an explicitly stopped and resumed OOF chain."""

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
PIPELINE_REVIEW = (
    "OOF_TRANSITIVE_SOURCE_V2R1_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json"
)
PIPELINE_REVIEW_SHA = "2782b686947c9ddd5f723ad2b279802d21f3adbbee79aa76a6cd6e8bce551a78"
WRAPPER_REVIEW = (
    "OOF_TRANSITIVE_SOURCE_V2R1_RUNTIME_IMPLEMENTATION_REVIEW_20261024.json"
)
WRAPPER_REVIEW_SHA = "7431a6df11966c46ce5aa66bac5d707b7dfe9e131f59366df24f0f2f66c222c9"
ADDITIONAL_AUTHORITIES = {
    WRAPPER_REVIEW: WRAPPER_REVIEW_SHA,
    "OOF_TRANSITIVE_SOURCE_V2_SCIENTIFIC_INVARIANCE_REVIEW_20261024.json": "47dc8ecaf527a94fc227dd5e42c99c6ea4e7fa7cb5e354c32bc417ae0aab0fe5",
    "OOF_TRANSITIVE_SOURCE_V2_IMPLEMENTATION_CONTRACT_20261024.md": "85c8bd20107e6a2ee6cf0d6e00bb8d16a7d6b5d1c6bce5839f542266e4c17a8c",
    "OOF_ECONOMIC_AUDIT_V2_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json": "211b64f7be7d8829eb8161f2853b390a1ade9c67cad2dea4040e4ea78c785556",
}
ORIGINAL_PROVENANCE = {
    "launch_oof_economic_audit_v2_20261024.py": "71decd9f97e40029dd4311fb5db3e59e7a68b569bca0fe5a80346bd8ccff69b6",
    "test_launch_oof_economic_audit_v2_20261024.py": "c43bc15886b2d9f1ab2ed46e5600fb97de8ecf27f0bdd61d957ba7e8e41be90d",
    "OOF_ECONOMIC_AUDIT_V2_LAUNCH_CONTRACT_20261024.md": "ce60993785b5d551827ecf5ad256e8ecb91567a3e8907fb08d1633b6c68acf11",
}
NEW_FILES = (
    NAME,
    "test_launch_oof_economic_audit_user_stop_continuation_20261029.py",
    "OOF_USER_STOP_CONTINUATION_DESIGN_20261029.md",
)
REVIEW_NAME = "OOF_ECONOMIC_AUDIT_USER_STOP_IMPLEMENTATION_REVIEW_20261029.json"
REVIEW_STATUS = "PASS_OOF_ECONOMIC_AUDIT_USER_STOP_IMPLEMENTATION_REVIEW"
BINDING_STATUS = "PASS_OOF_ECONOMIC_AUDIT_USER_STOP_RUNTIME_BINDING"
CONTINUATION_CODE = "launch_oof_pipeline_user_stop_continuation_20261029.py"
CONTINUATION_TEST = "test_launch_oof_pipeline_user_stop_continuation_20261029.py"
CONTINUATION_REVIEW = "OOF_USER_STOP_CONTINUATION_IMPLEMENTATION_REVIEW_20261029.json"
DESIGN_REVIEW = "OOF_USER_STOP_CONTINUATION_DESIGN_REVIEW_20261029.json"
ORIGINAL_AUDIT_REVIEW = "OOF_ECONOMIC_AUDIT_V2R1_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json"
ORIGINAL_REQUEST_PATH = CODE / "OOF_PIPELINE_V2R1_RUNTIME_REQUEST_20261024_01.json"
ORIGINAL_REQUEST_SHA = "37f2018c7145d3b82cba2e34fbff9ae3008e33f32b004c5580e433157f38ef15"
ORIGINAL_BINDING_PATH = CODE / "OOF_PIPELINE_V2R1_LAUNCH_RUNTIME_BINDING_20261024_01.json"
ORIGINAL_BINDING_SHA = "9e4949227dfd8b0aa3e72a35271b081413dbd9dee482b79c98911ea25478813c"
ORIGINAL_FAILURE_SHA = "798543125e9917d468a225018ad02c639309f63bf16bda0d5ffc2ad96d8427c6"
ORIGINAL_STOP_SHA = "fa8690ceee3f55f06107cf8802db8abab27171707246d6a57bed3d2f1c5b287a"
ORIGINAL_POST_STOP_SHA = "021be4945dbee80dac1caf08f073e097c33595353c22e7e83fb4dad433644032"
SOURCE_SHA = "ec2f728baf2ab28adaaf3855847d74bf6354ac587d440afb83b50278e5ca3234"
TAIL_SHA = "e5dfb3505d3e8e621d91e6ef46dcffd89380a3aa62f13cbc1a37b3816747110e"
REMAINING = [[m, st] for m in ("202605", "202606") for st in ("correction", "replay")]
CONTINUATION_REQUEST_KEYS = {"version", "status", "runtime_authorized", "original_request", "original_binding", "authorization", "snapshot_manifest", "independent_prefix_review", "stopped_launch", "expected_completed_phases", "adopted_phases", "tail_receipt_sha256", "source_admission_sha256", "remaining_phases", "preserved_root_locks"}
CONTINUATION_BINDING_KEYS = {"version", "status", "request", "implementation_review", "published_files", "allowed_read_roots", "logs_root", "observer_root", "snapshot_root", "repository_snapshot_root", "future_audit_root", "future_audit_logs_root"}

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
    if p.is_file():
        require(p.stat().st_nlink == 1, "Hardlink authority forbidden")
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
    wrapper = evidence.json(CODE / WRAPPER_REVIEW, WRAPPER_REVIEW_SHA)
    require(
        wrapper["status"]
        == "PASS_OOF_TRANSITIVE_SOURCE_V2R1_RUNTIME_IMPLEMENTATION_REVIEW"
        and wrapper["decision"] == "CLEAR"
        and wrapper["scope"] == "IMPLEMENTATION_ONLY"
        and wrapper["runtime_authorized"] is False
        and len(wrapper["binding"]["runtime_dependency_map"]) == 18,
        "Wrapper V2R1 review required",
    )
    previous = evidence.json(CODE / PIPELINE_REVIEW, PIPELINE_REVIEW_SHA)
    require(
        previous["status"]
        == "PASS_OOF_TRANSITIVE_SOURCE_V2R1_LAUNCH_IMPLEMENTATION_REVIEW"
        and previous["decision"] == "CLEAR"
        and previous["scope"] == "IMPLEMENTATION_ONLY"
        and previous["runtime_authorized"] is False,
        "Pipeline V2R1 supervisor review required",
    )
    for mapping in (
        wrapper["binding"]["runtime_dependency_map"],
        previous["files"],
        ADDITIONAL_AUTHORITIES,
        ORIGINAL_PROVENANCE,
    ):
        for name, value in mapping.items():
            require(
                Path(name).name == name
                and (name not in frozen or frozen[name] == value),
                "V2R1/provenance pin conflict",
            )
            frozen[name] = value
    preserved = {
        "launch_oof_economic_audit_v2r1_20261024.py": "93ad3efcc124099ea2a8e4f8c64995671e1922e5ce1974c9f07b3fa02cd3ce1a",
        "test_launch_oof_economic_audit_v2r1_20261024.py": "90e2125bc62c8ff2faf93ea3f380996757afde1dc40a9d09f6bea77645ff54ee",
        ORIGINAL_AUDIT_REVIEW: "fbbeebd2f0f7bbd1a7dd697df5cd6bd9acc6e7da5bf9ebb9b55b1e76aeee059f",
        DESIGN_REVIEW: "ad2ab016a45c769c3fb849a25e63173c0510f6577f7c5cd20beac867ebd414f6",
        "OOF_USER_STOP_CONTINUATION_DESIGN_20261029.md": "ae9d7466aa09f2c43e694fca86a5216d3222e0cff0042b035d7c8d057f54d109",
    }
    continuation = evidence.json(CODE / CONTINUATION_REVIEW, sha(CODE / CONTINUATION_REVIEW))
    require(continuation["status"] == "PASS_OOF_USER_STOP_CONTINUATION_IMPLEMENTATION_REVIEW"
        and continuation["decision"] == "CLEAR" and continuation["scope"] == "IMPLEMENTATION_ONLY"
        and continuation["runtime_authorized"] is False
        and continuation["cpu0_inheritance_test"]["status"] == "PASS_FIRST_INSTRUCTION_CPU0_THREADS1"
        and {CONTINUATION_CODE, CONTINUATION_TEST} <= set(continuation["files"]),
        "Reviewed continuation implementation required")
    for mapping in (preserved, continuation["files"]):
        for name, value in mapping.items():
            require(Path(name).name == name and (name not in frozen or frozen[name] == value), "Continuation pin conflict")
            frozen[name] = value
    frozen[CONTINUATION_REVIEW] = sha(CODE / CONTINUATION_REVIEW)
    for name in NEW_FILES:
        value = sha(CODE / name)
        require(name not in frozen or frozen[name] == value, "New authority pin conflict")
        frozen[name] = value
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


def process_chain(pre, opened, ended, refs, authority, expected_command, exit_code):
    require(opened["status"] == "PROCESS_HANDLE_RETAINED"
        and ended["status"] == "PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE"
        and opened["creation_time_source"] == "GetProcessTimes_retained_Popen_handle"
        and ended["exit_code_source"] == "GetExitCodeProcess_retained_Popen_handle", "Retained process evidence required")
    require(type(opened["pid"]) is int and opened["pid"] > 0
        and type(opened["creation_time"]) in (int, float) and math.isfinite(opened["creation_time"])
        and opened["creation_time"] > 0 and type(ended["pid"]) is int
        and type(ended["creation_time"]) in (int, float)
        and ended["pid"] == opened["pid"] and ended["creation_time"] == opened["creation_time"]
        and type(ended["exit_code"]) is int and ended["exit_code"] == exit_code,
        "Retained process identity/exit differs")
    require(pre["command"] == opened["command"] == expected_command
        and all(opened[k] == v and ended[k] == v for k, v in authority.items())
        and ended["process_receipt_sha256"] == refs["process"]["sha256"], "Process authority chain differs")
    begin, end = opened["creation_time"], stamp(ended["observed_utc"]).timestamp()
    require(begin <= stamp(opened["monitor_started_utc"]).timestamp() <= end, "Process chronology differs")
    return begin, end


def no_unknown_failures(roots, exemption, evidence):
    allowed = path(exemption["path"])
    require(exemption["sha256"] == ORIGINAL_FAILURE_SHA, "Exact stopped failure hash required")
    evidence.file(allowed, ORIGINAL_FAILURE_SHA)
    for root in roots:
        for item in path(root).rglob("*"):
            path(item)
            if item.name in ("failure.json", "audit_failure.json") or item.name.endswith(".partial"):
                require(item == allowed and sha(item) == ORIGINAL_FAILURE_SHA, "Unknown upstream failure/partial")


def stopped_chain(operational, source, runtime, evidence):
    refs = operational["stopped_launch"]
    require(set(refs) == {"preflight", "process", "exit", "failure", "user_stop", "post_stop_verification"}, "Exact stopped chain required")
    logs = path(runtime["logs_root"])
    observer = BASE / "oof_pipeline_v2r1_observer_20261024_01"
    for name, value in refs.items():
        require(path(value["path"]) == (observer if name in ("user_stop", "post_stop_verification") else logs) / (name + ".json"), "Stopped receipt path differs")
    require(refs["failure"]["sha256"] == ORIGINAL_FAILURE_SHA
        and refs["user_stop"]["sha256"] == ORIGINAL_STOP_SHA
        and refs["post_stop_verification"]["sha256"] == ORIGINAL_POST_STOP_SHA, "Frozen stop evidence differs")
    pre, proc, ended, failure, stop, post = (evidence.ref(refs[n]) for n in ("preflight", "process", "exit", "failure", "user_stop", "post_stop_verification"))
    expected_command = [sys.executable, "-u", str(CODE / "run_oof_calibrated_pipeline_v2r1.py"), "--request", str(ORIGINAL_REQUEST_PATH), "--request-sha256", ORIGINAL_REQUEST_SHA]
    require(pre["status"] == "PASS_OOF_LAUNCH_PREFLIGHT_NOT_EXECUTED" and pre["executed"] is False
        and pre["request_sha256"] == ORIGINAL_REQUEST_SHA and pre["runtime_binding_sha256"] == ORIGINAL_BINDING_SHA
        and pre["implementation_review_sha256"] == PIPELINE_REVIEW_SHA and pre["source_admission_sha256"] == SOURCE_SHA,
        "Original preflight authority differs")
    authority = dict(monitor_code_sha256=evidence.files[str(CODE / "launch_oof_pipeline_v2r1_20261024.py")], request_sha256=ORIGINAL_REQUEST_SHA,
        runtime_binding_sha256=ORIGINAL_BINDING_SHA, implementation_review_sha256=PIPELINE_REVIEW_SHA,
        publication_commit=pre["publication_commit"], preflight_sha256=refs["preflight"]["sha256"])
    interval = process_chain(pre, proc, ended, refs, authority, expected_command, 15)
    require(failure["status"] == "FAILED_OR_INTERRUPTED_PRESERVED" and failure["retry"] is False
        and failure["error"] == "ValueError('OOF child must exit zero')" and not (logs / "completion.json").exists(), "Preserved original failure differs")
    require(stop["status"] == "STOPPED_BY_EXPLICIT_USER_REQUEST" and stop["automatic_resume"] is False
        and stop["artifacts_preserved"] is True and stop["remaining_known_research_processes"] == [], "Explicit user stop required")
    identities = [p for p in stop["identities_before_stop"] if p["pid"] == proc["pid"]]
    require(len(identities) == 1 and identities[0]["command"] == expected_command
        and type(identities[0]["creation"]) in (int, float) and math.isfinite(identities[0]["creation"])
        and abs(identities[0]["creation"] - proc["creation_time"]) <= 1e-6, "Stopped process identity differs")
    names = [f"{i:02d}.json" for i in range(8)]
    require(post["remaining_research_python_pids"] == [] and post["phase_receipts"] == names and post["phase_starts"] == names
        and post["pipeline_completion_exists"] is False and post["supervisor_exit_exists"] is True
        and post["supervisor_failure_exists"] is True, "Post-stop verification differs")
    require(interval[1] <= stamp(failure["utc"]).timestamp() <= stamp(stop["utc"]).timestamp() <= stamp(post["utc"]).timestamp(), "Stop chronology differs")
    no_unknown_failures((logs, observer), refs["failure"], evidence)
    return interval, stamp(post["utc"]).timestamp()


def validate_snapshot(operational, runtime, pre, evidence):
    snapshot = evidence.ref(operational["snapshot_manifest"])
    require(set(snapshot) == {"version", "status", "copies", "original_files", "output_inventory", "control_inventory", "preserved_root_locks"}, "Snapshot schema differs")
    require(snapshot["output_inventory"] == pre["baseline"]["outputs"]
        and snapshot["control_inventory"] == pre["baseline"]["controls"]
        and snapshot["preserved_root_locks"] == pre["baseline"]["locks"] == operational["preserved_root_locks"]
        and len(snapshot["preserved_root_locks"]) == 5, "Adopted snapshot baseline differs")
    originals = snapshot["original_files"]
    required = {v["path"]: v["sha256"] for v in operational["stopped_launch"].values()}
    for adopted in operational["adopted_phases"]:
        required.update({adopted[k]["path"]: adopted[k]["sha256"] for k in ("start", "receipt", "closure")})
    required.update(operational["preserved_root_locks"])
    require(all(originals.get(p) == h for p, h in required.items()), "Snapshot omits adopted original")
    for p, h in originals.items(): evidence.file(p, h)
    groups = {p: set() for p in originals}
    destinations_seen = set()
    roots = (path(runtime["snapshot_root"]), path(runtime["repository_snapshot_root"]))
    require(disjoint(*roots), "Snapshot copy roots overlap")
    for pair in snapshot["copies"]:
        require(set(pair) == {"original", "copy", "sha256", "size"} and pair["original"] in originals
            and originals[pair["original"]] == pair["sha256"] and type(pair["size"]) is int, "Snapshot pair differs")
        copy = path(pair["copy"])
        group = [i for i, root in enumerate(roots) if copy.is_relative_to(root)]
        require(len(group) == 1 and group[0] not in groups[pair["original"]] and str(copy) not in destinations_seen, "Snapshot group/duplicate differs")
        evidence.file(copy, pair["sha256"])
        require(copy.stat().st_size == path(pair["original"]).stat().st_size == pair["size"], "Snapshot size differs")
        groups[pair["original"]].add(group[0]); destinations_seen.add(str(copy))
    require(all(value == {0, 1} for value in groups.values()), "Both snapshot copies required")
    return snapshot


def validate_phase_lifetimes(source, operational, values, compact, stopped_interval, continued_interval, envelope):
    pipeline = path(source["pipeline_root"])
    previous = {"old": stopped_interval[0], "new": continued_interval[0]}
    expected_new = []
    for i, (month, stage) in enumerate((m, st) for m in MONTHS for st in ("correction", "replay")):
        start_path, receipt_path = str(pipeline / f"starts/{i:02d}.json"), str(pipeline / f"receipts/{i:02d}.json")
        start = values[start_path]
        interval = stopped_interval if i < 8 else continued_interval
        key = "old" if i < 8 else "new"
        when = stamp(start["started_at_utc"]).timestamp()
        require(previous[key] <= when <= interval[1], "Phase outside retained process lifetime")
        previous[key] = when
        entry = dict(phase=[month, stage], start=dict(path=start_path, sha256=compact[start_path]), receipt=dict(path=receipt_path, sha256=compact[receipt_path]))
        if i < 8:
            target = path(source["correction_root"]) / (month + ".complete.json") if stage == "correction" else path(source["evaluation_roots"][month]) / "completion.json"
            require(operational["adopted_phases"][i] == dict(**entry, closure=dict(path=str(target), sha256=compact[str(target)])), "Adopted phase pin differs")
        else: expected_new.append(entry)
    require(envelope["new_phases"] == expected_new and envelope["baseline_preserved"] is True, "Exactly four new phases required")
    require(compact[str(pipeline / "receipts/07.json")] == operational["tail_receipt_sha256"] == TAIL_SHA, "Preserved tail differs")


def upstream(request, binding, evidence):
    refs = binding["upstream"]
    require(set(refs) == {"pipeline_request", "pipeline_binding", "continuation_request", "continuation_binding", "continuation_review", "preflight", "process", "exit", "supervisor_completion", "pipeline_completion"}, "Exact two-chain upstream membership required")
    require(refs["pipeline_request"] == dict(path=str(ORIGINAL_REQUEST_PATH), sha256=ORIGINAL_REQUEST_SHA)
        and refs["pipeline_binding"] == dict(path=str(ORIGINAL_BINDING_PATH), sha256=ORIGINAL_BINDING_SHA), "Frozen original request/binding required")
    source, original = (evidence.ref(refs[n]) for n in ("pipeline_request", "pipeline_binding"))
    operational, runtime, review = (evidence.ref(refs[n]) for n in ("continuation_request", "continuation_binding", "continuation_review"))
    require(source["version"] == "OOF_PIPELINE_RUNTIME_REQUEST_V2R1" and source["status"] == "REVIEWED_OOF_PIPELINE_RUNTIME_REQUEST"
        and source["runtime_authorized"] is True and source["months"] == MONTHS and len(source["code"]) == 18, "Original request18 required")
    wrapper = evidence.json(CODE / WRAPPER_REVIEW, WRAPPER_REVIEW_SHA)
    require(source["code"] == wrapper["binding"]["runtime_dependency_map"] and all(evidence.files.get(str(CODE / n)) == h for n, h in source["code"].items()), "Exact original request18 membership")
    require(original["status"] == "PASS_OOF_TRANSITIVE_SOURCE_V2R1_LAUNCH_RUNTIME_BINDING" and original["request"] == refs["pipeline_request"]
        and original["implementation_review"] == dict(path=str(CODE / PIPELINE_REVIEW), sha256=PIPELINE_REVIEW_SHA), "Original binding differs")
    require(set(operational) == CONTINUATION_REQUEST_KEYS and operational["version"] == "OOF_USER_STOP_CONTINUATION_REQUEST_V1"
        and operational["status"] == "REVIEWED_OOF_USER_STOP_CONTINUATION_REQUEST" and operational["runtime_authorized"] is True
        and operational["original_request"] == refs["pipeline_request"] and operational["original_binding"] == refs["pipeline_binding"]
        and operational["source_admission_sha256"] == binding["source_admission_sha256"] == SOURCE_SHA
        and type(operational["expected_completed_phases"]) is int and operational["expected_completed_phases"] == 8
        and len(operational["adopted_phases"]) == 8 and operational["remaining_phases"] == REMAINING
        and operational["tail_receipt_sha256"] == TAIL_SHA, "Exact eight-phase adoption authority required")
    require(set(runtime) == CONTINUATION_BINDING_KEYS and runtime["version"] == "OOF_USER_STOP_CONTINUATION_BINDING_V1"
        and runtime["status"] == "PASS_OOF_USER_STOP_CONTINUATION_RUNTIME_BINDING"
        and runtime["request"] == refs["continuation_request"] and runtime["implementation_review"] == refs["continuation_review"]
        and refs["continuation_review"]["path"] == str(CODE / CONTINUATION_REVIEW)
        and evidence.files[str(CODE / CONTINUATION_REVIEW)] == refs["continuation_review"]["sha256"], "Continuation review/binding differs")
    require(review["status"] == "PASS_OOF_USER_STOP_CONTINUATION_IMPLEMENTATION_REVIEW" and review["decision"] == "CLEAR"
        and review["scope"] == "IMPLEMENTATION_ONLY" and review["runtime_authorized"] is False
        and all(evidence.files.get(str(CODE / n)) == h for n, h in review["files"].items()), "Continuation implementation review differs")
    authorization = operational["authorization"]
    require(path(authorization["path"]) == CODE / "RESUMPTION_20261029.md", "Current resumption authority required")
    evidence.file(authorization["path"], authorization["sha256"])
    independent = evidence.ref(operational["independent_prefix_review"])
    require(independent["decision"] == "CLEAR" and independent["runtime_authorized"] is False, "Independent prefix review required")
    stopped_interval, stopped_after = stopped_chain(operational, source, original, evidence)
    logs = path(runtime["logs_root"])
    require(logs == BASE / "oof_pipeline_user_stop_continuation_launch_20261029_01"
        and path(binding["output_root"]) == path(runtime["future_audit_root"]) == BASE / "oof_economic_audit_user_stop_continuation_20261029_01"
        and path(binding["logs_root"]) == path(runtime["future_audit_logs_root"]) == BASE / "oof_economic_audit_user_stop_continuation_launch_20261029_01", "Exact continuation/audit destinations required")
    for key, filename in (("preflight", "preflight.json"), ("process", "process.json"), ("exit", "exit.json"), ("supervisor_completion", "completion.json")):
        require(path(refs[key]["path"]) == logs / filename, "Continuation receipt location differs")
    pre, opened, ended, finished = (evidence.ref(refs[n]) for n in ("preflight", "process", "exit", "supervisor_completion"))
    require(pre["status"] == "PASS_OOF_USER_STOP_CONTINUATION_PREFLIGHT_NOT_EXECUTED" and pre["executed"] is False
        and pre["request_sha256"] == refs["continuation_request"]["sha256"] and pre["runtime_binding_sha256"] == refs["continuation_binding"]["sha256"]
        and pre["implementation_review_sha256"] == refs["continuation_review"]["sha256"]
        and pre["source_admission_sha256"] == SOURCE_SHA and pre["cpu0_inheritance_test"] == review["cpu0_inheritance_test"], "Continuation preflight differs")
    authority = dict(request_sha256=refs["continuation_request"]["sha256"], runtime_binding_sha256=refs["continuation_binding"]["sha256"],
        implementation_review_sha256=refs["continuation_review"]["sha256"], publication_commit=pre["publication_commit"],
        preflight_sha256=refs["preflight"]["sha256"], monitor_code_sha256=evidence.files[str(CODE / CONTINUATION_CODE)])
    expected_command = [sys.executable, "-u", str(CODE / "run_oof_calibrated_pipeline_v2r1.py"), "--request", str(ORIGINAL_REQUEST_PATH), "--request-sha256", ORIGINAL_REQUEST_SHA, "--resume"]
    continued_interval = process_chain(pre, opened, ended, refs, authority, expected_command, 0)
    require(stopped_after <= continued_interval[0] and opened["child_cpu_affinity"] == [0], "Continuation chronology/CPU0 differs")
    require(finished["status"] == "COMPLETE_OOF_USER_STOP_CONTINUATION_PENDING_INDEPENDENT_AUDIT"
        and type(finished["exit_code"]) is int and finished["exit_code"] == 0
        and finished["process_files"] == {refs[k]["path"]: refs[k]["sha256"] for k in ("preflight", "process", "exit")}
        and all(finished[k] == authority[k] for k in ("request_sha256", "runtime_binding_sha256", "implementation_review_sha256", "publication_commit"))
        and all(finished[k] is False for k in ("auditor_executed", "technical_ready", "promotion_approved", "retry"))
        and finished["winner_selected"] is None and finished["stopped_launch"] == operational["stopped_launch"]
        and finished["adopted_phases"] == operational["adopted_phases"] and finished["snapshot_manifest"] == operational["snapshot_manifest"]
        and finished["source_admission_sha256"] == SOURCE_SHA
        and continued_interval[1] <= stamp(finished["completed_utc"]).timestamp(), "Continuation completion differs")
    snapshot = validate_snapshot(operational, runtime, pre, evidence)
    envelope = finished["pipeline_closure"]
    require(set(envelope) == {"original_validation", "new_phases", "baseline_preserved"}, "Final closure envelope differs")
    closure = envelope["original_validation"]
    require(closure["source_admission_sha256"] == SOURCE_SHA, "Final source admission differs")
    final_source = validate_closed_pipeline(request, source, evidence, refs, logs, closure, SOURCE_SHA, operational, stopped_interval, continued_interval, envelope)
    final_inventory = read(path(source["pipeline_root"]) / "receipts/11.json")["output_inventory"]
    require(all(final_inventory.get(p) == h for p, h in snapshot["output_inventory"].items()), "Adopted outputs not preserved in final inventory")
    require(all(closure["compact_files"].get(p) == h for p, h in snapshot["control_inventory"].items()), "Adopted controls changed")
    no_unknown_failures((logs, path(source["pipeline_root"]), path(source["correction_root"]), *(path(v) for v in source["evaluation_roots"].values())), operational["stopped_launch"]["failure"], evidence)
    return final_source


def validate_closed_pipeline(request, source, evidence, refs, logs, closure, admission_sha, operational, stopped_interval, continued_interval, closure_envelope):
    source_sha = refs["pipeline_request"]["sha256"]
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
    compact = closure["compact_files"]
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
            version="OOF_PIPELINE_V2R1",
            request_sha256=source_sha,
            code=source["code"],
            correction_layout="SHARED_CUMULATIVE",
            source_admission_sha256=admission_sha,
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
    validate_phase_lifetimes(source, operational, values, compact, stopped_interval, continued_interval, closure_envelope)
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
        closure["output_count"] == len(last_inventory)
        and closure["output_inventory_sha256"] == inventory_sha,
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
    require(os.name == "nt" and sys.flags.optimize == 0 and not os.environ.get("PYTHONOPTIMIZE"), "Unoptimized Windows required")
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
        and review["files"] == files
        and review["cpu0_inheritance_test"]["status"] == "PASS_FIRST_INSTRUCTION_CPU0_THREADS1",
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
    for key in ("pipeline_request", "pipeline_binding", "continuation_request", "continuation_binding", "continuation_review"):
        ref = binding["upstream"][key]
        published[str(path(ref["path"]))] = ref["sha256"]
    require(binding["published_files"] == published, "Exact publication membership")
    published[str(binding_path)] = binding_sha
    publication(commit, published)
    verify(evidence.files)
    return dict(
        status="PASS_OOF_USER_STOP_AUDIT_PREFLIGHT_NOT_EXECUTED",
        executed=False,
        request_path=str(request_path),
        request_sha256=request_sha,
        binding_path=str(binding_path),
        binding_sha256=binding_sha,
        source_admission_sha256=binding["source_admission_sha256"],
        implementation_review_sha256=review_sha,
        publication_commit=commit,
        files=evidence.files,
        publication_files=published,
        output_root=str(outputs[0]),
        logs_root=str(outputs[1]),
        command=command(request_path, request_sha, outputs[0]),
        cpu0_inheritance_test=review["cpu0_inheritance_test"],
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


def establish_cpu0():
    import psutil
    process = psutil.Process()
    previous = process.cpu_affinity()
    process.cpu_affinity([0])
    require(process.cpu_affinity() == [0], "CPU0 affinity must be imposed before Popen")
    return dict(parent_pid=os.getpid(), parent_cpu_affinity=[0], previous_parent_cpu_affinity=previous,
        mechanism="Windows_child_inherits_parent_affinity_at_CreateProcess", verified_utc=utc())


def child_environment():
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONUTF8="1")
    return env


def monitor(child, receipt, preflight_sha):
    import psutil

    logs = Path(receipt["logs_root"])
    ended, samples, errors, safety_errors = False, 0, [], []
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
        process, affinity = None, None
        try:
            process = psutil.Process(child.pid)
            require(abs(process.create_time() - created) <= 1e-6, "Child retained identity differs")
            affinity = process.cpu_affinity()
            require(affinity == [0], "Child did not inherit CPU0")
        except (psutil.Error, OSError, ValueError) as exc:
            safety_errors.append(repr(exc))
            process = None
        process_sha = publish(logs / "process.json", dict(
            status="PROCESS_HANDLE_RETAINED", pid=child.pid, creation_time=created,
            creation_time_source="GetProcessTimes_retained_Popen_handle", command=receipt["command"],
            child_cpu_affinity=affinity, child_identity_affinity_errors=list(safety_errors),
            monitor_started_utc=utc(), **authority))
        while True:
            code = retained.wait_exit()
            if code is not None:
                ended = True
                break
            if process is not None:
                try:
                    require(process.cpu_affinity() == [0], "Child CPU affinity drift")
                except (psutil.Error, OSError, ValueError) as exc:
                    safety_errors.append(repr(exc))
                    process = None
            try:
                if process is not None:
                    memory = process.memory_info()
                    samples += 1
                    peak_rss, peak_private = max(peak_rss or 0, memory.rss), max(peak_private or 0, memory.private)
                current = observation()
                minimum = current if minimum is None else {k: min(minimum[k], v) for k, v in current.items()}
            except (psutil.Error, OSError, ValueError) as exc:
                errors.append(repr(exc))
        exit_sha = publish(logs / "exit.json", dict(
            status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE", pid=child.pid, creation_time=created,
            exit_code=code, exit_code_source="GetExitCodeProcess_retained_Popen_handle", observed_utc=utc(),
            process_receipt_sha256=process_sha, monitor_seconds=time.monotonic() - started, sample_count=samples,
            peak_sampled_rss_bytes=peak_rss, peak_sampled_private_bytes=peak_private,
            minimum_free_observed=minimum, monitor_errors=errors, child_identity_affinity_errors=safety_errors,
            retry=False, **authority))
        require(not safety_errors, "Child identity/affinity could not be verified; retained exit preserved")
        return code, {str(logs / "process.json"): process_sha, str(logs / "exit.json"): exit_sha,
            str(logs / "preflight.json"): preflight_sha}
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
        receipt["status"] == "PASS_OOF_USER_STOP_AUDIT_PREFLIGHT_NOT_EXECUTED",
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
        env = child_environment()
        try:
            with (
                (logs / "stdout.log").open("xb") as stdout,
                (logs / "stderr.log").open("xb") as stderr,
            ):
                verify(receipt["files"])
                affinity = establish_cpu0()
                resources = observation()
                gate(resources)
                publish(logs / "admission.json", dict(**resources, minimum_free_bytes=MIN_FREE, utc=utc(),
                    **affinity, cpu0_inheritance_test=receipt["cpu0_inheritance_test"]))
                require(psutil.Process().cpu_affinity() == [0], "Parent CPU affinity changed before Popen")
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
            verify(snapshots)
            publish(
                logs / "completion.json",
                dict(
                    status="COMPLETE_OOF_ECONOMIC_AUDIT_USER_STOP_SUPERVISION",
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
