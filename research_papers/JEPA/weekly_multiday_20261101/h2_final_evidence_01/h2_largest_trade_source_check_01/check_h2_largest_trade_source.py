from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


NY = ZoneInfo("America/New_York")
PROJECTED = ("symbol", "expiration", "trade_date", "strike", "right", "timestamp", "underlying_timestamp", "bid", "ask", "underlying_price", "delta")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_jsonl(path: Path, predicate) -> list[dict[str, Any]]:
    found = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if predicate(row):
                found.append(row)
    return found


def clock_text(value: Any, trade_date: str) -> str | None:
    if isinstance(value, datetime):
        parsed = value
        fraction = bool(value.microsecond or getattr(value, "nanosecond", 0))
    elif isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        fraction_text = value.split(".", 1)[1] if "." in value else ""
        fraction_text = fraction_text.split("+", 1)[0].split("-", 1)[0].rstrip("Z")
        fraction = bool(fraction_text and any(char != "0" for char in fraction_text))
    else:
        raise RuntimeError(f"invalid clock type: {type(value).__name__}")
    local = parsed.replace(tzinfo=NY) if parsed.tzinfo is None else parsed.astimezone(NY)
    if local.strftime("%Y%m%d") != trade_date:
        raise RuntimeError("clock date mismatch")
    if local.second or fraction:
        return None
    return local.strftime("%H:%M")


