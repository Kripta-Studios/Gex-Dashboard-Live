from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TICKERS = ("SPY", "QQQ", "SPXW")
SEGMENT_DATES = ("20260629", "20260630", "20260701", "20260702")
ENTRY_DATES = SEGMENT_DATES[:2]
SOURCE_ROOT = Path(r"D:\ThetaData")
ARTIFACT_ROOT = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
H1_ROOT = ARTIFACT_ROOT / "h2_dataset_v2_01"
Q3_ROOT = ARTIFACT_ROOT / "h2_dataset_v2_extension_2026q3_partial_01"
OUTPUT_DIR = ARTIFACT_ROOT / "h2_boundary_bridge_01"
H1_MANIFEST_SHA256 = "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8"
Q3_MANIFEST_SHA256 = "b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b"
HERE = Path(__file__).absolute().parent
BUILDER_PATH = HERE / "build_weekly_h2_dataset_v2.py"
BUILDER_SHA256 = "ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945"
HELPER_PATH = HERE / "weekly_multiday_source_pilot.py"
HELPER_SHA256 = "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878"
CONTRACT_PATH = HERE / "H2_JUNE_JULY_BRIDGE_CONTRACT_20261101.md"
CONTRACT_SHA256 = "fe506ec96812ea582f11d0bc23497c34e51e878ae912ccc76fcc8924c30cda55"
H2_CONTRACT_PATH = HERE / "ECONOMIC_H2_CONTRACT.md"
H2_CONTRACT_SHA256 = "245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5"
CLOCK_AMENDMENT_PATH = HERE / "H2_CLOCK_FILTER_V2_AMENDMENT.md"
CLOCK_AMENDMENT_SHA256 = "9210c6e50094e5745f80c5e03f577f6bd673263f84d3c3ef764ad76b22ca56eb"
STATUS = "COMPLETE_WEEKLY_H2_BOUNDARY_BRIDGE_NOT_EVALUATED"


class BridgeError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(_json_bytes(value))


def _guard_file(path: Path, expected_sha256: str, pilot: Any, label: str) -> None:
    if pilot._is_link_or_reparse(path) or not path.is_file():
        raise BridgeError(f"{label} path guard failed")
    if sha256_file(path) != expected_sha256:
        raise BridgeError(f"{label} SHA-256 mismatch")


