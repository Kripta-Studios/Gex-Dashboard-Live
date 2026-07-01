from __future__ import annotations

import argparse
from itertools import product
import json
from pathlib import Path

import numpy as np
import pandas as pd

from apply_event_trade_union_window_meta_selector import load_candidate, select_walkforward
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


def build_selector_args(base: argparse.Namespace, rule: dict, start_month: str, end_month: str) -> argparse.Namespace:
    meta_select_months = int(rule["meta_select_months"])
    min_select_trades = int(base.min_select_trades_per_month) * max(meta_select_months, 1)
    return argparse.Namespace(
        selector_source=list(base.selector_source),
        output_dir=str(base.output_dir),
        tickers=list(base.tickers),
        start_month=str(start_month),
        end_month=str(end_month),
        meta_select_months=meta_select_months,
        min_history_months=int(rule["min_history_months"]),
        selection_mode=str(rule["selection_mode"]),
        rank_mode=str(rule["rank_mode"]),
        min_select_trades=min_select_trades,
        min_select_month_trades=int(rule["min_select_month_trades"]),
        relax_min_month_if_empty=bool(rule["relax_min_month_if_empty"]),
        min_select_win_rate=float(base.min_select_win_rate),
        min_select_profit_factor=float(base.min_select_profit_factor),
        score_pf_weight=float(rule["score_pf_weight"]),
        score_pf_cap=float(base.score_pf_cap),
        score_win_weight=float(rule["score_win_weight"]),
        score_return_weight=float(rule["score_return_weight"]),
        score_positive_month_weight=float(rule["score_positive_month_weight"]),
        score_volume_weight=float(rule["score_volume_weight"]),
        score_daily_dd_penalty=float(rule["score_daily_dd_penalty"]),
        score_top5_penalty=float(rule["score_top5_penalty"]),
        risk_capital=float(base.risk_capital),
    )


def rule_grid(args: argparse.Namespace) -> list[dict]:
    rules: list[dict] = []
    for (
        selection_mode,
        meta_select_months,
        rank_mode,
        min_month,
        relax,
        pf_weight,
        win_weight,
        return_weight,
        positive_weight,
        volume_weight,
        dd_penalty,
        top5_penalty,
    ) in product(
        args.selection_mode_grid,
        args.meta_select_months_grid,
        args.rank_mode_grid,
        args.min_select_month_trades_grid,
        args.relax_min_month_if_empty_grid,
        args.score_pf_weight_grid,
        args.score_win_weight_grid,
        args.score_return_weight_grid,
        args.score_positive_month_weight_grid,
        args.score_volume_weight_grid,
        args.score_daily_dd_penalty_grid,
        args.score_top5_penalty_grid,
    ):
        if int(min_month) <= 0 and bool(relax):
            continue
        rules.append(
            {
                "selection_mode": str(selection_mode),
                "meta_select_months": int(meta_select_months),
                "min_history_months": int(meta_select_months),
                "rank_mode": str(rank_mode),
                "min_select_month_trades": int(min_month),
                "relax_min_month_if_empty": bool(relax),
                "score_pf_weight": float(pf_weight),
                "score_win_weight": float(win_weight),
                "score_return_weight": float(return_weight),
                "score_positive_month_weight": float(positive_weight),
                "score_volume_weight": float(volume_weight),
                "score_daily_dd_penalty": float(dd_penalty),
                "score_top5_penalty": float(top5_penalty),
            }
        )
    return rules


def ticker_pass(row: dict, args: argparse.Namespace) -> bool:
    wr = float(row.get("win_rate", 0.0) or 0.0)
    pf = float(row.get("profit_factor", 0.0) or 0.0)
    min_month = int(row.get("min_month_trades", 0) or 0)
    pnl = float(row.get("pnl_return", 0.0) or 0.0)
    return (
        np.isfinite(wr)
        and np.isfinite(pf)
        and wr >= float(args.min_win_rate)
        and pf >= float(args.min_profit_factor)
        and min_month >= int(args.min_month_trades)
        and pnl > 0.0
    )


