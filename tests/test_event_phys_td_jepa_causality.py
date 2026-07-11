from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from neural.jepa.event_option_component_live import LIVE_INCONSISTENT_INTRADAY_STATE_FEATURES
from neural.jepa.walkforward_event_phys_td_jepa_oof import (
    EventPhysTDJEPADataset,
    EventPhysTDJEPA,
    EventPhysTDJEPAConfig,
    GramConsistencyLoss,
    ModalSequenceEncoder,
    build_contexts,
    export_observed_transition_features,
    filter_frame_to_month_cutoff,
    fold_seed,
    select_feature_columns,
    set_seed,
)


class _IdentityNormalizer:
    def transform_frame(self, frame: pd.DataFrame) -> np.ndarray:
        return frame[["feature"]].to_numpy(dtype=np.float32)


def test_set_seed_can_require_deterministic_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    previous = torch.are_deterministic_algorithms_enabled()
    previous_cudnn = torch.backends.cudnn.deterministic
    previous_benchmark = torch.backends.cudnn.benchmark
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    try:
        set_seed(17, deterministic=True)
        assert torch.are_deterministic_algorithms_enabled()
        assert torch.backends.cudnn.deterministic
        assert not torch.backends.cudnn.benchmark
    finally:
        torch.use_deterministic_algorithms(previous)
        torch.backends.cudnn.deterministic = previous_cudnn
        torch.backends.cudnn.benchmark = previous_benchmark


def test_fold_seed_is_stable_per_month_and_shared_between_arms() -> None:
    assert fold_seed(20260618, "202505") == fold_seed(20260618, "202505")
    assert fold_seed(20260618, "202505") != fold_seed(20260618, "202506")
    with pytest.raises(ValueError, match="Invalid fold month"):
        fold_seed(20260618, "2025-05")


def test_phys_td_feature_selection_rejects_live_inconsistent_state() -> None:
    frame = pd.DataFrame(
        {
            "safe_feature": [1.0],
            "dist_ib_high_bps": [2.0],
            "future_outcome": [3.0],
            **{name: [float(index)] for index, name in enumerate(LIVE_INCONSISTENT_INTRADAY_STATE_FEATURES)},
        }
    )

    selected = select_feature_columns(frame, entry_start_minute_et=630)

    assert "safe_feature" in selected
    assert "dist_ib_high_bps" in selected
    assert "future_outcome" not in selected
    assert not (set(selected) & LIVE_INCONSISTENT_INTRADAY_STATE_FEATURES)


def test_phys_td_feature_selection_rejects_initial_balance_before_completion() -> None:
    frame = pd.DataFrame({"safe_feature": [1.0], "dist_ib_high_bps": [2.0]})

    selected = select_feature_columns(frame, entry_start_minute_et=600)

    assert selected == ["safe_feature"]


def test_phys_td_dataset_never_bridges_missing_five_minute_bars() -> None:
    frame = pd.DataFrame(
        {
            "ticker": ["SPY"] * 6,
            "date": ["20260102"] * 6,
            "minute": [630, 635, 640, 650, 655, 660],
            "feature": np.arange(6, dtype=np.float32),
        }
    )
    dataset = EventPhysTDJEPADataset(
        frame,
        ["feature"],
        ["feature"],
        _IdentityNormalizer(),
        context_len=2,
        horizons=[1],
        group_cols=["ticker", "date"],
        expected_step_minutes=5,
    )

    assert len(dataset) == 2
    first_ctx = dataset[0][0].numpy().reshape(-1).tolist()
    second_ctx = dataset[1][0].numpy().reshape(-1).tolist()
    assert first_ctx == [0.0, 1.0]
    assert second_ctx == [3.0, 4.0]


def test_export_contexts_require_exact_five_minute_continuity() -> None:
    arr = np.arange(6, dtype=np.float32).reshape(-1, 1)

    _ctx, _delta, positions = build_contexts(
        arr,
        context_len=3,
        minutes=[630, 635, 640, 650, 655, 660],
        expected_step_minutes=5,
    )

    assert positions == [2, 5]


