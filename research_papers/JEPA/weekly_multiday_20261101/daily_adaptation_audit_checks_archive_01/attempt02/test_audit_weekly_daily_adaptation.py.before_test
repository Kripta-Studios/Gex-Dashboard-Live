from __future__ import annotations

import ast
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import audit_weekly_daily_adaptation as audit


def dump_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def plan(state_id: str, day: str, frequencies: list[str]) -> dict:
    return {
        "state_id": state_id, "creation_date": day,
        "asof": f"{day[:4]}-{day[4:6]}-{day[6:]}T00:00:00-05:00",
        "frequencies": frequencies, "cal_sessions": [f"C{i:02d}" for i in range(63)],
        "cal_start": "C00", "cal_end": "C62", "train_ids": ["TRAIN"],
        "cal_ids": ["CAL"], "purged_train_ids": ["PURGED"],
        "train_label_available_max": "2025-01-01T10:35:00-05:00",
        "cal_label_available_max": "2025-12-31T10:35:00-05:00",
    }


def schedule_fixture() -> tuple[list[str], dict, dict, list[dict]]:
    sessions = [f"D{i:06d}" for i in range(176)] + ["20260916", "20260917"]
    upstream, plans, rows = [], [], []
    for index, day in enumerate(sessions):
        state_id = f"CONTEXT182_{day}"
        if index < audit.EXPECTED_REUSED:
            value = plan(state_id, day, ["WEEKLY"])
            upstream.append(value)
            source, source_row = "REUSED", index
        else:
            value = plan(state_id, day, ["DAILY"])
            source, source_row = "NEW", None
        plans.append(value)
        terminal = day in {"20260916", "20260917"}
        rows.append({
            "date": day, "state_id": state_id, "source": source,
            "source_row": source_row, "used_for_scoring": not terminal,
            "terminal_unused_for_scoring": terminal,
        })
    schedule = {
        "schema": audit.SCHEDULE_SCHEMA, "count": 178,
        "reused_source": {"path": "states.jsonl", "bytes": 1, "sha256": "a" * 64},
        "rows": rows,
    }
    plans_doc = {"schema": audit.PLAN_SCHEMA, "count": 178, "plans": plans}
    return sessions, schedule, plans_doc, upstream


def test_schedule_closes_178_42_136_and_terminal_two() -> None:
    sessions, schedule, plans_doc, upstream = schedule_fixture()
    plans, reused, new = audit.validate_schedule(schedule, plans_doc, upstream, upstream, sessions, schedule["reused_source"])
    assert len(plans) == 178
    assert len(reused) == 42
    assert len(new) == 136
    assert {schedule["rows"][-2]["date"], schedule["rows"][-1]["date"]} == {"20260916", "20260917"}


def test_schedule_rejects_reused_mutation_and_skipped_fit() -> None:
    sessions, schedule, plans_doc, upstream = schedule_fixture()
    plans_doc["plans"][0] = dict(plans_doc["plans"][0], cal_end="MUTATED")
    with pytest.raises(audit.AuditError, match="reused plan exact"):
        audit.validate_schedule(schedule, plans_doc, upstream, upstream, sessions, schedule["reused_source"])
    sessions, schedule, plans_doc, upstream = schedule_fixture()
    schedule["rows"][42]["source"] = "REUSED"
    schedule["rows"][42]["source_row"] = 0
    with pytest.raises(audit.AuditError):
        audit.validate_schedule(schedule, plans_doc, upstream, upstream, sessions, schedule["reused_source"])


def test_schedule_source_row_uses_states_order_not_plan_order() -> None:
    sessions, schedule, plans_doc, upstream = schedule_fixture()
    states_in_different_order = [upstream[1], upstream[0], *upstream[2:]]
    with pytest.raises(audit.AuditError, match="reused source row exact"):
        audit.validate_schedule(
            schedule, plans_doc, upstream, states_in_different_order,
            sessions, schedule["reused_source"],
        )


def test_saved_state_versions_must_be_identical() -> None:
    states = {
        "A": {"model": {"sklearn_version": "1.8.0"}},
        "B": {"model": {"sklearn_version": "1.9.0"}},
    }
    with pytest.raises(audit.AuditError, match="version coherence"):
        audit.validate_state_versions(states)