def summarize_period(
    trades: pd.DataFrame,
    folds: pd.DataFrame,
    months: list[str],
    prefix: str,
    args: argparse.Namespace,
) -> dict:
    out: dict = {}
    ticker_passes: list[bool] = []
    min_pf = float("inf")
    min_wr = float("inf")
    min_month_trades = 10**9
    total_pnl = 0.0
    for ticker in [str(t).upper() for t in args.tickers]:
        part = trades[
            trades.get("ticker", pd.Series(dtype=str)).astype(str).str.upper().eq(ticker)
            & trades.get("month", pd.Series(dtype=str)).astype(str).isin(months)
        ].copy()
        row = metrics(part, months)
        passed = ticker_pass(row, args)
        ticker_passes.append(passed)
        min_pf = min(min_pf, float(row.get("profit_factor", 0.0) or 0.0))
        min_wr = min(min_wr, float(row.get("win_rate", 0.0) or 0.0))
        min_month_trades = min(min_month_trades, int(row.get("min_month_trades", 0) or 0))
        total_pnl += float(row.get("pnl_return", 0.0) or 0.0)
        for key in ("trades", "win_rate", "profit_factor", "pnl_return", "min_month_trades", "positive_month_rate"):
            out[f"{prefix}_{ticker}_{key}"] = row.get(key)
        out[f"{prefix}_{ticker}_passed"] = bool(passed)
    selected_candidates = (
        folds[["ticker", "selected_meta_window_candidate"]]
        .drop_duplicates()
        .sort_values(["ticker", "selected_meta_window_candidate"])
        if not folds.empty and {"ticker", "selected_meta_window_candidate"}.issubset(folds.columns)
        else pd.DataFrame()
    )
    out[f"{prefix}_passed_all"] = bool(all(ticker_passes))
    out[f"{prefix}_min_pf"] = 0.0 if min_pf == float("inf") else min_pf
    out[f"{prefix}_min_wr"] = 0.0 if min_wr == float("inf") else min_wr
    out[f"{prefix}_min_month_trades"] = 0 if min_month_trades == 10**9 else int(min_month_trades)
    out[f"{prefix}_total_pnl_return"] = total_pnl
    out[f"{prefix}_selected_candidates"] = ";".join(
        f"{row.ticker}:{row.selected_meta_window_candidate}" for row in selected_candidates.itertuples(index=False)
    )
    out[f"{prefix}_fold_modes"] = (
        ",".join(sorted(folds["mode"].astype(str).unique().tolist())) if not folds.empty and "mode" in folds.columns else ""
    )
    return out


def validation_score(row: dict, args: argparse.Namespace) -> float:
    score = 0.0
    for ticker in [str(t).upper() for t in args.tickers]:
        wr = float(row.get(f"validation_{ticker}_win_rate", 0.0) or 0.0)
        pf = float(row.get(f"validation_{ticker}_profit_factor", 0.0) or 0.0)
        pnl = float(row.get(f"validation_{ticker}_pnl_return", 0.0) or 0.0)
        min_month = float(row.get(f"validation_{ticker}_min_month_trades", 0.0) or 0.0)
        score += min(pf, 2.0) * 6.0 + wr * 30.0 + pnl * 0.25 + min(min_month, 60.0) * 0.15
        score -= max(0.0, float(args.min_profit_factor) - pf) * 30.0
        score -= max(0.0, float(args.min_win_rate) - wr) * 40.0
        score -= max(0.0, float(args.min_month_trades) - min_month) * 0.75
        if pnl <= 0.0:
            score += pnl * 0.5
    if bool(row.get("validation_passed_all", False)):
        score += 1000.0
    return float(score)


