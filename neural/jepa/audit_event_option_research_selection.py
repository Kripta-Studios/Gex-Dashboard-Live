from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from evaluate_xinput_level_filter import month_range


PRIOR_MONTH_COLUMNS = (
    "train_months",
    "val_months",
    "select_months",
    "profile_train_months",
    "profile_inner_val_months",
    "nested_select_months",
)

SELECTOR_COLUMNS = (
    "stream_selector_source",
    "selected_source",
    "selector_source",
    "nested_mode",
    "primary",
    "fallback",
    "nested_primary",
    "nested_fallback",
    "daily_router_source",
    "daily_source",
    "chosen_counts",
    "selected_meta_window_candidate",
    "meta_window_candidate",
)

WEAK_FOLD_MODES = {
    "NO_HISTORY",
    "INSUFFICIENT_ROWS",
    "INSUFFICIENT_META_ROWS",
    "SINGLE_CLASS_TRAIN",
    "EMPTY",
}

BACKFILL_CONFIG_REQUIRED_COLUMNS = {
    "primary_trades",
    "fallback_trades",
    "primary_name",
    "fallback_name",
    "ticker",
    "start_month",
    "end_month",
}


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


def load_sources(result_dir: Path) -> dict[str, Any]:
    metrics_path = result_dir / "metrics.json"
    if not metrics_path.exists():
        return {}
    try:
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"metrics_json_error": "invalid json"}
    sources = payload.get("sources")
    return sources if isinstance(sources, dict) else {}


