"""Resumable executable exit study for the frozen KING-GEX K1 opportunities."""

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
from neural.jepa.build_event_option_dataset import load_chain, select_contract
from neural.jepa.evaluate_king_gex_slope_v1 import (
    CANDIDATE_ARM,
    EXPECTED_ALIGNED_SIGNALS,
    INNER_GATES,
    KEY,
    MASTER,
    MASTER_SHA256,
    MAX_TOP5_DAY_GROSS_PROFIT_SHARE,
    MAX_TOP5_TRADE_GROSS_PROFIT_SHARE,
    WALL_STATE_SHA256,
    _concentration,
    economic_metrics,
    gate_pass,
    load_development_data,
    policy_candidates,
    runner_protocol_sha256 as king_runner_protocol_sha256,
)
from neural.jepa.existing_data_edge_scheduler_v1 import (
    SCHEDULER,
    _assert_scheduler_output,
    replay_live_equivalent,
)


EXPERIMENT = "KING_GEX_EXIT1_EXECUTABLE_V1"
DIRECTIONS = ("D0_K1", "D1_INVERTED")
MONTHS = tuple(f"2023{month:02d}" for month in range(1, 13))
PREDECLARATION = ROOT / "research_papers/JEPA/KING_GEX_EXIT1_EXECUTABLE_PREDECLARATION.md"
PREDECLARATION_SHA256 = "4cb58b26f772a52ad7f7599cc70daa851f7cb6e38fff596a2b6dbe7e39db79c4"
RUNTIME_CLARIFICATION = ROOT / "research_papers/JEPA/KING_GEX_EXIT1_RUNTIME_CLARIFICATION.md"
RUNTIME_CLARIFICATION_SHA256 = "a60ad8e273d1aca5b707703be42241bad0f8474cc891ea9598596632d1dd6c20"
SOURCE_MANIFEST = (
    ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "thetadata_manifest_spxw_spy_qqq_202201_202605_sealed_v1/"
    "thetadata_option_manifest.csv"
)
SOURCE_MANIFEST_SHA256 = "88be8a2ff44c18fb57fca360d31def574ddbb0419a792fc88349942711d2974a"
RUN_SCHEMA = "king_gex_exit1_run_checkpoint_v1"
SOURCE_CELL_SCHEMA = "king_gex_exit1_source_cell_checkpoint_v1"
POLICY_SCHEMA = "king_gex_exit1_policy_checkpoint_v1"
MIN_HOLD_MINUTES = 30
TAKE_PROFIT = 10.0


def _config(
    config_id: str,
    stop_loss: float,
    trail_activation: float,
    trail_drawdown: float,
    horizon_minutes: int,
) -> dict[str, Any]:
    return {
        "config_id": config_id,
        "stop_loss": stop_loss,
        "trail_activation": trail_activation,
        "trail_drawdown": trail_drawdown,
        "horizon_minutes": horizon_minutes,
        "min_hold_minutes": MIN_HOLD_MINUTES,
        "take_profit": TAKE_PROFIT,
    }


EXIT_CONFIGS = (
    _config("B00", 0.60, 0.50, 0.25, 180),
    _config("S30", 0.30, 0.50, 0.25, 180),
    _config("S40", 0.40, 0.50, 0.25, 180),
    _config("S50", 0.50, 0.50, 0.25, 180),
    _config("S80", 0.80, 0.50, 0.25, 180),
    _config("S100", 1.00, 0.50, 0.25, 180),
    _config("H60", 0.60, 0.50, 0.25, 60),
    _config("H90", 0.60, 0.50, 0.25, 90),
    _config("H120", 0.60, 0.50, 0.25, 120),
    _config("T30D15", 0.60, 0.30, 0.15, 180),
    _config("T50D15", 0.60, 0.50, 0.15, 180),
    _config("T50D40", 0.60, 0.50, 0.40, 180),
    _config("T75D25", 0.60, 0.75, 0.25, 180),
    _config("S40_T30D15", 0.40, 0.30, 0.15, 180),
    _config("S40_T50D40", 0.40, 0.50, 0.40, 180),
    _config("S40_H90", 0.40, 0.50, 0.25, 90),
)
CONFIG_BY_ID = {str(item["config_id"]): item for item in EXIT_CONFIGS}


