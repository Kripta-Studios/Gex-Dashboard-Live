"""Read existing census plus representative parquet footers; never read row values."""

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import re

import pyarrow.parquet as pq

INVENTORY = Path("D:/GexResearchArtifacts/restart_20261018/inventory")
RAW = Path("D:/ThetaData")
OUT = Path("D:/GexResearchArtifacts/level_oracle_20261018/volume_source_inventory_v1")
CORE = {"QQQ", "SPY", "SPXW"}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run():
    schemas = json.loads((INVENTORY / "schemas.json").read_text())
    categories = {}
    for schema in schemas:
        fields = {f[0] for f in schema["fields"]}
        category = (
            "option_bar_volume"
            if "volume" in fields
            else "option_trade_size"
            if {"size", "trade_timestamp"} <= fields
            else "observation_count_not_volume"
            if "tick_count" in fields
            else "quoted_size_not_volume"
            if {"bid_size", "ask_size"} <= fields
            else None
        )
        if category:
            categories[schema["schema_id"]] = category
    grouped = defaultdict(
        lambda: dict(files=0, rows=0, bytes=0, dates=set(), schemas=set())
    )
    core_ohlc = defaultdict(list)
    trade_examples = defaultdict(list)
    all_selected = 0
    with (INVENTORY / "files.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            category = categories.get(row["schema_id"])
            if category is None:
                continue
            all_selected += 1
            parts = Path(row["path"]).parts
            ticker = row["ticker"] or (
                parts[1] if len(parts) > 1 and parts[1] in CORE else ""
            )
            date = row["date"]
            if row["family"] != "data_options":
                exact = [part for part in parts if re.fullmatch(r"20\d{6}", part)]
                if exact:
                    date = exact[0]
                else:
                    found = re.search(r"(?:^|_)(20\d{6})(?:_|\.)", parts[-1])
                    if found:
                        date = found.group(1)
            year = date[:4] if date else ""
            key = (
                category,
                row["family"],
                ticker,
                year,
                row["zero_dte"]
                if row["family"] == "data_options"
                else "UNVERIFIED_BY_FILENAME",
            )
            item = grouped[key]
            item["files"] += 1
            item["rows"] += int(row["rows"] or 0)
            item["bytes"] += int(row["bytes"])
            if date:
                item["dates"].add(date)
            item["schemas"].add(row["schema_id"])
            if (
                category == "option_bar_volume"
                and row["family"] == "data_options"
                and ticker in CORE
                and row["zero_dte"] == "True"
                and "20230103" <= date <= "20260630"
            ):
                core_ohlc[(ticker, year)].append({**row, "date": date})
            if category == "option_trade_size":
                trade_examples[(row["family"], ticker, year)].append(
                    {**row, "date": date}
                )
    output_groups = []
    for key, value in sorted(grouped.items()):
        dates = sorted(value.pop("dates"))
        value["schemas"] = sorted(value["schemas"])
        output_groups.append(
            dict(zip(("category", "family", "ticker", "year", "zero_dte"), key))
            | value
            | dict(
                distinct_dates=len(dates),
                first_date=dates[0] if dates else None,
                last_date=dates[-1] if dates else None,
                dates=dates,
            )
        )
    representatives = []
    for groups in (core_ohlc, trade_examples):
        for key, rows in sorted(groups.items()):
            ordered = sorted(rows, key=lambda x: x["date"])
            for row in [ordered[0], ordered[-1]]:
                path = RAW / row["path"]
                footer = pq.ParquetFile(path)
                names = footer.schema_arrow.names
                stats = {}
                for name in (
                    "interval_used",
                    "timestamp",
                    "trade_timestamp",
                    "quote_timestamp",
                    "expiration",
                ):
                    if name not in names:
                        continue
                    index = names.index(name)
                    parts = []
                    for rg in range(footer.metadata.num_row_groups):
                        statistic = (
                            footer.metadata.row_group(rg).column(index).statistics
                        )
                        if statistic is not None:
                            parts.append(
                                dict(
                                    min=str(statistic.min),
                                    max=str(statistic.max),
                                    null_count=statistic.null_count,
                                )
                            )
                    stats[name] = parts
                representatives.append(
                    dict(
                        path=str(path),
                        rows=footer.metadata.num_rows,
                        schema_id=row["schema_id"],
                        footer_statistics=stats,
                    )
                )
    calendar = Path(
        "D:/GexResearchArtifacts/level_oracle_20261018/cache_v1/expected_calendar.csv"
    )
    with calendar.open(newline="", encoding="utf-8") as handle:
        expected = {row["date"] for row in csv.DictReader(handle)}
    coverage = []
    for ticker in sorted(CORE):
        available = {
            row["date"]
            for (tick, _), rows in core_ohlc.items()
            if tick == ticker
            for row in rows
        }
        coverage.append(
            dict(
                ticker=ticker,
                expected_days=len(expected),
                available_days=len(expected & available),
                missing_dates=sorted(expected - available),
                outside_calendar=sorted(available - expected),
            )
        )
    result = dict(
        scope="Existing complete census plus representative footers only; no row reads, API, features or fits",
        producer_sha256=sha(__file__),
        inputs={
            str(INVENTORY / n): sha(INVENTORY / n)
            for n in ("files.csv", "schemas.json")
        },
        selected_file_count=all_selected,
        groups=output_groups,
        candidate_schemas=[s for s in schemas if s["schema_id"] in categories],
        core_0dte_ohlc_2023_2026H1=coverage,
        representative_footers=representatives,
    )
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            dict(
                groups=len(output_groups),
                representative_footers=len(representatives),
                coverage=coverage,
                summary_sha256=sha(OUT / "summary.json"),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    run()
