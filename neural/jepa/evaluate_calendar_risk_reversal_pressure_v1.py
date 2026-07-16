#!/usr/bin/env python3
"""Frozen 2023 development ledger for CALENDAR_RISK_REVERSAL_PRESSURE_V1."""

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

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa.surface_flow_features import validate_underlying_session  # noqa: E402


PROJECT_ROOT = SCRIPT_REPO_ROOT
TICKERS = ("QQQ", "SPXW", "SPY")
DEVELOPMENT_START = "20230101"
DEVELOPMENT_END = "20231231"
ENTRY_TIME = "10:36:00"
EXIT_TIME = "13:36:00"
HOLD_MINUTES = 180
ROUND_TRIP_COST_BPS = 1.0
MIN_PROFIT_FACTOR = 1.20
MIN_WIN_RATE = 0.45
MIN_TRADES_EXCLUSIVE = 12
HALF_DAYS = frozenset({"20230703", "20231124"})

DATA_GATE_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "calendar_risk_reversal_pressure_v1_202301_202312_v1_data_gate"
)
DATA_GATE_MANIFEST = DATA_GATE_DIR / "manifest.json"
FEATURE_PATH = DATA_GATE_DIR / "calendar_rr_features.parquet"
SOURCE_INVENTORY_PATH = DATA_GATE_DIR / "source_inventory.csv"
PREDECLARATION = PROJECT_ROOT / (
    "research_papers/JEPA/CALENDAR_RISK_REVERSAL_PRESSURE_V1_PREDECLARATION.md"
)
DATA_GATE_RESULT = PROJECT_ROOT / (
    "research_papers/JEPA/CALENDAR_RISK_REVERSAL_PRESSURE_V1_DATA_GATE_RESULT.md"
)
DEFAULT_FROZEN_MANIFEST = DATA_GATE_DIR.parent / (
    "calendar_risk_reversal_pressure_v1_development_runner_frozen/manifest.json"
)
DEFAULT_OUTPUT = DATA_GATE_DIR.parent / (
    "calendar_risk_reversal_pressure_v1_development_202301_202312_v1"
)

