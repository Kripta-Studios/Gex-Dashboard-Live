from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import ctypes
from collections import defaultdict
from pathlib import Path


BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
SOURCE = BASE / "ev_components_diagnostic_01"
OUTPUT = BASE / "ev_components_independent_review_01"
CONTRACT = Path(
    r"C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live"
    r"\research_papers\JEPA\weekly_multiday_20261101"
    r"\EV_COMPONENT_DIAGNOSTIC_CONTRACT_20261101.md"
)

POLICIES = (
    "FROZEN_CONTEXT182",
    "MONTHLY_RAW",
    "WEEKLY_RAW",
    "MONTHLY_GUARDED",
    "WEEKLY_GUARDED",
)
LEDGERS = {
    p: BASE / "h2_context_adaptation_01" / f"ledger_{p.lower()}_adverse.jsonl"
    for p in POLICIES
}
CANDIDATE_PATHS = (
    BASE / "h2_dataset_v2_01" / "candidates.jsonl",
    BASE / "h2_dataset_v2_extension_2026q3_partial_01" / "candidates.jsonl",
    BASE / "h2_boundary_bridge_01" / "candidates.jsonl",
)
SCORES_PATH = BASE / "h2_context_adaptation_01" / "candidate_scores.jsonl"
STATES_PATH = BASE / "h2_context_adaptation_01" / "states.jsonl"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def snapshot(path: Path) -> dict[str, object]:
    st = path.stat()
    return {"path": str(path), "bytes": st.st_size, "sha256": sha256(path)}


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def dump_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def close(a: float, b: float, tol: float) -> bool:
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=tol)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def resource_gate() -> dict[str, int]:
    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong), ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong), ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]
    value = MemoryStatusEx()
    value.length = ctypes.sizeof(MemoryStatusEx)
    require(bool(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value))), "memory observation failed")
    observed = {
        "available_ram_bytes": int(value.available_physical),
        "free_commit_bytes": int(value.available_page_file),
    }
    require(min(observed.values()) >= 2_000_000_000, f"2GB resource gate failed: {observed}")
    require(os.environ.get("CUDA_VISIBLE_DEVICES") == "-1", "CPU-only gate missing")
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        require(os.environ.get(key) == "1", f"thread gate missing: {key}")
    return observed


