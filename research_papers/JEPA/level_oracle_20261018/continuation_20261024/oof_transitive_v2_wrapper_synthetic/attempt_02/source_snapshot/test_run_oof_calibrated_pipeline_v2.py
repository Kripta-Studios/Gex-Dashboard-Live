"""Synthetic wrapper lifecycle; producers unchanged, no market or fit."""

import copy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil

import pandas as pd
import pytest

import run_oof_calibrated_pipeline_v2 as runner
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
        self.external = root / "engine_v1"
        self.external_audited = {}
        for (ticker, day), row in self.index.iterrows():
            if row.close_i == 210:
                continue
            destination = self.external / ticker / day
            destination.mkdir(parents=True)
            for kind in ("actions", "labels"):
                target = destination / (kind + ".parquet")
                shutil.copyfile(Path(row.day_root) / target.name, target)
                if not day.startswith("202606"):
                    self.external_audited[str(target)] = runner.sha(target)
            self.index.loc[(ticker, day), "day_root"] = str(destination)


def setup_request(root, monkeypatch):
    source = FullSource(root / "evidence")
    source.index.reset_index().to_parquet(source.session / "index.parquet", index=False)
    index_sha = runner.sha(source.session / "index.parquet")
    session_audit = write(
        root / "session_audit.json",
        dict(
            status="PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT",
            binding=dict(engine_root=str(source.session), index_sha256=index_sha,
                         available_days=len(source.index), missing_days=0),
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
            verified_files={"synthetic": source.external_audited},
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
        version="OOF_PIPELINE_RUNTIME_REQUEST_V2",
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
        value["code"]["run_oof_calibrated_pipeline_v2.py"] = "0" * 64
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


def test_external_sibling_and_index_only_june_cross_real_closures(completed_pipeline):
    _, request, result, source = completed_pipeline
    june = source.external / "SPY/20260602"
    for kind in ("actions", "labels"):
        path = june / (kind + ".parquet")
        assert str(path) not in source.external_audited
        member = request.admission["members"][runner.path_key(path)]
        assert member["origins"] == [f"index:SPY:20260602:{kind}"]
    correction = json.loads((request.correction / "202606.inputs.json").read_text())
    assert str(june / "actions.parquet") in correction["files"]
    assert str(june / "labels.parquet") not in correction["files"]
    replay = json.loads((request.evaluations["202606"] / "completion.json").read_text())
    assert str(june / "labels.parquet") in replay["monthly_files"]
    assert result["months"]["202606"]["evaluation_completion_sha256"]
    contract = json.loads((request.pipeline / "contract.json").read_text())
    assert contract["source_admission_sha256"] == request.admission["map_sha256"]
    assert contract["version"] == "OOF_PIPELINE_V2"


@pytest.fixture
def metadata_sources(tmp_path):
    rows, audited = [], {}
    for month in runner.HISTORY:
        root = tmp_path / ("session" if month == "202507" else "engine_v1") / "SPY" / (month + "02")
        root.mkdir(parents=True)
        row = dict(ticker="SPY", date=month + "02", status="COMPLETE",
                   close_i=210 if month == "202507" else 390, day_root=str(root))
        for kind in ("actions", "labels"):
            path = root / (kind + ".parquet")
            path.write_bytes((kind + month).encode())  # never parsed as a market table
            row[kind + "_sha256"] = runner.sha(path)
            if month != "202606":
                audited[str(path)] = runner.sha(path)
        rows.append(row)
    rows.append(dict(ticker="QQQ", date="20260401", status="MISSING_SOURCE", close_i=390,
                     day_root=None, actions_sha256=None, labels_sha256=None))
    index = tmp_path / "index.parquet"
    pd.DataFrame(rows).to_parquet(index, index=False)
    return dict(verified_files={"fit_inputs": audited}), index, dict(
        binding=dict(available_days=18, missing_days=1))


def admit(case):
    monthly, index, session = case
    return runner.transitive_admission(monthly, index, runner.sha(index), session)


def fake_request(tmp_path, admission):
    request = object.__new__(runner.Request)
    request.path = tmp_path / "request.json"
    request.monthly = tmp_path / "monthly"
    request.session = tmp_path / "session"
    request.correction = tmp_path / "correction"
    request.evaluations = {m: tmp_path / ("replay_" + m) for m in runner.MONTHS}
    request.authorities = {}
    request.admission = admission
    request.consumed_identities = dict(admission["indexed_identities"])
    return request


def test_metadata_only_A_and_exact_I_scope(metadata_sources, tmp_path, monkeypatch):
    monthly, _, _ = metadata_sources
    historical = tmp_path / "historical_arrays/never_stat.npy"
    monthly["verified_files"]["fit_inputs"][str(historical)] = "0" * 64
    original = Path.stat

    def guarded(path, *args, **kwargs):
        assert path != historical, "A inventory payload was stat'ed"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", guarded)
    result = admit(metadata_sources)
    assert len(result["indexed_sidecars"]) == 36
    assert runner.path_key(historical) in result["members"]
    runner.protect_transitive_outputs([tmp_path / "new_output"], result)
    assert all("20260401" not in key for key in result["indexed_sidecars"])


@pytest.mark.parametrize("fault", ["hash", "unlisted", "outside_calendar", "alias", "separator_alias", "output"])
def test_transitive_consumption_and_output_guards(metadata_sources, tmp_path, fault):
    monthly, _, _ = metadata_sources
    if fault == "outside_calendar":
        old = tmp_path / "engine_v1/SPY/20241202/actions.parquet"
        old.parent.mkdir(parents=True)
        old.write_bytes(b"past outside declared sidecar calendar")
        monthly["verified_files"]["fit_inputs"][str(old)] = runner.sha(old)
    admission = admit(metadata_sources)
    request = fake_request(tmp_path, admission)
    path = tmp_path / "engine_v1/SPY/20260602/actions.parquet"
    if fault == "output":
        with pytest.raises(ValueError, match="Output overlaps"):
            runner.protect_transitive_outputs([path.parent / "new_output"], admission)
        return
    if fault == "outside_calendar":
        path = old
    elif fault == "unlisted":
        path = path.with_name("unlisted.json")
        path.write_bytes(b"{}")
    name = str(path).swapcase() if fault == "alias" else str(path)
    if fault == "separator_alias":
        name = str(path).replace("\\", "/")
    expected = "0" * 64 if fault == "hash" else runner.sha(path)
    with pytest.raises(ValueError):
        runner.verify_map(request, {name: expected})


@pytest.mark.parametrize("fault", ["conflict", "separator_alias", "case_alias", "missing_nonnull", "duplicate"])
def test_authority_union_faults(metadata_sources, fault):
    monthly, index, _ = metadata_sources
    paths = monthly["verified_files"]["fit_inputs"]
    path = next(iter(paths))
    if fault == "conflict":
        paths[path] = "0" * 64
    elif fault == "separator_alias":
        monthly["verified_files"]["alias"] = {path.replace("\\", "/"): paths[path]}
    elif fault == "case_alias":
        monthly["verified_files"]["alias"] = {path.swapcase(): paths[path]}
    else:
        frame = pd.read_parquet(index)
        if fault == "missing_nonnull":
            frame.loc[frame.status == "MISSING_SOURCE", "actions_sha256"] = "a" * 64
        else:
            frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
        frame.to_parquet(index, index=False)
    with pytest.raises(ValueError):
        admit(metadata_sources)


def test_omitted_index_only_june_and_changed_index_fail(metadata_sources, tmp_path, monkeypatch):
    monthly, index, session = metadata_sources
    frame = pd.read_parquet(index)
    frame = frame.loc[~frame.date.str.startswith("202606")]
    frame.to_parquet(index, index=False)
    session["binding"]["available_days"] = 17
    with pytest.raises(ValueError, match="month coverage"):
        admit(metadata_sources)
    expected = runner.sha(index)
    original = pd.read_parquet

    def mutate(path, **kwargs):
        result = original(path, **kwargs)
        index.write_bytes(index.read_bytes() + b"changed")
        return result

    monkeypatch.setattr(pd, "read_parquet", mutate)
    with pytest.raises(ValueError, match="changed during metadata"):
        runner.transitive_admission(monthly, index, expected, session)


def test_missing_payload_is_deferred_to_consumption(metadata_sources, tmp_path):
    path = tmp_path / "engine_v1/SPY/20260602/labels.parquet"
    expected = runner.sha(path)
    path.unlink()
    admission = admit(metadata_sources)
    request = fake_request(tmp_path, admission)
    with pytest.raises(FileNotFoundError):
        runner.verify_map(request, {str(path): expected})


def test_hardlink_and_physical_alias_rejected(metadata_sources, tmp_path, monkeypatch):
    path = tmp_path / "engine_v1/SPY/20260602/labels.parquet"
    alias = tmp_path / "hardlink"
    os.link(path, alias)
    with pytest.raises(ValueError, match="Hardlinked"):
        admit(metadata_sources)
    alias.unlink()
    other = path.with_name("actions.parquet")
    identities = {}
    runner.inspect_consumed_identity(path, identities)
    original = Path.stat
    physical = original(path)

    def same_id(candidate, *args, **kwargs):
        return physical if candidate == other else original(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", same_id)
    with pytest.raises(ValueError, match="Physical input alias"):
        runner.inspect_consumed_identity(other, identities)


def test_linked_ancestor_rejected_without_payload_read(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "linked"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        import subprocess
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True,
                       capture_output=True)
    with pytest.raises(ValueError, match="Linked"):
        runner.absolute(str(link / "unread.parquet"))


def test_economic_closure_functions_ast_unchanged():
    import ast
    original = ast.parse(Path(runner.__file__).with_name("run_oof_calibrated_pipeline.py").read_text())
    current = ast.parse(Path(runner.__file__).read_text())
    names = {"correction_closure", "replay_closure", "completed_prefix", "phases", "inventory"}
    before = {n.name: ast.dump(n, include_attributes=False) for n in original.body
              if isinstance(n, ast.FunctionDef) and n.name in names}
    after = {n.name: ast.dump(n, include_attributes=False) for n in current.body
             if isinstance(n, ast.FunctionDef) and n.name in names}
    assert before == after and set(before) == names
