"""Tests for regime gate integration in walkforward_event_option_profile_selector."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "neural" / "jepa"))

from walkforward_event_option_profile_selector import (
    NO_REGIME_GATE,
    RegimeGateConfig,
    apply_regime_gate,
    build_regime_gates,
)


# ── build_regime_gates ──────────────────────────────────────────────


def _make_train(n: int = 200) -> pd.DataFrame:
    rng = np.random.RandomState(42)
    return pd.DataFrame({
        "phys_d25_iv_skew_put_minus_call": rng.normal(0, 0.05, n),
        "phys_d25_spread_mean": rng.exponential(0.02, n),
        "phys_abs_ret_5m_bps": rng.exponential(5, n),
        "ib_range_bps": rng.exponential(30, n),
    })


def test_build_regime_gates_returns_no_gate_first():
    """The first element must always be NO_REGIME_GATE (None)."""
    gates = build_regime_gates(_make_train(), ["phys_d25_iv_skew_put_minus_call"])
    assert gates[0] is NO_REGIME_GATE


def test_build_regime_gates_count():
    """4 quantiles × 2 directions + 1 no-gate per feature."""
    train = _make_train()
    gates = build_regime_gates(train, ["phys_d25_iv_skew_put_minus_call"])
    # 1 no-gate + 4 quantiles × 2 directions = 9
    assert len(gates) == 9


def test_build_regime_gates_multiple_features():
    train = _make_train()
    features = ["phys_d25_iv_skew_put_minus_call", "phys_d25_spread_mean"]
    gates = build_regime_gates(train, features)
    # 1 no-gate + 2 features × 4 quantiles × 2 directions = 17
    assert len(gates) == 17


def test_build_regime_gates_missing_feature():
    """Missing features must raise KeyError."""
    train = _make_train()
    with pytest.raises(KeyError):
        build_regime_gates(train, ["nonexistent_feature"])


def test_build_regime_gates_empty_features():
    """Empty feature list produces only no-gate."""
    gates = build_regime_gates(_make_train(), [])
    assert len(gates) == 1
    assert gates[0] is NO_REGIME_GATE


def test_build_regime_gates_uses_train_only_percentiles():
    """Verify that thresholds come from train data percentiles."""
    rng = np.random.RandomState(99)
    train = pd.DataFrame({"feat": rng.normal(100, 10, 500)})
    gates = build_regime_gates(train, ["feat"])
    # Find the gate with quantile 0.40
    q40_gates = [g for g in gates if g is not None and g.quantile == 0.40]
    assert len(q40_gates) == 2  # above and below
    expected = float(np.percentile(train["feat"], 40))
    for g in q40_gates:
        assert abs(g.threshold - expected) < 1e-6


def test_build_regime_gates_all_nan_feature():
    """Feature with all NaN produces no gates for that feature."""
    train = pd.DataFrame({"bad_feat": [np.nan] * 100})
    gates = build_regime_gates(train, ["bad_feat"])
    assert len(gates) == 1  # only no-gate


# ── apply_regime_gate ───────────────────────────────────────────────


def _make_scored() -> pd.DataFrame:
    return pd.DataFrame({
        "score": [0.1, 0.2, 0.3, 0.4, 0.5],
        "phys_d25_iv_skew_put_minus_call": [-0.1, -0.05, 0.0, 0.05, 0.1],
        "realized_return": [0.02, -0.01, 0.03, -0.02, 0.04],
    })


def test_apply_regime_gate_none():
    """No gate returns the full frame."""
    scored = _make_scored()
    result = apply_regime_gate(scored, NO_REGIME_GATE)
    assert len(result) == len(scored)


def test_apply_regime_gate_above():
    scored = _make_scored()
    gate = RegimeGateConfig(
        feature="phys_d25_iv_skew_put_minus_call",
        direction="above",
        quantile=0.60,
        threshold=0.0,
    )
    result = apply_regime_gate(scored, gate)
    # values >= 0.0: [0.0, 0.05, 0.1] → 3 rows
    assert len(result) == 3
    assert (result["phys_d25_iv_skew_put_minus_call"] >= 0.0).all()


def test_apply_regime_gate_below():
    scored = _make_scored()
    gate = RegimeGateConfig(
        feature="phys_d25_iv_skew_put_minus_call",
        direction="below",
        quantile=0.40,
        threshold=0.0,
    )
    result = apply_regime_gate(scored, gate)
    # values < 0.0: [-0.1, -0.05] → 2 rows
    assert len(result) == 2
    assert (result["phys_d25_iv_skew_put_minus_call"] < 0.0).all()


def test_apply_regime_gate_missing_feature():
    """Missing feature must raise KeyError."""
    scored = _make_scored()
    gate = RegimeGateConfig(
        feature="nonexistent",
        direction="above",
        quantile=0.50,
        threshold=0.0,
    )
    with pytest.raises(KeyError):
        apply_regime_gate(scored, gate)


def test_apply_regime_gate_empty_input():
    scored = pd.DataFrame(columns=["score", "phys_d25_iv_skew_put_minus_call"])
    gate = RegimeGateConfig(
        feature="phys_d25_iv_skew_put_minus_call",
        direction="above",
        quantile=0.50,
        threshold=0.0,
    )
    result = apply_regime_gate(scored, gate)
    assert len(result) == 0


# ── RegimeGateConfig ────────────────────────────────────────────────


def test_regime_gate_config_name():
    gate = RegimeGateConfig(
        feature="phys_d25_iv_skew_put_minus_call",
        direction="above",
        quantile=0.60,
        threshold=0.01,
    )
    assert gate.name == "rg_phys_d25_iv_skew_put_minus_call_above_q60pct"


def test_regime_gate_config_frozen():
    gate = RegimeGateConfig(
        feature="feat",
        direction="above",
        quantile=0.20,
        threshold=1.0,
    )
    with pytest.raises(AttributeError):
        gate.feature = "other"  # type: ignore[misc]


# ── Causality: train percentiles must NOT include val/test ──────────


def test_regime_gate_train_val_isolation():
    """Gate thresholds computed on train must differ from those using val data."""
    rng = np.random.RandomState(7)
    n_train = 200
    n_val = 100
    # train: normal(50, 5), val: normal(80, 5) — very different distributions
    train = pd.DataFrame({"feat": rng.normal(50, 5, n_train)})
    val = pd.DataFrame({"feat": rng.normal(80, 5, n_val)})
    combined = pd.concat([train, val], ignore_index=True)

    gates_train = build_regime_gates(train, ["feat"])
    gates_combined = build_regime_gates(combined, ["feat"])

    # Thresholds must differ because val data has higher values
    train_thresholds = {g.threshold for g in gates_train if g is not None}
    combined_thresholds = {g.threshold for g in gates_combined if g is not None}
    assert train_thresholds != combined_thresholds


# ── Integration: regime gate applied to scored candidates ───────────


def test_regime_gate_reduces_trades():
    """When a gate is applied, the number of surviving rows must be <= original."""
    rng = np.random.RandomState(123)
    n = 500
    scored = pd.DataFrame({
        "score": rng.uniform(0, 1, n),
        "phys_abs_ret_5m_bps": rng.exponential(5, n),
    })
    # Build gates from the same data (just for testing the filter)
    gates = build_regime_gates(scored, ["phys_abs_ret_5m_bps"])
    for gate in gates:
        if gate is None:
            continue
        result = apply_regime_gate(scored, gate)
        assert len(result) <= len(scored)
        assert len(result) > 0  # with 500 rows, no percentile gate should empty it


def test_build_regime_gates_allowed_direction():
    """Verify that build_regime_gates properly filters configurations by allowed direction."""
    train = _make_train()
    
    # 1. Force 'below' direction
    gates_below = build_regime_gates(train, ["phys_d25_spread_mean"], allowed_direction="below")
    # Should only contain NO_REGIME_GATE and gates with direction == 'below'
    for g in gates_below:
        if g is not None:
            assert g.direction == "below"
            
    # 2. Force 'above' direction
    gates_above = build_regime_gates(train, ["phys_d25_spread_mean"], allowed_direction="above")
    for g in gates_above:
        if g is not None:
            assert g.direction == "above"
            
    # 3. 'any' direction includes both
    gates_any = build_regime_gates(train, ["phys_d25_spread_mean"], allowed_direction="any")
    directions = {g.direction for g in gates_any if g is not None}
    assert directions == {"above", "below"}


def test_build_regime_gates_constant_feature():
    """Verify that build_regime_gates handles constant features correctly without duplicate thresholds."""
    train = pd.DataFrame({"constant_feat": [42.0] * 100})
    gates = build_regime_gates(train, ["constant_feat"])
    # 1 no-gate + 2 directions (above, below) with threshold=42.0 and quantile=0.50
    assert len(gates) == 3
    assert gates[0] is NO_REGIME_GATE
    assert gates[1].threshold == 42.0
    assert gates[1].quantile == 0.50
    assert gates[2].threshold == 42.0
    assert gates[2].quantile == 0.50


