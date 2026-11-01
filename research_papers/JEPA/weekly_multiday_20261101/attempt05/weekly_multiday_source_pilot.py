from __future__ import annotations

import argparse
import hashlib
import json
import math
import numbers
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq


TICKERS = ("SPY", "QQQ", "SPXW")
CLOCKS = ("09:30", "10:30", "10:35", "15:55")
NY = ZoneInfo("America/New_York")
REAL_SOURCE_ROOT = Path(r"D:\ThetaData")
REAL_OUTPUT = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101\source_pilot_01")
STATUS = "COMPLETE_SOURCE_DIAGNOSTIC_NOT_ECONOMIC_EVALUATION"
CHAINS = (
    ("20250404", "20250411", ("20250404", "20250407", "20250408", "20250409", "20250410", "20250411")),
    ("20250411", "20250417", ("20250411", "20250414", "20250415", "20250416", "20250417")),
    ("20250417", "20250425", ("20250417", "20250421", "20250422", "20250423", "20250424", "20250425")),
    ("20250425", "20250502", ("20250425", "20250428", "20250429", "20250430", "20250501", "20250502")),
)
BASE_COLUMNS = ("symbol", "expiration", "trade_date", "strike", "right")
OPTIONAL_COLUMNS = ("timestamp", "underlying_timestamp", "interval_used", "bid", "ask")
FORBIDDEN_OUTPUT_TOKENS = ("pnl", "profit", "return", "delta", "label", "fill", "side_selection")


class AdmissionError(RuntimeError):
    pass


@dataclass(frozen=True)
class NominalFile:
    ticker: str
    entry_date: str
    expiration: str
    trade_date: str
    session_index: int
    path: Path

    @property
    def identifier(self) -> str:
        return f"{self.ticker}:{self.entry_date}:{self.expiration}:{self.trade_date}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _yyyymmdd(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    digits = text.replace("-", "")
    if len(digits) == 8 and digits.isdigit():
        datetime.strptime(digits, "%Y%m%d")
        return digits
    raise AdmissionError(f"invalid calendar identity: {value!r}")


def nominal_files(source_root: Path) -> list[NominalFile]:
    rows: list[NominalFile] = []
    for ticker in TICKERS:
        for entry, expiration, sessions in CHAINS:
            for index, trade_date in enumerate(sessions):
                year, month = trade_date[:4], trade_date[4:6]
                name = f"{ticker}_{expiration}_{trade_date}_greeks.parquet"
                path = source_root / "data_options" / ticker / "greeks" / year / month / name
                rows.append(NominalFile(ticker, entry, expiration, trade_date, index, path))
    if len(rows) != 69 or len({str(row.path) for row in rows}) != 69:
        raise AssertionError("the frozen pilot must contain exactly 69 nominal identities")
    return rows


def _is_link_or_reparse(path: Path) -> bool:
    current = Path(os.path.abspath(path))
    while True:
        try:
            info = current.lstat()
        except FileNotFoundError:
            info = None
        if info is not None:
            if stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400):
                return True
        if current.parent == current:
            return False
        current = current.parent


def validate_source_path(path: Path, source_root: Path, expected: set[Path]) -> None:
    absolute = Path(os.path.abspath(path))
    root_absolute = Path(os.path.abspath(source_root))
    if absolute not in expected:
        raise AdmissionError(f"path is not one of the 69 nominal identities: {absolute}")
    if _is_link_or_reparse(absolute):
        raise AdmissionError(f"link/reparse source is forbidden: {absolute}")
    resolved = absolute.resolve(strict=True)
    root_resolved = root_absolute.resolve(strict=True)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise AdmissionError(f"source resolves outside allowed root: {absolute}") from exc
    if not resolved.is_file():
        raise AdmissionError(f"source is not a regular file: {absolute}")


