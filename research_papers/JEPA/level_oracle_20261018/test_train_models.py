"""Synthetic learner checks. No local market parquet is opened by these tests."""

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest
import torch

spec = importlib.util.spec_from_file_location(
    "train_models", Path(__file__).with_name("train_models.py")
)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def pack():
    rng = np.random.default_rng(123)
    return {
        "base": rng.normal(size=(4, 3)).astype(np.float32),
        "tokens": rng.normal(size=(4, 20, 4)).astype(np.float32),
        "maps": rng.normal(size=(4, 20, 5, 64)).astype(np.float32),
        "token_mask": np.ones((4, 20, 2), np.float32),
        "map_mask": np.ones((4, 20, 5), np.float32),
        "action_features": rng.normal(size=(8, 5)).astype(np.float32),
    }


def stats(p):
    return {
        k: {"mean": [0.0] * width, "std": [1.0] * width}
        for k, width in (
            ("base", p["base"].shape[-1]),
            ("tokens", p["tokens"].shape[-1]),
            ("maps", 5),
            ("action", p["action_features"].shape[-1]),
        )
    }


def test_priority_reproducible_unique_and_labels_irrelevant():
    ids = np.arange(10_000)
    a = m.row_priority("SPY", "20240103", ids)
    assert np.array_equal(a, m.row_priority("SPY", "20240103", ids))
    assert len(np.unique(a)) == len(a)
    assert not np.array_equal(a, m.row_priority("QQQ", "20240103", ids))


def test_streaming_sample_equals_global_lowest_and_stable_hash_ties():
    f = pd.DataFrame({"day_key": ["SPY/20240103"] * 1000, "action_id": np.arange(1000)})
    f["priority"] = m.row_priority("SPY", "20240103", f.action_id)
    direct = m.bounded_lowest(f, 71).sort_values("action_id")
    stream = pd.DataFrame()
    for split in np.array_split(f, 17):
        stream = m.bounded_lowest(pd.concat([stream, split], ignore_index=True), 71)
    assert (
        direct.action_id.tolist() == stream.sort_values("action_id").action_id.tolist()
    )
    tied = f.iloc[:3].copy()
    tied["priority"] = 7
    assert m.bounded_lowest(tied.iloc[::-1], 2).action_id.tolist() == [0, 1]


def test_horvitz_thompson_weights_restore_stratum_population():
    population = [1000, 10]
    selected = [50, 10]
    raw = np.r_[
        np.full(selected[0], population[0] / selected[0]),
        np.full(selected[1], population[1] / selected[1]),
    ]
    normalized = raw / raw.mean()
    label = np.r_[np.ones(selected[0]), np.full(selected[1], 100.0)]
    assert np.average(label, weights=normalized) == pytest.approx((1000 + 1000) / 1010)
    assert normalized.mean() == pytest.approx(1.0)


def test_weighted_median_uses_only_valid_positive_training_observations():
    assert m.weighted_median([1, 2, 100, np.nan, -100], [1, 10, 1, 999, 999]) == 2
    with pytest.raises(ValueError):
        m.weighted_median([np.nan, 0], [1, 1])


def test_weighted_moments_and_missing_imputation_mask():
    moments = m.Moments(2)
    moments.update([[1, np.nan], [3, 5]], [1, 3])
    stat = moments.result()
    assert stat["mean"] == [2.5, 5.0]
    value = m.normalized([[np.nan, 5]], stat)
    assert value.shape == (1, 4)
    assert np.isfinite(value).all()
    assert value.tolist() == [[0.0, 0.0, 0.0, 1.0]]


def validation_table(score):
    return {
        m.policy_id(model, threshold): {
            "tickers": {t: {"base_net_usd": score} for t in m.TICKERS}
        }
        for model in m.MODELS
        for threshold in m.THRESHOLDS
    }


def test_cash_wins_all_losses_and_exact_zero_ties():
    scales = {t: 100.0 for t in m.TICKERS}
    for net in (-10.0, 0.0):
        winner, choices = m.select_policy(validation_table(net), scales)
        assert winner["policy"] == "CASH" and len(choices) == 10
    winner, _ = m.select_policy(validation_table(10.0), scales)
    assert winner["policy"] == "gbt_net__0"


def test_selection_uses_past_risk_normalization_not_spx_nominal_dominance():
    table = validation_table(-1)
    table["gbt_net__0"]["tickers"] = {
        "SPXW": {"base_net_usd": 1000.0},
        "SPY": {"base_net_usd": -100.0},
        "QQQ": {"base_net_usd": -100.0},
    }
    winner, _ = m.select_policy(table, {"SPXW": 1000.0, "SPY": 100.0, "QQQ": 100.0})
    assert winner["policy"] == "CASH"


