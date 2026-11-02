"""Independent, outcome-free audit of weekly option and spot value paths.

This module intentionally shares no imports with either value-path producer.
The reviewed CLI is fail-closed and is the only entry point for a real audit.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import struct
from typing import Any, Iterator, Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


HERE = Path(__file__).resolve().parent
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
SOURCE_ROOT = Path(r"D:\ThetaData\data_options")
STAGE_A = BASE / "weekly_zone_event_source_plan_01"
PRODUCER = BASE / "weekly_zone_event_value_paths_02"
OUTPUT = BASE / "weekly_zone_event_value_paths_audit_03"
OBSERVER = BASE / "weekly_zone_event_value_paths_audit_observer_03"
PRODUCER_OBSERVER = BASE / "weekly_zone_event_value_paths_observer_02"
PRIOR_PRODUCER_OBSERVER = BASE / "weekly_zone_event_value_paths_observer_01"
CONTRACT = HERE / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2_CALENDAR_AMENDMENT_20261102.md"
ORIGINAL_CONTRACT = HERE / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md"
TESTS = HERE / "test_audit_weekly_zone_event_value_paths_v2r1.py"
ADMISSION_AMENDMENT = HERE / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R1_AUDIT_ADMISSION_AMENDMENT_20261102.md"
RESOURCE_HELPER = HERE.parent / "level_oracle_20261018" / "launch_monthly_test_index_v2_audit_20261024.py"
CONTRACT_SHA256 = "65fd1aaef25ddea13957ce07e6c21285771adc889f097d603f93e00572cf1146"
ORIGINAL_CONTRACT_SHA256 = "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9"
HELPER_SHA256 = "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"
ADMISSION_AMENDMENT_BYTES = 4291
ADMISSION_AMENDMENT_SHA256 = "2afce2d91e35393aad91e9dd65d6b9d9b6e156c0307ffd0f67823254032943d3"
TICKERS = ("SPY", "QQQ", "SPXW")
TICKER_ORDINAL = {value: index for index, value in enumerate(TICKERS)}
RIGHT_ORDINAL = {"CALL": 0, "PUT": 1}
ROLE_ORDINAL = {"D": 0, "D1": 1, "H2": 2}
NY = ZoneInfo("America/New_York")
REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
TEN_VARS = (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS",
    "ARROW_NUM_THREADS", "POLARS_MAX_THREADS", "TBB_NUM_THREADS", "NUMBA_NUM_THREADS",
)
FORBIDDEN_PARTS = {
    "candidates.jsonl", "context.jsonl", "coverage.json", "index.parquet",
    "state60", "features.npz", "outcomes", "ledger", "scores",
}
_OFFICIAL_OBSERVATION: Any = None
OPTION_COLUMNS = (
    "symbol", "expiration", "trade_date", "strike", "right",
    "underlying_timestamp", "underlying_price", "bid", "ask", "delta",
    "implied_vol", "theta", "vega", "rho",
)
FLOAT_COLUMNS = (
    "underlying_price", "bid", "ask", "delta", "implied_vol", "theta", "vega", "rho",
)
DATA_OUTPUTS = (
    "source_admission.jsonl", "decision_contracts.parquet",
    "option_quote_observations.parquet", "segment_coverage.parquet",
    "cache_admission.jsonl", "spot_paths.parquet", "spot_coverage.jsonl",
)
EXPECTED_FLAGS = {
    "actions_read": False, "candidates_read": False,
    "context_feature_arrays_read": False, "economic_evaluation_performed": False,
    "fit_performed": False, "inference_performed": False, "labels_read": False,
    "models_read": False, "option_raw_values_read": True, "outcomes_read": False,
    "parquet_footers_read": True, "pnl_computed": False,
    "promotion_approved": False, "replay_performed": False,
    "risk_or_qty_computed": False, "selected_policy": None,
    "spot_cache_arrays_read": True, "technical_ready": False,
}
EXPECTED_LIMITATIONS = [
    "Stored timestamps do not prove live receipt time.",
    "Underlying timestamp proxy has unknown age.",
    "Minute samples do not prove intraminute touches.",
    "Outcomes were not read.",
    "No economic evaluation was performed.",
]
RAW_CALENDAR_ORDER = "TICKER_MAJOR_QQQ_SPXW_SPY_DATE_ASC"
CANONICAL_CALENDAR_ORDER = "DATE_ASC_TICKER_ORDINAL_SPY_QQQ_SPXW"
CANONICAL_CALENDAR_BYTES = 137640
CANONICAL_CALENDAR_SHA256 = "13bc456a32c6dc711fffb71ef24375ecd5e455c11a9efedfb117b9ad903fb929"
IMPLEMENTATION_PATHS = {
    "builder": HERE / "build_weekly_zone_event_value_paths_v2.py",
    "spot_module": HERE / "weekly_zone_event_spot_paths.py",
    "builder_tests": HERE / "test_build_weekly_zone_event_value_paths_v2.py",
    "spot_tests": HERE / "test_weekly_zone_event_spot_paths.py",
    "contract": CONTRACT,
    "builder_final_review": HERE / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2_BUILDER_FINAL_REVIEW_20261102.md",
    "spot_final_review": HERE / "WEEKLY_ZONE_EVENT_SPOT_PATH_FINAL_REVIEW_20261102.md",
    "runtime_binding": HERE / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2_RUNTIME_BINDING_20261102.md",
    "launcher": HERE / "launch_weekly_zone_event_value_paths_v2_20261102.py",
    "resource_helper": RESOURCE_HELPER,
}


def decision_schema() -> pa.Schema:
    return pa.schema([
        pa.field("decision_id", pa.string(), False), pa.field("plan_id", pa.string(), False),
        pa.field("source_authority", pa.string(), False), pa.field("ticker", pa.string(), False),
        pa.field("entry_date", pa.string(), False), pa.field("expiration", pa.string(), False),
        pa.field("right", pa.string(), False), pa.field("strike_decimal", pa.string(), False),
        pa.field("decision_clock", pa.string(), False), pa.field("decision_minute_i", pa.int16(), False),
        pa.field("decision_bid", pa.float64(), False), pa.field("decision_ask", pa.float64(), False),
        pa.field("decision_delta", pa.float64(), False), pa.field("decision_underlying_price", pa.float64(), False),
        pa.field("relative_spread", pa.float64(), False), pa.field("selector_distance", pa.float64(), False),
        pa.field("source_path", pa.string(), False), pa.field("source_sha256", pa.string(), False),
        pa.field("clock_basis", pa.string(), False), pa.field("receipt_time_status", pa.string(), False),
        pa.field("interval_used", pa.string()), pa.field("gamma_column_present", pa.bool_(), False),
    ])


def observation_schema() -> pa.Schema:
    fields = [pa.field(name, pa.string(), False) for name in
              ("observation_id", "source_path", "source_sha256", "ticker", "trade_date",
               "expiration", "right", "strike_decimal")]
    fields += [pa.field("minute_i", pa.int16(), False), pa.field("clock_local", pa.string(), False),
               pa.field("clock_basis", pa.string(), False), pa.field("receipt_time_status", pa.string(), False),
               pa.field("interval_used", pa.string())]
    fields += [pa.field(name, pa.float64()) for name in
               ("bid", "ask", "delta", "implied_vol", "gamma", "theta", "vega", "rho", "underlying_price")]
    fields += [pa.field("underlying_timestamp_raw", pa.string()), pa.field("underlying_age_ms", pa.float64()),
               pa.field("underlying_age_status", pa.string(), False), pa.field("quote_valid", pa.bool_(), False)]
    return pa.schema(fields)


def coverage_schema() -> pa.Schema:
    gap = pa.struct([pa.field("start_i", pa.int16(), False), pa.field("end_i", pa.int16(), False)])
    return pa.schema([
        *[pa.field(name, pa.string(), False) for name in ("decision_id", "plan_id", "role", "ticker",
                                                          "segment_date", "expiration", "right",
                                                          "strike_decimal", "source_path", "source_status")],
        pa.field("source_sha256", pa.string()), pa.field("close_i", pa.int16(), False),
        pa.field("expected_minute_count", pa.int16(), False),
        pa.field("observed_exact_minute_count", pa.int16(), False),
        pa.field("missing_minute_count", pa.int16(), False), pa.field("missing_ranges", pa.list_(gap), False),
        pa.field("first_observed_i", pa.int16()), pa.field("last_observed_i", pa.int16()),
        pa.field("ignored_subminute_rows", pa.int64(), False),
        pa.field("ignored_out_of_session_rows", pa.int64(), False),
        pa.field("clock_basis", pa.string()), pa.field("gamma_column_present", pa.bool_()),
    ])


def spot_schema() -> pa.Schema:
    return pa.schema([
        pa.field("ticker", pa.string(), False), pa.field("ticker_ordinal", pa.int8(), False),
        pa.field("date", pa.string(), False), pa.field("session_kind", pa.string(), False),
        pa.field("cache_status", pa.string(), False), pa.field("minute_i", pa.int16(), False),
        pa.field("time_ns", pa.int64(), False), pa.field("spot", pa.float64()),
        pa.field("spot_valid", pa.bool_(), False), pa.field("missing_reason", pa.string()),
        pa.field("authority", pa.string(), False), pa.field("feature_metadata_path", pa.string()),
        pa.field("feature_metadata_sha256", pa.string()), pa.field("cache_metadata_path", pa.string()),
        pa.field("cache_metadata_sha256", pa.string()), pa.field("cache_npz_path", pa.string()),
        pa.field("cache_npz_sha256", pa.string()), pa.field("cache_version", pa.string()),
    ])


def require_schema(actual: pa.Schema, expected: pa.Schema, label: str) -> None:
    require(actual.equals(expected, check_metadata=False), f"{label} Arrow schema")

PINS = {
    "stage_a_entry_plan": (STAGE_A / "entry_plan.jsonl", 1018910, "0db0065f2dcdd254122a4c4575ecb9c752318cab3a90666ad8215aef922d91bb"),
    "stage_a_weekly_sources": (STAGE_A / "weekly_sources.jsonl", 2367532, "59081a049d11a0403204ca06e62ef4661bb6de3cd042548e081c10f8eaddd1f7"),
    "stage_a_summary": (STAGE_A / "summary.json", 1398, "612ecf1abf18f973656aeda347f21efe563f5c84b9cc06f96e22383ed19b3b39"),
    "stage_a_manifest": (STAGE_A / "manifest.json", 5094, "a0a9d330992d7f5768550c5b60401a701e1c1b02caec4a0967de50b7c7f13161"),
    "stage_a_audit": (BASE / "weekly_zone_event_source_plan_audit_01/audit.json", 9071, "1b71077525d146cd7e2166076f987afd315fe46e27c15e51c4f7555be06299cd"),
    "stage_a_audit_manifest": (BASE / "weekly_zone_event_source_plan_audit_01/manifest.json", 8945, "49935941c89b67f2aef69272201d68d089d9499d0fca71838867b5457bf85ba7"),
    "stage_a_audit_exit": (BASE / "weekly_zone_event_source_plan_audit_observer_01/exit.json", 1337, "bfdf36bfb7f636f27a391ad0b0ed38be5306e69b0c5be144d0c0599de9d65362"),
    "h1_inventory": (BASE / "h2_dataset_v2_01/inventory.json", 5589855, "099dcf065a62705cbd88f2c1b90b2e4a9b99ff4d994ad703634101920c934b12"),
    "h1_inventory_manifest": (BASE / "h2_dataset_v2_01/inventory_manifest.json", 187, "c417e67f3499522d4ebd4a21bf28d1cba8ce249ef2d38a1352001216714bb899"),
    "h1_manifest": (BASE / "h2_dataset_v2_01/manifest.json", 1541, "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8"),
    "q3_inventory": (BASE / "h2_dataset_v2_extension_2026q3_partial_01/inventory.json", 327384, "f633d0ee192f28650698a4033ee7f6d2dc00dad07aa38239c40e9e2b5092ea5c"),
    "q3_inventory_manifest": (BASE / "h2_dataset_v2_extension_2026q3_partial_01/inventory_manifest.json", 197, "5b39e0796599fa72b5d74d029885a24fd57fada207f12989576737aa46d75b2f"),
    "q3_manifest": (BASE / "h2_dataset_v2_extension_2026q3_partial_01/manifest.json", 6184, "b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b"),
    "bridge_inventory": (BASE / "h2_boundary_bridge_01/inventory.json", 14721, "599ca400fecae12ce4098187a45af3ee0cf8c1b070e060d8c84e422ce92c6161"),
    "bridge_inventory_manifest": (BASE / "h2_boundary_bridge_01/inventory_manifest.json", 330, "0a7a5fab0f932d23fdf9a3140027f99eb85ccd958b79ef55152c53ab5ced70f2"),
    "bridge_manifest": (BASE / "h2_boundary_bridge_01/manifest.json", 4748, "9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86"),
    "unified_calendar": (BASE / "h2_boundary_bridge_01/unified_calendar.json", 232573, "be622bb24aca35448594743dfeb5236e6b2d08a4410109b20302891f8c1fa7d6"),
    "h1_context_inventory": (BASE / "h2_context_1030_01/inventory.json", 1829496, "b347523c8638825c822100cf78b5a03ab4f56fc948bc7aa23674b0b73866df5e"),
    "h1_context_inventory_manifest": (BASE / "h2_context_1030_01/inventory_manifest.json", 197, "a7547c375a4de723b168ce2983b84ba98a35dd70aef24c82ed08c1e3c5358ea8"),
    "h1_context_manifest": (BASE / "h2_context_1030_01/manifest.json", 612610, "77aaf00d60accc071ff1f58ec099cee72bc3a4150f89e4ad41a601821a74a38a"),
    "q3_context_inventory": (BASE / "h2_context_q3_1030_01/inventory.json", 1489911, "25da3398984c633a044eef4f20c5525c6224a1b076a5941d0311fae93eab68cf"),
    "q3_context_inventory_manifest": (BASE / "h2_context_q3_1030_01/inventory_manifest.json", 193, "2b74c18e98366670e77e3d2a4fc19e260cd404e6959fbd7e140f2e88fd5050be"),
    "q3_context_manifest": (BASE / "h2_context_q3_1030_01/manifest.json", 172889, "1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66"),
    "selector_builder_v2": (Path(r"build_weekly_h2_dataset_v2.py"), 33142, "ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945"),
    "normalization_pilot": (Path(r"weekly_multiday_source_pilot.py"), 31380, "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878"),
    "original_value_path_contract": (ORIGINAL_CONTRACT, 36466, ORIGINAL_CONTRACT_SHA256),
    "prior_producer_exit": (PRIOR_PRODUCER_OBSERVER / "exit.json", 358, "48b635e9fbdeef729de7c1be0b24948e21655ceb6cf5a154c02809e8a8a951d3"),
    "prior_producer_failure": (PRIOR_PRODUCER_OBSERVER / "failure_receipt.json", 305, "6ee1cb2ee3a29b74484c5ed54fe5049eb45da6e299c4fcd9ea8553bc809086fc"),
    "prior_producer_journal": (PRIOR_PRODUCER_OBSERVER / "journal.jsonl", 6473, "a12c7f5d5e1171e220cc1bcefd9f3191caf6e414f5c5df1cdeb5b4bc8b36aa08"),
}


class AuditError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AuditError(message)


def absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(absolute(path))))


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def file_pin(path: Path) -> dict[str, Any]:
    return {"path": str(absolute(path)), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def same_pin(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return left.get("bytes") == right.get("bytes") and left.get("sha256") == right.get("sha256")


def exact_output_pin(value: Mapping[str, Any], path: Path, rows: int) -> None:
    actual = file_pin(path)
    require(set(value) == {"path", "bytes", "sha256", "rows"} and
            value["path"] == str(absolute(path)) and value["bytes"] == actual["bytes"] and
            value["sha256"] == actual["sha256"] and value["rows"] == rows, f"exact output pin: {path.name}")


def require_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    require(set(value) == expected, f"{label} exact keys")


def validate_output_map(value: Mapping[str, Any], root: Path,
                        row_counts: Mapping[str, int], label: str) -> None:
    require_keys(value, set(row_counts), label)
    for name, rows in row_counts.items():
        exact_output_pin(value[name], root / name, rows)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def stable_id(parts: Sequence[Any]) -> str:
    return hashlib.sha256(canonical_json(list(parts))).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    data = path.read_bytes()
    require(data.endswith(b"\n"), f"JSONL lacks LF terminator: {path}")
    rows = []
    for number, raw in enumerate(data.splitlines(), 1):
        require(bool(raw), f"blank JSONL row {number}: {path}")
        value = json.loads(raw)
        require(isinstance(value, dict), f"non-object JSONL row {number}: {path}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    with path.open("wb") as stream:
        stream.write(canonical_json(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def linked(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & REPARSE)


def forbidden_path_text(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    basename = path.name.lower()
    return (basename in {"candidates.jsonl", "context.jsonl", "coverage.json", "index.parquet", "features.npz"}
            or basename.startswith("state60") or basename.startswith("outcome")
            or bool(parts & {"outcomes", "ledgers", "scores"}))


def physical_id(info: os.stat_result) -> list[int]:
    return [int(info.st_dev), int(info.st_ino)]


def guard_file(path: Path, roots: Sequence[Path], seen: set[tuple[int, int]] | None = None) -> Path:
    lexical = Path(path)
    require(lexical.is_absolute() and ".." not in lexical.parts, f"unsafe lexical path: {path}")
    require(not forbidden_path_text(lexical), f"forbidden path before open: {path}")
    candidate = absolute(lexical)
    permitted = [absolute(root) for root in roots]
    root = next((item for item in permitted if candidate == item or candidate.is_relative_to(item)), None)
    require(root is not None, f"path outside admitted roots: {path}")
    anchor = Path(candidate.anchor)
    current = candidate
    while True:
        info = current.lstat()
        require(not linked(info), f"link/reparse forbidden: {current}")
        if current == anchor:
            break
        current = current.parent
    info = candidate.stat(follow_symlinks=False)
    require(stat.S_ISREG(info.st_mode) and int(getattr(info, "st_nlink", 1)) == 1, f"not unique regular file: {path}")
    identity = (int(info.st_dev), int(info.st_ino))
    if seen is not None:
        require(identity not in seen, f"physical alias: {path}")
        seen.add(identity)
    return candidate


def guard_missing(path: Path, root: Path) -> Path:
    lexical = Path(path)
    require(lexical.is_absolute() and ".." not in lexical.parts, f"unsafe missing lexical path: {path}")
    candidate, root = absolute(lexical), absolute(root)
    require(candidate.is_relative_to(root) and not candidate.exists(), "missing path root/presence")
    current = candidate.parent
    anchor = Path(candidate.anchor)
    while True:
        info = current.lstat()
        require(not linked(info), f"missing ancestor link/reparse: {current}")
        if current == anchor:
            break
        current = current.parent
    return candidate


def stat_record(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "bytes": None, "mtime_ns": None, "physical_id": None}
    info = path.stat(follow_symlinks=False)
    return {"exists": True, "bytes": info.st_size, "mtime_ns": info.st_mtime_ns,
            "physical_id": physical_id(info)}


def validate_environment() -> None:
    if os.name == "nt":
        process_mask = ctypes.c_size_t()
        system_mask = ctypes.c_size_t()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                                                    ctypes.POINTER(ctypes.c_size_t)]
        ok = kernel32.GetProcessAffinityMask(kernel32.GetCurrentProcess(),
                                             ctypes.byref(process_mask), ctypes.byref(system_mask))
        require(bool(ok) and process_mask.value == 1, "logical CPU affinity must be CPU0 only")
    else:
        require(os.sched_getaffinity(0) == {0}, "logical CPU affinity must be {0}")
    require(all(os.environ.get(name) == "1" for name in TEN_VARS), "ten thread variables must equal 1")
    require(os.environ.get("CUDA_VISIBLE_DEVICES") == "-1", "CUDA_VISIBLE_DEVICES must equal -1")
    require(np.__version__ == "2.3.5" and pa.__version__ == "23.0.1", "runtime version pin")


def resource_gate() -> dict[str, int]:
    require(callable(_OFFICIAL_OBSERVATION), "official resource observation is not bound")
    gate = _OFFICIAL_OBSERVATION()
    require(set(gate) == {"available_ram_bytes", "free_commit_bytes"}, "resource gate schema")
    require(all(type(gate[key]) is int and gate[key] >= 2_000_000_000 for key in gate), "RAM/commit gate")
    disk = shutil.disk_usage("D:/").free
    require(disk >= 2_000_000_000, "D: free disk gate")
    return {**gate, "disk_free_bytes": disk}


def bind_resource_helper() -> None:
    global _OFFICIAL_OBSERVATION
    require(sha256_file(RESOURCE_HELPER) == HELPER_SHA256, "resource helper pin before import")
    spec = importlib.util.spec_from_file_location("weekly_value_paths_audit_resource_helper", RESOURCE_HELPER)
    require(spec is not None and spec.loader is not None, "resource helper import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(callable(getattr(module, "observation", None)) and callable(getattr(module, "gate", None)),
            "resource helper API")
    _OFFICIAL_OBSERVATION = module.observation


class Journal:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, stage: str, event: str, identity: str, **details: Any) -> None:
        row = {"utc": datetime.now(timezone.utc).isoformat(), "stage": stage,
               "event": event, "identity": identity, **details}
        with self.path.open("ab") as stream:
            stream.write(canonical_json(row) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())

    @contextmanager
    def unit(self, stage: str, identity: str, paths: Sequence[Path]) -> Iterator[dict[str, Any]]:
        gate = resource_gate()
        self.append(stage, "STARTED", identity, gate=gate)
        details: dict[str, Any] = {}
        try:
            before = {str(path): file_pin(path) for path in paths if path.exists()}
            yield details
        except BaseException as error:
            self.append(stage, "ERROR", identity, error=type(error).__name__, details=details)
            raise
        after = {str(path): file_pin(path) for path in paths if path.exists()}
        self.append(stage, "COMPLETED", identity, pins_before=before, pins_after=after, details=details)


def validate_stage_a_receipt(audit_doc: Mapping[str, Any], exit_doc: Mapping[str, Any]) -> None:
    expected_strings = {
        "schema": "weekly_zone_event_source_plan_audit_v1",
        "status": "PASS_INDEPENDENT_WEEKLY_ZONE_EVENT_SOURCE_PLAN_METADATA_AUDIT",
        "scope": "METADATA_ONLY_NOT_VALUE_ADMISSION",
        "producer_status": "SOURCE_PLAN_NOT_VALUE_ADMISSION",
    }
    require(all(type(audit_doc.get(name)) is str and audit_doc.get(name) == value
                for name, value in expected_strings.items()), "Stage A audit exact identity")
    checks = audit_doc.get("checks")
    expected_checks = {
        "all_entries_exact": True,
        "all_sources_and_references_exact": True,
        "authorities": 10,
        "bridge_overlay_rows": 6,
        "current_metadata_exact": True,
        "entry_plans": 2790,
        "source_references": 4860,
        "summary_exact": True,
        "unique_sources": 2784,
    }
    require(isinstance(checks, dict) and set(checks) == set(expected_checks), "Stage A audit exact check keys")
    for name, expected in expected_checks.items():
        require(type(checks[name]) is type(expected) and checks[name] == expected,
                f"Stage A audit exact typed check: {name}")
    required_exit = {"exit_code", "audit_child_exit_code", "changed_pins", "metadata_error", "retry", "source"}
    require(isinstance(exit_doc, dict) and required_exit <= set(exit_doc), "Stage A audit exit required keys")
    require(type(exit_doc["exit_code"]) is int and exit_doc["exit_code"] == 0 and
            type(exit_doc["audit_child_exit_code"]) is int and exit_doc["audit_child_exit_code"] == 0 and
            type(exit_doc["changed_pins"]) is list and exit_doc["changed_pins"] == [] and
            exit_doc["metadata_error"] is None and exit_doc["retry"] is False and
            type(exit_doc["source"]) is str and exit_doc["source"] == "subprocess.Popen.wait_retained_handle",
            "Stage A audit exact exit receipt")


def admit_pins() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    amendment_path = guard_file(ADMISSION_AMENDMENT, (HERE,))
    amendment_pin = file_pin(amendment_path)
    require(amendment_pin["bytes"] == ADMISSION_AMENDMENT_BYTES and
            amendment_pin["sha256"] == ADMISSION_AMENDMENT_SHA256, "V2R1 admission amendment pin")
    documents: dict[str, Any] = {}
    pins: dict[str, dict[str, Any]] = {}
    for name, (raw_path, size, digest) in PINS.items():
        path = raw_path if raw_path.is_absolute() else HERE / raw_path
        guard_file(path, (HERE, BASE))
        actual = file_pin(path)
        require(actual["bytes"] == size and actual["sha256"] == digest, f"authority pin drift: {name}")
        pins[name] = actual
        if path.suffix == ".json":
            documents[name] = load_json(path)
        elif name == "prior_producer_journal":
            documents[name] = load_jsonl(path)
    require(len(pins) == 29 and set(pins) == set(PINS), "V2 authority population")
    require(file_pin(CONTRACT)["sha256"] == CONTRACT_SHA256, "contract pin")
    require(file_pin(RESOURCE_HELPER)["sha256"] == HELPER_SHA256, "resource helper pin")
    exit_doc = documents["stage_a_audit_exit"]
    audit_doc = documents["stage_a_audit"]
    validate_stage_a_receipt(audit_doc, exit_doc)
    validate_prior_failure_v2(documents)
    return documents, pins


def validate_prior_failure_v2(documents: Mapping[str, Any]) -> None:
    exit_doc = documents.get("prior_producer_exit")
    failure = documents.get("prior_producer_failure")
    rows = documents.get("prior_producer_journal")
    require(isinstance(exit_doc, dict) and exit_doc.get("exit_code") == 1 and
            exit_doc.get("value_child_exit_code") == 1 and exit_doc.get("retry") is False and
            exit_doc.get("changed_pins") == [], "prior producer exit evidence")
    require(isinstance(failure, dict) and failure.get("exit_code") == 1 and
            failure.get("value_child_exit_code") == 1 and
            failure.get("partial_output_not_authorized_for_adoption") is True and
            failure.get("retry") is False, "prior producer failure evidence")
    require(isinstance(rows, list) and len(rows) == 4, "prior producer journal cardinality")
    require(all(isinstance(row, dict) for row in rows), "prior producer journal row types")
    sequence = [(row.get("kind"), row.get("identity"), row.get("event")) for row in rows]
    require(sequence == [
        ("ADMIT_AUTHORITIES", "IMPLEMENTATION_PINS", "STARTED"),
        ("ADMIT_AUTHORITIES", "IMPLEMENTATION_PINS", "COMPLETED"),
        ("ADMIT_AUTHORITIES", "PINNED_AUTHORITIES", "STARTED"),
        ("ADMIT_AUTHORITIES", "PINNED_AUTHORITIES", "COMPLETED"),
    ], "prior producer journal sequence")
    original_names = tuple(name for name in PINS if name not in {
        "original_value_path_contract", "prior_producer_exit", "prior_producer_failure",
        "prior_producer_journal",
    })
    authority_paths = [str(absolute(path if path.is_absolute() else HERE / path))
                       for name in original_names for path, _size, _digest in (PINS[name],)]
    implementation_paths = [str(absolute(PRIOR_PRODUCER_OBSERVER / "implementation_pins.json"))]
    require(rows[0].get("paths") == rows[1].get("paths") == implementation_paths and
            rows[2].get("paths") == rows[3].get("paths") == authority_paths,
            "prior producer journal admitted paths")
    for index, row in enumerate(rows):
        expected_keys = {"at_utc", "event", "gate", "identity", "kind", "paths"}
        if row.get("event") == "COMPLETED":
            expected_keys.add("details")
        require(set(row) == expected_keys and isinstance(row.get("at_utc"), str),
                "prior producer journal row schema")
        gate = row.get("gate")
        require(isinstance(gate, dict) and set(gate) == {
            "available_ram_bytes", "disk_free_bytes", "free_commit_bytes",
        } and all(type(gate[name]) is int and gate[name] >= 2_000_000_000 for name in gate),
                "prior producer journal gate")
        if index == 1:
            require(row["details"] == {"pins": 10}, "prior producer implementation admission")
        elif index == 3:
            require(row["details"] == {"authorities": 25}, "prior producer authority admission")
    require(not any(row.get("event") == "ERROR" for row in rows), "prior producer journal ERROR")


def normalize_calendar_v2(
    document: Mapping[str, Any], raw_pin: Mapping[str, Any], *, expected_sessions: int = 930,
    expected_short: int = 24, expected_full: int = 2766,
    expected_bytes: int = CANONICAL_CALENDAR_BYTES,
    expected_sha256: str = CANONICAL_CALENDAR_SHA256,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    require(set(document) == {"schema", "rows"}, "calendar top-level keys")
    require(document.get("schema") == "weekly_h2_boundary_unified_calendar_v1", "calendar schema")
    raw_rows = document.get("rows")
    expected_rows = expected_sessions * 3
    require(isinstance(raw_rows, list) and len(raw_rows) == expected_rows, "calendar row count")
    triples: list[tuple[str, str, int]] = []
    by_ticker: dict[str, list[str]] = {ticker: [] for ticker in TICKERS}
    for row in raw_rows:
        require(isinstance(row, dict) and set(row) == {"close_i", "date", "ticker"}, "calendar row keys")
        ticker, day, close_i = row["ticker"], row["date"], row["close_i"]
        require(ticker in TICKERS and isinstance(day, str) and re.fullmatch(r"\d{8}", day) is not None and
                parse_day(day, "calendar") == day and type(close_i) is int and close_i in (210, 390),
                "calendar row domain")
        triples.append((ticker, day, close_i))
        by_ticker[ticker].append(day)
    require(len({(ticker, day) for ticker, day, _close in triples}) == expected_rows, "calendar duplicate identity")
    require(all(len(days) == expected_sessions and days == sorted(days) for days in by_ticker.values()),
            "calendar ticker date order/count")
    require(set(by_ticker["SPY"]) == set(by_ticker["QQQ"]) == set(by_ticker["SPXW"]),
            "calendar ticker date sets")
    require(sum(close == 210 for _ticker, _day, close in triples) == expected_short and
            sum(close == 390 for _ticker, _day, close in triples) == expected_full, "calendar session counts")
    require(triples == sorted(triples, key=lambda value: (value[0], value[1])), "calendar upstream ticker-major order")
    canonical = [{"ticker": ticker, "date": day, "close_i": close}
                 for ticker, day, close in sorted(triples, key=lambda value: (value[1], TICKER_ORDINAL[value[0]]))]
    require(canonical is not raw_rows and all(row is not raw for row, raw in zip(canonical, raw_rows, strict=True)),
            "calendar canonical copy")
    require({(row["ticker"], row["date"], row["close_i"]) for row in canonical} == set(triples),
            "calendar identity/close preservation")
    payload = b"".join(canonical_json({"close_i": row["close_i"], "date": row["date"],
                                       "ticker": row["ticker"]}) + b"\n" for row in canonical)
    digest = hashlib.sha256(payload).hexdigest()
    require(len(payload) == expected_bytes and digest == expected_sha256, "calendar canonical digest")
    if expected_sessions == 930:
        require(canonical[0] == {"ticker": "SPY", "date": "20230103", "close_i": 390} and
                canonical[-1] == {"ticker": "SPXW", "date": "20260917", "close_i": 390},
                "calendar canonical endpoints")
    envelope = {"raw_pin": dict(raw_pin), "raw_order": RAW_CALENDAR_ORDER,
                "canonical_order": CANONICAL_CALENDAR_ORDER, "rows": expected_rows,
                "canonical_jsonl_bytes": expected_bytes, "canonical_jsonl_sha256": expected_sha256,
                "identity_set_preserved": True, "close_i_preserved": True}
    details = {"raw_pin": dict(raw_pin), "raw_schema": document["schema"], "raw_rows": expected_rows,
               "raw_order": RAW_CALENDAR_ORDER, "canonical_order": CANONICAL_CALENDAR_ORDER,
               "canonical_rows": expected_rows, "canonical_jsonl_bytes": expected_bytes,
               "canonical_jsonl_sha256": expected_sha256,
               "identity_set_preserved": True, "close_i_preserved": True}
    return canonical, envelope, details


def parse_day(value: Any, label: str) -> str:
    if isinstance(value, datetime) or isinstance(value, bool):
        raise AuditError(f"{label}: datetime/bool forbidden")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    require(isinstance(value, str) and value == value.strip(), f"{label}: date type/whitespace")
    require(bool(re.fullmatch(r"\d{8}|\d{4}-\d{2}-\d{2}", value)), f"{label}: date shape")
    fmt = "%Y%m%d" if len(value) == 8 else "%Y-%m-%d"
    try:
        parsed = datetime.strptime(value, fmt).date()
    except ValueError as error:
        raise AuditError(f"{label}: invalid date") from error
    return parsed.strftime("%Y%m%d")


def canonical_strike(value: Any) -> tuple[str, float]:
    require(not isinstance(value, bool), "strike bool")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise AuditError("invalid strike") from error
    require(decimal.is_finite(), "non-finite strike")
    return format(decimal.normalize(), "f"), float(value)


def normalize_right(value: Any) -> str:
    require(isinstance(value, str), "right type")
    result = value.strip().upper()
    require(result in {"C", "CALL", "P", "PUT"}, "right value")
    return "CALL" if result in {"C", "CALL"} else "PUT"


def normalize_symbol(value: Any, ticker: str) -> str:
    require(isinstance(value, str) and value.strip().upper() == ticker, "symbol mismatch")
    return ticker


def localize_naive(value: datetime) -> datetime:
    first = value.replace(tzinfo=NY, fold=0)
    second = value.replace(tzinfo=NY, fold=1)
    valid = []
    for candidate in (first, second):
        roundtrip = candidate.astimezone(timezone.utc).astimezone(NY).replace(tzinfo=None)
        if roundtrip == value:
            valid.append(candidate)
    require(bool(valid), "nonexistent NY time")
    require(len(valid) == 1 or valid[0].utcoffset() == valid[-1].utcoffset(), "ambiguous/nonexistent NY time")
    return valid[0]


def parse_clock(value: Any, trade_date: str | None) -> datetime:
    require(value is not None and not isinstance(value, (bool, int, float, date)) or isinstance(value, datetime),
            "clock null/numeric/date forbidden")
    if isinstance(value, datetime):
        parsed = value
    else:
        require(isinstance(value, str) and "T" in value and value == value.strip(), "clock ISO complete")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise AuditError("malformed clock") from error
    local = localize_naive(parsed) if parsed.tzinfo is None else parsed.astimezone(NY)
    if trade_date is not None:
        require(local.strftime("%Y%m%d") == trade_date, "clock local date mismatch")
    return local


def minute_index(value: Any, trade_date: str) -> tuple[int, bool, datetime]:
    local = parse_clock(value, trade_date)
    index = (local.hour * 60 + local.minute) - (9 * 60 + 30)
    exact = local.second == 0 and local.microsecond == 0
    return index, exact, local


def scalar_float(value: Any, nullable: bool = True) -> float | None:
    if value is None:
        require(nullable, "required float null")
        return None
    require(not isinstance(value, bool) and isinstance(value, (int, float)), "float scalar")
    return float(value)


def quote_valid(bid: Any, ask: Any) -> bool:
    if isinstance(bid, bool) or isinstance(ask, bool) or not isinstance(bid, (int, float)) or not isinstance(ask, (int, float)):
        return False
    return math.isfinite(float(bid)) and math.isfinite(float(ask)) and 0 <= float(bid) <= float(ask) and float(ask) > 0


def candidate_key(row: Mapping[str, Any], right: str) -> tuple[float, float, float] | None:
    bid, ask, spot, delta = (row.get(name) for name in ("bid", "ask", "underlying_price", "delta"))
    if not quote_valid(bid, ask) or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (spot, delta)):
        return None
    spot_f, delta_f, ask_f, bid_f = float(spot), float(delta), float(ask), float(bid)
    if not math.isfinite(spot_f) or spot_f <= 0 or not math.isfinite(delta_f) or ask_f > 49.95 or abs(delta_f) > 1:
        return None
    if (right == "CALL" and delta_f <= 0) or (right == "PUT" and delta_f >= 0):
        return None
    _strike, strike_f = canonical_strike(row["strike"])
    return abs(abs(delta_f) - 0.50), (ask_f - bid_f) / ask_f, strike_f


def parquet_schema_signature(schema: pa.Schema) -> list[dict[str, str]]:
    return [{"name": field.name, "type": str(field.type)} for field in schema]


def clock_column(schema: pa.Schema) -> tuple[str, str]:
    names = set(schema.names)
    if "timestamp" in names:
        return "timestamp", "NATIVE_STORED_TIMESTAMP"
    require("underlying_timestamp" in names, "no clock column")
    return "underlying_timestamp", "UNDERLYING_TIMESTAMP_PROXY"


def validate_option_schema(schema: pa.Schema) -> tuple[str, str, bool, list[str]]:
    names = set(schema.names)
    require(set(OPTION_COLUMNS).issubset(names), "required option columns")
    clock, basis = clock_column(schema)
    gamma = "gamma" in names
    for name in (*FLOAT_COLUMNS, *(("gamma",) if gamma else ())):
        require(pa.types.is_float64(schema.field(name).type), f"{name} must be float64")
    projection = list(OPTION_COLUMNS) + [clock]
    if gamma:
        projection.append("gamma")
    if "interval_used" in names:
        data_type = schema.field("interval_used").type
        require(pa.types.is_string(data_type) or pa.types.is_large_string(data_type) or
                pa.types.is_integer(data_type) or pa.types.is_floating(data_type) or
                pa.types.is_decimal(data_type), "interval_used type")
        projection.append("interval_used")
    return clock, basis, gamma, list(dict.fromkeys(projection))


def interval_text(value: Any) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def raw_timestamp_text(value: Any, data_type: pa.DataType) -> str | None:
    scalar = value if isinstance(value, pa.Scalar) else None
    if isinstance(value, pa.Scalar):
        if not value.is_valid:
            return None
        value = value.as_py()
    if value is None:
        return None
    if isinstance(value, str):
        return value
    require(isinstance(value, datetime) and pa.types.is_timestamp(data_type), "underlying timestamp representation")
    unit = data_type.unit
    digits = {"s": 0, "ms": 3, "us": 6, "ns": 9}[unit]
    base = value.strftime("%Y-%m-%dT%H:%M:%S")
    if digits:
        # Python carries microseconds; ns Arrow scalars expose remaining precision in .value.
        residual = int(scalar.value) % 1000 if digits == 9 and scalar is not None else 0
        fraction = f"{value.microsecond:06d}" + (f"{residual:03d}" if digits == 9 else "")
        base += "." + fraction[:digits]
    if data_type.tz is not None:
        base += value.strftime("%z")[:3] + ":" + value.strftime("%z")[3:]
    return base


def datetime_epoch_ns(value: datetime, extra_ns: int = 0) -> int:
    aware = localize_naive(value) if value.tzinfo is None else value.astimezone(timezone.utc)
    utc_value = aware.astimezone(timezone.utc)
    delta = utc_value - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return ((delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds) * 1000 + extra_ns


def clock_epoch_ns(scalar: pa.Scalar, data_type: pa.DataType, trade_date: str | None) -> int:
    require(scalar.is_valid, "timestamp scalar null")
    value = scalar.as_py()
    if pa.types.is_timestamp(data_type):
        require(isinstance(value, datetime), "Arrow timestamp scalar")
        local = localize_naive(value) if value.tzinfo is None else value.astimezone(NY)
        if trade_date is not None:
            require(local.strftime("%Y%m%d") == trade_date, "clock local date mismatch")
        factor = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1000, "ns": 1}[data_type.unit]
        if data_type.tz is not None:
            return int(scalar.value) * factor
        remainder = int(scalar.value) % (1000 if data_type.unit == "ns" else 1)
        return datetime_epoch_ns(value, remainder)
    require(isinstance(value, str), "clock scalar type")
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})?", value)
    require(match is not None, "clock ISO nanosecond shape")
    base, fraction, offset = match.groups()
    fraction = fraction or ""
    parse_text = base + (("." + fraction[:6]) if fraction else "") + (offset or "")
    local = parse_clock(parse_text, trade_date)
    extra = int((fraction[6:] + "000")[:3]) if len(fraction) > 6 else 0
    return datetime_epoch_ns(local, extra)


def contract_row(row: Mapping[str, Any], ticker: str, trade_date: str, expiration: str) -> tuple[str, str]:
    normalize_symbol(row["symbol"], ticker)
    require(parse_day(row["trade_date"], "row trade_date") == trade_date, "row trade date mismatch")
    require(parse_day(row["expiration"], "row expiration") == expiration, "row expiration mismatch")
    strike, _value = canonical_strike(row["strike"])
    return strike, normalize_right(row["right"])


def scan_option_source(path: Path, ticker: str, trade_date: str, expiration: str,
                       close_i: int, wanted: set[tuple[str, str]] | None,
                       selection_only: bool) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    guard_file(path, (SOURCE_ROOT,))
    parquet = pq.ParquetFile(path)
    clock, basis, gamma, columns = validate_option_schema(parquet.schema_arrow)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    ignored_subminute = ignored_out = 0
    ignored_by_key: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for batch in parquet.iter_batches(batch_size=65536, columns=columns, use_threads=False):
        clock_array = batch.column(batch.schema.get_field_index(clock))
        clock_type = batch.schema.field(clock).type
        selected_indices = []
        selected_clock: dict[int, tuple[int, datetime]] = {}
        for index, scalar in enumerate(clock_array):
            value = scalar.as_py() if scalar.is_valid else None
            minute_i, exact, _local = minute_index(value, trade_date)
            if exact and pa.types.is_timestamp(clock_type):
                units_per_second = {"s": 1, "ms": 1000, "us": 1_000_000, "ns": 1_000_000_000}[clock_type.unit]
                exact = int(scalar.value) % units_per_second == 0
            elif exact and isinstance(value, str):
                fraction = re.search(r"\.(\d+)(?:Z|[+-]\d{2}:\d{2})?$", value)
                exact = fraction is None or set(fraction.group(1)) <= {"0"}
            if not exact:
                ignored_subminute += 1
                identity = {name: batch.column(batch.schema.get_field_index(name))[index].as_py()
                            for name in ("symbol", "expiration", "trade_date", "strike", "right")}
                strike, right = contract_row(identity, ticker, trade_date, expiration)
                if wanted is None or (strike, right) in wanted:
                    ignored_by_key[(strike, right)]["ignored_subminute_rows"] += 1
                continue
            if minute_i < 0 or minute_i > close_i:
                ignored_out += 1
                identity = {name: batch.column(batch.schema.get_field_index(name))[index].as_py()
                            for name in ("symbol", "expiration", "trade_date", "strike", "right")}
                strike, right = contract_row(identity, ticker, trade_date, expiration)
                if wanted is None or (strike, right) in wanted:
                    ignored_by_key[(strike, right)]["ignored_out_of_session_rows"] += 1
                continue
            if selection_only and minute_i != 60:
                continue
            selected_indices.append(index)
            selected_clock[index] = (minute_i, _local)
        if not selected_indices:
            continue
        material = batch.take(pa.array(selected_indices, type=pa.int64())).to_pylist()
        for original_index, row in zip(selected_indices, material, strict=True):
            minute_i, _local = selected_clock[original_index]
            row["_clock_scalar"] = batch.column(batch.schema.get_field_index(clock))[original_index]
            row["_clock_type"] = batch.schema.field(clock).type
            row["_underlying_scalar"] = batch.column(batch.schema.get_field_index("underlying_timestamp"))[original_index]
            row["_underlying_type"] = batch.schema.field("underlying_timestamp").type
            strike, right = contract_row(row, ticker, trade_date, expiration)
            unique = (strike, right, minute_i)
            require(unique not in seen, f"duplicate source/key/minute: {path}/{unique}")
            seen.add(unique)
            if wanted is not None and (strike, right) not in wanted:
                continue
            rows.append({**row, "strike_decimal": strike, "right_normalized": right,
                         "minute_i": minute_i, "clock_basis": basis,
                         "gamma_column_present": gamma})
    footer = {"rows": parquet.metadata.num_rows, "row_groups": parquet.metadata.num_row_groups,
              "projected_schema": parquet_schema_signature(parquet.schema_arrow),
              "clock_column": clock, "clock_basis": basis, "gamma_column_present": gamma}
    counts = {"ignored_subminute_rows": ignored_subminute, "ignored_out_of_session_rows": ignored_out,
              "by_key": ignored_by_key}
    return rows, footer, counts


def select_contracts(plans: Sequence[Mapping[str, Any]], expected: int = 3240,
                     journal: Journal | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    decisions: list[dict[str, Any]] = []
    no_valid = Counter()
    reads = 0
    for plan in plans:
        if plan["status"] != "PLANNED":
            continue
        path = Path(plan["entry_path"])
        if journal is None:
            rows, footer, _counts = scan_option_source(path, plan["ticker"], plan["date"], plan["expiration"],
                                                       plan["close_i"], None, True)
        else:
            with journal.unit("SELECT_1030_SOURCE", plan["plan_id"], [path]) as details:
                rows, footer, _counts = scan_option_source(path, plan["ticker"], plan["date"], plan["expiration"],
                                                           plan["close_i"], None, True)
                details["source_reads"] = 1
        reads += 1
        for right in ("CALL", "PUT"):
            candidates = [(candidate_key(row, right), row) for row in rows if row["right_normalized"] == right]
            candidates = [(key, row) for key, row in candidates if key is not None]
            if not candidates:
                no_valid[right] += 1
                continue
            _key, row = min(candidates, key=lambda item: item[0])
            strike = row["strike_decimal"]
            bid, ask, delta, spot = map(float, (row["bid"], row["ask"], row["delta"], row["underlying_price"]))
            decisions.append({
                "decision_id": stable_id([plan["plan_id"], plan["ticker"], plan["expiration"], strike, right]),
                "plan_id": plan["plan_id"], "source_authority": plan["source_authority"],
                "ticker": plan["ticker"], "entry_date": plan["date"], "expiration": plan["expiration"],
                "right": right, "strike_decimal": strike, "decision_clock": "10:30",
                "decision_minute_i": 60, "decision_bid": bid, "decision_ask": ask,
                "decision_delta": delta, "decision_underlying_price": spot,
                "relative_spread": (ask - bid) / ask, "selector_distance": abs(abs(delta) - 0.5),
                "source_path": str(absolute(path)), "source_sha256": sha256_file(path),
                "clock_basis": footer["clock_basis"], "receipt_time_status": "UNKNOWN",
                "interval_used": interval_text(row.get("interval_used")),
                "gamma_column_present": footer["gamma_column_present"],
            })
    decisions.sort(key=lambda row: (row["entry_date"], TICKER_ORDINAL[row["ticker"]], RIGHT_ORDINAL[row["right"]]))
    require(len(decisions) == expected and not no_valid, f"selector cardinality/no-valid: {len(decisions)}/{dict(no_valid)}")
    return decisions, {"selector_source_reads": reads, "no_valid_call": no_valid["CALL"],
                       "no_valid_put": no_valid["PUT"]}


def missing_ranges(observed: set[int], close_i: int) -> list[dict[str, int]]:
    result = []
    start = None
    for value in range(close_i + 1):
        if value not in observed and start is None:
            start = value
        if value in observed and start is not None:
            result.append({"start_i": start, "end_i": value - 1})
            start = None
    if start is not None:
        result.append({"start_i": start, "end_i": close_i})
    return result


def table_rows(path: Path) -> tuple[pa.Schema, list[dict[str, Any]]]:
    table = pq.read_table(path, use_threads=False)
    return table.schema, table.to_pylist()


def compare_value(left: Any, right: Any, label: str) -> None:
    if isinstance(left, float) and isinstance(right, float):
        require(struct.pack(">d", left) == struct.pack(">d", right),
                f"float bits mismatch {label}: {left!r} != {right!r}")
        return
    require(left == right, f"value mismatch {label}: {left!r} != {right!r}")


def compare_rows(actual: Sequence[Mapping[str, Any]], expected: Sequence[Mapping[str, Any]], label: str) -> None:
    require(len(actual) == len(expected), f"{label} row count")
    for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
        require(list(left) == list(right), f"{label} schema/order row {index}")
        for key in left:
            compare_value(left[key], right[key], f"{label}/{index}/{key}")


def option_paths(plans: Sequence[Mapping[str, Any]], decisions: Sequence[Mapping[str, Any]],
                 sources: Mapping[str, Mapping[str, Any]], journal: Journal | None = None,
                 observation_consumer: Any = None,
                 ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    decision_by_plan = defaultdict(list)
    for decision in decisions:
        decision_by_plan[decision["plan_id"]].append(decision)
    requests: dict[str, dict[str, Any]] = {}
    coverage_requests = []
    for plan in plans:
        for decision in decision_by_plan.get(plan["plan_id"], []):
            for role, field in (("D", "D"), ("D1", "D1"), ("H2", "D2")):
                segment_date = plan["session_dates"][field]
                path = str(absolute(SOURCE_ROOT / plan["ticker"] / "greeks" / segment_date[:4] / segment_date[4:6] /
                                    f"{plan['ticker']}_{plan['expiration']}_{segment_date}_greeks.parquet"))
                coverage_requests.append((decision, role, segment_date, path))
                item = requests.setdefault(path, {"ticker": plan["ticker"], "trade_date": segment_date,
                                                   "expiration": plan["expiration"], "close_i": sources[path]["close_i"],
                                                   "wanted": set()})
                item["wanted"].add((decision["strike_decimal"], decision["right"]))
    observations = []
    scanned: dict[str, tuple[dict[tuple[str, str], list[dict[str, Any]]], dict[str, Any], dict[str, Any]]] = {}
    total_counts = Counter()
    ordered_paths = sorted(requests, key=lambda value: (requests[value]["trade_date"],
                           TICKER_ORDINAL[requests[value]["ticker"]], requests[value]["expiration"],
                           os.path.normcase(value)))
    observation_count = 0
    for path_text in ordered_paths:
        info = requests[path_text]
        source = sources[path_text]
        if not source["exists"]:
            continue
        if journal is None:
            rows, footer, counts = scan_option_source(Path(path_text), info["ticker"], info["trade_date"],
                                                      info["expiration"], info["close_i"], info["wanted"], False)
        else:
            with journal.unit("STREAM_OPTION_SOURCE", path_text, [Path(path_text)]) as details:
                rows, footer, counts = scan_option_source(Path(path_text), info["ticker"], info["trade_date"],
                                                          info["expiration"], info["close_i"], info["wanted"], False)
                details["source_reads"] = 1
        by_key: dict[tuple[str, str], set[int]] = defaultdict(set)
        source_observations = []
        for row in rows:
            by_key[(row["strike_decimal"], row["right_normalized"])].add(row["minute_i"])
            raw_underlying = raw_timestamp_text(row["_underlying_scalar"], row["_underlying_type"])
            age = None
            age_status = "PROXY_UNKNOWN"
            if footer["clock_basis"] == "NATIVE_STORED_TIMESTAMP":
                try:
                    main_ns = clock_epoch_ns(row["_clock_scalar"], row["_clock_type"], info["trade_date"])
                    underlying_ns = clock_epoch_ns(row["_underlying_scalar"], row["_underlying_type"], None)
                    age = (main_ns - underlying_ns) / 1_000_000.0
                    age_status = "NATIVE_DERIVED"
                except AuditError:
                    age_status = "MISSING_OR_MALFORMED"
            minute_i = row["minute_i"]
            source_observations.append({
                "observation_id": stable_id([str(absolute(Path(path_text))), info["ticker"], info["expiration"],
                                             row["strike_decimal"], row["right_normalized"], minute_i]),
                "source_path": str(absolute(Path(path_text))), "source_sha256": source["sha256"],
                "ticker": info["ticker"], "trade_date": info["trade_date"], "expiration": info["expiration"],
                "right": row["right_normalized"], "strike_decimal": row["strike_decimal"],
                "minute_i": minute_i, "clock_local": (datetime(2000, 1, 1, 9, 30) + timedelta(minutes=minute_i)).strftime("%H:%M"),
                "clock_basis": footer["clock_basis"], "receipt_time_status": "UNKNOWN",
                "interval_used": interval_text(row.get("interval_used")),
                "bid": scalar_float(row.get("bid")), "ask": scalar_float(row.get("ask")),
                "delta": scalar_float(row.get("delta")), "implied_vol": scalar_float(row.get("implied_vol")),
                "gamma": scalar_float(row.get("gamma")), "theta": scalar_float(row.get("theta")),
                "vega": scalar_float(row.get("vega")), "rho": scalar_float(row.get("rho")),
                "underlying_price": scalar_float(row.get("underlying_price")),
                "underlying_timestamp_raw": raw_underlying, "underlying_age_ms": age,
                "underlying_age_status": age_status, "quote_valid": quote_valid(row.get("bid"), row.get("ask")),
            })
        source_observations.sort(key=lambda row: (RIGHT_ORDINAL[row["right"]], Decimal(row["strike_decimal"]),
                                                  row["minute_i"]))
        observation_count += len(source_observations)
        if observation_consumer is None:
            observations.extend(source_observations)
        else:
            observation_consumer(path_text, source_observations)
        scanned[path_text] = (by_key, footer, counts)
        total_counts.update({name: counts[name] for name in ("ignored_subminute_rows", "ignored_out_of_session_rows")})
    coverage = []
    for decision, role, segment_date, path_text in coverage_requests:
        source = sources[path_text]
        close_i = source["close_i"]
        if source["exists"]:
            by_key, footer, counts = scanned[path_text]
            observed = by_key.get((decision["strike_decimal"], decision["right"]), set())
            key_counts = counts["by_key"].get((decision["strike_decimal"], decision["right"]), {})
            basis, gamma = footer["clock_basis"], footer["gamma_column_present"]
        else:
            observed, key_counts, basis, gamma = set(), {}, None, None
        gaps = missing_ranges(observed, close_i)
        coverage.append({
            "decision_id": decision["decision_id"], "plan_id": decision["plan_id"], "role": role,
            "ticker": decision["ticker"], "segment_date": segment_date, "expiration": decision["expiration"],
            "right": decision["right"], "strike_decimal": decision["strike_decimal"], "source_path": path_text,
            "source_status": "PRESENT" if source["exists"] else "MISSING",
            "source_sha256": source.get("sha256"), "close_i": close_i,
            "expected_minute_count": close_i + 1, "observed_exact_minute_count": len(observed),
            "missing_minute_count": close_i + 1 - len(observed), "missing_ranges": gaps,
            "first_observed_i": min(observed) if observed else None, "last_observed_i": max(observed) if observed else None,
            "ignored_subminute_rows": int(key_counts.get("ignored_subminute_rows", 0)),
            "ignored_out_of_session_rows": int(key_counts.get("ignored_out_of_session_rows", 0)),
            "clock_basis": basis, "gamma_column_present": gamma,
        })
    decision_date = {row["decision_id"]: row["entry_date"] for row in decisions}
    coverage.sort(key=lambda row: (decision_date[row["decision_id"]],
                                   TICKER_ORDINAL[row["ticker"]], RIGHT_ORDINAL[row["right"]], ROLE_ORDINAL[row["role"]]))
    require(len(coverage) == len(decisions) * 3, "coverage cardinality")
    return observations, coverage, {"trajectory_source_reads": len(scanned),
                                    "observation_count": observation_count, **total_counts}


def validate_npz(path: Path, ticker: str, day: str, close_i: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    with np.load(path, allow_pickle=False) as archive:
        names = set(archive.files)
        require({"time_ns", "spot", "spot_valid"}.issubset(names), "spot triplet names")
        time_ns = archive["time_ns"]
        spot = archive["spot"]
        valid = archive["spot_valid"]
        require(time_ns.dtype == np.dtype("int64") and spot.dtype == np.dtype("float64") and valid.dtype == np.dtype("bool"), "spot dtypes")
        require(time_ns.shape == spot.shape == valid.shape == (close_i + 1,), "spot shapes")
        start = np.datetime64(f"{day[:4]}-{day[4:6]}-{day[6:]}T09:30", "ns").astype(np.int64)
        expected = start + np.arange(close_i + 1, dtype=np.int64) * 60_000_000_000
        require(np.array_equal(time_ns, expected), "spot time axis")
        require(np.all(np.isfinite(spot[valid])) and np.all(spot[valid] > 0), "valid spot values")
        rows = [{"minute_i": index, "time_ns": int(time_ns[index]), "spot": float(spot[index]),
                 "spot_valid": bool(valid[index])} for index in range(close_i + 1)]
    indices = {row["minute_i"] for row in rows if row["spot_valid"]}
    return rows, {"valid_count": len(indices), "invalid_count": close_i + 1 - len(indices),
                  "first_valid_i": min(indices) if indices else None, "last_valid_i": max(indices) if indices else None}


def validate_cache_metadata(document: Mapping[str, Any], path: Path, npz_path: Path,
                            ticker: str, day: str, close_i: int, npz_pin: Mapping[str, Any]) -> str:
    expected_version = "SESSION_CLOCK_CACHE_V1" if close_i == 210 else "LEVEL_DAILY_CACHE_V1"
    require(document.get("version") == expected_version and document.get("ticker") == ticker and
            document.get("date") == day, "cache metadata identity/version")
    require(document.get("npz_bytes") == npz_pin["bytes"] and document.get("sha256") == npz_pin["sha256"],
            "cache metadata NPZ binding")
    schema = document.get("array_schema")
    require(isinstance(schema, dict), "cache array schema")
    expected = {"time_ns": {"shape": [close_i + 1], "dtype": "int64"},
                "spot": {"shape": [close_i + 1], "dtype": "float64"},
                "spot_valid": {"shape": [close_i + 1], "dtype": "bool"}}
    require(all(schema.get(name) == value for name, value in expected.items()), "spot triplet metadata schema")
    require(path.suffix.lower() == ".json" and npz_path == path.with_suffix(".npz"), "cache sidecar relation")
    return expected_version


def expected_cache_admission(documents: Mapping[str, Any], journal: Journal | None = None,
                             calendar_rows: Sequence[Mapping[str, Any]] | None = None,
                             ) -> tuple[list[dict[str, Any]], dict[tuple[str, str], tuple[list[dict[str, Any]], dict[str, int]]]]:
    calendar = list(calendar_rows) if calendar_rows is not None else documents["unified_calendar"].get("rows")
    require(isinstance(calendar, list) and len(calendar) == 2790, "spot calendar")
    calendar = sorted(calendar, key=lambda row: (row["date"], TICKER_ORDINAL[row["ticker"]]))
    h1_rows = {(row["ticker"], row["date"]): row for row in documents["h1_context_inventory"]["identities"]}
    q3_rows = {(row["ticker"], row["date"]): row for row in documents["q3_context_inventory"]["identities"]}
    require(len(h1_rows) == 2625 and len(q3_rows) == 165 and not set(h1_rows).intersection(q3_rows), "spot authority partition")
    q3_files = documents["q3_context_manifest"].get("raw_cache_files")
    require(isinstance(q3_files, dict) and len(q3_files) == 306, "Q3 raw cache pins")
    output = []
    payloads: dict[tuple[str, str], tuple[list[dict[str, Any]], dict[str, int]]] = {}
    seen_physical: set[tuple[int, int]] = set()
    missing_expected = {
        *(('QQQ', day) for day in ('20260401', '20260409', '20260415')),
        *(('SPY', day) for day in ('20260401', '20260409', '20260415')),
        *(('QQQ', day) for day in ('20260701', '20260707', '20260710', '20260716', '20260826', '20260901')),
        *(('SPY', day) for day in ('20260701', '20260707', '20260710', '20260716', '20260826', '20260901')),
    }
    actual_missing = set()
    for item in calendar:
        ticker, day, close_i = item["ticker"], item["date"], item["close_i"]
        key = (ticker, day)
        authority = "H1" if key in h1_rows else "Q3"
        identity = h1_rows.get(key, q3_rows.get(key))
        require(identity is not None and identity["close_i"] == close_i, "spot identity/calendar")
        gate = resource_gate()
        if journal is not None:
            journal.append("CACHE_SPOT_PATH", "STARTED", f"{ticker}:{day}", gate=gate, pins_before={})
        base = {"ticker": ticker, "ticker_ordinal": TICKER_ORDINAL[ticker], "date": day,
                "session_kind": "SHORT" if close_i == 210 else "FULL", "close_i": close_i,
                "authority": authority}
        if identity["status"] != "COMPLETE":
            require(identity["status"] == "MISSING_SOURCE", "spot missing authority status")
            actual_missing.add(key)
            output.append({**base, "cache_status": "MISSING", "missing_reason": "MISSING_SOURCE",
                           "feature_metadata_path": None, "feature_metadata_bytes": None,
                           "feature_metadata_sha256": None, "cache_metadata_path": None,
                           "cache_metadata_bytes": None, "cache_metadata_sha256": None,
                           "npz_path": None, "npz_bytes": None, "npz_sha256": None,
                           "cache_version": None, "binding_source_sha256": None,
                           "binding_source_metadata_sha256": None, "stats": None})
            if journal is not None:
                journal.append("CACHE_SPOT_PATH", "COMPLETED", f"{ticker}:{day}", pins_after={},
                               details={"substeps": ["DECLARED_MISSING"]})
            continue
        feature_pin = None
        feature_doc = None
        if authority == "H1":
            feature_pin = identity.get("features_metadata")
            require(isinstance(feature_pin, dict), "H1 feature metadata pin")
            feature_path = guard_file(Path(feature_pin["path"]), (BASE.parent / "level_oracle_20261018",), seen_physical)
            require(same_pin(feature_pin, file_pin(feature_path)), "H1 feature metadata inventory pin")
            feature_doc = load_json(feature_path)
            require(feature_doc.get("version") == "SESSION_CLOCK_FEATURES_V1" and
                    feature_doc.get("ticker") == ticker and feature_doc.get("date") == day and
                    feature_doc.get("outcomes_read") is False, "H1 feature metadata identity")
            binding = feature_doc.get("binding")
            require(isinstance(binding, dict), "H1 binding")
            npz_path = Path(feature_doc["source_path"])
            full_expected = BASE.parent / "level_oracle_20261018/cache_v1" / ticker / f"{day}.npz"
            short_expected = BASE.parent / "level_oracle_20261018/session_clock_dataset_v1/short" / ticker / day / "cache.npz"
            require(path_key(npz_path) == path_key(short_expected if close_i == 210 else full_expected), "H1 nominal raw cache path")
            metadata_path = npz_path.with_suffix(".json")
            # The features NPZ pin is validated semantically only. It is deliberately
            # neither stat'ed nor opened by this auditor.
            features_npz = identity.get("features")
            require(isinstance(features_npz, dict) and feature_doc.get("sha256") == features_npz.get("sha256"),
                    "H1 features NPZ metadata binding")
            metadata_pin = file_pin(guard_file(metadata_path, (BASE.parent / "level_oracle_20261018",), seen_physical))
            npz_pin = file_pin(guard_file(npz_path, (BASE.parent / "level_oracle_20261018",), seen_physical))
            require(metadata_pin["sha256"] == binding.get("source_metadata_sha256") and
                    npz_pin["sha256"] == binding.get("source_sha256"), "H1 raw cache binding")
            binding_sha, binding_metadata_sha = binding["source_sha256"], binding["source_metadata_sha256"]
        else:
            feature_path = None
            relative = f"raw_cache\\{ticker}\\{day}"
            metadata_authority = q3_files.get(relative + ".json")
            npz_authority = q3_files.get(relative + ".npz")
            require(isinstance(metadata_authority, dict) and isinstance(npz_authority, dict), "Q3 complete pair")
            metadata_path = guard_file(Path(metadata_authority["path"]), (BASE / "h2_context_q3_1030_01",), seen_physical)
            npz_path = guard_file(Path(npz_authority["path"]), (BASE / "h2_context_q3_1030_01",), seen_physical)
            metadata_pin, npz_pin = file_pin(metadata_path), file_pin(npz_path)
            require(same_pin(metadata_authority, metadata_pin) and same_pin(npz_authority, npz_pin), "Q3 raw cache authority pin")
            binding_sha, binding_metadata_sha = npz_pin["sha256"], metadata_pin["sha256"]
        metadata_doc = load_json(metadata_path)
        cache_version = validate_cache_metadata(metadata_doc, metadata_path, npz_path, ticker, day, close_i, npz_pin)
        payloads[key] = validate_npz(npz_path, ticker, day, close_i)
        stats = {"cache_metadata": {"before": stat_record(metadata_path), "after": stat_record(metadata_path)},
                 "npz": {"before": stat_record(npz_path), "after": stat_record(npz_path)}}
        if feature_path is not None:
            stats = {"feature_metadata": {"before": stat_record(feature_path), "after": stat_record(feature_path)}, **stats}
        output.append({**base, "cache_status": "AVAILABLE", "missing_reason": None,
                       "feature_metadata_path": str(absolute(feature_path)) if feature_path else None,
                       "feature_metadata_bytes": feature_pin["bytes"] if feature_pin else None,
                       "feature_metadata_sha256": feature_pin["sha256"] if feature_pin else None,
                       "cache_metadata_path": str(absolute(metadata_path)), "cache_metadata_bytes": metadata_pin["bytes"],
                       "cache_metadata_sha256": metadata_pin["sha256"], "npz_path": str(absolute(npz_path)),
                       "npz_bytes": npz_pin["bytes"], "npz_sha256": npz_pin["sha256"],
                       "cache_version": cache_version, "binding_source_sha256": binding_sha,
                       "binding_source_metadata_sha256": binding_metadata_sha, "stats": stats})
        if journal is not None:
            opened = ([feature_pin] if feature_pin else []) + [metadata_pin, npz_pin]
            journal.append("CACHE_SPOT_PATH", "COMPLETED", f"{ticker}:{day}",
                           pins_after={pin["path"]: pin for pin in opened},
                           details={"substeps": ["ADMIT_SPOT_METADATA", "LOAD_SPOT_TRIPLETS"]})
    require(actual_missing == missing_expected and len(output) == 2790, "closed spot missing list")
    validate_cache_population(output)
    return output, payloads


def validate_cache_population(rows: Sequence[Mapping[str, Any]]) -> None:
    counts = Counter((row["authority"], row["cache_status"], row["session_kind"]) for row in rows)
    require(len(rows) == 2790, "spot identity population")
    require(sum(value for (authority, status, _kind), value in counts.items()
                if authority == "H1" and status == "AVAILABLE") == 2619, "H1 available population")
    require(sum(value for (authority, status, _kind), value in counts.items()
                if authority == "H1" and status == "MISSING") == 6, "H1 missing population")
    require(sum(value for (authority, status, _kind), value in counts.items()
                if authority == "Q3" and status == "AVAILABLE") == 153, "Q3 available population")
    require(sum(value for (authority, status, _kind), value in counts.items()
                if authority == "Q3" and status == "MISSING") == 12, "Q3 missing population")
    require(sum(value for (_authority, status, kind), value in counts.items()
                if status == "AVAILABLE" and kind == "FULL") == 2748, "FULL available population")
    require(sum(value for (_authority, status, kind), value in counts.items()
                if status == "MISSING" and kind == "FULL") == 18, "FULL missing population")
    require(sum(value for (_authority, status, kind), value in counts.items()
                if status == "AVAILABLE" and kind == "SHORT") == 24, "SHORT available population")


def compare_spot(producer_root: Path, cache_rows: Sequence[Mapping[str, Any]],
                 payloads: Mapping[tuple[str, str], tuple[list[dict[str, Any]], dict[str, int]]],
                 ) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    spot_file = pq.ParquetFile(producer_root / "spot_paths.parquet")
    require_schema(spot_file.schema_arrow, spot_schema(), "spot_paths")
    require(spot_file.metadata.num_row_groups == len(cache_rows), "spot row-group count")
    actual_coverage = load_jsonl(producer_root / "spot_coverage.jsonl")
    expected_coverage = []
    admitted: dict[str, dict[str, Any]] = {}
    total_rows = valid_rows = 0
    for group_index, cache in enumerate(cache_rows):
        close_i = cache["close_i"]
        if cache["cache_status"] == "AVAILABLE":
            if cache["feature_metadata_path"] is not None:
                admitted[cache["feature_metadata_path"]] = {"path": cache["feature_metadata_path"],
                                                              "bytes": cache["feature_metadata_bytes"],
                                                              "sha256": cache["feature_metadata_sha256"]}
            admitted[cache["cache_metadata_path"]] = {"path": cache["cache_metadata_path"],
                                                        "bytes": cache["cache_metadata_bytes"],
                                                        "sha256": cache["cache_metadata_sha256"]}
            admitted[cache["npz_path"]] = {"path": cache["npz_path"], "bytes": cache["npz_bytes"],
                                            "sha256": cache["npz_sha256"]}
            rows, counts = payloads[(cache["ticker"], cache["date"])]
        else:
            start = np.datetime64(f"{cache['date'][:4]}-{cache['date'][4:6]}-{cache['date'][6:]}T09:30", "ns").astype(np.int64)
            rows = [{"minute_i": index, "time_ns": int(start + index * 60_000_000_000), "spot": None,
                     "spot_valid": False} for index in range(close_i + 1)]
            counts = {"valid_count": 0, "invalid_count": close_i + 1, "first_valid_i": None, "last_valid_i": None}
        for row in rows:
            row.update({
                "ticker": cache["ticker"], "ticker_ordinal": cache["ticker_ordinal"], "date": cache["date"],
                "session_kind": cache["session_kind"], "cache_status": cache["cache_status"], **row,
                "missing_reason": cache["missing_reason"], "authority": cache["authority"],
                "feature_metadata_path": cache["feature_metadata_path"],
                "feature_metadata_sha256": cache["feature_metadata_sha256"],
                "cache_metadata_path": cache["cache_metadata_path"],
                "cache_metadata_sha256": cache["cache_metadata_sha256"],
                "cache_npz_path": cache["npz_path"], "cache_npz_sha256": cache["npz_sha256"],
                "cache_version": cache["cache_version"],
            })
        # Rebuild field order after row.update, whose pre-existing minute fields lead.
        expected_rows = [{name: row[name] for name in spot_schema().names} for row in rows]
        actual_rows = spot_file.read_row_group(group_index, use_threads=False).to_pylist()
        require({(row["ticker"], row["date"]) for row in actual_rows} == {(cache["ticker"], cache["date"])},
                "spot row group mixes identities")
        compare_rows(actual_rows, expected_rows, f"spot_paths/{cache['ticker']}:{cache['date']}")
        total_rows += len(expected_rows)
        valid_rows += sum(row["spot_valid"] for row in expected_rows)
        invalid = {row["minute_i"] for row in rows if not row["spot_valid"]}
        expected_coverage.append({
            "ticker": cache["ticker"], "ticker_ordinal": cache["ticker_ordinal"], "date": cache["date"],
            "session_kind": cache["session_kind"], "cache_status": cache["cache_status"],
            "missing_reason": cache["missing_reason"], "expected_count": close_i + 1, **counts,
            "invalid_ranges": missing_ranges({i for i in range(close_i + 1) if i not in invalid}, close_i),
            "metadata_path": cache["cache_metadata_path"], "metadata_sha256": cache["cache_metadata_sha256"],
            "npz_path": cache["npz_path"], "npz_sha256": cache["npz_sha256"],
        })
    require(total_rows == 1_086_570 and len(expected_coverage) == 2790, "spot cardinality")
    compare_rows(actual_coverage, expected_coverage, "spot_coverage")
    return {"identities": len(cache_rows), "rows": total_rows,
            "available": sum(row["cache_status"] == "AVAILABLE" for row in cache_rows),
            "missing": sum(row["cache_status"] == "MISSING" for row in cache_rows),
            "valid_rows": valid_rows}, admitted


def validate_calendar_envelope(value: Any, expected: Mapping[str, Any]) -> None:
    require(value == expected, "calendar normalization envelope")


def validate_producer_manifest(root: Path, digest: str, exit_path: Path, exit_digest: str,
                               calendar_envelope: Mapping[str, Any]) -> dict[str, Any]:
    require(root == PRODUCER and root.is_dir(), "fixed producer root")
    require(exit_path == PRODUCER_OBSERVER / "exit.json", "fixed producer observer exit path")
    manifest_path = root / "manifest.json"
    seen: set[tuple[int, int]] = set()
    guard_file(manifest_path, (PRODUCER,), seen)
    guard_file(exit_path, (PRODUCER_OBSERVER,), seen)
    require(sha256_file(manifest_path) == digest, "producer manifest CLI pin")
    require(sha256_file(exit_path) == exit_digest and load_json(exit_path).get("exit_code") == 0, "producer exit0 pin")
    manifest = load_json(manifest_path)
    require_keys(manifest, {"schema", "status", "created_utc", "implementation_pins", "authority_inputs",
                            "admitted_option_sources", "admitted_spot_inputs", "outputs", "counts",
                            "flags", "environment", "calendar_normalization"}, "producer manifest top-level schema")
    require(manifest.get("schema") == "weekly_zone_event_value_paths_manifest_v2_calendar_normalized" and
            manifest.get("status") == "COMPLETE_OUTCOME_FREE_VALUE_PATHS", "producer manifest header")
    validate_calendar_envelope(manifest.get("calendar_normalization"), calendar_envelope)
    require(isinstance(manifest.get("created_utc"), str), "producer manifest created_utc")
    require(manifest.get("flags") == EXPECTED_FLAGS, "producer flags")
    require(manifest.get("counts") == {"option_sources": 2784, "decisions": 3240, "segments": 9720,
                                       "spot_identities": 2790, "spot_rows": 1086570}, "producer counts")
    require(manifest.get("environment") == {"python": manifest["environment"]["python"], "numpy": "2.3.5",
                                              "pyarrow": "23.0.1", "ruff": "0.15.20", "pytest": "9.0.2"},
            "producer environment")
    require_keys(manifest["outputs"], {*DATA_OUTPUTS, "summary.json"}, "producer manifest output set")
    for name in (*DATA_OUTPUTS, "summary.json"):
        guard_file(root / name, (PRODUCER,), seen)
    row_counts = {"source_admission.jsonl": 2784, "decision_contracts.parquet": 3240,
                  "option_quote_observations.parquet": pq.ParquetFile(root / "option_quote_observations.parquet").metadata.num_rows,
                  "segment_coverage.parquet": 9720, "cache_admission.jsonl": 2790,
                  "spot_paths.parquet": 1086570, "spot_coverage.jsonl": 2790, "summary.json": 1}
    validate_output_map(manifest["outputs"], root, row_counts, "producer manifest outputs")
    return manifest


def validate_implementation_pins(manifest: Mapping[str, Any]) -> None:
    pins = manifest.get("implementation_pins")
    require(isinstance(pins, dict) and set(pins) == set(IMPLEMENTATION_PATHS),
            "producer implementation pin schema")
    for name, value in pins.items():
        require(isinstance(value, dict) and set(value) == {"path", "bytes", "sha256"}, f"implementation pin: {name}")
        require(path_key(Path(value["path"])) == path_key(IMPLEMENTATION_PATHS[name]),
                f"implementation pin exact path: {name}")
        if name == "resource_helper":
            path = guard_file(Path(value["path"]), (RESOURCE_HELPER.parent,))
        else:
            path = guard_file(Path(value["path"]), (HERE,))
        require(same_pin(value, file_pin(path)), f"implementation pin drift: {name}")
    require(pins["contract"]["sha256"] == CONTRACT_SHA256 and
            pins["resource_helper"]["sha256"] == HELPER_SHA256, "contract/helper implementation pins")


def validate_producer_journal(exit_path: Path, expected_selector: Mapping[str, str],
                              expected_trajectory: set[str], expected_cache: set[str],
                              expected_source_pins: Mapping[str, Mapping[str, Any]],
                              calendar_details: Mapping[str, Any],
                              authority_pins: Mapping[str, Mapping[str, Any]],
                              implementation_pins: Mapping[str, Mapping[str, Any]],
                              spot_pins: Mapping[str, Mapping[str, Any]],
                              expected_missing: set[str], producer_manifest: Mapping[str, Any]) -> dict[str, int]:
    path = exit_path.parent / "journal.jsonl"
    require(path.is_file(), "producer observer journal missing")
    guard_file(path, (PRODUCER_OBSERVER,))
    rows = load_jsonl(path)
    kinds = Counter(row.get("kind") for row in rows)
    for kind in ("ADMIT_AUTHORITIES", "ADMIT_OPTION_FOOTERS", "SELECT_1030",
                 "STREAM_OPTION_PATHS", "WRITE_OUTPUTS", "CLOSING_REHASH", "NORMALIZE_CALENDAR"):
        require(kinds[kind] >= 2, f"producer journal kind missing: {kind}")
    implementation_document_path = guard_file(exit_path.parent / "implementation_pins.json", (PRODUCER_OBSERVER,))
    implementation_document = file_pin(implementation_document_path)
    admissions = [row for row in rows if row.get("kind") == "ADMIT_AUTHORITIES"]
    admission_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in admissions:
        admission_groups[str(row.get("identity"))].append(row)
    require(set(admission_groups) == {"IMPLEMENTATION_PINS", "PINNED_AUTHORITIES"},
            "producer authority admission identities")
    expected_admissions = {
        "IMPLEMENTATION_PINS": ([implementation_document["path"]], {"pins": 10}),
        "PINNED_AUTHORITIES": ([value["path"] for value in authority_pins.values()], {"authorities": 29}),
    }
    for identity, events in admission_groups.items():
        paths, details = expected_admissions[identity]
        require([event.get("event") for event in events] == ["STARTED", "COMPLETED"] and
                events[0].get("paths") == events[1].get("paths") == paths and
                events[1].get("details") == details,
                f"producer authority admission lifecycle: {identity}")
    normalization = [row for row in rows if row.get("kind") == "NORMALIZE_CALENDAR"]
    require(len(normalization) == 2 and [row.get("event") for row in normalization] == ["STARTED", "COMPLETED"],
            "producer calendar normalization lifecycle")
    require(all(row.get("identity") == "UNIFIED_CALENDAR" and
                row.get("paths") == [calendar_details["raw_pin"]["path"]] for row in normalization),
            "producer calendar normalization identity/path")
    require(normalization[-1].get("details") == calendar_details, "producer calendar normalization details")
    authority_complete_i = max(index for index, row in enumerate(rows)
                               if row.get("kind") == "ADMIT_AUTHORITIES" and row.get("event") == "COMPLETED")
    normalize_complete_i = rows.index(normalization[-1])
    footer_start_i = min(index for index, row in enumerate(rows)
                         if row.get("kind") == "ADMIT_OPTION_FOOTERS" and row.get("event") == "STARTED")
    require(authority_complete_i < rows.index(normalization[0]) < normalize_complete_i < footer_start_i,
            "calendar normalization journal order")

    def lifecycle(kind: str, expected: int) -> dict[str, list[Mapping[str, Any]]]:
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in rows:
            if row.get("kind") == kind and row.get("identity") != "GLOBAL_PASS":
                grouped[str(row.get("identity"))].append(row)
        require(len(grouped) == expected, f"producer {kind} identity count")
        for identity, events in grouped.items():
            require([event.get("event") for event in events] == ["STARTED", "COMPLETED"],
                    f"producer {kind} lifecycle: {identity}")
        return grouped

    selector_units = lifecycle("SELECT_1030", 1620)
    trajectory_units = lifecycle("STREAM_OPTION_PATHS", 2768)
    by_identity = lifecycle("CACHE_SPOT_PATH", 2790)
    require(set(selector_units) == set(expected_selector), "producer selector exact identity set")
    require(set(trajectory_units) == expected_trajectory, "producer trajectory exact path set")
    require(set(by_identity) == expected_cache, "producer cache exact identity set")
    for kind, grouped in (("SELECT_1030", selector_units),
                          ("STREAM_OPTION_PATHS", trajectory_units)):
        for identity, events in grouped.items():
            completed = events[-1]
            details = completed.get("details")
            expected_path = identity if kind == "STREAM_OPTION_PATHS" else expected_selector[identity]
            require(isinstance(details, dict) and details.get("source_reads") == 1,
                    f"producer {kind} source_reads: {identity}")
            require(events[0].get("paths") == events[1].get("paths") == [expected_path],
                    f"producer {kind} event path identity: {identity}")
            before_stat, after_stat = details.get("before_stat"), details.get("after_stat")
            before_sha, after_sha = details.get("sha256_before"), details.get("sha256_after")
            require(before_stat == after_stat == stat_record(Path(expected_path)),
                    f"producer {kind} stable stat: {identity}")
            current_pin = expected_source_pins.get(expected_path)
            require(isinstance(current_pin, Mapping), f"producer {kind} admitted source pin: {identity}")
            require(before_sha == after_sha == current_pin["sha256"] and
                    before_stat.get("bytes") == current_pin["bytes"],
                    f"producer {kind} stable hash/bytes: {identity}")
    require(all(re.fullmatch(r"(?:SPY|QQQ|SPXW):\d{8}", identity) for identity in selector_units),
            "producer selector unit identities")
    require(all(Path(identity).is_absolute() for identity in trajectory_units), "producer trajectory identities")
    missing_cache = {
        *(f"{ticker}:{day}" for ticker in ("QQQ", "SPY") for day in ("20260401", "20260409", "20260415")),
        *(f"{ticker}:{day}" for ticker in ("QQQ", "SPY") for day in
          ("20260701", "20260707", "20260710", "20260716", "20260826", "20260901")),
    }
    for identity, events in by_identity.items():
        details = events[-1].get("details")
        expected_steps = ["DECLARED_MISSING"] if identity in missing_cache else ["ADMIT_SPOT_METADATA", "LOAD_SPOT_TRIPLETS"]
        require(isinstance(details, dict) and details.get("substeps") == expected_steps,
                f"producer cache substeps/status: {identity}")
    for row in rows:
        if row.get("event") == "STARTED":
            gate = row.get("gate")
            require(isinstance(gate, dict) and gate.get("available_ram_bytes", 0) >= 2_000_000_000 and
                    gate.get("free_commit_bytes", 0) >= 2_000_000_000 and
                    gate.get("disk_free_bytes", 0) >= 2_000_000_000, "producer journal resource gate")
        require(row.get("kind") not in {"ADMIT_SPOT_METADATA", "LOAD_SPOT_TRIPLETS", "DECLARED_MISSING"},
                "spot substep incorrectly created a context")
        path_values = row.get("paths", []) if isinstance(row.get("paths"), list) else []
        require(not any(forbidden_path_text(Path(value)) for value in path_values),
                "producer journal contains forbidden opened path")
    require(not any(row.get("event") == "ERROR" for row in rows), "producer journal ERROR")
    require(len(authority_pins) == 29 and len(implementation_pins) == 10 and
            len(expected_source_pins) == 2768 and len(spot_pins) == 8163 and
            len(expected_missing) == 16, "producer closing input populations")
    runtime_inputs = {
        **authority_pins, **expected_source_pins, **spot_pins, **implementation_pins,
        "runtime_implementation_pins_document": implementation_document,
    }
    require(len(runtime_inputs) == 10971, "producer closing unique input population")
    expected_outputs = dict(producer_manifest["outputs"])
    expected_outputs["manifest.json"] = file_pin(PRODUCER / "manifest.json")
    require(set(expected_outputs) == {*DATA_OUTPUTS, "summary.json", "manifest.json"},
            "producer closing output population")
    expected_closing = set(runtime_inputs)
    expected_closing.update(f"EXPECTED_MISSING:{value}" for value in expected_missing)
    expected_closing.update(f"OUTPUT:{name}" for name in expected_outputs)
    closing_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("kind") == "CLOSING_REHASH":
            closing_groups[str(row.get("identity"))].append(row)
    require(set(closing_groups) == expected_closing and len(closing_groups) == 10996 and
            sum(len(events) for events in closing_groups.values()) == 21992,
            "producer closing exact identity set")
    staging_parent: Path | None = None
    for identity, events in closing_groups.items():
        require([event.get("event") for event in events] == ["STARTED", "COMPLETED"],
                f"producer closing lifecycle: {identity}")
        details = events[-1].get("details")
        require(isinstance(details, dict) and set(details) == {"before", "after"} and
                details["before"] == details["after"], f"producer closing stable details: {identity}")
        before = details["before"]
        require(isinstance(before, dict), f"producer closing before pin/stat: {identity}")
        if identity.startswith("EXPECTED_MISSING:"):
            expected_path = identity.removeprefix("EXPECTED_MISSING:")
            require(events[0].get("paths") == events[1].get("paths") == [expected_path] and
                    before == {"exists": False, "bytes": None, "mtime_ns": None, "physical_id": None},
                    f"producer closing expected missing: {identity}")
        elif identity.startswith("OUTPUT:"):
            name = identity.removeprefix("OUTPUT:")
            expected = expected_outputs[name]
            paths = events[0].get("paths")
            require(paths == events[1].get("paths") and isinstance(paths, list) and len(paths) == 1,
                    f"producer closing output path envelope: {name}")
            staging_path = Path(paths[0])
            require(set(before) == {"path", "bytes", "sha256"} and staging_path.name == name and
                    staging_path.parent.parent == PRODUCER.parent and
                    staging_path.parent.name.startswith(f".{PRODUCER.name}.") and
                    before.get("path") == str(absolute(staging_path)) and
                    before.get("bytes") == expected["bytes"] and before.get("sha256") == expected["sha256"],
                    f"producer closing staging output pin: {name}")
            if staging_parent is None:
                staging_parent = staging_path.parent
            require(staging_path.parent == staging_parent, "producer closing single staging root")
        else:
            expected = runtime_inputs[identity]
            require(events[0].get("paths") == events[1].get("paths") == [expected["path"]] and
                    before == expected, f"producer closing input pin: {identity}")
    return {"rows": len(rows), "calendar_normalizations": 1,
            "selector_source_contexts": len(selector_units),
            "trajectory_source_contexts": len(trajectory_units), "cache_contexts": len(by_identity)}


def reconstruct_sources(source_rows: Sequence[Mapping[str, Any]], historical: Mapping[str, Mapping[str, Any]],
                        journal: Journal | None = None) -> dict[str, dict[str, Any]]:
    result = {}
    seen_physical: set[tuple[int, int]] = set()
    for row in source_rows:
        path = str(absolute(Path(row["path"])))
        exists = bool(row["observation"]["exists"])
        refs = row["references"]
        require(refs and path not in result, "source identity")
        close_values = {ref["close_i"] for ref in refs}
        require(len(close_values) == 1, "source close disagreement")
        value = {"exists": exists, "close_i": close_values.pop(), "sha256": None,
                 "pin": None, "rows": None, "row_groups": None, "schema": None,
                 "clock_column": None, "clock_basis": None, "gamma_column_present": None,
                 "stat": stat_record(Path(path))}
        @contextmanager
        def unit() -> Iterator[dict[str, Any]]:
            if journal is None:
                resource_gate()
                yield {}
            else:
                with journal.unit("ADMIT_OPTION_FOOTER", path, [Path(path)] if exists else []) as details:
                    yield details
        with unit() as details:
            if exists:
                guard_file(Path(path), (SOURCE_ROOT,), seen_physical)
                pin = file_pin(Path(path))
                value["sha256"] = pin["sha256"]
                footer = pq.ParquetFile(path)
                clock, basis, gamma, _columns = validate_option_schema(footer.schema_arrow)
                value.update({"pin": pin, "rows": footer.metadata.num_rows,
                              "row_groups": footer.metadata.num_row_groups, "schema": footer.schema_arrow,
                              "clock_column": clock, "clock_basis": basis,
                              "gamma_column_present": gamma})
                if path in historical:
                    expected = historical[path]
                    require(pin["bytes"] == expected["bytes"] and pin["sha256"] == expected["sha256"], "historical source pin")
                    require(footer.metadata.num_rows == expected["rows"] and
                            parquet_schema_signature(footer.schema_arrow) == expected["projected_schema"], "historical footer projection")
            else:
                guard_missing(Path(path), SOURCE_ROOT)
            details["footer_reads"] = int(exists)
        result[path] = value
    require(len(result) == 2784 and sum(v["exists"] for v in result.values()) == 2768, "source population")
    return result


def metadata_pairs(value: Mapping[bytes, bytes] | None) -> list[dict[str, str]]:
    if not value:
        return []
    return [{"key_b64": base64.b64encode(key).decode("ascii"),
             "value_b64": base64.b64encode(item).decode("ascii")}
            for key, item in sorted(value.items())]


def full_schema(schema: pa.Schema) -> dict[str, Any]:
    return {"fields": [{"name": field.name, "type": str(field.type), "nullable": field.nullable,
                         "metadata": metadata_pairs(field.metadata)} for field in schema],
            "metadata": metadata_pairs(schema.metadata)}


def validate_source_admission(actual: Sequence[Mapping[str, Any]], source_rows: Sequence[Mapping[str, Any]],
                              historical: Mapping[str, Mapping[str, Any]],
                              reconstructed: Mapping[str, Mapping[str, Any]]) -> None:
    source_index = {str(absolute(Path(row["path"]))): row for row in source_rows}
    require(len(actual) == len(source_index) == 2784, "source admission population")
    require([row["path"] for row in actual] == sorted(source_index, key=os.path.normcase), "source admission order")
    kinds = Counter()
    for row in actual:
        expected_keys = {
            "path", "ticker", "trade_date", "expiration", "stage_a_exists", "admission_status",
            "binding_kind", "bytes", "sha256", "rows", "row_groups", "projected_schema",
            "full_schema", "clock_column", "clock_basis", "gamma_column_present",
            "expected_binding_authorities", "before_stat", "after_stat", "ignored_reason",
        }
        require(set(row) == expected_keys, "source admission schema")
        source = source_index.get(row["path"])
        require(source is not None, "source admission unknown path")
        _ = source["references"]
        require(row["ticker"] == source["ticker"] and row["trade_date"] == source["trade_date"] and
                row["expiration"] == source["expiration"], "source admission identity")
        authorities = sorted({item["authority"] for item in source["expected_upstream_bindings"]})
        require(row["expected_binding_authorities"] == authorities, "source admission authorities")
        exists = bool(source["observation"]["exists"])
        require(row["stage_a_exists"] is exists and row["admission_status"] == ("PRESENT" if exists else "MISSING"),
                "source admission existence")
        kind = "EXPECTED_MISSING" if not exists else ("HISTORICAL" if row["path"] in historical else "FIRST_AUTHORITY")
        require(row["binding_kind"] == kind, "source admission binding kind")
        kinds[kind] += 1
        if not exists:
            empty_stat = {"exists": False, "bytes": None, "mtime_ns": None, "physical_id": None}
            require(all(row[name] is None for name in ("bytes", "sha256", "rows", "row_groups",
                                                       "projected_schema", "full_schema", "clock_column",
                                                       "clock_basis", "gamma_column_present")), "missing admission nulls")
            require(row["before_stat"] == row["after_stat"] == empty_stat and
                    row["ignored_reason"] == "EXPECTED_MISSING_STAGE_A", "missing admission stat/reason")
            continue
        cached = reconstructed[row["path"]]
        current_pin = cached["pin"]
        require(row["bytes"] == current_pin["bytes"] and row["sha256"] == current_pin["sha256"] and
                row["rows"] == cached["rows"] and row["row_groups"] == cached["row_groups"],
                "present source admission footer/pin")
        require(row["clock_column"] == cached["clock_column"] and row["clock_basis"] == cached["clock_basis"] and
                row["gamma_column_present"] is cached["gamma_column_present"] and row["ignored_reason"] is None,
                "source admission clock/gamma")
        current_stat = cached["stat"]
        require(row["before_stat"] == row["after_stat"] == current_stat, "source admission stats")
        if kind == "HISTORICAL":
            expected = historical[row["path"]]
            require(row["projected_schema"] == expected["projected_schema"] and row["full_schema"] is None,
                    "historical admission schema")
        else:
            require(row["projected_schema"] is None and row["full_schema"] == full_schema(cached["schema"]),
                    "first authority full schema")
    require(kinds == {"HISTORICAL": 2765, "FIRST_AUTHORITY": 3, "EXPECTED_MISSING": 16},
            "source admission kind counts")


def run(producer_root: Path, producer_manifest_sha256: str, producer_exit: Path,
        producer_exit_sha256: str, auditor_sha256: str, tests_sha256: str,
        review_pin: Mapping[str, Any], binding_pin: Mapping[str, Any], launcher_pin: Mapping[str, Any],
        output: Path = OUTPUT, observer: Path = OBSERVER) -> dict[str, Any]:
    require(output == OUTPUT and observer == OBSERVER and not output.exists() and not observer.exists(), "exclusive audit roots")
    validate_environment()
    bind_resource_helper()
    observer.mkdir(parents=False, exist_ok=False)
    journal = Journal(observer / "journal.jsonl")
    with journal.unit("ADMIT_AUTHORITIES", "ALL", [CONTRACT, RESOURCE_HELPER]):
        documents, authority_pins = admit_pins()
        require(sha256_file(Path(__file__).resolve()) == auditor_sha256 and sha256_file(TESTS) == tests_sha256,
                "auditor/tests CLI pins")
        for label, value in (("review", review_pin), ("binding", binding_pin), ("launcher", launcher_pin)):
            path = guard_file(Path(value["path"]), (HERE,))
            require(same_pin(value, file_pin(path)), f"{label} pin")
    with journal.unit("NORMALIZE_CALENDAR", "UNIFIED_CALENDAR",
                      [Path(authority_pins["unified_calendar"]["path"])]) as normalization_journal:
        normalized_calendar, calendar_envelope, calendar_details = normalize_calendar_v2(
            documents["unified_calendar"], authority_pins["unified_calendar"],
        )
        normalization_journal.update(calendar_details)
    manifest = validate_producer_manifest(
        producer_root, producer_manifest_sha256, producer_exit, producer_exit_sha256, calendar_envelope,
    )
    validate_implementation_pins(manifest)
    require(manifest.get("authority_inputs") == authority_pins, "producer authority input closure")
    plans = load_jsonl(STAGE_A / "entry_plan.jsonl")
    source_rows = load_jsonl(STAGE_A / "weekly_sources.jsonl")
    expected_selector = {row["plan_id"]: str(absolute(Path(row["entry_path"])))
                         for row in plans if row["status"] == "PLANNED"}
    expected_trajectory = {str(absolute(Path(row["path"]))) for row in source_rows
                           if row["observation"]["exists"]}
    expected_missing = {str(absolute(Path(row["path"]))) for row in source_rows
                        if not row["observation"]["exists"]}
    expected_cache_ids = {f"{row['ticker']}:{row['date']}" for row in normalized_calendar}
    producer_journal = validate_producer_journal(
        producer_exit, expected_selector, expected_trajectory, expected_cache_ids,
        manifest["admitted_option_sources"], calendar_details, authority_pins,
        manifest["implementation_pins"], manifest["admitted_spot_inputs"], expected_missing, manifest,
    )
    historical = {}
    for name in ("h1_inventory", "q3_inventory", "bridge_inventory"):
        for row in documents[name]["sources"]:
            if row.get("status") == "INVENTORIED":
                historical[str(absolute(Path(row["path"])))] = row
    with journal.unit("ADMIT_OPTION_FOOTERS", "ALL", [Path(row["path"]) for row in source_rows if row["observation"]["exists"]]):
        sources = reconstruct_sources(source_rows, historical, journal=journal)
        source_admission = load_jsonl(producer_root / "source_admission.jsonl")
        validate_source_admission(source_admission, source_rows, historical, sources)
    with journal.unit("SELECT_1030", "ALL", [Path(plan["entry_path"]) for plan in plans if plan["status"] == "PLANNED"]):
        decisions, selector_counts = select_contracts(plans, journal=journal)
    actual_decision_schema, actual_decisions = table_rows(producer_root / "decision_contracts.parquet")
    require_schema(actual_decision_schema, decision_schema(), "decision_contracts")
    compare_rows(actual_decisions, decisions, "decision_contracts")
    observation_file = pq.ParquetFile(producer_root / "option_quote_observations.parquet")
    require_schema(observation_file.schema_arrow, observation_schema(), "option_quote_observations")
    observation_group = 0

    def consume_observations(source_path: str, expected_rows: Sequence[Mapping[str, Any]]) -> None:
        nonlocal observation_group
        if not expected_rows:
            return
        require(observation_group < observation_file.metadata.num_row_groups, "observation row-group underflow")
        actual_rows = observation_file.read_row_group(observation_group, use_threads=False).to_pylist()
        require({row["source_path"] for row in actual_rows} == {source_path}, "observation row group mixes sources")
        compare_rows(actual_rows, expected_rows, f"option_quote_observations/{source_path}")
        observation_group += 1

    with journal.unit("STREAM_OPTION_PATHS", "ALL", [Path(path) for path, source in sources.items() if source["exists"]]):
        observations, coverage, option_counts = option_paths(
            plans, decisions, sources, journal=journal, observation_consumer=consume_observations,
        )
    require(not observations and observation_group == observation_file.metadata.num_row_groups,
            "observation streaming row-group closure")
    actual_observation_schema = observation_file.schema_arrow
    actual_coverage_schema, actual_coverage = table_rows(producer_root / "segment_coverage.parquet")
    require_schema(actual_coverage_schema, coverage_schema(), "segment_coverage")
    compare_rows(actual_coverage, coverage, "segment_coverage")
    cache_admission = load_jsonl(producer_root / "cache_admission.jsonl")
    expected_cache, spot_payloads = expected_cache_admission(
        documents, journal=journal, calendar_rows=normalized_calendar,
    )
    compare_rows(cache_admission, expected_cache, "cache_admission")
    require(len(cache_admission) == 2790 and sum(row["cache_status"] == "MISSING" for row in cache_admission) == 18,
            "cache admission population")
    spot_counts, admitted_spot = compare_spot(producer_root, expected_cache, spot_payloads)
    require(len(admitted_spot) == 8163, "admitted spot input cardinality")
    summary = load_json(producer_root / "summary.json")
    require_keys(summary, {"schema", "status", "created_utc", "stage_a", "option_admission", "selector",
                           "option_paths", "spot", "outputs", "flags", "limitations",
                           "calendar_normalization"}, "summary top-level schema")
    require(summary.get("schema") == "weekly_zone_event_value_paths_summary_v2_calendar_normalized" and
            summary.get("flags") == EXPECTED_FLAGS and summary.get("status") == "COMPLETE_OUTCOME_FREE_VALUE_PATHS",
            "summary header/flags")
    validate_calendar_envelope(summary.get("calendar_normalization"), calendar_envelope)
    require(isinstance(summary.get("created_utc"), str), "summary created_utc")
    require(summary["stage_a"] == {"sessions": 930, "ticker_days": 2790, "planned": 1620,
                                    "no_series": 1164, "terminal": 6, "references": 4860,
                                    "unique_sources": 2784}, "summary Stage A")
    new_bases = Counter(row["clock_basis"] for row in source_admission if row["binding_kind"] == "FIRST_AUTHORITY")
    require(summary["option_admission"] == {"present": 2768, "missing": 16, "historical": 2765,
                                             "first_authority": 3, "native_historical": 1562,
                                             "proxy_historical": 1203,
                                             "native_new": new_bases["NATIVE_STORED_TIMESTAMP"],
                                             "proxy_new": new_bases["UNDERLYING_TIMESTAMP_PROXY"]},
            "summary option admission exact")
    require(summary["selector"] == {"plans": 1620, "decisions": 3240, "h1": 3054, "q3": 180,
                                     "bridge": 6, "calls": 1620, "puts": 1620,
                                     "no_valid_call": 0, "no_valid_put": 0}, "summary selector")
    require(summary["option_paths"] == {"segments": 9720, "observations": option_counts["observation_count"],
                                         "selector_source_reads": 1620, "trajectory_source_reads": 2768,
                                         "ignored_subminute_rows": option_counts["ignored_subminute_rows"],
                                         "ignored_out_of_session_rows": option_counts["ignored_out_of_session_rows"],
                                         "missing_minutes": sum(row["missing_minute_count"] for row in coverage)},
            "summary option paths exact")
    require(summary["spot"] == {"identities": 2790, "available": 2772, "missing": 18,
                                 "full": 2766, "short": 24, "available_rows": 1079532,
                                 "missing_rows": 7038, "path_rows": 1086570,
                                 "valid_rows": spot_counts["valid_rows"],
                                 "invalid_rows": 1086570 - spot_counts["valid_rows"]}, "summary spot exact")
    summary_rows = {"source_admission.jsonl": 2784, "decision_contracts.parquet": 3240,
                    "option_quote_observations.parquet": option_counts["observation_count"],
                    "segment_coverage.parquet": 9720, "cache_admission.jsonl": 2790,
                    "spot_paths.parquet": 1086570, "spot_coverage.jsonl": 2790}
    validate_output_map(summary["outputs"], producer_root, summary_rows, "summary outputs")
    limitations = summary["limitations"]
    require(isinstance(limitations, list) and len(limitations) == 5, "summary limitations count")
    require(limitations == EXPECTED_LIMITATIONS, "summary limitations exact/order")
    require(manifest["admitted_spot_inputs"] == dict(sorted(admitted_spot.items(), key=lambda item: os.path.normcase(item[0]))),
            "admitted spot input closure")
    admitted_options = {path: file_pin(Path(path)) for path, source in sources.items() if source["exists"]}
    require(manifest["admitted_option_sources"] == dict(sorted(admitted_options.items(), key=lambda item: os.path.normcase(item[0]))),
            "admitted option input closure")
    producer_outputs = {f"producer_output:{name}": file_pin(producer_root / name)
                        for name in (*DATA_OUTPUTS, "summary.json", "manifest.json")}
    all_inputs = {**authority_pins, **admitted_options, **admitted_spot, **producer_outputs,
                  "producer_exit": file_pin(producer_exit)}
    for name, value in all_inputs.items():
        with journal.unit("CLOSING_REHASH", str(name), [Path(value["path"])]):
            require(same_pin(value, file_pin(Path(value["path"]))), f"closing rehash drift: {name}")
    for path, source in sources.items():
        if not source["exists"]:
            with journal.unit("CLOSING_REHASH", path, []):
                require(not Path(path).exists(), f"expected missing source appeared at close: {path}")
    output.mkdir(parents=False, exist_ok=False)
    audit = {
        "schema": "weekly_zone_event_value_paths_audit_v2_calendar_normalized", "status": "PASS",
        "producer": {"manifest": file_pin(producer_root / "manifest.json"), "exit": file_pin(producer_exit)},
        "implementation": {"auditor": file_pin(Path(__file__).resolve()), "tests": file_pin(TESTS),
                           "review": dict(review_pin), "runtime_binding": dict(binding_pin), "launcher": dict(launcher_pin)},
        "reconstruction": {"sources": len(sources), "present_sources": len(admitted_options),
                           "decisions": len(decisions), "observations": option_counts["observation_count"],
                           "segments": len(coverage), "spot": spot_counts,
                           "selector_source_reads": selector_counts["selector_source_reads"],
                           "trajectory_source_reads": option_counts["trajectory_source_reads"],
                           "calendar_normalization": calendar_envelope},
        "comparisons": {"decision_schema": str(actual_decision_schema),
                        "observation_schema": str(actual_observation_schema),
                        "coverage_schema": str(actual_coverage_schema), "rows_values_order": "PASS",
                        "producer_output_hashes": "PASS", "summary": "PASS", "closing_rehash": "PASS"},
        "security": {"producer_imported": False, "spot_module_imported": False,
                     "forbidden_paths_opened": False, "source_once_per_pass": True,
                     "spot_arrays_read": ["time_ns", "spot", "spot_valid"],
                     "producer_journal": producer_journal},
        "flags": EXPECTED_FLAGS,
        "limitations": EXPECTED_LIMITATIONS,
    }
    with journal.unit("WRITE_AUDIT_OUTPUT", "audit.json", []):
        write_json(output / "audit.json", audit)
    audit_pin = file_pin(output / "audit.json")
    audit_manifest = {
        "schema": "weekly_zone_event_value_paths_audit_manifest_v2_calendar_normalized", "status": "PASS",
        "audit": audit_pin, "producer_manifest": file_pin(producer_root / "manifest.json"),
        "producer_exit": file_pin(producer_exit), "authority_inputs": authority_pins,
        "admitted_option_sources": dict(sorted(admitted_options.items(), key=lambda item: os.path.normcase(item[0]))),
        "admitted_spot_inputs": dict(sorted(admitted_spot.items(), key=lambda item: os.path.normcase(item[0]))),
        "counts": audit["reconstruction"], "flags": EXPECTED_FLAGS,
        "calendar_normalization": calendar_envelope,
    }
    with journal.unit("WRITE_AUDIT_OUTPUT", "manifest.json", []):
        write_json(output / "manifest.json", audit_manifest)
    return audit


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--execute-reviewed-audit", action="store_true")
    result.add_argument("--producer-root", type=Path, default=PRODUCER)
    result.add_argument("--producer-manifest-sha256")
    result.add_argument("--producer-exit", type=Path)
    result.add_argument("--producer-exit-sha256")
    result.add_argument("--auditor-sha256")
    result.add_argument("--tests-sha256")
    for prefix in ("review", "runtime-binding", "launcher"):
        result.add_argument(f"--{prefix}-path", type=Path)
        result.add_argument(f"--{prefix}-bytes", type=int)
        result.add_argument(f"--{prefix}-sha256")
    result.add_argument("--output", type=Path, default=OUTPUT)
    result.add_argument("--observer", type=Path, default=OBSERVER)
    return result


def cli_pin(args: argparse.Namespace, prefix: str) -> dict[str, Any]:
    name = prefix.replace("-", "_")
    path = getattr(args, name + "_path")
    size = getattr(args, name + "_bytes")
    digest = getattr(args, name + "_sha256")
    require(path is not None and type(size) is int and isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest),
            f"{prefix} reviewed pin args")
    return {"path": str(absolute(path)), "bytes": size, "sha256": digest}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.execute_reviewed_audit:
        print(json.dumps({"status": "READY_NOT_EXECUTED", "scope": "independent outcome-free value-path audit",
                          "output": str(args.output)}, sort_keys=True))
        return 0
    hashes = (args.producer_manifest_sha256, args.producer_exit_sha256, args.auditor_sha256, args.tests_sha256)
    require(args.producer_exit is not None and all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                                                   for value in hashes), "reviewed hash args")
    audit = run(absolute(args.producer_root), args.producer_manifest_sha256, absolute(args.producer_exit),
                args.producer_exit_sha256, args.auditor_sha256, args.tests_sha256,
                cli_pin(args, "review"), cli_pin(args, "runtime-binding"), cli_pin(args, "launcher"),
                absolute(args.output), absolute(args.observer))
    print(json.dumps({"status": audit["status"], "audit": str(args.output / "audit.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
