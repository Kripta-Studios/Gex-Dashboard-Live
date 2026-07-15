"""Fixed-rule executable development replay for KING-GEX-SLOPE1."""

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
from neural.jepa.build_tpo_value_migration_view_v1 import EARLY_CLOSE_DATES, MASTER_SHA256
from neural.jepa.existing_data_edge_scheduler_v1 import (
    EXECUTION_CONTRACT,
    SCHEDULER,
    attach_selected_payoff,
    replay_live_equivalent,
    verify_executable_build_summary,
)


EXPERIMENT = "KING_GEX_SLOPE1_EXECUTABLE_V1"
KEY = ["ticker", "trade_date", "minute"]
ARMS = ("K0_LEVEL", "K1_ALIGNED")
CANDIDATE_ARM = "K1_ALIGNED"
DEVELOPMENT_MONTHS = tuple(f"2023{month:02d}" for month in range(1, 13))
MASTER = ROOT / "tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet"
WALL_STATE = ROOT / "tmp/wall_state_gex_dex_202201_202512_v1/wall_state.parquet"
BUILD_SUMMARY = ROOT / "tmp/event_option_dataset_execquote_causal1030_202201_202605_v1/SUMMARY.json"
PROTOCOL_DOCUMENT = ROOT / "research_papers/JEPA/KING_GEX_SLOPE1_EXECUTABLE_PREDECLARATION.md"
CLARIFICATION_DOCUMENT = ROOT / "research_papers/JEPA/KING_GEX_SLOPE1_DATA_GATE_CLARIFICATION.md"
WALL_STATE_SHA256 = "94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef"
PROTOCOL_DOCUMENT_SHA256 = "f9e19f83f13e3eae44a4c4cd6b9c92801564dede507e5ed29184575f9b4c5dd6"
CLARIFICATION_DOCUMENT_SHA256 = "17d00155c315f007f25d87b22220c161a8360f9ea54128df665224ae5422c504"
EXPECTED_DEVELOPMENT_ROWS = 20_309
EXPECTED_ALIGNED_SIGNALS = 13_286
SLOPE_LAG_MINUTES = 45
SLOPE_NORMALIZATION_MINUTES = 15
FIRST_DECISION_MINUTE = 680
LAST_DECISION_MINUTE = 870
INNER_GATES = {
    "profit_factor": 1.30,
    "win_rate": 0.50,
    "trades": 18,
    "pnl": 0.0,
    "minimum_hold": 30.0,
}
MAX_TOP5_TRADE_GROSS_PROFIT_SHARE = 0.20
MAX_TOP5_DAY_GROSS_PROFIT_SHARE = 0.30
RUN_CHECKPOINT_SCHEMA = "king_gex_slope1_run_checkpoint_v1"
CELL_CHECKPOINT_SCHEMA = "king_gex_slope1_cell_checkpoint_v1"
CHECKPOINT_CODE_CLOSURE = (
    "neural/jepa/evaluate_king_gex_slope_v1.py",
    "neural/jepa/existing_data_edge_scheduler_v1.py",
)