def test_control_clock_uses_latest_cadence_state() -> None:
    sessions = ["20260102", "20260105", "20260106"]
    plans = {
        "A": {"state_id": "A", "creation_date": "20260102", "frequencies": ["MONTHLY", "WEEKLY"]},
        "B": {"state_id": "B", "creation_date": "20260106", "frequencies": ["WEEKLY"]},
    }
    clock = audit.control_model_clock(sessions, plans)
    assert clock["FROZEN_CONTEXT182"] == {day: "FROZEN_CONTEXT182_H1" for day in sessions}
    assert clock["MONTHLY_RAW"] == {day: "A" for day in sessions}
    assert clock["WEEKLY_RAW"] == {"20260102": "A", "20260105": "A", "20260106": "B"}


def bridge_rows() -> tuple[list[dict], dict]:
    candidates, rows = [], []
    for ticker in audit.TICKERS:
        ids = []
        for right in ("CALL", "PUT"):
            candidate_id = f"{ticker}:20260629:20260702:{right}"
            ids.append(candidate_id)
            candidates.append({"candidate_id": candidate_id, "entry_date": "20260629", "exit_date": "20260701"})
        rows.append({"ticker": ticker, "entry_date": "20260629", "exit_date": "20260701", "status": "CANDIDATES_BUILT", "candidate_ids": ids})
        rows.append({"ticker": ticker, "entry_date": "20260630", "exit_date": "20260702", "status": "NO_SERIES", "candidate_ids": []})
    return candidates, {"rows": rows}


def test_bridge_exact_six_and_three_no_series() -> None:
    candidates, coverage = bridge_rows()
    audit.validate_bridge(candidates, coverage)
    coverage["rows"][1]["status"] = "CANDIDATES_BUILT"
    with pytest.raises(audit.AuditError, match="June30"):
        audit.validate_bridge(candidates, coverage)


def test_journal_only_new_states_and_persistent_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "EXPECTED_JOURNAL_ROWS", 2)
    monkeypatch.setattr(audit, "EXPECTED_ALL_CANDIDATES", 1)
    state_id = "CONTEXT182_20260105"
    state = {"state_id": state_id, "creation_date": "20260105", "asof": "2026-01-05T00:00:00-05:00"}
    state_file = tmp_path / f"fit_state_{state_id}.json"
    state_file.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(state_file.read_bytes()).hexdigest()
    gate = {"available_ram_bytes": 2_000_000_000, "free_commit_bytes": 2_000_000_001}
    common = {"state_id": state_id, "creation_date": "20260105", "asof": state["asof"], "gate": gate}
    rows = [
        {"event": "FIT_START", "utc": "2026-11-01T10:00:00+00:00", "state_sha256": None, **common},
        {"event": "FIT_COMPLETE", "utc": "2026-11-01T10:01:00+00:00", "state_sha256": digest, **common},
    ]
    result = audit.validate_journal(rows, {state_id}, {state_id: state_file}, {state_id: state})
    assert result == {"rows": 2, "fits": 1}
    rows[0]["state_id"] = "CONTEXT182_REUSED"
    with pytest.raises(audit.AuditError, match="new state only"):
        audit.validate_journal(rows, {state_id}, {state_id: state_file}, {state_id: state})


def test_binary_saved_weight_probability_is_sigmoid_without_fit() -> None:
    v4 = audit.import_pinned(audit.V4, audit.V4_SHA256, "daily_test_v4_binary")
    model = {
        "penalty": "l2", "constructor_penalty_omitted": True, "l1_ratio": 0.0,
        "C": 1.0, "solver": "lbfgs", "max_iter": 2000, "random_state": 0,
        "warm_start": False, "class_weight": None, "classes_full": [0, 1, 2, 3, 4],
        "classes_present": [1, 4], "sklearn_version": "1.8.0", "fit_warnings": [],
        "coefficient": [[2.0]], "intercept": [0.0], "type": "LogisticRegression",
        "fit_scope": "TRAIN_ONLY",
    }
    probabilities = v4.restored_probabilities_adaptation(np.asarray([[0.0], [1.0]]), model)
    assert probabilities[0].tolist() == pytest.approx([0.0, 0.5, 0.0, 0.0, 0.5])
    positive = 1.0 / (1.0 + np.exp(-2.0))
    assert probabilities[1].tolist() == pytest.approx([0.0, 1.0 - positive, 0.0, 0.0, positive])


