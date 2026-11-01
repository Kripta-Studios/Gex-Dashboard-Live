from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

import pyarrow.compute as pc
import pyarrow.parquet as pq


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pinned(path: Path, expected: str):
    if sha256_file(path) != expected:
        raise RuntimeError("pilot helper pin mismatch")
    spec = importlib.util.spec_from_file_location("h2_clock_pilot_pinned", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load pilot helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def raw_key(value: Any) -> tuple[str, str]:
    return type(value).__name__, repr(value)


def diagnose(inventory_path: Path, inventory_sha: str, pilot_path: Path, pilot_sha: str) -> dict[str, Any]:
    if sha256_file(inventory_path) != inventory_sha:
        raise RuntimeError("inventory pin mismatch")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    pilot = load_pinned(pilot_path, pilot_sha)
    sources = {item["path"]: item for item in inventory["sources"]}
    cache: OrderedDict[str, None] = OrderedDict()
    sequence_index = 0
    for cover in inventory["coverage_plan"]:
        if cover["status"] != "PLANNED":
            continue
        for role in ("entry", "exit"):
            path_text = cover[f"{role}_path"]
            item = sources[path_text]
            if item["status"] != "INVENTORIED":
                continue
            if path_text in cache:
                cache.move_to_end(path_text)
                continue
            cache[path_text] = None
            if len(cache) > 16:
                cache.popitem(last=False)
            sequence_index += 1
            path = Path(path_text)
            if pilot._is_link_or_reparse(path):
                raise RuntimeError(f"source link/reparse guard failed: {path}")
            before = sha256_file(path)
            if before != item["sha256"]:
                raise RuntimeError(f"source pin mismatch: {path}")
            parquet = pq.ParquetFile(path)
            names = set(parquet.schema_arrow.names)
            clock_column = "timestamp" if "timestamp" in names else "underlying_timestamp"
            counts: dict[tuple[str, str], int] = {}
            first_error: dict[str, Any] | None = None
            invalid: list[dict[str, Any]] = []
            for batch in parquet.iter_batches(columns=[clock_column], use_threads=False, batch_size=65536):
                clock_array = batch.column(0)
                for row in pc.value_counts(clock_array).to_pylist():
                    value, count = row["values"], int(row["counts"])
                    key = raw_key(value)
                    counts[key] = counts.get(key, 0) + count
                    try:
                        pilot._parse_clock(value, cover["entry_date"] if role == "entry" else cover["exit_date"])
                    except Exception as exc:
                        failure = {"raw_type": key[0], "raw_repr": key[1], "error_type": type(exc).__name__, "error": str(exc)}
                        invalid.append(failure)
                        if first_error is None:
                            first_error = failure
            after = sha256_file(path)
            if after != before:
                raise RuntimeError(f"source changed during clock projection: {path}")
            if first_error is not None:
                frequencies = [
                    {"raw_type": key[0], "raw_repr": key[1], "rows": counts[key]}
                    for key in sorted(counts, key=lambda value: (value[0], value[1]))
                ]
                return {
                    "schema": "weekly_h2_clock_failure_diagnostic_v1",
                    "status": "FIRST_INVALID_CLOCK_LOCATED",
                    "inventory": {"path": str(inventory_path), "sha256": inventory_sha},
                    "pilot": {"path": str(pilot_path), "sha256": pilot_sha},
                    "sequence_index": sequence_index,
                    "coverage_role": role,
                    "ticker": cover["ticker"],
                    "trade_date": cover["entry_date"] if role == "entry" else cover["exit_date"],
                    "expiration": cover["expiration"],
                    "source": {"path": path_text, "sha256": before, "bytes": path.stat().st_size},
                    "clock_column": clock_column,
                    "first_error": first_error,
                    "invalid_unique_count": len(invalid),
                    "invalid_unique": invalid,
                    "unique_clock_count": len(counts),
                    "clock_frequencies": frequencies,
                    "quotes_or_greeks_read": False,
                }
    return {"schema": "weekly_h2_clock_failure_diagnostic_v1", "status": "NO_INVALID_CLOCK_FOUND", "quotes_or_greeks_read": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--pilot", required=True)
    parser.add_argument("--pilot-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(os.path.abspath(args.output_dir))
    if output.exists() and ((output / "diagnostic.json").exists() or (output / "manifest.json").exists()):
        raise FileExistsError(f"immutable diagnostic exists: {output}")
    output.mkdir(parents=True, exist_ok=True)
    result = diagnose(Path(args.inventory), args.inventory_sha256, Path(args.pilot), args.pilot_sha256)
    result_path = output / ".diagnostic.json.tmp"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"diagnostic.json": {"bytes": result_path.stat().st_size, "sha256": sha256_file(result_path)}, "code_sha256": sha256_file(Path(__file__).resolve())}
    manifest_path = output / ".manifest.json.tmp"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result_path.rename(output / "diagnostic.json")
    manifest_path.rename(output / "manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
