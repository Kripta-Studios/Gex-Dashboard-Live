from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

import audit_weekly_context_models as auditor


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate(
    candidate_id: str = "SPY:20260105:20260109:CALL", right: str = "CALL"
) -> dict:
    features = {name: float(index + 1) for index, name in enumerate(auditor.FEATURE18)}
    features.update(
        ticker_SPY=1.0,
        ticker_QQQ=0.0,
        ticker_SPXW=0.0,
        right_call=float(right == "CALL"),
        weekday=0.0,
    )
    return {
        "candidate_id": candidate_id,
        "ticker": "SPY",
        "right": right,
        "entry_date": "20260105",
        "exit_date": "20260107",
        "expiration": "20260109",
        "label_available_at": "2026-01-07T10:35:00-05:00",
        "scenario": 3,
        "payoff_is_lower_bound": False,
        "decision_ask": 1.0,
        "entry_ask": 1.0,
        "exit_bid": 1.5,
        "entry_debit_base": 102.3,
        "entry_debit_adverse": 103.3,
        "net_base": 45.4,
        "net_adverse": 43.4,
        "status": "OBSERVED_EXIT",
        "features": features,
    }


def saved_transform(values: np.ndarray, names: list[str]) -> dict:
    value = auditor.independently_recompute_transform(values)
    indices = value["indicator_indices"]
    return {
        "feature_order": names,
        "missing_indicator_source_indices": indices,
        "missing_indicator_order": [f"{names[index]}__missing" for index in indices],
        "medians": value["medians"].tolist(),
        "scaler_mean": value["mean"].tolist(),
        "scaler_scale": value["scale"].tolist(),
        "fit_scope": "TRAIN_ONLY",
        "imputer": {
            "strategy": "median",
            "add_indicator": True,
            "keep_empty_features": True,
        },
    }


def zero_model(width: int) -> dict:
    return {
        "type": "LogisticRegression",
        "sklearn_version": "fixture",
        "C": 1.0,
        "solver": "lbfgs",
        "max_iter": 2000,
        "random_state": 0,
        "classes_present": [0, 1, 2, 3, 4],
        "classes_full": [0, 1, 2, 3, 4],
        "coefficient": np.zeros((5, width)).tolist(),
        "intercept": np.zeros(5).tolist(),
        "fit_scope": "TRAIN_ONLY",
        "fit_warnings": [],
    }


def test_category30_and_context182_are_independent_and_causal() -> None:
    row = candidate()
    category = auditor.category30(row)
    assert len(category) == 30 and sum(category) == 1 and category[0] == 1
    feature_names = [f"c{i}" for i in range(81)]
    available = {
        "status": "CONTEXT_AVAILABLE",
        "state_valid": True,
        "context_81": [float(i) for i in range(81)],
    }
    context = auditor.context182(row, available)
    assert len(context) == 182 and context[18:99] == [float(i) for i in range(81)]
    assert context[99:180] == [float(i) for i in range(81)] and context[-2:] == [
        1.0,
        1.0,
    ]
    put = candidate("SPY:20260105:20260109:PUT", "PUT")
    assert auditor.context182(put, available)[99:180] == [-float(i) for i in range(81)]
    invalid = auditor.context182(
        row,
        {"status": "CONTEXT_AVAILABLE", "state_valid": False, "context_81": [9.0] * 81},
    )
    missing = auditor.context182(
        row,
        {"status": "CONTEXT_MISSING_SOURCE", "state_valid": None, "context_81": None},
    )
    assert invalid[18:180] == [0.0] * 162 and invalid[-2:] == [1.0, 0.0]
    assert missing[18:180] == [0.0] * 162 and missing[-2:] == [0.0, 0.0]
    assert len(auditor.context_names(feature_names)) == 182


def test_join_rejects_duplicate_or_missing_context() -> None:
    rows = [candidate()]
    context = {
        "ticker": "SPY",
        "date": "20260105",
        "status": "CONTEXT_MISSING_SOURCE",
        "state_valid": None,
        "context_81": None,
    }
    coverage = {"ticker": "SPY", "date": "20260105"}
    auditor.join_context(rows, [context], [coverage])
    assert len(rows[0]["_x_category"]) == 30 and len(rows[0]["_x_context"]) == 182
    with pytest.raises(auditor.AuditError, match="duplicate"):
        auditor.join_context([candidate()], [context, context], [coverage])


