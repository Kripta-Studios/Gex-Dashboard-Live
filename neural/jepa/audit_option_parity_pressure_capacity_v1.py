"""Outcome-free listing-capacity audit for OPTION_PARITY_PRESSURE_V1."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TICKERS = ("QQQ", "SPXW", "SPY")
START_MONTH = "202301"
END_MONTH = "202512"
HALF_DAYS = frozenset(
    {
        "20230703",
        "20231124",
        "20240703",
        "20241129",
        "20241224",
        "20250703",
        "20251128",
        "20251224",
    }
)
PREDECLARATION = Path("research_papers/JEPA/OPTION_PARITY_PRESSURE_V1_PREDECLARATION.md")
SCOPE_AMENDMENT = Path("research_papers/JEPA/OPTION_PARITY_PRESSURE_V1_SCOPE_AMENDMENT.md")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def expected_months(start: str = START_MONTH, end: str = END_MONTH) -> list[str]:
    year, month = int(start[:4]), int(start[4:])
    end_year, end_month = int(end[:4]), int(end[4:])
    result: list[str] = []
    while (year, month) <= (end_year, end_month):
        result.append(f"{year:04d}{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return result


def discover_zero_dte_files(option_root: str | Path) -> list[dict[str, Any]]:
    root = Path(option_root)
    rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        pattern = re.compile(rf"^{ticker}_(\d{{8}})_(\d{{8}})_greeks\.parquet$")
        source_root = root / ticker / "greeks"
        if not source_root.is_dir():
            raise FileNotFoundError(f"missing Greeks source directory: {source_root}")
        seen: set[str] = set()
        for path in sorted(source_root.rglob("*.parquet")):
            match = pattern.fullmatch(path.name)
            if match is None:
                continue
            expiration, trade_date = match.groups()
            if not (START_MONTH <= trade_date[:6] <= END_MONTH):
                continue
            if expiration != trade_date:
                continue
            if trade_date in seen:
                raise AssertionError(f"duplicate exact-0DTE source for {ticker} {trade_date}")
            seen.add(trade_date)
            rows.append(
                {
                    "ticker": ticker,
                    "trade_date": trade_date,
                    "month": trade_date[:6],
                    "path": str(path),
                    "bytes": int(path.stat().st_size),
                    "calendar_half_day": trade_date in HALF_DAYS,
                    "eligible_fixed_180m_clock": trade_date not in HALF_DAYS,
                }
            )
    if not rows:
        raise AssertionError("no exact-0DTE sources found in the frozen scope")
    return sorted(rows, key=lambda row: (row["ticker"], row["trade_date"]))


def evaluate_capacity(
    rows: list[dict[str, Any]],
    months: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    month_axis = months or expected_months()
    counts = Counter(
        (str(row["ticker"]), str(row["month"]))
        for row in rows
        if bool(row["eligible_fixed_180m_clock"])
    )
    monthly: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for ticker in TICKERS:
        for month in month_axis:
            sessions = int(counts[(ticker, month)])
            passed = sessions > 12
            record = {
                "ticker": ticker,
                "month": month,
                "eligible_zero_dte_sessions": sessions,
                "required_strictly_greater_than": 12,
                "capacity_pass": passed,
            }
            monthly.append(record)
            if not passed:
                failures.append(record.copy())
    return monthly, failures


def csv_bytes(rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
    from io import StringIO

    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def atomic_publish(target: Path, files: dict[str, bytes]) -> None:
    if target.exists():
        raise FileExistsError(f"immutable output already exists: {target}")
    staging = target.with_name(f"{target.name}.staging-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        for name, payload in files.items():
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        staging.replace(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def run(option_root: Path, output_dir: Path) -> dict[str, Any]:
    rows = discover_zero_dte_files(option_root)
    monthly, failures = evaluate_capacity(rows)
    inventory_fields = [
        "ticker",
        "trade_date",
        "month",
        "path",
        "bytes",
        "calendar_half_day",
        "eligible_fixed_180m_clock",
    ]
    monthly_fields = [
        "ticker",
        "month",
        "eligible_zero_dte_sessions",
        "required_strictly_greater_than",
        "capacity_pass",
    ]
    inventory_payload = csv_bytes(rows, inventory_fields)
    monthly_payload = csv_bytes(monthly, monthly_fields)
    manifest = {
        "schema": "option_parity_pressure_v1_capacity_audit",
        "status": "PASS_FREQUENCY_CAPACITY" if not failures else "FAILED_FREQUENCY_OUTCOME_FREE",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "scope": {"start_month": START_MONTH, "end_month": END_MONTH},
        "tickers": list(TICKERS),
        "exact_zero_dte_source_files": len(rows),
        "source_files_by_ticker": dict(Counter(str(row["ticker"]) for row in rows)),
        "calendar_half_days_excluded": sorted(HALF_DAYS),
        "minimum_monthly_sessions_by_ticker": {
            ticker: min(
                int(row["eligible_zero_dte_sessions"])
                for row in monthly
                if row["ticker"] == ticker
            )
            for ticker in TICKERS
        },
        "failed_cells": failures,
        "frequency_gate": {"trades_per_month_strictly_greater_than": 12, "one_trade_per_session": True},
        "outcome_accessed": False,
        "quote_content_accessed": False,
        "holdout_2024_2025_opened": False,
        "holdout_2026_opened": False,
        "production_modified": False,
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "scope_amendment_sha256": sha256_file(SCOPE_AMENDMENT),
        "runner_sha256": sha256_file(__file__),
        "source_inventory_sha256": sha256_bytes(inventory_payload),
        "monthly_capacity_sha256": sha256_bytes(monthly_payload),
    }
    manifest_payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_publish(
        output_dir,
        {
            "source_inventory.csv": inventory_payload,
            "monthly_capacity.csv": monthly_payload,
            "manifest.json": manifest_payload,
        },
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--option-root", type=Path, default=Path("D:/ThetaData/data_options"))
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = run(args.option_root, args.output_dir)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
