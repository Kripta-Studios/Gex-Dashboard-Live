"""Independent audit kernels for the weekly context adaptation walk-forward.

The producer is never imported and LogisticRegression.fit is never called.  The
auditor rebuilds temporal membership, preprocessing, priors, conditional means,
calibration, inference, proposal transitions, and continuous books from sealed
rows and stored coefficients.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np


WEEK = Path(__file__).resolve().parent
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
PRODUCER_ROOT = BASE / "h2_context_adaptation_01"
OUTPUT = BASE / "h2_context_adaptation_audit_04"
CONTRACT = WEEK / "ADAPTATION_WALKFORWARD_CONTRACT_20261101.md"
HELPER = WEEK / "audit_weekly_context_models.py"
CONTRACT_SHA256 = "608dae37c21c19277a36dbcc1eeaa36da0135385a080618d461a4e240855cc61"
HELPER_SHA256 = "3eb6b9795ad260971435259858f86d3c00111bcc141973faf986411d4a68ad99"
PRODUCER_SHA256 = "d03494bf68e281bc7c9e68f385aa111567eac4206cf5b44133e17bb480ed5df8"
PRODUCER_TESTS_SHA256 = "2f44f17d459cd7cb43c5c3842fb4b2d72c689278f797426a75ac006f0d5db43f"
POLICIES = ("FROZEN_CONTEXT182", "MONTHLY_RAW", "WEEKLY_RAW", "MONTHLY_GUARDED", "WEEKLY_GUARDED")
COSTS = ("base", "adverse")
TICKERS = ("SPY", "QQQ", "SPXW")
RIGHTS = ("CALL", "PUT")
NY = ZoneInfo("America/New_York")
STARTING_CASH = 100_000.0
COMMISSION = 1.30
BUDGET_CENTS = 500_000
LAST_ENTRY = "20260915"
PLAN_KEYS = {
    "state_id", "creation_date", "asof", "frequencies", "cal_sessions",
    "cal_start", "cal_end", "train_ids", "cal_ids", "purged_train_ids",
    "train_label_available_max", "cal_label_available_max",
}
MODEL_KEYS = {
    "type", "sklearn_version", "C", "penalty", "solver", "max_iter",
    "random_state", "warm_start", "class_weight", "classes_present",
    "classes_full", "coefficient", "intercept", "fit_scope", "fit_warnings",
    "constructor_penalty_omitted", "l1_ratio",
}
PRODUCER_SCHEMA = "weekly_context_adaptation_walkforward_v1"
PRODUCER_STATUS = "PASS_SEEN_DEVELOPMENT_GIVEN_BRIDGE_AND_FROZEN_AUTHORITIES"
AUDIT_SCHEMA = "weekly_context_adaptation_audit_v1"
AUDIT_STATUS = "PASS_INDEPENDENT_NUMERIC_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT"
EXTERNAL_KEYS = {
    "contract", "context_helper", "evaluator_helper", "replay_helper", "producer",
    "tests", "bridge_manifest", "bridge_audit", "dataset_h1", "dataset_q3",
    "context_h1", "context_q3", "comparison_h1", "comparison_q3", "frozen_ev",
    "context_q3_audit", "comparison_h1_audit", "comparison_q3_audit",
}
FROZEN_EXTERNAL_SHA256 = {
    "contract": CONTRACT_SHA256,
    "context_helper": "bdc6534f059ade7acc58f23952a88ed2068c7a712518b04f438945a583a07a2f",
    "evaluator_helper": "8a9e75855d542a12662e5c812583f2ef86042f5c3ae1bbbad73c16042e063476",
    "replay_helper": "e4f42a9fa65120939cf5e131911c8f2990a9cd33d21ae036fa98d9eb816d5b9d",
    "dataset_h1": "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8",
    "dataset_q3": "b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b",
    "context_h1": "77aaf00d60accc071ff1f58ec099cee72bc3a4150f89e4ad41a601821a74a38a",
    "context_q3": "1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66",
    "comparison_h1": "662ac63eaa2895beff4363b9e94a97cd7adc91aac3558139bdd919d8fbf2861a",
    "comparison_q3": "dcdc8b0bef5a508f40b322ba632109d4afaff689a3d0d36514f30d8618531e66",
    "frozen_ev": "54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96",
    "context_q3_audit": "ae90d005b6fa9a3a1a708fdfafd3361bdef9146312ddda324d103a139cd18633",
    "comparison_h1_audit": "bb661fe916f65ed6ee40dd3cf684650a8d318447005a7f224edec6a4b814b3eb",
    "comparison_q3_audit": "ef6a325b8f4defc579aa568ebd9dc980ede750e106a8ef4578b025d999215f69",
}
OUTPUT_FILES = {
    "fit_plans.json", "states.jsonl", "candidate_scores.jsonl",
    "policy_timeline.jsonl", "proposals.jsonl", "shadow_predictions.jsonl",
    "gate_replays.jsonl", "summary.json",
    *{
        f"ledger_{policy.lower()}_{cost}.jsonl"
        for policy in POLICIES for cost in COSTS
    },
}


class AdaptationAuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AdaptationAuditError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_link_or_reparse(path: Path) -> bool:
    current = Path(os.path.abspath(path))
    while True:
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            info = None
        if info is not None:
            attrs = getattr(info, "st_file_attributes", 0)
            if stat.S_ISLNK(info.st_mode) or attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                return True
        if current.parent == current:
            return False
        current = current.parent


def plain(path: Path, label: str, *, exists: bool = True) -> Path:
    path = Path(os.path.abspath(path))
    require(not is_link_or_reparse(path), f"link/reparse {label}")
    if exists:
        require(path.exists(), f"missing {label}")
    return path


def pin(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "sha256": sha256_file(path)}


def verify(path: Path, expected: dict[str, Any], label: str) -> None:
    path = plain(path, label)
    require(path.is_file() and pin(path) == {"bytes": expected["bytes"], "sha256": expected["sha256"]}, f"pin {label}")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL {path}:{number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"object required {path}:{number}")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def import_helper() -> Any:
    path = plain(HELPER, "independent H1 helper")
    before = pin(path)
    require(before["sha256"] == HELPER_SHA256, "H1 helper authority")
    spec = importlib.util.spec_from_file_location("_adaptation_independent_h1_helper", path)
    require(spec is not None and spec.loader is not None, "H1 helper spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(Path(os.path.abspath(module.__file__)) == path and pin(path) == before, "H1 helper changed during import")
    return module


def parse_available(value: Any) -> datetime | None:
    if value is None:
        return None
    require(isinstance(value, str), "label_available_at type")
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, "label_available_at timezone")
    return parsed.astimezone(NY)


def midnight(day: str) -> datetime:
    return datetime.strptime(day, "%Y%m%d").replace(tzinfo=NY)


def creation_dates(eval_sessions: list[str]) -> dict[str, list[str]]:
    require(eval_sessions == sorted(set(eval_sessions)) and len(eval_sessions) == 178, "evaluation sessions")
    monthly, weekly = [], []
    seen_month, seen_week = set(), set()
    for day in eval_sessions:
        value = datetime.strptime(day, "%Y%m%d")
        month, week = (value.year, value.month), value.isocalendar()[:2]
        if month not in seen_month:
            seen_month.add(month)
            monthly.append(day)
        if week not in seen_week:
            seen_week.add(week)
            weekly.append(day)
    require(len(monthly) == 9 and len(weekly) == 38 and len(set(monthly) | set(weekly)) == 42 and len(set(monthly) & set(weekly)) == 5, "creation schedule counts")
    return {"monthly": monthly, "weekly": weekly, "physical": sorted(set(monthly) | set(weekly))}


def derive_split(
    creation_day: str, calendar: list[str], rows: list[dict[str, Any]],
) -> dict[str, Any]:
    require(calendar == sorted(set(calendar)) and creation_day in calendar, "calendar/creation")
    index = calendar.index(creation_day)
    require(index >= 65, "insufficient CAL history")
    cal_sessions = calendar[index - 65:index - 2]
    require(len(cal_sessions) == 63, "CAL session count")
    cal_start, asof = cal_sessions[0], midnight(creation_day)
    train, cal, purged = [], [], []
    for row in rows:
        available = parse_available(row.get("label_available_at"))
        day, candidate_id = row["entry_date"], row["candidate_id"]
        if day < cal_start:
            if available is not None and available < midnight(cal_start):
                train.append(candidate_id)
            else:
                purged.append(candidate_id)
        elif day in set(cal_sessions):
            if available is not None and available < asof:
                cal.append(candidate_id)
            else:
                purged.append(candidate_id)
    require(set(train).isdisjoint(cal) and set(train).isdisjoint(purged) and set(cal).isdisjoint(purged), "split overlap")
    return {
        "creation_date": creation_day, "asof": asof.isoformat(),
        "cal_sessions": cal_sessions, "cal_start": cal_start,
        "train_ids": sorted(train), "cal_ids": sorted(cal), "purged_ids": sorted(purged),
    }


def conditional_means(train: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {"shrinkage": 20, "global": {}, "cells": {}}
    for cost in COSTS:
        by_class = {label: [] for label in range(5)}
        cells = {(label, ticker, right): [] for label in range(5) for ticker in TICKERS for right in RIGHTS}
        for row in train:
            label = int(row["scenario"])
            normalized = float(row[f"net_{cost}"]) / (float(row["decision_ask"]) * 100)
            by_class[label].append(normalized)
            cells[(label, row["ticker"], row["right"])].append(normalized)
        global_means = {str(label): math.fsum(by_class[label]) / len(by_class[label]) if by_class[label] else 0.0 for label in range(5)}
        output["global"][cost], output["cells"][cost] = global_means, {}
        for ticker in TICKERS:
            for right in RIGHTS:
                key = f"{ticker}:{right}"
                output["cells"][cost][key] = {}
                for label in range(5):
                    values = cells[(label, ticker, right)]
                    mean = (math.fsum(values) + 20 * global_means[str(label)]) / (len(values) + 20)
                    output["cells"][cost][key][str(label)] = {"n": len(values), "mean_y": mean}
    return output


def assert_close(actual: Any, expected: Any, label: str, *, atol: float = 1e-12) -> None:
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), f"{label} keys")
        for key in expected:
            assert_close(actual[key], expected[key], f"{label}.{key}", atol=atol)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f"{label} list")
        for index, value in enumerate(expected):
            assert_close(actual[index], value, f"{label}[{index}]", atol=atol)
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        require(isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isclose(float(actual), float(expected), abs_tol=atol, rel_tol=1e-12), f"{label} numeric")
    else:
        require(actual == expected, f"{label} value")


def restored_probabilities_adaptation(
    values: np.ndarray, saved_model: dict[str, Any],
) -> np.ndarray:
    """Restore sklearn LR inference, including sklearn's binary one-row form."""
    require(
        saved_model.get("type") == "LogisticRegression"
        and saved_model.get("fit_scope") == "TRAIN_ONLY",
        "model schema",
    )
    require(
        saved_model.get("penalty") == "l2"
        and saved_model.get("constructor_penalty_omitted") is True
        and saved_model.get("l1_ratio") == 0.0
        and saved_model.get("C") == 1.0
        and saved_model.get("solver") == "lbfgs"
        and saved_model.get("max_iter") == 2000
        and saved_model.get("random_state") == 0
        and saved_model.get("warm_start") is False
        and saved_model.get("class_weight") is None,
        "model recipe",
    )
    require(saved_model.get("classes_full") == list(range(5)), "model class universe")
    classes = [int(value) for value in saved_model.get("classes_present", [])]
    require(
        len(classes) >= 2
        and classes == sorted(set(classes))
        and all(0 <= value < 5 for value in classes),
        "model classes",
    )
    require(
        isinstance(saved_model.get("sklearn_version"), str)
        and bool(saved_model["sklearn_version"])
        and isinstance(saved_model.get("fit_warnings"), list),
        "model metadata",
    )
    coefficient = np.asarray(saved_model["coefficient"], dtype=float)
    intercept = np.asarray(saved_model["intercept"], dtype=float)
    if len(classes) == 2:
        require(
            coefficient.shape == (1, values.shape[1]) and intercept.shape == (1,),
            "binary coefficient shape",
        )
        decision = values @ coefficient[0] + intercept[0]
        positive = np.empty_like(decision)
        nonnegative = decision >= 0
        positive[nonnegative] = 1.0 / (1.0 + np.exp(-decision[nonnegative]))
        exponent = np.exp(decision[~nonnegative])
        positive[~nonnegative] = exponent / (1.0 + exponent)
        partial = np.column_stack([1.0 - positive, positive])
    else:
        require(
            coefficient.shape == (len(classes), values.shape[1])
            and intercept.shape == (len(classes),),
            "multiclass coefficient shape",
        )
        logits = values @ coefficient.T + intercept
        logits -= logits.max(axis=1, keepdims=True)
        partial = np.exp(logits)
        partial /= partial.sum(axis=1, keepdims=True)
    output = np.zeros((len(values), 5), dtype=float)
    output[:, classes] = partial
    return output


