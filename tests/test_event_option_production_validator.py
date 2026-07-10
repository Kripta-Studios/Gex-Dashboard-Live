from __future__ import annotations

import hashlib

import pandas as pd

from neural.jepa.validate_event_option_production_package import (
    assert_policy_selection_causality,
    assert_trade_artifact_live_equivalence,
    recompute_trade_metrics,
)


def test_fixed_policy_selection_rejects_reported_month_reuse() -> None:
    policy = {
        "policy_selection_provenance": {
            "passed": True,
            "mode": "fixed_pre_oos",
            "evaluation_months": ["202601"],
            "training_months": ["202501"],
            "selection_months": ["202601"],
            "policy_frozen_before_evaluation": True,
        }
    }
    registry = {
        "available_components": {
            "SPY.policy": {"select_months": ["202601"]},
        }
    }
    issues: list[str] = []

    assert_policy_selection_causality(policy, registry, ["202601"], issues)

    assert any("uses reported OOS months" in issue for issue in issues)
    assert any("SPY.policy" in issue and "overlap" in issue for issue in issues)


def test_nested_walk_forward_accepts_strictly_prior_fold_sources() -> None:
    digest = hashlib.sha256(b"frozen fold policy").hexdigest()
    policy = {
        "policy_selection_provenance": {
            "passed": True,
            "mode": "nested_walk_forward",
            "evaluation_months": ["202601", "202602"],
            "selection_protocol_frozen_before_evaluation": True,
            "trade_artifact_kind": "nested_walk_forward_fold_outputs",
            "folds": [
                {
                    "evaluation_month": "202601",
                    "training_months": ["202501", "202502"],
                    "selection_months": ["202512"],
                    "policy_frozen_before_evaluation": True,
                    "policy_artifact_sha256": digest,
                },
                {
                    "evaluation_month": "202602",
                    "training_months": ["202501", "202512"],
                    "selection_months": ["202601"],
                    "policy_frozen_before_evaluation": True,
                    "policy_artifact_sha256": digest,
                },
            ],
        }
    }
    issues: list[str] = []

    assert_policy_selection_causality(policy, {"available_components": {}}, ["202601", "202602"], issues)

    assert issues == []


def test_recomputed_min_month_count_includes_missing_months() -> None:
    trades = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY"],
            "month": ["202601", "202601"],
            "realized_return": [1.0, -0.25],
        }
    )

    metrics = recompute_trade_metrics(trades, validation_months=["202601", "202602"])["SPY"]

    assert metrics["trades"] == 2.0
    assert metrics["profit_factor"] == 4.0
    assert metrics["min_month_trades"] == 0.0
    assert metrics["positive_month_rate"] == 0.5


def test_trade_artifact_audit_detects_off_grid_and_overlapping_entry() -> None:
    trades = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY"],
            "trade_date": ["20260102", "20260102"],
            "month": ["202601", "202601"],
            "minute": [630, 631],
            "exit_minutes": [30, 30],
            "realized_return": [1.0, 1.0],
        }
    )
    metrics = recompute_trade_metrics(trades, validation_months=["202601"])["SPY"]
    policy = {
        "live_contract": {
            "entry_sample_minutes": 5,
            "candidate_universe_filter": {
                "entry_sample_minutes": 5,
                "entry_sample_anchor_minute_et": "10:00",
            },
        }
    }
    validation = {"by_ticker": {"SPY": metrics}}
    issues: list[str] = []

    assert_trade_artifact_live_equivalence(
        policy,
        validation,
        trades,
        ["202601"],
        ["SPY"],
        0.50,
        1.30,
        0,
        issues,
    )

    assert any("off the live 5-minute grid" in issue for issue in issues)
    assert any("overlapping same-ticker" in issue for issue in issues)
