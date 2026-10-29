"""Independent artificial review cases for the new operational boundary."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
import hashlib
import importlib
import json
import os
import subprocess
import sys

import pytest


def subject():
    return importlib.import_module("launch_oof_pipeline_user_stop_continuation_20261029")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def final_state(s, tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    preflight_sha = write(logs / "preflight.json", {"synthetic": True})
    write(logs / "admission.json", {"synthetic": True})
    (logs / "stdout.log").write_bytes(b"")
    (logs / "stderr.log").write_bytes(b"")
    code_path = str(Path(s.__file__).resolve())
    code_sha = s.sha(code_path)
    authority = dict(monitor_code_sha256=code_sha, request_sha256="b" * 64,
        runtime_binding_sha256="c" * 64, implementation_review_sha256="d" * 64,
        publication_commit="e" * 40, preflight_sha256=preflight_sha)
    created = datetime.fromisoformat("2026-10-29T10:00:00+00:00").timestamp()
    ended = "2026-10-29T10:10:00+00:00"
    process_sha = write(logs / "process.json", dict(**authority, status="PROCESS_HANDLE_RETAINED", pid=424242,
        creation_time=created, command=["synthetic_child"], creation_time_source="GetProcessTimes_retained_Popen_handle",
        initial_child_affinity_verified=True, child_cpu_affinity=[0], monitor_started_utc="2026-10-29T10:00:01+00:00"))
    exit_sha = write(logs / "exit.json", dict(**authority, status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE", pid=424242,
        creation_time=created, exit_code=0, exit_code_source="GetExitCodeProcess_retained_Popen_handle",
        process_receipt_sha256=process_sha, monitor_valid=True, observed_utc=ended))
    receipt = dict(logs_root=str(logs), command=["synthetic_child"], files={code_path: code_sha},
        request_sha256="b" * 64, runtime_binding_sha256="c" * 64, implementation_review_sha256="d" * 64,
        publication_commit="e" * 40, source_admission_sha256="a" * 64,
        baseline={"outputs": {}}, protected_trees={})
    monitored = dict(exit_code=0, monitor_valid=True, pid=424242, creation_time=created,
        observed_exit_time=datetime.fromisoformat(ended).timestamp(), files={str(logs / "preflight.json"): preflight_sha,
        str(logs / "process.json"): process_sha, str(logs / "exit.json"): exit_sha})
    return receipt, monitored


def test_unreviewed_transitive_helper_rejected_before_import(monkeypatch, tmp_path):
    s = subject()
    old_review = tmp_path / "old_review.json"
    old = SimpleNamespace(REVIEW=old_review, REVIEW_STATUS="REVIEWED",
        implementation_files=lambda: ({"overlay.py": "a" * 64}, {}))
    imported = []

    def importer(name):
        imported.append(name)
        assert name == s.ORIGINAL.removesuffix(".py"), "Helper imported before external map check"
        return old

    def reader(path):
        if Path(path) == old_review:
            return dict(status="REVIEWED", decision="CLEAR", scope="IMPLEMENTATION_ONLY",
                runtime_authorized=False, files={"overlay.py": "b" * 64})
        return {"implementation_review": {"path": str(old_review), "sha256": "c" * 64}}

    monkeypatch.setattr(s, "verify", lambda files: None)
    monkeypatch.setattr(s, "read", reader)
    monkeypatch.setattr(s.importlib, "import_module", importer)
    with pytest.raises(ValueError, match="Frozen operational import closure"):
        s.operational_modules()
    assert imported == [s.ORIGINAL.removesuffix(".py")]


@pytest.mark.parametrize("fault,expected_valid", [("exit_race", True), ("initial_missing", False), ("affinity_drift", False)])
def test_monitor_preserves_real_exit_across_observation_faults(monkeypatch, tmp_path, fault, expected_valid):
    s = subject()
    import psutil
    created = 1793289600.0
    returns = iter([None, 0])
    process = SimpleNamespace(pid=424242)
    drains = []

    class Retained:
        def __init__(self, child):
            assert child is process
        def creation_time(self):
            return created
        def wait_exit(self):
            return next(returns)

    class Sample:
        reads = 0
        def create_time(self):
            return created
        def cpu_affinity(self):
            self.reads += 1
            if self.reads == 1:
                return [0]
            if fault == "exit_race":
                raise psutil.NoSuchProcess(process.pid)
            return [1]

    def process_factory(pid):
        assert pid == process.pid
        if fault == "initial_missing":
            raise psutil.NoSuchProcess(pid)
        return Sample()

    def publish(directory, name, value):
        path = directory / name
        assert not path.exists()
        return write(path, value)

    monkeypatch.setattr(psutil, "Process", process_factory)
    helper = SimpleNamespace(RetainedProcess=Retained, publish=publish, drain_child=lambda child: drains.append(child))
    ops = SimpleNamespace(observation=lambda: dict(available_ram_bytes=3_000_000_000, free_commit_bytes=3_000_000_000))
    preflight_sha = write(tmp_path / "preflight.json", {"synthetic": True})
    receipt = dict(logs_root=str(tmp_path), files={str(Path(s.__file__).resolve()): "a" * 64},
        request_sha256="b" * 64, runtime_binding_sha256="c" * 64, implementation_review_sha256="d" * 64,
        publication_commit="e" * 40, command=["synthetic_child"])
    result = s.monitor(process, receipt, helper, ops, preflight_sha)
    ended = s.read(tmp_path / "exit.json")
    opened = s.read(tmp_path / "process.json")
    assert result["exit_code"] == ended["exit_code"] == 0
    assert result["monitor_valid"] is expected_valid and ended["monitor_valid"] is expected_valid
    assert ended["exit_code_source"] == "GetExitCodeProcess_retained_Popen_handle"
    assert ended["pid"] == opened["pid"] == process.pid
    assert ended["creation_time"] == opened["creation_time"] == created
    assert ended["process_receipt_sha256"] == s.sha(tmp_path / "process.json")
    assert ended["monitor_errors"] and drains == []
    s.verify(result["files"])


@pytest.mark.parametrize("kind", ["prior_output", "old_stop", "snapshot_copy", "root_lock"])
def test_final_validation_rejects_late_preserved_byte_mutation(monkeypatch, tmp_path, kind):
    s = subject()
    receipt, monitored = final_state(s, tmp_path)
    preserved = tmp_path / kind
    preserved.write_bytes(b"preserved bytes")
    expected = s.sha(preserved)
    pipeline = tmp_path / "pipeline"
    write(pipeline / "receipts/11.json", {"output_inventory": {str(preserved): expected}})

    def validate(*args):
        preserved.write_bytes(b"changed after final validation")
        return {"source_admission_sha256": "a" * 64}

    old = SimpleNamespace(validate_pipeline=validate, tree_files=lambda root: {str(p) for p in root.rglob("*") if p.is_file()})
    monkeypatch.setattr(s, "operational_modules", lambda: (old, None, None))
    receipt["baseline"]["outputs"][str(preserved)] = expected
    receipt["files"][str(preserved)] = expected
    with pytest.raises(ValueError, match="Pinned bytes differ"):
        s.validate_final({"pipeline_root": str(pipeline)}, {"original_request": {"sha256": "b" * 64}},
            receipt, monitored)


def test_new_phase_chronology_uses_new_process_interval(monkeypatch, tmp_path):
    s = subject()
    receipt, monitored = final_state(s, tmp_path)
    pipeline = tmp_path / "pipeline"
    source_sha = "a" * 64
    write(pipeline / "receipts/11.json", {"output_inventory": {}})
    for index, phase in enumerate(s.REMAINING, start=8):
        write(pipeline / f"starts/{index:02d}.json", {"phase": phase, "started_at_utc": "2026-10-24T06:00:00+00:00"})
    old = SimpleNamespace(validate_pipeline=lambda *args: {"source_admission_sha256": source_sha},
        tree_files=lambda root: {str(p) for p in root.rglob("*") if p.is_file()})
    monkeypatch.setattr(s, "operational_modules", lambda: (old, None, None))
    with pytest.raises(ValueError, match="outside continuation process interval"):
        s.validate_final({"pipeline_root": str(pipeline)}, {"original_request": {"sha256": "b" * 64}},
            receipt, monitored)


@pytest.mark.parametrize("target", ["new_logs", "preserved_tree"])
def test_added_failure_cannot_coexist_with_valid_final_closure(monkeypatch, tmp_path, target):
    s = subject()
    receipt, monitored = final_state(s, tmp_path)
    pipeline = tmp_path / "pipeline"
    write(pipeline / "receipts/11.json", {"output_inventory": {}})
    preserved = tmp_path / "preserved"
    preserved.mkdir()
    receipt["protected_trees"] = {str(preserved): []}
    if target == "new_logs":
        write(Path(receipt["logs_root"]) / "failure.json", {"unexpected": True})

    def validate(*args):
        if target == "preserved_tree":
            write(preserved / "new_failure.json", {"unexpected": True})
        return {"source_admission_sha256": "a" * 64}

    old = SimpleNamespace(validate_pipeline=validate, tree_files=lambda root: {str(p) for p in root.rglob("*") if p.is_file()})
    monkeypatch.setattr(s, "operational_modules", lambda: (old, None, None))
    expected = "Unexpected continuation log artifact" if target == "new_logs" else "Preserved evidence tree membership changed"
    with pytest.raises(ValueError, match=expected):
        s.validate_final({"pipeline_root": str(pipeline)}, {"original_request": {"sha256": "b" * 64}}, receipt, monitored)


def test_cpu0_and_threads_observed_by_independent_first_statement(tmp_path):
    s = subject()
    import psutil
    before = psutil.Process().cpu_affinity()
    try:
        admitted = s.establish_cpu0()
        code = "import ctypes,json,os; k=ctypes.WinDLL('kernel32',use_last_error=True); k.GetCurrentProcess.restype=ctypes.c_void_p; k.GetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]; p=ctypes.c_size_t(); q=ctypes.c_size_t(); ok=k.GetProcessAffinityMask(k.GetCurrentProcess(),ctypes.byref(p),ctypes.byref(q)); print(json.dumps({'ok':ok,'mask':p.value,'threads':[os.environ[x] for x in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')]}))"
        result = subprocess.run([sys.executable, "-c", code], env=s.child_environment(), capture_output=True,
            text=True, encoding="utf-8", check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        observed = json.loads(result.stdout)
        assert observed == {"ok": 1, "mask": 1, "threads": ["1", "1", "1"]}
        assert admitted["parent_cpu_affinity"] == [0]
        evidence = {"status": "PASS_FIRST_INSTRUCTION_CPU0_THREADS1", "parent": admitted,
            "child_observation": {"mask": observed["mask"], "threads": observed["threads"]}, "win32_api_succeeded": observed["ok"] == 1,
            "code_sha256": s.sha(s.__file__), "tests_sha256": s.sha(Path(s.__file__).with_name("test_launch_oof_pipeline_user_stop_continuation_20261029.py")),
            "child_exit_code": result.returncode, "script_sha256": hashlib.sha256(code.encode()).hexdigest(),
            "scope": "Artificial child observed affinity before any scientific work; no producer invoked."}
        target = Path(os.environ["OOF_REVIEW_ATTEMPT_DIR"]) / "cpu0_independent_evidence.json"
        assert not target.exists()
        write(target, evidence)
    finally:
        psutil.Process().cpu_affinity(before)
