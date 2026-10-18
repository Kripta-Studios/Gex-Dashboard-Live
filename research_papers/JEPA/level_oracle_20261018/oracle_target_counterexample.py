"""Exact finite example: privileged oracle advantage can discourage profit.

Synthetic reasoning check only, with two equiprobable exogenous outcomes.
Neither decision observes which outcome will occur. No market data or fit.
"""


def counterexample():
    # At t0: take +1 and occupy the remaining session, or WAIT to t1.
    # At t1: one candidate returns +3 or -3 with probability 1/2 each.
    # Both branches have identical causal inputs at both decision times.
    # Thus any causal t1 trade has expectation zero. WAIT ties win.
    branches = [(0.5, 3.0), (0.5, -3.0)]
    immediate_net = 1.0
    causal_future_trade_mean = sum(prob * payoff for prob, payoff in branches)
    causal_wait_value = max(0.0, causal_future_trade_mean)
    oracle_wait_expected = sum(prob * max(0.0, payoff) for prob, payoff in branches)
    oracle_advantage_target_mean = immediate_net - oracle_wait_expected
    causal_advantage = immediate_net - causal_wait_value
    # A squared-error learner with indistinguishable causal inputs learns the
    # conditional mean label. Thresholding the oracle label chooses WAIT.
    oracle_label_policy_net = causal_wait_value if oracle_advantage_target_mean <= 0 else immediate_net
    causal_label_policy_net = immediate_net if causal_advantage > 0 else causal_wait_value
    return dict(
        causal_t1_expected_trade_net=causal_future_trade_mean,
        causal_wait_value=causal_wait_value,
        oracle_expected_wait_value=oracle_wait_expected,
        oracle_advantage_conditional_mean=oracle_advantage_target_mean,
        causal_advantage=causal_advantage,
        oracle_advantage_learner_expected_net=oracle_label_policy_net,
        causal_advantage_learner_expected_net=causal_label_policy_net,
        oracle_expected_total_net=sum(prob * max(immediate_net, payoff) for prob, payoff in branches),
    )


if __name__ == "__main__":
    import json
    print(json.dumps(counterexample(), indent=2))
