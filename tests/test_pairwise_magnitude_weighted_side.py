from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "neural" / "jepa"))
from walkforward_pairwise_magnitude_weighted_side_v1 import magnitude_weights, physics_side_feature_cols


def test_magnitude_weights_are_train_only_clipped_and_normalized():
    train = pd.Series([0.1, -0.2, 0.3, -10.0])
    weights, cap = magnitude_weights(train, quantile=0.75)
    assert cap == np.quantile(np.abs(train), 0.75)
    assert np.isclose(weights.mean(), 1.0)
    assert weights[-1] == weights.max()
    assert weights[-1] < 10.0 / np.abs(train).mean()


def test_magnitude_weights_reject_zero_or_nonfinite_advantage():
    for values in ([0.1, 0.0], [0.1, np.nan], [0.1, np.inf]):
        try:
            magnitude_weights(pd.Series(values))
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected ValueError for {values}")


def test_physics_side_features_are_current_time_and_exclude_nonlive_event_fields():
    base = ["minute", "ret_30m_bps"]
    columns = base + [
        "phys_d35_iv_mean", "phys_total_option_volume_log", "ctx_spx_ret_5m_bps",
        "ctx_spx_spot", "phys_event_seq_in_day", "future_close_ret_bps",
        "call_d35_opt_exit_ret",
    ]
    result = physics_side_feature_cols(columns, base)
    assert result == base + ["phys_d35_iv_mean", "phys_total_option_volume_log", "ctx_spx_ret_5m_bps"]
