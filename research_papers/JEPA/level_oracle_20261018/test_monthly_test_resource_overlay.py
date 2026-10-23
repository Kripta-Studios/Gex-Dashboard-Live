"""Small synthetic-only launch/authority tests; never run a market producer."""

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

import run_monthly_test_resource_overlay as overlay


def put(path, value):
    # Intentional mutations are restricted to fresh synthetic fixture roots.
    overlay.shared.atomic_json(path, value, replace=True)
    return {"path": str(path.resolve()), "sha256": overlay.shared.sha(path)}


def authority_fixture(tmp_path, monkeypatch):
    root = tmp_path / "research"
    science = root / "monthly_walk_forward_v1"
    science.mkdir(parents=True)
    (science / "run.lock").write_bytes(b"0")
    monkeypatch.setattr(overlay, "ROOT", root)
    monkeypatch.setattr(overlay, "SCIENTIFIC_ROOT", science)
    monkeypatch.setattr(overlay.shared.psutil, "pid_exists", lambda pid: False)
    source = root / "session_clock_dataset_v1"
    source.mkdir()
    (source / "index.parquet").write_bytes(b"synthetic calendar index, not parsed")
    source_audit = root / "session_clock_dataset_v1_audit/audit.json"
    sb = dict(index_sha256=overlay.shared.sha(source / "index.parquet"), engine_root=str(source))
    put(source_audit, dict(status="PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT", binding=sb))
    contract = dict(dependencies=overlay.monthly.dependency_hashes(), engine_root=str(source),
        source_audit=dict(sha256=overlay.shared.sha(source_audit), binding=sb))
    put(science / "run_contract.json", contract)
    binding = overlay.shared.sha(science / "run_contract.json")
    monkeypatch.setattr(overlay, "RUN_CONTRACT_SHA", binding)
    for name in contract["dependencies"]:
        path = science / "executed_code" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes((overlay.HERE / name).read_bytes())

    def mark(name, paths):
        path = science / (name + ".complete.json")
        put(path, dict(status="COMPLETE", binding=binding,
            files={str(p.relative_to(science)): overlay.shared.sha(p) for p in paths},
            extra={}, completed_utc="2026-10-23T10:00:00+00:00"))
        return path

    def artifact(name, value):
        path = science / (name + ".json")
        put(path, value)
        mark(name, [path])
        return path

    def add_model(key):
        path = science / f"models/{key}.txt"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"synthetic model; never fit or inferred")
        started = science / f"models/{key}.fit_started.json"
        put(started, dict(binding=binding, config={"synthetic": True}))
        mark("models/" + key, [path, started])

    for key in overlay.fit_keys(2025):
        add_model(key)
    freeze_path = artifact("validation_freeze", dict(status="FAIL_NO_DAILY_COMPLIANT_MODE",
        selected_mode=None, approved=False, selection_period="2025", outcomes_2026_used_for_mode_selection=False))
    for stamp in overlay.VALIDATION_MONTHS:
        for name in ("daily", "economics"):
            artifact(f"months/{stamp}/{name}", {"synthetic": True})
        mark(f"months/{stamp}/predictions", [science / f"months/{stamp}/daily.json"])
    artifact("reports/2025", {"selected_mode": None, "synthetic": True})
    verified = {str(p.resolve()): overlay.shared.sha(p) for p in science.rglob("*")
                if p.is_file() and p.name != "run.lock"}
    audit_path = root / "audit2025.json"
    audit_spec = put(audit_path, dict(status=overlay.AUDIT_STATUS,
        binding=dict(monthly_root=str(science), run_contract_sha256=binding,
            session_root=str(source), session_audit_sha256=overlay.shared.sha(source_audit),
            index_sha256=sb["index_sha256"], completed_months=list(overlay.VALIDATION_MONTHS)),
        audited=dict(months=12, unique_fit_windows=24, calendar_ticker_days=750, modes=list(overlay.MODES),
            validation_selection_reconstructed=True, validation_period_report_reconstructed=True),
        verified_files=dict(synthetic=verified)))
    validation_root = root / "validation_runtime"
    validation_root.mkdir()
    process_root = root / "validation_process"
    process_root.mkdir()
    monitor = process_root / "monitor.py"
    monitor.write_bytes(b"synthetic retained-handle monitor authority, never executed")
    source_launch = put(process_root / "process.json", {"arguments": ["PowerShell original"], "started_utc": "earlier"})
    command = [sys.executable, "-u", str(overlay.HERE / "run_monthly_resource_overlay.py"),
               "--runtime-root", str(validation_root)]
    process = put(process_root / "process_monitor_binding.json", dict(pid=12345, creation_time=100.0,
        started_unix=100.0, command=command, source_launch_receipt_sha256=source_launch["sha256"]))
    opened = put(process_root / "monitor_open.json", dict(status="PROCESS_HANDLE_RETAINED", pid=12345,
        creation_time=100.0, command=command, monitor_started_utc="2026-10-23T09:01:00+00:00",
        process_receipt_sha256=process["sha256"], monitor_code_sha256=overlay.shared.sha(monitor)))
    exited = put(process_root / "monitored_exit.json", dict(status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE",
        pid=12345, creation_time=100.0, exit_code=0, observed_utc="2026-10-23T11:01:00+00:00",
        process_receipt_sha256=process["sha256"]))
    launch = put(validation_root / "launch.json", dict(status="MONTHLY_RESOURCE_OVERLAY_STARTED", pid=12345,
        started_utc="2026-10-23T09:00:00+00:00", original_argv=[*overlay.original_argv()[:-1], "validation"],
        authority=dict(original_dependencies=contract["dependencies"]), runtime_review_sha256="a" * 64))
    _, preserved = overlay.checkpoints(science)
    completion = put(validation_root / "completion.json", dict(status="COMPLETE_MONTHLY_RESOURCE_OVERLAY_VALIDATION",
        original_run_contract_sha256=binding, scientific_inputs_changed=False, runtime_review_sha256="a" * 64,
        completed_utc="2026-10-23T11:00:00+00:00", preserved_checkpoints=preserved, final_checkpoints=preserved,
        runtime_members={launch["path"]: launch["sha256"]}))
    validation = dict(audit=audit_spec, freeze={"path": str(freeze_path), "sha256": overlay.shared.sha(freeze_path)},
        runtime_root=str(validation_root), runtime_launch=launch, runtime_completion=completion,
        process_binding=process, monitor_open=opened, monitored_exit=exited,
        monitor_code={"path": str(monitor), "sha256": overlay.shared.sha(monitor)}, source_launch=source_launch)
    review_path, runtime_path = root / "review.json", root / "runtime.json"
    put(review_path, dict(status=overlay.REVIEW_STATUS, **overlay.review_expectations()))
    runtime = dict(status=overlay.RUNTIME_STATUS, scope="test", scientific_root=str(science),
        original_run_contract_sha256=binding, implementation_review_sha256=overlay.shared.sha(review_path),
        review_expectations=overlay.review_expectations(), allowed_read_roots=[str(root), str(overlay.HERE)],
        mode="initial", expected_completed_test_fit_keys=[], prior_test_attempts=[], validation=validation)
    put(runtime_path, runtime)
    return SimpleNamespace(root=root, science=science, review=review_path, runtime_path=runtime_path,
        runtime=runtime, validation=validation, audit_sha=audit_spec["sha256"], add_model=add_model,
        artifact=artifact, mark=mark, runtime_out=root / "test_runtime")


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    return authority_fixture(tmp_path, monkeypatch)


