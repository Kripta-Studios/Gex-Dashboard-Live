from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from audit_event_option_research_selection import summarize_ticker
from evaluate_xinput_level_filter import month_range


DEFAULT_SCAN_SUMMARY = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "scan_existing_results_pre2026_select_2025_eval_202601_202604/summary.json"
)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def list_from(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    text = text.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
    return [item.strip() for item in text.split(",") if item.strip()]


def audit_row_for_dir(scan: dict[str, Any], result_dir: Path) -> dict[str, Any]:
    target = str(result_dir).replace("/", "\\")
    rows = []
    top = scan.get("top_lineage_clean_holdout")
    if isinstance(top, dict):
        rows.append(top)
    rows.extend(row for row in scan.get("top_rows", []) if isinstance(row, dict))
    matches = [row for row in rows if str(row.get("dir", "")).replace("/", "\\") == target]
    if matches:
        return matches[0]
    raise ValueError(f"{result_dir} is not present in scan summary top rows")


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    scan_path = Path(args.scan_summary)
    scan = read_json(scan_path)
    result_dir = Path(args.result_dir)
    folds_path = result_dir / "combined_folds.csv"
    if not folds_path.exists():
        raise FileNotFoundError(folds_path)

    row = audit_row_for_dir(scan, result_dir)
    if row.get("eligible_pre2026_selection") is not True:
        raise ValueError(f"{result_dir} is not eligible by pre-2026 selection scan")
    if row.get("test_pass_with_lineage") is not True:
        raise ValueError(f"{result_dir} does not pass holdout lineage in pre-2026 selection scan")
    if scan.get("rank_fields_are_pre2026_only") is not True:
        raise ValueError("scan rank fields are not pre-2026 only")

    months = month_range(str(args.start_month), str(args.end_month))
    folds = pd.read_csv(folds_path, dtype=str).fillna("")
    if "test_month" not in folds.columns and "month" in folds.columns:
        folds["test_month"] = folds["month"].astype(str)
    if "test_month" not in folds.columns:
        raise ValueError(f"{folds_path} missing test_month/month")
    if "ticker" not in folds.columns:
        raise ValueError(f"{folds_path} missing ticker")
    folds["test_month"] = folds["test_month"].astype(str)
    folds["ticker"] = folds["ticker"].astype(str).str.upper()

    tickers: dict[str, Any] = {}
    for ticker in sorted(set(folds[folds["test_month"].isin(months)]["ticker"].astype(str))):
        ticker_rows = folds[folds["ticker"].eq(ticker)].copy()
        summary = summarize_ticker(ticker, ticker_rows, months)
        tickers[ticker] = {
            "selection_method": "pre2026_existing_result_scan_rank_then_static_union_lineage",
            "selection_evidence_months": list_from(scan.get("selection_months")),
            "expected_source_streams": summary.get("source_streams", []),
            "allowed_source_streams": summary.get("source_streams", []),
            "observed_selected_sources": summary.get("selected_sources", []),
            "allowed_selected_sources": summary.get("selected_sources", []),
            "allowed_modes": summary.get("modes", []),
            "source_files": summary.get("source_files", []),
            "source_paths": sorted(
                set(
                    str(item).strip()
                    for item in ticker_rows.get("source_path", pd.Series(dtype=str)).dropna().astype(str)
                    if str(item).strip()
                )
            ),
            "notes": (
                "Outer branch selected by pre-2026 scan metrics only; inner static-union source rows "
                "use prior select_months encoded in combined_folds.csv."
            ),
        }

    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "frozen_before_month": str(args.start_month),
        "source_result_dir": str(result_dir),
        "source_folds_file": str(folds_path),
        "selection_scan_summary": str(scan_path),
        "selection_scan_rank_fields": scan.get("rank_fields", []),
        "selection_scan_rank_fields_are_pre2026_only": bool(scan.get("rank_fields_are_pre2026_only")),
        "selection_scan_counts": {
            "evaluated_dirs": scan.get("evaluated_dirs"),
            "eligible_pre2026_selection": scan.get("eligible_pre2026_selection"),
            "eligible_and_test_pass": scan.get("eligible_and_test_pass"),
        },
        "source_universe_caveat": (
            "This manifest proves the chosen branch is reproducible from the current existing-results scan "
            "using pre-2026 rank fields, and that its evaluated folds use prior evidence. It does not prove "
            "the result-directory universe itself was timestamp-frozen before 2026."
        ),
        "purpose": (
            "Retrospective pre-2026 selection reconstruction for the raw-complete 2026 holdout. "
            "Use together with the scan summary and strict research-selection audit."
        ),
        "tickers": tickers,
    }
    return manifest


def write_summary(output_dir: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Pre-2026 Scan Selection Manifest",
        "",
        f"- Frozen before month: `{manifest['frozen_before_month']}`",
        f"- Source result dir: `{manifest['source_result_dir']}`",
        f"- Selection scan: `{manifest['selection_scan_summary']}`",
        f"- Rank fields are pre-2026 only: `{manifest['selection_scan_rank_fields_are_pre2026_only']}`",
        "",
        "## Tickers",
        "",
        "| Ticker | Selection Evidence Months | Source Streams | Selected Sources | Modes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for ticker, entry in manifest["tickers"].items():
        lines.append(
            f"| {ticker} | {', '.join(entry['selection_evidence_months'])} | "
            f"{', '.join(entry['expected_source_streams']) or 'n/a'} | "
            f"{', '.join(entry['allowed_selected_sources']) or 'n/a'} | "
            f"{', '.join(entry['allowed_modes']) or 'n/a'} |"
        )
    lines += [
        "",
        "## Caveat",
        "",
        manifest["source_universe_caveat"],
    ]
    (output_dir / "PRE2026_SELECTION_MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a research-selection manifest from the pre-2026 scan output.")
    parser.add_argument(
        "--result-dir",
        default=(
            "research_papers/JEPA/results/"
            "event_static_union_longsrc_2024h2select_objpass_simpler_spy_daily_guard_l5p2_risk5000_v1"
        ),
    )
    parser.add_argument("--scan-summary", default=str(DEFAULT_SCAN_SUMMARY))
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202604")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--manifest-name", default="research_selection_manifest.json")
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else result_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(args)
    manifest_path = output_dir / str(args.manifest_name)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_summary(output_dir, manifest)
    print((output_dir / "PRE2026_SELECTION_MANIFEST.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
