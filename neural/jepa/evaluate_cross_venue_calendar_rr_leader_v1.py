#!/usr/bin/env python3
"""Evaluate the frozen 2024 outer for CROSS_VENUE_CALENDAR_RR_LEADER_V1."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa.build_cross_venue_calendar_rr_leader_v1 import (  # noqa: E402
    HALF_DAYS as DATA_GATE_HALF_DAYS,
    SENSOR_MAP,
    TICKERS,
    canonical_date,
    sha256_file,
    tracked_clean,
)


PROJECT_ROOT = SCRIPT_REPO_ROOT
HALF_DAYS = DATA_GATE_HALF_DAYS
OUTER_YEAR = "2024"
OUTER_START = "20240101"
OUTER_END = "20241231"
ENTRY_TIME = "10:36:00"
EXIT_TIME = "13:36:00"
HOLD_MINUTES = 180
PRIMARY_COST_BPS = 1.0
COST_SENSITIVITY_BPS = (1.0, 2.0, 3.0)

INCREMENTAL_MIN_PROFIT_FACTOR = 1.0
FINAL_MIN_PROFIT_FACTOR = 1.20
MIN_WIN_RATE = 0.45
MIN_TRADES_EXCLUSIVE = 12

DATA_GATE_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v1_data_gate_202401_202512_v1r1"
)
DATA_GATE_FILES = (
    "manifest.json",
    "cross_venue_calendar_rr_features.parquet",
    "source_inventory.csv",
)
DEFAULT_FROZEN_MANIFEST = DATA_GATE_DIR.parent / (
    "cross_venue_calendar_rr_leader_v1_outer_2024_runner_frozen/manifest.json"
)
DEFAULT_OUTPUT = DATA_GATE_DIR.parent / (
    "cross_venue_calendar_rr_leader_v1_outer_2024_v1"
)

PREDECLARATION = Path(
    "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_LEADER_V1_PREDECLARATION.md"
)
DATA_GATE_CONTRACT = Path(
    "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_LEADER_V1_DATA_GATE_CONTRACT.md"
)
OUTER_CONTRACT = Path(
    "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_LEADER_V1_OUTER_2024_RUNNER_CONTRACT.md"
)
RUNNER_CODE_PATHS = (
    Path("neural/jepa/evaluate_cross_venue_calendar_rr_leader_v1.py"),
    Path("neural/jepa/freeze_cross_venue_calendar_rr_leader_v1_runner.py"),
    PREDECLARATION,
    DATA_GATE_CONTRACT,
    OUTER_CONTRACT,
)

POLICY = {
    "feature": "signal_pressure",
    "action": "sign(signal_pressure)",
    "sensor_map": SENSOR_MAP,
    "zero_action": "NO_TRADE",
    "decision_time": "after_10:35:00",
    "entry": "derived_underlying_open_10:36:00",
    "exit": "derived_underlying_open_13:36:00",
    "hold_minutes": HOLD_MINUTES,
    "primary_round_trip_cost_bps": PRIMARY_COST_BPS,
    "cost_sensitivity_bps": list(COST_SENSITIVITY_BPS),
    "positions_per_ticker_per_day": 1,
    "overlap_policy": "one_fixed_nonoverlapping_position_per_ticker_day",
}
INCREMENTAL_GATE_SPEC = {
    "profit_factor_strictly_greater_than": INCREMENTAL_MIN_PROFIT_FACTOR,
    "win_rate_strictly_greater_than": MIN_WIN_RATE,
    "aggregate_net_bps_strictly_greater_than": 0.0,
    "trades_per_month_strictly_greater_than": MIN_TRADES_EXCLUSIVE,
    "all_tickers_required": True,
}
PROMOTION_GATE_SPEC = {
    "profit_factor_strictly_greater_than": FINAL_MIN_PROFIT_FACTOR,
    "win_rate_strictly_greater_than": MIN_WIN_RATE,
    "trades_per_month_strictly_greater_than": MIN_TRADES_EXCLUSIVE,
    "monthly_net_bps_strictly_greater_than": 0.0,
    "all_tickers_required": True,
}


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


def ordered_hash(values: Iterable[str]) -> str:
    payload = "".join(f"{value}\n" for value in sorted(values)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _as_bool(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    for column in columns:
        if not pd.api.types.is_bool_dtype(frame[column]):
            raise TypeError(f"data-gate boolean column is not strict bool: {column}")


def _validate_expected_hashes(
    data_gate_dir: Path, expected_hashes: dict[str, str] | None
) -> None:
    if expected_hashes is None:
        return
    if set(expected_hashes) != set(DATA_GATE_FILES):
        raise AssertionError("frozen data-gate hash closure changed")
    for name, expected in expected_hashes.items():
        path = data_gate_dir / name
        if not path.is_file() or sha256_file(path) != expected:
            raise AssertionError(f"frozen data-gate artifact changed: {path}")


def validate_data_gate(
    data_gate_dir: Path = DATA_GATE_DIR,
    *,
    expected_hashes: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    for name in DATA_GATE_FILES:
        if not (data_gate_dir / name).is_file():
            raise FileNotFoundError(data_gate_dir / name)
    _validate_expected_hashes(data_gate_dir, expected_hashes)
    manifest = json.loads((data_gate_dir / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("schema")
        != "cross_venue_calendar_rr_leader_v1_outcome_free_data_gate"
        or manifest.get("status") != "PASS_DATA_GATE"
        or manifest.get("data_gate", {}).get("passed") is not True
        or manifest.get("labels_built") is not False
        or manifest.get("outcome_accessed") is not False
        or manifest.get("underlying_outcome_clocks_read") is not False
        or manifest.get("outer_2024_opened") is not False
        or manifest.get("outer_2025_opened") is not False
        or manifest.get("holdout_2026_opened") is not False
        or manifest.get("production_modified") is not False
        or int(manifest.get("rows", -1)) != 1_506
        or int(manifest.get("scope", {}).get("captures", -1)) != 3_012
        or manifest.get("feature_contract", {}).get("mapping") != SENSOR_MAP
    ):
        raise AssertionError("authoritative cross-venue data gate is not a valid PASS")
    for name in DATA_GATE_FILES[1:]:
        expected = manifest.get("output_sha256", {}).get(name)
        if not isinstance(expected, str) or sha256_file(data_gate_dir / name) != expected:
            raise AssertionError(f"data-gate manifest output hash mismatch: {name}")

    features = pd.read_parquet(data_gate_dir / DATA_GATE_FILES[1]).copy()
    required = {
        "ticker",
        "trade_date",
        "year",
        "month",
        "calendar_half_day",
        "economic_clock_eligible",
        "local_feature_valid",
        "sensor_ticker",
        "sensor_local_feature_valid",
        "signal_pressure",
        "signal_action",
        "mapped_feature_valid",
        "economic_event_valid",
    }
    missing = sorted(required.difference(features.columns))
    if missing:
        raise KeyError(f"cross-venue feature schema mismatch: {missing}")
    _as_bool(
        features,
        (
            "calendar_half_day",
            "economic_clock_eligible",
            "local_feature_valid",
            "sensor_local_feature_valid",
            "mapped_feature_valid",
            "economic_event_valid",
        ),
    )
    features["ticker"] = features["ticker"].astype(str).str.upper().str.strip()
    features["sensor_ticker"] = (
        features["sensor_ticker"].astype(str).str.upper().str.strip()
    )
    features["trade_date"] = features["trade_date"].map(canonical_date)
    features["year"] = features["trade_date"].str[:4]
    features["month"] = features["trade_date"].str[:6]
    features["signal_pressure"] = pd.to_numeric(
        features["signal_pressure"], errors="coerce"
    )
    features["signal_action"] = pd.to_numeric(
        features["signal_action"], errors="raise"
    ).astype(np.int64)
    expected_sensor = features["ticker"].map(SENSOR_MAP)
    valid = features["mapped_feature_valid"]
    expected_action = np.sign(features.loc[valid, "signal_pressure"]).astype(np.int64)
    if (
        len(features) != 1_506
        or features.duplicated(["ticker", "trade_date"]).any()
        or set(features["ticker"]) != set(TICKERS)
        or not features["year"].isin(["2024", "2025"]).all()
        or not features["sensor_ticker"].eq(expected_sensor).all()
        or not np.isfinite(features.loc[valid, "signal_pressure"].to_numpy()).all()
        or not features.loc[valid, "signal_action"].eq(expected_action).all()
        or not features.loc[~valid, "signal_action"].eq(0).all()
        or int(features["local_feature_valid"].sum())
        != int(manifest.get("local_valid_rows", -1))
        or int(features["mapped_feature_valid"].sum())
        != int(manifest.get("mapped_valid_rows", -1))
        or int(features["economic_event_valid"].sum())
        != int(manifest.get("economic_event_rows", -1))
    ):
        raise AssertionError("cross-venue feature view violates frozen identity")
    outer = features.loc[
        features["year"].eq(OUTER_YEAR) & features["economic_event_valid"]
    ].copy()
    counts = outer.groupby(["ticker", "month"], observed=True).size()
    if (
        outer.empty
        or len(counts) != 36
        or int(counts.min()) <= MIN_TRADES_EXCLUSIVE
        or outer["calendar_half_day"].any()
        or not outer["trade_date"].between(OUTER_START, OUTER_END).all()
        or outer["signal_action"].eq(0).any()
    ):
        raise AssertionError("outer-2024 feature capacity violates frozen contract")

    inventory = pd.read_csv(
        data_gate_dir / DATA_GATE_FILES[2], dtype={"trade_date": str, "sha256": str}
    )
    inventory["ticker"] = inventory["ticker"].astype(str).str.upper().str.strip()
    inventory["trade_date"] = inventory["trade_date"].map(canonical_date)
    underlying = inventory.loc[inventory["kind"].astype(str).eq("underlying")].copy()
    if (
        len(inventory) != int(manifest.get("source_inventory_rows", -1))
        or len(underlying) != 1_506
        or underlying.duplicated(["ticker", "trade_date"]).any()
        or not underlying["trade_date"].str[:4].isin(["2024", "2025"]).all()
    ):
        raise AssertionError("data-gate underlying inventory contract mismatch")
    selected = outer[
        ["ticker", "trade_date", "signal_pressure", "signal_action", "sensor_ticker"]
    ].merge(
        underlying[["ticker", "trade_date", "path", "size_bytes", "sha256"]],
        on=["ticker", "trade_date"],
        how="left",
        validate="one_to_one",
    )
    if (
        len(selected) != len(outer)
        or selected[["path", "sha256"]].isna().any().any()
        or not selected["trade_date"].str.startswith(OUTER_YEAR).all()
    ):
        raise AssertionError("outer features/underlying inventory join mismatch")
    return (
        outer.sort_values(["ticker", "trade_date"], kind="stable").reset_index(
            drop=True
        ),
        selected.sort_values(["ticker", "trade_date"], kind="stable").reset_index(
            drop=True
        ),
        manifest,
    )


def action_from_pressure(pressure: float) -> int:
    if not np.isfinite(pressure):
        raise ValueError("signal pressure must be finite")
    return int(np.sign(pressure))


def log_return_bps(end: float, start: float) -> float:
    if not (np.isfinite(end) and np.isfinite(start) and end > 0.0 and start > 0.0):
        raise ValueError("prices must be finite and positive")
    return float(math.log(end / start) * 10_000.0)


def _timestamp_values(day: str, clock: str) -> list[str]:
    date = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    return [
        f"{date}T{clock}",
        f"{date}T{clock}.000",
        f"{date} {clock}",
        f"{date} {clock}.000",
    ]


def read_exact_return_opens(path: Path, ticker: str, trade_date: str) -> tuple[float, float]:
    required = ("symbol", "date", "timestamp", "open")
    schema = set(pq.read_schema(path).names)
    missing = sorted(set(required).difference(schema))
    if missing:
        raise KeyError(f"underlying source lacks fields {missing}: {path}")
    values = _timestamp_values(trade_date, ENTRY_TIME) + _timestamp_values(
        trade_date, EXIT_TIME
    )
    frame = pd.read_parquet(
        path,
        columns=list(required),
        filters=[("timestamp", "in", values)],
    ).copy()
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame["date"] = frame["date"].map(canonical_date)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame["open"] = pd.to_numeric(frame["open"], errors="coerce")
    expected = (
        pd.Timestamp(f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} {ENTRY_TIME}"),
        pd.Timestamp(f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} {EXIT_TIME}"),
    )
    if (
        len(frame) != 2
        or frame.isna().any().any()
        or not frame["symbol"].eq(ticker).all()
        or not frame["date"].eq(trade_date).all()
        or set(frame["timestamp"]) != set(expected)
        or frame["timestamp"].duplicated().any()
        or not np.isfinite(frame["open"].to_numpy(dtype=float)).all()
        or not frame["open"].gt(0.0).all()
    ):
        raise AssertionError(f"invalid exact return clocks: {path}")
    indexed = frame.set_index("timestamp")
    return float(indexed.loc[expected[0], "open"]), float(
        indexed.loc[expected[1], "open"]
    )


def make_trade_row(
    *,
    ticker: str,
    trade_date: str,
    sensor_ticker: str,
    pressure: float,
    frozen_action: int,
    entry_open: float,
    exit_open: float,
) -> dict[str, Any]:
    side = action_from_pressure(pressure)
    if side == 0 or side != frozen_action:
        raise AssertionError("frozen signal action does not match pressure sign")
    underlying_return = log_return_bps(exit_open, entry_open)
    gross = float(side * underlying_return)
    row: dict[str, Any] = {
        "ticker": ticker,
        "trade_date": trade_date,
        "month": trade_date[:6],
        "sensor_ticker": sensor_ticker,
        "decision_time": "10:35:00",
        "entry_time": ENTRY_TIME,
        "exit_time": EXIT_TIME,
        "hold_minutes": HOLD_MINUTES,
        "signal_pressure": float(pressure),
        "side": side,
        "entry_open": float(entry_open),
        "exit_open": float(exit_open),
        "underlying_return_bps": underlying_return,
        "gross_bps": gross,
    }
    for cost in COST_SENSITIVITY_BPS:
        row[f"net_bps_{int(cost)}bp"] = gross - cost
    row["net_bps"] = row["net_bps_1bp"]
    return row


def build_ledger(features: pd.DataFrame, inventory: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_map = features.set_index(["ticker", "trade_date"])
    if not feature_map.index.is_unique:
        raise AssertionError("outer feature keys are not unique")
    rows: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for record in inventory.itertuples(index=False):
        path = Path(str(record.path))
        if not path.is_file() or path.stat().st_size != int(record.size_bytes):
            raise AssertionError(f"underlying source missing or size changed: {path}")
        actual_hash = sha256_file(path)
        if actual_hash != str(record.sha256):
            raise AssertionError(f"underlying source hash changed: {path}")
        ticker = str(record.ticker)
        day = str(record.trade_date)
        feature = feature_map.loc[(ticker, day)]
        entry_open, exit_open = read_exact_return_opens(path, ticker, day)
        rows.append(
            make_trade_row(
                ticker=ticker,
                trade_date=day,
                sensor_ticker=str(feature["sensor_ticker"]),
                pressure=float(feature["signal_pressure"]),
                frozen_action=int(feature["signal_action"]),
                entry_open=entry_open,
                exit_open=exit_open,
            )
        )
        audits.append(
            {
                "ticker": ticker,
                "trade_date": day,
                "source_path": str(path),
                "source_sha256": actual_hash,
                "source_size_bytes": int(path.stat().st_size),
                "rows_read": 2,
                "entry_time": ENTRY_TIME,
                "exit_time": EXIT_TIME,
            }
        )
    ledger = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    source_audit = pd.DataFrame(audits).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(ledger) != len(features)
        or ledger.duplicated(["ticker", "trade_date"]).any()
        or not ledger["trade_date"].between(OUTER_START, OUTER_END).all()
        or not ledger["hold_minutes"].eq(HOLD_MINUTES).all()
        or not ledger["side"].isin([-1, 1]).all()
    ):
        raise AssertionError("outer ledger violates frozen scope/scheduler")
    return ledger, source_audit


def profit_factor(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    gross_profit = float(array[array > 0.0].sum())
    gross_loss = float(-array[array < 0.0].sum())
    if gross_loss == 0.0:
        return 1.0e12 if gross_profit > 0.0 else 0.0
    return gross_profit / gross_loss


def summarize_monthly(ledger: pd.DataFrame) -> pd.DataFrame:
    months = pd.period_range("2024-01", "2024-12", freq="M").strftime("%Y%m")
    rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        ticker_rows = ledger.loc[ledger["ticker"].eq(ticker)]
        for month in months:
            selected = ticker_rows.loc[ticker_rows["month"].eq(month)]
            net = selected["net_bps"].to_numpy(dtype=np.float64)
            trades = int(len(selected))
            rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "trades": trades,
                    "win_rate": float(np.mean(net > 0.0)) if trades else 0.0,
                    "profit_factor": profit_factor(net),
                    "net_bps": float(net.sum()),
                    "frequency_pass": trades > MIN_TRADES_EXCLUSIVE,
                    "pnl_positive": bool(net.sum() > 0.0),
                }
            )
    output = pd.DataFrame(rows)
    if len(output) != 36:
        raise AssertionError("outer monthly summary must contain 36 cells")
    return output


def summarize_tickers(ledger: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        selected = ledger.loc[ledger["ticker"].eq(ticker)]
        net = selected["net_bps"].to_numpy(dtype=np.float64)
        cells = monthly.loc[monthly["ticker"].eq(ticker)]
        trades = int(len(selected))
        win_rate = float(np.mean(net > 0.0)) if trades else 0.0
        pf = profit_factor(net)
        pnl = float(net.sum())
        minimum = int(cells["trades"].min())
        positive_months = int(cells["pnl_positive"].sum())
        incremental_pass = bool(
            pf > INCREMENTAL_MIN_PROFIT_FACTOR
            and win_rate > MIN_WIN_RATE
            and pnl > 0.0
            and minimum > MIN_TRADES_EXCLUSIVE
        )
        promotion_pass = bool(
            pf > FINAL_MIN_PROFIT_FACTOR
            and win_rate > MIN_WIN_RATE
            and minimum > MIN_TRADES_EXCLUSIVE
            and positive_months == 12
        )
        rows.append(
            {
                "ticker": ticker,
                "trades": trades,
                "win_rate": win_rate,
                "profit_factor": pf,
                "net_bps": pnl,
                "min_month_trades": minimum,
                "positive_months": positive_months,
                "incremental_gate_pass": incremental_pass,
                "promotion_gate_pass": promotion_pass,
            }
        )
    return pd.DataFrame(rows)


def summarize_cost_sensitivity(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope in (*TICKERS, "POOLED"):
        selected = ledger if scope == "POOLED" else ledger.loc[ledger["ticker"].eq(scope)]
        for cost in COST_SENSITIVITY_BPS:
            net = selected[f"net_bps_{int(cost)}bp"].to_numpy(dtype=np.float64)
            rows.append(
                {
                    "scope": scope,
                    "cost_bps": cost,
                    "trades": int(len(net)),
                    "win_rate": float(np.mean(net > 0.0)) if len(net) else 0.0,
                    "profit_factor": profit_factor(net),
                    "net_bps": float(net.sum()),
                }
            )
    return pd.DataFrame(rows)


def classify_status(advance_to_2025: bool, promotion_gate: bool, ticker_summary: pd.DataFrame) -> str:
    if advance_to_2025 and promotion_gate:
        return "PASS_OUTER_2024_PROMOTION_GATE_2025_NOT_OPENED"
    if advance_to_2025:
        return "PASS_OUTER_2024_INCREMENTAL_GATE_2025_NOT_OPENED"
    if bool(ticker_summary["profit_factor"].gt(1.0).all()):
        return "INCREMENTAL_PF_ONLY_OUTER_2024_CLOSED"
    if bool(ticker_summary["profit_factor"].gt(1.0).any()):
        return "PARTIAL_INCREMENTAL_EDGE_OUTER_2024_CLOSED"
    return "NO_AGGREGATE_EDGE_OUTER_2024_CLOSED"


def verify_frozen_manifest(path: Path) -> dict[str, Any]:
    tracked_clean(path, "frozen outer runner manifest")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("schema")
        != "cross_venue_calendar_rr_leader_v1_frozen_outer_2024_runner"
        or payload.get("status") != "PREEXECUTION_FROZEN"
        or payload.get("phase") != "outer_2024"
        or payload.get("policy") != POLICY
        or payload.get("incremental_gate_spec") != INCREMENTAL_GATE_SPEC
        or payload.get("promotion_gate_spec") != PROMOTION_GATE_SPEC
        or payload.get("outcome_accessed") is not False
        or payload.get("execution_started") is not False
        or payload.get("outer_2024_opened") is not False
        or payload.get("outer_2025_opened") is not False
        or payload.get("holdout_2026_opened") is not False
        or payload.get("production_modified") is not False
    ):
        raise AssertionError("frozen outer-2024 runner contract mismatch")
    code_hashes = payload.get("code_hashes", {})
    for relative in RUNNER_CODE_PATHS:
        path_now = PROJECT_ROOT / relative
        if code_hashes.get(relative.as_posix()) != sha256_file(path_now):
            raise AssertionError(f"frozen runner/protocol hash changed: {relative}")
    inputs = payload.get("data_gate_inputs", {})
    expected_hashes = {name: str(inputs.get(name, {}).get("sha256", "")) for name in DATA_GATE_FILES}
    _validate_expected_hashes(DATA_GATE_DIR, expected_hashes)
    frozen_commit = str(payload.get("runner_commit", ""))
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", frozen_commit, current_git_commit()],
        cwd=PROJECT_ROOT,
        check=False,
    ).returncode != 0:
        raise AssertionError("frozen runner commit is not an ancestor of current HEAD")
    return payload


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False, lineterminator="\n")


def render_summary(summary: dict[str, Any], ticker_summary: pd.DataFrame) -> str:
    lines = [
        "# CROSS_VENUE_CALENDAR_RR_LEADER_V1 — outer 2024",
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
            f"Advance to 2025: `{summary['advance_to_2025']}`.",
            f"Promotion gate on 2024: `{summary['promotion_gate_pass']}`.",
            "",
            "2025, 2026 and production were not opened.",
            "",
        ]
    )
    return "\n".join(lines)


def run(output_dir: Path, frozen_manifest_path: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    frozen = verify_frozen_manifest(frozen_manifest_path)
    expected_hashes = {
        name: str(frozen["data_gate_inputs"][name]["sha256"])
        for name in DATA_GATE_FILES
    }
    features, inventory, data_gate = validate_data_gate(
        DATA_GATE_DIR, expected_hashes=expected_hashes
    )
    event_ids = [f"{row.ticker}|{row.trade_date}" for row in features.itertuples()]
    if ordered_hash(event_ids) != frozen.get("event_id_sha256"):
        raise AssertionError("frozen outer event IDs changed")
    ledger, source_audit = build_ledger(features, inventory)
    monthly = summarize_monthly(ledger)
    ticker_summary = summarize_tickers(ledger, monthly)
    sensitivity = summarize_cost_sensitivity(ledger)
    advance_to_2025 = bool(ticker_summary["incremental_gate_pass"].all())
    promotion_gate = bool(ticker_summary["promotion_gate_pass"].all())
    status = classify_status(advance_to_2025, promotion_gate, ticker_summary)
    pooled = ledger["net_bps"].to_numpy(dtype=np.float64)
    summary: dict[str, Any] = {
        "schema": "cross_venue_calendar_rr_leader_v1_outer_2024_evaluation",
        "status": status,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "outer_2024",
        "outcome_accessed": True,
        "outer_2024_opened": True,
        "advance_to_2025": advance_to_2025,
        "promotion_gate_pass": promotion_gate,
        "outer_2025_opened": False,
        "holdout_2026_opened": False,
        "production_modified": False,
        "policy": POLICY,
        "incremental_gate_spec": INCREMENTAL_GATE_SPEC,
        "promotion_gate_spec": PROMOTION_GATE_SPEC,
        "frozen_manifest_sha256": sha256_file(frozen_manifest_path),
        "frozen_runner_commit": frozen["runner_commit"],
        "execution_commit": current_git_commit(),
        "data_gate_commit": data_gate["git_commit"],
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "event_id_sha256": ordered_hash(event_ids),
        "source_inventory_sha256": dataframe_digest(inventory),
        "source_audit_sha256": dataframe_digest(source_audit),
        "trades_sha256": dataframe_digest(ledger),
        "monthly_sha256": dataframe_digest(monthly),
        "ticker_summary_sha256": dataframe_digest(ticker_summary),
        "cost_sensitivity_sha256": dataframe_digest(sensitivity),
        "eligible_events": int(len(features)),
        "executed_trades": int(len(ledger)),
        "pooled_primary": {
            "trades": int(len(ledger)),
            "win_rate": float(np.mean(pooled > 0.0)) if len(pooled) else 0.0,
            "profit_factor": profit_factor(pooled),
            "net_bps": float(pooled.sum()),
        },
        "per_ticker": ticker_summary.to_dict(orient="records"),
        "cost_sensitivity": sensitivity.to_dict(orient="records"),
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        _write_csv(staging / "source_inventory.csv", inventory)
        _write_csv(staging / "source_audit.csv", source_audit)
        _write_csv(staging / "trades.csv", ledger)
        _write_csv(staging / "monthly_metrics.csv", monthly)
        _write_csv(staging / "ticker_summary.csv", ticker_summary)
        _write_csv(staging / "cost_sensitivity.csv", sensitivity)
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
    parser.add_argument("--frozen-manifest", type=Path, default=DEFAULT_FROZEN_MANIFEST)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(args.output_dir.resolve(), args.frozen_manifest.resolve())
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
