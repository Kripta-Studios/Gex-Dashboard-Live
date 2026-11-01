from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

import evaluate_weekly_context_adaptation as adaptation
import evaluate_weekly_context_models as context_helper
import evaluate_weekly_h2_ev_v2 as evaluator


def sessions(count: int = 1000) -> list[str]:
    start = datetime(2022, 9, 1)
    values = []
    while len(values) < count:
        if start.weekday() < 5:
            values.append(start.strftime("%Y%m%d"))
        start += timedelta(days=1)
    return values


def row(day: str, number: int, scenario: int | None = None, available_day: str | None = None) -> dict:
    label = number % 5 if scenario is None else scenario
    available_day = available_day or day
    return {
        "candidate_id": f"SPY:{day}:X:{number}:CALL", "entry_date": day,
        "ticker": "SPY", "right": "CALL", "scenario": label,
        "label_available_at": f"{available_day[:4]}-{available_day[4:6]}-{available_day[6:]}T10:35:00-05:00",
        "decision_ask": 1.0, "net_base": float(label), "net_adverse": float(label),
        "_x_context": [float(number), np.nan],
    }


def test_fit_plan_uses_exact_i_minus_65_i_minus_2_and_purges_train_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    days = sessions()
    monkeypatch.setattr(adaptation, "FIRST_EVAL", days[200])
    monkeypatch.setattr(adaptation, "LAST_EVAL", days[377])
    monkeypatch.setattr(adaptation, "EXPECTED_MONTHLY", len({d[:6] for d in days[200:378]}))
    iso = {datetime.strptime(d, "%Y%m%d").date().isocalendar()[:2] for d in days[200:378]}
    monkeypatch.setattr(adaptation, "EXPECTED_WEEKLY", len(iso))
    evaluation = days[200:378]
    monthly = [d for i, d in enumerate(evaluation) if i == 0 or evaluation[i - 1][:6] != d[:6]]
    weekly = [d for i, d in enumerate(evaluation) if i == 0 or datetime.strptime(evaluation[i - 1], "%Y%m%d").date().isocalendar()[:2] != datetime.strptime(d, "%Y%m%d").date().isocalendar()[:2]]
    monkeypatch.setattr(adaptation, "EXPECTED_COINCIDENT", len(set(monthly) & set(weekly)))
    monkeypatch.setattr(adaptation, "EXPECTED_PHYSICAL_FITS", len(set(monthly) | set(weekly)))
    schedules = adaptation.creation_dates(days)
    rows = [row(day, index, available_day=days[min(index + 2, len(days) - 1)]) for index, day in enumerate(days[:378])]
    creation = schedules["PHYSICAL"][0]
    i = days.index(creation)
    # This early entry label crosses CAL_start00 and must be recorded as purged.
    poisoned = row(days[i - 70], 9999, available_day=days[i - 64])
    rows.append(poisoned)
    plans = adaptation.build_fit_plans(rows, days)
    plan = plans[0]
    assert plan["cal_sessions"] == days[i - 65:i - 2]
    assert poisoned["candidate_id"] in plan["purged_train_ids"]
    assert poisoned["candidate_id"] not in plan["train_ids"]
    assert all(candidate_id not in plan["train_ids"] for candidate_id in plan["cal_ids"])


def test_future_postdate_poison_does_not_change_past_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    days = sessions()
    monkeypatch.setattr(adaptation, "FIRST_EVAL", days[200])
    monkeypatch.setattr(adaptation, "LAST_EVAL", days[377])
    monthly = len({d[:6] for d in days[200:378]})
    weekly = len({datetime.strptime(d, "%Y%m%d").date().isocalendar()[:2] for d in days[200:378]})
    monkeypatch.setattr(adaptation, "EXPECTED_MONTHLY", monthly)
    monkeypatch.setattr(adaptation, "EXPECTED_WEEKLY", weekly)
    evaluation = days[200:378]
    monthly_dates = [d for i, d in enumerate(evaluation) if i == 0 or evaluation[i - 1][:6] != d[:6]]
    weekly_dates = [d for i, d in enumerate(evaluation) if i == 0 or datetime.strptime(evaluation[i - 1], "%Y%m%d").date().isocalendar()[:2] != datetime.strptime(d, "%Y%m%d").date().isocalendar()[:2]]
    monkeypatch.setattr(adaptation, "EXPECTED_COINCIDENT", len(set(monthly_dates) & set(weekly_dates)))
    monkeypatch.setattr(adaptation, "EXPECTED_PHYSICAL_FITS", len(set(monthly_dates) | set(weekly_dates)))
    adaptation.creation_dates(days)
    base = [row(day, index, available_day=days[min(index + 2, len(days)-1)]) for index, day in enumerate(days[:378])]
    first = adaptation.build_fit_plans(base, days)[0]
    poison = row(days[300], 10001, available_day=days[301])
    second = adaptation.build_fit_plans([*base, poison], days)[0]
    assert first == second


