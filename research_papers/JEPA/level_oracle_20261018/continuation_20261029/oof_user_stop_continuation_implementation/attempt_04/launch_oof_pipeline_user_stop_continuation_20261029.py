"""Admit exactly eight stopped phases; explicitly continue the frozen wrapper once."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = Path("D:/GexResearchArtifacts/level_oracle_20261018")
WRAPPER = HERE / "run_oof_calibrated_pipeline_v2r1.py"
ORIGINAL = "launch_oof_pipeline_v2r1_20261024.py"
ORIGINAL_SHA = "e53084c70f99e4410814066a757e8f455dbb91bece8838fcd73417ce4614dce2"
WRAPPER_SHA = "87512b315d69c75c948c68a671939a9423f53abaa6cf2649d5faee7acd22b15a"
OPS_NAME = "launch_monthly_test_index_v2_audit_20261024.py"
OPS_SHA = "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"
HELPER_NAME = "launch_monthly_test_20261023.py"
HELPER_SHA = "3e77bda56dabd8287b04ae9a47b4dcd45d5967a01a31514e933cbb44b6f4c08d"
DESIGN = "OOF_USER_STOP_CONTINUATION_DESIGN_20261029.md"
DESIGN_SHA = "ae9d7466aa09f2c43e694fca86a5216d3222e0cff0042b035d7c8d057f54d109"
DESIGN_REVIEW = "OOF_USER_STOP_CONTINUATION_DESIGN_REVIEW_20261029.json"
DESIGN_REVIEW_SHA = "ad2ab016a45c769c3fb849a25e63173c0510f6577f7c5cd20beac867ebd414f6"
REVIEW = HERE / "OOF_USER_STOP_CONTINUATION_IMPLEMENTATION_REVIEW_20261029.json"
ORIGINAL_REQUEST = HERE / "OOF_PIPELINE_V2R1_RUNTIME_REQUEST_20261024_01.json"
ORIGINAL_REQUEST_SHA = "37f2018c7145d3b82cba2e34fbff9ae3008e33f32b004c5580e433157f38ef15"
ORIGINAL_BINDING = HERE / "OOF_PIPELINE_V2R1_LAUNCH_RUNTIME_BINDING_20261024_01.json"
ORIGINAL_BINDING_SHA = "9e4949227dfd8b0aa3e72a35271b081413dbd9dee482b79c98911ea25478813c"
SOURCE_SHA = "ec2f728baf2ab28adaaf3855847d74bf6354ac587d440afb83b50278e5ca3234"
TAIL_SHA = "e5dfb3505d3e8e621d91e6ef46dcffd89380a3aa62f13cbc1a37b3816747110e"
MONTHS = [f"2026{m:02d}" for m in range(1,7)]
REMAINING = [[m,s] for m in MONTHS[4:] for s in ("correction","replay")]
OPERATIONAL_LOCK = BASE / "oof_pipeline_launch.lock"
GLOBAL_LOCK = BASE / "oof_pipeline_runtime.lock"
REQUEST_KEYS = {"version","status","runtime_authorized","original_request","original_binding","authorization",
    "snapshot_manifest","independent_prefix_review","stopped_launch","expected_completed_phases","adopted_phases",
    "tail_receipt_sha256","source_admission_sha256","remaining_phases","preserved_root_locks"}
BINDING_KEYS = {"version","status","request","implementation_review","published_files","allowed_read_roots",
    "logs_root","observer_root","snapshot_root","repository_snapshot_root","future_audit_root","future_audit_logs_root"}
SNAPSHOT_KEYS = {"version","status","copies","original_files","output_inventory","control_inventory","preserved_root_locks"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    require(isinstance(value,str) and re.fullmatch(r"[0-9a-f]{64}",value),"External SHA256 required")
    return value


def verify(files):
    for path, expected in files.items():
        require(sha(path) == digest(expected),"Pinned bytes differ: "+str(path))


def ref(value):
    require(isinstance(value,dict) and set(value) == {"path","sha256"},"Exact path/hash reference required")
    digest(value["sha256"])
    return value


def operational_modules():
    pins = {HERE/ORIGINAL:ORIGINAL_SHA,WRAPPER:WRAPPER_SHA,HERE/OPS_NAME:OPS_SHA,HERE/HELPER_NAME:HELPER_SHA,
        HERE/"OOF_PIPELINE_V2R1_LAUNCH_RUNTIME_BINDING_20261024_01.json":"9e4949227dfd8b0aa3e72a35271b081413dbd9dee482b79c98911ea25478813c"}
    verify(pins)
    old = importlib.import_module(ORIGINAL.removesuffix(".py"))
    original_binding = read(HERE/"OOF_PIPELINE_V2R1_LAUNCH_RUNTIME_BINDING_20261024_01.json")
    original_review = original_binding["implementation_review"]
    ref(original_review)
    require(Path(original_review["path"])==old.REVIEW,"Original review location differs")
    verify({original_review["path"]:original_review["sha256"]})
    reviewed = read(original_review["path"])
    require(reviewed["status"]==old.REVIEW_STATUS and reviewed["decision"]=="CLEAR"
        and reviewed["scope"]=="IMPLEMENTATION_ONLY" and reviewed["runtime_authorized"] is False,"Frozen operational review required")
    # Verify the entire reviewed local import closure before importing operational helpers.
    files, _ = old.implementation_files()
    require(files==reviewed["files"],"Frozen operational import closure changed")
    pins.update({HERE/n:h for n,h in reviewed["files"].items()})
    verify(pins)
    ops = importlib.import_module(OPS_NAME.removesuffix(".py"))
    helper = importlib.import_module(HELPER_NAME.removesuffix(".py"))
    verify(pins)
    return old,ops,helper


def implementation_files():
    old,_,_ = operational_modules()
    result, dependencies = old.implementation_files()
    explicit = {ORIGINAL:ORIGINAL_SHA, WRAPPER.name:WRAPPER_SHA, DESIGN:DESIGN_SHA,
        DESIGN_REVIEW:DESIGN_REVIEW_SHA, ORIGINAL_REQUEST.name:ORIGINAL_REQUEST_SHA,
        ORIGINAL_BINDING.name:ORIGINAL_BINDING_SHA}
    original_review = read(ORIGINAL_BINDING)["implementation_review"]
    require(Path(original_review["path"]) == old.REVIEW,"Original supervisor review path differs")
    explicit[old.REVIEW.name] = original_review["sha256"]
    for name in (old.PIPELINE_REVIEW.name,old.AUDITOR_REVIEW.name,old.MONTHLY_PRODUCER_REVIEW.name,
                 old.MONTHLY_RUNTIME.name,old.MONTHLY_REVIEW.name,Path(__file__).name,
                 "test_launch_oof_pipeline_user_stop_continuation_20261029.py"):
        explicit[name] = sha(HERE/name)
    verify({HERE/n:h for n,h in explicit.items()})
    result.update(explicit)
    require(len(dependencies)==18,"Exact eighteen scientific dependencies required")
    return dict(sorted(result.items())),dependencies


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds()==0,"Aware UTC required")
    return parsed.timestamp()


def checked_member(spec, old, files):
    ref(spec)
    path = old.inspect_consumed_identity(spec["path"])
    require(str(path)==spec["path"],"Aliased compact declaration")
    verify({path:spec["sha256"]})
    value = read(path)
    verify({path:spec["sha256"]})
    require(str(path) not in files or files[str(path)]==spec["sha256"],"Conflicting compact SHA")
    files[str(path)] = spec["sha256"]
    return value


def command(request_path, request_sha):
    return [sys.executable,"-u",str(WRAPPER),"--request",str(request_path),"--request-sha256",request_sha,"--resume"]


def validate_stopped_launch(operational, scientific, original_binding):
    old,_,_ = operational_modules()
    refs = operational["stopped_launch"]
    require(set(refs)=={"preflight","process","exit","failure","user_stop","post_stop_verification"},"Exact stopped chain required")
    logs = old.absolute(original_binding["logs_root"])
    observer = BASE/"oof_pipeline_v2r1_observer_20261024_01"
    files = {}
    values = {}
    for name,spec in refs.items():
        expected = (observer if name in ("user_stop","post_stop_verification") else logs)/(name+".json")
        require(old.absolute(spec["path"])==expected,"Stopped receipt path differs")
        values[name] = checked_member(spec,old,files)
    pre,proc,exited,fail,stop,post = (values[n] for n in ("preflight","process","exit","failure","user_stop","post_stop_verification"))
    expected_command = command(Path(operational["original_request"]["path"]),operational["original_request"]["sha256"])[:-1]
    require(pre["status"]=="PASS_OOF_LAUNCH_PREFLIGHT_NOT_EXECUTED" and pre["executed"] is False
        and pre["command"]==expected_command and pre["request_sha256"]==operational["original_request"]["sha256"]
        and pre["runtime_binding_sha256"]==operational["original_binding"]["sha256"]
        and pre["source_admission_sha256"]==operational["source_admission_sha256"],"Original preflight differs")
    identity = dict(monitor_code_sha256=ORIGINAL_SHA,request_sha256=operational["original_request"]["sha256"],
        runtime_binding_sha256=operational["original_binding"]["sha256"],
        implementation_review_sha256=original_binding["implementation_review"]["sha256"],
        publication_commit=pre["publication_commit"],preflight_sha256=refs["preflight"]["sha256"])
    require(all(r.get(k)==v for r in (proc,exited) for k,v in identity.items()),"Original process authority differs")
    require(proc["status"]=="PROCESS_HANDLE_RETAINED" and proc["command"]==expected_command
        and proc["creation_time_source"]=="GetProcessTimes_retained_Popen_handle"
        and type(proc["pid"]) is int and proc["pid"]>0
        and type(proc["creation_time"]) in (float,int) and math.isfinite(proc["creation_time"]) and proc["creation_time"]>0,
        "Original retained process required")
    require(exited["status"]=="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE" and type(exited["exit_code"]) is int
        and exited["exit_code"]==15 and exited["exit_code_source"]=="GetExitCodeProcess_retained_Popen_handle"
        and type(exited["pid"]) is int and exited["pid"]==proc["pid"]
        and type(exited["creation_time"]) in (int,float) and exited["creation_time"]==proc["creation_time"]
        and exited["process_receipt_sha256"]==refs["process"]["sha256"],"Preserved retained exit15 required")
    require(fail["status"]=="FAILED_OR_INTERRUPTED_PRESERVED" and fail["retry"] is False
        and fail["error"]=="ValueError('OOF child must exit zero')" and not (logs/"completion.json").exists(),"Exact original failure required")
    require(stop["status"]=="STOPPED_BY_EXPLICIT_USER_REQUEST" and stop["automatic_resume"] is False
        and stop["artifacts_preserved"] is True and stop["remaining_known_research_processes"]==[],"User stop differs")
    matches = [p for p in stop["identities_before_stop"] if p["pid"]==proc["pid"]]
    require(len(matches)==1 and matches[0]["command"]==expected_command
        and type(matches[0]["creation"]) in (int,float) and math.isfinite(matches[0]["creation"])
        and abs(matches[0]["creation"]-proc["creation_time"])<=1e-6,"Stopped identity/tolerance differs")
    names = [f"{i:02d}.json" for i in range(8)]
    require(post["remaining_research_python_pids"]==[] and post["phase_receipts"]==names
        and post["phase_starts"]==names and post["pipeline_completion_exists"] is False
        and post["supervisor_exit_exists"] is True and post["supervisor_failure_exists"] is True,"Post-stop verification differs")
    end = timestamp(exited["observed_utc"])
    require(proc["creation_time"]<=timestamp(proc["monitor_started_utc"])<=end<=timestamp(fail["utc"])
        <=timestamp(stop["utc"])<=timestamp(post["utc"]),"Stopped chronology differs")
    return dict(creation_time=proc["creation_time"],observed_exit_time=end,files=files,pid=proc["pid"],
        logs_root=str(logs),observer_root=str(observer))


def validate_adopted_prefix(scientific, operational, admission, interval):
    old,_,_ = operational_modules()
    require(type(operational["expected_completed_phases"]) is int and operational["expected_completed_phases"]==8
        and operational["remaining_phases"]==REMAINING and len(operational["adopted_phases"])==8,"Exact prefix eight required")
    require(admission["map_sha256"]==operational["source_admission_sha256"],"Source admission differs")
    pipeline,correction = (old.absolute(scientific[n]) for n in ("pipeline_root","correction_root"))
    evaluations = {m:old.absolute(scientific["evaluation_roots"][m]) for m in MONTHS}
    roots = [correction,*evaluations.values()]
    controls,compact,sources,identities = {},{},{},{}
    request_sha = operational["original_request"]["sha256"]
    def member(path,expected=None,control=False):
        value = checked_member(dict(path=str(path),sha256=expected or sha(path)),old,compact)
        if control: controls[str(path)] = compact[str(path)]
        return value
    require(member(pipeline/"request.json",request_sha,True)==scientific,"Stored request differs")
    require(member(pipeline/"contract.json",control=True)==dict(version="OOF_PIPELINE_V2R1",request_sha256=request_sha,
        code=scientific["code"],correction_layout="SHARED_CUMULATIVE",source_admission_sha256=admission["map_sha256"]),"Contract differs")
    allowed = [HERE,old.absolute(scientific["monthly_root"]),old.absolute(scientific["session_root"]),*roots]
    exact = {str(old.absolute(operational["original_request"]["path"])),scientific["monthly_audit"]["path"],scientific["session_audit"]["path"]}
    def source_map(mapping):
        require(isinstance(mapping,dict),"Source map required")
        aliases = set()
        for name,expected in mapping.items():
            path = old.inspect_consumed_identity(name,identities)
            require(str(path)==name and old.path_key(path) not in aliases,"Aliased source path")
            aliases.add(old.path_key(path))
            item = admission["members"].get(old.path_key(path))
            if item is not None:
                require(item["path"]==name and item["sha256"]==expected,"Source differs from authority")
            if name not in exact and not any(path.is_relative_to(r) for r in allowed):
                require(item is not None,"Source outside admitted roots")
                if path.name in ("actions.parquet","labels.parquet"):
                    require(old.path_key(path) in admission["indexed_sidecars"],"External sidecar not indexed")
            require(name not in sources or sources[name]==expected,"Conflicting source SHA")
            verify({path:expected})
            sources[name] = expected
    adapter_names,replay_names,_ = old.dependency_sets()
    adapter = {n:scientific["code"][n] for n in adapter_names}
    replay = {n:scientific["code"][n] for n in replay_names}
    cumulative,prior,closures = {},None,{}
    last_time = interval["creation_time"]
    for index,(month,stage) in enumerate((m,s) for m in MONTHS[:4] for s in ("correction","replay")):
        adopted = operational["adopted_phases"][index]
        require(set(adopted)=={"phase","start","receipt","closure"} and adopted["phase"]==[month,stage],"Adopted phase differs")
        start_path,receipt_path = pipeline/f"starts/{index:02d}.json",pipeline/f"receipts/{index:02d}.json"
        closed_path = correction/f"{month}.complete.json" if stage=="correction" else evaluations[month]/"completion.json"
        for name,path in (("start",start_path),("receipt",receipt_path),("closure",closed_path)):
            ref(adopted[name])
            require(adopted[name]["path"]==str(path),"Adopted reference path differs")
        receipt = member(receipt_path,adopted["receipt"]["sha256"],True)
        start = member(start_path,adopted["start"]["sha256"],True)
        require(receipt["status"]=="COMPLETE_OOF_PIPELINE_PHASE" and receipt["request_sha256"]==request_sha
            and receipt["phase"]==[month,stage] and receipt["previous_receipt_sha256"]==prior
            and receipt["start_sha256"]==adopted["start"]["sha256"] and receipt["completion_sha256"]==adopted["closure"]["sha256"]
            and receipt["winner_selected"] is None and receipt["independent_audit_pending"] is True,"Phase receipt differs")
        require(start["request_sha256"]==request_sha and start["phase"]==[month,stage] and start["previous_receipt_sha256"]==prior,"Phase start differs")
        start_time = timestamp(start["started_at_utc"])
        require(last_time<=start_time<=interval["observed_exit_time"],"Phase outside original process interval")
        last_time = start_time
        observed = old.output_mapping(receipt["output_inventory"],roots)
        require(all(observed.get(p)==h for p,h in cumulative.items()),"Earlier output omitted or changed")
        closed = member(closed_path,receipt["completion_sha256"])
        require(observed.get(str(closed_path))==receipt["completion_sha256"],"Closure missing from output inventory")
        if stage=="correction":
            require(closed["status"]=="COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS" and closed["target_month"]==month
                and closed["monthly_audit_sha256"]==scientific["monthly_audit"]["sha256"] and closed["dependencies"]==adapter
                and closed["target_labels_read"] is False and closed["base_models_refitted"] is False
                and closed["winner_selected"] is None and closed["development_seen"] is True,"Correction closure differs")
            inputs_path = correction/f"{month}.inputs.json"
            require(observed.get(str(inputs_path))==closed["inputs_sha256"],"Correction input pin differs")
            inputs = member(inputs_path,closed["inputs_sha256"])
            source_map(inputs["files"])
            source_map(inputs["run_authorities"])
            require(inputs["dependencies"]==adapter and inputs["monthly_audit_sha256"]==scientific["monthly_audit"]["sha256"],"Correction input authority differs")
            impl_path,contract_path = correction/"implementation.json",correction/f"{month}.run_contract.json"
            impl = member(impl_path,inputs["run_authorities"][str(impl_path)])
            contract = member(contract_path,inputs["run_authorities"][str(contract_path)])
            require(impl==dict(dependencies=adapter,monthly_root=scientific["monthly_root"],session_root=scientific["session_root"],
                version="PREQUENTIAL_MAXIMUM_OFFSET_V1",calibrator_window="EXPANDING_FROM_202501",threshold=0,winner_selected=None)
                and contract==dict(target_month=month,monthly_audit_sha256=scientific["monthly_audit"]["sha256"],implementation_sha256=compact[str(impl_path)]),"Correction contract differs")
            require(all(Path(p).is_relative_to(correction) for p in set(observed)-set(cumulative)),"Correction writes another root")
            require(set(closed["procedures"])=={"static","expanding","rolling12"},"Correction procedures differ")
            generated = {str(p) for p in (closed_path,inputs_path,impl_path,contract_path)}
            for mode,part in closed["procedures"].items():
                calibration = correction/mode/month/"calibration.json"
                require(observed.get(str(calibration))==part["calibration_sha256"],"Calibration output pin differs")
                generated.add(str(calibration))
                for group in ("history_calendar","target_calendar"):
                    for row in part[group]:
                        require(row["procedure"]==mode and row["ticker"] in ("QQQ","SPY","SPXW")
                            and re.fullmatch(r"[0-9]{8}",row["day"]) and row["source_status"] in ("COMPLETE","MISSING_SOURCE"),"Calendar metadata differs")
                        if row["source_status"]=="MISSING_SOURCE": continue
                        selection = correction/mode/"selections"/row["ticker"]/(row["day"]+".json")
                        require(observed.get(str(selection))==row["selection_sha256"],"Selection byte pin differs")
                        generated.add(str(selection))
                        if group=="history_calendar":
                            generated.add(str(correction/mode/"realized"/row["ticker"]/(row["day"]+".json")))
                        else:
                            score = correction/mode/month/"scores"/row["ticker"]/(row["day"]+".json")
                            require(row["score_path"]==str(score) and row["selection_path"]==str(selection)
                                and observed.get(str(score))==row["score_sha256"],"Score byte pin differs")
                            generated.add(str(score))
            require(set(observed)==set(cumulative)|generated,"Correction output membership differs")
            closures[month] = dict(correction_completion_sha256=receipt["completion_sha256"])
        else:
            root = evaluations[month]
            require(closed["status"]=="COMPLETE_FIXED_OOF_POLICY_MONTH" and closed["target_month"]==month
                and closed["winner_selected"] is None and closed["dependencies"]==replay,"Replay closure differs")
            source_map(closed["files"])
            source_map(closed["monthly_files"])
            correction_sha = closures[month]["correction_completion_sha256"]
            require(closed["files"].get(str(correction/f"{month}.complete.json"))==correction_sha,"Replay correction link differs")
            contract_path = root/"run_contract.json"
            require(member(contract_path,closed["files"][str(contract_path)])==dict(version="OOF_POLICY_REPLAY_V1",dependencies=replay,
                monthly_audit_sha256=scientific["monthly_audit"]["sha256"],correction_completion_sha256=correction_sha,
                target_month=month,threshold=0,winner_selected=None),"Replay contract differs")
            for name in ("run_contract.json","summary.json","all_scores_and_controls.json"):
                require(str(root/name) in observed and observed[str(root/name)]==closed["files"].get(str(root/name)),"Replay output pin differs")
            local = {p:h for p,h in closed["files"].items() if Path(p).is_relative_to(root)}
            require(all(observed.get(p)==h for p,h in local.items())
                and set(observed)-set(cumulative)=={str(closed_path),*local},"Replay output membership differs")
            closures[month]["evaluation_completion_sha256"] = receipt["completion_sha256"]
        require(type(receipt["new_output_bytes"]) is int and type(receipt["cumulative_output_bytes"]) is int
            and receipt["new_output_bytes"]==sum(Path(p).stat().st_size for p in set(observed)-set(cumulative))
            and receipt["cumulative_output_bytes"]==sum(Path(p).stat().st_size for p in observed),"Phase byte accounting differs")
        cumulative,prior = observed,adopted["receipt"]["sha256"]
    require(prior==operational["tail_receipt_sha256"],"Adopted tail differs")
    require(old.tree_files(pipeline)==set(controls),"Unexpected pipeline control artifact")
    require(all(not evaluations[m].exists() for m in MONTHS[4:]),"Pending replay root exists")
    require(set().union(*(old.tree_files(r,True) for r in roots))==set(cumulative),"Output inventory membership differs")
    locks = operational["preserved_root_locks"]
    require(set(locks)=={str(r/".lock") for r in [correction,*[evaluations[m] for m in MONTHS[:4]]]},"Exact five preserved locks required")
    for path,expected in {**cumulative,**locks,**compact}.items():
        old.inspect_consumed_identity(path,identities)
        verify({path:expected})
    return dict(completed_phases=8,tail_receipt_sha256=prior,controls=controls,compact=compact,sources=sources,
        outputs=cumulative,locks=locks,closures=closures)


def destinations(scientific,binding):
    old,_,_ = operational_modules()
    require(set(scientific["evaluation_roots"])==set(MONTHS),"Six original replay roots required")
    roots = [old.absolute(scientific[n]) for n in ("pipeline_root","correction_root")]
    roots += [old.absolute(scientific["evaluation_roots"][m]) for m in MONTHS]
    require(all(p.is_dir() for p in roots[:6]) and all(not p.exists() for p in roots[6:]),"Exact existing prefix and absent pending roots required")
    expected = dict(logs_root=BASE/"oof_pipeline_user_stop_continuation_launch_20261029_01",
        observer_root=BASE/"oof_pipeline_user_stop_continuation_observer_20261029_01",
        snapshot_root=BASE/"oof_user_stop_continuation_evidence_20261029_01",
        repository_snapshot_root=HERE/"continuation_20261029/oof_user_stop_continuation_snapshot",
        future_audit_root=BASE/"oof_economic_audit_user_stop_continuation_20261029_01",
        future_audit_logs_root=BASE/"oof_economic_audit_user_stop_continuation_launch_20261029_01")
    for name,path in expected.items():
        require(old.absolute(binding[name])==path,"Operational destination differs: "+name)
        if name in ("snapshot_root","repository_snapshot_root"):
            require(path.is_dir(),"Sealed snapshot root required")
        elif name!="observer_root":
            require(not path.exists(),"Fresh operational destination required")
    operational = [expected[n] for n in ("logs_root","observer_root","snapshot_root","future_audit_root","future_audit_logs_root")]
    protected = [HERE,old.absolute(scientific["monthly_root"]),old.absolute(scientific["session_root"]),
        old.MONTHLY_OUTPUT,old.MONTHLY_LOGS,BASE/"engine_v1",BASE/"features_v1",GLOBAL_LOCK,OPERATIONAL_LOCK,
        *[old.absolute(p) for p in binding["allowed_read_roots"] if not Path(p).is_relative_to(expected["snapshot_root"])
          and not Path(p).is_relative_to(expected["repository_snapshot_root"])]]
    all_roots = roots+operational
    require(all(old.disjoint(a,b) for i,a in enumerate(all_roots) for b in all_roots[i+1:]),"Destination overlap")
    # Existing source/evidence read roots may name the exact adopted output trees.
    writable = [*roots[:2],*roots[6:],expected["logs_root"],expected["observer_root"]]
    for target in writable:
        require(all(old.disjoint(target,p) for p in protected if p!=target and p not in roots),"Writable destination overlaps protected source")
    return dict(roots=[str(p) for p in roots],**{n:str(p) for n,p in expected.items()})


def validate_snapshot(operational,binding,baseline,stopped):
    old,_,_ = operational_modules()
    files = {}
    manifest = checked_member(operational["snapshot_manifest"],old,files)
    require(Path(operational["snapshot_manifest"]["path"])==Path(binding["repository_snapshot_root"])/"snapshot_manifest.json",
        "Repository snapshot manifest authority required")
    files[str(Path(binding["snapshot_root"])/"snapshot_manifest.json")] = operational["snapshot_manifest"]["sha256"]
    require(set(manifest)==SNAPSHOT_KEYS and manifest["version"]=="OOF_USER_STOP_CONTINUATION_SNAPSHOT_V1"
        and manifest["status"]=="SEALED_METADATA_AND_HASHES_ONLY","Exact sealed snapshot schema required")
    require(manifest["output_inventory"]==baseline["outputs"] and manifest["control_inventory"]==baseline["controls"]
        and manifest["preserved_root_locks"]==baseline["locks"],"Snapshot baseline differs")
    originals = {**baseline["compact"],**baseline["locks"],
        operational["original_request"]["path"]:operational["original_request"]["sha256"],
        operational["original_binding"]["path"]:operational["original_binding"]["sha256"]}
    for directory in (stopped["logs_root"],stopped["observer_root"]):
        for path in old.tree_files(Path(directory)):
            require(path in manifest["original_files"],"Original log/observer omitted from snapshot")
            originals[path] = manifest["original_files"][path]
    require(manifest["original_files"]==originals,"Exact original snapshot membership required")
    local,repository = old.absolute(binding["snapshot_root"]),old.absolute(binding["repository_snapshot_root"])
    destinations_seen,set_by_original = set(),{p:set() for p in originals}
    for pair in manifest["copies"]:
        require(set(pair)=={"original","copy","sha256","size"} and pair["original"] in originals
            and pair["sha256"]==originals[pair["original"]] and type(pair["size"]) is int,"Snapshot pair differs")
        destination = old.inspect_consumed_identity(pair["copy"])
        require(str(destination)==pair["copy"] and pair["copy"] not in destinations_seen,"Duplicate snapshot destination")
        group = "local" if destination.is_relative_to(local) else "repository" if destination.is_relative_to(repository) else None
        require(group is not None and group not in set_by_original[pair["original"]],"Snapshot copy outside exact roots/duplicate group")
        require(Path(pair["original"]).stat().st_size==pair["size"]==destination.stat().st_size,"Snapshot copy size differs")
        set_by_original[pair["original"]].add(group)
        destinations_seen.add(pair["copy"])
        files[pair["copy"]] = pair["sha256"]
    require(all(groups=={"local","repository"} for groups in set_by_original.values()),"Both snapshot copies required")
    files.update(originals)
    for path in files: old.inspect_consumed_identity(path)
    verify(files)
    return files


def no_competitors():
    import psutil
    names = {WRAPPER.name,ORIGINAL,Path(__file__).name,"launch_oof_pipeline_v2_20261024.py","run_oof_calibrated_pipeline.py",
        "run_oof_calibrated_pipeline_v2.py","launch_oof_economic_audit_v2r1_20261024.py","audit_oof_calibrated_policy.py"}
    observed = []
    for process in psutil.process_iter(["pid","name","cmdline","create_time"]):
        if process.pid==os.getpid(): continue
        try:
            args = process.info["cmdline"] or []
            if any(Path(arg).name in names for arg in args):
                observed.append(dict(pid=process.pid,command=args,creation_time=process.info["create_time"]))
        except (psutil.NoSuchProcess,psutil.ZombieProcess):
            continue
    require(not observed,"Competing research process exists")
    return dict(observed_utc=utc(),competing_processes=observed)


def validate_authority(request_path,request_sha,binding_path,binding_sha,review_sha,commit):
    verify({str(request_path):digest(request_sha),str(binding_path):digest(binding_sha),str(REVIEW):digest(review_sha)})
    old,ops,helper = operational_modules()
    request_path,binding_path = old.absolute(str(request_path)),old.absolute(str(binding_path))
    pins = {str(request_path):digest(request_sha),str(binding_path):digest(binding_sha),str(REVIEW):digest(review_sha)}
    verify(pins)
    request,binding,review = read(request_path),read(binding_path),read(REVIEW)
    require(set(request)==REQUEST_KEYS and request["version"]=="OOF_USER_STOP_CONTINUATION_REQUEST_V1"
        and request["status"]=="REVIEWED_OOF_USER_STOP_CONTINUATION_REQUEST" and request["runtime_authorized"] is True,"Exact continuation request schema required")
    require(set(binding)==BINDING_KEYS and binding["version"]=="OOF_USER_STOP_CONTINUATION_BINDING_V1"
        and binding["status"]=="PASS_OOF_USER_STOP_CONTINUATION_RUNTIME_BINDING"
        and binding["request"]==dict(path=str(request_path),sha256=request_sha)
        and binding["implementation_review"]==dict(path=str(REVIEW),sha256=review_sha),"Exact continuation binding required")
    require(request["original_request"]==dict(path=str(ORIGINAL_REQUEST),sha256=ORIGINAL_REQUEST_SHA)
        and request["original_binding"]==dict(path=str(ORIGINAL_BINDING),sha256=ORIGINAL_BINDING_SHA)
        and request["source_admission_sha256"]==SOURCE_SHA and request["tail_receipt_sha256"]==TAIL_SHA,"Frozen original authority differs")
    files,dependencies = implementation_files()
    require(review.get("status")=="PASS_OOF_USER_STOP_CONTINUATION_IMPLEMENTATION_REVIEW" and review.get("decision")=="CLEAR"
        and review.get("scope")=="IMPLEMENTATION_ONLY" and review.get("runtime_authorized") is False
        and review.get("files")==files,"Exact implementation review required")
    require(review.get("cpu0_inheritance_test",{}).get("status")=="PASS_FIRST_INSTRUCTION_CPU0_THREADS1", "Reviewed CPU inheritance evidence required")
    for name in ("authorization","snapshot_manifest","independent_prefix_review"):
        ref(request[name]); pins[request[name]["path"]] = request[name]["sha256"]
    require(Path(request["authorization"]["path"])==HERE/"RESUMPTION_20261029.md","Current authorization required")
    verify(pins)
    scientific,original_binding = read(ORIGINAL_REQUEST),read(ORIGINAL_BINDING)
    expected_reads = set(original_binding["allowed_read_roots"]) | {binding["snapshot_root"],binding["repository_snapshot_root"]}
    require(len(binding["allowed_read_roots"])==len(expected_reads) and set(binding["allowed_read_roots"])==expected_reads,
        "Exact original read roots plus two snapshot roots required")
    require(scientific["code"]==dependencies and scientific["months"]==MONTHS
        and old.absolute(scientific["coordination_lock"])==GLOBAL_LOCK
        and old.absolute(scientific["monthly_root"])==old.MONTHLY_ROOT
        and old.absolute(scientific["session_root"])==old.SESSION_ROOT,"Frozen scientific request differs")
    return old,ops,helper,request,binding,review,scientific,original_binding,pins,files


def preflight(request_path,request_sha,binding_path,binding_sha,review_sha,commit):
    require(os.name=="nt" and sys.flags.optimize==0 and not os.environ.get("PYTHONOPTIMIZE"),"Unoptimized Windows required")
    old,ops,_,request,binding,review,scientific,original_binding,pins,implementation = validate_authority(
        request_path,request_sha,binding_path,binding_sha,review_sha,commit)
    roots = destinations(scientific,binding)
    ops.gate(ops.observation())
    evidence = ops.Evidence(binding["allowed_read_roots"])
    old.upstream(scientific,original_binding,evidence,ops)
    admission = old.request_admission(scientific)
    require(admission["map_sha256"]==SOURCE_SHA,"Original source map differs")
    old.protect_transitive_outputs([Path(p) for p in roots["roots"]]+[Path(roots["logs_root"]),Path(roots["observer_root"])],admission)
    stopped = validate_stopped_launch(request,scientific,original_binding)
    baseline = validate_adopted_prefix(scientific,request,admission,stopped)
    snapshot = validate_snapshot(request,binding,baseline,stopped)
    independent = checked_member(request["independent_prefix_review"],old,pins)
    require(Path(request["independent_prefix_review"]["path"])==HERE/"OOF_INTERRUPTION_INDEPENDENT_REVIEW_20261029.json",
        "Independent review path differs")
    require(independent.get("status")=="PASS_STOPPED_PREFIX_METADATA_AND_HASHES_ONLY"
        and independent.get("schema")=="INDEPENDENT_METADATA_HASH_REVIEW_V1"
        and independent.get("verdict")=="EIGHT_CLOSURES_INTEGRITY_VERIFIED_NOT_YET_ADOPTED"
        and independent.get("adoption_authorized_by_this_review") is False
        and independent.get("economics_interpreted") is False and independent.get("audit_full_h1_performed") is False
        and independent.get("failed_checks")==0 and independent.get("request_sha256")==ORIGINAL_REQUEST_SHA
        and independent.get("original_runtime_binding_sha256")==ORIGINAL_BINDING_SHA
        and independent.get("final_receipt_sha256")==TAIL_SHA and independent.get("source_admission_sha256")==SOURCE_SHA
        and independent.get("original_exit_code")==15 and independent.get("original_failure_preserved") is True
        and independent.get("closures")==baseline["closures"] and len(independent.get("reviewed_phases",[]))==8,
        "Independent prefix metadata review differs")
    for index,(reviewed,adopted) in enumerate(zip(independent["reviewed_phases"],request["adopted_phases"])):
        require(reviewed["index"]==index and [reviewed["month"],reviewed["stage"]]==adopted["phase"]
            and reviewed["start_sha256"]==adopted["start"]["sha256"] and reviewed["receipt_sha256"]==adopted["receipt"]["sha256"]
            and reviewed["completion_sha256"]==adopted["closure"]["sha256"],"Independent phase differs")
    source_ref = ref(independent["review_result_source"])
    pins[source_ref["path"]] = source_ref["sha256"]
    pins[str(HERE/"OOF_INTERRUPTION_INDEPENDENT_REVIEW_20261029.md")] = "fed60704c8520006f0ca3637a38d2dc970273cf4107f9473190190799202bf4a"
    verify(pins)
    published = {str(HERE/n):h for n,h in implementation.items()}
    published.update({p:h for p,h in pins.items() if p!=str(old.absolute(str(binding_path))) and Path(p).is_relative_to(REPO)})
    published.update({p:h for p,h in snapshot.items() if Path(p).is_relative_to(REPO)})
    require(binding["published_files"]==published,"Exact publication membership differs")
    publication_files = {**published,str(old.absolute(str(binding_path))):binding_sha}
    old.publication(commit,publication_files)
    all_files = {**pins,**publication_files,**evidence.files,**snapshot,**stopped["files"],**baseline["sources"],**baseline["outputs"],**baseline["locks"],**baseline["compact"]}
    verify(all_files)
    observed = no_competitors()
    return dict(status="PASS_OOF_USER_STOP_CONTINUATION_PREFLIGHT_NOT_EXECUTED",executed=False,retry=False,
        request_path=str(old.absolute(str(request_path))),request_sha256=request_sha,runtime_binding=str(old.absolute(str(binding_path))),
        runtime_binding_sha256=binding_sha,implementation_review_sha256=review_sha,publication_commit=commit,
        publication_files=publication_files,files=all_files,logs_root=roots["logs_root"],destinations=roots,
        command=command(ORIGINAL_REQUEST,ORIGINAL_REQUEST_SHA),source_admission_sha256=admission["map_sha256"],
        source_admission_summary=admission["summary"],baseline=baseline,stopped_launch=stopped,
        process_observation=observed,cpu0_inheritance_test=review["cpu0_inheritance_test"])


def establish_cpu0():
    import psutil
    process = psutil.Process()
    previous = process.cpu_affinity()
    process.cpu_affinity([0])
    require(process.cpu_affinity()==[0],"CPU0 affinity must be imposed before Popen")
    return dict(parent_pid=os.getpid(),parent_cpu_affinity=[0],previous_parent_cpu_affinity=previous,
        mechanism="Windows_child_inherits_parent_affinity_at_CreateProcess",verified_utc=utc())


def child_environment():
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",PYTHONUTF8="1")
    return env


def monitor(child,receipt,helper,ops,preflight_sha):
    logs = Path(receipt["logs_root"])
    ended = False
    try:
        retained = helper.RetainedProcess(child)
        created = retained.creation_time()
        import psutil
        errors,valid,affinity = [],True,None
        child_process = None
        try:
            child_process = psutil.Process(child.pid)
            require(abs(child_process.create_time()-created)<=1e-6,"Child retained identity differs")
            affinity = child_process.cpu_affinity()
            require(affinity==[0],"Child did not inherit CPU0")
        except (psutil.Error,OSError,ValueError) as exc:
            errors.append(repr(exc))
            valid = False
        authority = dict(monitor_code_sha256=receipt["files"][str(Path(__file__).resolve())],
            request_sha256=receipt["request_sha256"],runtime_binding_sha256=receipt["runtime_binding_sha256"],
            implementation_review_sha256=receipt["implementation_review_sha256"],publication_commit=receipt["publication_commit"],preflight_sha256=preflight_sha)
        helper.publish(logs,"process.json",dict(status="PROCESS_HANDLE_RETAINED",pid=child.pid,creation_time=created,
            creation_time_source="GetProcessTimes_retained_Popen_handle",command=receipt["command"],monitor_started_utc=utc(),
            child_cpu_affinity=affinity,initial_child_affinity_verified=valid,**authority))
        process_sha = sha(logs/"process.json")
        start = time.monotonic()
        minimum,samples = None,0
        while True:
            code = retained.wait_exit()
            if code is not None:
                ended = True
                break
            try:
                if child_process is not None:
                    require(child_process.cpu_affinity()==[0],"Child CPU affinity drift")
            except (psutil.NoSuchProcess,psutil.ZombieProcess) as exc:
                errors.append(repr(exc))
            except (psutil.Error,OSError,ValueError) as exc:
                errors.append(repr(exc))
                valid = False
            try:
                resources = ops.observation()
                minimum = resources if minimum is None else {k:min(v,minimum[k]) for k,v in resources.items()}
                samples += 1
            except (OSError,ValueError) as exc:
                errors.append(repr(exc))
        helper.publish(logs,"exit.json",dict(status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE",pid=child.pid,
            creation_time=created,exit_code=code,exit_code_source="GetExitCodeProcess_retained_Popen_handle",observed_utc=utc(),
            process_receipt_sha256=process_sha,monitor_seconds=time.monotonic()-start,sample_count=samples,
            minimum_free_observed=minimum,monitor_errors=errors,monitor_valid=valid,retry=False,**authority))
        return dict(exit_code=code,monitor_valid=valid,creation_time=created,observed_exit_time=timestamp(read(logs/"exit.json")["observed_utc"]),
            files={str(logs/"process.json"):process_sha,str(logs/"exit.json"):sha(logs/"exit.json"),str(logs/"preflight.json"):preflight_sha})
    finally:
        if not ended: helper.drain_child(child)


def validate_final(scientific,operational,receipt,monitored):
    old,_,_ = operational_modules()
    require(type(monitored["exit_code"]) is int and monitored["exit_code"]==0 and monitored["monitor_valid"] is True,
        "Continuation requires retained exit zero and valid monitor")
    verify(monitored["files"])
    closed = old.validate_pipeline(scientific,operational["original_request"]["sha256"])
    require(closed["source_admission_sha256"]==receipt["source_admission_sha256"],"Source admission changed during child")
    baseline = receipt["baseline"]
    pipeline = Path(scientific["pipeline_root"])
    final = read(pipeline/"receipts/11.json")["output_inventory"]
    require(all(final.get(p)==h for p,h in baseline["outputs"].items()),"Baseline not a final inventory subset")
    verify(receipt["files"])
    last = monitored["creation_time"]
    new_refs = []
    for i,phase in enumerate(REMAINING,start=8):
        path = pipeline/f"starts/{i:02d}.json"
        start = read(path)
        when = timestamp(start["started_at_utc"])
        require(start["phase"]==phase and last<=when<=monitored["observed_exit_time"],"New phase outside continuation process interval")
        last = when
        new_refs.append(dict(phase=phase,start=dict(path=str(path),sha256=sha(path)),
            receipt=dict(path=str(pipeline/f"receipts/{i:02d}.json"),sha256=sha(pipeline/f"receipts/{i:02d}.json"))))
    return dict(original_validation=closed,new_phases=new_refs,baseline_preserved=True)


def launch(receipt):
    require(receipt.get("status")=="PASS_OOF_USER_STOP_CONTINUATION_PREFLIGHT_NOT_EXECUTED" and receipt.get("executed") is False,"Continuation preflight required")
    verify(receipt["files"])
    old,ops,helper = operational_modules()
    operational,binding = read(receipt["request_path"]),read(receipt["runtime_binding"])
    scientific = read(operational["original_request"]["path"])
    require(receipt["command"]==command(Path(operational["original_request"]["path"]),operational["original_request"]["sha256"]),"Fixed resume command differs")
    with helper.overlay.os_lock(OPERATIONAL_LOCK,create=True):
        fresh = preflight(receipt["request_path"],receipt["request_sha256"],receipt["runtime_binding"],receipt["runtime_binding_sha256"],
            receipt["implementation_review_sha256"],receipt["publication_commit"])
        require(all(fresh[k]==receipt[k] for k in ("files","baseline","destinations","command","publication_files","source_admission_sha256")),"Authority changed before continuation")
        with helper.overlay.os_lock(GLOBAL_LOCK,create=False):
            pass
        logs = Path(receipt["logs_root"])
        destinations(scientific,binding)
        logs.mkdir(parents=True,exist_ok=False)
        try:
            helper.publish(logs,"preflight.json",receipt)
            preflight_sha = sha(logs/"preflight.json")
            with (logs/"stdout.log").open("xb") as stdout,(logs/"stderr.log").open("xb") as stderr:
                affinity = establish_cpu0()
                verify(receipt["files"])
                old.publication(receipt["publication_commit"],receipt["publication_files"])
                observation = no_competitors()
                resources = ops.observation()
                ops.gate(resources)
                helper.publish(logs,"admission.json",dict(**resources,minimum_free_bytes=2_000_000_000,utc=utc(),
                    **affinity,cpu0_inheritance_test=receipt["cpu0_inheritance_test"],process_observation=observation))
                # Recheck affinity immediately at the creation boundary; child never starts on another CPU.
                import psutil
                require(psutil.Process().cpu_affinity()==[0],"Parent CPU affinity changed before Popen")
                child = subprocess.Popen(receipt["command"],cwd=REPO,env=child_environment(),stdin=subprocess.DEVNULL,
                    stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    monitored = monitor(child,receipt,helper,ops,preflight_sha)
                finally:
                    helper.drain_child(child)
            final = validate_final(scientific,operational,receipt,monitored)
            verify(monitored["files"])
            verify(receipt["files"])
            helper.publish(logs,"completion.json",dict(status="COMPLETE_OOF_USER_STOP_CONTINUATION_PENDING_INDEPENDENT_AUDIT",
                exit_code=0,request_sha256=receipt["request_sha256"],runtime_binding_sha256=receipt["runtime_binding_sha256"],
                implementation_review_sha256=receipt["implementation_review_sha256"],publication_commit=receipt["publication_commit"],
                stopped_launch=operational["stopped_launch"],adopted_phases=operational["adopted_phases"],
                snapshot_manifest=operational["snapshot_manifest"],source_admission_sha256=receipt["source_admission_sha256"],
                process_files=monitored["files"],pipeline_closure=final,completed_utc=utc(),auditor_executed=False,
                winner_selected=None,technical_ready=False,promotion_approved=False,retry=False))
            return 0
        except BaseException as exc:
            helper.publish(logs,"failure.json",dict(status="FAILED_OR_INTERRUPTED_PRESERVED",error=repr(exc),utc=utc(),retry=False))
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request",type=Path,required=True)
    parser.add_argument("--request-sha256",required=True)
    parser.add_argument("--runtime-binding",type=Path,required=True)
    parser.add_argument("--runtime-binding-sha256",required=True)
    parser.add_argument("--implementation-review-sha256",required=True)
    parser.add_argument("--publication-commit",required=True)
    parser.add_argument("--execute-reviewed-continuation",action="store_true")
    args = parser.parse_args()
    receipt = preflight(args.request,args.request_sha256,args.runtime_binding,args.runtime_binding_sha256,
        args.implementation_review_sha256,args.publication_commit)
    if args.execute_reviewed_continuation: return launch(receipt)
    print(json.dumps(receipt,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
