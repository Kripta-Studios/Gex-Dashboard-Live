"""Artificial metadata, byte payloads and children; never real market producers."""
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

NAME = "launch_oof_pipeline_user_stop_continuation_20261029"


def module():
    assert importlib.util.find_spec(NAME) is not None, "Continuation supervisor has not been implemented"
    return importlib.import_module(NAME)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def pin(path):
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def correction(a, month):
    old = a.old
    root = Path(a.scientific["correction_root"])
    deps = {n: a.scientific["code"][n] for n in old.dependency_sets()[0]}
    implementation = write(root / "implementation.json", dict(dependencies=deps,
        monthly_root=a.scientific["monthly_root"], session_root=a.scientific["session_root"],
        version="PREQUENTIAL_MAXIMUM_OFFSET_V1", calibrator_window="EXPANDING_FROM_202501",
        threshold=0, winner_selected=None)) if not (root / "implementation.json").exists() else pin(root / "implementation.json")
    contract = write(root / f"{month}.run_contract.json", dict(target_month=month,
        monthly_audit_sha256=a.scientific["monthly_audit"]["sha256"], implementation_sha256=implementation["sha256"]))
    inputs = write(root / f"{month}.inputs.json", dict(files=a.source_map,
        run_authorities={p["path"]: p["sha256"] for p in (implementation, contract)},
        dependencies=deps, monthly_audit_sha256=a.scientific["monthly_audit"]["sha256"]))
    procedures = {}
    for mode in ("static", "expanding", "rolling12"):
        cal = write(root / mode / month / "calibration.json", dict(procedure=mode, target_month=month, training_records=[]))
        procedures[mode] = dict(calibration_sha256=cal["sha256"], history_calendar=[], target_calendar=[])
    return write(root / f"{month}.complete.json", dict(status="COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS",
        target_month=month, monthly_audit_sha256=a.scientific["monthly_audit"]["sha256"],
        dependencies=deps, target_labels_read=False, base_models_refitted=False, winner_selected=None,
        development_seen=True, inputs_sha256=inputs["sha256"], procedures=procedures))


def replay(a, month):
    old = a.old
    root = Path(a.scientific["evaluation_roots"][month])
    deps = {n: a.scientific["code"][n] for n in old.dependency_sets()[1]}
    closed = pin(Path(a.scientific["correction_root"]) / f"{month}.complete.json")
    contract = write(root / "run_contract.json", dict(version="OOF_POLICY_REPLAY_V1", dependencies=deps,
        monthly_audit_sha256=a.scientific["monthly_audit"]["sha256"], correction_completion_sha256=closed["sha256"],
        target_month=month, threshold=0, winner_selected=None))
    files = {p["path"]: p["sha256"] for p in (closed, contract)}
    for name in ("summary.json", "all_scores_and_controls.json"):
        # Deliberately opaque economic payload: admission must never parse it.
        path = root / name
        path.write_bytes(b"not JSON: opaque artificial economics")
        files[str(path)] = pin(path)["sha256"]
    return write(root / "completion.json", dict(status="COMPLETE_FIXED_OOF_POLICY_MONTH", target_month=month,
        winner_selected=None, dependencies=deps, files=files, monthly_files=a.source_map))


def append_phase(a, index, month, stage):
    s = module()
    root = Path(a.scientific["pipeline_root"])
    previous = None if index == 0 else pin(root / f"receipts/{index-1:02d}.json")["sha256"]
    start = write(root / f"starts/{index:02d}.json", dict(request_sha256=a.request_pin["sha256"],
        phase=[month, stage], previous_receipt_sha256=previous, started_at_utc=f"2026-10-24T05:{31+index:02d}:00+00:00"))
    before = {} if index == 0 else s.read(root / f"receipts/{index-1:02d}.json")["output_inventory"]
    closed = correction(a, month) if stage == "correction" else replay(a, month)
    outputs = {}
    for directory in [Path(a.scientific["correction_root"]), *map(Path, a.scientific["evaluation_roots"].values())]:
        for path in directory.rglob("*"):
            if path.is_file() and path.name != ".lock":
                outputs[str(path)] = pin(path)["sha256"]
    receipt = write(root / f"receipts/{index:02d}.json", dict(status="COMPLETE_OOF_PIPELINE_PHASE",
        request_sha256=a.request_pin["sha256"], phase=[month, stage], previous_receipt_sha256=previous,
        start_sha256=start["sha256"], completion_sha256=closed["sha256"], output_inventory=outputs,
        new_output_bytes=sum(Path(p).stat().st_size for p in set(outputs)-set(before)),
        cumulative_output_bytes=sum(Path(p).stat().st_size for p in outputs),
        winner_selected=None, independent_audit_pending=True))
    return dict(phase=[month, stage], start=start, receipt=receipt, closure=closed)


