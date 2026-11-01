from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import build_weekly_h2_boundary_bridge as bridge


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _weekdays_ending(end: date, count: int) -> list[str]:
    values: list[str] = []
    current = end
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current.strftime("%Y%m%d"))
        current -= timedelta(days=1)
    return sorted(values)


def _weekdays_starting(start: date, count: int) -> list[str]:
    values: list[str] = []
    current = start
    while len(values) < count:
        if current.weekday() < 5 and current not in {date(2026, 7, 3), date(2026, 9, 7)}:
            values.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return values


def _write_authority(root: Path, schema: str, dates: list[str], candidate_count: int, *, h1: bool) -> None:
    root.mkdir()
    calendar = [{"ticker": ticker, "date": day, "close_i": 390} for ticker in bridge.TICKERS for day in dates]
    rows = []
    eligible_indexes: list[int] = []
    for ticker in bridge.TICKERS:
        for day in dates:
            row = {
                "ticker": ticker, "entry_date": day, "exit_date": None, "expiration": None,
                "status": "OTHER", "reason": None, "candidate_ids": [], "entry_path": None, "exit_path": None,
            }
            if h1 and day in bridge.ENTRY_DATES:
                row.update(status="HORIZON_OUTSIDE_CALENDAR", reason="NO_OFFICIAL_H2")
            else:
                eligible_indexes.append(len(rows))
            rows.append(row)
    prefix = "H" if h1 else "Q"
    ids = [f"{prefix}:{index:04d}" for index in range(candidate_count)]
    for index, candidate_id in enumerate(ids):
        rows[eligible_indexes[index % len(eligible_indexes)]]["candidate_ids"].append(candidate_id)
    coverage = {"schema": schema, "calendar": calendar, "rows": rows}
    (root / "coverage.json").write_text(json.dumps(coverage, sort_keys=True) + "\n", encoding="utf-8")
    (root / "candidates.jsonl").write_text("".join(json.dumps({"candidate_id": value}) + "\n" for value in ids), encoding="utf-8")
    manifest = {
        "files": {
            name: {"bytes": (root / name).stat().st_size, "sha256": _sha(root / name)}
            for name in ("coverage.json", "candidates.jsonl")
        }
    }
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")


