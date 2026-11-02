from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

import evaluate_weekly_daily_adaptation as daily


def weekdays(start: str, count: int) -> list[str]:
    value = datetime.strptime(start, "%Y%m%d")
    output = []
    while len(output) < count:
        if value.weekday() < 5:
            output.append(value.strftime("%Y%m%d"))
        value += timedelta(days=1)
    return output


def plan(day: str, *, frequency: str = "DAILY") -> dict:
    return {
        "state_id": f"CONTEXT182_{day}", "creation_date": day,
        "asof": f"{day[:4]}-{day[4:6]}-{day[6:]}T00:00:00-05:00",
        "frequencies": [frequency], "cal_sessions": ["20251201"],
        "cal_start": "20251201", "cal_end": "20251201", "train_ids": ["T"],
        "cal_ids": ["C"], "purged_train_ids": [],
        "train_label_available_max": "2025-11-30T10:35:00-05:00",
        "cal_label_available_max": "2025-12-01T10:35:00-05:00",
    }


def score(candidate_id: str, policy: str, model_id: str, ev: float = 1.0) -> dict:
    ticker, entry_date, _expiration, right = candidate_id.split(":")
    return {
        "candidate_id": candidate_id, "entry_date": entry_date, "ev_adverse": ev,
        "ev_base": ev + 0.1, "is_bridge": False, "model_id": model_id,
        "p_cal": [0.2] * 5, "p_model": [0.2] * 5,
        "payoff_is_lower_bound": False, "policy": policy, "right": right,
        "scenario": 1, "ticker": ticker,
    }


def test_build_daily_plans_has_strict_63_session_cal_and_gap_two(monkeypatch: pytest.MonkeyPatch) -> None:
    sessions = weekdays("20250901", 70)
    monkeypatch.setattr(daily, "FIRST_EVAL", sessions[68])
    monkeypatch.setattr(daily, "LAST_EVAL", sessions[69])
    monkeypatch.setattr(daily, "EXPECTED_SESSIONS", 2)
    rows = []
    for index, day in enumerate(sessions):
        for scenario in (1, 4):
            rows.append({
                "candidate_id": f"SPY:{day}:X:{scenario}", "entry_date": day,
                "scenario": scenario,
                "label_available_at": f"{day[:4]}-{day[4:6]}-{day[6:]}T10:35:00-05:00",
            })
    plans = daily.build_daily_plans(rows, sessions)
    assert len(plans) == 2
    assert len(plans[0]["cal_sessions"]) == 63
    assert plans[0]["cal_sessions"] == sessions[3:66]
    assert sessions[66:68] == [sessions[66], sessions[67]]
    assert all(candidate_id.split(":")[1] < plans[0]["cal_start"] for candidate_id in plans[0]["train_ids"])


def test_future_label_does_not_enter_past_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    sessions = weekdays("20250901", 69)
    monkeypatch.setattr(daily, "FIRST_EVAL", sessions[-1])
    monkeypatch.setattr(daily, "LAST_EVAL", sessions[-1])
    monkeypatch.setattr(daily, "EXPECTED_SESSIONS", 1)
    rows = [
        {"candidate_id": f"SPY:{day}:X:{scenario}", "entry_date": day, "scenario": scenario, "label_available_at": f"{day[:4]}-{day[4:6]}-{day[6:]}T10:35:00-05:00"}
        for day in sessions for scenario in (1, 4)
    ]
    poisoned = dict(rows[0])
    poisoned["candidate_id"] = "SPY:20250901:FUTURE:1"
    poisoned["label_available_at"] = "2027-01-01T10:35:00-05:00"
    baseline = daily.build_daily_plans(rows, sessions)
    changed = daily.build_daily_plans([*rows, poisoned], sessions)
    assert baseline[0]["train_ids"] == changed[0]["train_ids"]
    assert baseline[0]["cal_ids"] == changed[0]["cal_ids"]
    assert poisoned["candidate_id"] in changed[0]["purged_train_ids"]


