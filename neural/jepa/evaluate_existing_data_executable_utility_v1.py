"""Nested executable-return evaluation for EXISTING_DATA_EXECUTABLE_UTILITY_V1.

Development mode is fail-closed to outer months no later than 2023-12.  Frozen
mode requires the exact 24 months 2024-01..2025-12 and a committed runner
manifest.  Thresholds are created from training predictions and selected only
when every one of the three immediately preceding inner months passes all
economic gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from neural.jepa.audit_existing_data_edge_join_inventory_v1 import ROOT, sha256_file
from neural.jepa.existing_data_edge_alternative_v1 import (
    MODEL_FAMILY as HUBER_FAMILY,
    apply_utility_policy,
    fit_robust_utility,
    frozen_spec_sha256 as huber_spec_sha256,
    training_percentile_grid,
)
from neural.jepa.existing_data_edge_hurdle_v1 import (
    MODEL_FAMILY as HURDLE_FAMILY,
    fit_hurdle_utility,
    frozen_spec_sha256 as hurdle_spec_sha256,
)
from neural.jepa.existing_data_edge_scheduler_v1 import (
    EXECUTION_CONTRACT,
    SCHEDULER,
    attach_selected_payoff,
    replay_live_equivalent,
    verify_executable_build_summary,
)


KEY = ["ticker", "trade_date", "minute"]
MASTER = ROOT / "tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet"
VIEW = ROOT / "tmp/existing_data_edge_sprint_v1/modeling_view_features.parquet"
VIEW_MANIFEST = ROOT / "tmp/existing_data_edge_sprint_v1/modeling_view_manifest.json"
BUILD_SUMMARY = ROOT / "tmp/event_option_dataset_execquote_causal1030_202201_202605_v1/SUMMARY.json"
OUTER_MONTHS = tuple(f"{year}{month:02d}" for year in (2024, 2025) for month in range(1, 13))
TICKER_OFFSET = {"SPXW": 100, "QQQ": 200, "SPY": 300}
BASE_SEED = 42
INNER_MONTH_COUNT = 3
INNER_GATES = {
    "profit_factor": 1.30,
    "win_rate": 0.50,
    "trades": 18,
    "pnl": 0.0,
    "minimum_hold": 30.0,
}
MODEL_FAMILIES = (HURDLE_FAMILY, HUBER_FAMILY)


def month_add(month: str, offset: int) -> str:
    year, value = divmod(int(month[:4]) * 12 + int(month[4:]) - 1 + offset, 12)
    return f"{year}{value + 1:02d}"


def month_range(first: str, last: str) -> list[str]:
    months: list[str] = []
    current = first
    while current <= last:
        months.append(current)
        current = month_add(current, 1)
    return months


def _canonical_json_sha(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def runner_protocol() -> dict[str, Any]:
    return {
        "schema": "existing_data_executable_utility_runner_protocol_v1",
        "arms": ["E0", "E1"],
        "model_families": list(MODEL_FAMILIES),
        "model_spec_hashes": {
            HURDLE_FAMILY: hurdle_spec_sha256(),
            HUBER_FAMILY: huber_spec_sha256(),
        },
        "outer_months": list(OUTER_MONTHS),
        "train": "all eligible history strictly before first inner month",
        "inner": "three calendar months immediately before outer month",
        "outer": "one calendar month",
        "threshold_selection": "training prediction percentiles; must pass every inner month",
        "inner_gates": dict(INNER_GATES),
        "passing_grid_rank_desc": [
            "worst_inner_month_pnl", "worst_inner_month_pf", "worst_inner_month_wr",
            "minimum_inner_month_trades", "pooled_inner_pnl", "pooled_inner_pf",
            "utility_percentile", "margin_percentile",
        ],
        "no_passing_grid": "ABSTAIN_OUTER",
        "seed": "42 + integer outer YYYYMM + ticker offset; same seed across E0/E1",
        "scheduler": SCHEDULER,
        "execution": EXECUTION_CONTRACT,
        "candidate_success": "E1 only; all three tickers and all 24 outer months pass every gate",
        "profit_concentration": "top five positive trades/days divided by gross positive profit",
    }


def runner_protocol_sha256() -> str:
    return _canonical_json_sha(runner_protocol())


def _verify_view(view_path: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("status") != "PASS_EXACT_EXISTING_DATA_VIEW"
        or manifest.get("outcomes_in_view") is not False
        or manifest.get("new_data_source") is not False
        or int(manifest.get("master_rows_preserved", -1)) != 97_625
        or manifest.get("view_sha256") != sha256_file(view_path)
        or manifest.get("date_max") != "20251231"
    ):
        raise AssertionError("temporary exact modeling-view contract failed")
    return manifest


def _verify_frozen_manifest(path: Path, view_manifest: dict[str, Any]) -> dict[str, Any]:
    frozen = json.loads(path.read_text(encoding="utf-8"))
    if frozen.get("schema") != "existing_data_executable_utility_v1_frozen_runner" or frozen.get("status") != "PREEXECUTION_FROZEN":
        raise AssertionError("outer evaluation requires PREEXECUTION_FROZEN manifest")
    if frozen.get("runner_protocol_sha256") != runner_protocol_sha256():
        raise AssertionError("active runner protocol differs from frozen manifest")
    if frozen.get("inputs", {}).get("modeling_view", {}).get("sha256") != view_manifest["view_sha256"]:
        raise AssertionError("frozen modeling view differs from active view")
    if frozen.get("feature_arms") != {arm: view_manifest[arm] for arm in ("E0", "E1")}:
        raise AssertionError("frozen E0/E1 feature arms differ from active view")
    active = {
        relative: sha256_file(ROOT / relative)
        for relative in frozen.get("code_hashes", {})
    }
    if active != frozen.get("code_hashes"):
        raise AssertionError("active economic runner code differs from frozen code")
    if frozen.get("holdout_2026_opened") is not False or frozen.get("june_2026_sealed") is not True:
        raise AssertionError("2026 boundary missing from frozen runner")
    return frozen


def _target_columns() -> list[str]:
    return [
        "option_price_mode",
        *[
            f"{right}_d{bucket:02d}_{suffix}"
            for right in ("call", "put")
            for bucket in (25, 35)
            for suffix in ("opt_exit_ret", "opt_exit_minutes")
        ],
    ]


def load_modeling_data(
    view_path: Path,
    view_manifest_path: Path,
    *,
    maximum_date: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    manifest = _verify_view(view_path, view_manifest_path)
    verify_executable_build_summary(BUILD_SUMMARY)
    features = pd.read_parquet(view_path, filters=[("trade_date", "<=", maximum_date)])
    outcomes = pd.read_parquet(
        MASTER,
        columns=[*KEY, *_target_columns()],
        filters=[("trade_date", "<=", maximum_date)],
    )
    features["trade_date"] = features["trade_date"].astype(str).str.replace("-", "", regex=False).str[:8]
    outcomes["trade_date"] = outcomes["trade_date"].astype(str).str.replace("-", "", regex=False).str[:8]
    if features.duplicated(KEY).any() or outcomes.duplicated(KEY).any():
        raise AssertionError("modeling keys must remain unique")
    data = features.merge(outcomes, on=KEY, how="inner", validate="one_to_one")
    if len(data) != len(features):
        raise AssertionError("feature/outcome exact-key parity failed")
    data["month"] = data["trade_date"].str[:6]
    data["call_return"] = np.nan
    data["put_return"] = np.nan
    data["call_exit_minutes"] = np.nan
    data["put_exit_minutes"] = np.nan
    for ticker, config in SCHEDULER.items():
        bucket = int(config["bucket"])
        mask = data["ticker"].astype(str).eq(ticker)
        for side in ("call", "put"):
            data.loc[mask, f"{side}_return"] = pd.to_numeric(
                data.loc[mask, f"{side}_d{bucket:02d}_opt_exit_ret"], errors="coerce"
            )
            data.loc[mask, f"{side}_exit_minutes"] = pd.to_numeric(
                data.loc[mask, f"{side}_d{bucket:02d}_opt_exit_minutes"], errors="coerce"
            )
    if not data["option_price_mode"].astype(str).eq("executable_quote").all():
        raise AssertionError("master contains a non-executable price mode")
    finite_call = np.isfinite(data["call_return"].to_numpy(float))
    finite_put = np.isfinite(data["put_return"].to_numpy(float))
    data["both_executable_outcomes"] = finite_call & finite_put
    missing = data.loc[~data["both_executable_outcomes"], [*KEY, "call_return", "put_return"]]
    expected_missing = {("SPXW", "20220222", 630), ("SPXW", "20220222", 680)}
    observed_missing = set(missing[KEY].itertuples(index=False, name=None))
    if observed_missing != expected_missing:
        raise AssertionError(f"unexpected executable-side missingness: {observed_missing}")
    holds = data.loc[data["both_executable_outcomes"], ["call_exit_minutes", "put_exit_minutes"]].to_numpy(float)
    if not np.isfinite(holds).all():
        raise AssertionError("complete executable outcomes have missing hold times")
    return data, manifest


def economic_metrics(trades: pd.DataFrame) -> dict[str, float | int]:
    if trades.empty:
        return {
            "trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "pnl": 0.0,
            "minimum_hold": math.nan, "maximum_hold": math.nan, "max_drawdown": 0.0,
            "call_rate": 0.0, "put_rate": 0.0,
        }
    ordered = trades.sort_values(["trade_date", "minute", "ticker"], kind="stable")
    returns = pd.to_numeric(ordered["realized_return"], errors="raise").to_numpy(float)
    gross_profit = float(returns[returns > 0.0].sum())
    gross_loss = float(-returns[returns < 0.0].sum())
    pf = gross_profit / gross_loss if gross_loss > 0.0 else (math.inf if gross_profit > 0.0 else 0.0)
    curve = np.cumsum(returns)
    peaks = np.maximum.accumulate(np.r_[0.0, curve])
    drawdown = np.r_[0.0, curve] - peaks
    action = ordered["action"].astype(str).str.upper()
    hold = pd.to_numeric(ordered["exit_minutes"], errors="raise")
    return {
        "trades": int(len(ordered)),
        "win_rate": float(np.mean(returns > 0.0)),
        "profit_factor": float(pf),
        "pnl": float(returns.sum()),
        "minimum_hold": float(hold.min()),
        "maximum_hold": float(hold.max()),
        "max_drawdown": float(-drawdown.min()),
        "call_rate": float(action.eq("CALL").mean()),
        "put_rate": float(action.eq("PUT").mean()),
    }


def _gate_pass(metric: dict[str, float | int]) -> bool:
    minimum_hold = float(metric["minimum_hold"])
    return bool(
        float(metric["profit_factor"]) >= INNER_GATES["profit_factor"]
        and float(metric["win_rate"]) >= INNER_GATES["win_rate"]
        and int(metric["trades"]) >= INNER_GATES["trades"]
        and float(metric["pnl"]) > INNER_GATES["pnl"]
        and np.isfinite(minimum_hold)
        and minimum_hold >= INNER_GATES["minimum_hold"]
    )


def _attach_and_schedule(policy_rows: pd.DataFrame) -> pd.DataFrame:
    if policy_rows.empty:
        empty = policy_rows.copy()
        empty["realized_return"] = pd.Series(dtype=float)
        empty["exit_minutes"] = pd.Series(dtype=float)
        return empty
    return replay_live_equivalent(attach_selected_payoff(policy_rows))


def _select_inner_grid(
    inner_scores: pd.DataFrame,
    grid: list[dict[str, float | int]],
    inner_months: list[str],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    passing: list[tuple[tuple[float, ...], dict[str, Any]]] = []
    for config in grid:
        policy = apply_utility_policy(
            inner_scores,
            utility_threshold=float(config["utility_threshold"]),
            side_margin=float(config["side_margin"]),
        )
        trades = _attach_and_schedule(policy)
        month_metrics: list[dict[str, float | int]] = []
        for month in inner_months:
            metric = economic_metrics(trades.loc[trades["month"].eq(month)])
            month_metrics.append(metric)
        pooled = economic_metrics(trades)
        passed = all(_gate_pass(metric) for metric in month_metrics)
        row: dict[str, Any] = {
            **config,
            "passed": passed,
            "policy_candidates": int(len(policy)),
            "scheduled_trades": int(len(trades)),
            "worst_inner_month_pnl": min(float(value["pnl"]) for value in month_metrics),
            "worst_inner_month_pf": min(float(value["profit_factor"]) for value in month_metrics),
            "worst_inner_month_wr": min(float(value["win_rate"]) for value in month_metrics),
            "minimum_inner_month_trades": min(int(value["trades"]) for value in month_metrics),
            "minimum_inner_hold": min(
                (float(value["minimum_hold"]) for value in month_metrics if np.isfinite(float(value["minimum_hold"]))),
                default=math.nan,
            ),
            "pooled_inner_pnl": float(pooled["pnl"]),
            "pooled_inner_pf": float(pooled["profit_factor"]),
            "inner_month_metrics": json.dumps(
                {month: metric for month, metric in zip(inner_months, month_metrics)},
                sort_keys=True,
                allow_nan=True,
            ),
        }
        rows.append(row)
        if passed:
            rank = (
                float(row["worst_inner_month_pnl"]),
                float(row["worst_inner_month_pf"]),
                float(row["worst_inner_month_wr"]),
                float(row["minimum_inner_month_trades"]),
                float(row["pooled_inner_pnl"]),
                float(row["pooled_inner_pf"]),
                float(config["utility_percentile"]),
                float(config["margin_percentile"]),
            )
            passing.append((rank, row))
    return (max(passing, key=lambda item: item[0])[1] if passing else None), rows


def _fit_model(
    family: str,
    train: pd.DataFrame,
    feature_cols: list[str],
    base_seed: int,
) -> Any:
    kwargs = {
        "call_return_col": "call_return", "put_return_col": "put_return", "base_seed": base_seed,
    }
    if family == HURDLE_FAMILY:
        return fit_hurdle_utility(train, feature_cols, **kwargs)
    if family == HUBER_FAMILY:
        return fit_robust_utility(train, feature_cols, **kwargs)
    raise ValueError(f"unknown frozen model family: {family}")


def _concentration(trades: pd.DataFrame) -> tuple[float, float]:
    if trades.empty:
        return 0.0, 0.0
    positive = trades.loc[trades["realized_return"].gt(0.0), "realized_return"].astype(float)
    gross_profit = float(positive.sum())
    if gross_profit <= 0.0:
        return 0.0, 0.0
    trade_share = float(positive.nlargest(5).sum() / gross_profit)
    daily = trades.groupby("trade_date", observed=True)["realized_return"].sum()
    day_share = float(daily[daily > 0.0].nlargest(5).sum() / gross_profit)
    return trade_share, day_share


def evaluate(
    data: pd.DataFrame,
    view_manifest: dict[str, Any],
    *,
    outer_months: list[str],
    output_dir: Path,
    mode: str,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    selections: list[dict[str, Any]] = []
    grids: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    outer_trades: list[pd.DataFrame] = []
    for outer_month in outer_months:
        inner_months = [month_add(outer_month, offset) for offset in (-3, -2, -1)]
        train_end = month_add(outer_month, -4)
        if not train_end < inner_months[0] or not max(inner_months) < outer_month:
            raise AssertionError("chronological fold ordering failed")
        for ticker in ("SPXW", "QQQ", "SPY"):
            ticker_data = data.loc[data["ticker"].eq(ticker)]
            train = ticker_data.loc[ticker_data["month"].le(train_end)].copy()
            inner = ticker_data.loc[ticker_data["month"].isin(inner_months)].copy()
            outer = ticker_data.loc[ticker_data["month"].eq(outer_month)].copy()
            if train.empty or inner.empty or outer.empty:
                raise AssertionError(f"empty chronological split for {ticker} {outer_month}")
            if not train["month"].max() < inner["month"].min() or not inner["month"].max() < outer_month:
                raise AssertionError("train/inner/outer overlap")
            if not inner["both_executable_outcomes"].all() or not outer["both_executable_outcomes"].all():
                raise AssertionError("inner/outer contains a missing executable side; no causal fill is allowed")
            for arm in ("E0", "E1"):
                feature_cols = list(view_manifest[arm]["features"])
                if arm == "E0" and len(feature_cols) != 30:
                    raise AssertionError("E0 feature count changed")
                if arm == "E1" and len(feature_cols) != 527:
                    raise AssertionError("E1 feature count changed")
                for family in MODEL_FAMILIES:
                    base_seed = BASE_SEED + int(outer_month) + TICKER_OFFSET[ticker]
                    model = _fit_model(family, train, feature_cols, base_seed)
                    training_scores = model.score(train)
                    grid = training_percentile_grid(training_scores)
                    inner_scores = model.score(inner)
                    selected, grid_rows = _select_inner_grid(inner_scores, grid, inner_months)
                    for grid_row in grid_rows:
                        grids.append({
                            "mode": mode, "outer_month": outer_month, "ticker": ticker,
                            "arm": arm, "model_family": family, **grid_row,
                        })
                    outer_scores = model.score(outer)
                    common = {
                        "mode": mode, "outer_month": outer_month, "ticker": ticker,
                        "arm": arm, "model_family": family,
                        "train_date_min": str(train["trade_date"].min()),
                        "train_date_max": str(train["trade_date"].max()),
                        "inner_months": ",".join(inner_months),
                        "outer_rows": int(len(outer)),
                    }
                    if selected is None:
                        selections.append({**common, "status": "ABSTAIN_OUTER", "passing_grid_count": 0})
                        monthly_rows.append({
                            **common, "status": "ABSTAIN_OUTER", **economic_metrics(outer.iloc[0:0]),
                            "policy_candidates": 0, "scheduler_rejections": 0,
                            "abstention_rate": 1.0, "positive_month": False, "gate_pass": False,
                        })
                        continue
                    passing_count = sum(bool(row["passed"]) for row in grid_rows)
                    selections.append({
                        **common, "status": "TRADE_OUTER", "passing_grid_count": passing_count,
                        **{key: selected[key] for key in (
                            "utility_percentile", "margin_percentile", "utility_threshold", "side_margin",
                            "worst_inner_month_pnl", "worst_inner_month_pf", "worst_inner_month_wr",
                            "minimum_inner_month_trades", "pooled_inner_pnl", "pooled_inner_pf",
                        )},
                    })
                    policy = apply_utility_policy(
                        outer_scores,
                        utility_threshold=float(selected["utility_threshold"]),
                        side_margin=float(selected["side_margin"]),
                    )
                    trades = _attach_and_schedule(policy)
                    trades = trades.assign(
                        outer_month=outer_month, arm=arm, model_family=family,
                        utility_percentile=int(selected["utility_percentile"]),
                        margin_percentile=int(selected["margin_percentile"]),
                    )
                    outer_trades.append(trades)
                    metric = economic_metrics(trades)
                    monthly_rows.append({
                        **common, "status": "TRADE_OUTER", **metric,
                        "policy_candidates": int(len(policy)),
                        "scheduler_rejections": int(len(policy) - len(trades)),
                        "abstention_rate": float(1.0 - len(policy) / len(outer)),
                        "positive_month": bool(float(metric["pnl"]) > 0.0),
                        "gate_pass": _gate_pass(metric),
                    })

    selection_frame = pd.DataFrame(selections)
    grid_frame = pd.DataFrame(grids)
    monthly = pd.DataFrame(monthly_rows)
    if outer_trades:
        trades = pd.concat(outer_trades, ignore_index=True)
    else:
        trades = data.iloc[0:0].copy()
        trades["arm"] = pd.Series(dtype=str)
        trades["model_family"] = pd.Series(dtype=str)
        trades["realized_return"] = pd.Series(dtype=float)
        trades["exit_minutes"] = pd.Series(dtype=float)
        trades["action"] = pd.Series(dtype=str)
    summaries: list[dict[str, Any]] = []
    for (arm, family), cells in monthly.groupby(["arm", "model_family"], observed=True, sort=False):
        selected_trades = trades.loc[trades["arm"].eq(arm) & trades["model_family"].eq(family)] if not trades.empty else trades
        pooled = economic_metrics(selected_trades)
        trade_concentration, day_concentration = _concentration(selected_trades)
        all_cells_pass = bool(len(cells) == len(outer_months) * 3 and cells["gate_pass"].all())
        summaries.append({
            "arm": arm, "model_family": family, **pooled,
            "outer_month_cells": int(len(cells)),
            "abstain_outer_cells": int(cells["status"].eq("ABSTAIN_OUTER").sum()),
            "positive_month_rate": float(cells["positive_month"].mean()),
            "minimum_monthly_trades": int(cells["trades"].min()),
            "worst_month_pf": float(cells["profit_factor"].min()),
            "worst_month_pnl": float(cells["pnl"].min()),
            "mean_abstention_rate": float(cells["abstention_rate"].mean()),
            "profit_concentration_top5_trades": trade_concentration,
            "profit_concentration_top5_days": day_concentration,
            "all_ticker_month_gates_pass": all_cells_pass,
            "scientific_candidate": bool(arm == "E1" and all_cells_pass),
        })
    summary_frame = pd.DataFrame(summaries)
    candidate_found = bool(summary_frame["scientific_candidate"].any()) if not summary_frame.empty else False
    result = {
        "schema": "existing_data_executable_utility_v1_results",
        "mode": mode,
        "outer_months": outer_months,
        "runner_protocol_sha256": runner_protocol_sha256(),
        "view_sha256": view_manifest["view_sha256"],
        "E0_sha256": view_manifest["E0"]["ordered_json_sha256"],
        "E1_sha256": view_manifest["E1"]["ordered_json_sha256"],
        "candidate_found": candidate_found,
        "verdict": "ECONOMIC_CANDIDATE_FOUND" if candidate_found else "NO_EDGE_IN_EXISTING_DATA",
        "holdout_2026_opened": False,
        "june_2026_sealed": True,
        "production_modified": False,
    }
    selection_frame.to_csv(output_dir / "fold_selections.csv", index=False)
    grid_frame.to_csv(output_dir / "inner_grid.csv", index=False)
    monthly.to_csv(output_dir / "monthly_metrics.csv", index=False)
    summary_frame.to_csv(output_dir / "portfolio_summary.csv", index=False)
    trades.to_csv(output_dir / "outer_trades.csv", index=False)
    files = ["fold_selections.csv", "inner_grid.csv", "monthly_metrics.csv", "portfolio_summary.csv", "outer_trades.csv"]
    result["files"] = {
        name: {"sha256": sha256_file(output_dir / name), "bytes": (output_dir / name).stat().st_size}
        for name in files
    }
    (output_dir / "SUMMARY.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    result["summary_sha256"] = sha256_file(output_dir / "SUMMARY.json")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("development", "frozen_outer"))
    parser.add_argument("--first-outer")
    parser.add_argument("--last-outer")
    parser.add_argument("--view", default=str(VIEW.relative_to(ROOT)))
    parser.add_argument("--view-manifest", default=str(VIEW_MANIFEST.relative_to(ROOT)))
    parser.add_argument("--frozen-manifest")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    if args.mode == "development":
        if not args.first_outer or not args.last_outer:
            raise SystemExit("development mode requires --first-outer and --last-outer")
        outer_months = month_range(args.first_outer, args.last_outer)
        if max(outer_months) > "202312":
            raise AssertionError("development mode seals 2024 onward")
        maximum_date = f"{args.last_outer}31"
    else:
        if args.first_outer or args.last_outer or not args.frozen_manifest:
            raise SystemExit("frozen_outer uses exact 2024-2025 months and requires --frozen-manifest")
        outer_months = list(OUTER_MONTHS)
        maximum_date = "20251231"
    view_path = ROOT / args.view
    view_manifest_path = ROOT / args.view_manifest
    data, view_manifest = load_modeling_data(view_path, view_manifest_path, maximum_date=maximum_date)
    if args.mode == "frozen_outer":
        _verify_frozen_manifest(ROOT / args.frozen_manifest, view_manifest)
    output_dir = ROOT / args.output_dir
    if args.mode == "development":
        authorized = (ROOT / "tmp/existing_data_edge_sprint_v1").resolve()
        if authorized not in output_dir.resolve().parents:
            raise AssertionError("development output must remain under the authorized temp root")
    result = evaluate(
        data, view_manifest, outer_months=outer_months, output_dir=output_dir, mode=args.mode,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
