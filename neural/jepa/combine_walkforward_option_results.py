from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.search_option_structural_profiles import metrics, month_list  # noqa: E402
from neural.jepa.walkforward_structural_option_profiles import empty_metrics  # noqa: E402


def requirement_summary(overall: dict, per_ticker: dict[str, dict], tickers: list[str], args: argparse.Namespace) -> dict:
    checks: dict[str, dict] = {}
    for ticker in tickers:
        item = per_ticker.get(ticker, empty_metrics())
        pf = float(item.get("profit_factor", 0.0))
        pnl = float(item.get("pnl_dollars", 0.0))
        wr = float(item.get("win_rate", float("nan")))
        long_rate = float(item.get("long_rate", float("nan")))
        checks[ticker] = {
            "profitable": bool(pnl > float(args.min_test_pnl) and pf >= float(args.min_test_pf)),
            "win_rate_ok": bool(math.isfinite(wr) and wr >= float(args.min_test_win_rate)),
            "volume_ok": bool(int(item.get("min_month_trades", 0)) >= int(args.min_test_month_trades)),
            "both_sides_ok": bool(
                math.isfinite(long_rate)
                and long_rate >= float(args.min_test_long_rate)
                and long_rate <= float(args.max_test_long_rate)
            ),
            "metrics": item,
        }
        checks[ticker]["passed"] = bool(
            checks[ticker]["profitable"]
            and checks[ticker]["win_rate_ok"]
            and checks[ticker]["volume_ok"]
            and checks[ticker]["both_sides_ok"]
        )
    return {"overall": overall, "per_ticker": checks, "all_tickers_passed": bool(all(v["passed"] for v in checks.values()))}


