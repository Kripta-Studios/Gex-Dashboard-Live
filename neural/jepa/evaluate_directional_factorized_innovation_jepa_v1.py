#!/usr/bin/env python3
"""Factorized innovation-JEPA diagnostic on the frozen price-only panel."""

from __future__ import annotations

import argparse
import copy
import json
import math
from dataclasses import asdict
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

from neural.jepa import evaluate_directional_semantic_jepa_v1 as base
from neural.jepa.sigreg import VISRegLoss, latent_diagnostics


PREDECLARATION = (
    base.REPO_ROOT
    / "research_papers/JEPA/DIRECTIONAL_FACTORIZED_INNOVATION_JEPA_V1_PREDECLARATION.md"
)
DEFAULT_DEVELOPMENT_OUTPUT = (
    base.REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "directional_factorized_innovation_jepa_v1_development_202208_202512"
)
DEFAULT_EVALUATION_OUTPUT = (
    base.REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "directional_factorized_innovation_jepa_v1_evaluation_202601_20260715"
)

COMMON_DIM = 8
RESIDUAL_DIM = 4
VOLATILITY_DIM = 4
BLOCK_SLICES = {
    "common": slice(0, 8),
    "qqq_residual": slice(8, 12),
    "spxw_residual": slice(12, 16),
    "spy_residual": slice(16, 20),
    "volatility": slice(20, 24),
}
RAW_SUMMARY_CHANNELS = {"ret1": 0, "range": 1, "body": 2, "versus_open": 4}
HEALTH_MIN_RANK_RATIO = 0.40
HEALTH_MAX_PC_RATIO = 0.70


class BlockEncoder(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int) -> None:
        super().__init__()
        self.gru = nn.GRU(input_dim, hidden_dim, batch_first=True)
        self.projection = nn.Sequential(
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, output_dim),
        )

    def forward(self, sequence: torch.Tensor) -> torch.Tensor:
        _, hidden = self.gru(sequence)
        return self.projection(hidden[-1])


