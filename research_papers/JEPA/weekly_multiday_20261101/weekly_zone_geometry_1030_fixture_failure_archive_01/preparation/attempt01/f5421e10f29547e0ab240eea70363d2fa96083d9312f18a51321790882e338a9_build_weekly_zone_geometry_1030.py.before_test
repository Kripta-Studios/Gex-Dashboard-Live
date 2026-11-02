"""Causal state-60 zone geometry producer.

Synthetic implementation authority only until a complete reviewed B binding is
supplied.  The CLI fails before creating runtime paths when any authority is
pending.  It never calls build_day, reads outcomes, or selects weekly options.
"""

from __future__ import annotations

import os

for _thread_var in (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS",
    "ARROW_NUM_THREADS", "POLARS_MAX_THREADS", "TBB_NUM_THREADS",
    "NUMBA_NUM_THREADS",
):
    os.environ[_thread_var] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from datetime import datetime, time as Time, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PureWindowsPath
import re
import shutil
import stat
import sys
from typing import Any, Callable, Iterator, Mapping, MutableMapping, Sequence
import uuid

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


STATUS = "C_GEOMETRY_1030_CLOSED"
BINDING_SCHEMA = "c_geometry_1030_runtime_binding_v1"
BINDING_STATUS = "PASS_FINAL_C_RUNTIME_BINDING"
ANCHOR_SCHEMA = "C_GEOMETRY_1030_ANCHOR_V1"
MIN_FREE = 2_000_000_000
CALENDAR_SEMANTIC_BYTES = 137_640
CALENDAR_SEMANTIC_SHA256 = "13bc456a32c6dc711fffb71ef24375ecd5e455c11a9efedfb117b9ad903fb929"
CACHE_ADMISSION_BYTES = 5_104_757
CACHE_ADMISSION_SHA256 = "e0b4512791adbe70642d8ca83391dd4f0379037aae02f2af4888242bab3b0e14"
RESOURCE_HELPER_BYTES = 31_463
RESOURCE_HELPER_SHA256 = "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"
RUNTIME_VERSIONS = {"numpy": "2.3.5", "pyarrow": "23.0.1"}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
DATE8 = re.compile(r"[0-9]{8}\Z")
TICKER_ORDINAL = {"SPY": 0, "QQQ": 1, "SPXW": 2}
ENGINE_PINS = {
    "level_engine.py": "70cc5d20990d971d16299fd008ff8e05ac99f99a6a2917a202fcb9a5f413b7c6",
    "session_level_engine.py": "f93d3be334a2326dbec5d742e217bce63449e1beaf46b35fa46be83f25548883",
    "session_clock.py": "1e63cf2d314caea14dd8b0b8f025f647d67bf8df58f246613975891a256f51e9",
    "session_cache.py": "6300a7f8e5c6c99101d32d642081f4b8dec170d3c40f2751c27f1642d55466f1",
    "build_cache.py": "985e87dcbd1e73289b58e4576445e47e73a6edea13e5ac73dde3ad629180d69f",
}
CONTRACT_PINS = {
    "C_GEOMETRY_1030_ADMISSION_CONTRACT_20261102.md": "c28572543c1658ab87b1083d60bfdfbdc059c57960c5240c54f98bef5cdd8027",
    "C_GEOMETRY_1030_OPERATIONAL_DRAFT_20261102.md": "88f76551957e73e37c5dd816b00ec17d035132186df5071be10a5c534368cb3f",
    "C_GEOMETRY_PARALLEL_PREPARATION_AMENDMENT_20261102.md": "f32d3bb23a830c9c67197926ab9defa847e5b347422b90fcf1d54d5bdb09b237",
    "C_GEOMETRY_PARALLEL_PREPARATION_REVIEW_20261102.md": "b3b056d2d447e407902a99d8567b437479ce1ee99e7efc7f62146e47c1fa2580",
    "C_GEOMETRY_1030_BINDING_FEASIBILITY_20261102.md": "149fb9f9ddd3a01be24af1fd5f461a9ed7e0abad84d417837f11aff562d2f88a",
    "C_GEOMETRY_WINDOWS_PUBLICATION_FEASIBILITY_20261102.md": "f16d1a1c418fb51b5c5b180719c7a762ba338817a183c6006d472bc34ce13f31",
}
ARRAY_NAMES = (
    "time_ns", "strike", "right", "bid", "ask", "delta", "iv", "vega",
    "theta", "row_flags", "spot", "spot_valid", "oi_contract_idx",
    "oi_value", "oi_available_ns", "oi_valid",
)
OPTIONAL_UNOPENED_ARRAY = "underlying_age_ms"
FINAL_B_FLAG_KEYS = {
    "actions_read", "candidates_read", "context_feature_arrays_read",
    "economic_evaluation_performed", "fit_performed", "inference_performed",
    "labels_read", "models_read", "option_raw_values_read", "outcomes_read",
    "parquet_footers_read", "pnl_computed", "promotion_approved", "replay_performed",
    "risk_or_qty_computed", "selected_policy", "spot_cache_arrays_read", "technical_ready",
}
OUTPUT_NAMES = (
    "geometry_states_1030.parquet", "geometry_levels_1030.parquet",
    "coverage.json", "manifest.json",
)
B_OUTPUT_NAMES = {
    "cache_admission.jsonl", "decision_contracts.parquet",
    "option_quote_observations.parquet", "segment_coverage.parquet",
    "source_admission.jsonl", "spot_coverage.jsonl", "spot_paths.parquet",
    "summary.json",
}
B_OUTPUT_ROWS = {
    "cache_admission.jsonl": 2790,
    "decision_contracts.parquet": 3240,
    "option_quote_observations.parquet": 3_606_310,
    "segment_coverage.parquet": 9720,
    "source_admission.jsonl": 2784,
    "spot_coverage.jsonl": 2790,
    "spot_paths.parquet": 1_086_570,
    "summary.json": 1,
}
B_AUTHORITY_KEYS = {
    "stage_a_entry_plan", "stage_a_weekly_sources", "stage_a_summary",
    "stage_a_manifest", "stage_a_audit", "stage_a_audit_manifest",
    "stage_a_audit_exit", "h1_inventory", "h1_inventory_manifest",
    "h1_manifest", "q3_inventory", "q3_inventory_manifest", "q3_manifest",
    "bridge_inventory", "bridge_inventory_manifest", "bridge_manifest",
    "unified_calendar", "h1_context_inventory",
    "h1_context_inventory_manifest", "h1_context_manifest",
    "q3_context_inventory", "q3_context_inventory_manifest",
    "q3_context_manifest", "selector_builder_v2", "normalization_pilot",
    "original_value_path_contract", "prior_producer_exit",
    "prior_producer_failure", "prior_producer_journal",
}
SEMANTIC_STATE_COLUMNS = (
    "calendar_ordinal", "ticker", "trade_date", "authority_period",
    "session_kind", "close_i", "source_status", "geometry_status",
    "missing_reason", "state_i", "state_clock_local", "formed_from_start",
    "formed_from_end", "first_available_at", "spot_1030", "ib_observed",
    "ib_low", "ib_high", "ib_range", "band", "tau_years", "level_count",
    "known_contract_count", "oi_known_count", "oi_missing_count",
    "fib_component_count", "call_oi_wall_count", "put_oi_wall_count",
    "call_gamma_wall_count", "put_gamma_wall_count",
)
SEMANTIC_LEVEL_COLUMNS = (
    "calendar_ordinal", "cluster_ordinal", "anchor_id", "ticker",
    "trade_date", "session_kind", "close_i", "state_i",
    "first_available_at", "center", "band", "source_mask", "n_components",
    "semantic_components_json",
)


class GeometryError(RuntimeError):
    """Fatal admission, scientific, or publication error."""

    def __init__(self, message: str, exit_code: int = 14):
        super().__init__(message)
        self.exit_code = exit_code


def require(condition: Any, message: str, exit_code: int = 14) -> None:
    if not condition:
        raise GeometryError(message, exit_code)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: Any, newline: bool = False) -> bytes:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return raw + (b"\n" if newline else b"")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compact_pin(path: Path) -> dict[str, Any]:
    before = path.stat()
    digest = sha256_file(path)
    after = path.stat()
    require(
        (before.st_size, before.st_mtime_ns, before.st_dev, before.st_ino)
        == (after.st_size, after.st_mtime_ns, after.st_dev, after.st_ino),
        f"file drift while hashing: {path}", 13,
    )
    return {"path": str(path), "bytes": after.st_size, "sha256": digest}


def physical_identity(path: Path) -> list[int]:
    value = path.lstat()
    return [int(value.st_dev), int(value.st_ino)]


def physical_snapshot(path: Path) -> list[int]:
    value = path.lstat()
    return [int(value.st_dev), int(value.st_ino), int(value.st_size), int(value.st_mtime_ns)]