EXPECTED_DATA_GATE_HASHES = {
    "manifest.json": "604f53b2f036d0ac7743883b1ae9fe21e0cab2f9405a8facd4ebe2720615a9c1",
    "calendar_rr_features.parquet": "de0ec4b3251505b763dff3dc8baee2f3462ca7a5833d70ed6db014b03112858b",
    "source_inventory.csv": "6f81e4f8cc102f63c60e23c04d0c13d7a5be4af535c745f2dc5ec2646a2184d8",
}
POLICY = {
    "feature": "calendar_rr_pressure",
    "action": "sign(calendar_rr_pressure)",
    "zero_action": "NO_TRADE",
    "entry": "derived_underlying_open_10:36:00",
    "exit": "derived_underlying_open_13:36:00",
    "hold_minutes": HOLD_MINUTES,
    "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
    "positions_per_ticker_per_day": 1,
    "overlap_policy": "one_fixed_nonoverlapping_position_per_ticker_day",
}
GATE_SPEC = {
    "profit_factor_strictly_greater_than": MIN_PROFIT_FACTOR,
    "win_rate_strictly_greater_than": MIN_WIN_RATE,
    "trades_per_month_strictly_greater_than": MIN_TRADES_EXCLUSIVE,
    "monthly_net_bps_strictly_greater_than": 0.0,
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_digest(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()


def current_git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def tracked_clean(path: Path, label: str) -> None:
    relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", relative],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise AssertionError(f"{label} must be committed and clean: {dirty}")


def canonical_date(value: object) -> str:
    digits = "".join(character for character in str(value) if character.isdigit())
    if len(digits) < 8:
        raise ValueError(f"invalid date: {value!r}")
    return digits[:8]


def _timestamp(day: str, clock: str) -> pd.Timestamp:
    return pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {clock}")


def validate_data_gate() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    for name, expected in EXPECTED_DATA_GATE_HASHES.items():
        path = DATA_GATE_DIR / name
        if not path.is_file() or sha256_file(path) != expected:
            raise AssertionError(f"data-gate artifact hash mismatch: {path}")
    manifest = json.loads(DATA_GATE_MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "calendar_risk_reversal_pressure_v1_outcome_free_data_gate"
        or manifest.get("status") != "PASS_DATA_GATE"
        or manifest.get("data_gate", {}).get("passed") is not True
        or manifest.get("labels_built") is not False
        or manifest.get("outcome_accessed") is not False
        or manifest.get("outer_2024_2025_opened") is not False
        or manifest.get("holdout_2026_opened") is not False
        or manifest.get("production_modified") is not False
        or int(manifest.get("rows", -1)) != 750
        or int(manifest.get("valid_rows", -1)) != 747
    ):
        raise AssertionError("authoritative calendar-RR data gate is not the frozen PASS")
    for name in ("calendar_rr_features.parquet", "source_inventory.csv"):
        if manifest.get("output_sha256", {}).get(name) != EXPECTED_DATA_GATE_HASHES[name]:
            raise AssertionError(f"manifest output hash mismatch: {name}")

    features = pd.read_parquet(FEATURE_PATH)
    required = {
        "ticker",
        "trade_date",
        "month",
        "calendar_half_day",
        "economic_clock_eligible",
        "feature_valid",
        "invalid_reason",
        "calendar_rr_pressure",
    }
    if required.difference(features.columns):
        raise KeyError(f"feature schema mismatch: {sorted(required.difference(features.columns))}")
    features = features.copy()
    features["ticker"] = features["ticker"].astype(str).str.upper()
    features["trade_date"] = features["trade_date"].map(canonical_date)
    features["month"] = features["month"].astype(str).str.replace(r"\D", "", regex=True).str[:6]
    features["calendar_rr_pressure"] = pd.to_numeric(features["calendar_rr_pressure"], errors="coerce")
    if (
        len(features) != 750
        or set(features["ticker"]) != set(TICKERS)
        or features.duplicated(["ticker", "trade_date"]).any()
        or not features["trade_date"].between(DEVELOPMENT_START, DEVELOPMENT_END).all()
        or int(features["feature_valid"].sum()) != 747
    ):
        raise AssertionError("feature view violates frozen development universe")
    valid = features.loc[features["feature_valid"]].copy()
    if not np.isfinite(valid["calendar_rr_pressure"].to_numpy(dtype=np.float64)).all():
        raise AssertionError("valid calendar-RR pressure contains non-finite values")
    expected_half_days = set(features.loc[features["calendar_half_day"], "trade_date"])
    if expected_half_days != set(HALF_DAYS):
        raise AssertionError("half-day calendar mismatch")
    development = valid.loc[valid["economic_clock_eligible"]].copy()
    monthly_counts = development.groupby(["ticker", "month"], observed=True).size()
    if (
        len(development) != 741
        or len(monthly_counts) != 36
        or int(monthly_counts.min()) <= MIN_TRADES_EXCLUSIVE
        or development["calendar_half_day"].any()
    ):
        raise AssertionError("eligible development view violates frozen capacity")

    inventory = pd.read_csv(SOURCE_INVENTORY_PATH, dtype={"trade_date": str, "expiration": str})
    inventory["ticker"] = inventory["ticker"].astype(str).str.upper()
    inventory["trade_date"] = inventory["trade_date"].map(canonical_date)
    underlying = inventory.loc[inventory["kind"].astype(str).eq("underlying")].copy()
    if (
        len(inventory) != 3750
        or len(underlying) != 750
        or underlying.duplicated(["ticker", "trade_date"]).any()
        or not underlying["trade_date"].str.startswith("2023").all()
    ):
        raise AssertionError("committed underlying inventory contract mismatch")
    selected = development[["ticker", "trade_date"]].merge(
        underlying,
        on=["ticker", "trade_date"],
        how="left",
        validate="one_to_one",
    )
    if len(selected) != len(development) or selected["path"].isna().any():
        raise AssertionError("eligible feature/underlying inventory join mismatch")
    return (
        development.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True),
        selected.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True),
        manifest,
    )


