from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_RESULT = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1"
)
DEFAULT_OFFLINE_FILL = DEFAULT_RESULT / "offline_fill_simulation" / "offline_fill_simulation.json"
DEFAULT_PAPER_ORDER = DEFAULT_RESULT / "paper_order_validation" / "paper_order_validation.json"
DEFAULT_BROKER_ORDER = DEFAULT_RESULT / "broker_order_contract_validation" / "broker_order_contract_validation.json"
DEFAULT_OUTPUT_DIR = DEFAULT_RESULT / "trade_raw_coverage_validation"
DEFAULT_OPTIONS_ROOT = Path(r"D:\ThetaData\data_options")
DEFAULT_UNDERLYING_ROOT = Path(r"D:\ThetaData\data_underlying_derived")
OPTION_KINDS = ("greeks", "iv", "ohlc", "oi")
DATE_RE = re.compile(r"\D")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def norm_date(value: Any) -> str:
    return DATE_RE.sub("", str(value or ""))[:8]


def normalize_root(value: Any) -> str:
    root = str(value or "").upper().strip()
    return "SPXW" if root == "SPX" else root


def find_file(root: Path, ticker: str, name: str) -> str | None:
    ticker_dir = root / ticker
    if not ticker_dir.exists():
        return None
    direct = ticker_dir / name
    if direct.exists():
        return str(direct)
    matches = list(ticker_dir.rglob(name))
    return str(matches[0]) if matches else None


def option_part_paths(options_root: Path, root: str, expiration: str, date: str) -> dict[str, str | None]:
    return {
        kind: find_file(options_root, root, f"{root}_{expiration}_{date}_{kind}.parquet")
        for kind in OPTION_KINDS
    }


def underlying_path(underlying_root: Path, root: str, date: str) -> str | None:
    return find_file(underlying_root, root, f"{root}_{date}.parquet")


def add_record(records: list[dict[str, Any]], source: str, source_index: int, raw: dict[str, Any]) -> None:
    date = norm_date(raw.get("date") or raw.get("trade_date"))
    contract = raw.get("option_contract") if isinstance(raw.get("option_contract"), dict) else {}
    root = normalize_root(raw.get("symbol") or raw.get("option_root") or contract.get("root") or raw.get("ticker"))
    expiration = norm_date(raw.get("expiration") or contract.get("expiration"))
    right = str(raw.get("right") or contract.get("right") or "").upper()
    strike = raw.get("strike", contract.get("strike"))
    records.append(
        {
            "source": source,
            "source_index": int(source_index),
            "date": date,
            "root": root,
            "expiration": expiration,
            "right": right,
            "strike": strike,
            "offline_exit_available": raw.get("exit_available"),
            "offline_raw_premium_match": raw.get("raw_premium_match"),
            "offline_entry_limit_covers_ask": raw.get("entry_limit_covers_ask"),
        }
    )


def load_records(args: argparse.Namespace) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offline = read_json(Path(args.offline_fill)) if Path(args.offline_fill).exists() else {}
    for idx, order in enumerate(offline.get("orders", []) if isinstance(offline.get("orders"), list) else []):
        if isinstance(order, dict):
            add_record(records, "offline_fill_simulation", idx, order)

    paper = read_json(Path(args.paper_order)) if Path(args.paper_order).exists() else {}
    for idx, order in enumerate(paper.get("orders", []) if isinstance(paper.get("orders"), list) else []):
        if isinstance(order, dict):
            add_record(records, "paper_order_validation", idx, order)

    broker = read_json(Path(args.broker_order)) if Path(args.broker_order).exists() else {}
    for idx, order in enumerate(broker.get("orders", []) if isinstance(broker.get("orders"), list) else []):
        if not isinstance(order, dict):
            continue
        payload = order.get("broker_payload") if isinstance(order.get("broker_payload"), dict) else {}
        raw = {
            "trade_date": order.get("trade_date"),
            "option_contract": payload.get("option_contract"),
            "ticker": order.get("ticker"),
        }
        add_record(records, "broker_order_contract_validation", idx, raw)
    return records


