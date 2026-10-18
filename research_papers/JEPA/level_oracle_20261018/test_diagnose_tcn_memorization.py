import numpy as np
import pandas as pd
import pytest
import torch

import diagnose_tcn_memorization as d


def test_hash_sampling_order_invariant_and_train_only():
    sample = pd.DataFrame(
        dict(day_key=["QQQ_20230103"] * 150, action_id=np.arange(150))
    )
    a = d.select_rows(sample)
    b = d.select_rows(sample.sample(frac=1, random_state=9))
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 128
    sample.loc[0, "day_key"] = "QQQ_20250103"
    with pytest.raises(ValueError, match="Non-TRAIN"):
        d.select_rows(sample)


def test_exact_input_conflicts_and_floor():
    values = (torch.tensor([[1.0, 2.0], [1.0, 2.0], [2.0, 1.0]]),) * 6
    hashes = d.input_hashes(values)
    assert hashes[0] == hashes[1] != hashes[2]
    result = d.duplicate_diagnostics(
        hashes, [0.0, 2.0, 8.0], [0.0, 1.0, 1.0], [1.0, 3.0, 2.0]
    )
    assert result["unique_inputs"] == 2
    assert result["contradictory_net_groups"] == 1
    assert result["contradictory_teacher_groups"] == 1
    assert result["identical_input_weighted_mse_floor"] == 0.5


def test_loss_retains_original_denominator_and_weighting():
    p = torch.tensor([0.0, 2.0], requires_grad=True)
    t = torch.tensor([1.0, 0.0])
    w = torch.tensor([2.0, 3.0])
    loss = d.fixed_loss(p, torch.zeros(2), t, t, w)
    expected = (14 + 0.5 * np.log(2)) / 1024
    assert float(loss.detach()) == pytest.approx(expected)
    loss.backward()
    np.testing.assert_allclose(p.grad.numpy(), [-4 / 1024, 12 / 1024])


def test_fixed_cpu_measurement_does_not_mutate_model_or_rng():
    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.linear = torch.nn.Linear(2, 2)

        def forward(self, x):
            out = self.linear(x)
            return out[:, 0], out[:, 1]

    model = Model()
    before = {k: v.clone() for k, v in model.state_dict().items()}
    rng = torch.get_rng_state().clone()
    result = d.measure(
        model, (torch.ones(3, 2),), torch.arange(3.0), torch.zeros(3), torch.ones(3), 50
    )
    assert result["update"] == 50
    assert result["constant_weighted_mse"] == pytest.approx(2 / 3)
    assert torch.equal(rng, torch.get_rng_state())
    assert all(torch.equal(v, before[k]) for k, v in model.state_dict().items())