def test_transition_export_pairs_only_observed_contiguous_same_session_targets() -> None:
    torch.manual_seed(7)
    model = EventPhysTDJEPA(
        EventPhysTDJEPAConfig(
            input_dim=1,
            q_dim=1,
            context_len=2,
            horizons=[1],
            z_dim=4,
            phys_dim=1,
            delta_dim=2,
            horizon_dim=2,
            hidden_dim=8,
            num_layers=1,
            dropout=0.0,
        )
    )
    frame = pd.DataFrame(
        {
            "ticker": ["SPY"] * 7,
            "date": ["20260102"] * 7,
            "trade_date": ["20260102"] * 7,
            "expiration": ["20260102"] * 7,
            "expiry_mode": ["zero_dte"] * 7,
            "timestamp": pd.to_datetime(
                [
                    "2026-01-02 10:30",
                    "2026-01-02 10:35",
                    "2026-01-02 10:40",
                    "2026-01-02 10:50",
                    "2026-01-02 10:55",
                    "2026-01-02 11:00",
                    "2026-01-02 11:05",
                ]
            ),
            "time": ["10:30", "10:35", "10:40", "10:50", "10:55", "11:00", "11:05"],
            "minute": [630, 635, 640, 650, 655, 660, 665],
            "feature": np.arange(7, dtype=np.float32),
        }
    )
    args = SimpleNamespace(
        expected_step_minutes=5,
        infer_batch_size=16,
        group_expiry_mode=True,
    )

    exported = export_observed_transition_features(
        model,
        _IdentityNormalizer(),
        frame,
        ["feature"],
        args,
        torch.device("cpu"),
    )

    assert exported["minute"].tolist() == [635, 655, 660]
    assert exported["target_minute"].tolist() == [640, 660, 665]
    assert (exported["target_minute"] - exported["minute"]).eq(5).all()
    target_cols = [f"target_z_{index:02d}" for index in range(4)]
    z_cols = [f"z_t_{index:02d}" for index in range(4)]
    assert np.allclose(exported.loc[1, target_cols].to_numpy(float), exported.loc[2, z_cols].to_numpy(float))
    assert exported["target_available_after_timestamp"].equals(exported["target_timestamp"])


def test_month_cutoff_physically_removes_sealed_holdout() -> None:
    frame = pd.DataFrame(
        {
            "trade_date": [20260529, 20260601, 20260630],
            "value": [1.0, 2.0, 3.0],
        }
    )

    filtered = filter_frame_to_month_cutoff(frame, "202605")

    assert filtered["trade_date"].tolist() == [20260529]


@pytest.mark.parametrize(
    ("mask_modal_prob", "mask_temporal_prob"),
    [(1.0, 0.0), (0.0, 1.0)],
)
def test_modal_encoder_masks_only_the_observed_context_tokens(
    mask_modal_prob: float,
    mask_temporal_prob: float,
) -> None:
    torch.manual_seed(7)
    encoder = ModalSequenceEncoder(
        input_dim=4,
        hidden_dim=8,
        output_dim=5,
        num_layers=1,
        dropout=0.0,
        modal_feature_indices=[[0, 1], [2, 3]],
        modal_token_dim=3,
        mask_modal_prob=mask_modal_prob,
        mask_temporal_prob=mask_temporal_prob,
    )
    observed = torch.arange(24, dtype=torch.float32).reshape(2, 3, 4)
    captured: list[torch.Tensor] = []
    hook = encoder.gru.register_forward_pre_hook(lambda _module, args: captured.append(args[0].detach().clone()))

    encoder.train()
    encoder(observed)
    masked_fused = captured.pop()
    expected = torch.cat(
        [encoder.modal_mask_tokens[i].view(1, 1, -1).expand(2, 3, -1) for i in range(2)],
        dim=-1,
    )
    assert torch.equal(masked_fused, expected)

    encoder(observed, apply_mask=False)
    explicitly_unmasked_fused = captured.pop()
    assert not torch.equal(explicitly_unmasked_fused, expected)

    encoder.eval()
    encoder(observed)
    unmasked_fused = captured.pop()
    hook.remove()
    assert torch.equal(unmasked_fused, explicitly_unmasked_fused)


@pytest.mark.parametrize(
    ("mask_modal_prob", "mask_temporal_prob"),
    [(-0.01, 0.0), (1.01, 0.0), (0.0, -0.01), (0.0, 1.01)],
)
def test_modal_encoder_rejects_invalid_mask_probabilities(
    mask_modal_prob: float,
    mask_temporal_prob: float,
) -> None:
    with pytest.raises(ValueError, match="must be between 0 and 1"):
        ModalSequenceEncoder(
            input_dim=4,
            hidden_dim=8,
            output_dim=5,
            num_layers=1,
            dropout=0.0,
            modal_feature_indices=[[0, 1], [2, 3]],
            modal_token_dim=3,
            mask_modal_prob=mask_modal_prob,
            mask_temporal_prob=mask_temporal_prob,
        )


def test_gram_consistency_loss_is_zero_for_equal_geometry_and_backpropagates() -> None:
    loss_fn = GramConsistencyLoss()
    student = torch.tensor([[1.0, 0.0], [0.0, 1.0]], requires_grad=True)
    same_target = student.detach().clone()

    same_loss = loss_fn(student, same_target)
    assert same_loss.item() == pytest.approx(0.0)

    different_target = torch.tensor([[1.0, 0.0], [1.0, 0.0]])
    different_loss = loss_fn(student, different_target)
    assert different_loss.item() > 0.0
    different_loss.backward()
    assert student.grad is not None
    assert torch.isfinite(student.grad).all()
