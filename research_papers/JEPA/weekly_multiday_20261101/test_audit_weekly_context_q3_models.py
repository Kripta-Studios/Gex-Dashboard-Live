from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import numpy as np
import pytest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("q3_model_audit", HERE / "audit_weekly_context_q3_models.py")
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
HELPER = audit.import_helper()


def feature18(weekday: int, right: str) -> dict:
    values = {name: float(index + 1) for index, name in enumerate(HELPER.FEATURE18)}
    values["weekday"] = weekday
    values["right_call"] = float(right == "CALL")
    return values


def candidate(candidate_id: str, right: str, scenario: int) -> dict:
    ask, exit_bid = 1.0, 1.4
    return {
        "candidate_id": candidate_id, "ticker": "SPY", "entry_date": "20260701",
        "exit_date": "20260706", "right": right, "features": feature18(2, right),
        "scenario": scenario, "decision_ask": ask, "entry_ask": ask, "exit_bid": exit_bid,
        "status": "OBSERVED_EXIT", "payoff_is_lower_bound": False,
        "entry_debit_base": (ask + 0.01) * 100 + 1.30,
        "entry_debit_adverse": (ask + 0.02) * 100 + 1.30,
        "net_base": (exit_bid - 0.01 - ask - 0.01) * 100 - 2.60,
        "net_adverse": (exit_bid - 0.02 - ask - 0.02) * 100 - 2.60,
    }


def context_rows() -> tuple[list[dict], list[dict], list[str]]:
    names = [f"b{index}" for index in range(81)]
    context = [{"ticker": "SPY", "date": "20260701", "status": "CONTEXT_AVAILABLE", "state_valid": True, "context_81": [float(index) / 100 for index in range(81)]}]
    coverage = [{"ticker": "SPY", "date": "20260701", "status": "CONTEXT_AVAILABLE", "state_valid": True}]
    return context, coverage, names


def transform(names: list[str]) -> dict:
    width = len(names)
    return {
        "feature_order": names, "fit_scope": "TRAIN_ONLY", "medians": [0.0] * width,
        "missing_indicator_source_indices": [], "scaler_mean": [0.0] * width,
        "scaler_scale": [1.0] * width,
    }


def model(width: int) -> dict:
    negative = [-4.0] + [0.0] * (width - 1)
    positive = [4.0] + [0.0] * (width - 1)
    return {
        "type": "LogisticRegression", "fit_scope": "TRAIN_ONLY", "C": 1.0,
        "solver": "lbfgs", "max_iter": 2000, "random_state": 0,
        "classes_full": list(range(5)), "classes_present": [0, 1],
        "sklearn_version": "fixture", "fit_warnings": [],
        "coefficient": [negative, positive], "intercept": [0.0, 0.0],
    }


def means() -> dict:
    return {
        "cells": {
            cost: {
                f"{ticker}:{right}": {str(label): {"mean_y": float(label + 1), "n": 1} for label in range(5)}
                for ticker in HELPER.TICKERS for right in HELPER.RIGHTS
            } for cost in audit.COSTS
        }
    }


def artifacts(names30: list[str], names182: list[str]) -> dict:
    return {
        "CATEGORY30": {"transform": transform(names30), "model": model(30), "calibration": {"formula": "(1-alpha)*p_model+alpha*p_train_prior", "selected_alpha": 0.3}},
        "CONTEXT182": {"transform": transform(names182), "model": model(182), "calibration": {"formula": "(1-alpha)*p_model+alpha*p_train_prior", "selected_alpha": 0.6}},
    }


def coverage_fixture() -> tuple[list[dict], list[str]]:
    sessions = ["20260701", "20260702", "20260706"]
    rows = []
    for ticker in HELPER.TICKERS:
        for day in sessions:
            ids = ["c", "p"] if ticker == "SPY" and day == sessions[0] else []
            rows.append({"ticker": ticker, "entry_date": day, "candidate_ids": ids, "status": "CANDIDATES_BUILT" if ids else "NO_SERIES", "reason": None if ids else "NO_1_TO_8_DTE_SERIES_ALLOWING_H2"})
    return rows, sessions


