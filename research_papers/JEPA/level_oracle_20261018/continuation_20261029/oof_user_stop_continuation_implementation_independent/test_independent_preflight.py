"""New admission orchestration with artificial authorities and external helper stubs."""
from pathlib import Path
from types import SimpleNamespace
import copy
import hashlib
import importlib
import json
import shutil

import pytest


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.fixture(scope="module")
def trusted_boundary():
    s = importlib.import_module("launch_oof_pipeline_user_stop_continuation_20261029")
    old, ops, helper = s.operational_modules()
    pinned = json.loads((Path(__file__).parent / "final_implementation_map.json").read_text(encoding="utf-8"))
    return old, ops, helper, pinned["scientific_dependencies"]


@pytest.mark.parametrize("fault", [None, "prefix_schema", "cpu_mapping", "publication_omits_cpu", "publication_extra", "broad_read_root", "review_map"])
def test_actual_preflight_authority_schema_and_publication(monkeypatch, tmp_path, fault, trusted_boundary):
    s = importlib.import_module("launch_oof_pipeline_user_stop_continuation_20261029")
    real_here = s.HERE
    old, ops, helper, scientific_dependencies = trusted_boundary
    repository = tmp_path / "repository"
    here = repository / "research"
    here.mkdir(parents=True)
    local = tmp_path / "local"
    monthly, session = local / "monthly", local / "session"
    local_snapshot, repo_snapshot = local / "snapshot", here / "snapshot"
    old_logs, old_observer = local / "old_logs", local / "old_observer"
    for root in (monthly, session, local_snapshot, repo_snapshot, old_logs, old_observer):
        root.mkdir(parents=True)
    source_sha, tail_sha = "1" * 64, "2" * 64
    global_lock = local / "runtime.lock"
    scientific = dict(code=scientific_dependencies, months=s.MONTHS, monthly_root=str(monthly),
        session_root=str(session), coordination_lock=str(global_lock))
    original_request = write(here / "original_request.json", scientific)
    original_binding_value = dict(allowed_read_roots=[str(here), str(monthly), str(session)])
    original_binding = write(here / "original_binding.json", original_binding_value)
    files = {}
    for name in (Path(s.__file__).name, "test_launch_oof_pipeline_user_stop_continuation_20261029.py"):
        shutil.copyfile(real_here / name, here / name)
        files[name] = s.sha(here / name)
    files.update({Path(original_request["path"]).name: original_request["sha256"],
        Path(original_binding["path"]).name: original_binding["sha256"]})
    cpu = dict(status="PASS_FIRST_INSTRUCTION_CPU0_THREADS1", parent={"parent_cpu_affinity": [0]},
        child_observation={"mask": 1, "threads": ["1", "1", "1"]},
        code_sha256=files[Path(s.__file__).name], tests_sha256=files["test_launch_oof_pipeline_user_stop_continuation_20261029.py"])
    if fault == "cpu_mapping":
        cpu["code_sha256"] = "0" * 64
    cpu_ref = write(here / "cpu_evidence.json", cpu)
    review_value = dict(status="PASS_OOF_USER_STOP_CONTINUATION_IMPLEMENTATION_REVIEW", decision="CLEAR",
        scope="IMPLEMENTATION_ONLY", runtime_authorized=False, files=copy.deepcopy(files),
        cpu0_inheritance_test={"status": "PASS_FIRST_INSTRUCTION_CPU0_THREADS1", "evidence": cpu_ref})
    if fault == "review_map":
        review_value["files"]["foreign.py"] = "a" * 64
    review_ref = write(here / "implementation_review.json", review_value)
    authorization = write(here / "RESUMPTION_20261029.md", {"synthetic_authorization": True})
    manifest_ref = write(repo_snapshot / "snapshot_manifest.json", {"synthetic_snapshot_boundary": True})
    local_manifest = write(local_snapshot / "snapshot_manifest.json", {"synthetic_snapshot_boundary": True})
    local_result = write(local / "review_result.json", {"synthetic_independent_result": True})
    adopted = []
    phases = []
    for index, (month, stage) in enumerate((m, t) for m in s.MONTHS[:4] for t in ("correction", "replay")):
        row = dict(phase=[month, stage], start={"path": str(local / f"s{index}.json"), "sha256": "3" * 64},
            receipt={"path": str(local / f"r{index}.json"), "sha256": "4" * 64},
            closure={"path": str(local / f"c{index}.json"), "sha256": "5" * 64})
        adopted.append(row)
        phases.append(dict(index=index, month=month, stage=stage, start_sha256="3" * 64,
            receipt_sha256="4" * 64, completion_sha256="5" * 64))
    independent = dict(status="PASS_STOPPED_PREFIX_METADATA_AND_HASHES_ONLY", schema="INDEPENDENT_METADATA_HASH_REVIEW_V1",
        verdict="EIGHT_CLOSURES_INTEGRITY_VERIFIED_NOT_YET_ADOPTED", adoption_authorized_by_this_review=False,
        economics_interpreted=False, audit_full_h1_performed=False, failed_checks=0,
        request_sha256=original_request["sha256"], original_runtime_binding_sha256=original_binding["sha256"],
        final_receipt_sha256=tail_sha, source_admission_sha256=source_sha, original_exit_code=15,
        original_failure_preserved=True, closures={}, reviewed_phases=phases, review_result_source=local_result)
    if fault == "prefix_schema":
        independent["status"] = "CLEAR"
    independent_ref = write(here / "OOF_INTERRUPTION_INDEPENDENT_REVIEW_20261029.json", independent)
    # The implementation deliberately fixes this already published report hash.
    report = here / "OOF_INTERRUPTION_INDEPENDENT_REVIEW_20261029.md"
    shutil.copyfile(real_here / report.name, report)
    request_value = dict(version="OOF_USER_STOP_CONTINUATION_REQUEST_V1", status="REVIEWED_OOF_USER_STOP_CONTINUATION_REQUEST",
        runtime_authorized=True, original_request=original_request, original_binding=original_binding,
        authorization=authorization, snapshot_manifest=manifest_ref, independent_prefix_review=independent_ref,
        stopped_launch={}, expected_completed_phases=8, adopted_phases=adopted, tail_receipt_sha256=tail_sha,
        source_admission_sha256=source_sha, remaining_phases=s.REMAINING, preserved_root_locks={})
    request_ref = write(here / "request.json", request_value)
    binding_value = dict(version="OOF_USER_STOP_CONTINUATION_BINDING_V1", status="PASS_OOF_USER_STOP_CONTINUATION_RUNTIME_BINDING",
        request=request_ref, implementation_review=review_ref,
        allowed_read_roots=original_binding_value["allowed_read_roots"] + [str(local_snapshot), str(repo_snapshot)],
        logs_root=str(local / "new_logs"), observer_root=str(local / "new_observer"), snapshot_root=str(local_snapshot),
        repository_snapshot_root=str(repo_snapshot), future_audit_root=str(local / "future_audit"),
        future_audit_logs_root=str(local / "future_audit_logs"))
    published = {str(here / name): pin for name, pin in files.items()}
    for item in (request_ref, review_ref, cpu_ref, authorization, manifest_ref, independent_ref):
        published[item["path"]] = item["sha256"]
    published[str(report)] = s.sha(report)
    binding_value["published_files"] = copy.deepcopy(published)
    if fault == "publication_omits_cpu":
        binding_value["published_files"].pop(cpu_ref["path"])
    elif fault == "publication_extra":
        extra = write(here / "extra.json", {"unconsumed": True})
        binding_value["published_files"][extra["path"]] = extra["sha256"]
    elif fault == "broad_read_root":
        binding_value["allowed_read_roots"].append(str(local))
    binding_ref = write(here / "binding.json", binding_value)
    publication_calls = []

    def publication(commit, declared):
        assert commit == "6" * 40
        assert declared == {**published, binding_ref["path"]: binding_ref["sha256"]}
        assert all(Path(name).is_relative_to(repository) for name in declared)
        s.verify(declared)
        publication_calls.append(copy.deepcopy(declared))

    proxy = SimpleNamespace(absolute=old.absolute, inspect_consumed_identity=old.inspect_consumed_identity,
        MONTHLY_ROOT=monthly, SESSION_ROOT=session, upstream=lambda *args: None,
        request_admission=lambda *args: {"map_sha256": source_sha, "summary": {"synthetic": True}},
        protect_transitive_outputs=lambda *args: None, publication=publication, tree_files=old.tree_files)
    monkeypatch.setattr(s, "operational_modules", lambda: (proxy, ops, helper))
    monkeypatch.setattr(s, "implementation_files", lambda: (copy.deepcopy(files), copy.deepcopy(scientific_dependencies)))
    for name, value in dict(HERE=here, REPO=repository, REVIEW=Path(review_ref["path"]),
        ORIGINAL_REQUEST=Path(original_request["path"]), ORIGINAL_REQUEST_SHA=original_request["sha256"],
        ORIGINAL_BINDING=Path(original_binding["path"]), ORIGINAL_BINDING_SHA=original_binding["sha256"],
        SOURCE_SHA=source_sha, TAIL_SHA=tail_sha, GLOBAL_LOCK=global_lock).items():
        monkeypatch.setattr(s, name, value)
    roots = dict(roots=[], logs_root=binding_value["logs_root"], observer_root=binding_value["observer_root"])
    baseline = dict(sources={}, outputs={}, locks={}, compact={}, controls={}, closures={}, completed_phases=8)
    stopped = dict(files={}, logs_root=str(old_logs), observer_root=str(old_observer))
    monkeypatch.setattr(s, "destinations", lambda *args: copy.deepcopy(roots))
    monkeypatch.setattr(s, "validate_stopped_launch", lambda *args: copy.deepcopy(stopped))
    monkeypatch.setattr(s, "validate_adopted_prefix", lambda *args: copy.deepcopy(baseline))
    monkeypatch.setattr(s, "validate_snapshot", lambda *args: {manifest_ref["path"]: manifest_ref["sha256"], local_manifest["path"]: local_manifest["sha256"]})
    monkeypatch.setattr(s, "no_competitors", lambda: {"synthetic": True, "competing_processes": []})
    monkeypatch.setattr(s.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("Admission launched a child"))
    before = {str(p) for p in tmp_path.rglob("*")}
    args = (request_ref["path"], request_ref["sha256"], binding_ref["path"], binding_ref["sha256"], review_ref["sha256"], "6" * 40)
    if fault is None:
        result = s.preflight(*args)
        assert result["status"] == "PASS_OOF_USER_STOP_CONTINUATION_PREFLIGHT_NOT_EXECUTED" and result["executed"] is False
        assert publication_calls == [{**published, binding_ref["path"]: binding_ref["sha256"]}]
        assert local_result["path"] in result["files"] and local_result["path"] not in result["publication_files"]
        assert cpu_ref["path"] in result["publication_files"]
        assert result["command"][-1] == "--resume"
    else:
        with pytest.raises(ValueError):
            s.preflight(*args)
        assert publication_calls == []
    assert {str(p) for p in tmp_path.rglob("*")} == before
