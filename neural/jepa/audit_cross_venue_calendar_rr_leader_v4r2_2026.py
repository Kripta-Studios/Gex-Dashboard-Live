#!/usr/bin/env python3
"""Independently audit the frozen V4R2 cash-proxy outer 2026."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
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
from neural.jepa import (  # noqa: E402
    evaluate_cross_venue_calendar_rr_leader_v4r2_2026 as outer,
)
from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v2 as v2  # noqa: E402


DEFAULT_INPUT = common.OUTER_DIR
DEFAULT_OUTPUT = common.OUTER_AUDIT_DIR


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
        elif column in right.columns and pd.api.types.is_string_dtype(left[column]):
            right[column] = right[column].fillna("").astype(str)
    try:
        pd.testing.assert_frame_equal(
            left,
            right[left.columns],
            check_dtype=False,
            rtol=1e-12,
            atol=1e-12,
        )
    except AssertionError as error:
        raise AssertionError(f"V4R2 stored {label} differs from audit") from error


def _timestamp(trade_date: str, clock: str) -> pd.Timestamp:
    return pd.Timestamp(
        f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} {clock}"
    )


def read_two_opens_independent(
    path: Path, ticker: str, trade_date: str
) -> tuple[float, float]:
    frame = pd.read_parquet(path, columns=["symbol", "date", "timestamp", "open"])
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame["date"] = frame["date"].astype(str).str.replace("-", "", regex=False)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame["open"] = pd.to_numeric(frame["open"], errors="coerce")
    entry = _timestamp(trade_date, "10:36:00")
    exit_value = _timestamp(trade_date, "13:36:00")
    selected = frame.loc[frame["timestamp"].isin([entry, exit_value])]
    if (
        len(selected) != 2
        or selected.isna().any().any()
        or selected["timestamp"].duplicated().any()
        or set(selected["timestamp"]) != {entry, exit_value}
        or not selected["symbol"].eq(ticker).all()
        or not selected["date"].eq(trade_date).all()
        or not selected["open"].gt(0.0).all()
    ):
        raise AssertionError(f"V4R2 audit exact clocks failed: {path}")
    values = selected.set_index("timestamp")["open"]
    return float(values.loc[entry]), float(values.loc[exit_value])


def refit_and_load_events() -> tuple[pd.DataFrame, dict[str, Any]]:
    manifest = json.loads(common.FROZEN_MANIFEST.read_text(encoding="utf-8"))
    events_path = common.FROZEN_DIR / "events.parquet"
    model_path = common.FROZEN_DIR / "model.json"
    expected_code_hashes = {
        relative.as_posix(): common.sha256_file(common.PROJECT_ROOT / relative)
        for relative in common.RUNNER_CODE_PATHS
    }
    expected_input_hashes = {
        str(input_path.relative_to(common.PROJECT_ROOT)).replace("\\", "/"): value
        for input_path, value in common.INPUT_HASHES.items()
    }
    if (
        manifest.get("schema")
        != "cross_venue_calendar_rr_leader_v4r2_outer_2026_frozen_v1"
        or manifest.get("status") != "PREEXECUTION_FROZEN"
        or manifest.get("code_hashes") != expected_code_hashes
        or manifest.get("input_hashes") != expected_input_hashes
        or common.sha256_file(events_path) != manifest.get("events_sha256")
        or common.sha256_file(model_path) != manifest.get("model_sha256")
        or manifest.get("outcome_accessed") is not False
        or manifest.get("execution_started") is not False
    ):
        raise AssertionError("V4R2 audit frozen manifest closure changed")
    events = pd.read_parquet(events_path)
    training = common.load_final_training()
    model = v2.make_model()
    model.fit(training[list(common.FEATURE_COLUMNS)], training["direct_win"])
    stored_model = json.loads(
        model_path.read_text(encoding="utf-8")
    )
    probabilities = model.predict_proba(events[list(common.FEATURE_COLUMNS)])[:, 1]
    orientations = np.where(probabilities >= 0.5, 1, -1).astype(np.int64)
    if (
        common.serialize_model(model, training) != stored_model
        or not np.allclose(
            probabilities,
            events["direct_probability"].to_numpy(dtype=float),
            rtol=0.0,
            atol=1e-15,
        )
        or not np.array_equal(
            orientations, events["orientation"].to_numpy(dtype=np.int64)
        )
        or common.dataframe_digest(events) != manifest["events_recomputed_sha256"]
    ):
        raise AssertionError("V4R2 audit frozen model/event mismatch")
    return events, manifest


def recompute_ledger(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    trades: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for record in events.itertuples(index=False):
        path = Path(str(record.source_path))
        if (
            not path.is_file()
            or path.stat().st_size != int(record.source_size_bytes)
            or common.sha256_file(path) != str(record.source_sha256)
        ):
            raise AssertionError(f"V4R2 audit source changed: {path}")
        entry_open, exit_open = read_two_opens_independent(
            path, str(record.ticker), str(record.trade_date)
        )
        underlying_return = float(np.log(exit_open / entry_open) * 10_000.0)
        gross = float(int(record.side) * underlying_return)
        trades.append(
            {
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
        )
        audits.append(
            {
                "ticker": str(record.ticker),
                "trade_date": str(record.trade_date),
                "path": str(path),
                "size_bytes": int(path.stat().st_size),
                "sha256": common.sha256_file(path),
                "rows_read": 2,
                "entry_time": "10:36:00",
                "exit_time": "13:36:00",
            }
        )
    ledger = pd.DataFrame(trades).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    source_audit = pd.DataFrame(audits).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    return ledger, source_audit


def summarize_independent(
    ledger: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    monthly_rows: list[dict[str, Any]] = []
    for ticker in common.TICKERS:
        for month in common.MONTHS:
            net = ledger.loc[
                ledger["ticker"].eq(ticker) & ledger["month"].eq(month), "net_bps"
            ].to_numpy(dtype=float)
            monthly_rows.append(
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
    monthly = pd.DataFrame(monthly_rows)
    ticker_rows: list[dict[str, Any]] = []
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
        ticker_rows.append(
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
    tickers = pd.DataFrame(ticker_rows)
    july = monthly.loc[monthly["month"].eq(common.JULY_MTD)].copy()
    july["july_mtd_net_positive"] = july["net_bps"].gt(0.0)
    july = july.drop(columns=["month_complete", "july_mtd"]).reset_index(drop=True)
    sensitivity_rows: list[dict[str, Any]] = []
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
                sensitivity_rows.append(
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
    return monthly, tickers, july, pd.DataFrame(sensitivity_rows)


def run(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V4R2 outer audit exists: {output_dir}")
    common.tracked_worktree_clean()
    summary = json.loads((input_dir / "SUMMARY.json").read_text(encoding="utf-8"))
    for name in (*outer.OUTPUT_FILES, "SUMMARY.json"):
        if not (input_dir / name).is_file():
            raise FileNotFoundError(input_dir / name)
    expected_hashes = summary.get("output_sha256")
    if not isinstance(expected_hashes, dict) or set(expected_hashes) != set(
        outer.OUTPUT_FILES
    ):
        raise AssertionError("V4R2 outer output closure changed")
    for name, expected in expected_hashes.items():
        if common.sha256_file(input_dir / name) != expected:
            raise AssertionError(f"V4R2 outer output hash mismatch: {name}")
    events, manifest = refit_and_load_events()
    if (
        common.sha256_file(common.FROZEN_MANIFEST)
        != summary.get("frozen_manifest_sha256")
        or manifest.get("runner_commit") != summary.get("frozen_runner_commit")
        or summary.get("outer_2026_opened") is not True
        or summary.get("physical_option_payoff_opened") is not False
        or summary.get("production_modified") is not False
    ):
        raise AssertionError("V4R2 outer summary contract changed")
    ledger, source_audit = recompute_ledger(events)
    monthly, tickers, july, sensitivity = summarize_independent(ledger)
    compare_frames(
        source_audit,
        pd.read_csv(input_dir / "source_audit.csv", dtype={"trade_date": str}),
        ["ticker", "trade_date"],
        "source audit",
    )
    compare_frames(
        ledger,
        pd.read_csv(
            input_dir / "trades.csv", dtype={"trade_date": str, "month": str}
        ),
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
        pd.read_csv(input_dir / "ticker_summary_closed_h1.csv"),
        ["ticker"],
        "ticker summary",
    )
    compare_frames(
        july,
        pd.read_csv(input_dir / "july_mtd_summary.csv", dtype={"month": str}),
        ["ticker"],
        "July MTD",
    )
    compare_frames(
        sensitivity,
        pd.read_csv(input_dir / "cost_sensitivity.csv"),
        ["period", "scope", "cost_bps"],
        "cost sensitivity",
    )
    objective = bool(tickers["objective_gate_pass"].all())
    july_positive = bool(july["july_mtd_net_positive"].all())
    passed = objective and july_positive
    expected_status = (
        "PASS_OUTER_2026_CASH_PROXY_PHYSICAL_PENDING"
        if passed
        else "FAILED_OUTER_2026_NOT_PROMOTABLE"
    )
    if (
        summary.get("status") != expected_status
        or summary.get("closed_h1_objective_gate_pass") is not objective
        or summary.get("july_mtd_all_tickers_net_positive") is not july_positive
        or summary.get("advance_to_physical_payoff") is not passed
        or summary.get("trades_recomputed_sha256") != common.dataframe_digest(ledger)
        or summary.get("monthly_recomputed_sha256") != common.dataframe_digest(monthly)
        or summary.get("ticker_summary_recomputed_sha256")
        != common.dataframe_digest(tickers)
        or summary.get("july_mtd_recomputed_sha256")
        != common.dataframe_digest(july)
        or summary.get("cost_sensitivity_recomputed_sha256")
        != common.dataframe_digest(sensitivity)
    ):
        raise AssertionError("V4R2 outer status/digest closure changed")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        tickers.to_csv(
            staging / "ticker_summary_recomputed.csv", index=False, lineterminator="\n"
        )
        july.to_csv(
            staging / "july_mtd_recomputed.csv", index=False, lineterminator="\n"
        )
        names = ("ticker_summary_recomputed.csv", "july_mtd_recomputed.csv")
        audit = {
            "schema": "cross_venue_calendar_rr_leader_v4r2_outer_2026_audit_v1",
            "status": "PASS_INDEPENDENT_V4R2_OUTER_2026_AUDIT",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "evaluation_commit": summary["execution_commit"],
            "audit_commit": common.current_git_commit(),
            "outer_status": expected_status,
            "eligible_events": int(len(events)),
            "source_files_rehashed": int(len(source_audit)),
            "source_mismatches": 0,
            "model_refit_exact": True,
            "prediction_vector_exact": True,
            "closed_h1_objective_gate_pass": objective,
            "july_mtd_all_tickers_net_positive": july_positive,
            "advance_to_physical_payoff": passed,
            "outer_2026_opened": True,
            "physical_option_payoff_opened": False,
            "production_modified": False,
            "live_or_systemd_modified": False,
            "evaluation_summary_sha256": common.sha256_file(
                input_dir / "SUMMARY.json"
            ),
            "trades_recomputed_sha256": common.dataframe_digest(ledger),
            "monthly_recomputed_sha256": common.dataframe_digest(monthly),
            "ticker_summary_recomputed_sha256": common.dataframe_digest(tickers),
            "july_mtd_recomputed_sha256": common.dataframe_digest(july),
            "cost_sensitivity_recomputed_sha256": common.dataframe_digest(
                sensitivity
            ),
            "output_sha256": {
                name: common.sha256_file(staging / name) for name in names
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