def test_split_has_63_cal_gap2_strict_maturity_and_future_invariance() -> None:
    v4 = audit.import_pinned(audit.V4, audit.V4_SHA256, "daily_test_v4_split")
    calendar = [(date(2025, 1, 1) + timedelta(days=index)).strftime("%Y%m%d") for index in range(70)]
    creation = calendar[69]
    cal_start = calendar[4]
    rows = [
        {"candidate_id": "TRAIN", "entry_date": calendar[0], "label_available_at": "2025-01-04T10:35:00-05:00"},
        {"candidate_id": "PURGED_STRICT", "entry_date": calendar[1], "label_available_at": "2025-01-05T00:00:00-05:00"},
        {"candidate_id": "CAL", "entry_date": cal_start, "label_available_at": "2025-03-10T10:35:00-05:00"},
        {"candidate_id": "CAL_FUTURE", "entry_date": calendar[5], "label_available_at": "2025-03-11T00:00:00-05:00"},
        {"candidate_id": "AFTER", "entry_date": "20260101", "label_available_at": "2099-01-01T00:00:00-05:00"},
    ]
    split = v4.derive_split(creation, calendar, rows)
    assert len(split["cal_sessions"]) == 63
    assert split["cal_sessions"] == calendar[4:67]
    assert calendar[67:69] == ["20250309", "20250310"]
    assert split["train_ids"] == ["TRAIN"]
    assert set(split["purged_ids"]) == {"PURGED_STRICT", "CAL_FUTURE"}
    assert split["cal_ids"] == ["CAL"]
    rows[-1]["label_available_at"] = "2100-01-01T00:00:00-05:00"
    assert v4.derive_split(creation, calendar, rows) == split


def test_top1_is_positive_unique_and_ties_abstain() -> None:
    rows = [
        {"candidate_id": "A", "entry_date": "20260102", "ticker": "SPY", "ev_adverse": 1.0},
        {"candidate_id": "B", "entry_date": "20260102", "ticker": "SPY", "ev_adverse": 0.5},
        {"candidate_id": "C", "entry_date": "20260102", "ticker": "QQQ", "ev_adverse": 2.0},
        {"candidate_id": "D", "entry_date": "20260102", "ticker": "QQQ", "ev_adverse": 2.0},
        {"candidate_id": "E", "entry_date": "20260102", "ticker": "SPXW", "ev_adverse": -0.1},
    ]
    assert audit.winner_ids(rows) == {"A"}


def replay_candidate() -> dict:
    return {
        "candidate_id": "SPY:20260102:X:CALL", "ticker": "SPY", "right": "CALL",
        "entry_date": "20260102", "exit_date": "20260106", "decision_ask": 1.0,
        "entry_ask": 1.0, "exit_bid": 1.5, "status": "OBSERVED_EXIT",
        "entry_debit_base": 102.30, "entry_debit_adverse": 103.30,
        "net_base": 45.40, "net_adverse": 43.40,
        "_ev_base": 4.0, "_ev_adverse": 3.0,
    }


def test_real_helper_replay_is_continuous_across_intermediate_session() -> None:
    helper = audit.import_pinned(audit.HELPER, audit.HELPER_SHA256, "daily_test_replay_helper")
    sessions = ["20260102", "20260105", "20260106"]
    coverage = [
        {"ticker": ticker, "entry_date": day, "status": "NO_SERIES", "reason": "NO_SERIES"}
        for day in sessions for ticker in audit.TICKERS
    ]
    books = helper.replay_risk([replay_candidate()], coverage, sessions, "20260105")
    for cost in audit.COSTS:
        events = books[cost]
        assert any(row["event"] == "ENTRY" and row["date"] == "20260102" for row in events)
        assert any(row["event"] == "WAIT" and row["date"] == "20260105" and row["reason"] == "OPEN_POSITION" for row in events)
        assert any(row["event"] == "EXIT" and row["date"] == "20260106" for row in events)