def make_bundle() -> dict:
    candidates = [candidate("c", "CALL", 0), candidate("p", "PUT", 1)]
    candidates[1]["decision_ask"] = 1.1
    contexts, context_coverage, names = context_rows()
    work = copy.deepcopy(candidates)
    HELPER.join_context(work, contexts, context_coverage)
    for row in work:
        row["_model_label_eligible"], row["_split"] = True, audit.SPLIT
        row["_x_category"] = HELPER.category30(row)
    prior = np.asarray([0.5, 0.5, 0, 0, 0], dtype=float)
    saved = artifacts(HELPER.category_names(), HELPER.context_names(names))
    base_scores = []
    for index, row in enumerate(work):
        probability = [0.6, 0.4, 0, 0, 0] if index == 0 else [0.3, 0.7, 0, 0, 0]
        row["_p_BASE18_FROZEN"] = probability
        base_scores.append({"candidate_id": row["candidate_id"], "split": audit.SPLIT, "scenario": row["scenario"], "payoff_is_lower_bound": False, "p_cal": probability, "ev_base": 0.0, "ev_adverse": 0.0})
        row["_ev_BASE18_FROZEN_base"] = row["_ev_BASE18_FROZEN_adverse"] = 0.0
    audit.load_saved_probabilities(HELPER, work, "CATEGORY30", "_x_category", HELPER.category_names(), saved["CATEGORY30"], prior, means(), 0.3)
    audit.load_saved_probabilities(HELPER, work, "CONTEXT182", "_x_context", HELPER.context_names(names), saved["CONTEXT182"], prior, means(), 0.6)
    producer_scores = [{
        "candidate_id": row["candidate_id"], "split": audit.SPLIT, "scenario": row["scenario"],
        "payoff_is_lower_bound": False, "context_status": row["_context_status"],
        "context_state_valid": row["_context_state_valid"],
        **{f"p_{name.lower()}": row[f"_p_{name}"] for name in audit.MODELS},
        **{f"ev_{name.lower()}_{cost}": row[f"_ev_{name}_{cost}"] for name in audit.MODELS for cost in audit.COSTS},
    } for row in work]
    coverage_rows, sessions = coverage_fixture()
    books = {name: HELPER.replay_risk(audit.prepare_replay_rows(work, name), coverage_rows, sessions, sessions[-1]) for name in audit.MODELS}
    controls = {"source": "fixture", "books": {}}
    summary = audit.rebuild_summary(HELPER, work, books, sessions, controls, 20)
    return {
        "candidates": candidates, "context_rows": contexts, "context_coverage_rows": context_coverage,
        "feature_names": names, "base_scores": base_scores, "prior": prior, "means": means(),
        "artifacts": saved, "producer_scores": producer_scores, "producer_ledgers": books,
        "baseline_ledgers": books["BASE18_FROZEN"], "coverage_rows": coverage_rows,
        "sessions": sessions, "producer_summary": summary, "controls": controls,
        "expected_count": 2, "bootstrap_resamples": 20,
    }


def test_significant_negative_parameters_are_applied_not_clipped() -> None:
    rows = [{"ticker": "SPY", "right": "CALL", "decision_ask": 1.0, "_x": [1.0]}]
    saved = {"transform": transform(["x"]), "model": model(1), "calibration": {"formula": "(1-alpha)*p_model+alpha*p_train_prior", "selected_alpha": 0.3}}
    audit.load_saved_probabilities(HELPER, rows, "CATEGORY30", "_x", ["x"], saved, np.asarray([0.5, 0.5, 0, 0, 0]), means(), 0.3)
    assert rows[0]["_p_CATEGORY30"][1] > 0.8
    assert rows[0]["_p_CATEGORY30"][0] < 0.2


def test_artificial_numeric_bundle_passes_without_fit() -> None:
    result = audit.audit_numeric_bundle(HELPER, **make_bundle())
    assert result["status"] == "PASS_INDEPENDENT_Q3_CONTEXT_MODEL_NUMERIC_AUDIT"
    assert result["fit_performed"] is False


