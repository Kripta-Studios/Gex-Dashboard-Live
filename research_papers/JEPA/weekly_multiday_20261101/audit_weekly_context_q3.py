"""Independent numeric audit of the causal Q3 state-60 context extension.

The auditor never imports the Q3 producer and never opens option outcomes.  It
admits a closed producer package, loads sealed daily raw caches with the frozen
cache module, and independently reruns only the frozen feature functions needed
for state 60.
"""

from __future__ import annotations

# Native thread limits must precede NumPy imports.
# ruff: noqa: E402

import os

for _variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
):
    os.environ[_variable] = "1"

import argparse
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


WEEK = Path(__file__).resolve().parent
FROZEN = WEEK.parent / "level_oracle_20261018"
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
SOURCE_ROOT = Path(r"D:\ThetaData\data_options")
PRODUCER_ROOT = BASE / "h2_context_q3_1030_01"
OUTPUT_ROOT = BASE / "h2_context_q3_1030_audit_01"
CALENDAR_ROOT = BASE / "h2_q3_partial_calendar_01"
CONTRACT = WEEK / "Q3_CONTEXT_EXTENSION_CONTRACT_20261101.md"
PRODUCER = WEEK / "build_weekly_context_q3.py"

CONTRACT_SHA256 = "8775399421be05d7cee9ce4d08190fe374906ecb989f6e93c5d3469db29bc4ed"
BUILD_CACHE_SHA256 = "985e87dcbd1e73289b58e4576445e47e73a6edea13e5ac73dde3ad629180d69f"
FEATURES_SHA256 = "b5c63f918319f844793abb3346a34515526073374f5e71af2129a94f2369d4e0"
LEVEL_ENGINE_SHA256 = "70cc5d20990d971d16299fd008ff8e05ac99f99a6a2917a202fcb9a5f413b7c6"
FEATURE_CONTRACT_SHA256 = (
    "777890230663b0f683d0007117c58b5818047699fe8b25d27b5b819bac7f83db"
)
FEATURE_CONTRACT = (
    BASE.parent
    / "level_oracle_20261018"
    / "session_clock_dataset_v1"
    / "feature_contract.json"
)
CALENDAR_JSON_SHA256 = (
    "ac9bd2569d91e9bd9b0475d6f5e2d5400b2816cc1d1d0d9ec98c69e4dbe2e72b"
)
CALENDAR_PARQUET_SHA256 = (
    "e16ef041efadc0f6914585540e19e9c04fcb05f1597952137e4f5bcf06de8c78"
)
CALENDAR_MANIFEST_SHA256 = (
    "5a530747f2c97704869d87c04d09bba3cc00125f38a8a78454c2d459a2ea502c"
)

TICKERS = ("SPY", "QQQ", "SPXW")
KINDS = ("greeks", "oi")
STATE_I = 60
EXPECTED = {
    "identities": 165,
    "sources": 330,
    "present_sources": 318,
    "missing_sources": 12,
    "available_identities": 153,
    "missing_identities": 12,
}
MISSING_GREEK_DATES = {
    "20260701",
    "20260707",
    "20260710",
    "20260716",
    "20260826",
    "20260901",
}
ARRAY_SCHEMA = {
    "state_i": ((1,), "int16"),
    "base": ((1, 81), "float32"),
    "tokens": ((1, 20, 45), "float32"),
    "maps": ((1, 20, 5, 64), "float32"),
    "token_mask": ((1, 20), "bool"),
    "bar_mask": ((1, 20), "bool"),
    "map_mask": ((1, 20, 5), "float32"),
    "bar_end_i": ((1, 20), "int16"),
    "state_valid": ((1,), "bool"),
}
CONTEXT_KEYS = {
    "ticker",
    "date",
    "source_status",
    "close_i",
    "state_i",
    "status",
    "state_valid",
    "context_81",
    "token_mask_20",
    "bar_mask_20",
    "map_mask_20x5",
    "bar_end_i_20",
    "sources",
}


class Q3AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Q3AuditError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_link_or_reparse(path: Path) -> bool:
    current = path
    while True:
        if current.exists() or current.is_symlink():
            attributes = getattr(current.lstat(), "st_file_attributes", 0)
            if current.is_symlink() or attributes & 0x400:
                return True
        if current.parent == current:
            return False
        current = current.parent


def plain_path(
    path: Path, label: str, *, root: Path | None = None, file: bool = False
) -> Path:
    absolute = Path(os.path.abspath(path))
    require(absolute.exists(), f"missing {label}")
    require(not _is_link_or_reparse(absolute), f"link/reparse {label}")
    if root is not None:
        bounded = Path(os.path.abspath(root))
        require(
            absolute == bounded or absolute.is_relative_to(bounded),
            f"path outside {label} root",
        )
    if file:
        require(absolute.is_file(), f"regular file {label}")
    return absolute


