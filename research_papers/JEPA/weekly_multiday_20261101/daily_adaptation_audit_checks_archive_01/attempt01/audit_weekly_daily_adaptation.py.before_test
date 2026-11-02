"""Independent numeric audit of the saved-weight DAILY adaptation experiment.

The audit never fits sklearn and never imports either scientific producer.  It
rebuilds causal splits, saved-weight inference, scores, and all risk books.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


BASE = Path("D:/GexResearchArtifacts/weekly_multiday_20261101")
HERE = Path(__file__).resolve().parent
OUTPUT = BASE / "h2_daily_adaptation_audit_01"
CONTRACT = HERE / "DAILY_ADAPTATION_CONTRACT_20261101.md"
V4 = HERE / "audit_weekly_context_adaptation_v4.py"
HELPER = HERE / "audit_weekly_context_models.py"
TESTS = HERE / "test_audit_weekly_daily_adaptation.py"
UPSTREAM = BASE / "h2_context_adaptation_01"
UPSTREAM_MANIFEST = UPSTREAM / "manifest.json"
UPSTREAM_AUDIT = BASE / "h2_context_adaptation_audit_04" / "audit.json"
UPSTREAM_EXIT = BASE / "h2_context_adaptation_audit_observer_04" / "exit.json"

CONTRACT_SHA256 = "5d388e484435c8fe23d40476c02928887c6ab5487af62197e5e74f08c1fe0047"
V4_SHA256 = "0723696ae01dcc86af7c2af8e8fdc2e3b281ba913987a65d95bd4703c959aa9c"
HELPER_SHA256 = "3eb6b9795ad260971435259858f86d3c00111bcc141973faf986411d4a68ad99"
UPSTREAM_MANIFEST_SHA256 = "e8cf5cd4a001cd98cdf29e54cf47bbdf3c34d6652abf34ef7c71fffa0bd97f23"
UPSTREAM_AUDIT_SHA256 = "9a487fba18504ae4faff2c1dba17d1c000eb237436a09a7fe22747e328cb307a"
UPSTREAM_EXIT_SHA256 = "5d59d1a3978d8d9aa31c7c3fab567d1ae7e901494aa8efb12377ca65f91de420"
UPSTREAM_MANIFEST_BYTES = 17599

PRODUCER_SCHEMA = "weekly_daily_adaptation_manifest_v1"
PRODUCER_STATUS = "COMPLETE_SEEN_DEVELOPMENT_NOT_PROMOTED"
AUDIT_SCHEMA = "weekly_daily_adaptation_audit_v1"
AUDIT_STATUS = "PASS_INDEPENDENT_DAILY_ADAPTATION_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT"
PLAN_SCHEMA = "weekly_daily_adaptation_fit_plans_v1"
SCHEDULE_SCHEMA = "weekly_daily_adaptation_schedule_v1"
SUMMARY_SCHEMA = "weekly_daily_adaptation_summary_v1"
POLICIES = ("FROZEN_CONTEXT182", "MONTHLY_RAW", "WEEKLY_RAW", "DAILY_RAW")
CONTROL_POLICIES = POLICIES[:3]
COSTS = ("base", "adverse")
TICKERS = ("SPY", "QQQ", "SPXW")
START, LAST_ENTRY, END = "20260102", "20260915", "20260917"
EXPECTED_SESSIONS = 178
EXPECTED_REUSED = 42
EXPECTED_NEW = 136
EXPECTED_CANDIDATES = 612
EXPECTED_SCORES = 2448
EXPECTED_JOURNAL_ROWS = 272
EXPECTED_ALL_CANDIDATES = 3240
PROB_TOL = 1e-12
EV_TOL = 1e-8
AGG_TOL = 1e-6
PLAN_KEYS = {
    "state_id", "creation_date", "asof", "frequencies", "cal_sessions",
    "cal_start", "cal_end", "train_ids", "cal_ids", "purged_train_ids",
    "train_label_available_max", "cal_label_available_max",
}
SCHEDULE_KEYS = {
    "date", "state_id", "source", "source_row", "used_for_scoring",
    "terminal_unused_for_scoring",
}
SCORE_KEYS = {
    "candidate_id", "entry_date", "ev_adverse", "ev_base", "is_bridge",
    "model_id", "p_cal", "p_model", "payoff_is_lower_bound", "policy",
    "right", "scenario", "ticker",
}
STATE_DIAGNOSTIC_KEYS = {
    "date", "state_id", "source", "train_n", "cal_n", "purged_n",
    "class_support", "prior", "alpha", "score_count",
    "terminal_unused_for_scoring",
}
COMPARISON_KEYS = {
    "candidate_id", "entry_date", "ticker", "right", "daily_model_id",
    "weekly_model_id", "p_model_diff", "p_cal_diff", "ev_base_diff",
    "ev_adverse_diff", "daily_top1", "weekly_top1", "top1_changed",
}
PRODUCER_FLAGS = {
    "models_fit": True, "reused_states_fit": False, "seen_development": True,
    "raw_read": False, "api_read": False, "broker_read": False,
    "future_labels_used": False, "guarded_used": False,
    "ev_filter_used": False, "selection_made": False,
    "technical_ready": False, "promotion_approved": False,
    "production_changed": False,
}
UPSTREAM_MANIFEST_FLAGS = {
    "api_read": False, "broker_read": False, "frozen_fit": False,
    "future_labels_used": False, "models_fit": True,
    "production_changed": False, "promotion_approved": False,
    "raw_read": False, "seen_development": True,
}
UPSTREAM_AUDIT_FLAGS = {
    "api_read": False, "broker_read": False, "fit_performed": False,
    "producer_imported": False, "production_changed": False,
    "promotion_approved": False, "raw_read": False,
    "saved_weights_used": True, "seen_development": True,
}


def expected_output_names() -> set[str]:
    core = {
        "daily_fit_plans.json", "daily_schedule.json", "daily_states_new.jsonl",
        "fit_journal.jsonl", "candidate_scores.jsonl", "state_diagnostics.jsonl",
        "daily_vs_weekly.jsonl", "summary.json",
    }
    core |= {
        f"ledger_{policy.lower()}_{cost}.jsonl"
        for policy in POLICIES for cost in COSTS
    }
    return core


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def pin(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def plain(path: Path, roots: Iterable[Path]) -> None:
    require(path.is_absolute(), f"absolute path: {path}")
    chosen: tuple[Path, Path] | None = None
    for root in roots:
        try:
            chosen = root, path.relative_to(root)
            break
        except ValueError:
            pass
    require(chosen is not None, f"outside roots: {path}")
    root, relative = chosen
    cursor = root
    for part in relative.parts:
        require(cursor.is_dir() and not cursor.is_symlink(), f"ancestor: {cursor}")
        attrs = getattr(cursor.lstat(), "st_file_attributes", 0)
        require(not attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0), f"reparse: {cursor}")
        cursor /= part
    require(path.is_file() and not path.is_symlink(), f"plain file: {path}")
    attrs = getattr(path.lstat(), "st_file_attributes", 0)
    require(not attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0), f"reparse file: {path}")
    require(path.resolve(strict=True).is_relative_to(root.resolve(strict=True)), f"escaped root: {path}")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            require(line.strip() != "", f"blank row {path}:{number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"object row {path}:{number}")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def import_pinned(path: Path, expected: str, name: str) -> Any:
    plain(path, (HERE,))
    require(sha256_file(path) == expected, f"{name} pin before")
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"{name} spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(sha256_file(path) == expected, f"{name} pin after")
    return module


def assert_close(actual: Any, expected: Any, label: str, tolerance: float = PROB_TOL) -> None:
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), f"{label} keys")
        for key in expected:
            assert_close(actual[key], expected[key], f"{label}.{key}", tolerance)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f"{label} list")
        for index, value in enumerate(expected):
            assert_close(actual[index], value, f"{label}[{index}]", tolerance)
    elif type(expected) is int:
        require(type(actual) is int and actual == expected, f"{label} int")
    elif type(expected) is float:
        require(isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isclose(float(actual), expected, abs_tol=tolerance, rel_tol=0.0), f"{label} float")
    else:
        require(actual == expected, f"{label} value")


def index_unique(rows: list[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    output = {}
    for row in rows:
        value = row.get(key)
        require(isinstance(value, str) and value and value not in output, f"{label} ID {value}")
        output[value] = row
    return output


def find_input(inputs: dict[str, Any], suffix: str) -> Path:
    matches = [Path(name) for name in inputs if name.replace("\\", "/").endswith(suffix.replace("\\", "/"))]
    require(len(matches) == 1, f"input lookup {suffix}: {matches}")
    return matches[0]


def validate_upstream_semantics(
    upstream_manifest: dict[str, Any], upstream_audit: dict[str, Any],
    upstream_exit: dict[str, Any],
) -> None:
    require(
        upstream_manifest.get("schema") == "weekly_context_adaptation_walkforward_v1"
        and upstream_manifest.get("status") == "PASS_SEEN_DEVELOPMENT_GIVEN_BRIDGE_AND_FROZEN_AUTHORITIES"
        and upstream_manifest.get("flags") == UPSTREAM_MANIFEST_FLAGS,
        "upstream manifest semantics",
    )
    require(
        upstream_audit.get("schema") == "weekly_context_adaptation_audit_v1"
        and upstream_audit.get("status") == "PASS_INDEPENDENT_NUMERIC_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT"
        and upstream_audit.get("flags") == UPSTREAM_AUDIT_FLAGS
        and upstream_audit.get("inputs", {}).get("producer_manifest") == {
            "path": str(UPSTREAM_MANIFEST), "bytes": UPSTREAM_MANIFEST_BYTES,
            "sha256": UPSTREAM_MANIFEST_SHA256,
        },
        "upstream audit binding/semantics",
    )
    require(upstream_exit.get("exit_code") == 0, "upstream audit exit")


def admit(
    producer_root: Path, producer_manifest_sha256: str, producer_exit: Path,
    producer_exit_sha256: str, auditor_sha256: str, tests_sha256: str,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    roots = (BASE, HERE)
    require(producer_root == BASE / "h2_daily_adaptation_01", "fixed producer root")
    producer_manifest = producer_root / "manifest.json"
    authorities = {
        producer_manifest: producer_manifest_sha256, producer_exit: producer_exit_sha256,
        Path(__file__).resolve(): auditor_sha256, TESTS: tests_sha256,
        CONTRACT: CONTRACT_SHA256,
        V4: V4_SHA256, HELPER: HELPER_SHA256,
        UPSTREAM_MANIFEST: UPSTREAM_MANIFEST_SHA256,
        UPSTREAM_AUDIT: UPSTREAM_AUDIT_SHA256, UPSTREAM_EXIT: UPSTREAM_EXIT_SHA256,
    }
    for path, digest in authorities.items():
        require(len(digest) == 64, f"SHA required {path}")
        plain(path, roots)
        require(sha256_file(path) == digest, f"authority pin {path}")
    require(read_json(producer_exit).get("exit_code") == 0, "producer exit")
    upstream_manifest_doc = read_json(UPSTREAM_MANIFEST)
    validate_upstream_semantics(
        upstream_manifest_doc, read_json(UPSTREAM_AUDIT), read_json(UPSTREAM_EXIT),
    )
    manifest = read_json(producer_manifest)
    require(manifest.get("schema") == PRODUCER_SCHEMA and manifest.get("status") == PRODUCER_STATUS, "producer manifest status")
    require(set(manifest) == {"schema", "status", "inputs", "outputs", "flags"}, "producer manifest schema")
    require(manifest["flags"] == PRODUCER_FLAGS, "producer manifest flags")
    snapshots = {str(path): pin(path) for path in authorities}
    for name, binding in frozen_transitive_payloads(upstream_manifest_doc).items():
        path = Path(name)
        plain(path, roots)
        require(
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)} == binding,
            f"transitive frozen pin {name}",
        )
        snapshots[name] = pin(path)
    inputs = manifest["inputs"]
    require(isinstance(inputs, dict), "producer inputs")
    for name, binding in inputs.items():
        path = Path(name)
        plain(path, roots)
        require(set(binding) == {"before", "after"} and binding["before"] == binding["after"], f"input closure {name}")
        actual = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        require(actual == binding["before"], f"input pin {name}")
        snapshots[name] = pin(path)
    required_inputs = {
        UPSTREAM_MANIFEST: UPSTREAM_MANIFEST_SHA256,
        UPSTREAM_AUDIT: UPSTREAM_AUDIT_SHA256,
        UPSTREAM_EXIT: UPSTREAM_EXIT_SHA256,
        CONTRACT: CONTRACT_SHA256,
    }
    for path, digest in required_inputs.items():
        require(str(path.resolve()) in inputs, f"required producer input {path}")
        require(inputs[str(path.resolve())]["before"]["sha256"] == digest, f"required input SHA {path}")
    outputs = manifest["outputs"]
    require(isinstance(outputs, dict), "producer outputs")
    state_outputs = {
        name for name in outputs
        if name.startswith("fit_state_CONTEXT182_") and name.endswith(".json")
    }
    require(
        len(state_outputs) == EXPECTED_NEW
        and set(outputs) == expected_output_names() | state_outputs,
        "producer output allowlist/count",
    )
    for name, expected in outputs.items():
        require(Path(name).name == name and set(expected) == {"bytes", "sha256"}, f"output binding {name}")
        path = producer_root / name
        plain(path, (producer_root,))
        require({"bytes": path.stat().st_size, "sha256": sha256_file(path)} == expected, f"output pin {name}")
        snapshots[str(path)] = pin(path)
    return manifest, snapshots


def revalidate(snapshots: dict[str, dict[str, Any]]) -> None:
    for name, before in snapshots.items():
        current = pin(Path(name))
        require(current["bytes"] == before["bytes"] and current["sha256"] == before["sha256"], f"changed input/output {name}")


def attach_context(helper: Any, candidates: list[dict[str, Any]], contexts: list[dict[str, Any]]) -> None:
    context_index = {}
    for value in contexts:
        key = (value.get("ticker"), value.get("date"))
        require(key not in context_index, f"context duplicate {key}")
        context_index[key] = value
    for value in candidates:
        key = (value["ticker"], value["entry_date"])
        require(key in context_index, f"context missing {key}")
        value["_x_context"] = helper.context182(value, context_index[key])


def common_calendar(h1: dict[str, Any], q3: dict[str, Any]) -> tuple[list[str], list[str]]:
    rows = [*h1["calendar"], *q3["calendar"]]
    by_ticker = {
        ticker: sorted(row["date"] for row in rows if row["ticker"] == ticker)
        for ticker in TICKERS
    }
    require(all(values == by_ticker["SPY"] for values in by_ticker.values()), "common calendar")
    full = by_ticker["SPY"]
    require(len(full) == 930 and full == sorted(set(full)), "full calendar count")
    evaluation = [day for day in full if START <= day <= END]
    require(len(evaluation) == EXPECTED_SESSIONS, "evaluation calendar")
    return full, evaluation


def validate_bridge(candidates: list[dict[str, Any]], coverage: dict[str, Any]) -> None:
    require(len(candidates) == 6, "bridge candidate count")
    ids = index_unique(candidates, "candidate_id", "bridge candidate")
    require(
        all(row.get("entry_date") == "20260629" and row.get("exit_date") == "20260701" for row in ids.values()),
        "bridge candidate dates",
    )
    rows = coverage.get("rows")
    require(isinstance(rows, list) and len(rows) == 6, "bridge coverage count")
    keys = {(row.get("ticker"), row.get("entry_date")) for row in rows}
    require(keys == {(ticker, day) for ticker in TICKERS for day in ("20260629", "20260630")}, "bridge coverage identities")
    covered_ids: set[str] = set()
    for row in rows:
        require(row.get("exit_date") == ("20260701" if row["entry_date"] == "20260629" else "20260702"), "bridge exit date")
        candidate_ids = row.get("candidate_ids")
        require(isinstance(candidate_ids, list) and len(candidate_ids) == len(set(candidate_ids)), "bridge coverage IDs")
        if row["entry_date"] == "20260630":
            require(row.get("status") == "NO_SERIES" and candidate_ids == [], "bridge June30 NO_SERIES")
        else:
            require(row.get("status") == "CANDIDATES_BUILT" and len(candidate_ids) == 2, "bridge June29 candidates")
            covered_ids.update(candidate_ids)
    require(covered_ids == set(ids), "bridge candidate/coverage closure")


def winner_ids(rows: list[dict[str, Any]]) -> set[str]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((row["entry_date"], row["ticker"]), []).append(row)
    output: set[str] = set()
    for values in grouped.values():
        best = max(float(row["ev_adverse"]) for row in values)
        winners = [row for row in values if float(row["ev_adverse"]) == best]
        if best > 0.0 and len(winners) == 1:
            output.add(winners[0]["candidate_id"])
    return output


def validate_diagnostics(
    producer_root: Path, states: dict[str, dict[str, Any]], plans: dict[str, dict[str, Any]],
    validations: dict[str, dict[str, Any]], schedule: dict[str, dict[str, Any]],
    scores: list[dict[str, Any]], reused_ids: set[str],
) -> dict[str, int]:
    state_rows = read_jsonl(producer_root / "state_diagnostics.jsonl")
    require(len(state_rows) == EXPECTED_SESSIONS, "state diagnostic count")
    state_index = index_unique(state_rows, "state_id", "state diagnostic")
    score_counts: dict[str, int] = {}
    for row in scores:
        if row["policy"] == "DAILY_RAW":
            score_counts[row["entry_date"]] = score_counts.get(row["entry_date"], 0) + 1
    for state_id, state in states.items():
        row = state_index[state_id]
        plan, validation = plans[state_id], validations[state_id]
        day = plan["creation_date"]
        require(set(row) == STATE_DIAGNOSTIC_KEYS, f"state diagnostic schema {state_id}")
        expected = {
            "date": day, "state_id": state_id,
            "source": "REUSED" if state_id in reused_ids else "NEW",
            "train_n": len(plan["train_ids"]), "cal_n": len(plan["cal_ids"]),
            "purged_n": len(plan["purged_train_ids"]),
            "class_support": state["prior_support"], "prior": state["prior"],
            "alpha": validation["alpha"], "score_count": score_counts.get(day, 0),
            "terminal_unused_for_scoring": schedule[day]["terminal_unused_for_scoring"],
        }
        assert_close(row, expected, f"state diagnostic {state_id}")

    comparison_rows = read_jsonl(producer_root / "daily_vs_weekly.jsonl")
    require(len(comparison_rows) == EXPECTED_CANDIDATES, "daily/weekly diagnostic count")
    comparison_index = index_unique(comparison_rows, "candidate_id", "daily/weekly diagnostic")
    score_index = {(row["policy"], row["candidate_id"]): row for row in scores}
    daily_rows = [row for row in scores if row["policy"] == "DAILY_RAW"]
    weekly_rows = [row for row in scores if row["policy"] == "WEEKLY_RAW"]
    daily_winners, weekly_winners = winner_ids(daily_rows), winner_ids(weekly_rows)
    changed = 0
    for candidate_id, actual in comparison_index.items():
        require(set(actual) == COMPARISON_KEYS, f"daily/weekly schema {candidate_id}")
        daily, weekly = score_index[("DAILY_RAW", candidate_id)], score_index[("WEEKLY_RAW", candidate_id)]
        daily_top, weekly_top = candidate_id in daily_winners, candidate_id in weekly_winners
        expected = {
            "candidate_id": candidate_id, "entry_date": daily["entry_date"],
            "ticker": daily["ticker"], "right": daily["right"],
            "daily_model_id": daily["model_id"], "weekly_model_id": weekly["model_id"],
            "p_model_diff": [float(a) - float(b) for a, b in zip(daily["p_model"], weekly["p_model"], strict=True)],
            "p_cal_diff": [float(a) - float(b) for a, b in zip(daily["p_cal"], weekly["p_cal"], strict=True)],
            "ev_base_diff": float(daily["ev_base"]) - float(weekly["ev_base"]),
            "ev_adverse_diff": float(daily["ev_adverse"]) - float(weekly["ev_adverse"]),
            "daily_top1": daily_top, "weekly_top1": weekly_top,
            "top1_changed": daily_top != weekly_top,
        }
        changed += int(expected["top1_changed"])
        for key in ("p_model_diff", "p_cal_diff"):
            assert_close(actual[key], expected[key], f"daily/weekly {candidate_id}.{key}", PROB_TOL)
        for key in ("ev_base_diff", "ev_adverse_diff"):
            assert_close(actual[key], expected[key], f"daily/weekly {candidate_id}.{key}", EV_TOL)
        for key in set(expected) - {"p_model_diff", "p_cal_diff", "ev_base_diff", "ev_adverse_diff"}:
            require(actual[key] == expected[key], f"daily/weekly {candidate_id}.{key}")
    return {"state_rows": len(state_rows), "candidate_rows": len(comparison_rows), "top1_changed": changed}


def validate_schedule(
    schedule_doc: dict[str, Any], plans_doc: dict[str, Any],
    upstream_plans: list[dict[str, Any]], upstream_states_rows: list[dict[str, Any]],
    sessions: list[str], reused_source: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], set[str], set[str]]:
    require(
        set(schedule_doc) == {"schema", "count", "reused_source", "rows"}
        and schedule_doc.get("schema") == SCHEDULE_SCHEMA
        and schedule_doc.get("count") == EXPECTED_SESSIONS
        and schedule_doc.get("reused_source") == reused_source,
        "schedule header/source",
    )
    schedule_rows = schedule_doc.get("rows")
    require(isinstance(schedule_rows, list) and len(schedule_rows) == EXPECTED_SESSIONS, "schedule rows")
    schedule = index_unique(schedule_rows, "date", "schedule")
    require(list(schedule) == sessions, "schedule dates/order")
    require(
        set(plans_doc) == {"schema", "count", "plans"}
        and plans_doc.get("schema") == PLAN_SCHEMA
        and plans_doc.get("count") == EXPECTED_SESSIONS,
        "plans header",
    )
    plans = index_unique(plans_doc.get("plans", []), "state_id", "plan")
    require(len(plans) == EXPECTED_SESSIONS and all(set(plan) == PLAN_KEYS for plan in plans.values()), "plan schema/count")
    upstream = index_unique(upstream_plans, "state_id", "upstream plan")
    upstream_states = index_unique(upstream_states_rows, "state_id", "upstream state row")
    require(set(upstream_states) == set(upstream), "upstream state/plan closure")
    reused, new = set(), set()
    for index, day in enumerate(sessions):
        row = schedule[day]
        require(set(row) == SCHEDULE_KEYS and row["state_id"] == f"CONTEXT182_{day}", f"schedule row {day}")
        terminal = day in {"20260916", "20260917"}
        require(row["terminal_unused_for_scoring"] is terminal and row["used_for_scoring"] is (not terminal), f"schedule terminal {day}")
        plan = plans[row["state_id"]]
        require(plan["creation_date"] == day, f"plan date {day}")
        if row["source"] == "REUSED":
            require(type(row["source_row"]) is int and 0 <= row["source_row"] < EXPECTED_REUSED, "reused source row")
            source_state = upstream_states_rows[row["source_row"]]
            require(source_state["state_id"] == row["state_id"], f"reused source row exact {day}")
            require(plan == upstream[row["state_id"]], f"reused plan exact {day}")
            reused.add(row["state_id"])
        else:
            require(row["source"] == "NEW" and row["source_row"] is None, f"new source {day}")
            require(plan["frequencies"] == ["DAILY"], f"new DAILY frequency {day}")
            new.add(row["state_id"])
    require(len(reused) == EXPECTED_REUSED and set(upstream) == reused, "reused closure")
    require(len(new) == EXPECTED_NEW and reused.isdisjoint(new), "new closure")
    return plans, reused, new


def validate_state_versions(states: dict[str, dict[str, Any]]) -> str:
    versions = {
        state.get("model", {}).get("sklearn_version")
        for state in states.values()
    }
    require(
        len(versions) == 1
        and all(isinstance(version, str) and version for version in versions),
        "saved state sklearn version coherence",
    )
    return next(iter(versions))


def frozen_state(inputs: dict[str, Any]) -> dict[str, Any]:
    transform = read_json(find_input(inputs, "/h2_context_model_comparison_01/context182_transform.json"))
    model = read_json(find_input(inputs, "/h2_context_model_comparison_01/context182_model.json"))
    calibration = read_json(find_input(inputs, "/h2_context_model_comparison_01/context182_calibration.json"))
    ev_model = read_json(find_input(inputs, "/h2_ev_v2_01/model.json"))
    means = read_json(find_input(inputs, "/h2_ev_v2_01/conditional_means.json"))
    return {
        "state_id": "FROZEN_CONTEXT182_H1",
        "feature_order": transform["feature_order"], "transform": transform,
        "model": model, "prior": ev_model["train_prior"],
        "conditional_means": means, "calibration": calibration,
        "inference": "FROZEN_H1_HELPER",
    }


def frozen_transitive_payloads(upstream_manifest: dict[str, Any]) -> dict[str, Any]:
    consumed = upstream_manifest.get("consumed_payloads")
    require(isinstance(consumed, dict), "upstream consumed payloads")
    suffixes = (
        "/h2_context_model_comparison_01/context182_transform.json",
        "/h2_context_model_comparison_01/context182_model.json",
        "/h2_context_model_comparison_01/context182_calibration.json",
        "/h2_ev_v2_01/model.json",
        "/h2_ev_v2_01/conditional_means.json",
    )
    selected: dict[str, Any] = {}
    for suffix in suffixes:
        path = find_input(consumed, suffix)
        binding = consumed[str(path)]
        require(
            set(binding) == {"path", "bytes", "sha256"}
            and binding["path"] == str(path),
            f"transitive frozen binding {suffix}",
        )
        selected[str(path)] = binding
    require(len(selected) == 5, "transitive frozen payload closure")
    return selected


def control_model_clock(
    sessions: list[str], plans: dict[str, dict[str, Any]],
) -> dict[str, dict[str, str]]:
    plans_by_day = {plan["creation_date"]: plan for plan in plans.values()}
    current = {"MONTHLY_RAW": None, "WEEKLY_RAW": None}
    output = {policy: {} for policy in CONTROL_POLICIES}
    for day in sessions:
        output["FROZEN_CONTEXT182"][day] = "FROZEN_CONTEXT182_H1"
        plan = plans_by_day.get(day)
        for policy, cadence in (("MONTHLY_RAW", "MONTHLY"), ("WEEKLY_RAW", "WEEKLY")):
            if plan is not None and cadence in plan["frequencies"]:
                current[policy] = plan["state_id"]
            require(isinstance(current[policy], str), f"active control model {policy}/{day}")
            output[policy][day] = current[policy]
    return output


def validate_journal(
    rows: list[dict[str, Any]], new_ids: set[str], state_files: dict[str, Path], states: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    require(len(rows) == EXPECTED_JOURNAL_ROWS, "journal row count")
    by_state: dict[str, list[dict[str, Any]]] = {state_id: [] for state_id in new_ids}
    for row in rows:
        require(set(row) == {"event", "state_id", "creation_date", "asof", "utc", "gate", "state_sha256"}, "journal schema")
        require(row.get("state_id") in by_state, "journal new state only")
        by_state[row["state_id"]].append(row)
    for state_id, events in by_state.items():
        require(len(events) == 2 and [row["event"] for row in events] == ["FIT_START", "FIT_COMPLETE"], f"journal events {state_id}")
        start, complete = events
        require(start["event"] == "FIT_START" and complete["event"] == "FIT_COMPLETE", f"journal event literal {state_id}")
        require(start["state_sha256"] is None and isinstance(complete["state_sha256"], str) and len(complete["state_sha256"]) == 64, f"journal state hash {state_id}")
        require(start["creation_date"] == complete["creation_date"] == states[state_id]["creation_date"], f"journal date {state_id}")
        require(start["asof"] == complete["asof"] == states[state_id]["asof"], f"journal asof {state_id}")
        start_time, complete_time = datetime.fromisoformat(start["utc"]), datetime.fromisoformat(complete["utc"])
        require(start_time.tzinfo is not None and complete_time.tzinfo is not None and start_time < complete_time, f"journal time {state_id}")
        for event in events:
            gate = event.get("gate")
            require(isinstance(gate, dict) and set(gate) == {"available_ram_bytes", "free_commit_bytes"}, f"journal gate schema {state_id}")
            require(all(type(gate[key]) is int and gate[key] >= 2_000_000_000 for key in gate), f"journal gate {state_id}")
        require(sha256_file(state_files[state_id]) == complete["state_sha256"], f"journal persistent hash {state_id}")
        assert_close(read_json(state_files[state_id]), states[state_id], f"persistent state {state_id}")
    return {"rows": len(rows), "fits": len(by_state)}


def compare_score(actual: dict[str, Any], rebuilt: dict[str, Any], label: str) -> None:
    require(set(actual) == SCORE_KEYS, f"score schema {label}")
    require(actual["candidate_id"] == rebuilt["candidate_id"], f"score ID {label}")
    assert_close(actual["p_model"], rebuilt["p_model"], f"score p_model {label}", PROB_TOL)
    assert_close(actual["p_cal"], rebuilt["p_cal"], f"score p_cal {label}", PROB_TOL)
    assert_close(actual["ev_base"], rebuilt["ev_base"], f"score EV base {label}", EV_TOL)
    assert_close(actual["ev_adverse"], rebuilt["ev_adverse"], f"score EV adverse {label}", EV_TOL)


def strip_annotations(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in {"policy", "model_id"}}


def compare_ledgers(actual: list[dict[str, Any]], rebuilt: list[dict[str, Any]], label: str) -> None:
    require(len(actual) == len(rebuilt), f"ledger length {label}")
    for index, (left, right) in enumerate(zip(actual, rebuilt, strict=True)):
        normalized = strip_annotations(left)
        require(set(normalized) == set(right), f"ledger keys {label}/{index}")
        assert_close(normalized, right, f"ledger {label}/{index}", AGG_TOL)


def numeric_audit(
    producer_root: Path, manifest: dict[str, Any], v4: Any, helper: Any,
) -> dict[str, Any]:
    inputs = manifest["inputs"]
    h1_candidates = read_jsonl(find_input(inputs, "/h2_dataset_v2_01/candidates.jsonl"))
    q3_candidates = read_jsonl(find_input(inputs, "/h2_dataset_v2_extension_2026q3_partial_01/candidates.jsonl"))
    bridge_candidates = read_jsonl(find_input(inputs, "/h2_boundary_bridge_01/candidates.jsonl"))
    bridge_ids = {row["candidate_id"] for row in bridge_candidates}
    candidates = [*h1_candidates, *q3_candidates, *bridge_candidates]
    rows_by_id = index_unique(candidates, "candidate_id", "candidate")
    require(len(rows_by_id) == EXPECTED_ALL_CANDIDATES, "candidate count")
    h1_context = read_jsonl(find_input(inputs, "/h2_context_1030_01/context.jsonl"))
    q3_context = read_jsonl(find_input(inputs, "/h2_context_q3_1030_01/context.jsonl"))
    attach_context(helper, candidates, [*h1_context, *q3_context])
    h1_coverage = read_json(find_input(inputs, "/h2_dataset_v2_01/coverage.json"))
    q3_coverage = read_json(find_input(inputs, "/h2_dataset_v2_extension_2026q3_partial_01/coverage.json"))
    bridge_coverage = read_json(find_input(inputs, "/h2_boundary_bridge_01/coverage_overlay.json"))
    validate_bridge(bridge_candidates, bridge_coverage)
    full_calendar, sessions = common_calendar(h1_coverage, q3_coverage)
    coverage_index = {(row["ticker"], row["entry_date"]): row for row in [*h1_coverage["rows"], *q3_coverage["rows"]]}
    for row in bridge_coverage["rows"]:
        coverage_index[(row["ticker"], row["entry_date"])] = row
    coverage_eval = [coverage_index[(ticker, day)] for day in sessions for ticker in TICKERS]

    upstream_plans_doc = read_json(find_input(inputs, "/h2_context_adaptation_01/fit_plans.json"))
    upstream_states_path = find_input(inputs, "/h2_context_adaptation_01/states.jsonl")
    upstream_states_rows = read_jsonl(upstream_states_path)
    upstream_states = index_unique(upstream_states_rows, "state_id", "upstream state")
    plans_doc = read_json(producer_root / "daily_fit_plans.json")
    schedule_doc = read_json(producer_root / "daily_schedule.json")
    plans, reused_ids, new_ids = validate_schedule(
        schedule_doc, plans_doc, upstream_plans_doc["plans"], upstream_states_rows,
        sessions,
        pin(upstream_states_path),
    )
    new_states_rows = read_jsonl(producer_root / "daily_states_new.jsonl")
    new_states = index_unique(new_states_rows, "state_id", "new state")
    require(set(new_states) == new_ids, "new state IDs")
    states = {**upstream_states, **new_states}
    require(set(states) == reused_ids | new_ids and len(states) == EXPECTED_SESSIONS, "all state closure")
    saved_sklearn_version = validate_state_versions(states)
    validations = {}
    for state_id in sorted(states):
        validations[state_id] = v4.validate_saved_state(helper, states[state_id], plans[state_id], rows_by_id, full_calendar)

    state_files = {state_id: producer_root / f"fit_state_{state_id}.json" for state_id in new_ids}
    journal = validate_journal(read_jsonl(producer_root / "fit_journal.jsonl"), new_ids, state_files, states)

    scores = read_jsonl(producer_root / "candidate_scores.jsonl")
    require(len(scores) == EXPECTED_SCORES, "score count")
    score_index = {(row["policy"], row["candidate_id"]): row for row in scores}
    require(len(score_index) == EXPECTED_SCORES, "score uniqueness")
    upstream_scores = read_jsonl(find_input(inputs, "/h2_context_adaptation_01/candidate_scores.jsonl"))
    upstream_score_index = {(row["policy"], row["candidate_id"]): row for row in upstream_scores}
    for policy in CONTROL_POLICIES:
        for candidate_id in {row["candidate_id"] for row in upstream_scores if row["policy"] == policy}:
            require(score_index[(policy, candidate_id)] == upstream_score_index[(policy, candidate_id)], f"control score copy {policy}/{candidate_id}")

    schedule_index = {row["date"]: row for row in schedule_doc["rows"]}
    eval_candidates = [row for row in candidates if ("FROZEN_CONTEXT182", row["candidate_id"]) in upstream_score_index]
    require(len(eval_candidates) == EXPECTED_CANDIDATES, "evaluation candidate count")
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in eval_candidates:
        by_date.setdefault(row["entry_date"], []).append(row)
    frozen = frozen_state(frozen_transitive_payloads(read_json(UPSTREAM_MANIFEST)))
    require(frozen["model"].get("sklearn_version") == saved_sklearn_version, "frozen/adaptive sklearn version")
    all_states = {**states, frozen["state_id"]: frozen}
    control_clock = control_model_clock(sessions, plans)
    for policy in CONTROL_POLICIES:
        for source in eval_candidates:
            actual = score_index[(policy, source["candidate_id"])]
            expected_model = control_clock[policy][source["entry_date"]]
            require(
                actual["model_id"] == expected_model
                and actual["entry_date"] == source["entry_date"]
                and actual["ticker"] == source["ticker"]
                and actual["right"] == source["right"]
                and actual["scenario"] == source["scenario"]
                and actual["payoff_is_lower_bound"] is source["payoff_is_lower_bound"]
                and actual["is_bridge"] is (source["candidate_id"] in bridge_ids),
                f"control identity/model clock {policy}/{source['candidate_id']}",
            )
            rebuilt = v4.score_state(helper, all_states[expected_model], [source])[0]
            compare_score(actual, rebuilt, f"{policy}/{source['candidate_id']}")
    rebuilt_daily = []
    for day in sessions:
        rows = sorted(by_date.get(day, []), key=lambda row: row["candidate_id"])
        if not rows:
            continue
        state = states[schedule_index[day]["state_id"]]
        rebuilt = v4.score_state(helper, state, rows)
        for source, rebuilt_row in zip(rows, rebuilt, strict=True):
            actual = score_index[("DAILY_RAW", source["candidate_id"])]
            compare_score(actual, rebuilt_row, f"DAILY/{source['candidate_id']}")
            require(
                actual["model_id"] == state["state_id"]
                and actual["entry_date"] == day
                and actual["policy"] == "DAILY_RAW"
                and actual["ticker"] == source["ticker"]
                and actual["right"] == source["right"]
                and actual["scenario"] == source["scenario"]
                and actual["payoff_is_lower_bound"] is source["payoff_is_lower_bound"]
                and actual["is_bridge"] is (source["candidate_id"] in bridge_ids),
                "daily score metadata/clock",
            )
            rebuilt_daily.append(actual)
            if state["state_id"] in reused_ids:
                matches = [value for value in upstream_scores if value["candidate_id"] == source["candidate_id"] and value["model_id"] == state["state_id"]]
                require(matches and all(value["p_model"] == actual["p_model"] and value["p_cal"] == actual["p_cal"] and value["ev_base"] == actual["ev_base"] and value["ev_adverse"] == actual["ev_adverse"] for value in matches), "reused score exact copy")
    require(len(rebuilt_daily) == EXPECTED_CANDIDATES, "daily rebuilt score count")

    metrics = {}
    rebuilt_policies = {}
    for policy in POLICIES:
        policy_scores = {row["candidate_id"]: row for row in scores if row["policy"] == policy}
        require(len(policy_scores) == EXPECTED_CANDIDATES, f"policy score count {policy}")
        replay_rows = []
        model_by_candidate = {}
        for source in eval_candidates:
            value = dict(source)
            score = policy_scores[source["candidate_id"]]
            value["_ev_base"], value["_ev_adverse"] = score["ev_base"], score["ev_adverse"]
            replay_rows.append(value)
            model_by_candidate[source["candidate_id"]] = score["model_id"]
        books = helper.replay_risk(replay_rows, coverage_eval, sessions, LAST_ENTRY)
        selected = helper.selected_ids(books["adverse"])
        filled = {row["candidate_id"] for row in books["adverse"] if row["event"] == "ENTRY"}
        for cost in COSTS:
            actual = read_jsonl(producer_root / f"ledger_{policy.lower()}_{cost}.jsonl")
            if policy in CONTROL_POLICIES:
                upstream_ledger_path = find_input(inputs, f"/h2_context_adaptation_01/ledger_{policy.lower()}_{cost}.jsonl")
                upstream_ledger = read_jsonl(upstream_ledger_path)
                require(
                    (producer_root / f"ledger_{policy.lower()}_{cost}.jsonl").read_bytes() == upstream_ledger_path.read_bytes(),
                    f"control ledger byte copy {policy}/{cost}",
                )
                require(actual == upstream_ledger, f"control ledger byte-semantic copy {policy}/{cost}")
            compare_ledgers(actual, books[cost], f"{policy}/{cost}")
            annotated = []
            for event in books[cost]:
                value = dict(event)
                candidate_id = value.get("candidate_id")
                value["policy"] = policy
                value["model_id"] = model_by_candidate.get(candidate_id) if candidate_id else None
                annotated.append(value)
            metrics.setdefault(policy, {})[cost] = v4.extended_book_metrics(helper, annotated, sessions)
        metric_rows = []
        for source in eval_candidates:
            value = dict(source)
            score = policy_scores[source["candidate_id"]]
            value["_model_label_eligible"] = True
            value[f"_p_{policy}"] = score["p_cal"]
            value[f"_ev_{policy}_base"] = score["ev_base"]
            value[f"_ev_{policy}_adverse"] = score["ev_adverse"]
            metric_rows.append(value)
        probability_ev = {
            "all": v4.combined_probability_ev(helper, metric_rows, policy, None, False),
            "selected": v4.combined_probability_ev(helper, metric_rows, policy, selected, False),
            "all_observed_only": v4.combined_probability_ev(helper, metric_rows, policy, None, True),
            "selected_observed_only": v4.combined_probability_ev(helper, metric_rows, policy, selected, True),
        }
        rebuilt_policies[policy] = {
            "economics": metrics[policy], "probability_ev": probability_ev,
            "selected_ids": sorted(selected), "filled_ids": sorted(filled),
            "adverse_net_minus_frozen": None,
        }

    diagnostics = validate_diagnostics(
        producer_root, states, plans, validations, schedule_index, scores, reused_ids,
    )
    summary = read_json(producer_root / "summary.json")
    require(
        set(summary) == {"schema", "status", "scope", "states", "policies", "comparisons", "criterion", "diagnostics", "flags"}
        and summary.get("schema") == SUMMARY_SCHEMA and summary.get("status") == PRODUCER_STATUS,
        "summary header",
    )
    require(summary["flags"] == PRODUCER_FLAGS, "summary flags")
    require(summary["scope"] == {
        "sessions": EXPECTED_SESSIONS, "candidate_universe": EXPECTED_CANDIDATES,
        "policies": list(POLICIES), "scores": EXPECTED_SCORES, "books": 8,
    }, "summary scope")
    require(summary["states"] == {
        "daily": EXPECTED_SESSIONS, "reused": EXPECTED_REUSED,
        "new": EXPECTED_NEW, "terminal_unused": 2,
    }, "summary states")
    require(summary["diagnostics"] == diagnostics, "summary diagnostics")
    upstream_summary = read_json(find_input(inputs, "/h2_context_adaptation_01/summary.json"))
    for policy in CONTROL_POLICIES:
        require(summary["policies"][policy] == upstream_summary["policies"][policy], f"control summary copy {policy}")
    frozen_net = rebuilt_policies["FROZEN_CONTEXT182"]["economics"]["adverse"]["net_usd"]
    for policy in POLICIES:
        rebuilt_policies[policy]["adverse_net_minus_frozen"] = rebuilt_policies[policy]["economics"]["adverse"]["net_usd"] - frozen_net
        assert_close(summary["policies"][policy], rebuilt_policies[policy], f"summary policy {policy}", AGG_TOL)
    comparisons = {}
    for baseline in ("WEEKLY_RAW", "MONTHLY_RAW"):
        comparisons[baseline] = {}
        for cost in COSTS:
            daily_monthly = rebuilt_policies["DAILY_RAW"]["economics"][cost]["details"]["monthly_net_including_zeros"]
            baseline_monthly = rebuilt_policies[baseline]["economics"][cost]["details"]["monthly_net_including_zeros"]
            comparisons[baseline][cost] = {
                "total_net_usd": rebuilt_policies["DAILY_RAW"]["economics"][cost]["net_usd"] - rebuilt_policies[baseline]["economics"][cost]["net_usd"],
                "monthly_net_usd": {month: daily_monthly[month] - baseline_monthly[month] for month in daily_monthly},
            }
    assert_close(summary["comparisons"], comparisons, "summary comparisons", AGG_TOL)
    complete_months = [f"2026{month:02d}" for month in range(1, 9)]
    daily_monthly = rebuilt_policies["DAILY_RAW"]["economics"]["adverse"]["details"]["monthly_net_including_zeros"]
    passed = all(float(daily_monthly[month]) > 0.0 for month in complete_months)
    require(summary["criterion"] == {
        "months": complete_months,
        "necessary": "DAILY_RAW adverse exit-date net strictly positive in every complete month",
        "daily_passes_8_of_8": passed, "selected_policy": None,
        "promotion_approved": False,
    }, "summary criterion")
    return {
        "sessions": len(sessions), "plans": len(plans), "reused_states": len(reused_ids),
        "new_states": len(new_ids), "validated_states": len(validations),
        "saved_sklearn_version": saved_sklearn_version,
        "scores": len(scores), "daily_scores": len(rebuilt_daily), "journal": journal,
        "books": len(POLICIES) * len(COSTS), "diagnostics": diagnostics,
    }


def run(
    producer_root: Path, producer_manifest_sha256: str, producer_exit: Path,
    producer_exit_sha256: str, auditor_sha256: str, tests_sha256: str,
    output: Path = OUTPUT,
) -> dict[str, Any]:
    require(output == OUTPUT and not output.exists(), "exclusive audit output")
    manifest, snapshots = admit(
        producer_root, producer_manifest_sha256, producer_exit,
        producer_exit_sha256, auditor_sha256, tests_sha256,
    )
    v4 = import_pinned(V4, V4_SHA256, "sealed_adaptation_auditor_v4")
    helper = import_pinned(HELPER, HELPER_SHA256, "sealed_context_audit_helper")
    numeric = numeric_audit(producer_root, manifest, v4, helper)
    revalidate(snapshots)
    output.mkdir(parents=False, exist_ok=False)
    result = {
        "schema": AUDIT_SCHEMA, "status": AUDIT_STATUS,
        "inputs": {
            "producer_manifest": pin(producer_root / "manifest.json"),
            "producer_exit": pin(producer_exit), "auditor": pin(Path(__file__).resolve()),
            "tests": pin(TESTS),
            "contract": pin(CONTRACT), "v4_helper": pin(V4), "context_helper": pin(HELPER),
        },
        "numeric": numeric,
        "flags": {
            "fit_performed": False, "inference_from_saved_weights": True,
            "raw_read": False, "api_read": False, "broker_read": False,
            "producer_imported": False, "production_changed": False,
            "promotion_approved": False, "seen_development": True,
        },
        "limitations": "Independent reconstruction given saved weights; sklearn training was not repeated.",
    }
    write_json(output / "audit.json", result)
    revalidate(snapshots)
    write_json(output / "manifest.json", {
        "schema": "weekly_daily_adaptation_audit_manifest_v1", "status": AUDIT_STATUS,
        "audit.json": {"bytes": (output / "audit.json").stat().st_size, "sha256": sha256_file(output / "audit.json")},
    })
    revalidate(snapshots)
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--execute-reviewed-audit", action="store_true")
    value.add_argument("--producer-root", type=Path)
    value.add_argument("--producer-manifest-sha256")
    value.add_argument("--producer-exit", type=Path)
    value.add_argument("--producer-exit-sha256")
    value.add_argument("--auditor-sha256")
    value.add_argument("--tests-sha256")
    value.add_argument("--output", type=Path, default=OUTPUT)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.execute_reviewed_audit:
        print(json.dumps({"status": "READY_NOT_EXECUTED", "output": str(args.output), "scope": "saved-weight DAILY independent audit; no fit/raw"}, sort_keys=True))
        return 0
    pins = (
        args.producer_manifest_sha256, args.producer_exit_sha256,
        args.auditor_sha256, args.tests_sha256,
    )
    require(args.producer_root is not None and args.producer_exit is not None and all(isinstance(value, str) and len(value) == 64 for value in pins), "reviewed CLI arguments")
    result = run(
        args.producer_root.resolve(), args.producer_manifest_sha256,
        args.producer_exit.resolve(), args.producer_exit_sha256,
        args.auditor_sha256, args.tests_sha256, args.output.resolve(),
    )
    print(json.dumps({"status": result["status"], "audit": str(args.output / "audit.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
