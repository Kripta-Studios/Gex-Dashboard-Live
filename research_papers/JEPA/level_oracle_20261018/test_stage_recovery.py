"""Technical recovery fixtures only: no historical market fit or evaluation."""

import importlib.util
import json
from pathlib import Path
import sys
import subprocess
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


s = load("stage_recovery")
r = load("recover_learners")
m = load("train_models")


def test_completed_gbts_never_refit(tmp_path):
    def forbidden(**_kwargs):
        raise AssertionError("Completed model was refitted")

    producer = SimpleNamespace(
        train_gbts=m.train_gbts,
        SEED=m.SEED,
        lgb=SimpleNamespace(LGBMRegressor=forbidden),
        write_json=m.write_json,
    )
    sample = pd.DataFrame({"ticker": ["SPY"]})
    r.fit_missing_gbts(
        producer, None, sample, {"SPY": 10}, tmp_path, ["gbt_net", "gbt_advantage"]
    )
    assert r.read(tmp_path / "gbt_config.json")["n_estimators"] == 200


def test_only_missing_gbt_fits_exact_target_weights(tmp_path):
    calls = []

    class Model:
        def __init__(self, **kwargs):
            self.booster_ = self
            assert kwargs == r.gbt_config(m)

        def fit(self, x, target, sample_weight):
            calls.append((x.copy(), target.copy(), sample_weight.copy()))

        def save_model(self, path):
            Path(path).write_text("synthetic complete model")

    producer = SimpleNamespace(
        train_gbts=m.train_gbts,
        SEED=m.SEED,
        lgb=SimpleNamespace(LGBMRegressor=Model),
        write_json=m.write_json,
    )
    sample = pd.DataFrame(
        {"ticker": ["SPY", "SPY"], "dp_advantage": [20.0, -10.0], "weight": [1.5, 0.5]}
    )
    r.fit_missing_gbts(
        producer, np.ones((2, 3)), sample, {"SPY": 10}, tmp_path, ["gbt_net"]
    )
    assert len(calls) == 1
    np.testing.assert_array_equal(calls[0][1], [2, -1])
    np.testing.assert_array_equal(calls[0][2], [1.5, 0.5])
    assert not (tmp_path / "gbt_net.txt").exists()


def test_cpu_checkpoint_exact_order_global_numpy_optimizer_and_epoch4(tmp_path):
    torch.manual_seed(12)
    np.random.seed(13)
    rng = np.random.default_rng(14)
    model = torch.nn.Linear(2, 1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.01)
    source = tmp_path / "input"
    source.write_text("immutable")
    binding = {"files": {str(source): s.sha(source)}, "device": "cpu"}

    def step(network, optim, generator):
        order = generator.permutation(8)
        x = torch.randn(8, 2)[order]
        y = torch.tensor(np.random.normal(size=(8, 1)), dtype=torch.float32)
        optim.zero_grad()
        (network(x) - y).square().sum().backward()
        optim.step()
        return order

    step(model, optimizer, rng)
    path = tmp_path / "tcn_epoch04.pt"
    history = [{"epoch": i, "summed_fixed_batch_loss": float(i)} for i in range(1, 5)]
    m.save_epoch_checkpoint(path, model, optimizer, rng, 4, history, binding)
    expected_order = step(model, optimizer, rng)
    expected = {k: v.clone() for k, v in model.state_dict().items()}
    restored = torch.nn.Linear(2, 1)
    optim2 = torch.optim.AdamW(restored.parameters(), lr=0.01)
    rng2 = np.random.default_rng(999)
    assert s.validate_epoch_pair(path)["epoch"] == 4
    epoch, _ = m.restore_epoch_checkpoint(path, restored, optim2, rng2, binding)
    assert list(range(epoch, m.EPOCHS)) == []  # completed epoch4 adds no training
    np.testing.assert_array_equal(step(restored, optim2, rng2), expected_order)
    assert all(torch.equal(expected[k], v) for k, v in restored.state_dict().items())
    # Later orphan/corrupt pairs cannot displace the last fully valid checkpoint.
    (tmp_path / "tcn_epoch05.pt").write_bytes(b"orphan")
    (tmp_path / "tcn_epoch06.pt").write_bytes(b"broken")
    (tmp_path / "tcn_epoch06.json").write_text("{")
    latest, rejected = r.latest_valid_epoch(tmp_path)
    assert latest == (4, path) and len(rejected) == 2
    assert (tmp_path / "tcn_epoch05.pt").exists()
    source.write_text("changed")
    with pytest.raises(ValueError, match="Changed"):
        s.validate_epoch_pair(path)


