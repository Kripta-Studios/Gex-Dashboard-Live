import copy

import numpy as np
import pandas as pd
import pytest
import torch

import run_tcn_row_mixed as mixed
from test_run_tcn_flags import Store, assert_nested, original_module, training_fixture


class TinyCache:
    def __init__(self, original, sample, stats):
        store = Store()
        tensors, keys = [[] for _ in range(6)], []
        for day_number, (_, rows) in enumerate(sample.groupby("day_key", sort=True)):
            pack, ai, si = store.rows("unused", rows.action_id)
            batch = original.neural_batch(pack, ai, si, stats, "cpu")
            for dest, value in zip(tensors, batch):
                dest.append(value)
            keys.extend(day_number * 391 + si)
        self.arrays = tuple(torch.cat(items) for items in tensors)
        self.keys = np.array(keys)
        self.config = dict(
            base_dim=2, token_dim=2, action_dim=2, token_mask_dim=2, map_mask_dim=5
        )

    def inputs(self, rows, device):
        return tuple(x[rows].to(device) for x in self.arrays)

    def state_keys(self, rows):
        return self.keys[rows]


def test_original_schedule_rng_and_complete_exposures():
    sample, _ = training_fixture()
    rng = mixed.ReplayRNG()
    reference = np.random.default_rng(mixed.flags.SEED)
    for _ in range(4):
        expected = []
        groups = {
            k: r.index.to_numpy() for k, r in sample.groupby("day_key", sort=True)
        }
        for key in reference.permutation(np.array(sorted(groups), dtype=object)):
            expected.extend(reference.permutation(groups[key]))
        plan = mixed.epoch_plan(sample, rng)
        np.testing.assert_array_equal(plan["original_order"], expected)
        np.testing.assert_array_equal(plan["sizes"], [3, 3])
        np.testing.assert_array_equal(np.sort(plan["mixed_order"]), np.arange(6))
        assert rng.schedule.bit_generator.state == reference.bit_generator.state


def test_original_schedule_keeps_1024_boundary_and_partial_batches():
    sample = pd.DataFrame({"day_key": ["QQQ/20230103"] * 1030 + ["QQQ/20230104"] * 17})
    plan = mixed.epoch_plan(sample, mixed.ReplayRNG())
    assert sorted(plan["sizes"].tolist()) == [6, 17, 1024]
    assert plan["sizes"].sum() == 1047
    np.testing.assert_array_equal(np.sort(plan["mixed_order"]), np.arange(1047))


def test_same_minute_on_different_days_is_not_deduplicated():
    class Model:
        def encode_state(self, base, *unused):
            return base

        def score_actions(self, state, action):
            return state[:, 0], state[:, 0]

    inputs = (torch.tensor([[1.0], [2.0]]),) * 6
    expected, _ = mixed.score_prepacked(Model(), inputs, np.array([60, 451]))
    assert torch.equal(expected, torch.tensor([1.0, 2.0]))
    collapsed, _ = mixed.score_prepacked(Model(), inputs, np.array([60, 60]))
    assert torch.equal(collapsed, torch.tensor([1.0, 1.0]))


def test_single_day_scores_and_diagnostics_match_frozen_helper_exactly():
    torch.set_num_threads(1)
    original = original_module()
    sample, stats = training_fixture()
    cache = TinyCache(original, sample, stats)
    torch.manual_seed(9)
    model = original.LevelTCN(**cache.config)
    store = Store()
    idx = np.array([2, 0, 1, 2])
    pack, ai, si = store.rows("unused", sample.iloc[idx].action_id)
    expected = original.neural_actions(model, pack, ai, si, stats, "cpu")
    observed = mixed.score_prepacked(
        model, cache.inputs(idx, "cpu"), cache.state_keys(idx)
    )
    assert all(torch.equal(a, b) for a, b in zip(expected, observed))
    before_rng = torch.get_rng_state().clone()
    a = mixed.flags.fixed_train_evaluation(
        original, model, sample, store, {"SPXW": 10.0}, stats, "cpu"
    )
    b = mixed.cached_train_evaluation(model, sample, cache, {"SPXW": 10.0}, "cpu")
    assert a == b
    assert torch.equal(before_rng, torch.get_rng_state())


def test_composite_rng_checkpoint_resume_exact_weights_adam_and_history(tmp_path):
    original = original_module()
    sample, stats = training_fixture()
    cache = TinyCache(original, sample, stats)
    full, resume = tmp_path / "full", tmp_path / "resume"
    full.mkdir()
    resume.mkdir()
    binding = dict(files={}, device="cpu", experiment="fixture")
    model1, opt1, history1 = mixed.train_cached(
        original,
        sample,
        cache,
        {"SPXW": 10.0},
        full,
        "cpu",
        copy.deepcopy(binding),
        epochs=2,
        diagnostic=True,
    )
    mixed.train_cached(
        original,
        sample,
        cache,
        {"SPXW": 10.0},
        resume,
        "cpu",
        copy.deepcopy(binding),
        epochs=1,
        diagnostic=True,
    )
    model2, opt2, history2 = mixed.train_cached(
        original,
        sample,
        cache,
        {"SPXW": 10.0},
        resume,
        "cpu",
        copy.deepcopy(binding),
        resume=True,
        epochs=2,
        diagnostic=True,
    )
    assert_nested(model1.state_dict(), model2.state_dict())
    assert_nested(opt1.state_dict(), opt2.state_dict())
    assert_nested(history1, history2)
    a = torch.load(full / "tcn_epoch02.pt", map_location="cpu", weights_only=False)
    b = torch.load(resume / "tcn_epoch02.pt", map_location="cpu", weights_only=False)
    assert_nested(a["rng"], b["rng"])
    assert set(a["rng"]["generator"]) == {"schedule", "mixed"}


