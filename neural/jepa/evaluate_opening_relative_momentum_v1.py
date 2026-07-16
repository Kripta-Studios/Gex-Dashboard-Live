#!/usr/bin/env python3
"""Frozen development ledger for OPENING_RELATIVE_MOMENTUM_V1."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from neural.jepa import evaluate_cross_session_relative_value_v1 as source


REPO_ROOT = Path(__file__).resolve().parents[2]
PREDECLARATION = REPO_ROOT / "research_papers/JEPA/OPENING_RELATIVE_MOMENTUM_V1_PREDECLARATION.md"
DEFAULT_DATA_ROOT = source.DEFAULT_DATA_ROOT
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/opening_relative_momentum_v1_development_202201_202312"
)

SOURCE_TICKERS = source.SOURCE_TICKERS
DEVELOPMENT_END = "20231231"
OPEN_TIME = "09:30"
DECISION_BAR_TIME = "10:34"
ENTRY_TIME = "10:36"
EXIT_TIME = "13:36"
HOLD_MINUTES = 180
COST_PER_LEG_BPS = 1.0
TOTAL_COST_BPS = 2.0
HALF_DAYS = frozenset({"20221125", "20230703", "20231124"})
INVALID_TRADE_DAYS = frozenset({"20230605"})


def _timestamp(day: str, clock: str) -> pd.Timestamp:
    return pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {clock}")


def build_trade_row(day: str, frames: dict[str, pd.DataFrame]) -> dict:
    opening_moves: dict[str, float] = {}
    for ticker in SOURCE_TICKERS:
        open_price = float(frames[ticker].loc[_timestamp(day, OPEN_TIME), "open"])
        decision_close = float(frames[ticker].loc[_timestamp(day, DECISION_BAR_TIME), "close"])
        opening_moves[ticker] = source.log_return_bps(decision_close, open_price)

    market_anchor = 0.5 * (opening_moves["SPY"] + opening_moves["SPXW"])
    relative_impulse = opening_moves["QQQ"] - market_anchor
    if relative_impulse > 0.0:
        qqq_position, spy_position, action = 1, -1, "LONG_QQQ_SHORT_SPY"
    elif relative_impulse < 0.0:
        qqq_position, spy_position, action = -1, 1, "SHORT_QQQ_LONG_SPY"
    else:
        qqq_position, spy_position, action = 0, 0, "NO_TRADE_ZERO_IMPULSE"

    entry_timestamp = _timestamp(day, ENTRY_TIME)
    exit_timestamp = _timestamp(day, EXIT_TIME)
    qqq_return = source.log_return_bps(
        float(frames["QQQ"].loc[exit_timestamp, "open"]),
        float(frames["QQQ"].loc[entry_timestamp, "open"]),
    )
    spy_return = source.log_return_bps(
        float(frames["SPY"].loc[exit_timestamp, "open"]),
        float(frames["SPY"].loc[entry_timestamp, "open"]),
    )
    gross = float(qqq_position * qqq_return + spy_position * spy_return)
    executed = bool(qqq_position)
    return {
        "trade_date": day,
        "month": day[:6],
        "open_time": OPEN_TIME,
        "decision_bar_time": DECISION_BAR_TIME,
        "entry_time": ENTRY_TIME,
        "exit_time": EXIT_TIME,
        "hold_minutes": HOLD_MINUTES,
        "qqq_opening_move_bps": opening_moves["QQQ"],
        "spxw_opening_move_bps": opening_moves["SPXW"],
        "spy_opening_move_bps": opening_moves["SPY"],
        "market_anchor_bps": market_anchor,
        "relative_impulse_bps": relative_impulse,
        "action": action,
        "trade_executed": executed,
        "qqq_position": qqq_position,
        "spy_position": spy_position,
        "qqq_leg_return_bps": qqq_return,
        "spy_leg_return_bps": spy_return,
        "gross_bps": gross,
        "cost_bps": TOTAL_COST_BPS if executed else 0.0,
        "net_bps": gross - TOTAL_COST_BPS if executed else 0.0,
        "mean_reversion_control_net_bps": -gross - TOTAL_COST_BPS if executed else 0.0,
        "fixed_long_qqq_short_spy_net_bps": qqq_return - spy_return - TOTAL_COST_BPS,
    }


def build_development_ledger(
    sessions: dict[str, dict[str, pd.DataFrame]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict] = []
    exclusions: list[dict] = []
    for day in sorted(sessions):
        if day in HALF_DAYS:
            exclusions.append({"trade_date": day, "reason": "CURRENT_HALF_DAY"})
            continue
        if day in INVALID_TRADE_DAYS:
            exclusions.append({"trade_date": day, "reason": "KNOWN_INVALID_SIGNAL_WINDOW"})
            continue
        rows.append(build_trade_row(day, sessions[day]))
    ledger = pd.DataFrame(rows).sort_values("trade_date", kind="stable").reset_index(drop=True)
    excluded = pd.DataFrame(exclusions).sort_values("trade_date", kind="stable").reset_index(drop=True)
    if ledger.empty or ledger["trade_date"].duplicated().any():
        raise AssertionError("invalid development ledger")
    if ledger["trade_date"].max() > DEVELOPMENT_END:
        raise AssertionError("ledger crossed development cutoff")
    if not ledger["hold_minutes"].eq(HOLD_MINUTES).all():
        raise AssertionError("hold contract mismatch")
    return ledger, excluded


def classify_status(development_pass: bool, aggregate_profit_factor: float) -> str:
    if development_pass:
        return "PASS_DEVELOPMENT_GATE_OUTER_NOT_OPENED"
    if aggregate_profit_factor > 1.0:
        return "INCREMENTAL_EDGE_ONLY"
    return "NO_AGGREGATE_EDGE"


def render_summary(summary: dict, monthly: pd.DataFrame) -> str:
    aggregate = summary["primary_aggregate"]
    return "\n".join(
        [
            "# OPENING_RELATIVE_MOMENTUM_V1 development",
            "",
            f"Status: `{summary['status']}`",
            "",
            (
                f"Primary momentum: {aggregate['trades']} trades, WR "
                f"{aggregate['win_rate']:.3%}, PF {aggregate['profit_factor']:.6f}, "
                f"PnL {aggregate['net_bps']:+.3f} bps."
            ),
            "",
            f"Months passing all gates: {int(monthly['month_pass'].sum())}/{len(monthly)}.",
            "",
            "2024-2026 and production were not opened.",
            "",
        ]
    )


def run(data_root: Path, output_dir: Path) -> dict:
    if not PREDECLARATION.is_file():
        raise FileNotFoundError(PREDECLARATION)
    if source.DEVELOPMENT_END != DEVELOPMENT_END:
        raise AssertionError("source dependency cutoff mismatch")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    inventory = source.discover_source_files(data_root)
    sessions = source.load_sessions(inventory)
    ledger, exclusions = build_development_ledger(sessions)
    monthly = source.summarize_monthly(ledger)
    executed = ledger.loc[ledger["trade_executed"]]
    net = executed["net_bps"].to_numpy(dtype=np.float64)
    aggregate_pf = source.profit_factor(net)
    aggregate = {
        "trades": int(len(executed)),
        "win_rate": float(np.mean(net > 0.0)) if len(net) else 0.0,
        "profit_factor": aggregate_pf,
        "net_bps": float(net.sum()),
        "min_month_trades": int(monthly["trades"].min()),
        "positive_months": int((monthly["net_bps"] > 0.0).sum()),
        "months_passing": int(monthly["month_pass"].sum()),
    }
    development_pass = bool(monthly["month_pass"].all())
    incremental_edge = bool(aggregate_pf > 1.0)
    controls = pd.DataFrame(
        [
            source.summarize_control(ledger, "mean_reversion_control_net_bps"),
            source.summarize_control(ledger, "fixed_long_qqq_short_spy_net_bps"),
        ]
    )

    source._atomic_write_csv(output_dir / "source_inventory.csv", inventory)
    source._atomic_write_csv(output_dir / "trades.csv", ledger)
    source._atomic_write_csv(output_dir / "excluded_sessions.csv", exclusions)
    source._atomic_write_csv(output_dir / "monthly_metrics.csv", monthly)
    source._atomic_write_csv(output_dir / "controls_summary.csv", controls)

    summary = {
        "schema_version": "opening_relative_momentum_v1.development.v1",
        "status": classify_status(development_pass, aggregate_pf),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "development_202201_202312",
        "development_pass": development_pass,
        "incremental_aggregate_edge": incremental_edge,
        "outer_2024_2025_opened": False,
        "holdout_2026_opened": False,
        "production_changed": False,
        "predeclaration_sha256": source.sha256_file(PREDECLARATION),
        "runner_sha256": source.sha256_file(Path(__file__).resolve()),
        "source_dependency_sha256": source.sha256_file(Path(source.__file__).resolve()),
        "source_inventory_sha256": source.dataframe_digest(inventory),
        "trades_sha256": source.dataframe_digest(ledger),
        "monthly_sha256": source.dataframe_digest(monthly),
        "controls_sha256": source.dataframe_digest(controls),
        "source_sessions_per_ticker": {
            ticker: int(inventory["ticker"].eq(ticker).sum()) for ticker in SOURCE_TICKERS
        },
        "trade_clock": {
            "open_time": OPEN_TIME,
            "decision_bar_time": DECISION_BAR_TIME,
            "entry_time": ENTRY_TIME,
            "exit_time": EXIT_TIME,
            "hold_minutes": HOLD_MINUTES,
            "cost_per_leg_bps": COST_PER_LEG_BPS,
            "total_cost_bps": TOTAL_COST_BPS,
        },
        "gates": {
            "profit_factor_strictly_greater_than": source.MIN_PROFIT_FACTOR,
            "win_rate_strictly_greater_than": source.MIN_WIN_RATE,
            "trades_per_month_strictly_greater_than": source.MIN_TRADES_EXCLUSIVE,
            "monthly_net_bps_strictly_greater_than": 0.0,
        },
        "primary_aggregate": aggregate,
        "excluded_sessions": exclusions.to_dict(orient="records"),
        "control_diagnostics": controls.to_dict(orient="records"),
    }
    source._atomic_write_text(output_dir / "SUMMARY.json", json.dumps(summary, indent=2) + "\n")
    source._atomic_write_text(output_dir / "SUMMARY.md", render_summary(summary, monthly))
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(args.data_root.resolve(), args.output_dir.resolve())
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
