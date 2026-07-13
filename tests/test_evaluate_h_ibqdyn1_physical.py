from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import neural.jepa.evaluate_h_ibqdyn1_physical as evaluator
import neural.jepa.freeze_h_ibqdyn1_physical_runner as freezer
from neural.jepa import evaluate_wall_quote_size_pressure_at_touch_v1 as shared
from neural.jepa.build_wall_quote_tick_dynamics_sidecar import sha256_file


def test_model_architecture_is_exact_and_small() -> None:
    assert len(evaluator.raw_feature_names("F0")) == 18
    assert len(evaluator.raw_feature_names("F1")) == 38
    assert len(evaluator.feature_names("F0")) == 26
    assert len(evaluator.feature_names("F1")) == 46
    assert evaluator.LR_PARAMS["penalty"] == "l2"
    assert evaluator.GATE_SPEC["maximum_wilcoxon_one_sided_p"] == 0.0125
    assert evaluator.LABEL_SPEC["touch_universe_bps"] == 20.0


def test_shared_adapter_is_scoped_and_restores_globals() -> None:
    original_features = shared.QSIZE_FEATURES
    original_specs = shared.WALL_SPECS
    with evaluator._shared_contract():
        assert shared.QSIZE_FEATURES == evaluator.ALPHA_FIELDS
        assert tuple(sorted(shared.WALL_SPECS)) == evaluator.LEVEL_IDENTITIES
        assert shared.feature_names("F1") == evaluator.feature_names("F1")
    assert shared.QSIZE_FEATURES is original_features
    assert shared.WALL_SPECS is original_specs


def test_closed_family_features_are_rejected() -> None:
    evaluator.assert_no_closed_features(list(evaluator.ALPHA_FIELDS))
    with pytest.raises(AssertionError, match="closed features"):
        evaluator.assert_no_closed_features([evaluator.QSIZE_FEATURES[0]])
    with pytest.raises(AssertionError, match="closed features"):
        evaluator.assert_no_closed_features([evaluator.CLOSED_QDYN_FEATURES[0]])


def test_physical_pass_alone_authorizes_research_payoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        shared,
        "summarize_gate",
        lambda *_args, **_kwargs: {
            "physical_mechanism_pass": True,
            "advance_to_option_payoff": False,
            "production_live_ready": False,
        },
    )
    result = evaluator.summarize_gate(
        pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "CONDITIONAL", "BLOCKED"
    )
    assert result["research_payoff_authorized"]
    assert result["advance_to_option_payoff"]
    assert not result["production_live_ready"]
    assert result["complete_case_pairing"] == "ibqdyn_both_valid"


def test_strict_data_manifest_rejects_failed_gate(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.bin"
    source = tmp_path / "source.csv"
    dataset.write_bytes(b"dataset")
    source.write_bytes(b"source")
    manifest = {
        "schema": "h_ibqdyn1_outcome_free_dataset_v1",
        "status": "PASS_DATA_GATE",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "errors": [],
        "rows": evaluator.EXPECTED_EVENTS,
        "eligible_events": 16_852,
        "dataset_sha256": sha256_file(dataset),
        "source_inventory_sha256": sha256_file(source),
        "data_gate": {
            "rows_preserved": True,
            "coverage_pass": True,
            "distinctness_pass": False,
            "control_coverage_pass": True,
            "identical_complete_case_pass": True,
            "passed": False,
        },
    }
    with pytest.raises(AssertionError, match="strict PASS"):
        evaluator._strict_data_manifest(manifest, dataset, source)


def test_freezer_cannot_run_without_complete_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "dataset.parquet"
    label = tmp_path / "labels.csv"
    source = tmp_path / "contracts.csv"
    manifest_path = tmp_path / "manifest.json"
    dataset.write_bytes(b"dataset")
    label.write_text("x\n", encoding="utf-8")
    source.write_text("x\n", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "schema": "h_ibqdyn1_outcome_free_dataset_v1",
                "status": "REJECTED_DATA_GATE",
                "outcome_free": True,
                "holdout_2026_used": False,
                "production_modified": False,
                "errors": [],
                "rows": freezer.EXPECTED_EVENTS,
                "dataset_sha256": sha256_file(dataset),
                "source_inventory_sha256": sha256_file(source),
                "data_gate": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(freezer, "tracked_clean", lambda *_args: "a" * 64)
    monkeypatch.setattr(freezer, "assert_source_inventory", lambda *_args: None)
    monkeypatch.setattr(
        freezer, "assert_contract_source_inventory", lambda *_args: None
    )
    with pytest.raises(AssertionError, match="failed H-IBQDYN1 data gate"):
        freezer.build_frozen_payload(dataset, label, source, manifest_path)


def test_freezer_emits_preexecution_contract_only_after_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "dataset.parquet"
    label = tmp_path / "labels.csv"
    source = tmp_path / "contracts.csv"
    manifest_path = tmp_path / "manifest.json"
    dataset.write_bytes(b"dataset")
    label.write_text("x\n", encoding="utf-8")
    source.write_text("x\n", encoding="utf-8")
    gate = {
        "rows_preserved": True,
        "coverage_pass": True,
        "distinctness_pass": True,
        "control_coverage_pass": True,
        "identical_complete_case_pass": True,
        "passed": True,
    }
    manifest_path.write_text(
        json.dumps(
            {
                "schema": "h_ibqdyn1_outcome_free_dataset_v1",
                "status": "PASS_DATA_GATE",
                "outcome_free": True,
                "holdout_2026_used": False,
                "production_modified": False,
                "errors": [],
                "rows": freezer.EXPECTED_EVENTS,
                "dataset_sha256": sha256_file(dataset),
                "source_inventory_sha256": sha256_file(source),
                "data_gate": gate,
                "code_hashes": {},
                "runtime_lock_sha256": "lock",
                "runtime_environment_sha256": "environment",
                "control_feature_hash": freezer.hash_list(freezer.CONTROL_FEATURES),
                "alpha_feature_hash": freezer.hash_list(freezer.ALPHA_FIELDS),
                "quality_field_hash": freezer.hash_list(freezer.QUALITY_FIELDS),
                "historical_provenance": "CONDITIONAL_REMOTE_TERMINAL_RECONSTRUCTION",
                "live_parity": "BLOCKED",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(freezer, "tracked_clean", lambda *_args: "a" * 64)
    monkeypatch.setattr(freezer, "assert_source_inventory", lambda *_args: None)
    monkeypatch.setattr(
        freezer, "assert_contract_source_inventory", lambda *_args: None
    )
    monkeypatch.setattr(freezer, "CODE_CLOSURE", ())
    monkeypatch.setattr(freezer, "PROTOCOL_CLOSURE", ())
    monkeypatch.setattr(freezer, "BUILD_CODE_CLOSURE", ())
    monkeypatch.setattr(
        freezer,
        "assert_runtime_lock",
        lambda *_args: {
            "lock_sha256": "lock",
            "environment": {},
            "environment_sha256": "environment",
        },
    )
    monkeypatch.setattr(
        freezer.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="f" * 40),
    )
    payload = freezer.build_frozen_payload(dataset, label, source, manifest_path)
    assert payload["status"] == "PREEXECUTION_FROZEN"
    assert not payload["payoff_authorized_at_freeze"]
    assert payload["feature_names"]["F1"] == evaluator.feature_names("F1")
