from __future__ import annotations

import numpy as np
import torch

from neural.jepa import evaluate_directional_factorized_innovation_jepa_v1 as module
from neural.jepa import evaluate_directional_semantic_jepa_v1 as base


def test_factorized_encoder_preserves_declared_block_contract() -> None:
    model = module.FactorizedInnovationJEPA()
    context = torch.randn(7, base.CONTEXT_LENGTH, base.MODEL_INPUT_CHANNELS)
    context[:, :, base.RAW_CHANNELS :] = 0.0
    latent = model.encoder(context)
    assert latent.shape == (7, base.LATENT_DIM)
    assert [(name, block.stop - block.start) for name, block in module.BLOCK_SLICES.items()] == [
        ("common", 8),
        ("qqq_residual", 4),
        ("spxw_residual", 4),
        ("spy_residual", 4),
        ("volatility", 4),
    ]


def test_innovation_and_future_latent_interfaces_are_consistent() -> None:
    model = module.FactorizedInnovationJEPA()
    latent = torch.randn(5, base.LATENT_DIM)
    innovation = model.predict_innovations(latent)
    future = model.predict_latents(latent)
    raw = model.predict_raw_innovations(latent)
    assert innovation.shape == (5, len(base.HORIZONS), base.LATENT_DIM)
    assert raw.shape == (5, len(base.HORIZONS), base.RAW_CHANNELS)
    assert torch.allclose(future, latent[:, None, :] + innovation)


def test_corruption_marks_time_and_can_remove_semantic_blocks() -> None:
    torch.manual_seed(20260716)
    context = torch.ones(16, base.CONTEXT_LENGTH, base.MODEL_INPUT_CHANNELS)
    context[:, :, base.RAW_CHANNELS :] = 0.0
    corrupted = module.corrupt_student_context(context)
    assert corrupted.shape == context.shape
    assert (corrupted[:, :, base.RAW_CHANNELS] == 1.0).any(dim=1).all()
    assert (corrupted[:, :, : base.RAW_CHANNELS] == 0.0).any()


def test_batch_loss_uses_only_context_and_ssl_future_windows() -> None:
    torch.manual_seed(3)
    model = module.FactorizedInnovationJEPA()
    teacher = module.FactorizedEncoder()
    teacher.load_state_dict(model.encoder.state_dict())
    context = torch.randn(8, base.CONTEXT_LENGTH, base.MODEL_INPUT_CHANNELS)
    targets = torch.randn(
        8, len(base.HORIZONS), base.CONTEXT_LENGTH, base.MODEL_INPUT_CHANNELS
    )
    context[:, :, base.RAW_CHANNELS :] = 0.0
    targets[:, :, :, base.RAW_CHANNELS :] = 0.0
    loss, metrics = module.jepa_batch_loss(
        model, teacher, context, targets, corrupt=True
    )
    assert torch.isfinite(loss)
    assert set(metrics) == {
        "total",
        "latent_prediction",
        "raw_prediction",
        "alignment",
        "visreg_full",
        "visreg_blocks",
    }
    loss.backward()
    assert any(parameter.grad is not None for parameter in model.parameters())


def test_latent_health_gate_rejects_collapsed_geometry() -> None:
    collapsed = {
        "effective_rank_ratio": 0.1,
        "max_pc_var_ratio": 0.9,
        "near_zero_std_dims": 5,
    }
    assert collapsed["effective_rank_ratio"] < module.HEALTH_MIN_RANK_RATIO
    assert collapsed["max_pc_var_ratio"] > module.HEALTH_MAX_PC_RATIO


def test_semantic_features_include_factorized_raw_innovation_summaries() -> None:
    rng = np.random.default_rng(4)
    array = rng.normal(size=(391, base.RAW_CHANNELS)).astype(np.float32)
    normalizer = base.fit_normalizer([array])
    model = module.FactorizedInnovationJEPA()
    features = module.semantic_feature_values(model, array, normalizer, torch.device("cpu"))
    assert len(features) == 90
    assert "jepa_z_00" in features
    assert "jepa_dz_23" in features
    assert "jepa_pred_qqq_versus_open_delta_180m" in features
    assert "jepa_pred_spxw_range_delta_60m" in features
    assert "jepa_pred_spy_body_delta_15m" in features
    assert np.isfinite(list(features.values())).all()
