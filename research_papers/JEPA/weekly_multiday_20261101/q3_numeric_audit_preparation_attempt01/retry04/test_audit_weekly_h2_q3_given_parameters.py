from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("q3_numeric_audit", HERE / "audit_weekly_h2_q3_given_parameters.py")
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def artifacts() -> tuple[dict, dict, dict, dict]:
    transform = {
        "feature_order": ["x", "z"], "medians": [2.0, 3.0],
        "missing_indicator_source_indices": [1], "scaler_mean": [1.0, 2.0, 0.5],
        "scaler_scale": [2.0, 4.0, 0.5],
    }
    model = {
        "type": "LogisticRegression", "C": 1.0, "max_iter": 2000, "random_state": 0, "solver": "lbfgs",
        "classes_present": [0, 1, 2], "coefficient": [[0.2, 0.1, -0.1], [-0.1, 0.3, 0.2], [0.0, -0.2, 0.1]],
        "intercept": [0.1, -0.2, 0.05], "train_prior": [0.2, 0.3, 0.5, 0.0, 0.0],
    }
    calibration = {"selected_alpha": 0.3}
    cells = {}
    for cost in audit.COSTS:
        cells[cost] = {"SPY:CALL": {str(label): {"mean_y": float(label - 1)} for label in range(5)}}
    return transform, model, calibration, {"cells": cells}


def test_restored_sklearn_predicts_without_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    transform, model_json, calibration, means = artifacts()
    monkeypatch.setattr(LogisticRegression, "fit", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fit called")))
    rows = [{
        "candidate_id": "a", "features": {"x": 5.0, "z": None}, "ticker": "SPY", "right": "CALL",
        "decision_ask": 1.0, "scenario": 2, "status": "OBSERVED_EXIT", "payoff_is_lower_bound": False,
    }]
    scores = audit.independent_scores(rows, model_json, transform, calibration, means)
    assert len(scores) == 1 and sum(scores[0]["p_model"]) == pytest.approx(1.0)
    assert sum(scores[0]["p_cal"]) == pytest.approx(1.0)
    restored = audit.restore_logistic(model_json)
    assert restored.n_features_in_ == restored.n_features_ == 3
    assert np.array_equal(restored.classes_, np.array([0, 1, 2]))


def test_transform_imputes_and_adds_frozen_indicator() -> None:
    transform, _, _, _ = artifacts()
    matrix = audit.transform_matrix([{"features": {"x": 5.0, "z": None}}], transform)
    assert np.allclose(matrix, np.asarray([[2.0, 0.25, 1.0]]), atol=0, rtol=0)
    with pytest.raises(audit.AuditError, match="feature order"):
        audit.transform_matrix([{"features": {"z": None, "x": 5.0}}], transform)


def test_score_comparison_detects_probability_mutation() -> None:
    transform, model, calibration, means = artifacts()
    rows = [{
        "candidate_id": "a", "features": {"x": 5.0, "z": None}, "ticker": "SPY", "right": "CALL",
        "decision_ask": 1.0, "scenario": 2, "status": "OBSERVED_EXIT", "payoff_is_lower_bound": False,
    }]
    expected = audit.independent_scores(rows, model, transform, calibration, means)
    actual = [dict(expected[0])]
    actual[0]["p_model"] = list(actual[0]["p_model"])
    actual[0]["p_model"][0] += 1e-4
    with pytest.raises(audit.AuditError, match="p_model"):
        audit.compare_scores(expected, actual)


def replay_fixture() -> tuple[list[dict], dict, list[str]]:
    row = {
        "candidate_id": "SPY:20260701:x:CALL", "ticker": "SPY", "right": "CALL",
        "entry_date": "20260701", "exit_date": "20260703", "status": "OBSERVED_EXIT",
        "entry_ask": 1.0, "exit_bid": 1.5, "entry_debit_base": 102.3, "entry_debit_adverse": 103.3,
        "net_base": 45.4, "net_adverse": 43.4, "_ev_base": 10.0, "_ev_adverse": 9.0,
        "duration_calendar_days": 2,
    }
    sessions = ["20260701", "20260702", "20260703"]
    coverage_rows = []
    for ticker in audit.TICKERS:
        for day in sessions:
            ids = [row["candidate_id"]] if ticker == "SPY" and day == "20260701" else []
            coverage_rows.append({"ticker": ticker, "entry_date": day, "candidate_ids": ids, "status": "CANDIDATES_BUILT" if ids else "NO_SERIES", "reason": None if ids else "NO_SERIES"})
    return [row], {"rows": coverage_rows}, sessions


def test_independent_replay_sequence_cash_and_max_one_ticker() -> None:
    rows, coverage, sessions = replay_fixture()
    ledger = audit.independent_replay(rows, coverage, sessions, "20260701", "EV_TOP1_H2", "adverse")
    events = [row["event"] for row in ledger if row["ticker"] == "SPY"]
    assert events == ["ENTRY", "EXIT"]
    assert ledger[-1]["event"] == "EXIT"
    assert ledger[-1]["cash"] == pytest.approx(audit.STARTING_CASH + 43.4)


def test_replay_does_not_open_second_same_ticker_before_h2_exit() -> None:
    rows, coverage, sessions = replay_fixture()
    second = dict(rows[0])
    second.update(
        candidate_id="SPY:20260702:y:CALL", entry_date="20260702", exit_date="20260703",
        duration_calendar_days=1,
    )
    rows.append(second)
    cover = next(row for row in coverage["rows"] if row["ticker"] == "SPY" and row["entry_date"] == "20260702")
    cover.update(candidate_ids=[second["candidate_id"]], status="CANDIDATES_BUILT", reason=None)
    ledger = audit.independent_replay(rows, coverage, sessions, "20260702", "EV_TOP1_H2", "adverse")
    assert sum(row["event"] == "ENTRY" for row in ledger) == 1
    assert any(row["event"] == "WAIT" and row["reason"] == "OPEN_POSITION" for row in ledger)


def test_ledger_comparison_and_monthly_reconciliation_fail_closed() -> None:
    rows, coverage, sessions = replay_fixture()
    expected = audit.independent_replay(rows, coverage, sessions, "20260701", "ALWAYS_CALL_H2", "base")
    actual = [dict(row) for row in expected]
    actual[-1]["cash"] += 1
    with pytest.raises(audit.AuditError, match="ledger numeric"):
        audit.compare_ledgers(expected, actual)
    metrics = audit.ledger_metrics(expected)
    assert sum(metrics["monthly_net_usd"].values()) == pytest.approx(metrics["net_usd"])
    published = {key: value for key, value in metrics.items() if key != "monthly_net_usd"}
    audit.compare_metric_map(metrics, published, "fixture")
    published["wait"] += 1
    with pytest.raises(audit.AuditError, match="summary metric fixture/wait"):
        audit.compare_metric_map(metrics, published, "fixture")


def test_closing_payload_snapshot_detects_bytes_or_hash_mutation(tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}\n", encoding="utf-8")
    pin = {"bytes": payload.stat().st_size, "sha256": audit.sha256_file(payload)}
    audit.verify_payload_snapshot({payload: pin}, "admission")
    payload.write_text('{"changed":true}\n', encoding="utf-8")
    with pytest.raises(audit.AuditError, match="pin closing:payload.json"):
        audit.verify_payload_snapshot({payload: pin}, "closing")
