#!/usr/bin/env python3
"""Independently audit the frozen sequential cross-venue V3 outer 2025."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa import (  # noqa: E402
    evaluate_cross_venue_calendar_rr_leader_v3_outer_2025 as outer,
)
from neural.jepa.build_calendar_risk_reversal_pressure_v1 import (  # noqa: E402
    canonical_date,
    tracked_clean,
)


PROJECT_ROOT = SCRIPT_REPO_ROOT
DEFAULT_INPUT = outer.DEFAULT_OUTPUT
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v3_outer_2025_v1_audit"
)
OUTPUT_HASH_FILES = (
    "monthly_orientation_states.csv",
    "source_audit.csv",
    "trades.csv",
    "monthly_metrics.csv",
    "ticker_summary.csv",
    "cost_sensitivity.csv",
    "SUMMARY.md",
)
REQUIRED_FILES = (*OUTPUT_HASH_FILES, "SUMMARY.json")
TRADE_DTYPES = {"trade_date": str, "month": str, "prior_month": str}


def validate_output_hashes(summary: dict[str, Any], input_dir: Path) -> None:
    expected = summary.get("output_sha256")
    if not isinstance(expected, dict) or set(expected) != set(OUTPUT_HASH_FILES):
        raise AssertionError("V3 outer audit output hash closure changed")
    for name in OUTPUT_HASH_FILES:
        if expected[name] != outer.sha256_file(input_dir / name):
            raise AssertionError(f"V3 outer output hash mismatch: {name}")


def _timestamp(trade_date: str, clock: str) -> pd.Timestamp:
    return pd.Timestamp(
        f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} {clock}"
    )


def read_two_opens(path: Path, ticker: str, trade_date: str) -> tuple[float, float]:
    frame = pd.read_parquet(path, columns=["symbol", "date", "timestamp", "open"])
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame["date"] = frame["date"].map(canonical_date)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame["open"] = pd.to_numeric(frame["open"], errors="coerce")
    entry = _timestamp(trade_date, "10:36:00")
    exit_value = _timestamp(trade_date, "13:36:00")
    selected = frame.loc[frame["timestamp"].isin([entry, exit_value])].copy()
    if (
        len(selected) != 2
        or selected.isna().any().any()
        or selected["timestamp"].duplicated().any()
        or set(selected["timestamp"]) != {entry, exit_value}
        or not selected["symbol"].eq(ticker).all()
        or not selected["date"].eq(trade_date).all()
        or not np.isfinite(selected["open"].to_numpy(dtype=float)).all()
        or not selected["open"].gt(0.0).all()
    ):
        raise AssertionError(f"V3 outer audit exact clocks failed: {path}")
    values = selected.set_index("timestamp")["open"]
    return float(values.loc[entry]), float(values.loc[exit_value])


def profit_factor(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    gains = float(array[array > 0.0].sum())
    losses = float(-array[array < 0.0].sum())
    if losses == 0.0:
        return 1.0e12 if gains > 0.0 else 0.0
    return gains / losses


def state_from_month(rows: pd.DataFrame, prior_month: str) -> dict[str, Any]:
    counts = rows.groupby("ticker", observed=True).size().to_dict()
    if set(counts) != set(outer.TICKERS) or any(
        int(counts[ticker]) <= outer.MIN_MONTH_TRADES_EXCLUSIVE
        for ticker in outer.TICKERS
    ):
        raise AssertionError(f"V3 outer audit monthly capacity failed: {prior_month}")
    direct_hits = rows["base_gross_bps"].gt(0.0)
    rate = float(direct_hits.mean())
    orientation = 1 if rate >= 0.5 else -1
    return {
        "prior_month": prior_month,
        "prior_trades_QQQ": int(counts["QQQ"]),
        "prior_trades_SPXW": int(counts["SPXW"]),
        "prior_trades_SPY": int(counts["SPY"]),
        "prior_pooled_trades": int(len(rows)),
        "prior_direct_hits": int(direct_hits.sum()),
        "prior_direct_hit_rate": rate,
        "orientation": orientation,
        "orientation_name": "DIRECT" if orientation == 1 else "INVERSE",
    }


def recompute(
    events: pd.DataFrame, manifest: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    states: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    state = dict(manifest["initial_state"])
    months = pd.period_range("2025-01", "2025-12", freq="M").strftime("%Y%m")
    for month in months:
        expected_prior = (pd.Period(month, freq="M") - 1).strftime("%Y%m")
        if state["prior_month"] != expected_prior:
            raise AssertionError("V3 outer audit prior-month chain failed")
        states.append({"month": month, **state})
        direct_rows: list[dict[str, Any]] = []
        month_events = events.loc[events["month"].eq(month)]
        for record in month_events.itertuples(index=False):
            path = Path(str(record.path))
            if not path.is_file() or path.stat().st_size != int(record.size_bytes):
                raise AssertionError(f"V3 outer audit source size failed: {path}")
            source_hash = outer.sha256_file(path)
            if source_hash != str(record.sha256):
                raise AssertionError(f"V3 outer audit source hash failed: {path}")
            entry_open, exit_open = read_two_opens(
                path, str(record.ticker), str(record.trade_date)
            )
            underlying_return = float(np.log(exit_open / entry_open) * 10_000.0)
            base_side = int(np.sign(float(record.signal_pressure)))
            orientation = int(state["orientation"])
            side = base_side * orientation
            base_gross = base_side * underlying_return
            gross = side * underlying_return
            row = {
                "ticker": str(record.ticker),
                "trade_date": str(record.trade_date),
                "month": month,
                "sensor_ticker": str(record.sensor_ticker),
                "signal_pressure": float(record.signal_pressure),
                "base_side": base_side,
                "prior_month": state["prior_month"],
                "prior_direct_hit_rate": float(state["prior_direct_hit_rate"]),
                "orientation": orientation,
                "side": side,
                "entry_open": entry_open,
                "exit_open": exit_open,
                "underlying_return_bps": underlying_return,
                "base_gross_bps": base_gross,
                "gross_bps": gross,
                "net_bps_1bp": gross - 1.0,
                "net_bps_2bp": gross - 2.0,
                "net_bps_3bp": gross - 3.0,
                "net_bps": gross - 1.0,
            }
            trades.append(row)
            direct_rows.append(
                {
                    "ticker": str(record.ticker),
                    "base_gross_bps": base_gross,
                }
            )
            audits.append(
                {
                    "ticker": str(record.ticker),
                    "trade_date": str(record.trade_date),
                    "path": str(path),
                    "sha256": source_hash,
                    "size_bytes": int(path.stat().st_size),
                    "rows_read": 2,
                    "entry_time": "10:36:00",
                    "exit_time": "13:36:00",
                }
            )
        state = state_from_month(pd.DataFrame(direct_rows), month)
    ledger = pd.DataFrame(trades).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    source_audit = pd.DataFrame(audits).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if len(ledger) != len(events):
        raise AssertionError("V3 outer audit coverage failed")
    return ledger, pd.DataFrame(states), source_audit


def summarize_monthly(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    months = pd.period_range("2025-01", "2025-12", freq="M").strftime("%Y%m")
    for ticker in outer.TICKERS:
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
                    "frequency_pass": int(len(net))
                    > outer.MIN_MONTH_TRADES_EXCLUSIVE,
                    "pnl_positive": bool(net.sum() > 0.0),
                }
            )
    return pd.DataFrame(rows)


def summarize_tickers(ledger: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in outer.TICKERS:
        selected = ledger.loc[ledger["ticker"].eq(ticker)]
        cells = monthly.loc[monthly["ticker"].eq(ticker)]
        net = selected["net_bps"].to_numpy(dtype=float)
        pf = profit_factor(net)
        win_rate = float(np.mean(net > 0.0))
        minimum = int(cells["trades"].min())
        positive = int(cells["pnl_positive"].sum())
        rows.append(
            {
                "ticker": ticker,
                "trades": int(len(net)),
                "win_rate": win_rate,
                "profit_factor": pf,
                "net_bps": float(net.sum()),
                "min_month_trades": minimum,
                "positive_months": positive,
                "objective_gate_pass": bool(
                    pf > 1.20
                    and win_rate > 0.45
                    and minimum > 12
                    and positive == 12
                ),
            }
        )
    return pd.DataFrame(rows)


def summarize_sensitivity(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope in (*outer.TICKERS, "POOLED"):
        selected = ledger if scope == "POOLED" else ledger.loc[
            ledger["ticker"].eq(scope)
        ]
        for cost in (1.0, 2.0, 3.0):
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


def compare_frames(
    recomputed: pd.DataFrame,
    stored: pd.DataFrame,
    keys: list[str],
    label: str,
) -> None:
    left = recomputed.sort_values(keys, kind="stable").reset_index(drop=True)
    right = stored.sort_values(keys, kind="stable").reset_index(drop=True)
    for column in left.columns:
        if column in right.columns and pd.api.types.is_bool_dtype(left[column]):
            right[column] = right[column].map(
                lambda value: str(value).strip().lower() in {"true", "1"}
            )
    try:
        pd.testing.assert_frame_equal(
            left,
            right[left.columns],
            check_dtype=False,
            rtol=1e-12,
            atol=1e-12,
        )
    except AssertionError as exc:
        raise AssertionError(f"V3 outer stored {label} differs from audit") from exc


def run(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V3 outer audit exists: {output_dir}")
    tracked_clean(Path(__file__).resolve(), "V3 outer independent auditor")
    for name in REQUIRED_FILES:
        if not (input_dir / name).is_file():
            raise FileNotFoundError(input_dir / name)
    summary = json.loads((input_dir / "SUMMARY.json").read_text(encoding="utf-8"))
    manifest = outer.verify_frozen_manifest(outer.DEFAULT_FROZEN_MANIFEST)
    if (
        summary.get("schema")
        != "cross_venue_calendar_rr_leader_v3_outer_2025_v1"
        or summary.get("frozen_manifest_sha256")
        != outer.sha256_file(outer.DEFAULT_FROZEN_MANIFEST)
        or summary.get("mapping") != outer.SENSOR_MAP
        or summary.get("outer_year") != "2025"
        or summary.get("outer_2025_opened") is not True
        or summary.get("holdout_2026_opened") is not False
        or summary.get("production_modified") is not False
        or summary.get("live_or_systemd_modified") is not False
    ):
        raise AssertionError("V3 outer audit summary contract changed")
    validate_output_hashes(summary, input_dir)
    _, events = outer.load_2025_inputs()
    ledger, states, source_audit = recompute(events, manifest)
    monthly = summarize_monthly(ledger)
    tickers = summarize_tickers(ledger, monthly)
    sensitivity = summarize_sensitivity(ledger)
    compare_frames(
        states,
        pd.read_csv(
            input_dir / "monthly_orientation_states.csv",
            dtype={"month": str, "prior_month": str},
        ),
        ["month"],
        "states",
    )
    compare_frames(
        source_audit,
        pd.read_csv(input_dir / "source_audit.csv", dtype={"trade_date": str}),
        ["ticker", "trade_date"],
        "source audit",
    )
    compare_frames(
        ledger,
        pd.read_csv(input_dir / "trades.csv", dtype=TRADE_DTYPES),
        ["ticker", "trade_date"],
        "trades",
    )
    compare_frames(
        monthly,
        pd.read_csv(input_dir / "monthly_metrics.csv", dtype={"month": str}),
        ["ticker", "month"],
        "monthly metrics",
    )
    compare_frames(
        tickers,
        pd.read_csv(input_dir / "ticker_summary.csv"),
        ["ticker"],
        "ticker summary",
    )
    compare_frames(
        sensitivity,
        pd.read_csv(input_dir / "cost_sensitivity.csv"),
        ["scope", "cost_bps"],
        "cost sensitivity",
    )
    passed = bool(tickers["objective_gate_pass"].all())
    expected_status = (
        "PASS_OUTER_2025_OBJECTIVE_2026_NOT_FROZEN"
        if passed
        else "FAILED_OUTER_2025_2026_CLOSED"
    )
    if (
        summary.get("status") != expected_status
        or summary.get("objective_gate_pass") is not passed
        or summary.get("advance_to_2026_freeze") is not passed
        or int(summary.get("eligible_events", -1)) != len(events)
        or int(summary.get("executed_trades", -1)) != len(ledger)
        or summary.get("states_recomputed_sha256") != outer.dataframe_digest(states)
        or summary.get("trades_recomputed_sha256") != outer.dataframe_digest(ledger)
        or summary.get("monthly_recomputed_sha256") != outer.dataframe_digest(monthly)
        or summary.get("ticker_summary_recomputed_sha256")
        != outer.dataframe_digest(tickers)
        or summary.get("cost_sensitivity_recomputed_sha256")
        != outer.dataframe_digest(sensitivity)
    ):
        raise AssertionError("V3 outer audit status/digest closure changed")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        states.to_csv(staging / "states_recomputed.csv", index=False)
        tickers.to_csv(staging / "ticker_summary_recomputed.csv", index=False)
        sensitivity.to_csv(staging / "cost_sensitivity_recomputed.csv", index=False)
        names = (
            "states_recomputed.csv",
            "ticker_summary_recomputed.csv",
            "cost_sensitivity_recomputed.csv",
        )
        audit = {
            "schema": "cross_venue_calendar_rr_leader_v3_outer_2025_audit_v1",
            "status": "PASS_INDEPENDENT_V3_OUTER_2025_AUDIT",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "evaluation_commit": summary["execution_commit"],
            "audit_commit": outer.current_git_commit(),
            "outer_status": expected_status,
            "eligible_events": int(len(events)),
            "source_files_rehashed": int(len(source_audit)),
            "source_mismatches": 0,
            "objective_gate_pass": passed,
            "advance_to_2026_freeze": passed,
            "outer_2025_opened": True,
            "holdout_2026_opened": False,
            "production_modified": False,
            "live_or_systemd_modified": False,
            "evaluation_summary_sha256": outer.sha256_file(
                input_dir / "SUMMARY.json"
            ),
            "states_recomputed_sha256": outer.dataframe_digest(states),
            "trades_recomputed_sha256": outer.dataframe_digest(ledger),
            "monthly_recomputed_sha256": outer.dataframe_digest(monthly),
            "ticker_summary_recomputed_sha256": outer.dataframe_digest(tickers),
            "cost_sensitivity_recomputed_sha256": outer.dataframe_digest(
                sensitivity
            ),
            "output_sha256": {
                name: outer.sha256_file(staging / name) for name in names
            },
        }
        (staging / "audit_summary.json").write_text(
            json.dumps(audit, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return audit


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    audit = run(args.input_dir.resolve(), args.output_dir.resolve())
    print(json.dumps(audit, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
