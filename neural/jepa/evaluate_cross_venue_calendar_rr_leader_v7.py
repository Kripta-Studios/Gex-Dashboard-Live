#!/usr/bin/env python3
"""Run the single predeclared V7 rolling-12 monthly development evaluation."""

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


DEFAULT_OUTPUT = common.OUTPUT_DIR
TABLE_FILES = (
    "folds.csv",
    "predictions.csv",
    "trades.csv",
    "monthly_metrics.csv",
    "ticker_summary_closed_h1.csv",
    "july_mtd_summary.csv",
    "cost_sensitivity.csv",
    "SUMMARY.md",
)


def profit_factor(values: Iterable[float]) -> float:
    return common.v4r2.profit_factor(values)


def fit_fold(
    combined: pd.DataFrame,
    labeled_2026: pd.DataFrame,
    month: str,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    training = common.training_for_month(combined, month)
    test = common.testing_for_month(labeled_2026, month)
    model = v2.make_model()
    model.fit(training[list(common.FEATURE_COLUMNS)], training["direct_win"])
    probabilities = model.predict_proba(test[list(common.FEATURE_COLUMNS)])[:, 1]
    orientation = np.where(probabilities >= 0.5, 1, -1).astype(np.int64)
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
    ledger["orientation"] = orientation
    ledger["side"] = ledger["base_side"].astype(np.int64) * orientation
    ledger["gross_bps"] = ledger["base_gross_bps"] * orientation
    for cost in common.COSTS_BPS:
        ledger[f"net_bps_{int(cost)}bp"] = ledger["gross_bps"] - float(cost)
    ledger["net_bps"] = ledger["net_bps_1bp"]
    ledger["train_month_start"], ledger["train_month_end"] = common.fold_bounds(
        month
    )
    ledger = ledger.sort_values(["ticker", "trade_date"], kind="stable").reset_index(
        drop=True
    )
    model_payload = common.serialize_model(model, training, month)
    train_counts = training.groupby("ticker").size().reindex(common.TICKERS)
    test_counts = test.groupby("ticker").size().reindex(common.TICKERS)
    fold = {
        "test_month": month,
        "train_month_start": model_payload["train_month_start"],
        "train_month_end": model_payload["train_month_end"],
        "train_rows": int(len(training)),
        "test_rows": int(len(test)),
        "train_ticker_counts": "/".join(str(int(x)) for x in train_counts),
        "test_ticker_counts": "/".join(str(int(x)) for x in test_counts),
        "training_recomputed_sha256": model_payload["training_recomputed_sha256"],
        "causal_fold_pass": bool(training["month"].lt(month).all()),
    }
    return ledger, model_payload, fold


def summarize_monthly(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in common.TICKERS:
        for month in common.MONTHS:
            net = ledger.loc[
                ledger["ticker"].eq(ticker) & ledger["month"].eq(month),
                "net_bps",
            ].to_numpy(dtype=float)
            rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "trades": int(len(net)),
                    "win_rate": float(np.mean(net > 0.0)),
                    "profit_factor": profit_factor(net),
                    "net_bps": float(net.sum()),
                    "frequency_pass": int(len(net)) >= 13,
                    "pnl_positive": bool(net.sum() > 0.0),
                    "month_complete": month in common.CLOSED_MONTHS,
                    "july_mtd": month == common.JULY_MTD,
                }
            )
    return pd.DataFrame(rows)


def summarize_h1(ledger: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in common.TICKERS:
        selected = ledger.loc[
            ledger["ticker"].eq(ticker)
            & ledger["month"].isin(common.CLOSED_MONTHS)
        ]
        cells = monthly.loc[
            monthly["ticker"].eq(ticker) & monthly["month_complete"]
        ]
        net = selected["net_bps"].to_numpy(dtype=float)
        pf = profit_factor(net)
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
                "development_gate_pass": bool(
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
    july = monthly.loc[monthly["month"].eq(common.JULY_MTD)].copy()
    july["july_mtd_health_pass"] = (
        july["profit_factor"].gt(1.20)
        & july["win_rate"].gt(0.45)
        & july["net_bps"].gt(0.0)
    )
    return july.drop(columns=["month_complete", "july_mtd"]).reset_index(drop=True)


def summarize_costs(ledger: pd.DataFrame) -> pd.DataFrame:
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
                        "profit_factor": profit_factor(net),
                        "net_bps": float(net.sum()),
                    }
                )
    return pd.DataFrame(rows)