def validate_missing_source_path(path: Path, source_root: Path, expected: set[Path]) -> None:
    absolute = Path(os.path.abspath(path))
    root_absolute = Path(os.path.abspath(source_root))
    if absolute not in expected:
        raise AdmissionError(f"path is not one of the 69 nominal identities: {absolute}")
    try:
        absolute.relative_to(root_absolute)
    except ValueError as exc:
        raise AdmissionError(f"nominal source is outside allowed root: {absolute}") from exc
    if _is_link_or_reparse(absolute):
        raise AdmissionError(f"link/reparse nominal path is forbidden: {absolute}")


def _normalize_right(value: Any) -> str:
    text = str(value).strip().upper()
    mapping = {"C": "CALL", "CALL": "CALL", "P": "PUT", "PUT": "PUT"}
    if text not in mapping:
        raise AdmissionError(f"invalid option right: {value!r}")
    return mapping[text]


def _strike_key(value: Any) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AdmissionError(f"invalid strike: {value!r}") from exc
    if not number.is_finite():
        raise AdmissionError(f"invalid strike: {value!r}")
    return format(number.normalize(), "f")


def _parse_clock(value: Any, trade_date: str) -> str:
    if value is None:
        raise AdmissionError("null snapshot clock")
    if isinstance(value, bool) or isinstance(value, (int, float, Decimal)):
        raise AdmissionError("numeric/epoch snapshot clocks are forbidden")
    if isinstance(value, date) and not isinstance(value, datetime):
        raise AdmissionError("date without time is not a snapshot clock")
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        if "T" not in text and " " not in text:
            raise AdmissionError(f"snapshot clock is not complete ISO: {value!r}")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise AdmissionError(f"invalid ISO snapshot clock: {value!r}") from exc
    else:
        raise AdmissionError(f"unsupported snapshot clock type: {type(value).__name__}")
    local = parsed.replace(tzinfo=NY) if parsed.tzinfo is None else parsed.astimezone(NY)
    if local.strftime("%Y%m%d") != trade_date:
        raise AdmissionError("snapshot clock local date differs from trade_date")
    if local.second or local.microsecond:
        raise AdmissionError("sub-minute snapshot clocks are outside the contract")
    return local.strftime("%H:%M")


def _valid_quote(bid: Any, ask: Any) -> tuple[bool, str]:
    if bid is None or ask is None:
        return False, "MISSING_OR_NON_NUMERIC"
    allowed = (numbers.Real, Decimal)
    if isinstance(bid, bool) or isinstance(ask, bool) or not isinstance(bid, allowed) or not isinstance(ask, allowed):
        return False, "NON_NUMERIC_TYPE"
    bid_number, ask_number = float(bid), float(ask)
    if not math.isfinite(bid_number) or not math.isfinite(ask_number):
        return False, "NON_FINITE"
    if bid_number < 0 or ask_number <= 0:
        return False, "NON_POSITIVE_OR_NEGATIVE"
    if bid_number > ask_number:
        return False, "CROSSED"
    return True, "VALID"


def _schema_descriptor(schema: pa.Schema, projection: Iterable[str]) -> list[dict[str, str]]:
    return [{"name": name, "type": str(schema.field(name).type)} for name in projection]


