#!/usr/bin/env python3
"""Run the frozen sequential outer 2025 for cross-venue monthly V3."""

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

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v1 as v1  # noqa: E402
from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v3 as v3  # noqa: E402
from neural.jepa.build_calendar_risk_reversal_pressure_v1 import (  # noqa: E402
    canonical_date,
    tracked_clean,
)


PROJECT_ROOT = SCRIPT_REPO_ROOT
TICKERS = v3.TICKERS
SENSOR_MAP = v3.SENSOR_MAP
OUTER_YEAR = "2025"
OUTER_START = "20250101"
OUTER_END = "20251231"
COSTS_BPS = v3.COSTS_BPS
OBJECTIVE_MIN_PF = 1.20
MIN_WIN_RATE = 0.45
MIN_MONTH_TRADES_EXCLUSIVE = 12

PREDECLARATION = PROJECT_ROOT / (
    "research_papers/JEPA/"
    "CROSS_VENUE_CALENDAR_RR_LEADER_V3_MONTHLY_ORIENTATION_PREDECLARATION.md"
)
DATA_GATE_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v1_data_gate_202401_202512_v1r1"
)
DATA_GATE_HASHES = {
    "manifest.json": "492f51c8a80b5e03c453486da185bd6cad85ef1c913a9510366cb19455d0452e",
    "cross_venue_calendar_rr_features.parquet": (
        "fd2953bd9bc918b95079d494663cf7ca2fc9dfe141604b8e8803cc2bf605d268"
    ),
    "source_inventory.csv": (
        "b63ca25185627528b1bc22ad937dcb834dbb4846d03b451aa395a62003d4c56c"
    ),
}
DEVELOPMENT_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v3_development_2024_v1"
)
DEVELOPMENT_AUDIT_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v3_development_2024_v1_audit"
)
DEVELOPMENT_HASHES = {
    DEVELOPMENT_DIR / "SUMMARY.json": (
        "6a688225e1eda2ee5f3dacb04db6ac7bb7b6cff3d36812012c06649f481850f5"
    ),
    DEVELOPMENT_DIR / "trades.csv": (
        "2f5433764970187df919e2a6911ad52e7570bdcb515e993f9757bcc742aba570"
    ),
    DEVELOPMENT_AUDIT_DIR / "audit_summary.json": (
        "fa923cc95740950e394004d2e16d3d6e95816842dbb1b4dce9ee485cd92692ba"
    ),
}
DEFAULT_FROZEN_MANIFEST = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v3_outer_2025_runner_frozen/manifest.json"
)
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v3_outer_2025_v1"
)
FREEZER_PATH = Path("neural/jepa/freeze_cross_venue_calendar_rr_leader_v3_runner.py")
RUNNER_CODE_PATHS = (
    Path("neural/jepa/evaluate_cross_venue_calendar_rr_leader_v3_outer_2025.py"),
    FREEZER_PATH,
    Path("neural/jepa/audit_cross_venue_calendar_rr_leader_v3_outer_2025.py"),
    Path("neural/jepa/evaluate_cross_venue_calendar_rr_leader_v3.py"),
    Path("neural/jepa/evaluate_cross_venue_calendar_rr_leader_v1.py"),
    PREDECLARATION.relative_to(PROJECT_ROOT),
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


def ordered_hash(values: Iterable[str]) -> str:
    payload = "".join(f"{value}\n" for value in sorted(values)).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_frozen_inputs() -> None:
    for name, expected in DATA_GATE_HASHES.items():
        path = DATA_GATE_DIR / name
        if not path.is_file() or sha256_file(path) != expected:
            raise AssertionError(f"V3 outer data-gate input changed: {path}")
    for path, expected in DEVELOPMENT_HASHES.items():
        if not path.is_file() or sha256_file(path) != expected:
            raise AssertionError(f"V3 outer development input changed: {path}")


def load_2025_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    validate_frozen_inputs()
    features = pd.read_parquet(
        DATA_GATE_DIR / "cross_venue_calendar_rr_features.parquet",
        filters=[("year", "==", OUTER_YEAR)],
    ).copy()
    required = {
        "ticker",
        "trade_date",
        "year",
        "month",
        "sensor_ticker",
        "signal_pressure",
        "signal_action",
        "economic_event_valid",
    }
    missing = sorted(required.difference(features.columns))
    if missing:
        raise KeyError(f"V3 outer feature view lacks fields: {missing}")
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
    outer = features.loc[features["economic_event_valid"]].copy()
    expected_action = np.sign(outer["signal_pressure"]).astype(np.int64)
    counts = outer.groupby(["ticker", "month"], observed=True).size()
    if (
        outer.empty
        or outer.duplicated(["ticker", "trade_date"]).any()
        or set(outer["ticker"]) != set(TICKERS)
        or not outer["year"].eq(OUTER_YEAR).all()
        or not outer["trade_date"].between(OUTER_START, OUTER_END).all()
        or not outer["sensor_ticker"].eq(outer["ticker"].map(SENSOR_MAP)).all()
        or not np.isfinite(outer["signal_pressure"].to_numpy()).all()
        or not outer["signal_action"].eq(expected_action).all()
        or outer["signal_action"].eq(0).any()
        or len(counts) != 36
        or int(counts.min()) <= MIN_MONTH_TRADES_EXCLUSIVE
    ):
        raise AssertionError("V3 outer 2025 feature identity/capacity failed")

    inventory = pd.read_csv(
        DATA_GATE_DIR / "source_inventory.csv",
        dtype={"trade_date": str, "sha256": str},
    )
    inventory["ticker"] = inventory["ticker"].astype(str).str.upper().str.strip()
    inventory["trade_date"] = inventory["trade_date"].map(canonical_date)
    underlying = inventory.loc[
        inventory["kind"].astype(str).eq("underlying")
        & inventory["trade_date"].str.startswith(OUTER_YEAR)
    ].copy()
    selected = outer[
        ["ticker", "trade_date", "month", "sensor_ticker", "signal_pressure", "signal_action"]
    ].merge(
        underlying[["ticker", "trade_date", "path", "size_bytes", "sha256"]],
        on=["ticker", "trade_date"],
        how="left",
        validate="one_to_one",
    )
    if len(selected) != len(outer) or selected[["path", "sha256"]].isna().any().any():
        raise AssertionError("V3 outer features/underlying join failed")
    return (
        outer.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True),
        selected.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True),
    )


