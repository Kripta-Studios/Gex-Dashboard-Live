"""Independent artifact audit for EXISTING_DATA_EXECUTABLE_UTILITY_V1."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from neural.jepa.audit_existing_data_edge_join_inventory_v1 import ROOT, sha256_file
from neural.jepa.evaluate_existing_data_executable_utility_v1 import (
    INNER_GATES,
    MODEL_FAMILIES,
    OUTER_MONTHS,
    economic_metrics,
    month_add,
    runner_protocol_sha256,
)
from neural.jepa.existing_data_edge_scheduler_v1 import SCHEDULER


DEFAULT_RESULTS = ROOT / "research_papers/JEPA/results/_diagnostics/existing_data_executable_utility_v1_202401_202512"
DEFAULT_FREEZE = ROOT / "research_papers/JEPA/results/_diagnostics/existing_data_executable_utility_v1_frozen_runner/manifest.json"


def _close(left: Any, right: Any, tolerance: float = 1e-10) -> bool:
    a, b = float(left), float(right)
    if math.isnan(a) and math.isnan(b):
        return True
    if math.isinf(a) or math.isinf(b):
        return a == b
    return abs(a - b) <= tolerance


def _assert_rank(selection: pd.Series, grids: pd.DataFrame) -> None:
    passing = grids.loc[grids["passed"].astype(bool)].copy()
    count = int(len(passing))
    if int(selection["passing_grid_count"]) != count:
        raise AssertionError("selection passing-grid count mismatch")
    if count == 0:
        if selection["status"] != "ABSTAIN_OUTER":
            raise AssertionError("fold traded without a passing inner grid")
        return
    if selection["status"] != "TRADE_OUTER":
        raise AssertionError("fold abstained despite a passing inner grid")
    rank_cols = [
        "worst_inner_month_pnl", "worst_inner_month_pf", "worst_inner_month_wr",
        "minimum_inner_month_trades", "pooled_inner_pnl", "pooled_inner_pf",
        "utility_percentile", "margin_percentile",
    ]
    chosen = passing.sort_values(rank_cols, ascending=False, kind="stable").iloc[0]
    for field in ("utility_percentile", "margin_percentile", "utility_threshold", "side_margin"):
        if not _close(selection[field], chosen[field]):
            raise AssertionError(f"selected inner grid is not frozen-rank maximum: {field}")


def _audit_scheduler(trades: pd.DataFrame) -> None:
    if trades.duplicated(["arm", "model_family", "ticker", "trade_date", "minute"]).any():
        raise AssertionError("duplicate scheduled trade decision")
    for (arm, family, ticker, date), day in trades.groupby(
        ["arm", "model_family", "ticker", "trade_date"], observed=True, sort=False
    ):
        config = SCHEDULER[str(ticker)]
        ordered = day.sort_values("minute", kind="stable")
        if len(ordered) > int(config["max_trades_per_day"]):
            raise AssertionError(f"daily cap violation: {arm}/{family}/{ticker}/{date}")
        prior_entry: float | None = None
        prior_exit: float | None = None
        for row in ordered.itertuples(index=False):
            entry = float(row.minute)
            if prior_exit is not None and entry < prior_exit:
                raise AssertionError("position overlap in published trades")
            if prior_entry is not None and entry < prior_entry + int(config["cooldown_minutes"]):
                raise AssertionError("cooldown violation in published trades")
            prior_entry = entry
            prior_exit = entry + float(row.exit_minutes)
            bucket = int(config["bucket"])
            side = str(row.action).lower()
            expected_return = float(getattr(row, f"{side}_d{bucket:02d}_opt_exit_ret"))
            expected_exit = float(getattr(row, f"{side}_d{bucket:02d}_opt_exit_minutes"))
            if not _close(row.realized_return, expected_return) or not _close(row.exit_minutes, expected_exit):
                raise AssertionError("published trade is not bound to selected ask-to-bid side payoff")


def _audit_monthly(monthly: pd.DataFrame, trades: pd.DataFrame) -> None:
    numeric = [
        "trades", "win_rate", "profit_factor", "pnl", "minimum_hold", "maximum_hold",
        "max_drawdown", "call_rate", "put_rate",
    ]
    for row in monthly.itertuples(index=False):
        part = trades.loc[
            trades["arm"].eq(row.arm)
            & trades["model_family"].eq(row.model_family)
            & trades["ticker"].eq(row.ticker)
            & trades["outer_month"].astype(str).eq(str(row.outer_month))
        ]
        metric = economic_metrics(part)
        for field in numeric:
            if not _close(getattr(row, field), metric[field]):
                raise AssertionError(f"monthly metric mismatch: {row.arm}/{row.model_family}/{row.ticker}/{row.outer_month}/{field}")
        expected_gate = bool(
            metric["profit_factor"] >= INNER_GATES["profit_factor"]
            and metric["win_rate"] >= INNER_GATES["win_rate"]
            and metric["trades"] >= INNER_GATES["trades"]
            and metric["pnl"] > INNER_GATES["pnl"]
            and np.isfinite(metric["minimum_hold"])
            and metric["minimum_hold"] >= INNER_GATES["minimum_hold"]
        )
        if bool(row.gate_pass) != expected_gate:
            raise AssertionError("published outer gate flag mismatch")


def audit(results_dir: Path, freeze_path: Path) -> dict[str, Any]:
    summary = json.loads((results_dir / "SUMMARY.json").read_text(encoding="utf-8"))
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if (
        summary.get("mode") != "frozen_outer"
        or summary.get("outer_months") != list(OUTER_MONTHS)
        or summary.get("runner_protocol_sha256") != runner_protocol_sha256()
        or summary.get("runner_protocol_sha256") != freeze.get("runner_protocol_sha256")
        or summary.get("holdout_2026_opened") is not False
        or summary.get("june_2026_sealed") is not True
        or summary.get("production_modified") is not False
    ):
        raise AssertionError("result/freeze boundary mismatch")
    for name, metadata in summary["files"].items():
        path = results_dir / name
        if metadata["sha256"] != sha256_file(path) or int(metadata["bytes"]) != path.stat().st_size:
            raise AssertionError(f"published result hash mismatch: {name}")

    selections = pd.read_csv(results_dir / "fold_selections.csv", dtype={"outer_month": str})
    grids = pd.read_csv(results_dir / "inner_grid.csv", dtype={"outer_month": str})
    monthly = pd.read_csv(results_dir / "monthly_metrics.csv", dtype={"outer_month": str})
    trades = pd.read_csv(results_dir / "outer_trades.csv", dtype={"outer_month": str, "trade_date": str})
    portfolio = pd.read_csv(results_dir / "portfolio_summary.csv")
    expected_cells = len(OUTER_MONTHS) * 3 * 2 * 2
    if len(selections) != expected_cells or len(monthly) != expected_cells or len(grids) != expected_cells * 42:
        raise AssertionError("published fold/grid/month cell count mismatch")
    if set(selections["outer_month"]) != set(OUTER_MONTHS):
        raise AssertionError("outer month coverage mismatch")
    if set(selections["model_family"]) != set(MODEL_FAMILIES) or set(selections["arm"]) != {"E0", "E1"}:
        raise AssertionError("published arm/model portfolio mismatch")

    group_key = ["outer_month", "ticker", "arm", "model_family"]
    for key, group in grids.groupby(group_key, observed=True, sort=False):
        selection = selections.loc[
            selections["outer_month"].eq(key[0])
            & selections["ticker"].eq(key[1])
            & selections["arm"].eq(key[2])
            & selections["model_family"].eq(key[3])
        ]
        if len(selection) != 1 or len(group) != 42:
            raise AssertionError("grid-to-selection cardinality mismatch")
        _assert_rank(selection.iloc[0], group)
        inner = [month_add(key[0], offset) for offset in (-3, -2, -1)]
        if selection.iloc[0]["inner_months"].split(",") != inner:
            raise AssertionError("inner calendar months mismatch")
        if str(selection.iloc[0]["train_date_max"])[:6] >= inner[0] or inner[-1] >= key[0]:
            raise AssertionError("train/inner/outer chronology mismatch")

    if trades["trade_date"].astype(str).str[:4].eq("2026").any():
        raise AssertionError("2026 entered published trades")
    _audit_scheduler(trades)
    _audit_monthly(monthly, trades)
    e1 = monthly.loc[monthly["arm"].eq("E1")]
    if len(e1) != 144 or not e1["status"].eq("ABSTAIN_OUTER").all() or int(e1["trades"].sum()) != 0:
        raise AssertionError("E1 did not fully abstain as summarized")
    if bool(summary.get("candidate_found")) or summary.get("verdict") != "NO_EDGE_IN_EXISTING_DATA":
        raise AssertionError("candidate/verdict mismatch")
    if bool(portfolio["scientific_candidate"].astype(bool).any()):
        raise AssertionError("portfolio unexpectedly marks a scientific candidate")

    traded = monthly.loc[monthly["status"].eq("TRADE_OUTER")]
    audit_payload = {
        "schema": "existing_data_executable_utility_v1_independent_audit",
        "status": "PASS_RESULT_AUDIT",
        "verdict": "NO_EDGE_IN_EXISTING_DATA",
        "summary_sha256": sha256_file(results_dir / "SUMMARY.json"),
        "freeze_manifest_sha256": sha256_file(freeze_path),
        "fold_cells": len(selections),
        "inner_grid_rows": len(grids),
        "outer_monthly_cells": len(monthly),
        "published_trades": len(trades),
        "trade_outer_cells": len(traded),
        "abstain_outer_cells": int(monthly["status"].eq("ABSTAIN_OUTER").sum()),
        "passing_inner_grids": {
            f"{arm}/{family}": int(group["passed"].astype(bool).sum())
            for (arm, family), group in grids.groupby(["arm", "model_family"], observed=True)
        },
        "outer_gate_pass_cells": int(monthly["gate_pass"].astype(bool).sum()),
        "E1_trade_cells": 0,
        "E1_trades": 0,
        "stress_authorized": False,
        "stress_reason": "base candidate contract failed; execution stress is forbidden before base pass",
        "holdout_2026_opened": False,
        "june_2026_sealed": True,
        "production_modified": False,
        "checks": [
            "file hashes and sizes", "288 fold/month cells", "42 train-only grids per fold",
            "frozen lexicographic inner selection", "expanding train/three-inner/one-outer chronology",
            "ask-to-bid side payoff binding", "daily caps/cooldown/no overlap/equal-exit convention",
            "monthly metric recomputation", "full E1 abstention", "2026 exclusion",
        ],
    }
    (results_dir / "AUDIT.json").write_text(json.dumps(audit_payload, indent=2) + "\n", encoding="utf-8")
    return {**audit_payload, "audit_sha256": sha256_file(results_dir / "AUDIT.json")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS.relative_to(ROOT)))
    parser.add_argument("--freeze", default=str(DEFAULT_FREEZE.relative_to(ROOT)))
    args = parser.parse_args()
    result = audit(ROOT / args.results_dir, ROOT / args.freeze)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