def test_cash_not_marked_profitable():
    gate = m.economic_gate({"policy": "CASH"}, {})
    assert (
        not gate["passes"]
        and gate["reason"] == "CASH_SELECTED_NOT_A_PROFITABLE_LEARNER"
    )


def test_selected_policy_gate_cannot_be_rescued_by_other_candidate():
    good = {
        "trades": 60,
        "base_net_usd": 100.0,
        "adverse_net_usd": 20.0,
        "base_pf": 1.2,
    }
    candidate = {
        "tickers": {t: dict(good) for t in m.TICKERS},
        "months": {
            t: {str(i): {"base_net_usd": 1.0 if i < 3 else -1.0} for i in range(6)}
            for t in m.TICKERS
        },
    }
    summaries = {"selected": candidate, "better": candidate}
    assert m.economic_gate({"policy": "selected"}, summaries)["passes"]
    candidate["tickers"]["QQQ"]["trades"] = 59
    assert not m.economic_gate({"policy": "selected"}, summaries)["passes"]


def test_gbt_view_preserves_every_candle_and_spatial_cell():
    p = pack()
    first = m.flatten_gbt(p, np.array([0]), np.array([0]))
    p["maps"][0, 19, 4, 63] += 8.0
    changed = m.flatten_gbt(p, np.array([0]), np.array([0]))
    assert np.count_nonzero(first != changed) == 1
    p["tokens"][0, 0, 0] += 1.0
    assert (
        np.count_nonzero(changed != m.flatten_gbt(p, np.array([0]), np.array([0]))) == 1
    )


def test_causal_block_output_prefix_ignores_later_tokens():
    torch.manual_seed(123)
    block = m.CausalBlock(3, 2).eval()
    x = torch.randn(2, 3, 10)
    y = x.clone()
    y[:, :, 5:] = 1e6
    with torch.inference_mode():
        assert torch.equal(block(x)[:, :, :5], block(y)[:, :, :5])


@pytest.mark.parametrize("device", ["cpu", "cuda"])
def test_true_neural_forward_backward_and_serialization(tmp_path, device):
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    torch.manual_seed(123)
    torch.use_deterministic_algorithms(True)
    p = pack()
    batch = m.neural_batch(p, np.array([0, 1]), np.array([0, 1]), stats(p), device)
    model = m.LevelTCN(3, 4, 5, 2, 5).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001)
    before = model.net.weight.detach().clone()
    predictions, teacher = model(*batch)
    # Fixed denominator even for this synthetic partial batch.
    loss = (
        (predictions - 0.5).square()
        + 0.1
        * torch.nn.functional.binary_cross_entropy_with_logits(
            teacher, torch.ones_like(teacher), reduction="none"
        )
    ).sum() / 1024
    loss.backward()
    optimizer.step()
    assert not torch.equal(model.net.weight, before)
    target = tmp_path / (device + ".pt")
    torch.save({"config": model.config, "state_dict": model.cpu().state_dict()}, target)
    stored = torch.load(target, map_location="cpu", weights_only=True)
    restored = m.LevelTCN(**stored["config"])
    restored.load_state_dict(stored["state_dict"])
    cpu_batch = tuple(v.cpu() for v in batch)
    with torch.inference_mode():
        assert torch.equal(model(*cpu_batch)[0], restored(*cpu_batch)[0])


def test_oracle_failure_blocks_fit(tmp_path):
    path = tmp_path / "audit.json"
    path.write_text(json.dumps({"status": "FAILED"}))
    with pytest.raises(ValueError):
        m.require_oracle_pass(path, tmp_path)


