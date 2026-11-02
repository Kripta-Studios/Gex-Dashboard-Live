"""One-shot, fail-closed wrapper for the reviewed C geometry producer.

This module intentionally contains only standard-library code.  It never imports
the C producer, C auditor, B auditor, or any market-data module: the producer is
started as one separately retained child only after every launcher admission
check has completed.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable, Mapping, Sequence


PYTHON = Path(r"C:\Program Files\Python314\python.exe")
REPO = Path(r"C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live")
WEEK = REPO / "research_papers" / "JEPA" / "weekly_multiday_20261101"
LEVEL = REPO / "research_papers" / "JEPA" / "level_oracle_20261018"
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
BRANCH = "research/multiscale-v1r1-net-usd"
MINIMUM_BYTES = 2_000_000_000
PLAN_SCHEMA = "c_geometry_1030_producer_launch_plan_v1"
PLAN_STATUS = "PASS_FINAL_C_GEOMETRY_PRODUCER_LAUNCH_PLAN"
BUNDLE_SCHEMA = "weekly_zone_event_value_paths_final_admission_v1"
BUNDLE_STATUS = "PASS_FINAL_B_ADMISSION"
BINDING_SCHEMA = "c_geometry_1030_runtime_binding_v1"
BINDING_STATUS = "PASS_FINAL_C_RUNTIME_BINDING"
FORMAL_FIXTURE_SCHEMA = "c_geometry_1030_producer_launcher_fixture_closure_v1"
FORMAL_FIXTURE_STATUS = "PASS_CLOSED"
FORMAL_PYTEST_EXIT_KEYS = {"exit_code", "pid", "creation_epoch", "metadata_error", "changed_pins", "retry"}
OFFICIAL_RESOURCE_HELPER = LEVEL / "launch_monthly_test_index_v2_audit_20261024.py"
OFFICIAL_RESOURCE_HELPER_PIN = {
    "path": str(OFFICIAL_RESOURCE_HELPER), "bytes": 31_463,
    "sha256": "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
}
CANONICAL_C_PRODUCER = WEEK / "build_weekly_zone_geometry_1030.py"
CANONICAL_C_PRODUCER_PIN = {
    "path": str(CANONICAL_C_PRODUCER), "bytes": 73_030,
    "sha256": "ebe7c8984e2e7eb3806193e7c891dbbb0d0449b19e13e0657d0b68cdbe0d1b01",
}
C_FINAL_REVIEW = WEEK / "C_GEOMETRY_FINAL_IMPLEMENTATION_REVIEW_20261102.md"
C_FINAL_REVIEW_PIN = {
    "path": str(C_FINAL_REVIEW), "bytes": 2_160,
    "sha256": "3e306e8bebc95686fd2e6dd4fa3496d834fdf9b07882f4b15922fedc7f679fc7",
}

OUTPUT = BASE / "weekly_zone_geometry_1030_01"
CHILD_OBSERVER = BASE / "weekly_zone_geometry_1030_observer_01"
OBSERVER = BASE / "weekly_zone_geometry_1030_launcher_observer_01"
CHILD_JOURNAL = CHILD_OBSERVER / "journal.jsonl"
EXPECTED_ROOTS = {
    "output_dir": str(OUTPUT),
    "observer_dir": str(CHILD_OBSERVER),
    "launcher_observer_dir": str(OBSERVER),
    "journal": str(CHILD_JOURNAL),
}
THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "ARROW_NUM_THREADS": "1",
    "POLARS_MAX_THREADS": "1",
    "TBB_NUM_THREADS": "1",
    "NUMBA_NUM_THREADS": "1",
}
PIN_KEYS = {"path", "bytes", "sha256"}
B_OUTPUT_NAMES = {
    "cache_admission.jsonl", "decision_contracts.parquet",
    "option_quote_observations.parquet", "segment_coverage.parquet",
    "source_admission.jsonl", "spot_coverage.jsonl", "spot_paths.parquet",
    "summary.json",
}
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
FINAL_B_FLAG_KEYS = {
    "actions_read", "candidates_read", "context_feature_arrays_read",
    "economic_evaluation_performed", "fit_performed", "inference_performed",
    "labels_read", "models_read", "option_raw_values_read", "outcomes_read",
    "parquet_footers_read", "pnl_computed", "promotion_approved",
    "replay_performed", "risk_or_qty_computed", "selected_policy",
    "spot_cache_arrays_read", "technical_ready",
}
REPOSITORY_ROLES = {
    "launcher", "runtime_binding", "runtime_binding_review", "launcher_contract",
    "launcher_tests", "wrapper_fixture_receipt", "wrapper_fixture_exit",
    "c_final_review", "c_producer", "c_producer_tests", "c_auditor",
    "c_auditor_tests", "c_admission_contract", "c_operational_draft",
    "c_binding_feasibility", "c_windows_feasibility", "c_parallel_amendment",
    "c_parallel_review", "level_engine", "session_level_engine", "session_clock",
    "session_cache", "build_cache", "resource_helper", "b_final_bundle",
    "b_final_review",
}


class LaunchError(RuntimeError):
    """An admission or closure error that must not be retried automatically."""


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def compact_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contains_pending(value: Any) -> bool:
    if isinstance(value, str):
        return "PENDING" in value.upper()
    if isinstance(value, Mapping):
        return any(contains_pending(key) or contains_pending(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(contains_pending(item) for item in value)
    return False


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _plain_path(path: Path, label: str) -> Path:
    absolute = Path(os.path.abspath(path))
    if path != absolute or path.is_symlink() or not path.is_file():
        raise LaunchError(f"{label}: path is absent, relative, linked, or non-file")
    current = path
    while True:
        info = os.lstat(current)
        if getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise LaunchError(f"{label}: reparse point {current}")
        if current.parent == current:
            break
        current = current.parent
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise LaunchError(f"{label}: file is not one plain regular file")
    return path


def verify_pin(value: Any, label: str) -> tuple[Path, dict[str, Any], tuple[int, int]]:
    if not isinstance(value, Mapping) or set(value) != PIN_KEYS:
        raise LaunchError(f"{label}: pin keys")
    if type(value["path"]) is not str or not PureWindowsPath(value["path"]).is_absolute():
        raise LaunchError(f"{label}: absolute Windows pin path")
    if type(value["bytes"]) is not int or value["bytes"] < 0 or not _is_sha256(value["sha256"]):
        raise LaunchError(f"{label}: pin scalar")
    path = _plain_path(Path(value["path"]), label)
    info = path.stat()
    actual = sha256_file(path)
    if info.st_size != value["bytes"] or actual != value["sha256"]:
        raise LaunchError(f"{label}: pin bytes/hash mismatch")
    return path, dict(value), (int(info.st_dev), int(info.st_ino))


def read_pinned_json(value: Any, label: str) -> tuple[Path, dict[str, Any], tuple[int, int]]:
    path, pin, identity = verify_pin(value, label)
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LaunchError(f"{label}: pinned JSON unreadable: {type(error).__name__}: {error}") from error
    if not isinstance(result, dict):
        raise LaunchError(f"{label}: JSON object required")
    return path, result, identity


def assert_no_physical_aliases(records: Iterable[tuple[str, Path, Mapping[str, Any], tuple[int, int]]]) -> None:
    """Permit repeated roles for one nominal file, never alternate names for one file."""
    by_identity: dict[tuple[int, int], list[tuple[str, Path, Mapping[str, Any]]]] = {}
    for role, path, pin, identity in records:
        by_identity.setdefault(identity, []).append((role, path, pin))
    for identity, values in by_identity.items():
        paths = {os.path.normcase(os.path.abspath(path)) for _, path, _ in values}
        if len(paths) != 1:
            roles = sorted(role for role, _, _ in values)
            raise LaunchError(f"physical alias across roles {roles}: {identity}")
        pins = {(item["bytes"], item["sha256"]) for _, _, item in values}
        if len(pins) != 1:
            raise LaunchError(f"conflicting pin records for physical file {identity}")


def _require_exact_keys(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise LaunchError(f"{label}: exact keys required")
    return value


def _require_b_exit(value: Mapping[str, Any], child_key: str, label: str) -> None:
    if (type(value.get("exit_code")) is not int or value["exit_code"] != 0 or
            type(value.get(child_key)) is not int or value[child_key] != 0 or
            value.get("changed_pins") != [] or value.get("metadata_error") is not None or
            value.get("retry") is not False or type(value.get("pid")) is not int or value["pid"] <= 0 or
            type(value.get("creation_epoch")) not in {int, float}):
        raise LaunchError(f"{label}: retained effective/child exit closure")


def _read_closed_journal(pin: Any, label: str, unit_key: str, terminal_unit: str) -> None:
    path, _checked, _identity = verify_pin(pin, label + " journal")
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LaunchError(f"{label}: journal JSONL unreadable") from error
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise LaunchError(f"{label}: journal records")
    paired: dict[tuple[str, str], int] = {}
    for row in rows:
        event, unit, identity = row.get("event"), row.get(unit_key), row.get("identity")
        if event not in {"STARTED", "COMPLETED"} or not isinstance(unit, str) or not isinstance(identity, str):
            raise LaunchError(f"{label}: journal envelope")
        pair_key = (unit, identity)
        paired[pair_key] = paired.get(pair_key, 0) + (1 if event == "STARTED" else -1)
        if paired[pair_key] < 0:
            raise LaunchError(f"{label}: journal completion without start")
    if any(balance != 0 for balance in paired.values()):
        raise LaunchError(f"{label}: journal unit left open")
    if rows[-1].get("event") != "COMPLETED" or rows[-1].get(unit_key) != terminal_unit:
        raise LaunchError(f"{label}: journal terminal closure")


def validate_final_b_bundle(bundle_pin: Any) -> dict[str, Any]:
    """Check only final B closure metadata; do not reopen raw option or NPZ data."""
    _bundle_path, bundle, _bundle_identity = read_pinned_json(bundle_pin, "B final bundle")
    expected = {"schema", "status", "producer", "auditor", "authority_inputs", "calendar", "flags", "data_scope"}
    _require_exact_keys(bundle, expected, "B final bundle")
    if (bundle["schema"] != BUNDLE_SCHEMA or bundle["status"] != BUNDLE_STATUS or
            bundle["data_scope"] != "SEEN_DEVELOPMENT" or contains_pending(bundle)):
        raise LaunchError("B final bundle: identity/status/PENDING")
    producer = _require_exact_keys(bundle["producer"], {"manifest", "outputs", "observer"}, "B producer")
    auditor = _require_exact_keys(bundle["auditor"], {"audit", "manifest", "exit", "process", "journal"}, "B auditor")
    outputs = producer["outputs"]
    if not isinstance(outputs, Mapping) or set(outputs) != B_OUTPUT_NAMES:
        raise LaunchError("B producer: output role set")
    producer_observer = _require_exact_keys(producer["observer"], {"exit", "process", "journal"}, "B producer observer")
    authorities = bundle["authority_inputs"]
    if not isinstance(authorities, Mapping) or set(authorities) != B_AUTHORITY_KEYS:
        raise LaunchError("B authorities: role set")
    calendar = _require_exact_keys(bundle["calendar"], {"raw_file_pin", "semantic_jsonl", "identity_set_preserved", "close_i_preserved"}, "B calendar")
    semantic = _require_exact_keys(calendar["semantic_jsonl"], {"bytes", "sha256", "order", "rows"}, "B calendar semantic")
    if (type(semantic["bytes"]) is not int or not _is_sha256(semantic["sha256"]) or
            semantic["order"] != "DATE_ASC_TICKER_ORDINAL_SPY_QQQ_SPXW" or semantic["rows"] != 2790 or
            calendar["identity_set_preserved"] is not True or calendar["close_i_preserved"] is not True):
        raise LaunchError("B calendar: semantic closure")
    flags = bundle["flags"]
    if not isinstance(flags, Mapping) or set(flags) != FINAL_B_FLAG_KEYS:
        raise LaunchError("B flags: exact role set")
    true_flags = {"option_raw_values_read", "parquet_footers_read", "spot_cache_arrays_read"}
    if flags.get("selected_policy") is not None:
        raise LaunchError("B flags: selected policy")
    for name in FINAL_B_FLAG_KEYS - {"selected_policy"}:
        if flags[name] is not (name in true_flags):
            raise LaunchError(f"B flags: {name}")
    pin_records: list[tuple[str, Path, Mapping[str, Any], tuple[int, int]]] = []
    pin_values: dict[str, Any] = {"producer.manifest": producer["manifest"]}
    pin_values.update({f"producer.outputs.{name}": pin for name, pin in outputs.items()})
    pin_values.update({f"producer.observer.{name}": pin for name, pin in producer_observer.items()})
    pin_values.update({f"auditor.{name}": pin for name, pin in auditor.items()})
    pin_values.update({f"authority_inputs.{name}": pin for name, pin in authorities.items()})
    pin_values["calendar.raw_file_pin"] = calendar["raw_file_pin"]
    if len(pin_values) != 47 or authorities["unified_calendar"] != calendar["raw_file_pin"]:
        raise LaunchError("B final bundle: 47 roles / intentional calendar duplicate")
    for role, pin in pin_values.items():
        path, checked, identity = verify_pin(pin, "B " + role)
        pin_records.append((role, path, checked, identity))
    assert_no_physical_aliases(pin_records)
    by_path: dict[str, list[str]] = {}
    for role, path, _pin, _identity in pin_records:
        by_path.setdefault(os.path.normcase(os.path.abspath(path)), []).append(role)
    duplicates = [set(roles) for roles in by_path.values() if len(roles) > 1]
    if len(by_path) != 46 or duplicates != [{"authority_inputs.unified_calendar", "calendar.raw_file_pin"}]:
        raise LaunchError("B final bundle: illegal role alias")
    _producer_exit_path, producer_exit, _ = read_pinned_json(producer_observer["exit"], "B producer exit")
    _require_b_exit(producer_exit, "value_child_exit_code", "B producer")
    _producer_process_path, producer_process, _ = read_pinned_json(producer_observer["process"], "B producer process")
    if (producer_process.get("pid"), producer_process.get("creation_epoch")) != (producer_exit["pid"], producer_exit["creation_epoch"]):
        raise LaunchError("B producer: process identity")
    _producer_manifest_path, producer_manifest, _ = read_pinned_json(producer["manifest"], "B producer manifest")
    if (producer_manifest.get("schema") != "weekly_zone_event_value_paths_manifest_v2_calendar_normalized" or
            producer_manifest.get("status") != "COMPLETE_OUTCOME_FREE_VALUE_PATHS"):
        raise LaunchError("B producer: manifest schema/status")
    manifest_outputs = producer_manifest.get("outputs")
    if not isinstance(manifest_outputs, Mapping) or set(manifest_outputs) != B_OUTPUT_NAMES:
        raise LaunchError("B producer: manifest output roles")
    projected_outputs: dict[str, dict[str, Any]] = {}
    for name, record in manifest_outputs.items():
        if not isinstance(record, Mapping) or set(record) != {"path", "bytes", "sha256", "rows"} or type(record["rows"]) is not int:
            raise LaunchError("B producer: manifest output record")
        projected_outputs[name] = {key: record[key] for key in ("path", "bytes", "sha256")}
    if projected_outputs != outputs or producer_manifest.get("authority_inputs") != authorities or producer_manifest.get("flags") != flags:
        raise LaunchError("B producer: manifest closure crosslink")
    producer_calendar = producer_manifest.get("calendar_normalization")
    expected_calendar_envelope = {
        "raw_pin": calendar["raw_file_pin"], "canonical_jsonl_bytes": semantic["bytes"],
        "canonical_jsonl_sha256": semantic["sha256"], "canonical_order": semantic["order"],
        "rows": semantic["rows"], "identity_set_preserved": True, "close_i_preserved": True,
        "raw_order": "TICKER_MAJOR_QQQ_SPXW_SPY_DATE_ASC",
    }
    if producer_calendar != expected_calendar_envelope:
        raise LaunchError("B producer: calendar envelope")
    _audit_exit_path, audit_exit, _ = read_pinned_json(auditor["exit"], "B audit exit")
    _require_b_exit(audit_exit, "value_child_exit_code", "B audit")
    _audit_process_path, audit_process, _ = read_pinned_json(auditor["process"], "B audit process")
    if (audit_process.get("pid"), audit_process.get("creation_epoch")) != (audit_exit["pid"], audit_exit["creation_epoch"]):
        raise LaunchError("B audit: process identity")
    _audit_path, audit_document, _ = read_pinned_json(auditor["audit"], "B audit document")
    _audit_manifest_path, audit_manifest, _ = read_pinned_json(auditor["manifest"], "B audit manifest")
    if (audit_document.get("schema") != "weekly_zone_event_value_paths_audit_v2_calendar_normalized" or
            audit_document.get("status") != "PASS" or audit_document.get("producer") != {
                "manifest": producer["manifest"], "exit": producer_observer["exit"]} or
            audit_document.get("flags") != flags or
            audit_document.get("reconstruction", {}).get("calendar_normalization") != expected_calendar_envelope):
        raise LaunchError("B audit: document closure")
    if (audit_manifest.get("schema") != "weekly_zone_event_value_paths_audit_manifest_v2_calendar_normalized" or
            audit_manifest.get("status") != "PASS" or audit_manifest.get("audit") != auditor["audit"] or
            audit_manifest.get("producer_manifest") != producer["manifest"] or
            audit_manifest.get("producer_exit") != producer_observer["exit"] or
            audit_manifest.get("authority_inputs") != authorities or audit_manifest.get("flags") != flags or
            audit_manifest.get("calendar_normalization") != expected_calendar_envelope):
        raise LaunchError("B audit: manifest closure")
    _read_closed_journal(producer_observer["journal"], "B producer", "kind", "CLOSING_REHASH")
    _read_closed_journal(auditor["journal"], "B audit", "stage", "WRITE_AUDIT_OUTPUT")
    return bundle


def _review_marker(pin: Any, label: str, marker: str, required_sha256: str) -> None:
    path, _checked, _identity = verify_pin(pin, label)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise LaunchError(f"{label}: review unreadable") from error
    if marker not in text or required_sha256 not in text:
        raise LaunchError(f"{label}: missing reviewed marker or subject hash")


def validate_c_final_review_pin(value: Any) -> None:
    """Admit only the separately frozen, limited 69-pass implementation review."""
    if value != C_FINAL_REVIEW_PIN:
        raise LaunchError("plan must pin frozen C final implementation review")
    path, _pin, _identity = verify_pin(value, "C final implementation review")
    if "CLEAR_FINAL_IMPLEMENTATION_LIMITED_C_GEOMETRY_PREPARATION" not in path.read_text(encoding="utf-8"):
        raise LaunchError("C final review marker")


def validate_formal_fixture_closure(receipt_pin: Any, pytest_exit_pin: Any,
                                    repository_pins: Mapping[str, Any]) -> None:
    _receipt_path, receipt, _identity = read_pinned_json(receipt_pin, "formal wrapper fixture receipt")
    expected = {"schema", "status", "launcher", "tests", "compile_exit_code", "ruff_exit_code", "pytest_exit_code", "pytest_exit"}
    _require_exact_keys(receipt, expected, "formal wrapper fixture receipt")
    if (receipt["schema"] != FORMAL_FIXTURE_SCHEMA or receipt["status"] != FORMAL_FIXTURE_STATUS or
            receipt["launcher"] != repository_pins["launcher"] or receipt["tests"] != repository_pins["launcher_tests"] or
            receipt["compile_exit_code"] != 0 or receipt["ruff_exit_code"] != 0 or receipt["pytest_exit_code"] != 0 or
            receipt["pytest_exit"] != pytest_exit_pin):
        raise LaunchError("formal wrapper fixture receipt closure")
    _exit_path, pytest_exit, _ = read_pinned_json(pytest_exit_pin, "formal wrapper fixture pytest exit")
    if (set(pytest_exit) != FORMAL_PYTEST_EXIT_KEYS or
            type(pytest_exit.get("exit_code")) is not int or pytest_exit["exit_code"] != 0 or
            type(pytest_exit.get("pid")) is not int or pytest_exit["pid"] <= 0 or
            type(pytest_exit.get("creation_epoch")) not in {int, float} or not math.isfinite(pytest_exit["creation_epoch"]) or
            pytest_exit.get("metadata_error") is not None or pytest_exit.get("changed_pins") != [] or pytest_exit.get("retry") is not False):
        raise LaunchError("formal wrapper fixture retained pytest exit")


def validate_runtime_binding(binding_pin: Any, b_bundle_pin: Any, b_review_pin: Any,
                             bundle: Mapping[str, Any], repository_pins: Mapping[str, Any],
                             roots: Mapping[str, str]) -> dict[str, Any]:
    _binding_path, binding, _identity = read_pinned_json(binding_pin, "C runtime binding")
    expected = {"schema", "status", "contracts", "engines", "b_final", "resource_helper", "runtime", "runtime_roots", "windows_publication"}
    _require_exact_keys(binding, expected, "C runtime binding")
    if binding["schema"] != BINDING_SCHEMA or binding["status"] != BINDING_STATUS or contains_pending(binding):
        raise LaunchError("C runtime binding: identity/status/PENDING")
    b_final = _require_exact_keys(binding["b_final"], {"bundle", "review", "cache_admission", "raw_calendar", "calendar_semantic"}, "C binding B final")
    if b_final["bundle"] != b_bundle_pin or b_final["review"] != b_review_pin:
        raise LaunchError("C runtime binding: B bundle/review crosspin")
    if (b_final["cache_admission"] != bundle["producer"]["outputs"]["cache_admission.jsonl"] or
            b_final["raw_calendar"] != bundle["calendar"]["raw_file_pin"]):
        raise LaunchError("C runtime binding: B cache/calendar crosspin")
    if binding["resource_helper"] != repository_pins["resource_helper"]:
        raise LaunchError("C runtime binding: resource helper crosspin")
    contracts = binding["contracts"]
    contract_roles = {
        "C_GEOMETRY_1030_ADMISSION_CONTRACT_20261102.md": "c_admission_contract",
        "C_GEOMETRY_1030_OPERATIONAL_DRAFT_20261102.md": "c_operational_draft",
        "C_GEOMETRY_PARALLEL_PREPARATION_AMENDMENT_20261102.md": "c_parallel_amendment",
        "C_GEOMETRY_PARALLEL_PREPARATION_REVIEW_20261102.md": "c_parallel_review",
        "C_GEOMETRY_1030_BINDING_FEASIBILITY_20261102.md": "c_binding_feasibility",
        "C_GEOMETRY_WINDOWS_PUBLICATION_FEASIBILITY_20261102.md": "c_windows_feasibility",
    }
    if not isinstance(contracts, Mapping) or set(contracts) != set(contract_roles):
        raise LaunchError("C runtime binding: contract role set")
    for name, role in contract_roles.items():
        if contracts[name] != repository_pins[role]:
            raise LaunchError("C runtime binding: contract crosspin " + name)
    engines = binding["engines"]
    engine_roles = {
        "level_engine.py": "level_engine", "session_level_engine.py": "session_level_engine",
        "session_clock.py": "session_clock", "session_cache.py": "session_cache", "build_cache.py": "build_cache",
    }
    if not isinstance(engines, Mapping) or set(engines) != set(engine_roles):
        raise LaunchError("C runtime binding: engine role set")
    for name, role in engine_roles.items():
        if engines[name] != repository_pins[role]:
            raise LaunchError("C runtime binding: engine crosspin " + name)
    runtime = _require_exact_keys(binding["runtime"], {"python", "numpy", "pyarrow", "producer"}, "C binding runtime")
    if runtime["producer"] != repository_pins["c_producer"]:
        raise LaunchError("C runtime binding: producer crosspin")
    if binding["runtime_roots"] != {key: roots[key] for key in ("output_dir", "observer_dir", "journal")}:
        raise LaunchError("C runtime binding: designated runtime roots")
    if binding["windows_publication"] != {"api": "MoveFileExW", "flags": 8, "same_volume": True, "replace": False}:
        raise LaunchError("C runtime binding: publication policy")
    return binding


def load_plan(path: Path, expected_sha256: str) -> dict[str, Any]:
    if not _is_sha256(expected_sha256):
        raise LaunchError("plan CLI SHA-256")
    plain = _plain_path(path, "plan")
    if sha256_file(plain) != expected_sha256:
        raise LaunchError("plan CLI hash mismatch")
    try:
        plan = json.loads(plain.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LaunchError(f"plan JSON unreadable: {type(error).__name__}: {error}") from error
    expected = {"schema", "status", "branch", "data_scope", "repository_pins", "b_final", "runtime_binding", "runtime_roots"}
    _require_exact_keys(plan, expected, "plan")
    if (plan["schema"] != PLAN_SCHEMA or plan["status"] != PLAN_STATUS or plan["branch"] != BRANCH or
            plan["data_scope"] != "SEEN_DEVELOPMENT" or contains_pending(plan)):
        raise LaunchError("plan identity/status/branch/PENDING")
    roots = plan["runtime_roots"]
    if not isinstance(roots, Mapping) or dict(roots) != EXPECTED_ROOTS:
        raise LaunchError("plan designated runtime roots")
    repository_pins = plan["repository_pins"]
    if not isinstance(repository_pins, Mapping) or set(repository_pins) != REPOSITORY_ROLES:
        raise LaunchError("plan repository pin role set")
    checked: list[tuple[str, Path, Mapping[str, Any], tuple[int, int]]] = []
    for role, pin in repository_pins.items():
        path_value, checked_pin, identity = verify_pin(pin, "plan " + role)
        checked.append((role, path_value, checked_pin, identity))
    assert_no_physical_aliases(checked)
    if repository_pins["resource_helper"] != OFFICIAL_RESOURCE_HELPER_PIN:
        raise LaunchError("plan must pin the frozen official resource helper")
    if repository_pins["c_producer"] != CANONICAL_C_PRODUCER_PIN:
        raise LaunchError("plan must pin canonical 69-pass C producer")
    if repository_pins["launcher"] != {"path": str(Path(__file__).resolve()),
                                         "bytes": Path(__file__).stat().st_size,
                                         "sha256": sha256_file(Path(__file__).resolve())}:
        raise LaunchError("plan launcher self pin")
    b_final = _require_exact_keys(plan["b_final"], {"bundle", "review"}, "plan B final")
    runtime_binding = _require_exact_keys(plan["runtime_binding"], {"binding", "review"}, "plan runtime binding")
    if (b_final["bundle"] != repository_pins["b_final_bundle"] or b_final["review"] != repository_pins["b_final_review"] or
            runtime_binding["binding"] != repository_pins["runtime_binding"] or
            runtime_binding["review"] != repository_pins["runtime_binding_review"]):
        raise LaunchError("plan duplicated pin cross-reference")
    validate_c_final_review_pin(repository_pins["c_final_review"])
    bundle = validate_final_b_bundle(b_final["bundle"])
    _review_marker(b_final["review"], "B final review", "CLEAR_FINAL_B_CLOSURE", b_final["bundle"]["sha256"])
    validate_formal_fixture_closure(repository_pins["wrapper_fixture_receipt"], repository_pins["wrapper_fixture_exit"], repository_pins)
    validate_runtime_binding(runtime_binding["binding"], b_final["bundle"], b_final["review"], bundle, repository_pins, roots)
    _review_marker(runtime_binding["review"], "C binding final review", "CLEAR_FINAL_C_RUNTIME_BINDING", runtime_binding["binding"]["sha256"])
    binding_review_text = Path(runtime_binding["review"]["path"]).read_text(encoding="utf-8")
    for role in ("launcher", "launcher_tests", "launcher_contract"):
        if repository_pins[role]["sha256"] not in binding_review_text:
            raise LaunchError("C binding review wrapper pin " + role)
    return dict(plan)


def git_bytes(commit: str, path: Path) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path.relative_to(REPO).as_posix()}"], cwd=REPO)


def verify_publication(plan_path: Path, plan_sha256: str, plan: Mapping[str, Any]) -> str:
    if not plan_path.is_relative_to(REPO):
        raise LaunchError("plan must be a published repository member")
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip()
    if branch != BRANCH:
        raise LaunchError(f"unexpected branch: {branch}")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    remote_rows = subprocess.check_output(["git", "ls-remote", "origin", f"refs/heads/{BRANCH}"], cwd=REPO, text=True).split()
    if not remote_rows or commit != remote_rows[0]:
        raise LaunchError("local HEAD is not published remote HEAD")
    if sha256_file(plan_path) != plan_sha256 or git_bytes(commit, plan_path) != plan_path.read_bytes():
        raise LaunchError("plan is not byte-exact at published HEAD")
    for role, pin in plan["repository_pins"].items():
        path, _checked, _identity = verify_pin(pin, "published " + role)
        if not path.is_relative_to(REPO) or git_bytes(commit, path) != path.read_bytes():
            raise LaunchError(f"repository publication mismatch: {role}")
    return commit


def authoritative_pins(plan: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Every byte pin eligible for the wrapper closing snapshot, deduplicated by path."""
    values: dict[str, dict[str, Any]] = {}
    for role, pin in plan["repository_pins"].items():
        values["repo:" + role] = dict(pin)
    values["plan:b_bundle"] = dict(plan["b_final"]["bundle"])
    values["plan:b_review"] = dict(plan["b_final"]["review"])
    values["plan:binding"] = dict(plan["runtime_binding"]["binding"])
    values["plan:binding_review"] = dict(plan["runtime_binding"]["review"])
    _bundle_path, bundle, _ = read_pinned_json(plan["b_final"]["bundle"], "snapshot B final bundle")
    producer = bundle["producer"]
    values["bundle:producer_manifest"] = dict(producer["manifest"])
    values.update({"bundle:producer_output:" + key: dict(value) for key, value in producer["outputs"].items()})
    values.update({"bundle:producer_observer:" + key: dict(value) for key, value in producer["observer"].items()})
    values.update({"bundle:auditor:" + key: dict(value) for key, value in bundle["auditor"].items()})
    values.update({"bundle:authority:" + key: dict(value) for key, value in bundle["authority_inputs"].items()})
    values["bundle:raw_calendar"] = dict(bundle["calendar"]["raw_file_pin"])
    return values


