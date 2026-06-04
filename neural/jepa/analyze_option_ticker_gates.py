from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.train_option_value_jepa import (
    select_fixed_delta,
    simulate_trailing_exit,
    trade_metrics,
)


TICKERS = ["QQQ", "SPX", "SPY"]


def fmt_pct(value: float) -> str:
    if value is None or not np.isfinite(float(value)):
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def fmt_float(value: float, digits: int = 3) -> str:
    if value is None or not np.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.{digits}f}"


def fmt_money(value: float) -> str:
    sign = "+" if float(value) >= 0 else "-"
    return f"{sign}${abs(float(value)):,.0f}"


def compact_metrics(trades: pd.DataFrame) -> dict:
    metrics = trade_metrics(trades)
    return {
        "trades": int(metrics.get("trades", 0)),
        "win_rate": float(metrics.get("win_rate", np.nan)),
        "profit_factor": float(metrics.get("profit_factor", np.nan)),
        "pnl_dollars": float(metrics.get("pnl_dollars", 0.0)),
        "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
        "avg_pnl": float(metrics.get("avg_pnl", np.nan)),
    }


def metric_row(label: str, metrics: dict) -> str:
    return (
        f"| {label} | {metrics['trades']} | {fmt_pct(metrics['win_rate'])} | "
        f"{fmt_float(metrics['profit_factor'])} | {fmt_money(metrics['pnl_dollars'])} | "
        f"{fmt_money(metrics['max_drawdown'])} | {fmt_money(metrics['avg_pnl'])} |"
    )


def cross_confirmed(trades: pd.DataFrame, target: str, confirmers: list[str]) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    keys = {
        ticker: set(map(tuple, group[["date", "time", "side"]].values))
        for ticker, group in trades.groupby("ticker", sort=False)
    }
    target_trades = trades[trades["ticker"].astype(str) == target].copy()
    keep = []
    for row in target_trades[["date", "time", "side"]].itertuples(index=False, name=None):
        keep.append(any(row in keys.get(confirmer, set()) for confirmer in confirmers if confirmer != target))
    return target_trades[keep].reset_index(drop=True)


def period_fixed_trades(candidates: pd.DataFrame, state_rows: pd.DataFrame, start: str, end: str | None) -> pd.DataFrame:
    mask = candidates["date"].astype(str) >= start
    if end:
        mask &= candidates["date"].astype(str) <= end
    selected = select_fixed_delta(candidates[mask].copy(), 0.70)
    args = SimpleNamespace(
        hard_stop_pct=-0.60,
        trail_activation_pct=0.50,
        trail_drawdown_pct=0.25,
        trail_take_profit_pct=10.0,
        entry_cutoff_time="14:30",
    )
    return simulate_trailing_exit(selected, state_rows, args, "fixed_delta_0.70_trail_cutoff")


def load_oracle_per_ticker(metrics_path: Path) -> dict:
    if not metrics_path.exists():
        return {}
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    policy_metrics = data.get("policy_metrics", {})
    oracle = policy_metrics.get("oracle_best_delta_hard", {})
    return oracle.get("per_ticker", {}) if isinstance(oracle, dict) else {}


