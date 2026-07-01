from __future__ import annotations

import argparse
import csv
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from verify_event_option_result import load_trades, parse_month_list
from walkforward_event_option_gate import metrics


DEFAULT_RESULT_ROOT = Path("research_papers/JEPA/results")
DEFAULT_OUTPUT_DIR = (
    DEFAULT_RESULT_ROOT / "_diagnostics" / "scan_existing_results_pre2026_select_2025_eval_202601_202604"
)

TRADE_FILE_NAMES = (
    "combined_trades.csv",
    "monthly_volume_backfill_trades.csv",
    "nested_volume_backfill_trades.csv",
    "stream_selector_trades.csv",
    "intraday_circuit_trades.csv",
    "daily_source_router_trades.csv",
    "relative_momentum_trades.csv",
    "market_state_expert_trades.csv",
    "selected_variant_trades.csv",
    "event_option_profile_trades.csv",
    "trade_union_meta_trades.csv",
    "trade_union_topk_regressor_trades.csv",
    "trade_union_backfill_selector_trades.csv",
    "trade_union_config_selector_trades.csv",
    "delta_selector_trades.csv",
    "static_union_trades.csv",
    "static_union_mtd_rescue_trades.csv",
    "event_option_gate_trades.csv",
)

FOLD_FILE_NAMES = (
    "combined_folds.csv",
    "intraday_circuit_folds.csv",
    "daily_source_router_folds.csv",
    "relative_momentum_folds.csv",
    "selected_folds.csv",
    "fold_configs.csv",
    "trade_union_meta_folds.csv",
    "trade_union_topk_regressor_folds.csv",
    "trade_union_backfill_selector_folds.csv",
    "trade_union_config_selector_folds.csv",
    "delta_selector_folds.csv",
    "static_union_folds.csv",
    "static_union_mtd_rescue_folds.csv",
)

MONTH_COLUMNS = (
    "train_months",
    "val_months",
    "select_months",
    "profile_train_months",
    "profile_inner_val_months",
    "inner_val_months",
    "core_months",
)

RANK_FIELDS = (
    "select_pass",
    "select_pf_min",
    "select_wr_min",
    "select_min_month_min",
    "select_pnl_sum",
    "select_overall_profit_factor",
    "select_overall_win_rate",
    "select_overall_trades",
    "fold_2025_ok",
)


def finite_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def locate_first(root: Path, names: tuple[str, ...]) -> Path | None:
    return next((root / name for name in names if (root / name).exists()), None)


def candidate_result_dirs(result_root: Path, include_diagnostics: bool) -> list[Path]:
    roots: list[Path] = []
    for path in sorted(result_root.iterdir()):
        if not path.is_dir():
            continue
        if path.name == "_diagnostics":
            if include_diagnostics:
                roots.extend(sorted(child for child in path.iterdir() if child.is_dir()))
            continue
        roots.append(path)
    out = [path for path in roots if locate_first(path, TRADE_FILE_NAMES) is not None]
    return sorted(out, key=lambda p: str(p).lower())


def safe_metrics(frame: pd.DataFrame, months: list[str]) -> dict[str, Any]:
    if frame.empty:
        return metrics(frame, months)
    return metrics(frame.copy(), months)


def ticker_metrics(
    trades: pd.DataFrame,
    months: list[str],
    ticker: str,
    min_win_rate: float,
    min_profit_factor: float,
    min_month_trades: int,
    min_call_rate: float,
    max_call_rate: float,
) -> dict[str, Any]:
    part = trades[trades["ticker"].astype(str).str.upper().eq(ticker)].copy()
    row = safe_metrics(part, months)
    wr = finite_float(row.get("win_rate"), -1.0)
    pf = finite_float(row.get("profit_factor"), -1.0)
    pnl = finite_float(row.get("pnl_return"), 0.0)
    call_rate = finite_float(row.get("call_rate"), -1.0)
    min_month = int(finite_float(row.get("min_month_trades"), 0.0))
    row["pass"] = bool(
        wr >= min_win_rate
        and pf >= min_profit_factor
        and min_month >= min_month_trades
        and pnl > 0.0
        and call_rate >= min_call_rate
        and call_rate <= max_call_rate
    )
    return row


