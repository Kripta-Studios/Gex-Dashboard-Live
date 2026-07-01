from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


def parse_month_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, float) and math.isnan(value):
        return []
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    text = text.replace('"', "")
    return [part.strip() for part in text.split(",") if part.strip()]


def load_trades(result_dir: Path) -> pd.DataFrame:
    trade_names = [
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
    ]
    path = next((result_dir / name for name in trade_names if (result_dir / name).exists()), None)
    if path is None:
        raise FileNotFoundError(result_dir / "combined_trades.csv")
    df = pd.read_csv(path, dtype={"ticker": str, "date": str, "month": str, "time": str, "test_month": str})
    df["ticker"] = df["ticker"].astype(str).str.upper()
    if "month" not in df.columns and "test_month" in df.columns:
        df["month"] = df["test_month"].astype(str)
    if "test_month" not in df.columns and "month" in df.columns:
        df["test_month"] = df["month"].astype(str)
    df["month"] = df["month"].astype(str)
    df["date"] = df["date"].astype(str)
    df["realized_return"] = pd.to_numeric(df["realized_return"], errors="coerce").fillna(0.0)
    return df


WEAK_FOLD_MODES = {
    "NO_HISTORY",
    "INSUFFICIENT_ROWS",
    "INSUFFICIENT_META_ROWS",
    "SINGLE_CLASS_TRAIN",
    "EMPTY",
}


def audit_folds(result_dir: Path, months: list[str], disallow_weak_modes: bool = False) -> dict:
    fold_names = [
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
    ]
    path = next((result_dir / name for name in fold_names if (result_dir / name).exists()), None)
    if path is None:
        return {"passed": False, "folds_checked": 0, "issues": ["fold file missing"]}
    folds = pd.read_csv(path, dtype=str)
    month_cols = [
        "train_months",
        "train_month_max",
        "first_val_month",
        "val_months",
        "val_month_max",
        "select_months",
        "profile_train_months",
        "profile_inner_val_months",
        "inner_val_months",
        "core_months",
    ]
    issues: list[str] = []
    checked = 0
    for idx, row in folds.iterrows():
        test_month = str(row.get("test_month", row.get("month", row.get("eval_month", "")))).strip()
        if not test_month:
            continue
        if test_month in months:
            checked += 1
            if disallow_weak_modes:
                for mode_col in ("mode", "meta_mode", "topk_mode"):
                    if mode_col not in folds.columns:
                        continue
                    mode = str(row.get(mode_col, "")).strip().upper()
                    if mode in WEAK_FOLD_MODES:
                        source = str(row.get("source_stream", row.get("source", "")))
                        issues.append(f"row {idx} {source} {test_month}: weak fold mode {mode_col}={mode}")
        for col in month_cols:
            if col not in folds.columns:
                continue
            non_prior = [month for month in parse_month_list(row.get(col)) if month >= test_month]
            if non_prior:
                source = str(row.get("source_stream", ""))
                issues.append(f"row {idx} {source} {test_month}: {col} has non-prior months {non_prior}")
        train_max = parse_month_list(row.get("train_month_max")) if "train_month_max" in folds.columns else []
        first_val = parse_month_list(row.get("first_val_month")) if "first_val_month" in folds.columns else []
        if train_max and first_val and max(train_max) >= min(first_val):
            source = str(row.get("source_stream", ""))
            issues.append(f"row {idx} {source} {test_month}: train_month_max {max(train_max)} >= first_val_month {min(first_val)}")
        if len(issues) >= 50:
            break
    return {"passed": bool(checked > 0 and not issues), "folds_checked": int(checked), "issues": issues}


def audit_backfill(trades: pd.DataFrame) -> dict:
    issues: list[str] = []
    checked = 0
    if "backfill_mode" not in trades.columns:
        return {"passed": True, "rows_checked": 0, "issues": []}
    required_cols = {"backfill_count_before", "backfill_required_count", "backfill_mode"}
    missing = sorted(required_cols.difference(trades.columns))
    if missing:
        return {"passed": False, "rows_checked": 0, "issues": [f"missing backfill columns {missing}"]}
    bf = trades[trades["backfill_mode"].astype(str).eq("fallback_volume_pace")].copy()
    for idx, row in bf.iterrows():
        checked += 1
        count_before = pd.to_numeric(pd.Series([row.get("backfill_count_before")]), errors="coerce").iloc[0]
        required = pd.to_numeric(pd.Series([row.get("backfill_required_count")]), errors="coerce").iloc[0]
        if not np.isfinite(count_before) or not np.isfinite(required):
            issues.append(f"row {idx}: invalid backfill count/required")
        elif float(count_before) >= float(required):
            issues.append(f"row {idx}: fallback selected despite count_before {count_before} >= required {required}")
        if len(issues) >= 50:
            break
    return {"passed": not issues, "rows_checked": int(checked), "issues": issues}


