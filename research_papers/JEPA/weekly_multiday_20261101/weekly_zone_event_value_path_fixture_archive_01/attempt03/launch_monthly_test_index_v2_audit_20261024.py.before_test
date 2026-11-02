"""One-shot audit supervisor. Default is metadata admission only, never execution."""
from __future__ import annotations

import argparse
import ast
import ctypes
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

CODE = Path(__file__).resolve().parent
REPO = CODE.parents[2]
BASE = Path("D:/GexResearchArtifacts/level_oracle_20261018")
MONTHLY = BASE / "monthly_walk_forward_v1"
SESSION = BASE / "session_clock_dataset_v1"
SOURCE_AUDIT = BASE / "session_clock_dataset_v1_audit/audit.json"
VALIDATION_AUDIT = BASE / "monthly_walk_forward_validation_audit_20261024_02/audit.json"
AUDITOR = CODE / "audit_monthly_walk_forward_test_index_v2.py"
AUDITOR_REVIEW = CODE / "MONTHLY_TEST_INDEX_AUDIT_V2_REVIEW_20261024.json"
SUPERVISOR_REVIEW = CODE / "MONTHLY_TEST_INDEX_V2_AUDIT_LAUNCH_REVIEW_20261024.json"
NEW_FILES = (Path(__file__).name, "test_launch_monthly_test_index_v2_audit_20261024.py",
             "MONTHLY_TEST_INDEX_V2_AUDIT_LAUNCH_SPEC_20261024.md")
REVIEW_STATUS = "PASS_MONTHLY_TEST_INDEX_V2_AUDIT_LAUNCH_IMPLEMENTATION_REVIEW"
RUNTIME_STATUS = "PASS_MONTHLY_TEST_INDEX_V2_AUDIT_RUNTIME_REVIEW"
AUDIT_STATUS = "PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES"
SCOPE = "VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1"
CONTRACT_SHA = "7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f"
VALIDATION_SHA = "ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc"
SOURCE_SHA = "678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9"
INDEX_SHA = "7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4"
FREEZE_SHA = "df9a490d310d86a040e0ca9e6ad5b07c64d3474b9c71ce83e445309511fa9237"
AUDITOR_REVIEW_SHA = "493806fbc25a50a3333b4d2e65f3bd041bd30b30d5a10203d8c188c0520ee2b3"
PRODUCER_REVIEW = CODE / "MONTHLY_TEST_RESOURCE_OVERLAY_REVIEW_20261023.json"
PRODUCER_REVIEW_SHA = "49a3590504c74c06dc5a9b830bcf71b7472dbecae2ab267218aaa22aa2dd0280"
PRODUCER_RUNTIME_SHA = "1c6072a871d7d4cbcabc7e82dbbbbdb28d5767ff083571638f956d92250b557b"
HELPER_PINS = {
    "launch_monthly_test_20261023.py": "3e77bda56dabd8287b04ae9a47b4dcd45d5967a01a31514e933cbb44b6f4c08d",
    "run_monthly_test_resource_overlay.py": "f2b0490cdec916f98c09fc77a6533d0eab8c4f2711331753f7d5c998d81253c1",
}
MODES = ["static", "expanding", "rolling12"]
MONTHS = [f"2025{m:02d}" for m in range(1, 13)] + [f"2026{m:02d}" for m in range(1, 7)]
MIN_FREE = 2_000_000_000


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


def absolute(value):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "Absolute path required")
    return path.resolve()


def digest(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "External SHA256 required")
    return value


def verify(files):
    for path, expected in files.items():
        require(sha(path) == digest(expected), "Pinned bytes differ: " + str(path))


def observation():
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in ("total", "ram", "total_commit", "commit", "v", "fv", "ex")]
    value = Memory()
    value.length = ctypes.sizeof(value)
    require(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)), "Memory observation failed")
    return dict(available_ram_bytes=value.ram, free_commit_bytes=value.commit)


def gate(value):
    require(all(type(value.get(k)) is int and value[k] >= MIN_FREE
                for k in ("available_ram_bytes", "free_commit_bytes")), "2GB RAM/commit gate unmet")