def load_manifest(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"selection manifest missing: {path.name}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"selection manifest invalid json: {exc}"]
    if not isinstance(payload, dict):
        return None, ["selection manifest must be a json object"]
    return payload, []


def expand_backfill_config_rows(rows: pd.DataFrame, months: list[str]) -> pd.DataFrame:
    """Convert monthly_volume_backfill_config rows into auditable fold rows.

    Combined packages sometimes include the one-row backfill config as a fold
    file. Without expansion, the research-selection audit skips that ticker
    because the config has no test_month. The generated rows let the existing
    selected-source audit recurse into the primary/fallback stream folds.
    """
    if not BACKFILL_CONFIG_REQUIRED_COLUMNS.issubset(rows.columns):
        return rows
    expanded: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        if str(row.get("test_month", "")).strip():
            continue
        primary_path = str(row.get("primary_trades", "")).strip()
        fallback_path = str(row.get("fallback_trades", "")).strip()
        ticker = str(row.get("ticker", "")).strip().upper()
        if not primary_path or not fallback_path or not ticker:
            continue
        start_month = str(row.get("start_month", "")).strip()
        end_month = str(row.get("end_month", "")).strip()
        eval_months = [month for month in months if (not start_month or month >= start_month) and (not end_month or month <= end_month)]
        if not eval_months:
            continue
        source_stream = str(row.get("source_stream", row.get("output_dir", "monthly_volume_backfill"))).strip()
        source_file = str(row.get("source_file", row.get("output_dir", ""))).strip()
        for month in eval_months:
            for role, name_col, path in (
                ("PRIMARY", "primary_name", primary_path),
                ("FALLBACK", "fallback_name", fallback_path),
            ):
                item = {col: "" for col in rows.columns}
                for col in rows.columns:
                    if col in row.index:
                        item[col] = row.get(col, "")
                item.update(
                    {
                        "ticker": ticker,
                        "test_month": month,
                        "mode": f"MONTHLY_VOLUME_BACKFILL_{role}",
                        "selected_source": str(row.get(name_col, role.lower())).strip(),
                        "source_path": path,
                        "source_stream": source_stream,
                        "source_file": source_file,
                    }
                )
                expanded.append(item)
    if not expanded:
        return rows
    return pd.concat([rows, pd.DataFrame(expanded)], ignore_index=True, sort=False).fillna("")


def resolve_fold_file(source_path: str) -> Path | None:
    raw = str(source_path).strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_dir():
        candidates = [
            "stream_selector_folds.csv",
            "trade_union_topk_regressor_folds.csv",
            "nested_volume_backfill_folds.csv",
            "intraday_circuit_folds.csv",
            "daily_source_router_folds.csv",
            "static_union_folds.csv",
            "fold_configs.csv",
        ]
        for name in candidates:
            candidate = path / name
            if candidate.exists():
                return candidate
        return None
    name = path.name
    replacements = [
        ("combined_trades.csv", "combined_folds.csv"),
        ("stream_selector_trades.csv", "stream_selector_folds.csv"),
        ("trade_union_topk_regressor_trades.csv", "trade_union_topk_regressor_folds.csv"),
        ("nested_volume_backfill_trades.csv", "nested_volume_backfill_folds.csv"),
        ("monthly_volume_backfill_trades.csv", "monthly_volume_backfill_config.csv"),
        ("intraday_circuit_trades.csv", "intraday_circuit_folds.csv"),
        ("daily_source_router_trades.csv", "daily_source_router_folds.csv"),
        ("static_union_trades.csv", "static_union_folds.csv"),
        ("event_option_gate_trades.csv", "fold_configs.csv"),
    ]
    for trade_name, fold_name in replacements:
        if name == trade_name:
            candidate = path.with_name(fold_name)
            return candidate if candidate.exists() else None
    return None


def has_selector_evidence(rows: pd.DataFrame) -> bool:
    for col in SELECTOR_COLUMNS:
        if col in rows.columns and rows[col].astype(str).replace("nan", "").str.len().sum() > 0:
            return True
    return False


def has_causal_model_evidence(rows: pd.DataFrame) -> bool:
    if "mode" not in rows.columns:
        return False
    modes = set(rows["mode"].astype(str))
    if "DAILY_SOURCE_REG" in modes and "train_months" in rows.columns:
        return bool(rows["train_months"].astype(str).replace("nan", "").str.len().sum() > 0)
    if not ({"TOPK_REGRESSOR", "SELECTED"} & modes):
        return False
    if "select_months" not in rows.columns:
        return False
    return bool(rows["select_months"].astype(str).replace("nan", "").str.len().sum() > 0)


def audit_prior_months(rows: pd.DataFrame, months: list[str]) -> list[str]:
    issues: list[str] = []
    if "test_month" not in rows.columns:
        return ["combined_folds.csv missing test_month column"]
    for idx, row in rows.iterrows():
        test_month = str(row.get("test_month", ""))
        if test_month not in months:
            continue
        for col in PRIOR_MONTH_COLUMNS:
            if col not in rows.columns:
                continue
            non_prior = [month for month in parse_month_list(row.get(col)) if month >= test_month]
            if non_prior:
                source = str(row.get("source_stream", row.get("selected_source", "")))
                issues.append(f"row {idx} {source} {test_month}: {col} has non-prior months {non_prior}")
    return issues


def audit_selected_source_folds(rows: pd.DataFrame, months: list[str]) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    warnings: list[str] = []
    if "selected_source" not in rows.columns or "source_path" not in rows.columns:
        return issues, warnings
    cache: dict[str, pd.DataFrame | None] = {}

    def split_source_paths(path_text: str) -> list[str]:
        return [part.strip() for part in str(path_text).split("|") if part.strip()]

    def read_source_folds(path_text: str, row_idx: Any, test_month: str) -> pd.DataFrame | None:
        if path_text not in cache:
            fold_file = resolve_fold_file(path_text)
            if fold_file is None:
                cache[path_text] = None
                warnings.append(f"row {row_idx} {test_month}: no source fold file found for {path_text}")
            else:
                source_rows = pd.read_csv(fold_file, dtype=str).fillna("")
                source_rows = expand_backfill_config_rows(source_rows, months)
                if "mode" not in source_rows.columns and "deploy_config" in source_rows.columns:
                    source_rows["mode"] = "FOLD_CONFIG"
                cache[path_text] = source_rows
        return cache.get(path_text)

    def audit_matches(
        matches: pd.DataFrame,
        row_idx: Any,
        selected: str,
        test_month: str,
        source_path: str,
        depth: int = 0,
    ) -> None:
        weak = sorted(set(matches["mode"].astype(str)) & WEAK_FOLD_MODES)
        if weak:
            issues.append(f"row {row_idx} {selected} {test_month}: selected source has weak inner fold mode(s) {weak}")
        for match_idx, match in matches.iterrows():
            for col in PRIOR_MONTH_COLUMNS:
                if col not in matches.columns:
                    continue
                non_prior = [month for month in parse_month_list(match.get(col)) if month >= test_month]
                if non_prior:
                    issues.append(
                        f"row {row_idx} {selected} {test_month}: selected source fold row {match_idx} "
                        f"{col} has non-prior months {non_prior}"
                    )
            inner_path = str(match.get("source_path", "")).strip()
            if depth >= 1 or not inner_path or inner_path == source_path:
                continue
            inner_folds = read_source_folds(inner_path, row_idx, test_month)
            if inner_folds is None or inner_folds.empty:
                continue
            inner_month_col = (
                "test_month"
                if "test_month" in inner_folds.columns
                else "month"
                if "month" in inner_folds.columns
                else ""
            )
            if not inner_month_col or "mode" not in inner_folds.columns:
                warnings.append(f"row {row_idx} {test_month}: source fold file lacks month/mode columns for {inner_path}")
                continue
            inner_matches = inner_folds[inner_folds[inner_month_col].astype(str).eq(test_month)].copy()
            if inner_matches.empty:
                warnings.append(f"row {row_idx} {test_month}: source fold file has no fold for selected month in {inner_path}")
                continue
            audit_matches(
                inner_matches,
                row_idx,
                f"{selected}->{match.get('selected_source', '')}",
                test_month,
                inner_path,
                depth + 1,
            )

    for idx, row in rows.iterrows():
        test_month = str(row.get("test_month", ""))
        if test_month not in months:
            continue
        source_paths = split_source_paths(str(row.get("source_path", "")))
        if not source_paths:
            continue
        for source_path in source_paths:
            source_folds = read_source_folds(source_path, idx, test_month)
            if source_folds is None or source_folds.empty:
                continue
            month_col = "test_month" if "test_month" in source_folds.columns else "month" if "month" in source_folds.columns else ""
            if not month_col or "mode" not in source_folds.columns:
                warnings.append(f"row {idx} {test_month}: source fold file lacks month/mode columns for {source_path}")
                continue
            matches = source_folds[source_folds[month_col].astype(str).eq(test_month)].copy()
            if matches.empty:
                warnings.append(f"row {idx} {test_month}: source fold file has no fold for selected month in {source_path}")
                continue
            audit_matches(matches, idx, str(row.get("selected_source", "")), test_month, source_path)
    return issues, warnings


def summarize_ticker(ticker: str, rows: pd.DataFrame, months: list[str]) -> dict[str, Any]:
    eval_rows = rows[rows["test_month"].astype(str).isin(months)].copy()
    source_streams = sorted(set(eval_rows.get("source_stream", pd.Series(dtype=str)).dropna().astype(str)))
    source_files = sorted(set(eval_rows.get("source_file", pd.Series(dtype=str)).dropna().astype(str)))
    modes = sorted(set(eval_rows.get("mode", pd.Series(dtype=str)).dropna().astype(str)))
    selected_sources = sorted(
        set(eval_rows.get("selected_source", pd.Series(dtype=str)).dropna().astype(str).replace("nan", ""))
        - {""}
    )
    selector_evidence = has_selector_evidence(eval_rows)
    causal_model_evidence = has_causal_model_evidence(eval_rows)
    fold_months = sorted(set(eval_rows["test_month"].astype(str))) if "test_month" in eval_rows.columns else []
    if selector_evidence:
        selection_status = "causal_outer_or_inner_selector_present"
    elif causal_model_evidence:
        selection_status = "causal_model_training_or_topk_selection_present"
    elif len(source_streams) == 1:
        selection_status = "fixed_stream_requires_external_freeze_evidence"
    else:
        selection_status = "multiple_streams_without_selector_evidence"
    return {
        "ticker": ticker,
        "fold_months": fold_months,
        "source_streams": source_streams,
        "source_files": source_files,
        "selected_sources": selected_sources,
        "modes": modes,
        "selector_evidence": selector_evidence,
        "causal_model_evidence": causal_model_evidence,
        "selection_status": selection_status,
    }


def parse_name_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value if str(item).strip()}
    return set(parse_month_list(value))


