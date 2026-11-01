from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import build_weekly_h2_q3_partial_extension as extension
import score_weekly_h2_q3_partial_frozen as scorer
from test_build_weekly_h2_dataset_v2 import quote, source_path, write_source


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


def calendar_fixture(tmp_path: Path) -> tuple[Path, str, Path, str]:
    rows = [
        {"ticker": ticker, "date": date, "close_i": 390}
        for ticker in extension.TICKERS
        for date in extension.DATES
    ]
    json_path = tmp_path / "calendar.json"
    write_json(
        json_path,
        {
            "schema": "weekly_h2_q3_partial_calendar_v1",
            "sessions": list(extension.DATES),
            "rows": rows,
        },
    )
    parquet_path = tmp_path / "calendar.parquet"
    pq.write_table(
        pa.table(
            {
                "ticker": [row["ticker"] for row in rows],
                "date": [row["date"] for row in rows],
                "close_i": [row["close_i"] for row in rows],
            }
        ),
        parquet_path,
    )
    return json_path, sha(json_path), parquet_path, sha(parquet_path)


def wrapped_dataset_fixture(tmp_path: Path, monkeypatch) -> tuple[Path, str]:
    source = tmp_path / "artificial_source"
    source.mkdir()
    entry_date, exit_date, expiration = "20260706", "20260708", "20260710"
    write_source(
        source_path(source, "SPY", expiration, entry_date),
        [
            quote("SPY", expiration, entry_date, "10:30", 500.0, "CALL", 1.8, 2.0, 0.50),
            quote("SPY", expiration, entry_date, "10:30", 500.0, "PUT", 1.9, 2.0, -0.50),
            quote("SPY", expiration, entry_date, "10:35", 500.0, "CALL", 1.9, 2.1, 0.49),
            quote("SPY", expiration, entry_date, "10:35", 500.0, "PUT", 1.8, 2.1, -0.49),
        ],
    )
    write_source(
        source_path(source, "SPY", expiration, exit_date),
        [
            quote("SPY", expiration, exit_date, "10:35", 500.0, "CALL", 2.8, 3.0, 0.60),
            quote("SPY", expiration, exit_date, "10:35", 500.0, "PUT", 1.0, 1.2, -0.30),
        ],
    )
    calendar_json, json_sha, calendar_parquet, parquet_sha = calendar_fixture(tmp_path)
    dataset = tmp_path / "dataset"
    wrapper_sha = sha(Path(extension.__file__))
    assert wrapper_sha == scorer.WRAPPER_SHA256
    assert extension.EXTENSION_CONTRACT_SHA256 == scorer.CONTRACT_SHA256
    extension.build_reviewed_inventory(
        source,
        calendar_json,
        json_sha,
        calendar_parquet,
        parquet_sha,
        dataset,
        wrapper_sha,
    )
    inventory = dataset / "inventory.json"
    extension.execute_reviewed_extension(
        source,
        calendar_json,
        json_sha,
        calendar_parquet,
        parquet_sha,
        dataset,
        wrapper_sha,
        inventory,
        sha(inventory),
    )
    monkeypatch.setattr(scorer, "CALENDAR_JSON_PATH", calendar_json)
    monkeypatch.setattr(scorer, "CALENDAR_JSON_SHA256", json_sha)
    monkeypatch.setattr(scorer, "CALENDAR_PARQUET_PATH", calendar_parquet)
    monkeypatch.setattr(scorer, "CALENDAR_PARQUET_SHA256", parquet_sha)
    return dataset, sha(dataset / "manifest.json")


def test_source_has_no_fit_calls() -> None:
    tree = ast.parse(Path(scorer.__file__).read_text(encoding="utf-8"))
    calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert "fit" not in calls
    assert "fit_transform" not in calls