def admitted_snapshot(path: Path, label: str) -> dict[str, Any]:
    guard_regular_file(path, label)
    before_identity = physical_identity(path)
    before_stat = physical_snapshot(path)
    pin = compact_pin(path)
    guard_regular_file(path, label)
    after_identity = physical_identity(path)
    require(after_identity == before_identity, label + " physical identity drift", 13)
    require(physical_snapshot(path) == before_stat, label + " physical stat drift", 13)
    return {"pin": pin, "physical_identity": before_identity, "stat_identity": before_stat}


def require_snapshot(path: Path, expected: Mapping[str, Any], label: str) -> dict[str, Any]:
    actual = admitted_snapshot(path, label)
    require(actual == expected, label + " snapshot drift", 13)
    return actual


def validate_sha(value: Any, label: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, label)
    return value


def validate_pin(value: Any, label: str) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == {"path", "bytes", "sha256"}, label)
    require(isinstance(value["path"], str) and value["path"], label + " path")
    require(type(value["bytes"]) is int and value["bytes"] >= 0, label + " bytes")
    validate_sha(value["sha256"], label + " sha256")
    return dict(value)


def verify_pin(value: Mapping[str, Any], label: str) -> Path:
    pin = validate_pin(value, label)
    path = Path(pin["path"])
    guard_regular_file(path, label)
    actual = compact_pin(path)
    require(actual == pin, label + " pin mismatch", 13)
    return path


def guard_regular_file(path: Path, label: str) -> None:
    raw = str(path)
    pure = PureWindowsPath(raw)
    require(pure.is_absolute() and "." not in pure.parts and ".." not in pure.parts, label + " lexical path", 11)
    require(path.exists(), label + " exists", 11)
    for item in [path, *path.parents]:
        value = item.lstat()
        attributes = int(getattr(value, "st_file_attributes", 0))
        require(not item.is_symlink() and not (attributes & 0x400), label + " reparse path", 11)
        if str(item) == path.anchor:
            break
    value = path.lstat()
    require(stat.S_ISREG(value.st_mode) and value.st_nlink == 1, label + " regular single-link file", 11)


def contains_pending(value: Any) -> bool:
    if isinstance(value, str):
        return "PENDING" in value.upper()
    if isinstance(value, Mapping):
        return any(contains_pending(k) or contains_pending(v) for k, v in value.items())
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return any(contains_pending(item) for item in value)
    return False


def states_schema() -> pa.Schema:
    fields = [
        ("calendar_ordinal", pa.int32(), False), ("ticker", pa.utf8(), False),
        ("trade_date", pa.date32(), False), ("authority_period", pa.utf8(), False),
        ("session_kind", pa.utf8(), False), ("close_i", pa.int16(), False),
        ("source_status", pa.utf8(), False), ("geometry_status", pa.utf8(), False),
        ("missing_reason", pa.utf8(), True), ("state_i", pa.int16(), False),
        ("state_clock_local", pa.timestamp("ns"), False),
        ("formed_from_start", pa.timestamp("ns"), True),
        ("formed_from_end", pa.timestamp("ns"), True),
        ("first_available_at", pa.timestamp("ns"), True),
        ("spot_1030", pa.float64(), True), ("ib_observed", pa.int16(), True),
        ("ib_low", pa.float64(), True), ("ib_high", pa.float64(), True),
        ("ib_range", pa.float64(), True), ("band", pa.float64(), True),
        ("tau_years", pa.float64(), True), ("level_count", pa.int16(), False),
        ("known_contract_count", pa.int32(), True),
        ("oi_known_count", pa.int32(), True), ("oi_missing_count", pa.int32(), True),
        ("fib_component_count", pa.int16(), True),
        ("call_oi_wall_count", pa.int8(), True), ("put_oi_wall_count", pa.int8(), True),
        ("call_gamma_wall_count", pa.int8(), True),
        ("put_gamma_wall_count", pa.int8(), True),
        ("cache_metadata_path", pa.utf8(), True),
        ("cache_metadata_sha256", pa.utf8(), True),
        ("cache_npz_path", pa.utf8(), True), ("cache_npz_sha256", pa.utf8(), True),
        ("clock_basis", pa.utf8(), True), ("oi_clock_basis", pa.utf8(), True),
        ("oi_assumed_availability", pa.utf8(), True),
        ("clock_delay_applied", pa.bool_(), True),
        ("receipt_status", pa.utf8(), False),
    ]
    return pa.schema([pa.field(name, typ, nullable=null) for name, typ, null in fields])


def levels_schema() -> pa.Schema:
    fields = [
        ("calendar_ordinal", pa.int32()), ("cluster_ordinal", pa.int16()),
        ("anchor_id", pa.utf8()), ("ticker", pa.utf8()),
        ("trade_date", pa.date32()), ("session_kind", pa.utf8()),
        ("close_i", pa.int16()), ("state_i", pa.int16()),
        ("first_available_at", pa.timestamp("ns")), ("center", pa.float64()),
        ("band", pa.float64()), ("source_mask", pa.int16()),
        ("n_components", pa.int16()), ("semantic_components_json", pa.utf8()),
        ("provenance_components_json", pa.utf8()), ("cache_npz_path", pa.utf8()),
        ("cache_npz_sha256", pa.utf8()), ("clock_basis", pa.utf8()),
        ("oi_clock_basis", pa.utf8()), ("receipt_status", pa.utf8()),
    ]
    return pa.schema([pa.field(name, typ, nullable=False) for name, typ in fields])


def canonical_f64(value: Any) -> str:
    number = float(value)
    require(math.isfinite(number), "anchor double must be finite")
    return "0x0.0p+0" if number == 0.0 else number.hex().lower()


def semantic_components(
    components_json: str, strike: np.ndarray, right: np.ndarray,
) -> list[dict[str, Any]]:
    raw = json.loads(components_json)
    require(isinstance(raw, list) and raw, "level components")
    normalized: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for item in raw:
        require(isinstance(item, dict), "level component object")
        center = float(item["center"])
        mask = int(item["source_mask"])
        name = str(item["name"])
        if name == "FIB":
            ratio = float(item["ratio"])
            value = {
                "kind": "FIB", "name": name, "source_mask": mask,
                "ratio_f64": canonical_f64(ratio), "center_f64": canonical_f64(center),
            }
            key = (center, mask, name, -1, -math.inf, ratio, -math.inf)
        else:
            ci = int(item["contract_i"])
            require(0 <= ci < len(strike), "component contract_i")
            weight = float(item["weight"])
            side = int(right[ci])
            strike_value = float(strike[ci])
            value = {
                "kind": "WALL", "name": name, "source_mask": mask, "right": side,
                "strike_f64": canonical_f64(strike_value),
                "weight_f64": canonical_f64(weight), "center_f64": canonical_f64(center),
            }
            key = (center, mask, name, side, strike_value, -math.inf, weight)
        normalized.append((key, value))
    normalized.sort(key=lambda pair: pair[0])
    return [value for _, value in normalized]


def anchor_id(
    ticker: str, day: str, close_i: int, level: Mapping[str, Any],
    components: Sequence[Mapping[str, Any]], band: float,
) -> str:
    payload = {
        "anchor_schema": ANCHOR_SCHEMA, "ticker": ticker,
        "date": datetime.strptime(day, "%Y%m%d").strftime("%Y-%m-%d"),
        "state_i": 60, "close_i": int(close_i),
        "cluster_ordinal": int(level["level_id"]),
        "center_f64": canonical_f64(level["center"]),
        "band_f64": canonical_f64(band), "source_mask": int(level["source_mask"]),
        "components": list(components),
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def parse_day(value: Any) -> str:
    require(isinstance(value, str) and DATE8.fullmatch(value) is not None, "date YYYYMMDD")
    datetime.strptime(value, "%Y%m%d")
    return value


def local_ns(day: str, hour: int, minute: int) -> int:
    stamp = datetime.combine(datetime.strptime(day, "%Y%m%d").date(), Time(hour, minute))
    return int(np.datetime64(stamp, "ns").astype(np.int64))


def normalize_calendar(
    document: Mapping[str, Any], *, expected_first: Mapping[str, Any] | None = None,
    expected_last: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], bytes]:
    require(set(document) == {"schema", "rows"}, "calendar top-level keys")
    require(document["schema"] == "weekly_h2_boundary_unified_calendar_v1", "calendar schema")
    rows = document["rows"]
    require(isinstance(rows, list) and len(rows) == 2790, "calendar row count")
    triples: list[tuple[str, str, int]] = []
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"close_i", "date", "ticker"}, "calendar row")
        ticker, day, close_i = row["ticker"], parse_day(row["date"]), row["close_i"]
        require(ticker in TICKER_ORDINAL and type(close_i) is int and close_i in (210, 390), "calendar values")
        triples.append((ticker, day, close_i))
    require(len({(ticker, day) for ticker, day, _ in triples}) == 2790, "calendar unique identities")
    dates = {ticker: {day for t, day, _ in triples if t == ticker} for ticker in TICKER_ORDINAL}
    require(all(len(value) == 930 for value in dates.values()), "930 dates per ticker")
    require(dates["SPY"] == dates["QQQ"] == dates["SPXW"], "calendar identical dates")
    require(sum(close_i == 210 for _, _, close_i in triples) == 24, "24 short sessions")
    require(triples == sorted(triples, key=lambda value: (value[0], value[1])), "calendar raw order")
    canonical = sorted(triples, key=lambda value: (value[1], TICKER_ORDINAL[value[0]]))
    result = [
        {"calendar_ordinal": ordinal, "ticker": ticker, "date": day,
         "close_i": close_i, "session_kind": "FULL" if close_i == 390 else "SHORT"}
        for ordinal, (ticker, day, close_i) in enumerate(canonical)
    ]
    semantic = b"".join(
        canonical_json_bytes({"close_i": row["close_i"], "date": row["date"], "ticker": row["ticker"]}, newline=True)
        for row in result
    )
    first = expected_first or {"calendar_ordinal": 0, "ticker": "SPY", "date": "20230103", "close_i": 390, "session_kind": "FULL"}
    last = expected_last or {"calendar_ordinal": 2789, "ticker": "SPXW", "date": "20260917", "close_i": 390, "session_kind": "FULL"}
    require(result[0] == dict(first), "calendar first")
    require(result[-1] == dict(last), "calendar last")
    return result, semantic