class FactorizedEncoder(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.common = BlockEncoder(7, 32, COMMON_DIM)
        self.residuals = nn.ModuleList(
            [BlockEncoder(8, 24, RESIDUAL_DIM) for _ in base.SOURCE_TICKERS]
        )
        self.volatility = BlockEncoder(13, 24, VOLATILITY_DIM)

    def forward(self, sequence: torch.Tensor) -> torch.Tensor:
        raw = sequence[..., : base.RAW_CHANNELS].reshape(
            *sequence.shape[:2], len(base.SOURCE_TICKERS), base.RAW_CHANNELS_PER_TICKER
        )
        time_mask = sequence[..., base.RAW_CHANNELS : base.RAW_CHANNELS + 1]
        ticker_masks = sequence[..., base.RAW_CHANNELS + 1 :]
        common_raw = raw.mean(dim=2)
        common = self.common(torch.cat([common_raw, time_mask], dim=-1))
        residuals = []
        for ticker_index, encoder in enumerate(self.residuals):
            residual_input = torch.cat(
                [
                    raw[:, :, ticker_index, :] - common_raw,
                    time_mask,
                    ticker_masks[:, :, ticker_index : ticker_index + 1],
                ],
                dim=-1,
            )
            residuals.append(encoder(residual_input))
        volatility_raw = torch.stack(
            [raw[..., 0].abs(), raw[..., 1], raw[..., 2].abs(), raw[..., 5]],
            dim=-1,
        ).flatten(start_dim=2)
        volatility = self.volatility(torch.cat([volatility_raw, time_mask], dim=-1))
        latent = torch.cat([common, *residuals, volatility], dim=-1)
        if latent.shape[-1] != base.LATENT_DIM:
            raise AssertionError("factorized latent dimension mismatch")
        return latent


class FactorizedInnovationJEPA(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.encoder = FactorizedEncoder()
        self.innovation_predictors = nn.ModuleList(
            [self._predictor(base.LATENT_DIM) for _ in base.HORIZONS]
        )
        self.raw_predictors = nn.ModuleList(
            [self._predictor(base.RAW_CHANNELS) for _ in base.HORIZONS]
        )

    @staticmethod
    def _predictor(output_dim: int) -> nn.Sequential:
        return nn.Sequential(
            nn.Linear(base.LATENT_DIM, base.HIDDEN_DIM),
            nn.GELU(),
            nn.Linear(base.HIDDEN_DIM, output_dim),
        )

    def predict_innovations(self, latent: torch.Tensor) -> torch.Tensor:
        return torch.stack(
            [predictor(latent) for predictor in self.innovation_predictors], dim=1
        )

    def predict_latents(self, latent: torch.Tensor) -> torch.Tensor:
        return latent[:, None, :] + self.predict_innovations(latent)

    def predict_raw_innovations(self, latent: torch.Tensor) -> torch.Tensor:
        return torch.stack([predictor(latent) for predictor in self.raw_predictors], dim=1)


FULL_VISREG = VISRegLoss(
    base.LATENT_DIM,
    num_slices=64,
    center_weight=1.0,
    scale_weight=1.0,
    shape_weight=2.0,
)
BLOCK_VISREG = {
    name: VISRegLoss(
        block.stop - block.start,
        num_slices=32,
        center_weight=1.0,
        scale_weight=1.0,
        shape_weight=2.0,
    )
    for name, block in BLOCK_SLICES.items()
}


def corrupt_student_context(context: torch.Tensor) -> torch.Tensor:
    corrupted = context.clone()
    batch, length, _ = corrupted.shape
    for sample in range(batch):
        block_length = int(torch.randint(6, 19, (1,), device=corrupted.device).item())
        start = int(
            torch.randint(0, length - block_length + 1, (1,), device=corrupted.device).item()
        )
        corrupted[sample, start : start + block_length, : base.RAW_CHANNELS] = 0.0
        corrupted[sample, start : start + block_length, base.RAW_CHANNELS] = 1.0
        if float(torch.rand((), device=corrupted.device)) < 0.50:
            ticker_index = int(
                torch.randint(0, len(base.SOURCE_TICKERS), (1,), device=corrupted.device).item()
            )
            left = ticker_index * base.RAW_CHANNELS_PER_TICKER
            right = left + base.RAW_CHANNELS_PER_TICKER
            corrupted[sample, :, left:right] = 0.0
            corrupted[sample, :, base.RAW_CHANNELS + 1 + ticker_index] = 1.0
        if float(torch.rand((), device=corrupted.device)) < 0.50:
            modality = int(
                torch.randint(0, base.RAW_CHANNELS_PER_TICKER, (1,), device=corrupted.device).item()
            )
            for ticker_index in range(len(base.SOURCE_TICKERS)):
                corrupted[
                    sample,
                    :,
                    ticker_index * base.RAW_CHANNELS_PER_TICKER + modality,
                ] = 0.0
    return corrupted


def _visreg_loss(latent: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    full = FULL_VISREG(latent)
    blocks = torch.stack(
        [BLOCK_VISREG[name](latent[:, block]) for name, block in BLOCK_SLICES.items()]
    ).mean()
    return full, blocks


def jepa_batch_loss(
    model: FactorizedInnovationJEPA,
    teacher: FactorizedEncoder,
    context: torch.Tensor,
    targets: torch.Tensor,
    *,
    corrupt: bool,
) -> tuple[torch.Tensor, dict[str, float]]:
    student_input = corrupt_student_context(context) if corrupt else context
    latent = model.encoder(student_input)
    batch, horizons, length, channels = targets.shape
    future_student = model.encoder(targets.reshape(batch * horizons, length, channels)).reshape(
        batch, horizons, base.LATENT_DIM
    )
    with torch.no_grad():
        teacher_current = teacher(context)
        teacher_future = teacher(targets.reshape(batch * horizons, length, channels)).reshape(
            batch, horizons, base.LATENT_DIM
        )
        target_innovation = teacher_future - teacher_current[:, None, :]
        raw_target = (
            targets[:, :, -1, : base.RAW_CHANNELS]
            - context[:, None, -1, : base.RAW_CHANNELS]
        )
    latent_prediction = F.smooth_l1_loss(
        model.predict_innovations(latent), target_innovation
    )
    raw_prediction = F.smooth_l1_loss(model.predict_raw_innovations(latent), raw_target)
    alignment = 0.5 * (
        F.smooth_l1_loss(latent, teacher_current)
        + F.smooth_l1_loss(future_student, teacher_future)
    )
    regularized_states = torch.cat([latent, future_student.flatten(0, 1)], dim=0)
    visreg_full, visreg_blocks = _visreg_loss(regularized_states)
    total = (
        latent_prediction
        + 0.50 * raw_prediction
        + 0.25 * alignment
        + 0.20 * visreg_full
        + 0.10 * visreg_blocks
    )
    metrics = {
        "total": float(total.detach()),
        "latent_prediction": float(latent_prediction.detach()),
        "raw_prediction": float(raw_prediction.detach()),
        "alignment": float(alignment.detach()),
        "visreg_full": float(visreg_full.detach()),
        "visreg_blocks": float(visreg_blocks.detach()),
    }
    return total, metrics


def _run_loader(
    model: FactorizedInnovationJEPA,
    teacher: FactorizedEncoder,
    loader: DataLoader,
    device: torch.device,
    *,
    training: bool,
    optimizer: torch.optim.Optimizer | None = None,
) -> dict[str, float]:
    model.train(training)
    teacher.eval()
    totals: dict[str, float] = {}
    rows = 0
    for context, targets in loader:
        context = context.to(device=device, dtype=torch.float32)
        targets = targets.to(device=device, dtype=torch.float32)
        with torch.set_grad_enabled(training):
            loss, metrics = jepa_batch_loss(
                model, teacher, context, targets, corrupt=training
            )
            if training:
                if optimizer is None:
                    raise AssertionError("training requires optimizer")
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                base.update_teacher(teacher, model.encoder)
        for name, value in metrics.items():
            totals[name] = totals.get(name, 0.0) + value * len(context)
        rows += len(context)
    return {name: value / max(1, rows) for name, value in totals.items()}


def train_jepa_selection(
    train_dataset: base.MarketWindowDataset,
    validation_dataset: base.MarketWindowDataset,
    device: torch.device,
) -> base.JepaTrainingResult:
    base.set_seed()
    model = FactorizedInnovationJEPA().to(device)
    teacher = copy.deepcopy(model.encoder).to(device).eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    optimizer = torch.optim.AdamW(model.parameters(), lr=7e-4, weight_decay=0.02)
    train_loader = DataLoader(
        train_dataset, batch_size=base.BATCH_SIZE, shuffle=True, num_workers=0
    )
    validation_loader = DataLoader(
        validation_dataset, batch_size=base.BATCH_SIZE, shuffle=False, num_workers=0
    )
    best_loss = math.inf
    best_epoch = 0
    best_state: dict | None = None
    history: list[dict] = []
    bad_epochs = 0
    for epoch in range(1, base.MAX_EPOCHS + 1):
        train_metrics = _run_loader(
            model, teacher, train_loader, device, training=True, optimizer=optimizer
        )
        validation_metrics = _run_loader(
            model, teacher, validation_loader, device, training=False
        )
        row = {
            "epoch": epoch,
            **{f"train_{key}": value for key, value in train_metrics.items()},
            **{f"validation_{key}": value for key, value in validation_metrics.items()},
        }
        history.append(row)
        print(json.dumps({"phase": "jepa_selection", **row}), flush=True)
        validation_loss = validation_metrics["total"]
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
        raise AssertionError("factorized JEPA selection produced no checkpoint")
    return base.JepaTrainingResult(best_epoch, float(best_loss), best_state, history)


def final_fit_jepa(
    dataset: base.MarketWindowDataset, epochs: int, device: torch.device
) -> dict:
    base.set_seed()
    model = FactorizedInnovationJEPA().to(device)
    teacher = copy.deepcopy(model.encoder).to(device).eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    optimizer = torch.optim.AdamW(model.parameters(), lr=7e-4, weight_decay=0.02)
    loader = DataLoader(dataset, batch_size=base.BATCH_SIZE, shuffle=True, num_workers=0)
    for epoch in range(1, epochs + 1):
        metrics = _run_loader(
            model, teacher, loader, device, training=True, optimizer=optimizer
        )
        print(json.dumps({"phase": "jepa_final_fit", "epoch": epoch, **metrics}), flush=True)
    return {"model": model.state_dict(), "teacher": teacher.state_dict()}


def model_from_state(state: dict, device: torch.device) -> FactorizedInnovationJEPA:
    model = FactorizedInnovationJEPA().to(device)
    model.load_state_dict(state["model"])
    model.eval()
    return model


def latent_health(
    model: FactorizedInnovationJEPA,
    arrays_by_date: dict[str, np.ndarray],
    normalizer: base.Normalizer,
    device: torch.device,
) -> dict:
    current_rows = []
    delta_rows = []
    model.eval()
    with torch.no_grad():
        for day in sorted(arrays_by_date):
            normalized = normalizer.transform(arrays_by_date[day])
            current = torch.from_numpy(base.padded_context(normalized, 65)).unsqueeze(0)
            previous = torch.from_numpy(base.padded_context(normalized, 60)).unsqueeze(0)
            current_latent = model.encoder(current.to(device).float())
            previous_latent = model.encoder(previous.to(device).float())
            current_rows.append(current_latent.cpu())
            delta_rows.append((current_latent - previous_latent).cpu())
    z = torch.cat(current_rows, dim=0)
    dz = torch.cat(delta_rows, dim=0)
    full = {"z": latent_diagnostics(z), "dz": latent_diagnostics(dz)}
    blocks = {
        name: latent_diagnostics(z[:, block]) for name, block in BLOCK_SLICES.items()
    }
    checks = {
        "z_rank": full["z"]["effective_rank_ratio"] >= HEALTH_MIN_RANK_RATIO,
        "dz_rank": full["dz"]["effective_rank_ratio"] >= HEALTH_MIN_RANK_RATIO,
        "z_pc1": full["z"]["max_pc_var_ratio"] <= HEALTH_MAX_PC_RATIO,
        "dz_pc1": full["dz"]["max_pc_var_ratio"] <= HEALTH_MAX_PC_RATIO,
        "z_no_dead": full["z"]["near_zero_std_dims"] == 0,
        "dz_no_dead": full["dz"]["near_zero_std_dims"] == 0,
        **{
            f"{name}_rank": metrics["effective_rank_ratio"] >= HEALTH_MIN_RANK_RATIO
            for name, metrics in blocks.items()
        },
    }
    return {
        "thresholds": {
            "minimum_effective_rank_ratio": HEALTH_MIN_RANK_RATIO,
            "maximum_pc1_ratio": HEALTH_MAX_PC_RATIO,
        },
        "full": full,
        "blocks": blocks,
        "checks": checks,
        "pass": all(checks.values()),
    }


def semantic_feature_values(
    model: FactorizedInnovationJEPA,
    array: np.ndarray,
    normalizer: base.Normalizer,
    device: torch.device,
) -> dict[str, float]:
    normalized = normalizer.transform(array)
    current = torch.from_numpy(base.padded_context(normalized, 65)).unsqueeze(0).to(device)
    previous = torch.from_numpy(base.padded_context(normalized, 60)).unsqueeze(0).to(device)
    model.eval()
    with torch.no_grad():
        latent = model.encoder(current.float())
        previous_latent = model.encoder(previous.float())
        predicted_latents = model.predict_latents(latent)
        predicted_raw = model.predict_raw_innovations(latent)
    z = latent[0].cpu().numpy()
    dz = (latent - previous_latent)[0].cpu().numpy()
    future_z = predicted_latents[0].cpu().numpy()
    raw_delta = predicted_raw[0].cpu().numpy()
    values: dict[str, float] = {}
    for index, value in enumerate(z):
        values[f"jepa_z_{index:02d}"] = float(value)
    for index, value in enumerate(dz):
        values[f"jepa_dz_{index:02d}"] = float(value)
    for horizon_index, horizon in enumerate(base.HORIZONS):
        displacement = future_z[horizon_index] - z
        values[f"jepa_pred_displacement_{horizon}m"] = float(np.linalg.norm(displacement))
        denominator = max(
            1e-9, float(np.linalg.norm(future_z[horizon_index]) * np.linalg.norm(z))
        )
        values[f"jepa_pred_cosine_{horizon}m"] = float(
            np.dot(future_z[horizon_index], z) / denominator
        )
        for ticker_index, ticker in enumerate(base.SOURCE_TICKERS):
            for channel_name, local_channel in RAW_SUMMARY_CHANNELS.items():
                channel = ticker_index * base.RAW_CHANNELS_PER_TICKER + local_channel
                values[
                    f"jepa_pred_{ticker.lower()}_{channel_name}_delta_{horizon}m"
                ] = float(raw_delta[horizon_index, channel])
    return values


def build_daily_frame(
    sessions: dict[str, dict[str, pd.DataFrame]],
    arrays_by_date: dict[str, np.ndarray],
    model: FactorizedInnovationJEPA,
    normalizer: base.Normalizer,
    device: torch.device,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    dates = sorted(sessions)
    rows: list[dict] = []
    technical_features: list[str] | None = None
    semantic_features: list[str] | None = None
    for index, day in enumerate(dates):
        if index == 0 or day in base.HALF_DAYS:
            continue
        previous_day = dates[index - 1]
        semantic = semantic_feature_values(model, arrays_by_date[day], normalizer, device)
        if semantic_features is None:
            semantic_features = list(semantic)
        for ticker in base.SOURCE_TICKERS:
            row, features = base.build_technical_row(
                day, sessions[day], previous_day, sessions[previous_day], ticker
            )
            if technical_features is None:
                technical_features = features
            elif technical_features != features:
                raise AssertionError("technical feature order changed")
            row.update(semantic)
            rows.append(row)
    frame = pd.DataFrame(rows).sort_values(["ticker", "trade_date"], kind="stable")
    frame = frame.reset_index(drop=True)
    if frame.empty or technical_features is None or semantic_features is None:
        raise AssertionError("factorized daily frame is empty")
    features = technical_features + semantic_features
    if frame[features].isna().any().any() or not np.isfinite(frame[features]).all().all():
        raise AssertionError("factorized daily features contain non-finite values")
    return frame, technical_features, semantic_features


def _common_provenance(inventory: pd.DataFrame) -> dict:
    return {
        "schema": "directional_factorized_innovation_jepa_v1_provenance",
        "created_at_utc": base.utc_now(),
        "predeclaration_path": str(PREDECLARATION.relative_to(base.REPO_ROOT)),
        "predeclaration_sha256": base.sha256_file(PREDECLARATION),
        "runner_path": str(Path(__file__).resolve().relative_to(base.REPO_ROOT)),
        "runner_sha256": base.sha256_file(__file__),
        "parent_runner_sha256": base.sha256_file(Path(base.__file__)),
        "source_inventory_rows": int(len(inventory)),
        "source_inventory_sha256": base._source_inventory_digest(inventory),
        "source_kind": "existing_underlying_derived_minute_ohlc",
        "new_dataset_created": False,
        "adaptive_after_2026_parent_diagnosis": True,
        "production_modified": False,
    }


def _write_training_artifacts(
    output: Path,
    inventory: pd.DataFrame,
    selection: base.JepaTrainingResult,
    normalizer: base.Normalizer,
    state: dict,
    provenance: dict,
) -> None:
    output.mkdir(parents=True, exist_ok=False)
    inventory.to_csv(output / "source_inventory.csv", index=False, lineterminator="\n")
    pd.DataFrame(selection.history).to_csv(output / "jepa_training_history.csv", index=False)
    (output / "normalizer.json").write_text(
        json.dumps(asdict(normalizer), indent=2), encoding="utf-8"
    )
    torch.save(state, output / "factorized_innovation_jepa.pt")
    provenance["model_sha256"] = base.sha256_file(
        output / "factorized_innovation_jepa.pt"
    )
    provenance["normalizer_sha256"] = base.sha256_file(output / "normalizer.json")
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )


def run_development(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable development output exists: {output}")
    inventory = base.discover_source_files(Path(args.data_root), base.DEVELOPMENT_END)
    counts = inventory.groupby("ticker").size().to_dict()
    if counts != {ticker: 859 for ticker in base.SOURCE_TICKERS}:
        raise AssertionError(f"development source census mismatch: {counts}")
    usable = inventory.loc[~inventory["trade_date"].isin(base.INVALID_SOURCE_DAYS)]
    sessions = base.load_sessions(usable)
    dates = sorted(sessions)
    train_dates = [
        day for day in dates if day <= "20241231" and day not in base.HALF_DAYS
    ]
    validation_dates = [
        day for day in dates if day.startswith("2025") and day not in base.HALF_DAYS
    ]
    train_arrays, train_mapping = base._arrays_for_dates(sessions, train_dates)
    validation_arrays, validation_mapping = base._arrays_for_dates(sessions, validation_dates)
    normalizer = base.fit_normalizer(train_arrays)
    train_dataset = base.MarketWindowDataset(
        train_arrays, base.pretraining_positions(train_arrays), normalizer
    )
    validation_dataset = base.MarketWindowDataset(
        validation_arrays, base.pretraining_positions(validation_arrays), normalizer
    )
    device = torch.device(args.device)
    selection = train_jepa_selection(train_dataset, validation_dataset, device)
    all_arrays = train_arrays + validation_arrays
    final_normalizer = base.fit_normalizer(all_arrays)
    all_dataset = base.MarketWindowDataset(
        all_arrays, base.pretraining_positions(all_arrays), final_normalizer
    )
    final_state = final_fit_jepa(all_dataset, selection.best_epoch, device)
    model = model_from_state(final_state, device)
    arrays_by_date = {**train_mapping, **validation_mapping}
    health = latent_health(model, arrays_by_date, final_normalizer, device)
    provenance = _common_provenance(inventory)
    _write_training_artifacts(
        output, inventory, selection, final_normalizer, final_state, provenance
    )
    base_metrics = {
        "schema": "directional_factorized_innovation_jepa_v1_development_metrics",
        "created_at_utc": base.utc_now(),
        "scope": {"start_date": base.START_DATE, "end_date": base.DEVELOPMENT_END},
        "source_sessions_by_ticker": counts,
        "jepa": {
            "best_epoch": selection.best_epoch,
            "best_validation_loss": selection.validation_loss,
            "train_windows": len(train_dataset),
            "validation_windows": len(validation_dataset),
            "final_windows": len(all_dataset),
        },
        "latent_health": health,
        "holdout_2026_used_for_training_or_profile_selection": False,
        "adaptive_design_after_parent_2026_diagnosis": True,
        "production_modified": False,
    }
    if not health["pass"]:
        metrics = {**base_metrics, "status": "CLOSED_LATENT_HEALTH"}
        metrics["provenance_sha256"] = base.sha256_file(output / "provenance.json")
        (output / "metrics.json").write_text(
            json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
        )
        print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
        return metrics
    daily, technical_features, semantic_features = build_daily_frame(
        sessions, arrays_by_date, model, final_normalizer, device
    )
    months = [f"2025{month:02d}" for month in range(1, 13)]
    trades = base.run_walkforward(
        daily,
        months,
        technical_features,
        semantic_features,
        include_controls=True,
    )
    selections, ranking = base.select_profiles(trades)
    monthly = base.monthly_metrics(trades)
    metrics = {
        **base_metrics,
        "status": "PASS_DEVELOPMENT_FREEZE",
        "development_months": months,
        "daily_rows": int(len(daily)),
        "technical_feature_count": len(technical_features),
        "semantic_feature_count": len(semantic_features),
        "selected_profiles": selections,
    }
    trades.to_parquet(output / "development_trade_ledger.parquet", index=False)
    monthly.to_csv(output / "development_monthly_metrics.csv", index=False)
    ranking.to_csv(output / "profile_ranking.csv", index=False)
    (output / "technical_features.json").write_text(
        json.dumps(technical_features, indent=2), encoding="utf-8"
    )
    (output / "semantic_features.json").write_text(
        json.dumps(semantic_features, indent=2), encoding="utf-8"
    )
    metrics["provenance_sha256"] = base.sha256_file(output / "provenance.json")
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
    return metrics


def _load_development(
    development_dir: Path, device: torch.device
) -> tuple[dict, dict, base.Normalizer, FactorizedInnovationJEPA, list[str], list[str]]:
    metrics = json.loads((development_dir / "metrics.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (development_dir / "provenance.json").read_text(encoding="utf-8")
    )
    if metrics.get("status") != "PASS_DEVELOPMENT_FREEZE":
        raise AssertionError("development did not pass latent health and freeze")
    if provenance.get("predeclaration_sha256") != base.sha256_file(PREDECLARATION):
        raise AssertionError("predeclaration changed after development")
    if provenance.get("runner_sha256") != base.sha256_file(__file__):
        raise AssertionError("runner changed after development")
    if provenance.get("parent_runner_sha256") != base.sha256_file(Path(base.__file__)):
        raise AssertionError("parent runner changed after development")
    if provenance.get("model_sha256") != base.sha256_file(
        development_dir / "factorized_innovation_jepa.pt"
    ):
        raise AssertionError("factorized model hash mismatch")
    normalizer_payload = json.loads(
        (development_dir / "normalizer.json").read_text(encoding="utf-8")
    )
    normalizer = base.Normalizer(
        tuple(normalizer_payload["median"]), tuple(normalizer_payload["scale"])
    )
    state = torch.load(
        development_dir / "factorized_innovation_jepa.pt",
        map_location=device,
        weights_only=True,
    )
    model = model_from_state(state, device)
    technical = json.loads(
        (development_dir / "technical_features.json").read_text(encoding="utf-8")
    )
    semantic = json.loads(
        (development_dir / "semantic_features.json").read_text(encoding="utf-8")
    )
    return metrics, provenance, normalizer, model, technical, semantic


def _verify_development_sources(
    inventory: pd.DataFrame, development_dir: Path, provenance: dict
) -> None:
    frozen = pd.read_csv(development_dir / "source_inventory.csv", dtype={"trade_date": str})
    current = inventory.loc[inventory["trade_date"] <= base.DEVELOPMENT_END].reset_index(
        drop=True
    )
    columns = ["ticker", "trade_date", "path", "size_bytes", "sha256"]
    if not frozen[columns].astype(str).equals(current[columns].astype(str)):
        raise AssertionError("pre-2026 source inventory changed")
    if provenance.get("source_inventory_sha256") != base._source_inventory_digest(current):
        raise AssertionError("pre-2026 source digest changed")


def run_evaluation(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable evaluation output exists: {output}")
    development_dir = Path(args.development_dir)
    device = torch.device(args.device)
    development, frozen_provenance, normalizer, model, technical, semantic = (
        _load_development(development_dir, device)
    )
    inventory = base.discover_source_files(Path(args.data_root), base.EVALUATION_END)
    counts = inventory.groupby("ticker").size().to_dict()
    if counts != {ticker: 992 for ticker in base.SOURCE_TICKERS}:
        raise AssertionError(f"evaluation source census mismatch: {counts}")
    _verify_development_sources(inventory, development_dir, frozen_provenance)
    usable = inventory.loc[~inventory["trade_date"].isin(base.INVALID_SOURCE_DAYS)]
    sessions = base.load_sessions(usable)
    _, arrays_by_date = base._arrays_for_dates(sessions, sorted(sessions))
    daily, observed_technical, observed_semantic = build_daily_frame(
        sessions, arrays_by_date, model, normalizer, device
    )
    if observed_technical != technical or observed_semantic != semantic:
        raise AssertionError("evaluation feature contract changed")
    months = [f"2026{month:02d}" for month in range(1, 8)]
    selected = {
        str(key): str(value) for key, value in development["selected_profiles"].items()
    }
    trades = base.run_walkforward(
        daily,
        months,
        technical,
        semantic,
        profiles_by_ticker=selected,
        include_controls=False,
    )
    complete_months = months[:6]
    gate = base.evaluate_complete_month_gate(trades, complete_months)
    monthly = base.monthly_metrics(trades)
    july = monthly.loc[monthly["month"].eq("202607")].copy()
    july["month"] = "202607_MTD"
    metrics = {
        "schema": "directional_factorized_innovation_jepa_v1_evaluation_metrics",
        "status": (
            "ADAPTIVE_DIAGNOSTIC_GATE_PASS"
            if gate["joint_gate_pass"]
            else "CLOSED_ADAPTIVE_DIAGNOSTIC_GATE"
        ),
        "created_at_utc": base.utc_now(),
        "scope": {
            "start_date": "20260101",
            "end_date": base.EVALUATION_END,
            "complete_months": complete_months,
            "july_status": "MTD",
        },
        "selected_profiles": selected,
        "source_sessions_by_ticker": counts,
        "execution": {
            "decision_time": base.DECISION_TIME,
            "entry_time": base.ENTRY_TIME,
            "exit_time": base.EXIT_TIME,
            "hold_minutes": base.HOLD_MINUTES,
            "cost_bps": base.COST_BPS,
            "overlap_count": 0,
            "fill_kind": "underlying_open_spot_proxy_not_futures_fill",
        },
        **gate,
        "july_mtd": july.to_dict("records"),
        "confirmatory_evidence": False,
        "adaptive_after_parent_2026_diagnosis": True,
        "production_modified": False,
    }
    provenance = _common_provenance(inventory)
    provenance.update(
        {
            "development_metrics_sha256": base.sha256_file(
                development_dir / "metrics.json"
            ),
            "development_model_sha256": base.sha256_file(
                development_dir / "factorized_innovation_jepa.pt"
            ),
        }
    )
    output.mkdir(parents=True, exist_ok=False)
    inventory.to_csv(output / "source_inventory.csv", index=False, lineterminator="\n")
    trades.to_parquet(output / "trade_ledger.parquet", index=False)
    monthly.to_csv(output / "monthly_metrics.csv", index=False)
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    metrics["provenance_sha256"] = base.sha256_file(output / "provenance.json")
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("development", "evaluation"), required=True)
    parser.add_argument("--data-root", default=str(base.DEFAULT_DATA_ROOT))
    parser.add_argument("--development-dir", default=str(DEFAULT_DEVELOPMENT_OUTPUT))
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--device", default="cuda" if torch.cuda.is_available() else "cpu"
    )
    args = parser.parse_args()
    if not args.output:
        args.output = str(
            DEFAULT_DEVELOPMENT_OUTPUT
            if args.phase == "development"
            else DEFAULT_EVALUATION_OUTPUT
        )
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