def full_audit_fixture(tmp_path):
    root = tmp_path / "engine"
    cache = tmp_path / "cache"
    root.mkdir()
    cache.mkdir()
    m.write_json(cache / "cache_contract.json", {"fixture": True})
    m.write_json(cache / "full_summary.json", {"fixture": True})
    contract = {
        "cache_root": str(cache),
        "engine_sha256": m.sha(Path(m.__file__).with_name("level_engine.py")),
        "runner_sha256": m.sha(Path(m.__file__).with_name("run_engine_dataset.py")),
        "cache_contract_sha256": m.sha(cache / "cache_contract.json"),
        "expected_calendar_rows": 2601,
        "expected_available_days": 2595,
        "expected_missing_days": 6,
    }
    m.write_json(root / "dataset_contract.json", contract)
    pd.DataFrame(
        {
            "ticker": ["FIXTURE"] * 2601,
            "date": [str(i) for i in range(2601)],
            "status": ["COMPLETE"] * 2595 + ["MISSING_SOURCE"] * 6,
        }
    ).to_parquet(root / "index.parquet")
    m.write_json(root / "summary.json", {"fixture": True})
    completion = {
        "status": "COMPLETE",
        "index_sha256": m.sha(root / "index.parquet"),
        "summary_sha256": m.sha(root / "summary.json"),
        "dataset_contract_sha256": m.sha(root / "dataset_contract.json"),
        "cache_full_summary_sha256": m.sha(cache / "full_summary.json"),
    }
    m.write_json(root / "completion.json", completion)
    binding = {
        "engine_root": str(root),
        "engine_sha256": contract["engine_sha256"],
        "engine_runner_sha256": contract["runner_sha256"],
        "completion_sha256": m.sha(root / "completion.json"),
        "index_sha256": completion["index_sha256"],
        "dataset_contract_sha256": completion["dataset_contract_sha256"],
        "cache_contract_sha256": contract["cache_contract_sha256"],
        "cache_full_summary_sha256": completion["cache_full_summary_sha256"],
        "available_days": 2595,
        "missing_days": 6,
    }
    audit = {"status": "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT", "binding": binding}
    path = tmp_path / "audit.json"
    m.write_json(path, audit)
    return path, root, audit


@pytest.mark.parametrize("mutation", ["pilot", "root", "hash", "coverage"])
def test_full_audit_gate_rejects_wrong_scope_root_hash_counts(tmp_path, mutation):
    path, root, audit = full_audit_fixture(tmp_path)
    assert len(m.require_oracle_pass(path, root)["verified_files"]) == 9
    if mutation == "pilot":
        audit["status"] = "PASS_INDEPENDENT_LEVEL_ORACLE_PILOT_AUDIT"
    elif mutation == "root":
        audit["binding"]["engine_root"] = str(tmp_path / "different")
    elif mutation == "hash":
        audit["binding"]["index_sha256"] = "0" * 64
    else:
        audit["binding"]["available_days"] = 3
    m.write_json(path, audit)
    with pytest.raises(ValueError):
        m.require_oracle_pass(path, root)


def test_audited_sidecar_seal_detects_mutation_before_and_after_use(tmp_path):
    day_root = tmp_path / "SPY" / "20230103"
    day_root.mkdir(parents=True)
    path = day_root / "labels.parquet"
    pd.DataFrame({"action_id": [1], "net_base": [2.0]}).to_parquet(path)
    pd.DataFrame(
        [
            {
                "ticker": "SPY",
                "date": "20230103",
                "status": "COMPLETE",
                "day_root": str(day_root),
                "labels_sha256": m.sha(path),
            }
        ]
    ).to_parquet(tmp_path / "index.parquet")
    seal = m.SourceSeal(tmp_path)
    day = m.Day("SPY", "20230103", day_root, tmp_path / "features.npz")
    seal.check(day, "labels.parquet")
    seal.recheck()
    pd.DataFrame({"action_id": [1], "net_base": [999.0]}).to_parquet(path)
    with pytest.raises(ValueError):
        seal.check(day, "labels.parquet")
    with pytest.raises(ValueError):
        seal.recheck()


def test_epoch_resume_restores_optimizer_rng_and_rejects_changed_source(tmp_path):
    torch.manual_seed(123)
    rng = np.random.default_rng(456)
    model = torch.nn.Linear(2, 1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.01)

    def step(network, optim, generator):
        x = torch.randn(4, 2)
        target = torch.as_tensor(generator.normal(size=(4, 1)), dtype=torch.float32)
        optim.zero_grad()
        (network(x) - target).square().mean().backward()
        optim.step()

    step(model, optimizer, rng)
    source = tmp_path / "source.txt"
    source.write_text("immutable")
    binding = {"files": {str(source): m.sha(source)}, "device": "cpu"}
    checkpoint = tmp_path / "epoch.pt"
    m.save_epoch_checkpoint(
        checkpoint, model, optimizer, rng, 1, [{"epoch": 1}], binding
    )
    step(model, optimizer, rng)
    expected = {k: v.clone() for k, v in model.state_dict().items()}
    restored = torch.nn.Linear(2, 1)
    restored_optimizer = torch.optim.AdamW(restored.parameters(), lr=0.01)
    restored_rng = np.random.default_rng(999)
    epoch, history = m.restore_epoch_checkpoint(
        checkpoint, restored, restored_optimizer, restored_rng, binding
    )
    assert epoch == 1 and history == [{"epoch": 1}]
    step(restored, restored_optimizer, restored_rng)
    assert all(torch.equal(expected[k], v) for k, v in restored.state_dict().items())
    with pytest.raises(ValueError, match="Never overwrite"):
        m.save_epoch_checkpoint(checkpoint, model, optimizer, rng, 2, [], binding)
    source.write_text("changed")
    with pytest.raises(ValueError, match="Resume input changed"):
        m.restore_epoch_checkpoint(
            checkpoint, restored, restored_optimizer, restored_rng, binding
        )


