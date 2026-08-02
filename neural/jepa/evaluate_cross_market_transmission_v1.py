"""Nested executable evaluation for CROSS_MARKET_TRANSMISSION_V1.

Development fails closed at 2023-12. Frozen mode requires an immutable runner
manifest and evaluates exactly 2024-01..2025-12 once. Threshold values come
only from training predictions; one pair must pass every one of the three inner
months or the corresponding outer month abstains completely.
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
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from neural.jepa.audit_existing_data_edge_join_inventory_v1 import ROOT, sha256_file
from neural.jepa.build_cross_market_transmission_view_v1 import (
    CROSS_FEATURES,
    EARLY_CLOSE_DATES,
    ELIGIBLE_ROWS_V1R1,
    MASTER_SHA256,
    PAIRWISE_E0_FEATURES,
)
from neural.jepa.existing_data_edge_scheduler_v1 import (
    EXECUTION_CONTRACT,
    SCHEDULER,
    attach_selected_payoff,
    replay_live_equivalent,
    verify_executable_build_summary,
)
from neural.jepa.existing_data_quantile_distribution_v1 import (
    MODEL_FAMILY,
    apply_quantile_policy,
    assert_development_only,
    fit_quantile_distribution,
    frozen_spec_sha256,
    training_percentile_grid,
)


KEY = ["ticker", "trade_date", "minute"]
VIEW_KEY = ["ticker", "trade_date", "timestamp", "minute"]
MASTER = ROOT / "tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet"
VIEW = ROOT / "tmp/existing_data_edge_sprint_v1/cross_market_transmission_v1/modeling_view.parquet"
VIEW_MANIFEST = ROOT / "tmp/existing_data_edge_sprint_v1/cross_market_transmission_v1/manifest.json"
BUILD_SUMMARY = ROOT / "tmp/event_option_dataset_execquote_causal1030_202201_202605_v1/SUMMARY.json"
OUTER_MONTHS = tuple(f"{year}{month:02d}" for year in (2024, 2025) for month in range(1, 13))
TICKER_OFFSET = {"SPXW": 100, "QQQ": 200, "SPY": 300}
BASE_SEED = 42
INNER_GATES = {
    "profit_factor": 1.30,
    "win_rate": 0.50,
    "trades": 18,
    "pnl": 0.0,
    "minimum_hold": 30.0,
}
EXPECTED_X0_SHA256 = "b68b6c2e17b333597281a7d7fa27237b1f1e2640deb8952867d25eced26cbe38"
EXPECTED_CROSS_SHA256 = "5df3d817d12c5d938427eabeca145f1d4e59420e1283fa3cf3bdaeef6b112058"
EXPECTED_X1_SHA256 = "3ef89d8da590dd548dd4c14a4cd8931becfa27d3d10c5fd71440146f402252d1"
FROZEN_CODE_CLOSURE = (
    "neural/jepa/build_cross_market_transmission_view_v1.py",
    "neural/jepa/evaluate_cross_market_transmission_v1.py",
    "neural/jepa/existing_data_quantile_distribution_v1.py",
    "neural/jepa/existing_data_edge_scheduler_v1.py",
    "neural/jepa/walkforward_pairwise_opportunity_side.py",
    "neural/jepa/freeze_cross_market_transmission_v1.py",
)
FROZEN_PROTOCOL_CLOSURE = (
    "research_papers/JEPA/CROSS_MARKET_TRANSMISSION_V1_PREDECLARATION.md",
    "research_papers/JEPA/CROSS_MARKET_TRANSMISSION_V1R1_HALF_DAY_REPAIR.md",
)
FROZEN_OUTER_OUTPUT = "research_papers/JEPA/results/_diagnostics/cross_market_transmission_v1r1_202401_202512"
MAX_TOP5_TRADE_GROSS_PROFIT_SHARE = 0.20
MAX_TOP5_DAY_GROSS_PROFIT_SHARE = 0.30


def month_add(month: str, offset: int) -> str:
    year, value = divmod(int(month[:4]) * 12 + int(month[4:]) - 1 + offset, 12)
    return f"{year}{value + 1:02d}"


def month_range(first: str, last: str) -> list[str]:
    values: list[str] = []
    current = first
    while current <= last:
        values.append(current)
        current = month_add(current, 1)
    return values


def development_outer_months(first: str | None, last: str | None) -> list[str]:
    if first != "202304" or last != "202312":
        raise AssertionError("development range is frozen to 202304..202312")
    values = month_range(first, last)
    if values != month_range("202304", "202312"):
        raise AssertionError("development month grid changed")
    return values


def _canonical_sha(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def runner_protocol() -> dict[str, Any]:
    return {
        "schema": "cross_market_transmission_runner_protocol_v1r1",
        "experiment": "CROSS_MARKET_TRANSMISSION_V1R1",
        "arms": ["X0", "X1"],
        "model_family": MODEL_FAMILY,
        "model_spec_sha256": frozen_spec_sha256(),
        "outer_months": list(OUTER_MONTHS),
        "train": "all eligible history before first inner month",
        "inner": "three calendar months immediately before outer",
        "outer": "one calendar month",
        "threshold_source": "training predictions only",
        "inner_gates": dict(INNER_GATES),
        "passing_rank_desc": [
            "worst_inner_month_pnl",
            "worst_inner_month_pf",
            "worst_inner_month_wr",
            "minimum_inner_month_trades",
            "pooled_inner_pnl",
            "pooled_inner_pf",
            "utility_percentile",
            "margin_percentile",
        ],
        "no_passing_grid": "ABSTAIN_OUTER",
        "scheduler": SCHEDULER,
        "execution": EXECUTION_CONTRACT,
        "candidate": "X1 only; all three tickers and every outer month pass",
        "concentration_gates": {
            "pooled_and_each_ticker_top5_trade_gross_profit_share_max": MAX_TOP5_TRADE_GROSS_PROFIT_SHARE,
            "pooled_and_each_ticker_top5_day_gross_profit_share_max": MAX_TOP5_DAY_GROSS_PROFIT_SHARE,
        },
        "live_parity": "BLOCKED_IMPLEMENTATION until a base economic pass",
        "holdout_2026_opened": False,
        "june_2026_sealed": True,
    }


def runner_protocol_sha256() -> str:
    return _canonical_sha(runner_protocol())


def _verify_view(view_path: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {
        "schema": "cross_market_transmission_view_v1r1",
        "experiment": "CROSS_MARKET_TRANSMISSION_V1R1",
        "status": "PASS_EXACT_CROSS_MARKET_VIEW",
        "outcomes_in_view": False,
        "new_data_source": False,
        "master_rows_preserved": ELIGIBLE_ROWS_V1R1,
        "master_physical_rows": 97_625,
        "master_sha256": MASTER_SHA256,
        "source_sessions": 3_848,
        "excluded_early_close_rows": 1_072,
        "live_parity": "BLOCKED_IMPLEMENTATION",
    }
    mismatches = {key: (value, manifest.get(key)) for key, value in expected.items() if manifest.get(key) != value}
    if mismatches:
        raise AssertionError(f"cross-market view contract failed: {mismatches}")
    if manifest.get("view_sha256") != sha256_file(view_path):
        raise AssertionError("cross-market view hash mismatch")
    if manifest.get("date_max") != "20251231":
        raise AssertionError("cross-market view date boundary changed")
    if manifest.get("excluded_early_close_dates") != list(EARLY_CLOSE_DATES):
        raise AssertionError("V1R1 early-close exclusion changed")
    parquet = pq.ParquetFile(view_path)
    if parquet.metadata.num_rows != ELIGIBLE_ROWS_V1R1:
        raise AssertionError("view physical row count differs from the V1R1 census")
    expected_x0 = list(PAIRWISE_E0_FEATURES)
    expected_x1 = [*expected_x0, *CROSS_FEATURES]
    expected_columns = list(dict.fromkeys([*VIEW_KEY, *expected_x1]))
    if parquet.schema_arrow.names != expected_columns:
        raise AssertionError("view physical schema differs from exact keys plus X1")
    exact_arms = {
        "X0": (expected_x0, EXPECTED_X0_SHA256),
        "X1": (expected_x1, EXPECTED_X1_SHA256),
    }
    if _canonical_sha(list(CROSS_FEATURES)) != EXPECTED_CROSS_SHA256:
        raise AssertionError("active cross-market block hash changed")
    for arm, count in (("X0", 30), ("X1", 58)):
        arm_payload = manifest.get(arm, {})
        if int(arm_payload.get("feature_count", -1)) != count:
            raise AssertionError(f"{arm} feature count changed")
        features = arm_payload.get("features")
        if not isinstance(features, list) or len(features) != count or len(features) != len(set(features)):
            raise AssertionError(f"{arm} ordered allowlist invalid")
        expected_features, expected_sha = exact_arms[arm]
        if features != expected_features or arm_payload.get("ordered_json_sha256") != expected_sha:
            raise AssertionError(f"{arm} differs from the predeclared allowlist")
        if _canonical_sha(features) != expected_sha:
            raise AssertionError(f"{arm} allowlist hash mismatch")
    if manifest["X1"]["features"][:30] != manifest["X0"]["features"]:
        raise AssertionError("X1 must begin with exact X0")
    return manifest


def _verify_frozen_manifest(path: Path, view_manifest: dict[str, Any]) -> dict[str, Any]:
    frozen = json.loads(path.read_text(encoding="utf-8"))
    if frozen.get("schema") != "cross_market_transmission_v1r1_frozen_runner" or frozen.get("status") != "PREEXECUTION_FROZEN":
        raise AssertionError("frozen runner manifest invalid")
    if frozen.get("runner_protocol_sha256") != runner_protocol_sha256():
        raise AssertionError("active runner protocol differs from freeze")
    if frozen.get("view_sha256") != view_manifest["view_sha256"]:
        raise AssertionError("active outcome-free view differs from freeze")
    if frozen.get("feature_arms") != {arm: view_manifest[arm] for arm in ("X0", "X1")}:
        raise AssertionError("active feature arms differ from freeze")
    if set(frozen.get("code_hashes", {})) != set(FROZEN_CODE_CLOSURE):
        raise AssertionError("frozen code closure is incomplete or self-selected")
    if set(frozen.get("protocol_hashes", {})) != set(FROZEN_PROTOCOL_CLOSURE):
        raise AssertionError("frozen protocol closure is incomplete")
    active_hashes = {relative: sha256_file(ROOT / relative) for relative in FROZEN_CODE_CLOSURE}
    if active_hashes != frozen.get("code_hashes"):
        raise AssertionError("active runner code differs from freeze")
    if frozen.get("holdout_2026_opened") is not False or frozen.get("june_2026_sealed") is not True:
        raise AssertionError("2026 boundary missing from freeze")
    if frozen.get("outer_output_dir") != FROZEN_OUTER_OUTPUT:
        raise AssertionError("frozen one-shot output target changed")
    return frozen


def _target_columns() -> list[str]:
    return [
        "option_price_mode",
        *[
            f"{side}_d{bucket:02d}_{suffix}"
            for side in ("call", "put")
            for bucket in (25, 35)
            for suffix in ("opt_exit_ret", "opt_exit_minutes")
        ],
    ]


def load_modeling_data(view_path: Path, manifest_path: Path, *, maximum_date: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    manifest = _verify_view(view_path, manifest_path)
    verify_executable_build_summary(BUILD_SUMMARY)
    if sha256_file(MASTER) != MASTER_SHA256:
        raise AssertionError("authoritative executable master hash changed")
    features = pd.read_parquet(view_path, filters=[("trade_date", "<=", maximum_date)])
    outcomes = pd.read_parquet(MASTER, columns=[*KEY, *_target_columns()], filters=[("trade_date", "<=", maximum_date)])
    for frame in (features, outcomes):
        frame["trade_date"] = frame["trade_date"].astype(str).str.replace("-", "", regex=False).str[:8]
        if frame.duplicated(KEY).any():
            raise AssertionError("modeling keys must be unique")
    outcomes = outcomes.loc[~outcomes["trade_date"].isin(EARLY_CLOSE_DATES)].reset_index(drop=True)
    feature_keys = pd.MultiIndex.from_frame(features[KEY])
    outcome_keys = pd.MultiIndex.from_frame(outcomes[KEY])
    missing_view = outcome_keys.difference(feature_keys)
    missing_master = feature_keys.difference(outcome_keys)
    if len(features) != len(outcomes) or len(missing_view) or len(missing_master):
        raise AssertionError(
            f"feature/outcome bidirectional key parity failed: "
            f"missing_view={len(missing_view)} missing_master={len(missing_master)}"
        )
    data = features.merge(outcomes, on=KEY, how="inner", validate="one_to_one")
    data["month"] = data["trade_date"].str[:6]
    for output in ("call_return", "put_return", "call_exit_minutes", "put_exit_minutes"):
        data[output] = np.nan
    for ticker, config in SCHEDULER.items():
        bucket = int(config["bucket"])
        mask = data["ticker"].astype(str).eq(ticker)
        for side in ("call", "put"):
            data.loc[mask, f"{side}_return"] = pd.to_numeric(data.loc[mask, f"{side}_d{bucket:02d}_opt_exit_ret"], errors="coerce")
            data.loc[mask, f"{side}_exit_minutes"] = pd.to_numeric(data.loc[mask, f"{side}_d{bucket:02d}_opt_exit_minutes"], errors="coerce")
    if not data["option_price_mode"].astype(str).eq("executable_quote").all():
        raise AssertionError("non-executable label source")
    data["both_executable_outcomes"] = np.isfinite(data["call_return"]) & np.isfinite(data["put_return"])
    missing = set(data.loc[~data["both_executable_outcomes"], KEY].itertuples(index=False, name=None))
    expected_missing = {("SPXW", "20220222", 630), ("SPXW", "20220222", 680)}
    if missing != expected_missing:
        raise AssertionError(f"unexpected target missingness: {missing}")
    return data, manifest


def economic_metrics(trades: pd.DataFrame) -> dict[str, float | int]:
    if trades.empty:
        return {"trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "pnl": 0.0, "minimum_hold": math.nan, "maximum_hold": math.nan, "max_drawdown": 0.0, "call_rate": 0.0, "put_rate": 0.0}
    ordered = trades.copy()
    ordered["exit_sort_minute"] = pd.to_numeric(ordered["minute"], errors="raise") + pd.to_numeric(ordered["exit_minutes"], errors="raise")
    ordered = ordered.sort_values(["trade_date", "exit_sort_minute", "ticker"], kind="stable")
    returns = pd.to_numeric(ordered["realized_return"], errors="raise").to_numpy(float)
    gross_profit = float(returns[returns > 0.0].sum())
    gross_loss = float(-returns[returns < 0.0].sum())
    pf = gross_profit / gross_loss if gross_loss > 0.0 else (math.inf if gross_profit > 0.0 else 0.0)
    realized_by_exit = ordered.groupby(["trade_date", "exit_sort_minute"], sort=True, observed=True)["realized_return"].sum()
    curve = np.cumsum(realized_by_exit.to_numpy(dtype=float))
    drawdown = np.r_[0.0, curve] - np.maximum.accumulate(np.r_[0.0, curve])
    action = ordered["action"].astype(str).str.upper()
    hold = pd.to_numeric(ordered["exit_minutes"], errors="raise")
    return {"trades": int(len(ordered)), "win_rate": float(np.mean(returns > 0.0)), "profit_factor": float(pf), "pnl": float(returns.sum()), "minimum_hold": float(hold.min()), "maximum_hold": float(hold.max()), "max_drawdown": float(-drawdown.min()), "call_rate": float(action.eq("CALL").mean()), "put_rate": float(action.eq("PUT").mean())}


def _gate_pass(metric: dict[str, float | int]) -> bool:
    hold = float(metric["minimum_hold"])
    return bool(float(metric["profit_factor"]) >= 1.30 and float(metric["win_rate"]) >= 0.50 and int(metric["trades"]) >= 18 and float(metric["pnl"]) > 0.0 and np.isfinite(hold) and hold >= 30.0)


def _schedule(scores: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, int]:
    policy = apply_quantile_policy(scores, utility_threshold=float(config["utility_threshold"]), side_margin=float(config["side_margin"]))
    if policy.empty:
        empty = policy.copy()
        empty["realized_return"] = pd.Series(dtype=float)
        empty["exit_minutes"] = pd.Series(dtype=float)
        return empty, 0
    trades = replay_live_equivalent(attach_selected_payoff(policy))
    return trades, int(len(policy))


def _select_inner(inner_scores: pd.DataFrame, grid: list[dict[str, float | int]], inner_months: list[str]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    passing: list[tuple[tuple[float, ...], dict[str, Any]]] = []
    for config in grid:
        trades, candidates = _schedule(inner_scores, config)
        metrics = [economic_metrics(trades.loc[trades["month"].eq(month)]) for month in inner_months]
        pooled = economic_metrics(trades)
        row = {
            **config,
            "passed": all(_gate_pass(metric) for metric in metrics),
            "policy_candidates": candidates,
            "scheduled_trades": int(len(trades)),
            "worst_inner_month_pnl": min(float(metric["pnl"]) for metric in metrics),
            "worst_inner_month_pf": min(float(metric["profit_factor"]) for metric in metrics),
            "worst_inner_month_wr": min(float(metric["win_rate"]) for metric in metrics),
            "minimum_inner_month_trades": min(int(metric["trades"]) for metric in metrics),
            "pooled_inner_pnl": float(pooled["pnl"]),
            "pooled_inner_pf": float(pooled["profit_factor"]),
            "inner_month_metrics": json.dumps(dict(zip(inner_months, metrics)), sort_keys=True, allow_nan=True),
        }
        rows.append(row)
        if row["passed"]:
            rank = tuple(float(row[key]) for key in ("worst_inner_month_pnl", "worst_inner_month_pf", "worst_inner_month_wr", "minimum_inner_month_trades", "pooled_inner_pnl", "pooled_inner_pf")) + (float(config["utility_percentile"]), float(config["margin_percentile"]))
            passing.append((rank, row))
    return (max(passing, key=lambda item: item[0])[1] if passing else None), rows


def _concentration(trades: pd.DataFrame) -> tuple[float, float]:
    if trades.empty:
        return 0.0, 0.0
    positive = trades.loc[trades["realized_return"].gt(0.0), "realized_return"].astype(float)
    gross = float(positive.sum())
    if gross <= 0.0:
        return 0.0, 0.0
    daily = trades.groupby("trade_date", observed=True)["realized_return"].sum()
    return float(positive.nlargest(5).sum() / gross), float(daily[daily > 0.0].nlargest(5).sum() / gross)


def _concentration_audit(trades: pd.DataFrame, arm: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scopes = [("POOLED", trades)]
    scopes.extend((ticker, trades.loc[trades["ticker"].eq(ticker)]) for ticker in ("SPXW", "QQQ", "SPY"))
    for scope, scoped in scopes:
        trade_share, day_share = _concentration(scoped)
        rows.append(
            {
                "arm": arm,
                "scope": scope,
                "trades": int(len(scoped)),
                "top5_trade_gross_profit_share": trade_share,
                "top5_day_gross_profit_share": day_share,
                "trade_concentration_pass": trade_share <= MAX_TOP5_TRADE_GROSS_PROFIT_SHARE,
                "day_concentration_pass": day_share <= MAX_TOP5_DAY_GROSS_PROFIT_SHARE,
                "concentration_pass": (
                    trade_share <= MAX_TOP5_TRADE_GROSS_PROFIT_SHARE
                    and day_share <= MAX_TOP5_DAY_GROSS_PROFIT_SHARE
                ),
            }
        )
    return rows


def evaluate(data: pd.DataFrame, view_manifest: dict[str, Any], *, outer_months: list[str], output_dir: Path, mode: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    selection_rows: list[dict[str, Any]] = []
    grid_rows_all: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    trade_frames: list[pd.DataFrame] = []
    for outer_month in outer_months:
        inner_months = [month_add(outer_month, offset) for offset in (-3, -2, -1)]
        train_end = month_add(outer_month, -4)
        for ticker in ("SPXW", "QQQ", "SPY"):
            ticker_data = data.loc[data["ticker"].eq(ticker)]
            train = ticker_data.loc[ticker_data["month"].le(train_end)].copy()
            inner = ticker_data.loc[ticker_data["month"].isin(inner_months)].copy()
            outer = ticker_data.loc[ticker_data["month"].eq(outer_month)].copy()
            if train.empty or inner.empty or outer.empty or not train["month"].max() < inner["month"].min() or not inner["month"].max() < outer_month:
                raise AssertionError(f"invalid chronological fold {ticker} {outer_month}")
            if not inner["both_executable_outcomes"].all() or not outer["both_executable_outcomes"].all():
                raise AssertionError("inner/outer contains missing side")
            for arm in ("X0", "X1"):
                features = list(view_manifest[arm]["features"])
                base_seed = BASE_SEED + int(outer_month) + TICKER_OFFSET[ticker]
                model = fit_quantile_distribution(train, features, call_return_col="call_return", put_return_col="put_return", base_seed=base_seed)
                training_scores = model.score(train)
                grid = training_percentile_grid(training_scores)
                inner_scores = model.score(inner)
                selected, grid_rows = _select_inner(inner_scores, grid, inner_months)
                for row in grid_rows:
                    grid_rows_all.append({"mode": mode, "outer_month": outer_month, "ticker": ticker, "arm": arm, "model_family": MODEL_FAMILY, **row})
                common = {
                    "mode": mode,
                    "outer_month": outer_month,
                    "ticker": ticker,
                    "arm": arm,
                    "model_family": MODEL_FAMILY,
                    "train_date_min": str(train["trade_date"].min()),
                    "train_date_max": str(train["trade_date"].max()),
                    "inner_months": ",".join(inner_months),
                    "outer_rows": int(len(outer)),
                }
                if selected is None:
                    selection_rows.append({**common, "status": "ABSTAIN_OUTER", "passing_grid_count": 0})
                    monthly_rows.append({**common, "status": "ABSTAIN_OUTER", **economic_metrics(outer.iloc[0:0]), "policy_candidates": 0, "scheduler_rejections": 0, "abstention_rate": 1.0, "positive_month": False, "gate_pass": False})
                    continue
                selection_rows.append({**common, "status": "TRADE_OUTER", "passing_grid_count": sum(bool(row["passed"]) for row in grid_rows), **{key: selected[key] for key in ("utility_percentile", "margin_percentile", "utility_threshold", "side_margin", "worst_inner_month_pnl", "worst_inner_month_pf", "worst_inner_month_wr", "minimum_inner_month_trades", "pooled_inner_pnl", "pooled_inner_pf")}})
                outer_scores = model.score(outer)
                trades, candidates = _schedule(outer_scores, selected)
                trades = trades.assign(outer_month=outer_month, arm=arm, model_family=MODEL_FAMILY, utility_percentile=int(selected["utility_percentile"]), margin_percentile=int(selected["margin_percentile"]))
                trade_frames.append(trades)
                metric = economic_metrics(trades)
                monthly_rows.append({**common, "status": "TRADE_OUTER", **metric, "policy_candidates": candidates, "scheduler_rejections": candidates - len(trades), "abstention_rate": float(1.0 - candidates / len(outer)), "positive_month": bool(float(metric["pnl"]) > 0.0), "gate_pass": _gate_pass(metric)})

    selections = pd.DataFrame(selection_rows)
    grids = pd.DataFrame(grid_rows_all)
    monthly = pd.DataFrame(monthly_rows)
    if trade_frames:
        trades = pd.concat(trade_frames, ignore_index=True)
    else:
        trades = pd.DataFrame(columns=[*KEY, "outer_month", "arm", "model_family", "action", "score", "selected_pwin", "realized_return", "exit_minutes"])
    summaries: list[dict[str, Any]] = []
    concentration_rows: list[dict[str, Any]] = []
    for arm, cells in monthly.groupby("arm", observed=True, sort=False):
        arm_trades = trades.loc[trades["arm"].eq(arm)] if not trades.empty else trades
        pooled = economic_metrics(arm_trades)
        top_trades, top_days = _concentration(arm_trades)
        all_pass = bool(len(cells) == len(outer_months) * 3 and cells["gate_pass"].all())
        arm_concentration = _concentration_audit(arm_trades, arm)
        concentration_rows.extend(arm_concentration)
        concentration_pass = all(bool(row["concentration_pass"]) for row in arm_concentration)
        base_pass = bool(arm == "X1" and all_pass and concentration_pass)
        summaries.append({"arm": arm, "model_family": MODEL_FAMILY, **pooled, "outer_month_cells": int(len(cells)), "abstain_outer_cells": int(cells["status"].eq("ABSTAIN_OUTER").sum()), "positive_month_rate": float(cells["positive_month"].mean()), "minimum_monthly_trades": int(cells["trades"].min()), "worst_month_pf": float(cells["profit_factor"].min()), "worst_month_pnl": float(cells["pnl"].min()), "mean_abstention_rate": float(cells["abstention_rate"].mean()), "profit_concentration_top5_trades": top_trades, "profit_concentration_top5_days": top_days, "all_ticker_month_gates_pass": all_pass, "concentration_pass": concentration_pass, "base_economic_pass": base_pass, "scientific_candidate": False})
    summary_frame = pd.DataFrame(summaries)
    concentration_frame = pd.DataFrame(concentration_rows)
    base_economic_pass = bool(summary_frame["base_economic_pass"].any())
    candidate = False
    result = {
        "schema": "cross_market_transmission_v1_results",
        "mode": mode,
        "outer_months": outer_months,
        "runner_protocol_sha256": runner_protocol_sha256(),
        "view_sha256": view_manifest["view_sha256"],
        "X0_sha256": view_manifest["X0"]["ordered_json_sha256"],
        "X1_sha256": view_manifest["X1"]["ordered_json_sha256"],
        "candidate_found": candidate,
        "base_economic_pass": base_economic_pass,
        "development_promising": bool(mode == "development" and base_economic_pass),
        "verdict": (
            "DEVELOPMENT_ONLY"
            if mode == "development"
            else ("BASE_ECONOMIC_PASS_PENDING_LIVE_PARITY_STRESS" if base_economic_pass else "FAILED_ECONOMIC")
        ),
        "live_parity": "BLOCKED_IMPLEMENTATION",
        "holdout_2026_opened": False,
        "june_2026_sealed": True,
        "production_modified": False,
    }
    outputs = {"fold_selections.csv": selections, "inner_grid.csv": grids, "monthly_metrics.csv": monthly, "portfolio_summary.csv": summary_frame, "concentration_by_ticker.csv": concentration_frame, "outer_trades.csv": trades}
    for name, frame in outputs.items():
        frame.to_csv(output_dir / name, index=False)
    result["files"] = {name: {"sha256": sha256_file(output_dir / name), "bytes": (output_dir / name).stat().st_size} for name in outputs}
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
            raise SystemExit("development requires first/last outer")
        outer_months = development_outer_months(args.first_outer, args.last_outer)
        maximum_date = f"{args.last_outer}31"
    else:
        if args.first_outer or args.last_outer or not args.frozen_manifest:
            raise SystemExit("frozen_outer requires only --frozen-manifest")
        outer_months = list(OUTER_MONTHS)
        maximum_date = "20251231"
    data, manifest = load_modeling_data(ROOT / args.view, ROOT / args.view_manifest, maximum_date=maximum_date)
    if args.mode == "development":
        assert_development_only(data)
        authorized = (ROOT / "tmp/existing_data_edge_sprint_v1").resolve()
        output = (ROOT / args.output_dir).resolve()
        if authorized not in output.parents:
            raise AssertionError("development output must remain under authorized tmp")
    else:
        frozen = _verify_frozen_manifest(ROOT / args.frozen_manifest, manifest)
        output = ROOT / args.output_dir
        expected_output = ROOT / str(frozen["outer_output_dir"])
        if output.resolve() != expected_output.resolve():
            raise AssertionError("frozen outer output must equal the one-shot target")
    result = evaluate(data, manifest, outer_months=outer_months, output_dir=output, mode=args.mode)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
