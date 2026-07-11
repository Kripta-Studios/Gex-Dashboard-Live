from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

if __package__:
    from .evaluate_xinput_level_filter import month_add, month_range
    from .walkforward_event_option_gate import DeployConfig, build_fold_grid, deploy, metrics, score_metrics
else:
    from evaluate_xinput_level_filter import month_add, month_range
    from walkforward_event_option_gate import DeployConfig, build_fold_grid, deploy, metrics, score_metrics


TICKERS = ("SPXW", "QQQ", "SPY")
DELTA_BY_TICKER = {"SPXW": 25, "QQQ": 35, "SPY": 35}
DAILY_CAPS = {"SPXW": 4, "QQQ": 2, "SPY": 1}
COOLDOWNS = {"SPXW": 0, "QQQ": 30, "SPY": 0}
SUMMARY_FEATURES = (
    "ptdj_latent_velocity",
    "ptdj_input_delta_norm",
    "ptdj_motion_norm_h1",
    "ptdj_pred_dispersion",
    "ptdj_phys_transition_norm_h1",
    "ptdj_lagged_pred_h1_err",
)
CONTRACT_SUFFIXES = (
    "strike_bps",
    "abs_delta",
    "iv",
    "mid_bps",
    "spread_pct",
    "theta_over_mid",
    "vega",
    "oi",
    "volume",
)


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest().upper()


def month_seed(base_seed: int, month: str) -> int:
    return int(base_seed) + int(str(month))


def seed_everything(seed: int, *, deterministic: bool, device: str) -> None:
    random.seed(int(seed))
    np.random.seed(int(seed) % (2**32 - 1))
    torch.manual_seed(int(seed))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(seed))
    if deterministic:
        if str(device).startswith("cuda") and os.environ.get("CUBLAS_WORKSPACE_CONFIG") not in {
            ":4096:8",
            ":16:8",
        }:
            raise RuntimeError("deterministic CUDA requires CUBLAS_WORKSPACE_CONFIG=:4096:8 or :16:8")
        torch.use_deterministic_algorithms(True)
        if torch.backends.cudnn.is_available():
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True


def gaussian_kl_diag(
    q_mu: torch.Tensor,
    q_logvar: torch.Tensor,
    p_mu: torch.Tensor,
    p_logvar: torch.Tensor,
) -> torch.Tensor:
    """KL(q || p) for diagonal Gaussians, reduced only across latent dimensions."""
    q_logvar = q_logvar.clamp(-12.0, 8.0)
    p_logvar = p_logvar.clamp(-12.0, 8.0)
    ratio = torch.exp(q_logvar - p_logvar)
    mean_term = (q_mu - p_mu).square() * torch.exp(-p_logvar)
    return 0.5 * (p_logvar - q_logvar + ratio + mean_term - 1.0).sum(dim=-1)