def test_preserve_partial_directory_hashes_and_reject_escape(tmp_path):
    output = tmp_path / "out"
    partial = output / "test"
    partial.mkdir(parents=True)
    (partial / "scores.npz").write_bytes(b"partial")
    archive = output / "recovery_attempts" / "one"
    r.preserve(partial, output, archive, "interrupted evaluation")
    assert (archive / "test" / "scores.npz").read_bytes() == b"partial"
    manifest = json.loads((archive / "test.preserved.json").read_text())
    assert manifest["hashes"]["test\\scores.npz"] == s.sha(
        archive / "test" / "scores.npz"
    )
    outside = tmp_path / "outside"
    outside.write_text("untouched")
    with pytest.raises(ValueError, match="within"):
        r.preserve(outside, output, archive, "invalid")
    assert outside.read_text() == "untouched"


def test_scientific_failure_not_technical_retry(tmp_path):
    (tmp_path / "stdout.log").write_text(
        "FloatingPointError: Nonfinite fixed neural loss"
    )
    with pytest.raises(ValueError, match="Scientific"):
        r.check_failure(tmp_path, "resource_exhaustion")
    with pytest.raises(ValueError, match="Only explicit"):
        r.check_failure(tmp_path, "unprofitable")


def test_atomic_snapshot_rejects_corruption_and_preserves_existing(tmp_path):
    source, target = tmp_path / "source", tmp_path / "snapshot"
    source.write_bytes(b"complete")
    assert s.atomic_copy(source, target) == s.sha(source)
    source.write_bytes(b"different")
    with pytest.raises(ValueError, match="different bytes"):
        s.atomic_copy(source, target)
    assert target.read_bytes() == b"complete"


def test_epoch4_actual_producer_exports_without_optimizer_update(tmp_path, monkeypatch):
    p = {
        "base": np.zeros((1, 3), np.float32),
        "tokens": np.zeros((1, 20, 4), np.float32),
        "maps": np.zeros((1, 20, 5, 64), np.float32),
        "action_features": np.zeros((1, 5), np.float32),
        "token_mask": np.ones((1, 20, 2), np.float32),
        "map_mask": np.ones((1, 20, 5), np.float32),
    }
    stats = {
        key: {"mean": [0.0] * width, "std": [1.0] * width}
        for key, width in (("base", 3), ("tokens", 4), ("maps", 5), ("action", 5))
    }
    model = m.LevelTCN(3, 4, 5, 2, 5)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
    binding = {
        "output_root": str(tmp_path.resolve()),
        "device": "cpu",
        "torch": torch.__version__,
        "numpy": np.__version__,
        "lightgbm": m.lgb.__version__,
        "files": {},
    }
    path = tmp_path / "tcn_epoch04.pt"
    history = [{"epoch": i, "summed_fixed_batch_loss": float(i)} for i in range(1, 5)]
    m.save_epoch_checkpoint(
        path, model, optimizer, np.random.default_rng(1), 4, history, binding
    )
    monkeypatch.setattr(m, "checkpoint_binding", lambda *_args: binding)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Epoch4 continuation attempted optimizer update")

    monkeypatch.setattr(torch.optim.AdamW, "step", forbidden)
    store = SimpleNamespace(
        hashes={}, rows=lambda *_args: (p, np.array([0]), np.array([0]))
    )
    sample = pd.DataFrame({"day_key": ["synthetic"], "action_id": [0]})
    m.train_tcn(sample, store, {}, stats, tmp_path, "cpu", path)
    exported = torch.load(tmp_path / "tcn_teacher.pt", weights_only=True)
    assert all(
        torch.equal(value, exported["state_dict"][key])
        for key, value in model.state_dict().items()
    )
    assert r.read(tmp_path / "neural_training.json")["epochs"] == history


def test_truncated_final_summary_is_partial_not_completed(tmp_path):
    path = tmp_path / "summary.json"
    assert r.summary_state(path) == "absent"
    path.write_text('{"status":')
    assert r.summary_state(path) == "partial"
    path.write_text('{"status":"COMPLETED_CAUSAL_LEARNER_DEVELOPMENT"}')
    assert r.summary_state(path) == "partial"
    s.atomic_json(
        path,
        {
            "status": "COMPLETED_CAUSAL_LEARNER_DEVELOPMENT",
            "selected_policy": {},
            "provisional_gate": {},
            "validation_choices": {},
            "risk_scales_usd": {},
        },
    )
    assert r.summary_state(path) == "complete"


