"""Synthetic two-policy evaluation/recovery. No real sources or model fits."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import evaluate_market_cue_control as runner
from test_market_cue_vectors import arrays


class Model:
    def __init__(self, width):
        self.width, self.calls = width, 0

    def num_feature(self):
        return self.width

    def predict(self, values, num_threads):
        assert values.shape[1] == self.width and num_threads == 4
        self.calls += 1
        return np.full(len(values), 0.02 if self.width == 1954 else 0.03)


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
        status = (
            "NO_ORIGINAL_REFERENCE_SHORT_SESSION"
            if self.row(key).close_i == 210
            else "EXACT_ORIGINAL_FULL_SESSION"
        )
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
    models = dict(zip(runner.comparison.POLICIES, (Model(1954), Model(152))))
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
        == "COMPLETE_FIXED_CUE_COMPARISON"
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
    np.testing.assert_array_equal(scores["original_net__0"], [2.0, 2.0])
    np.testing.assert_array_equal(scores["cue_net__0"], [3.0, 3.0])
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


def test_original_reference_scores_bitexact_state_and_hash_checks(tmp_path):
    root = tmp_path / "original"
    root.mkdir()
    dayroot = tmp_path / "original_engine_day"
    dayroot.mkdir()
    actions = pd.DataFrame(dict(action_id=[4, 2], state_i=[60, 61]))
    action_path = dayroot / "actions.parquet"
    actions.to_parquet(action_path, index=False)
    hashes = {}

    def verify(path, digest):
        assert runner.sha(path) == digest
        hashes[str(path)] = digest

    original = SimpleNamespace(
        original=root,
        verify=verify,
        index=pd.DataFrame(
            [
                dict(
                    ticker="SPY",
                    date="20250102",
                    status="COMPLETE",
                    day_root=str(dayroot),
                    actions_sha256=runner.sha(action_path),
                )
            ]
        ).set_index(["ticker", "date"]),
    )
    binding = {}
    expected = np.array([1.0, 2.0], np.float64)
    for period in ("validation", "test"):
        folder = root / period
        folder.mkdir()
        prediction = folder / "SPY_20250102.npz"
        np.savez(prediction, action_ids=actions.action_id.to_numpy(), gbt_net=expected)
        manifest = folder / "prediction_hashes.json"
        runner.atomic_json(manifest, {prediction.name: runner.sha(prediction)})
        binding[period + "_prediction_manifest_sha256"] = runner.sha(manifest)
    audit = tmp_path / "audit.json"
    runner.atomic_json(audit, {"binding": binding})
    reference = runner.OriginalScores(original, audit)
    proof, sources = reference.compare("SPY/20250102", 390, actions, expected)
    assert proof["bitexact_checked"] and len(sources) == 3
    changed = expected.copy()
    changed[0] = np.nextafter(changed[0], np.inf)
    with pytest.raises(ValueError, match="not bitexact"):
        reference.compare("SPY/20250102", 390, actions, changed)
    wrong_state = actions.copy()
    wrong_state.loc[0, "state_i"] = 62
    with pytest.raises(ValueError, match="state order"):
        reference.compare("SPY/20250102", 390, wrong_state, expected)
    proof, sources = reference.compare("QQQ/20251128", 210, actions, expected)
    assert proof["status"] == "NO_ORIGINAL_REFERENCE_SHORT_SESSION" and not sources
