from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from validate_frozen_pre2025_monthly_backfill_runtime_replay import replay_runtime_policy
from walkforward_event_option_gate import metrics


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "research_papers"
    / "JEPA"
    / "results"
    / "_diagnostics"
    / "frozen_source_selector_dense15_pre2025_static_202301_202604_source_replay_v1"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize the frozen pre-2025 static source selector candidate over a historical month range.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--start-month", default="202301")
    parser.add_argument("--end-month", default="202604")
    parser.add_argument("--exclude-months", nargs="*", default=["202403"])
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--max-day", type=int, default=3)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    replay_args = SimpleNamespace(
        start_month=str(args.start_month),
        end_month=str(args.end_month),
        tickers=[str(t).upper() for t in args.tickers],
        primary_name="win_valthr_wr45_d25",
        fallback_name="forcedmax3_d50",
        min_month_trades=int(args.min_month_trades),
        max_day=int(args.max_day),
        cooldown_minutes=int(args.cooldown_minutes),
        auto_partial_month_target=False,
        partial_month_observed_floor=0,
    )
    trades = replay_runtime_policy(replay_args)
    if trades.empty:
        raise RuntimeError("No trades materialized")
    trades = trades[~trades["month"].astype(str).isin([str(m) for m in args.exclude_months])].copy()
    trades["event_delta_bucket"] = np.where(trades["backfill_mode"].astype(str).eq("primary"), 25, 50)
    trades["event_delta_target"] = trades["event_delta_bucket"].astype(float) / 100.0
    trades["test_month"] = trades["month"].astype(str)
    trades = trades.sort_values(["date", "entry_minute", "ticker", "backfill_mode"], kind="stable").reset_index(drop=True)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    trade_path = output_dir / "combined_trades.csv"
    trades.to_csv(trade_path, index=False)

    months = [m for m in month_range(str(args.start_month), str(args.end_month)) if m not in set(str(x) for x in args.exclude_months)]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "artifact": "frozen_pre2025_static_source_replay",
        "trade_file": str(trade_path.resolve().relative_to(PROJECT_ROOT.resolve())),
        "months": months,
        "excluded_months": [str(x) for x in args.exclude_months],
        "tickers": [str(t).upper() for t in args.tickers],
        "overall": metrics(trades, months),
        "by_ticker": {ticker: metrics(part, months) for ticker, part in trades.groupby("ticker", sort=True)},
        "risk_capital": float(args.risk_capital),
        "policy_parameters": {
            "min_month_trades": int(args.min_month_trades),
            "max_day": int(args.max_day),
            "cooldown_minutes": int(args.cooldown_minutes),
        },
        "scope_note": "This materializes the fixed pre-2025-selected source family over historical OOS candidate streams. It is an input for causal guard selection, not new production evidence by itself.",
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Frozen Pre-2025 Static Source Replay",
        "",
        f"- Trades: `{len(trades)}`",
        f"- Months: `{args.start_month}`-`{args.end_month}`",
        f"- Excluded months: `{', '.join(str(x) for x in args.exclude_months)}`",
        f"- Min month target: `{int(args.min_month_trades)}`",
        f"- Max day: `{int(args.max_day)}`",
        f"- Cooldown minutes: `{int(args.cooldown_minutes)}`",
        "",
        "```json",
        json.dumps(payload["by_ticker"], indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), "trades": int(len(trades)), "by_ticker": payload["by_ticker"]}, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