def write_rule_result(
    output_dir: Path,
    label: str,
    candidate_trades: dict[str, pd.DataFrame],
    candidate_folds: dict[str, pd.DataFrame],
    base_args: argparse.Namespace,
    rule: dict,
    start_month: str,
    end_month: str,
) -> None:
    result_dir = output_dir / label
    result_dir.mkdir(parents=True, exist_ok=True)
    selector_args = build_selector_args(base_args, rule, start_month, end_month)
    selector_args.output_dir = str(result_dir)
    trades, folds = select_walkforward(candidate_trades, candidate_folds, selector_args)
    if not trades.empty:
        trades.to_csv(result_dir / "trade_union_window_meta_selector_trades.csv", index=False)
        trades.to_csv(result_dir / "combined_trades.csv", index=False)
    folds.to_csv(result_dir / "trade_union_window_meta_selector_folds.csv", index=False)
    folds.to_csv(result_dir / "combined_folds.csv", index=False)
    months = month_range(str(start_month), str(end_month))
    metric_rows = []
    for ticker in [str(t).upper() for t in base_args.tickers]:
        part = trades[
            trades.get("ticker", pd.Series(dtype=str)).astype(str).str.upper().eq(ticker)
            & trades.get("month", pd.Series(dtype=str)).astype(str).isin(months)
        ].copy()
        metric_rows.append({"period": label, "ticker": ticker, **metrics(part, months)})
    metric_rows.append({"period": label, "ticker": "ALL", **metrics(trades, months)})
    pd.DataFrame(metric_rows).to_csv(result_dir / "metrics_by_period.csv", index=False)
    payload = {"rule": rule, "start_month": start_month, "end_month": end_month, "metrics_by_period": metric_rows}
    (result_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Selected Window Meta Rule Result",
        "",
        f"- Label: `{label}`",
        f"- Months: `{start_month}` to `{end_month}`",
        "",
        "## Metrics",
        "",
        "| Ticker | Trades | WR | PF | Min Trades/Month | PnL R |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in metric_rows:
        lines.append(
            f"| {row['ticker']} | {int(row.get('trades', 0))} | {float(row.get('win_rate', 0.0)):.2%} | "
            f"{float(row.get('profit_factor', 0.0)):.3f} | {int(row.get('min_month_trades', 0))} | "
            f"{float(row.get('pnl_return', 0.0)):.3f} |"
        )
    lines += ["", "## Rule", "", "```json", json.dumps(rule, indent=2), "```"]
    (result_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan causal meta-rules over rolling trade-union window selectors.")
    parser.add_argument("--selector-source", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--validation-start-month", default="202501")
    parser.add_argument("--validation-end-month", default="202512")
    parser.add_argument("--test-start-month", default="202601")
    parser.add_argument("--test-end-month", default="202606")
    parser.add_argument("--selection-mode-grid", nargs="+", default=["frozen", "monthly"])
    parser.add_argument("--meta-select-months-grid", nargs="+", type=int, default=[3, 6, 12])
    parser.add_argument("--rank-mode-grid", nargs="+", default=["continuous", "strict"])
    parser.add_argument("--min-select-trades-per-month", type=int, default=18)
    parser.add_argument("--min-select-month-trades-grid", nargs="+", type=int, default=[0, 18])
    parser.add_argument("--relax-min-month-if-empty-grid", nargs="+", type=int, default=[0, 1])
    parser.add_argument("--min-select-win-rate", type=float, default=0.45)
    parser.add_argument("--min-select-profit-factor", type=float, default=1.30)
    parser.add_argument("--score-pf-weight-grid", nargs="+", type=float, default=[3.0, 6.0])
    parser.add_argument("--score-pf-cap", type=float, default=4.0)
    parser.add_argument("--score-win-weight-grid", nargs="+", type=float, default=[20.0, 30.0])
    parser.add_argument("--score-return-weight-grid", nargs="+", type=float, default=[0.1, 0.5, 1.0])
    parser.add_argument("--score-positive-month-weight-grid", nargs="+", type=float, default=[0.0, 4.0])
    parser.add_argument("--score-volume-weight-grid", nargs="+", type=float, default=[0.1, 0.3])
    parser.add_argument("--score-daily-dd-penalty-grid", nargs="+", type=float, default=[0.05])
    parser.add_argument("--score-top5-penalty-grid", nargs="+", type=float, default=[0.25])
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_trades: dict[str, pd.DataFrame] = {}
    candidate_folds: dict[str, pd.DataFrame] = {}
    for spec in args.selector_source:
        name = spec.split("=", 1)[0] if "=" in spec else Path(spec).name
        trades, folds = load_candidate(spec)
        candidate_trades[name] = trades
        candidate_folds[name] = folds

    validation_months = month_range(str(args.validation_start_month), str(args.validation_end_month))
    test_months = month_range(str(args.test_start_month), str(args.test_end_month))
    rows: list[dict] = []
    rules = rule_grid(args)
    for idx, rule in enumerate(rules):
        val_args = build_selector_args(args, rule, str(args.validation_start_month), str(args.validation_end_month))
        val_trades, val_folds = select_walkforward(candidate_trades, candidate_folds, val_args)
        test_args = build_selector_args(args, rule, str(args.test_start_month), str(args.test_end_month))
        test_trades, test_folds = select_walkforward(candidate_trades, candidate_folds, test_args)
        row = {"rule_id": idx, **rule}
        row.update(summarize_period(val_trades, val_folds, validation_months, "validation", args))
        row.update(summarize_period(test_trades, test_folds, test_months, "test", args))
        row["validation_selection_score"] = validation_score(row, args)
        rows.append(row)

    scan = pd.DataFrame(rows).sort_values(
        ["validation_passed_all", "validation_selection_score", "test_passed_all"],
        ascending=[False, False, False],
    )
    scan.to_csv(output_dir / "window_meta_rule_scan.csv", index=False)
    if scan.empty:
        raise RuntimeError("No rules scanned.")
    best = scan.iloc[0].to_dict()
    best_rule = {key: best[key] for key in rules[0].keys()}
    write_rule_result(
        output_dir,
        "selected_by_validation_validation_period",
        candidate_trades,
        candidate_folds,
        args,
        best_rule,
        str(args.validation_start_month),
        str(args.validation_end_month),
    )
    write_rule_result(
        output_dir,
        "selected_by_validation_test_period",
        candidate_trades,
        candidate_folds,
        args,
        best_rule,
        str(args.test_start_month),
        str(args.test_end_month),
    )
    summary = {
        "status": "scan_complete",
        "rules_scanned": int(len(scan)),
        "validation_pass_rules": int(scan["validation_passed_all"].sum()),
        "test_pass_rules": int(scan["test_passed_all"].sum()),
        "both_pass_rules": int((scan["validation_passed_all"] & scan["test_passed_all"]).sum()),
        "best_rule": best_rule,
        "best_validation_passed_all": bool(best["validation_passed_all"]),
        "best_test_passed_all": bool(best["test_passed_all"]),
        "best_validation_score": float(best["validation_selection_score"]),
        "best_validation_selected_candidates": best.get("validation_selected_candidates", ""),
        "best_test_selected_candidates": best.get("test_selected_candidates", ""),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Window Meta Rule Scan",
        "",
        f"- Rules scanned: {summary['rules_scanned']}",
        f"- Validation pass rules: {summary['validation_pass_rules']}",
        f"- Test pass rules: {summary['test_pass_rules']}",
        f"- Both pass rules: {summary['both_pass_rules']}",
        f"- Best validation rule passes validation: {summary['best_validation_passed_all']}",
        f"- Best validation rule passes test: {summary['best_test_passed_all']}",
        "",
        "## Best Rule",
        "",
        "```json",
        json.dumps(best_rule, indent=2),
        "```",
        "",
        "## Top Rows",
        "",
        "```csv",
        scan.head(20).to_csv(index=False),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