def validate_manifest(manifest: dict[str, Any] | None, ticker_rows: dict[str, dict[str, Any]], start_month: str) -> list[str]:
    if manifest is None:
        return []
    issues: list[str] = []
    frozen_before = str(manifest.get("frozen_before_month", ""))
    if not frozen_before:
        issues.append("selection manifest missing frozen_before_month")
    elif frozen_before > start_month:
        issues.append(f"selection manifest frozen_before_month {frozen_before} is after evaluated start_month {start_month}")
    ticker_entries = manifest.get("tickers", {})
    if not isinstance(ticker_entries, dict):
        issues.append("selection manifest tickers must be an object")
        return issues
    for ticker, summary in ticker_rows.items():
        entry = ticker_entries.get(ticker)
        if not isinstance(entry, dict):
            issues.append(f"selection manifest missing ticker entry: {ticker}")
            continue
        method = str(entry.get("selection_method", ""))
        if not method:
            issues.append(f"{ticker}: selection manifest missing selection_method")
        evidence_months = parse_month_list(entry.get("selection_evidence_months"))
        future_evidence = [month for month in evidence_months if month >= start_month]
        if future_evidence:
            issues.append(f"{ticker}: selection_evidence_months include evaluated/future months {future_evidence}")
        expected_streams = parse_name_set(entry.get("expected_source_streams"))
        if expected_streams:
            actual_streams = set(summary.get("source_streams", []))
            if actual_streams != expected_streams:
                issues.append(
                    f"{ticker}: source_streams {sorted(actual_streams)} do not match manifest expected_source_streams {sorted(expected_streams)}"
                )
        allowed_streams = parse_name_set(entry.get("allowed_source_streams"))
        if allowed_streams:
            actual_streams = set(summary.get("source_streams", []))
            unexpected = sorted(actual_streams - allowed_streams)
            if unexpected:
                issues.append(f"{ticker}: source_streams include values outside manifest allowed_source_streams {unexpected}")
        allowed_selected = parse_name_set(entry.get("allowed_selected_sources"))
        if allowed_selected:
            actual_selected = set(summary.get("selected_sources", []))
            unexpected = sorted(actual_selected - allowed_selected)
            if unexpected:
                issues.append(f"{ticker}: selected_sources include values outside manifest allowed_selected_sources {unexpected}")
        allowed_modes = parse_name_set(entry.get("allowed_modes"))
        if allowed_modes:
            actual_modes = set(summary.get("modes", []))
            unexpected = sorted(actual_modes - allowed_modes)
            if unexpected:
                issues.append(f"{ticker}: modes include values outside manifest allowed_modes {unexpected}")
    return issues


