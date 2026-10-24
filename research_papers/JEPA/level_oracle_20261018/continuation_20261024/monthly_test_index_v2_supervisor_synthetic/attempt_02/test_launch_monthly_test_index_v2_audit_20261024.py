"""Small artificial receipts/models only; no market auditor child."""
from copy import deepcopy
from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

import launch_monthly_test_index_v2_audit_20261024 as supervisor


@pytest.fixture(scope="module", autouse=True)
def actual_resource_gate():
    supervisor.gate(supervisor.observation())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return {"path": str(path), "sha256": supervisor.sha(path)}


def free():
    return dict(available_ram_bytes=2_000_000_000, free_commit_bytes=2_000_000_000)


def test_gate_inclusive_both_limits_and_bool_rejected():
    supervisor.gate(free())
    for name in free():
        for value in (1_999_999_999, True, None):
            observed = free()
            observed[name] = value
            with pytest.raises(ValueError, match="gate"):
                supervisor.gate(observed)


@pytest.mark.parametrize("key", ["../escape", "/rooted", "C:/absolute", "x//y", "x/./y", "x ", "x:ads", "\\\\server\\share"])
def test_unsafe_marker_keys_rejected(tmp_path, key):
    with pytest.raises(ValueError, match="Unsafe|escaped"):
        supervisor.safe_members(tmp_path, {key: "a" * 64})


def test_marker_alias_collision_rejected(tmp_path):
    with pytest.raises(ValueError, match="collision"):
        supervisor.safe_members(tmp_path, {"dir/file": "a" * 64, "DIR\\FILE": "a" * 64})


def test_exact_git_objects_required(tmp_path, monkeypatch):
    monkeypatch.setattr(supervisor, "REPO", tmp_path)
    file = tmp_path / "code.py"
    file.write_bytes(b"expected")
    monkeypatch.setattr(supervisor.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=b"changed"))
    with pytest.raises(ValueError, match="Git object"):
        supervisor.publication("a" * 40, {file: supervisor.sha(file)})