def snapshot_pins(pins: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for role, pin in pins.items():
        path, checked, _identity = verify_pin(pin, "snapshot " + role)
        result[str(path)] = {"bytes": checked["bytes"], "sha256": checked["sha256"]}
    return result


def verify_closing(before: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    changed: list[dict[str, Any]] = []
    for raw_path, expected in before.items():
        path = Path(raw_path)
        try:
            info = _plain_path(path, "closing pin").stat()
            actual = {"bytes": info.st_size, "sha256": sha256_file(path)}
        except Exception as error:
            actual = {"error": f"{type(error).__name__}: {error}"}
        if actual != dict(expected):
            changed.append({"path": raw_path, "before": dict(expected), "after": actual})
    return changed


def _kernel32() -> Any:
    if os.name != "nt":
        raise LaunchError("Windows-only launcher")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    kernel.SetProcessAffinityMask.restype = ctypes.c_int
    kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
    kernel.GetProcessAffinityMask.restype = ctypes.c_int
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)]
    kernel.GetProcessTimes.restype = ctypes.c_int
    return kernel


def affinity_mask(handle: int | None = None) -> int:
    kernel = _kernel32()
    process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
    target = kernel.GetCurrentProcess() if handle is None else ctypes.c_void_p(handle)
    if not kernel.GetProcessAffinityMask(target, ctypes.byref(process_mask), ctypes.byref(system_mask)):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(process_mask.value)


