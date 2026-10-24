"""Isolated artificial clock graphs; no market imports, arrays, fitting or optimizer."""
from dataclasses import asdict, dataclass
import argparse
import ctypes
import hashlib
import json
import math
from pathlib import Path

STEPS = (1e-4, 1e-5, 1e-6)


@dataclass(frozen=True)
class Slot:
    t: int
    state_valid: bool
    token_mask: tuple[bool, ...]
    bar_mask: tuple[bool, ...]
    map_mask: tuple[bool, ...]


@dataclass(frozen=True)
class Offer:
    name: str
    status: str
    entry_i: int
    exit_i: int
    reward: float


@dataclass(frozen=True)
class Graph:
    name: str
    slots: tuple[Slot, ...]
    offers: dict[int, tuple[Offer, ...]]
    last_liquidation: int
    penalty: float = 3.0
    source_status: str = "COMPLETE"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate(graph):
    require(graph.source_status == "COMPLETE", "Absent source cannot become WAIT session")
    require(graph.slots and len(graph.slots) <= 400, "Finite nonempty slots required")
    times = [s.t for s in graph.slots]
    require(all(type(t) is int for t in times) and type(graph.last_liquidation) is int, "Integer clocks required")
    require(times[0] >= 0 and times == list(range(times[0], times[-1] + 1)), "Consecutive ordered slots required")
    require(times[-1] <= graph.last_liquidation, "Liquidation horizon precedes decisions")
    require(math.isfinite(graph.penalty) and graph.penalty >= 0, "Invalid artificial penalty")
    require(len(graph.offers) <= 8, "At most eight branching slots")
    for slot in graph.slots:
        require(type(slot.state_valid) is bool, "Boolean state validity required")
        for mask in (slot.token_mask, slot.bar_mask, slot.map_mask):
            require(type(mask) is tuple and len(mask) == 4 and all(type(x) is bool for x in mask), "Four boolean toy masks required")
        require(slot.state_valid or not any((*slot.token_mask, *slot.bar_mask, *slot.map_mask)), "Invalid slot masks must remain false")
    for t, offers in graph.offers.items():
        require(type(t) is int and t in times, "Offer clock outside slots")
        require(graph.slots[t - times[0]].state_valid or not offers, "Offer at invalid slot")
        require(len(offers) <= 3, "Too many artificial offers")
        names = [o.name for o in offers]
        require(len(set(names)) == len(names) and all(type(n) is str and n and n != "WAIT" for n in names), "Duplicate or reserved action")
        for offer in offers:
            require(type(offer.entry_i) is int and type(offer.exit_i) is int, "Integer offer clocks required")
            require(offer.entry_i == t + 1, "Entry must equal t+1")
            require(math.isfinite(offer.reward), "Finite artificial reward required")
            if offer.status == "NO_FILL":
                require(offer.exit_i == t + 1 and offer.reward == 0, "NO_FILL requires exit=t+1 and zero reward")
            elif offer.status == "FILLED":
                require(t + 2 <= offer.exit_i <= graph.last_liquidation, "FILLED violates liquidation clock")
            else:
                raise ValueError("Unknown status")


def states(graph):
    return [(slot.t, h) for slot in graph.slots for h in (0, 1)]


def names(graph, t):
    return ("WAIT", *(offer.name for offer in graph.offers.get(t, ())))


def layout(graph):
    return [(s, a) for s in states(graph) if graph.offers.get(s[0]) for a in names(graph, s[0])]