def build_inventory(source_root: Path) -> dict[str, Any]:
    """Hash and inspect footers only; never iterate a record batch."""
    source_root = Path(os.path.abspath(source_root))
    rows = nominal_files(source_root)
    expected = {Path(os.path.abspath(row.path)) for row in rows}
    files: list[dict[str, Any]] = []
    for row in rows:
        base = {
            "identifier": row.identifier,
            "ticker": row.ticker,
            "entry_date": row.entry_date,
            "expiration": row.expiration,
            "trade_date": row.trade_date,
            "session_index": row.session_index,
            "path": str(row.path),
        }
        if not row.path.exists():
            validate_missing_source_path(row.path, source_root, expected)
            files.append({**base, "status": "MISSING_SOURCE", "size": None, "sha256": None, "row_count_footer": None, "projected_schema": None})
            continue
        validate_source_path(row.path, source_root, expected)
        size_before = row.path.stat().st_size
        sha_before = sha256_file(row.path)
        parquet = pq.ParquetFile(row.path)
        names = set(parquet.schema_arrow.names)
        missing = set(BASE_COLUMNS) - names
        if missing:
            raise AdmissionError(f"missing required columns in {row.identifier}: {sorted(missing)}")
        if "timestamp" not in names and "underlying_timestamp" not in names:
            raise AdmissionError(f"no admitted snapshot clock in {row.identifier}")
        projection = [name for name in (*BASE_COLUMNS, *OPTIONAL_COLUMNS) if name in names]
        size_after = row.path.stat().st_size
        sha_after = sha256_file(row.path)
        if size_before != size_after or sha_before != sha_after:
            raise AdmissionError(f"source changed during inventory: {row.identifier}")
        files.append(
            {
                **base,
                "status": "INVENTORIED",
                "size": size_before,
                "sha256": sha_before,
                "row_count_footer": parquet.metadata.num_rows,
                "projected_schema": _schema_descriptor(parquet.schema_arrow, projection),
                "full_schema_field_count": len(parquet.schema_arrow),
            }
        )
    return {
        "schema": "weekly_multiday_source_inventory_v1",
        "mode": "METADATA_HASHES_ONLY_NO_RECORD_BATCHES",
        "source_root": str(source_root),
        "nominal_file_count": 69,
        "files": files,
    }