def test_compare_ledgers_keeps_exact_quantities() -> None:
    rebuilt = [{"event": "NO_FILL", "date": "20260102", "ticker": "SPY", "cost": "adverse", "quantity": 3}]
    actual = [{**rebuilt[0], "policy": "DAILY_RAW", "model_id": "CONTEXT182_20260102"}]
    audit.compare_ledgers(actual, rebuilt, "exact")
    actual[0]["quantity"] = 3.0000001
    with pytest.raises(audit.AuditError, match="int"):
        audit.compare_ledgers(actual, rebuilt, "quantity drift")


def test_output_allowlist_is_16_core_plus_136_states() -> None:
    assert len(audit.expected_output_names()) == 16
    state_names = {f"fit_state_CONTEXT182_D{i:06d}.json" for i in range(136)}
    assert len(audit.expected_output_names() | state_names) == 152


def test_plain_file_guard_rejects_path_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.json"
    dump_json(outside, {"outside": True})
    with pytest.raises(audit.AuditError, match="outside roots"):
        audit.plain(outside, (root,))


def test_auditor_source_never_imports_producers_or_calls_fit() -> None:
    tree = ast.parse(Path(audit.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any("evaluate_weekly_daily_adaptation" in name for name in imported)
    assert not any("evaluate_weekly_context_adaptation" in name for name in imported)
    assert "sklearn" not in imported
    calls = [node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
    assert "fit" not in calls


def test_default_cli_is_readiness_only(capsys: pytest.CaptureFixture[str]) -> None:
    assert audit.main([]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "READY_NOT_EXECUTED"


def test_final_rehash_occurs_after_audit_manifest_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    watched = tmp_path / "watched.json"
    dump_json(watched, {"stable": True})
    producer_manifest = tmp_path / "manifest.json"
    producer_exit = tmp_path / "exit.json"
    dump_json(producer_manifest, {"synthetic": "producer manifest"})
    dump_json(producer_exit, {"exit_code": 0})
    output = tmp_path / "audit_output"
    monkeypatch.setattr(audit, "OUTPUT", output)
    monkeypatch.setattr(
        audit, "admit",
        lambda *_args: ({}, {str(watched): audit.pin(watched)}),
    )
    monkeypatch.setattr(audit, "import_pinned", lambda *_args: object())
    monkeypatch.setattr(audit, "numeric_audit", lambda *_args: {"ok": True})
    original_write = audit.write_json

    def mutating_write(path: Path, value: object) -> None:
        original_write(path, value)
        if path.name == "manifest.json":
            dump_json(watched, {"stable": False})

    monkeypatch.setattr(audit, "write_json", mutating_write)
    with pytest.raises(audit.AuditError, match="changed input/output"):
        audit.run(tmp_path, "a" * 64, producer_exit, "b" * 64, "c" * 64, "d" * 64, output)


def test_upstream_semantic_binding_and_flags_are_explicit_constants() -> None:
    assert audit.UPSTREAM_MANIFEST_FLAGS["models_fit"] is True
    assert audit.UPSTREAM_MANIFEST_FLAGS["promotion_approved"] is False
    assert audit.UPSTREAM_AUDIT_FLAGS["saved_weights_used"] is True
    assert audit.UPSTREAM_AUDIT_FLAGS["fit_performed"] is False
    assert audit.UPSTREAM_MANIFEST_BYTES == 17599


def test_upstream_nonzero_exit_is_rejected() -> None:
    manifest = {
        "schema": "weekly_context_adaptation_walkforward_v1",
        "status": "PASS_SEEN_DEVELOPMENT_GIVEN_BRIDGE_AND_FROZEN_AUTHORITIES",
        "flags": audit.UPSTREAM_MANIFEST_FLAGS,
    }
    upstream_audit = {
        "schema": "weekly_context_adaptation_audit_v1",
        "status": "PASS_INDEPENDENT_NUMERIC_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT",
        "flags": audit.UPSTREAM_AUDIT_FLAGS,
        "inputs": {"producer_manifest": {
            "path": str(audit.UPSTREAM_MANIFEST),
            "bytes": audit.UPSTREAM_MANIFEST_BYTES,
            "sha256": audit.UPSTREAM_MANIFEST_SHA256,
        }},
    }
    with pytest.raises(audit.AuditError, match="upstream audit exit"):
        audit.validate_upstream_semantics(manifest, upstream_audit, {"exit_code": 1})


def test_numeric_audit_integrates_scores_books_metrics_and_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit, "EXPECTED_SESSIONS", 1)
    monkeypatch.setattr(audit, "EXPECTED_REUSED", 0)
    monkeypatch.setattr(audit, "EXPECTED_NEW", 1)
    monkeypatch.setattr(audit, "EXPECTED_CANDIDATES", 1)
    monkeypatch.setattr(audit, "EXPECTED_SCORES", 4)
    monkeypatch.setattr(audit, "EXPECTED_JOURNAL_ROWS", 2)
    monkeypatch.setattr(audit, "EXPECTED_ALL_CANDIDATES", 1)
    monkeypatch.setattr(audit, "validate_bridge", lambda *_args: None)
    monkeypatch.setattr(audit, "common_calendar", lambda *_args: (["20260102"], ["20260102"]))

    producer = tmp_path / "producer"
    producer.mkdir()
    upstream = tmp_path / "h2_context_adaptation_01"
    state_id = "CONTEXT182_20260102"
    candidate_id = "SPY:20260102:X:CALL"
    fit_plan = plan(state_id, "20260102", ["DAILY"])
    state = {
        "state_id": state_id, "creation_date": "20260102", "asof": fit_plan["asof"],
        "prior_support": [1, 0, 0, 0, 0], "prior": [1.0, 0.0, 0.0, 0.0, 0.0],
        "model": {"sklearn_version": "1.8.0"},
    }
    candidate = {
        "candidate_id": candidate_id, "ticker": "SPY", "right": "CALL",
        "entry_date": "20260102", "exit_date": "20260106", "scenario": 0,
        "payoff_is_lower_bound": False,
    }
    score_core = {
        "candidate_id": candidate_id, "entry_date": "20260102", "ticker": "SPY",
        "right": "CALL", "scenario": 0, "payoff_is_lower_bound": False,
        "is_bridge": True, "p_model": [1.0, 0.0, 0.0, 0.0, 0.0],
        "p_cal": [1.0, 0.0, 0.0, 0.0, 0.0], "ev_base": 1.0,
        "ev_adverse": 1.0,
    }
    control_scores = [
        {**score_core, "policy": "FROZEN_CONTEXT182", "model_id": "FROZEN_CONTEXT182_H1"},
        {**score_core, "policy": "MONTHLY_RAW", "model_id": state_id},
        {**score_core, "policy": "WEEKLY_RAW", "model_id": state_id},
    ]
    daily_score = {**score_core, "policy": "DAILY_RAW", "model_id": state_id}
    scores = [*control_scores, daily_score]

    paths = {
        "h1_candidates": tmp_path / "h2_dataset_v2_01" / "candidates.jsonl",
        "q3_candidates": tmp_path / "h2_dataset_v2_extension_2026q3_partial_01" / "candidates.jsonl",
        "bridge_candidates": tmp_path / "h2_boundary_bridge_01" / "candidates.jsonl",
        "h1_context": tmp_path / "h2_context_1030_01" / "context.jsonl",
        "q3_context": tmp_path / "h2_context_q3_1030_01" / "context.jsonl",
        "h1_coverage": tmp_path / "h2_dataset_v2_01" / "coverage.json",
        "q3_coverage": tmp_path / "h2_dataset_v2_extension_2026q3_partial_01" / "coverage.json",
        "bridge_coverage": tmp_path / "h2_boundary_bridge_01" / "coverage_overlay.json",
        "plans": upstream / "fit_plans.json", "states": upstream / "states.jsonl",
        "scores": upstream / "candidate_scores.jsonl", "summary": upstream / "summary.json",
        "frozen_transform": tmp_path / "h2_context_model_comparison_01" / "context182_transform.json",
        "frozen_model": tmp_path / "h2_context_model_comparison_01" / "context182_model.json",
        "frozen_calibration": tmp_path / "h2_context_model_comparison_01" / "context182_calibration.json",
        "ev_model": tmp_path / "h2_ev_v2_01" / "model.json",
        "means": tmp_path / "h2_ev_v2_01" / "conditional_means.json",
    }
    dump_jsonl(paths["h1_candidates"], [])
    dump_jsonl(paths["q3_candidates"], [])
    dump_jsonl(paths["bridge_candidates"], [candidate])
    dump_jsonl(paths["h1_context"], [{"ticker": "SPY", "date": "20260102"}])
    dump_jsonl(paths["q3_context"], [])
    coverage_rows = [
        {"ticker": ticker, "entry_date": "20260102", "status": "NO_SERIES", "reason": "NO_SERIES"}
        for ticker in audit.TICKERS
    ]
    dump_json(paths["h1_coverage"], {"calendar": [], "rows": coverage_rows})
    dump_json(paths["q3_coverage"], {"calendar": [], "rows": []})
    dump_json(paths["bridge_coverage"], {"rows": []})
    dump_json(paths["plans"], {"plans": []})
    dump_jsonl(paths["states"], [])
    dump_jsonl(paths["scores"], control_scores)
    dump_json(paths["frozen_transform"], {"feature_order": ["x"]})
    dump_json(paths["frozen_model"], {"sklearn_version": "1.8.0"})
    dump_json(paths["frozen_calibration"], {"selected_alpha": 0.0})
    dump_json(paths["ev_model"], {"train_prior": [1.0, 0.0, 0.0, 0.0, 0.0]})
    dump_json(paths["means"], {"synthetic": True})
    synthetic_upstream_manifest = tmp_path / "adaptation_authority_manifest.json"
    dump_json(synthetic_upstream_manifest, {
        "consumed_payloads": {
            str(paths[key]): audit.pin(paths[key])
            for key in (
                "frozen_transform", "frozen_model", "frozen_calibration",
                "ev_model", "means",
            )
        }
    })
    monkeypatch.setattr(audit, "UPSTREAM_MANIFEST", synthetic_upstream_manifest)

    months = {f"2026{month:02d}": 0.0 for month in range(1, 10)}
    book = {"net_usd": 0.0, "details": {"monthly_net_including_zeros": months}}
    probability = {"n": 1}
    policy_summary = {
        "economics": {"base": book, "adverse": book},
        "probability_ev": {
            "all": probability, "selected": probability,
            "all_observed_only": probability, "selected_observed_only": probability,
        },
        "selected_ids": [], "filled_ids": [], "adverse_net_minus_frozen": 0.0,
    }
    dump_json(paths["summary"], {"policies": {policy: policy_summary for policy in audit.CONTROL_POLICIES}})
    for policy in audit.CONTROL_POLICIES:
        for cost in audit.COSTS:
            path = upstream / f"ledger_{policy.lower()}_{cost}.jsonl"
            dump_jsonl(path, [])
            paths[f"ledger_{policy}_{cost}"] = path

    dump_json(producer / "daily_fit_plans.json", {
        "schema": audit.PLAN_SCHEMA, "count": 1, "plans": [fit_plan],
    })
    dump_json(producer / "daily_schedule.json", {
        "schema": audit.SCHEDULE_SCHEMA, "count": 1,
        "reused_source": audit.pin(paths["states"]),
        "rows": [{
            "date": "20260102", "state_id": state_id, "source": "NEW",
            "source_row": None, "used_for_scoring": True,
            "terminal_unused_for_scoring": False,
        }],
    })
    dump_jsonl(producer / "daily_states_new.jsonl", [state])
    state_file = producer / f"fit_state_{state_id}.json"
    dump_json(state_file, state)
    gate = {"available_ram_bytes": 2_000_000_000, "free_commit_bytes": 2_000_000_000}
    journal_common = {"state_id": state_id, "creation_date": "20260102", "asof": state["asof"], "gate": gate}
    dump_jsonl(producer / "fit_journal.jsonl", [
        {"event": "FIT_START", "utc": "2026-11-01T10:00:00+00:00", "state_sha256": None, **journal_common},
        {"event": "FIT_COMPLETE", "utc": "2026-11-01T10:01:00+00:00", "state_sha256": audit.sha256_file(state_file), **journal_common},
    ])
    dump_jsonl(producer / "candidate_scores.jsonl", scores)
    dump_jsonl(producer / "state_diagnostics.jsonl", [{
        "date": "20260102", "state_id": state_id, "source": "NEW",
        "train_n": 1, "cal_n": 1, "purged_n": 1,
        "class_support": state["prior_support"], "prior": state["prior"],
        "alpha": 0.0, "score_count": 1, "terminal_unused_for_scoring": False,
    }])
    dump_jsonl(producer / "daily_vs_weekly.jsonl", [{
        "candidate_id": candidate_id, "entry_date": "20260102", "ticker": "SPY",
        "right": "CALL", "daily_model_id": state_id,
        "weekly_model_id": state_id, "p_model_diff": [0.0] * 5,
        "p_cal_diff": [0.0] * 5, "ev_base_diff": 0.0, "ev_adverse_diff": 0.0,
        "daily_top1": True, "weekly_top1": True, "top1_changed": False,
    }])
    for policy in audit.POLICIES:
        for cost in audit.COSTS:
            dump_jsonl(producer / f"ledger_{policy.lower()}_{cost}.jsonl", [])
    dump_json(producer / "summary.json", {
        "schema": audit.SUMMARY_SCHEMA, "status": audit.PRODUCER_STATUS,
        "scope": {"sessions": 1, "candidate_universe": 1, "policies": list(audit.POLICIES), "scores": 4, "books": 8},
        "states": {"daily": 1, "reused": 0, "new": 1, "terminal_unused": 2},
        "policies": {policy: policy_summary for policy in audit.POLICIES},
        "comparisons": {
            baseline: {cost: {"total_net_usd": 0.0, "monthly_net_usd": months} for cost in audit.COSTS}
            for baseline in ("WEEKLY_RAW", "MONTHLY_RAW")
        },
        "criterion": {
            "months": [f"2026{month:02d}" for month in range(1, 9)],
            "necessary": "DAILY_RAW adverse exit-date net strictly positive in every complete month",
            "daily_passes_8_of_8": False, "selected_policy": None,
            "promotion_approved": False,
        },
        "diagnostics": {"state_rows": 1, "candidate_rows": 1, "top1_changed": 0},
        "flags": audit.PRODUCER_FLAGS,
    })

    inputs = {str(path): {} for path in paths.values()}
    fake_helper = SimpleNamespace(
        context182=lambda *_args: [0.0] * 182,
        replay_risk=lambda *_args: {"base": [], "adverse": []},
        selected_ids=lambda _rows: set(),
    )
    fake_v4 = SimpleNamespace(
        validate_saved_state=lambda *_args: {"alpha": 0.0},
        score_state=lambda _helper, _state, rows: [
            {"candidate_id": row["candidate_id"], "p_model": [1.0, 0.0, 0.0, 0.0, 0.0],
             "p_cal": [1.0, 0.0, 0.0, 0.0, 0.0], "ev_base": 1.0, "ev_adverse": 1.0}
            for row in rows
        ],
        extended_book_metrics=lambda *_args: book,
        combined_probability_ev=lambda *_args: probability,
    )
    monkeypatch.setattr(audit, "control_model_clock", lambda *_args: {
        "FROZEN_CONTEXT182": {"20260102": "FROZEN_CONTEXT182_H1"},
        "MONTHLY_RAW": {"20260102": state_id},
        "WEEKLY_RAW": {"20260102": state_id},
    })
    result = audit.numeric_audit(producer, {"inputs": inputs}, fake_v4, fake_helper)
    assert result["scores"] == 4
    assert result["books"] == 8
    assert result["journal"] == {"rows": 2, "fits": 1}
    corrupted = [dict(row) for row in control_scores]
    corrupted[0]["ev_adverse"] = 2.0
    producer_scores = [*corrupted, daily_score]
    dump_jsonl(paths["scores"], corrupted)
    dump_jsonl(producer / "candidate_scores.jsonl", producer_scores)
    with pytest.raises(audit.AuditError, match="score EV adverse"):
        audit.numeric_audit(producer, {"inputs": inputs}, fake_v4, fake_helper)