def parse_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        for line_number, line in enumerate(stream, 1):
            require(line.endswith("\n") and line.strip(), f"JSONL line {line_number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"JSONL object {line_number}")
            rows.append(value)
    return rows


def normalize_cache_admission(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    expected = {
        "ticker", "ticker_ordinal", "date", "session_kind", "close_i", "cache_status",
        "missing_reason", "authority", "feature_metadata_path", "feature_metadata_bytes",
        "feature_metadata_sha256", "cache_metadata_path", "cache_metadata_bytes",
        "cache_metadata_sha256", "npz_path", "npz_bytes", "npz_sha256", "cache_version",
        "binding_source_sha256", "binding_source_metadata_sha256", "stats",
    }
    require(len(rows) == 2790, "cache admission row count")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row_value in rows:
        row = dict(row_value)
        require(set(row) == expected, "cache admission keys")
        ticker, day = row["ticker"], parse_day(row["date"])
        require(ticker in TICKER_ORDINAL and row["ticker_ordinal"] == TICKER_ORDINAL[ticker], "cache identity")
        require(row["session_kind"] in ("FULL", "SHORT") and row["close_i"] in (390, 210), "cache clock")
        require(row["authority"] in ("H1", "Q3"), "cache authority")
        require(row["cache_status"] in ("AVAILABLE", "MISSING"), "cache status")
        key = (ticker, day)
        require(key not in result, "duplicate cache identity")
        if row["cache_status"] == "AVAILABLE":
            require(row["missing_reason"] is None, "available missing reason")
            for prefix in ("cache_metadata", "npz"):
                validate_pin({"path": row[prefix + "_path"], "bytes": row[prefix + "_bytes"], "sha256": row[prefix + "_sha256"]}, prefix)
            require(row["binding_source_sha256"] == row["npz_sha256"], "npz binding")
            require(row["binding_source_metadata_sha256"] == row["cache_metadata_sha256"], "metadata binding")
        else:
            require(row["missing_reason"] == "MISSING_SOURCE", "missing reason")
            for key_name in ("cache_metadata_path", "cache_metadata_bytes", "cache_metadata_sha256", "npz_path", "npz_bytes", "npz_sha256"):
                require(row[key_name] is None, "missing cache pin")
        result[key] = row
    return result


def validate_final_b_bundle(value: Any, binding: Mapping[str, Any]) -> None:
    require(isinstance(value, dict) and set(value) == {
        "schema", "status", "producer", "auditor", "authority_inputs",
        "calendar", "flags", "data_scope",
    }, "final B bundle keys")
    require(value["schema"] == "weekly_zone_event_value_paths_final_admission_v1", "final B schema")
    require(value["status"] == "PASS_FINAL_B_ADMISSION" and value["data_scope"] == "SEEN_DEVELOPMENT", "final B status")
    producer = value["producer"]
    require(isinstance(producer, dict) and set(producer) == {"manifest", "outputs", "observer"}, "final B producer")
    validate_pin(producer["manifest"], "final B producer manifest")
    require(isinstance(producer["outputs"], dict) and set(producer["outputs"]) == B_OUTPUT_NAMES, "final B producer outputs")
    for name, pin in producer["outputs"].items():
        validate_pin(pin, "final B producer output " + name)
    require(isinstance(producer["observer"], dict) and set(producer["observer"]) == {"exit", "process", "journal"}, "final B producer observer")
    for name, pin in producer["observer"].items():
        validate_pin(pin, "final B producer observer " + name)
    cache_pin = producer["outputs"].get("cache_admission.jsonl")
    require(cache_pin == binding["b_final"]["cache_admission"], "final B cache admission crosspin")
    auditor = value["auditor"]
    require(isinstance(auditor, dict) and set(auditor) == {"audit", "manifest", "exit", "process", "journal"}, "final B auditor")
    for name, pin in auditor.items():
        validate_pin(pin, "final B auditor " + name)
    authority_inputs = value["authority_inputs"]
    require(isinstance(authority_inputs, dict) and set(authority_inputs) == B_AUTHORITY_KEYS, "final B authority inputs")
    for name, pin in authority_inputs.items():
        require(isinstance(name, str) and name, "final B authority identity")
        validate_pin(pin, "final B authority " + name)
    calendar = value["calendar"]
    require(isinstance(calendar, dict) and set(calendar) == {"raw_file_pin", "semantic_jsonl", "identity_set_preserved", "close_i_preserved"}, "final B calendar")
    require(calendar["raw_file_pin"] == binding["b_final"]["raw_calendar"], "final B raw calendar crosspin")
    require(calendar["raw_file_pin"] == authority_inputs["unified_calendar"], "final B intentional calendar duplicate")
    require(calendar["semantic_jsonl"] == binding["b_final"]["calendar_semantic"], "final B semantic calendar crosspin")
    require(calendar["identity_set_preserved"] is True and calendar["close_i_preserved"] is True, "final B calendar preservation")
    flags = value["flags"]
    require(isinstance(flags, dict) and set(flags) == FINAL_B_FLAG_KEYS, "final B flags")
    require(flags["option_raw_values_read"] is True and flags["parquet_footers_read"] is True and flags["spot_cache_arrays_read"] is True, "final B admitted reads")
    require(flags["selected_policy"] is None, "final B selected policy")
    for key in FINAL_B_FLAG_KEYS - {"option_raw_values_read", "parquet_footers_read", "spot_cache_arrays_read", "selected_policy"}:
        require(flags[key] is False, "final B false flag " + key)
    role_pins = {
        "producer.manifest": producer["manifest"],
        **{"producer.outputs." + name: pin for name, pin in producer["outputs"].items()},
        **{"producer.observer." + name: pin for name, pin in producer["observer"].items()},
        **{"auditor." + name: pin for name, pin in auditor.items()},
        **{"authority_inputs." + name: pin for name, pin in authority_inputs.items()},
        "calendar.raw_file_pin": calendar["raw_file_pin"],
    }
    require(len(role_pins) == 47, "final B pin occurrence count")
    by_path: dict[str, list[str]] = {}
    for role, pin in role_pins.items():
        by_path.setdefault(os.path.normcase(os.path.abspath(pin["path"])), []).append(role)
    require(len(by_path) == 46, "final B distinct path count")
    duplicates = [set(roles) for roles in by_path.values() if len(roles) > 1]
    require(duplicates == [{"authority_inputs.unified_calendar", "calendar.raw_file_pin"}], "final B illegal role alias")


def _read_pinned_json(pin: Mapping[str, Any], label: str) -> dict[str, Any]:
    path = verify_pin(pin, label)
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), label + " object")
    return value


def _validate_retained_exit(value: Mapping[str, Any], label: str) -> None:
    require(type(value.get("exit_code")) is int and value["exit_code"] == 0, label + " exit0")
    require(type(value.get("value_child_exit_code")) is int and value["value_child_exit_code"] == 0, label + " child exit0")
    require(value.get("changed_pins") == [] and value.get("metadata_error") is None, label + " clean closure")
    require(value.get("retry") is False and type(value.get("pid")) is int and value["pid"] > 0, label + " retained process")
    require(type(value.get("creation_epoch")) in (int, float) and not isinstance(value.get("creation_epoch"), bool), label + " creation epoch")


