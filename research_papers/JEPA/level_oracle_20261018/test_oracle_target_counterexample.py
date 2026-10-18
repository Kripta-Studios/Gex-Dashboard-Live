from oracle_target_counterexample import counterexample


def test_privileged_continuation_penalizes_causally_profitable_entry():
    result = counterexample()
    assert result["causal_wait_value"] == 0
    assert result["oracle_expected_wait_value"] == 1.5
    assert result["oracle_advantage_conditional_mean"] == -0.5
    assert result["causal_advantage"] == 1
    assert result["oracle_advantage_learner_expected_net"] == 0
    assert result["causal_advantage_learner_expected_net"] == 1
    assert result["oracle_expected_total_net"] == 2
