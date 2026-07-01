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


def derive_minute(df: pd.DataFrame) -> pd.Series:
    out = pd.Series(np.nan, index=df.index, dtype=float)
    for col in ("minute", "minute_x", "minute_y", "entry_minute"):
        if col in df.columns:
            cand = pd.to_numeric(df[col], errors="coerce")
            out = out.where(out.notna(), cand)
    missing = out.isna()
    if missing.any() and "time" in df.columns:
        parsed = pd.to_datetime(df.loc[missing, "time"].astype(str), format="%H:%M", errors="coerce")
        out.loc[missing] = parsed.dt.hour * 60 + parsed.dt.minute
    return out.fillna(0).astype(int)


def load_trades(path: Path, source_name: str) -> pd.DataFrame:
    if path.is_dir():
        path = path / "event_option_gate_trades.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str})
    required = {"ticker", "date", "month", "time", "action", "realized_return"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{path} missing columns {missing}")
    df = df.copy()
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df["date"] = df["date"].astype(str)
    df["month"] = df["month"].astype(str)
    if "test_month" not in df.columns:
        df["test_month"] = df["month"]
    df["test_month"] = df["test_month"].astype(str)
    df["time"] = df["time"].astype(str)
    df["action"] = df["action"].astype(str).str.upper()
    df["realized_return"] = pd.to_numeric(df["realized_return"], errors="coerce").fillna(0.0)
    df["entry_minute"] = derive_minute(df)
    df["source_stream"] = source_name
    df["source_file"] = str(path)
    df["_source_order"] = np.arange(len(df), dtype=np.int64)
    if "score" in df.columns:
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
    else:
        df["score"] = 0.0
    return df


def business_day_position(month: str, date: str) -> tuple[int, int]:
    start = pd.Timestamp(year=int(month[:4]), month=int(month[4:6]), day=1)
    end = start + pd.offsets.MonthEnd(0)
    days = pd.bdate_range(start, end)
    current = pd.to_datetime(date, format="%Y%m%d", errors="coerce")
    if pd.isna(current):
        return 1, max(1, len(days))
    elapsed = int((days <= current).sum())
    return max(1, elapsed), max(1, len(days))


def required_count_by_date(month: str, date: str, target: int) -> int:
    elapsed, total = business_day_position(month, date)
    return int(math.ceil(float(target) * float(elapsed) / float(total)))


def target_count_for_month(month: str, dates: pd.Series, args: argparse.Namespace) -> int:
    base_target = int(args.min_month_trades)
    if not bool(getattr(args, "auto_partial_month_target", False)):
        return base_target
    observed_floor = int(getattr(args, "partial_month_observed_floor", 0) or 0)
    if observed_floor <= 0:
        return base_target
    valid_dates = dates.astype(str).replace("nan", np.nan).dropna()
    if valid_dates.empty:
        return base_target
    last_date = str(valid_dates.max())
    elapsed, total = business_day_position(str(month), last_date)
    if elapsed >= total:
        return base_target
    partial_target = int(math.ceil(float(observed_floor) * float(total) / float(max(1, elapsed))))
    return max(base_target, partial_target)


def is_partial_month(month: str, dates: pd.Series) -> bool:
    valid_dates = dates.astype(str).replace("nan", np.nan).dropna()
    if valid_dates.empty:
        return False
    last_date = str(valid_dates.max())
    elapsed, total = business_day_position(str(month), last_date)
    return elapsed < total


def selected_months(args: argparse.Namespace) -> list[str]:
    excluded = {str(month) for month in getattr(args, "exclude_months", []) if str(month).strip()}
    return [month for month in month_range(str(args.start_month), str(args.end_month)) if month not in excluded]


def apply_backfill(primary: pd.DataFrame, fallback: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    months = selected_months(args)
    frames: list[pd.DataFrame] = []
    primary = primary[primary["month"].astype(str).isin(months)].copy()
    fallback = fallback[fallback["month"].astype(str).isin(months)].copy()
    tickers = sorted(set(primary["ticker"].unique()) | set(fallback["ticker"].unique()))
    cooldown = int(args.cooldown_minutes)
    max_day = int(args.max_day)

    for ticker in tickers:
        p_ticker = primary[primary["ticker"].eq(ticker)].copy()
        f_ticker = fallback[fallback["ticker"].eq(ticker)].copy()
        for month in months:
            p_month = p_ticker[p_ticker["month"].astype(str).eq(month)].copy()
            f_month = f_ticker[f_ticker["month"].astype(str).eq(month)].copy()
            if p_month.empty and f_month.empty:
                continue

            combined = pd.concat([p_month, f_month], ignore_index=True, sort=False)
            target = target_count_for_month(month, combined["date"], args)
            partial_month = is_partial_month(month, combined["date"])
            combined["_priority"] = np.where(combined["source_stream"].astype(str).eq(str(args.primary_name)), 0, 1)
            combined = combined.sort_values(
                ["date", "entry_minute", "_priority", "score", "_source_order"],
                ascending=[True, True, True, False, True],
                kind="stable",
            )

            selected: list[pd.Series] = []
            selected_keys: set[tuple[str, str, str, str]] = set()
            selected_count = 0
            day_counts: dict[str, int] = {}
            next_allowed_by_day: dict[str, int] = {}
            for _, row in combined.iterrows():
                date = str(row["date"])
                time = str(row["time"])
                action = str(row["action"])
                expiry_mode = str(row.get("expiry_mode", ""))
                key = (date, time, action, expiry_mode)
                if key in selected_keys:
                    continue
                day_taken = int(day_counts.get(date, 0))
                if day_taken >= max_day:
                    continue
                minute = int(row["entry_minute"])
                if minute < int(next_allowed_by_day.get(date, -1)):
                    continue
                is_primary = str(row["source_stream"]) == str(args.primary_name)
                required = required_count_by_date(month, date, target)
                allow_fallback = selected_count < required
                if bool(getattr(args, "backfill_only_partial_months", False)) and not partial_month:
                    allow_fallback = False
                if (not is_primary) and (not allow_fallback):
                    continue
                out = row.copy()
                out["backfill_required_count"] = required
                out["backfill_count_before"] = selected_count
                out["backfill_month_target"] = target
                out["backfill_partial_month"] = partial_month
                out["backfill_mode"] = "primary" if is_primary else "fallback_volume_pace"
                selected.append(out)
                selected_keys.add(key)
                selected_count += 1
                day_counts[date] = day_taken + 1
                next_allowed_by_day[date] = minute + cooldown
            if selected:
                frames.append(pd.DataFrame(selected))

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    out = out.sort_values(["date", "entry_minute", "ticker", "source_stream"], kind="stable").reset_index(drop=True)
    return out


def write_plot(output_dir: Path, trades: pd.DataFrame, risk_capital: float) -> None:
    if trades.empty:
        return
    work = trades.copy()
    work["dt"] = pd.to_datetime(work["date"].astype(str), format="%Y%m%d", errors="coerce")
    work["pnl"] = pd.to_numeric(work["realized_return"], errors="coerce").fillna(0.0) * float(risk_capital)
    daily = work.groupby("dt")["pnl"].sum().sort_index()
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    daily = daily.reindex(idx).fillna(0.0)
    pd.DataFrame({"date": idx.strftime("%Y%m%d"), "daily_pnl": daily.values, "cum_pnl": daily.cumsum().values}).to_csv(
        output_dir / "monthly_volume_backfill_daily_total.csv", index=False
    )
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(idx, daily.cumsum().values, color="#111827", linewidth=2.4)
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Monthly Volume Backfill Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(idx, daily.values, color=np.where(daily.values >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "monthly_volume_backfill_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, args: argparse.Namespace) -> None:
    months = selected_months(args)
    overall = metrics(trades, months)
    by_ticker = {ticker: metrics(part, months) for ticker, part in trades.groupby("ticker", sort=True)} if not trades.empty else {}
    by_source = {source: metrics(part, months) for source, part in trades.groupby("source_stream", sort=True)} if not trades.empty else {}
    monthly_rows = []
    for month in months:
        part = trades[trades["month"].astype(str).eq(month)].copy() if not trades.empty else trades
        row = metrics(part, [month])
        row["month"] = month
        row["pnl_dollars"] = float(row["pnl_return"]) * float(args.risk_capital)
        monthly_rows.append(row)
    payload = {
        "overall": overall,
        "by_ticker": by_ticker,
        "by_source": by_source,
        "monthly": monthly_rows,
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "risk_capital": float(args.risk_capital),
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Monthly Volume Backfill",
        "",
        "This result takes a primary causal OOS trade stream and adds fallback trades only when month-to-date selected count is below the deterministic pace needed to reach the monthly volume floor.",
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
        "## By Source",
        "",
        "```json",
        json.dumps(by_source, indent=2, allow_nan=True),
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
        "## Config",
        "",
        "```json",
        json.dumps(vars(args), indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal month-to-date volume backfill between two event-option trade streams.")
    parser.add_argument("--primary-trades", required=True)
    parser.add_argument("--fallback-trades", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--primary-name", default="primary")
    parser.add_argument("--fallback-name", default="fallback")
    parser.add_argument("--ticker", default="", help="Optional ticker filter applied to both primary and fallback streams.")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--exclude-months", nargs="*", default=[], help="Months to remove from this backfill run, e.g. raw-partial months.")
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument(
        "--auto-partial-month-target",
        action="store_true",
        help="Raise the monthly target for a partial month so the observed month-to-date count can still clear a strict gate.",
    )
    parser.add_argument(
        "--partial-month-observed-floor",
        type=int,
        default=0,
        help="Observed trades required by the latest available date when --auto-partial-month-target is enabled.",
    )
    parser.add_argument(
        "--backfill-only-partial-months",
        action="store_true",
        help="Allow fallback trades only for months whose latest available date is before the month-end business day.",
    )
    parser.add_argument("--max-day", type=int, default=8)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--min-entry-minute", type=int, default=0)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    primary = load_trades(Path(args.primary_trades), str(args.primary_name))
    fallback = load_trades(Path(args.fallback_trades), str(args.fallback_name))
    if str(args.ticker).strip():
        ticker = str(args.ticker).upper()
        primary = primary[primary["ticker"].astype(str).str.upper().eq(ticker)].copy()
        fallback = fallback[fallback["ticker"].astype(str).str.upper().eq(ticker)].copy()
    if int(args.min_entry_minute) > 0:
        primary = primary[primary["entry_minute"] >= int(args.min_entry_minute)].copy()
        fallback = fallback[fallback["entry_minute"] >= int(args.min_entry_minute)].copy()
    selected = apply_backfill(primary, fallback, args)
    selected.to_csv(output_dir / "monthly_volume_backfill_trades.csv", index=False)
    pd.DataFrame([vars(args)]).to_csv(output_dir / "monthly_volume_backfill_config.csv", index=False)
    write_plot(output_dir, selected, float(args.risk_capital))
    write_summary(output_dir, selected, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
