from __future__ import annotations

import torch
from torch import nn


class SIGRegLoss(nn.Module):
    """Sketched isotropic Gaussian regularization for latent batches."""

    def __init__(
        self,
        z_dim: int,
        num_projections: int = 64,
        num_frequencies: int = 16,
        max_frequency: float = 3.0,
    ) -> None:
        super().__init__()
        self.z_dim = int(z_dim)
        self.num_projections = int(num_projections)
        self.num_frequencies = int(num_frequencies)
        self.max_frequency = float(max_frequency)
        freqs = torch.linspace(0.25, self.max_frequency, self.num_frequencies)
        self.register_buffer("freqs", freqs)

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        if z.ndim != 2:
            z = z.reshape(-1, z.shape[-1])
        if len(z) < 4:
            return z.new_tensor(0.0)

        projections = torch.randn(self.num_projections, z.shape[-1], device=z.device, dtype=z.dtype)
        projections = projections / projections.norm(dim=1, keepdim=True).clamp_min(1e-6)
        projected = z @ projections.t()

        t = self.freqs.to(device=z.device, dtype=z.dtype).view(1, 1, -1)
        p = projected.unsqueeze(-1)
        empirical_real = torch.cos(t * p).mean(dim=0)
        empirical_imag = torch.sin(t * p).mean(dim=0)
        target_real = torch.exp(-0.5 * (self.freqs.to(z.device, z.dtype) ** 2)).view(1, -1)

        cf_loss = (empirical_real - target_real).pow(2).mean() + empirical_imag.pow(2).mean()
        mean_loss = projected.mean(dim=0).pow(2).mean()
        var_loss = (projected.var(dim=0, unbiased=False) - 1.0).pow(2).mean()
        return cf_loss + 0.10 * mean_loss + 0.10 * var_loss


def latent_diagnostics(z: torch.Tensor) -> dict:
    with torch.no_grad():
        z = z.detach().float().cpu()
        if z.ndim != 2 or len(z) < 2:
            return {"error": "need at least two 2D latent rows"}
        zc = z - z.mean(dim=0, keepdim=True)
        cov = (zc.t() @ zc) / max(1, len(z) - 1)
        eigvals = torch.linalg.eigvalsh(cov).clamp_min(0.0)
        total = eigvals.sum().clamp_min(1e-12)
        probs = eigvals / total
        entropy = -(probs * (probs + 1e-12).log()).sum()
        effective_rank = float(torch.exp(entropy).item())
        std = z.std(dim=0, unbiased=False)
        return {
            "n": int(len(z)),
            "z_dim": int(z.shape[1]),
            "effective_rank": effective_rank,
            "effective_rank_ratio": effective_rank / float(z.shape[1]),
            "max_pc_var_ratio": float((eigvals.max() / total).item()),
            "min_dim_std": float(std.min().item()),
            "median_dim_std": float(std.median().item()),
            "near_zero_std_dims": int((std < 0.05).sum().item()),
            "mean_abs": float(z.mean(dim=0).abs().mean().item()),
        }


class VarianceCovarianceLoss(nn.Module):
    """VICReg-style latent health regularizer used as a stronger v2 fallback."""

    def __init__(self, min_std: float = 1.0, cov_weight: float = 1.0, var_weight: float = 1.0) -> None:
        super().__init__()
        self.min_std = float(min_std)
        self.cov_weight = float(cov_weight)
        self.var_weight = float(var_weight)

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        if z.ndim != 2:
            z = z.reshape(-1, z.shape[-1])
        if len(z) < 4:
            return z.new_tensor(0.0)
        z = z - z.mean(dim=0, keepdim=True)
        std = torch.sqrt(z.var(dim=0, unbiased=False) + 1e-4)
        var_loss = torch.relu(self.min_std - std).mean()
        cov = (z.t() @ z) / max(1, len(z) - 1)
        off_diag = cov - torch.diag(torch.diag(cov))
        cov_loss = off_diag.pow(2).sum() / z.shape[1]
        return self.var_weight * var_loss + self.cov_weight * cov_loss
