from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import stat
import sys
import tempfile
from datetime import date, datetime
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
OUTPUT_DIR = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101\h2_dataset_01")
PILOT_PATH = Path(__file__).resolve().with_name("weekly_multiday_source_pilot.py")
PILOT_SHA256 = "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878"
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
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _label_time(day: str) -> str:
    local = datetime.strptime(day + EXECUTION_CLOCK, "%Y%m%d%H:%M").replace(tzinfo=NY)
    return local.isoformat()


def _assert_plain_path(path: Path, root: Path) -> None:
    absolute, root_absolute = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    try:
        absolute.relative_to(root_absolute)
    except ValueError as exc:
        raise DatasetError(f"path outside declared root: {absolute}") from exc
    current = absolute
    while True:
        if current.exists():
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400):
                raise DatasetError(f"symlink/reparse source forbidden: {absolute}")
        if current.parent == current:
            break
        current = current.parent


def read_calendar(calendar_path: Path, expected_sha256: str) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
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


def _entry_files(source_root: Path, ticker: str, day: str) -> list[tuple[str, Path]]:
    directory = source_root / "data_options" / ticker / "greeks" / day[:4] / day[4:6]
    if not directory.is_dir():
        return []
    result: list[tuple[str, Path]] = []
    for path in directory.glob(f"{ticker}_*_{day}_greeks.parquet"):
        match = FILE_RE.match(path.name)
        if match is not None and match.group("trade_date") == day:
            _assert_plain_path(path, source_root)
            result.append((match.group("expiration"), path))
    return sorted(result)


def plan_calendar(source_root: Path, sessions: dict[str, list[str]]) -> tuple[list[dict[str, Any]], dict[str, Path]]:
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
            for expiration, path in _entry_files(source_root, ticker, entry_date):
                dte = (datetime.strptime(expiration, "%Y%m%d") - datetime.strptime(entry_date, "%Y%m%d")).days
                if 1 <= dte <= 8 and exit_date < expiration:
                    eligible.append((expiration, path))
            if not eligible:
                coverage.append({**base, "exit_date": exit_date, "status": "NO_SERIES", "reason": "NO_1_TO_8_DTE_SERIES_ALLOWING_H2"})
                continue
            expiration, entry_path = min(eligible, key=lambda item: item[0])
            exit_path = source_root / "data_options" / ticker / "greeks" / exit_date[:4] / exit_date[4:6] / f"{ticker}_{expiration}_{exit_date}_greeks.parquet"
            _assert_plain_path(exit_path, source_root)
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


def extract_snapshots(path: Path, inventory: dict[str, Any], ticker: str, trade_date: str, expiration: str, pilot: Any) -> tuple[dict[str, dict[tuple[str, str], dict[str, Any]]], str]:
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
    for batch in parquet.iter_batches(columns=projection, use_threads=False, batch_size=65536):
        clock_array = batch.column(batch.schema.get_field_index(clock_column))
        admitted_raw: list[Any] = []
        for raw in pc.unique(clock_array).to_pylist():
            try:
                clock = pilot._parse_clock(raw, trade_date)
            except Exception:
                continue
            if clock in snapshots:
                admitted_raw.append(raw)
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
    return snapshots, clock_basis


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


