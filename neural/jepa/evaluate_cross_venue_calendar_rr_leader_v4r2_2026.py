#!/usr/bin/env python3
"""Execute the frozen V4R2 cash-proxy outer 2026 exactly once."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa import (  # noqa: E402
    cross_venue_calendar_rr_leader_v4r2_2026_outer_common as common,
)
from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v2 as v2  # noqa: E402


DEFAULT_FROZEN_MANIFEST = common.FROZEN_MANIFEST
DEFAULT_OUTPUT = common.OUTER_DIR
OUTPUT_FILES = (
    "source_audit.csv",
    "trades.csv",
    "monthly_metrics.csv",
    "ticker_summary_closed_h1.csv",
    "july_mtd_summary.csv",
    "cost_sensitivity.csv",
    "SUMMARY.md",
)


def verify_frozen_manifest(path: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    common.validate_frozen_inputs()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    frozen_dir = path.parent
    events_path = frozen_dir / "events.parquet"
    model_path = frozen_dir / "model.json"
    if (
        manifest.get("schema")
        != "cross_venue_calendar_rr_leader_v4r2_outer_2026_frozen_v1"
        or manifest.get("status") != "PREEXECUTION_FROZEN"
        or manifest.get("mapping") != common.SENSOR_MAP
        or manifest.get("events") != 394
        or manifest.get("outcome_accessed") is not False
        or manifest.get("execution_started") is not False
        or manifest.get("open_1036_read") is not False
        or manifest.get("open_1336_read") is not False
        or manifest.get("outer_2026_opened") is not False
        or common.sha256_file(events_path) != manifest.get("events_sha256")
        or common.sha256_file(model_path) != manifest.get("model_sha256")
    ):
        raise AssertionError("V4R2 frozen manifest changed")
    expected_code_hashes = {
        relative.as_posix(): common.sha256_file(common.PROJECT_ROOT / relative)
        for relative in common.RUNNER_CODE_PATHS
    }
    expected_input_hashes = {
        str(input_path.relative_to(common.PROJECT_ROOT)).replace("\\", "/"): value
        for input_path, value in common.INPUT_HASHES.items()
    }
    if (
        manifest.get("code_hashes") != expected_code_hashes
        or manifest.get("input_hashes") != expected_input_hashes
    ):
        raise AssertionError("V4R2 frozen runner/input closure changed")
    events = pd.read_parquet(events_path)
    if (
        common.dataframe_digest(events) != manifest.get("events_recomputed_sha256")
        or common.ordered_hash(
            f"{row.ticker}|{row.trade_date}" for row in events.itertuples()
        )
        != manifest.get("event_id_sha256")
    ):
        raise AssertionError("V4R2 frozen events changed")
    training = common.load_final_training()
    model = v2.make_model()
    model.fit(training[list(common.FEATURE_COLUMNS)], training["direct_win"])
    model_payload = common.serialize_model(model, training)
    stored_model = json.loads(model_path.read_text(encoding="utf-8"))
    probabilities = model.predict_proba(events[list(common.FEATURE_COLUMNS)])[:, 1]
    if (
        model_payload != stored_model
        or not np.allclose(
            probabilities,
            events["direct_probability"].to_numpy(dtype=float),
            rtol=0.0,
            atol=1e-15,
        )
        or not np.array_equal(
            np.where(probabilities >= 0.5, 1, -1),
            events["orientation"].to_numpy(dtype=np.int64),
        )
    ):
        raise AssertionError("V4R2 frozen model/predictions changed")
    for record in events.itertuples(index=False):
        source = Path(str(record.source_path))
        if (
            not source.is_file()
            or source.stat().st_size != int(record.source_size_bytes)
            or common.sha256_file(source) != str(record.source_sha256)
        ):
            raise AssertionError(f"V4R2 frozen outcome source changed: {source}")
    return manifest, events


def _timestamp(trade_date: str, clock: str) -> pd.Timestamp:
    return pd.Timestamp(
        f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} {clock}"
    )


def read_two_opens(path: Path, ticker: str, trade_date: str) -> tuple[float, float]:
    frame = pd.read_parquet(path, columns=["symbol", "date", "timestamp", "open"])
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame["date"] = frame["date"].astype(str).str.replace("-", "", regex=False)
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
        or not selected["open"].gt(0.0).all()
    ):
        raise AssertionError(f"V4R2 exact outcome clocks failed: {path}")
    values = selected.set_index("timestamp")["open"]
    return float(values.loc[entry]), float(values.loc[exit_value])


def evaluate_event(record: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    path = Path(str(record.source_path))
    entry_open, exit_open = read_two_opens(
        path, str(record.ticker), str(record.trade_date)
    )
    underlying_return = float(np.log(exit_open / entry_open) * 10_000.0)
    gross = float(int(record.side) * underlying_return)
    row = {
        "ticker": str(record.ticker),
        "trade_date": str(record.trade_date),
        "month": str(record.month),
        "sensor_ticker": str(record.sensor_ticker),
        "signal_pressure": float(record.signal_pressure),
        "base_side": int(record.base_side),
        "direct_probability": float(record.direct_probability),
        "orientation": int(record.orientation),
        "side": int(record.side),
        "entry_open": entry_open,
        "exit_open": exit_open,
        "underlying_return_bps": underlying_return,
        "base_gross_bps": float(int(record.base_side) * underlying_return),
        "gross_bps": gross,
        "net_bps_1bp": gross - 1.0,
        "net_bps_2bp": gross - 2.0,
        "net_bps_3bp": gross - 3.0,
        "net_bps": gross - 1.0,
    }
    audit = {
        "ticker": str(record.ticker),
        "trade_date": str(record.trade_date),
        "path": str(path),
        "size_bytes": int(path.stat().st_size),
        "sha256": common.sha256_file(path),
        "rows_read": 2,
        "entry_time": "10:36:00",
        "exit_time": "13:36:00",
    }
    return row, audit


def build_ledger(events: pd.DataFrame, workers: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(evaluate_event, record)
            for record in events.itertuples(index=False)
        ]
        for future in as_completed(futures):
            row, audit = future.result()
            rows.append(row)
            audits.append(audit)
    ledger = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    source_audit = pd.DataFrame(audits).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if len(ledger) != 394 or len(source_audit) != 394:
        raise AssertionError("V4R2 outer coverage failed")
    return ledger, source_audit


def summarize_monthly(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in common.TICKERS:
        for month in common.MONTHS:
            net = ledger.loc[
                ledger["ticker"].eq(ticker) & ledger["month"].eq(month), "net_bps"
            ].to_numpy(dtype=float)
            rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "trades": int(len(net)),
                    "win_rate": float(np.mean(net > 0.0)),
                    "profit_factor": common.profit_factor(net),
                    "net_bps": float(net.sum()),
                    "frequency_pass": int(len(net)) >= 13,
                    "pnl_positive": bool(net.sum() > 0.0),
                    "month_complete": month in common.CLOSED_MONTHS,
                    "july_mtd": month == common.JULY_MTD,
                }
            )
    return pd.DataFrame(rows)


def summarize_closed_h1(ledger: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in common.TICKERS:
        selected = ledger.loc[
            ledger["ticker"].eq(ticker) & ledger["month"].isin(common.CLOSED_MONTHS)
        ]
        cells = monthly.loc[
            monthly["ticker"].eq(ticker) & monthly["month_complete"]
        ]
        net = selected["net_bps"].to_numpy(dtype=float)
        pf = common.profit_factor(net)
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
                "objective_gate_pass": bool(
                    pf > 1.20
                    and win_rate > 0.45
                    and pnl > 0.0
                    and minimum >= 13
                    and positive == 6
                ),
            }
        )
    return pd.DataFrame(rows)


def summarize_july(monthly: pd.DataFrame) -> pd.DataFrame:
    result = monthly.loc[monthly["month"].eq(common.JULY_MTD)].copy()
    result["july_mtd_net_positive"] = result["net_bps"].gt(0.0)
    return result.drop(columns=["month_complete", "july_mtd"]).reset_index(drop=True)


def summarize_sensitivity(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    periods = {
        "CLOSED_H1": common.CLOSED_MONTHS,
        "JULY_MTD": (common.JULY_MTD,),
        "ALL_AVAILABLE": common.MONTHS,
    }
    for period, months in periods.items():
        for scope in (*common.TICKERS, "POOLED"):
            selected = ledger.loc[ledger["month"].isin(months)]
            if scope != "POOLED":
                selected = selected.loc[selected["ticker"].eq(scope)]
            for cost in common.COSTS_BPS:
                net = selected[f"net_bps_{int(cost)}bp"].to_numpy(dtype=float)
                rows.append(
                    {
                        "period": period,
                        "scope": scope,
                        "cost_bps": cost,
                        "trades": int(len(net)),
                        "win_rate": float(np.mean(net > 0.0)),
                        "profit_factor": common.profit_factor(net),
                        "net_bps": float(net.sum()),
                    }
                )
    return pd.DataFrame(rows)


def run(output_dir: Path, frozen_manifest: Path, workers: int) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V4R2 outer output exists: {output_dir}")
    if not 1 <= workers <= 16:
        raise ValueError("workers must be in [1, 16]")
    common.tracked_worktree_clean()
    manifest, events = verify_frozen_manifest(frozen_manifest)
    ledger, source_audit = build_ledger(events, workers)
    monthly = summarize_monthly(ledger)
    tickers = summarize_closed_h1(ledger, monthly)
    july = summarize_july(monthly)
    sensitivity = summarize_sensitivity(ledger)
    objective = bool(tickers["objective_gate_pass"].all())
    july_positive = bool(july["july_mtd_net_positive"].all())
    passed = objective and july_positive
    status = (
        "PASS_OUTER_2026_CASH_PROXY_PHYSICAL_PENDING"
        if passed
        else "FAILED_OUTER_2026_NOT_PROMOTABLE"
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        source_audit.to_csv(staging / "source_audit.csv", index=False, lineterminator="\n")
        ledger.to_csv(staging / "trades.csv", index=False, lineterminator="\n")
        monthly.to_csv(staging / "monthly_metrics.csv", index=False, lineterminator="\n")
        tickers.to_csv(
            staging / "ticker_summary_closed_h1.csv", index=False, lineterminator="\n"
        )
        july.to_csv(staging / "july_mtd_summary.csv", index=False, lineterminator="\n")
        sensitivity.to_csv(
            staging / "cost_sensitivity.csv", index=False, lineterminator="\n"
        )
        lines = [
            "# CROSS_VENUE_CALENDAR_RR_LEADER_V4R2 outer 2026",
            "",
            f"Status: `{status}`.",
            "",
            "| Ticker | H1 trades | WR | PF | Net bps | Min/month | Positive months |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in tickers.itertuples(index=False):
            lines.append(
                f"| {row.ticker} | {row.trades} | {row.win_rate:.6%} | "
                f"{row.profit_factor:.6f} | {row.net_bps:.3f} | "
                f"{row.min_month_trades} | {row.positive_months} |"
            )
        lines.extend(["", "July is MTD through 2026-07-24 and is reported separately."])
        (staging / "SUMMARY.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
        )
        summary = {
            "schema": "cross_venue_calendar_rr_leader_v4r2_outer_2026_v1",
            "status": status,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "execution_commit": common.current_git_commit(),
            "frozen_manifest_sha256": common.sha256_file(frozen_manifest),
            "frozen_runner_commit": manifest["runner_commit"],
            "eligible_events": int(len(events)),
            "executed_trades": int(len(ledger)),
            "closed_h1_objective_gate_pass": objective,
            "july_mtd_all_tickers_net_positive": july_positive,
            "advance_to_physical_payoff": passed,
            "mapping": common.SENSOR_MAP,
            "outer_2026_opened": True,
            "july_mtd_end": "2026-07-24",
            "physical_option_payoff_opened": False,
            "production_modified": False,
            "live_or_systemd_modified": False,
            "output_sha256": {
                name: common.sha256_file(staging / name) for name in OUTPUT_FILES
            },
            "trades_recomputed_sha256": common.dataframe_digest(ledger),
            "monthly_recomputed_sha256": common.dataframe_digest(monthly),
            "ticker_summary_recomputed_sha256": common.dataframe_digest(tickers),
            "july_mtd_recomputed_sha256": common.dataframe_digest(july),
            "cost_sensitivity_recomputed_sha256": common.dataframe_digest(sensitivity),
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
    parser.add_argument(
        "--frozen-manifest", type=Path, default=DEFAULT_FROZEN_MANIFEST
    )
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(
        args.output_dir.resolve(), args.frozen_manifest.resolve(), args.workers
    )
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
