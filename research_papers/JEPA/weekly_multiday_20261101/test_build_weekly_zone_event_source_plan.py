from __future__ import annotations

import ast
import builtins
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_weekly_zone_event_source_plan as planner


DATES = (
    "20260629",
    "20260630",
    "20260701",
    "20260702",
    "20260706",
    "20260707",
    "20260916",
    "20260917",
)
SMALL = planner.Expectations(
    calendar_rows=24,
    sessions=8,
    h1_rows=6,
    q3_rows=18,
    short_rows=0,
    status_counts={
        "PLANNED": 6,
        "NO_SERIES": 12,
        "HORIZON_OUTSIDE_CALENDAR": 6,
    },
    overlay_rows=6,
    reference_count=18,
    first_date="20260629",
    last_date="20260917",
)


def calendar_rows(dates: tuple[str, ...] = DATES) -> list[dict[str, object]]:
    return [
        {"ticker": ticker, "date": day, "close_i": 390}
        for day in dates
        for ticker in planner.TICKERS
    ]


def coverage_row(
    root: Path,
    ticker: str,
    day: str,
    status: str,
    d2: str | None,
    *,
    expiration: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_ids": [],
        "entry_date": day,
        "entry_path": None,
        "exit_date": d2,
        "exit_path": None,
        "expiration": None,
        "reason": None,
        "status": status,
        "ticker": ticker,
    }
    if status == "PLANNED":
        assert expiration is not None and d2 is not None
        row.update(
            expiration=expiration,
            entry_path=str(planner.nominal_source_path(root, ticker, expiration, day)),
            exit_path=str(planner.nominal_source_path(root, ticker, expiration, d2)),
        )
    elif status == "NO_SERIES":
        row["reason"] = "NO_1_TO_8_DTE_SERIES_ALLOWING_H2"
    else:
        row.update(exit_date=None, reason="NO_OFFICIAL_H2")
    return row


def artificial_bundle(root: Path) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    h1 = [
        coverage_row(root, ticker, day, "HORIZON_OUTSIDE_CALENDAR", None)
        for day in DATES[:2]
        for ticker in planner.TICKERS
    ]
    q3: list[dict[str, object]] = []
    for index, day in enumerate(DATES[2:], start=2):
        for ticker in planner.TICKERS:
            if day == "20260701":
                q3.append(coverage_row(root, ticker, day, "PLANNED", DATES[index + 2], expiration="20260708"))
            elif index + 2 < len(DATES):
                q3.append(coverage_row(root, ticker, day, "NO_SERIES", DATES[index + 2]))
            else:
                q3.append(coverage_row(root, ticker, day, "HORIZON_OUTSIDE_CALENDAR", None))
    bridge = []
    for ticker in planner.TICKERS:
        bridge.append(coverage_row(root, ticker, "20260629", "PLANNED", "20260701", expiration="20260702"))
        bridge.append(coverage_row(root, ticker, "20260630", "NO_SERIES", "20260702"))
    return h1, q3, bridge


def plans_and_calendar(root: Path) -> tuple[list[dict[str, object]], dict[tuple[str, str], int]]:
    rows = calendar_rows()
    dates, calendar = planner.validate_calendar(rows, rows[:6], rows[6:], SMALL)
    h1, q3, bridge = artificial_bundle(root)
    return planner.build_entry_plan(h1, q3, bridge, dates, calendar, root, SMALL), calendar


def historical_row(path: Path, *, size: int | None, status: str = "INVENTORIED") -> dict[str, object]:
    return {
        "bytes": size,
        "path": str(path),
        "projected_schema": None,
        "rows": None,
        "sha256": "a" * 64 if status == "INVENTORIED" else None,
        "status": status,
    }


def test_calendar_partition_and_h2_are_session_based(tmp_path: Path) -> None:
    plans, _calendar = plans_and_calendar(tmp_path)
    june29 = next(row for row in plans if row["plan_id"] == "SPY:20260629")
    assert june29["session_dates"] == {"D": "20260629", "D1": "20260630", "D2": "20260701"}
    assert june29["source_authority"] == "BRIDGE"
    assert len(plans) == 24