def test_transform_recomputed_from_train_and_saved_application() -> None:
    train = np.asarray([[1.0, np.nan, np.nan], [3.0, 4.0, np.nan], [5.0, 8.0, np.nan]])
    names = ["a", "b", "empty"]
    saved = saved_transform(train, names)
    auditor.validate_transform(train, names, saved)
    transformed = auditor.apply_saved_transform(np.asarray([[3.0, np.nan, 9.0]]), saved)
    assert transformed.shape == (1, 5) and np.isfinite(transformed).all()
    broken = dict(saved)
    broken["medians"] = [99.0, 4.0, 0.0]
    with pytest.raises(auditor.AuditError, match="medians"):
        auditor.validate_transform(train, names, broken)


def test_scaler_uses_float64_variance_error_bound_for_near_constants() -> None:
    count = 1752
    constant_decimal = np.full(count, 0.1, dtype=np.float64)
    near_constant = np.full(count, 1e12, dtype=np.float64)
    near_constant[::2] -= 0.1
    near_constant[1::2] += 0.1
    distinguishable = np.full(count, 1e12, dtype=np.float64)
    distinguishable[::2] -= 1.0
    distinguishable[1::2] += 1.0
    train = np.column_stack([constant_decimal, near_constant, distinguishable])
    rebuilt = auditor.independently_recompute_transform(train)
    assert rebuilt["scale"][0] == 1.0
    assert rebuilt["scale"][1] == 1.0
    assert 0.0 < rebuilt["scale"][2] < 1.0
    saved = saved_transform(train, ["constant_0_1", "near", "distinguishable"])
    auditor.validate_transform(
        train, ["constant_0_1", "near", "distinguishable"], saved
    )


def test_coefficients_calibration_and_old_means_without_fit() -> None:
    rows = []
    for split in ("TRAIN", "CAL"):
        for label in range(5):
            row = candidate(f"SPY:{split}:{label}:CALL")
            row.update(_split=split, _model_label_eligible=True, scenario=label)
            row["_x"] = [float(label), math.nan if label == 0 else float(label)]
            rows.append(row)
    train = np.asarray([row["_x"] for row in rows if row["_split"] == "TRAIN"])
    transform = saved_transform(train, ["x", "maybe"])
    model = zero_model(len(transform["scaler_mean"]))
    calibration = {
        "formula": "(1-alpha)*p_model+alpha*p_train_prior",
        "selected_alpha": 0.0,
        "scores": [{"alpha": step / 10, "log_loss": math.log(5)} for step in range(11)],
    }
    prior = np.full(5, 0.2)
    means = {
        "cells": {
            cost: {
                "SPY:CALL": {str(label): {"mean_y": label / 10} for label in range(5)}
            }
            for cost in auditor.COSTS
        }
    }
    auditor.audit_saved_model(
        rows,
        "CATEGORY30",
        "_x",
        ["x", "maybe"],
        transform,
        model,
        calibration,
        prior,
        means,
    )
    assert all(np.allclose(row["_p_CATEGORY30"], np.full(5, 0.2)) for row in rows)
    assert all(math.isclose(row["_ev_CATEGORY30_base"], 20.0) for row in rows)


def test_direct_risk_replay_uses_decision_quantity_and_shared_books() -> None:
    row = candidate()
    row["_ev_base"], row["_ev_adverse"] = 10.0, 9.0
    sessions = ["20260105", "20260106", "20260107"]
    coverage = [
        {
            "ticker": ticker,
            "entry_date": day,
            "status": "CANDIDATES_BUILT"
            if ticker == "SPY" and day == "20260105"
            else "NO_SERIES",
            "reason": None if ticker == "SPY" and day == "20260105" else "NO_SERIES",
        }
        for day in sessions
        for ticker in auditor.TICKERS
    ]
    ledgers = auditor.replay_risk([row], coverage, sessions, "20260105")
    for cost in auditor.COSTS:
        entries = [event for event in ledgers[cost] if event["event"] == "ENTRY"]
        exits = [event for event in ledgers[cost] if event["event"] == "EXIT"]
        assert len(entries) == len(exits) == 1
        assert entries[0][
            "quantity"
        ] == auditor.BUDGET_CENTS // auditor.unit_risk_cents(1.0)
        assert exits[0]["net_usd"] == entries[0]["quantity"] * row[f"net_{cost}"]
    assert auditor.direct_select([{**row, "_ev_adverse": 0.0}]) == (
        None,
        "EV_NOT_POSITIVE",
    )


