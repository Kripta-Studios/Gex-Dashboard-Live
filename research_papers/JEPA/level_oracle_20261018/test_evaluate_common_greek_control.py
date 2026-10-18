"""Synthetic two-policy evaluation/recovery. No real sources or model fits."""

from types import SimpleNamespace
import json

import numpy as np
import pandas as pd
import pytest

import evaluate_common_greek_control as runner
from test_market_cue_vectors import arrays
from test_common_greek_dynamics import raw_fixture


class Model:
    def __init__(self, width):
        self.width, self.calls = width, 0

    def num_feature(self):
        return self.width

    def predict(self, values, num_threads):
        assert values.shape[1] == self.width and num_threads == 4
        self.calls += 1
        return np.full(len(values), 0.02 if self.width == 152 else 0.03)


class Source:
    def __init__(self, root, evidence):
        self.path = root / "audited_feature_fixture.txt"
        self.path.write_text("fixed input", encoding="utf-8")
        self.hashes = {str(self.path): runner.sha(self.path)}
        self.evidence = evidence
        self.feature_calls = self.label_calls = 0

    def keys(self, year):
        return [f"{ticker}/{year}0102" for ticker in ("SPXW", "SPY", "QQQ")] + (
            ["SPY/20260401"] if year == 2026 else []
        )

    def row(self, key):
        return SimpleNamespace(
            status="MISSING_SOURCE" if key.endswith("20260401") else "COMPLETE",
            close_i=210 if key.startswith("QQQ") else 390,
        )

    def feature_day(self, key):
        self.feature_calls += 1
        pack = arrays()
        pack["state_i"] = np.array([60, 61])
        pack["dynamics272"] = np.zeros((2, 272), np.float32)
        pack["maps"] = np.zeros((2, 20, 5, 64), np.float32)
        pack["map_mask"] = np.zeros((2, 20, 5), bool)
        actions = pd.DataFrame(dict(action_id=[2, 1], state_i=[60, 61]))
        return pack, np.array([1, 2]), actions, self.hashes

    def labels(self, key):
        assert self.evidence.complete("predictions/" + key)
        saved = self.evidence.root / ("predictions/" + key + ".npz")
        with np.load(saved, allow_pickle=False) as arrays:
            assert set(runner.comparison.POLICIES).issubset(arrays.files)
        self.label_calls += 1
        return pd.DataFrame(
            dict(
                action_id=[1, 2],
                status=["FILLED", "NO_FILL"],
                exit_i=[64, 61],
                net_base=[5.0, 0.0],
                net_adverse=[4.0, 0.0],
            )
        ), self.hashes

    def reference_control(self, key, actions, score):
        status = "EXACT_AUDITED_CUE_ALL_SESSIONS"
        return {"status": status, "synthetic_double": True}, {}

    def recheck(self):
        for path, digest in self.hashes.items():
            assert runner.sha(path) == digest


def setup(tmp_path):
    evidence = runner.Evidence(tmp_path / "out", "frozen two models before labels")
    runner.atomic_json(
        evidence.root / "freeze.json",
        {"synthetic_fixed_models": list(runner.comparison.POLICIES)},
    )
    evidence.binding = runner.sha(evidence.root / "freeze.json")
    source = Source(tmp_path, evidence)
    models = dict(zip(runner.comparison.POLICIES, (Model(152), Model(424))))
    scales = dict(SPXW=1000.0, SPY=100.0, QQQ=200.0)
    return source, models, scales, evidence


