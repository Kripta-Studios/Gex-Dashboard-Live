from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range


def max_drawdown(values: np.ndarray) -> tuple[float, int]:
    if values.size == 0:
        return 0.0, 0
    peak = np.maximum.accumulate(values)
    dd = values - peak
    min_dd = float(dd.min())
    max_duration = 0
    current = 0
    for item in dd:
        if item < 0.0:
            current += 1
            max_duration = max(max_duration, current)
        else:
            current = 0
    return min_dd, int(max_duration)


def max_negative_streak(values: np.ndarray) -> int:
    best = 0
    current = 0
    for value in values:
        if value < 0.0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return int(best)


def profit_factor(values: pd.Series) -> float:
    gains = float(values[values > 0.0].sum())
    losses = float(-values[values < 0.0].sum())
    if losses <= 0.0:
        return float("inf") if gains > 0.0 else 0.0
    return gains / losses


def top_share(values: pd.Series, top_n: int) -> float:
    total = float(values.sum())
    if total <= 0.0:
        return float("nan")
    return float(values.sort_values(ascending=False).head(top_n).sum() / total)


def linear_curve_r2(curve: np.ndarray) -> float:
    if curve.size < 2:
        return float("nan")
    x = np.arange(curve.size, dtype=float)
    y = curve.astype(float)
    y_mean = float(y.mean())
    ss_tot = float(((y - y_mean) ** 2).sum())
    if ss_tot <= 0.0:
        return float("nan")
    coef = np.polyfit(x, y, 1)
    pred = coef[0] * x + coef[1]
    ss_res = float(((y - pred) ** 2).sum())
    return 1.0 - ss_res / ss_tot


def health_flags(row: dict, args: argparse.Namespace) -> list[str]:
    flags: list[str] = []
    final_pnl = float(row.get("final_pnl", 0.0))
    if final_pnl <= 0.0:
        flags.append("final_pnl_non_positive")
    dd_ratio = abs(float(row.get("max_drawdown", 0.0))) / final_pnl if final_pnl > 0.0 else float("inf")
    if dd_ratio > float(args.max_drawdown_to_pnl):
        flags.append(f"drawdown_to_pnl>{args.max_drawdown_to_pnl:g}")
    top5 = float(row.get("top5_share", float("nan")))
    if np.isfinite(top5) and top5 > float(args.max_top5_share):
        flags.append(f"top5_share>{args.max_top5_share:g}")
    top1 = float(row.get("top1_share", float("nan")))
    if np.isfinite(top1) and top1 > float(args.max_top1_share):
        flags.append(f"top1_share>{args.max_top1_share:g}")
    if int(row.get("negative_months", 0)) > 0:
        flags.append("negative_months")
    max_month_share = float(row.get("max_month_pnl_share", float("nan")))
    if np.isfinite(max_month_share) and max_month_share > float(args.max_month_pnl_share):
        flags.append(f"max_month_pnl_share>{args.max_month_pnl_share:g}")
    if int(row.get("max_negative_day_streak", 0)) > int(args.max_negative_streak):
        flags.append(f"negative_day_streak>{args.max_negative_streak}")
    milestones = row.get("milestones", {})
    first_two = milestones.get("first_2_months", {})
    first_three = milestones.get("first_3_months", {})
    first_two_share = float(first_two.get("share_of_final_pnl", float("nan")))
    first_three_share = float(first_three.get("share_of_final_pnl", float("nan")))
    if np.isfinite(first_two_share) and first_two_share < float(args.min_first_two_month_share):
        flags.append(f"first_2_month_share<{args.min_first_two_month_share:g}")
    if np.isfinite(first_three_share) and first_three_share < float(args.min_first_three_month_share):
        flags.append(f"first_3_month_share<{args.min_first_three_month_share:g}")
    return flags


def build_daily(trades: pd.DataFrame, risk_capital: float, months: list[str]) -> pd.DataFrame:
    work = trades.copy()
    work["dt"] = pd.to_datetime(work["date"].astype(str), format="%Y%m%d", errors="coerce")
    work = work[work["dt"].notna() & work["month"].astype(str).isin(months)].copy()
    work["pnl"] = pd.to_numeric(work["realized_return"], errors="coerce").fillna(0.0) * float(risk_capital)
    if work.empty:
        return pd.DataFrame(columns=["dt", "ticker", "daily_pnl", "trade_count"])
    all_days = pd.date_range(work["dt"].min(), work["dt"].max(), freq="B")
    frames: list[pd.DataFrame] = []
    for ticker, part in work.groupby("ticker", sort=True):
        grouped = part.groupby("dt").agg(daily_pnl=("pnl", "sum"), trade_count=("pnl", "size")).sort_index()
        grouped = grouped.reindex(all_days).fillna({"daily_pnl": 0.0, "trade_count": 0})
        grouped["ticker"] = str(ticker)
        grouped = grouped.reset_index(names="dt")
        frames.append(grouped)
    return pd.concat(frames, ignore_index=True)