def test_future_and_join_ids_are_explicitly_forbidden_feature_names():
    assert {
        "contract_i",
        "action_id",
        "entry_level_id",
        "target_level_id",
        "stop_level_id",
        "entry_ask",
        "net_base",
        "exit_i",
        "dp_advantage",
    } <= m.FORBIDDEN_FEATURES


def test_exit_diagnostics_separate_target_stop_eod_and_variable_holding():
    frame = pd.DataFrame(
        {
            "reason": ["TARGET", "STOP", "EOD", "TARGET"],
            "hold_minutes": [2, 7, 250, 11],
            "net_base": [10, -5, 90, 20],
            "net_adverse": [8, -7, 88, 18],
        }
    )
    result = m.economic_metrics(frame)
    assert result["exit_reasons"]["TARGET"] == {
        "trades": 2,
        "base_net_usd": 30.0,
        "adverse_net_usd": 26.0,
    }
    assert result["exit_reasons"]["EOD"]["base_net_usd"] == 90
    assert result["holding_minutes"] == {"min": 2.0, "median": 9.0, "max": 250.0}


def test_profit_factor_distinguishes_no_losses_from_no_profit():
    positive = m.economic_metrics(
        pd.DataFrame({"net_base": [5.0, 4.0], "net_adverse": [3.0, 2.0]})
    )
    assert positive["base_pf"] is None and positive["base_pf_infinite"]
    zero = m.economic_metrics(pd.DataFrame({"net_base": [0.0], "net_adverse": [0.0]}))
    assert zero["base_pf"] is None and not zero["base_pf_infinite"]


def test_metrics_exposes_adverse_loss_despite_base_profit():
    metrics = m.economic_metrics(
        pd.DataFrame({"net_base": [10.0, -2.0], "net_adverse": [-1.0, -5.0]})
    )
    assert metrics["base_net_usd"] == 8.0
    assert metrics["adverse_net_usd"] == -6.0
    assert metrics["base_max_drawdown_usd"] == 2.0


def test_unique_state_encoder_matches_repeated_state_forward():
    torch.manual_seed(123)
    p = pack()
    network = m.LevelTCN(3, 4, 5, 2, 5).eval()
    ai, si = np.array([0, 1, 2, 3]), np.array([1, 1, 2, 1])
    with torch.inference_mode():
        repeated = network(*m.neural_batch(p, ai, si, stats(p), "cpu"))
        shared = m.neural_actions(network, p, ai, si, stats(p), "cpu")
    for a, b in zip(repeated, shared):
        torch.testing.assert_close(a, b, rtol=1e-6, atol=1e-7)


def test_vectorized_scheduler_matches_canonical_all_thresholds_and_no_fill():
    engine = m.import_sibling("level_engine")
    scheduler = m.import_sibling("run_policy")
    rng = np.random.default_rng(931)
    actions = pd.DataFrame(
        {"action_id": np.arange(600), "state_i": np.repeat(np.arange(60, 260), 3)}
    )
    filled = rng.random(len(actions)) > 0.1
    labels = pd.DataFrame(
        {
            "action_id": actions.action_id,
            "status": np.where(filled, "FILLED", "NO_FILL"),
            "exit_i": actions.state_i
            + np.where(filled, rng.integers(2, 60, len(actions)), 1),
            "net_base": rng.normal(size=len(actions)),
            "net_adverse": rng.normal(size=len(actions)),
        }
    )
    # Tie, no-fill and nonfinite score cases are deliberate, with shuffled sources.
    scores = rng.choice([0.0, 5.0, 10.0, 15.0, np.nan, np.inf], len(actions))
    actions = actions.sample(frac=1, random_state=9).reset_index(drop=True)
    labels = labels.sample(frac=1, random_state=8).reset_index(drop=True)
    view = scheduler.PolicyView(actions, labels)
    for threshold in (0.0, 5.0, 10.0):
        reference = engine.evaluate_policy(actions, labels, scores, threshold)
        actual = view.evaluate(scores, threshold, engine)
        pd.testing.assert_frame_equal(
            reference.attempts.reset_index(drop=True),
            actual.attempts.reset_index(drop=True),
            check_dtype=False,
        )
        assert reference.summary == actual.summary


