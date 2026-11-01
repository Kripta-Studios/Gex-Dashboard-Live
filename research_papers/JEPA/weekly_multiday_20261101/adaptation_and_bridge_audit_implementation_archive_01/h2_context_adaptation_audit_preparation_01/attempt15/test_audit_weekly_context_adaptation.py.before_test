from __future__ import annotations

import copy
from datetime import date, timedelta
import importlib.util
import inspect
import json
from pathlib import Path

import numpy as np
import pytest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "adaptation_audit", HERE / "audit_weekly_context_adaptation.py"
)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
HELPER = audit.import_helper()


def evaluation_sessions() -> list[str]:
    holidays = {
        "20260119", "20260216", "20260403", "20260525",
        "20260619", "20260703", "20260907",
    }
    day, final, output = date(2026, 1, 2), date(2026, 9, 17), []
    while day <= final:
        value = day.strftime("%Y%m%d")
        if day.weekday() < 5 and value not in holidays:
            output.append(value)
        day += timedelta(days=1)
    return output


def calendar_sessions(start: date, count: int) -> list[str]:
    output = []
    while len(output) < count:
        if start.weekday() < 5:
            output.append(start.strftime("%Y%m%d"))
        start += timedelta(days=1)
    return output


def row(candidate_id: str, day: str, label: int, available: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "ticker": "SPY",
        "right": "CALL",
        "entry_date": day,
        "exit_date": day,
        "label_available_at": available,
        "scenario": label,
        "decision_ask": 1.0,
        "net_base": float(label * 10 - 15),
        "net_adverse": float(label * 10 - 17),
        "_x_context": [float(label)] + [0.0] * 181,
    }


def transform(train: np.ndarray, names: list[str]) -> dict:
    rebuilt = HELPER.independently_recompute_transform(train)
    indices = rebuilt["indicator_indices"]
    return {
        "feature_order": names,
        "fit_scope": "TRAIN_ONLY",
        "imputer": {
            "strategy": "median",
            "add_indicator": True,
            "keep_empty_features": True,
        },
        "medians": rebuilt["medians"].tolist(),
        "missing_indicator_source_indices": indices,
        "missing_indicator_order": [f"{names[index]}__missing" for index in indices],
        "scaler_mean": rebuilt["mean"].tolist(),
        "scaler_scale": rebuilt["scale"].tolist(),
    }


def saved_model(width: int) -> dict:
    return {
        "type": "LogisticRegression",
        "fit_scope": "TRAIN_ONLY",
        "penalty": "l2",
        "constructor_penalty_omitted": True,
        "l1_ratio": 0.0,
        "C": 1.0,
        "solver": "lbfgs",
        "max_iter": 2000,
        "random_state": 0,
        "warm_start": False,
        "class_weight": None,
        "classes_full": list(range(5)),
        "classes_present": [0, 1],
        "sklearn_version": "fixture",
        "fit_warnings": [],
        "coefficient": [[0.0] * width],
        "intercept": [0.0],
    }


def test_calendar_schedule_has_42_physical_states_and_shared_overlaps() -> None:
    sessions = evaluation_sessions()
    schedule = audit.creation_dates(sessions)
    states = [{"state_id": f"s-{day}"} for day in schedule["physical"]]
    plans = []
    for day in schedule["physical"]:
        cadences = []
        if day in schedule["monthly"]:
            cadences.append("MONTHLY")
        if day in schedule["weekly"]:
            cadences.append("WEEKLY")
        plans.append({"creation_date": day, "state_id": f"s-{day}", "frequencies": cadences})
    result = audit.validate_fit_plan_schedule(sessions, plans, states)
    assert result == {
        "monthly_references": 9,
        "weekly_references": 38,
        "physical_states": 42,
        "coincident_dates": 5,
    }
    broken = copy.deepcopy(plans)
    overlap = next(item for item in broken if len(item["frequencies"]) == 2)
    overlap["frequencies"].remove("WEEKLY")
    with pytest.raises(audit.AdaptationAuditError, match="plan cadence reference"):
        audit.validate_fit_plan_schedule(sessions, broken, states)
    reused = copy.deepcopy(plans)
    reused[1]["state_id"] = reused[0]["state_id"]
    with pytest.raises(audit.AdaptationAuditError, match="plan/state bijection"):
        audit.validate_fit_plan_schedule(sessions, reused, states)