def test_duplicate_calendar_identity_is_rejected() -> None:
    rows = calendar_rows()
    rows[-1] = dict(rows[0])
    with pytest.raises(planner.PlanError, match="duplicate calendar"):
        planner.validate_calendar(rows, rows[:6], rows[6:], SMALL)


def test_unequal_ticker_calendar_is_rejected() -> None:
    rows = calendar_rows()
    rows[0]["close_i"] = 210
    with pytest.raises(planner.PlanError, match="ticker calendars unequal"):
        planner.validate_calendar(rows, rows[:6], rows[6:], SMALL)


def test_short_day_count_and_q3_short_day_are_rejected() -> None:
    rows = calendar_rows()
    for row in rows[:3]:
        row["close_i"] = 210
    valid = planner.Expectations(**{**SMALL.__dict__, "short_rows": 3})
    dates, calendar = planner.validate_calendar(rows, rows[:6], rows[6:], valid)
    assert dates[0] == DATES[0] and sum(value == 210 for value in calendar.values()) == 3
    wrong = planner.Expectations(**{**SMALL.__dict__, "short_rows": 2})
    with pytest.raises(planner.PlanError, match="short-day count"):
        planner.validate_calendar(rows, rows[:6], rows[6:], wrong)
    q3_rows = calendar_rows()
    for row in q3_rows[6:9]:
        row["close_i"] = 210
    with pytest.raises(planner.PlanError, match="Q3 contains a short session"):
        planner.validate_calendar(q3_rows, q3_rows[:6], q3_rows[6:], valid)


def test_overlay_must_be_exact_and_within_six(tmp_path: Path) -> None:
    rows = calendar_rows()
    dates, calendar = planner.validate_calendar(rows, rows[:6], rows[6:], SMALL)
    h1, q3, bridge = artificial_bundle(tmp_path)
    with pytest.raises(planner.PlanError, match="exact|outside"):
        planner.build_entry_plan(h1, q3, bridge[:-1], dates, calendar, tmp_path, SMALL)
    extra = coverage_row(tmp_path, "SPY", "20260701", "NO_SERIES", "20260706")
    with pytest.raises(planner.PlanError, match="outside"):
        planner.build_entry_plan(h1, q3, bridge + [extra], dates, calendar, tmp_path, SMALL)


def test_no_series_and_terminal_rows_never_invent_paths(tmp_path: Path) -> None:
    plans, _calendar = plans_and_calendar(tmp_path)
    no_series = [row for row in plans if row["status"] == "NO_SERIES"]
    terminal = [row for row in plans if row["status"] == "HORIZON_OUTSIDE_CALENDAR"]
    assert len(no_series) == 12 and len(terminal) == 6
    assert all(row["expiration"] is None and row["entry_path"] is None and row["h2_path"] is None for row in no_series + terminal)
    assert all("candidate_ids" not in row for row in plans)
    assert terminal[0]["session_dates"]["D1"] == "20260917"
    assert terminal[0]["session_dates"]["D2"] is None


@pytest.mark.parametrize("expiration", ["20260629", "20260720", "20260701"])
def test_expiry_bounds_and_expiry_after_h2_are_enforced(tmp_path: Path, expiration: str) -> None:
    rows = calendar_rows()
    dates, calendar = planner.validate_calendar(rows, rows[:6], rows[6:], SMALL)
    h1, q3, bridge = artificial_bundle(tmp_path)
    bridge[0] = coverage_row(tmp_path, "SPY", "20260629", "PLANNED", "20260701", expiration=expiration)
    with pytest.raises(planner.PlanError, match="expiry"):
        planner.build_entry_plan(h1, q3, bridge, dates, calendar, tmp_path, SMALL)


