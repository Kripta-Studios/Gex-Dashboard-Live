"""Outcome-free fixtures for the independent episode learner auditor."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd

SPEC = importlib.util.spec_from_file_location(
    "audit_episode_learner_fixture",
    Path(__file__).with_name("audit_episode_learner_economics.py"),
)
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def action_frames():
    actions = pd.DataFrame(
        {"action_id": [10, 11, 20, 30, 40], "state_i": [60, 60, 61, 62, 66]}
    )
    labels = pd.DataFrame(
        {
            "action_id": [10, 11, 20, 30, 40],
            "status": ["NO_FILL", "FILLED", "FILLED", "FILLED", "FILLED"],
            "exit_i": [61, 65, 64, 63, 68],
            "net_base": [0.0, 20.0, 5.0, -2.0, 7.0],
            "net_adverse": [0.0, 18.0, 3.0, -4.0, 5.0],
        }
    )
    return actions, labels


def test_scheduler_free_timing_tie_threshold_nofill_and_overlap():
    actions, labels = action_frames()
    scores = np.array([12.0, 12.0, 11.0, 10.0, 9.0])
    ranked = audit.rank_by_state(actions, scores)
    assert actions.iloc[ranked].action_id.tolist() == [10, 20, 30, 40]
    attempts, ledger = audit.schedule(actions, labels, scores, 10.0, ranked)
    assert attempts.action_id.tolist() == [10, 20]
    assert ledger.action_id.tolist() == [20]
    attempts, ledger = audit.schedule(actions, labels, scores, 5.0, ranked)
    assert attempts.action_id.tolist() == [10, 20, 40]
    assert ledger.action_id.tolist() == [20, 40]


def validation(viable, scores=None):
    scores = scores or [0.0] * 6
    result = {}
    for number, ident in enumerate(audit.policies()):
        result[ident] = {
            "tickers": {
                ticker: {"base_net_usd": scores[number]} for ticker in audit.TICKERS
            },
            "daily_compliance": {"viable": viable[number]},
        }
    return result


def test_selection_uses_only_daily_viable_and_stable_order():
    selected = audit.select_policy(
        validation([False, True, True, True, False, False], [100, -3, -3, -3, 200, 300]),
        {ticker: 1 for ticker in audit.TICKERS},
    )
    assert selected["selected_policy"]["policy"] == "gbt_net__5"
    assert selected["diagnostic_policy"]["policy"] == "gbt_net_episode__10"
    assert selected["approved"] is False


def test_no_viable_policy_is_failure_with_null_selection_and_frozen_diagnostic():
    selected = audit.select_policy(
        validation([False] * 6), {ticker: 1 for ticker in audit.TICKERS}
    )
    assert selected["selection_status"] == "FAIL_NO_DAILY_COMPLIANT_POLICY"
    assert selected["selected_policy"] is None
    assert selected["diagnostic_policy"]["policy"] == "gbt_net__0"
    assert all(choice["policy"] != "CASH" for choice in selected["choices"])


def test_daily_compliance_separates_zero_fill_from_no_evaluable():
    ledger = pd.DataFrame({"date": ["20260102"], "ticker": ["SPXW"]})
    table, result = audit.daily_compliance(
        ledger,
        ["20260102"],
        {("SPXW", "20260102"), ("SPY", "20260102")},
    )
    assert result["days_without_fill"] == 1
    assert result["no_evaluable_ticker_days"] == 1
    assert result["minimum_daily_pass"] is False and result["coverage_pass"] is False
    qqq = table.loc[table.ticker == "QQQ"].iloc[0]
    assert qqq.source_status == "NO_EVALUABLE" and qqq.meets_minimum is None


def test_metrics_and_prediction_errors_are_independent_float_reductions():
    frame = pd.DataFrame(
        {
            "net_base": [5.0, -8.0, 4.0],
            "net_adverse": [3.0, -10.0, 2.0],
            "reason": ["TARGET", "STOP", "EOD"],
            "hold_minutes": [3, 7, 5],
        }
    )
    metrics = audit.economic_metrics(frame)
    assert metrics["base_net_usd"] == 1.0
    assert metrics["base_max_drawdown_usd"] == 8.0
    report = audit.error_report(audit.error_moments([2.0, 4.0], [1.0, 5.0]))
    assert report["rows"] == 2 and report["bias_usd"] == 0.0


def test_gate_cannot_pass_without_all_three_tickers():
    metrics = {
        "base_net_usd": 100.0,
        "adverse_net_usd": 90.0,
        "base_pf": 2.0,
        "base_pf_infinite": False,
        "trades": 100,
    }
    period = {
        "candidate": {
            "tickers": {ticker: dict(metrics) for ticker in audit.TICKERS},
            "months": {
                ticker: {
                    month: {"base_net_usd": 1.0}
                    for month in ("202601", "202602", "202603")
                }
                for ticker in audit.TICKERS
            },
        }
    }
    assert audit.economic_gate({"policy": "candidate"}, period)["passes"]
    period["candidate"]["tickers"]["QQQ"]["adverse_net_usd"] = -1.0
    assert not audit.economic_gate({"policy": "candidate"}, period)["passes"]
