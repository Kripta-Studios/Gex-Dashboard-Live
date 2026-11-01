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

import pyarrow.parquet as pq


TICKERS = ("SPY", "QQQ", "SPXW")
DATES = (
    "20260701", "20260702", "20260706", "20260707", "20260708", "20260709", "20260710",
    "20260713", "20260714", "20260715", "20260716", "20260717", "20260720", "20260721",
    "20260722", "20260723", "20260724", "20260727", "20260728", "20260729", "20260730",
    "20260731", "20260803", "20260804", "20260805", "20260806", "20260807", "20260810",
    "20260811", "20260812", "20260813", "20260814", "20260817", "20260818", "20260819",
    "20260820", "20260821", "20260824", "20260825", "20260826", "20260827", "20260828",
    "20260831", "20260901", "20260902", "20260903", "20260904", "20260908", "20260909",
    "20260910", "20260911", "20260914", "20260915", "20260916", "20260917",
)
SPLIT = "Q3_PARTIAL_2026_SEEN_DEVELOPMENT"
STATUS = "COMPLETE_WEEKLY_H2_Q3_PARTIAL_DATASET_NOT_EVALUATED"
SOURCE_ROOT = Path(r"D:\ThetaData")
ARTIFACT_ROOT = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
CALENDAR_ROOT = ARTIFACT_ROOT / "h2_q3_partial_calendar_01"
CALENDAR_JSON = CALENDAR_ROOT / "calendar.json"
CALENDAR_PARQUET = CALENDAR_ROOT / "calendar.parquet"
CALENDAR_JSON_SHA256 = "ac9bd2569d91e9bd9b0475d6f5e2d5400b2816cc1d1d0d9ec98c69e4dbe2e72b"
CALENDAR_PARQUET_SHA256 = "e16ef041efadc0f6914585540e19e9c04fcb05f1597952137e4f5bcf06de8c78"
CALENDAR_MANIFEST = CALENDAR_ROOT / "manifest.json"
CALENDAR_MANIFEST_SHA256 = "5a530747f2c97704869d87c04d09bba3cc00125f38a8a78454c2d459a2ea502c"
OUTPUT_DIR = ARTIFACT_ROOT / "h2_dataset_v2_extension_2026q3_partial_01"
FROZEN_STATE_ROOT = ARTIFACT_ROOT / "h2_ev_v2_01"
FROZEN_STATE = {
    "model": (FROZEN_STATE_ROOT / "model.json", "68712c7c326d2337a34f8401579ddc52a4dab0e3f505c8c4ff2f1b1d51c03fb4"),
    "transform": (FROZEN_STATE_ROOT / "transform.json", "db4be1e1863ab825117fac6278023fe0b5036ba1454d44243266a5eeb3f9736b"),
    "conditional_means": (FROZEN_STATE_ROOT / "conditional_means.json", "a8dc329233ce431b282c500e27cf91ac91d845cbb6a1fc752cee36026aef3f90"),
    "calibration_grid": (FROZEN_STATE_ROOT / "calibration_grid.json", "0b587bedbabc1cb405c203f11910e5ed10d7ea025e529a98f4ebf2daa1049ed4"),
    "h1_evaluation_manifest": (FROZEN_STATE_ROOT / "manifest.json", "54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96"),
}
HERE = Path(__file__).resolve().parent
BUILDER_PATH = HERE / "build_weekly_h2_dataset_v2.py"
BUILDER_SHA256 = "ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945"
HELPER_PATH = HERE / "weekly_multiday_source_pilot.py"
HELPER_SHA256 = "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878"
H2_CONTRACT_PATH = HERE / "ECONOMIC_H2_CONTRACT.md"
H2_CONTRACT_SHA256 = "245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5"
CLOCK_AMENDMENT_PATH = HERE / "H2_CLOCK_FILTER_V2_AMENDMENT.md"
CLOCK_AMENDMENT_SHA256 = "9210c6e50094e5745f80c5e03f577f6bd673263f84d3c3ef764ad76b22ca56eb"
EXTENSION_CONTRACT_PATH = HERE / "WEEKLY_H2_2026Q3_PARTIAL_EXTENSION_CONTRACT.md"
EXTENSION_CONTRACT_SHA256 = "207e0d3cf103eb6af27193762f568f7397908f4e2e15b47f2e5ff6a56d712b33"