def validate_record(record: dict[str, Any], options_root: Path, underlying_root: Path) -> dict[str, Any]:
    issues: list[str] = []
    date = str(record.get("date") or "")
    root = str(record.get("root") or "")
    expiration = str(record.get("expiration") or "")
    if len(date) != 8:
        issues.append(f"invalid date {date!r}")
    if len(expiration) != 8:
        issues.append(f"invalid expiration {expiration!r}")
    if expiration != date:
        issues.append(f"not 0DTE: expiration {expiration!r} != date {date!r}")
    if not root:
        issues.append("missing option root")
    option_paths = option_part_paths(options_root, root, expiration, date) if root and expiration and date else {}
    missing_option_parts = [kind for kind, path in option_paths.items() if not path]
    if missing_option_parts:
        issues.append(f"missing option raw parts {missing_option_parts}")
    u_path = underlying_path(underlying_root, root, date) if root and date else None
    if not u_path:
        issues.append("missing underlying raw file")
    if record.get("source") == "offline_fill_simulation":
        if record.get("offline_exit_available") is not True:
            issues.append("offline fill exit path unavailable")
        if record.get("offline_raw_premium_match") is not True:
            issues.append("offline raw premium did not match")
        if record.get("offline_entry_limit_covers_ask") is not True:
            issues.append("offline entry limit did not cover ask")
    out = dict(record)
    out.update(
        {
            "option_paths": option_paths,
            "underlying_path": u_path,
            "missing_option_parts": missing_option_parts,
            "passed": not issues,
            "issues": issues,
        }
    )
    return out


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dense Candidate Trade Raw Coverage Validation",
        "",
        f"- Passed: `{payload['passed']}`",
        f"- Records checked: `{payload['records_checked']}`",
        f"- Passed records: `{payload['records_passed']}`",
        f"- Unique ticker/date pairs: `{len(payload['unique_root_dates'])}`",
        "- Scope: trade/order-level raw file and offline-fill coverage only; this does not certify partial months as official completed months.",
        "",
        "## Source Counts",
        "",
        "| Source | Records | Passed |",
        "| --- | ---: | ---: |",
    ]
    for source, row in payload["by_source"].items():
        lines.append(f"| {source} | {row['records']} | {row['passed']} |")
    lines.extend(["", "## Root-Date Coverage", "", "| Root | Date | Records |", "| --- | ---: | ---: |"])
    for item in payload["unique_root_dates"]:
        lines.append(f"| {item['root']} | {item['date']} | {item['records']} |")
    if payload["issues"]:
        lines.extend(["", "## Issues", ""])
        for issue in payload["issues"]:
            lines.append(f"- {issue}")
    output_dir.joinpath("TRADE_RAW_COVERAGE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate raw 0DTE file coverage for selected dense-candidate trades/orders.")
    parser.add_argument("--offline-fill", default=str(DEFAULT_OFFLINE_FILL))
    parser.add_argument("--paper-order", default=str(DEFAULT_PAPER_ORDER))
    parser.add_argument("--broker-order", default=str(DEFAULT_BROKER_ORDER))
    parser.add_argument("--options-root", default=str(DEFAULT_OPTIONS_ROOT))
    parser.add_argument("--underlying-root", default=str(DEFAULT_UNDERLYING_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = load_records(args)
    checked = [validate_record(r, Path(args.options_root), Path(args.underlying_root)) for r in records]
    issues = [f"{r['source']}[{r['source_index']}]: " + "; ".join(r["issues"]) for r in checked if r.get("issues")]
    source_counts: dict[str, Counter[str]] = defaultdict(Counter)
    root_date_counts: Counter[tuple[str, str]] = Counter()
    for row in checked:
        source_counts[str(row["source"])] ["records"] += 1
        if row.get("passed"):
            source_counts[str(row["source"])] ["passed"] += 1
        root_date_counts[(str(row.get("root")), str(row.get("date")))] += 1
    payload = {
        "schema_version": 1,
        "validation": "dense_candidate_trade_raw_coverage",
        "passed": not issues and bool(checked),
        "records_checked": len(checked),
        "records_passed": sum(1 for row in checked if row.get("passed")),
        "by_source": {source: dict(counter) for source, counter in sorted(source_counts.items())},
        "unique_root_dates": [
            {"root": root, "date": date, "records": count}
            for (root, date), count in sorted(root_date_counts.items())
        ],
        "scope": "trade/order-level raw 0DTE file coverage; not official partial-month completion evidence",
        "not_covered": [
            "full-month completion for partial months",
            "broker API order acceptance",
            "paper/live broker submission",
            "exchange queue position or partial fills",
            "future completed-month performance",
        ],
        "records": checked,
        "issues": issues,
    }
    output_dir.joinpath("trade_raw_coverage_validation.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
