from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader, Dataset

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.dataset import RobustNormalizer, TickerRobustNormalizer
from neural.jepa.features import write_feature_names
from neural.jepa.sigreg import SIGRegLoss, VarianceCovarianceLoss, latent_diagnostics


LEAKY_PATTERNS = (
    "future",
    "spot_long",
    "spot_short",
    "spot_best",
    "_opt_win",
    "_opt_status",
    "_opt_exit_ret",
    "_opt_exit_minutes",
    "_opt_max_ret",
    "_opt_min_ret",
)

ID_COLUMNS = {
    "ticker",
    "underlying_ticker",
    "trade_date",
    "date",
    "expiration",
    "expiry_mode",
    "timestamp",
    "time",
    "nearest_level_name",
}

BASE_PHYSICS_NAMES = (
    "minute",
    "dte_days",
    "spot",
    "underlying_volume",
    "dist_ib_high_bps",
    "dist_ib_low_bps",
    "dist_fib_127_up_bps",
    "dist_fib_161_up_bps",
    "dist_fib_200_up_bps",
    "dist_fib_127_dn_bps",
    "dist_fib_161_dn_bps",
    "dist_fib_200_dn_bps",
    "nearest_level_abs_bps",
    "ib_range_bps",
    "ret_1m_bps",
    "ret_5m_bps",
    "ret_15m_bps",
    "ret_30m_bps",
)