def exact_rows(path: Path, source_sha: str, ticker: str, expiration: str, trade_date: str, strike: float, right: str, clocks: set[str]) -> tuple[dict[str, dict[str, Any]], str, str]:
    before = sha256_file(path)
    if before != source_sha:
        raise RuntimeError(f"source hash mismatch before read: {path}")
    parquet = pq.ParquetFile(path)
    names = set(parquet.schema_arrow.names)
    clock_column = "timestamp" if "timestamp" in names else "underlying_timestamp"
    basis = "NATIVE_STORED_TIMESTAMP" if clock_column == "timestamp" else "UNDERLYING_TIMESTAMP_PROXY"
    columns = [name for name in PROJECTED if name in names]
    required = {"symbol", "expiration", "trade_date", "strike", "right", clock_column, "bid", "ask", "underlying_price", "delta"}
    if not required.issubset(columns):
        raise RuntimeError(f"required projected column missing: {path}")
    selected: dict[str, dict[str, Any]] = {}
    for batch in parquet.iter_batches(columns=columns, use_threads=False, batch_size=65536):
        clock_array = batch.column(batch.schema.get_field_index(clock_column))
        keep_raw = []
        for raw in pc.unique(clock_array).to_pylist():
            if raw is None:
                raise RuntimeError("null clock")
            if clock_text(raw, trade_date) in clocks:
                keep_raw.append(raw)
        if not keep_raw:
            continue
        filtered = batch.filter(pc.is_in(clock_array, value_set=pa.array(keep_raw, type=clock_array.type)))
        for row in filtered.to_pylist():
            if str(row["symbol"]).strip().upper() != ticker or str(row["expiration"]).replace("-", "") != expiration or str(row["trade_date"]).replace("-", "") != trade_date:
                raise RuntimeError("row identity mismatch")
            if float(row["strike"]) != strike or str(row["right"]).strip().upper() not in ({"CALL", "C"} if right == "CALL" else {"PUT", "P"}):
                continue
            clock = clock_text(row[clock_column], trade_date)
            if clock in selected:
                raise RuntimeError(f"duplicate selected contract snapshot: {clock}")
            selected[clock] = {
                "clock": clock,
                "clock_raw": str(row[clock_column]),
                "ticker": ticker,
                "expiration": expiration,
                "trade_date": trade_date,
                "strike": float(row["strike"]),
                "right": right,
                "bid": float(row["bid"]),
                "ask": float(row["ask"]),
                "spot": float(row["underlying_price"]),
                "delta": float(row["delta"]),
            }
    after = sha256_file(path)
    if after != before:
        raise RuntimeError(f"source changed during read: {path}")
    if set(selected) != clocks:
        raise RuntimeError(f"missing exact clocks {clocks - set(selected)} in {path}")
    return selected, basis, after


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(os.path.abspath(args.output_dir))
    if output.exists() and (output / "result.json").exists():
        raise FileExistsError("immutable result exists")
    output.mkdir(parents=True, exist_ok=True)
    candidate_rows = find_jsonl(Path(args.candidates), lambda row: row.get("candidate_id") == args.candidate_id)
    ledger_rows = find_jsonl(Path(args.ledger), lambda row: row.get("candidate_id") == args.candidate_id)
    if len(candidate_rows) != 1:
        raise RuntimeError("candidate id is not unique")
    candidate = candidate_rows[0]
    entry_events = [row for row in ledger_rows if row.get("event") == "ENTRY"]
    exit_events = [row for row in ledger_rows if row.get("event") == "EXIT"]
    if len(entry_events) != 1 or len(exit_events) != 1:
        raise RuntimeError("ledger entry/exit is not unique")
    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    source_inventory = {item["path"]: item for item in inventory["sources"]}
    pins = candidate["source_pins"]
    for role in ("entry", "exit"):
        item = source_inventory[pins[f"{role}_path"]]
        if item["sha256"] != pins[f"{role}_sha256"]:
            raise RuntimeError(f"candidate/inventory {role} pin mismatch")
    entry_path, exit_path = Path(pins["entry_path"]), Path(pins["exit_path"])
    entry, entry_basis, entry_after = exact_rows(entry_path, pins["entry_sha256"], candidate["ticker"], candidate["expiration"], candidate["entry_date"], float(candidate["strike"]), candidate["right"], {"10:30", "10:35"})
    exit_rows, exit_basis, exit_after = exact_rows(exit_path, pins["exit_sha256"], candidate["ticker"], candidate["expiration"], candidate["exit_date"], float(candidate["strike"]), candidate["right"], {"10:35"})
    entry_ask, exit_bid = entry["10:35"]["ask"], exit_rows["10:35"]["bid"]
    net_adverse = (max(exit_bid - 0.02, 0.0) - entry_ask - 0.02) * 100.0 - 2.60
    checks = {
        "decision_matches_candidate": all(math.isclose(entry["10:30"][key], candidate["features"][candidate_key], abs_tol=1e-12) for key, candidate_key in (("bid", "bid"), ("ask", "ask"), ("spot", "spot"), ("delta", "delta"))),
        "entry_ask_matches_candidate": math.isclose(entry_ask, float(candidate["entry_ask"]), abs_tol=1e-12),
        "exit_bid_matches_candidate": math.isclose(exit_bid, float(candidate["exit_bid"]), abs_tol=1e-12),
        "candidate_net_adverse_matches_formula": math.isclose(net_adverse, float(candidate["net_adverse"]), abs_tol=1e-9),
        "ledger_net_adverse_matches_formula": math.isclose(net_adverse, float(exit_events[0]["net_usd"]), abs_tol=1e-9),
        "source_hashes_stable": entry_after == pins["entry_sha256"] and exit_after == pins["exit_sha256"],
    }
    result = {
        "schema": "weekly_h2_largest_trade_source_check_v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "candidate_id": args.candidate_id,
        "checks": checks,
        "candidate": candidate,
        "ledger": {"entry": entry_events[0], "exit": exit_events[0]},
        "source_snapshots": {"decision_10_30": entry["10:30"], "entry_10_35": entry["10:35"], "exit_10_35": exit_rows["10:35"]},
        "clock_basis": {"entry": entry_basis, "exit": exit_basis},
        "recomputed_net_adverse": net_adverse,
        "formula": "(max(exit_bid-0.02,0)-entry_ask-0.02)*100-2.60",
        "limitations": ["stored snapshot clocks do not prove observed live receipt", "one contract and multiplier 100 are contractual assumptions", "no independent tick-level audit beyond the stored exact-minute rows"],
    }
    temp = output / ".result.json.tmp"
    temp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"result.json": {"bytes": temp.stat().st_size, "sha256": sha256_file(temp)}, "code_sha256": sha256_file(Path(__file__).resolve())}
    manifest_temp = output / ".manifest.json.tmp"
    manifest_temp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.rename(output / "result.json")
    manifest_temp.rename(output / "manifest.json")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
