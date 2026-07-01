from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


MONTH_COLUMNS = (
    "train_months",
    "val_months",
    "select_months",
    "profile_train_months",
    "profile_inner_val_months",
    "inner_val_months",
    "core_months",
)


def parse_month_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []
    text = str(value).strip().replace("[", "").replace("]", "").replace("'", "").replace('"', "")
    if not text or text.lower() == "nan":
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def clean_values(frame: pd.DataFrame, column: str) -> list[str]:
    if column not in frame.columns:
        return []
    values = frame[column].dropna().astype(str).str.strip()
    values = values[(values != "") & (values.str.lower() != "nan")]
    return sorted(set(values.tolist()))


def evidence_months(rows: pd.DataFrame, frozen_before_month: str) -> list[str]:
    months: set[str] = set()
    for column in MONTH_COLUMNS:
        if column not in rows.columns:
            continue
        for value in rows[column].tolist():
            months.update(month for month in parse_month_list(value) if month < frozen_before_month)
    return sorted(months)


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    result_dir = Path(args.result_dir)
    folds_path = result_dir / str(args.folds_file)
    folds = pd.read_csv(folds_path, dtype=str).fillna("")
    if "ticker" not in folds.columns:
        raise ValueError(f"{folds_path} missing ticker")
    if "test_month" not in folds.columns and "month" in folds.columns:
        folds["test_month"] = folds["month"].astype(str)
    if "test_month" not in folds.columns:
        raise ValueError(f"{folds_path} missing test_month/month")
    folds["ticker"] = folds["ticker"].astype(str).str.upper()
    folds["test_month"] = folds["test_month"].astype(str)

    eval_rows = folds[folds["test_month"] >= str(args.frozen_before_month)].copy()
    if eval_rows.empty:
        raise ValueError("no rows at or after frozen_before_month")

    tickers: dict[str, Any] = {}
    for ticker, rows in eval_rows.groupby("ticker", sort=True):
        tickers[str(ticker)] = {
            "selection_method": str(args.selection_method),
            "selection_evidence_months": evidence_months(rows, str(args.frozen_before_month)),
            "expected_source_streams": clean_values(rows, "source_stream"),
            "allowed_source_streams": clean_values(rows, "source_stream"),
            "observed_selected_sources": clean_values(rows, "selected_source"),
            "allowed_selected_sources": clean_values(rows, "selected_source"),
            "allowed_modes": clean_values(rows, "mode"),
            "source_files": clean_values(rows, "source_file"),
            "source_paths": clean_values(rows, "source_path"),
            "notes": str(args.ticker_note),
        }

    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "frozen_before_month": str(args.frozen_before_month),
        "source_result_dir": str(result_dir),
        "source_folds_file": str(folds_path),
        "purpose": "Retrospective static multi-stream freeze for evaluating months at or after frozen_before_month.",
        "research_caveat": str(args.research_caveat),
        "tickers": tickers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze a deterministic static multi-stream result family.")
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--folds-file", default="combined_folds.csv")
    parser.add_argument("--output", default="")
    parser.add_argument("--frozen-before-month", required=True)
    parser.add_argument("--selection-method", default="static primary plus deterministic fallback frozen before holdout")
    parser.add_argument(
        "--research-caveat",
        default=(
            "This manifest freezes the deterministic source family for the specified holdout start. "
            "It proves the audited holdout does not use future months, but it is still retrospective research evidence."
        ),
    )
    parser.add_argument("--ticker-note", default="SPXW is the SPX weekly option proxy used for SPX execution.")
    args = parser.parse_args()

    output = Path(args.output) if str(args.output).strip() else Path(args.result_dir) / "research_selection_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(args)
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(output), "frozen_before_month": manifest["frozen_before_month"], "tickers": sorted(manifest["tickers"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())