def test_reused_plan_is_referenced_without_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    sealed = plan("20260102", frequency="MONTHLY")
    state = {**sealed, "model": {"coefficient": [[1.0]]}}
    daily_plan = {**sealed, "frequencies": ["DAILY"]}
    original = dict(state)
    monkeypatch.setattr(daily, "EXPECTED_SESSIONS", 1)
    monkeypatch.setattr(daily, "EXPECTED_REUSED", 1)
    monkeypatch.setattr(daily, "EXPECTED_NEW", 0)
    schedule, new, reused, published = daily.bind_reused([daily_plan], [sealed], [state])
    assert schedule[0]["source"] == "REUSED" and schedule[0]["source_row"] == 0
    assert new == [] and reused[state["state_id"]] is state
    assert published == [sealed]
    assert state == original and state["frequencies"] == ["MONTHLY"]


def test_terminal_states_are_kept_but_unused(monkeypatch: pytest.MonkeyPatch) -> None:
    plans = [plan("20260916"), plan("20260917")]
    monkeypatch.setattr(daily, "EXPECTED_SESSIONS", 2)
    monkeypatch.setattr(daily, "EXPECTED_REUSED", 0)
    monkeypatch.setattr(daily, "EXPECTED_NEW", 2)
    schedule, new, reused, published = daily.bind_reused(plans, [], [])
    assert len(new) == 2 and reused == {}
    assert published == plans
    assert all(row["terminal_unused_for_scoring"] and not row["used_for_scoring"] for row in schedule)


def test_reused_state_frequency_must_equal_sealed_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    sealed = plan("20260102", frequency="MONTHLY")
    daily_plan = {**sealed, "frequencies": ["DAILY"]}
    state = {**sealed, "frequencies": ["WEEKLY"]}
    monkeypatch.setattr(daily, "EXPECTED_SESSIONS", 1)
    monkeypatch.setattr(daily, "EXPECTED_REUSED", 1)
    monkeypatch.setattr(daily, "EXPECTED_NEW", 0)
    with pytest.raises(daily.DailyAdaptationError, match="state/plan mismatch"):
        daily.bind_reused([daily_plan], [sealed], [state])


class FakeGate:
    def __init__(self, fail: bool = False) -> None:
        self.observations = 0
        self.gates = 0
        self.fail = fail

    def observation(self) -> dict:
        self.observations += 1
        return {"available_ram_bytes": 3_000_000_000, "free_commit_bytes": 3_000_000_000}

    def gate(self, _value: dict) -> None:
        self.gates += 1
        if self.fail:
            raise ValueError("gate")


class FakeOriginal:
    def __init__(self) -> None:
        self.fit_calls = 0

    def fit_state(self, value: dict, _by_id: dict, _context: object, _evaluator: object) -> dict:
        self.fit_calls += 1
        return {**value, "prior": [0.0, 1.0, 0.0, 0.0, 0.0], "prior_support": [0, 1, 0, 0, 0], "calibration": {"selected_alpha": 0.0}, "model": {}, "transform": {}, "conditional_means": {}, "_runtime": True}

    def score_state(self, _state: dict, rows: list[dict]) -> list[dict]:
        return [{"candidate_id": row["candidate_id"], "p_model": [0.2] * 5, "p_cal": [0.2] * 5, "ev_base": 1.1, "ev_adverse": 1.0} for row in rows]

    def strip_runtime(self, state: dict) -> dict:
        return {key: value for key, value in state.items() if key != "_runtime"}


def test_new_fit_journal_gate_and_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plans = [plan("20260106"), plan("20260107")]
    original, gate = FakeOriginal(), FakeGate()
    monkeypatch.setattr(daily, "EXPECTED_NEW", 2)
    result = daily.fit_new_states(plans, {"C": {"candidate_id": "C"}}, object(), object(), original, gate, tmp_path)
    assert original.fit_calls == gate.observations == gate.gates == 2
    assert len(result) == 2 and len(daily.read_jsonl(tmp_path / "fit_journal.jsonl")) == 4
    assert len(daily.read_jsonl(tmp_path / "daily_states_new.jsonl")) == 2
    assert len(list(tmp_path.glob("fit_state_CONTEXT182_*.json"))) == 2


