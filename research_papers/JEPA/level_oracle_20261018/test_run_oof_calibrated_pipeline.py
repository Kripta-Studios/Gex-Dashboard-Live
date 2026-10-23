"""Synthetic wrapper lifecycle; producers unchanged, no market or fit."""

import copy
from contextlib import contextmanager
import json
from pathlib import Path

import pandas as pd
import pytest

import run_oof_calibrated_pipeline as runner
import test_audit_oof_calibrated_policy as audit_fixture


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(runner.canonical(value))
    return path


@contextmanager
def preserve(path):
    data = path.read_bytes() if path.exists() else None
    try:
        yield
    finally:
        if data is None:
            if path.exists():
                path.unlink()
        else:
            path.write_bytes(data)


class FullSource(audit_fixture.TinySource):
    """Only the audited-source I/O boundary is synthetic; six producer months run."""

    def __init__(self, root):
        super().__init__(root)
        rows = self.index.reset_index().to_dict("records")
        for month in runner.MONTHS[1:]:
            for ticker in runner.adapter.core.TICKERS:
                day = month + "02"
                destination = self.session / ticker / day
                destination.mkdir(parents=True)
                actions, labels = self.frames()
                actions.to_parquet(destination / "actions.parquet", index=False)
                labels.to_parquet(destination / "labels.parquet", index=False)
                rows.append(
                    dict(
                        ticker=ticker,
                        date=day,
                        status="COMPLETE",
                        close_i=390,
                        day_root=str(destination),
                        actions_sha256=runner.sha(destination / "actions.parquet"),
                        labels_sha256=runner.sha(destination / "labels.parquet"),
                    )
                )
        self.index = pd.DataFrame(rows).set_index(["ticker", "date"])
        self.completed = self.completed_months = set(runner.HISTORY)
        for month in runner.MONTHS[1:]:
            for mode in runner.MODES:
                for ticker in runner.adapter.core.TICKERS:
                    day = month + "02"
                    selected = self.selection(mode, ticker, day)
                    lookup = {
                        r["action_id"]: r
                        for r in self.table(ticker, day, "labels").to_dict("records")
                    }
                    result = runner.evaluator.replay(
                        selected["selected"], 390, lambda i: lookup[i]
                    )
                    prefix = self.root / "ledgers" / month / mode / ticker / day
                    prefix.parent.mkdir(parents=True)
                    for suffix, values in (
                        ("_attempts", result["attempts"]),
                        ("_ledger", result["ledger"]),
                    ):
                        path = Path(str(prefix) + suffix + ".parquet")
                        pd.DataFrame(
                            values, columns=runner.evaluator.FIELDS
                        ).to_parquet(path, index=False)
                        self.allowed[str(path)] = runner.sha(path)


def setup_request(root, monkeypatch):
    source = FullSource(root / "evidence")
    source.index.reset_index().to_parquet(source.session / "index.parquet", index=False)
    index_sha = runner.sha(source.session / "index.parquet")
    session_audit = write(
        root / "session_audit.json",
        dict(
            status="PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT",
            binding=dict(engine_root=str(source.session), index_sha256=index_sha),
        ),
    )
    contract = write(source.root / "run_contract.json", dict(synthetic=True))
    write(
        source.audit_path,
        dict(
            status=runner.adapter.STATUS,
            binding=dict(
                monthly_root=str(source.root),
                session_root=str(source.session),
                completed_months=list(runner.HISTORY),
                run_contract_sha256=runner.sha(contract),
                session_audit_sha256=runner.sha(session_audit),
                index_sha256=index_sha,
            ),
            verified_files={"synthetic": {}},
        ),
    )
    source.authority_sha = source.audit_sha = runner.sha(source.audit_path)
    source.base_used = {str(source.audit_path): source.audit_sha}
    source.used = dict(source.base_used)
    lock = root / "coordination" / "pipeline.lock"
    monkeypatch.setattr(runner, "GLOBAL_LOCK", lock)
    records = []

    def fresh(*_args):
        instance = copy.copy(source)
        instance.used = dict(source.base_used)
        instance.seal = audit_fixture.audit.Seal()
        records.append(instance)
        return instance

    monkeypatch.setattr(runner.adapter, "MonthlyInputs", fresh)
    value = dict(
        version="OOF_PIPELINE_RUNTIME_REQUEST_V1",
        status="REVIEWED_OOF_PIPELINE_RUNTIME_REQUEST",
        runtime_authorized=True,
        months=list(runner.MONTHS),
        coordination_lock=str(lock),
        code=runner.dependencies(),
        monthly_root=str(source.root),
        session_root=str(source.session),
        monthly_audit=dict(path=str(source.audit_path), sha256=source.audit_sha),
        session_audit=dict(path=str(session_audit), sha256=runner.sha(session_audit)),
        pipeline_root=str(root / "pipeline"),
        correction_root=str(root / "correction"),
        evaluation_roots={m: str(root / ("evaluation_" + m)) for m in runner.MONTHS},
    )
    request = write(root / "request.json", value)
    return request, records, source