def aggregate(
    members: list[dict], policy: str, universe: str, view: str,
    partition: str, value: str, quantities: dict[str, int], exit_net: dict[str, float],
) -> dict:
    members = sorted(members, key=lambda row: row["candidate_id"])
    n = len(members)
    fs = math.fsum
    sums = {
        name: fs(float(row[name]) for row in members)
        for name in (
            "ev", "net", "error", "c_probability", "c_payoff",
            "c_model", "c_calibration",
        )
    }
    result = {
        "policy": policy,
        "universe": universe,
        "view": view,
        "partition": partition,
        "value": value,
        "n": n,
        "lower_bound_n": sum(bool(row["payoff_is_lower_bound"]) for row in members),
        "sum_ev": sums["ev"],
        "sum_net": sums["net"],
        "sum_error": sums["error"],
        "sum_c_probability": sums["c_probability"],
        "sum_c_payoff": sums["c_payoff"],
        "sum_c_model": sums["c_model"],
        "sum_c_calibration": sums["c_calibration"],
        "sum_class_contributions": [
            fs(float(row["class_contributions"][k]) for row in members) for k in range(5)
        ],
        "mean_ev": sums["ev"] / n if n else None,
        "mean_net": sums["net"] / n if n else None,
        "mean_error": sums["error"] / n if n else None,
        "mean_c_probability": sums["c_probability"] / n if n else None,
        "mean_c_payoff": sums["c_payoff"] / n if n else None,
        "mean_c_model": sums["c_model"] / n if n else None,
        "mean_c_calibration": sums["c_calibration"] / n if n else None,
        "mae_error": fs(abs(float(row["error"])) for row in members) / n if n else None,
        "rmse_error": math.sqrt(fs(float(row["error"]) ** 2 for row in members) / n) if n else None,
        "mean_abs_c_probability": fs(abs(float(row["c_probability"])) for row in members) / n if n else None,
        "mean_abs_c_payoff": fs(abs(float(row["c_payoff"])) for row in members) / n if n else None,
        "cell_n_min": [min(int(row["cell_n"][k]) for row in members) for k in range(5)] if n else None,
        "cell_n_mean": [fs(float(row["cell_n"][k]) for row in members) / n for k in range(5)] if n else None,
        "max_abs_residual": max(
            (abs(float(x)) for row in members for x in row["residuals"].values()), default=0.0
        ),
    }
    eligible = [row for row in members if row["model_label_eligible"]]
    if eligible:
        eps = 1e-15
        result["logloss"] = -fs(
            math.log(min(1.0 - eps, max(eps, float(row["p_cal"][int(row["scenario"])]))))
            for row in eligible
        ) / len(eligible)
        result["brier"] = fs(
            fs((float(row["p_cal"][k]) - (1.0 if int(row["scenario"]) == k else 0.0)) ** 2 for k in range(5))
            for row in eligible
        ) / len(eligible)
    else:
        result["logloss"] = None
        result["brier"] = None
    if universe == "FILLED":
        result["sum_quantity_ev"] = fs(float(row["ev"]) * quantities[row["candidate_id"]] for row in members)
        result["sum_quantity_net"] = fs(float(row["net"]) * quantities[row["candidate_id"]] for row in members)
        result["exit_net_usd"] = fs(exit_net[row["candidate_id"]] for row in members)
    return result