def configure_parent() -> dict[str, Any]:
    for name, value in THREAD_ENV.items():
        os.environ[name] = value
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    kernel = _kernel32()
    if not kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(), 1):
        raise ctypes.WinError(ctypes.get_last_error())
    affinity = affinity_mask()
    if affinity != 1 or any(os.environ.get(name) != value for name, value in THREAD_ENV.items()) or os.environ.get("CUDA_VISIBLE_DEVICES") != "-1":
        raise LaunchError("parent CPU/thread/CUDA state drift")
    return {"cpu_affinity_mask": affinity, "thread_variables": dict(THREAD_ENV), "cuda_visible_devices": "-1"}


def process_times(handle: int) -> dict[str, float | None]:
    kernel = _kernel32()
    creation, exited, kernel_time, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
    if not kernel.GetProcessTimes(ctypes.c_void_p(handle), ctypes.byref(creation), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user)):
        raise ctypes.WinError(ctypes.get_last_error())

    def ticks(value: FILETIME) -> int:
        return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)

    def epoch(value: FILETIME) -> float | None:
        raw = ticks(value)
        return None if raw == 0 else (raw - 116_444_736_000_000_000) / 10_000_000.0

    result = {"creation_epoch": epoch(creation), "exit_epoch": epoch(exited),
              "kernel_seconds": ticks(kernel_time) / 10_000_000.0,
              "user_seconds": ticks(user) / 10_000_000.0}
    if result["creation_epoch"] is None or not math.isfinite(result["creation_epoch"]):
        raise LaunchError("retained handle lacks finite creation time")
    for key in ("kernel_seconds", "user_seconds"):
        if not math.isfinite(result[key]) or result[key] < 0.0:
            raise LaunchError(f"retained handle invalid {key}")
    if result["exit_epoch"] is not None and (not math.isfinite(result["exit_epoch"]) or result["exit_epoch"] < result["creation_epoch"]):
        raise LaunchError("retained handle invalid exit time")
    return result