GOOD_MEMORY = dict(available_ram_bytes=3_000_000_000, free_commit_bytes=3_000_000_000)


@pytest.fixture(scope="module")
def completed_pipeline(tmp_path_factory):
    root = tmp_path_factory.mktemp("oof_pipeline_complete")
    with pytest.MonkeyPatch.context() as patch:
        path, instances, source = setup_request(root, patch)
        calls = []

        def pause_at_boundary():
            calls.append(1)
            if len(calls) == 3:
                raise ValueError("synthetic resource gate before replay")
            return GOOD_MEMORY

        patch.setattr(runner, "resource_gate", pause_at_boundary)
        with pytest.raises(ValueError, match="resource gate"):
            runner.pipeline(path, runner.sha(path))
        request = runner.Request(path, runner.sha(path))
        assert runner.receipt_path(request, 0).exists()
        assert not runner.start_path(request, 1).exists()
        patch.setattr(runner, "resource_gate", lambda: GOOD_MEMORY)
        with preserve(request.pipeline / "completion.json"):
            write(request.pipeline / "completion.json", {"orphan": True})
            with pytest.raises(ValueError, match="Premature"):
                runner.pipeline(path, runner.sha(path), resume=True)
            assert len(instances) == 1
        result = runner.pipeline(path, runner.sha(path), resume=True)
        assert len(instances) == 12
        assert len({id(s.used) for s in instances}) == 12
        # A correction instance never inherited the replay's target-month label reads.
        for month, instance in zip(runner.MONTHS, instances[::2]):
            assert not any(
                month in p and p.endswith("labels.parquet") for p in instance.used
            )
        yield path, request, result, source


def test_full_pipeline_boundary_resume_and_all_fixed_months(completed_pipeline):
    path, request, result, _ = completed_pipeline
    assert result["status"] == "PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT"
    assert list(result["months"]) == list(runner.MONTHS)
    assert result["winner_selected"] is None and not result["auditor_executed"]
    assert not result["technical_ready"] and not result["promotion_approved"]
    count, inventory, last, closures = runner.completed_prefix(request)
    assert count == 12 and inventory and closures == result["months"]
    assert last == result["last_receipt_sha256"]
    assert runner.sha(path) == request.sha
    assert len(list((request.pipeline / "failures").glob("*.json"))) == 2
    receipts = [
        json.loads(runner.receipt_path(request, i).read_text()) for i in range(12)
    ]
    assert (
        sum(r["new_output_bytes"] for r in receipts)
        == receipts[-1]["cumulative_output_bytes"]
    )
    assert all(
        r["rss_start_bytes"] > 0
        and r["rss_end_bytes"] > 0
        and r["rss_peak_measured"] is False
        for r in receipts
    )


def test_full_resume_revalidates_without_producer_calls(
    completed_pipeline, monkeypatch
):
    path, _, result, _ = completed_pipeline

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Completed phase was repeated")

    monkeypatch.setattr(runner.adapter, "prepare_correction", forbidden)
    monkeypatch.setattr(runner.evaluator, "evaluate_month", forbidden)
    monkeypatch.setattr(runner.adapter, "MonthlyInputs", forbidden)
    assert runner.pipeline(path, runner.sha(path), resume=True) == result


@pytest.mark.parametrize(
    "fault",
    [
        "orphan",
        "changed",
        "partial",
        "missing_receipt",
        "foreign_start",
        "bad_completion",
    ],
)
def test_completed_prefix_rejects_mutations_and_orphans(completed_pipeline, fault):
    _, request, _, _ = completed_pipeline
    if fault == "orphan":
        path = request.correction / "unclaimed.json"
    elif fault == "changed":
        path = request.correction / "static/202601/calibration.json"
    elif fault == "partial":
        path = request.evaluations["202606"] / "extra.partial"
    elif fault == "missing_receipt":
        path = runner.receipt_path(request, 11)
    elif fault == "bad_completion":
        path = request.pipeline / "completion.json"
    else:
        path = request.pipeline / "starts/12.json"
    with preserve(path):
        if fault == "missing_receipt":
            path.unlink()
        else:
            path.write_bytes(b"{}")
        with pytest.raises((ValueError, KeyError)):
            runner.completed_prefix(request)


