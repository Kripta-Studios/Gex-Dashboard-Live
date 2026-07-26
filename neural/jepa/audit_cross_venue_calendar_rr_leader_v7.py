#!/usr/bin/env python3
"""Independently audit the V7 rolling-12 monthly development evaluation."""

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

from neural.jepa import cross_venue_calendar_rr_leader_v7_common as common  # noqa: E402
from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v2 as v2  # noqa: E402
from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v7 as evaluator  # noqa: E402


DEFAULT_INPUT = common.OUTPUT_DIR
DEFAULT_OUTPUT = common.AUDIT_DIR


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
        raise AssertionError(f"V7 stored {label} differs from audit") from error


def _profit_factor(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    gains = float(array[array > 0.0].sum())
    losses = float(-array[array < 0.0].sum())
    if losses == 0.0:
        return 1.0e12 if gains > 0.0 else 0.0
    return gains / losses


def recompute(
    input_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    history = common.load_history()
    labeled = common.load_labeled_2026()
    combined = common.combined_training(history, labeled)
    ledger_parts: list[pd.DataFrame] = []
    folds: list[dict[str, Any]] = []
    for month in common.MONTHS:
        training = common.training_for_month(combined, month)
        test = common.testing_for_month(labeled, month)
        model = v2.make_model()
        model.fit(training[list(common.FEATURE_COLUMNS)], training["direct_win"])
        probabilities = model.predict_proba(test[list(common.FEATURE_COLUMNS)])[:, 1]
        orientations = np.where(probabilities >= 0.5, 1, -1).astype(np.int64)
        model_payload = common.serialize_model(model, training, month)
        stored_model = json.loads(
            (input_dir / "model_artifacts" / f"model_{month}.json").read_text(
                encoding="utf-8"
            )
        )
        if model_payload != stored_model:
            raise AssertionError(f"V7 model artifact differs: {month}")

        ledger = test[
            [
                "ticker",
                "trade_date",
                "month",
                "sensor_ticker",
                "signal_pressure",
                "base_side",
                "entry_open",
                "exit_open",
                "underlying_return_bps",
                "base_gross_bps",
            ]
        ].copy()
        ledger["direct_probability"] = probabilities
        ledger["orientation"] = orientations
        ledger["side"] = ledger["base_side"].astype(np.int64) * orientations
        ledger["gross_bps"] = ledger["base_gross_bps"] * orientations
        for cost in common.COSTS_BPS:
            ledger[f"net_bps_{int(cost)}bp"] = ledger["gross_bps"] - float(cost)
        ledger["net_bps"] = ledger["net_bps_1bp"]
        ledger["train_month_start"], ledger["train_month_end"] = common.fold_bounds(
            month
        )
        ledger = ledger.sort_values(
            ["ticker", "trade_date"], kind="stable"
        ).reset_index(drop=True)
        fold_predictions = pd.read_csv(
            input_dir / "fold_predictions" / f"predictions_{month}.csv",
            dtype={"trade_date": str, "month": str, "train_month_start": str, "train_month_end": str},
        )
        compare_frames(
            ledger[
                [
                    "ticker",
                    "trade_date",
                    "month",
                    "direct_probability",
                    "orientation",
                    "base_side",
                    "side",
                    "train_month_start",
                    "train_month_end",
                ]
            ],
            fold_predictions,
            ["ticker", "trade_date"],
            f"fold predictions {month}",
        )
        train_counts = training.groupby("ticker").size().reindex(common.TICKERS)
        test_counts = test.groupby("ticker").size().reindex(common.TICKERS)
        folds.append(
            {
                "test_month": month,
                "train_month_start": model_payload["train_month_start"],
                "train_month_end": model_payload["train_month_end"],
                "train_rows": int(len(training)),
                "test_rows": int(len(test)),
                "train_ticker_counts": "/".join(str(int(x)) for x in train_counts),
                "test_ticker_counts": "/".join(str(int(x)) for x in test_counts),
                "training_recomputed_sha256": model_payload[
                    "training_recomputed_sha256"
                ],
                "causal_fold_pass": bool(training["month"].lt(month).all()),
            }
        )
        ledger_parts.append(ledger)

    trades = pd.concat(ledger_parts, ignore_index=True).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    fold_frame = pd.DataFrame(folds)
    monthly_rows: list[dict[str, Any]] = []
    for ticker in common.TICKERS:
        for month in common.MONTHS:
            net = trades.loc[
                trades["ticker"].eq(ticker) & trades["month"].eq(month),
                "net_bps",
            ].to_numpy(dtype=float)
            monthly_rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "trades": int(len(net)),
                    "win_rate": float(np.mean(net > 0.0)),
                    "profit_factor": _profit_factor(net),
                    "net_bps": float(net.sum()),
                    "frequency_pass": int(len(net)) >= 13,
                    "pnl_positive": bool(net.sum() > 0.0),
                    "month_complete": month in common.CLOSED_MONTHS,
                    "july_mtd": month == common.JULY_MTD,
                }
            )
    monthly = pd.DataFrame(monthly_rows)
    h1_rows: list[dict[str, Any]] = []
    for ticker in common.TICKERS:
        selected = trades.loc[
            trades["ticker"].eq(ticker)
            & trades["month"].isin(common.CLOSED_MONTHS)
        ]
        cells = monthly.loc[
            monthly["ticker"].eq(ticker) & monthly["month_complete"]
        ]
        net = selected["net_bps"].to_numpy(dtype=float)
        pf = _profit_factor(net)
        wr = float(np.mean(net > 0.0))
        pnl = float(net.sum())
        minimum = int(cells["trades"].min())
        positive = int(cells["pnl_positive"].sum())
        h1_rows.append(
            {
                "ticker": ticker,
                "trades": int(len(net)),
                "win_rate": wr,
                "profit_factor": pf,
                "net_bps": pnl,
                "min_month_trades": minimum,
                "positive_months": positive,
                "development_gate_pass": bool(
                    pf > 1.20
                    and wr > 0.45
                    and pnl > 0.0
                    and minimum >= 13
                    and positive == 6
                ),
            }
        )
    h1 = pd.DataFrame(h1_rows)
    july = monthly.loc[monthly["month"].eq(common.JULY_MTD)].copy()
    july["july_mtd_health_pass"] = (
        july["profit_factor"].gt(1.20)
        & july["win_rate"].gt(0.45)
        & july["net_bps"].gt(0.0)
    )
    july = july.drop(columns=["month_complete", "july_mtd"]).reset_index(drop=True)
    return trades, fold_frame, monthly, h1, july