def _canonical_sha(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def protocol() -> dict[str, Any]:
    return {
        "schema": "king_gex_exit1_protocol_v1",
        "experiment": EXPERIMENT,
        "development_months": list(MONTHS),
        "directions": list(DIRECTIONS),
        "configs": list(EXIT_CONFIGS),
        "opportunities": "KING_GEX K1 aligned exact executable master",
        "entry": "selected contract ask at exact entry snapshot",
        "exit": "future bid; stop then trail then peak update/TP; forced final mark",
        "scheduler": SCHEDULER,
        "gates": INNER_GATES,
        "concentration": {
            "top5_trade_max": MAX_TOP5_TRADE_GROSS_PROFIT_SHARE,
            "top5_day_max": MAX_TOP5_DAY_GROSS_PROFIT_SHARE,
        },
        "selection": ["worst_month_pf", "worst_month_wr", "pooled_pf", "config_id"],
        "outer_2024_2025_opened": False,
        "holdout_2026_opened": False,
        "june_2026_sealed": True,
    }


def protocol_sha256() -> str:
    return _canonical_sha(protocol())


def _code_hashes() -> dict[str, str]:
    paths = (
        "neural/jepa/evaluate_king_gex_exit_v1.py",
        "neural/jepa/evaluate_king_gex_slope_v1.py",
        "neural/jepa/build_event_option_dataset.py",
        "neural/jepa/existing_data_edge_scheduler_v1.py",
    )
    return {path: sha256_file(ROOT / path) for path in paths}


def _run_identity() -> dict[str, Any]:
    return {
        "schema": RUN_SCHEMA,
        "experiment": EXPERIMENT,
        "protocol_sha256": protocol_sha256(),
        "king_runner_protocol_sha256": king_runner_protocol_sha256(),
        "master_sha256": MASTER_SHA256,
        "wall_state_sha256": WALL_STATE_SHA256,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "predeclaration_sha256": PREDECLARATION_SHA256,
        "runtime_clarification_sha256": RUNTIME_CLARIFICATION_SHA256,
        "code_hashes": _code_hashes(),
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def _atomic_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def _ensure_run_checkpoint(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "RUN_CHECKPOINT.json"
    expected = _run_identity()
    if path.exists():
        stored = json.loads(path.read_text(encoding="utf-8"))
        if stored != expected:
            raise AssertionError("run checkpoint identity changed; use a new target")
        return stored
    unexpected = [item.name for item in output_dir.iterdir() if not item.name.startswith(".")]
    if unexpected:
        raise AssertionError("output exists without a run checkpoint")
    _atomic_json(path, expected)
    return expected


def _extra_columns() -> list[str]:
    return [
        *KEY,
        *[
            f"{side}_d{bucket:02d}_{suffix}"
            for side in ("call", "put")
            for bucket in (25, 35)
            for suffix in ("strike", "opt_status", "opt_max_ret", "opt_min_ret")
        ],
    ]


def load_exit_candidates() -> pd.DataFrame:
    if sha256_file(PREDECLARATION) != PREDECLARATION_SHA256:
        raise AssertionError("KING-GEX-EXIT1 predeclaration changed")
    if sha256_file(RUNTIME_CLARIFICATION) != RUNTIME_CLARIFICATION_SHA256:
        raise AssertionError("KING-GEX-EXIT1 runtime clarification changed")
    if sha256_file(SOURCE_MANIFEST) != SOURCE_MANIFEST_SHA256:
        raise AssertionError("ThetaData source manifest changed")
    base = load_development_data()
    extra = pd.read_parquet(
        MASTER,
        columns=_extra_columns(),
        filters=[("trade_date", ">=", "20230101"), ("trade_date", "<=", "20231231")],
    )
    extra["ticker"] = extra["ticker"].astype(str).str.upper()
    extra["trade_date"] = extra["trade_date"].astype(str).str.replace("-", "", regex=False).str[:8]
    extra["minute"] = pd.to_numeric(extra["minute"], errors="raise").astype(int)
    if extra.duplicated(KEY).any():
        raise AssertionError("exit diagnostic master keys are not unique")
    merged = base.merge(extra, on=KEY, how="left", validate="one_to_one", indicator=True)
    if not merged["_merge"].eq("both").all():
        raise AssertionError("a KING-GEX opportunity lacks exact exit diagnostics")
    candidates = policy_candidates(merged.drop(columns="_merge"), CANDIDATE_ARM)
    if len(candidates) != EXPECTED_ALIGNED_SIGNALS:
        raise AssertionError("K1 opportunity census changed")
    candidates["month"] = candidates["trade_date"].str[:6]
    return candidates.sort_values(KEY, kind="stable").reset_index(drop=True)


def load_source_manifest() -> pd.DataFrame:
    frame = pd.read_csv(SOURCE_MANIFEST, dtype={"trade_date": str, "expiration": str})
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["trade_date"] = frame["trade_date"].astype(str).str.replace("-", "", regex=False).str[:8]
    frame = frame.loc[
        frame["ticker"].isin(SCHEDULER)
        & frame["trade_date"].str.startswith("2023")
        & frame["expiry_mode"].astype(str).eq("zero_dte")
    ].copy()
    if frame.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("zero-DTE source manifest keys are not unique")
    required = ("greeks_path", "oi_path", "ohlc_path")
    if frame[list(required)].isna().any().any():
        raise AssertionError("source manifest contains missing path")
    return frame.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)


def _source_hashes(cell: pd.DataFrame, manifest: pd.DataFrame) -> dict[str, Any]:
    dates = sorted(cell["trade_date"].astype(str).unique())
    part = manifest.loc[
        manifest["ticker"].eq(str(cell["ticker"].iloc[0]))
        & manifest["trade_date"].isin(dates)
    ]
    if len(part) != len(dates):
        raise AssertionError("a source day is missing from the manifest")
    output: dict[str, Any] = {}
    for row in part.itertuples(index=False):
        output[str(row.trade_date)] = {
            name: sha256_file(Path(str(getattr(row, name))))
            for name in ("greeks_path", "oi_path", "ohlc_path")
        }
    return output


def _raw_quote_path(
    quotes: pd.DataFrame,
    contract: pd.Series,
    ts: pd.Timestamp,
) -> tuple[float, pd.DataFrame]:
    entry_ask = float(contract.get("ask", np.nan))
    entry_bid = float(contract.get("bid", np.nan))
    if not np.isfinite(entry_ask) or not np.isfinite(entry_bid) or entry_bid <= 0.0 or entry_ask < entry_bid:
        raise AssertionError("invalid executable entry quote")
    quote_time = pd.to_datetime(quotes["quote_dt"], errors="coerce")
    bid = pd.to_numeric(quotes["bid"], errors="coerce")
    ask = pd.to_numeric(quotes["ask"], errors="coerce")
    path = pd.DataFrame({"quote_time": quote_time, "exit_bid": bid, "ask": ask})
    path = path.loc[
        (path["quote_time"] > ts)
        & (path["quote_time"] <= ts + pd.Timedelta(minutes=180))
        & np.isfinite(path["exit_bid"])
        & np.isfinite(path["ask"])
        & path["exit_bid"].ge(0.0)
        & path["ask"].ge(path["exit_bid"])
    ].copy()
    path = path.sort_values("quote_time", kind="stable").drop_duplicates("quote_time", keep="last")
    return entry_ask, path[["quote_time", "exit_bid"]].reset_index(drop=True)


def simulate_quote_path_reference(
    raw_path: pd.DataFrame,
    entry_ask: float,
    ts: pd.Timestamp,
    config: dict[str, Any],
) -> dict[str, Any]:
    horizon = int(config["horizon_minutes"])
    end_ts = ts + pd.Timedelta(minutes=horizon)
    path = raw_path.loc[pd.to_datetime(raw_path["quote_time"]) <= end_ts].copy()
    forced_exit = min(end_ts, ts.normalize() + pd.Timedelta(hours=16))
    if path.empty or pd.Timestamp(path.iloc[-1]["quote_time"]) < forced_exit:
        path = pd.concat(
            [path, pd.DataFrame([{"quote_time": forced_exit, "exit_bid": 0.0}])],
            ignore_index=True,
        )
    returns = pd.to_numeric(path["exit_bid"], errors="raise").astype(float) / float(entry_ask) - 1.0
    max_ret = float(returns.max())
    min_ret = float(returns.min())
    peak_ret = -float("inf")
    status = 0
    exit_ret = math.nan
    exit_minutes = 0
    exit_reason = "horizon"
    for item in path.itertuples(index=False):
        elapsed = int((pd.Timestamp(item.quote_time) - ts).total_seconds() // 60)
        mark_ret = float(item.exit_bid) / float(entry_ask) - 1.0
        if elapsed < int(config["min_hold_minutes"]):
            peak_ret = max(peak_ret, mark_ret)
            continue
        if mark_ret <= -float(config["stop_loss"]):
            status = -1
            exit_ret = mark_ret
            exit_minutes = elapsed
            exit_reason = "stop"
            break
        if (
            peak_ret >= float(config["trail_activation"])
            and mark_ret <= peak_ret - float(config["trail_drawdown"])
        ):
            status = 1 if mark_ret > 0.0 else -1
            exit_ret = mark_ret
            exit_minutes = elapsed
            exit_reason = "trail"
            break
        peak_ret = max(peak_ret, mark_ret)
        if mark_ret >= float(config["take_profit"]):
            status = 1
            exit_ret = mark_ret
            exit_minutes = elapsed
            exit_reason = "take_profit"
            break
    if status == 0:
        exit_ret = float(returns.iloc[-1])
        exit_minutes = int((pd.Timestamp(path.iloc[-1]["quote_time"]) - ts).total_seconds() // 60)
    if not np.isfinite(exit_ret) or not MIN_HOLD_MINUTES <= exit_minutes <= 180:
        raise AssertionError("alternate exit produced invalid return/hold")
    return {
        "realized_return": float(exit_ret),
        "exit_minutes": int(exit_minutes),
        "status": int(status),
        "max_ret": max_ret,
        "min_ret": min_ret,
        "exit_reason": exit_reason,
    }


def _horizon_arrays(
    raw_path: pd.DataFrame,
    ts: pd.Timestamp,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    quote_time = pd.to_datetime(raw_path["quote_time"], errors="raise")
    elapsed_all = ((quote_time - ts).dt.total_seconds() // 60).to_numpy(dtype=np.int64)
    bids_all = pd.to_numeric(raw_path["exit_bid"], errors="raise").to_numpy(dtype=float)
    keep = elapsed_all <= int(horizon)
    elapsed = elapsed_all[keep]
    bids = bids_all[keep]
    forced_ts = min(
        ts + pd.Timedelta(minutes=int(horizon)),
        ts.normalize() + pd.Timedelta(hours=16),
    )
    forced_elapsed = int((forced_ts - ts).total_seconds() // 60)
    if len(elapsed) == 0 or int(elapsed[-1]) < forced_elapsed:
        elapsed = np.append(elapsed, forced_elapsed)
        bids = np.append(bids, 0.0)
    return elapsed, bids


def _simulate_arrays(
    elapsed: np.ndarray,
    bids: np.ndarray,
    entry_ask: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    returns = bids.astype(float, copy=False) / float(entry_ask) - 1.0
    if len(returns) == 0 or not np.isfinite(returns).all():
        raise AssertionError("alternate path arrays are empty/non-finite")
    cumulative_peak = np.maximum.accumulate(returns)
    peak_before = np.empty_like(cumulative_peak)
    peak_before[0] = -float("inf")
    peak_before[1:] = cumulative_peak[:-1]
    eligible = elapsed >= int(config["min_hold_minutes"])
    stop = eligible & (returns <= -float(config["stop_loss"]))
    trail = (
        eligible
        & (peak_before >= float(config["trail_activation"]))
        & (returns <= peak_before - float(config["trail_drawdown"]))
    )
    take_profit = eligible & (returns >= float(config["take_profit"]))
    triggered = stop | trail | take_profit
    positions = np.flatnonzero(triggered)
    if len(positions):
        position = int(positions[0])
        if bool(stop[position]):
            reason = "stop"
            status = -1
        elif bool(trail[position]):
            reason = "trail"
            status = 1 if float(returns[position]) > 0.0 else -1
        else:
            reason = "take_profit"
            status = 1
    else:
        position = len(returns) - 1
        reason = "horizon"
        status = 0
    exit_ret = float(returns[position])
    exit_minutes = int(elapsed[position])
    if not np.isfinite(exit_ret) or not MIN_HOLD_MINUTES <= exit_minutes <= 180:
        raise AssertionError("alternate exit produced invalid return/hold")
    return {
        "realized_return": exit_ret,
        "exit_minutes": exit_minutes,
        "status": status,
        "max_ret": float(returns.max()),
        "min_ret": float(returns.min()),
        "exit_reason": reason,
    }


def simulate_quote_path(
    raw_path: pd.DataFrame,
    entry_ask: float,
    ts: pd.Timestamp,
    config: dict[str, Any],
) -> dict[str, Any]:
    elapsed, bids = _horizon_arrays(raw_path, ts, int(config["horizon_minutes"]))
    return _simulate_arrays(elapsed, bids, entry_ask, config)


def simulate_all_configs(
    raw_path: pd.DataFrame,
    entry_ask: float,
    ts: pd.Timestamp,
) -> dict[str, dict[str, Any]]:
    arrays = {
        horizon: _horizon_arrays(raw_path, ts, horizon)
        for horizon in sorted({int(item["horizon_minutes"]) for item in EXIT_CONFIGS})
    }
    return {
        str(config["config_id"]): _simulate_arrays(
            *arrays[int(config["horizon_minutes"])], entry_ask, config
        )
        for config in EXIT_CONFIGS
    }


def _expected_baseline(row: Any, side: str, bucket: int) -> dict[str, float | int]:
    prefix = f"{side.lower()}_d{bucket:02d}"
    return {
        "realized_return": float(getattr(row, f"{prefix}_opt_exit_ret")),
        "exit_minutes": int(getattr(row, f"{prefix}_opt_exit_minutes")),
        "status": int(getattr(row, f"{prefix}_opt_status")),
        "max_ret": float(getattr(row, f"{prefix}_opt_max_ret")),
        "min_ret": float(getattr(row, f"{prefix}_opt_min_ret")),
    }


def assert_baseline_parity(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    for key in ("exit_minutes", "status"):
        if int(actual[key]) != int(expected[key]):
            raise AssertionError(f"baseline {key} mismatch: {actual[key]} != {expected[key]}")
    for key in ("realized_return", "max_ret", "min_ret"):
        if not np.isclose(float(actual[key]), float(expected[key]), rtol=1e-7, atol=1e-7):
            raise AssertionError(f"baseline {key} mismatch: {actual[key]} != {expected[key]}")


def build_source_cell(
    cell: pd.DataFrame,
    manifest: pd.DataFrame,
) -> pd.DataFrame:
    ticker = str(cell["ticker"].iloc[0])
    bucket = int(SCHEDULER[ticker]["bucket"])
    manifest_lookup = {
        str(row.trade_date): pd.Series(row._asdict())
        for row in manifest.loc[manifest["ticker"].eq(ticker)].itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []
    for trade_date, day in cell.groupby("trade_date", sort=True, observed=True):
        source = manifest_lookup.get(str(trade_date))
        if source is None:
            raise AssertionError(f"missing source manifest row: {ticker} {trade_date}")
        greeks, _ = load_chain(
            source,
            require_open_interest=True,
            option_price_mode="executable_quote",
        )
        if greeks.empty:
            raise AssertionError(f"empty executable chain: {ticker} {trade_date}")
        snapshots = {stamp: part for stamp, part in greeks.groupby("dt", sort=False, observed=True)}
        quote_groups = {
            (str(right), float(strike)): part
            for (right, strike), part in greeks.groupby(["right", "strike"], sort=False, observed=True)
        }
        for event in day.itertuples(index=False):
            ts = pd.Timestamp(str(event.trade_date)) + pd.Timedelta(minutes=int(event.minute))
            snapshot = snapshots.get(ts)
            if snapshot is None or snapshot.empty:
                raise AssertionError(f"missing exact entry snapshot: {ticker} {event.trade_date} {event.minute}")
            for side in ("CALL", "PUT"):
                contract = select_contract(snapshot, side, bucket / 100.0, "executable_quote")
                if contract is None:
                    raise AssertionError("frozen K1 event lost an executable contract")
                prefix = f"{side.lower()}_d{bucket:02d}"
                expected_strike = float(getattr(event, f"{prefix}_strike"))
                if not np.isclose(float(contract["strike"]), expected_strike, rtol=0.0, atol=1e-6):
                    raise AssertionError("selected contract strike differs from frozen master")
                quotes = quote_groups.get((side, float(contract["strike"])))
                if quotes is None:
                    raise AssertionError("selected contract has no quote path")
                entry_ask, raw_path = _raw_quote_path(quotes, contract, ts)
                expected = _expected_baseline(event, side, bucket)
                outcomes = simulate_all_configs(raw_path, entry_ask, ts)
                for config in EXIT_CONFIGS:
                    outcome = outcomes[str(config["config_id"])]
                    if str(config["config_id"]) == "B00":
                        assert_baseline_parity(outcome, expected)
                    rows.append(
                        {
                            "ticker": ticker,
                            "trade_date": str(event.trade_date),
                            "minute": int(event.minute),
                            "month": str(event.trade_date)[:6],
                            "side": side,
                            "config_id": str(config["config_id"]),
                            "strike": float(contract["strike"]),
                            "entry_ask": entry_ask,
                            **outcome,
                        }
                    )
    output = pd.DataFrame(rows)
    expected_rows = len(cell) * 2 * len(EXIT_CONFIGS)
    if len(output) != expected_rows or output.duplicated([*KEY, "side", "config_id"]).any():
        raise AssertionError("source-cell outcome census/key contract failed")
    return output.sort_values([*KEY, "side", "config_id"], kind="stable").reset_index(drop=True)


def _checkpoint_files_valid(directory: Path, manifest: dict[str, Any]) -> bool:
    for name, spec in manifest.get("files", {}).items():
        path = directory / name
        if (
            not path.is_file()
            or sha256_file(path) != spec.get("sha256")
            or path.stat().st_size != int(spec.get("bytes", -1))
        ):
            return False
        if name.endswith(".parquet"):
            rows = len(pd.read_parquet(path))
        else:
            rows = len(pd.read_csv(path))
        if rows != int(spec.get("rows", -1)):
            return False
    return True


def _write_source_checkpoint(
    directory: Path,
    identity: dict[str, Any],
    outcomes: pd.DataFrame,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    manifest_path.unlink(missing_ok=True)
    path = directory / "outcomes.parquet"
    _atomic_parquet(path, outcomes)
    _atomic_json(
        manifest_path,
        {
            **identity,
            "status": "COMPLETE",
            "atomic_manifest_last": True,
            "files": {
                path.name: {
                    "rows": len(outcomes),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            },
        },
    )


def _read_source_checkpoint(directory: Path, identity: dict[str, Any]) -> pd.DataFrame | None:
    path = directory / "manifest.json"
    if not path.exists():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if {key: manifest.get(key) for key in identity} != identity:
        raise AssertionError("source checkpoint identity changed; use a new target")
    if manifest.get("status") != "COMPLETE" or manifest.get("atomic_manifest_last") is not True:
        return None
    if not _checkpoint_files_valid(directory, manifest):
        return None
    return pd.read_parquet(directory / "outcomes.parquet")


def prepare_source_outcomes(
    candidates: pd.DataFrame,
    source_manifest: pd.DataFrame,
    output_dir: Path,
    run_identity: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, int], dict[str, str]]:
    frames: list[pd.DataFrame] = []
    checkpoint_hashes: dict[str, str] = {}
    built = 0
    reused = 0
    index = 0
    for month in MONTHS:
        for ticker in ("SPXW", "QQQ", "SPY"):
            index += 1
            cell = candidates.loc[candidates["month"].eq(month) & candidates["ticker"].eq(ticker)].copy()
            if cell.empty:
                raise AssertionError(f"empty K1 source cell: {month} {ticker}")
            raw_hashes = _source_hashes(cell, source_manifest)
            identity = {
                **run_identity,
                "schema": SOURCE_CELL_SCHEMA,
                "month": month,
                "ticker": ticker,
                "candidate_keys_sha256": _canonical_sha(cell[KEY].to_dict("records")),
                "raw_source_hashes": raw_hashes,
            }
            directory = output_dir / "source_checkpoints" / month / ticker
            outcomes = _read_source_checkpoint(directory, identity)
            if outcomes is None:
                outcomes = build_source_cell(cell, source_manifest)
                _write_source_checkpoint(directory, identity, outcomes)
                built += 1
                status = "built"
            else:
                reused += 1
                status = "reused"
            frames.append(outcomes)
            manifest_path = directory / "manifest.json"
            checkpoint_hashes[f"{month}/{ticker}"] = sha256_file(manifest_path)
            print(f"[source {index}/36] {month} {ticker} checkpoint={status}", flush=True)
    combined = pd.concat(frames, ignore_index=True)
    expected = EXPECTED_ALIGNED_SIGNALS * 2 * len(EXIT_CONFIGS)
    if len(combined) != expected or combined.duplicated([*KEY, "side", "config_id"]).any():
        raise AssertionError("combined source outcome census/key contract failed")
    return combined, {"built": built, "reused": reused}, checkpoint_hashes


def _direction_action(candidates: pd.DataFrame, direction: str) -> pd.Series:
    action = candidates["action"].astype(str).str.upper()
    if direction == "D0_K1":
        return action
    if direction == "D1_INVERTED":
        return action.map({"CALL": "PUT", "PUT": "CALL"})
    raise ValueError(f"unknown direction: {direction}")


def evaluate_policy(
    candidates: pd.DataFrame,
    outcomes: pd.DataFrame,
    direction: str,
    config_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    work = candidates.copy()
    work["action"] = _direction_action(work, direction)
    selected = outcomes.loc[outcomes["config_id"].eq(config_id)].rename(columns={"side": "action"})
    selected = selected[[*KEY, "action", "realized_return", "exit_minutes", "status", "exit_reason"]]
    work = work.merge(selected, on=[*KEY, "action"], how="left", validate="one_to_one", indicator=True)
    if not work["_merge"].eq("both").all():
        raise AssertionError("a policy candidate lacks its alternate executable outcome")
    work = work.drop(columns="_merge")
    if not np.isfinite(work[["realized_return", "exit_minutes"]].to_numpy(float)).all():
        raise AssertionError("policy contains missing/non-finite payoff")
    work["score"] = 1.0
    work["date"] = work["trade_date"]
    trades = replay_live_equivalent(work)
    _assert_scheduler_output(trades)
    trades["month"] = trades["trade_date"].astype(str).str[:6]
    trades["direction"] = direction
    trades["config_id"] = config_id
    monthly_rows: list[dict[str, Any]] = []
    for month in MONTHS:
        for ticker in ("SPXW", "QQQ", "SPY"):
            part = trades.loc[trades["month"].eq(month) & trades["ticker"].eq(ticker)]
            metric = economic_metrics(part)
            monthly_rows.append(
                {
                    "month": month,
                    "ticker": ticker,
                    "direction": direction,
                    "config_id": config_id,
                    **metric,
                    "positive_month": bool(float(metric["pnl"]) > 0.0),
                    "gate_pass": gate_pass(metric),
                }
            )
    monthly = pd.DataFrame(monthly_rows)
    concentration_rows: list[dict[str, Any]] = []
    concentration_pass = True
    for scope, part in [("POOLED", trades)] + [
        (ticker, trades.loc[trades["ticker"].eq(ticker)]) for ticker in ("SPXW", "QQQ", "SPY")
    ]:
        top_trades, top_days = _concentration(part)
        passed = bool(
            top_trades <= MAX_TOP5_TRADE_GROSS_PROFIT_SHARE
            and top_days <= MAX_TOP5_DAY_GROSS_PROFIT_SHARE
        )
        concentration_pass &= passed
        concentration_rows.append(
            {
                "direction": direction,
                "config_id": config_id,
                "scope": scope,
                "trades": len(part),
                "top5_trade_gross_profit_share": top_trades,
                "top5_day_gross_profit_share": top_days,
                "concentration_pass": passed,
            }
        )
    concentration = pd.DataFrame(concentration_rows)
    pooled = economic_metrics(trades)
    eligible = bool(len(monthly) == 36 and monthly["gate_pass"].all() and concentration_pass)
    summary = pd.DataFrame(
        [
            {
                "direction": direction,
                "config_id": config_id,
                **pooled,
                "passing_cells": int(monthly["gate_pass"].sum()),
                "minimum_monthly_trades": int(monthly["trades"].min()),
                "worst_month_pf": float(monthly["profit_factor"].min()),
                "worst_month_wr": float(monthly["win_rate"].min()),
                "worst_month_pnl": float(monthly["pnl"].min()),
                "positive_month_rate": float(monthly["positive_month"].mean()),
                "concentration_pass": concentration_pass,
                "eligible_36_of_36": eligible,
            }
        ]
    )
    return monthly, trades, concentration, summary


def _write_policy_checkpoint(
    directory: Path,
    identity: dict[str, Any],
    frames: dict[str, pd.DataFrame],
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    manifest_path.unlink(missing_ok=True)
    files: dict[str, Any] = {}
    for name, frame in frames.items():
        path = directory / name
        _atomic_csv(path, frame)
        files[name] = {"rows": len(frame), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
    _atomic_json(
        manifest_path,
        {**identity, "status": "COMPLETE", "atomic_manifest_last": True, "files": files},
    )


def _read_policy_checkpoint(
    directory: Path,
    identity: dict[str, Any],
) -> dict[str, pd.DataFrame] | None:
    path = directory / "manifest.json"
    if not path.exists():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if {key: manifest.get(key) for key in identity} != identity:
        raise AssertionError("policy checkpoint identity changed; use a new target")
    if manifest.get("status") != "COMPLETE" or manifest.get("atomic_manifest_last") is not True:
        return None
    if not _checkpoint_files_valid(directory, manifest):
        return None
    return {name: pd.read_csv(directory / name, dtype={"month": str}) for name in manifest["files"]}


def _assert_baseline_aggregates(summary: pd.DataFrame) -> None:
    expected = {
        "D0_K1": (1324, 0.42220543806646527, 0.8044194011408395, -89.84473407058478),
        "D1_INVERTED": (1304, 0.4302147239263804, 0.8502829098236963, -67.67717732675477),
    }
    for direction, values in expected.items():
        row = summary.loc[summary["direction"].eq(direction) & summary["config_id"].eq("B00")]
        if len(row) != 1:
            raise AssertionError("missing baseline policy summary")
        actual = row.iloc[0]
        if int(actual["trades"]) != values[0]:
            raise AssertionError("baseline aggregate trade count changed")
        for column, value in zip(("win_rate", "profit_factor", "pnl"), values[1:], strict=True):
            if not np.isclose(float(actual[column]), value, rtol=1e-12, atol=1e-12):
                raise AssertionError(f"baseline aggregate {column} changed")


def evaluate(
    candidates: pd.DataFrame,
    source_outcomes: pd.DataFrame,
    output_dir: Path,
    run_identity: dict[str, Any],
    source_checkpoint_hashes: dict[str, str],
) -> dict[str, Any]:
    source_seal_sha = _canonical_sha(source_checkpoint_hashes)
    frames = {name: [] for name in ("monthly_metrics.csv", "trades.csv", "concentration.csv", "policy_summary.csv")}
    built = 0
    reused = 0
    index = 0
    for direction in DIRECTIONS:
        for config in EXIT_CONFIGS:
            index += 1
            config_id = str(config["config_id"])
            identity = {
                **run_identity,
                "schema": POLICY_SCHEMA,
                "direction": direction,
                "config": config,
                "source_checkpoint_seal_sha256": source_seal_sha,
            }
            directory = output_dir / "policy_checkpoints" / direction / config_id
            cached = _read_policy_checkpoint(directory, identity)
            if cached is None:
                monthly, trades, concentration, summary = evaluate_policy(
                    candidates, source_outcomes, direction, config_id
                )
                cached = {
                    "monthly_metrics.csv": monthly,
                    "trades.csv": trades,
                    "concentration.csv": concentration,
                    "policy_summary.csv": summary,
                }
                _write_policy_checkpoint(directory, identity, cached)
                built += 1
                status = "built"
            else:
                reused += 1
                status = "reused"
            for name in frames:
                frames[name].append(cached[name])
            print(f"[policy {index}/32] {direction} {config_id} checkpoint={status}", flush=True)
    combined = {name: pd.concat(parts, ignore_index=True) for name, parts in frames.items()}
    summary = combined["policy_summary.csv"]
    for column in ("eligible_36_of_36", "concentration_pass"):
        summary[column] = summary[column].astype(str).str.lower().eq("true")
    _assert_baseline_aggregates(summary)
    eligible = summary.loc[summary["eligible_36_of_36"]].copy()
    selected: dict[str, Any] | None = None
    if not eligible.empty:
        eligible = eligible.sort_values(
            ["worst_month_pf", "worst_month_wr", "profit_factor", "config_id"],
            ascending=[False, False, False, True],
            kind="stable",
        )
        selected = eligible.iloc[0].to_dict()
    for name, frame in combined.items():
        _atomic_csv(output_dir / name, frame)
    result = {
        "schema": "king_gex_exit1_development_results_v1",
        "experiment": EXPERIMENT,
        "status": "PASS_DEVELOPMENT" if selected is not None else "FAILED_ECONOMIC",
        "protocol_sha256": protocol_sha256(),
        "source_checkpoint_seal_sha256": source_seal_sha,
        "selected": selected,
        "eligible_policies": len(eligible),
        "policy_checkpoint": {"total": 32, "built_this_run": built, "reused_this_run": reused},
        "files": {
            name: {"rows": len(frame), "bytes": (output_dir / name).stat().st_size, "sha256": sha256_file(output_dir / name)}
            for name, frame in combined.items()
        },
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
    authorized = (ROOT / "tmp/king_gex_exit_v1").resolve()
    if authorized != output and authorized not in output.parents:
        raise AssertionError("output must remain under tmp/king_gex_exit_v1")
    run_identity = _ensure_run_checkpoint(output)
    candidates = load_exit_candidates()
    source_manifest = load_source_manifest()
    outcomes, source_counts, source_hashes = prepare_source_outcomes(
        candidates, source_manifest, output, run_identity
    )
    result = evaluate(candidates, outcomes, output, run_identity, source_hashes)
    result["source_checkpoint"] = {"total": 36, **source_counts}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
