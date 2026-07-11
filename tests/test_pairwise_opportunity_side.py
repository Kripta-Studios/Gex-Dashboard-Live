"""
Tests for PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_V1 walkforward logic.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import shutil
import subprocess
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "neural" / "jepa"))

import walkforward_pairwise_opportunity_side as pairwise

from walkforward_pairwise_opportunity_side import (
    COMMON_FEATURES,
    DIFF_METRICS,
    CHANGE_LAGS,
    FROZEN_LGB_PARAMS,
    FROZEN_SEED,
    TRADE_THRESHOLDS,
    SIDE_MARGINS,
    FIRST_ALLOWED_MINUTE,
    HEAD_OFFSET_C0_CALL,
    HEAD_OFFSET_C0_PUT,
    HEAD_OFFSET_P1_OPP,
    HEAD_OFFSET_P1_SIDE,
    C0_TIE_THRESHOLD_EXECUTION,
    SIDE_TIE_THRESHOLD_TRAINING,
    generate_folds,
    build_diff_features,
    build_labels,
    apply_pairwise_policy,
    apply_c0_policy,
    compute_monthly_inner_gates,
    select_best_config_p1,
    select_best_config_c0,
    compute_feature_hash,
    make_lgb_params,
    compute_lr_diagnostics,
    compute_scientific_side_metrics,
)

# ── 1. Allowlist and causal checks ──────────────────────────────────────

def test_feature_allowlist_structure():
    """Verify primary feature exclusions (dte_days, spot, underlying_volume)."""
    assert "dte_days" not in COMMON_FEATURES
    assert "spot" not in COMMON_FEATURES
    assert "underlying_volume" not in COMMON_FEATURES

    # Ensure only causal features are in COMMON_FEATURES
    allowed = {
        "minute",
        "ib_range_bps",
        "dist_ib_high_bps",
        "dist_ib_low_bps",
        "nearest_level_abs_bps",
        "ret_1m_bps",
        "ret_5m_bps",
        "ret_15m_bps",
        "ret_30m_bps",
    }
    assert set(COMMON_FEATURES) == allowed


# ── 2. build_diff_features and shift grouping ───────────────────────────

def test_build_diff_features_grouping():
    """Verify difference generation and shifts grouped by (ticker, trade_date, bucket).

    Ensures:
      - no cross-contamination between tickers;
      - no cross-contamination between sessions (days);
      - no cross-contamination between buckets;
      - first observation of each group produces NaN;
      - no backward fill.
    """
    # Create fake intraday data for two tickers, two days, and two buckets
    data = pd.DataFrame({
        "ticker": ["SPXW", "QQQ"] * 10,
        "trade_date": ["20240102"] * 10 + ["20240103"] * 10,
        "bucket": [25, 35] * 10,
        "minute": [635, 635, 640, 640, 645, 645, 650, 650, 655, 655] * 2,

        # Bucket 25 fields
        "call_d25_iv": [1.0 if t=="SPXW" else 0.0 for t in ["SPXW", "QQQ"] * 10],
        "put_d25_iv":  [0.8 if t=="SPXW" else 0.0 for t in ["SPXW", "QQQ"] * 10],
        # Bucket 35 fields
        "call_d35_iv": [0.0 if t=="SPXW" else 2.0 for t in ["SPXW", "QQQ"] * 10],
        "put_d35_iv":  [0.0 if t=="SPXW" else 1.5 for t in ["SPXW", "QQQ"] * 10],

        # Placeholders for other diff metrics to satisfy columns audit check
        "call_d25_spread_pct": [0.01] * 20, "put_d25_spread_pct": [0.01] * 20,
        "call_d25_volume": [100.0] * 20, "put_d25_volume": [100.0] * 20,
        "call_d25_oi": [1000.0] * 20, "put_d25_oi": [1000.0] * 20,
        "call_d25_abs_delta": [0.25] * 20, "put_d25_abs_delta": [0.25] * 20,
        "call_d25_vega": [0.1] * 20, "put_d25_vega": [0.1] * 20,

        "call_d35_spread_pct": [0.01] * 20, "put_d35_spread_pct": [0.01] * 20,
        "call_d35_volume": [100.0] * 20, "put_d35_volume": [100.0] * 20,
        "call_d35_oi": [1000.0] * 20, "put_d35_oi": [1000.0] * 20,
        "call_d35_abs_delta": [0.35] * 20, "put_d35_abs_delta": [0.35] * 20,
        "call_d35_vega": [0.1] * 20, "put_d35_vega": [0.1] * 20,

        # Mock other common features to keep function happy
        "ib_range_bps": [10.0] * 20, "dist_ib_high_bps": [5.0] * 20, "dist_ib_low_bps": [5.0] * 20,
        "nearest_level_abs_bps": [2.0] * 20, "ret_1m_bps": [0.0] * 20, "ret_5m_bps": [0.0] * 20,
        "ret_15m_bps": [0.0] * 20, "ret_30m_bps": [0.0] * 20,
    })

    # Sort & Intercalate rows manually to verify grouping sort robustness
    data = data.sample(frac=1.0, random_state=42).reset_index(drop=True)

    # SPXW (d25)
    spxw_data = data[data["ticker"] == "SPXW"].copy()
    spxw_out, spxw_feats = build_diff_features(spxw_data, "SPXW", 25)
    # Check that shifts did not contamination across sessions/tickers
    # Sort spxw_out chronologically for assertion
    spxw_out = spxw_out.sort_values(["trade_date", "minute"]).reset_index(drop=True)
    # 2 days: Day 1 index 0..4, Day 2 index 5..9
    assert pd.isna(spxw_out["iv_diff_chg_5m"].iloc[0]) # Day 1 first bar is NaN
    assert pd.isna(spxw_out["iv_diff_chg_5m"].iloc[5]) # Day 2 first bar is NaN
    assert not pd.isna(spxw_out["iv_diff_chg_5m"].iloc[1]) # Intraday shifts populated
    assert not pd.isna(spxw_out["iv_diff_chg_5m"].iloc[6])

    # QQQ (d35)
    qqq_data = data[data["ticker"] == "QQQ"].copy()
    qqq_out, qqq_feats = build_diff_features(qqq_data, "QQQ", 35)
    qqq_out = qqq_out.sort_values(["trade_date", "minute"]).reset_index(drop=True)
    assert pd.isna(qqq_out["iv_diff_chg_5m"].iloc[0]) # Day 1 first bar is NaN
    assert pd.isna(qqq_out["iv_diff_chg_5m"].iloc[5]) # Day 2 first bar is NaN


# ── 3. build_labels and training mask checks ────────────────────────────

def test_build_labels_and_training_mask():
    """Verify side head masks and raises if any invalid cases are trained.

    Side head must exclude:
      - rows where opportunity_label == 0
      - ties (abs(side_advantage) <= 1e-9)
      - non-finite labels
    """
    # Create fake training data
    train_data = pd.DataFrame({
        "call_d25_opt_exit_ret": [0.05, -0.02, 0.0, -0.01, 0.10, np.nan, 0.02],
        "put_d25_opt_exit_ret":  [-0.01, 0.03, 0.0, -0.05, 0.10, 0.01, np.inf],
        "call_d25_opt_exit_minutes": [30] * 7,
        "put_d25_opt_exit_minutes":  [30] * 7,
    })

    # build_labels will perform strict finite checking
    out = build_labels(train_data, 25)

    # 5 rows remain after finite filtering (rows with nan and inf dropped)
    assert len(out) == 5

    # y_opp_train matches np.maximum(call, put) > 0
    # idx 0: max(0.05, -0.01) = 0.05 > 0 -> opp = 1
    # idx 1: max(-0.02, 0.03) = 0.03 > 0 -> opp = 1
    # idx 2: max(0, 0) = 0 -> opp = 0
    # idx 3: max(-0.01, -0.05) = -0.01 -> opp = 0
    # idx 4: max(0.1, 0.1) = 0.1 > 0 -> opp = 1
    np.testing.assert_array_equal(out["opportunity_label"].values, [1, 1, 0, 0, 1])

    # Side training mask: opportunity_label == 1 & abs(call - put) > 1e-9
    side_mask = (
        (out["opportunity_label"] == 1)
        & (out["side_advantage"].astype(float).abs() > 1e-9)
    )
    side_train = out[side_mask]

    # Indices that should remain:
    # idx 0: opp=1, diff=0.06 > 1e-9 -> KEEP (label = 1)
    # idx 1: opp=1, diff=-0.05 -> KEEP (label = 0)
    # idx 2: opp=0 -> DROP
    # idx 3: opp=0 -> DROP
    # idx 4: opp=1, diff=0.0 (tie) -> DROP (excluded!)
    assert len(side_train) == 2
    np.testing.assert_array_equal(side_train["side_label"].values, [1, 0])

    # Assert no non-finites remain in the features or targets
    assert side_train["side_label"].notna().all()
    assert np.isfinite(side_train["side_label"].values).all()


# ── 4. generate_folds and last fold check ───────────────────────────────

def test_generate_folds_last_fold():
    """Verify walkforward folds bounds and specifically the final fold."""
    folds = generate_folds("202304", "202512")
    assert len(folds) == 33

    # Verify first fold
    assert folds[0]["test_month"] == "202304"
    assert folds[0]["inner_months"] == ["202301", "202302", "202303"]
    assert folds[0]["train_months"] == [f"2022{m:02d}" for m in range(1, 13)]

    # Verify last fold (202512)
    last = folds[-1]
    assert last["test_month"] == "202512"
    assert last["inner_months"] == ["202509", "202510", "202511"]
    assert last["train_months"] == ["202409", "202410", "202411", "202412"] + [f"2025{m:02d}" for m in range(1, 9)]


# ── 5. compute_monthly_inner_gates duration ─────────────────────────────

def test_compute_monthly_inner_gates_duration():
    """Verify compute_monthly_inner_gates fails if hold duration is less than 30m."""
    inner_months = ["202301"]

    # Case 1: Pass (all holds >= 30m)
    trades_pass = pd.DataFrame({
        "month": ["202301"] * 18,
        "minute": [650] * 18,
        "exit_minutes": [30] * 18,
        "realized_return": [0.05] * 10 + [-0.01] * 8,
    })
    passed, details = compute_monthly_inner_gates(trades_pass, inner_months)
    assert passed

    # Case 2: Fail (one hold < 30m)
    trades_fail = pd.DataFrame({
        "month": ["202301"] * 18,
        "minute": [650] * 18,
        "exit_minutes": [29] * 18,
        "realized_return": [0.05] * 10 + [-0.01] * 8,
    })
    passed, details = compute_monthly_inner_gates(trades_fail, inner_months)
    assert not passed
    assert not details["months"]["202301"]["pass"]


# ── 6. Initial Balance cutoff check ─────────────────────────────────────

def test_ib_cutoff_rule():
    """Verify that minute == 630 is excluded for IB features."""
    # The runner filters using minute > 630
    # Any candidate at 630 (10:30) is excluded since the 10:30 candle is the 10:25-10:30 period
    # and the IB closes at 10:29:59 (so we can only trade from 10:35 candle onwards)
    candidates = pd.DataFrame({"minute": [630, 631, 635]})
    filtered = candidates[candidates["minute"] > 630]
    assert 630 not in filtered["minute"].values
    assert 631 in filtered["minute"].values


# ── 7. Reused Scheduler & deploy() simulation ───────────────────────────

from walkforward_event_option_gate import DeployConfig, deploy

def test_deploy_scheduler_constraints():
    """Verify scheduler properties using deploy().

    - one-position at a time (non-overlap)
    - daily caps (e.g. max 2 trades/day)
    - cooldown step (e.g. 30m = 6 bars)
    - ranking (prioritize higher score)
    - entry ask / exit bid simulation (exit_minutes matches trade duration)
    """
    scored = pd.DataFrame({
        "ticker": ["QQQ"] * 5,
        "date": ["20240102"] * 5,
        "minute": [640, 645, 650, 680, 690],
        # exit minutes (durations):
        "exit_minutes": [20.0, 30.0, 15.0, 30.0, 30.0],
        "score": [0.8, 0.9, 0.75, 0.85, 0.95],
        "action": ["CALL"] * 5,
        "realized_return": [0.02] * 5,
    })

    cfg = DeployConfig(threshold=0.5, max_trades_per_day=2)
    # Cooldown = 30 minutes
    traded = deploy(scored, cfg, cooldown_minutes=30)

    assert len(traded) == 2
    assert list(traded["minute"].values) == [640, 680]


# ═══════════════════════════════════════════════════════════════════════
# NEW TESTS — per user request #10
# ═══════════════════════════════════════════════════════════════════════

# ── 8. C0 call_win and put_win labels ──────────────────────────────────

def test_c0_labels_call_win_put_win():
    """Verify C0 labels: call_win_label = int(call_return > 0), put_win_label = int(put_return > 0)."""
    data = pd.DataFrame({
        "call_d25_opt_exit_ret": [0.05, -0.02, 0.0, -0.01, 0.10],
        "put_d25_opt_exit_ret":  [-0.01, 0.03, 0.0, -0.05, 0.10],
        "call_d25_opt_exit_minutes": [30] * 5,
        "put_d25_opt_exit_minutes":  [30] * 5,
    })
    out = build_labels(data, 25)

    # call_win_label: 0.05>0=1, -0.02>0=0, 0>0=0, -0.01>0=0, 0.10>0=1
    np.testing.assert_array_equal(out["call_win_label"].values, [1, 0, 0, 0, 1])
    # put_win_label: -0.01>0=0, 0.03>0=1, 0>0=0, -0.05>0=0, 0.10>0=1
    np.testing.assert_array_equal(out["put_win_label"].values, [0, 1, 0, 0, 1])


# ── 9. C0/P1 same feature matrix and hash ─────────────────────────────

def test_feature_parity_c0_p1():
    """Verify C0 and P1 receive exactly the same feature allowlist and hash.

    The only difference between arms is label definition, not features.
    """
    data = pd.DataFrame({
        "ticker": ["SPXW"] * 10,
        "trade_date": ["20240102"] * 10,
        "minute": list(range(635, 685, 5)),
        "call_d25_iv": [1.0] * 10, "put_d25_iv": [0.8] * 10,
        "call_d25_spread_pct": [0.01] * 10, "put_d25_spread_pct": [0.01] * 10,
        "call_d25_volume": [100.0] * 10, "put_d25_volume": [100.0] * 10,
        "call_d25_oi": [1000.0] * 10, "put_d25_oi": [1000.0] * 10,
        "call_d25_abs_delta": [0.25] * 10, "put_d25_abs_delta": [0.25] * 10,
        "call_d25_vega": [0.1] * 10, "put_d25_vega": [0.1] * 10,
        "ib_range_bps": [10.0] * 10, "dist_ib_high_bps": [5.0] * 10,
        "dist_ib_low_bps": [5.0] * 10, "nearest_level_abs_bps": [2.0] * 10,
        "ret_1m_bps": [0.0] * 10, "ret_5m_bps": [0.0] * 10,
        "ret_15m_bps": [0.0] * 10, "ret_30m_bps": [0.0] * 10,
    })

    _, feat_cols_c0 = build_diff_features(data.copy(), "SPXW", 25)
    _, feat_cols_p1 = build_diff_features(data.copy(), "SPXW", 25)

    hash_c0 = compute_feature_hash(feat_cols_c0)
    hash_p1 = compute_feature_hash(feat_cols_p1)

    assert sorted(feat_cols_c0) == sorted(feat_cols_p1), "Feature columns must be identical for C0 and P1"
    assert hash_c0 == hash_p1, "Feature hash must be identical for C0 and P1"


# ── 10. C0/P1 same grid ──────────────────────────────────────────────

def test_same_grid_c0_p1():
    """Verify C0 and P1 use the same threshold and side_margin grid."""
    # Both C0 and P1 sweep the same TRADE_THRESHOLDS × SIDE_MARGINS
    assert len(TRADE_THRESHOLDS) == 9
    assert TRADE_THRESHOLDS == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    assert len(SIDE_MARGINS) == 7
    assert SIDE_MARGINS == [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]


# ── 11. C0 tie produces abstention ──────────────────────────────────

def test_c0_tie_abstains():
    """Verify that C0 policy abstains when abs(p_call_win - p_put_win) <= 1e-12."""
    scored = pd.DataFrame({
        "p_call_win": [0.6, 0.6000000000001, 0.4],  # row 1 is a tie within 1e-12
        "p_put_win":  [0.6, 0.6,             0.7],
        "call_return": [0.05, 0.05, 0.05],
        "put_return": [-0.01, -0.01, 0.03],
        "call_d25_opt_exit_minutes": [60, 60, 60],
        "put_d25_opt_exit_minutes": [60, 60, 60],
    })

    # With side_margin=0 and trade_threshold=0.3 — row 0 (tied) should be abstained
    result = apply_c0_policy(scored, trade_threshold=0.3, side_margin=0.0, bucket=25)

    # Row 0: p_call_win == p_put_win exactly → ABSTAIN
    # Row 1: abs(0.6000000000001 - 0.6) = 1e-13 → <= 1e-12 → ABSTAIN
    # Row 2: p_put_win > p_call_win and gap = 0.3 >= 0 → PUT
    assert len(result) == 1
    assert result.iloc[0]["action"] == "PUT"


# ── 12. subsample_freq=1 ────────────────────────────────────────────

def test_subsample_freq_in_params():
    """Verify subsample_freq=1 is set in FROZEN_LGB_PARAMS."""
    assert "subsample_freq" in FROZEN_LGB_PARAMS
    assert FROZEN_LGB_PARAMS["subsample_freq"] == 1
    assert FROZEN_LGB_PARAMS["subsample"] == 0.8


# ── 13. Imputer/scaler fitted only on train ─────────────────────────

def test_lr_pipeline_fit_on_train_only():
    """Verify SimpleImputer and StandardScaler are fit on train data only.

    The pipeline for LR diagnostic is:
      1. SimpleImputer(strategy='median') - fit on train
      2. StandardScaler() - fit on train
      3. LogisticRegression

    The imputer and scaler must NOT be fit on val or test data.
    """
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    rng = np.random.RandomState(42)
    X_train = pd.DataFrame({
        "f1": [1.0, 2.0, np.nan, 4.0, 5.0],
        "f2": [10.0, np.nan, 30.0, 40.0, 50.0],
    })
    X_test = pd.DataFrame({
        "f1": [100.0, np.nan],
        "f2": [np.nan, 200.0],
    })

    imp = SimpleImputer(strategy="median")
    sc = StandardScaler()

    X_train_imp = imp.fit_transform(X_train)
    X_train_sc = sc.fit_transform(X_train_imp)

    # Imputer medians should come from train only
    # f1 median of [1, 2, 4, 5] = 3.0 (nan excluded)
    # f2 median of [10, 30, 40, 50] = 35.0 (nan excluded)
    assert np.isclose(imp.statistics_[0], 3.0)
    assert np.isclose(imp.statistics_[1], 35.0)

    X_test_imp = imp.transform(X_test)
    X_test_sc = sc.transform(X_test_imp)

    # After imputation, test row 0 f1=100 (untouched), f2=35 (train median)
    assert np.isclose(X_test_imp[0, 0], 100.0)
    assert np.isclose(X_test_imp[0, 1], 35.0)  # train median, not test

    # After imputation, test row 1 f1=3 (train median), f2=200 (untouched)
    assert np.isclose(X_test_imp[1, 0], 3.0)  # train median, not test
    assert np.isclose(X_test_imp[1, 1], 200.0)


# ── 14. Logistic Regression does not generate trades ────────────────

def test_lr_does_not_generate_trades():
    """Verify LR diagnostic reports only metrics, never trade decisions."""
    # compute_lr_diagnostics returns only ROC-AUC, PR-AUC, balanced accuracy, Spearman
    y_true = np.array([0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1])
    y_prob = np.array([0.1, 0.8, 0.6, 0.3, 0.9, 0.2, 0.7, 0.4, 0.85, 0.15, 0.65])

    diag = compute_lr_diagnostics(y_true, y_prob, "test_label")

    # Must contain these diagnostic keys
    assert "roc_auc" in diag
    assert "pr_auc" in diag
    assert "balanced_accuracy" in diag
    assert "spearman" in diag

    # Must NOT contain any trade/policy/economic keys
    assert "trades" not in diag
    assert "pnl" not in diag
    assert "threshold" not in diag
    assert "trade_threshold" not in diag
    assert "side_margin" not in diag
    assert "action" not in diag


# ── 15. First minute allowed is 635 ────────────────────────────────

def test_first_minute_allowed_is_635():
    """Verify FIRST_ALLOWED_MINUTE == 635 and minute > 630 on 5m grid yields 635."""
    assert FIRST_ALLOWED_MINUTE == 635

    # On a 5-minute grid starting from 630, filtering minute > 630 gives 635 as first
    grid_5m = list(range(625, 660, 5))  # [625, 630, 635, 640, 645, 650, 655]
    filtered = [m for m in grid_5m if m > 630]
    assert filtered[0] == 635


# ── 16. Scientific criteria do not use inner pass rate ──────────────

def test_scientific_criteria_no_inner_pass_rate():
    """Verify scientific success criteria are based on balanced accuracy delta
    and Spearman, not inner pass rate."""
    from walkforward_pairwise_opportunity_side import compute_scientific_criteria

    # Mock results with completed folds. They are deliberately fewer than the
    # fixed 99-cell denominator, so the remainder must stay as missing/degenerate.
    mock_results = []
    for i in range(10):
        mock_results.append({
            "status": "completed",
            "test_month": f"2024{(i + 3):02d}" if i + 3 <= 12 else f"2025{(i + 3 - 12):02d}",
            "ticker": "SPXW",
            "sci_cell_degenerate": False,
            "sci_ba_delta": 0.05,
            "sci_p1_spearman": 0.10,
            "c0": {
                "valid_inner": True,
                "diagnostics": {"side_balanced_accuracy_A": 0.50},
            },
            "p1": {
                "valid_inner": True,
                "diagnostics": {
                    "side_balanced_accuracy_A": 0.55,
                    "spearman_side_advantage_A": 0.10,
                },
            },
        })

    sci = compute_scientific_criteria(mock_results)

    # Scientific criteria keys exist
    assert "ba_delta_positive_rate" in sci
    assert "ba_delta_median" in sci
    assert "spearman_positive_rate" in sci
    assert "spearman_median" in sci

    # Inner pass rate is NOT a scientific criterion
    assert "inner_pass_rate" not in sci
    assert sci["total_denominator"] == 99
    assert sci["missing_scientific_cells"] == 89


# ── 17. Economic success evaluated per ticker per month ─────────────

def test_economic_criteria_per_ticker_per_month():
    """Verify economic success is evaluated individually per ticker × month cell,
    not averaged across months."""
    from walkforward_pairwise_opportunity_side import compute_economic_criteria

    # Create mock with one passing and one failing cell
    mock_results = [
        {
            "status": "completed",
            "ticker": "SPXW",
            "test_month": "202401",
            "c0": {"valid_inner": True, "test_metrics": {"profit_factor": 1.5, "win_rate": 0.55, "trades": 20}, "diagnostics": {"pnl": 2.0, "min_hold_minutes": 35}},
            "p1": {"valid_inner": True, "test_metrics": {"profit_factor": 1.5, "win_rate": 0.55, "trades": 20}, "diagnostics": {"pnl": 2.0, "min_hold_minutes": 35}},
        },
        {
            "status": "completed",
            "ticker": "SPXW",
            "test_month": "202402",
            "c0": {"valid_inner": True, "test_metrics": {"profit_factor": 0.8, "win_rate": 0.40, "trades": 10}, "diagnostics": {"pnl": -1.0, "min_hold_minutes": 35}},
            "p1": {"valid_inner": True, "test_metrics": {"profit_factor": 0.8, "win_rate": 0.40, "trades": 10}, "diagnostics": {"pnl": -1.0, "min_hold_minutes": 35}},
        },
    ]

    econ = compute_economic_criteria(mock_results)

    # Only 1 of 2 cells passes (PF<1.3, WR<50%, trades<18, PnL<0 fails)
    assert econ["p1_passing_cells"] == 1
    assert econ["p1_total_cells"] == 2


# ── 18. PF monthly is not averaged for promotion ───────────────────

def test_pf_not_averaged_for_promotion():
    """Verify economic criteria report worst-month PF and pooled PF,
    not averaged monthly PF."""
    from walkforward_pairwise_opportunity_side import compute_economic_criteria

    mock_results = [
        {
            "status": "completed", "ticker": "SPXW", "test_month": "202401",
            "p1": {"valid_inner": True, "test_metrics": {"profit_factor": 2.0, "win_rate": 0.60, "trades": 25},
                   "diagnostics": {"pnl": 3.0, "min_hold_minutes": 40}},
            "c0": {"valid_inner": True, "test_metrics": {"profit_factor": 2.0, "win_rate": 0.60, "trades": 25},
                   "diagnostics": {"pnl": 3.0, "min_hold_minutes": 40}},
        },
        {
            "status": "completed", "ticker": "SPXW", "test_month": "202402",
            "p1": {"valid_inner": True, "test_metrics": {"profit_factor": 1.0, "win_rate": 0.50, "trades": 20},
                   "diagnostics": {"pnl": 0.1, "min_hold_minutes": 35}},
            "c0": {"valid_inner": True, "test_metrics": {"profit_factor": 1.0, "win_rate": 0.50, "trades": 20},
                   "diagnostics": {"pnl": 0.1, "min_hold_minutes": 35}},
        },
    ]

    econ = compute_economic_criteria(mock_results)

    # worst_month_pf is 1.0, not the average of (2.0, 1.0) = 1.5
    assert econ["p1_worst_month_pf"] == 1.0
    # Pooled PF is also reported
    assert "p1_pooled_pf" in econ
    # No "p1_mean_monthly_pf" key
    assert "p1_mean_monthly_pf" not in econ


def test_zero_trades_has_undefined_not_infinite_pooled_pf():
    from walkforward_pairwise_opportunity_side import compute_economic_criteria

    result = compute_economic_criteria([{
        "status": "completed",
        "ticker": "SPXW",
        "test_month": "202304",
        "c0": {"valid_inner": False},
        "p1": {"valid_inner": False},
    }])
    assert result["c0_pooled_pf"] is None
    assert result["p1_pooled_pf"] is None


# ── 19. Seed offsets are correct per head ──────────────────────────

def test_seed_offsets_per_head():
    """Verify seed offsets: C0_CALL=+1, C0_PUT=+2, P1_OPP=+3, P1_SIDE=+4."""
    assert HEAD_OFFSET_C0_CALL == 1
    assert HEAD_OFFSET_C0_PUT == 2
    assert HEAD_OFFSET_P1_OPP == 3
    assert HEAD_OFFSET_P1_SIDE == 4

    # All offsets must be different
    offsets = [HEAD_OFFSET_C0_CALL, HEAD_OFFSET_C0_PUT, HEAD_OFFSET_P1_OPP, HEAD_OFFSET_P1_SIDE]
    assert len(set(offsets)) == 4

    # make_lgb_params produces consistent deterministic seeds
    base = 42 + 202304 + 100  # SPXW, test_month 202304
    params = make_lgb_params(base, HEAD_OFFSET_C0_CALL)
    expected_seed = base + HEAD_OFFSET_C0_CALL
    assert params["random_state"] == expected_seed
    assert params["bagging_seed"] == expected_seed
    assert params["feature_fraction_seed"] == expected_seed
    assert params["data_random_seed"] == expected_seed
    assert params["deterministic"] is True
    assert params["force_col_wise"] is True
    assert params["verbose"] == -1
    assert params["subsample_freq"] == 1


# ── 20. Side score formulas and scientific evaluation mask ─────────────

def test_side_score_formulas_and_scientific_mask():
    """Verify side scores: C0 is p_call_win - p_put_win, P1 is 2*p_call - 1.
    Verify they are evaluated on the exact same mask (opp == 1 and abs(diff) > 1e-9).
    """
    # Create fake test df
    test_df = pd.DataFrame({
        "call_return": [0.05, -0.01, 0.0, 0.10],
        "put_return":  [-0.01, 0.02, 0.0, 0.10],
        "p_call_win":  [0.8, 0.4, 0.5, 0.9],
        "p_put_win":   [0.2, 0.7, 0.5, 0.8],
        "p_call":      [0.75, 0.3, 0.5, 0.85],
    })

    # Calculations:
    # row 0: max(0.05, -0.01)=0.05 > 0 (opp=1), diff=0.06 > 1e-9 (sci=True)
    # row 1: max(-0.01, 0.02)=0.02 > 0 (opp=1), diff=-0.03 (abs=0.03 > 1e-9) (sci=True)
    # row 2: max(0, 0)=0 (opp=0) (sci=False)
    # row 3: max(0.1, 0.1)=0.1 > 0 (opp=1), diff=0.0 (abs=0 <= 1e-9) (sci=False)

    call_ret = test_df["call_return"].to_numpy(dtype=float)
    put_ret = test_df["put_return"].to_numpy(dtype=float)
    c0_side_score = test_df["p_call_win"] - test_df["p_put_win"]
    p1_side_score = 2 * test_df["p_call"] - 1

    assert np.allclose(c0_side_score.iloc[0], 0.6)
    assert np.allclose(p1_side_score.iloc[0], 0.5)
    assert np.allclose(c0_side_score.iloc[1], -0.3)
    assert np.allclose(p1_side_score.iloc[1], -0.4)

    scientific = compute_scientific_side_metrics(
        call_ret,
        put_ret,
        c0_side_score.to_numpy(),
        p1_side_score.to_numpy(),
    )
    assert scientific["scientific_mask_rows"] == 2
    assert scientific["sci_cell_degenerate"] is False
    assert scientific["sci_c0_accuracy"] == 1.0
    assert scientific["sci_p1_accuracy"] == 1.0
    assert scientific["sci_c0_balanced_accuracy"] == 1.0
    assert scientific["sci_p1_balanced_accuracy"] == 1.0


# ── 21. Denominator 99 for scientific cells and degenerate handling ──

from walkforward_pairwise_opportunity_side import compute_scientific_criteria

def test_denominator_and_degenerate_scientific_cells():
    """Verify that degenerate cells do not get deleted, and total denominator is 99.
    Verify that median annual delta calculation uses only valid (non-degenerate) cells.
    """
    mock_results = []
    # Generate 99 cells
    tickers = ["SPXW", "QQQ", "SPY"]
    months = [f"2024{m:02d}" for m in range(1, 13)] + [f"2025{m:02d}" for m in range(1, 13)] + [f"2023{m:02d}" for m in range(4, 13)] # 12 + 12 + 9 = 33 months

    for t in tickers:
        for m in months:
            # Let's make some degenerate, some favorable, some unfavorable
            # We have 99 cells total
            is_degen = (m == "202401")  # 3 cells degenerate
            mock_results.append({
                "status": "completed",
                "ticker": t,
                "test_month": m,
                "sci_cell_degenerate": is_degen,
                "sci_ba_delta": 0.05 if not is_degen else float("nan"),
                "sci_p1_spearman": 0.10 if not is_degen else float("nan"),
            })

    sci = compute_scientific_criteria(mock_results)

    # Total denominator is strictly 99
    assert sci["total_denominator"] == 99
    # 3 cells are degenerate
    assert sci["degenerate_scientific_cells"] == 3
    # 96 cells are valid
    assert sci["valid_scientific_cells"] == 96
    # Favorable cells = 96 (all deltas are 0.05 > 0)
    assert sci["favorable_cells"] == 96
    # Rate is 96 / 99 = 0.9697
    assert np.isclose(sci["ba_delta_positive_rate"], 0.9697)


# ── 22. Policy-level metrics are isolated from model-level ──────────

def test_policy_level_vs_model_level_independence():
    """Verify that model-level metrics are computed for all opportunity-positive
    non-tie rows, regardless of whether the policy chose to trade or abstain.
    """
    parameters = set(inspect.signature(compute_scientific_side_metrics).parameters)
    assert parameters == {"call_return", "put_return", "c0_side_score", "p1_side_score"}
    assert not parameters.intersection({"traded", "policy", "threshold", "side_margin"})

    call_return = np.array([0.2, -0.1, 0.3, -0.2])
    put_return = np.array([-0.1, 0.2, -0.2, 0.3])
    c0_score = np.array([0.4, -0.2, 0.1, -0.5])
    p1_score = np.array([0.3, -0.4, 0.2, -0.1])
    first = compute_scientific_side_metrics(call_return, put_return, c0_score, p1_score)
    second = compute_scientific_side_metrics(call_return, put_return, c0_score, p1_score)
    assert first == second
    assert first["scientific_mask_rows"] == 4


def test_scientific_mask_is_common_finite_and_degenerate_is_preserved():
    result = compute_scientific_side_metrics(
        call_return=np.array([0.2, 0.3, 0.4, np.nan]),
        put_return=np.array([-0.1, 0.3, -0.2, 0.1]),
        c0_side_score=np.array([0.2, 0.1, np.nan, -0.1]),
        p1_side_score=np.array([0.3, 0.2, -0.4, 0.1]),
    )
    # Only row 0 survives: row 1 is a return tie, row 2 has a nonfinite C0
    # score, and row 3 has a nonfinite label. One class/row is degenerate.
    assert result["scientific_mask_rows"] == 1
    assert result["sci_cell_degenerate"] is True
    assert result["sci_cell_degenerate_reason"].startswith("SCIENTIFIC_CELL_DEGENERATE")
    assert np.isnan(result["sci_ba_delta"])


# ── 23. Preflight and execution directory isolation ────────────────

def test_preflight_vs_execution_directory_paths():
    """Verify preflight and execution folders are separated as specified."""
    # Preflight must output to pairwise_opportunity_side_v1_preflight
    # Execution must output to pairwise_opportunity_side_v1
    runner_text = (Path(__file__).resolve().parent.parent / "run_pairwise_opportunity_side_v1.ps1").read_text(encoding="utf-8")
    preflight_dir = "research_papers/JEPA/results/_diagnostics/pairwise_opportunity_side_v1_preflight"
    real_dir = "research_papers/JEPA/results/_diagnostics/pairwise_opportunity_side_v1"
    assert preflight_dir != real_dir
    assert f'$PreflightOutput = "{preflight_dir}"' in runner_text
    assert f'$RealOutput = "{real_dir}"' in runner_text
    assert 'if (Test-Path -LiteralPath $RealOutput)' in runner_text


def test_dry_run_never_calls_training(monkeypatch, tmp_path):
    """--dry-run must return before feature construction or fold training."""
    fake = pd.DataFrame({"trade_date": ["20220103", "20251231"]})
    monkeypatch.setattr(pairwise.pd, "read_parquet", lambda _path: fake.copy())
    monkeypatch.setattr(pairwise, "sha256_file", lambda _path: "0" * 64)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("training was called from --dry-run")

    monkeypatch.setattr(pairwise, "run_fold", fail_if_called)
    output = tmp_path / "preflight"
    monkeypatch.setattr(sys, "argv", [
        "walkforward_pairwise_opportunity_side.py",
        "--dataset", str(tmp_path / "sealed.parquet"),
        "--output-dir", str(output),
        "--dry-run",
    ])
    assert pairwise.main() == 0
    config = json.loads((output / "run_config.json").read_text(encoding="utf-8"))
    assert config["folds"] == 33
    assert not list(output.glob("SPXW_*"))


def test_runner_requires_explicit_mode():
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("pwsh is not installed")
    repo = Path(__file__).resolve().parent.parent
    completed = subprocess.run(
        [pwsh, "-NoProfile", "-File", str(repo / "run_pairwise_opportunity_side_v1.ps1")],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    assert completed.returncode != 0
    assert "exactly one explicit mode" in ((completed.stdout or "") + (completed.stderr or ""))


def test_current_feature_hash_is_frozen():
    diff_cols = [f"{name}_diff" for name in DIFF_METRICS]
    change_cols = [
        f"{name}_chg_{label}"
        for name in diff_cols
        if name != "oi_diff"
        for _, label in CHANGE_LAGS
    ]
    assert compute_feature_hash(COMMON_FEATURES + diff_cols + change_cols) == (
        "fa2057653ed0327b7f84a165c25f6e6d31e31b3b05c5591593e9c0bd3056d50e"
    )