def parse_months(value: object) -> list[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def integrity_summary(
    folds: pd.DataFrame,
    selected: pd.DataFrame,
    months: list[str],
    tickers: list[str],
) -> dict:
    issues: list[str] = []
    expected_months = set(months)
    expected_tickers = {ticker.upper() for ticker in tickers}

    if folds.empty:
        issues.append("combined inputs do not include fold_configs.csv")
    else:
        for idx, row in folds.iterrows():
            ticker = str(row.get("ticker", "")).upper()
            test_month = str(row.get("test_month", ""))
            train_months = parse_months(row.get("train_months", ""))
            core_months = parse_months(row.get("core_months", ""))
            val_months = parse_months(row.get("inner_val_months", ""))
            if ticker not in expected_tickers:
                issues.append(f"fold row {idx}: unexpected ticker {ticker}")
            if test_month not in expected_months:
                issues.append(f"fold row {idx}: unexpected test_month {test_month}")
            for name, prior_months in {
                "train_months": train_months,
                "core_months": core_months,
                "inner_val_months": val_months,
            }.items():
                non_prior = [month for month in prior_months if month >= test_month]
                if non_prior:
                    issues.append(f"{ticker} {test_month}: {name} contains non-prior months {non_prior}")
            if set(core_months) & set(val_months):
                issues.append(f"{ticker} {test_month}: core/inner_val overlap")
            if core_months or val_months:
                if not set(core_months).issubset(set(train_months)) or not set(val_months).issubset(set(train_months)):
                    issues.append(f"{ticker} {test_month}: core/inner_val is not subset of train")
                if sorted(core_months + val_months) != sorted(train_months):
                    issues.append(f"{ticker} {test_month}: core + inner_val does not reconstruct train")
            if len(issues) >= 25:
                break

    selected_rows = int(len(selected)) if selected is not None else 0
    if selected is not None and not selected.empty:
        required_cols = {"ticker", "month", "fold_month", "profile_train_months", "profile_inner_val_months"}
        missing = sorted(required_cols.difference(selected.columns))
        if missing:
            issues.append(f"selected_trades missing columns {missing}")
        else:
            for idx, row in selected.iterrows():
                ticker = str(row.get("ticker", "")).upper()
                month = str(row.get("month", ""))
                fold_month = str(row.get("fold_month", ""))
                train_months = parse_months(row.get("profile_train_months", ""))
                val_months = parse_months(row.get("profile_inner_val_months", ""))
                if ticker not in expected_tickers:
                    issues.append(f"selected row {idx}: unexpected ticker {ticker}")
                if fold_month not in expected_months:
                    issues.append(f"selected row {idx}: unexpected fold_month {fold_month}")
                if month != fold_month:
                    issues.append(f"selected row {idx}: trade month {month} != fold_month {fold_month}")
                non_prior = [prior for prior in train_months + val_months if prior >= fold_month]
                if non_prior:
                    issues.append(f"selected row {idx}: profile prior months contain {non_prior}")
                if len(issues) >= 25:
                    break

    return {
        "passed": bool(not issues),
        "folds_checked": int(len(folds)) if folds is not None else 0,
        "selected_rows_checked": selected_rows,
        "issues": issues[:25],
    }


def write_summary(out_dir: Path, summary: dict) -> None:
    lines = [
        "# Combined Nested Walk-Forward Option Results",
        "",
        "## Requirement Check",
        "",
        "| Ticker | Passed | Trades | WR | PF | PnL | Min Month Trades | Long Rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for ticker, item in summary["requirements"]["per_ticker"].items():
        m = item["metrics"]
        lines.append(
            f"| {ticker} | {item['passed']} | {int(m.get('trades', 0))} | "
            f"{float(m.get('win_rate', float('nan'))):.1%} | {float(m.get('profit_factor', float('nan'))):.3f} | "
            f"{float(m.get('pnl_dollars', 0.0)):,.0f} | {int(m.get('min_month_trades', 0))} | "
            f"{float(m.get('long_rate', float('nan'))):.1%} |"
        )
    overall = summary["overall"]
    lines += [
        "",
        "## Overall",
        "",
        f"- Trades: {int(overall.get('trades', 0))}",
        f"- Win rate: {float(overall.get('win_rate', float('nan'))):.1%}",
        f"- Profit factor: {float(overall.get('profit_factor', float('nan'))):.3f}",
        f"- PnL: {float(overall.get('pnl_dollars', 0.0)):,.0f}",
        f"- Min monthly trades: {int(overall.get('min_month_trades', 0))}",
        "",
        "## Walk-Forward Integrity",
        "",
        f"- Passed: {bool(summary.get('integrity', {}).get('passed', False))}",
        f"- Folds checked: {int(summary.get('integrity', {}).get('folds_checked', 0))}",
        f"- Selected rows checked: {int(summary.get('integrity', {}).get('selected_rows_checked', 0))}",
    ]
    issues = summary.get("integrity", {}).get("issues", [])
    if issues:
        lines += [
            "- Issues:",
            *[f"  - {issue}" for issue in issues],
        ]
    lines += [
        "",
        "## JSON",
        "",
        "```json",
        json.dumps(summary, indent=2, allow_nan=True),
        "```",
        "",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Combine per-ticker walk-forward selected_trades.csv outputs.")
    parser.add_argument("--input-dir", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument(
        "--exclude-months",
        nargs="*",
        default=[],
        help="YYYYMM months to exclude from selected rows, folds, and requirement windows.",
    )
    parser.add_argument("--min-test-pf", type=float, default=1.0)
    parser.add_argument("--min-test-pnl", type=float, default=0.0)
    parser.add_argument("--min-test-win-rate", type=float, default=0.0)
    parser.add_argument("--min-test-month-trades", type=int, default=15)
    parser.add_argument("--min-test-long-rate", type=float, default=0.20)
    parser.add_argument("--max-test-long-rate", type=float, default=0.80)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []
    fold_frames: list[pd.DataFrame] = []
    for raw_dir in args.input_dir:
        input_dir = Path(raw_dir)
        path = input_dir / "selected_trades.csv"
        if path.exists():
            frame = pd.read_csv(path).copy()
            frame = frame.assign(source_result_dir=str(input_dir))
            frames.append(frame)
        fold_path = input_dir / "fold_configs.csv"
        if fold_path.exists():
            fold_frame = pd.read_csv(fold_path).copy()
            fold_frame = fold_frame.assign(source_result_dir=str(input_dir))
            fold_frames.append(fold_frame)
    selected = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    excluded_months = {str(month)[:6] for month in args.exclude_months}
    if not selected.empty:
        selected["ticker"] = selected["ticker"].astype(str).str.upper()
        selected["month"] = selected["month"].astype(str)
        selected = selected[selected["ticker"].isin([t.upper() for t in args.tickers])].copy()
        if excluded_months:
            selected = selected[~selected["month"].isin(excluded_months)].copy()
        selected = selected.sort_values(["date", "time", "ticker", "candidate_id"]).reset_index(drop=True)
        selected.to_csv(out_dir / "selected_trades.csv", index=False)
    folds = pd.concat(fold_frames, ignore_index=True) if fold_frames else pd.DataFrame()
    if not folds.empty:
        folds["ticker"] = folds["ticker"].astype(str).str.upper()
        folds["test_month"] = folds["test_month"].astype(str)
        folds = folds[folds["ticker"].isin([t.upper() for t in args.tickers])].copy()
        folds = folds[folds["test_month"].isin(month_list(args.start_month, args.end_month))].copy()
        if excluded_months:
            folds = folds[~folds["test_month"].isin(excluded_months)].copy()
        folds = folds.sort_values(["test_month", "ticker"]).reset_index(drop=True)
        folds.to_csv(out_dir / "fold_configs.csv", index=False)

    months = [m for m in month_list(args.start_month, args.end_month) if m not in excluded_months]
    tickers = [t.upper() for t in args.tickers]
    overall = metrics(selected, months)
    per_ticker = {
        ticker: metrics(selected[selected["ticker"].eq(ticker)].copy(), months) if not selected.empty else empty_metrics()
        for ticker in tickers
    }
    summary = {
        "args": vars(args),
        "folds": folds.to_dict(orient="records") if not folds.empty else [],
        "overall": overall,
        "per_ticker": per_ticker,
    }
    summary["requirements"] = requirement_summary(overall, per_ticker, tickers, args)
    summary["integrity"] = integrity_summary(folds, selected, months, tickers)
    (out_dir / "metrics.json").write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(out_dir, summary)
    print((out_dir / "SUMMARY.md").read_text(encoding="utf-8"), flush=True)
    return 0 if summary["requirements"]["all_tickers_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
