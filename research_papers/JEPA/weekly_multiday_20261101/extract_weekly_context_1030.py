from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

WEEK = Path(__file__).resolve().parent
DATASET_ROOT = Path(
    r"D:\GexResearchArtifacts\level_oracle_20261018\session_clock_dataset_v1"
)
FEATURES_ROOT = Path(r"D:\GexResearchArtifacts\level_oracle_20261018\features_v1")
INDEX_PATH = DATASET_ROOT / "index.parquet"
OUTPUT_DIR = Path(
    r"D:\GexResearchArtifacts\weekly_multiday_20261101\h2_context_1030_01"
)
INDEX_SHA256 = "7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4"
CONTRACT_PATH = WEEK / "CAUSAL_CONTEXT_1030_EXTRACTION_CONTRACT_20261101.md"
AUTHORITIES = {
    "dataset_contract": (
        DATASET_ROOT / "dataset_contract.json",
        "437f480794dc89b80ff0c4999c3053d19d936fab779b99cb75b923433d641a43",
    ),
    "feature_contract": (
        DATASET_ROOT / "feature_contract.json",
        "777890230663b0f683d0007117c58b5818047699fe8b25d27b5b819bac7f83db",
    ),
    "completion": (
        DATASET_ROOT / "completion.json",
        "86e0c623ca47010434cb4c5d9b644cba0fc6457aacce2e680474dce6f1b932e5",
    ),
    "audit": (
        DATASET_ROOT.parent / "session_clock_dataset_v1_audit" / "audit.json",
        "678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9",
    ),
    "features_py": (
        WEEK.parent / "level_oracle_20261018" / "features.py",
        "b5c63f918319f844793abb3346a34515526073374f5e71af2129a94f2369d4e0",
    ),
    "extraction_contract": (
        CONTRACT_PATH,
        "c7e6dd53ab35b2b982f5871689768478600b5c90f61a5113f4fcabe41091ff02",
    ),
}
EXPECTED_COUNTS = {"identities": 2625, "full": 2595, "short": 24, "missing": 6}
STATUS = "COMPLETE_CAUSAL_CONTEXT_1030_NOT_JOINED_NOT_EVALUATED"
STATE_I = 60
ARRAY_NAMES = {
    "state_i",
    "base",
    "tokens",
    "maps",
    "token_mask",
    "bar_mask",
    "map_mask",
    "bar_end_i",
    "state_valid",
}
INDEX_COLUMNS = (
    "ticker",
    "date",
    "status",
    "cache_path",
    "day_root",
    "cache_npz_sha256",
    "cache_meta_sha256",
    "states_sha256",
    "levels_sha256",
    "actions_sha256",
    "labels_sha256",
    "causal_freeze_sha256",
    "close_i",
    "reused_full_session",
    "cache_meta_path",
    "features_path",
    "features_meta_path",
    "features_sha256",
    "features_meta_sha256",
    "action_features_path",
    "action_features_meta_path",
    "action_features_sha256",
    "action_features_meta_sha256",
    "evaluation_status",
)
SAFE_INDEX_PROJECTION = (
    "ticker",
    "date",
    "status",
    "close_i",
    "reused_full_session",
    "features_path",
    "features_meta_path",
    "features_sha256",
    "features_meta_sha256",
)


class ContextError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExtractionConfig:
    dataset_root: Path
    features_root: Path
    index_path: Path
    index_sha256: str
    authorities: dict[str, tuple[Path, str]]
    expected_counts: dict[str, int]


