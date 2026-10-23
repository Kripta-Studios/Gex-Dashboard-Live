"""Small synthetic supervisor checks. Never invokes watch/admit/audit/market."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

SPEC = importlib.util.spec_from_file_location("audit_launcher_fixture", Path(__file__).with_name("launch_when_validation_complete.py"))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


@pytest.mark.parametrize("ram,commit,wanted", [(2_000_000_000, 2_000_000_000, True),
    (1_999_999_999, 3_000_000_000, False), (3_000_000_000, 1_999_999_999, False)])
def test_gate(ram, commit, wanted):
    assert M.ready(dict(available_ram_bytes=ram, free_commit_bytes=commit)) is wanted


def test_receipt_no_overwrite(tmp_path):
    path = tmp_path / "once.json"
    M.write_new(path, {"attempt": 1})
    with pytest.raises(FileExistsError):
        M.write_new(path, {"attempt": 2})
    assert M.read(path) == {"attempt": 1}


def test_launcher_bytes_cannot_change(tmp_path, monkeypatch):
    path = tmp_path / "launcher.py"
    path.write_text("original", encoding="utf-8")
    monkeypatch.setattr(M, "__file__", str(path))
    digest = M.sha(path)
    M.require_own_bytes(digest)
    path.write_text("changed during wait", encoding="utf-8")
    with pytest.raises(ValueError, match="Launcher changed"):
        M.require_own_bytes(digest)


def chain():
    binding = {"command": ["python", "validation"]}
    opened = dict(command=binding["command"], monitor_started_utc="2026-10-23T00:00:00+00:00")
    exited = dict(status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE", pid=M.PID,
                  creation_time=M.CREATED, process_receipt_sha256=M.PINS[M.MONITOR / "process_monitor_binding.json"],
                  exit_code=0, observed_utc="2026-10-23T01:00:00+00:00")
    return binding, opened, exited


def test_valid_retained_exit():
    M.validate_exit(*chain())


@pytest.mark.parametrize("field,value", [("exit_code", 1), ("exit_code", False),
    ("pid", 77), ("creation_time", 0), ("process_receipt_sha256", "wrong"),
    ("observed_utc", "2026-10-22T00:00:00+00:00"), ("status", "PID_ABSENT")])
def test_retained_exit_rejects(field, value):
    binding, opened, exited = chain()
    exited[field] = value
    with pytest.raises(ValueError):
        M.validate_exit(binding, opened, exited)


def test_missing_process_and_monitor_not_success(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "MONITOR", tmp_path)
    monkeypatch.setattr(M, "process_binding", lambda: ({}, {"monitor_pid": 99}))
    monkeypatch.setattr(M.psutil, "pid_exists", lambda _: False)
    monkeypatch.setattr(M.time, "sleep", lambda _: pytest.fail("Must fail without waiting"))
    with pytest.raises(ValueError, match="Monitor vanished"):
        M.wait_validation()


def test_scientific_lock_keeps_bytes_on_error(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "SCIENCE", tmp_path)
    path = tmp_path / "run.lock"
    path.write_bytes(b"frozen-scientific-lock")
    with pytest.raises(RuntimeError):
        with M.scientific_lock():
            raise RuntimeError("synthetic failure")
    assert path.read_bytes() == b"frozen-scientific-lock"
    with M.scientific_lock():
        pass


def test_operational_lock_excludes_duplicate(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "LAUNCH_ROOT", tmp_path)
    with M.operational_lock():
        with pytest.raises(OSError):
            with M.operational_lock():
                pytest.fail("Concurrent supervisor admitted")
    with M.operational_lock():
        pass


def test_retained_popen_handle_after_fast_exit():
    child = subprocess.Popen([sys.executable, "-c", "pass"], creationflags=subprocess.CREATE_NO_WINDOW)
    assert child.wait(timeout=30) == 0
    assert M.handle_creation_time(child._handle) > 0


def test_resource_wait_then_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "LAUNCH_ROOT", tmp_path)
    samples = iter([dict(available_ram_bytes=0, free_commit_bytes=2_000_000_000),
                    dict(available_ram_bytes=2_000_000_000, free_commit_bytes=2_000_000_000)])
    monkeypatch.setattr(M, "observation", lambda: next(samples))
    sleeps = []
    monkeypatch.setattr(M.time, "sleep", sleeps.append)
    assert M.ready(M.wait_resources())
    assert sleeps == [30]
    assert len(list(tmp_path.glob("resource_*.json"))) == 2


def test_command_scope():
    command = M.audit_command("a" * 64)
    assert command[2].endswith("audit_monthly_walk_forward_index_v2.py")
    assert command[3::2] == ["--monthly-root", "--source-audit", "--implementation-review",
                           "--implementation-review-sha256", "--output"]
    assert command[10] == "a" * 64
    assert "--stage" not in command


@pytest.mark.parametrize("value", [None, "", "a" * 63, "g" * 64, "A" * 64])
def test_external_review_pin_required(value):
    with pytest.raises(ValueError, match="External V2 review SHA"):
        M.audit_command(value)


def test_cli_has_no_default_review_authority(monkeypatch):
    monkeypatch.setattr(M.sys, "argv", ["launcher", "--watch"])
    with pytest.raises(SystemExit) as exited:
        M.main()
    assert exited.value.code == 2


def synthetic_v2_review(tmp_path, monkeypatch):
    files = {}
    for name in ("AUDITOR", "V2_TESTS", "V2_SPEC"):
        path = tmp_path / name
        path.write_text("synthetic authority fixture " + name, encoding="utf-8")
        monkeypatch.setattr(M, name, path)
        files[name] = path
    review_path = tmp_path / "synthetic_review.json"
    monkeypatch.setattr(M, "REVIEW", review_path)
    review = dict(status=M.V2_REVIEW_STATUS, auditor_sha256=M.sha(files["AUDITOR"]),
                  tests_sha256=M.sha(files["V2_TESTS"]), contract_sha256=M.sha(files["V2_SPEC"]),
                  original_auditor_sha256=M.ORIGINAL_AUDITOR_SHA,
                  original_review_sha256=M.PINS[M.ORIGINAL_REVIEW],
                  original_contract_sha256=M.PINS[M.HERE / "MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDIT_CONTRACT.md"])
    M.write_new(review_path, review)
    return review_path, review


def test_v2_review_exact_external_pin(tmp_path, monkeypatch):
    path, _ = synthetic_v2_review(tmp_path, monkeypatch)
    digest = M.sha(path)
    assert M.v2_authority(digest)[M.AUDITOR] == M.sha(M.AUDITOR)
    with pytest.raises(ValueError, match="Evidence hash differs"):
        M.v2_authority("0" * 64)
    M.AUDITOR.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="Evidence hash differs"):
        M.v2_authority(digest)


@pytest.mark.parametrize("field,value", [("status", "NOT_REVIEWED"),
    ("original_auditor_sha256", "0" * 64), ("original_review_sha256", "0" * 64),
    ("original_contract_sha256", "0" * 64), ("auditor_sha256", None)])
def test_v2_review_wrong_contract_rejected(tmp_path, monkeypatch, field, value):
    import json
    path, review = synthetic_v2_review(tmp_path, monkeypatch)
    review[field] = value
    path.write_text(json.dumps(review), encoding="utf-8")
    with pytest.raises(ValueError):
        M.v2_authority(M.sha(path))


def test_published_copy_cannot_watch(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "LAUNCH_ROOT", tmp_path)
    with pytest.raises(ValueError, match="canonical external"):
        M.watch("a" * 64)
    assert not (tmp_path / "watch_started.json").exists()


def test_published_cli_creates_no_operational_files(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "LAUNCH_ROOT", tmp_path)
    monkeypatch.setattr(M.sys, "argv", ["launcher", "--watch", "--v2-review-sha256", "a" * 64])
    with pytest.raises(ValueError, match="canonical external"):
        M.main()
    assert list(tmp_path.iterdir()) == []


def synthetic_audit_result(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "OUTPUT", tmp_path)
    spec = M.HERE / "MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDIT_CONTRACT.md"
    roots = {str(M.REVIEW.resolve()): "a" * 64,
             str(M.ORIGINAL_AUDITOR.resolve()): M.ORIGINAL_AUDITOR_SHA,
             str(M.ORIGINAL_REVIEW.resolve()): M.PINS[M.ORIGINAL_REVIEW],
             str(spec.resolve()): M.PINS[spec]}
    result = dict(status=M.AUDIT_STATUS, audit_script_sha256="b" * 64,
        binding=dict(monthly_root=str(M.SCIENCE), run_contract_sha256=M.CONTRACT_SHA,
                     session_audit_sha256=M.PINS[M.SOURCE_AUDIT],
                     completed_months=[f"2025{m:02d}" for m in range(1, 13)]),
        audited=dict(months=12, unique_fit_windows=24, calendar_ticker_days=750,
                     modes=["static", "expanding", "rolling12"],
                     validation_selection_reconstructed=True, validation_period_report_reconstructed=True),
        promotion_approved=False, verified_files=dict(root=roots))
    M.write_new(tmp_path / "audit.json", result)
    return result


def test_audit_closure_requires_v2_and_original_lineage(tmp_path, monkeypatch):
    import json
    result = synthetic_audit_result(tmp_path, monkeypatch)
    assert M.audit_result("b" * 64, "a" * 64)["status"] == M.AUDIT_STATUS
    result["verified_files"]["root"].pop(str(M.REVIEW.resolve()))
    (tmp_path / "audit.json").write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="missing reviewed V2/original lineage"):
        M.audit_result("b" * 64, "a" * 64)


def previous_chain_fixture(tmp_path, monkeypatch):
    previous = tmp_path / "failed01"
    previous.mkdir()
    monkeypatch.setattr(M, "PREVIOUS", previous)
    monkeypatch.setattr(M, "PREVIOUS_OUTPUT", tmp_path / "absent_output01")
    command = [str(M.PYTHON), "-u", str(M.ORIGINAL_AUDITOR), "--monthly-root", str(M.SCIENCE),
               "--source-audit", str(M.SOURCE_AUDIT), "--implementation-review", str(M.ORIGINAL_REVIEW),
               "--output", str(M.PREVIOUS_OUTPUT)]
    process = dict(status="AUDITOR_PROCESS_STARTED", pid=6840, creation_time=1792797439.9007168,
                   identity_source="GetProcessTimes on retained Popen handle", command=command,
                   started_utc="2026-10-23T23:17:19+00:00")
    M.write_new(previous / "process.json", process)
    pins = dict(M.PINS)
    pins[previous / "process.json"] = M.sha(previous / "process.json")
    pins[previous / "admission.json"] = "a" * 64
    pins[previous / "launch_when_validation_complete.py"] = "b" * 64
    exited = dict(status="AUDITOR_EXIT_OBSERVED_BY_POPEN_HANDLE", pid=6840,
                  creation_time=process["creation_time"], exit_code=1,
                  process_receipt_sha256=pins[previous / "process.json"],
                  observed_utc="2026-10-23T23:17:21+00:00")
    M.write_new(previous / "exit.json", exited)
    M.write_new(previous / "failure.json", dict(status="FAILED_PRESERVED_NO_RETRY", utc="2026-10-23T23:17:22+00:00"))
    M.write_new(previous / "attempt.json", dict(command=command, retry_allowed=False,
        admission_sha256=pins[previous / "admission.json"], script_sha256=pins[previous / "launch_when_validation_complete.py"]))
    for name in ("exit.json", "failure.json"):
        pins[previous / name] = M.sha(previous / name)
    pins[previous / "stderr.log"] = "c" * 64
    monkeypatch.setattr(M, "PINS", pins)
    return previous


def test_preserved_failure_chain(tmp_path, monkeypatch):
    previous_chain_fixture(tmp_path, monkeypatch)
    assert M.previous_failure()["audit_output_absent"] is True
    M.PREVIOUS_OUTPUT.mkdir()
    with pytest.raises(ValueError, match="must remain absent"):
        M.previous_failure()


@pytest.mark.parametrize("field,value", [("exit_code", 0), ("exit_code", True),
    ("pid", 88), ("creation_time", 0), ("process_receipt_sha256", "0" * 64)])
def test_previous_failure_cannot_be_reinterpreted(tmp_path, monkeypatch, field, value):
    import json
    previous = previous_chain_fixture(tmp_path, monkeypatch)
    path = previous / "exit.json"
    exited = M.read(path)
    exited[field] = value
    path.write_text(json.dumps(exited), encoding="utf-8")
    with pytest.raises(ValueError, match="retained exit/failure chain"):
        M.previous_failure()
