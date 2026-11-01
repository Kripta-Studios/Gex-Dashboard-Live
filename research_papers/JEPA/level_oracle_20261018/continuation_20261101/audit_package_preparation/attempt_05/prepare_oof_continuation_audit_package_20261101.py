"""Build the reviewed FULL_H1 audit request/binding only after real OOF closure.

Default invocation is read-only and reports whether the five required receipts
exist.  ``--prepare`` validates compact closure metadata and writes both package
files exclusively.  It never imports scientific modules or reads economic data.
This is a document assembler, not an auditor or a substitute for the official
preflight.  A partial write is preserved and blocks automatic retry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
BASE = Path("D:/GexResearchArtifacts/level_oracle_20261018")
PIPELINE = BASE / "oof_pipeline_runtime_20261024_v2r1_01"
CONTINUATION_LOGS = BASE / "oof_pipeline_user_stop_continuation_launch_20261029_01"
AUDIT_OUTPUT = BASE / "oof_economic_audit_user_stop_continuation_20261029_01"
AUDIT_LOGS = BASE / "oof_economic_audit_user_stop_continuation_launch_20261029_01"

SOURCE_REQUEST = HERE / "OOF_PIPELINE_V2R1_RUNTIME_REQUEST_20261024_01.json"
SOURCE_REQUEST_SHA = "37f2018c7145d3b82cba2e34fbff9ae3008e33f32b004c5580e433157f38ef15"
SOURCE_BINDING = HERE / "OOF_PIPELINE_V2R1_LAUNCH_RUNTIME_BINDING_20261024_01.json"
SOURCE_BINDING_SHA = "9e4949227dfd8b0aa3e72a35271b081413dbd9dee482b79c98911ea25478813c"
CONTINUATION_REQUEST = HERE / "OOF_USER_STOP_CONTINUATION_REQUEST_20261029_01.json"
CONTINUATION_REQUEST_SHA = "f32e35e965722631e2f685db3c3a38aefc6021f5edd35db18f55984061982fef"
CONTINUATION_BINDING = HERE / "OOF_USER_STOP_CONTINUATION_RUNTIME_BINDING_20261029_01.json"
CONTINUATION_BINDING_SHA = "4197cd14d7110211164238c3863df8c88c7eca9d26db248aa4c1e11a3bdb9510"
CONTINUATION_REVIEW = HERE / "OOF_USER_STOP_CONTINUATION_IMPLEMENTATION_REVIEW_20261029.json"
CONTINUATION_REVIEW_SHA = "6a06521fc74fd9b8afd4efeab0209066f9138749e7e1acde562ce6c50ede16bf"
ECONOMIC_REVIEW = HERE / "OOF_ECONOMIC_AUDIT_USER_STOP_IMPLEMENTATION_REVIEW_20261029.json"
ECONOMIC_REVIEW_SHA = "0c4edfd7c74b74f1573f8ce7133c79d7339cf4da06c243edc36699164622403b"
AUDITOR_REVIEW = HERE / "OOF_ECONOMIC_AUDITOR_IMPLEMENTATION_REVIEW_20261023.json"
AUDITOR_REVIEW_SHA = "cf7a0659b495ad9bab484839d71c1f4377fb25c5c9df60d772cf0b7667c4d653"
PIPELINE_REVIEW = HERE / "OOF_TRANSITIVE_SOURCE_V2R1_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json"
PIPELINE_REVIEW_SHA = "2782b686947c9ddd5f723ad2b279802d21f3adbbee79aa76a6cd6e8bce551a78"
SOURCE_ADMISSION_SHA = "ec2f728baf2ab28adaaf3855847d74bf6354ac587d440afb83b50278e5ca3234"
CONTINUATION_CODE_SHA = "599f6d5c347ebdc3801bbe8cc21de55603a80a46858a8bad1d20729d307eee11"
REQUEST_OUTPUT = HERE / "OOF_ECONOMIC_AUDIT_USER_STOP_REQUEST_20261101_01.json"
BINDING_OUTPUT = HERE / "OOF_ECONOMIC_AUDIT_USER_STOP_BINDING_20261101_01.json"
MONTHS = [f"2026{i:02d}" for i in range(1, 7)]
ADAPTER_NAMES = (
    "monthly_oof_calibration_adapter.py",
    "oof_maximum_calibration.py",
    "rolling_monthly_schedule.py",
    "MONTHLY_OOF_CALIBRATION_ADAPTER_SPEC.md",
    "PREQUENTIAL_MAX_CALIBRATION_DESIGN.md",
    "OOF_MAXIMUM_CALIBRATION_INTEGRATION.md",
)
REPLAY_NAMES = (*ADAPTER_NAMES, "evaluate_oof_calibrated_policy.py", "OOF_CALIBRATED_POLICY_EVALUATION_SPEC.md")

CPU_FILES = {
    str(HERE / "continuation_20261029/oof_economic_audit_user_stop_implementation/cpu_inheritance_01.json"):
        "6133e8cefbddc2c87338ceb0d825bf096cfe36e0c51e640c894fe2ef57cfd8f5",
    str(HERE / "continuation_20261029/oof_user_stop_continuation_implementation_independent/attempt_01/cpu0_independent_evidence.json"):
        "29536ceb50c7b96e341551f2498937a7d8bead35b4e930f08edcfc42ead006e4",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "SHA256 required")
    return value


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def ref(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path)}


def verify(path, expected):
    require(Path(path).is_file() and sha(path) == digest(expected), "Pinned authority differs: " + str(path))


def add_pin(target, path, expected):
    path, expected = str(Path(path).resolve()), digest(expected)
    require(path not in target or target[path] == expected, "Conflicting publication pin: " + path)
    target[path] = expected


def required_receipt_paths(logs=None, pipeline=None):
    logs = CONTINUATION_LOGS if logs is None else Path(logs)
    pipeline = PIPELINE if pipeline is None else Path(pipeline)
    return {
        "preflight": Path(logs) / "preflight.json",
        "process": Path(logs) / "process.json",
        "exit": Path(logs) / "exit.json",
        "supervisor_completion": Path(logs) / "completion.json",
        "pipeline_completion": Path(pipeline) / "completion.json",
    }


def compact_paths(source, pipeline=PIPELINE):
    pipeline = Path(pipeline)
    expected = {str(pipeline / name) for name in ("request.json", "contract.json", "completion.json")}
    expected.update(str(pipeline / f"{folder}/{i:02d}.json") for folder in ("starts", "receipts") for i in range(12))
    expected.update(str(Path(source["correction_root"]) / f"{month}.complete.json") for month in MONTHS)
    expected.update(
        str(Path(source["evaluation_roots"][month]) / name)
        for month in MONTHS for name in ("completion.json", "run_contract.json")
    )
    return expected


def control_paths(source):
    pipeline = Path(source["pipeline_root"])
    expected = {str(pipeline / name) for name in ("request.json", "contract.json", "completion.json")}
    expected.update(str(pipeline / f"{folder}/{i:02d}.json") for folder in ("starts", "receipts") for i in range(12))
    require(len(expected) == 27, "Twenty-seven controls required")
    return expected


def load_compact_documents(source, compact):
    """Reject an out-of-scope map before opening any path from it."""
    require(set(compact) == compact_paths(source, Path(source["pipeline_root"])), "Exact compact closure membership required")
    documents = {}
    for path, expected in compact.items():
        verify(path, expected)
        documents[str(Path(path))] = read(path)
    return documents


def reject_unknown_failures(source, continuation_logs=CONTINUATION_LOGS):
    roots = [
        Path(continuation_logs),
        Path(source["pipeline_root"]),
        Path(source["correction_root"]),
        *(Path(source["evaluation_roots"][month]) for month in MONTHS),
    ]
    for root in roots:
        require(root.is_dir(), "Closed upstream root required: " + str(root))
        for item in root.rglob("*"):
            if item.is_file() and (item.name in ("failure.json", "audit_failure.json") or item.name.endswith(".partial")):
                raise ValueError("Unknown upstream failure/partial: " + str(item))


def validate_closed_metadata(source, continuation_request, continuation_binding, continuation_review,
                             preflight, process, ended, supervisor_completion, pipeline_completion,
                             closure, compact, documents, paths, unexpected_failure=False):
    """Validate the exact compact chain and return six closure pin pairs."""
    require(source["months"] == MONTHS and source["version"] == "OOF_PIPELINE_RUNTIME_REQUEST_V2R1", "Frozen source request required")
    require(continuation_request["remaining_phases"] == [[m, s] for m in MONTHS[4:] for s in ("correction", "replay")], "Four pending phases authority differs")
    require(continuation_binding["request"] == {"path": str(CONTINUATION_REQUEST), "sha256": CONTINUATION_REQUEST_SHA}, "Continuation binding differs")
    require(continuation_review["status"] == "PASS_OOF_USER_STOP_CONTINUATION_IMPLEMENTATION_REVIEW" and continuation_review["decision"] == "CLEAR", "Continuation review required")
    require(preflight["status"] == "PASS_OOF_USER_STOP_CONTINUATION_PREFLIGHT_NOT_EXECUTED" and preflight["executed"] is False, "Real continuation preflight required")
    require(preflight["request_sha256"] == CONTINUATION_REQUEST_SHA and preflight["runtime_binding_sha256"] == CONTINUATION_BINDING_SHA and preflight["implementation_review_sha256"] == CONTINUATION_REVIEW_SHA and preflight["source_admission_sha256"] == SOURCE_ADMISSION_SHA, "Continuation preflight pins differ")
    require(process["status"] == "PROCESS_HANDLE_RETAINED" and process["creation_time_source"] == "GetProcessTimes_retained_Popen_handle" and ended["status"] == "PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE" and ended["exit_code_source"] == "GetExitCodeProcess_retained_Popen_handle", "Retained continuation process required")
    require(type(ended.get("exit_code")) is int and ended["exit_code"] == 0, "Continuation exit zero required")
    require(process["pid"] == ended["pid"] and process["creation_time"] == ended["creation_time"], "Continuation process identity differs")
    require(process["command"] == preflight["command"] and process["child_cpu_affinity"] == [0] and process["initial_child_affinity_verified"] is True, "Continuation command/initial monitor differs")
    require(ended["monitor_valid"] is True and ended["retry"] is False, "Valid continuation monitor required")
    require(ended["process_receipt_sha256"] == paths["process"]["sha256"], "Continuation process receipt pin differs")
    authority = {
        "request_sha256": CONTINUATION_REQUEST_SHA,
        "runtime_binding_sha256": CONTINUATION_BINDING_SHA,
        "implementation_review_sha256": CONTINUATION_REVIEW_SHA,
        "publication_commit": preflight["publication_commit"],
        "preflight_sha256": paths["preflight"]["sha256"],
        "monitor_code_sha256": CONTINUATION_CODE_SHA,
    }
    require(all(value.get(key) == expected for value in (process, ended) for key, expected in authority.items()), "Continuation process authority differs")
    require(supervisor_completion["status"] == "COMPLETE_OOF_USER_STOP_CONTINUATION_PENDING_INDEPENDENT_AUDIT" and supervisor_completion["exit_code"] == 0, "Real supervisor completion required")
    require(supervisor_completion["process_files"] == {paths[k]["path"]: paths[k]["sha256"] for k in ("preflight", "process", "exit")}, "Supervisor process file map differs")
    require(supervisor_completion["auditor_executed"] is False and supervisor_completion["winner_selected"] is None and supervisor_completion["technical_ready"] is False and supervisor_completion["promotion_approved"] is False and supervisor_completion["retry"] is False, "Supervisor closure flags differ")
    require(all(supervisor_completion[key] == authority[key] for key in ("request_sha256", "runtime_binding_sha256", "implementation_review_sha256", "publication_commit")), "Supervisor authority differs")
    require(not unexpected_failure, "New continuation failure receipt present")
    require(supervisor_completion["pipeline_closure"] == closure and closure["baseline_preserved"] is True and len(closure["new_phases"]) == 4, "Continuation closure envelope differs")
    require(set(closure) == {"original_validation", "new_phases", "baseline_preserved"}, "Closure envelope schema differs")
    require(closure["original_validation"]["source_admission_sha256"] == SOURCE_ADMISSION_SHA, "Source admission differs")
    require(compact == closure["original_validation"]["compact_files"] and set(compact) == compact_paths(source, Path(source["pipeline_root"])), "Exact compact closure membership required")
    require(compact[str(Path(source["pipeline_root"]) / "completion.json")] == paths["pipeline_completion"]["sha256"], "Pipeline completion pin differs")
    require(documents[str(Path(source["pipeline_root"]) / "completion.json")] == pipeline_completion, "Pipeline completion bytes differ")

    controls = control_paths(source)
    require(controls <= set(compact), "Twenty-seven controls required")
    require(documents[str(Path(source["pipeline_root"]) / "request.json")] == source, "Stored request differs")

    previous, pairs, expected_new = None, {}, []
    for i, (month, stage) in enumerate((m, s) for m in MONTHS for s in ("correction", "replay")):
        start_path = str(Path(source["pipeline_root"]) / f"starts/{i:02d}.json")
        receipt_path = str(Path(source["pipeline_root"]) / f"receipts/{i:02d}.json")
        started, receipt = documents[start_path], documents[receipt_path]
        require(started["phase"] == receipt["phase"] == [month, stage] and started["previous_receipt_sha256"] == receipt["previous_receipt_sha256"] == previous, "Twelve-phase chain differs")
        require(started["request_sha256"] == receipt["request_sha256"] == SOURCE_REQUEST_SHA, "Phase request authority differs")
        require(receipt["status"] == "COMPLETE_OOF_PIPELINE_PHASE" and receipt["start_sha256"] == compact[start_path] and receipt["winner_selected"] is None and receipt["independent_audit_pending"] is True, "Phase receipt differs")
        previous = compact[receipt_path]
        if i >= 8:
            expected_new.append({"phase": [month, stage], "start": {"path": start_path, "sha256": compact[start_path]}, "receipt": {"path": receipt_path, "sha256": compact[receipt_path]}})
        target = Path(source["correction_root"]) / f"{month}.complete.json" if stage == "correction" else Path(source["evaluation_roots"][month]) / "completion.json"
        closed = documents[str(target)]
        require(receipt["completion_sha256"] == compact[str(target)] and closed["target_month"] == month and closed["winner_selected"] is None, "Monthly closure binding differs")
        names = ADAPTER_NAMES if stage == "correction" else REPLAY_NAMES
        require(closed["dependencies"] == {name: source["code"][name] for name in names}, "Monthly closure dependencies differ")
        if stage == "correction":
            require(closed["status"] == "COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS" and closed["monthly_audit_sha256"] == source["monthly_audit"]["sha256"] and closed["target_labels_read"] is False and closed["base_models_refitted"] is False and closed["development_seen"] is True, "Correction closure differs")
            pairs[month] = {"correction_completion_sha256": compact[str(target)]}
        else:
            require(closed["status"] == "COMPLETE_FIXED_OOF_POLICY_MONTH", "Replay closure differs")
            pairs[month]["evaluation_completion_sha256"] = compact[str(target)]
            contract_path = str(Path(source["evaluation_roots"][month]) / "run_contract.json")
            require(documents[contract_path] == {
                "version": "OOF_POLICY_REPLAY_V1",
                "dependencies": closed["dependencies"],
                "monthly_audit_sha256": source["monthly_audit"]["sha256"],
                "correction_completion_sha256": pairs[month]["correction_completion_sha256"],
                "target_month": month,
                "threshold": 0,
                "winner_selected": None,
            }, "Replay run contract differs")

    require(closure["new_phases"] == expected_new, "Exact new phase references required")

    require(pipeline_completion == {
        "status": "PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT",
        "request_sha256": SOURCE_REQUEST_SHA,
        "last_receipt_sha256": previous,
        "months": pairs,
        "winner_selected": None,
        "technical_ready": False,
        "promotion_approved": False,
        "auditor_executed": False,
    }, "Exact pipeline completion required")
    return pairs


def build_request(source, pairs):
    result = {
        "version": "OOF_ECONOMIC_AUDIT_REQUEST_V1",
        "scope": "FULL_H1",
        "monthly_root": source["monthly_root"],
        "monthly_audit": source["monthly_audit"]["path"],
        "monthly_audit_sha256": source["monthly_audit"]["sha256"],
        "session_root": source["session_root"],
        "session_audit": source["session_audit"]["path"],
        "correction_root": source["correction_root"],
        "months": [{"month": m, "evaluation_root": source["evaluation_roots"][m], **pairs[m]} for m in MONTHS],
    }
    require(len(result) == 9, "Nine-field request required")
    return result


def allowed_roots(source):
    roots = [
        HERE,
        BASE / "monthly_walk_forward_test_audit_20261024_01",
        BASE / "session_clock_dataset_v1_audit",
        Path(source["pipeline_root"]),
        Path(source["correction_root"]),
        *(Path(source["evaluation_roots"][m]) for m in MONTHS),
        BASE / "oof_pipeline_launch_20261024_v2r1_01",
        BASE / "oof_pipeline_v2r1_observer_20261024_01",
        CONTINUATION_LOGS,
        BASE / "oof_user_stop_continuation_evidence_20261029_01",
        BASE / "resumption_review_20261029_independent_01",
    ]
    require(len(roots) == 16 and len(set(map(str, roots))) == 16, "Sixteen canonical roots required")
    return [str(p.resolve()) for p in roots]


def publication_map(request_sha, upstream):
    review = read(ECONOMIC_REVIEW)
    require(review["status"] == "PASS_OOF_ECONOMIC_AUDIT_USER_STOP_IMPLEMENTATION_REVIEW" and review["decision"] == "CLEAR" and review["files_count"] == 74 and len(review["files"]) == 74, "Exact economic implementation review required")
    published = {}
    for name, expected in review["files"].items():
        require(Path(name).name == name, "Review members must be basenames")
        add_pin(published, HERE / name, expected)
    for path, expected in CPU_FILES.items():
        add_pin(published, path, expected)
    for path, expected in ((AUDITOR_REVIEW, AUDITOR_REVIEW_SHA), (PIPELINE_REVIEW, PIPELINE_REVIEW_SHA), (ECONOMIC_REVIEW, ECONOMIC_REVIEW_SHA), (REQUEST_OUTPUT, request_sha)):
        add_pin(published, path, expected)
    for key in ("pipeline_request", "pipeline_binding", "continuation_request", "continuation_binding", "continuation_review"):
        add_pin(published, upstream[key]["path"], upstream[key]["sha256"])
    require(len(published) == 81, "Exactly eighty-one internal publication pins required")
    return published


def build_binding(request_sha, receipt_refs, source):
    upstream = {
        "pipeline_request": {"path": str(SOURCE_REQUEST), "sha256": SOURCE_REQUEST_SHA},
        "pipeline_binding": {"path": str(SOURCE_BINDING), "sha256": SOURCE_BINDING_SHA},
        "continuation_request": {"path": str(CONTINUATION_REQUEST), "sha256": CONTINUATION_REQUEST_SHA},
        "continuation_binding": {"path": str(CONTINUATION_BINDING), "sha256": CONTINUATION_BINDING_SHA},
        "continuation_review": {"path": str(CONTINUATION_REVIEW), "sha256": CONTINUATION_REVIEW_SHA},
        **receipt_refs,
    }
    require(len(upstream) == 10, "Ten upstream references required")
    result = {
        "status": "PASS_OOF_ECONOMIC_AUDIT_USER_STOP_RUNTIME_BINDING",
        "source_admission_sha256": SOURCE_ADMISSION_SHA,
        "request": {"path": str(REQUEST_OUTPUT), "sha256": request_sha},
        "implementation_review": {"path": str(ECONOMIC_REVIEW), "sha256": ECONOMIC_REVIEW_SHA},
        "output_root": str(AUDIT_OUTPUT),
        "logs_root": str(AUDIT_LOGS),
        "allowed_read_roots": allowed_roots(source),
        "published_files": publication_map(request_sha, upstream),
        "upstream": upstream,
    }
    require(len(result) == 9, "Nine-field binding required")
    return result


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def verify_pin_map(pins):
    for path, expected in pins.items():
        verify(path, expected)


def prepare():
    require(not REQUEST_OUTPUT.exists() and not BINDING_OUTPUT.exists(), "Package destinations must be absent")
    require(not AUDIT_OUTPUT.exists() and not AUDIT_LOGS.exists(), "Audit destinations must be absent")
    authorities = ((SOURCE_REQUEST, SOURCE_REQUEST_SHA), (SOURCE_BINDING, SOURCE_BINDING_SHA),
                   (CONTINUATION_REQUEST, CONTINUATION_REQUEST_SHA), (CONTINUATION_BINDING, CONTINUATION_BINDING_SHA),
                   (CONTINUATION_REVIEW, CONTINUATION_REVIEW_SHA), (ECONOMIC_REVIEW, ECONOMIC_REVIEW_SHA),
                   (AUDITOR_REVIEW, AUDITOR_REVIEW_SHA), (PIPELINE_REVIEW, PIPELINE_REVIEW_SHA), *CPU_FILES.items())
    for path, expected in authorities:
        verify(path, expected)
    receipt_paths = required_receipt_paths()
    require(all(path.is_file() for path in receipt_paths.values()), "Five real closure receipts required")
    refs = {name: ref(path) for name, path in receipt_paths.items()}
    source, operational, runtime, continuation_review = map(read, (SOURCE_REQUEST, CONTINUATION_REQUEST, CONTINUATION_BINDING, CONTINUATION_REVIEW))
    preflight, process, ended, supervisor, pipeline_complete = (read(receipt_paths[n]) for n in ("preflight", "process", "exit", "supervisor_completion", "pipeline_completion"))
    closure = supervisor["pipeline_closure"]
    compact = closure["original_validation"]["compact_files"]
    documents = load_compact_documents(source, compact)
    observed_controls = {str(path) for path in Path(source["pipeline_root"]).rglob("*") if path.is_file()}
    require(observed_controls == control_paths(source), "Exact twenty-seven-control tree required")
    reject_unknown_failures(source)
    pairs = validate_closed_metadata(source, operational, runtime, continuation_review, preflight, process, ended, supervisor, pipeline_complete, closure, compact, documents, refs, (CONTINUATION_LOGS / "failure.json").exists())
    request = build_request(source, pairs)
    request_bytes = encoded(request)
    request_sha = hashlib.sha256(request_bytes).hexdigest()
    binding = build_binding(request_sha, refs, source)
    existing_publication = {path: expected for path, expected in binding["published_files"].items() if path != str(REQUEST_OUTPUT)}
    require(len(existing_publication) == 80, "Eighty existing publication pins required")
    verify_pin_map(existing_publication)
    verify_pin_map({value["path"]: value["sha256"] for value in refs.values()})
    verify_pin_map(compact)
    with REQUEST_OUTPUT.open("xb") as stream:
        stream.write(request_bytes)
    with BINDING_OUTPUT.open("xb") as stream:
        stream.write(encoded(binding))
    return {"status": "PREPARED_FOR_INDEPENDENT_METADATA_REVIEW_NOT_RUNTIME_AUTHORIZED", "request": ref(REQUEST_OUTPUT), "binding": ref(BINDING_OUTPUT), "phases": 12, "controls": 27, "published_files": 81}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps(prepare(), indent=2))
        return 0
    paths = required_receipt_paths()
    print(json.dumps({
        "status": "OOF_AUDIT_PACKAGE_PREPARATION_READINESS_ONLY",
        "prepared": False,
        "required_receipts": {name: {"path": str(path), "exists": path.is_file()} for name, path in paths.items()},
        "package_destinations_absent": not REQUEST_OUTPUT.exists() and not BINDING_OUTPUT.exists(),
        "audit_destinations_absent": not AUDIT_OUTPUT.exists() and not AUDIT_LOGS.exists(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
