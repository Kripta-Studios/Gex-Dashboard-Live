"""Tiny metadata and text payload fixtures. No MonthlyInputs or scientific producers."""
from pathlib import Path
from types import SimpleNamespace
import json
import sys

import pytest

import launch_oof_pipeline_20261024 as supervisor
import launch_monthly_test_index_v2_audit_20261024 as ops
import test_launch_monthly_test_index_v2_audit_20261024 as prior_fixtures


@pytest.fixture(scope="module", autouse=True)
def resource_gate():
    ops.gate(ops.observation())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return dict(path=str(path), sha256=supervisor.sha(path))


@pytest.fixture
def authorities(tmp_path, monkeypatch):
    tmp_path = tmp_path.resolve()
    data = tmp_path / "metadata"
    monthly, session = data / "monthly", data / "session"
    monthly.mkdir(parents=True)
    session.mkdir()
    contract = write(monthly / "run_contract.json", {"synthetic": True})
    index = write(session / "index.parquet", {"synthetic_metadata_only": True})
    source = write(data / "source_audit.json", dict(status="PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT",
        binding=dict(engine_root=str(session), index_sha256=index["sha256"])))
    prior = write(data / "prior.json", dict(verified_files={"source": {source["path"]: source["sha256"]}}))
    for name, value in dict(MONTHLY=monthly, SESSION=session, CONTRACT_SHA=contract["sha256"],
        INDEX_SHA=index["sha256"], SOURCE_SHA=source["sha256"], SOURCE_AUDIT=Path(source["path"]),
        VALIDATION_AUDIT=Path(prior["path"]), VALIDATION_SHA=prior["sha256"]).items():
        monkeypatch.setattr(ops, name, value)
    monthly_runtime = write(data / "monthly_runtime.json", {"synthetic_runtime": True})
    monthly_review = write(data / "monthly_review.json", {"synthetic_review": True})
    output, logs = data / "monthly_audit", data / "monthly_logs"
    logs.mkdir()
    for name, value in dict(BASE=tmp_path, MONTHLY_ROOT=monthly, SESSION_ROOT=session,
        MONTHLY_RUNTIME=Path(monthly_runtime["path"]), MONTHLY_RUNTIME_SHA=monthly_runtime["sha256"],
        MONTHLY_REVIEW=Path(monthly_review["path"]), MONTHLY_REVIEW_SHA=monthly_review["sha256"],
        MONTHLY_OUTPUT=output, MONTHLY_LOGS=logs, OPERATIONAL_LOCK=tmp_path / "oof_pipeline_launch.lock",
        GLOBAL_LOCK=tmp_path / "oof_pipeline_runtime.lock", REVIEW=data / "supervisor_review.json").items():
        monkeypatch.setattr(supervisor, name, value)
    dependencies = supervisor.read(ops.AUDITOR_REVIEW)["dependencies"]
    upstream_receipt = dict(status="PASS_AUDIT_SUPERVISOR_PREFLIGHT_NOT_EXECUTED", output_root=str(output),
        dependencies=dependencies, runtime_review=monthly_runtime["path"], runtime_review_sha256=monthly_runtime["sha256"],
        supervisor_review_sha256=monthly_review["sha256"], publication_commit="a" * 40,
        command=ops.command(Path(monthly_runtime["path"]), output))
    prior_fixtures.audit_output.__wrapped__(upstream_receipt)
    preflight = write(logs / "preflight.json", upstream_receipt)
    identity = dict(monitor_code_sha256=supervisor.OPS_SHA, runtime_review_sha256=monthly_runtime["sha256"],
        supervisor_review_sha256=monthly_review["sha256"], publication_commit="a" * 40, preflight_sha256=preflight["sha256"])
    process = write(logs / "process.json", dict(status="PROCESS_HANDLE_RETAINED", pid=1073741824,
        creation_time=123.0, creation_time_source="GetProcessTimes_retained_Popen_handle", command=upstream_receipt["command"],
        monitor_started_utc="2026-10-24T00:00:00+00:00", **identity))
    exited = write(logs / "exit.json", dict(status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE", pid=1073741824,
        creation_time=123.0, exit_code=0, exit_code_source="GetExitCodeProcess_retained_Popen_handle",
        process_receipt_sha256=process["sha256"], observed_utc="2026-10-24T00:01:00+00:00", **identity))
    upstream = dict(preflight=preflight, process=process, exit=exited,
        audit_launch=dict(path=str(output / "launch.json"), sha256=supervisor.sha(output / "launch.json")),
        audit=dict(path=str(output / "audit.json"), sha256=supervisor.sha(output / "audit.json")))
    complete = dict(status="COMPLETE_MONTHLY_TEST_INDEX_V2_AUDIT_SUPERVISION", exit_code=0,
        closure_files={p["path"]: p["sha256"] for p in upstream.values()}, audit_path=upstream["audit"]["path"],
        audit_sha256=upstream["audit"]["sha256"], runtime_review_sha256=monthly_runtime["sha256"],
        supervisor_review_sha256=monthly_review["sha256"], publication_commit="a" * 40,
        completed_utc="2026-10-24T00:02:00+00:00")
    upstream["completion"] = write(logs / "completion.json", complete)
    code, deps = supervisor.implementation_files()
    review = write(supervisor.REVIEW, dict(status=supervisor.REVIEW_STATUS, decision="CLEAR",
        scope="IMPLEMENTATION_ONLY", runtime_authorized=False, files=code))
    request = dict(version="OOF_PIPELINE_RUNTIME_REQUEST_V1", status="REVIEWED_OOF_PIPELINE_RUNTIME_REQUEST",
        runtime_authorized=True, months=supervisor.MONTHS, coordination_lock=str(supervisor.GLOBAL_LOCK), code=deps,
        monthly_root=str(monthly), session_root=str(session), monthly_audit=upstream["audit"], session_audit=source,
        pipeline_root=str(tmp_path / "pipeline"), correction_root=str(tmp_path / "correction"),
        evaluation_roots={m: str(tmp_path / ("replay_" + m)) for m in supervisor.MONTHS})
    request_pin = write(data / "request.json", request)
    published = {str(supervisor.HERE / n): h for n, h in code.items()}
    published.update({request_pin["path"]: request_pin["sha256"], review["path"]: review["sha256"],
        str(supervisor.PIPELINE_REVIEW): supervisor.PIPELINE_REVIEW_SHA, str(supervisor.AUDITOR_REVIEW): supervisor.AUDITOR_REVIEW_SHA,
        str(supervisor.MONTHLY_PRODUCER_REVIEW): supervisor.MONTHLY_PRODUCER_REVIEW_SHA,
        monthly_runtime["path"]: monthly_runtime["sha256"], monthly_review["path"]: monthly_review["sha256"]})
    binding = dict(status=supervisor.BINDING_STATUS, request=request_pin, implementation_review=review,
        logs_root=str(tmp_path / "logs"), allowed_read_roots=[str(data), str(supervisor.HERE)],
        published_files=published, upstream=upstream)
    binding_pin = write(data / "binding.json", binding)
    calls = []
    monkeypatch.setattr(supervisor, "publication", lambda commit, files: calls.append((commit, files)))
    return SimpleNamespace(request=request, request_pin=request_pin, binding=binding, binding_pin=binding_pin,
        review_pin=review, data=data, calls=calls)


