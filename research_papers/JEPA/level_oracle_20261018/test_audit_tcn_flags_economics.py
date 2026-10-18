"""Pre-result fixtures for the independent TCN flags economic auditor."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd

SPEC = importlib.util.spec_from_file_location(
    "audit_tcn_flags_fixture", Path(__file__).with_name("audit_tcn_flags_economics.py")
)
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def test_scheduler_tie_strict_threshold_nofill_and_no_replacement():
    actions = pd.DataFrame(
        {"action_id": [4, 2, 7, 8], "state_i": [60, 60, 61, 62]}
    )
    labels = pd.DataFrame(
        {
            "action_id": [4, 2, 7, 8],
            "status": ["FILLED", "NO_FILL", "FILLED", "FILLED"],
            "exit_i": [64, 61, 63, 65],
            "net_base": [9.0, 0.0, 3.0, 2.0],
            "net_adverse": [7.0, 0.0, 1.0, 0.0],
        }
    )
    scores = np.array([5.0, 5.0, 6.0, 5.0])
    ranked = audit.rank_by_state(actions, scores)
    assert actions.iloc[ranked].action_id.tolist() == [2, 7, 8]
    attempts, ledger = audit.schedule(actions, labels, scores, 5.0, ranked)
    assert attempts.action_id.tolist() == [7]
    assert ledger.action_id.tolist() == [7]


def summary_fixture(passes, scores):
    return {
        ident: {
            "daily_gate": {"passes": passes[number]},
            "tickers": {
                ticker: {"base_net_usd": scores[number]} for ticker in audit.TICKERS
            },
        }
        for number, ident in enumerate(audit.policies())
    }


def test_validation_selection_hard_daily_gate_and_stable_ties():
    selection = audit.select_validation(
        summary_fixture([False, True, True, True, False, False], [99, 1, 1, 1, 200, 300]),
        {ticker: 1 for ticker in audit.TICKERS},
    )
    assert selection["selected_policy"] == "control__5"
    assert selection["diagnostic_best_not_approved"] is None
    assert selection["best_per_arm_2025"]["variant"] == "variant__10"


def test_no_viable_policy_freezes_diagnostic_without_approval():
    selection = audit.select_validation(
        summary_fixture([False] * 6, [0] * 6),
        {ticker: 1 for ticker in audit.TICKERS},
    )
    assert selection["selected_policy"] is None
    assert selection["diagnostic_best_not_approved"] == "control__0"
    assert selection["eligible"] == []


def test_daily_gate_distinguishes_zero_fill_and_no_evaluable():
    ledger = pd.DataFrame({"ticker": ["SPXW"], "date": ["20260102"]})
    gate, frame = audit.daily_gate(
        ledger,
        ["20260102"],
        {("SPXW", "20260102"), ("SPY", "20260102")},
    )
    assert gate["observable_days_with_trade"] == 1
    assert gate["no_evaluable_days"] == 1 and not gate["passes"]
    assert frame.loc[frame.ticker == "QQQ", "status"].iloc[0] == "NO_EVALUABLE"


def test_metrics_use_realized_order_and_both_costs():
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
    assert metrics["adverse_net_usd"] == -5.0


def test_economic_gate_requires_every_ticker():
    metrics = {
        "base_net_usd": 10.0,
        "adverse_net_usd": 5.0,
        "base_pf": 2.0,
        "base_pf_infinite": False,
        "trades": 60,
    }
    test = {
        "chosen": {
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
    assert audit.economic_gate("chosen", test)["passes"]
    test["chosen"]["tickers"]["QQQ"]["adverse_net_usd"] = -1
    assert not audit.economic_gate("chosen", test)["passes"]
