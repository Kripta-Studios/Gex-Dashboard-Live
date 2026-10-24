"""Compact archive of a finished composite audit; root reviews before use.

Requires three externally supplied real closure hashes. No metrics, model,
matrix, raw or ledger payload is consumed; no auditor/producer is imported.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

BASE = Path("D:/GexResearchArtifacts/level_oracle_20261018")
HERE = Path(__file__).resolve().parent
AUDIT = BASE / "monthly_walk_forward_test_audit_20261024_01"
LOGS = BASE / "monthly_test_index_v2_audit_launch_20261024_01"
MONTHLY = BASE / "monthly_walk_forward_v1"
SESSION = BASE / "session_clock_dataset_v1"
OUT = HERE / "continuation_20261024/monthly_test_2026_audit"
PLAN = HERE / "MONTHLY_TEST_2026_AUDIT_ARCHIVE_PLAN_20261024.md"
STATUS = "PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES"
SCOPE = "VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1"
VALIDATION_SHA = "ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc"
CONTRACT_SHA = "7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f"
SOURCE_SHA = "678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9"
INDEX_SHA = "7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4"
AUDITOR_REVIEW_SHA = "493806fbc25a50a3333b4d2e65f3bd041bd30b30d5a10203d8c188c0520ee2b3"
MONTHS = [f"2025{m:02d}" for m in range(1, 13)] + [f"2026{m:02d}" for m in range(1, 7)]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def absolute(value):
    path = Path(value)
    require(path.is_absolute(), "Absolute authority path required")
    return path.resolve()


def mapping(value):
    result = {}
    for name, digest in value.items():
        path = str(absolute(name))
        require(path not in result or result[path] == digest, "Conflicting normalized hash")
        result[path] = digest
    return result


def utc(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None, "Timezone required")
    return result


def run(audit_sha, supervisor_sha, exit_sha):
    require(not OUT.exists(), "Use a fresh archive root")
    for root in (AUDIT, LOGS):
        require(not (root / "failure.json").exists(), "Failure coexists with closure")
    initial = {AUDIT / "audit.json": audit_sha, LOGS / "completion.json": supervisor_sha,
               LOGS / "exit.json": exit_sha}
    require(all(sha(p) == h for p, h in initial.items()), "External closure pin differs")
    audit, supervision, exited = (read(p) for p in initial)
    require(supervision.get("status") == "COMPLETE_MONTHLY_TEST_INDEX_V2_AUDIT_SUPERVISION"
            and supervision.get("exit_code") == 0 and supervision.get("retry") is False
            and absolute(supervision["audit_path"]) == (AUDIT / "audit.json").resolve()
            and supervision.get("audit_sha256") == audit_sha, "Supervisor closure differs")
    closure = mapping(supervision["closure_files"])
    closure_paths = {str((AUDIT / n).resolve()) for n in ("audit.json", "launch.json")}
    closure_paths |= {str((LOGS / n).resolve()) for n in ("process.json", "exit.json", "preflight.json")}
    require(set(closure) == closure_paths and closure[str((AUDIT / "audit.json").resolve())] == audit_sha
            and closure[str((LOGS / "exit.json").resolve())] == exit_sha, "Exact closure inventory required")
    require(all(sha(p) == h for p, h in closure.items()), "Closure member changed")
    process, preflight, launch = read(LOGS / "process.json"), read(LOGS / "preflight.json"), read(AUDIT / "launch.json")
    require(process.get("status") == "PROCESS_HANDLE_RETAINED"
            and process.get("creation_time_source") == "GetProcessTimes_retained_Popen_handle"
            and exited.get("status") == "PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE"
            and exited.get("exit_code_source") == "GetExitCodeProcess_retained_Popen_handle"
            and exited.get("exit_code") == 0 and exited.get("retry") is False
            and exited.get("pid") == process.get("pid")
            and exited.get("creation_time") == process.get("creation_time")
            and exited.get("process_receipt_sha256") == closure[str((LOGS / "process.json").resolve())],
            "Retained process identity/exit differs")
    require(utc(process["monitor_started_utc"]) <= utc(exited["observed_utc"])
            <= utc(supervision["completed_utc"]), "Closure chronology differs")
    require(preflight.get("status") == "PASS_AUDIT_SUPERVISOR_PREFLIGHT_NOT_EXECUTED"
            and absolute(preflight["output_root"]) == AUDIT.resolve()
            and absolute(preflight["logs_root"]) == LOGS.resolve()
            and process["command"] == preflight["command"], "Preflight destinations/command differ")
    for key in ("publication_commit", "supervisor_review_sha256", "runtime_review_sha256"):
        require(supervision[key] == preflight[key] == process[key] == exited[key], "Process authority differs: " + key)
    require(process["preflight_sha256"] == exited["preflight_sha256"] == sha(LOGS / "preflight.json"),
            "Process preflight pin differs")
    require(audit.get("status") == STATUS and audit.get("scope") == SCOPE
            and audit.get("development_seen") is True and audit.get("promotion_approved") is False,
            "Composite audit PASS required")
    binding = audit["binding"]
    require(absolute(binding["monthly_root"]) == MONTHLY.resolve()
            and absolute(binding["session_root"]) == SESSION.resolve()
            and binding["run_contract_sha256"] == CONTRACT_SHA and binding["completed_months"] == MONTHS
            and binding["session_audit_sha256"] == SOURCE_SHA and binding["index_sha256"] == INDEX_SHA,
            "Composite audit roots/contract/months differ")
    require(audit["prior_validation_audit"] == dict(
        path=str(BASE / "monthly_walk_forward_validation_audit_20261024_02/audit.json"),
        sha256=VALIDATION_SHA, scope="VALIDATION_2025", inventory_rehashed=True,
        reconstruction_inherited_not_repeated=True), "Prior validation inheritance differs")
    counts = dict(new_months=6, new_unique_fit_windows=12, models_used_test=13,
                  total_unique_fit_windows=36, calendar_ticker_days=369,
                  available_ticker_days=363, missing_no_evaluable=6)
    require(all(type(audit["audited"].get(k)) is int and audit["audited"][k] == v for k, v in counts.items()),
            "Audited scope counts differ")
    require(audit["audited"].get("modes") == ["static", "expanding", "rolling12"]
            and audit["audited"].get("selected_mode") is None
            and audit["audited"].get("missing_identities") == sorted(
                [[t, d] for t in ("QQQ", "SPY") for d in ("20260401", "20260409", "20260415")]),
            "Audited modes/freeze/missing identities differ")
    for key in ("selection_reused_without_test_reselection", "new_fit_samples_targets_weights_matrices_reconstructed",
                "scheduler_ledgers_economics_reconstructed", "all_three_monthly_fit_scores_sealed_before_ledgers",
                "test_period_report_reconstructed"):
        require(audit["audited"].get(key) is True, "Missing completed audit check: " + key)
    dependencies = preflight["dependencies"]
    require(len(dependencies) == 13 and all(Path(n).name == n for n in dependencies), "Thirteen basename dependencies required")
    expected_snapshots = {str((AUDIT / "executed_code" / n).resolve()): h for n, h in dependencies.items()}
    review_path = AUDIT / "authorities/implementation_review.json"
    runtime_path = AUDIT / "authorities/runtime_review.json"
    snapshots = mapping(audit["execution_snapshots"])
    require(len(snapshots) == 15 and set(snapshots) == set(expected_snapshots) | {str(review_path.resolve()), str(runtime_path.resolve())},
            "Exact fifteen audit snapshots required")
    require(all(snapshots[p] == h for p, h in expected_snapshots.items())
            and snapshots[str(review_path.resolve())] == AUDITOR_REVIEW_SHA
            and snapshots[str(runtime_path.resolve())] == preflight["runtime_review_sha256"]
            and audit["audit_script_sha256"] == dependencies["audit_monthly_walk_forward_test_index_v2.py"],
            "Executed audit code/runtime pins differ")
    require(launch == dict(scope=SCOPE, dependencies=dependencies, snapshots=audit["execution_snapshots"],
            runtime_review_sha256=preflight["runtime_review_sha256"], validation_audit_sha256=VALIDATION_SHA),
            "Audit launch differs")
    inventory = {}
    for group in audit["verified_files"].values():
        for p, h in mapping(group).items():
            require(p not in inventory or inventory[p] == h, "Conflicting audited inventory")
            inventory[p] = h
    prior_path = BASE / "monthly_walk_forward_validation_audit_20261024_02/audit.json"
    require(sha(prior_path) == VALIDATION_SHA, "Pinned prior audit changed")
    prior = read(prior_path)
    require(all(inventory.get(p) == h for group in prior["verified_files"].values()
                for p, h in mapping(group).items()), "Prior inventory missing from composite")
    planned = {}

    def plan(source, relative, expected):
        source = Path(source).resolve()
        require(source.is_file() and source.stat().st_size < 100_000_000, "Compact source missing or exceeds 100 MB")
        require(sha(source) == expected, "Compact source SHA differs")
        require(relative not in planned, "Duplicate archive destination")
        planned[relative] = (source, expected)

    for path, h in {**closure, str((LOGS / "completion.json").resolve()): supervisor_sha}.items():
        p = Path(path)
        plan(p, ("audit/" if p.parent == AUDIT.resolve() else "supervisor/") + p.name, h)
    for path, h in snapshots.items():
        p = Path(path)
        plan(p, "audit/" + p.relative_to(AUDIT.resolve()).as_posix(), h)
    require(all(sha(p) == h for p, h in snapshots.items()), "Audit snapshot changed")
    for name in ("admission.json", "stdout.log", "stderr.log"):
        plan(LOGS / name, "supervisor/" + name, sha(LOGS / name))
    for value, h in mapping(preflight["publication_files"]).items():
        p = Path(value)
        require(p.is_relative_to(HERE.resolve()) and p.suffix in (".py", ".md", ".json"),
                "Published code/authority outside code directory")
        plan(p, "code/" + p.relative_to(HERE.resolve()).as_posix(), h)
    models = {p: h for p, h in inventory.items() if Path(p).parent == (MONTHLY / "models").resolve() and Path(p).suffix == ".txt"}
    require(len(models) == 36, "Expected 36 already archived models")
    archives, archived_models = [], {}
    for name in ("monthly_validation_2025", "monthly_test_2026"):
        path = HERE / "continuation_20261024" / name / "MANIFEST.json"
        metadata = read(path)
        archives.append(dict(path=str(path), sha256=sha(path), model_payloads_rehashed=False))
        for entry in metadata["copies"]:
            original = str(absolute(entry["original_path"]))
            if original in models:
                require(entry["sha256"] == models[original], "Previously archived model differs from audit")
                copy_path = path.parent / entry["archive_path"]
                require(copy_path.is_file() and copy_path.stat().st_size == entry["bytes"],
                        "Previously archived model missing or size changed")
                archived_models[original] = dict(sha256=entry["sha256"],
                    archive_copy=str(copy_path), payload_rehashed=False)
    require(set(archived_models) == set(models), "Previously archived models incomplete")
    plan(Path(__file__), "archive_monthly_test_audit_20261024.py", sha(__file__))
    plan(PLAN, PLAN.name, sha(PLAN))
    OUT.mkdir(parents=True)
    copies = []
    for relative, (source, h) in sorted(planned.items()):
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        require(not target.exists(), "Archive target already exists")
        shutil.copyfile(source, target)
        require(sha(source) == h == sha(target), "Source/copy changed")
        copies.append(dict(original_path=str(source), archive_path=relative, sha256=h, bytes=source.stat().st_size))
    write(OUT / "LOCAL_REFERENCES.json", dict(
        full_inventory="audit/audit.json#verified_files", audited_inventory_files=len(inventory),
        inventory_payloads_rehashed_by_archive=False, prior_validation_audit=dict(path=str(prior_path), sha256=VALIDATION_SHA),
        previous_archives=archives, models=archived_models, model_copies_added=0,
        large_payload_copies=0, reference_scope="Metadata/hash-map comparison only; no model/matrix/raw/score/ledger payload reads."))
    for entry in copies:
        require(sha(entry["original_path"]) == entry["sha256"] == sha(OUT / entry["archive_path"]),
                "Compact source/copy changed before manifest")
    write(OUT / "MANIFEST.json", dict(status="COMPACT_COMPOSITE_MONTHLY_AUDIT_ARCHIVE",
        archived_utc=datetime.now(timezone.utc).isoformat(), audit_sha256=audit_sha,
        supervisor_completion_sha256=supervisor_sha, retained_exit_sha256=exit_sha,
        scope=SCOPE, copied_files=len(copies), copied_bytes=sum(x["bytes"] for x in copies), copies=copies,
        local_references_sha256=sha(OUT / "LOCAL_REFERENCES.json"), metrics_parsed=False,
        auditor_reexecuted=False, model_or_raw_payloads_copied=False,
        limitation="Given sealed scores; no refit/inference reproduced. This archive is not a second audit or performance report."))
    print(json.dumps(dict(status="ARCHIVE_COMPLETE", files=len(copies), manifest_sha256=sha(OUT / "MANIFEST.json"))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-sha256", required=True)
    parser.add_argument("--supervisor-completion-sha256", required=True)
    parser.add_argument("--retained-exit-sha256", required=True)
    args = parser.parse_args()
    run(args.audit_sha256, args.supervisor_completion_sha256, args.retained_exit_sha256)


if __name__ == "__main__":
    main()