def state_from_direct_rows(rows: pd.DataFrame, prior_month: str) -> dict[str, Any]:
    selected = rows.loc[rows["month"].eq(prior_month)].copy()
    counts = selected.groupby("ticker", observed=True).size().to_dict()
    if (
        set(counts) != set(TICKERS)
        or any(int(counts[ticker]) <= MIN_MONTH_TRADES_EXCLUSIVE for ticker in TICKERS)
    ):
        raise AssertionError(f"V3 outer state frequency failed: {prior_month}/{counts}")
    if "base_gross_bps" in selected.columns:
        direct = pd.to_numeric(selected["base_gross_bps"], errors="raise").gt(0.0)
    else:
        direct = pd.to_numeric(selected["direct_win"], errors="raise").astype(bool)
    rate = float(direct.mean())
    orientation = v3.orientation_from_hit_rate(rate)
    return {
        "prior_month": prior_month,
        "prior_trades_QQQ": int(counts["QQQ"]),
        "prior_trades_SPXW": int(counts["SPXW"]),
        "prior_trades_SPY": int(counts["SPY"]),
        "prior_pooled_trades": int(len(selected)),
        "prior_direct_hits": int(direct.sum()),
        "prior_direct_hit_rate": rate,
        "orientation": orientation,
        "orientation_name": "DIRECT" if orientation == 1 else "INVERSE",
    }


def initial_state_from_development() -> dict[str, Any]:
    trades = pd.read_csv(
        DEVELOPMENT_DIR / "trades.csv", dtype={"trade_date": str, "month": str}
    )
    return state_from_direct_rows(trades, "202412")