def test_timeline_enforces_raw_activation_and_guarded_conservation() -> None:
    sessions = evaluation_sessions()
    schedule = audit.creation_dates(sessions)
    plans = []
    for day in schedule["physical"]:
        frequencies = [
            name.upper() for name in ("monthly", "weekly") if day in schedule[name]
        ]
        plans.append({
            "creation_date": day,
            "state_id": f"CONTEXT182_{day}",
            "frequencies": frequencies,
        })
    proposals = []
    for cadence in ("MONTHLY", "WEEKLY"):
        for day in schedule[cadence.lower()]:
            proposals.append({
                "proposal_id": f"{cadence}_{day}", "cadence": cadence,
                "created_date": day, "challenger_id": f"CONTEXT182_{day}",
                "incumbent_snapshot_id": "FROZEN_CONTEXT182_H1",
                "gate_sessions": sessions[sessions.index(day):sessions.index(day) + 21],
                "maturity_date": None, "status": "PENDING_BEYOND_DECISION_CUTOFF",
                "resolved_at": None, "effective_at": None, "comparison": None,
            })
    timeline, active = [], {
        "FROZEN_CONTEXT182": "FROZEN_CONTEXT182_H1",
        "MONTHLY_RAW": "NO_ACTIVE_MODEL", "WEEKLY_RAW": "NO_ACTIVE_MODEL",
        "MONTHLY_GUARDED": "FROZEN_CONTEXT182_H1",
        "WEEKLY_GUARDED": "FROZEN_CONTEXT182_H1",
    }
    plan_index = {value["creation_date"]: value for value in plans}
    for day in sessions:
        for policy in audit.POLICIES:
            before, after, created = active[policy], active[policy], None
            if policy.endswith("_RAW"):
                cadence = policy.removesuffix("_RAW")
                plan = plan_index.get(day)
                if plan and cadence in plan["frequencies"]:
                    after = plan["state_id"]
            elif policy.endswith("_GUARDED"):
                cadence = policy.removesuffix("_GUARDED")
                if (cadence, day) in {(value["cadence"], value["created_date"]) for value in proposals}:
                    created = f"{cadence}_{day}"
            timeline.append({
                "date": day, "policy": policy,
                "phase_order": "RESOLVE_CREATE_ACTIVATE_SCORE_EXECUTE",
                "active_model_before": before, "active_model_after": after,
                "created_proposal_id": created, "resolved_proposal_ids": [],
            })
            active[policy] = after
    result = audit.validate_policy_timeline(sessions, plans, proposals, timeline)
    assert result["rows"] == 890 and result["proposals"] == 47
    broken = copy.deepcopy(timeline)
    target = next(value for value in broken if value["policy"] == "WEEKLY_RAW")
    target["active_model_after"] = "FUTURE_MODEL"
    with pytest.raises(audit.AdaptationAuditError, match="timeline transition"):
        audit.validate_policy_timeline(sessions, plans, proposals, broken)


def test_split_uses_label_maturity_and_purges_boundaries() -> None:
    calendar = calendar_sessions(date(2025, 9, 1), 75)
    creation = calendar[70]
    cal_start = calendar[5]
    cal_day = calendar[10]
    values = [
        row("train", calendar[2], 0, f"{cal_start[:4]}-{cal_start[4:6]}-{cal_start[6:]}T00:00:00-04:00"),
        row("purged-train", calendar[3], 1, f"{cal_start[:4]}-{cal_start[4:6]}-{cal_start[6:]}T00:00:00-04:00"),
        row("cal", cal_day, 0, "2025-09-20T10:35:00-04:00"),
        row("purged-cal", calendar[67], 1, audit.midnight(creation).isoformat()),
    ]
    # Strictly before CAL_start: move the first row one second earlier.
    values[0]["label_available_at"] = "2025-09-07T23:59:59-04:00"
    plan = audit.derive_split(creation, calendar, values)
    assert plan["train_ids"] == ["train"]
    assert plan["cal_ids"] == ["cal"]
    assert plan["purged_ids"] == ["purged-cal", "purged-train"]
    assert len(plan["cal_sessions"]) == 63