def load_gate_helper() -> Any:
    path, _checked, _identity = verify_pin(OFFICIAL_RESOURCE_HELPER_PIN, "official resource helper")
    namespace: dict[str, Any] = {"__name__": "c_geometry_gate_helper", "__file__": str(path)}
    try:
        exec(compile(path.read_bytes(), str(path), "exec"), namespace, namespace)
    except Exception as error:
        raise LaunchError(f"official resource helper load: {type(error).__name__}: {error}") from error
    if not callable(namespace.get("observation")) or not callable(namespace.get("gate")):
        raise LaunchError("official resource helper interface")
    return type("GateHelper", (), namespace)


def resource_gate(helper: Any) -> tuple[dict[str, int], int]:
    observation = helper.observation()
    if not isinstance(observation, Mapping):
        raise LaunchError("official resource observation type")
    helper.gate(observation)
    resources = {"available_ram_bytes": observation.get("available_ram_bytes"), "free_commit_bytes": observation.get("free_commit_bytes")}
    if any(type(value) is not int or value < MINIMUM_BYTES for value in resources.values()):
        raise LaunchError("official resource helper accepted invalid observation")
    disk_free = shutil.disk_usage(BASE).free
    if disk_free < MINIMUM_BYTES:
        raise LaunchError(f"D: free bytes {disk_free} below {MINIMUM_BYTES}")
    return resources, disk_free


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> bytes:
    payload = compact_json(value)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return payload