def test_two_policies_all_clocks_sealed_before_labels_complete_resume(tmp_path):
    source, models, scales, evidence = setup(tmp_path)
    with pytest.raises(ValueError, match="2025 first"):
        runner.evaluate_period(2026, source, models, scales, evidence, source.hashes)
    first = runner.evaluate_period(
        2025, source, models, scales, evidence, source.hashes
    )
    assert not runner.complete_comparison(evidence)
    second = runner.evaluate_period(
        2026, source, models, scales, evidence, source.hashes
    )
    assert runner.complete_comparison(evidence)
    assert runner.complete_comparison(evidence)
    assert (
        runner.read_json(evidence.root / "completion.json")["status"]
        == "COMPLETE_FIXED_COMMON_GREEK_COMPARISON"
    )
    assert first["winner_selected"] is None and second["winner_selected"] is None
    for policy in runner.comparison.POLICIES:
        assert first["policies"][policy]["ALL"]["coverage"]["universal_daily_pass"]
        report = second["policies"][policy]["ALL"]
        assert report["available_economics"]["net_base"] == 15
        assert report["coverage"]["universal_daily_status"] == "NO_EVALUABLE"
        assert report["coverage"]["observable_daily_pass"]
        assert (
            sum(row["n"] for row in report["calibration"]["all_offers_action_weighted"])
            == 6
        )
        assert sum(row["n"] for row in report["calibration"]["selected_attempts"]) == 6
        assert sum(row["n"] for row in report["calibration"]["selected_fills"]) == 3
    calls = (
        source.feature_calls,
        source.label_calls,
        tuple(model.calls for model in models.values()),
    )
    assert (
        runner.evaluate_period(2025, source, models, scales, evidence, source.hashes)
        == first
    )
    assert (
        runner.evaluate_period(2026, source, models, scales, evidence, source.hashes)
        == second
    )
    assert calls == (
        source.feature_calls,
        source.label_calls,
        tuple(model.calls for model in models.values()),
    )
    source.path.write_text(
        "coherent changed input after completed period", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Changed checkpoint input"):
        runner.evaluate_period(2025, source, models, scales, evidence, source.hashes)


def test_interrupted_daily_reuses_both_predictions_and_preserves_partial(
    tmp_path, monkeypatch
):
    source, models, scales, evidence = setup(tmp_path)
    key = source.keys(2025)[0]
    canonical = runner.comparison.schedule

    def interrupted(*args):
        raise RuntimeError("synthetic interruption after predictions")

    monkeypatch.setattr(runner.comparison, "schedule", interrupted)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        runner.evaluate_day(key, source, models, scales, evidence, source.hashes)
    assert source.feature_calls == 1 and evidence.complete("predictions/" + key)
    partial = evidence.root / ("days/" + key + ".json")
    partial.write_text('{"fabricated_partial_net":999999999}', encoding="utf-8")
    monkeypatch.setattr(runner.comparison, "schedule", canonical)
    result = runner.evaluate_day(key, source, models, scales, evidence, source.hashes)
    assert source.feature_calls == 1
    assert all(result[policy]["net_base"] == 5 for policy in runner.comparison.POLICIES)
    assert len(list((evidence.root / "preserved_orphans").rglob("*.json"))) == 1


def test_prediction_bitexact_control_scale_and_offered_join(tmp_path):
    source, models, scales, _ = setup(tmp_path)
    pack, ids, actions, _ = source.feature_day("SPY/20250102")
    scores = runner.predict_both(pack, ids, actions, models, scales["SPY"])
    np.testing.assert_array_equal(scores["cue_net__0"], [2.0, 2.0])
    np.testing.assert_array_equal(scores["common_greek_net__0"], [3.0, 3.0])
    assert set(scores) == set(runner.comparison.POLICIES)
    actions.loc[0, "state_i"] = 62
    with pytest.raises(ValueError, match="does not match"):
        runner.predict_both(pack, ids, actions, models, scales["SPY"])


def test_coherent_feature_replacement_before_first_load_rejected(tmp_path):
    source = runner.SessionInputs.__new__(runner.SessionInputs)
    source.hashes = {}
    source.paths = [
        "features_path",
        "features_meta_path",
        "action_features_path",
        "action_features_meta_path",
    ]
    source.digests = [
        "features_sha256",
        "features_meta_sha256",
        "action_features_sha256",
        "action_features_meta_sha256",
    ]
    record = dict(status="COMPLETE")
    for field, digest in zip(source.paths, source.digests):
        path = tmp_path / field
        path.write_text("original audited bytes", encoding="utf-8")
        record[field], record[digest] = str(path), runner.sha(path)
    source.index = pd.DataFrame(
        [dict(ticker="SPY", date="20250102", **record)]
    ).set_index(["ticker", "date"])
    # Even coherent replacement of NPZ and its metadata cannot establish a new baseline.
    for field in source.paths:
        (tmp_path / field).write_text("replacement bytes", encoding="utf-8")
    with pytest.raises(ValueError, match="differs from authority"):
        source.feature_day("SPY/20250102")
    assert not source.hashes


def test_prediction_marker_cannot_omit_consumed_npz(tmp_path):
    source, models, scales, evidence = setup(tmp_path)
    key = source.keys(2025)[0]
    dummy = evidence.root / "unrelated.txt"
    dummy.write_text("unrelated", encoding="utf-8")
    evidence.finish("predictions/" + key, [dummy], {"sources": source.hashes})
    with pytest.raises(ValueError, match="omits consumed"):
        runner.evaluate_day(key, source, models, scales, evidence, source.hashes)
    assert source.feature_calls == source.label_calls == 0


def test_short211_padding_exact_and_future_tail_invariant():
    raw = raw_fixture()
    short = {
        name: value[:211].copy()
        if name
        in (
            "time_ns",
            "spot",
            "spot_valid",
            "row_flags",
            "iv",
            "delta",
            "vega",
            "theta",
        )
        else value.copy()
        for name, value in raw.items()
    }
    padded = runner.raw_for_dynamics(short, 210)
    for name in (
        "time_ns",
        "spot",
        "spot_valid",
        "row_flags",
        "iv",
        "delta",
        "vega",
        "theta",
    ):
        assert padded[name][:211].tobytes() == short[name].tobytes()
    assert not padded["row_flags"][211:].any() and not padded["spot_valid"][211:].any()
    assert np.isnan(padded["spot"][211:]).all()
    states = np.arange(60, 196)
    expected = runner.dynamic.encode_states(
        runner.dynamic.prepare_day(raw, close_i=210), states
    )
    actual = runner.dynamic.encode_states(
        runner.dynamic.prepare_day(padded, close_i=210), states
    )
    assert actual.tobytes() == expected.tobytes()
    for field in ("spot", "iv", "delta", "vega", "theta"):
        raw[field][196:] *= 100
    perturbed = runner.dynamic.encode_states(
        runner.dynamic.prepare_day(raw, close_i=210), states
    )
    assert perturbed.tobytes() == actual.tobytes()
    with pytest.raises(ValueError, match="Unknown physical close"):
        runner.raw_for_dynamics(short, 211)


def test_dynamic_join_prefix_and_control_prediction_identical(tmp_path):
    source, models, scales, _ = setup(tmp_path)
    pack, ids, actions, _ = source.feature_day("SPY/20250102")
    pack["dynamics272"][:] = np.arange(2)[:, None]
    cue_pack = {
        k: v for k, v in pack.items() if k not in ("maps", "map_mask", "dynamics272")
    }
    control = runner.training.predict_offered_day(
        models[runner.POLICIES[0]], cue_pack, ids, actions, scales["SPY"]
    )["scores"]

    class Inspect(Model):
        def predict(self, x, num_threads):
            assert x.shape == (2, 424)
            # Actions are offered [ID2/state60, ID1/state61], not pack order.
            np.testing.assert_array_equal(
                x[:, 152:], np.broadcast_to([[0], [1]], (2, 272))
            )
            ai, si = runner.vectors.join_action_rows(
                reference_action_ids=actions.action_id.to_numpy(),
                reference_state_i=actions.state_i.to_numpy(),
                pack_action_ids=ids,
                offered_action_ids=actions.action_id.to_numpy(),
                offered_state_i=actions.state_i.to_numpy(),
                pack_state_i=pack["state_i"],
            )
            prefix = runner.fast.vectorize_rows(
                **cue_pack, action_positions=ai, state_positions=si
            )
            assert x[:, :152].tobytes() == prefix.tobytes()
            return np.array([0.1, 0.2], np.float32)

    models[runner.POLICIES[1]] = Inspect(424)
    scored = runner.predict_both(pack, ids, actions, models, scales["SPY"])
    assert scored[runner.POLICIES[0]].tobytes() == control.tobytes()
    np.testing.assert_array_equal(
        scored[runner.POLICIES[1]],
        np.array([0.1, 0.2], np.float32).astype(np.float64) * 100,
    )


def cue_authority(tmp_path, close_i):
    root = tmp_path / "prior"
    root.mkdir()
    runner.atomic_json(root / "freeze.json", {"fixed": True})
    binding = runner.sha(root / "freeze.json")
    evidence = runner.Evidence(root, binding)
    key = "SPY/20250703" if close_i == 210 else "SPY/20250102"
    path = root / ("predictions/" + key + ".npz")
    runner.save_npz(
        path,
        action_id=np.array([2, 1]),
        state_i=np.array([60, 61]),
        cue_net__0=np.array([2.0, 3.0]),
    )
    evidence.finish("predictions/" + key, [path], dict(sources={}, outcomes_read=False))
    runner.atomic_json(
        root / "completion.json", dict(status="COMPLETE_FIXED_CUE_COMPARISON")
    )
    evidence.finish(
        "comparison",
        [
            root / "freeze.json",
            root / "completion.json",
            path,
            evidence.marker("predictions/" + key),
        ],
        dict(sources={}),
    )
    audit = tmp_path / "audit.json"
    runner.atomic_json(
        audit,
        dict(
            status="PASS_INDEPENDENT_MARKET_CUE_COMPARISON_ECONOMIC_AUDIT",
            binding=dict(
                comparison_root=str(root),
                freeze_sha256=binding,
                completion_sha256=runner.sha(root / "completion.json"),
                comparison_complete_sha256=runner.sha(evidence.marker("comparison")),
            ),
        ),
    )
    return root, audit, key, path


@pytest.mark.parametrize("close_i", [210, 390])
def test_baseline_cue_exact_for_full_and_short_before_labels(tmp_path, close_i):
    root, audit, key, path = cue_authority(tmp_path, close_i)
    baseline = runner.CueScores(root, audit, runner.sha(audit))
    actions = pd.DataFrame(dict(action_id=[2, 1], state_i=[60, 61]))
    proof, _ = baseline.compare(key, close_i, actions, np.array([2.0, 3.0]))
    assert (
        proof["bitexact_checked"]
        and proof["status"] == "EXACT_AUDITED_CUE_ALL_SESSIONS"
    )
    with pytest.raises(ValueError, match="not bitexact"):
        baseline.compare(key, close_i, actions, np.array([2.0, 3.0], np.float32))
    with pytest.raises(ValueError, match="order differs"):
        baseline.compare(key, close_i, actions.iloc[::-1], np.array([2.0, 3.0]))
    path.write_bytes(b"coherent replacement after audit")
    with pytest.raises(ValueError, match="differs from authority"):
        baseline.compare(key, close_i, actions, np.array([2.0, 3.0]))


def test_incomplete_or_changed_baseline_audit_rejected(tmp_path):
    root, audit, _, _ = cue_authority(tmp_path, 390)
    digest = runner.sha(audit)
    changed = runner.read_json(audit)
    changed["status"] = "INCOMPLETE"
    audit.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from authority"):
        runner.CueScores(root, audit, digest)
    with pytest.raises(ValueError, match="audit required"):
        runner.CueScores(root, audit, runner.sha(audit))


def test_session_raw_cache_binding_and_short_adapter(tmp_path, monkeypatch):
    raw = raw_fixture()
    for name in (
        "time_ns",
        "spot",
        "spot_valid",
        "row_flags",
        "iv",
        "delta",
        "vega",
        "theta",
    ):
        raw[name] = raw[name][:211]
    path, meta = tmp_path / "raw.npz", tmp_path / "raw.json"
    runner.save_npz(path, **raw)
    runner.atomic_json(
        meta, dict(ticker="SPY", date="20250703", sha256=runner.sha(path))
    )
    source = runner.SessionInputs.__new__(runner.SessionInputs)
    source.hashes = {}
    source.index = pd.DataFrame(
        [
            dict(
                ticker="SPY",
                date="20250703",
                close_i=210,
                cache_npz_sha256=runner.sha(path),
                cache_meta_sha256=runner.sha(meta),
            )
        ]
    ).set_index(["ticker", "date"])
    source.cache_paths = pd.DataFrame(
        [
            dict(
                ticker="SPY",
                date="20250703",
                cache_path=str(path),
                cache_meta_path=str(meta),
            )
        ]
    ).set_index(["ticker", "date"])
    pack = arrays()
    pack["state_i"] = np.array([60, 195])
    actions = pd.DataFrame(dict(action_id=[1, 2], state_i=[60, 195]))
    monkeypatch.setattr(
        runner.previous.SessionInputs,
        "feature_day",
        lambda self, key: (dict(pack), np.array([1, 2]), actions, {}),
    )
    loaded, _, _, hashes = source.feature_day("SPY/20250703")
    assert loaded["dynamics272"].shape == (2, 272) and len(hashes) == 2
    expected = runner.dynamic.encode_states(
        runner.dynamic.prepare_day(runner.raw_for_dynamics(raw, 210), close_i=210),
        np.array([60, 195]),
    )
    assert loaded["dynamics272"].tobytes() == expected.tobytes()
    path.write_bytes(b"coherent raw replacement")
    meta.write_text(
        json.dumps(dict(ticker="SPY", date="20250703", sha256=runner.sha(path))),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="differs from authority"):
        source.feature_day("SPY/20250703")


def test_trained_contract_requires_exact_prefix_target_scope_and_scales():
    import copy

    control = dict(
        config=runner.training.CONFIG,
        scales=dict(SPY=81, SPXW=680, QQQ=88),
        training_rows=270377,
        schema=dict(column_names=list(runner.vectors.COLUMN_NAMES)),
    )
    trained = dict(
        config=runner.training.CONFIG,
        scales=dict(control["scales"]),
        rows=270377,
        train_only=True,
        control_model_refitted=False,
        schema=dict(
            column_names=[*runner.vectors.COLUMN_NAMES, *runner.dynamic.FEATURE_NAMES]
        ),
    )
    runner.validate_trained_contract(trained, control)
    for field, value in (
        ("rows", 270378),
        ("train_only", False),
        ("control_model_refitted", True),
    ):
        changed = copy.deepcopy(trained)
        changed[field] = value
        with pytest.raises(ValueError, match="scope differs"):
            runner.validate_trained_contract(changed, control)
    changed = copy.deepcopy(trained)
    changed["schema"]["column_names"][0] = "future_label"
    with pytest.raises(ValueError, match="schema differs"):
        runner.validate_trained_contract(changed, control)


def test_bulk_training_provenance_pinned_manifest_and_final_mutation(tmp_path):
    path = tmp_path / "TRAIN.bin"
    path.write_bytes(b"synthetic admitted training input")
    expected = runner.sha(path)
    provenance = runner.TrainingProvenance()
    provenance.verify(path, expected)
    manifest = tmp_path / "training_provenance.json"
    digest = runner.seal_training_provenance(provenance, manifest)
    assert runner.seal_training_provenance(provenance, manifest) == digest
    assert runner.read_json(manifest)["files"] == {str(path.resolve()): expected}
    provenance.recheck()
    path.write_bytes(b"changed after admission")
    with pytest.raises(ValueError, match="differs from authority"):
        provenance.recheck()
    # A future resume cannot silently baseline the replacement against new bytes.
    resumed = runner.TrainingProvenance()
    with pytest.raises(ValueError, match="differs from authority"):
        resumed.verify(path, expected)