def validate_saved_state(
    helper: Any, state: dict[str, Any], plan: dict[str, Any],
    rows_by_id: dict[str, dict[str, Any]], full_calendar: list[str],
) -> dict[str, Any]:
    require(plan["asof"] == midnight(plan["creation_date"]).isoformat(), "state creation timestamp")
    require(set(plan) == PLAN_KEYS, "fit plan schema")
    require(
        set(state) == PLAN_KEYS | {
            "feature_order", "transform", "model", "prior", "prior_support",
            "conditional_means", "calibration",
        },
        "saved state schema",
    )
    require(state.get("state_id") == plan.get("state_id"), "state/plan identity")
    for key in (
        "creation_date", "asof", "frequencies", "cal_sessions", "cal_start",
        "cal_end", "train_ids", "cal_ids", "purged_train_ids",
        "train_label_available_max", "cal_label_available_max",
    ):
        require(state.get(key) == plan.get(key), f"state split {key}")
    require(
        len(plan["cal_sessions"]) == 63
        and plan["cal_sessions"] == sorted(set(plan["cal_sessions"]))
        and plan["cal_start"] == plan["cal_sessions"][0]
        and plan["cal_end"] == plan["cal_sessions"][-1],
        "state exact CAL calendar",
    )
    require(
        full_calendar == sorted(set(full_calendar))
        and plan["creation_date"] in full_calendar,
        "full calendar authority",
    )
    creation_index = full_calendar.index(plan["creation_date"])
    require(
        creation_index >= 65
        and plan["cal_sessions"] == full_calendar[creation_index - 65:creation_index - 2],
        "independently derived CAL window",
    )
    train = [rows_by_id[candidate_id] for candidate_id in plan["train_ids"]]
    cal = [rows_by_id[candidate_id] for candidate_id in plan["cal_ids"]]
    cal_start, asof = midnight(plan["cal_start"]), midnight(plan["creation_date"])
    expected_train, expected_purged, expected_cal = [], [], []
    cal_session_set = set(plan["cal_sessions"])
    for candidate_id, row in rows_by_id.items():
        available = parse_available(row.get("label_available_at"))
        if row["entry_date"] < plan["cal_start"]:
            (expected_train if available is not None and available < cal_start else expected_purged).append(candidate_id)
        elif row["entry_date"] in cal_session_set:
            require(available is not None and available < asof, "CAL label not mature")
            expected_cal.append(candidate_id)
    require(sorted(plan["train_ids"]) == sorted(expected_train), "rebuilt TRAIN membership")
    require(sorted(plan["purged_train_ids"]) == sorted(expected_purged), "rebuilt TRAIN purge")
    require(sorted(plan["cal_ids"]) == sorted(expected_cal), "rebuilt CAL membership")
    train_max = max((parse_available(row["label_available_at"]) for row in train), default=None)
    cal_max = max((parse_available(row["label_available_at"]) for row in cal), default=None)
    require(
        plan["train_label_available_max"] == (train_max.isoformat() if train_max else None)
        and plan["cal_label_available_max"] == (cal_max.isoformat() if cal_max else None),
        "label availability maxima",
    )
    require(train and cal and len({row["scenario"] for row in train}) >= 2, "state class/CAL support")
    train_matrix = np.asarray([row["_x_context"] for row in train], dtype=float)
    require(len(state["feature_order"]) == 182, "state feature width")
    helper.validate_transform(train_matrix, state["feature_order"], state["transform"])
    prior_counts = np.bincount(np.asarray([row["scenario"] for row in train], dtype=int), minlength=5)
    prior = prior_counts.astype(float) / len(train)
    require(state.get("prior_support") == prior_counts.astype(int).tolist(), "state prior support")
    require(np.array_equal(prior, np.asarray(state["prior"], dtype=float)), "state prior")
    rebuilt_means = conditional_means(train)
    assert_close(state["conditional_means"], rebuilt_means, "state conditional means")
    classes = sorted({int(row["scenario"]) for row in train})
    require(
        set(state["model"]) == MODEL_KEYS
        and state["model"]["fit_warnings"] == [],
        "state model closure",
    )
    require(state["model"].get("classes_present") == classes, "state TRAIN classes")
    transformed_cal = helper.apply_saved_transform(np.asarray([row["_x_context"] for row in cal], dtype=float), state["transform"])
    raw_cal = restored_probabilities_adaptation(transformed_cal, state["model"])
    labels = np.asarray([row["scenario"] for row in cal], dtype=int)
    grid = []
    for step in range(11):
        alpha = step / 10
        mixed = (1 - alpha) * raw_cal + alpha * prior
        grid.append({"alpha": alpha, "log_loss": helper.log_loss(labels, mixed)})
    best = min(grid, key=lambda item: (item["log_loss"], item["alpha"]))
    require(
        set(state["calibration"]) == {"formula", "selected_alpha", "scores"}
        and state["calibration"]["formula"] == "(1-alpha)*p_model+alpha*p_train_prior"
        and state["calibration"]["selected_alpha"] == best["alpha"],
        "state calibration alpha",
    )
    assert_close(state["calibration"]["scores"], grid, "state calibration grid")
    return {"prior": prior, "means": rebuilt_means, "alpha": float(best["alpha"]), "train": train, "cal": cal}


