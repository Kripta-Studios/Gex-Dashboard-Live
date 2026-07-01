from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


WEAK_FOLD_MODES = {
    "NO_HISTORY",
    "INSUFFICIENT_ROWS",
    "INSUFFICIENT_META_ROWS",
    "SINGLE_CLASS_TRAIN",
    "EMPTY",
}

EVIDENCE_MONTH_COLUMNS = (
    "train_months",
    "val_months",
    "select_months",
    "profile_train_months",
    "profile_inner_val_months",
    "nested_select_months",
)


def resolve_folds_file(result_dir: Path) -> Path:
    for name in (
        "combined_folds.csv",
        "stream_selector_folds.csv",
        "trade_union_topk_regressor_folds.csv",
        "nested_volume_backfill_folds.csv",
        "intraday_circuit_folds.csv",
        "fold_configs.csv",
    ):
        candidate = result_dir / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(result_dir / "combined_folds.csv")


def clean_values(frame: pd.DataFrame, column: str) -> list[str]:
    if column not in frame.columns:
        return []
    values = frame[column].dropna().astype(str).str.strip()
    values = values[(values != "") & (values.str.lower() != "nan")]
    return sorted(set(values.tolist()))


def parse_month_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    text = text.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
    return [item.strip() for item in text.split(",") if item.strip()]


def selection_evidence_months_for_rows(rows: pd.DataFrame) -> list[str]:
    months: set[str] = set()
    for column in EVIDENCE_MONTH_COLUMNS:
        if column not in rows.columns:
            continue
        for value in rows[column].tolist():
            months.update(parse_month_list(value))
    if months:
        return sorted(months)
    return clean_values(rows, "test_month")


def source_names_from_spec(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        return sorted(str(key).strip() for key in value.keys() if str(key).strip())
    if isinstance(value, list):
        names: list[str] = []
        for item in value:
            text = str(item).strip()
            if "=" in text:
                names.append(text.split("=", 1)[0].strip())
        return sorted(set(name for name in names if name))
    return []


def source_pool_from_result_file(path_text: str) -> list[str]:
    path = Path(str(path_text))
    directory = path.parent if path.suffix else path
    names: set[str] = set()
    for filename in ("selector_metadata.json", "metrics.json"):
        candidate = directory / filename
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        names.update(source_names_from_spec(payload.get("sources")))
        args = payload.get("args", {})
        if isinstance(args, dict):
            names.update(source_names_from_spec(args.get("sources")))
            names.update(source_names_from_spec(args.get("source")))
    return sorted(names)


def allowed_sources_for_rows(rows: pd.DataFrame) -> list[str]:
    names = set(clean_values(rows, "selected_source"))
    names.update(clean_values(rows, "primary"))
    names.update(clean_values(rows, "fallback"))
    for source_file in clean_values(rows, "source_file"):
        names.update(source_pool_from_result_file(source_file))
    return sorted(name for name in names if name)


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    result_dir = Path(args.result_dir)
    folds_path = resolve_folds_file(result_dir)
    folds = pd.read_csv(folds_path, dtype=str).fillna("")
    if "ticker" not in folds.columns:
        raise ValueError(f"{folds_path} missing ticker column")
    if "test_month" not in folds.columns and "month" in folds.columns:
        folds["test_month"] = folds["month"].astype(str)
    if "test_month" not in folds.columns:
        raise ValueError(f"{folds_path} missing test_month/month column")
    folds["ticker"] = folds["ticker"].astype(str).str.upper()
    folds["test_month"] = folds["test_month"].astype(str)

    evidence = folds[folds["test_month"].astype(str) < str(args.frozen_before_month)].copy()
    evidence_end_month = str(getattr(args, "evidence_end_month", "") or "").strip()
    if evidence_end_month:
        evidence = evidence[evidence["test_month"].astype(str) <= evidence_end_month].copy()
    if evidence.empty:
        raise ValueError("No fold rows are earlier than frozen_before_month")
    tickers: dict[str, Any] = {}
    for ticker, rows in evidence.groupby("ticker", sort=True):
        evidence_months = selection_evidence_months_for_rows(rows)
        source_streams = clean_values(rows, "source_stream")
        selected_sources = clean_values(rows, "selected_source")
        allowed_selected_sources = allowed_sources_for_rows(rows)
        modes = [mode for mode in clean_values(rows, "mode") if mode not in WEAK_FOLD_MODES]
        source_files = clean_values(rows, "source_file")
        source_paths = clean_values(rows, "source_path")
        tickers[str(ticker)] = {
            "selection_method": str(args.selection_method),
            "selection_evidence_months": evidence_months,
            "expected_source_streams": source_streams,
            "allowed_source_streams": source_streams,
            "observed_selected_sources": selected_sources,
            "allowed_selected_sources": allowed_selected_sources,
            "allowed_modes": modes,
            "source_files": source_files,
            "source_paths": source_paths,
            "notes": str(args.ticker_note),
        }

    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "frozen_before_month": str(args.frozen_before_month),
        "source_result_dir": str(result_dir),
        "source_folds_file": str(folds_path),
        "purpose": (
            "Forward-only event-option research architecture freeze. This manifest must not be used "
            "to certify months earlier than frozen_before_month."
        ),
        "research_caveat": str(args.research_caveat),
        "tickers": tickers,
    }


def write_summary(output_dir: Path, manifest_path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Event Option Research Freeze Manifest",
        "",
        "This folder freezes a research architecture/source pool for future walk-forward validation.",
        "",
        f"- Manifest: `{manifest_path.name}`",
        f"- Frozen before month: `{manifest['frozen_before_month']}`",
        f"- Source result dir: `{manifest['source_result_dir']}`",
        "",
        "## Tickers",
        "",
        "| Ticker | Evidence Months | Source Streams | Selected Sources | Modes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for ticker, entry in manifest["tickers"].items():
        lines.append(
            f"| {ticker} | {', '.join(entry['selection_evidence_months']) or 'n/a'} | "
            f"{', '.join(entry['expected_source_streams']) or 'n/a'} | "
            f"{', '.join(entry['allowed_selected_sources']) or 'n/a'} | "
            f"{', '.join(entry['allowed_modes']) or 'n/a'} |"
        )
    lines += [
        "",
        "## Caveat",
        "",
        manifest["research_caveat"],
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a forward-only research selection freeze manifest.")
    parser.add_argument("--result-dir", required=True, help="Existing causal result folder to freeze from.")
    parser.add_argument("--output-dir", required=True, help="Separate folder where the manifest will be written.")
    parser.add_argument("--frozen-before-month", required=True, help="First month this manifest may validate, e.g. 202607.")
    parser.add_argument(
        "--evidence-end-month",
        default="",
        help="Optional last month allowed as freeze evidence, useful to exclude partial months.",
    )
    parser.add_argument("--manifest-name", default="research_selection_manifest.json")
    parser.add_argument(
        "--selection-method",
        default="frozen_event_option_outer_stream_selector",
        help="Human-readable architecture/source-selection method name.",
    )
    parser.add_argument(
        "--research-caveat",
        default=(
            "The source pool was discovered during prior research. This manifest is valid only for "
            "future months after the freeze date, not as retroactive proof for the evidence months."
        ),
    )
    parser.add_argument("--ticker-note", default="")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(args)
    manifest_path = output_dir / str(args.manifest_name)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_summary(output_dir, manifest_path, manifest)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
