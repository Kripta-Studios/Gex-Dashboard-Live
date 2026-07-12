from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from neural.jepa.evaluate_wall_quote_size_pressure_at_touch_v1 import (
    GATE_SPEC,
    LR_PARAMS,
    assert_no_closed_features,
    feature_names,
    fit_model,
    make_lr_pipeline,
    summarize_gate,
    assert_qsize_source_inventory,
)
from neural.jepa.iv_surface_deformation_features import IV_SURFACE_FEATURES
from neural.jepa.quote_size_pressure_features import (
    QSIZE_FEATURES,
    QSIZE_QUALITY_FIELDS,
)
from neural.jepa.surface_flow_features import (
    CONTROL_FEATURES,
    FLOW_FEATURES,
    WALL_SPECS,
)


def test_frozen_model_allowlist_excludes_closed_and_quality_fields() -> None:
    identities = [f"identity_{name}" for name in sorted(WALL_SPECS)]
    assert feature_names("F0") == [*CONTROL_FEATURES, *identities]
    assert feature_names("F1") == [*CONTROL_FEATURES, *QSIZE_FEATURES, *identities]
    assert len(QSIZE_FEATURES) == 40
    assert len(QSIZE_QUALITY_FIELDS) == 5
    assert not set(feature_names("F1")).intersection(QSIZE_QUALITY_FIELDS)
    assert not set(feature_names("F1")).intersection(FLOW_FEATURES)
    assert not set(feature_names("F1")).intersection(IV_SURFACE_FEATURES)
    assert_no_closed_features(feature_names("F1"))
    with pytest.raises(AssertionError, match="H-FLOW/H-IVSURF"):
        assert_no_closed_features([FLOW_FEATURES[0]])


def test_primary_model_and_third_sequential_gate_are_frozen() -> None:
    pipeline = make_lr_pipeline()
    assert pipeline.named_steps["imputer"].strategy == "median"
    assert pipeline.named_steps["imputer"].add_indicator is False
    assert pipeline.named_steps["standardizer"].with_mean is True
    assert LR_PARAMS["C"] == 1.0
    assert LR_PARAMS["max_iter"] == 5000
    assert LR_PARAMS["random_state"] == 20260712
    assert GATE_SPEC["maximum_wilcoxon_one_sided_p"] == 0.0167
    assert GATE_SPEC["sensitivity_can_rescue_primary"] is False


def test_lr_imputation_is_train_only(tmp_path) -> None:
    rng = np.random.default_rng(17)
    rows = 60
    raw_names = [*CONTROL_FEATURES, *QSIZE_FEATURES]
    frame = pd.DataFrame({name: rng.normal(size=rows) for name in raw_names})
    frame["wall_identity"] = "gex_max"
    frame.loc[:9, QSIZE_FEATURES[0]] = np.nan
    frame["target"] = np.tile([0, 1], rows // 2)
    train, test = frame.iloc[:40].copy(), frame.iloc[40:].copy()
    test.loc[:, QSIZE_FEATURES[0]] = 1_000_000.0
    result, probability, _ = fit_model(
        train, test, "target", "F1", "lr", tmp_path / "model.joblib"
    )
    assert result["valid"] is True
    assert probability is not None and len(probability) == len(test)
    assert (tmp_path / "model.joblib").exists()


def test_gate_uses_third_sequential_p_threshold(monkeypatch) -> None:
    passing_family = {
        "valid_paired_cells": 24,
        "wins": 24,
        "median_auc_delta": 0.02,
        "wilcoxon_one_sided_p": 0.02,
        "ticker_pass": True,
        "joint_average_precision_logloss_losses": 0,
    }
    sensitivity = {
        **passing_family,
        "wilcoxon_one_sided_p": 0.0,
        "wins": 24,
    }

    def fake_family_gate(_cells, _paired, family):
        return passing_family if family == "lr" else sensitivity

    monkeypatch.setattr(
        "neural.jepa.evaluate_wall_quote_size_pressure_at_touch_v1._family_gate",
        fake_family_gate,
    )
    monthly = pd.DataFrame(
        {
            "horizon": np.tile([30, 60], 72),
            "resolved_episodes": np.full(144, 18),
            "both_classes": np.ones(144, dtype=bool),
        }
    )
    summary = summarize_gate(
        pd.DataFrame(), pd.DataFrame(), monthly, "CONDITIONAL", "BLOCKED"
    )
    assert summary["primary_physical_pass"] is False
    assert summary["physical_mechanism_pass"] is False


def test_qsize_inventory_rejects_incomplete_or_swapped_source() -> None:
    with pytest.raises(AssertionError, match="schema"):
        assert_qsize_source_inventory(pd.DataFrame({"ticker": ["SPY"]}))
