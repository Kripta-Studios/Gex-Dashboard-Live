from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import weekly_multiday_source_pilot as pilot


def nominal(root: Path, ticker: str = "SPY", entry: str = "20250404", expiration: str = "20250411", trade: str = "20250404") -> pilot.NominalFile:
    session = next(s for e, x, sessions in pilot.CHAINS if e == entry and x == expiration for s in sessions if s == trade)
    index = next(i for i, value in enumerate(next(sessions for e, x, sessions in pilot.CHAINS if e == entry and x == expiration)) if value == session)
    path = root / "data_options" / ticker / "greeks" / trade[:4] / trade[4:6] / f"{ticker}_{expiration}_{trade}_greeks.parquet"
    return pilot.NominalFile(ticker, entry, expiration, trade, index, path)


def write_rows(row: pilot.NominalFile, rows: list[dict], *, proxy: bool = False, extra: dict | None = None) -> None:
    row.path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for item in rows:
        clock = item.pop("clock")
        record = {
            "symbol": row.ticker,
            "expiration": row.expiration,
            "trade_date": row.trade_date,
            "strike": 5000.0,
            "right": "CALL",
            "interval_used": "1m",
            "bid": 1.0,
            "ask": 1.2,
            ("underlying_timestamp" if proxy else "timestamp"): f"{row.trade_date[:4]}-{row.trade_date[4:6]}-{row.trade_date[6:]}T{clock}:00",
        }
        record.update(item)
        if extra:
            record.update(extra)
        payload.append(record)
    pq.write_table(pa.Table.from_pylist(payload), row.path)


def inspect_one(root: Path, row: pilot.NominalFile):
    expected = {Path(os.path.abspath(item.path)) for item in pilot.nominal_files(root)}
    return pilot.inspect_file(row, root, expected)


def test_calendar_holiday_and_missing_are_not_shifted(tmp_path: Path) -> None:
    rows = pilot.nominal_files(tmp_path)
    chain = [r.trade_date for r in rows if r.ticker == "SPY" and r.entry_date == "20250417"]
    assert chain == ["20250417", "20250421", "20250422", "20250423", "20250424", "20250425"]
    diagnostic = pilot.build_diagnostic(tmp_path)
    gap = next(r for r in diagnostic["inventory"] if r["ticker"] == "SPY" and r["entry_date"] == "20250417" and r["trade_date"] == "20250421")
    assert gap["status"] == "MISSING_SOURCE"
    assert diagnostic["nominal_file_count"] == 69


def test_exact_contract_intersection_no_expiry_rollover_and_dte_zero_allowed(tmp_path: Path) -> None:
    entry = nominal(tmp_path)
    later = nominal(tmp_path, trade="20250407")
    expiry = nominal(tmp_path, trade="20250411")
    write_rows(entry, [{"clock": "10:35"}])
    write_rows(later, [{"clock": "10:35", "strike": 5000.0}, {"clock": "09:30", "strike": 5001.0}])
    write_rows(expiry, [{"clock": "10:35"}])
    diagnostic = pilot.build_diagnostic(tmp_path)
    match = next(r for r in diagnostic["intersections"] if r["ticker"] == "SPY" and r["entry_date"] == "20250404" and r["session_date"] == "20250407" and r["clock_et"] == "10:35")
    assert match["same_contract_identity_count"] == 1
    exit_row = next(r for r in diagnostic["intersections"] if r["ticker"] == "SPY" and r["entry_date"] == "20250404" and r["session_date"] == "20250411" and r["clock_et"] == "10:35")
    assert exit_row["dte_calendar"] == 0
    wrong_expiry = nominal(tmp_path, trade="20250408")
    wrong_expiry.path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist([{"symbol": "SPY", "expiration": "20250417", "trade_date": "20250408", "strike": 5000.0, "right": "CALL", "timestamp": "2025-04-08T10:35:00", "bid": 1.0, "ask": 1.2}]), wrong_expiry.path)
    with pytest.raises(pilot.AdmissionError, match="row date identity"):
        inspect_one(tmp_path, wrong_expiry)