def test_saved_state_rebuilds_train_transform_prior_means_and_cal_alpha() -> None:
    names = [f"f{index}" for index in range(182)]
    history = calendar_sessions(date(2025, 10, 1), 65)
    full_calendar = [*history, "20260102"]
    cal_sessions = history[:63]
    train_rows = [
        row("t0a", "20240102", 0, "2024-01-04T10:35:00-05:00"),
        row("t0b", "20240103", 0, "2024-01-05T10:35:00-05:00"),
        row("t1a", "20240104", 1, "2024-01-08T10:35:00-05:00"),
        row("t1b", "20240105", 1, "2024-01-09T10:35:00-05:00"),
    ]
    cal_rows = [
        row("c0", cal_sessions[-4], 0, "2025-12-23T10:35:00-05:00"),
        row("c1", cal_sessions[-3], 1, "2025-12-24T10:35:00-05:00"),
    ]
    rows = train_rows + cal_rows
    matrix = np.asarray([value["_x_context"] for value in train_rows], dtype=float)
    plan = {
        "state_id": "s0",
        "creation_date": "20260102",
        "asof": audit.midnight("20260102").isoformat(),
        "frequencies": ["MONTHLY", "WEEKLY"],
        "train_ids": [value["candidate_id"] for value in train_rows],
        "cal_ids": [value["candidate_id"] for value in cal_rows],
        "purged_train_ids": [],
        "cal_sessions": cal_sessions,
        "cal_start": cal_sessions[0],
        "cal_end": cal_sessions[-1],
        "train_label_available_max": "2024-01-09T10:35:00-05:00",
        "cal_label_available_max": "2025-12-24T10:35:00-05:00",
    }
    probabilities = np.full((2, 2), 0.5)
    prior = [0.5, 0.5, 0.0, 0.0, 0.0]
    grid = []
    labels = np.asarray([0, 1])
    for step in range(11):
        alpha = step / 10
        full = np.zeros((2, 5))
        full[:, :2] = probabilities
        mixed = (1 - alpha) * full + alpha * np.asarray(prior)
        grid.append({"alpha": alpha, "log_loss": HELPER.log_loss(labels, mixed)})
    state = {
        "state_id": "s0",
        "feature_order": names,
        **copy.deepcopy(plan),
        "transform": transform(matrix, names),
        "model": saved_model(182),
        "prior": prior,
        "prior_support": [2, 2, 0, 0, 0],
        "conditional_means": audit.conditional_means(train_rows),
        "calibration": {
            "formula": "(1-alpha)*p_model+alpha*p_train_prior",
            "selected_alpha": 0.0,
            "scores": grid,
        },
    }
    result = audit.validate_saved_state(
        HELPER, state, plan, {value["candidate_id"]: value for value in rows},
        full_calendar,
    )
    assert result["alpha"] == 0.0
    changed = copy.deepcopy(state)
    changed["conditional_means"]["cells"]["base"]["SPY:CALL"]["0"]["mean_y"] += 0.01
    with pytest.raises(audit.AdaptationAuditError, match="conditional means"):
        audit.validate_saved_state(
            HELPER, changed, plan, {value["candidate_id"]: value for value in rows},
            full_calendar,
        )
    wrong_plan, wrong_state = copy.deepcopy(plan), copy.deepcopy(state)
    wrong_window = history[1:64]
    for value in (wrong_plan, wrong_state):
        value["cal_sessions"] = wrong_window
        value["cal_start"], value["cal_end"] = wrong_window[0], wrong_window[-1]
    with pytest.raises(audit.AdaptationAuditError, match="derived CAL window"):
        audit.validate_saved_state(
            HELPER, wrong_state, wrong_plan,
            {value["candidate_id"]: value for value in rows}, full_calendar,
        )


