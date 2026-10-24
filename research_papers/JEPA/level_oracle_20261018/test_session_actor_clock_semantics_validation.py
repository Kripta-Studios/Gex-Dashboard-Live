"""Artificial graph checks only; no real data, models or prior laboratory imports."""
from copy import deepcopy
from dataclasses import replace

import pytest

import session_actor_clock_semantics_validation as lab


@pytest.fixture(scope="module", autouse=True)
def resource_gate():
    lab.resource_gate()


def deterministic(graph, choose_offer=False):
    return {s: {a: float(a == (lab.names(graph, s[0])[-1] if choose_offer else "WAIT"))
        for a in lab.names(graph, s[0])} for s in lab.states(graph)}


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("shared", [False, True])
def test_predeclared_values_occupancies_gradients_three_steps(index, shared):
    result = lab.checks(lab.graphs()[index], shared)
    assert all(c["passed"] for c in result["checks"]), result
    assert [c["check"] for c in result["checks"] if c["check"].startswith("central")] == [
        "central difference 0.0001", "central difference 1e-05", "central difference 1e-06"]


def test_retry_counterexample_detects_wrong_exit_plus_one():
    value = lab.counterexample()
    assert all(c["passed"] for c in value["checks"])
    assert value["correct"] == dict(pnl=7.0, attempts=2.0, fills=1.0, objective=7.0)
    assert value["wrong"] == dict(pnl=0, attempts=1, fills=0, objective=-3)


@pytest.mark.parametrize("index,slots,end", [(3, 316, 375), (4, 136, 195)])
def test_full_and_short_clock_keep_every_invalid_slot_and_masks(index, slots, end):
    graph = lab.graphs()[index]
    before = deepcopy(graph)
    direct = lab.enumerate_paths(graph, deterministic(graph))
    assert graph == before and len(graph.slots) == slots
    assert set(direct["visits"]) == {(t, h) for t in range(60, end+1) for h in (0, 1)}
    assert all(direct["visits"][(t, 0)] == 1 for t in range(60, end+1))
    assert all(direct["visits"][(t, 1)] == 0 for t in range(60, end+1))
    assert all(lab.names(graph, s.t) == ("WAIT",) for s in graph.slots if not s.state_valid)
    assert graph.slots[0].token_mask == (True, False, True, False)
    assert direct["pnl"] == 0 and direct["objective"] == -3


@pytest.mark.parametrize("index", [3, 4])
def test_last_decision_fill_liquidates_after_decision_horizon(index):
    graph = lab.graphs()[index]
    probs = deterministic(graph)
    t = graph.slots[-1].t
    for h in (0, 1):
        probs[(t, h)] = {"WAIT": 0.0, graph.offers[t][0].name: 1.0}
    result = lab.enumerate_paths(graph, probs)
    assert result["terminals"][(graph.last_liquidation+1, 1)] == 1.0
    assert result["pnl"] == 1 and result["fills"] == 1 and result["attempts"] == 1


def test_attempts_not_fills_and_no_fill_does_not_set_history_flag():
    graph = lab.graphs()[1]
    result = lab.enumerate_paths(graph, deterministic(graph, True))
    assert result["attempts"] == 2 and result["fills"] == 0 and result["no_fill"] == 1
    assert result["visits"][(1, 0)] == 1 and result["visits"][(1, 1)] == 0
    assert result["objective"] == -3 and result["pnl"] == 0


def test_filled_blocks_through_exit_and_changes_h():
    graph = lab.graphs()[2]
    probs = deterministic(graph)
    probs[(1, 0)] = {"WAIT": 0.0, "offer_1": 1.0, "offer_2": 0.0}
    result = lab.enumerate_paths(graph, probs)
    assert result["visits"][(2, 0)] == result["visits"][(2, 1)] == 0
    assert result["visits"][(3, 0)] == result["visits"][(3, 1)] == 0
    assert result["visits"][(4, 1)] == 1


def test_enumeration_is_independent_of_dp_transition_and_occupancy(monkeypatch):
    graph = lab.graphs()[-1]
    probabilities = deterministic(graph, True)
    def forbidden(*args, **kwargs):
        pytest.fail("Enumeration borrowed the algorithm under test")
    for name in ("edge", "backward", "occupancy", "adjoint"):
        monkeypatch.setattr(lab, name, forbidden)
    assert lab.enumerate_paths(graph, probabilities)["objective"] == 7


def test_status_does_not_remove_offers_or_change_slot_masks():
    graph = lab.graphs()[-1]
    offers = deepcopy(graph.offers)
    offers[0] = (replace(offers[0][0], status="FILLED", exit_i=2, reward=-1.0),)
    changed = replace(graph, offers=offers)
    lab.validate(changed)
    assert lab.layout(changed) == lab.layout(graph)
    assert changed.slots == graph.slots
    params = [0.2] * len(lab.layout(graph))
    assert lab.policy(graph, params) == lab.policy(changed, params)


@pytest.mark.parametrize("fault", ["compressed", "reordered", "bool_clock", "mask", "invalid_offer",
    "nofill_exit", "nofill_reward", "early_fill", "late_fill", "status", "absent_source"])
def test_malformed_graphs_fail_closed(fault):
    graph = lab.graphs()[2]
    offers = deepcopy(graph.offers)
    if fault == "compressed":
        graph = replace(graph, slots=graph.slots[:2]+graph.slots[3:])
    elif fault == "reordered":
        graph = replace(graph, slots=(graph.slots[1], graph.slots[0], *graph.slots[2:]))
    elif fault == "bool_clock":
        graph = replace(graph, slots=(replace(graph.slots[0], t=False), *graph.slots[1:]))
    elif fault == "mask":
        graph = replace(graph, slots=(replace(graph.slots[0], token_mask=(1, False, True, False)), *graph.slots[1:]))
    elif fault == "absent_source":
        graph = replace(graph, source_status="NO_EVALUABLE")
    else:
        if fault == "invalid_offer":
            offers[2] = (lab.Offer("invalid", "NO_FILL", 3, 3, 0.0),)
        elif fault == "nofill_exit":
            offers[0] = (replace(offers[0][0], exit_i=2),)
        elif fault == "nofill_reward":
            offers[0] = (replace(offers[0][0], reward=1.0),)
        elif fault == "early_fill":
            offers[1] = (replace(offers[1][0], exit_i=2), offers[1][1])
        elif fault == "late_fill":
            offers[1] = (replace(offers[1][0], exit_i=11), offers[1][1])
        else:
            offers[0] = (replace(offers[0][0], status="UNKNOWN"),)
        graph = replace(graph, offers=offers)
    with pytest.raises(ValueError):
        lab.validate(graph)


@pytest.mark.parametrize("fault", ["omitted", "invented", "state_omitted", "unnormalized", "nan", "negative"])
def test_policy_support_and_probability_fail_closed(fault):
    graph = lab.graphs()[-1]
    probs = deterministic(graph)
    if fault == "omitted":
        probs[(0, 0)].pop("offer_0")
    elif fault == "invented":
        probs[(0, 0)]["invented"] = 0.0
    elif fault == "state_omitted":
        probs.pop((1, 1))
    elif fault == "unnormalized":
        probs[(0, 0)]["WAIT"] = 0.7
    elif fault == "nan":
        probs[(0, 0)]["WAIT"] = float("nan")
    else:
        probs[(0, 0)]["offer_0"] = -0.1
    with pytest.raises(ValueError):
        lab.enumerate_paths(graph, probs)