def manifest_allows_static_multi_stream(
    manifest: dict[str, Any] | None,
    ticker: str,
    summary: dict[str, Any],
    start_month: str,
) -> bool:
    """Return true when a valid external freeze covers a fixed multi-stream family."""
    if manifest is None:
        return False
    frozen_before = str(manifest.get("frozen_before_month", ""))
    if not frozen_before or frozen_before > start_month:
        return False
    ticker_entries = manifest.get("tickers", {})
    if not isinstance(ticker_entries, dict):
        return False
    entry = ticker_entries.get(ticker)
    if not isinstance(entry, dict):
        return False
    if not str(entry.get("selection_method", "")).strip():
        return False
    evidence_months = parse_month_list(entry.get("selection_evidence_months"))
    if any(month >= start_month for month in evidence_months):
        return False
    actual_streams = set(summary.get("source_streams", []))
    expected_streams = parse_name_set(entry.get("expected_source_streams"))
    if expected_streams and actual_streams != expected_streams:
        return False
    allowed_streams = parse_name_set(entry.get("allowed_source_streams"))
    if not allowed_streams or not actual_streams.issubset(allowed_streams):
        return False
    actual_modes = set(summary.get("modes", [])) - {""}
    allowed_modes = parse_name_set(entry.get("allowed_modes"))
    if allowed_modes and not actual_modes.issubset(allowed_modes):
        return False
    return True