def policy(graph, parameters, shared=False):
    """Fixed algebraic variables; returns probabilities and d(log pi)/d parameters."""
    validate(graph)
    size = len(layout(graph))
    require(len(parameters) == (3 if shared else size) and all(math.isfinite(x) for x in parameters), "Parameter support differs")
    result, log_derivatives, offset = {}, {}, 0
    for state in states(graph):
        actions = names(graph, state[0])
        if len(actions) == 1:
            result[state] = {"WAIT": 1.0}
            log_derivatives[(state, "WAIT")] = [0.0] * len(parameters)
            continue
        rows = []
        for i in range(offset, offset + len(actions)):
            row = [0.0] * len(parameters)
            if shared:
                row[i % 3] += 1 + (i % 3) / 4
                row[(i + 1) % 3] += 0.1
            else:
                row[i] = 1.0
            rows.append(row)
        logits = [sum(c * p for c, p in zip(row, parameters, strict=True)) for row in rows]
        exps = [math.exp(z - max(logits)) for z in logits]
        probs = [x / sum(exps) for x in exps]
        result[state] = dict(zip(actions, probs, strict=True))
        average = [sum(p * row[j] for p, row in zip(probs, rows, strict=True)) for j in range(len(parameters))]
        for action, row in zip(actions, rows, strict=True):
            log_derivatives[(state, action)] = [v - mean for v, mean in zip(row, average, strict=True)]
        offset += len(actions)
    return result, log_derivatives


def validate_policy(graph, probabilities):
    validate(graph)
    require(set(probabilities) == set(states(graph)), "Policy state support differs")
    for (t, _h), values in probabilities.items():
        require(set(values) == set(names(graph, t)), "Policy action support differs")
        require(all(type(x) is float and math.isfinite(x) and 0 <= x <= 1 for x in values.values()), "Invalid probability")
        require(abs(sum(values.values()) - 1) <= 1e-12, "Probabilities not normalized")


def enumerate_paths(graph, probabilities, log_derivatives=None):
    """Independent path expansion: no transition, DP or occupancy helper calls."""
    validate_policy(graph, probabilities)
    n = len(next(iter(log_derivatives.values()))) if log_derivatives else 0
    visits = {s: 0.0 for s in probabilities}
    branches = {(s, a): 0.0 for s in probabilities for a in probabilities[s]}
    terminals, gradient = {}, [0.0] * n
    totals = dict(objective=0.0, pnl=0.0, attempts=0.0, fills=0.0, no_fill=0.0)
    stack = [(graph.slots[0].t, 0, 1.0, 0.0, 0, 0, [0.0] * n)]
    paths = 0
    while stack:
        t, h, mass, net, attempts, fills, score = stack.pop()
        if t > graph.slots[-1].t:
            paths += 1
            terminals[(t, h)] = terminals.get((t, h), 0.0) + mass
            utility = net - graph.penalty * (1 - h)
            for key, value in dict(objective=utility, pnl=net, attempts=attempts, fills=fills, no_fill=1-h).items():
                totals[key] += mass * value
            for j in range(n):
                gradient[j] += mass * utility * score[j]
            continue
        state = (t, h)
        visits[state] += mass
        for action, probability in probabilities[state].items():
            branch = mass * probability
            branches[(state, action)] += branch
            new_score = [score[j] + log_derivatives[(state, action)][j] for j in range(n)]
            if action == "WAIT":
                stack.append((t + 1, h, branch, net, attempts, fills, new_score))
            else:
                offer = next(o for o in graph.offers[t] if o.name == action)
                if offer.status == "NO_FILL":
                    # Representation has exit_i=t+1; retry at this minute, not exit+1.
                    stack.append((t + 1, h, branch, net, attempts + 1, fills, new_score))
                else:
                    stack.append((offer.exit_i + 1, 1, branch, net + offer.reward, attempts + 1, fills + 1, new_score))
    return dict(**totals, visits=visits, branches=branches, terminals=terminals, gradient=gradient, paths=paths)


def edge(graph, state, action):
    t, h = state
    if action == "WAIT":
        return (t + 1, h), 0.0, 0, 0
    offer = next(o for o in graph.offers[t] if o.name == action)
    if offer.status == "NO_FILL":
        return (offer.exit_i, h), 0.0, 1, 0
    return (offer.exit_i + 1, 1), offer.reward, 1, 1


def backward(graph, probabilities):
    validate_policy(graph, probabilities)
    values, q = {}, {}
    for state in reversed(states(graph)):
        for action in probabilities[state]:
            target, net, _attempt, _fill = edge(graph, state, action)
            future = -graph.penalty * (1 - target[1]) if target[0] > graph.slots[-1].t else values[target]
            q[(state, action)] = net + future
        values[state] = sum(p * q[(state, a)] for a, p in probabilities[state].items())
    return values, q


