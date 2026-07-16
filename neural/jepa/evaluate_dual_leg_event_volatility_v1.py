#!/usr/bin/env python3
"""Strict common-key, non-overlapping dual-leg event volatility replayer."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from neural.jepa import evaluate_directional_semantic_jepa_v1 as base


PREDECLARATION = (
    base.REPO_ROOT
    / "research_papers/JEPA/DUAL_LEG_EVENT_VOLATILITY_V1_PREDECLARATION.md"
)
DEFAULT_DATASET = Path(
    "tmp/event_option_dataset_execquote_causal1030_202201_202605_v1_physics/"
    "event_option_dataset.parquet"
)
EXPECTED_DATASET_SHA256 = (
    "11e26aaddd91fd441222d552e0362c1d4c2c4489a08d7a6de66479d6eb454fb1"
)
DEFAULT_OUTPUT = (
    base.REPO_ROOT / "research_papers/JEPA/results/_diagnostics/"
    "dual_leg_event_volatility_v1_development_2025"
)
TICKERS = ("QQQ", "SPXW", "SPY")
REPORT_TICKER = {"QQQ": "QQQ", "SPXW": "SPX", "SPY": "SPY"}
DELTA_BUCKET = {"QQQ": "d35", "SPXW": "d25", "SPY": "d35"}
ENTRY_START_MINUTE = 630
ENTRY_END_MINUTE = 870
MIN_HOLD_MINUTES = 30
MAX_HOLD_MINUTES = 180
RETURN_HAIRCUT = 0.002


def profit_factor(values: pd.Series) -> float:
    array = values.to_numpy(dtype=np.float64)
    profit = float(array[array > 0.0].sum())
    loss = float(-array[array < 0.0].sum())
    if loss == 0.0:
        return math.inf if profit > 0.0 else 0.0
    return profit / loss


def summarize(frame: pd.DataFrame) -> dict:
    return {
        "trades": int(len(frame)),
        "win_rate": float((frame["net_return"] > 0.0).mean()) if len(frame) else 0.0,
        "profit_factor": profit_factor(frame["net_return"]),
        "net_return_sum": float(frame["net_return"].sum()),
    }


def load_eligible_events(dataset: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    if base.sha256_file(dataset) != EXPECTED_DATASET_SHA256:
        raise AssertionError("dual-leg source dataset hash mismatch")
    fixed = [
        "ticker",
        "trade_date",
        "expiration",
        "dte_days",
        "expiry_mode",
        "timestamp",
        "time",
        "minute",
        "option_price_mode",
    ]
    dynamic = []
    for bucket in sorted(set(DELTA_BUCKET.values())):
        for right in ("call", "put"):
            dynamic.extend(
                (
                    f"{right}_{bucket}_available",
                    f"{right}_{bucket}_opt_exit_ret",
                    f"{right}_{bucket}_opt_exit_minutes",
                )
            )
    source = pd.read_parquet(dataset, columns=[*fixed, *dynamic])
    source["trade_date"] = (
        source["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    )
    source["timestamp"] = pd.to_datetime(source["timestamp"], errors="coerce")
    source = source.loc[
        source["ticker"].isin(TICKERS)
        & source["expiry_mode"].eq("zero_dte")
        & source["option_price_mode"].eq("executable_quote")
        & source["minute"].between(
            ENTRY_START_MINUTE, ENTRY_END_MINUTE, inclusive="both"
        )
    ].copy()
    frames = {}
    preintersection = {}
    for ticker in TICKERS:
        bucket = DELTA_BUCKET[ticker]
        frame = source.loc[source["ticker"].eq(ticker)].copy()
        call_return = f"call_{bucket}_opt_exit_ret"
        put_return = f"put_{bucket}_opt_exit_ret"
        call_exit = f"call_{bucket}_opt_exit_minutes"
        put_exit = f"put_{bucket}_opt_exit_minutes"
        mask = frame[f"call_{bucket}_available"].eq(1) & frame[
            f"put_{bucket}_available"
        ].eq(1)
        for column in (call_return, put_return, call_exit, put_exit):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
            mask &= np.isfinite(frame[column])
        mask &= frame[call_exit].between(MIN_HOLD_MINUTES, MAX_HOLD_MINUTES)
        mask &= frame[put_exit].between(MIN_HOLD_MINUTES, MAX_HOLD_MINUTES)
        frame = frame.loc[mask].copy()
        frame = frame.rename(
            columns={
                call_return: "call_return",
                put_return: "put_return",
                call_exit: "call_exit_minutes",
                put_exit: "put_exit_minutes",
            }
        )
        keys = ["trade_date", "timestamp"]
        if frame.duplicated(keys).any() or frame["timestamp"].isna().any():
            raise AssertionError(f"{ticker}: duplicate or invalid dual-leg event key")
        preintersection[ticker] = int(len(frame))
        frames[ticker] = frame
    common_keys = frames[TICKERS[0]][["trade_date", "timestamp"]]
    for ticker in TICKERS[1:]:
        common_keys = common_keys.merge(
            frames[ticker][["trade_date", "timestamp"]],
            on=["trade_date", "timestamp"],
            how="inner",
            validate="one_to_one",
        )
    common_keys = common_keys.drop_duplicates().sort_values(
        ["trade_date", "timestamp"], kind="stable"
    )
    if common_keys.empty:
        raise AssertionError("dual-leg exact common-key intersection is empty")
    for ticker in TICKERS:
        frames[ticker] = (
            frames[ticker]
            .merge(
                common_keys,
                on=["trade_date", "timestamp"],
                how="inner",
                validate="one_to_one",
            )
            .sort_values(["trade_date", "timestamp"], kind="stable")
        )
    audit = {
        "eligible_rows_before_intersection": preintersection,
        "common_event_keys": int(len(common_keys)),
        "common_dates": int(common_keys["trade_date"].nunique()),
    }
    return frames, audit


def run_scheduler(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    indexes = {
        ticker: frame.set_index(["trade_date", "timestamp"], drop=False)
        for ticker, frame in frames.items()
    }
    reference = frames[TICKERS[0]][["trade_date", "timestamp"]]
    rows = []
    for day, day_keys in reference.groupby("trade_date", sort=True):
        available_at: pd.Timestamp | None = None
        for key in day_keys.sort_values("timestamp", kind="stable").itertuples(
            index=False
        ):
            timestamp = pd.Timestamp(key.timestamp)
            if available_at is not None and timestamp < available_at:
                continue
            event_rows = {
                ticker: indexes[ticker].loc[(str(day), timestamp)] for ticker in TICKERS
            }
            global_hold = max(
                int(max(row["call_exit_minutes"], row["put_exit_minutes"]))
                for row in event_rows.values()
            )
            available_at = timestamp + pd.Timedelta(minutes=global_hold)
            for ticker, row in event_rows.items():
                gross = 0.5 * (float(row["call_return"]) + float(row["put_return"]))
                rows.append(
                    {
                        "ticker": REPORT_TICKER[ticker],
                        "source_ticker": ticker,
                        "trade_date": str(day),
                        "month": str(day)[:6],
                        "entry_timestamp": timestamp,
                        "call_exit_minutes": int(row["call_exit_minutes"]),
                        "put_exit_minutes": int(row["put_exit_minutes"]),
                        "global_portfolio_hold_minutes": global_hold,
                        "call_return": float(row["call_return"]),
                        "put_return": float(row["put_return"]),
                        "gross_return": gross,
                        "net_return": gross - RETURN_HAIRCUT,
                    }
                )
    trades = (
        pd.DataFrame(rows)
        .sort_values(["ticker", "entry_timestamp"], kind="stable")
        .reset_index(drop=True)
    )
    if trades.empty or not np.isfinite(trades["net_return"]).all():
        raise AssertionError("dual-leg scheduler produced no finite trades")
    counts = trades.groupby(["trade_date", "entry_timestamp"]).size()
    if not counts.eq(len(TICKERS)).all():
        raise AssertionError("dual-leg scheduler lost common-ticker parity")
    for ticker, group in trades.groupby("ticker"):
        previous_exit: pd.Timestamp | None = None
        for row in group.sort_values("entry_timestamp").itertuples(index=False):
            if previous_exit is not None and row.entry_timestamp < previous_exit:
                raise AssertionError(f"{ticker}: overlapping dual-leg positions")
            previous_exit = row.entry_timestamp + pd.Timedelta(
                minutes=row.global_portfolio_hold_minutes
            )
    return trades


def evaluate_2025(trades: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    months = [f"2025{month:02d}" for month in range(1, 13)]
    evaluation = trades.loc[trades["month"].isin(months)].copy()
    monthly_rows = []
    ticker_metrics = {}
    for ticker in sorted(evaluation["ticker"].unique()):
        ticker_trades = evaluation.loc[evaluation["ticker"].eq(ticker)]
        for month in months:
            monthly_rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    **summarize(ticker_trades.loc[ticker_trades["month"].eq(month)]),
                }
            )
        ticker_monthly = pd.DataFrame(
            [row for row in monthly_rows if row["ticker"] == ticker]
        )
        aggregate = summarize(ticker_trades)
        minimum = int(ticker_monthly["trades"].min())
        positive = int((ticker_monthly["net_return_sum"] > 0.0).sum())
        passed = (
            aggregate["win_rate"] > 0.45
            and aggregate["profit_factor"] > 1.20
            and minimum > 12
            and positive == len(months)
        )
        ticker_metrics[ticker] = {
            **aggregate,
            "min_month_trades": minimum,
            "positive_months": positive,
            "evaluated_months": len(months),
            "gate_pass": passed,
        }
    return pd.DataFrame(monthly_rows), {
        "ticker_metrics": ticker_metrics,
        "joint_gate_pass": all(item["gate_pass"] for item in ticker_metrics.values()),
    }


def run(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable dual-leg output exists: {output}")
    dataset = Path(args.dataset)
    frames, coverage = load_eligible_events(dataset)
    trades = run_scheduler(frames)
    monthly, gate = evaluate_2025(trades)
    metrics = {
        "schema": "dual_leg_event_volatility_v1_development_metrics",
        "status": "PASS_PRE2026_GATE"
        if gate["joint_gate_pass"]
        else "CLOSED_PRE2026_GATE",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {"evaluation_months": [f"2025{month:02d}" for month in range(1, 13)]},
        "coverage": coverage,
        "scheduler_trade_rows_all_years": int(len(trades)),
        "scheduler_decisions_all_years": int(len(trades) // len(TICKERS)),
        "execution": {
            "delta_bucket": DELTA_BUCKET,
            "entry_window_minutes": [ENTRY_START_MINUTE, ENTRY_END_MINUTE],
            "min_hold_minutes": MIN_HOLD_MINUTES,
            "max_hold_minutes": MAX_HOLD_MINUTES,
            "return_haircut": RETURN_HAIRCUT,
            "position_overlap_policy": "global_reject_while_any_leg_open",
        },
        **gate,
        "holdout_2026_used": False,
        "production_modified": False,
    }
    provenance = {
        "schema": "dual_leg_event_volatility_v1_provenance",
        "predeclaration_sha256": base.sha256_file(PREDECLARATION),
        "runner_sha256": base.sha256_file(__file__),
        "dataset_path": str(dataset.resolve()),
        "dataset_sha256": base.sha256_file(dataset),
        "source_label": "executable_quote_ask_to_bid",
        "new_dataset_created": False,
        "production_modified": False,
    }
    output.mkdir(parents=True, exist_ok=False)
    trades.to_parquet(output / "trade_ledger.parquet", index=False)
    monthly.to_csv(output / "monthly_metrics.csv", index=False)
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), flush=True)
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