def inspect_file(
    row: NominalFile,
    source_root: Path,
    expected: set[Path],
    frozen_row: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, set[tuple[str, str, str, str]]], dict[str, set[tuple[str, str, str, str]]]]:
    validate_source_path(row.path, source_root, expected)
    before_size = row.path.stat().st_size
    before_sha = sha256_file(row.path)
    parquet = pq.ParquetFile(row.path)
    schema = parquet.schema_arrow
    names = set(schema.names)
    missing = set(BASE_COLUMNS) - names
    if missing:
        raise AdmissionError(f"missing required columns in {row.identifier}: {sorted(missing)}")
    if "timestamp" in names:
        clock_column = "timestamp"
        clock_basis = "NATIVE_STORED_TIMESTAMP"
    elif "underlying_timestamp" in names:
        clock_column = "underlying_timestamp"
        clock_basis = "UNDERLYING_TIMESTAMP_PROXY"
    else:
        raise AdmissionError(f"no admitted snapshot clock in {row.identifier}")
    projection = [name for name in (*BASE_COLUMNS, *OPTIONAL_COLUMNS) if name in names]
    if any(any(token in name.lower() for token in FORBIDDEN_OUTPUT_TOKENS) for name in projection):
        raise AssertionError("economic column entered the closed projection")
    projected_schema = _schema_descriptor(schema, projection)
    if frozen_row is not None:
        prebatch_checks = {
            "status": frozen_row.get("status") == "INVENTORIED",
            "size": before_size == frozen_row.get("size"),
            "sha256": before_sha == frozen_row.get("sha256"),
            "row_count_footer": parquet.metadata.num_rows == frozen_row.get("row_count_footer"),
            "projected_schema": projected_schema == frozen_row.get("projected_schema"),
            "full_schema_field_count": len(schema) == frozen_row.get("full_schema_field_count"),
        }
        failed = sorted(name for name, passed in prebatch_checks.items() if not passed)
        if failed:
            raise AdmissionError(f"source differs from frozen inventory before batch read ({','.join(failed)}): {row.identifier}")

    contracts_by_clock = {clock: set() for clock in CLOCKS}
    valid_by_clock = {clock: set() for clock in CLOCKS}
    day_contracts: set[tuple[str, str, str, str]] = set()
    duplicate_guard: set[tuple[tuple[str, str, str, str], str]] = set()
    intervals: dict[str, int] = {}
    quote_reasons: dict[str, int] = {}
    observed_clock_counts: dict[str, int] = {}
    native_underlying_clock_differences = 0
    rows_seen = 0

    for batch in parquet.iter_batches(batch_size=65536, columns=projection, use_threads=False):
        for record in batch.to_pylist():
            rows_seen += 1
            symbol = str(record["symbol"]).strip().upper()
            if symbol != row.ticker:
                raise AdmissionError(f"row symbol differs from nominal ticker in {row.identifier}")
            expiration = _yyyymmdd(record["expiration"])
            trade_date = _yyyymmdd(record["trade_date"])
            if expiration != row.expiration or trade_date != row.trade_date:
                raise AdmissionError(f"row date identity differs from nominal identity in {row.identifier}")
            key = (row.ticker, expiration, _strike_key(record["strike"]), _normalize_right(record["right"]))
            clock = _parse_clock(record[clock_column], row.trade_date)
            duplicate_key = (key, clock)
            if duplicate_key in duplicate_guard:
                raise AdmissionError(f"duplicate contract+snapshot in {row.identifier}")
            duplicate_guard.add(duplicate_key)
            day_contracts.add(key)
            observed_clock_counts[clock] = observed_clock_counts.get(clock, 0) + 1
            if "interval_used" in record:
                interval = "<NULL>" if record["interval_used"] is None else str(record["interval_used"])
                intervals[interval] = intervals.get(interval, 0) + 1
            valid, reason = _valid_quote(record.get("bid"), record.get("ask"))
            quote_reasons[reason] = quote_reasons.get(reason, 0) + 1
            if clock in contracts_by_clock:
                contracts_by_clock[clock].add(key)
                if valid:
                    valid_by_clock[clock].add(key)
            if clock_basis == "NATIVE_STORED_TIMESTAMP" and "underlying_timestamp" in record and record["underlying_timestamp"] is not None:
                underlying_clock = _parse_clock(record["underlying_timestamp"], row.trade_date)
                if underlying_clock != clock:
                    native_underlying_clock_differences += 1

    after_size = row.path.stat().st_size
    after_sha = sha256_file(row.path)
    if before_size != after_size or before_sha != after_sha:
        raise AdmissionError(f"source changed during read: {row.identifier}")
    result = {
        "identifier": row.identifier,
        "ticker": row.ticker,
        "entry_date": row.entry_date,
        "expiration": row.expiration,
        "trade_date": row.trade_date,
        "session_index": row.session_index,
        "path": str(row.path),
        "status": "ADMITTED",
        "size_before": before_size,
        "size_after": after_size,
        "sha256_before": before_sha,
        "sha256_after": after_sha,
        "projected_schema": projected_schema,
        "full_schema_field_count": len(schema),
        "projected_columns": projection,
        "row_count_footer": parquet.metadata.num_rows,
        "row_count_read": rows_seen,
        "clock_basis": clock_basis,
        "clock_basis_scope": "diagnostic_snapshot_only_not_quote_clock_or_observed_reception" if clock_basis == "UNDERLYING_TIMESTAMP_PROXY" else "stored_native_snapshot_clock_not_observed_reception",
        "interval_counts": dict(sorted(intervals.items())),
        "observed_clock_counts": dict(sorted(observed_clock_counts.items())),
        "contract_count_day": len(day_contracts),
        "contract_counts_exact_clock": {clock: len(contracts_by_clock[clock]) for clock in CLOCKS},
        "quote_valid_counts_exact_clock": {clock: len(valid_by_clock[clock]) for clock in CLOCKS},
        "quote_validity_reasons": dict(sorted(quote_reasons.items())),
        "native_underlying_clock_difference_count": native_underlying_clock_differences,
        "staleness_assessed": False,
        "quote_age_claimed": False,
    }
    return result, contracts_by_clock, valid_by_clock


