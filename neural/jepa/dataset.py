from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from neural.jepa.features import load_base_feature_columns


SORT_COLUMNS_CANDIDATES = ("timestamp", "time")


@dataclass
class RobustNormalizer:
    feature_names: list[str]
    median: np.ndarray
    iqr: np.ndarray
    clip: float = 10.0

    @classmethod
    def fit(cls, df: pd.DataFrame, feature_names: Sequence[str], clip: float = 10.0) -> "RobustNormalizer":
        values = df[list(feature_names)].replace([np.inf, -np.inf], np.nan)
        median = values.median(axis=0).astype(np.float32).values
        q25 = values.quantile(0.25, axis=0).astype(np.float32).values
        q75 = values.quantile(0.75, axis=0).astype(np.float32).values
        iqr = q75 - q25
        iqr = np.where(np.isfinite(iqr) & (np.abs(iqr) > 1e-6), iqr, 1.0).astype(np.float32)
        median = np.where(np.isfinite(median), median, 0.0).astype(np.float32)
        return cls(list(feature_names), median, iqr, float(clip))

    def transform_frame(self, df: pd.DataFrame) -> np.ndarray:
        values = df[self.feature_names].values.astype(np.float32, copy=False)
        values = np.nan_to_num(values, nan=0.0, posinf=self.clip, neginf=-self.clip)
        out = (values - self.median.reshape(1, -1)) / self.iqr.reshape(1, -1)
        out = np.nan_to_num(out, nan=0.0, posinf=self.clip, neginf=-self.clip)
        return np.clip(out, -self.clip, self.clip).astype(np.float32, copy=False)

    def to_dict(self) -> dict:
        return {
            "feature_names": self.feature_names,
            "kind": "global",
            "median": self.median.tolist(),
            "iqr": self.iqr.tolist(),
            "clip": self.clip,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RobustNormalizer":
        if data.get("kind") == "ticker":
            return TickerRobustNormalizer.from_dict(data)
        return cls(
            feature_names=[str(x) for x in data["feature_names"]],
            median=np.asarray(data["median"], dtype=np.float32),
            iqr=np.asarray(data["iqr"], dtype=np.float32),
            clip=float(data.get("clip", 10.0)),
        )

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "RobustNormalizer":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

@dataclass
class TickerRobustNormalizer(RobustNormalizer):
    """Causal robust scaling with independent statistics per underlying ticker."""

    ticker_median: dict[str, np.ndarray] | None = None
    ticker_iqr: dict[str, np.ndarray] | None = None
    ticker_column: str = "ticker"

    @classmethod
    def fit(
        cls,
        df: pd.DataFrame,
        feature_names: Sequence[str],
        clip: float = 10.0,
        ticker_column: str = "ticker",
    ) -> "TickerRobustNormalizer":
        global_normalizer = RobustNormalizer.fit(df, feature_names, clip=clip)
        ticker_median: dict[str, np.ndarray] = {}
        ticker_iqr: dict[str, np.ndarray] = {}
        if ticker_column in df.columns:
            for ticker, group in df.groupby(ticker_column, sort=False):
                key = str(ticker).upper()
                ticker_normalizer = RobustNormalizer.fit(group, feature_names, clip=clip)
                ticker_median[key] = ticker_normalizer.median
                ticker_iqr[key] = ticker_normalizer.iqr
        return cls(
            list(feature_names),
            global_normalizer.median,
            global_normalizer.iqr,
            float(clip),
            ticker_median=ticker_median,
            ticker_iqr=ticker_iqr,
            ticker_column=str(ticker_column),
        )

    def transform_frame(self, df: pd.DataFrame) -> np.ndarray:
        values = df[self.feature_names].values.astype(np.float32, copy=False)
        values = np.nan_to_num(values, nan=0.0, posinf=self.clip, neginf=-self.clip)
        median = np.broadcast_to(self.median.reshape(1, -1), values.shape).copy()
        iqr = np.broadcast_to(self.iqr.reshape(1, -1), values.shape).copy()
        if self.ticker_column in df.columns:
            tickers = df[self.ticker_column].astype(str).str.upper().to_numpy()
            for ticker in np.unique(tickers):
                if self.ticker_median is None or self.ticker_iqr is None:
                    continue
                ticker_median = self.ticker_median.get(str(ticker))
                ticker_iqr = self.ticker_iqr.get(str(ticker))
                if ticker_median is None or ticker_iqr is None:
                    continue
                mask = tickers == ticker
                median[mask] = ticker_median
                iqr[mask] = ticker_iqr
        out = (values - median) / iqr
        out = np.nan_to_num(out, nan=0.0, posinf=self.clip, neginf=-self.clip)
        return np.clip(out, -self.clip, self.clip).astype(np.float32, copy=False)

    def to_dict(self) -> dict:
        return {
            "kind": "ticker",
            "feature_names": self.feature_names,
            "median": self.median.tolist(),
            "iqr": self.iqr.tolist(),
            "clip": self.clip,
            "ticker_column": self.ticker_column,
            "ticker_median": {key: value.tolist() for key, value in (self.ticker_median or {}).items()},
            "ticker_iqr": {key: value.tolist() for key, value in (self.ticker_iqr or {}).items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TickerRobustNormalizer":
        return cls(
            feature_names=[str(x) for x in data["feature_names"]],
            median=np.asarray(data["median"], dtype=np.float32),
            iqr=np.asarray(data["iqr"], dtype=np.float32),
            clip=float(data.get("clip", 10.0)),
            ticker_column=str(data.get("ticker_column", "ticker")),
            ticker_median={key: np.asarray(value, dtype=np.float32) for key, value in data.get("ticker_median", {}).items()},
            ticker_iqr={key: np.asarray(value, dtype=np.float32) for key, value in data.get("ticker_iqr", {}).items()},
        )



def infer_sort_columns(df: pd.DataFrame) -> list[str]:
    cols = ["ticker", "date"]
    for c in SORT_COLUMNS_CANDIDATES:
        if c in df.columns:
            cols.append(c)
            break
    return cols


def prepare_jepa_frame(path: str | Path, feature_names: Sequence[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    df = pd.read_parquet(path)
    if feature_names is None:
        feature_names = [c for c in load_base_feature_columns() if c in df.columns]
    else:
        feature_names = [c for c in feature_names if c in df.columns]
    if not feature_names:
        raise ValueError("No JEPA input features are present in the dataframe")
    missing = {"ticker", "date"} - set(df.columns)
    if missing:
        raise KeyError(f"Missing required grouping columns: {sorted(missing)}")
    sort_cols = infer_sort_columns(df)
    df = df.sort_values(sort_cols).reset_index(drop=True)
    df["date"] = df["date"].astype(str)
    return df, list(feature_names)


def split_dates(df: pd.DataFrame, val_fraction: float = 0.15) -> tuple[set[str], set[str]]:
    dates = sorted(df["date"].astype(str).unique().tolist())
    if len(dates) < 3:
        return set(dates), set(dates[-1:])
    n_val = max(1, int(round(len(dates) * float(val_fraction))))
    val_dates = set(dates[-n_val:])
    train_dates = set(dates[:-n_val])
    if not train_dates:
        train_dates = set(dates[:-1])
        val_dates = set(dates[-1:])
    return train_dates, val_dates


class TemporalJEPADataset(Dataset):
    def __init__(
        self,
        df: pd.DataFrame,
        normalizer: RobustNormalizer,
        context_len: int,
        horizons: Sequence[int],
        allowed_dates: set[str] | None = None,
    ) -> None:
        self.context_len = int(context_len)
        self.horizons = [int(h) for h in horizons]
        self.max_horizon = max(self.horizons)
        self.normalizer = normalizer
        self.sequences: list[np.ndarray] = []
        self.index: list[tuple[int, int]] = []

        work = df
        if allowed_dates is not None:
            work = work[work["date"].astype(str).isin(allowed_dates)].copy()

        for _, group in work.groupby(["ticker", "date"], sort=False):
            if len(group) < self.context_len + self.max_horizon:
                continue
            arr = normalizer.transform_frame(group)
            seq_id = len(self.sequences)
            self.sequences.append(arr)
            start = self.context_len - 1
            stop = len(arr) - self.max_horizon
            for pos in range(start, stop):
                self.index.append((seq_id, pos))

        if not self.index:
            raise ValueError("No valid JEPA windows were created")

    def __len__(self) -> int:
        return len(self.index)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        seq_id, pos = self.index[idx]
        arr = self.sequences[seq_id]
        ctx = arr[pos - self.context_len + 1 : pos + 1]
        targets = []
        for h in self.horizons:
            end = pos + h
            targets.append(arr[end - self.context_len + 1 : end + 1])
        return torch.from_numpy(ctx), torch.from_numpy(np.stack(targets, axis=0))


class AlphaTemporalJEPADataset(Dataset):
    """Temporal JEPA windows with an auxiliary current-row trading target."""

    def __init__(
        self,
        df: pd.DataFrame,
        normalizer: RobustNormalizer,
        context_len: int,
        horizons: Sequence[int],
        allowed_dates: set[str] | None = None,
    ) -> None:
        self.context_len = int(context_len)
        self.horizons = [int(h) for h in horizons]
        self.max_horizon = max(self.horizons)
        self.normalizer = normalizer
        self.sequences: list[np.ndarray] = []
        self.targets: list[np.ndarray] = []
        self.index: list[tuple[int, int]] = []
        self.labels: list[int] = []

        work = df
        if allowed_dates is not None:
            work = work[work["date"].astype(str).isin(allowed_dates)].copy()
        if "target" not in work.columns:
            raise KeyError("AlphaTemporalJEPADataset requires a 'target' column")

        for _, group in work.groupby(["ticker", "date"], sort=False):
            if len(group) < self.context_len + self.max_horizon:
                continue
            arr = normalizer.transform_frame(group)
            raw_y = group["target"].to_numpy()
            if np.nanmin(raw_y) < 0:
                y = (raw_y + 1).astype(np.int64)
            else:
                y = raw_y.astype(np.int64)
            y = np.clip(y, 0, 2)
            seq_id = len(self.sequences)
            self.sequences.append(arr)
            self.targets.append(y)
            start = self.context_len - 1
            stop = len(arr) - self.max_horizon
            for pos in range(start, stop):
                self.index.append((seq_id, pos))
                self.labels.append(int(y[pos]))

        if not self.index:
            raise ValueError("No valid AlphaJEPA windows were created")

    def __len__(self) -> int:
        return len(self.index)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        seq_id, pos = self.index[idx]
        arr = self.sequences[seq_id]
        ctx = arr[pos - self.context_len + 1 : pos + 1]
        target_windows = []
        for h in self.horizons:
            end = pos + h
            target_windows.append(arr[end - self.context_len + 1 : end + 1])
        y = self.targets[seq_id][pos]
        return (
            torch.from_numpy(ctx),
            torch.from_numpy(np.stack(target_windows, axis=0)),
            torch.tensor(int(y), dtype=torch.long),
        )