def admit(a):
    return supervisor.preflight(a.request_pin["path"], a.request_pin["sha256"], a.binding_pin["path"],
        a.binding_pin["sha256"], a.review_pin["sha256"], "b" * 40)


def test_complete_metadata_admission_no_output_or_scientific_import(authorities, monkeypatch):
    a = authorities
    original = supervisor.importlib.import_module
    imports = []
    def imported(name):
        imports.append(name)
        assert name == supervisor.OPS_NAME.removesuffix(".py")
        return original(name)
    monkeypatch.setattr(supervisor.importlib, "import_module", imported)
    before = {str(p) for p in a.data.parent.rglob("*")}
    receipt = admit(a)
    assert receipt["executed"] is False and len(receipt["dependencies"]) == 17
    assert len(receipt["output_roots"]) == 9
    assert before == {str(p) for p in a.data.parent.rglob("*")}
    assert len(a.calls) == 1 and imports == [supervisor.OPS_NAME.removesuffix(".py")]


@pytest.mark.parametrize("fault", ["exit_false", "exit_nonzero", "naive", "pid_bool", "creation_bool", "creation_nan", "missing_snapshot"])
def test_resigned_upstream_metadata_faults(authorities, fault):
    a = authorities
    u = a.binding["upstream"]
    target = "process" if fault in ("pid_bool", "creation_bool", "creation_nan") else ("audit" if fault == "missing_snapshot" else "exit")
    changed = supervisor.read(u[target]["path"])
    if fault == "exit_false":
        changed["exit_code"] = False
    elif fault == "exit_nonzero":
        changed["exit_code"] = 7
    elif fault == "naive":
        changed["observed_utc"] = "2026-10-24T00:01:00"
    elif fault == "pid_bool":
        changed["pid"] = True
    elif fault == "creation_nan":
        changed["creation_time"] = float("nan")
    elif fault == "creation_bool":
        changed["creation_time"] = True
    else:
        changed["execution_snapshots"].pop(next(iter(changed["execution_snapshots"])))
    u[target] = write(Path(u[target]["path"]), changed)
    if target == "process":
        exited = supervisor.read(u["exit"]["path"])
        exited.update(pid=changed["pid"], creation_time=changed["creation_time"], process_receipt_sha256=u["process"]["sha256"])
        u["exit"] = write(Path(u["exit"]["path"]), exited)
    if target == "audit":
        a.request["monthly_audit"] = u[target]
    complete = supervisor.read(u["completion"]["path"])
    complete["closure_files"] = {p["path"]: p["sha256"] for n, p in u.items() if n != "completion"}
    if target == "audit":
        complete["audit_sha256"] = u[target]["sha256"]
    u["completion"] = write(Path(u["completion"]["path"]), complete)
    with pytest.raises(ValueError):
        supervisor.upstream(a.request, a.binding, ops.Evidence(a.binding["allowed_read_roots"]), ops)