def summarize_ticker(daily: pd.DataFrame, trades: pd.DataFrame, ticker: str, months: list[str], risk_capital: float) -> dict:
    part_daily = daily[daily["ticker"].astype(str).eq(ticker)].sort_values("dt").copy()
    daily_pnl = pd.to_numeric(part_daily["daily_pnl"], errors="coerce").fillna(0.0)
    curve = daily_pnl.cumsum().to_numpy(dtype=float)
    dd, dd_duration = max_drawdown(curve)
    month_rows = []
    negative_months = 0
    monthly_pnls_dollars: list[float] = []
    for month in months:
        month_part = trades[(trades["ticker"].astype(str).eq(ticker)) & (trades["month"].astype(str).eq(month))].copy()
        returns = pd.to_numeric(month_part["realized_return"], errors="coerce").fillna(0.0)
        pnl = float(returns.sum())
        monthly_pnls_dollars.append(float(pnl) * float(risk_capital))
        if pnl <= 0.0:
            negative_months += 1
        month_rows.append(
            {
                "month": month,
                "trades": int(len(month_part)),
                "win_rate": float((returns > 0.0).mean()) if len(returns) else 0.0,
                "profit_factor": profit_factor(returns),
                "pnl_return": pnl,
            }
        )
    final_pnl = float(sum(monthly_pnls_dollars))
    positive_month_pnls = [pnl for pnl in monthly_pnls_dollars if pnl > 0.0]
    max_month_pnl = max(positive_month_pnls) if positive_month_pnls else 0.0
    max_month_pnl_share = float(max_month_pnl / final_pnl) if final_pnl > 0.0 else float("nan")
    max_month_pnl_idx = int(np.argmax(monthly_pnls_dollars)) if monthly_pnls_dollars else -1
    max_month_pnl_month = months[max_month_pnl_idx] if max_month_pnl_idx >= 0 else ""
    positive_days = int((daily_pnl > 0.0).sum())
    active_days = int((part_daily["trade_count"] > 0).sum())
    milestones: dict[str, dict] = {}
    running = 0.0
    for idx, pnl in enumerate(monthly_pnls_dollars, start=1):
        running += float(pnl)
        if idx in (1, 2, 3, 4) and idx <= len(months):
            milestones[f"first_{idx}_months"] = {
                "through_month": months[idx - 1],
                "pnl_dollars": float(running),
                "share_of_final_pnl": float(running / final_pnl) if final_pnl > 0.0 else float("nan"),
            }
    return {
        "ticker": ticker,
        "final_pnl": final_pnl,
        "daily_profit_factor": profit_factor(daily_pnl),
        "daily_win_rate_all_business_days": float((daily_pnl > 0.0).mean()) if len(daily_pnl) else 0.0,
        "daily_win_rate_active_days": float((daily_pnl[part_daily["trade_count"] > 0] > 0.0).mean()) if active_days else 0.0,
        "active_days": active_days,
        "positive_days": positive_days,
        "max_drawdown": dd,
        "max_drawdown_to_pnl": float(abs(dd) / daily_pnl.sum()) if daily_pnl.sum() > 0.0 else float("inf"),
        "max_drawdown_business_days": dd_duration,
        "max_negative_day_streak": max_negative_streak(daily_pnl.to_numpy(dtype=float)),
        "top1_share": top_share(daily_pnl, 1),
        "top3_share": top_share(daily_pnl, 3),
        "top5_share": top_share(daily_pnl, 5),
        "max_month_pnl": float(max_month_pnl),
        "max_month_pnl_month": max_month_pnl_month,
        "max_month_pnl_share": max_month_pnl_share,
        "curve_linear_r2": linear_curve_r2(curve),
        "negative_months": int(negative_months),
        "milestones": milestones,
        "monthly": month_rows,
    }


