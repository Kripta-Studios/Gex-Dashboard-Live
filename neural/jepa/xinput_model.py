from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import nn


@dataclass
class XInputJEPAConfig:
    state_dim: int
    input_dim: int
    context_len: int
    horizons: list[int]
    hidden_dim: int = 96
    z_dim: int = 16
    u_dim: int = 12
    num_layers: int = 2
    dropout: float = 0.15

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "XInputJEPAConfig":
        data = dict(data)
        data["horizons"] = [int(x) for x in data["horizons"]]
        return cls(**data)


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


class XInputPredictor(nn.Module):
    def __init__(self, config: XInputJEPAConfig) -> None:
        super().__init__()
        self.horizon_embed = nn.Embedding(len(config.horizons), config.u_dim)
        in_dim = config.z_dim + config.u_dim + config.u_dim
        self.heads = nn.ModuleList(
            [
                nn.Sequential(
                    nn.LayerNorm(in_dim),
                    nn.Linear(in_dim, config.hidden_dim),
                    nn.GELU(),
                    nn.Dropout(config.dropout),
                    nn.Linear(config.hidden_dim, config.z_dim),
                )
                for _ in config.horizons
            ]
        )

    def forward(self, z: torch.Tensor, u: torch.Tensor) -> torch.Tensor:
        outs = []
        for idx, head in enumerate(self.heads):
            h = self.horizon_embed.weight[idx].view(1, -1).expand(len(z), -1)
            outs.append(head(torch.cat([z, u, h], dim=-1)))
        return torch.stack(outs, dim=1)


class XInputMarketJEPA(nn.Module):
    def __init__(self, config: XInputJEPAConfig) -> None:
        super().__init__()
        self.config = config
        self.state_encoder = SequenceEncoder(
            config.state_dim, config.z_dim, config.hidden_dim, config.num_layers, config.dropout
        )
        self.input_encoder = SequenceEncoder(
            config.input_dim, config.u_dim, config.hidden_dim, config.num_layers, config.dropout
        )
        self.predictor = XInputPredictor(config)
        self.class_head = nn.Sequential(
            nn.LayerNorm(config.z_dim + config.u_dim + config.z_dim),
            nn.Linear(config.z_dim + config.u_dim + config.z_dim, config.hidden_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim, 3),
        )

    def encode_state(self, state_ctx: torch.Tensor) -> torch.Tensor:
        return self.state_encoder(state_ctx)

    def encode_input(self, input_ctx: torch.Tensor) -> torch.Tensor:
        return self.input_encoder(input_ctx)

    def forward(self, state_ctx: torch.Tensor, input_ctx: torch.Tensor):
        z = self.encode_state(state_ctx)
        u = self.encode_input(input_ctx)
        pred = self.predictor(z, u)
        pred_summary = pred.mean(dim=1)
        logits = self.class_head(torch.cat([z, u, pred_summary], dim=-1))
        return z, u, pred, logits


def save_xinput_model(model: XInputMarketJEPA, output_dir: str | Path, extra: dict | None = None) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "config": model.config.to_dict(),
        "model_state": model.state_dict(),
        "extra": extra or {},
    }
    torch.save(payload, out / "model.pt")
    (out / "model_config.json").write_text(json.dumps(model.config.to_dict(), indent=2), encoding="utf-8")


def load_xinput_model(model_dir: str | Path, map_location: str | torch.device = "cpu") -> XInputMarketJEPA:
    payload = torch.load(Path(model_dir) / "model.pt", map_location=map_location)
    config = XInputJEPAConfig.from_dict(payload["config"])
    model = XInputMarketJEPA(config)
    model.load_state_dict(payload["model_state"])
    return model

