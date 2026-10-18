"""Synthetic control conversion, authority, chronology and recovery checks."""

from types import SimpleNamespace
from pathlib import Path
import shutil

import numpy as np
import pytest
import torch

import evaluate_tcn_row_mixed as module


def make_control(tmp_path, period="validation", empty=False):
    control = tmp_path / "flags"
    folder = control / period
    folder.mkdir(parents=True)
    name = "SPY_20250102.npz" if period == "validation" else "SPY_20260102.npz"
    source = folder / name
    ids = np.array([], dtype=np.int64) if empty else np.array([8, 3], dtype=np.int64)
    scores = np.array([], dtype=np.float64) if empty else np.array([2.25, -7.5])
    np.savez_compressed(
        source, action_ids=ids, control=np.ones(len(ids)) * 999, variant=scores
    )
    sidecar = source.with_suffix(".json")
    module.flags.atomic_json(
        sidecar,
        {
            "files": {str(source): module.flags.sha(source)},
            "feature_files": {},
            "oracle_files": {},
        },
    )
    module.flags.atomic_json(
        folder / "prediction_manifest.json", {sidecar.name: module.flags.sha(sidecar)}
    )
    out = tmp_path / "evaluation"
    out.mkdir(exist_ok=True)
    return control, out, source, ids, scores


@pytest.mark.parametrize("empty", [False, True])
def test_adapter_exact_flag_variant_and_resumes(tmp_path, empty):
    control, out, source, ids, scores = make_control(tmp_path, empty=empty)
    root = module.adapt_control_period(control, out, "validation", {source.name})
    target = root / "validation" / source.name
    before = module.flags.sha(target)
    with np.load(target) as data:
        assert set(data.files) == {"action_ids", "tcn_teacher"}
        np.testing.assert_array_equal(data["action_ids"], ids)
        np.testing.assert_array_equal(data["tcn_teacher"], scores)
        assert data["tcn_teacher"].dtype == scores.dtype
    module.adapt_control_period(control, out, "validation", {source.name})
    assert module.flags.sha(target) == before
    lineage = module.flags.read_json(root / "validation/adapter_lineage.json")
    assert lineage["days"][source.name]["source_sha256"] == module.flags.sha(source)


def test_test_adapter_requires_existing_valid_freeze(tmp_path):
    control, out, source, _, _ = make_control(tmp_path, "test")
    with pytest.raises(ValueError, match="before validation freeze"):
        module.adapt_control_period(control, out, "test", {source.name})
    assert not (out / "control_adapter").exists()
    authority = out / "authority"
    authority.write_text("original")
    module.flags.atomic_json(
        out / "freeze.json", {"files": {str(authority): module.flags.sha(authority)}}
    )
    authority.write_text("changed")
    with pytest.raises(ValueError, match="Changed bound source"):
        module.adapt_control_period(control, out, "test", {source.name})


def test_adapter_detects_source_and_adapted_mutations(tmp_path):
    control, out, source, ids, _ = make_control(tmp_path)
    root = module.adapt_control_period(control, out, "validation", {source.name})
    adapted = root / "validation" / source.name
    np.savez_compressed(adapted, action_ids=ids, tcn_teacher=np.array([99.0, 99.0]))
    with pytest.raises(ValueError, match="differs from FLAGS64"):
        module.adapt_control_period(control, out, "validation", {source.name})
    np.savez_compressed(source, action_ids=ids, variant=np.array([9.0, 9.0]))
    with pytest.raises(ValueError, match="not bound"):
        module.adapt_control_period(control, out, "validation", {source.name})


def test_adapter_exact_calendar_universe(tmp_path):
    control, out, source, _, _ = make_control(tmp_path)
    with pytest.raises(ValueError, match="universe"):
        module.adapt_control_period(
            control, out, "validation", {source.name, "QQQ_20250102.npz"}
        )


def test_null_gate_finish_recovery_preserves_all_six_policies(tmp_path):
    out = tmp_path
    module.flags.atomic_json(out / "freeze.json", {"files": {}})
    test = {
        p: {"pooled": {"base_net_usd": 0.0, "adverse_net_usd": 0.0}}
        for p in module.flags.POLICIES
    }
    selection = {"selected_policy": None, "diagnostic_best_not_approved": "control__0"}
    original = SimpleNamespace(
        economic_gate=lambda *_: pytest.fail("No economic selection for null")
    )
    store = SimpleNamespace(hashes={})
    seal = SimpleNamespace(recheck=lambda: None)
    module.finish(out, {"files": {}}, selection, test, original, store, seal)
    completion = module.flags.sha(out / "completion.json")
    module.finish(out, {"files": {}}, selection, test, original, store, seal)
    assert module.flags.sha(out / "completion.json") == completion
    summary = module.flags.read_json(out / "summary.json")
    assert summary["selected_test"] is None
    assert summary["gate"]["passes"] is False
    assert set(summary["test"]) == set(module.flags.POLICIES)


def test_snapshot_partial_preserved(tmp_path):
    source, target = tmp_path / "source", tmp_path / "copy"
    source.write_bytes(b"exact")
    target.with_name("copy.partial").write_bytes(b"incomplete")
    module.copy_exact(source, target)
    assert target.read_bytes() == b"exact"
    assert any(
        p.read_bytes() == b"incomplete"
        for p in (tmp_path / "recovery").rglob("copy.partial")
    )
    source.write_bytes(b"mutated")
    with pytest.raises(ValueError, match="Snapshot differs"):
        module.copy_exact(source, target)


