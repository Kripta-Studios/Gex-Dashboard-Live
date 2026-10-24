"""Metadata-only proposal builder. Never emits runtime PASS or executes a child."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

BASE = Path("D:/GexResearchArtifacts/level_oracle_20261018")
CODE = Path(__file__).resolve().parents[0]  # Replaced only by required explicit --code argument.
PUBLISHED_COMMIT = "52b53f8f8e9931f2667b7837898c2b6b6abf5352"
SUPERVISOR_REVIEW_SHA = "e38ae0fb7ebfc3d5841fe87052d00605f58cba21a8ba987341d0f307ede9e432"
AUDITOR_REVIEW_SHA = "493806fbc25a50a3333b4d2e65f3bd041bd30b30d5a10203d8c188c0520ee2b3"
PRODUCER_REVIEW_SHA = "49a3590504c74c06dc5a9b830bcf71b7472dbecae2ab267218aaa22aa2dd0280"
PRODUCER_RUNTIME_SHA = "1c6072a871d7d4cbcabc7e82dbbbbdb28d5767ff083571638f956d92250b557b"
CONTRACT_SHA = "7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f"
PRIOR_SHA = "ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc"
SOURCE_SHA = "678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9"
INDEX_SHA = "7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4"
FREEZE_SHA = "df9a490d310d86a040e0ca9e6ad5b07c64d3474b9c71ce83e445309511fa9237"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pin(path, expected=None):
    actual = sha(path)
    require(expected is None or actual == expected, "Pinned metadata/code changed: " + str(path))
    return dict(path=str(path), sha256=actual)


def collect(code, closed):
    code = code.resolve()
    monthly = BASE / "monthly_walk_forward_v1"
    session = BASE / "session_clock_dataset_v1"
    prior = BASE / "monthly_walk_forward_validation_audit_20261024_02/audit.json"
    source = BASE / "session_clock_dataset_v1_audit/audit.json"
    runtime_root = BASE / "monthly_test_resource_overlay_20261024_01"
    logs = BASE / "monthly_test_launch_20261024_01"
    review = code / "MONTHLY_TEST_INDEX_V2_AUDIT_LAUNCH_REVIEW_20261024.json"
    auditor_review = code / "MONTHLY_TEST_INDEX_AUDIT_V2_REVIEW_20261024.json"
    producer_review = code / "MONTHLY_TEST_RESOURCE_OVERLAY_REVIEW_20261023.json"
    producer_runtime = code / "MONTHLY_TEST_RESOURCE_RUNTIME_REVIEW_20261024_01.json"
    fixed = {review: SUPERVISOR_REVIEW_SHA, auditor_review: AUDITOR_REVIEW_SHA,
        producer_review: PRODUCER_REVIEW_SHA, producer_runtime: PRODUCER_RUNTIME_SHA,
        monthly / "run_contract.json": CONTRACT_SHA, prior: PRIOR_SHA, source: SOURCE_SHA,
        monthly / "validation_freeze.json": FREEZE_SHA}
    observed = {str(path): pin(path, expected)["sha256"] for path, expected in fixed.items()}
    implementation = read(review)
    require(implementation["status"] == "PASS_MONTHLY_TEST_INDEX_V2_AUDIT_LAUNCH_IMPLEMENTATION_REVIEW"
        and implementation["decision"] == "CLEAR" and implementation["runtime_authorized"] is False,
        "Supervisor implementation authority differs")
    files = implementation["files"]
    require(len(files) == 31 and all(Path(n).name == n for n in files), "Exact 31 code members required")
    for name, expected in files.items():
        observed[str(code / name)] = pin(code / name, expected)["sha256"]
    dependencies = read(auditor_review)["dependencies"]
    require(len(dependencies) == 13, "Exact thirteen extension dependencies required")
    published = {str(code / name): digest for name, digest in files.items()}
    published.update({str(review): SUPERVISOR_REVIEW_SHA, str(auditor_review): AUDITOR_REVIEW_SHA,
        str(producer_review): PRODUCER_REVIEW_SHA, str(producer_runtime): PRODUCER_RUNTIME_SHA})
    require(len(published) == 35, "Exact 35 publication members required")
    roots = [code, monthly, session, source.parent, prior.parent, BASE / "engine_v1", BASE / "features_v1", runtime_root, logs]
    require(all(p.is_dir() for p in roots), "Read root missing")
    inherited = read(prior)["verified_files"]
    inherited_count = 0
    for group in inherited.values():
        for value in group:
            path = Path(value).resolve()
            require(any(path.is_relative_to(root) for root in roots), "Inherited reference outside roots")
            inherited_count += 1
    output = BASE / "monthly_walk_forward_test_audit_20261024_01"
    audit_logs = BASE / "monthly_test_index_v2_audit_launch_20261024_01"
    for path in (output, audit_logs):
        require(not path.exists(), "Proposed output already exists")
        require(all(not path.is_relative_to(root) and not root.is_relative_to(path) for root in roots), "Output overlaps input")
    require(not output.is_relative_to(audit_logs) and not audit_logs.is_relative_to(output), "Outputs overlap")
    binding_path = logs / "process_binding.json"
    monitor_path = logs / "monitor_open.json"
    launch_path = runtime_root / "launch.json"
    binding, monitor, launch = read(binding_path), read(monitor_path), read(launch_path)
    binding_pin, monitor_pin, launch_pin = pin(binding_path), pin(monitor_path), pin(launch_path)
    require(monitor["status"] == "PROCESS_HANDLE_RETAINED" and binding["pid"] == monitor["pid"] == launch["pid"]
        and binding["creation_time"] == monitor["creation_time"] and binding["command"] == monitor["command"]
        and monitor["process_receipt_sha256"] == binding_pin["sha256"], "Producer open identity differs")
    monitor_code = code / "launch_monthly_test_20261023.py"
    monitor_code_pin = pin(monitor_code, files[monitor_code.name])
    require(monitor["monitor_code_sha256"] == monitor_code_pin["sha256"], "Monitor code differs")
    members = dict(process_binding=binding_pin, monitor_open=monitor_pin, monitored_exit=None,
        runtime_launch=launch_pin, monitor_code=monitor_code_pin)
    pending = []
    paths = dict(process_chain=logs / "process_chain.json", monitored_exit=logs / "monitored_exit.json",
        runtime_completion=runtime_root / "completion.json")
    for name, path in paths.items():
        if not path.exists():
            pending.append(dict(member=name, path=str(path)))
    producer = dict(runtime_root=str(runtime_root), command=binding["command"], process_chain=None,
        process_members=members, runtime_completion=None, runtime_review=pin(producer_runtime, PRODUCER_RUNTIME_SHA))
    if closed:
        require(not pending, "Real producer closure still absent")
        chain, exited, completion = (read(paths[n]) for n in ("process_chain", "monitored_exit", "runtime_completion"))
        members["monitored_exit"] = pin(paths["monitored_exit"])
        if "source_launch" in chain["members"]:
            original = chain["members"]["source_launch"]
            original_path = Path(original["path"]).resolve()
            require(any(original_path.is_relative_to(root) for root in roots), "Normalized launch outside roots")
            members["source_launch"] = pin(original_path, original["sha256"])
        require(chain["status"] == "PROCESS_CHAIN_RECORDED" and chain["members"] == members
            and Path(chain["runtime_root"]).resolve() == runtime_root, "Process chain membership differs")
        require(exited["status"] == "PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE" and exited["exit_code"] == 0
            and exited["pid"] == binding["pid"] and exited["creation_time"] == binding["creation_time"]
            and exited["process_receipt_sha256"] == binding_pin["sha256"], "Retained exit zero absent")
        require(completion["status"] == "COMPLETE_MONTHLY_TEST_RESOURCE_OVERLAY"
            and completion["original_run_contract_sha256"] == CONTRACT_SHA
            and completion["validation_audit_sha256"] == PRIOR_SHA
            and completion["runtime_review_sha256"] == PRODUCER_RUNTIME_SHA
            and completion["selected_mode"] is None and completion["scientific_inputs_changed"] is False,
            "Runtime completion binding differs")
        parse = datetime.fromisoformat
        require(parse(launch["started_utc"]) < parse(completion["completed_utc"]) <= parse(exited["observed_utc"]), "Closure chronology differs")
        actual_members = {str(p) for p in runtime_root.rglob("*") if p.is_file() and p != paths["runtime_completion"]}
        require(set(completion["runtime_members"]) == actual_members, "Runtime members differ")
        for value, expected in completion["runtime_members"].items():
            path = Path(value).resolve()
            require(path.is_relative_to(runtime_root), "Runtime member escaped")
            observed[str(path)] = pin(path, expected)["sha256"]
        require(completion["preserved_checkpoints"] == launch["preserved_checkpoints"], "Preserved checkpoint metadata differs")
        final_paths = {str(p) for p in monthly.rglob("*.complete.json")}
        for pattern in ("*.txt", "*.fit_started.json"):
            final_paths.update(str(p) for p in (monthly / "models").glob(pattern))
        final_paths.update(str(p) for p in (monthly / "executed_code").iterdir() if p.is_file())
        final_paths.add(str(monthly / "run_contract.json"))
        require(set(completion["final_checkpoints"]) == final_paths, "Final checkpoint membership differs")
        producer["process_chain"] = pin(paths["process_chain"])
        producer["runtime_completion"] = pin(paths["runtime_completion"])
    science_path = monthly / "completion.json"
    science = read(science_path)
    require(science["status"] == "COMPLETE" and science["evaluated_months"] == 18
        and science["unique_fit_windows"] == 36 and science["selected_mode"] is None
        and science["development_seen"] is True and science["promotion_approved"] is False, "Scientific closure differs")
    proposal = dict(status="PENDING_INDEPENDENT_RUNTIME_REVIEW", scope="VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1",
        dependencies=dependencies, binding=dict(monthly_root=str(monthly), source_audit=str(source), validation_audit=str(prior),
            validation_audit_sha256=PRIOR_SHA, implementation_review_sha256=AUDITOR_REVIEW_SHA,
            run_contract_sha256=CONTRACT_SHA, source_audit_sha256=SOURCE_SHA, index_sha256=INDEX_SHA,
            session_root=str(session), validation_freeze_sha256=FREEZE_SHA), allowed_read_roots=[str(p) for p in roots],
        producer=producer, launch_binding=dict(status="PENDING_INDEPENDENT_ONE_SHOT_REVIEW",
            output_root=str(output), logs_root=str(audit_logs), supervisor_review=pin(review, SUPERVISOR_REVIEW_SHA), published_files=published))
    return dict(status="DRAFT_NOT_RUNTIME_AUTHORITY", runtime_authorized=False,
        captured_utc=datetime.now(timezone.utc).isoformat(), code_publication_commit=PUBLISHED_COMMIT,
        proposed_final_path=str(code / "MONTHLY_TEST_INDEX_V2_AUDIT_RUNTIME_REVIEW_20261024_01.json"),
        pending=pending, closed_metadata_checked=closed, proposed_runtime=proposal,
        scientific_completion=pin(science_path), inherited_reference_count=inherited_count,
        verified_small_files=observed, limits=["No metric payloads or arrays opened.",
            "No auditor constructor, supervisor preflight or child executed.",
            "Inherited sources and final model/input files are metadata references only here; full rehash belongs to published supervisor/auditor.",
            "No runtime PASS emitted. Final authority requires independent review, exact publication and root launch decision."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--closed-metadata", action="store_true")
    args = parser.parse_args()
    require(args.output.resolve().parent == Path(__file__).resolve().parent, "Draft must remain in preparation root")
    require(not args.output.exists(), "Never overwrite a draft")
    value = collect(args.code, args.closed_metadata)
    value["builder_sha256"] = sha(Path(__file__).resolve())
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    print(json.dumps(dict(status=value["status"],pending=value["pending"],sha256=sha(args.output)),indent=2))


if __name__ == "__main__":
    main()
