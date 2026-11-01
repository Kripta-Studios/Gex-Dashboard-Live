from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

import score_weekly_h2_q3_partial_frozen as scorer


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def frozen_fixture(root: Path, monkeypatch) -> str:
    root.mkdir()
    transform = {
        "feature_order": list(scorer.FEATURES),
        "missing_indicator_source_indices": [13],
        "missing_indicator_order": ["implied_vol__missing"],
        "medians": [0.0] * 18,
        "scaler_mean": [0.0] * 19,
        "scaler_scale": [1.0] * 19,
        "fit_scope": "TRAIN_ONLY",
    }
    model = {
        "fit_scope": "TRAIN_ONLY",
        "classes_present": list(range(5)),
        "classes_full": list(range(5)),
        "coefficient": [[0.0] * 19 for _ in range(5)],
        "intercept": [0.0] * 5,
        "train_prior": [0.2] * 5,
    }
    means = {"shrinkage": 20, "cells": {cost: {} for cost in scorer.COSTS}}
    for cost in scorer.COSTS:
        for ticker in scorer.TICKERS:
            for right in scorer.RIGHTS:
                means["cells"][cost][f"{ticker}:{right}"] = {
                    str(label): {"n": 1, "mean_y": 0.01 * label} for label in range(5)
                }
    grid = {
        "selected_alpha": 0.3,
        "scores": [{"alpha": index / 10, "log_loss": 1.0} for index in range(11)],
    }
    values = {
        "transform.json": transform,
        "model.json": model,
        "conditional_means.json": means,
        "calibration_grid.json": grid,
    }
    for name, value in values.items():
        write_json(root / name, value)
    frozen = {name: sha(root / name) for name in values}
    manifest = {
        "schema": "weekly_h2_ev_manifest_v1",
        "outputs": {
            name: {"bytes": (root / name).stat().st_size, "sha256": digest}
            for name, digest in frozen.items()
        },
    }
    write_json(root / "manifest.json", manifest)
    manifest_sha = sha(root / "manifest.json")
    monkeypatch.setattr(scorer, "FROZEN", frozen)
    monkeypatch.setattr(scorer, "H1_EVALUATION_MANIFEST_SHA256", manifest_sha)
    return manifest_sha


def candidate(entry_date: str = "20260701") -> dict:
    features = {name: 0.0 for name in scorer.FEATURES}
    features.update(
        ticker_SPY=1.0,
        right_call=1.0,
        dte=6.0,
        weekday=2.0,
        spot=100.0,
        strike=100.0,
        bid=0.8,
        ask=1.0,
        spread_relative=0.2,
        delta=0.5,
        implied_vol=None,
    )
    return {
        "candidate_id": f"SPY:{entry_date}:20260707:CALL",
        "ticker": "SPY",
        "entry_date": entry_date,
        "exit_date": "20260706",
        "expiration": "20260707",
        "strike": 100.0,
        "right": "CALL",
        "features": features,
        "decision_ask": 1.0,
        "entry_ask": None,
        "exit_bid": None,
        "status": "NO_FILL",
        "label_available_at": "2026-07-01T10:35:00-04:00",
        "scenario": 0,
        "net_base": 0.0,
        "net_adverse": 0.0,
        "entry_debit_base": 0.0,
        "entry_debit_adverse": 0.0,
        "payoff_is_lower_bound": False,
        "source_pins": {},
    }


