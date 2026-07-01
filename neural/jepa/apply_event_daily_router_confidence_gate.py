from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from apply_event_monthly_volume_backfill import apply_backfill, load_trades, write_plot
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics, score_metrics


def filter_primary(primary: pd.DataFrame, threshold: float, pred_col: str) -> pd.DataFrame:
    out = primary.copy()
    pred = pd.to_numeric(out[pred_col], errors="coerce").fillna(float("-inf"))
    out = out[pred >= float(threshold)].copy()
    out["confidence_threshold"] = float(threshold)
    return out


def run_backfill_for_months(
    primary: pd.DataFrame,
    fallback: pd.DataFrame,
    threshold: float,
    months: list[str],
    args: argparse.Namespace,
) -> pd.DataFrame:
    if not months:
        return pd.DataFrame()
    local_args = argparse.Namespace(**vars(args))
    local_args.start_month = min(months)
    local_args.end_month = max(months)
    gated = filter_primary(primary, float(threshold), str(args.pred_col))
    selected = apply_backfill(gated, fallback, local_args)
    if not selected.empty:
        selected["confidence_threshold"] = float(threshold)
    return selected


def selection_score(row: dict, args: argparse.Namespace) -> float:
    score = score_metrics(
        row,
        int(args.min_select_trades),
        int(args.min_select_month_trades),
        float(args.min_select_pf),
        float(args.min_select_win_rate),
        float(args.min_call_rate),
        float(args.max_call_rate),
    )
    positive_month_rate = float(row.get("positive_month_rate", 0.0) or 0.0)
    if bool(args.require_select_positive_months) and positive_month_rate < 1.0:
        score -= 1_000_000.0 + 1000.0 * (1.0 - positive_month_rate)
    if np.isfinite(float(args.max_select_top5_share)):
        top5_share = float(row.get("top5_share_of_pnl", float("nan")))
        if not np.isfinite(top5_share) or top5_share < 0.0 or top5_share > float(args.max_select_top5_share):
            score -= 1_000_000.0
    pnl = float(row.get("pnl_return", 0.0) or 0.0)
    drawdown = abs(float(row.get("max_drawdown", 0.0) or 0.0))
    drawdown_to_pnl = drawdown / pnl if pnl > 0.0 else float("inf")
    if np.isfinite(float(args.max_select_drawdown_to_pnl)) and drawdown_to_pnl > float(args.max_select_drawdown_to_pnl):
        score -= 1_000_000.0
    score += min(max(float(row.get("profit_factor", 0.0) or 0.0), 0.0), float(args.score_pf_cap)) * float(args.score_pf_weight)
    score += float(row.get("win_rate", 0.0) or 0.0) * float(args.score_win_weight)
    score += pnl * float(args.score_return_weight)
    score += positive_month_rate * float(args.score_positive_month_weight)
    score += min(float(row.get("min_month_trades", 0.0) or 0.0), 60.0) * float(args.score_volume_weight)
    return float(score)


def selection_passed(row: dict, args: argparse.Namespace) -> bool:
    base_score = score_metrics(
        row,
        int(args.min_select_trades),
        int(args.min_select_month_trades),
        float(args.min_select_pf),
        float(args.min_select_win_rate),
        float(args.min_call_rate),
        float(args.max_call_rate),
    )
    if base_score <= -1e17:
        return False
    positive_month_rate = float(row.get("positive_month_rate", 0.0) or 0.0)
    if bool(args.require_select_positive_months) and positive_month_rate < 1.0:
        return False
    if np.isfinite(float(args.max_select_top5_share)):
        top5_share = float(row.get("top5_share_of_pnl", float("nan")))
        if not np.isfinite(top5_share) or top5_share < 0.0 or top5_share > float(args.max_select_top5_share):
            return False
    pnl = float(row.get("pnl_return", 0.0) or 0.0)
    drawdown = abs(float(row.get("max_drawdown", 0.0) or 0.0))
    drawdown_to_pnl = drawdown / pnl if pnl > 0.0 else float("inf")
    if np.isfinite(float(args.max_select_drawdown_to_pnl)) and drawdown_to_pnl > float(args.max_select_drawdown_to_pnl):
        return False
    return True