def main() -> int:
    gate = resource_gate()
    require(OUTPUT.is_dir(), "review output root missing")
    own_outputs = [
        OUTPUT / "components_recomputed.jsonl",
        OUTPUT / "aggregates_recomputed.jsonl",
        OUTPUT / "comparison.json",
        OUTPUT / "findings.json",
        OUTPUT / "receipt.json",
    ]
    require(not any(path.exists() for path in own_outputs), "review output already exists")

    producer_manifest = load_json(SOURCE / "manifest.json")
    expected_inputs = producer_manifest["inputs_before"]
    input_paths = [Path(item["path"]) for item in expected_inputs.values()]
    input_before = {str(path): snapshot(path) for path in sorted(input_paths, key=str)}
    for path, got in input_before.items():
        expected = expected_inputs[path]
        require(got["sha256"] == expected["sha256"] and got["bytes"] == expected["bytes"], f"input pin mismatch: {path}")

    candidates: dict[str, dict] = {}
    source_candidate_count = 0
    for path in CANDIDATE_PATHS:
        for row in load_jsonl(path):
            source_candidate_count += 1
            cid = row["candidate_id"]
            require(cid not in candidates, f"duplicate candidate: {cid}")
            candidates[cid] = row
    require(source_candidate_count == 3240 and len(candidates) == 3240, "candidate universe is not 3240 unique IDs")

    scores = load_jsonl(SCORES_PATH)
    require(len(scores) == 3060, "score row count is not 3060")
    score_keys = [(row["policy"], row["candidate_id"]) for row in scores]
    require(len(set(score_keys)) == 3060, "duplicate policy/candidate score")
    by_policy_ids = {policy: {row["candidate_id"] for row in scores if row["policy"] == policy} for policy in POLICIES}
    common_ids = set.intersection(*by_policy_ids.values())
    require(len(common_ids) == 612 and all(ids == common_ids for ids in by_policy_ids.values()), "policy candidate IDs are not identical 612-member sets")
    require(common_ids <= candidates.keys(), "score candidate absent from sealed candidate union")

    states = {row["state_id"]: row for row in load_jsonl(STATES_PATH)}
    require(len(states) == 42, "adaptive state count is not 42")
    frozen_model = load_json(BASE / "h2_ev_v2_01" / "model.json")
    frozen_means = load_json(BASE / "h2_ev_v2_01" / "conditional_means.json")
    frozen_cal = load_json(BASE / "h2_context_model_comparison_01" / "context182_calibration.json")

    selected: dict[str, set[str]] = {}
    filled: dict[str, set[str]] = {}
    quantities: dict[str, dict[str, int]] = {}
    exit_nets: dict[str, dict[str, float]] = {}
    for policy, path in LEDGERS.items():
        ledger = load_jsonl(path)
        selected[policy] = {
            row["candidate_id"] for row in ledger
            if row["event"] in {"ENTRY", "NO_FILL", "CAPITAL_BLOCKED"}
        }
        entries = {row["candidate_id"]: row for row in ledger if row["event"] == "ENTRY"}
        exits = {row["candidate_id"]: row for row in ledger if row["event"] == "EXIT"}
        require(entries.keys() == exits.keys(), f"ENTRY/EXIT mismatch: {policy}")
        filled[policy] = set(entries)
        quantities[policy] = {}
        exit_nets[policy] = {}
        for cid in sorted(entries):
            entry, exit_row = entries[cid], exits[cid]
            require(entry["model_id"] == exit_row["model_id"], f"model mismatch: {policy}/{cid}")
            require(int(entry["quantity"]) == int(exit_row["quantity"]), f"quantity mismatch: {policy}/{cid}")
            quantities[policy][cid] = int(entry["quantity"])
            exit_nets[policy][cid] = float(exit_row["net_usd"])

    rows: list[dict] = []
    max_probability_residual = 0.0
    for score in sorted(scores, key=lambda row: (row["policy"], row["candidate_id"])):
        policy, cid = score["policy"], score["candidate_id"]
        candidate = candidates[cid]
        if score["model_id"] == "FROZEN_CONTEXT182_H1":
            require(score["model_id"] == "FROZEN_CONTEXT182_H1", "unexpected frozen model ID")
            prior = [float(x) for x in frozen_model["train_prior"]]
            alpha = float(frozen_cal["selected_alpha"])
            cell = frozen_means["cells"]["adverse"][f"{candidate['ticker']}:{candidate['right']}"]
        else:
            state = states[score["model_id"]]
            prior = [float(x) for x in state["prior"]]
            alpha = float(state["calibration"]["selected_alpha"])
            cell = state["conditional_means"]["cells"]["adverse"][f"{candidate['ticker']}:{candidate['right']}"]
        q = [float(x) for x in score["p_model"]]
        p_stored = [float(x) for x in score["p_cal"]]
        require(len(q) == len(p_stored) == len(prior) == 5, f"probability length: {policy}/{cid}")
        p = [(1.0 - alpha) * q[k] + alpha * prior[k] for k in range(5)]
        prob_resid = max(abs(p[k] - p_stored[k]) for k in range(5))
        max_probability_residual = max(max_probability_residual, prob_resid)
        require(prob_resid <= 1e-10, f"calibration mismatch: {policy}/{cid}")
        require(abs(math.fsum(p) - 1.0) <= 1e-10, f"probability sum mismatch: {policy}/{cid}")
        means = [float(cell[str(k)]["mean_y"]) for k in range(5)]
        cell_n = [int(cell[str(k)]["n"]) for k in range(5)]
        scenario = int(candidate["scenario"])
        scale = float(candidate["decision_ask"]) * 100.0
        ev = scale * math.fsum(p[k] * means[k] for k in range(5))
        realized = scale * means[scenario]
        net = float(candidate["net_adverse"])
        c_model = scale * math.fsum(q[k] * means[k] for k in range(5)) - realized
        c_cal = scale * math.fsum((p[k] - q[k]) * means[k] for k in range(5))
        c_prob = ev - realized
        c_payoff = realized - net
        error = ev - net
        contrib = [scale * (p[k] - (1.0 if scenario == k else 0.0)) * means[k] for k in range(5)]
        residuals = {
            "stored_ev": ev - float(score["ev_adverse"]),
            "error_components": error - (c_prob + c_payoff),
            "probability_components": c_prob - (c_model + c_cal),
            "class_contributions": c_prob - math.fsum(contrib),
        }
        require(max(abs(x) for x in residuals.values()) <= 1e-8, f"identity residual: {policy}/{cid}")
        require(score["ticker"] == candidate["ticker"] and score["right"] == candidate["right"], f"candidate identity mismatch: {policy}/{cid}")
        require(int(score["scenario"]) == scenario and score["entry_date"] == candidate["entry_date"], f"candidate label mismatch: {policy}/{cid}")
        require(bool(score["payoff_is_lower_bound"]) == bool(candidate["payoff_is_lower_bound"]), f"lower-bound mismatch: {policy}/{cid}")
        rows.append({
            "alpha": alpha,
            "c_calibration": c_cal,
            "c_model": c_model,
            "c_payoff": c_payoff,
            "c_probability": c_prob,
            "candidate_id": cid,
            "cell_n": cell_n,
            "class_contributions": contrib,
            "entry_date": candidate["entry_date"],
            "error": error,
            "ev": ev,
            "filled": cid in filled[policy],
            "is_bridge": bool(score["is_bridge"]),
            "label_available_at": candidate["label_available_at"],
            "means_adverse": means,
            "model_id": score["model_id"],
            "model_label_eligible": True,
            "net": net,
            "p_cal": p,
            "p_model": q,
            "payoff_is_lower_bound": bool(candidate["payoff_is_lower_bound"]),
            "policy": policy,
            "prior": prior,
            "realized_class_value": realized,
            "residuals": residuals,
            "right": candidate["right"],
            "scale_usd": scale,
            "scenario": scenario,
            "selected": cid in selected[policy],
            "status": candidate["status"],
            "ticker": candidate["ticker"],
        })

    policy_rows = {policy: [row for row in rows if row["policy"] == policy] for policy in POLICIES}
    partitions = [("TOTAL", "ALL", lambda row: True)]
    partitions += [("ENTRY_MONTH", f"2026{month:02d}", lambda row, m=f"2026{month:02d}": row["entry_date"].startswith(m)) for month in range(1, 10)]
    partitions += [
        ("ENTRY_BLOCK", "H1_2026", lambda row: row["entry_date"] <= "20260630"),
        ("ENTRY_BLOCK", "Q3_PARTIAL_2026", lambda row: row["entry_date"] >= "20260701"),
    ]
    partitions += [("SCENARIO", str(k), lambda row, k=k: int(row["scenario"]) == k) for k in range(5)]
    partitions += [("STATUS", status, lambda row, status=status: row["status"] == status) for status in ("NO_FILL", "OBSERVED_EXIT", "MISSING_EXIT_QUOTE", "MISSING_EXIT_SOURCE")]
    partitions += [("TICKER_RIGHT", key, lambda row, key=key: f"{row['ticker']}:{row['right']}" == key) for key in ("SPY:CALL", "SPY:PUT", "QQQ:CALL", "QQQ:PUT", "SPXW:CALL", "SPXW:PUT")]
    require(len(partitions) == 27, "partition definition count is not 27")

    aggregates: list[dict] = []
    for policy in POLICIES:
        base_rows = policy_rows[policy]
        for universe in ("ALL", "SELECTED", "FILLED"):
            universe_rows = [
                row for row in base_rows
                if universe == "ALL" or (universe == "SELECTED" and row["selected"]) or (universe == "FILLED" and row["filled"])
            ]
            for view in ("conservative_all", "without_lower_bounds"):
                view_rows = universe_rows if view == "conservative_all" else [row for row in universe_rows if not row["payoff_is_lower_bound"]]
                for partition, value, predicate in partitions:
                    members = [row for row in view_rows if predicate(row)]
                    aggregates.append(aggregate(members, policy, universe, view, partition, value, quantities[policy], exit_nets[policy]))
    require(len(aggregates) == 810, "aggregate count is not 810")
    aggregate_keys = {(r["policy"], r["universe"], r["view"], r["partition"], r["value"]) for r in aggregates}
    require(len(aggregate_keys) == 810, "aggregate keys are not unique")

    producer_components = load_jsonl(SOURCE / "components.jsonl")
    producer_aggregates = load_jsonl(SOURCE / "aggregates.jsonl")
    own_component_map = {(r["policy"], r["candidate_id"]): r for r in rows}
    producer_component_map = {(r["policy"], r["candidate_id"]): r for r in producer_components}
    require(own_component_map.keys() == producer_component_map.keys(), "component key mismatch")
    own_aggregate_map = {(r["policy"], r["universe"], r["view"], r["partition"], r["value"]): r for r in aggregates}
    producer_aggregate_map = {(r["policy"], r["universe"], r["view"], r["partition"], r["value"]): r for r in producer_aggregates}
    require(own_aggregate_map.keys() == producer_aggregate_map.keys(), "aggregate key mismatch")

    component_fields = (
        "ev", "net", "error", "c_probability", "c_payoff", "c_model", "c_calibration",
        "realized_class_value", "scale_usd", "alpha",
    )
    component_diffs = defaultdict(float)
    exact_component_mismatches = 0
    for key in sorted(own_component_map):
        ours, theirs = own_component_map[key], producer_component_map[key]
        for field in component_fields:
            component_diffs[field] = max(component_diffs[field], abs(float(ours[field]) - float(theirs[field])))
        for field in ("candidate_id", "policy", "model_id", "entry_date", "ticker", "right", "scenario", "status", "selected", "filled", "payoff_is_lower_bound", "cell_n"):
            exact_component_mismatches += ours[field] != theirs[field]
        for field in ("p_cal", "p_model", "prior", "means_adverse", "class_contributions"):
            component_diffs[field] = max(component_diffs[field], *(abs(float(a)-float(b)) for a,b in zip(ours[field], theirs[field])))

    numeric_aggregate_fields = (
        "sum_ev", "sum_net", "sum_error", "sum_c_probability", "sum_c_payoff", "sum_c_model", "sum_c_calibration",
        "mean_ev", "mean_net", "mean_error", "mean_c_probability", "mean_c_payoff", "mean_c_model", "mean_c_calibration",
        "mae_error", "rmse_error", "mean_abs_c_probability", "mean_abs_c_payoff", "max_abs_residual", "logloss", "brier",
        "sum_quantity_ev", "sum_quantity_net", "exit_net_usd",
    )
    aggregate_diffs = defaultdict(float)
    exact_aggregate_mismatches = 0
    for key in sorted(own_aggregate_map):
        ours, theirs = own_aggregate_map[key], producer_aggregate_map[key]
        for field in ("n", "lower_bound_n", "cell_n_min"):
            exact_aggregate_mismatches += ours[field] != theirs[field]
        for field in numeric_aggregate_fields:
            if field not in ours and field not in theirs:
                continue
            a, b = ours.get(field), theirs.get(field)
            if a is None or b is None:
                exact_aggregate_mismatches += a is not b
            else:
                aggregate_diffs[field] = max(aggregate_diffs[field], abs(float(a)-float(b)))
        for field in ("sum_class_contributions", "cell_n_mean"):
            a, b = ours[field], theirs[field]
            if a is None or b is None:
                exact_aggregate_mismatches += a is not b
            else:
                aggregate_diffs[field] = max(aggregate_diffs[field], *(abs(float(x)-float(y)) for x,y in zip(a,b)))

    comparison = {
        "status": "PASS" if exact_component_mismatches == exact_aggregate_mismatches == 0 and max(component_diffs.values(), default=0.0) <= 1e-8 and max(aggregate_diffs.values(), default=0.0) <= 1e-6 else "FAIL",
        "counts": {"components": len(rows), "aggregates": len(aggregates), "candidate_union": len(candidates), "common_candidates": len(common_ids), "states": len(states)},
        "exact_component_mismatches": exact_component_mismatches,
        "exact_aggregate_mismatches": exact_aggregate_mismatches,
        "max_component_differences": dict(sorted(component_diffs.items())),
        "max_aggregate_differences": dict(sorted(aggregate_diffs.items())),
        "max_probability_reconstruction_residual": max_probability_residual,
    }
    require(comparison["status"] == "PASS", "producer comparison failed")

    findings = []
    for policy in POLICIES:
        for universe in ("ALL", "SELECTED", "FILLED"):
            for block in ("H1_2026", "Q3_PARTIAL_2026"):
                row = own_aggregate_map[(policy, universe, "conservative_all", "ENTRY_BLOCK", block)]
                findings.append({
                    "policy": policy,
                    "block": block,
                    "universe": universe,
                    "n": row["n"],
                    "lower_bound_n": row["lower_bound_n"],
                    "sum_ev": row["sum_ev"],
                    "sum_net": row["sum_net"],
                    "sum_error": row["sum_error"],
                    "sum_c_probability": row["sum_c_probability"],
                    "sum_c_payoff": row["sum_c_payoff"],
                    "sum_c_model": row["sum_c_model"],
                    "sum_c_calibration": row["sum_c_calibration"],
                    **({"sum_quantity_ev": row["sum_quantity_ev"], "sum_quantity_net": row["sum_quantity_net"], "exit_net_usd": row["exit_net_usd"]} if universe == "FILLED" else {}),
                })

    dump_jsonl(OUTPUT / "components_recomputed.jsonl", rows)
    dump_jsonl(OUTPUT / "aggregates_recomputed.jsonl", aggregates)
    dump_json(OUTPUT / "comparison.json", comparison)
    dump_json(OUTPUT / "findings.json", {
        "scope": "DESCRIPTIVE_CONDITIONAL_ERROR_AND_VARIABILITY_NOT_CAUSAL_IDENTIFICATION",
        "rows": findings,
    })

    input_after = {str(path): snapshot(path) for path in sorted(input_paths, key=str)}
    require(input_before == input_after, "input changed during independent reconstruction")
    evidence_files = [
        OUTPUT / "reconstruct_independent.py",
        OUTPUT / "components_recomputed.jsonl",
        OUTPUT / "aggregates_recomputed.jsonl",
        OUTPUT / "comparison.json",
        OUTPUT / "findings.json",
    ]
    receipt = {
        "schema": "ev_components_independent_review_receipt_v1",
        "status": "PASS_INDEPENDENT_RECONSTRUCTION" ,
        "scope": "NO_REFIT_NO_REPLAY_NO_NEW_POLICY_DESCRIPTIVE_NOT_CAUSAL",
        "producer": {
            "manifest": snapshot(SOURCE / "manifest.json"),
            "components": snapshot(SOURCE / "components.jsonl"),
            "aggregates": snapshot(SOURCE / "aggregates.jsonl"),
        },
        "counts": comparison["counts"],
        "comparison": comparison,
        "inputs_before": input_before,
        "inputs_after": input_after,
        "outputs": {path.name: snapshot(path) for path in evidence_files},
        "runtime": {
            "pid": os.getpid(),
            "python": sys.version,
            "cpu_gate": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "thread_env": {key: os.environ.get(key) for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")},
            "resource_gate": gate,
        },
    }
    dump_json(OUTPUT / "receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "counts": receipt["counts"], "receipt_sha256": sha256(OUTPUT / "receipt.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
