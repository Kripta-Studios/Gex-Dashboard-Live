from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import tempfile
from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


TICKERS = ("SPY", "QQQ", "SPXW")
START_DATE, END_DATE = "20230103", "20260630"
DECISION_CLOCK, EXECUTION_CLOCK = "10:30", "10:35"
MAX_ASK = 49.95
BASE_SLIPPAGE, ADVERSE_SLIPPAGE = 0.01, 0.02
COMMISSION_PER_SIDE = 1.30
SOURCE_ROOT = Path(r"D:\ThetaData")
CALENDAR_PATH = Path(r"D:\GexResearchArtifacts\level_oracle_20261018\session_clock_dataset_v1\index.parquet")
CALENDAR_SHA256 = "7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4"
OUTPUT_DIR = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101\h2_dataset_v2_01")
PILOT_PATH = Path(__file__).resolve().with_name("weekly_multiday_source_pilot.py")
PILOT_SHA256 = "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878"
CONTRACT_PATH = Path(__file__).resolve().with_name("ECONOMIC_H2_CONTRACT.md")
CONTRACT_SHA256 = "245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5"
AMENDMENT_PATH = Path(__file__).resolve().with_name("H2_CLOCK_FILTER_V2_AMENDMENT.md")
AMENDMENT_SHA256 = "9210c6e50094e5745f80c5e03f577f6bd673263f84d3c3ef764ad76b22ca56eb"
STATUS = "COMPLETE_WEEKLY_H2_DATASET_NOT_EVALUATED"
FILE_RE = re.compile(r"^(?P<ticker>SPY|QQQ|SPXW)_(?P<expiration>\d{8})_(?P<trade_date>\d{8})_greeks\.parquet$")
FEATURE_KEYS = (
    "ticker_SPY", "ticker_QQQ", "ticker_SPXW", "right_call", "dte", "weekday",
    "spot", "strike", "moneyness", "bid", "ask", "spread_relative", "delta",
    "implied_vol", "gamma", "theta", "vega", "rho",
)
IDENTITY_COLUMNS = ("symbol", "expiration", "trade_date", "strike", "right")
VALUE_COLUMNS = (
    "timestamp", "underlying_timestamp", "interval_used", "underlying_price", "bid", "ask",
    "delta", "implied_vol", "gamma", "theta", "vega", "rho",
)
NY = ZoneInfo("America/New_York")