def build_candidates(coverage: list[dict[str, Any]], inventory: dict[str, dict[str, Any]], calendar_sha: str, pilot: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for cover in coverage:
        if cover["status"] != "PLANNED":
            continue
        ticker, entry_date, exit_date, expiration = cover["ticker"], cover["entry_date"], cover["exit_date"], cover["expiration"]
        entry_path, exit_path = Path(cover["entry_path"]), Path(cover["exit_path"])
        entry_inventory, exit_inventory = inventory[str(entry_path)], inventory[str(exit_path)]
        if entry_inventory["status"] != "INVENTORIED":
            cover.update(status="MISSING_ENTRY_SOURCE", reason="SELECTED_ENTRY_SOURCE_MISSING")
            continue
        entry_snapshots, entry_basis = extract_snapshots(entry_path, entry_inventory, ticker, entry_date, expiration, pilot)
        exit_snapshots, exit_basis = None, None
        if exit_inventory["status"] == "INVENTORIED":
            exit_snapshots, exit_basis = extract_snapshots(exit_path, exit_inventory, ticker, exit_date, expiration, pilot)
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
    return sorted(candidates, key=lambda row: row["candidate_id"])


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_dataset(
    source_root: Path,
    calendar_path: Path,
    calendar_sha256: str,
    output_dir: Path,
    *,
    pilot_path: Path = PILOT_PATH,
    pilot_sha256: str = PILOT_SHA256,
) -> dict[str, Any]:
    source_root, calendar_path, output_dir = (Path(os.path.abspath(path)) for path in (source_root, calendar_path, output_dir))
    if output_dir.exists():
        raise FileExistsError(f"immutable output exists: {output_dir}")
    pilot = load_pilot(pilot_path, pilot_sha256)
    sessions, calendar_rows = read_calendar(calendar_path, calendar_sha256)
    coverage, planned_sources = plan_calendar(source_root, sessions)
    inventory_by_path, source_inventory = inventory_sources(planned_sources)
    inventory = {
        "schema": "weekly_h2_source_inventory_v1", "calendar_path": str(calendar_path), "calendar_sha256": calendar_sha256,
        "calendar_rows": len(calendar_rows), "sources": source_inventory,
    }
    candidates = build_candidates(coverage, inventory_by_path, calendar_sha256, pilot)
    closing_by_path, closing_sources = inventory_sources(planned_sources)
    if closing_sources != source_inventory or set(closing_by_path) != set(inventory_by_path):
        raise DatasetError("source inventory changed before publication")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        candidates_path = staging / "candidates.jsonl"
        with candidates_path.open("x", encoding="utf-8") as handle:
            for row in candidates:
                handle.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
        _write_json(staging / "coverage.json", {"schema": "weekly_h2_coverage_v1", "calendar": calendar_rows, "rows": coverage})
        _write_json(staging / "inventory.json", inventory)
        manifest = {
            "schema": "weekly_h2_dataset_manifest_v1", "status": STATUS,
            "flags": {"fit_performed": False, "economic_evaluation_performed": False, "promotion_approved": False, "production_modified": False},
            "calendar": {"path": str(calendar_path), "sha256": calendar_sha256}, "files": {},
            "implementation_pins": {"build_weekly_h2_dataset.py": sha256_file(Path(__file__).resolve()), "weekly_multiday_source_pilot.py": pilot_sha256},
        }
        for name, rows_count in (("candidates.jsonl", len(candidates)), ("coverage.json", len(coverage)), ("inventory.json", len(source_inventory))):
            path = staging / name
            manifest["files"][name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path), "rows": rows_count}
        _write_json(staging / "manifest.json", manifest)
        if output_dir.exists():
            raise FileExistsError(f"publication target appeared: {output_dir}")
        staging.rename(output_dir)
    except BaseException as exc:
        try:
            _write_json(staging / "failure.json", {"status": "FAILED_PARTIAL_PRESERVED", "exception_type": type(exc).__name__, "message": str(exc)})
        except BaseException:
            pass
        raise
    return manifest


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build the frozen weekly H2 source-level dataset")
    parser.add_argument("--execute-reviewed-builder", action="store_true")
    parser.add_argument("--source-root", default=str(SOURCE_ROOT))
    parser.add_argument("--calendar", default=str(CALENDAR_PATH))
    parser.add_argument("--calendar-sha256", default=CALENDAR_SHA256)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()
    if not args.execute_reviewed_builder:
        parser.error("real build requires --execute-reviewed-builder")
    if Path(os.path.abspath(args.source_root)) != Path(os.path.abspath(SOURCE_ROOT)) or Path(os.path.abspath(args.calendar)) != Path(os.path.abspath(CALENDAR_PATH)) or Path(os.path.abspath(args.output_dir)) != Path(os.path.abspath(OUTPUT_DIR)):
        parser.error("real CLI roots are frozen; fixtures must use the Python API")
    build_dataset(Path(args.source_root), Path(args.calendar), args.calendar_sha256, Path(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
