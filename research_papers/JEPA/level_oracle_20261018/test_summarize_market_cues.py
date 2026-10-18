import copy

import pytest

import summarize_market_cues as s


def fixture():
    rows = []
    for action_id, state, value in ((0, 60, 0), (1, 60, 0), (2, 61, 10)):
        rows.append(dict(action_id=action_id, state_i=state, ticker="SPY", date="20250102",
                         decision_nyse="2025-01-02T10:30:00-05:00", outcomes_read=False,
                         metrics={name: dict(value=value, valid=True, missing_reason=None)
                                  for name in (*s.METRICS, "is_put")}, evidence_tags=[]))
    overlay = dict(model_policy="gbt_net__0", rows=[dict(action_id=i, oracle_selected=i == 0, model_selected=i == 2) for i in range(3)])
    return rows, overlay


def test_states_receive_equal_weight_and_missing_is_not_zero():
    rows, overlay = fixture()
    result = s.summarize(rows, overlay)
    metric = result["groups"]["all_candidates"]["metrics"]["delta"]
    assert metric["positive_state_weight_fraction_among_valid"] == 0.5
    assert result["groups"]["oracle_selected"]["actions"] == 1
    rows[2]["metrics"]["delta"] = dict(value=None, valid=False, missing_reason="MISSING")
    result = s.summarize(rows, overlay)
    metric = result["groups"]["all_candidates"]["metrics"]["delta"]
    assert metric["valid_state_weight_fraction"] == 0.5
    assert metric["missing_actions"] == 1
    assert result["groups"]["model_selected"]["metrics"]["delta"]["weighted_median"] is None


def test_membership_is_exact_and_nonfinite_valid_values_rejected():
    rows, overlay = fixture()
    bad = copy.deepcopy(overlay)
    bad["rows"].pop()
    with pytest.raises(ValueError, match="Exact"):
        s.summarize(rows, bad)
    rows[0]["metrics"]["delta"]["value"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        s.summarize(rows, overlay)


def test_empty_selected_group_is_retained_without_pseudo_statistics():
    rows, overlay = fixture()
    for member in overlay["rows"]:
        member["oracle_selected"] = False
    result = s.summarize(rows, overlay)
    oracle = result["groups"]["oracle_selected"]
    assert oracle["actions"] == oracle["states"] == 0
    assert all(metric["weighted_median"] is None for metric in oracle["metrics"].values())