def verify_frozen_manifest(path: Path) -> dict[str, Any]:
    tracked_clean(path, "V3 outer 2025 frozen manifest")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("schema") != "cross_venue_calendar_rr_leader_v3_outer_2025_frozen_runner"
        or payload.get("status") != "PREEXECUTION_FROZEN"
        or payload.get("year") != OUTER_YEAR
        or payload.get("mapping") != SENSOR_MAP
        or payload.get("rule", {}).get("threshold") != v3.ORIENTATION_THRESHOLD
        or payload.get("outcome_accessed") is not False
        or payload.get("execution_started") is not False
        or payload.get("outer_2025_opened") is not False
        or payload.get("holdout_2026_opened") is not False
        or payload.get("production_modified") is not False
        or payload.get("live_or_systemd_modified") is not False
        or payload.get("data_gate_hashes") != DATA_GATE_HASHES
        or payload.get("development_hashes")
        != {
            relative.as_posix(): expected
            for source, expected in DEVELOPMENT_HASHES.items()
            for relative in (source.relative_to(PROJECT_ROOT),)
        }
        or payload.get("initial_state") != initial_state_from_development()
    ):
        raise AssertionError("V3 outer frozen manifest contract changed")
    for relative in RUNNER_CODE_PATHS:
        if payload.get("code_hashes", {}).get(relative.as_posix()) != sha256_file(
            PROJECT_ROOT / relative
        ):
            raise AssertionError(f"V3 outer frozen code changed: {relative}")
    frozen_commit = str(payload.get("runner_commit", ""))
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", frozen_commit, current_git_commit()],
        cwd=PROJECT_ROOT,
        check=False,
    ).returncode != 0:
        raise AssertionError("V3 frozen runner commit is not an ancestor")
    return payload


def build_sequential_ledger(
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
            raise AssertionError("V3 sequential state prior month changed")
        states.append({"month": month, **state})
        month_events = events.loc[events["month"].eq(month)].copy()
        month_direct_rows: list[dict[str, Any]] = []
        for record in month_events.itertuples(index=False):
            path = Path(str(record.path))
            if not path.is_file() or path.stat().st_size != int(record.size_bytes):
                raise AssertionError(f"V3 outer source missing/size changed: {path}")
            actual_hash = sha256_file(path)
            if actual_hash != str(record.sha256):
                raise AssertionError(f"V3 outer source hash changed: {path}")
            entry_open, exit_open = v1.read_exact_return_opens(
                path, str(record.ticker), str(record.trade_date)
            )
            underlying_return = v1.log_return_bps(exit_open, entry_open)
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
            }
            for cost in COSTS_BPS:
                row[f"net_bps_{int(cost)}bp"] = gross - cost
            row["net_bps"] = row["net_bps_1bp"]
            trades.append(row)
            month_direct_rows.append(
                {
                    "ticker": str(record.ticker),
                    "month": month,
                    "base_gross_bps": base_gross,
                }
            )
            audits.append(
                {
                    "ticker": str(record.ticker),
                    "trade_date": str(record.trade_date),
                    "path": str(path),
                    "sha256": actual_hash,
                    "size_bytes": int(path.stat().st_size),
                    "rows_read": 2,
                    "entry_time": v1.ENTRY_TIME,
                    "exit_time": v1.EXIT_TIME,
                }
            )
        state = state_from_direct_rows(pd.DataFrame(month_direct_rows), month)
    ledger = pd.DataFrame(trades).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    state_frame = pd.DataFrame(states)
    source_audit = pd.DataFrame(audits).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if len(ledger) != len(events):
        raise AssertionError("V3 outer sequential ledger coverage changed")
    return ledger, state_frame, source_audit


