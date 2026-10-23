"""Operational fixtures only: no market files or real child process."""

from copy import deepcopy
import json
import sys
import time
from types import SimpleNamespace

import pytest

import launch_common_greek_audit_02 as launcher


def reviewed():
    return {"status": launcher.REVIEW_STATUS, "decision": "CLEAR",
            "scope": "IMPLEMENTATION_ONLY", "runtime_authorized": False,
            "binding": {"original_auditor": {
                "audit_common_greek_comparison.py": launcher.ORIGINAL_AUDITOR_SHA},
                "reviewed_implementation": {
                    "audit_common_greek_comparison_paths_v2.py": "a" * 64,
                    "test_audit_common_greek_comparison_paths_v2.py": "b" * 64,
                    "COMMON_GREEK_COMPARISON_PATH_AUDIT_V2_SPEC_20261023.md": "c" * 64}}}


def free(value=2_000_000_000):
    return {"available_ram_bytes": value, "free_commit_bytes": value}


def test_both_resource_limits_are_required_inclusive():
    launcher.resource_gate(free())
    for field in free():
        observed = free()
        observed[field] -= 1
        with pytest.raises(RuntimeError, match="admission gate"):
            launcher.resource_gate(observed)


def test_clear_implementation_review_is_separate_from_runtime_authorization():
    original = reviewed()
    assert launcher.validate_v2_review(original) == original["binding"]["reviewed_implementation"]
    changed = deepcopy(original)
    changed["runtime_authorized"] = True
    with pytest.raises(RuntimeError, match="not CLEAR"):
        launcher.validate_v2_review(changed)
    changed = deepcopy(original)
    changed["binding"]["original_auditor"]["audit_common_greek_comparison.py"] = "0" * 64
    with pytest.raises(RuntimeError, match="Original auditor"):
        launcher.validate_v2_review(changed)
    changed = deepcopy(original)
    changed["binding"]["reviewed_implementation"]["extra.py"] = "d" * 64
    with pytest.raises(RuntimeError, match="membership"):
        launcher.validate_v2_review(changed)


def test_external_review_pin_checked_before_admitting_other_inputs(tmp_path, monkeypatch):
    review = tmp_path / "review.json"
    review.write_text(json.dumps(reviewed()), encoding="utf-8")
    monkeypatch.setattr(launcher, "V2_REVIEW", review)
    monkeypatch.setattr(launcher, "OUT", tmp_path / "out")
    monkeypatch.setattr(launcher, "LOGS", tmp_path / "logs")
    with pytest.raises(RuntimeError, match="External V2 review pin differs"):
        launcher.preflight("0" * 64, "0" * 40)
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "logs").exists()


def test_publication_rejects_different_git_object(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "REPO", tmp_path)
    path = tmp_path / "script.py"
    path.write_bytes(b"reviewed")
    monkeypatch.setattr(launcher.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=b"changed"))
    with pytest.raises(RuntimeError, match="Published Git object differs"):
        launcher.verify_publication("a" * 40, {path: launcher.sha(path)})


def test_default_cli_is_preflight_only(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["launcher", "--v2-review-sha256", "a" * 64,
                                     "--publication-commit", "b" * 40])
    monkeypatch.setattr(launcher, "preflight", lambda *args: {"status": "SYNTHETIC_PREFLIGHT"})
    monkeypatch.setattr(launcher, "launch", lambda *args: pytest.fail("Unexpected child launch"))
    assert launcher.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "SYNTHETIC_PREFLIGHT"


def test_child_command_keeps_scientific_review_and_uses_only_new_auditor_output():
    command = launcher.command()
    assert command[2] == str(launcher.V2)
    assert command[command.index("--review") + 1] == str(launcher.ORIGINAL_REVIEW)
    assert command[command.index("--output") + 1] == str(launcher.OUT)
    assert "--stage" not in command and "--fit" not in command


def setup_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "OUT", tmp_path / "audit02")
    monkeypatch.setattr(launcher, "LOGS", tmp_path / "logs02")
    monkeypatch.setattr(launcher, "verify_pins", lambda *args: None)
    monkeypatch.setattr(launcher, "handle_creation_time", lambda child: 123.5)
    return {"files": {}, "command": ["synthetic-child"]}


def test_memory_rechecked_immediately_before_child(tmp_path, monkeypatch):
    receipt = setup_launch(tmp_path, monkeypatch)
    observed = iter([free(), free(1_999_999_999)])
    monkeypatch.setattr(launcher, "resources", lambda: next(observed))
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k: pytest.fail("Gate bypass"))
    with pytest.raises(RuntimeError, match="admission gate"):
        launcher.launch(receipt)
    assert (launcher.LOGS / "preflight.json").exists()
    assert not (launcher.LOGS / "process.json").exists()


