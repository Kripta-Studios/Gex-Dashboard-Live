#!/usr/bin/env python3
"""Frozen 2023 development ledger for OPTION_PARITY_PRESSURE_V1."""

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
DEVELOPMENT_YEAR = "2023"
DEVELOPMENT_START = "20230101"
DEVELOPMENT_END = "20231231"
ENTRY_TIME = "10:36:00"
EXIT_TIME = "13:36:00"
HOLD_MINUTES = 180
ROUND_TRIP_COST_BPS = 1.0
MIN_PROFIT_FACTOR = 1.20
MIN_WIN_RATE = 0.45
MIN_TRADES_EXCLUSIVE = 12
HALF_DAYS_2023 = frozenset({"20230703", "20231124"})

DATA_GATE_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "option_parity_pressure_v1_202301_202512_v1r1_data_gate"
)
DATA_GATE_MANIFEST = DATA_GATE_DIR / "manifest.json"
FEATURE_PATH = DATA_GATE_DIR / "parity_features.parquet"
DATA_GATE_RESULT = PROJECT_ROOT / "research_papers/JEPA/OPTION_PARITY_PRESSURE_V1_DATA_GATE_RESULT.md"
PREDECLARATION = PROJECT_ROOT / "research_papers/JEPA/OPTION_PARITY_PRESSURE_V1_PREDECLARATION.md"
SCOPE_AMENDMENT = PROJECT_ROOT / "research_papers/JEPA/OPTION_PARITY_PRESSURE_V1_SCOPE_AMENDMENT.md"
DEFAULT_UNDERLYING_ROOT = Path("D:/ThetaData/data_underlying_derived")
DEFAULT_FROZEN_MANIFEST = DATA_GATE_DIR.parent / (
    "option_parity_pressure_v1_development_runner_frozen/manifest.json"
)
DEFAULT_OUTPUT = DATA_GATE_DIR.parent / "option_parity_pressure_v1_development_202301_202312_v1"

EXPECTED_DATA_GATE_HASHES = {
    "manifest.json": "2b36e5765ee56677225437bd60c3a24e443e8b2c1e32ff35d3f6a493b665fbc7",
    "parity_features.parquet": "45bca098588fa7bafefaf9a134e2f7de19f5d5d256d5d388766b5d33a38d5100",
}
GATE_SPEC = {
    "profit_factor_strictly_greater_than": MIN_PROFIT_FACTOR,
    "win_rate_strictly_greater_than": MIN_WIN_RATE,
    "trades_per_month_strictly_greater_than": MIN_TRADES_EXCLUSIVE,
    "monthly_net_bps_strictly_greater_than": 0.0,
}
POLICY = {
    "feature": "parity_pressure",
    "action": "sign(parity_pressure)",
    "zero_action": "NO_TRADE",
    "entry": "derived_underlying_open_10:36:00",
    "exit": "derived_underlying_open_13:36:00",
    "hold_minutes": HOLD_MINUTES,
    "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
    "positions_per_ticker_per_day": 1,
    "overlap_policy": "one_fixed_nonoverlapping_position_per_ticker_day",
}


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