def test_plan_recovery_preserves_unsealed_file_and_replays(tmp_path):
    sample, _ = training_fixture()
    rng = mixed.ReplayRNG()
    before = rng.state
    plan = mixed.epoch_plan(sample, rng)
    after = rng.state
    (tmp_path / "epoch01_plan.npz").write_bytes(b"partial-unsealed")
    files = mixed.persist_plan(tmp_path, 1, plan, before, after)
    assert any(
        p.read_bytes() == b"partial-unsealed"
        for p in (tmp_path / "recovery").rglob("*.npz")
    )
    assert mixed.persist_plan(tmp_path, 1, plan, before, after) == files
    bad = copy.deepcopy(plan)
    bad["mixed_order"] = bad["mixed_order"][::-1]
    with pytest.raises(ValueError, match="replay differs"):
        mixed.persist_plan(tmp_path, 1, bad, before, after)


def test_feature_hashes_match_prior_training_not_new_self_baseline(tmp_path):
    sources = []
    for name in ("features.npz", "features.json", "actions.npz", "actions.json"):
        path = tmp_path / name
        path.write_bytes(name.encode())
        sources.append(path)
    authority = {str(p.resolve()): mixed.flags.sha(p) for p in sources}
    mixed.check_training_authority(authority, authority)
    sources[-1].write_bytes(b"changed feature sidecar")
    new_baseline = {str(p.resolve()): mixed.flags.sha(p) for p in sources}
    with pytest.raises(ValueError, match="FLAGS TRAIN authority"):
        mixed.check_training_authority(new_baseline, authority)
    with pytest.raises(ValueError, match="FLAGS TRAIN authority"):
        mixed.check_training_authority(
            {str(tmp_path / "unknown.npz"): "new"}, authority
        )


def test_cache_resumes_sealed_day_preserves_only_unfinished_rows(tmp_path):
    source = tmp_path / "source.npz"
    source.write_bytes(b"frozen")
    authority = {str(source.resolve()): mixed.flags.sha(source)}
    arrays = {
        "base": np.lib.format.open_memmap(
            tmp_path / "base.npy", mode="w+", shape=(600, 2), dtype=np.float32
        ),
        "state_key": np.lib.format.open_memmap(
            tmp_path / "state.npy", mode="w+", shape=(600,), dtype=np.int64
        ),
    }
    first, second = np.arange(300), np.arange(300, 600)
    arrays["base"][first] = 3
    arrays["state_key"][:] = np.arange(600)
    done = tmp_path / "complete.json"
    mixed.flags.atomic_json(
        done,
        dict(
            day_key="QQQ/20230103",
            source_files=authority,
            chunks=mixed.chunk_hashes(arrays, first),
        ),
    )
    original = arrays["base"][first].copy()
    # Simulate power loss after writing only part of the next day's rows.
    arrays["base"][second[:50]] = 9
    folder = tmp_path / "unfinished"
    folder.mkdir()
    mixed.flags.atomic_json(folder / "started_01.json", {"key": "QQQ/20230104"})
    mixed.preserve_unfinished_day(folder, arrays, second)
    saved = list(folder.glob("recovery_*/rows_*.npz"))
    assert len(saved) == 2
    recovered = []
    for path in saved:
        with np.load(path, allow_pickle=False) as chunk:
            recovered.extend(chunk["indices"].tolist())
            assert chunk["indices"].min() >= 300
    assert sorted(recovered) == second.tolist()
    assert not list(folder.glob("started_*.json"))
    assert (
        mixed.verify_cached_day(done, arrays, first, "QQQ/20230103", authority)
        == authority
    )
    np.testing.assert_array_equal(arrays["base"][first], original)
    arrays["base"][second] = 7
    mixed.flags.atomic_json(
        folder / "complete.json",
        dict(
            day_key="QQQ/20230104",
            source_files=authority,
            chunks=mixed.chunk_hashes(arrays, second),
        ),
    )
    mixed.verify_cached_day(
        folder / "complete.json", arrays, second, "QQQ/20230104", authority
    )
    arrays["base"][0, 0] = 4
    with pytest.raises(ValueError, match="Completed cache day changed"):
        mixed.verify_cached_day(done, arrays, first, "QQQ/20230103", authority)