def _greek_file(path: Path, ticker: str, day: str, *, exit_file: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for clock in ("10:30:00", "10:35:00"):
        for right, delta in (("CALL", 0.5), ("PUT", -0.5)):
            rows.append(
                {
                    "symbol": ticker, "expiration": "20260702", "trade_date": day,
                    "strike": 100.0, "right": right, "timestamp": f"{day[:4]}-{day[4:6]}-{day[6:]}T{clock}",
                    "underlying_price": 100.0, "bid": 2.0 if exit_file else 1.0,
                    "ask": 2.1 if exit_file else (1.2 if clock == "10:35:00" else 1.1),
                    "delta": delta, "implied_vol": 0.2, "gamma": 0.01, "theta": -0.02,
                    "vega": 0.03, "rho": 0.01,
                }
            )
    pq.write_table(pa.Table.from_pylist(rows), path)


@pytest.fixture
def environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    h1, q3 = tmp_path / "h1", tmp_path / "q3"
    h1_dates = _weekdays_ending(date(2026, 6, 30), 875)
    q3_dates = _weekdays_starting(date(2026, 7, 1), 55)
    assert h1_dates[-2:] == list(bridge.ENTRY_DATES)
    assert q3_dates[:2] == list(bridge.SEGMENT_DATES[2:])
    _write_authority(h1, "weekly_h2_coverage_v2", h1_dates, 3054, h1=True)
    _write_authority(q3, "weekly_h2_q3_partial_coverage_v1", q3_dates, 180, h1=False)
    monkeypatch.setattr(bridge, "H1_MANIFEST_SHA256", _sha(h1 / "manifest.json"))
    monkeypatch.setattr(bridge, "Q3_MANIFEST_SHA256", _sha(q3 / "manifest.json"))
    source = tmp_path / "source"
    source.mkdir()
    for ticker in bridge.TICKERS:
        _greek_file(
            source / "data_options" / ticker / "greeks" / "2026" / "06" / f"{ticker}_20260702_20260629_greeks.parquet",
            ticker, "20260629",
        )
    _greek_file(
        source / "data_options" / "SPXW" / "greeks" / "2026" / "07" / "SPXW_20260702_20260701_greeks.parquet",
        "SPXW", "20260701", exit_file=True,
    )
    return {"source": source, "h1": h1, "q3": q3, "output": tmp_path / "bridge"}


def _wrapper_sha() -> str:
    return _sha(Path(bridge.__file__))


def test_inventory_exact_six_plan_four_present_two_missing(environment: dict[str, Path]) -> None:
    receipt = bridge.build_reviewed_inventory(
        environment["source"], environment["h1"], environment["q3"], environment["output"], _wrapper_sha()
    )
    inventory_path = environment["output"] / "inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    assert receipt["schema"] == "weekly_h2_boundary_bridge_inventory_manifest_v1"
    assert inventory["unified_calendar"]["rows"] == 2790
    assert len(inventory["segment_calendar"]) == 12
    assert len(inventory["coverage_plan"]) == 6
    assert len(inventory["sources"]) == 6
    assert sum(row["status"] == "INVENTORIED" for row in inventory["sources"]) == 4
    assert sum(row["status"] == "MISSING_SOURCE" for row in inventory["sources"]) == 2
    june30 = [row for row in inventory["coverage_plan"] if row["entry_date"] == "20260630"]
    assert len(june30) == 3 and all(row["status"] == "NO_SERIES" for row in june30)
    assert all("20260702_20260702" not in row["path"] for row in inventory["sources"])


def test_end_to_end_overlay_preserves_originals_and_missing_exit_lower_bounds(environment: dict[str, Path]) -> None:
    original_pins = {
        path: _sha(path)
        for root in (environment["h1"], environment["q3"])
        for path in root.iterdir()
    }
    bridge.build_reviewed_inventory(
        environment["source"], environment["h1"], environment["q3"], environment["output"], _wrapper_sha()
    )
    inventory = environment["output"] / "inventory.json"
    manifest = bridge.execute_reviewed_bridge(
        environment["source"], environment["h1"], environment["q3"], environment["output"],
        _wrapper_sha(), inventory, _sha(inventory),
    )
    overlay = json.loads((environment["output"] / "coverage_overlay.json").read_text(encoding="utf-8"))
    candidates = [json.loads(line) for line in (environment["output"] / "candidates.jsonl").read_text(encoding="utf-8").splitlines()]
    assert manifest["status"] == bridge.STATUS
    assert len(overlay["rows"]) == 6 and len(overlay["replacement_keys"]) == 6
    assert len(candidates) == 6
    assert sum(row["status"] == "MISSING_EXIT_SOURCE" for row in candidates) == 4
    assert sum(row["status"] == "OBSERVED_EXIT" for row in candidates) == 2
    assert all(_sha(path) == digest for path, digest in original_pins.items())
    assert manifest["split"] == bridge.SPLIT
    assert all(set(pin) == {"bytes", "sha256"} for pin in manifest["files"].values())
    assert manifest["flags"] == {
        "fit_performed": False, "economic_evaluation_performed": False,
        "promotion_approved": False, "originals_modified": False,
        "development_seen": True, "not_oos": True,
    }


def test_inventory_tamper_fails_before_candidate_builder(environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    bridge.build_reviewed_inventory(
        environment["source"], environment["h1"], environment["q3"], environment["output"], _wrapper_sha()
    )
    inventory = environment["output"] / "inventory.json"
    frozen_sha = _sha(inventory)
    data = bytearray(inventory.read_bytes())
    data[data.index(b"2790")] = ord("1")
    inventory.write_bytes(data)
    called = False
    original_load = bridge._load_frozen

    def wrapped_load() -> tuple[object, object]:
        nonlocal called
        builder, pilot = original_load()
        monkeypatch.setattr(builder, "build_candidates", lambda *args: (_ for _ in ()).throw(AssertionError("must not run")))
        called = True
        return builder, pilot

    monkeypatch.setattr(bridge, "_load_frozen", wrapped_load)
    with pytest.raises(bridge.BridgeError, match="external SHA binding failed"):
        bridge.execute_reviewed_bridge(
            environment["source"], environment["h1"], environment["q3"], environment["output"],
            _wrapper_sha(), inventory, frozen_sha,
        )
    assert called is True


def test_source_change_between_phases_fails_closed(environment: dict[str, Path]) -> None:
    bridge.build_reviewed_inventory(
        environment["source"], environment["h1"], environment["q3"], environment["output"], _wrapper_sha()
    )
    inventory = environment["output"] / "inventory.json"
    target = environment["source"] / "data_options" / "SPY" / "greeks" / "2026" / "06" / "SPY_20260702_20260629_greeks.parquet"
    target.write_bytes(target.read_bytes() + b"changed")
    with pytest.raises(Exception, match="source changed during inventory|inventory differs|Parquet"):
        bridge.execute_reviewed_bridge(
            environment["source"], environment["h1"], environment["q3"], environment["output"],
            _wrapper_sha(), inventory, _sha(inventory),
        )
    assert not (environment["output"] / "manifest.json").exists()


def test_collision_is_rejected(environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    bridge.build_reviewed_inventory(
        environment["source"], environment["h1"], environment["q3"], environment["output"], _wrapper_sha()
    )
    original_load = bridge._load_frozen

    def colliding_load() -> tuple[object, object]:
        builder, pilot = original_load()
        monkeypatch.setattr(builder, "build_candidates", lambda *args: ([{"candidate_id": "H:0000"}], []))
        return builder, pilot

    monkeypatch.setattr(bridge, "_load_frozen", colliding_load)
    inventory = environment["output"] / "inventory.json"
    with pytest.raises(bridge.BridgeError, match="collides"):
        bridge.execute_reviewed_bridge(
            environment["source"], environment["h1"], environment["q3"], environment["output"],
            _wrapper_sha(), inventory, _sha(inventory),
        )


def test_wrapper_pin_and_occupied_destination_fail(environment: dict[str, Path]) -> None:
    with pytest.raises(bridge.BridgeError, match="wrapper SHA-256 mismatch"):
        bridge.build_reviewed_inventory(
            environment["source"], environment["h1"], environment["q3"], environment["output"], "0" * 64
        )
    environment["output"].mkdir()
    with pytest.raises(bridge.BridgeError, match="immutable output exists"):
        bridge.build_reviewed_inventory(
            environment["source"], environment["h1"], environment["q3"], environment["output"], _wrapper_sha()
        )


def test_clock_v2_exact_and_subminute_semantics() -> None:
    builder, _ = bridge._load_frozen()
    assert builder._parse_clock_v2("2026-06-29T10:30", "20260629") == ("10:30", False)
    assert builder._parse_clock_v2("2026-06-29T10:35:00.0000001", "20260629") == (None, True)


def test_unresolved_reparse_guard_detects_ancestor(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "module.py").write_text("value = 1\n", encoding="utf-8")
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    assert bridge._is_link_or_reparse_unresolved(alias / "module.py") is True