def admit(evidence):
    return overlay.admit(evidence.review, evidence.runtime_path, evidence.audit_sha)


@pytest.mark.parametrize("low", ["available_ram_bytes", "free_commit_bytes"])
def test_exact_resource_boundaries(tmp_path, monkeypatch, low):
    first = dict(available_ram_bytes=2_000_000_000, free_commit_bytes=2_000_000_000, utc="first")
    first[low] -= 1
    second = dict(available_ram_bytes=2_000_000_000, free_commit_bytes=2_000_000_000, utc="second")
    values, sleeps = iter([first, second]), []
    monkeypatch.setattr(overlay, "resource_observation", lambda: next(values))
    monkeypatch.setattr(overlay.time, "sleep", sleeps.append)
    overlay.wait_resources(tmp_path / "science", tmp_path / "runtime")
    records = [overlay.shared.read_json(p) for p in sorted((tmp_path / "runtime/observations").glob("*.json"))]
    assert [r["stage"] for r in records] == ["WAITING_RESOURCES_2GB", "RESOURCE_OVERLAY_READY"]
    assert records[-1]["threshold_bytes"] == 2_000_000_000 and sleeps == [30]


@pytest.mark.parametrize("failure", [False, True])
def test_restores_only_resource_function(tmp_path, monkeypatch, failure):
    original, main, fit = overlay.shared.wait_resources, overlay.monthly.main, overlay.shared.fit_once
    monkeypatch.setattr(overlay, "wait_resources", lambda *a: None)
    try:
        with overlay.resource_overlay(tmp_path):
            assert overlay.shared.fit_once is fit and overlay.monthly.main is main
            overlay.shared.wait_resources("science")
            if failure:
                raise RuntimeError("synthetic")
    except RuntimeError:
        assert failure
    assert overlay.shared.wait_resources is original


