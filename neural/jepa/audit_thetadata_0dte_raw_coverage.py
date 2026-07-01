from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_OPTIONS_ROOT = Path(r"D:\ThetaData\data_options")
DEFAULT_UNDERLYING_ROOT = Path(r"D:\ThetaData\data_underlying_derived")
DEFAULT_OUTPUT_DIR = Path(
    "research_papers/JEPA/results/_diagnostics/thetadata_0dte_raw_coverage_spxw_spy_qqq"
)
OPTION_RE = re.compile(r"^(?P<ticker>[A-Z0-9]+)_(?P<expiration>\d{8})_(?P<date>\d{8})_(?P<kind>[^.]+)\.parquet$")
UNDERLYING_RE = re.compile(r"^(?P<ticker>[A-Z0-9]+)_(?P<date>\d{8})\.parquet$")
OPTION_KINDS = ["greeks", "iv", "ohlc", "oi"]


def last_business_date_for_month(month: str) -> str:
    start = pd.Timestamp(year=int(month[:4]), month=int(month[4:6]), day=1)
    return pd.bdate_range(start, start + pd.offsets.MonthEnd(0))[-1].strftime("%Y%m%d")


def month_completed(month: str, latest_date: str | None) -> bool:
    if not latest_date:
        return False
    return str(latest_date) >= last_business_date_for_month(str(month))


def summarize_dates(dates: list[str] | set[str]) -> dict[str, Any]:
    values = list(dates)
    unique = set(values)
    if not unique:
        return {"files": 0, "unique_dates": 0, "min_date": None, "max_date": None, "months": {}}
    months: dict[str, dict[str, Any]] = {}
    for date in sorted(unique):
        month = date[:6]
        row = months.setdefault(month, {"dates": []})
        row["dates"].append(date)
    month_payload: dict[str, Any] = {}
    for month, row in months.items():
        month_dates = row["dates"]
        latest = max(month_dates)
        month_payload[month] = {
            "unique_dates": len(set(month_dates)),
            "first_date": min(month_dates),
            "latest_date": latest,
            "last_business_date": last_business_date_for_month(month),
            "completed": month_completed(month, latest),
        }
    return {
        "files": len(values),
        "unique_dates": len(unique),
        "min_date": min(unique),
        "max_date": max(unique),
        "months": month_payload,
    }


