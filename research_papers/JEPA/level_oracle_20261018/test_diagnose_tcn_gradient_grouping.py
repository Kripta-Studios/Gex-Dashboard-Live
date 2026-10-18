import numpy as np
import pandas as pd
import torch

import diagnose_tcn_gradient_grouping as d


def test_same_rows_balanced_mixed_and_exact_gradient_mean():
    torch.manual_seed(17)
    torch.set_num_threads(1)
    daily, mixed = d.partitions()
    assert np.array_equal(np.sort(daily.ravel()), np.arange(512))
    assert np.array_equal(np.sort(mixed.ravel()), np.arange(512))
    assert all(np.array_equal(np.bincount(row // 32), np.full(16, 2)) for row in mixed)

    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.network = torch.nn.Sequential(
                torch.nn.Linear(3, 12), torch.nn.ReLU(), torch.nn.Linear(12, 2)
            )

        def forward(self, x):
            scores = self.network(x)
            return scores[:, 0], scores[:, 1]

    model = Model()
    inputs = (torch.randn(512, 3),)
    target, teacher, weight = (
        torch.randn(512),
        torch.randint(2, (512,)).float(),
        torch.rand(512) + 0.1,
    )
    before = {k: v.clone() for k, v in model.state_dict().items()}
    gd = d.gradients(model, inputs, target, teacher, weight, daily)
    gm = d.gradients(model, inputs, target, teacher, weight, mixed)
    np.testing.assert_allclose(gd.mean(0), gm.mean(0), rtol=1e-5, atol=1e-9)
    assert all(torch.equal(v, before[k]) for k, v in model.state_dict().items())
    assert all(p.grad is None for p in model.parameters())


def test_hash_selection_order_independent():
    sample = pd.DataFrame(
        [
            dict(day_key=f"QQQ_202301{day:02d}", action_id=i)
            for day in range(1, 21)
            for i in range(35)
        ]
    )
    a = d.select_block(sample)
    b = d.select_block(sample.sample(frac=1, random_state=9))
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 512 and a.day_key.nunique() == 16