def test_creation_schedule_shares_coincident_physical_fits(monkeypatch: pytest.MonkeyPatch) -> None:
    days = sessions()
    monkeypatch.setattr(adaptation, "FIRST_EVAL", days[200])
    monkeypatch.setattr(adaptation, "LAST_EVAL", days[377])
    evaluation = days[200:378]
    monkeypatch.setattr(adaptation, "EXPECTED_MONTHLY", len({d[:6] for d in evaluation}))
    monkeypatch.setattr(adaptation, "EXPECTED_WEEKLY", len({datetime.strptime(d, "%Y%m%d").date().isocalendar()[:2] for d in evaluation}))
    monthly = [d for i, d in enumerate(evaluation) if i == 0 or evaluation[i-1][:6] != d[:6]]
    weekly = [d for i, d in enumerate(evaluation) if i == 0 or datetime.strptime(evaluation[i-1], "%Y%m%d").date().isocalendar()[:2] != datetime.strptime(d, "%Y%m%d").date().isocalendar()[:2]]
    monkeypatch.setattr(adaptation, "EXPECTED_COINCIDENT", len(set(monthly) & set(weekly)))
    monkeypatch.setattr(adaptation, "EXPECTED_PHYSICAL_FITS", len(set(monthly) | set(weekly)))
    result = adaptation.creation_dates(days)
    assert len(result["PHYSICAL"]) == len(set(result["MONTHLY"]) | set(result["WEEKLY"]))


def test_context_saved_transform_and_inference_are_deterministic() -> None:
    state = {
        "state_id": "S", "feature_order": ["a", "b"],
        "transform": {"feature_order": ["a", "b"], "medians": [0.0, 0.0], "missing_indicator_source_indices": [1], "scaler_mean": [0.0, 0.0, 0.0], "scaler_scale": [1.0, 1.0, 1.0]},
        "model": {"classes_present": [0, 1], "coefficient": [[1.0, 0.0, 0.0]], "intercept": [0.0]},
        "prior": [0.5, 0.5, 0.0, 0.0, 0.0], "calibration": {"selected_alpha": 0.0},
        "conditional_means": {"cells": {cost: {"SPY:CALL": {str(i): {"mean_y": float(i)} for i in range(5)}} for cost in adaptation.COSTS}},
    }
    values = np.asarray([[2.0, np.nan]])
    p = adaptation.saved_probabilities(values, state)
    assert p.shape == (1, 5) and p.sum() == pytest.approx(1.0) and p[0, 1] > p[0, 0]
    scored = adaptation.score_state(state, [{"candidate_id": "C", "entry_date": "20260102", "ticker": "SPY", "right": "CALL", "decision_ask": 1.0, "_x_context": [2.0, np.nan]}])
    assert scored[0]["model_id"] == "S" and scored[0]["ev_adverse"] == pytest.approx(scored[0]["ev_base"])


def test_saved_binary_probabilities_match_real_sklearn_predict_proba() -> None:
    from sklearn.linear_model import LogisticRegression

    values = np.asarray([[-2.0], [-1.0], [1.0], [2.0]])
    labels = np.asarray([1, 1, 4, 4])
    fitted = LogisticRegression(C=1.0, l1_ratio=0.0, solver="lbfgs", max_iter=2000, random_state=0).fit(values, labels)
    state = {
        "feature_order": ["x"],
        "transform": {"feature_order": ["x"], "medians": [0.0], "missing_indicator_source_indices": [], "scaler_mean": [0.0], "scaler_scale": [1.0]},
        "model": {"classes_present": fitted.classes_.astype(int).tolist(), "coefficient": fitted.coef_.tolist(), "intercept": fitted.intercept_.tolist()},
    }
    restored = adaptation.saved_probabilities(values, state)
    expected = np.zeros((len(values), 5))
    expected[:, fitted.classes_.astype(int)] = fitted.predict_proba(values)
    assert np.allclose(restored, expected, atol=1e-15, rtol=0)


def test_real_two_class_fit_state_has_no_warning_and_saved_scoring_parity() -> None:
    feature_names = [f"context_{index}" for index in range(81)]
    rows = []
    for index in range(16):
        scenario = 1 if index % 2 == 0 else 4
        rows.append({
            "candidate_id": f"C{index}", "_x_context": [float((index + column) % 7) for column in range(182)],
            "entry_date": "20250102",
            "scenario": scenario, "ticker": "SPY", "right": "CALL", "decision_ask": 1.0,
            "net_base": float(scenario - 2), "net_adverse": float(scenario - 2.1),
            "_model_label_eligible": True,
        })
    plan = {"state_id": "CONTEXT182_TOY", "train_ids": [row["candidate_id"] for row in rows[:10]], "cal_ids": [row["candidate_id"] for row in rows[10:]], "purged_train_ids": []}
    by_id = {row["candidate_id"]: row for row in rows}
    by_id["__feature_names__"] = feature_names
    state = adaptation.fit_state(plan, by_id, context_helper, evaluator)
    assert state["model"]["classes_present"] == [1, 4]
    assert state["model"]["fit_warnings"] == [] and state["model"]["penalty"] == "l2"
    runtime = adaptation.score_state(state, rows[10:])
    saved = adaptation.score_state(adaptation.strip_runtime(state), rows[10:])
    assert np.allclose([item["p_cal"] for item in runtime], [item["p_cal"] for item in saved], atol=1e-12, rtol=0)
    assert np.allclose([item["ev_adverse"] for item in runtime], [item["ev_adverse"] for item in saved], atol=1e-10, rtol=0)


