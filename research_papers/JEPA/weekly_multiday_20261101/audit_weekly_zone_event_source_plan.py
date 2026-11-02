"""Independently audit a closed weekly zone-event metadata source plan."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Mapping, Sequence


TICKERS = ("SPY", "QQQ", "SPXW")
TICKER_INDEX = {value: index for index, value in enumerate(TICKERS)}
ROLES = ("ENTRY_DAY", "INTERMEDIATE_DAY", "H2_DAY")
STATUS = "SOURCE_PLAN_NOT_VALUE_ADMISSION"
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
PRODUCER = BASE / "weekly_zone_event_source_plan_01"
OUTPUT = BASE / "weekly_zone_event_source_plan_audit_01"
SOURCE_ROOT = Path(r"D:\ThetaData")
HERE = Path(__file__).resolve().parent
AUDITOR_TESTS = HERE / "test_audit_weekly_zone_event_source_plan.py"
CONTRACT = HERE / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_CONTRACT_20261102.md"
CONTRACT_SHA256 = "c1891e794cab794d5f6570f99d838a888663a48b8ccededd4d96d27a63173d65"
REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

AUTHORITIES = {
    "h2_dataset_v2_01/inventory.json": "099dcf065a62705cbd88f2c1b90b2e4a9b99ff4d994ad703634101920c934b12",
    "h2_dataset_v2_01/inventory_manifest.json": "c417e67f3499522d4ebd4a21bf28d1cba8ce249ef2d38a1352001216714bb899",
    "h2_dataset_v2_01/manifest.json": "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8",
    "h2_dataset_v2_extension_2026q3_partial_01/inventory.json": "f633d0ee192f28650698a4033ee7f6d2dc00dad07aa38239c40e9e2b5092ea5c",
    "h2_dataset_v2_extension_2026q3_partial_01/inventory_manifest.json": "5b39e0796599fa72b5d74d029885a24fd57fada207f12989576737aa46d75b2f",
    "h2_dataset_v2_extension_2026q3_partial_01/manifest.json": "b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b",
    "h2_boundary_bridge_01/inventory.json": "599ca400fecae12ce4098187a45af3ee0cf8c1b070e060d8c84e422ce92c6161",
    "h2_boundary_bridge_01/inventory_manifest.json": "0a7a5fab0f932d23fdf9a3140027f99eb85ccd958b79ef55152c53ab5ced70f2",
    "h2_boundary_bridge_01/manifest.json": "9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86",
    "h2_boundary_bridge_01/unified_calendar.json": "be622bb24aca35448594743dfeb5236e6b2d08a4410109b20302891f8c1fa7d6",
}

EXPECTED_FLAGS = {
    "raw_values_read": False,
    "raw_files_hashed": False,
    "parquet_footers_read": False,
    "arrays_read": False,
    "outcomes_read": False,
    "fit_performed": False,
    "inference_performed": False,
    "replay_performed": False,
    "selected_policy": None,
    "technical_ready": False,
    "promotion_approved": False,
}
OBSERVER_FILES = (
    "resource_observation.json", "admission.json", "process.json", "stdout.log", "stderr.log",
)


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def digest_shape(value: Any) -> str:
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "SHA256 shape")
    return value


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def canonical_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(absolute(path))))


def linked(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & REPARSE)


def guard_compact(path: Path, roots: Sequence[Path]) -> Path:
    path = absolute(path)
    permitted = [absolute(root) for root in roots]
    require(any(path == root or path.is_relative_to(root) for root in permitted), "compact input outside roots")
    current = path
    stop = next(root for root in permitted if path == root or path.is_relative_to(root))
    while True:
        info = current.lstat()
        require(not linked(info), f"compact link/reparse forbidden: {current}")
        if current == stop:
            break
        current = current.parent
    require(path.is_file(), f"compact input not regular: {path}")
    return path


def load_json(path: Path, roots: Sequence[Path]) -> Any:
    return json.loads(guard_compact(path, roots).read_text(encoding="utf-8"))


def load_jsonl(path: Path, roots: Sequence[Path]) -> list[dict[str, Any]]:
    value = []
    for line_number, line in enumerate(guard_compact(path, roots).read_text(encoding="utf-8").splitlines(), 1):
        require(bool(line.strip()), f"blank JSONL line {line_number}")
        row = json.loads(line)
        require(isinstance(row, dict), f"JSONL row is not object {line_number}")
        value.append(row)
    return value


def pin(path: Path) -> dict[str, Any]:
    return {"path": str(absolute(path)), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def validate_pin(value: Any, expected: Mapping[str, Any], label: str, rows: int | None = None) -> None:
    require(isinstance(value, dict), f"{label} pin object")
    require(value.get("bytes") == expected["bytes"] and value.get("sha256") == expected["sha256"],
            f"{label} crosspin")
    if rows is not None:
        require(value.get("rows") == rows, f"{label} rows")


def authority_bundle(base: Path = BASE) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    documents: dict[str, Any] = {}
    pins: dict[str, dict[str, Any]] = {}
    for relative, expected_sha in AUTHORITIES.items():
        path = guard_compact(base / relative, (base,))
        actual = pin(path)
        require(actual["sha256"] == expected_sha, f"authority hash: {relative}")
        documents[relative] = json.loads(path.read_text(encoding="utf-8"))
        pins[relative] = actual
    return documents, pins


def validate_authority_crosspins(d: Mapping[str, Any], p: Mapping[str, Mapping[str, Any]]) -> None:
    h1i, h1r, h1m = (d[f"h2_dataset_v2_01/{name}"] for name in
                       ("inventory.json", "inventory_manifest.json", "manifest.json"))
    q3i, q3r, q3m = (d[f"h2_dataset_v2_extension_2026q3_partial_01/{name}"] for name in
                       ("inventory.json", "inventory_manifest.json", "manifest.json"))
    bri, brr, brm = (d[f"h2_boundary_bridge_01/{name}"] for name in
                       ("inventory.json", "inventory_manifest.json", "manifest.json"))
    uni = d["h2_boundary_bridge_01/unified_calendar.json"]
    require(h1i.get("schema") == "weekly_h2_source_inventory_v2_clock_filter", "H1 schema")
    require(h1r.get("schema") == "weekly_h2_inventory_manifest_v1", "H1 receipt schema")
    require(h1m.get("schema") == "weekly_h2_dataset_manifest_v2" and
            h1m.get("status") == "COMPLETE_WEEKLY_H2_DATASET_NOT_EVALUATED", "H1 manifest")
    require(q3i.get("schema") == "weekly_h2_q3_partial_inventory_v1", "Q3 schema")
    require(q3r.get("schema") == "weekly_h2_q3_partial_inventory_manifest_v1", "Q3 receipt schema")
    require(q3m.get("schema") == "weekly_h2_q3_partial_dataset_manifest_v1" and
            q3m.get("status") == "COMPLETE_WEEKLY_H2_Q3_PARTIAL_DATASET_NOT_EVALUATED", "Q3 manifest")
    require(bri.get("schema") == "weekly_h2_boundary_bridge_inventory_v1", "bridge schema")
    require(brr.get("schema") == "weekly_h2_boundary_bridge_inventory_manifest_v1", "bridge receipt schema")
    require(brm.get("schema") == "weekly_h2_boundary_bridge_manifest_v1" and
            brm.get("status") == "COMPLETE_WEEKLY_H2_BOUNDARY_BRIDGE_NOT_EVALUATED", "bridge manifest")
    require(uni.get("schema") == "weekly_h2_boundary_unified_calendar_v1", "calendar schema")
    validate_pin(h1r.get("inventory.json"), p["h2_dataset_v2_01/inventory.json"], "H1 receipt")
    validate_pin(h1m.get("files", {}).get("inventory.json"), p["h2_dataset_v2_01/inventory.json"],
                 "H1 manifest inventory", 2619)
    require(h1m.get("inventory_bound_sha256") == p["h2_dataset_v2_01/inventory.json"]["sha256"],
            "H1 bound hash")
    validate_pin(q3r.get("inventory.json"), p["h2_dataset_v2_extension_2026q3_partial_01/inventory.json"],
                 "Q3 receipt")
    validate_pin(q3m.get("files", {}).get("inventory.json"),
                 p["h2_dataset_v2_extension_2026q3_partial_01/inventory.json"], "Q3 manifest inventory")
    validate_pin(q3m.get("files", {}).get("inventory_manifest.json"),
                 p["h2_dataset_v2_extension_2026q3_partial_01/inventory_manifest.json"], "Q3 manifest receipt")
    validate_pin(q3m.get("source_inventory"), p["h2_dataset_v2_extension_2026q3_partial_01/inventory.json"],
                 "Q3 source inventory")
    validate_pin(brr.get("inventory.json"), p["h2_boundary_bridge_01/inventory.json"], "bridge receipt")
    validate_pin(brr.get("unified_calendar.json"), p["h2_boundary_bridge_01/unified_calendar.json"],
                 "bridge calendar receipt")
    for name in ("inventory.json", "inventory_manifest.json", "unified_calendar.json"):
        validate_pin(brm.get("files", {}).get(name), p[f"h2_boundary_bridge_01/{name}"], f"bridge {name}")
    require(bri.get("unified_calendar") == {
        "rows": 2790, "schema": "weekly_h2_boundary_unified_calendar_v1",
        "sha256": p["h2_boundary_bridge_01/unified_calendar.json"]["sha256"]}, "bridge calendar binding")
    require(h1m.get("flags") == {"economic_evaluation_performed": False, "fit_performed": False,
                                  "production_modified": False, "promotion_approved": False}, "H1 flags")
    require(q3m.get("flags") == {"no_fit": True, "no_recalibration": True, "no_refit": True,
                                  "no_selection": True, "not_oos": True, "not_promotion": True,
                                  "not_technical_readiness": True}, "Q3 flags")
    require(brm.get("flags") == {"development_seen": True, "economic_evaluation_performed": False,
                                  "fit_performed": False, "not_oos": True, "originals_modified": False,
                                  "promotion_approved": False}, "bridge flags")
    require(bri.get("scope") == {"entry_dates": ["20260629", "20260630"],
                                  "nominal_source_count": 6, "plan_count": 6,
                                  "segment_dates": ["20260629", "20260630", "20260701", "20260702"],
                                  "ticker_count": 3}, "bridge scope")
    authority = bri.get("authority_pins", {})
    require(authority == brm.get("authority_pins"), "bridge authority pins disagree")
    validate_pin(authority.get("h1_manifest"), p["h2_dataset_v2_01/manifest.json"], "bridge H1 manifest")
    validate_pin(authority.get("q3_manifest"), p["h2_dataset_v2_extension_2026q3_partial_01/manifest.json"],
                 "bridge Q3 manifest")
    for prefix, manifest in (("h1", h1m), ("q3", q3m)):
        validate_pin(authority.get(prefix + "_coverage"), manifest["files"]["coverage.json"],
                     f"bridge {prefix} coverage")
        validate_pin(authority.get(prefix + "_candidates"), manifest["files"]["candidates.jsonl"],
                     f"bridge {prefix} candidates")


def parse_day(value: Any, label: str) -> datetime:
    require(isinstance(value, str) and re.fullmatch(r"\d{8}", value), f"{label} date shape")
    try:
        return datetime.strptime(value, "%Y%m%d")
    except ValueError as error:
        raise AuditError(f"{label} invalid date") from error


def nominal_path(ticker: str, expiration: str, trade_date: str) -> Path:
    require(ticker in TICKERS, "ticker")
    parse_day(expiration, "expiration")
    parse_day(trade_date, "trade")
    return absolute(SOURCE_ROOT / "data_options" / ticker / "greeks" / trade_date[:4] / trade_date[4:6] /
                    f"{ticker}_{expiration}_{trade_date}_greeks.parquet")


def validate_nominal_path_text(value: Any) -> Path:
    require(isinstance(value, str), "nominal source path text")
    lexical = Path(value)
    require(lexical.is_absolute() and ".." not in lexical.parts, "nominal source lexical traversal")
    options = SOURCE_ROOT / "data_options"
    try:
        relative = lexical.relative_to(options)
    except ValueError as error:
        raise AuditError("nominal source outside options root") from error
    require(len(relative.parts) == 5 and relative.parts[1] == "greeks", "nominal source template")
    ticker, _greeks, year, month, filename = relative.parts
    match = re.fullmatch(r"(SPY|QQQ|SPXW)_(\d{8})_(\d{8})_greeks\.parquet", filename)
    require(match is not None and ticker == match.group(1), "nominal source filename")
    expiration, trade_date = match.group(2), match.group(3)
    require((year, month) == (trade_date[:4], trade_date[4:6]), "nominal source date directories")
    expected = nominal_path(ticker, expiration, trade_date)
    require(canonical_key(lexical) == canonical_key(expected), "nominal source canonical identity")
    return expected


def validate_coverage(row: Any, key: tuple[str, str]) -> None:
    require(isinstance(row, dict) and set(row) == {
        "candidate_ids", "entry_date", "entry_path", "exit_date", "exit_path", "expiration",
        "reason", "status", "ticker"}, "coverage schema")
    require((row["ticker"], row["entry_date"]) == key, "coverage identity")
    require(row["status"] in ("PLANNED", "NO_SERIES", "HORIZON_OUTSIDE_CALENDAR"), "coverage status")
    require(row["candidate_ids"] == [], "candidate IDs must remain empty metadata")


def planned_upstream_paths(upstream: Mapping[str, Any], ticker: str, expiration: str,
                           entry_date: str, h2_date: str) -> tuple[str, str]:
    expected_entry = nominal_path(ticker, expiration, entry_date)
    expected_h2 = nominal_path(ticker, expiration, h2_date)
    actual_entry = validate_nominal_path_text(upstream.get("entry_path"))
    actual_h2 = validate_nominal_path_text(upstream.get("exit_path"))
    require(canonical_key(actual_entry) == canonical_key(expected_entry), "upstream entry path altered")
    require(canonical_key(actual_h2) == canonical_key(expected_h2), "upstream H2 path altered")
    return str(expected_entry), str(expected_h2)


def reconstruct_entries(documents: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[tuple[str, str], int]]:
    h1 = documents["h2_dataset_v2_01/inventory.json"]
    q3 = documents["h2_dataset_v2_extension_2026q3_partial_01/inventory.json"]
    bridge = documents["h2_boundary_bridge_01/inventory.json"]
    unified = documents["h2_boundary_bridge_01/unified_calendar.json"]
    require(all(isinstance(document.get("source_root"), str) and
                canonical_key(Path(document["source_root"])) == canonical_key(SOURCE_ROOT)
                for document in (h1, q3, bridge)), "source roots")
    calendar: dict[tuple[str, str], int] = {}
    rows = unified.get("rows")
    require(isinstance(rows, list) and len(rows) == 2790, "unified calendar count")
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"ticker", "date", "close_i"}, "calendar row schema")
        key = (row["ticker"], row["date"])
        require(key not in calendar and row["ticker"] in TICKERS and row["close_i"] in (210, 390),
                "calendar identity/value")
        parse_day(row["date"], "calendar")
        calendar[key] = row["close_i"]
    dates = sorted({day for _ticker, day in calendar})
    require(len(dates) == 930 and dates[0] == "20230103" and dates[-1] == "20260917", "calendar bounds")
    require(sum(value == 210 for value in calendar.values()) == 24, "short rows")
    require(all(all((ticker, day) in calendar for ticker in TICKERS) and
                len({calendar[(ticker, day)] for ticker in TICKERS}) == 1 for day in dates), "common calendar")
    segment: dict[tuple[str, str], int] = {}
    for name, segment_rows, count in (("H1", h1.get("calendar_rows"), 2625),
                                      ("Q3", q3.get("calendar_rows"), 165)):
        require(isinstance(segment_rows, list) and len(segment_rows) == count, f"{name} calendar count")
        for row in segment_rows:
            require(isinstance(row, dict) and set(row) in ({"ticker", "date", "close_i"},
                                                            {"ticker", "date", "close_i", "status"}),
                    f"{name} calendar schema")
            key = (row["ticker"], row["date"])
            require(key in calendar and key not in segment and row["close_i"] == calendar[key],
                    f"{name} calendar partition")
            segment[key] = row["close_i"]
    require(set(segment) == set(calendar), "segment partition")
    require(all(calendar[(row["ticker"], row["date"])] == 390 for row in q3["calendar_rows"]), "Q3 short")
    base: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
    for authority, coverage in (("H1", h1.get("coverage_plan")), ("Q3", q3.get("coverage_plan"))):
        require(isinstance(coverage, list), f"{authority} coverage")
        for row in coverage:
            key = (row.get("ticker"), row.get("entry_date"))
            validate_coverage(row, key)
            require(key in calendar and key not in base, "coverage duplicate/outside")
            base[key] = (authority, row)
    require(set(base) == set(calendar), "coverage span")
    overlay_keys = {(ticker, day) for day in ("20260629", "20260630") for ticker in TICKERS}
    overlay: dict[tuple[str, str], dict[str, Any]] = {}
    bridge_rows = bridge.get("coverage_plan")
    require(isinstance(bridge_rows, list) and len(bridge_rows) == 6, "bridge count")
    for row in bridge_rows:
        key = (row.get("ticker"), row.get("entry_date"))
        validate_coverage(row, key)
        require(key in overlay_keys and key not in overlay and base[key][1]["status"] == "HORIZON_OUTSIDE_CALENDAR",
                "bridge overlay identity")
        overlay[key] = row
    require(set(overlay) == overlay_keys, "bridge overlay completeness")
    output: list[dict[str, Any]] = []
    for date_index, day in enumerate(dates):
        sessions = {"D": day, "D1": dates[date_index + 1] if date_index + 1 < len(dates) else None,
                    "D2": dates[date_index + 2] if date_index + 2 < len(dates) else None}
        for ticker in TICKERS:
            key = (ticker, day)
            authority, upstream = base[key]
            if key in overlay:
                authority, upstream = "BRIDGE", overlay[key]
            status = upstream["status"]
            expiration = entry_path = h2_path = None
            if status == "PLANNED":
                expiration = upstream["expiration"]
                require(sessions["D2"] is not None and upstream["exit_date"] == sessions["D2"] and
                        upstream["reason"] is None and isinstance(expiration, str), "planned H2")
                dte = (parse_day(expiration, "expiry") - parse_day(day, "entry")).days
                require(1 <= dte <= 8 and parse_day(sessions["D2"], "H2") < parse_day(expiration, "expiry"),
                        "expiry constraints")
                entry_path, h2_path = planned_upstream_paths(
                    upstream, ticker, expiration, day, sessions["D2"])
            elif status == "NO_SERIES":
                require(sessions["D2"] is not None and upstream["exit_date"] == sessions["D2"] and
                        all(upstream[name] is None for name in ("expiration", "entry_path", "exit_path")) and
                        isinstance(upstream["reason"], str), "NO_SERIES shape")
            else:
                require(sessions["D2"] is None and all(upstream[name] is None for name in
                        ("exit_date", "expiration", "entry_path", "exit_path")) and
                        upstream["reason"] == "NO_OFFICIAL_H2", "horizon shape")
            output.append({"plan_id": f"{ticker}:{day}", "ticker": ticker, "date": day,
                           "close_i": calendar[key], "status": status, "reason": upstream["reason"],
                           "expiration": expiration, "session_dates": sessions, "entry_path": entry_path,
                           "h2_path": h2_path, "source_authority": authority})
    require(Counter(row["status"] for row in output) == Counter(
        {"PLANNED": 1620, "NO_SERIES": 1164, "HORIZON_OUTSIDE_CALENDAR": 6}), "status counts")
    return output, calendar


def validate_historical_source(row: Any, authority: str) -> tuple[str, dict[str, Any]]:
    require(isinstance(row, dict), "historical source object")
    keys = {"bytes", "path", "projected_schema", "rows", "sha256", "status"}
    if authority == "BRIDGE":
        keys |= {"clock_basis", "physical_id"}
    require(set(row) == keys and row["status"] in ("INVENTORIED", "MISSING_SOURCE"), "historical schema")
    historical_path = validate_nominal_path_text(row.get("path"))
    if row["status"] == "INVENTORIED":
        require(isinstance(row["bytes"], int) and row["bytes"] >= 0 and
                isinstance(row["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]),
                "inventoried binding")
    else:
        require(row["bytes"] is None and row["sha256"] is None, "missing binding")
    binding = {"authority": authority, "status": row["status"], "bytes": row["bytes"],
               "sha256": row["sha256"], "expected_upstream_pin_not_currently_rehashed": True}
    return canonical_key(historical_path), binding


def reconstruct_sources(entries: Sequence[Mapping[str, Any]], calendar: Mapping[tuple[str, str], int],
                        documents: Mapping[str, Any]) -> list[dict[str, Any]]:
    bindings: dict[str, list[dict[str, Any]]] = {}
    for authority, inventory_name in (("H1", "h2_dataset_v2_01/inventory.json"),
                                      ("Q3", "h2_dataset_v2_extension_2026q3_partial_01/inventory.json"),
                                      ("BRIDGE", "h2_boundary_bridge_01/inventory.json")):
        rows = documents[inventory_name].get("sources")
        expected_count = {"H1": 2619, "Q3": 156, "BRIDGE": 6}[authority]
        require(isinstance(rows, list) and len(rows) == expected_count, f"{authority} historical count")
        for row in rows:
            key, value = validate_historical_source(row, authority)
            if key in bindings:
                triples = {(item["status"], item["bytes"], item["sha256"]) for item in bindings[key]}
                require((value["status"], value["bytes"], value["sha256"]) in triples,
                        "conflicting normalized historical binding")
            bindings.setdefault(key, []).append(value)
    sources: dict[str, dict[str, Any]] = {}
    references = 0
    for entry in entries:
        if entry["status"] != "PLANNED":
            continue
        for role, trade_date in zip(ROLES, (entry["session_dates"]["D"], entry["session_dates"]["D1"],
                                            entry["session_dates"]["D2"]), strict=True):
            path = nominal_path(entry["ticker"], entry["expiration"], trade_date)
            key = canonical_key(path)
            reference = {"plan_id": entry["plan_id"], "ticker": entry["ticker"],
                         "entry_date": entry["date"], "expiration": entry["expiration"], "role": role,
                         "trade_date": trade_date, "close_i": calendar[(entry["ticker"], trade_date)]}
            sources.setdefault(key, {"path": str(path), "ticker": entry["ticker"],
                                      "expiration": entry["expiration"], "trade_date": trade_date,
                                      "references": [], "expected_upstream_bindings":
                                          [dict(item) for item in bindings.get(key, ())],
                                      "new_without_upstream_binding": key not in bindings})["references"].append(reference)
            references += 1
    require(references == 4860, "reference count")
    for source in sources.values():
        source["references"].sort(key=lambda row: (row["entry_date"], TICKER_INDEX[row["ticker"]],
                                                    ROLES.index(row["role"])))
    return sorted(sources.values(), key=lambda row: os.path.normcase(row["path"]))


def market_observation(path: Path, lstat_adapter: Any = os.lstat) -> dict[str, Any]:
    path = validate_nominal_path_text(str(path))
    options = absolute(SOURCE_ROOT / "data_options")
    require(path.is_relative_to(options), "market path outside options")
    parts = path.relative_to(options).parts
    require(len(parts) == 5 and parts[1] == "greeks", "market path template")
    match = re.fullmatch(r"(SPY|QQQ|SPXW)_(\d{8})_(\d{8})_greeks\.parquet", parts[4])
    require(match is not None and match.group(1) == parts[0] and parts[2:4] ==
            (match.group(3)[:4], match.group(3)[4:6]), "market filename")
    ancestor_chain: list[Path] = []
    ancestor = absolute(SOURCE_ROOT)
    while True:
        ancestor_chain.append(ancestor)
        if ancestor.parent == ancestor:
            break
        ancestor = ancestor.parent
    ancestor_chain.reverse()
    ancestor_chain.append(options)
    for ancestor in ancestor_chain:
        try:
            info = lstat_adapter(ancestor)
        except FileNotFoundError:
            if ancestor == options:
                return {"exists": False, "bytes": None, "mtime_ns": None, "physical_id": None}
            raise AuditError(f"market ancestor is absent: {ancestor}") from None
        require(not linked(info), f"market link/reparse forbidden: {ancestor}")
        require(stat.S_ISDIR(info.st_mode), f"market root is not a directory: {ancestor}")
    current = options
    target: os.stat_result | None = None
    missing = False
    for part in path.relative_to(options).parts:
        current /= part
        if missing:
            continue
        try:
            info = lstat_adapter(current)
        except FileNotFoundError:
            missing = True
            continue
        require(not linked(info), f"market link/reparse: {current}")
        require(stat.S_ISREG(info.st_mode) if current == path else stat.S_ISDIR(info.st_mode),
                f"market path type: {current}")
        if current == path:
            target = info
    if target is None:
        return {"exists": False, "bytes": None, "mtime_ns": None, "physical_id": None}
    return {"exists": True, "bytes": target.st_size, "mtime_ns": target.st_mtime_ns,
            "physical_id": [target.st_dev, target.st_ino]}


def discrepancy(bindings: Sequence[Mapping[str, Any]], observation: Mapping[str, Any]) -> list[str]:
    values: set[str] = set()
    for binding in bindings:
        if binding["status"] == "INVENTORIED" and not observation["exists"]:
            values.add("EXPECTED_PRESENT_NOW_MISSING")
        elif binding["status"] == "MISSING_SOURCE" and observation["exists"]:
            values.add("EXPECTED_MISSING_NOW_PRESENT")
        elif (binding["status"] == "INVENTORIED" and observation["exists"] and
              binding["bytes"] != observation["bytes"]):
            values.add("CURRENT_BYTES_DIFFER_FROM_EXPECTED_UPSTREAM")
    return sorted(values)


def attach_observations(sources: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    physical: dict[tuple[int, int], str] = {}
    for source in sources:
        observation = market_observation(Path(source["path"]))
        if observation["exists"]:
            identity = tuple(observation["physical_id"])
            require(identity not in physical or canonical_key(Path(physical[identity])) == canonical_key(Path(source["path"])),
                    "physical alias")
            physical[identity] = source["path"]
        value = dict(source)
        value["observation"] = observation
        value["metadata_discrepancies"] = discrepancy(source["expected_upstream_bindings"], observation)
        output.append(value)
    return output


def expected_summary(entries: Sequence[Mapping[str, Any]], sources: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    references = [reference for source in sources for reference in source["references"]]
    discrepancy_counts = Counter(code for source in sources for code in source["metadata_discrepancies"])
    return {"schema": "weekly_zone_event_source_plan_summary_v1", "status": STATUS,
            "entry_plans": {"total": len(entries),
                            "by_status": dict(sorted(Counter(row["status"] for row in entries).items())),
                            "by_ticker": dict(sorted(Counter(row["ticker"] for row in entries).items())),
                            "by_year": dict(sorted(Counter(row["date"][:4] for row in entries).items()))},
            "references": {"total": len(references),
                           "by_role": dict(sorted(Counter(row["role"] for row in references).items())),
                           "by_ticker": dict(sorted(Counter(row["ticker"] for row in references).items())),
                           "by_year": dict(sorted(Counter(row["trade_date"][:4] for row in references).items()))},
            "sources": {"unique": len(sources), "present": sum(row["observation"]["exists"] for row in sources),
                        "absent": sum(not row["observation"]["exists"] for row in sources),
                        "present_unique_bytes": sum(row["observation"]["bytes"] or 0 for row in sources),
                        "new_without_upstream_binding": sum(row["new_without_upstream_binding"] for row in sources),
                        "with_upstream_binding": sum(not row["new_without_upstream_binding"] for row in sources),
                        "with_metadata_discrepancy": sum(bool(row["metadata_discrepancies"]) for row in sources),
                        "discrepancies": dict(sorted(discrepancy_counts.items()))},
            "flags": {"metadata_only": True, **EXPECTED_FLAGS}}


def validate_producer_manifest(manifest: Any, authority_pins: Mapping[str, Mapping[str, Any]],
                               producer_builder_sha: str, producer_tests_sha: str) -> dict[str, Any]:
    require(isinstance(manifest, dict) and manifest.get("schema") == "weekly_zone_event_source_plan_manifest_v1"
            and manifest.get("status") == STATUS, "producer manifest schema/status")
    require(manifest.get("flags") == EXPECTED_FLAGS, "producer manifest flags")
    require(manifest.get("inputs") == authority_pins, "producer manifest input pins")
    implementations = manifest.get("implementation_pins")
    require(isinstance(implementations, dict) and set(implementations) == {"builder", "tests", "contract"},
            "producer implementation pins")
    expected = {"builder": producer_builder_sha, "tests": producer_tests_sha, "contract": CONTRACT_SHA256}
    exact_paths = {"builder": HERE / "build_weekly_zone_event_source_plan.py",
                   "tests": HERE / "test_build_weekly_zone_event_source_plan.py",
                   "contract": CONTRACT}
    for name, expected_sha in expected.items():
        validate_implementation_pin(implementations[name], exact_paths[name], expected_sha,
                                    f"producer {name}")
    outputs = manifest.get("outputs")
    require(isinstance(outputs, dict) and set(outputs) == {"entry_plan.jsonl", "weekly_sources.jsonl", "summary.json"},
            "producer output pins")
    for name, value in outputs.items():
        path = guard_compact(PRODUCER / name, (PRODUCER,))
        require(value == pin(path), f"producer output pin {name}")
    require(isinstance(manifest.get("created_utc"), str), "producer created timestamp")
    return implementations


def validate_implementation_pin(value: Any, exact_path: Path, expected_sha: str, label: str,
                                root: Path = HERE) -> None:
    require(isinstance(value, dict) and set(value) == {"path", "bytes", "sha256"}, f"{label} pin shape")
    path = guard_compact(Path(value["path"]), (root,))
    require(canonical_key(path) == canonical_key(exact_path), f"{label} exact path")
    require(value == pin(path) and value["sha256"] == expected_sha, f"{label} pin")


def validate_retained_exit(value: Any, exit_path: Path | None = None) -> dict[str, dict[str, Any]]:
    require(isinstance(value, dict) and set(value) == {
        "exit_code", "planner_child_exit_code", "utc", "source", "elapsed_seconds", "pid",
        "creation_time", "cpu_affinity", "metadata_error", "changed_pins", "files", "retry",
    }, "producer retained exit object/schema")
    require(type(value["exit_code"]) is int and value["exit_code"] == 0 and
            type(value["planner_child_exit_code"]) is int and value["planner_child_exit_code"] == 0,
            "producer retained exit is not zero")
    require(value["source"] == "subprocess.Popen.wait_retained_handle" and
            value["metadata_error"] is None and value["changed_pins"] == [] and
            value["cpu_affinity"] == [0] and value["retry"] is False,
            "producer retained exit controls")
    require(isinstance(value["utc"], str) and type(value["pid"]) is int and value["pid"] > 0 and
            isinstance(value["creation_time"], (int, float)) and
            isinstance(value["elapsed_seconds"], (int, float)) and value["elapsed_seconds"] >= 0 and
            isinstance(value["files"], dict), "producer retained exit value types")
    observer = absolute(exit_path).parent if exit_path is not None else absolute(
        BASE / "weekly_zone_event_source_plan_observer_01")
    expected_files = {str(absolute(observer / name)) for name in OBSERVER_FILES}
    require(set(value["files"]) == expected_files, "producer retained exit exact observer files")
    observer_pins: dict[str, dict[str, Any]] = {}
    if exit_path is not None:
        expected_exit = BASE / "weekly_zone_event_source_plan_observer_01/exit.json"
        require(canonical_key(exit_path) == canonical_key(expected_exit), "producer retained exit path")
        for path_text, expected_sha in value["files"].items():
            require(isinstance(path_text, str), "observer file path")
            path = guard_compact(Path(path_text), (observer,))
            require(sha256_file(path) == digest_shape(expected_sha), "observer file hash")
            observer_pins[path_text] = pin(path)
    return observer_pins


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def audit(producer_manifest_sha: str, producer_exit_path: Path, producer_exit_sha: str,
          producer_builder_sha: str, producer_tests_sha: str, auditor_sha: str,
          auditor_tests_sha: str, contract_sha: str) -> dict[str, Any]:
    require(not OUTPUT.exists(), "exclusive audit output exists")
    supplied = [producer_manifest_sha, producer_exit_sha, producer_builder_sha, producer_tests_sha,
                auditor_sha, auditor_tests_sha, contract_sha]
    require(all(digest_shape(value) == value for value in supplied), "pin arguments")
    require(contract_sha == CONTRACT_SHA256, "contract argument")
    auditor_path = guard_compact(Path(__file__), (HERE,))
    tests_path = guard_compact(AUDITOR_TESTS, (HERE,))
    contract_path = guard_compact(CONTRACT, (HERE,))
    require(sha256_file(auditor_path) == auditor_sha and sha256_file(tests_path) == auditor_tests_sha
            and sha256_file(contract_path) == contract_sha, "auditor implementation pins")
    manifest_path = guard_compact(PRODUCER / "manifest.json", (PRODUCER,))
    require(sha256_file(manifest_path) == producer_manifest_sha, "producer manifest argument")
    exit_path = guard_compact(absolute(producer_exit_path), (BASE,))
    require(sha256_file(exit_path) == producer_exit_sha, "producer exit argument")
    exit_value = load_json(exit_path, (BASE,))
    observer_pins = validate_retained_exit(exit_value, exit_path)
    documents, authority_pins = authority_bundle()
    validate_authority_crosspins(documents, authority_pins)
    manifest = load_json(manifest_path, (PRODUCER,))
    implementations = validate_producer_manifest(manifest, authority_pins, producer_builder_sha, producer_tests_sha)
    expected_entries, calendar = reconstruct_entries(documents)
    actual_entries = load_jsonl(PRODUCER / "entry_plan.jsonl", (PRODUCER,))
    require(actual_entries == expected_entries, "entry_plan differs from independent reconstruction")
    expected_source_core = reconstruct_sources(expected_entries, calendar, documents)
    expected_sources = attach_observations(expected_source_core)
    actual_sources = load_jsonl(PRODUCER / "weekly_sources.jsonl", (PRODUCER,))
    require(actual_sources == expected_sources, "weekly_sources differs from independent reconstruction/current stat")
    summary = load_json(PRODUCER / "summary.json", (PRODUCER,))
    require(summary == expected_summary(expected_entries, expected_sources), "summary differs")
    require(len(expected_entries) == 2790 and len([row for row in expected_entries if row["source_authority"] == "BRIDGE"]) == 6
            and sum(len(source["references"]) for source in expected_sources) == 4860, "required counts")
    watched = dict(authority_pins)
    watched["producer/manifest.json"] = pin(manifest_path)
    watched["producer/entry_plan.jsonl"] = pin(PRODUCER / "entry_plan.jsonl")
    watched["producer/weekly_sources.jsonl"] = pin(PRODUCER / "weekly_sources.jsonl")
    watched["producer/summary.json"] = pin(PRODUCER / "summary.json")
    watched["producer/exit.json"] = pin(exit_path)
    for name, value in observer_pins.items():
        watched[f"producer_observer/{name}"] = value
    for name, value in implementations.items():
        watched[f"producer_implementation/{name}"] = dict(value)
    watched["auditor"] = pin(auditor_path)
    watched["auditor_tests"] = pin(tests_path)
    watched["contract"] = pin(contract_path)
    staging = Path(tempfile.mkdtemp(prefix=".weekly_zone_event_source_plan_audit.", dir=BASE))
    try:
        audit_value = {"schema": "weekly_zone_event_source_plan_audit_v1",
                       "status": "PASS_INDEPENDENT_WEEKLY_ZONE_EVENT_SOURCE_PLAN_METADATA_AUDIT",
                       "scope": "METADATA_ONLY_NOT_VALUE_ADMISSION",
                       "producer_status": STATUS,
                       "checks": {"entry_plans": 2790, "bridge_overlay_rows": 6,
                                  "source_references": 4860, "unique_sources": len(expected_sources),
                                  "authorities": 10, "summary_exact": True, "all_entries_exact": True,
                                  "all_sources_and_references_exact": True, "current_metadata_exact": True},
                       "flags": {"raw_values_read": False, "raw_files_hashed": False,
                                 "parquet_footers_read": False, "arrays_read": False,
                                 "outcomes_read": False, "fit_performed": False,
                                 "inference_performed": False, "replay_performed": False,
                                 "selected_policy": None, "technical_ready": False,
                                 "promotion_approved": False},
                       "inputs": watched, "created_utc": datetime.now(timezone.utc).isoformat()}
        write_json(staging / "audit.json", audit_value)
        for name, expected in watched.items():
            path = Path(expected["path"])
            require(pin(path) == expected, f"watched compact input changed: {name}")
        closing_sources = attach_observations(expected_source_core)
        require(closing_sources == expected_sources, "market metadata changed during audit close")
        staged_audit_pin = pin(staging / "audit.json")
        audit_pin = {**staged_audit_pin, "path": str(absolute(OUTPUT / "audit.json"))}
        manifest_value = {"schema": "weekly_zone_event_source_plan_audit_manifest_v1",
                          "status": audit_value["status"], "inputs": watched,
                          "outputs": {"audit.json": audit_pin}, "flags": audit_value["flags"],
                          "created_utc": datetime.now(timezone.utc).isoformat()}
        write_json(staging / "manifest.json", manifest_value)
        require(not OUTPUT.exists(), "audit output appeared during close")
        staging.rename(OUTPUT)
        return manifest_value
    except BaseException:
        raise


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--execute-reviewed-audit", action="store_true")
    value.add_argument("--producer-manifest-sha256", required=True)
    value.add_argument("--producer-exit-path", required=True)
    value.add_argument("--producer-exit-sha256", required=True)
    value.add_argument("--producer-builder-sha256", required=True)
    value.add_argument("--producer-tests-sha256", required=True)
    value.add_argument("--auditor-sha256", required=True)
    value.add_argument("--auditor-tests-sha256", required=True)
    value.add_argument("--contract-sha256", required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.execute_reviewed_audit:
        parser().error("execution requires --execute-reviewed-audit")
    audit(args.producer_manifest_sha256.lower(), Path(args.producer_exit_path),
          args.producer_exit_sha256.lower(), args.producer_builder_sha256.lower(),
          args.producer_tests_sha256.lower(), args.auditor_sha256.lower(),
          args.auditor_tests_sha256.lower(), args.contract_sha256.lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
