#!/usr/bin/env python3
"""Audit the completed one-shot 2024 cross-venue calendar-RR ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v1 as evaluate  # noqa: E402


PROJECT_ROOT = SCRIPT_REPO_ROOT
DEFAULT_INPUT = evaluate.DEFAULT_OUTPUT
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "tmp/cross_venue_calendar_rr_leader_v1_outer_2024_v1_audit"
)
REQUIRED_FILES = (
    "source_inventory.csv",
    "source_audit.csv",
    "trades.csv",
    "monthly_metrics.csv",
    "ticker_summary.csv",
    "cost_sensitivity.csv",
    "SUMMARY.json",
    "SUMMARY.md",
)
SUMMARY_OUTPUT_HASHES = {
    "source_inventory_sha256": "source_inventory.csv",
    "source_audit_sha256": "source_audit.csv",
    "trades_sha256": "trades.csv",
    "monthly_sha256": "monthly_metrics.csv",
    "ticker_summary_sha256": "ticker_summary.csv",
    "cost_sensitivity_sha256": "cost_sensitivity.csv",
}


def current_git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_digest(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_summary_output_hashes(summary: dict[str, Any], input_dir: Path) -> None:
    for field, name in SUMMARY_OUTPUT_HASHES.items():
        if summary.get(field) != sha256_file(input_dir / name):
            raise AssertionError(f"outer summary output hash mismatch: {name}")


def profit_factor(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    gains = float(array[array > 0.0].sum())
    losses = float(-array[array < 0.0].sum())
    if losses == 0.0:
        return 1.0e12 if gains > 0.0 else 0.0
    return gains / losses


def validate_and_recompute_trades(ledger: pd.DataFrame) -> pd.DataFrame:
    required = {
        "ticker",
        "trade_date",
        "month",
        "sensor_ticker",
        "decision_time",
        "entry_time",
        "exit_time",
        "hold_minutes",
        "signal_pressure",
        "side",
        "entry_open",
        "exit_open",
        "underlying_return_bps",
        "gross_bps",
        "net_bps_1bp",
        "net_bps_2bp",
        "net_bps_3bp",
        "net_bps",
    }
    missing = sorted(required.difference(ledger.columns))
    if missing:
        raise KeyError(f"outer ledger lacks fields: {missing}")
    work = ledger.copy()
    work["ticker"] = work["ticker"].astype(str).str.upper().str.strip()
    work["sensor_ticker"] = work["sensor_ticker"].astype(str).str.upper().str.strip()
    work["trade_date"] = (
        work["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    )
    work["month"] = work["trade_date"].str[:6]
    numeric = (
        "hold_minutes",
        "signal_pressure",
        "side",
        "entry_open",
        "exit_open",
        "underlying_return_bps",
        "gross_bps",
        "net_bps_1bp",
        "net_bps_2bp",
        "net_bps_3bp",
        "net_bps",
    )
    for column in numeric:
        work[column] = pd.to_numeric(work[column], errors="raise")
    if (
        work.empty
        or work.duplicated(["ticker", "trade_date"]).any()
        or not work["trade_date"].between(evaluate.OUTER_START, evaluate.OUTER_END).all()
        or not work["sensor_ticker"].eq(work["ticker"].map(evaluate.SENSOR_MAP)).all()
        or not work["decision_time"].astype(str).eq("10:35:00").all()
        or not work["entry_time"].astype(str).eq(evaluate.ENTRY_TIME).all()
        or not work["exit_time"].astype(str).eq(evaluate.EXIT_TIME).all()
        or not work["hold_minutes"].eq(evaluate.HOLD_MINUTES).all()
        or not work["side"].isin([-1, 1]).all()
        or not work["side"].eq(np.sign(work["signal_pressure"]).astype(np.int64)).all()
    ):
        raise AssertionError("outer ledger scope/policy identity failed")
    start = work["entry_open"].to_numpy(dtype=float)
    end = work["exit_open"].to_numpy(dtype=float)
    if (
        not np.isfinite(start).all()
        or not np.isfinite(end).all()
        or (start <= 0.0).any()
        or (end <= 0.0).any()
    ):
        raise AssertionError("outer ledger prices are invalid")
    recomputed_return = np.log(end / start) * 10_000.0
    recomputed_gross = work["side"].to_numpy(dtype=float) * recomputed_return
    checks = {
        "underlying_return_bps": recomputed_return,
        "gross_bps": recomputed_gross,
        "net_bps_1bp": recomputed_gross - 1.0,
        "net_bps_2bp": recomputed_gross - 2.0,
        "net_bps_3bp": recomputed_gross - 3.0,
        "net_bps": recomputed_gross - 1.0,
    }
    for column, expected in checks.items():
        if not np.allclose(
            work[column].to_numpy(dtype=float),
            expected,
            rtol=0.0,
            atol=1e-10,
            equal_nan=False,
        ):
            raise AssertionError(f"outer ledger economic recomputation failed: {column}")
    return work.sort_values(["ticker", "trade_date"], kind="stable").reset_index(
        drop=True
    )


def recompute_monthly(ledger: pd.DataFrame) -> pd.DataFrame:
    months = pd.period_range("2024-01", "2024-12", freq="M").strftime("%Y%m")
    rows: list[dict[str, Any]] = []
    for ticker in evaluate.TICKERS:
        ticker_rows = ledger.loc[ledger["ticker"].eq(ticker)]
        for month in months:
            selected = ticker_rows.loc[ticker_rows["month"].eq(month)]
            net = selected["net_bps"].to_numpy(dtype=float)
            rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "trades": int(len(net)),
                    "win_rate": float(np.mean(net > 0.0)) if len(net) else 0.0,
                    "profit_factor": profit_factor(net),
                    "net_bps": float(net.sum()),
                    "frequency_pass": int(len(net)) > evaluate.MIN_TRADES_EXCLUSIVE,
                    "pnl_positive": bool(net.sum() > 0.0),
                }
            )
    return pd.DataFrame(rows)


def recompute_tickers(ledger: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in evaluate.TICKERS:
        selected = ledger.loc[ledger["ticker"].eq(ticker)]
        cells = monthly.loc[monthly["ticker"].eq(ticker)]
        net = selected["net_bps"].to_numpy(dtype=float)
        trades = int(len(net))
        win_rate = float(np.mean(net > 0.0)) if trades else 0.0
        pf = profit_factor(net)
        pnl = float(net.sum())
        minimum = int(cells["trades"].min())
        positive_months = int(cells["pnl_positive"].sum())
        rows.append(
            {
                "ticker": ticker,
                "trades": trades,
                "win_rate": win_rate,
                "profit_factor": pf,
                "net_bps": pnl,
                "min_month_trades": minimum,
                "positive_months": positive_months,
                "incremental_gate_pass": bool(
                    pf > evaluate.INCREMENTAL_MIN_PROFIT_FACTOR
                    and win_rate > evaluate.MIN_WIN_RATE
                    and pnl > 0.0
                    and minimum > evaluate.MIN_TRADES_EXCLUSIVE
                ),
                "promotion_gate_pass": bool(
                    pf > evaluate.FINAL_MIN_PROFIT_FACTOR
                    and win_rate > evaluate.MIN_WIN_RATE
                    and minimum > evaluate.MIN_TRADES_EXCLUSIVE
                    and positive_months == 12
                ),
            }
        )
    return pd.DataFrame(rows)


def recompute_sensitivity(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope in (*evaluate.TICKERS, "POOLED"):
        selected = ledger if scope == "POOLED" else ledger.loc[ledger["ticker"].eq(scope)]
        for cost in evaluate.COST_SENSITIVITY_BPS:
            net = selected[f"net_bps_{int(cost)}bp"].to_numpy(dtype=float)
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


def _compare_tables(
    recomputed: pd.DataFrame, stored: pd.DataFrame, keys: list[str], label: str
) -> None:
    left = recomputed.sort_values(keys, kind="stable").reset_index(drop=True)
    right = stored.sort_values(keys, kind="stable").reset_index(drop=True)
    for column in left.columns:
        if column in right.columns and pd.api.types.is_bool_dtype(left[column]):
            right[column] = right[column].map(
                lambda value: str(value).strip().lower() in {"true", "1"}
            )
    try:
        pd.testing.assert_frame_equal(left, right[left.columns], check_dtype=False)
    except AssertionError as exc:
        raise AssertionError(f"stored {label} differs from recomputation") from exc


def rehash_underlying_sources(inventory: pd.DataFrame, workers: int) -> pd.DataFrame:
    required = {"ticker", "trade_date", "path", "size_bytes", "sha256"}
    missing = sorted(required.difference(inventory.columns))
    if missing:
        raise KeyError(f"outer source inventory lacks fields: {missing}")
    output = inventory.copy()
    output["path"] = output["path"].astype(str)
    output["size_bytes"] = pd.to_numeric(output["size_bytes"], errors="raise").astype(
        np.int64
    )
    output["sha256"] = output["sha256"].astype(str)
    if output["path"].duplicated().any():
        raise AssertionError("outer underlying paths are not unique")

    def one(path_value: str) -> tuple[int, str]:
        path = Path(path_value)
        if not path.is_file():
            raise FileNotFoundError(path)
        return int(path.stat().st_size), sha256_file(path)

    actual: dict[str, tuple[int, str]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(one, path): path for path in output["path"]}
        for future in as_completed(futures):
            actual[futures[future]] = future.result()
    output["actual_size_bytes"] = output["path"].map(lambda path: actual[path][0])
    output["actual_sha256"] = output["path"].map(lambda path: actual[path][1])
    output["size_match"] = output["size_bytes"].eq(output["actual_size_bytes"])
    output["hash_match"] = output["sha256"].eq(output["actual_sha256"])
    if not output["size_match"].all() or not output["hash_match"].all():
        raise AssertionError("outer underlying source changed")
    return output


def run(input_dir: Path, output_dir: Path, workers: int) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    if workers < 1:
        raise ValueError("workers must be positive")
    evaluate.tracked_clean(Path(__file__).resolve(), "outer auditor")
    for name in REQUIRED_FILES:
        if not (input_dir / name).is_file():
            raise FileNotFoundError(input_dir / name)
    summary = json.loads((input_dir / "SUMMARY.json").read_text(encoding="utf-8"))
    if (
        summary.get("schema")
        != "cross_venue_calendar_rr_leader_v1_outer_2024_evaluation"
        or summary.get("phase") != "outer_2024"
        or summary.get("outcome_accessed") is not True
        or summary.get("outer_2024_opened") is not True
        or summary.get("outer_2025_opened") is not False
        or summary.get("holdout_2026_opened") is not False
        or summary.get("production_modified") is not False
        or summary.get("policy") != evaluate.POLICY
        or summary.get("incremental_gate_spec") != evaluate.INCREMENTAL_GATE_SPEC
        or summary.get("promotion_gate_spec") != evaluate.PROMOTION_GATE_SPEC
    ):
        raise AssertionError("outer-2024 evaluation summary contract changed")
    validate_summary_output_hashes(summary, input_dir)
    frozen_path = evaluate.DEFAULT_FROZEN_MANIFEST
    if (
        not frozen_path.is_file()
        or sha256_file(frozen_path) != summary.get("frozen_manifest_sha256")
    ):
        raise AssertionError("outer-2024 frozen manifest changed")

    raw_ledger = pd.read_csv(
        input_dir / "trades.csv", dtype={"trade_date": str, "month": str}
    )
    ledger = validate_and_recompute_trades(raw_ledger)
    if set(ledger["ticker"]) != set(evaluate.TICKERS):
        raise AssertionError("outer ledger ticker scope is incomplete")
    monthly = recompute_monthly(ledger)
    ticker_summary = recompute_tickers(ledger, monthly)
    sensitivity = recompute_sensitivity(ledger)
    _compare_tables(
        monthly,
        pd.read_csv(input_dir / "monthly_metrics.csv", dtype={"month": str}),
        ["ticker", "month"],
        "monthly metrics",
    )
    _compare_tables(
        ticker_summary,
        pd.read_csv(input_dir / "ticker_summary.csv"),
        ["ticker"],
        "ticker summary",
    )
    _compare_tables(
        sensitivity,
        pd.read_csv(input_dir / "cost_sensitivity.csv"),
        ["scope", "cost_bps"],
        "cost sensitivity",
    )
    advance = bool(ticker_summary["incremental_gate_pass"].all())
    promotion = bool(ticker_summary["promotion_gate_pass"].all())
    expected_status = evaluate.classify_status(advance, promotion, ticker_summary)
    if (
        summary.get("status") != expected_status
        or summary.get("advance_to_2025") is not advance
        or summary.get("promotion_gate_pass") is not promotion
        or int(summary.get("executed_trades", -1)) != len(ledger)
    ):
        raise AssertionError("outer summary metrics/hashes differ from independent audit")
    inventory = pd.read_csv(
        input_dir / "source_inventory.csv",
        dtype={"trade_date": str, "sha256": str},
    )
    source_hash_audit = rehash_underlying_sources(inventory, workers)
    if len(source_hash_audit) != len(ledger):
        raise AssertionError("outer source inventory/trade count mismatch")
    expected_source_audit = source_hash_audit[
        ["ticker", "trade_date", "path", "actual_sha256", "actual_size_bytes"]
    ].rename(
        columns={
            "path": "source_path",
            "actual_sha256": "source_sha256",
            "actual_size_bytes": "source_size_bytes",
        }
    )
    expected_source_audit["rows_read"] = 2
    expected_source_audit["entry_time"] = evaluate.ENTRY_TIME
    expected_source_audit["exit_time"] = evaluate.EXIT_TIME
    stored_source_audit = pd.read_csv(
        input_dir / "source_audit.csv",
        dtype={"trade_date": str, "source_sha256": str},
    )
    _compare_tables(
        expected_source_audit,
        stored_source_audit,
        ["ticker", "trade_date"],
        "source audit",
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        monthly.to_csv(staging / "monthly_recomputed.csv", index=False)
        ticker_summary.to_csv(staging / "ticker_summary_recomputed.csv", index=False)
        sensitivity.to_csv(staging / "cost_sensitivity_recomputed.csv", index=False)
        output_names = (
            "monthly_recomputed.csv",
            "ticker_summary_recomputed.csv",
            "cost_sensitivity_recomputed.csv",
        )
        audit = {
            "schema": "cross_venue_calendar_rr_leader_v1_outer_2024_audit_v1",
            "status": "PASS_INDEPENDENT_OUTER_2024_AUDIT",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "audit_commit": current_git_commit(),
            "evaluation_commit": summary["execution_commit"],
            "evaluation_status": summary["status"],
            "advance_to_2025": advance,
            "promotion_gate_pass": promotion,
            "trades": int(len(ledger)),
            "source_hash_mismatches": int((~source_hash_audit["hash_match"]).sum()),
            "source_size_mismatches": int((~source_hash_audit["size_match"]).sum()),
            "trades_recomputed_sha256": dataframe_digest(ledger),
            "monthly_recomputed_sha256": dataframe_digest(monthly),
            "ticker_summary_recomputed_sha256": dataframe_digest(ticker_summary),
            "cost_sensitivity_recomputed_sha256": dataframe_digest(sensitivity),
            "source_hash_audit_sha256": dataframe_digest(source_hash_audit),
            "evaluation_summary_sha256": sha256_file(input_dir / "SUMMARY.json"),
            "auditor_sha256": sha256_file(Path(__file__).resolve()),
            "output_sha256": {
                name: sha256_file(staging / name) for name in output_names
            },
            "outer_2024_outcomes_reused": True,
            "new_outcome_source_read": False,
            "outer_2025_opened": False,
            "holdout_2026_opened": False,
            "production_modified": False,
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
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    audit = run(args.input_dir.resolve(), args.output_dir.resolve(), args.workers)
    print(json.dumps(audit, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