class DatasetError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pilot(path: Path, expected_sha256: str):
    path = path.resolve(strict=True)
    if sha256_file(path) != expected_sha256:
        raise DatasetError("frozen source-pilot helper pin mismatch")
    spec = importlib.util.spec_from_file_location("weekly_multiday_source_pilot_frozen", path)
    if spec is None or spec.loader is None:
        raise DatasetError("cannot load frozen source-pilot helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _yyyymmdd(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    text = str(value).strip().replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise DatasetError(f"invalid date identity: {value!r}")
    datetime.strptime(text, "%Y%m%d")
    return text


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _label_time(day: str) -> str:
    local = datetime.strptime(day + EXECUTION_CLOCK, "%Y%m%d%H:%M").replace(tzinfo=NY)
    return local.isoformat()


def _assert_plain_path(path: Path, root: Path, pilot: Any) -> None:
    absolute, root_absolute = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    try:
        absolute.relative_to(root_absolute)
    except ValueError as exc:
        raise DatasetError(f"path outside declared root: {absolute}") from exc
    if pilot._is_link_or_reparse(absolute):
        raise DatasetError(f"symlink/reparse source forbidden: {absolute}")


def read_calendar(calendar_path: Path, expected_sha256: str, pilot: Any) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    if pilot._is_link_or_reparse(calendar_path):
        raise DatasetError("calendar or ancestor is link/reparse")
    before = sha256_file(calendar_path)
    if before != expected_sha256:
        raise DatasetError("calendar SHA-256 mismatch")
    parquet = pq.ParquetFile(calendar_path)
    if not {"ticker", "date", "close_i"}.issubset(parquet.schema_arrow.names):
        raise DatasetError("calendar lacks ticker/date/close_i")
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    columns = [name for name in ("ticker", "date", "close_i", "status") if name in parquet.schema_arrow.names]
    for batch in parquet.iter_batches(columns=columns, use_threads=False, batch_size=65536):
        for row in batch.to_pylist():
            ticker, day = str(row["ticker"]).strip().upper(), _yyyymmdd(row["date"])
            if ticker not in TICKERS or not START_DATE <= day <= END_DATE:
                continue
            if (ticker, day) in seen:
                raise DatasetError(f"duplicate calendar identity: {ticker}:{day}")
            seen.add((ticker, day))
            rows.append({"ticker": ticker, "date": day, "close_i": int(row["close_i"]), "status": row.get("status")})
    if sha256_file(calendar_path) != before:
        raise DatasetError("calendar changed during metadata read")
    sessions = {ticker: sorted(row["date"] for row in rows if row["ticker"] == ticker) for ticker in TICKERS}
    return sessions, sorted(rows, key=lambda row: (row["ticker"], row["date"]))


def _entry_files(source_root: Path, ticker: str, day: str, pilot: Any) -> list[tuple[str, Path]]:
    directory = source_root / "data_options" / ticker / "greeks" / day[:4] / day[4:6]
    if not directory.is_dir():
        return []
    result: list[tuple[str, Path]] = []
    for path in directory.glob(f"{ticker}_*_{day}_greeks.parquet"):
        match = FILE_RE.match(path.name)
        if match is not None and match.group("trade_date") == day:
            _assert_plain_path(path, source_root, pilot)
            result.append((match.group("expiration"), path))
    return sorted(result)


def plan_calendar(source_root: Path, sessions: dict[str, list[str]], pilot: Any) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    if pilot._is_link_or_reparse(source_root):
        raise DatasetError("source root or ancestor is link/reparse")
    coverage: list[dict[str, Any]] = []
    sources: dict[str, Path] = {}
    for ticker in TICKERS:
        dates = sessions[ticker]
        for index, entry_date in enumerate(dates):
            base = {"ticker": ticker, "entry_date": entry_date, "exit_date": None, "expiration": None, "status": None, "reason": None, "candidate_ids": [], "entry_path": None, "exit_path": None}
            if index + 2 >= len(dates):
                coverage.append({**base, "status": "HORIZON_OUTSIDE_CALENDAR", "reason": "NO_OFFICIAL_H2"})
                continue
            exit_date = dates[index + 2]
            eligible: list[tuple[str, Path]] = []
            for expiration, path in _entry_files(source_root, ticker, entry_date, pilot):
                dte = (datetime.strptime(expiration, "%Y%m%d") - datetime.strptime(entry_date, "%Y%m%d")).days
                if 1 <= dte <= 8 and exit_date < expiration:
                    eligible.append((expiration, path))
            if not eligible:
                coverage.append({**base, "exit_date": exit_date, "status": "NO_SERIES", "reason": "NO_1_TO_8_DTE_SERIES_ALLOWING_H2"})
                continue
            expiration, entry_path = min(eligible, key=lambda item: item[0])
            exit_path = source_root / "data_options" / ticker / "greeks" / exit_date[:4] / exit_date[4:6] / f"{ticker}_{expiration}_{exit_date}_greeks.parquet"
            _assert_plain_path(exit_path, source_root, pilot)
            sources[str(entry_path)], sources[str(exit_path)] = entry_path, exit_path
            coverage.append({**base, "exit_date": exit_date, "expiration": expiration, "status": "PLANNED", "entry_path": str(entry_path), "exit_path": str(exit_path)})
    return coverage, sources


def inventory_sources(sources: dict[str, Path]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    by_path: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for text, path in sorted(sources.items()):
        if not path.exists():
            item = {"path": text, "status": "MISSING_SOURCE", "bytes": None, "sha256": None, "rows": None, "projected_schema": None}
        else:
            size, digest = path.stat().st_size, sha256_file(path)
            parquet = pq.ParquetFile(path)
            projection = [name for name in (*IDENTITY_COLUMNS, *VALUE_COLUMNS) if name in parquet.schema_arrow.names]
            item = {"path": text, "status": "INVENTORIED", "bytes": size, "sha256": digest, "rows": parquet.metadata.num_rows, "projected_schema": [{"name": name, "type": str(parquet.schema_arrow.field(name).type)} for name in projection]}
            if path.stat().st_size != size or sha256_file(path) != digest:
                raise DatasetError(f"source changed during inventory: {path}")
        by_path[text] = item
        rows.append(item)
    return by_path, rows


ISO_CLOCK_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})[T ](?P<hour>\d{2}):(?P<minute>\d{2})"
    r"(?::(?P<second>\d{2})(?P<fraction>\.\d+)?)?(?P<zone>Z|[+-]\d{2}:\d{2})?$"
)