@pytest.mark.parametrize("name", ["run_contract.json", "index.parquet"])
def test_actual_contract_or_index_mutation_rejected(authorities, name):
    a = authorities
    root = Path(a.request["monthly_root"] if name == "run_contract.json" else a.request["session_root"])
    (root / name).write_bytes(b"mutated metadata fixture")
    with pytest.raises(ValueError, match="Pinned"):
        supervisor.upstream(a.request, a.binding, ops.Evidence(a.binding["allowed_read_roots"]), ops)


def test_external_pin_fails_before_import(authorities, monkeypatch):
    monkeypatch.setattr(supervisor.importlib, "import_module", lambda *a: pytest.fail("Early import"))
    a = authorities
    with pytest.raises(ValueError, match="Pinned"):
        supervisor.preflight(a.request_pin["path"], "0" * 64, a.binding_pin["path"], a.binding_pin["sha256"], a.review_pin["sha256"], "b" * 40)


def test_publication_rejects_changed_git_object(tmp_path, monkeypatch):
    path = tmp_path / "code.py"
    path.write_bytes(b"expected")
    monkeypatch.setattr(supervisor, "REPO", tmp_path)
    monkeypatch.setattr(supervisor.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=b"changed"))
    with pytest.raises(ValueError, match="Git object"):
        supervisor.publication("a" * 40, {str(path): supervisor.sha(path)})


def build_pipeline(a):
    request, request_sha = a.request, a.request_pin["sha256"]
    root, correction = Path(request["pipeline_root"]), Path(request["correction_root"])
    root.mkdir()
    (root / "request.json").write_bytes(Path(a.request_pin["path"]).read_bytes())
    write(root / "contract.json", dict(version="OOF_PIPELINE_V1", request_sha256=request_sha, code=request["code"], correction_layout="SHARED_CUMULATIVE"))
    adapter_names, replay_names, _ = supervisor.dependency_sets()
    adapter = {n: request["code"][n] for n in adapter_names}
    replay = {n: request["code"][n] for n in replay_names}
    prior, cumulative, closures = None, {}, {}
    for i, (month, stage) in enumerate((m, s) for m in supervisor.MONTHS for s in ("correction", "replay")):
        before = dict(cumulative)
        start = write(root / f"starts/{i:02d}.json", dict(request_sha256=request_sha, phase=[month, stage], previous_receipt_sha256=prior))
        if stage == "correction":
            inputs = write(correction / f"{month}.inputs.json", {"synthetic": True})
            closed = write(correction / f"{month}.complete.json", dict(status="COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS",
                target_month=month, monthly_audit_sha256=request["monthly_audit"]["sha256"], dependencies=adapter,
                target_labels_read=False, base_models_refitted=False, winner_selected=None, development_seen=True, inputs_sha256=inputs["sha256"]))
            cumulative.update({p["path"]: p["sha256"] for p in (inputs, closed)})
            closures[month] = dict(correction_completion_sha256=closed["sha256"])
        else:
            replay_root = Path(request["evaluation_roots"][month])
            correction_path = correction / f"{month}.complete.json"
            correction_sha = closures[month]["correction_completion_sha256"]
            files = {str(correction_path): correction_sha}
            for name in ("summary.json", "all_scores_and_controls.json", "extra_payload.json"):
                p = write(replay_root / name, {"synthetic_text_only": True})
                files[p["path"]] = p["sha256"]
            p = write(replay_root / "run_contract.json", dict(version="OOF_POLICY_REPLAY_V1", dependencies=replay,
                monthly_audit_sha256=request["monthly_audit"]["sha256"], correction_completion_sha256=correction_sha,
                target_month=month, threshold=0, winner_selected=None))
            files[p["path"]] = p["sha256"]
            closed = write(replay_root / "completion.json", dict(status="COMPLETE_FIXED_OOF_POLICY_MONTH", target_month=month,
                winner_selected=None, dependencies=replay, files=files, monthly_files={}))
            cumulative.update({p: h for p, h in files.items() if Path(p).is_relative_to(replay_root)})
            cumulative[closed["path"]] = closed["sha256"]
            closures[month]["evaluation_completion_sha256"] = closed["sha256"]
        receipt = write(root / f"receipts/{i:02d}.json", dict(status="COMPLETE_OOF_PIPELINE_PHASE", request_sha256=request_sha,
            phase=[month, stage], previous_receipt_sha256=prior, start_sha256=start["sha256"], completion_sha256=closed["sha256"],
            output_inventory=dict(cumulative), winner_selected=None, independent_audit_pending=True,
            new_output_bytes=sum(Path(p).stat().st_size for p in set(cumulative)-set(before)),
            cumulative_output_bytes=sum(Path(p).stat().st_size for p in cumulative)))
        prior = receipt["sha256"]
    write(root / "completion.json", dict(status="PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT", request_sha256=request_sha,
        last_receipt_sha256=prior, months=closures, winner_selected=None, technical_ready=False, promotion_approved=False, auditor_executed=False))