def test_receipt_chain_rejects_rebinding(completed_pipeline):
    _, request, _, _ = completed_pipeline
    path = runner.receipt_path(request, 1)
    with preserve(path):
        record = json.loads(path.read_text())
        record["previous_receipt_sha256"] = "0" * 64
        write(path, record)
        with pytest.raises(ValueError, match="chain"):
            runner.completed_prefix(request)


def test_realized_mutation_rejected_by_correction_closure_before_new_receipt(
    completed_pipeline,
):
    _, request, result, _ = completed_pipeline
    path = request.correction / "static/realized/SPY/20250102.json"
    with preserve(path):
        payload = json.loads(path.read_text())
        payload["rows"][0]["net_base"] += 1
        write(path, payload)
        with pytest.raises(ValueError, match="Changed sealed"):
            runner.correction_closure(
                request,
                "202601",
                result["months"]["202601"]["correction_completion_sha256"],
            )


@pytest.mark.parametrize(
    "fault", ["hash", "code", "overlap", "lock", "months", "authority", "relative"]
)
def test_request_rejects_before_outputs(completed_pipeline, tmp_path, fault):
    path, request, _, _ = completed_pipeline
    value = json.loads(path.read_text())
    if fault == "code":
        value["code"]["run_oof_calibrated_pipeline.py"] = "0" * 64
    elif fault == "overlap":
        value["correction_root"] = value["monthly_root"]
    elif fault == "lock":
        value["coordination_lock"] = str(tmp_path / "other.lock")
    elif fault == "months":
        value["months"].pop()
    elif fault == "authority":
        value["monthly_audit"]["sha256"] = "0" * 64
    elif fault == "relative":
        value["pipeline_root"] = "relative"
    test_path = write(tmp_path / "request.json", value)
    with pytest.raises(ValueError):
        runner.Request(
            test_path, "0" * 64 if fault == "hash" else runner.sha(test_path)
        )
    assert runner.sha(path) == request.sha


def test_global_lock_is_sequence_wide(completed_pipeline):
    with runner.sequence_lock():
        with pytest.raises(OSError):
            with runner.sequence_lock():
                pytest.fail("A second pipeline acquired the same global lock")


@pytest.mark.parametrize("fault", ["crash", "realized_mutation"])
def test_crash_after_producer_closure_never_adopts_receiptless_output(
    tmp_path, monkeypatch, fault
):
    path, instances, _ = setup_request(tmp_path, monkeypatch)
    monkeypatch.setattr(runner, "resource_gate", lambda: GOOD_MEMORY)
    original = runner.correction_closure

    def crash(request, month, expected):
        if fault == "crash":
            raise RuntimeError("crash after producer closure before receipt")
        realized = request.correction / "static/realized/SPY/20250102.json"
        payload = json.loads(realized.read_text())
        payload["rows"][0]["net_base"] += 1
        write(realized, payload)
        return original(request, month, expected)

    monkeypatch.setattr(runner, "correction_closure", crash)
    with pytest.raises(
        (RuntimeError, ValueError), match="before receipt|Changed sealed"
    ):
        runner.pipeline(path, runner.sha(path))
    request = runner.Request(path, runner.sha(path))
    assert (request.correction / "202601.complete.json").exists()
    assert not runner.receipt_path(request, 0).exists()
    assert not (request.pipeline / "completion.json").exists()
    monkeypatch.setattr(runner, "correction_closure", original)
    with pytest.raises(ValueError, match="orphan|partial"):
        runner.pipeline(path, runner.sha(path), resume=True)
    assert len(instances) == 1
    assert len(list((request.pipeline / "failures").glob("*.json"))) == 2


def test_resource_rejection_before_admission_writes_nothing(tmp_path, monkeypatch):
    path = write(tmp_path / "request.json", {})
    monkeypatch.setattr(
        runner, "resource_gate", lambda: (_ for _ in ()).throw(ValueError("2GB"))
    )
    with pytest.raises(ValueError, match="2GB"):
        runner.pipeline(path, runner.sha(path))
    assert list(tmp_path.iterdir()) == [path]


def test_no_final_auditor_import_or_invocation():
    import ast

    tree = ast.parse(Path(runner.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module]
            )
            assert "audit_oof_calibrated_policy" not in names
