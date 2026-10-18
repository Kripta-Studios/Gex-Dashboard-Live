"""Synthetic-only fixtures for the isolated normalization experiment."""

import copy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import run_tcn_flags as flags  # noqa: E402


def original_module():
    spec = importlib.util.spec_from_file_location(
        "flags_fixture_original", ROOT / "train_models.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def semantic_fixture():
    schema = {
        flags.SCHEMA_KEYS[k]: list(v) + ["continuous_market"]
        for k, v in flags.WHITELIST.items()
    }
    stats = {
        k: {
            "mean": [4.0] * len(schema[flags.SCHEMA_KEYS[k]]),
            "std": [2.0] * len(schema[flags.SCHEMA_KEYS[k]]),
            "weight": [8.0] * len(schema[flags.SCHEMA_KEYS[k]]),
        }
        for k in flags.WHITELIST
    }
    return schema, {"features": stats, "risk_scales_usd": {"SPXW": 1.0}}


def test_semantic_64_and_exact_untouched_continuous():
    schema, stats = semantic_fixture()
    before = copy.deepcopy(stats)
    after, changed = flags.override_stats(stats, schema)
    assert len(changed) == 64
    assert {k: len(v) for k, v in flags.WHITELIST.items()} == {
        "base": 32,
        "tokens": 15,
        "action": 17,
        "maps": 0,
    }
    assert stats == before
    assert not any(
        "oi_positive" in x["name"] or "outside" in x["name"] or "age" in x["name"]
        for x in changed
    )
    for group in flags.WHITELIST:
        assert after["features"][group]["mean"][-1] == 4.0
        assert after["features"][group]["std"][-1] == 2.0
        assert after["features"][group]["weight"] == before["features"][group]["weight"]
    original = original_module()
    x = np.array([[0.0, 1.0, np.nan]], dtype=np.float32)
    prior = {"mean": [4.0, 4.0, 4.0], "std": [2.0, 2.0, 2.0]}
    patched = {"mean": [0.0, 4.0, 4.0], "std": [1.0, 2.0, 2.0]}
    a, b = original.normalized(x, prior), original.normalized(x, patched)
    np.testing.assert_array_equal(a[:, 1:], b[:, 1:])
    assert b[0, 0] == 0


def test_schema_and_domains_fail_closed():
    schema, stats = semantic_fixture()
    pack = {
        "action_features" if k == "action" else k: np.zeros(
            (2, len(schema[flags.SCHEMA_KEYS[k]]))
        )
        for k in flags.WHITELIST
    }
    flags.validate_pack(pack, schema)
    pack["base"][0, 0] = 0.5
    with pytest.raises(ValueError, match="Nonbinary"):
        flags.validate_pack(pack, schema)
    pack["base"][0, 0] = 0
    pack["tokens"][0, 0] = np.nan
    with pytest.raises(ValueError, match="natural-range"):
        flags.validate_pack(pack, schema)
    schema["base_names"][0] = "unknown"
    with pytest.raises(ValueError, match="Missing semantic"):
        flags.override_stats(stats, schema)


class Store:
    def __init__(self):
        r = np.random.default_rng(12)
        self.pack = {
            "base": r.normal(size=(3, 2)).astype("f4"),
            "tokens": r.normal(size=(3, 20, 2)).astype("f4"),
            "maps": r.normal(size=(3, 20, 5, 64)).astype("f4"),
            "action_features": r.normal(size=(6, 2)).astype("f4"),
            "token_mask": np.ones((3, 20, 2), "f4"),
            "map_mask": np.ones((3, 20, 5), "f4"),
        }
        self.hashes, self.seal = {}, None

    def rows(self, key, ids):
        ai = np.asarray(ids, dtype=int)
        return self.pack, ai, ai % 3


def training_fixture():
    sample = pd.DataFrame(
        {
            "day_key": ["SPXW/20230103"] * 3 + ["SPXW/20230104"] * 3,
            "ticker": ["SPXW"] * 6,
            "action_id": np.arange(6),
            "net_base": [1.0, -2.0, 8.0, -4.0, 7.0, -9.0],
            "state_optimal_action": [1, 0, 1, 0, 1, 0],
            "weight": [1.0, 0.5, 2.0, 1.0, 0.7, 0.8],
        }
    )
    stats = {
        k: {"mean": [0.0] * d, "std": [1.0] * d}
        for k, d in (("base", 2), ("tokens", 2), ("action", 2), ("maps", 5))
    }
    return sample, stats


def assert_nested(a, b):
    if isinstance(a, torch.Tensor):
        assert torch.equal(a, b)
    elif isinstance(a, dict):
        assert a.keys() == b.keys()
        for key in a:
            assert_nested(a[key], b[key])
    elif isinstance(a, (tuple, list)):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            assert_nested(x, y)
    elif isinstance(a, np.ndarray):
        np.testing.assert_array_equal(a, b)
    else:
        assert a == b


def test_instrumented_equals_original_weights_adam_order_and_resume(
    tmp_path, monkeypatch
):
    original = original_module()
    sample, stats = training_fixture()
    saved = []
    monkeypatch.setattr(original, "EPOCHS", 2)
    monkeypatch.setattr(original, "checkpoint_binding", lambda *args: {})

    def capture(path, model, optimizer, rng, epoch, history, binding):
        saved.append(
            {
                "model": copy.deepcopy(model.state_dict()),
                "optimizer": copy.deepcopy(optimizer.state_dict()),
                "generator": copy.deepcopy(rng.bit_generator.state),
                "history": copy.deepcopy(history),
            }
        )

    monkeypatch.setattr(original, "save_epoch_checkpoint", capture)
    old, new, resumed = (tmp_path / name for name in ("old", "new", "resumed"))
    for folder in (old, new, resumed):
        folder.mkdir()
    original.train_tcn(sample, Store(), {"SPXW": 10.0}, stats, old, "cpu")
    model, optimizer, history = flags.train_instrumented(
        original,
        sample,
        Store(),
        {"SPXW": 10.0},
        stats,
        new,
        "cpu",
        {"files": {}, "device": "cpu"},
        epochs=2,
    )
    assert_nested(model.state_dict(), saved[-1]["model"])
    assert_nested(optimizer.state_dict(), saved[-1]["optimizer"])
    checkpoint = torch.load(new / "tcn_epoch02.pt", weights_only=False)
    assert_nested(checkpoint["rng"]["generator"], saved[-1]["generator"])
    assert [x["summed_fixed_batch_loss"] for x in history] == [
        x["summed_fixed_batch_loss"] for x in saved[-1]["history"]
    ]
    flags.train_instrumented(
        original,
        sample,
        Store(),
        {"SPXW": 10.0},
        stats,
        resumed,
        "cpu",
        {"files": {}, "device": "cpu"},
        epochs=1,
    )
    restored, opt2, history2 = flags.train_instrumented(
        original,
        sample,
        Store(),
        {"SPXW": 10.0},
        stats,
        resumed,
        "cpu",
        {"files": {}, "device": "cpu"},
        epochs=2,
        resume=True,
    )
    assert_nested(model.state_dict(), restored.state_dict())
    assert_nested(optimizer.state_dict(), opt2.state_dict())
    assert history == history2
    with pytest.raises(FileExistsError):
        flags.train_instrumented(
            original,
            sample,
            Store(),
            {"SPXW": 10.0},
            stats,
            resumed,
            "cpu",
            {"files": {}, "device": "cpu"},
            epochs=1,
        )


def test_diagnostic_preserves_rng_and_mode():
    original = original_module()
    sample, stats = training_fixture()
    store = Store()
    model = original.LevelTCN(2, 2, 2, 2, 5)
    model.train()
    before = flags.rng_state()
    result = flags.fixed_train_evaluation(
        original, model, sample, store, {"SPXW": 10.0}, stats, "cpu"
    )
    assert model.training
    assert_nested(before, flags.rng_state())
    assert result["pooled"]["rows"] == 6


def test_daily_gate_and_joint_null_ties():
    calendar = ["20250102"]
    available = {(t, calendar[0]) for t in flags.TICKERS}
    ledger = pd.DataFrame({"ticker": flags.TICKERS, "date": calendar * 3})
    gate, _ = flags.daily_gate(ledger, calendar, available)
    assert gate["passes"]
    incomplete, rows = flags.daily_gate(ledger.iloc[:2], calendar, available)
    assert not incomplete["passes"] and incomplete["observable_days_with_trade"] == 2
    missing, _ = flags.daily_gate(ledger, calendar, set())
    assert missing["no_evaluable_days"] == 3 and not missing["passes"]
    empty, _ = flags.daily_gate(ledger.iloc[:0], calendar, available)
    assert not empty["passes"]
    summaries = {
        p: {
            "daily_gate": gate,
            "tickers": {t: {"base_net_usd": 1.0} for t in flags.TICKERS},
        }
        for p in flags.POLICIES
    }
    assert (
        flags.select_validation(summaries, dict.fromkeys(flags.TICKERS, 1.0))[
            "selected_policy"
        ]
        == "control__0"
    )
    for value in summaries.values():
        value["daily_gate"] = empty
    choice = flags.select_validation(summaries, dict.fromkeys(flags.TICKERS, 1.0))
    assert choice["selected_policy"] is None
    assert choice["diagnostic_best_not_approved"] == "control__0"


def test_scheduler_no_fill_is_not_daily_trade():
    original = original_module()
    policy = original.import_sibling("run_policy")
    actions = pd.DataFrame({"action_id": [1, 2], "state_i": [60, 61]})
    labels = pd.DataFrame(
        {
            "action_id": [1, 2],
            "status": ["NO_FILL", "FILLED"],
            "exit_i": [61, 65],
            "net_base": [0.0, 1.0],
            "net_adverse": [0.0, -1.0],
        }
    )
    engine = SimpleNamespace(
        FIRST_STATE=60,
        ledger_summary=lambda x: {},
        PolicyResult=lambda a, ledger, s: SimpleNamespace(
            attempts=a, ledger=ledger, summary=s
        ),
    )
    result = policy.PolicyView(actions, labels).evaluate([20.0, 20.0], 0, engine)
    assert list(result.attempts.action_id) == [1, 2]
    assert list(result.ledger.action_id) == [2]


def test_crash_recovery_checkpoint_pointer_orphans_and_export(tmp_path):
    original = original_module()
    sample, stats = training_fixture()
    model, _, history = flags.train_instrumented(
        original,
        sample,
        Store(),
        {"SPXW": 10.0},
        stats,
        tmp_path,
        "cpu",
        {"files": {}, "device": "cpu"},
        epochs=4,
    )
    latest = flags.read_json(tmp_path / "latest_checkpoint.json")
    # Simulate death after epoch4 metadata, before updating the old epoch3 pointer.
    third = tmp_path / "tcn_epoch03.pt"
    flags.atomic_json(
        tmp_path / "latest_checkpoint.json",
        {
            "file": third.name,
            "metadata_sha256": flags.sha(third.with_suffix(".json")),
            "sha256": flags.sha(third),
            "epoch": 3,
        },
        replace=True,
    )
    (tmp_path / "tcn_epoch05.pt").write_bytes(b"orphan incomplete epoch")
    (tmp_path / "tcn_epoch05.json.partial").write_bytes(b"partial metadata")
    assert flags.reconcile_checkpoints(tmp_path)
    assert flags.read_json(tmp_path / "latest_checkpoint.json") == latest
    assert list((tmp_path / "recovery").glob("*/tcn_epoch05.pt"))
    assert not (tmp_path / "tcn_epoch05.pt").exists()
    # Model was durably published, but training_complete was not.
    torch.save(
        {
            "state_dict": model.cpu().state_dict(),
            "config": model.config,
            "epoch": 4,
            "seed": flags.SEED,
        },
        tmp_path / "tcn_variant.pt",
    )
    digest = flags.sha(tmp_path / "tcn_variant.pt")
    flags.export_final(tmp_path, model, history, {"files": {}})
    assert flags.sha(tmp_path / "tcn_variant.pt") == digest
    flags.export_final(tmp_path, model, history, {"files": {}})


def test_output_lock_exclusive(tmp_path):
    root = tmp_path / "run"
    with flags.output_lock(root):
        with pytest.raises(RuntimeError, match="already owned"):
            with flags.output_lock(root):
                pass
    with flags.output_lock(root):
        pass


def test_synthetic_evaluation_control_variant_seal_empty_and_resume(
    tmp_path, monkeypatch
):
    original = original_module()
    out, learner, oracle = (tmp_path / x for x in ("out", "learner", "oracle"))
    out.mkdir()
    (learner / "validation").mkdir(parents=True)
    (out / "tcn_variant.pt").write_bytes(b"synthetic immutable model")
    pd.DataFrame({"date": ["20250102"]}).to_csv(
        out / "expected_full_calendar.csv", index=False
    )
    days, hashes = [], {}
    for index, ticker in enumerate(flags.TICKERS):
        folder = oracle / ticker / "20250102"
        folder.mkdir(parents=True)
        day = SimpleNamespace(
            ticker=ticker, date="20250102", oracle=folder, key=ticker + "/20250102"
        )
        days.append(day)
        actions = pd.DataFrame(
            {"action_id": [1, 2], "state_i": [60, 61], "entry_i": [61, 62]}
        )
        labels = pd.DataFrame(
            {
                "action_id": [1, 2],
                "status": ["NO_FILL", "FILLED"],
                "exit_i": [61, 65],
                "net_base": [0.0, 10.0],
                "net_adverse": [0.0, 8.0],
                "reason": ["NO_FILL", "TARGET"],
            }
        )
        actions.to_parquet(folder / "actions.parquet", index=False)
        labels.to_parquet(folder / "labels.parquet", index=False)
        path = learner / "validation" / f"{ticker}_20250102.npz"
        np.savez_compressed(
            path, action_ids=np.array([1, 2]), tcn_teacher=np.array([6.0, 6.0])
        )
        hashes[path.name] = flags.sha(path)
    flags.atomic_json(learner / "validation/prediction_hashes.json", hashes)

    class Seal:
        def __init__(self):
            self.hashes = {}

        def check(self, day, name):
            if name == "labels.parquet":
                assert (
                    out / "validation" / f"{day.ticker}_{day.date}.prediction.json"
                ).exists()
            self.hashes[str(day.oracle / name)] = flags.sha(day.oracle / name)

    store = SimpleNamespace(hashes={}, seal=Seal())
    monkeypatch.setattr(flags, "inference", lambda *args: np.array([9.0, 9.0]))
    summary = flags.evaluate_period(
        original,
        days,
        store,
        SimpleNamespace(eval=lambda: None),
        dict.fromkeys(flags.TICKERS, 10.0),
        {},
        out,
        learner,
        "validation",
        "cpu",
    )
    assert summary["control__0"]["pooled"]["trades"] == 3
    assert summary["variant__10"]["pooled"]["trades"] == 0
    assert not summary["control__10"]["daily_gate"]["passes"]
    assert (
        flags.select_validation(summary, dict.fromkeys(flags.TICKERS, 10.0))[
            "selected_policy"
        ]
        == "control__0"
    )
    monkeypatch.setattr(
        flags, "inference", lambda *args: pytest.fail("Must reuse completed day")
    )
    again = flags.evaluate_period(
        original,
        days,
        store,
        SimpleNamespace(eval=lambda: None),
        dict.fromkeys(flags.TICKERS, 10.0),
        {},
        out,
        learner,
        "validation",
        "cpu",
    )
    assert again == summary
    # Any corruption of a completed day shard fails before reuse.
    path = out / "validation/SPXW_20250102_control__0.parquet"
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Changed bound source"):
        flags.evaluate_period(
            original,
            days,
            store,
            SimpleNamespace(eval=lambda: None),
            dict.fromkeys(flags.TICKERS, 10.0),
            {},
            out,
            learner,
            "validation",
            "cpu",
        )


def test_prepare_bindings_semantic_snapshot_and_prior_freeze_guard(tmp_path):
    learner, engine, features, out = (
        tmp_path / n for n in ("learner", "engine", "features", "out")
    )
    learner.mkdir()
    engine.mkdir()
    features.mkdir()
    schema, normalizers = semantic_fixture()
    for name, value in (
        ("normalizers.json", normalizers),
        ("feature_schema.json", schema),
        ("sampling_manifest.json", {}),
        ("summary.json", {"status": "COMPLETED"}),
    ):
        flags.atomic_json(learner / name, value)
    pd.DataFrame({"x": [1]}).to_parquet(learner / "training_sample.parquet")
    for name in (
        "train_models.py",
        "run_policy.py",
        "level_engine.py",
        "features.py",
        "build_cache.py",
    ):
        (learner / name).write_text("# synthetic fixture", encoding="utf8")
    for period in ("validation", "test"):
        (learner / period).mkdir()
        flags.atomic_json(learner / period / "prediction_hashes.json", {})
    flags.atomic_json(
        learner / "freeze.json",
        {
            "artifacts": {"normalizers.json": flags.sha(learner / "normalizers.json")},
            "script_sha256": flags.sha(learner / "train_models.py"),
        },
    )
    (engine / "index.parquet").write_bytes(b"synthetic index")
    flags.atomic_json(engine / "completion.json", {"status": "COMPLETE"})
    oracle_audit, audit_path = tmp_path / "oracle_audit.json", tmp_path / "audit.json"
    flags.atomic_json(oracle_audit, {"status": "SYNTHETIC"})
    bindings = {
        "learner_root": str(learner.resolve()),
        "learner_summary_sha256": flags.sha(learner / "summary.json"),
        "freeze_sha256": flags.sha(learner / "freeze.json"),
        "validation_prediction_manifest_sha256": flags.sha(
            learner / "validation/prediction_hashes.json"
        ),
        "test_prediction_manifest_sha256": flags.sha(
            learner / "test/prediction_hashes.json"
        ),
        "oracle_index_sha256": flags.sha(engine / "index.parquet"),
        "oracle_completion_sha256": flags.sha(engine / "completion.json"),
        "oracle_full_audit_sha256": flags.sha(oracle_audit),
    }
    flags.atomic_json(
        audit_path,
        {
            "status": "PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT",
            "binding": bindings,
        },
    )
    original = SimpleNamespace(
        require_oracle_pass=lambda *args: {"verified_files": {}},
        discover_days=lambda *args: [],
        verify_full_coverage=lambda days, folder: pd.DataFrame(
            {"date": ["20250102"]}
        ).to_csv(folder / "expected_full_calendar.csv", index=False),
    )
    flags.prepare(original, learner, engine, features, out, audit_path, oracle_audit)
    identity = flags.read_json(out / "identity.json")
    flags.verify_files(identity["files"])
    assert identity["semantic_channels"] == 64
    assert flags.sha(out / "run_tcn_flags.executed.py") == flags.sha(flags.__file__)
    assert len(flags.read_json(out / "normalization_intervention.json")) == 64
    (out / "test").mkdir()
    with pytest.raises(ValueError, match="without prior freeze"):
        flags.require_prior_freeze(out)
    flags.atomic_json(
        out / "freeze.json",
        {"files": {str(out / "normalizers.json"): flags.sha(out / "normalizers.json")}},
    )
    flags.require_prior_freeze(out)
    (out / "normalizers.json").write_text("{}")
    with pytest.raises(ValueError, match="Changed bound source"):
        flags.require_prior_freeze(out)
    (learner / "test/prediction_hashes.json").write_text('{"changed": true}')
    with pytest.raises(ValueError, match="audit binding mismatch"):
        flags.prepare(
            original,
            learner,
            engine,
            features,
            tmp_path / "new",
            audit_path,
            oracle_audit,
        )
