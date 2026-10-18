"""Read-only tree census and Parquet footer census; never reads data pages.

Output is an inventory, not a raw-content seal or causal admission. Filenames,
filesystem stat, schema, row counts and pandas index metadata only are read.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq


def describe_file(item):
    root, path, size, mtime = item
    relative = path.relative_to(root)
    parts = relative.parts
    family = parts[0] if len(parts) > 1 else "__root__"
    ticker = next((p for p in parts[1:] if p in TICKERS), "")
    match = re.match(r"([A-Z]+)_(\d{8})_(\d{8})_(\w+)\.parquet$", path.name)
    dates = [part for part in parts[:-1] if re.fullmatch(r"20\d{6}", part)]
    if not dates:
        dates = re.findall(r"(?<![A-Za-z0-9])(20\d{6})(?![A-Za-z0-9])", path.name)
    kind, expiration, day = "", "", dates[-1] if dates else ""
    if match:
        ticker, expiration, day, kind = match.groups()
    elif family == "data_training_input":
        ticker = path.stem.split("_")[1]
    if not kind:
        kind = parts[2] if family == "data_options" and len(parts) > 2 else path.stem if path.stem.isalpha() else "other"
    record = dict(path=relative.as_posix(), family=family, ticker=ticker, kind=kind,
                  date=day, year=day[:4], expiration=expiration,
                  zero_dte=bool(day and expiration == day), bytes=size,
                  mtime_ns=mtime, suffix=path.suffix.lower(), schema_id="", rows="", row_groups="", error="")
    schema_record = None
    if path.suffix.lower() == ".parquet":
        try:
            parquet = pq.ParquetFile(path)
            schema = parquet.schema_arrow
            fields = [(f.name, str(f.type), f.nullable) for f in schema]
            metadata = schema.metadata or {}
            pandas = json.loads(metadata.get(b"pandas", b"{}"))
            descriptor = dict(fields=fields, pandas_index_columns=pandas.get("index_columns", []),
                              metadata_keys=sorted(k.decode("utf-8", errors="replace") for k in metadata))
            schema_id = hashlib.sha256(json.dumps(descriptor, sort_keys=True).encode()).hexdigest()
            schema_record = dict(schema_id=schema_id, **descriptor,
                                 temporal_fields=[f.name for f in schema if any(x in f.name.lower() for x in ("timestamp", "time", "date"))],
                                 physical_timestamp_fields=[f.name for f in schema if "timestamp" in str(f.type)],
                                 example=relative.as_posix())
            record.update(schema_id=schema_id, rows=parquet.metadata.num_rows, row_groups=parquet.metadata.num_row_groups)
            parquet.close()
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
    return record, schema_record


TICKERS = {"SPX", "SPXW", "SPY", "QQQ", "NDX", "NDXP", "AAPL", "AMZN", "GLD", "GOOGL", "HOOD", "IWM", "META", "MSFT", "NFLX", "NVDA", "PLTR", "SLV", "TLT", "TSLA", "UNH", "VIX", "VIXW"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("D:/ThetaData"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    files, traversal_errors = [], []
    def onerror(error):
        traversal_errors.append(str(error))
    for folder, dirs, names in os.walk(args.root, onerror=onerror, followlinks=False):
        dirs.sort()
        for name in sorted(names):
            path = Path(folder, name)
            try:
                stat = path.stat()
                files.append((args.root, path, stat.st_size, stat.st_mtime_ns))
            except OSError as exc:
                traversal_errors.append(f"{path}: {exc}")
    print(json.dumps({"discovered_files": len(files), "bytes": sum(item[2] for item in files)}), flush=True)
    schemas, groups, family_totals, errors = {}, {}, {}, []
    coverage = defaultdict(lambda: defaultdict(set))
    with (args.output / "files.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = None
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for index, (record, schema) in enumerate(pool.map(describe_file, files, buffersize=args.workers * 4), 1):
                if writer is None:
                    writer = csv.DictWriter(handle, fieldnames=list(record))
                    writer.writeheader()
                writer.writerow(record)
                if schema:
                    schemas.setdefault(schema["schema_id"], schema)
                if record["error"]:
                    errors.append({"path": record["path"], "error": record["error"]})
                key = tuple(record[k] for k in ("family", "ticker", "kind", "year", "zero_dte", "suffix", "schema_id"))
                if key not in groups:
                    groups[key] = dict(zip(("family", "ticker", "kind", "year", "zero_dte", "suffix", "schema_id"), key), files=0, bytes=0, rows=0, dates=set(), first_date="", last_date="")
                group = groups[key]
                group["files"] += 1
                group["bytes"] += record["bytes"]
                group["rows"] += int(record["rows"] or 0)
                if record["date"]:
                    group["dates"].add(record["date"])
                total = family_totals.setdefault(record["family"], dict(files=0, bytes=0, parquets=0, rows=0))
                total["files"] += 1
                total["bytes"] += record["bytes"]
                total["parquets"] += record["suffix"] == ".parquet"
                total["rows"] += int(record["rows"] or 0)
                if record["family"] == "data_options" and record["zero_dte"]:
                    coverage[record["ticker"]][record["kind"]].add(record["date"])
                if index % 25000 == 0:
                    print(json.dumps({"processed": index, "seconds": round(time.monotonic() - started, 1), "errors": len(errors)}), flush=True)
    aggregates = []
    for group in groups.values():
        days = sorted(group.pop("dates"))
        group.update(distinct_dates=len(days), first_date=days[0] if days else "", last_date=days[-1] if days else "")
        aggregates.append(group)
    coverage_json = {ticker: {kind: sorted(days) for kind, days in kinds.items()} for ticker, kinds in coverage.items()}
    summary = dict(root=str(args.root.resolve()), completed_utc=datetime.now(timezone.utc).isoformat(),
                   elapsed_seconds=time.monotonic()-started, files=len(files), bytes=sum(i[2] for i in files),
                   families=family_totals, unique_schemas=len(schemas), footer_errors=errors,
                   traversal_errors=traversal_errors, values_read=False, raw_content_hashed=False,
                   script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    for name, data in (("summary.json", summary), ("groups.json", aggregates), ("schemas.json", list(schemas.values())), ("zero_dte_dates.json", coverage_json)):
        (args.output / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    artifact_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.output.iterdir()) if p.is_file()}
    (args.output / "artifact_hashes.json").write_text(json.dumps(artifact_hashes, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"complete": True, "files": len(files), "seconds": round(summary["elapsed_seconds"], 1), "schemas": len(schemas), "footer_errors": len(errors), "traversal_errors": len(traversal_errors)}), flush=True)


if __name__ == "__main__":
    main()
