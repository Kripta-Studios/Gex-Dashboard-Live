"""One-shot metadata wrapper that launches one canonical C auditor after admission.

It imports no C science and opens no arrays itself; the sole child is canonical.
"""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

PYTHON = Path(r"C:\Program Files\Python314\python.exe")
REPO = Path(r"C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live")
WEEK = REPO / "research_papers" / "JEPA" / "weekly_multiday_20261101"
LEVEL = REPO / "research_papers" / "JEPA" / "level_oracle_20261018"
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
BRANCH = "research/multiscale-v1r1-net-usd"
PRODUCER_WRAPPER = WEEK / "launch_weekly_zone_geometry_1030_producer_20261102.py"
PRODUCER_WRAPPER_PIN = (49697, "9a7410432da2a495e8fb161c4ba83fd5f6b1f290798f9f154d61a2ffb11482f5")
PRODUCER = WEEK / "build_weekly_zone_geometry_1030.py"
PRODUCER_PIN = (73030, "ebe7c8984e2e7eb3806193e7c891dbbb0d0449b19e13e0657d0b68cdbe0d1b01")
AUDITOR = WEEK / "audit_weekly_zone_geometry_1030.py"
AUDITOR_PIN = (93663, "f2d17a789bacf813be3b56652eab98fb4388afea8aaa4d691080e563cdc8b01e")
OUTPUT = BASE / "weekly_zone_geometry_1030_audit_01"
CHILD_OBSERVER = BASE / "weekly_zone_geometry_1030_audit_observer_01"
OBSERVER = BASE / "weekly_zone_geometry_1030_audit_launcher_observer_01"
PRODUCER_OUTPUT = BASE / "weekly_zone_geometry_1030_01"
PRODUCER_OBSERVER = BASE / "weekly_zone_geometry_1030_observer_01"
PRODUCER_LAUNCHER_OBSERVER = BASE / "weekly_zone_geometry_1030_launcher_observer_01"
ROOTS = {"output_dir": str(OUTPUT), "observer_dir": str(CHILD_OBSERVER), "launcher_observer_dir": str(OBSERVER)}
PLAN_SCHEMA = "c_geometry_1030_audit_launch_plan_v1"
PLAN_STATUS = "PASS_FINAL_C_GEOMETRY_AUDIT_LAUNCH_PLAN"
FIXTURE_SCHEMA = "c_geometry_1030_audit_launcher_fixture_closure_v1"
FIXTURE_STATUS = "PASS_CLOSED"
PRODUCER_WRAPPER_REVIEW_MARKER = "CLEAR_FINAL_C_PRODUCER_WRAPPER_IMPLEMENTATION"
C_PRODUCER_FINAL_REVIEW_MARKER = "CLEAR_FINAL_C_GEOMETRY_PRODUCER"
BINDING_REVIEW_MARKER = "CLEAR_FINAL_C_GEOMETRY_AUDIT_BINDING"
MANIFEST_KEYS = {"status", "contract", "implementation", "authorities", "authority_pins", "input_count", "inputs_digest", "outputs", "counts", "journal_closure", "resource_policy", "created_at_utc", "no_events", "no_labels", "no_weekly_selection", "no_economics"}
OUTPUT_NAMES = {"geometry_states_1030.parquet", "geometry_levels_1030.parquet", "coverage.json"}
PRODUCER_MEMBER_NAMES = OUTPUT_NAMES | {"manifest.json"}
IMMUTABLE_AUTHORITIES = {
    "contract": {"path": str(WEEK / "C_GEOMETRY_1030_ADMISSION_CONTRACT_20261102.md"), "bytes": 14617, "sha256": "c28572543c1658ab87b1083d60bfdfbdc059c57960c5240c54f98bef5cdd8027"},
    "draft": {"path": str(WEEK / "C_GEOMETRY_1030_OPERATIONAL_DRAFT_20261102.md"), "bytes": 20544, "sha256": "88f76551957e73e37c5dd816b00ec17d035132186df5071be10a5c534368cb3f"},
    "amendment": {"path": str(WEEK / "C_GEOMETRY_PARALLEL_PREPARATION_AMENDMENT_20261102.md"), "bytes": 3761, "sha256": "f32d3bb23a830c9c67197926ab9defa847e5b347422b90fcf1d54d5bdb09b237"},
    "amendment_review": {"path": str(WEEK / "C_GEOMETRY_PARALLEL_PREPARATION_REVIEW_20261102.md"), "bytes": 1212, "sha256": "b3b056d2d447e407902a99d8567b437479ce1ee99e7efc7f62146e47c1fa2580"},
    "windows_note": {"path": str(WEEK / "C_GEOMETRY_WINDOWS_PUBLICATION_FEASIBILITY_20261102.md"), "bytes": 5695, "sha256": "f16d1a1c418fb51b5c5b180719c7a762ba338817a183c6006d472bc34ce13f31"},
    "binding_note": {"path": str(WEEK / "C_GEOMETRY_1030_BINDING_FEASIBILITY_20261102.md"), "bytes": 8652, "sha256": "149fb9f9ddd3a01be24af1fd5f461a9ed7e0abad84d417837f11aff562d2f88a"},
}
IMMUTABLE_IMPLEMENTATIONS = {
    "level_engine.py": {"path": str(LEVEL / "level_engine.py"), "bytes": 27435, "sha256": "70cc5d20990d971d16299fd008ff8e05ac99f99a6a2917a202fcb9a5f413b7c6"},
    "session_level_engine.py": {"path": str(LEVEL / "session_level_engine.py"), "bytes": 21874, "sha256": "f93d3be334a2326dbec5d742e217bce63449e1beaf46b35fa46be83f25548883"},
    "session_clock.py": {"path": str(LEVEL / "session_clock.py"), "bytes": 1046, "sha256": "1e63cf2d314caea14dd8b0b8f025f647d67bf8df58f246613975891a256f51e9"},
    "session_cache.py": {"path": str(LEVEL / "session_cache.py"), "bytes": 2371, "sha256": "6300a7f8e5c6c99101d32d642081f4b8dec170d3c40f2751c27f1642d55466f1"},
    "build_cache.py": {"path": str(LEVEL / "build_cache.py"), "bytes": 18248, "sha256": "985e87dcbd1e73289b58e4576445e47e73a6edea13e5ac73dde3ad629180d69f"},
    "resource_helper": {"path": str(LEVEL / "launch_monthly_test_index_v2_audit_20261024.py"), "bytes": 31463, "sha256": "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"},
    "producer_tests": {"path": str(WEEK / "test_build_weekly_zone_geometry_1030.py"), "bytes": 35739, "sha256": "ec6aebc5c74d8dcc62e3a10a6ee2d4e722b1e6f58f84c4f56436abbd294dbcd5"},
    "auditor_tests": {"path": str(WEEK / "test_audit_weekly_zone_geometry_1030.py"), "bytes": 55343, "sha256": "e010c83e6891cf600b5ee6cee16cc5e2eb9a269b6bbd27270ffc3cdaa0f53848"},
}
REPOSITORY_ROLES = {"launcher", "launcher_tests", "launcher_contract", "fixture_harness", "producer_wrapper", "producer_wrapper_review", "producer", "producer_tests", "auditor", "auditor_tests", "b_final_review", "c_producer_final_review", "audit_binding_review", "c_admission_contract", "c_operational_draft", "c_parallel_amendment", "c_parallel_review", "c_binding_feasibility", "c_windows_feasibility", "level_engine", "session_level_engine", "session_clock", "session_cache", "build_cache", "resource_helper"}