def _parse_clock_v2(value: Any, trade_date: str, fraction_nonzero_override: bool | None = None) -> tuple[str | None, bool]:
    if value is None or isinstance(value, (bool, int, float, Decimal)):
        raise DatasetError(f"invalid snapshot clock type: {type(value).__name__}")
    fraction_nonzero = False
    if isinstance(value, datetime):
        parsed = value
        fraction_nonzero = bool(value.microsecond or getattr(value, "nanosecond", 0))
    elif isinstance(value, str):
        match = ISO_CLOCK_RE.fullmatch(value.strip())
        if match is None:
            raise DatasetError(f"invalid ISO snapshot clock: {value!r}")
        fraction = match.group("fraction")
        fraction_nonzero = fraction is not None and any(char != "0" for char in fraction[1:])
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise DatasetError(f"invalid ISO snapshot clock: {value!r}") from exc
    else:
        raise DatasetError(f"invalid snapshot clock type: {type(value).__name__}")
    if fraction_nonzero_override is not None:
        fraction_nonzero = fraction_nonzero_override
    local = parsed.replace(tzinfo=NY) if parsed.tzinfo is None else parsed.astimezone(NY)
    if local.strftime("%Y%m%d") != trade_date:
        raise DatasetError("snapshot clock local date differs from trade_date")
    subminute = local.second != 0 or fraction_nonzero
    clock = local.strftime("%H:%M")
    selected = clock if not subminute and clock in (DECISION_CLOCK, EXECUTION_CLOCK) else None
    return selected, subminute


def _arrow_fraction_nonzero(scalar: Any, arrow_type: pa.DataType) -> bool | None:
    if not pa.types.is_timestamp(arrow_type):
        return None
    units_per_second = {"s": 1, "ms": 1_000, "us": 1_000_000, "ns": 1_000_000_000}
    return int(scalar.value) % units_per_second[arrow_type.unit] != 0