def action_from_pressure(pressure: float) -> tuple[int, str]:
    if not np.isfinite(pressure):
        raise ValueError("calendar-RR pressure must be finite")
    if pressure > 0.0:
        return 1, "LONG"
    if pressure < 0.0:
        return -1, "SHORT"
    return 0, "NO_TRADE_ZERO_PRESSURE"


def log_return_bps(end: float, start: float) -> float:
    if not (np.isfinite(end) and np.isfinite(start) and end > 0.0 and start > 0.0):
        raise ValueError("prices must be finite and positive")
    return float(math.log(end / start) * 10_000.0)


def make_trade_row(
    *,
    ticker: str,
    trade_date: str,
    pressure: float,
    entry_open: float,
    exit_open: float,
) -> dict[str, Any]:
    side, action = action_from_pressure(pressure)
    underlying_return = log_return_bps(exit_open, entry_open)
    executed = side != 0
    gross = float(side * underlying_return)
    return {
        "ticker": ticker,
        "trade_date": trade_date,
        "month": trade_date[:6],
        "decision_time": "10:35:00",
        "entry_time": ENTRY_TIME,
        "exit_time": EXIT_TIME,
        "hold_minutes": HOLD_MINUTES,
        "calendar_rr_pressure": float(pressure),
        "side": side,
        "action": action,
        "trade_executed": executed,
        "entry_open": float(entry_open),
        "exit_open": float(exit_open),
        "underlying_return_bps": underlying_return,
        "gross_bps": gross,
        "cost_bps": ROUND_TRIP_COST_BPS if executed else 0.0,
        "net_bps": gross - ROUND_TRIP_COST_BPS if executed else 0.0,
        "inverse_sign_control_net_bps": -gross - ROUND_TRIP_COST_BPS if executed else 0.0,
        "always_long_control_net_bps": underlying_return - ROUND_TRIP_COST_BPS,
    }


def build_ledger(features: pd.DataFrame, inventory: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_map = features.set_index(["ticker", "trade_date"])
    if not feature_map.index.is_unique:
        raise AssertionError("feature key is not unique")
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
        raw = pd.read_parquet(path)
        validated, audit = validate_underlying_session(
            raw,
            expected_ticker=ticker,
            expected_trade_date=day,
        )
        indexed = validated.set_index("bar_start")
        if not indexed.index.is_unique:
            raise AssertionError("validated underlying clock is not unique")
        entry_open = float(indexed.loc[_timestamp(day, ENTRY_TIME), "open"])
        exit_open = float(indexed.loc[_timestamp(day, EXIT_TIME), "open"])
        pressure = float(feature_map.loc[(ticker, day), "calendar_rr_pressure"])
        rows.append(
            make_trade_row(
                ticker=ticker,
                trade_date=day,
                pressure=pressure,
                entry_open=entry_open,
                exit_open=exit_open,
            )
        )
        audits.append(
            {
                "ticker": ticker,
                "trade_date": day,
                "source_sha256": actual_hash,
                "underlying_rows": int(audit["underlying_rows"]),
                "required_window_minutes": int(audit["underlying_required_window_minutes"]),
                "expected_required_window_minutes": int(audit["expected_underlying_required_window_minutes"]),
                "out_of_scope_invalid_rows": int(audit["underlying_out_of_scope_invalid_rows"]),
            }
        )
    ledger = pd.DataFrame(rows).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    source_audit = pd.DataFrame(audits).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    if (
        len(ledger) != 741
        or ledger.duplicated(["ticker", "trade_date"]).any()
        or not ledger["trade_date"].between(DEVELOPMENT_START, DEVELOPMENT_END).all()
        or not ledger["hold_minutes"].eq(HOLD_MINUTES).all()
    ):
        raise AssertionError("development ledger violates frozen scope or scheduler")
    return ledger, source_audit


def profit_factor(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    gross_profit = float(array[array > 0.0].sum())
    gross_loss = float(-array[array < 0.0].sum())
    if gross_loss == 0.0:
        return 1.0e12 if gross_profit > 0.0 else 0.0
    return gross_profit / gross_loss


def summarize_monthly(ledger: pd.DataFrame) -> pd.DataFrame:
    months = pd.period_range("2023-01", "2023-12", freq="M").astype(str).str.replace("-", "")
    rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        ticker_rows = ledger.loc[ledger["ticker"].eq(ticker)]
        for month in months:
            eligible = ticker_rows.loc[ticker_rows["month"].eq(month)]
            executed = eligible.loc[eligible["trade_executed"]]
            net = executed["net_bps"].to_numpy(dtype=np.float64)
            trades = int(len(executed))
            win_rate = float(np.mean(net > 0.0)) if trades else 0.0
            pf = profit_factor(net)
            pnl = float(net.sum())
            rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "eligible_events": int(len(eligible)),
                    "zero_pressure_events": int((~eligible["trade_executed"]).sum()),
                    "trades": trades,
                    "win_rate": win_rate,
                    "profit_factor": pf,
                    "net_bps": pnl,
                    "frequency_pass": trades > MIN_TRADES_EXCLUSIVE,
                    "win_rate_pass": win_rate > MIN_WIN_RATE,
                    "profit_factor_pass": pf > MIN_PROFIT_FACTOR,
                    "pnl_pass": pnl > 0.0,
                }
            )
    output = pd.DataFrame(rows)
    output["month_pass"] = output[
        ["frequency_pass", "win_rate_pass", "profit_factor_pass", "pnl_pass"]
    ].all(axis=1)
    if len(output) != 36:
        raise AssertionError("monthly summary must contain 36 cells")
    return output


