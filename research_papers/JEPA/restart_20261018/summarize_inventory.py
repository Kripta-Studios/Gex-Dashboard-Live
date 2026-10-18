"""Summarize existing census only; no source traversal or market-value reads."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    root = args.inventory
    schemas = {item["schema_id"]: item for item in json.loads((root / "schemas.json").read_text(encoding="utf-8"))}
    main_counts = defaultdict(lambda: dict(files=0, rows=0, bytes=0, dates=set()))
    clocks = defaultdict(lambda: dict(files=0, rows=0))
    sidecars = defaultdict(lambda: dict(files=0, rows=0, bytes=0, dates=set(), schemas=set()))
    suffixes = Counter()
    corrected = 0
    date_corrected = 0
    core = {"SPY", "QQQ", "SPXW"}
    with (root / "files.csv").open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            suffixes[record["suffix"]] += 1
            if record["suffix"] != ".parquet":
                continue
            family, ticker = record["family"], record["ticker"]
            if family != "data_options":
                path = Path(record["path"])
                dates = [part for part in path.parts[:-1] if re.fullmatch(r"20\d{6}", part)]
                if not dates:
                    dates = re.findall(r"(?<![A-Za-z0-9])(20\d{6})(?![A-Za-z0-9])", path.name)
                actual_date = dates[-1] if dates else ""
                date_corrected += actual_date != record["date"]
                record["date"], record["year"] = actual_date, actual_date[:4]
            if family == "data_underlying_derived":
                actual = Path(record["path"]).parts[1]
                corrected += actual != ticker
                ticker = actual
            schema = schemas.get(record["schema_id"], {})
            columns = {field[0] for field in schema.get("fields", [])}
            key = (family, ticker, record["kind"], record["year"], record["zero_dte"])
            group = main_counts[key]
            group["files"] += 1
            group["rows"] += int(record["rows"] or 0)
            group["bytes"] += int(record["bytes"])
            if record["date"]:
                group["dates"].add(record["date"])
            if family == "data_options" and ticker in core and record["zero_dte"] == "True":
                clock_key = (ticker, record["kind"], record["year"], "timestamp" in columns,
                             "underlying_timestamp" in columns, {"bid", "ask"} <= columns,
                             "gamma" in columns)
                clocks[clock_key]["files"] += 1
                clocks[clock_key]["rows"] += int(record["rows"] or 0)
            if family not in {"data_options", "data_underlying_derived", "data_training_input"}:
                side = sidecars[(family, ticker)]
                side["files"] += 1
                side["rows"] += int(record["rows"] or 0)
                side["bytes"] += int(record["bytes"])
                if record["date"]:
                    side["dates"].add(record["date"])
                side["schemas"].add(record["schema_id"])
    def serialize_counts(mapping, fields):
        result = []
        for key, value in sorted(mapping.items()):
            value = dict(value)
            if "dates" in value:
                days = sorted(value.pop("dates"))
                value.update(distinct_dates=len(days), first_date=days[0] if days else "", last_date=days[-1] if days else "")
            if "schemas" in value:
                value["schemas"] = sorted(value["schemas"])
            result.append(dict(zip(fields, key), **value))
        return result
    data = dict(
        derivation="Existing files.csv and schemas.json only; derived ticker from second path segment; non-option date from exact date directory or isolated filename token, never event hash fragments.",
        derived_ticker_labels_corrected=corrected,
        parquet_date_labels_corrected=date_corrected,
        suffixes=dict(suffixes),
        all_parquet_counts=serialize_counts(main_counts, ("family", "ticker", "kind", "year", "zero_dte")),
        core_zero_dte_clocks=serialize_counts(clocks, ("ticker", "kind", "year", "timestamp", "underlying_timestamp", "bid_ask", "gamma")),
        sidecar_counts=serialize_counts(sidecars, ("family", "ticker")),
        input_sha256={name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ("files.csv", "schemas.json")},
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    output = root / "review_summary.json"
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "derived_ticker_labels_corrected": corrected, "parquet_files": suffixes[".parquet"]}))


if __name__ == "__main__":
    main()