def test_native_proxy_classification_and_clock_contract(tmp_path: Path) -> None:
    native = nominal(tmp_path)
    write_rows(native, [{"clock": "10:35"}], extra={"underlying_timestamp": "2025-04-04T10:34:00"})
    result, _, _ = inspect_one(tmp_path, native)
    assert result["clock_basis"] == "NATIVE_STORED_TIMESTAMP"
    assert result["native_underlying_clock_difference_count"] == 1
    assert result["staleness_assessed"] is False and result["quote_age_claimed"] is False
    proxy = nominal(tmp_path, trade="20250407")
    write_rows(proxy, [{"clock": "10:35"}], proxy=True)
    result, _, _ = inspect_one(tmp_path, proxy)
    assert result["clock_basis"] == "UNDERLYING_TIMESTAMP_PROXY"
    assert "not_quote_clock_or_observed_reception" in result["clock_basis_scope"]
    assert pilot._parse_clock(datetime(2025, 4, 4, 14, 35, tzinfo=timezone.utc), "20250404") == "10:35"
    with pytest.raises(pilot.AdmissionError, match="numeric/epoch"):
        pilot._parse_clock(1743777300, "20250404")


def test_missing_is_not_wait_and_invalid_crossed_has_no_age_claim(tmp_path: Path) -> None:
    row = nominal(tmp_path)
    write_rows(row, [{"clock": "10:35", "bid": 2.0, "ask": 1.0}, {"clock": "09:30", "strike": 5001.0, "bid": None}])
    result, contracts, valid = inspect_one(tmp_path, row)
    assert len(contracts["10:35"]) == 1 and len(valid["10:35"]) == 0
    assert result["quote_validity_reasons"] == {"CROSSED": 1, "MISSING_OR_NON_NUMERIC": 1}
    diagnostic = pilot.build_diagnostic(tmp_path)
    missing = next(item for item in diagnostic["inventory"] if item["trade_date"] == "20250407" and item["ticker"] == "SPY" and item["entry_date"] == "20250404")
    assert missing["status"] == "MISSING_SOURCE"
    assert "WAIT" not in json.dumps(diagnostic)


def test_duplicate_identity_snapshot_fails(tmp_path: Path) -> None:
    row = nominal(tmp_path)
    write_rows(row, [{"clock": "10:35"}, {"clock": "10:35"}])
    with pytest.raises(pilot.AdmissionError, match=r"duplicate contract\+snapshot"):
        inspect_one(tmp_path, row)


def test_hash_change_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    row = nominal(tmp_path)
    write_rows(row, [{"clock": "10:35"}])
    real = pilot.sha256_file
    calls = 0
    def changing(path: Path) -> str:
        nonlocal calls
        calls += 1
        value = real(path)
        return value if calls == 1 else "0" * 64
    monkeypatch.setattr(pilot, "sha256_file", changing)
    with pytest.raises(pilot.AdmissionError, match="source changed"):
        inspect_one(tmp_path, row)


def test_paths_and_symlink_guard(tmp_path: Path) -> None:
    row = nominal(tmp_path)
    write_rows(row, [{"clock": "10:35"}])
    expected = {Path(os.path.abspath(item.path)) for item in pilot.nominal_files(tmp_path)}
    with pytest.raises(pilot.AdmissionError, match="not one of"):
        pilot.validate_source_path(tmp_path / "other.parquet", tmp_path, expected)
    link = row.path.with_name("linked.parquet")
    try:
        link.symlink_to(row.path)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(pilot.AdmissionError, match="link/reparse"):
        pilot.validate_source_path(link, tmp_path, {Path(os.path.abspath(link))})


def test_closed_projection_and_output_exclude_economic_fields(tmp_path: Path) -> None:
    row = nominal(tmp_path)
    write_rows(row, [{"clock": "10:35"}], extra={"delta": 0.5, "pnl": 999.0, "label": "future"})
    result, _, _ = inspect_one(tmp_path, row)
    assert not ({"delta", "pnl", "label"} & set(result["projected_columns"]))
    diagnostic = pilot.build_diagnostic(tmp_path)
    text = json.dumps(diagnostic).lower()
    assert '"pnl"' not in text and '"delta"' not in text and '"label"' not in text
    assert diagnostic["flags"]["profitability_evaluated"] is False


