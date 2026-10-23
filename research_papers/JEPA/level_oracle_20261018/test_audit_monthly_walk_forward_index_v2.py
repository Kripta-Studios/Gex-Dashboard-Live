"""Synthetic metadata admission, including the six actual null-row identities."""

import ast
import inspect
import json
from pathlib import Path
import sys
import textwrap
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import audit_monthly_walk_forward as original
import audit_monthly_walk_forward_index_v2 as audit
import test_audit_monthly_walk_forward as legacy


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def row(root, **changes):
    value = dict(ticker="SPY", date="20250102", status="COMPLETE", close_i=390,
                 day_root=str(root / "day"), evaluation_status=None)
    value.update({name: str(root / name) for name in audit.FEATURE_PATH_FIELDS})
    value.update({name: "a" * 64 for name in audit.SOURCE_HASH_FIELDS})
    value.update(changes)
    return value


def missing_row(root, **changes):
    value = row(root, ticker="QQQ", date="20260401", status="MISSING_SOURCE", evaluation_status="NO_EVALUABLE")
    value.update({name: None for name in (*audit.FEATURE_PATH_FIELDS, *audit.SOURCE_HASH_FIELDS)})
    value.update(changes)
    return value


def metadata_fixture(root, fault=None):
    import exchange_calendars as xc
    monthly, session = root / "monthly", root / "session"
    session.mkdir(parents=True)
    schedule = xc.get_calendar("XNYS").schedule.loc["2023-01-03":"2026-06-30"]
    rows = []
    for ticker in audit.TICKERS:
        for stamp, clock in schedule.iterrows():
            day = stamp.strftime("%Y%m%d")
            factory = missing_row if (ticker, day) in audit.MISSING else row
            rows.append(factory(root, ticker=ticker, date=day,
                                close_i=int((clock.close-clock.open).total_seconds()/60)))
    frame = pd.DataFrame(rows)
    if fault == "drop":
        frame = frame.iloc[:-1].copy()
    elif fault == "missing_identity":
        position = frame.index[frame.status == "MISSING_SOURCE"][0]
        frame.loc[position, "date"] = "20260418"
    elif fault == "complete_null":
        frame.loc[0, "features_path"] = None
    elif fault == "schema":
        frame = frame.drop(columns="evaluation_status")
    frame.to_parquet(session / "index.parquet", index=False)
    for name in ("dataset_contract.json", "completion.json", "feature_contract.json"):
        write(session / name, {"synthetic_metadata": name})
    binding = dict(engine_root=str(session), feature_root=str(session),
        index_sha256=audit.sha(session / "index.parquet"),
        dataset_contract_sha256=audit.sha(session / "dataset_contract.json"),
        completion_sha256=audit.sha(session / "completion.json"),
        feature_contract_sha256=audit.sha(session / "feature_contract.json"),
        available_days=2619, missing_days=6)
    source_audit = write(root / "source_audit.json", dict(
        status="PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT", binding=binding))
    dependencies = {}
    for name in audit.DEPENDENCIES:
        path = monthly / "executed_code" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic frozen code " + name)
        dependencies[name] = audit.sha(path)
    write(monthly / "run_contract.json", dict(version=audit.VERSION, seed=audit.SEED,
        features=1954, dependencies=dependencies, feature_root=str(session),
        source_audit=dict(path=str(source_audit), sha256=audit.sha(source_audit), binding=binding,
                          coverage={"synthetic": True}, feature_contract_sha256=binding["feature_contract_sha256"])))
    return monthly, source_audit, frame


def review_payload():
    return dict(status=audit.REVIEW_STATUS, decision="CLEAR", scope="IMPLEMENTATION_ONLY", runtime_authorized=False,
        auditor_sha256=audit.sha(audit.__file__),
        tests_sha256=audit.sha(__file__),
        contract_sha256=audit.sha(Path(audit.__file__).with_name("MONTHLY_WALK_FORWARD_INDEX_AUDIT_V2_SPEC_20261024.md")),
        original_auditor_sha256=audit.ORIGINAL_AUDITOR_SHA,
        original_review_sha256=audit.ORIGINAL_REVIEW_SHA,
        original_contract_sha256=audit.ORIGINAL_CONTRACT_SHA)