def test_only_test_cli_and_frozen_window_counts():
    args = overlay.original_argv()
    assert args[-2:] == ["--stage", "test"] and "all" not in args and len(args) == 12
    assert len(overlay.fit_keys(2025)) == 24 and len(overlay.fit_keys(2026)) == 12
    assert not overlay.fit_keys(2025) & overlay.fit_keys(2026)


def test_admission_preserves_null_and_exact_twenty_four(evidence):
    result = admit(evidence)
    assert result["freeze"]["selected_mode"] is None
    assert result["expectations"]["scope"] == "test"
    assert len(overlay.checkpoints(evidence.science)[0]) == 24
    overlay.verify_hashes(result["preserved"])


def test_legitimate_outcome_free_2026_preparation_allowed(evidence):
    for relative in ("day_samples/SPY/20260102.npz", "feature_inputs/SPY/20260102.json"):
        path = evidence.science / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic outcome-free preparation")
    assert overlay.test_evidence(evidence.science) == {}
    admit(evidence)


@pytest.mark.parametrize("relative", ["predictions/202601/x.npz", "months/202601/daily.json",
    "ledgers/202601/static/SPY/20260102_ledger.parquet", "reports/2026.json",
    "fits/train_20230101_20260101_exclusive/inputs.json", "day_chunks/SPY/20260102.npz"])
def test_initial_rejects_test_evidence_before_main(evidence, relative):
    path = evidence.science / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"prior test evidence must not be adopted")
    with pytest.raises(ValueError, match="cannot adopt"):
        admit(evidence)


def test_external_audit_hash_and_review_fail_closed(evidence):
    with pytest.raises(ValueError, match="External validation audit hash"):
        overlay.admit(evidence.review, evidence.runtime_path, "0" * 64)
    value = overlay.shared.read_json(evidence.review)
    value["scope"] = "all"
    put(evidence.review, value)
    with pytest.raises(ValueError, match="Exact test overlay review"):
        admit(evidence)


def update_validation_member(evidence, name, change):
    path = Path(evidence.validation[name]["path"])
    value = overlay.shared.read_json(path)
    change(value)
    evidence.validation[name] = put(path, value)
    evidence.runtime["validation"] = evidence.validation
    put(evidence.runtime_path, evidence.runtime)


@pytest.mark.parametrize("member,change,message", [
    ("monitored_exit", lambda x: x.update(exit_code=1), "observed exit zero"),
    ("monitored_exit", lambda x: x.update(exit_code=False), "Invalid process exit"),
    ("monitored_exit", lambda x: x.update(creation_time=101), "creation time differs"),
    ("monitored_exit", lambda x: x.update(status="PROCESS_NOT_FOUND"), "chain identity differs"),
    ("monitor_open", lambda x: x.update(process_receipt_sha256="0" * 64), "chain identity differs"),
    ("runtime_launch", lambda x: x.update(original_argv=["--stage", "all"]), "another stage"),
])
def test_handle_identity_and_exit_fail_closed(evidence, member, change, message):
    update_validation_member(evidence, member, change)
    with pytest.raises(ValueError, match=message):
        admit(evidence)


def test_reused_pid_rejected_without_process_actions(evidence, monkeypatch):
    monkeypatch.setattr(overlay.shared.psutil, "pid_exists", lambda pid: True)
    with pytest.raises(ValueError, match="PID still exists"):
        admit(evidence)


def test_incomplete_fit_preserved_without_refit(evidence):
    key = sorted(overlay.fit_keys(2026))[0]
    path = evidence.science / f"models/{key}.fit_started.json"
    put(path, {"synthetic": "interrupted fit"})
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Incomplete started fit"):
        admit(evidence)
    assert path.read_bytes() == before


def test_changed_validation_model_and_null_rejected(evidence):
    model = next((evidence.science / "models").glob("*.txt"))
    model.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA256 differs"):
        admit(evidence)


def test_scientific_probe_does_not_change_bytes_and_rejects_concurrency(tmp_path):
    path = tmp_path / "run.lock"
    path.write_bytes(b"original scientific lock bytes")
    before = path.read_bytes()
    with overlay.os_lock(path, create=False):
        with pytest.raises(RuntimeError, match="holds the lock"):
            with overlay.os_lock(path, create=False):
                pytest.fail("Duplicate producer admitted")
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="Existing nonempty"):
        with overlay.os_lock(tmp_path / "absent", create=False):
            pytest.fail("Scientific lock created")