def test_inventory_is_metadata_only_and_binds_69_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    row = nominal(tmp_path)
    write_rows(row, [{"clock": "10:35"}], extra={"delta": 0.5, "pnl": 999.0})
    def forbidden(*args, **kwargs):
        raise AssertionError("record batch read during inventory")
    monkeypatch.setattr(pq.ParquetFile, "iter_batches", forbidden)
    inventory = pilot.build_inventory(tmp_path)
    assert inventory["nominal_file_count"] == 69
    admitted = next(item for item in inventory["files"] if item["status"] == "INVENTORIED")
    assert admitted["sha256"] and admitted["row_count_footer"] == 1
    assert not ({"delta", "pnl"} & {field["name"] for field in admitted["projected_schema"]})
    assert sum(item["status"] == "MISSING_SOURCE" for item in inventory["files"]) == 68


def test_value_read_is_bound_to_frozen_inventory(tmp_path: Path) -> None:
    row = nominal(tmp_path)
    write_rows(row, [{"clock": "10:35"}])
    inventory = pilot.build_inventory(tmp_path)
    write_rows(row, [{"clock": "10:35", "strike": 5001.0}])
    with pytest.raises(pilot.AdmissionError, match="differs from frozen inventory before batch"):
        pilot.build_diagnostic(tmp_path, frozen_inventory=inventory)


def test_frozen_admission_rejects_before_first_batch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    row = nominal(tmp_path)
    write_rows(row, [{"clock": "10:35"}])
    inventory = pilot.build_inventory(tmp_path)
    write_rows(row, [{"clock": "10:35", "strike": 5001.0}])
    def forbidden(*args, **kwargs):
        raise AssertionError("iter_batches reached before frozen admission")
    monkeypatch.setattr(pq.ParquetFile, "iter_batches", forbidden)
    with pytest.raises(pilot.AdmissionError, match="before batch read"):
        pilot.build_diagnostic(tmp_path, frozen_inventory=inventory)


def test_frozen_missing_and_present_status_cannot_change(tmp_path: Path) -> None:
    row = nominal(tmp_path)
    missing_inventory = pilot.build_inventory(tmp_path)
    write_rows(row, [{"clock": "10:35"}])
    with pytest.raises(pilot.AdmissionError, match="appeared after frozen"):
        pilot.build_diagnostic(tmp_path, frozen_inventory=missing_inventory)
    present_inventory = pilot.build_inventory(tmp_path)
    row.path.unlink()
    with pytest.raises(pilot.AdmissionError, match="disappeared after frozen"):
        pilot.build_diagnostic(tmp_path, frozen_inventory=present_inventory)


def test_quote_validity_rejects_strings_and_bools() -> None:
    assert pilot._valid_quote("1.0", 1.2) == (False, "NON_NUMERIC_TYPE")
    assert pilot._valid_quote(True, 1.2) == (False, "NON_NUMERIC_TYPE")
    assert pilot._valid_quote(1, 1.2) == (True, "VALID")


def test_happy_path_two_phase_api_writes_bound_final_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    output_dir = tmp_path / "results" / "source_pilot_01"
    row = nominal(source_root)
    write_rows(row, [{"clock": "10:35"}])
    monkeypatch.setattr(pilot, "REAL_SOURCE_ROOT", source_root)
    monkeypatch.setattr(pilot, "REAL_OUTPUT", output_dir)

    pilot.build_real_inventory(source_root, output_dir)
    inventory_path = output_dir / "inventory.json"
    inventory_sha = pilot.sha256_file(inventory_path)
    pilot.run_real(source_root, output_dir, inventory_path, inventory_sha)

    diagnostic = json.loads((output_dir / "diagnostic.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "final_manifest.json").read_text(encoding="utf-8"))
    assert diagnostic["status"] == pilot.STATUS
    assert diagnostic["clock_policy"]["forward_fill"] is False
    assert manifest["inventory_bound_sha256"] == inventory_sha
    assert manifest["closing_inventory_matches_frozen"] is True
    assert set(manifest["implementation_pins"]) == {"weekly_multiday_source_pilot.py", "SOURCE_PILOT_CONTRACT.md"}


def test_real_run_controls_reject_other_roots_and_outputs(tmp_path: Path) -> None:
    with pytest.raises(pilot.AdmissionError, match="source root"):
        pilot.run_real(tmp_path, pilot.REAL_OUTPUT, tmp_path / "inventory.json", "0" * 64)
    with pytest.raises(pilot.AdmissionError, match="output"):
        pilot.run_real(pilot.REAL_SOURCE_ROOT, tmp_path / "out", tmp_path / "inventory.json", "0" * 64)