def test_exit_is_child_handle_exit_and_never_auto_retries(tmp_path, monkeypatch):
    import psutil

    receipt = setup_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(launcher, "resources", free)
    monkeypatch.setattr(launcher.time, "sleep", lambda *args: None)
    calls = []

    class Child:
        pid = 123456
        returncode = None
        polls = 0

        def poll(self):
            self.polls += 1
            if self.polls > 1:
                self.returncode = 1
            return self.returncode

    def spawn(*args, **kwargs):
        calls.append((args, kwargs))
        return Child()

    monkeypatch.setattr(launcher.subprocess, "Popen", spawn)
    monkeypatch.setattr(psutil, "Process", lambda pid: SimpleNamespace(
        create_time=lambda: 123.5,
        memory_info=lambda: SimpleNamespace(rss=1024, private=512)))
    assert launcher.launch(receipt) == 1
    assert len(calls) == 1
    assert calls[0][1]["env"]["OMP_NUM_THREADS"] == "1"
    result = json.loads((launcher.LOGS / "exit.json").read_text())
    assert result["exit_code"] == 1 and result["retry"] is False
    assert result["peak_sampled_rss_bytes"] == 1024
    assert result["sample_count"] == 1
    assert not launcher.OUT.exists()


def test_fast_real_python_exit_keeps_creation_from_retained_handle():
    if sys.platform != "win32":
        pytest.skip("Windows process handle fixture")
    started = time.time()
    child = launcher.subprocess.Popen([sys.executable, "-c", "pass"],
                                      creationflags=launcher.subprocess.CREATE_NO_WINDOW)
    assert child.wait(timeout=10) == 0
    created = launcher.handle_creation_time(child)
    assert started - 1 <= created <= time.time() + 1
    assert launcher.handle_creation_time(child) == created


def test_fast_child_without_memory_samples_does_not_report_zero_peaks(tmp_path, monkeypatch):
    import psutil

    receipt = setup_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(launcher, "resources", free)
    child = SimpleNamespace(pid=123456, returncode=0, poll=lambda: 0)
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: child)

    def missing(pid):
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(psutil, "Process", missing)
    assert launcher.launch(receipt) == 0
    process = json.loads((launcher.LOGS / "process.json").read_text())
    result = json.loads((launcher.LOGS / "exit.json").read_text())
    assert process["creation_time"] == 123.5
    assert process["creation_time_source"] == "GetProcessTimes_retained_Popen_handle"
    assert result["sample_count"] == 0
    assert result["peak_sampled_rss_bytes"] is None
    assert result["peak_sampled_private_bytes"] is None
    assert result["monitor_errors"][0]["stage"] == "process_identity"


def test_reused_pid_identity_cannot_supply_memory_samples(tmp_path, monkeypatch):
    import psutil

    receipt = setup_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(launcher, "resources", free)
    monkeypatch.setattr(launcher.time, "sleep", lambda *args: None)
    polls = iter([None, 0])
    child = SimpleNamespace(pid=123456, returncode=0, poll=lambda: next(polls))
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: child)
    monkeypatch.setattr(psutil, "Process", lambda pid: SimpleNamespace(
        create_time=lambda: 124.5,
        memory_info=lambda: pytest.fail("Memory attributed to reused PID")))
    assert launcher.launch(receipt) == 0
    result = json.loads((launcher.LOGS / "exit.json").read_text())
    assert result["sample_count"] == 0 and result["peak_sampled_rss_bytes"] is None
    assert result["monitor_errors"][0]["error"] == "PID creation mismatch"


def test_memory_monitor_error_preserves_real_child_exit(tmp_path, monkeypatch):
    import psutil

    receipt = setup_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(launcher, "resources", free)
    monkeypatch.setattr(launcher.time, "sleep", lambda *args: None)
    polls = iter([None, 2])
    child = SimpleNamespace(pid=123456, returncode=2, poll=lambda: next(polls))
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: child)

    def denied():
        raise psutil.AccessDenied(123456)

    monkeypatch.setattr(psutil, "Process", lambda pid: SimpleNamespace(
        create_time=lambda: 123.5, memory_info=denied))
    assert launcher.launch(receipt) == 2
    result = json.loads((launcher.LOGS / "exit.json").read_text())
    assert result["exit_code"] == 2 and result["retry"] is False
    assert result["sample_count"] == 0 and result["peak_sampled_private_bytes"] is None
    assert result["monitor_errors"][0]["stage"] == "process_memory"