def test_binary_saved_lr_uses_sklearn_one_row_sigmoid_semantics() -> None:
    model = saved_model(1)
    model["coefficient"] = [[2.0]]
    model["intercept"] = [-0.5]
    values = np.asarray([[-1.0], [0.0], [1.0]])
    actual = audit.restored_probabilities_adaptation(values, model)
    decision = values[:, 0] * 2.0 - 0.5
    positive = 1.0 / (1.0 + np.exp(-decision))
    assert np.allclose(actual[:, 0], 1.0 - positive, atol=1e-15)
    assert np.allclose(actual[:, 1], positive, atol=1e-15)
    assert np.array_equal(actual[:, 2:], np.zeros((3, 3)))
    broken = copy.deepcopy(model)
    broken["warm_start"] = True
    with pytest.raises(audit.AdaptationAuditError, match="model recipe"):
        audit.restored_probabilities_adaptation(values, broken)
    broken = copy.deepcopy(model)
    broken["constructor_penalty_omitted"] = False
    with pytest.raises(audit.AdaptationAuditError, match="model recipe"):
        audit.restored_probabilities_adaptation(values, broken)


def test_future_row_does_not_change_past_train_artifacts() -> None:
    train = [row("a", "20240102", 0, "2024-01-04T10:35:00-05:00")]
    before = audit.conditional_means(train)
    future = row("future", "20260901", 4, "2026-09-03T10:35:00-04:00")
    assert audit.conditional_means(train) == before
    assert future not in train


def test_double_gate_ties_promote_and_stale_or_pending_conserve() -> None:
    proposal = {"incumbent_snapshot_id": "frozen", "challenger_id": "new"}
    tie = {
        "candidate_count": 3,
        "challenger_logloss": 0.4,
        "incumbent_logloss": 0.4,
        "challenger_net_adverse": -10.0,
        "incumbent_net_adverse": -10.0,
    }
    assert audit.resolve_proposal(proposal, "frozen", tie) == ("PROMOTED", "new")
    assert audit.resolve_proposal(proposal, "other", tie) == (
        "STALE_CHALLENGER_REJECTED", "other"
    )
    assert audit.resolve_proposal(proposal, "frozen", None) == (
        "PENDING_BEYOND_DECISION_CUTOFF", "frozen"
    )
    bad = dict(tie, challenger_logloss=0.41)
    assert audit.resolve_proposal(proposal, "frozen", bad) == ("REJECTED", "frozen")


def test_gate_resolution_requires_all_h2_labels_before_midnight() -> None:
    sessions = evaluation_sessions()[:30]
    calendar = evaluation_sessions()[:35]
    gate = audit.proposal_gate_sessions(sessions[0], sessions)
    final = gate[-1]
    next_day = calendar[21]
    rows = [row("x", final, 1, audit.midnight(next_day).isoformat())]
    assert audit.proposal_resolution_day(gate, calendar, rows, calendar[-1]) == calendar[22]
    rows[0]["label_available_at"] = audit.midnight(next_day).isoformat().replace("T00:00:00", "T10:35:00")
    assert audit.proposal_resolution_day(gate, calendar, rows, next_day) is None


def test_gate_rows_cover_identical_shadow_rows_and_pending_has_none() -> None:
    sessions = evaluation_sessions()[:30]
    calendar = evaluation_sessions()[:35]
    gate_sessions = sessions[:21]
    proposal = {
        "proposal_id": "p1",
        "created_date": sessions[0],
        "gate_sessions": gate_sessions,
        "resolved_at": calendar[22],
        "status": "PROMOTED",
    }
    values = [row("x", gate_sessions[-1], 1, f"{calendar[21][:4]}-{calendar[21][4:6]}-{calendar[21][6:]}T10:35:00-05:00")]
    gates = [
        {
            "proposal_id": "p1", "role": role, "sessions": gate_sessions,
            "cost": "adverse", "starting_cash": 100_000.0,
            "cal_rows_used": 0, "candidate_ids": ["x"], "logloss": 0.5,
            "net_adverse": 1.0,
        }
        for role in ("challenger", "incumbent")
    ]
    rebuilt = audit.validate_gate_replay(
        proposal, gates, sessions, calendar, values, calendar[-1]
    )
    assert rebuilt and rebuilt["candidate_count"] == 1
    broken = copy.deepcopy(gates)
    broken[0]["candidate_ids"] = ["other"]
    with pytest.raises(audit.AdaptationAuditError, match="different rows"):
        audit.validate_gate_replay(proposal, broken, sessions, calendar, values, calendar[-1])