def validate_final_b_closure(value: Mapping[str, Any]) -> None:
    """Reconstruct the retained producer/auditor proof rather than trust PASS text."""
    producer = value["producer"]
    producer_manifest = _read_pinned_json(producer["manifest"], "final B producer manifest")
    require(producer_manifest.get("schema") == "weekly_zone_event_value_paths_manifest_v2_calendar_normalized", "producer manifest schema")
    require(producer_manifest.get("status") == "COMPLETE_OUTCOME_FREE_VALUE_PATHS", "producer manifest status")
    manifest_outputs = producer_manifest.get("outputs")
    require(isinstance(manifest_outputs, dict) and set(manifest_outputs) == B_OUTPUT_NAMES, "producer manifest output set")
    projected_outputs: dict[str, dict[str, Any]] = {}
    for name, record in manifest_outputs.items():
        require(isinstance(record, dict) and set(record) == {"path", "bytes", "sha256", "rows"}, "producer manifest output record")
        rows = record["rows"]
        require(type(rows) is int and rows == B_OUTPUT_ROWS[name], "producer manifest output rows")
        projected_outputs[name] = {key: record[key] for key in ("path", "bytes", "sha256")}
    require(projected_outputs == producer["outputs"], "producer output projection closure")
    require(producer_manifest.get("authority_inputs") == value["authority_inputs"], "producer authority closure")
    producer_exit = _read_pinned_json(producer["observer"]["exit"], "final B producer exit")
    _validate_retained_exit(producer_exit, "producer")
    producer_process = _read_pinned_json(producer["observer"]["process"], "final B producer process")
    require(producer_process.get("pid") == producer_exit["pid"] and producer_process.get("creation_epoch") == producer_exit["creation_epoch"], "producer process identity")

    auditor = value["auditor"]
    audit = _read_pinned_json(auditor["audit"], "final B audit")
    require(audit.get("schema") == "weekly_zone_event_value_paths_audit_v2_calendar_normalized" and audit.get("status") == "PASS", "auditor PASS document")
    audit_manifest = _read_pinned_json(auditor["manifest"], "final B audit manifest")
    require(audit_manifest.get("schema") == "weekly_zone_event_value_paths_audit_manifest_v2_calendar_normalized" and audit_manifest.get("status") == "PASS", "auditor manifest PASS")
    require(audit_manifest.get("authority_inputs") == value["authority_inputs"], "auditor authority closure")
    audit_exit = _read_pinned_json(auditor["exit"], "final B audit exit")
    _validate_retained_exit(audit_exit, "auditor")
    audit_process = _read_pinned_json(auditor["process"], "final B audit process")
    require(audit_process.get("pid") == audit_exit["pid"] and audit_process.get("creation_epoch") == audit_exit["creation_epoch"], "auditor process identity")
    for label, pin in (("producer", producer["observer"]["journal"]), ("auditor", auditor["journal"])):
        path = verify_pin(pin, "final B " + label + " journal")
        rows = parse_jsonl(path)
        require(rows and all(isinstance(row, dict) for row in rows), label + " journal records")
        require(all(row.get("event") in {"STARTED", "COMPLETED", "ERROR"} for row in rows), label + " journal event schema")
        require(not any(row.get("event") == "ERROR" for row in rows), label + " journal error")
        require(rows[-1].get("event") == "COMPLETED", label + " journal closure")
        if label == "producer":
            require(all("kind" in row and "stage" not in row for row in rows), "producer journal envelope")
        else:
            require(all("stage" in row and "kind" not in row for row in rows), "auditor journal envelope")


def final_b_proof_pins(value: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    pins = {
        "b_producer_manifest": value["producer"]["manifest"],
        **{"b_producer_output:" + name: pin for name, pin in value["producer"]["outputs"].items()},
        **{"b_producer_observer:" + name: pin for name, pin in value["producer"]["observer"].items()},
        **{"b_auditor:" + name: pin for name, pin in value["auditor"].items()},
        **{"b_authority:" + name: pin for name, pin in value["authority_inputs"].items()},
    }
    return pins


def validate_cache_metadata(
    metadata: Mapping[str, Any], row: Mapping[str, Any], arrays: Mapping[str, np.ndarray],
) -> None:
    require(metadata.get("ticker") == row["ticker"] and metadata.get("date") == row["date"], "cache metadata identity")
    require(metadata.get("version") == row["cache_version"], "cache metadata version")
    require(metadata.get("sha256") == row["npz_sha256"], "cache metadata npz hash")
    require(metadata.get("timezone_convention") == "America/New_York naive", "cache timezone")
    require(metadata.get("clock_basis") in ("NATIVE_STORED_TIMESTAMP", "ASSUMED_UNDERLYING_SNAPSHOT_CLOCK"), "clock basis")
    oi_basis = metadata.get("oi_clock_basis")
    require(oi_basis in ("NATIVE_STORED_TIMESTAMP", "ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT"), "OI clock basis")
    assumed = metadata.get("oi_assumed_availability")
    if oi_basis == "NATIVE_STORED_TIMESTAMP":
        require(assumed is None, "native OI assumed availability")
    else:
        expected_assumed = datetime.strptime(row["date"], "%Y%m%d").strftime("%Y-%m-%d 09:30:00")
        require(assumed == expected_assumed, "assumed OI availability")
    require(metadata.get("clock_delay_applied") is False, "clock delay literal")
    if row["session_kind"] == "SHORT":
        session_clock = metadata.get("session_clock")
        require(isinstance(session_clock, dict) and session_clock.get("close_i") == 210 and session_clock.get("n_slots") == 211, "short metadata clock")
    schema = metadata.get("array_schema")
    require(isinstance(schema, dict), "array schema")
    allowed = set(ARRAY_NAMES) | {OPTIONAL_UNOPENED_ARRAY}
    require(set(schema) in (set(ARRAY_NAMES), allowed), "cache array names")
    require(set(arrays) == set(ARRAY_NAMES), "opened array whitelist")
    for name, array in arrays.items():
        descriptor = schema[name]
        require(isinstance(descriptor, dict) and set(descriptor) == {"shape", "dtype"}, "array descriptor")
        require(list(array.shape) == descriptor["shape"] and str(array.dtype) == descriptor["dtype"], "array descriptor mismatch")


def load_cache_arrays(npz_path: Path) -> tuple[dict[str, np.ndarray], tuple[str, ...]]:
    arrays: dict[str, np.ndarray] = {}
    with np.load(npz_path, allow_pickle=False) as stored:
        names = tuple(stored.files)
        require(set(names) in (set(ARRAY_NAMES), set(ARRAY_NAMES) | {OPTIONAL_UNOPENED_ARRAY}), "NPZ array names")
        for name in ARRAY_NAMES:
            arrays[name] = stored[name]
    return arrays, names


def load_pure_engines(engine_paths: Mapping[str, Path]) -> tuple[Any, Any]:
    for name, expected in ENGINE_PINS.items():
        require(name in engine_paths and sha256_file(engine_paths[name]) == expected, "engine pin " + name)
    package = "c_geometry_pinned_engines"
    package_module = type(sys)(package)
    package_module.__path__ = [str(engine_paths["level_engine.py"].parent)]
    sys.modules[package] = package_module
    loaded: dict[str, Any] = {}
    for leaf in ("level_engine.py", "session_clock.py", "session_level_engine.py"):
        module_name = leaf[:-3]
        qualified = package + "." + module_name
        spec = importlib.util.spec_from_file_location(qualified, engine_paths[leaf])
        require(spec is not None and spec.loader is not None, "engine import spec")
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)
        loaded[module_name] = module
    require(not hasattr(loaded["session_level_engine"], "__c_geometry_mutated__"), "engine mutation marker")
    return loaded["session_level_engine"], loaded["session_clock"]


def _base_state(calendar: Mapping[str, Any], admission: Mapping[str, Any]) -> dict[str, Any]:
    day = calendar["date"]
    source_status = admission["cache_status"]
    return {
        "calendar_ordinal": calendar["calendar_ordinal"], "ticker": calendar["ticker"],
        "trade_date": datetime.strptime(day, "%Y%m%d").date(),
        "authority_period": admission["authority"], "session_kind": calendar["session_kind"],
        "close_i": calendar["close_i"], "source_status": source_status,
        "geometry_status": "MISSING_SOURCE" if source_status == "MISSING" else None,
        "missing_reason": "SOURCE_PLAN_MISSING" if source_status == "MISSING" else None,
        "state_i": 60, "state_clock_local": local_ns(day, 10, 30),
        "formed_from_start": None, "formed_from_end": None, "first_available_at": None,
        "spot_1030": None, "ib_observed": None, "ib_low": None, "ib_high": None,
        "ib_range": None, "band": None, "tau_years": None, "level_count": 0,
        "known_contract_count": None, "oi_known_count": None, "oi_missing_count": None,
        "fib_component_count": None, "call_oi_wall_count": None,
        "put_oi_wall_count": None, "call_gamma_wall_count": None,
        "put_gamma_wall_count": None,
        "cache_metadata_path": admission["cache_metadata_path"],
        "cache_metadata_sha256": admission["cache_metadata_sha256"],
        "cache_npz_path": admission["npz_path"], "cache_npz_sha256": admission["npz_sha256"],
        "clock_basis": None, "oi_clock_basis": None, "oi_assumed_availability": None,
        "clock_delay_applied": None,
        "receipt_status": "NOT_APPLICABLE" if source_status == "MISSING" else "UNVERIFIED",
    }


