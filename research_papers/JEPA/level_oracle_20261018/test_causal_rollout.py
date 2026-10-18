import numpy as np
import pytest

from causal_rollout import ActionRows, OutcomeRows, fixed_policy_values
from causal_rollout import freeze_choices, residual_targets, validate_engine_outcomes


def rows(ids, times, statuses, exits, net):
    actions = ActionRows(np.array(ids, dtype=np.int64), np.array(times, dtype=np.int64))
    outcomes = OutcomeRows(actions.action_id.copy(), np.array(statuses),
                           np.array(exits, dtype=np.int64), np.array(net, dtype=float))
    return actions, outcomes


def test_fixed_losing_continuation_is_never_replaced_by_clairvoyant_winner():
    actions, outcomes = rows([2, 1, 3], [60, 60, 63], ["FILLED"] * 3,
                             [62, 62, 64], [1000, -10, -20])
    choices = freeze_choices(actions, [[1, 1], [2, 2], [3, 3]], last=64)
    assert choices[0].tolist() == [1, 1]
    value = fixed_policy_values(actions, outcomes, choices, 50, last=64)
    assert value[0].tolist() == [-30, -30]
    # Choosing an offered but unselected action is a counterfactual label only.
    target = residual_targets(actions, outcomes, value, last=64)
    assert target[0].tolist() == [1000, 1000]
    assert target[1].tolist() == [-10, -10]


def test_wait_policy_penalty_and_first_fill_are_not_economic_pnl():
    actions, outcomes = rows([0, 1], [60, 61], ["FILLED", "NO_FILL"], [64, -1], [-5, 0])
    choices = freeze_choices(actions, np.zeros((2, 2)), last=64)
    value = fixed_policy_values(actions, outcomes, choices, 20, last=64)
    target = residual_targets(actions, outcomes, value, last=64)
    assert value[0].tolist() == [-20, 0]
    assert target.tolist() == [[15, -5], [0, 0]]
    assert outcomes.net_base.tolist() == [-5, 0]
    # With no penalty, a WAIT policy gives the immediate economic reward.
    unpenalized = fixed_policy_values(actions, outcomes, choices, 0, last=64)
    assert residual_targets(actions, outcomes, unpenalized, last=64).tolist() == [[-5, -5], [0, 0]]


def test_nofill_preserves_flag_and_never_rescues_another_same_minute_action():
    actions, outcomes = rows([0, 1, 2], [60, 60, 61],
                             ["NO_FILL", "FILLED", "FILLED"], [-1, 63, 63], [0, 500, 0])
    choices = freeze_choices(actions, [[2, 2], [1, 1], [1, 1]], last=64)
    value = fixed_policy_values(actions, outcomes, choices, 10, last=64)
    assert value[0].tolist() == [0, 0]  # Zero-return fill still satisfies daily fill.
    assert residual_targets(actions, outcomes, value, last=64)[0].tolist() == [0, 0]


def test_occupation_cost_and_terminal_clamping():
    actions, outcomes = rows([0, 1], [60, 62], ["FILLED"] * 2, [80, 64], [20, 30])
    choices = freeze_choices(actions, [[-1, -1], [1, 1]], last=64)
    value = fixed_policy_values(actions, outcomes, choices, 10, last=64)
    assert residual_targets(actions, outcomes, value, last=64)[0].tolist() == [-10, -10]


def test_choices_ignore_outcomes_and_future_score_changes_do_not_change_prefix():
    actions, outcomes = rows([0, 1, 2], [60, 60, 63], ["FILLED"] * 3, [62, 62, 64], [1, 2, 3])
    scores = np.array([[0., 1.], [0., 1.], [2., 2.]])
    choices = freeze_choices(actions, scores, last=64)
    assert choices[0].tolist() == [-1, 0]  # WAIT wins equality; smallest ID wins positive tie.
    changed_scores = scores.copy()
    changed_scores[2] = -100
    assert np.array_equal(choices[:3], freeze_choices(actions, changed_scores, last=64)[:3])
    changed = OutcomeRows(outcomes.action_id, outcomes.status, outcomes.exit_i, outcomes.net_base * -1000)
    assert not np.array_equal(fixed_policy_values(actions, outcomes, choices, 10, last=64),
                              fixed_policy_values(actions, changed, choices, 10, last=64))
    assert np.array_equal(choices, freeze_choices(actions, scores, last=64))
    with pytest.raises(ValueError):
        choices[0, 0] = 1


