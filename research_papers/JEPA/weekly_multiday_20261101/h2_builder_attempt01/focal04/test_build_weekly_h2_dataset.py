from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import build_weekly_h2_dataset as builder


PILOT = Path(__file__).resolve().with_name("weekly_multiday_source_pilot.py")


def write_calendar(path: Path, dates: list[str]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"ticker": ticker, "date": day, "close_i": 390, "status": "COMPLETE"} for ticker in builder.TICKERS for day in dates]
    pq.write_table(pa.Table.from_pylist(rows), path)
    return builder.sha256_file(path)


def source_path(root: Path, ticker: str, expiration: str, day: str) -> Path:
    return root / "data_options" / ticker / "greeks" / day[:4] / day[4:6] / f"{ticker}_{expiration}_{day}_greeks.parquet"


def quote(ticker: str, expiration: str, day: str, clock: str, strike: float, right: str, bid: float, ask: float, delta: float) -> dict:
    return {
        "symbol": ticker, "expiration": expiration, "trade_date": day,
        "timestamp": f"{day[:4]}-{day[4:6]}-{day[6:]}T{clock}:00", "interval_used": "1m",
        "underlying_price": 500.0, "strike": strike, "right": right, "bid": bid, "ask": ask,
        "delta": delta, "implied_vol": 0.2, "gamma": 0.01, "theta": -0.02, "vega": 0.1, "rho": 0.03,
    }


def write_source(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)


def build_fixture(tmp_path: Path, *, exit_mode: str = "OBSERVED", execution_ask: float = 2.1):
    source, calendar = tmp_path / "source", tmp_path / "calendar.parquet"
    dates, expiration = ["20250106", "20250107", "20250108", "20250109"], "20250110"
    calendar_sha = write_calendar(calendar, dates)
    entry = source_path(source, "SPY", expiration, dates[0])
    write_source(entry, [
        quote("SPY", expiration, dates[0], "10:30", 500.0, "CALL", 1.8, 2.0, 0.50),
        quote("SPY", expiration, dates[0], "10:30", 501.0, "CALL", 1.7, 1.9, 0.50),
        quote("SPY", expiration, dates[0], "10:30", 500.0, "PUT", 1.9, 2.0, -0.50),
        quote("SPY", expiration, dates[0], "10:35", 500.0, "CALL", 1.9, execution_ask, 0.49),
        quote("SPY", expiration, dates[0], "10:35", 500.0, "PUT", 1.8, execution_ask, -0.49),
        quote("SPY", expiration, dates[0], "12:00", 500.0, "CALL", 999.0, 999.0, 0.1),
    ])
    exit_path = source_path(source, "SPY", expiration, dates[2])
    if exit_mode != "MISSING_SOURCE":
        rows = [
            quote("SPY", expiration, dates[2], "10:35", 500.0, "CALL", 2.8, 3.0, 0.6),
            quote("SPY", expiration, dates[2], "10:35", 500.0, "PUT", 1.0, 1.2, -0.3),
        ]
        if exit_mode == "MISSING_QUOTE":
            rows = [quote("SPY", expiration, dates[2], "09:30", 500.0, "CALL", 2.8, 3.0, 0.6)]
        write_source(exit_path, rows)
    output = tmp_path / "output"
    manifest = builder.build_dataset(source, calendar, calendar_sha, output, pilot_path=PILOT, pilot_sha256=builder.PILOT_SHA256)
    candidates = [json.loads(line) for line in (output / "candidates.jsonl").read_text(encoding="utf-8").splitlines()]
    coverage = json.loads((output / "coverage.json").read_text(encoding="utf-8"))
    return output, manifest, candidates, coverage