REAL_CONFIG = ExtractionConfig(
    DATASET_ROOT, FEATURES_ROOT, INDEX_PATH, INDEX_SHA256, AUTHORITIES, EXPECTED_COUNTS
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_link_or_reparse(path: Path) -> bool:
    current = Path(os.path.abspath(path))
    while True:
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            info = None
        if info is not None:
            attributes = getattr(info, "st_file_attributes", 0)
            if stat.S_ISLNK(info.st_mode) or attributes & getattr(
                stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400
            ):
                return True
        if current.parent == current:
            return False
        current = current.parent


def _plain_file(path: Path, root: Path, label: str) -> Path:
    path, root = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    if _is_link_or_reparse(path):
        raise ContextError(f"{label} link/reparse forbidden")
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ContextError(f"{label} outside declared root") from exc
    if not path.is_file():
        raise ContextError(f"{label} is not a regular file")
    return path


def _pinned_file(path: Path, expected: str, label: str) -> dict[str, Any]:
    path = Path(os.path.abspath(path))
    if _is_link_or_reparse(path) or not path.is_file():
        raise ContextError(f"{label} path guard failed")
    actual = sha256_file(path)
    if actual != expected:
        raise ContextError(f"{label} SHA-256 mismatch")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": actual}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContextError(f"invalid {label} JSON") from exc
    if not isinstance(value, dict):
        raise ContextError(f"{label} must be an object")
    return value


def _expected_array_schema(
    close_i: int, base_dim: int, token_dim: int, map_dim: int
) -> dict[str, tuple[tuple[int, ...], str]]:
    states = close_i - 74
    return {
        "state_i": ((states,), "int16"),
        "base": ((states, base_dim), "float32"),
        "tokens": ((states, 20, token_dim), "float32"),
        "maps": ((states, 20, map_dim, 64), "float32"),
        "token_mask": ((states, 20), "bool"),
        "bar_mask": ((states, 20), "bool"),
        "map_mask": ((states, 20, map_dim), "float32"),
        "bar_end_i": ((states, 20), "int16"),
        "state_valid": ((states,), "bool"),
    }


def _validate_feature_metadata(
    metadata: dict[str, Any], row: dict[str, Any], feature_schema: dict[str, Any]
) -> None:
    if metadata.get("version") != "SESSION_CLOCK_FEATURES_V1":
        raise ContextError("feature metadata version mismatch")
    if metadata.get("ticker") != row["ticker"] or metadata.get("date") != row["date"]:
        raise ContextError("feature metadata identity mismatch")
    expected_npz_sha256 = row.get("features_sha256") or row.get("features", {}).get(
        "sha256"
    )
    if (
        metadata.get("sha256") != expected_npz_sha256
        or metadata.get("schema") != feature_schema
    ):
        raise ContextError("feature metadata binding/schema mismatch")
    if metadata.get("outcomes_read") is not False:
        raise ContextError("feature metadata outcomes_read must be false")
    clock = metadata.get("session_clock")
    if (
        not isinstance(clock, dict)
        or clock.get("close_i") != row["close_i"]
        or clock.get("first_state") != STATE_I
    ):
        raise ContextError("feature metadata session clock mismatch")
    expected = _expected_array_schema(
        row["close_i"],
        feature_schema["base_dim"],
        feature_schema["token_dim"],
        len(feature_schema["map_names"]),
    )
    schema = metadata.get("array_schema")
    if not isinstance(schema, dict) or set(schema) != ARRAY_NAMES:
        raise ContextError("feature array schema names mismatch")
    for name, (shape, dtype) in expected.items():
        item = schema[name]
        if (
            not isinstance(item, dict)
            or set(item) != {"shape", "dtype"}
            or tuple(item["shape"]) != shape
            or item["dtype"] != dtype
        ):
            raise ContextError(f"feature array schema mismatch: {name}")


def prepare_inventory_payload(
    config: ExtractionConfig, extractor_sha256: str
) -> dict[str, Any]:
    dataset_root, features_root = (
        Path(os.path.abspath(config.dataset_root)),
        Path(os.path.abspath(config.features_root)),
    )
    if _is_link_or_reparse(dataset_root) or _is_link_or_reparse(features_root):
        raise ContextError("declared root link/reparse forbidden")
    extractor_pin = _pinned_file(Path(__file__), extractor_sha256, "extractor")
    authority_pins = {
        name: _pinned_file(path, expected, name)
        for name, (path, expected) in config.authorities.items()
    }
    if set(authority_pins) != {
        "dataset_contract",
        "feature_contract",
        "completion",
        "audit",
        "features_py",
        "extraction_contract",
    }:
        raise ContextError("authority pin closure mismatch")
    feature_contract = _load_json(
        Path(config.authorities["feature_contract"][0]), "feature contract"
    )
    feature_schema = feature_contract.get("schema")
    if (
        feature_contract.get("version") != "SESSION_CLOCK_FEATURES_V1"
        or feature_contract.get("outcomes_read") is not False
        or not isinstance(feature_schema, dict)
        or feature_schema.get("base_dim") != 81
        or len(feature_schema.get("base_names", [])) != 81
        or len(set(feature_schema["base_names"])) != 81
        or feature_schema.get("bars") != {"5m": 12, "15m": 8}
    ):
        raise ContextError("feature contract schema failed")
    dataset_contract = _load_json(
        Path(config.authorities["dataset_contract"][0]), "dataset contract"
    )
    completion = _load_json(Path(config.authorities["completion"][0]), "completion")
    if dataset_contract.get("expected_days") != config.expected_counts["identities"]:
        raise ContextError("dataset contract identity count mismatch")
    if (
        completion.get("available_days")
        != config.expected_counts["full"] + config.expected_counts["short"]
        or completion.get("missing_days") != config.expected_counts["missing"]
    ):
        raise ContextError("completion counts mismatch")
    index_path = _plain_file(config.index_path, dataset_root, "index")
    index_before = sha256_file(index_path)
    if index_before != config.index_sha256:
        raise ContextError("index SHA-256 mismatch")
    parquet = pq.ParquetFile(index_path)
    if tuple(parquet.schema_arrow.names) != INDEX_COLUMNS:
        raise ContextError("index schema names mismatch")
    expected_types = {
        "ticker": "string",
        "date": "string",
        "status": "string",
        "close_i": "int64",
        "reused_full_session": "bool",
        "features_path": "string",
        "features_meta_path": "string",
        "features_sha256": "string",
        "features_meta_sha256": "string",
    }
    for name, dtype in expected_types.items():
        if str(parquet.schema_arrow.field(name).type) != dtype:
            raise ContextError(f"index type mismatch: {name}")
    identities, seen = [], set()
    counts = {"identities": 0, "full": 0, "short": 0, "missing": 0}
    for batch in parquet.iter_batches(
        columns=list(SAFE_INDEX_PROJECTION), use_threads=False, batch_size=1024
    ):
        for row in batch.to_pylist():
            identity = (row["ticker"], row["date"])
            if identity in seen or row["ticker"] not in {"QQQ", "SPXW", "SPY"}:
                raise ContextError("duplicate or invalid index identity")
            seen.add(identity)
            counts["identities"] += 1
            status, close_i = row["status"], row["close_i"]
            if status == "MISSING_SOURCE":
                if (
                    close_i != 390
                    or row["reused_full_session"]
                    or any(
                        row[name] is not None
                        for name in (
                            "features_path",
                            "features_meta_path",
                            "features_sha256",
                            "features_meta_sha256",
                        )
                    )
                ):
                    raise ContextError("missing identity contains feature source")
                counts["missing"] += 1
                identities.append(
                    {
                        "ticker": row["ticker"],
                        "date": row["date"],
                        "status": status,
                        "close_i": close_i,
                        "reused_full_session": False,
                        "features": None,
                        "features_metadata": None,
                    }
                )
                continue
            if status != "COMPLETE" or close_i not in {210, 390}:
                raise ContextError("unsupported index status/clock")
            is_full = close_i == 390
            if bool(row["reused_full_session"]) != is_full:
                raise ContextError("full/short reuse flag mismatch")
            counts["full" if is_full else "short"] += 1
            npz_path = _plain_file(
                Path(row["features_path"]),
                features_root if is_full else dataset_root,
                "features NPZ",
            )
            meta_path = _plain_file(
                Path(row["features_meta_path"]), dataset_root, "features metadata"
            )
            meta_before = sha256_file(meta_path)
            if meta_before != row["features_meta_sha256"]:
                raise ContextError("feature metadata SHA-256 mismatch")
            metadata = _load_json(meta_path, "features metadata")
            _validate_feature_metadata(metadata, row, feature_schema)
            if sha256_file(meta_path) != meta_before:
                raise ContextError("feature metadata changed during inventory")
            identities.append(
                {
                    "ticker": row["ticker"],
                    "date": row["date"],
                    "status": status,
                    "close_i": close_i,
                    "reused_full_session": is_full,
                    "features": {
                        "path": str(npz_path),
                        "bytes": npz_path.stat().st_size,
                        "sha256": row["features_sha256"],
                    },
                    "features_metadata": {
                        "path": str(meta_path),
                        "bytes": meta_path.stat().st_size,
                        "sha256": meta_before,
                    },
                }
            )
    if (
        counts != config.expected_counts
        or parquet.metadata.num_rows != counts["identities"]
    ):
        raise ContextError(f"index support counts mismatch: {counts}")
    if sha256_file(index_path) != index_before:
        raise ContextError("index changed during inventory")
    identities.sort(key=lambda row: (row["ticker"], row["date"]))
    return {
        "schema": "weekly_context_1030_inventory_v1",
        "state_i": STATE_I,
        "counts": counts,
        "feature_schema": feature_schema,
        "index": {
            "path": str(index_path),
            "bytes": index_path.stat().st_size,
            "sha256": index_before,
        },
        "authorities": authority_pins,
        "extractor": extractor_pin,
        "identities": identities,
        "flags": {
            "npz_opened": False,
            "outcomes_read": False,
            "actions_read": False,
            "raw_read": False,
        },
    }


def _preserve_failure(staging: Path, exc: BaseException) -> None:
    try:
        _write_json(
            staging / "failure.json",
            {
                "status": "FAILED_PARTIAL_PRESERVED",
                "exception_type": type(exc).__name__,
                "message": str(exc),
            },
        )
    except BaseException:
        pass


def build_reviewed_inventory(
    config: ExtractionConfig, output_dir: Path, extractor_sha256: str
) -> dict[str, Any]:
    payload = prepare_inventory_payload(config, extractor_sha256)
    output_dir = Path(os.path.abspath(output_dir))
    if _is_link_or_reparse(output_dir) or output_dir.exists():
        raise ContextError("immutable output exists or is link/reparse")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent)
    )
    try:
        inventory = staging / "inventory.json"
        _write_json(inventory, payload)
        receipt = {
            "schema": "weekly_context_1030_inventory_manifest_v1",
            "inventory.json": {
                "bytes": inventory.stat().st_size,
                "sha256": sha256_file(inventory),
            },
        }
        _write_json(staging / "inventory_manifest.json", receipt)
        staging.rename(output_dir)
        return receipt
    except BaseException as exc:
        _preserve_failure(staging, exc)
        raise


