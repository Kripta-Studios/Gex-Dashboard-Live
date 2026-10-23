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
    command = M.audit_command()
    assert command[2].endswith("audit_monthly_walk_forward.py")
    assert command[3::2] == ["--monthly-root", "--source-audit", "--implementation-review", "--output"]
    assert "--stage" not in command
