"""Build resumable causal +30m states for KING-GEX-MANAGE30-V1.

Only 2022 training and 2023 development are authorized here.  Outer years are
deliberately rejected by the CLI and must use a separately frozen runner.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
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
from neural.jepa.build_tpo_value_migration_view_v1 import EARLY_CLOSE_DATES, MASTER_SHA256
from neural.jepa.evaluate_king_gex_exit_v1 import (
    EXIT_CONFIGS,
    _expected_baseline,
    _raw_quote_path,
    assert_baseline_parity,
    simulate_all_configs,
)
from neural.jepa.evaluate_king_gex_slope_v1 import KEY, MASTER, WALL_STATE, WALL_STATE_SHA256
from neural.jepa.existing_data_edge_scheduler_v1 import SCHEDULER
from services.compute_features import calculate_exact_t, get_net_exposures_from_parquet


EXPERIMENT = "KING_GEX_MANAGE30_V1"
PREDECLARATION = ROOT / "research_papers/JEPA/KING_GEX_MANAGE30_V1_PREDECLARATION.md"
PREDECLARATION_SHA256 = "b534cd8857833285010dccc0ae440f89a4ca8235dd4d2e7c99dd17a731d74948"
DATA_GATE_CLARIFICATION = (
    ROOT / "research_papers/JEPA/KING_GEX_MANAGE30_V1_DATA_GATE_CLARIFICATION.md"
)
DATA_GATE_CLARIFICATION_SHA256 = "931fc27d74b05760abf9c8a8907fe64ba5d0d046bfb8f64cf16a5d4b16229e46"
SNAPSHOT_CLARIFICATION = (
    ROOT
    / "research_papers/JEPA/"
    "KING_GEX_MANAGE30_V1_DATA_GATE_CLARIFICATION_V1R2.md"
)
SNAPSHOT_CLARIFICATION_SHA256 = (
    "35e09f5a2679e2ce807a9439dcf9fa051c3e629fa95003975e02d5f39e39a844"
)
SOURCE_MANIFEST = (
    ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "thetadata_manifest_spxw_spy_qqq_202201_202605_sealed_v1/"
    "thetadata_option_manifest.csv"
)
SOURCE_MANIFEST_SHA256 = "88be8a2ff44c18fb57fca360d31def574ddbb0419a792fc88349942711d2974a"
START_DATE = "20220101"
END_DATE = "20231231"
EXPECTED_SOURCE_CANDIDATES = 22_273
EXPECTED_EXECUTABLE_CANDIDATES = 22_272
FROZEN_ENTRY_REJECTIONS = (
    {
        "ticker": "SPXW",
        "trade_date": "20220222",
        "minute": 680,
        "action": "PUT",
        "reason": "exact_entry_contract_not_executable",
    },
)
FIRST_ENTRY_MINUTE = 680
LAST_ENTRY_MINUTE = 870
DECISION_MINIMUM = 30
DECISION_MAXIMUM = 31
RUN_SCHEMA = "king_gex_manage30_build_run_v1"
SESSION_SCHEMA = "king_gex_manage30_session_checkpoint_v1"
DATASET_SCHEMA = "king_gex_manage30_train_dev_dataset_v1"
ACTION_IDS = tuple([str(item["config_id"]) for item in EXIT_CONFIGS] + ["E30"])

NET_EXPOSURES = (
    "net_gamma",
    "net_vanna",
    "net_charm",
    "net_dgex",
    "net_zomma",
    "net_delta",
    "net_vega",
    "net_vomma",
)
WALL_EXPOSURES = (
    "max_gamma",
    "min_gamma",
    "max_vanna",
    "min_vanna",
    "max_dgex",
    "min_dgex",
    "max_zomma",
    "min_zomma",
    "max_vega",
    "min_vega",
    "max_vomma",
    "min_vomma",
)

M0_FEATURES = (
    "decision_state_available",
    "entry_minute",
    "action_is_call",
    "king_gex_level_log",
    "king_gex_slope_log",
    "entry_ret_15m_bps",
    "entry_spot",
    "entry_strike_dist_bps",
    "entry_bid",
    "entry_ask",
    "entry_spread_pct",
    "entry_delta",
    "entry_abs_delta",
    "entry_iv",
    "entry_theta",
    "entry_vega",
    "entry_open_interest",
    "decision_elapsed",
    "decision_spot",
    "decision_bid",
    "decision_ask",
    "decision_spread_pct",
    "decision_delta",
    "decision_abs_delta",
    "decision_iv",
    "decision_theta",
    "decision_vega",
    "decision_return",
    "path_mfe",
    "path_mae",
    "path_drawdown_from_peak",
    "path_return_5m",
    "path_return_15m",
    "path_return_30m",
    "path_slope_5_15",
    "path_slope_15_30",
    "path_quote_count",
    "path_positive_fraction",
    "spot_return_from_entry_bps",
    "spot_return_1m_bps",
    "spot_return_5m_bps",
    "spot_return_15m_bps",
    "spot_return_30m_bps",
    "spot_path_rv_bps",
    "delta_change",
    "iv_change",
    "theta_change",
    "vega_change",
    "minutes_to_close",
    "dow_sin",
    "dow_cos",
)

M1_EXTRA_FEATURES = tuple(
    [
        name
        for exposure in NET_EXPOSURES
        for name in (
            f"synth_entry_{exposure}_log",
            f"synth_decision_{exposure}_log",
            f"synth_change_{exposure}_log",
        )
    ]
    + [
        name
        for exposure in WALL_EXPOSURES
        for name in (
            f"synth_entry_{exposure}_dist_bps",
            f"synth_decision_{exposure}_dist_bps",
            f"synth_migration_{exposure}_bps",
        )
    ]
)
M1_FEATURES = tuple([*M0_FEATURES, *M1_EXTRA_FEATURES])


def _canonical_sha(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _signed_log(value: float) -> float:
    value = float(value)
    if not np.isfinite(value):
        return math.nan
    return float(np.sign(value) * np.log1p(abs(value)))


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def _day(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace("-", "", regex=False).str[:8]


def _target_columns() -> list[str]:
    return [
        *[
            f"{side}_d{bucket:02d}_{suffix}"
            for side in ("call", "put")
            for bucket in (25, 35)
            for suffix in (
                "strike",
                "opt_exit_ret",
                "opt_exit_minutes",
                "opt_status",
                "opt_max_ret",
                "opt_min_ret",
            )
        ]
    ]


def load_candidates() -> pd.DataFrame:
    """Rebuild K1 outcome-free and bind only frozen executable diagnostics."""

    if sha256_file(PREDECLARATION) != PREDECLARATION_SHA256:
        raise AssertionError("MANAGE30 predeclaration changed")
    if sha256_file(DATA_GATE_CLARIFICATION) != DATA_GATE_CLARIFICATION_SHA256:
        raise AssertionError("MANAGE30 data-gate clarification changed")
    if sha256_file(SNAPSHOT_CLARIFICATION) != SNAPSHOT_CLARIFICATION_SHA256:
        raise AssertionError("MANAGE30 snapshot clarification changed")
    if sha256_file(MASTER) != MASTER_SHA256:
        raise AssertionError("authoritative executable master changed")
    if sha256_file(WALL_STATE) != WALL_STATE_SHA256:
        raise AssertionError("wall-state source changed")
    master = pd.read_parquet(
        MASTER,
        columns=[*KEY, "ret_15m_bps", *_target_columns()],
        filters=[("trade_date", ">=", START_DATE), ("trade_date", "<=", END_DATE)],
    )
    wall = pd.read_parquet(
        WALL_STATE,
        columns=[*KEY, "wall_net_gamma_total_log"],
        filters=[("trade_date", ">=", START_DATE), ("trade_date", "<=", END_DATE)],
    )
    for frame in (master, wall):
        frame["ticker"] = frame["ticker"].astype(str).str.upper()
        frame["trade_date"] = _day(frame["trade_date"])
        frame["minute"] = pd.to_numeric(frame["minute"], errors="raise").astype(int)
        frame.drop(frame.index[frame["trade_date"].isin(EARLY_CLOSE_DATES)], inplace=True)
        if frame.duplicated(KEY).any():
            raise AssertionError("source keys are not unique")
    master = master.loc[master["minute"].between(FIRST_ENTRY_MINUTE, LAST_ENTRY_MINUTE)].copy()
    wall = wall.sort_values(KEY, kind="stable").reset_index(drop=True)
    grouped = wall.groupby(["ticker", "trade_date"], observed=True, sort=False)
    wall["lag_minute"] = grouped["minute"].shift(9)
    wall["gex_log_lag45"] = grouped["wall_net_gamma_total_log"].shift(9)
    current_log = pd.to_numeric(wall["wall_net_gamma_total_log"], errors="coerce")
    lag_log = pd.to_numeric(wall["gex_log_lag45"], errors="coerce")
    wall["net_gex_proxy"] = np.sign(current_log) * np.expm1(np.abs(current_log))
    wall["net_gex_proxy_lag45"] = np.sign(lag_log) * np.expm1(np.abs(lag_log))
    wall["net_gex_slope15"] = (wall["net_gex_proxy"] - wall["net_gex_proxy_lag45"]) / 3.0
    wall = wall.loc[wall["lag_minute"].eq(wall["minute"] - 45)].copy()
    joined = master.merge(
        wall[[*KEY, "wall_net_gamma_total_log", "net_gex_proxy", "net_gex_slope15"]],
        on=KEY,
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if not joined["_merge"].eq("both").all():
        raise AssertionError("an executable key lacks exact wall state")
    joined = joined.drop(columns="_merge")
    momentum = np.sign(pd.to_numeric(joined["ret_15m_bps"], errors="coerce"))
    gex = pd.to_numeric(joined["net_gex_proxy"], errors="coerce")
    slope = pd.to_numeric(joined["net_gex_slope15"], errors="coerce")
    valid = np.isfinite(momentum) & np.isfinite(gex) & np.isfinite(slope)
    valid &= momentum.ne(0.0) & gex.ne(0.0) & slope.ne(0.0)
    valid &= np.sign(slope).eq(np.sign(gex))
    out = joined.loc[valid].copy()
    d0_sign = np.where(gex.loc[valid].lt(0.0), momentum.loc[valid], -momentum.loc[valid])
    d0_action = pd.Series(np.where(d0_sign > 0.0, "CALL", "PUT"), index=out.index)
    out["action"] = d0_action.map({"CALL": "PUT", "PUT": "CALL"})
    out["month"] = out["trade_date"].str[:6]
    out["year"] = out["trade_date"].str[:4]
    out = out.sort_values(KEY, kind="stable").reset_index(drop=True)
    if len(out) != EXPECTED_SOURCE_CANDIDATES:
        raise AssertionError(
            f"K1 train/dev census changed: {len(out)} != {EXPECTED_SOURCE_CANDIDATES}"
        )
    if not out["trade_date"].between(START_DATE, END_DATE).all():
        raise AssertionError("candidate loader opened a forbidden date")
    return out


def load_source_manifest() -> pd.DataFrame:
    if sha256_file(SOURCE_MANIFEST) != SOURCE_MANIFEST_SHA256:
        raise AssertionError("ThetaData source manifest changed")
    frame = pd.read_csv(SOURCE_MANIFEST, dtype={"trade_date": str, "expiration": str})
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["trade_date"] = _day(frame["trade_date"])
    frame = frame.loc[
        frame["ticker"].isin(SCHEDULER)
        & frame["trade_date"].between(START_DATE, END_DATE)
        & frame["expiry_mode"].astype(str).eq("zero_dte")
    ].copy()
    if frame.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("zero-DTE source manifest keys are not unique")
    required = ["greeks_path", "oi_path", "ohlc_path"]
    if frame[required].isna().any().any():
        raise AssertionError("source manifest contains a missing path")
    return frame.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)


def _code_hashes() -> dict[str, str]:
    paths = (
        "neural/jepa/build_king_gex_manage30_v1.py",
        "neural/jepa/evaluate_king_gex_exit_v1.py",
        "neural/jepa/evaluate_king_gex_slope_v1.py",
        "neural/jepa/build_event_option_dataset.py",
        "services/compute_features.py",
        "training_data/stats.py",
    )
    return {path: sha256_file(ROOT / path) for path in paths}


def run_identity() -> dict[str, Any]:
    return {
        "schema": RUN_SCHEMA,
        "experiment": EXPERIMENT,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "expected_source_candidates": EXPECTED_SOURCE_CANDIDATES,
        "expected_executable_candidates": EXPECTED_EXECUTABLE_CANDIDATES,
        "frozen_entry_rejections": list(FROZEN_ENTRY_REJECTIONS),
        "predeclaration_sha256": PREDECLARATION_SHA256,
        "data_gate_clarification_sha256": DATA_GATE_CLARIFICATION_SHA256,
        "snapshot_clarification_sha256": SNAPSHOT_CLARIFICATION_SHA256,
        "master_sha256": MASTER_SHA256,
        "wall_state_sha256": WALL_STATE_SHA256,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "actions": list(ACTION_IDS),
        "M0_features": list(M0_FEATURES),
        "M1_features": list(M1_FEATURES),
        "code_hashes": _code_hashes(),
        "outer_2024_2025_opened": False,
        "holdout_2026_opened": False,
    }


def _ensure_run_checkpoint(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "RUN_CHECKPOINT.json"
    expected = run_identity()
    if path.exists():
        stored = json.loads(path.read_text(encoding="utf-8"))
        if stored != expected:
            raise AssertionError("run identity changed; use a new immutable target")
        return stored
    unexpected = [item.name for item in output_dir.iterdir() if not item.name.startswith(".")]
    if unexpected:
        raise AssertionError("target exists without a run checkpoint")
    _atomic_json(path, expected)
    return expected


def _valid_contract_quotes(quotes: pd.DataFrame, ts: pd.Timestamp) -> pd.DataFrame:
    quote_time = pd.to_datetime(quotes["quote_dt"], errors="coerce")
    bid = pd.to_numeric(quotes["bid"], errors="coerce")
    ask = pd.to_numeric(quotes["ask"], errors="coerce")
    path = quotes.loc[
        (quote_time > ts)
        & (quote_time <= ts + pd.Timedelta(minutes=180))
        & np.isfinite(bid)
        & np.isfinite(ask)
        & bid.ge(0.0)
        & ask.ge(bid)
    ].copy()
    path["quote_time"] = pd.to_datetime(path["quote_dt"], errors="raise")
    return path.sort_values("quote_time", kind="stable").drop_duplicates(
        "quote_time", keep="last"
    )


def _exact_snapshot_groups(greeks: pd.DataFrame) -> dict[pd.Timestamp, pd.DataFrame]:
    if "quote_dt" not in greeks.columns:
        raise KeyError("exact snapshots require native quote_dt")
    quote_time = pd.to_datetime(greeks["quote_dt"], errors="coerce")
    if quote_time.isna().any():
        raise AssertionError("exact snapshot source contains invalid quote_dt")
    work = greeks.copy()
    work["quote_dt"] = quote_time
    return {
        pd.Timestamp(stamp): part
        for stamp, part in work.groupby("quote_dt", sort=False, observed=True)
    }


def _frozen_rejection_key(
    ticker: str, trade_date: str, minute: int, action: str
) -> bool:
    key = (str(ticker), str(trade_date), int(minute), str(action).upper())
    allowed = {
        (
            str(item["ticker"]),
            str(item["trade_date"]),
            int(item["minute"]),
            str(item["action"]).upper(),
        )
        for item in FROZEN_ENTRY_REJECTIONS
    }
    return key in allowed


def _assert_frozen_rejection_master(event: Any, action: str, bucket: int) -> None:
    prefix = f"{str(action).lower()}_d{int(bucket):02d}"
    if np.isfinite(float(getattr(event, f"{prefix}_strike"))):
        raise AssertionError("frozen entry rejection gained a master strike")
    expected = _expected_baseline(event, action, bucket)
    if int(expected["exit_minutes"]) != 0 or int(expected["status"]) != 0:
        raise AssertionError("frozen entry rejection gained a master outcome state")
    if any(
        np.isfinite(float(expected[name]))
        for name in ("realized_return", "max_ret", "min_ret")
    ):
        raise AssertionError("frozen entry rejection gained a master payoff")


def _spread_pct(bid: float, ask: float) -> float:
    mid = (float(bid) + float(ask)) / 2.0
    return float((float(ask) - float(bid)) / mid) if mid > 0.0 else math.nan


def _mark_at_elapsed(path: pd.DataFrame, entry_ask: float, ts: pd.Timestamp, elapsed: int) -> float:
    minutes = ((path["quote_time"] - ts).dt.total_seconds() // 60).astype(int)
    part = path.loc[minutes.eq(int(elapsed))]
    if part.empty:
        return math.nan
    return float(part.iloc[-1]["bid"]) / float(entry_ask) - 1.0


def _spot_return(
    path: pd.DataFrame,
    current_spot: float,
    current_time: pd.Timestamp,
    lag: int,
) -> float:
    target = pd.Timestamp(current_time) - pd.Timedelta(minutes=int(lag))
    part = path.loc[path["quote_time"].eq(target)]
    if part.empty:
        return math.nan
    prior = float(part.iloc[-1]["underlying_price"])
    return float((float(current_spot) / prior - 1.0) * 10_000.0) if prior > 0.0 else math.nan


def _synthetic_snapshot(snapshot: pd.DataFrame, stamp: pd.Timestamp, prefix: str) -> dict[str, float]:
    output = {name: math.nan for name in M1_EXTRA_FEATURES if name.startswith(prefix)}
    if snapshot.empty:
        return output
    work = snapshot.copy()
    work["T"] = float(calculate_exact_t(stamp))
    try:
        exposure = get_net_exposures_from_parquet(work)
    except (FloatingPointError, ValueError, ZeroDivisionError):
        return output
    if not exposure:
        return output
    spot = float(exposure.get("spot_price", math.nan))
    for name in NET_EXPOSURES:
        output[f"{prefix}_{name}_log"] = _signed_log(float(exposure.get(name, math.nan)))
    for name in WALL_EXPOSURES:
        strike = float(exposure.get(f"{name}_strike", math.nan))
        output[f"{prefix}_{name}_dist_bps"] = (
            float((strike / spot - 1.0) * 10_000.0)
            if np.isfinite(strike) and np.isfinite(spot) and spot > 0.0
            else math.nan
        )
    return output


def _entry_features(event: Any, contract: pd.Series, action: str) -> dict[str, float | int]:
    bid = float(contract.get("bid", math.nan))
    ask = float(contract.get("ask", math.nan))
    spot = float(contract.get("underlying_price", math.nan))
    strike = float(contract.get("strike", math.nan))
    return {
        "entry_minute": int(event.minute),
        "action_is_call": int(action == "CALL"),
        "king_gex_level_log": float(event.wall_net_gamma_total_log),
        "king_gex_slope_log": _signed_log(float(event.net_gex_slope15)),
        "entry_ret_15m_bps": float(event.ret_15m_bps),
        "entry_spot": spot,
        "entry_strike_dist_bps": float((strike / spot - 1.0) * 10_000.0),
        "entry_bid": bid,
        "entry_ask": ask,
        "entry_spread_pct": _spread_pct(bid, ask),
        "entry_delta": float(contract.get("delta", math.nan)),
        "entry_abs_delta": abs(float(contract.get("delta", math.nan))),
        "entry_iv": float(contract.get("implied_vol", math.nan)),
        "entry_theta": float(contract.get("theta", math.nan)),
        "entry_vega": float(contract.get("vega", math.nan)),
        "entry_open_interest": float(contract.get("open_interest", math.nan)),
    }


def _missing_decision_features(stamp: pd.Timestamp) -> dict[str, float | int]:
    fields = {name: math.nan for name in M0_FEATURES if name not in {
        "decision_state_available", "entry_minute", "action_is_call",
        "king_gex_level_log", "king_gex_slope_log", "entry_ret_15m_bps",
        "entry_spot", "entry_strike_dist_bps", "entry_bid", "entry_ask",
        "entry_spread_pct", "entry_delta", "entry_abs_delta", "entry_iv",
        "entry_theta", "entry_vega", "entry_open_interest",
    }}
    fields["decision_state_available"] = 0
    fields["minutes_to_close"] = float(960 - (stamp.hour * 60 + stamp.minute + 30))
    fields["dow_sin"] = float(np.sin(2.0 * np.pi * stamp.dayofweek / 5.0))
    fields["dow_cos"] = float(np.cos(2.0 * np.pi * stamp.dayofweek / 5.0))
    return fields


def _decision_features(
    path: pd.DataFrame,
    entry_ask: float,
    entry: dict[str, float | int],
    ts: pd.Timestamp,
) -> tuple[dict[str, float | int], pd.Series | None]:
    elapsed = ((path["quote_time"] - ts).dt.total_seconds() // 60).astype(int)
    decision = path.loc[elapsed.between(DECISION_MINIMUM, DECISION_MAXIMUM)]
    if decision.empty:
        return _missing_decision_features(ts), None
    row = decision.iloc[0]
    current_time = pd.Timestamp(row["quote_time"])
    decision_elapsed = int((current_time - ts).total_seconds() // 60)
    observed = path.loc[path["quote_time"].le(current_time)].copy()
    returns = pd.to_numeric(observed["bid"], errors="raise").astype(float) / float(entry_ask) - 1.0
    current_return = float(row["bid"]) / float(entry_ask) - 1.0
    peak = float(returns.max())
    trough = float(returns.min())
    current_spot = float(row["underlying_price"])
    spots = pd.to_numeric(observed["underlying_price"], errors="coerce").dropna().astype(float)
    log_returns = np.diff(np.log(spots.to_numpy())) if len(spots) >= 2 and (spots > 0.0).all() else np.array([])
    mark5 = _mark_at_elapsed(observed, entry_ask, ts, 5)
    mark15 = _mark_at_elapsed(observed, entry_ask, ts, 15)
    mark30 = _mark_at_elapsed(observed, entry_ask, ts, 30)
    output: dict[str, float | int] = {
        "decision_state_available": 1,
        "decision_elapsed": decision_elapsed,
        "decision_spot": current_spot,
        "decision_bid": float(row["bid"]),
        "decision_ask": float(row["ask"]),
        "decision_spread_pct": _spread_pct(float(row["bid"]), float(row["ask"])),
        "decision_delta": float(row.get("delta", math.nan)),
        "decision_abs_delta": abs(float(row.get("delta", math.nan))),
        "decision_iv": float(row.get("implied_vol", math.nan)),
        "decision_theta": float(row.get("theta", math.nan)),
        "decision_vega": float(row.get("vega", math.nan)),
        "decision_return": current_return,
        "path_mfe": peak,
        "path_mae": trough,
        "path_drawdown_from_peak": peak - current_return,
        "path_return_5m": mark5,
        "path_return_15m": mark15,
        "path_return_30m": mark30,
        "path_slope_5_15": mark15 - mark5 if np.isfinite(mark5) and np.isfinite(mark15) else math.nan,
        "path_slope_15_30": mark30 - mark15 if np.isfinite(mark15) and np.isfinite(mark30) else math.nan,
        "path_quote_count": int(len(observed)),
        "path_positive_fraction": float((returns > 0.0).mean()),
        "spot_return_from_entry_bps": float((current_spot / float(entry["entry_spot"]) - 1.0) * 10_000.0),
        "spot_return_1m_bps": _spot_return(observed, current_spot, current_time, 1),
        "spot_return_5m_bps": _spot_return(observed, current_spot, current_time, 5),
        "spot_return_15m_bps": _spot_return(observed, current_spot, current_time, 15),
        "spot_return_30m_bps": float((current_spot / float(entry["entry_spot"]) - 1.0) * 10_000.0),
        "spot_path_rv_bps": float(np.std(log_returns, ddof=0) * 10_000.0) if len(log_returns) else 0.0,
        "delta_change": float(row.get("delta", math.nan)) - float(entry["entry_delta"]),
        "iv_change": float(row.get("implied_vol", math.nan)) - float(entry["entry_iv"]),
        "theta_change": float(row.get("theta", math.nan)) - float(entry["entry_theta"]),
        "vega_change": float(row.get("vega", math.nan)) - float(entry["entry_vega"]),
        "minutes_to_close": float(960 - (pd.Timestamp(row["quote_time"]).hour * 60 + pd.Timestamp(row["quote_time"]).minute)),
        "dow_sin": float(np.sin(2.0 * np.pi * ts.dayofweek / 5.0)),
        "dow_cos": float(np.cos(2.0 * np.pi * ts.dayofweek / 5.0)),
    }
    return output, row


def _surface_features(
    entry_snapshot: pd.DataFrame,
    decision_snapshot: pd.DataFrame,
    entry_ts: pd.Timestamp,
    decision_ts: pd.Timestamp | None,
) -> dict[str, float]:
    entry = _synthetic_snapshot(entry_snapshot, entry_ts, "synth_entry")
    decision = (
        _synthetic_snapshot(decision_snapshot, decision_ts, "synth_decision")
        if decision_ts is not None
        else {name: math.nan for name in M1_EXTRA_FEATURES if name.startswith("synth_decision")}
    )
    out = {**entry, **decision}
    for name in NET_EXPOSURES:
        a = out.get(f"synth_entry_{name}_log", math.nan)
        b = out.get(f"synth_decision_{name}_log", math.nan)
        out[f"synth_change_{name}_log"] = float(b - a) if np.isfinite(a) and np.isfinite(b) else math.nan
    for name in WALL_EXPOSURES:
        a = out.get(f"synth_entry_{name}_dist_bps", math.nan)
        b = out.get(f"synth_decision_{name}_dist_bps", math.nan)
        out[f"synth_migration_{name}_bps"] = float(b - a) if np.isfinite(a) and np.isfinite(b) else math.nan
    return out


def build_session(events: pd.DataFrame, source: pd.Series) -> pd.DataFrame:
    ticker = str(events["ticker"].iloc[0])
    trade_date = str(events["trade_date"].iloc[0])
    bucket = int(SCHEDULER[ticker]["bucket"])
    greeks, _ = load_chain(source, require_open_interest=True, option_price_mode="executable_quote")
    if greeks.empty:
        raise AssertionError(f"empty executable chain: {ticker} {trade_date}")
    snapshots = _exact_snapshot_groups(greeks)
    quote_groups = {
        (str(right), float(strike)): part
        for (right, strike), part in greeks.groupby(["right", "strike"], sort=False, observed=True)
    }
    rows: list[dict[str, Any]] = []
    for event in events.itertuples(index=False):
        ts = pd.Timestamp(str(event.trade_date)) + pd.Timedelta(minutes=int(event.minute))
        snapshot = snapshots.get(ts)
        if snapshot is None or snapshot.empty:
            raise AssertionError(f"missing exact entry snapshot: {ticker} {trade_date} {event.minute}")
        action = str(event.action).upper()
        contract = select_contract(snapshot, action, bucket / 100.0, "executable_quote")
        frozen_rejection = _frozen_rejection_key(
            ticker, trade_date, int(event.minute), action
        )
        if frozen_rejection:
            if contract is not None:
                raise AssertionError("frozen entry rejection gained an executable contract")
            _assert_frozen_rejection_master(event, action, bucket)
            continue
        if contract is None:
            raise AssertionError("frozen K1 event lost its executable contract")
        prefix = f"{action.lower()}_d{bucket:02d}"
        expected_strike = float(getattr(event, f"{prefix}_strike"))
        if not np.isclose(float(contract["strike"]), expected_strike, rtol=0.0, atol=1e-6):
            raise AssertionError("selected contract strike differs from frozen master")
        quotes = quote_groups.get((action, float(contract["strike"])))
        if quotes is None:
            raise AssertionError("selected contract has no quote path")
        entry_ask, raw_path = _raw_quote_path(quotes, contract, ts)
        outcomes = simulate_all_configs(raw_path, entry_ask, ts)
        assert_baseline_parity(outcomes["B00"], _expected_baseline(event, action, bucket))
        contract_path = _valid_contract_quotes(quotes, ts)
        entry_features = _entry_features(event, contract, action)
        decision_features, decision_row = _decision_features(contract_path, entry_ask, entry_features, ts)
        decision_ts = pd.Timestamp(decision_row["quote_time"]) if decision_row is not None else None
        decision_snapshot = (
            snapshots.get(decision_ts, pd.DataFrame())
            if decision_ts is not None
            else pd.DataFrame()
        )
        surface = _surface_features(snapshot, decision_snapshot, ts, decision_ts)
        row: dict[str, Any] = {
            "ticker": ticker,
            "trade_date": trade_date,
            "month": trade_date[:6],
            "year": trade_date[:4],
            "minute": int(event.minute),
            "action": action,
            "strike": float(contract["strike"]),
            **entry_features,
            **decision_features,
            **surface,
        }
        for config in EXIT_CONFIGS:
            config_id = str(config["config_id"])
            outcome = outcomes[config_id]
            for field in ("realized_return", "exit_minutes", "status", "exit_reason"):
                row[f"outcome_{config_id}_{field}"] = outcome[field]
        if decision_row is None:
            row["outcome_E30_realized_return"] = math.nan
            row["outcome_E30_exit_minutes"] = math.nan
            row["outcome_E30_status"] = math.nan
            row["outcome_E30_exit_reason"] = "unavailable"
        else:
            e30_return = float(decision_row["bid"]) / float(entry_ask) - 1.0
            e30_elapsed = int((pd.Timestamp(decision_row["quote_time"]) - ts).total_seconds() // 60)
            row["outcome_E30_realized_return"] = e30_return
            row["outcome_E30_exit_minutes"] = e30_elapsed
            row["outcome_E30_status"] = 1 if e30_return > 0.0 else (-1 if e30_return < 0.0 else 0)
            row["outcome_E30_exit_reason"] = "decision_exit"
        rows.append(row)
    output = pd.DataFrame(rows).sort_values(KEY, kind="stable").reset_index(drop=True)
    expected_rejections = sum(
        _frozen_rejection_key(
            ticker, trade_date, int(event.minute), str(event.action)
        )
        for event in events.itertuples(index=False)
    )
    if len(output) != len(events) - expected_rejections or output.duplicated(KEY).any():
        raise AssertionError("session output census/key contract failed")
    if output["trade_date"].str[:4].astype(int).gt(2023).any():
        raise AssertionError("builder opened an outer year")
    return output


def _session_identity(
    base: dict[str, Any], events: pd.DataFrame, source: pd.Series
) -> dict[str, Any]:
    hashes = {
        name: sha256_file(Path(str(source[name])))
        for name in ("greeks_path", "oi_path", "ohlc_path")
    }
    return {
        **base,
        "schema": SESSION_SCHEMA,
        "ticker": str(events["ticker"].iloc[0]),
        "trade_date": str(events["trade_date"].iloc[0]),
        "candidate_keys_sha256": _canonical_sha(events[KEY].to_dict("records")),
        "raw_source_hashes": hashes,
    }


def _read_checkpoint(directory: Path, identity: dict[str, Any]) -> pd.DataFrame | None:
    manifest_path = directory / "manifest.json"
    output_path = directory / "states.parquet"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if {key: manifest.get(key) for key in identity} != identity:
        raise AssertionError("session checkpoint identity changed; use a new target")
    spec = manifest.get("file", {})
    if (
        manifest.get("status") != "COMPLETE"
        or manifest.get("atomic_manifest_last") is not True
        or not output_path.is_file()
        or spec.get("sha256") != sha256_file(output_path)
        or int(spec.get("bytes", -1)) != output_path.stat().st_size
    ):
        return None
    frame = pd.read_parquet(output_path)
    if len(frame) != int(spec.get("rows", -1)):
        return None
    return frame


def _write_checkpoint(directory: Path, identity: dict[str, Any], frame: pd.DataFrame) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    manifest_path.unlink(missing_ok=True)
    output_path = directory / "states.parquet"
    _atomic_parquet(output_path, frame)
    _atomic_json(
        manifest_path,
        {
            **identity,
            "status": "COMPLETE",
            "atomic_manifest_last": True,
            "file": {
                "rows": len(frame),
                "bytes": output_path.stat().st_size,
                "sha256": sha256_file(output_path),
            },
        },
    )


def _build_task(payload: tuple[pd.DataFrame, dict[str, Any], str, dict[str, Any]]) -> dict[str, Any]:
    events, source_payload, directory_text, base = payload
    source = pd.Series(source_payload)
    directory = Path(directory_text)
    identity = _session_identity(base, events, source)
    cached = _read_checkpoint(directory, identity)
    if cached is not None:
        return {"status": "reused", "rows": len(cached), "path": str(directory / "states.parquet")}
    frame = build_session(events, source)
    _write_checkpoint(directory, identity, frame)
    return {"status": "built", "rows": len(frame), "path": str(directory / "states.parquet")}


def _dataset_summary(frame: pd.DataFrame) -> dict[str, Any]:
    decision = frame["decision_state_available"].astype(int).eq(1)
    coverage = (
        frame.assign(decision_available=decision)
        .groupby(["ticker", "year"], observed=True)["decision_available"]
        .agg(["count", "sum", "mean"])
        .reset_index()
    )
    synth_complete = frame[list(M1_EXTRA_FEATURES)].notna().all(axis=1) & decision
    synth_coverage = (
        frame.assign(synth_complete=synth_complete)
        .groupby(["ticker", "year"], observed=True)["synth_complete"]
        .agg(["count", "sum", "mean"])
        .reset_index()
    )
    return {
        "schema": DATASET_SCHEMA,
        "status": "PASS_DATA_GATE",
        "rows": len(frame),
        "source_candidate_rows": EXPECTED_SOURCE_CANDIDATES,
        "entry_rejected_rows": len(FROZEN_ENTRY_REJECTIONS),
        "entry_rejections": list(FROZEN_ENTRY_REJECTIONS),
        "columns": len(frame.columns),
        "date_min": str(frame["trade_date"].min()),
        "date_max": str(frame["trade_date"].max()),
        "rows_by_ticker_year": frame.groupby(["ticker", "year"], observed=True).size().rename("rows").reset_index().to_dict("records"),
        "decision_coverage": coverage.to_dict("records"),
        "synth_complete_coverage": synth_coverage.to_dict("records"),
        "M0_features": list(M0_FEATURES),
        "M1_features": list(M1_FEATURES),
        "actions": list(ACTION_IDS),
        "outer_2024_2025_opened": False,
        "holdout_2026_opened": False,
    }


def build(output_dir: Path, workers: int) -> dict[str, Any]:
    base = _ensure_run_checkpoint(output_dir)
    candidates = load_candidates()
    manifest = load_source_manifest()
    source_lookup = {
        (str(row.ticker), str(row.trade_date)): row._asdict()
        for row in manifest.itertuples(index=False)
    }
    tasks: list[tuple[pd.DataFrame, dict[str, Any], str, dict[str, Any]]] = []
    for (ticker, trade_date), events in candidates.groupby(["ticker", "trade_date"], observed=True, sort=True):
        source = source_lookup.get((str(ticker), str(trade_date)))
        if source is None:
            raise AssertionError(f"missing source manifest row: {ticker} {trade_date}")
        directory = output_dir / "session_checkpoints" / str(trade_date)[:4] / str(trade_date)[4:6] / str(ticker) / str(trade_date)
        tasks.append((events.reset_index(drop=True), source, str(directory), base))
    results: list[dict[str, Any]] = []
    total = len(tasks)
    if int(workers) <= 1:
        for index, task in enumerate(tasks, start=1):
            result = _build_task(task)
            results.append(result)
            print(f"[session {index}/{total}] {result['status']} rows={result['rows']}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=min(int(workers), total)) as executor:
            futures = {executor.submit(_build_task, task): index for index, task in enumerate(tasks, start=1)}
            done = 0
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                done += 1
                print(f"[session {done}/{total}] {result['status']} rows={result['rows']}", flush=True)
    paths = sorted(Path(result["path"]) for result in results)
    parts = [pd.read_parquet(path) for path in paths]
    dataset = pd.concat(parts, ignore_index=True).sort_values(KEY, kind="stable").reset_index(drop=True)
    if (
        len(candidates) != EXPECTED_SOURCE_CANDIDATES
        or len(dataset) != EXPECTED_EXECUTABLE_CANDIDATES
        or dataset.duplicated(KEY).any()
    ):
        raise AssertionError("combined dataset census/key contract failed")
    if dataset["trade_date"].str[:4].astype(int).gt(2023).any():
        raise AssertionError("combined dataset opened outer years")
    outcome_return_cols = [f"outcome_{action}_realized_return" for action in ACTION_IDS[:-1]]
    if not np.isfinite(dataset[outcome_return_cols].to_numpy(dtype=float)).all():
        raise AssertionError("a frozen action outcome is missing/non-finite")
    if not dataset["outcome_B00_exit_minutes"].between(30, 180).all():
        raise AssertionError("B00 hold violates execution contract")
    dataset_path = output_dir / "king_gex_manage30_train_dev.parquet"
    _atomic_parquet(dataset_path, dataset)
    summary = _dataset_summary(dataset)
    summary.update(
        {
            "dataset": {
                "path": str(dataset_path),
                "bytes": dataset_path.stat().st_size,
                "sha256": sha256_file(dataset_path),
            },
            "sessions": total,
            "built_this_run": sum(result["status"] == "built" for result in results),
            "reused_this_run": sum(result["status"] == "reused" for result in results),
        }
    )
    _atomic_json(output_dir / "SUMMARY.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    summary = build(Path(args.output_dir), max(1, int(args.workers)))
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