def validate_data_gate() -> tuple[pd.DataFrame, dict[str, Any]]:
    for name, expected_hash in EXPECTED_DATA_GATE_HASHES.items():
        path = DATA_GATE_DIR / name
        if not path.is_file() or sha256_file(path) != expected_hash:
            raise AssertionError(f"data-gate artifact hash mismatch: {path}")
    manifest = json.loads(DATA_GATE_MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "option_parity_pressure_v1_outcome_free_data_gate"
        or manifest.get("status") != "PASS_DATA_GATE"
        or manifest.get("labels_built") is not False
        or manifest.get("outcome_accessed") is not False
        or manifest.get("holdout_2026_opened") is not False
        or manifest.get("production_modified") is not False
        or int(manifest.get("rows", -1)) != 2256
        or int(manifest.get("valid_rows", -1)) != 2256
        or manifest.get("data_gate", {}).get("passed") is not True
    ):
        raise AssertionError("authoritative data gate is not the frozen outcome-free PASS")
    if manifest.get("output_sha256", {}).get("parity_features.parquet") != EXPECTED_DATA_GATE_HASHES[
        "parity_features.parquet"
    ]:
        raise AssertionError("feature hash and data-gate manifest disagree")

    features = pd.read_parquet(FEATURE_PATH)
    required = {
        "ticker",
        "trade_date",
        "year",
        "month",
        "calendar_half_day",
        "economic_clock_eligible",
        "parity_valid",
        "invalid_reason",
        "parity_pressure",
    }
    if required.difference(features.columns):
        raise KeyError(f"feature view schema mismatch: {sorted(required.difference(features.columns))}")
    features = features.copy()
    features["ticker"] = features["ticker"].astype(str).str.upper()
    features["trade_date"] = features["trade_date"].map(canonical_date)
    features["year"] = features["year"].astype(str)
    features["month"] = features["month"].astype(str).str.replace(r"\D", "", regex=True).str[:6]
    features["parity_pressure"] = pd.to_numeric(features["parity_pressure"], errors="coerce")
    if (
        len(features) != 2256
        or set(features["ticker"]) != set(TICKERS)
        or features.duplicated(["ticker", "trade_date"]).any()
        or not features["trade_date"].between("20230101", "20251231").all()
        or features["trade_date"].str.startswith("2026").any()
        or not features["parity_valid"].eq(True).all()  # noqa: E712
        or not np.isfinite(features["parity_pressure"].to_numpy(dtype=np.float64)).all()
        or not features["year"].eq(features["trade_date"].str[:4]).all()
        or not features["month"].eq(features["trade_date"].str[:6]).all()
    ):
        raise AssertionError("feature view violates frozen data-gate scope or validity")

    development = features.loc[
        features["year"].eq(DEVELOPMENT_YEAR) & features["economic_clock_eligible"].eq(True)  # noqa: E712
    ].copy()
    expected_half_days = features.loc[
        features["year"].eq(DEVELOPMENT_YEAR) & features["calendar_half_day"].eq(True),  # noqa: E712
        "trade_date",
    ]
    if set(expected_half_days) != set(HALF_DAYS_2023):
        raise AssertionError("2023 half-day exclusions disagree with frozen calendar")
    if (
        development.empty
        or not development["trade_date"].between(DEVELOPMENT_START, DEVELOPMENT_END).all()
        or development["calendar_half_day"].any()
        or set(development["ticker"]) != set(TICKERS)
    ):
        raise AssertionError("development selection crossed the frozen 2023 scope")
    monthly_counts = development.groupby(["ticker", "month"], observed=True).size()
    if len(monthly_counts) != 36 or int(monthly_counts.min()) <= MIN_TRADES_EXCLUSIVE:
        raise AssertionError("development feature capacity does not satisfy the frozen monthly gate")
    return development.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True), manifest