def test_full_realistic_index_constructor_retains_all_rows_without_payload_reads(tmp_path, monkeypatch):
    monthly, source_audit, frame = metadata_fixture(tmp_path)
    review = write(tmp_path / "review_v2.json", review_payload())
    original_read = audit.pd.read_parquet
    seen = []

    def metadata_only(path, *args, **kwargs):
        assert Path(path) == tmp_path / "session/index.parquet"
        seen.append(str(path))
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(audit.pd, "read_parquet", metadata_only)
    monkeypatch.setattr(audit.np, "load", lambda *_a, **_k: pytest.fail("Feature array read during admission"))
    instance = audit.MonthlyAudit(monthly, source_audit, review)
    assert len(instance.days) == len(instance.index) == 2625 and len(seen) == 1
    assert list(instance.days) == list(zip(frame.ticker, frame.date))
    assert sum(day.status == "COMPLETE" for day in instance.days.values()) == 2619
    assert sum(day.stamp.startswith("2025") for day in instance.days.values()) == 750
    assert sum(day.stamp.startswith("2026") for day in instance.days.values()) == 369
    missing = [day for day in instance.days.values() if day.status == "MISSING_SOURCE"]
    assert {(day.ticker, day.stamp) for day in missing} == audit.MISSING
    assert all(day.feature_paths is None and day.actions_sha256 is None and day.labels_sha256 is None for day in missing)
    assert not instance.source_reads
    monkeypatch.setattr(audit, "sha", lambda *_a: pytest.fail("Missing source hashed"))
    for day in missing:
        for name in ("actions.parquet", "labels.parquet"):
            with pytest.raises(ValueError, match="cannot be read"):
                instance.source_frame(day, name)


@pytest.mark.parametrize("fault", ["drop", "missing_identity", "complete_null", "schema"])
def test_full_constructor_rejects_bad_metadata(tmp_path, fault):
    monthly, source_audit, _ = metadata_fixture(tmp_path, fault)
    with pytest.raises(ValueError):
        audit.MonthlyAudit(monthly, source_audit)


@pytest.mark.parametrize("field", [*audit.FEATURE_PATH_FIELDS, *audit.SOURCE_HASH_FIELDS])
def test_complete_null_field_rejected(tmp_path, field):
    with pytest.raises(ValueError):
        audit.source_day_from_index(SimpleNamespace(**row(tmp_path, **{field: None})))


@pytest.mark.parametrize("field", [*audit.FEATURE_PATH_FIELDS, *audit.SOURCE_HASH_FIELDS])
def test_missing_nonnull_field_rejected(tmp_path, field):
    value = "a" * 64 if field in audit.SOURCE_HASH_FIELDS else str(tmp_path / "fabricated")
    with pytest.raises(ValueError, match="null paths and hashes"):
        audit.source_day_from_index(SimpleNamespace(**missing_row(tmp_path, **{field: value})))


@pytest.mark.parametrize("value", [None, np.nan, pd.NA])
def test_missing_null_representations_preserved(tmp_path, value):
    payload = missing_row(tmp_path)
    payload.update({name: value for name in (*audit.FEATURE_PATH_FIELDS, *audit.SOURCE_HASH_FIELDS)})
    result = audit.source_day_from_index(SimpleNamespace(**payload))
    assert result.feature_paths is None and result.actions_sha256 is None


@pytest.mark.parametrize("change", [dict(status="UNKNOWN"), dict(features_path="relative"),
    dict(features_path=""), dict(actions_sha256="bad"), dict(evaluation_status="NO_EVALUABLE"),
    dict(day_root=None), dict(close_i=389)])
def test_complete_invalid_metadata_rejected(tmp_path, change):
    with pytest.raises(ValueError):
        audit.source_day_from_index(SimpleNamespace(**row(tmp_path, **change)))


@pytest.mark.parametrize("change", [dict(date="20260418"), dict(ticker="SPXW"), dict(evaluation_status=None)])
def test_missing_identity_and_no_evaluable_contract(tmp_path, change):
    with pytest.raises(ValueError):
        audit.source_day_from_index(SimpleNamespace(**missing_row(tmp_path, **change)))