def test_upstream_entry_and_h2_paths_cannot_change(tmp_path: Path) -> None:
    rows = calendar_rows()
    dates, calendar = planner.validate_calendar(rows, rows[:6], rows[6:], SMALL)
    h1, q3, bridge = artificial_bundle(tmp_path)
    bridge[0]["entry_path"] = str(planner.nominal_source_path(tmp_path, "SPY", "20260702", "20260630"))
    with pytest.raises(planner.PlanError, match="entry path altered"):
        planner.build_entry_plan(h1, q3, bridge, dates, calendar, tmp_path, SMALL)
    h1, q3, bridge = artificial_bundle(tmp_path)
    bridge[0]["exit_path"] = str(planner.nominal_source_path(tmp_path, "SPY", "20260702", "20260630"))
    with pytest.raises(planner.PlanError, match="H2 path altered"):
        planner.build_entry_plan(h1, q3, bridge, dates, calendar, tmp_path, SMALL)


def test_conflicting_historical_bindings_after_normalization_fail(tmp_path: Path) -> None:
    path = planner.nominal_source_path(tmp_path, "SPY", "20260702", "20260629")
    first = historical_row(path, size=10)
    second = historical_row(path, size=11)
    with pytest.raises(planner.PlanError, match="conflicting historical"):
        planner.collect_historical_bindings((("H1", [first]), ("Q3", [second])), tmp_path)


def test_intermediate_absence_is_new_metadata_not_reselection(tmp_path: Path) -> None:
    plans, calendar = plans_and_calendar(tmp_path)
    entry = planner.nominal_source_path(tmp_path, "SPY", "20260702", "20260629")
    bindings = planner.collect_historical_bindings((("H1", [historical_row(entry, size=10)]),), tmp_path)
    records = planner.source_records(plans, calendar, tmp_path, bindings, SMALL)
    assert sum(len(row["references"]) for row in records) == 18
    intermediate = next(row for row in records if row["ticker"] == "SPY" and row["trade_date"] == "20260630" and row["expiration"] == "20260702")
    assert intermediate["new_without_upstream_binding"] is True
    assert intermediate["expected_upstream_bindings"] == []


def test_presence_and_size_changes_are_only_diagnostics() -> None:
    present = {"exists": True, "bytes": 11, "mtime_ns": 1, "physical_id": [1, 2]}
    absent = {"exists": False, "bytes": None, "mtime_ns": None, "physical_id": None}
    inventoried = [{"status": "INVENTORIED", "bytes": 10}]
    missing = [{"status": "MISSING_SOURCE", "bytes": None}]
    assert planner.discrepancy_codes(inventoried, present) == ["CURRENT_BYTES_DIFFER_FROM_EXPECTED_UPSTREAM"]
    assert planner.discrepancy_codes(inventoried, absent) == ["EXPECTED_PRESENT_NOW_MISSING"]
    assert planner.discrepancy_codes(missing, present) == ["EXPECTED_MISSING_NOW_PRESENT"]


def test_traversal_and_bad_template_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(planner.PlanError, match="traversal|template"):
        planner.parse_nominal_source(tmp_path / ".." / "escape.parquet", tmp_path)
    with pytest.raises(planner.PlanError, match="template"):
        planner.parse_nominal_source(tmp_path / "data_options" / "SPY" / "bad.parquet", tmp_path)


def test_traversal_normalizing_to_valid_path_is_rejected_by_all_routes(tmp_path: Path) -> None:
    nominal = planner.nominal_source_path(tmp_path, "SPY", "20260702", "20260629")
    disguised = nominal.parent / "discard" / ".." / nominal.name
    with pytest.raises(planner.PlanError, match="lexical traversal"):
        planner.parse_nominal_source(disguised, tmp_path)
    with pytest.raises(planner.PlanError, match="lexical traversal"):
        planner.collect_historical_bindings(
            (("H1", [historical_row(disguised, size=10)]),), tmp_path
        )
    with pytest.raises(planner.PlanError, match="lexical traversal"):
        planner.inspect_nominal_path(disguised, tmp_path, planner.RealStatAdapter())

    rows = calendar_rows()
    dates, calendar = planner.validate_calendar(rows, rows[:6], rows[6:], SMALL)
    h1, q3, bridge = artificial_bundle(tmp_path)
    bridge[0]["entry_path"] = str(disguised)
    with pytest.raises(planner.PlanError, match="lexical traversal"):
        planner.build_entry_plan(h1, q3, bridge, dates, calendar, tmp_path, SMALL)