def build_source_inventory(features: pd.DataFrame, underlying_root: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in features.itertuples(index=False):
        ticker = str(row.ticker)
        day = str(row.trade_date)
        if not day.startswith(DEVELOPMENT_YEAR):
            raise AssertionError("attempted outcome path outside development 2023")
        path = underlying_root / ticker / DEVELOPMENT_YEAR / day[4:6] / f"{ticker}_{day}.parquet"
        if not path.is_file():
            raise FileNotFoundError(path)
        rows.append(
            {
                "ticker": ticker,
                "trade_date": day,
                "path": str(path.resolve()),
                "size_bytes": int(path.stat().st_size),
                "sha256": sha256_file(path),
            }
        )
    inventory = pd.DataFrame(rows).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    if len(inventory) != len(features) or inventory.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("underlying source inventory is not one-to-one with development features")
    if not inventory["trade_date"].str.startswith(DEVELOPMENT_YEAR).all():
        raise AssertionError("underlying source inventory crossed development 2023")
    return inventory


def action_from_pressure(pressure: float) -> tuple[int, str]:
    if not np.isfinite(pressure):
        raise ValueError("parity pressure must be finite")
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
    *, ticker: str, trade_date: str, parity_pressure: float, entry_open: float, exit_open: float
) -> dict[str, Any]:
    side, action = action_from_pressure(parity_pressure)
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
        "parity_pressure": float(parity_pressure),
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
    feature_map = features.set_index(["ticker", "trade_date"], verify_integrity=True)
    rows: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for record in inventory.itertuples(index=False):
        ticker = str(record.ticker)
        day = str(record.trade_date)
        raw = pd.read_parquet(str(record.path))
        validated, audit = validate_underlying_session(
            raw,
            expected_ticker=ticker,
            expected_trade_date=day,
        )
        indexed = validated.set_index("bar_start", verify_integrity=True)
        entry_open = float(indexed.loc[_timestamp(day, ENTRY_TIME), "open"])
        exit_open = float(indexed.loc[_timestamp(day, EXIT_TIME), "open"])
        pressure = float(feature_map.loc[(ticker, day), "parity_pressure"])
        rows.append(
            make_trade_row(
                ticker=ticker,
                trade_date=day,
                parity_pressure=pressure,
                entry_open=entry_open,
                exit_open=exit_open,
            )
        )
        audits.append(
            {
                "ticker": ticker,
                "trade_date": day,
                "source_sha256": str(record.sha256),
                "underlying_rows": int(audit["underlying_rows"]),
                "required_window_minutes": int(audit["underlying_required_window_minutes"]),
                "expected_required_window_minutes": int(audit["expected_underlying_required_window_minutes"]),
                "out_of_scope_invalid_rows": int(audit["underlying_out_of_scope_invalid_rows"]),
            }
        )
    ledger = pd.DataFrame(rows).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    source_audit = pd.DataFrame(audits).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    if (
        ledger.empty
        or len(ledger) != len(features)
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
        raise AssertionError("monthly summary must contain exactly 36 ticker-month cells")
    return output


def summarize_tickers(ledger: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        executed = ledger.loc[ledger["ticker"].eq(ticker) & ledger["trade_executed"]]
        net = executed["net_bps"].to_numpy(dtype=np.float64)
        ticker_months = monthly.loc[monthly["ticker"].eq(ticker)]
        rows.append(
            {
                "ticker": ticker,
                "trades": int(len(executed)),
                "win_rate": float(np.mean(net > 0.0)) if len(net) else 0.0,
                "profit_factor": profit_factor(net),
                "net_bps": float(net.sum()),
                "min_month_trades": int(ticker_months["trades"].min()),
                "positive_months": int(ticker_months["pnl_pass"].sum()),
                "months_passing": int(ticker_months["month_pass"].sum()),
                "all_months_pass": bool(ticker_months["month_pass"].all()),
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
        for control, values in controls.items():
            array = values.to_numpy(dtype=np.float64)
            rows.append(
                {
                    "ticker": ticker,
                    "control": control,
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
    ticker_edge = ticker_summary["profit_factor"].gt(1.0)
    if bool(ticker_edge.all()):
        return "INCREMENTAL_EDGE_ALL_TICKERS_ONLY"
    if bool(ticker_edge.any()):
        return "PARTIAL_INCREMENTAL_EDGE_ONLY"
    return "NO_AGGREGATE_EDGE"


def verify_frozen_manifest(path: Path) -> dict[str, Any]:
    tracked_clean(path, "frozen runner manifest")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("schema") != "option_parity_pressure_v1_frozen_development_runner"
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
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", frozen_commit, current_git_commit()],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if ancestor.returncode != 0:
        raise AssertionError("frozen runner commit is not an ancestor of current HEAD")
    return payload


def _atomic_write_csv(path: Path, frame: pd.DataFrame) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False, lineterminator="\n")
    os.replace(temporary, path)


def _atomic_write_text(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def render_summary(summary: dict[str, Any], ticker_summary: pd.DataFrame) -> str:
    lines = [
        "# OPTION_PARITY_PRESSURE_V1 — development 2023",
        "",
        f"Status: `{summary['status']}`",
        "",
    ]
    for row in ticker_summary.itertuples(index=False):
        lines.append(
            f"- {row.ticker}: {row.trades} trades, WR {row.win_rate:.3%}, "
            f"PF {row.profit_factor:.6f}, PnL {row.net_bps:+.3f} bps, "
            f"months passing {row.months_passing}/12."
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


def run(underlying_root: Path, output_dir: Path, frozen_manifest_path: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    frozen_manifest = verify_frozen_manifest(frozen_manifest_path)
    features, data_gate_manifest = validate_data_gate()
    inventory = build_source_inventory(features, underlying_root)
    ledger, source_audit = build_ledger(features, inventory)
    monthly = summarize_monthly(ledger)
    ticker_summary = summarize_tickers(ledger, monthly)
    controls = summarize_controls(ledger)
    development_pass = bool(monthly["month_pass"].all())
    status = classify_status(development_pass, ticker_summary)

    executed = ledger.loc[ledger["trade_executed"]]
    pooled_net = executed["net_bps"].to_numpy(dtype=np.float64)
    summary: dict[str, Any] = {
        "schema": "option_parity_pressure_v1_development_evaluation",
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
        "frozen_runner_commit": frozen_manifest["runner_commit"],
        "execution_commit": current_git_commit(),
        "data_gate_commit": data_gate_manifest["git_commit"],
        "data_gate_manifest_sha256": EXPECTED_DATA_GATE_HASHES["manifest.json"],
        "feature_sha256": EXPECTED_DATA_GATE_HASHES["parity_features.parquet"],
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "source_inventory_sha256": dataframe_digest(inventory),
        "source_audit_sha256": dataframe_digest(source_audit),
        "trades_sha256": dataframe_digest(ledger),
        "monthly_sha256": dataframe_digest(monthly),
        "ticker_summary_sha256": dataframe_digest(ticker_summary),
        "controls_sha256": dataframe_digest(controls),
        "source_sessions": int(len(inventory)),
        "eligible_events": int(len(ledger)),
        "executed_trades": int(len(executed)),
        "pooled_primary": {
            "trades": int(len(executed)),
            "win_rate": float(np.mean(pooled_net > 0.0)) if len(pooled_net) else 0.0,
            "profit_factor": profit_factor(pooled_net),
            "net_bps": float(pooled_net.sum()),
        },
        "per_ticker": ticker_summary.to_dict(orient="records"),
        "controls": controls.to_dict(orient="records"),
    }

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(f"staging output already exists: {staging}")
    staging.mkdir()
    try:
        _atomic_write_csv(staging / "source_inventory.csv", inventory)
        _atomic_write_csv(staging / "source_audit.csv", source_audit)
        _atomic_write_csv(staging / "trades.csv", ledger)
        _atomic_write_csv(staging / "monthly_metrics.csv", monthly)
        _atomic_write_csv(staging / "ticker_summary.csv", ticker_summary)
        _atomic_write_csv(staging / "controls_summary.csv", controls)
        _atomic_write_text(staging / "SUMMARY.json", json.dumps(summary, indent=2, allow_nan=False) + "\n")
        _atomic_write_text(staging / "SUMMARY.md", render_summary(summary, ticker_summary))
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--underlying-root", type=Path, default=DEFAULT_UNDERLYING_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frozen-manifest", type=Path, default=DEFAULT_FROZEN_MANIFEST)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(
        args.underlying_root.resolve(),
        args.output_dir.resolve(),
        args.frozen_manifest.resolve(),
    )
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
