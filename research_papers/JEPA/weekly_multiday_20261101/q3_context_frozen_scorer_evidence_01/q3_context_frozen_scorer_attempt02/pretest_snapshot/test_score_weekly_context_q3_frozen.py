from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

import score_weekly_context_q3_frozen as scorer


def candidate(candidate_id: str = "SPY:20260701:20260710:CALL", right: str = "CALL") -> dict:
    values = {name: float(index + 1) for index, name in enumerate(scorer.FEATURE18)}
    values.update(ticker_SPY=1.0, ticker_QQQ=0.0, ticker_SPXW=0.0, right_call=float(right == "CALL"), weekday=2.0)
    return {
        "candidate_id": candidate_id, "ticker": "SPY", "right": right,
        "entry_date": "20260701", "exit_date": "20260702", "expiration": "20260710",
        "features": values, "decision_ask": 1.0, "entry_ask": 1.0, "exit_bid": 1.5,
        "status": "OBSERVED_EXIT", "scenario": 3, "payoff_is_lower_bound": False,
        "net_base": 45.4, "net_adverse": 43.4,
        "entry_debit_base": 102.3, "entry_debit_adverse": 103.3,
    }


def transform(width: int) -> dict:
    return {
        "feature_order": [f"f{index}" for index in range(width)],
        "fit_scope": "TRAIN_ONLY", "medians": [0.0] * width,
        "missing_indicator_source_indices": [0],
        "missing_indicator_order": ["f0__missing"],
        "scaler_mean": [0.0] * (width + 1), "scaler_scale": [1.0] * (width + 1),
        "imputer": {"strategy": "median", "add_indicator": True, "keep_empty_features": True},
    }


def model(width: int) -> dict:
    coefficients = np.zeros((5, width + 1), dtype=float)
    coefficients[:, 0] = np.arange(5)
    return {
        "type": "LogisticRegression", "fit_scope": "TRAIN_ONLY", "C": 1.0,
        "solver": "lbfgs", "max_iter": 2000, "random_state": 0,
        "classes_present": list(range(5)), "classes_full": list(range(5)),
        "coefficient": coefficients.tolist(), "intercept": [0.0] * 5,
    }


def means() -> dict:
    cells = {}
    for cost in scorer.COSTS:
        cells[cost] = {}
        for ticker in scorer.TICKERS:
            for right in scorer.RIGHTS:
                cells[cost][f"{ticker}:{right}"] = {str(label): {"mean_y": float(label - 2)} for label in range(5)}
    return {"cells": cells}


def test_category_and_context_semantics_preserve_missing_and_invalid() -> None:
    row = candidate()
    category = scorer.category30(row)
    assert len(category) == 30 and sum(category) == 1 and category[2] == 1
    available = {"status": "CONTEXT_AVAILABLE", "state_valid": True, "context_81": [float(index) for index in range(81)]}
    invalid = {"status": "CONTEXT_AVAILABLE", "state_valid": False, "context_81": [9.0] * 81}
    missing = {"status": "CONTEXT_MISSING_SOURCE", "state_valid": None, "context_81": None}
    assert scorer.context182(row, available)[18:99] == available["context_81"]
    assert scorer.context182(row, invalid)[18:180] == [0.0] * 162
    assert scorer.context182(row, invalid)[-2:] == [1.0, 0.0]
    assert scorer.context182(row, missing)[18:180] == [0.0] * 162
    assert scorer.context182(row, missing)[-2:] == [0.0, 0.0]
    put = candidate("SPY:20260701:20260710:PUT", "PUT")
    assert scorer.context182(put, available)[99:180] == [-float(index) for index in range(81)]


def test_transform_and_coefficients_are_restored_without_estimator() -> None:
    saved = transform(2)
    saved["feature_order"] = ["a", "b"]
    matrix = np.asarray([[np.nan, 2.0], [3.0, 4.0]])
    transformed = scorer.apply_transform(matrix, saved, ["a", "b"])
    assert transformed.tolist() == [[0.0, 2.0, 1.0], [3.0, 4.0, 0.0]]
    probabilities = scorer.restored_probabilities(transformed, model(2))
    assert probabilities.shape == (2, 5)
    assert np.allclose(probabilities.sum(axis=1), 1.0)
    assert probabilities[1, 4] > probabilities[1, 0]