def test_complete_twelve_phase_metadata_and_output_hashes(authorities):
    build_pipeline(authorities)
    result = supervisor.validate_pipeline(authorities.request, authorities.request_pin["sha256"])
    assert result["output_count"] == 42
    assert len(result["compact_files"]) == 45


@pytest.mark.parametrize("fault", ["phase", "missing_receipt", "failure", "payload", "nested_lock", "extra_control", "premature", "start_hash"])
def test_pipeline_closure_faults(authorities, fault):
    a = authorities
    build_pipeline(a)
    root = Path(a.request["pipeline_root"])
    if fault == "missing_receipt":
        (root / "receipts/11.json").unlink()
    elif fault == "failure":
        write(root / "failures/one.json", {"synthetic": True})
    elif fault == "payload":
        (Path(a.request["evaluation_roots"]["202601"]) / "extra_payload.json").write_bytes(b"changed")
    elif fault == "nested_lock":
        write(Path(a.request["correction_root"]) / "nested/.lock", {})
    elif fault == "extra_control":
        write(root / "orphan.json", {})
    else:
        path = root / ("completion.json" if fault == "premature" else "receipts/01.json")
        value = supervisor.read(path)
        if fault == "premature":
            value["months"].pop("202606")
        elif fault == "phase":
            value["phase"] = ["202606", "replay"]
        else:
            value["start_sha256"] = "0" * 64
        write(path, value)
    with pytest.raises((ValueError, FileNotFoundError)):
        supervisor.validate_pipeline(a.request, a.request_pin["sha256"])


def test_root_lock_only_is_excluded(authorities):
    build_pipeline(authorities)
    for root in [Path(authorities.request["correction_root"]), *[Path(p) for p in authorities.request["evaluation_roots"].values()]]:
        (root / ".lock").write_bytes(b"0")
    supervisor.validate_pipeline(authorities.request, authorities.request_pin["sha256"])


def test_parent_link_rejected_before_destination_resolution(tmp_path, monkeypatch):
    linked = tmp_path / "linked"
    original = Path.is_junction
    monkeypatch.setattr(Path, "is_junction", lambda p: p == linked or original(p))
    with pytest.raises(ValueError, match="Linked"):
        supervisor.absolute(str(linked / "new_output"))


@pytest.mark.parametrize("fault", ["extra_local_digest", "correction_other_root"])
def test_resigned_phase_inventory_partition(authorities, fault):
    a = authorities
    build_pipeline(a)
    root = Path(a.request["pipeline_root"])
    replay = Path(a.request["evaluation_roots"]["202601"])
    if fault == "extra_local_digest":
        path = replay / "completion.json"
        closed = supervisor.read(path)
        closed["files"][str(replay / "extra_payload.json")] = "0" * 64
        changed = write(path, closed)
        receipt_path = root / "receipts/01.json"
        receipt = supervisor.read(receipt_path)
        receipt["completion_sha256"] = changed["sha256"]
        receipt["output_inventory"][str(path)] = changed["sha256"]
        message = "Replay local output pin"
    else:
        receipt_path = root / "receipts/00.json"
        receipt = supervisor.read(receipt_path)
        path = replay / "extra_payload.json"
        receipt["output_inventory"][str(path)] = supervisor.sha(path)
        message = "Correction phase writes"
    write(receipt_path, receipt)
    with pytest.raises(ValueError, match=message):
        supervisor.validate_pipeline(a.request, a.request_pin["sha256"])