@pytest.fixture
def artificial(tmp_path):
    s = module()
    old = s.operational_modules()[0]
    import test_run_oof_calibrated_pipeline_v2r1 as fixtures
    monthly, index, session = fixtures.metadata_sources.__wrapped__(tmp_path / "sources")
    monthly_root, session_root = tmp_path / "monthly", index.parent
    contract = write(monthly_root / "run_contract.json", {"artificial": True})
    session_pin = write(tmp_path / "session_audit.json", dict(status="PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT",
        binding=dict(**session["binding"], engine_root=str(session_root), index_sha256=pin(index)["sha256"])))
    monthly_pin = write(tmp_path / "monthly_audit.json", dict(status="PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_TEST_COMPOSITE_AUDIT",
        verified_files=monthly["verified_files"], binding=dict(monthly_root=str(monthly_root), session_root=str(session_root),
        completed_months=list(old.HISTORY), run_contract_sha256=contract["sha256"],
        session_audit_sha256=session_pin["sha256"], index_sha256=pin(index)["sha256"])))
    _, deps = old.implementation_files()
    scientific = dict(version="OOF_PIPELINE_RUNTIME_REQUEST_V2R1", status="REVIEWED_OOF_PIPELINE_RUNTIME_REQUEST",
        runtime_authorized=True, months=old.MONTHS, code=deps, monthly_root=str(monthly_root), session_root=str(session_root),
        monthly_audit=monthly_pin, session_audit=session_pin, coordination_lock=str(tmp_path / "runtime.lock"),
        pipeline_root=str(tmp_path / "pipeline"), correction_root=str(tmp_path / "correction"),
        evaluation_roots={m:str(tmp_path / ("replay_"+m)) for m in old.MONTHS})
    request_pin = write(tmp_path / "original_request.json", scientific)
    a = SimpleNamespace(old=old,scientific=scientific, request_pin=request_pin, source_map=monthly["verified_files"]["fit_inputs"])
    admission = old.request_admission(scientific)
    a.admission = admission
    pipeline = Path(scientific["pipeline_root"])
    write(pipeline / "request.json", scientific)
    write(pipeline / "contract.json", dict(version="OOF_PIPELINE_V2R1", request_sha256=request_pin["sha256"],
        code=deps, correction_layout="SHARED_CUMULATIVE", source_admission_sha256=admission["map_sha256"]))
    phases = [append_phase(a,i,m,t) for i,(m,t) in enumerate((m,t) for m in old.MONTHS[:4] for t in ("correction","replay"))]
    locks = {}
    for directory in [Path(scientific["correction_root"]), *[Path(scientific["evaluation_roots"][m]) for m in old.MONTHS[:4]]]:
        (directory / ".lock").write_bytes(b"0")
        locks[str(directory / ".lock")] = pin(directory / ".lock")["sha256"]
    a.operational = dict(expected_completed_phases=8, adopted_phases=phases, tail_receipt_sha256=phases[-1]["receipt"]["sha256"],
        source_admission_sha256=admission["map_sha256"], remaining_phases=[["202605","correction"],["202605","replay"],["202606","correction"],["202606","replay"]],
        original_request=request_pin, preserved_root_locks=locks)
    a.interval = dict(creation_time=1792819783.154357, observed_exit_time=1792823850.47794)
    return a


def test_command_has_only_original_request_and_resume():
    s = module()
    assert s.command(Path("C:/fixture/request.json"), "a"*64) == [sys.executable,"-u",str(s.WRAPPER),"--request","C:\\fixture\\request.json","--request-sha256","a"*64,"--resume"]


def test_prefix_metadata_accepts_eight_without_economic_parsing(artificial):
    a = artificial
    baseline = module().validate_adopted_prefix(a.scientific,a.operational,a.admission,a.interval)
    assert len(baseline["controls"]) == 18 and len(baseline["locks"]) == 5
    assert baseline["completed_phases"] == 8
    assert baseline["tail_receipt_sha256"] == a.operational["tail_receipt_sha256"]


@pytest.mark.parametrize("fault", ["count7","count9","gap","start08","completion","partial","orphan","tail","request","receipt","start","output","input","lock","hardlink","closure","flags","source_hash","source_alias","time"])
def test_prefix_rejects_mutation_before_launch(artificial,fault):
    a = artificial
    s = module()
    root = Path(a.scientific["pipeline_root"])
    if fault.startswith("count"):
        a.operational["expected_completed_phases"] = int(fault[-1])
    elif fault == "gap":
        (root / "receipts/03.json").unlink()
    elif fault in ("start08","completion","partial","orphan"):
        write(root / {"start08":"starts/08.json","completion":"completion.json","partial":"x.partial","orphan":"other.json"}[fault],{})
    elif fault in ("tail","request"):
        if fault == "tail": a.operational["tail_receipt_sha256"] = "0"*64
        else: a.operational["original_request"]["sha256"] = "0"*64
    elif fault in ("receipt","start","closure"):
        Path(a.operational["adopted_phases"][0][fault]["path"]).write_bytes(b"changed")
    elif fault in ("flags","time"):
        kind = "receipt" if fault == "flags" else "start"
        ref = a.operational["adopted_phases"][0][kind]
        value = s.read(ref["path"])
        value["winner_selected" if fault == "flags" else "started_at_utc"] = "INVALID"
        a.operational["adopted_phases"][0][kind] = write(Path(ref["path"]),value)
    elif fault in ("output","lock"):
        mapping = s.read(root / "receipts/07.json")["output_inventory"] if fault == "output" else a.operational["preserved_root_locks"]
        Path(next(iter(mapping))).write_bytes(b"mutation")
    elif fault == "input":
        Path(next(iter(a.source_map))).write_bytes(b"changed input")
    elif fault == "hardlink":
        target = Path(next(iter(a.source_map)))
        os.link(target,target.with_name("hardlink"))
    elif fault == "source_hash":
        for item in a.admission["members"].values(): item["sha256"] = "0"*64
    else:
        item = next(iter(a.admission["members"].values()))
        item["path"] = item["path"].replace("sources", "SOURCES")
    with pytest.raises((ValueError,FileNotFoundError,KeyError)):
        s.validate_adopted_prefix(a.scientific,a.operational,a.admission,a.interval)