def test_pending_tail_still_reconstructs_partial_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = [
        {"candidate_id": "inside", "entry_date": "20260917", "ticker": "SPY", "right": "CALL"},
        {"candidate_id": "outside", "entry_date": "20260901", "ticker": "SPY", "right": "PUT"},
    ]
    proposal = {"proposal_id": "WEEKLY_20260917", "gate_sessions": ["20260917"]}
    def fake_score(_helper: object, _state: dict, rows: list[dict]) -> list[dict]:
        return [{
            "candidate_id": value["candidate_id"], "p_model": [1, 0, 0, 0, 0],
            "p_cal": [1, 0, 0, 0, 0], "ev_base": 0.0, "ev_adverse": 0.0,
        } for value in rows]
    monkeypatch.setattr(audit, "score_state", fake_score)
    rows = audit.rebuild_shadow_rows(
        object(), proposal, {"CHALLENGER": {"state_id": "tail"}}, candidates
    )
    assert [(value["candidate_id"], value["model_id"]) for value in rows] == [("inside", "tail")]


def test_bridge_preserves_all_old_candidates_and_exact_six_identities() -> None:
    old = [{"candidate_id": f"old-{index}", "value": index} for index in range(3234)]
    bridge, coverage = [], []
    for entry, exit_day in (("20260629", "20260701"), ("20260630", "20260702")):
        for ticker in audit.TICKERS:
            candidate_id = f"bridge:{ticker}:{entry}:CALL"
            built = entry == "20260629" and ticker != "SPY"
            if built:
                bridge.append({
                    "candidate_id": candidate_id, "ticker": ticker,
                    "entry_date": entry, "exit_date": exit_day,
                })
            coverage.append({
                "ticker": ticker, "entry_date": entry, "exit_date": exit_day,
                "status": (
                    "CANDIDATES_BUILT" if built
                    else "NO_DECISION_CANDIDATE" if entry == "20260629"
                    else "NO_SERIES"
                ),
                "reason": (
                    None if built
                    else "NO_VALID_1030_CALL_OR_PUT" if entry == "20260629"
                    else "NO_1_TO_8_DTE_SERIES_ALLOWING_H2"
                ),
                "candidate_ids": [candidate_id] if built else [],
            })
    result = audit.validate_bridge(old, bridge, coverage, old + bridge)
    assert result == {
        "old_candidates": 3234, "bridge_candidates": 2,
        "combined_candidates": 3236, "bridge_coverage_rows": 6,
    }
    mutated = copy.deepcopy(old + bridge)
    mutated[0]["value"] = -1
    with pytest.raises(audit.AdaptationAuditError, match="old candidate mutated"):
        audit.validate_bridge(old, bridge, coverage, mutated)


def test_score_comparison_detects_model_trace_and_probability_drift() -> None:
    expected = [{
        "policy": "WEEKLY_RAW", "candidate_id": "c", "entry_date": "20260102",
        "model_id": "s0", "context_status": "CONTEXT_AVAILABLE",
        "context_state_valid": True, "p_model": [0.5] * 2,
        "p_cal": [0.5] * 2, "ev_base": 1.0, "ev_adverse": 0.5,
    }]
    audit.compare_scores(copy.deepcopy(expected), expected, label="fixture scores")
    drift = copy.deepcopy(expected)
    drift[0]["model_id"] = "future"
    with pytest.raises(audit.AdaptationAuditError, match="model_id"):
        audit.compare_scores(drift, expected, label="fixture scores")
    with pytest.raises(audit.AdaptationAuditError, match="future/wrong model"):
        audit.validate_score_model_clock(
            {"policy": "WEEKLY_RAW", "model_id": "future"},
            {"entry_date": "20260102"},
            {"WEEKLY_RAW": {"20260102": "current"}},
        )


def test_auditor_has_no_fit_call_and_never_imports_producer() -> None:
    source = inspect.getsource(audit)
    assert ".fit(" not in source
    assert source.count("spec_from_file_location(") == 1
    assert 'spec_from_file_location("_adaptation_independent_h1_helper"' in source