def select_threshold(
    primary: pd.DataFrame,
    fallback: pd.DataFrame,
    select_months: list[str],
    thresholds: list[float],
    args: argparse.Namespace,
) -> tuple[float, dict, float, bool, list[dict]]:
    best_threshold = float(args.default_threshold)
    best_metrics = metrics(
        run_backfill_for_months(primary, fallback, best_threshold, select_months, args),
        select_months,
    )
    best_score = selection_score(best_metrics, args)
    best_passed = selection_passed(best_metrics, args)
    rows: list[dict] = []
    for threshold in thresholds:
        selected = run_backfill_for_months(primary, fallback, float(threshold), select_months, args)
        row = metrics(selected, select_months)
        score = selection_score(row, args)
        passed = selection_passed(row, args)
        record = {"threshold": float(threshold), "select_score": score, "select_passed": passed}
        record.update(row)
        rows.append(record)
        if score > best_score:
            best_threshold = float(threshold)
            best_metrics = row
            best_score = score
            best_passed = passed
    return best_threshold, best_metrics, best_score, best_passed, rows


def walkforward(primary: pd.DataFrame, fallback: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    eval_months = month_range(str(args.start_month), str(args.end_month))
    history_months = month_range(str(args.history_start_month), str(args.end_month))
    thresholds = [float(x) for x in args.threshold_grid]
    out_parts: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    candidate_rows: list[dict] = []

    primary = primary[primary["month"].astype(str).isin(history_months)].copy()
    fallback = fallback[fallback["month"].astype(str).isin(history_months)].copy()
    for month in eval_months:
        previous = [m for m in history_months if m < month]
        if len(previous) < int(args.select_months):
            select_months: list[str] = []
            threshold = float(args.default_threshold)
            select_row = metrics(pd.DataFrame(), [])
            select_score = float("nan")
            select_pass = False
            mode = "NO_HISTORY"
        else:
            select_months = previous[-int(args.select_months):]
            threshold, select_row, select_score, select_pass, candidates = select_threshold(primary, fallback, select_months, thresholds, args)
            for row in candidates:
                row.update({"test_month": month, "select_months": ",".join(select_months)})
                candidate_rows.append(row)
            mode = "SELECTED"

        if bool(args.fail_closed_on_select_fail) and not select_pass:
            selected = pd.DataFrame()
            mode = "SELECT_FAIL" if mode == "SELECTED" else mode
        else:
            selected = run_backfill_for_months(primary, fallback, threshold, [month], args)
        if not selected.empty:
            selected["confidence_gate_mode"] = mode
            selected["confidence_select_months"] = ",".join(select_months)
            out_parts.append(selected)
        test_row = metrics(selected, [month])
        fold = {
            "ticker": str(args.ticker).upper(),
            "test_month": month,
            "mode": mode,
            "threshold": float(threshold),
            "select_months": ",".join(select_months),
            "select_score": select_score,
            "select_passed": bool(select_pass),
        }
        fold.update({f"select_{k}": v for k, v in select_row.items()})
        fold.update({f"test_{k}": v for k, v in test_row.items()})
        fold_rows.append(fold)

    trades = pd.concat(out_parts, ignore_index=True, sort=False) if out_parts else pd.DataFrame()
    return trades, pd.DataFrame(fold_rows), pd.DataFrame(candidate_rows)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, candidates: pd.DataFrame, args: argparse.Namespace) -> None:
    expected = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, expected)
    by_ticker = {ticker: metrics(part, expected) for ticker, part in trades.groupby("ticker", sort=True)} if not trades.empty else {}
    payload = {
        "overall": overall,
        "by_ticker": by_ticker,
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "risk_capital": float(args.risk_capital),
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    monthly_rows = []
    for month in expected:
        part = trades[trades["month"].astype(str).eq(month)].copy() if not trades.empty else trades
        row = metrics(part, [month])
        row["month"] = month
        row["pnl_dollars"] = float(row["pnl_return"]) * float(args.risk_capital)
        monthly_rows.append(row)
    lines = [
        "# Event Daily Router Confidence Gate",
        "",
        "This result selects a per-month confidence threshold using only prior OOS months, filters the primary daily-router stream, then applies deterministic monthly volume backfill.",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        f"- Risk capital: ${float(args.risk_capital):,.0f}",
        f"- Net PnL: ${payload['net_pnl']:,.0f}",
        "",
        "## By Ticker",
        "",
        "```json",
        json.dumps(by_ticker, indent=2, allow_nan=True),
        "```",
        "",
        "## Monthly",
        "",
        "| Month | Trades | WR | PF | PnL Return | PnL $ |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in monthly_rows:
        lines.append(
            f"| {row['month']} | {int(row['trades'])} | {float(row['win_rate']):.1%} | "
            f"{float(row['profit_factor']):.3f} | {float(row['pnl_return']):.3f} | "
            f"{float(row['pnl_dollars']):,.0f} |"
        )
    lines += [
        "",
        "## Folds",
        "",
        "```csv",
        folds.to_csv(index=False),
        "```",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(vars(args), indent=2, allow_nan=True),
        "```",
    ]
    if not candidates.empty:
        lines += [
            "",
            "## Candidate Thresholds",
            "",
            "```csv",
            candidates.to_csv(index=False),
            "```",
        ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward confidence gate for an event daily source router.")
    parser.add_argument("--primary-trades", required=True)
    parser.add_argument("--fallback-trades", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ticker", default="SPY")
    parser.add_argument("--history-start-month", default="202507")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--select-months", type=int, default=2)
    parser.add_argument("--threshold-grid", nargs="+", type=float, default=[-999.0, -0.20, -0.10, -0.05, 0.0, 0.025, 0.05, 0.10, 0.15])
    parser.add_argument("--default-threshold", type=float, default=-999.0)
    parser.add_argument("--pred-col", default="daily_router_pred_return")
    parser.add_argument("--primary-name", default="daily_router")
    parser.add_argument("--fallback-name", default="topk")
    parser.add_argument("--min-month-trades", type=int, default=24)
    parser.add_argument("--max-day", type=int, default=4)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--min-entry-minute", type=int, default=660)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--min-select-trades", type=int, default=36)
    parser.add_argument("--min-select-month-trades", type=int, default=18)
    parser.add_argument("--min-select-win-rate", type=float, default=0.45)
    parser.add_argument("--min-select-pf", type=float, default=1.10)
    parser.add_argument("--require-select-positive-months", action="store_true")
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--score-pf-weight", type=float, default=3.0)
    parser.add_argument("--score-pf-cap", type=float, default=4.0)
    parser.add_argument("--score-win-weight", type=float, default=20.0)
    parser.add_argument("--score-return-weight", type=float, default=0.10)
    parser.add_argument("--score-positive-month-weight", type=float, default=4.0)
    parser.add_argument("--score-volume-weight", type=float, default=0.10)
    parser.add_argument("--max-select-top5-share", type=float, default=float("inf"))
    parser.add_argument("--max-select-drawdown-to-pnl", type=float, default=float("inf"))
    parser.add_argument("--fail-closed-on-select-fail", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    primary = load_trades(Path(args.primary_trades), str(args.primary_name))
    fallback = load_trades(Path(args.fallback_trades), str(args.fallback_name))
    primary = primary[primary["ticker"].astype(str).str.upper().eq(str(args.ticker).upper())].copy()
    fallback = fallback[fallback["ticker"].astype(str).str.upper().eq(str(args.ticker).upper())].copy()
    if str(args.pred_col) not in primary.columns:
        raise ValueError(f"Primary trades missing prediction column: {args.pred_col}")
    if int(args.min_entry_minute) > 0:
        fallback = fallback[pd.to_numeric(fallback["entry_minute"], errors="coerce").fillna(0).astype(int) >= int(args.min_entry_minute)].copy()

    trades, folds, candidates = walkforward(primary, fallback, args)
    trades.to_csv(output_dir / "confidence_gate_trades.csv", index=False)
    folds.to_csv(output_dir / "confidence_gate_folds.csv", index=False)
    candidates.to_csv(output_dir / "confidence_gate_threshold_candidates.csv", index=False)
    pd.DataFrame([vars(args)]).to_csv(output_dir / "confidence_gate_config.csv", index=False)
    write_plot(output_dir, trades, float(args.risk_capital))
    write_summary(output_dir, trades, folds, candidates, args)
    print(json.dumps({"overall": metrics(trades, month_range(str(args.start_month), str(args.end_month))), "trades": int(len(trades))}, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
