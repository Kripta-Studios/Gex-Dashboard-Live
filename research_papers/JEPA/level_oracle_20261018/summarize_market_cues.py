"""Descriptive evidence tables; no outcomes, selection, predictions or fitting."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path

METRICS = (
    "nearest_visible_level_distance_ib", "visible_source_types_inside_band",
    "directional_change_5m_ib", "directional_change_15m_ib",
    "last_closed_5m_body_ib", "target_distance_ib", "stop_distance_ib",
    "target_stop_ratio", "spread_over_premium", "delta", "iv",
    "theta_over_spot", "vega_over_spot", "put_share_observed_oi",
    "put_share_observed_gamma", "rejection_description",
    "acceptance_retest_description",
)
GROUPS = ("all_candidates", "oracle_selected", "model_selected", "neither_selected")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(2**20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def weighted_quantile(values, weights, fraction):
    """Left-continuous weighted empirical quantile, not interpolated units."""
    pairs = sorted(zip(values, weights))
    if not pairs:
        return None
    boundary = math.fsum(weights) * fraction
    cumulative = 0.0
    for value, weight in pairs:
        cumulative += weight
        if cumulative >= boundary:
            return value
    return pairs[-1][0]


def summarize(rows, overlay):
    """Each state receives equal mass within each reported cohort.

    Rows without a cue remain in coverage denominators. Quantiles condition on
    valid values, with coverage reported alongside. Membership is retrospective.
    """
    if overlay.get("model_policy") != "gbt_net__0":
        raise ValueError("Fixed descriptive control must be gbt_net__0")
    by_id = {}
    for row in rows:
        key = row["action_id"]
        if type(key) is not int or key in by_id:
            raise ValueError("Duplicate or invalid action identity")
        if row.get("outcomes_read") is not False:
            raise ValueError("Expected outcome-free evidence")
        if (row.get("ticker"), row.get("date")) != ("SPY", "20250102"):
            raise ValueError("This illustration is fixed to SPY 20250102")
        if type(row["state_i"]) is not int:
            raise ValueError("Invalid state index")
        for name in METRICS:
            metric = row["metrics"][name]
            if type(metric["valid"]) is not bool:
                raise ValueError("Validity must be explicit Boolean")
            value = metric["value"]
            if metric["valid"]:
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                    raise ValueError("Valid evidence must be finite numeric")
            elif value is not None:
                raise ValueError("Missing evidence must remain null")
        by_id[key] = row
    membership = {}
    for row in overlay["rows"]:
        key = row["action_id"]
        if key in membership or type(key) is not int:
            raise ValueError("Duplicate or invalid membership identity")
        if any(type(row[name]) is not bool for name in ("oracle_selected", "model_selected")):
            raise ValueError("Membership must be Boolean")
        membership[key] = row
    if not by_id or set(by_id) != set(membership):
        raise ValueError("Exact nonempty offered-action membership required")
    masks = {
        "all_candidates": lambda item: True,
        "oracle_selected": lambda item: item["oracle_selected"],
        "model_selected": lambda item: item["model_selected"],
        "neither_selected": lambda item: not item["oracle_selected"] and not item["model_selected"],
    }
    groups = {}
    for group in GROUPS:
        chosen = [row for key, row in by_id.items() if masks[group](membership[key])]
        state_counts = Counter(row["state_i"] for row in chosen)
        weights = [1 / state_counts[row["state_i"]] for row in chosen]
        denominator = math.fsum(weights)
        stats = {}
        for name in METRICS:
            good = [(row["metrics"][name]["value"], weight) for row, weight in zip(chosen, weights)
                    if row["metrics"][name]["valid"]]
            values, valid_weights = zip(*good) if good else ([], [])
            stats[name] = {
                "valid_actions": len(good), "missing_actions": len(chosen) - len(good),
                "valid_state_weight_fraction": math.fsum(valid_weights) / denominator if denominator else None,
                "weighted_p25": weighted_quantile(values, valid_weights, 0.25),
                "weighted_median": weighted_quantile(values, valid_weights, 0.5),
                "weighted_p75": weighted_quantile(values, valid_weights, 0.75),
                "positive_state_weight_fraction_among_valid": (
                    math.fsum(weight for value, weight in good if value > 0) / math.fsum(valid_weights)
                    if good else None
                ),
            }
        groups[group] = dict(actions=len(chosen), states=len(state_counts), metrics=stats)
    selected = []
    for key, row in sorted(by_id.items(), key=lambda item: (item[1]["state_i"], item[0])):
        member = membership[key]
        if member["oracle_selected"] or member["model_selected"]:
            selected.append(dict(
                action_id=key, decision_nyse=row["decision_nyse"], state_i=row["state_i"],
                oracle_selected=member["oracle_selected"], model_selected=member["model_selected"],
                is_put=row["metrics"]["is_put"]["value"],
                **{name: row["metrics"][name]["value"] for name in METRICS},
                evidence_tags=";".join(row["evidence_tags"]),
            ))
    return dict(
        status="DESCRIPTIVE_SINGLE_SESSION_NO_PREDICTIVE_OR_ECONOMIC_CLAIM",
        ticker="SPY", date="20250102", groups=groups,
        model_policy=overlay["model_policy"],
        weighting="Equal state mass within each cohort; equal action mass within state",
        source_days=1, selected_actions=selected,
        shared_selected_actions=sum(row["oracle_selected"] and row["model_selected"] for row in membership.values()),
        historical_level_availability_verified=False,
        hypothesis_tests_performed=False, training_performed=False, economic_values_read=False,
    )


def run(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    completion_path = source / "completion.json"
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    if completion["status"] != "COMPLETE_SINGLE_SESSION_DESCRIPTIVE_CUES":
        raise ValueError("Complete producer evidence required")
    expected = ("all_candidate_cues.jsonl", "features_seal.json", "membership_overlay.json")
    for name in expected:
        if sha(source / name) != completion["files"][name]:
            raise ValueError("Producer artifact mismatch: " + name)
    source_hashes = {name: sha(source / name) for name in (*expected, "completion.json")}
    code_before = sha(__file__)
    with (source / expected[0]).open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    overlay = json.loads((source / "membership_overlay.json").read_text(encoding="utf-8"))
    seal = json.loads((source / "features_seal.json").read_text(encoding="utf-8"))
    if overlay["cues_sha256"] != source_hashes[expected[0]] or seal["cues_sha256"] != source_hashes[expected[0]]:
        raise ValueError("Membership or feature seal binds different evidence")
    result = summarize(rows, overlay)
    result.update(source_hashes=source_hashes, source=str(source), code_sha256=code_before)
    if any(sha(source / name) != digest for name, digest in source_hashes.items()) or sha(__file__) != code_before:
        raise ValueError("Input or code changed during summary")
    output.mkdir(parents=True, exist_ok=False)
    (output / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    selected = result["selected_actions"]
    with (output / "selected_action_evidence.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]) if selected else ["action_id"])
        writer.writeheader()
        writer.writerows(selected)
    (output / "completion.json").write_text(json.dumps({
        "status": "COMPLETE_DESCRIPTIVE_SUMMARY", "code_sha256": code_before,
        "source_hashes": source_hashes,
        "outputs": {name: sha(output / name) for name in ("summary.json", "selected_action_evidence.csv")},
    }, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    result = run(arguments.source, arguments.out)
    print(json.dumps({key: {field: value[field] for field in ("actions", "states")}
                      for key, value in result["groups"].items()}))
