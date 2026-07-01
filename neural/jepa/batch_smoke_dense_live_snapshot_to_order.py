from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.smoke_dense_live_snapshot_to_order import run_smoke


def _safe_name(date: str, cutoff: str) -> str:
    return f"{date}_{cutoff.replace(':', '')}"


def _run_case(spec: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(spec["output_root"]) / _safe_name(str(spec["date"]), str(spec["cutoff"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    args = SimpleNamespace(
        date=str(spec["date"]),
        cutoff=str(spec["cutoff"]),
        tickers=list(spec["tickers"]),
        registry=str(spec["registry"]),
        output_dir=str(output_dir),
        strict_features=bool(spec["strict_features"]),
    )
    try:
        payload = run_smoke(args)
        (output_dir / "snapshot_to_order_smoke.json").write_text(
            json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8"
        )
        return {
            "date": str(spec["date"]),
            "cutoff": str(spec["cutoff"]),
            "passed": bool(payload.get("passed")),
            "output_dir": str(output_dir),
            "snapshot_rows": int((payload.get("snapshot_summary") or {}).get("rows", 0)),
            "candidate_rows": int(payload.get("candidate_rows", 0)),
            "issues": payload.get("candidate_issues", []),
            "selections": payload.get("selections", []),
        }
    except Exception as exc:
        return {
            "date": str(spec["date"]),
            "cutoff": str(spec["cutoff"]),
            "passed": False,
            "output_dir": str(output_dir),
            "snapshot_rows": 0,
            "candidate_rows": 0,
            "issues": [f"{type(exc).__name__}: {exc}"],
            "traceback": traceback.format_exc(),
            "selections": [],
        }


def _selection_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in rows:
        for selection in row.get("selections", []):
            ticker = str(selection.get("ticker", ""))
            if not ticker:
                continue
            item = out.setdefault(ticker, {"cases": 0, "selected": 0})
            item["cases"] += 1
            if selection.get("selected"):
                item["selected"] += 1
    return out


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dense Snapshot-To-Order Batch Smoke",
        "",
        f"- Passed: {payload['passed']}",
        f"- Cases: {payload['passed_cases']}/{payload['total_cases']}",
        f"- Strict features: {payload['strict_features']}",
        f"- Registry: `{payload['registry']}`",
        "",
        "## Cases",
        "",
        "| Date | Cutoff | Passed | Snapshot Rows | Candidate Rows | Selected | Issues |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["cases"]:
        selected = sum(1 for item in row.get("selections", []) if item.get("selected"))
        issues = "; ".join(str(item) for item in row.get("issues", [])[:3])
        lines.append(
            f"| {row['date']} | {row['cutoff']} | {row['passed']} | {row['snapshot_rows']} | "
            f"{row['candidate_rows']} | {selected} | {issues} |"
        )
    lines += [
        "",
        "## Selection Counts",
        "",
        "```json",
        json.dumps(payload["selection_counts"], indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch smoke-test dense live snapshot-to-order runtime compatibility.")
    parser.add_argument("--dates", nargs="+", required=True)
    parser.add_argument("--cutoffs", nargs="+", default=["10:00", "12:00", "14:30"])
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument(
        "--registry",
        default="neural/models/jepa/jepa_production_event_options_dense15_strict_uniform_candidate/component_registry.json",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--strict-features", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = [
        {
            "date": str(date),
            "cutoff": str(cutoff),
            "tickers": [str(t).upper() for t in args.tickers],
            "registry": str(args.registry),
            "output_root": str(output_dir / "cases"),
            "strict_features": bool(args.strict_features),
        }
        for date in args.dates
        for cutoff in args.cutoffs
    ]
    workers = max(1, min(int(args.workers), len(specs)))
    if workers == 1:
        rows = [_run_case(spec) for spec in specs]
    else:
        with futures.ProcessPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(_run_case, specs))
    rows = sorted(rows, key=lambda item: (str(item["date"]), str(item["cutoff"])))
    payload = {
        "schema_version": 1,
        "smoke": "dense_live_snapshot_to_order_batch",
        "passed": bool(all(row["passed"] for row in rows)),
        "total_cases": int(len(rows)),
        "passed_cases": int(sum(1 for row in rows if row["passed"])),
        "dates": [str(item) for item in args.dates],
        "cutoffs": [str(item) for item in args.cutoffs],
        "tickers": [str(item).upper() for item in args.tickers],
        "registry": str(args.registry),
        "strict_features": bool(args.strict_features),
        "cases": rows,
        "selection_counts": _selection_counts(rows),
        "scope": "Batch ThetaData historical files -> live day_dir schema -> event snapshot builder -> candidate registry scorer -> bot delta contract selection.",
        "not_covered": [
            "statistical trading quality",
            "future deploy-month forward evidence",
            "broker/order execution fills",
        ],
    }
    (output_dir / "snapshot_to_order_batch_smoke.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8"
    )
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