class ExtensionError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_frozen(path: Path, expected_sha256: str):
    path = path.resolve(strict=True)
    if sha256_file(path) != expected_sha256:
        raise ExtensionError("frozen H2 V2 builder pin mismatch")
    spec = importlib.util.spec_from_file_location("weekly_h2_builder_v2_frozen_for_q3", path)
    if spec is None or spec.loader is None:
        raise ExtensionError("cannot load frozen H2 V2 builder")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _assert_pin(path: Path, expected_sha256: str, pilot: Any, label: str) -> None:
    if pilot._is_link_or_reparse(path) or not path.is_file() or sha256_file(path) != expected_sha256:
        raise ExtensionError(f"{label} pin/path guard failed")


def _normalize_calendar_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        ticker = str(row.get("ticker", "")).strip().upper()
        day = str(row.get("date", "")).replace("-", "")
        key = (ticker, day)
        if ticker not in TICKERS or day not in DATES or key in seen:
            raise ExtensionError(f"invalid/duplicate calendar identity: {key}")
        if isinstance(row.get("close_i"), bool) or int(row.get("close_i")) != 390:
            raise ExtensionError(f"non-regular close_i: {key}")
        if set(row) != {"ticker", "date", "close_i"}:
            raise ExtensionError(f"calendar row must have exactly ticker/date/close_i: {key}")
        seen.add(key)
        normalized.append({"ticker": ticker, "date": day, "close_i": 390})
    expected = {(ticker, day) for ticker in TICKERS for day in DATES}
    if seen != expected or len(normalized) != 165:
        raise ExtensionError("calendar must contain exactly 55 sessions x 3 tickers")
    ticker_order = {ticker: index for index, ticker in enumerate(TICKERS)}
    return sorted(normalized, key=lambda row: (ticker_order[row["ticker"]], row["date"]))


def read_calendar_pair(
    json_path: Path,
    json_sha256: str,
    parquet_path: Path,
    parquet_sha256: str,
    pilot: Any,
) -> list[dict[str, Any]]:
    for path, digest, label in (
        (json_path, json_sha256, "calendar JSON"),
        (parquet_path, parquet_sha256, "calendar Parquet"),
    ):
        _assert_pin(path, digest, pilot, label)
    json_payload = json.loads(json_path.read_text(encoding="utf-8"))
    if json_payload.get("schema") != "weekly_h2_q3_partial_calendar_v1":
        raise ExtensionError("calendar JSON schema mismatch")
    if json_payload.get("sessions") != list(DATES):
        raise ExtensionError("calendar JSON sessions differ from frozen 55-session membership")
    if set(json_payload) != {"schema", "sessions", "rows"}:
        raise ExtensionError("calendar JSON must contain exactly schema/sessions/rows")
    json_rows = _normalize_calendar_rows(json_payload.get("rows", []))
    parquet = pq.ParquetFile(parquet_path)
    if not {"ticker", "date", "close_i"}.issubset(parquet.schema_arrow.names):
        raise ExtensionError("calendar Parquet lacks required columns")
    if parquet.schema_arrow.names != ["ticker", "date", "close_i"]:
        raise ExtensionError("calendar Parquet must have exactly ticker/date/close_i")
    columns = ["ticker", "date", "close_i"]
    parquet_rows: list[dict[str, Any]] = []
    for batch in parquet.iter_batches(columns=columns, use_threads=False, batch_size=1024):
        parquet_rows.extend(batch.to_pylist())
    parquet_rows = _normalize_calendar_rows(parquet_rows)
    if json_rows != parquet_rows:
        raise ExtensionError("calendar JSON/Parquet rows differ")
    if sha256_file(json_path) != json_sha256 or sha256_file(parquet_path) != parquet_sha256:
        raise ExtensionError("calendar changed during metadata admission")
    return json_rows