def occupancy(graph, probabilities):
    validate_policy(graph, probabilities)
    visits = {s: 0.0 for s in probabilities}
    visits[(graph.slots[0].t, 0)] = 1.0
    branches, terminals = {}, {}
    pnl = attempts = fills = 0.0
    for state in states(graph):
        for action, probability in probabilities[state].items():
            mass = visits[state] * probability
            branches[(state, action)] = mass
            target, net, attempt, fill = edge(graph, state, action)
            pnl += mass * net
            attempts += mass * attempt
            fills += mass * fill
            if target[0] > graph.slots[-1].t:
                terminals[target] = terminals.get(target, 0.0) + mass
            else:
                visits[target] += mass
    no_fill = sum(m for (_t, h), m in terminals.items() if h == 0)
    return dict(pnl=pnl, attempts=attempts, fills=fills, no_fill=no_fill,
        objective=pnl-graph.penalty*no_fill, visits=visits, branches=branches, terminals=terminals)


def adjoint(graph, probabilities, log_derivatives):
    values, q = backward(graph, probabilities)
    forward = occupancy(graph, probabilities)
    n = len(next(iter(log_derivatives.values())))
    result = [0.0] * n
    for state in states(graph):
        for action, p in probabilities[state].items():
            coefficient = forward["visits"][state] * p * (q[(state, action)] - values[state])
            for j, derivative in enumerate(log_derivatives[(state, action)]):
                result[j] += coefficient * derivative
    return result


def compare(name, actual, expected, numerical=False):
    atol, rtol = (1e-7, 1e-5) if numerical else (1e-10, 1e-9)
    a = list(actual) if isinstance(actual, (list, tuple)) else [actual]
    b = list(expected) if isinstance(expected, (list, tuple)) else [expected]
    require(len(a) == len(b), "Comparison support differs")
    errors = [abs(x-y) for x, y in zip(a, b, strict=True)]
    return dict(check=name, passed=all(math.isfinite(x) and math.isfinite(y) and abs(x-y) <= atol+rtol*abs(y)
        for x, y in zip(a, b, strict=True)), max_absolute_error=max(errors, default=0.0),
        atol=atol, rtol=rtol, actual=actual, expected=expected)


def checks(graph, shared):
    parameters = [0.2, -0.3, 0.4] if shared else [(i % 7 - 3) / 5 for i in range(len(layout(graph)))]
    probs, derivative = policy(graph, parameters, shared)
    direct = enumerate_paths(graph, probs, derivative)
    values, _ = backward(graph, probs)
    forward = occupancy(graph, probs)
    results = [compare("DP objective", values[(graph.slots[0].t, 0)], direct["objective"])]
    for key in ("objective", "pnl", "attempts", "fills", "no_fill"):
        results.append(compare("occupancy " + key, forward[key], direct[key]))
    for key in ("visits", "branches", "terminals"):
        keys = sorted(set(forward[key]) | set(direct[key]))
        results.append(compare(key, [forward[key].get(k, 0.0) for k in keys], [direct[key].get(k, 0.0) for k in keys]))
    results.extend([compare("terminal mass", sum(direct["terminals"].values()), 1.0),
        compare("penalty separate", direct["objective"], direct["pnl"] - graph.penalty * direct["no_fill"]),
        compare("analytic path derivative vs adjoint", adjoint(graph, probs, derivative), direct["gradient"])])
    for step in STEPS:
        finite = []
        for j in range(len(parameters)):
            left, right = parameters.copy(), parameters.copy()
            left[j] -= step
            right[j] += step
            lo = enumerate_paths(graph, policy(graph, left, shared)[0])["objective"]
            hi = enumerate_paths(graph, policy(graph, right, shared)[0])["objective"]
            finite.append((hi-lo)/(2*step))
        results.append(compare(f"central difference {step:g}", finite, direct["gradient"], numerical=True))
    return dict(graph=graph.name, shared=shared, checks=results, paths=direct["paths"],
        metrics={k: direct[k] for k in ("objective", "pnl", "attempts", "fills", "no_fill")})