def test_symlink_or_reparse_ancestor_is_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "data_options"
    try:
        alias.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    path = planner.nominal_source_path(tmp_path, "SPY", "20260702", "20260629")
    with pytest.raises(planner.PlanError, match="link/reparse"):
        planner.inspect_nominal_path(path, tmp_path, planner.RealStatAdapter())


def test_deterministic_reparse_and_nonregular_guards(tmp_path: Path) -> None:
    target = planner.nominal_source_path(tmp_path, "SPY", "20260702", "20260629")

    class FakeStatAdapter:
        def __init__(self, *, reparse: Path | None = None, nonregular: Path | None = None):
            self.reparse = reparse
            self.nonregular = nonregular

        def lstat(self, path: Path) -> SimpleNamespace:
            mode = stat.S_IFDIR | 0o755
            if path == target:
                mode = stat.S_IFREG | 0o644
            if path == self.nonregular:
                mode = stat.S_IFDIR | 0o755
            attributes = planner.REPARSE_FLAG if path == self.reparse else 0
            return SimpleNamespace(
                st_mode=mode,
                st_file_attributes=attributes,
                st_size=10,
                st_mtime_ns=20,
                st_dev=1,
                st_ino=2,
            )

    with pytest.raises(planner.PlanError, match="link/reparse"):
        planner.inspect_nominal_path(
            target,
            tmp_path,
            FakeStatAdapter(reparse=tmp_path / "data_options"),
        )
    with pytest.raises(planner.PlanError, match="not a regular file"):
        planner.inspect_nominal_path(
            target,
            tmp_path,
            FakeStatAdapter(nonregular=target),
        )


def test_hardlink_alias_between_nominal_paths_is_rejected(tmp_path: Path) -> None:
    first = planner.nominal_source_path(tmp_path, "SPY", "20260702", "20260629")
    second = planner.nominal_source_path(tmp_path, "SPY", "20260703", "20260629")
    first.parent.mkdir(parents=True)
    first.write_bytes(b"metadata only")
    try:
        os.link(first, second)
    except OSError:
        pytest.skip("hardlinks unavailable")
    records = [
        {"path": str(path), "expected_upstream_bindings": []}
        for path in (first, second)
    ]
    with pytest.raises(planner.PlanError, match="alias the same physical"):
        planner.inspect_sources(records, tmp_path, planner.RealStatAdapter())


def test_stat_change_at_close_fails_closed() -> None:
    before = [{"path": "a", "observation": {"exists": True, "bytes": 1}}]
    after = [{"path": "a", "observation": {"exists": True, "bytes": 2}}]
    with pytest.raises(planner.PlanError, match="stat changed"):
        planner.require_stable_sources(before, after)


def test_output_pin_names_final_path_while_hashing_staging(tmp_path: Path) -> None:
    staging = tmp_path / "stage.json"
    staging.write_bytes(b"payload")
    final = tmp_path / "final" / "summary.json"
    pin = planner.compact_pin(staging, final)
    assert pin == {
        "path": str(final),
        "bytes": 7,
        "sha256": "239f59ed55e737c77147cf55ad0c1b030b6d7ee748a7426952f9b852d5a935e5",
    }


def test_market_content_open_is_forbidden_during_inspection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = planner.nominal_source_path(tmp_path, "SPY", "20260702", "20260629")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"must never be read")
    original_open = Path.open

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self.suffix == ".parquet":
            raise AssertionError("market content opened")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(builtins, "open", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("open called")))
    observation = planner.inspect_nominal_path(path, tmp_path, planner.RealStatAdapter())
    assert observation["exists"] is True and observation["bytes"] == len(b"must never be read")


def test_source_code_has_no_market_value_library_or_market_read_call() -> None:
    source = Path(planner.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not ({"pyarrow", "pandas", "numpy", "polars", "sklearn"} & imported)
    assert "read_parquet" not in source and "np.load" not in source
    assert "--execute-reviewed-plan" in source
    assert "--builder-sha256" in source and "--tests-sha256" in source and "--contract-sha256" in source