def _pins(builder: Any, calendar_json: Path, calendar_json_sha256: str, calendar_parquet: Path, calendar_parquet_sha256: str) -> dict[str, dict[str, Any]]:
    items = (
        ("wrapper", Path(__file__).resolve(), sha256_file(Path(__file__).resolve())),
        ("builder_v2", BUILDER_PATH, BUILDER_SHA256),
        ("source_pilot", HELPER_PATH, HELPER_SHA256),
        ("h2_contract", H2_CONTRACT_PATH, H2_CONTRACT_SHA256),
        ("clock_amendment", CLOCK_AMENDMENT_PATH, CLOCK_AMENDMENT_SHA256),
        ("extension_contract", EXTENSION_CONTRACT_PATH, EXTENSION_CONTRACT_SHA256),
        ("calendar_json", calendar_json, calendar_json_sha256),
        ("calendar_parquet", calendar_parquet, calendar_parquet_sha256),
    )
    result = {name: {"path": str(path), "sha256": digest} for name, path, digest in items}
    result.update({name: {"path": str(path), "sha256": digest} for name, (path, digest) in FROZEN_STATE.items()})
    if tuple(builder.FEATURE_KEYS) != (
        "ticker_SPY", "ticker_QQQ", "ticker_SPXW", "right_call", "dte", "weekday",
        "spot", "strike", "moneyness", "bid", "ask", "spread_relative", "delta",
        "implied_vol", "gamma", "theta", "vega", "rho",
    ):
        raise ExtensionError("frozen feature order mismatch")
    return result


def prepare_inventory_payload(
    source_root: Path,
    calendar_json: Path,
    calendar_json_sha256: str,
    calendar_parquet: Path,
    calendar_parquet_sha256: str,
) -> tuple[dict[str, Any], Any, Any]:
    builder = _load_frozen(BUILDER_PATH, BUILDER_SHA256)
    pilot = builder.load_pilot(HELPER_PATH, HELPER_SHA256)
    for path, digest, label in (
        (H2_CONTRACT_PATH, H2_CONTRACT_SHA256, "H2 contract"),
        (CLOCK_AMENDMENT_PATH, CLOCK_AMENDMENT_SHA256, "clock amendment"),
        (EXTENSION_CONTRACT_PATH, EXTENSION_CONTRACT_SHA256, "extension contract"),
    ):
        _assert_pin(path, digest, pilot, label)
    source_root = Path(os.path.abspath(source_root))
    if pilot._is_link_or_reparse(source_root):
        raise ExtensionError("source root or ancestor is link/reparse")
    rows = read_calendar_pair(calendar_json, calendar_json_sha256, calendar_parquet, calendar_parquet_sha256, pilot)
    sessions = {ticker: list(DATES) for ticker in TICKERS}
    coverage, planned_sources = builder.plan_calendar(source_root, sessions, pilot)
    if len(coverage) != 165:
        raise ExtensionError("planner did not preserve all 165 ticker-sessions")
    for cover in coverage:
        if cover["entry_date"] in DATES[-2:] and cover["status"] != "HORIZON_OUTSIDE_CALENDAR":
            raise ExtensionError("terminal calendar rows were not retained as horizon-outside")
    _, source_inventory = builder.inventory_sources(planned_sources)
    payload = {
        "schema": "weekly_h2_q3_partial_inventory_v1",
        "split": SPLIT,
        "source_root": str(source_root),
        "calendar": {
            "json_path": str(calendar_json), "json_sha256": calendar_json_sha256,
            "parquet_path": str(calendar_parquet), "parquet_sha256": calendar_parquet_sha256,
            "session_count": 55, "ticker_count": 3, "row_count": 165,
            "first_date": DATES[0], "last_date": DATES[-1], "last_eligible_entry": DATES[-3],
        },
        "calendar_rows": rows,
        "coverage_plan": coverage,
        "sources": source_inventory,
        "implementation_pins": _pins(builder, calendar_json, calendar_json_sha256, calendar_parquet, calendar_parquet_sha256),
    }
    return payload, builder, pilot


