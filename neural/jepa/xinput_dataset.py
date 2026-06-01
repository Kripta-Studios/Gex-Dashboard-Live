from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from neural.jepa.dataset import RobustNormalizer, infer_sort_columns
from neural.jepa.xinput_features import XInputFeatureSplit, build_xinput_feature_split


@dataclass
class XInputNormalizers:
    state: RobustNormalizer
    input: RobustNormalizer

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps({"state": self.state.to_dict(), "input": self.input.to_dict()}, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "XInputNormalizers":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            state=RobustNormalizer.from_dict(data["state"]),
            input=RobustNormalizer.from_dict(data["input"]),
        )


def prepare_xinput_frame(path: str | Path) -> tuple[pd.DataFrame, XInputFeatureSplit]:
    df = pd.read_parquet(path)
    missing = {"ticker", "date"} - set(df.columns)
    if missing:
        raise KeyError(f"Missing required grouping columns: {sorted(missing)}")
    df["date"] = df["date"].astype(str)
    df = df.sort_values(infer_sort_columns(df)).reset_index(drop=True)
    split = build_xinput_feature_split(df)
    return df, split


def fit_xinput_normalizers(
    df: pd.DataFrame,
    split: XInputFeatureSplit,
    train_dates: set[str],
    clip: float = 10.0,
) -> XInputNormalizers:
    train_df = df[df["date"].astype(str).isin(train_dates)].copy()
    return XInputNormalizers(
        state=RobustNormalizer.fit(train_df, split.state_features, clip=clip),
        input=RobustNormalizer.fit(train_df, split.input_features, clip=clip),
    )


class XInputJEPADataset(Dataset):
    def __init__(
        self,
        df: pd.DataFrame,
        normalizers: XInputNormalizers,
        context_len: int,
        horizons: Sequence[int],
        allowed_dates: set[str] | None = None,
    ) -> None:
        self.context_len = int(context_len)
        self.horizons = [int(h) for h in horizons]
        self.max_horizon = max(self.horizons)
        self.normalizers = normalizers
        self.state_sequences: list[np.ndarray] = []
        self.input_sequences: list[np.ndarray] = []
        self.target_sequences: list[np.ndarray] = []
        self.index: list[tuple[int, int]] = []
        self.labels: list[int] = []

        work = df
        if allowed_dates is not None:
            work = work[work["date"].astype(str).isin(allowed_dates)].copy()
        if "target" not in work.columns:
            raise KeyError("XInputJEPADataset requires a 'target' column")

        for _, group in work.groupby(["ticker", "date"], sort=False):
            if len(group) < self.context_len + self.max_horizon:
                continue
            s_arr = normalizers.state.transform_frame(group)
            u_arr = normalizers.input.transform_frame(group)
            raw_y = group["target"].to_numpy()
            if np.nanmin(raw_y) < 0:
                y = (raw_y + 1).astype(np.int64)
            else:
                y = raw_y.astype(np.int64)
            y = np.clip(y, 0, 2)
            seq_id = len(self.state_sequences)
            self.state_sequences.append(s_arr)
            self.input_sequences.append(u_arr)
            self.target_sequences.append(y)
            start = self.context_len - 1
            stop = len(s_arr) - self.max_horizon
            for pos in range(start, stop):
                self.index.append((seq_id, pos))
                self.labels.append(int(y[pos]))

        if not self.index:
            raise ValueError("No valid XInputJEPA windows were created")

    def __len__(self) -> int:
        return len(self.index)

    def __getitem__(self, idx: int):
        seq_id, pos = self.index[idx]
        s_arr = self.state_sequences[seq_id]
        u_arr = self.input_sequences[seq_id]
        s_ctx = s_arr[pos - self.context_len + 1 : pos + 1]
        u_ctx = u_arr[pos - self.context_len + 1 : pos + 1]
        target_state_windows = []
        for h in self.horizons:
            end = pos + h
            target_state_windows.append(s_arr[end - self.context_len + 1 : end + 1])
        y = self.target_sequences[seq_id][pos]
        return (
            torch.from_numpy(s_ctx),
            torch.from_numpy(u_ctx),
            torch.from_numpy(np.stack(target_state_windows, axis=0)),
            torch.tensor(int(y), dtype=torch.long),
        )

