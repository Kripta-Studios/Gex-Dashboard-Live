#!/usr/bin/env python3
"""Frozen two-phase semantic-JEPA direction experiment on existing minute OHLC."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import lightgbm as lgb
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, Dataset


REPO_ROOT = Path(__file__).resolve().parents[2]
PREDECLARATION = REPO_ROOT / "research_papers/JEPA/DIRECTIONAL_SEMANTIC_JEPA_V1_PREDECLARATION.md"
DEFAULT_DATA_ROOT = Path("D:/ThetaData/data_underlying_derived")
DEFAULT_DEVELOPMENT_OUTPUT = (
    REPO_ROOT / "research_papers/JEPA/results/_diagnostics/directional_semantic_jepa_v1_development_202208_202512"
)
DEFAULT_EVALUATION_OUTPUT = (
    REPO_ROOT / "research_papers/JEPA/results/_diagnostics/directional_semantic_jepa_v1_evaluation_202601_20260715"
)

SOURCE_TICKERS = ("QQQ", "SPXW", "SPY")
REPORT_TICKER = {"QQQ": "QQQ", "SPXW": "SPX", "SPY": "SPY"}
START_DATE = "20220801"
DEVELOPMENT_END = "20251231"
EVALUATION_END = "20260715"
DECISION_TIME = "10:35"
ENTRY_TIME = "10:36"
EXIT_TIME = "13:36"
HOLD_MINUTES = 180
COST_BPS = 1.0
CONTEXT_LENGTH = 66
HORIZONS = (15, 60, 180)
PRETRAIN_END_MINUTES = tuple(range(65, 211, 15))  # 10:35 through 12:50.
RAW_CHANNELS_PER_TICKER = 6
RAW_CHANNELS = RAW_CHANNELS_PER_TICKER * len(SOURCE_TICKERS)
MASK_CHANNELS = 1 + len(SOURCE_TICKERS)
MODEL_INPUT_CHANNELS = RAW_CHANNELS + MASK_CHANNELS
HIDDEN_DIM = 64
LATENT_DIM = 24
MAX_EPOCHS = 25
BATCH_SIZE = 256
SEED = 20260716

# Frozen US equity early closes inside the source/development range. 2026 has
# no early close before the frozen 15 July endpoint.
HALF_DAYS = frozenset(
    {
        "20221125",
        "20230703",
        "20231124",
        "20240703",
        "20241129",
        "20241224",
        "20250703",
        "20251128",
        "20251224",
    }
)
INVALID_SOURCE_DAYS = frozenset({"20230605"})

TECH_PROFILE = "TECH_RESIDUAL"
SEMANTIC_PROFILE = "SEMANTIC_RESIDUAL"
SELECTABLE_PROFILES = (TECH_PROFILE, SEMANTIC_PROFILE)
CONTROL_PROFILES = ("ALWAYS_LONG", "PERSISTENCE_RIDGE")


@dataclass(frozen=True)
class Normalizer:
    median: tuple[float, ...]
    scale: tuple[float, ...]

    def transform(self, array: np.ndarray) -> np.ndarray:
        median = np.asarray(self.median, dtype=np.float32)
        scale = np.asarray(self.scale, dtype=np.float32)
        return np.clip((array.astype(np.float32) - median) / scale, -10.0, 10.0)


@dataclass(frozen=True)
class JepaTrainingResult:
    best_epoch: int
    validation_loss: float
    state_dict: dict
    history: list[dict]


class MarketWindowDataset(Dataset):
    def __init__(
        self,
        arrays: Sequence[np.ndarray],
        end_positions: Sequence[tuple[int, int]],
        normalizer: Normalizer,
    ) -> None:
        self.arrays = arrays
        self.end_positions = list(end_positions)
        self.normalizer = normalizer

    def __len__(self) -> int:
        return len(self.end_positions)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        sequence_id, end = self.end_positions[index]
        array = self.normalizer.transform(self.arrays[sequence_id])
        context = array[end - CONTEXT_LENGTH + 1 : end + 1]
        targets = np.stack(
            [array[end + horizon - CONTEXT_LENGTH + 1 : end + horizon + 1] for horizon in HORIZONS],
            axis=0,
        )
        zeros_context = np.zeros((CONTEXT_LENGTH, MASK_CHANNELS), dtype=np.float32)
        zeros_targets = np.zeros((len(HORIZONS), CONTEXT_LENGTH, MASK_CHANNELS), dtype=np.float32)
        return (
            torch.from_numpy(np.concatenate([context, zeros_context], axis=1)),
            torch.from_numpy(np.concatenate([targets, zeros_targets], axis=2)),
        )


class SequenceEncoder(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.gru = nn.GRU(MODEL_INPUT_CHANNELS, HIDDEN_DIM, batch_first=True)
        self.projection = nn.Sequential(nn.LayerNorm(HIDDEN_DIM), nn.Linear(HIDDEN_DIM, LATENT_DIM))

    def forward(self, sequence: torch.Tensor) -> torch.Tensor:
        _, hidden = self.gru(sequence)
        return self.projection(hidden[-1])


class SemanticJEPA(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.encoder = SequenceEncoder()
        self.predictors = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Linear(LATENT_DIM, HIDDEN_DIM),
                    nn.GELU(),
                    nn.Linear(HIDDEN_DIM, LATENT_DIM),
                )
                for _ in HORIZONS
            ]
        )

    def predict_latents(self, latent: torch.Tensor) -> torch.Tensor:
        return torch.stack([predictor(latent) for predictor in self.predictors], dim=1)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


def sha256_file(path: str | Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_date(value: object) -> str:
    digits = "".join(character for character in str(value) if character.isdigit())
    if len(digits) < 8:
        raise ValueError(f"invalid date: {value!r}")
    return digits[:8]


def discover_source_files(root: Path, end_date: str) -> pd.DataFrame:
    rows: list[dict] = []
    for ticker in SOURCE_TICKERS:
        for path in sorted((root / ticker).glob("*/*/*.parquet")):
            day = canonical_date(path.stem)
            if START_DATE <= day <= end_date:
                rows.append(
                    {
                        "ticker": ticker,
                        "trade_date": day,
                        "path": str(path.resolve()),
                        "size_bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )
    out = pd.DataFrame(rows).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    expected_dates: set[str] | None = None
    for ticker in SOURCE_TICKERS:
        dates = set(out.loc[out["ticker"].eq(ticker), "trade_date"])
        if expected_dates is None:
            expected_dates = dates
        elif dates != expected_dates:
            raise AssertionError(f"source session mismatch for {ticker}")
    if not expected_dates:
        raise AssertionError("no underlying source files found")
    if out.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("duplicate underlying source session")
    return out


def validate_bar_frame(frame: pd.DataFrame, ticker: str, day: str) -> pd.DataFrame:
    required = {"symbol", "date", "timestamp", "open", "high", "low", "close", "tick_count"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError(f"{ticker} {day}: missing columns {missing}")
    out = frame.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    for column in ("open", "high", "low", "close", "tick_count"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if out.empty or out["timestamp"].isna().any() or out["timestamp"].duplicated().any():
        raise AssertionError(f"{ticker} {day}: invalid timestamp grid")
    if not out["timestamp"].dt.strftime("%Y%m%d").eq(day).all():
        raise AssertionError(f"{ticker} {day}: timestamp date mismatch")
    if not out["date"].map(canonical_date).eq(day).all():
        raise AssertionError(f"{ticker} {day}: metadata date mismatch")
    if not out["symbol"].astype(str).str.upper().eq(ticker).all():
        raise AssertionError(f"{ticker} {day}: symbol mismatch")
    if not np.isfinite(out[["open", "high", "low", "close", "tick_count"]]).all().all():
        raise AssertionError(f"{ticker} {day}: non-finite OHLC/ticks")
    envelope = (
        (out["open"] > 0.0)
        & (out["close"] > 0.0)
        & (out["low"] <= out[["open", "close"]].min(axis=1) + 1e-9)
        & (out["high"] + 1e-9 >= out[["open", "close"]].max(axis=1))
        & (out["high"] >= out["low"])
        & (out["tick_count"] >= 0.0)
    )
    if not envelope.all():
        raise AssertionError(f"{ticker} {day}: OHLC envelope failure")
    out = out.sort_values("timestamp", kind="stable").set_index("timestamp", drop=False)
    expected_grid = pd.date_range(
        pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} 09:30"),
        pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} 16:00"),
        freq="min",
    )
    if not out.index.equals(expected_grid):
        raise AssertionError(f"{ticker} {day}: underlying grid is not exact 09:30-16:00")
    required_times = {DECISION_TIME, ENTRY_TIME, EXIT_TIME, "09:30", "10:29", "16:00"}
    observed = set(out["timestamp"].dt.strftime("%H:%M"))
    if not required_times.issubset(observed):
        raise AssertionError(f"{ticker} {day}: missing required clock {sorted(required_times - observed)}")
    return out


def load_sessions(inventory: pd.DataFrame) -> dict[str, dict[str, pd.DataFrame]]:
    sessions: dict[str, dict[str, pd.DataFrame]] = {}
    for row in inventory.itertuples(index=False):
        frame = pd.read_parquet(row.path)
        sessions.setdefault(str(row.trade_date), {})[str(row.ticker)] = validate_bar_frame(
            frame, str(row.ticker), str(row.trade_date)
        )
    for day, frames in sessions.items():
        if set(frames) != set(SOURCE_TICKERS):
            raise AssertionError(f"{day}: incomplete cross-market session")
        reference = frames[SOURCE_TICKERS[0]]["timestamp"].tolist()
        for ticker in SOURCE_TICKERS[1:]:
            if frames[ticker]["timestamp"].tolist() != reference:
                raise AssertionError(f"{day}: cross-market timestamp mismatch")
    return dict(sorted(sessions.items()))


def session_close(frame: pd.DataFrame, day: str) -> float:
    clock = "13:00" if day in HALF_DAYS else "16:00"
    return float(frame.loc[pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {clock}"), "close"])


def log_return_bps(end: float, start: float) -> float:
    if not (np.isfinite(end) and np.isfinite(start) and end > 0.0 and start > 0.0):
        raise ValueError("prices must be finite and positive")
    return float(math.log(end / start) * 10000.0)


def raw_market_array(frames: dict[str, pd.DataFrame]) -> np.ndarray:
    channels: list[np.ndarray] = []
    for ticker in SOURCE_TICKERS:
        frame = frames[ticker]
        open_ = frame["open"].to_numpy(dtype=np.float64)
        high = frame["high"].to_numpy(dtype=np.float64)
        low = frame["low"].to_numpy(dtype=np.float64)
        close = frame["close"].to_numpy(dtype=np.float64)
        tick = frame["tick_count"].to_numpy(dtype=np.float64)
        ret1 = np.zeros_like(close)
        ret1[1:] = np.log(close[1:] / close[:-1]) * 10000.0
        bar_range = (high - low) / close * 10000.0
        body = np.log(close / open_) * 10000.0
        close_location = np.divide(
            close - low,
            high - low,
            out=np.full_like(close, 0.5),
            where=(high - low) > 1e-12,
        ) - 0.5
        versus_open = np.log(close / open_[0]) * 10000.0
        channels.extend([ret1, bar_range, body, close_location, versus_open, np.log1p(tick)])
    array = np.stack(channels, axis=1).astype(np.float32)
    if array.shape[1] != RAW_CHANNELS or not np.isfinite(array).all():
        raise AssertionError("invalid semantic market array")
    return array


def fit_normalizer(arrays: Sequence[np.ndarray]) -> Normalizer:
    stacked = np.concatenate(arrays, axis=0).astype(np.float64)
    median = np.median(stacked, axis=0)
    q25 = np.quantile(stacked, 0.25, axis=0)
    q75 = np.quantile(stacked, 0.75, axis=0)
    scale = q75 - q25
    scale = np.where(scale > 1e-6, scale, 1.0)
    return Normalizer(tuple(median.tolist()), tuple(scale.tolist()))


def pretraining_positions(arrays: Sequence[np.ndarray]) -> list[tuple[int, int]]:
    positions: list[tuple[int, int]] = []
    for sequence_id, array in enumerate(arrays):
        for end in PRETRAIN_END_MINUTES:
            if end - CONTEXT_LENGTH + 1 >= 0 and end + max(HORIZONS) < len(array):
                positions.append((sequence_id, end))
    return positions


def corrupt_student_context(context: torch.Tensor) -> torch.Tensor:
    corrupted = context.clone()
    batch, length, _ = corrupted.shape
    for sample in range(batch):
        block = int(torch.randint(6, 19, (1,), device=corrupted.device).item())
        start = int(torch.randint(0, length - block + 1, (1,), device=corrupted.device).item())
        corrupted[sample, start : start + block, :RAW_CHANNELS] = 0.0
        corrupted[sample, start : start + block, RAW_CHANNELS] = 1.0
        if float(torch.rand((), device=corrupted.device)) < 0.25:
            ticker_index = int(torch.randint(0, len(SOURCE_TICKERS), (1,), device=corrupted.device).item())
            left = ticker_index * RAW_CHANNELS_PER_TICKER
            right = left + RAW_CHANNELS_PER_TICKER
            corrupted[sample, :, left:right] = 0.0
            corrupted[sample, :, RAW_CHANNELS + 1 + ticker_index] = 1.0
    channel_mask = torch.rand((batch, 1, RAW_CHANNELS), device=corrupted.device) < 0.10
    corrupted[:, :, :RAW_CHANNELS] = corrupted[:, :, :RAW_CHANNELS].masked_fill(channel_mask, 0.0)
    return corrupted


def variance_covariance_loss(latent: torch.Tensor) -> torch.Tensor:
    centered = latent - latent.mean(dim=0, keepdim=True)
    std = torch.sqrt(centered.var(dim=0, unbiased=False) + 1e-4)
    variance = F.relu(1.0 - std).mean()
    covariance = centered.T @ centered / max(1, len(latent) - 1)
    off_diagonal = covariance - torch.diag(torch.diag(covariance))
    return variance + 0.02 * off_diagonal.square().sum() / LATENT_DIM


def jepa_batch_loss(
    model: SemanticJEPA,
    teacher: SequenceEncoder,
    context: torch.Tensor,
    targets: torch.Tensor,
    *,
    corrupt: bool,
) -> tuple[torch.Tensor, dict[str, float]]:
    student_input = corrupt_student_context(context) if corrupt else context
    latent = model.encoder(student_input)
    predictions = model.predict_latents(latent)
    batch, horizons, length, channels = targets.shape
    with torch.no_grad():
        teacher_latent = teacher(targets.reshape(batch * horizons, length, channels)).reshape(
            batch, horizons, LATENT_DIM
        )
    prediction = F.smooth_l1_loss(predictions, teacher_latent)
    regularization = variance_covariance_loss(latent)
    total = prediction + 0.10 * regularization
    return total, {"total": float(total.detach()), "prediction": float(prediction.detach()), "regularization": float(regularization.detach())}


def update_teacher(teacher: nn.Module, student: nn.Module, decay: float = 0.99) -> None:
    with torch.no_grad():
        for teacher_parameter, student_parameter in zip(teacher.parameters(), student.parameters(), strict=True):
            teacher_parameter.mul_(decay).add_(student_parameter, alpha=1.0 - decay)


def evaluate_jepa_loss(
    model: SemanticJEPA,
    teacher: SequenceEncoder,
    loader: DataLoader,
    device: torch.device,
) -> float:
    model.eval()
    teacher.eval()
    total = 0.0
    rows = 0
    with torch.no_grad():
        for context, targets in loader:
            context = context.to(device=device, dtype=torch.float32)
            targets = targets.to(device=device, dtype=torch.float32)
            loss, _ = jepa_batch_loss(model, teacher, context, targets, corrupt=False)
            total += float(loss) * len(context)
            rows += len(context)
    return total / max(1, rows)


def train_jepa_selection(
    train_dataset: MarketWindowDataset,
    validation_dataset: MarketWindowDataset,
    device: torch.device,
) -> JepaTrainingResult:
    set_seed()
    model = SemanticJEPA().to(device)
    teacher = copy.deepcopy(model.encoder).to(device).eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    optimizer = torch.optim.AdamW(model.parameters(), lr=7e-4, weight_decay=0.02)
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    validation_loader = DataLoader(validation_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    best_loss = math.inf
    best_epoch = 0
    best_state: dict | None = None
    history: list[dict] = []
    bad_epochs = 0
    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        train_total = 0.0
        train_rows = 0
        for context, targets in train_loader:
            context = context.to(device=device, dtype=torch.float32)
            targets = targets.to(device=device, dtype=torch.float32)
            loss, _ = jepa_batch_loss(model, teacher, context, targets, corrupt=True)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            update_teacher(teacher, model.encoder)
            train_total += float(loss.detach()) * len(context)
            train_rows += len(context)
        validation_loss = evaluate_jepa_loss(model, teacher, validation_loader, device)
        row = {
            "epoch": epoch,
            "train_loss": train_total / max(1, train_rows),
            "validation_loss": validation_loss,
        }
        history.append(row)
        print(json.dumps({"phase": "jepa_selection", **row}), flush=True)
        if validation_loss < best_loss - 1e-5:
            best_loss = validation_loss
            best_epoch = epoch
            best_state = {
                "model": copy.deepcopy(model.state_dict()),
                "teacher": copy.deepcopy(teacher.state_dict()),
            }
            bad_epochs = 0
        else:
            bad_epochs += 1
            if bad_epochs >= 5:
                break
    if best_state is None or best_epoch <= 0:
        raise AssertionError("JEPA selection did not produce a checkpoint")
    return JepaTrainingResult(best_epoch, float(best_loss), best_state, history)


def final_fit_jepa(dataset: MarketWindowDataset, epochs: int, device: torch.device) -> dict:
    set_seed()
    model = SemanticJEPA().to(device)
    teacher = copy.deepcopy(model.encoder).to(device).eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    optimizer = torch.optim.AdamW(model.parameters(), lr=7e-4, weight_decay=0.02)
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    for epoch in range(1, epochs + 1):
        model.train()
        running = 0.0
        rows = 0
        for context, targets in loader:
            context = context.to(device=device, dtype=torch.float32)
            targets = targets.to(device=device, dtype=torch.float32)
            loss, _ = jepa_batch_loss(model, teacher, context, targets, corrupt=True)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            update_teacher(teacher, model.encoder)
            running += float(loss.detach()) * len(context)
            rows += len(context)
        print(json.dumps({"phase": "jepa_final_fit", "epoch": epoch, "loss": running / max(1, rows)}), flush=True)
    return {"model": model.state_dict(), "teacher": teacher.state_dict()}


def _window_metrics(frame: pd.DataFrame, end_position: int, horizon: int) -> dict[str, float]:
    start = end_position - horizon + 1
    if start < 0:
        raise AssertionError("technical window begins before the session")
    window = frame.iloc[start : end_position + 1]
    close = window["close"].to_numpy(dtype=np.float64)
    one_minute = np.diff(np.log(close)) * 10000.0
    high = float(window["high"].max())
    low = float(window["low"].min())
    last = float(close[-1])
    first_open = float(window["open"].iloc[0])
    close_location = (last - low) / max(1e-9, high - low)
    return {
        "ret": log_return_bps(last, first_open),
        "rv": float(np.std(one_minute, ddof=0)) if len(one_minute) else 0.0,
        "range": float((high - low) / last * 10000.0),
        "close_location": float(close_location),
    }


def build_technical_row(
    day: str,
    frames: dict[str, pd.DataFrame],
    previous_day: str,
    previous_frames: dict[str, pd.DataFrame],
    target_ticker: str,
) -> tuple[dict[str, float | str], list[str]]:
    decision_timestamp = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {DECISION_TIME}")
    entry_timestamp = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {ENTRY_TIME}")
    exit_timestamp = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {EXIT_TIME}")
    row: dict[str, float | str] = {
        "ticker": REPORT_TICKER[target_ticker],
        "source_ticker": target_ticker,
        "trade_date": day,
        "month": day[:6],
        "decision_time": DECISION_TIME,
        "entry_time": ENTRY_TIME,
        "exit_time": EXIT_TIME,
        "hold_minutes": HOLD_MINUTES,
    }
    technical_features: list[str] = []
    cross_returns: dict[int, list[float]] = {5: [], 15: [], 30: [], 60: []}
    for ticker in SOURCE_TICKERS:
        frame = frames[ticker]
        position = int(frame.index.get_loc(decision_timestamp))
        prefix = ticker.lower()
        for horizon in (5, 15, 30, 60):
            metrics = _window_metrics(frame, position, horizon)
            for metric, value in metrics.items():
                name = f"{prefix}_{metric}_{horizon}m"
                row[name] = value
                technical_features.append(name)
            cross_returns[horizon].append(float(metrics["ret"]))
        close_now = float(frame.loc[decision_timestamp, "close"])
        open_today = float(frame.iloc[0]["open"])
        since_open_name = f"{prefix}_ret_since_open"
        row[since_open_name] = log_return_bps(close_now, open_today)
        technical_features.append(since_open_name)

        previous = previous_frames[ticker]
        previous_close = session_close(previous, previous_day)
        gap_name = f"{prefix}_gap_bps"
        row[gap_name] = log_return_bps(open_today, previous_close)
        technical_features.append(gap_name)
        previous_clock = "13:00" if previous_day in HALF_DAYS else "16:00"
        previous_end = pd.Timestamp(
            f"{previous_day[:4]}-{previous_day[4:6]}-{previous_day[6:]} {previous_clock}"
        )
        previous_rth = previous.loc[:previous_end]
        previous_high = float(previous_rth["high"].max())
        previous_low = float(previous_rth["low"].min())
        previous_open = float(previous_rth.iloc[0]["open"])
        previous_return_name = f"{prefix}_previous_return"
        previous_range_name = f"{prefix}_previous_range"
        previous_location_name = f"{prefix}_previous_close_location"
        row[previous_return_name] = log_return_bps(previous_close, previous_open)
        row[previous_range_name] = (previous_high - previous_low) / previous_close * 10000.0
        row[previous_location_name] = (previous_close - previous_low) / max(1e-9, previous_high - previous_low)
        technical_features.extend([previous_return_name, previous_range_name, previous_location_name])

        ib_start = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} 09:30")
        ib_end = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} 10:29")
        ib = frame.loc[ib_start:ib_end]
        if len(ib) != 60:
            raise AssertionError(f"{ticker} {day}: Initial Balance does not contain 60 bars")
        ib_high = float(ib["high"].max())
        ib_low = float(ib["low"].min())
        ib_range = ib_high - ib_low
        ib_feature_values = {
            f"{prefix}_ib_range_bps": ib_range / close_now * 10000.0,
            f"{prefix}_dist_ib_high_bps": (close_now - ib_high) / close_now * 10000.0,
            f"{prefix}_dist_ib_low_bps": (close_now - ib_low) / close_now * 10000.0,
            f"{prefix}_ib_position": (close_now - ib_low) / max(1e-9, ib_range),
        }
        row.update(ib_feature_values)
        technical_features.extend(ib_feature_values)
        for multiplier in (1.272, 1.618, 2.0, 2.618):
            upper = ib_low + multiplier * ib_range
            lower = ib_high - multiplier * ib_range
            tag = str(multiplier).replace(".", "p")
            upper_name = f"{prefix}_dist_fib_{tag}_up_bps"
            lower_name = f"{prefix}_dist_fib_{tag}_down_bps"
            row[upper_name] = (close_now - upper) / close_now * 10000.0
            row[lower_name] = (close_now - lower) / close_now * 10000.0
            technical_features.extend([upper_name, lower_name])

    for horizon, values in cross_returns.items():
        dispersion_name = f"cross_return_dispersion_{horizon}m"
        row[dispersion_name] = float(np.std(values, ddof=0))
        technical_features.append(dispersion_name)
    day_of_week = pd.Timestamp(day).dayofweek
    row["dow_sin"] = math.sin(2.0 * math.pi * day_of_week / 5.0)
    row["dow_cos"] = math.cos(2.0 * math.pi * day_of_week / 5.0)
    technical_features.extend(["dow_sin", "dow_cos"])

    target_frame = frames[target_ticker]
    entry_open = float(target_frame.loc[entry_timestamp, "open"])
    exit_open = float(target_frame.loc[exit_timestamp, "open"])
    row["entry_spot"] = entry_open
    row["exit_spot"] = exit_open
    row["future_return_bps"] = log_return_bps(exit_open, entry_open)
    return row, technical_features


def padded_context(normalized: np.ndarray, end: int) -> np.ndarray:
    start = end - CONTEXT_LENGTH + 1
    if start < 0:
        pad = np.repeat(normalized[[0]], -start, axis=0)
        context = np.concatenate([pad, normalized[: end + 1]], axis=0)
    else:
        context = normalized[start : end + 1]
    if len(context) != CONTEXT_LENGTH:
        raise AssertionError("semantic inference context length mismatch")
    return np.concatenate([context, np.zeros((CONTEXT_LENGTH, MASK_CHANNELS), dtype=np.float32)], axis=1)


def semantic_feature_values(
    model: SemanticJEPA,
    array: np.ndarray,
    normalizer: Normalizer,
    device: torch.device,
) -> dict[str, float]:
    normalized = normalizer.transform(array)
    current = torch.from_numpy(padded_context(normalized, 65)).unsqueeze(0).to(device)
    previous = torch.from_numpy(padded_context(normalized, 60)).unsqueeze(0).to(device)
    model.eval()
    with torch.no_grad():
        latent = model.encoder(current.float())
        previous_latent = model.encoder(previous.float())
        predicted = model.predict_latents(latent)
    z = latent[0].cpu().numpy()
    dz = (latent - previous_latent)[0].cpu().numpy()
    predicted_np = predicted[0].cpu().numpy()
    values: dict[str, float] = {}
    for index, value in enumerate(z):
        values[f"jepa_z_{index:02d}"] = float(value)
    for index, value in enumerate(dz):
        values[f"jepa_dz_{index:02d}"] = float(value)
    for index, horizon in enumerate(HORIZONS):
        displacement = predicted_np[index] - z
        values[f"jepa_pred_displacement_{horizon}m"] = float(np.linalg.norm(displacement))
        denominator = max(1e-9, float(np.linalg.norm(predicted_np[index]) * np.linalg.norm(z)))
        values[f"jepa_pred_cosine_{horizon}m"] = float(np.dot(predicted_np[index], z) / denominator)
    return values


def build_daily_frame(
    sessions: dict[str, dict[str, pd.DataFrame]],
    arrays_by_date: dict[str, np.ndarray],
    model: SemanticJEPA,
    normalizer: Normalizer,
    device: torch.device,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    dates = sorted(sessions)
    rows: list[dict] = []
    technical_features: list[str] | None = None
    semantic_features: list[str] | None = None
    for index, day in enumerate(dates):
        if index == 0 or day in HALF_DAYS:
            continue
        previous_day = dates[index - 1]
        semantic = semantic_feature_values(model, arrays_by_date[day], normalizer, device)
        if semantic_features is None:
            semantic_features = list(semantic)
        for ticker in SOURCE_TICKERS:
            row, features = build_technical_row(
                day,
                sessions[day],
                previous_day,
                sessions[previous_day],
                ticker,
            )
            if technical_features is None:
                technical_features = features
            elif features != technical_features:
                raise AssertionError("technical feature order changed")
            row.update(semantic)
            rows.append(row)
    frame = pd.DataFrame(rows).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    if frame.empty or technical_features is None or semantic_features is None:
        raise AssertionError("daily feature frame is empty")
    feature_columns = technical_features + semantic_features
    if frame[feature_columns].isna().any().any() or not np.isfinite(frame[feature_columns]).all().all():
        raise AssertionError("daily features contain non-finite values")
    if frame.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("duplicate daily market sample")
    return frame, technical_features, semantic_features


def profit_factor(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    gross_profit = float(array[array > 0.0].sum())
    gross_loss = float(-array[array < 0.0].sum())
    if gross_loss == 0.0:
        return 1.0e12 if gross_profit > 0.0 else 0.0
    return gross_profit / gross_loss


def summarize_trades(frame: pd.DataFrame) -> dict:
    pnl = frame["net_bps"].to_numpy(dtype=np.float64) if not frame.empty else np.array([], dtype=np.float64)
    return {
        "trades": int(len(frame)),
        "win_rate": float(np.mean(pnl > 0.0)) if len(pnl) else 0.0,
        "profit_factor": profit_factor(pnl),
        "net_bps": float(pnl.sum()),
    }


def fit_residual_predictor(
    train: pd.DataFrame,
    test: pd.DataFrame,
    technical_features: list[str],
    model_features: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    persistence_features = [
        feature
        for feature in technical_features
        if feature.endswith(("_ret_5m", "_ret_15m", "_ret_30m", "_ret_60m", "_ret_since_open"))
    ]
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    ridge.fit(train[persistence_features], train["future_return_bps"])
    train_persistence = ridge.predict(train[persistence_features])
    test_persistence = ridge.predict(test[persistence_features])
    residual = train["future_return_bps"].to_numpy(dtype=np.float64) - train_persistence
    model = lgb.LGBMRegressor(
        objective="huber",
        n_estimators=240,
        learning_rate=0.025,
        num_leaves=7,
        max_depth=3,
        min_child_samples=40,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        reg_alpha=0.05,
        reg_lambda=0.5,
        random_state=SEED,
        n_jobs=8,
        deterministic=True,
        force_col_wise=True,
        verbosity=-1,
    )
    model.fit(train[model_features], residual)
    prediction = test_persistence + model.predict(test[model_features])
    return np.asarray(prediction, dtype=np.float64), np.asarray(test_persistence, dtype=np.float64)


def predictions_to_trades(test: pd.DataFrame, prediction: np.ndarray, profile_id: str) -> pd.DataFrame:
    if len(test) != len(prediction):
        raise AssertionError("prediction length mismatch")
    output = test[
        [
            "ticker",
            "source_ticker",
            "trade_date",
            "month",
            "decision_time",
            "entry_time",
            "exit_time",
            "hold_minutes",
            "entry_spot",
            "exit_spot",
            "future_return_bps",
        ]
    ].copy()
    output["profile_id"] = profile_id
    output["predicted_return_bps"] = prediction
    output["side"] = np.where(prediction >= 0.0, "LONG", "SHORT")
    signed = np.where(prediction >= 0.0, output["future_return_bps"], -output["future_return_bps"])
    output["gross_bps"] = signed
    output["net_bps"] = signed - COST_BPS
    return output


def run_walkforward(
    daily: pd.DataFrame,
    months: list[str],
    technical_features: list[str],
    semantic_features: list[str],
    profiles_by_ticker: dict[str, str] | None = None,
    include_controls: bool = False,
) -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    for ticker in sorted(daily["ticker"].unique()):
        ticker_frame = daily.loc[daily["ticker"].eq(ticker)].copy()
        requested = (
            [profiles_by_ticker[ticker]]
            if profiles_by_ticker is not None
            else list(SELECTABLE_PROFILES)
        )
        for month in months:
            train = ticker_frame.loc[ticker_frame["month"] < month].copy()
            test = ticker_frame.loc[ticker_frame["month"].eq(month)].copy()
            if test.empty:
                continue
            if len(train) < 400:
                raise AssertionError(f"{ticker} {month}: insufficient chronological training rows")
            persistence_prediction: np.ndarray | None = None
            for profile_id in requested:
                model_features = technical_features if profile_id == TECH_PROFILE else technical_features + semantic_features
                prediction, persistence = fit_residual_predictor(train, test, technical_features, model_features)
                outputs.append(predictions_to_trades(test, prediction, profile_id))
                persistence_prediction = persistence
            if include_controls:
                if persistence_prediction is None:
                    _, persistence_prediction = fit_residual_predictor(
                        train, test, technical_features, technical_features
                    )
                outputs.append(predictions_to_trades(test, persistence_prediction, "PERSISTENCE_RIDGE"))
                outputs.append(predictions_to_trades(test, np.ones(len(test)), "ALWAYS_LONG"))
    if not outputs:
        raise AssertionError("walk-forward produced no trades")
    return pd.concat(outputs, ignore_index=True).sort_values(
        ["ticker", "trade_date", "profile_id"], kind="stable"
    ).reset_index(drop=True)


def monthly_metrics(trades: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for (ticker, profile_id, month), group in trades.groupby(["ticker", "profile_id", "month"], sort=True):
        rows.append({"ticker": ticker, "profile_id": profile_id, "month": month, **summarize_trades(group)})
    return pd.DataFrame(rows)


def select_profiles(trades: pd.DataFrame) -> tuple[dict[str, str], pd.DataFrame]:
    monthly = monthly_metrics(trades.loc[trades["profile_id"].isin(SELECTABLE_PROFILES)])
    selections: dict[str, str] = {}
    ranking_rows: list[dict] = []
    for ticker in sorted(monthly["ticker"].unique()):
        candidates: list[dict] = []
        for profile_id in SELECTABLE_PROFILES:
            profile_monthly = monthly.loc[
                monthly["ticker"].eq(ticker) & monthly["profile_id"].eq(profile_id)
            ].sort_values("month")
            profile_trades = trades.loc[
                trades["ticker"].eq(ticker) & trades["profile_id"].eq(profile_id)
            ]
            if len(profile_monthly) != 12 or int(profile_monthly["trades"].min()) < 13:
                raise AssertionError(f"{ticker} {profile_id}: incomplete 2025 development coverage")
            candidate = {
                "ticker": ticker,
                "profile_id": profile_id,
                "positive_months": int((profile_monthly["net_bps"] > 0.0).sum()),
                "monthly_net_q25": float(profile_monthly["net_bps"].quantile(0.25)),
                "aggregate_profit_factor": profit_factor(profile_trades["net_bps"]),
                "aggregate_win_rate": float((profile_trades["net_bps"] > 0.0).mean()),
                "aggregate_net_bps": float(profile_trades["net_bps"].sum()),
                "min_month_trades": int(profile_monthly["trades"].min()),
            }
            candidates.append(candidate)
        candidates.sort(
            key=lambda item: (
                -item["positive_months"],
                -item["monthly_net_q25"],
                -item["aggregate_profit_factor"],
                item["profile_id"],
            )
        )
        for rank, candidate in enumerate(candidates, start=1):
            candidate["rank"] = rank
            candidate["selected"] = rank == 1
            ranking_rows.append(candidate)
        selections[ticker] = candidates[0]["profile_id"]
    return selections, pd.DataFrame(ranking_rows)


def evaluate_complete_month_gate(trades: pd.DataFrame, months: list[str]) -> dict:
    ticker_metrics: dict[str, dict] = {}
    monthly = monthly_metrics(trades)
    for ticker in sorted(trades["ticker"].unique()):
        ticker_trades = trades.loc[trades["ticker"].eq(ticker) & trades["month"].isin(months)]
        ticker_monthly = monthly.loc[monthly["ticker"].eq(ticker) & monthly["month"].isin(months)]
        if len(ticker_monthly) != len(months):
            raise AssertionError(f"{ticker}: incomplete evaluation months")
        summary = summarize_trades(ticker_trades)
        minimum = int(ticker_monthly["trades"].min())
        positives = int((ticker_monthly["net_bps"] > 0.0).sum())
        passed = (
            summary["win_rate"] > 0.45
            and summary["profit_factor"] > 1.20
            and minimum > 12
            and positives == len(months)
        )
        ticker_metrics[ticker] = {
            **summary,
            "min_month_trades": minimum,
            "positive_months": positives,
            "evaluated_months": len(months),
            "gate_pass": passed,
        }
    return {
        "ticker_metrics": ticker_metrics,
        "joint_gate_pass": all(metrics["gate_pass"] for metrics in ticker_metrics.values()),
    }


def _arrays_for_dates(
    sessions: dict[str, dict[str, pd.DataFrame]],
    dates: Iterable[str],
) -> tuple[list[np.ndarray], dict[str, np.ndarray]]:
    mapping = {day: raw_market_array(sessions[day]) for day in dates if day not in HALF_DAYS}
    return list(mapping.values()), mapping


def _model_from_state(state: dict, device: torch.device) -> SemanticJEPA:
    model = SemanticJEPA().to(device)
    model.load_state_dict(state["model"])
    model.eval()
    return model


def _source_inventory_digest(inventory: pd.DataFrame) -> str:
    payload = inventory[["ticker", "trade_date", "path", "size_bytes", "sha256"]].to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _common_provenance(inventory: pd.DataFrame) -> dict:
    return {
        "schema": "directional_semantic_jepa_v1_provenance",
        "created_at_utc": utc_now(),
        "predeclaration_path": str(PREDECLARATION.relative_to(REPO_ROOT)),
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "runner_path": str(Path(__file__).resolve().relative_to(REPO_ROOT)),
        "runner_sha256": sha256_file(__file__),
        "source_inventory_rows": int(len(inventory)),
        "source_inventory_sha256": _source_inventory_digest(inventory),
        "source_kind": "underlying_derived_minute_ohlc",
        "option_decay_used": False,
        "future_fills_used": False,
        "production_modified": False,
    }


def run_development(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable development output exists: {output}")
    inventory = discover_source_files(Path(args.data_root), DEVELOPMENT_END)
    counts = inventory.groupby("ticker").size().to_dict()
    if counts != {ticker: 859 for ticker in SOURCE_TICKERS}:
        raise AssertionError(f"development source census mismatch: {counts}")
    usable_inventory = inventory.loc[~inventory["trade_date"].isin(INVALID_SOURCE_DAYS)].copy()
    sessions = load_sessions(usable_inventory)
    dates = sorted(sessions)
    train_dates = [day for day in dates if day <= "20241231" and day not in HALF_DAYS]
    validation_dates = [day for day in dates if day.startswith("2025") and day not in HALF_DAYS]
    train_arrays, train_mapping = _arrays_for_dates(sessions, train_dates)
    validation_arrays, validation_mapping = _arrays_for_dates(sessions, validation_dates)
    normalizer = fit_normalizer(train_arrays)
    train_dataset = MarketWindowDataset(train_arrays, pretraining_positions(train_arrays), normalizer)
    validation_dataset = MarketWindowDataset(
        validation_arrays, pretraining_positions(validation_arrays), normalizer
    )
    device = torch.device(args.device)
    selection = train_jepa_selection(train_dataset, validation_dataset, device)

    all_arrays = train_arrays + validation_arrays
    final_normalizer = fit_normalizer(all_arrays)
    all_dataset = MarketWindowDataset(all_arrays, pretraining_positions(all_arrays), final_normalizer)
    final_state = final_fit_jepa(all_dataset, selection.best_epoch, device)
    model = _model_from_state(final_state, device)
    arrays_by_date = {**train_mapping, **validation_mapping}
    daily, technical_features, semantic_features = build_daily_frame(
        sessions, arrays_by_date, model, final_normalizer, device
    )
    development_months = [f"2025{month:02d}" for month in range(1, 13)]
    trades = run_walkforward(
        daily,
        development_months,
        technical_features,
        semantic_features,
        include_controls=True,
    )
    selections, ranking = select_profiles(trades)
    monthly = monthly_metrics(trades)
    metrics = {
        "schema": "directional_semantic_jepa_v1_development_metrics",
        "status": "PASS_DEVELOPMENT_FREEZE",
        "created_at_utc": utc_now(),
        "scope": {"start_date": START_DATE, "end_date": DEVELOPMENT_END, "development_months": development_months},
        "source_sessions_by_ticker": counts,
        "excluded_source_days": sorted(INVALID_SOURCE_DAYS),
        "daily_rows": int(len(daily)),
        "technical_feature_count": len(technical_features),
        "semantic_feature_count": len(semantic_features),
        "jepa": {
            "train_dates": len(train_dates),
            "validation_dates": len(validation_dates),
            "train_windows": len(train_dataset),
            "validation_windows": len(validation_dataset),
            "final_windows": len(all_dataset),
            "best_epoch": selection.best_epoch,
            "best_validation_loss": selection.validation_loss,
        },
        "selected_profiles": selections,
        "holdout_2026_used": False,
        "production_modified": False,
    }
    provenance = _common_provenance(inventory)
    output.mkdir(parents=True, exist_ok=False)
    inventory.to_csv(output / "source_inventory.csv", index=False, lineterminator="\n")
    pd.DataFrame(selection.history).to_csv(output / "jepa_training_history.csv", index=False)
    trades.to_parquet(output / "development_trade_ledger.parquet", index=False)
    monthly.to_csv(output / "development_monthly_metrics.csv", index=False)
    ranking.to_csv(output / "profile_ranking.csv", index=False)
    (output / "technical_features.json").write_text(json.dumps(technical_features, indent=2), encoding="utf-8")
    (output / "semantic_features.json").write_text(json.dumps(semantic_features, indent=2), encoding="utf-8")
    (output / "normalizer.json").write_text(json.dumps(asdict(final_normalizer), indent=2), encoding="utf-8")
    torch.save(final_state, output / "semantic_jepa.pt")
    provenance["semantic_jepa_sha256"] = sha256_file(output / "semantic_jepa.pt")
    provenance["normalizer_sha256"] = sha256_file(output / "normalizer.json")
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    metrics["provenance_sha256"] = sha256_file(output / "provenance.json")
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
    return metrics


def _load_development(development_dir: Path, device: torch.device) -> tuple[dict, dict, Normalizer, SemanticJEPA, list[str], list[str]]:
    metrics = json.loads((development_dir / "metrics.json").read_text(encoding="utf-8"))
    provenance = json.loads((development_dir / "provenance.json").read_text(encoding="utf-8"))
    if metrics.get("schema") != "directional_semantic_jepa_v1_development_metrics" or metrics.get("status") != "PASS_DEVELOPMENT_FREEZE":
        raise AssertionError("invalid frozen development metrics")
    if bool(metrics.get("holdout_2026_used", True)) or bool(metrics.get("production_modified", True)):
        raise AssertionError("development freeze used holdout or modified production")
    if provenance.get("predeclaration_sha256") != sha256_file(PREDECLARATION):
        raise AssertionError("predeclaration changed after development freeze")
    if provenance.get("runner_sha256") != sha256_file(__file__):
        raise AssertionError("runner changed after development freeze")
    if provenance.get("semantic_jepa_sha256") != sha256_file(development_dir / "semantic_jepa.pt"):
        raise AssertionError("semantic JEPA artifact hash mismatch")
    if provenance.get("normalizer_sha256") != sha256_file(development_dir / "normalizer.json"):
        raise AssertionError("normalizer hash mismatch")
    normalizer_payload = json.loads((development_dir / "normalizer.json").read_text(encoding="utf-8"))
    normalizer = Normalizer(tuple(normalizer_payload["median"]), tuple(normalizer_payload["scale"]))
    state = torch.load(development_dir / "semantic_jepa.pt", map_location=device, weights_only=True)
    model = _model_from_state(state, device)
    technical_features = json.loads((development_dir / "technical_features.json").read_text(encoding="utf-8"))
    semantic_features = json.loads((development_dir / "semantic_features.json").read_text(encoding="utf-8"))
    return metrics, provenance, normalizer, model, technical_features, semantic_features


def _verify_development_sources(inventory: pd.DataFrame, development_dir: Path, provenance: dict) -> None:
    frozen = pd.read_csv(development_dir / "source_inventory.csv", dtype={"trade_date": str})
    current = inventory.loc[inventory["trade_date"] <= DEVELOPMENT_END].reset_index(drop=True)
    columns = ["ticker", "trade_date", "path", "size_bytes", "sha256"]
    if not frozen[columns].astype(str).equals(current[columns].astype(str)):
        raise AssertionError("pre-2026 source inventory changed after development freeze")
    if provenance.get("source_inventory_sha256") != _source_inventory_digest(current):
        raise AssertionError("pre-2026 source inventory digest mismatch")


def run_evaluation(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable evaluation output exists: {output}")
    development_dir = Path(args.development_dir)
    device = torch.device(args.device)
    development, frozen_provenance, normalizer, model, technical_features, semantic_features = _load_development(
        development_dir, device
    )
    inventory = discover_source_files(Path(args.data_root), EVALUATION_END)
    counts = inventory.groupby("ticker").size().to_dict()
    if counts != {ticker: 992 for ticker in SOURCE_TICKERS}:
        raise AssertionError(f"evaluation source census mismatch: {counts}")
    _verify_development_sources(inventory, development_dir, frozen_provenance)
    usable_inventory = inventory.loc[~inventory["trade_date"].isin(INVALID_SOURCE_DAYS)].copy()
    sessions = load_sessions(usable_inventory)
    arrays, arrays_by_date = _arrays_for_dates(sessions, sorted(sessions))
    if not arrays:
        raise AssertionError("no semantic arrays for evaluation")
    daily, observed_technical, observed_semantic = build_daily_frame(
        sessions, arrays_by_date, model, normalizer, device
    )
    if observed_technical != technical_features or observed_semantic != semantic_features:
        raise AssertionError("evaluation feature contract differs from development")
    evaluation_months = [f"2026{month:02d}" for month in range(1, 8)]
    selected_profiles = {str(key): str(value) for key, value in development["selected_profiles"].items()}
    trades = run_walkforward(
        daily,
        evaluation_months,
        technical_features,
        semantic_features,
        profiles_by_ticker=selected_profiles,
        include_controls=False,
    )
    complete_months = evaluation_months[:6]
    gate = evaluate_complete_month_gate(trades, complete_months)
    monthly = monthly_metrics(trades)
    july = monthly.loc[monthly["month"].eq("202607")].copy()
    july["month"] = "202607_MTD"
    metrics = {
        "schema": "directional_semantic_jepa_v1_evaluation_metrics",
        "status": "PASS_2026_GATE" if gate["joint_gate_pass"] else "CLOSED_2026_GATE",
        "created_at_utc": utc_now(),
        "scope": {
            "start_date": "20260101",
            "end_date": EVALUATION_END,
            "complete_months": complete_months,
            "july_status": "MTD",
        },
        "selected_profiles": selected_profiles,
        "source_sessions_by_ticker": counts,
        "excluded_source_days": sorted(INVALID_SOURCE_DAYS),
        "execution": {
            "decision_time": DECISION_TIME,
            "entry_time": ENTRY_TIME,
            "exit_time": EXIT_TIME,
            "hold_minutes": HOLD_MINUTES,
            "cost_bps": COST_BPS,
            "overlap_count": 0,
            "fill_kind": "underlying_open_spot_proxy_not_futures_fill",
        },
        **gate,
        "july_mtd": july.to_dict("records"),
        "production_modified": False,
    }
    provenance = _common_provenance(inventory)
    provenance.update(
        {
            "development_metrics_sha256": sha256_file(development_dir / "metrics.json"),
            "development_provenance_sha256": sha256_file(development_dir / "provenance.json"),
            "development_model_sha256": sha256_file(development_dir / "semantic_jepa.pt"),
            "holdout_2026_used_for_selection": False,
            "futures_fills_validated": False,
        }
    )
    output.mkdir(parents=True, exist_ok=False)
    inventory.to_csv(output / "source_inventory.csv", index=False, lineterminator="\n")
    trades.to_parquet(output / "trade_ledger.parquet", index=False)
    monthly.to_csv(output / "monthly_metrics.csv", index=False)
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    metrics["provenance_sha256"] = sha256_file(output / "provenance.json")
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("development", "evaluation"), required=True)
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--development-dir", default=str(DEFAULT_DEVELOPMENT_OUTPUT))
    parser.add_argument("--output", default="")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()
    if not args.output:
        args.output = str(DEFAULT_DEVELOPMENT_OUTPUT if args.phase == "development" else DEFAULT_EVALUATION_OUTPUT)
    return args


def main() -> int:
    args = parse_args()
    if args.phase == "development":
        run_development(args)
    else:
        run_evaluation(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
