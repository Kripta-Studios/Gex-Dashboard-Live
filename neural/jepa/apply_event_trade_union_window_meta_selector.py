from __future__ import annotations

import argparse
from copy import copy
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
        path = Path(value)
        return path.name, path
    name, raw_path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"Missing source name in {value!r}")
    return name, Path(raw_path.strip())


def load_candidate(spec: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    name, path = parse_named_path(spec)
    trade_path = next(
        (
            path / filename
            for filename in (
                "trade_union_config_selector_trades.csv",
                "trade_union_window_meta_selector_trades.csv",
                "combined_trades.csv",
                "static_union_trades.csv",
            )
            if (path / filename).exists()
        ),
        None,
    )
    fold_path = next(
        (
            path / filename
            for filename in (
                "trade_union_config_selector_folds.csv",
                "trade_union_window_meta_selector_folds.csv",
                "combined_folds.csv",
                "static_union_folds.csv",
            )
            if (path / filename).exists()
        ),
        None,
    )
    if trade_path is None:
        raise FileNotFoundError(path / "trade_union_config_selector_trades.csv")
    if fold_path is None:
        raise FileNotFoundError(path / "trade_union_config_selector_folds.csv")
    trades = pd.read_csv(
        trade_path,
        dtype={"ticker": str, "date": str, "month": str, "time": str, "test_month": str},
        low_memory=False,
    )
    folds = pd.read_csv(fold_path, dtype=str)
    for frame in (trades, folds):
        if "test_month" not in frame.columns and "month" in frame.columns:
            frame["test_month"] = frame["month"].astype(str)
        if "month" not in frame.columns and "test_month" in frame.columns:
            frame["month"] = frame["test_month"].astype(str)
        frame["ticker"] = frame["ticker"].astype(str).str.upper()
        frame["month"] = frame["month"].astype(str)
        frame["test_month"] = frame["test_month"].astype(str)
        frame["meta_window_candidate"] = name
        frame["meta_window_candidate_dir"] = path.name
    trades["realized_return"] = pd.to_numeric(trades["realized_return"], errors="coerce").fillna(0.0)
    return trades, folds


def finite_or(value: float, default: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def score_metrics(row: dict, args: argparse.Namespace) -> float:
    trades = int(row.get("trades", 0) or 0)
    min_month = int(row.get("min_month_trades", 0) or 0)
    pf = finite_or(row.get("profit_factor", 0.0), float(args.score_pf_cap))
    wr = finite_or(row.get("win_rate", 0.0), 0.0)
    pnl_return = finite_or(row.get("pnl_return", 0.0), 0.0)
    positive_month_rate = finite_or(row.get("positive_month_rate", 0.0), 0.0)
    daily_dd = abs(finite_or(row.get("daily_max_drawdown", 0.0), 0.0))
    top5 = finite_or(row.get("top5_share_of_pnl", 0.0), 0.0)
    top5_target = float(getattr(args, "score_top5_target", 1.0))
    if trades < int(args.min_select_trades):
        return -1e18
    if min_month < int(args.min_select_month_trades):
        return -1e18
    if str(args.rank_mode) == "strict":
        if wr < float(args.min_select_win_rate):
            return -1e18
        if pf < float(args.min_select_profit_factor):
            return -1e18
        if pnl_return <= 0.0:
            return -1e18
    return (
        min(pf, float(args.score_pf_cap)) * float(args.score_pf_weight)
        + wr * float(args.score_win_weight)
        + pnl_return * float(args.score_return_weight)
        + positive_month_rate * float(args.score_positive_month_weight)
        + min(float(min_month), 60.0) * float(args.score_volume_weight)
        - daily_dd * float(args.score_daily_dd_penalty)
        - max(top5 - top5_target, 0.0) * float(args.score_top5_penalty)
    )


def flatten(prefix: str, row: dict | None) -> dict:
    return {f"{prefix}_{key}": value for key, value in (row or {}).items()}


def choose_candidate(
    ticker: str,
    month: str,
    candidates: dict[str, pd.DataFrame],
    all_months: list[str],
    args: argparse.Namespace,
) -> tuple[str | None, list[str], dict, float]:
    previous = [m for m in all_months if m < month]
    if int(args.meta_select_months) > 0:
        previous = previous[-int(args.meta_select_months) :]
    if len(previous) < int(args.min_history_months):
        return None, previous, {}, float("nan")
    best_name: str | None = None
    best_metrics: dict = {}
    best_score = -1e18
    best_relaxed = False
    for name, trades in candidates.items():
        hist = trades[
            trades["ticker"].astype(str).str.upper().eq(ticker)
            & trades["month"].astype(str).isin(previous)
        ].copy()
        row = metrics(hist, previous)
        score = score_metrics(row, args)
        if score > best_score:
            best_name = name
            best_metrics = row
            best_score = float(score)
            best_relaxed = False
    if best_score <= -1e17 and bool(args.relax_min_month_if_empty) and int(args.min_select_month_trades) > 0:
        relaxed_args = copy(args)
        relaxed_args.min_select_month_trades = 0
        for name, trades in candidates.items():
            hist = trades[
                trades["ticker"].astype(str).str.upper().eq(ticker)
                & trades["month"].astype(str).isin(previous)
            ].copy()
            row = metrics(hist, previous)
            score = score_metrics(row, relaxed_args)
            if score > best_score:
                best_name = name
                best_metrics = row
                best_score = float(score)
                best_relaxed = True
    if best_score <= -1e17:
        return None, previous, best_metrics, best_score
    if best_relaxed:
        best_metrics = dict(best_metrics)
        best_metrics["relaxed_min_month_filter"] = True
    return best_name, previous, best_metrics, best_score


def select_walkforward(
    candidate_trades: dict[str, pd.DataFrame],
    candidate_folds: dict[str, pd.DataFrame],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    months = month_range(str(args.start_month), str(args.end_month))
    tickers = [ticker.upper() for ticker in args.tickers]
    all_months = sorted(
        {
            str(month)
            for trades in candidate_trades.values()
            for month in trades["month"].astype(str).unique().tolist()
        }
    )
    out_parts: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    frozen_choices: dict[str, tuple[str | None, list[str], dict, float]] = {}
    if str(args.selection_mode) == "frozen":
        for ticker in tickers:
            frozen_choices[ticker] = choose_candidate(ticker, months[0], candidate_trades, all_months, args)
    for ticker in tickers:
        for month in months:
            if str(args.selection_mode) == "frozen":
                selected_name, select_months, select_metrics, select_score = frozen_choices[ticker]
            else:
                selected_name, select_months, select_metrics, select_score = choose_candidate(
                    ticker, month, candidate_trades, all_months, args
                )
            if selected_name is None:
                mode = "NO_VALID_SOURCE" if len(select_months) >= int(args.min_history_months) else "NO_META_HISTORY"
                fold_rows.append(
                    {
                        "ticker": ticker,
                        "month": month,
                        "test_month": month,
                        "mode": mode,
                        "selected_meta_window_candidate": "",
                        "select_months": ",".join(select_months),
                        "select_score": select_score,
                        **flatten("select", select_metrics),
                        **flatten("test", metrics(pd.DataFrame(), [month])),
                    }
                )
                continue
            source_trades = candidate_trades[selected_name]
            selected = source_trades[
                source_trades["ticker"].astype(str).str.upper().eq(ticker)
                & source_trades["month"].astype(str).eq(month)
            ].copy()
            source_folds = candidate_folds[selected_name]
            source_fold = source_folds[
                source_folds["ticker"].astype(str).str.upper().eq(ticker)
                & source_folds["month"].astype(str).eq(month)
            ].copy()
            candidate_inner_months = ""
            selected_variants = ""
            selected_max_day = ""
            selected_cooldown = ""
            selected_daily_order = ""
            candidate_mode = ""
            if not source_fold.empty:
                first = source_fold.iloc[0].to_dict()
                candidate_inner_months = str(first.get("select_months", ""))
                selected_variants = str(first.get("variants", first.get("union_sources", "")))
                selected_max_day = str(first.get("max_day", first.get("max_trades_per_day", "")))
                selected_cooldown = str(first.get("cooldown", ""))
                selected_daily_order = str(first.get("daily_order", ""))
                candidate_mode = str(first.get("mode", ""))
            if not selected.empty:
                selected["meta_window_selector_mode"] = "SELECTED"
                selected["selected_meta_window_candidate"] = selected_name
                selected["meta_select_months"] = ",".join(select_months)
                selected["meta_select_score"] = select_score
                selected["candidate_inner_select_months"] = candidate_inner_months
                out_parts.append(selected)
            test_metrics = metrics(selected, [month])
            fold_rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "test_month": month,
                    "mode": "SELECTED_FROZEN" if str(args.selection_mode) == "frozen" else "SELECTED",
                    "selected_meta_window_candidate": selected_name,
                    "candidate_mode": candidate_mode,
                    "candidate_variants": selected_variants,
                    "candidate_max_day": selected_max_day,
                    "candidate_cooldown": selected_cooldown,
                    "candidate_daily_order": selected_daily_order,
                    "select_months": ",".join(select_months),
                    "inner_val_months": candidate_inner_months,
                    "select_score": select_score,
                    **flatten("select", select_metrics),
                    **flatten("test", test_metrics),
                }
            )
    trades = pd.concat(out_parts, ignore_index=True, sort=False) if out_parts else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    return trades, folds


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
        output_dir / "window_meta_selector_daily_total.csv", index=False
    )
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(idx, daily.cumsum().values, color="#111827", linewidth=2.4)
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Trade Union Window Meta-Selector Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(idx, daily.values, color=np.where(daily.values >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "window_meta_selector_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def metrics_by_period(trades: pd.DataFrame, args: argparse.Namespace) -> list[dict]:
    periods = [("eval", month_range(str(args.start_month), str(args.end_month)))]
    if str(args.start_month) <= "202501" and str(args.end_month) >= "202512":
        periods.append(("2025", month_range("202501", "202512")))
    if str(args.start_month) <= "202601" and str(args.end_month) >= "202606":
        periods.append(("2026_partial", month_range("202601", "202606")))
    rows: list[dict] = []
    for period, months in periods:
        for ticker in [ticker.upper() for ticker in args.tickers]:
            part = trades[
                trades["ticker"].astype(str).str.upper().eq(ticker)
                & trades["month"].astype(str).isin(months)
            ].copy()
            rows.append({"period": period, "ticker": ticker, **metrics(part, months)})
        rows.append(
            {
                "period": period,
                "ticker": "ALL",
                **metrics(trades[trades["month"].astype(str).isin(months)].copy(), months),
            }
        )
    return rows


def write_summary(
    output_dir: Path,
    trades: pd.DataFrame,
    folds: pd.DataFrame,
    metric_rows: list[dict],
    source_specs: list[str],
    args: argparse.Namespace,
) -> None:
    payload = {
        "status": "walkforward_window_meta_selector",
        "source_specs": source_specs,
        "args": vars(args),
        "metrics_by_period": metric_rows,
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Trade Union Window Meta-Selector",
        "",
        "This result selects among precomputed rolling trade-union config selectors by ticker/month using only earlier OOS months from the same candidate selector outputs.",
        "",
        "## Metrics",
        "",
    ]
    for period in dict.fromkeys(row["period"] for row in metric_rows):
        lines += [
            f"### {period}",
            "",
            "| Ticker | Trades | WR | PF | Min Trades/Month | PnL R |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in [r for r in metric_rows if r["period"] == period]:
            lines.append(
                f"| {row['ticker']} | {int(row.get('trades', 0))} | "
                f"{float(row.get('win_rate', 0.0)):.2%} | {float(row.get('profit_factor', 0.0)):.3f} | "
                f"{int(row.get('min_month_trades', 0))} | {float(row.get('pnl_return', 0.0)):.3f} |"
            )
        lines.append("")
    lines += [
        "## Selected Candidates",
        "",
        "```csv",
        folds[
            [
                "ticker",
                "month",
                "mode",
                "selected_meta_window_candidate",
                "select_months",
                "select_score",
                "candidate_variants",
                "candidate_max_day",
                "candidate_cooldown",
                "candidate_daily_order",
                "test_trades",
                "test_win_rate",
                "test_profit_factor",
                "test_pnl_return",
            ]
        ].to_csv(index=False),
        "```",
        "",
        "## Sources",
        "",
        "```json",
        json.dumps(source_specs, indent=2),
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
    parser = argparse.ArgumentParser(description="Causal meta-selector over rolling event trade-union selector windows.")
    parser.add_argument("--selector-source", action="append", required=True, help="name=path to selector result dir")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--meta-select-months", type=int, default=12)
    parser.add_argument("--min-history-months", type=int, default=3)
    parser.add_argument("--selection-mode", choices=["monthly", "frozen"], default="monthly")
    parser.add_argument("--rank-mode", choices=["continuous", "strict"], default="continuous")
    parser.add_argument("--min-select-trades", type=int, default=1)
    parser.add_argument("--min-select-month-trades", type=int, default=0)
    parser.add_argument("--relax-min-month-if-empty", action="store_true")
    parser.add_argument("--min-select-win-rate", type=float, default=0.45)
    parser.add_argument("--min-select-profit-factor", type=float, default=1.30)
    parser.add_argument("--score-pf-weight", type=float, default=3.0)
    parser.add_argument("--score-pf-cap", type=float, default=4.0)
    parser.add_argument("--score-win-weight", type=float, default=20.0)
    parser.add_argument("--score-return-weight", type=float, default=0.10)
    parser.add_argument("--score-positive-month-weight", type=float, default=4.0)
    parser.add_argument("--score-volume-weight", type=float, default=0.10)
    parser.add_argument("--score-daily-dd-penalty", type=float, default=0.05)
    parser.add_argument("--score-top5-target", type=float, default=1.0)
    parser.add_argument("--score-top5-penalty", type=float, default=0.25)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_trades: dict[str, pd.DataFrame] = {}
    candidate_folds: dict[str, pd.DataFrame] = {}
    for spec in args.selector_source:
        name, _path = parse_named_path(spec)
        trades, folds = load_candidate(spec)
        if name in candidate_trades:
            raise RuntimeError(f"Duplicate selector source name {name}")
        candidate_trades[name] = trades
        candidate_folds[name] = folds
    trades, folds = select_walkforward(candidate_trades, candidate_folds, args)
    if not trades.empty:
        trades.to_csv(output_dir / "trade_union_window_meta_selector_trades.csv", index=False)
        trades.to_csv(output_dir / "combined_trades.csv", index=False)
    folds.to_csv(output_dir / "trade_union_window_meta_selector_folds.csv", index=False)
    folds.to_csv(output_dir / "combined_folds.csv", index=False)
    metric_rows = metrics_by_period(trades, args)
    pd.DataFrame(metric_rows).to_csv(output_dir / "metrics_by_period.csv", index=False)
    write_plot(output_dir, trades, float(args.risk_capital))
    write_summary(output_dir, trades, folds, metric_rows, list(args.selector_source), args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