def compute_identity_geometry(
    calendar: Mapping[str, Any], admission: Mapping[str, Any], metadata: Mapping[str, Any],
    cache: Mapping[str, np.ndarray], engine: Any, clocks: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    state = _base_state(calendar, admission)
    require(admission["cache_status"] == "AVAILABLE", "compute missing identity")
    require(calendar["session_kind"] == admission["session_kind"] and calendar["close_i"] == admission["close_i"], "calendar/cache clock")
    clock = clocks.FULL if calendar["close_i"] == 390 else clocks.SHORT
    engine.validate_cache(cache, clock)
    times = np.asarray(cache["time_ns"], dtype=np.int64)
    expected_start = local_ns(calendar["date"], 9, 30)
    require(times[0] == expected_start and times[60] == local_ns(calendar["date"], 10, 30), "cache local clock")
    state.update({
        "formed_from_start": int(times[0]), "formed_from_end": int(times[59]),
        "clock_basis": metadata["clock_basis"], "oi_clock_basis": metadata["oi_clock_basis"],
        "oi_assumed_availability": metadata.get("oi_assumed_availability"),
        "clock_delay_applied": metadata["clock_delay_applied"],
    })
    ib = engine.ib_bounds(cache)
    if ib is None:
        state["geometry_status"] = "INVALID_IB"
        return state, []
    low, high, observed = ib
    state.update({"ib_observed": int(observed), "ib_low": float(low), "ib_high": float(high), "ib_range": float(high - low)})
    spot = float(cache["spot"][60])
    valid_spot = bool(cache["spot_valid"][60]) and math.isfinite(spot) and spot > 0
    if not valid_spot:
        state["geometry_status"] = "INVALID_STATE60"
        return state, []
    band = max(0.05 * (high - low), 0.0001 * spot)
    oi_row = engine.available_oi_matrix(cache, clock)[60]
    known_row = engine.known_contract_matrix(cache)[60]
    levels = engine.causal_levels(cache, oi_row, 60, low, high, band, clock)
    strike = np.asarray(cache["strike"], dtype=np.float64)
    right = np.asarray(cache["right"])
    count_by_mask = {2: 0, 4: 0, 8: 0, 16: 0}
    level_rows: list[dict[str, Any]] = []
    for level in levels:
        raw = json.loads(level["components_json"])
        for component in raw:
            mask = int(component["source_mask"])
            if mask in count_by_mask:
                count_by_mask[mask] += 1
        components = semantic_components(level["components_json"], strike, right)
        semantic_text = canonical_json_bytes(components).decode("utf-8")
        level_rows.append({
            "calendar_ordinal": calendar["calendar_ordinal"],
            "cluster_ordinal": int(level["level_id"]),
            "anchor_id": anchor_id(calendar["ticker"], calendar["date"], calendar["close_i"], level, components, band),
            "ticker": calendar["ticker"], "trade_date": datetime.strptime(calendar["date"], "%Y%m%d").date(),
            "session_kind": calendar["session_kind"], "close_i": calendar["close_i"],
            "state_i": 60, "first_available_at": int(times[60]),
            "center": float(level["center"]), "band": float(band),
            "source_mask": int(level["source_mask"]), "n_components": int(level["n_components"]),
            "semantic_components_json": semantic_text,
            "provenance_components_json": level["components_json"],
            "cache_npz_path": admission["npz_path"], "cache_npz_sha256": admission["npz_sha256"],
            "clock_basis": metadata["clock_basis"], "oi_clock_basis": metadata["oi_clock_basis"],
            "receipt_status": "UNVERIFIED",
        })
    state.update({
        "geometry_status": "AVAILABLE_GEOMETRY", "first_available_at": int(times[60]),
        "spot_1030": spot, "band": float(band),
        "tau_years": (calendar["close_i"] - 60) * 60 / (365 * 86400),
        "level_count": len(level_rows), "known_contract_count": int(known_row.sum()),
        "oi_known_count": int((known_row & np.isfinite(oi_row)).sum()),
        "oi_missing_count": int((known_row & ~np.isfinite(oi_row)).sum()),
        "fib_component_count": 13, "call_oi_wall_count": count_by_mask[2],
        "put_oi_wall_count": count_by_mask[4], "call_gamma_wall_count": count_by_mask[8],
        "put_gamma_wall_count": count_by_mask[16],
    })
    return state, level_rows


def validate_rows(states: Sequence[Mapping[str, Any]], levels: Sequence[Mapping[str, Any]], expected_total: int = 2790) -> dict[str, int]:
    require(len(states) == expected_total, "state row count")
    require([row["calendar_ordinal"] for row in states] == list(range(expected_total)), "state order")
    statuses = {"MISSING_SOURCE", "INVALID_IB", "INVALID_STATE60", "AVAILABLE_GEOMETRY"}
    require(all(row["geometry_status"] in statuses for row in states), "geometry status")
    require(list(levels) == sorted(levels, key=lambda row: (row["calendar_ordinal"], row["cluster_ordinal"])), "level order")
    require(len({row["anchor_id"] for row in levels}) == len(levels), "anchor uniqueness")
    by_identity: dict[int, list[Mapping[str, Any]]] = {}
    for row in levels:
        by_identity.setdefault(row["calendar_ordinal"], []).append(row)
    for state in states:
        unit = by_identity.get(state["calendar_ordinal"], [])
        for level in unit:
            require(level["ticker"] == state["ticker"], "level/state ticker FK")
            require(level["trade_date"] == state["trade_date"], "level/state date FK")
            require(level["session_kind"] == state["session_kind"], "level/state session FK")
            require(level["close_i"] == state["close_i"], "level/state close_i FK")
            require(level["state_i"] == state["state_i"] == 60, "level/state state_i FK")
        require([row["cluster_ordinal"] for row in unit] == list(range(len(unit))), "cluster ordinals")
        require(state["level_count"] == len(unit), "level count")
        if state["geometry_status"] == "AVAILABLE_GEOMETRY":
            require(state["oi_known_count"] + state["oi_missing_count"] == state["known_contract_count"], "OI coverage")
    counts = {name: sum(row["geometry_status"] == name for row in states) for name in statuses}
    source_partitions = {
        "h1_full_available": sum(row["source_status"] == "AVAILABLE" and row["authority_period"] == "H1" and row["session_kind"] == "FULL" for row in states),
        "h1_short_available": sum(row["source_status"] == "AVAILABLE" and row["authority_period"] == "H1" and row["session_kind"] == "SHORT" for row in states),
        "q3_available": sum(row["source_status"] == "AVAILABLE" and row["authority_period"] == "Q3" for row in states),
        "h1_missing": sum(row["source_status"] == "MISSING" and row["authority_period"] == "H1" for row in states),
        "q3_missing": sum(row["source_status"] == "MISSING" and row["authority_period"] == "Q3" for row in states),
    }
    require(source_partitions == {
        "h1_full_available": 2595, "h1_short_available": 24,
        "q3_available": 153, "h1_missing": 6, "q3_missing": 12,
    }, "source/session partitions")
    counts.update(source_partitions)
    return counts


def table_from_rows(rows: Sequence[Mapping[str, Any]], schema: pa.Schema) -> pa.Table:
    columns = [pa.array([row[field.name] for row in rows], type=field.type) for field in schema]
    return pa.Table.from_arrays(columns, schema=schema)


def write_parquet(path: Path, table: pa.Table, row_groups: Sequence[tuple[int, int]]) -> None:
    with pq.ParquetWriter(
        path, table.schema, version="2.6", data_page_version="1.0",
        compression="zstd", compression_level=9, use_dictionary=False,
        write_statistics=True, store_schema=True,
    ) as writer:
        for start, length in row_groups:
            writer.write_table(table.slice(start, length), row_group_size=length)


def level_row_groups(levels: Sequence[Mapping[str, Any]], limit: int = 65_536) -> list[tuple[int, int]]:
    if not levels:
        return []
    groups: list[tuple[int, int]] = []
    start = 0
    while start < len(levels):
        end = start
        while end < len(levels):
            identity = levels[end]["calendar_ordinal"]
            unit_end = end + 1
            while unit_end < len(levels) and levels[unit_end]["calendar_ordinal"] == identity:
                unit_end += 1
            if end > start and unit_end - start > limit:
                break
            require(unit_end - end <= limit, "single identity exceeds row group")
            end = unit_end
        groups.append((start, end - start))
        start = end
    return groups


def write_json(path: Path, value: Any) -> None:
    with path.open("xb") as stream:
        stream.write(canonical_json_bytes(value, newline=True))
        stream.flush()
        os.fsync(stream.fileno())


def disk_gate(root: Path, observation: Mapping[str, Any]) -> dict[str, int]:
    require(set(observation) == {"available_ram_bytes", "free_commit_bytes"}, "resource observation keys")
    require(type(observation["available_ram_bytes"]) is int, "available RAM exact int")
    require(type(observation["free_commit_bytes"]) is int, "free commit exact int")
    disk = shutil.disk_usage(root).free
    require(type(disk) is int, "disk free exact int")
    result = {
        "available_ram_bytes": observation["available_ram_bytes"],
        "free_commit_bytes": observation["free_commit_bytes"],
        "disk_free_bytes": disk,
    }
    require(min(result.values()) >= MIN_FREE, "2GB resource gate", 12)
    return result


class Journal:
    def __init__(
        self, path: Path, gate: Callable[[], Mapping[str, int]], disk_root: Path,
        flusher: Callable[[Any], None] | None = None,
    ):
        self.path = path
        self._gate = gate
        self._disk_root = disk_root
        self._seq = 0
        self._flusher = flusher
        self._stream = path.open("x", encoding="utf-8", newline="\n")

    def _flush(self) -> None:
        self._stream.flush()
        if self._flusher is None:
            os.fsync(self._stream.fileno())
        else:
            self._flusher(self._stream)

    def close(self) -> None:
        self._flush()
        self._stream.close()

    def append(self, kind: str, identity: str, phase: str, paths: Sequence[str], gate: Mapping[str, Any], details: Mapping[str, Any]) -> None:
        record = {
            "seq": self._seq, "utc": utc_now(), "kind": kind, "identity": identity,
            "phase": phase, "paths": list(paths), "gate": dict(gate), "details": dict(details),
        }
        self._stream.write(canonical_json_bytes(record, newline=True).decode("utf-8"))
        self._flush()
        self._seq += 1

    @contextmanager
    def unit(self, kind: str, identity: str, paths: Sequence[str]) -> Iterator[MutableMapping[str, Any]]:
        gate = disk_gate(self._disk_root, self._gate())
        self.append(kind, identity, "START", paths, gate, {})
        details: dict[str, Any] = {}
        try:
            yield details
        except BaseException as exc:
            self.append(kind, identity, "ERROR", paths, gate, {"error_type": type(exc).__name__, "message": str(exc)})
            raise
        else:
            self.append(kind, identity, "COMPLETE", paths, gate, details)

    def prefix_snapshot(self) -> dict[str, Any]:
        self._flush()
        return {"prepublish_last_seq": self._seq - 1, "prepublish_prefix_sha256": sha256_file(self.path)}


def load_resource_helper(pin: Mapping[str, Any]) -> Callable[[], Mapping[str, int]]:
    path = verify_pin(pin, "resource helper")
    spec = importlib.util.spec_from_file_location("c_geometry_resource_helper", path)
    require(spec is not None and spec.loader is not None, "resource helper spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    observation = getattr(module, "observation", None)
    require(callable(observation), "resource helper observation")
    return observation


def validate_runtime_binding(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict), "binding object")
    expected = {"schema", "status", "contracts", "engines", "b_final", "resource_helper", "runtime", "runtime_roots", "windows_publication"}
    require(set(value) == expected, "binding keys")
    require(value["schema"] == BINDING_SCHEMA and value["status"] == BINDING_STATUS, "binding identity")
    require(not contains_pending(value), "binding contains PENDING")
    for name in (
        "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS",
        "ARROW_NUM_THREADS", "POLARS_MAX_THREADS", "TBB_NUM_THREADS",
        "NUMBA_NUM_THREADS",
    ):
        require(os.environ.get(name) == "1", "thread environment " + name)
    require(os.environ.get("CUDA_VISIBLE_DEVICES") == "-1", "CUDA environment")
    require(isinstance(value["contracts"], dict) and set(value["contracts"]) == set(CONTRACT_PINS), "contract binding keys")
    for name, expected_sha in CONTRACT_PINS.items():
        pin = validate_pin(value["contracts"][name], "contract " + name)
        require(pin["sha256"] == expected_sha, "contract expected hash")
    require(isinstance(value["engines"], dict) and set(value["engines"]) == set(ENGINE_PINS), "engine binding keys")
    for name, expected_sha in ENGINE_PINS.items():
        pin = validate_pin(value["engines"][name], "engine " + name)
        require(pin["sha256"] == expected_sha, "engine expected hash")
    b_final = value["b_final"]
    require(isinstance(b_final, dict) and set(b_final) == {"bundle", "review", "cache_admission", "raw_calendar", "calendar_semantic"}, "B final keys")
    for name in ("bundle", "review", "cache_admission", "raw_calendar"):
        validate_pin(b_final[name], "B " + name)
    semantic = b_final["calendar_semantic"]
    require(isinstance(semantic, dict) and set(semantic) == {"bytes", "sha256", "rows", "order"}, "calendar semantic")
    require(semantic["bytes"] == CALENDAR_SEMANTIC_BYTES and semantic["rows"] == 2790, "calendar semantic counts")
    validate_sha(semantic["sha256"], "calendar semantic sha")
    require(semantic["sha256"] == CALENDAR_SEMANTIC_SHA256, "calendar semantic expected hash")
    require(semantic["order"] == "DATE_ASC_TICKER_ORDINAL_SPY_QQQ_SPXW", "calendar semantic order")
    require(b_final["cache_admission"]["bytes"] == CACHE_ADMISSION_BYTES and b_final["cache_admission"]["sha256"] == CACHE_ADMISSION_SHA256, "cache admission expected pin")
    helper_pin = validate_pin(value["resource_helper"], "resource helper")
    require(helper_pin["bytes"] == RESOURCE_HELPER_BYTES and helper_pin["sha256"] == RESOURCE_HELPER_SHA256, "official resource helper pin")
    require(value["windows_publication"] == {"api": "MoveFileExW", "flags": 8, "same_volume": True, "replace": False}, "Windows publication binding")
    runtime = value["runtime"]
    require(isinstance(runtime, dict) and set(runtime) == {"python", "numpy", "pyarrow", "producer"}, "runtime keys")
    require(runtime["python"] == sys.version, "runtime Python")
    require(runtime["numpy"] == RUNTIME_VERSIONS["numpy"] == np.__version__, "runtime NumPy")
    require(runtime["pyarrow"] == RUNTIME_VERSIONS["pyarrow"] == pa.__version__, "runtime PyArrow")
    producer_pin = validate_pin(runtime["producer"], "runtime producer")
    require(Path(producer_pin["path"]).name == Path(__file__).name, "runtime producer name")
    require(Path(producer_pin["path"]).resolve() == Path(__file__).resolve(), "runtime producer path")
    require(producer_pin["sha256"] == sha256_file(Path(__file__).resolve()), "runtime producer expected hash")
    roots = value["runtime_roots"]
    require(isinstance(roots, dict) and set(roots) == {"output_dir", "observer_dir", "journal"}, "runtime root keys")
    for name, path_text in roots.items():
        require(isinstance(path_text, str) and PureWindowsPath(path_text).is_absolute(), "runtime root " + name)
    return dict(value)


def read_binding_before_mutation(path: Path, expected_sha: str) -> dict[str, Any]:
    try:
        validate_sha(expected_sha, "binding CLI sha")
        guard_regular_file(path, "binding file")
        require(sha256_file(path) == expected_sha, "binding file hash")
        value = json.loads(path.read_text(encoding="utf-8"))
        return validate_runtime_binding(value)
    except (GeometryError, OSError, ValueError) as exc:
        raise GeometryError(str(exc), 10) from exc


class WindowsPublisher:
    MOVEFILE_WRITE_THROUGH = 0x8
    DRIVE_REMOTE = 4

    def __init__(self) -> None:
        require(os.name == "nt", "Windows publication required")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        self.kernel.MoveFileExW.restype = wintypes.BOOL
        self.kernel.FlushFileBuffers.argtypes = [wintypes.HANDLE]
        self.kernel.FlushFileBuffers.restype = wintypes.BOOL
        self.kernel.GetVolumePathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        self.kernel.GetVolumePathNameW.restype = wintypes.BOOL
        self.kernel.GetVolumeNameForVolumeMountPointW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        self.kernel.GetVolumeNameForVolumeMountPointW.restype = wintypes.BOOL
        self.kernel.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
        self.kernel.GetDriveTypeW.restype = wintypes.UINT
        self.kernel.GetCurrentProcess.restype = wintypes.HANDLE
        self.kernel.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
        self.kernel.SetProcessAffinityMask.restype = wintypes.BOOL

    def bind_cpu0(self) -> None:
        require(bool(self.kernel.SetProcessAffinityMask(self.kernel.GetCurrentProcess(), 1)), "CPU0 affinity", 12)

    def flush_regular_file(self, path: Path) -> None:
        with path.open("r+b", buffering=0) as stream:
            self.flush_stream(stream)

    def flush_stream(self, stream: Any) -> None:
        import msvcrt
        handle = wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno()))
        require(bool(self.kernel.FlushFileBuffers(handle)), f"FlushFileBuffers failed {ctypes.get_last_error()}", 15)

    def move(self, staging: Path, final: Path) -> None:
        require(not final.exists(), "final already exists")
        ok = self.kernel.MoveFileExW(str(staging), str(final), self.MOVEFILE_WRITE_THROUGH)
        if not ok:
            raise GeometryError(f"MoveFileExW failed {ctypes.get_last_error()}", 15)

    def volume_id(self, path: Path) -> str:
        mount = ctypes.create_unicode_buffer(32768)
        require(bool(self.kernel.GetVolumePathNameW(str(path), mount, len(mount))), "GetVolumePathNameW")
        volume = ctypes.create_unicode_buffer(128)
        require(bool(self.kernel.GetVolumeNameForVolumeMountPointW(mount.value, volume, len(volume))), "GetVolumeNameForVolumeMountPointW")
        return volume.value.casefold()

    def require_local_volume(self, path: Path) -> None:
        mount = ctypes.create_unicode_buffer(32768)
        require(bool(self.kernel.GetVolumePathNameW(str(path), mount, len(mount))), "GetVolumePathNameW")
        require(self.kernel.GetDriveTypeW(mount.value) != self.DRIVE_REMOTE, "remote runtime volume forbidden", 11)