def copy_plain_file_exclusive(source: Path, destination: Path, label: str) -> None:
    """Copy one already-durable parent record byte-for-byte without overwrite."""
    _plain_path(source, label)
    payload = source.read_bytes()
    with destination.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _plain_directory(path: Path, label: str) -> None:
    if not path.is_dir() or path.is_symlink():
        raise LaunchError(f"{label}: plain directory required")
    current = path
    while True:
        info = os.lstat(current)
        if getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise LaunchError(f"{label}: reparse directory")
        if current.parent == current:
            break
        current = current.parent


def child_command(plan: Mapping[str, Any]) -> list[str]:
    pins = plan["repository_pins"]
    binding = plan["runtime_binding"]["binding"]
    return [str(PYTHON), "-X", "utf8", "-u", pins["c_producer"]["path"],
            "--binding-json", binding["path"], "--binding-sha256", binding["sha256"],
            "--output-dir", EXPECTED_ROOTS["output_dir"], "--observer-dir", EXPECTED_ROOTS["observer_dir"],
            "--journal", EXPECTED_ROOTS["journal"]]


def _pre_child_roots() -> dict[str, bool]:
    return {"output_lexists": os.path.lexists(OUTPUT), "child_observer_lexists": os.path.lexists(CHILD_OBSERVER),
            "launcher_observer_lexists": os.path.lexists(OBSERVER)}


