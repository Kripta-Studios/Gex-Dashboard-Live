"""Finite artificial session graphs: no data, model, optimizer or market runner."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import time

for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_name] = "1"

import torch  # noqa: E402 -- thread limits must precede the numerical runtime.

torch.set_num_threads(1)
torch.set_num_interop_threads(1)
DTYPE = torch.float64
STEPS = (1e-4, 1e-5, 1e-6)


@dataclass(frozen=True)
class Offer:
    name: str
    status: str
    entry: int
    exit: int | None = None
    reward: float = 0.0


@dataclass(frozen=True)
class Graph:
    name: str
    last_decision: int
    last_liquidation: int
    offers: dict[int, tuple[Offer, ...]]
    penalty: float = 3.0
    start: int = 0


def scalar(value):
    return torch.tensor(value, dtype=DTYPE, device="cpu")


def states(graph):
    return [(t, h) for t in range(graph.start, graph.last_decision + 1) for h in (0, 1)]


def validate_graph(graph):
    if any(type(value) is not int for value in
           (graph.start, graph.last_decision, graph.last_liquidation)):
        raise ValueError("Clock indices must be integers, not booleans")
    if not (0 <= graph.start <= graph.last_decision <= graph.last_liquidation):
        raise ValueError("Invalid horizons")
    if not math.isfinite(graph.penalty) or graph.penalty < 0:
        raise ValueError("Invalid artificial penalty")
    if len(graph.offers) > 8:
        raise ValueError("Too many branching decisions")
    for t, offers in graph.offers.items():
        if type(t) is not int:
            raise ValueError("Decision clock must be integer")
        if t not in range(graph.start, graph.last_decision + 1) or len(offers) > 3:
            raise ValueError("Invalid decision or offer count")
        names = [offer.name for offer in offers]
        if len(set(names)) != len(names) or "WAIT" in names:
            raise ValueError("Duplicate or reserved action")
        for offer in offers:
            if type(offer.entry) is not int or (offer.exit is not None and type(offer.exit) is not int):
                raise ValueError("Entry and exit clocks must be integers")
            if offer.entry != t + 1:
                raise ValueError("Entry must be decision plus one")
            if offer.status == "FILLED":
                if offer.exit is None or not offer.entry + 1 <= offer.exit <= graph.last_liquidation:
                    raise ValueError("Exit violates physical clock")
                if not math.isfinite(offer.reward):
                    raise ValueError("Invalid reward")
            elif offer.status == "NO_FILL":
                if offer.reward != 0 or offer.exit is not None:
                    raise ValueError("NO_FILL must have zero reward and no exit")
            else:
                raise ValueError("Unknown offer status")


def validate_policy(graph, policy):
    validate_graph(graph)
    if set(policy) != set(states(graph)):
        raise ValueError("Policy state support differs")
    for (t, _h), probabilities in policy.items():
        expected = {"WAIT", *(offer.name for offer in graph.offers.get(t, ()))}
        if set(probabilities) != expected:
            raise ValueError("Unavailable or omitted action")
        if any(not isinstance(value, torch.Tensor) or value.ndim != 0
               for value in probabilities.values()):
            raise ValueError("Each probability must be a scalar tensor")
        if any(value.dtype != DTYPE or value.device.type != "cpu"
               for value in probabilities.values()):
            raise ValueError("Every probability requires CPU float64")
        values = torch.stack(list(probabilities.values()))
        if values.dtype != DTYPE or values.device.type != "cpu":
            raise ValueError("CPU float64 required")
        if not torch.isfinite(values).all() or (values < 0).any():
            raise ValueError("Invalid probability")
        if abs(float(values.detach().sum()) - 1) > 1e-12:
            raise ValueError("Probabilities must sum to one")


def enumerate_paths(graph, policy):
    """Direct path expansion; deliberately does not call DP or transition helpers."""
    validate_policy(graph, policy)
    visits = {s: scalar(0) for s in policy}
    branches = {(s, a): scalar(0) for s in policy for a in policy[s]}
    terminals = {}
    total = pnl = no_fill = count = scalar(0)
    paths = 0
    stack = [(graph.start, 0, scalar(1), scalar(0), 0)]
    while stack:
        t, h, mass, net, fills = stack.pop()
        if t > graph.last_decision:
            paths += 1
            terminals[(t, h)] = terminals.get((t, h), scalar(0)) + mass
            total = total + mass * (net - graph.penalty * (1 - h))
            pnl = pnl + mass * net
            no_fill = no_fill + mass * (1 - h)
            count = count + mass * fills
            continue
        state = (t, h)
        visits[state] = visits[state] + mass
        for name, probability in policy[state].items():
            branch_mass = mass * probability
            branches[(state, name)] = branches[(state, name)] + branch_mass
            if name == "WAIT":
                stack.append((t + 1, h, branch_mass, net, fills))
            else:
                offer = next(item for item in graph.offers.get(t, ()) if item.name == name)
                if offer.status == "NO_FILL":
                    stack.append((t + 1, h, branch_mass, net, fills))
                else:
                    stack.append((offer.exit + 1, 1, branch_mass, net + offer.reward, fills + 1))
    return dict(objective=total, pnl=pnl, no_fill=no_fill, fills=count,
                visits=visits, branches=branches, terminals=terminals, paths=paths)


def transition(graph, state, name):
    t, h = state
    if name == "WAIT":
        return (t + 1, h), 0.0, 0
    offer = next((item for item in graph.offers.get(t, ()) if item.name == name), None)
    if offer is None:
        raise ValueError("Unavailable action")
    if offer.status == "NO_FILL":
        return (t + 1, h), 0.0, 0
    return (offer.exit + 1, 1), offer.reward, 1


def dynamic_program(graph, policy):
    validate_policy(graph, policy)
    values, qvalues = {}, {}
    for state in reversed(states(graph)):
        value = scalar(0)
        for name, probability in policy[state].items():
            target, reward, _ = transition(graph, state, name)
            future = (scalar(-graph.penalty * (1 - target[1]))
                      if target[0] > graph.last_decision else values[target])
            qvalues[(state, name)] = reward + future
            value = value + probability * qvalues[(state, name)]
        values[state] = value
    return values, qvalues


def occupancy(graph, policy):
    validate_policy(graph, policy)
    visits = {s: scalar(0) for s in policy}
    visits[(graph.start, 0)] = scalar(1)
    branches, terminals = {}, {}
    pnl = fills = scalar(0)
    for state in states(graph):
        for name, probability in policy[state].items():
            mass = visits[state] * probability
            branches[(state, name)] = mass
            target, reward, filled = transition(graph, state, name)
            pnl = pnl + mass * reward
            fills = fills + mass * filled
            if target[0] > graph.last_decision:
                terminals[target] = terminals.get(target, scalar(0)) + mass
            else:
                visits[target] = visits[target] + mass
    no_fill = sum((mass for (_t, h), mass in terminals.items() if h == 0), scalar(0))
    return dict(visits=visits, branches=branches, terminals=terminals, pnl=pnl,
                fills=fills, no_fill=no_fill, objective=pnl - graph.penalty * no_fill)


def layout(graph):
    return [(s, name) for s in states(graph)
            for name in ("WAIT", *(offer.name for offer in graph.offers.get(s[0], ())))]


def policy_from_logits(graph, logits):
    result, offset = {}, 0
    for state in states(graph):
        names = ["WAIT", *(offer.name for offer in graph.offers.get(state[0], ()))]
        probabilities = torch.softmax(logits[offset:offset + len(names)], dim=0)
        result[state] = dict(zip(names, probabilities, strict=True))
        offset += len(names)
    if offset != len(logits):
        raise ValueError("Logit support differs")
    return result


def shared_logits(parameters, size):
    # Small algebraic expressions with shared variables; no network or fitting.
    return torch.stack([(1 + (i % 3) / 4) * parameters[i % 3]
                        + 0.1 * parameters[(i + 1) % 3] ** 2 for i in range(size)])


def compare(label, actual, expected, numerical=False):
    left = torch.as_tensor(actual, dtype=DTYPE).detach()
    right = torch.as_tensor(expected, dtype=DTYPE).detach()
    atol, rtol = (1e-7, 1e-5) if numerical else (1e-10, 1e-9)
    error = float(torch.max(torch.abs(left - right))) if left.numel() else 0.0
    return dict(check=label, passed=bool(torch.allclose(left, right, atol=atol, rtol=rtol)),
                max_absolute_error=error, atol=atol, rtol=rtol,
                actual=left.tolist(), expected=right.tolist())


def value_checks(graph, policy):
    direct = enumerate_paths(graph, policy)
    values, _ = dynamic_program(graph, policy)
    forward = occupancy(graph, policy)
    checks = [compare("DP objective", values[(graph.start, 0)], direct["objective"])]
    for key in ("objective", "pnl", "no_fill", "fills"):
        checks.append(compare("occupancy " + key, forward[key], direct[key]))
    for key in ("visits", "branches", "terminals"):
        keys = sorted(set(direct[key]) | set(forward[key]))
        checks.append(compare(key, torch.stack([forward[key].get(s, scalar(0)) for s in keys]),
                              torch.stack([direct[key].get(s, scalar(0)) for s in keys])))
    checks.append(compare("terminal mass", sum(direct["terminals"].values()), scalar(1)))
    checks.append(compare("penalty separate", direct["objective"],
                          direct["pnl"] - graph.penalty * direct["no_fill"]))
    return checks, direct


def gradient_checks(graph, shared=False):
    size = len(layout(graph))
    initial = [0.2, -0.3, 0.4] if shared else [(i % 7 - 3) / 5 for i in range(size)]
    parameters = scalar(initial).requires_grad_()

    def logits_for(params):
        return shared_logits(params, size) if shared else params

    logits = logits_for(parameters)
    policy = policy_from_logits(graph, logits)
    values, qvalues = dynamic_program(graph, policy)
    forward = occupancy(graph, policy)
    direct = enumerate_paths(graph, policy)
    gradient = torch.autograd.grad(direct["objective"], parameters, retain_graph=True)[0]
    dp_gradient = torch.autograd.grad(values[(graph.start, 0)], parameters, retain_graph=True)[0]
    adjoint = torch.stack([forward["visits"][s] * policy[s][a] * (qvalues[(s, a)] - values[s])
                           for s, a in layout(graph)]).detach()
    chain = torch.autograd.grad((logits * adjoint).sum(), parameters)[0]
    checks = [compare("autograd DP vs enumeration", dp_gradient, gradient),
              compare("adjoint chain vs enumeration", chain, gradient)]
    accumulated = torch.zeros_like(parameters)
    original = parameters.detach().clone()
    for start in range(0, size, 3):
        fresh_logits = logits_for(parameters)
        checks.append(compare(f"block {start} logits", fresh_logits, logits.detach()))
        loss = (fresh_logits[start:start + 3] * adjoint[start:start + 3]).sum()
        accumulated += torch.autograd.grad(loss, parameters)[0]
    checks.append(compare("block gradient", accumulated, gradient))
    checks.append(compare("unchanged variables", parameters, original))
    for step in STEPS:
        differences = []
        for index in range(len(parameters)):
            plus, minus = original.clone(), original.clone()
            plus[index] += step
            minus[index] -= step
            a = enumerate_paths(graph, policy_from_logits(graph, logits_for(plus)))["objective"]
            b = enumerate_paths(graph, policy_from_logits(graph, logits_for(minus)))["objective"]
            differences.append((a - b) / (2 * step))
        checks.append(compare(f"central step {step}", torch.stack(differences), gradient, True))
    return dict(mode="shared_algebraic" if shared else "independent_logits", checks=checks,
                parameters=original.tolist(), logits=logits.detach().tolist())


def fixtures():
    return [
        Graph("wait_only", 2, 4, {}),
        Graph("all_no_fill", 2, 4, {0: (Offer("N", "NO_FILL", 1),),
                                     2: (Offer("M", "NO_FILL", 3),)}),
        Graph("note", 2, 4, {0: (Offer("A", "FILLED", 1, 4, 2),),
                              2: (Offer("B", "FILLED", 3, 4, -1),)}),
        Graph("durations_confluence", 6, 8, {
            0: (Offer("short", "FILLED", 1, 2, 2), Offer("long", "FILLED", 1, 3, -1),
                Offer("miss", "NO_FILL", 1)),
            3: (Offer("C", "FILLED", 4, 5, -2),),
            4: (Offer("D", "FILLED", 5, 6, 3),),
            6: (Offer("E", "FILLED", 7, 8, 1),)}),
        Graph("three_fills_or_none", 6, 8, {
            t: (Offer("F", "FILLED", t + 1, t + 2, 1),) for t in (0, 3, 6)}),
    ]


def note_policy(graph):
    policy = {}
    for state in states(graph):
        probability = 0.4 if state[0] == 0 else 0.25
        names = [offer.name for offer in graph.offers.get(state[0], ())]
        policy[state] = {"WAIT": scalar(1 - probability if names else 1)}
        policy[state].update({name: scalar(probability) for name in names})
    return policy


def three_fill_policy(graph):
    policy = {}
    for t, h in states(graph):
        if t in graph.offers:
            probability = 0.5 if t == 0 else float(h)
            policy[(t, h)] = {"WAIT": scalar(1 - probability), "F": scalar(probability)}
        else:
            policy[(t, h)] = {"WAIT": scalar(1)}
    return policy


def run_validation():
    cases, all_checks = [], []
    for graph in fixtures():
        logits = scalar([(i % 7 - 3) / 5 for i in range(len(layout(graph)))])
        policy = policy_from_logits(graph, logits)
        recorded_policy = {str(s): {a: float(p.detach()) for a, p in row.items()}
                           for s, row in policy.items()}
        checks, direct = value_checks(graph, policy)
        gradients = [gradient_checks(graph, shared) for shared in (False, True)]
        special = []
        if graph.name == "note":
            special, note = value_checks(graph, note_policy(graph))
            for key, expected in (("objective", -0.7), ("pnl", 0.65), ("no_fill", 0.45)):
                special.append(compare("note " + key, note[key], scalar(expected)))
            variables = scalar([math.log(0.4 / 0.6), math.log(0.25 / 0.75)]).requires_grad_()
            p, q = torch.sigmoid(variables)
            policy = note_policy(graph)
            for t, h in states(graph):
                if t in (0, 2):
                    prob = p if t == 0 else q
                    policy[(t, h)] = {"WAIT": 1 - prob, "A" if t == 0 else "B": prob}
            grad = torch.autograd.grad(enumerate_paths(graph, policy)["objective"], variables)[0]
            special.append(compare("note log odds gradients", grad, scalar([1.08, 0.225])))
        if graph.name == "three_fills_or_none":
            special, triple = value_checks(graph, three_fill_policy(graph))
            special += [compare("expected fills", triple["fills"], scalar(1.5)),
                        compare("positive no fill", triple["no_fill"], scalar(0.5))]
        case = dict(graph=asdict(graph), policy=recorded_policy,
                    paths=direct["paths"], checks=checks, gradients=gradients, special=special)
        cases.append(case)
        all_checks.extend(checks + special + [c for g in gradients for c in g["checks"]])
    cardinality = []
    for n in (1, 2, 3):
        graph = Graph(f"cardinality_{n}", 0, 2,
                      {0: tuple(Offer(str(i), "NO_FILL", 1) for i in range(n))})
        policy = policy_from_logits(graph, torch.zeros(len(layout(graph)), dtype=DTYPE))
        direct = enumerate_paths(graph, policy)
        cardinality += [compare(f"N={n} attempt", 1 - policy[(0, 0)]["WAIT"], scalar(n / (n + 1))),
                        compare(f"N={n} no fill", direct["no_fill"], scalar(1))]
    all_checks.extend(cardinality)
    return dict(status="PASS_ARTIFICIAL_MATH_IDENTITIES" if all(c["passed"] for c in all_checks)
                else "FAILED_MATH_VALIDATION", cases=cases, cardinality=cardinality,
                checks=len(all_checks), failed=[c for c in all_checks if not c["passed"]],
                max_absolute_error=max(c["max_absolute_error"] for c in all_checks),
                scope="Artificial exogenous graphs only; no market or profitability evidence")


def resource_gate():
    import psutil

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                    *[(name, ctypes.c_ulonglong) for name in
                      ("total_phys", "avail_phys", "total_page", "avail_page", "total_virtual",
                       "avail_virtual", "avail_extended")]]

    if os.name != "nt":
        raise RuntimeError("This receipt requires Windows commit headroom")
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("GlobalMemoryStatusEx failed")
    process = psutil.Process()
    available_cpus = process.cpu_affinity()
    process.cpu_affinity([available_cpus[0]])
    receipt = dict(available_ram_bytes=status.avail_phys,
                   available_commit_bytes=status.avail_page, cpu_affinity=process.cpu_affinity(),
                   torch_threads=torch.get_num_threads(), dtype="float64", device="cpu")
    receipt["torch_interop_threads"] = torch.get_num_interop_threads()
    receipt["passed"] = status.avail_phys >= 2_000_000_000 and status.avail_page >= 2_000_000_000
    return receipt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = dict(started=datetime.now(timezone.utc).isoformat(), pid=os.getpid(),
                   source_sha256=sha(__file__), status="STARTED")
    started = time.monotonic()
    receipt_path = args.output / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    try:
        receipt["resources"] = resource_gate()
        if not receipt["resources"]["passed"]:
            raise RuntimeError("RAM/commit gate below 2 GB")
        result = run_validation()
        (args.output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        receipt["result_sha256"] = sha(args.output / "result.json")
        receipt["status"] = result["status"]
        if result["failed"]:
            raise AssertionError("Mathematical comparisons failed; full results preserved")
    except BaseException as error:
        receipt.update(status="FAILED", error=repr(error))
        raise
    finally:
        receipt["elapsed_seconds"] = time.monotonic() - started
        receipt["finished"] = datetime.now(timezone.utc).isoformat()
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("cases", "cardinality")}))


if __name__ == "__main__":
    main()