def test_exactly_136_new_fit_calls_and_272_journal_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plans = [plan(day) for day in weekdays("20260102", 136)]
    original, gate = FakeOriginal(), FakeGate()
    monkeypatch.setattr(daily, "EXPECTED_NEW", 136)
    result = daily.fit_new_states(plans, {"C": {"candidate_id": "C"}}, object(), object(), original, gate, tmp_path)
    assert len(result) == 136
    assert original.fit_calls == gate.observations == gate.gates == 136
    assert len(daily.read_jsonl(tmp_path / "fit_journal.jsonl")) == 272
    assert len(daily.read_jsonl(tmp_path / "daily_states_new.jsonl")) == 136
    assert len(list(tmp_path.glob("fit_state_CONTEXT182_*.json"))) == 136


def test_gate_failure_preserves_start_and_stops_before_fit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original, gate = FakeOriginal(), FakeGate(fail=True)
    monkeypatch.setattr(daily, "EXPECTED_NEW", 1)
    with pytest.raises(ValueError, match="gate"):
        daily.fit_new_states([plan("20260106")], {"C": {"candidate_id": "C"}}, object(), object(), original, gate, tmp_path)
    journal = daily.read_jsonl(tmp_path / "fit_journal.jsonl")
    assert len(journal) == 1 and journal[0]["event"] == "FIT_START"
    assert original.fit_calls == 0 and not list(tmp_path.glob("fit_state_*.json"))


def test_reused_sklearn_version_and_frequency_composition(monkeypatch: pytest.MonkeyPatch) -> None:
    version = daily.importlib.metadata.version("scikit-learn")
    states = []
    for frequencies, count in ((["MONTHLY"], 4), (["WEEKLY"], 33), (["MONTHLY", "WEEKLY"], 5)):
        states.extend({"model": {"sklearn_version": version}, "frequencies": frequencies} for _ in range(count))
    daily.validate_reused_states(states)
    states[0]["model"]["sklearn_version"] = "0.0.invalid"
    with pytest.raises(daily.DailyAdaptationError, match="sklearn version"):
        daily.validate_reused_states(states)


class MismatchedSavedOriginal(FakeOriginal):
    def score_state(self, state: dict, rows: list[dict]) -> list[dict]:
        values = super().score_state(state, rows)
        if "_runtime" not in state:
            values[0]["p_cal"] = [0.1, 0.2, 0.2, 0.2, 0.3]
            values[0]["ev_base"] = 9.0
        return values