def _validate_inventory_binding(
    output_dir: Path, inventory_path: Path, inventory_sha256: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    if _is_link_or_reparse(inventory_path) or not inventory_path.is_file():
        raise ContextError("inventory path guard failed")
    inventory_pin = {
        "bytes": inventory_path.stat().st_size,
        "sha256": sha256_file(inventory_path),
    }
    if inventory_pin["sha256"] != inventory_sha256:
        raise ContextError("inventory SHA-256 binding failed")
    receipt_path = output_dir / "inventory_manifest.json"
    if _is_link_or_reparse(receipt_path) or not receipt_path.is_file():
        raise ContextError("inventory manifest path guard failed")
    receipt = _load_json(receipt_path, "inventory manifest")
    if (
        set(receipt) != {"schema", "inventory.json"}
        or receipt.get("schema") != "weekly_context_1030_inventory_manifest_v1"
        or receipt["inventory.json"] != inventory_pin
    ):
        raise ContextError("inventory manifest binding failed")
    return inventory_pin, {
        "bytes": receipt_path.stat().st_size,
        "sha256": sha256_file(receipt_path),
    }


def _extract_identity(
    item: dict[str, Any], feature_schema: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    common = {
        "ticker": item["ticker"],
        "date": item["date"],
        "source_status": item["status"],
        "close_i": item["close_i"],
        "state_i": STATE_I,
    }
    if item["status"] == "MISSING_SOURCE":
        return (
            {
                **common,
                "status": "CONTEXT_MISSING_SOURCE",
                "state_valid": None,
                "context_81": None,
                "token_mask_20": None,
                "bar_mask_20": None,
                "map_mask_20x5": None,
                "bar_end_i_20": None,
                "sources": {"features": None, "features_metadata": None},
            },
            {**common, "status": "CONTEXT_MISSING_SOURCE", "state_valid": None},
        )
    npz_info, meta_info = item["features"], item["features_metadata"]
    npz_path, meta_path = Path(npz_info["path"]), Path(meta_info["path"])
    if (
        not npz_path.is_file()
        or _is_link_or_reparse(npz_path)
        or not meta_path.is_file()
        or _is_link_or_reparse(meta_path)
    ):
        raise ContextError("feature source path guard failed before array read")
    if (
        npz_path.stat().st_size != npz_info["bytes"]
        or meta_path.stat().st_size != meta_info["bytes"]
    ):
        raise ContextError("feature source size changed before array read")
    meta_before = sha256_file(meta_path)
    if meta_before != meta_info["sha256"]:
        raise ContextError("feature metadata changed before array read")
    metadata = _load_json(meta_path, "features metadata")
    _validate_feature_metadata(metadata, item, feature_schema)
    npz_before = sha256_file(npz_path)
    if npz_before != npz_info["sha256"]:
        raise ContextError("features NPZ SHA-256 mismatch before array read")
    expected = _expected_array_schema(
        item["close_i"],
        feature_schema["base_dim"],
        feature_schema["token_dim"],
        len(feature_schema["map_names"]),
    )
    with np.load(npz_path, allow_pickle=False) as arrays:
        if set(arrays.files) != ARRAY_NAMES:
            raise ContextError("NPZ array name closure mismatch")
        loaded = {name: arrays[name] for name in ARRAY_NAMES}
        for name, (shape, dtype) in expected.items():
            if loaded[name].shape != shape or str(loaded[name].dtype) != dtype:
                raise ContextError(f"NPZ shape/dtype mismatch: {name}")
        state_i = loaded["state_i"]
        expected_states = np.arange(STATE_I, item["close_i"] - 14, dtype=np.int16)
        if (
            not np.array_equal(state_i, expected_states)
            or np.count_nonzero(state_i == STATE_I) != 1
        ):
            raise ContextError("state_i order/uniqueness mismatch")
        for name in ("base", "tokens", "maps", "map_mask"):
            if not np.isfinite(loaded[name]).all():
                raise ContextError(f"non-finite feature array: {name}")
        if np.any((loaded["map_mask"] < 0) | (loaded["map_mask"] > 1)):
            raise ContextError("map_mask outside [0,1]")
        valid_bar, state_grid = loaded["bar_mask"], state_i[:, None]
        if np.any(loaded["bar_end_i"][valid_bar] < 0) or np.any(
            np.broadcast_to(state_grid, valid_bar.shape)[valid_bar]
            <= loaded["bar_end_i"][valid_bar]
        ):
            raise ContextError("valid bar_end_i is not causal")
        pos = int(np.flatnonzero(state_i == STATE_I)[0])
        bar_mask = loaded["bar_mask"][pos]
        bar_end = loaded["bar_end_i"][pos]
        if np.any(bar_end[bar_mask] >= STATE_I):
            raise ContextError("state60 valid bar_end_i must be less than 60")
        state_valid = bool(loaded["state_valid"][pos])
        row = {
            **common,
            "status": "CONTEXT_AVAILABLE",
            "state_valid": state_valid,
            "context_81": [float(v) for v in loaded["base"][pos]],
            "token_mask_20": [bool(v) for v in loaded["token_mask"][pos]],
            "bar_mask_20": [bool(v) for v in bar_mask],
            "map_mask_20x5": [
                [float(v) for v in values] for values in loaded["map_mask"][pos]
            ],
            "bar_end_i_20": [int(v) for v in bar_end],
            "sources": {"features": npz_info, "features_metadata": meta_info},
        }
    if sha256_file(npz_path) != npz_before or sha256_file(meta_path) != meta_before:
        raise ContextError("feature source changed during array read")
    source_pin = {
        "path": str(npz_path),
        "bytes": npz_path.stat().st_size,
        "sha256": npz_before,
    }
    return row, {
        **common,
        "status": "CONTEXT_AVAILABLE",
        "state_valid": state_valid,
        "npz_input": source_pin,
    }


def execute_reviewed_extraction(
    config: ExtractionConfig,
    output_dir: Path,
    inventory_path: Path,
    inventory_sha256: str,
    extractor_sha256: str,
) -> dict[str, Any]:
    output_dir, inventory_path = (
        Path(os.path.abspath(output_dir)),
        Path(os.path.abspath(inventory_path)),
    )
    if inventory_path != output_dir / "inventory.json":
        raise ContextError("inventory must be bound inside output root")
    current = prepare_inventory_payload(config, extractor_sha256)
    inventory_pin, receipt_pin = _validate_inventory_binding(
        output_dir, inventory_path, inventory_sha256
    )
    frozen = _load_json(inventory_path, "inventory")
    if current != frozen:
        raise ContextError("metadata inventory differs before first NPZ array")
    context_rows, coverage_rows, npz_inputs = [], [], []
    for item in frozen["identities"]:
        context, coverage = _extract_identity(item, frozen["feature_schema"])
        context_rows.append(context)
        if "npz_input" in coverage:
            npz_inputs.append(coverage.pop("npz_input"))
        coverage_rows.append(coverage)
    closing = prepare_inventory_payload(config, extractor_sha256)
    closing_inventory_pin, closing_receipt_pin = _validate_inventory_binding(
        output_dir, inventory_path, inventory_sha256
    )
    if (
        closing != frozen
        or closing_inventory_pin != inventory_pin
        or closing_receipt_pin != receipt_pin
    ):
        raise ContextError("metadata/inventory changed before publication")
    for name in ("context.jsonl", "coverage.json", "manifest.json"):
        if (output_dir / name).exists():
            raise FileExistsError(f"immutable artifact exists: {name}")
    staging = Path(tempfile.mkdtemp(prefix=".context1030.", dir=output_dir))
    try:
        context_path = staging / "context.jsonl"
        with context_path.open("x", encoding="utf-8") as handle:
            for row in context_rows:
                handle.write(
                    json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n"
                )
        coverage = {
            "schema": "weekly_context_1030_coverage_v1",
            "state_i": STATE_I,
            "feature_names": frozen["feature_schema"]["base_names"],
            "counts": frozen["counts"],
            "rows": coverage_rows,
            "flags": {
                "outcomes_read": False,
                "actions_read": False,
                "raw_read": False,
                "economic_join_performed": False,
            },
        }
        _write_json(staging / "coverage.json", coverage)
        files = {
            "context.jsonl": context_path,
            "coverage.json": staging / "coverage.json",
            "inventory.json": inventory_path,
            "inventory_manifest.json": output_dir / "inventory_manifest.json",
        }
        file_pins = {
            name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for name, path in files.items()
        }
        if (
            file_pins["inventory.json"] != closing_inventory_pin
            or file_pins["inventory_manifest.json"] != closing_receipt_pin
        ):
            raise ContextError("closing inventory pins changed before manifest")
        manifest = {
            "schema": "weekly_context_1030_manifest_v1",
            "status": STATUS,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "state_i": STATE_I,
            "counts": frozen["counts"],
            "feature_names": frozen["feature_schema"]["base_names"],
            "files": file_pins,
            "index": frozen["index"],
            "authorities": frozen["authorities"],
            "extractor": frozen["extractor"],
            "npz_inputs": npz_inputs,
            "flags": {
                "fit_performed": False,
                "outcomes_read": False,
                "actions_read": False,
                "raw_read": False,
                "economic_join_performed": False,
                "promotion_approved": False,
                "technical_ready": False,
            },
            "limitations": [
                "context is 0DTE and distinct from the weekly option expiration",
                "walls and gamma/OI are frozen proxies, not dealer positions",
                "stored availability assumptions do not prove observed live receipt",
                "Q3 context is not available from this audited support",
            ],
        }
        _write_json(staging / "manifest.json", manifest)
        for name in ("context.jsonl", "coverage.json", "manifest.json"):
            (staging / name).rename(output_dir / name)
        return manifest
    except BaseException as exc:
        _preserve_failure(staging, exc)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract audited causal 10:30 context without outcomes"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build-reviewed-inventory", action="store_true")
    mode.add_argument("--execute-reviewed-extraction", action="store_true")
    parser.add_argument("--dataset-root", default=str(DATASET_ROOT))
    parser.add_argument("--features-root", default=str(FEATURES_ROOT))
    parser.add_argument("--index", default=str(INDEX_PATH))
    parser.add_argument("--index-sha256", default=INDEX_SHA256)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--extractor-sha256", required=True)
    parser.add_argument("--inventory")
    parser.add_argument("--inventory-sha256")
    args = parser.parse_args()
    frozen_paths = (
        (args.dataset_root, DATASET_ROOT),
        (args.features_root, FEATURES_ROOT),
        (args.index, INDEX_PATH),
        (args.output_dir, OUTPUT_DIR),
    )
    if any(
        Path(os.path.abspath(a)) != Path(os.path.abspath(e)) for a, e in frozen_paths
    ):
        parser.error("real CLI roots are frozen; fixtures must use the Python API")
    if args.index_sha256.lower() != INDEX_SHA256:
        parser.error("real CLI index SHA-256 is frozen")
    if args.build_reviewed_inventory:
        if args.inventory or args.inventory_sha256:
            parser.error("inventory binding belongs only to extraction mode")
        build_reviewed_inventory(
            REAL_CONFIG, Path(args.output_dir), args.extractor_sha256.lower()
        )
    else:
        if not args.inventory or not args.inventory_sha256:
            parser.error("extraction mode requires --inventory and --inventory-sha256")
        execute_reviewed_extraction(
            REAL_CONFIG,
            Path(args.output_dir),
            Path(args.inventory),
            args.inventory_sha256.lower(),
            args.extractor_sha256.lower(),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
