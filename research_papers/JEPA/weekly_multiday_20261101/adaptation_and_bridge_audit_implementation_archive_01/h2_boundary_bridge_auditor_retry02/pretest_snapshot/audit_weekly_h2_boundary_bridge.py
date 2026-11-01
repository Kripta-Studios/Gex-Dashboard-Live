from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any


TICKERS = ("SPY", "QQQ", "SPXW")
ENTRY_DATES = ("20260629", "20260630")
SEGMENT_DATES = (*ENTRY_DATES, "20260701", "20260702")
ARTIFACT_ROOT = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
SOURCE_ROOT = Path(r"D:\ThetaData")
H1_ROOT = ARTIFACT_ROOT / "h2_dataset_v2_01"
Q3_ROOT = ARTIFACT_ROOT / "h2_dataset_v2_extension_2026q3_partial_01"
BRIDGE_ROOT = ARTIFACT_ROOT / "h2_boundary_bridge_01"
OUTPUT_DIR = ARTIFACT_ROOT / "h2_boundary_bridge_audit_01"
HERE = Path(__file__).absolute().parent
WRAPPER_PATH = HERE / "build_weekly_h2_boundary_bridge.py"
BUILDER_PATH = HERE / "build_weekly_h2_dataset_v2.py"
BUILDER_SHA256 = "ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945"
HELPER_PATH = HERE / "weekly_multiday_source_pilot.py"
HELPER_SHA256 = "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878"
CONTRACT_PATH = HERE / "H2_JUNE_JULY_BRIDGE_CONTRACT_20261101.md"
CONTRACT_SHA256 = "fe506ec96812ea582f11d0bc23497c34e51e878ae912ccc76fcc8924c30cda55"
H2_CONTRACT_SHA256 = "245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5"
CLOCK_AMENDMENT_SHA256 = "9210c6e50094e5745f80c5e03f577f6bd673263f84d3c3ef764ad76b22ca56eb"
STATUS = "PASS_INDEPENDENT_BOUNDARY_BRIDGE_GIVEN_FROZEN_BUILDERS"


class AuditError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_link_or_reparse_unresolved(path: Path) -> bool:
    current = Path(os.path.abspath(path))
    while True:
        try:
            info = current.lstat()
        except FileNotFoundError:
            pass
        else:
            if stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                return True
        if current.parent == current:
            return False
        current = current.parent


def _guard(path: Path, expected_sha256: str, label: str) -> dict[str, Any]:
    if _is_link_or_reparse_unresolved(path) or not path.is_file():
        raise AuditError(f"{label} path guard failed")
    size, digest = path.stat().st_size, sha256_file(path)
    if digest != expected_sha256:
        raise AuditError(f"{label} SHA-256 mismatch")
    return {"path": str(path), "bytes": size, "sha256": digest}