def _load_module(path: Path, expected_sha256: str, name: str, pilot: Any | None = None) -> Any:
    if pilot is not None and pilot._is_link_or_reparse(path):
        raise BridgeError(f"{name} link/reparse forbidden")
    if not path.is_file() or sha256_file(path) != expected_sha256:
        raise BridgeError(f"{name} pin mismatch")
    before = (path.stat().st_size, expected_sha256)
    spec = importlib.util.spec_from_file_location(f"boundary_bridge_{name}", path)
    if spec is None or spec.loader is None:
        raise BridgeError(f"cannot import {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    loaded = Path(os.path.abspath(module.__file__))
    if loaded != Path(os.path.abspath(path)):
        raise BridgeError(f"{name} imported from unexpected path")
    if path.stat().st_size != before[0] or sha256_file(path) != before[1]:
        raise BridgeError(f"{name} changed during import")
    return module


def _load_frozen() -> tuple[Any, Any]:
    # Bootstrap the helper only after an unresolved-path check. Its own link
    # guard is then used for every authority and source ancestor.
    if HELPER_PATH.is_symlink() or not HELPER_PATH.is_file() or sha256_file(HELPER_PATH) != HELPER_SHA256:
        raise BridgeError("source-pilot helper pin/path guard failed")
    helper = _load_module(HELPER_PATH, HELPER_SHA256, "source_pilot")
    if helper._is_link_or_reparse(HELPER_PATH):
        raise BridgeError("source-pilot helper link/reparse forbidden")
    builder = _load_module(BUILDER_PATH, BUILDER_SHA256, "builder_v2", helper)
    return builder, helper


def _file_pin(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _manifest_payload(root: Path, expected_sha256: str, pilot: Any, label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = root / "manifest.json"
    _guard_file(manifest_path, expected_sha256, pilot, f"{label} manifest")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BridgeError(f"invalid {label} manifest") from exc
    files = manifest.get("files")
    if not isinstance(files, dict) or not {"coverage.json", "candidates.jsonl"}.issubset(files):
        raise BridgeError(f"{label} manifest file pins missing")
    payload: dict[str, Any] = {}
    for name in ("coverage.json", "candidates.jsonl"):
        path = root / name
        item = files[name]
        if not isinstance(item, dict) or not isinstance(item.get("bytes"), int) or not isinstance(item.get("sha256"), str):
            raise BridgeError(f"invalid {label} {name} pin")
        _guard_file(path, item["sha256"], pilot, f"{label} {name}")
        if path.stat().st_size != item["bytes"]:
            raise BridgeError(f"{label} {name} byte count mismatch")
        payload[name] = _file_pin(path)
    coverage_path = root / "coverage.json"
    try:
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BridgeError(f"invalid {label} coverage") from exc
    payload["manifest.json"] = _file_pin(manifest_path)
    payload["coverage"] = coverage
    return manifest, payload


def _calendar_row(row: dict[str, Any]) -> dict[str, Any]:
    ticker, day, close_i = row.get("ticker"), row.get("date"), row.get("close_i")
    if ticker not in TICKERS or not isinstance(day, str) or len(day) != 8 or close_i != 390:
        raise BridgeError("invalid authority calendar row")
    return {"ticker": ticker, "date": day, "close_i": 390}


def _load_authorities(h1_root: Path, q3_root: Path, pilot: Any) -> dict[str, Any]:
    _, h1 = _manifest_payload(h1_root, H1_MANIFEST_SHA256, pilot, "H1")
    _, q3 = _manifest_payload(q3_root, Q3_MANIFEST_SHA256, pilot, "Q3")
    hc, qc = h1["coverage"], q3["coverage"]
    if hc.get("schema") != "weekly_h2_coverage_v2" or qc.get("schema") != "weekly_h2_q3_partial_coverage_v1":
        raise BridgeError("authority coverage schema mismatch")
    hrows, qrows = hc.get("rows"), qc.get("rows")
    if not isinstance(hrows, list) or len(hrows) != 2625 or not isinstance(qrows, list) or len(qrows) != 165:
        raise BridgeError("authority coverage row count mismatch")
    hcal = [_calendar_row(row) for row in hc.get("calendar", [])]
    qcal = [_calendar_row(row) for row in qc.get("calendar", [])]
    if len(hcal) != 2625 or len(qcal) != 165:
        raise BridgeError("authority calendar row count mismatch")
    calendar = sorted(hcal + qcal, key=lambda row: (row["ticker"], row["date"]))
    keys = [(row["ticker"], row["date"]) for row in calendar]
    if len(calendar) != 2790 or len(set(keys)) != 2790:
        raise BridgeError("unified calendar collision or count mismatch")
    for ticker in TICKERS:
        dates = [row["date"] for row in calendar if row["ticker"] == ticker]
        try:
            positions = [dates.index(day) for day in SEGMENT_DATES]
        except ValueError as exc:
            raise BridgeError("unified calendar boundary membership mismatch") from exc
        if len(dates) != 930 or positions != list(range(positions[0], positions[0] + 4)):
            raise BridgeError("unified calendar boundary mismatch")
    boundary = [row for row in hrows if row.get("entry_date") in ENTRY_DATES]
    if len(boundary) != 6 or any(row.get("status") != "HORIZON_OUTSIDE_CALENDAR" or row.get("candidate_ids") != [] for row in boundary):
        raise BridgeError("six original H1 boundary rows mismatch")
    old_ids: list[str] = []
    for row in hrows + qrows:
        ids = row.get("candidate_ids")
        if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
            raise BridgeError("authority candidate_ids malformed")
        old_ids.extend(ids)
    if len(old_ids) != 3234 or len(set(old_ids)) != 3234:
        raise BridgeError("authority candidate ID count/collision mismatch")
    # The line counts bind the candidate payload cardinality without parsing
    # economic fields in the metadata-only phase.
    candidate_lines = 0
    for item in (h1["candidates.jsonl"], q3["candidates.jsonl"]):
        with Path(item["path"]).open("rb") as handle:
            candidate_lines += sum(1 for line in handle if line.strip())
    if candidate_lines != 3234:
        raise BridgeError("authority candidate payload row count mismatch")
    return {
        "unified_calendar": calendar,
        "old_candidate_ids": sorted(old_ids),
        "authority_pins": {
            "h1_manifest": h1["manifest.json"], "h1_coverage": h1["coverage.json"],
            "h1_candidates": h1["candidates.jsonl"], "q3_manifest": q3["manifest.json"],
            "q3_coverage": q3["coverage.json"], "q3_candidates": q3["candidates.jsonl"],
        },
    }


def _augment_inventory(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    physical: set[tuple[int, int]] = set()
    result: list[dict[str, Any]] = []
    for source in rows:
        item = dict(source)
        path = Path(item["path"])
        if item["status"] == "INVENTORIED":
            stat = path.stat()
            identity = (int(stat.st_dev), int(stat.st_ino))
            if identity in physical:
                raise BridgeError("source physical alias detected")
            physical.add(identity)
            names = [field["name"] for field in item["projected_schema"]]
            if "timestamp" in names:
                basis = "NATIVE_STORED_TIMESTAMP"
            elif "underlying_timestamp" in names:
                basis = "UNDERLYING_TIMESTAMP_PROXY"
            else:
                raise BridgeError("source clock column missing")
            item.update(physical_id=[identity[0], identity[1]], clock_basis=basis)
        else:
            item.update(physical_id=None, clock_basis=None)
        result.append(item)
    return result


def _implementation_pins(wrapper_sha256: str, pilot: Any) -> dict[str, Any]:
    pins = {
        "wrapper": {"path": str(Path(__file__).absolute()), "sha256": wrapper_sha256},
        "builder_v2": {"path": str(BUILDER_PATH), "sha256": BUILDER_SHA256},
        "source_pilot": {"path": str(HELPER_PATH), "sha256": HELPER_SHA256},
        "bridge_contract": {"path": str(CONTRACT_PATH), "sha256": CONTRACT_SHA256},
        "h2_contract": {"path": str(H2_CONTRACT_PATH), "sha256": H2_CONTRACT_SHA256},
        "clock_amendment": {"path": str(CLOCK_AMENDMENT_PATH), "sha256": CLOCK_AMENDMENT_SHA256},
    }
    for label, item in pins.items():
        _guard_file(Path(item["path"]), item["sha256"], pilot, label)
    return pins


def prepare_inventory_payload(
    source_root: Path,
    h1_root: Path,
    q3_root: Path,
    wrapper_sha256: str,
) -> tuple[dict[str, Any], Any, Any, dict[str, Any]]:
    builder, pilot = _load_frozen()
    source_root = Path(os.path.abspath(source_root))
    if pilot._is_link_or_reparse(source_root) or not source_root.is_dir():
        raise BridgeError("source root path guard failed")
    implementation_pins = _implementation_pins(wrapper_sha256, pilot)
    authorities = _load_authorities(Path(h1_root), Path(q3_root), pilot)
    sessions = {ticker: list(SEGMENT_DATES) for ticker in TICKERS}
    full_plan, planned_sources = builder.plan_calendar(source_root, sessions, pilot)
    plans = [row for row in full_plan if row["entry_date"] in ENTRY_DATES]
    if len(plans) != 6:
        raise BridgeError("bridge plan must contain exactly six rows")
    for row in plans:
        if row["entry_date"] == "20260629":
            if (row["exit_date"], row["expiration"], row["status"]) != ("20260701", "20260702", "PLANNED"):
                raise BridgeError("June 29 plan mismatch")
        elif (row["exit_date"], row["expiration"], row["status"], row["reason"]) != (
            "20260702", None, "NO_SERIES", "NO_1_TO_8_DTE_SERIES_ALLOWING_H2"
        ):
            raise BridgeError("June 30 plan mismatch")
    expected_paths = {
        str(source_root / "data_options" / ticker / "greeks" / year / month / f"{ticker}_20260702_{day}_greeks.parquet")
        for ticker in TICKERS
        for day, year, month in (("20260629", "2026", "06"), ("20260701", "2026", "07"))
    }
    if set(planned_sources) != expected_paths or len(planned_sources) != 6:
        raise BridgeError("nominal source scope differs from exact six paths")
    _, source_rows = builder.inventory_sources(planned_sources)
    source_rows = _augment_inventory(source_rows)
    if sum(row["status"] == "INVENTORIED" for row in source_rows) != 4 or sum(row["status"] == "MISSING_SOURCE" for row in source_rows) != 2:
        raise BridgeError("source existence pattern differs from four present/two missing")
    missing_names = {Path(row["path"]).name for row in source_rows if row["status"] == "MISSING_SOURCE"}
    if missing_names != {"SPY_20260702_20260701_greeks.parquet", "QQQ_20260702_20260701_greeks.parquet"}:
        raise BridgeError("unexpected missing nominal source")
    unified = {"schema": "weekly_h2_boundary_unified_calendar_v1", "rows": authorities["unified_calendar"]}
    unified_sha = hashlib.sha256(_json_bytes(unified)).hexdigest()
    payload = {
        "schema": "weekly_h2_boundary_bridge_inventory_v1",
        "scope": {"entry_dates": list(ENTRY_DATES), "segment_dates": list(SEGMENT_DATES), "ticker_count": 3, "plan_count": 6, "nominal_source_count": 6},
        "source_root": str(source_root),
        "unified_calendar": {"schema": unified["schema"], "rows": 2790, "sha256": unified_sha},
        "segment_calendar": [row for row in authorities["unified_calendar"] if row["date"] in SEGMENT_DATES],
        "coverage_plan": plans,
        "sources": source_rows,
        "authority_pins": authorities["authority_pins"],
        "old_candidate_ids_sha256": hashlib.sha256("\n".join(authorities["old_candidate_ids"]).encode()).hexdigest(),
        "old_candidate_id_count": 3234,
        "implementation_pins": implementation_pins,
    }
    return payload, builder, pilot, unified


def _validate_receipt(output_dir: Path, inventory_path: Path, inventory_sha256: str, pilot: Any) -> tuple[dict[str, Any], dict[str, Any], Path, dict[str, Any]]:
    if pilot._is_link_or_reparse(inventory_path) or not inventory_path.is_file():
        raise BridgeError("inventory path guard failed")
    inventory_pin = _file_pin(inventory_path)
    if inventory_pin["sha256"] != inventory_sha256:
        raise BridgeError("inventory external SHA binding failed")
    calendar_path = output_dir / "unified_calendar.json"
    if pilot._is_link_or_reparse(calendar_path) or not calendar_path.is_file():
        raise BridgeError("unified calendar path guard failed")
    calendar_pin = _file_pin(calendar_path)
    receipt_path = output_dir / "inventory_manifest.json"
    if pilot._is_link_or_reparse(receipt_path) or not receipt_path.is_file():
        raise BridgeError("inventory receipt path guard failed")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if set(receipt) != {"schema", "inventory.json", "unified_calendar.json"} or receipt.get("schema") != "weekly_h2_boundary_bridge_inventory_manifest_v1":
        raise BridgeError("inventory receipt schema/keys mismatch")
    if receipt["inventory.json"] != {"bytes": inventory_pin["bytes"], "sha256": inventory_pin["sha256"]}:
        raise BridgeError("inventory receipt does not bind inventory")
    if receipt["unified_calendar.json"] != {"bytes": calendar_pin["bytes"], "sha256": calendar_pin["sha256"]}:
        raise BridgeError("inventory receipt does not bind unified calendar")
    return inventory_pin, calendar_pin, receipt_path, _file_pin(receipt_path)


def build_reviewed_inventory(source_root: Path, h1_root: Path, q3_root: Path, output_dir: Path, wrapper_sha256: str) -> dict[str, Any]:
    payload, _, pilot, unified = prepare_inventory_payload(source_root, h1_root, q3_root, wrapper_sha256)
    output_dir = Path(os.path.abspath(output_dir))
    if pilot._is_link_or_reparse(output_dir) or output_dir.exists():
        raise BridgeError("immutable output exists or is link/reparse")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        _write_json(staging / "inventory.json", payload)
        _write_json(staging / "unified_calendar.json", unified)
        receipt = {
            "schema": "weekly_h2_boundary_bridge_inventory_manifest_v1",
            "inventory.json": {k: v for k, v in _file_pin(staging / "inventory.json").items() if k != "path"},
            "unified_calendar.json": {k: v for k, v in _file_pin(staging / "unified_calendar.json").items() if k != "path"},
        }
        _write_json(staging / "inventory_manifest.json", receipt)
        staging.rename(output_dir)
        return receipt
    except BaseException as exc:
        try:
            _write_json(staging / "failure.json", {"status": "FAILED_PARTIAL_PRESERVED", "exception_type": type(exc).__name__, "message": str(exc)})
        except BaseException:
            pass
        raise


def execute_reviewed_bridge(
    source_root: Path,
    h1_root: Path,
    q3_root: Path,
    output_dir: Path,
    wrapper_sha256: str,
    inventory_path: Path,
    inventory_sha256: str,
) -> dict[str, Any]:
    output_dir, inventory_path = Path(os.path.abspath(output_dir)), Path(os.path.abspath(inventory_path))
    current, builder, pilot, unified = prepare_inventory_payload(source_root, h1_root, q3_root, wrapper_sha256)
    if inventory_path != output_dir / "inventory.json":
        raise BridgeError("inventory must belong to immutable output root")
    inventory_pin, calendar_pin, receipt_path, receipt_pin = _validate_receipt(output_dir, inventory_path, inventory_sha256, pilot)
    frozen = json.loads(inventory_path.read_text(encoding="utf-8"))
    if frozen != current or calendar_pin["sha256"] != frozen["unified_calendar"]["sha256"]:
        raise BridgeError("metadata/plan/source inventory differs before first value")
    coverage = json.loads(json.dumps(frozen["coverage_plan"]))
    inventory_by_path = {item["path"]: item for item in frozen["sources"]}
    candidates, clock_files = builder.build_candidates(coverage, inventory_by_path, calendar_pin["sha256"], pilot)
    new_ids = [row.get("candidate_id") for row in candidates]
    if any(not isinstance(value, str) for value in new_ids) or len(new_ids) != len(set(new_ids)):
        raise BridgeError("new candidate IDs malformed or duplicated")
    authorities = _load_authorities(Path(h1_root), Path(q3_root), pilot)
    if set(new_ids) & set(authorities["old_candidate_ids"]):
        raise BridgeError("new candidate ID collides with frozen authority")
    closing, _, closing_pilot, closing_unified = prepare_inventory_payload(source_root, h1_root, q3_root, wrapper_sha256)
    if closing != frozen or closing_unified != unified:
        raise BridgeError("metadata/plan/source inventory changed before publication")
    close_inventory, close_calendar, close_receipt_path, close_receipt = _validate_receipt(output_dir, inventory_path, inventory_sha256, closing_pilot)
    if (close_inventory, close_calendar, close_receipt_path, close_receipt) != (inventory_pin, calendar_pin, receipt_path, receipt_pin):
        raise BridgeError("inventory/calendar/receipt changed before publication")
    for name in ("candidates.jsonl", "coverage_overlay.json", "manifest.json"):
        if (output_dir / name).exists():
            raise BridgeError(f"immutable artifact exists: {name}")
    staging = Path(tempfile.mkdtemp(prefix=".bridge.", dir=output_dir))
    try:
        with (staging / "candidates.jsonl").open("x", encoding="utf-8") as handle:
            for row in candidates:
                handle.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
        overlay = {
            "schema": "weekly_h2_boundary_bridge_coverage_overlay_v1",
            "replacement_keys": [{"ticker": t, "entry_date": d} for t in TICKERS for d in ENTRY_DATES],
            "rows": coverage,
            "clock_files": clock_files,
            "unified_calendar_sha256": calendar_pin["sha256"],
        }
        _write_json(staging / "coverage_overlay.json", overlay)
        files = {
            "candidates.jsonl": _file_pin(staging / "candidates.jsonl"),
            "coverage_overlay.json": _file_pin(staging / "coverage_overlay.json"),
            "inventory.json": inventory_pin,
            "inventory_manifest.json": receipt_pin,
            "unified_calendar.json": calendar_pin,
        }
        manifest = {
            "schema": "weekly_h2_boundary_bridge_manifest_v1", "status": STATUS,
            "scope": frozen["scope"], "files": files, "authority_pins": frozen["authority_pins"],
            "implementation_pins": frozen["implementation_pins"],
            "old_candidate_id_count": 3234, "new_candidate_id_count": len(candidates),
            "flags": {"fit_performed": False, "economic_evaluation_performed": False, "promotion_approved": False, "originals_modified": False},
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(staging / "manifest.json", manifest)
        for name in ("candidates.jsonl", "coverage_overlay.json", "manifest.json"):
            (staging / name).rename(output_dir / name)
        return manifest
    except BaseException as exc:
        try:
            _write_json(staging / "failure.json", {"status": "FAILED_PARTIAL_PRESERVED", "exception_type": type(exc).__name__, "message": str(exc)})
        except BaseException:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the frozen June/July weekly-H2 boundary bridge")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build-reviewed-inventory", action="store_true")
    mode.add_argument("--execute-reviewed-bridge", action="store_true")
    parser.add_argument("--source-root", default=str(SOURCE_ROOT))
    parser.add_argument("--h1-root", default=str(H1_ROOT))
    parser.add_argument("--q3-root", default=str(Q3_ROOT))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--wrapper-sha256", required=True)
    parser.add_argument("--inventory")
    parser.add_argument("--inventory-sha256")
    args = parser.parse_args()
    actual = tuple(Path(os.path.abspath(value)) for value in (args.source_root, args.h1_root, args.q3_root, args.output_dir))
    expected = tuple(Path(os.path.abspath(value)) for value in (SOURCE_ROOT, H1_ROOT, Q3_ROOT, OUTPUT_DIR))
    if actual != expected:
        parser.error("real CLI roots are frozen; fixtures must use the Python API")
    common = (*actual, args.wrapper_sha256.lower())
    if args.build_reviewed_inventory:
        if args.inventory or args.inventory_sha256:
            parser.error("inventory binding belongs only to execute mode")
        build_reviewed_inventory(*common)
    else:
        if not args.inventory or not args.inventory_sha256:
            parser.error("execute mode requires --inventory and --inventory-sha256")
        execute_reviewed_bridge(*common, Path(args.inventory), args.inventory_sha256.lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