def _base_exit(*, effective_exit: int, child_exit: int | None, process_payload: Mapping[str, Any],
               final_times: Mapping[str, Any] | None, metadata_error: str | None,
               changed: list[dict[str, Any]], elapsed: float | None, source: str,
               publication_commit: str, mirror: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "exit_code": effective_exit, "geometry_child_exit_code": child_exit, "utc": utc_now(), "source": source,
        "elapsed_seconds": elapsed, "pid": process_payload.get("pid"), "creation_epoch": process_payload.get("creation_epoch"),
        "cpu_affinity": process_payload.get("cpu_affinity"), "process_times": final_times,
        "metadata_error": metadata_error, "changed_pins": changed, "retry": False,
        "publication_commit": publication_commit, "mirror": dict(mirror),
    }


def _mirror_child_observer(_process_payload: Mapping[str, Any], exit_payload: Mapping[str, Any]) -> None:
    if not os.path.lexists(CHILD_OBSERVER):
        raise LaunchError("child observer absent; it is never fabricated by wrapper")
    _plain_directory(CHILD_OBSERVER, "child observer")
    process_path, exit_path = CHILD_OBSERVER / "process.json", CHILD_OBSERVER / "exit.json"
    if os.path.lexists(process_path) or os.path.lexists(exit_path):
        raise LaunchError("child observer mirror target already exists")
    copy_plain_file_exclusive(OBSERVER / "process.json", process_path, "parent process mirror source")
    write_json_exclusive(exit_path, exit_payload)