def test_synthetic_e2e_binding_freeze_and_complete_resume(tmp_path, monkeypatch):
    control, out, val_source, _, _ = make_control(tmp_path)
    _, _, test_source, _, _ = make_control(tmp_path, "test")
    training_root = tmp_path / "training"
    training_root.mkdir()
    root_identity = {
        "files": {},
        "learner_root": str(tmp_path / "learner"),
        "engine_root": str(tmp_path / "engine"),
        "feature_root": str(tmp_path / "features"),
    }
    module.flags.atomic_json(control / "identity.json", root_identity)
    module.flags.atomic_json(
        control / "normalizers.json",
        {"features": {}, "risk_scales_usd": {t: 1.0 for t in module.flags.TICKERS}},
    )
    module.flags.atomic_json(control / "feature_schema.json", {})
    (control / "training_sample.parquet").write_bytes(b"synthetic-authority")
    (control / "expected_full_calendar.csv").write_text("date\n20250102\n20260102\n")
    for name in ("summary.json", "freeze.json", "evaluation_runtime_completion.json"):
        module.flags.atomic_json(control / name, {})
    module.flags.atomic_json(control / "completion.json", {"files": {}})
    audit_binding = {"root": str(control)}
    for name, key in (
        ("summary.json", "summary_sha256"),
        ("completion.json", "completion_sha256"),
        ("freeze.json", "freeze_sha256"),
        ("validation/prediction_manifest.json", "validation_manifest_sha256"),
        ("test/prediction_manifest.json", "test_manifest_sha256"),
        ("evaluation_runtime_completion.json", "compatibility_completion_sha256"),
    ):
        audit_binding[key] = module.flags.sha(control / name)
    audit_path = tmp_path / "audit.json"
    module.flags.atomic_json(
        audit_path,
        {
            "status": "PASS_INDEPENDENT_TCN_FLAGS_ECONOMIC_AUDIT",
            "binding": audit_binding,
        },
    )
    monkeypatch.setattr(module, "CONTROL_AUDIT_SHA", module.flags.sha(audit_path))
    shutil.copyfile(
        Path(module.__file__).with_name("run_tcn_row_mixed.py"),
        training_root / "run_tcn_row_mixed.executed.py",
    )
    torch.save(
        {"epoch": 4, "config": {}, "state_dict": {}}, training_root / "tcn_variant.pt"
    )
    module.flags.atomic_json(
        training_root / "training_complete.json",
        {
            "binding": {
                "files": {},
                "variant": "row_mixed_original_batch_sizes",
                "device": "cpu",
            },
            "model_sha256": module.flags.sha(training_root / "tcn_variant.pt"),
        },
    )
    module.flags.atomic_json(
        training_root / "cache_complete.json",
        {
            "flags_root": str(control),
            "files": {
                str(control / name): module.flags.sha(control / name)
                for name in (
                    "normalizers.json",
                    "feature_schema.json",
                    "training_sample.parquet",
                )
            },
        },
    )
    days = [
        SimpleNamespace(ticker="SPY", date="20250102"),
        SimpleNamespace(ticker="SPY", date="20260102"),
    ]
    seal = SimpleNamespace(hashes={}, recheck=lambda: None)
    store = SimpleNamespace(hashes={})
    original = SimpleNamespace(
        discover_days=lambda *_: days,
        SourceSeal=lambda *_: seal,
        FeatureStore=lambda *a, **k: store,
        LevelTCN=torch.nn.Module,
        economic_gate=lambda *_: pytest.fail("null cannot approve"),
    )
    monkeypatch.setattr(module.flags, "load_original", lambda _: original)
    monkeypatch.setattr(module.flags, "CheckedStore", lambda value, _: value)
    order = []

    def period(*args):
        output, adapter, label = args[6], args[7], args[8]
        order.append(label)
        assert (output / "freeze.json").exists() == (label == "test")
        source = val_source if label == "validation" else test_source
        with np.load(adapter / label / source.name) as adapted:
            np.testing.assert_array_equal(adapted["tcn_teacher"], [2.25, -7.5])
        folder = output / label
        folder.mkdir()
        summaries = {
            p: {
                "daily_gate": {"passes": False},
                "pooled": {"base_net_usd": 0.0, "adverse_net_usd": 0.0},
                "tickers": {t: {"base_net_usd": 0.0} for t in module.flags.TICKERS},
            }
            for p in module.flags.POLICIES
        }
        module.flags.atomic_json(folder / "summary.json", summaries)
        return summaries

    monkeypatch.setattr(module.flags, "evaluate_period", period)
    args = SimpleNamespace(
        output=out,
        training_root=training_root,
        flags_root=control,
        control_audit=audit_path,
    )
    module.evaluate(args)
    assert order == ["validation", "test"]
    completed = module.flags.sha(out / "completion.json")
    module.evaluate(args)
    assert order == ["validation", "test"]
    assert module.flags.sha(out / "completion.json") == completed
    frozen = module.flags.read_json(out / "freeze.json")
    assert frozen["selection"]["selected_policy"] is None
    assert all(
        "control_adapter/test" not in path.replace("\\", "/")
        for path in frozen["files"]
    )
    assert str(val_source) in frozen["files"]
    assert str(test_source) in module.flags.read_json(out / "completion.json")["files"]
    test_source.write_bytes(b"mutation-after-completion")
    with pytest.raises(ValueError, match="Changed bound source"):
        module.evaluate(args)