def test_vectorized_scheduler_wait_tie_and_no_future_action_replacement():
    engine = m.import_sibling("level_engine")
    scheduler = m.import_sibling("run_policy")
    actions = pd.DataFrame({"action_id": [0, 1, 2], "state_i": [60, 60, 61]})
    labels = pd.DataFrame(
        {
            "action_id": [0, 1, 2],
            "status": ["NO_FILL", "FILLED", "FILLED"],
            "exit_i": [61, 65, 63],
            "net_base": [0.0, 1000.0, -1.0],
            "net_adverse": [0.0, 999.0, -2.0],
        }
    )
    view = scheduler.PolicyView(actions, labels)
    result = view.evaluate(np.array([11.0, 10.0, 0.0]), 0.0, engine)
    assert result.attempts.action_id.tolist() == [0]
    assert result.ledger.empty
    assert result.summary["no_fill_attempts"] == 1


def test_shared_state_encoding_weighted_gradients_match_repeated():
    torch.manual_seed(912)
    p = pack()
    repeated = m.LevelTCN(3, 4, 5, 2, 5)
    shared = m.LevelTCN(3, 4, 5, 2, 5)
    shared.load_state_dict(repeated.state_dict())
    ai, si = np.array([0, 1, 2, 3]), np.array([1, 1, 2, 1])
    weights = torch.tensor([1.0, 10.0, 0.5, 3.0])
    a = repeated(*m.neural_batch(p, ai, si, stats(p), "cpu"))[0]
    b = m.neural_actions(shared, p, ai, si, stats(p), "cpu")[0]
    (weights * (a - 0.3).square()).sum().div(1024).backward()
    (weights * (b - 0.3).square()).sum().div(1024).backward()
    for left, right in zip(repeated.parameters(), shared.parameters()):
        if left.grad is None:
            assert right.grad is None
        else:
            torch.testing.assert_close(left.grad, right.grad, rtol=2e-5, atol=1e-8)


def test_feature_store_joins_keys_only_and_verifies_whitelist_hashes(tmp_path):
    state_path = tmp_path / "features" / "SPY" / "20240103" / "features.npz"
    oracle_path = tmp_path / "engine" / "SPY" / "20240103"
    state_path.parent.mkdir(parents=True)
    oracle_path.mkdir(parents=True)
    arrays = pack()
    actions = arrays.pop("action_features")
    arrays["token_mask"] = arrays["token_mask"][:, :, 0]
    arrays["bar_mask"] = np.ones((4, 20), bool)
    arrays["state_i"] = np.arange(60, 64)
    np.savez_compressed(state_path, **arrays)
    action_path = state_path.with_name("actions.npz")
    np.savez_compressed(action_path, action_id=np.arange(8), action_features=actions)
    pd.DataFrame(
        {"action_id": np.arange(8), "state_i": np.repeat(np.arange(60, 64), 2)}
    ).to_parquet(oracle_path / "actions.parquet")
    schema = {
        "base_names": [f"base{i}" for i in range(3)],
        "token_names": [f"token{i}" for i in range(4)],
        "map_names": [f"map{i}" for i in range(5)],
        "action_names": [f"action{i}" for i in range(5)],
    }
    contract = {"schema": schema, "dependencies": {}, "outcomes_read": False}
    m.write_json(tmp_path / "features" / "feature_contract.json", contract)
    m.write_json(
        state_path.with_suffix(".json"),
        {
            "schema": schema,
            "binding": {"dependencies": {}},
            "sha256": m.sha(state_path),
            "outcomes_read": False,
        },
    )
    action_metadata = {
        "action_names": schema["action_names"],
        "binding": {"dependencies": {}},
        "sha256": m.sha(action_path),
        "outcomes_read": False,
    }
    m.write_json(action_path.with_suffix(".json"), action_metadata)
    day = m.Day("SPY", "20240103", oracle_path, state_path)
    store = m.FeatureStore([day])
    p, ai, si = store.rows(day.key, [7, 0, 3])
    assert ai.tolist() == [7, 0, 3] and si.tolist() == [3, 0, 1]
    assert m.flatten_gbt(p, ai, si).shape[0] == 3
    assert "action_id" not in sum(store.schema.values(), [])
    action_metadata["action_names"][0] = "exit_i"
    m.write_json(action_path.with_suffix(".json"), action_metadata)
    with pytest.raises(ValueError, match="whitelist"):
        m.FeatureStore([day]).get(day.key)