def _load_module(path: Path, digest: str, name: str) -> Any:
    pin = _guard(path, digest, name)
    spec = importlib.util.spec_from_file_location(f"boundary_audit_{name}", path)
    if spec is None or spec.loader is None:
        raise AuditError(f"cannot import {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if Path(os.path.abspath(module.__file__)) != Path(os.path.abspath(path)):
        raise AuditError(f"{name} imported from unexpected path")
    if path.stat().st_size != pin["bytes"] or sha256_file(path) != digest:
        raise AuditError(f"{name} changed during import")
    return module


def _read_json(path: Path, expected_sha256: str, label: str) -> tuple[Any, dict[str, Any]]:
    pin = _guard(path, expected_sha256, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"invalid {label} JSON") from exc
    if sha256_file(path) != expected_sha256:
        raise AuditError(f"{label} changed during read")
    return value, pin


def _verify_file_map(root: Path, files: dict[str, Any]) -> dict[str, dict[str, Any]]:
    expected = {"candidates.jsonl", "coverage_overlay.json", "inventory.json", "inventory_manifest.json", "unified_calendar.json"}
    if set(files) != expected:
        raise AuditError("bridge manifest file set mismatch")
    pins: dict[str, dict[str, Any]] = {}
    for name in sorted(expected):
        item = files[name]
        if not isinstance(item, dict) or set(item) != {"bytes", "sha256"}:
            raise AuditError("bridge manifest file pin shape mismatch")
        pin = _guard(root / name, item["sha256"], name)
        if pin["bytes"] != item["bytes"]:
            raise AuditError(f"{name} byte count mismatch")
        pins[name] = pin
    return pins


def _validate_calendar(calendar: dict[str, Any], inventory: dict[str, Any]) -> None:
    rows = calendar.get("rows")
    if calendar.get("schema") != "weekly_h2_boundary_unified_calendar_v1" or not isinstance(rows, list) or len(rows) != 2790:
        raise AuditError("unified calendar schema/count mismatch")
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if set(row) != {"ticker", "date", "close_i"}:
            raise AuditError("unified calendar row keys mismatch")
        close_i = row["close_i"]
        if row["ticker"] not in TICKERS or not isinstance(row["date"], str) or isinstance(close_i, bool) or not isinstance(close_i, int) or close_i not in {210, 390}:
            raise AuditError("invalid unified calendar row")
        key = (row["ticker"], row["date"])
        if key in seen:
            raise AuditError("duplicate unified calendar identity")
        seen.add(key)
    if len(seen) != 2790:
        raise AuditError("unified calendar identity count mismatch")
    segment = [row for row in rows if row["date"] in SEGMENT_DATES]
    if len(segment) != 12 or any(row["close_i"] != 390 for row in segment):
        raise AuditError("boundary calendar segment mismatch")
    if inventory.get("segment_calendar") != segment:
        raise AuditError("inventory segment calendar differs")


def _source_state(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(rows) != 6:
        raise AuditError("source inventory must contain six nominals")
    result: list[dict[str, Any]] = []
    present = missing = 0
    physical: set[tuple[int, int]] = set()
    for item in rows:
        path = Path(item.get("path", ""))
        if _is_link_or_reparse_unresolved(path):
            raise AuditError("source nominal path is link/reparse")
        if item.get("status") == "MISSING_SOURCE":
            missing += 1
            if path.exists() or any(item.get(key) is not None for key in ("bytes", "sha256", "rows", "projected_schema", "physical_id", "clock_basis")):
                raise AuditError("missing source metadata mismatch")
        elif item.get("status") == "INVENTORIED":
            present += 1
            pin = _guard(path, item.get("sha256"), "source")
            if pin["bytes"] != item.get("bytes"):
                raise AuditError("source byte count mismatch")
            stat_value = path.stat()
            identity = (int(stat_value.st_dev), int(stat_value.st_ino))
            if item.get("physical_id") != [identity[0], identity[1]] or identity in physical:
                raise AuditError("source physical identity/alias mismatch")
            physical.add(identity)
            result.append(pin)
        else:
            raise AuditError("invalid source inventory status")
    if (present, missing) != (4, 2):
        raise AuditError("source presence pattern mismatch")
    return result


def _validate_plan_and_sources(inventory: dict[str, Any], expected_source_root: Path) -> None:
    plans = inventory.get("coverage_plan")
    if not isinstance(plans, list) or len(plans) != 6:
        raise AuditError("inventory bridge plan count mismatch")
    by_key = {(row.get("ticker"), row.get("entry_date")): row for row in plans}
    expected_keys = {(ticker, day) for ticker in TICKERS for day in ENTRY_DATES}
    if set(by_key) != expected_keys:
        raise AuditError("inventory bridge plan identity mismatch")
    source_root = Path(os.path.abspath(inventory.get("source_root", "")))
    if source_root != Path(os.path.abspath(expected_source_root)):
        raise AuditError("inventory source root differs from admitted root")
    expected_paths: set[str] = set()
    for ticker in TICKERS:
        entry = source_root / "data_options" / ticker / "greeks" / "2026" / "06" / f"{ticker}_20260702_20260629_greeks.parquet"
        exit_path = source_root / "data_options" / ticker / "greeks" / "2026" / "07" / f"{ticker}_20260702_20260701_greeks.parquet"
        expected_paths.update((str(entry), str(exit_path)))
        june29 = by_key[(ticker, "20260629")]
        if (
            june29.get("exit_date"), june29.get("expiration"), june29.get("status"), june29.get("reason"),
            june29.get("entry_path"), june29.get("exit_path"), june29.get("candidate_ids"),
        ) != ("20260701", "20260702", "PLANNED", None, str(entry), str(exit_path), []):
            raise AuditError("June 29 bridge plan semantics mismatch")
        june30 = by_key[(ticker, "20260630")]
        if (
            june30.get("exit_date"), june30.get("expiration"), june30.get("status"), june30.get("reason"),
            june30.get("entry_path"), june30.get("exit_path"), june30.get("candidate_ids"),
        ) != ("20260702", None, "NO_SERIES", "NO_1_TO_8_DTE_SERIES_ALLOWING_H2", None, None, []):
            raise AuditError("June 30 bridge plan semantics mismatch")
    sources = inventory.get("sources")
    if not isinstance(sources, list) or {row.get("path") for row in sources} != expected_paths:
        raise AuditError("exact six nominal source paths mismatch")
    missing = {Path(row["path"]).name for row in sources if row.get("status") == "MISSING_SOURCE"}
    if missing != {"SPY_20260702_20260701_greeks.parquet", "QQQ_20260702_20260701_greeks.parquet"}:
        raise AuditError("exact missing source identities mismatch")


def _validate_authority_pins(inventory: dict[str, Any], h1_root: Path, q3_root: Path) -> None:
    pins = inventory.get("authority_pins")
    expected_paths = {
        "h1_manifest": h1_root / "manifest.json",
        "h1_coverage": h1_root / "coverage.json",
        "h1_candidates": h1_root / "candidates.jsonl",
        "q3_manifest": q3_root / "manifest.json",
        "q3_coverage": q3_root / "coverage.json",
        "q3_candidates": q3_root / "candidates.jsonl",
    }
    if not isinstance(pins, dict) or set(pins) != set(expected_paths):
        raise AuditError("authority pin key set mismatch")
    for label, expected_path in expected_paths.items():
        item = pins[label]
        if not isinstance(item, dict) or Path(os.path.abspath(item.get("path", ""))) != Path(os.path.abspath(expected_path)):
            raise AuditError(f"authority pin path mismatch: {label}")


def _validate_overlay_binding(overlay: dict[str, Any], calendar_sha256: str) -> None:
    if overlay.get("unified_calendar_sha256") != calendar_sha256:
        raise AuditError("overlay unified calendar binding mismatch")


def _validate_manifest_closure(manifest: dict[str, Any], inventory: dict[str, Any], candidate_count: int) -> None:
    expected_flags = {
        "fit_performed": False, "economic_evaluation_performed": False,
        "promotion_approved": False, "originals_modified": False,
        "development_seen": True, "not_oos": True,
    }
    if manifest.get("flags") != expected_flags:
        raise AuditError("bridge manifest flags mismatch")
    if manifest.get("old_candidate_id_count") != 3234 or manifest.get("new_candidate_id_count") != candidate_count:
        raise AuditError("bridge manifest candidate counts mismatch")
    if manifest.get("authority_pins") != inventory.get("authority_pins"):
        raise AuditError("bridge manifest authority pins mismatch")
    if manifest.get("scope") != inventory.get("scope"):
        raise AuditError("bridge manifest scope mismatch")


def _validate_old_ids_digest(inventory: dict[str, Any], authority_ids: set[str]) -> None:
    digest = hashlib.sha256("\n".join(sorted(authority_ids)).encode()).hexdigest()
    if inventory.get("old_candidate_ids_sha256") != digest:
        raise AuditError("old candidate ID digest mismatch")


def _load_candidates(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise AuditError("candidate row is not an object")
                rows.append(value)
    return rows


def _candidate_ids_only(path: Path) -> set[str]:
    result: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line).get("candidate_id")
            if not isinstance(value, str) or value in result:
                raise AuditError("authority candidate payload ID mismatch")
            result.add(value)
    return result


def run_audit(
    bridge_root: Path,
    output_dir: Path,
    bridge_manifest_sha256: str,
    inventory_sha256: str,
    wrapper_sha256: str,
    auditor_sha256: str,
    *,
    expected_source_root: Path = SOURCE_ROOT,
    expected_h1_root: Path = H1_ROOT,
    expected_q3_root: Path = Q3_ROOT,
) -> dict[str, Any]:
    bridge_root, output_dir = Path(os.path.abspath(bridge_root)), Path(os.path.abspath(output_dir))
    if _is_link_or_reparse_unresolved(bridge_root) or not bridge_root.is_dir():
        raise AuditError("bridge root path guard failed")
    if _is_link_or_reparse_unresolved(output_dir) or output_dir.exists():
        raise AuditError("immutable audit output exists or is link/reparse")
    admission = {
        "auditor": _guard(Path(__file__).absolute(), auditor_sha256, "auditor"),
        "wrapper": _guard(WRAPPER_PATH, wrapper_sha256, "wrapper"),
        "contract": _guard(CONTRACT_PATH, CONTRACT_SHA256, "contract"),
        "builder_v2": _guard(BUILDER_PATH, BUILDER_SHA256, "builder_v2"),
        "source_pilot": _guard(HELPER_PATH, HELPER_SHA256, "source_pilot"),
    }
    manifest, manifest_pin = _read_json(bridge_root / "manifest.json", bridge_manifest_sha256, "bridge manifest")
    if manifest.get("schema") != "weekly_h2_boundary_bridge_manifest_v1" or manifest.get("status") != "COMPLETE_WEEKLY_H2_BOUNDARY_BRIDGE_NOT_EVALUATED":
        raise AuditError("bridge manifest schema/status mismatch")
    if manifest.get("split") != "H1_Q3_BOUNDARY_2026_SEEN_DEVELOPMENT":
        raise AuditError("bridge split mismatch")
    implementation = manifest.get("implementation_pins", {})
    required_implementation = {
        "wrapper": wrapper_sha256, "builder_v2": BUILDER_SHA256,
        "source_pilot": HELPER_SHA256, "bridge_contract": CONTRACT_SHA256,
        "h2_contract": H2_CONTRACT_SHA256, "clock_amendment": CLOCK_AMENDMENT_SHA256,
    }
    if set(implementation) != set(required_implementation):
        raise AuditError("bridge implementation pin key set mismatch")
    for label, digest in required_implementation.items():
        item = implementation.get(label)
        if not isinstance(item, dict) or item.get("sha256") != digest:
            raise AuditError(f"bridge implementation pin mismatch: {label}")
    file_pins = _verify_file_map(bridge_root, manifest.get("files", {}))
    if file_pins["inventory.json"]["sha256"] != inventory_sha256:
        raise AuditError("external inventory SHA binding mismatch")
    inventory, _ = _read_json(bridge_root / "inventory.json", inventory_sha256, "inventory")
    if inventory.get("schema") != "weekly_h2_boundary_bridge_inventory_v1" or inventory.get("old_candidate_id_count") != 3234:
        raise AuditError("inventory schema/count mismatch")
    _validate_plan_and_sources(inventory, expected_source_root)
    _validate_authority_pins(inventory, expected_h1_root, expected_q3_root)
    calendar, _ = _read_json(bridge_root / "unified_calendar.json", file_pins["unified_calendar.json"]["sha256"], "unified calendar")
    receipt, _ = _read_json(
        bridge_root / "inventory_manifest.json", file_pins["inventory_manifest.json"]["sha256"], "inventory receipt"
    )
    if receipt != {
        "schema": "weekly_h2_boundary_bridge_inventory_manifest_v1",
        "inventory.json": {"bytes": file_pins["inventory.json"]["bytes"], "sha256": inventory_sha256},
        "unified_calendar.json": {
            "bytes": file_pins["unified_calendar.json"]["bytes"],
            "sha256": file_pins["unified_calendar.json"]["sha256"],
        },
    }:
        raise AuditError("inventory receipt binding mismatch")
    _validate_calendar(calendar, inventory)
    if hashlib.sha256((json.dumps(calendar, indent=2, sort_keys=True) + "\n").encode()).hexdigest() != inventory["unified_calendar"]["sha256"]:
        raise AuditError("unified calendar canonical SHA mismatch")
    sources_before = _source_state(inventory.get("sources", []))
    plans = inventory["coverage_plan"]
    for label, pin in inventory.get("authority_pins", {}).items():
        _guard(Path(pin["path"]), pin["sha256"], f"authority {label}")
    overlay, _ = _read_json(bridge_root / "coverage_overlay.json", file_pins["coverage_overlay.json"]["sha256"], "coverage overlay")
    if overlay.get("schema") != "weekly_h2_boundary_bridge_coverage_overlay_v1" or len(overlay.get("rows", [])) != 6 or len(overlay.get("replacement_keys", [])) != 6:
        raise AuditError("coverage overlay shape mismatch")
    _validate_overlay_binding(overlay, file_pins["unified_calendar.json"]["sha256"])
    replacement = {(row["ticker"], row["entry_date"]) for row in overlay["replacement_keys"]}
    if replacement != {(ticker, day) for ticker in TICKERS for day in ENTRY_DATES}:
        raise AuditError("coverage replacement key set mismatch")
    builder = _load_module(BUILDER_PATH, BUILDER_SHA256, "builder_v2")
    helper = _load_module(HELPER_PATH, HELPER_SHA256, "source_pilot")
    plans = json.loads(json.dumps(plans))
    reproduced, clocks = builder.build_candidates(
        plans, {item["path"]: item for item in inventory["sources"]},
        inventory["unified_calendar"]["sha256"], helper,
    )
    observed = _load_candidates(bridge_root / "candidates.jsonl")
    if observed != reproduced or overlay["rows"] != plans or overlay["clock_files"] != clocks:
        raise AuditError("frozen-function reproduction differs")
    new_ids = [row.get("candidate_id") for row in observed]
    if len(new_ids) != len(set(new_ids)):
        raise AuditError("new candidate ID collision")
    authority_ids: set[str] = set()
    authority_payload_ids: set[str] = set()
    for label in ("h1_coverage", "q3_coverage"):
        pin = inventory["authority_pins"][label]
        coverage, _ = _read_json(Path(pin["path"]), pin["sha256"], label)
        for row in coverage["rows"]:
            authority_ids.update(row["candidate_ids"])
        if label == "h1_coverage":
            boundary = [row for row in coverage["rows"] if row.get("entry_date") in ENTRY_DATES]
            if len(boundary) != 6 or any(row.get("status") != "HORIZON_OUTSIDE_CALENDAR" or row.get("candidate_ids") != [] for row in boundary):
                raise AuditError("original H1 boundary rows mismatch")
    for label in ("h1_candidates", "q3_candidates"):
        authority_payload_ids.update(_candidate_ids_only(Path(inventory["authority_pins"][label]["path"])))
    if authority_ids != authority_payload_ids or len(authority_ids) != 3234 or authority_ids.intersection(new_ids):
        raise AuditError("authority/new candidate reconciliation mismatch")
    _validate_old_ids_digest(inventory, authority_ids)
    _validate_manifest_closure(manifest, inventory, len(observed))
    closing_manifest = _guard(bridge_root / "manifest.json", bridge_manifest_sha256, "closing bridge manifest")
    closing_inventory = _guard(bridge_root / "inventory.json", inventory_sha256, "closing inventory")
    if _source_state(inventory["sources"]) != sources_before:
        raise AuditError("source pins changed during audit")
    for name, pin in file_pins.items():
        _guard(Path(pin["path"]), pin["sha256"], f"closing {name}")
    for label, pin in inventory.get("authority_pins", {}).items():
        _guard(Path(pin["path"]), pin["sha256"], f"closing authority {label}")
    for label, pin in admission.items():
        _guard(Path(pin["path"]), pin["sha256"], f"closing {label}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    result = {
        "schema": "weekly_h2_boundary_bridge_audit_v1", "status": STATUS,
        "inputs": {"producer_manifest": manifest_pin, "inventory": closing_inventory, "wrapper": admission["wrapper"]},
        "counts": {"unified_calendar_rows": 2790, "overlay_rows": 6, "old_candidate_ids": 3234, "new_candidate_ids": len(new_ids), "sources_present": 4, "sources_missing": 2},
        "pins": {**admission, "closing_bridge_manifest": closing_manifest},
        "flags": {"fit_performed": False, "economic_evaluation_performed": False, "outcomes_reinterpreted": False, "promotion_approved": False, "development_seen": True},
        "limitations": ["Reproduces the frozen ec19/ad5 functions; it is not a second independent raw parser or an economic/model audit."],
    }
    try:
        (staging / "audit.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staging.rename(output_dir)
        return result
    except BaseException as exc:
        try:
            (staging / "failure.json").write_text(json.dumps({"status": "FAILED_PARTIAL_PRESERVED", "exception_type": type(exc).__name__, "message": str(exc)}, indent=2) + "\n", encoding="utf-8")
        except BaseException:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the frozen weekly-H2 June/July boundary bridge")
    parser.add_argument("--bridge-root", default=str(BRIDGE_ROOT))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--bridge-manifest-sha256", required=True)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--wrapper-sha256", required=True)
    parser.add_argument("--auditor-sha256", required=True)
    args = parser.parse_args()
    if Path(os.path.abspath(args.bridge_root)) != BRIDGE_ROOT or Path(os.path.abspath(args.output_dir)) != OUTPUT_DIR:
        parser.error("real CLI roots are frozen; fixtures must use the Python API")
    run_audit(
        Path(args.bridge_root), Path(args.output_dir), args.bridge_manifest_sha256.lower(),
        args.inventory_sha256.lower(), args.wrapper_sha256.lower(), args.auditor_sha256.lower(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