def write_summary(
    output_dir: Path,
    blended: pd.DataFrame,
    fixed_val: pd.DataFrame,
    fixed_oos: pd.DataFrame,
    oracle_per_ticker: dict,
) -> None:
    lines: list[str] = [
        "# JEPA Option Ticker Gate Diagnostics",
        "",
        "This report is diagnostic research for ticker-specific deployment gates.",
        "Validation uses 2026-01-01 through 2026-03-31; OOS uses 2026-04-01 onward.",
        "",
        "## Current OOS OptionValue Blended + Trail/Cutoff",
        "",
        "| Scope | Trades | WR | PF | PnL | Max DD | Avg PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.append(metric_row("ALL", compact_metrics(blended)))
    for ticker in TICKERS:
        lines.append(metric_row(ticker, compact_metrics(blended[blended["ticker"].astype(str) == ticker])))

    lines += [
        "",
        "## Cross-Ticker Confirmation On Current OOS Blended Trades",
        "",
        "| Gate | Trades | WR | PF | PnL | Max DD | Avg PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.append(metric_row("SPY confirmed by SPX", compact_metrics(cross_confirmed(blended, "SPY", ["SPX"]))))
    lines.append(metric_row("SPY confirmed by any other", compact_metrics(cross_confirmed(blended, "SPY", ["SPX", "QQQ"]))))
    lines.append(metric_row("QQQ confirmed by SPX", compact_metrics(cross_confirmed(blended, "QQQ", ["SPX"]))))
    lines.append(metric_row("QQQ confirmed by SPX or SPY", compact_metrics(cross_confirmed(blended, "QQQ", ["SPX", "SPY"]))))

    lines += [
        "",
        "## Fixed 0.70 Trail/Cutoff Validation vs OOS Confirmation",
        "",
        "| Gate | Trades | WR | PF | PnL | Max DD | Avg PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, trades in [("VAL fixed 0.70", fixed_val), ("OOS fixed 0.70", fixed_oos)]:
        lines.append(metric_row(label, compact_metrics(trades)))
        for ticker in TICKERS:
            lines.append(metric_row(f"{label} {ticker}", compact_metrics(trades[trades["ticker"].astype(str) == ticker])))
        lines.append(metric_row(f"{label} SPY confirmed by SPX", compact_metrics(cross_confirmed(trades, "SPY", ["SPX"]))))
        lines.append(metric_row(f"{label} QQQ confirmed by SPX", compact_metrics(cross_confirmed(trades, "QQQ", ["SPX"]))))

    if oracle_per_ticker:
        lines += [
            "",
            "## OOS Oracle Delta Hard-Exit Upper Bound",
            "",
            "| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for ticker in TICKERS:
            metrics = oracle_per_ticker.get(ticker, {})
            if metrics:
                lines.append(
                    metric_row(
                        ticker,
                        {
                            "trades": int(metrics.get("trades", 0)),
                            "win_rate": float(metrics.get("win_rate", np.nan)),
                            "profit_factor": float(metrics.get("profit_factor", np.nan)),
                            "pnl_dollars": float(metrics.get("pnl_dollars", 0.0)),
                            "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
                            "avg_pnl": float(metrics.get("avg_pnl", np.nan)),
                        },
                    )
                )

    lines += [
        "",
        "## Interpretation",
        "",
        "- SPY's weak aggregate OOS result is mostly from unconfirmed SPY-only entries; SPY trades confirmed by SPX are SPX-like.",
        "- QQQ is not rescued by SPX/SPY confirmation in the current OOS window.",
        "- QQQ's hard-exit oracle delta upper bound is still far below SPX in the current OOS split, so strike selection alone cannot make QQQ SPX-like.",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose ticker-specific JEPA option gates.")
    parser.add_argument("--candidate-labels", default="research_papers/JEPA/results/jepa_full_pipeline_option_policy/candidate_labels.parquet")
    parser.add_argument("--state-rows", default="research_papers/JEPA/results/jepa_full_pipeline_option_value_split/option_value_state_rows.parquet")
    parser.add_argument("--blended-trades", default="research_papers/JEPA/results/jepa_full_pipeline_option_value_split/option_value_blended_score_trail_cutoff_trades.csv")
    parser.add_argument("--metrics", default="research_papers/JEPA/results/jepa_full_pipeline_option_value_split/metrics.json")
    parser.add_argument("--output-dir", default="research_papers/JEPA/results/jepa_full_pipeline_option_ticker_diagnostics")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = pd.read_parquet(args.candidate_labels)
    candidates["date"] = candidates["date"].astype(str)
    state_rows = pd.read_parquet(
        args.state_rows,
        columns=["candidate_id", "path_time", "hold_minutes", "current_pnl_pct", "pnl_dollars"],
    )
    blended = pd.read_csv(args.blended_trades)
    fixed_val = period_fixed_trades(candidates, state_rows, "20260101", "20260331")
    fixed_oos = period_fixed_trades(candidates, state_rows, "20260401", None)

    fixed_val.to_csv(output_dir / "fixed_delta_0.70_trail_cutoff_validation.csv", index=False)
    fixed_oos.to_csv(output_dir / "fixed_delta_0.70_trail_cutoff_oos.csv", index=False)
    cross_confirmed(blended, "SPY", ["SPX"]).to_csv(output_dir / "blended_spy_confirmed_by_spx.csv", index=False)
    cross_confirmed(blended, "QQQ", ["SPX"]).to_csv(output_dir / "blended_qqq_confirmed_by_spx.csv", index=False)

    write_summary(output_dir, blended, fixed_val, fixed_oos, load_oracle_per_ticker(Path(args.metrics)))
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