def guard_runtime_paths(output_dir: Path, observer_dir: Path, journal_path: Path, binding: Mapping[str, Any]) -> None:
    for path in (output_dir, observer_dir, journal_path):
        raw = str(path)
        pure = PureWindowsPath(raw)
        require(pure.is_absolute() and "." not in pure.parts and ".." not in pure.parts, "runtime lexical path")
    require(output_dir.parent == observer_dir.parent, "runtime roots must be siblings")
    require(journal_path.parent == observer_dir, "journal must be under observer")
    roots = binding["runtime_roots"]
    require(str(output_dir) == roots["output_dir"], "designated output root")
    require(str(observer_dir) == roots["observer_dir"], "designated observer root")
    require(str(journal_path) == roots["journal"], "designated journal path")
    require(not output_dir.exists() and not observer_dir.exists(), "runtime roots must be absent")
    require(output_dir.parent.is_dir(), "runtime parent")
    for item in [output_dir.parent, *output_dir.parent.parents]:
        value = item.lstat()
        attributes = int(getattr(value, "st_file_attributes", 0))
        require(not item.is_symlink() and not (attributes & 0x400) and stat.S_ISDIR(value.st_mode), "runtime reparse/non-directory ancestor")
        if str(item) == output_dir.anchor:
            break


def validate_final_counts(states: Sequence[Mapping[str, Any]], levels: Sequence[Mapping[str, Any]], counts: Mapping[str, int]) -> None:
    require(counts["AVAILABLE_GEOMETRY"] + counts["INVALID_IB"] + counts["INVALID_STATE60"] == 2772, "available geometry partition")
    require(counts["MISSING_SOURCE"] == 18 and len(states) == 2790, "missing/state counts")
    require(len(levels) == sum(row["level_count"] for row in states), "level count reconciliation")


