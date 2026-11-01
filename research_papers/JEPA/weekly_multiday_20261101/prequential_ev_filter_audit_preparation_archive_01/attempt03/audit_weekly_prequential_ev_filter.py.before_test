"""Independent audit for the prequential EV selection/abstention overlay.

The auditor never imports the producer or the original replay helper.  It may
load the previously reviewed economic-auditor module by exact hash and uses
only its pure risk/replay/metric functions.  No estimator or market-data parser
is present in this module.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


WEEK = Path(__file__).resolve().parent
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
PRODUCER_ROOT = BASE / "prequential_ev_filter_01"
PRODUCER_OBSERVER = BASE / "prequential_ev_filter_observer_01"
OUTPUT = BASE / "prequential_ev_filter_audit_01"

CONTRACT = WEEK / "PREQUENTIAL_EV_FILTER_CONTRACT_20261101.md"
CONTRACT_SHA256 = "0b81b77b0f058248e5e55b004c263dd0f97e5089cabb96336ae5c74f622312aa"
PURE_AUDITOR = WEEK / "audit_weekly_context_models.py"
PURE_AUDITOR_SHA256 = "3eb6b9795ad260971435259858f86d3c00111bcc141973faf986411d4a68ad99"
PRODUCER_REPLAY = WEEK / "replay_equal_risk_frozen.py"
PRODUCER_REPLAY_SHA256 = "e4f42a9fa65120939cf5e131911c8f2990a9cd33d21ae036fa98d9eb816d5b9d"

ADAPTATION_ROOT = BASE / "h2_context_adaptation_01"
ADAPTATION_MANIFEST_SHA256 = "e8cf5cd4a001cd98cdf29e54cf47bbdf3c34d6652abf34ef7c71fffa0bd97f23"
ADAPTATION_MANIFEST_BYTES = 17599
ADAPTATION_AUDIT = BASE / "h2_context_adaptation_audit_04" / "audit.json"
ADAPTATION_AUDIT_SHA256 = "9a487fba18504ae4faff2c1dba17d1c000eb237436a09a7fe22747e328cb307a"
ADAPTATION_EXIT = BASE / "h2_context_adaptation_audit_observer_04" / "exit.json"
ADAPTATION_EXIT_SHA256 = "5d59d1a3978d8d9aa31c7c3fab567d1ae7e901494aa8efb12377ca65f91de420"
DIAGNOSTIC = WEEK / "EV_COMPONENT_DIAGNOSTIC_RESULT_20261101.md"
DIAGNOSTIC_SHA256 = "980611e26c3badf945d95d9669b53b5f9e99ac11d462629e88a3259969d0832c"
ACCEPTANCE = WEEK / "USER_MONTHLY_PROFITABILITY_ACCEPTANCE_20261101.md"
ACCEPTANCE_SHA256 = "806f7728a2ad434bc08929d3715f307455bd37862ae4c19a2cd2cc1d64a5ee5b"

DATASET_H1 = BASE / "h2_dataset_v2_01"
DATASET_Q3 = BASE / "h2_dataset_v2_extension_2026q3_partial_01"
BRIDGE = BASE / "h2_boundary_bridge_01"
TICKERS = ("SPY", "QQQ", "SPXW")
RIGHTS = ("CALL", "PUT")
PARENTS = ("FROZEN_CONTEXT182", "MONTHLY_RAW", "WEEKLY_RAW")
VARIANTS = ("CONTROL", "FILTER")
COSTS = ("base", "adverse")
FIRST_DATE, LAST_DATE, LAST_ENTRY = "20260102", "20260917", "20260915"
NY = ZoneInfo("America/New_York")
MIN_HISTORY = 20
SHRINKAGE = 20
BUFFER_Z = 1.645
EXPECTED_SESSIONS = 178
EXPECTED_ALL_SESSIONS = 930
EXPECTED_COVERAGE_IDENTITIES = 2790
EXPECTED_ALL_CANDIDATES = 3240
EXPECTED_CANDIDATES = 612
EXPECTED_SCORES = 3060
EXPECTED_USED_SCORES = 1836
MONTHS = tuple(f"2026{month:02d}" for month in range(1, 10))
COMPLETE_MONTHS = MONTHS[:8]
SUMMARY_FLAGS = {
    "models_fit": False, "inference_run": False, "raw_read": False,
    "api_read": False, "broker_read": False, "future_labels_used": False,
    "scores_changed": False, "replay_run": True, "seen_development": True,
    "technical_ready": False, "promotion_approved": False,
    "production_changed": False,
}
ADAPTATION_FLAGS = {
    "models_fit": True, "seen_development": True, "api_read": False,
    "broker_read": False, "frozen_fit": False, "future_labels_used": False,
    "production_changed": False, "promotion_approved": False, "raw_read": False,
}
ADAPTATION_AUDIT_FLAGS = {
    "saved_weights_used": True, "seen_development": True, "api_read": False,
    "broker_read": False, "fit_performed": False, "producer_imported": False,
    "production_changed": False, "promotion_approved": False, "raw_read": False,
}

SCORE_FIELDS = {
    "candidate_id", "entry_date", "ev_adverse", "ev_base", "is_bridge", "model_id",
    "p_cal", "p_model", "payoff_is_lower_bound", "policy", "right", "scenario", "ticker",
}
CANDIDATE_FIELDS = {
    "candidate_id", "ticker", "entry_date", "exit_date", "expiration", "strike", "right",
    "features", "decision_ask", "source_pins", "entry_ask", "exit_bid", "status",
    "label_available_at", "scenario", "payoff_is_lower_bound", "net_base", "net_adverse",
    "entry_debit_base", "entry_debit_adverse",
}


class PrequentialAuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PrequentialAuditError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def plain(path: Path, label: str, *, exists: bool = True, regular: bool = False) -> Path:
    absolute = Path(os.path.abspath(path))
    if exists:
        require(absolute.exists(), f"missing {label}")
    current = absolute if absolute.exists() else absolute.parent
    while True:
        if current.exists():
            attrs = getattr(current.lstat(), "st_file_attributes", 0)
            require(not current.is_symlink() and not attrs & 0x400, f"link/reparse {label}")
        if current.parent == current:
            break
        current = current.parent
    if regular:
        require(absolute.is_file(), f"regular file {label}")
    return absolute


def pin(path: Path) -> dict[str, Any]:
    path = plain(path, str(path), regular=True)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def verify(path: Path, expected: dict[str, Any], label: str) -> None:
    actual = pin(path)
    require(isinstance(expected, dict) and set(expected) >= {"bytes", "sha256"}, f"pin shape {label}")
    require(actual["bytes"] == expected["bytes"] and actual["sha256"] == expected["sha256"], f"pin {label}")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(plain(path, str(path), regular=True).read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    with plain(path, str(path), regular=True).open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL {path}:{number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"JSONL object {path}:{number}")
            values.append(value)
    return values


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def guard_output(path: Path) -> Path:
    value = plain(path, "audit output", exists=False)
    require(value.is_absolute() and not value.exists(), "exclusive audit output")
    parent = plain(value.parent, "audit output parent")
    require(parent.is_dir(), "audit output parent directory")
    forbidden = (
        PRODUCER_ROOT, PRODUCER_OBSERVER, ADAPTATION_ROOT, ADAPTATION_AUDIT.parent,
        ADAPTATION_EXIT.parent, DATASET_H1, DATASET_Q3, BRIDGE, WEEK,
    )
    require(not any(value == root or value.is_relative_to(root) for root in forbidden), "audit output nested in input root")
    return value


def import_pure_auditor() -> Any:
    path = plain(PURE_AUDITOR, "pure economic auditor", regular=True)
    require(sha256_file(path) == PURE_AUDITOR_SHA256, "pure auditor authority")
    spec = importlib.util.spec_from_file_location("prequential_pure_economic_auditor", path)
    require(spec is not None and spec.loader is not None, "pure auditor import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(sha256_file(path) == PURE_AUDITOR_SHA256, "pure auditor changed during import")
    allowed = ("replay_risk", "book_metrics")
    require(all(callable(getattr(module, name, None)) for name in allowed), "pure helper interface")
    return module


def midnight(day: str) -> datetime:
    return datetime.strptime(day, "%Y%m%d").replace(tzinfo=NY)


def label_time(row: dict[str, Any]) -> datetime:
    value = datetime.fromisoformat(row["label_available_at"])
    require(value.tzinfo is not None, "aware label time")
    return value


def finite(value: Any, label: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)), f"finite {label}")
    return float(value)


def normalize_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    require(set(raw) == CANDIDATE_FIELDS, "candidate schema")
    row = dict(raw)
    require(row["ticker"] in TICKERS and row["right"] in RIGHTS, "candidate identity")
    require(row["candidate_id"] == f"{row['ticker']}:{row['entry_date']}:{row['expiration']}:{row['right']}", "candidate ID")
    require(row["entry_date"] < row["exit_date"] < row["expiration"], "candidate calendar")
    ask = finite(row["decision_ask"], "decision ask")
    require(ask > 0 and label_time(row).strftime("%Y%m%d") in {row["entry_date"], row["exit_date"]}, "candidate timing")
    require(row["status"] in {"OBSERVED_EXIT", "NO_FILL", "MISSING_EXIT_QUOTE", "MISSING_EXIT_SOURCE"}, "candidate status")
    require(label_time(row) < midnight("20260918"), "candidate label final cutoff")
    for name in ("net_base", "net_adverse", "entry_debit_base", "entry_debit_adverse"):
        finite(row[name], name)
    require(type(row["scenario"]) is int and 0 <= row["scenario"] < 5, "candidate scenario")
    require(isinstance(row["payoff_is_lower_bound"], bool), "lower bound flag")
    return row


def normalize_score(raw: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    require(set(raw) == SCORE_FIELDS, "score schema")
    row = dict(raw)
    require(row["policy"] in (*PARENTS, "MONTHLY_GUARDED", "WEEKLY_GUARDED"), "score policy")
    require(FIRST_DATE <= row["entry_date"] <= LAST_ENTRY, "score date scope")
    require(row["candidate_id"] == candidate["candidate_id"] and row["entry_date"] == candidate["entry_date"], "score identity")
    require(row["ticker"] == candidate["ticker"] and row["right"] == candidate["right"], "score side")
    require(row["scenario"] == candidate["scenario"] and row["payoff_is_lower_bound"] == candidate["payoff_is_lower_bound"], "score label")
    for name in ("ev_base", "ev_adverse"):
        finite(row[name], name)
    for name in ("p_model", "p_cal"):
        values = row[name]
        require(isinstance(values, list) and len(values) == 5, f"{name} shape")
        checked = [finite(value, f"{name} value") for value in values]
        require(all(0 <= value <= 1 for value in checked), f"{name} values")
        require(math.isclose(math.fsum(map(float, values)), 1.0, abs_tol=1e-10, rel_tol=0), f"{name} sum")
    require(isinstance(row["model_id"], str) and isinstance(row["is_bridge"], bool), "score metadata")
    return row


def common_calendar(h1: dict[str, Any], q3: dict[str, Any]) -> list[str]:
    calendar = [*h1.get("calendar", []), *q3.get("calendar", [])]
    require(len(calendar) == EXPECTED_COVERAGE_IDENTITIES, "calendar identity count")
    identities = {(item.get("ticker"), item.get("date")) for item in calendar}
    require(len(identities) == EXPECTED_COVERAGE_IDENTITIES, "calendar uniqueness")
    dates = sorted({date for ticker, date in identities if ticker in TICKERS and isinstance(date, str)})
    require(identities == {(ticker, date) for ticker in TICKERS for date in dates} and len(dates) == EXPECTED_ALL_SESSIONS, "common calendar")
    evaluation = [day for day in dates if FIRST_DATE <= day <= LAST_DATE]
    require(len(evaluation) == EXPECTED_SESSIONS, "evaluation sessions")
    return evaluation


def merge_coverage(h1: dict[str, Any], q3: dict[str, Any], overlay: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [*h1.get("rows", []), *q3.get("rows", [])]
    index = {(row["ticker"], row["entry_date"]): dict(row) for row in rows}
    require(len(index) == len(rows) == EXPECTED_COVERAGE_IDENTITIES, "coverage union")
    replacements = overlay.get("rows")
    require(isinstance(replacements, list) and len(replacements) == 6, "bridge replacements")
    expected = {(ticker, day) for ticker in TICKERS for day in ("20260629", "20260630")}
    require({(row.get("ticker"), row.get("entry_date")) for row in replacements} == expected, "bridge scope")
    for row in replacements:
        key = (row["ticker"], row["entry_date"])
        require(index[key].get("status") == "HORIZON_OUTSIDE_CALENDAR", "bridge replaces horizon")
        if row["entry_date"] == "20260629":
            require(row.get("status") == "CANDIDATES_BUILT" and row.get("exit_date") == "20260701", "June29 bridge")
        else:
            require(row.get("status") == "NO_SERIES" and row.get("exit_date") == "20260702", "June30 bridge")
        index[key] = dict(row)
    return list(index.values())


def raw_intentions(parent: str, rows: list[dict[str, Any]], scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    require(parent in PARENTS, "parent")
    candidates = {row["candidate_id"]: row for row in rows}
    require(len(candidates) == len(rows), "candidate IDs")
    selected_scores = [row for row in scores if row["policy"] == parent]
    require(len(selected_scores) == EXPECTED_CANDIDATES, "parent score count")
    require({row["candidate_id"] for row in selected_scores} == set(candidates), "parent score universe")
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for score in selected_scores:
        by_group[(score["entry_date"], score["ticker"])].append(score)
    intentions: list[dict[str, Any]] = []
    for (day, ticker), values in sorted(by_group.items()):
        require(1 <= len(values) <= 2 and len({row["right"] for row in values}) == len(values), "group side uniqueness")
        best = max(float(row["ev_adverse"]) for row in values)
        matches = [row for row in values if float(row["ev_adverse"]) == best]
        if best <= 0 or len(matches) != 1:
            continue
        score = matches[0]
        candidate = candidates[score["candidate_id"]]
        scale = finite(candidate["decision_ask"], "intention decision ask") * 100
        require(scale > 0, "intention scale")
        net = finite(candidate["net_adverse"], "intention net")
        residual = (net - best) / scale
        require(math.isfinite(residual), "normalized residual")
        intentions.append({
            "parent": parent, "candidate_id": score["candidate_id"], "entry_date": day,
            "ticker": ticker, "right": score["right"], "model_id": score["model_id"],
            "ev_base_raw": float(score["ev_base"]), "ev_adverse_raw": best,
            "decision_ask": float(candidate["decision_ask"]), "scale_usd": scale,
            "net_base": float(candidate["net_base"]), "net_adverse": net,
            "status": candidate["status"], "scenario": candidate["scenario"],
            "label_available_at": candidate["label_available_at"],
            "payoff_is_lower_bound": candidate["payoff_is_lower_bound"],
            "normalized_residual": residual,
        })
    return intentions


def filter_state(day: str, intentions: list[dict[str, Any]]) -> dict[str, Any]:
    history = sorted(
        (row for row in intentions if row["entry_date"] < day and datetime.fromisoformat(row["label_available_at"]) < midnight(day)),
        key=lambda row: (row["entry_date"], row["ticker"], row["candidate_id"]),
    )
    n = len(history)
    ids = [row["candidate_id"] for row in history]
    if n < MIN_HISTORY:
        return {"date": day, "history_ids": ids, "n": n, "mean": None, "s": None, "w": None, "correction": 0.0, "buffer": 0.0, "state": "WARMUP_RAW"}
    residuals = [float(row["normalized_residual"]) for row in history]
    mean = math.fsum(residuals) / n
    s = math.sqrt(math.fsum((value - mean) ** 2 for value in residuals) / (n - 1))
    w = n / (n + SHRINKAGE)
    correction = min(0.0, w * mean)
    buffer = BUFFER_Z * w * s / math.sqrt(n)
    require(all(math.isfinite(value) for value in (mean, s, w, correction, buffer)), "finite filter state")
    require(correction <= 0 and buffer >= 0, "one-sided filter state")
    return {"date": day, "history_ids": ids, "n": n, "mean": mean, "s": s, "w": w, "correction": correction, "buffer": buffer, "state": "ACTIVE_FILTER"}


def gate_intention(intention: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    ev_raw, scale = float(intention["ev_adverse_raw"]), float(intention["scale_usd"])
    ev_gate = ev_raw + scale * (float(state["correction"]) - float(state["buffer"]))
    require(math.isfinite(ev_gate) and ev_gate <= ev_raw, "gate score one-sided")
    accepted = ev_raw > 0 and ev_gate > 0
    return {**intention, "history_n": state["n"], "filter_state": state["state"], "correction": state["correction"], "buffer": state["buffer"], "ev_gate": ev_gate, "accepted": accepted, "reason": "FILTER_ACCEPT" if accepted else "FILTER_GATE_NOT_POSITIVE"}


def reconstruct_decision_rows(
    parent: str, intentions: list[dict[str, Any]], scores: list[dict[str, Any]], sessions: list[str],
) -> list[dict[str, Any]]:
    score_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for score in scores:
        if score["policy"] == parent:
            score_groups[(score["entry_date"], score["ticker"])].append(score)
    intention_index = {row["candidate_id"]: row for row in intentions}
    output = []
    for day in (value for value in sessions if value <= LAST_ENTRY):
        state = filter_state(day, intentions)
        state_fields = {key: state[key] for key in ("history_ids", "n", "mean", "s", "w", "correction", "buffer", "state")}
        for ticker in TICKERS:
            values = score_groups.get((day, ticker), [])
            winner = None
            raw_reason = "NO_OPPORTUNITY"
            if values:
                best = max(float(row["ev_adverse"]) for row in values)
                matches = [row for row in values if float(row["ev_adverse"]) == best]
                if best <= 0:
                    raw_reason = "EV_NOT_POSITIVE"
                elif len(matches) != 1:
                    raw_reason = "EV_TIE_WAIT"
                else:
                    raw_reason, winner = "EV_TOP1", matches[0]
            if winner is None:
                output.append({"parent": parent, "entry_date": day, "ticker": ticker, **state_fields, "raw_winner_id": None, "raw_reason": raw_reason, "ev_raw": None, "ev_gate": None, "accepted": False, "filter_reason": raw_reason})
                continue
            intention = intention_index.get(winner["candidate_id"])
            require(intention is not None, "winner intention")
            gated = gate_intention(intention, state)
            output.append({
                "parent": parent, "entry_date": day, "ticker": ticker, **state_fields,
                "raw_winner_id": winner["candidate_id"], "raw_reason": "EV_TOP1",
                "ev_raw": float(winner["ev_adverse"]), "ev_gate": gated["ev_gate"],
                "accepted": gated["accepted"],
                "filter_reason": "FILTER_ACCEPT" if gated["accepted"] else "FILTER_ABSTAIN",
            })
    return output


def prepare_rows(
    parent: str, variant: str, candidates: list[dict[str, Any]], scores: list[dict[str, Any]], decisions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    require(variant in VARIANTS, "variant")
    score_index = {row["candidate_id"]: row for row in scores if row["policy"] == parent}
    decision_groups = {(row["entry_date"], row["ticker"]): row for row in decisions}
    decision_index = {row["raw_winner_id"]: row for row in decisions if row["raw_winner_id"] is not None}
    output = []
    for candidate in candidates:
        score = score_index.get(candidate["candidate_id"])
        require(score is not None, "candidate score")
        row = dict(candidate)
        row["_ev_base"] = float(score["ev_base"])
        if variant == "CONTROL":
            row["_ev_adverse"] = float(score["ev_adverse"])
        else:
            group = decision_groups[(candidate["entry_date"], candidate["ticker"])]
            if group["raw_reason"] != "EV_TOP1":
                row["_ev_adverse"] = float(score["ev_adverse"])
            elif group["raw_winner_id"] == candidate["candidate_id"] and group["accepted"]:
                row["_ev_adverse"] = float(group["ev_gate"])
            else:
                row["_ev_adverse"] = 0.0
        output.append(row)
    return output, decision_index


def normalize_ledger(ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in row.items() if key not in {"policy", "model_id", "ev_gate"}} for row in ledger]


def reconcile_control(actual: dict[str, list[dict[str, Any]]], expected: dict[str, list[dict[str, Any]]]) -> None:
    for cost in COSTS:
        left, right = normalize_ledger(actual[cost]), normalize_ledger(expected[cost])
        require(len(left) == len(right), f"control ledger length {cost}")
        for a, b in zip(left, right, strict=True):
            require(set(a) == set(b), f"control ledger fields {cost}")
            for key in a:
                if isinstance(a[key], float) and isinstance(b[key], float):
                    require(math.isclose(float(a[key]), float(b[key]), abs_tol=1e-6, rel_tol=0), f"control numeric {cost}/{key}")
                else:
                    require(type(a[key]) is type(b[key]) and a[key] == b[key], f"control value {cost}/{key}")


def compare_rows(actual: list[dict[str, Any]], expected: list[dict[str, Any]], label: str, *, abs_tol: float = 1e-10) -> float:
    require(len(actual) == len(expected), f"{label} row count")
    maximum = 0.0
    for left, right in zip(actual, expected, strict=True):
        require(set(left) == set(right), f"{label} fields")
        for key in left:
            a, b = left[key], right[key]
            if isinstance(a, float) and isinstance(b, float):
                difference = abs(float(a) - float(b))
                maximum = max(maximum, difference)
                require(difference <= abs_tol, f"{label} numeric {key}")
            else:
                require(type(a) is type(b) and a == b, f"{label} value {key}")
    return maximum


def enrich_ledger(
    ledger: list[dict[str, Any]], parent: str, variant: str, scores: list[dict[str, Any]], decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    policy = f"{parent}_{variant}"
    score_index = {row["candidate_id"]: row for row in scores if row["policy"] == parent}
    gate_index = {row["raw_winner_id"]: row for row in decisions if row["raw_winner_id"] is not None}
    output = []
    for event in ledger:
        row = dict(event)
        candidate_id = row.get("candidate_id")
        score = score_index.get(candidate_id)
        row.update({"policy": policy, "parent": parent, "variant": variant, "model_id": score["model_id"] if score else None})
        if row["event"] == "ENTRY":
            require(score is not None, "ENTRY score")
            row["ev_base"], row["ev_adverse"] = float(score["ev_base"]), float(score["ev_adverse"])
            row["ev_gate"] = float(score["ev_adverse"]) if variant == "CONTROL" else float(gate_index[candidate_id]["ev_gate"])
        output.append(row)
    return output


def monthly_full_gate(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    monthly = {f"2026{month:02d}": 0.0 for month in range(1, 10)}
    for row in ledger:
        if row["event"] == "EXIT":
            monthly[row["date"][:6]] += float(row["net_usd"])
    completed = {month: monthly[month] for month in sorted(monthly)[:8]}
    return {"monthly_exit_net_usd": monthly, "completed_positive": sum(value > 0 for value in completed.values()), "passes_8_of_8": all(value > 0 for value in completed.values())}


def diagnostic_cell(rows: list[dict[str, Any]], parent: str, universe: str, view: str, partition: str, value: str) -> dict[str, Any]:
    output: dict[str, Any] = {
        "parent": parent, "universe": universe, "view": view,
        "partition": partition, "value": value, "n": len(rows),
    }
    for target, source in (("ev_raw", "ev_adverse_raw"), ("ev_gate", "ev_gate"), ("net", "net_adverse")):
        values = [finite(row[source], source) for row in rows]
        output[f"mean_{target}"] = math.fsum(values) / len(values) if values else None
    raw_errors = [float(row["ev_adverse_raw"]) - float(row["net_adverse"]) for row in rows]
    gate_errors = [float(row["ev_gate"]) - float(row["net_adverse"]) for row in rows]
    for name, values in (("raw", raw_errors), ("gate", gate_errors)):
        output[f"bias_{name}"] = math.fsum(values) / len(values) if values else None
        output[f"mae_{name}"] = math.fsum(abs(item) for item in values) / len(values) if values else None
    output["lower_bound_n"] = sum(bool(row["payoff_is_lower_bound"]) for row in rows)
    return output


def build_ev_diagnostics(intentions: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decision_index = {
        (row["parent"], row["raw_winner_id"]): row
        for row in decisions if row["raw_winner_id"] is not None
    }
    enriched = []
    for source in intentions:
        row = dict(source)
        decision = decision_index.get((row["parent"], row["candidate_id"]))
        require(decision is not None and decision["raw_reason"] == "EV_TOP1", "intention decision binding")
        row["accepted"] = bool(decision["accepted"])
        row["ev_gate"] = finite(decision["ev_gate"], "diagnostic EV gate")
        enriched.append(row)
    partitions = (("TOTAL", ("ALL",)), ("ENTRY_BLOCK", ("H1_2026", "Q3_PARTIAL_2026")), ("ENTRY_MONTH", MONTHS))
    output = []
    for parent in PARENTS:
        parent_rows = [row for row in enriched if row["parent"] == parent]
        universes = (
            ("INTENTIONS", parent_rows),
            ("ACCEPTED", [row for row in parent_rows if row["accepted"]]),
            ("PRUNED", [row for row in parent_rows if not row["accepted"]]),
        )
        for universe, universe_rows in universes:
            for view in ("conservative_all", "without_lower_bounds"):
                viewed = [row for row in universe_rows if view == "conservative_all" or not row["payoff_is_lower_bound"]]
                for partition, values in partitions:
                    for value in values:
                        if partition == "TOTAL":
                            rows = viewed
                        elif partition == "ENTRY_BLOCK":
                            rows = [row for row in viewed if ("H1_2026" if row["entry_date"] <= "20260630" else "Q3_PARTIAL_2026") == value]
                        else:
                            rows = [row for row in viewed if row["entry_date"][:6] == value]
                        output.append(diagnostic_cell(rows, parent, universe, view, partition, value))
    require(len(output) == 216, "diagnostic row count")
    return output


def extended_metrics(ledger: list[dict[str, Any]], helper: Any) -> dict[str, Any]:
    result = helper.book_metrics(ledger)
    exits = [row for row in ledger if row["event"] == "EXIT"]
    monthly = {month: math.fsum(float(row["net_usd"]) for row in exits if row["date"][:6] == month) for month in MONTHS}
    largest = max(exits, key=lambda row: (abs(float(row["net_usd"])), row["candidate_id"]), default=None)
    largest_month = max(MONTHS, key=lambda month: (abs(monthly[month]), month))
    result.update({
        "monthly_net_including_zeros": monthly,
        "monthly_convention": "exit_date_realization",
        "block_net_by_exit": {
            "H1_2026": math.fsum(float(row["net_usd"]) for row in exits if row["date"] <= "20260630"),
            "Q3_PARTIAL_2026": math.fsum(float(row["net_usd"]) for row in exits if row["date"] >= "20260701"),
        },
        "lower_bound_exits": sum(row.get("status") in {"MISSING_EXIT_SOURCE", "MISSING_EXIT_QUOTE"} for row in exits),
        "largest_trade": None if largest is None else {key: largest[key] for key in ("candidate_id", "date", "ticker", "right", "net_usd", "quantity")},
        "largest_month": {"month": largest_month, "net_usd": monthly[largest_month]},
    })
    return result


def output_names() -> set[str]:
    ledgers = {f"ledger_{parent.lower()}_{variant.lower()}_{cost}.jsonl" for parent in PARENTS for variant in VARIANTS for cost in COSTS}
    return {"intentions.jsonl", "decision_states.jsonl", "ev_diagnostics.jsonl", "summary.json", *ledgers}


def manifest_payload(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    value = manifest.get("outputs", {}).get(name)
    require(isinstance(value, dict) and set(value) >= {"bytes", "sha256"}, f"manifest output {name}")
    return value


def compare_value(actual: Any, expected: Any, label: str, *, tolerance: float = 1e-10) -> float:
    if isinstance(actual, dict) and isinstance(expected, dict):
        require(set(actual) == set(expected), f"{label} keys")
        return max((compare_value(actual[key], expected[key], f"{label}/{key}", tolerance=tolerance) for key in actual), default=0.0)
    if isinstance(actual, list) and isinstance(expected, list):
        require(len(actual) == len(expected), f"{label} length")
        return max((compare_value(a, b, f"{label}/{number}", tolerance=tolerance) for number, (a, b) in enumerate(zip(actual, expected, strict=True))), default=0.0)
    if isinstance(actual, float) and isinstance(expected, float):
        difference = abs(float(actual) - float(expected))
        require(math.isfinite(difference) and difference <= tolerance, f"{label} numeric")
        return difference
    require(type(actual) is type(expected) and actual == expected, f"{label} value")
    return 0.0


def require_pin_shape(value: Any, label: str, *, path_required: bool = True) -> None:
    keys = {"path", "bytes", "sha256"} if path_required else {"bytes", "sha256"}
    require(isinstance(value, dict) and set(value) == keys, f"{label} pin fields")
    require(isinstance(value["bytes"], int) and value["bytes"] >= 0, f"{label} pin bytes")
    require(isinstance(value["sha256"], str) and len(value["sha256"]) == 64, f"{label} pin SHA")
    if path_required:
        require(isinstance(value["path"], str), f"{label} pin path")


def payload_pin(manifest: dict[str, Any], path: Path) -> dict[str, Any]:
    value = manifest.get("consumed_payloads", {}).get(str(path)) or manifest.get("outputs", {}).get(path.name)
    require(isinstance(value, dict), f"upstream payload pin {path}")
    verify(path, value, f"upstream payload {path.name}")
    return value


def validate_score_universe(
    scores: list[dict[str, Any]], candidates: dict[str, dict[str, Any]], bridge_ids: set[str],
) -> dict[str, list[dict[str, Any]]]:
    require(len(scores) == EXPECTED_SCORES, "score total")
    require(len({(row["policy"], row["candidate_id"]) for row in scores}) == len(scores), "score uniqueness")
    policies = (*PARENTS, "MONTHLY_GUARDED", "WEEKLY_GUARDED")
    by_policy = {policy: [row for row in scores if row.get("policy") == policy] for policy in policies}
    require(all(len(rows) == EXPECTED_CANDIDATES for rows in by_policy.values()), "five score counts")
    common = {row["candidate_id"] for row in by_policy[PARENTS[0]]}
    require(len(common) == EXPECTED_CANDIDATES and all({row["candidate_id"] for row in rows} == common for rows in by_policy.values()), "common score IDs")
    require(common <= set(candidates), "score candidate closure")
    normalized = [normalize_score(row, candidates[row["candidate_id"]]) for row in scores]
    require(all(bool(row["is_bridge"]) == (row["candidate_id"] in bridge_ids) for row in normalized), "score bridge flags")
    require(sum(row["policy"] in PARENTS for row in normalized) == EXPECTED_USED_SCORES, "used score count")
    return {policy: [row for row in normalized if row["policy"] == policy] for policy in policies}


def admit_upstream() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = ADAPTATION_ROOT / "manifest.json"
    require(sha256_file(manifest_path) == ADAPTATION_MANIFEST_SHA256, "adaptation manifest SHA")
    manifest = read_json(manifest_path)
    require(manifest.get("schema") == "weekly_context_adaptation_walkforward_v1", "adaptation schema")
    require(manifest.get("status") == "PASS_SEEN_DEVELOPMENT_GIVEN_BRIDGE_AND_FROZEN_AUTHORITIES", "adaptation status")
    require(manifest.get("flags") == ADAPTATION_FLAGS, "adaptation flags")
    require(sha256_file(ADAPTATION_AUDIT) == ADAPTATION_AUDIT_SHA256, "adaptation audit SHA")
    audit = read_json(ADAPTATION_AUDIT)
    require(audit.get("schema") == "weekly_context_adaptation_audit_v1", "adaptation audit schema")
    require(audit.get("status") == "PASS_INDEPENDENT_NUMERIC_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT", "adaptation audit status")
    require(audit.get("flags") == ADAPTATION_AUDIT_FLAGS, "adaptation audit flags")
    expected = {"path": str(manifest_path), "bytes": ADAPTATION_MANIFEST_BYTES, "sha256": ADAPTATION_MANIFEST_SHA256}
    require(audit.get("inputs", {}).get("producer_manifest") == expected, "adaptation audit binding")
    require(sha256_file(ADAPTATION_EXIT) == ADAPTATION_EXIT_SHA256 and read_json(ADAPTATION_EXIT).get("exit_code") == 0, "adaptation exit")
    return manifest, audit


def expected_summary(
    sessions: list[str], intentions: list[dict[str, Any]], decisions: list[dict[str, Any]],
    books: dict[tuple[str, str], list[dict[str, Any]]], helper: Any,
) -> dict[str, Any]:
    policy_summary: dict[str, Any] = {}
    for parent in PARENTS:
        for variant in VARIANTS:
            policy = f"{parent}_{variant}"
            metrics = {cost: extended_metrics(books[(policy, cost)], helper) for cost in COSTS}
            policy_summary[policy] = {
                "books": metrics,
                "eight_of_eight_positive_adverse": all(metrics["adverse"]["monthly_net_including_zeros"][month] > 0 for month in COMPLETE_MONTHS),
            }
    intention_summary = {}
    for parent in PARENTS:
        parent_intentions = [row for row in intentions if row["parent"] == parent]
        parent_decisions = [row for row in decisions if row["parent"] == parent]
        winners = [row for row in parent_decisions if row["raw_winner_id"] is not None]
        active = [row for row in parent_decisions if row["state"] == "ACTIVE_FILTER"]
        reasons = sorted({row["filter_reason"] for row in parent_decisions})
        intention_summary[parent] = {
            "intentions": len(parent_intentions),
            "accepted": sum(bool(row["accepted"]) for row in winners),
            "pruned": sum(not bool(row["accepted"]) for row in winners),
            "activation_entry_date": active[0]["entry_date"] if active else None,
            "activation_n": active[0]["n"] if active else None,
            "decision_reasons": {reason: sum(row["filter_reason"] == reason for row in parent_decisions) for reason in reasons},
        }
    return {
        "schema": "weekly_prequential_ev_filter_summary_v1",
        "status": "COMPLETE_SEEN_DEVELOPMENT_NOT_PROMOTED",
        "scope": {"sessions": len(sessions), "candidate_universe": EXPECTED_CANDIDATES, "parents": list(PARENTS), "policies": [f"{parent}_{variant}" for parent in PARENTS for variant in VARIANTS]},
        "intentions": intention_summary,
        "policies": policy_summary,
        "filter_minus_control": {
            parent: {cost: policy_summary[f"{parent}_FILTER"]["books"][cost]["net_usd"] - policy_summary[f"{parent}_CONTROL"]["books"][cost]["net_usd"] for cost in COSTS}
            for parent in PARENTS
        },
        "criterion": {"months": list(COMPLETE_MONTHS), "necessary": "adverse exit-date net strictly positive in every month", "promotion_approved": False},
        "flags": SUMMARY_FLAGS,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent prequential EV filter audit")
    parser.add_argument("--execute-reviewed-audit", action="store_true")
    parser.add_argument("--producer-manifest-sha256", required=True)
    parser.add_argument("--producer-exit-sha256", required=True)
    parser.add_argument("--auditor-sha256", required=True)
    args = parser.parse_args()
    if not args.execute_reviewed_audit:
        parser.error("execution requires --execute-reviewed-audit")
    for value in (args.producer_manifest_sha256, args.producer_exit_sha256, args.auditor_sha256):
        require(isinstance(value, str) and len(value) == 64, "SHA-256 CLI")
    run(args.producer_manifest_sha256.lower(), args.producer_exit_sha256.lower(), args.auditor_sha256.lower())
    return 0


def run(producer_manifest_sha256: str, producer_exit_sha256: str, auditor_sha256: str, output: Path = OUTPUT) -> dict[str, Any]:
    require(sha256_file(CONTRACT) == CONTRACT_SHA256, "contract pin")
    require(sha256_file(Path(__file__)) == auditor_sha256, "auditor self pin")
    output = guard_output(output)
    manifest = plain(PRODUCER_ROOT / "manifest.json", "producer manifest", regular=True)
    exit_path = plain(PRODUCER_OBSERVER / "exit.json", "producer exit", regular=True)
    require(sha256_file(manifest) == producer_manifest_sha256 and sha256_file(exit_path) == producer_exit_sha256, "producer binding SHA")
    producer_manifest = read_json(manifest)
    require(set(producer_manifest) == {"schema", "status", "inputs", "outputs", "flags"}, "producer manifest fields")
    require(producer_manifest["schema"] == "weekly_prequential_ev_filter_manifest_v1", "producer manifest schema")
    require(producer_manifest["status"] == "COMPLETE_SEEN_DEVELOPMENT_NOT_PROMOTED", "producer manifest status")
    require(producer_manifest["flags"] == SUMMARY_FLAGS, "producer manifest flags")
    producer_exit = read_json(exit_path)
    require(producer_exit.get("exit_code") == 0, "producer retained exit")
    inputs = producer_manifest["inputs"]
    require(isinstance(inputs, dict) and len(inputs) == 24, "producer input closure count")
    input_paths: dict[str, Path] = {}
    for name, value in inputs.items():
        require(isinstance(name, str) and isinstance(value, dict) and set(value) == {"before", "after"}, "producer input shape")
        require_pin_shape(value["before"], name, path_required=False)
        require_pin_shape(value["after"], name, path_required=False)
        require(value["before"] == value["after"], f"producer input closure {name}")
        path = plain(Path(name), f"producer input {name}", regular=True)
        actual = pin(path)
        require({"bytes": actual["bytes"], "sha256": actual["sha256"]} == value["before"], f"producer input current {name}")
        input_paths[name] = path

    adaptation_manifest, _adaptation_audit = admit_upstream()
    fixed = {
        str(ADAPTATION_ROOT / "manifest.json"): ADAPTATION_MANIFEST_SHA256,
        str(ADAPTATION_AUDIT): ADAPTATION_AUDIT_SHA256,
        str(ADAPTATION_EXIT): ADAPTATION_EXIT_SHA256,
        str(DIAGNOSTIC): DIAGNOSTIC_SHA256,
        str(ACCEPTANCE): ACCEPTANCE_SHA256,
        str(PRODUCER_REPLAY): PRODUCER_REPLAY_SHA256,
        str(CONTRACT): CONTRACT_SHA256,
    }
    for name, expected_sha in fixed.items():
        require(name in inputs and inputs[name]["before"]["sha256"] == expected_sha, f"fixed producer input {name}")

    payload_paths = [
        DATASET_H1 / "candidates.jsonl", DATASET_Q3 / "candidates.jsonl", BRIDGE / "candidates.jsonl",
        DATASET_H1 / "coverage.json", DATASET_Q3 / "coverage.json", BRIDGE / "coverage_overlay.json",
        ADAPTATION_ROOT / "candidate_scores.jsonl", ADAPTATION_ROOT / "summary.json",
        *[ADAPTATION_ROOT / f"ledger_{parent.lower()}_{cost}.jsonl" for parent in PARENTS for cost in COSTS],
    ]
    require(len(payload_paths) == 14, "payload closure definition")
    for path in payload_paths:
        expected = payload_pin(adaptation_manifest, path)
        require(str(path) in inputs and inputs[str(path)]["before"] == {"bytes": expected["bytes"], "sha256": expected["sha256"]}, f"producer payload binding {path.name}")

    expected_outputs = output_names()
    require(set(producer_manifest["outputs"]) == expected_outputs, "producer output set")
    producer_outputs: dict[str, Path] = {}
    for name, expected in producer_manifest["outputs"].items():
        require_pin_shape(expected, f"producer output {name}", path_required=False)
        path = plain(PRODUCER_ROOT / name, f"producer output {name}", regular=True)
        verify(path, expected, f"producer output {name}")
        producer_outputs[name] = path

    initial_snapshots = {
        str(path): pin(path)
        for path in {manifest, exit_path, Path(__file__), *input_paths.values(), *producer_outputs.values()}
    }

    helper = import_pure_auditor()
    raw_candidates = [*read_jsonl(payload_paths[0]), *read_jsonl(payload_paths[1]), *read_jsonl(payload_paths[2])]
    require(len(raw_candidates) == EXPECTED_ALL_CANDIDATES, "candidate union count")
    candidates = [normalize_candidate(row) for row in raw_candidates]
    candidate_index = {row["candidate_id"]: row for row in candidates}
    require(len(candidate_index) == EXPECTED_ALL_CANDIDATES, "candidate union uniqueness")
    bridge_rows = read_jsonl(payload_paths[2])
    bridge_ids = {row["candidate_id"] for row in candidates if row["entry_date"] == "20260629" and row["exit_date"] == "20260701"}
    require(
        len(bridge_ids) == 6
        and {(row["ticker"], row["right"]) for row in bridge_rows} == {(ticker, right) for ticker in TICKERS for right in RIGHTS}
        and all(row["entry_date"] == "20260629" and row["exit_date"] == "20260701" for row in bridge_rows),
        "bridge candidate scope",
    )

    h1_coverage, q3_coverage, overlay = (read_json(payload_paths[3]), read_json(payload_paths[4]), read_json(payload_paths[5]))
    sessions = common_calendar(h1_coverage, q3_coverage)
    coverage = merge_coverage(h1_coverage, q3_coverage, overlay)
    raw_scores = read_jsonl(payload_paths[6])
    by_policy = validate_score_universe(raw_scores, candidate_index, bridge_ids)
    score_ids = {row["candidate_id"] for row in by_policy[PARENTS[0]]}
    eval_candidates = [candidate_index[candidate_id] for candidate_id in sorted(score_ids)]
    covered_ids = {candidate_id for row in coverage if FIRST_DATE <= row["entry_date"] <= LAST_ENTRY for candidate_id in row.get("candidate_ids", [])}
    require(covered_ids == score_ids, "coverage score closure")

    reconstructed_intentions: list[dict[str, Any]] = []
    reconstructed_decisions: list[dict[str, Any]] = []
    parent_scores = {parent: by_policy[parent] for parent in PARENTS}
    for parent in PARENTS:
        intentions = raw_intentions(parent, eval_candidates, parent_scores[parent])
        decisions = reconstruct_decision_rows(parent, intentions, parent_scores[parent], sessions)
        reconstructed_intentions.extend(intentions)
        reconstructed_decisions.extend(decisions)
    actual_intentions = read_jsonl(producer_outputs["intentions.jsonl"])
    actual_decisions = read_jsonl(producer_outputs["decision_states.jsonl"])
    max_intention_error = compare_rows(actual_intentions, reconstructed_intentions, "intentions", abs_tol=1e-10)
    max_decision_error = compare_rows(actual_decisions, reconstructed_decisions, "decisions", abs_tol=1e-10)

    books: dict[tuple[str, str], list[dict[str, Any]]] = {}
    max_ledger_error = 0.0
    for parent in PARENTS:
        scores = parent_scores[parent]
        decisions = [row for row in reconstructed_decisions if row["parent"] == parent]
        for variant in VARIANTS:
            replay_rows, _decision_index = prepare_rows(parent, variant, eval_candidates, scores, decisions)
            replayed = helper.replay_risk(replay_rows, coverage, sessions, LAST_ENTRY)
            if variant == "CONTROL":
                upstream = {cost: read_jsonl(ADAPTATION_ROOT / f"ledger_{parent.lower()}_{cost}.jsonl") for cost in COSTS}
                reconcile_control(replayed, upstream)
            policy = f"{parent}_{variant}"
            for cost in COSTS:
                enriched = enrich_ledger(replayed[cost], parent, variant, scores, decisions)
                actual = read_jsonl(producer_outputs[f"ledger_{parent.lower()}_{variant.lower()}_{cost}.jsonl"])
                max_ledger_error = max(max_ledger_error, compare_rows(actual, enriched, f"ledger {policy}/{cost}", abs_tol=1e-6))
                books[(policy, cost)] = enriched

    expected_diagnostics = build_ev_diagnostics(reconstructed_intentions, reconstructed_decisions)
    actual_diagnostics = read_jsonl(producer_outputs["ev_diagnostics.jsonl"])
    max_diagnostic_error = compare_rows(actual_diagnostics, expected_diagnostics, "EV diagnostics", abs_tol=1e-10)
    summary = expected_summary(sessions, reconstructed_intentions, reconstructed_decisions, books, helper)
    actual_summary = read_json(producer_outputs["summary.json"])
    max_summary_error = compare_value(actual_summary, summary, "summary", tolerance=1e-6)

    require(sha256_file(PURE_AUDITOR) == PURE_AUDITOR_SHA256, "pure helper closing pin")
    output.mkdir(parents=False, exist_ok=False)
    result = {
        "schema": "weekly_prequential_ev_filter_audit_v1",
        "status": "PASS_INDEPENDENT_PREQUENTIAL_EV_FILTER_RECONSTRUCTION",
        "inputs": {
            "auditor": pin(Path(__file__)), "contract": pin(CONTRACT),
            "independent_helper": pin(PURE_AUDITOR),
            "producer_manifest": pin(manifest), "producer_exit": pin(exit_path),
            "upstream_manifest": pin(ADAPTATION_ROOT / "manifest.json"),
            "upstream_audit": pin(ADAPTATION_AUDIT), "upstream_exit": pin(ADAPTATION_EXIT),
            "diagnostic": pin(DIAGNOSTIC), "acceptance": pin(ACCEPTANCE),
        },
        "flags": {
            "fit_performed": False, "inference_run": False, "raw_read": False,
            "api_read": False, "broker_read": False, "producer_imported": False,
            "production_changed": False, "promotion_approved": False,
            "seen_development": True,
        },
        "numeric": {
            "candidates_validated": len(candidates), "scores_validated": len(raw_scores),
            "scores_used": EXPECTED_USED_SCORES, "intentions_reconstructed": len(reconstructed_intentions),
            "decision_rows_reconstructed": len(reconstructed_decisions), "books_reconstructed": len(books),
            "diagnostic_rows_reconstructed": len(expected_diagnostics),
            "max_abs_error": {"intentions": max_intention_error, "decisions": max_decision_error, "ledgers": max_ledger_error, "diagnostics": max_diagnostic_error, "summary": max_summary_error},
        },
        "producer": {"manifest": producer_manifest, "criterion": {parent: summary["policies"][f"{parent}_FILTER"]["eight_of_eight_positive_adverse"] for parent in PARENTS}},
        "limitations": [
            "all 2026 periods are seen development and no promotion is approved",
            "the audit reconstructs from sealed scores and potential payoffs; it does not fit or infer a model",
            "the heuristic buffer is not a calibrated 95 percent confidence bound",
        ],
    }
    write_json(output / "audit.json", result)
    for name, before in initial_snapshots.items():
        now = pin(Path(name))
        require(before == now, f"closing snapshot {name}")
    require(sha256_file(Path(__file__)) == auditor_sha256 and sha256_file(PURE_AUDITOR) == PURE_AUDITOR_SHA256, "final implementation closure")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
