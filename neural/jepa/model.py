from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import torch
from torch import nn


@dataclass
class JEPAConfig:
    input_dim: int
    context_len: int
    horizons: list[int]
    hidden_dim: int = 128
    z_dim: int = 32
    num_layers: int = 2
    dropout: float = 0.10

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "JEPAConfig":
        data = dict(data)
        data["horizons"] = [int(x) for x in data["horizons"]]
        return cls(**data)


class TemporalEncoder(nn.Module):
    def __init__(self, config: JEPAConfig) -> None:
        super().__init__()
        self.config = config
        self.input_norm = nn.LayerNorm(config.input_dim)
        self.gru = nn.GRU(
            input_size=config.input_dim,
            hidden_size=config.hidden_dim,
            num_layers=config.num_layers,
            batch_first=True,
            dropout=config.dropout if config.num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.LayerNorm(config.hidden_dim),
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim, config.z_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_norm(x)
        _, h = self.gru(x)
        last = h[-1]
        return self.head(last)


class MultiHorizonPredictor(nn.Module):
    def __init__(self, config: JEPAConfig) -> None:
        super().__init__()
        self.config = config
        self.heads = nn.ModuleList(
            [
                nn.Sequential(
                    nn.LayerNorm(config.z_dim),
                    nn.Linear(config.z_dim, config.hidden_dim),
                    nn.GELU(),
                    nn.Dropout(config.dropout),
                    nn.Linear(config.hidden_dim, config.z_dim),
                )
                for _ in config.horizons
            ]
        )

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        return torch.stack([head(z) for head in self.heads], dim=1)


class TemporalJEPA(nn.Module):
    def __init__(self, config: JEPAConfig) -> None:
        super().__init__()
        self.config = config
        self.encoder = TemporalEncoder(config)
        self.predictor = MultiHorizonPredictor(config)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)

    def predict(self, z: torch.Tensor) -> torch.Tensor:
        return self.predictor(z)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        z = self.encode(x)
        return z, self.predict(z)


class AlphaTemporalJEPA(nn.Module):
    """JEPA encoder with auxiliary trading-aligned prediction heads."""

    def __init__(self, config: JEPAConfig) -> None:
        super().__init__()
        self.config = config
        self.encoder = TemporalEncoder(config)
        self.predictor = MultiHorizonPredictor(config)
        self.class_head = nn.Sequential(
            nn.LayerNorm(config.z_dim),
            nn.Linear(config.z_dim, config.hidden_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim, 3),
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)

    def predict(self, z: torch.Tensor) -> torch.Tensor:
        return self.predictor(z)

    def classify(self, z: torch.Tensor) -> torch.Tensor:
        return self.class_head(z)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        z = self.encode(x)
        return z, self.predict(z), self.classify(z)


def save_model(model: TemporalJEPA, output_dir: str | Path, extra: dict | None = None) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "config": model.config.to_dict(),
        "model_state": model.state_dict(),
        "extra": extra or {},
    }
    torch.save(payload, out / "model.pt")
    torch.save(model.encoder.state_dict(), out / "encoder.pt")
    torch.save(model.predictor.state_dict(), out / "predictor.pt")
    (out / "model_config.json").write_text(json.dumps(model.config.to_dict(), indent=2), encoding="utf-8")


def load_model(model_dir: str | Path, map_location: str | torch.device = "cpu") -> TemporalJEPA:
    payload = torch.load(Path(model_dir) / "model.pt", map_location=map_location)
    config = JEPAConfig.from_dict(payload["config"])
    model = TemporalJEPA(config)
    model.load_state_dict(payload["model_state"])
    return model


def load_alpha_model(model_dir: str | Path, map_location: str | torch.device = "cpu") -> AlphaTemporalJEPA:
    payload = torch.load(Path(model_dir) / "model.pt", map_location=map_location)
    config = JEPAConfig.from_dict(payload["config"])
    model = AlphaTemporalJEPA(config)
    model.load_state_dict(payload["model_state"])
    return model


def encode_contexts(
    model: TemporalJEPA,
    contexts: torch.Tensor,
    batch_size: int = 4096,
    device: str | torch.device = "cpu",
) -> torch.Tensor:
    model.eval()
    outs = []
    with torch.no_grad():
        for start in range(0, len(contexts), batch_size):
            batch = contexts[start : start + batch_size].to(device)
            outs.append(model.encode(batch).cpu())
    return torch.cat(outs, dim=0)
