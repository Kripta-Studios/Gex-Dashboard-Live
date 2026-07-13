from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa.existing_data_edge_hurdle_v1 import (
    fit_hurdle_utility,
    frozen_spec,
    frozen_spec_sha256,
    training_percentile_grid,
)


def _training_frame(rows: int = 120) -> pd.DataFrame:
    x = np.linspace(-2.0, 2.0, rows)
    return pd.DataFrame(
        {
            "x": x,
            "missing": np.where(np.arange(rows) % 7 == 0, np.nan, x * x),
            "all_missing": np.nan,
            "call_return": np.where(x > 0.0, 0.15 + x * 0.2, -0.25 - np.abs(x) * 0.1),
            "put_return": np.where(x < 0.0, 0.10 + np.abs(x) * 0.25, -0.20 - np.abs(x) * 0.1),
        }
    )


def test_hurdle_spec_freezes_complete_expected_utility() -> None:
    spec = frozen_spec()
    assert spec["family"] == "lightgbm_hurdle_expected_utility_v1"
    assert spec["utility"] == "p * gain - (1 - p) * loss"
    assert spec["winsor_source"].endswith("training rows only")
    assert len(frozen_spec_sha256()) == 64


def test_hurdle_fit_is_deterministic_and_train_only() -> None:
    train = _training_frame()
    model = fit_hurdle_utility(
        train,
        ["x", "missing", "all_missing"],
        call_return_col="call_return",
        put_return_col="put_return",
        base_seed=20260714,
    )
    assert model.medians["all_missing"] == 0.0
    score_a = model.score(train)
    score_b = model.score(train)
    np.testing.assert_allclose(score_a["utility_call"], score_b["utility_call"])
    np.testing.assert_allclose(score_a["utility_put"], score_b["utility_put"])
    assert (score_a["pred_call_gain"] >= 0.0).all()
    assert (score_a["pred_call_loss"] >= 0.0).all()


def test_hurdle_training_grid_has_only_frozen_percentiles() -> None:
    train = _training_frame()
    model = fit_hurdle_utility(
        train,
        ["x", "missing"],
        call_return_col="call_return",
        put_return_col="put_return",
        base_seed=42,
    )
    grid = training_percentile_grid(model.score(train))
    assert len(grid) == 42
    assert sorted({row["utility_percentile"] for row in grid}) == [50, 60, 70, 80, 85, 90, 95]
    assert sorted({row["margin_percentile"] for row in grid}) == [0, 10, 20, 30, 40, 50]