def test_score_drift_is_detected() -> None:
    bundle = make_bundle()
    bundle["producer_scores"][0]["p_context182"][0] += 0.01
    with pytest.raises(audit.Q3ModelAuditError, match="score drift probability"):
        audit.audit_numeric_bundle(HELPER, **bundle)


def test_ledger_drift_is_detected() -> None:
    bundle = make_bundle()
    ledger = bundle["producer_ledgers"]["CONTEXT182"]["adverse"]
    exit_row = next(row for row in ledger if row["event"] == "EXIT")
    exit_row["net_usd"] += 1.0
    with pytest.raises(HELPER.AuditError, match="ledger CONTEXT182:adverse"):
        audit.audit_numeric_bundle(HELPER, **bundle)


def test_source_mutation_fails_closing_revalidation(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    payload = tmp_path / "payload.json"
    manifest.write_text("{}\n", encoding="utf-8")
    payload.write_text("{}\n", encoding="utf-8")
    snapshots = {"fixture": {"path": str(manifest.resolve()), **audit.pin(manifest)}}
    payloads = {payload.resolve(): audit.pin(payload)}
    audit.revalidate(snapshots, payloads)
    payload.write_text('{"changed":true}\n', encoding="utf-8")
    with pytest.raises(audit.Q3ModelAuditError, match="pin closing payload"):
        audit.revalidate(snapshots, payloads)


def test_bootstrap_q3_uses_55_sessions_11_blocks_and_all_180() -> None:
    sessions = [f"2026{index:04d}" for index in range(55)]
    rows = []
    for index in range(180):
        rows.append({
            "entry_date": sessions[index % 55], "scenario": 0,
            "_model_label_eligible": True,
            "_p_BASE18_FROZEN": [0.5, 0.5, 0, 0, 0],
            "_p_CONTEXT182": [0.6, 0.4, 0, 0, 0],
        })
    first = HELPER.paired_bootstrap(rows, sessions, resamples=100, expected_eligible=180)
    second = HELPER.paired_bootstrap(rows, sessions, resamples=100, expected_eligible=180)
    assert first == second and first["sessions"] == 55 and first["block_sessions"] == 5
    assert sum(row["candidate_count"] for row in first["paired_daily_contributions"]) == 180


def test_no_fit_and_no_scorer_import_static() -> None:
    source = (HERE / "audit_weekly_context_q3_models.py").read_text(encoding="utf-8")
    assert ".fit(" not in source
    assert "spec_from_file_location(\"score" not in source
    assert "import score_weekly_context_q3_frozen" not in source
    assert "audit_saved_model(" not in source and "split_rows(" not in source


def test_producer_manifest_source_authority_rejects_wrong_scorer() -> None:
    snapshots = {name: {"bytes": 1, "sha256": name} for name in (*audit.FIXED_MANIFESTS, "context", "context_audit", "producer")}
    paths = {Path("x"): {"bytes": 1, "sha256": "x"}}
    manifest = {
        "schema": "weekly_h2_context_model_comparison_q3_manifest_v1",
        "status": "COMPLETE_Q3_PARTIAL_2026_SEEN_DEVELOPMENT",
        "external_authorities": {name: {"bytes": value["bytes"], "sha256": value["sha256"]} for name, value in snapshots.items() if name != "producer"},
        "consumed_payloads": {str(path): value for path, value in paths.items()},
        "implementation": {
            audit.SCORER.name: "wrong", audit.CONTRACT.name: audit.CONTRACT_SHA256,
            "replay_equal_risk_frozen.py": audit.REPLAY_SHA256,
        },
        "flags": {
            "development_seen": True, "fit_performed": False,
            "promotion_approved": False, "q3_used": True,
            "raw_or_api_used": False, "recalibration_performed": False,
            "technical_ready": False,
        },
    }
    with pytest.raises(audit.Q3ModelAuditError, match="implementation pins"):
        audit.validate_producer_manifest(manifest, snapshots, "expected", paths)