def pin(path: Path) -> dict[str, Any]:
    path = plain_path(path, str(path), file=True)
    before = path.stat()
    digest = sha256_file(path)
    after = path.stat()
    require(
        (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
        f"file changed while hashing: {path}",
    )
    return {
        "bytes": after.st_size,
        "sha256": digest,
        "mtime_ns": after.st_mtime_ns,
    }


def pin_core(value: dict[str, Any]) -> dict[str, Any]:
    require(
        isinstance(value, dict) and set(value) >= {"bytes", "sha256"},
        "pin shape",
    )
    return {"bytes": value["bytes"], "sha256": value["sha256"]}


def path_pin(value: dict[str, Any]) -> dict[str, Any]:
    require(isinstance(value, dict) and "path" in value, "path pin shape")
    return {"path": value["path"], **pin_core(value)}


def verify_pin(path: Path, expected: dict[str, Any], label: str) -> dict[str, Any]:
    actual = pin(path)
    require(
        {"bytes": actual["bytes"], "sha256": actual["sha256"]} == pin_core(expected),
        f"pin mismatch {label}",
    )
    if "mtime_ns" in expected:
        require(actual["mtime_ns"] == expected["mtime_ns"], f"mtime mismatch {label}")
    return actual


def read_json(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(plain_path(path, label, file=True).read_text("utf-8"))
    require(isinstance(value, dict), f"JSON object required {label}")
    return value


def read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    rows = []
    with plain_path(path, label, file=True).open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL {label}:{number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"object required {label}:{number}")
            rows.append(value)
    return rows


def nominal_source(ticker: str, date: str, kind: str) -> Path:
    return (
        SOURCE_ROOT
        / ticker
        / kind
        / date[:4]
        / date[4:6]
        / f"{ticker}_{date}_{date}_{kind}.parquet"
    )


def validate_calendar_membership(
    calendar: dict[str, Any], payload: dict[str, Any]
) -> list[dict[str, Any]]:
    require(
        set(payload) == {"schema", "sessions", "rows"}
        and payload["schema"] == "weekly_h2_q3_partial_calendar_v1"
        and isinstance(payload["sessions"], list)
        and len(payload["sessions"]) == 55
        and payload["sessions"] == sorted(set(payload["sessions"])),
        "calendar JSON schema/sessions",
    )
    expected = [
        {"ticker": ticker, "date": date, "close_i": 390}
        for ticker in TICKERS
        for date in payload["sessions"]
    ]
    require(
        isinstance(calendar.get("rows"), list)
        and payload["rows"] == expected
        and calendar["rows"] == expected,
        "calendar rows",
    )
    return expected


def validate_physical_identity(
    item: dict[str, Any], path: Path, seen: set[tuple[int, int]]
) -> None:
    require(
        isinstance(item["physical_id"], list)
        and len(item["physical_id"]) == 2
        and all(type(value) is int for value in item["physical_id"]),
        "source physical identity",
    )
    identity = tuple(item["physical_id"])
    info = path.stat()
    require(
        item["physical_id"] == [int(info.st_dev), int(info.st_ino)],
        "source physical identity differs from filesystem",
    )
    require(identity not in seen, "source physical alias")
    seen.add(identity)


def validate_inventory(inventory: dict[str, Any], producer_sha256: str) -> None:
    require(
        set(inventory)
        == {
            "schema",
            "state_i",
            "calendar",
            "counts",
            "feature_schema",
            "authorities",
            "versions",
            "sources",
            "identities",
            "flags",
        },
        "inventory keys",
    )
    require(
        inventory["schema"] == "weekly_context_q3_1030_inventory_v1"
        and inventory["state_i"] == STATE_I,
        "inventory schema/state",
    )
    require(
        inventory["counts"]
        == {
            "identities": 165,
            "available": 153,
            "missing": 12,
            "sources": 330,
            "sources_present": 318,
            "sources_missing": 12,
        },
        "inventory counts",
    )
    feature_schema = inventory["feature_schema"]
    require(
        feature_schema.get("base_dim") == 81
        and feature_schema.get("token_dim") == 45
        and feature_schema.get("map_names")
        == ["fib", "call_oi", "put_oi", "call_gamma", "put_gamma"]
        and len(feature_schema.get("base_names", [])) == 81
        and len(set(feature_schema["base_names"])) == 81,
        "feature schema",
    )
    calendar = inventory["calendar"]
    require(set(calendar) == {"rows", "pins"}, "calendar keys")
    calendar_specs = {
        "calendar.json": (CALENDAR_ROOT / "calendar.json", CALENDAR_JSON_SHA256),
        "calendar.parquet": (
            CALENDAR_ROOT / "calendar.parquet",
            CALENDAR_PARQUET_SHA256,
        ),
        "calendar_manifest": (
            CALENDAR_ROOT / "manifest.json",
            CALENDAR_MANIFEST_SHA256,
        ),
    }
    require(set(calendar["pins"]) == set(calendar_specs), "calendar pin closure")
    for name, (path, digest) in calendar_specs.items():
        actual = pin(path)
        require(
            calendar["pins"][name]
            == {"path": str(path), "bytes": actual["bytes"], "sha256": digest}
            and actual["sha256"] == digest,
            f"calendar pin {name}",
        )
    calendar_payload = read_json(CALENDAR_ROOT / "calendar.json", "calendar JSON")
    expected_calendar_rows = validate_calendar_membership(calendar, calendar_payload)
    authority_specs = {
        "contract": (CONTRACT, CONTRACT_SHA256),
        **calendar_specs,
        "feature_contract": (FEATURE_CONTRACT, FEATURE_CONTRACT_SHA256),
        "build_cache.py": (FROZEN / "build_cache.py", BUILD_CACHE_SHA256),
        "features.py": (FROZEN / "features.py", FEATURES_SHA256),
        "level_engine.py": (FROZEN / "level_engine.py", LEVEL_ENGINE_SHA256),
        "build_weekly_context_q3.py": (PRODUCER, producer_sha256),
    }
    authorities = inventory["authorities"]
    require(set(authorities) == set(authority_specs), "authority closure")
    for name, (path, digest) in authority_specs.items():
        actual = pin(path)
        require(
            authorities[name]
            == {"path": str(path), "bytes": actual["bytes"], "sha256": digest}
            and actual["sha256"] == digest,
            f"authority {name}",
        )
    require(
        set(inventory["versions"])
        == {"python", "numpy", "pandas", "pyarrow", "exchange-calendars"}
        and all(
            isinstance(value, str) and value for value in inventory["versions"].values()
        ),
        "inventory versions",
    )
    require(
        inventory["flags"]
        == {
            "values_read": False,
            "raw_read": False,
            "outcomes_read": False,
            "actions_read": False,
            "labels_read": False,
            "oracle_read": False,
            "models_fit": False,
        },
        "inventory flags",
    )
    sources = inventory["sources"]
    require(isinstance(sources, list) and len(sources) == 330, "source count")
    expected_order = []
    source_index = {}
    present = missing = 0
    physical_ids = set()
    for item in sources:
        require(
            isinstance(item, dict)
            and item.get("ticker") in TICKERS
            and item.get("kind") in KINDS,
            "source identity",
        )
        identity = (item["ticker"], item["date"], item["kind"])
        require(identity not in source_index, "duplicate source identity")
        expected_order.append(identity)
        source_index[identity] = item
        nominal = nominal_source(*identity)
        require(Path(item["path"]) == nominal, "non-nominal source path")
        should_be_missing = (
            item["kind"] == "greeks"
            and item["ticker"] in {"SPY", "QQQ"}
            and item["date"] in MISSING_GREEK_DATES
        )
        require(item["exists"] is (not should_be_missing), "source coverage changed")
        require(
            set(item)
            == {
                "ticker",
                "date",
                "kind",
                "path",
                "exists",
                "bytes",
                "mtime_ns",
                "sha256",
                "rows",
                "schema",
                "clock_basis",
                "physical_id",
            },
            "source record keys",
        )
        metadata_keys = (
            "bytes",
            "sha256",
            "mtime_ns",
            "rows",
            "schema",
            "clock_basis",
            "physical_id",
        )
        if should_be_missing:
            require(
                all(item.get(key) is None for key in metadata_keys),
                "missing source has metadata",
            )
            require(
                not nominal.exists() and not nominal.is_symlink(),
                "missing source appeared",
            )
            missing += 1
        else:
            require(
                all(item.get(key) is not None for key in metadata_keys)
                and item["clock_basis"] == "NATIVE_STORED_TIMESTAMP"
                and isinstance(item["schema"], list)
                and all(
                    isinstance(field, dict)
                    and set(field) == {"name", "type", "nullable"}
                    for field in item["schema"]
                ),
                "present source metadata",
            )
            verify_pin(nominal, item, f"source {identity}")
            validate_physical_identity(item, nominal, physical_ids)
            present += 1
    require(
        expected_order
        == sorted(
            expected_order,
            key=lambda value: (
                TICKERS.index(value[0]),
                value[1],
                KINDS.index(value[2]),
            ),
        ),
        "source order",
    )
    require((present, missing) == (318, 12), "source present/missing counts")
    identities = inventory["identities"]
    require(isinstance(identities, list) and len(identities) == 165, "identity count")
    seen = set()
    for item in identities:
        key = (item.get("ticker"), item.get("date"))
        require(key not in seen and key[0] in TICKERS, "duplicate/invalid identity")
        seen.add(key)
        greek, oi = source_index[key + ("greeks",)], source_index[key + ("oi",)]
        expected_status = (
            "COMPLETE" if greek["exists"] and oi["exists"] else "MISSING_SOURCE"
        )
        require(
            set(item) == {"ticker", "date", "close_i", "status", "sources"}
            and item.get("close_i") == 390
            and item.get("status") == expected_status
            and item.get("sources") == {"greeks": greek, "oi": oi},
            "identity/source binding",
        )
    require(
        [(row["ticker"], row["date"]) for row in identities]
        == [(row["ticker"], row["date"]) for row in expected_calendar_rows],
        "identity order",
    )


def validate_inventory_binding(
    root: Path,
    inventory_path: Path,
    inventory_sha256: str,
    producer_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = plain_path(root, "producer root")
    inventory_path = plain_path(inventory_path, "inventory", root=root, file=True)
    require(inventory_path == root / "inventory.json", "inventory location")
    inventory_pin = pin(inventory_path)
    require(inventory_pin["sha256"] == inventory_sha256, "inventory authority")
    receipt_path = plain_path(
        root / "inventory_manifest.json",
        "inventory manifest",
        root=root,
        file=True,
    )
    receipt = read_json(receipt_path, "inventory manifest")
    require(
        receipt
        == {
            "schema": "weekly_context_q3_1030_inventory_manifest_v1",
            "inventory.json": pin_core(inventory_pin),
        },
        "inventory receipt",
    )
    inventory = read_json(inventory_path, "inventory")
    validate_inventory(inventory, producer_sha256)
    binding = {
        "inventory": {"path": str(inventory_path), **inventory_pin},
        "receipt": {"path": str(receipt_path), **pin(receipt_path)},
    }
    for name, value in inventory["authorities"].items():
        binding[f"authority:{name}"] = {
            "path": value["path"],
            **pin(Path(value["path"])),
        }
    return inventory, binding


def import_frozen_modules() -> tuple[Any, Any, Any, dict[str, Any]]:
    expected = {
        "build_cache": (FROZEN / "build_cache.py", BUILD_CACHE_SHA256),
        "level_engine": (FROZEN / "level_engine.py", LEVEL_ENGINE_SHA256),
        "features": (FROZEN / "features.py", FEATURES_SHA256),
    }
    modules = {}
    previous = {name: sys.modules.get(name) for name in expected}
    try:
        for name in ("build_cache", "level_engine", "features"):
            path, digest = expected[name]
            path = plain_path(path, f"frozen {name}", root=FROZEN, file=True)
            require(sha256_file(path) == digest, f"frozen module pin {name}")
            specification = importlib.util.spec_from_file_location(name, path)
            require(
                specification is not None and specification.loader is not None,
                f"module spec {name}",
            )
            module = importlib.util.module_from_spec(specification)
            sys.modules[name] = module
            specification.loader.exec_module(module)
            imported_path = Path(os.path.abspath(module.__file__))
            require(
                imported_path == path
                and not _is_link_or_reparse(imported_path)
                and sha256_file(imported_path) == digest,
                f"module shadowing {name}",
            )
            modules[name] = module
    except BaseException:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        raise
    versions = {
        "python": sys.version,
        "numpy": importlib.metadata.version("numpy"),
        "pandas": importlib.metadata.version("pandas"),
        "pyarrow": importlib.metadata.version("pyarrow"),
        "exchange-calendars": importlib.metadata.version("exchange_calendars"),
    }
    imports = {
        name: str(Path(os.path.abspath(module.__file__)))
        for name, module in modules.items()
    }
    require(
        modules["features"].build_cache is modules["build_cache"]
        and modules["features"].level_engine is modules["level_engine"],
        "frozen module binding",
    )
    return (
        modules["build_cache"],
        modules["features"],
        modules["level_engine"],
        {"versions": versions, "imports": imports},
        previous,
    )


def restore_frozen_modules(previous: dict[str, Any]) -> None:
    for name, module in previous.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


def validate_source_schemas(sources: list[dict[str, Any]], build_cache: Any) -> None:
    required = {
        "greeks": set(build_cache.GREEK_COLUMNS),
        "oi": set(build_cache.OI_COLUMNS),
    }
    for item in sources:
        if not item["exists"]:
            continue
        require(
            type(item["rows"]) is int and item["rows"] >= 0,
            "source row count",
        )
        names = [field["name"] for field in item["schema"]]
        require(
            len(names) == len(set(names)) and not required[item["kind"]] - set(names),
            f"source required schema {item['kind']}",
        )


def verify_frozen_module_closure() -> None:
    for name, path, digest in (
        ("build_cache", FROZEN / "build_cache.py", BUILD_CACHE_SHA256),
        ("features", FROZEN / "features.py", FEATURES_SHA256),
        ("level_engine", FROZEN / "level_engine.py", LEVEL_ENGINE_SHA256),
    ):
        path = plain_path(path, f"closing frozen {name}", root=FROZEN, file=True)
        require(sha256_file(path) == digest, f"closing frozen module {name}")


def validate_state_arrays(arrays: dict[str, np.ndarray], label: str) -> None:
    require(set(arrays) == set(ARRAY_SCHEMA), f"array names {label}")
    for name, (shape, dtype) in ARRAY_SCHEMA.items():
        value = arrays[name]
        require(
            isinstance(value, np.ndarray)
            and value.shape == shape
            and str(value.dtype) == dtype,
            f"array schema {label}:{name}",
        )
    require(
        np.array_equal(arrays["state_i"], np.asarray([STATE_I], dtype=np.int16)),
        f"state index {label}",
    )
    for name in ("base", "tokens", "maps", "map_mask"):
        require(np.isfinite(arrays[name]).all(), f"nonfinite {label}:{name}")
    require(
        np.all((arrays["map_mask"] >= 0) & (arrays["map_mask"] <= 1)),
        f"map mask range {label}",
    )
    bar_mask = arrays["bar_mask"][0]
    bar_end = arrays["bar_end_i"][0]
    require(
        np.all(bar_end[bar_mask] >= 0) and np.all(bar_end[bar_mask] < STATE_I),
        f"causal bar ends {label}",
    )
    require(np.all(bar_end[~bar_mask] == -1), f"masked bar ends {label}")


def load_npz(path: Path, expected: dict[str, Any], label: str) -> dict[str, np.ndarray]:
    path = plain_path(path, label, file=True)
    verify_pin(path, expected, label)
    with np.load(path, allow_pickle=False) as archive:
        require(set(archive.files) == set(ARRAY_SCHEMA), f"NPZ names {label}")
        arrays = {name: archive[name] for name in ARRAY_SCHEMA}
    validate_state_arrays(arrays, label)
    verify_pin(path, expected, f"closing {label}")
    return arrays


def compare_arrays(
    recomputed: dict[str, np.ndarray], stored: dict[str, np.ndarray], label: str
) -> None:
    validate_state_arrays(recomputed, f"recomputed {label}")
    validate_state_arrays(stored, f"stored {label}")
    for name in ARRAY_SCHEMA:
        require(
            np.array_equal(recomputed[name], stored[name]),
            f"array mismatch {label}:{name}",
        )


def validate_context_row(
    row: dict[str, Any], arrays: dict[str, np.ndarray] | None
) -> None:
    require(set(row) == CONTEXT_KEYS, "context row keys")
    require(row["close_i"] == 390 and row["state_i"] == STATE_I, "context clock")
    if arrays is None:
        require(
            row["source_status"] == "MISSING_SOURCE"
            and row["status"] == "CONTEXT_MISSING_SOURCE"
            and row["state_valid"] is None
            and all(
                row[name] is None
                for name in (
                    "context_81",
                    "token_mask_20",
                    "bar_mask_20",
                    "map_mask_20x5",
                    "bar_end_i_20",
                )
            ),
            "missing context row",
        )
        return
    require(
        row["source_status"] == "COMPLETE"
        and row["status"] == "CONTEXT_AVAILABLE"
        and type(row["state_valid"]) is bool
        and row["state_valid"] == bool(arrays["state_valid"][0]),
        "available context status",
    )
    comparisons = {
        "context_81": arrays["base"][0].tolist(),
        "token_mask_20": arrays["token_mask"][0].tolist(),
        "bar_mask_20": arrays["bar_mask"][0].tolist(),
        "map_mask_20x5": arrays["map_mask"][0].tolist(),
        "bar_end_i_20": arrays["bar_end_i"][0].tolist(),
    }
    for name, expected in comparisons.items():
        actual = np.asarray(row[name])
        reference = np.asarray(expected)
        require(
            actual.shape == reference.shape and np.array_equal(actual, reference),
            f"context projection {name}",
        )


def rehash_binding(binding: dict[str, dict[str, Any]]) -> None:
    for label, value in binding.items():
        verify_pin(
            Path(value["path"]),
            {
                key: value[key]
                for key in ("bytes", "sha256", "mtime_ns")
                if key in value
            },
            f"closing {label}",
        )


def audit_identity(
    *,
    identity: dict[str, Any],
    context_row: dict[str, Any],
    root: Path,
    build_cache: Any,
    features: Any,
) -> dict[str, Any]:
    ticker, date = identity["ticker"], identity["date"]
    label = f"{ticker}:{date}"
    if identity["status"] == "MISSING_SOURCE":
        require(
            isinstance(context_row["sources"], dict)
            and set(context_row["sources"])
            == {
                "greeks",
                "oi",
                "cache",
                "cache_metadata",
                "state",
                "state_metadata",
            }
            and context_row["sources"]["greeks"] == identity["sources"]["greeks"]
            and context_row["sources"]["oi"] == identity["sources"]["oi"]
            and all(
                context_row["sources"][name] is None
                for name in ("cache", "cache_metadata", "state", "state_metadata")
            ),
            f"missing source closure {label}",
        )
        validate_context_row(context_row, None)
        return {"ticker": ticker, "date": date, "status": "MISSING_SOURCE"}
    sources = context_row["sources"]
    require(
        isinstance(sources, dict)
        and set(sources)
        == {"greeks", "oi", "cache", "cache_metadata", "state", "state_metadata"},
        f"source closure {label}",
    )
    for kind in KINDS:
        require(
            sources[kind] == identity["sources"][kind], f"raw source binding {label}"
        )
        verify_pin(Path(sources[kind]["path"]), sources[kind], f"raw {label}:{kind}")
    expected_cache = root / "raw_cache" / ticker / f"{date}.npz"
    expected_state = root / "state60" / ticker / f"{date}.npz"
    require(
        Path(sources["cache"]["path"]) == expected_cache
        and Path(sources["cache_metadata"]["path"])
        == expected_cache.with_suffix(".json")
        and Path(sources["state"]["path"]) == expected_state
        and Path(sources["state_metadata"]["path"])
        == expected_state.with_suffix(".json"),
        f"cache/state path {label}",
    )
    cache_path = plain_path(expected_cache, f"raw cache {label}", root=root, file=True)
    cache_meta_path = plain_path(
        expected_cache.with_suffix(".json"),
        f"raw cache metadata {label}",
        root=root,
        file=True,
    )
    verify_pin(cache_path, sources["cache"], f"raw cache {label}")
    verify_pin(
        cache_meta_path, sources["cache_metadata"], f"raw cache metadata {label}"
    )
    cache_metadata = read_json(cache_meta_path, f"raw cache metadata {label}")
    require(
        cache_metadata.get("ticker") == ticker
        and cache_metadata.get("date") == date
        and cache_metadata.get("producer_sha256") == BUILD_CACHE_SHA256
        and cache_metadata.get("clock_basis") == "NATIVE_STORED_TIMESTAMP"
        and cache_metadata.get("oi_clock_basis") == "NATIVE_STORED_TIMESTAMP"
        and cache_metadata.get("source_hashes")
        == {
            sources[kind]["path"]: {
                key: sources[kind][key] for key in ("sha256", "bytes", "mtime_ns")
            }
            for kind in KINDS
        },
        f"raw cache metadata binding {label}",
    )
    raw = build_cache.load_day_cache(cache_path)
    recomputed = features.encode_states(
        features.build_day_feature_cache(raw), indices=[STATE_I]
    )
    stored = load_npz(expected_state, sources["state"], f"state NPZ {label}")
    compare_arrays(recomputed, stored, label)
    state_metadata = read_json(
        expected_state.with_suffix(".json"), f"state metadata {label}"
    )
    expected_state_schema = {
        name: {"shape": list(shape), "dtype": dtype}
        for name, (shape, dtype) in ARRAY_SCHEMA.items()
    }
    require(
        set(state_metadata)
        == {
            "version",
            "identity",
            "sha256",
            "bytes",
            "raw_cache",
            "raw_metadata",
            "dependencies",
            "array_schema",
            "state_valid",
            "outcomes_read",
        }
        and state_metadata.get("version") == "weekly_context_q3_state60_v1"
        and state_metadata.get("identity")
        == {"ticker": ticker, "date": date, "state_i": STATE_I}
        and state_metadata.get("sha256") == sources["state"]["sha256"]
        and state_metadata.get("bytes") == sources["state"]["bytes"]
        and state_metadata.get("raw_cache") == sources["cache"]
        and state_metadata.get("raw_metadata") == sources["cache_metadata"]
        and state_metadata.get("dependencies")
        == {
            "build_cache": BUILD_CACHE_SHA256,
            "features": FEATURES_SHA256,
            "level_engine": LEVEL_ENGINE_SHA256,
        }
        and state_metadata.get("array_schema") == expected_state_schema
        and type(state_metadata.get("state_valid")) is bool
        and state_metadata.get("state_valid") == bool(stored["state_valid"][0])
        and state_metadata.get("outcomes_read") is False,
        f"state metadata binding {label}",
    )
    validate_context_row(context_row, stored)
    for name in ("greeks", "oi", "cache", "cache_metadata", "state", "state_metadata"):
        verify_pin(
            Path(sources[name]["path"]), sources[name], f"closing {label}:{name}"
        )
    return {
        "ticker": ticker,
        "date": date,
        "status": "RECOMPUTED_EXACT",
        "state_valid": bool(stored["state_valid"][0]),
    }


def validate_artifact_map(
    root: Path,
    values: dict[str, Any],
    prefix: str,
    expected_relatives: set[str],
    label: str,
) -> dict[str, dict[str, Any]]:
    require(
        isinstance(values, dict) and set(values) == expected_relatives,
        f"{label} exact paths",
    )
    result = {}
    suffix_counts = {".npz": 0, ".json": 0}
    for relative, expected in values.items():
        relative_path = Path(relative)
        require(
            isinstance(relative, str)
            and relative_path.parts
            and relative_path.parts[0] == prefix
            and relative_path.suffix in suffix_counts
            and not relative_path.is_absolute()
            and ".." not in relative_path.parts,
            f"{label} relative path",
        )
        path = plain_path(
            root / relative_path, f"{label} {relative}", root=root, file=True
        )
        require(
            isinstance(expected, dict)
            and set(expected) == {"path", "bytes", "sha256"}
            and Path(expected["path"]) == path,
            f"{label} pin shape",
        )
        verify_pin(path, expected, f"{label} {relative}")
        result[relative] = {"path": str(path), **pin_core(expected)}
        suffix_counts[relative_path.suffix] += 1
    half = len(expected_relatives) // 2
    require(
        len(expected_relatives) % 2 == 0
        and suffix_counts == {".npz": half, ".json": half},
        f"{label} suffix counts",
    )
    return result


def admit_final_manifest(
    *,
    root: Path,
    manifest_sha256: str,
    inventory: dict[str, Any],
    inventory_binding: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = plain_path(
        root / "manifest.json", "producer manifest", root=root, file=True
    )
    manifest_pin = pin(manifest_path)
    require(manifest_pin["sha256"] == manifest_sha256, "producer manifest authority")
    manifest = read_json(manifest_path, "producer manifest")
    require(
        set(manifest)
        == {
            "schema",
            "status",
            "split",
            "state_i",
            "counts",
            "feature_names",
            "files",
            "authorities",
            "versions",
            "imports",
            "raw_cache_files",
            "state_files",
            "flags",
            "limitations",
        },
        "producer manifest keys",
    )
    require(
        manifest["schema"] == "weekly_context_q3_1030_manifest_v1"
        and manifest["status"]
        == "COMPLETE_CAUSAL_CONTEXT_Q3_1030_NOT_JOINED_NOT_EVALUATED"
        and manifest["split"] == "Q3_PARTIAL_2026_SEEN_DEVELOPMENT"
        and manifest["state_i"] == STATE_I,
        "producer manifest schema/status",
    )
    require(manifest["authorities"] == inventory["authorities"], "manifest authorities")
    require(manifest["versions"] == inventory["versions"], "manifest versions")
    require(
        manifest["flags"]
        == {
            "outcomes_read": False,
            "actions_read": False,
            "labels_read": False,
            "oracle_read": False,
            "models_fit": False,
            "development_seen": True,
            "promotion_approved": False,
        },
        "manifest flags",
    )
    require(
        manifest["counts"].get("identities") == 165
        and manifest["counts"].get("available") == 153
        and manifest["counts"].get("missing") == 12
        and manifest["counts"].get("state_valid_true", 0)
        + manifest["counts"].get("state_valid_false", 0)
        == 153
        and set(manifest["counts"])
        == {
            "identities",
            "available",
            "missing",
            "state_valid_true",
            "state_valid_false",
        },
        "manifest counts",
    )
    require(
        manifest["feature_names"] == inventory["feature_schema"]["base_names"],
        "manifest feature names",
    )
    files = manifest["files"]
    require(
        isinstance(files, dict)
        and set(files)
        == {
            "context.jsonl",
            "coverage.json",
            "inventory.json",
            "inventory_manifest.json",
        },
        "manifest file set",
    )
    file_binding = {}
    for name, expected in files.items():
        path = plain_path(root / name, f"manifest file {name}", root=root, file=True)
        actual = verify_pin(path, expected, f"manifest file {name}")
        file_binding[name] = {"path": str(path), **actual}
    require(
        pin_core(files["inventory.json"]) == pin_core(inventory_binding["inventory"])
        and pin_core(files["inventory_manifest.json"])
        == pin_core(inventory_binding["receipt"]),
        "manifest inventory binding",
    )
    complete = [row for row in inventory["identities"] if row["status"] == "COMPLETE"]
    raw_expected = {
        str(Path("raw_cache") / row["ticker"] / f"{row['date']}{suffix}")
        for row in complete
        for suffix in (".npz", ".json")
    }
    state_expected = {
        str(Path("state60") / row["ticker"] / f"{row['date']}{suffix}")
        for row in complete
        for suffix in (".npz", ".json")
    }
    require(len(raw_expected) == len(state_expected) == 306, "derived artifact closure")
    raw_files = validate_artifact_map(
        root,
        manifest["raw_cache_files"],
        "raw_cache",
        raw_expected,
        "raw cache map",
    )
    state_files = validate_artifact_map(
        root, manifest["state_files"], "state60", state_expected, "state map"
    )
    return manifest, {
        "manifest": {"path": str(manifest_path), **manifest_pin},
        **{f"file:{name}": value for name, value in file_binding.items()},
        **{f"raw:{name}": value for name, value in raw_files.items()},
        **{f"state:{name}": value for name, value in state_files.items()},
    }


def validate_coverage(
    coverage: dict[str, Any], manifest: dict[str, Any]
) -> dict[tuple[str, str], dict[str, Any]]:
    require(
        set(coverage)
        == {"schema", "state_i", "feature_names", "counts", "rows", "flags"}
        and coverage["schema"] == "weekly_context_q3_1030_coverage_v1"
        and coverage["state_i"] == STATE_I
        and coverage["feature_names"] == manifest["feature_names"]
        and coverage["counts"] == manifest["counts"],
        "coverage schema/binding",
    )
    require(
        coverage["flags"] == manifest["flags"],
        "coverage flags",
    )
    rows = coverage["rows"]
    require(isinstance(rows, list) and len(rows) == 165, "coverage rows")
    index = {}
    for row in rows:
        require(
            set(row) == {"ticker", "date", "source_status", "status", "state_valid"},
            "coverage row keys",
        )
        key = (row["ticker"], row["date"])
        require(key not in index, "duplicate coverage row")
        index[key] = row
    return index


def validate_result_counts(
    results: list[dict[str, Any]], counts: dict[str, int]
) -> None:
    require(
        sum(row["status"] == "RECOMPUTED_EXACT" for row in results) == 153
        and sum(row["status"] == "MISSING_SOURCE" for row in results) == 12,
        "audit result counts",
    )
    available = [row for row in results if row["status"] == "RECOMPUTED_EXACT"]
    require(
        sum(row["state_valid"] is True for row in available)
        == counts["state_valid_true"]
        and sum(row["state_valid"] is False for row in available)
        == counts["state_valid_false"],
        "state-valid count reconciliation",
    )


def execute_reviewed_audit(
    *,
    producer_root: Path,
    producer_manifest_sha256: str,
    inventory_path: Path,
    inventory_sha256: str,
    producer_sha256: str,
    auditor_sha256: str,
    output_dir: Path,
) -> dict[str, Any]:
    require(sha256_file(CONTRACT) == CONTRACT_SHA256, "contract pin")
    require(sha256_file(Path(__file__)) == auditor_sha256, "auditor pin")
    require(sha256_file(PRODUCER) == producer_sha256, "producer pin")
    root = plain_path(producer_root, "producer root")
    require(root == PRODUCER_ROOT, "producer root authority")
    inventory, inventory_binding = validate_inventory_binding(
        root, inventory_path, inventory_sha256, producer_sha256
    )
    manifest, artifact_binding = admit_final_manifest(
        root=root,
        manifest_sha256=producer_manifest_sha256,
        inventory=inventory,
        inventory_binding=inventory_binding,
    )
    build_cache, features, _level_engine, imported, previous = import_frozen_modules()
    try:
        require(imported["versions"] == manifest["versions"], "runtime versions")
        require(imported["imports"] == manifest["imports"], "runtime import paths")
        validate_source_schemas(inventory["sources"], build_cache)
        feature_contract = read_json(FEATURE_CONTRACT, "feature contract")
        names = list(features.BASE_NAMES)
        require(
            feature_contract["schema"]["base_names"]
            == inventory["feature_schema"]["base_names"]
            == manifest["feature_names"]
            == names,
            "ordered feature-name equality",
        )
        # Only after every metadata/code authority above is admitted do we read
        # producer numerical projections.
        context_rows = read_jsonl(root / "context.jsonl", "context rows")
        require(len(context_rows) == 165, "context row count")
        context_index = {}
        for row in context_rows:
            key = (row.get("ticker"), row.get("date"))
            require(key not in context_index, "duplicate context row")
            context_index[key] = row
        coverage = read_json(root / "coverage.json", "coverage")
        coverage_index = validate_coverage(coverage, manifest)
        require(
            coverage["feature_names"] == names
            and set(context_index) == set(coverage_index),
            "context/coverage universe",
        )
        expected_order = [
            (identity["ticker"], identity["date"])
            for identity in inventory["identities"]
        ]
        require(
            [(row["ticker"], row["date"]) for row in context_rows] == expected_order
            and [(row["ticker"], row["date"]) for row in coverage["rows"]]
            == expected_order,
            "context/coverage order",
        )
        results = []
        for identity in inventory["identities"]:
            key = (identity["ticker"], identity["date"])
            context_row, coverage_row = context_index[key], coverage_index[key]
            result = audit_identity(
                identity=identity,
                context_row=context_row,
                root=root,
                build_cache=build_cache,
                features=features,
            )
            require(
                coverage_row["source_status"] == context_row["source_status"]
                and coverage_row["status"] == context_row["status"]
                and coverage_row["state_valid"] == context_row["state_valid"],
                "coverage/context row",
            )
            results.append(result)
    finally:
        try:
            verify_frozen_module_closure()
        finally:
            restore_frozen_modules(previous)
    validate_result_counts(results, manifest["counts"])
    rehash_binding({**inventory_binding, **artifact_binding})
    # All 318 present source files are independently rehashed at close.
    for item in inventory["sources"]:
        if item["exists"]:
            verify_pin(Path(item["path"]), item, "closing raw source")
        else:
            path = Path(item["path"])
            require(
                not path.exists() and not path.is_symlink(),
                "missing source appeared at close",
            )
    output_parent = plain_path(output_dir.parent, "audit output parent")
    output_dir = output_parent / output_dir.name
    require(
        output_dir == OUTPUT_ROOT and not output_dir.exists(), "audit output authority"
    )
    output_dir.mkdir()
    report = {
        "schema": "weekly_context_q3_1030_independent_audit_v1",
        "status": "PASS_INDEPENDENT_CONTEXT_Q3_1030_GIVEN_FROZEN_FUNCTIONS",
        "counts": manifest["counts"],
        "inputs": {
            "producer_manifest": path_pin(artifact_binding["manifest"]),
            "inventory": path_pin(inventory_binding["inventory"]),
        },
        "implementation": {
            Path(__file__).name: auditor_sha256,
            PRODUCER.name: producer_sha256,
            CONTRACT.name: CONTRACT_SHA256,
            "build_cache.py": BUILD_CACHE_SHA256,
            "features.py": FEATURES_SHA256,
            "level_engine.py": LEVEL_ENGINE_SHA256,
        },
        "flags": {
            "raw_normalization_independently_reimplemented": False,
            "state60_recomputed_from_sealed_cache": True,
            "fit_performed": False,
            "outcomes_read": False,
            "models_fit": False,
            "development_seen": True,
            "promotion_approved": False,
        },
    }
    audit_path = output_dir / "audit.json"
    with audit_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
    rehash_binding({**inventory_binding, **artifact_binding})
    output_manifest = {
        "schema": "weekly_context_q3_1030_independent_audit_manifest_v1",
        "status": report["status"],
        "files": {"audit.json": pin_core(pin(audit_path))},
        "inputs": report["inputs"],
        "implementation": report["implementation"],
        "flags": report["flags"],
    }
    with (output_dir / "manifest.json").open(
        "x", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(
            json.dumps(output_manifest, indent=2, sort_keys=True, allow_nan=False)
            + "\n"
        )
    rehash_binding({**inventory_binding, **artifact_binding})
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent Q3 causal context audit")
    parser.add_argument("--execute-reviewed-audit", action="store_true")
    parser.add_argument("--producer-root", required=True)
    parser.add_argument("--producer-manifest-sha256", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--producer-sha256", required=True)
    parser.add_argument("--auditor-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    if not args.execute_reviewed_audit:
        parser.error("execution requires --execute-reviewed-audit")
    require(sha256_file(CONTRACT) == CONTRACT_SHA256, "contract pin")
    require(sha256_file(Path(__file__)) == args.auditor_sha256.lower(), "auditor pin")
    execute_reviewed_audit(
        producer_root=Path(args.producer_root),
        producer_manifest_sha256=args.producer_manifest_sha256.lower(),
        inventory_path=Path(args.inventory),
        inventory_sha256=args.inventory_sha256.lower(),
        producer_sha256=args.producer_sha256.lower(),
        auditor_sha256=args.auditor_sha256.lower(),
        output_dir=Path(args.output_dir),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