def test_observed_interface_selector_and_manifest_pins(tmp_path: Path) -> None:
    output, manifest, candidates, coverage = build_fixture(tmp_path)
    assert [row["right"] for row in candidates] == ["CALL", "PUT"]
    call = candidates[0]
    assert call["strike"] == 500.0
    assert tuple(call["features"]) == builder.FEATURE_KEYS
    assert call["status"] == "OBSERVED_EXIT" and call["scenario"] == 4
    assert call["payoff_is_lower_bound"] is False
    assert call["label_available_at"].startswith("2025-01-08T10:35:00")
    assert call["source_pins"]["calendar_sha256"] == manifest["calendar"]["sha256"]
    assert manifest["status"] == builder.STATUS
    assert manifest["inventory_bound_sha256"] == builder.sha256_file(output / "inventory.json")
    assert builder.CONTRACT_SHA256 == "245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5"
    assert manifest["implementation_pins"]["ECONOMIC_H2_CONTRACT.md"] == builder.CONTRACT_SHA256
    for name in ("candidates.jsonl", "coverage.json", "inventory.json"):
        assert builder.sha256_file(output / name) == manifest["files"][name]["sha256"]
    row = next(item for item in coverage["rows"] if item["ticker"] == "SPY" and item["entry_date"] == "20250106")
    assert row["exit_date"] == "20250108" and len(row["candidate_ids"]) == 2


def test_nofill_is_zero_and_available_at_entry(tmp_path: Path) -> None:
    _, _, candidates, _ = build_fixture(tmp_path, execution_ask=50.0)
    assert all(row["status"] == "NO_FILL" and row["scenario"] == 0 for row in candidates)
    assert all(row["net_base"] == 0 and row["entry_debit_base"] == 0 for row in candidates)
    assert all(row["label_available_at"].startswith("2025-01-06T10:35:00") for row in candidates)


@pytest.mark.parametrize("mode,status", [("MISSING_SOURCE", "MISSING_EXIT_SOURCE"), ("MISSING_QUOTE", "MISSING_EXIT_QUOTE")])
def test_missing_exit_retained_as_scenario1_lower_bound(tmp_path: Path, mode: str, status: str) -> None:
    _, _, candidates, _ = build_fixture(tmp_path, exit_mode=mode)
    assert all(row["status"] == status and row["scenario"] == 1 and row["exit_bid"] is None for row in candidates)
    assert all(row["payoff_is_lower_bound"] is True and row["label_available_at"].startswith("2025-01-08T10:35:00") for row in candidates)
    assert all(row["net_base"] < 0 and row["entry_debit_base"] > 0 for row in candidates)


def test_h2_preexpiry_and_calendar_end_are_not_shifted(tmp_path: Path) -> None:
    source, calendar = tmp_path / "source", tmp_path / "calendar.parquet"
    dates = ["20250106", "20250107", "20250108"]
    calendar_sha = write_calendar(calendar, dates)
    write_source(source_path(source, "SPY", "20250108", dates[0]), [quote("SPY", "20250108", dates[0], "10:30", 500, "CALL", 1, 1.2, 0.5)])
    output = tmp_path / "output"
    builder.build_dataset(source, calendar, calendar_sha, output, pilot_path=PILOT, pilot_sha256=builder.PILOT_SHA256)
    coverage = json.loads((output / "coverage.json").read_text(encoding="utf-8"))["rows"]
    first = next(row for row in coverage if row["ticker"] == "SPY" and row["entry_date"] == dates[0])
    assert first["status"] == "NO_SERIES"
    assert all(row["status"] == "HORIZON_OUTSIDE_CALENDAR" for row in coverage if row["entry_date"] in dates[-2:])


def test_duplicate_used_snapshot_is_fatal(tmp_path: Path) -> None:
    source, calendar = tmp_path / "source", tmp_path / "calendar.parquet"
    dates = ["20250106", "20250107", "20250108"]
    calendar_sha = write_calendar(calendar, dates)
    row = quote("SPY", "20250110", dates[0], "10:30", 500, "CALL", 1, 1.2, 0.5)
    write_source(source_path(source, "SPY", "20250110", dates[0]), [row, dict(row)])
    with pytest.raises(builder.DatasetError, match="duplicate contract snapshot"):
        builder.build_dataset(source, calendar, calendar_sha, tmp_path / "output", pilot_path=PILOT, pilot_sha256=builder.PILOT_SHA256)


