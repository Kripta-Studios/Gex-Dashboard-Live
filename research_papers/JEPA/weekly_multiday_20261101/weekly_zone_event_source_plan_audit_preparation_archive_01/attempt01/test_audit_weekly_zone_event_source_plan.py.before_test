"""Synthetic tests for the independent weekly zone-event metadata auditor."""
from __future__ import annotations

from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

import audit_weekly_zone_event_source_plan as audit


def test_digest_shape_rejects_non_lowercase_sha() -> None:
    with pytest.raises(audit.AuditError, match="SHA256 shape"):
        audit.digest_shape("A" * 64)


def test_validate_pin_checks_rows_when_requested() -> None:
    expected = {"bytes": 7, "sha256": "a" * 64}
    with pytest.raises(audit.AuditError, match="rows"):
        audit.validate_pin({**expected, "rows": 2}, expected, "fixture", rows=3)


def test_validate_coverage_requires_empty_candidate_ids() -> None:
    row = {
        "candidate_ids": ["forbidden"], "entry_date": "20260102", "entry_path": None,
        "exit_date": "20260106", "exit_path": None, "expiration": None,
        "reason": "NO_SERIES", "status": "NO_SERIES", "ticker": "SPY",
    }
    with pytest.raises(audit.AuditError, match="candidate IDs"):
        audit.validate_coverage(row, ("SPY", "20260102"))


def test_validate_coverage_rejects_extra_field() -> None:
    row = {
        "candidate_ids": [], "entry_date": "20260102", "entry_path": None,
        "exit_date": "20260106", "exit_path": None, "expiration": None,
        "reason": "NO_SERIES", "status": "NO_SERIES", "ticker": "SPY", "extra": 1,
    }
    with pytest.raises(audit.AuditError, match="coverage schema"):
        audit.validate_coverage(row, ("SPY", "20260102"))


def test_nominal_path_rejects_lexical_traversal() -> None:
    value = (audit.SOURCE_ROOT / "data_options" / "SPY" / "greeks" / "2026" / "01" / ".." /
             "SPY_20260109_20260102_greeks.parquet")
    with pytest.raises(audit.AuditError, match="lexical traversal"):
        audit.validate_nominal_path_text(str(value))


def test_nominal_path_rejects_trade_date_directory_mismatch() -> None:
    value = audit.SOURCE_ROOT / "data_options/SPY/greeks/2025/12/SPY_20260109_20260102_greeks.parquet"
    with pytest.raises(audit.AuditError, match="date directories"):
        audit.validate_nominal_path_text(str(value))


def test_reconstruct_planned_path_rejects_lexical_traversal() -> None:
    entry = (audit.SOURCE_ROOT / "data_options/SPY/greeks/2026/01" / ".." / "01" /
             "SPY_20260109_20260102_greeks.parquet")
    h2 = audit.nominal_path("SPY", "20260109", "20260106")
    with pytest.raises(audit.AuditError, match="lexical traversal"):
        audit.planned_upstream_paths(
            {"entry_path": str(entry), "exit_path": str(h2)},
            "SPY", "20260109", "20260102", "20260106")


def test_discrepancy_reports_presence_absence_and_bytes() -> None:
    bindings = [
        {"status": "INVENTORIED", "bytes": 10},
        {"status": "MISSING_SOURCE", "bytes": None},
    ]
    assert audit.discrepancy(bindings, {"exists": True, "bytes": 11}) == [
        "CURRENT_BYTES_DIFFER_FROM_EXPECTED_UPSTREAM", "EXPECTED_MISSING_NOW_PRESENT"
    ]
    assert audit.discrepancy(bindings[:1], {"exists": False, "bytes": None}) == [
        "EXPECTED_PRESENT_NOW_MISSING"
    ]


def test_market_observation_never_opens_market_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "SOURCE_ROOT", tmp_path)
    market = tmp_path / "data_options/SPY/greeks/2026/01/SPY_20260109_20260102_greeks.parquet"
    market.parent.mkdir(parents=True)
    market.write_bytes(b"do-not-read")

    def forbidden_open(*_args, **_kwargs):
        raise AssertionError("market content opened")

    monkeypatch.setattr(Path, "open", forbidden_open)
    value = audit.market_observation(market)
    assert value["exists"] is True
    assert value["bytes"] == len(b"do-not-read")


def test_market_observation_rejects_reparse_or_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "SOURCE_ROOT", tmp_path)
    market = tmp_path / "data_options/SPY/greeks/2026/01/SPY_20260109_20260102_greeks.parquet"
    market.parent.mkdir(parents=True)
    market.write_bytes(b"x")
    monkeypatch.setattr(audit, "linked", lambda _info: True)
    with pytest.raises(audit.AuditError, match="link/reparse"):
        audit.market_observation(market)


@pytest.mark.parametrize(
    ("bad_mode", "attributes", "message"),
    ((stat.S_IFDIR, audit.REPARSE, "link/reparse"), (stat.S_IFREG, 0, "not a directory")),
)
def test_market_observation_rejects_bad_anchor_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_mode: int, attributes: int, message: str
) -> None:
    monkeypatch.setattr(audit, "SOURCE_ROOT", tmp_path)
    market = tmp_path / "data_options/SPY/greeks/2026/01/SPY_20260109_20260102_greeks.parquet"
    bad_anchor = Path(tmp_path.anchor)

    def fake_lstat(path: Path):
        path = audit.absolute(Path(path))
        if path == audit.absolute(bad_anchor):
            return SimpleNamespace(st_mode=bad_mode, st_file_attributes=attributes)
        if path == audit.absolute(market):
            return SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0, st_size=1,
                                   st_mtime_ns=2, st_dev=3, st_ino=4)
        return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0)

    with pytest.raises(audit.AuditError, match=message):
        audit.market_observation(market, fake_lstat)