class PayoffBackbone(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, dropout: float) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.SiLU(),
            nn.Dropout(dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class DeterministicPayoffHead(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 128, latent_dim: int = 16, dropout: float = 0.1) -> None:
        super().__init__()
        self.backbone = PayoffBackbone(input_dim, hidden_dim, dropout)
        self.latent = nn.Linear(hidden_dim, latent_dim)
        self.decoder = nn.Sequential(nn.Linear(latent_dim, hidden_dim), nn.SiLU(), nn.Linear(hidden_dim, 1))

    def encode(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        mu = self.latent(self.backbone(x))
        return mu, torch.zeros_like(mu)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        mu, _ = self.encode(x)
        return self.decoder(mu).squeeze(-1)

    def loss(self, x: torch.Tensor, y: torch.Tensor, _beta: float = 0.0) -> dict[str, torch.Tensor]:
        prediction = self(x)
        reconstruction = torch.mean((prediction - y).square())
        zero = reconstruction.detach() * 0.0
        return {"total": reconstruction, "reconstruction": reconstruction, "kl": zero}


class VariationalPayoffHead(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 128, latent_dim: int = 16, dropout: float = 0.1) -> None:
        super().__init__()
        self.backbone = PayoffBackbone(input_dim, hidden_dim, dropout)
        self.prior = nn.Linear(hidden_dim, 2 * latent_dim)
        self.posterior = nn.Sequential(
            nn.Linear(hidden_dim + 1, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, 2 * latent_dim),
        )
        self.decoder = nn.Sequential(nn.Linear(latent_dim, hidden_dim), nn.SiLU(), nn.Linear(hidden_dim, 1))

    @staticmethod
    def _stats(raw: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        mu, logvar = raw.chunk(2, dim=-1)
        return mu, logvar.clamp(-8.0, 4.0)

    def encode(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        hidden = self.backbone(x)
        return self._stats(self.prior(hidden))

    def loss(self, x: torch.Tensor, y: torch.Tensor, beta: float) -> dict[str, torch.Tensor]:
        hidden = self.backbone(x)
        p_mu, p_logvar = self._stats(self.prior(hidden))
        q_mu, q_logvar = self._stats(self.posterior(torch.cat([hidden, y[:, None]], dim=-1)))
        q_z = q_mu + torch.randn_like(q_mu) * torch.exp(0.5 * q_logvar)
        p_z = p_mu + torch.randn_like(p_mu) * torch.exp(0.5 * p_logvar)
        q_prediction = self.decoder(q_z).squeeze(-1)
        p_prediction = self.decoder(p_z).squeeze(-1)
        reconstruction = 0.5 * (
            torch.mean((q_prediction - y).square()) + torch.mean((p_prediction - y).square())
        )
        kl = gaussian_kl_diag(q_mu, q_logvar, p_mu, p_logvar).mean()
        return {"total": reconstruction + float(beta) * kl, "reconstruction": reconstruction, "kl": kl}

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        p_mu, _ = self.encode(x)
        return self.decoder(p_mu).squeeze(-1)


@dataclass
class Preprocessor:
    features: list[str]
    medians: np.ndarray
    means: np.ndarray
    scales: np.ndarray

    @classmethod
    def fit(cls, frame: pd.DataFrame, features: list[str]) -> "Preprocessor":
        numeric = frame[features].replace([np.inf, -np.inf], np.nan).astype(float)
        medians = numeric.median(axis=0).fillna(0.0)
        filled = numeric.fillna(medians).fillna(0.0)
        means = filled.mean(axis=0)
        scales = filled.std(axis=0, ddof=0).replace(0.0, 1.0).fillna(1.0)
        return cls(
            features=list(features),
            medians=medians.to_numpy(dtype=np.float32),
            means=means.to_numpy(dtype=np.float32),
            scales=scales.to_numpy(dtype=np.float32),
        )

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        numeric = frame[self.features].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=np.float32, copy=True)
        missing = ~np.isfinite(numeric)
        if missing.any():
            numeric[missing] = np.broadcast_to(self.medians, numeric.shape)[missing]
        return ((numeric - self.means) / self.scales).astype(np.float32, copy=False)

    def to_json(self) -> dict[str, Any]:
        return {
            "features": self.features,
            "medians": self.medians.astype(float).tolist(),
            "means": self.means.astype(float).tolist(),
            "scales": self.scales.astype(float).tolist(),
        }


def latent_feature_columns(columns: Iterable[str]) -> list[str]:
    available = set(columns)
    z_cols = sorted(col for col in available if col.startswith("ptdj_z_"))
    dz_cols = sorted(col for col in available if col.startswith("ptdj_dz_h1_"))
    summaries = [col for col in SUMMARY_FEATURES if col in available]
    if len(z_cols) != 32 or len(dz_cols) != 32 or len(summaries) != len(SUMMARY_FEATURES):
        raise RuntimeError(
            f"unexpected frozen Phys-TD feature contract: z={len(z_cols)}, dz={len(dz_cols)}, summaries={summaries}"
        )
    return z_cols + dz_cols + summaries


def required_source_columns(latent_cols: list[str]) -> list[str]:
    columns = [
        "ticker",
        "trade_date",
        "expiration",
        "expiry_mode",
        "dte_days",
        "timestamp",
        "minute",
        "option_price_mode",
        "ptdj_context_valid",
        *latent_cols,
    ]
    for ticker, delta in DELTA_BY_TICKER.items():
        del ticker
        for side in ("call", "put"):
            columns.extend(
                [
                    f"{side}_d{delta}_available",
                    f"{side}_d{delta}_opt_exit_ret",
                    f"{side}_d{delta}_opt_exit_minutes",
                    *[f"{side}_d{delta}_{suffix}" for suffix in CONTRACT_SUFFIXES],
                ]
            )
    return list(dict.fromkeys(columns))


def load_base_frame(path: str | Path) -> tuple[pd.DataFrame, list[str]]:
    path = Path(path)
    schema_cols = pq.ParquetFile(path).schema_arrow.names
    latent_cols = latent_feature_columns(schema_cols)
    requested = required_source_columns(latent_cols)
    missing = sorted(set(requested) - set(schema_cols))
    if missing:
        raise RuntimeError(f"dataset missing required columns: {missing}")
    frame = pd.read_parquet(path, columns=requested)
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["date"] = frame["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    frame["month"] = frame["date"].str[:6]
    if set(frame["ticker"]) != set(TICKERS):
        raise RuntimeError(f"unexpected tickers: {sorted(frame['ticker'].unique())}")
    if set(frame["option_price_mode"].astype(str)) != {"executable_quote"}:
        raise RuntimeError("dataset is not exclusively executable_quote")
    if set(frame["expiry_mode"].astype(str)) != {"zero_dte"} or set(pd.to_numeric(frame["dte_days"])) != {0}:
        raise RuntimeError("dataset is not exclusively zero_dte")
    if int(frame["date"].astype(int).max()) >= 20260601:
        raise RuntimeError("sealed June 2026 boundary violated")
    minute = pd.to_numeric(frame["minute"], errors="raise").astype(int)
    if minute.min() < 630 or minute.max() > 870 or not bool(((minute - 600) % 5 == 0).all()):
        raise RuntimeError("dataset violates 10:30-14:30 ET five-minute grid")
    frame = frame[pd.to_numeric(frame["ptdj_context_valid"], errors="coerce").fillna(0.0).gt(0.0)].copy()
    usable: list[pd.DataFrame] = []
    for ticker in TICKERS:
        delta = DELTA_BY_TICKER[ticker]
        part = frame[frame["ticker"].eq(ticker)].copy()
        label_cols: list[str] = []
        availability = np.ones(len(part), dtype=bool)
        for side in ("call", "put"):
            availability &= pd.to_numeric(part[f"{side}_d{delta}_available"], errors="coerce").eq(1).to_numpy()
            label_cols.extend([f"{side}_d{delta}_opt_exit_ret", f"{side}_d{delta}_opt_exit_minutes"])
        finite = np.isfinite(part[label_cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)).all(axis=1)
        part = part.loc[availability & finite].copy()
        holds = part[[f"call_d{delta}_opt_exit_minutes", f"put_d{delta}_opt_exit_minutes"]].astype(float)
        if len(holds) and float(holds.min().min()) < 30.0:
            raise RuntimeError(f"{ticker} contains an executable label with hold below 30 minutes")
        part["delta_bucket"] = int(delta)
        usable.append(part)
    result = pd.concat(usable, ignore_index=True).sort_values(["month", "ticker", "date", "minute"])
    result["event_id"] = np.arange(len(result), dtype=np.int64)
    return result.reset_index(drop=True), latent_cols


def build_action_frame(base: pd.DataFrame, latent_cols: list[str]) -> tuple[pd.DataFrame, list[str]]:
    pieces: list[pd.DataFrame] = []
    for ticker in TICKERS:
        delta = DELTA_BY_TICKER[ticker]
        source = base[base["ticker"].eq(ticker)].copy()
        for side in ("call", "put"):
            part = source.copy()
            part["action"] = side.upper()
            part["action_call"] = float(side == "call")
            part["target_return"] = pd.to_numeric(part[f"{side}_d{delta}_opt_exit_ret"], errors="raise")
            part["exit_minutes"] = pd.to_numeric(part[f"{side}_d{delta}_opt_exit_minutes"], errors="raise")
            for suffix in CONTRACT_SUFFIXES:
                values = pd.to_numeric(part[f"{side}_d{delta}_{suffix}"], errors="coerce")
                if suffix in {"oi", "volume"}:
                    values = np.log1p(values.clip(lower=0.0))
                part[f"contract_{suffix}"] = values.astype(float)
            pieces.append(part)
    result = pd.concat(pieces, ignore_index=True)
    result["minute_fraction"] = (pd.to_numeric(result["minute"], errors="raise") - 630.0) / 240.0
    result["delta_fraction"] = pd.to_numeric(result["delta_bucket"], errors="raise") / 100.0
    for ticker in TICKERS:
        result[f"ticker_{ticker}"] = result["ticker"].eq(ticker).astype(float)
    model_features = [
        *latent_cols,
        *[f"contract_{suffix}" for suffix in CONTRACT_SUFFIXES],
        "action_call",
        "minute_fraction",
        "delta_fraction",
        *[f"ticker_{ticker}" for ticker in TICKERS],
    ]
    forbidden = ("future", "return", "exit", "win", "status", "max_ret", "min_ret")
    leaked = [feature for feature in model_features if any(token in feature.lower() for token in forbidden)]
    if leaked:
        raise RuntimeError(f"outcome-like feature entered payoff head: {leaked}")
    return result.sort_values(["month", "ticker", "date", "minute", "action"]).reset_index(drop=True), model_features


def make_model(arm: str, input_dim: int, args: argparse.Namespace) -> nn.Module:
    kwargs = {
        "input_dim": int(input_dim),
        "hidden_dim": int(args.hidden_dim),
        "latent_dim": int(args.latent_dim),
        "dropout": float(args.dropout),
    }
    if arm == "deterministic":
        return DeterministicPayoffHead(**kwargs)
    if arm == "variational":
        return VariationalPayoffHead(**kwargs)
    raise ValueError(f"unknown arm: {arm}")


def train_model(
    train: pd.DataFrame,
    features: list[str],
    arm: str,
    seed: int,
    args: argparse.Namespace,
) -> tuple[nn.Module, Preprocessor, list[dict[str, float]]]:
    seed_everything(seed, deterministic=bool(args.deterministic), device=str(args.device))
    preprocessor = Preprocessor.fit(train, features)
    x = torch.from_numpy(preprocessor.transform(train))
    y = torch.from_numpy(
        pd.to_numeric(train["target_return"], errors="raise")
        .clip(-float(args.clip_return), float(args.clip_return))
        .to_numpy(dtype=np.float32)
    )
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    loader = DataLoader(
        TensorDataset(x, y),
        batch_size=int(args.batch_size),
        shuffle=True,
        num_workers=0,
        generator=generator,
        drop_last=False,
    )
    device = torch.device(str(args.device))
    model = make_model(arm, len(features), args).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    history: list[dict[str, float]] = []
    for epoch in range(int(args.epochs)):
        model.train()
        totals = {"total": 0.0, "reconstruction": 0.0, "kl": 0.0, "rows": 0}
        beta = 0.0
        if arm == "variational":
            beta = float(args.kl_weight) * min((epoch + 1) / max(int(args.kl_anneal_epochs), 1), 1.0)
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(device, non_blocking=True)
            batch_y = batch_y.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            losses = model.loss(batch_x, batch_y, beta)
            losses["total"].backward()
            nn.utils.clip_grad_norm_(model.parameters(), float(args.grad_clip))
            optimizer.step()
            rows = int(len(batch_x))
            totals["rows"] += rows
            for name in ("total", "reconstruction", "kl"):
                totals[name] += float(losses[name].detach().cpu()) * rows
        history.append(
            {
                "epoch": int(epoch + 1),
                "beta": float(beta),
                **{name: float(totals[name] / max(totals["rows"], 1)) for name in ("total", "reconstruction", "kl")},
            }
        )
    model.eval()
    return model, preprocessor, history


@torch.inference_mode()
def predict_actions(
    model: nn.Module,
    preprocessor: Preprocessor,
    frame: pd.DataFrame,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, np.ndarray]:
    if frame.empty:
        return frame.copy(), np.empty((0, int(args.latent_dim)), dtype=np.float32)
    x = torch.from_numpy(preprocessor.transform(frame))
    loader = DataLoader(TensorDataset(x), batch_size=int(args.infer_batch_size), shuffle=False, num_workers=0)
    predictions: list[np.ndarray] = []
    uncertainty: list[np.ndarray] = []
    latents: list[np.ndarray] = []
    device = torch.device(str(args.device))
    model.eval()
    for (batch_x,) in loader:
        batch_x = batch_x.to(device, non_blocking=True)
        mu, logvar = model.encode(batch_x)
        pred = model.decoder(mu).squeeze(-1)
        predictions.append(pred.detach().cpu().numpy())
        uncertainty.append(torch.exp(logvar).mean(dim=-1).detach().cpu().numpy())
        latents.append(mu.detach().cpu().numpy())
    out = frame.copy()
    out["pred_return"] = np.concatenate(predictions).astype(float)
    out["latent_uncertainty"] = np.concatenate(uncertainty).astype(float)
    return out, np.concatenate(latents).astype(np.float32)


def choose_action(scored_actions: pd.DataFrame) -> pd.DataFrame:
    if scored_actions.empty:
        return scored_actions.copy()
    ordered = scored_actions.sort_values(
        ["event_id", "pred_return", "action"], ascending=[True, False, True], kind="stable"
    )
    selected = ordered.drop_duplicates("event_id", keep="first").copy()
    selected["score"] = selected["pred_return"].astype(float)
    selected["realized_return"] = selected["target_return"].astype(float)
    return selected.sort_values(["ticker", "date", "minute"]).reset_index(drop=True)


def prediction_metrics(scored_actions: pd.DataFrame, train: pd.DataFrame) -> dict[str, float | int]:
    if scored_actions.empty:
        return {
            "rows": 0,
            "mae": float("nan"),
            "rmse": float("nan"),
            "directional_accuracy": float("nan"),
            "mae_to_train_mean_ratio": float("nan"),
            "uncertainty_error_spearman": float("nan"),
        }
    actual = pd.to_numeric(scored_actions["target_return"], errors="raise").to_numpy(dtype=float)
    predicted = pd.to_numeric(scored_actions["pred_return"], errors="raise").to_numpy(dtype=float)
    clipped = np.clip(actual, -2.0, 2.0)
    error = np.abs(predicted - clipped)
    train_means = train.groupby(["ticker", "action"])["target_return"].mean().to_dict()
    baseline = np.array(
        [float(train_means.get((ticker, action), 0.0)) for ticker, action in zip(scored_actions["ticker"], scored_actions["action"])],
        dtype=float,
    )
    baseline_mae = float(np.mean(np.abs(baseline - clipped)))
    uncertainty = pd.to_numeric(scored_actions["latent_uncertainty"], errors="coerce")
    uncertainty_values = uncertainty.to_numpy(dtype=float)
    if np.unique(error).size > 1 and np.unique(uncertainty_values[np.isfinite(uncertainty_values)]).size > 1:
        spearman = pd.Series(error).corr(pd.Series(uncertainty_values), method="spearman")
    else:
        spearman = float("nan")
    mae = float(np.mean(error))
    return {
        "rows": int(len(scored_actions)),
        "mae": mae,
        "rmse": float(np.sqrt(np.mean((predicted - clipped) ** 2))),
        "directional_accuracy": float(((predicted > 0.0) == (clipped > 0.0)).mean()),
        "mae_to_train_mean_ratio": float(mae / baseline_mae) if baseline_mae > 0.0 else float("nan"),
        "uncertainty_error_spearman": float(spearman) if pd.notna(spearman) else float("nan"),
    }


def effective_rank_metrics(latents: np.ndarray) -> dict[str, float]:
    if len(latents) < 2:
        return {"effective_rank_ratio": float("nan"), "max_pc_var_ratio": float("nan")}
    centered = latents.astype(np.float64) - latents.astype(np.float64).mean(axis=0, keepdims=True)
    singular = np.linalg.svd(centered, full_matrices=False, compute_uv=False)
    variance = singular**2
    if float(variance.sum()) <= 0.0:
        return {"effective_rank_ratio": 0.0, "max_pc_var_ratio": 1.0}
    weights = variance / variance.sum()
    entropy = -float(np.sum(weights[weights > 0.0] * np.log(weights[weights > 0.0])))
    return {
        "effective_rank_ratio": float(np.exp(entropy) / len(weights)),
        "max_pc_var_ratio": float(weights.max()),
    }


def select_threshold(
    scored: pd.DataFrame,
    ticker: str,
    val_months: list[str],
    args: argparse.Namespace,
) -> tuple[DeployConfig | None, dict[str, Any], float, pd.DataFrame]:
    ticker_scored = scored[scored["ticker"].eq(ticker)].copy()
    grid_args = SimpleNamespace(
        threshold_grid=[float(v) for v in args.threshold_grid],
        threshold_quantiles=[float(v) for v in args.threshold_quantiles],
        max_day_grid=[int(DAILY_CAPS[ticker])],
    )
    grid = build_fold_grid(ticker_scored, grid_args)
    rows: list[dict[str, Any]] = []
    best_cfg: DeployConfig | None = None
    best_metrics: dict[str, Any] = metrics(pd.DataFrame(), val_months)
    best_score = -1e18
    best_seen = False
    for cfg in grid:
        trades = deploy(ticker_scored, cfg, int(COOLDOWNS[ticker]))
        row = metrics(trades, val_months)
        value = score_metrics(
            row,
            int(args.min_val_trades),
            int(args.min_month_trades),
            float(args.min_val_pf),
            float(args.min_val_win_rate),
            float(args.min_call_rate),
            float(args.max_call_rate),
        )
        positive_month_rate = float(row.get("positive_month_rate", float("nan")))
        if (
            value > -1e17
            and (
                not np.isfinite(positive_month_rate)
                or positive_month_rate < float(args.min_val_positive_month_rate)
            )
        ):
            value = -1e18 + int(row.get("trades", 0))
        if np.isfinite(float(row.get("daily_win_rate", float("nan")))):
            value += float(args.daily_win_weight) * float(row["daily_win_rate"])
        if np.isfinite(float(row.get("top5_share_of_pnl", float("nan")))):
            value -= float(args.top5_share_penalty) * max(float(row["top5_share_of_pnl"]) - 1.0, 0.0)
        rows.append({"ticker": ticker, "deploy_config": cfg.name, "score": float(value), **row})
        # Invalid candidates can all round to the same -1e18 sentinel.  Keep
        # the first one's real diagnostics even when no policy is selectable;
        # the candidate grid remains authoritative and selection is unchanged.
        if not best_seen or value > best_score:
            best_cfg, best_metrics, best_score = cfg, row, float(value)
            best_seen = True
    if best_score <= -1e17:
        best_cfg = None
    return best_cfg, best_metrics, best_score, pd.DataFrame(rows)


def save_model_artifact(
    path: Path,
    model: nn.Module,
    preprocessor: Preprocessor,
    arm: str,
    month: str,
    seed: int,
    args: argparse.Namespace,
) -> str:
    payload = {
        "schema_version": 1,
        "arm": arm,
        "evaluation_month": str(month),
        "seed": int(seed),
        "model_class": type(model).__name__,
        "model_config": {
            "input_dim": len(preprocessor.features),
            "hidden_dim": int(args.hidden_dim),
            "latent_dim": int(args.latent_dim),
            "dropout": float(args.dropout),
        },
        "preprocessor": preprocessor.to_json(),
        "state_dict": {key: value.detach().cpu() for key, value in model.state_dict().items()},
    }
    torch.save(payload, path)
    return sha256_file(path)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")


def flatten_metrics(prefix: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in payload.items()}


def run_fold(
    action_frame: pd.DataFrame,
    model_features: list[str],
    arm: str,
    test_month: str,
    output_dir: Path,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]], pd.DataFrame]:
    val_months = [month_add(str(test_month), -offset) for offset in range(int(args.val_months), 0, -1)]
    first_val = val_months[0]
    train = action_frame[action_frame["month"].astype(str) < first_val].copy()
    val = action_frame[action_frame["month"].astype(str).isin(val_months)].copy()
    test = action_frame[action_frame["month"].astype(str).eq(str(test_month))].copy()
    train_months = sorted(train["month"].astype(str).unique())
    if len(train) < int(args.min_train_rows) or val.empty or test.empty:
        raise RuntimeError(
            f"insufficient fold rows for {test_month}: train={len(train)}, val={len(val)}, test={len(test)}"
        )
    seed = month_seed(int(args.seed), str(test_month))
    model, preprocessor, history = train_model(train, model_features, arm, seed, args)
    model_path = output_dir / "fold_model_artifacts" / f"payoff_head_{test_month}.pt"
    model_hash = save_model_artifact(model_path, model, preprocessor, arm, test_month, seed, args)
    history_path = output_dir / "fold_training_history" / f"training_{test_month}.json"
    write_json(history_path, history)

    val_scored_actions, val_latents = predict_actions(model, preprocessor, val, args)
    val_scored = choose_action(val_scored_actions)
    policies: dict[str, DeployConfig | None] = {}
    val_metrics_by_ticker: dict[str, dict[str, Any]] = {}
    val_scores: dict[str, float] = {}
    grid_parts: list[pd.DataFrame] = []
    policy_fields: dict[str, dict[str, str]] = {}
    for ticker in TICKERS:
        cfg, val_metrics, val_score, grid = select_threshold(val_scored, ticker, val_months, args)
        policies[ticker] = cfg
        val_metrics_by_ticker[ticker] = val_metrics
        val_scores[ticker] = val_score
        grid["month"] = str(test_month)
        grid_parts.append(grid)
        policy_payload = {
            "schema_version": 1,
            "component": "portfolio_payoff_head",
            "arm": arm,
            "ticker": ticker,
            "delta_bucket": int(DELTA_BY_TICKER[ticker]),
            "evaluation_month": str(test_month),
            "training_months": train_months,
            "selection_months": val_months,
            "seed": int(seed),
            "model_artifact_path": str(model_path),
            "model_artifact_sha256": model_hash,
            "deploy_config": cfg.name if cfg is not None else "ABSTAIN_NO_VALID_THRESHOLD",
            "daily_cap": int(DAILY_CAPS[ticker]),
            "cooldown_minutes": int(COOLDOWNS[ticker]),
            "uncertainty_used_for_selection": False,
            "policy_frozen_before_evaluation": True,
        }
        policy_path = output_dir / "fold_policy_artifacts" / f"policy_{ticker}_{test_month}.json"
        write_json(policy_path, policy_payload)
        policy_fields[ticker] = {
            "policy_artifact_path": str(policy_path),
            "policy_artifact_sha256": sha256_file(policy_path),
        }

    # Test is scored only after all ticker policies for the month exist on disk.
    test_scored_actions, test_latents = predict_actions(model, preprocessor, test, args)
    test_scored = choose_action(test_scored_actions)
    trades_parts: list[pd.DataFrame] = []
    fold_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        cfg = policies[ticker]
        ticker_test = test_scored[test_scored["ticker"].eq(ticker)].copy()
        if cfg is None:
            ticker_trades = ticker_test.iloc[0:0].copy()
            test_metrics = metrics(ticker_trades, [str(test_month)])
            status = "invalid_validation"
            deploy_name = "ABSTAIN_NO_VALID_THRESHOLD"
        else:
            ticker_trades = deploy(ticker_test, cfg, int(COOLDOWNS[ticker]))
            test_metrics = metrics(ticker_trades, [str(test_month)])
            status = "ok"
            deploy_name = cfg.name
            if not ticker_trades.empty:
                ticker_trades = ticker_trades.copy()
                ticker_trades["test_month"] = str(test_month)
                ticker_trades["arm"] = arm
                ticker_trades["delta_bucket"] = int(DELTA_BY_TICKER[ticker])
                trades_parts.append(ticker_trades)
        fold_rows.append(
            {
                "ticker": ticker,
                "month": str(test_month),
                "arm": arm,
                "status": status,
                "selected": cfg is not None,
                "deploy_config": deploy_name,
                "delta_bucket": int(DELTA_BY_TICKER[ticker]),
                "cooldown_minutes": int(COOLDOWNS[ticker]),
                "daily_cap": int(DAILY_CAPS[ticker]),
                "training_months": ",".join(train_months),
                "selection_months": ",".join(val_months),
                "train_rows": int(len(train)),
                "val_rows": int(len(val[val["ticker"].eq(ticker)])),
                "test_rows": int(len(test[test["ticker"].eq(ticker)])),
                "seed": int(seed),
                "model_artifact_path": str(model_path),
                "model_artifact_sha256": model_hash,
                **policy_fields[ticker],
                "val_score": float(val_scores[ticker]),
                **flatten_metrics("val", val_metrics_by_ticker[ticker]),
                **flatten_metrics("test", test_metrics),
            }
        )
        test_action_part = test_scored_actions[test_scored_actions["ticker"].eq(ticker)]
        train_part = train[train["ticker"].eq(ticker)]
        pred = prediction_metrics(test_action_part, train_part)
        latent_mask = test["ticker"].eq(ticker).to_numpy()
        # The action frame has both sides; masks align with the scored action rows.
        rank = effective_rank_metrics(test_latents[latent_mask])
        diagnostic_rows.append(
            {
                "arm": arm,
                "ticker": ticker,
                "month": str(test_month),
                **pred,
                **rank,
            }
        )
    trades = pd.concat(trades_parts, ignore_index=True) if trades_parts else test_scored.iloc[0:0].copy()
    grids = pd.concat(grid_parts, ignore_index=True) if grid_parts else pd.DataFrame()
    return trades, fold_rows, diagnostic_rows, grids


def build_provenance(folds: pd.DataFrame, expected_months: list[str], output_dir: Path, arm: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    passed = True
    for month in expected_months:
        part = folds[folds["month"].astype(str).eq(month)]
        month_ok = len(part) == len(TICKERS)
        ticker_rows: list[dict[str, Any]] = []
        for row in part.to_dict("records"):
            policy_path = Path(str(row["policy_artifact_path"]))
            model_path = Path(str(row["model_artifact_path"]))
            hashes_ok = (
                policy_path.is_file()
                and model_path.is_file()
                and sha256_file(policy_path) == str(row["policy_artifact_sha256"])
                and sha256_file(model_path) == str(row["model_artifact_sha256"])
            )
            training = [value for value in str(row["training_months"]).split(",") if value]
            selection = [value for value in str(row["selection_months"]).split(",") if value]
            causal = bool(training and selection) and all(value < month for value in training + selection)
            ticker_ok = bool(hashes_ok and causal)
            month_ok &= ticker_ok
            ticker_rows.append(
                {
                    "ticker": str(row["ticker"]),
                    "evaluation_month": month,
                    "training_months": training,
                    "selection_months": selection,
                    "model_artifact_path": str(model_path),
                    "model_artifact_sha256": str(row["model_artifact_sha256"]),
                    "policy_artifact_path": str(policy_path),
                    "policy_artifact_sha256": str(row["policy_artifact_sha256"]),
                    "policy_frozen_before_evaluation": ticker_ok,
                }
            )
        passed &= month_ok
        rows.append({"evaluation_month": month, "passed": bool(month_ok), "tickers": ticker_rows})
    return {
        "schema_version": 1,
        "mode": "nested_walk_forward",
        "component": "portfolio_payoff_head",
        "arm": arm,
        "evaluation_months": expected_months,
        "passed": bool(passed),
        "uncertainty_used_for_selection": False,
        "folds": rows,
        "output_dir": str(output_dir),
    }


def audit_runtime_replay(trades: pd.DataFrame) -> dict[str, Any]:
    issues: list[str] = []
    if trades.empty:
        return {"passed": True, "issues": issues, "trades": 0}
    for ticker in TICKERS:
        part = trades[trades["ticker"].eq(ticker)].copy()
        if part.empty:
            continue
        if not pd.to_numeric(part["delta_bucket"], errors="coerce").eq(DELTA_BY_TICKER[ticker]).all():
            issues.append(f"{ticker}: unexpected delta bucket")
        if float(pd.to_numeric(part["exit_minutes"], errors="raise").min()) < 30.0:
            issues.append(f"{ticker}: hold below 30 minutes")
        daily_counts = part.groupby("date").size()
        if int(daily_counts.max()) > DAILY_CAPS[ticker]:
            issues.append(f"{ticker}: daily cap exceeded")
        for date, day in part.groupby("date", sort=False):
            ordered = day.sort_values(["minute", "score"], ascending=[True, False], kind="stable")
            prior_entry: float | None = None
            prior_duration: float | None = None
            for row in ordered.itertuples(index=False):
                entry = float(row.minute)
                duration = float(row.exit_minutes)
                if prior_entry is not None and prior_duration is not None:
                    required = prior_entry + max(prior_duration, float(COOLDOWNS[ticker]))
                    if entry < required:
                        issues.append(f"{ticker}/{date}: overlapping position or cooldown violation")
                        break
                prior_entry, prior_duration = entry, duration
    return {"passed": not issues, "issues": issues, "trades": int(len(trades))}


def summary_metrics(trades: pd.DataFrame, expected_months: list[str], arm: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "arm": arm,
        "overall": metrics(trades, expected_months),
        "tickers": {},
        "months": {},
        "runtime_replay_audit": audit_runtime_replay(trades),
    }
    for ticker in TICKERS:
        result["tickers"][ticker] = metrics(trades[trades["ticker"].eq(ticker)], expected_months)
    for month in expected_months:
        result["months"][month] = metrics(trades[trades["month"].astype(str).eq(month)], [month])
    return result


def ensure_output_dirs(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    for child in ("fold_model_artifacts", "fold_policy_artifacts", "fold_training_history"):
        (output_dir / child).mkdir()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Nested deterministic-vs-variational action-conditioned payoff head over frozen flat Phys-TD features."
    )
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--arm", choices=["deterministic", "variational"], required=True)
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-train-rows", type=int, default=5000)
    parser.add_argument("--clip-return", type=float, default=2.0)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--latent-dim", type=int, default=16)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--infer-batch-size", type=int, default=4096)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.000001)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--kl-weight", type=float, default=1.0)
    parser.add_argument("--kl-anneal-epochs", type=int, default=20)
    parser.add_argument(
        "--threshold-grid",
        nargs="+",
        type=float,
        default=[-1e9, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20],
    )
    parser.add_argument("--threshold-quantiles", nargs="+", type=float, default=[0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    parser.add_argument("--min-val-trades", type=int, default=54)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-val-pf", type=float, default=1.3)
    parser.add_argument("--min-val-win-rate", type=float, default=0.5)
    parser.add_argument("--min-val-positive-month-rate", type=float, default=1.0)
    parser.add_argument("--min-call-rate", type=float, default=0.0)
    parser.add_argument("--max-call-rate", type=float, default=1.0)
    parser.add_argument("--daily-win-weight", type=float, default=0.25)
    parser.add_argument("--top5-share-penalty", type=float, default=0.10)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    parser.add_argument("--seed", type=int, default=20260618)
    parser.add_argument("--deterministic", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    ensure_output_dirs(output_dir)
    data_path = Path(args.data)
    base, latent_cols = load_base_frame(data_path)
    action_frame, model_features = build_action_frame(base, latent_cols)
    expected_months = month_range(str(args.start_month), str(args.end_month))
    if expected_months != ["202601", "202602", "202603", "202604", "202605"]:
        raise RuntimeError(f"evaluation window must remain sealed at 202601..202605, got {expected_months}")
    metadata = {
        "schema_version": 1,
        "args": vars(args),
        "data_path": str(data_path),
        "data_sha256": sha256_file(data_path),
        "data_rows_after_contract": int(len(base)),
        "action_rows": int(len(action_frame)),
        "date_min": str(base["date"].min()),
        "date_max": str(base["date"].max()),
        "latent_features": latent_cols,
        "model_features": model_features,
        "delta_by_ticker": DELTA_BY_TICKER,
        "daily_caps": DAILY_CAPS,
        "cooldowns": COOLDOWNS,
        "dataset_contract": "executable_quote_ask_to_bid",
        "hold_action_contract": "implicit_abstention_via_validation_frozen_threshold",
        "minimum_hold_minutes": 30,
        "validation_acceptance_gates": {
            "profit_factor": float(args.min_val_pf),
            "win_rate": float(args.min_val_win_rate),
            "trades_per_month": int(args.min_month_trades),
            "positive_month_rate": float(args.min_val_positive_month_rate),
        },
        "model_parameter_count": int(
            sum(parameter.numel() for parameter in make_model(str(args.arm), len(model_features), args).parameters())
        ),
        "uncertainty_used_for_selection": False,
    }
    write_json(output_dir / "metadata.json", metadata)

    all_trades: list[pd.DataFrame] = []
    all_folds: list[dict[str, Any]] = []
    all_diagnostics: list[dict[str, Any]] = []
    all_grids: list[pd.DataFrame] = []
    for month in expected_months:
        trades, folds, diagnostics, grids = run_fold(
            action_frame, model_features, str(args.arm), month, output_dir, args
        )
        if not trades.empty:
            all_trades.append(trades)
        all_folds.extend(folds)
        all_diagnostics.extend(diagnostics)
        if not grids.empty:
            all_grids.append(grids)
        pd.DataFrame(all_folds).to_csv(output_dir / "selected_folds.csv", index=False)
        pd.DataFrame(all_diagnostics).to_csv(output_dir / "representation_ticker_month.csv", index=False)
        if all_trades:
            pd.concat(all_trades, ignore_index=True).to_csv(output_dir / "portfolio_payoff_trades.csv", index=False)
        if all_grids:
            pd.concat(all_grids, ignore_index=True).to_csv(output_dir / "candidate_validation.csv", index=False)
        print(f"[PORTFOLIO_VAR_JEPA] arm={args.arm} month={month} folds={len(all_folds)}/{len(expected_months)*len(TICKERS)}")

    folds_frame = pd.DataFrame(all_folds).sort_values(["ticker", "month"]).reset_index(drop=True)
    trades_frame = (
        pd.concat(all_trades, ignore_index=True).sort_values(["ticker", "date", "minute"]).reset_index(drop=True)
        if all_trades
        else action_frame.iloc[0:0].copy()
    )
    folds_frame.to_csv(output_dir / "selected_folds.csv", index=False)
    trades_frame.to_csv(output_dir / "portfolio_payoff_trades.csv", index=False)
    pd.DataFrame(all_diagnostics).sort_values(["ticker", "month"]).to_csv(
        output_dir / "representation_ticker_month.csv", index=False
    )
    provenance = build_provenance(folds_frame, expected_months, output_dir, str(args.arm))
    write_json(output_dir / "policy_selection_provenance.json", provenance)
    if not provenance["passed"]:
        raise RuntimeError("policy selection provenance failed")
    summary = summary_metrics(trades_frame, expected_months, str(args.arm))
    if not summary["runtime_replay_audit"]["passed"]:
        raise RuntimeError(f"runtime replay audit failed: {summary['runtime_replay_audit']['issues']}")
    write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