def test_exclusive_os_lock_and_release_after_owner_exit(tmp_path):
    with r.output_lock(tmp_path):
        with pytest.raises(ValueError, match="already held"):
            with r.output_lock(tmp_path):
                pass
    # Exit without a context-manager cleanup: kernel must release the byte lock.
    code = (
        "import os,sys,msvcrt; from pathlib import Path; "
        "f=(Path(sys.argv[1])/'recovery.lock').open('r+b'); "
        "msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1); os._exit(0)"
    )
    subprocess.run([sys.executable, "-c", code, str(tmp_path)], check=True)
    with r.output_lock(tmp_path):
        pass


def test_partial_freeze_is_detected_without_reading_outcomes(tmp_path):
    path = tmp_path / "freeze.json"
    assert r.freeze_state(path) == "absent"
    path.write_text('{"artifacts":')
    assert r.freeze_state(path) == "partial"
    path.write_text("{}")
    assert r.freeze_state(path) == "partial"


def test_existing_test_requires_recoverable_freeze_even_when_file_absent(tmp_path):
    assert r.guard_freeze_authority(tmp_path) == "absent"
    (tmp_path / "test").mkdir()
    with pytest.raises(ValueError, match="cannot reconstruct"):
        r.guard_freeze_authority(tmp_path)
    (tmp_path / "freeze.json").write_text('{"artifacts":')
    with pytest.raises(ValueError, match="cannot reconstruct"):
        r.guard_freeze_authority(tmp_path)


def test_interrupted_atomic_copy_never_publishes_partial_target(tmp_path, monkeypatch):
    source, target = tmp_path / "source", tmp_path / "target"
    source.write_bytes(b"complete bytes")

    def broken_copy(_source, temporary):
        Path(temporary).write_bytes(b"partial")
        raise OSError("synthetic interrupted copy")

    monkeypatch.setattr(s.shutil, "copyfile", broken_copy)
    with pytest.raises(OSError, match="interrupted"):
        s.atomic_copy(source, target)
    assert not target.exists()
    partials = list(tmp_path.glob("target.partial-*"))
    assert len(partials) == 1 and partials[0].read_bytes() == b"partial"