def ticker_checks(trades: pd.DataFrame, months: list[str], tickers: list[str], args: argparse.Namespace) -> dict:
    out: dict[str, dict] = {}
    for ticker in tickers:
        part = trades[trades["ticker"].astype(str).str.upper().eq(ticker)].copy()
        m = metrics(part, months)
        month_rows: dict[str, dict] = {}
        for month in months:
            mm = metrics(part[part["month"].astype(str).eq(month)].copy(), [month])
            month_rows[month] = mm
        min_month = int(m.get("min_month_trades", 0))
        if bool(args.strict_month_trades):
            volume_ok = min_month > int(args.min_month_trades)
        else:
            volume_ok = min_month >= int(args.min_month_trades)
        wr = float(m.get("win_rate", float("nan")))
        pf = float(m.get("profit_factor", float("nan")))
        pnl = float(m.get("pnl_return", 0.0))
        call_rate = float(m.get("call_rate", float("nan")))
        monthly_positive_ok = all(float(row.get("pnl_return", 0.0)) > 0.0 for row in month_rows.values())
        checks = {
            "win_rate_ok": bool(np.isfinite(wr) and wr > float(args.min_win_rate)),
            "profit_factor_ok": bool(np.isfinite(pf) and pf > float(args.min_profit_factor)),
            "volume_ok": bool(volume_ok),
            "pnl_ok": bool(pnl > 0.0),
            "monthly_positive_ok": bool(monthly_positive_ok or not args.require_positive_months),
            "call_rate_ok": bool(
                np.isfinite(call_rate)
                and call_rate >= float(args.min_call_rate)
                and call_rate <= float(args.max_call_rate)
            ),
        }
        checks["passed"] = bool(all(checks.values()))
        out[ticker] = {"metrics": m, "monthly": month_rows, "checks": checks}
    return out


def write_report(path: Path, payload: dict) -> None:
    lines = [
        "# Event Option Result Verification",
        "",
        f"- Passed: {payload['passed']}",
        f"- Result dir: `{payload['result_dir']}`",
        "",
        "## Gates",
        "",
        "```json",
        json.dumps(payload["gates"], indent=2, allow_nan=True),
        "```",
        "",
        "## Tickers",
        "",
        "| Ticker | Passed | Trades | WR | PF | Min Month Trades | PnL Return | Call Rate | Positive Months |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for ticker, item in payload["tickers"].items():
        m = item["metrics"]
        positive_months = sum(1 for row in item["monthly"].values() if float(row.get("pnl_return", 0.0)) > 0.0)
        lines.append(
            f"| {ticker} | {item['checks']['passed']} | {int(m.get('trades', 0))} | "
            f"{float(m.get('win_rate', float('nan'))):.2%} | {float(m.get('profit_factor', float('nan'))):.3f} | "
            f"{int(m.get('min_month_trades', 0))} | {float(m.get('pnl_return', 0.0)):.3f} | "
            f"{float(m.get('call_rate', float('nan'))):.2%} | {positive_months}/{len(item['monthly'])} |"
        )
    lines += [
        "",
        "## Integrity",
        "",
        "```json",
        json.dumps(payload["integrity"], indent=2, allow_nan=True),
        "```",
        "",
        "## Backfill Audit",
        "",
        "```json",
        json.dumps(payload["backfill"], indent=2, allow_nan=True),
        "```",
    ]
    if payload["issues"]:
        lines += [
            "",
            "## Issues",
            "",
            *[f"- {issue}" for issue in payload["issues"]],
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an event-option combined result against causal and profitability gates.")
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--exclude-months", nargs="*", default=[], help="Months to remove from the evaluated window, e.g. raw partial months.")
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--strict-month-trades", action="store_true")
    parser.add_argument("--require-positive-months", action="store_true")
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--disallow-weak-fold-modes", action="store_true")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    parser.add_argument(
        "--report-suffix",
        default="",
        help="Write verification_<suffix>.json and VERIFICATION_<suffix>.md instead of default files.",
    )
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    excluded_months = {str(month) for month in args.exclude_months}
    months = [month for month in month_range(str(args.start_month), str(args.end_month)) if month not in excluded_months]
    tickers = [str(t).upper() for t in args.tickers]
    trades = load_trades(result_dir)
    trades = trades[trades["month"].astype(str).isin(months)].copy()
    by_ticker = ticker_checks(trades, months, tickers, args)
    integrity = audit_folds(result_dir, months, bool(args.disallow_weak_fold_modes))
    backfill = audit_backfill(trades)
    issues: list[str] = []
    for ticker, item in by_ticker.items():
        if not item["checks"]["passed"]:
            failed = [key for key, ok in item["checks"].items() if key != "passed" and not ok]
            issues.append(f"{ticker} failed checks: {failed}")
    if not integrity["passed"]:
        issues.append("fold integrity failed")
    if not backfill["passed"]:
        issues.append("backfill audit failed")
    payload = {
        "passed": bool(not issues),
        "result_dir": str(result_dir),
        "gates": {
            "tickers": tickers,
            "months": months,
            "min_win_rate": float(args.min_win_rate),
            "min_profit_factor": float(args.min_profit_factor),
            "min_month_trades": int(args.min_month_trades),
            "strict_month_trades": bool(args.strict_month_trades),
            "require_positive_months": bool(args.require_positive_months),
            "min_call_rate": float(args.min_call_rate),
            "max_call_rate": float(args.max_call_rate),
            "disallow_weak_fold_modes": bool(args.disallow_weak_fold_modes),
            "excluded_months": sorted(excluded_months),
        },
        "tickers": by_ticker,
        "integrity": integrity,
        "backfill": backfill,
        "issues": issues,
    }
    suffix = str(args.report_suffix).strip()
    if suffix:
        safe_suffix = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in suffix)
        default_json = result_dir / f"verification_{safe_suffix}.json"
        default_md = result_dir / f"VERIFICATION_{safe_suffix}.md"
    else:
        default_json = result_dir / "verification.json"
        default_md = result_dir / "VERIFICATION.md"
    json_path = Path(args.output_json) if str(args.output_json).strip() else default_json
    md_path = Path(args.output_md) if str(args.output_md).strip() else default_md
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_report(md_path, payload)
    print(md_path.read_text(encoding="utf-8"))
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