def test_external_runtime_pin_fails_before_import(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime.json"
    runtime.write_bytes(b"{}")
    monkeypatch.setattr(supervisor, "observation", free)
    monkeypatch.setattr(supervisor.importlib, "import_module", lambda *a: pytest.fail("Unpinned import"))
    with pytest.raises(ValueError, match="Pinned bytes"):
        supervisor.preflight(runtime, "0" * 64, "a" * 64, "b" * 40)


def test_default_cli_never_launches(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["test", "--runtime-review", "synthetic.json",
        "--runtime-review-sha256", "a" * 64, "--supervisor-review-sha256", "b" * 64,
        "--publication-commit", "c" * 40])
    monkeypatch.setattr(supervisor, "preflight", lambda *a: {"synthetic": True})
    monkeypatch.setattr(supervisor, "launch", lambda *a: pytest.fail("Unexpected execution"))
    assert supervisor.main() == 0
    assert json.loads(capsys.readouterr().out) == {"synthetic": True}


def test_fresh_disjoint_destinations(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    runtime = dict(allowed_read_roots=[str(source)], launch_binding={
        "output_root": str(tmp_path / "audit"), "logs_root": str(tmp_path / "logs")})
    supervisor.destinations(runtime, [])
    for target in (source / "inside", source.parent):
        changed = deepcopy(runtime)
        changed["launch_binding"]["output_root"] = str(target)
        with pytest.raises(ValueError, match="Fresh|overlaps"):
            supervisor.destinations(changed, [])
    changed = deepcopy(runtime)
    changed["launch_binding"]["logs_root"] = changed["launch_binding"]["output_root"]
    with pytest.raises(ValueError, match="Outputs overlap"):
        supervisor.destinations(changed, [])


@pytest.fixture
def science(tmp_path, monkeypatch):
    data = tmp_path / "sources"
    root = data / "monthly"
    root.mkdir(parents=True)
    monkeypatch.setattr(supervisor, "MONTHLY", root)
    evidence = supervisor.Evidence([str(data)])

    def seal(name, paths, extra=None):
        value = dict(status="COMPLETE", binding=supervisor.CONTRACT_SHA,
            files={str(p.relative_to(root)): supervisor.sha(p) for p in paths}, extra=extra or {})
        pin = write(root / (name + ".complete.json"), value)
        evidence.file(pin["path"], pin["sha256"])
        return pin

    for key in supervisor.fit_keys(2025) | supervisor.fit_keys(2026):
        model = root / f"models/{key}.txt"
        model.parent.mkdir(exist_ok=True)
        model.write_text("SYNTHETIC MODEL NEVER INFERRED", encoding="utf-8")
        started = root / f"models/{key}.fit_started.json"
        write(started, {"synthetic": True})
        seal("models/" + key, [model, started])
        inputs = root / f"fits/{key}/inputs.json"
        write(inputs, {"synthetic": True})
        seal(f"fits/{key}/inputs", [inputs])
    for month in supervisor.MONTHS:
        for kind in ("daily", "economics", "predictions"):
            path = root / f"months/{month}/{kind}.json"
            write(path, {"synthetic": True})
            extra = dict(fit_keys=sorted(["train_20230101_20250101_exclusive",
                f"train_20230101_{month}01_exclusive", f"train_2025{month[4:]}01_{month}01_exclusive"]), labels_read=False)
            seal(f"months/{month}/{kind}", [path], extra)
    for name in ("reports/2025", "reports/2026", "validation_freeze"):
        path = root / (name + ".json")
        write(path, {"synthetic": True})
        seal(name, [path])
    completion = dict(status="COMPLETE", modes=supervisor.MODES, evaluated_months=18,
        unique_fit_windows=36, selected_mode=None, development_seen=True, promotion_approved=False,
        report_hashes={str(y): supervisor.sha(root / f"reports/{y}.json") for y in (2025, 2026)})
    write(root / "completion.json", completion)
    seal("completion", [root / "completion.json"])
    write(root / "run_contract.json", {"synthetic": True})
    (root / "executed_code").mkdir()
    return SimpleNamespace(root=root, data=data, evidence=evidence, seal=seal, completion=completion)


def test_all_36_models_and_18_months_close_without_scores(science):
    supervisor.science_closure(science.evidence, science.completion)
    assert len(supervisor.fit_keys(2025)) == 24
    assert len(supervisor.fit_keys(2025) | supervisor.fit_keys(2026)) == 36


@pytest.mark.parametrize("fault", ["missing_model", "extra_model", "late_selection", "missing_fit_key"])
def test_scientific_closure_failures(science, fault):
    root = science.root
    completion = deepcopy(science.completion)
    if fault == "missing_model":
        next((root / "models").glob("*.txt")).unlink()
    elif fault == "extra_model":
        (root / "models/undeclared.txt").write_text("synthetic")
    elif fault == "late_selection":
        completion["selected_mode"] = "expanding"
    else:
        path = root / "months/202601/predictions.complete.json"
        payload = supervisor.read(path)
        payload["extra"]["fit_keys"].pop()
        write(path, payload)
        science.evidence.files[str(path)] = supervisor.sha(path)
    with pytest.raises(ValueError, match="models|closure|fit keys"):
        supervisor.science_closure(science.evidence, completion)


@pytest.fixture
def producer(science, monkeypatch):
    import launch_monthly_test_20261023 as helper

    data, root = science.data, science.root
    runtime_root, logs = data / "runtime", data / "producer_logs"
    runtime_root.mkdir()
    logs.mkdir()
    monkeypatch.setattr(helper.overlay, "SCIENTIFIC_ROOT", root)
    monkeypatch.setattr(helper.overlay, "ROOT", data)
    monkeypatch.setattr(helper.overlay, "RUN_CONTRACT_SHA", supervisor.CONTRACT_SHA)
    producer_review = data / "producer_review.json"
    write(producer_review, {"synthetic": True})
    monkeypatch.setattr(supervisor, "PRODUCER_REVIEW", producer_review)
    monkeypatch.setattr(supervisor, "PRODUCER_REVIEW_SHA", supervisor.sha(producer_review))
    expectations = helper.overlay.review_expectations()
    runtime_file = data / "producer_runtime.json"
    runtime_value = dict(status="PASS_MONTHLY_TEST_RESOURCE_RUNTIME_REVIEW", scope="test",
        original_run_contract_sha256=supervisor.CONTRACT_SHA, scientific_root=str(root),
        implementation_review_sha256=supervisor.PRODUCER_REVIEW_SHA, review_expectations=expectations,
        validation={"audit": {"path": str(supervisor.VALIDATION_AUDIT), "sha256": supervisor.VALIDATION_SHA},
                    "freeze": {"path": str(root / "validation_freeze.json"), "sha256": supervisor.FREEZE_SHA}},
        launch_binding={"runtime_root": str(runtime_root)})
    runtime_pin = write(runtime_file, runtime_value)
    monkeypatch.setattr(supervisor, "PRODUCER_RUNTIME_SHA", runtime_pin["sha256"])
    snapshots = {}
    for name in expectations["files"]:
        target = runtime_root / "executed_code" / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes((supervisor.CODE / name).read_bytes())
        snapshots[str(target)] = supervisor.sha(target)
    for name, source in [("implementation_review.json", producer_review), ("runtime_review.json", runtime_file)]:
        target = runtime_root / "authorities" / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(source.read_bytes())
        snapshots[str(target)] = supervisor.sha(target)
    final_paths = set(root.rglob("*.complete.json")) | set((root / "models").glob("*.txt")) | set((root / "models").glob("*.fit_started.json"))
    final_paths.add(root / "run_contract.json")
    final = {str(p): supervisor.sha(p) for p in final_paths}
    preserved = {path: value for path, value in final.items() if "/2026" not in path.replace("\\", "/")}
    command = [sys.executable, "-u", str(supervisor.CODE / "run_monthly_test_resource_overlay.py"), "--runtime-root", str(runtime_root)]
    launch = dict(status="MONTHLY_TEST_RESOURCE_OVERLAY_STARTED", pid=1073741824,
        original_argv=helper.overlay.original_argv(), original_run_contract_sha256=supervisor.CONTRACT_SHA,
        scientific_inputs_changed=False, review=expectations, validation_audit_sha256=supervisor.VALIDATION_SHA,
        implementation_review_sha256=supervisor.PRODUCER_REVIEW_SHA, runtime_review_sha256=runtime_pin["sha256"],
        started_utc="2026-10-24T00:00:00+00:00", snapshots=snapshots, preserved_checkpoints=preserved)
    launch_pin = write(runtime_root / "launch.json", launch)
    binding = dict(pid=1073741824, creation_time=123.0, command=command)
    binding_pin = write(logs / "binding.json", binding)
    opened = dict(status="PROCESS_HANDLE_RETAINED", pid=binding["pid"], creation_time=123.0, command=command,
        monitor_started_utc="2026-10-24T00:00:00+00:00", process_receipt_sha256=binding_pin["sha256"],
        monitor_code_sha256=supervisor.HELPER_PINS["launch_monthly_test_20261023.py"])
    exited = dict(status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE", pid=binding["pid"], creation_time=123.0,
        observed_utc="2026-10-24T00:02:00+00:00", process_receipt_sha256=binding_pin["sha256"], exit_code=0)
    members = dict(process_binding=binding_pin, monitor_open=write(logs / "opened.json", opened),
        monitored_exit=write(logs / "exit.json", exited), runtime_launch=launch_pin,
        monitor_code=dict(path=str(supervisor.CODE / "launch_monthly_test_20261023.py"),
                          sha256=supervisor.HELPER_PINS["launch_monthly_test_20261023.py"]))
    chain = write(logs / "chain.json", dict(status="PROCESS_CHAIN_RECORDED", members=members, runtime_root=str(runtime_root)))
    closed = dict(status="COMPLETE_MONTHLY_TEST_RESOURCE_OVERLAY", completed_utc="2026-10-24T00:01:00+00:00",
        original_run_contract_sha256=supervisor.CONTRACT_SHA, validation_audit_sha256=supervisor.VALIDATION_SHA,
        runtime_review_sha256=runtime_pin["sha256"], scientific_inputs_changed=False, selected_mode=None,
        preserved_checkpoints=preserved, final_checkpoints=final,
        runtime_members={str(p): supervisor.sha(p) for p in runtime_root.rglob("*") if p.is_file()})
    closed_pin = write(runtime_root / "completion.json", closed)
    runtime = dict(producer=dict(runtime_root=str(runtime_root), process_chain=chain, process_members=members,
        command=command, runtime_completion=closed_pin, runtime_review=runtime_pin))
    science.evidence.roots += (supervisor.CODE,)
    return SimpleNamespace(runtime=runtime, helper=helper, evidence=science.evidence, logs=logs, root=runtime_root)


def test_real_frozen_chain_helper_and_full_producer_closure(producer):
    result = supervisor.producer_closure(producer.runtime, producer.evidence, producer.helper)
    assert result["selected_mode"] is None


@pytest.mark.parametrize("fault,message", [("exit", "exit zero"), ("chain", "chain"),
    ("completion", "completion binding"), ("chronology", "chronology"),
    ("snapshot", "snapshots"), ("checkpoint", "checkpoint inventory")])
def test_resigned_producer_faults_rejected(producer, fault, message):
    record = producer.runtime["producer"]
    if fault == "exit":
        pin = record["process_members"]["monitored_exit"]
        changed = supervisor.read(pin["path"])
        changed["exit_code"] = 2
        record["process_members"]["monitored_exit"] = write(Path(pin["path"]), changed)
        chain = supervisor.read(record["process_chain"]["path"])
        chain["members"] = record["process_members"]
        record["process_chain"] = write(Path(record["process_chain"]["path"]), chain)
    elif fault == "chain":
        pin = record["process_chain"]
        changed = supervisor.read(pin["path"])
        changed["members"].pop("monitor_code")
        record["process_chain"] = write(Path(pin["path"]), changed)
    elif fault == "snapshot":
        # An omitted snapshot is a metadata failure even if all bytes remain valid.
        pin = record["process_members"]["runtime_launch"]
        changed = supervisor.read(pin["path"])
        changed["snapshots"].pop(next(iter(changed["snapshots"])))
        record["process_members"]["runtime_launch"] = write(Path(pin["path"]), changed)
        chain = supervisor.read(record["process_chain"]["path"])
        chain["members"] = record["process_members"]
        record["process_chain"] = write(Path(record["process_chain"]["path"]), chain)
        closed = supervisor.read(record["runtime_completion"]["path"])
        closed["runtime_members"][pin["path"]] = record["process_members"]["runtime_launch"]["sha256"]
        record["runtime_completion"] = write(Path(record["runtime_completion"]["path"]), closed)
    else:
        pin = record["runtime_completion"]
        changed = supervisor.read(pin["path"])
        if fault == "completion":
            changed["selected_mode"] = "expanding"
        elif fault == "chronology":
            changed["completed_utc"] = "2026-10-24T00:03:00+00:00"
        else:
            changed["final_checkpoints"].pop(next(iter(changed["final_checkpoints"])))
        record["runtime_completion"] = write(Path(pin["path"]), changed)
    with pytest.raises(ValueError, match=message):
        supervisor.producer_closure(producer.runtime, producer.evidence, producer.helper)


def test_retained_handle_observes_fast_empty_python():
    import launch_monthly_test_20261023 as helper
    child = supervisor.subprocess.Popen([sys.executable, "-c", "pass"], creationflags=supervisor.subprocess.CREATE_NO_WINDOW)
    try:
        retained = helper.RetainedProcess(child)
        creation = retained.creation_time()
        assert child.wait(timeout=10) == 0
        assert retained.creation_time() == creation
        assert retained.wait_exit() == 0
    finally:
        helper.drain_child(child)


def test_monitor_initialization_failure_drains_child(tmp_path):
    drained = []
    def broken(child):
        raise OSError("synthetic handle error")
    helper = SimpleNamespace(RetainedProcess=broken, drain_child=lambda child: drained.append(child))
    child = object()
    with pytest.raises(OSError, match="handle"):
        supervisor.monitor(child, {"logs_root": str(tmp_path)}, helper)
    assert drained == [child]
    assert not (tmp_path / "exit.json").exists()


def test_scientific_lock_bytes_preserved(tmp_path):
    import launch_monthly_test_20261023 as helper
    path = tmp_path / "run.lock"
    path.write_bytes(b"unchanged scientific lock")
    before = path.read_bytes()
    with helper.overlay.os_lock(path, create=False):
        with pytest.raises(RuntimeError, match="holds the lock"):
            with helper.overlay.os_lock(path, create=False):
                pytest.fail("Concurrent lock admitted")
    assert path.read_bytes() == before


def test_launch_gate_is_immediate_and_claim_never_reused(tmp_path, monkeypatch):
    logs, output = tmp_path / "logs", tmp_path / "audit"
    runtime_file = tmp_path / "runtime.json"
    write(runtime_file, {"allowed_read_roots": [str(tmp_path)]})
    receipt = dict(status="PASS_AUDIT_SUPERVISOR_PREFLIGHT_NOT_EXECUTED", files={},
        runtime_review=str(runtime_file), output_root=str(output), logs_root=str(logs),
        command=supervisor.command(runtime_file, output), publication_commit="a" * 40, publication_files={})
    @contextmanager
    def lock(*a, **k):
        yield
    def publish(root, name, value):
        path = root / name
        assert not path.exists()
        write(path, value)
    helper = SimpleNamespace(overlay=SimpleNamespace(os_lock=lock), publish=publish)
    monkeypatch.setattr(supervisor.importlib, "import_module", lambda *a: helper)
    monkeypatch.setattr(supervisor, "publication", lambda *a: None)
    monkeypatch.setattr(supervisor, "producer_closure", lambda *a: None)
    monkeypatch.setattr(supervisor, "destinations", lambda *a: (output, logs))
    observed = free()
    observed["free_commit_bytes"] -= 1
    monkeypatch.setattr(supervisor, "observation", lambda: observed)
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *a, **k: pytest.fail("Gate bypass"))
    with pytest.raises(ValueError, match="gate"):
        supervisor.launch(receipt)
    assert (logs / "preflight.json").exists()
    assert (logs / "failure.json").exists()
    assert not output.exists()
    with pytest.raises(FileExistsError):
        supervisor.launch(receipt)


@pytest.fixture
def admitted(science, monkeypatch):
    """Complete artificial authority chain; only Git object access is substituted."""
    data, root = science.data, science.root
    deps = supervisor.read(supervisor.AUDITOR_REVIEW)["dependencies"]
    # Use the actual eleven published scientific dependencies without loading an auditor.
    contract_deps = supervisor.read(supervisor.CODE / "MONTHLY_TEST_RESOURCE_OVERLAY_REVIEW_20261023.json")["original_dependencies"]
    contract = write(root / "run_contract.json", {"dependencies": contract_deps})
    monkeypatch.setattr(supervisor, "CONTRACT_SHA", contract["sha256"])
    session = data / "session"
    index = write(session / "index.parquet", {"synthetic_index_metadata": True})
    source = write(data / "source_audit.json", {"synthetic": True})
    prior = write(data / "prior.json", dict(status=supervisor.AUDIT_STATUS,
        binding={"completed_months": supervisor.MONTHS[:12]}, verified_files={"source": {source["path"]: source["sha256"]}}))
    freeze = write(root / "validation_freeze.json", dict(selected_mode=None, approved=False, status="FAIL_NO_DAILY_COMPLIANT_MODE"))
    for name, value in dict(SESSION=session, INDEX_SHA=index["sha256"], SOURCE_AUDIT=Path(source["path"]),
        SOURCE_SHA=source["sha256"], VALIDATION_AUDIT=Path(prior["path"]), VALIDATION_SHA=prior["sha256"], FREEZE_SHA=freeze["sha256"]).items():
        monkeypatch.setattr(supervisor, name, value)
    for path in root.rglob("*.complete.json"):
        value = supervisor.read(path)
        value["binding"] = contract["sha256"]
        value["files"] = {n: supervisor.sha(root / n) for n in value["files"]}
        write(path, value)
    (root / "run.lock").write_bytes(b"SYNTHETIC LOCK PRESERVED")
    assembled = producer.__wrapped__(science, monkeypatch)
    code = supervisor.import_closure(set(supervisor.NEW_FILES) | set(supervisor.HELPER_PINS) | set(contract_deps) | set(deps))
    review_path = data / "supervisor_review.json"
    review = write(review_path, dict(status=supervisor.REVIEW_STATUS, decision="CLEAR", scope="IMPLEMENTATION_ONLY",
        runtime_authorized=False, files=code))
    monkeypatch.setattr(supervisor, "SUPERVISOR_REVIEW", review_path)
    published = {str(supervisor.CODE / n): h for n, h in code.items()}
    published.update({review["path"]: review["sha256"], str(supervisor.AUDITOR_REVIEW): supervisor.AUDITOR_REVIEW_SHA,
        str(supervisor.PRODUCER_REVIEW): supervisor.PRODUCER_REVIEW_SHA,
        assembled.runtime["producer"]["runtime_review"]["path"]: supervisor.PRODUCER_RUNTIME_SHA})
    runtime = dict(status=supervisor.RUNTIME_STATUS, scope=supervisor.SCOPE, dependencies=deps,
        binding=dict(monthly_root=str(root), source_audit=str(supervisor.SOURCE_AUDIT),
            validation_audit=str(supervisor.VALIDATION_AUDIT), validation_audit_sha256=supervisor.VALIDATION_SHA,
            implementation_review_sha256=supervisor.AUDITOR_REVIEW_SHA, run_contract_sha256=supervisor.CONTRACT_SHA,
            source_audit_sha256=supervisor.SOURCE_SHA, index_sha256=supervisor.INDEX_SHA, session_root=str(session),
            validation_freeze_sha256=supervisor.FREEZE_SHA),
        producer=assembled.runtime["producer"], allowed_read_roots=[str(data), str(supervisor.CODE)],
        launch_binding=dict(status="REVIEWED_MONTHLY_TEST_INDEX_V2_AUDIT_ONE_SHOT", supervisor_review=review,
            published_files=published, output_root=str(data.parent / "audit"), logs_root=str(data.parent / "logs")))
    runtime_pin = write(data / "runtime_review.json", runtime)
    seen = []
    monkeypatch.setattr(supervisor, "publication", lambda commit, files: seen.append((commit, files)))
    before = {str(p) for p in data.parent.rglob("*")}
    receipt = supervisor.preflight(runtime_pin["path"], runtime_pin["sha256"], review["sha256"], "a" * 40)
    assert {str(p) for p in data.parent.rglob("*")} == before
    assert seen == [("a" * 40, {**published, runtime_pin["path"]: runtime_pin["sha256"]})]
    return receipt


def test_complete_preflight_is_metadata_only_and_preserves_files(admitted):
    assert admitted["executed"] is False
    assert len(admitted["dependencies"]) == 13
    assert not Path(admitted["logs_root"]).exists()
    assert not Path(admitted["output_root"]).exists()


@pytest.fixture
def audit_output(admitted):
    output = Path(admitted["output_root"])
    output.mkdir()
    snapshots = {}
    for name, value in admitted["dependencies"].items():
        path = output / "executed_code" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes((supervisor.CODE / name).read_bytes())
        snapshots[str(path)] = value
    for name, source in [("implementation_review.json", supervisor.AUDITOR_REVIEW), ("runtime_review.json", Path(admitted["runtime_review"]))]:
        path = output / "authorities" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(source.read_bytes())
        snapshots[str(path)] = supervisor.sha(path)
    write(output / "launch.json", dict(scope=supervisor.SCOPE, dependencies=admitted["dependencies"], snapshots=snapshots,
        runtime_review_sha256=admitted["runtime_review_sha256"], validation_audit_sha256=supervisor.VALIDATION_SHA))
    checks = dict(new_months=6, new_unique_fit_windows=12, models_used_test=13, total_unique_fit_windows=36,
        modes=supervisor.MODES, calendar_ticker_days=369, available_ticker_days=363, missing_no_evaluable=6,
        selected_mode=None, selection_reused_without_test_reselection=True,
        new_fit_samples_targets_weights_matrices_reconstructed=True, scheduler_ledgers_economics_reconstructed=True,
        all_three_monthly_fit_scores_sealed_before_ledgers=True, test_period_report_reconstructed=True,
        missing_identities=sorted([[t, d] for t in ("QQQ", "SPY") for d in ("20260401", "20260409", "20260415")]))
    result = dict(status=supervisor.AUDIT_STATUS, scope=supervisor.SCOPE,
        audit_script_sha256=admitted["dependencies"][supervisor.AUDITOR.name], development_seen=True, promotion_approved=False,
        binding=dict(monthly_root=str(supervisor.MONTHLY), run_contract_sha256=supervisor.CONTRACT_SHA,
            session_root=str(supervisor.SESSION), session_audit_sha256=supervisor.SOURCE_SHA,
            index_sha256=supervisor.INDEX_SHA, completed_months=supervisor.MONTHS),
        prior_validation_audit=dict(path=str(supervisor.VALIDATION_AUDIT), sha256=supervisor.VALIDATION_SHA,
            scope="VALIDATION_2025", inventory_rehashed=True, reconstruction_inherited_not_repeated=True),
        audited=checks, execution_snapshots=snapshots, verified_files=supervisor.read(supervisor.VALIDATION_AUDIT)["verified_files"])
    write(output / "audit.json", result)
    return output, admitted


def test_complete_audit_result_and_launch_close_exactly(audit_output):
    output, receipt = audit_output
    assert supervisor.validate_audit(output, receipt) == {str(output / n): supervisor.sha(output / n) for n in ("audit.json", "launch.json")}


@pytest.mark.parametrize("fault", ["launch", "failure", "inherited", "snapshot", "binding"])
def test_audit_closure_rejects_resigned_metadata_faults(audit_output, fault):
    output, receipt = audit_output
    if fault == "failure":
        write(output / "failure.json", {"error": "synthetic"})
    elif fault == "launch":
        value = supervisor.read(output / "launch.json")
        value["runtime_review_sha256"] = "0" * 64
        write(output / "launch.json", value)
    else:
        value = supervisor.read(output / "audit.json")
        if fault == "inherited":
            value["verified_files"] = {}
        elif fault == "snapshot":
            value["execution_snapshots"].pop(next(iter(value["execution_snapshots"])))
        else:
            value["binding"]["completed_months"] = supervisor.MONTHS[:12]
        write(output / "audit.json", value)
    with pytest.raises(ValueError):
        supervisor.validate_audit(output, receipt)


def test_monitor_receipts_bind_real_handle_runtime_and_code(tmp_path):
    import launch_monthly_test_20261023 as helper
    receipt = dict(logs_root=str(tmp_path), files={str(Path(supervisor.__file__).resolve()): supervisor.sha(supervisor.__file__)},
        runtime_review_sha256="a" * 64, supervisor_review_sha256="b" * 64, publication_commit="c" * 40,
        command=[sys.executable, "-c", "pass"])
    write(tmp_path / "preflight.json", receipt)
    child = supervisor.subprocess.Popen(receipt["command"], creationflags=supervisor.subprocess.CREATE_NO_WINDOW)
    try:
        closed = supervisor.monitor(child, receipt, helper)
        assert closed["exit_code"] == 0
        supervisor.verify(closed["files"])
        exited = supervisor.read(tmp_path / "exit.json")
        assert exited["process_receipt_sha256"] == supervisor.sha(tmp_path / "process.json")
        assert exited["runtime_review_sha256"] == receipt["runtime_review_sha256"]
        assert "observed_utc" in exited and "monitor_seconds" in exited and "seconds" not in exited
    finally:
        helper.drain_child(child)


@pytest.mark.parametrize("bad_result", [False, True])
def test_launch_complete_chain_or_preserved_real_exit_on_late_failure(admitted, monkeypatch, bad_result):
    output, logs = Path(admitted["output_root"]), Path(admitted["logs_root"])
    operational = output.parent / "operational"
    operational.mkdir()
    monkeypatch.setattr(supervisor, "BASE", operational)
    original_popen = supervisor.subprocess.Popen
    events = []
    def resources():
        events.append("gate")
        return free()
    def synthetic_child(argv, **kwargs):
        assert argv == admitted["command"]
        assert events[-1] == "gate"
        events.append("popen")
        # The process boundary alone is replaced with an empty Python child.
        audit_output.__wrapped__(admitted)
        if bad_result:
            write(output / "failure.json", {"synthetic": True})
        return original_popen([sys.executable, "-c", "pass"], **kwargs)
    monkeypatch.setattr(supervisor, "observation", resources)
    monkeypatch.setattr(supervisor.subprocess, "Popen", synthetic_child)
    if bad_result:
        with pytest.raises(ValueError, match="failure coexists"):
            supervisor.launch(admitted)
        assert not (logs / "completion.json").exists()
        assert (logs / "failure.json").exists()
    else:
        assert supervisor.launch(admitted) == 0
        completion = supervisor.read(logs / "completion.json")
        supervisor.verify(completion["closure_files"])
        assert set(completion["closure_files"]) == {str(p) for p in [logs / "preflight.json",
            logs / "process.json", logs / "exit.json", output / "launch.json", output / "audit.json"]}
    assert supervisor.read(logs / "exit.json")["exit_code"] == 0
    assert events.count("popen") == 1
    with pytest.raises(ValueError, match="Fresh"):
        supervisor.launch(admitted)
    assert events.count("popen") == 1