@dataclass
class EventPhysTDJEPAConfig:
    input_dim: int
    q_dim: int
    context_len: int
    horizons: list[int]
    z_dim: int = 32
    phys_dim: int = 12
    delta_dim: int = 16
    horizon_dim: int = 8
    hidden_dim: int = 128
    num_layers: int = 2
    dropout: float = 0.10

    encoder_input_mode: str = "flat"
    modal_token_dim: int = 32
    modal_feature_indices: list[list[int]] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class SequenceEncoder(nn.Module):
    def __init__(self, input_dim: int, output_dim: int, hidden_dim: int, num_layers: int, dropout: float) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(input_dim)
        self.gru = nn.GRU(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, output_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.norm(x)
        _, h = self.gru(x)
        return self.head(h[-1])


class ModalSequenceEncoder(nn.Module):
    """Balance heterogeneous market modalities before temporal encoding."""

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        hidden_dim: int,
        num_layers: int,
        dropout: float,
        modal_feature_indices: Sequence[Sequence[int]],
        modal_token_dim: int,
    ) -> None:
        super().__init__()
        groups = [[int(index) for index in group] for group in modal_feature_indices if group]
        flattened = [index for group in groups for index in group]
        if sorted(flattened) != list(range(int(input_dim))):
            raise ValueError("Modal feature indices must cover each input feature exactly once")
        if len(set(flattened)) != len(flattened):
            raise ValueError("Modal feature indices overlap")
        self.modal_buffer_names: list[str] = []
        self.norms = nn.ModuleList()
        self.projectors = nn.ModuleList()
        for index, group in enumerate(groups):
            buffer_name = f"modal_indices_{index}"
            self.register_buffer(buffer_name, torch.tensor(group, dtype=torch.long), persistent=False)
            self.modal_buffer_names.append(buffer_name)
            self.norms.append(nn.LayerNorm(len(group)))
            self.projectors.append(
                nn.Sequential(
                    nn.Linear(len(group), int(modal_token_dim)),
                    nn.GELU(),
                    nn.Dropout(dropout),
                    nn.LayerNorm(int(modal_token_dim)),
                )
            )
        fused_dim = len(groups) * int(modal_token_dim)
        self.gru = nn.GRU(
            input_size=fused_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, output_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        tokens = []
        for buffer_name, norm, projector in zip(self.modal_buffer_names, self.norms, self.projectors):
            indices = getattr(self, buffer_name)
            tokens.append(projector(norm(torch.index_select(x, dim=-1, index=indices))))
        fused = torch.cat(tokens, dim=-1)
        _, h = self.gru(fused)
        return self.head(h[-1])


class EventPhysTDJEPA(nn.Module):
    """Temporal-difference + physics-latent JEPA for event-option snapshots."""

    def __init__(self, config: EventPhysTDJEPAConfig) -> None:
        super().__init__()
        if config.context_len < 2:
            raise ValueError("context_len must be >= 2 for temporal-difference encoding")
        if config.phys_dim <= 0 or config.phys_dim >= config.z_dim:
            raise ValueError("phys_dim must be in [1, z_dim)")
        self.config = config
        if config.encoder_input_mode == "flat":
            self.state_encoder = SequenceEncoder(
                config.input_dim,
                config.z_dim,
                config.hidden_dim,
                config.num_layers,
                config.dropout,
            )
            self.delta_encoder = SequenceEncoder(
                config.input_dim,
                config.delta_dim,
                config.hidden_dim,
                config.num_layers,
                config.dropout,
            )
        elif config.encoder_input_mode == "modal":
            if not config.modal_feature_indices:
                raise ValueError("Modal encoder requires modal_feature_indices")
            self.state_encoder = ModalSequenceEncoder(
                config.input_dim,
                config.z_dim,
                config.hidden_dim,
                config.num_layers,
                config.dropout,
                config.modal_feature_indices,
                config.modal_token_dim,
            )
            self.delta_encoder = ModalSequenceEncoder(
                config.input_dim,
                config.delta_dim,
                config.hidden_dim,
                config.num_layers,
                config.dropout,
                config.modal_feature_indices,
                config.modal_token_dim,
            )
        else:
            raise ValueError(f"Unsupported encoder input mode: {config.encoder_input_mode}")
        self.horizon_embed = nn.Embedding(len(config.horizons), config.horizon_dim)
        motion_in = config.z_dim + config.delta_dim + config.horizon_dim
        self.motion_heads = nn.ModuleList(
            [
                nn.Sequential(
                    nn.LayerNorm(motion_in),
                    nn.Linear(motion_in, config.hidden_dim),
                    nn.GELU(),
                    nn.Dropout(config.dropout),
                    nn.Linear(config.hidden_dim, config.z_dim),
                )
                for _ in config.horizons
            ]
        )
        self.physics_projector = nn.Sequential(
            nn.LayerNorm(config.phys_dim),
            nn.Linear(config.phys_dim, max(config.hidden_dim // 2, config.q_dim)),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(max(config.hidden_dim // 2, config.q_dim), config.q_dim),
        )
        self.prototype_head = nn.Sequential(
            nn.LayerNorm(config.z_dim),
            nn.Linear(config.z_dim, config.hidden_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim, config.hidden_dim),
        )

    def encode_state(self, ctx: torch.Tensor) -> torch.Tensor:
        return self.state_encoder(ctx)

    def encode_delta(self, delta_ctx: torch.Tensor) -> torch.Tensor:
        return self.delta_encoder(delta_ctx)

    def project_physics(self, z: torch.Tensor) -> torch.Tensor:
        return self.physics_projector(z[..., : self.config.phys_dim])

    def prototype_features(self, z: torch.Tensor) -> torch.Tensor:
        return F.normalize(self.prototype_head(z), dim=-1)

    def forward(self, ctx: torch.Tensor, delta_ctx: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        z = self.encode_state(ctx)
        d = self.encode_delta(delta_ctx)
        preds = []
        for idx, head in enumerate(self.motion_heads):
            h = self.horizon_embed.weight[idx].view(1, -1).expand(len(z), -1)
            dz = head(torch.cat([z, d, h], dim=-1))
            preds.append(z + dz)
        return z, d, torch.stack(preds, dim=1)


class PrototypeDistillationLoss(nn.Module):
    """DINO-style prototype loss for temporal prediction targets."""

    def __init__(self, dim: int, prototypes: int, teacher_temp: float, student_temp: float, center_momentum: float) -> None:
        super().__init__()
        self.prototypes = nn.Linear(int(dim), int(prototypes), bias=False)
        nn.init.trunc_normal_(self.prototypes.weight, std=0.02)
        self.teacher_temp = float(teacher_temp)
        self.student_temp = float(student_temp)
        self.center_momentum = float(center_momentum)
        self.register_buffer("center", torch.zeros(1, int(prototypes)))

    def forward(self, student_feat: torch.Tensor, teacher_feat: torch.Tensor, update_center: bool) -> torch.Tensor:
        student_logits = self.prototypes(student_feat) / max(self.student_temp, 1e-6)
        with torch.no_grad():
            teacher_logits = self.prototypes(teacher_feat)
            centered = (teacher_logits - self.center.to(teacher_logits.device, teacher_logits.dtype)) / max(self.teacher_temp, 1e-6)
            teacher_probs = F.softmax(centered, dim=-1)
            if update_center:
                batch_center = teacher_logits.mean(dim=0, keepdim=True)
                self.center.mul_(self.center_momentum).add_(batch_center.detach(), alpha=1.0 - self.center_momentum)
        return -(teacher_probs * F.log_softmax(student_logits, dim=-1)).sum(dim=-1).mean()


def make_ema_teacher(model: EventPhysTDJEPA) -> EventPhysTDJEPA:
    teacher = EventPhysTDJEPA(model.config).to(next(model.parameters()).device)
    teacher.load_state_dict(model.state_dict())
    teacher.eval()
    for param in teacher.parameters():
        param.requires_grad_(False)
    return teacher


@torch.no_grad()
def update_ema_teacher(model: EventPhysTDJEPA, teacher: EventPhysTDJEPA, momentum: float) -> None:
    m = float(momentum)
    for t_param, s_param in zip(teacher.parameters(), model.parameters()):
        t_param.data.mul_(m).add_(s_param.data, alpha=1.0 - m)
    for t_buf, s_buf in zip(teacher.buffers(), model.buffers()):
        if t_buf.dtype.is_floating_point:
            t_buf.data.mul_(m).add_(s_buf.data, alpha=1.0 - m)
        else:
            t_buf.copy_(s_buf)


class EventPhysTDJEPADataset(Dataset):
    def __init__(
        self,
        df: pd.DataFrame,
        feature_cols: Sequence[str],
        physical_cols: Sequence[str],
        normalizer: RobustNormalizer,
        context_len: int,
        horizons: Sequence[int],
        group_cols: Sequence[str],
    ) -> None:
        self.feature_cols = list(feature_cols)
        self.physical_cols = list(physical_cols)
        self.phys_idx = [self.feature_cols.index(c) for c in self.physical_cols]
        self.context_len = int(context_len)
        self.horizons = [int(h) for h in horizons]
        self.max_horizon = max(self.horizons)
        self.normalizer = normalizer
        self.sequences: list[np.ndarray] = []
        self.index: list[tuple[int, int]] = []

        for _, group in df.groupby(list(group_cols), sort=False):
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
            raise ValueError("No valid EventPhysTDJEPA windows were created")

    def __len__(self) -> int:
        return len(self.index)

    def __getitem__(self, idx: int):
        seq_id, pos = self.index[idx]
        arr = self.sequences[seq_id]
        ctx = arr[pos - self.context_len + 1 : pos + 1]
        delta_ctx = np.diff(ctx, axis=0)
        targets = []
        q_future = []
        for h in self.horizons:
            end = pos + h
            targets.append(arr[end - self.context_len + 1 : end + 1])
            q_future.append(arr[end, self.phys_idx])
        q_now = arr[pos, self.phys_idx]
        return (
            torch.from_numpy(ctx),
            torch.from_numpy(delta_ctx),
            torch.from_numpy(np.stack(targets, axis=0)),
            torch.from_numpy(q_now.astype(np.float32, copy=False)),
            torch.from_numpy(np.stack(q_future, axis=0).astype(np.float32, copy=False)),
        )


def month_add(yyyymm: str, delta: int) -> str:
    value = int(yyyymm)
    year = value // 100
    month = value % 100 + int(delta)
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return f"{year:04d}{month:02d}"


def month_range(start: str, end: str) -> list[str]:
    out = []
    cur = str(start)
    while cur <= str(end):
        out.append(cur)
        cur = month_add(cur, 1)
    return out


def parse_horizons(text: str) -> list[int]:
    values = [int(x.strip()) for x in str(text).split(",") if x.strip()]
    if not values:
        raise ValueError("At least one horizon is required")
    return sorted(set(values))


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def sanitize_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", str(name)).strip("_").lower()


def prepare_frame(path: str | Path, tickers: Sequence[str], expiry_modes: Sequence[str] | None) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df["date"] = df["trade_date"].astype(str)
    df["month"] = df["date"].str[:6]
    if tickers:
        allowed = {str(t).upper() for t in tickers}
        df = df[df["ticker"].isin(allowed)].copy()
    if expiry_modes:
        modes = {str(x) for x in expiry_modes}
        df = df[df["expiry_mode"].astype(str).isin(modes)].copy()
    sort_cols = ["ticker", "date", "expiry_mode"]
    if "timestamp" in df.columns:
        sort_cols.append("timestamp")
    else:
        sort_cols.append("time")
    return df.sort_values(sort_cols).reset_index(drop=True)


def select_feature_columns(df: pd.DataFrame) -> list[str]:
    selected: list[str] = []
    for col in df.columns:
        low = str(col).lower()
        if col in ID_COLUMNS:
            continue
        if any(pattern in low for pattern in LEAKY_PATTERNS):
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            selected.append(col)
    return selected


MODAL_FEATURE_GROUPS = ("price_level", "option_surface", "physics", "cross_asset", "other")


def classify_feature_modality(col: str) -> str:
    low = str(col).lower()
    if low.startswith("ctx_"):
        return "cross_asset"
    if low.startswith("phys_"):
        return "physics"
    if low.startswith(("call_", "put_")):
        return "option_surface"
    if any(token in low for token in ("gamma", "delta", "vega", "theta", "rho", "iv", "open_interest", "oi_", "bid", "ask")):
        return "option_surface"
    if low in BASE_PHYSICS_NAMES or low.startswith(("dist_", "ret_", "ib_", "nearest_level", "spot", "underlying_", "dte_", "minute")):
        return "price_level"
    return "other"


def build_modal_feature_indices(feature_cols: Sequence[str]) -> list[list[int]]:
    groups: dict[str, list[int]] = {name: [] for name in MODAL_FEATURE_GROUPS}
    for index, col in enumerate(feature_cols):
        groups[classify_feature_modality(col)].append(index)
    return [groups[name] for name in MODAL_FEATURE_GROUPS if groups[name]]


def summarize_modal_feature_groups(feature_cols: Sequence[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {name: [] for name in MODAL_FEATURE_GROUPS}
    for col in feature_cols:
        groups[classify_feature_modality(col)].append(str(col))
    return {name: values for name, values in groups.items() if values}


def select_physical_columns(feature_cols: Sequence[str], max_physical_features: int) -> list[str]:
    feature_set = set(feature_cols)
    selected = [c for c in BASE_PHYSICS_NAMES if c in feature_set]
    selected += [c for c in feature_cols if c.startswith("phys_") and c not in selected]
    selected += [c for c in feature_cols if c.startswith("ctx_") and c not in selected]
    selected = selected[: int(max_physical_features)]
    if not selected:
        raise ValueError("No physical columns were selected")
    return selected


def build_feature_names(args: argparse.Namespace, physical_cols: Sequence[str]) -> list[str]:
    feature_prefix = str(args.feature_prefix).strip() or "ptdj"
    first_h = parse_horizons(args.horizons)[0]
    return (
        [f"{feature_prefix}_z_{i:02d}" for i in range(int(args.z_dim))]
        + [f"{feature_prefix}_dz_h{first_h}_{i:02d}" for i in range(int(args.z_dim))]
        + [f"{feature_prefix}_phys_{i:02d}_{sanitize_name(c)}" for i, c in enumerate(physical_cols)]
        + [f"{feature_prefix}_phys_delta_h{first_h}_{i:02d}_{sanitize_name(c)}" for i, c in enumerate(physical_cols)]
        + [
            f"{feature_prefix}_context_valid",
            f"{feature_prefix}_latent_velocity",
            f"{feature_prefix}_input_delta_norm",
            f"{feature_prefix}_motion_norm_h{first_h}",
            f"{feature_prefix}_pred_dispersion",
            f"{feature_prefix}_phys_transition_norm_h{first_h}",
            f"{feature_prefix}_lagged_pred_h{first_h}_err",
        ]
    )


def make_loader(ds: EventPhysTDJEPADataset, args: argparse.Namespace, shuffle: bool) -> DataLoader:
    return DataLoader(
        ds,
        batch_size=int(args.batch_size),
        shuffle=shuffle,
        num_workers=int(args.num_workers),
        pin_memory=torch.cuda.is_available(),
        persistent_workers=bool(args.num_workers > 0),
        drop_last=shuffle,
    )


def train_epoch(
    model: EventPhysTDJEPA,
    teacher: EventPhysTDJEPA | None,
    proto_loss_fn: PrototypeDistillationLoss | None,
    loader: DataLoader,
    sigreg: SIGRegLoss,
    vicreg: VarianceCovarianceLoss,
    opt: torch.optim.Optimizer,
    args: argparse.Namespace,
    device: torch.device,
) -> dict:
    model.train()
    if teacher is not None:
        teacher.eval()
    sums = {"pred": 0.0, "proto": 0.0, "state": 0.0, "dyn": 0.0, "sig": 0.0, "vic": 0.0, "total": 0.0}
    total = 0
    for ctx, delta_ctx, targets, q_now, q_future in loader:
        ctx = ctx.to(device).float()
        delta_ctx = delta_ctx.to(device).float()
        targets = targets.to(device).float()
        q_now = q_now.to(device).float()
        q_future = q_future.to(device).float()
        b, h, l, f = targets.shape
        z, _, pred_z = model(ctx, delta_ctx)
        if teacher is None:
            target_z = model.encode_state(targets.reshape(b * h, l, f)).reshape(b, h, -1)
        else:
            with torch.no_grad():
                target_z = teacher.encode_state(targets.reshape(b * h, l, f)).reshape(b, h, -1)
        pred_loss = F.mse_loss(pred_z, target_z.detach())
        proto_loss = pred_loss.new_tensor(0.0)
        if proto_loss_fn is not None and float(args.lambda_proto) > 0.0:
            student_feat = model.prototype_features(pred_z.reshape(b * h, -1))
            target_model = teacher if teacher is not None else model
            with torch.no_grad():
                teacher_feat = target_model.prototype_features(target_z.reshape(b * h, -1))
            proto_loss = proto_loss_fn(student_feat, teacher_feat, update_center=True)
        q_now_pred = model.project_physics(z)
        q_pred = model.project_physics(pred_z.reshape(b * h, -1)).reshape(b, h, -1)
        state_loss = F.mse_loss(q_now_pred, q_now) + F.mse_loss(q_pred, q_future)
        dyn_loss = F.mse_loss(q_pred - q_now_pred.unsqueeze(1), q_future - q_now.unsqueeze(1))
        res_start = int(model.config.phys_dim)
        res_all = torch.cat([z[:, res_start:], target_z.reshape(b * h, -1)[:, res_start:]], dim=0)
        sig_loss = sigreg(res_all)
        vic_loss = vicreg(res_all)
        loss = (
            pred_loss
            + float(args.lambda_proto) * proto_loss
            + float(args.lambda_state) * state_loss
            + float(args.lambda_dyn) * dyn_loss
            + float(args.lambda_sigreg) * sig_loss
            + float(args.lambda_vicreg) * vic_loss
        )
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), float(args.grad_clip))
        opt.step()
        if teacher is not None:
            update_ema_teacher(model, teacher, float(args.teacher_momentum))
        n = len(ctx)
        total += n
        sums["pred"] += float(pred_loss.item()) * n
        sums["proto"] += float(proto_loss.item()) * n
        sums["state"] += float(state_loss.item()) * n
        sums["dyn"] += float(dyn_loss.item()) * n
        sums["sig"] += float(sig_loss.item()) * n
        sums["vic"] += float(vic_loss.item()) * n
        sums["total"] += float(loss.item()) * n
    return {k: v / max(1, total) for k, v in sums.items()}


def evaluate_model(
    model: EventPhysTDJEPA,
    teacher: EventPhysTDJEPA | None,
    proto_loss_fn: PrototypeDistillationLoss | None,
    loader: DataLoader,
    sigreg: SIGRegLoss,
    vicreg: VarianceCovarianceLoss,
    args: argparse.Namespace,
    device: torch.device,
) -> dict:
    model.eval()
    if teacher is not None:
        teacher.eval()
    sums = {"pred": 0.0, "proto": 0.0, "state": 0.0, "dyn": 0.0, "sig": 0.0, "vic": 0.0, "total": 0.0}
    total = 0
    z_batches = []
    with torch.no_grad():
        for ctx, delta_ctx, targets, q_now, q_future in loader:
            ctx = ctx.to(device).float()
            delta_ctx = delta_ctx.to(device).float()
            targets = targets.to(device).float()
            q_now = q_now.to(device).float()
            q_future = q_future.to(device).float()
            b, h, l, f = targets.shape
            z, _, pred_z = model(ctx, delta_ctx)
            if teacher is None:
                target_z = model.encode_state(targets.reshape(b * h, l, f)).reshape(b, h, -1)
            else:
                target_z = teacher.encode_state(targets.reshape(b * h, l, f)).reshape(b, h, -1)
            pred_loss = F.mse_loss(pred_z, target_z.detach())
            proto_loss = pred_loss.new_tensor(0.0)
            if proto_loss_fn is not None and float(args.lambda_proto) > 0.0:
                student_feat = model.prototype_features(pred_z.reshape(b * h, -1))
                target_model = teacher if teacher is not None else model
                teacher_feat = target_model.prototype_features(target_z.reshape(b * h, -1))
                proto_loss = proto_loss_fn(student_feat, teacher_feat, update_center=False)
            q_now_pred = model.project_physics(z)
            q_pred = model.project_physics(pred_z.reshape(b * h, -1)).reshape(b, h, -1)
            state_loss = F.mse_loss(q_now_pred, q_now) + F.mse_loss(q_pred, q_future)
            dyn_loss = F.mse_loss(q_pred - q_now_pred.unsqueeze(1), q_future - q_now.unsqueeze(1))
            res_start = int(model.config.phys_dim)
            res_all = torch.cat([z[:, res_start:], target_z.reshape(b * h, -1)[:, res_start:]], dim=0)
            sig_loss = sigreg(res_all)
            vic_loss = vicreg(res_all)
            loss = (
                pred_loss
                + float(args.lambda_proto) * proto_loss
                + float(args.lambda_state) * state_loss
                + float(args.lambda_dyn) * dyn_loss
                + float(args.lambda_sigreg) * sig_loss
                + float(args.lambda_vicreg) * vic_loss
            )
            n = len(ctx)
            total += n
            sums["pred"] += float(pred_loss.item()) * n
            sums["proto"] += float(proto_loss.item()) * n
            sums["state"] += float(state_loss.item()) * n
            sums["dyn"] += float(dyn_loss.item()) * n
            sums["sig"] += float(sig_loss.item()) * n
            sums["vic"] += float(vic_loss.item()) * n
            sums["total"] += float(loss.item()) * n
            if len(z_batches) < 12:
                z_batches.append(z.detach().cpu())
    out = {k: v / max(1, total) for k, v in sums.items()}
    if z_batches:
        out.update({f"z_{k}": v for k, v in latent_diagnostics(torch.cat(z_batches)).items()})
    return out


def build_contexts(arr: np.ndarray, context_len: int) -> tuple[np.ndarray, np.ndarray, list[int]]:
    contexts = []
    deltas = []
    positions = []
    for pos in range(context_len - 1, len(arr)):
        ctx = arr[pos - context_len + 1 : pos + 1]
        contexts.append(ctx)
        deltas.append(np.diff(ctx, axis=0))
        positions.append(pos)
    if not contexts:
        empty_ctx = np.zeros((0, context_len, arr.shape[1]), dtype=np.float32)
        empty_delta = np.zeros((0, max(0, context_len - 1), arr.shape[1]), dtype=np.float32)
        return empty_ctx, empty_delta, []
    return np.stack(contexts).astype(np.float32), np.stack(deltas).astype(np.float32), positions


def pairwise_dispersion(preds: np.ndarray) -> float:
    if len(preds) < 2:
        return 0.0
    vals = []
    for i in range(len(preds)):
        for j in range(i + 1, len(preds)):
            vals.append(float(np.linalg.norm(preds[i] - preds[j])))
    return float(np.mean(vals)) if vals else 0.0


def export_month_features(
    model: EventPhysTDJEPA,
    normalizer: RobustNormalizer,
    month_df: pd.DataFrame,
    feature_cols: Sequence[str],
    physical_cols: Sequence[str],
    args: argparse.Namespace,
    device: torch.device,
) -> pd.DataFrame:
    work = month_df.copy().reset_index(drop=True)
    work["_orig_index"] = np.arange(len(work), dtype=np.int64)
    sort_cols = ["ticker", "date", "expiry_mode", "timestamp" if "timestamp" in work.columns else "time"]
    work = work.sort_values(sort_cols).reset_index(drop=True)
    z_dim = int(model.config.z_dim)
    q_dim = int(model.config.q_dim)
    first_h = int(model.config.horizons[0])
    prefix = str(getattr(args, "feature_prefix", "ptdj")).strip() or "ptdj"
    feature_data: dict[str, np.ndarray] = {}
    for i in range(z_dim):
        feature_data[f"{prefix}_z_{i:02d}"] = np.zeros(len(work), dtype=np.float32)
        feature_data[f"{prefix}_dz_h{first_h}_{i:02d}"] = np.zeros(len(work), dtype=np.float32)
    phys_names = [sanitize_name(c) for c in physical_cols]
    for i, name in enumerate(phys_names):
        feature_data[f"{prefix}_phys_{i:02d}_{name}"] = np.zeros(len(work), dtype=np.float32)
        feature_data[f"{prefix}_phys_delta_h{first_h}_{i:02d}_{name}"] = np.zeros(len(work), dtype=np.float32)
    scalar_cols = [
        f"{prefix}_context_valid",
        f"{prefix}_latent_velocity",
        f"{prefix}_input_delta_norm",
        f"{prefix}_motion_norm_h{first_h}",
        f"{prefix}_pred_dispersion",
        f"{prefix}_phys_transition_norm_h{first_h}",
        f"{prefix}_lagged_pred_h{first_h}_err",
    ]
    for col in scalar_cols:
        feature_data[col] = np.zeros(len(work), dtype=np.float32)

    h_to_idx = {int(h): i for i, h in enumerate(model.config.horizons)}
    batch_size = int(args.infer_batch_size)
    group_cols = ["ticker", "date", "expiry_mode"] if bool(args.group_expiry_mode) else ["ticker", "date"]
    first_idx = h_to_idx[first_h]
    model.eval()
    with torch.no_grad():
        for _, group in work.groupby(group_cols, sort=False):
            arr = normalizer.transform_frame(group)
            ctx, delta_ctx, positions = build_contexts(arr, int(model.config.context_len))
            if len(ctx) == 0:
                continue
            z_out, pred_out, q_out, q_pred_first_out = [], [], [], []
            for start in range(0, len(ctx), batch_size):
                x = torch.from_numpy(ctx[start : start + batch_size]).to(device).float()
                dx = torch.from_numpy(delta_ctx[start : start + batch_size]).to(device).float()
                z, _, pred = model(x, dx)
                q = model.project_physics(z)
                q_pred_first = model.project_physics(pred[:, first_idx])
                z_out.append(z.cpu().numpy())
                pred_out.append(pred.cpu().numpy())
                q_out.append(q.cpu().numpy())
                q_pred_first_out.append(q_pred_first.cpu().numpy())
            z = np.concatenate(z_out)
            pred = np.concatenate(pred_out)
            q_now = np.concatenate(q_out)
            q_pred_first = np.concatenate(q_pred_first_out)
            z_by_pos = np.zeros((len(group), z_dim), dtype=np.float32)
            pred_by_pos = np.zeros((len(group), len(model.config.horizons), z_dim), dtype=np.float32)
            q_by_pos = np.zeros((len(group), q_dim), dtype=np.float32)
            q_pred_first_by_pos = np.zeros((len(group), q_dim), dtype=np.float32)
            valid = np.zeros(len(group), dtype=bool)
            for row_i, pos in enumerate(positions):
                z_by_pos[pos] = z[row_i]
                pred_by_pos[pos] = pred[row_i]
                q_by_pos[pos] = q_now[row_i]
                q_pred_first_by_pos[pos] = q_pred_first[row_i]
                valid[pos] = True
            orig = group["_orig_index"].to_numpy(dtype=np.int64)
            for pos in range(len(group)):
                out_i = orig[pos]
                if not valid[pos]:
                    continue
                feature_data[f"{prefix}_context_valid"][out_i] = 1.0
                dz = pred_by_pos[pos, first_idx] - z_by_pos[pos]
                q_delta = q_pred_first_by_pos[pos] - q_by_pos[pos]
                for zi in range(z_dim):
                    feature_data[f"{prefix}_z_{zi:02d}"][out_i] = z_by_pos[pos, zi]
                    feature_data[f"{prefix}_dz_h{first_h}_{zi:02d}"][out_i] = dz[zi]
                for qi, name in enumerate(phys_names):
                    feature_data[f"{prefix}_phys_{qi:02d}_{name}"][out_i] = q_by_pos[pos, qi]
                    feature_data[f"{prefix}_phys_delta_h{first_h}_{qi:02d}_{name}"][out_i] = q_delta[qi]
                if pos >= 1 and valid[pos - 1]:
                    feature_data[f"{prefix}_latent_velocity"][out_i] = float(np.linalg.norm(z_by_pos[pos] - z_by_pos[pos - 1]))
                feature_data[f"{prefix}_input_delta_norm"][out_i] = float(np.linalg.norm(np.diff(arr[max(0, pos - int(model.config.context_len) + 1) : pos + 1], axis=0)))
                feature_data[f"{prefix}_motion_norm_h{first_h}"][out_i] = float(np.linalg.norm(dz))
                feature_data[f"{prefix}_pred_dispersion"][out_i] = pairwise_dispersion(pred_by_pos[pos])
                feature_data[f"{prefix}_phys_transition_norm_h{first_h}"][out_i] = float(np.linalg.norm(q_delta))
                src = pos - first_h
                if src >= 0 and valid[src]:
                    feature_data[f"{prefix}_lagged_pred_h{first_h}_err"][out_i] = float(
                        np.linalg.norm(pred_by_pos[src, first_idx] - z_by_pos[pos])
                    )

    key = work[["ticker", "trade_date", "expiration", "expiry_mode", "timestamp", "time"]].copy()
    feature_frame = pd.DataFrame(feature_data, index=work.index)
    out = pd.concat([key, feature_frame], axis=1)
    return out.sort_values(["ticker", "trade_date", "expiry_mode", "timestamp" if "timestamp" in out.columns else "time"]).reset_index(drop=True)


def fit_normalizer(train_df: pd.DataFrame, feature_cols: Sequence[str], args: argparse.Namespace) -> RobustNormalizer:
    mode = str(args.normalizer_mode)
    if mode == "ticker":
        return TickerRobustNormalizer.fit(train_df, feature_cols, clip=float(args.clip), ticker_column="ticker")
    if mode != "global":
        raise ValueError(f"Unsupported normalizer mode: {mode}")
    return RobustNormalizer.fit(train_df, feature_cols, clip=float(args.clip))


def fit_encoder(
    train_df: pd.DataFrame,
    feature_cols: list[str],
    physical_cols: list[str],
    args: argparse.Namespace,
    device: torch.device,
) -> dict:
    train_months = sorted(train_df["month"].astype(str).unique().tolist())
    normalizer = fit_normalizer(train_df, feature_cols, args)
    group_cols = ["ticker", "date", "expiry_mode"] if bool(args.group_expiry_mode) else ["ticker", "date"]
    ds = EventPhysTDJEPADataset(
        train_df,
        feature_cols,
        physical_cols,
        normalizer,
        int(args.context_len),
        parse_horizons(args.horizons),
        group_cols,
    )
    loader = make_loader(ds, args, shuffle=True)
    config = EventPhysTDJEPAConfig(
        input_dim=len(feature_cols),
        q_dim=len(physical_cols),
        context_len=int(args.context_len),
        horizons=parse_horizons(args.horizons),
        z_dim=int(args.z_dim),
        phys_dim=int(args.phys_dim),
        delta_dim=int(args.delta_dim),
        horizon_dim=int(args.horizon_dim),
        hidden_dim=int(args.hidden_dim),
        num_layers=int(args.num_layers),
        dropout=float(args.dropout),
        encoder_input_mode=str(args.encoder_input_mode),
        modal_token_dim=int(args.modal_token_dim),
        modal_feature_indices=build_modal_feature_indices(feature_cols) if str(args.encoder_input_mode) == "modal" else None,
    )
    model = EventPhysTDJEPA(config).to(device)
    teacher = make_ema_teacher(model) if bool(args.use_ema_teacher) else None
    proto_loss_fn = (
        PrototypeDistillationLoss(
            dim=int(args.hidden_dim),
            prototypes=int(args.proto_prototypes),
            teacher_temp=float(args.proto_teacher_temp),
            student_temp=float(args.proto_student_temp),
            center_momentum=float(args.proto_center_momentum),
        ).to(device)
        if float(args.lambda_proto) > 0.0
        else None
    )
    sigreg = SIGRegLoss(max(1, int(args.z_dim) - int(args.phys_dim)), num_projections=int(args.sigreg_projections)).to(device)
    vicreg = VarianceCovarianceLoss(min_std=float(args.vicreg_min_std), cov_weight=0.05, var_weight=1.0).to(device)
    params = list(model.parameters()) + (list(proto_loss_fn.parameters()) if proto_loss_fn is not None else [])
    opt = torch.optim.AdamW(params, lr=float(args.lr), weight_decay=float(args.weight_decay))
    history = []
    for epoch in range(1, int(args.epochs) + 1):
        row = {"epoch": epoch, **train_epoch(model, teacher, proto_loss_fn, loader, sigreg, vicreg, opt, args, device)}
        history.append(row)
    eval_loader = make_loader(ds, args, shuffle=False)
    train_eval = evaluate_model(model, teacher, proto_loss_fn, eval_loader, sigreg, vicreg, args, device)
    export_model = teacher if teacher is not None and bool(args.export_teacher_features) else model
    return {
        "model": model,
        "teacher": teacher,
        "export_model": export_model,
        "normalizer": normalizer,
        "config": config,
        "train_eval": train_eval,
        "history": history,
        "train_months": train_months,
        "train_rows": int(len(train_df)),
        "train_windows": int(len(ds)),
    }


def export_deploy_model(
    output_dir: Path,
    train_frame: pd.DataFrame,
    feature_cols: list[str],
    physical_cols: list[str],
    feature_names: list[str],
    args: argparse.Namespace,
    device: torch.device,
) -> None:
    deploy_month = str(args.deploy_month).strip()
    if not deploy_month:
        raise RuntimeError("--export-deploy-model requires --deploy-month")
    deploy_train_end = str(args.deploy_train_end_month).strip()
    if deploy_train_end and deploy_train_end >= deploy_month:
        raise RuntimeError(f"--deploy-train-end-month {deploy_train_end} must be earlier than deploy month {deploy_month}")
    train = train_frame[train_frame["month"].astype(str) < deploy_month].copy()
    if deploy_train_end:
        train = train[train["month"].astype(str) <= deploy_train_end].copy()
    train_months = sorted(train["month"].astype(str).unique().tolist())
    if len(train_months) < int(args.min_train_months) or len(train) < int(args.min_train_rows):
        raise RuntimeError(
            f"Not enough rows to export deploy encoder for {deploy_month}: "
            f"months={len(train_months)} rows={len(train):,}"
        )
    print(f"[deploy] train_months={train_months[0]}..{train_months[-1]} rows={len(train):,} device={device}")
    fitted = fit_encoder(train, feature_cols, physical_cols, args, device)
    deploy_dir = Path(args.deploy_output_dir).resolve() if str(args.deploy_output_dir).strip() else output_dir / "deploy_model"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    model_path = deploy_dir / "event_phys_td_jepa_encoder.pt"
    metadata_path = deploy_dir / "event_phys_td_jepa_encoder.json"
    metadata = {
        "schema_version": 1,
        "component": "event_phys_td_jepa_encoder",
        "deploy_month": deploy_month,
        "deploy_train_end_month": deploy_train_end or None,
        "train_months": fitted["train_months"],
        "train_rows": fitted["train_rows"],
        "train_windows": fitted["train_windows"],
        "config": fitted["config"].to_dict(),
        "feature_cols": feature_cols,
        "physical_cols": physical_cols,
        "feature_names": feature_names,
        "normalizer": fitted["normalizer"].to_dict(),
        "train_eval": fitted["train_eval"],
        "last_epoch": fitted["history"][-1] if fitted["history"] else {},
        "args": vars(args),
    }
    torch.save(
        {
            "schema_version": 1,
            "component": "event_phys_td_jepa_encoder",
            "model_state_dict": fitted["export_model"].state_dict(),
            "config": fitted["config"].to_dict(),
            "feature_cols": feature_cols,
            "physical_cols": physical_cols,
            "feature_names": feature_names,
            "normalizer": fitted["normalizer"].to_dict(),
            "metadata": metadata,
        },
        model_path,
    )
    metadata_path.write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    write_feature_names(deploy_dir / "event_phys_td_jepa_feature_names.json", feature_names)
    print(f"[deploy] wrote {model_path}")


def train_fold(
    train_df: pd.DataFrame,
    month_df: pd.DataFrame,
    feature_cols: list[str],
    physical_cols: list[str],
    args: argparse.Namespace,
    device: torch.device,
) -> tuple[pd.DataFrame, dict]:
    train_months = sorted(train_df["month"].astype(str).unique().tolist())
    normalizer = fit_normalizer(train_df, feature_cols, args)
    group_cols = ["ticker", "date", "expiry_mode"] if bool(args.group_expiry_mode) else ["ticker", "date"]
    ds = EventPhysTDJEPADataset(
        train_df,
        feature_cols,
        physical_cols,
        normalizer,
        int(args.context_len),
        parse_horizons(args.horizons),
        group_cols,
    )
    loader = make_loader(ds, args, shuffle=True)
    config = EventPhysTDJEPAConfig(
        input_dim=len(feature_cols),
        q_dim=len(physical_cols),
        context_len=int(args.context_len),
        horizons=parse_horizons(args.horizons),
        z_dim=int(args.z_dim),
        phys_dim=int(args.phys_dim),
        delta_dim=int(args.delta_dim),
        horizon_dim=int(args.horizon_dim),
        hidden_dim=int(args.hidden_dim),
        num_layers=int(args.num_layers),
        dropout=float(args.dropout),
        encoder_input_mode=str(args.encoder_input_mode),
        modal_token_dim=int(args.modal_token_dim),
        modal_feature_indices=build_modal_feature_indices(feature_cols) if str(args.encoder_input_mode) == "modal" else None,
    )
    model = EventPhysTDJEPA(config).to(device)
    teacher = make_ema_teacher(model) if bool(args.use_ema_teacher) else None
    proto_loss_fn = (
        PrototypeDistillationLoss(
            dim=int(args.hidden_dim),
            prototypes=int(args.proto_prototypes),
            teacher_temp=float(args.proto_teacher_temp),
            student_temp=float(args.proto_student_temp),
            center_momentum=float(args.proto_center_momentum),
        ).to(device)
        if float(args.lambda_proto) > 0.0
        else None
    )
    sigreg = SIGRegLoss(max(1, int(args.z_dim) - int(args.phys_dim)), num_projections=int(args.sigreg_projections)).to(device)
    vicreg = VarianceCovarianceLoss(min_std=float(args.vicreg_min_std), cov_weight=0.05, var_weight=1.0).to(device)
    params = list(model.parameters()) + (list(proto_loss_fn.parameters()) if proto_loss_fn is not None else [])
    opt = torch.optim.AdamW(params, lr=float(args.lr), weight_decay=float(args.weight_decay))
    history = []
    for epoch in range(1, int(args.epochs) + 1):
        row = {"epoch": epoch, **train_epoch(model, teacher, proto_loss_fn, loader, sigreg, vicreg, opt, args, device)}
        history.append(row)
    eval_loader = make_loader(ds, args, shuffle=False)
    train_eval = evaluate_model(model, teacher, proto_loss_fn, eval_loader, sigreg, vicreg, args, device)
    export_model = teacher if teacher is not None and bool(args.export_teacher_features) else model
    features = export_month_features(export_model, normalizer, month_df, feature_cols, physical_cols, args, device)
    fold = {
        "month": str(month_df["month"].iloc[0]) if not month_df.empty else "",
        "train_start_month": train_months[0] if train_months else "",
        "train_end_month": train_months[-1] if train_months else "",
        "train_rows": int(len(train_df)),
        "train_months": int(len(train_months)),
        "train_windows": int(len(ds)),
        "test_rows": int(len(month_df)),
        "feature_count": int(len(feature_cols)),
        "physical_feature_count": int(len(physical_cols)),
        "context_valid_rate": float(features[f"{str(args.feature_prefix).strip() or 'ptdj'}_context_valid"].mean()) if not features.empty else 0.0,
        **{f"train_{k}": v for k, v in train_eval.items()},
    }
    fold["last_epoch_total"] = float(history[-1]["total"]) if history else float("nan")
    return features, fold


def consolidate_chunks(output_dir: Path, original_df: pd.DataFrame, feature_names: list[str], output_data: str | None) -> None:
    chunk_dir = output_dir / "feature_chunks"
    chunks = sorted(chunk_dir.glob("*.parquet")) if chunk_dir.exists() else []
    if not chunks:
        return
    feat = pd.concat([pd.read_parquet(p) for p in chunks], ignore_index=True)
    key_cols = ["ticker", "trade_date", "expiration", "expiry_mode", "timestamp", "time"]
    feat = feat.drop_duplicates(key_cols, keep="last")
    feat.to_parquet(output_dir / "oof_event_phys_td_jepa_features.parquet", index=False)
    if output_data:
        merged = original_df.merge(feat[key_cols + feature_names], on=key_cols, how="left")
        for col in feature_names:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0).astype(np.float32)
        Path(output_data).parent.mkdir(parents=True, exist_ok=True)
        merged.to_parquet(output_data, index=False)


def write_summary(output_dir: Path, metadata: dict, folds: list[dict], feature_rows: int) -> None:
    fold_df = pd.DataFrame(folds)
    lines = [
        "# Event Phys-TD-JEPA OOF Features",
        "",
        "Each exported month is encoded by a model trained only on earlier months. The encoder is self-supervised and uses no option outcome labels.",
        "",
        f"- Feature rows: `{feature_rows}`",
        f"- Completed folds: `{len(folds)}`",
        "",
        "## Folds",
        "",
        "```csv",
        fold_df.to_csv(index=False) if not fold_df.empty else "",
        "```",
        "",
        "## Metadata",
        "",
        "```json",
        json.dumps(metadata, indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def load_done(output_dir: Path, resume: bool) -> tuple[list[dict], set[str]]:
    folds_path = output_dir / "fold_configs.csv"
    if not resume or not folds_path.exists():
        return [], set()
    fold_df = pd.read_csv(folds_path, dtype={"month": str})
    rows = fold_df.to_dict("records")
    done = {str(r["month"]) for r in rows}
    return rows, done


def main() -> int:
    parser = argparse.ArgumentParser(description="Export causal OOF Phys-TD-JEPA features for event-option rows.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-data", default="")
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"], help="Rows to export.")
    parser.add_argument("--train-tickers", nargs="*", default=[], help="Optional tickers used to train the self-supervised encoder. Default uses all rows in --data after expiry filtering.")
    parser.add_argument("--expiry-modes", nargs="*", default=["zero_dte", "front_weekly"])
    parser.add_argument("--start-month", default="202407")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--min-train-months", type=int, default=4)
    parser.add_argument("--min-train-rows", type=int, default=2000)
    parser.add_argument("--context-len", type=int, default=6)
    parser.add_argument("--horizons", default="1,2,3,6")
    parser.add_argument("--z-dim", type=int, default=32)
    parser.add_argument("--phys-dim", type=int, default=12)
    parser.add_argument("--delta-dim", type=int, default=16)
    parser.add_argument("--horizon-dim", type=int, default=8)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.10)
    parser.add_argument("--max-physical-features", type=int, default=48)
    parser.add_argument("--lambda-state", type=float, default=0.20)
    parser.add_argument("--lambda-dyn", type=float, default=0.10)
    parser.add_argument("--lambda-proto", type=float, default=0.0, help="DINO/TDV-style prototype loss weight; 0 keeps the legacy objective.")
    parser.add_argument("--lambda-sigreg", type=float, default=0.05)
    parser.add_argument("--lambda-vicreg", type=float, default=0.10)
    parser.add_argument("--use-ema-teacher", action="store_true", help="Use an EMA teacher for temporal prediction targets.")
    parser.add_argument("--teacher-momentum", type=float, default=0.996)
    parser.add_argument("--export-teacher-features", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--proto-prototypes", type=int, default=256)
    parser.add_argument("--proto-teacher-temp", type=float, default=0.07)
    parser.add_argument("--proto-student-temp", type=float, default=0.10)
    parser.add_argument("--proto-center-momentum", type=float, default=0.90)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--infer-batch-size", type=int, default=4096)
    parser.add_argument("--lr", type=float, default=7e-4)
    parser.add_argument("--weight-decay", type=float, default=2e-2)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--clip", type=float, default=10.0)
    parser.add_argument("--sigreg-projections", type=int, default=64)
    parser.add_argument("--vicreg-min-std", type=float, default=0.75)
    parser.add_argument("--normalizer-mode", choices=("global", "ticker"), default="global", help="Fit robust feature statistics globally or independently per ticker within each causal fold.")
    parser.add_argument("--encoder-input-mode", choices=("flat", "modal"), default="flat", help="Use the legacy flat feature encoder or modality-balanced input projections.")
    parser.add_argument("--modal-token-dim", type=int, default=32, help="Per-modality projection width when --encoder-input-mode modal is active.")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--seed", type=int, default=20260618)
    parser.add_argument("--feature-prefix", default="ptdj")
    parser.add_argument("--group-expiry-mode", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--export-deploy-model", action="store_true")
    parser.add_argument("--deploy-month", default="")
    parser.add_argument("--deploy-train-end-month", default="", help="Latest completed YYYYMM allowed in deploy encoder training.")
    parser.add_argument("--deploy-output-dir", default="", help="Optional explicit deploy_model output directory.")
    parser.add_argument("--skip-oof", action="store_true", help="Skip OOF feature export and only run requested deploy export.")
    args = parser.parse_args()

    set_seed(int(args.seed))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    chunk_dir = output_dir / "feature_chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)

    full = pd.read_parquet(args.data)
    train_tickers = [str(t).upper() for t in args.train_tickers]
    train_frame = prepare_frame(args.data, train_tickers, args.expiry_modes)
    export_frame = prepare_frame(args.data, args.tickers, args.expiry_modes)
    feature_cols = select_feature_columns(train_frame)
    physical_cols = select_physical_columns(feature_cols, int(args.max_physical_features))
    feature_names = build_feature_names(args, physical_cols)
    modal_feature_groups = summarize_modal_feature_groups(feature_cols)
    metadata = {
        "args": vars(args),
        "input_rows": int(len(full)),
        "train_rows_after_filter": int(len(train_frame)),
        "export_rows_after_filter": int(len(export_frame)),
        "feature_cols": feature_cols,
        "physical_cols": physical_cols,
        "feature_names": feature_names,
        "leaky_feature_names": [c for c in feature_cols if any(p in c.lower() for p in LEAKY_PATTERNS)],
        "modal_feature_group_counts": {name: len(cols) for name, cols in modal_feature_groups.items()},
        "modal_feature_groups": modal_feature_groups,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    write_feature_names(output_dir / "jepa_feature_names.json", feature_names)

    fold_rows, done = load_done(output_dir, resume=not bool(args.no_resume))
    device = torch.device(args.device)
    if not bool(args.skip_oof):
        months = month_range(str(args.start_month), str(args.end_month))
        for test_month in months:
            chunk_path = chunk_dir / f"{test_month}.parquet"
            if test_month in done and chunk_path.exists() and not bool(args.no_resume):
                print(f"[resume] skip month={test_month}")
                continue
            train = train_frame[train_frame["month"].astype(str) < str(test_month)].copy()
            train_months = sorted(train["month"].astype(str).unique().tolist())
            month_df = export_frame[export_frame["month"].astype(str) == str(test_month)].copy()
            if len(train_months) < int(args.min_train_months) or len(train) < int(args.min_train_rows) or month_df.empty:
                print(f"[skip] month={test_month} train_months={len(train_months)} train_rows={len(train)} export_rows={len(month_df)}")
                continue
            print(f"[fold] month={test_month} train_rows={len(train)} export_rows={len(month_df)} device={device}")
            features, fold = train_fold(train, month_df, feature_cols, physical_cols, args, device)
            features.to_parquet(chunk_path, index=False)
            fold_rows = [r for r in fold_rows if str(r.get("month")) != str(test_month)]
            fold_rows.append(fold)
            fold_df = pd.DataFrame(fold_rows).sort_values("month")
            fold_df.to_csv(output_dir / "fold_configs.csv", index=False)
            write_summary(output_dir, metadata, fold_rows, int(sum(len(pd.read_parquet(p, columns=["ticker"])) for p in chunk_dir.glob("*.parquet"))))
        consolidate_chunks(output_dir, full, feature_names, args.output_data or None)
        feature_path = output_dir / "oof_event_phys_td_jepa_features.parquet"
        feature_rows = int(len(pd.read_parquet(feature_path, columns=["ticker"]))) if feature_path.exists() else 0
    else:
        feature_rows = 0
    write_summary(output_dir, metadata, fold_rows, feature_rows)
    if bool(args.export_deploy_model):
        export_deploy_model(output_dir, train_frame, feature_cols, physical_cols, feature_names, args, device)
    print(f"[done] output_dir={output_dir} feature_rows={feature_rows} output_data={args.output_data}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
