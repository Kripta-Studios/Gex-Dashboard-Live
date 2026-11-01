from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import prepare_oof_continuation_audit_package_20261101 as p


H = "1" * 64


def fixture(tmp_path):
    pipeline = tmp_path / "pipeline"
    correction = tmp_path / "correction"
    evaluations = {m: str(tmp_path / ("eval_" + m)) for m in p.MONTHS}
    source = {
        "version": "OOF_PIPELINE_RUNTIME_REQUEST_V2R1", "months": p.MONTHS,
        "pipeline_root": str(pipeline), "correction_root": str(correction),
        "evaluation_roots": evaluations, "monthly_root": "M", "session_root": "S",
        "monthly_audit": {"path": "MA", "sha256": H}, "session_audit": {"path": "SA", "sha256": H},
        "code": {name: H for name in set(p.REPLAY_NAMES)},
    }
    compact, documents, previous, pairs = {}, {}, None, {}
    def add(path, value):
        raw = (json.dumps(value, sort_keys=True) + "\n").encode()
        compact[str(path)] = hashlib.sha256(raw).hexdigest()
        documents[str(path)] = value
    add(pipeline / "request.json", source)
    add(pipeline / "contract.json", {"fixture": True})
    for i, (month, stage) in enumerate((m, s) for m in p.MONTHS for s in ("correction", "replay")):
        start_path, receipt_path = pipeline / f"starts/{i:02d}.json", pipeline / f"receipts/{i:02d}.json"
        start = {"phase": [month, stage], "previous_receipt_sha256": previous, "request_sha256": p.SOURCE_REQUEST_SHA}
        add(start_path, start)
        target = correction / f"{month}.complete.json" if stage == "correction" else Path(evaluations[month]) / "completion.json"
        names = p.ADAPTER_NAMES if stage == "correction" else p.REPLAY_NAMES
        closed = {"target_month": month, "winner_selected": None, "dependencies": {name: H for name in names}}
        if stage == "correction":
            closed.update(status="COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS", monthly_audit_sha256=H, target_labels_read=False, base_models_refitted=False, development_seen=True)
        else:
            closed["status"] = "COMPLETE_FIXED_OOF_POLICY_MONTH"
        add(target, closed)
        receipt = {"phase": [month, stage], "previous_receipt_sha256": previous, "request_sha256": p.SOURCE_REQUEST_SHA, "status": "COMPLETE_OOF_PIPELINE_PHASE", "start_sha256": compact[str(start_path)], "completion_sha256": compact[str(target)], "winner_selected": None, "independent_audit_pending": True}
        add(receipt_path, receipt)
        previous = compact[str(receipt_path)]
        if stage == "correction": pairs[month] = {"correction_completion_sha256": compact[str(target)]}
        else:
            pairs[month]["evaluation_completion_sha256"] = compact[str(target)]
            add(Path(evaluations[month]) / "run_contract.json", {"version": "OOF_POLICY_REPLAY_V1", "dependencies": closed["dependencies"], "monthly_audit_sha256": H, "correction_completion_sha256": pairs[month]["correction_completion_sha256"], "target_month": month, "threshold": 0, "winner_selected": None})
    completion = {"status": "PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT", "request_sha256": p.SOURCE_REQUEST_SHA, "last_receipt_sha256": previous, "months": pairs, "winner_selected": None, "technical_ready": False, "promotion_approved": False, "auditor_executed": False}
    add(pipeline / "completion.json", completion)
    refs = {k: {"path": str(tmp_path / (k + ".json")), "sha256": H} for k in ("preflight", "process", "exit", "supervisor_completion", "pipeline_completion")}
    refs["pipeline_completion"]["sha256"] = compact[str(pipeline / "completion.json")]
    operational = {"remaining_phases": [[m, s] for m in p.MONTHS[4:] for s in ("correction", "replay")]}
    runtime = {"request": {"path": str(p.CONTINUATION_REQUEST), "sha256": p.CONTINUATION_REQUEST_SHA}}
    review = {"status": "PASS_OOF_USER_STOP_CONTINUATION_IMPLEMENTATION_REVIEW", "decision": "CLEAR"}
    command = ["python", "frozen", "--resume"]
    pre = {"status": "PASS_OOF_USER_STOP_CONTINUATION_PREFLIGHT_NOT_EXECUTED", "executed": False, "request_sha256": p.CONTINUATION_REQUEST_SHA, "runtime_binding_sha256": p.CONTINUATION_BINDING_SHA, "implementation_review_sha256": p.CONTINUATION_REVIEW_SHA, "source_admission_sha256": p.SOURCE_ADMISSION_SHA, "publication_commit": "2" * 40, "command": command}
    authority = {"request_sha256": p.CONTINUATION_REQUEST_SHA, "runtime_binding_sha256": p.CONTINUATION_BINDING_SHA, "implementation_review_sha256": p.CONTINUATION_REVIEW_SHA, "publication_commit": pre["publication_commit"], "preflight_sha256": H, "monitor_code_sha256": p.CONTINUATION_CODE_SHA}
    proc = {"status": "PROCESS_HANDLE_RETAINED", "pid": 4, "creation_time": 5.0, "creation_time_source": "GetProcessTimes_retained_Popen_handle", "command": command, "child_cpu_affinity": [0], "initial_child_affinity_verified": True, **authority}
    ended = {"status": "PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE", "pid": 4, "creation_time": 5.0, "exit_code": 0, "exit_code_source": "GetExitCodeProcess_retained_Popen_handle", "process_receipt_sha256": H, "monitor_valid": True, "retry": False, **authority}
    new_phases = [{"phase": documents[str(pipeline / f"starts/{i:02d}.json")]["phase"], "start": {"path": str(pipeline / f"starts/{i:02d}.json"), "sha256": compact[str(pipeline / f"starts/{i:02d}.json")]}, "receipt": {"path": str(pipeline / f"receipts/{i:02d}.json"), "sha256": compact[str(pipeline / f"receipts/{i:02d}.json")]}} for i in range(8, 12)]
    closure = {"original_validation": {"source_admission_sha256": p.SOURCE_ADMISSION_SHA, "compact_files": compact}, "new_phases": new_phases, "baseline_preserved": True}
    supervisor = {"status": "COMPLETE_OOF_USER_STOP_CONTINUATION_PENDING_INDEPENDENT_AUDIT", "exit_code": 0, "process_files": {refs[k]["path"]: refs[k]["sha256"] for k in ("preflight", "process", "exit")}, "auditor_executed": False, "winner_selected": None, "technical_ready": False, "promotion_approved": False, "retry": False, "pipeline_closure": closure, **{k: authority[k] for k in ("request_sha256", "runtime_binding_sha256", "implementation_review_sha256", "publication_commit")}}
    return [source, operational, runtime, review, pre, proc, ended, supervisor, completion, closure, compact, documents, refs]