def summary_markdown(
    status: str,
    h1: pd.DataFrame,
    july: pd.DataFrame,
) -> str:
    lines = [
        "# V7 rolling12 monthly logistic — development 2026",
        "",
        f"Status: `{status}`.",
        "",
        "2026 ya estaba visto antes de predeclarar V7. Este resultado no es OOS ni promocionable.",
        "",
        "| Ticker | H1 trades | WR | PF | Net bps | Min/mes | Meses + | Gate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in h1.itertuples(index=False):
        lines.append(
            f"| {row.ticker} | {row.trades} | {row.win_rate:.3%} | "
            f"{row.profit_factor:.6f} | {row.net_bps:+.3f} | "
            f"{row.min_month_trades} | {row.positive_months}/6 | "
            f"{bool(row.development_gate_pass)} |"
        )
    lines.extend(
        [
            "",
            "| Ticker | Julio MTD trades | WR | PF | Net bps | Health |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in july.itertuples(index=False):
        lines.append(
            f"| {row.ticker} | {row.trades} | {row.win_rate:.3%} | "
            f"{row.profit_factor:.6f} | {row.net_bps:+.3f} | "
            f"{bool(row.july_mtd_health_pass)} |"
        )
    lines.extend(
        [
            "",
            "`physical_option_payoff_opened=false`; `production_modified=false`.",
            "",
        ]
    )
    return "\n".join(lines)


def run(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V7 output exists: {output_dir}")
    common.v4r2.tracked_worktree_clean()
    common.validate_inputs()
    history = common.load_history()
    labeled = common.load_labeled_2026()
    combined = common.combined_training(history, labeled)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    (staging / "model_artifacts").mkdir(parents=True)
    (staging / "fold_predictions").mkdir()
    ledgers: list[pd.DataFrame] = []
    folds: list[dict[str, Any]] = []
    try:
        for month in common.MONTHS:
            ledger, model_payload, fold = fit_fold(combined, labeled, month)
            (staging / "model_artifacts" / f"model_{month}.json").write_text(
                json.dumps(model_payload, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )
            prediction_columns = [
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
            ledger[prediction_columns].to_csv(
                staging / "fold_predictions" / f"predictions_{month}.csv",
                index=False,
                lineterminator="\n",
            )
            ledgers.append(ledger)
            folds.append(fold)

        trades = pd.concat(ledgers, ignore_index=True).sort_values(
            ["ticker", "trade_date"], kind="stable"
        ).reset_index(drop=True)
        if len(trades) != 394 or trades.duplicated(["ticker", "trade_date"]).any():
            raise AssertionError("V7 ledger coverage changed")
        predictions = trades[
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
        ].copy()
        fold_frame = pd.DataFrame(folds)
        monthly = summarize_monthly(trades)
        h1 = summarize_h1(trades, monthly)
        july = summarize_july(monthly)
        costs = summarize_costs(trades)
        h1_pass = bool(h1["development_gate_pass"].all())
        july_pass = bool(july["july_mtd_health_pass"].all())
        status = (
            "PASS_DEVELOPMENT_GATE_FUTURE_OUTER_REQUIRED"
            if h1_pass and july_pass
            else "FAILED_DEVELOPMENT_NOT_STABLE"
        )

        fold_frame.to_csv(staging / "folds.csv", index=False, lineterminator="\n")
        predictions.to_csv(
            staging / "predictions.csv", index=False, lineterminator="\n"
        )
        trades.to_csv(staging / "trades.csv", index=False, lineterminator="\n")
        monthly.to_csv(
            staging / "monthly_metrics.csv", index=False, lineterminator="\n"
        )
        h1.to_csv(
            staging / "ticker_summary_closed_h1.csv",
            index=False,
            lineterminator="\n",
        )
        july.to_csv(
            staging / "july_mtd_summary.csv", index=False, lineterminator="\n"
        )
        costs.to_csv(
            staging / "cost_sensitivity.csv", index=False, lineterminator="\n"
        )
        (staging / "SUMMARY.md").write_text(
            summary_markdown(status, h1, july), encoding="utf-8"
        )

        output_files = [*TABLE_FILES]
        output_files.extend(
            f"model_artifacts/model_{month}.json" for month in common.MONTHS
        )
        output_files.extend(
            f"fold_predictions/predictions_{month}.csv" for month in common.MONTHS
        )
        output_hashes = {
            name: common.v4r2.sha256_file(staging / name) for name in output_files
        }
        summary = {
            "schema": "cross_venue_calendar_rr_leader_v7_development_v1",
            "status": status,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "runner_commit": common.v4r2.current_git_commit(),
            "code_hashes": common.code_hashes(),
            "input_hashes": common.input_hashes_relative(),
            "folds": 7,
            "trades": 394,
            "h1_gate_pass": h1_pass,
            "july_mtd_health_pass": july_pass,
            "outcome_2026_already_seen": True,
            "development_only": True,
            "promotable": False,
            "physical_option_payoff_opened": False,
            "production_modified": False,
            "output_sha256": output_hashes,
        }
        (staging / "SUMMARY.json").write_text(
            json.dumps(summary, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )
        os.replace(staging, output_dir)
        return summary
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(args.output)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