def summarize_window(
    trades: pd.DataFrame,
    months: list[str],
    tickers: list[str],
    prefix: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    out: dict[str, Any] = {}
    for ticker in tickers:
        row = ticker_metrics(
            trades[trades["month"].astype(str).isin(months)].copy(),
            months,
            ticker,
            float(args.min_win_rate),
            float(args.min_profit_factor),
            int(args.min_month_trades),
            float(args.min_call_rate),
            float(args.max_call_rate),
        )
        rows[ticker] = row
        low = ticker.lower()
        for key in (
            "trades",
            "win_rate",
            "profit_factor",
            "pnl_return",
            "min_month_trades",
            "call_rate",
            "positive_month_rate",
            "pass",
        ):
            out[f"{prefix}_{low}_{key}"] = row.get(key)

    overall = safe_metrics(trades[trades["month"].astype(str).isin(months)].copy(), months)
    for key in (
        "trades",
        "win_rate",
        "profit_factor",
        "pnl_return",
        "min_month_trades",
        "call_rate",
        "positive_month_rate",
    ):
        out[f"{prefix}_overall_{key}"] = overall.get(key)

    out[f"{prefix}_pass"] = bool(all(bool(rows[ticker].get("pass")) for ticker in tickers))
    out[f"{prefix}_pf_min"] = min(finite_float(rows[ticker].get("profit_factor"), -1.0) for ticker in tickers)
    out[f"{prefix}_wr_min"] = min(finite_float(rows[ticker].get("win_rate"), -1.0) for ticker in tickers)
    out[f"{prefix}_min_month_min"] = min(int(finite_float(rows[ticker].get("min_month_trades"), 0.0)) for ticker in tickers)
    out[f"{prefix}_pnl_sum"] = sum(finite_float(rows[ticker].get("pnl_return"), 0.0) for ticker in tickers)
    return out


def audit_fold_file(
    result_dir: Path,
    months: list[str],
    max_evidence_month: str | None = None,
) -> dict[str, Any]:
    fold_path = locate_first(result_dir, FOLD_FILE_NAMES)
    if fold_path is None:
        return {"path": "", "ok": False, "checked": 0, "issues": "fold file missing"}

    folds = pd.read_csv(fold_path, dtype=str)
    issues: list[str] = []
    checked = 0
    months_set = set(months)
    for idx, row in folds.iterrows():
        test_month = str(row.get("test_month", row.get("month", row.get("eval_month", "")))).strip()[:6]
        if test_month not in months_set:
            continue
        checked += 1
        for col in MONTH_COLUMNS:
            if col not in folds.columns:
                continue
            evidence_months = parse_month_list(row.get(col))
            non_prior = [month for month in evidence_months if month >= test_month]
            if non_prior:
                issues.append(f"row{idx}:{col}:non_prior={','.join(non_prior[:6])}")
            if max_evidence_month is not None:
                after_cutoff = [month for month in evidence_months if month > max_evidence_month]
                if after_cutoff:
                    issues.append(f"row{idx}:{col}:after_{max_evidence_month}")
        if len(issues) >= 50:
            break
    if checked <= 0:
        issues.append("no matching folds")
    return {
        "path": fold_path.name,
        "ok": bool(checked > 0 and not issues),
        "checked": int(checked),
        "issues": "|".join(issues[:50]),
    }


def score_row(row: dict[str, Any]) -> float:
    if not bool(row.get("select_pass")):
        return -1.0e9
    pf_min = finite_float(row.get("select_pf_min"))
    wr_min = finite_float(row.get("select_wr_min"))
    min_month = finite_float(row.get("select_min_month_min"))
    pnl_sum = finite_float(row.get("select_pnl_sum"))
    overall_pf = finite_float(row.get("select_overall_profit_factor"))
    overall_wr = finite_float(row.get("select_overall_win_rate"))
    trades = finite_float(row.get("select_overall_trades"))
    return (
        8.0 * max(0.0, pf_min - 1.0)
        + 20.0 * max(0.0, wr_min - 0.45)
        + 0.25 * max(0.0, min_month - 18.0)
        + 0.05 * pnl_sum
        + 2.0 * max(0.0, overall_pf - 1.0)
        + 10.0 * max(0.0, overall_wr - 0.45)
        + 0.001 * trades
    )


def scan_one(result_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    row: dict[str, Any] = {
        "dir": str(result_dir),
        "name": result_dir.name,
        "trade_file": "",
        "status": "ok",
    }
    trade_path = locate_first(result_dir, TRADE_FILE_NAMES)
    if trade_path is None:
        row["status"] = "missing_trade_file"
        return row
    row["trade_file"] = trade_path.name
    try:
        trades = load_trades(result_dir)
        if "ticker" not in trades.columns or "month" not in trades.columns:
            raise ValueError("trade file missing ticker/month")
        tickers = [str(item).upper() for item in args.tickers]
        select_months = month_range(str(args.select_start_month), str(args.select_end_month))
        test_months = month_range(str(args.test_start_month), str(args.test_end_month))
        row.update(summarize_window(trades, select_months, tickers, "select", args))
        row.update(summarize_window(trades, test_months, tickers, "test", args))

        fold_2025 = audit_fold_file(result_dir, select_months)
        fold_2026 = audit_fold_file(result_dir, test_months, max_evidence_month=str(args.max_test_evidence_month))
        row.update(
            {
                "fold_file": fold_2026["path"] or fold_2025["path"],
                "fold_2025_ok": bool(fold_2025["ok"]),
                "fold_2025_checked": int(fold_2025["checked"]),
                "fold_2025_issues": fold_2025["issues"],
                "fold_2026_ok": bool(fold_2026["ok"]),
                "fold_2026_checked": int(fold_2026["checked"]),
                "fold_2026_issues": fold_2026["issues"],
            }
        )
        row["select_score"] = score_row(row)
        row["eligible_pre2026_selection"] = bool(row["select_pass"] and row["fold_2025_ok"])
        row["test_pass_with_lineage"] = bool(row["test_pass"] and row["fold_2026_ok"])
    except Exception as exc:  # noqa: BLE001 - this is a diagnostic scanner.
        row["status"] = f"error:{type(exc).__name__}:{exc}"
    return row


def rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        not bool(row.get("eligible_pre2026_selection")),
        -finite_float(row.get("select_score"), -1.0e9),
        -finite_float(row.get("select_pf_min")),
        -finite_float(row.get("select_wr_min")),
        -finite_float(row.get("select_pnl_sum")),
        str(row.get("name", "")),
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    top = payload.get("top_lineage_clean_holdout") or {}
    lines = [
        "# Existing Event-Option Pre-2026 Selection Scan",
        "",
        "This diagnostic scans existing result directories with a mechanical rule:",
        f"select/rank using `{payload['selection_months'][0]}..{payload['selection_months'][-1]}` only,",
        f"then report holdout `{payload['test_months'][0]}..{payload['test_months'][-1]}`.",
        "",
        "It is not strict production proof if the available directory universe was created after seeing 2026.",
        "",
        "## Result",
        "",
        f"- Evaluated result dirs: `{payload['evaluated_dirs']}`",
        f"- Eligible by pre-2026 selection gates and fold chronology: `{payload['eligible_pre2026_selection']}`",
        f"- Eligible and holdout pass with lineage: `{payload['eligible_and_test_pass']}`",
        f"- Rank fields are pre-2026 only: `{payload['rank_fields_are_pre2026_only']}`",
        "",
    ]
    if top:
        lines += [
            "## Top Lineage-Clean Holdout Candidate",
            "",
            f"`{top['dir']}`",
            "",
            "| Ticker | Trades | WR | PF | Min Trades/Month | PnL Return |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for ticker in payload["tickers"]:
            low = ticker.lower()
            lines.append(
                f"| {ticker} | {int(finite_float(top.get(f'test_{low}_trades')))} | "
                f"{finite_float(top.get(f'test_{low}_win_rate')):.2%} | "
                f"{finite_float(top.get(f'test_{low}_profit_factor')):.3f} | "
                f"{int(finite_float(top.get(f'test_{low}_min_month_trades')))} | "
                f"{finite_float(top.get(f'test_{low}_pnl_return')):.3f} |"
            )
        lines += [
            "",
            f"Fold lineage: `{top.get('fold_2026_checked')}` folds checked, issues `{top.get('fold_2026_issues') or 'none'}`.",
            "",
        ]
    lines += [
        "## Top Ranked Rows",
        "",
        "| Rank | Eligible | Holdout+Lineage | Dir | Select PF Min | Select WR Min | Holdout PF Min | Holdout WR Min |",
        "| ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for idx, row in enumerate(payload.get("top_rows", []), start=1):
        lines.append(
            f"| {idx} | {row.get('eligible_pre2026_selection')} | {row.get('test_pass_with_lineage')} | "
            f"`{row.get('dir')}` | {finite_float(row.get('select_pf_min')):.3f} | "
            f"{finite_float(row.get('select_wr_min')):.2%} | {finite_float(row.get('test_pf_min')):.3f} | "
            f"{finite_float(row.get('test_wr_min')):.2%} |"
        )
    lines += [
        "",
        "Artifacts:",
        "",
        "- `scan_results.csv`",
        "- `summary.json`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan existing event-option result dirs by pre-2026 selection metrics and 2026 holdout lineage."
    )
    parser.add_argument("--result-root", default=str(DEFAULT_RESULT_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--select-start-month", default="202501")
    parser.add_argument("--select-end-month", default="202512")
    parser.add_argument("--test-start-month", default="202601")
    parser.add_argument("--test-end-month", default="202604")
    parser.add_argument("--max-test-evidence-month", default="202512")
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--exclude-diagnostics", action="store_true")
    args = parser.parse_args()

    result_root = Path(args.result_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dirs = candidate_result_dirs(result_root, include_diagnostics=not bool(args.exclude_diagnostics))
    workers = max(1, int(args.workers))
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(scan_one, path, args) for path in dirs]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=rank_key)

    eligible = [row for row in rows if bool(row.get("eligible_pre2026_selection"))]
    lineage_clean = [row for row in eligible if bool(row.get("test_pass_with_lineage"))]
    rank_fields_are_pre2026_only = not any(field.startswith("test_") or field.startswith("forward_") for field in RANK_FIELDS)
    payload = {
        "schema_version": 1,
        "audit": "existing_event_option_pre2026_selection_scan",
        "evaluated_dirs": len(rows),
        "eligible_pre2026_selection": len(eligible),
        "eligible_and_test_pass": len(lineage_clean),
        "rank_fields": list(RANK_FIELDS),
        "rank_fields_are_pre2026_only": bool(rank_fields_are_pre2026_only),
        "selection_months": month_range(str(args.select_start_month), str(args.select_end_month)),
        "test_months": month_range(str(args.test_start_month), str(args.test_end_month)),
        "max_test_evidence_month": str(args.max_test_evidence_month),
        "tickers": [str(item).upper() for item in args.tickers],
        "top_lineage_clean_holdout": lineage_clean[0] if lineage_clean else {},
        "top_rows": rows[:25],
        "caveat": (
            "This scan prevents forward columns in ranking, but it cannot prove the result-directory universe "
            "was frozen before 2026. Use it as triage, not as final production proof."
        ),
    }

    write_csv(output_dir / "scan_results.csv", rows)
    (output_dir / "summary.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_markdown(output_dir / "SUMMARY.md", payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