def _missing_result(row: NominalFile) -> dict[str, Any]:
    return {
        "identifier": row.identifier,
        "ticker": row.ticker,
        "entry_date": row.entry_date,
        "expiration": row.expiration,
        "trade_date": row.trade_date,
        "session_index": row.session_index,
        "path": str(row.path),
        "status": "MISSING_SOURCE",
        "size_before": None,
        "size_after": None,
        "sha256_before": None,
        "sha256_after": None,
        "schema": None,
        "row_count_footer": None,
        "row_count_read": None,
        "contract_counts_exact_clock": {clock: 0 for clock in CLOCKS},
        "quote_valid_counts_exact_clock": {clock: 0 for clock in CLOCKS},
        "staleness_assessed": False,
        "quote_age_claimed": False,
    }


def build_diagnostic(source_root: Path, frozen_inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    source_root = Path(os.path.abspath(source_root))
    rows = nominal_files(source_root)
    expected = {Path(os.path.abspath(row.path)) for row in rows}
    frozen_by_id = (
        {item["identifier"]: item for item in frozen_inventory["files"]}
        if frozen_inventory is not None
        else {}
    )
    if frozen_inventory is not None:
        expected_ids = {row.identifier for row in rows}
        if frozen_inventory.get("nominal_file_count") != 69 or set(frozen_by_id) != expected_ids or len(frozen_inventory.get("files", [])) != 69:
            raise AdmissionError("frozen inventory does not contain the exact 69 nominal identities")
    inventory: list[dict[str, Any]] = []
    contracts: dict[str, dict[str, set[tuple[str, str, str, str]]]] = {}
    valid: dict[str, dict[str, set[tuple[str, str, str, str]]]] = {}
    for row in rows:
        frozen_row = frozen_by_id.get(row.identifier) if frozen_inventory is not None else None
        exists = row.path.exists()
        if frozen_row is not None and frozen_row.get("status") == "MISSING_SOURCE":
            validate_missing_source_path(row.path, source_root, expected)
            if exists:
                raise AdmissionError(f"source appeared after frozen inventory: {row.identifier}")
            inventory.append(_missing_result(row))
            continue
        if frozen_row is not None and frozen_row.get("status") != "INVENTORIED":
            raise AdmissionError(f"invalid frozen inventory status: {row.identifier}")
        if not exists:
            validate_missing_source_path(row.path, source_root, expected)
            if frozen_row is not None:
                raise AdmissionError(f"source disappeared after frozen inventory: {row.identifier}")
            inventory.append(_missing_result(row))
            continue
        result, contract_sets, valid_sets = inspect_file(row, source_root, expected, frozen_row=frozen_row)
        inventory.append(result)
        contracts[row.identifier] = contract_sets
        valid[row.identifier] = valid_sets

    intersections: list[dict[str, Any]] = []
    by_tuple = {(row.ticker, row.entry_date, row.expiration, row.trade_date): row for row in rows}
    for ticker in TICKERS:
        for entry_date, expiration, sessions in CHAINS:
            entry_row = by_tuple[(ticker, entry_date, expiration, entry_date)]
            for offset, session in enumerate(sessions[1:], start=1):
                later_row = by_tuple[(ticker, entry_date, expiration, session)]
                entry_present = entry_row.identifier in contracts
                later_present = later_row.identifier in contracts
                for clock in CLOCKS:
                    entry_contracts = contracts.get(entry_row.identifier, {}).get(clock, set())
                    later_contracts = contracts.get(later_row.identifier, {}).get(clock, set())
                    entry_valid = valid.get(entry_row.identifier, {}).get(clock, set())
                    later_valid = valid.get(later_row.identifier, {}).get(clock, set())
                    intersections.append(
                        {
                            "ticker": ticker,
                            "entry_date": entry_date,
                            "expiration": expiration,
                            "session_date": session,
                            "session_offset": offset,
                            "dte_calendar": (datetime.strptime(expiration, "%Y%m%d") - datetime.strptime(session, "%Y%m%d")).days,
                            "clock_et": clock,
                            "entry_source_status": "ADMITTED" if entry_present else "MISSING_SOURCE",
                            "session_source_status": "ADMITTED" if later_present else "MISSING_SOURCE",
                            "entry_identity_count_at_clock": len(entry_contracts),
                            "session_identity_count_at_clock": len(later_contracts),
                            "same_contract_identity_count": len(entry_contracts & later_contracts),
                            "same_contract_quote_valid_both_count": len(entry_valid & later_valid),
                        }
                    )
    return {
        "schema": "weekly_multiday_source_pilot_v1",
        "status": STATUS,
        "flags": {
            "fit_performed": False,
            "profitability_evaluated": False,
            "promotion_approved": False,
            "technical_ready": False,
            "production_modified": False,
            "broker_or_api_used": False,
        },
        "source_root": str(source_root),
        "nominal_file_count": 69,
        "admitted_file_count": sum(row["status"] == "ADMITTED" for row in inventory),
        "missing_source_count": sum(row["status"] == "MISSING_SOURCE" for row in inventory),
        "clock_policy": {"exact_et": list(CLOCKS), "nearest": False, "forward_fill": False},
        "inventory": inventory,
        "intersections": intersections,
    }


def _assert_no_economic_output(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            parts = set(lowered.split("_"))
            if parts & {"pnl", "delta", "label", "return"}:
                raise AssertionError(f"economic output key forbidden at {path}.{key}")
            _assert_no_economic_output(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_economic_output(item, f"{path}[{index}]")


def write_atomic(diagnostic: dict[str, Any], output_dir: Path) -> None:
    _assert_no_economic_output(diagnostic)
    output_dir = Path(os.path.abspath(output_dir))
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        payload = json.dumps(diagnostic, indent=2, sort_keys=True) + "\n"
        (staging / "diagnostic.json").write_text(payload, encoding="utf-8")
        manifest = {
            "diagnostic.json": {
                "bytes": (staging / "diagnostic.json").stat().st_size,
                "sha256": sha256_file(staging / "diagnostic.json"),
            }
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staging.replace(output_dir)
    except BaseException as exc:
        _record_partial_failure(staging, exc)
        raise


def write_inventory_atomic(inventory: dict[str, Any], output_dir: Path) -> None:
    _assert_no_economic_output(inventory)
    output_dir = Path(os.path.abspath(output_dir))
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        payload = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
        inventory_path = staging / "inventory.json"
        inventory_path.write_text(payload, encoding="utf-8")
        manifest = {"inventory.json": {"bytes": inventory_path.stat().st_size, "sha256": sha256_file(inventory_path)}}
        (staging / "inventory_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staging.replace(output_dir)
    except BaseException as exc:
        _record_partial_failure(staging, exc)
        raise


def _record_partial_failure(staging: Path, exc: BaseException) -> None:
    try:
        failure = staging / "failure.json"
        with failure.open("x", encoding="utf-8") as handle:
            json.dump({"status": "FAILED_PARTIAL_PRESERVED", "exception_type": type(exc).__name__, "message": str(exc)}, handle, indent=2)
            handle.write("\n")
    except BaseException:
        pass


def _validate_output_path(output_dir: Path) -> None:
    if _is_link_or_reparse(output_dir):
        raise AdmissionError(f"link/reparse output path is forbidden: {output_dir}")
    if output_dir.exists() and not output_dir.is_dir():
        raise AdmissionError(f"output path is not a directory: {output_dir}")


def _validate_real_roots(source_root: Path, output_dir: Path) -> None:
    if Path(os.path.abspath(source_root)) != Path(os.path.abspath(REAL_SOURCE_ROOT)):
        raise AdmissionError("real execution source root is frozen to D:/ThetaData")
    if Path(os.path.abspath(output_dir)) != Path(os.path.abspath(REAL_OUTPUT)):
        raise AdmissionError("real execution output is frozen to source_pilot_01")
    if _is_link_or_reparse(source_root):
        raise AdmissionError("source root or parent is link/reparse")
    source_resolved = source_root.resolve(strict=True)
    output_parent = Path(os.path.abspath(output_dir.parent))
    _validate_output_path(output_dir)
    try:
        output_parent.relative_to(source_resolved)
    except ValueError:
        pass
    else:
        raise AdmissionError("output cannot be inside the source root")
    return None


def build_real_inventory(source_root: Path, output_dir: Path) -> None:
    _validate_real_roots(source_root, output_dir)
    write_inventory_atomic(build_inventory(source_root), output_dir)


def run_real(source_root: Path, output_dir: Path, inventory_path: Path, inventory_sha256: str) -> None:
    _validate_real_roots(source_root, output_dir)
    expected_inventory = Path(os.path.abspath(output_dir / "inventory.json"))
    if Path(os.path.abspath(inventory_path)) != expected_inventory:
        raise AdmissionError("inventory must be the frozen inventory.json in source_pilot_01")
    if _is_link_or_reparse(inventory_path):
        raise AdmissionError("inventory or parent is link/reparse")
    if not inventory_path.is_file() or sha256_file(inventory_path).lower() != inventory_sha256.lower():
        raise AdmissionError("inventory SHA-256 binding failed")
    frozen = json.loads(inventory_path.read_text(encoding="utf-8"))
    current = build_inventory(source_root)
    if frozen != current:
        raise AdmissionError("current metadata/hashes differ from frozen inventory")
    diagnostic_path = output_dir / "diagnostic.json"
    manifest_path = output_dir / "final_manifest.json"
    if diagnostic_path.exists() or manifest_path.exists():
        raise FileExistsError("immutable diagnostic or final manifest already exists")
    diagnostic = build_diagnostic(source_root, frozen_inventory=frozen)
    _assert_no_economic_output(diagnostic)
    closing = build_inventory(source_root)
    if closing != frozen:
        raise AdmissionError("source inventory changed before final publication")
    staging = Path(tempfile.mkdtemp(prefix=".diagnostic.", dir=output_dir))
    try:
        _validate_output_path(staging)
        staged_diagnostic = staging / "diagnostic.json"
        staged_diagnostic.write_text(json.dumps(diagnostic, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        code_path = Path(__file__).resolve(strict=True)
        contract_path = code_path.with_name("SOURCE_PILOT_CONTRACT.md")
        manifest = {
            "schema": "weekly_multiday_source_pilot_final_manifest_v1",
            "status": STATUS,
            "inventory_bound_sha256": inventory_sha256.lower(),
            "closing_inventory_matches_frozen": True,
            "artifacts": {
                "inventory.json": {"bytes": inventory_path.stat().st_size, "sha256": sha256_file(inventory_path)},
                "diagnostic.json": {"bytes": staged_diagnostic.stat().st_size, "sha256": sha256_file(staged_diagnostic)},
            },
            "implementation_pins": {
                "weekly_multiday_source_pilot.py": sha256_file(code_path),
                "SOURCE_PILOT_CONTRACT.md": sha256_file(contract_path),
            },
        }
        staged_manifest = staging / "final_manifest.json"
        staged_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if diagnostic_path.exists() or manifest_path.exists():
            raise FileExistsError("publication target appeared during finalization")
        staged_diagnostic.rename(diagnostic_path)
        staged_manifest.rename(manifest_path)
    except BaseException as exc:
        _record_partial_failure(staging, exc)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Source-only weekly/multiday continuity diagnostic")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build-reviewed-inventory", action="store_true")
    mode.add_argument("--execute-reviewed-source-pilot", action="store_true")
    parser.add_argument("--source-root", default=str(REAL_SOURCE_ROOT))
    parser.add_argument("--output-dir", default=str(REAL_OUTPUT))
    parser.add_argument("--inventory")
    parser.add_argument("--inventory-sha256")
    args = parser.parse_args()
    if args.build_reviewed_inventory:
        build_real_inventory(Path(args.source_root), Path(args.output_dir))
    else:
        if not args.inventory or not args.inventory_sha256:
            parser.error("diagnostic requires --inventory and --inventory-sha256")
        run_real(Path(args.source_root), Path(args.output_dir), Path(args.inventory), args.inventory_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
