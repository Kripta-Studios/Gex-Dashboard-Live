import pandas as pd
import pytest

from diagnose_oracle_quote_anomalies_panel import control_attempts


def test_control_attempts_preserve_filled_and_no_fill_choices():
    states = pd.DataFrame({"state_i": [60, 61, 62], "model_action_id": [4, 5, -1],
                           "model_free": [True, True, False],
                           "model_filled": [True, False, False]})
    actions = pd.DataFrame({"action_id": [4, 5], "state_i": [60, 61],
                            "entry_i": [61, 62], "contract_i": [2, 3]})
    labels = pd.DataFrame({"action_id": [4, 5], "status": ["FILLED", "NO_FILL"],
                           "exit_i": [70, 62]})
    result = control_attempts(states, actions, labels)
    assert result.action_id.tolist() == [4, 5]
    assert result.status.tolist() == ["FILLED", "NO_FILL"]


def test_control_attempt_fill_mismatch_fails_closed():
    states = pd.DataFrame({"state_i": [60], "model_action_id": [4],
                           "model_free": [True], "model_filled": [False]})
    actions = pd.DataFrame({"action_id": [4], "state_i": [60],
                            "entry_i": [61], "contract_i": [2]})
    labels = pd.DataFrame({"action_id": [4], "status": ["FILLED"], "exit_i": [70]})
    with pytest.raises(AssertionError, match="fill status"):
        control_attempts(states, actions, labels)
