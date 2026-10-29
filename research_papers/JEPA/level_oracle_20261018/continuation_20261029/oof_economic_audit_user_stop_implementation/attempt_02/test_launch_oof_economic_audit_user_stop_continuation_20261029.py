"""Artificial two-process provenance; never execute the scientific auditor."""

import importlib.util
from pathlib import Path


def test_operational_adapter_exists_separately_from_frozen_supervisor():
    name = "launch_oof_economic_audit_user_stop_continuation_20261029"
    spec = importlib.util.find_spec(name)
    assert spec is not None, "A separate continuation audit supervisor is required"
    assert Path(spec.origin).name == name + ".py"


import importlib
import json
import hashlib
import shutil
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
import test_launch_oof_economic_audit_v2r1_20261024 as legacy


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value), encoding="utf-8")
    return {"path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}


def rewrite(ref, value):
    ref.update(write(Path(ref["path"]),value))


@pytest.fixture
def case(tmp_path, monkeypatch):
    s=importlib.import_module("launch_oof_economic_audit_user_stop_continuation_20261029")
    real_code=s.CODE
    c=legacy.case.__wrapped__(tmp_path, monkeypatch)
    for key,value in (("CODE",c.code),("REPO",tmp_path),("BASE",c.base)):
        monkeypatch.setattr(s,key,value)
    refs=c.binding["upstream"]
    source_ref=refs["pipeline_request"]
    runtime_ref=refs["pipeline_binding"]
    monkeypatch.setattr(s,"ORIGINAL_REQUEST_PATH",Path(source_ref["path"]))
    monkeypatch.setattr(s,"ORIGINAL_BINDING_PATH",Path(runtime_ref["path"]))
    monkeypatch.setattr(s,"ORIGINAL_REQUEST_SHA",source_ref["sha256"])
    monkeypatch.setattr(s,"ORIGINAL_BINDING_SHA",runtime_ref["sha256"])
    for name in (*s.NEW_FILES,s.NAME,s.CONTINUATION_CODE,s.CONTINUATION_TEST,s.DESIGN_REVIEW,s.ORIGINAL_AUDIT_REVIEW,"RESUMPTION_20261029.md"):
        shutil.copyfile(real_code/name,c.code/name)
    continuation_files={n:s.sha(c.code/n) for n in (s.CONTINUATION_CODE,s.CONTINUATION_TEST,*legacy.s.NEW_FILES)}
    continuation_review=write(c.code/s.CONTINUATION_REVIEW,dict(status="PASS_OOF_USER_STOP_CONTINUATION_IMPLEMENTATION_REVIEW",decision="CLEAR",scope="IMPLEMENTATION_ONLY",runtime_authorized=False,files=continuation_files,cpu0_inheritance_test={"status":"PASS_FIRST_INSTRUCTION_CPU0_THREADS1"}))
    source_sha=s.SOURCE_SHA
    pre=s.read(refs["preflight"]["path"]);pre["source_admission_sha256"]=source_sha;rewrite(refs["preflight"],pre)
    proc=s.read(refs["process"]["path"])
    proc.update(creation_time=datetime(2026,10,24,1,tzinfo=timezone.utc).timestamp(),preflight_sha256=refs["preflight"]["sha256"])
    rewrite(refs["process"],proc)
    ended=s.read(refs["exit"]["path"]);ended.update(creation_time=proc["creation_time"],exit_code=15,preflight_sha256=refs["preflight"]["sha256"],process_receipt_sha256=refs["process"]["sha256"]);rewrite(refs["exit"],ended)
    failure=write(c.logs/"failure.json",dict(status="FAILED_OR_INTERRUPTED_PRESERVED",retry=False,error="ValueError('OOF child must exit zero')",utc="2026-10-24T01:01:01+00:00"))
    monkeypatch.setattr(s,"ORIGINAL_FAILURE_SHA",failure["sha256"])
    observer=c.base/"oof_pipeline_v2r1_observer_20261024_01"
    stop=write(observer/"user_stop.json",dict(status="STOPPED_BY_EXPLICIT_USER_REQUEST",automatic_resume=False,artifacts_preserved=True,remaining_known_research_processes=[],identities_before_stop=[dict(pid=789,creation=proc["creation_time"],command=proc["command"])],utc="2026-10-24T01:01:02+00:00"))
    post=write(observer/"post_stop_verification.json",dict(remaining_research_python_pids=[],phase_receipts=[f"{i:02d}.json" for i in range(8)],phase_starts=[f"{i:02d}.json" for i in range(8)],pipeline_completion_exists=False,supervisor_exit_exists=True,supervisor_failure_exists=True,utc="2026-10-24T01:01:03+00:00"))
    monkeypatch.setattr(s,"ORIGINAL_STOP_SHA",stop["sha256"])
    monkeypatch.setattr(s,"ORIGINAL_POST_STOP_SHA",post["sha256"])
    old_finished=s.read(refs["supervisor_completion"]["path"])
    Path(refs["supervisor_completion"]["path"]).unlink()
    closed=old_finished["pipeline_closure"];closed["source_admission_sha256"]=source_sha
    compact=closed["compact_files"]
    contract=s.read(c.pipeline/"contract.json");contract["source_admission_sha256"]=source_sha
    compact[str(c.pipeline/"contract.json")]=write(c.pipeline/"contract.json",contract)["sha256"]
    previous=None;adopted=[];new=[]
    for i in range(12):
        start_path=c.pipeline/f"starts/{i:02d}.json";receipt_path=c.pipeline/f"receipts/{i:02d}.json"
        start=s.read(start_path);start.update(previous_receipt_sha256=previous,started_at_utc=f"2026-10-{'24' if i<8 else '29'}T01:00:{i+1:02d}+00:00")
        start_ref=write(start_path,start);compact[str(start_path)]=start_ref["sha256"]
        r=s.read(receipt_path);r.update(previous_receipt_sha256=previous,start_sha256=start_ref["sha256"])
        receipt_ref=write(receipt_path,r);compact[str(receipt_path)]=receipt_ref["sha256"];previous=receipt_ref["sha256"]
        phase=dict(phase=start["phase"],start=start_ref,receipt=receipt_ref)
        if i<8:
            month,stage=start["phase"]
            closure=Path(c.source["correction_root"])/(month+".complete.json") if stage=="correction" else Path(c.source["evaluation_roots"][month])/"completion.json"
            adopted.append(dict(**phase,closure={"path":str(closure),"sha256":compact[str(closure)]}))
        else: new.append(phase)
    pipeline_complete=s.read(refs["pipeline_completion"]["path"]);pipeline_complete["last_receipt_sha256"]=previous
    rewrite(refs["pipeline_completion"],pipeline_complete);compact[refs["pipeline_completion"]["path"]]=refs["pipeline_completion"]["sha256"]
    monkeypatch.setattr(s,"TAIL_SHA",adopted[-1]["receipt"]["sha256"])
    stopped={k:refs[k] for k in ("preflight","process","exit")};stopped.update(failure=failure,user_stop=stop,post_stop_verification=post)
    locks={}
    for root in [Path(c.source["correction_root"]),*[Path(c.source["evaluation_roots"][m]) for m in s.MONTHS[:4]]]:
        lock=root/".lock";lock.write_bytes(b"0");locks[str(lock)]=s.sha(lock)
    originals={v["path"]:v["sha256"] for v in stopped.values()}
    for entry in adopted:
        for key in ("start","receipt","closure"): originals[entry[key]["path"]]=entry[key]["sha256"]
    originals.update(locks)
    snapshot_root=c.base/"snapshot";repo_snapshot=c.code/"snapshot"
    copies=[]
    for i,(p,h) in enumerate(originals.items()):
        for root in (snapshot_root,repo_snapshot):
            target=root/str(i)/Path(p).name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
            copies.append(dict(original=p,copy=str(target),sha256=h,size=Path(p).stat().st_size))
    prefix_inventory=s.read(c.pipeline/"receipts/07.json")["output_inventory"]
    snapshot=write(snapshot_root/"manifest.json",dict(version="OOF_USER_STOP_CONTINUATION_SNAPSHOT_V1",status="PASS_SNAPSHOT",copies=copies,original_files=originals,output_inventory=prefix_inventory,control_inventory={str(p):s.sha(p) for p in [c.pipeline/"request.json",c.pipeline/"contract.json",*[c.pipeline/f"{folder}/{i:02d}.json" for folder in ("starts","receipts") for i in range(8)]]},preserved_root_locks=locks))
    prefix_review=write(c.code/"prefix_review.json",dict(decision="CLEAR",runtime_authorized=False))
    operational=dict(version="OOF_USER_STOP_CONTINUATION_REQUEST_V1",status="REVIEWED_OOF_USER_STOP_CONTINUATION_REQUEST",runtime_authorized=True,original_request=source_ref,original_binding=runtime_ref,authorization={"path":str(c.code/"RESUMPTION_20261029.md"),"sha256":s.sha(c.code/"RESUMPTION_20261029.md")},snapshot_manifest=snapshot,independent_prefix_review=prefix_review,stopped_launch=stopped,expected_completed_phases=8,adopted_phases=adopted,tail_receipt_sha256=s.TAIL_SHA,source_admission_sha256=source_sha,remaining_phases=s.REMAINING,preserved_root_locks=locks)
    operational_ref=write(c.code/"continuation_request.json",operational)
    logs=c.base/"oof_pipeline_user_stop_continuation_launch_20261029_01";logs.mkdir()
    continuation_binding=dict(version="OOF_USER_STOP_CONTINUATION_BINDING_V1",status="PASS_OOF_USER_STOP_CONTINUATION_RUNTIME_BINDING",request=operational_ref,implementation_review=continuation_review,published_files={},allowed_read_roots=[],logs_root=str(logs),observer_root=str(c.base/"continuation_observer"),snapshot_root=str(snapshot_root),repository_snapshot_root=str(repo_snapshot),future_audit_root=str(c.base/"oof_economic_audit_user_stop_continuation_20261029_01"),future_audit_logs_root=str(c.base/"oof_economic_audit_user_stop_continuation_launch_20261029_01"))
    continuation_binding_ref=write(c.code/"continuation_binding.json",continuation_binding)
    command=proc["command"]+["--resume"]
    pre_new=write(logs/"preflight.json",dict(status="PASS_OOF_USER_STOP_CONTINUATION_PREFLIGHT_NOT_EXECUTED",executed=False,request_sha256=operational_ref["sha256"],runtime_binding_sha256=continuation_binding_ref["sha256"],implementation_review_sha256=continuation_review["sha256"],command=command,publication_commit="c"*40,source_admission_sha256=source_sha,baseline=dict(outputs=prefix_inventory,controls=s.read(snapshot["path"])["control_inventory"],locks=locks),cpu0_inheritance_test={"status":"PASS_FIRST_INSTRUCTION_CPU0_THREADS1"}))
    identity=dict(monitor_code_sha256=s.sha(c.code/s.CONTINUATION_CODE),request_sha256=operational_ref["sha256"],runtime_binding_sha256=continuation_binding_ref["sha256"],implementation_review_sha256=continuation_review["sha256"],publication_commit="c"*40,preflight_sha256=pre_new["sha256"])
    proc_new=write(logs/"process.json",dict(status="PROCESS_HANDLE_RETAINED",pid=790,creation_time=datetime(2026,10,29,1,tzinfo=timezone.utc).timestamp(),creation_time_source="GetProcessTimes_retained_Popen_handle",command=command,monitor_started_utc="2026-10-29T01:00:00+00:00",child_cpu_affinity=[0],**identity))
    exit_new=write(logs/"exit.json",dict(status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE",pid=790,creation_time=datetime(2026,10,29,1,tzinfo=timezone.utc).timestamp(),exit_code=0,exit_code_source="GetExitCodeProcess_retained_Popen_handle",process_receipt_sha256=proc_new["sha256"],observed_utc="2026-10-29T01:01:00+00:00",**identity))
    finish_new=write(logs/"completion.json",dict(status="COMPLETE_OOF_USER_STOP_CONTINUATION_PENDING_INDEPENDENT_AUDIT",exit_code=0,request_sha256=operational_ref["sha256"],runtime_binding_sha256=continuation_binding_ref["sha256"],implementation_review_sha256=continuation_review["sha256"],publication_commit="c"*40,stopped_launch=stopped,adopted_phases=adopted,snapshot_manifest=snapshot,source_admission_sha256=source_sha,process_files={r["path"]:r["sha256"] for r in (pre_new,proc_new,exit_new)},pipeline_closure=dict(original_validation=closed,new_phases=new,baseline_preserved=True),completed_utc="2026-10-29T01:02:00+00:00",auditor_executed=False,winner_selected=None,technical_ready=False,promotion_approved=False,retry=False))
    c.binding.update(status=s.BINDING_STATUS,source_admission_sha256=source_sha,output_root=continuation_binding["future_audit_root"],logs_root=continuation_binding["future_audit_logs_root"],upstream=dict(pipeline_request=source_ref,pipeline_binding=runtime_ref,continuation_request=operational_ref,continuation_binding=continuation_binding_ref,continuation_review=continuation_review,preflight=pre_new,process=proc_new,exit=exit_new,supervisor_completion=finish_new,pipeline_completion=refs["pipeline_completion"]))
    c.binding["allowed_read_roots"].extend(map(str,(observer,logs,snapshot_root)))
    evidence=s.Evidence(c.binding["allowed_read_roots"])
    files=s.review_files(evidence)
    c.review=write(c.code/s.REVIEW_NAME,dict(status=s.REVIEW_STATUS,decision="CLEAR",scope="IMPLEMENTATION_ONLY",runtime_authorized=False,files=files,cpu0_inheritance_test={"status":"PASS_FIRST_INSTRUCTION_CPU0_THREADS1"}))
    c.binding["implementation_review"]=c.review
    published={str(c.code/n):h for n,h in files.items()}
    published.update({str(c.code/s.AUDIT_REVIEW):s.AUDIT_REVIEW_SHA,str(c.code/s.PIPELINE_REVIEW):s.PIPELINE_REVIEW_SHA,c.review["path"]:c.review["sha256"],c.request_ref["path"]:c.request_ref["sha256"]})
    for name in ("pipeline_request","pipeline_binding","continuation_request","continuation_binding","continuation_review"):
        ref=c.binding["upstream"][name];published[ref["path"]]=ref["sha256"]
    c.binding["published_files"]=published;rewrite(c.binding_ref,c.binding)
    monkeypatch.setattr(s,"publication",lambda commit,files:c.publication_calls.append((commit,files)))
    c.s=s;c.operational=operational;c.operational_ref=operational_ref;c.new_logs=logs;c.closed=closed
    return c


def admit(c):
    return c.s.preflight(c.request_ref["path"],c.request_ref["sha256"],c.binding_ref["path"],c.binding_ref["sha256"],c.review["sha256"],"b"*40)


def test_full_two_chain_preflight_is_read_only(case):
    before={str(p):case.s.sha(p) for p in case.base.rglob("*") if p.is_file()}
    receipt=admit(case)
    assert receipt["executed"] is False
    assert receipt["status"]=="PASS_OOF_USER_STOP_AUDIT_PREFLIGHT_NOT_EXECUTED"
    assert before=={str(p):case.s.sha(p) for p in case.base.rglob("*") if p.is_file()}
    assert receipt["command"][2].endswith("audit_oof_calibrated_policy.py")
    assert "--resume" not in receipt["command"]


@pytest.mark.parametrize("key,field,value",[("exit","exit_code",15),("exit","pid",789),("exit","creation_time",123.5),("process","command",[]),("process","child_cpu_affinity",[1]),("supervisor_completion","adopted_phases",[]),("supervisor_completion","source_admission_sha256","f"*64),("supervisor_completion","auditor_executed",True)])
def test_rejects_incomplete_or_forged_continuation(case,key,field,value):
    ref=case.binding["upstream"][key];data=case.s.read(ref["path"]);data[field]=value;rewrite(ref,data);rewrite(case.binding_ref,case.binding)
    with pytest.raises(ValueError): admit(case)


@pytest.mark.parametrize("fault",["old_exit_zero","old_failure_other","missing_stop","source_map","adoption7","remaining","fake_tail","unknown_failure_permission"])
def test_rejects_inadmissible_stopped_authority(case,fault):
    if fault=="old_exit_zero":
        ref=case.operational["stopped_launch"]["exit"];v=case.s.read(ref["path"]);v["exit_code"]=0;rewrite(ref,v)
    elif fault=="old_failure_other":
        ref=case.operational["stopped_launch"]["failure"];v=case.s.read(ref["path"]);v["error"]="other";rewrite(ref,v)
    elif fault=="missing_stop": case.operational["stopped_launch"].pop("user_stop")
    elif fault=="source_map": case.operational["source_admission_sha256"]="e"*64
    elif fault=="adoption7": case.operational["adopted_phases"].pop()
    elif fault=="remaining": case.operational["remaining_phases"].pop()
    elif fault=="fake_tail": case.operational["tail_receipt_sha256"]="f"*64
    else: case.operational["ignore_failures"]=True
    rewrite(case.operational_ref,case.operational);rewrite(case.binding_ref,case.binding)
    with pytest.raises((ValueError,KeyError)): admit(case)


@pytest.mark.parametrize("where",["new_logs","pipeline","correction","replay","old_logs_unknown"])
def test_rejects_any_foreign_failure(case,where):
    roots=dict(new_logs=case.new_logs,pipeline=case.pipeline,correction=Path(case.source["correction_root"]),replay=Path(case.source["evaluation_roots"]["202606"]),old_logs_unknown=case.logs/"foreign")
    write(roots[where]/"failure.json",{"unrecognized":True})
    with pytest.raises(ValueError): admit(case)


@pytest.mark.parametrize("fault",["eleven","phase_orphan","mutated_start","snapshot_copy","lock"])
def test_rejects_missing_closure_or_preservation_drift(case,fault):
    if fault=="eleven": (case.pipeline/"receipts/11.json").unlink()
    if fault=="phase_orphan": write(case.pipeline/"starts/12.json",{})
    if fault=="mutated_start": (case.pipeline/"starts/00.json").write_bytes(b"{}")
    if fault=="snapshot_copy":
        snapshot=case.s.read(case.operational["snapshot_manifest"]["path"]);Path(snapshot["copies"][0]["copy"]).write_bytes(b"mutated")
    if fault=="lock": Path(next(iter(case.operational["preserved_root_locks"]))).write_bytes(b"changed")
    with pytest.raises((ValueError,FileNotFoundError)): admit(case)


@pytest.mark.parametrize("fault",["partial_scope","five_months","wrong_closure"])
def test_scientific_full_h1_contract_unchanged(case,fault):
    if fault=="partial_scope": case.request["scope"]="PARTIAL"
    if fault=="five_months": case.request["months"].pop()
    if fault=="wrong_closure": case.request["months"][0]["correction_completion_sha256"]="f"*64
    rewrite(case.request_ref,case.request);rewrite(case.binding_ref,case.binding)
    with pytest.raises(ValueError): admit(case)


def test_real_child_inherits_cpu0_and_one_thread_from_first_instruction(tmp_path):
    import psutil,subprocess,os
    s=importlib.import_module("launch_oof_economic_audit_user_stop_continuation_20261029")
    s.gate(s.observation())
    receipt=s.establish_cpu0()
    assert receipt["parent_cpu_affinity"]==[0]
    probe="import psutil,os,json; print(json.dumps([psutil.Process().cpu_affinity(),[os.environ[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')]]))"
    result=subprocess.run([sys.executable,"-c",probe],env=s.child_environment(),capture_output=True,check=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    assert json.loads(result.stdout)==[[0],["1","1","1"]]