def summarize_tickers(ledger: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        executed = ledger.loc[ledger["ticker"].eq(ticker) & ledger["trade_executed"]]
        net = executed["net_bps"].to_numpy(dtype=np.float64)
        cells = monthly.loc[monthly["ticker"].eq(ticker)]
        rows.append(
            {
                "ticker": ticker,
                "trades": int(len(executed)),
                "win_rate": float(np.mean(net > 0.0)) if len(net) else 0.0,
                "profit_factor": profit_factor(net),
                "net_bps": float(net.sum()),
                "min_month_trades": int(cells["trades"].min()),
                "positive_months": int(cells["pnl_pass"].sum()),
                "months_passing": int(cells["month_pass"].sum()),
                "all_months_pass": bool(cells["month_pass"].all()),
            }
        )
    return pd.DataFrame(rows)


def summarize_controls(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        ticker_rows = ledger.loc[ledger["ticker"].eq(ticker)]
        controls = {
            "inverse_sign": ticker_rows.loc[ticker_rows["trade_executed"], "inverse_sign_control_net_bps"],
            "always_long": ticker_rows["always_long_control_net_bps"],
        }
        for name, values in controls.items():
            array = values.to_numpy(dtype=np.float64)
            rows.append(
                {
                    "ticker": ticker,
                    "control": name,
                    "trades": int(len(array)),
                    "win_rate": float(np.mean(array > 0.0)) if len(array) else 0.0,
                    "profit_factor": profit_factor(array),
                    "net_bps": float(array.sum()),
                }
            )
    return pd.DataFrame(rows)


def classify_status(development_pass: bool, ticker_summary: pd.DataFrame) -> str:
    if development_pass:
        return "PASS_DEVELOPMENT_GATE_OUTER_NOT_OPENED"
    edge = ticker_summary["profit_factor"].gt(1.0)
    if bool(edge.all()):
        return "INCREMENTAL_EDGE_ALL_TICKERS_ONLY"
    if bool(edge.any()):
        return "PARTIAL_INCREMENTAL_EDGE_ONLY"
    return "NO_AGGREGATE_EDGE"


def verify_frozen_manifest(path: Path) -> dict[str, Any]:
    tracked_clean(path, "frozen runner manifest")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("schema") != "calendar_risk_reversal_pressure_v1_frozen_development_runner"
        or payload.get("status") != "PREEXECUTION_FROZEN"
        or payload.get("phase") != "development_2023"
        or payload.get("policy") != POLICY
        or payload.get("gate_spec") != GATE_SPEC
        or payload.get("outer_2024_2025_opened") is not False
        or payload.get("holdout_2026_opened") is not False
        or payload.get("production_modified") is not False
    ):
        raise AssertionError("frozen runner manifest contract mismatch")
    runner_relative = Path(__file__).resolve().relative_to(PROJECT_ROOT).as_posix()
    if payload.get("code_hashes", {}).get(runner_relative) != sha256_file(Path(__file__).resolve()):
        raise AssertionError("frozen evaluator hash mismatch")
    for name, expected in EXPECTED_DATA_GATE_HASHES.items():
        if payload.get("data_gate_inputs", {}).get(name, {}).get("sha256") != expected:
            raise AssertionError(f"frozen data-gate input mismatch: {name}")
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
    lines = ["# CALENDAR_RISK_REVERSAL_PRESSURE_V1 — development 2023", "", f"Status: `{summary['status']}`", ""]
    for row in ticker_summary.itertuples(index=False):
        lines.append(
            f"- {row.ticker}: {row.trades} trades, WR {row.win_rate:.3%}, PF {row.profit_factor:.6f}, "
            f"PnL {row.net_bps:+.3f} bps, months passing {row.months_passing}/12."
        )
    lines.extend(
        [
            "",
            f"Ticker-month cells passing all gates: {summary['ticker_month_cells_passing']}/36.",
            "",
            "2024–2026 and production were not opened.",
            "",
        ]
    )
    return "\n".join(lines)


def run(output_dir: Path, frozen_manifest_path: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    frozen = verify_frozen_manifest(frozen_manifest_path)
    features, inventory, data_gate = validate_data_gate()
    ledger, source_audit = build_ledger(features, inventory)
    monthly = summarize_monthly(ledger)
    ticker_summary = summarize_tickers(ledger, monthly)
    controls = summarize_controls(ledger)
    development_pass = bool(monthly["month_pass"].all())
    status = classify_status(development_pass, ticker_summary)
    executed = ledger.loc[ledger["trade_executed"]]
    pooled = executed["net_bps"].to_numpy(dtype=np.float64)
    summary: dict[str, Any] = {
        "schema": "calendar_risk_reversal_pressure_v1_development_evaluation",
        "status": status,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "development_2023",
        "development_pass": development_pass,
        "incremental_edge_all_tickers_pf_gt_1": bool(ticker_summary["profit_factor"].gt(1.0).all()),
        "ticker_month_cells_passing": int(monthly["month_pass"].sum()),
        "ticker_month_cells_total": 36,
        "outer_2024_2025_opened": False,
        "holdout_2026_opened": False,
        "production_modified": False,
        "policy": POLICY,
        "gate_spec": GATE_SPEC,
        "frozen_manifest_sha256": sha256_file(frozen_manifest_path),
        "frozen_runner_commit": frozen["runner_commit"],
        "execution_commit": current_git_commit(),
        "data_gate_commit": data_gate["git_commit"],
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "source_inventory_sha256": dataframe_digest(inventory),
        "source_audit_sha256": dataframe_digest(source_audit),
        "trades_sha256": dataframe_digest(ledger),
        "monthly_sha256": dataframe_digest(monthly),
        "ticker_summary_sha256": dataframe_digest(ticker_summary),
        "controls_sha256": dataframe_digest(controls),
        "eligible_events": int(len(ledger)),
        "executed_trades": int(len(executed)),
        "pooled_primary": {
            "trades": int(len(executed)),
            "win_rate": float(np.mean(pooled > 0.0)) if len(pooled) else 0.0,
            "profit_factor": profit_factor(pooled),
            "net_bps": float(pooled.sum()),
        },
        "per_ticker": ticker_summary.to_dict(orient="records"),
        "controls": controls.to_dict(orient="records"),
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
        _write_csv(staging / "controls_summary.csv", controls)
        (staging / "SUMMARY.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n"
        )
        (staging / "SUMMARY.md").write_text(render_summary(summary, ticker_summary), encoding="utf-8", newline="\n")
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