def collect_option_dates(root: Path, tickers: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ticker in tickers:
        by_kind: dict[str, list[str]] = {kind: [] for kind in OPTION_KINDS}
        all_expirations: set[str] = set()
        zero_dte_expirations: set[str] = set()
        scanned_option_files = 0
        zero_dte_option_files = 0
        non_zero_dte_option_files = 0
        ticker_dir = root / ticker
        if ticker_dir.exists():
            for path in ticker_dir.rglob("*.parquet"):
                match = OPTION_RE.match(path.name)
                if not match:
                    continue
                scanned_option_files += 1
                kind = match.group("kind")
                date = match.group("date")
                expiration = match.group("expiration")
                all_expirations.add(expiration)
                if expiration != date:
                    non_zero_dte_option_files += 1
                    continue
                zero_dte_option_files += 1
                zero_dte_expirations.add(expiration)
                if kind not in by_kind:
                    by_kind[kind] = []
                by_kind[kind].append(date)
        out[ticker] = {
            "path": str(ticker_dir),
            "exists": ticker_dir.exists(),
            "scanned_option_files": scanned_option_files,
            "zero_dte_option_files": zero_dte_option_files,
            "non_zero_dte_option_files": non_zero_dte_option_files,
            "kinds": {kind: summarize_dates(dates) for kind, dates in sorted(by_kind.items())},
            "min_expiration": min(zero_dte_expirations) if zero_dte_expirations else None,
            "max_expiration": max(zero_dte_expirations) if zero_dte_expirations else None,
            "min_expiration_all_options": min(all_expirations) if all_expirations else None,
            "max_expiration_all_options": max(all_expirations) if all_expirations else None,
        }
    return out

def collect_underlying_dates(root: Path, tickers: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ticker in tickers:
        dates: list[str] = []
        ticker_dir = root / ticker
        if ticker_dir.exists():
            for path in ticker_dir.rglob("*.parquet"):
                match = UNDERLYING_RE.match(path.name)
                if match:
                    dates.append(match.group("date"))
        out[ticker] = {
            "path": str(ticker_dir),
            "exists": ticker_dir.exists(),
            **summarize_dates(dates),
        }
    return out



def per_ticker_status(options: dict[str, Any], underlying: dict[str, Any], tickers: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ticker in tickers:
        latest_values: list[str] = []
        month_maps: list[dict[str, Any]] = []
        missing_parts: list[str] = []
        for kind in OPTION_KINDS:
            row = options.get(ticker, {}).get("kinds", {}).get(kind, {})
            if row.get("max_date"):
                latest_values.append(str(row["max_date"]))
            else:
                missing_parts.append(f"options.{kind}")
            month_maps.append(row.get("months", {}))
        u = underlying.get(ticker, {})
        if u.get("max_date"):
            latest_values.append(str(u["max_date"]))
        else:
            missing_parts.append("underlying")
        month_maps.append(u.get("months", {}))
        common_months = sorted(set.intersection(*(set(m.keys()) for m in month_maps if m)) if month_maps else set())
        month_status: dict[str, Any] = {}
        for month in common_months:
            latest = min(str(m[month].get("latest_date")) for m in month_maps if month in m)
            month_status[month] = {
                "latest_common_date": latest,
                "last_business_date": last_business_date_for_month(month),
                "completed": month_completed(month, latest),
            }
        out[ticker] = {
            "missing_parts": missing_parts,
            "min_latest_available_date_across_parts": min(latest_values) if latest_values else None,
            "max_latest_available_date_across_parts": max(latest_values) if latest_values else None,
            "months": month_status,
        }
    return out


def combined_status(per_ticker: dict[str, Any]) -> dict[str, Any]:
    month_sets = [set(row.get("months", {}).keys()) for row in per_ticker.values()]
    common_months = sorted(set.intersection(*month_sets) if month_sets else set())
    months: dict[str, Any] = {}
    for month in common_months:
        latest = min(str(row["months"][month]["latest_common_date"]) for row in per_ticker.values())
        completed = all(bool(row["months"][month]["completed"]) for row in per_ticker.values())
        months[month] = {
            "latest_common_date": latest,
            "last_business_date": last_business_date_for_month(month),
            "completed": completed,
        }
    latest_values = [row.get("min_latest_available_date_across_parts") for row in per_ticker.values() if row.get("min_latest_available_date_across_parts")]
    completed_months = [month for month, row in months.items() if row["completed"]]
    partial_months = [month for month, row in months.items() if not row["completed"]]
    return {
        "latest_common_date_all_tickers": min(latest_values) if latest_values else None,
        "months": months,
        "completed_months": completed_months,
        "partial_months": partial_months,
    }


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# ThetaData 0DTE Raw Coverage Audit",
        "",
        f"- Latest common date all tickers: `{payload['combined']['latest_common_date_all_tickers']}`",
        f"- Completed months: `{', '.join(payload['combined']['completed_months']) or '(none)'}`",
        f"- Partial months: `{', '.join(payload['combined']['partial_months']) or '(none)'}`",
        "",
        "## Tickers",
        "",
        "| Ticker | 0DTE Option Files | Non-0DTE Option Files Ignored | Min Latest Across Parts | Max Latest Across Parts | Missing Parts |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for ticker, row in payload["per_ticker"].items():
        opt = payload.get("options", {}).get(ticker, {})
        lines.append(
            f"| {ticker} | {opt.get('zero_dte_option_files')} | "
            f"{opt.get('non_zero_dte_option_files')} | "
            f"{row.get('min_latest_available_date_across_parts')} | "
            f"{row.get('max_latest_available_date_across_parts')} | "
            f"{', '.join(row.get('missing_parts', [])) or '-'} |"
        )
    lines.extend([
        "",
        "This audit reports raw local 0DTE file availability only. Option files count only when expiration date equals quote date. It does not make a trading performance claim and does not make a partial month official forward evidence.",
        "",
    ])
    (output_dir / "RAW_COVERAGE.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit raw local ThetaData coverage for SPXW/SPY/QQQ 0DTE inputs.")
    parser.add_argument("--options-root", default=str(DEFAULT_OPTIONS_ROOT))
    parser.add_argument("--underlying-root", default=str(DEFAULT_UNDERLYING_ROOT))
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    tickers = [str(t).upper() for t in args.tickers]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    options = collect_option_dates(Path(args.options_root), tickers)
    underlying = collect_underlying_dates(Path(args.underlying_root), tickers)
    per_ticker = per_ticker_status(options, underlying, tickers)
    payload = {
        "schema_version": 2,
        "audit": "thetadata_0dte_raw_coverage",
        "options_root": str(args.options_root),
        "underlying_root": str(args.underlying_root),
        "tickers": tickers,
        "options": options,
        "underlying": underlying,
        "per_ticker": per_ticker,
        "combined": combined_status(per_ticker),
        "official_forward_evidence": False,
        "note": "Raw local 0DTE file availability only; option files count only when expiration date equals quote date. Partial months are not official forward evidence.",
    }
    (output_dir / "raw_coverage.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
