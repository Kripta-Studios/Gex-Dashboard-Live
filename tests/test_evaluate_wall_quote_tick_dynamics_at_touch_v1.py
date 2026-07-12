import json
import pandas as pd
import pytest

from neural.jepa import evaluate_wall_quote_tick_dynamics_at_touch_v1 as module


def test_frozen_feature_and_gate_contract():
    assert module.raw_feature_names("F0") == list(module.CONTROL_FEATURES)
    assert module.raw_feature_names("F1") == [
        *module.CONTROL_FEATURES,
        *module.QDYN_FEATURES,
    ]
    assert len(module.QDYN_FEATURES) == 28
    assert not set(module.feature_names("F1")).intersection(
        module.QDYN_QUALITY_FIELDS
    )
    assert module.GATE_SPEC["planned_paired_cells"] == 24
    assert module.GATE_SPEC["maximum_wilcoxon_one_sided_p"] == 0.0125
    assert module.GATE_SPEC["primary_horizons"] == [30, 60]


def test_evaluate_cells_uses_identical_qdyn_complete_cases(monkeypatch, tmp_path):
    observed = {}

    def fake(frame, model_dir):
        observed["valid"] = frame["qsize_both_valid"].tolist()
        observed["features"] = tuple(module.shared.QSIZE_FEATURES)
        return (pd.DataFrame(),) * 6

    monkeypatch.setattr(module.shared, "evaluate_cells", fake)
    frame = pd.DataFrame({"qdyn_both_valid": [True, False, True]})
    module.evaluate_cells(frame, tmp_path)
    assert observed["valid"] == [True, False, True]
    assert observed["features"] == tuple(module.QDYN_FEATURES)


def test_verify_freeze_rejects_non_pass_data_gate(tmp_path):
    dataset = tmp_path / "dataset.bin"
    labels = tmp_path / "labels.csv"
    qdyn = tmp_path / "qdyn.csv"
    for path in (dataset, labels, qdyn):
        path.write_bytes(b"x")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema": "wall_quote_tick_dynamics_at_touch_dataset_v1r1r1",
        "status": "REJECTED_DATA_GATE",
    }), encoding="utf-8")
    freeze = tmp_path / "freeze.json"
    freeze.write_text(json.dumps({
        "schema": "wall_quote_tick_dynamics_at_touch_frozen_runner_v1r1r1",
        "status": "PREEXECUTION_FROZEN",
        "inputs": {
            "dataset": {"sha256": module.sha256_file(dataset)},
            "label_source_hashes": {"sha256": module.sha256_file(labels)},
            "qdyn_source_hashes": {"sha256": module.sha256_file(qdyn)},
            "data_manifest": {"sha256": module.sha256_file(manifest)},
        },
    }), encoding="utf-8")
    with pytest.raises(AssertionError, match="data gate/hash is not PASS"):
        module.verify_freeze(freeze, dataset, labels, qdyn, manifest)


def test_summary_reports_qdyn_complete_case(monkeypatch):
    monkeypatch.setattr(module.shared, "summarize_gate", lambda *args: {
        "complete_case_pairing": "qsize_both_valid",
        "physical_mechanism_pass": False,
    })
    result = module.summarize_gate(
        pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "CONDITIONAL", "BLOCKED"
    )
    assert result["complete_case_pairing"] == "qdyn_both_valid"
    assert result["physical_mechanism_pass"] is False
