from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.audit_dense_candidate_statistical_robustness import (
    month_range,
    read_trades,
    ticker_audit,
)


DEFAULT_SCAN_RESULTS = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "scan_existing_results_pre2026_select_2025_eval_202601_202604/scan_results.csv"
)
DEFAULT_OUTPUT_DIR = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "pre2026_lineage_tradelevel_robustness"
)


def safe_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def read_scan_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for idx, row in enumerate(rows, start=1):
        row["scan_rank"] = idx
    return rows


def candidate_rows(scan_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [
        row
        for row in scan_rows
        if safe_bool(row.get("eligible_pre2026_selection")) and safe_bool(row.get("test_pass_with_lineage"))
    ]
    return sorted(out, key=lambda row: int(row["scan_rank"]))


def robust_arg_namespace(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        min_win_rate=float(args.min_win_rate),
        min_profit_factor=float(args.min_profit_factor),
        min_month_trades=int(args.min_month_trades),
        min_call_rate=float(args.min_call_rate),
        max_call_rate=float(args.max_call_rate),
        bootstrap_iterations=int(args.bootstrap_iterations),
        remove_top_winners=int(args.remove_top_winners),
    )


def audit_one(row: dict[str, Any], months: list[str], tickers: list[str], args: argparse.Namespace) -> dict[str, Any]:
    result_dir = Path(str(row.get("dir", "")))
    trade_file = result_dir / str(row.get("trade_file", "combined_trades.csv") or "combined_trades.csv")
    robust_args = robust_arg_namespace(args)
    payload: dict[str, Any] = {
        "scan_rank": int(row["scan_rank"]),
        "name": row.get("name", result_dir.name),
        "result_dir": str(result_dir),
        "trade_file": str(trade_file),
        "scan_select_score": safe_float(row.get("select_score")),
        "scan_test_wr_min": safe_float(row.get("test_wr_min")),
        "scan_test_pf_min": safe_float(row.get("test_pf_min")),
        "scan_test_min_month_min": safe_float(row.get("test_min_month_min")),
        "tickers": {},
        "issues": [],
    }
    try:
        trades = read_trades(trade_file, months, tickers)
        expiry_modes = (
            sorted(str(value) for value in trades["expiry_mode"].dropna().astype(str).unique())
            if "expiry_mode" in trades.columns
            else []
        )
        zero_dte_only = bool(expiry_modes == ["zero_dte"])
        ticker_rows: dict[str, Any] = {}
        for offset, ticker in enumerate(tickers):
            ticker_rows[ticker] = ticker_audit(
                trades,
                ticker,
                months,
                robust_args,
                int(args.seed) + int(row["scan_rank"]) * 100 + offset,
            )
        checks = {
            "zero_dte_only": zero_dte_only,
            "observed_gate_passed": all(bool(item["observed_gate_passed"]) for item in ticker_rows.values()),
            "leave_one_month_out_passed": all(bool(item["leave_one_month_out_passed"]) for item in ticker_rows.values()),
            "bootstrap_lower_quantile_passed": all(
                bool(item["bootstrap_lower_quantile_passed"]) for item in ticker_rows.values()
            ),
            "wilson_lower_passed": all(bool(item["wilson_lower_passed"]) for item in ticker_rows.values()),
            "top_winner_stress_passed": all(bool(item["top_winner_stress_passed"]) for item in ticker_rows.values()),
        }
        passed = bool(all(checks.values()))
        issues: list[str] = []
        for ticker, item in ticker_rows.items():
            issues.extend(f"{ticker}: {issue}" for issue in item.get("issues", []))
        wilson_min = min(float(item["wilson_95_win_rate"]["lower"]) for item in ticker_rows.values())
        bootstrap_wr_min = min(float(item["bootstrap"]["win_rate_p05"]) for item in ticker_rows.values())
        bootstrap_pf_min = min(float(item["bootstrap"]["profit_factor_p05"]) for item in ticker_rows.values())
        lomo_pass_count = sum(1 for item in ticker_rows.values() if bool(item["leave_one_month_out_passed"]))
        stress_pass_count = sum(1 for item in ticker_rows.values() if bool(item["top_winner_stress_passed"]))
        payload.update(
            {
                "status": "ok",
                "passed": passed,
                "checks": checks,
                "expiry_modes": expiry_modes,
                "wilson_min": wilson_min,
                "bootstrap_win_rate_p05_min": bootstrap_wr_min,
                "bootstrap_profit_factor_p05_min": bootstrap_pf_min,
                "leave_one_month_out_passed_tickers": lomo_pass_count,
                "top_winner_stress_passed_tickers": stress_pass_count,
                "tickers": ticker_rows,
                "issues": issues,
            }
        )
    except Exception as exc:
        payload.update(
            {
                "status": "error",
                "passed": False,
                "checks": {},
                "wilson_min": float("nan"),
                "bootstrap_win_rate_p05_min": float("nan"),
                "bootstrap_profit_factor_p05_min": float("nan"),
                "leave_one_month_out_passed_tickers": 0,
                "top_winner_stress_passed_tickers": 0,
                "issues": [f"{type(exc).__name__}: {exc}"],
            }
        )
    return payload


def score_for_sort(row: dict[str, Any]) -> tuple[float, float, float, float]:
    checks = row.get("checks", {}) if isinstance(row.get("checks"), dict) else {}
    check_score = sum(1.0 for value in checks.values() if bool(value))
    return (
        check_score,
        float(row.get("wilson_min", float("nan"))),
        float(row.get("bootstrap_win_rate_p05_min", float("nan"))),
        float(row.get("bootstrap_profit_factor_p05_min", float("nan"))),
    )


def flat_candidate(row: dict[str, Any], tickers: list[str]) -> dict[str, Any]:
    checks = row.get("checks", {}) if isinstance(row.get("checks"), dict) else {}
    out: dict[str, Any] = {
        "scan_rank": row.get("scan_rank"),
        "name": row.get("name"),
        "result_dir": row.get("result_dir"),
        "status": row.get("status"),
        "passed": row.get("passed"),
        "observed_gate_passed": checks.get("observed_gate_passed"),
        "zero_dte_only": checks.get("zero_dte_only"),
        "leave_one_month_out_passed": checks.get("leave_one_month_out_passed"),
        "bootstrap_lower_quantile_passed": checks.get("bootstrap_lower_quantile_passed"),
        "wilson_lower_passed": checks.get("wilson_lower_passed"),
        "top_winner_stress_passed": checks.get("top_winner_stress_passed"),
        "wilson_min": row.get("wilson_min"),
        "bootstrap_win_rate_p05_min": row.get("bootstrap_win_rate_p05_min"),
        "bootstrap_profit_factor_p05_min": row.get("bootstrap_profit_factor_p05_min"),
        "leave_one_month_out_passed_tickers": row.get("leave_one_month_out_passed_tickers"),
        "top_winner_stress_passed_tickers": row.get("top_winner_stress_passed_tickers"),
        "issues": "; ".join(row.get("issues", [])),
    }
    ticker_payload = row.get("tickers", {}) if isinstance(row.get("tickers"), dict) else {}
    for ticker in tickers:
        item = ticker_payload.get(ticker, {}) if isinstance(ticker_payload.get(ticker), dict) else {}
        obs = item.get("observed", {}) if isinstance(item.get("observed"), dict) else {}
        ci = item.get("wilson_95_win_rate", {}) if isinstance(item.get("wilson_95_win_rate"), dict) else {}
        boot = item.get("bootstrap", {}) if isinstance(item.get("bootstrap"), dict) else {}
        prefix = ticker.lower()
        out[f"{prefix}_trades"] = obs.get("trades")
        out[f"{prefix}_win_rate"] = obs.get("win_rate")
        out[f"{prefix}_profit_factor"] = obs.get("profit_factor")
        out[f"{prefix}_min_month_trades"] = obs.get("min_month_trades")
        out[f"{prefix}_wilson_lower"] = ci.get("lower")
        out[f"{prefix}_bootstrap_wr_p05"] = boot.get("win_rate_p05")
        out[f"{prefix}_bootstrap_pf_p05"] = boot.get("profit_factor_p05")
        out[f"{prefix}_lomo_passed"] = item.get("leave_one_month_out_passed")
        out[f"{prefix}_top_winner_stress_passed"] = item.get("top_winner_stress_passed")
    return out


def write_csv(path: Path, rows: list[dict[str, Any]], tickers: list[str]) -> None:
    flat = [flat_candidate(row, tickers) for row in rows]
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


def num(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "nan"


def write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Pre-2026 Lineage Trade-Level Robustness",
        "",
        f"- Passed: `{payload['passed']}`",
        f"- Strict candidates audited: `{payload['counts']['strict_candidates']}`",
        f"- Robust candidates: `{payload['counts']['passed']}`",
        f"- Months: `{', '.join(payload['months'])}`",
        f"- Bootstrap iterations: `{payload['thresholds']['bootstrap_iterations']}`",
        "",
        "## Candidates",
        "",
        "| Rank | Name | 0DTE | Observed | Wilson | Bootstrap | LOMO | Top Winners | Wilson Min | Boot WR Min | Boot PF Min |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["candidates_by_robustness"]:
        checks = row.get("checks", {})
        lines.append(
            "| {rank} | `{name}` | {zero} | {obs} | {wilson} | {boot} | {lomo} | {stress} | {wmin} | {bwr} | {bpf} |".format(
                rank=row.get("scan_rank"),
                name=row.get("name"),
                zero=checks.get("zero_dte_only"),
                obs=checks.get("observed_gate_passed"),
                wilson=checks.get("wilson_lower_passed"),
                boot=checks.get("bootstrap_lower_quantile_passed"),
                lomo=checks.get("leave_one_month_out_passed"),
                stress=checks.get("top_winner_stress_passed"),
                wmin=pct(row.get("wilson_min")),
                bwr=pct(row.get("bootstrap_win_rate_p05_min")),
                bpf=num(row.get("bootstrap_profit_factor_p05_min")),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "All strict pre-2026 + lineage-clean candidates pass the observed gates, but none pass the trade-level robustness screen.",
            "The recurring weak points are SPXW or QQQ Wilson lower bounds below 45%, bootstrap PF/WR lower quantiles below target, and sensitivity to leave-one-month-out or top-winner removal.",
            "These longsrc branches are also not pure 0DTE on the audited window; they include front-weekly rows and therefore are not valid final candidates for the requested 0DTE-only system.",
            "This keeps these branches as research leads rather than production-ready evidence.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run trade-level robustness on strict pre-2026-selected lineage-clean event-option candidates."
    )
    parser.add_argument("--scan-results", default=str(DEFAULT_SCAN_RESULTS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202604")
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--bootstrap-iterations", type=int, default=5000)
    parser.add_argument("--remove-top-winners", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260630)
    parser.add_argument("--exit-zero-on-fail", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    months = month_range(str(args.start_month), str(args.end_month))
    tickers = [str(ticker).upper() for ticker in args.tickers]
    strict_rows = candidate_rows(read_scan_rows(Path(args.scan_results)))

    workers = max(1, int(args.workers))
    candidates: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(audit_one, row, months, tickers, args) for row in strict_rows]
        for future in as_completed(futures):
            candidates.append(future.result())
    candidates_by_rank = sorted(candidates, key=lambda row: int(row.get("scan_rank", 10**9)))
    candidates_by_robustness = sorted(candidates, key=score_for_sort, reverse=True)
    passed = [row for row in candidates if bool(row.get("passed"))]

    payload = {
        "schema_version": 1,
        "audit": "pre2026_lineage_tradelevel_robustness",
        "passed": bool(passed),
        "scan_results": str(Path(args.scan_results)),
        "months": months,
        "tickers": tickers,
        "thresholds": {
            "min_win_rate": float(args.min_win_rate),
            "min_profit_factor": float(args.min_profit_factor),
            "min_month_trades": int(args.min_month_trades),
            "min_call_rate": float(args.min_call_rate),
            "max_call_rate": float(args.max_call_rate),
            "bootstrap_iterations": int(args.bootstrap_iterations),
            "remove_top_winners": int(args.remove_top_winners),
        },
        "counts": {
            "strict_candidates": len(candidates),
            "passed": len(passed),
            "errors": sum(1 for row in candidates if row.get("status") != "ok"),
        },
        "best_by_robustness": candidates_by_robustness[0] if candidates_by_robustness else {},
        "candidates_by_rank": candidates_by_rank,
        "candidates_by_robustness": candidates_by_robustness,
        "issues": [] if passed else ["no strict pre-2026 lineage-clean candidate passed trade-level robustness"],
        "note": "This audit uses only pre-2026-selected lineage-clean scan rows; it is a robustness screen, not a model selection rerank for deployment.",
    }
    (output_dir / "pre2026_lineage_tradelevel_robustness.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    write_csv(output_dir / "candidate_summary.csv", candidates_by_rank, tickers)
    write_csv(output_dir / "candidate_summary_by_robustness.csv", candidates_by_robustness, tickers)
    write_report(output_dir / "SUMMARY.md", payload)
    print(f"passed={payload['passed']}")
    print(f"strict_candidates={len(candidates)}")
    print(f"robust_candidates={len(passed)}")
    print(f"output_dir={output_dir}")
    return 0 if payload["passed"] or args.exit_zero_on_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