def test_simulated_junction_after_inventory_before_hash(authorities, monkeypatch):
    a = authorities
    build_pipeline(a)
    target_parent = Path(a.request["evaluation_roots"]["202601"])
    last = Path(a.request["evaluation_roots"]["202606"])
    redirected = False
    original_tree, original_junction = supervisor.tree_files, Path.is_junction
    def tree(root, exclude_root_lock=False):
        nonlocal redirected
        result = original_tree(root, exclude_root_lock)
        if root == last:
            redirected = True
        return result
    monkeypatch.setattr(supervisor, "tree_files", tree)
    monkeypatch.setattr(Path, "is_junction", lambda p: (redirected and p == target_parent) or original_junction(p))
    with pytest.raises(ValueError, match="Linked"):
        supervisor.validate_pipeline(a.request, a.request_pin["sha256"])


@pytest.mark.parametrize("fault", ["receipt_outputs", "simulated_parent_junction"])
def test_destinations_revalidated_between_preflight_and_launch(authorities, monkeypatch, fault):
    receipt = admit(authorities)
    if fault == "receipt_outputs":
        receipt["output_roots"][0] += "_changed"
    else:
        parent = Path(authorities.request["pipeline_root"]).parent
        original = Path.is_junction
        monkeypatch.setattr(Path, "is_junction", lambda p: p == parent or original(p))
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *a, **k: pytest.fail("Redirected output admitted"))
    with pytest.raises(ValueError, match="outputs differ|Linked"):
        supervisor.launch(receipt)


@pytest.mark.parametrize("fault", [None, "preflight", "late_failure", "exit7"])
def test_launch_retained_exit_claim_gate_and_distinct_lock(authorities, monkeypatch, fault):
    import launch_monthly_test_20261023 as helper
    a = authorities
    receipt = admit(a)
    logs = Path(receipt["logs_root"])
    original_popen = supervisor.subprocess.Popen
    events = []
    def observation():
        events.append("gate")
        return dict(available_ram_bytes=2_000_000_000, free_commit_bytes=2_000_000_000)
    def child(argv, **kwargs):
        assert argv == receipt["command"] and events[-1] == "gate"
        events.append("popen")
        # If parent incorrectly held pipeline's lock this exact acquisition would fail.
        with helper.overlay.os_lock(supervisor.GLOBAL_LOCK, create=True):
            pass
        build_pipeline(a)
        if fault == "preflight":
            write(logs / "preflight.json", {"mutated": True})
        elif fault == "late_failure":
            write(Path(a.request["pipeline_root"]) / "failure.json", {})
        return original_popen([sys.executable, "-c", "raise SystemExit(7)" if fault == "exit7" else "pass"], **kwargs)
    monkeypatch.setattr(ops, "observation", observation)
    monkeypatch.setattr(supervisor.subprocess, "Popen", child)
    if fault is None:
        assert supervisor.launch(receipt) == 0
        closed = supervisor.read(logs / "completion.json")
        supervisor.verify(closed["process_files"])
        assert closed["auditor_executed"] is False
    else:
        with pytest.raises(ValueError):
            supervisor.launch(receipt)
        assert not (logs / "completion.json").exists() and (logs / "failure.json").exists()
    assert supervisor.read(logs / "exit.json")["exit_code"] == (7 if fault == "exit7" else 0)
    with pytest.raises(ValueError, match="Fresh"):
        supervisor.launch(receipt)
    assert events.count("popen") == 1


def test_low_commit_never_spawns(authorities, monkeypatch):
    receipt = admit(authorities)
    monkeypatch.setattr(ops, "observation", lambda: dict(available_ram_bytes=3_000_000_000, free_commit_bytes=1_999_999_999))
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *a, **k: pytest.fail("Gate bypass"))
    with pytest.raises(ValueError, match="gate"):
        supervisor.launch(receipt)
    assert Path(receipt["logs_root"], "failure.json").exists()


def test_monitor_init_failure_drains_and_never_fakes_exit(tmp_path):
    drained = []
    def broken(child):
        raise OSError("synthetic retained handle error")
    helper = SimpleNamespace(RetainedProcess=broken, drain_child=lambda child: drained.append(child))
    child = object()
    with pytest.raises(OSError):
        supervisor.monitor(child, {"logs_root": str(tmp_path)}, helper, ops, "0" * 64)
    assert drained == [child] and not (tmp_path / "exit.json").exists()
