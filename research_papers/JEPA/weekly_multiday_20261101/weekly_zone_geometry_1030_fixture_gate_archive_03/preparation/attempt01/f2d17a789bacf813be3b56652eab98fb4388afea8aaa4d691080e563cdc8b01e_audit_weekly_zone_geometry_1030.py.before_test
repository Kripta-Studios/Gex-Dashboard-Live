"""Independent C geometry auditor.

This module never imports the C producer.  It readmits the published runtime
binding, verifies the five frozen pure engines, reconstructs state-60 geometry
from the sealed cache population, and compares the producer's four outputs.
Real execution remains impossible until a complete, non-pending runtime binding
is published.  The pure helpers are intentionally usable by artificial tests.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import stat
import sys
import types
from typing import Any, Iterable, Mapping, Sequence

for _thread_name in (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS",
    "ARROW_NUM_THREADS", "POLARS_MAX_THREADS", "RAYON_NUM_THREADS",
    "CUDA_VISIBLE_DEVICES",
):
    os.environ[_thread_name] = "-1" if _thread_name == "CUDA_VISIBLE_DEVICES" else "1"

import numpy as np  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402


HERE = Path(__file__).resolve().parent
LEVEL_ROOT = HERE.parent / "level_oracle_20261018"
RESOURCE_HELPER = LEVEL_ROOT / "launch_monthly_test_index_v2_audit_20261024.py"
RESOURCE_HELPER_PIN = (31463, "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046")
CONTRACT = HERE / "C_GEOMETRY_1030_ADMISSION_CONTRACT_20261102.md"
DRAFT = HERE / "C_GEOMETRY_1030_OPERATIONAL_DRAFT_20261102.md"
AMENDMENT = HERE / "C_GEOMETRY_PARALLEL_PREPARATION_AMENDMENT_20261102.md"
AMENDMENT_REVIEW = HERE / "C_GEOMETRY_PARALLEL_PREPARATION_REVIEW_20261102.md"
WINDOWS_NOTE = HERE / "C_GEOMETRY_WINDOWS_PUBLICATION_FEASIBILITY_20261102.md"
BINDING_NOTE = HERE / "C_GEOMETRY_1030_BINDING_FEASIBILITY_20261102.md"

AUTHORITY_PINS = {
    "contract": (CONTRACT, 14617, "c28572543c1658ab87b1083d60bfdfbdc059c57960c5240c54f98bef5cdd8027"),
    "draft": (DRAFT, 20544, "88f76551957e73e37c5dd816b00ec17d035132186df5071be10a5c534368cb3f"),
    "amendment": (AMENDMENT, 3761, "f32d3bb23a830c9c67197926ab9defa847e5b347422b90fcf1d54d5bdb09b237"),
    "amendment_review": (AMENDMENT_REVIEW, 1212, "b3b056d2d447e407902a99d8567b437479ce1ee99e7efc7f62146e47c1fa2580"),
    "windows_note": (WINDOWS_NOTE, 5695, "f16d1a1c418fb51b5c5b180719c7a762ba338817a183c6006d472bc34ce13f31"),
    "binding_note": (BINDING_NOTE, 8652, "149fb9f9ddd3a01be24af1fd5f461a9ed7e0abad84d417837f11aff562d2f88a"),
}
ENGINE_PINS = {
    "level_engine.py": (27435, "70cc5d20990d971d16299fd008ff8e05ac99f99a6a2917a202fcb9a5f413b7c6"),
    "session_level_engine.py": (21874, "f93d3be334a2326dbec5d742e217bce63449e1beaf46b35fa46be83f25548883"),
    "session_clock.py": (1046, "1e63cf2d314caea14dd8b0b8f025f647d67bf8df58f246613975891a256f51e9"),
    "session_cache.py": (2371, "6300a7f8e5c6c99101d32d642081f4b8dec170d3c40f2751c27f1642d55466f1"),
    "build_cache.py": (18248, "985e87dcbd1e73289b58e4576445e47e73a6edea13e5ac73dde3ad629180d69f"),
}

ARRAYS = (
    "time_ns", "strike", "right", "bid", "ask", "delta", "iv", "vega",
    "theta", "row_flags", "spot", "spot_valid", "oi_contract_idx",
    "oi_value", "oi_available_ns", "oi_valid",
)
OPTIONAL_DECLARED_ARRAY = "underlying_age_ms"
TICKER_ORDINAL = {"SPY": 0, "QQQ": 1, "SPXW": 2}
CANONICAL_CALENDAR_BYTES = 137640
CANONICAL_CALENDAR_SHA256 = "13bc456a32c6dc711fffb71ef24375ecd5e455c11a9efedfb117b9ad903fb929"
B_OUTPUT_NAMES = {"cache_admission.jsonl", "decision_contracts.parquet",
                  "option_quote_observations.parquet", "segment_coverage.parquet",
                  "source_admission.jsonl", "spot_coverage.jsonl", "spot_paths.parquet", "summary.json"}
B_AUTHORITY_KEYS = {
    "stage_a_entry_plan", "stage_a_weekly_sources", "stage_a_summary", "stage_a_manifest",
    "stage_a_audit", "stage_a_audit_manifest", "stage_a_audit_exit", "h1_inventory",
    "h1_inventory_manifest", "h1_manifest", "q3_inventory", "q3_inventory_manifest",
    "q3_manifest", "bridge_inventory", "bridge_inventory_manifest", "bridge_manifest",
    "unified_calendar", "h1_context_inventory", "h1_context_inventory_manifest",
    "h1_context_manifest", "q3_context_inventory", "q3_context_inventory_manifest",
    "q3_context_manifest", "selector_builder_v2", "normalization_pilot",
    "original_value_path_contract", "prior_producer_exit", "prior_producer_failure",
    "prior_producer_journal",
}
FINAL_B_FLAG_KEYS = {"actions_read", "candidates_read", "context_feature_arrays_read",
                     "economic_evaluation_performed", "fit_performed", "inference_performed",
                     "labels_read", "models_read", "option_raw_values_read", "outcomes_read",
                     "parquet_footers_read", "pnl_computed", "promotion_approved", "replay_performed",
                     "risk_or_qty_computed", "selected_policy", "spot_cache_arrays_read", "technical_ready"}
RATIOS = (-1.0, -0.618, -0.272, 0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.0)
STATE_SEMANTIC_COLUMNS = (
    "calendar_ordinal", "ticker", "trade_date", "authority_period",
    "session_kind", "close_i", "source_status", "geometry_status",
    "missing_reason", "state_i", "state_clock_local", "formed_from_start",
    "formed_from_end", "first_available_at", "spot_1030", "ib_observed",
    "ib_low", "ib_high", "ib_range", "band", "tau_years", "level_count",
    "known_contract_count", "oi_known_count", "oi_missing_count",
    "fib_component_count", "call_oi_wall_count", "put_oi_wall_count",
    "call_gamma_wall_count", "put_gamma_wall_count",
)
LEVEL_SEMANTIC_COLUMNS = (
    "calendar_ordinal", "cluster_ordinal", "anchor_id", "ticker", "trade_date",
    "session_kind", "close_i", "state_i", "first_available_at", "center",
    "band", "source_mask", "n_components", "semantic_components_json",
)


def state_schema() -> pa.Schema:
    fields = (
        ("calendar_ordinal", pa.int32(), False), ("ticker", pa.string(), False),
        ("trade_date", pa.date32(), False), ("authority_period", pa.string(), False),
        ("session_kind", pa.string(), False), ("close_i", pa.int16(), False),
        ("source_status", pa.string(), False), ("geometry_status", pa.string(), False),
        ("missing_reason", pa.string(), True), ("state_i", pa.int16(), False),
        ("state_clock_local", pa.timestamp("ns"), False),
        ("formed_from_start", pa.timestamp("ns"), True),
        ("formed_from_end", pa.timestamp("ns"), True),
        ("first_available_at", pa.timestamp("ns"), True),
        ("spot_1030", pa.float64(), True), ("ib_observed", pa.int16(), True),
        ("ib_low", pa.float64(), True), ("ib_high", pa.float64(), True),
        ("ib_range", pa.float64(), True), ("band", pa.float64(), True),
        ("tau_years", pa.float64(), True), ("level_count", pa.int16(), False),
        ("known_contract_count", pa.int32(), True), ("oi_known_count", pa.int32(), True),
        ("oi_missing_count", pa.int32(), True), ("fib_component_count", pa.int16(), True),
        ("call_oi_wall_count", pa.int8(), True), ("put_oi_wall_count", pa.int8(), True),
        ("call_gamma_wall_count", pa.int8(), True), ("put_gamma_wall_count", pa.int8(), True),
        ("cache_metadata_path", pa.string(), True),
        ("cache_metadata_sha256", pa.string(), True),
        ("cache_npz_path", pa.string(), True), ("cache_npz_sha256", pa.string(), True),
        ("clock_basis", pa.string(), True), ("oi_clock_basis", pa.string(), True),
        ("oi_assumed_availability", pa.string(), True),
        ("clock_delay_applied", pa.bool_(), True), ("receipt_status", pa.string(), False),
    )
    return pa.schema([pa.field(name, kind, nullable=nullable) for name, kind, nullable in fields])


def level_schema() -> pa.Schema:
    fields = (
        ("calendar_ordinal", pa.int32()), ("cluster_ordinal", pa.int16()),
        ("anchor_id", pa.string()), ("ticker", pa.string()),
        ("trade_date", pa.date32()), ("session_kind", pa.string()),
        ("close_i", pa.int16()), ("state_i", pa.int16()),
        ("first_available_at", pa.timestamp("ns")), ("center", pa.float64()),
        ("band", pa.float64()), ("source_mask", pa.int16()),
        ("n_components", pa.int16()), ("semantic_components_json", pa.string()),
        ("provenance_components_json", pa.string()), ("cache_npz_path", pa.string()),
        ("cache_npz_sha256", pa.string()), ("clock_basis", pa.string()),
        ("oi_clock_basis", pa.string()), ("receipt_status", pa.string()),
    )
    return pa.schema([pa.field(name, kind, nullable=False) for name, kind in fields])


class AuditError(RuntimeError):
    """Fatal independent-audit failure."""


@dataclass(frozen=True)
class Pin:
    path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class Engines:
    level: Any
    session_level: Any
    clock: Any


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_pin(value: Any, label: str) -> Pin:
    if not isinstance(value, dict) or set(value) != {"path", "bytes", "sha256"}:
        raise AuditError(f"{label}: pin schema")
    if type(value["path"]) is not str or type(value["bytes"]) is not int:
        raise AuditError(f"{label}: pin types")
    sha = value["sha256"]
    if type(sha) is not str or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise AuditError(f"{label}: sha256")
    return Pin(value["path"], value["bytes"], sha)


def is_pending(value: Any) -> bool:
    if isinstance(value, str):
        return not value or "PENDING" in value or "UNKNOWN" in value
    if isinstance(value, dict):
        return any(is_pending(item) for item in value.values())
    if isinstance(value, list):
        return any(is_pending(item) for item in value)
    return value is None


def load_runtime_binding(path: Path, expected_sha256: str) -> dict[str, Any]:
    """Read the one permitted pre-root file and reject unresolved bindings."""
    guard_regular(path)
    if len(expected_sha256) != 64 or sha256_file(path) != expected_sha256:
        raise AuditError("runtime binding pin")
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema", "status", "producer_output_root", "producer_observer_root",
        "producer_manifest", "producer_journal", "producer_exit", "producer_process",
        "b_final_bundle", "b_final_review", "calendar", "cache_admission", "authority_pins",
        "implementation_pins", "audit_output_root", "audit_observer_root",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise AuditError("runtime binding schema")
    if value["schema"] != "c_geometry_1030_runtime_binding_v1" or value["status"] != "BOUND_REAL_C_GEOMETRY_1030":
        raise AuditError("runtime binding status")
    if is_pending(value):
        raise AuditError("runtime binding unresolved")
    for key in ("producer_manifest", "producer_journal", "producer_exit", "producer_process",
                "b_final_bundle", "b_final_review", "calendar", "cache_admission"):
        strict_pin(value[key], key)
    if set(value["authority_pins"]) != set(AUTHORITY_PINS):
        raise AuditError("runtime authority set")
    expected_implementations = set(ENGINE_PINS) | {
        "producer", "producer_tests", "resource_helper", "auditor", "auditor_tests",
    }
    if set(value["implementation_pins"]) != expected_implementations:
        raise AuditError("runtime implementation set")
    return value


def require_runtime_roots(binding: Mapping[str, Any], output: Path, observer: Path) -> None:
    if output != Path(binding["audit_output_root"]) or observer != Path(binding["audit_observer_root"]):
        raise AuditError("exclusive audit roots")
    for path in (output, observer):
        pure = PureWindowsPath(str(path))
        if not pure.is_absolute() or "." in pure.parts or ".." in pure.parts or path.exists():
            raise AuditError("audit root must be lexical absolute and absent")
        parent = path.parent
        if not parent.is_dir():
            raise AuditError("audit root parent")
        for ancestor in [parent, *parent.parents]:
            info = ancestor.lstat()
            attributes = int(getattr(info, "st_file_attributes", 0))
            if ancestor.is_symlink() or attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                raise AuditError("audit root reparse ancestor")
            if str(ancestor) == ancestor.anchor:
                break


def guard_published_roots(binding: Mapping[str, Any]) -> tuple[Path, Path]:
    producer = Path(binding["producer_output_root"])
    observer = Path(binding["producer_observer_root"])
    for root in (producer, observer):
        if not root.is_absolute() or not root.is_dir() or root.is_symlink():
            raise AuditError("producer root security")
        info = root.lstat()
        if int(getattr(info, "st_file_attributes", 0)) & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise AuditError("producer root reparse")
    members = {path.name for path in producer.iterdir()}
    if members != {"geometry_states_1030.parquet", "geometry_levels_1030.parquet", "coverage.json", "manifest.json"}:
        raise AuditError("producer final member set")
    if Path(strict_pin(binding["producer_manifest"], "producer manifest").path) != producer / "manifest.json":
        raise AuditError("producer manifest root")
    for name in ("producer_journal", "producer_exit", "producer_process"):
        if Path(strict_pin(binding[name], name).path).parent != observer:
            raise AuditError("producer observer path")
    return producer, observer


def guard_regular(path: Path, expected: Pin | None = None) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise AuditError(f"unsafe path: {path}")
    resolved = path.resolve(strict=True)
    if os.path.normcase(str(resolved)) != os.path.normcase(str(path)):
        raise AuditError(f"aliased path: {path}")
    anchor = Path(path.anchor)
    for ancestor in reversed(path.parents):
        if ancestor == anchor:
            continue
        ancestor_info = ancestor.lstat()
        attributes = int(getattr(ancestor_info, "st_file_attributes", 0))
        if ancestor.is_symlink() or attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise AuditError(f"reparse ancestor: {ancestor}")
    info = path.lstat()
    attributes = int(getattr(info, "st_file_attributes", 0))
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
            attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))):
        raise AuditError(f"not exclusive regular file: {path}")
    if expected is not None:
        if str(path) != expected.path or info.st_size != expected.bytes:
            raise AuditError(f"pin path/bytes: {path}")
        if sha256_file(path) != expected.sha256:
            raise AuditError(f"pin hash: {path}")


def require_distinct_physical_files(pins: Iterable[Pin]) -> None:
    observed: dict[tuple[int, int], str] = {}
    for pin in pins:
        path = Path(pin.path)
        guard_regular(path, pin)
        info = path.stat()
        identity = (int(info.st_dev), int(info.st_ino))
        previous = observed.get(identity)
        if previous is not None and os.path.normcase(previous) != os.path.normcase(pin.path):
            raise AuditError("physical file alias")
        observed[identity] = pin.path


def merge_closing_pins(*groups: Mapping[str, Pin]) -> dict[str, Pin]:
    """Form the exact audit-closing population without hiding pin conflicts."""
    result: dict[str, Pin] = {}
    for group in groups:
        for path_text, pin in group.items():
            if path_text != pin.path:
                raise AuditError("closing pin path key")
            if path_text in result and result[path_text] != pin:
                raise AuditError("conflicting audit closing pin")
            result[path_text] = pin
    return result


def verify_static_authorities(binding: Mapping[str, Any]) -> None:
    for name, (path, size, sha) in AUTHORITY_PINS.items():
        pin = strict_pin(binding["authority_pins"][name], name)
        expected = Pin(str(path), size, sha)
        if pin != expected:
            raise AuditError(f"authority pin: {name}")
        guard_regular(path, expected)
    for name, (size, sha) in ENGINE_PINS.items():
        path = LEVEL_ROOT / name
        pin = strict_pin(binding["implementation_pins"][name], name)
        expected = Pin(str(path), size, sha)
        if pin != expected:
            raise AuditError(f"engine pin: {name}")
        guard_regular(path, expected)
    helper_size, helper_sha = RESOURCE_HELPER_PIN
    helper_expected = Pin(str(RESOURCE_HELPER), helper_size, helper_sha)
    helper_pin = strict_pin(binding["implementation_pins"]["resource_helper"], "resource helper")
    if helper_pin != helper_expected:
        raise AuditError("resource helper pin")
    guard_regular(RESOURCE_HELPER, helper_expected)
    expected_names = {"producer": "build_weekly_zone_geometry_1030.py",
                      "producer_tests": "test_build_weekly_zone_geometry_1030.py",
                      "auditor": Path(__file__).name,
                      "auditor_tests": "test_audit_weekly_zone_geometry_1030.py"}
    for role, filename in expected_names.items():
        pin = strict_pin(binding["implementation_pins"][role], role)
        path = Path(pin.path)
        if path.name != filename:
            raise AuditError(f"implementation filename: {role}")
        guard_regular(path, pin)
        if path.resolve() != (HERE / filename).resolve():
            raise AuditError(f"implementation exact path: {role}")


def validate_retained_closure(exit_value: Any, process_value: Any) -> None:
    required_exit = {"exit_code", "geometry_child_exit_code", "pid", "creation_epoch",
                     "changed_pins", "metadata_error", "retry"}
    required_process = {"pid", "creation_epoch"}
    if not isinstance(exit_value, dict) or not required_exit.issubset(exit_value):
        raise AuditError("producer retained exit schema")
    if not isinstance(process_value, dict) or not required_process.issubset(process_value):
        raise AuditError("producer retained process schema")
    if (exit_value["exit_code"] != 0 or exit_value["geometry_child_exit_code"] != 0 or
            exit_value["changed_pins"] != [] or exit_value["metadata_error"] is not None or
            exit_value["retry"] is not False):
        raise AuditError("producer retained exit outcome")
    if (type(exit_value["pid"]) is not int or type(process_value["pid"]) is not int or
            type(exit_value["creation_epoch"]) not in {int, float} or
            type(process_value["creation_epoch"]) not in {int, float} or
            (exit_value["pid"], exit_value["creation_epoch"]) !=
            (process_value["pid"], process_value["creation_epoch"])):
        raise AuditError("producer retained process identity")


def bind_engines() -> Engines:
    """Load the pinned pure graph under an isolated package namespace."""
    package_name = "_c_geometry_audit_frozen"
    package = types.ModuleType(package_name)
    package.__path__ = [str(LEVEL_ROOT)]
    sys.modules[package_name] = package
    loaded: dict[str, Any] = {}
    for name in ("level_engine", "session_clock", "session_level_engine"):
        spec = importlib.util.spec_from_file_location(f"{package_name}.{name}", LEVEL_ROOT / f"{name}.py")
        if spec is None or spec.loader is None:
            raise AuditError(f"engine loader: {name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        loaded[name] = module
    return Engines(loaded["level_engine"], loaded["session_level_engine"], loaded["session_clock"])


def bind_resource_helper() -> tuple[Any, Any]:
    spec = importlib.util.spec_from_file_location("c_geometry_audit_resource_helper", RESOURCE_HELPER)
    if spec is None or spec.loader is None:
        raise AuditError("resource helper loader")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    observation, gate = getattr(module, "observation", None), getattr(module, "gate", None)
    if not callable(observation) or not callable(gate):
        raise AuditError("resource helper interface")
    return observation, gate


def resource_gate(observation: Any, gate: Any, disk_root: Path) -> dict[str, int]:
    try:
        memory = dict(observation())
        gate(memory)
        result = {**memory, "disk_free_bytes": int(shutil.disk_usage(disk_root).free)}
    except Exception as exc:
        raise AuditError("official resource gate") from exc
    if (set(result) != {"available_ram_bytes", "free_commit_bytes", "disk_free_bytes"} or
            any(type(value) is not int or value < 2_000_000_000 for value in result.values())):
        raise AuditError("2GB RAM/commit/disk gate")
    return result


def file_snapshot(path: Path, expected: Pin | None = None) -> dict[str, Any]:
    guard_regular(path, expected)
    before = path.stat()
    pin = Pin(str(path), int(before.st_size), sha256_file(path))
    after = path.stat()
    before_stat = [int(before.st_dev), int(before.st_ino), int(before.st_size), int(before.st_mtime_ns)]
    after_stat = [int(after.st_dev), int(after.st_ino), int(after.st_size), int(after.st_mtime_ns)]
    if before_stat != after_stat or (expected is not None and pin != expected):
        raise AuditError("file snapshot drift")
    return {"pin": pin.__dict__, "physical_identity": before_stat[:2], "stat_identity": before_stat}


class AuditJournal:
    def __init__(self, path: Path, observation: Any, gate: Any, disk_root: Path) -> None:
        self.path = path
        self._observation = observation
        self._gate = gate
        self._disk_root = disk_root
        self._seq = 0
        with path.open("xb") as stream:
            stream.flush()
            os.fsync(stream.fileno())

    def append(self, kind: str, identity: str, phase: str, paths: Sequence[str],
               gate_value: Mapping[str, int], details: Mapping[str, Any]) -> None:
        row = {"seq": self._seq, "utc": datetime.now(timezone.utc).isoformat(), "kind": kind,
               "identity": identity, "phase": phase, "paths": list(paths),
               "gate": dict(gate_value), "details": dict(details)}
        with self.path.open("ab") as stream:
            stream.write(canonical_json(row) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._seq += 1

    @contextmanager
    def unit(self, kind: str, identity: str, paths: Sequence[str]) -> Iterable[dict[str, Any]]:
        gate_value = resource_gate(self._observation, self._gate, self._disk_root)
        self.append(kind, identity, "START", paths, gate_value, {})
        details: dict[str, Any] = {}
        try:
            yield details
        except BaseException as exc:
            self.append(kind, identity, "ERROR", paths, gate_value,
                        {"error_type": type(exc).__name__, "message": str(exc)})
            raise
        self.append(kind, identity, "COMPLETE", paths, gate_value, details)

    def close(self) -> None:
        return None


def write_durable_json(path: Path, value: Any) -> Pin:
    with path.open("xb") as stream:
        stream.write(canonical_json(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return Pin(str(path), path.stat().st_size, sha256_file(path))


def parse_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.endswith("\n") or line == "\n":
                raise AuditError(f"JSONL framing: {line_no}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise AuditError(f"JSONL object: {line_no}")
            if line.encode("utf-8") != canonical_json(value) + b"\n":
                raise AuditError(f"JSONL canonical encoding: {line_no}")
            rows.append(value)
    return rows


def validate_cache_admission(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    keys = {
        "ticker", "ticker_ordinal", "date", "session_kind", "close_i", "cache_status",
        "missing_reason", "authority", "feature_metadata_path", "feature_metadata_bytes",
        "feature_metadata_sha256", "cache_metadata_path", "cache_metadata_bytes",
        "cache_metadata_sha256", "npz_path", "npz_bytes", "npz_sha256", "cache_version",
        "binding_source_sha256", "binding_source_metadata_sha256", "stats",
    }
    if len(rows) != 2790:
        raise AuditError("cache admission population")
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    counts: Counter[tuple[str, str]] = Counter()
    for ordinal, source in enumerate(rows):
        if set(source) != keys:
            raise AuditError("cache admission schema")
        ticker, day = source["ticker"], source["date"]
        if ticker not in TICKER_ORDINAL or source["ticker_ordinal"] != TICKER_ORDINAL[ticker]:
            raise AuditError("cache ticker")
        if type(day) is not str or len(day) != 8 or not day.isdigit():
            raise AuditError("cache date")
        try:
            parsed = date.fromisoformat(day)
        except (TypeError, ValueError) as exc:
            raise AuditError("cache date") from exc
        identity = (ticker, day)
        if identity in seen:
            raise AuditError("cache duplicate identity")
        seen.add(identity)
        session = source["session_kind"]
        if session not in {"FULL", "SHORT"} or source["close_i"] != {"FULL": 390, "SHORT": 210}[session]:
            raise AuditError("cache session clock")
        authority = source["authority"]
        if authority not in {"H1", "Q3"}:
            raise AuditError("cache authority")
        status = source["cache_status"]
        if status not in {"AVAILABLE", "MISSING"}:
            raise AuditError("cache status")
        if status == "MISSING":
            if source["missing_reason"] != "MISSING_SOURCE":
                raise AuditError("cache missing reason")
            for name in ("cache_metadata_path", "cache_metadata_bytes", "cache_metadata_sha256",
                         "npz_path", "npz_bytes", "npz_sha256", "cache_version"):
                if source[name] is not None:
                    raise AuditError("missing cache has value pin")
        else:
            if source["missing_reason"] is not None:
                raise AuditError("available cache missing reason")
            strict_pin({"path": source["cache_metadata_path"], "bytes": source["cache_metadata_bytes"],
                        "sha256": source["cache_metadata_sha256"]}, "cache metadata")
            strict_pin({"path": source["npz_path"], "bytes": source["npz_bytes"],
                        "sha256": source["npz_sha256"]}, "cache npz")
            if (source["binding_source_sha256"] != source["npz_sha256"] or
                    source["binding_source_metadata_sha256"] != source["cache_metadata_sha256"]):
                raise AuditError("cache binding crosspin")
        counts[(authority, status)] += 1
        output.append({**source, "calendar_ordinal": ordinal, "trade_date": parsed})
    if sorted(output, key=lambda row: (row["trade_date"], TICKER_ORDINAL[row["ticker"]])) != output:
        raise AuditError("cache canonical calendar order")
    expected = Counter({("H1", "AVAILABLE"): 2619, ("Q3", "AVAILABLE"): 153,
                        ("H1", "MISSING"): 6, ("Q3", "MISSING"): 12})
    if counts != expected or sum(row["session_kind"] == "SHORT" and row["cache_status"] == "AVAILABLE" for row in output) != 24:
        raise AuditError("cache population decomposition")
    return output


def validate_calendar_document(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict) or set(document) != {"schema", "rows"}:
        raise AuditError("calendar top-level schema")
    if document["schema"] != "weekly_h2_boundary_unified_calendar_v1":
        raise AuditError("calendar schema")
    raw = document["rows"]
    if not isinstance(raw, list) or len(raw) != 2790:
        raise AuditError("calendar rows")
    triples = []
    by_ticker: dict[str, list[str]] = {ticker: [] for ticker in TICKER_ORDINAL}
    for row in raw:
        if (not isinstance(row, dict) or set(row) != {"close_i", "date", "ticker"} or
                row["ticker"] not in TICKER_ORDINAL or type(row["date"]) is not str or
                re.fullmatch(r"\d{8}", row["date"]) is None or
                type(row["close_i"]) is not int or row["close_i"] not in {210, 390}):
            raise AuditError("calendar row domain")
        try:
            date.fromisoformat(row["date"])
        except ValueError as exc:
            raise AuditError("calendar date") from exc
        triple = (row["ticker"], row["date"], row["close_i"])
        triples.append(triple)
        by_ticker[row["ticker"]].append(row["date"])
    if (len(set(triples)) != 2790 or triples != sorted(triples, key=lambda value: (value[0], value[1])) or
            any(len(days) != 930 or days != sorted(days) for days in by_ticker.values()) or
            not (set(by_ticker["SPY"]) == set(by_ticker["QQQ"]) == set(by_ticker["SPXW"])) or
            sum(close_i == 210 for _ticker, _day, close_i in triples) != 24):
        raise AuditError("calendar identity/order/counts")
    canonical = [{"ticker": ticker, "date": day, "close_i": close_i}
                 for ticker, day, close_i in sorted(triples, key=lambda value: (value[1], TICKER_ORDINAL[value[0]]))]
    payload = b"".join(canonical_json({"close_i": row["close_i"], "date": row["date"],
                                       "ticker": row["ticker"]}) + b"\n" for row in canonical)
    if len(payload) != CANONICAL_CALENDAR_BYTES or hashlib.sha256(payload).hexdigest() != CANONICAL_CALENDAR_SHA256:
        raise AuditError("calendar canonical digest")
    if canonical[0] != {"ticker": "SPY", "date": "20230103", "close_i": 390} or canonical[-1] != {"ticker": "SPXW", "date": "20260917", "close_i": 390}:
        raise AuditError("calendar endpoints")
    return canonical


def validate_final_b_bundle(value: Any, binding: Mapping[str, Any]) -> None:
    if not isinstance(value, dict) or set(value) != {"schema", "status", "producer", "auditor",
                                                        "authority_inputs", "calendar", "flags", "data_scope"}:
        raise AuditError("final B bundle schema")
    if (value["schema"] != "weekly_zone_event_value_paths_final_admission_v1" or
            value["status"] != "PASS_FINAL_B_ADMISSION" or value["data_scope"] != "SEEN_DEVELOPMENT"):
        raise AuditError("final B bundle status")
    producer = value["producer"]
    if not isinstance(producer, dict) or set(producer) != {"manifest", "outputs", "observer"}:
        raise AuditError("final B producer schema")
    strict_pin(producer["manifest"], "final B producer manifest")
    if not isinstance(producer["outputs"], dict) or set(producer["outputs"]) != B_OUTPUT_NAMES:
        raise AuditError("final B producer outputs")
    for name, pin in producer["outputs"].items():
        strict_pin(pin, f"final B output {name}")
    if producer["outputs"]["cache_admission.jsonl"] != binding["cache_admission"]:
        raise AuditError("final B cache admission crosspin")
    if not isinstance(producer["observer"], dict) or set(producer["observer"]) != {"exit", "process", "journal"}:
        raise AuditError("final B producer observer")
    for name, pin in producer["observer"].items():
        strict_pin(pin, f"final B producer observer {name}")
    auditor = value["auditor"]
    if not isinstance(auditor, dict) or set(auditor) != {"audit", "manifest", "exit", "process", "journal"}:
        raise AuditError("final B auditor schema")
    for name, pin in auditor.items():
        strict_pin(pin, f"final B auditor {name}")
    authorities = value["authority_inputs"]
    if not isinstance(authorities, dict) or set(authorities) != B_AUTHORITY_KEYS:
        raise AuditError("final B authority inputs")
    for name, pin in authorities.items():
        if type(name) is not str or not name:
            raise AuditError("final B authority identity")
        strict_pin(pin, f"final B authority {name}")
    calendar = value["calendar"]
    semantic = {"bytes": CANONICAL_CALENDAR_BYTES, "sha256": CANONICAL_CALENDAR_SHA256,
                "order": "DATE_ASC_TICKER_ORDINAL_SPY_QQQ_SPXW", "rows": 2790}
    if (not isinstance(calendar, dict) or set(calendar) != {"raw_file_pin", "semantic_jsonl",
                                                            "identity_set_preserved", "close_i_preserved"} or
            calendar["raw_file_pin"] != binding["calendar"] or calendar["semantic_jsonl"] != semantic or
            calendar["identity_set_preserved"] is not True or calendar["close_i_preserved"] is not True):
        raise AuditError("final B calendar crosspin")
    flags = value["flags"]
    if not isinstance(flags, dict) or set(flags) != FINAL_B_FLAG_KEYS:
        raise AuditError("final B flags")
    true_flags = {"option_raw_values_read", "parquet_footers_read", "spot_cache_arrays_read"}
    if flags["selected_policy"] is not None:
        raise AuditError("final B selected policy")
    for name in FINAL_B_FLAG_KEYS - {"selected_policy"}:
        if flags[name] is not (name in true_flags):
            raise AuditError("final B flags values")
    occurrences = [producer["manifest"], *producer["outputs"].values(),
                   *producer["observer"].values(), *auditor.values(),
                   *authorities.values(), calendar["raw_file_pin"]]
    if len(occurrences) != 47:
        raise AuditError("final B pin role count")
    paths = [strict_pin(pin, "final B role pin").path for pin in occurrences]
    path_counts = Counter(paths)
    duplicates = {path: count for path, count in path_counts.items() if count > 1}
    raw_calendar = strict_pin(calendar["raw_file_pin"], "final B raw calendar")
    unified = authorities.get("unified_calendar")
    if (len(path_counts) != 46 or duplicates != {raw_calendar.path: 2} or
            unified != calendar["raw_file_pin"]):
        raise AuditError("final B physical role cardinality")


def final_b_proof_pins(value: Mapping[str, Any]) -> dict[str, Pin]:
    raw = {
        "b_producer_manifest": value["producer"]["manifest"],
        **{f"b_producer_output:{name}": pin for name, pin in value["producer"]["outputs"].items()},
        **{f"b_producer_observer:{name}": pin for name, pin in value["producer"]["observer"].items()},
        **{f"b_auditor:{name}": pin for name, pin in value["auditor"].items()},
        **{f"b_authority:{name}": pin for name, pin in value["authority_inputs"].items()},
    }
    return {name: strict_pin(pin, name) for name, pin in raw.items()}


def read_pinned_json(pin_value: Mapping[str, Any], label: str) -> dict[str, Any]:
    pin = strict_pin(pin_value, label)
    guard_regular(Path(pin.path), pin)
    value = json.loads(Path(pin.path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AuditError(f"{label} object")
    return value


def validate_b_retained_exit(value: Mapping[str, Any], child_key: str, label: str) -> None:
    if (type(value.get("exit_code")) is not int or value["exit_code"] != 0 or
            type(value.get(child_key)) is not int or value[child_key] != 0 or
            value.get("changed_pins") != [] or value.get("metadata_error") is not None or
            value.get("retry") is not False or type(value.get("pid")) is not int or value["pid"] <= 0 or
            type(value.get("creation_epoch")) not in {int, float}):
        raise AuditError(f"final B {label} retained exit")


def validate_final_b_closure(value: Mapping[str, Any]) -> None:
    producer = value["producer"]
    producer_manifest = read_pinned_json(producer["manifest"], "final B producer manifest")
    manifest_outputs = producer_manifest.get("outputs")
    if not isinstance(manifest_outputs, dict) or set(manifest_outputs) != B_OUTPUT_NAMES:
        raise AuditError("final B producer output records")
    projected_outputs = {}
    expected_b_rows = {"cache_admission.jsonl": 2790, "decision_contracts.parquet": 3240,
                       "option_quote_observations.parquet": 3_606_310,
                       "segment_coverage.parquet": 9720, "source_admission.jsonl": 2784,
                       "spot_coverage.jsonl": 2790, "spot_paths.parquet": 1_086_570,
                       "summary.json": 1}
    for name, record in manifest_outputs.items():
        if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256", "rows"}:
            raise AuditError("final B producer output record")
        rows = record["rows"]
        if type(rows) is not int or rows != expected_b_rows[name]:
            raise AuditError("final B producer output record")
        projected_outputs[name] = {key: record[key] for key in ("path", "bytes", "sha256")}
    if (producer_manifest.get("schema") != "weekly_zone_event_value_paths_manifest_v2_calendar_normalized" or
            producer_manifest.get("status") != "COMPLETE_OUTCOME_FREE_VALUE_PATHS" or
            projected_outputs != producer["outputs"] or
            producer_manifest.get("authority_inputs") != value["authority_inputs"]):
        raise AuditError("final B producer closure")
    producer_exit = read_pinned_json(producer["observer"]["exit"], "final B producer exit")
    validate_b_retained_exit(producer_exit, "value_child_exit_code", "producer")
    producer_process = read_pinned_json(producer["observer"]["process"], "final B producer process")
    if (producer_process.get("pid"), producer_process.get("creation_epoch")) != (producer_exit["pid"], producer_exit["creation_epoch"]):
        raise AuditError("final B producer process identity")
    auditor = value["auditor"]
    audit_document = read_pinned_json(auditor["audit"], "final B audit")
    audit_manifest = read_pinned_json(auditor["manifest"], "final B audit manifest")
    if (audit_document.get("schema") != "weekly_zone_event_value_paths_audit_v2_calendar_normalized" or
            audit_document.get("status") != "PASS" or
            audit_manifest.get("schema") != "weekly_zone_event_value_paths_audit_manifest_v2_calendar_normalized" or
            audit_manifest.get("status") != "PASS" or audit_manifest.get("authority_inputs") != value["authority_inputs"]):
        raise AuditError("final B auditor closure")
    audit_exit = read_pinned_json(auditor["exit"], "final B audit exit")
    validate_b_retained_exit(audit_exit, "value_child_exit_code", "auditor")
    audit_process = read_pinned_json(auditor["process"], "final B audit process")
    if (audit_process.get("pid"), audit_process.get("creation_epoch")) != (audit_exit["pid"], audit_exit["creation_epoch"]):
        raise AuditError("final B auditor process identity")
    for label, pin_value, terminal_key, terminal_value in (
            ("producer", producer["observer"]["journal"], "kind", "CLOSING_REHASH"),
            ("auditor", auditor["journal"], "stage", "WRITE_AUDIT_OUTPUT")):
        pin = strict_pin(pin_value, f"final B {label} journal")
        guard_regular(Path(pin.path), pin)
        rows = parse_jsonl(Path(pin.path))
        if label == "producer":
            dialect_ok = all("kind" in row and "stage" not in row and
                             row.get("event") in {"STARTED", "COMPLETED", "ERROR"} for row in rows)
        else:
            dialect_ok = all("stage" in row and "kind" not in row and
                             row.get("event") in {"STARTED", "COMPLETED", "ERROR"} for row in rows)
        if (not rows or not dialect_ok or any(row.get("event") == "ERROR" for row in rows) or
                rows[-1].get("event") != "COMPLETED" or rows[-1].get(terminal_key) != terminal_value):
            raise AuditError(f"final B {label} journal closure")


def validate_metadata(metadata: Mapping[str, Any], source: Mapping[str, Any]) -> None:
    if metadata.get("ticker") != source["ticker"] or metadata.get("date") != source["date"]:
        raise AuditError("cache metadata identity")
    if metadata.get("version") != source["cache_version"]:
        raise AuditError("cache metadata version")
    if metadata.get("sha256") != source["npz_sha256"]:
        raise AuditError("cache metadata npz hash")
    if metadata.get("timezone_convention") != "America/New_York naive":
        raise AuditError("cache timezone")
    schema = metadata.get("array_schema")
    if not isinstance(schema, dict) or not set(ARRAYS).issubset(schema) or set(schema) - set(ARRAYS) - {OPTIONAL_DECLARED_ARRAY}:
        raise AuditError("cache array whitelist")
    if metadata.get("clock_delay_applied") is not False:
        raise AuditError("cache clock delay")
    if metadata.get("clock_basis") not in {"NATIVE_STORED_TIMESTAMP", "ASSUMED_UNDERLYING_SNAPSHOT_CLOCK"}:
        raise AuditError("cache clock basis")
    oi_basis = metadata.get("oi_clock_basis")
    assumed = metadata.get("oi_assumed_availability")
    if oi_basis not in {"NATIVE_STORED_TIMESTAMP", "ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT"}:
        raise AuditError("cache OI clock basis")
    if oi_basis == "NATIVE_STORED_TIMESTAMP" and assumed is not None:
        raise AuditError("native OI availability")
    if oi_basis == "ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT":
        expected_assumed = datetime.strptime(source["date"].replace("-", ""), "%Y%m%d").strftime("%Y-%m-%d 09:30:00")
        if assumed != expected_assumed:
            raise AuditError("assumed OI availability")
    if source["session_kind"] == "SHORT":
        session_clock = metadata.get("session_clock")
        if not isinstance(session_clock, dict) or session_clock.get("close_i") != 210 or session_clock.get("n_slots") != 211:
            raise AuditError("short metadata clock")
    for name, descriptor in schema.items():
        if not isinstance(descriptor, dict) or set(descriptor) != {"shape", "dtype"}:
            raise AuditError(f"cache array descriptor: {name}")


def load_cache(source: Mapping[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    metadata_pin = strict_pin({"path": source["cache_metadata_path"], "bytes": source["cache_metadata_bytes"],
                               "sha256": source["cache_metadata_sha256"]}, "cache metadata")
    npz_pin = strict_pin({"path": source["npz_path"], "bytes": source["npz_bytes"],
                          "sha256": source["npz_sha256"]}, "cache npz")
    metadata_path, npz_path = Path(metadata_pin.path), Path(npz_pin.path)
    guard_regular(metadata_path, metadata_pin)
    guard_regular(npz_path, npz_pin)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    validate_metadata(metadata, source)
    with np.load(npz_path, allow_pickle=False) as stored:
        if set(stored.files) != set(metadata["array_schema"]):
            raise AuditError("cache stored array names")
        arrays = {name: stored[name] for name in ARRAYS}
    for name, array in arrays.items():
        descriptor = metadata["array_schema"][name]
        if list(array.shape) != descriptor.get("shape") or str(array.dtype) != descriptor.get("dtype"):
            raise AuditError(f"cache array descriptor: {name}")
    guard_regular(metadata_path, metadata_pin)
    guard_regular(npz_path, npz_pin)
    return arrays, metadata


def float_hex(value: float) -> str:
    number = float(value)
    if not np.isfinite(number):
        raise AuditError("nonfinite anchor float")
    return "0x0.0p+0" if number == 0.0 else number.hex().lower()


def semantic_component(component: Mapping[str, Any], cache: Mapping[str, np.ndarray]) -> dict[str, Any]:
    if component["name"] == "FIB":
        return {"kind": "FIB", "name": "FIB", "source_mask": int(component["source_mask"]),
                "ratio_f64": float_hex(component["ratio"]), "center_f64": float_hex(component["center"])}
    index = int(component["contract_i"])
    return {"kind": "WALL", "name": str(component["name"]),
            "source_mask": int(component["source_mask"]), "right": int(cache["right"][index]),
            "strike_f64": float_hex(cache["strike"][index]),
            "weight_f64": float_hex(component["weight"]),
            "center_f64": float_hex(component["center"])}


def component_sort_key(component: Mapping[str, Any], cache: Mapping[str, np.ndarray]) -> tuple[Any, ...]:
    index = component.get("contract_i")
    right = -1 if index is None else int(cache["right"][int(index)])
    strike = float("-inf") if index is None else float(cache["strike"][int(index)])
    return (float(component["center"]), int(component["source_mask"]), str(component["name"]),
            right, strike, float(component.get("ratio", float("-inf"))),
            float(component.get("weight", float("-inf"))))


def anchor_payload(source: Mapping[str, Any], cluster_ordinal: int, center: float,
                   band: float, source_mask: int, components: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"anchor_schema": "C_GEOMETRY_1030_ANCHOR_V1", "ticker": source["ticker"],
            "date": source["trade_date"].isoformat(), "state_i": 60, "close_i": source["close_i"],
            "cluster_ordinal": cluster_ordinal, "center_f64": float_hex(center),
            "band_f64": float_hex(band), "source_mask": source_mask,
            "components": list(components)}


def reconstruct_identity(source: Mapping[str, Any], engines: Engines,
                         arrays: Mapping[str, np.ndarray] | None = None,
                         metadata: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    day = source["trade_date"]
    clock_ns = np.datetime64(f"{day.isoformat()}T10:30:00", "ns")
    common = {"calendar_ordinal": source["calendar_ordinal"], "ticker": source["ticker"],
              "trade_date": day, "authority_period": source["authority"],
              "session_kind": source["session_kind"], "close_i": source["close_i"],
              "state_i": 60, "state_clock_local": clock_ns}
    if source["cache_status"] == "MISSING":
        state = {**common, "source_status": "MISSING", "geometry_status": "MISSING_SOURCE",
                 "missing_reason": "SOURCE_PLAN_MISSING", "formed_from_start": None,
                 "formed_from_end": None, "first_available_at": None, "spot_1030": None,
                 "ib_observed": None, "ib_low": None, "ib_high": None, "ib_range": None,
                 "band": None, "tau_years": None, "level_count": 0,
                 "known_contract_count": None, "oi_known_count": None, "oi_missing_count": None,
                 "fib_component_count": None, "call_oi_wall_count": None,
                 "put_oi_wall_count": None, "call_gamma_wall_count": None,
                 "put_gamma_wall_count": None, "cache_metadata_path": None,
                 "cache_metadata_sha256": None, "cache_npz_path": None,
                 "cache_npz_sha256": None, "clock_basis": None, "oi_clock_basis": None,
                 "oi_assumed_availability": None, "clock_delay_applied": None,
                 "receipt_status": "NOT_APPLICABLE"}
        return state, []
    if arrays is None or metadata is None:
        raise AuditError("available cache not loaded")
    clock = engines.clock.FULL if source["session_kind"] == "FULL" else engines.clock.SHORT
    engines.session_level.validate_cache(arrays, clock)
    expected_times = np.arange(clock.n_slots, dtype=np.int64) * 60_000_000_000
    expected_times += np.datetime64(f"{day.isoformat()}T09:30:00", "ns").astype(np.int64)
    if not np.array_equal(np.asarray(arrays["time_ns"], dtype=np.int64), expected_times):
        raise AuditError("cache NY naive minute axis")
    formed_start = np.datetime64(int(expected_times[0]), "ns")
    formed_end = np.datetime64(int(expected_times[59]), "ns")
    provenance = {"cache_metadata_path": source["cache_metadata_path"],
                  "cache_metadata_sha256": source["cache_metadata_sha256"],
                  "cache_npz_path": source["npz_path"], "cache_npz_sha256": source["npz_sha256"],
                  "clock_basis": metadata["clock_basis"], "oi_clock_basis": metadata["oi_clock_basis"],
                  "oi_assumed_availability": metadata["oi_assumed_availability"],
                  "clock_delay_applied": metadata["clock_delay_applied"], "receipt_status": "UNVERIFIED"}
    ib = engines.level.ib_bounds(arrays)
    if ib is None:
        return ({**common, "source_status": "AVAILABLE", "geometry_status": "INVALID_IB",
                 "missing_reason": None, "formed_from_start": formed_start, "formed_from_end": formed_end,
                 "first_available_at": None, "spot_1030": None, "ib_observed": None,
                 "ib_low": None, "ib_high": None, "ib_range": None, "band": None,
                 "tau_years": None, "level_count": 0, "known_contract_count": None,
                 "oi_known_count": None, "oi_missing_count": None, "fib_component_count": None,
                 "call_oi_wall_count": None, "put_oi_wall_count": None,
                 "call_gamma_wall_count": None, "put_gamma_wall_count": None, **provenance}, [])
    low, high, observed = ib
    spot = float(arrays["spot"][60])
    valid_spot = bool(arrays["spot_valid"][60]) and np.isfinite(spot) and spot > 0
    if not valid_spot:
        return ({**common, "source_status": "AVAILABLE", "geometry_status": "INVALID_STATE60",
                 "missing_reason": None, "formed_from_start": formed_start, "formed_from_end": formed_end,
                 "first_available_at": None, "spot_1030": None, "ib_observed": observed,
                 "ib_low": low, "ib_high": high, "ib_range": high - low, "band": None,
                 "tau_years": None, "level_count": 0, "known_contract_count": None,
                 "oi_known_count": None, "oi_missing_count": None, "fib_component_count": None,
                 "call_oi_wall_count": None, "put_oi_wall_count": None,
                 "call_gamma_wall_count": None, "put_gamma_wall_count": None, **provenance}, [])
    oi = engines.session_level.available_oi_matrix(arrays, clock)[60]
    known = engines.level.known_contract_matrix(arrays)[60]
    band = max(0.05 * (high - low), 0.0001 * spot)
    clusters = engines.session_level.causal_levels(arrays, oi, 60, low, high, band, clock)
    raw_counts = Counter()
    level_rows = []
    for cluster in clusters:
        raw = json.loads(cluster["components_json"])
        raw.sort(key=lambda item: component_sort_key(item, arrays))
        semantic = [semantic_component(item, arrays) for item in raw]
        for item in raw:
            raw_counts[item["name"]] += 1
        payload = anchor_payload(source, int(cluster["level_id"]), float(cluster["center"]),
                                 band, int(cluster["source_mask"]), semantic)
        anchor = hashlib.sha256(canonical_json(payload)).hexdigest()
        level_rows.append({"calendar_ordinal": source["calendar_ordinal"],
                           "cluster_ordinal": int(cluster["level_id"]), "anchor_id": anchor,
                           "ticker": source["ticker"], "trade_date": day,
                           "session_kind": source["session_kind"], "close_i": source["close_i"],
                           "state_i": 60, "first_available_at": clock_ns,
                           "center": float(cluster["center"]), "band": band,
                           "source_mask": int(cluster["source_mask"]),
                           "n_components": int(cluster["n_components"]),
                           "semantic_components_json": canonical_json(semantic).decode("utf-8"),
                           "provenance_components_json": canonical_json(raw).decode("utf-8"),
                           "cache_npz_path": source["npz_path"],
                           "cache_npz_sha256": source["npz_sha256"],
                           "clock_basis": metadata["clock_basis"],
                           "oi_clock_basis": metadata["oi_clock_basis"],
                           "receipt_status": "UNVERIFIED"})
    state = {**common, "source_status": "AVAILABLE", "geometry_status": "AVAILABLE_GEOMETRY",
             "missing_reason": None, "formed_from_start": formed_start, "formed_from_end": formed_end,
             "first_available_at": clock_ns, "spot_1030": spot, "ib_observed": observed,
             "ib_low": low, "ib_high": high, "ib_range": high - low, "band": band,
             "tau_years": (source["close_i"] - 60) * 60 / (365 * 86400),
             "level_count": len(level_rows), "known_contract_count": int(known.sum()),
             "oi_known_count": int((known & np.isfinite(oi)).sum()),
             "oi_missing_count": int((known & ~np.isfinite(oi)).sum()),
             "fib_component_count": raw_counts["FIB"], "call_oi_wall_count": raw_counts["CALL_OI"],
             "put_oi_wall_count": raw_counts["PUT_OI"],
             "call_gamma_wall_count": raw_counts["CALL_BS_GAMMA_PROXY"],
             "put_gamma_wall_count": raw_counts["PUT_BS_GAMMA_PROXY"], **provenance}
    return state, level_rows


def tables_from_rows(states: Sequence[Mapping[str, Any]], levels: Sequence[Mapping[str, Any]]) -> tuple[pa.Table, pa.Table]:
    return (pa.Table.from_pylist(list(states), schema=state_schema()),
            pa.Table.from_pylist(list(levels), schema=level_schema()))


def assert_tables_equal(expected: pa.Table, actual: pa.Table, label: str) -> None:
    if actual.schema != expected.schema:
        raise AuditError(f"{label} schema")
    if actual.num_rows != expected.num_rows:
        raise AuditError(f"{label} rows")
    if not actual.equals(expected, check_metadata=True):
        raise AuditError(f"{label} content/order/null")


def coverage_from_states(states: Sequence[Mapping[str, Any]], level_rows: int) -> dict[str, Any]:
    counts = Counter(row["geometry_status"] for row in states)
    available = [row for row in states if row["source_status"] == "AVAILABLE"]
    return {"status": "C_GEOMETRY_1030_CLOSED", "calendar_rows": 2790,
            "available_sources": len(available), "missing_sources": 18,
            "h1_full_available": sum(row["authority_period"] == "H1" and row["session_kind"] == "FULL" and row["source_status"] == "AVAILABLE" for row in states),
            "h1_short_available": sum(row["authority_period"] == "H1" and row["session_kind"] == "SHORT" and row["source_status"] == "AVAILABLE" for row in states),
            "q3_available": sum(row["authority_period"] == "Q3" and row["source_status"] == "AVAILABLE" for row in states),
            "h1_missing": sum(row["authority_period"] == "H1" and row["source_status"] == "MISSING" for row in states),
            "q3_missing": sum(row["authority_period"] == "Q3" and row["source_status"] == "MISSING" for row in states),
            "geometry_available": counts["AVAILABLE_GEOMETRY"], "invalid_ib": counts["INVALID_IB"],
            "invalid_state60": counts["INVALID_STATE60"], "state_rows": len(states),
            "level_rows": level_rows, "entry_frozen_supported": True,
            "session_1030_reset_supported": True, "event_rules_adopted": False,
            "data_scope": "SEEN_DEVELOPMENT"}


def validate_coverage(value: Any, expected: Mapping[str, Any]) -> None:
    if not isinstance(value, dict) or set(value) != set(expected) or value != expected:
        raise AuditError("coverage exact")


def physical_inputs_digest(pins: Mapping[str, Pin]) -> str:
    records = []
    for path_name, pin in sorted(pins.items()):
        info = Path(path_name).stat()
        records.append({"path": pin.path, "bytes": pin.bytes, "sha256": pin.sha256,
                        "physical_identity": [int(info.st_dev), int(info.st_ino)]})
    return hashlib.sha256(canonical_json(records)).hexdigest()


def validate_manifest(value: Any, coverage: Mapping[str, Any], output_root: Path,
                      binding: Mapping[str, Any], input_pins: Mapping[str, Pin]) -> None:
    keys = {"status", "contract", "implementation", "authorities", "authority_pins",
            "input_count", "inputs_digest", "outputs", "counts", "journal_closure",
            "resource_policy", "created_at_utc", "no_events", "no_labels",
            "no_weekly_selection", "no_economics"}
    if not isinstance(value, dict) or set(value) != keys or value["status"] != "C_GEOMETRY_1030_CLOSED":
        raise AuditError("producer manifest schema/status")
    if set(value["outputs"]) != {"geometry_states_1030.parquet", "geometry_levels_1030.parquet", "coverage.json"}:
        raise AuditError("producer manifest outputs")
    expected_contracts = {path.name: strict_pin(binding["authority_pins"][name], name).__dict__
                          for name, (path, _size, _sha) in AUTHORITY_PINS.items()}
    if value["contract"] != expected_contracts:
        raise AuditError("producer manifest contracts")
    if value["implementation"] != strict_pin(binding["implementation_pins"]["producer"], "producer").__dict__:
        raise AuditError("producer manifest implementation")
    if value["authorities"] != {"b_bundle": strict_pin(binding["b_final_bundle"], "bundle").__dict__,
                                 "b_review": strict_pin(binding["b_final_review"], "review").__dict__}:
        raise AuditError("producer manifest authorities")
    expected_authority_pins = {
        "calendar": strict_pin(binding["calendar"], "calendar").__dict__,
        "cache_admission": strict_pin(binding["cache_admission"], "cache admission").__dict__,
        "engines": {name: strict_pin(binding["implementation_pins"][name], name).__dict__ for name in ENGINE_PINS},
    }
    if value["authority_pins"] != expected_authority_pins:
        raise AuditError("producer manifest authority pins")
    if value["input_count"] != len(input_pins):
        raise AuditError("producer manifest input count")
    if value["inputs_digest"] != physical_inputs_digest(input_pins):
        raise AuditError("producer manifest inputs digest")
    rows = {"geometry_states_1030.parquet": 2790,
            "geometry_levels_1030.parquet": coverage["level_rows"], "coverage.json": None}
    for name, expected_rows in rows.items():
        record = value["outputs"][name]
        if set(record) != {"path", "bytes", "sha256", "rows"} or record["rows"] != expected_rows:
            raise AuditError("producer output record")
        pin = strict_pin({key: record[key] for key in ("path", "bytes", "sha256")}, name)
        if Path(pin.path) != output_root / name:
            raise AuditError("producer output path")
        guard_regular(Path(pin.path), pin)
    if value["counts"] != {key: coverage[key] for key in ("calendar_rows", "available_sources", "missing_sources", "geometry_available", "invalid_ib", "invalid_state60", "state_rows", "level_rows")}:
        raise AuditError("producer manifest counts")
    closure = value["journal_closure"]
    if (not isinstance(closure, dict) or set(closure) != {"prepublish_last_seq", "prepublish_prefix_sha256"} or
            type(closure["prepublish_last_seq"]) is not int or closure["prepublish_last_seq"] < 1 or
            type(closure["prepublish_prefix_sha256"]) is not str or len(closure["prepublish_prefix_sha256"]) != 64):
        raise AuditError("producer manifest journal closure")
    if value["resource_policy"] != {"minimum_bytes": 2_000_000_000, "cpu_affinity": [0], "threads": 1}:
        raise AuditError("producer manifest resource policy")
    if any(value[name] is not True for name in ("no_events", "no_labels", "no_weekly_selection", "no_economics")):
        raise AuditError("producer manifest scope")
    try:
        datetime.fromisoformat(value["created_at_utc"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise AuditError("producer manifest created_at_utc") from exc


def preflight_manifest_outputs(value: Any, output_root: Path) -> dict[str, Pin]:
    if not isinstance(value, dict) or not isinstance(value.get("outputs"), dict):
        raise AuditError("producer manifest outputs")
    expected_names = {"geometry_states_1030.parquet", "geometry_levels_1030.parquet", "coverage.json"}
    if set(value["outputs"]) != expected_names:
        raise AuditError("producer manifest outputs")
    pins: dict[str, Pin] = {}
    for name, record in value["outputs"].items():
        if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256", "rows"}:
            raise AuditError("producer output record")
        pin = strict_pin({key: record[key] for key in ("path", "bytes", "sha256")}, name)
        if Path(pin.path) != output_root / name:
            raise AuditError("producer output path")
        guard_regular(Path(pin.path), pin)
        pins[name] = pin
    return pins


def validate_parquet_physical(path: Path, expected_schema: pa.Schema, states: bool) -> None:
    parquet = pq.ParquetFile(path)
    if parquet.schema_arrow != expected_schema:
        raise AuditError("Parquet physical schema")
    metadata = parquet.metadata
    if states and metadata.num_row_groups != 1:
        raise AuditError("states row groups")
    previous_last: int | None = None
    for group_index in range(metadata.num_row_groups):
        group = metadata.row_group(group_index)
        if not states and group.num_rows > 65_536:
            raise AuditError("levels row group size")
        for column_index in range(group.num_columns):
            column = group.column(column_index)
            if column.compression != "ZSTD" or column.statistics is None:
                raise AuditError("Parquet encoding/statistics")
            if any("DICTIONARY" in encoding for encoding in column.encodings):
                raise AuditError("Parquet dictionary encoding")
        if not states and group.num_rows:
            ordinals = parquet.read_row_group(group_index, columns=["calendar_ordinal"], use_threads=False).column(0)
            first, last = int(ordinals[0].as_py()), int(ordinals[-1].as_py())
            if previous_last is not None and first == previous_last:
                raise AuditError("identity split across row groups")
            previous_last = last


def validate_producer_journal(rows: Sequence[Mapping[str, Any]], identities: Sequence[Mapping[str, Any]],
                              input_pins: Mapping[str, Pin], output_pins: Mapping[str, Pin],
                              producer_root: Path, authority_units: Mapping[str, Pin]) -> None:
    required = {"seq", "utc", "kind", "identity", "phase", "paths", "gate", "details"}
    allowed = {"ADMIT_AUTHORITY", "GEOMETRY_IDENTITY", "WRITE_OUTPUT", "CLOSING_INPUT", "CLOSING_OUTPUT", "PUBLISH_ROOT"}
    if [row.get("seq") for row in rows] != list(range(len(rows))):
        raise AuditError("journal sequence")
    lifecycle: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in rows:
        if set(row) != required or row["kind"] not in allowed or row["phase"] not in {"START", "COMPLETE", "ERROR"}:
            raise AuditError("journal schema")
        if row["phase"] == "ERROR":
            raise AuditError("journal error")
        try:
            parsed_utc = datetime.fromisoformat(row["utc"].replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise AuditError("journal utc") from exc
        if parsed_utc.tzinfo is None:
            raise AuditError("journal utc")
        if not isinstance(row["paths"], list) or not isinstance(row["details"], dict):
            raise AuditError("journal paths/details")
        if (set(row["gate"]) != {"available_ram_bytes", "free_commit_bytes", "disk_free_bytes"} or
                any(type(value) is not int or value < 2_000_000_000 for value in row["gate"].values())):
            raise AuditError("journal resource gate")
        lifecycle[(row["kind"], row["identity"])].append(row["phase"])
    if any(phases != ["START", "COMPLETE"] for phases in lifecycle.values()):
        raise AuditError("journal lifecycle")
    rank = {name: index for index, name in enumerate(
            ("ADMIT_AUTHORITY", "GEOMETRY_IDENTITY", "WRITE_OUTPUT",
             "CLOSING_INPUT", "CLOSING_OUTPUT", "PUBLISH_ROOT"))}
    if [rank[row["kind"]] for row in rows] != sorted(rank[row["kind"]] for row in rows):
        raise AuditError("journal block order")
    for index in range(0, len(rows), 2):
        if (index + 1 >= len(rows) or rows[index]["phase"] != "START" or
                rows[index + 1]["phase"] != "COMPLETE" or
                (rows[index]["kind"], rows[index]["identity"]) !=
                (rows[index + 1]["kind"], rows[index + 1]["identity"])):
            raise AuditError("journal adjacent lifecycle")
    expected_authorities = set(authority_units)
    actual_authorities = {identity for kind, identity in lifecycle if kind == "ADMIT_AUTHORITY"}
    if actual_authorities != expected_authorities:
        raise AuditError("journal authority identities")
    for row in rows:
        if row["kind"] != "ADMIT_AUTHORITY":
            continue
        expected_authority = authority_units[row["identity"]]
        if row["paths"] != [expected_authority.path] or row["paths"][0] not in input_pins:
            raise AuditError("journal authority path")
        if row["phase"] == "START" and row["details"] != {}:
            raise AuditError("journal authority start details")
        if row["phase"] == "COMPLETE":
            if set(row["details"]) != {"before", "after", "physical_identity"}:
                raise AuditError("journal authority details")
            expected = expected_authority
            if strict_pin(row["details"]["before"], "authority before") != expected or strict_pin(row["details"]["after"], "authority after") != expected:
                raise AuditError("journal authority pin")
            info = Path(expected.path).stat()
            if row["details"]["physical_identity"] != [int(info.st_dev), int(info.st_ino)]:
                raise AuditError("journal authority physical identity")
    geometry_ids = {f'{row["ticker"]}:{str(row["date"]).replace("-", "")}' for row in identities}
    actual_geometry = {identity for kind, identity in lifecycle if kind == "GEOMETRY_IDENTITY"}
    if actual_geometry != geometry_ids:
        raise AuditError("journal geometry identities")
    identity_map = {f'{row["ticker"]}:{str(row["date"]).replace("-", "")}': row for row in identities}
    for row in rows:
        if row["kind"] != "GEOMETRY_IDENTITY" or row["phase"] != "COMPLETE":
            continue
        source = identity_map[row["identity"]]
        details = row["details"]
        if set(details) != {"geometry_status", "level_rows", "opened_array_names", "physical_array_names", "inputs"}:
            raise AuditError("journal geometry details")
        expected_status = source.get("audited_geometry_status")
        if expected_status is None:
            expected_status = "MISSING_SOURCE" if source["cache_status"] == "MISSING" else None
        if details["geometry_status"] != expected_status or details["level_rows"] != source.get("audited_level_rows", 0):
            raise AuditError("journal geometry outcome")
        if source["cache_status"] == "MISSING":
            if (row["paths"] != [] or details["opened_array_names"] != [] or
                    details["physical_array_names"] != [] or details["inputs"] != {}):
                raise AuditError("journal missing opened input")
            continue
        if row["paths"] != [source["cache_metadata_path"], source["npz_path"]]:
            raise AuditError("journal geometry paths")
        if details["opened_array_names"] != list(ARRAYS):
            raise AuditError("journal opened array whitelist")
        physical = details["physical_array_names"]
        if (not isinstance(physical, list) or set(physical) not in
                (set(ARRAYS), set(ARRAYS) | {OPTIONAL_DECLARED_ARRAY})):
            raise AuditError("journal physical arrays")
        if set(details["inputs"]) != {"metadata", "npz"}:
            raise AuditError("journal geometry input details")
        for role, expected in (("metadata", Pin(source["cache_metadata_path"], source["cache_metadata_bytes"], source["cache_metadata_sha256"])),
                               ("npz", Pin(source["npz_path"], source["npz_bytes"], source["npz_sha256"]))):
            pair = details["inputs"][role]
            if set(pair) != {"before", "after"} or strict_pin(pair["before"], role) != expected or strict_pin(pair["after"], role) != expected:
                raise AuditError("journal geometry input pin")
    writes = {identity for kind, identity in lifecycle if kind == "WRITE_OUTPUT"}
    if writes != {"geometry_states_1030.parquet", "geometry_levels_1030.parquet", "coverage.json", "manifest.json"}:
        raise AuditError("journal output identities")
    write_starts = [row["identity"] for row in rows if row["kind"] == "WRITE_OUTPUT" and row["phase"] == "START"]
    if write_starts != ["geometry_states_1030.parquet", "geometry_levels_1030.parquet", "coverage.json", "manifest.json"]:
        raise AuditError("journal write order")
    for row in rows:
        if row["kind"] != "WRITE_OUTPUT":
            continue
        if len(row["paths"]) != 1 or Path(row["paths"][0]).name != row["identity"]:
            raise AuditError("journal write path")
        if Path(row["paths"][0]).parent.parent != producer_root.parent:
            raise AuditError("journal write staging root")
        if row["phase"] == "START" and row["details"] != {}:
            raise AuditError("journal write start details")
        if row["phase"] == "COMPLETE":
            if set(row["details"]) != {"pin"}:
                raise AuditError("journal write details")
            pin_value = row["details"]["pin"]
            if not isinstance(pin_value, dict) or set(pin_value) != {"path", "bytes", "sha256", "rows"}:
                raise AuditError("journal write pin schema")
            pin = strict_pin({key: pin_value[key] for key in ("path", "bytes", "sha256")}, "write output")
            expected = output_pins[row["identity"]]
            expected_rows = (len(identities) if row["identity"] == "geometry_states_1030.parquet" else
                             sum(int(item.get("audited_level_rows", 0)) for item in identities)
                             if row["identity"] == "geometry_levels_1030.parquet" else None)
            if pin_value["rows"] != expected_rows:
                raise AuditError("journal write rows")
            if (pin.bytes, pin.sha256) != (expected.bytes, expected.sha256):
                raise AuditError("journal write pin")
            if row["identity"] != "manifest.json" and Path(pin.path) != producer_root / row["identity"]:
                raise AuditError("journal write final path")
            if row["identity"] == "manifest.json" and Path(pin.path) != Path(row["paths"][0]):
                raise AuditError("journal write manifest staging path")
    closing_inputs = {identity for kind, identity in lifecycle if kind == "CLOSING_INPUT"}
    if closing_inputs != set(input_pins):
        raise AuditError("journal closing inputs")
    closing_outputs = {identity for kind, identity in lifecycle if kind == "CLOSING_OUTPUT"}
    if closing_outputs != set(output_pins):
        raise AuditError("journal closing outputs")
    if {identity for kind, identity in lifecycle if kind == "PUBLISH_ROOT"} != {producer_root.name}:
        raise AuditError("journal publish root")
    publish_rows = [row for row in rows if row["kind"] == "PUBLISH_ROOT"]
    publish_start, publish_complete = publish_rows
    if len(publish_start["paths"]) != 2:
        raise AuditError("journal publish start")
    staging_path = Path(publish_start["paths"][0])
    if (publish_start["paths"] != [str(staging_path), str(producer_root)] or
            staging_path.parent != producer_root.parent or set(publish_start["details"]) != {"staging_identity"} or
            not isinstance(publish_start["details"]["staging_identity"], list) or
            len(publish_start["details"]["staging_identity"]) != 2 or
            any(type(item) is not int for item in publish_start["details"]["staging_identity"])):
        raise AuditError("journal publish start")
    if (publish_complete["paths"] != [str(producer_root)] or
            publish_complete["details"] != {"status": "C_GEOMETRY_1030_CLOSED",
                                             "staging_identity": publish_start["details"]["staging_identity"]}):
        raise AuditError("journal publish complete")
    for row in rows:
        if row["phase"] != "COMPLETE" or row["kind"] not in {"CLOSING_INPUT", "CLOSING_OUTPUT"}:
            continue
        expected = input_pins.get(row["identity"]) or output_pins.get(row["identity"])
        expected_keys = {"before", "after", "physical_identity"} if row["kind"] == "CLOSING_INPUT" else {"before", "after"}
        if set(row["details"]) != expected_keys:
            raise AuditError("journal closing details")
        before = strict_pin(row["details"]["before"], "journal before")
        after = strict_pin(row["details"]["after"], "journal after")
        if row["paths"] != [before.path]:
            raise AuditError("journal closing paths")
        if before != after:
            raise AuditError("journal closing pin")
        if row["kind"] == "CLOSING_INPUT":
            if before != expected:
                raise AuditError("journal closing pin")
            info = Path(expected.path).stat()
            if row["details"]["physical_identity"] != [int(info.st_dev), int(info.st_ino)]:
                raise AuditError("journal closing physical identity")
        else:
            if (before.bytes, before.sha256) != (expected.bytes, expected.sha256):
                raise AuditError("journal closing output pin")
            staging = Path(before.path)
            final = Path(expected.path)
            if staging.name != row["identity"] or staging == final or staging.parent.parent != final.parent.parent:
                raise AuditError("journal closing output staging path")


def validate_journal_prefix(path: Path, closure: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> None:
    count = int(closure["prepublish_last_seq"])
    if count >= len(rows) or not (rows[count]["kind"] == "WRITE_OUTPUT" and
                                  rows[count]["identity"] == "manifest.json" and
                                  rows[count]["phase"] == "START"):
        raise AuditError("journal prepublish terminal record")
    digest = hashlib.sha256()
    seen = 0
    with path.open("rb") as stream:
        for line in stream:
            seen += 1
            if seen <= count + 1:
                digest.update(line)
    if seen < count + 1 or digest.hexdigest() != closure["prepublish_prefix_sha256"]:
        raise AuditError("journal prepublish prefix")


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, (date, datetime, np.datetime64)):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    return value


def semantic_projection(table: pa.Table, columns: Sequence[str]) -> bytes:
    return canonical_json(jsonable(table.select(columns).to_pylist()))


def assert_future_invariance(original: tuple[pa.Table, pa.Table], variant: tuple[pa.Table, pa.Table]) -> None:
    if semantic_projection(original[0], STATE_SEMANTIC_COLUMNS) != semantic_projection(variant[0], STATE_SEMANTIC_COLUMNS):
        raise AuditError("future state influence")
    if semantic_projection(original[1], LEVEL_SEMANTIC_COLUMNS) != semantic_projection(variant[1], LEVEL_SEMANTIC_COLUMNS):
        raise AuditError("future level influence")


def reconstructed_tables(source: Mapping[str, Any], engines: Engines,
                         arrays: Mapping[str, np.ndarray], metadata: Mapping[str, Any]) -> tuple[pa.Table, pa.Table]:
    state, levels = reconstruct_identity(source, engines, arrays, metadata)
    return tables_from_rows([state], levels)


def exercise_input_invariances(source: Mapping[str, Any], engines: Engines,
                               arrays: Mapping[str, np.ndarray], metadata: Mapping[str, Any],
                               baseline: tuple[pa.Table, pa.Table]) -> None:
    suffix = dict(arrays)
    for name in ("bid", "ask", "delta", "iv", "vega", "theta"):
        value = np.asarray(arrays[name]).copy()
        value[61:] = np.where(np.isfinite(value[61:]), -value[61:] - 1.0, 123.0)
        suffix[name] = value
    flags = np.asarray(arrays["row_flags"]).copy()
    flags[61:] ^= np.uint8(7)
    suffix["row_flags"] = flags
    spot = np.asarray(arrays["spot"]).copy()
    spot[61:] = np.arange(len(spot) - 61, dtype=np.float64) + 1.0
    suffix["spot"] = spot
    spot_valid = np.asarray(arrays["spot_valid"]).copy()
    spot_valid[61:] = ~spot_valid[61:]
    suffix["spot_valid"] = spot_valid
    future_oi = np.asarray(arrays["oi_available_ns"]) > int(arrays["time_ns"][60])
    oi_value = np.asarray(arrays["oi_value"]).copy()
    oi_value[future_oi] = np.where(oi_value[future_oi] >= 0, oi_value[future_oi] + 1, 0)
    suffix["oi_value"] = oi_value
    oi_valid = np.asarray(arrays["oi_valid"]).copy()
    oi_valid[future_oi] = ~oi_valid[future_oi]
    suffix["oi_valid"] = oi_valid
    assert_future_invariance(baseline, reconstructed_tables(source, engines, suffix, metadata))

    order = np.arange(len(arrays["strike"]) - 1, -1, -1)
    inverse = np.empty(len(order), dtype=np.int32)
    inverse[order] = np.arange(len(order), dtype=np.int32)
    permuted = dict(arrays)
    for name in ("strike", "right"):
        permuted[name] = np.asarray(arrays[name])[order]
    for name in ("bid", "ask", "delta", "iv", "vega", "theta", "row_flags"):
        permuted[name] = np.asarray(arrays[name])[:, order]
    permuted["oi_contract_idx"] = inverse[np.asarray(arrays["oi_contract_idx"], dtype=np.int32)]
    assert_future_invariance(baseline, reconstructed_tables(source, engines, permuted, metadata))

    added = dict(arrays)
    added["strike"] = np.append(np.asarray(arrays["strike"]), float(np.max(arrays["strike"])) * 2.0 + 1.0)
    added["right"] = np.append(np.asarray(arrays["right"]), np.int8(0))
    slots = len(arrays["time_ns"])
    for name in ("bid", "ask", "delta", "iv", "vega", "theta"):
        column = np.full((slots, 1), np.nan, dtype=np.asarray(arrays[name]).dtype)
        added[name] = np.concatenate((np.asarray(arrays[name]), column), axis=1)
    added_flags = np.zeros((slots, 1), dtype=np.uint8)
    added_flags[61:] = 1
    added["row_flags"] = np.concatenate((np.asarray(arrays["row_flags"]), added_flags), axis=1)
    added["iv"][61:, -1] = 0.2
    added["oi_contract_idx"] = np.append(np.asarray(arrays["oi_contract_idx"]), np.int32(len(added["strike"]) - 1))
    added["oi_value"] = np.append(np.asarray(arrays["oi_value"]), np.int64(999))
    added["oi_available_ns"] = np.append(np.asarray(arrays["oi_available_ns"]), np.int64(arrays["time_ns"][61]))
    added["oi_valid"] = np.append(np.asarray(arrays["oi_valid"]), True)
    assert_future_invariance(baseline, reconstructed_tables(source, engines, added, metadata))


def load_compact_json(path: Path, pin: Pin) -> dict[str, Any]:
    guard_regular(path, pin)
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or raw != canonical_json(json.loads(raw)) + b"\n":
        raise AuditError(f"noncanonical JSON: {path}")
    return json.loads(raw)


def run(binding_path: Path, binding_sha256: str, output: Path, observer: Path) -> dict[str, Any]:
    binding = load_runtime_binding(binding_path, binding_sha256)
    require_runtime_roots(binding, output, observer)
    verify_static_authorities(binding)
    observation, gate = bind_resource_helper()
    resource_gate(observation, gate, Path(binding_path.anchor))
    observer.mkdir(parents=True, exist_ok=False)
    audit_journal = AuditJournal(observer / "journal.jsonl", observation, gate, Path(observer.anchor))
    binding_pin = Pin(str(binding_path), binding_path.stat().st_size, binding_sha256)
    evidence_pins = {binding_pin.path: binding_pin}
    for name in ("producer_exit", "producer_process", "producer_journal", "producer_manifest"):
        pin = strict_pin(binding[name], name)
        if pin.path in evidence_pins:
            raise AuditError("duplicate producer evidence path")
        evidence_pins[pin.path] = pin
    require_distinct_physical_files(evidence_pins.values())
    evidence_snapshots = {path_text: file_snapshot(Path(path_text), pin)
                          for path_text, pin in evidence_pins.items()}
    validate_retained_closure(read_pinned_json(binding["producer_exit"], "producer exit"),
                              read_pinned_json(binding["producer_process"], "producer process"))
    bundle_pin = strict_pin(binding["b_final_bundle"], "B final bundle")
    guard_regular(Path(bundle_pin.path), bundle_pin)
    bundle_value = json.loads(Path(bundle_pin.path).read_text(encoding="utf-8"))
    validate_final_b_bundle(bundle_value, binding)
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    engines = bind_engines()
    producer_root, _producer_observer = guard_published_roots(binding)
    manifest_pin = strict_pin(binding["producer_manifest"], "producer manifest")
    manifest = load_compact_json(Path(manifest_pin.path), manifest_pin)
    producer_output_pins = preflight_manifest_outputs(manifest, producer_root)
    for pin in producer_output_pins.values():
        if pin.path in evidence_pins:
            raise AuditError("duplicate producer evidence path")
        evidence_pins[pin.path] = pin
        evidence_snapshots[pin.path] = file_snapshot(Path(pin.path), pin)
    require_distinct_physical_files(evidence_pins.values())
    calendar_pin = strict_pin(binding["calendar"], "calendar")
    guard_regular(Path(calendar_pin.path), calendar_pin)
    calendar = validate_calendar_document(json.loads(Path(calendar_pin.path).read_text(encoding="utf-8")))
    admission_pin = strict_pin(binding["cache_admission"], "cache admission")
    guard_regular(Path(admission_pin.path), admission_pin)
    identities = validate_cache_admission(parse_jsonl(Path(admission_pin.path)))
    if [(row["ticker"], row["date"], row["close_i"]) for row in identities] != [
            (row["ticker"], row["date"], row["close_i"]) for row in calendar]:
        raise AuditError("calendar/cache admission identity")
    states, levels = [], []
    authority_units = {
        "binding_bundle": bundle_pin,
        "binding_review": strict_pin(binding["b_final_review"], "b final review"),
        "calendar": calendar_pin, "cache_admission": admission_pin,
        "implementation": strict_pin(binding["implementation_pins"]["producer"], "producer implementation"),
        "resource_helper": strict_pin(binding["implementation_pins"]["resource_helper"], "resource helper"),
        **{f"contract:{path.name}": strict_pin(binding["authority_pins"][name], name)
           for name, (path, _size, _sha) in AUTHORITY_PINS.items()},
        **{f"engine:{name}": strict_pin(binding["implementation_pins"][name], name) for name in ENGINE_PINS},
        **final_b_proof_pins(bundle_value),
    }
    initial_inputs = list(authority_units.values())
    input_pins: dict[str, Pin] = {}
    for initial_pin in initial_inputs:
        if initial_pin.path in input_pins and input_pins[initial_pin.path] != initial_pin:
            raise AuditError("conflicting admitted input pin")
        input_pins[initial_pin.path] = initial_pin
    if set(input_pins) & set(evidence_pins):
        raise AuditError("producer evidence reused as admitted input")
    require_distinct_physical_files(list(input_pins.values()) + list(evidence_pins.values()))
    initial_snapshots = {path_text: file_snapshot(Path(path_text), pin)
                         for path_text, pin in input_pins.items()}
    validate_final_b_closure(bundle_value)
    for path_text, snapshot in initial_snapshots.items():
        if file_snapshot(Path(path_text), Pin(**snapshot["pin"])) != snapshot:
            raise AuditError("B closure input snapshot drift")
    for source in identities:
        identity = f'{source["ticker"]}:{source["date"]}'
        paths = [] if source["cache_status"] == "MISSING" else [source["cache_metadata_path"], source["npz_path"]]
        with audit_journal.unit("AUDIT_GEOMETRY_IDENTITY", identity, paths) as unit_details:
            arrays = metadata = None
            snapshots: dict[str, dict[str, Any]] = {}
            if source["cache_status"] == "AVAILABLE":
                metadata_input = Pin(source["cache_metadata_path"], source["cache_metadata_bytes"], source["cache_metadata_sha256"])
                npz_input = Pin(source["npz_path"], source["npz_bytes"], source["npz_sha256"])
                snapshots = {"metadata": file_snapshot(Path(metadata_input.path), metadata_input),
                             "npz": file_snapshot(Path(npz_input.path), npz_input)}
                arrays, metadata = load_cache(source)
                if (metadata_input.path in input_pins or npz_input.path in input_pins or
                        metadata_input.path in evidence_pins or npz_input.path in evidence_pins):
                    raise AuditError("duplicate physical input path")
                input_pins[metadata_input.path] = metadata_input
                input_pins[npz_input.path] = npz_input
                initial_snapshots[metadata_input.path] = snapshots["metadata"]
                initial_snapshots[npz_input.path] = snapshots["npz"]
            state, identity_levels = reconstruct_identity(source, engines, arrays, metadata)
            if arrays is not None and metadata is not None:
                baseline_identity = tables_from_rows([state], identity_levels)
                exercise_input_invariances(source, engines, arrays, metadata, baseline_identity)
                for role, snapshot in snapshots.items():
                    expected = Pin(**snapshot["pin"])
                    if file_snapshot(Path(expected.path), expected) != snapshot:
                        raise AuditError("identity input snapshot drift")
            source["audited_geometry_status"] = state["geometry_status"]
            source["audited_level_rows"] = len(identity_levels)
            unit_details.update({"geometry_status": state["geometry_status"],
                                 "level_rows": len(identity_levels), "snapshots": snapshots})
            states.append(state)
            levels.extend(identity_levels)
    expected_states, expected_levels = tables_from_rows(states, levels)
    verification_paths = [pin.path for pin in producer_output_pins.values()] + [manifest_pin.path]
    with audit_journal.unit("VERIFY_PRODUCER_OUTPUTS", "FINAL_OUTPUTS", verification_paths) as details:
        before = {path_text: file_snapshot(Path(path_text), pin)
                  for path_text, pin in evidence_pins.items() if path_text in verification_paths}
        validate_parquet_physical(producer_root / "geometry_states_1030.parquet", state_schema(), True)
        validate_parquet_physical(producer_root / "geometry_levels_1030.parquet", level_schema(), False)
        actual_states = pq.read_table(producer_root / "geometry_states_1030.parquet", use_threads=False)
        actual_levels = pq.read_table(producer_root / "geometry_levels_1030.parquet", use_threads=False)
        assert_tables_equal(expected_states, actual_states, "states")
        assert_tables_equal(expected_levels, actual_levels, "levels")
        coverage = coverage_from_states(states, len(levels))
        coverage_record = manifest["outputs"]["coverage.json"]
        coverage_pin = strict_pin({key: coverage_record[key] for key in ("path", "bytes", "sha256")},
                                  "coverage")
        validate_coverage(load_compact_json(Path(coverage_pin.path), coverage_pin), coverage)
        require_distinct_physical_files(list(input_pins.values()) + list(evidence_pins.values()))
        validate_manifest(manifest, coverage, producer_root, binding, input_pins)
        after = {path_text: file_snapshot(Path(path_text), evidence_pins[path_text])
                 for path_text in before}
        if before != after or any(before[path_text] != evidence_snapshots[path_text]
                                  for path_text in before):
            raise AuditError("producer output evidence drift")
        details.update({"before": before, "after": after})
    output_pins = dict(producer_output_pins)
    output_pins["manifest.json"] = manifest_pin
    journal_pin = strict_pin(binding["producer_journal"], "producer journal")
    with audit_journal.unit("VERIFY_PRODUCER_JOURNAL", "PRODUCER_JOURNAL", [journal_pin.path]) as details:
        before = file_snapshot(Path(journal_pin.path), journal_pin)
        journal_rows = parse_jsonl(Path(journal_pin.path))
        validate_producer_journal(journal_rows, identities, input_pins, output_pins,
                                  producer_root, authority_units)
        validate_journal_prefix(Path(journal_pin.path), manifest["journal_closure"], journal_rows)
        after = file_snapshot(Path(journal_pin.path), journal_pin)
        if before != after or before != evidence_snapshots[journal_pin.path]:
            raise AuditError("producer journal evidence drift")
        details.update({"before": before, "after": after})
    if set(input_pins) & set(evidence_pins):
        raise AuditError("producer evidence reused as admitted input")
    require_distinct_physical_files(list(input_pins.values()) + list(evidence_pins.values()))
    audit_closing_pins = merge_closing_pins(input_pins, evidence_pins)
    audit_initial_snapshots = {**initial_snapshots, **evidence_snapshots}
    for path_text, pin in sorted(audit_closing_pins.items()):
        with audit_journal.unit("AUDIT_CLOSING_INPUT", path_text, [path_text]) as details:
            before = file_snapshot(Path(path_text), pin)
            after = file_snapshot(Path(path_text), pin)
            if before != after or before != audit_initial_snapshots[path_text]:
                raise AuditError("audit closing input drift")
            details.update({"before": before, "after": after})
    result = {"status": "PASS_INDEPENDENT_C_GEOMETRY_1030_AUDIT", "state_rows": 2790,
              "level_rows": len(levels), "available_sources": 2772, "missing_sources": 18,
              "producer_manifest_sha256": manifest_pin.sha256, "no_events": True,
              "no_labels": True, "no_weekly_selection": True, "no_economics": True}
    resource_gate(observation, gate, Path(output.anchor))
    output.mkdir(parents=True, exist_ok=False)
    with audit_journal.unit("WRITE_AUDIT_OUTPUT", "audit.json", [str(output / "audit.json")]) as details:
        audit_pin = write_durable_json(output / "audit.json", result)
        details["pin"] = audit_pin.__dict__
    audit_manifest = {"status": result["status"], "producer_manifest": manifest_pin.__dict__,
                      "audit": audit_pin.__dict__, "authorities": sorted(AUTHORITY_PINS),
                      "engines": sorted(ENGINE_PINS),
                      "created_at_utc": datetime.now(timezone.utc).isoformat()}
    with audit_journal.unit("WRITE_AUDIT_OUTPUT", "manifest.json", [str(output / "manifest.json")]) as details:
        audit_manifest_pin = write_durable_json(output / "manifest.json", audit_manifest)
        details["pin"] = audit_manifest_pin.__dict__
    for pin in (audit_pin, audit_manifest_pin):
        with audit_journal.unit("AUDIT_CLOSING_OUTPUT", Path(pin.path).name, [pin.path]) as details:
            before = file_snapshot(Path(pin.path), pin)
            after = file_snapshot(Path(pin.path), pin)
            if before != after:
                raise AuditError("audit closing output drift")
            details.update({"before": before, "after": after})
    audit_journal.close()
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--binding-json", required=True, type=Path)
    value.add_argument("--binding-sha256", required=True)
    value.add_argument("--output-dir", required=True, type=Path)
    value.add_argument("--observer-dir", required=True, type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        result = run(args.binding_json, args.binding_sha256, args.output_dir, args.observer_dir)
    except AuditError as exc:
        print(json.dumps({"status": "AUDIT_FAILED", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
