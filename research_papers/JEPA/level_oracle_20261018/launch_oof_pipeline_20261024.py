"""Metadata-only default; one reviewed OOF child, never automatic resume or audit."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = Path("D:/GexResearchArtifacts/level_oracle_20261018")
MONTHLY_ROOT = BASE / "monthly_walk_forward_v1"
SESSION_ROOT = BASE / "session_clock_dataset_v1"
WRAPPER = HERE / "run_oof_calibrated_pipeline.py"
PIPELINE_REVIEW = HERE / "OOF_PIPELINE_RUNTIME_IMPLEMENTATION_REVIEW_20261023.json"
PIPELINE_REVIEW_SHA = "c35541a487c87512cb678cc511006a8729fbf233a00b639e4dcc60a3fdee68d6"
REVIEW = HERE / "OOF_PIPELINE_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json"
REVIEW_STATUS = "PASS_OOF_PIPELINE_LAUNCH_IMPLEMENTATION_REVIEW"
BINDING_STATUS = "PASS_OOF_PIPELINE_LAUNCH_RUNTIME_BINDING"
OPERATIONAL_LOCK = BASE / "oof_pipeline_launch.lock"
GLOBAL_LOCK = BASE / "oof_pipeline_runtime.lock"
OPS_NAME = "launch_monthly_test_index_v2_audit_20261024.py"
OPS_SHA = "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"
HELPER_NAME = "launch_monthly_test_20261023.py"
HELPER_SHA = "3e77bda56dabd8287b04ae9a47b4dcd45d5967a01a31514e933cbb44b6f4c08d"
MONTHLY_RUNTIME = HERE / "MONTHLY_TEST_INDEX_V2_AUDIT_RUNTIME_REVIEW_20261024_01.json"
MONTHLY_RUNTIME_SHA = "055d2734469a77dc607585d000f594ed3088580400c46f513c209119a793eab1"
MONTHLY_REVIEW = HERE / "MONTHLY_TEST_INDEX_V2_AUDIT_LAUNCH_REVIEW_20261024.json"
MONTHLY_REVIEW_SHA = "e38ae0fb7ebfc3d5841fe87052d00605f58cba21a8ba987341d0f307ede9e432"
AUDITOR_REVIEW = HERE / "MONTHLY_TEST_INDEX_AUDIT_V2_REVIEW_20261024.json"
AUDITOR_REVIEW_SHA = "493806fbc25a50a3333b4d2e65f3bd041bd30b30d5a10203d8c188c0520ee2b3"
MONTHLY_PRODUCER_REVIEW = HERE / "MONTHLY_TEST_RESOURCE_OVERLAY_REVIEW_20261023.json"
MONTHLY_PRODUCER_REVIEW_SHA = "49a3590504c74c06dc5a9b830bcf71b7472dbecae2ab267218aaa22aa2dd0280"
MONTHLY_OUTPUT = BASE / "monthly_walk_forward_test_audit_20261024_01"
MONTHLY_LOGS = BASE / "monthly_test_index_v2_audit_launch_20261024_01"
MONTHS = [f"2026{m:02d}" for m in range(1, 7)]
NEW_FILES = (Path(__file__).name, "test_launch_oof_pipeline_20261024.py", "OOF_PIPELINE_LAUNCH_SPEC_20261024.md")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "External SHA256 required")
    return value


def absolute(value):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts and path != Path(path.anchor), "Bounded absolute path required")
    for part in (path, *path.parents):
        require(not part.is_symlink() and not part.is_junction(), "Linked path or ancestor")
    return path.resolve()


def verify(files):
    for path, expected in files.items():
        require(sha(path) == digest(expected), "Pinned bytes differ: " + str(path))


def literal(name):
    tree = ast.parse(WRAPPER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name:
            return ast.literal_eval(node.value)
    raise ValueError("Frozen literal absent: " + name)


def dependency_sets():
    adapter = {"monthly_oof_calibration_adapter.py", "oof_maximum_calibration.py", "rolling_monthly_schedule.py",
        "MONTHLY_OOF_CALIBRATION_ADAPTER_SPEC.md", "PREQUENTIAL_MAX_CALIBRATION_DESIGN.md", "OOF_MAXIMUM_CALIBRATION_INTEGRATION.md"}
    replay = adapter | {"evaluate_oof_calibrated_policy.py", "OOF_CALIBRATED_POLICY_EVALUATION_SPEC.md"}
    return adapter, replay, replay | set(literal("EXTRA_CODE"))


def implementation_files():
    verify({PIPELINE_REVIEW: PIPELINE_REVIEW_SHA, AUDITOR_REVIEW: AUDITOR_REVIEW_SHA,
            MONTHLY_PRODUCER_REVIEW: MONTHLY_PRODUCER_REVIEW_SHA,
            HERE / OPS_NAME: OPS_SHA, HERE / HELPER_NAME: HELPER_SHA})
    metadata = read(PIPELINE_REVIEW)
    dependencies = metadata["binding"]["runtime_dependency_map"]
    require(metadata["status"] == "PASS_OOF_PIPELINE_RUNTIME_IMPLEMENTATION_REVIEW" and metadata["decision"] == "CLEAR",
            "Frozen pipeline implementation review required")
    require(len(dependencies) == 17 and set(dependencies) == dependency_sets()[2], "Exact seventeen dependencies required")
    require(all(dependencies.get(n) == h for n, h in literal("PINS").items())
            and literal("PINS") == metadata["binding"]["frozen_pins"], "Frozen producer pins differ")
    audit_dependencies = read(AUDITOR_REVIEW)["dependencies"]
    require(len(audit_dependencies) == 13, "Monthly audit dependency authority differs")
    scientific = read(MONTHLY_PRODUCER_REVIEW)["original_dependencies"]
    require(len(scientific) == 11, "Eleven frozen scientific dependencies required")
    pending = list(set(NEW_FILES) | set(dependencies) | set(audit_dependencies) | set(scientific) | {OPS_NAME, HELPER_NAME})
    found = set()
    while pending:
        name = pending.pop()
        if name in found:
            continue
        require(Path(name).name == name, "Local import members must be basenames")
        found.add(name)
        path = HERE / name
        if path.suffix != ".py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for module in modules:
                candidate = module.split(".")[0] + ".py"
                if (HERE / candidate).is_file():
                    pending.append(candidate)
    result = {n: sha(HERE / n) for n in sorted(found)}
    require(all(result[n] == h for n, h in dependencies.items()), "Pipeline dependency bytes changed")
    require(all(result[n] == h for n, h in audit_dependencies.items()), "Monthly audit dependency bytes changed")
    require(all(result[n] == h for n, h in scientific.items()), "Frozen helper scientific dependency changed")
    return result, dependencies


def publication(commit, files):
    require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit), "Full publication commit required")
    for value, expected in files.items():
        path = absolute(value)
        require(path.is_relative_to(REPO), "Published member outside repository")
        item = subprocess.run(["git", "show", commit + ":" + path.relative_to(REPO).as_posix()],
            cwd=REPO, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        require(hashlib.sha256(item.stdout).hexdigest() == expected, "Git object differs")


def output_roots(request, binding):
    require(set(request["evaluation_roots"]) == set(MONTHS), "Six replay roots required")
    roots = [absolute(request[n]) for n in ("pipeline_root", "correction_root")]
    roots += [absolute(request["evaluation_roots"][m]) for m in MONTHS]
    roots.append(absolute(binding["logs_root"]))
    protected = [HERE, absolute(request["monthly_root"]), absolute(request["session_root"]),
        MONTHLY_OUTPUT, MONTHLY_LOGS, BASE / "engine_v1", BASE / "features_v1", GLOBAL_LOCK, OPERATIONAL_LOCK]
    protected += [absolute(p) for p in binding["allowed_read_roots"]]
    for i, root in enumerate(roots):
        require(not root.exists(), "Fresh outputs and logs required")
        require(all(not root.is_relative_to(other) and not other.is_relative_to(root)
            for other in roots[i+1:] + protected), "Output roots overlap")
    return roots


def upstream(request, binding, evidence, ops):
    """Metadata only; reuse the published compact audit result checker, never its CLI."""
    source = binding["upstream"]
    paths = dict(preflight=MONTHLY_LOGS / "preflight.json", process=MONTHLY_LOGS / "process.json",
        exit=MONTHLY_LOGS / "exit.json", completion=MONTHLY_LOGS / "completion.json",
        audit_launch=MONTHLY_OUTPUT / "launch.json", audit=MONTHLY_OUTPUT / "audit.json")
    require(set(source) == set(paths), "Exact upstream process authority set required")
    values = {}
    for name, path in paths.items():
        require(absolute(source[name]["path"]) == path, "Upstream authority path differs")
        values[name] = evidence.member(source[name])
    require(not (MONTHLY_LOGS / "failure.json").exists() and not (MONTHLY_OUTPUT / "failure.json").exists(), "Upstream failure coexists")
    evidence.file(MONTHLY_RUNTIME, MONTHLY_RUNTIME_SHA)
    evidence.file(MONTHLY_REVIEW, MONTHLY_REVIEW_SHA)
    preflight, process, exited, complete = (values[n] for n in ("preflight", "process", "exit", "completion"))
    require(preflight["status"] == "PASS_AUDIT_SUPERVISOR_PREFLIGHT_NOT_EXECUTED"
        and preflight["runtime_review"] == str(MONTHLY_RUNTIME)
        and preflight["runtime_review_sha256"] == MONTHLY_RUNTIME_SHA
        and preflight["supervisor_review_sha256"] == MONTHLY_REVIEW_SHA
        and preflight["command"] == ops.command(MONTHLY_RUNTIME, MONTHLY_OUTPUT), "Upstream preflight binding differs")
    expected_identity = dict(monitor_code_sha256=OPS_SHA, runtime_review_sha256=MONTHLY_RUNTIME_SHA,
        supervisor_review_sha256=MONTHLY_REVIEW_SHA, publication_commit=preflight["publication_commit"],
        preflight_sha256=source["preflight"]["sha256"])
    require(process["status"] == "PROCESS_HANDLE_RETAINED" and process["command"] == preflight["command"]
        and process["creation_time_source"] == "GetProcessTimes_retained_Popen_handle", "Upstream process differs")
    require(exited["status"] == "PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE" and exited["exit_code"] == 0
        and type(exited["exit_code"]) is int
        and exited["exit_code_source"] == "GetExitCodeProcess_retained_Popen_handle"
        and exited["pid"] == process["pid"] and exited["creation_time"] == process["creation_time"]
        and exited["process_receipt_sha256"] == source["process"]["sha256"], "Upstream retained exit zero required")
    require(type(process["pid"]) is int and process["pid"] > 0 and type(exited["pid"]) is int
        and type(process["creation_time"]) in (int, float) and math.isfinite(process["creation_time"])
        and process["creation_time"] > 0 and type(exited["creation_time"]) in (int, float), "Strict process identity required")
    require(all(record.get(k) == v for record in (process, exited) for k, v in expected_identity.items()), "Upstream identity authority mismatch")
    expected_files = {str(paths[n]): source[n]["sha256"] for n in paths if n != "completion"}
    require(complete["status"] == "COMPLETE_MONTHLY_TEST_INDEX_V2_AUDIT_SUPERVISION" and complete["exit_code"] == 0
        and type(complete["exit_code"]) is int
        and complete["closure_files"] == expected_files and complete["audit_path"] == str(paths["audit"])
        and complete["audit_sha256"] == source["audit"]["sha256"]
        and complete["runtime_review_sha256"] == MONTHLY_RUNTIME_SHA
        and complete["supervisor_review_sha256"] == MONTHLY_REVIEW_SHA
        and complete["publication_commit"] == preflight["publication_commit"], "Upstream supervisor closure differs")
    times = [datetime.fromisoformat(v) for v in (process["monitor_started_utc"], exited["observed_utc"], complete["completed_utc"])]
    require(all(t.tzinfo is not None and t.utcoffset() == timedelta(0) for t in times), "Aware UTC receipts required")
    require(times[0] <= times[1] <= times[2], "Upstream chronology differs")
    require(request["monthly_audit"] == source["audit"], "Request monthly authority differs")
    require(preflight["dependencies"] == read(ops.AUDITOR_REVIEW)["dependencies"], "Upstream thirteen dependencies differ")
    evidence.file(ops.VALIDATION_AUDIT, ops.VALIDATION_SHA)
    ops.validate_audit(MONTHLY_OUTPUT, preflight)
    snapshots = values["audit"]["execution_snapshots"]
    for path, value in snapshots.items():
        evidence.file(path, value)
    session = evidence.member(request["session_audit"])
    audit_binding = values["audit"]["binding"]
    require(session["status"] == "PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT"
        and absolute(session["binding"]["engine_root"]) == absolute(request["session_root"])
        and audit_binding["session_audit_sha256"] == request["session_audit"]["sha256"]
        and session["binding"]["index_sha256"] == audit_binding["index_sha256"], "Session authority mismatch")
    evidence.file(absolute(request["monthly_root"]) / "run_contract.json", audit_binding["run_contract_sha256"])
    evidence.file(absolute(request["session_root"]) / "index.parquet", audit_binding["index_sha256"])
    return values


def command(request_path, request_sha):
    return [sys.executable, "-u", str(WRAPPER), "--request", str(request_path), "--request-sha256", request_sha]


def preflight(request_path, request_sha, binding_path, binding_sha, review_sha, commit):
    require(os.name == "nt" and sys.flags.optimize == 0 and not os.environ.get("PYTHONOPTIMIZE"), "Unoptimized Windows Python required")
    request_path, binding_path = absolute(str(request_path)), absolute(str(binding_path))
    pins = {str(request_path): digest(request_sha), str(binding_path): digest(binding_sha), str(REVIEW): digest(review_sha),
        str(PIPELINE_REVIEW): PIPELINE_REVIEW_SHA, str(AUDITOR_REVIEW): AUDITOR_REVIEW_SHA,
        str(MONTHLY_PRODUCER_REVIEW): MONTHLY_PRODUCER_REVIEW_SHA,
        str(MONTHLY_RUNTIME): MONTHLY_RUNTIME_SHA, str(MONTHLY_REVIEW): MONTHLY_REVIEW_SHA}
    verify(pins)
    files, dependencies = implementation_files()
    review, request, binding = read(REVIEW), read(request_path), read(binding_path)
    require(review.get("status") == REVIEW_STATUS and review.get("decision") == "CLEAR" and review.get("files") == files
        and review.get("scope") == "IMPLEMENTATION_ONLY" and review.get("runtime_authorized") is False, "Exact supervisor review required")
    require(binding.get("status") == BINDING_STATUS and binding.get("request") == dict(path=str(request_path), sha256=request_sha)
        and binding.get("implementation_review") == dict(path=str(REVIEW), sha256=review_sha), "External operational binding differs")
    require(request.get("version") == "OOF_PIPELINE_RUNTIME_REQUEST_V1" and request.get("status") == "REVIEWED_OOF_PIPELINE_RUNTIME_REQUEST"
        and request.get("runtime_authorized") is True and request.get("months") == MONTHS
        and request.get("code") == dependencies and absolute(request["coordination_lock"]) == GLOBAL_LOCK,
        "Exact reviewed OOF request required")
    require(absolute(request["monthly_root"]) == MONTHLY_ROOT
        and absolute(request["session_root"]) == SESSION_ROOT, "Scientific roots differ")
    roots = output_roots(request, binding)
    published = {str(HERE / n): h for n, h in files.items()}
    published.update({p: h for p, h in pins.items() if p != str(binding_path)})
    require(binding.get("published_files") == published, "Publication membership differs")
    pins.update(published)
    verify(pins)
    publication(commit, pins)
    ops = importlib.import_module(OPS_NAME.removesuffix(".py"))
    verify(pins)
    ops.gate(ops.observation())
    evidence = ops.Evidence(binding["allowed_read_roots"])
    for path, value in pins.items():
        evidence.file(path, value)
    upstream(request, binding, evidence, ops)
    verify(evidence.files)
    return dict(status="PASS_OOF_LAUNCH_PREFLIGHT_NOT_EXECUTED", executed=False, retry=False,
        request_path=str(request_path), request_sha256=request_sha, runtime_binding=str(binding_path), runtime_binding_sha256=binding_sha,
        implementation_review_sha256=review_sha, publication_commit=commit, publication_files=pins, files=evidence.files,
        logs_root=str(roots[-1]), output_roots=[str(p) for p in roots],
        command=command(request_path, request_sha), dependencies=dependencies)


def no_link(path):
    path = Path(path)
    require(absolute(str(path)) == path, "Linked or redirected output")


def output_mapping(mapping, roots):
    require(isinstance(mapping, dict), "Output inventory must be a mapping")
    result, aliases = {}, set()
    for value, expected in mapping.items():
        path = absolute(value)
        require(str(path) == value and any(path.is_relative_to(r) and path != r for r in roots), "Output inventory escaped or aliased")
        require(str(path).casefold() not in aliases, "Duplicate output alias")
        no_link(path)
        aliases.add(str(path).casefold())
        result[str(path)] = digest(expected)
    return result


def tree_files(root, exclude_root_lock=False):
    no_link(root)
    result = set()
    for path in root.rglob("*"):
        no_link(path)
        require(path.resolve().is_relative_to(root), "Output tree escaped")
        if path.is_file():
            if exclude_root_lock and path.name == ".lock" and path.parent == root:
                continue
            require(not path.name.endswith(".partial"), "Partial output preserved")
            result.add(str(path))
    return result


def validate_pipeline(request, request_sha):
    """Verify compact closure metadata and stream output hashes, never scientific helpers."""
    pipeline = absolute(request["pipeline_root"])
    correction = absolute(request["correction_root"])
    evaluations = {m: absolute(request["evaluation_roots"][m]) for m in MONTHS}
    roots = [correction, *evaluations.values()]
    compact = {}

    def member(path, expected=None):
        path = Path(path)
        no_link(path)
        actual = sha(path)
        require(expected is None or actual == expected, "Closure bytes differ")
        value = read(path)
        require(sha(path) == actual, "Closure changed during read")
        compact[str(path)] = actual
        return value, actual

    stored, _ = member(pipeline / "request.json", request_sha)
    require(stored == request, "Stored request differs")
    contract, _ = member(pipeline / "contract.json")
    require(contract == dict(version="OOF_PIPELINE_V1", request_sha256=request_sha,
        code=request["code"], correction_layout="SHARED_CUMULATIVE"), "Pipeline contract differs")
    adapter_names, replay_names, _ = dependency_sets()
    adapter = {n: request["code"][n] for n in adapter_names}
    replay = {n: request["code"][n] for n in replay_names}
    prior, cumulative, closures = None, {}, {}
    expected_control = {str(pipeline / n) for n in ("request.json", "contract.json", "completion.json")}
    for index, (month, stage) in enumerate((m, s) for m in MONTHS for s in ("correction", "replay")):
        start_path, receipt_path = pipeline / f"starts/{index:02d}.json", pipeline / f"receipts/{index:02d}.json"
        expected_control.update((str(start_path), str(receipt_path)))
        receipt, receipt_sha = member(receipt_path)
        require(receipt["status"] == "COMPLETE_OOF_PIPELINE_PHASE" and receipt["request_sha256"] == request_sha
            and receipt["phase"] == [month, stage] and receipt["previous_receipt_sha256"] == prior
            and receipt["winner_selected"] is None and receipt["independent_audit_pending"] is True,
            "Phase receipt chain differs")
        start, _ = member(start_path, receipt["start_sha256"])
        require(start["request_sha256"] == request_sha and start["phase"] == [month, stage]
            and start["previous_receipt_sha256"] == prior, "Phase start chain differs")
        observed = output_mapping(receipt["output_inventory"], roots)
        require(all(observed.get(p) == h for p, h in cumulative.items()), "Earlier phase output changed or omitted")
        if stage == "correction":
            require(all(Path(p).is_relative_to(correction) for p in set(observed)-set(cumulative)), "Correction phase writes another root")
            closed_path = correction / f"{month}.complete.json"
            closed, _ = member(closed_path, receipt["completion_sha256"])
            require(closed["status"] == "COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS"
                and closed["target_month"] == month and closed["monthly_audit_sha256"] == request["monthly_audit"]["sha256"]
                and closed["dependencies"] == adapter and closed["target_labels_read"] is False
                and closed["base_models_refitted"] is False and closed["winner_selected"] is None
                and closed["development_seen"] is True, "Correction closure differs")
            require(observed.get(str(correction / f"{month}.inputs.json")) == closed["inputs_sha256"], "Correction inputs pin differs")
            closures[month] = dict(correction_completion_sha256=receipt["completion_sha256"])
        else:
            root = evaluations[month]
            closed_path = root / "completion.json"
            closed, _ = member(closed_path, receipt["completion_sha256"])
            require(closed["status"] == "COMPLETE_FIXED_OOF_POLICY_MONTH" and closed["target_month"] == month
                and closed["winner_selected"] is None and closed["dependencies"] == replay, "Replay closure differs")
            correction_sha = closures[month]["correction_completion_sha256"]
            require(closed["files"].get(str(correction / f"{month}.complete.json")) == correction_sha, "Replay correction pin differs")
            replay_contract, _ = member(root / "run_contract.json", closed["files"][str(root / "run_contract.json")])
            require(replay_contract == dict(version="OOF_POLICY_REPLAY_V1", dependencies=replay,
                monthly_audit_sha256=request["monthly_audit"]["sha256"], correction_completion_sha256=correction_sha,
                target_month=month, threshold=0, winner_selected=None), "Replay contract differs")
            for name in ("run_contract.json", "summary.json", "all_scores_and_controls.json"):
                require(observed.get(str(root / name)) == closed["files"].get(str(root / name))
                    and str(root / name) in observed, "Replay output pin differs")
            local = {}
            for name, expected in closed["files"].items():
                path = absolute(name)
                if path.is_relative_to(root):
                    require(str(path) == name and observed.get(name) == expected, "Replay local output pin differs")
                    local[name] = expected
            require(set(observed)-set(cumulative) == {str(closed_path), *local}, "Replay phase output membership differs")
            closures[month]["evaluation_completion_sha256"] = receipt["completion_sha256"]
        require(observed.get(str(closed_path)) == receipt["completion_sha256"], "Phase closure absent from inventory")
        require(receipt["new_output_bytes"] == sum(Path(p).stat().st_size for p in set(observed)-set(cumulative))
            and receipt["cumulative_output_bytes"] == sum(Path(p).stat().st_size for p in observed), "Output byte accounting differs")
        prior, cumulative = receipt_sha, observed
    complete, _ = member(pipeline / "completion.json")
    require(complete == dict(status="PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT", request_sha256=request_sha,
        last_receipt_sha256=prior, months=closures, winner_selected=None, technical_ready=False,
        promotion_approved=False, auditor_executed=False), "Final pipeline completion differs")
    require(tree_files(pipeline) == expected_control, "Unexpected pipeline control artifact")
    actual = set().union(*(tree_files(root, True) for root in roots))
    require(actual == set(cumulative), "Final output inventory membership differs")
    # One streaming pass over final outputs; no payload parsing or source rehash.
    for name, expected in cumulative.items():
        path = absolute(name)
        no_link(path)
        require(any(path.is_relative_to(root) and path != root for root in roots), "Output redirected before hash")
        verify({path: expected})
    verify(compact)
    return dict(compact_files=compact, output_count=len(cumulative),
        output_inventory_sha256=hashlib.sha256(json.dumps(cumulative, sort_keys=True, separators=(",", ":")).encode()).hexdigest())


def monitor(child, receipt, helper, ops, preflight_sha):
    logs = Path(receipt["logs_root"])
    ended, errors, samples = False, [], 0
    peak_rss = peak_private = minimum = None
    started = time.monotonic()
    try:
        retained = helper.RetainedProcess(child)
        created = retained.creation_time()
        authority = dict(monitor_code_sha256=receipt["files"][str(Path(__file__).resolve())],
            request_sha256=receipt["request_sha256"], runtime_binding_sha256=receipt["runtime_binding_sha256"],
            implementation_review_sha256=receipt["implementation_review_sha256"],
            publication_commit=receipt["publication_commit"], preflight_sha256=preflight_sha)
        helper.publish(logs, "process.json", dict(status="PROCESS_HANDLE_RETAINED", pid=child.pid,
            creation_time=created, creation_time_source="GetProcessTimes_retained_Popen_handle",
            command=receipt["command"], monitor_started_utc=utc(), **authority))
        process_sha = sha(logs / "process.json")
        import psutil
        try:
            process = psutil.Process(child.pid)
            require(abs(process.create_time()-created) < 0.001, "PID identity mismatch")
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
                    peak_rss = max(peak_rss or 0, memory.rss)
                    peak_private = max(peak_private or 0, memory.private)
                    samples += 1
                value = ops.observation()
                minimum = value if minimum is None else {k: min(minimum[k], v) for k, v in value.items()}
            except (psutil.Error, OSError, ValueError) as exc:
                errors.append(repr(exc))
        helper.publish(logs, "exit.json", dict(status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE", pid=child.pid,
            creation_time=created, exit_code=code, exit_code_source="GetExitCodeProcess_retained_Popen_handle",
            observed_utc=utc(), process_receipt_sha256=process_sha, monitor_seconds=time.monotonic()-started,
            sample_count=samples, peak_sampled_rss_bytes=peak_rss, peak_sampled_private_bytes=peak_private,
            minimum_free_observed=minimum, monitor_errors=errors, retry=False, **authority))
        return dict(exit_code=code, files={str(logs / "process.json"): process_sha,
            str(logs / "exit.json"): sha(logs / "exit.json"), str(logs / "preflight.json"): preflight_sha})
    finally:
        if not ended:
            helper.drain_child(child)


def launch(receipt):
    require(receipt.get("status") == "PASS_OOF_LAUNCH_PREFLIGHT_NOT_EXECUTED", "Preflight required")
    verify(receipt["files"])
    helper = importlib.import_module(HELPER_NAME.removesuffix(".py"))
    ops = importlib.import_module(OPS_NAME.removesuffix(".py"))
    verify(receipt["files"])
    request_path, binding_path = Path(receipt["request_path"]), Path(receipt["runtime_binding"])
    request, binding = read(request_path), read(binding_path)
    roots = output_roots(request, binding)
    logs = roots[-1]
    require(str(logs) == receipt["logs_root"] and [str(p) for p in roots] == receipt["output_roots"]
        and receipt["command"] == command(request_path, receipt["request_sha256"]), "Fixed OOF command/outputs differ")
    require(OPERATIONAL_LOCK != GLOBAL_LOCK, "Supervisor must not own pipeline lock")
    with helper.overlay.os_lock(OPERATIONAL_LOCK, create=True):
        publication(receipt["publication_commit"], receipt["publication_files"])
        evidence = ops.Evidence(binding["allowed_read_roots"])
        evidence.files.update(receipt["files"])
        upstream(request, binding, evidence, ops)
        verify(evidence.files)
        output_roots(request, binding)
        logs.mkdir(parents=True, exist_ok=False)
        helper.publish(logs, "preflight.json", receipt)
        preflight_sha = sha(logs / "preflight.json")
        env = os.environ.copy()
        env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        try:
            with (logs / "stdout.log").open("xb") as stdout, (logs / "stderr.log").open("xb") as stderr:
                verify(evidence.files)
                resources = ops.observation()
                ops.gate(resources)
                child = subprocess.Popen(receipt["command"], cwd=REPO, env=env, stdin=subprocess.DEVNULL,
                    stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    helper.publish(logs, "admission.json", dict(**resources, minimum_free_bytes=2_000_000_000, utc=utc()))
                    monitored = monitor(child, receipt, helper, ops, preflight_sha)
                finally:
                    helper.drain_child(child)
            require(monitored["exit_code"] == 0, "OOF child must exit zero")
            verify(monitored["files"])
            verify(evidence.files)
            closed = validate_pipeline(request, receipt["request_sha256"])
            verify(monitored["files"])
            verify(evidence.files)
            helper.publish(logs, "completion.json", dict(status="COMPLETE_OOF_PIPELINE_SUPERVISION_PENDING_INDEPENDENT_AUDIT",
                exit_code=0, request_sha256=receipt["request_sha256"], runtime_binding_sha256=receipt["runtime_binding_sha256"],
                implementation_review_sha256=receipt["implementation_review_sha256"], publication_commit=receipt["publication_commit"],
                process_files=monitored["files"], pipeline_closure=closed, completed_utc=utc(),
                auditor_executed=False, technical_ready=False, promotion_approved=False, retry=False))
            return 0
        except BaseException as exc:
            helper.publish(logs, "failure.json", dict(status="FAILED_OR_INTERRUPTED_PRESERVED", error=repr(exc), utc=utc(), retry=False))
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--runtime-binding", type=Path, required=True)
    parser.add_argument("--runtime-binding-sha256", required=True)
    parser.add_argument("--implementation-review-sha256", required=True)
    parser.add_argument("--publication-commit", required=True)
    parser.add_argument("--execute-reviewed-pipeline", action="store_true")
    args = parser.parse_args()
    receipt = preflight(args.request, args.request_sha256, args.runtime_binding, args.runtime_binding_sha256,
        args.implementation_review_sha256, args.publication_commit)
    if args.execute_reviewed_pipeline:
        return launch(receipt)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