def test_score_restored_uses_fixed_alpha_prior_and_means() -> None:
    row = candidate()
    row["_matrix"] = [1.0, 2.0]
    saved_transform = transform(2)
    saved_transform["feature_order"] = ["a", "b"]
    artifacts = {
        "transform": saved_transform,
        "model": model(2),
        "calibration": {"selected_alpha": 0.3, "formula": "(1-alpha)*p_model+alpha*p_train_prior"},
    }
    scorer.score_restored([row], "CATEGORY30", "_matrix", ["a", "b"], artifacts, np.full(5, 0.2), means())
    assert len(row["_p_CATEGORY30"]) == 5
    assert sum(row["_p_CATEGORY30"]) == pytest.approx(1.0)
    assert row["_ev_CATEGORY30_adverse"] == pytest.approx(row["_ev_CATEGORY30_base"])
    artifacts["calibration"]["selected_alpha"] = 0.4
    with pytest.raises(scorer.FrozenScoringError, match="frozen alpha"):
        scorer.score_restored([row], "CATEGORY30", "_matrix", ["a", "b"], artifacts, np.full(5, 0.2), means())


def test_join_requires_full_context_coverage_and_never_filters_candidates() -> None:
    rows = [candidate()]
    names = [f"c{index}" for index in range(81)]
    context_rows, coverage_rows = [], []
    for ticker in scorer.TICKERS:
        for index in range(55):
            date = f"202607{index + 1:02d}" if index < 9 else f"202608{index - 8:02d}"
            item = {"ticker": ticker, "date": date, "status": "CONTEXT_MISSING_SOURCE", "state_valid": None, "context_81": None}
            context_rows.append(item)
            coverage_rows.append({"ticker": ticker, "date": date})
    context_rows[0]["date"] = "20260701"
    coverage_rows[0]["date"] = "20260701"
    scorer.join_context(rows, context_rows, {"feature_names": names, "rows": coverage_rows})
    assert len(rows) == 1 and rows[0]["_context_status"] == "CONTEXT_MISSING_SOURCE"
    with pytest.raises(scorer.FrozenScoringError, match="coverage identities"):
        scorer.join_context(rows, context_rows[:-1], {"feature_names": names, "rows": coverage_rows})


def test_replay_produces_six_books_and_base_identity() -> None:
    replay = scorer.import_replay()
    row = candidate()
    for model_name in scorer.MODELS:
        row[f"_ev_{model_name}_base"] = 1.0
        row[f"_ev_{model_name}_adverse"] = 1.0
    coverage = {"rows": []}
    for day in ("20260701", "20260702"):
        for ticker in scorer.TICKERS:
            coverage["rows"].append({"ticker": ticker, "entry_date": day, "status": "NO_SERIES", "reason": "NO_SERIES"})
    books = {
        model_name: replay.replay_pair(scorer.prepare_rows([row], model_name), coverage, ["20260701", "20260702"], "20260701", "EV_TOP1_H2")
        for model_name in scorer.MODELS
    }
    assert set(books) == set(scorer.MODELS)
    assert sum(len(value) for model_books in books.values() for value in model_books.values()) > 0
    for cost in scorer.COSTS:
        assert books["BASE18_FROZEN"][cost] == books["CATEGORY30"][cost] == books["CONTEXT182"][cost]


def test_bootstrap_uses_all_180_candidates_and_fixed_55_sessions() -> None:
    sessions = [f"d{index:02d}" for index in range(55)]
    rows = []
    for index in range(180):
        row = {"entry_date": sessions[index % 55], "scenario": 0, "_p_BASE18_FROZEN": [0.5, 0.125, 0.125, 0.125, 0.125], "_p_CONTEXT182": [0.4, 0.15, 0.15, 0.15, 0.15]}
        rows.append(row)
    result = scorer.paired_bootstrap(rows, sessions, resamples=25)
    assert result["estimate"] == pytest.approx(-np.log(0.5) + np.log(0.4))
    assert result["sessions"] == 55 and result["resamples"] == 25
    assert sum(item["candidate_count"] for item in result["paired_daily_contributions"]) == 180


def test_revalidate_detects_payload_mutation(tmp_path: Path) -> None:
    authority, payload = tmp_path / "authority.json", tmp_path / "payload.json"
    authority.write_text("{}\n", encoding="utf-8")
    payload.write_text("{}\n", encoding="utf-8")
    snapshots = {"authority": {"path": str(authority), **scorer.pin(authority)}}
    payloads = {payload: scorer.pin(payload)}
    scorer.revalidate(snapshots, payloads)
    payload.write_text('{"changed":true}\n', encoding="utf-8")
    with pytest.raises(scorer.FrozenScoringError, match="closing payload"):
        scorer.revalidate(snapshots, payloads)


def test_module_contains_no_fit_or_sklearn_and_cli_is_explicit() -> None:
    source = Path(scorer.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
    assert not any(name.startswith("sklearn") for name in imported)
    calls = [node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
    assert "fit" not in calls and "fit_transform" not in calls
    assert "--execute-reviewed-scoring" in source
    assert "immutable output exists" in source