class LaunchError(RuntimeError):
    pass


def pin(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def exact(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise LaunchError(label + ": exact keys")
    return value


def bootstrap_parent() -> dict[str, Any]:
    """Set CPU0/TEN1/CUDA=-1 before any pin I/O or dynamic import."""
    thread_names = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                    "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS", "ARROW_NUM_THREADS", "POLARS_MAX_THREADS",
                    "TBB_NUM_THREADS", "NUMBA_NUM_THREADS")
    for name in thread_names:
        os.environ[name] = "1"
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    if os.name != "nt":
        raise LaunchError("Windows-only launcher")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    kernel.SetProcessAffinityMask.restype = ctypes.c_int
    kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
    kernel.GetProcessAffinityMask.restype = ctypes.c_int
    current = kernel.GetCurrentProcess()
    if not kernel.SetProcessAffinityMask(current, 1):
        raise ctypes.WinError(ctypes.get_last_error())
    process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
    if not kernel.GetProcessAffinityMask(current, ctypes.byref(process_mask), ctypes.byref(system_mask)) or process_mask.value != 1:
        raise LaunchError("CPU0 affinity")
    return {"cpu_affinity_mask": 1, "thread_variables": {name: "1" for name in thread_names}, "cuda_visible_devices": "-1"}


def import_producer_primitives() -> Any:
    if not PRODUCER_WRAPPER.is_file() or pin(PRODUCER_WRAPPER) != {"path": str(PRODUCER_WRAPPER), "bytes": PRODUCER_WRAPPER_PIN[0], "sha256": PRODUCER_WRAPPER_PIN[1]}:
        raise LaunchError("producer wrapper pin")
    spec = importlib.util.spec_from_file_location("_c_audit_parent_primitives", PRODUCER_WRAPPER)
    if spec is None or spec.loader is None:
        raise LaunchError("producer wrapper import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = ("configure_parent", "verify_pin", "read_pinned_json", "assert_no_physical_aliases", "contains_pending", "sha256_file", "load_gate_helper", "resource_gate", "process_times", "affinity_mask", "write_json_exclusive", "verify_closing")
    if any(not callable(getattr(module, name, None)) for name in names):
        raise LaunchError("producer wrapper primitive interface")
    return module


def review(P: Any, value: Any, label: str, marker: str, *digests: str) -> None:
    path, _checked, _identity = P.verify_pin(value, label)
    text = path.read_text(encoding="utf-8")
    if marker not in text or any(digest not in text for digest in digests):
        raise LaunchError(label + ": marker/pin evidence")


def validate_fixture(P: Any, receipt_pin: Any, exit_pin: Any, repository: Mapping[str, Any]) -> None:
    _path, receipt, _identity = P.read_pinned_json(receipt_pin, "audit wrapper fixture receipt")
    exact(receipt, {"schema", "status", "launcher", "tests", "compile_exit_code", "ruff_exit_code", "pytest_exit_code", "pytest_exit"}, "audit wrapper fixture receipt")
    if (receipt["schema"] != FIXTURE_SCHEMA or receipt["status"] != FIXTURE_STATUS or receipt["launcher"] != repository["launcher"] or receipt["tests"] != repository["launcher_tests"] or receipt["compile_exit_code"] != 0 or receipt["ruff_exit_code"] != 0 or receipt["pytest_exit_code"] != 0 or receipt["pytest_exit"] != exit_pin):
        raise LaunchError("audit wrapper fixture receipt closure")
    _path, retained, _identity = P.read_pinned_json(exit_pin, "audit wrapper fixture pytest exit")
    if (set(retained) != {"exit_code", "pid", "creation_epoch", "metadata_error", "changed_pins", "retry"} or retained["exit_code"] != 0 or type(retained["pid"]) is not int or retained["pid"] <= 0 or type(retained["creation_epoch"]) not in {int, float} or not math.isfinite(retained["creation_epoch"]) or retained["metadata_error"] is not None or retained["changed_pins"] != [] or retained["retry"] is not False):
        raise LaunchError("audit wrapper fixture retained pytest exit")


def read_journal(P: Any, value: Any) -> None:
    path, _checked, _identity = P.verify_pin(value, "producer C journal")
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except (UnicodeError, json.JSONDecodeError) as error:
        raise LaunchError("producer C journal JSONL") from error
    required = {"seq", "utc", "kind", "identity", "phase", "paths", "gate", "details"}
    if not rows or [row.get("seq") for row in rows] != list(range(len(rows))):
        raise LaunchError("producer C journal sequence")
    paired: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != required or row.get("phase") not in {"START", "COMPLETE"}:
            raise LaunchError("producer C journal error/envelope")
        paired.setdefault((row["kind"], row["identity"]), []).append(row["phase"])
    if any(phases != ["START", "COMPLETE"] for phases in paired.values()) or rows[-1]["kind"] != "PUBLISH_ROOT" or rows[-1]["phase"] != "COMPLETE":
        raise LaunchError("producer C journal paired terminal closure")


def validate_retained_closure(exit_value: Any, process_value: Any) -> None:
    required_exit = {"exit_code", "geometry_child_exit_code", "pid", "creation_epoch", "changed_pins", "metadata_error", "retry"}
    if not isinstance(exit_value, Mapping) or not required_exit.issubset(exit_value) or not isinstance(process_value, Mapping):
        raise LaunchError("producer C retained closure schema")
    if (exit_value["exit_code"] != 0 or exit_value["geometry_child_exit_code"] != 0 or exit_value["changed_pins"] != [] or
            exit_value["metadata_error"] is not None or exit_value["retry"] is not False or type(exit_value["pid"]) is not int or
            exit_value["pid"] <= 0 or type(process_value.get("pid")) is not int or
            type(exit_value["creation_epoch"]) not in {int, float} or not math.isfinite(exit_value["creation_epoch"]) or
            type(process_value.get("creation_epoch")) not in {int, float} or not math.isfinite(process_value["creation_epoch"]) or
            (exit_value["pid"], exit_value["creation_epoch"]) != (process_value.get("pid"), process_value.get("creation_epoch"))):
        raise LaunchError("producer C retained closure outcome/identity")


def validate_producer_closure(P: Any, closure: Any, repository: Mapping[str, Any], plan: Mapping[str, Any], binding: Mapping[str, Any]) -> None:
    exact(closure, {"manifest", "journal", "wrapper_exit", "wrapper_process", "mirror_exit", "mirror_process", "review", "outputs"}, "producer C closure")
    outputs = closure["outputs"]
    if not isinstance(outputs, Mapping) or set(outputs) != OUTPUT_NAMES:
        raise LaunchError("producer C output pins")
    values = {key: closure[key] for key in closure if key != "outputs"} | {"output:" + key: value for key, value in outputs.items()}
    records = [(name, *P.verify_pin(value, "producer C " + name)) for name, value in values.items()]
    P.assert_no_physical_aliases(records)
    producer_root = Path(binding["producer_output_root"])
    producer_observer = Path(binding["producer_observer_root"])
    if (not producer_root.is_dir() or producer_root.is_symlink() or {path.name for path in producer_root.iterdir()} != PRODUCER_MEMBER_NAMES or
            not producer_observer.is_dir() or producer_observer.is_symlink()):
        raise LaunchError("producer C designated roots/member set")
    _path, exit_value, _identity = P.read_pinned_json(closure["wrapper_exit"], "producer C wrapper exit")
    _path, process_value, _identity = P.read_pinned_json(closure["wrapper_process"], "producer C wrapper process")
    validate_retained_closure(exit_value, process_value)
    locations = {name: path for name, path, _checked, _identity in records}
    if (locations["manifest"] != producer_root / "manifest.json" or
            any(locations["output:" + name] != producer_root / name for name in OUTPUT_NAMES) or
            locations["journal"].parent != producer_observer or locations["mirror_exit"].parent != producer_observer or
            locations["mirror_process"].parent != producer_observer or locations["wrapper_exit"].parent != PRODUCER_LAUNCHER_OBSERVER or
            locations["wrapper_process"].parent != PRODUCER_LAUNCHER_OBSERVER):
        raise LaunchError("producer C designated closure paths")
    if (binding["producer_manifest"] != closure["manifest"] or binding["producer_journal"] != closure["journal"] or
            binding["producer_exit"] != closure["mirror_exit"] or binding["producer_process"] != closure["mirror_process"]):
        raise LaunchError("producer C binding closure paths")
    if locations["wrapper_exit"].read_bytes() != locations["mirror_exit"].read_bytes() or locations["wrapper_process"].read_bytes() != locations["mirror_process"].read_bytes():
        raise LaunchError("producer C byte-exact parent mirrors")
    _path, manifest, _identity = P.read_pinned_json(closure["manifest"], "producer C manifest")
    if not isinstance(manifest, Mapping) or set(manifest) != MANIFEST_KEYS or manifest.get("status") != "C_GEOMETRY_1030_CLOSED":
        raise LaunchError("producer C manifest schema/status")
    expected_contract = {Path(value["path"]).name: value for value in binding["authority_pins"].values()}
    if manifest["implementation"] != repository["producer"] or manifest["authorities"] != {"b_bundle": plan["b_final"]["bundle"], "b_review": plan["b_final"]["review"]} or manifest["contract"] != expected_contract:
        raise LaunchError("producer C manifest implementation/B crosspins")
    expected_engines = {"level_engine.py", "session_level_engine.py", "session_clock.py", "session_cache.py", "build_cache.py"}
    expected_authorities = {"calendar": binding["calendar"], "cache_admission": binding["cache_admission"], "engines": {name: binding["implementation_pins"][name] for name in expected_engines}}
    if manifest["authority_pins"] != expected_authorities or any(manifest[key] is not True for key in ("no_events", "no_labels", "no_weekly_selection", "no_economics")):
        raise LaunchError("producer C manifest authority/scope")
    if set(manifest["outputs"]) != OUTPUT_NAMES:
        raise LaunchError("producer C manifest output names")
    counts = manifest["counts"]
    if (not isinstance(counts, Mapping) or type(counts.get("level_rows")) is not int or counts["level_rows"] < 0 or
            any(type(value) is not int or value < 0 for value in counts.values())):
        raise LaunchError("producer C manifest level count")
    expected_rows: dict[str, int | None] = {"geometry_states_1030.parquet": 2790, "geometry_levels_1030.parquet": counts["level_rows"], "coverage.json": None}
    for name, record in manifest["outputs"].items():
        if (not isinstance(record, Mapping) or set(record) != {"path", "bytes", "sha256", "rows"} or
                record["rows"] != expected_rows[name] or (name != "coverage.json" and type(record["rows"]) is not int) or
                (name == "coverage.json" and record["rows"] is not None) or type(record["bytes"]) is not int or record["bytes"] < 0 or
                {key: record[key] for key in ("path", "bytes", "sha256")} != outputs[name]):
            raise LaunchError("producer C manifest output crosspin")
    read_journal(P, closure["journal"])
    if closure["review"] != repository["c_producer_final_review"]:
        raise LaunchError("producer C final review crosspin")
    review(P, closure["review"], "producer C final review", C_PRODUCER_FINAL_REVIEW_MARKER, closure["manifest"]["sha256"], repository["producer"]["sha256"])


def validate_binding(P: Any, binding_pin: Any, plan: Mapping[str, Any], bundle: Mapping[str, Any]) -> dict[str, Any]:
    path, _checked, _identity = P.verify_pin(binding_pin, "audit runtime binding")
    try:
        binding = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise LaunchError("audit runtime binding JSON") from error
    required = {"schema", "status", "producer_output_root", "producer_observer_root", "producer_manifest", "producer_journal", "producer_exit", "producer_process", "b_final_bundle", "b_final_review", "calendar", "cache_admission", "authority_pins", "implementation_pins", "audit_output_root", "audit_observer_root"}
    if not isinstance(binding, Mapping) or set(binding) != required or binding["schema"] != "c_geometry_1030_runtime_binding_v1" or binding["status"] != "BOUND_REAL_C_GEOMETRY_1030" or P.contains_pending(binding):
        raise LaunchError("audit runtime binding schema/status")
    repository = plan["repository_pins"]
    direct = {"producer": "producer", "producer_tests": "producer_tests", "resource_helper": "resource_helper", "auditor": "auditor", "auditor_tests": "auditor_tests"}
    implementation = binding["implementation_pins"]
    authorities = binding["authority_pins"]
    expected_implementation = {"level_engine.py", "session_level_engine.py", "session_clock.py", "session_cache.py", "build_cache.py", "producer", "producer_tests", "resource_helper", "auditor", "auditor_tests"}
    expected_authorities = {"contract", "draft", "amendment", "amendment_review", "windows_note", "binding_note"}
    if not isinstance(implementation, Mapping) or set(implementation) != expected_implementation or not isinstance(authorities, Mapping) or set(authorities) != expected_authorities:
        raise LaunchError("audit runtime binding role maps")
    for name in ("producer_manifest", "producer_journal", "producer_exit", "producer_process", "b_final_bundle", "b_final_review", "calendar", "cache_admission"):
        P.verify_pin(binding[name], "audit binding " + name)
    for name, value in {**implementation, **authorities}.items():
        P.verify_pin(value, "audit binding map " + name)
    for name, role in direct.items():
        if implementation[name] != repository[role]:
            raise LaunchError("audit binding implementation crosspin " + name)
    contracts = {"contract": "c_admission_contract", "draft": "c_operational_draft", "amendment": "c_parallel_amendment", "amendment_review": "c_parallel_review", "binding_note": "c_binding_feasibility", "windows_note": "c_windows_feasibility"}
    for name, role in contracts.items():
        if authorities[name] != repository[role]:
            raise LaunchError("audit binding authority crosspin " + name)
    engines = {"level_engine.py": "level_engine", "session_level_engine.py": "session_level_engine", "session_clock.py": "session_clock", "session_cache.py": "session_cache", "build_cache.py": "build_cache"}
    for name, role in engines.items():
        if implementation[name] != repository[role]:
            raise LaunchError("audit binding engine crosspin " + name)
    immutable_implementation = {**IMMUTABLE_IMPLEMENTATIONS, "producer": {"path": str(PRODUCER), "bytes": PRODUCER_PIN[0], "sha256": PRODUCER_PIN[1]}, "auditor": {"path": str(AUDITOR), "bytes": AUDITOR_PIN[0], "sha256": AUDITOR_PIN[1]}}
    if authorities != IMMUTABLE_AUTHORITIES or implementation != immutable_implementation:
        raise LaunchError("audit binding immutable authority/implementation pins")
    if binding["calendar"] != bundle["calendar"]["raw_file_pin"] or binding["cache_admission"] != bundle["producer"]["outputs"]["cache_admission.jsonl"]:
        raise LaunchError("audit binding B calendar/cache crosspins")
    if binding["b_final_bundle"] != plan["b_final"]["bundle"] or binding["b_final_review"] != plan["b_final"]["review"] or binding["producer_output_root"] != str(PRODUCER_OUTPUT) or binding["producer_observer_root"] != str(PRODUCER_OBSERVER) or binding["audit_output_root"] != ROOTS["output_dir"] or binding["audit_observer_root"] != ROOTS["observer_dir"]:
        raise LaunchError("audit binding B/root crosspins")
    return binding


def load_plan(P: Any, path: Path, digest: str) -> dict[str, Any]:
    if len(digest) != 64 or P.sha256_file(path) != digest:
        raise LaunchError("plan CLI hash")
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LaunchError("plan JSON") from error
    exact(plan, {"schema", "status", "branch", "data_scope", "repository_pins", "b_final", "audit_binding", "producer_closure", "formal_fixture", "runtime_roots"}, "audit plan")
    if plan["schema"] != PLAN_SCHEMA or plan["status"] != PLAN_STATUS or plan["branch"] != BRANCH or plan["data_scope"] != "SEEN_DEVELOPMENT" or P.contains_pending(plan) or plan["runtime_roots"] != ROOTS:
        raise LaunchError("audit plan identity/PENDING/roots")
    repository = plan["repository_pins"]
    if not isinstance(repository, Mapping) or set(repository) != REPOSITORY_ROLES:
        raise LaunchError("audit plan repository roles")
    records = [(role, *P.verify_pin(value, "audit plan " + role)) for role, value in repository.items()]
    P.assert_no_physical_aliases(records)
    if repository["launcher"] != pin(Path(__file__).resolve()) or repository["producer"] != pin(PRODUCER) or repository["auditor"] != pin(AUDITOR) or repository["producer_wrapper"] != pin(PRODUCER_WRAPPER) or repository["producer"]["bytes"] != PRODUCER_PIN[0] or repository["producer"]["sha256"] != PRODUCER_PIN[1] or repository["auditor"]["bytes"] != AUDITOR_PIN[0] or repository["auditor"]["sha256"] != AUDITOR_PIN[1] or repository["producer_wrapper"]["bytes"] != PRODUCER_WRAPPER_PIN[0] or repository["producer_wrapper"]["sha256"] != PRODUCER_WRAPPER_PIN[1]:
        raise LaunchError("audit plan self/canonical pins")
    exact(plan["b_final"], {"bundle", "review"}, "audit plan B final")
    binding_part = exact(plan["audit_binding"], {"binding", "review"}, "audit plan binding")
    if plan["b_final"]["review"] != repository["b_final_review"] or binding_part["review"] != repository["audit_binding_review"]:
        raise LaunchError("audit plan review crosspins")
    try:
        _path, bundle, _identity = P.read_pinned_json(plan["b_final"]["bundle"], "final B bundle")
        validated_bundle = P.validate_final_b_bundle(plan["b_final"]["bundle"])
    except Exception as error:
        raise LaunchError("final B metadata closure validator: " + str(error)) from error
    if bundle != validated_bundle:
        raise LaunchError("final B bundle validator disagreement")
    binding = validate_binding(P, binding_part["binding"], plan, bundle)
    review(P, plan["b_final"]["review"], "final B review", "CLEAR_FINAL_B_CLOSURE", plan["b_final"]["bundle"]["sha256"])
    validate_producer_closure(P, plan["producer_closure"], repository, plan, binding)
    for key, name in {"producer_manifest": "manifest", "producer_journal": "journal", "producer_exit": "mirror_exit", "producer_process": "mirror_process"}.items():
        if binding[key] != plan["producer_closure"][name]:
            raise LaunchError("audit binding producer closure crosspin " + key)
    exact(plan["formal_fixture"], {"receipt", "pytest_exit"}, "audit plan fixture")
    validate_fixture(P, plan["formal_fixture"]["receipt"], plan["formal_fixture"]["pytest_exit"], repository)
    review(P, binding_part["review"], "audit binding review", BINDING_REVIEW_MARKER, binding_part["binding"]["sha256"], repository["launcher"]["sha256"], repository["launcher_tests"]["sha256"], repository["launcher_contract"]["sha256"])
    review(P, repository["producer_wrapper_review"], "producer wrapper review", PRODUCER_WRAPPER_REVIEW_MARKER, repository["producer_wrapper"]["sha256"])
    plan["_bundle"], plan["_binding"] = bundle, binding
    return plan


def verify_publication(P: Any, plan_path: Path, plan_sha: str, plan: Mapping[str, Any]) -> str:
    if not plan_path.is_relative_to(REPO):
        raise LaunchError("plan publication path")
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    remote = subprocess.check_output(["git", "ls-remote", "origin", f"refs/heads/{BRANCH}"], cwd=REPO, text=True).split()
    if branch != BRANCH or not remote or remote[0] != commit or P.sha256_file(plan_path) != plan_sha:
        raise LaunchError("local/remote publication")
    publication_members = {"plan": pin(plan_path), **plan["repository_pins"], "b_bundle": plan["b_final"]["bundle"],
                           "audit_binding": plan["audit_binding"]["binding"], "fixture_receipt_projection": plan["formal_fixture"]["receipt"],
                           "fixture_exit_projection": plan["formal_fixture"]["pytest_exit"]}
    for name, value in publication_members.items():
        source, _checked, _identity = P.verify_pin(value, "published " + name)
        if not source.is_relative_to(REPO) or subprocess.check_output(["git", "show", f"{commit}:{source.relative_to(REPO).as_posix()}"], cwd=REPO) != source.read_bytes():
            raise LaunchError("published byte mismatch " + name)
    return commit


def authoritative_pins(P: Any, plan: Mapping[str, Any], plan_path: Path) -> dict[str, dict[str, Any]]:
    values = {"repo:" + name: value for name, value in plan["repository_pins"].items()} | {"plan": pin(plan_path), "b_bundle": plan["b_final"]["bundle"], "audit_binding": plan["audit_binding"]["binding"], "fixture_receipt": plan["formal_fixture"]["receipt"], "fixture_exit": plan["formal_fixture"]["pytest_exit"]}
    bundle = plan["_bundle"]
    values |= {"b_manifest": bundle["producer"]["manifest"], **{"b_output:" + name: value for name, value in bundle["producer"]["outputs"].items()}, **{"b_observer:" + name: value for name, value in bundle["producer"]["observer"].items()}, **{"b_audit:" + name: value for name, value in bundle["auditor"].items()}, **{"b_authority:" + name: value for name, value in bundle["authority_inputs"].items()}, "b_calendar": bundle["calendar"]["raw_file_pin"]}
    closure = plan["producer_closure"]
    values |= {"c_" + name: value for name, value in closure.items() if name != "outputs"} | {"c_output:" + name: value for name, value in closure["outputs"].items()}
    snapshots: dict[str, dict[str, Any]] = {}
    records = []
    for role, value in values.items():
        source, checked, identity = P.verify_pin(value, "authoritative " + role)
        observed = {"bytes": checked["bytes"], "sha256": checked["sha256"]}
        if str(source) in snapshots and snapshots[str(source)] != observed:
            raise LaunchError("authoritative pin conflict")
        snapshots[str(source)] = observed
        records.append((role, source, checked, identity))
    P.assert_no_physical_aliases(records)
    return snapshots


def command(plan: Mapping[str, Any]) -> list[str]:
    binding = plan["audit_binding"]["binding"]
    return [str(PYTHON), "-X", "utf8", "-u", str(AUDITOR), "--binding-json", binding["path"], "--binding-sha256", binding["sha256"], "--output-dir", ROOTS["output_dir"], "--observer-dir", ROOTS["observer_dir"]]


def failure(P: Any, code: int, stage: str, detail: str, before: Mapping[str, Mapping[str, Any]], process: Mapping[str, Any] | None = None, child_exit: int | None = None) -> int:
    P.write_json_exclusive(OBSERVER / "exit.json", {"exit_code": code, "geometry_audit_child_exit_code": child_exit, "pid": (process or {}).get("pid"), "creation_epoch": (process or {}).get("creation_epoch"), "metadata_error": detail, "changed_pins": P.verify_closing(before), "retry": False, "stage": stage, "failure_closure": True})
    return code


def run(plan_path: Path, plan_sha: str) -> int:
    state = bootstrap_parent()
    P = import_producer_primitives()
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise LaunchError("unexpected Python")
    plan = load_plan(P, plan_path, plan_sha)
    if any(os.path.lexists(path) for path in (OUTPUT, CHILD_OBSERVER, OBSERVER)):
        raise LaunchError("exclusive audit roots already exist")
    commit = verify_publication(P, plan_path, plan_sha, plan)
    before = authoritative_pins(P, plan, plan_path)
    helper = P.load_gate_helper()
    try:
        initial_resources, initial_disk = P.resource_gate(helper)
    except Exception as error:
        if any(os.path.lexists(path) for path in (OUTPUT, CHILD_OBSERVER, OBSERVER)):
            raise LaunchError("initial gate changed exclusive roots") from error
        return 12
    OBSERVER.mkdir(parents=False, exist_ok=False)
    P.write_json_exclusive(OBSERVER / "bootstrap.json", {"state": state, "commit": commit, "authoritative_pins": before, "C_output_and_child_observer_absent": True})
    P.write_json_exclusive(OBSERVER / "admission.json", {"resources": initial_resources, "disk_free_bytes": initial_disk, "command": command(plan), "initial_gate_before_C_runtime_roots": True})
    try:
        resources, disk = P.resource_gate(helper)
        roots = {"output_lexists": os.path.lexists(OUTPUT), "child_observer_lexists": os.path.lexists(CHILD_OBSERVER), "launcher_observer_lexists": os.path.lexists(OBSERVER)}
        if roots != {"output_lexists": False, "child_observer_lexists": False, "launcher_observer_lexists": True}:
            raise LaunchError("immediate prechild roots")
        P.write_json_exclusive(OBSERVER / "prechild.json", {"resources": resources, "disk_free_bytes": disk, "roots": roots, "authoritative_pins": before})
    except Exception as error:
        return failure(P, 12, "prechild_gate", f"{type(error).__name__}: {error}", before)
    record: dict[str, Any] = {"pid": None, "creation_epoch": None, "cpu_affinity": None, "handle_retained": False, "wait_pending": False, "record_scope": "PARENT_OBSERVED", "start_utc": None}
    started = time.monotonic()
    with (OBSERVER / "stdout.log").open("xb") as stdout, (OBSERVER / "stderr.log").open("xb") as stderr:
        try:
            process = subprocess.Popen(command(plan), cwd=str(WEEK), env=os.environ.copy(), stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as error:
            return failure(P, 11, "popen", f"{type(error).__name__}: {error}", before, record)
        metadata_error: str | None = None
        child_exit: int | None = None
        try:
            record.update({"pid": process.pid, "handle_retained": True, "wait_pending": True, "start_utc": dt.datetime.now(dt.timezone.utc).isoformat()})
            try:
                handle = int(process._handle)
                initial = P.process_times(handle)
                record["creation_epoch"] = initial["creation_epoch"]
                record["cpu_affinity"] = P.affinity_mask(handle)
                if record["cpu_affinity"] != 1:
                    raise LaunchError("child CPU affinity")
            except Exception as error:
                metadata_error = f"{type(error).__name__}: {error}"
            record["metadata_error"] = metadata_error
            try:
                P.write_json_exclusive(OBSERVER / "process.json", record)
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else metadata_error + "; " + detail
        finally:
            child_exit = process.wait()
            try:
                final = P.process_times(int(process._handle))
                if final["creation_epoch"] != record["creation_epoch"] or final["exit_epoch"] is None:
                    raise LaunchError("retained child identity/exit")
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else metadata_error + "; " + detail
    changed = P.verify_closing(before)
    effective = int(child_exit)
    if metadata_error is not None and effective == 0:
        effective = 3
    if changed and effective == 0:
        effective = 4
    P.write_json_exclusive(OBSERVER / "exit.json", {"exit_code": effective, "geometry_audit_child_exit_code": child_exit, "pid": record["pid"], "creation_epoch": record["creation_epoch"], "cpu_affinity": record["cpu_affinity"], "start_utc": record["start_utc"], "process_times": final if "final" in locals() else None, "metadata_error": metadata_error, "changed_pins": changed, "retry": False, "elapsed_seconds": time.monotonic() - started, "failure_closure": effective != 0})
    return effective


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        return run(args.plan_json, args.plan_sha256)
    except LaunchError as error:
        print(str(error), file=sys.stderr)
        return 10


if __name__ == "__main__":
    raise SystemExit(main())