def write_plots(output_dir: Path, daily: pd.DataFrame, risk_capital: float) -> None:
    if daily.empty:
        return
    plot_dir = output_dir / "curve_health"
    plot_dir.mkdir(parents=True, exist_ok=True)
    tickers = sorted(daily["ticker"].astype(str).unique())
    fig, axes = plt.subplots(len(tickers), 1, figsize=(14, max(4, 3.2 * len(tickers))), sharex=True)
    if len(tickers) == 1:
        axes = [axes]
    for ax, ticker in zip(axes, tickers):
        part = daily[daily["ticker"].astype(str).eq(ticker)].sort_values("dt")
        curve = part["daily_pnl"].astype(float).cumsum()
        ax.plot(part["dt"], curve, linewidth=2.2, label=f"{ticker} cumulative")
        ax.axhline(0.0, color="#6b7280", linewidth=0.8)
        ax.set_title(f"{ticker} net PnL, risk_capital={risk_capital:g}")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(plot_dir / "ticker_cumulative_net_pnl.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(len(tickers), 1, figsize=(14, max(4, 3.2 * len(tickers))), sharex=True)
    if len(tickers) == 1:
        axes = [axes]
    for ax, ticker in zip(axes, tickers):
        part = daily[daily["ticker"].astype(str).eq(ticker)].sort_values("dt")
        values = part["daily_pnl"].astype(float).to_numpy()
        colors = np.where(values >= 0.0, "#16a34a", "#dc2626")
        ax.bar(part["dt"], values, color=colors, width=0.8)
        ax.axhline(0.0, color="#6b7280", linewidth=0.8)
        ax.set_title(f"{ticker} daily PnL")
        ax.grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(plot_dir / "ticker_daily_pnl.png", dpi=160)
    plt.close(fig)


def write_report(output_dir: Path, payload: dict) -> None:
    lines = [
        "# Event Option Curve Health",
        "",
        "This report audits daily net-PnL curve quality. It does not train or select trades.",
        "",
        "## Gates",
        "",
        "```json",
        json.dumps(payload["gates"], indent=2, allow_nan=True),
        "```",
        "",
        "## Summary",
        "",
        "| Ticker | Healthy | PnL $ | Daily PF | Active-Day WR | Max DD $ | DD/PnL | Top1 Share | Top5 Share | Neg Months | Max Neg Streak | R2 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["tickers"].values():
        flags = row["health_flags"]
        lines.append(
            f"| {row['ticker']} | {not flags} | {row['final_pnl']:,.0f} | "
            f"{row['daily_profit_factor']:.3f} | {row['daily_win_rate_active_days']:.1%} | "
            f"{row['max_drawdown']:,.0f} | {row['max_drawdown_to_pnl']:.1%} | "
            f"{row['top1_share']:.1%} | {row['top5_share']:.1%} | "
            f"{row['negative_months']} | {row['max_negative_day_streak']} | {row['curve_linear_r2']:.3f} |"
        )
    lines += ["", "## Flags", ""]
    for ticker, row in payload["tickers"].items():
        flags = row["health_flags"]
        lines.append(f"- {ticker}: {', '.join(flags) if flags else 'none'}")
    lines += [
        "",
        "## Monthly Concentration",
        "",
        "| Ticker | Largest Month | Largest Month PnL | Share Of Final PnL |",
        "| --- | --- | ---: | ---: |",
    ]
    for ticker, row in payload["tickers"].items():
        lines.append(
            f"| {ticker} | {row['max_month_pnl_month']} | "
            f"${row['max_month_pnl']:,.0f} | {row['max_month_pnl_share']:.1%} |"
        )
    lines += [
        "",
        "## Prefix Health",
        "",
        "| Ticker | First 2 Months | First 3 Months | First 4 Months |",
        "| --- | ---: | ---: | ---: |",
    ]
    for ticker, row in payload["tickers"].items():
        milestones = row.get("milestones", {})
        def fmt(key: str) -> str:
            item = milestones.get(key, {})
            pnl = float(item.get("pnl_dollars", float("nan")))
            share = float(item.get("share_of_final_pnl", float("nan")))
            if not np.isfinite(pnl) or not np.isfinite(share):
                return "n/a"
            return f"${pnl:,.0f} / {share:.1%}"
        lines.append(f"| {ticker} | {fmt('first_2_months')} | {fmt('first_3_months')} | {fmt('first_4_months')} |")
    lines += [
        "",
        "## Monthly",
        "",
        "| Ticker | Month | Trades | WR | PF | PnL Return |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for ticker, row in payload["tickers"].items():
        for month in row["monthly"]:
            lines.append(
                f"| {ticker} | {month['month']} | {month['trades']} | "
                f"{month['win_rate']:.1%} | {month['profit_factor']:.3f} | {month['pnl_return']:.3f} |"
            )
    lines += [
        "",
        "## Artifacts",
        "",
        "- `curve_health/ticker_cumulative_net_pnl.png`",
        "- `curve_health/ticker_daily_pnl.png`",
        "- `curve_health/ticker_daily_curve.csv`",
        "- `curve_health/curve_health.json`",
    ]
    (output_dir / "CURVE_HEALTH.md").write_text("\n".join(lines), encoding="utf-8")


def resolve_trade_file(result_dir: Path) -> Path:
    for name in (
        "combined_trades.csv",
        "stream_selector_trades.csv",
        "trade_union_topk_regressor_trades.csv",
        "trade_union_backfill_selector_trades.csv",
        "trade_union_config_selector_trades.csv",
        "nested_volume_backfill_trades.csv",
        "intraday_circuit_trades.csv",
        "event_option_gate_trades.csv",
        "volume_backfill_trades.csv",
        "selected_trades.csv",
    ):
        candidate = result_dir / name
        if candidate.exists():
            return candidate
    return result_dir / "combined_trades.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze daily net-PnL health for combined event-option results.")
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--exclude-months", nargs="*", default=[], help="Months to remove from the curve-health window, e.g. raw-partial months.")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--max-top1-share", type=float, default=0.45)
    parser.add_argument("--max-top5-share", type=float, default=0.80)
    parser.add_argument("--max-drawdown-to-pnl", type=float, default=0.45)
    parser.add_argument("--max-month-pnl-share", type=float, default=0.65)
    parser.add_argument("--max-negative-streak", type=int, default=4)
    parser.add_argument("--min-first-two-month-share", type=float, default=0.10)
    parser.add_argument("--min-first-three-month-share", type=float, default=0.20)
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    trades_path = resolve_trade_file(result_dir)
    if not trades_path.exists():
        raise FileNotFoundError(trades_path)
    excluded = {str(month) for month in args.exclude_months if str(month).strip()}
    months = [month for month in month_range(str(args.start_month), str(args.end_month)) if month not in excluded]
    trades = pd.read_csv(trades_path, dtype={"ticker": str, "date": str, "month": str, "time": str})
    trades["ticker"] = trades["ticker"].astype(str).str.upper()
    if "month" not in trades.columns and "test_month" in trades.columns:
        trades["month"] = trades["test_month"].astype(str)
    trades["month"] = trades["month"].astype(str)
    trades["realized_return"] = pd.to_numeric(trades["realized_return"], errors="coerce").fillna(0.0)
    trades = trades[trades["month"].isin(months)].copy()
    daily = build_daily(trades, float(args.risk_capital), months)
    output_dir = result_dir / "curve_health"
    output_dir.mkdir(parents=True, exist_ok=True)
    daily_out = daily.copy()
    if not daily_out.empty:
        daily_out["date"] = daily_out["dt"].dt.strftime("%Y%m%d")
        daily_out = daily_out.drop(columns=["dt"])
    daily_out.to_csv(output_dir / "ticker_daily_curve.csv", index=False)

    tickers: dict[str, dict] = {}
    for ticker in sorted(trades["ticker"].unique()):
        row = summarize_ticker(daily, trades, ticker, months, float(args.risk_capital))
        row["health_flags"] = health_flags(row, args)
        tickers[ticker] = row

    payload = {
        "passed": bool(all(not row["health_flags"] for row in tickers.values())),
        "result_dir": str(result_dir),
        "gates": {
            "months": months,
            "excluded_months": sorted(excluded),
            "risk_capital": float(args.risk_capital),
            "max_top1_share": float(args.max_top1_share),
            "max_top5_share": float(args.max_top5_share),
            "max_drawdown_to_pnl": float(args.max_drawdown_to_pnl),
            "max_month_pnl_share": float(args.max_month_pnl_share),
            "max_negative_streak": int(args.max_negative_streak),
            "min_first_two_month_share": float(args.min_first_two_month_share),
            "min_first_three_month_share": float(args.min_first_three_month_share),
        },
        "tickers": tickers,
    }
    write_plots(result_dir, daily, float(args.risk_capital))
    (output_dir / "curve_health.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_report(result_dir, payload)
    print((result_dir / "CURVE_HEALTH.md").read_text(encoding="utf-8"))
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
