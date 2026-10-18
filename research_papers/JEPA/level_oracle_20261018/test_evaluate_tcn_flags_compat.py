"""Synthetic inference parity; no market values or fitting."""

from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pandas as pd
import pytest
import torch

sys.path.insert(0, str(Path(__file__).parent))
import run_tcn_flags as runner  # noqa: E402
import evaluate_tcn_flags_compat as compat  # noqa: E402


class ConstantGBT:
    def predict(self, x, num_threads):
        return np.zeros(len(x))


def test_exact_original_scores_batch_boundaries_duplicates_and_empty(tmp_path):
    original = runner.load_original(Path(__file__).parent)
    torch.set_num_threads(2)
    torch.manual_seed(123)
    torch.use_deterministic_algorithms(True)
    random = np.random.default_rng(45)
    states, count = 320, 1305
    pack = {
        "base": random.normal(size=(states, 2)).astype("f4"),
        "tokens": random.normal(size=(states, 20, 2)).astype("f4"),
        "maps": random.normal(size=(states, 20, 5, 64)).astype("f4"),
        "action_features": random.normal(size=(count, 2)).astype("f4"),
        "token_mask": np.ones((states, 20, 2), "f4"),
        "map_mask": np.ones((states, 20, 5), "f4"),
    }
    # Noncontiguous/repeated states, with >256 unique rows and >1024 actions.
    all_si = random.permutation(np.arange(count)) % 300
    order = random.permutation(count)
    actions = pd.DataFrame({"action_id": order, "state_i": all_si[order]})
    actions.to_parquet(tmp_path / "actions.parquet", index=False)
    day = SimpleNamespace(oracle=tmp_path, key="fixture", ticker="SPXW")

    class Store:
        seal = None

        def __init__(self):
            self.orders = []

        def rows(self, key, ids):
            indices = np.asarray(ids, dtype=int)
            self.orders.append(indices.copy())
            return pack, indices, all_si[indices]

    stats = {
        key: {"mean": [0.0] * n, "std": [1.0] * n}
        for key, n in (("base", 2), ("tokens", 2), ("maps", 5), ("action", 2))
    }
    model = original.LevelTCN(2, 2, 2, 2, 5).eval()
    models = {
        "gbt_net": ConstantGBT(),
        "gbt_advantage": ConstantGBT(),
        "tcn_teacher": model,
    }
    old_store, new_store = Store(), Store()
    original_actions, old = original.predict_day(
        day, old_store, models, {"SPXW": 81.0}, stats, "cpu"
    )
    score = compat.inference_exact(
        original, model, new_store, day, actions, stats, 81.0, "cpu"
    )
    assert (
        original_actions.action_id.to_numpy().tobytes()
        == actions.action_id.to_numpy().tobytes()
    )
    assert score.dtype == np.float64
    assert score.tobytes() == old["tcn_teacher"].tobytes()
    assert len(old_store.orders) == len(new_store.orders)
    for before, after in zip(old_store.orders, new_store.orders):
        np.testing.assert_array_equal(before, after)
    previous_helper = runner.inference(
        original, model, Store(), day, actions, stats, 81.0, "cpu"
    )
    assert previous_helper.tobytes() != score.tobytes(), (
        "Fixture must expose the prior rounding discrepancy"
    )
    assert compat.inference_exact(
        original, model, Store(), day, actions.iloc[:0], stats, 81.0, "cpu"
    ).shape == (0,)


def test_compat_binding_before_predictions_and_mutations(tmp_path, monkeypatch):
    out, learner = tmp_path / "out", tmp_path / "learner"
    out.mkdir()
    learner.mkdir()
    original = learner / "train_models.py"
    original.write_bytes(b"original fixture")
    monkeypatch.setattr(compat, "EXPECTED_ORIGINAL_SHA", runner.sha(original))
    for name in (
        "tcn_variant.pt",
        "normalizers.json",
        "feature_schema.json",
        "run_tcn_flags.executed.py",
    ):
        (out / name).write_bytes(name.encode())
    runner.atomic_json(
        out / "identity.json", {"learner_root": str(learner), "files": {}}
    )
    runner.atomic_json(
        out / "training_complete.json",
        {"binding": {"files": {}}, "model_sha256": runner.sha(out / "tcn_variant.pt")},
    )
    _, _, files = compat.bind_runtime(runner, out)
    runner.verify_files(files)
    (out / "validation").mkdir()
    _, _, again = compat.bind_runtime(runner, out)
    assert files == again
    (out / "normalizers.json").write_bytes(b"changed")
    with pytest.raises(ValueError, match="binding differs"):
        compat.bind_runtime(runner, out)
    # A missing binding cannot be reconstructed after prediction artifacts exist.
    (out / "evaluation_runtime.json").rename(out / "preserved_runtime.json")
    with pytest.raises(ValueError, match="without prior compatibility"):
        compat.bind_runtime(runner, out)


def test_final_certificate_recovery_without_economic_replay(tmp_path):
    runner.atomic_json(tmp_path / "evaluation_runtime.json", {"fixture": True})
    runner.atomic_json(tmp_path / "summary.json", {"status": "COMPLETE"})
    runner.atomic_json(
        tmp_path / "freeze.json",
        {
            "files": {
                str(tmp_path / "evaluation_runtime.json"): runner.sha(
                    tmp_path / "evaluation_runtime.json"
                )
            }
        },
    )
    runner.atomic_json(
        tmp_path / "completion.json",
        {
            "status": "COMPLETE",
            "files": {
                str(tmp_path / "summary.json"): runner.sha(tmp_path / "summary.json")
            },
        },
    )
    (tmp_path / "evaluation_runtime_completion.json.partial").write_bytes(
        b"interrupted"
    )
    compat.finalize_runtime(runner, tmp_path, {})
    path = tmp_path / "evaluation_runtime_completion.json"
    before = runner.sha(path)
    compat.finalize_runtime(runner, tmp_path, {})
    assert runner.sha(path) == before
    assert list(
        (tmp_path / "recovery").glob("*/evaluation_runtime_completion.json.partial")
    )
    (tmp_path / "summary.json").write_bytes(b"changed")
    with pytest.raises(ValueError, match="Changed bound source"):
        compat.finalize_runtime(runner, tmp_path, {})