def add_prior_test_attempt(evidence):
    key = sorted(overlay.fit_keys(2026))[0]
    evidence.add_model(key)
    previous = evidence.root / "old_test_runtime"
    previous.mkdir()
    monitor = previous / "monitor.py"
    monitor.write_bytes(b"synthetic retained-handle monitor")
    command = [sys.executable, str(overlay.HERE / "run_monthly_test_resource_overlay.py"),
               "--runtime-root", str(previous)]
    process = put(previous / "process_binding.json", dict(pid=23456, creation_time=200.0, command=command))
    opened = put(previous / "monitor_open.json", dict(status="PROCESS_HANDLE_RETAINED", pid=23456,
        creation_time=200.0, command=command, monitor_started_utc="2026-10-23T12:00:00+00:00",
        process_receipt_sha256=process["sha256"], monitor_code_sha256=overlay.shared.sha(monitor)))
    exited = put(previous / "monitored_exit.json", dict(status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE",
        pid=23456, creation_time=200.0, exit_code=1, observed_utc="2026-10-23T13:00:00+00:00",
        process_receipt_sha256=process["sha256"]))
    launch = put(previous / "launch.json", dict(status="MONTHLY_TEST_RESOURCE_OVERLAY_STARTED", pid=23456,
        original_argv=overlay.original_argv(), original_run_contract_sha256=overlay.RUN_CONTRACT_SHA,
        validation_audit_sha256=evidence.audit_sha, scientific_inputs_changed=False,
        review=dict(original_dependencies=overlay.monthly.dependency_hashes(), scope="test")))
    prior = dict(runtime_root=str(previous), runtime_launch=launch, process_binding=process,
        monitor_open=opened, monitored_exit=exited, monitor_code={"path": str(monitor), "sha256": overlay.shared.sha(monitor)})
    evidence.runtime.update(mode="resume", expected_completed_test_fit_keys=[key],
        expected_test_evidence=overlay.test_evidence(evidence.science), prior_test_attempts=[prior])
    put(evidence.runtime_path, evidence.runtime)
    return key


def test_resume_completed_model_with_reviewed_prior_handle(evidence):
    key = add_prior_test_attempt(evidence)
    before = (evidence.science / f"models/{key}.txt").read_bytes()
    result = admit(evidence)
    assert len(overlay.checkpoints(evidence.science)[0]) == 25
    assert result["runtime"]["mode"] == "resume"
    assert (evidence.science / f"models/{key}.txt").read_bytes() == before


def test_resume_requires_exact_inventory_and_prior_attempt(evidence):
    add_prior_test_attempt(evidence)
    evidence.runtime["expected_test_evidence"] = {}
    put(evidence.runtime_path, evidence.runtime)
    with pytest.raises(ValueError, match="externally reviewed"):
        admit(evidence)


def test_normalized_binding_cannot_drop_source_launch(evidence):
    del evidence.runtime["validation"]["source_launch"]
    put(evidence.runtime_path, evidence.runtime)
    with pytest.raises(ValueError, match="requires its source launch"):
        admit(evidence)


def test_source_launch_without_binding_hash_rejected(evidence):
    process_path = Path(evidence.validation["process_binding"]["path"])
    binding = overlay.shared.read_json(process_path)
    binding.pop("source_launch_receipt_sha256")
    evidence.validation["process_binding"] = put(process_path, binding)
    for name in ("monitor_open", "monitored_exit"):
        path = Path(evidence.validation[name]["path"])
        value = overlay.shared.read_json(path)
        value["process_receipt_sha256"] = evidence.validation["process_binding"]["sha256"]
        evidence.validation[name] = put(path, value)
    put(evidence.runtime_path, evidence.runtime)
    with pytest.raises(ValueError, match="lost source launch"):
        admit(evidence)


def test_resume_cannot_change_original_source_cli(evidence):
    add_prior_test_attempt(evidence)
    prior = evidence.runtime["prior_test_attempts"][0]
    path = Path(prior["runtime_launch"]["path"])
    launch = overlay.shared.read_json(path)
    launch["original_argv"][launch["original_argv"].index("--out") + 1] = str(evidence.root / "other-science")
    prior["runtime_launch"] = put(path, launch)
    put(evidence.runtime_path, evidence.runtime)
    with pytest.raises(ValueError, match="Previous test attempt stage/contract"):
        admit(evidence)