def validate(values):
    return p.validate_closed_metadata(*values)


def test_exact_schemas_and_chain(tmp_path):
    values = fixture(tmp_path)
    pairs = validate(values)
    request = p.build_request(values[0], pairs)
    assert len(request) == 9 and len(request["months"]) == 6
    assert len(values[10]) == 45


@pytest.mark.parametrize("fault", ["nonzero", "mismatch", "missing_closure", "monitor", "failure"])
def test_fail_closed_receipts(tmp_path, fault):
    values = fixture(tmp_path)
    if fault == "nonzero": values[6]["exit_code"] = 1
    elif fault == "mismatch": values[6]["creation_time"] = 6.0
    elif fault == "missing_closure": values[7]["status"] = "RUNNING"
    elif fault == "monitor": values[6]["monitor_valid"] = False
    else: values.append(True)
    with pytest.raises(ValueError): validate(values)


def test_package_overwrite_rejected(tmp_path, monkeypatch):
    target = tmp_path / "request.json"
    target.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(p, "REQUEST_OUTPUT", target)
    monkeypatch.setattr(p, "BINDING_OUTPUT", tmp_path / "binding.json")
    with pytest.raises(ValueError, match="destinations"):
        p.prepare()


def test_default_cli_is_read_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(p, "CONTINUATION_LOGS", tmp_path / "missing")
    monkeypatch.setattr(p, "PIPELINE", tmp_path / "pipeline")
    monkeypatch.setattr("sys.argv", ["prepare"])
    assert p.main() == 0
    value = json.loads(capsys.readouterr().out)
    assert value["prepared"] is False and not any(x["exists"] for x in value["required_receipts"].values())
    assert {x["path"] for x in value["required_receipts"].values()} == {
        str(tmp_path / "missing" / n) for n in ("preflight.json", "process.json", "exit.json", "completion.json")
    } | {str(tmp_path / "pipeline" / "completion.json")}


