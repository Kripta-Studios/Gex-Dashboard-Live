from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NEURAL_ROOT = PROJECT_ROOT / "neural"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(NEURAL_ROOT) not in sys.path:
    sys.path.insert(0, str(NEURAL_ROOT))

from neural.jepa.evaluate_180m_direction import fmt_float, fmt_money, fmt_pct
from neural.jepa.train_backtest_option_policy import (
    EXIT_DYNAMIC_FEATURES,
    LEAKAGE_COLUMNS,
    OPTION_FEATURES,
    _load_daily_greeks,
    candidate_trades_from_selection,
    fixed_delta_policy,
    load_path_frame,
    normalize_date,
    option_path_for_candidate,
    oracle_policy,
    score_metrics,
    time_to_minutes,
    trade_metrics,
)


LOG_PATH: Path | None = None

OPTION_VALUE_TARGETS = [
    "hold180_return_on_risk",
    "rule_return_on_risk",
    "oracle_return_on_risk",
]

DYNAMIC_TARGET_COLUMNS = {
    "future_best": "future_best_return_on_risk",
    "future_edge": "future_edge_return_on_risk",
    "terminal": "terminal_return_on_risk",
}

STATIC_DROP_COLUMNS = {
    "candidate_id",
    "signal_id",
    "date",
    "month",
    "time",
    "ticker",
    "side",
    "rule_exit_reason",
    "rule_exit_time",
    "rule_hold_minutes",
    "rule_pnl_pct",
    "rule_pnl_dollars",
    "rule_return_on_risk",
    "hold180_exit_time",
    "hold180_hold_minutes",
    "hold180_pnl_pct",
    "hold180_pnl_dollars",
    "hold180_return_on_risk",
    "oracle_exit_reason",
    "oracle_exit_time",
    "oracle_hold_minutes",
    "oracle_pnl_pct",
    "oracle_pnl_dollars",
    "oracle_return_on_risk",
}


def log(message: str) -> None:
    print(message, flush=True)
    if LOG_PATH is not None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(message + os.linesep)


def clean_date_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["date"] = out["date"].astype(str).map(normalize_date)
    out["month"] = out["date"].astype(str).str[:6]
    return out