def test_calendar_and_helper_pins_fail_closed(tmp_path: Path) -> None:
    calendar = tmp_path / "calendar.parquet"
    calendar_sha = write_calendar(calendar, ["20250106", "20250107", "20250108"])
    with pytest.raises(builder.DatasetError, match="calendar SHA"):
        builder.build_dataset(tmp_path / "source", calendar, "0" * 64, tmp_path / "out1", pilot_path=PILOT, pilot_sha256=builder.PILOT_SHA256)
    with pytest.raises(builder.DatasetError, match="helper pin"):
        builder.build_dataset(tmp_path / "source", calendar, calendar_sha, tmp_path / "out2", pilot_path=PILOT, pilot_sha256="0" * 64)


def test_persisted_inventory_precedes_values_and_survives_failure(tmp_path: Path) -> None:
    source, calendar, output = tmp_path / "source", tmp_path / "calendar.parquet", tmp_path / "output"
    dates, expiration = ["20250106", "20250107", "20250108"], "20250110"
    calendar_sha = write_calendar(calendar, dates)
    bad = quote("SPY", expiration, dates[0], "10:30", 500, "CALL", 1, 1.2, 0.5)
    bad["timestamp"] = "not-a-clock"
    write_source(source_path(source, "SPY", expiration, dates[0]), [bad])
    builder.build_reviewed_inventory(source, calendar, calendar_sha, output, pilot_path=PILOT, pilot_sha256=builder.PILOT_SHA256)
    inventory = output / "inventory.json"
    with pytest.raises(Exception, match="clock|ISO"):
        builder.execute_reviewed_builder(source, calendar, calendar_sha, output, inventory, builder.sha256_file(inventory), pilot_path=PILOT, pilot_sha256=builder.PILOT_SHA256)
    assert inventory.is_file() and (output / "inventory_manifest.json").is_file()
    assert not (output / "candidates.jsonl").exists()


def test_plan_change_rejected_before_value_read(tmp_path: Path) -> None:
    source, calendar, output = tmp_path / "source", tmp_path / "calendar.parquet", tmp_path / "output"
    dates = ["20250106", "20250107", "20250108"]
    calendar_sha = write_calendar(calendar, dates)
    write_source(source_path(source, "SPY", "20250110", dates[0]), [quote("SPY", "20250110", dates[0], "10:30", 500, "CALL", 1, 1.2, 0.5)])
    builder.build_reviewed_inventory(source, calendar, calendar_sha, output, pilot_path=PILOT, pilot_sha256=builder.PILOT_SHA256)
    inventory = output / "inventory.json"
    write_source(source_path(source, "SPY", "20250109", dates[0]), [quote("SPY", "20250109", dates[0], "10:30", 500, "CALL", 1, 1.2, 0.5)])
    with pytest.raises(builder.DatasetError, match="differs before first value"):
        builder.execute_reviewed_builder(source, calendar, calendar_sha, output, inventory, builder.sha256_file(inventory), pilot_path=PILOT, pilot_sha256=builder.PILOT_SHA256)


def test_decimal_arrow_values_are_admitted_end_to_end(tmp_path: Path) -> None:
    source, calendar, output = tmp_path / "source", tmp_path / "calendar.parquet", tmp_path / "output"
    dates, expiration = ["20250106", "20250107", "20250108"], "20250110"
    calendar_sha = write_calendar(calendar, dates)
    entry_rows = []
    for clock in ("10:30", "10:35"):
        row = quote("SPY", expiration, dates[0], clock, 500, "CALL", 1, 1.2, 0.5)
        for key in ("underlying_price", "strike", "bid", "ask", "delta", "implied_vol", "gamma", "theta", "vega", "rho"):
            row[key] = Decimal(str(row[key]))
        entry_rows.append(row)
    exit_row = quote("SPY", expiration, dates[2], "10:35", 500, "CALL", 2, 2.2, 0.6)
    for key in ("underlying_price", "strike", "bid", "ask", "delta", "implied_vol", "gamma", "theta", "vega", "rho"):
        exit_row[key] = Decimal(str(exit_row[key]))
    write_source(source_path(source, "SPY", expiration, dates[0]), entry_rows)
    write_source(source_path(source, "SPY", expiration, dates[2]), [exit_row])
    builder.build_dataset(source, calendar, calendar_sha, output, pilot_path=PILOT, pilot_sha256=builder.PILOT_SHA256)
    candidate = json.loads((output / "candidates.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert candidate["status"] == "OBSERVED_EXIT" and candidate["features"]["delta"] == 0.5
