from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


def parse_named_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Expected NAME=PATH, got {value!r}")
    name, raw_path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"Empty source name in {value!r}")
    return name, Path(raw_path.strip())


def load_trade_file(value: str) -> pd.DataFrame:
    name, path = parse_named_path(value)
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, dtype={"ticker": str, "date": str, "month": str, "time": str, "test_month": str})
    required = {"ticker", "date", "month", "time", "action", "realized_return"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")
    df = df.copy()
    df["source_stream"] = name
    df["source_file"] = str(path)
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df["month"] = df["month"].astype(str)
    if "test_month" not in df.columns:
        df["test_month"] = df["month"]
    df["test_month"] = df["test_month"].astype(str)
    df["realized_return"] = pd.to_numeric(df["realized_return"], errors="coerce").fillna(0.0)
    if "candidate_id" not in df.columns:
        df["candidate_id"] = np.arange(len(df), dtype=np.int64)
    return df


def load_fold_file(value: str) -> pd.DataFrame:
    name, path = parse_named_path(value)
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, dtype=str)
    df = df.copy()
    df["source_stream"] = name
    df["source_file"] = str(path)
    if "ticker" in df.columns:
        df["ticker"] = df["ticker"].astype(str).str.upper()
    if "month" in df.columns and "test_month" not in df.columns:
        df["test_month"] = df["month"].astype(str)
    if "test_month" in df.columns:
        df["test_month"] = df["test_month"].astype(str)
    return df


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


def audit_folds(folds: pd.DataFrame, eval_months: list[str]) -> dict:
    if folds.empty:
        return {"passed": False, "folds_checked": 0, "issues": ["no fold files supplied"]}
    issues: list[str] = []
    month_cols = [
        "train_months",
        "val_months",
        "select_months",
        "profile_train_months",
        "profile_inner_val_months",
        "inner_val_months",
        "core_months",
    ]
    checked = 0
    for idx, row in folds.iterrows():
        test_month = str(row.get("test_month", "")).strip()
        if not test_month:
            continue
        if test_month in eval_months:
            checked += 1
        for col in month_cols:
            if col not in folds.columns:
                continue
            non_prior = [month for month in parse_month_list(row.get(col)) if month >= test_month]
            if non_prior:
                source = str(row.get("source_stream", ""))
                issues.append(f"row {idx} {source} {test_month}: {col} has non-prior months {non_prior}")
        if len(issues) >= 25:
            break
    return {"passed": not issues and checked > 0, "folds_checked": int(checked), "issues": issues[:25]}


def write_daily_plot(output_dir: Path, trades: pd.DataFrame, risk_capital: float) -> None:
    if trades.empty:
        return
    work = trades.copy()
    work["dt"] = pd.to_datetime(work["date"].astype(str), format="%Y%m%d", errors="coerce")
    work = work[work["dt"].notna()].copy()
    work["pnl"] = pd.to_numeric(work["realized_return"], errors="coerce").fillna(0.0) * float(risk_capital)
    daily = work.groupby("dt")["pnl"].sum().sort_index()
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    daily = daily.reindex(idx).fillna(0.0)
    daily_df = pd.DataFrame({"date": idx.strftime("%Y%m%d"), "daily_pnl": daily.values, "cum_pnl": daily.cumsum().values})
    daily_df.to_csv(output_dir / "combined_daily_total.csv", index=False)

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(idx, daily.cumsum().values, color="#111827", linewidth=2.4, label="TOTAL")
    for ticker, part in work.groupby("ticker", sort=True):
        curve = part.groupby("dt")["pnl"].sum().sort_index().reindex(idx).fillna(0.0).cumsum()
        axes[0].plot(idx, curve.values, linewidth=1.5, label=str(ticker))
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Combined Event Option Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(idx, daily.values, color=np.where(daily.values >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "combined_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, payload: dict) -> None:
    overall = payload["overall"]
    by_ticker = payload["by_ticker"]
    monthly = payload["monthly"]
    lines = [
        "# Combined Event Option Trade Streams",
        "",
        "This artifact combines already generated causal OOS trade streams. It does not train or select any new trade.",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        f"- Risk capital: ${float(payload['risk_capital']):,.0f}",
        f"- Net PnL: ${float(payload['net_pnl']):,.0f}",
        "",
        "## By Ticker",
        "",
        "```json",
        json.dumps(by_ticker, indent=2, allow_nan=True),
        "```",
        "",
        "## Monthly PnL Return",
        "",
        "| Month | Ticker | Trades | WR | PF | PnL Return | PnL $ |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in monthly:
        lines.append(
            f"| {row['month']} | {row['ticker']} | {int(row['trades'])} | "
            f"{float(row['win_rate']):.1%} | {float(row['profit_factor']):.3f} | "
            f"{float(row['pnl_return']):.3f} | {float(row['pnl_dollars']):,.0f} |"
        )
    lines += [
        "",
        "## Integrity",
        "",
        "```json",
        json.dumps(payload["integrity"], indent=2, allow_nan=True),
        "```",
        "",
        "## Sources",
        "",
        "```json",
        json.dumps(payload["sources"], indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Combine event-option trade CSVs that use realized_return.")
    parser.add_argument("--trade-file", action="append", required=True, help="NAME=path/to/trades.csv")
    parser.add_argument("--fold-file", action="append", default=[], help="NAME=path/to/folds.csv")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    months = month_range(str(args.start_month), str(args.end_month))
    trades = pd.concat([load_trade_file(item) for item in args.trade_file], ignore_index=True)
    trades = trades[trades["month"].astype(str).isin(months)].copy()
    sort_cols = [col for col in ["date", "time", "ticker", "source_stream", "candidate_id"] if col in trades.columns]
    trades = trades.sort_values(sort_cols, kind="stable").reset_index(drop=True)
    trades.to_csv(output_dir / "combined_trades.csv", index=False)

    folds = pd.concat([load_fold_file(item) for item in args.fold_file], ignore_index=True) if args.fold_file else pd.DataFrame()
    if not folds.empty:
        folds.to_csv(output_dir / "combined_folds.csv", index=False)

    overall = metrics(trades, months)
    by_ticker = {ticker: metrics(part, months) for ticker, part in trades.groupby("ticker", sort=True)}
    monthly_rows: list[dict] = []
    for month in months:
        for ticker in sorted(trades["ticker"].unique()):
            part = trades[(trades["month"].astype(str) == month) & (trades["ticker"].astype(str) == ticker)].copy()
            row = metrics(part, [month])
            row["month"] = month
            row["ticker"] = ticker
            row["pnl_dollars"] = float(row["pnl_return"]) * float(args.risk_capital)
            monthly_rows.append(row)
        month_part = trades[trades["month"].astype(str) == month].copy()
        row = metrics(month_part, [month])
        row["month"] = month
        row["ticker"] = "TOTAL"
        row["pnl_dollars"] = float(row["pnl_return"]) * float(args.risk_capital)
        monthly_rows.append(row)

    payload = {
        "overall": overall,
        "by_ticker": by_ticker,
        "monthly": monthly_rows,
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "risk_capital": float(args.risk_capital),
        "integrity": audit_folds(folds, months),
        "sources": {
            "trade_file": args.trade_file,
            "fold_file": args.fold_file,
            "start_month": str(args.start_month),
            "end_month": str(args.end_month),
        },
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_daily_plot(output_dir, trades, float(args.risk_capital))
    write_summary(output_dir, payload)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