def extract_snapshots(path: Path, inventory: dict[str, Any], ticker: str, trade_date: str, expiration: str, pilot: Any) -> tuple[dict[str, dict[tuple[str, str], dict[str, Any]]], str, dict[str, Any]]:
    if inventory["status"] != "INVENTORIED" or not path.is_file():
        raise DatasetError(f"source is not inventoried: {path}")
    if path.stat().st_size != inventory["bytes"] or sha256_file(path) != inventory["sha256"]:
        raise DatasetError(f"source differs before value read: {path}")
    parquet = pq.ParquetFile(path)
    names = set(parquet.schema_arrow.names)
    if not set(IDENTITY_COLUMNS).issubset(names):
        raise DatasetError(f"identity columns missing: {path}")
    if "timestamp" in names:
        clock_column, clock_basis = "timestamp", "NATIVE_STORED_TIMESTAMP"
    elif "underlying_timestamp" in names:
        clock_column, clock_basis = "underlying_timestamp", "UNDERLYING_TIMESTAMP_PROXY"
    else:
        raise DatasetError(f"snapshot clock missing: {path}")
    projection = [name for name in (*IDENTITY_COLUMNS, *VALUE_COLUMNS) if name in names]
    schema = [{"name": name, "type": str(parquet.schema_arrow.field(name).type)} for name in projection]
    if schema != inventory["projected_schema"] or parquet.metadata.num_rows != inventory["rows"]:
        raise DatasetError(f"source schema/rows differ before value read: {path}")
    snapshots: dict[str, dict[tuple[str, str], dict[str, Any]]] = {DECISION_CLOCK: {}, EXECUTION_CLOCK: {}}
    clock_metadata = {
        "path": str(path), "trade_date": trade_date, "clock_column": clock_column, "clock_basis": clock_basis,
        "rows_total": 0, "rows_selected_10_30": 0, "rows_selected_10_35": 0,
        "rows_ignored_valid": 0, "rows_ignored_subminute": 0, "unique_raw_clocks": set(),
    }
    for batch in parquet.iter_batches(columns=projection, use_threads=False, batch_size=65536):
        clock_array = batch.column(batch.schema.get_field_index(clock_column))
        admitted_raw: list[Any] = []
        parsed_by_key: dict[tuple[str, str], tuple[str | None, bool]] = {}
        for scalar in pc.unique(clock_array):
            if not scalar.is_valid:
                raise DatasetError(f"null snapshot clock: {path}")
            raw = scalar.as_py()
            parsed = _parse_clock_v2(raw, trade_date, _arrow_fraction_nonzero(scalar, clock_array.type))
            key = (type(raw).__name__, repr(raw))
            parsed_by_key[key] = parsed
            clock_metadata["unique_raw_clocks"].add(key)
            if parsed[0] is not None:
                admitted_raw.append(raw)
        for counted in pc.value_counts(clock_array).to_pylist():
            raw, count = counted["values"], int(counted["counts"])
            selected, subminute = parsed_by_key[(type(raw).__name__, repr(raw))]
            clock_metadata["rows_total"] += count
            if selected == DECISION_CLOCK:
                clock_metadata["rows_selected_10_30"] += count
            elif selected == EXECUTION_CLOCK:
                clock_metadata["rows_selected_10_35"] += count
            else:
                clock_metadata["rows_ignored_valid"] += count
                if subminute:
                    clock_metadata["rows_ignored_subminute"] += count
        if not admitted_raw:
            continue
        filtered = batch.filter(pc.is_in(clock_array, value_set=pa.array(admitted_raw, type=clock_array.type)))
        for row in filtered.to_pylist():
            if str(row["symbol"]).strip().upper() != ticker or _yyyymmdd(row["trade_date"]) != trade_date or _yyyymmdd(row["expiration"]) != expiration:
                raise DatasetError(f"row identity mismatch: {path}")
            clock = pilot._parse_clock(row[clock_column], trade_date)
            key = (pilot._strike_key(row["strike"]), pilot._normalize_right(row["right"]))
            if key in snapshots[clock]:
                raise DatasetError(f"duplicate contract snapshot: {path}:{clock}:{key}")
            snapshots[clock][key] = row
    if path.stat().st_size != inventory["bytes"] or sha256_file(path) != inventory["sha256"]:
        raise DatasetError(f"source changed during value read: {path}")
    clock_metadata["unique_raw_clock_count"] = len(clock_metadata.pop("unique_raw_clocks"))
    return snapshots, clock_basis, clock_metadata


def _decision_candidate(row: dict[str, Any], right: str, pilot: Any) -> dict[str, Any] | None:
    quote_ok, _ = pilot._valid_quote(row.get("bid"), row.get("ask"))
    bid, ask = _number(row.get("bid")), _number(row.get("ask"))
    spot, strike, delta = _number(row.get("underlying_price")), _number(row.get("strike")), _number(row.get("delta"))
    if not quote_ok or bid is None or ask is None or spot is None or strike is None or delta is None or spot <= 0 or ask > MAX_ASK or abs(delta) > 1:
        return None
    if (right == "CALL" and delta <= 0) or (right == "PUT" and delta >= 0):
        return None
    spread = (ask - bid) / ask
    return {"row": row, "bid": bid, "ask": ask, "spot": spot, "strike": strike, "delta": delta, "spread": spread, "sort": (abs(abs(delta) - 0.50), spread, strike)}


