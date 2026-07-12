from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from neural.jepa.evaluate_wall_iv_surface_at_touch_v1 import (
    GATE_SPEC,
    IV_SURFACE_ALLOWLIST,
    LR_PARAMS,
    assert_no_flow_features,
    feature_names,
    fit_model,
    make_lr_pipeline,
)
from neural.jepa.surface_flow_features import (
    CONTROL_FEATURES,
    FLOW_FEATURES,
    WALL_SPECS,
)
from neural.jepa.iv_surface_deformation_features import IV_SURFACE_FEATURES


def test_frozen_allowlist_excludes_all_hflow_features() -> None:
    identities = [f"identity_{name}" for name in sorted(WALL_SPECS)]
    assert feature_names("F0") == [*CONTROL_FEATURES, *identities]
    assert feature_names("F1") == [
        *CONTROL_FEATURES,
        *IV_SURFACE_ALLOWLIST,
        *identities,
    ]
    assert not set(feature_names("F1")).intersection(FLOW_FEATURES)
    assert len(IV_SURFACE_FEATURES) == 18
    assert len(IV_SURFACE_ALLOWLIST) == 23
    assert_no_flow_features(feature_names("F1"))
    with pytest.raises(AssertionError, match="H-FLOW"):
        assert_no_flow_features([FLOW_FEATURES[0]])


def test_primary_model_and_sequential_gate_are_frozen() -> None:
    pipeline = make_lr_pipeline()
    assert pipeline.named_steps["imputer"].strategy == "median"
    assert pipeline.named_steps["imputer"].add_indicator is True
    assert pipeline.named_steps["standardizer"].with_mean is True
    assert LR_PARAMS["C"] == 1.0
    assert LR_PARAMS["max_iter"] == 5000
    assert LR_PARAMS["random_state"] == 20260712
    assert GATE_SPEC["maximum_wilcoxon_one_sided_p"] == 0.025
    assert GATE_SPEC["sensitivity_minimum_wins"] == 13
    assert GATE_SPEC["sensitivity_can_rescue_primary"] is False


def test_lr_imputation_is_train_only_and_missing_indicators_are_fitted(
    tmp_path,
) -> None:
    rng = np.random.default_rng(3)
    rows = 60
    raw_names = [*CONTROL_FEATURES, *IV_SURFACE_ALLOWLIST]
    frame = pd.DataFrame({name: rng.normal(size=rows) for name in raw_names})
    frame["wall_identity"] = "gex_max"
    frame.loc[:9, IV_SURFACE_FEATURES[0]] = np.nan
    frame["target"] = np.tile([0, 1], rows // 2)
    train, test = frame.iloc[:40].copy(), frame.iloc[40:].copy()
    # A wildly shifted test distribution must not alter the learned train median.
    test.loc[:, IV_SURFACE_FEATURES[0]] = 1_000_000.0
    result, probability, _ = fit_model(
        train, test, "target", "F1", "lr", tmp_path / "model.joblib"
    )
    assert result["valid"] is True
    assert probability is not None and len(probability) == len(test)
    assert (tmp_path / "model.joblib").exists()
