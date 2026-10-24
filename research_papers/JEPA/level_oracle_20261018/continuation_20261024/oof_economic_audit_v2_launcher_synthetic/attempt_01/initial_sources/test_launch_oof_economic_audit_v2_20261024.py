"""Small synthetic JSON/text evidence and harmless Python children; no science run."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

import launch_oof_economic_audit_v2_20261024 as s


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value), encoding="utf-8")
    return {"path": str(p), "sha256": s.sha(p)}


def rewrite(ref, value):
    ref.update(write(Path(ref["path"]), value))


@pytest.fixture
def case(tmp_path, monkeypatch):
    tmp_path = tmp_path.resolve()
    code, base = tmp_path / "code", tmp_path / "artifacts"
    code.mkdir()
    base.mkdir()
    metadata = base / "metadata"
    metadata.mkdir()
    original = s.CODE
    scientific = s.read(original / s.AUDIT_REVIEW)
    previous = s.read(original / s.PIPELINE_REVIEW)
    names = (
        set(previous["files"]) | set(s.NEW_FILES) | {s.AUDIT_REVIEW, s.PIPELINE_REVIEW}
    )
    for group in scientific["binding"].values():
        names.update(group)
    names.update(s.ADDITIONAL_AUTHORITIES)
    names.update(s.ORIGINAL_PROVENANCE)
    names.update(
        s.read(original / s.WRAPPER_REVIEW)["binding"]["runtime_dependency_map"]
    )
    for name in names:
        shutil.copyfile(original / name, code / name)
    monkeypatch.setattr(s, "CODE", code)
    monkeypatch.setattr(s, "REPO", tmp_path)
    monkeypatch.setattr(s, "BASE", base)
    source_code = s.read(original / s.WRAPPER_REVIEW)["binding"][
        "runtime_dependency_map"
    ]
    monthly, session, correction, pipeline, logs = (
        base / n
        for n in ("monthly", "session", "correction", "pipeline", "upstream_logs")
    )
    evaluations = {m: base / ("replay_" + m) for m in s.MONTHS}
    for root in (monthly, session, correction, pipeline, logs, *evaluations.values()):
        root.mkdir()
    source = dict(
        version="OOF_PIPELINE_RUNTIME_REQUEST_V2",
        status="REVIEWED_OOF_PIPELINE_RUNTIME_REQUEST",
        runtime_authorized=True,
        months=s.MONTHS,
        code=source_code,
        coordination_lock=str(base / "oof_pipeline_runtime.lock"),
        monthly_root=str(monthly),
        session_root=str(session),
        correction_root=str(correction),
        pipeline_root=str(pipeline),
        evaluation_roots={m: str(p) for m, p in evaluations.items()},
        monthly_audit=write(metadata / "monthly_audit.json", {"synthetic": "monthly"}),
        session_audit=write(metadata / "session_audit.json", {"synthetic": "source"}),
    )
    (base / "oof_pipeline_runtime.lock").write_bytes(b"0")
    source_ref = write(metadata / "pipeline_request.json", source)
    runtime = dict(
        status="PASS_OOF_TRANSITIVE_SOURCE_V2_LAUNCH_RUNTIME_BINDING",
        request=source_ref,
        implementation_review={
            "path": str(code / s.PIPELINE_REVIEW),
            "sha256": s.PIPELINE_REVIEW_SHA,
        },
        logs_root=str(logs),
    )
    runtime_ref = write(metadata / "pipeline_binding.json", runtime)
    command = [
        sys.executable,
        "-u",
        str(code / "run_oof_calibrated_pipeline_v2.py"),
        "--request",
        source_ref["path"],
        "--request-sha256",
        source_ref["sha256"],
    ]
    pre = write(
        logs / "preflight.json",
        dict(
            status="PASS_OOF_LAUNCH_PREFLIGHT_NOT_EXECUTED",
            executed=False,
            request_sha256=source_ref["sha256"],
            runtime_binding_sha256=runtime_ref["sha256"],
            implementation_review_sha256=s.PIPELINE_REVIEW_SHA,
            command=command,
            publication_commit="a" * 40,
            source_admission_sha256="a" * 64,
        ),
    )
    identity = dict(
        monitor_code_sha256=s.sha(code / "launch_oof_pipeline_v2_20261024.py"),
        request_sha256=source_ref["sha256"],
        runtime_binding_sha256=runtime_ref["sha256"],
        implementation_review_sha256=s.PIPELINE_REVIEW_SHA,
        publication_commit="a" * 40,
        preflight_sha256=pre["sha256"],
    )
    opened = write(
        logs / "process.json",
        dict(
            status="PROCESS_HANDLE_RETAINED",
            pid=789,
            creation_time=123.5,
            creation_time_source="GetProcessTimes_retained_Popen_handle",
            command=command,
            monitor_started_utc="2026-10-24T01:00:00+00:00",
            **identity,
        ),
    )
    exited = write(
        logs / "exit.json",
        dict(
            status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE",
            pid=789,
            creation_time=123.5,
            exit_code=0,
            exit_code_source="GetExitCodeProcess_retained_Popen_handle",
            process_receipt_sha256=opened["sha256"],
            observed_utc="2026-10-24T01:01:00+00:00",
            **identity,
        ),
    )
    compact = {}

    def member(p, value):
        ref = write(p, value)
        compact[ref["path"]] = ref["sha256"]
        return ref["sha256"]

    member(pipeline / "request.json", source)
    member(
        pipeline / "contract.json",
        dict(
            version="OOF_PIPELINE_V2",
            request_sha256=source_ref["sha256"],
            code=source_code,
            correction_layout="SHARED_CUMULATIVE",
            source_admission_sha256="a" * 64,
        ),
    )
    prior, pairs, inventory = None, {}, {}
    for i, (month, stage) in enumerate(
        (m, st) for m in s.MONTHS for st in ("correction", "replay")
    ):
        phase = dict(
            request_sha256=source_ref["sha256"],
            phase=[month, stage],
            previous_receipt_sha256=prior,
        )
        started = member(pipeline / f"starts/{i:02d}.json", phase)
        if stage == "correction":
            target = correction / (month + ".complete.json")
            close_sha = member(
                target,
                dict(
                    status="COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS",
                    target_month=month,
                    monthly_audit_sha256=source["monthly_audit"]["sha256"],
                    dependencies={n: source_code[n] for n in s.ADAPTER_NAMES},
                    winner_selected=None,
                    target_labels_read=False,
                    base_models_refitted=False,
                    development_seen=True,
                ),
            )
            pairs[month] = {"correction_completion_sha256": close_sha}
        else:
            target = evaluations[month] / "completion.json"
            deps = {n: source_code[n] for n in s.REPLAY_NAMES}
            close_sha = member(
                target,
                dict(
                    status="COMPLETE_FIXED_OOF_POLICY_MONTH",
                    target_month=month,
                    winner_selected=None,
                    dependencies=deps,
                ),
            )
            contract = evaluations[month] / "run_contract.json"
            inventory[str(contract)] = member(
                contract,
                dict(
                    version="OOF_POLICY_REPLAY_V1",
                    dependencies=deps,
                    monthly_audit_sha256=source["monthly_audit"]["sha256"],
                    correction_completion_sha256=pairs[month][
                        "correction_completion_sha256"
                    ],
                    target_month=month,
                    threshold=0,
                    winner_selected=None,
                ),
            )
            pairs[month]["evaluation_completion_sha256"] = close_sha
        inventory[str(target)] = close_sha
        prior = member(
            pipeline / f"receipts/{i:02d}.json",
            dict(
                status="COMPLETE_OOF_PIPELINE_PHASE",
                winner_selected=None,
                independent_audit_pending=True,
                start_sha256=started,
                completion_sha256=close_sha,
                output_inventory=dict(inventory),
                **phase,
            ),
        )
    science = write(
        pipeline / "completion.json",
        dict(
            status="PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT",
            request_sha256=source_ref["sha256"],
            last_receipt_sha256=prior,
            months=pairs,
            winner_selected=None,
            technical_ready=False,
            promotion_approved=False,
            auditor_executed=False,
        ),
    )
    compact[science["path"]] = science["sha256"]
    finished = write(
        logs / "completion.json",
        dict(
            status="COMPLETE_OOF_PIPELINE_SUPERVISION_PENDING_INDEPENDENT_AUDIT",
            exit_code=0,
            request_sha256=source_ref["sha256"],
            runtime_binding_sha256=runtime_ref["sha256"],
            implementation_review_sha256=s.PIPELINE_REVIEW_SHA,
            publication_commit="a" * 40,
            process_files={ref["path"]: ref["sha256"] for ref in (pre, opened, exited)},
            pipeline_closure=dict(
                source_admission_sha256="a" * 64,
                compact_files=compact,
                output_count=len(inventory),
                output_inventory_sha256=hashlib.sha256(
                    json.dumps(
                        inventory, sort_keys=True, separators=(",", ":")
                    ).encode()
                ).hexdigest(),
            ),
            completed_utc="2026-10-24T01:02:00+00:00",
            auditor_executed=False,
            technical_ready=False,
            promotion_approved=False,
            retry=False,
        ),
    )
    request = dict(
        version="OOF_ECONOMIC_AUDIT_REQUEST_V1",
        scope="FULL_H1",
        monthly_root=str(monthly),
        session_root=str(session),
        correction_root=str(correction),
        monthly_audit=source["monthly_audit"]["path"],
        monthly_audit_sha256=source["monthly_audit"]["sha256"],
        session_audit=source["session_audit"]["path"],
        months=[
            dict(month=m, evaluation_root=str(evaluations[m]), **pairs[m])
            for m in s.MONTHS
        ],
    )
    request_ref = write(metadata / "audit_request.json", request)
    read_roots = [
        str(code),
        str(metadata),
        str(monthly),
        str(session),
        str(correction),
        str(pipeline),
        str(logs),
        *map(str, evaluations.values()),
    ]
    evidence = s.Evidence(read_roots)
    files = s.review_files(evidence)
    review = write(
        code / s.REVIEW_NAME,
        dict(
            status=s.REVIEW_STATUS,
            decision="CLEAR",
            scope="IMPLEMENTATION_ONLY",
            runtime_authorized=False,
            files=files,
        ),
    )
    published = {str(code / n): h for n, h in files.items()}
    published.update(
        {
            str(code / s.AUDIT_REVIEW): s.AUDIT_REVIEW_SHA,
            str(code / s.PIPELINE_REVIEW): s.PIPELINE_REVIEW_SHA,
            review["path"]: review["sha256"],
            request_ref["path"]: request_ref["sha256"],
            source_ref["path"]: source_ref["sha256"],
            runtime_ref["path"]: runtime_ref["sha256"],
        }
    )
    binding = dict(
        status=s.BINDING_STATUS,
        source_admission_sha256="a" * 64,
        request=request_ref,
        implementation_review=review,
        output_root=str(base / "audit_out"),
        logs_root=str(base / "audit_logs"),
        allowed_read_roots=read_roots,
        published_files=published,
        upstream=dict(
            pipeline_request=source_ref,
            pipeline_binding=runtime_ref,
            preflight=pre,
            process=opened,
            exit=exited,
            supervisor_completion=finished,
            pipeline_completion=science,
        ),
    )
    binding_ref = write(metadata / "audit_binding.json", binding)
    publication_calls = []
    monkeypatch.setattr(
        s,
        "publication",
        lambda commit, files: publication_calls.append((commit, files)),
    )
    return SimpleNamespace(
        request=request,
        binding=binding,
        request_ref=request_ref,
        binding_ref=binding_ref,
        review=review,
        source=source,
        base=base,
        code=code,
        pipeline=pipeline,
        logs=logs,
        publication_calls=publication_calls,
    )


def admit(c):
    return s.preflight(
        c.request_ref["path"],
        c.request_ref["sha256"],
        c.binding_ref["path"],
        c.binding_ref["sha256"],
        c.review["sha256"],
        "b" * 40,
    )


def test_full_preflight_no_side_effect_or_scientific_import(case):
    before = set(case.base.rglob("*"))
    receipt = admit(case)
    assert receipt["executed"] is False and set(case.base.rglob("*")) == before
    assert len(case.publication_calls) == 1 and not Path(receipt["logs_root"]).exists()


@pytest.mark.parametrize("fault", ["scope", "months", "monthly_object", "future_hash"])
def test_bad_request(case, fault):
    if fault == "scope":
        case.request["scope"] = "MONTHS"
    if fault == "months":
        case.request["months"].pop()
    if fault == "monthly_object":
        case.request["monthly_audit"] = case.source["monthly_audit"]
    if fault == "future_hash":
        case.request["months"][0]["evaluation_completion_sha256"] = None
    rewrite(case.request_ref, case.request)
    rewrite(case.binding_ref, case.binding)
    with pytest.raises((ValueError, TypeError)):
        admit(case)


@pytest.mark.parametrize(
    "field,value",
    [
        ("exit_code", False),
        ("exit_code", 7),
        ("pid", True),
        ("creation_time", True),
        ("observed_utc", "2026-10-24T01:01:00"),
        ("process_receipt_sha256", "0" * 64),
    ],
)
def test_resigned_exit_fault(case, field, value):
    ref = case.binding["upstream"]["exit"]
    changed = s.read(ref["path"])
    changed[field] = value
    rewrite(ref, changed)
    finished_ref = case.binding["upstream"]["supervisor_completion"]
    finished = s.read(finished_ref["path"])
    finished["process_files"][ref["path"]] = ref["sha256"]
    rewrite(finished_ref, finished)
    rewrite(case.binding_ref, case.binding)
    with pytest.raises(ValueError):
        admit(case)


@pytest.mark.parametrize(
    "fault",
    [
        "missing_compact",
        "wrong_inventory",
        "wrong_review",
        "wrong_code",
        "upstream_failure",
        "nested_partial",
        "output_exists",
        "output_overlap",
    ],
)
def test_bad_authority_or_output(case, fault):
    ref = case.binding["upstream"]["supervisor_completion"]
    finished = s.read(ref["path"])
    if fault == "missing_compact":
        finished["pipeline_closure"]["compact_files"].pop(
            next(iter(finished["pipeline_closure"]["compact_files"]))
        )
    if fault == "wrong_inventory":
        finished["pipeline_closure"]["output_inventory_sha256"] = "0" * 64
    if fault in ("missing_compact", "wrong_inventory"):
        rewrite(ref, finished)
    if fault == "wrong_review":
        case.binding["implementation_review"]["sha256"] = "0" * 64
    if fault == "wrong_code":
        (case.code / s.AUDITOR).write_text("changed", encoding="utf-8")
    if fault == "upstream_failure":
        write(case.logs / "failure.json", {})
    if fault == "nested_partial":
        write(case.pipeline / "starts/00.json.partial", {})
    if fault == "output_exists":
        Path(case.binding["output_root"]).mkdir()
    if fault == "output_overlap":
        case.binding["output_root"] = case.source["correction_root"]
    rewrite(case.binding_ref, case.binding)
    with pytest.raises(ValueError):
        admit(case)


def test_exact_code18_membership_not_merely_count(case):
    u = case.binding["upstream"]
    source = s.read(u["pipeline_request"]["path"])
    source["code"].pop("test_run_oof_calibrated_pipeline_v2.py")
    source["code"]["train_models.py"] = s.sha(case.code / "train_models.py")
    rewrite(u["pipeline_request"], source)
    runtime = s.read(u["pipeline_binding"]["path"])
    runtime["request"] = u["pipeline_request"]
    rewrite(u["pipeline_binding"], runtime)
    rewrite(case.binding_ref, case.binding)
    with pytest.raises(ValueError, match="Exact OOF V2 request18"):
        admit(case)


def reseal_process_metadata(case):
    """Synthetic signing helper; ensures faults reach the intended digest guard."""
    u = case.binding["upstream"]
    opened = s.read(u["process"]["path"])
    opened["preflight_sha256"] = u["preflight"]["sha256"]
    rewrite(u["process"], opened)
    exited = s.read(u["exit"]["path"])
    exited["preflight_sha256"] = u["preflight"]["sha256"]
    exited["process_receipt_sha256"] = u["process"]["sha256"]
    rewrite(u["exit"], exited)
    finished = s.read(u["supervisor_completion"]["path"])
    finished["process_files"] = {
        u[k]["path"]: u[k]["sha256"] for k in ("preflight", "process", "exit")
    }
    rewrite(u["supervisor_completion"], finished)
    rewrite(case.binding_ref, case.binding)


@pytest.mark.parametrize(
    "fault",
    [
        "request_v1",
        "binding_v1",
        "contract_v1",
        "preflight_digest",
        "contract_digest",
        "supervision_digest",
        "external_digest",
        "missing_digest",
        "invented_completion_digest",
    ],
)
def test_v2_identity_and_source_admission_exact(case, fault):
    u = case.binding["upstream"]
    if fault == "request_v1":
        source = s.read(u["pipeline_request"]["path"])
        source["version"] = "OOF_PIPELINE_RUNTIME_REQUEST_V1"
        rewrite(u["pipeline_request"], source)
    elif fault == "binding_v1":
        runtime = s.read(u["pipeline_binding"]["path"])
        runtime["status"] = "PASS_OOF_PIPELINE_LAUNCH_RUNTIME_BINDING"
        rewrite(u["pipeline_binding"], runtime)
    elif fault in ("preflight_digest", "missing_digest"):
        pre = s.read(u["preflight"]["path"])
        if fault == "missing_digest":
            pre.pop("source_admission_sha256")
        else:
            pre["source_admission_sha256"] = "b" * 64
        rewrite(u["preflight"], pre)
    elif fault == "external_digest":
        case.binding["source_admission_sha256"] = "b" * 64
    else:
        finished = s.read(u["supervisor_completion"]["path"])
        if fault == "supervision_digest":
            finished["pipeline_closure"]["source_admission_sha256"] = "b" * 64
        elif fault == "invented_completion_digest":
            complete = s.read(u["pipeline_completion"]["path"])
            complete["source_admission_sha256"] = "a" * 64
            rewrite(u["pipeline_completion"], complete)
            finished["pipeline_closure"]["compact_files"][
                u["pipeline_completion"]["path"]
            ] = u["pipeline_completion"]["sha256"]
        else:
            target = case.pipeline / "contract.json"
            contract = s.read(target)
            if fault == "contract_v1":
                contract["version"] = "OOF_PIPELINE_V1"
            else:
                contract["source_admission_sha256"] = "b" * 64
            pin = write(target, contract)
            finished["pipeline_closure"]["compact_files"][str(target)] = pin["sha256"]
        rewrite(u["supervisor_completion"], finished)
    reseal_process_metadata(case)
    expected = {
        "request_v1": "Pipeline request schema",
        "binding_v1": "Pipeline runtime authority",
        "contract_v1": "Pipeline stored request/contract",
        "preflight_digest": "source admission binding",
        "contract_digest": "Pipeline stored request/contract",
        "supervision_digest": "source admission binding",
        "external_digest": "source admission binding",
        "invented_completion_digest": "Pipeline final closure",
    }
    if fault == "missing_digest":
        with pytest.raises(KeyError, match="source_admission_sha256"):
            admit(case)
    else:
        with pytest.raises(ValueError, match=expected[fault]):
            admit(case)


@pytest.mark.parametrize("unreviewed", [None, "0" * 64])
def test_upstream_review_cannot_be_pending(case, monkeypatch, unreviewed):
    monkeypatch.setattr(s, "PIPELINE_REVIEW_SHA", unreviewed)
    with pytest.raises(ValueError):
        admit(case)


def audit_output(receipt):
    request = s.read(receipt["request_path"])
    root = Path(receipt["output_root"])
    root.mkdir()
    evidence = dict(receipt["files"])
    result = dict(
        status="PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_FULL_H1",
        scope="OOF_OFFSETS_AND_ECONOMIC_EXECUTION_GIVEN_AUDITED_BASE_SCORES",
        binding=dict(
            request_sha256=receipt["request_sha256"],
            monthly_audit_sha256=request["monthly_audit_sha256"],
            audited_months=s.MONTHS,
            correction_root=request["correction_root"],
        ),
        months=[dict(target_month=m) for m in s.MONTHS],
        policies={
            m + suffix: {}
            for m in ("static", "expanding", "rolling12")
            for suffix in ("__control", "__corrected")
        },
        verified_files=evidence,
        winner_selected=None,
        development_seen=True,
        base_fit_reproduced=False,
        base_inference_reproduced=False,
        raw_quote_replay=False,
        technical_ready=False,
        promotion_approved=False,
    )
    write(root / "audit.json", result)
    return result


@pytest.mark.parametrize(
    "fault", [None, "failure", "scope", "request", "member", "promotion", "months"]
)
def test_result_metadata(case, fault):
    receipt = admit(case)
    result = audit_output(receipt)
    root = Path(receipt["output_root"])
    if fault == "failure":
        write(root / "audit_failure.json", {})
    if fault == "scope":
        result["status"] = "PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_DECLARED_MONTHS"
    if fault == "request":
        result["binding"]["request_sha256"] = "0" * 64
    if fault == "member":
        result["verified_files"].pop(str(s.CODE / s.AUDITOR))
    if fault == "promotion":
        result["promotion_approved"] = True
    if fault == "months":
        result["months"].pop()
    write(root / "audit.json", result)
    if fault:
        with pytest.raises(ValueError):
            s.validate_audit(receipt)
    else:
        assert s.validate_audit(receipt) == {
            str(root / "audit.json"): s.sha(root / "audit.json")
        }


@pytest.mark.parametrize("field", ["available_ram_bytes", "free_commit_bytes"])
def test_low_gate(field):
    resources = dict(available_ram_bytes=s.MIN_FREE, free_commit_bytes=s.MIN_FREE)
    resources[field] -= 1
    with pytest.raises(ValueError):
        s.gate(resources)


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "exit7",
        "preflight_mutated",
        "publish_failed",
        "junction_after_popen",
        "invalid_audit",
        "late_snapshot",
    ],
)
def test_real_empty_child_and_failures(case, monkeypatch, fault):
    receipt = admit(case)
    original_validate = s.validate_audit

    def validate(receipt):
        result = original_validate(receipt)
        if fault == "late_snapshot":
            (Path(receipt["logs_root"]) / s.NAME).write_text(
                "late mutation", encoding="utf-8"
            )
        return result

    monkeypatch.setattr(s, "validate_audit", validate)
    original_popen, original_publish, original_path = (
        s.subprocess.Popen,
        s.publish,
        s.path,
    )
    events, children = [], []

    def gate(value):
        events.append("gate")
        assert min(value.values()) >= s.MIN_FREE

    def popen(*args, **kwargs):
        assert events[-1] == "gate"
        events.append("popen")
        assert args[0] == receipt["command"]
        child = original_popen(
            [
                sys.executable,
                "-c",
                "raise SystemExit(7)" if fault == "exit7" else "pass",
            ],
            **kwargs,
        )
        children.append(child)
        audit_output(receipt)
        if fault == "preflight_mutated":
            write(Path(receipt["logs_root"]) / "preflight.json", {"changed": True})
        if fault == "invalid_audit":
            write(Path(receipt["output_root"]) / "audit_failure.json", {})
        if fault == "junction_after_popen":

            def redirected(value):
                if str(value) == receipt["output_root"]:
                    raise ValueError("simulated output junction after Popen")
                return original_path(value)

            monkeypatch.setattr(s, "path", redirected)
        return child

    def publish(p, value):
        if fault == "publish_failed" and Path(p).name == "admission.json":
            raise OSError("synthetic publication failure")
        return original_publish(p, value)

    monkeypatch.setattr(s, "gate", gate)
    monkeypatch.setattr(s.subprocess, "Popen", popen)
    monkeypatch.setattr(s, "publish", publish)
    if fault:
        with pytest.raises((ValueError, OSError)):
            s.launch(receipt)
    else:
        assert s.launch(receipt) == 0
    logs = Path(receipt["logs_root"])
    assert len(children) == 1 and children[0].poll() is not None
    assert (logs / "completion.json").exists() == (fault is None)
    if fault == "publish_failed":
        assert not (logs / "exit.json").exists()
    else:
        assert s.read(logs / "exit.json")["exit_code"] == (7 if fault == "exit7" else 0)
    if fault:
        assert (logs / "failure.json").is_file()
    with pytest.raises(ValueError):
        s.launch(receipt)
    assert len(children) == 1


def test_monitor_init_failure_drains(case, monkeypatch):
    receipt = admit(case)
    Path(receipt["logs_root"]).mkdir()
    child = subprocess.Popen(
        [sys.executable, "-c", "pass"], creationflags=subprocess.CREATE_NO_WINDOW
    )
    monkeypatch.setattr(
        s,
        "RetainedProcess",
        lambda child: (_ for _ in ()).throw(OSError("init failure")),
    )
    with pytest.raises(OSError):
        s.monitor(child, receipt, "0" * 64)
    assert child.poll() == 0 and not (Path(receipt["logs_root"]) / "exit.json").exists()


def test_locks_exclusive_global_bytes_preserved(case):
    global_lock = s.BASE / "oof_pipeline_runtime.lock"
    before = global_lock.read_bytes()
    with s.lock(global_lock, False):
        with pytest.raises(OSError):
            with s.lock(global_lock, False):
                pass
    assert global_lock.read_bytes() == before


def test_publication_rejects_wrong_object(tmp_path, monkeypatch):
    p = tmp_path.resolve() / "x.txt"
    p.write_bytes(b"local")
    monkeypatch.setattr(s, "REPO", tmp_path.resolve())
    monkeypatch.setattr(
        s.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=b"different")
    )
    with pytest.raises(ValueError):
        s.publication("b" * 40, {str(p): s.sha(p)})


def test_default_cli_no_launch(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launcher",
            "--request",
            "x",
            "--request-sha256",
            "a",
            "--runtime-binding",
            "b",
            "--runtime-binding-sha256",
            "c",
            "--implementation-review-sha256",
            "d",
            "--publication-commit",
            "e",
        ],
    )
    monkeypatch.setattr(s, "preflight", lambda *a: {"executed": False})
    monkeypatch.setattr(s, "launch", lambda *a: pytest.fail("default must not launch"))
    assert s.main() == 0 and json.loads(capsys.readouterr().out)["executed"] is False