@pytest.mark.parametrize("interrupted_period", ["validation", "test"])
def test_controller_replays_evaluation_without_refit_or_test_reselection(
    tmp_path, monkeypatch, interrupted_period
):
    """Full controller with deterministic producer doubles, no market data."""
    out, snapshots, runtime = (
        tmp_path / name for name in ("out", "snapshots", "runtime")
    )
    for path in (out, snapshots / "base", runtime):
        path.mkdir(parents=True)
    (runtime / "stdout.log").write_text("")
    s.atomic_json(snapshots / "environment.json", {"pid": 0, "environment": {}})
    s.atomic_json(
        snapshots / "base/manifest.json", {"output_root": str(out), "artifacts": {}}
    )
    base_sha = s.sha(snapshots / "base/manifest.json")
    s.atomic_json(
        out / "run_identity.json", {"oracle_audit": {}, "device": "cpu", "days": []}
    )
    s.atomic_json(
        out / "normalizers.json",
        {"risk_scales_usd": {"SPY": 10}, "features": {}, "gbt_columns": 3},
    )
    pd.DataFrame(
        {"ticker": ["SPY"], "day_key": ["synthetic"], "action_id": [0]}
    ).to_parquet(out / "training_sample.parquet")
    np.save(out / "train_x.npy", np.zeros((1, 3), np.float32))
    for name in s.MODELS:
        target = snapshots / name
        target.mkdir()
        (target / "model.txt").write_text(name + " complete immutable")
        s.atomic_json(
            target / "manifest.json",
            {
                "status": "COMPLETE_GBT_SNAPSHOT",
                "base_manifest_sha256": base_sha,
                "model_sha256": s.sha(target / "model.txt"),
            },
        )
    epoch = out / "tcn_epoch04.pt"
    epoch.write_bytes(b"synthetic epoch4")
    s.atomic_json(epoch.with_suffix(".json"), {"binding": {"files": {}}})
    final = snapshots / "final_models"
    final.mkdir()
    (final / "tcn_teacher.pt").write_bytes(b"synthetic frozen model")
    s.atomic_json(final / "neural_training.json", {"epochs": [1, 2, 3, 4]})
    m.write_json(final / "gbt_config.json", r.gbt_config(m))
    s.atomic_json(
        final / "manifest.json",
        {
            "status": "COMPLETE_FINAL_MODEL_SNAPSHOT",
            "base_manifest_sha256": base_sha,
            "environment_sha256": s.sha(snapshots / "environment.json"),
            "epoch4_sha256": s.sha(epoch),
            "artifacts": {p.name: s.sha(p) for p in final.iterdir()},
        },
    )
    monkeypatch.setattr(r, "ensure_stopped", lambda *_args: None)
    monkeypatch.setattr(r, "fingerprint", lambda: {})
    monkeypatch.setattr(r, "latest_valid_epoch", lambda _out: ((4, epoch), []))
    calls = {"fit": 0, "train": 0, "select": 0, "periods": []}

    def forbidden_fit(**_kwargs):
        calls["fit"] += 1
        raise AssertionError("refit complete GBT")

    def forbidden_train(*_args):
        calls["train"] += 1
        raise AssertionError("retrain complete TCN")

    def evaluate(_days, _store, _models, _scales, _stats, root, period, *_rest):
        calls["periods"].append(period)
        target = root / period
        target.mkdir(exist_ok=False)
        # Same complete result as an uninterrupted deterministic producer;
        # the interrupted very-favorable ledger is never used for selection.
        (target / "ledger.json").write_text('[{"net":-3,"action":7}]')
        s.atomic_json(target / "prediction_hashes.json", {})
        s.atomic_json(target / "summary.json", {"P": {"base_net_usd": -3}})
        return {"P": {"base_net_usd": -3}}

    def select(_validation, _scales):
        calls["select"] += 1
        return {"policy": "P"}, [{"policy": "P"}]

    def freeze(root, selection, choices, _store, _audit):
        record = {
            "selected_policy": selection,
            "validation_choices": choices,
            "artifacts": {},
            "feature_sources": {},
            "oracle_audit": {},
            "script_sha256": "synthetic",
            "plan_sha256": "synthetic",
            "engine_sha256": "synthetic",
            "scheduler_sha256": "synthetic",
            "protocol_sha256": "synthetic",
        }
        s.atomic_json(root / "freeze.json", record)

    if interrupted_period == "test":
        (out / "validation").mkdir()
        s.atomic_json(out / "validation/prediction_hashes.json", {})
        s.atomic_json(out / "oracle_sources_before_test.json", {})
        freeze(out, {"policy": "P"}, [{"policy": "P"}], None, None)
    partial = out / interrupted_period
    partial.mkdir()
    (partial / "ledger.json").write_text('[{"net":999999999}]')
    seal = SimpleNamespace(hashes={}, check=lambda *_args: None, recheck=lambda: None)
    store = SimpleNamespace(hashes={})
    producer = SimpleNamespace(
        SEED=m.SEED,
        EPOCHS=4,
        train_gbts=m.train_gbts,
        lgb=SimpleNamespace(
            LGBMRegressor=forbidden_fit,
            Booster=lambda **_kwargs: SimpleNamespace(
                num_trees=lambda: 200, num_feature=lambda: 3
            ),
        ),
        require_oracle_pass=lambda *_args: {},
        discover_days=lambda *_args: [],
        verify_full_coverage=lambda *_args: None,
        SourceSeal=lambda *_args: seal,
        FeatureStore=lambda *_args, **_kwargs: store,
        pd=pd,
        np=np,
        write_json=m.write_json,
        train_tcn=forbidden_train,
        load_predictors=lambda *_args: {},
        import_sibling=lambda *_args: None,
        evaluate_period=evaluate,
        select_policy=select,
        freeze=freeze,
        verify_freeze=lambda root: r.read(root / "freeze.json"),
        economic_gate=lambda *_args: {"passes": False},
    )
    monkeypatch.setitem(sys.modules, "train_models", producer)
    args = SimpleNamespace(
        output=out,
        recovery=snapshots,
        runtime=runtime,
        reason="process_interruption",
        oracle_audit=tmp_path / "audit",
        oracle_root=tmp_path,
        feature_root=tmp_path,
        device="cpu",
    )
    r.continue_run(args)
    assert calls["fit"] == calls["train"] == 0
    assert calls["select"] == (1 if interrupted_period == "validation" else 0)
    assert calls["periods"] == (
        ["validation", "test"] if interrupted_period == "validation" else ["test"]
    )
    assert r.read(out / "summary.json")["selected_policy"] == {"policy": "P"}
    assert (out / "test/ledger.json").read_text() == '[{"net":-3,"action":7}]'
    archived = list(
        (out / "recovery_attempts").glob("*/" + interrupted_period + "/ledger.json")
    )
    assert len(archived) == 1 and "999999999" in archived[0].read_text()