def test_normalized_resume_requires_source_launch_too(evidence):
    add_prior_test_attempt(evidence)
    prior = evidence.runtime["prior_test_attempts"][0]
    path = Path(prior["process_binding"]["path"])
    binding = overlay.shared.read_json(path)
    binding["normalized_from_existing_receipt_with_live_command_and_creation_check"] = True
    prior["process_binding"] = put(path, binding)
    for name in ("monitor_open", "monitored_exit"):
        path = Path(prior[name]["path"])
        value = overlay.shared.read_json(path)
        value["process_receipt_sha256"] = prior["process_binding"]["sha256"]
        prior[name] = put(path, value)
    put(evidence.runtime_path, evidence.runtime)
    with pytest.raises(ValueError, match="requires its source launch"):
        admit(evidence)


def close_synthetic_test(evidence):
    for key in overlay.fit_keys(2026):
        evidence.add_model(key)
    for stamp in overlay.TEST_MONTHS:
        for kind in ("daily", "economics"):
            evidence.artifact(f"months/{stamp}/{kind}", {"synthetic": True})
        evidence.mark(f"months/{stamp}/predictions", [evidence.science / f"months/{stamp}/daily.json"])
    evidence.artifact("reports/2026", {"synthetic": True, "selected_mode": None})
    evidence.artifact("completion", dict(status="COMPLETE", evaluated_months=18, unique_fit_windows=36,
        selected_mode=None, promotion_approved=False,
        report_hashes={str(y): overlay.shared.sha(evidence.science / f"reports/{y}.json") for y in (2025, 2026)}))


@pytest.mark.parametrize("failure", [False, True])
def test_run_with_double_preserves_and_restores(evidence, monkeypatch, failure):
    # Main double only: authority admission and locks still run unchanged.
    old_argv, old_wait = sys.argv, overlay.shared.wait_resources
    old_hashes = overlay.checkpoints(evidence.science)[1]
    calls = []

    def fake_main():
        calls.append(tuple(sys.argv))
        assert sys.argv[-2:] == ["--stage", "test"]
        assert overlay.shared.wait_resources is not old_wait
        # The wrapper released its probe; the original runner can own the lock.
        with overlay.os_lock(evidence.science / "run.lock", create=False):
            if failure:
                raise RuntimeError("synthetic runner failure")
            close_synthetic_test(evidence)

    monkeypatch.setattr(overlay.monthly, "main", fake_main)
    if failure:
        with pytest.raises(RuntimeError, match="synthetic runner failure"):
            overlay.run(evidence.runtime_out, evidence.review, evidence.runtime_path, evidence.audit_sha)
        assert (evidence.runtime_out / "failure.json").exists()
        assert not (evidence.runtime_out / "completion.json").exists()
    else:
        overlay.run(evidence.runtime_out, evidence.review, evidence.runtime_path, evidence.audit_sha)
        result = overlay.shared.read_json(evidence.runtime_out / "completion.json")
        assert result["scientific_inputs_changed"] is False and result["selected_mode"] is None
        overlay.verify_hashes(result["runtime_members"])
        assert result["preserved_checkpoints"] == old_hashes
        assert len(overlay.checkpoints(evidence.science)[0]) == 36
    assert len(calls) == 1 and sys.argv is old_argv and overlay.shared.wait_resources is old_wait
    overlay.verify_hashes(old_hashes)
    with pytest.raises(ValueError, match="new runtime attempt"):
        overlay.run(evidence.runtime_out, evidence.review, evidence.runtime_path, evidence.audit_sha)


def test_existing_root_and_protected_roots_rejected(evidence):
    for path in (evidence.science, evidence.science / "child", overlay.ROOT, overlay.HERE):
        with pytest.raises(ValueError, match="separate directory"):
            overlay.guard_runtime_root(path)
    evidence.runtime_out.mkdir()
    with pytest.raises(ValueError, match="new runtime"):
        overlay.guard_runtime_root(evidence.runtime_out)


def test_terminal_scientific_completion_is_required(evidence):
    admitted = admit(evidence)
    with pytest.raises(ValueError, match="thirty-six"):
        overlay.finish_science(admitted)
    close_synthetic_test(evidence)
    result = overlay.finish_science(admitted)
    assert result
    completion = overlay.shared.read_json(evidence.science / "completion.json")
    completion["selected_mode"] = "expanding"
    evidence.artifact("completion", completion)
    with pytest.raises(ValueError, match="Scientific completion differs"):
        overlay.finish_science(admitted)