def test_frozen_forward_weights_match_independent_manual_algebra() -> None:
    state = scorer.load_frozen(
        extension.FROZEN_STATE_ROOT,
        extension.FROZEN_STATE["h1_evaluation_manifest"][1],
    )
    raw = [0.0] * 18
    raw[0], raw[3], raw[4], raw[5] = 1.0, 1.0, 4.0, 0.0
    raw[6:13] = [500.0, 500.0, 0.0, 1.8, 2.0, 0.1, 0.5]
    raw[13:] = [0.2, 0.01, -0.02, 0.1, 0.03]
    for index in state["transform"]["missing_indicator_source_indices"]:
        raw[index] = None
    transformed = scorer.transform(raw, state["transform"])
    manual_expanded = [
        state["transform"]["medians"][index] if value is None else value
        for index, value in enumerate(raw)
    ] + [
        float(raw[index] is None)
        for index in state["transform"]["missing_indicator_source_indices"]
    ]
    manual_transformed = [
        (value - state["transform"]["scaler_mean"][index])
        / state["transform"]["scaler_scale"][index]
        for index, value in enumerate(manual_expanded)
    ]
    assert transformed == pytest.approx(manual_transformed, abs=1e-14)
    logits = [
        sum(weight * value for weight, value in zip(weights, manual_transformed))
        + state["model"]["intercept"][index]
        for index, weights in enumerate(state["model"]["coefficient"])
    ]
    maximum = max(logits)
    exponentials = [math.exp(value - maximum) for value in logits]
    expected = [value / sum(exponentials) for value in exponentials]
    assert scorer.probabilities(transformed, state["model"]) == pytest.approx(
        expected, abs=1e-14
    )


def test_full_synthetic_frozen_scoring_happy_path(tmp_path, monkeypatch) -> None:
    dataset_root, dataset_manifest = wrapped_dataset_fixture(tmp_path, monkeypatch)
    output = tmp_path / "output"
    result = scorer.run(
        dataset_root,
        dataset_manifest,
        extension.FROZEN_STATE_ROOT,
        extension.FROZEN_STATE["h1_evaluation_manifest"][1],
        output,
    )
    assert result["status"] == "COMPLETE_EXTENSION_PARTIAL_SEEN_DEVELOPMENT"
    assert len(list(output.glob("ledger_*.jsonl"))) == 8
    assert result["fit_performed"] is False
    candidates = (dataset_root / "candidates.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(candidates) == 2
    ledger = [
        json.loads(line)
        for line in (
            output
            / "ledger_always_call_h2_q3_partial_2026_seen_development_base.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert {row["event"] for row in ledger} >= {"ENTRY", "EXIT"}


def test_mutated_frozen_artifact_is_rejected(tmp_path, monkeypatch) -> None:
    frozen_root = tmp_path / "frozen"
    manifest_sha = frozen_fixture(frozen_root, monkeypatch)
    (frozen_root / "model.json").write_text("{}", encoding="utf-8")
    with pytest.raises(scorer.ScoringError, match="frozen artifact model.json"):
        scorer.load_frozen(frozen_root, manifest_sha)


def test_nested_implementation_pin_path_is_exact(tmp_path, monkeypatch) -> None:
    dataset_root, _ = wrapped_dataset_fixture(tmp_path, monkeypatch)
    manifest_path = dataset_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["implementation_pins"]["builder_v2"]["path"] += ".wrong"
    write_json(manifest_path, manifest)
    with pytest.raises(scorer.ScoringError, match="implementation frozen pins"):
        scorer.load_dataset(dataset_root, sha(manifest_path))


def test_candidate_date_leak_is_rejected(tmp_path, monkeypatch) -> None:
    dataset_root, _ = wrapped_dataset_fixture(tmp_path, monkeypatch)
    leaked = candidate("20260916")
    candidates = dataset_root / "candidates.jsonl"
    candidates.write_text(json.dumps(leaked) + "\n", encoding="utf-8")
    manifest_path = dataset_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["candidates.jsonl"] = {
        "bytes": candidates.stat().st_size,
        "sha256": sha(candidates),
    }
    write_json(manifest_path, manifest)
    dataset_manifest = sha(manifest_path)
    with pytest.raises(scorer.ScoringError, match="candidate date leak"):
        scorer.run(
            dataset_root,
            dataset_manifest,
            extension.FROZEN_STATE_ROOT,
            extension.FROZEN_STATE["h1_evaluation_manifest"][1],
            tmp_path / "output",
        )