def run(plan_path: Path, plan_sha256: str) -> int:
    process_state = configure_parent()  # CPU0/TEN1/CUDA-1 precede all plan and provenance I/O.
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise LaunchError(f"unexpected Python: {sys.executable}")
    plan = load_plan(plan_path, plan_sha256)
    if os.path.lexists(OUTPUT) or os.path.lexists(CHILD_OBSERVER) or os.path.lexists(OBSERVER):
        raise LaunchError("contracted C output or observer root already exists")
    publication_commit = verify_publication(plan_path, plan_sha256, plan)
    all_pins = authoritative_pins(plan)
    all_pins["cli:plan"] = {"path": str(plan_path.resolve()), "bytes": plan_path.stat().st_size,
                            "sha256": plan_sha256}
    before = snapshot_pins(all_pins)
    helper = load_gate_helper()
    initial_resources, initial_disk = resource_gate(helper)  # no runtime root exists before this gate

    OBSERVER.mkdir(parents=False, exist_ok=False)
    write_json_exclusive(OBSERVER / "admission.json", {
        "schema": PLAN_SCHEMA, "status": PLAN_STATUS, "utc": utc_now(), "plan": {"path": str(plan_path), "sha256": plan_sha256},
        "publication_commit": publication_commit, "initial_gate_before_all_runtime_roots": True,
        "resources": initial_resources, "disk_free_bytes": initial_disk, "minimum_bytes": MINIMUM_BYTES,
        "process_state": process_state, "authoritative_pins": before,
    })
    command = child_command(plan)
    write_json_exclusive(OBSERVER / "command.json", {"utc": utc_now(), "command": command, "cwd": str(WEEK)})
    metadata_error: str | None = None
    process_payload: dict[str, Any] = {"pid": None, "creation_epoch": None, "start_utc": None, "command": command,
                                       "cpu_affinity": None, "metadata_error": None, "handle_retained": False,
                                       "wait_pending": False, "record_scope": "PARENT_OBSERVED",
                                       "mirror_provenance": {"target": str(CHILD_OBSERVER), "mode": "exclusive_parent_observed"}}
    child_exit: int | None = None
    final_times: dict[str, float | None] | None = None
    started: float | None = None
    try:
        immediate_resources, immediate_disk = resource_gate(helper)
        root_state = _pre_child_roots()
        if root_state != {"output_lexists": False, "child_observer_lexists": False, "launcher_observer_lexists": True}:
            raise LaunchError(f"immediate pre-child root state: {root_state}")
        write_json_exclusive(OBSERVER / "pre_child_observation.json", {
            "utc": utc_now(), "resources": immediate_resources, "disk_free_bytes": immediate_disk,
            "minimum_bytes": MINIMUM_BYTES, "process_state": process_state, "roots": root_state,
            "child_created": False, "authoritative_pins": snapshot_pins(all_pins),
        })
    except Exception as error:
        changed = verify_closing(before)
        exit_payload = _base_exit(effective_exit=12, child_exit=None, process_payload=process_payload, final_times=None,
                                  metadata_error=f"{type(error).__name__}: {error}", changed=changed, elapsed=None,
                                  source="immediate_prechild_admission_no_process", publication_commit=publication_commit,
                                  mirror={"status": "NOT_ATTEMPTED_NO_CHILD"})
        write_json_exclusive(OBSERVER / "exit.json", exit_payload)
        return 12

    started = time.monotonic()
    process_payload["start_utc"] = utc_now()
    with (OBSERVER / "stdout.log").open("xb") as stdout, (OBSERVER / "stderr.log").open("xb") as stderr:
        try:
            process = subprocess.Popen(command, cwd=str(WEEK), env=os.environ.copy(), stdin=subprocess.DEVNULL,
                                       stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as error:
            changed = verify_closing(before)
            exit_payload = _base_exit(effective_exit=11, child_exit=None, process_payload=process_payload, final_times=None,
                                      metadata_error=f"{type(error).__name__}: {error}", changed=changed,
                                      elapsed=time.monotonic() - started, source="subprocess.Popen_no_child_handle",
                                      publication_commit=publication_commit, mirror={"status": "NOT_ATTEMPTED_NO_CHILD"})
            write_json_exclusive(OBSERVER / "exit.json", exit_payload)
            return 11
        try:
            process_payload["pid"] = process.pid
            process_payload["handle_retained"] = True
            process_payload["wait_pending"] = True
            try:
                retained_handle = int(process._handle)
                initial_times = process_times(retained_handle)
                process_payload["creation_epoch"] = initial_times["creation_epoch"]
                process_payload["cpu_affinity"] = affinity_mask(retained_handle)
                if process_payload["cpu_affinity"] != 1:
                    raise LaunchError(f"child affinity mask {process_payload['cpu_affinity']}, expected 1")
            except Exception as error:
                metadata_error = f"{type(error).__name__}: {error}"
            process_payload["metadata_error"] = metadata_error
            try:
                write_json_exclusive(OBSERVER / "process.json", process_payload)
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else metadata_error + "; " + detail
        finally:
            child_exit = process.wait()  # retained Popen handle is deliberately waited even after metadata error
            try:
                final_times = process_times(int(process._handle))
                if final_times["creation_epoch"] != process_payload["creation_epoch"] or final_times["exit_epoch"] is None:
                    raise LaunchError("retained handle identity/exit-time closure")
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else metadata_error + "; " + detail
                process_payload["metadata_error"] = metadata_error

    changed = verify_closing(before)
    effective_exit = int(child_exit)
    if metadata_error is not None and effective_exit == 0:
        effective_exit = 3
    if changed and effective_exit == 0:
        effective_exit = 4
    mirror: dict[str, Any] = {"status": "PARENT_OBSERVED_MIRRORS_WRITTEN", "target": str(CHILD_OBSERVER),
                              "mode": "exclusive_no_overwrite"}
    exit_payload = _base_exit(effective_exit=effective_exit, child_exit=child_exit, process_payload=process_payload,
                              final_times=final_times, metadata_error=metadata_error, changed=changed,
                              elapsed=time.monotonic() - started, source="subprocess.Popen.wait_retained_handle",
                              publication_commit=publication_commit, mirror=mirror)
    try:
        _mirror_child_observer(process_payload, exit_payload)
    except Exception as error:
        detail = f"{type(error).__name__}: {error}"
        metadata_error = detail if metadata_error is None else metadata_error + "; " + detail
        if effective_exit == 0:
            effective_exit = 5
        exit_payload = _base_exit(effective_exit=effective_exit, child_exit=child_exit, process_payload=process_payload,
                                  final_times=final_times, metadata_error=metadata_error, changed=changed,
                                  elapsed=time.monotonic() - started, source="subprocess.Popen.wait_retained_handle",
                                  publication_commit=publication_commit,
                                  mirror={"status": "FAILED", "error": detail, "partial_output_not_authorized_for_adoption": True})
    write_json_exclusive(OBSERVER / "exit.json", exit_payload)
    return effective_exit


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--plan-json", type=Path, required=True)
    value.add_argument("--plan-sha256", required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return run(args.plan_json, args.plan_sha256)
    except LaunchError as error:
        print(str(error), file=sys.stderr)
        return 10


if __name__ == "__main__":
    raise SystemExit(main())