def profit_factor(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    gains = float(array[array > 0.0].sum())
    losses = float(-array[array < 0.0].sum())
    if losses == 0.0:
        return 1.0e12 if gains > 0.0 else 0.0
    return gains / losses


def summarize_monthly(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    months = pd.period_range("2025-01", "2025-12", freq="M").strftime("%Y%m")
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


def run(output_dir: Path, frozen_manifest_path: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V3 outer output exists: {output_dir}")
    manifest = verify_frozen_manifest(frozen_manifest_path)
    _, events = load_2025_inputs()
    event_ids = [f"{row.ticker}|{row.trade_date}" for row in events.itertuples()]
    monthly_counts = (
        events.groupby(["ticker", "month"], observed=True)
        .size()
        .rename("events")
        .reset_index()
        .to_dict(orient="records")
    )
    if (
        len(events) != manifest.get("events")
        or ordered_hash(event_ids) != manifest.get("event_id_sha256")
        or dataframe_digest(events) != manifest.get("source_inventory_sha256")
        or monthly_counts != manifest.get("monthly_counts")
    ):
        raise AssertionError("V3 outer frozen event inventory changed")
    ledger, states, source_audit = build_sequential_ledger(events, manifest)
    monthly = summarize_monthly(ledger)
    tickers = summarize_tickers(ledger, monthly)
    sensitivity = summarize_sensitivity(ledger)
    passed = bool(tickers["objective_gate_pass"].all())
    status = (
        "PASS_OUTER_2025_OBJECTIVE_2026_NOT_FROZEN"
        if passed
        else "FAILED_OUTER_2025_2026_CLOSED"
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        states.to_csv(staging / "monthly_orientation_states.csv", index=False)
        source_audit.to_csv(staging / "source_audit.csv", index=False)
        ledger.to_csv(staging / "trades.csv", index=False)
        monthly.to_csv(staging / "monthly_metrics.csv", index=False)
        tickers.to_csv(staging / "ticker_summary.csv", index=False)
        sensitivity.to_csv(staging / "cost_sensitivity.csv", index=False)
        summary_lines = [
            "# CROSS_VENUE_CALENDAR_RR_LEADER_V3 outer 2025",
            "",
            f"Status: `{status}`.",
            "",
            "| Ticker | Trades | WR | PF | Net bps | Min/month | Positive months | Gate |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for row in tickers.itertuples(index=False):
            summary_lines.append(
                f"| {row.ticker} | {row.trades} | {row.win_rate:.6%} | "
                f"{row.profit_factor:.6f} | {row.net_bps:.3f} | "
                f"{row.min_month_trades} | {row.positive_months} | "
                f"{'PASS' if row.objective_gate_pass else 'FAIL'} |"
            )
        summary_lines.extend(
            [
                "",
                "Mapping: QQQ←QQQ, SPXW←SPY, SPY←SPY. "
                "Cash proxy open10:36→open13:36, hold180, primary cost1bp.",
                "",
                "2026 remains unopened. Production/live/systemd remain untouched.",
            ]
        )
        (staging / "SUMMARY.md").write_text(
            "\n".join(summary_lines) + "\n", encoding="utf-8", newline="\n"
        )
        output_names = (
            "monthly_orientation_states.csv",
            "source_audit.csv",
            "trades.csv",
            "monthly_metrics.csv",
            "ticker_summary.csv",
            "cost_sensitivity.csv",
            "SUMMARY.md",
        )
        summary = {
            "schema": "cross_venue_calendar_rr_leader_v3_outer_2025_v1",
            "status": status,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "execution_commit": current_git_commit(),
            "frozen_manifest_sha256": sha256_file(frozen_manifest_path),
            "frozen_runner_commit": manifest["runner_commit"],
            "mapping": SENSOR_MAP,
            "rule": manifest["rule"],
            "outer_year": OUTER_YEAR,
            "eligible_events": int(len(events)),
            "executed_trades": int(len(ledger)),
            "per_ticker": tickers.to_dict(orient="records"),
            "objective_gate_pass": passed,
            "advance_to_2026_freeze": passed,
            "outer_2025_opened": True,
            "holdout_2026_opened": False,
            "production_modified": False,
            "live_or_systemd_modified": False,
            "output_sha256": {
                name: sha256_file(staging / name) for name in output_names
            },
            "states_recomputed_sha256": dataframe_digest(states),
            "trades_recomputed_sha256": dataframe_digest(ledger),
            "monthly_recomputed_sha256": dataframe_digest(monthly),
            "ticker_summary_recomputed_sha256": dataframe_digest(tickers),
            "cost_sensitivity_recomputed_sha256": dataframe_digest(sensitivity),
        }
        (staging / "SUMMARY.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
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
