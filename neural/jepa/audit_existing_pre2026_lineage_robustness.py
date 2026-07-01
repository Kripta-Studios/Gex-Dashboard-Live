from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any


DEFAULT_SCAN_RESULTS = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "scan_existing_results_pre2026_select_2025_eval_202601_202604/scan_results.csv"
)
DEFAULT_SCAN_SUMMARY = DEFAULT_SCAN_RESULTS.with_name("summary.json")
DEFAULT_OUTPUT_DIR = Path(
    "research_papers/JEPA/results/_diagnostics/existing_pre2026_lineage_robustness_scan"
)


def safe_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def safe_int(value: Any, default: int = 0) -> int:
    out = safe_float(value, float("nan"))
    return int(out) if math.isfinite(out) else default


def wilson_interval(wins: int, n: int, z: float = 1.959963984540054) -> dict[str, float]:
    if n <= 0:
        return {"lower": float("nan"), "upper": float("nan")}
    p = wins / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt((p * (1.0 - p) / n) + (z * z / (4.0 * n * n))) / denom
    return {"lower": float(max(0.0, center - half)), "upper": float(min(1.0, center + half))}


def read_scan(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for idx, row in enumerate(rows, start=1):
        row["scan_rank"] = idx
    return rows


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def ticker_robustness(row: dict[str, Any], ticker: str, args: argparse.Namespace) -> dict[str, Any]:
    key = ticker.lower()
    trades = safe_int(row.get(f"test_{key}_trades"))
    win_rate = safe_float(row.get(f"test_{key}_win_rate"))
    wins = int(round(trades * win_rate)) if trades > 0 and math.isfinite(win_rate) else 0
    ci = wilson_interval(wins, trades)
    profit_factor = safe_float(row.get(f"test_{key}_profit_factor"))
    min_month_trades = safe_int(row.get(f"test_{key}_min_month_trades"))
    observed_gate = bool(
        trades > 0
        and math.isfinite(win_rate)
        and win_rate >= float(args.min_win_rate)
        and math.isfinite(profit_factor)
        and profit_factor >= float(args.min_profit_factor)
        and min_month_trades >= int(args.min_month_trades)
    )
    return {
        "ticker": ticker,
        "trades": trades,
        "wins": wins,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "min_month_trades": min_month_trades,
        "observed_gate_passed": observed_gate,
        "wilson_95_win_rate": ci,
        "wilson_lower_passed": bool(math.isfinite(ci["lower"]) and ci["lower"] >= float(args.min_win_rate)),
    }


def enrich_row(row: dict[str, Any], tickers: list[str], args: argparse.Namespace) -> dict[str, Any]:
    tick = {ticker: ticker_robustness(row, ticker, args) for ticker in tickers}
    wilson_lowers = {
        ticker: payload["wilson_95_win_rate"]["lower"]
        for ticker, payload in tick.items()
        if math.isfinite(payload["wilson_95_win_rate"]["lower"])
    }
    wilson_min_ticker = min(wilson_lowers, key=wilson_lowers.get) if wilson_lowers else ""
    wilson_min = wilson_lowers.get(wilson_min_ticker, float("nan"))
    observed_ticker_gates = bool(all(payload["observed_gate_passed"] for payload in tick.values()))
    wilson_all_tickers_pass = bool(all(payload["wilson_lower_passed"] for payload in tick.values()))
    eligible = safe_bool(row.get("eligible_pre2026_selection"))
    lineage = safe_bool(row.get("test_pass_with_lineage"))
    test_pass = safe_bool(row.get("test_pass"))
    fold_2026_ok = safe_bool(row.get("fold_2026_ok"))
    return {
        "scan_rank": int(row["scan_rank"]),
        "dir": row.get("dir", ""),
        "name": row.get("name", ""),
        "trade_file": row.get("trade_file", ""),
        "eligible_pre2026_selection": eligible,
        "test_pass": test_pass,
        "fold_2026_ok": fold_2026_ok,
        "test_pass_with_lineage": lineage,
        "observed_ticker_gates_passed": observed_ticker_gates,
        "all_ticker_wilson_lower_passed": wilson_all_tickers_pass,
        "strict_pre2026_lineage_candidate": bool(eligible and lineage),
        "strict_pre2026_lineage_robust_passed": bool(eligible and lineage and wilson_all_tickers_pass),
        "any_lineage_robust_passed": bool(lineage and wilson_all_tickers_pass),
        "test_wr_min": safe_float(row.get("test_wr_min")),
        "test_pf_min": safe_float(row.get("test_pf_min")),
        "test_min_month_min": safe_int(row.get("test_min_month_min")),
        "test_pnl_sum": safe_float(row.get("test_pnl_sum")),
        "select_score": safe_float(row.get("select_score")),
        "fold_2026_checked": safe_int(row.get("fold_2026_checked")),
        "fold_2026_issues": row.get("fold_2026_issues", ""),
        "wilson_min": wilson_min,
        "wilson_min_ticker": wilson_min_ticker,
        "tickers": tick,
    }


def flat_row(row: dict[str, Any], tickers: list[str]) -> dict[str, Any]:
    out = {
        key: row.get(key)
        for key in [
            "scan_rank",
            "name",
            "dir",
            "eligible_pre2026_selection",
            "test_pass",
            "fold_2026_ok",
            "test_pass_with_lineage",
            "observed_ticker_gates_passed",
            "all_ticker_wilson_lower_passed",
            "strict_pre2026_lineage_candidate",
            "strict_pre2026_lineage_robust_passed",
            "test_wr_min",
            "test_pf_min",
            "test_min_month_min",
            "test_pnl_sum",
            "wilson_min",
            "wilson_min_ticker",
            "select_score",
            "fold_2026_checked",
            "fold_2026_issues",
        ]
    }
    for ticker in tickers:
        t = row["tickers"][ticker]
        low = t["wilson_95_win_rate"]["lower"]
        high = t["wilson_95_win_rate"]["upper"]
        prefix = ticker.lower()
        out[f"{prefix}_trades"] = t["trades"]
        out[f"{prefix}_wins"] = t["wins"]
        out[f"{prefix}_win_rate"] = t["win_rate"]
        out[f"{prefix}_profit_factor"] = t["profit_factor"]
        out[f"{prefix}_min_month_trades"] = t["min_month_trades"]
        out[f"{prefix}_wilson_lower"] = low
        out[f"{prefix}_wilson_upper"] = high
        out[f"{prefix}_wilson_lower_passed"] = t["wilson_lower_passed"]
    return out


def write_csv(path: Path, rows: list[dict[str, Any]], tickers: list[str]) -> None:
    flat = [flat_row(row, tickers) for row in rows]
    if not flat:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat[0].keys()))
        writer.writeheader()
        writer.writerows(flat)


def pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "nan"


def num(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "nan"


def write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Existing Pre-2026 Lineage Robustness Audit",
        "",
        f"- Passed: `{payload['passed']}`",
        f"- No robust candidate found: `{payload['no_robust_candidate_found']}`",
        f"- Scan results: `{payload['scan_results']}`",
        f"- Eligible pre-2026 selection rows: `{payload['counts']['eligible_pre2026_selection']}`",
        f"- Eligible + lineage-clean holdout pass rows: `{payload['counts']['strict_pre2026_lineage_candidates']}`",
        f"- Eligible + lineage-clean Wilson pass rows: `{payload['counts']['strict_pre2026_lineage_robust_passed']}`",
        f"- Any lineage-clean Wilson pass rows: `{payload['counts']['any_lineage_robust_passed']}`",
        "",
        "## Strict Eligible Lineage Rows",
        "",
        "| Rank | Name | WR Min | PF Min | Wilson Min | Weak Ticker | Robust |",
        "| ---: | --- | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in payload["strict_pre2026_lineage_candidates"][:12]:
        lines.append(
            "| {rank} | `{name}` | {wr} | {pf} | {wilson} | {ticker} | {robust} |".format(
                rank=row["scan_rank"],
                name=row["name"],
                wr=pct(row["test_wr_min"]),
                pf=num(row["test_pf_min"]),
                wilson=pct(row["wilson_min"]),
                ticker=row["wilson_min_ticker"],
                robust=row["strict_pre2026_lineage_robust_passed"],
            )
        )

    best_any = payload.get("best_any_lineage_by_wilson") or {}
    lines.extend(
        [
            "",
            "## Best Any-Lineage Row",
            "",
            f"- Name: `{best_any.get('name', '')}`",
            f"- Eligible by pre-2026 selection scan: `{best_any.get('eligible_pre2026_selection')}`",
            f"- Wilson min: `{pct(best_any.get('wilson_min'))}` on `{best_any.get('wilson_min_ticker', '')}`",
            "",
            "## Rejected High-Metric Rows",
            "",
            "These rows can look attractive on observed WR/PF, but their 2026 fold lineage is not clean under the scan rule.",
            "",
            "| Rank | Name | WR Min | PF Min | Fold Issue |",
            "| ---: | --- | ---: | ---: | --- |",
        ]
    )
    for row in payload["rejected_high_metric_non_lineage"][:8]:
        issue = str(row.get("fold_2026_issues", "")).replace("|", "; ")
        if len(issue) > 120:
            issue = issue[:117] + "..."
        lines.append(
            "| {rank} | `{name}` | {wr} | {pf} | {issue} |".format(
                rank=row["scan_rank"],
                name=row["name"],
                wr=pct(row["test_wr_min"]),
                pf=num(row["test_pf_min"]),
                issue=issue or "none",
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "No existing candidate in this scan gives a 95% Wilson lower-bound proof that all ticker win rates exceed the 45% target.",
            "The high observed WR/PF rows should therefore remain causal research evidence at best, not robust production evidence.",
            "This audit uses only aggregate scan outputs, so it is a lower-bound overfit screen rather than a replacement for trade-level bootstrap and live fill validation.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit existing pre-2026-selected event-option scan rows for lineage-clean statistical robustness."
    )
    parser.add_argument("--scan-results", default=str(DEFAULT_SCAN_RESULTS))
    parser.add_argument("--scan-summary", default=str(DEFAULT_SCAN_SUMMARY))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--tickers", default="SPXW,SPY,QQQ")
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--exit-zero-on-fail", action="store_true")
    args = parser.parse_args()

    tickers = [part.strip().upper() for part in str(args.tickers).split(",") if part.strip()]
    scan_path = Path(args.scan_results)
    summary_path = Path(args.scan_summary)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = [enrich_row(row, tickers, args) for row in read_scan(scan_path)]
    strict = [row for row in rows if row["strict_pre2026_lineage_candidate"]]
    any_lineage = [row for row in rows if row["test_pass_with_lineage"]]
    rejected_high_metric = [
        row
        for row in rows
        if row["eligible_pre2026_selection"] and row["test_pass"] and not row["fold_2026_ok"]
    ]

    strict_by_rank = sorted(strict, key=lambda row: int(row["scan_rank"]))
    strict_by_wilson = sorted(strict, key=lambda row: float(row["wilson_min"]), reverse=True)
    any_lineage_by_wilson = sorted(any_lineage, key=lambda row: float(row["wilson_min"]), reverse=True)
    rejected_high_metric = sorted(rejected_high_metric, key=lambda row: int(row["scan_rank"]))

    write_csv(output_dir / "strict_pre2026_lineage_candidates.csv", strict_by_rank, tickers)
    write_csv(output_dir / "strict_pre2026_lineage_candidates_by_wilson.csv", strict_by_wilson, tickers)
    write_csv(output_dir / "any_lineage_holdout_candidates_by_wilson.csv", any_lineage_by_wilson, tickers)
    write_csv(output_dir / "rejected_high_metric_non_lineage.csv", rejected_high_metric, tickers)
    write_csv(output_dir / "scan_results_with_wilson.csv", rows, tickers)

    scan_summary = read_json(summary_path)
    strict_robust = [row for row in strict if row["strict_pre2026_lineage_robust_passed"]]
    any_lineage_robust = [row for row in any_lineage if row["any_lineage_robust_passed"]]
    issues: list[str] = []
    if not strict:
        issues.append("no strict pre-2026 lineage candidates found")
    if not strict_robust:
        issues.append("no strict pre-2026 lineage candidate passed Wilson robustness")
    if not any_lineage_robust:
        issues.append("no any-lineage candidate passed Wilson robustness")

    payload = {
        "schema_version": 1,
        "audit": "existing_pre2026_lineage_robustness",
        "passed": bool(strict_robust),
        "no_robust_candidate_found": bool(not strict_robust and not any_lineage_robust and strict),
        "scan_results": str(scan_path),
        "scan_summary": str(summary_path),
        "selection_scan_caveat": scan_summary.get("caveat", ""),
        "thresholds": {
            "min_win_rate": float(args.min_win_rate),
            "min_profit_factor": float(args.min_profit_factor),
            "min_month_trades": int(args.min_month_trades),
            "wilson_confidence": 0.95,
        },
        "counts": {
            "total_rows": len(rows),
            "eligible_pre2026_selection": sum(1 for row in rows if row["eligible_pre2026_selection"]),
            "test_pass_with_lineage": len(any_lineage),
            "strict_pre2026_lineage_candidates": len(strict),
            "strict_pre2026_lineage_robust_passed": len(strict_robust),
            "any_lineage_robust_passed": len(any_lineage_robust),
            "rejected_high_metric_non_lineage": len(rejected_high_metric),
        },
        "best_strict_by_scan_rank": strict_by_rank[0] if strict_by_rank else {},
        "best_strict_by_wilson": strict_by_wilson[0] if strict_by_wilson else {},
        "best_any_lineage_by_wilson": any_lineage_by_wilson[0] if any_lineage_by_wilson else {},
        "strict_pre2026_lineage_candidates": strict_by_rank,
        "rejected_high_metric_non_lineage": rejected_high_metric[:20],
        "issues": issues,
        "note": (
            "This audit does not select a model. It checks whether already scanned, lineage-clean "
            "candidates have enough sample support for a 45% WR lower-bound claim."
        ),
    }
    (output_dir / "existing_pre2026_lineage_robustness.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8"
    )
    write_report(output_dir / "SUMMARY.md", payload)

    print(f"passed={payload['passed']}")
    print(f"strict_pre2026_lineage_candidates={len(strict)}")
    print(f"strict_pre2026_lineage_robust_passed={len(strict_robust)}")
    print(f"any_lineage_robust_passed={len(any_lineage_robust)}")
    print(f"output_dir={output_dir}")
    if payload["passed"] or args.exit_zero_on_fail:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
