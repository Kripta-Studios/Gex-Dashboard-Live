"""Daily CONTEXT182 adaptation against frozen monthly/weekly controls.

This producer imports the reviewed adaptation implementation only as a pinned
library of explicitly allowlisted pure functions.  It never calls that
module's execution entry points and never refits the 42 sealed states.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import numpy as np


WEEK = Path(__file__).resolve().parent
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
OUTPUT = BASE / "h2_daily_adaptation_01"
TESTS = WEEK / "test_evaluate_weekly_daily_adaptation.py"
REVIEW = WEEK / "DAILY_ADAPTATION_CONTRACT_REVIEW_20261101.md"
CONTRACT = WEEK / "DAILY_ADAPTATION_CONTRACT_20261101.md"
CONTRACT_SHA256 = "5d388e484435c8fe23d40476c02928887c6ab5487af62197e5e74f08c1fe0047"
ORIGINAL = WEEK / "evaluate_weekly_context_adaptation.py"
ORIGINAL_SHA256 = "d03494bf68e281bc7c9e68f385aa111567eac4206cf5b44133e17bb480ed5df8"
CONTEXT_HELPER = WEEK / "evaluate_weekly_context_models.py"
CONTEXT_HELPER_SHA256 = "bdc6534f059ade7acc58f23952a88ed2068c7a712518b04f438945a583a07a2f"
EVALUATOR_HELPER = WEEK / "evaluate_weekly_h2_ev_v2.py"
EVALUATOR_HELPER_SHA256 = "8a9e75855d542a12662e5c812583f2ef86042f5c3ae1bbbad73c16042e063476"
REPLAY_HELPER = WEEK / "replay_equal_risk_frozen.py"
REPLAY_HELPER_SHA256 = "e4f42a9fa65120939cf5e131911c8f2990a9cd33d21ae036fa98d9eb816d5b9d"
GATE_HELPER = WEEK.parent / "level_oracle_20261018" / "launch_monthly_test_index_v2_audit_20261024.py"
GATE_HELPER_SHA256 = "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"

ADAPTATION = BASE / "h2_context_adaptation_01"
ADAPTATION_MANIFEST = ADAPTATION / "manifest.json"
ADAPTATION_MANIFEST_SHA256 = "e8cf5cd4a001cd98cdf29e54cf47bbdf3c34d6652abf34ef7c71fffa0bd97f23"
ADAPTATION_AUDIT = BASE / "h2_context_adaptation_audit_04" / "audit.json"
ADAPTATION_AUDIT_SHA256 = "9a487fba18504ae4faff2c1dba17d1c000eb237436a09a7fe22747e328cb307a"
ADAPTATION_EXIT = BASE / "h2_context_adaptation_audit_observer_04" / "exit.json"
ADAPTATION_EXIT_SHA256 = "5d59d1a3978d8d9aa31c7c3fab567d1ae7e901494aa8efb12377ca65f91de420"
BRIDGE_MANIFEST = BASE / "h2_boundary_bridge_01" / "manifest.json"
BRIDGE_MANIFEST_SHA256 = "9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86"
BRIDGE_AUDIT = BASE / "h2_boundary_bridge_audit_01" / "audit.json"
BRIDGE_AUDIT_SHA256 = "83c9ade0b6b7205484dd275df8593107238f94468d8564f7351e9481a475033c"
ACCEPTANCE = WEEK / "USER_MONTHLY_PROFITABILITY_ACCEPTANCE_20261101.md"
ACCEPTANCE_SHA256 = "806f7728a2ad434bc08929d3715f307455bd37862ae4c19a2cd2cc1d64a5ee5b"

UPSTREAM_OUTPUT_SHA256 = {
    "states.jsonl": "d9313b329b4543aecd1aaad39116aa13eff3efad271e9931916caa91feeac475",
    "fit_plans.json": "c120c8de05dfb98b85e6ad942a2f7400baac0297e0bd80d0d2c2f05194a0e6fb",
    "candidate_scores.jsonl": "9acae826edba3b712fb67b448d5711778c0af99bb027800d3a6626ddc4b02a4f",
    "summary.json": "1ad1dbca873d255b431a2e097be169b0ad91913b728fbe2a2478f2d30212049f",
}

PARENTS = ("FROZEN_CONTEXT182", "MONTHLY_RAW", "WEEKLY_RAW", "DAILY_RAW")
CONTROLS = PARENTS[:3]
COSTS = ("base", "adverse")
TICKERS = ("SPY", "QQQ", "SPXW")
FIRST_EVAL, LAST_ENTRY, LAST_EVAL = "20260102", "20260915", "20260917"
MONTHS = tuple(f"2026{month:02d}" for month in range(1, 10))
COMPLETE_MONTHS = MONTHS[:8]
NY = ZoneInfo("America/New_York")
EXPECTED_SESSIONS = 178
EXPECTED_REUSED = 42
EXPECTED_NEW = 136
EXPECTED_CANDIDATES = 612
SCORE_KEYS = {
    "candidate_id", "entry_date", "ev_adverse", "ev_base", "is_bridge", "model_id",
    "p_cal", "p_model", "payoff_is_lower_bound", "policy", "right", "scenario", "ticker",
}
PLAN_KEYS = {
    "asof", "cal_end", "cal_ids", "cal_label_available_max", "cal_sessions", "cal_start",
    "creation_date", "frequencies", "purged_train_ids", "state_id", "train_ids",
    "train_label_available_max",
}
ORIGINAL_ALLOWLIST = {
    "admit_sources", "calendar_dates", "load_context_union", "fit_state", "score_state",
    "strip_runtime", "attach_scores", "enrich_ledger", "generic_metrics", "economic_details",
}
FLAGS = {
    "models_fit": True, "reused_states_fit": False, "seen_development": True,
    "raw_read": False, "api_read": False, "broker_read": False,
    "future_labels_used": False, "guarded_used": False, "ev_filter_used": False,
    "selection_made": False, "technical_ready": False, "promotion_approved": False,
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


class DailyAdaptationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DailyAdaptationError(message)


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
    values = []
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


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def import_pinned(path: Path, expected_sha256: str, name: str, allowed: set[str] | None = None) -> Any:
    path = plain(path, name, regular=True)
    require(sha256_file(path) == expected_sha256, f"{name} authority")
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"{name} import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(sha256_file(path) == expected_sha256, f"{name} changed during import")
    if allowed is not None:
        require(all(callable(getattr(module, item, None)) for item in allowed), f"{name} allowlist")
    return module


def midnight(day: str) -> datetime:
    return datetime.strptime(day, "%Y%m%d").replace(tzinfo=NY)


def available(row: dict[str, Any]) -> datetime:
    value = row.get("_available")
    if isinstance(value, datetime):
        return value
    parsed = datetime.fromisoformat(row["label_available_at"])
    require(parsed.tzinfo is not None, "aware label availability")
    return parsed


def build_daily_plans(rows: list[dict[str, Any]], sessions: list[str]) -> list[dict[str, Any]]:
    eval_sessions = [day for day in sessions if FIRST_EVAL <= day <= LAST_EVAL]
    require(len(eval_sessions) == EXPECTED_SESSIONS, "178 evaluation sessions")
    index = {day: offset for offset, day in enumerate(sessions)}
    plans = []
    for day in eval_sessions:
        offset = index[day]
        require(offset >= 65, f"63-session CAL unavailable {day}")
        cal_sessions = sessions[offset - 65:offset - 2]
        require(len(cal_sessions) == 63, "CAL width")
        cal_start, cutoff = cal_sessions[0], midnight(day)
        train_cutoff, cal_set = midnight(cal_start), set(cal_sessions)
        train = [row for row in rows if row["entry_date"] < cal_start and available(row) < train_cutoff]
        purged = [row for row in rows if row["entry_date"] < cal_start and available(row) >= train_cutoff]
        cal = [row for row in rows if row["entry_date"] in cal_set and available(row) < cutoff]
        require(train and len({int(row["scenario"]) for row in train}) >= 2, f"TRAIN classes {day}")
        require(cal, f"CAL empty {day}")
        plan = {
            "state_id": f"CONTEXT182_{day}", "creation_date": day,
            "asof": cutoff.isoformat(), "frequencies": ["DAILY"],
            "cal_sessions": cal_sessions, "cal_start": cal_start, "cal_end": cal_sessions[-1],
            "train_ids": sorted(row["candidate_id"] for row in train),
            "cal_ids": sorted(row["candidate_id"] for row in cal),
            "purged_train_ids": sorted(row["candidate_id"] for row in purged),
            "train_label_available_max": max(available(row) for row in train).isoformat(),
            "cal_label_available_max": max(available(row) for row in cal).isoformat(),
        }
        require(set(plan) == PLAN_KEYS, "daily plan keys")
        plans.append(plan)
    return plans


def bind_reused(
    plans: list[dict[str, Any]], upstream_plans: list[dict[str, Any]], upstream_states: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    plan_index = {row["state_id"]: row for row in upstream_plans}
    state_rows = {row["state_id"]: (number, row) for number, row in enumerate(upstream_states)}
    require(len(plan_index) == len(state_rows) == EXPECTED_REUSED, "42 upstream states")
    schedule, new_plans, reused, published_plans = [], [], {}, []
    scientific = PLAN_KEYS - {"frequencies"}
    for plan in plans:
        state_id, day = plan["state_id"], plan["creation_date"]
        source = "REUSED" if state_id in plan_index else "NEW"
        if source == "REUSED":
            sealed = plan_index[state_id]
            require(set(sealed) == PLAN_KEYS, "sealed plan keys")
            require(all(plan[key] == sealed[key] for key in scientific), f"reused plan mismatch {state_id}")
            source_row, state = state_rows[state_id]
            require(state["state_id"] == state_id and state["creation_date"] == day, "reused state identity")
            require(all(state[key] == sealed[key] for key in PLAN_KEYS), f"reused state/plan mismatch {state_id}")
            reused[state_id] = state
            published_plans.append(sealed)
        else:
            source_row = None
            new_plans.append(plan)
            published_plans.append(plan)
        terminal = day in {"20260916", "20260917"}
        schedule.append({
            "date": day, "state_id": state_id, "source": source, "source_row": source_row,
            "used_for_scoring": not terminal, "terminal_unused_for_scoring": terminal,
        })
    require(len(schedule) == EXPECTED_SESSIONS and len(reused) == EXPECTED_REUSED and len(new_plans) == EXPECTED_NEW, "178/42/136 schedule")
    return schedule, new_plans, reused, published_plans


def validate_reused_states(states: list[dict[str, Any]]) -> None:
    require(len(states) == EXPECTED_REUSED, "42 reused states")
    versions = {state.get("model", {}).get("sklearn_version") for state in states}
    require(versions == {importlib.metadata.version("scikit-learn")}, "sklearn version parity")
    composition = Counter(tuple(state.get("frequencies", [])) for state in states)
    require(
        composition == Counter({("MONTHLY",): 4, ("WEEKLY",): 33, ("MONTHLY", "WEEKLY"): 5}),
        "reused frequency composition",
    )


def compare_score_payload(left: dict[str, Any], right: dict[str, Any]) -> None:
    for key in SCORE_KEYS - {"policy"}:
        if key in {"p_model", "p_cal"}:
            require(np.array_equal(np.asarray(left[key]), np.asarray(right[key])), f"reused score {key}")
        else:
            require(left[key] == right[key], f"reused score {key}")


def validate_score_universe(
    scores: list[dict[str, Any]], rows: list[dict[str, Any]], policies: tuple[str, ...],
) -> None:
    candidate_index = {row["candidate_id"]: row for row in rows}
    require(len(candidate_index) == len(rows) == EXPECTED_CANDIDATES, "score candidate universe")
    common = set(candidate_index)
    require(len(scores) == len(policies) * EXPECTED_CANDIDATES, "score total")
    require(len({(row.get("policy"), row.get("candidate_id")) for row in scores}) == len(scores), "score uniqueness")
    for policy in policies:
        values = [row for row in scores if row.get("policy") == policy]
        require(len(values) == EXPECTED_CANDIDATES and {row["candidate_id"] for row in values} == common, f"score set {policy}")
        for value in values:
            require(set(value) == SCORE_KEYS, f"score schema {policy}")
            source = candidate_index[value["candidate_id"]]
            require(
                value["entry_date"] == source["entry_date"]
                and value["ticker"] == source["ticker"]
                and value["right"] == source["right"]
                and value["scenario"] == source["scenario"]
                and value["payoff_is_lower_bound"] == source["payoff_is_lower_bound"],
                f"score identity {policy}",
            )
            require(isinstance(value["model_id"], str) and bool(value["model_id"]), f"score model {policy}")


def reused_daily_scores(
    rows: list[dict[str, Any]], schedule: list[dict[str, Any]], upstream_scores: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    row_ids = {row["candidate_id"] for row in rows}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for score in upstream_scores:
        if score["policy"] in {"MONTHLY_RAW", "WEEKLY_RAW"}:
            grouped[(score["model_id"], score["candidate_id"])].append(score)
    output = []
    for item in schedule:
        if item["source"] != "REUSED" or not item["used_for_scoring"]:
            continue
        ids = sorted(row["candidate_id"] for row in rows if row["entry_date"] == item["date"])
        for candidate_id in ids:
            require(candidate_id in row_ids, "reused candidate")
            matches = grouped.get((item["state_id"], candidate_id), [])
            require(matches, f"missing reused score {candidate_id}")
            for other in matches[1:]:
                compare_score_payload(matches[0], other)
            value = dict(matches[0])
            value["policy"] = "DAILY_RAW"
            require(set(value) == SCORE_KEYS, "daily score schema")
            output.append(value)
    return output


def extended_metrics(ledger: list[dict[str, Any]], replay: Any, original: Any) -> dict[str, Any]:
    return {**replay.book_metrics(ledger), "details": original.economic_details(ledger)}


def fit_new_states(
    new_plans: list[dict[str, Any]], by_id: dict[str, Any], context: Any,
    evaluator: Any, original: Any, gate: Any, output: Path,
) -> dict[str, dict[str, Any]]:
    journal_path, states_jsonl = output / "fit_journal.jsonl", output / "daily_states_new.jsonl"
    journal_path.touch(exist_ok=False)
    states_jsonl.touch(exist_ok=False)
    new_states: dict[str, dict[str, Any]] = {}
    for plan in new_plans:
        observation = gate.observation()
        require(
            isinstance(observation, dict)
            and set(observation) == {"available_ram_bytes", "free_commit_bytes"}
            and all(type(observation[key]) is int for key in observation),
            "gate observation schema",
        )
        append_jsonl(journal_path, {
            "event": "FIT_START", "state_id": plan["state_id"], "creation_date": plan["creation_date"],
            "asof": plan["asof"], "utc": datetime.now(timezone.utc).isoformat(), "gate": observation,
            "state_sha256": None,
        })
        gate.gate(observation)
        fitted = original.fit_state(plan, by_id, context, evaluator)
        probe = [by_id[candidate_id] for candidate_id in fitted["cal_ids"][:7]]
        runtime_scores = original.score_state(fitted, probe)
        saved = original.strip_runtime(fitted)
        saved_scores = original.score_state(saved, probe)
        for left, right in zip(runtime_scores, saved_scores, strict=True):
            require(left["candidate_id"] == right["candidate_id"], "runtime/saved candidate order")
            require(np.allclose(left["p_model"], right["p_model"], atol=1e-12, rtol=0), "runtime/saved probability parity")
            require(np.allclose(left["p_cal"], right["p_cal"], atol=1e-12, rtol=0), "runtime/saved calibrated parity")
            for cost in COSTS:
                require(math.isclose(left[f"ev_{cost}"], right[f"ev_{cost}"], abs_tol=1e-10, rel_tol=0), f"runtime/saved EV parity {cost}")
        state_path = output / f"fit_state_{plan['state_id']}.json"
        write_json(state_path, saved)
        state_sha = sha256_file(state_path)
        append_jsonl(states_jsonl, saved)
        append_jsonl(journal_path, {
            "event": "FIT_COMPLETE", "state_id": plan["state_id"], "creation_date": plan["creation_date"],
            "asof": plan["asof"], "utc": datetime.now(timezone.utc).isoformat(), "gate": observation,
            "state_sha256": state_sha,
        })
        new_states[plan["state_id"]] = saved
    require(len(new_states) == EXPECTED_NEW and len(read_jsonl(journal_path)) == 2 * EXPECTED_NEW, "completed fit count")
    return new_states


def selected_ids(ledger: list[dict[str, Any]]) -> set[str]:
    return {
        row["candidate_id"] for row in ledger
        if row["event"] in {"ENTRY", "NO_FILL", "CAPITAL_BLOCKED"} and "candidate_id" in row
    }


def monthly_exit(ledger: list[dict[str, Any]]) -> dict[str, float]:
    return {
        month: math.fsum(float(row["net_usd"]) for row in ledger if row["event"] == "EXIT" and row["date"][:6] == month)
        for month in MONTHS
    }


def passes_complete_months(monthly: dict[str, float]) -> bool:
    require(set(monthly) == set(MONTHS), "nine month keys")
    return all(float(monthly[month]) > 0 for month in COMPLETE_MONTHS)


def copy_control_ledger(source: Path, target: Path, expected: dict[str, Any]) -> None:
    verify(source, expected, f"control ledger source {source.name}")
    shutil.copyfile(source, target)
    require(target.read_bytes() == source.read_bytes(), f"byte exact control ledger {source.name}")


def compare_nested(actual: Any, expected: Any, label: str, tolerance: float = 1e-6) -> None:
    if isinstance(actual, dict) and isinstance(expected, dict):
        require(set(actual) == set(expected), f"{label} keys")
        for key in actual:
            compare_nested(actual[key], expected[key], f"{label}/{key}", tolerance)
        return
    if isinstance(actual, list) and isinstance(expected, list):
        require(len(actual) == len(expected), f"{label} length")
        for number, (left, right) in enumerate(zip(actual, expected, strict=True)):
            compare_nested(left, right, f"{label}/{number}", tolerance)
        return
    if isinstance(actual, float) and isinstance(expected, float):
        require(math.isclose(actual, expected, abs_tol=tolerance, rel_tol=0), f"{label} numeric")
        return
    require(type(actual) is type(expected) and actual == expected, f"{label} value")


def candidate_diagnostics(scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    daily = {row["candidate_id"]: row for row in scores if row["policy"] == "DAILY_RAW"}
    weekly = {row["candidate_id"]: row for row in scores if row["policy"] == "WEEKLY_RAW"}
    require(set(daily) == set(weekly) and len(daily) == EXPECTED_CANDIDATES, "daily/weekly score universe")
    top: dict[tuple[str, str, str], set[str]] = {}
    for policy, index in (("DAILY_RAW", daily), ("WEEKLY_RAW", weekly)):
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in index.values():
            groups[(row["entry_date"], row["ticker"])].append(row)
        for identity, values in groups.items():
            best = max(float(row["ev_adverse"]) for row in values)
            winners = {row["candidate_id"] for row in values if float(row["ev_adverse"]) == best and best > 0}
            top[(policy, *identity)] = winners if len(winners) == 1 else set()
    output = []
    for candidate_id in sorted(daily):
        left, right = daily[candidate_id], weekly[candidate_id]
        identity = (left["entry_date"], left["ticker"])
        daily_top = candidate_id in top[("DAILY_RAW", *identity)]
        weekly_top = candidate_id in top[("WEEKLY_RAW", *identity)]
        output.append({
            "candidate_id": candidate_id, "entry_date": left["entry_date"], "ticker": left["ticker"], "right": left["right"],
            "daily_model_id": left["model_id"], "weekly_model_id": right["model_id"],
            "p_model_diff": (np.asarray(left["p_model"]) - np.asarray(right["p_model"])).tolist(),
            "p_cal_diff": (np.asarray(left["p_cal"]) - np.asarray(right["p_cal"])).tolist(),
            "ev_base_diff": float(left["ev_base"]) - float(right["ev_base"]),
            "ev_adverse_diff": float(left["ev_adverse"]) - float(right["ev_adverse"]),
            "daily_top1": daily_top, "weekly_top1": weekly_top, "top1_changed": daily_top != weekly_top,
        })
    return output


def admit_fixed() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    require(sha256_file(CONTRACT) == CONTRACT_SHA256, "contract authority")
    fixed = {
        ORIGINAL: ORIGINAL_SHA256, CONTEXT_HELPER: CONTEXT_HELPER_SHA256,
        EVALUATOR_HELPER: EVALUATOR_HELPER_SHA256, REPLAY_HELPER: REPLAY_HELPER_SHA256,
        GATE_HELPER: GATE_HELPER_SHA256, ADAPTATION_MANIFEST: ADAPTATION_MANIFEST_SHA256,
        ADAPTATION_AUDIT: ADAPTATION_AUDIT_SHA256, ADAPTATION_EXIT: ADAPTATION_EXIT_SHA256,
        BRIDGE_MANIFEST: BRIDGE_MANIFEST_SHA256, BRIDGE_AUDIT: BRIDGE_AUDIT_SHA256,
        ACCEPTANCE: ACCEPTANCE_SHA256, CONTRACT: CONTRACT_SHA256,
    }
    snapshots = {}
    for path, expected in fixed.items():
        require(sha256_file(plain(path, str(path), regular=True)) == expected, f"authority {path.name}")
        snapshots[str(path)] = pin(path)
    manifest, audit, exit_value = read_json(ADAPTATION_MANIFEST), read_json(ADAPTATION_AUDIT), read_json(ADAPTATION_EXIT)
    require(manifest.get("schema") == "weekly_context_adaptation_walkforward_v1" and manifest.get("status") == "PASS_SEEN_DEVELOPMENT_GIVEN_BRIDGE_AND_FROZEN_AUTHORITIES", "adaptation manifest status")
    require(manifest.get("flags") == ADAPTATION_FLAGS, "adaptation manifest flags")
    require(audit.get("schema") == "weekly_context_adaptation_audit_v1" and audit.get("status") == "PASS_INDEPENDENT_NUMERIC_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT", "adaptation audit status")
    require(audit.get("flags") == ADAPTATION_AUDIT_FLAGS, "adaptation audit flags")
    require(audit.get("inputs", {}).get("producer_manifest") == {"path": str(ADAPTATION_MANIFEST), "bytes": 17599, "sha256": ADAPTATION_MANIFEST_SHA256}, "adaptation audit binding")
    require(exit_value.get("exit_code") == 0, "adaptation exit0")
    bridge_manifest, bridge_audit = read_json(BRIDGE_MANIFEST), read_json(BRIDGE_AUDIT)
    require(bridge_manifest.get("schema") == "weekly_h2_boundary_bridge_manifest_v1" and bridge_manifest.get("status") == "COMPLETE_WEEKLY_H2_BOUNDARY_BRIDGE_NOT_EVALUATED", "bridge manifest status")
    require(bridge_manifest.get("new_candidate_id_count") == 6, "bridge six candidates")
    require(bridge_audit.get("schema") == "weekly_h2_boundary_bridge_audit_v1" and bridge_audit.get("status") == "PASS_INDEPENDENT_BOUNDARY_BRIDGE_GIVEN_FROZEN_BUILDERS", "bridge audit status")
    require(bridge_audit.get("inputs", {}).get("producer_manifest") == {"path": str(BRIDGE_MANIFEST), "bytes": 4748, "sha256": BRIDGE_MANIFEST_SHA256}, "bridge audit binding")
    for name, expected_sha in UPSTREAM_OUTPUT_SHA256.items():
        path = ADAPTATION / name
        expected = manifest.get("outputs", {}).get(name)
        require(isinstance(expected, dict) and expected.get("sha256") == expected_sha, f"upstream output manifest {name}")
        verify(path, expected, name)
        snapshots[str(path)] = pin(path)
    for parent in CONTROLS:
        for cost in COSTS:
            name = f"ledger_{parent.lower()}_{cost}.jsonl"
            expected = manifest.get("outputs", {}).get(name)
            require(isinstance(expected, dict), f"upstream ledger manifest {name}")
            verify(ADAPTATION / name, expected, name)
            snapshots[str(ADAPTATION / name)] = pin(ADAPTATION / name)
    return manifest, audit, exit_value, snapshots


def guard_output(output: Path) -> Path:
    value = plain(output, "daily output", exists=False)
    require(not value.exists() and value.parent == BASE, "exclusive contracted output")
    return value


def run(output: Path = OUTPUT) -> dict[str, Any]:
    output = guard_output(output)
    snapshots = {str(path): pin(path) for path in (Path(__file__), TESTS, REVIEW)}
    adaptation_manifest, _audit, _exit, fixed_snapshots = admit_fixed()
    snapshots.update(fixed_snapshots)
    original = import_pinned(ORIGINAL, ORIGINAL_SHA256, "daily_original_pure", ORIGINAL_ALLOWLIST)
    context = import_pinned(CONTEXT_HELPER, CONTEXT_HELPER_SHA256, "daily_context")
    evaluator = import_pinned(EVALUATOR_HELPER, EVALUATOR_HELPER_SHA256, "daily_evaluator")
    replay = import_pinned(REPLAY_HELPER, REPLAY_HELPER_SHA256, "daily_replay")
    gate = import_pinned(GATE_HELPER, GATE_HELPER_SHA256, "daily_gate")
    bridge_manifest, bridge_audit = read_json(BRIDGE_MANIFEST), read_json(BRIDGE_AUDIT)
    admitted = original.admit_sources(bridge_manifest, bridge_audit, evaluator)
    rows, bridge_rows, coverage = admitted["rows"], admitted["bridge_rows"], admitted["coverage"]
    consumed, external = admitted["consumed"], admitted["external"]
    sessions = original.calendar_dates(coverage)
    feature_names = original.load_context_union(context, rows, admitted["manifests"], consumed)
    for path, expected in consumed.items():
        verify(path, expected, f"consumed initial {path}")
        snapshots[str(path)] = pin(path)
    for expected in external.values():
        path = Path(expected["path"])
        verify(path, expected, f"external initial {path}")
        snapshots[str(path)] = pin(path)
    by_id = {row["candidate_id"]: row for row in rows}
    by_id["__feature_names__"] = feature_names
    plans = build_daily_plans(rows, sessions)
    upstream_plan_file = read_json(ADAPTATION / "fit_plans.json")
    upstream_states = read_jsonl(ADAPTATION / "states.jsonl")
    validate_reused_states(upstream_states)
    schedule, new_plans, reused, published_plans = bind_reused(plans, upstream_plan_file["plans"], upstream_states)
    output.mkdir(parents=False, exist_ok=False)
    write_json(output / "daily_fit_plans.json", {"schema": "weekly_daily_adaptation_fit_plans_v1", "count": len(published_plans), "plans": published_plans})
    write_json(output / "daily_schedule.json", {
        "schema": "weekly_daily_adaptation_schedule_v1", "count": len(schedule),
        "reused_source": pin(ADAPTATION / "states.jsonl"), "rows": schedule,
    })
    new_states = fit_new_states(new_plans, by_id, context, evaluator, original, gate, output)
    state_index = {**reused, **new_states}
    eval_rows = [row for row in rows if FIRST_EVAL <= row["entry_date"] <= LAST_EVAL]
    require(len(eval_rows) == EXPECTED_CANDIDATES, "612 evaluation candidates")
    upstream_scores = read_jsonl(ADAPTATION / "candidate_scores.jsonl")
    controls = [row for row in upstream_scores if row["policy"] in CONTROLS]
    validate_score_universe(controls, eval_rows, CONTROLS)
    daily_scores = reused_daily_scores(eval_rows, schedule, controls)
    rows_by_date = {day: [row for row in eval_rows if row["entry_date"] == day] for day in (item["date"] for item in schedule)}
    bridge_ids = {row["candidate_id"] for row in bridge_rows}
    for item in schedule:
        if item["source"] != "NEW" or not item["used_for_scoring"]:
            continue
        for score in original.score_state(state_index[item["state_id"]], rows_by_date[item["date"]]):
            source = by_id[score["candidate_id"]]
            daily_scores.append({
                "policy": "DAILY_RAW", **score, "scenario": source["scenario"],
                "payoff_is_lower_bound": source["payoff_is_lower_bound"],
                "is_bridge": score["candidate_id"] in bridge_ids,
            })
    require(len(daily_scores) == EXPECTED_CANDIDATES and {row["candidate_id"] for row in daily_scores} == {row["candidate_id"] for row in eval_rows}, "612 daily scores")
    validate_score_universe(daily_scores, eval_rows, ("DAILY_RAW",))
    all_scores = [*controls, *sorted(daily_scores, key=lambda row: (row["entry_date"], row["ticker"], row["right"]))]
    validate_score_universe(all_scores, eval_rows, PARENTS)
    write_jsonl(output / "candidate_scores.jsonl", all_scores)
    books: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for parent in CONTROLS:
        for cost in COSTS:
            source = ADAPTATION / f"ledger_{parent.lower()}_{cost}.jsonl"
            target = output / source.name
            copy_control_ledger(source, target, adaptation_manifest["outputs"][source.name])
            books[(parent, cost)] = read_jsonl(target)
    daily_input = original.attach_scores(eval_rows, daily_scores)
    raw_daily = replay.replay_pair(daily_input, coverage, [day for day in sessions if FIRST_EVAL <= day <= LAST_EVAL], LAST_ENTRY, "EV_TOP1_H2")
    model_map = {row["candidate_id"]: row["model_id"] for row in daily_scores}
    for cost in COSTS:
        ledger = original.enrich_ledger(raw_daily[cost], "DAILY_RAW", model_map)
        books[("DAILY_RAW", cost)] = ledger
        write_jsonl(output / f"ledger_daily_raw_{cost}.jsonl", ledger)
    diagnostics = candidate_diagnostics(all_scores)
    write_jsonl(output / "daily_vs_weekly.jsonl", diagnostics)
    state_diagnostics = []
    score_count = Counter(row["entry_date"] for row in daily_scores)
    for item in schedule:
        state = state_index[item["state_id"]]
        state_diagnostics.append({
            "date": item["date"], "state_id": item["state_id"], "source": item["source"],
            "train_n": len(state["train_ids"]), "cal_n": len(state["cal_ids"]),
            "purged_n": len(state["purged_train_ids"]), "class_support": state["prior_support"],
            "prior": state["prior"], "alpha": state["calibration"]["selected_alpha"],
            "score_count": score_count[item["date"]],
            "terminal_unused_for_scoring": item["terminal_unused_for_scoring"],
        })
    write_jsonl(output / "state_diagnostics.jsonl", state_diagnostics)
    upstream_summary = read_json(ADAPTATION / "summary.json")
    for parent in CONTROLS:
        upstream_policy = upstream_summary["policies"][parent]
        for cost in COSTS:
            recomputed = extended_metrics(books[(parent, cost)], replay, original)
            compare_nested(recomputed, upstream_policy["economics"][cost], f"control economics {parent}/{cost}")
        control_selected = selected_ids(books[(parent, "adverse")])
        require(control_selected == selected_ids(books[(parent, "base")]) == set(upstream_policy["selected_ids"]), f"control selected {parent}")
        control_scores = [row for row in controls if row["policy"] == parent]
        recomputed_probability = original.generic_metrics(eval_rows, control_scores, control_selected)
        compare_nested(recomputed_probability, upstream_policy["probability_ev"], f"control probability {parent}", 1e-12)
    policy_summary = {parent: upstream_summary["policies"][parent] for parent in CONTROLS}
    daily_selected = selected_ids(books[("DAILY_RAW", "adverse")])
    require(daily_selected == selected_ids(books[("DAILY_RAW", "base")]), "paired daily decisions")
    daily_filled = {row["candidate_id"] for row in books[("DAILY_RAW", "adverse")] if row["event"] == "ENTRY"}
    policy_summary["DAILY_RAW"] = {
        "economics": {cost: extended_metrics(books[("DAILY_RAW", cost)], replay, original) for cost in COSTS},
        "probability_ev": original.generic_metrics(eval_rows, daily_scores, daily_selected),
        "selected_ids": sorted(daily_selected), "filled_ids": sorted(daily_filled),
    }
    policy_summary["DAILY_RAW"]["adverse_net_minus_frozen"] = (
        policy_summary["DAILY_RAW"]["economics"]["adverse"]["net_usd"]
        - policy_summary["FROZEN_CONTEXT182"]["economics"]["adverse"]["net_usd"]
    )
    monthly = {parent: monthly_exit(books[(parent, "adverse")]) for parent in PARENTS}
    monthly_by_cost = {
        (parent, cost): monthly_exit(books[(parent, cost)]) for parent in PARENTS for cost in COSTS
    }
    comparisons = {
        baseline: {
            cost: {
                "total_net_usd": policy_summary["DAILY_RAW"]["economics"][cost]["net_usd"] - policy_summary[baseline]["economics"][cost]["net_usd"],
                "monthly_net_usd": {month: monthly_by_cost[("DAILY_RAW", cost)][month] - monthly_by_cost[(baseline, cost)][month] for month in MONTHS},
            }
            for cost in COSTS
        }
        for baseline in ("WEEKLY_RAW", "MONTHLY_RAW")
    }
    summary = {
        "schema": "weekly_daily_adaptation_summary_v1", "status": "COMPLETE_SEEN_DEVELOPMENT_NOT_PROMOTED",
        "scope": {"sessions": EXPECTED_SESSIONS, "candidate_universe": EXPECTED_CANDIDATES, "policies": list(PARENTS), "scores": len(all_scores), "books": len(books)},
        "states": {"daily": EXPECTED_SESSIONS, "reused": EXPECTED_REUSED, "new": EXPECTED_NEW, "terminal_unused": 2},
        "policies": policy_summary, "comparisons": comparisons,
        "criterion": {"months": list(COMPLETE_MONTHS), "necessary": "DAILY_RAW adverse exit-date net strictly positive in every complete month", "daily_passes_8_of_8": passes_complete_months(monthly["DAILY_RAW"]), "selected_policy": None, "promotion_approved": False},
        "diagnostics": {"state_rows": len(state_diagnostics), "candidate_rows": len(diagnostics), "top1_changed": sum(row["top1_changed"] for row in diagnostics)},
        "flags": FLAGS,
    }
    write_json(output / "summary.json", summary)
    for path, expected in consumed.items():
        verify(path, expected, f"consumed close {path}")
        snapshots.setdefault(str(path), pin(path))
    for name, before in list(snapshots.items()):
        require(pin(Path(name)) == before, f"input closure {name}")
    core_paths = [path for path in output.rglob("*") if path.is_file()]
    outputs = {str(path.relative_to(output)).replace("\\", "/"): {"bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in sorted(core_paths)}
    manifest = {
        "schema": "weekly_daily_adaptation_manifest_v1", "status": summary["status"],
        "inputs": {name: {"before": {"bytes": value["bytes"], "sha256": value["sha256"]}, "after": {"bytes": value["bytes"], "sha256": value["sha256"]}} for name, value in sorted(snapshots.items())},
        "outputs": outputs, "flags": FLAGS,
    }
    write_json(output / "manifest.json", manifest)
    for name, before in snapshots.items():
        require(pin(Path(name)) == before, f"post-manifest input closure {name}")
    for name, expected in outputs.items():
        verify(output / name, expected, f"post-manifest output closure {name}")
    require(sha256_file(ORIGINAL) == ORIGINAL_SHA256 and sha256_file(CONTEXT_HELPER) == CONTEXT_HELPER_SHA256 and sha256_file(EVALUATOR_HELPER) == EVALUATOR_HELPER_SHA256 and sha256_file(REPLAY_HELPER) == REPLAY_HELPER_SHA256, "final helper closure")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-reviewed-daily-adaptation", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--implementation-sha256", required=True)
    parser.add_argument("--tests-sha256", required=True)
    parser.add_argument("--review-sha256", required=True)
    args = parser.parse_args()
    require(args.execute_reviewed_daily_adaptation, "execution flag required")
    require(args.contract_sha256 == CONTRACT_SHA256, "contract CLI pin")
    require(sha256_file(Path(__file__)) == args.implementation_sha256, "implementation CLI pin")
    require(sha256_file(TESTS) == args.tests_sha256 and sha256_file(REVIEW) == args.review_sha256, "reviewed code binding")
    result = run(args.output)
    print(json.dumps({"status": result["status"], "manifest": str(args.output / "manifest.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