def _canonical_sha(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def runner_protocol() -> dict[str, Any]:
    return {
        "schema": "king_gex_slope1_runner_protocol_v1",
        "experiment": EXPERIMENT,
        "mode": "development_fixed_rule",
        "months": list(DEVELOPMENT_MONTHS),
        "arms": list(ARMS),
        "candidate_arm": CANDIDATE_ARM,
        "source_hashes": {
            "master": MASTER_SHA256,
            "wall_state": WALL_STATE_SHA256,
            "predeclaration": PROTOCOL_DOCUMENT_SHA256,
            "data_gate_clarification": CLARIFICATION_DOCUMENT_SHA256,
        },
        "grid": {
            "first_minute": FIRST_DECISION_MINUTE,
            "last_minute": LAST_DECISION_MINUTE,
            "cadence_minutes": 5,
            "lag_minutes": SLOPE_LAG_MINUTES,
        },
        "gex_inverse": "sign(L)*expm1(abs(L))",
        "slope": "(G_t-G_t_minus_45m)/3",
        "momentum": "sign(ret_15m_bps)",
        "K0_LEVEL": "negative gamma follows momentum; positive gamma fades momentum",
        "K1_ALIGNED": "K0 direction only when sign(slope)==sign(G_t)",
        "zero_or_nonfinite": "ABSTAIN",
        "fit": None,
        "threshold": None,
        "score": 1.0,
        "execution": EXECUTION_CONTRACT,
        "scheduler": SCHEDULER,
        "gates": dict(INNER_GATES),
        "concentration": {
            "top5_trade_max": MAX_TOP5_TRADE_GROSS_PROFIT_SHARE,
            "top5_day_max": MAX_TOP5_DAY_GROSS_PROFIT_SHARE,
        },
        "checkpoint": {
            "schema": CELL_CHECKPOINT_SCHEMA,
            "granularity": "month_ticker_arm",
            "atomic_manifest_last": True,
        },
        "outer_2024_2025_opened": False,
        "holdout_2026_opened": False,
        "june_2026_sealed": True,
    }


def runner_protocol_sha256() -> str:
    return _canonical_sha(runner_protocol())


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


def _day(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace("-", "", regex=False).str[:8]


def load_development_data() -> pd.DataFrame:
    if sha256_file(MASTER) != MASTER_SHA256:
        raise AssertionError("authoritative executable master hash changed")
    if sha256_file(WALL_STATE) != WALL_STATE_SHA256:
        raise AssertionError("wall-state source hash changed")
    if sha256_file(PROTOCOL_DOCUMENT) != PROTOCOL_DOCUMENT_SHA256:
        raise AssertionError("active predeclaration differs from committed protocol")
    if sha256_file(CLARIFICATION_DOCUMENT) != CLARIFICATION_DOCUMENT_SHA256:
        raise AssertionError("active data-gate clarification differs from committed protocol")
    verify_executable_build_summary(BUILD_SUMMARY)
    master = pd.read_parquet(
        MASTER,
        columns=[*KEY, "ret_15m_bps", *_target_columns()],
        filters=[("trade_date", ">=", "20230101"), ("trade_date", "<=", "20231231")],
    )
    wall = pd.read_parquet(
        WALL_STATE,
        columns=[*KEY, "wall_net_gamma_total_log"],
        filters=[("trade_date", ">=", "20230101"), ("trade_date", "<=", "20231231")],
    )
    for frame in (master, wall):
        frame["ticker"] = frame["ticker"].astype(str).str.upper()
        frame["trade_date"] = _day(frame["trade_date"])
        frame["minute"] = pd.to_numeric(frame["minute"], errors="raise").astype(int)
        frame.drop(frame.index[frame["trade_date"].isin(EARLY_CLOSE_DATES)], inplace=True)
        if frame.duplicated(KEY).any():
            raise AssertionError("source keys must be unique")
    master = master.loc[
        master["minute"].between(FIRST_DECISION_MINUTE, LAST_DECISION_MINUTE)
    ].copy()
    wall = wall.sort_values(KEY, kind="stable").reset_index(drop=True)
    grouped = wall.groupby(["ticker", "trade_date"], observed=True, sort=False)
    wall["lag_minute"] = grouped["minute"].shift(SLOPE_LAG_MINUTES // 5)
    wall["gex_log_lag45"] = grouped["wall_net_gamma_total_log"].shift(
        SLOPE_LAG_MINUTES // 5
    )
    current_log = pd.to_numeric(wall["wall_net_gamma_total_log"], errors="coerce")
    lag_log = pd.to_numeric(wall["gex_log_lag45"], errors="coerce")
    wall["net_gex_proxy"] = np.sign(current_log) * np.expm1(np.abs(current_log))
    wall["net_gex_proxy_lag45"] = np.sign(lag_log) * np.expm1(np.abs(lag_log))
    wall["net_gex_slope15"] = (
        wall["net_gex_proxy"] - wall["net_gex_proxy_lag45"]
    ) / (SLOPE_LAG_MINUTES / SLOPE_NORMALIZATION_MINUTES)
    contiguous = wall["lag_minute"].eq(wall["minute"] - SLOPE_LAG_MINUTES)
    wall = wall.loc[
        contiguous & wall["minute"].between(FIRST_DECISION_MINUTE, LAST_DECISION_MINUTE)
    ].copy()
    values = wall[
        ["wall_net_gamma_total_log", "net_gex_proxy", "net_gex_slope15"]
    ].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise AssertionError("non-finite GEX state entered the development view")
    roundtrip = np.sign(wall["net_gex_proxy"]) * np.log1p(np.abs(wall["net_gex_proxy"]))
    if not np.allclose(
        roundtrip,
        wall["wall_net_gamma_total_log"],
        rtol=1e-12,
        atol=1e-12,
    ):
        raise AssertionError("signed-log GEX inversion failed")
    joined = master.merge(wall, on=KEY, how="left", validate="one_to_one", indicator=True)
    if not joined["_merge"].eq("both").all():
        raise AssertionError("an executable master key lacks exact wall state")
    joined = joined.drop(columns="_merge")
    if len(joined) != EXPECTED_DEVELOPMENT_ROWS:
        raise AssertionError(
            f"development master census changed: {len(joined)} != {EXPECTED_DEVELOPMENT_ROWS}"
        )
    if not joined["option_price_mode"].astype(str).eq("executable_quote").all():
        raise AssertionError("non-executable payoff source")
    if joined["trade_date"].str[:4].ne("2023").any():
        raise AssertionError("development loader opened a non-2023 outcome")
    joined["month"] = joined["trade_date"].str[:6]
    aligned = policy_candidates(joined, CANDIDATE_ARM)
    if len(aligned) != EXPECTED_ALIGNED_SIGNALS:
        raise AssertionError(
            f"aligned-signal census changed: {len(aligned)} != {EXPECTED_ALIGNED_SIGNALS}"
        )
    return joined.sort_values(KEY, kind="stable").reset_index(drop=True)


def policy_candidates(frame: pd.DataFrame, arm: str) -> pd.DataFrame:
    if arm not in ARMS:
        raise ValueError(f"unknown arm: {arm}")
    work = frame.copy()
    momentum = np.sign(pd.to_numeric(work["ret_15m_bps"], errors="coerce"))
    gex = pd.to_numeric(work["net_gex_proxy"], errors="coerce")
    slope = pd.to_numeric(work["net_gex_slope15"], errors="coerce")
    valid = np.isfinite(momentum) & np.isfinite(gex) & np.isfinite(slope)
    valid &= momentum.ne(0.0) & gex.ne(0.0) & slope.ne(0.0)
    if arm == CANDIDATE_ARM:
        valid &= np.sign(slope).eq(np.sign(gex))
    work = work.loc[valid].copy()
    momentum = momentum.loc[valid]
    gex = gex.loc[valid]
    action_sign = np.where(gex.lt(0.0), momentum, -momentum)
    work["action"] = np.where(action_sign > 0.0, "CALL", "PUT")
    work["score"] = 1.0
    return work


def economic_metrics(trades: pd.DataFrame) -> dict[str, float | int]:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "pnl": 0.0,
            "minimum_hold": math.nan,
            "maximum_hold": math.nan,
            "max_drawdown": 0.0,
            "call_rate": 0.0,
            "put_rate": 0.0,
        }
    ordered = trades.sort_values(["trade_date", "minute", "ticker"], kind="stable")
    returns = pd.to_numeric(ordered["realized_return"], errors="raise").to_numpy(float)
    gross_profit = float(returns[returns > 0.0].sum())
    gross_loss = float(-returns[returns < 0.0].sum())
    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0.0
        else (math.inf if gross_profit > 0.0 else 0.0)
    )
    equity = np.cumsum(returns)
    drawdown = np.r_[0.0, equity] - np.maximum.accumulate(np.r_[0.0, equity])
    hold = pd.to_numeric(ordered["exit_minutes"], errors="raise")
    action = ordered["action"].astype(str)
    return {
        "trades": int(len(ordered)),
        "win_rate": float(np.mean(returns > 0.0)),
        "profit_factor": float(profit_factor),
        "pnl": float(returns.sum()),
        "minimum_hold": float(hold.min()),
        "maximum_hold": float(hold.max()),
        "max_drawdown": float(-drawdown.min()),
        "call_rate": float(action.eq("CALL").mean()),
        "put_rate": float(action.eq("PUT").mean()),
    }


def gate_pass(metric: dict[str, float | int]) -> bool:
    hold = float(metric["minimum_hold"])
    return bool(
        float(metric["profit_factor"]) >= INNER_GATES["profit_factor"]
        and float(metric["win_rate"]) >= INNER_GATES["win_rate"]
        and int(metric["trades"]) >= INNER_GATES["trades"]
        and float(metric["pnl"]) > INNER_GATES["pnl"]
        and np.isfinite(hold)
        and hold >= INNER_GATES["minimum_hold"]
    )


def _concentration(trades: pd.DataFrame) -> tuple[float, float]:
    if trades.empty:
        return 0.0, 0.0
    positive = trades.loc[trades["realized_return"].gt(0.0), "realized_return"].astype(float)
    gross = float(positive.sum())
    if gross <= 0.0:
        return 0.0, 0.0
    daily = trades.groupby("trade_date", observed=True)["realized_return"].sum()
    return (
        float(positive.nlargest(5).sum() / gross),
        float(daily[daily > 0.0].nlargest(5).sum() / gross),
    )


def _atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _code_hashes() -> dict[str, str]:
    return {relative: sha256_file(ROOT / relative) for relative in CHECKPOINT_CODE_CLOSURE}


def _run_identity() -> dict[str, Any]:
    return {
        "schema": RUN_CHECKPOINT_SCHEMA,
        "experiment": EXPERIMENT,
        "months": list(DEVELOPMENT_MONTHS),
        "runner_protocol_sha256": runner_protocol_sha256(),
        "master_sha256": MASTER_SHA256,
        "wall_state_sha256": WALL_STATE_SHA256,
        "protocol_document_sha256": PROTOCOL_DOCUMENT_SHA256,
        "clarification_document_sha256": CLARIFICATION_DOCUMENT_SHA256,
        "code_hashes": _code_hashes(),
    }


def _ensure_run_checkpoint(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "RUN_CHECKPOINT.json"
    expected = _run_identity()
    if path.exists():
        stored = json.loads(path.read_text(encoding="utf-8"))
        if stored != expected:
            raise AssertionError("run checkpoint identity changed; use a new immutable target")
        return stored
    unexpected = [item.name for item in output_dir.iterdir() if not item.name.startswith(".")]
    if unexpected:
        raise AssertionError("output exists without run checkpoint")
    _atomic_json(path, expected)
    return expected


def _cell_identity(
    run_identity: dict[str, Any], *, month: str, ticker: str, arm: str
) -> dict[str, Any]:
    return {
        **run_identity,
        "schema": CELL_CHECKPOINT_SCHEMA,
        "month": month,
        "ticker": ticker,
        "arm": arm,
    }


def _write_cell_checkpoint(
    directory: Path,
    identity: dict[str, Any],
    metrics: pd.DataFrame,
    trades: pd.DataFrame,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    manifest_path.unlink(missing_ok=True)
    frames = {"metrics.csv": metrics, "trades.csv": trades}
    files: dict[str, Any] = {}
    for name, frame in frames.items():
        path = directory / name
        _atomic_csv(path, frame)
        files[name] = {
            "rows": int(len(frame)),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    _atomic_json(
        manifest_path,
        {**identity, "status": "COMPLETE", "atomic_manifest_last": True, "files": files},
    )


def _read_cell_checkpoint(
    directory: Path, identity: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if {key: manifest.get(key) for key in identity} != identity:
        raise AssertionError("cell checkpoint identity changed; use a new target")
    if manifest.get("status") != "COMPLETE" or manifest.get("atomic_manifest_last") is not True:
        return None
    outputs: list[pd.DataFrame] = []
    for name in ("metrics.csv", "trades.csv"):
        path = directory / name
        spec = manifest.get("files", {}).get(name, {})
        if (
            not path.is_file()
            or spec.get("sha256") != sha256_file(path)
            or int(spec.get("bytes", -1)) != path.stat().st_size
        ):
            return None
        frame = pd.read_csv(path)
        if int(spec.get("rows", -1)) != len(frame):
            return None
        outputs.append(frame)
    return outputs[0], outputs[1]


def _compute_cell(
    data: pd.DataFrame, *, month: str, ticker: str, arm: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cell = data.loc[data["month"].eq(month) & data["ticker"].eq(ticker)].copy()
    if cell.empty:
        raise AssertionError(f"empty development cell {month} {ticker}")
    candidates = policy_candidates(cell, arm)
    payoff = attach_selected_payoff(candidates) if not candidates.empty else candidates
    trades = replay_live_equivalent(payoff) if not payoff.empty else payoff
    if not trades.empty:
        trades = trades.assign(month=month, arm=arm, policy=EXPERIMENT)
    metric = economic_metrics(trades)
    metrics = pd.DataFrame(
        [
            {
                "month": month,
                "ticker": ticker,
                "arm": arm,
                "source_rows": int(len(cell)),
                "policy_candidates": int(len(candidates)),
                "scheduler_rejections": int(len(candidates) - len(trades)),
                **metric,
                "positive_month": bool(float(metric["pnl"]) > 0.0),
                "gate_pass": gate_pass(metric),
            }
        ]
    )
    return metrics, trades


def evaluate(data: pd.DataFrame, output_dir: Path) -> dict[str, Any]:
    run_identity = _ensure_run_checkpoint(output_dir)
    metric_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    built = 0
    reused = 0
    total = len(DEVELOPMENT_MONTHS) * len(SCHEDULER) * len(ARMS)
    index = 0
    for month in DEVELOPMENT_MONTHS:
        for ticker in ("SPXW", "QQQ", "SPY"):
            for arm in ARMS:
                index += 1
                identity = _cell_identity(run_identity, month=month, ticker=ticker, arm=arm)
                directory = output_dir / "cell_checkpoints" / month / ticker / arm
                cached = _read_cell_checkpoint(directory, identity)
                if cached is None:
                    metrics, trades = _compute_cell(data, month=month, ticker=ticker, arm=arm)
                    _write_cell_checkpoint(directory, identity, metrics, trades)
                    built += 1
                    status = "built"
                else:
                    metrics, trades = cached
                    reused += 1
                    status = "reused"
                metric_frames.append(metrics)
                if not trades.empty:
                    trade_frames.append(trades)
                print(
                    f"[cell {index}/{total}] {month} {ticker} {arm} checkpoint={status}",
                    flush=True,
                )
    monthly = pd.concat(metric_frames, ignore_index=True)
    monthly["gate_pass"] = monthly["gate_pass"].astype(str).str.lower().eq("true")
    monthly["positive_month"] = monthly["positive_month"].astype(str).str.lower().eq("true")
    trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    summaries: list[dict[str, Any]] = []
    concentration_rows: list[dict[str, Any]] = []
    for arm in ARMS:
        cells = monthly.loc[monthly["arm"].eq(arm)]
        arm_trades = trades.loc[trades["arm"].eq(arm)] if not trades.empty else trades
        scopes = [("POOLED", arm_trades)] + [
            (ticker, arm_trades.loc[arm_trades["ticker"].eq(ticker)])
            for ticker in ("SPXW", "QQQ", "SPY")
        ]
        concentration_pass = True
        for scope, scoped in scopes:
            top_trades, top_days = _concentration(scoped)
            passed = bool(
                top_trades <= MAX_TOP5_TRADE_GROSS_PROFIT_SHARE
                and top_days <= MAX_TOP5_DAY_GROSS_PROFIT_SHARE
            )
            concentration_pass &= passed
            concentration_rows.append(
                {
                    "arm": arm,
                    "scope": scope,
                    "trades": int(len(scoped)),
                    "top5_trade_gross_profit_share": top_trades,
                    "top5_day_gross_profit_share": top_days,
                    "concentration_pass": passed,
                }
            )
        pooled = economic_metrics(arm_trades)
        all_months_pass = bool(len(cells) == 36 and cells["gate_pass"].all())
        base_pass = bool(arm == CANDIDATE_ARM and all_months_pass and concentration_pass)
        summaries.append(
            {
                "arm": arm,
                **pooled,
                "ticker_month_cells": int(len(cells)),
                "passing_cells": int(cells["gate_pass"].sum()),
                "minimum_monthly_trades": int(cells["trades"].min()),
                "worst_month_pf": float(cells["profit_factor"].min()),
                "worst_month_wr": float(cells["win_rate"].min()),
                "worst_month_pnl": float(cells["pnl"].min()),
                "positive_month_rate": float(cells["positive_month"].mean()),
                "all_ticker_month_gates_pass": all_months_pass,
                "concentration_pass": concentration_pass,
                "base_economic_pass": base_pass,
            }
        )
    portfolio = pd.DataFrame(summaries)
    concentration = pd.DataFrame(concentration_rows)
    base_pass = bool(portfolio["base_economic_pass"].any())
    outputs = {
        "monthly_metrics.csv": monthly,
        "trades.csv": trades,
        "portfolio_summary.csv": portfolio,
        "concentration.csv": concentration,
    }
    for name, frame in outputs.items():
        _atomic_csv(output_dir / name, frame)
    result = {
        "schema": "king_gex_slope1_development_results_v1",
        "experiment": EXPERIMENT,
        "status": "PASS_DEVELOPMENT" if base_pass else "FAILED_ECONOMIC",
        "runner_protocol_sha256": runner_protocol_sha256(),
        "candidate_arm": CANDIDATE_ARM,
        "candidate_found": False,
        "base_economic_pass": base_pass,
        "development_promising": base_pass,
        "checkpoint": {
            "schema": CELL_CHECKPOINT_SCHEMA,
            "cells_total": total,
            "cells_built_this_run": built,
            "cells_reused_this_run": reused,
            "atomic_manifest_last": True,
        },
        "files": {
            name: {"sha256": sha256_file(output_dir / name), "bytes": (output_dir / name).stat().st_size}
            for name in outputs
        },
        "live_parity": "RESEARCH_PROXY_LIVE_PARITY_BLOCKED",
        "outer_2024_2025_opened": False,
        "holdout_2026_opened": False,
        "june_2026_sealed": True,
        "production_modified": False,
    }
    _atomic_json(output_dir / "SUMMARY.json", result)
    result["summary_sha256"] = sha256_file(output_dir / "SUMMARY.json")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = (ROOT / args.output_dir).resolve()
    authorized = (ROOT / "tmp/king_gex_slope_v1").resolve()
    if authorized != output and authorized not in output.parents:
        raise AssertionError("development output must remain under tmp/king_gex_slope_v1")
    data = load_development_data()
    result = evaluate(data, output)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