def publish_checked(
    staging: Path, output_dir: Path, expected: Mapping[str, Mapping[str, Any]],
    publisher: Any, journal: Journal, observation: Callable[[], Mapping[str, int]],
) -> None:
    """Single-attempt terminal rename with durable success/error evidence."""
    publish_gate = disk_gate(output_dir.parent, observation())
    staging_identity = physical_identity(staging)
    journal.append("PUBLISH_ROOT", output_dir.name, "START", [str(staging), str(output_dir)], publish_gate, {"staging_identity": staging_identity})
    try:
        require(publisher.volume_id(staging) == publisher.volume_id(output_dir.parent), "publication volume mismatch")
        publisher.move(staging, output_dir)
        require(output_dir.is_dir() and set(path.name for path in output_dir.iterdir()) == set(expected), "published member set")
        require(physical_identity(output_dir) == staging_identity, "published directory physical identity drift")
        for name, expected_pin in expected.items():
            final_pin = compact_pin(output_dir / name)
            require(final_pin["bytes"] == expected_pin["bytes"] and final_pin["sha256"] == expected_pin["sha256"], "post-move output drift " + name)
    except BaseException as exc:
        journal.append("PUBLISH_ROOT", output_dir.name, "ERROR", [str(staging), str(output_dir)], publish_gate, {"error_type": type(exc).__name__, "message": str(exc), "adoptable": False})
        raise
    journal.append("PUBLISH_ROOT", output_dir.name, "COMPLETE", [str(output_dir)], publish_gate, {"status": STATUS, "staging_identity": staging_identity})


