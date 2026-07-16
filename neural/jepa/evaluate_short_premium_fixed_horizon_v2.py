#!/usr/bin/env python3
"""Executable fixed-horizon defined-risk short-premium walk-forward V2."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from neural.jepa import evaluate_short_premium_defined_risk_v1 as v1


PREDECLARATION = (
    v1.REPO_ROOT
    / "research_papers/JEPA/SHORT_PREMIUM_FIXED_HORIZON_V2_PREDECLARATION.md"
)
DEFAULT_OUTPUT = (
    v1.REPO_ROOT / "research_papers/JEPA/results/_diagnostics/"
    "short_premium_fixed_horizon_v2_202401_202512"
)
HOLD_MINUTES = (30, 60, 90, 120)


def exact_exit(
    greeks: pd.DataFrame,
    structure: v1.Structure,
    entry_dt: pd.Timestamp,
    hold_minutes: int,
) -> dict | None:
    exit_dt = entry_dt + pd.Timedelta(minutes=hold_minutes)
    exit_frame = greeks.loc[greeks["qdt"].eq(exit_dt)]
    return exact_exit_snapshot(exit_frame, structure, exit_dt, hold_minutes)


def exact_exit_snapshot(
    exit_frame: pd.DataFrame,
    structure: v1.Structure,
    exit_dt: pd.Timestamp,
    hold_minutes: int,
) -> dict | None:
    specs = (
        ("short_call", "C", structure.short_call_strike),
        ("short_put", "P", structure.short_put_strike),
        ("long_call", "C", structure.long_call_strike),
        ("long_put", "P", structure.long_put_strike),
    )
    legs: dict[str, pd.Series] = {}
    for name, right, strike in specs:
        rows = exit_frame.loc[
            exit_frame["right"].eq(right)
            & np.isclose(exit_frame["strike"], strike, rtol=0.0, atol=1e-9)
        ]
        rows = rows.loc[v1.valid_quotes(rows)]
        if len(rows) != 1:
            return None
        legs[name] = rows.iloc[0]
    close_debit = (
        float(legs["short_call"]["ask"])
        + float(legs["short_put"]["ask"])
        - float(legs["long_call"]["bid"])
        - float(legs["long_put"]["bid"])
    )
    if not np.isfinite(close_debit) or close_debit < 0.0:
        return None
    gross_points = structure.entry_credit - close_debit
    net_points = gross_points - v1.ROUND_TRIP_FRICTION_POINTS
    return {
        "exit_dt": exit_dt,
        "exit_reason": "time",
        "hold_minutes": hold_minutes,
        "close_debit": close_debit,
        "gross_pnl_points": gross_points,
        "net_pnl_points": net_points,
        "net_pnl_R": net_points / structure.max_risk_points,
    }


def build_session_candidates(
    greeks: pd.DataFrame, native_clock: pd.DataFrame, ticker: str, day: str
) -> tuple[list[dict], list[dict]]:
    entry_dt = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {v1.ENTRY_TIME}")
    required_exit = entry_dt + pd.Timedelta(minutes=max(HOLD_MINUTES))
    if native_clock["qdt"].max() < required_exit:
        raise AssertionError(f"{ticker} {day}: native clock cannot support TIME120")
    entry = greeks.loc[greeks["qdt"].eq(entry_dt)].copy()
    exit_snapshots = {
        hold_minutes: greeks.loc[
            greeks["qdt"].eq(entry_dt + pd.Timedelta(minutes=hold_minutes))
        ].copy()
        for hold_minutes in HOLD_MINUTES
    }
    structures: list[v1.Structure] = []
    for delta in v1.CONDOR_DELTAS:
        for width in v1.WIDTHS[ticker]:
            structure = v1.build_structure(
                entry, ticker, kind="IC", short_delta=delta, width=width
            )
            if structure is not None:
                structures.append(structure)
    for width in v1.FLY_WIDTHS[ticker]:
        structure = v1.build_structure(
            entry, ticker, kind="IF", short_delta=0.50, width=width
        )
        if structure is not None:
            structures.append(structure)
    trades = []
    unresolved = []
    for structure in structures:
        for hold_minutes in HOLD_MINUTES:
            profile_id = f"{structure.structure_id}__TIME{hold_minutes}"
            exit_dt = entry_dt + pd.Timedelta(minutes=hold_minutes)
            result = exact_exit_snapshot(
                exit_snapshots[hold_minutes], structure, exit_dt, hold_minutes
            )
            if result is None:
                unresolved.append(
                    {"ticker": ticker, "trade_date": day, "profile_id": profile_id}
                )
                continue
            trades.append(
                {
                    "ticker": ticker,
                    "trade_date": day,
                    "month": day[:6],
                    "entry_dt": entry_dt,
                    "scheduled_exit_dt": result["exit_dt"],
                    "profile_id": profile_id,
                    "exit_rule": f"TIME{hold_minutes}",
                    **asdict(structure),
                    **result,
                }
            )
    return trades, unresolved


def run(args: argparse.Namespace) -> dict:
    if args.start_date != v1.FROZEN_START_DATE or args.end_date != v1.FROZEN_END_DATE:
        raise ValueError("V2 accepts only frozen 2024-01-01..2025-12-31")
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable V2 output exists: {output}")
    seals = v1.validate_seals(
        Path(args.native_seal),
        Path(args.complement_seal),
        Path(args.native_index),
        Path(args.complement_index),
    )
    source_index = v1.load_source_index(
        Path(args.native_index), Path(args.complement_index)
    )
    source_index = source_index.loc[
        source_index["ticker"].isin(v1.TICKERS)
        & source_index["trade_date"].between(
            args.start_date, args.end_date, inclusive="both"
        )
    ].copy()
    counts = source_index.groupby("ticker", sort=True).size().to_dict()
    expected = {ticker: v1.FROZEN_SESSIONS_PER_TICKER for ticker in v1.TICKERS}
    if counts != expected:
        raise AssertionError(f"V2 source-session census mismatch: {counts}")
    all_trades = []
    unresolved = []
    for position, (_, row) in enumerate(source_index.iterrows(), start=1):
        greeks, clock = v1._read_session(row, verify_hashes=True)
        trades, failures = build_session_candidates(
            greeks, clock, str(row["ticker"]), str(row["trade_date"])
        )
        all_trades.extend(trades)
        unresolved.extend(failures)
        if position % 50 == 0 or position == len(source_index):
            print(
                f"sessions={position}/{len(source_index)} candidates={len(all_trades)} "
                f"unresolved={len(unresolved)}",
                flush=True,
            )
    if unresolved:
        raise AssertionError(
            f"V2 entry-resolved profiles contain unresolved exits: {unresolved[:10]}"
        )
    candidates = pd.DataFrame(all_trades)
    if candidates.empty or not np.isfinite(candidates["net_pnl_R"]).all():
        raise AssertionError("V2 candidate ledger is empty or non-finite")
    months = [f"2025{month:02d}" for month in range(1, 13)]
    selected, selections = v1.select_walkforward(candidates, months)
    monthly, gate = v1.evaluate_gate(selected, months)
    metrics = {
        "schema": "short_premium_fixed_horizon_v2_metrics",
        "status": "PASS_PRE2026_GATE"
        if gate["joint_gate_pass"]
        else "CLOSED_PRE2026_GATE",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "start_date": args.start_date,
            "end_date": args.end_date,
            "months": months,
        },
        "execution": {
            "entry_time": v1.ENTRY_TIME,
            "hold_minutes": list(HOLD_MINUTES),
            "round_trip_friction_points": v1.ROUND_TRIP_FRICTION_POINTS,
            "entry_fill": "short_bid_minus_long_ask",
            "exit_fill": "short_ask_minus_long_bid",
        },
        "candidate_rows": int(len(candidates)),
        "selected_rows": int(len(selected)),
        "source_sessions": int(len(source_index)),
        "source_sessions_by_ticker": counts,
        **gate,
        "holdout_2026_used": False,
        "production_modified": False,
    }
    provenance = {
        "schema": "short_premium_fixed_horizon_v2_provenance",
        "predeclaration_sha256": v1.sha256_file(PREDECLARATION),
        "runner_sha256": v1.sha256_file(__file__),
        "v1_runner_sha256": v1.sha256_file(Path(v1.__file__)),
        "native_index_sha256": v1.sha256_file(args.native_index),
        "complement_index_sha256": v1.sha256_file(args.complement_index),
        "native_seal_status": seals["native"]["status"],
        "complement_seal_status": seals["complement"]["status"],
        "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
        "original_greek_bid_ask_used": True,
        "sidecar_prices_used": False,
        "file_hash_validation": True,
        "holdout_2026_used": False,
        "production_modified": False,
    }
    output.mkdir(parents=True, exist_ok=False)
    candidates.to_parquet(output / "candidate_trade_ledger.parquet", index=False)
    selected.to_parquet(output / "selected_trade_ledger.parquet", index=False)
    selections.to_csv(output / "selected_folds.csv", index=False)
    monthly.to_csv(output / "monthly_metrics.csv", index=False)
    source_index.to_csv(output / "source_sessions.csv", index=False)
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
    parser.add_argument("--start-date", default=v1.FROZEN_START_DATE)
    parser.add_argument("--end-date", default=v1.FROZEN_END_DATE)
    parser.add_argument("--native-index", default=str(v1.DEFAULT_NATIVE_INDEX))
    parser.add_argument("--complement-index", default=str(v1.DEFAULT_COMPLEMENT_INDEX))
    parser.add_argument("--native-seal", default=str(v1.DEFAULT_NATIVE_SEAL))
    parser.add_argument("--complement-seal", default=str(v1.DEFAULT_COMPLEMENT_SEAL))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
