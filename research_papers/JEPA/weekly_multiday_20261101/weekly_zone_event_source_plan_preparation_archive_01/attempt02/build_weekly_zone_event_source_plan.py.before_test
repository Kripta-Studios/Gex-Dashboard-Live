"""Build a metadata-only source plan for future weekly zone-event research."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


TICKERS = ("SPY", "QQQ", "SPXW")
TICKER_ORDER = {ticker: index for index, ticker in enumerate(TICKERS)}
ROLES = ("ENTRY_DAY", "INTERMEDIATE_DAY", "H2_DAY")
STATUSES = ("PLANNED", "NO_SERIES", "HORIZON_OUTSIDE_CALENDAR")
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
SOURCE_ROOT = Path(r"D:\ThetaData")
OUTPUT = BASE / "weekly_zone_event_source_plan_01"
HERE = Path(__file__).absolute().parent
TESTS = HERE / "test_build_weekly_zone_event_source_plan.py"
CONTRACT = HERE / "WEEKLY_ZONE_EVENT_SOURCE_PLAN_CONTRACT_20261102.md"
CONTRACT_SHA256 = "c1891e794cab794d5f6570f99d838a888663a48b8ccededd4d96d27a63173d65"
STATUS = "SOURCE_PLAN_NOT_VALUE_ADMISSION"
REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

AUTHORITY_SHA256 = {
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


class PlanError(RuntimeError):
    pass


@dataclass(frozen=True)
class Expectations:
    calendar_rows: int
    sessions: int
    h1_rows: int
    q3_rows: int
    short_rows: int
    status_counts: Mapping[str, int]
    overlay_rows: int
    reference_count: int
    first_date: str
    last_date: str


REAL_EXPECTATIONS = Expectations(
    calendar_rows=2790,
    sessions=930,
    h1_rows=2625,
    q3_rows=165,
    short_rows=24,
    status_counts={"PLANNED": 1620, "NO_SERIES": 1164, "HORIZON_OUTSIDE_CALENDAR": 6},
    overlay_rows=6,
    reference_count=4860,
    first_date="20230103",
    last_date="20260917",
)


class RealStatAdapter:
    """The only adapter allowed to touch nominal market paths."""

    def lstat(self, path: Path) -> os.stat_result:
        return path.lstat()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PlanError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact_pin(path: Path, final_path: Path | None = None) -> dict[str, Any]:
    return {
        "path": str(final_path if final_path is not None else path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(json_bytes(value))


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("xb") as handle:
        for row in rows:
            line = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            handle.write((line + "\n").encode("utf-8"))


def canonical_path(path: Path) -> Path:
    return Path(os.path.abspath(path))


def canonical_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(canonical_path(path))))


def linked(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & REPARSE_FLAG
    )


def guard_metadata_file(path: Path, root: Path) -> None:
    path = canonical_path(path)
    root = canonical_path(root)
    require(
        os.path.commonpath((str(path), str(root))) == str(root),
        "metadata path outside authority root",
    )
    current = path
    while True:
        info = current.lstat()
        require(not linked(info), f"metadata link/reparse forbidden: {current}")
        if current == root:
            break
        parent = current.parent
        require(parent != current, "metadata root traversal")
        current = parent
    require(path.is_file(), f"metadata authority is not a regular file: {path}")


def load_authorities(
    base: Path = BASE,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    base = canonical_path(base)
    documents: dict[str, Any] = {}
    pins: dict[str, dict[str, Any]] = {}
    for relative, expected in AUTHORITY_SHA256.items():
        path = canonical_path(base / Path(relative))
        guard_metadata_file(path, base)
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        require(digest == expected, f"authority SHA mismatch: {relative}")
        try:
            documents[relative] = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PlanError(f"authority is not valid UTF-8 JSON: {relative}") from error
        pins[relative] = {"path": str(path), "bytes": len(raw), "sha256": digest}
    return documents, pins


def validate_pin(
    value: Any,
    expected: Mapping[str, Any],
    label: str,
    *,
    rows: int | None = None,
) -> None:
    require(isinstance(value, dict), f"{label} pin is not an object")
    require(
        value.get("bytes") == expected["bytes"]
        and value.get("sha256") == expected["sha256"],
        f"{label} crosspin mismatch",
    )
    if rows is not None:
        require(value.get("rows") == rows, f"{label} row count mismatch")


def parse_day(value: Any, label: str) -> date:
    require(
        isinstance(value, str) and re.fullmatch(r"\d{8}", value) is not None,
        f"{label} date shape",
    )
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as error:
        raise PlanError(f"{label} invalid date") from error


def validate_calendar(
    unified_rows: Sequence[Mapping[str, Any]],
    h1_rows: Sequence[Mapping[str, Any]],
    q3_rows: Sequence[Mapping[str, Any]],
    expected: Expectations = REAL_EXPECTATIONS,
) -> tuple[list[str], dict[tuple[str, str], int]]:
    require(len(unified_rows) == expected.calendar_rows, "unified calendar row count")
    require(
        len(h1_rows) == expected.h1_rows and len(q3_rows) == expected.q3_rows,
        "segment calendar row count",
    )
    calendar: dict[tuple[str, str], int] = {}
    for row in unified_rows:
        require(set(row) == {"ticker", "date", "close_i"}, "calendar row schema")
        ticker, day, close_i = row["ticker"], row["date"], row["close_i"]
        require(ticker in TICKERS and close_i in (210, 390), "calendar value")
        parse_day(day, "calendar")
        key = (ticker, day)
        require(key not in calendar, "duplicate calendar identity")
        calendar[key] = close_i
    dates = sorted({day for _ticker, day in calendar})
    require(
        len(dates) == expected.sessions
        and dates[0] == expected.first_date
        and dates[-1] == expected.last_date,
        "calendar session bounds",
    )
    for day in dates:
        values = [calendar.get((ticker, day)) for ticker in TICKERS]
        require(None not in values and len(set(values)) == 1, "ticker calendars unequal")
    require(
        sum(value == 210 for value in calendar.values()) == expected.short_rows,
        "short-day count",
    )

    segment: dict[tuple[str, str], int] = {}
    for name, rows, schemas in (
        ("H1", h1_rows, ({"ticker", "date", "close_i"}, {"ticker", "date", "close_i", "status"})),
        ("Q3", q3_rows, ({"ticker", "date", "close_i"},)),
    ):
        for row in rows:
            require(set(row) in schemas, f"{name} calendar row schema")
            key = (row["ticker"], row["date"])
            require(key not in segment and key in calendar, f"{name} calendar identity")
            require(row["close_i"] == calendar[key], f"{name} close_i disagreement")
            segment[key] = row["close_i"]
    require(set(segment) == set(calendar), "segment calendars do not partition unified")
    q3_keys = {(row["ticker"], row["date"]) for row in q3_rows}
    require(all(calendar[key] == 390 for key in q3_keys), "Q3 contains a short session")
    return dates, calendar


def validate_crosspins(
    documents: Mapping[str, Any], pins: Mapping[str, Mapping[str, Any]]
) -> None:
    h1i = documents["h2_dataset_v2_01/inventory.json"]
    h1r = documents["h2_dataset_v2_01/inventory_manifest.json"]
    h1m = documents["h2_dataset_v2_01/manifest.json"]
    q3i = documents["h2_dataset_v2_extension_2026q3_partial_01/inventory.json"]
    q3r = documents["h2_dataset_v2_extension_2026q3_partial_01/inventory_manifest.json"]
    q3m = documents["h2_dataset_v2_extension_2026q3_partial_01/manifest.json"]
    bri = documents["h2_boundary_bridge_01/inventory.json"]
    brr = documents["h2_boundary_bridge_01/inventory_manifest.json"]
    brm = documents["h2_boundary_bridge_01/manifest.json"]
    uni = documents["h2_boundary_bridge_01/unified_calendar.json"]

    require(
        h1i.get("schema") == "weekly_h2_source_inventory_v2_clock_filter",
        "H1 inventory schema",
    )
    require(h1r.get("schema") == "weekly_h2_inventory_manifest_v1", "H1 receipt schema")
    require(
        h1m.get("schema") == "weekly_h2_dataset_manifest_v2"
        and h1m.get("status") == "COMPLETE_WEEKLY_H2_DATASET_NOT_EVALUATED",
        "H1 manifest status",
    )
    require(q3i.get("schema") == "weekly_h2_q3_partial_inventory_v1", "Q3 inventory schema")
    require(
        q3r.get("schema") == "weekly_h2_q3_partial_inventory_manifest_v1",
        "Q3 receipt schema",
    )
    require(
        q3m.get("schema") == "weekly_h2_q3_partial_dataset_manifest_v1"
        and q3m.get("status")
        == "COMPLETE_WEEKLY_H2_Q3_PARTIAL_DATASET_NOT_EVALUATED",
        "Q3 manifest status",
    )
    require(
        bri.get("schema") == "weekly_h2_boundary_bridge_inventory_v1",
        "bridge inventory schema",
    )
    require(
        brr.get("schema") == "weekly_h2_boundary_bridge_inventory_manifest_v1",
        "bridge receipt schema",
    )
    require(
        brm.get("schema") == "weekly_h2_boundary_bridge_manifest_v1"
        and brm.get("status") == "COMPLETE_WEEKLY_H2_BOUNDARY_BRIDGE_NOT_EVALUATED",
        "bridge manifest status",
    )
    require(
        uni.get("schema") == "weekly_h2_boundary_unified_calendar_v1",
        "unified calendar schema",
    )

    validate_pin(
        h1r.get("inventory.json"),
        pins["h2_dataset_v2_01/inventory.json"],
        "H1 receipt inventory",
    )
    validate_pin(
        h1m.get("files", {}).get("inventory.json"),
        pins["h2_dataset_v2_01/inventory.json"],
        "H1 manifest inventory",
        rows=2619,
    )
    require(
        h1m.get("inventory_bound_sha256")
        == pins["h2_dataset_v2_01/inventory.json"]["sha256"],
        "H1 inventory bound hash",
    )
    validate_pin(
        q3r.get("inventory.json"),
        pins["h2_dataset_v2_extension_2026q3_partial_01/inventory.json"],
        "Q3 receipt inventory",
    )
    validate_pin(
        q3m.get("files", {}).get("inventory.json"),
        pins["h2_dataset_v2_extension_2026q3_partial_01/inventory.json"],
        "Q3 manifest inventory",
    )
    validate_pin(
        q3m.get("files", {}).get("inventory_manifest.json"),
        pins["h2_dataset_v2_extension_2026q3_partial_01/inventory_manifest.json"],
        "Q3 manifest receipt",
    )
    validate_pin(
        q3m.get("source_inventory"),
        pins["h2_dataset_v2_extension_2026q3_partial_01/inventory.json"],
        "Q3 source inventory",
    )
    validate_pin(
        brr.get("inventory.json"),
        pins["h2_boundary_bridge_01/inventory.json"],
        "bridge receipt inventory",
    )
    validate_pin(
        brr.get("unified_calendar.json"),
        pins["h2_boundary_bridge_01/unified_calendar.json"],
        "bridge receipt calendar",
    )
    validate_pin(
        brm.get("files", {}).get("inventory.json"),
        pins["h2_boundary_bridge_01/inventory.json"],
        "bridge manifest inventory",
    )
    validate_pin(
        brm.get("files", {}).get("inventory_manifest.json"),
        pins["h2_boundary_bridge_01/inventory_manifest.json"],
        "bridge manifest receipt",
    )
    validate_pin(
        brm.get("files", {}).get("unified_calendar.json"),
        pins["h2_boundary_bridge_01/unified_calendar.json"],
        "bridge manifest calendar",
    )
    require(
        bri.get("unified_calendar")
        == {
            "rows": 2790,
            "schema": "weekly_h2_boundary_unified_calendar_v1",
            "sha256": pins["h2_boundary_bridge_01/unified_calendar.json"]["sha256"],
        },
        "bridge calendar binding",
    )

    require(
        h1m.get("flags")
        == {
            "economic_evaluation_performed": False,
            "fit_performed": False,
            "production_modified": False,
            "promotion_approved": False,
        },
        "H1 flags",
    )
    require(
        q3m.get("flags")
        == {
            "no_fit": True,
            "no_recalibration": True,
            "no_refit": True,
            "no_selection": True,
            "not_oos": True,
            "not_promotion": True,
            "not_technical_readiness": True,
        },
        "Q3 flags",
    )
    require(
        brm.get("flags")
        == {
            "development_seen": True,
            "economic_evaluation_performed": False,
            "fit_performed": False,
            "not_oos": True,
            "originals_modified": False,
            "promotion_approved": False,
        },
        "bridge flags",
    )
    require(bri.get("authority_pins") == brm.get("authority_pins"), "bridge pins disagree")
    require(
        bri.get("scope")
        == {
            "entry_dates": ["20260629", "20260630"],
            "nominal_source_count": 6,
            "plan_count": 6,
            "segment_dates": ["20260629", "20260630", "20260701", "20260702"],
            "ticker_count": 3,
        },
        "bridge scope",
    )
    authority = bri.get("authority_pins", {})
    validate_pin(
        authority.get("h1_manifest"),
        pins["h2_dataset_v2_01/manifest.json"],
        "bridge H1 manifest",
    )
    validate_pin(
        authority.get("q3_manifest"),
        pins["h2_dataset_v2_extension_2026q3_partial_01/manifest.json"],
        "bridge Q3 manifest",
    )
    for prefix, manifest in (("h1", h1m), ("q3", q3m)):
        validate_pin(
            authority.get(f"{prefix}_coverage"),
            manifest.get("files", {}).get("coverage.json", {}),
            f"bridge {prefix} coverage",
        )
        validate_pin(
            authority.get(f"{prefix}_candidates"),
            manifest.get("files", {}).get("candidates.jsonl", {}),
            f"bridge {prefix} candidates",
        )


def nominal_source_path(
    source_root: Path, ticker: str, expiration: str, trade_date: str
) -> Path:
    require(ticker in TICKERS, "unsupported ticker")
    parse_day(expiration, "expiration")
    parse_day(trade_date, "trade")
    return canonical_path(
        canonical_path(source_root)
        / "data_options"
        / ticker
        / "greeks"
        / trade_date[:4]
        / trade_date[4:6]
        / f"{ticker}_{expiration}_{trade_date}_greeks.parquet"
    )


def parse_nominal_source(path: Path, source_root: Path) -> tuple[str, str, str]:
    lexical = Path(path)
    require(lexical.is_absolute() and ".." not in lexical.parts, "source lexical traversal/nonabsolute path")
    path = canonical_path(path)
    options = canonical_path(source_root) / "data_options"
    try:
        relative = Path(os.path.relpath(path, options))
    except ValueError as error:
        raise PlanError("source on a different volume") from error
    require(
        not relative.is_absolute() and ".." not in relative.parts,
        "source traversal/outside options root",
    )
    parts = relative.parts
    require(len(parts) == 5 and parts[1] == "greeks", "source path template")
    ticker, _greeks, year, month, filename = parts
    match = re.fullmatch(
        r"(SPY|QQQ|SPXW)_(\d{8})_(\d{8})_greeks\.parquet", filename
    )
    require(match is not None and match.group(1) == ticker, "source filename template")
    expiration, trade_date = match.group(2), match.group(3)
    require(
        year == trade_date[:4] and month == trade_date[4:6],
        "source date directory mismatch",
    )
    require(
        canonical_key(path)
        == canonical_key(nominal_source_path(source_root, ticker, expiration, trade_date)),
        "noncanonical nominal source",
    )
    return ticker, expiration, trade_date


def validate_coverage_row(row: Mapping[str, Any], ticker: str, day: str) -> None:
    required = {
        "candidate_ids",
        "entry_date",
        "entry_path",
        "exit_date",
        "exit_path",
        "expiration",
        "reason",
        "status",
        "ticker",
    }
    require(set(row) == required, "coverage row schema")
    require(
        row["ticker"] == ticker
        and row["entry_date"] == day
        and row["status"] in STATUSES,
        "coverage identity/status",
    )
    ids = row["candidate_ids"]
    require(
        ids == [],
        "source inventory coverage must precede candidates",
    )


def build_entry_plan(
    h1_coverage: Sequence[Mapping[str, Any]],
    q3_coverage: Sequence[Mapping[str, Any]],
    bridge_coverage: Sequence[Mapping[str, Any]],
    dates: Sequence[str],
    calendar: Mapping[tuple[str, str], int],
    source_root: Path,
    expected: Expectations = REAL_EXPECTATIONS,
) -> list[dict[str, Any]]:
    base: dict[tuple[str, str], tuple[str, Mapping[str, Any]]] = {}
    for authority, rows in (("H1", h1_coverage), ("Q3", q3_coverage)):
        for row in rows:
            key = (row.get("ticker"), row.get("entry_date"))
            require(key not in base and key in calendar, "coverage duplicate/outside calendar")
            validate_coverage_row(row, key[0], key[1])
            base[key] = (authority, row)
    require(set(base) == set(calendar), "coverage does not span unified calendar")

    overlay_keys = {
        (ticker, day) for ticker in TICKERS for day in ("20260629", "20260630")
    }
    overlay: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in bridge_coverage:
        key = (row.get("ticker"), row.get("entry_date"))
        require(
            key in overlay_keys and key not in overlay,
            "bridge overlay outside exact six identities",
        )
        validate_coverage_row(row, key[0], key[1])
        require(
            base[key][1]["status"] == "HORIZON_OUTSIDE_CALENDAR",
            "bridge may replace only prior horizon rows",
        )
        overlay[key] = row
    require(
        set(overlay) == overlay_keys and len(overlay) == expected.overlay_rows,
        "bridge overlay is not exact",
    )

    date_position = {day: index for index, day in enumerate(dates)}
    output: list[dict[str, Any]] = []
    for day in dates:
        index = date_position[day]
        sessions = {
            "D": day,
            "D1": dates[index + 1] if index + 1 < len(dates) else None,
            "D2": dates[index + 2] if index + 2 < len(dates) else None,
        }
        for ticker in TICKERS:
            key = (ticker, day)
            authority, original = base[key]
            row = overlay.get(key, original)
            if key in overlay:
                authority = "BRIDGE"
            status = row["status"]
            d2 = sessions["D2"]
            if status == "PLANNED":
                require(
                    d2 is not None
                    and row["exit_date"] == d2
                    and row["reason"] is None,
                    "planned H2/reason",
                )
                expiration = row["expiration"]
                require(isinstance(expiration, str), "planned expiration")
                delta = (
                    parse_day(expiration, "expiration") - parse_day(day, "entry")
                ).days
                require(
                    1 <= delta <= 8
                    and parse_day(d2, "H2") < parse_day(expiration, "expiration"),
                    "planned expiry constraints",
                )
                entry = nominal_source_path(source_root, ticker, expiration, day)
                h2 = nominal_source_path(source_root, ticker, expiration, d2)
                require(
                    isinstance(row["entry_path"], str),
                    "upstream entry path missing",
                )
                require(
                    parse_nominal_source(Path(row["entry_path"]), source_root)
                    == (ticker, expiration, day)
                    and canonical_key(Path(row["entry_path"])) == canonical_key(entry),
                    "upstream entry path altered",
                )
                require(
                    isinstance(row["exit_path"], str),
                    "upstream H2 path missing",
                )
                require(
                    parse_nominal_source(Path(row["exit_path"]), source_root)
                    == (ticker, expiration, d2)
                    and canonical_key(Path(row["exit_path"])) == canonical_key(h2),
                    "upstream H2 path altered",
                )
                entry_path, h2_path = str(entry), str(h2)
            elif status == "NO_SERIES":
                require(
                    d2 is not None and row["exit_date"] == d2,
                    "NO_SERIES H2",
                )
                require(
                    row["expiration"] is None
                    and row["entry_path"] is None
                    and row["exit_path"] is None
                    and isinstance(row["reason"], str),
                    "NO_SERIES must not invent sources",
                )
                expiration = entry_path = h2_path = None
            else:
                require(d2 is None, "horizon row has an available H2 session")
                require(
                    row["exit_date"] is None
                    and row["expiration"] is None
                    and row["entry_path"] is None
                    and row["exit_path"] is None,
                    "horizon row invented future metadata",
                )
                require(row["reason"] == "NO_OFFICIAL_H2", "horizon reason")
                expiration = entry_path = h2_path = None
            output.append(
                {
                    "plan_id": f"{ticker}:{day}",
                    "ticker": ticker,
                    "date": day,
                    "close_i": calendar[key],
                    "status": status,
                    "reason": row["reason"],
                    "expiration": expiration,
                    "session_dates": sessions,
                    "entry_path": entry_path,
                    "h2_path": h2_path,
                    "source_authority": authority,
                }
            )
    require(len(output) == expected.calendar_rows, "entry plan count")
    require(
        dict(Counter(row["status"] for row in output))
        == dict(expected.status_counts),
        "entry plan status counts",
    )
    return output


def historical_binding(row: Mapping[str, Any], authority: str) -> dict[str, Any]:
    require(
        row.get("status") in ("INVENTORIED", "MISSING_SOURCE"),
        "historical source status",
    )
    expected_keys = {"bytes", "path", "projected_schema", "rows", "sha256", "status"}
    if authority == "BRIDGE":
        expected_keys |= {"clock_basis", "physical_id"}
    require(set(row) == expected_keys, f"{authority} historical source schema")
    if row["status"] == "INVENTORIED":
        require(
            isinstance(row["bytes"], int)
            and row["bytes"] >= 0
            and isinstance(row["sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is not None,
            "inventoried binding shape",
        )
    else:
        require(
            row["bytes"] is None and row["sha256"] is None,
            "missing binding shape",
        )
    return {
        "authority": authority,
        "status": row["status"],
        "bytes": row["bytes"],
        "sha256": row["sha256"],
        "expected_upstream_pin_not_currently_rehashed": True,
    }


def collect_historical_bindings(
    inventories: Sequence[tuple[str, Sequence[Mapping[str, Any]]]],
    source_root: Path,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for authority, rows in inventories:
        for row in rows:
            require(isinstance(row.get("path"), str), "historical source path")
            raw_path = Path(row["path"])
            parse_nominal_source(raw_path, source_root)
            path = canonical_path(raw_path)
            key = canonical_key(path)
            binding = historical_binding(row, authority)
            if key in result:
                prior = {
                    (value["status"], value["bytes"], value["sha256"])
                    for value in result[key]
                }
                require(
                    (binding["status"], binding["bytes"], binding["sha256"])
                    in prior,
                    "conflicting historical bindings after path normalization",
                )
            else:
                result[key] = []
            result[key].append(binding)
    return result


def source_records(
    plans: Sequence[Mapping[str, Any]],
    calendar: Mapping[tuple[str, str], int],
    source_root: Path,
    bindings: Mapping[str, Sequence[Mapping[str, Any]]],
    expected: Expectations = REAL_EXPECTATIONS,
) -> list[dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    reference_count = 0
    for plan in plans:
        if plan["status"] != "PLANNED":
            continue
        expiration = plan["expiration"]
        days = (
            plan["session_dates"]["D"],
            plan["session_dates"]["D1"],
            plan["session_dates"]["D2"],
        )
        require(all(day is not None for day in days), "planned source sessions")
        for role, trade_date in zip(ROLES, days, strict=True):
            path = nominal_source_path(
                source_root, plan["ticker"], expiration, trade_date
            )
            key = canonical_key(path)
            reference = {
                "plan_id": plan["plan_id"],
                "ticker": plan["ticker"],
                "entry_date": plan["date"],
                "expiration": expiration,
                "role": role,
                "trade_date": trade_date,
                "close_i": calendar[(plan["ticker"], trade_date)],
            }
            if key not in sources:
                sources[key] = {
                    "path": str(path),
                    "ticker": plan["ticker"],
                    "expiration": expiration,
                    "trade_date": trade_date,
                    "references": [],
                    "expected_upstream_bindings": [
                        dict(value) for value in bindings.get(key, ())
                    ],
                    "new_without_upstream_binding": key not in bindings,
                }
            source = sources[key]
            require(
                (
                    source["ticker"],
                    source["expiration"],
                    source["trade_date"],
                )
                == (plan["ticker"], expiration, trade_date),
                "nominal path identity collision",
            )
            source["references"].append(reference)
            reference_count += 1
    require(reference_count == expected.reference_count, "source reference count")
    for source in sources.values():
        source["references"].sort(
            key=lambda row: (
                row["entry_date"],
                TICKER_ORDER[row["ticker"]],
                ROLES.index(row["role"]),
            )
        )
    return sorted(sources.values(), key=lambda row: os.path.normcase(row["path"]))


def inspect_nominal_path(path: Path, source_root: Path, adapter: Any) -> dict[str, Any]:
    parse_nominal_source(path, source_root)
    path = canonical_path(path)
    source_root = canonical_path(source_root)
    options = source_root / "data_options"
    ancestor_chain: list[Path] = []
    current_ancestor = source_root
    while True:
        ancestor_chain.append(current_ancestor)
        if current_ancestor.parent == current_ancestor:
            break
        current_ancestor = current_ancestor.parent
    ancestor_chain.reverse()
    ancestor_chain.append(options)
    for ancestor in ancestor_chain:
        try:
            ancestor_info = adapter.lstat(ancestor)
        except FileNotFoundError:
            if ancestor != options:
                raise PlanError(f"market ancestor is absent: {ancestor}") from None
            return {
                "exists": False,
                "bytes": None,
                "mtime_ns": None,
                "physical_id": None,
            }
        require(
            not linked(ancestor_info),
            f"market link/reparse forbidden: {ancestor}",
        )
        require(
            stat.S_ISDIR(ancestor_info.st_mode),
            f"market root is not a directory: {ancestor}",
        )
    relative = Path(os.path.relpath(path, options))
    current = options
    target_info: os.stat_result | None = None
    missing = False
    for part in relative.parts:
        current = current / part
        if missing:
            continue
        try:
            info = adapter.lstat(current)
        except FileNotFoundError:
            missing = True
            continue
        require(not linked(info), f"market link/reparse forbidden: {current}")
        if current != path:
            require(
                stat.S_ISDIR(info.st_mode),
                f"market ancestor is not a directory: {current}",
            )
        else:
            require(
                stat.S_ISREG(info.st_mode),
                f"market path is not a regular file: {current}",
            )
            target_info = info
    if target_info is None:
        return {
            "exists": False,
            "bytes": None,
            "mtime_ns": None,
            "physical_id": None,
        }
    return {
        "exists": True,
        "bytes": target_info.st_size,
        "mtime_ns": target_info.st_mtime_ns,
        "physical_id": [target_info.st_dev, target_info.st_ino],
    }


def discrepancy_codes(
    bindings: Sequence[Mapping[str, Any]], observation: Mapping[str, Any]
) -> list[str]:
    values: list[str] = []
    for binding in bindings:
        if binding["status"] == "INVENTORIED" and not observation["exists"]:
            values.append("EXPECTED_PRESENT_NOW_MISSING")
        elif binding["status"] == "MISSING_SOURCE" and observation["exists"]:
            values.append("EXPECTED_MISSING_NOW_PRESENT")
        elif (
            binding["status"] == "INVENTORIED"
            and observation["exists"]
            and binding["bytes"] != observation["bytes"]
        ):
            values.append("CURRENT_BYTES_DIFFER_FROM_EXPECTED_UPSTREAM")
    return sorted(set(values))


def inspect_sources(
    records: Sequence[Mapping[str, Any]], source_root: Path, adapter: Any
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    physical: dict[tuple[int, int], str] = {}
    for record in records:
        observation = inspect_nominal_path(Path(record["path"]), source_root, adapter)
        if observation["exists"]:
            identity = tuple(observation["physical_id"])
            prior = physical.get(identity)
            require(
                prior is None
                or canonical_key(Path(prior)) == canonical_key(Path(record["path"])),
                "different nominal paths alias the same physical file",
            )
            physical[identity] = record["path"]
        value = dict(record)
        value["observation"] = observation
        value["metadata_discrepancies"] = discrepancy_codes(
            record["expected_upstream_bindings"], observation
        )
        output.append(value)
    return output


def require_stable_sources(
    before: Sequence[Mapping[str, Any]], after: Sequence[Mapping[str, Any]]
) -> None:
    require(len(before) == len(after), "source set changed during close")
    for initial, final in zip(before, after, strict=True):
        require(
            initial["path"] == final["path"]
            and initial["observation"] == final["observation"],
            f"market stat changed during close: {initial['path']}",
        )


def make_summary(
    plans: Sequence[Mapping[str, Any]], sources: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    references = [
        reference for source in sources for reference in source["references"]
    ]
    discrepancies = Counter(
        code for source in sources for code in source["metadata_discrepancies"]
    )
    return {
        "schema": "weekly_zone_event_source_plan_summary_v1",
        "status": STATUS,
        "entry_plans": {
            "total": len(plans),
            "by_status": dict(
                sorted(Counter(row["status"] for row in plans).items())
            ),
            "by_ticker": dict(
                sorted(Counter(row["ticker"] for row in plans).items())
            ),
            "by_year": dict(
                sorted(Counter(row["date"][:4] for row in plans).items())
            ),
        },
        "references": {
            "total": len(references),
            "by_role": dict(
                sorted(Counter(row["role"] for row in references).items())
            ),
            "by_ticker": dict(
                sorted(Counter(row["ticker"] for row in references).items())
            ),
            "by_year": dict(
                sorted(Counter(row["trade_date"][:4] for row in references).items())
            ),
        },
        "sources": {
            "unique": len(sources),
            "present": sum(row["observation"]["exists"] for row in sources),
            "absent": sum(not row["observation"]["exists"] for row in sources),
            "present_unique_bytes": sum(
                row["observation"]["bytes"] or 0 for row in sources
            ),
            "new_without_upstream_binding": sum(
                row["new_without_upstream_binding"] for row in sources
            ),
            "with_upstream_binding": sum(
                not row["new_without_upstream_binding"] for row in sources
            ),
            "with_metadata_discrepancy": sum(
                bool(row["metadata_discrepancies"]) for row in sources
            ),
            "discrepancies": dict(sorted(discrepancies.items())),
        },
        "flags": {
            "metadata_only": True,
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
        },
    }


def validate_real_bundle(
    documents: Mapping[str, Any],
    pins: Mapping[str, Mapping[str, Any]],
    source_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validate_crosspins(documents, pins)
    h1 = documents["h2_dataset_v2_01/inventory.json"]
    q3 = documents["h2_dataset_v2_extension_2026q3_partial_01/inventory.json"]
    bridge = documents["h2_boundary_bridge_01/inventory.json"]
    unified = documents["h2_boundary_bridge_01/unified_calendar.json"]
    require(
        all(
            isinstance(value, str)
            and canonical_key(Path(value)) == canonical_key(source_root)
            for value in (
                h1.get("source_root"),
                q3.get("source_root"),
                bridge.get("source_root"),
            )
        ),
        "upstream source root",
    )
    require(
        len(h1.get("sources", [])) == 2619
        and len(q3.get("sources", [])) == 156
        and len(bridge.get("sources", [])) == 6,
        "historical source counts",
    )
    dates, calendar = validate_calendar(
        unified.get("rows", []),
        h1.get("calendar_rows", []),
        q3.get("calendar_rows", []),
    )
    plans = build_entry_plan(
        h1.get("coverage_plan", []),
        q3.get("coverage_plan", []),
        bridge.get("coverage_plan", []),
        dates,
        calendar,
        source_root,
    )
    bindings = collect_historical_bindings(
        (
            ("H1", h1["sources"]),
            ("Q3", q3["sources"]),
            ("BRIDGE", bridge["sources"]),
        ),
        source_root,
    )
    records = source_records(plans, calendar, source_root, bindings)
    return plans, records


def closing_authorities(initial: Mapping[str, Mapping[str, Any]]) -> None:
    for relative, expected in initial.items():
        path = Path(expected["path"])
        require(
            path.stat().st_size == expected["bytes"]
            and sha256_file(path) == expected["sha256"],
            f"authority changed during close: {relative}",
        )


def execute_plan(
    builder_sha256: str,
    tests_sha256: str,
    contract_sha256: str,
    *,
    base: Path = BASE,
    source_root: Path = SOURCE_ROOT,
    output: Path = OUTPUT,
    stat_adapter: Any | None = None,
) -> dict[str, Any]:
    builder = canonical_path(Path(__file__))
    tests = canonical_path(TESTS)
    contract = canonical_path(CONTRACT)
    require(
        re.fullmatch(r"[0-9a-f]{64}", builder_sha256) is not None
        and sha256_file(builder) == builder_sha256,
        "builder pin mismatch",
    )
    require(
        re.fullmatch(r"[0-9a-f]{64}", tests_sha256) is not None
        and sha256_file(tests) == tests_sha256,
        "tests pin mismatch",
    )
    require(
        contract_sha256 == CONTRACT_SHA256
        and sha256_file(contract) == contract_sha256,
        "contract pin mismatch",
    )
    require(
        canonical_path(base) == canonical_path(BASE)
        and canonical_path(source_root) == canonical_path(SOURCE_ROOT)
        and canonical_path(output) == canonical_path(OUTPUT),
        "real roots are frozen",
    )
    require(not output.exists(), "exclusive output already exists")
    documents, authority_pins = load_authorities(base)
    plans, records = validate_real_bundle(documents, authority_pins, source_root)
    adapter = stat_adapter or RealStatAdapter()
    inspected = inspect_sources(records, source_root, adapter)
    summary = make_summary(plans, inspected)
    require(
        summary["entry_plans"]["total"] == 2790
        and summary["references"]["total"] == 4860,
        "final plan counts",
    )

    implementation_pins = {
        "builder": {
            "path": str(builder),
            "bytes": builder.stat().st_size,
            "sha256": builder_sha256,
        },
        "tests": {
            "path": str(tests),
            "bytes": tests.stat().st_size,
            "sha256": tests_sha256,
        },
        "contract": {
            "path": str(contract),
            "bytes": contract.stat().st_size,
            "sha256": contract_sha256,
        },
    }
    staging = Path(
        tempfile.mkdtemp(prefix=".weekly_zone_event_source_plan.", dir=base)
    )
    try:
        write_jsonl(staging / "entry_plan.jsonl", plans)
        write_jsonl(staging / "weekly_sources.jsonl", inspected)
        write_json(staging / "summary.json", summary)
        closing = inspect_sources(records, source_root, adapter)
        require_stable_sources(inspected, closing)
        closing_authorities(authority_pins)
        for name, expected in implementation_pins.items():
            path = Path(expected["path"])
            require(
                path.stat().st_size == expected["bytes"]
                and sha256_file(path) == expected["sha256"],
                f"implementation pin changed: {name}",
            )
        outputs = {
            name: compact_pin(staging / name, output / name)
            for name in ("entry_plan.jsonl", "weekly_sources.jsonl", "summary.json")
        }
        manifest = {
            "schema": "weekly_zone_event_source_plan_manifest_v1",
            "status": STATUS,
            "inputs": dict(authority_pins),
            "implementation_pins": implementation_pins,
            "outputs": outputs,
            "flags": {
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
            },
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }
        write_json(staging / "manifest.json", manifest)
        require(not output.exists(), "exclusive output appeared during close")
        staging.rename(output)
        return manifest
    except BaseException as error:
        try:
            write_json(
                staging / "failure.json",
                {
                    "status": "FAILED_PARTIAL_NOT_ADOPTABLE",
                    "exception_type": type(error).__name__,
                    "message": str(error),
                },
            )
        except BaseException:
            pass
        raise


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--execute-reviewed-plan", action="store_true")
    value.add_argument("--builder-sha256", required=True)
    value.add_argument("--tests-sha256", required=True)
    value.add_argument("--contract-sha256", required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.execute_reviewed_plan:
        parser().error("execution requires --execute-reviewed-plan")
    execute_plan(
        args.builder_sha256.lower(),
        args.tests_sha256.lower(),
        args.contract_sha256.lower(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
