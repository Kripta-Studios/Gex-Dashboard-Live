#!/usr/bin/env python3
"""Evaluate the frozen monthly-orientation V3 on development year 2024."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa.build_calendar_risk_reversal_pressure_v1 import (  # noqa: E402
    canonical_date,
    tracked_clean,
)


PROJECT_ROOT = SCRIPT_REPO_ROOT
TICKERS = ("QQQ", "SPXW", "SPY")
SENSOR_MAP = {"QQQ": "QQQ", "SPXW": "SPY", "SPY": "SPY"}
ORIENTATION_THRESHOLD = 0.50
COSTS_BPS = (1.0, 2.0, 3.0)
INCREMENTAL_MIN_PF = 1.0
OBJECTIVE_MIN_PF = 1.20
MIN_WIN_RATE = 0.45
MIN_MONTH_TRADES_EXCLUSIVE = 12
DEVELOPMENT_YEAR = "2024"

PREDECLARATION = PROJECT_ROOT / (
    "research_papers/JEPA/"
    "CROSS_VENUE_CALENDAR_RR_LEADER_V3_MONTHLY_ORIENTATION_PREDECLARATION.md"
)
RESULT_2023 = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "calendar_risk_reversal_pressure_v1_development_202301_202312_v1"
)
RESULT_2024 = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v1_outer_2024_v1"
)
INPUTS = {
    RESULT_2023 / "trades.csv": (
        "9c5178045e4172e6bfaf6d7bf30eb07a6ae68ff66a3bb8b738965de1e0d0fa66"
    ),
    RESULT_2024 / "trades.csv": (
        "d989f586749738b75bb3c62c69d189d0e6e29b3106d060a1332c956af2917aa4"
    ),
}
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v3_development_2024_v1"
)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_digest(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def current_git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def verify_inputs() -> None:
    tracked_clean(Path(__file__).resolve(), "V3 evaluator")
    tracked_clean(PREDECLARATION, "V3 predeclaration")
    for path, expected in INPUTS.items():
        if not path.is_file() or sha256_file(path) != expected:
            raise AssertionError(f"V3 frozen input changed: {path}")


def _canonical_target_rows(frame: pd.DataFrame, year: str) -> pd.DataFrame:
    required = {"ticker", "trade_date", "underlying_return_bps"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError(f"V3 ledger lacks fields: {missing}")
    output = frame.copy()
    output["ticker"] = output["ticker"].astype(str).str.upper().str.strip()
    output["trade_date"] = output["trade_date"].map(canonical_date)
    output["month"] = output["trade_date"].str[:6]
    output["underlying_return_bps"] = pd.to_numeric(
        output["underlying_return_bps"], errors="coerce"
    )
    if (
        output.empty
        or output.duplicated(["ticker", "trade_date"]).any()
        or set(output["ticker"]) != set(TICKERS)
        or not output["trade_date"].str.startswith(year).all()
        or not np.isfinite(output["underlying_return_bps"].to_numpy()).all()
    ):
        raise AssertionError(f"V3 {year} ledger identity failed")
    return output


def load_2023_mapped_history() -> pd.DataFrame:
    raw = pd.read_csv(
        RESULT_2023 / "trades.csv", dtype={"trade_date": str, "month": str}
    )
    if "calendar_rr_pressure" not in raw.columns:
        raise KeyError("V3 2023 ledger lacks calendar_rr_pressure")
    targets = _canonical_target_rows(raw, "2023")[
        ["ticker", "trade_date", "month", "underlying_return_bps"]
    ].copy()
    sensors = raw[["ticker", "trade_date", "calendar_rr_pressure"]].copy()
    sensors["ticker"] = sensors["ticker"].astype(str).str.upper().str.strip()
    sensors["trade_date"] = sensors["trade_date"].map(canonical_date)
    sensors["calendar_rr_pressure"] = pd.to_numeric(
        sensors["calendar_rr_pressure"], errors="coerce"
    )
    sensors = sensors.rename(
        columns={"ticker": "sensor_ticker", "calendar_rr_pressure": "signal_pressure"}
    )
    targets["sensor_ticker"] = targets["ticker"].map(SENSOR_MAP)
    output = targets.merge(
        sensors,
        on=["sensor_ticker", "trade_date"],
        how="left",
        validate="many_to_one",
    )
    if output["signal_pressure"].isna().any():
        raise AssertionError("V3 2023 exact-date sensor mapping is incomplete")
    zero_keys = frozenset(
        output.loc[output["signal_pressure"].eq(0.0), "ticker"].astype(str)
        + "|"
        + output.loc[output["signal_pressure"].eq(0.0), "trade_date"].astype(str)
    )
    if zero_keys != frozenset({"QQQ|20231116", "QQQ|20231215"}):
        raise AssertionError(f"V3 2023 zero-pressure keys changed: {sorted(zero_keys)}")
    output["base_side"] = np.sign(output["signal_pressure"]).astype(np.int64)
    output["trade_executed"] = output["base_side"].ne(0)
    output["base_gross_bps"] = (
        output["base_side"] * output["underlying_return_bps"]
    )
    output["direct_win"] = output["base_gross_bps"].gt(0.0)
    return output


def load_2024_history() -> pd.DataFrame:
    raw = pd.read_csv(
        RESULT_2024 / "trades.csv", dtype={"trade_date": str, "month": str}
    )
    if "signal_pressure" not in raw.columns:
        raise KeyError("V3 2024 ledger lacks signal_pressure")
    output = _canonical_target_rows(raw, "2024")
    output["sensor_ticker"] = output["ticker"].map(SENSOR_MAP)
    output["signal_pressure"] = pd.to_numeric(
        output["signal_pressure"], errors="coerce"
    )
    if (
        output["signal_pressure"].isna().any()
        or output["signal_pressure"].eq(0.0).any()
        or len(output) != 743
    ):
        raise AssertionError("V3 2024 signal identity failed")
    output["base_side"] = np.sign(output["signal_pressure"]).astype(np.int64)
    output["trade_executed"] = True
    output["base_gross_bps"] = (
        output["base_side"] * output["underlying_return_bps"]
    )
    output["direct_win"] = output["base_gross_bps"].gt(0.0)
    if "gross_bps" in raw.columns and not np.allclose(
        output["base_gross_bps"],
        pd.to_numeric(raw["gross_bps"], errors="raise"),
        rtol=0.0,
        atol=1e-12,
    ):
        raise AssertionError("V3 does not reproduce V1 direct gross")
    return output


def orientation_from_hit_rate(hit_rate: float) -> int:
    if not np.isfinite(hit_rate) or not 0.0 <= hit_rate <= 1.0:
        raise ValueError("V3 direct hit rate must be finite in [0,1]")
    return 1 if hit_rate >= ORIENTATION_THRESHOLD else -1


def build_monthly_states(history: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    months = pd.period_range("2024-01", "2024-12", freq="M").strftime("%Y%m")
    for month in months:
        prior = (pd.Period(month, freq="M") - 1).strftime("%Y%m")
        selected = history.loc[
            history["month"].eq(prior) & history["trade_executed"]
        ].copy()
        counts = selected.groupby("ticker", observed=True).size().to_dict()
        if (
            set(counts) != set(TICKERS)
            or any(int(counts[ticker]) <= MIN_MONTH_TRADES_EXCLUSIVE for ticker in TICKERS)
        ):
            raise AssertionError(f"V3 prior-month frequency failed: {prior}/{counts}")
        hit_rate = float(selected["direct_win"].mean())
        orientation = orientation_from_hit_rate(hit_rate)
        rows.append(
            {
                "month": month,
                "prior_month": prior,
                "prior_trades_QQQ": int(counts["QQQ"]),
                "prior_trades_SPXW": int(counts["SPXW"]),
                "prior_trades_SPY": int(counts["SPY"]),
                "prior_pooled_trades": int(len(selected)),
                "prior_direct_hits": int(selected["direct_win"].sum()),
                "prior_direct_hit_rate": hit_rate,
                "orientation": orientation,
                "orientation_name": "DIRECT" if orientation == 1 else "INVERSE",
            }
        )
    return pd.DataFrame(rows)


def build_ledger(history_2024: pd.DataFrame, states: pd.DataFrame) -> pd.DataFrame:
    output = history_2024.merge(
        states[["month", "prior_month", "prior_direct_hit_rate", "orientation"]],
        on="month",
        how="left",
        validate="many_to_one",
    )
    if output[["prior_month", "orientation"]].isna().any().any():
        raise AssertionError("V3 monthly state join failed")
    output["side"] = output["base_side"] * output["orientation"].astype(np.int64)
    output["gross_bps"] = output["side"] * output["underlying_return_bps"]
    for cost in COSTS_BPS:
        output[f"net_bps_{int(cost)}bp"] = output["gross_bps"] - cost
    output["net_bps"] = output["net_bps_1bp"]
    columns = [
        "ticker",
        "trade_date",
        "month",
        "sensor_ticker",
        "signal_pressure",
        "base_side",
        "prior_month",
        "prior_direct_hit_rate",
        "orientation",
        "side",
        "underlying_return_bps",
        "base_gross_bps",
        "gross_bps",
        "net_bps_1bp",
        "net_bps_2bp",
        "net_bps_3bp",
        "net_bps",
    ]
    return output[columns].sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)


def profit_factor(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    gains = float(array[array > 0.0].sum())
    losses = float(-array[array < 0.0].sum())
    if losses == 0.0:
        return 1.0e12 if gains > 0.0 else 0.0
    return gains / losses


def summarize_monthly(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    months = pd.period_range("2024-01", "2024-12", freq="M").strftime("%Y%m")
    for ticker in TICKERS:
        for month in months:
            selected = ledger.loc[
                ledger["ticker"].eq(ticker) & ledger["month"].eq(month)
            ]
            net = selected["net_bps"].to_numpy(dtype=float)
            rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "trades": int(len(net)),
                    "win_rate": float(np.mean(net > 0.0)),
                    "profit_factor": profit_factor(net),
                    "net_bps": float(net.sum()),
                    "frequency_pass": int(len(net)) > MIN_MONTH_TRADES_EXCLUSIVE,
                    "pnl_positive": bool(net.sum() > 0.0),
                }
            )
    return pd.DataFrame(rows)


def summarize_tickers(ledger: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        selected = ledger.loc[ledger["ticker"].eq(ticker)]
        cells = monthly.loc[monthly["ticker"].eq(ticker)]
        net = selected["net_bps"].to_numpy(dtype=float)
        pf = profit_factor(net)
        win_rate = float(np.mean(net > 0.0))
        pnl = float(net.sum())
        minimum = int(cells["trades"].min())
        positive = int(cells["pnl_positive"].sum())
        rows.append(
            {
                "ticker": ticker,
                "trades": int(len(net)),
                "win_rate": win_rate,
                "profit_factor": pf,
                "net_bps": pnl,
                "min_month_trades": minimum,
                "positive_months": positive,
                "incremental_gate_pass": bool(
                    pf > INCREMENTAL_MIN_PF
                    and win_rate > MIN_WIN_RATE
                    and pnl > 0.0
                    and minimum > MIN_MONTH_TRADES_EXCLUSIVE
                ),
                "objective_gate_pass": bool(
                    pf > OBJECTIVE_MIN_PF
                    and win_rate > MIN_WIN_RATE
                    and minimum > MIN_MONTH_TRADES_EXCLUSIVE
                    and positive == 12
                ),
            }
        )
    return pd.DataFrame(rows)


def summarize_sensitivity(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope in (*TICKERS, "POOLED"):
        selected = ledger if scope == "POOLED" else ledger.loc[ledger["ticker"].eq(scope)]
        for cost in COSTS_BPS:
            net = selected[f"net_bps_{int(cost)}bp"].to_numpy(dtype=float)
            rows.append(
                {
                    "scope": scope,
                    "cost_bps": cost,
                    "trades": int(len(net)),
                    "win_rate": float(np.mean(net > 0.0)),
                    "profit_factor": profit_factor(net),
                    "net_bps": float(net.sum()),
                }
            )
    return pd.DataFrame(rows)


def render_summary(summary: dict[str, Any], ticker_summary: pd.DataFrame) -> str:
    lines = [
        "# CROSS_VENUE_CALENDAR_RR_LEADER_V3 — development 2024",
        "",
        f"Status: `{summary['status']}`",
        "",
    ]
    for row in ticker_summary.itertuples(index=False):
        lines.append(
            f"- {row.ticker}: {row.trades} trades, WR {row.win_rate:.3%}, "
            f"PF {row.profit_factor:.6f}, PnL {row.net_bps:+.3f} bps, "
            f"positive months {row.positive_months}/12."
        )
    lines.extend(
        [
            "",
            f"Eligible to prepare 2025 freeze: `{summary['advance_to_2025_freeze']}`.",
            "2025, 2026 and production were not opened.",
            "",
        ]
    )
    return "\n".join(lines)


def run(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V3 output already exists: {output_dir}")
    verify_inputs()
    history_2023 = load_2023_mapped_history()
    history_2024 = load_2024_history()
    history = pd.concat([history_2023, history_2024], ignore_index=True)
    states = build_monthly_states(history)
    ledger = build_ledger(history_2024, states)
    monthly = summarize_monthly(ledger)
    ticker_summary = summarize_tickers(ledger, monthly)
    sensitivity = summarize_sensitivity(ledger)
    advance = bool(ticker_summary["incremental_gate_pass"].all())
    objective = bool(ticker_summary["objective_gate_pass"].all())
    status = (
        "PASS_DEVELOPMENT_OBJECTIVE_2025_NOT_FROZEN"
        if advance and objective
        else "PASS_DEVELOPMENT_INCREMENTAL_2025_NOT_FROZEN"
        if advance
        else "FAILED_DEVELOPMENT_2025_CLOSED"
    )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        states.to_csv(staging / "monthly_orientation_states.csv", index=False)
        ledger.to_csv(staging / "trades.csv", index=False)
        monthly.to_csv(staging / "monthly_metrics.csv", index=False)
        ticker_summary.to_csv(staging / "ticker_summary.csv", index=False)
        sensitivity.to_csv(staging / "cost_sensitivity.csv", index=False)
        output_names = (
            "monthly_orientation_states.csv",
            "trades.csv",
            "monthly_metrics.csv",
            "ticker_summary.csv",
            "cost_sensitivity.csv",
        )
        summary: dict[str, Any] = {
            "schema": "cross_venue_calendar_rr_leader_v3_development_2024_v1",
            "status": status,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "execution_commit": current_git_commit(),
            "predeclaration_sha256": sha256_file(PREDECLARATION),
            "evaluator_sha256": sha256_file(Path(__file__).resolve()),
            "input_sha256": {
                str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): expected
                for path, expected in INPUTS.items()
            },
            "mapping": SENSOR_MAP,
            "rule": {
                "state_source": "immediately_previous_calendar_month",
                "statistic": "pooled_physical_trade_direct_hit_rate",
                "threshold": ORIENTATION_THRESHOLD,
                "tie": "DIRECT",
                "zero_pressure": "NO_TRADE",
                "state_constant_within_month": True,
            },
            "economics": {
                "entry": "open_10:36:00",
                "exit": "open_13:36:00",
                "hold_minutes": 180,
                "primary_cost_bps": 1.0,
                "sensitivity_costs_bps": list(COSTS_BPS),
                "positions_per_ticker_day": 1,
                "overlap": False,
            },
            "development_year": DEVELOPMENT_YEAR,
            "history_rows_2023": int(len(history_2023)),
            "history_executed_rows_2023": int(history_2023["trade_executed"].sum()),
            "development_trades": int(len(ledger)),
            "orientation_states": states.to_dict(orient="records"),
            "per_ticker": ticker_summary.to_dict(orient="records"),
            "advance_to_2025_freeze": advance,
            "objective_gate_pass": objective,
            "outer_2025_opened": False,
            "holdout_2026_opened": False,
            "production_modified": False,
            "live_or_systemd_modified": False,
            "output_sha256": {
                name: sha256_file(staging / name) for name in output_names
            },
            "states_recomputed_sha256": dataframe_digest(states),
            "trades_recomputed_sha256": dataframe_digest(ledger),
            "monthly_recomputed_sha256": dataframe_digest(monthly),
            "ticker_summary_recomputed_sha256": dataframe_digest(ticker_summary),
            "cost_sensitivity_recomputed_sha256": dataframe_digest(sensitivity),
        }
        (staging / "SUMMARY.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "SUMMARY.md").write_text(
            render_summary(summary, ticker_summary), encoding="utf-8", newline="\n"
        )
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(args.output_dir.resolve())
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