def test_default_cli_never_launches(monkeypatch,capsys):
    s = module()
    monkeypatch.setattr(sys,"argv",["test","--request","request.json","--request-sha256","a"*64,
        "--runtime-binding","binding.json","--runtime-binding-sha256","b"*64,
        "--implementation-review-sha256","c"*64,"--publication-commit","d"*40])
    monkeypatch.setattr(s,"preflight",lambda *args:dict(executed=False,synthetic=True))
    monkeypatch.setattr(s,"launch",lambda *args:pytest.fail("Default spawned child"))
    assert s.main() == 0 and json.loads(capsys.readouterr().out)["executed"] is False


def test_cpu0_is_inherited_at_first_child_instruction(tmp_path):
    s = module()
    import psutil
    before = psutil.Process().cpu_affinity()
    try:
        record = s.establish_cpu0()
        # ctypes GetProcessAffinityMask is the first executed statement after imports.
        script = "import ctypes,os,json; p=ctypes.c_size_t(); q=ctypes.c_size_t(); k=ctypes.WinDLL('kernel32'); k.GetCurrentProcess.restype=ctypes.c_void_p; k.GetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]; assert k.GetProcessAffinityMask(k.GetCurrentProcess(),ctypes.byref(p),ctypes.byref(q)); print(json.dumps({'mask':p.value,'threads':[os.environ[x] for x in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')]}))"
        result = subprocess.run([sys.executable,"-c",script],env=s.child_environment(),capture_output=True,text=True,check=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
        assert json.loads(result.stdout) == dict(mask=1,threads=["1","1","1"])
        assert record["parent_cpu_affinity"] == [0]
    finally:
        psutil.Process().cpu_affinity(before)


def test_failed_affinity_is_fail_closed(monkeypatch):
    s = module()
    import psutil
    class Denied:
        def cpu_affinity(self,value=None):
            if value is not None: raise OSError("denied affinity")
            return [1]
    monkeypatch.setattr(psutil,"Process",lambda *a:Denied())
    with pytest.raises(OSError): s.establish_cpu0()


def test_retained_handle_failure_drains_child(tmp_path):
    s = module()
    drained = []
    def broken(child): raise OSError("retained handle unavailable")
    helper = SimpleNamespace(RetainedProcess=broken,drain_child=lambda c:drained.append(c))
    child = object()
    with pytest.raises(OSError): s.monitor(child,dict(logs_root=str(tmp_path)),helper,None,"a"*64)
    assert drained == [child] and not (tmp_path / "exit.json").exists()


@pytest.mark.parametrize("fault",["quick_exit","sampling_error","affinity_drift"])
def test_monitor_preserves_retained_exit_on_sampling_race(tmp_path,monkeypatch,fault):
    s = module()
    _,ops,helper = s.operational_modules()
    import psutil
    receipt = dict(logs_root=str(tmp_path),files={str(Path(s.__file__).resolve()):s.sha(s.__file__)},
        request_sha256="a"*64,runtime_binding_sha256="b"*64,implementation_review_sha256="c"*64,
        publication_commit="d"*40,command=[sys.executable,"-c","pass"])
    before = psutil.Process().cpu_affinity()
    try:
        s.establish_cpu0()
        child = subprocess.Popen([sys.executable,"-c","import time;time.sleep(1.2)"],creationflags=subprocess.CREATE_NO_WINDOW)
        if fault=="quick_exit":
            child.wait()
        if fault=="sampling_error":
            monkeypatch.setattr(ops,"observation",lambda:(_ for _ in ()).throw(OSError("synthetic sample failure")))
        if fault=="affinity_drift":
            real = psutil.Process
            class Changed:
                def __init__(self,pid): self.p = real(pid)
                def create_time(self): return self.p.create_time()
                def cpu_affinity(self): return [1]
            monkeypatch.setattr(psutil,"Process",Changed)
        result = s.monitor(child,receipt,helper,ops,"e"*64)
        assert result["exit_code"]==0 and s.read(tmp_path/"exit.json")["exit_code"]==0
        assert s.read(tmp_path/"exit.json")["pid"]==child.pid
        assert result["monitor_valid"] is (fault!="affinity_drift")
    finally:
        helper.drain_child(child)
        monkeypatch.undo()
        psutil.Process().cpu_affinity(before)