def test_attach_observations_rejects_physical_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    same = {"exists": True, "bytes": 1, "mtime_ns": 2, "physical_id": [3, 4]}
    monkeypatch.setattr(audit, "market_observation", lambda _path: dict(same))
    records = [
        {"path": r"D:\ThetaData\data_options\SPY\greeks\2026\01\SPY_20260109_20260102_greeks.parquet",
         "references": [], "expected_upstream_bindings": [], "new_without_upstream_binding": True},
        {"path": r"D:\ThetaData\data_options\QQQ\greeks\2026\01\QQQ_20260109_20260102_greeks.parquet",
         "references": [], "expected_upstream_bindings": [], "new_without_upstream_binding": True},
    ]
    with pytest.raises(audit.AuditError, match="physical alias"):
        audit.attach_observations(records)


def test_expected_summary_counts_unique_bytes_not_references() -> None:
    entries = [
        {"status": "PLANNED", "ticker": "SPY", "date": "20260102"},
        {"status": "NO_SERIES", "ticker": "QQQ", "date": "20260102"},
    ]
    reference = {"role": "ENTRY_DAY", "ticker": "SPY", "trade_date": "20260102"}
    sources = [{"references": [reference, dict(reference)],
                "observation": {"exists": True, "bytes": 17},
                "new_without_upstream_binding": True, "metadata_discrepancies": []}]
    value = audit.expected_summary(entries, sources)
    assert value["references"]["total"] == 2
    assert value["sources"]["unique"] == 1
    assert value["sources"]["present_unique_bytes"] == 17


def test_expected_summary_keeps_all_safety_flags_false() -> None:
    value = audit.expected_summary([], [])
    assert value["flags"] == {"metadata_only": True, **audit.EXPECTED_FLAGS}


def test_validate_retained_exit_requires_exact_integer_zero() -> None:
    observer = audit.BASE / "weekly_zone_event_source_plan_observer_01"
    files = {str(audit.absolute(observer / name)): "a" * 64 for name in audit.OBSERVER_FILES}
    valid = {"exit_code": 0, "planner_child_exit_code": 0, "utc": "2026-11-02T00:00:00+00:00",
             "source": "subprocess.Popen.wait_retained_handle", "elapsed_seconds": 1.0, "pid": 7,
             "creation_time": 2.0, "cpu_affinity": [0], "metadata_error": None,
             "changed_pins": [], "files": files, "retry": False}
    audit.validate_retained_exit(valid)
    for changed in ({"exit_code": 1}, {"exit_code": True}, {"planner_child_exit_code": 1}):
        value = {**valid, **changed}
        with pytest.raises(audit.AuditError, match="retained exit"):
            audit.validate_retained_exit(value)
    for value in ({}, []):
        with pytest.raises(audit.AuditError, match="retained exit"):
            audit.validate_retained_exit(value)


def test_validate_retained_exit_requires_exact_five_observer_files() -> None:
    observer = audit.BASE / "weekly_zone_event_source_plan_observer_01"
    files = {str(audit.absolute(observer / name)): "a" * 64 for name in audit.OBSERVER_FILES}
    valid = {"exit_code": 0, "planner_child_exit_code": 0, "utc": "2026-11-02T00:00:00+00:00",
             "source": "subprocess.Popen.wait_retained_handle", "elapsed_seconds": 1.0, "pid": 7,
             "creation_time": 2.0, "cpu_affinity": [0], "metadata_error": None,
             "changed_pins": [], "files": files, "retry": False}
    missing = dict(files)
    missing.pop(next(iter(missing)))
    with pytest.raises(audit.AuditError, match="exact observer files"):
        audit.validate_retained_exit({**valid, "files": missing})
    with pytest.raises(audit.AuditError, match="exact observer files"):
        audit.validate_retained_exit({**valid, "files": {**files, str(observer / "extra.json"): "b" * 64}})


def test_implementation_pin_rejects_same_basename_in_wrong_subdir(tmp_path: Path) -> None:
    expected = tmp_path / "build_weekly_zone_event_source_plan.py"
    wrong = tmp_path / "nested" / expected.name
    wrong.parent.mkdir()
    expected.write_text("expected", encoding="utf-8")
    wrong.write_text("wrong", encoding="utf-8")
    value = audit.pin(wrong)
    with pytest.raises(audit.AuditError, match="exact path"):
        audit.validate_implementation_pin(value, expected, value["sha256"], "producer builder", tmp_path)


def test_historical_source_rejects_path_outside_exact_root() -> None:
    row = {"bytes": 1, "path": r"D:\Elsewhere\SPY_20260109_20260102_greeks.parquet",
           "projected_schema": [], "rows": 1, "sha256": "a" * 64, "status": "INVENTORIED"}
    with pytest.raises(audit.AuditError, match="outside options root"):
        audit.validate_historical_source(row, "H1")


def test_cli_requires_all_runtime_pins() -> None:
    with pytest.raises(SystemExit):
        audit.parser().parse_args(["--execute-reviewed-audit"])
