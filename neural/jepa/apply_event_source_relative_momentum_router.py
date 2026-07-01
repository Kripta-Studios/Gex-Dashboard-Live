from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


def load_trades(path: Path, name: str, ticker: str, start_month: str, end_month: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str})
    if "test_month" not in df.columns:
        df["test_month"] = df["month"].astype(str)
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df["month"] = df["month"].astype(str)
    df["test_month"] = df["test_month"].astype(str)
    df["realized_return"] = pd.to_numeric(df["realized_return"], errors="coerce").fillna(0.0)
    df = df[
        df["ticker"].eq(str(ticker).upper())
        & df["test_month"].between(str(start_month), str(end_month))
    ].copy()
    df["relative_router_stream"] = str(name)
    df["relative_router_source_file"] = str(path)
    return df


def load_relative_scores(path: Path, source_a: str, source_b: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"test_month": str, "month": str, "daily_source": str})
    if "test_month" not in df.columns:
        df["test_month"] = df["month"].astype(str)
    required = {"test_month", "daily_source", "daily_target_return"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{path} missing columns {missing}")
    df["test_month"] = df["test_month"].astype(str)
    df["daily_source"] = df["daily_source"].astype(str)
    df["daily_target_return"] = pd.to_numeric(df["daily_target_return"], errors="coerce").fillna(0.0)
    monthly = df.groupby(["test_month", "daily_source"])["daily_target_return"].sum().unstack(fill_value=0.0)
    for source in (source_a, source_b):
        if source not in monthly.columns:
            monthly[source] = 0.0
    monthly = monthly.sort_index()
    return monthly[[source_a, source_b]].copy()


def write_plot(output_dir: Path, trades: pd.DataFrame, risk_capital: float) -> None:
    if trades.empty:
        return
    work = trades.copy()
    work["dt"] = pd.to_datetime(work["date"].astype(str), format="%Y%m%d", errors="coerce")
    work = work[work["dt"].notna()].copy()
    work["pnl"] = pd.to_numeric(work["realized_return"], errors="coerce").fillna(0.0) * float(risk_capital)
    daily = work.groupby("dt")["pnl"].sum().sort_index()
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    daily = daily.reindex(idx).fillna(0.0)
    pd.DataFrame({"date": idx.strftime("%Y%m%d"), "daily_pnl": daily.values, "cum_pnl": daily.cumsum().values}).to_csv(
        output_dir / "relative_momentum_daily_total.csv", index=False
    )
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(idx, daily.cumsum().values, color="#111827", linewidth=2.4)
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Relative Momentum Source Router Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(idx, daily.values, color=np.where(daily.values >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "relative_momentum_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, monthly_scores: pd.DataFrame, args: argparse.Namespace) -> None:
    months = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, months)
    by_ticker = {ticker: metrics(part, months) for ticker, part in trades.groupby("ticker", sort=True)} if not trades.empty else {}
    monthly_rows = []
    for month in months:
        part = trades[trades["test_month"].astype(str).eq(month)].copy() if not trades.empty else trades
        row = metrics(part, [month])
        row["month"] = month
        row["pnl_dollars"] = float(row["pnl_return"]) * float(args.risk_capital)
        monthly_rows.append(row)
    payload = {
        "overall": overall,
        "by_ticker": by_ticker,
        "monthly": monthly_rows,
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "risk_capital": float(args.risk_capital),
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Source Relative Momentum Router",
        "",
        "This result switches between two precomputed causal streams only when source A outperformed source B over the prior lookback months. It does not use the evaluated month for selection.",
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
        "## Monthly Source Scores",
        "",
        "```csv",
        monthly_scores.reset_index().to_csv(index=False),
        "```",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(vars(args), indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal source router using prior relative source momentum.")
    parser.add_argument("--primary-trades", required=True, help="Default stream used unless relative momentum switches.")
    parser.add_argument("--alternate-trades", required=True, help="Alternate stream selected when source A persistently beats source B.")
    parser.add_argument("--score-candidates", required=True, help="Long daily candidate file with daily_source and daily_target_return.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ticker", default="SPY")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--lookback-months", type=int, default=2)
    parser.add_argument("--source-a", default="topk")
    parser.add_argument("--source-b", default="nested")
    parser.add_argument("--primary-name", default="dailyrouter")
    parser.add_argument("--alternate-name", default="topk")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    months = month_range(str(args.start_month), str(args.end_month))
    primary = load_trades(Path(args.primary_trades), str(args.primary_name), str(args.ticker), str(args.start_month), str(args.end_month))
    alternate = load_trades(Path(args.alternate_trades), str(args.alternate_name), str(args.ticker), str(args.start_month), str(args.end_month))
    monthly_scores = load_relative_scores(Path(args.score_candidates), str(args.source_a), str(args.source_b))

    parts: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    for month in months:
        previous = [m for m in monthly_scores.index.astype(str).tolist() if m < month]
        select_months = previous[-int(args.lookback_months):]
        use_alternate = False
        comparisons: list[bool] = []
        if len(select_months) == int(args.lookback_months):
            comparisons = [
                float(monthly_scores.loc[m, str(args.source_a)]) > float(monthly_scores.loc[m, str(args.source_b)])
                for m in select_months
            ]
            use_alternate = all(comparisons)
        selected_name = str(args.alternate_name) if use_alternate else str(args.primary_name)
        source = alternate if use_alternate else primary
        part = source[source["test_month"].astype(str).eq(month)].copy()
        if not part.empty:
            part["relative_router_selected_source"] = selected_name
            part["relative_router_select_months"] = ",".join(select_months)
            part["relative_router_source_a"] = str(args.source_a)
            part["relative_router_source_b"] = str(args.source_b)
            parts.append(part)
        test_row = metrics(part, [month])
        fold = {
            "ticker": str(args.ticker).upper(),
            "test_month": month,
            "mode": "SELECTED" if len(select_months) == int(args.lookback_months) else "DEFAULT_PRIMARY",
            "selected_source": selected_name,
            "source_path": str(args.alternate_trades if use_alternate else args.primary_trades),
            "select_months": ",".join(select_months),
            "lookback_months": int(args.lookback_months),
            "source_a": str(args.source_a),
            "source_b": str(args.source_b),
            "source_a_gt_source_b": json.dumps(comparisons),
        }
        for source_name in (str(args.source_a), str(args.source_b)):
            for selected_month in select_months:
                fold[f"{selected_month}_{source_name}_return"] = float(monthly_scores.loc[selected_month, source_name])
        fold.update({f"test_{key}": value for key, value in test_row.items()})
        fold_rows.append(fold)

    trades = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    if not trades.empty:
        trades = trades.sort_values(["date", "time", "ticker", "relative_router_selected_source"], kind="stable").reset_index(drop=True)
    trades.to_csv(output_dir / "relative_momentum_trades.csv", index=False)
    folds.to_csv(output_dir / "relative_momentum_folds.csv", index=False)
    monthly_scores.to_csv(output_dir / "relative_momentum_source_scores.csv")
    write_plot(output_dir, trades, float(args.risk_capital))
    write_summary(output_dir, trades, folds, monthly_scores, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
