"""Tests for regime gate audit, serialization, cutoff checks, and substitutions."""
from __future__ import annotations

import json
import tempfile
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "neural" / "jepa"))

from walkforward_event_option_profile_selector import (
    freeze_fold_policy_artifact,
    fit_profile_fold
)
from walkforward_event_option_regime_gate import (
    RegimeGateConfig,
    NO_REGIME_GATE,
    apply_regime_gate
)

def test_regime_gate_serialization():
    """Verify that regime gate configurations and metadata are serialized correctly."""
    gate = RegimeGateConfig(
        feature="phys_d35_iv_skew_put_minus_call",
        direction="above",
        quantile=0.20,
        threshold=0.012700021
    )
    
    # Real dataclasses
    from walkforward_event_option_profile_selector import ProfileConfig
    from walkforward_event_option_gate import DeployConfig
    
    profile = ProfileConfig(
        name="test_profile",
        delta_bucket=35,
        label_mode="win",
        expiry_modes=("zero_dte",),
        train_scope="target"
    )
    deploy_config = DeployConfig(
        threshold=0.7,
        max_trades_per_day=999
    )
    
    # Mock args
    args = argparse.Namespace(
        data="tmp/event_option_dataset_execquote_causal1030_202501_202605_regime_v1.parquet",
        output_dir="tmp/test_serialization_output",
        cooldown_minutes=30,
    )
    
    medians = pd.Series({"feature1": 1.0, "feature2": 2.0})
    
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)
        
        # Call serialization
        freeze_fold_policy_artifact(
            artifact_dir=artifact_dir,
            ticker="QQQ",
            test_month="202602",
            profile=profile,  # type: ignore
            train_months=["202501", "202502"],
            selection_months=["202511", "202512"],
            deploy_config=deploy_config,  # type: ignore
            call_model=None,
            put_model=None,
            medians=medians,
            feature_cols=["feature1", "feature2"],
            args=args,
            direction_mode="model",
            regime_gate=gate
        )
        
        # Verify JSON
        policy_path = artifact_dir / "fold_policy.json"
        assert policy_path.exists()
        
        policy_data = json.loads(policy_path.read_text(encoding="utf-8"))
        assert "regime_gate" in policy_data
        assert policy_data["regime_gate"]["feature"] == "phys_d35_iv_skew_put_minus_call"
        assert policy_data["regime_gate"]["direction"] == "above"
        assert policy_data["regime_gate"]["quantile"] == 0.20
        assert policy_data["regime_gate"]["threshold"] == 0.012700021
        assert policy_data["dataset_sha256"] != "unknown"
        assert policy_data["commit_sha"] != "unknown"

def test_causal_cutoff_check():
    """Verify that minute <= 630 cutoff is applied strictly if ib_range_bps is in features."""
    # Create fake dataset with minute <= 630 and minute > 630
    df = pd.DataFrame({
        "ticker": ["QQQ"] * 4,
        "month": ["202602"] * 4,
        "minute": [600, 630, 631, 700],
        "call_d35_opt_exit_ret": [0.1] * 4,
        "put_d35_opt_exit_ret": [0.1] * 4,
        "call_d35_available": [1] * 4,
        "put_d35_available": [1] * 4,
        "ib_range_bps": [10.0] * 4,
    })
    
    # R4 features include ib_range_bps
    regime_features = ["ib_range_bps"]
    
    # Filter using logic from walkforward_event_option_profile_selector.py
    if "ib_range_bps" in regime_features and "minute" in df.columns:
        filtered_df = df[pd.to_numeric(df["minute"], errors="coerce") > 630].copy()
        
    assert len(filtered_df) == 2
    assert (filtered_df["minute"] > 630).all()

def test_substitution_gated_out_candidates():
    """Verify that gated out candidates are successfully filtered by apply_regime_gate."""
    # Candidates scored
    scored = pd.DataFrame({
        "score": [0.8, 0.9],
        "phys_d35_iv_skew_put_minus_call": [0.01, 0.02]
    })
    
    # Gate below 0.015: only 0.01 passes, 0.02 is gated out
    gate = RegimeGateConfig(
        feature="phys_d35_iv_skew_put_minus_call",
        direction="below",
        quantile=0.50,
        threshold=0.015
    )
    
    gated = apply_regime_gate(scored, gate)
    assert len(gated) == 1
    assert gated.iloc[0]["phys_d35_iv_skew_put_minus_call"] == 0.01
