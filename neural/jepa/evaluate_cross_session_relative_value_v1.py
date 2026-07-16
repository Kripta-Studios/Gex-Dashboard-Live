#!/usr/bin/env python3
"""Frozen development ledger for CROSS_SESSION_RELATIVE_VALUE_V1."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
PREDECLARATION = (
    REPO_ROOT / "research_papers/JEPA/CROSS_SESSION_RELATIVE_VALUE_V1_PREDECLARATION.md"
)
DATA_GATE_CLARIFICATION = (
    REPO_ROOT / "research_papers/JEPA/CROSS_SESSION_RELATIVE_VALUE_V1_DATA_GATE_CLARIFICATION.md"
)
DEFAULT_DATA_ROOT = Path("D:/ThetaData/data_underlying_derived")
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/cross_session_relative_value_v1_development_202201_202312"
)

SOURCE_TICKERS = ("QQQ", "SPXW", "SPY")
START_DATE = "20220103"
DEVELOPMENT_END = "20231231"
DECISION_BAR_TIME = "10:34"
ENTRY_TIME = "10:36"
EXIT_TIME = "13:36"
HOLD_MINUTES = 180
COST_PER_LEG_BPS = 1.0
TOTAL_COST_BPS = 2.0

HALF_DAYS = frozenset(
    {
        "20221125",
        "20230703",
        "20231124",
        "20240703",
        "20241129",
        "20241224",
        "20250703",
        "20251128",
        "20251224",
    }
)
INVALID_TRADE_DAYS = frozenset({"20230605"})
KNOWN_ENVELOPE_EXCEPTIONS = {
    ("SPY", "20230605"): frozenset({"09:54", "09:55", "09:56"}),
}
REQUIRED_COLUMNS = (
    "symbol",
    "date",
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "tick_count",
)

MIN_PROFIT_FACTOR = 1.20
MIN_WIN_RATE = 0.45
MIN_TRADES_EXCLUSIVE = 12


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_date(value: object) -> str:
    digits = "".join(character for character in str(value) if character.isdigit())
    if len(digits) < 8:
        raise ValueError(f"invalid date: {value!r}")
    return digits[:8]


def discover_source_files(root: Path) -> pd.DataFrame:
    rows: list[dict] = []
    for ticker in SOURCE_TICKERS:
        for path in sorted((root / ticker).glob("*/*/*.parquet")):
            day = canonical_date(path.stem)
            if START_DATE <= day <= DEVELOPMENT_END:
                rows.append(
                    {
                        "ticker": ticker,
                        "trade_date": day,
                        "path": str(path.resolve()),
                        "size_bytes": int(path.stat().st_size),
                        "sha256": sha256_file(path),
                    }
                )
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise AssertionError("no development source files found")
    frame = frame.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    if frame.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("duplicate source ticker/date")
    expected_dates: set[str] | None = None
    for ticker in SOURCE_TICKERS:
        dates = set(frame.loc[frame["ticker"].eq(ticker), "trade_date"].astype(str))
        if expected_dates is None:
            expected_dates = dates
        elif dates != expected_dates:
            raise AssertionError(f"source session mismatch for {ticker}")
    if not expected_dates or max(expected_dates) > DEVELOPMENT_END:
        raise AssertionError("development inventory crossed the frozen cutoff")
    return frame


def _timestamp(day: str, clock: str) -> pd.Timestamp:
    return pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {clock}")


def validate_bar_frame(frame: pd.DataFrame, ticker: str, day: str) -> pd.DataFrame:
    missing = sorted(set(REQUIRED_COLUMNS).difference(frame.columns))
    if missing:
        raise KeyError(f"{ticker} {day}: missing columns {missing}")
    out = frame.loc[:, REQUIRED_COLUMNS].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    for column in ("open", "high", "low", "close", "tick_count"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if out.empty or out["timestamp"].isna().any() or out["timestamp"].duplicated().any():
        raise AssertionError(f"{ticker} {day}: invalid timestamp grid")
    if not out["timestamp"].dt.strftime("%Y%m%d").eq(day).all():
        raise AssertionError(f"{ticker} {day}: timestamp date mismatch")
    if not out["date"].map(canonical_date).eq(day).all():
        raise AssertionError(f"{ticker} {day}: metadata date mismatch")
    if not out["symbol"].astype(str).str.upper().eq(ticker).all():
        raise AssertionError(f"{ticker} {day}: symbol mismatch")
    numeric = out[["open", "high", "low", "close", "tick_count"]]
    if not np.isfinite(numeric.to_numpy(dtype=np.float64)).all():
        raise AssertionError(f"{ticker} {day}: non-finite bars")
    envelope = (
        (out["open"] > 0.0)
        & (out["close"] > 0.0)
        & (out["low"] <= out[["open", "close"]].min(axis=1) + 1e-9)
        & (out["high"] + 1e-9 >= out[["open", "close"]].max(axis=1))
        & (out["high"] >= out["low"])
        & (out["tick_count"] >= 0.0)
    )
    if not envelope.all():
        invalid_clocks = frozenset(out.loc[~envelope, "timestamp"].dt.strftime("%H:%M"))
        expected_exceptions = KNOWN_ENVELOPE_EXCEPTIONS.get((ticker, day), frozenset())
        if invalid_clocks != expected_exceptions:
            raise AssertionError(
                f"{ticker} {day}: OHLC envelope failure at {sorted(invalid_clocks)}"
            )
    out = out.sort_values("timestamp", kind="stable").set_index("timestamp", drop=False)
    expected = pd.date_range(_timestamp(day, "09:30"), _timestamp(day, "16:00"), freq="min")
    if not out.index.equals(expected):
        raise AssertionError(f"{ticker} {day}: grid is not exact 09:30-16:00")
    required_times = {DECISION_BAR_TIME, ENTRY_TIME, EXIT_TIME, "09:30", "13:00", "16:00"}
    observed = set(out["timestamp"].dt.strftime("%H:%M"))
    if not required_times.issubset(observed):
        raise AssertionError(f"{ticker} {day}: missing required clocks")
    return out


def load_sessions(inventory: pd.DataFrame) -> dict[str, dict[str, pd.DataFrame]]:
    sessions: dict[str, dict[str, pd.DataFrame]] = {}
    for row in inventory.itertuples(index=False):
        ticker = str(row.ticker)
        day = str(row.trade_date)
        raw = pd.read_parquet(str(row.path))
        sessions.setdefault(day, {})[ticker] = validate_bar_frame(raw, ticker, day)
    for day, frames in sessions.items():
        if set(frames) != set(SOURCE_TICKERS):
            raise AssertionError(f"{day}: incomplete cross-market session")
        reference = frames[SOURCE_TICKERS[0]].index
        for ticker in SOURCE_TICKERS[1:]:
            if not frames[ticker].index.equals(reference):
                raise AssertionError(f"{day}: cross-market timestamp mismatch")
    return dict(sorted(sessions.items()))


def log_return_bps(end: float, start: float) -> float:
    if not (np.isfinite(end) and np.isfinite(start) and end > 0.0 and start > 0.0):
        raise ValueError("prices must be finite and positive")
    return float(math.log(end / start) * 10_000.0)


def session_close(frame: pd.DataFrame, day: str) -> float:
    close_clock = "13:00" if day in HALF_DAYS else "16:00"
    return float(frame.loc[_timestamp(day, close_clock), "close"])


def build_trade_row(
    day: str,
    current: dict[str, pd.DataFrame],
    previous_day: str,
    previous: dict[str, pd.DataFrame],
) -> dict:
    shocks: dict[str, float] = {}
    for ticker in SOURCE_TICKERS:
        prior_close = session_close(previous[ticker], previous_day)
        decision_close = float(current[ticker].loc[_timestamp(day, DECISION_BAR_TIME), "close"])
        shocks[ticker] = log_return_bps(decision_close, prior_close)

    market_anchor = 0.5 * (shocks["SPY"] + shocks["SPXW"])
    relative_shock = shocks["QQQ"] - market_anchor
    if relative_shock > 0.0:
        qqq_position, spy_position, action = -1, 1, "SHORT_QQQ_LONG_SPY"
    elif relative_shock < 0.0:
        qqq_position, spy_position, action = 1, -1, "LONG_QQQ_SHORT_SPY"
    else:
        qqq_position, spy_position, action = 0, 0, "NO_TRADE_ZERO_SHOCK"

    entry_timestamp = _timestamp(day, ENTRY_TIME)
    exit_timestamp = _timestamp(day, EXIT_TIME)
    qqq_return = log_return_bps(
        float(current["QQQ"].loc[exit_timestamp, "open"]),
        float(current["QQQ"].loc[entry_timestamp, "open"]),
    )
    spy_return = log_return_bps(
        float(current["SPY"].loc[exit_timestamp, "open"]),
        float(current["SPY"].loc[entry_timestamp, "open"]),
    )
    gross = float(qqq_position * qqq_return + spy_position * spy_return)
    executed = bool(qqq_position)
    return {
        "trade_date": day,
        "month": day[:6],
        "previous_trade_date": previous_day,
        "decision_bar_time": DECISION_BAR_TIME,
        "entry_time": ENTRY_TIME,
        "exit_time": EXIT_TIME,
        "hold_minutes": HOLD_MINUTES,
        "qqq_cross_session_bps": shocks["QQQ"],
        "spxw_cross_session_bps": shocks["SPXW"],
        "spy_cross_session_bps": shocks["SPY"],
        "market_anchor_bps": market_anchor,
        "relative_shock_bps": relative_shock,
        "action": action,
        "trade_executed": executed,
        "qqq_position": qqq_position,
        "spy_position": spy_position,
        "qqq_leg_return_bps": qqq_return,
        "spy_leg_return_bps": spy_return,
        "gross_bps": gross,
        "cost_bps": TOTAL_COST_BPS if executed else 0.0,
        "net_bps": gross - TOTAL_COST_BPS if executed else 0.0,
        "momentum_control_net_bps": -gross - TOTAL_COST_BPS if executed else 0.0,
        "fixed_long_qqq_short_spy_net_bps": qqq_return - spy_return - TOTAL_COST_BPS,
    }


def build_development_ledger(
    sessions: dict[str, dict[str, pd.DataFrame]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(sessions)
    rows: list[dict] = []
    excluded: list[dict] = []
    for index, day in enumerate(dates):
        if index == 0:
            excluded.append({"trade_date": day, "reason": "NO_PRIOR_SESSION_IN_SCOPE"})
            continue
        if day in HALF_DAYS:
            excluded.append({"trade_date": day, "reason": "CURRENT_HALF_DAY"})
            continue
        if day in INVALID_TRADE_DAYS:
            excluded.append({"trade_date": day, "reason": "KNOWN_INVALID_SIGNAL_WINDOW"})
            continue
        previous_day = dates[index - 1]
        rows.append(build_trade_row(day, sessions[day], previous_day, sessions[previous_day]))
    ledger = pd.DataFrame(rows).sort_values("trade_date", kind="stable").reset_index(drop=True)
    exclusions = pd.DataFrame(excluded).sort_values("trade_date", kind="stable").reset_index(drop=True)
    if ledger.empty or ledger["trade_date"].duplicated().any():
        raise AssertionError("invalid development ledger")
    if ledger["trade_date"].max() > DEVELOPMENT_END:
        raise AssertionError("ledger crossed development cutoff")
    if not ledger["hold_minutes"].eq(HOLD_MINUTES).all():
        raise AssertionError("hold contract mismatch")
    return ledger, exclusions


def profit_factor(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    gross_profit = float(array[array > 0.0].sum())
    gross_loss = float(-array[array < 0.0].sum())
    if gross_loss == 0.0:
        return 1.0e12 if gross_profit > 0.0 else 0.0
    return gross_profit / gross_loss


def summarize_monthly(ledger: pd.DataFrame) -> pd.DataFrame:
    executed = ledger.loc[ledger["trade_executed"]].copy()
    months = pd.period_range("2022-01", "2023-12", freq="M").astype(str).str.replace("-", "")
    rows: list[dict] = []
    for month in months:
        frame = executed.loc[executed["month"].eq(month)]
        net = frame["net_bps"].to_numpy(dtype=np.float64)
        trades = int(len(frame))
        pf = profit_factor(net)
        wr = float(np.mean(net > 0.0)) if trades else 0.0
        pnl = float(net.sum())
        rows.append(
            {
                "month": month,
                "trades": trades,
                "win_rate": wr,
                "profit_factor": pf,
                "net_bps": pnl,
                "frequency_pass": trades > MIN_TRADES_EXCLUSIVE,
                "win_rate_pass": wr > MIN_WIN_RATE,
                "profit_factor_pass": pf > MIN_PROFIT_FACTOR,
                "pnl_pass": pnl > 0.0,
            }
        )
    out = pd.DataFrame(rows)
    out["month_pass"] = out[
        ["frequency_pass", "win_rate_pass", "profit_factor_pass", "pnl_pass"]
    ].all(axis=1)
    return out


def summarize_control(ledger: pd.DataFrame, column: str) -> dict:
    frame = ledger.loc[ledger["trade_executed"]]
    values = frame[column].to_numpy(dtype=np.float64)
    return {
        "control": column,
        "trades": int(len(values)),
        "win_rate": float(np.mean(values > 0.0)) if len(values) else 0.0,
        "profit_factor": profit_factor(values),
        "net_bps": float(values.sum()),
    }


def dataframe_digest(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _atomic_write_csv(path: Path, frame: pd.DataFrame) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False, lineterminator="\n")
    os.replace(temporary, path)


def render_summary(summary: dict, monthly: pd.DataFrame) -> str:
    aggregate = summary["primary_aggregate"]
    lines = [
        "# CROSS_SESSION_RELATIVE_VALUE_V1 development",
        "",
        f"Status: `{summary['status']}`",
        "",
        (
            f"Primary mean-reversion: {aggregate['trades']} trades, WR "
            f"{aggregate['win_rate']:.3%}, PF {aggregate['profit_factor']:.6f}, "
            f"PnL {aggregate['net_bps']:+.3f} bps."
        ),
        "",
        f"Months passing all gates: {int(monthly['month_pass'].sum())}/{len(monthly)}.",
        "",
        "2024-2026 and production were not opened.",
        "",
    ]
    return "\n".join(lines)


def run(data_root: Path, output_dir: Path) -> dict:
    for protocol_path in (PREDECLARATION, DATA_GATE_CLARIFICATION):
        if not protocol_path.is_file():
            raise FileNotFoundError(protocol_path)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    inventory = discover_source_files(data_root)
    sessions = load_sessions(inventory)
    ledger, exclusions = build_development_ledger(sessions)
    monthly = summarize_monthly(ledger)
    executed = ledger.loc[ledger["trade_executed"]]
    net = executed["net_bps"].to_numpy(dtype=np.float64)
    aggregate = {
        "trades": int(len(executed)),
        "win_rate": float(np.mean(net > 0.0)) if len(net) else 0.0,
        "profit_factor": profit_factor(net),
        "net_bps": float(net.sum()),
        "min_month_trades": int(monthly["trades"].min()),
        "positive_months": int((monthly["net_bps"] > 0.0).sum()),
        "months_passing": int(monthly["month_pass"].sum()),
    }
    development_pass = bool(monthly["month_pass"].all())
    controls = pd.DataFrame(
        [
            summarize_control(ledger, "momentum_control_net_bps"),
            summarize_control(ledger, "fixed_long_qqq_short_spy_net_bps"),
        ]
    )

    inventory_path = output_dir / "source_inventory.csv"
    ledger_path = output_dir / "trades.csv"
    exclusions_path = output_dir / "excluded_sessions.csv"
    monthly_path = output_dir / "monthly_metrics.csv"
    controls_path = output_dir / "controls_summary.csv"
    _atomic_write_csv(inventory_path, inventory)
    _atomic_write_csv(ledger_path, ledger)
    _atomic_write_csv(exclusions_path, exclusions)
    _atomic_write_csv(monthly_path, monthly)
    _atomic_write_csv(controls_path, controls)

    summary = {
        "schema_version": "cross_session_relative_value_v1.development.v1",
        "status": (
            "PASS_DEVELOPMENT_GATE_OUTER_NOT_OPENED"
            if development_pass
            else "FAILED_ECONOMIC_DEVELOPMENT"
        ),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "development_202201_202312",
        "development_pass": development_pass,
        "outer_2024_2025_opened": False,
        "holdout_2026_opened": False,
        "production_changed": False,
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "data_gate_clarification_sha256": sha256_file(DATA_GATE_CLARIFICATION),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "source_inventory_sha256": dataframe_digest(inventory),
        "trades_sha256": dataframe_digest(ledger),
        "monthly_sha256": dataframe_digest(monthly),
        "controls_sha256": dataframe_digest(controls),
        "source_sessions_per_ticker": {
            ticker: int(inventory["ticker"].eq(ticker).sum()) for ticker in SOURCE_TICKERS
        },
        "trade_clock": {
            "decision_bar_time": DECISION_BAR_TIME,
            "entry_time": ENTRY_TIME,
            "exit_time": EXIT_TIME,
            "hold_minutes": HOLD_MINUTES,
            "cost_per_leg_bps": COST_PER_LEG_BPS,
            "total_cost_bps": TOTAL_COST_BPS,
        },
        "gates": {
            "profit_factor_strictly_greater_than": MIN_PROFIT_FACTOR,
            "win_rate_strictly_greater_than": MIN_WIN_RATE,
            "trades_per_month_strictly_greater_than": MIN_TRADES_EXCLUSIVE,
            "monthly_net_bps_strictly_greater_than": 0.0,
        },
        "primary_aggregate": aggregate,
        "excluded_sessions": exclusions.to_dict(orient="records"),
        "control_diagnostics": controls.to_dict(orient="records"),
    }
    _atomic_write_text(output_dir / "SUMMARY.json", json.dumps(summary, indent=2) + "\n")
    _atomic_write_text(output_dir / "SUMMARY.md", render_summary(summary, monthly))
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
