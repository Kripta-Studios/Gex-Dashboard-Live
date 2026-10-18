"""Inventory 1..7 calendar DTE using the existing census; no raw parquet reads."""

import csv
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re


BASE = Path("D:/GexResearchArtifacts")
INVENTORY = BASE / "restart_20261018/inventory"
OUT = BASE / "level_oracle_20261018/near_expiration_inventory_v1"
PATTERN = re.compile(r"^(SPY|QQQ|SPXW)_(\d{8})_(\d{8})_(greeks|oi|iv|ohlc)\.parquet$")


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    schemas = {
        s["schema_id"]: s for s in json.loads((INVENTORY / "schemas.json").read_text())
    }
    calendar_path = BASE / "level_oracle_20261018/cache_v1/expected_calendar.csv"
    with calendar_path.open(newline="", encoding="utf-8") as file:
        calendar = {r["date"] for r in csv.DictReader(file)}
    groups = defaultdict(
        lambda: {
            "files": 0,
            "bytes": 0,
            "rows": 0,
            "days": set(),
            "pairs": set(),
            "native": 0,
            "proxy": 0,
            "no_clock": 0,
            "dte": Counter(),
            "schemas": set(),
        }
    )
    matches = []
    with (INVENTORY / "files.csv").open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            match = PATTERN.fullmatch(Path(row["path"]).name)
            if not match or row["family"] != "data_options":
                continue
            ticker, expiration, date, kind = match.groups()
            if not "20230103" <= date <= "20261231":
                continue
            dte = (
                datetime.strptime(expiration, "%Y%m%d")
                - datetime.strptime(date, "%Y%m%d")
            ).days
            if not 1 <= dte <= 7:
                continue
            schema = schemas[row["schema_id"]]
            fields = {f[0] for f in schema["fields"]}
            clock = (
                "native"
                if "timestamp" in fields
                else "proxy"
                if "underlying_timestamp" in fields
                else "no_clock"
            )
            scope = (
                "research_20230103_20260630"
                if date <= "20260630"
                else "later_2026_inventory_only"
            )
            key = (scope, ticker, date[:4], kind)
            group = groups[key]
            group["files"] += 1
            group["bytes"] += int(row["bytes"])
            group["rows"] += int(row["rows"])
            group["days"].add(date)
            group["pairs"].add((date, expiration))
            group[clock] += 1
            group["dte"][dte] += 1
            group["schemas"].add(row["schema_id"])
            matches.append(
                dict(
                    path=row["path"],
                    ticker=ticker,
                    date=date,
                    expiration=expiration,
                    dte=dte,
                    kind=kind,
                    scope=scope,
                    clock=clock,
                    schema_id=row["schema_id"],
                    bytes=int(row["bytes"]),
                    rows=int(row["rows"]),
                )
            )
    report = []
    for (scope, ticker, year, kind), g in sorted(groups.items()):
        days = sorted(g.pop("days"))
        pairs = sorted(g.pop("pairs"))
        report.append(
            dict(
                scope=scope,
                ticker=ticker,
                year=year,
                kind=kind,
                **g,
                day_count=len(days),
                pair_count=len(pairs),
                first_date=days[0],
                last_date=days[-1],
                missing_calendar_dates=sorted(
                    d for d in calendar if d.startswith(year) and d not in days
                )
                if scope.startswith("research")
                else [],
                days=days,
            )
        )
        report[-1]["schemas"] = sorted(report[-1]["schemas"])
    pair_sets = {
        kind: {
            (r["ticker"], r["date"], r["expiration"])
            for r in matches
            if r["kind"] == kind and r["scope"].startswith("research")
        }
        for kind in ("greeks", "oi", "iv", "ohlc")
    }
    paired = pair_sets["greeks"] & pair_sets["oi"]
    coverage = {}
    for ticker in ("SPY", "QQQ", "SPXW"):
        covered = {day for t, day, expiration in paired if t == ticker}
        coverage[ticker] = dict(
            paired_days=len(covered),
            paired_expiration_days=sum(t == ticker for t, _, _ in paired),
            missing_dates=sorted(calendar - covered),
        )
    summary = dict(
        status="METADATA_ONLY_INVENTORY_COMPLETE",
        raw_values_read=False,
        canonical_family="data_options",
        dte_definition="expiration date minus trade date, calendar days, 1..7 inclusive",
        source_files_sha256=sha(INVENTORY / "files.csv"),
        source_schemas_sha256=sha(INVENTORY / "schemas.json"),
        calendar_sha256=sha(calendar_path),
        producer_sha256=sha(Path(__file__)),
        calendar_days=len(calendar),
        groups=report,
        paired_greek_oi_coverage=coverage,
        files=len(matches),
        other_families="Not assigned DTE from normalized filenames lacking expiration; no row identities read",
    )
    with (OUT / "files.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(matches[0]))
        writer.writeheader()
        writer.writerows(matches)
    summary["output_files_sha256"] = sha(OUT / "files.csv")
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "files": len(matches),
                "paired_greek_oi_coverage": coverage,
                "summary_sha256": sha(OUT / "summary.json"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