def run(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V7 audit output exists: {output_dir}")
    common.v4r2.tracked_worktree_clean()
    common.validate_inputs()
    summary_path = input_dir / "SUMMARY.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    expected_files = [*evaluator.TABLE_FILES]
    expected_files.extend(
        f"model_artifacts/model_{month}.json" for month in common.MONTHS
    )
    expected_files.extend(
        f"fold_predictions/predictions_{month}.csv" for month in common.MONTHS
    )
    if (
        summary.get("schema")
        != "cross_venue_calendar_rr_leader_v7_development_v1"
        or summary.get("runner_commit") != common.v4r2.current_git_commit()
        or summary.get("code_hashes") != common.code_hashes()
        or summary.get("input_hashes") != common.input_hashes_relative()
        or set(summary.get("output_sha256", {})) != set(expected_files)
        or summary.get("outcome_2026_already_seen") is not True
        or summary.get("development_only") is not True
        or summary.get("promotable") is not False
        or summary.get("physical_option_payoff_opened") is not False
        or summary.get("production_modified") is not False
    ):
        raise AssertionError("V7 evaluation summary closure changed")
    for name, expected in summary["output_sha256"].items():
        if common.v4r2.sha256_file(input_dir / name) != expected:
            raise AssertionError(f"V7 output hash changed: {name}")

    trades, folds, monthly, h1, july = recompute(input_dir)
    compare_frames(
        trades,
        pd.read_csv(
            input_dir / "trades.csv", dtype={"trade_date": str, "month": str}
        ),
        ["ticker", "trade_date"],
        "trades",
    )
    compare_frames(
        folds,
        pd.read_csv(
            input_dir / "folds.csv",
            dtype={"test_month": str, "train_month_start": str, "train_month_end": str},
        ),
        ["test_month"],
        "folds",
    )
    compare_frames(
        monthly,
        pd.read_csv(input_dir / "monthly_metrics.csv", dtype={"month": str}),
        ["ticker", "month"],
        "monthly metrics",
    )
    compare_frames(
        h1,
        pd.read_csv(input_dir / "ticker_summary_closed_h1.csv"),
        ["ticker"],
        "H1 summary",
    )
    compare_frames(
        july,
        pd.read_csv(input_dir / "july_mtd_summary.csv", dtype={"month": str}),
        ["ticker"],
        "July MTD summary",
    )
    h1_pass = bool(h1["development_gate_pass"].all())
    july_pass = bool(july["july_mtd_health_pass"].all())
    expected_status = (
        "PASS_DEVELOPMENT_GATE_FUTURE_OUTER_REQUIRED"
        if h1_pass and july_pass
        else "FAILED_DEVELOPMENT_NOT_STABLE"
    )
    if (
        summary.get("status") != expected_status
        or summary.get("h1_gate_pass") is not h1_pass
        or summary.get("july_mtd_health_pass") is not july_pass
        or summary.get("trades") != len(trades)
        or summary.get("folds") != len(folds)
    ):
        raise AssertionError("V7 stored gates differ from audit")

    audit_summary = {
        "schema": "cross_venue_calendar_rr_leader_v7_audit_v1",
        "status": "PASS_INDEPENDENT_V7_DEVELOPMENT_AUDIT",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_summary_sha256": common.v4r2.sha256_file(summary_path),
        "models_refit": 7,
        "probability_vectors_exact": True,
        "ledger_rows": int(len(trades)),
        "folds_recomputed": int(len(folds)),
        "input_hash_mismatches": 0,
        "output_hash_mismatches": 0,
        "h1_gate_pass": h1_pass,
        "july_mtd_health_pass": july_pass,
        "outcome_2026_already_seen": True,
        "development_only": True,
        "promotable": False,
        "physical_option_payoff_opened": False,
        "production_modified": False,
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        monthly.to_csv(
            staging / "monthly_metrics_recomputed.csv",
            index=False,
            lineterminator="\n",
        )
        h1.to_csv(
            staging / "ticker_summary_closed_h1_recomputed.csv",
            index=False,
            lineterminator="\n",
        )
        july.to_csv(
            staging / "july_mtd_summary_recomputed.csv",
            index=False,
            lineterminator="\n",
        )
        (staging / "audit_summary.json").write_text(
            json.dumps(audit_summary, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        os.replace(staging, output_dir)
        return audit_summary
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(args.input, args.output)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