def build_reviewed_inventory(
    source_root: Path,
    calendar_json: Path,
    calendar_json_sha256: str,
    calendar_parquet: Path,
    calendar_parquet_sha256: str,
    output_dir: Path,
) -> dict[str, Any]:
    payload, _, pilot = prepare_inventory_payload(source_root, calendar_json, calendar_json_sha256, calendar_parquet, calendar_parquet_sha256)
    output_dir = Path(os.path.abspath(output_dir))
    if pilot._is_link_or_reparse(output_dir) or output_dir.exists():
        raise ExtensionError("immutable output exists or is link/reparse")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        _write_json(staging / "inventory.json", payload)
        inventory = staging / "inventory.json"
        receipt = {
            "schema": "weekly_h2_q3_partial_inventory_manifest_v1",
            "inventory.json": {"bytes": inventory.stat().st_size, "sha256": sha256_file(inventory)},
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


def execute_reviewed_extension(
    source_root: Path,
    calendar_json: Path,
    calendar_json_sha256: str,
    calendar_parquet: Path,
    calendar_parquet_sha256: str,
    output_dir: Path,
    inventory_path: Path,
    inventory_sha256: str,
) -> dict[str, Any]:
    output_dir = Path(os.path.abspath(output_dir))
    inventory_path = Path(os.path.abspath(inventory_path))
    current, builder, pilot = prepare_inventory_payload(source_root, calendar_json, calendar_json_sha256, calendar_parquet, calendar_parquet_sha256)
    if pilot._is_link_or_reparse(output_dir) or pilot._is_link_or_reparse(inventory_path):
        raise ExtensionError("output/inventory or ancestor is link/reparse")
    if inventory_path != output_dir / "inventory.json" or not inventory_path.is_file() or sha256_file(inventory_path) != inventory_sha256:
        raise ExtensionError("frozen inventory binding failed")
    frozen = json.loads(inventory_path.read_text(encoding="utf-8"))
    if frozen != current:
        raise ExtensionError("metadata/plan/source inventory differs before first value")
    coverage = json.loads(json.dumps(frozen["coverage_plan"]))
    inventory_by_path = {item["path"]: item for item in frozen["sources"]}
    candidates, clock_files = builder.build_candidates(coverage, inventory_by_path, calendar_parquet_sha256, pilot)
    if any(row["entry_date"] > "20260915" for row in candidates):
        raise ExtensionError("candidate beyond last eligible partial-Q3 entry")
    closing, _, _ = prepare_inventory_payload(source_root, calendar_json, calendar_json_sha256, calendar_parquet, calendar_parquet_sha256)
    if closing != frozen:
        raise ExtensionError("metadata/plan/source inventory changed before publication")
    for name in ("candidates.jsonl", "coverage.json", "manifest.json"):
        if (output_dir / name).exists():
            raise FileExistsError(f"immutable artifact exists: {name}")
    staging = Path(tempfile.mkdtemp(prefix=".extension.", dir=output_dir))
    try:
        candidates_path = staging / "candidates.jsonl"
        with candidates_path.open("x", encoding="utf-8") as handle:
            for row in candidates:
                handle.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
        coverage_payload = {
            "schema": "weekly_h2_q3_partial_coverage_v1",
            "scope": {"split": SPLIT, "first_date": DATES[0], "last_date": DATES[-1], "last_eligible_entry": DATES[-3]},
            "calendar": frozen["calendar_rows"], "rows": coverage, "clock_files": clock_files,
        }
        _write_json(staging / "coverage.json", coverage_payload)
        inventory_manifest = output_dir / "inventory_manifest.json"
        file_paths = {
            "candidates.jsonl": candidates_path,
            "coverage.json": staging / "coverage.json",
            "inventory.json": inventory_path,
            "inventory_manifest.json": inventory_manifest,
        }
        manifest = {
            "schema": "weekly_h2_q3_partial_dataset_manifest_v1", "status": STATUS, "split": SPLIT,
            "scope": {"first_date": DATES[0], "last_date": DATES[-1], "last_eligible_entry": DATES[-3], "session_count": 55, "ticker_count": 3, "row_count": 165},
            "files": {name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)} for name, path in file_paths.items()},
            "flags": {"no_fit": True, "no_refit": True, "no_recalibration": True, "no_selection": True, "not_oos": True, "not_promotion": True, "not_technical_readiness": True},
            "implementation_pins": frozen["implementation_pins"],
            "source_inventory": {"path": str(inventory_path), "bytes": inventory_path.stat().st_size, "sha256": inventory_sha256},
            "calendar_pin": frozen["calendar"], "created_utc": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(staging / "manifest.json", manifest)
        for name in ("candidates.jsonl", "coverage.json", "manifest.json"):
            (staging / name).rename(output_dir / name)
        return manifest
    except BaseException as exc:
        try:
            _write_json(staging / "failure.json", {"status": "FAILED_PARTIAL_PRESERVED", "exception_type": type(exc).__name__, "message": str(exc)})
        except BaseException:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the frozen weekly H2 partial-Q3 extension")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build-reviewed-inventory", action="store_true")
    mode.add_argument("--execute-reviewed-extension", action="store_true")
    parser.add_argument("--source-root", default=str(SOURCE_ROOT))
    parser.add_argument("--calendar-json", default=str(CALENDAR_JSON))
    parser.add_argument("--calendar-json-sha256", default=CALENDAR_JSON_SHA256)
    parser.add_argument("--calendar-parquet", default=str(CALENDAR_PARQUET))
    parser.add_argument("--calendar-parquet-sha256", default=CALENDAR_PARQUET_SHA256)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--inventory")
    parser.add_argument("--inventory-sha256")
    args = parser.parse_args()
    frozen_paths = ((args.source_root, SOURCE_ROOT), (args.calendar_json, CALENDAR_JSON), (args.calendar_parquet, CALENDAR_PARQUET), (args.output_dir, OUTPUT_DIR))
    if any(Path(os.path.abspath(actual)) != Path(os.path.abspath(expected)) for actual, expected in frozen_paths):
        parser.error("real CLI roots are frozen; fixtures must use the Python API")
    if args.calendar_json_sha256.lower() != CALENDAR_JSON_SHA256 or args.calendar_parquet_sha256.lower() != CALENDAR_PARQUET_SHA256:
        parser.error("real CLI calendar SHA-256 pins are frozen")
    if not CALENDAR_MANIFEST.is_file() or sha256_file(CALENDAR_MANIFEST) != CALENDAR_MANIFEST_SHA256:
        parser.error("real CLI calendar manifest pin mismatch")
    if any(not path.is_file() or sha256_file(path) != digest for path, digest in FROZEN_STATE.values()):
        parser.error("real CLI frozen scoring-state pin mismatch")
    common = (Path(args.source_root), Path(args.calendar_json), args.calendar_json_sha256.lower(), Path(args.calendar_parquet), args.calendar_parquet_sha256.lower(), Path(args.output_dir))
    if args.build_reviewed_inventory:
        if args.inventory or args.inventory_sha256:
            parser.error("inventory binding belongs only to execute mode")
        build_reviewed_inventory(*common)
    else:
        if not args.inventory or not args.inventory_sha256:
            parser.error("execute mode requires --inventory and --inventory-sha256")
        execute_reviewed_extension(*common, Path(args.inventory), args.inventory_sha256.lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