def test_saved_parity_checks_calibrated_probability_and_base_ev(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(daily, "EXPECTED_NEW", 1)
    with pytest.raises(daily.DailyAdaptationError, match="calibrated parity"):
        daily.fit_new_states([plan("20260106")], {"C": {"candidate_id": "C"}}, object(), object(), MismatchedSavedOriginal(), FakeGate(), tmp_path)


class OrderMismatchOriginal(FakeOriginal):
    def score_state(self, state: dict, rows: list[dict]) -> list[dict]:
        values = super().score_state(state, rows)
        return list(reversed(values)) if "_runtime" not in state else values


def test_saved_parity_checks_candidate_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    value = plan("20260106")
    value["cal_ids"] = ["C", "D"]
    monkeypatch.setattr(daily, "EXPECTED_NEW", 1)
    with pytest.raises(daily.DailyAdaptationError, match="candidate order"):
        daily.fit_new_states([value], {"C": {"candidate_id": "C"}, "D": {"candidate_id": "D"}}, object(), object(), OrderMismatchOriginal(), FakeGate(), tmp_path)


def test_reused_score_is_copied_without_inference() -> None:
    candidate_id = "SPY:20260102:20260109:CALL"
    first = score(candidate_id, "MONTHLY_RAW", "CONTEXT182_20260102")
    second = score(candidate_id, "WEEKLY_RAW", "CONTEXT182_20260102")
    schedule = [{"date": "20260102", "state_id": "CONTEXT182_20260102", "source": "REUSED", "used_for_scoring": True}]
    rows = [{"candidate_id": candidate_id, "entry_date": "20260102"}]
    result = daily.reused_daily_scores(rows, schedule, [first, second])
    assert result == [{**first, "policy": "DAILY_RAW"}]


def test_reused_score_mismatch_fails_closed() -> None:
    candidate_id = "SPY:20260102:20260109:CALL"
    first = score(candidate_id, "MONTHLY_RAW", "CONTEXT182_20260102")
    second = score(candidate_id, "WEEKLY_RAW", "CONTEXT182_20260102", ev=2.0)
    schedule = [{"date": "20260102", "state_id": "CONTEXT182_20260102", "source": "REUSED", "used_for_scoring": True}]
    with pytest.raises(daily.DailyAdaptationError, match="reused score"):
        daily.reused_daily_scores([{"candidate_id": candidate_id, "entry_date": "20260102"}], schedule, [first, second])


def test_daily_weekly_diagnostic_detects_top1_change(monkeypatch: pytest.MonkeyPatch) -> None:
    call = "SPY:20260102:20260109:CALL"
    put = "SPY:20260102:20260109:PUT"
    values = [
        score(call, "DAILY_RAW", "D", 2.0), score(put, "DAILY_RAW", "D", 1.0),
        score(call, "WEEKLY_RAW", "W", 1.0), score(put, "WEEKLY_RAW", "W", 2.0),
    ]
    monkeypatch.setattr(daily, "EXPECTED_CANDIDATES", 2)
    result = daily.candidate_diagnostics(values)
    assert len(result) == 2 and all(row["top1_changed"] for row in result)


def test_score_universe_requires_exact_common_set_and_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate_id = "SPY:20260102:20260109:CALL"
    rows = [{"candidate_id": candidate_id, "entry_date": "20260102", "ticker": "SPY", "right": "CALL", "scenario": 1, "payoff_is_lower_bound": False}]
    monkeypatch.setattr(daily, "EXPECTED_CANDIDATES", 1)
    daily.validate_score_universe([score(candidate_id, "DAILY_RAW", "D")], rows, ("DAILY_RAW",))
    bad = score(candidate_id, "DAILY_RAW", "D")
    bad.pop("p_cal")
    with pytest.raises(daily.DailyAdaptationError, match="score schema"):
        daily.validate_score_universe([bad], rows, ("DAILY_RAW",))


def test_control_ledger_copy_is_byte_exact_and_tamper_fails(tmp_path: Path) -> None:
    source, target = tmp_path / "source.jsonl", tmp_path / "copy.jsonl"
    source.write_bytes(b'{"event":"WAIT"}\n')
    expected = daily.pin(source)
    daily.copy_control_ledger(source, target, expected)
    assert source.read_bytes() == target.read_bytes()
    source.write_bytes(b'{"event":"ENTRY"}\n')
    with pytest.raises(daily.DailyAdaptationError, match="pin control ledger"):
        daily.copy_control_ledger(source, tmp_path / "second.jsonl", expected)


def test_eight_month_criterion_fails_on_zero_month(monkeypatch: pytest.MonkeyPatch) -> None:
    months = {month: 1.0 for month in daily.MONTHS}
    assert daily.passes_complete_months(months)
    months["202604"] = 0.0
    assert not daily.passes_complete_months(months)


def test_source_does_not_call_forbidden_original_entry_points() -> None:
    source = Path(daily.__file__).read_text(encoding="utf-8")
    for name in ("creation_dates", "build_fit_plans", "simulate_guard", "execute_admitted", "finish_evaluation"):
        assert f"original.{name}(" not in source
    assert "original.run(" not in source and "original.main(" not in source