def make_graph(name, start, end, liquidation, entries, invalid=()):
    slots = tuple(Slot(t, t not in invalid, (True, False, True, False) if t == start and t not in invalid
        else (t not in invalid,) * 4, (t not in invalid,) * 4, (t not in invalid,) * 4) for t in range(start, end+1))
    offers = {}
    for i, (t, status, exit_i, reward) in enumerate(entries):
        offers[t] = (*offers.get(t, ()), Offer(f"offer_{i}", status, t+1, exit_i, float(reward)))
    return Graph(name, slots, offers, liquidation)


def graphs():
    return [make_graph("wait_only", 0, 3, 5, [], (1, 2)),
        make_graph("no_fill_only", 0, 3, 5, [(0, "NO_FILL", 1, 0), (2, "NO_FILL", 3, 0)], (1,)),
        make_graph("mixed", 0, 8, 10, [(0, "NO_FILL", 1, 0), (1, "FILLED", 3, 4),
            (1, "NO_FILL", 2, 0), (4, "FILLED", 6, -2), (6, "FILLED", 8, 1)], (2, 5)),
        make_graph("full_clock", 60, 375, 385, [(60, "NO_FILL", 61, 0), (61, "FILLED", 63, 2),
            (375, "FILLED", 385, 1)], (62, 374)),
        make_graph("short_clock", 60, 195, 205, [(60, "NO_FILL", 61, 0), (61, "FILLED", 63, 2),
            (195, "FILLED", 205, 1)], (62, 194)),
        make_graph("retry_counterexample", 0, 1, 3, [(0, "NO_FILL", 1, 0), (1, "FILLED", 3, 7)])]


def counterexample():
    graph = graphs()[-1]
    probs = {s: {a: float(a != "WAIT") for a in names(graph, s[0])} for s in states(graph)}
    correct = enumerate_paths(graph, probs)
    # Deliberately wrong simulator: uses exit+1 for every attempt, including NO_FILL.
    t = graph.slots[0].t
    pnl = attempts = fills = 0
    while t <= graph.slots[-1].t:
        offer = graph.offers[t][0]
        attempts += 1
        if offer.status == "FILLED":
            pnl += offer.reward
            fills += 1
        t = offer.exit_i + 1
    wrong = dict(pnl=pnl, attempts=attempts, fills=fills, objective=pnl-graph.penalty*(fills == 0))
    expected = dict(pnl=7.0, attempts=2.0, fills=1.0, objective=7.0)
    return dict(correct={k: correct[k] for k in expected}, wrong=wrong,
        checks=[compare("correct " + k, correct[k], v) for k, v in expected.items()]
        + [compare("wrong " + k, wrong[k], v) for k, v in dict(pnl=0, attempts=1, fills=0, objective=-3).items()])


def resource_gate():
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (n, ctypes.c_ulonglong) for n in ("total", "ram", "total_commit", "commit", "v", "fv", "ex")]
    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    require(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)), "Windows resource observation failed")
    result = dict(available_ram_bytes=memory.ram, free_commit_bytes=memory.commit)
    require(min(result.values()) >= 2_000_000_000, "2GB RAM/commit gate unmet")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    resources = resource_gate()
    require(not args.output.exists(), "Fresh result path required")
    cases = [checks(graph, shared) for graph in graphs() for shared in (False, True)]
    example = counterexample()
    all_checks = [c for case in cases for c in case["checks"]] + example["checks"]
    result = dict(status="PASS_SYNTHETIC_CLOCK_SEMANTICS" if all(c["passed"] for c in all_checks) else "FAIL_SYNTHETIC_CLOCK_SEMANTICS",
        scope="MATHEMATICAL_SYNTHETIC_ONLY", runtime_market_authorized=False, resources_before_comparisons=resources,
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        graphs=[asdict(g) for g in graphs()], cases=cases, counterexample=example,
        comparison_count=len(all_checks), max_absolute_error=max(c["max_absolute_error"] for c in all_checks))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return 0 if result["status"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