def _scenario(entry_ask: float, exit_bid: float) -> int:
    gross_return = (exit_bid - entry_ask) / entry_ask
    if gross_return < -0.25:
        return 1
    if gross_return < 0:
        return 2
    if gross_return < 0.25:
        return 3
    return 4


def _net(entry_ask: float, exit_value: float, slippage: float) -> float:
    return (max(exit_value - slippage, 0.0) - entry_ask - slippage) * 100.0 - 2.0 * COMMISSION_PER_SIDE


def _debit(entry_ask: float, slippage: float) -> float:
    return (entry_ask + slippage) * 100.0 + COMMISSION_PER_SIDE


def build_candidates(coverage: list[dict[str, Any]], inventory: dict[str, dict[str, Any]], calendar_sha: str, pilot: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    cache: OrderedDict[str, tuple[dict[str, dict[tuple[str, str], dict[str, Any]]], str, dict[str, Any]]] = OrderedDict()
    clock_files: dict[str, dict[str, Any]] = {}

    def cached_extract(path: Path, item: dict[str, Any], ticker: str, day: str, expiration: str):
        key = str(path)
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        value = extract_snapshots(path, item, ticker, day, expiration, pilot)
        cache[key] = value
        if len(cache) > 16:
            cache.popitem(last=False)
        return value

    for cover in coverage:
        if cover["status"] != "PLANNED":
            continue
        ticker, entry_date, exit_date, expiration = cover["ticker"], cover["entry_date"], cover["exit_date"], cover["expiration"]
        entry_path, exit_path = Path(cover["entry_path"]), Path(cover["exit_path"])
        entry_inventory, exit_inventory = inventory[str(entry_path)], inventory[str(exit_path)]
        if entry_inventory["status"] != "INVENTORIED":
            cover.update(status="MISSING_ENTRY_SOURCE", reason="SELECTED_ENTRY_SOURCE_MISSING")
            continue
        entry_snapshots, entry_basis, entry_clock_metadata = cached_extract(entry_path, entry_inventory, ticker, entry_date, expiration)
        clock_files[str(entry_path)] = entry_clock_metadata
        exit_snapshots, exit_basis = None, None
        if exit_inventory["status"] == "INVENTORIED":
            exit_snapshots, exit_basis, exit_clock_metadata = cached_extract(exit_path, exit_inventory, ticker, exit_date, expiration)
            clock_files[str(exit_path)] = exit_clock_metadata
        selected: dict[str, dict[str, Any]] = {}
        for right in ("CALL", "PUT"):
            options = [_decision_candidate(row, right, pilot) for (_, row_right), row in entry_snapshots[DECISION_CLOCK].items() if row_right == right]
            options = [option for option in options if option is not None]
            if options:
                selected[right] = min(options, key=lambda item: item["sort"])
        if not selected:
            cover.update(status="NO_DECISION_CANDIDATE", reason="NO_VALID_1030_CALL_OR_PUT")
            continue
        for right, chosen in selected.items():
            key = (pilot._strike_key(chosen["strike"]), right)
            execution = entry_snapshots[EXECUTION_CLOCK].get(key)
            execution_ask = _number(execution.get("ask")) if execution is not None else None
            entry_ok = execution is not None and pilot._valid_quote(execution.get("bid"), execution.get("ask"))[0] and execution_ask is not None and execution_ask <= MAX_ASK
            decision = chosen["row"]
            dte = (datetime.strptime(expiration, "%Y%m%d") - datetime.strptime(entry_date, "%Y%m%d")).days
            features = {
                "ticker_SPY": int(ticker == "SPY"), "ticker_QQQ": int(ticker == "QQQ"), "ticker_SPXW": int(ticker == "SPXW"),
                "right_call": int(right == "CALL"), "dte": dte, "weekday": datetime.strptime(entry_date, "%Y%m%d").weekday(),
                "spot": chosen["spot"], "strike": chosen["strike"], "moneyness": chosen["strike"] / chosen["spot"] - 1.0,
                "bid": chosen["bid"], "ask": chosen["ask"], "spread_relative": chosen["spread"], "delta": chosen["delta"],
                "implied_vol": _number(decision.get("implied_vol")), "gamma": _number(decision.get("gamma")), "theta": _number(decision.get("theta")),
                "vega": _number(decision.get("vega")), "rho": _number(decision.get("rho")),
            }
            if tuple(features) != FEATURE_KEYS:
                raise AssertionError("feature order differs from contract")
            candidate_id = f"{ticker}:{entry_date}:{expiration}:{right}"
            common = {
                "candidate_id": candidate_id, "ticker": ticker, "entry_date": entry_date, "exit_date": exit_date, "expiration": expiration,
                "strike": chosen["strike"], "right": right, "features": features, "decision_ask": chosen["ask"],
                "source_pins": {"calendar_sha256": calendar_sha, "entry_path": str(entry_path), "entry_sha256": entry_inventory["sha256"], "exit_path": str(exit_path), "exit_sha256": exit_inventory["sha256"], "clock_basis_entry": entry_basis, "clock_basis_exit": exit_basis},
            }
            if not entry_ok:
                candidate = {**common, "entry_ask": None, "exit_bid": None, "status": "NO_FILL", "label_available_at": _label_time(entry_date), "scenario": 0, "payoff_is_lower_bound": False, "net_base": 0.0, "net_adverse": 0.0, "entry_debit_base": 0.0, "entry_debit_adverse": 0.0}
            else:
                exit_row = exit_snapshots[EXECUTION_CLOCK].get(key) if exit_snapshots is not None else None
                exit_bid = _number(exit_row.get("bid")) if exit_row is not None else None
                exit_ok = exit_row is not None and pilot._valid_quote(exit_row.get("bid"), exit_row.get("ask"))[0] and exit_bid is not None
                if exit_inventory["status"] != "INVENTORIED":
                    row_status, observed_exit = "MISSING_EXIT_SOURCE", None
                elif not exit_ok:
                    row_status, observed_exit = "MISSING_EXIT_QUOTE", None
                else:
                    row_status, observed_exit = "OBSERVED_EXIT", exit_bid
                valuation = observed_exit if observed_exit is not None else 0.0
                candidate = {
                    **common, "entry_ask": execution_ask, "exit_bid": observed_exit, "status": row_status,
                    "label_available_at": _label_time(exit_date),
                    "scenario": _scenario(execution_ask, observed_exit) if observed_exit is not None else 1,
                    "payoff_is_lower_bound": observed_exit is None,
                    "net_base": _net(execution_ask, valuation, BASE_SLIPPAGE), "net_adverse": _net(execution_ask, valuation, ADVERSE_SLIPPAGE),
                    "entry_debit_base": _debit(execution_ask, BASE_SLIPPAGE), "entry_debit_adverse": _debit(execution_ask, ADVERSE_SLIPPAGE),
                }
            candidates.append(candidate)
            cover["candidate_ids"].append(candidate_id)
        cover.update(status="CANDIDATES_BUILT", reason=None)
    return sorted(candidates, key=lambda row: row["candidate_id"]), [clock_files[path] for path in sorted(clock_files)]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prepare_inventory_payload(
    source_root: Path,
    calendar_path: Path,
    calendar_sha256: str,
    *,
    pilot_path: Path = PILOT_PATH,
    pilot_sha256: str = PILOT_SHA256,
    contract_path: Path = CONTRACT_PATH,
    contract_sha256: str = CONTRACT_SHA256,
    amendment_path: Path = AMENDMENT_PATH,
    amendment_sha256: str = AMENDMENT_SHA256,
) -> tuple[dict[str, Any], Any]:
    source_root, calendar_path = (Path(os.path.abspath(path)) for path in (source_root, calendar_path))
    pilot = load_pilot(pilot_path, pilot_sha256)
    contract_path = Path(os.path.abspath(contract_path))
    if pilot._is_link_or_reparse(contract_path) or sha256_file(contract_path) != contract_sha256:
        raise DatasetError("economic contract pin/path guard failed")
    amendment_path = Path(os.path.abspath(amendment_path))
    if pilot._is_link_or_reparse(amendment_path) or sha256_file(amendment_path) != amendment_sha256:
        raise DatasetError("clock-filter amendment pin/path guard failed")
    sessions, calendar_rows = read_calendar(calendar_path, calendar_sha256, pilot)
    coverage, planned_sources = plan_calendar(source_root, sessions, pilot)
    _, source_inventory = inventory_sources(planned_sources)
    payload = {
        "schema": "weekly_h2_source_inventory_v2_clock_filter",
        "source_root": str(source_root),
        "calendar_path": str(calendar_path),
        "calendar_sha256": calendar_sha256,
        "calendar_rows": calendar_rows,
        "coverage_plan": coverage,
        "sources": source_inventory,
        "pins": {
            "weekly_multiday_source_pilot.py": pilot_sha256,
            "ECONOMIC_H2_CONTRACT.md": contract_sha256,
            "H2_CLOCK_FILTER_V2_AMENDMENT.md": amendment_sha256,
            "build_weekly_h2_dataset_v2.py": sha256_file(Path(__file__).resolve()),
        },
    }
    return payload, pilot


def _preserve_failure(staging: Path, exc: BaseException) -> None:
    try:
        _write_json(staging / "failure.json", {"status": "FAILED_PARTIAL_PRESERVED", "exception_type": type(exc).__name__, "message": str(exc)})
    except BaseException:
        pass


def build_reviewed_inventory(
    source_root: Path,
    calendar_path: Path,
    calendar_sha256: str,
    output_dir: Path,
    **pins: Any,
) -> dict[str, Any]:
    output_dir = Path(os.path.abspath(output_dir))
    payload, pilot = prepare_inventory_payload(source_root, calendar_path, calendar_sha256, **pins)
    if pilot._is_link_or_reparse(output_dir):
        raise DatasetError("output or ancestor is link/reparse")
    if output_dir.exists():
        raise FileExistsError(f"immutable output exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        if pilot._is_link_or_reparse(staging):
            raise DatasetError("inventory staging or ancestor is link/reparse")
        inventory_path = staging / "inventory.json"
        _write_json(inventory_path, payload)
        receipt = {"schema": "weekly_h2_inventory_manifest_v1", "inventory.json": {"bytes": inventory_path.stat().st_size, "sha256": sha256_file(inventory_path)}}
        _write_json(staging / "inventory_manifest.json", receipt)
        if output_dir.exists():
            raise FileExistsError(f"publication target appeared: {output_dir}")
        staging.rename(output_dir)
    except BaseException as exc:
        _preserve_failure(staging, exc)
        raise
    return receipt


def execute_reviewed_builder(
    source_root: Path,
    calendar_path: Path,
    calendar_sha256: str,
    output_dir: Path,
    inventory_path: Path,
    inventory_sha256: str,
    **pins: Any,
) -> dict[str, Any]:
    output_dir, inventory_path = Path(os.path.abspath(output_dir)), Path(os.path.abspath(inventory_path))
    current, pilot = prepare_inventory_payload(source_root, calendar_path, calendar_sha256, **pins)
    if pilot._is_link_or_reparse(output_dir) or pilot._is_link_or_reparse(inventory_path):
        raise DatasetError("output/inventory or ancestor is link/reparse")
    if inventory_path != output_dir / "inventory.json" or not inventory_path.is_file() or sha256_file(inventory_path) != inventory_sha256:
        raise DatasetError("frozen inventory binding failed")
    frozen = json.loads(inventory_path.read_text(encoding="utf-8"))
    if current != frozen:
        raise DatasetError("metadata/plan/source inventory differs before first value")
    coverage = json.loads(json.dumps(frozen["coverage_plan"]))
    source_inventory = frozen["sources"]
    inventory_by_path = {item["path"]: item for item in source_inventory}
    candidates, clock_files = build_candidates(coverage, inventory_by_path, calendar_sha256, pilot)
    closing, _ = prepare_inventory_payload(source_root, calendar_path, calendar_sha256, **pins)
    if closing != frozen:
        raise DatasetError("calendar/plan/source inventory changed before publication")
    for name in ("candidates.jsonl", "coverage.json", "manifest.json"):
        if (output_dir / name).exists():
            raise FileExistsError(f"immutable artifact exists: {name}")
    staging = Path(tempfile.mkdtemp(prefix=".builder.", dir=output_dir))
    try:
        if pilot._is_link_or_reparse(staging):
            raise DatasetError("builder staging or ancestor is link/reparse")
        candidates_path = staging / "candidates.jsonl"
        with candidates_path.open("x", encoding="utf-8") as handle:
            for row in candidates:
                handle.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
        _write_json(staging / "coverage.json", {"schema": "weekly_h2_coverage_v2", "calendar": frozen["calendar_rows"], "rows": coverage, "clock_files": clock_files})
        manifest = {
            "schema": "weekly_h2_dataset_manifest_v2", "status": STATUS,
            "flags": {"fit_performed": False, "economic_evaluation_performed": False, "promotion_approved": False, "production_modified": False},
            "calendar": {"path": frozen["calendar_path"], "sha256": calendar_sha256}, "files": {},
            "implementation_pins": frozen["pins"], "inventory_bound_sha256": inventory_sha256,
        }
        files = (("candidates.jsonl", len(candidates)), ("coverage.json", len(coverage)), ("inventory.json", len(source_inventory)))
        for name, rows_count in files:
            path = inventory_path if name == "inventory.json" else staging / name
            manifest["files"][name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path), "rows": rows_count}
        _write_json(staging / "manifest.json", manifest)
        for name in ("candidates.jsonl", "coverage.json", "manifest.json"):
            (staging / name).rename(output_dir / name)
    except BaseException as exc:
        _preserve_failure(staging, exc)
        raise
    return manifest


def build_dataset(
    source_root: Path,
    calendar_path: Path,
    calendar_sha256: str,
    output_dir: Path,
    **pins: Any,
) -> dict[str, Any]:
    build_reviewed_inventory(source_root, calendar_path, calendar_sha256, output_dir, **pins)
    inventory_path = Path(os.path.abspath(output_dir)) / "inventory.json"
    return execute_reviewed_builder(source_root, calendar_path, calendar_sha256, output_dir, inventory_path, sha256_file(inventory_path), **pins)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build the frozen weekly H2 source-level dataset")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build-reviewed-inventory", action="store_true")
    mode.add_argument("--execute-reviewed-builder", action="store_true")
    parser.add_argument("--source-root", default=str(SOURCE_ROOT))
    parser.add_argument("--calendar", default=str(CALENDAR_PATH))
    parser.add_argument("--calendar-sha256", default=CALENDAR_SHA256)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--inventory")
    parser.add_argument("--inventory-sha256")
    args = parser.parse_args()
    if Path(os.path.abspath(args.source_root)) != Path(os.path.abspath(SOURCE_ROOT)) or Path(os.path.abspath(args.calendar)) != Path(os.path.abspath(CALENDAR_PATH)) or Path(os.path.abspath(args.output_dir)) != Path(os.path.abspath(OUTPUT_DIR)):
        parser.error("real CLI roots are frozen; fixtures must use the Python API")
    if args.calendar_sha256.lower() != CALENDAR_SHA256:
        parser.error("real CLI calendar SHA-256 is frozen")
    if args.build_reviewed_inventory:
        build_reviewed_inventory(Path(args.source_root), Path(args.calendar), args.calendar_sha256, Path(args.output_dir))
    else:
        if not args.inventory or not args.inventory_sha256:
            parser.error("execution requires --inventory and --inventory-sha256")
        execute_reviewed_builder(Path(args.source_root), Path(args.calendar), args.calendar_sha256, Path(args.output_dir), Path(args.inventory), args.inventory_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