@pytest.mark.parametrize("field", ["status", "decision", "scope", "runtime_authorized", "auditor_sha256", "tests_sha256", "contract_sha256",
    "original_auditor_sha256", "original_review_sha256", "original_contract_sha256"])
def test_v2_review_and_original_lineage_are_exact(tmp_path, field):
    path = write(tmp_path / "review.json", review_payload())
    audit.verify_implementation_review(path, audit.Verifier())
    value = review_payload()
    value[field] = "wrong" if field == "status" else "0" * 64
    write(path, value)
    with pytest.raises(ValueError):
        audit.verify_implementation_review(path, audit.Verifier())


def test_cli_external_pin_fails_before_constructor(tmp_path, monkeypatch):
    path = write(tmp_path / "review.json", {})
    monkeypatch.setattr(sys, "argv", ["audit", "--monthly-root", str(tmp_path / "monthly"),
        "--source-audit", str(tmp_path / "source"), "--implementation-review", str(path),
        "--implementation-review-sha256", "0" * 64, "--output", str(tmp_path / "output")])
    monkeypatch.setattr(audit, "MonthlyAudit", lambda *_a: pytest.fail("Constructor before external review gate"))
    with pytest.raises(ValueError, match="External V2"):
        audit.main()
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("name", [name for name in vars(legacy)
    if name.startswith("test_") and name != "test_implementation_review_is_an_exact_byte_gate"])
def test_legacy_scientific_fixtures_use_v2(name, tmp_path, monkeypatch):
    monkeypatch.setattr(legacy, "audit", audit)
    function = getattr(legacy, name)
    function(tmp_path) if "tmp_path" in inspect.signature(function).parameters else function()


def parsed(function):
    return ast.dump(ast.parse(textwrap.dedent(inspect.getsource(function))))


def test_original_scientific_function_and_method_asts_are_identical():
    assert audit.sha(original.__file__) == audit.ORIGINAL_AUDITOR_SHA
    for name, function in vars(original).items():
        if inspect.isfunction(function) and function.__module__ == original.__name__ and name not in ("main", "verify_implementation_review"):
            assert parsed(function) == parsed(getattr(audit, name)), name
    for name, function in vars(original.MonthlyAudit).items():
        if inspect.isfunction(function) and name not in ("__init__", "source_frame"):
            assert parsed(function) == parsed(getattr(audit.MonthlyAudit, name)), name
    expected = inspect.getsource(original.MonthlyAudit.source_frame).replace(
        '    def source_frame(self, day, filename, columns=None):\n',
        '    def source_frame(self, day, filename, columns=None):\n'
        '        require(day.status == "COMPLETE", "Missing source cannot be read")\n')
    assert ast.dump(ast.parse(textwrap.dedent(expected))) == parsed(audit.MonthlyAudit.source_frame)
    before = inspect.getsource(original.MonthlyAudit.__init__)
    start, end = before.index('        self.days = {}\n'), before.index('        self._validated_training_days = {}\n')
    expected = before[:start] + '        self.days = source_days_from_index(index)\n' + before[end:]
    assert ast.dump(ast.parse(textwrap.dedent(expected))) == parsed(audit.MonthlyAudit.__init__)
    expected = inspect.getsource(original.main).replace(
        '    parser.add_argument("--implementation-review", type=Path, required=True)\n',
        '    parser.add_argument("--implementation-review", type=Path, required=True)\n'
        '    parser.add_argument("--implementation-review-sha256", required=True)\n').replace(
        '    require(not args.output.exists(), "Use a new audit output directory")\n',
        '    require(not args.output.exists(), "Use a new audit output directory")\n'
        '    require(sha(args.implementation_review) == args.implementation_review_sha256,\n'
        '            "External V2 implementation review SHA differs")\n')
    assert ast.dump(ast.parse(expected)) == parsed(audit.main)
    for name in ("STATUS", "VERSION", "MODES", "TICKERS", "SEED", "BANDS", "CAP_PER_BAND", "DEPENDENCIES"):
        assert getattr(audit, name) == getattr(original, name)