def test_manifest_admission_and_closing_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "producer"
    root.mkdir()
    monkeypatch.setattr(audit, "PRODUCER_ROOT", root)
    for name in audit.OUTPUT_FILES:
        (root / name).write_text("{}\n" if name.endswith(".json") else "", encoding="utf-8")
    bridge = tmp_path / "bridge_manifest.json"
    bridge.write_text(json.dumps({
        "schema": "weekly_h2_boundary_bridge_manifest_v1",
        "status": "COMPLETE_WEEKLY_H2_BOUNDARY_BRIDGE_NOT_EVALUATED",
    }), encoding="utf-8")
    bridge_pin = {"path": str(bridge.resolve()), **audit.pin(bridge)}
    bridge_audit = tmp_path / "bridge_audit.json"
    bridge_audit.write_text(json.dumps({
        "status": "PASS_ARTIFICIAL_BRIDGE_AUDIT",
        "inputs": {"producer_manifest": bridge_pin},
    }), encoding="utf-8")
    dummy = tmp_path / "authority.txt"
    dummy.write_text("authority", encoding="utf-8")
    dummy_pin = {"path": str(dummy.resolve()), **audit.pin(dummy)}
    authorities = {name: dict(dummy_pin) for name in audit.EXTERNAL_KEYS}
    authorities["contract"] = {"path": str(audit.CONTRACT.resolve()), **audit.pin(audit.CONTRACT)}
    authorities["context_helper"] = {"path": str(audit.HELPER.resolve()), **audit.pin(audit.HELPER)}
    authorities["bridge_manifest"] = bridge_pin
    authorities["bridge_audit"] = {"path": str(bridge_audit.resolve()), **audit.pin(bridge_audit)}
    producer_code = tmp_path / "evaluate_weekly_context_adaptation.py"
    producer_tests = tmp_path / "test_evaluate_weekly_context_adaptation.py"
    producer_code.write_text("# fixture\n", encoding="utf-8")
    producer_tests.write_text("# fixture\n", encoding="utf-8")
    authorities["producer"] = {"path": str(producer_code.resolve()), **audit.pin(producer_code)}
    authorities["tests"] = {"path": str(producer_tests.resolve()), **audit.pin(producer_tests)}
    monkeypatch.setattr(audit, "PRODUCER_SHA256", authorities["producer"]["sha256"])
    monkeypatch.setattr(audit, "PRODUCER_TESTS_SHA256", authorities["tests"]["sha256"])
    monkeypatch.setattr(audit, "FROZEN_EXTERNAL_SHA256", {
        name: authorities[name]["sha256"] for name in audit.FROZEN_EXTERNAL_SHA256
    })
    consumed = {}
    for index in range(27):
        path = tmp_path / f"payload-{index}.json"
        path.write_text("{}", encoding="utf-8")
        consumed[str(path.resolve())] = {"path": str(path.resolve()), **audit.pin(path)}
    manifest = {
        "schema": audit.PRODUCER_SCHEMA, "status": audit.PRODUCER_STATUS,
        "external_authorities": authorities, "consumed_payloads": consumed,
        "implementation": {"producer": authorities["producer"], "tests": authorities["tests"]},
        "outputs": {name: audit.pin(root / name) for name in audit.OUTPUT_FILES},
        "flags": {
            "raw_read": False, "api_read": False, "broker_read": False,
            "production_changed": False, "future_labels_used": False,
            "models_fit": True, "frozen_fit": False, "seen_development": True,
            "promotion_approved": False,
        },
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    admitted, snapshots, payloads = audit.admit_producer_bundle(
        audit.sha256_file(manifest_path), audit.sha256_file(producer_code),
        audit.sha256_file(producer_tests), audit.sha256_file(bridge),
        audit.sha256_file(bridge_audit), audit.sha256_file(Path(audit.__file__)),
    )
    assert admitted["schema"] == audit.PRODUCER_SCHEMA
    changed = next(iter(payloads))
    changed.write_text(changed.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(audit.AdaptationAuditError, match="pin closing payload"):
        audit.revalidate(snapshots, payloads)