def ensure_dynamic_targets(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if "future_edge_return_on_risk" not in out.columns:
        out["future_edge_return_on_risk"] = (
            out["future_best_return_on_risk"].astype(float)
            - out["current_return_on_risk"].astype(float)
        )
    return out


@dataclass
class FeatureScaler:
    features: list[str]
    median: dict[str, float]
    scale: dict[str, float]

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        if not self.features:
            return np.zeros((len(frame), 0), dtype=np.float32)
        x = frame.reindex(columns=self.features).apply(pd.to_numeric, errors="coerce")
        x = x.replace([np.inf, -np.inf], np.nan)
        med = pd.Series(self.median)
        sc = pd.Series(self.scale)
        x = x.fillna(med).fillna(0.0)
        x = (x - med) / sc
        return x.fillna(0.0).to_numpy(dtype=np.float32)


def fit_scaler(frame: pd.DataFrame, features: list[str]) -> FeatureScaler:
    if not features:
        return FeatureScaler([], {}, {})
    x = frame.reindex(columns=features).apply(pd.to_numeric, errors="coerce")
    x = x.replace([np.inf, -np.inf], np.nan)
    median = x.median(axis=0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    q75 = x.quantile(0.75, axis=0)
    q25 = x.quantile(0.25, axis=0)
    scale = ((q75 - q25) / 1.349).replace([np.inf, -np.inf], np.nan)
    fallback = x.std(axis=0).replace([np.inf, -np.inf], np.nan)
    scale = scale.where(scale.abs() > 1e-9, fallback).fillna(1.0)
    scale = scale.where(scale.abs() > 1e-9, 1.0)
    return FeatureScaler(
        features=list(features),
        median={k: float(v) for k, v in median.items()},
        scale={k: float(v) for k, v in scale.items()},
    )


@dataclass
class OptionValueConfig:
    market_dim: int
    option_dim: int
    dynamic_dim: int
    hidden_dim: int = 128
    market_z_dim: int = 32
    option_z_dim: int = 16
    dynamic_z_dim: int = 16
    dropout: float = 0.10

    def to_dict(self) -> dict:
        return asdict(self)


class MLPBlock(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, hidden_dim: int, dropout: float) -> None:
        super().__init__()
        if in_dim <= 0:
            self.net = None
            self.out_dim = 0
        else:
            self.net = nn.Sequential(
                nn.LayerNorm(in_dim),
                nn.Linear(in_dim, hidden_dim),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, out_dim),
                nn.GELU(),
            )
            self.out_dim = out_dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.net is None:
            return x.new_zeros((len(x), 0))
        return self.net(x)


class OptionValueJEPA(nn.Module):
    """Joint market/option value model.

    The entry path predicts option value targets for a candidate delta.
    The dynamic path predicts continuation value from the current option state.
    """

    def __init__(self, config: OptionValueConfig) -> None:
        super().__init__()
        self.config = config
        self.market_encoder = MLPBlock(config.market_dim, config.market_z_dim, config.hidden_dim, config.dropout)
        self.option_encoder = MLPBlock(config.option_dim, config.option_z_dim, config.hidden_dim, config.dropout)
        self.dynamic_encoder = MLPBlock(config.dynamic_dim, config.dynamic_z_dim, config.hidden_dim, config.dropout)
        entry_in = config.market_z_dim + config.option_z_dim + 1
        self.transition = nn.Sequential(
            nn.LayerNorm(entry_in),
            nn.Linear(entry_in, config.hidden_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim, config.market_z_dim),
            nn.GELU(),
        )
        self.entry_value_head = nn.Sequential(
            nn.LayerNorm(config.market_z_dim + config.option_z_dim + config.market_z_dim),
            nn.Linear(config.market_z_dim + config.option_z_dim + config.market_z_dim, config.hidden_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim, 3),
        )
        dyn_in = config.market_z_dim + config.option_z_dim + config.dynamic_z_dim + 1
        self.continuation_head = nn.Sequential(
            nn.LayerNorm(dyn_in),
            nn.Linear(dyn_in, config.hidden_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim, 1),
        )

    def encode_entry(self, market_x: torch.Tensor, option_x: torch.Tensor, horizon_norm: torch.Tensor):
        z_market = self.market_encoder(market_x)
        z_option = self.option_encoder(option_x)
        z_future = self.transition(torch.cat([z_market, z_option, horizon_norm], dim=1))
        return z_market, z_option, z_future

    def forward_entry(self, market_x: torch.Tensor, option_x: torch.Tensor, horizon_norm: torch.Tensor) -> torch.Tensor:
        z_market, z_option, z_future = self.encode_entry(market_x, option_x, horizon_norm)
        return self.entry_value_head(torch.cat([z_market, z_option, z_future], dim=1))

    def forward_dynamic(
        self,
        market_x: torch.Tensor,
        option_x: torch.Tensor,
        dynamic_x: torch.Tensor,
        horizon_norm: torch.Tensor,
    ) -> torch.Tensor:
        z_market = self.market_encoder(market_x)
        z_option = self.option_encoder(option_x)
        z_dynamic = self.dynamic_encoder(dynamic_x)
        return self.continuation_head(torch.cat([z_market, z_option, z_dynamic, horizon_norm], dim=1)).squeeze(1)


def infer_feature_sets(candidates: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    numeric_cols = [
        c
        for c in candidates.columns
        if c not in STATIC_DROP_COLUMNS
        and c not in LEAKAGE_COLUMNS
        and pd.api.types.is_numeric_dtype(candidates[c])
    ]
    option_names = set(OPTION_FEATURES) | {
        "actual_strike",
        "entry_cost_dollars",
        "contracts",
        "spot_price",
        "path_points",
    }
    option_features = [c for c in numeric_cols if c in option_names]
    market_features = [c for c in numeric_cols if c not in set(option_features)]
    dynamic_features = [c for c in EXIT_DYNAMIC_FEATURES if c != "current_return_on_risk"]
    return market_features, option_features, dynamic_features


def flush_state_chunk(rows: list[dict], chunk_dir: Path, chunk_index: int) -> int:
    if not rows:
        return chunk_index
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = chunk_dir / f"state_chunk_{chunk_index:05d}.parquet"
    pd.DataFrame(rows).to_parquet(chunk_path, index=False)
    log(f"[OPTION_VALUE] wrote {chunk_path.name} rows={len(rows):,}")
    rows.clear()
    return chunk_index + 1


def build_option_state_rows(
    candidates: pd.DataFrame,
    args,
    chunk_dir: Path,
    processed_candidate_ids: set[int] | None = None,
) -> pd.DataFrame:
    log("[OPTION_VALUE] rebuilding compact 5m option state rows from ThetaData")
    path_frame = load_path_frame(args.data, min_date=args.train_start_date)
    path_groups = {
        key: group.sort_values("minutes").reset_index(drop=True)
        for key, group in path_frame.groupby(["ticker", "date"], sort=False)
    }
    rows: list[dict] = []
    processed_candidate_ids = processed_candidate_ids or set()
    chunk_index = len(list(chunk_dir.glob("state_chunk_*.parquet"))) if chunk_dir.exists() else 0
    start = time.time()
    greeks_cache: dict[tuple[str, str], tuple] = {}

    grouped = list(candidates.groupby(["ticker", "date"], sort=False))
    for group_idx, ((ticker, date), group) in enumerate(grouped, start=1):
        cache_key = (str(ticker), normalize_date(date))
        if cache_key not in greeks_cache:
            greeks_cache[cache_key] = _load_daily_greeks(cache_key[1], cache_key[0])
            if len(greeks_cache) > int(args.greeks_cache_size):
                oldest = next(iter(greeks_cache))
                del greeks_cache[oldest]
        df_greeks, premium_lookup, greeks_lookup = greeks_cache[cache_key]
        if df_greeks is None or premium_lookup is None or greeks_lookup is None:
            continue
        day_rows = path_groups.get(cache_key)
        if day_rows is None or day_rows.empty:
            continue

        for cand in group.itertuples(index=False):
            cand_s = pd.Series(cand._asdict())
            if int(cand_s["candidate_id"]) in processed_candidate_ids:
                continue
            entry_time = str(cand_s["time"])
            entry_minute = time_to_minutes(entry_time)
            future_rows = day_rows[
                (day_rows["minutes"].astype(int) > entry_minute)
                & (day_rows["minutes"].astype(int) <= entry_minute + int(args.max_hold_minutes))
            ].copy()
            if future_rows.empty:
                continue
            side = str(cand_s["side"])
            option_right = "CALL" if side == "LONG" else "PUT"
            path = option_path_for_candidate(
                future_rows=future_rows,
                premium_lookup=premium_lookup,
                greeks_lookup=greeks_lookup,
                entry_spot=float(cand_s.get("spot_price", 0.0) or 0.0),
                entry_minute=entry_minute,
                entry_premium=float(cand_s["entry_premium"]),
                contracts=int(cand_s["contracts"]),
                actual_strike=float(cand_s["actual_strike"]),
                option_right=option_right,
                side=side,
                max_hold_minutes=int(args.max_hold_minutes),
            )
            if not path:
                continue
            pnl = np.asarray([float(p["pnl_dollars"]) for p in path], dtype=np.float64)
            future_best = np.maximum.accumulate(pnl[::-1])[::-1]
            terminal = float(pnl[-1])
            for idx, point in enumerate(path):
                current_pnl_pct = float(point["current_pnl_pct"])
                peak = float(point.get("peak_pnl_pct", current_pnl_pct))
                record = {
                    "candidate_id": int(cand_s["candidate_id"]),
                    "signal_id": int(cand_s["signal_id"]),
                    "ticker": str(cand_s["ticker"]),
                    "date": normalize_date(cand_s["date"]),
                    "month": str(cand_s["month"]),
                    "side": side,
                    "path_idx": int(idx),
                    "path_time": str(point["time"]),
                    "hold_minutes": int(point["hold_minutes"]),
                    "hold_norm": float(point["hold_minutes"]) / float(max(args.max_hold_minutes, 1)),
                    "current_pnl_pct": current_pnl_pct,
                    "current_return_on_risk": float(point["pnl_dollars"]) / float(max(args.risk_capital, 1e-9)),
                    "current_premium": float(point["current_premium"]),
                    "premium_ratio": float(point["current_premium"]) / float(max(float(cand_s["entry_premium"]), 1e-9)),
                    "peak_pnl_pct": peak,
                    "drawdown_from_peak": max(0.0, peak - current_pnl_pct),
                    "mae_pnl_pct": float(point.get("mae_pnl_pct", current_pnl_pct)),
                    "current_delta": float(point.get("current_delta", 0.0)),
                    "current_delta_abs": abs(float(point.get("current_delta", 0.0))),
                    "current_iv": float(point.get("current_iv", 0.15)),
                    "current_gamma": float(point.get("current_gamma", 0.0)),
                    "spot_return_bps": float(point.get("spot_return_bps", 0.0)),
                    "signed_spot_return_bps": float(point.get("signed_spot_return_bps", 0.0)),
                    "minutes_remaining": float(max(0, int(args.max_hold_minutes) - int(point["hold_minutes"]))),
                    "pnl_dollars": float(point["pnl_dollars"]),
                    "future_best_pnl_dollars": float(future_best[idx]),
                    "future_best_return_on_risk": float(future_best[idx]) / float(max(args.risk_capital, 1e-9)),
                    "future_edge_return_on_risk": (
                        float(future_best[idx]) - float(point["pnl_dollars"])
                    )
                    / float(max(args.risk_capital, 1e-9)),
                    "terminal_pnl_dollars": terminal,
                    "terminal_return_on_risk": terminal / float(max(args.risk_capital, 1e-9)),
                }
                rows.append(record)

        if rows and group_idx % int(args.state_chunk_groups) == 0:
            chunk_index = flush_state_chunk(rows, chunk_dir, chunk_index)

        if group_idx % int(args.progress_every) == 0:
            elapsed = time.time() - start
            log(
                f"[OPTION_VALUE] day_groups={group_idx}/{len(grouped)} "
                f"state_rows={len(rows):,} elapsed={elapsed:.1f}s"
            )

    flush_state_chunk(rows, chunk_dir, chunk_index)
    chunk_paths = sorted(chunk_dir.glob("state_chunk_*.parquet"))
    if not chunk_paths:
        return pd.DataFrame()
    state_rows = pd.concat([pd.read_parquet(path) for path in chunk_paths], ignore_index=True)
    state_rows = state_rows.drop_duplicates(["candidate_id", "path_idx"], keep="last").reset_index(drop=True)
    log(f"[OPTION_VALUE] built state_rows={len(state_rows):,}")
    return state_rows


def state_rows_cache_status(candidates: pd.DataFrame, state_rows: pd.DataFrame) -> tuple[bool, str]:
    if state_rows.empty:
        return False, "state rows are empty"
    required = {"candidate_id", "signal_id", "ticker", "date", "side"}
    missing_candidates = required - set(candidates.columns)
    missing_state = required - set(state_rows.columns)
    if missing_candidates or missing_state:
        return (
            False,
            f"missing key columns candidates={sorted(missing_candidates)} state_rows={sorted(missing_state)}",
        )

    candidate_keys = candidates[list(required)].copy()
    state_keys = state_rows[list(required)].drop_duplicates("candidate_id", keep="first").copy()
    candidate_keys["candidate_id"] = candidate_keys["candidate_id"].astype(int)
    state_keys["candidate_id"] = state_keys["candidate_id"].astype(int)
    for frame in (candidate_keys, state_keys):
        frame["signal_id"] = frame["signal_id"].astype(int)
        frame["ticker"] = frame["ticker"].astype(str)
        frame["date"] = frame["date"].astype(str).map(normalize_date)
        frame["side"] = frame["side"].astype(str)

    merged = candidate_keys.merge(state_keys, on="candidate_id", how="left", suffixes=("_candidate", "_state"))
    missing = int(merged["signal_id_state"].isna().sum())
    if missing:
        return False, f"missing state paths for {missing:,}/{len(candidate_keys):,} candidates"

    mismatch = (
        (merged["signal_id_candidate"].astype(int) != merged["signal_id_state"].astype(int))
        | (merged["ticker_candidate"].astype(str) != merged["ticker_state"].astype(str))
        | (merged["date_candidate"].astype(str) != merged["date_state"].astype(str))
        | (merged["side_candidate"].astype(str) != merged["side_state"].astype(str))
    )
    mismatch_count = int(mismatch.sum())
    if mismatch_count:
        return False, f"state path keys mismatch for {mismatch_count:,}/{len(candidate_keys):,} candidates"
    return True, f"covers {len(candidate_keys):,} candidates with {len(state_rows):,} state rows"


def missing_state_candidate_ids(candidates: pd.DataFrame, state_rows: pd.DataFrame) -> set[int]:
    if "candidate_id" not in candidates.columns or "candidate_id" not in state_rows.columns:
        return set()
    candidate_ids = set(int(x) for x in candidates["candidate_id"].dropna().astype(int).unique())
    state_ids = set(int(x) for x in state_rows["candidate_id"].dropna().astype(int).unique())
    return candidate_ids - state_ids


def clear_chunk_dir(chunk_dir: Path) -> None:
    if chunk_dir.exists():
        for chunk_path in chunk_dir.glob("state_chunk_*.parquet"):
            chunk_path.unlink()


def clear_state_cache(path: Path, chunk_dir: Path) -> None:
    if path.exists():
        path.unlink()
    clear_chunk_dir(chunk_dir)


def load_or_build_state_rows(candidates: pd.DataFrame, output_dir: Path, args) -> pd.DataFrame:
    path = output_dir / "option_value_state_rows.parquet"
    chunk_dir = output_dir / "option_value_state_chunks"
    if path.exists() and not args.rebuild_state_rows:
        state_rows = clean_date_columns(pd.read_parquet(path))
        state_rows = ensure_dynamic_targets(state_rows)
        ok, reason = state_rows_cache_status(candidates, state_rows)
        if ok:
            log(f"[OPTION_VALUE] reusing state rows from {path}; {reason}")
            return state_rows
        missing_ids = missing_state_candidate_ids(candidates, state_rows)
        if missing_ids and "missing state paths" in reason:
            log(
                f"[OPTION_VALUE] state row cache is missing {len(missing_ids):,} candidates; "
                "building only missing paths"
            )
            missing_candidates = candidates[candidates["candidate_id"].astype(int).isin(missing_ids)].copy()
            missing_chunk_dir = output_dir / "option_value_state_missing_chunks"
            clear_chunk_dir(missing_chunk_dir)
            missing_rows = build_option_state_rows(missing_candidates, args, missing_chunk_dir, set())
            if not missing_rows.empty:
                combined = pd.concat([state_rows, ensure_dynamic_targets(missing_rows)], ignore_index=True)
                combined = combined.drop_duplicates(["candidate_id", "path_idx"], keep="last").reset_index(drop=True)
                ok_after, reason_after = state_rows_cache_status(candidates, combined)
                if ok_after:
                    combined.to_parquet(path, index=False)
                    log(f"[OPTION_VALUE] repaired state row cache from missing paths; {reason_after}")
                    return combined
                log(f"[OPTION_VALUE] missing-path repair did not fully validate: {reason_after}")
            else:
                log("[OPTION_VALUE] missing-path repair produced no rows")
        log(f"[OPTION_VALUE] state row cache is stale: {reason}; rebuilding from scratch")
        clear_state_cache(path, chunk_dir)
    if args.rebuild_state_rows and chunk_dir.exists():
        clear_state_cache(path, chunk_dir)
    processed_candidate_ids: set[int] = set()
    if chunk_dir.exists() and not args.rebuild_state_rows:
        chunk_paths = sorted(chunk_dir.glob("state_chunk_*.parquet"))
        if chunk_paths:
            log(f"[OPTION_VALUE] found {len(chunk_paths)} existing state chunks; resuming")
            for chunk_path in chunk_paths:
                try:
                    ids = pd.read_parquet(chunk_path, columns=["candidate_id"])["candidate_id"].astype(int).unique()
                    processed_candidate_ids.update(int(x) for x in ids)
                except Exception as exc:
                    log(f"[OPTION_VALUE] failed reading chunk {chunk_path}: {exc}")
            log(f"[OPTION_VALUE] processed candidates in chunks={len(processed_candidate_ids):,}")
    state_rows = build_option_state_rows(candidates, args, chunk_dir, processed_candidate_ids)
    if state_rows.empty:
        raise RuntimeError("No option state rows were built.")
    state_rows = ensure_dynamic_targets(state_rows)
    state_rows.to_parquet(path, index=False)
    return state_rows


def make_entry_tensors(frame: pd.DataFrame, scalers: dict, device: torch.device):
    market = torch.from_numpy(scalers["market"].transform(frame)).to(device)
    option = torch.from_numpy(scalers["option"].transform(frame)).to(device)
    horizon = torch.full((len(frame), 1), 1.0, dtype=torch.float32, device=device)
    targets = frame[OPTION_VALUE_TARGETS].astype(float).clip(-2.0, 5.0).to_numpy(dtype=np.float32)
    return market, option, horizon, torch.from_numpy(targets.copy()).to(device)


def make_dynamic_frame(state_rows: pd.DataFrame, candidates: pd.DataFrame, market_features: list[str], option_features: list[str]) -> pd.DataFrame:
    static_cols = ["candidate_id", *market_features, *option_features]
    static = candidates.reindex(columns=static_cols).drop_duplicates("candidate_id")
    return state_rows.merge(static, on="candidate_id", how="inner", validate="many_to_one")


def make_dynamic_tensors(
    frame: pd.DataFrame,
    scalers: dict,
    max_hold_minutes: int,
    device: torch.device,
    dynamic_target: str = "future_best",
):
    market = torch.from_numpy(scalers["market"].transform(frame)).to(device)
    option = torch.from_numpy(scalers["option"].transform(frame)).to(device)
    dynamic = torch.from_numpy(scalers["dynamic"].transform(frame)).to(device)
    horizon = (frame["minutes_remaining"].astype(float).to_numpy(dtype=np.float32) / float(max(max_hold_minutes, 1))).reshape(-1, 1)
    target_col = DYNAMIC_TARGET_COLUMNS.get(str(dynamic_target))
    if target_col is None:
        target_col = "future_best_return_on_risk"
    target = frame[target_col].astype(float).clip(-2.0, 5.0).to_numpy(dtype=np.float32)
    return market, option, dynamic, torch.from_numpy(horizon.copy()).to(device), torch.from_numpy(target.copy()).to(device)


def train_model(
    entry_train: pd.DataFrame,
    dynamic_train: pd.DataFrame,
    market_features: list[str],
    option_features: list[str],
    dynamic_features: list[str],
    args,
) -> tuple[OptionValueJEPA, dict]:
    device = torch.device(args.device if args.device else ("cuda" if torch.cuda.is_available() else "cpu"))
    scalers = {
        "market": fit_scaler(entry_train, market_features),
        "option": fit_scaler(entry_train, option_features),
        "dynamic": fit_scaler(dynamic_train, dynamic_features),
    }
    config = OptionValueConfig(
        market_dim=len(market_features),
        option_dim=len(option_features),
        dynamic_dim=len(dynamic_features),
        hidden_dim=int(args.hidden_dim),
        market_z_dim=int(args.market_z_dim),
        option_z_dim=int(args.option_z_dim),
        dynamic_z_dim=int(args.dynamic_z_dim),
        dropout=float(args.dropout),
    )
    model = OptionValueJEPA(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.lr), weight_decay=float(args.weight_decay))
    loss_fn = nn.SmoothL1Loss()
    loss_fn_none = nn.SmoothL1Loss(reduction="none")

    em, eo, eh, ey = make_entry_tensors(entry_train, scalers, device)
    dm, do, dd, dh, dy = make_dynamic_tensors(
        dynamic_train,
        scalers,
        int(args.max_hold_minutes),
        device,
        str(getattr(args, "dynamic_target", "future_best")),
    )
    entry_loader = DataLoader(
        TensorDataset(em, eo, eh, ey),
        batch_size=int(args.entry_batch_size),
        shuffle=True,
        drop_last=False,
    )
    dyn_loader = DataLoader(
        TensorDataset(dm, do, dd, dh, dy),
        batch_size=int(args.dynamic_batch_size),
        shuffle=True,
        drop_last=False,
    )

    log(
        f"[OPTION_VALUE] train_model entry_rows={len(entry_train):,} dynamic_rows={len(dynamic_train):,} "
        f"device={device} market={len(market_features)} option={len(option_features)} dynamic={len(dynamic_features)}"
    )
    for epoch in range(1, int(args.epochs) + 1):
        model.train()
        entry_losses: list[float] = []
        dyn_losses: list[float] = []
        dyn_iter = iter(dyn_loader)
        for batch in entry_loader:
            try:
                dyn_batch = next(dyn_iter)
            except StopIteration:
                dyn_iter = iter(dyn_loader)
                dyn_batch = next(dyn_iter)
            optimizer.zero_grad(set_to_none=True)
            pred_entry = model.forward_entry(batch[0], batch[1], batch[2])
            loss_entry = loss_fn(pred_entry, batch[3])
            pred_dyn = model.forward_dynamic(dyn_batch[0], dyn_batch[1], dyn_batch[2], dyn_batch[3])
            base_loss_dyn = loss_fn_none(pred_dyn, dyn_batch[4])
            diff = pred_dyn - dyn_batch[4]
            asymmetry = torch.where((diff > 0) & (dyn_batch[4] <= 0.0), 5.0, 1.0)
            loss_dyn = (base_loss_dyn * asymmetry).mean()
            loss = loss_entry + float(args.dynamic_loss_weight) * loss_dyn
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            optimizer.step()
            entry_losses.append(float(loss_entry.detach().cpu()))
            dyn_losses.append(float(loss_dyn.detach().cpu()))
        if epoch == 1 or epoch % int(args.log_every_epochs) == 0 or epoch == int(args.epochs):
            log(
                f"[OPTION_VALUE] epoch={epoch:03d} "
                f"entry_loss={np.mean(entry_losses):.5f} dyn_loss={np.mean(dyn_losses):.5f}"
            )
    model.eval()
    return model, scalers


def predict_entry(model: OptionValueJEPA, scalers: dict, frame: pd.DataFrame, args) -> pd.DataFrame:
    device = next(model.parameters()).device
    out = frame.copy()
    preds = []
    for start in range(0, len(frame), int(args.predict_batch_size)):
        batch = frame.iloc[start : start + int(args.predict_batch_size)]
        market = torch.from_numpy(scalers["market"].transform(batch)).to(device)
        option = torch.from_numpy(scalers["option"].transform(batch)).to(device)
        horizon = torch.full((len(batch), 1), 1.0, dtype=torch.float32, device=device)
        with torch.no_grad():
            pred = model.forward_entry(market, option, horizon).detach().cpu().numpy()
        preds.append(pred)
    pred_all = np.vstack(preds) if preds else np.zeros((0, 3), dtype=np.float32)
    out["ovjepa_pred_hold180"] = pred_all[:, 0] if len(pred_all) else []
    out["ovjepa_pred_rule"] = pred_all[:, 1] if len(pred_all) else []
    out["ovjepa_pred_best"] = pred_all[:, 2] if len(pred_all) else []
    return out


def select_best(candidates: pd.DataFrame, pred_col: str) -> pd.DataFrame:
    return (
        candidates.sort_values(["signal_id", pred_col])
        .groupby("signal_id", sort=False)
        .tail(1)
        .sort_values(["ticker", "date", "time"])
        .reset_index(drop=True)
    )


def select_fixed_delta(candidates: pd.DataFrame, delta_target: float) -> pd.DataFrame:
    if candidates.empty:
        return candidates.copy()
    work = candidates.copy()
    work["_delta_diff"] = (work["delta_target"].astype(float) - float(delta_target)).abs()
    return (
        work.sort_values(["signal_id", "_delta_diff", "delta_target"])
        .groupby("signal_id", sort=False)
        .head(1)
        .drop(columns=["_delta_diff"])
        .sort_values(["ticker", "date", "time"])
        .reset_index(drop=True)
    )


SELECTOR_SCORE_BASES = [
    "ovjepa_pred_hold180",
    "ovjepa_pred_rule",
    "ovjepa_pred_best",
    "ovjepa_pred_mean",
    "ovjepa_pred_min",
    "ovjepa_pred_rule_best_mean",
]


def add_selector_score_bases(candidates: pd.DataFrame) -> pd.DataFrame:
    out = candidates.copy()
    pred_cols = ["ovjepa_pred_hold180", "ovjepa_pred_rule", "ovjepa_pred_best"]
    if all(col in out.columns for col in pred_cols):
        out["ovjepa_pred_mean"] = out[pred_cols].astype(float).mean(axis=1)
        out["ovjepa_pred_min"] = out[pred_cols].astype(float).min(axis=1)
        out["ovjepa_pred_rule_best_mean"] = (
            out["ovjepa_pred_rule"].astype(float) + out["ovjepa_pred_best"].astype(float)
        ) / 2.0
    return out


def select_scored_delta(
    candidates: pd.DataFrame,
    score_base: str,
    delta_bonus: float,
    min_delta_abs: float | None,
) -> pd.DataFrame:
    if candidates.empty or score_base not in candidates.columns:
        return candidates.iloc[0:0].copy()
    work = candidates.copy()
    if min_delta_abs is not None and float(min_delta_abs) > 0.0:
        work = work[work["actual_delta_abs"].astype(float) >= float(min_delta_abs)].copy()
    if work.empty:
        return work
    work["_selector_score"] = work[score_base].astype(float) + float(delta_bonus) * work["actual_delta_abs"].astype(float)
    return select_best(work, "_selector_score").drop(columns=["_selector_score"], errors="ignore")


def apply_same_side_ticker_confirmation(
    selected: pd.DataFrame,
    require_confirmers: dict[str, list[str]] | None = None,
    disabled_tickers: set[str] | None = None,
) -> pd.DataFrame:
    if selected.empty:
        return selected.copy()
    require_confirmers = require_confirmers or {}
    disabled_tickers = disabled_tickers or set()
    keys_by_ticker = {
        str(ticker): set(map(tuple, group[["date", "time", "side"]].astype(str).values))
        for ticker, group in selected.groupby("ticker", sort=False)
    }
    keep = []
    for _, row in selected.iterrows():
        ticker = str(row["ticker"])
        if ticker in disabled_tickers:
            keep.append(False)
            continue
        confirmers = [str(x) for x in require_confirmers.get(ticker, [])]
        if not confirmers:
            keep.append(True)
            continue
        key = (str(row["date"]), str(row["time"]), str(row["side"]))
        keep.append(any(key in keys_by_ticker.get(confirmer, set()) for confirmer in confirmers))
    return selected.loc[keep].sort_values(["ticker", "date", "time"]).reset_index(drop=True)


def entry_cutoff_minutes(value: str | None) -> int | None:
    if value is None or not str(value).strip():
        return None
    return time_to_minutes(str(value))


def apply_entry_cutoff(trades: pd.DataFrame, cutoff_time: str | None) -> pd.DataFrame:
    cutoff = entry_cutoff_minutes(cutoff_time)
    if cutoff is None or trades.empty:
        return trades.copy()
    out = trades.copy()
    return out[out["time"].astype(str).map(time_to_minutes) <= cutoff].reset_index(drop=True)


def set_policy_name(trades: pd.DataFrame, policy_name: str) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    out = trades.copy()
    out["policy"] = policy_name
    return out.reset_index(drop=True)


def order_policy_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    cols = [col for col in ["ticker", "date", "time", "candidate_id"] if col in trades.columns]
    return trades.sort_values(cols).reset_index(drop=True) if cols else trades.reset_index(drop=True)


def exclude_entry_time_window(
    trades: pd.DataFrame,
    ticker: str,
    start_exclusive: str,
    end_inclusive: str,
) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    start_minute = time_to_minutes(start_exclusive)
    end_minute = time_to_minutes(end_inclusive)
    out = trades.copy()
    minutes = out["time"].astype(str).map(time_to_minutes)
    is_target = out["ticker"].astype(str) == str(ticker)
    excluded = is_target & (minutes > start_minute) & (minutes <= end_minute)
    return order_policy_trades(out[~excluded])


def keep_ticker_early_entries(trades: pd.DataFrame, ticker: str, end_inclusive: str) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    end_minute = time_to_minutes(end_inclusive)
    out = trades.copy()
    minutes = out["time"].astype(str).map(time_to_minutes)
    is_target = out["ticker"].astype(str) == str(ticker)
    keep = (~is_target) | (minutes <= end_minute)
    return order_policy_trades(out[keep])


def make_trailing_args(args, hard_stop_pct: float, trail_activation_pct: float, trail_drawdown_pct: float):
    out = argparse.Namespace(**vars(args))
    out.hard_stop_pct = float(hard_stop_pct)
    out.trail_activation_pct = float(trail_activation_pct)
    out.trail_drawdown_pct = float(trail_drawdown_pct)
    return out


def filter_selected_for_ticker_gate(selected: pd.DataFrame, ticker: str, gate: str) -> pd.DataFrame:
    if selected.empty:
        return selected.copy()
    ticker = str(ticker)
    gate = str(gate)
    if gate == "spx_confirm":
        selected = apply_same_side_ticker_confirmation(selected, require_confirmers={ticker: ["SPX"]})
    target = selected[selected["ticker"].astype(str) == ticker].copy()
    if target.empty:
        return target
    minutes = target["time"].astype(str).map(time_to_minutes)
    if gate == "exclude_1131_1230":
        target = target[~((minutes > time_to_minutes("11:30")) & (minutes <= time_to_minutes("12:30")))].copy()
    elif gate == "early_only":
        target = target[minutes <= time_to_minutes("11:30")].copy()
    elif gate == "long_or_early_short":
        keep = (target["side"].astype(str) == "LONG") | (
            (target["side"].astype(str) == "SHORT") & (minutes <= time_to_minutes("11:30"))
        )
        target = target[keep].copy()
    elif gate not in {"all", "spx_confirm"}:
        raise ValueError(f"Unsupported ticker gate: {gate}")
    return order_policy_trades(target)


def filter_state_for_selected(state_rows: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    if state_rows.empty or selected.empty:
        return state_rows.iloc[0:0].copy()
    ids = set(selected["candidate_id"].astype(int))
    return state_rows[state_rows["candidate_id"].astype(int).isin(ids)].copy()


def simulate_ticker_policy(
    selected: pd.DataFrame,
    state_rows: pd.DataFrame,
    args,
    ticker: str,
    gate: str,
    policy_name: str,
) -> pd.DataFrame:
    ticker_selected = filter_selected_for_ticker_gate(selected, ticker, gate)
    return simulate_trailing_exit(ticker_selected, filter_state_for_selected(state_rows, ticker_selected), args, policy_name)


def choose_ticker_validated_policies(
    selected_val: pd.DataFrame,
    state_val: pd.DataFrame,
    args,
) -> tuple[dict[str, dict], dict]:
    configs: dict[str, dict] = {}
    grid_rows: list[dict] = []
    if selected_val.empty:
        return configs, {"grid": grid_rows}
    exit_grid = [
        ("base_60_50_25", float(args.hard_stop_pct), float(args.trail_activation_pct), float(args.trail_drawdown_pct)),
        ("loose_70_50_15", -0.70, 0.50, 0.15),
        ("loose_70_50_25", -0.70, 0.50, 0.25),
        ("loose_70_75_25", -0.70, 0.75, 0.25),
    ]
    base_gates = ["all", "exclude_1131_1230", "early_only", "long_or_early_short"]
    ticker_min_trades = int(getattr(args, "ticker_policy_min_val_trades", 20))
    min_trades = max(int(args.min_val_trades), ticker_min_trades)
    for ticker in sorted(selected_val["ticker"].astype(str).unique()):
        gates = list(base_gates)
        if ticker != "SPX":
            gates.append("spx_confirm")
        best_config: dict | None = None
        best_score = -1e18
        for exit_name, hard_stop, trail_activation, trail_drawdown in exit_grid:
            eval_args = make_trailing_args(args, hard_stop, trail_activation, trail_drawdown)
            for gate in gates:
                trades = simulate_ticker_policy(
                    selected_val,
                    state_val,
                    eval_args,
                    ticker,
                    gate,
                    "validation_ticker_policy",
                )
                metrics = trade_metrics(trades)
                score = score_selector_metrics(metrics, min_trades)
                row = {
                    "ticker": ticker,
                    "exit_name": exit_name,
                    "gate": gate,
                    "hard_stop_pct": float(hard_stop),
                    "trail_activation_pct": float(trail_activation),
                    "trail_drawdown_pct": float(trail_drawdown),
                    "score": float(score),
                    **metrics,
                }
                grid_rows.append(row)
                if score > best_score:
                    best_score = score
                    best_config = {
                        "ticker": ticker,
                        "exit_name": exit_name,
                        "gate": gate,
                        "hard_stop_pct": float(hard_stop),
                        "trail_activation_pct": float(trail_activation),
                        "trail_drawdown_pct": float(trail_drawdown),
                        "score": float(score),
                        "validation_metrics": metrics,
                    }
        if best_config is not None:
            configs[ticker] = best_config
    return configs, {"grid": grid_rows}


def apply_ticker_validated_policies(
    selected: pd.DataFrame,
    state_rows: pd.DataFrame,
    args,
    configs: dict[str, dict],
    policy_name: str,
) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    if selected.empty:
        return selected.iloc[0:0].copy()
    for ticker in sorted(selected["ticker"].astype(str).unique()):
        config = configs.get(
            ticker,
            {
                "gate": "all",
                "hard_stop_pct": float(args.hard_stop_pct),
                "trail_activation_pct": float(args.trail_activation_pct),
                "trail_drawdown_pct": float(args.trail_drawdown_pct),
            },
        )
        eval_args = make_trailing_args(
            args,
            float(config.get("hard_stop_pct", args.hard_stop_pct)),
            float(config.get("trail_activation_pct", args.trail_activation_pct)),
            float(config.get("trail_drawdown_pct", args.trail_drawdown_pct)),
        )
        ticker_trades = simulate_ticker_policy(
            selected,
            state_rows,
            eval_args,
            ticker,
            str(config.get("gate", "all")),
            policy_name,
        )
        parts.append(ticker_trades)
    return set_policy_name(pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(), policy_name)


def simulate_trailing_exit(
    selected: pd.DataFrame,
    state_rows: pd.DataFrame,
    args,
    policy_name: str,
) -> pd.DataFrame:
    trades: list[dict] = []
    if selected.empty or state_rows.empty:
        return pd.DataFrame()
    state_groups = {
        int(candidate_id): group.sort_values("hold_minutes").reset_index(drop=True)
        for candidate_id, group in state_rows.groupby("candidate_id", sort=False)
    }
    activation = float(getattr(args, "trail_activation_pct", float("nan")))
    drawdown = float(getattr(args, "trail_drawdown_pct", float("nan")))
    use_trail = np.isfinite(activation) and np.isfinite(drawdown)
    take_profit = float(getattr(args, "trail_take_profit_pct", 10.0))
    for _, candidate in selected.iterrows():
        path = state_groups.get(int(candidate["candidate_id"]))
        if path is None or path.empty:
            continue
        exit_point = path.iloc[-1]
        exit_reason = "max_time"
        peak_pnl_pct = -float("inf")
        for path_idx, (_, point) in enumerate(path.iterrows()):
            pnl_pct = float(point["current_pnl_pct"])
            peak_pnl_pct = max(peak_pnl_pct, pnl_pct)
            if pnl_pct <= float(args.hard_stop_pct):
                exit_point = path.iloc[path_idx]
                exit_reason = "hard_stop"
                break
            if pnl_pct >= take_profit:
                exit_point = path.iloc[path_idx]
                exit_reason = "take_profit"
                break
            if use_trail and peak_pnl_pct >= activation and pnl_pct <= peak_pnl_pct - drawdown:
                exit_point = path.iloc[path_idx]
                exit_reason = "trail_stop"
                break
        trades.append(path_rows_to_trade(candidate, exit_point, policy_name, exit_reason))
    return apply_entry_cutoff(pd.DataFrame(trades), getattr(args, "entry_cutoff_time", ""))


def score_selector_metrics(metrics: dict, min_trades: int) -> float:
    trades = int(metrics.get("trades", 0))
    wr = float(metrics.get("win_rate", 0.0))
    pf = float(metrics.get("profit_factor", 0.0))
    pnl = float(metrics.get("pnl_dollars", 0.0))
    dd = abs(float(metrics.get("max_drawdown", 0.0)))
    if trades < int(min_trades) or pnl <= 0.0 or pf <= 0.0 or not np.isfinite(pf):
        return -1e9 + pnl
    return pnl / 1000.0 + 100.0 * wr + 40.0 * np.log(max(pf, 1e-6)) + trades / 10.0 - dd / 2000.0


def choose_trailing_selector(
    val_pred: pd.DataFrame,
    state_val: pd.DataFrame,
    args,
) -> tuple[dict, dict]:
    enriched = add_selector_score_bases(val_pred)
    rows = []
    best_config: dict | None = None
    best_score = -1e18
    min_deltas = [float(x) for x in getattr(args, "selector_min_deltas", [0.0])]
    delta_bonuses = [float(x) for x in getattr(args, "selector_delta_bonuses", [0.0])]
    for score_base in SELECTOR_SCORE_BASES:
        if score_base not in enriched.columns:
            continue
        for delta_bonus in delta_bonuses:
            for min_delta in min_deltas:
                selected = select_scored_delta(
                    enriched,
                    score_base,
                    delta_bonus,
                    None if float(min_delta) <= 0.0 else float(min_delta),
                )
                trades = simulate_trailing_exit(selected, state_val, args, "validation_option_value_trail_selector")
                metrics = trade_metrics(trades)
                score = score_selector_metrics(metrics, int(args.min_val_trades))
                row = {
                    "score_base": score_base,
                    "delta_bonus": float(delta_bonus),
                    "min_delta_abs": None if float(min_delta) <= 0.0 else float(min_delta),
                    "score": float(score),
                    **metrics,
                }
                rows.append(row)
                if score > best_score:
                    best_score = score
                    best_config = {
                        "score_base": score_base,
                        "delta_bonus": float(delta_bonus),
                        "min_delta_abs": row["min_delta_abs"],
                        "score": float(score),
                    }
    if best_config is None:
        best_config = {"score_base": "ovjepa_pred_best", "delta_bonus": 0.0, "min_delta_abs": None, "score": -1e18}
    return best_config, {"grid": rows}


def path_rows_to_trade(candidate: pd.Series, point: pd.Series, policy_name: str, reason: str) -> dict:
    return {
        "policy": policy_name,
        "candidate_id": int(candidate["candidate_id"]),
        "signal_id": int(candidate["signal_id"]),
        "ticker": str(candidate["ticker"]),
        "date": str(candidate["date"]),
        "time": str(candidate["time"]),
        "side": str(candidate["side"]),
        "delta_target": float(candidate["delta_target"]),
        "actual_delta_abs": float(candidate["actual_delta_abs"]),
        "actual_strike": float(candidate["actual_strike"]),
        "entry_premium": float(candidate["entry_premium"]),
        "contracts": int(candidate["contracts"]),
        "exit_reason": reason,
        "exit_time": str(point["path_time"]),
        "hold_minutes": int(point["hold_minutes"]),
        "pnl_pct": float(point["current_pnl_pct"]),
        "pnl_dollars": float(point["pnl_dollars"]),
        "pred_hold180": float(candidate.get("ovjepa_pred_hold180", np.nan)),
        "pred_rule": float(candidate.get("ovjepa_pred_rule", np.nan)),
        "pred_best": float(candidate.get("ovjepa_pred_best", np.nan)),
    }


def predict_continuation(
    model: OptionValueJEPA,
    scalers: dict,
    candidate: pd.Series,
    point: pd.Series,
    market_features: list[str],
    option_features: list[str],
    dynamic_features: list[str],
    max_hold_minutes: int,
) -> float:
    device = next(model.parameters()).device
    row = {feature: candidate.get(feature, np.nan) for feature in market_features + option_features}
    for feature in dynamic_features:
        row[feature] = point.get(feature, np.nan)
    frame = pd.DataFrame([row])
    market = torch.from_numpy(scalers["market"].transform(frame)).to(device)
    option = torch.from_numpy(scalers["option"].transform(frame)).to(device)
    dynamic = torch.from_numpy(scalers["dynamic"].transform(frame)).to(device)
    horizon = torch.tensor(
        [[float(point.get("minutes_remaining", 0.0)) / float(max(max_hold_minutes, 1))]],
        dtype=torch.float32,
        device=device,
    )
    with torch.no_grad():
        return float(model.forward_dynamic(market, option, dynamic, horizon).detach().cpu().numpy()[0])


def predict_continuation_path(
    model: OptionValueJEPA,
    scalers: dict,
    candidate: pd.Series,
    path: pd.DataFrame,
    market_features: list[str],
    option_features: list[str],
    dynamic_features: list[str],
    max_hold_minutes: int,
) -> np.ndarray:
    if path.empty:
        return np.zeros(0, dtype=np.float32)
    device = next(model.parameters()).device
    base = {feature: candidate.get(feature, np.nan) for feature in market_features + option_features}
    rows = []
    for _, point in path.iterrows():
        row = dict(base)
        for feature in dynamic_features:
            row[feature] = point.get(feature, np.nan)
        rows.append(row)
    frame = pd.DataFrame(rows)
    market = torch.from_numpy(scalers["market"].transform(frame)).to(device)
    option = torch.from_numpy(scalers["option"].transform(frame)).to(device)
    dynamic = torch.from_numpy(scalers["dynamic"].transform(frame)).to(device)
    horizon = (
        path["minutes_remaining"].astype(float).to_numpy(dtype=np.float32).reshape(-1, 1)
        / float(max(max_hold_minutes, 1))
    )
    horizon_t = torch.from_numpy(horizon).to(device)
    with torch.no_grad():
        return model.forward_dynamic(market, option, dynamic, horizon_t).detach().cpu().numpy().astype(np.float32)


def build_dynamic_path_prediction_cache(
    selected: pd.DataFrame,
    state_rows: pd.DataFrame,
    model: OptionValueJEPA,
    scalers: dict,
    market_features: list[str],
    option_features: list[str],
    dynamic_features: list[str],
    args,
) -> dict[int, tuple[pd.Series, pd.DataFrame, np.ndarray]]:
    state_groups = {
        int(candidate_id): group.sort_values("hold_minutes").reset_index(drop=True)
        for candidate_id, group in state_rows.groupby("candidate_id", sort=False)
    }
    cache: dict[int, tuple[pd.Series, pd.DataFrame, np.ndarray]] = {}
    for _, candidate in selected.iterrows():
        candidate_id = int(candidate["candidate_id"])
        path = state_groups.get(candidate_id)
        if path is None or path.empty:
            continue
        predicted_path = predict_continuation_path(
            model,
            scalers,
            candidate,
            path,
            market_features,
            option_features,
            dynamic_features,
            int(args.max_hold_minutes),
        )
        cache[candidate_id] = (candidate, path, predicted_path)
    return cache


def simulate_learned_exit_from_cache(
    prediction_cache: dict[int, tuple[pd.Series, pd.DataFrame, np.ndarray]],
    args,
    margin: float,
    policy_name: str,
) -> pd.DataFrame:
    trades: list[dict] = []
    for candidate, path, predicted_path in prediction_cache.values():
        exit_point = path.iloc[-1]
        exit_reason = "max_time"
        for path_idx, (_, point) in enumerate(path.iterrows()):
            pnl_pct = float(point["current_pnl_pct"])
            if pnl_pct <= float(args.hard_stop_pct):
                exit_point = path.iloc[path_idx]
                exit_reason = "hard_stop"
                break
            if int(point["hold_minutes"]) < int(args.min_exit_hold_minutes):
                continue
            predicted_future = float(predicted_path[path_idx]) if len(predicted_path) else float("nan")
            current_return = float(point["pnl_dollars"]) / float(max(args.risk_capital, 1e-9))
            if str(getattr(args, "dynamic_target", "future_best")) == "future_edge":
                should_exit = predicted_future <= float(margin)
            else:
                should_exit = predicted_future <= current_return + float(margin)
            if should_exit:
                exit_point = path.iloc[path_idx]
                exit_reason = "learned_exit"
                break
        trades.append(path_rows_to_trade(candidate, exit_point, policy_name, exit_reason))
    return pd.DataFrame(trades)


def simulate_learned_exit(
    selected: pd.DataFrame,
    state_rows: pd.DataFrame,
    model: OptionValueJEPA,
    scalers: dict,
    market_features: list[str],
    option_features: list[str],
    dynamic_features: list[str],
    args,
    margin: float,
    policy_name: str,
) -> pd.DataFrame:
    prediction_cache = build_dynamic_path_prediction_cache(
        selected,
        state_rows,
        model,
        scalers,
        market_features,
        option_features,
        dynamic_features,
        args,
    )
    return simulate_learned_exit_from_cache(prediction_cache, args, margin, policy_name)


def simulate_learned_profit_lock_from_cache(
    prediction_cache: dict[int, tuple[pd.Series, pd.DataFrame, np.ndarray]],
    args,
    margin: float,
    profit_activation_pct: float,
    trail_activation_pct: float | None,
    trail_drawdown_pct: float | None,
    policy_name: str,
) -> pd.DataFrame:
    trades: list[dict] = []
    take_profit = float(getattr(args, "trail_take_profit_pct", 10.0))
    use_trail_gate = trail_activation_pct is not None and trail_drawdown_pct is not None
    for candidate, path, predicted_path in prediction_cache.values():
        exit_point = path.iloc[-1]
        exit_reason = "max_time"
        peak_pnl_pct = -float("inf")
        for path_idx, (_, point) in enumerate(path.iterrows()):
            pnl_pct = float(point["current_pnl_pct"])
            peak_pnl_pct = max(peak_pnl_pct, pnl_pct)
            if pnl_pct <= float(args.hard_stop_pct):
                exit_point = path.iloc[path_idx]
                exit_reason = "hard_stop"
                break
            if pnl_pct >= take_profit:
                exit_point = path.iloc[path_idx]
                exit_reason = "take_profit"
                break
            predicted_future = float(predicted_path[path_idx]) if len(predicted_path) else float("nan")
            if (
                use_trail_gate
                and peak_pnl_pct >= float(trail_activation_pct)
                and pnl_pct <= peak_pnl_pct - float(trail_drawdown_pct)
                and predicted_future <= float(margin)
            ):
                exit_point = path.iloc[path_idx]
                exit_reason = "learned_trail_stop"
                break
            if int(point["hold_minutes"]) < int(args.min_exit_hold_minutes):
                continue
            if pnl_pct >= float(profit_activation_pct) and predicted_future <= float(margin):
                exit_point = path.iloc[path_idx]
                exit_reason = "learned_profit_lock"
                break
        trades.append(path_rows_to_trade(candidate, exit_point, policy_name, exit_reason))
    return apply_entry_cutoff(pd.DataFrame(trades), getattr(args, "entry_cutoff_time", ""))


def simulate_learned_profit_lock_exit(
    selected: pd.DataFrame,
    state_rows: pd.DataFrame,
    model: OptionValueJEPA,
    scalers: dict,
    market_features: list[str],
    option_features: list[str],
    dynamic_features: list[str],
    args,
    margin: float,
    profit_activation_pct: float,
    trail_activation_pct: float | None,
    trail_drawdown_pct: float | None,
    policy_name: str,
) -> pd.DataFrame:
    prediction_cache = build_dynamic_path_prediction_cache(
        selected,
        state_rows,
        model,
        scalers,
        market_features,
        option_features,
        dynamic_features,
        args,
    )
    return simulate_learned_profit_lock_from_cache(
        prediction_cache,
        args,
        margin,
        profit_activation_pct,
        trail_activation_pct,
        trail_drawdown_pct,
        policy_name,
    )


def choose_exit_margin(
    selected_val: pd.DataFrame,
    state_rows: pd.DataFrame,
    model: OptionValueJEPA,
    scalers: dict,
    market_features: list[str],
    option_features: list[str],
    dynamic_features: list[str],
    args,
) -> tuple[float, dict]:
    if str(getattr(args, "dynamic_target", "future_best")) == "future_edge":
        grid = [-0.05, 0.0, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.45, 0.65]
    else:
        grid = [-0.30, -0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20, 0.35]
    best_margin = 0.0
    best_score = -1e18
    rows = []
    prediction_cache = build_dynamic_path_prediction_cache(
        selected_val,
        state_rows,
        model,
        scalers,
        market_features,
        option_features,
        dynamic_features,
        args,
    )
    log(
        "[OPTION_VALUE] validation exit-margin cached "
        f"paths={len(prediction_cache):,} grid={len(grid):,}"
    )
    for margin in grid:
        trades = simulate_learned_exit_from_cache(
            prediction_cache,
            args,
            margin,
            "validation_option_value_exit",
        )
        metrics = trade_metrics(trades)
        score = score_metrics(metrics, int(args.min_val_trades))
        rows.append({"margin": float(margin), "score": float(score), **metrics})
        if score > best_score:
            best_score = score
            best_margin = float(margin)
    return best_margin, {"grid": rows}


def choose_profit_lock_config(
    selected_val: pd.DataFrame,
    state_rows: pd.DataFrame,
    model: OptionValueJEPA,
    scalers: dict,
    market_features: list[str],
    option_features: list[str],
    dynamic_features: list[str],
    args,
) -> tuple[dict, dict]:
    margins = [float(x) for x in getattr(args, "profit_lock_margins", [-0.05, 0.0, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.45, 0.65, 1.0])]
    activations = [float(x) for x in getattr(args, "profit_lock_activations", [0.30, 0.50, 0.75, 1.0, 1.5, 2.0])]
    trail_pairs = [(None, None)]
    for value in getattr(args, "profit_lock_trail_pairs", ["0.50:0.25"]):
        text = str(value).strip()
        if not text:
            continue
        try:
            activation_text, drawdown_text = text.split(":", 1)
            trail_pairs.append((float(activation_text), float(drawdown_text)))
        except ValueError:
            raise ValueError(f"Invalid --profit-lock-trail-pairs value '{text}', expected activation:drawdown")
    rows = []
    best_config: dict | None = None
    best_score = -1e18
    prediction_cache = build_dynamic_path_prediction_cache(
        selected_val,
        state_rows,
        model,
        scalers,
        market_features,
        option_features,
        dynamic_features,
        args,
    )
    log(
        "[OPTION_VALUE] validation profit-lock cached "
        f"paths={len(prediction_cache):,} grid={len(margins) * len(activations) * len(trail_pairs):,}"
    )
    for margin in margins:
        for activation in activations:
            for trail_activation, trail_drawdown in trail_pairs:
                trades = simulate_learned_profit_lock_from_cache(
                    prediction_cache,
                    args,
                    margin,
                    activation,
                    trail_activation,
                    trail_drawdown,
                    "validation_option_value_profit_lock",
                )
                metrics = trade_metrics(trades)
                score = score_selector_metrics(metrics, int(args.min_val_trades))
                row = {
                    "margin": float(margin),
                    "profit_activation_pct": float(activation),
                    "trail_activation_pct": trail_activation,
                    "trail_drawdown_pct": trail_drawdown,
                    "score": float(score),
                    **metrics,
                }
                rows.append(row)
                if score > best_score:
                    best_score = score
                    best_config = {
                        "margin": float(margin),
                        "profit_activation_pct": float(activation),
                        "trail_activation_pct": trail_activation,
                        "trail_drawdown_pct": trail_drawdown,
                        "score": float(score),
                    }
    if best_config is None:
        best_config = {
            "margin": 0.0,
            "profit_activation_pct": 0.50,
            "trail_activation_pct": None,
            "trail_drawdown_pct": None,
            "score": -1e18,
        }
    return best_config, {"grid": rows}


def policy_payload(trades: pd.DataFrame) -> dict:
    ordered = order_policy_trades(trades)
    return {
        "overall": trade_metrics(ordered),
        "per_ticker": {str(k): trade_metrics(v) for k, v in ordered.groupby("ticker", sort=True)} if not ordered.empty else {},
        "trades": ordered,
    }


def metrics_row(label: str, metrics: dict) -> str:
    return (
        f"| {label} | {metrics.get('trades', 0)} | {fmt_pct(metrics.get('win_rate', float('nan')))} | "
        f"{fmt_float(metrics.get('profit_factor', float('nan')))} | "
        f"{fmt_money(metrics.get('pnl_dollars', 0.0))} | "
        f"{fmt_money(metrics.get('max_drawdown', 0.0))} | "
        f"{fmt_money(metrics.get('avg_pnl', 0.0))} | "
        f"{fmt_float(metrics.get('avg_hold_minutes', float('nan')), 1)} | "
        f"{fmt_float(metrics.get('avg_delta_abs', float('nan')), 3)} |"
    )


def write_summary(output_dir: Path, args, metadata: dict, policy_results: dict[str, dict]) -> None:
    production_train = bool(getattr(args, "production_train", False))
    title = "# OptionValueJEPA Production Final Fit" if production_train else "# OptionValueJEPA 0DTE Value And 5m Exit"
    test_start = normalize_date(args.test_start_date) if str(getattr(args, "test_start_date", "")).strip() else "n/a"
    lines = [
        title,
        "",
        f"Candidate labels: `{args.candidate_labels}`",
        f"Train cutoff: `{normalize_date(args.train_end_date)}`",
        f"Test start: `{test_start}`",
        f"Dynamic target: `{getattr(args, 'dynamic_target', 'future_best')}`",
        f"Max hold: `{args.max_hold_minutes}`m, hard stop `{args.hard_stop_pct:.0%}`, learned exit min hold `{args.min_exit_hold_minutes}`m.",
        "",
    ]
    if policy_results:
        lines += [
            "## OOS Results",
            "",
            "| Policy | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for policy, payload in policy_results.items():
            lines.append(metrics_row(policy, payload["overall"]))
    else:
        lines += [
            "## Production Fit",
            "",
            "No OOS trades are evaluated in this run. This artifact is the final production fit; promotion metrics come from the fixed OOS run.",
        ]

    lines += [
        "",
        "## Interpretation",
        "",
        "- `fixed_delta_0.70_hard` is the current deployable reference from prior validation.",
        "- `option_value_*_hard` tests whether OptionValueJEPA can choose a better delta/strike while keeping the mechanical exit.",
        "- `option_value_*_learned_exit` tests the same strike selector plus a continuation-value exit evaluated every 5m.",
        "- `*_trail_cutoff` uses the configured trailing-stop exit and entry cutoff; the OptionValue selector is selected only on validation months.",
        "- `*_ticker_validated_trail_cutoff` lets each ticker choose its own mechanical exit and entry gate from validation only, then applies that frozen config to OOS.",
        "- `*_learned_profit_lock` uses the dynamic JEPA continuation head only after the trade is already profitable, optionally gating the mechanical trail with predicted future edge.",
        "- Oracle rows are non-deployable ceilings.",
        "",
        "## Validation",
        "",
        f"- Exit margin selected on validation: `{fmt_float(metadata.get('exit_margin', float('nan')), 4)}`.",
        f"- Trail selector selected on validation: `{metadata.get('trail_selector_config', {})}`.",
        f"- Ticker policies selected on validation: `{metadata.get('ticker_policy_config', {})}`.",
        f"- Learned profit-lock selected on validation: `{metadata.get('profit_lock_config', {})}`.",
        f"- Blended selector tested: `{metadata.get('blended_selector_config', {})}`.",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(metadata, indent=2, allow_nan=True),
        "```",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def save_policy_outputs(output_dir: Path, policy_results: dict[str, dict]) -> None:
    for policy, payload in policy_results.items():
        payload["trades"].to_csv(output_dir / f"{policy}_trades.csv", index=False)


def save_model_artifacts(model_dir: Path, model: OptionValueJEPA, scalers: dict, metadata: dict) -> None:
    torch.save(
        {
            "config": model.config.to_dict(),
            "model_state": model.state_dict(),
            "metadata": metadata,
        },
        model_dir / "option_value_jepa.pt",
    )
    scaler_payload = {
        name: asdict(scaler) if isinstance(scaler, FeatureScaler) else scaler
        for name, scaler in scalers.items()
    }
    joblib.dump(scaler_payload, model_dir / "option_value_jepa_scalers.joblib")


def main() -> int:
    parser = argparse.ArgumentParser(description="Train OptionValueJEPA and a 5m learned option exit policy.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--train-start-date", default="20250101")
    parser.add_argument("--train-end-date", default="20260331")
    parser.add_argument("--test-start-date", default="20260401")
    parser.add_argument("--production-train", action="store_true", help="Train and save a final production model without OOS evaluation.")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--risk-capital", type=float, default=1000.0)
    parser.add_argument("--max-hold-minutes", type=int, default=180)
    parser.add_argument("--hard-stop-pct", type=float, default=-0.60)
    parser.add_argument("--min-exit-hold-minutes", type=int, default=15)
    parser.add_argument("--greeks-cache-size", type=int, default=60)
    parser.add_argument("--progress-every", type=int, default=20)
    parser.add_argument("--state-chunk-groups", type=int, default=20)
    parser.add_argument("--rebuild-state-rows", action="store_true")
    parser.add_argument("--epochs", type=int, default=35)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--market-z-dim", type=int, default=32)
    parser.add_argument("--option-z-dim", type=int, default=16)
    parser.add_argument("--dynamic-z-dim", type=int, default=16)
    parser.add_argument("--dropout", type=float, default=0.10)
    parser.add_argument("--lr", type=float, default=8e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--dynamic-loss-weight", type=float, default=0.75)
    parser.add_argument(
        "--dynamic-target",
        choices=sorted(DYNAMIC_TARGET_COLUMNS),
        default="future_best",
        help="Continuation target: absolute future best return or incremental future edge over current return.",
    )
    parser.add_argument("--entry-cutoff-time", default="", help="Optional latest entry time for trail/cutoff policies, e.g. 14:30.")
    parser.add_argument("--trail-activation-pct", type=float, default=float("nan"))
    parser.add_argument("--trail-drawdown-pct", type=float, default=float("nan"))
    parser.add_argument("--trail-take-profit-pct", type=float, default=10.0)
    parser.add_argument("--selector-delta-bonuses", nargs="+", type=float, default=[0.0, 0.5, 1.0, 1.5, 2.0, 3.0])
    parser.add_argument("--selector-min-deltas", nargs="+", type=float, default=[0.0, 0.50, 0.60])
    parser.add_argument("--blended-selector-score-base", default="ovjepa_pred_rule_best_mean")
    parser.add_argument("--blended-selector-delta-bonus", type=float, default=2.0)
    parser.add_argument("--blended-selector-min-delta", type=float, default=0.0)
    parser.add_argument("--ticker-policy-min-val-trades", type=int, default=20)
    parser.add_argument("--enable-profit-lock-research", action="store_true", help="Evaluate the experimental JEPA learned profit-lock exit grid.")
    parser.add_argument("--profit-lock-margins", nargs="+", type=float, default=[-0.05, 0.0, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.45, 0.65, 1.0])
    parser.add_argument("--profit-lock-activations", nargs="+", type=float, default=[0.30, 0.50, 0.75, 1.0, 1.5, 2.0])
    parser.add_argument(
        "--profit-lock-trail-pairs",
        nargs="+",
        default=["", "0.50:0.25", "0.30:0.05", "0.30:0.10", "0.50:0.10", "0.75:0.20"],
        help="Optional learned-gated trail configs as activation:drawdown. Empty string means no trail gate.",
    )
    parser.add_argument("--entry-batch-size", type=int, default=512)
    parser.add_argument("--dynamic-batch-size", type=int, default=4096)
    parser.add_argument("--predict-batch-size", type=int, default=4096)
    parser.add_argument("--min-val-trades", type=int, default=12)
    parser.add_argument("--seed", type=int, default=2227)
    parser.add_argument("--device", default="")
    parser.add_argument("--log-every-epochs", type=int, default=5)
    args = parser.parse_args()

    np.random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    output_dir = Path(args.output_dir)
    model_dir = Path(args.model_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    global LOG_PATH
    LOG_PATH = output_dir / "run.log"
    if LOG_PATH.exists():
        LOG_PATH.unlink()

    candidates = clean_date_columns(pd.read_parquet(args.candidate_labels))
    candidates = candidates[candidates["date"].astype(str) >= normalize_date(args.train_start_date)].copy()
    train_end = normalize_date(args.train_end_date)
    production_train = bool(getattr(args, "production_train", False))
    if production_train:
        candidates = candidates[candidates["date"].astype(str) <= train_end].copy()
    if candidates.empty:
        raise RuntimeError("No candidate rows after date filters.")
    state_rows = load_or_build_state_rows(candidates, output_dir, args)

    test_start = normalize_date(args.test_start_date)
    train_candidates = candidates[candidates["date"].astype(str) <= train_end].copy()
    if production_train:
        test_candidates = candidates.iloc[0:0].copy()
        log(
            f"[OPTION_VALUE] production_train enabled; final fit rows={len(train_candidates):,} "
            f"train_end={train_end}"
        )
    else:
        test_candidates = candidates[candidates["date"].astype(str) >= test_start].copy()
        if test_candidates.empty:
            raise RuntimeError("Train/test split produced no test rows.")
    if train_candidates.empty:
        raise RuntimeError("Train/test split produced no train rows.")

    train_months = sorted(train_candidates["month"].astype(str).unique().tolist())
    val_months = set(train_months[-int(args.val_months):])
    fit_candidates = train_candidates[~train_candidates["month"].isin(val_months)].copy()
    val_candidates = train_candidates[train_candidates["month"].isin(val_months)].copy()
    if fit_candidates.empty or val_candidates.empty:
        fit_candidates = train_candidates.copy()
        val_candidates = train_candidates.copy()

    market_features, option_features, dynamic_features = infer_feature_sets(candidates)
    dynamic_features = [f for f in dynamic_features if f in state_rows.columns]
    state_fit = state_rows[state_rows["candidate_id"].isin(set(fit_candidates["candidate_id"].astype(int)))].copy()
    state_val = state_rows[state_rows["candidate_id"].isin(set(val_candidates["candidate_id"].astype(int)))].copy()
    state_train = state_rows[state_rows["candidate_id"].isin(set(train_candidates["candidate_id"].astype(int)))].copy()
    state_test = (
        state_rows[state_rows["candidate_id"].isin(set(test_candidates["candidate_id"].astype(int)))].copy()
        if not production_train
        else state_rows.iloc[0:0].copy()
    )
    dyn_fit = make_dynamic_frame(state_fit, fit_candidates, market_features, option_features)
    dyn_train = make_dynamic_frame(state_train, train_candidates, market_features, option_features)
    if dyn_fit.empty or dyn_train.empty:
        raise RuntimeError("Dynamic training rows are empty.")

    log("[OPTION_VALUE] training fit model for validation margin")
    fit_model, fit_scalers = train_model(fit_candidates, dyn_fit, market_features, option_features, dynamic_features, args)
    val_pred = predict_entry(fit_model, fit_scalers, val_candidates, args)
    val_pred_scored = add_selector_score_bases(val_pred)
    selected_val_best = select_best(val_pred, "ovjepa_pred_best")
    exit_margin, exit_payload = choose_exit_margin(
        selected_val_best,
        state_val,
        fit_model,
        fit_scalers,
        market_features,
        option_features,
        dynamic_features,
        args,
    )
    trail_selector_config, trail_selector_payload = choose_trailing_selector(val_pred, state_val, args)
    selected_val_blended = select_scored_delta(
        val_pred_scored,
        str(args.blended_selector_score_base),
        float(args.blended_selector_delta_bonus),
        None if float(args.blended_selector_min_delta) <= 0.0 else float(args.blended_selector_min_delta),
    )
    ticker_policy_config, ticker_policy_payload = choose_ticker_validated_policies(
        selected_val_blended,
        state_val,
        args,
    )
    profit_lock_config: dict = {"enabled": False}
    profit_lock_payload: dict = {"grid": []}
    if bool(getattr(args, "enable_profit_lock_research", False)):
        profit_lock_config, profit_lock_payload = choose_profit_lock_config(
            selected_val_blended,
            state_val,
            fit_model,
            fit_scalers,
            market_features,
            option_features,
            dynamic_features,
            args,
        )
    log(
        "[OPTION_VALUE] validation trail selector "
        f"score_base={trail_selector_config.get('score_base')} "
        f"delta_bonus={trail_selector_config.get('delta_bonus')} "
        f"min_delta_abs={trail_selector_config.get('min_delta_abs')} "
        f"score={trail_selector_config.get('score'):.4f}"
    )
    log(f"[OPTION_VALUE] validation ticker policies {ticker_policy_config}")
    if bool(getattr(args, "enable_profit_lock_research", False)):
        log(
            "[OPTION_VALUE] validation learned profit-lock "
            f"margin={profit_lock_config.get('margin')} "
            f"activation={profit_lock_config.get('profit_activation_pct')} "
            f"trail_activation={profit_lock_config.get('trail_activation_pct')} "
            f"trail_drawdown={profit_lock_config.get('trail_drawdown_pct')} "
            f"score={profit_lock_config.get('score'):.4f}"
        )
    else:
        log("[OPTION_VALUE] learned profit-lock research skipped")

    log("[OPTION_VALUE] training final model")
    final_model, final_scalers = train_model(train_candidates, dyn_train, market_features, option_features, dynamic_features, args)
    if production_train:
        production_pred = add_selector_score_bases(predict_entry(final_model, final_scalers, train_candidates, args))
        production_selected = select_scored_delta(
            production_pred,
            str(args.blended_selector_score_base),
            float(args.blended_selector_delta_bonus),
            None if float(args.blended_selector_min_delta) <= 0.0 else float(args.blended_selector_min_delta),
        )
        production_pred.to_csv(output_dir / "production_candidate_predictions.csv", index=False)
        production_selected.to_csv(output_dir / "production_selected_candidates.csv", index=False)
        metadata = {
            "args": vars(args),
            "production_train": True,
            "market_features": market_features,
            "option_features": option_features,
            "dynamic_features": dynamic_features,
            "train_candidates": int(len(train_candidates)),
            "test_candidates": 0,
            "state_rows": int(len(state_rows)),
            "train_state_rows": int(len(state_train)),
            "test_state_rows": 0,
            "val_months": sorted(val_months),
            "exit_margin": exit_margin,
            "exit_margin_grid": exit_payload,
            "trail_selector_config": trail_selector_config,
            "trail_selector_grid": trail_selector_payload,
            "ticker_policy_config": ticker_policy_config,
            "ticker_policy_grid": ticker_policy_payload,
            "profit_lock_config": profit_lock_config,
            "profit_lock_grid": profit_lock_payload,
            "blended_selector_config": {
                "score_base": str(args.blended_selector_score_base),
                "delta_bonus": float(args.blended_selector_delta_bonus),
                "min_delta_abs": None if float(args.blended_selector_min_delta) <= 0.0 else float(args.blended_selector_min_delta),
            },
            "policy_metrics": {},
        }
        (output_dir / "metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
        save_model_artifacts(model_dir, final_model, final_scalers, metadata)
        write_summary(output_dir, args, metadata, {})
        print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
        return 0

    test_pred = predict_entry(final_model, final_scalers, test_candidates, args)
    test_pred_scored = add_selector_score_bases(test_pred)

    selected_hold = select_best(test_pred, "ovjepa_pred_hold180")
    selected_rule = select_best(test_pred, "ovjepa_pred_rule")
    selected_best = select_best(test_pred, "ovjepa_pred_best")
    selected_fixed_070 = select_fixed_delta(test_pred, 0.70)
    selected_trail_score = select_scored_delta(
        test_pred_scored,
        str(trail_selector_config.get("score_base", "ovjepa_pred_best")),
        float(trail_selector_config.get("delta_bonus", 0.0)),
        trail_selector_config.get("min_delta_abs"),
    )
    selected_blended_score = select_scored_delta(
        test_pred_scored,
        str(args.blended_selector_score_base),
        float(args.blended_selector_delta_bonus),
        None if float(args.blended_selector_min_delta) <= 0.0 else float(args.blended_selector_min_delta),
    )
    selected_blended_spy_confirmed = apply_same_side_ticker_confirmation(
        selected_blended_score,
        require_confirmers={"SPY": ["SPX"]},
    )
    selected_blended_qqq_spx_confirmed = apply_same_side_ticker_confirmation(
        selected_blended_score,
        require_confirmers={"QQQ": ["SPX"]},
    )

    fixed_070 = fixed_delta_policy(test_candidates, 0.70, "rule", "fixed_delta_0.70_hard")
    fixed_070_trail = simulate_trailing_exit(
        selected_fixed_070,
        state_test,
        args,
        "fixed_delta_0.70_trail_cutoff",
    )
    oracle_rule = oracle_policy(test_candidates, "rule_pnl_dollars", "rule", "oracle_best_delta_hard")
    oracle_exit = oracle_policy(test_candidates, "oracle_pnl_dollars", "oracle", "oracle_best_delta_oracle_exit")
    ov_hold_hard = candidate_trades_from_selection(selected_hold, "rule", "option_value_hold180_select_hard")
    ov_rule_hard = candidate_trades_from_selection(selected_rule, "rule", "option_value_rule_select_hard")
    ov_best_hard = candidate_trades_from_selection(selected_best, "rule", "option_value_best_select_hard")
    ov_best_learned = simulate_learned_exit(
        selected_best,
        state_test,
        final_model,
        final_scalers,
        market_features,
        option_features,
        dynamic_features,
        args,
        exit_margin,
        "option_value_best_select_learned_exit_5m",
    )
    ov_rule_learned = simulate_learned_exit(
        selected_rule,
        state_test,
        final_model,
        final_scalers,
        market_features,
        option_features,
        dynamic_features,
        args,
        exit_margin,
        "option_value_rule_select_learned_exit_5m",
    )
    fixed_070_learned = simulate_learned_exit(
        selected_fixed_070,
        state_test,
        final_model,
        final_scalers,
        market_features,
        option_features,
        dynamic_features,
        args,
        exit_margin,
        "fixed_delta_0.70_learned_exit_5m",
    )
    ov_trail_score = simulate_trailing_exit(
        selected_trail_score,
        state_test,
        args,
        "option_value_validated_score_trail_cutoff",
    )
    ov_blended_score = simulate_trailing_exit(
        selected_blended_score,
        state_test,
        args,
        "option_value_blended_score_trail_cutoff",
    )
    ov_blended_spy_confirmed = simulate_trailing_exit(
        selected_blended_spy_confirmed,
        state_test,
        args,
        "option_value_blended_score_trail_cutoff_spy_spx_confirm",
    )
    ov_blended_qqq_spx_confirmed = simulate_trailing_exit(
        selected_blended_qqq_spx_confirmed,
        state_test,
        args,
        "option_value_blended_score_trail_cutoff_qqq_spx_confirm",
    )
    ov_blended_ticker_validated = apply_ticker_validated_policies(
        selected_blended_score,
        state_test,
        args,
        ticker_policy_config,
        "option_value_blended_score_ticker_validated_trail_cutoff",
    )
    qqq_loose_exit_args = argparse.Namespace(**vars(args))
    qqq_loose_exit_args.hard_stop_pct = -0.70
    qqq_loose_exit_args.trail_activation_pct = 0.50
    qqq_loose_exit_args.trail_drawdown_pct = 0.15
    selected_blended_qqq = selected_blended_score[selected_blended_score["ticker"].astype(str) == "QQQ"].copy()
    ov_blended_qqq_loose_exit = simulate_trailing_exit(
        selected_blended_qqq,
        state_test,
        qqq_loose_exit_args,
        "option_value_blended_score_trail_cutoff_qqq_loose_exit",
    )
    ov_blended_non_qqq = ov_blended_score[ov_blended_score["ticker"].astype(str) != "QQQ"].copy()
    ov_blended_qqq_loose_exclude_midday = set_policy_name(
        pd.concat(
            [
                ov_blended_non_qqq,
                exclude_entry_time_window(ov_blended_qqq_loose_exit, "QQQ", "11:30", "12:30"),
            ],
            ignore_index=True,
        ),
        "option_value_blended_score_trail_cutoff_qqq_loose_exclude_1131_1230",
    )
    ov_blended_qqq_loose_early_only = set_policy_name(
        pd.concat(
            [
                ov_blended_non_qqq,
                keep_ticker_early_entries(ov_blended_qqq_loose_exit, "QQQ", "11:30"),
            ],
            ignore_index=True,
        ),
        "option_value_blended_score_trail_cutoff_qqq_loose_early_only",
    )

    policy_trades = {
        "fixed_delta_0.70_hard": fixed_070,
        "fixed_delta_0.70_learned_exit_5m": fixed_070_learned,
        "fixed_delta_0.70_trail_cutoff": fixed_070_trail,
        "option_value_hold180_select_hard": ov_hold_hard,
        "option_value_rule_select_hard": ov_rule_hard,
        "option_value_best_select_hard": ov_best_hard,
        "option_value_best_select_learned_exit_5m": ov_best_learned,
        "option_value_rule_select_learned_exit_5m": ov_rule_learned,
        "option_value_validated_score_trail_cutoff": ov_trail_score,
        "option_value_blended_score_trail_cutoff": ov_blended_score,
        "option_value_blended_score_ticker_validated_trail_cutoff": ov_blended_ticker_validated,
        "option_value_blended_score_trail_cutoff_spy_spx_confirm": ov_blended_spy_confirmed,
        "option_value_blended_score_trail_cutoff_qqq_spx_confirm": ov_blended_qqq_spx_confirmed,
        "option_value_blended_score_trail_cutoff_qqq_loose_exclude_1131_1230": ov_blended_qqq_loose_exclude_midday,
        "option_value_blended_score_trail_cutoff_qqq_loose_early_only": ov_blended_qqq_loose_early_only,
        "oracle_best_delta_hard": oracle_rule,
        "oracle_best_delta_oracle_exit": oracle_exit,
    }
    if bool(getattr(args, "enable_profit_lock_research", False)):
        policy_trades["option_value_blended_score_learned_profit_lock"] = simulate_learned_profit_lock_exit(
            selected_blended_score,
            state_test,
            final_model,
            final_scalers,
            market_features,
            option_features,
            dynamic_features,
            args,
            float(profit_lock_config.get("margin", 0.0)),
            float(profit_lock_config.get("profit_activation_pct", 0.50)),
            profit_lock_config.get("trail_activation_pct"),
            profit_lock_config.get("trail_drawdown_pct"),
            "option_value_blended_score_learned_profit_lock",
        )
    policy_results = {name: policy_payload(trades) for name, trades in policy_trades.items()}
    save_policy_outputs(output_dir, policy_results)
    test_pred.to_csv(output_dir / "test_candidate_predictions.csv", index=False)

    metadata = {
        "args": vars(args),
        "market_features": market_features,
        "option_features": option_features,
        "dynamic_features": dynamic_features,
        "train_candidates": int(len(train_candidates)),
        "test_candidates": int(len(test_candidates)),
        "state_rows": int(len(state_rows)),
        "train_state_rows": int(len(state_train)),
        "test_state_rows": int(len(state_test)),
        "val_months": sorted(val_months),
        "exit_margin": exit_margin,
        "exit_margin_grid": exit_payload,
        "trail_selector_config": trail_selector_config,
        "trail_selector_grid": trail_selector_payload,
        "ticker_policy_config": ticker_policy_config,
        "ticker_policy_grid": ticker_policy_payload,
        "profit_lock_config": profit_lock_config,
        "profit_lock_grid": profit_lock_payload,
        "blended_selector_config": {
            "score_base": str(args.blended_selector_score_base),
            "delta_bonus": float(args.blended_selector_delta_bonus),
            "min_delta_abs": None if float(args.blended_selector_min_delta) <= 0.0 else float(args.blended_selector_min_delta),
        },
        "policy_metrics": {
            name: {"overall": payload["overall"], "per_ticker": payload["per_ticker"]}
            for name, payload in policy_results.items()
        },
    }
    (output_dir / "metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    save_model_artifacts(model_dir, final_model, final_scalers, metadata)
    write_summary(output_dir, args, metadata, policy_results)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
