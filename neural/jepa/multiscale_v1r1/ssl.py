"""SSL-001: exact clock projection and causal same-trajectory objective primitives."""
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .contract import CHANNELS


def project_clock(values, masks):
    x, m = values.clone(), masks.clone()
    for name in ('time_of_day_sin', 'time_of_day_cos'):
        index = CHANNELS.index(name)
        x[..., index] = 0
        m[..., index] = 0
    return torch.cat((x, m), dim=-1).flatten(-2)


def encoder():
    return nn.Sequential(nn.Linear(4602, 96), nn.GELU(), nn.Linear(96, 96), nn.GELU(), nn.Linear(96, 32))


def predictor():
    return nn.Sequential(nn.Linear(32, 96), nn.GELU(), nn.Linear(96, 96), nn.GELU(), nn.Linear(96, 32))


def nce(z, predicted):
    # Batch matrix product prevents any negative candidate from another event.
    logits = F.normalize(predicted[:, :-1], dim=-1) @ F.normalize(z[:, 1:], dim=-1).transpose(1, 2) / .12
    labels = torch.arange(z.shape[1] - 1, device=z.device).repeat(z.shape[0])
    return F.cross_entropy(logits.flatten(0, 1), labels)


def causal_residual(z):
    count = torch.arange(1, z.shape[1] + 1, device=z.device, dtype=z.dtype)[None, :, None]
    return (z - z.cumsum(dim=1) / count)[:, 1:]


def directions(month):
    rng = np.random.Generator(np.random.PCG64(20260802 + int(month) + 1))
    matrix = rng.standard_normal((32, 24))
    return torch.tensor((matrix / np.linalg.norm(matrix, axis=0)).astype('float32'))


def vis(z, vectors):
    flat = causal_residual(z).flatten(0, 1)
    mean = flat.mean(dim=0)
    std = torch.sqrt(flat.var(dim=0, unbiased=False) + 1e-4)
    normalized = (flat - mean) / std.detach()
    projected = torch.sort(normalized @ vectors, dim=0).values
    q = (torch.arange(len(flat), dtype=flat.dtype, device=flat.device) + .5) / len(flat)
    normal = torch.distributions.Normal(0., 1.).icdf(q)
    return ((1 - std) ** 2).mean() + ((projected - normal[:, None]) ** 2).mean() + (mean ** 2).mean()