def import_closure(names):
    """Pin repository-local import code without importing or executing it."""
    pending, found = list(names), set()
    while pending:
        name = pending.pop()
        if name in found:
            continue
        require(Path(name).name == name, "Code members must be basenames")
        found.add(name)
        path = CODE / name
        if path.suffix != ".py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for module in modules:
                candidate = module.split(".")[0] + ".py"
                if (CODE / candidate).is_file():
                    pending.append(candidate)
    return {name: sha(CODE / name) for name in sorted(found)}


def publication(commit, files):
    require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit), "Full Git commit required")
    for path, expected in files.items():
        path = absolute(str(path))
        require(path.is_relative_to(REPO), "Published authority outside repository")
        result = subprocess.run(["git", "show", commit + ":" + path.relative_to(REPO).as_posix()],
                                cwd=REPO, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        require(hashlib.sha256(result.stdout).hexdigest() == expected, "Published Git object differs")


class Evidence:
    def __init__(self, roots):
        self.roots = tuple(absolute(p) for p in roots)
        require(self.roots and all(p.is_dir() and p != Path(p.anchor) and p != BASE.resolve()
                                 and not BASE.resolve().is_relative_to(p) for p in self.roots),
                "Concrete bounded read roots required")
        self.files = {}

    def file(self, path, expected):
        path = absolute(str(path))
        require(any(path == r or path.is_relative_to(r) for r in self.roots), "Evidence outside read roots")
        require(str(path) not in self.files or self.files[str(path)] == expected, "Conflicting evidence hashes")
        verify({path: expected})
        self.files[str(path)] = expected
        return path

    def member(self, spec, *, json=True):
        require(set(spec) == {"path", "sha256"}, "Exact path/hash member required")
        path = self.file(spec["path"], spec["sha256"])
        value = read(path) if json else None
        self.file(path, spec["sha256"])
        return value


def safe_members(root, mapping):
    root = absolute(str(root))
    result, folded = {}, set()
    for name, expected in mapping.items():
        require(isinstance(name, str) and name and ":" not in name, "Unsafe marker key")
        normalized = name.replace("\\", "/")
        parts = normalized.split("/")
        require(all(p not in ("", ".", "..") and p.rstrip(" .") == p for p in parts), "Unsafe marker key")
        path = (root / normalized).resolve()
        require(path.is_relative_to(root) and path != root, "Marker target escaped root")
        key = str(path).casefold()
        require(key not in folded, "Marker target collision")
        folded.add(key)
        result[str(path)] = digest(expected)
    return result


def marker(root, name, evidence, required=()):
    path = root / (name + ".complete.json")
    expected = evidence.files.get(str(path.resolve()))
    require(expected is not None, "Marker absent from externally closed inventory")
    record = evidence.member(dict(path=str(path), sha256=expected))
    require(record.get("status") == "COMPLETE" and record.get("binding") == CONTRACT_SHA, "Scientific marker differs")
    members = safe_members(root, record["files"])
    for target in required:
        require(str(target.resolve()) in members, "Required marker member absent")
    # Containment is checked again at consumption, not only when parsing keys.
    for target, value in members.items():
        require(absolute(target).is_relative_to(root.resolve()), "Marker target redirected")
        evidence.file(target, value)
    return record


def fit_keys(year):
    return {f"train_{start}_{year}{m:02d}01_exclusive"
            for m in range(1, 13 if year == 2025 else 7)
            for start in ("20230101", f"{year-1}{m:02d}01")}


def science_closure(evidence, completion):
    expected_keys = fit_keys(2025) | fit_keys(2026)
    require(len(expected_keys) == 36, "Internal fit membership")
    for suffix in (".txt", ".fit_started.json", ".complete.json"):
        found = {p.name.removesuffix(suffix) for p in (MONTHLY / "models").glob("*" + suffix)}
        require(found == expected_keys, "Exactly thirty-six closed models required")
    for key in sorted(expected_keys):
        marker(MONTHLY, "models/" + key, evidence,
               [MONTHLY / f"models/{key}.txt", MONTHLY / f"models/{key}.fit_started.json"])
        marker(MONTHLY, f"fits/{key}/inputs", evidence, [MONTHLY / f"fits/{key}/inputs.json"])
    for month in MONTHS:
        for kind in ("daily", "economics", "predictions"):
            record = marker(MONTHLY, f"months/{month}/{kind}", evidence,
                            [] if kind == "predictions" else [MONTHLY / f"months/{month}/{kind}.json"])
            if kind == "predictions" and month.startswith("2026"):
                expected = sorted(["train_20230101_20250101_exclusive",
                    f"train_20230101_{month}01_exclusive", f"train_2025{month[4:]}01_{month}01_exclusive"])
                require(record.get("extra", {}).get("fit_keys") == expected
                        and record["extra"].get("labels_read") is False, "Three frozen test fit keys required")
    for name in ("reports/2025", "reports/2026", "validation_freeze", "completion"):
        marker(MONTHLY, name, evidence, [MONTHLY / (name + ".json")])
    require(completion == dict(status="COMPLETE", modes=MODES, evaluated_months=18,
            unique_fit_windows=36, selected_mode=None, development_seen=True, promotion_approved=False,
            report_hashes={str(y): evidence.files[str((MONTHLY / f"reports/{y}.json").resolve())]
                           for y in (2025, 2026)}), "Scientific eighteen-month closure differs")


def producer_closure(runtime, evidence, helper):
    producer = runtime["producer"]
    root = absolute(producer["runtime_root"])
    chain = evidence.member(producer["process_chain"])
    members = producer["process_members"]
    expected_members = {"process_binding", "monitor_open", "monitored_exit", "monitor_code", "runtime_launch"}
    if "source_launch" in members:
        expected_members.add("source_launch")
    require(set(members) == expected_members and chain.get("status") == "PROCESS_CHAIN_RECORDED"
            and chain.get("members") == members and absolute(chain["runtime_root"]) == root,
            "Exact completed producer process chain required")
    require(absolute(members["monitor_code"]["path"]) == CODE / "launch_monthly_test_20261023.py"
            and members["monitor_code"]["sha256"] == HELPER_PINS["launch_monthly_test_20261023.py"],
            "Published producer monitor differs")
    launch, exited = helper.overlay.verify_process_chain(members, evidence, root, validation=False)
    require(exited["exit_code"] == 0, "Producer test must have retained-handle exit zero")
    require(evidence.member(members["process_binding"])["command"] == producer["command"], "Producer command binding differs")
    closed = evidence.member(producer["runtime_completion"])
    source_runtime = evidence.member(producer["runtime_review"])
    require(producer["runtime_review"]["sha256"] == PRODUCER_RUNTIME_SHA, "Reviewed producer runtime differs")
    evidence.file(PRODUCER_REVIEW, PRODUCER_REVIEW_SHA)
    require(absolute(members["runtime_launch"]["path"]) == root / "launch.json"
            and absolute(producer["runtime_completion"]["path"]) == root / "completion.json",
            "Producer runtime paths differ")
    require(closed.get("status") == "COMPLETE_MONTHLY_TEST_RESOURCE_OVERLAY"
            and closed.get("original_run_contract_sha256") == launch.get("original_run_contract_sha256") == CONTRACT_SHA
            and closed.get("validation_audit_sha256") == launch.get("validation_audit_sha256") == VALIDATION_SHA
            and closed.get("runtime_review_sha256") == launch.get("runtime_review_sha256") == producer["runtime_review"]["sha256"]
            and closed.get("scientific_inputs_changed") is False and closed.get("selected_mode") is None,
            "Producer runtime completion binding differs")
    require(source_runtime.get("status") == "PASS_MONTHLY_TEST_RESOURCE_RUNTIME_REVIEW"
            and source_runtime.get("scope") == "test"
            and source_runtime.get("original_run_contract_sha256") == CONTRACT_SHA
            and source_runtime.get("scientific_root") == str(MONTHLY)
            and source_runtime.get("implementation_review_sha256") == launch.get("implementation_review_sha256") == PRODUCER_REVIEW_SHA
            and source_runtime.get("review_expectations") == launch.get("review") == helper.overlay.review_expectations()
            and source_runtime["validation"]["audit"] == dict(path=str(VALIDATION_AUDIT), sha256=VALIDATION_SHA)
            and source_runtime["validation"]["freeze"] == dict(path=str(MONTHLY / "validation_freeze.json"), sha256=FREEZE_SHA)
            and absolute(source_runtime["launch_binding"]["runtime_root"]) == root,
            "Producer runtime review differs")
    parse = helper.overlay.parse_time
    require(parse(launch["started_utc"]) < parse(closed["completed_utc"]) <= parse(exited["observed_utc"]),
            "Producer closure chronology differs")
    actual_members = {str(p.resolve()) for p in root.rglob("*") if p.is_file() and p != root / "completion.json"}
    require(set(closed["runtime_members"]) == actual_members
            and closed["runtime_members"].get(str(root / "launch.json")) == members["runtime_launch"]["sha256"],
            "Producer runtime inventory differs")
    expected_snapshots = {str(root / "executed_code" / n): h for n, h in source_runtime["review_expectations"]["files"].items()}
    expected_snapshots.update({str(root / "authorities/implementation_review.json"): PRODUCER_REVIEW_SHA,
                              str(root / "authorities/runtime_review.json"): PRODUCER_RUNTIME_SHA})
    require(launch["snapshots"] == expected_snapshots, "Producer snapshots differ")
    final_paths = {str(p.resolve()) for p in MONTHLY.rglob("*.complete.json")}
    for pattern in ("*.txt", "*.fit_started.json"):
        final_paths.update(str(p.resolve()) for p in (MONTHLY / "models").glob(pattern))
    final_paths.update(str(p.resolve()) for p in (MONTHLY / "executed_code").glob("*") if p.is_file())
    final_paths.add(str((MONTHLY / "run_contract.json").resolve()))
    require(set(closed["final_checkpoints"]) == final_paths, "Final checkpoint inventory differs")
    for group in (closed["runtime_members"], closed["preserved_checkpoints"], closed["final_checkpoints"], launch["snapshots"]):
        for path, value in group.items():
            evidence.file(path, value)
    require(closed["preserved_checkpoints"] == launch["preserved_checkpoints"], "Preserved checkpoint inventory differs")
    for key in fit_keys(2025):
        for suffix in (".txt", ".fit_started.json", ".complete.json"):
            path = str((MONTHLY / f"models/{key}{suffix}").resolve())
            require(path in closed["preserved_checkpoints"] and path in closed["final_checkpoints"], "Original model not preserved")
    science_closure(evidence, read(MONTHLY / "completion.json"))
    return closed


def destinations(runtime, authority_paths):
    binding = runtime["launch_binding"]
    output, logs = absolute(binding["output_root"]), absolute(binding["logs_root"])
    protected = [absolute(p) for p in runtime["allowed_read_roots"]] + list(authority_paths)
    for target in (output, logs):
        require(target != Path(target.anchor) and not target.exists(), "Fresh output and logs required")
        for other in protected:
            require(not target.is_relative_to(other) and not other.is_relative_to(target), "Output overlaps evidence")
    require(not output.is_relative_to(logs) and not logs.is_relative_to(output), "Outputs overlap")
    return output, logs


def command(runtime_path, output):
    return [sys.executable, "-u", str(AUDITOR), "--monthly-root", str(MONTHLY),
            "--source-audit", str(SOURCE_AUDIT), "--validation-audit", str(VALIDATION_AUDIT),
            "--expected-validation-audit-sha256", VALIDATION_SHA,
            "--implementation-review", str(AUDITOR_REVIEW), "--runtime-review", str(runtime_path), "--output", str(output)]


def preflight(runtime_path, runtime_sha, review_sha, commit):
    require(os.name == "nt" and sys.flags.optimize == 0 and not os.environ.get("PYTHONOPTIMIZE"), "Unoptimized Windows Python required")
    gate(observation())
    runtime_path = absolute(str(runtime_path))
    pins = {runtime_path: digest(runtime_sha), SUPERVISOR_REVIEW: digest(review_sha),
            AUDITOR_REVIEW: AUDITOR_REVIEW_SHA, MONTHLY / "run_contract.json": CONTRACT_SHA}
    verify(pins)
    runtime, review, auditor_review, contract = map(read, (runtime_path, SUPERVISOR_REVIEW, AUDITOR_REVIEW, MONTHLY / "run_contract.json"))
    dependencies = auditor_review["dependencies"]
    require(auditor_review.get("status") == "PASS_MONTHLY_TEST_INDEX_V2_AUDITOR_IMPLEMENTATION_REVIEW"
            and len(dependencies) == 13, "Independent extension review required")
    code = import_closure(set(NEW_FILES) | set(HELPER_PINS) | set(contract["dependencies"]) | set(dependencies))
    require(review.get("status") == REVIEW_STATUS and review.get("decision") == "CLEAR"
            and review.get("scope") == "IMPLEMENTATION_ONLY" and review.get("runtime_authorized") is False
            and review.get("files") == code, "Exact independent supervisor review required")
    require(all(code.get(n) == h for n, h in {**dependencies, **contract["dependencies"], **HELPER_PINS}.items()), "Code dependency differs")
    expected_binding = dict(monthly_root=str(MONTHLY), source_audit=str(SOURCE_AUDIT), validation_audit=str(VALIDATION_AUDIT),
        validation_audit_sha256=VALIDATION_SHA, implementation_review_sha256=AUDITOR_REVIEW_SHA,
        run_contract_sha256=CONTRACT_SHA, source_audit_sha256=SOURCE_SHA, index_sha256=INDEX_SHA,
        session_root=str(SESSION), validation_freeze_sha256=FREEZE_SHA)
    require(runtime.get("status") == RUNTIME_STATUS and runtime.get("scope") == SCOPE
            and runtime.get("dependencies") == dependencies and runtime.get("binding") == expected_binding,
            "Exact external auditor runtime required")
    lb = runtime["launch_binding"]
    require(lb.get("status") == "REVIEWED_MONTHLY_TEST_INDEX_V2_AUDIT_ONE_SHOT"
            and lb.get("supervisor_review") == dict(path=str(SUPERVISOR_REVIEW), sha256=review_sha), "Supervisor runtime binding differs")
    output, logs = destinations(runtime, [runtime_path, SUPERVISOR_REVIEW, AUDITOR_REVIEW])
    published = {str(CODE / n): h for n, h in code.items()}
    published.update({str(SUPERVISOR_REVIEW): review_sha, str(AUDITOR_REVIEW): AUDITOR_REVIEW_SHA,
                      str(PRODUCER_REVIEW): PRODUCER_REVIEW_SHA,
                      runtime["producer"]["runtime_review"]["path"]: runtime["producer"]["runtime_review"]["sha256"]})
    require(lb.get("published_files") == published, "Published inventory differs")
    pins.update(published)
    verify(pins)
    publication(commit, {**published, str(runtime_path): runtime_sha})
    helper = importlib.import_module("launch_monthly_test_20261023")
    verify(pins)
    evidence = Evidence(runtime["allowed_read_roots"])
    for path, value in pins.items():
        evidence.file(path, value)
    with helper.overlay.os_lock(MONTHLY / "run.lock", create=False):
        for path, value in [(VALIDATION_AUDIT, VALIDATION_SHA), (SOURCE_AUDIT, SOURCE_SHA),
                            (SESSION / "index.parquet", INDEX_SHA), (MONTHLY / "validation_freeze.json", FREEZE_SHA)]:
            evidence.file(path, value)
        freeze = read(MONTHLY / "validation_freeze.json")
        require(freeze.get("selected_mode") is None and freeze.get("approved") is False
                and freeze.get("status") == "FAIL_NO_DAILY_COMPLIANT_MODE", "Frozen null selection differs")
        prior = read(VALIDATION_AUDIT)
        require(prior.get("status") == AUDIT_STATUS and prior["binding"]["completed_months"] == MONTHS[:12], "Validation closure required")
        for group in prior["verified_files"].values():
            for path, value in group.items():
                evidence.file(path, value)
        producer_closure(runtime, evidence, helper)
        verify(evidence.files)
    return dict(status="PASS_AUDIT_SUPERVISOR_PREFLIGHT_NOT_EXECUTED", runtime_review=str(runtime_path),
                runtime_review_sha256=runtime_sha, supervisor_review_sha256=review_sha, publication_commit=commit,
                publication_files={**published, str(runtime_path): runtime_sha}, files=evidence.files,
                output_root=str(output), logs_root=str(logs), command=command(runtime_path, output),
                dependencies=dependencies, retry=False, executed=False)


def validate_audit(output, receipt):
    require(not (output / "failure.json").exists(), "Auditor failure coexists with result")
    result_files = {str(output / name): sha(output / name) for name in ("audit.json", "launch.json")}
    result = read(output / "audit.json")
    require(result.get("status") == AUDIT_STATUS and result.get("scope") == SCOPE
            and result.get("audit_script_sha256") == receipt["dependencies"][AUDITOR.name]
            and result.get("development_seen") is True and result.get("promotion_approved") is False, "Auditor result status differs")
    binding = result["binding"]
    require(binding == dict(monthly_root=str(MONTHLY), run_contract_sha256=CONTRACT_SHA,
            session_root=str(SESSION), session_audit_sha256=SOURCE_SHA, index_sha256=INDEX_SHA,
            completed_months=MONTHS), "Composite audit binding differs")
    prior = result["prior_validation_audit"]
    require(prior == dict(path=str(VALIDATION_AUDIT), sha256=VALIDATION_SHA, scope="VALIDATION_2025",
            inventory_rehashed=True, reconstruction_inherited_not_repeated=True), "Prior audit inheritance differs")
    checks = result["audited"]
    for name, value in dict(new_months=6, new_unique_fit_windows=12, models_used_test=13,
            total_unique_fit_windows=36, modes=MODES, calendar_ticker_days=369,
            available_ticker_days=363, missing_no_evaluable=6, selected_mode=None,
            selection_reused_without_test_reselection=True, new_fit_samples_targets_weights_matrices_reconstructed=True,
            scheduler_ledgers_economics_reconstructed=True, all_three_monthly_fit_scores_sealed_before_ledgers=True,
            test_period_report_reconstructed=True).items():
        require(checks.get(name) == value, "Incomplete composite audit: " + name)
    missing = sorted([[t, d] for t in ("QQQ", "SPY") for d in ("20260401", "20260409", "20260415")])
    require(checks.get("missing_identities") == missing, "Missing identities differ")
    snapshots = {str(output / "executed_code" / n): h for n, h in receipt["dependencies"].items()}
    snapshots.update({str(output / "authorities/implementation_review.json"): AUDITOR_REVIEW_SHA,
                      str(output / "authorities/runtime_review.json"): receipt["runtime_review_sha256"]})
    require(result.get("execution_snapshots") == snapshots, "Exact fifteen audit snapshots required")
    require(read(output / "launch.json") == dict(scope=SCOPE, dependencies=receipt["dependencies"],
        snapshots=snapshots, runtime_review_sha256=receipt["runtime_review_sha256"],
        validation_audit_sha256=VALIDATION_SHA), "Auditor launch binding differs")
    verify(snapshots)
    flattened = {}
    for group in result["verified_files"].values():
        for path, value in group.items():
            require(path not in flattened or flattened[path] == value, "Conflicting audited files")
            flattened[path] = value
    for group in read(VALIDATION_AUDIT)["verified_files"].values():
        require(all(flattened.get(p) == h for p, h in group.items()), "Incomplete inherited audit inventory")
    verify(result_files)
    return result_files


def monitor(child, receipt, helper, preflight_sha):
    logs = Path(receipt["logs_root"])
    ended = False
    errors, samples = [], 0
    peak_rss = peak_private = None
    minimum = None
    started = time.monotonic()
    try:
        retained = helper.RetainedProcess(child)
        created = retained.creation_time()
        code_path = str(Path(__file__).resolve())
        authority = dict(monitor_code_sha256=receipt["files"][code_path],
            runtime_review_sha256=receipt["runtime_review_sha256"],
            supervisor_review_sha256=receipt["supervisor_review_sha256"],
            publication_commit=receipt["publication_commit"], preflight_sha256=preflight_sha)
        helper.publish(logs, "process.json", dict(status="PROCESS_HANDLE_RETAINED", pid=child.pid, creation_time=created,
            creation_time_source="GetProcessTimes_retained_Popen_handle", command=receipt["command"],
            monitor_started_utc=utc(), **authority))
        process_pin = {str(logs / "process.json"): sha(logs / "process.json")}
        import psutil
        try:
            process = psutil.Process(child.pid)
            require(abs(process.create_time() - created) < 0.001, "PID creation mismatch")
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
                value = observation()
                minimum = value if minimum is None else {k: min(minimum[k], v) for k, v in value.items()}
            except (psutil.Error, OSError, ValueError) as exc:
                errors.append(repr(exc))
        verify({**process_pin, code_path: authority["monitor_code_sha256"]})
        helper.publish(logs, "exit.json", dict(status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE",
            pid=child.pid, creation_time=created, exit_code=code,
            exit_code_source="GetExitCodeProcess_retained_Popen_handle", observed_utc=utc(),
            monitor_seconds=time.monotonic() - started, sample_count=samples, peak_sampled_rss_bytes=peak_rss,
            peak_sampled_private_bytes=peak_private, minimum_free_observed=minimum, monitor_errors=errors,
            process_receipt_sha256=process_pin[str(logs / "process.json")], **authority, retry=False))
        return dict(exit_code=code, files={**process_pin, str(logs / "exit.json"): sha(logs / "exit.json"),
                                         str(logs / "preflight.json"): preflight_sha})
    finally:
        if not ended:
            helper.drain_child(child)


def launch(receipt):
    require(receipt.get("status") == "PASS_AUDIT_SUPERVISOR_PREFLIGHT_NOT_EXECUTED", "Preflight required")
    verify(receipt["files"])
    helper = importlib.import_module("launch_monthly_test_20261023")
    verify(receipt["files"])
    runtime_path = Path(receipt["runtime_review"])
    runtime = read(runtime_path)
    output, logs = destinations(runtime, [runtime_path, SUPERVISOR_REVIEW, AUDITOR_REVIEW])
    require(str(output) == receipt["output_root"] and str(logs) == receipt["logs_root"]
            and receipt["command"] == command(runtime_path, output), "Fixed auditor command/destinations differ")
    with helper.overlay.os_lock(BASE / "monthly_test_index_v2_audit.lock", create=True), \
            helper.overlay.os_lock(MONTHLY / "run.lock", create=False):
        publication(receipt["publication_commit"], receipt["publication_files"])
        evidence = Evidence(runtime["allowed_read_roots"])
        evidence.files.update(receipt["files"])
        producer_closure(runtime, evidence, helper)
        verify(evidence.files)
        destinations(runtime, [runtime_path, SUPERVISOR_REVIEW, AUDITOR_REVIEW])
        logs.mkdir(parents=True, exist_ok=False)  # Durable one-claim, never deleted.
        helper.publish(logs, "preflight.json", receipt)
        preflight_sha = sha(logs / "preflight.json")
        env = os.environ.copy()
        env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        try:
            with (logs / "stdout.log").open("xb") as stdout, (logs / "stderr.log").open("xb") as stderr:
                verify(evidence.files)
                observed = observation()
                gate(observed)
                child = subprocess.Popen(receipt["command"], cwd=REPO, env=env, stdin=subprocess.DEVNULL,
                                         stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    helper.publish(logs, "admission.json", dict(**observed, minimum_free_bytes=MIN_FREE, utc=utc()))
                    monitored = monitor(child, receipt, helper, preflight_sha)
                finally:
                    helper.drain_child(child)
            require(monitored["exit_code"] == 0, "Auditor child did not exit zero")
            verify(monitored["files"])
            verify(evidence.files)
            audit_files = validate_audit(output, receipt)
            closure_files = {**monitored["files"], **audit_files}
            verify(closure_files)
            helper.publish(logs, "completion.json", dict(status="COMPLETE_MONTHLY_TEST_INDEX_V2_AUDIT_SUPERVISION",
                audit_path=str(output / "audit.json"), audit_sha256=audit_files[str(output / "audit.json")], exit_code=0,
                closure_files=closure_files, publication_commit=receipt["publication_commit"],
                supervisor_review_sha256=receipt["supervisor_review_sha256"],
                runtime_review_sha256=receipt["runtime_review_sha256"], completed_utc=utc(), retry=False))
            return 0
        except BaseException as exc:
            helper.publish(logs, "failure.json", dict(status="FAILED_OR_INTERRUPTED_PRESERVED", error=repr(exc), utc=utc(), retry=False))
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-review", type=Path, required=True)
    parser.add_argument("--runtime-review-sha256", required=True)
    parser.add_argument("--supervisor-review-sha256", required=True)
    parser.add_argument("--publication-commit", required=True)
    parser.add_argument("--execute-reviewed-audit", action="store_true")
    args = parser.parse_args()
    receipt = preflight(args.runtime_review, args.runtime_review_sha256, args.supervisor_review_sha256, args.publication_commit)
    if args.execute_reviewed_audit:
        return launch(receipt)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