def test_backward_values_equal_independent_forward_replay_for_every_start_and_flag():
    actions, outcomes = rows([0, 1, 2, 3], [60, 61, 63, 64],
                             ["NO_FILL", "FILLED", "FILLED", "FILLED"], [-1, 62, 64, 65], [0, -7, 13, 4])
    scores = np.array([[2., -1.], [3., 3.], [2., -1.], [4., 4.]])
    choices = freeze_choices(actions, scores, last=65)
    value = fixed_policy_values(actions, outcomes, choices, 11, last=65)
    for start in range(60, 67):
        for flag in (0, 1):
            minute, h, total = start, flag, 0.
            while minute <= 65:
                key = choices[minute - 60, h]
                if key < 0 or outcomes.status[key] == "NO_FILL":
                    minute += 1
                else:
                    total += outcomes.net_base[key]
                    h = 1
                    minute = outcomes.exit_i[key] + 1
            total -= 11 * (h == 0)
            assert value[min(start - 60, 6), flag] == total


def test_identity_join_and_invalid_transitions_fail_closed():
    actions, outcomes = rows([10, 20], [60, 61], ["FILLED", "NO_FILL"], [63, -1], [5, 0])
    choices = freeze_choices(actions, [[1, 1], [1, 1]], last=64)
    reversed_outcomes = OutcomeRows(*(getattr(outcomes, field)[::-1] for field in
                                     ("action_id", "status", "exit_i", "net_base")))
    assert np.array_equal(fixed_policy_values(actions, outcomes, choices, 10, last=64),
                          fixed_policy_values(actions, reversed_outcomes, choices, 10, last=64))
    bad = OutcomeRows(outcomes.action_id, outcomes.status, np.array([60, -1]), outcomes.net_base)
    with pytest.raises(ValueError, match="advance"):
        fixed_policy_values(actions, bad, choices, 10, last=64)
    with pytest.raises(ValueError, match="finite causal"):
        freeze_choices(actions, [[np.nan, 1], [1, 1]], last=64)


def test_common_teacher_flag_difference_is_only_terminal_no_fill_penalty():
    actions, outcomes = rows([0, 1], [60, 62], ["FILLED", "FILLED"], [61, 64], [3, -4])
    choices = freeze_choices(actions, [[-1, -1], [1, 1]], last=64)
    value = fixed_policy_values(actions, outcomes, choices, 17, last=64)
    assert (value[:, 1] - value[:, 0]).tolist() == [0, 0, 0, 17, 17, 17]
    target = residual_targets(actions, outcomes, value, last=64)
    assert (target[:, 0] - target[:, 1]).tolist() == [0, 17]


def test_empty_day_preserves_terminal_penalty_and_has_no_trade_targets():
    actions, outcomes = rows([], [], [], [], [])
    choices = freeze_choices(actions, np.empty((0, 2)), last=64)
    value = fixed_policy_values(actions, outcomes, choices, 9, last=64)
    assert np.all(value == np.array([-9, 0]))
    assert residual_targets(actions, outcomes, value, last=64).shape == (0, 2)


def test_market_adapter_enforces_actual_engine_latency_and_close():
    actions, outcomes = rows([0, 1, 2], [60, 374, 375],
                             ["FILLED", "NO_FILL", "FILLED"], [62, 375, 385], [5, 0, -3])
    validate_engine_outcomes(actions, outcomes)
    for exits in ([61, 375, 385], [62, 375, 386], [62, 376, 385]):
        invalid = OutcomeRows(outcomes.action_id, outcomes.status, np.array(exits), outcomes.net_base)
        with pytest.raises(ValueError):
            validate_engine_outcomes(actions, invalid)