def dataset_fixture(
    root: Path, frozen: dict[str, str], manifest_sha: str, row: dict
) -> str:
    root.mkdir()
    write_json(root / "inventory.json", {"schema": "weekly_h2_q3_partial_inventory_v1"})
    write_json(root / "inventory_manifest.json", {"status": "PASS_SYNTHETIC"})
    (root / "candidates.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    calendar = [
        {"ticker": ticker, "date": date, "close_i": 390}
        for date in scorer.SESSIONS
        for ticker in scorer.TICKERS
    ]
    coverage_rows = []
    for date in scorer.SESSIONS:
        for ticker in scorer.TICKERS:
            is_candidate = date == "20260701" and ticker == "SPY"
            terminal = date in {"20260916", "20260917"}
            coverage_rows.append(
                {
                    "ticker": ticker,
                    "entry_date": date,
                    "status": "CANDIDATES_BUILT"
                    if is_candidate
                    else ("HORIZON_OUTSIDE_CALENDAR" if terminal else "NO_SERIES"),
                    "reason": None
                    if is_candidate
                    else ("NO_OFFICIAL_H2" if terminal else "NO_SERIES"),
                    "candidate_ids": [row["candidate_id"]] if is_candidate else [],
                }
            )
    write_json(
        root / "coverage.json",
        {
            "schema": "weekly_h2_q3_partial_coverage_v1",
            "calendar": calendar,
            "rows": coverage_rows,
            "clock_files": [],
        },
    )
    files = {
        name: {"bytes": (root / name).stat().st_size, "sha256": sha(root / name)}
        for name in (
            "candidates.jsonl",
            "coverage.json",
            "inventory.json",
            "inventory_manifest.json",
        )
    }
    pins = {
        "contract": scorer.CONTRACT_SHA256,
        "wrapper": scorer.WRAPPER_SHA256,
        "builder": scorer.BUILDER_SHA256,
        "source_pilot": scorer.SOURCE_PILOT_SHA256,
        "h2_contract": scorer.H2_CONTRACT_SHA256,
        "clock_amendment": scorer.CLOCK_AMENDMENT_SHA256,
        "evaluator": scorer.EVALUATOR_SHA256,
        "h1_dataset_manifest": scorer.H1_DATASET_MANIFEST_SHA256,
        "calendar_json": scorer.CALENDAR_JSON_SHA256,
        "calendar_parquet": scorer.CALENDAR_PARQUET_SHA256,
        "calendar_manifest": scorer.CALENDAR_MANIFEST_SHA256,
        "h1_manifest": manifest_sha,
    }
    pins.update(
        {f"frozen_{index}": value for index, value in enumerate(frozen.values())}
    )
    manifest = {
        "schema": "weekly_h2_q3_partial_dataset_manifest_v1",
        "status": "COMPLETE_WEEKLY_H2_Q3_PARTIAL_DATASET_NOT_EVALUATED",
        "split": scorer.SPLIT,
        "flags": {
            "no_fit": True,
            "no_refit": True,
            "no_recalibration": True,
            "no_selection": True,
            "not_oos": True,
            "not_promotion": True,
            "not_technical_readiness": True,
        },
        "files": files,
        "calendar_pin": {
            "session_count": 55,
            "ticker_count": 3,
            "row_count": 165,
            "first_date": scorer.FIRST_DATE,
            "last_date": scorer.LAST_DATE,
            "last_eligible_entry": scorer.LAST_ENTRY,
        },
        "implementation_pins": pins,
    }
    write_json(root / "manifest.json", manifest)
    return sha(root / "manifest.json")


def test_source_has_no_fit_calls() -> None:
    tree = ast.parse(Path(scorer.__file__).read_text(encoding="utf-8"))
    calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert "fit" not in calls
    assert "fit_transform" not in calls


def test_full_synthetic_frozen_scoring_happy_path(tmp_path, monkeypatch) -> None:
    frozen_root = tmp_path / "frozen"
    frozen_manifest = frozen_fixture(frozen_root, monkeypatch)
    dataset_root = tmp_path / "dataset"
    dataset_manifest = dataset_fixture(
        dataset_root, scorer.FROZEN, frozen_manifest, candidate()
    )
    output = tmp_path / "output"
    result = scorer.run(
        dataset_root, dataset_manifest, frozen_root, frozen_manifest, output
    )
    assert result["status"] == "COMPLETE_EXTENSION_PARTIAL_SEEN_DEVELOPMENT"
    assert len(list(output.glob("ledger_*.jsonl"))) == 8
    assert result["fit_performed"] is False


def test_mutated_frozen_artifact_is_rejected(tmp_path, monkeypatch) -> None:
    frozen_root = tmp_path / "frozen"
    manifest_sha = frozen_fixture(frozen_root, monkeypatch)
    (frozen_root / "model.json").write_text("{}", encoding="utf-8")
    with pytest.raises(scorer.ScoringError, match="frozen artifact model.json"):
        scorer.load_frozen(frozen_root, manifest_sha)


def test_candidate_date_leak_is_rejected(tmp_path, monkeypatch) -> None:
    frozen_root = tmp_path / "frozen"
    frozen_manifest = frozen_fixture(frozen_root, monkeypatch)
    dataset_root = tmp_path / "dataset"
    leaked = candidate("20260916")
    dataset_manifest = dataset_fixture(
        dataset_root, scorer.FROZEN, frozen_manifest, leaked
    )
    with pytest.raises(scorer.ScoringError, match="candidate date leak"):
        scorer.run(
            dataset_root,
            dataset_manifest,
            frozen_root,
            frozen_manifest,
            tmp_path / "output",
        )