def score_state(helper: Any, state: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matrix = np.asarray([row["_x_context"] for row in rows], dtype=float)
    transformed = helper.apply_saved_transform(matrix, state["transform"])
    raw = (
        helper.restored_probabilities(transformed, state["model"])
        if state.get("inference") == "FROZEN_H1_HELPER"
        else restored_probabilities_adaptation(transformed, state["model"])
    )
    prior, alpha = np.asarray(state["prior"], dtype=float), float(state["calibration"]["selected_alpha"])
    calibrated = (1 - alpha) * raw + alpha * prior
    ev = {cost: helper.ev_values(rows, calibrated, state["conditional_means"], cost) for cost in COSTS}
    return [
        {"candidate_id": row["candidate_id"], "p_model": p_model.tolist(), "p_cal": p_cal.tolist(), "ev_base": float(ev["base"][index]), "ev_adverse": float(ev["adverse"][index])}
        for index, (row, p_model, p_cal) in enumerate(zip(rows, raw, calibrated, strict=True))
    ]


def annotate_books(
    books: dict[str, list[dict[str, Any]]], policy: str,
    candidate_models: dict[str, str], active_by_date: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    output = {cost: [] for cost in COSTS}
    for cost in COSTS:
        for event in books[cost]:
            value = dict(event)
            candidate_id = value.get("candidate_id")
            model_id = candidate_models.get(candidate_id) if candidate_id else None
            if value["event"] in {"ENTRY", "EXIT"}:
                require(isinstance(model_id, str) and model_id, "event model trace")
            value["policy"], value["model_id"] = policy, model_id
            output[cost].append(value)
    return output


def proposal_gate_sessions(created: str, eval_sessions: list[str]) -> list[str]:
    require(created in eval_sessions, "proposal creation session")
    index = eval_sessions.index(created)
    return eval_sessions[index:index + 21]


def proposal_resolution_day(
    gate_sessions: list[str], calendar: list[str], rows: list[dict[str, Any]],
    cutoff: str,
) -> str | None:
    if len(gate_sessions) != 21:
        return None
    require(
        calendar == sorted(set(calendar)) and gate_sessions[-1] in calendar,
        "proposal resolution calendar",
    )
    gate_end_index = calendar.index(gate_sessions[-1])
    if gate_end_index + 3 >= len(calendar):
        return None
    resolution = calendar[gate_end_index + 3]
    if resolution > cutoff:
        return None
    gate_set = set(gate_sessions)
    relevant = [row for row in rows if row["entry_date"] in gate_set]
    asof = midnight(resolution)
    availability = [parse_available(row.get("label_available_at")) for row in relevant]
    require(
        all(value is not None and value < asof for value in availability),
        "proposal labels not mature at conservative resolution",
    )
    return resolution


def resolve_proposal(
    proposal: dict[str, Any], current_incumbent: str,
    gate: dict[str, Any] | None,
) -> tuple[str, str]:
    if gate is None:
        return "PENDING_BEYOND_DECISION_CUTOFF", current_incumbent
    if current_incumbent != proposal["incumbent_snapshot_id"]:
        return "STALE_CHALLENGER_REJECTED", current_incumbent
    if gate["candidate_count"] == 0:
        return "REJECTED_NO_GATE_ROWS", current_incumbent
    accepted = gate["challenger_logloss"] <= gate["incumbent_logloss"] and gate["challenger_net_adverse"] >= gate["incumbent_net_adverse"]
    return ("PROMOTED", proposal["challenger_id"]) if accepted else ("REJECTED", current_incumbent)


def audit_proposal_queue(
    proposals: list[dict[str, Any]], gates: dict[str, dict[str, Any]],
    initial_incumbent: str,
) -> tuple[list[dict[str, Any]], str]:
    incumbent, events = initial_incumbent, []
    ordered = sorted(proposals, key=lambda item: (item.get("resolved_at") or "99999999", item["created_date"], item["proposal_id"]))
    for proposal in ordered:
        status, after = resolve_proposal(proposal, incumbent, gates.get(proposal["proposal_id"]))
        require(proposal["status"] == status, f"proposal status {proposal['proposal_id']}")
        require(proposal.get("active_model_before") == incumbent and proposal.get("active_model_after") == after, f"proposal conservation {proposal['proposal_id']}")
        events.append({"proposal_id": proposal["proposal_id"], "before": incumbent, "after": after, "status": status})
        incumbent = after
    return events, incumbent


def validate_fit_plan_schedule(
    eval_sessions: list[str], plans: list[dict[str, Any]], states: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate the 47 logical references to exactly 42 physical fits."""
    schedule = creation_dates(eval_sessions)
    require(len(plans) == 42 and len(states) == 42, "physical state/plan count")
    plans_by_day = {item.get("creation_date"): item for item in plans}
    states_by_id = {item.get("state_id"): item for item in states}
    require(
        len(plans_by_day) == len(plans)
        and set(plans_by_day) == set(schedule["physical"]),
        "physical creation dates",
    )
    require(len(states_by_id) == len(states), "state id uniqueness")
    require(
        {item.get("state_id") for item in plans} == set(states_by_id)
        and len({item.get("state_id") for item in plans}) == len(plans),
        "plan/state bijection",
    )
    logical: dict[tuple[str, str], str] = {}
    for cadence in ("monthly", "weekly"):
        for day in schedule[cadence]:
            plan = plans_by_day[day]
            require(plan.get("state_id") in states_by_id, "plan state reference")
            references = plan.get("frequencies")
            expected_cadences = [
                name.upper()
                for name in ("monthly", "weekly")
                if day in schedule[name]
            ]
            require(references == expected_cadences, "plan cadence reference")
            logical[(cadence, day)] = plan["state_id"]
    for day in set(schedule["monthly"]) & set(schedule["weekly"]):
        require(
            logical[("monthly", day)] == logical[("weekly", day)],
            "coincident cadence duplicated fit",
        )
    return {
        "monthly_references": len(schedule["monthly"]),
        "weekly_references": len(schedule["weekly"]),
        "physical_states": len(states),
        "coincident_dates": len(set(schedule["monthly"]) & set(schedule["weekly"])),
    }


def compare_scores(
    actual: list[dict[str, Any]], expected: list[dict[str, Any]], *, label: str,
) -> None:
    def index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        output: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            key = (row.get("policy"), row.get("candidate_id"))
            require(all(isinstance(value, str) and value for value in key), f"{label} key")
            require(key not in output, f"{label} duplicate")
            output[key] = row
        return output

    actual_index, expected_index = index(actual), index(expected)
    require(set(actual_index) == set(expected_index), f"{label} identities")
    for key, rebuilt in expected_index.items():
        saved = actual_index[key]
        for field in ("entry_date", "model_id", "context_status", "context_state_valid"):
            require(saved.get(field) == rebuilt.get(field), f"{label} {key} {field}")
        for field in ("p_model", "p_cal"):
            assert_close(saved.get(field), rebuilt.get(field), f"{label} {key} {field}")
        for field in ("ev_base", "ev_adverse"):
            assert_close(saved.get(field), rebuilt.get(field), f"{label} {key} {field}")


def validate_score_model_clock(
    score: dict[str, Any], candidate: dict[str, Any],
    active_models: dict[str, dict[str, str]],
) -> None:
    require(
        score["model_id"] == active_models[score["policy"]][candidate["entry_date"]],
        "candidate score future/wrong model",
    )


def validate_gate_replay(
    proposal: dict[str, Any], gate_rows: list[dict[str, Any]],
    eval_sessions: list[str], calendar: list[str], all_rows: list[dict[str, Any]],
    cutoff: str,
) -> dict[str, Any] | None:
    sessions = proposal_gate_sessions(proposal["created_date"], eval_sessions)
    require(proposal.get("gate_sessions") == sessions, "proposal gate sessions")
    resolution = proposal_resolution_day(sessions, calendar, all_rows, cutoff)
    require(proposal.get("resolved_at") == resolution, "proposal resolution clock")
    if resolution is None:
        require(
            proposal.get("status") == "PENDING_BEYOND_DECISION_CUTOFF",
            "EOF proposal pending",
        )
        require(not gate_rows, "pending proposal has resolved gate")
        return None
    require(len(gate_rows) == 2, "gate challenger/incumbent rows")
    roles = {row.get("role"): row for row in gate_rows}
    require(set(roles) == {"challenger", "incumbent"}, "gate roles")
    for role, row in roles.items():
        require(row.get("proposal_id") == proposal["proposal_id"], "gate proposal id")
        require(row.get("sessions") == sessions, "gate session window")
        require(row.get("cost") == "adverse", "gate cost")
        require(row.get("starting_cash") == STARTING_CASH, "gate isolated cash")
        require(row.get("cal_rows_used") == 0, "CAL used in gate")
        candidate_ids = row.get("candidate_ids")
        require(
            isinstance(candidate_ids, list)
            and len(candidate_ids) == len(set(candidate_ids)),
            f"gate {role} identities",
        )
    challenger, incumbent = roles["challenger"], roles["incumbent"]
    require(
        challenger["candidate_ids"] == incumbent["candidate_ids"],
        "gate roles use different rows",
    )
    return {
        "candidate_count": len(challenger["candidate_ids"]),
        "challenger_logloss": float(challenger["logloss"]),
        "incumbent_logloss": float(incumbent["logloss"]),
        "challenger_net_adverse": float(challenger["net_adverse"]),
        "incumbent_net_adverse": float(incumbent["net_adverse"]),
    }


def rebuild_isolated_gate_role(
    helper: Any,
    state: dict[str, Any],
    all_rows: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
    gate_sessions: list[str],
    replay_sessions: list[str],
) -> dict[str, Any]:
    """Rebuild one shadow role without CAL selection or shared portfolio state."""
    require(len(gate_sessions) == 21, "isolated gate length")
    candidates = [row for row in all_rows if row["entry_date"] in set(gate_sessions)]
    require(
        len({row["candidate_id"] for row in candidates}) == len(candidates),
        "isolated gate candidate uniqueness",
    )
    scores = score_state(helper, state, candidates)
    score_index = {row["candidate_id"]: row for row in scores}
    replay_rows = []
    losses = []
    for original in candidates:
        value = dict(original)
        score = score_index[value["candidate_id"]]
        value["_ev_base"] = float(score["ev_base"])
        value["_ev_adverse"] = float(score["ev_adverse"])
        replay_rows.append(value)
        losses.append(-math.log(max(float(score["p_cal"][int(value["scenario"])]), 1e-12)))
    coverage = [row for row in coverage_rows if row["entry_date"] in set(gate_sessions)]
    books = helper.replay_risk(replay_rows, coverage, replay_sessions, gate_sessions[-1])
    net_adverse = math.fsum(
        float(event["net_usd"])
        for event in books["adverse"]
        if event["event"] == "EXIT"
    )
    return {
        "candidate_ids": sorted(row["candidate_id"] for row in candidates),
        "candidate_count": len(candidates),
        "logloss": math.fsum(losses) / len(losses) if losses else None,
        "net_adverse": net_adverse,
        "scores": scores,
        "books": books,
        "starting_cash": STARTING_CASH,
        "cal_rows_used": 0,
    }


def rebuild_shadow_rows(
    helper: Any, proposal: dict[str, Any], role_states: dict[str, dict[str, Any]],
    all_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = [
        value for value in all_rows if value["entry_date"] in set(proposal["gate_sessions"])
    ]
    output = []
    for role, state in role_states.items():
        for score in score_state(helper, state, candidates):
            candidate = next(
                value for value in candidates if value["candidate_id"] == score["candidate_id"]
            )
            output.append({
                "proposal_id": proposal["proposal_id"], "role": role,
                "entry_date": candidate["entry_date"], "ticker": candidate["ticker"],
                "right": candidate["right"], "model_id": state["state_id"], **score,
            })
    return output


def compare_gate_role(saved: dict[str, Any], rebuilt: dict[str, Any], label: str) -> None:
    for key in ("candidate_ids", "candidate_count", "starting_cash", "cal_rows_used"):
        require(saved.get(key) == rebuilt[key], f"{label} {key}")
    assert_close(saved.get("logloss"), rebuilt["logloss"], f"{label} logloss")
    assert_close(saved.get("net_adverse"), rebuilt["net_adverse"], f"{label} net adverse")
    assert_close(saved.get("scores"), rebuilt["scores"], f"{label} scores")
    assert_close(saved.get("books"), rebuilt["books"], f"{label} books", atol=1e-8)


def rebuild_continuous_books(
    helper: Any,
    candidates: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
    sessions: list[str],
    last_entry: str,
    scores: list[dict[str, Any]],
    active_models: dict[str, dict[str, str]],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Rebuild five Jan-Sep books once each; no month/Q3 reset is possible."""
    require(sessions == sorted(set(sessions)) and len(sessions) == 178, "continuous sessions")
    require(
        LAST_ENTRY in sessions and sessions[-1] == "20260917"
        and last_entry == LAST_ENTRY,
        "continuous last entry",
    )
    candidate_index = {row["candidate_id"]: row for row in candidates}
    require(len(candidate_index) == len(candidates), "continuous candidate uniqueness")
    score_index: dict[tuple[str, str], dict[str, Any]] = {}
    for score in scores:
        key = (score.get("policy"), score.get("candidate_id"))
        require(key[0] in POLICIES and key[1] in candidate_index and key not in score_index, "continuous score identity")
        require(score.get("entry_date") == candidate_index[key[1]]["entry_date"], "continuous score date")
        score_index[key] = score
    require(
        set(score_index) == {(policy, candidate_id) for policy in POLICIES for candidate_id in candidate_index},
        "continuous score coverage",
    )
    output = {}
    for policy in POLICIES:
        model_by_candidate, replay_rows = {}, []
        for candidate_id, source in candidate_index.items():
            score = score_index[(policy, candidate_id)]
            value = dict(source)
            value["_ev_base"] = float(score["ev_base"])
            value["_ev_adverse"] = float(score["ev_adverse"])
            replay_rows.append(value)
            model_by_candidate[candidate_id] = score["model_id"]
        books = helper.replay_risk(replay_rows, coverage_rows, sessions, last_entry)
        output[policy] = annotate_books(
            books, policy, model_by_candidate, active_models[policy]
        )
        for cost in COSTS:
            ledger = output[policy][cost]
            first_cash = next((event for event in ledger if "cash" in event), None)
            if first_cash is None:
                require(
                    all(event["event"] not in {"ENTRY", "EXIT"} for event in ledger),
                    "continuous zero-entry book",
                )
            else:
                require(
                    first_cash["event"] == "ENTRY"
                    and first_cash["cash"] <= STARTING_CASH,
                    "continuous book first cash",
                )
            for event in ledger:
                require(event["date"] in sessions, "continuous event calendar")
            entries = {
                event["candidate_id"]: event["model_id"]
                for event in ledger if event["event"] == "ENTRY"
            }
            for event in ledger:
                if event["event"] == "EXIT":
                    require(event["model_id"] == entries[event["candidate_id"]], "open position model identity")
    return output


def compare_books(
    actual: dict[str, dict[str, list[dict[str, Any]]]],
    expected: dict[str, dict[str, list[dict[str, Any]]]],
) -> None:
    require(set(actual) == set(expected) == set(POLICIES), "policy book set")
    for policy in POLICIES:
        require(set(actual[policy]) == set(expected[policy]) == set(COSTS), "cost book set")
        for cost in COSTS:
            assert_close(actual[policy][cost], expected[policy][cost], f"book {policy} {cost}", atol=1e-8)


def validate_bridge(
    old_candidates: list[dict[str, Any]],
    bridge_candidates: list[dict[str, Any]],
    bridge_coverage: list[dict[str, Any]],
    combined_candidates: list[dict[str, Any]],
) -> dict[str, int]:
    expected = {
        (ticker, entry): exit_day
        for entry, exit_day in (("20260629", "20260701"), ("20260630", "20260702"))
        for ticker in TICKERS
    }
    coverage_index = {}
    for value in bridge_coverage:
        key = (value.get("ticker"), value.get("entry_date"))
        require(key in expected and key not in coverage_index, "bridge coverage identity")
        require(value.get("exit_date") == expected[key], "bridge H2 exit")
        candidate_ids = value.get("candidate_ids")
        if key[1] == "20260630":
            require(
                value.get("status") == "NO_SERIES"
                and value.get("reason") == "NO_1_TO_8_DTE_SERIES_ALLOWING_H2"
                and candidate_ids == [],
                "bridge June30 no-series semantics",
            )
        elif value.get("status") == "CANDIDATES_BUILT":
            require(
                value.get("reason") is None
                and isinstance(candidate_ids, list)
                and candidate_ids
                and len(candidate_ids) == len(set(candidate_ids)),
                "bridge built coverage candidates",
            )
        else:
            require(
                value.get("status") == "NO_DECISION_CANDIDATE"
                and value.get("reason") == "NO_VALID_1030_CALL_OR_PUT"
                and candidate_ids == [],
                "bridge June29 no-decision semantics",
            )
        coverage_index[key] = value
    require(set(coverage_index) == set(expected), "bridge six coverage rows")
    bridge_index = {}
    for value in bridge_candidates:
        key, candidate_id = (value.get("ticker"), value.get("entry_date")), value.get("candidate_id")
        require(key in expected and value.get("exit_date") == expected[key], "bridge candidate scope")
        require(isinstance(candidate_id, str) and candidate_id not in bridge_index, "bridge candidate identity")
        require(candidate_id in coverage_index[key]["candidate_ids"], "bridge candidate coverage")
        bridge_index[candidate_id] = value
    require(
        set(bridge_index)
        == {
            candidate_id
            for value in coverage_index.values()
            for candidate_id in value["candidate_ids"]
        },
        "bridge candidates/coverage mismatch",
    )
    old_index = {value["candidate_id"]: value for value in old_candidates}
    combined_index = {value["candidate_id"]: value for value in combined_candidates}
    require(len(old_index) == len(old_candidates) == 3234, "old universe preservation count")
    require(len(combined_index) == len(combined_candidates), "combined candidate uniqueness")
    require(not set(old_index) & set(bridge_index), "bridge overlaps old candidates")
    require(set(combined_index) == set(old_index) | set(bridge_index), "combined universe identity")
    for candidate_id, value in old_index.items():
        require(combined_index[candidate_id] == value, "old candidate mutated")
    return {
        "old_candidates": len(old_index),
        "bridge_candidates": len(bridge_index),
        "combined_candidates": len(combined_index),
        "bridge_coverage_rows": len(coverage_index),
    }


def validate_policy_timeline(
    sessions: list[str],
    plans: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
    gates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, int]:
    require(sessions == sorted(set(sessions)) and len(sessions) == 178, "timeline sessions")
    require(len(timeline) == len(sessions) * len(POLICIES), "timeline row count")
    timeline_index = {}
    for value in timeline:
        require(
            set(value)
            == {
                "date", "policy", "phase_order", "active_model_before",
                "active_model_after", "created_proposal_id", "resolved_proposal_ids",
            },
            "timeline row schema",
        )
        key = (value["date"], value["policy"])
        require(
            value["date"] in sessions
            and value["policy"] in POLICIES
            and key not in timeline_index,
            "timeline identity",
        )
        require(value["phase_order"] == "RESOLVE_CREATE_ACTIVATE_SCORE_EXECUTE", "daily phase order")
        timeline_index[key] = value
    plans_by_day = {value["creation_date"]: value for value in plans}
    proposals_by_created = {}
    proposals_by_resolved = {}
    for value in proposals:
        require(
            set(value)
            == {
                "proposal_id", "cadence", "created_date", "challenger_id",
                "incumbent_snapshot_id", "gate_sessions", "maturity_date",
                "status", "resolved_at", "effective_at", "comparison",
            },
            "proposal row schema",
        )
        require(value["cadence"] in {"MONTHLY", "WEEKLY"}, "proposal cadence")
        key = (value["cadence"], value["created_date"])
        require(key not in proposals_by_created, "proposal duplicate creation")
        require(value["proposal_id"] == f"{value['cadence']}_{value['created_date']}", "proposal identity")
        require(value["challenger_id"] == plans_by_day[value["created_date"]]["state_id"], "proposal challenger")
        proposals_by_created[key] = value
        if value["resolved_at"] is not None:
            proposals_by_resolved.setdefault((value["cadence"], value["resolved_at"]), []).append(value)
    schedule = creation_dates(sessions)
    require(
        set(proposals_by_created)
        == {
            (cadence.upper(), day)
            for cadence in ("monthly", "weekly")
            for day in schedule[cadence]
        },
        "proposal creation schedule",
    )
    active = {
        "FROZEN_CONTEXT182": "FROZEN_CONTEXT182_H1",
        "MONTHLY_RAW": "NO_ACTIVE_MODEL", "WEEKLY_RAW": "NO_ACTIVE_MODEL",
        "MONTHLY_GUARDED": "FROZEN_CONTEXT182_H1",
        "WEEKLY_GUARDED": "FROZEN_CONTEXT182_H1",
    }
    for day in sessions:
        for policy in POLICIES:
            value, before = timeline_index[(day, policy)], active[policy]
            created, resolved = None, []
            if policy == "FROZEN_CONTEXT182":
                after = before
            elif policy.endswith("_RAW"):
                cadence = policy.removesuffix("_RAW")
                plan = plans_by_day.get(day)
                after = plan["state_id"] if plan and cadence in plan["frequencies"] else before
            else:
                cadence = policy.removesuffix("_GUARDED")
                after = before
                matured = sorted(
                    proposals_by_resolved.get((cadence, day), []),
                    key=lambda item: item["created_date"],
                )
                for proposal in matured:
                    if gates is not None:
                        rebuilt_status, rebuilt_after = resolve_proposal(
                            proposal, after, gates.get(proposal["proposal_id"])
                        )
                        require(proposal["status"] == rebuilt_status, "proposal gate decision")
                        after = rebuilt_after
                    elif proposal["status"] == "PROMOTED":
                        require(after == proposal["incumbent_snapshot_id"], "promotion incumbent conservation")
                        after = proposal["challenger_id"]
                    elif proposal["status"] == "STALE_CHALLENGER_REJECTED":
                        require(after != proposal["incumbent_snapshot_id"], "false stale proposal")
                    else:
                        require(proposal["status"] in {"REJECTED", "REJECTED_NO_GATE_ROWS"}, "resolved proposal status")
                    resolved.append(proposal["proposal_id"])
                proposal = proposals_by_created.get((cadence, day))
                if proposal is not None:
                    require(proposal["incumbent_snapshot_id"] == after, "proposal snapshot at creation")
                    created = proposal["proposal_id"]
            require(
                value["active_model_before"] == before
                and value["active_model_after"] == after
                and value["created_proposal_id"] == created
                and value["resolved_proposal_ids"] == resolved,
                f"timeline transition {day} {policy}",
            )
            active[policy] = after
    return {
        "rows": len(timeline),
        "proposals": len(proposals),
        "promotions": sum(value["status"] == "PROMOTED" for value in proposals),
        "pending": sum(value["status"] == "PENDING_BEYOND_DECISION_CUTOFF" for value in proposals),
    }


def extended_book_metrics(
    helper: Any, ledger: list[dict[str, Any]], sessions: list[str],
) -> dict[str, Any]:
    metrics = helper.book_metrics(ledger)
    exits = [value for value in ledger if value["event"] == "EXIT"]
    entries = [value for value in ledger if value["event"] == "ENTRY"]
    months = sorted({day[:6] for day in sessions})
    monthly = {month: 0.0 for month in months}
    monthly_entry = {month: 0.0 for month in months}
    side = {right: 0.0 for right in RIGHTS}
    for value in exits:
        monthly[value["date"][:6]] += float(value["net_usd"])
        monthly_entry[value["entry_date"][:6]] += float(value["net_usd"])
        side[value["right"]] += float(value["net_usd"])
    net = math.fsum(float(value["net_usd"]) for value in exits)
    largest = max(exits, key=lambda value: abs(float(value["net_usd"])), default=None)
    event_counts = {
        event: sum(value["event"] == event for value in ledger)
        for event in sorted({value["event"] for value in ledger})
    }
    details = {
        "monthly_net_including_zeros": monthly,
        "monthly_convention": "exit_date_realization",
        "monthly_net_by_entry_cohort_including_zeros": monthly_entry,
        "block_net_by_exit_realization": {
            "H1_2026": math.fsum(value for month, value in monthly.items() if month <= "202606"),
            "Q3_PARTIAL_2026": math.fsum(value for month, value in monthly.items() if month >= "202607"),
        },
        "block_net_by_entry_cohort": {
            "H1_2026": math.fsum(value for month, value in monthly_entry.items() if month <= "202606"),
            "Q3_PARTIAL_2026": math.fsum(value for month, value in monthly_entry.items() if month >= "202607"),
        },
        "side_net": side,
        "event_counts": event_counts,
        "selected_missing_or_lower_bound": sum(
            value.get("status") in {"MISSING_EXIT_SOURCE", "MISSING_EXIT_QUOTE"}
            for value in exits
        ),
        "largest_trade": None if largest is None else {
            "candidate_id": largest["candidate_id"], "date": largest["date"],
            "ticker": largest["ticker"], "right": largest["right"],
            "model_id": largest["model_id"], "net_usd": float(largest["net_usd"]),
        },
        "largest_month_by_absolute_net": max(monthly, key=lambda month: abs(monthly[month])),
        "net_without_largest_month": net - monthly[max(monthly, key=lambda month: abs(monthly[month]))],
        "net_without_largest_trade": net - (float(largest["net_usd"]) if largest else 0.0),
    }
    metrics["details"] = details
    require(len(entries) == metrics["trades"], "entry/exit trade count")
    return metrics


def combined_probability_ev(
    helper: Any, rows: list[dict[str, Any]], policy: str,
    selected: set[str] | None, observed_only: bool,
) -> dict[str, Any]:
    probability = helper.probability_metrics(
        rows, policy, selected_ids=selected, observed_only=observed_only
    )
    probability["logloss"] = probability.pop("log_loss")
    ev = helper.ev_metrics(
        rows, policy, selected_ids=selected, observed_only=observed_only
    )
    probability["ev"] = {
        cost: {"bias": ev[cost]["bias"], "mae": ev[cost]["mae"]}
        for cost in COSTS
    }
    return probability


def validate_summary(
    helper: Any, summary: dict[str, Any], rows: list[dict[str, Any]],
    books: dict[str, dict[str, list[dict[str, Any]]]], sessions: list[str],
    proposals: list[dict[str, Any]], timeline: list[dict[str, Any]],
    bridge_count: int,
) -> None:
    require(
        set(summary) == {
            "schema", "status", "scope", "policies", "raw_minus_guarded",
            "proposal_status_counts", "guard_diagnostics", "flags",
        }
        and summary["schema"] == "weekly_context_adaptation_summary_v1"
        and summary["status"] == "COMPLETE_SEEN_DEVELOPMENT_NOT_PROMOTED",
        "summary schema/status",
    )
    require(summary["scope"] == {
        "sessions": 178, "candidates": len(rows), "bridge_candidates": bridge_count,
        "physical_fits": 42, "monthly_creations": 9, "weekly_creations": 38,
    }, "summary scope")
    rebuilt_policies = {}
    for policy in POLICIES:
        selected = helper.selected_ids(books[policy]["adverse"])
        require(selected == helper.selected_ids(books[policy]["base"]), "summary shared selections")
        rebuilt_policies[policy] = {
            "economics": {
                cost: extended_book_metrics(helper, books[policy][cost], sessions)
                for cost in COSTS
            },
            "probability_ev": {
                "all": combined_probability_ev(helper, rows, policy, None, False),
                "selected": combined_probability_ev(helper, rows, policy, selected, False),
                "all_observed_only": combined_probability_ev(helper, rows, policy, None, True),
                "selected_observed_only": combined_probability_ev(helper, rows, policy, selected, True),
            },
            "selected_ids": sorted(selected),
            "filled_ids": sorted({
                value["candidate_id"]
                for value in books[policy]["adverse"] if value["event"] == "ENTRY"
            }),
            "adverse_net_minus_frozen": 0.0,
        }
    frozen_net = rebuilt_policies["FROZEN_CONTEXT182"]["economics"]["adverse"]["net_usd"]
    for policy in POLICIES:
        rebuilt_policies[policy]["adverse_net_minus_frozen"] = (
            rebuilt_policies[policy]["economics"]["adverse"]["net_usd"] - frozen_net
        )
    assert_close(summary["policies"], rebuilt_policies, "summary policies", atol=1e-8)
    raw_minus_guarded = {}
    for cadence in ("MONTHLY", "WEEKLY"):
        raw, guarded = rebuilt_policies[f"{cadence}_RAW"], rebuilt_policies[f"{cadence}_GUARDED"]
        raw_minus_guarded[cadence] = {
            "adverse_net_usd": raw["economics"]["adverse"]["net_usd"] - guarded["economics"]["adverse"]["net_usd"],
            "all_logloss": raw["probability_ev"]["all"]["logloss"] - guarded["probability_ev"]["all"]["logloss"],
            "all_adverse_ev_mae": raw["probability_ev"]["all"]["ev"]["adverse"]["mae"] - guarded["probability_ev"]["all"]["ev"]["adverse"]["mae"],
        }
    assert_close(summary["raw_minus_guarded"], raw_minus_guarded, "summary raw/guarded", atol=1e-8)
    counts = {
        status: sum(value["status"] == status for value in proposals)
        for status in sorted({value["status"] for value in proposals})
    }
    require(summary["proposal_status_counts"] == counts, "summary proposal counts")
    guard_diagnostics = {}
    last_index = len(sessions) - 1
    for cadence in ("MONTHLY", "WEEKLY"):
        policy = f"{cadence}_GUARDED"
        own = sorted(
            (value for value in proposals if value["cadence"] == cadence),
            key=lambda value: value["created_date"],
        )
        promotions = [value for value in own if value["status"] == "PROMOTED"]
        final_active = next(
            value["active_model_after"]
            for value in reversed(timeline)
            if value["policy"] == policy
        )
        first_active = next(
            index for index, day in enumerate(sessions)
            if next(
                value["active_model_after"] for value in timeline
                if value["policy"] == policy and value["date"] == day
            ) == final_active
        )
        latest = promotions[-1]["effective_at"] if promotions else None
        transfer = []
        for promotion_index, proposal in enumerate(promotions):
            effective_index = sessions.index(proposal["effective_at"])
            next_effective = (
                promotions[promotion_index + 1]["effective_at"]
                if promotion_index + 1 < len(promotions) else None
            )
            period_end_index = (
                sessions.index(next_effective) - 1 if next_effective is not None else last_index
            )
            period_sessions = sessions[effective_index:period_end_index + 1]
            period_rows = [value for value in rows if value["entry_date"] in set(period_sessions)]
            period_exits = [
                value for value in books[policy]["adverse"]
                if value["event"] == "EXIT" and value["model_id"] == proposal["challenger_id"]
            ]
            period_selected = {
                value["candidate_id"]
                for value in books[policy]["adverse"]
                if value["event"] in {"ENTRY", "NO_FILL", "CAPITAL_BLOCKED"}
                and value.get("model_id") == proposal["challenger_id"]
                and value.get("candidate_id") is not None
            }
            period_months = sorted({day[:6] for day in period_sessions})
            monthly_entry = {month: 0.0 for month in period_months}
            for value in period_exits:
                monthly_entry[value["entry_date"][:6]] += float(value["net_usd"])
            probability_ev = {
                "all": combined_probability_ev(helper, period_rows, policy, None, False),
                "selected": combined_probability_ev(helper, period_rows, policy, period_selected, False),
                "all_observed_only": combined_probability_ev(helper, period_rows, policy, None, True),
                "selected_observed_only": combined_probability_ev(helper, period_rows, policy, period_selected, True),
            }
            transfer.append({
                "model_id": proposal["challenger_id"],
                "effective_at": proposal["effective_at"],
                "period_end_inclusive": sessions[period_end_index],
                "sessions": len(period_sessions),
                "candidates": len(period_rows),
                "trades": len(period_exits),
                "probability_ev": probability_ev,
                "main_book_adverse_exit_net": math.fsum(float(value["net_usd"]) for value in period_exits),
                "monthly_net_by_entry_cohort_including_zeros": monthly_entry,
                "block_net_by_entry_cohort": {
                    "H1_2026": math.fsum(value for month, value in monthly_entry.items() if month <= "202606"),
                    "Q3_PARTIAL_2026": math.fsum(value for month, value in monthly_entry.items() if month >= "202607"),
                },
            })
        guard_diagnostics[cadence] = {
            "final_active_model": final_active,
            "promotions": len(promotions),
            "rejections": sum(value["status"] == "REJECTED" for value in own),
            "stale": sum(value["status"] == "STALE_CHALLENGER_REJECTED" for value in own),
            "pending": sum(value["status"] == "PENDING_BEYOND_DECISION_CUTOFF" for value in own),
            "active_model_age_sessions": last_index - first_active + 1,
            "sessions_since_last_acceptance": len(sessions) if latest is None else last_index - sessions.index(latest),
            "observed_post_activation_transfer": transfer,
        }
    assert_close(summary["guard_diagnostics"], guard_diagnostics, "summary guard diagnostics", atol=1e-8)
    require(summary["flags"] == {
        "development_seen": True, "promotion_approved": False,
        "technical_ready": False, "raw_read": False, "api_read": False,
        "future_labels_used": False, "frozen_refit": False,
    }, "summary flags")


def snapshot_paths(paths: dict[str, Path], expected: dict[str, str]) -> dict[str, dict[str, Any]]:
    require(set(paths) == set(expected), "snapshot authority set")
    snapshots = {}
    for name, path in paths.items():
        path = plain(path, name)
        value = {"path": str(path), **pin(path)}
        require(path.is_file() and value["sha256"] == expected[name], f"authority {name}")
        snapshots[name] = value
    return snapshots


def revalidate(snapshots: dict[str, dict[str, Any]], payloads: dict[Path, dict[str, Any]]) -> None:
    for name, value in snapshots.items():
        verify(Path(value["path"]), value, f"closing authority {name}")
    for path, value in payloads.items():
        verify(path, value, f"closing payload {path}")


def admit_producer_bundle(
    producer_manifest_sha256: str,
    producer_sha256: str,
    producer_tests_sha256: str,
    bridge_manifest_sha256: str,
    bridge_audit_sha256: str,
    auditor_sha256: str,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[Path, dict[str, Any]]]:
    manifest_path = plain(PRODUCER_ROOT / "manifest.json", "producer manifest")
    manifest_pin = {"path": str(manifest_path), **pin(manifest_path)}
    require(manifest_pin["sha256"] == producer_manifest_sha256, "producer manifest authority")
    manifest = read_json(manifest_path)
    require(
        set(manifest) == {
            "schema", "status", "external_authorities", "consumed_payloads",
            "implementation", "outputs", "flags",
        }
        and manifest["schema"] == PRODUCER_SCHEMA
        and manifest["status"] == PRODUCER_STATUS,
        "producer manifest schema/status",
    )
    require(
        manifest["flags"]
        == {
            "raw_read": False, "api_read": False, "broker_read": False,
            "production_changed": False, "future_labels_used": False,
            "models_fit": True, "frozen_fit": False, "seen_development": True,
            "promotion_approved": False,
        },
        "producer flags",
    )
    authorities = manifest["external_authorities"]
    require(set(authorities) == EXTERNAL_KEYS, "external authority closure")
    snapshots = {"producer_manifest": manifest_pin}
    for name, value in authorities.items():
        require(set(value) == {"path", "bytes", "sha256"}, f"authority schema {name}")
        path = plain(Path(value["path"]), f"authority {name}")
        verify(path, value, f"authority {name}")
        snapshots[name] = dict(value)
    for name, digest in FROZEN_EXTERNAL_SHA256.items():
        require(authorities[name]["sha256"] == digest, f"frozen authority {name}")
    require(
        producer_sha256 == PRODUCER_SHA256
        and authorities["producer"]["sha256"] == PRODUCER_SHA256,
        "producer code argument",
    )
    require(
        producer_tests_sha256 == PRODUCER_TESTS_SHA256
        and authorities["tests"]["sha256"] == PRODUCER_TESTS_SHA256,
        "producer tests argument",
    )
    require(
        Path(authorities["producer"]["path"]).name == "evaluate_weekly_context_adaptation.py"
        and Path(authorities["tests"]["path"]).name == "test_evaluate_weekly_context_adaptation.py",
        "producer implementation paths",
    )
    require(authorities["bridge_manifest"]["sha256"] == bridge_manifest_sha256, "bridge manifest argument")
    require(authorities["bridge_audit"]["sha256"] == bridge_audit_sha256, "bridge audit argument")
    self_path = plain(Path(__file__), "auditor self")
    self_pin = {"path": str(self_path), **pin(self_path)}
    require(self_pin["sha256"] == auditor_sha256, "auditor self authority")
    snapshots["auditor"] = self_pin
    independent_helper = plain(HELPER, "independent auditor helper")
    independent_helper_pin = {"path": str(independent_helper), **pin(independent_helper)}
    require(independent_helper_pin["sha256"] == HELPER_SHA256, "independent helper authority")
    snapshots["independent_helper"] = independent_helper_pin
    consumed = manifest["consumed_payloads"]
    require(isinstance(consumed, dict) and len(consumed) == 27, "consumed payload closure")
    payloads = {}
    for text_path, value in consumed.items():
        require(set(value) == {"path", "bytes", "sha256"} and value["path"] == text_path, "consumed payload schema")
        path = plain(Path(text_path), "consumed payload")
        verify(path, value, f"consumed payload {path.name}")
        payloads[path] = dict(value)
    implementation = manifest["implementation"]
    require(set(implementation) == {"producer", "tests"}, "producer implementation closure")
    for name, value in implementation.items():
        require(value == authorities[name], f"implementation authority {name}")
    require(set(manifest["outputs"]) == OUTPUT_FILES, "producer output closure")
    for name, value in manifest["outputs"].items():
        require(set(value) == {"bytes", "sha256"}, f"output pin schema {name}")
        verify(PRODUCER_ROOT / name, value, f"producer output {name}")
        payloads[plain(PRODUCER_ROOT / name, f"output {name}")] = dict(value)
    bridge_manifest = read_json(Path(authorities["bridge_manifest"]["path"]))
    require(
        bridge_manifest.get("schema") == "weekly_h2_boundary_bridge_manifest_v1"
        and bridge_manifest.get("status") == "COMPLETE_WEEKLY_H2_BOUNDARY_BRIDGE_NOT_EVALUATED",
        "bridge manifest schema/status",
    )
    bridge_audit = read_json(Path(authorities["bridge_audit"]["path"]))
    require(str(bridge_audit.get("status", "")).startswith("PASS"), "bridge audit status")
    require(
        bridge_audit.get("inputs", {}).get("producer_manifest")
        == authorities["bridge_manifest"],
        "bridge audit binding",
    )
    return manifest, snapshots, payloads


def output_rows(name: str) -> list[dict[str, Any]]:
    return read_jsonl(PRODUCER_ROOT / name)


def payload_under(
    payloads: dict[Path, dict[str, Any]], root: Path, name: str,
) -> Path:
    root = Path(os.path.abspath(root))
    matches = [path for path in payloads if path.parent == root and path.name == name]
    require(len(matches) == 1, f"payload lookup {root} {name}")
    return matches[0]


def authority_root(snapshots: dict[str, dict[str, Any]], name: str) -> Path:
    return Path(snapshots[name]["path"]).parent


def attach_context(
    helper: Any, candidates: list[dict[str, Any]], context_rows: list[dict[str, Any]],
) -> None:
    context_index = {}
    for value in context_rows:
        key = (value.get("ticker"), value.get("date"))
        require(key not in context_index, "context identity collision")
        context_index[key] = value
    for value in candidates:
        key = (value["ticker"], value["entry_date"])
        require(key in context_index, "candidate context missing")
        context = context_index[key]
        value["_x_context"] = helper.context182(value, context)
        value["_context_status"] = context["status"]
        value["_context_state_valid"] = context["state_valid"]


def numeric_audit_from_sealed_payloads(
    helper: Any,
    snapshots: dict[str, dict[str, Any]],
    payloads: dict[Path, dict[str, Any]],
) -> dict[str, Any]:
    roots = {
        name: authority_root(snapshots, name)
        for name in (
            "dataset_h1", "dataset_q3", "context_h1", "context_q3",
            "comparison_h1", "frozen_ev", "bridge_manifest",
        )
    }
    h1_candidates = read_jsonl(payload_under(payloads, roots["dataset_h1"], "candidates.jsonl"))
    q3_candidates = read_jsonl(payload_under(payloads, roots["dataset_q3"], "candidates.jsonl"))
    bridge_candidates = read_jsonl(payload_under(payloads, roots["bridge_manifest"], "candidates.jsonl"))
    h1_coverage = read_json(payload_under(payloads, roots["dataset_h1"], "coverage.json"))["rows"]
    q3_coverage = read_json(payload_under(payloads, roots["dataset_q3"], "coverage.json"))["rows"]
    bridge_coverage = read_json(payload_under(payloads, roots["bridge_manifest"], "coverage_overlay.json"))["rows"]
    old_candidates = [*h1_candidates, *q3_candidates]
    combined = [*old_candidates, *bridge_candidates]
    validate_bridge(old_candidates, bridge_candidates, bridge_coverage, combined)
    h1_context = read_jsonl(payload_under(payloads, roots["context_h1"], "context.jsonl"))
    q3_context = read_jsonl(payload_under(payloads, roots["context_q3"], "context.jsonl"))
    attach_context(helper, combined, [*h1_context, *q3_context])
    rows_by_id = {value["candidate_id"]: value for value in combined}
    require(len(rows_by_id) == len(combined), "combined candidate IDs")
    calendar_identities = [
        (value["ticker"], value["entry_date"])
        for value in [*h1_coverage, *q3_coverage]
    ]
    require(
        len(calendar_identities) == len(set(calendar_identities)) == 2790,
        "full calendar ticker/date identities",
    )
    full_calendar = sorted({day for _, day in calendar_identities})
    require(len(full_calendar) == 930, "full official calendar session count")
    by_calendar_day: dict[str, set[str]] = {day: set() for day in full_calendar}
    for ticker, day in calendar_identities:
        by_calendar_day[day].add(ticker)
    require(
        all(tickers == set(TICKERS) for tickers in by_calendar_day.values()),
        "full official calendar ticker coverage",
    )

    plan_document = read_json(PRODUCER_ROOT / "fit_plans.json")
    require(
        set(plan_document) == {"schema", "count", "plans"}
        and plan_document["schema"] == "weekly_context_adaptation_fit_plans_v1"
        and plan_document["count"] == 42,
        "fit plan document",
    )
    plans, states = plan_document["plans"], output_rows("states.jsonl")
    timeline, proposals = output_rows("policy_timeline.jsonl"), output_rows("proposals.jsonl")
    sessions = sorted({value["date"] for value in timeline})
    require(
        sessions == [day for day in full_calendar if "20260102" <= day <= "20260917"]
        and len(sessions) == 178,
        "evaluation calendar authority",
    )
    validate_fit_plan_schedule(sessions, plans, states)
    states_by_id = {value["state_id"]: value for value in states}
    plans_by_id = {value["state_id"]: value for value in plans}
    require(set(states_by_id) == set(plans_by_id), "state/plan identities")
    for state_id, state in states_by_id.items():
        validate_saved_state(
            helper, state, plans_by_id[state_id], rows_by_id, full_calendar
        )
    timeline_result = validate_policy_timeline(sessions, plans, proposals, timeline)
    active_models = {
        policy: {
            value["date"]: value["active_model_after"]
            for value in timeline if value["policy"] == policy
        }
        for policy in POLICIES
    }

    comparison_root = roots["comparison_h1"]
    artifact_paths = {}
    for kind in ("transform", "model", "calibration"):
        matches = [
            path for path in payloads
            if path.parent == comparison_root
            and "context182" in path.name.lower() and kind in path.name.lower()
        ]
        require(len(matches) == 1, f"frozen context artifact {kind}")
        artifact_paths[kind] = matches[0]
    frozen_model_path = payload_under(payloads, roots["frozen_ev"], "model.json")
    means_path = payload_under(payloads, roots["frozen_ev"], "conditional_means.json")
    frozen_ev_model = read_json(frozen_model_path)
    frozen_state = {
        "state_id": "FROZEN_CONTEXT182_H1",
        "feature_order": read_json(artifact_paths["transform"])["feature_order"],
        "transform": read_json(artifact_paths["transform"]),
        "model": read_json(artifact_paths["model"]),
        "prior": frozen_ev_model["train_prior"],
        "conditional_means": read_json(means_path),
        "calibration": read_json(artifact_paths["calibration"]),
        "inference": "FROZEN_H1_HELPER",
    }
    all_states = {**states_by_id, frozen_state["state_id"]: frozen_state}
    producer_scores = output_rows("candidate_scores.jsonl")
    eval_ids = {value["candidate_id"] for value in combined if value["entry_date"] in set(sessions)}
    require(
        len(producer_scores) == len(eval_ids) * len(POLICIES)
        and {(value["policy"], value["candidate_id"]) for value in producer_scores}
        == {(policy, candidate_id) for policy in POLICIES for candidate_id in eval_ids},
        "candidate score closure",
    )
    rebuilt_scores = []
    for saved in producer_scores:
        require(
            set(saved)
            == {
                "policy", "candidate_id", "entry_date", "ticker", "right", "model_id",
                "p_model", "p_cal", "ev_base", "ev_adverse", "scenario",
                "payoff_is_lower_bound", "is_bridge",
            },
            "candidate score schema",
        )
        candidate = rows_by_id[saved["candidate_id"]]
        require(
            saved["policy"] in POLICIES
            and saved["entry_date"] == candidate["entry_date"]
            and saved["ticker"] == candidate["ticker"]
            and saved["right"] == candidate["right"]
            and saved["scenario"] == candidate["scenario"]
            and saved["payoff_is_lower_bound"] == candidate["payoff_is_lower_bound"]
            and saved["is_bridge"] == (saved["candidate_id"] in {row["candidate_id"] for row in bridge_candidates}),
            "candidate score identity",
        )
        validate_score_model_clock(saved, candidate, active_models)
        require(saved["model_id"] in all_states, "candidate model authority")
        rebuilt = score_state(helper, all_states[saved["model_id"]], [candidate])[0]
        rebuilt.update({
            "policy": saved["policy"], "entry_date": candidate["entry_date"],
            "model_id": saved["model_id"], "context_status": None,
            "context_state_valid": None,
        })
        rebuilt_scores.append(rebuilt)
        candidate[f"_p_{saved['policy']}"] = rebuilt["p_cal"]
        candidate[f"_ev_{saved['policy']}_base"] = rebuilt["ev_base"]
        candidate[f"_ev_{saved['policy']}_adverse"] = rebuilt["ev_adverse"]
        candidate["_model_label_eligible"] = True
    compare_scores(producer_scores, rebuilt_scores, label="adaptive scores")
    frozen_saved = {
        value["candidate_id"]: value
        for value in producer_scores if value["policy"] == "FROZEN_CONTEXT182"
    }
    original_frozen_rows = []
    for authority in ("comparison_h1", "comparison_q3"):
        root = authority_root(snapshots, authority)
        matches = [
            path for path in payloads
            if path.parent == root and path.suffix == ".jsonl" and "score" in path.name.lower()
        ]
        require(len(matches) == 1, f"frozen comparison scores {authority}")
        original_frozen_rows.extend(read_jsonl(matches[0]))
    original_index = {value["candidate_id"]: value for value in original_frozen_rows}
    require(len(original_index) == len(original_frozen_rows), "frozen comparison score identities")
    bridge_ids = {value["candidate_id"] for value in bridge_candidates}
    expected_common = eval_ids - bridge_ids
    require(
        set(original_index) & set(frozen_saved) == expected_common,
        "frozen common-authority candidate closure",
    )
    for candidate_id in expected_common:
        original, saved = original_index[candidate_id], frozen_saved[candidate_id]
        assert_close(saved["p_cal"], original["p_context182"], "frozen authority probability")
        assert_close(saved["ev_base"], original["ev_context182_base"], "frozen authority EV base")
        assert_close(saved["ev_adverse"], original["ev_context182_adverse"], "frozen authority EV adverse")

    coverage_index = {}
    for value in [*h1_coverage, *q3_coverage]:
        key = (value["ticker"], value["entry_date"])
        if value["entry_date"] in set(sessions):
            require(key not in coverage_index, "economic coverage collision")
            coverage_index[key] = value
    for value in bridge_coverage:
        coverage_index[(value["ticker"], value["entry_date"])] = value
    require(
        set(coverage_index) == {(ticker, day) for ticker in TICKERS for day in sessions},
        "continuous economic coverage",
    )
    books = rebuild_continuous_books(
        helper, [rows_by_id[value] for value in sorted(eval_ids)],
        list(coverage_index.values()), sessions, LAST_ENTRY,
        producer_scores, active_models,
    )
    saved_books = {
        policy: {
            cost: output_rows(f"ledger_{policy.lower()}_{cost}.jsonl")
            for cost in COSTS
        }
        for policy in POLICIES
    }
    compare_books(saved_books, books)
    gate_rows = output_rows("gate_replays.jsonl")
    gate_index = {}
    for value in gate_rows:
        require(
            set(value)
            == {
                "proposal_id", "role", "sessions", "candidate_ids", "logloss",
                "net_adverse", "adverse_metrics", "ledger_events",
            }
            and value["role"] in {"CHALLENGER", "INCUMBENT_SNAPSHOT"},
            "gate replay schema",
        )
        key = (value["proposal_id"], value["role"])
        require(key not in gate_index, "gate replay duplicate")
        gate_index[key] = value
    rebuilt_shadow = []
    gate_results: dict[str, dict[str, Any]] = {}
    for proposal in proposals:
        gate_sessions = proposal_gate_sessions(proposal["created_date"], sessions)
        require(proposal["gate_sessions"] == gate_sessions, "proposal gate calendar")
        resolution = proposal_resolution_day(gate_sessions, sessions, combined, sessions[-1])
        require(
            proposal["maturity_date"] == resolution
            and proposal["resolved_at"] == resolution,
            "proposal independent maturity",
        )
        if resolution is None:
            require(proposal["status"] == "PENDING_BEYOND_DECISION_CUTOFF", "tail proposal pending")
            require(proposal["effective_at"] is None and proposal["comparison"] is None, "pending proposal fields")
            require(not any(key[0] == proposal["proposal_id"] for key in gate_index), "pending gate emitted")
            rebuilt_shadow.extend(rebuild_shadow_rows(
                helper, proposal,
                {
                    "CHALLENGER": all_states[proposal["challenger_id"]],
                    "INCUMBENT_SNAPSHOT": all_states[proposal["incumbent_snapshot_id"]],
                },
                combined,
            ))
            continue
        replay_calendar = sessions[sessions.index(proposal["created_date"]):sessions.index(resolution) + 1]
        role_states = {
            "CHALLENGER": all_states[proposal["challenger_id"]],
            "INCUMBENT_SNAPSHOT": all_states[proposal["incumbent_snapshot_id"]],
        }
        rebuilt_roles = {}
        for role, role_state in role_states.items():
            rebuilt = rebuild_isolated_gate_role(
                helper, role_state, combined, list(coverage_index.values()),
                gate_sessions, replay_calendar,
            )
            saved = gate_index[(proposal["proposal_id"], role)]
            require(saved["sessions"] == gate_sessions, "gate saved sessions")
            require(saved["candidate_ids"] == rebuilt["candidate_ids"], "gate saved candidates")
            assert_close(saved["logloss"], rebuilt["logloss"], "gate saved logloss")
            assert_close(saved["net_adverse"], rebuilt["net_adverse"], "gate saved net")
            assert_close(saved["ledger_events"], rebuilt["books"], "gate saved books", atol=1e-8)
            assert_close(
                saved["adverse_metrics"], helper.book_metrics(rebuilt["books"]["adverse"]),
                "gate saved adverse metrics", atol=1e-8,
            )
            rebuilt_roles[role] = rebuilt
            for score in rebuilt["scores"]:
                candidate = rows_by_id[score["candidate_id"]]
                rebuilt_shadow.append({
                    "proposal_id": proposal["proposal_id"], "role": role,
                    "entry_date": candidate["entry_date"], "ticker": candidate["ticker"],
                    "right": candidate["right"], "model_id": role_state["state_id"],
                    **score,
                })
        gate = {
            "candidate_count": rebuilt_roles["CHALLENGER"]["candidate_count"],
            "challenger_logloss": rebuilt_roles["CHALLENGER"]["logloss"],
            "incumbent_logloss": rebuilt_roles["INCUMBENT_SNAPSHOT"]["logloss"],
            "challenger_net_adverse": rebuilt_roles["CHALLENGER"]["net_adverse"],
            "incumbent_net_adverse": rebuilt_roles["INCUMBENT_SNAPSHOT"]["net_adverse"],
        }
        gate_results[proposal["proposal_id"]] = gate
        require(
            proposal["effective_at"]
            == (proposal["resolved_at"] if proposal["status"] == "PROMOTED" else None),
            "proposal effective clock",
        )
        expected_comparison = {key: gate[key] for key in (
            "challenger_logloss", "incumbent_logloss", "challenger_net_adverse",
            "incumbent_net_adverse",
        )}
        assert_close(proposal["comparison"], expected_comparison, "proposal comparison")
    shadow_rows = output_rows("shadow_predictions.jsonl")
    shadow_index = {(value["proposal_id"], value["role"], value["candidate_id"]): value for value in shadow_rows}
    require(len(shadow_index) == len(shadow_rows) == len(rebuilt_shadow), "shadow prediction closure")
    for rebuilt in rebuilt_shadow:
        saved = shadow_index[(rebuilt["proposal_id"], rebuilt["role"], rebuilt["candidate_id"])]
        require(
            set(saved)
            == {
                "proposal_id", "role", "candidate_id", "entry_date", "ticker", "right",
                "model_id", "p_model", "p_cal", "ev_base", "ev_adverse",
            },
            "shadow row schema",
        )
        for field in ("entry_date", "ticker", "right", "model_id"):
            require(saved[field] == rebuilt[field], f"shadow {field}")
        for field in ("p_model", "p_cal", "ev_base", "ev_adverse"):
            assert_close(saved[field], rebuilt[field], f"shadow {field}")
    timeline_result = validate_policy_timeline(
        sessions, plans, proposals, timeline, gate_results
    )
    summary = read_json(PRODUCER_ROOT / "summary.json")
    eval_rows = [rows_by_id[value] for value in sorted(eval_ids)]
    validate_summary(
        helper, summary, eval_rows, books, sessions, proposals, timeline,
        len(bridge_candidates),
    )
    return {
        "states_reconstructed": len(states), "scores_reconstructed": len(rebuilt_scores),
        "books_reconstructed": 10, "timeline": timeline_result,
        "fit_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent context adaptation walk-forward auditor")
    parser.add_argument("--execute-reviewed-audit", action="store_true")
    parser.add_argument("--producer-manifest-sha256", required=True)
    parser.add_argument("--producer-sha256", required=True)
    parser.add_argument("--producer-tests-sha256", required=True)
    parser.add_argument("--bridge-manifest-sha256", required=True)
    parser.add_argument("--bridge-audit-sha256", required=True)
    parser.add_argument("--auditor-sha256", required=True)
    args = parser.parse_args()
    if not args.execute_reviewed_audit:
        parser.error("execution requires --execute-reviewed-audit")
    for name in (
        "producer_manifest_sha256", "producer_sha256", "producer_tests_sha256",
        "bridge_manifest_sha256",
        "bridge_audit_sha256", "auditor_sha256",
    ):
        require(len(getattr(args, name)) == 64, f"SHA argument {name}")
    output = plain(OUTPUT, "audit output", exists=False)
    require(not output.exists(), "immutable audit output exists")
    manifest, snapshots, payloads = admit_producer_bundle(
        args.producer_manifest_sha256.lower(), args.producer_sha256.lower(),
        args.producer_tests_sha256.lower(), args.bridge_manifest_sha256.lower(),
        args.bridge_audit_sha256.lower(), args.auditor_sha256.lower(),
    )
    helper = import_helper()
    numeric = numeric_audit_from_sealed_payloads(helper, snapshots, payloads)
    revalidate(snapshots, payloads)
    audit = {
        "schema": AUDIT_SCHEMA, "status": AUDIT_STATUS,
        "inputs": {
            name: {"path": value["path"], "bytes": value["bytes"], "sha256": value["sha256"]}
            for name, value in snapshots.items()
        },
        "producer": {
            "schema": manifest["schema"], "status": manifest["status"],
            "outputs": manifest["outputs"],
        },
        "numeric": numeric,
        "limitations": [
            "saved coefficients are inferred but never refit",
            "operational producer exit and retained-handle closure are launcher prerequisites outside this audit artifact",
            "all periods are seen development and no promotion is approved",
        ],
        "flags": {
            "producer_imported": False, "fit_performed": False,
            "saved_weights_used": True, "raw_read": False, "api_read": False,
            "broker_read": False, "production_changed": False,
            "seen_development": True, "promotion_approved": False,
        },
    }
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "audit.json", audit)
    revalidate(snapshots, payloads)
    write_json(
        output / "manifest.json",
        {
            "schema": "weekly_context_adaptation_audit_manifest_v1",
            "status": AUDIT_STATUS,
            "audit.json": pin(output / "audit.json"),
        },
    )
    revalidate(snapshots, payloads)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
