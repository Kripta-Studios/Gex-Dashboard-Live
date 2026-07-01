from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apply_event_monthly_volume_backfill import apply_backfill, load_trades
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


def parse_source(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Expected NAME=PATH, got {value!r}")
    name, raw_path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"Empty source name in {value!r}")
    return name, Path(raw_path.strip())


def parse_pair(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError(f"Expected PRIMARY=FALLBACK, got {value!r}")
    primary, fallback = value.split("=", 1)
    primary = primary.strip()
    fallback = fallback.strip()
    if not primary or not fallback:
        raise ValueError(f"Invalid pair {value!r}")
    return primary, fallback


def score_metrics_for_selection(row: dict, args: argparse.Namespace) -> float:
    trades = int(row.get("trades", 0))
    min_month = int(row.get("min_month_trades", 0))
    wr = float(row.get("win_rate", float("nan")))
    pf = float(row.get("profit_factor", float("nan")))
    pnl = float(row.get("pnl_return", 0.0))
    dd = abs(float(row.get("max_drawdown", 0.0)))
    call_rate = float(row.get("call_rate", float("nan")))
    positive_month_rate = float(row.get("positive_month_rate", 0.0))
    score = 0.0
    if trades < int(args.min_select_trades):
        score -= 1_000_000.0 + float(int(args.min_select_trades) - trades)
    if min_month < int(args.min_select_month_trades):
        score -= 1_000_000.0 + float(int(args.min_select_month_trades) - min_month)
    if not np.isfinite(wr) or wr <= float(args.min_select_win_rate):
        score -= 1_000_000.0 + 100.0 * max(0.0, float(args.min_select_win_rate) - (wr if np.isfinite(wr) else 0.0))
    if not np.isfinite(pf) or pf <= float(args.min_select_pf):
        score -= 1_000_000.0 + 100.0 * max(0.0, float(args.min_select_pf) - (pf if np.isfinite(pf) else 0.0))
    if not np.isfinite(call_rate) or call_rate < float(args.min_call_rate) or call_rate > float(args.max_call_rate):
        score -= 1_000_000.0
    if bool(args.require_select_positive_months) and positive_month_rate < 1.0:
        score -= 1_000_000.0 + 1000.0 * (1.0 - positive_month_rate)
    score += min(max(pf if np.isfinite(pf) else 0.0, 0.0), 5.0) * 5.0
    score += (wr if np.isfinite(wr) else 0.0) * 20.0
    score += pnl * 0.20
    score += positive_month_rate * 5.0
    score += min(min_month, 60) * 0.05
    score -= dd * 0.20
    return float(score)


def make_backfill_args(args: argparse.Namespace, primary: str, fallback: str, start_month: str, end_month: str) -> SimpleNamespace:
    return SimpleNamespace(
        start_month=str(start_month),
        end_month=str(end_month),
        min_month_trades=int(args.target_month_trades),
        max_day=int(args.max_day),
        cooldown_minutes=int(args.cooldown_minutes),
        primary_name=str(primary),
        fallback_name=str(fallback),
        risk_capital=float(args.risk_capital),
    )


def run_pair(
    sources: dict[str, pd.DataFrame],
    primary: str,
    fallback: str,
    args: argparse.Namespace,
    start_month: str,
    end_month: str,
) -> pd.DataFrame:
    return apply_backfill(
        sources[primary],
        sources[fallback],
        make_backfill_args(args, primary, fallback, start_month, end_month),
    )


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
        output_dir / "nested_volume_backfill_daily_total.csv", index=False
    )
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(idx, daily.cumsum().values, color="#111827", linewidth=2.4)
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Nested Volume Backfill Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(idx, daily.values, color=np.where(daily.values >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "nested_volume_backfill_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, payload: dict) -> None:
    lines = [
        "# Event Nested Volume Backfill",
        "",
        "This result selects the primary/fallback stream pair using only prior OOS months, then applies deterministic month-to-date volume backfill to the test month.",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(payload["overall"], indent=2, allow_nan=True),
        "```",
        "",
        "## By Ticker",
        "",
        "```json",
        json.dumps(payload["by_ticker"], indent=2, allow_nan=True),
        "```",
        "",
        f"- Risk capital: ${float(payload['risk_capital']):,.0f}",
        f"- Net PnL: ${float(payload['net_pnl']):,.0f}",
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
        json.dumps(payload["args"], indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Nested walk-forward selector for event-option monthly volume backfill pairs.")
    parser.add_argument("--source", action="append", required=True, help="NAME=path")
    parser.add_argument("--pair", action="append", required=True, help="PRIMARY=FALLBACK")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--history-start-month", default="202510")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--select-months", type=int, default=3)
    parser.add_argument("--target-month-trades", type=int, default=19)
    parser.add_argument("--max-day", type=int, default=8)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--min-select-trades", type=int, default=54)
    parser.add_argument("--min-select-month-trades", type=int, default=19)
    parser.add_argument("--min-select-win-rate", type=float, default=0.45)
    parser.add_argument("--min-select-pf", type=float, default=1.30)
    parser.add_argument("--require-select-positive-months", action="store_true")
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ticker = str(args.ticker).upper()
    sources: dict[str, pd.DataFrame] = {}
    source_specs: dict[str, str] = {}
    for spec in args.source:
        name, path = parse_source(spec)
        frame = load_trades(path, name)
        frame = frame[frame["ticker"].astype(str).str.upper().eq(ticker)].copy()
        frame = frame[
            (frame["month"].astype(str) >= str(args.history_start_month))
            & (frame["month"].astype(str) <= str(args.end_month))
        ].copy()
        sources[name] = frame
        source_specs[name] = str(path)
    pairs = [parse_pair(item) for item in args.pair]
    for primary, fallback in pairs:
        if primary not in sources:
            raise ValueError(f"Unknown primary source {primary!r}")
        if fallback not in sources:
            raise ValueError(f"Unknown fallback source {fallback!r}")

    eval_months = month_range(str(args.start_month), str(args.end_month))
    all_months = sorted(set().union(*[set(frame["month"].astype(str).unique()) for frame in sources.values()]))
    out_parts: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    for month in eval_months:
        previous = [m for m in all_months if m < str(month)]
        select_months = previous[-int(args.select_months) :]
        best_pair = pairs[0]
        best_select = metrics(pd.DataFrame(), select_months)
        best_score = -1e30
        mode = "NO_HISTORY"
        if len(select_months) >= int(args.select_months):
            mode = "SELECTED"
            for primary, fallback in pairs:
                selected_history = run_pair(sources, primary, fallback, args, select_months[0], select_months[-1])
                selected_history = selected_history[selected_history["month"].astype(str).isin(select_months)].copy()
                row = metrics(selected_history, select_months)
                score = score_metrics_for_selection(row, args)
                if score > best_score:
                    best_pair = (primary, fallback)
                    best_select = row
                    best_score = score
        test = run_pair(sources, best_pair[0], best_pair[1], args, str(month), str(month))
        if not test.empty:
            test["nested_primary"] = best_pair[0]
            test["nested_fallback"] = best_pair[1]
            test["nested_mode"] = mode
            test["nested_select_months"] = ",".join(select_months)
            out_parts.append(test)
        test_metrics = metrics(test, [str(month)])
        row = {
            "ticker": ticker,
            "test_month": str(month),
            "mode": mode,
            "primary": best_pair[0],
            "fallback": best_pair[1],
            "select_months": ",".join(select_months),
            "select_score": float(best_score),
        }
        row.update({f"select_{k}": v for k, v in best_select.items()})
        row.update({f"test_{k}": v for k, v in test_metrics.items()})
        fold_rows.append(row)

    trades = pd.concat(out_parts, ignore_index=True, sort=False) if out_parts else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    if not trades.empty:
        trades.to_csv(output_dir / "nested_volume_backfill_trades.csv", index=False)
    folds.to_csv(output_dir / "nested_volume_backfill_folds.csv", index=False)
    expected = eval_months
    overall = metrics(trades, expected)
    by_ticker = {t: metrics(part, expected) for t, part in trades.groupby("ticker", sort=True)} if not trades.empty else {}
    payload = {
        "overall": overall,
        "by_ticker": by_ticker,
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "risk_capital": float(args.risk_capital),
        "args": {**vars(args), "sources": source_specs},
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_plot(output_dir, trades, float(args.risk_capital))
    write_summary(output_dir, trades, folds, payload)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