def test_out_of_scope_compact_rejected_before_open(monkeypatch):
    source = {"pipeline_root": "P", "correction_root": "C", "evaluation_roots": {m: "E" + m for m in p.MONTHS}}
    opened = []
    monkeypatch.setattr(p, "verify", lambda *args: opened.append(args))
    monkeypatch.setattr(p, "read", lambda *args: opened.append(args))
    with pytest.raises(ValueError, match="membership"):
        p.load_compact_documents(source, {"outside": H})
    assert opened == []


def test_final_pin_mutation_rejected(tmp_path):
    item = tmp_path / "authority.json"
    item.write_bytes(b"one")
    pins = {str(item): hashlib.sha256(b"one").hexdigest()}
    p.verify_pin_map(pins)
    item.write_bytes(b"two")
    with pytest.raises(ValueError, match="differs"):
        p.verify_pin_map(pins)


def test_binding_schema_map_and_roots():
    receipt_refs = {k: {"path": str(Path("C:/receipts") / (k + ".json")), "sha256": H} for k in ("preflight", "process", "exit", "supervisor_completion", "pipeline_completion")}
    source = p.read(p.SOURCE_REQUEST)
    binding = p.build_binding(H, receipt_refs, source)
    assert len(binding) == 9 and len(binding["upstream"]) == 10
    assert len(binding["allowed_read_roots"]) == 16 and len(binding["published_files"]) == 81


@pytest.mark.parametrize("fault", ["new_phases", "request_sha", "receipt_flags", "closure_status", "dependencies", "run_contract"])
def test_compact_scientific_metadata_rejections(tmp_path, fault):
    values = fixture(tmp_path)
    if fault == "new_phases": values[9]["new_phases"] = [1, 2, 3, 4]
    elif fault == "request_sha": values[11][str(Path(values[0]["pipeline_root"]) / "starts/08.json")]["request_sha256"] = H
    elif fault == "receipt_flags": values[11][str(Path(values[0]["pipeline_root"]) / "receipts/08.json")]["independent_audit_pending"] = False
    elif fault == "closure_status": values[11][str(Path(values[0]["correction_root"]) / "202601.complete.json")]["status"] = "WRONG"
    elif fault == "dependencies": values[11][str(Path(values[0]["evaluation_roots"]["202601"]) / "completion.json")]["dependencies"] = {}
    else: values[11][str(Path(values[0]["evaluation_roots"]["202601"]) / "run_contract.json")]["threshold"] = 1
    with pytest.raises(ValueError): validate(values)


def test_failure_scan_covers_all_upstream_roots(tmp_path):
    source = {"pipeline_root": str(tmp_path / "pipeline"), "correction_root": str(tmp_path / "correction"), "evaluation_roots": {m: str(tmp_path / m) for m in p.MONTHS}}
    logs = tmp_path / "logs"
    for root in (logs, Path(source["pipeline_root"]), Path(source["correction_root"]), *(Path(v) for v in source["evaluation_roots"].values())):
        root.mkdir(parents=True)
    p.reject_unknown_failures(source, logs)
    bad = Path(source["evaluation_roots"]["202606"]) / "nested/failure.json"
    bad.parent.mkdir()
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="failure"):
        p.reject_unknown_failures(source, logs)