def test_bootstrap_is_exactly_seeded_and_type7() -> None:
    sessions = ["20260105", "20260106", "20260107"]
    rows = []
    for index, day in enumerate(sessions):
        row = candidate(f"SPY:{day}:x:CALL")
        row["entry_date"] = day
        row["scenario"] = index
        row["_model_label_eligible"] = True
        base = np.full(5, 0.2)
        context = np.full(5, 0.1)
        context[index] = 0.6
        context /= context.sum()
        row["_p_BASE18_FROZEN"], row["_p_CONTEXT182"] = base.tolist(), context.tolist()
        rows.append(row)
    first = auditor.paired_bootstrap(
        rows, sessions, resamples=100, seed=20261101, block=2
    )
    second = auditor.paired_bootstrap(
        rows, sessions, resamples=100, seed=20261101, block=2
    )
    assert first == second and first["resamples"] == 100
    assert auditor.percentile_type7([0.0, 10.0], 0.25) == 2.5


def test_full_artifact_restore_scores_books_and_metrics_without_fit() -> None:
    rows = []
    split_dates = {"TRAIN": "20230103", "CAL": "20250106", "EVAL": "20260105"}
    for split, day in split_dates.items():
        for label in range(5):
            row = candidate(f"SPY:{day}:100{label}:CALL")
            row.update(
                entry_date=day,
                exit_date={"TRAIN": "20230105", "CAL": "20250108", "EVAL": "20260107"}[
                    split
                ],
                expiration={"TRAIN": "20230106", "CAL": "20250110", "EVAL": "20260109"}[
                    split
                ],
                label_available_at={
                    "TRAIN": "2023-01-05T10:35:00-05:00",
                    "CAL": "2025-01-08T10:35:00-05:00",
                    "EVAL": "2026-01-07T10:35:00-05:00",
                }[split],
                scenario=label,
            )
            rows.append(row)
    names = [f"ctx_{index}" for index in range(81)]
    contexts = [
        {
            "ticker": "SPY",
            "date": day,
            "status": "CONTEXT_AVAILABLE",
            "state_valid": True,
            "context_81": [0.0] * 81,
        }
        for day in split_dates.values()
    ]
    context_coverage = [{"ticker": "SPY", "date": day} for day in split_dates.values()]
    prepared = copy.deepcopy(rows)
    auditor.join_context(prepared, contexts, context_coverage)
    splits = auditor.split_rows(prepared)
    prior = np.full(5, 0.2)
    means = {
        "cells": {
            cost: {
                f"{ticker}:{right}": {str(label): {"mean_y": 0.0} for label in range(5)}
                for ticker in auditor.TICKERS
                for right in auditor.RIGHTS
            }
            for cost in auditor.COSTS
        }
    }
    artifacts = {}
    for model, key, feature_names in (
        ("CATEGORY30", "_x_category", auditor.category_names()),
        ("CONTEXT182", "_x_context", auditor.context_names(names)),
    ):
        train = np.asarray([row[key] for row in splits["TRAIN"]], dtype=float)
        transform = saved_transform(train, feature_names)
        artifacts[model] = {
            "transform": transform,
            "model": zero_model(len(transform["scaler_mean"])),
            "calibration": {
                "formula": "(1-alpha)*p_model+alpha*p_train_prior",
                "selected_alpha": 0.0,
                "scores": [
                    {"alpha": step / 10, "log_loss": math.log(5)} for step in range(11)
                ],
            },
        }
        auditor.audit_saved_model(
            prepared,
            model,
            key,
            feature_names,
            artifacts[model]["transform"],
            artifacts[model]["model"],
            artifacts[model]["calibration"],
            prior,
            means,
        )
    frozen_scores = [
        {
            "candidate_id": row["candidate_id"],
            "scenario": row["scenario"],
            "label_eligible": True,
            "p_cal": prior.tolist(),
            "ev_base": 0.0,
            "ev_adverse": 0.0,
        }
        for row in rows
    ]
    producer_scores = [
        {
            "candidate_id": row["candidate_id"],
            "split": split,
            "scenario": row["scenario"],
            "payoff_is_lower_bound": row["payoff_is_lower_bound"],
            "context_status": row["_context_status"],
            "context_state_valid": row["_context_state_valid"],
            **{f"p_{model.lower()}": prior.tolist() for model in auditor.MODELS},
            **{
                f"ev_{model.lower()}_{cost}": 0.0
                for model in auditor.MODELS
                for cost in auditor.COSTS
            },
        }
        for split, values in splits.items()
        for row in values
    ]
    auditor.compare_scores(prepared, producer_scores, frozen_scores)
    sessions = ["20260105", "20260106", "20260107"]
    coverage = [
        {
            "ticker": ticker,
            "entry_date": day,
            "status": "CANDIDATES_BUILT"
            if ticker == "SPY" and day == "20260105"
            else "NO_SERIES",
            "reason": None if ticker == "SPY" and day == "20260105" else "NO_SERIES",
        }
        for day in sessions
        for ticker in auditor.TICKERS
    ]
    books = {
        model: auditor.replay_risk(
            auditor._prepare_replay_rows(splits["EVAL"], model),
            coverage,
            sessions,
            "20260105",
        )
        for model in auditor.MODELS
    }
    rebuilt = auditor.independently_rebuild_summary(
        prepared,
        splits,
        books,
        sessions,
        bootstrap_resamples=100,
        expected_eval_eligible=5,
    )
    summary = {
        **rebuilt,
        "schema": "weekly_h2_context_model_comparison_v1",
        "status": "COMPLETE_SEEN_DEVELOPMENT_DESCRIPTIVE",
        "fit_count": 2,
        "new_fits": ["CATEGORY30", "CONTEXT182"],
        "base18_refit": False,
        "flags": {
            "development_seen": True,
            "promotion_approved": False,
            "technical_ready": False,
            "q3_used": False,
            "raw_or_api_used": False,
        },
    }
    result = auditor.audit_numeric_bundle(
        candidates=rows,
        context_rows=contexts,
        context_coverage_rows=context_coverage,
        context_feature_names=names,
        frozen_scores=frozen_scores,
        frozen_model={"train_prior": prior.tolist()},
        means=means,
        artifacts=artifacts,
        producer_scores=producer_scores,
        producer_ledgers=books,
        frozen_baseline_ledgers=books["BASE18_FROZEN"],
        coverage_rows=coverage,
        sessions=sessions,
        last_entry="20260105",
        producer_summary=summary,
        expected_counts={"total": 15, "TRAIN": 5, "CAL": 5, "EVAL": 5},
        bootstrap_resamples=100,
    )
    assert result["status"] == "PASS_INDEPENDENT_NUMERIC_AUDIT_FIXTURES_ONLY"
    broken = copy.deepcopy(summary)
    broken["models"]["CONTEXT182"]["probability_all"]["log_loss"] += 0.01
    with pytest.raises(auditor.AuditError, match="summary.models.CONTEXT182"):
        auditor.audit_numeric_bundle(
            candidates=rows,
            context_rows=contexts,
            context_coverage_rows=context_coverage,
            context_feature_names=names,
            frozen_scores=frozen_scores,
            frozen_model={"train_prior": prior.tolist()},
            means=means,
            artifacts=artifacts,
            producer_scores=producer_scores,
            producer_ledgers=books,
            frozen_baseline_ledgers=books["BASE18_FROZEN"],
            coverage_rows=coverage,
            sessions=sessions,
            last_entry="20260105",
            producer_summary=broken,
            expected_counts={"total": 15, "TRAIN": 5, "CAL": 5, "EVAL": 5},
            bootstrap_resamples=100,
        )