def write_report(report_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Event Option Research Selection Audit",
        "",
        "This report audits architecture/source selection evidence. It is separate from fold chronology and profitability gates.",
        "",
        f"- Passed: {payload['passed']}",
        f"- Strict: {payload['strict']}",
        f"- Result dir: `{payload['result_dir']}`",
        f"- Evaluated months: {', '.join(payload['months'])}",
        "",
        "## Interpretation",
        "",
    ]
    if payload["passed"] and not payload["warnings"]:
        lines.append("- Source/family selection evidence is sufficient under this audit.")
    elif payload["passed"]:
        lines.append("- No blocking issue in non-strict mode, but warnings mean source/family selection is not fully proven.")
    else:
        lines.append("- Fold-level causality can be clean while research-level stream selection remains unproven.")
    lines += ["", "## Tickers", ""]
    lines += [
        "| Ticker | Status | Selector Evidence | Source Streams | Selected Sources | Modes |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for ticker, row in payload["tickers"].items():
        lines.append(
            f"| {ticker} | {row['selection_status']} | {row['selector_evidence']} | "
            f"{', '.join(row['source_streams']) or 'n/a'} | "
            f"{', '.join(row['selected_sources']) or 'n/a'} | "
            f"{', '.join(row['modes']) or 'n/a'} |"
        )
    lines += ["", "## Issues", ""]
    if payload["issues"]:
        lines.extend(f"- {issue}" for issue in payload["issues"])
    else:
        lines.append("- none")
    lines += ["", "## Warnings", ""]
    if payload["warnings"]:
        lines.extend(f"- {warning}" for warning in payload["warnings"])
    else:
        lines.append("- none")
    lines += ["", "## Sources", "", "```json", json.dumps(payload["sources"], indent=2), "```"]
    (report_dir / "RESEARCH_SELECTION_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit event-option source/family selection evidence.")
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--manifest", default="research_selection_manifest.json")
    parser.add_argument("--report-dir", default="", help="Optional directory for audit outputs. Defaults to result-dir.")
    parser.add_argument("--strict", action="store_true", help="Treat missing freeze evidence as failure.")
    parser.add_argument(
        "--exit-zero-on-failed-audit",
        action="store_true",
        help="Write the failed strict audit payload but return 0 for status-report suites.",
    )
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    report_dir = Path(args.report_dir) if str(args.report_dir).strip() else result_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    folds_path = result_dir / "combined_folds.csv"
    if not folds_path.exists():
        for name in ("stream_selector_folds.csv", "trade_union_topk_regressor_folds.csv", "nested_volume_backfill_folds.csv"):
            candidate = result_dir / name
            if candidate.exists():
                folds_path = candidate
                break
        else:
            raise FileNotFoundError(folds_path)
    months = month_range(str(args.start_month), str(args.end_month))
    folds = pd.read_csv(folds_path, dtype=str).fillna("")
    if "ticker" not in folds.columns:
        raise ValueError("combined_folds.csv missing ticker column")
    if "test_month" not in folds.columns and "month" in folds.columns:
        folds["test_month"] = folds["month"].astype(str)
    if "test_month" not in folds.columns:
        folds["test_month"] = ""
    folds["ticker"] = folds["ticker"].astype(str).str.upper()
    folds["test_month"] = folds["test_month"].astype(str)
    folds = expand_backfill_config_rows(folds, months)
    folds["ticker"] = folds["ticker"].astype(str).str.upper()
    folds["test_month"] = folds["test_month"].astype(str)

    issues = audit_prior_months(folds, months)
    warnings: list[str] = []
    source_issues, source_warnings = audit_selected_source_folds(folds, months)
    issues.extend(source_issues)
    warnings.extend(source_warnings)
    manifest_arg = Path(str(args.manifest))
    if manifest_arg.is_absolute():
        manifest_path = manifest_arg
    elif manifest_arg.exists():
        manifest_path = manifest_arg
    else:
        manifest_path = result_dir / manifest_arg
    manifest, manifest_warnings = load_manifest(manifest_path)
    tickers = sorted(set(folds[folds["test_month"].isin(months)]["ticker"].astype(str)))
    warnings.extend(manifest_warnings)

    ticker_rows = {ticker: summarize_ticker(ticker, folds[folds["ticker"].eq(ticker)].copy(), months) for ticker in tickers}
    issues.extend(validate_manifest(manifest, ticker_rows, str(args.start_month)))
    for ticker, row in ticker_rows.items():
        if row["selection_status"] == "multiple_streams_without_selector_evidence":
            if manifest_allows_static_multi_stream(manifest, ticker, row, str(args.start_month)):
                row["selection_status"] = "fixed_multi_stream_external_freeze_manifest"
                row["selector_evidence"] = True
            else:
                issues.append(f"{ticker}: multiple source streams are present without selector evidence")
        elif row["selection_status"] == "fixed_stream_requires_external_freeze_evidence":
            warnings.append(f"{ticker}: fixed source stream needs external pre-evaluation freeze evidence")
        elif row["selection_status"] == "causal_model_training_or_topk_selection_present":
            warnings.append(f"{ticker}: causal model/top-K selection is present, but family/source-pool freeze evidence is still needed")
    if args.strict and manifest is None:
        issues.append("strict mode requires a valid research_selection_manifest.json")

    payload = {
        "passed": bool(not issues and (not args.strict or not warnings)),
        "strict": bool(args.strict),
        "result_dir": str(result_dir),
        "months": months,
        "manifest_path": str(manifest_path),
        "manifest_present": manifest is not None,
        "tickers": ticker_rows,
        "issues": issues,
        "warnings": warnings,
        "sources": load_sources(result_dir),
    }
    (report_dir / "research_selection_audit.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_report(report_dir, payload)
    print((report_dir / "RESEARCH_SELECTION_AUDIT.md").read_text(encoding="utf-8"))
    if bool(args.exit_zero_on_failed_audit):
        return 0
    return 0 if payload["passed"] or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())