@pytest.mark.parametrize(
    ("loss_c", "loss_i", "net_c", "net_i", "same", "n", "expected"),
    [
        (1.0, 1.0, 0.0, 0.0, True, 1, "PROMOTED"),
        (1.1, 1.0, 1.0, 0.0, True, 1, "REJECTED"),
        (0.9, 1.0, -1.0, 0.0, True, 1, "REJECTED"),
        (0.9, 1.0, 1.0, 0.0, False, 1, "STALE_CHALLENGER_REJECTED"),
        (0.9, 1.0, 1.0, 0.0, True, 0, "REJECTED_NO_GATE_ROWS"),
    ],
)
def test_guard_double_condition_ties_stale_and_empty(loss_c: float, loss_i: float, net_c: float, net_i: float, same: bool, n: int, expected: str) -> None:
    assert adaptation.challenge_status(loss_c, loss_i, net_c, net_i, same_incumbent=same, gate_rows=n) == expected


def test_shadow_is_21_sessions_and_maturity_is_strict_next_session() -> None:
    days = sessions(100)
    gate = adaptation.proposal_gate(days[10], days)
    assert gate == days[10:31]
    assert adaptation.maturity_date(gate, days) == days[33]
    assert adaptation.maturity_date(days[-21:], days) is None
    assert adaptation.proposal_gate(days[-2], days) == days[-2:]
    assert adaptation.maturity_date(days[-2:], days) is None


def test_guard_maturity_rejects_same_day_1035_label_for_0000_asof() -> None:
    item = row("20260102", 1, available_day="20260105")
    assert not adaptation.gate_labels_mature([item], ["20260102"], "20260105")
    assert adaptation.gate_labels_mature([item], ["20260102"], "20260106")


def test_bridge_overlay_replaces_only_six_horizon_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    days = ["20260629", "20260630", "20260701", "20260702"]
    monkeypatch.setattr(adaptation, "EXPECTED_SESSION_COUNT", 4)
    calendar = [{"ticker": ticker, "date": day} for ticker in adaptation.TICKERS for day in days]
    h1_rows = [{"ticker": ticker, "entry_date": day, "status": "HORIZON_OUTSIDE_CALENDAR"} for ticker in adaptation.TICKERS for day in days[:2]]
    overlay = {
        "schema": "weekly_h2_boundary_bridge_coverage_overlay_v1",
        "replacement_keys": [{"ticker": ticker, "entry_date": day} for ticker in adaptation.TICKERS for day in days[:2]],
        "rows": [{"ticker": ticker, "entry_date": day, "exit_date": "20260701" if day.endswith("29") else "20260702", "status": "NO_DECISION_CANDIDATE" if day.endswith("29") else "NO_SERIES"} for ticker in adaptation.TICKERS for day in days[:2]],
    }
    adaptation.validate_bridge_overlay(overlay, [])
    merged = adaptation.merge_coverages({"calendar": calendar[:6], "rows": h1_rows}, {"calendar": calendar[6:], "rows": []}, overlay)
    assert len(merged["rows"]) == 6 and {x["status"] for x in merged["rows"]} == {"NO_DECISION_CANDIDATE", "NO_SERIES"}
    swapped = {**overlay, "rows": [dict(item) for item in overlay["rows"]]}
    swapped["rows"][0]["status"] = "NO_SERIES"
    with pytest.raises(adaptation.AdaptationError, match="June29 bridge"):
        adaptation.validate_bridge_overlay(swapped, [])
    bad = {"rows": overlay["rows"][:-1]}
    with pytest.raises(adaptation.AdaptationError, match="six coverage"):
        adaptation.merge_coverages({"calendar": calendar[:6], "rows": h1_rows}, {"calendar": calendar[6:], "rows": []}, bad)


def test_ledger_keeps_entry_and_exit_model_identity() -> None:
    ledger = [{"event": "ENTRY", "candidate_id": "C"}, {"event": "EXIT", "candidate_id": "C"}, {"event": "WAIT"}]
    result = adaptation.enrich_ledger(ledger, "WEEKLY_RAW", {"C": "S1"})
    assert [x["model_id"] for x in result] == ["S1", "S1", None]


def test_source_contains_no_fit_on_frozen_path_or_helper_global_mutation() -> None:
    source = Path(adaptation.__file__).read_text(encoding="utf-8")
    assert "frozen.fit(" not in source.lower()
    assert "setattr(context_helper" not in source and "setattr(evaluator" not in source
    assert "warm_start=False" in source
