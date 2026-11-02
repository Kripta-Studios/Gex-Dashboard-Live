"""Outcome-free admission and materialization of the sealed spot-cache paths.

This module is deliberately isolated from the value-path builder.  Its public
surface is the single ``extract_spot_paths`` function specified by
WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md.  It never opens option data,
feature arrays, state60 arrays, labels, models, or outcomes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path, PureWindowsPath
from typing import Any, Callable, ContextManager, Mapping, Sequence


class SpotPathError(RuntimeError):
    """Fail-closed violation of the spot-path admission contract."""


TICKER_ORDINAL = {"SPY": 0, "QQQ": 1, "SPXW": 2}
AUTHORITY_KEYS = (
    "h1_inventory",
    "h1_inventory_manifest",
    "h1_manifest",
    "q3_inventory",
    "q3_inventory_manifest",
    "q3_manifest",
)
OUTPUT_NAMES = (
    "cache_admission.jsonl",
    "spot_paths.parquet",
    "spot_coverage.jsonl",
)
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
DATE8 = re.compile(r"[0-9]{8}\Z")
REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

H1_CONTEXT_ROOT = Path(
    r"D:\GexResearchArtifacts\weekly_multiday_20261101\h2_context_1030_01"
)
Q3_CONTEXT_ROOT = Path(
    r"D:\GexResearchArtifacts\weekly_multiday_20261101\h2_context_q3_1030_01"
)
LEVEL_ROOT = Path(r"D:\GexResearchArtifacts\level_oracle_20261018")

EXPECTED_AUTHORITY_PINS: dict[str, dict[str, Any]] = {
    "h1_inventory": {
        "path": str(H1_CONTEXT_ROOT / "inventory.json"),
        "bytes": 1_829_496,
        "sha256": "b347523c8638825c822100cf78b5a03ab4f56fc948bc7aa23674b0b73866df5e",
    },
    "h1_inventory_manifest": {
        "path": str(H1_CONTEXT_ROOT / "inventory_manifest.json"),
        "bytes": 197,
        "sha256": "a7547c375a4de723b168ce2983b84ba98a35dd70aef24c82ed08c1e3c5358ea8",
    },
    "h1_manifest": {
        "path": str(H1_CONTEXT_ROOT / "manifest.json"),
        "bytes": 612_610,
        "sha256": "77aaf00d60accc071ff1f58ec099cee72bc3a4150f89e4ad41a601821a74a38a",
    },
    "q3_inventory": {
        "path": str(Q3_CONTEXT_ROOT / "inventory.json"),
        "bytes": 1_489_911,
        "sha256": "25da3398984c633a044eef4f20c5525c6224a1b076a5941d0311fae93eab68cf",
    },
    "q3_inventory_manifest": {
        "path": str(Q3_CONTEXT_ROOT / "inventory_manifest.json"),
        "bytes": 193,
        "sha256": "2b74c18e98366670e77e3d2a4fc19e260cd404e6959fbd7e140f2e88fd5050be",
    },
    "q3_manifest": {
        "path": str(Q3_CONTEXT_ROOT / "manifest.json"),
        "bytes": 172_889,
        "sha256": "1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66",
    },
}

H1_MISSING = {
    (ticker, date)
    for date in ("20260401", "20260409", "20260415")
    for ticker in ("SPY", "QQQ")
}
Q3_MISSING = {
    (ticker, date)
    for date in ("20260701", "20260707", "20260710", "20260716", "20260826", "20260901")
    for ticker in ("SPY", "QQQ")
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SpotPathError(message)


def _exact_keys(value: Mapping[str, Any], keys: set[str], label: str) -> None:
    _require(isinstance(value, Mapping), f"{label} must be a mapping")
    _require(set(value) == keys, f"{label} keys differ: {set(value)!r}")


def _canonical_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _same_path(left: Path | str, right: Path | str) -> bool:
    return _canonical_key(Path(left)) == _canonical_key(Path(right))


def _validate_sha(value: Any, label: str) -> str:
    _require(isinstance(value, str) and HEX64.fullmatch(value) is not None, f"invalid {label}")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    _require(isinstance(value, dict), f"JSON root must be object: {path}")
    return value


def _physical_id(info: os.stat_result) -> tuple[int, int]:
    return (int(info.st_dev), int(info.st_ino))


def _stat_object(info: os.stat_result) -> dict[str, Any]:
    return {
        "exists": True,
        "bytes": int(info.st_size),
        "mtime_ns": int(info.st_mtime_ns),
        "physical_id": [int(info.st_dev), int(info.st_ino)],
    }


def _validate_nominal_path(path: Path, expected: Path, label: str) -> Path:
    raw = os.fspath(path)
    pure = PureWindowsPath(raw)
    _require(pure.is_absolute(), f"{label} is not absolute: {raw}")
    _require(".." not in pure.parts and "." not in pure.parts, f"{label} has traversal: {raw}")
    _require(_same_path(path, expected), f"{label} is not nominal: {path} != {expected}")
    return expected


def _lstat_regular(path: Path, seen_physical: dict[tuple[int, int], str]) -> os.stat_result:
    current = Path(path.anchor)
    for part in path.parts[1:-1]:
        current = current / part
        info = current.lstat()
        attrs = int(getattr(info, "st_file_attributes", 0))
        _require(stat.S_ISDIR(info.st_mode), f"non-directory ancestor: {current}")
        _require(not stat.S_ISLNK(info.st_mode), f"symlink ancestor: {current}")
        _require(not attrs & REPARSE_FLAG, f"reparse ancestor: {current}")
    info = path.lstat()
    attrs = int(getattr(info, "st_file_attributes", 0))
    _require(stat.S_ISREG(info.st_mode), f"not a regular file: {path}")
    _require(not stat.S_ISLNK(info.st_mode), f"symlink file: {path}")
    _require(not attrs & REPARSE_FLAG, f"reparse file: {path}")
    _require(int(info.st_nlink) == 1, f"hardlinked file: {path}")
    identity = _physical_id(info)
    previous = seen_physical.get(identity)
    _require(previous is None or _same_path(previous, path), f"physical alias: {previous} and {path}")
    seen_physical[identity] = str(path)
    return info


def _pin_before(
    path: Path,
    expected_bytes: int | None,
    expected_sha: str | None,
    seen_physical: dict[tuple[int, int], str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    info = _lstat_regular(path, seen_physical)
    actual_sha = _sha256_file(path)
    if expected_bytes is not None:
        _require(int(info.st_size) == expected_bytes, f"byte drift: {path}")
    if expected_sha is not None:
        _require(actual_sha == expected_sha, f"hash drift: {path}")
    pin = {"path": str(path), "bytes": int(info.st_size), "sha256": actual_sha}
    return _stat_object(info), pin


def _pin_after(
    path: Path,
    before_stat: Mapping[str, Any],
    before_pin: Mapping[str, Any],
    seen_physical: dict[tuple[int, int], str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    info = _lstat_regular(path, seen_physical)
    actual_sha = _sha256_file(path)
    after_stat = _stat_object(info)
    after_pin = {"path": str(path), "bytes": int(info.st_size), "sha256": actual_sha}
    _require(after_stat == before_stat, f"stat changed during unit: {path}")
    _require(after_pin == before_pin, f"bytes changed during unit: {path}")
    return after_stat, after_pin


def _validate_authorities(
    authority_documents: Mapping[str, Any], authority_pins: Mapping[str, Any]
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]], dict[str, dict[str, Any]]]:
    _require(set(authority_documents) == set(AUTHORITY_KEYS), "authority_documents keys differ")
    _require(set(authority_pins) == set(AUTHORITY_KEYS), "authority_pins keys differ")
    for key in AUTHORITY_KEYS:
        pin = authority_pins[key]
        _exact_keys(pin, {"path", "bytes", "sha256"}, f"authority pin {key}")
        expected = EXPECTED_AUTHORITY_PINS[key]
        _validate_nominal_path(Path(pin["path"]), Path(expected["path"]), f"authority path {key}")
        _require(pin["bytes"] == expected["bytes"], f"authority bytes drift: {key}")
        _require(pin["sha256"] == expected["sha256"], f"authority hash drift: {key}")
        _require(isinstance(authority_documents[key], Mapping), f"authority document not object: {key}")

    h1_inventory = authority_documents["h1_inventory"]
    h1_inventory_manifest = authority_documents["h1_inventory_manifest"]
    h1_manifest = authority_documents["h1_manifest"]
    q3_inventory = authority_documents["q3_inventory"]
    q3_inventory_manifest = authority_documents["q3_inventory_manifest"]
    q3_manifest = authority_documents["q3_manifest"]

    _require(h1_inventory.get("schema") == "weekly_context_1030_inventory_v1", "H1 inventory schema")
    _require(h1_inventory.get("state_i") == 60, "H1 state_i")
    _require(h1_inventory.get("counts") == {"full": 2595, "identities": 2625, "missing": 6, "short": 24}, "H1 counts")
    _require(h1_inventory_manifest.get("schema") == "weekly_context_1030_inventory_manifest_v1", "H1 inventory-manifest schema")
    _require(h1_inventory_manifest.get("inventory.json") == {"bytes": 1_829_496, "sha256": EXPECTED_AUTHORITY_PINS["h1_inventory"]["sha256"]}, "H1 inventory cross-pin")
    _require(h1_manifest.get("schema") == "weekly_context_1030_manifest_v1", "H1 manifest schema")
    _require(h1_manifest.get("status") == "COMPLETE_CAUSAL_CONTEXT_1030_NOT_JOINED_NOT_EVALUATED", "H1 manifest status")
    _require(h1_manifest.get("state_i") == 60 and h1_manifest.get("counts") == h1_inventory.get("counts"), "H1 manifest counts")
    _require(isinstance(h1_manifest.get("npz_inputs"), list) and len(h1_manifest["npz_inputs"]) == 2619, "H1 npz input count")

    _require(q3_inventory.get("schema") == "weekly_context_q3_1030_inventory_v1", "Q3 inventory schema")
    _require(q3_inventory.get("state_i") == 60, "Q3 state_i")
    _require(q3_inventory.get("counts") == {"available": 153, "identities": 165, "missing": 12, "sources": 330, "sources_missing": 12, "sources_present": 318}, "Q3 inventory counts")
    _require(q3_inventory_manifest.get("schema") == "weekly_context_q3_1030_inventory_manifest_v1", "Q3 inventory-manifest schema")
    _require(q3_inventory_manifest.get("inventory.json") == {"bytes": 1_489_911, "sha256": EXPECTED_AUTHORITY_PINS["q3_inventory"]["sha256"]}, "Q3 inventory cross-pin")
    _require(q3_manifest.get("schema") == "weekly_context_q3_1030_manifest_v1", "Q3 manifest schema")
    _require(q3_manifest.get("status") == "COMPLETE_CAUSAL_CONTEXT_Q3_1030_NOT_JOINED_NOT_EVALUATED", "Q3 manifest status")
    _require(q3_manifest.get("state_i") == 60, "Q3 manifest state_i")
    _require(q3_manifest.get("counts") == {"available": 153, "identities": 165, "missing": 12, "state_valid_false": 0, "state_valid_true": 153}, "Q3 manifest counts")
    raw_cache_files = q3_manifest.get("raw_cache_files")
    _require(isinstance(raw_cache_files, Mapping) and len(raw_cache_files) == 306, "Q3 raw-cache pin count")

    h1_rows = _inventory_map(h1_inventory.get("identities"), "H1")
    q3_rows = _inventory_map(q3_inventory.get("identities"), "Q3")
    _require(len(h1_rows) == 2625 and len(q3_rows) == 165, "identity-map count")
    _require({key for key, row in h1_rows.items() if row.get("status") != "COMPLETE"} == H1_MISSING, "H1 missing set")
    _require({key for key, row in q3_rows.items() if row.get("status") != "COMPLETE"} == Q3_MISSING, "Q3 missing set")

    feature_inputs: dict[str, dict[str, Any]] = {}
    for pin in h1_manifest["npz_inputs"]:
        _validate_pin_shape(pin, "H1 feature input")
        canonical = _canonical_key(Path(pin["path"]))
        _require(canonical not in feature_inputs, "duplicate H1 feature input")
        feature_inputs[canonical] = dict(pin)
    for key, row in h1_rows.items():
        if row.get("status") == "COMPLETE":
            feature_pin = row.get("features")
            feature_metadata_pin = row.get("features_metadata")
            _validate_pin_shape(feature_pin, f"H1 features {key}")
            _validate_pin_shape(feature_metadata_pin, f"H1 features metadata {key}")
            _require(feature_inputs.get(_canonical_key(Path(feature_pin["path"]))) == feature_pin, f"H1 feature cross-pin {key}")
        else:
            _require(row.get("features") is None and row.get("features_metadata") is None, f"H1 missing pins {key}")

    q3_pins: dict[str, dict[str, Any]] = {}
    for relative, pin in raw_cache_files.items():
        _require(isinstance(relative, str), "Q3 raw-cache relative path")
        _validate_pin_shape(pin, f"Q3 raw-cache pin {relative}")
        canonical = _canonical_key(Path(pin["path"]))
        _require(canonical not in q3_pins, "duplicate Q3 raw-cache physical path")
        q3_pins[canonical] = dict(pin)
    return h1_rows, q3_rows, q3_pins


def _validate_pin_shape(pin: Any, label: str) -> None:
    _exact_keys(pin, {"path", "bytes", "sha256"}, label)
    _require(isinstance(pin["path"], str) and Path(pin["path"]).is_absolute(), f"{label} path")
    _require(isinstance(pin["bytes"], int) and not isinstance(pin["bytes"], bool) and pin["bytes"] >= 0, f"{label} bytes")
    _validate_sha(pin["sha256"], f"{label} sha256")


def _inventory_map(rows: Any, label: str) -> dict[tuple[str, str], dict[str, Any]]:
    _require(isinstance(rows, list), f"{label} identities not list")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        _require(isinstance(row, dict), f"{label} identity not object")
        ticker = row.get("ticker")
        date = row.get("date")
        _require(ticker in TICKER_ORDINAL and isinstance(date, str) and DATE8.fullmatch(date), f"{label} identity")
        key = (ticker, date)
        _require(key not in result, f"duplicate {label} identity {key}")
        _require(row.get("close_i") in (210, 390), f"{label} close_i {key}")
        _require(row.get("status") in ("COMPLETE", "MISSING_SOURCE"), f"{label} status {key}")
        result[key] = row
    return result


def _validate_calendar(calendar_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    _require(isinstance(calendar_rows, Sequence) and not isinstance(calendar_rows, (str, bytes)), "calendar_rows must be a sequence")
    _require(len(calendar_rows) == 2790, "calendar must contain 2790 identities")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    per_ticker = {ticker: 0 for ticker in TICKER_ORDINAL}
    for row in calendar_rows:
        _exact_keys(row, {"ticker", "date", "close_i"}, "calendar row")
        ticker = row["ticker"]
        date = row["date"]
        close_i = row["close_i"]
        _require(ticker in TICKER_ORDINAL, "calendar ticker")
        _require(isinstance(date, str) and DATE8.fullmatch(date), "calendar date")
        _require(isinstance(close_i, int) and not isinstance(close_i, bool) and close_i in (210, 390), "calendar close_i")
        key = (ticker, date)
        _require(key not in seen, f"duplicate calendar identity {key}")
        seen.add(key)
        per_ticker[ticker] += 1
        normalized.append({"ticker": ticker, "date": date, "close_i": close_i})
    expected_order = sorted(normalized, key=lambda row: (row["date"], TICKER_ORDINAL[row["ticker"]]))
    _require(normalized == expected_order, "calendar order differs")
    _require(per_ticker == {"SPY": 930, "QQQ": 930, "SPXW": 930}, "calendar ticker counts")
    _require(len({row["date"] for row in normalized}) == 930, "calendar session count")
    return normalized


def _expected_h1_paths(ticker: str, date: str, close_i: int, feature_path: Path) -> tuple[Path, Path, Path]:
    if close_i == 390:
        expected_feature = LEVEL_ROOT / "session_clock_dataset_v1" / "references" / ticker / date / "features.json"
        npz = LEVEL_ROOT / "cache_v1" / ticker / f"{date}.npz"
    else:
        expected_feature = LEVEL_ROOT / "session_clock_dataset_v1" / "short" / ticker / date / "features.json"
        npz = LEVEL_ROOT / "session_clock_dataset_v1" / "short" / ticker / date / "cache.npz"
    _validate_nominal_path(feature_path, expected_feature, "H1 feature metadata")
    return expected_feature, npz.with_suffix(".json"), npz


def _expected_q3_paths(ticker: str, date: str) -> tuple[Path, Path]:
    npz = Q3_CONTEXT_ROOT / "raw_cache" / ticker / f"{date}.npz"
    return npz.with_suffix(".json"), npz


def _validate_feature_metadata(
    value: Mapping[str, Any], ticker: str, date: str, npz_path: Path, inventory_row: Mapping[str, Any]
) -> tuple[str, str]:
    _require(value.get("version") == "SESSION_CLOCK_FEATURES_V1", "feature metadata version")
    _require(value.get("ticker") == ticker and value.get("date") == date, "feature metadata identity")
    _require(value.get("outcomes_read") is False, "feature metadata outcomes flag")
    source_path = value.get("source_path")
    _require(isinstance(source_path, str), "feature source path type")
    _validate_nominal_path(Path(source_path), npz_path, "feature source path")
    feature_pin = inventory_row["features"]
    _require(value.get("sha256") == feature_pin["sha256"], "feature NPZ metadata pin")
    binding = value.get("binding")
    _require(isinstance(binding, Mapping), "feature binding")
    source_sha = _validate_sha(binding.get("source_sha256"), "binding source hash")
    source_meta_sha = _validate_sha(binding.get("source_metadata_sha256"), "binding metadata hash")
    return source_sha, source_meta_sha


def _validate_cache_metadata(
    value: Mapping[str, Any], ticker: str, date: str, close_i: int, version: str,
    npz_pin: Mapping[str, Any],
) -> None:
    n = close_i + 1
    _require(value.get("version") == version, "cache metadata version")
    _require(value.get("ticker") == ticker and value.get("date") == date, "cache metadata identity")
    _require(value.get("timezone_convention") == "America/New_York naive", "cache timezone convention")
    _require(value.get("npz_bytes") == npz_pin["bytes"], "cache NPZ bytes")
    _require(value.get("sha256") == npz_pin["sha256"], "cache NPZ hash")
    array_schema = value.get("array_schema")
    _require(isinstance(array_schema, Mapping), "cache array_schema")
    expected = {
        "time_ns": {"shape": [n], "dtype": "int64"},
        "spot": {"shape": [n], "dtype": "float64"},
        "spot_valid": {"shape": [n], "dtype": "bool"},
    }
    for name, schema in expected.items():
        _require(array_schema.get(name) == schema, f"cache array schema {name}")


def _ranges(mask: Sequence[bool]) -> list[dict[str, int]]:
    result: list[dict[str, int]] = []
    start: int | None = None
    for index, value in enumerate(mask):
        if value and start is None:
            start = index
        elif not value and start is not None:
            result.append({"start_i": start, "end_i": index - 1})
            start = None
    if start is not None:
        result.append({"start_i": start, "end_i": len(mask) - 1})
    return result


def _json_line(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("xb") as stream:
        for row in rows:
            stream.write(_json_line(row))
        stream.flush()
        os.fsync(stream.fileno())


def _output_pin(path: Path) -> dict[str, Any]:
    info = path.stat()
    return {"path": str(path), "bytes": int(info.st_size), "sha256": _sha256_file(path)}


def _validate_final_counts(counts: Mapping[str, int]) -> None:
    expected_structural = {
        "identities": 2790,
        "available": 2772,
        "missing": 18,
        "full": 2766,
        "short": 24,
        "available_rows": 1_079_532,
        "missing_rows": 7_038,
        "path_rows": 1_086_570,
        "h1_available": 2619,
        "h1_missing": 6,
        "q3_available": 153,
        "q3_missing": 12,
        "admitted_inputs": 8163,
    }
    for key, expected in expected_structural.items():
        _require(counts[key] == expected, f"spot count {key}: {counts[key]} != {expected}")
    _require(
        counts["valid_rows"] + counts["invalid_rows"] == counts["path_rows"],
        "spot valid/invalid reconciliation",
    )


def _parquet_schema(pa: Any, np_version: str, pa_version: str) -> Any:
    metadata = {
        b"schema": b"weekly_zone_event_spot_paths_v1",
        b"numpy": np_version.encode("ascii"),
        b"pyarrow": pa_version.encode("ascii"),
    }
    return pa.schema(
        [
            pa.field("ticker", pa.utf8(), nullable=False),
            pa.field("ticker_ordinal", pa.int8(), nullable=False),
            pa.field("date", pa.utf8(), nullable=False),
            pa.field("session_kind", pa.utf8(), nullable=False),
            pa.field("cache_status", pa.utf8(), nullable=False),
            pa.field("minute_i", pa.int16(), nullable=False),
            pa.field("time_ns", pa.int64(), nullable=False),
            pa.field("spot", pa.float64(), nullable=True),
            pa.field("spot_valid", pa.bool_(), nullable=False),
            pa.field("missing_reason", pa.utf8(), nullable=True),
            pa.field("authority", pa.utf8(), nullable=False),
            pa.field("feature_metadata_path", pa.utf8(), nullable=True),
            pa.field("feature_metadata_sha256", pa.utf8(), nullable=True),
            pa.field("cache_metadata_path", pa.utf8(), nullable=True),
            pa.field("cache_metadata_sha256", pa.utf8(), nullable=True),
            pa.field("cache_npz_path", pa.utf8(), nullable=True),
            pa.field("cache_npz_sha256", pa.utf8(), nullable=True),
            pa.field("cache_version", pa.utf8(), nullable=True),
        ],
        metadata=metadata,
    )


def _load_spot_triplet(np: Any, npz_path: Path, date: str, n: int) -> tuple[Any, Any, Any]:
    """Load exactly the three contract-authorized members of one cache."""
    with np.load(npz_path, allow_pickle=False) as archive:
        archive_names = tuple(archive.files)
        _require(all(isinstance(name, str) for name in archive_names), "NPZ member names")
        _require(
            all(name in archive_names for name in ("time_ns", "spot", "spot_valid")),
            "NPZ spot members missing",
        )
        # These are intentionally the only archive member index operations.
        time_ns = np.asarray(archive["time_ns"])
        spot = np.asarray(archive["spot"])
        spot_valid = np.asarray(archive["spot_valid"])
        _require(time_ns.dtype == np.dtype("int64") and time_ns.shape == (n,), "time_ns dtype/shape")
        _require(spot.dtype == np.dtype("float64") and spot.shape == (n,), "spot dtype/shape")
        _require(spot_valid.dtype == np.dtype("bool") and spot_valid.shape == (n,), "spot_valid dtype/shape")
        time_ns = time_ns.copy()
        spot = spot.copy()
        spot_valid = spot_valid.copy()

    expected_start = np.datetime64(
        f"{date[:4]}-{date[4:6]}-{date[6:]}T09:30", "ns"
    ).astype(np.int64)
    expected_time = expected_start + np.arange(n, dtype=np.int64) * 60_000_000_000
    _require(np.array_equal(time_ns, expected_time), "cache clock differs")
    _require(
        bool(
            np.all(
                np.logical_or(
                    ~spot_valid,
                    np.logical_and(np.isfinite(spot), spot > 0.0),
                )
            )
        ),
        "valid spot is not finite positive",
    )
    return time_ns, spot, spot_valid


def _write_spot_parquet(path: Path, units: Sequence[Mapping[str, Any]], np: Any, pa: Any, pq: Any) -> None:
    schema = _parquet_schema(pa, np.__version__, pa.__version__)
    with path.open("xb") as raw_stream:
        writer = pq.ParquetWriter(
            raw_stream,
            schema,
            version="2.6",
            data_page_version="1.0",
            compression="zstd",
            compression_level=3,
            use_dictionary=True,
            write_statistics=True,
        )
        try:
            for unit in units:
                n = int(unit["close_i"]) + 1
                arrays = [
                    pa.array([unit["ticker"]] * n, type=pa.utf8()),
                    pa.array([unit["ticker_ordinal"]] * n, type=pa.int8()),
                    pa.array([unit["date"]] * n, type=pa.utf8()),
                    pa.array([unit["session_kind"]] * n, type=pa.utf8()),
                    pa.array([unit["cache_status"]] * n, type=pa.utf8()),
                    pa.array(np.arange(n, dtype=np.int16), type=pa.int16()),
                    pa.array(unit["time_ns"], type=pa.int64()),
                    pa.nulls(n, type=pa.float64()) if unit["spot"] is None else pa.array(unit["spot"], type=pa.float64(), from_pandas=False),
                    pa.array(unit["spot_valid"], type=pa.bool_()),
                    pa.array([unit["missing_reason"]] * n, type=pa.utf8()),
                    pa.array([unit["authority"]] * n, type=pa.utf8()),
                    pa.array([unit["feature_metadata_path"]] * n, type=pa.utf8()),
                    pa.array([unit["feature_metadata_sha256"]] * n, type=pa.utf8()),
                    pa.array([unit["cache_metadata_path"]] * n, type=pa.utf8()),
                    pa.array([unit["cache_metadata_sha256"]] * n, type=pa.utf8()),
                    pa.array([unit["npz_path"]] * n, type=pa.utf8()),
                    pa.array([unit["npz_sha256"]] * n, type=pa.utf8()),
                    pa.array([unit["cache_version"]] * n, type=pa.utf8()),
                ]
                table = pa.Table.from_arrays(arrays, schema=schema)
                writer.write_table(table, row_group_size=n)
        finally:
            writer.close()
        raw_stream.flush()
        os.fsync(raw_stream.fileno())


def extract_spot_paths(
    calendar_rows: Sequence[Mapping[str, Any]],
    output_dir: str | os.PathLike[str],
    authority_documents: Mapping[str, Any],
    authority_pins: Mapping[str, Any],
    unit_context: Callable[[str, str, list[str]], ContextManager[dict[str, Any]]],
) -> dict[str, Any]:
    """Admit the sealed spot caches and materialize dense minute paths."""
    calendar = _validate_calendar(calendar_rows)
    h1_rows, q3_rows, q3_pins = _validate_authorities(authority_documents, authority_pins)
    _require(set(h1_rows).isdisjoint(q3_rows), "H1/Q3 identity overlap")
    _require(set(h1_rows) | set(q3_rows) == {(row["ticker"], row["date"]) for row in calendar}, "calendar/inventory mismatch")

    staging = Path(output_dir)
    _require(staging.is_dir(), "output_dir must be an existing staging directory")
    output_paths = {name: staging / name for name in OUTPUT_NAMES}
    for name, path in output_paths.items():
        _require(not path.exists(), f"spot output already exists: {name}")

    # Runtime imports are intentionally delayed until all compact authorities and
    # the builder-supplied calendar have passed metadata-only validation.
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq

    _require(np.__version__ == "2.3.5", "NumPy version differs")
    _require(pa.__version__ == "23.0.1", "PyArrow version differs")

    units: list[dict[str, Any]] = []
    admission_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    admitted_inputs: dict[str, dict[str, Any]] = {}
    admitted_keys: set[str] = set()
    seen_physical: dict[tuple[int, int], str] = {}

    counts = {
        "identities": 0,
        "available": 0,
        "missing": 0,
        "full": 0,
        "short": 0,
        "available_rows": 0,
        "missing_rows": 0,
        "path_rows": 0,
        "valid_rows": 0,
        "invalid_rows": 0,
        "h1_available": 0,
        "h1_missing": 0,
        "q3_available": 0,
        "q3_missing": 0,
        "admitted_inputs": 0,
    }

    for row in calendar:
        ticker = row["ticker"]
        date = row["date"]
        close_i = row["close_i"]
        n = close_i + 1
        identity = (ticker, date)
        session_kind = "FULL" if close_i == 390 else "SHORT"
        authority = "H1" if identity in h1_rows else "Q3"
        inventory_row = h1_rows.get(identity, q3_rows.get(identity))
        _require(inventory_row is not None and inventory_row.get("close_i") == close_i, f"inventory/calendar close mismatch {identity}")
        available = inventory_row.get("status") == "COMPLETE"

        feature_path: Path | None = None
        cache_meta_path: Path | None = None
        npz_path: Path | None = None
        feature_expected_pin: Mapping[str, Any] | None = None
        cache_expected_pin: Mapping[str, Any] | None = None
        npz_expected_pin: Mapping[str, Any] | None = None
        cache_version: str | None = None

        if available and authority == "H1":
            feature_expected_pin = inventory_row["features_metadata"]
            feature_path, cache_meta_path, npz_path = _expected_h1_paths(
                ticker, date, close_i, Path(feature_expected_pin["path"])
            )
            cache_version = "LEVEL_DAILY_CACHE_V1" if close_i == 390 else "SESSION_CLOCK_CACHE_V1"
            context_paths = [str(feature_path), str(cache_meta_path), str(npz_path)]
        elif available:
            cache_meta_path, npz_path = _expected_q3_paths(ticker, date)
            cache_expected_pin = q3_pins.get(_canonical_key(cache_meta_path))
            npz_expected_pin = q3_pins.get(_canonical_key(npz_path))
            _require(cache_expected_pin is not None and npz_expected_pin is not None, f"Q3 pair missing {identity}")
            _validate_nominal_path(Path(cache_expected_pin["path"]), cache_meta_path, "Q3 cache metadata")
            _validate_nominal_path(Path(npz_expected_pin["path"]), npz_path, "Q3 cache NPZ")
            cache_version = "LEVEL_DAILY_CACHE_V1"
            context_paths = [str(cache_meta_path), str(npz_path)]
        else:
            context_paths = []

        with unit_context("CACHE_SPOT_PATH", f"{ticker}:{date}", context_paths) as details:
            _require(isinstance(details, dict), "unit_context must yield mutable dict")
            if not available:
                expected_missing = H1_MISSING if authority == "H1" else Q3_MISSING
                _require(identity in expected_missing, f"unexpected missing identity {identity}")
                reason = "MISSING_SOURCE"
                time_ns = np.datetime64(f"{date[:4]}-{date[4:6]}-{date[6:]}T09:30", "ns").astype(np.int64) + np.arange(n, dtype=np.int64) * 60_000_000_000
                spot_valid = np.zeros(n, dtype=np.bool_)
                details["substeps"] = ["DECLARED_MISSING"]
                details["counts"] = {"expected": n, "valid": 0, "invalid": n}
                details["pins_pre"] = {}
                details["pins_post"] = {}
                feature_before = feature_after = cache_before = cache_after = npz_before = npz_after = None
                feature_pin = cache_pin = npz_pin = None
                spot = None
            else:
                _require(cache_meta_path is not None and npz_path is not None and cache_version is not None, "available path resolution")
                before_stats: dict[str, dict[str, Any]] = {}
                before_pins: dict[str, dict[str, Any]] = {}
                if authority == "H1":
                    _require(feature_path is not None and feature_expected_pin is not None, "H1 feature path")
                    feature_before, feature_pin = _pin_before(
                        feature_path, feature_expected_pin["bytes"], feature_expected_pin["sha256"], seen_physical
                    )
                    before_stats[str(feature_path)] = feature_before
                    before_pins[str(feature_path)] = feature_pin
                    feature_metadata = _json_file(feature_path)
                    binding_npz_sha, binding_meta_sha = _validate_feature_metadata(
                        feature_metadata, ticker, date, npz_path, inventory_row
                    )
                    cache_before, cache_pin = _pin_before(cache_meta_path, None, binding_meta_sha, seen_physical)
                    npz_before, npz_pin = _pin_before(npz_path, None, binding_npz_sha, seen_physical)
                else:
                    feature_before = feature_pin = None
                    cache_before, cache_pin = _pin_before(
                        cache_meta_path, cache_expected_pin["bytes"], cache_expected_pin["sha256"], seen_physical
                    )
                    npz_before, npz_pin = _pin_before(
                        npz_path, npz_expected_pin["bytes"], npz_expected_pin["sha256"], seen_physical
                    )
                    binding_npz_sha = npz_pin["sha256"]
                    binding_meta_sha = cache_pin["sha256"]

                before_stats[str(cache_meta_path)] = cache_before
                before_stats[str(npz_path)] = npz_before
                before_pins[str(cache_meta_path)] = cache_pin
                before_pins[str(npz_path)] = npz_pin
                cache_metadata = _json_file(cache_meta_path)
                _validate_cache_metadata(cache_metadata, ticker, date, close_i, cache_version, npz_pin)

                time_ns, spot, spot_valid = _load_spot_triplet(np, npz_path, date, n)

                if feature_path is not None:
                    feature_after, feature_after_pin = _pin_after(
                        feature_path, feature_before, feature_pin, seen_physical
                    )
                else:
                    feature_after = feature_after_pin = None
                cache_after, cache_after_pin = _pin_after(
                    cache_meta_path, cache_before, cache_pin, seen_physical
                )
                npz_after, npz_after_pin = _pin_after(npz_path, npz_before, npz_pin, seen_physical)
                after_pins = {str(cache_meta_path): cache_after_pin, str(npz_path): npz_after_pin}
                if feature_path is not None:
                    after_pins[str(feature_path)] = feature_after_pin
                details["substeps"] = ["ADMIT_SPOT_METADATA", "LOAD_SPOT_TRIPLETS"]
                details["counts"] = {
                    "expected": n,
                    "valid": int(np.count_nonzero(spot_valid)),
                    "invalid": int(n - np.count_nonzero(spot_valid)),
                }
                details["pins_pre"] = dict(sorted(before_pins.items(), key=lambda item: _canonical_key(Path(item[0]))))
                details["pins_post"] = dict(sorted(after_pins.items(), key=lambda item: _canonical_key(Path(item[0]))))

                for pin in before_pins.values():
                    canonical = _canonical_key(Path(pin["path"]))
                    _require(canonical not in admitted_keys, f"input opened twice: {pin['path']}")
                    admitted_keys.add(canonical)
                    admitted_inputs[str(Path(os.path.abspath(pin["path"])))] = dict(pin)
                reason = None

        ticker_ordinal = TICKER_ORDINAL[ticker]
        valid_count = int(np.count_nonzero(spot_valid))
        invalid_count = n - valid_count
        invalid_ranges = _ranges([not bool(value) for value in spot_valid])
        valid_indices = np.flatnonzero(spot_valid)
        first_valid = int(valid_indices[0]) if valid_indices.size else None
        last_valid = int(valid_indices[-1]) if valid_indices.size else None
        feature_meta_path_text = str(feature_path) if feature_path is not None else None
        feature_meta_sha = feature_pin["sha256"] if feature_pin is not None else None
        cache_meta_path_text = str(cache_meta_path) if cache_meta_path is not None else None
        cache_meta_sha = cache_pin["sha256"] if cache_pin is not None else None
        npz_path_text = str(npz_path) if npz_path is not None else None
        npz_sha = npz_pin["sha256"] if npz_pin is not None else None

        stats_value = None
        if available:
            stats_value = {
                "feature_metadata": None if feature_path is None else {"before": feature_before, "after": feature_after},
                "cache_metadata": {"before": cache_before, "after": cache_after},
                "npz": {"before": npz_before, "after": npz_after},
            }
        admission_rows.append(
            {
                "ticker": ticker,
                "ticker_ordinal": ticker_ordinal,
                "date": date,
                "session_kind": session_kind,
                "close_i": close_i,
                "cache_status": "AVAILABLE" if available else "MISSING",
                "missing_reason": reason,
                "authority": authority,
                "feature_metadata_path": feature_meta_path_text,
                "feature_metadata_bytes": feature_pin["bytes"] if feature_pin is not None else None,
                "feature_metadata_sha256": feature_meta_sha,
                "cache_metadata_path": cache_meta_path_text,
                "cache_metadata_bytes": cache_pin["bytes"] if cache_pin is not None else None,
                "cache_metadata_sha256": cache_meta_sha,
                "npz_path": npz_path_text,
                "npz_bytes": npz_pin["bytes"] if npz_pin is not None else None,
                "npz_sha256": npz_sha,
                "cache_version": cache_version,
                "binding_source_sha256": npz_sha,
                "binding_source_metadata_sha256": cache_meta_sha,
                "stats": stats_value,
            }
        )
        coverage_rows.append(
            {
                "ticker": ticker,
                "ticker_ordinal": ticker_ordinal,
                "date": date,
                "session_kind": session_kind,
                "cache_status": "AVAILABLE" if available else "MISSING",
                "missing_reason": reason,
                "expected_count": n,
                "valid_count": valid_count,
                "invalid_count": invalid_count,
                "first_valid_i": first_valid,
                "last_valid_i": last_valid,
                "invalid_ranges": invalid_ranges,
                "metadata_path": cache_meta_path_text,
                "metadata_sha256": cache_meta_sha,
                "npz_path": npz_path_text,
                "npz_sha256": npz_sha,
            }
        )
        units.append(
            {
                "ticker": ticker,
                "ticker_ordinal": ticker_ordinal,
                "date": date,
                "session_kind": session_kind,
                "close_i": close_i,
                "cache_status": "AVAILABLE" if available else "MISSING",
                "missing_reason": reason,
                "authority": authority,
                "feature_metadata_path": feature_meta_path_text,
                "feature_metadata_sha256": feature_meta_sha,
                "cache_metadata_path": cache_meta_path_text,
                "cache_metadata_sha256": cache_meta_sha,
                "npz_path": npz_path_text,
                "npz_sha256": npz_sha,
                "cache_version": cache_version,
                "time_ns": time_ns,
                "spot": spot,
                "spot_valid": spot_valid,
            }
        )

        counts["identities"] += 1
        counts["full" if close_i == 390 else "short"] += 1
        counts["path_rows"] += n
        counts["valid_rows"] += valid_count
        counts["invalid_rows"] += invalid_count
        if available:
            counts["available"] += 1
            counts["available_rows"] += n
            counts[f"{authority.lower()}_available"] += 1
        else:
            counts["missing"] += 1
            counts["missing_rows"] += n
            counts[f"{authority.lower()}_missing"] += 1

    counts["admitted_inputs"] = len(admitted_inputs)
    _validate_final_counts(counts)

    output_rows = {
        "cache_admission.jsonl": 2790,
        "spot_paths.parquet": 1_086_570,
        "spot_coverage.jsonl": 2790,
    }
    outputs: dict[str, dict[str, Any]] = {}
    for name in OUTPUT_NAMES:
        path = output_paths[name]
        with unit_context("WRITE_OUTPUTS", name, [str(path)]) as details:
            _require(isinstance(details, dict), "output unit_context must yield mutable dict")
            if name == "cache_admission.jsonl":
                _write_jsonl(path, admission_rows)
            elif name == "spot_paths.parquet":
                _write_spot_parquet(path, units, np, pa, pq)
            else:
                _write_jsonl(path, coverage_rows)
            pin = _output_pin(path)
            outputs[name] = pin
            details["rows"] = output_rows[name]
            details["pin"] = dict(pin)
    admitted_sorted = {
        key: admitted_inputs[key]
        for key in sorted(admitted_inputs, key=os.path.normcase)
    }
    return {"outputs": outputs, "counts": counts, "admitted_inputs": admitted_sorted}


__all__ = ["SpotPathError", "extract_spot_paths"]
