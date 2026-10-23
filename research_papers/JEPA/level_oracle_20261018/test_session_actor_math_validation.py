"""Physical clocks, exact path identities and falsifiable artificial counterexamples."""

from dataclasses import replace
import inspect

import pytest
import torch

import session_actor_math_validation as lab


def uniform(graph):
    return lab.policy_from_logits(graph, torch.zeros(len(lab.layout(graph)), dtype=lab.DTYPE))


@pytest.mark.parametrize("graph", lab.fixtures(), ids=lambda graph: graph.name)
def test_all_paths_equal_dp_and_occupancies(graph):
    checks, _ = lab.value_checks(graph, uniform(graph))
    assert all(check["passed"] for check in checks), checks


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("graph", lab.fixtures(), ids=lambda graph: graph.name)
def test_adjoint_autograd_blocks_and_all_numerical_steps(graph, shared):
    result = lab.gradient_checks(graph, shared)
    assert all(check["passed"] for check in result["checks"]), result
    assert sum(check["check"].startswith("central step") for check in result["checks"]) == 3


def test_enumeration_does_not_call_dp_transition_or_occupancy(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Reference called implementation under test")

    for name in ("transition", "dynamic_program", "occupancy"):
        monkeypatch.setattr(lab, name, forbidden)
    graph = lab.fixtures()[2]
    direct = lab.enumerate_paths(graph, lab.note_policy(graph))
    assert float(direct["objective"]) == pytest.approx(-0.7)
    assert float(direct["pnl"]) == pytest.approx(0.65)
    assert float(direct["no_fill"]) == pytest.approx(0.45)
    assert float(direct["terminals"][(5, 1)]) == pytest.approx(0.55)
    assert float(direct["terminals"][(3, 0)]) == pytest.approx(0.45)


def test_no_fill_consumes_clock_and_does_not_retry_same_instant():
    graph = lab.Graph("miss", 0, 2, {0: (lab.Offer("miss", "NO_FILL", 1),
                                          lab.Offer("fill", "FILLED", 1, 2, 10))})
    policy = uniform(graph)
    direct = lab.enumerate_paths(graph, policy)
    assert float(direct["pnl"]) == pytest.approx(10 / 3)
    assert float(direct["no_fill"]) == pytest.approx(2 / 3)
    assert float(direct["fills"]) == pytest.approx(1 / 3)


def test_confluent_paths_sum_and_unreachable_states_have_zero_adjoint():
    graph = lab.Graph("merge", 4, 6, {
        0: (lab.Offer("A", "FILLED", 1, 2, 1), lab.Offer("B", "FILLED", 1, 2, -2)),
        3: (lab.Offer("C", "FILLED", 4, 5, 3),)})
    policy = uniform(graph)
    forward = lab.occupancy(graph, policy)
    assert float(forward["visits"][(3, 1)]) == pytest.approx(2 / 3)
    values, qvalues = lab.dynamic_program(graph, policy)
    for state in ((0, 1), (1, 1), (2, 1)):
        assert float(forward["visits"][state]) == 0
        for action, probability in policy[state].items():
            adjoint = forward["visits"][state] * probability * (qvalues[state, action] - values[state])
            assert float(adjoint) == 0


def test_filled_duration_skips_occupied_decisions():
    graph = lab.fixtures()[3]
    assert lab.transition(graph, (0, 0), "short")[0] == (3, 1)
    assert lab.transition(graph, (0, 0), "long")[0] == (4, 1)
    policy = uniform(graph)
    policy[(0, 0)] = {name: lab.scalar(float(name == "long")) for name in policy[(0, 0)]}
    forward = lab.occupancy(graph, policy)
    assert float(forward["visits"][(3, 1)]) == 0
    assert float(forward["visits"][(4, 1)]) == 1


def test_three_expected_fills_do_not_imply_daily_fill():
    graph = lab.fixtures()[4]
    direct = lab.enumerate_paths(graph, lab.three_fill_policy(graph))
    assert float(direct["fills"]) == 1.5
    assert float(direct["no_fill"]) == 0.5
    assert float(direct["pnl"]) == 1.5
    assert float(direct["objective"]) == 0


@pytest.mark.parametrize("offer,match", [
    (lab.Offer("A", "FILLED", 0, 2, 1), "Entry"),
    (lab.Offer("A", "FILLED", 1, 1, 1), "Exit"),
    (lab.Offer("A", "FILLED", 1, -1, 1), "Exit"),
    (lab.Offer("A", "FILLED", 1, 3, 1), "Exit"),
    (lab.Offer("A", "NO_FILL", 1, None, 1), "NO_FILL"),
    (lab.Offer("A", "NO_FILL", 1, 2), "NO_FILL"),
    (lab.Offer("A", "UNKNOWN", 1), "Unknown"),
    (lab.Offer("WAIT", "NO_FILL", 1), "reserved"),
    (lab.Offer("A", "FILLED", 1, 2, float("nan")), "reward"),
])
def test_invalid_graph_rejected(offer, match):
    graph = lab.Graph("invalid", 0, 2, {0: (offer,)})
    with pytest.raises(ValueError, match=match):
        lab.validate_graph(graph)


@pytest.mark.parametrize("values", [[-0.1, 1.1], [0.3, 0.3], [float("nan"), 0.5],
                                    [float("inf"), 0.5]])
def test_invalid_probabilities_rejected(values):
    graph = lab.Graph("invalid", 0, 2, {0: (lab.Offer("A", "NO_FILL", 1),)})
    policy = uniform(graph)
    policy[(0, 0)] = dict(zip(["WAIT", "A"], map(lab.scalar, values), strict=True))
    with pytest.raises(ValueError, match="[Pp]robabilit"):
        lab.enumerate_paths(graph, policy)


@pytest.mark.parametrize("mutation", ["add", "omit", "state", "float32", "mixed_dtype"])
def test_support_and_dtype_rejected(mutation):
    graph = lab.fixtures()[2]
    policy = uniform(graph)
    if mutation == "add":
        policy[(0, 0)]["absent"] = lab.scalar(0)
    elif mutation == "omit":
        del policy[(0, 0)]["A"]
    elif mutation == "state":
        del policy[(0, 0)]
    elif mutation == "mixed_dtype":
        policy[(0, 0)]["A"] = policy[(0, 0)]["A"].float()
    else:
        policy[(0, 0)] = {name: p.float() for name, p in policy[(0, 0)].items()}
    with pytest.raises(ValueError):
        lab.enumerate_paths(graph, policy)


def test_cardinality_changes_attempt_mass_not_fill_mass():
    for count in (1, 2, 3):
        graph = lab.Graph("duplicates", 0, 2,
                          {0: tuple(lab.Offer(str(i), "NO_FILL", 1) for i in range(count))})
        policy = uniform(graph)
        direct = lab.enumerate_paths(graph, policy)
        assert float(1 - policy[(0, 0)]["WAIT"]) == pytest.approx(count / (count + 1))
        assert float(direct["no_fill"]) == pytest.approx(1)
        assert float(direct["fills"]) == 0


def test_penalty_does_not_change_reported_pnl():
    graph = lab.fixtures()[2]
    zero = replace(graph, penalty=0)
    a = lab.enumerate_paths(graph, lab.note_policy(graph))
    b = lab.enumerate_paths(zero, lab.note_policy(zero))
    assert float(a["pnl"]) == float(b["pnl"])
    assert float(a["objective"] - b["objective"]) == pytest.approx(-1.35)


@pytest.mark.parametrize("field,value", [("start", False), ("last_decision", 0.5),
                                        ("last_liquidation", 2.5)])
def test_non_integer_horizons_rejected(field, value):
    graph = replace(lab.Graph("invalid", 0, 2, {}), **{field: value})
    with pytest.raises(ValueError, match="integers"):
        lab.validate_graph(graph)


@pytest.mark.parametrize("decision,entry,exit", [(False, 1, 2), (0, True, 2),
                                               (0, 1.0, 2), (0, 1, 2.5)])
def test_non_integer_offer_clocks_rejected(decision, entry, exit):
    graph = lab.Graph("invalid", 0, 3,
                      {decision: (lab.Offer("A", "FILLED", entry, exit, 1),)})
    with pytest.raises(ValueError, match="integer"):
        lab.validate_graph(graph)


def test_vector_probability_rejected_even_if_total_mass_is_one():
    graph = lab.Graph("invalid", 0, 2, {0: (lab.Offer("A", "NO_FILL", 1),)})
    policy = uniform(graph)
    policy[(0, 0)] = {"WAIT": lab.scalar([0.2, 0.3]), "A": lab.scalar([0.3, 0.2])}
    with pytest.raises(ValueError, match="scalar"):
        lab.validate_policy(graph, policy)


def test_source_has_no_optimizer_market_modules_or_neural_architecture():
    source = inspect.getsource(lab)
    for forbidden in ("torch.optim", "torch.nn", "pandas", "read_parquet", "ThetaData",
                      "evaluate_tcn", "audit_tcn", ".backward(", "manual_seed"):
        assert forbidden not in source
