"""Sealed, descriptive decomposition of already-published weekly H2 EV scores.

This is a document builder, not a model, replay, selector, or trading system.  It
only evaluates the algebra predeclared in EV_COMPONENT_DIAGNOSTIC_CONTRACT_20261101.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import stat
from collections import defaultdict
from datetime import datetime, time
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


BASE = Path("D:/GexResearchArtifacts/weekly_multiday_20261101")
HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "EV_COMPONENT_DIAGNOSTIC_CONTRACT_20261101.md"
PRODUCER = BASE / "h2_context_adaptation_01"
PRODUCER_MANIFEST = PRODUCER / "manifest.json"
AUDIT = BASE / "h2_context_adaptation_audit_04" / "audit.json"
EXIT = BASE / "h2_context_adaptation_audit_observer_04" / "exit.json"
OUTPUT_DEFAULT = BASE / "ev_components_diagnostic_01"

PRODUCER_MANIFEST_SHA256 = "e8cf5cd4a001cd98cdf29e54cf47bbdf3c34d6652abf34ef7c71fffa0bd97f23"
AUDIT_SHA256 = "9a487fba18504ae4faff2c1dba17d1c000eb237436a09a7fe22747e328cb307a"
EXIT_SHA256 = "5d59d1a3978d8d9aa31c7c3fab567d1ae7e901494aa8efb12377ca65f91de420"
AUDIT_STATUS = "PASS_INDEPENDENT_NUMERIC_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT"
POLICIES = (
    "FROZEN_CONTEXT182",
    "MONTHLY_RAW",
    "WEEKLY_RAW",
    "MONTHLY_GUARDED",
    "WEEKLY_GUARDED",
)
LEDGERS = {
    policy: PRODUCER / f"ledger_{policy.lower()}_adverse.jsonl" for policy in POLICIES
}
CANDIDATE_FILES = (
    BASE / "h2_dataset_v2_01" / "candidates.jsonl",
    BASE / "h2_dataset_v2_extension_2026q3_partial_01" / "candidates.jsonl",
    BASE / "h2_boundary_bridge_01" / "candidates.jsonl",
)
SCORES = PRODUCER / "candidate_scores.jsonl"
STATES = PRODUCER / "states.jsonl"
SUMMARY = PRODUCER / "summary.json"
FROZEN_MODEL = BASE / "h2_ev_v2_01" / "model.json"
FROZEN_MEANS = BASE / "h2_ev_v2_01" / "conditional_means.json"
FROZEN_CALIBRATION = BASE / "h2_context_model_comparison_01" / "context182_calibration.json"

ABS_ROW_TOL = 1e-8
PROB_TOL = 1e-10
AGG_TOL = 1e-6
EXPECTED_CANDIDATES = 3240
EXPECTED_SCORES = 3060
EXPECTED_STATES = 42
EXPECTED_PER_POLICY = 612
EXPECTED_AGGREGATES = 810
NY = ZoneInfo("America/New_York")
FINAL_LABEL_CUTOFF = datetime(2026, 9, 17, 10, 35, tzinfo=NY)
MONTHS = tuple(f"2026{month:02d}" for month in range(1, 10))
SCENARIOS = tuple(str(value) for value in range(5))
STATUSES = ("NO_FILL", "OBSERVED_EXIT", "MISSING_EXIT_QUOTE", "MISSING_EXIT_SOURCE")
TICKER_RIGHT = tuple(f"{ticker}:{right}" for ticker in ("SPY", "QQQ", "SPXW") for right in ("CALL", "PUT"))
PARTITIONS = (
    ("TOTAL", ("ALL",)),
    ("ENTRY_MONTH", MONTHS),
    ("ENTRY_BLOCK", ("H1_2026", "Q3_PARTIAL_2026")),
    ("SCENARIO", SCENARIOS),
    ("STATUS", STATUSES),
    ("TICKER_RIGHT", TICKER_RIGHT),
)
VIEWS = ("conservative_all", "without_lower_bounds")
UNIVERSES = ("ALL", "SELECTED", "FILLED")


class DiagnosticError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosticError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def guard_plain_file(path: Path, roots: Iterable[Path]) -> None:
    require(path.is_absolute(), f"not absolute: {path}")
    chosen: tuple[Path, Path] | None = None
    for root in roots:
        try:
            relative = path.relative_to(root)
            chosen = root, relative
            break
        except ValueError:
            pass
    require(chosen is not None, f"outside declared roots: {path}")
    root, relative = chosen
    cursor = root
    for part in relative.parts:
        require(cursor.exists() and cursor.is_dir(), f"missing ancestor: {cursor}")
        require(not cursor.is_symlink(), f"symlink ancestor refused: {cursor}")
        attributes = getattr(cursor.lstat(), "st_file_attributes", 0)
        require(not attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0), f"reparse ancestor refused: {cursor}")
        cursor /= part
    require(path.exists() and path.is_file(), f"missing file: {path}")
    require(not path.is_symlink(), f"symlink refused: {path}")
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    require(not attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0), f"reparse refused: {path}")
    require(path.resolve(strict=True).is_relative_to(root.resolve(strict=True)), f"resolved outside declared root: {path}")


def guard_output_root(output: Path) -> None:
    require(output == OUTPUT_DEFAULT, "output root must be the contracted root")
    require(not output.exists(), "output already exists")
    parent = output.parent
    require(parent.exists() and parent.is_dir(), "output parent missing")
    require(not BASE.is_symlink(), f"output symlink ancestor: {BASE}")
    base_attributes = getattr(BASE.lstat(), "st_file_attributes", 0)
    require(not base_attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0), f"output reparse ancestor: {BASE}")
    relative = parent.relative_to(BASE)
    cursor = BASE
    for part in (*relative.parts,):
        require(cursor.exists() and cursor.is_dir(), f"output ancestor missing: {cursor}")
        require(not cursor.is_symlink(), f"output symlink ancestor: {cursor}")
        attributes = getattr(cursor.lstat(), "st_file_attributes", 0)
        require(not attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0), f"output reparse ancestor: {cursor}")
        cursor /= part
    require(parent.resolve(strict=True).is_relative_to(BASE.resolve(strict=True)), "output parent escaped BASE")


def pin(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            require(line.strip() != "", f"blank JSONL row {path}:{number}")
            row = json.loads(line)
            require(isinstance(row, dict), f"JSONL object required {path}:{number}")
            rows.append(row)
    return rows


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def close(a: float, b: float, tolerance: float = ABS_ROW_TOL) -> bool:
    return math.isclose(float(a), float(b), abs_tol=tolerance, rel_tol=0.0)


def exact_manifest_pin(manifest: dict[str, Any], path: Path) -> dict[str, Any]:
    absolute = str(path)
    consumed = manifest.get("consumed_payloads", {})
    if absolute in consumed:
        item = consumed[absolute]
    else:
        item = manifest.get("outputs", {}).get(path.name)
    require(isinstance(item, dict), f"payload absent from producer manifest: {path}")
    require(set(item) >= {"bytes", "sha256"}, f"bad manifest pin: {path}")
    return {"path": absolute, "bytes": int(item["bytes"]), "sha256": str(item["sha256"])}


def admit_inputs(contract_sha256: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    roots = (BASE, HERE)
    authorities = (PRODUCER_MANIFEST, AUDIT, EXIT, CONTRACT)
    for path in authorities:
        guard_plain_file(path, roots)
    expected = {
        PRODUCER_MANIFEST: PRODUCER_MANIFEST_SHA256,
        AUDIT: AUDIT_SHA256,
        EXIT: EXIT_SHA256,
        CONTRACT: contract_sha256,
    }
    require(len(contract_sha256) == 64, "contract SHA256 required")
    for path, digest in expected.items():
        require(sha256_file(path) == digest, f"authority hash: {path}")
    audit = read_json(AUDIT)
    require(audit.get("status") == AUDIT_STATUS, "audit not PASS")
    producer_ref = audit.get("inputs", {}).get("producer_manifest", {})
    require(producer_ref.get("sha256") == PRODUCER_MANIFEST_SHA256, "audit producer binding")
    exit_receipt = read_json(EXIT)
    require(exit_receipt.get("exit_code") == 0, "audit exit not zero")
    manifest = read_json(PRODUCER_MANIFEST)
    paths = (*CANDIDATE_FILES, SCORES, STATES, SUMMARY, *LEDGERS.values(), FROZEN_MODEL, FROZEN_MEANS, FROZEN_CALIBRATION)
    snapshots: dict[str, dict[str, Any]] = {}
    for path in paths:
        guard_plain_file(path, roots)
        expected_pin = exact_manifest_pin(manifest, path)
        actual = pin(path)
        require(actual["bytes"] == expected_pin["bytes"] and actual["sha256"] == expected_pin["sha256"], f"payload pin: {path}")
        snapshots[str(path)] = actual
    for path in authorities:
        snapshots[str(path)] = pin(path)
    return manifest, snapshots


def index_unique(rows: list[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        require(isinstance(value, str) and value, f"{label} missing {key}")
        require(value not in output, f"duplicate {label} {value}")
        output[value] = row
    return output


def validate_candidate(row: dict[str, Any]) -> None:
    required = {
        "candidate_id", "ticker", "entry_date", "exit_date", "right", "decision_ask", "status",
        "scenario", "payoff_is_lower_bound", "net_adverse", "label_available_at",
    }
    require(required <= set(row), f"candidate keys {row.get('candidate_id')}")
    require(row["ticker"] in {"SPY", "QQQ", "SPXW"} and row["right"] in {"CALL", "PUT"}, "candidate identity")
    require(row["status"] in STATUSES and row["scenario"] in range(5), "candidate label")
    ask = float(row["decision_ask"])
    require(math.isfinite(ask) and ask > 0, "decision ask")
    require(math.isfinite(float(row["net_adverse"])), "candidate net")
    available = datetime.fromisoformat(row["label_available_at"])
    require(available.tzinfo is not None, "label availability timezone")
    local = available.astimezone(NY)
    expected_date = row["entry_date"] if row["status"] == "NO_FILL" else row["exit_date"]
    require(local.strftime("%Y%m%d") == expected_date and local.time().replace(tzinfo=None) == time(10, 35), "label H2 availability")
    require(local <= FINAL_LABEL_CUTOFF, "label beyond final cutoff")
    lower = bool(row["payoff_is_lower_bound"])
    if row["status"] == "NO_FILL":
        require(row["scenario"] == 0 and not lower and close(row["net_adverse"], 0), "candidate NO_FILL")
    elif row["status"] == "OBSERVED_EXIT":
        require(not lower, "observed lower bound")
    else:
        require(row["scenario"] == 1 and lower, "missing-exit lower bound")


def load_candidates() -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for path in CANDIDATE_FILES:
        for row in read_jsonl(path):
            validate_candidate(row)
            candidate_id = row["candidate_id"]
            require(candidate_id not in output, f"candidate collision {candidate_id}")
            row["_candidate_source"] = path.parent.name
            output[candidate_id] = row
    require(len(output) == EXPECTED_CANDIDATES, "candidate count")
    return output


def validate_probabilities(values: Any, label: str) -> list[float]:
    require(isinstance(values, list) and len(values) == 5, f"{label} length")
    result = [float(value) for value in values]
    require(all(math.isfinite(value) and -PROB_TOL <= value <= 1 + PROB_TOL for value in result), f"{label} range")
    require(close(sum(result), 1.0, PROB_TOL), f"{label} sum")
    return result


def validate_means(means: dict[str, Any], ticker: str, right: str) -> tuple[list[float], list[int]]:
    require(means.get("shrinkage") == 20, "mean shrinkage")
    key = f"{ticker}:{right}"
    cells = means.get("cells", {}).get("adverse", {}).get(key)
    require(isinstance(cells, dict) and set(cells) == set(SCENARIOS), f"mean cell {key}")
    values, support = [], []
    for label in SCENARIOS:
        cell = cells[label]
        value, count = float(cell["mean_y"]), int(cell["n"])
        require(math.isfinite(value) and count >= 0, f"mean value {key}/{label}")
        values.append(value)
        support.append(count)
    return values, support


def build_state_index() -> dict[str, dict[str, Any]]:
    rows = read_jsonl(STATES)
    require(len(rows) == EXPECTED_STATES, "state count")
    output = index_unique(rows, "state_id", "state")
    frozen_model = read_json(FROZEN_MODEL)
    output["FROZEN_CONTEXT182_H1"] = {
        "state_id": "FROZEN_CONTEXT182_H1",
        "prior": frozen_model["train_prior"],
        "calibration": read_json(FROZEN_CALIBRATION),
        "conditional_means": read_json(FROZEN_MEANS),
    }
    return output


def component_row(score: dict[str, Any], candidate: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    for name in ("entry_date", "ticker", "right", "scenario", "payoff_is_lower_bound"):
        require(score.get(name) == candidate.get(name), f"score candidate mismatch {name}: {score.get('candidate_id')}")
    require(score.get("model_id") == state.get("state_id"), "score state mismatch")
    require(bool(score.get("is_bridge")) == (candidate.get("_candidate_source") == "h2_boundary_bridge_01"), "bridge flag mismatch")
    require("20260102" <= score["entry_date"] <= "20260915", "score entry range")
    if state["state_id"] != "FROZEN_CONTEXT182_H1":
        entry_d00 = datetime.strptime(score["entry_date"], "%Y%m%d").replace(tzinfo=NY)
        creation = datetime.strptime(state["creation_date"], "%Y%m%d").replace(tzinfo=NY)
        asof = datetime.fromisoformat(state["asof"])
        require(asof.tzinfo is not None, "state asof timezone")
        require(creation <= entry_d00 and asof.astimezone(NY) <= entry_d00, "future state")
    q = validate_probabilities(score.get("p_model"), "p_model")
    p = validate_probabilities(score.get("p_cal"), "p_cal")
    r = validate_probabilities(state.get("prior"), "prior")
    alpha = float(state.get("calibration", {}).get("selected_alpha"))
    require(math.isfinite(alpha) and 0 <= alpha <= 1, "alpha")
    formula = state["calibration"].get("formula")
    require(formula == "(1-alpha)*p_model+alpha*p_train_prior", "calibration formula")
    for index in range(5):
        require(close(p[index], (1 - alpha) * q[index] + alpha * r[index], PROB_TOL), "calibration identity")
    means, support = validate_means(state["conditional_means"], candidate["ticker"], candidate["right"])
    scale = float(candidate["decision_ask"]) * 100.0
    scenario = int(candidate["scenario"])
    net = float(candidate["net_adverse"])
    ev = scale * math.fsum(p[index] * means[index] for index in range(5))
    realized_class = scale * means[scenario]
    c_probability = ev - realized_class
    c_payoff = realized_class - net
    error = ev - net
    c_model = scale * math.fsum(q[index] * means[index] for index in range(5)) - realized_class
    c_calibration = scale * math.fsum((p[index] - q[index]) * means[index] for index in range(5))
    contributions = [scale * (p[index] - (1.0 if index == scenario else 0.0)) * means[index] for index in range(5)]
    residuals = {
        "error_components": error - (c_probability + c_payoff),
        "probability_components": c_probability - (c_model + c_calibration),
        "class_contributions": c_probability - math.fsum(contributions),
        "stored_ev": ev - float(score["ev_adverse"]),
    }
    require(max(abs(value) for value in residuals.values()) <= ABS_ROW_TOL, f"row identity {score['policy']}/{score['candidate_id']}")
    return {
        "policy": score["policy"], "candidate_id": score["candidate_id"], "model_id": score["model_id"],
        "entry_date": candidate["entry_date"], "ticker": candidate["ticker"], "right": candidate["right"],
        "status": candidate["status"], "scenario": scenario, "payoff_is_lower_bound": bool(candidate["payoff_is_lower_bound"]),
        "label_available_at": candidate["label_available_at"], "is_bridge": bool(score.get("is_bridge")),
        "scale_usd": scale, "p_model": q, "p_cal": p,
        "prior": r, "alpha": alpha, "means_adverse": means, "cell_n": support,
        "ev": ev, "net": net, "error": error, "realized_class_value": realized_class,
        "c_probability": c_probability, "c_payoff": c_payoff, "c_model": c_model,
        "c_calibration": c_calibration, "class_contributions": contributions,
        "residuals": residuals,
    }


def ledger_sets(
    policy: str,
    rows: list[dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    score_models: dict[str, str] | None = None,
) -> dict[str, Any]:
    require(all(row.get("policy") == policy and row.get("cost") == "adverse" for row in rows), f"ledger identity {policy}")
    selected: set[str] = set()
    entries: dict[str, dict[str, Any]] = {}
    exits: dict[str, dict[str, Any]] = {}
    for row in rows:
        event = row.get("event")
        candidate_id = row.get("candidate_id")
        require(event in {"WAIT", "NO_OPPORTUNITY", "NO_FILL", "CAPITAL_BLOCKED", "ENTRY", "EXIT"}, f"ledger event {policy}/{event}")
        if event in {"WAIT", "NO_OPPORTUNITY"}:
            require(candidate_id is None and row.get("model_id") is None, f"non-candidate event identity {policy}")
        else:
            require(candidate_id in candidates, f"ledger candidate {policy}/{candidate_id}")
            if score_models is not None:
                require(row.get("model_id") == score_models.get(candidate_id), f"ledger score model {policy}/{candidate_id}")
        if event in {"ENTRY", "NO_FILL", "CAPITAL_BLOCKED"}:
            require(candidate_id not in selected, f"selected ledger ID {policy}/{candidate_id}")
            selected.add(candidate_id)
        if event == "ENTRY":
            require(candidate_id not in entries, f"duplicate ENTRY {policy}/{candidate_id}")
            entries[candidate_id] = row
        elif event == "EXIT":
            require(candidate_id not in exits, f"duplicate EXIT {policy}/{candidate_id}")
            exits[candidate_id] = row
    require(set(entries) == set(exits), f"ENTRY/EXIT closure {policy}")
    for candidate_id, entry in entries.items():
        exit_row = exits[candidate_id]
        require(entry.get("model_id") == exit_row.get("model_id"), f"ledger model closure {candidate_id}")
        require(int(entry["quantity"]) == int(exit_row["quantity"]) and int(entry["quantity"]) > 0, f"ledger quantity {candidate_id}")
        expected = int(entry["quantity"]) * float(candidates[candidate_id]["net_adverse"])
        require(close(exit_row["net_usd"], expected, AGG_TOL), f"ledger net {candidate_id}")
    return {"selected": selected, "filled": set(entries), "entries": entries, "exits": exits, "rows": rows}


def probability_metrics(rows: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    if not rows:
        return None, None
    logloss = -math.fsum(math.log(max(min(row["p_cal"][row["scenario"]], 1.0), 1e-12)) for row in rows) / len(rows)
    brier = math.fsum(math.fsum((row["p_cal"][index] - (1 if index == row["scenario"] else 0)) ** 2 for index in range(5)) for row in rows) / len(rows)
    return logloss, brier


def partition_value(row: dict[str, Any], partition: str) -> str:
    if partition == "TOTAL":
        return "ALL"
    if partition == "ENTRY_MONTH":
        return row["entry_date"][:6]
    if partition == "ENTRY_BLOCK":
        return "H1_2026" if row["entry_date"] <= "20260630" else "Q3_PARTIAL_2026"
    if partition == "SCENARIO":
        return str(row["scenario"])
    if partition == "STATUS":
        return row["status"]
    if partition == "TICKER_RIGHT":
        return f"{row['ticker']}:{row['right']}"
    raise DiagnosticError(f"unknown partition {partition}")


def aggregate_cell(rows: list[dict[str, Any]], base: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    fields = ("ev", "net", "error", "c_probability", "c_payoff", "c_model", "c_calibration")
    output = dict(base)
    output["n"] = len(rows)
    output["lower_bound_n"] = sum(row["payoff_is_lower_bound"] for row in rows)
    for name in fields:
        total = math.fsum(row[name] for row in rows)
        output[f"sum_{name}"] = total
        output[f"mean_{name}"] = total / len(rows) if rows else None
    output["mae_error"] = math.fsum(abs(row["error"]) for row in rows) / len(rows) if rows else None
    output["rmse_error"] = math.sqrt(math.fsum(row["error"] ** 2 for row in rows) / len(rows)) if rows else None
    output["mean_abs_c_probability"] = math.fsum(abs(row["c_probability"]) for row in rows) / len(rows) if rows else None
    output["mean_abs_c_payoff"] = math.fsum(abs(row["c_payoff"]) for row in rows) / len(rows) if rows else None
    output["sum_class_contributions"] = [math.fsum(row["class_contributions"][index] for row in rows) for index in range(5)]
    output["cell_n_min"] = [min((row["cell_n"][index] for row in rows), default=None) for index in range(5)]
    output["cell_n_mean"] = [math.fsum(row["cell_n"][index] for row in rows) / len(rows) if rows else None for index in range(5)]
    output["max_abs_residual"] = max((abs(value) for row in rows for value in row["residuals"].values()), default=0.0)
    output["logloss"], output["brier"] = probability_metrics(rows)
    if base["universe"] == "FILLED":
        output["sum_quantity_ev"] = math.fsum(int(ledger["entries"][row["candidate_id"]]["quantity"]) * row["ev"] for row in rows)
        output["sum_quantity_net"] = math.fsum(int(ledger["entries"][row["candidate_id"]]["quantity"]) * row["net"] for row in rows)
        output["exit_net_usd"] = math.fsum(float(ledger["exits"][row["candidate_id"]]["net_usd"]) for row in rows)
        require(close(output["sum_quantity_net"], output["exit_net_usd"], AGG_TOL), "filled net reconciliation")
    return output


def build_aggregates(components: list[dict[str, Any]], ledgers: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    by_policy = {policy: [row for row in components if row["policy"] == policy] for policy in POLICIES}
    output: list[dict[str, Any]] = []
    for policy in POLICIES:
        ledger = ledgers[policy]
        universe_ids = {"ALL": {row["candidate_id"] for row in by_policy[policy]}, "SELECTED": ledger["selected"], "FILLED": ledger["filled"]}
        for universe in UNIVERSES:
            universe_rows = [row for row in by_policy[policy] if row["candidate_id"] in universe_ids[universe]]
            for view in VIEWS:
                viewed = [row for row in universe_rows if view == "conservative_all" or not row["payoff_is_lower_bound"]]
                for partition, values in PARTITIONS:
                    for value in values:
                        rows = [row for row in viewed if partition_value(row, partition) == value]
                        output.append(aggregate_cell(rows, {"policy": policy, "universe": universe, "view": view, "partition": partition, "value": value}, ledger))
    require(len(output) == EXPECTED_AGGREGATES, "aggregate count")
    return output


def validate_partition_reconciliation(aggregates: list[dict[str, Any]]) -> dict[str, Any]:
    additive = (
        "n", "lower_bound_n", "sum_ev", "sum_net", "sum_error", "sum_c_probability",
        "sum_c_payoff", "sum_c_model", "sum_c_calibration",
    )
    index = {(row["policy"], row["universe"], row["view"], row["partition"], row["value"]): row for row in aggregates}
    require(len(index) == len(aggregates), "duplicate aggregate cell")
    checks = 0
    for policy in POLICIES:
        for universe in UNIVERSES:
            for view in VIEWS:
                total = index[(policy, universe, view, "TOTAL", "ALL")]
                require(close(math.fsum(total["sum_class_contributions"]), total["sum_c_probability"], AGG_TOL), "TOTAL contribution reconciliation")
                for partition, values in PARTITIONS[1:]:
                    cells = [index[(policy, universe, view, partition, value)] for value in values]
                    fields = additive + (("sum_quantity_ev", "sum_quantity_net", "exit_net_usd") if universe == "FILLED" else ())
                    for cell in cells:
                        require(close(math.fsum(cell["sum_class_contributions"]), cell["sum_c_probability"], AGG_TOL), f"cell contribution {partition}/{cell['value']}")
                    for field in fields:
                        if field in {"n", "lower_bound_n"}:
                            require(sum(int(cell[field]) for cell in cells) == int(total[field]), f"partition count {partition}/{field}")
                        else:
                            require(close(math.fsum(float(cell[field]) for cell in cells), float(total[field]), AGG_TOL), f"partition sum {partition}/{field}")
                    for class_index in range(5):
                        subtotal = math.fsum(float(cell["sum_class_contributions"][class_index]) for cell in cells)
                        require(close(subtotal, float(total["sum_class_contributions"][class_index]), AGG_TOL), f"partition contribution {partition}/{class_index}")
                    checks += 1
    return {"families_checked": checks, "exhaustive_disjoint_by_construction": True}


def validate_common_score_ids(components: list[dict[str, Any]]) -> set[str]:
    sets = {
        policy: {row["candidate_id"] for row in components if row["policy"] == policy}
        for policy in POLICIES
    }
    require(all(len(values) == EXPECTED_PER_POLICY for values in sets.values()), "score policy ID count")
    common = sets[POLICIES[0]]
    require(all(values == common for values in sets.values()), "score policies do not share exact candidate IDs")
    return common


def reconcile_summary(summary: dict[str, Any], components: list[dict[str, Any]], ledgers: dict[str, dict[str, Any]], aggregates: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    totals = {(row["policy"], row["universe"], row["view"]): row for row in aggregates if row["partition"] == "TOTAL"}
    for policy in POLICIES:
        published = summary["policies"][policy]
        require(set(published["selected_ids"]) == ledgers[policy]["selected"], f"summary selected {policy}")
        require(set(published["filled_ids"]) == ledgers[policy]["filled"], f"summary filled {policy}")
        for universe, summary_key in (("ALL", "all"), ("SELECTED", "selected")):
            for view, suffix in (("conservative_all", ""), ("without_lower_bounds", "_observed_only")):
                diagnostic = totals[(policy, universe, view)]
                reference = published["probability_ev"][summary_key + suffix]
                require(diagnostic["n"] == reference["n"], f"summary n {policy}/{universe}/{view}")
                require(close(diagnostic["logloss"], reference["logloss"], AGG_TOL), f"summary logloss {policy}/{universe}/{view}")
                require(close(diagnostic["brier"], reference["brier"], AGG_TOL), f"summary brier {policy}/{universe}/{view}")
        filled = totals[(policy, "FILLED", "conservative_all")]
        reference_net = float(published["economics"]["adverse"]["net_usd"])
        require(close(filled["exit_net_usd"], reference_net, AGG_TOL), f"summary adverse net {policy}")
        event_counts: dict[str, int] = defaultdict(int)
        reason_counts: dict[str, int] = defaultdict(int)
        for event in ledgers[policy]["rows"]:
            event_counts[str(event["event"])] += 1
            if event.get("reason") is not None:
                reason_counts[str(event["reason"])] += 1
        result[policy] = {
            "selected": len(ledgers[policy]["selected"]), "filled": len(ledgers[policy]["filled"]),
            "adverse_exit_net_usd": filled["exit_net_usd"],
            "event_counts": dict(sorted(event_counts.items())), "reason_counts": dict(sorted(reason_counts.items())),
        }
    return result


def closing_rehash(snapshots: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    closing: dict[str, dict[str, Any]] = {}
    for name, original in snapshots.items():
        path = Path(name)
        current = pin(path)
        require(current["bytes"] == original["bytes"] and current["sha256"] == original["sha256"], f"input changed: {path}")
        closing[name] = current
    return closing


def run(output: Path, contract_sha256: str, implementation_sha256: str) -> dict[str, Any]:
    guard_output_root(output)
    require(sha256_file(Path(__file__).resolve()) == implementation_sha256, "implementation pin")
    _manifest, snapshots = admit_inputs(contract_sha256)
    snapshots[str(Path(__file__).resolve())] = pin(Path(__file__).resolve())
    candidates = load_candidates()
    states = build_state_index()
    scores = read_jsonl(SCORES)
    require(len(scores) == EXPECTED_SCORES, "score count")
    seen: set[tuple[str, str]] = set()
    counts = defaultdict(int)
    components: list[dict[str, Any]] = []
    policy_order = {policy: index for index, policy in enumerate(POLICIES)}
    for score in sorted(scores, key=lambda row: (policy_order.get(row.get("policy"), 999), str(row.get("candidate_id")))):
        policy, candidate_id = score.get("policy"), score.get("candidate_id")
        require(policy in POLICIES and candidate_id in candidates, "score identity")
        key = (policy, candidate_id)
        require(key not in seen, f"duplicate score {key}")
        seen.add(key)
        require(score.get("model_id") in states, "score model")
        components.append(component_row(score, candidates[candidate_id], states[score["model_id"]]))
        counts[policy] += 1
    require(all(counts[policy] == EXPECTED_PER_POLICY for policy in POLICIES), "score policy counts")
    validate_common_score_ids(components)
    model_maps = {
        policy: {row["candidate_id"]: row["model_id"] for row in components if row["policy"] == policy}
        for policy in POLICIES
    }
    ledgers = {
        policy: ledger_sets(policy, read_jsonl(path), candidates, model_maps[policy])
        for policy, path in LEDGERS.items()
    }
    for row in components:
        row["selected"] = row["candidate_id"] in ledgers[row["policy"]]["selected"]
        row["filled"] = row["candidate_id"] in ledgers[row["policy"]]["filled"]
    summary = read_json(SUMMARY)
    aggregates = build_aggregates(components, ledgers)
    partition_reconciliation = validate_partition_reconciliation(aggregates)
    reconciliation = reconcile_summary(summary, components, ledgers, aggregates)
    reconciliation["partitions"] = partition_reconciliation
    max_residual = max(abs(value) for row in components for value in row["residuals"].values())
    report = {
        "schema": "weekly_ev_component_diagnostic_report_v1",
        "status": "COMPLETE_SEEN_DEVELOPMENT_DESCRIPTIVE_NOT_PROMOTED",
        "scope": {"candidate_rows": len(candidates), "score_rows": len(components), "aggregate_rows": len(aggregates), "cost": "adverse"},
        "interpretation": {
            "evidence": "signed algebraic decomposition of sealed scores and conservative/observed payoff proxies",
            "limitations": "realized-class value is posterior diagnostic information; components do not identify statistical causes and are not trading signals",
            "monthly_convention": "entry month; September is partial and differs from economic exit-month gates",
        },
        "max_abs_row_residual": max_residual,
        "reconciliation": reconciliation,
        "flags": {"models_fit": False, "replay_run": False, "inference_run": False, "selection_changed": False, "production_changed": False, "seen_development": True, "technical_ready": False, "promotion_approved": False},
    }
    closing_rehash(snapshots)
    output.mkdir(parents=False, exist_ok=False)
    write_jsonl(output / "components.jsonl", components)
    write_jsonl(output / "aggregates.jsonl", aggregates)
    write_json(output / "reconciliation.json", reconciliation)
    write_json(output / "report.json", report)
    outputs = {path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in sorted(output.iterdir())}
    closing = closing_rehash(snapshots)
    final_manifest = {
        "schema": "weekly_ev_component_diagnostic_manifest_v1",
        "status": report["status"], "inputs_before": snapshots, "inputs_after": closing,
        "producer_manifest": {"path": str(PRODUCER_MANIFEST), "sha256": PRODUCER_MANIFEST_SHA256},
        "implementation": {"path": str(Path(__file__).resolve()), "sha256": implementation_sha256},
        "outputs": outputs, "flags": report["flags"],
    }
    write_json(output / "manifest.json", final_manifest)
    return final_manifest


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--execute-reviewed-diagnostic", action="store_true")
    value.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    value.add_argument("--contract-sha256")
    value.add_argument("--implementation-sha256")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.execute_reviewed_diagnostic:
        print(json.dumps({"status": "READY_NOT_EXECUTED", "output": str(args.output), "scope": "sealed adverse EV component diagnostic; no fit/replay/inference"}, sort_keys=True))
        return 0
    require(args.contract_sha256 is not None and args.implementation_sha256 is not None, "review pins required")
    result = run(args.output.resolve(), args.contract_sha256, args.implementation_sha256)
    print(json.dumps({"status": result["status"], "manifest": str(args.output / "manifest.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