def close_output_checked(path: Path, expected: Mapping[str, Any], publisher: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    before = compact_pin(path)
    require(before == expected, "output drift since WRITE_OUTPUT")
    publisher.flush_regular_file(path)
    after = compact_pin(path)
    require(after == before == expected, "closing output drift")
    return before, after


def run(
    binding: Mapping[str, Any], output_dir: Path, observer_dir: Path, journal_path: Path,
    *, publisher: Any | None = None,
) -> dict[str, Any]:
    """Execute one real run after an already validated, non-pending binding."""
    binding = validate_runtime_binding(binding)
    guard_runtime_paths(output_dir, observer_dir, journal_path, binding)
    # Exact official helper is the only authority used before the journal; it is
    # required to make the boot resource observation which permits mutation.
    observation = load_resource_helper(binding["resource_helper"])
    publisher = publisher or WindowsPublisher()
    publisher.bind_cpu0()
    publisher.require_local_volume(output_dir.parent)
    require(publisher.volume_id(output_dir.parent) == publisher.volume_id(observer_dir.parent), "runtime volume mismatch")

    disk_gate(output_dir.parent, observation())
    observer_dir.mkdir(exist_ok=False)
    journal = Journal(journal_path, observation, output_dir.parent, publisher.flush_stream)
    staging = output_dir.parent / f".{output_dir.name}.staging-{uuid.uuid4().hex}"
    require(not staging.exists(), "staging collision")
    staging.mkdir(exist_ok=False)
    states: list[dict[str, Any]] = []
    levels: list[dict[str, Any]] = []
    admitted_inputs: dict[str, dict[str, Any]] = {}
    try:
        for label, pin in (
            [("binding_bundle", binding["b_final"]["bundle"]), ("binding_review", binding["b_final"]["review"]),
             ("calendar", binding["b_final"]["raw_calendar"]), ("cache_admission", binding["b_final"]["cache_admission"]),
             ("implementation", binding["runtime"]["producer"]), ("resource_helper", binding["resource_helper"])]
            + [("contract:" + name, pin) for name, pin in binding["contracts"].items()]
            + [("engine:" + name, pin) for name, pin in binding["engines"].items()]
        ):
            with journal.unit("ADMIT_AUTHORITY", label, [pin["path"]]) as details:
                snapshot = admitted_snapshot(Path(pin["path"]), "authority " + label)
                require(snapshot["pin"] == pin, "authority drift " + label)
                admitted_inputs[pin["path"]] = snapshot
                details.update({"before": pin, "after": snapshot["pin"], "physical_identity": snapshot["physical_identity"]})

        engine_paths = {name: Path(pin["path"]) for name, pin in binding["engines"].items()}
        bundle_path = Path(binding["b_final"]["bundle"]["path"])
        bundle_value = json.loads(bundle_path.read_text(encoding="utf-8"))
        validate_final_b_bundle(bundle_value, binding)
        for label, pin in final_b_proof_pins(bundle_value).items():
            with journal.unit("ADMIT_AUTHORITY", label, [pin["path"]]) as details:
                snapshot = admitted_snapshot(Path(pin["path"]), label)
                require(snapshot["pin"] == pin, "B proof authority drift " + label)
                admitted_inputs[pin["path"]] = snapshot
                details.update({"before": pin, "after": snapshot["pin"], "physical_identity": snapshot["physical_identity"]})
        validate_final_b_closure(bundle_value)
        authority_input_count = len(admitted_inputs)
        calendar_path = Path(binding["b_final"]["raw_calendar"]["path"])
        cache_admission_path = Path(binding["b_final"]["cache_admission"]["path"])
        calendar_document = json.loads(calendar_path.read_text(encoding="utf-8"))
        calendar, calendar_semantic = normalize_calendar(calendar_document)
        semantic_binding = binding["b_final"]["calendar_semantic"]
        require(len(calendar_semantic) == semantic_binding["bytes"] and hashlib.sha256(calendar_semantic).hexdigest() == semantic_binding["sha256"], "calendar semantic digest")
        admission = normalize_cache_admission(parse_jsonl(cache_admission_path))
        require(set(admission) == {(row["ticker"], row["date"]) for row in calendar}, "calendar/cache identity set")
        for row in calendar:
            source = admission[(row["ticker"], row["date"])]
            require(source["close_i"] == row["close_i"] and source["session_kind"] == row["session_kind"], "calendar close preservation")
        require(sum(row["cache_status"] == "AVAILABLE" for row in admission.values()) == 2772, "available cache count")
        require(sum(row["cache_status"] == "MISSING" for row in admission.values()) == 18, "missing cache count")
        engine, clocks = load_pure_engines(engine_paths)

        for calendar_row in calendar:
            key = (calendar_row["ticker"], calendar_row["date"])
            source = admission[key]
            identity = f"{key[0]}:{key[1]}"
            paths = [] if source["cache_status"] == "MISSING" else [source["cache_metadata_path"], source["npz_path"]]
            with journal.unit("GEOMETRY_IDENTITY", identity, paths) as details:
                details.update({"opened_array_names": [], "physical_array_names": [], "inputs": {}})
                if source["cache_status"] == "MISSING":
                    state = _base_state(calendar_row, source)
                    unit_levels: list[dict[str, Any]] = []
                else:
                    metadata_pin = {"path": source["cache_metadata_path"], "bytes": source["cache_metadata_bytes"], "sha256": source["cache_metadata_sha256"]}
                    npz_pin = {"path": source["npz_path"], "bytes": source["npz_bytes"], "sha256": source["npz_sha256"]}
                    metadata_path, npz_path = Path(metadata_pin["path"]), Path(npz_pin["path"])
                    metadata_snapshot = admitted_snapshot(metadata_path, identity + " metadata")
                    npz_snapshot = admitted_snapshot(npz_path, identity + " npz")
                    require(metadata_snapshot["pin"] == metadata_pin and npz_snapshot["pin"] == npz_pin, "cache admission pin")
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    cache, physical_names = load_cache_arrays(npz_path)
                    validate_cache_metadata(metadata, source, cache)
                    state, unit_levels = compute_identity_geometry(calendar_row, source, metadata, cache, engine, clocks)
                    metadata_after = require_snapshot(metadata_path, metadata_snapshot, identity + " metadata after")["pin"]
                    npz_after = require_snapshot(npz_path, npz_snapshot, identity + " npz after")["pin"]
                    admitted_inputs[str(metadata_path)] = metadata_snapshot
                    admitted_inputs[str(npz_path)] = npz_snapshot
                    details["physical_array_names"] = list(physical_names)
                    details["opened_array_names"] = list(ARRAY_NAMES)
                    details["inputs"] = {
                        "metadata": {"before": metadata_pin, "after": metadata_after},
                        "npz": {"before": npz_pin, "after": npz_after},
                    }
                states.append(state)
                levels.extend(unit_levels)
                details.update({"geometry_status": state["geometry_status"], "level_rows": len(unit_levels)})

        counts = validate_rows(states, levels)
        validate_final_counts(states, levels, counts)
        state_table = table_from_rows(states, states_schema())
        level_table = table_from_rows(levels, levels_schema())
        output_pins: dict[str, dict[str, Any]] = {}
        expected_staging: dict[str, dict[str, Any]] = {}

        state_path = staging / OUTPUT_NAMES[0]
        with journal.unit("WRITE_OUTPUT", state_path.name, [str(state_path)]) as details:
            write_parquet(state_path, state_table, [(0, len(states))])
            publisher.flush_regular_file(state_path)
            state_physical = compact_pin(state_path)
            expected_staging[state_path.name] = state_physical
            output_pins[state_path.name] = {**state_physical, "path": str(output_dir / state_path.name), "rows": len(states)}
            details["pin"] = output_pins[state_path.name]

        level_path = staging / OUTPUT_NAMES[1]
        with journal.unit("WRITE_OUTPUT", level_path.name, [str(level_path)]) as details:
            write_parquet(level_path, level_table, level_row_groups(levels))
            publisher.flush_regular_file(level_path)
            level_physical = compact_pin(level_path)
            expected_staging[level_path.name] = level_physical
            output_pins[level_path.name] = {**level_physical, "path": str(output_dir / level_path.name), "rows": len(levels)}
            details["pin"] = output_pins[level_path.name]

        coverage = {
            "status": STATUS, "calendar_rows": 2790, "available_sources": 2772,
            "missing_sources": 18,
            "h1_full_available": counts["h1_full_available"],
            "h1_short_available": counts["h1_short_available"],
            "q3_available": counts["q3_available"],
            "h1_missing": counts["h1_missing"], "q3_missing": counts["q3_missing"],
            "geometry_available": counts["AVAILABLE_GEOMETRY"], "invalid_ib": counts["INVALID_IB"],
            "invalid_state60": counts["INVALID_STATE60"], "state_rows": len(states),
            "level_rows": len(levels), "entry_frozen_supported": True,
            "session_1030_reset_supported": True, "event_rules_adopted": False,
            "data_scope": "SEEN_DEVELOPMENT",
        }
        coverage_path = staging / OUTPUT_NAMES[2]
        with journal.unit("WRITE_OUTPUT", coverage_path.name, [str(coverage_path)]) as details:
            write_json(coverage_path, coverage)
            publisher.flush_regular_file(coverage_path)
            coverage_physical = compact_pin(coverage_path)
            expected_staging[coverage_path.name] = coverage_physical
            output_pins[coverage_path.name] = {**coverage_physical, "path": str(output_dir / coverage_path.name), "rows": None}
            details["pin"] = output_pins[coverage_path.name]

        manifest_path = staging / OUTPUT_NAMES[3]
        with journal.unit("WRITE_OUTPUT", manifest_path.name, [str(manifest_path)]) as details:
            physical_registry: dict[tuple[int, int], str] = {}
            for input_path, snapshot in admitted_inputs.items():
                identity = tuple(snapshot["physical_identity"])
                require(identity not in physical_registry or physical_registry[identity] == input_path, "physical input alias")
                physical_registry[identity] = input_path
            require(len(admitted_inputs) == authority_input_count + 5544, "admitted input count")
            input_records = sorted(
                ({**snapshot["pin"], "physical_identity": snapshot["physical_identity"]} for snapshot in admitted_inputs.values()),
                key=lambda pin: pin["path"],
            )
            manifest = {
                "status": STATUS,
                "contract": {name: pin for name, pin in binding["contracts"].items()},
                "implementation": compact_pin(Path(__file__).resolve()),
                "authorities": {"b_bundle": binding["b_final"]["bundle"], "b_review": binding["b_final"]["review"]},
                "authority_pins": {"calendar": binding["b_final"]["raw_calendar"], "cache_admission": binding["b_final"]["cache_admission"], "engines": binding["engines"]},
                "input_count": len(input_records),
                "inputs_digest": hashlib.sha256(canonical_json_bytes(input_records)).hexdigest(),
                "outputs": {name: output_pins[name] for name in OUTPUT_NAMES[:3]},
                "counts": {key: coverage[key] for key in (
                    "calendar_rows", "available_sources", "missing_sources",
                    "geometry_available", "invalid_ib", "invalid_state60",
                    "state_rows", "level_rows",
                )},
                "journal_closure": journal.prefix_snapshot(),
                "resource_policy": {"minimum_bytes": MIN_FREE, "cpu_affinity": [0], "threads": 1},
                "created_at_utc": utc_now(), "no_events": True, "no_labels": True,
                "no_weekly_selection": True, "no_economics": True,
            }
            write_json(manifest_path, manifest)
            publisher.flush_regular_file(manifest_path)
            manifest_pin = {**compact_pin(manifest_path), "rows": None}
            expected_staging[manifest_path.name] = compact_pin(manifest_path)
            details["pin"] = manifest_pin

        for path_text, expected in sorted(admitted_inputs.items()):
            with journal.unit("CLOSING_INPUT", path_text, [path_text]) as details:
                actual = require_snapshot(Path(path_text), expected, "closing input")
                details.update({"before": expected["pin"], "after": actual["pin"], "physical_identity": actual["physical_identity"]})
        for name in OUTPUT_NAMES:
            path = staging / name
            with journal.unit("CLOSING_OUTPUT", name, [str(path)]) as details:
                before, after = close_output_checked(path, expected_staging[name], publisher)
                details.update({"before": before, "after": after})

        publish_checked(staging, output_dir, expected_staging, publisher, journal, observation)
        return {"status": STATUS, "output_dir": str(output_dir), "manifest": compact_pin(output_dir / "manifest.json"), "counts": coverage}
    finally:
        journal.close()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--binding-json", type=Path, required=True)
    result.add_argument("--binding-sha256", required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--observer-dir", type=Path, required=True)
    result.add_argument("--journal", type=Path, required=True)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        binding = read_binding_before_mutation(args.binding_json, args.binding_sha256)
        result = run(binding, args.output_dir, args.observer_dir, args.journal)
    except GeometryError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