def test_metadata_admission_and_closing_rehash_every_authority(tmp_path: Path) -> None:
    root = tmp_path / "comparison"
    root.mkdir()
    for name in auditor.EXPECTED_OUTPUTS:
        (root / name).write_text(f"fixture:{name}\n", encoding="utf-8")
    producer = tmp_path / auditor.PRODUCER_NAME
    producer.write_text("# reviewed fixture\n", encoding="utf-8")
    consumed = tmp_path / "consumed.json"
    consumed.write_text("{}\n", encoding="utf-8")
    external_paths = {}
    external_shas = {}
    for name in ("dataset", "frozen_eval", "context", "risk"):
        path = tmp_path / f"{name}_manifest.json"
        path.write_text(json.dumps({"name": name}) + "\n", encoding="utf-8")
        external_paths[name] = path
        external_shas[name] = sha256(path)
    manifest = {
        "schema": "weekly_h2_context_model_comparison_manifest_v1",
        "external_manifests": external_shas,
        "consumed_payloads": {str(consumed): auditor.file_pin(consumed)},
        "implementation": {
            auditor.PRODUCER_NAME: sha256(producer),
            auditor.EVALUATOR_NAME: auditor.EVALUATOR_SHA256,
            auditor.REPLAY_NAME: auditor.REPLAY_SHA256,
            auditor.CONTRACT.name: auditor.CONTRACT_SHA256,
        },
        "outputs": {
            name: auditor.file_pin(root / name) for name in auditor.EXPECTED_OUTPUTS
        },
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    admission = auditor.admit_comparison_package(
        comparison_root=root,
        comparison_manifest_sha256=sha256(manifest_path),
        external_manifest_paths=external_paths,
        expected_external_sha256=external_shas,
        producer_path=producer,
        producer_sha256=sha256(producer),
    )
    auditor.revalidate_comparison_package(admission)
    consumed.write_text("[]\n", encoding="utf-8")
    with pytest.raises(auditor.AuditError, match="closing consumed"):
        auditor.revalidate_comparison_package(admission)
