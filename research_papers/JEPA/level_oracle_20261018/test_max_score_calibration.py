import numpy as np
import pandas as pd
import pytest

from diagnose_max_score_calibration import aggregate, aligned, cohorts, moments, paired


def fixture():
    actions = pd.DataFrame(dict(action_id=[9, 2, 3, 4], state_i=[60, 60, 61, 61]))
    labels = pd.DataFrame(dict(action_id=[4, 3, 2, 9], status=["FILLED", "FILLED", "NO_FILL", "FILLED"], net_base=[-5., 7., 999., 1.]))
    frame = aligned(actions, labels, actions.action_id.to_numpy(), np.array([3., 3., -2., -3.]))
    states = pd.DataFrame(dict(state_i=[60, 61], model_free=[True, True], model_filled=[False, True],
                              model_action_id=[2, 3], model_score=[3., -2.], model_net=[0., 7.]))
    return actions, labels, frame, states


def test_argmax_before_threshold_tie_no_fill_and_exact_execution():
    _, _, frame, states = fixture()
    choices = cohorts(frame, states)
    assert choices["argmax_before_threshold"].action_id.tolist() == [2, 3]
    assert choices["argmax_before_threshold"].real.tolist() == [0., 7.]
    assert choices["executed_trades"].action_id.tolist() == [3]
    assert len(choices["all_actions"]) == 4
    assert frame.loc[frame.action_id == 2, "real"].iloc[0] == 0


def test_wrong_ids_duplicate_and_wrong_state_fail():
    actions, labels, frame, states = fixture()
    with pytest.raises(ValueError, match="aligned"):
        aligned(actions, labels, actions.action_id.to_numpy()[::-1], np.arange(4.))
    with pytest.raises(ValueError, match="Duplicate"):
        aligned(pd.concat([actions, actions.iloc[:1]]), labels, np.array([9, 2, 3, 4, 9]), np.arange(5.))
    with pytest.raises(ValueError, match="state alignment"):
        cohorts(frame, states.assign(state_i=[60, 65]))
    with pytest.raises(ValueError, match="score/payoff"):
        cohorts(frame, states.assign(model_score=[3., 99.]))


def day(date, pred, real, cohort="all_actions"):
    frame = pd.DataFrame(dict(pred=pred, real=real, status=["FILLED"] * len(pred)))
    return dict(split="validation", ticker="SPY", model="gbt_net", cohort=cohort, date=date, **moments(frame))


def test_equal_day_weight_not_pooled_action_count_and_weighted_correlation():
    daily = pd.DataFrame([day("a", [0.], [0.]), day("b", [10.] * 9, [20.] * 9)])
    result = aggregate(daily).iloc[0]
    assert result.predicted_mean_usd == 5
    assert result.realized_mean_usd == 10
    assert result.mean_error_usd == -5
    assert result.correlation == pytest.approx(1)
    assert result.rmse_usd == pytest.approx(np.sqrt(50))
    empty = pd.DataFrame([day("c", [], [])])
    result = aggregate(pd.concat([daily, empty])).iloc[0]
    assert (result.expected_days, result.nonempty_days, result.empty_days) == (3, 2, 1)
    assert result.predicted_mean_usd == 5


def test_paired_contrast_common_days_only():
    daily = pd.DataFrame([
        day("a", [1., 3.], [2., 0.]), day("b", [10.], [0.]),
        day("a", [3.], [0.], "argmax_before_threshold"),
        day("b", [10.], [0.], "argmax_before_threshold"),
        day("a", [3.], [0.], "executed_trades"),
        day("b", [], [], "executed_trades"),
    ])
    result = paired(daily)
    first = result.iloc[0]
    assert first.paired_days == 2
    assert first.pred_difference == .5
    assert first.real_difference == -.5
    assert first.error_difference == 1
    assert result.iloc[1].paired_days == 1
