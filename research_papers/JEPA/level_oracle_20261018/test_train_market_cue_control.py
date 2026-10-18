"""Synthetic doubles only: no LightGBM training, source market files or GPU."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import train_market_cue_control as runner
from test_market_cue_vectors import arrays


class Source:
    def __init__(self, root):
        self.calls = 0
        self.path = root / "source_identity.txt"
        self.path.write_text("synthetic original authority", encoding="utf-8")
        self.hashes = {str(self.path): runner.sha(self.path)}
        self.scales = dict(SPY=100.0, QQQ=200.0, SPXW=1000.0)
        self.sample = pd.DataFrame(
            dict(
                sample_i=np.arange(6),
                day_key=["SPY/20230103"] * 3 + ["QQQ/20230104"] * 3,
                ticker=["SPY"] * 3 + ["QQQ"] * 3,
                date=["20230103"] * 3 + ["20230104"] * 3,
                action_id=[5, 9, 11] * 2,
                state_i=[60, 60, 61] * 2,
                net_base=[1.0, 0.0, -2.0, 3.0, 0.0, -1.0],
                weight=[0.5, 1.5, 1.0, 2.0, 0.5, 0.5],
                status=["FILLED", "NO_FILL", "FILLED"] * 2,
            )
        )

    def verify(self, path, digest):
        assert runner.sha(path) == digest
        self.hashes[str(path)] = digest

    def recheck(self):
        for path, digest in self.hashes.items():
            self.verify(path, digest)

    def day(self, key):
        self.calls += 1
        pack = arrays()
        pack["state_i"] = np.array([60, 61])
        pack["action_features"] = np.concatenate(
            [pack["action_features"], pack["action_features"][:1]]
        )
        ids = np.array([11, 5, 9])
        offered = pd.DataFrame(dict(action_id=[5, 9, 11], state_i=[60, 60, 61]))
        return pack, ids, offered, self.hashes.copy()


class Model:
    def __init__(self, fits):
        self.fits = fits
        self.booster_ = self

    def fit(self, x, y, sample_weight):
        self.fits.append((np.array(x), y.copy(), sample_weight.copy()))

    def num_feature(self):
        return 152

    def save_model(self, path):
        Path(path).write_text("synthetic completed model", encoding="utf-8")


def test_code_snapshots_rechecked_before_checkpoint(tmp_path, monkeypatch):
    source = Source(tmp_path)
    script = tmp_path / "synthetic_module.py"
    script.write_text("immutable implementation", encoding="utf-8")
    monkeypatch.setattr(runner, "__file__", str(script))
    expected = {script.name: runner.sha(script)}
    output = tmp_path / "out"
    runner.bind_code_snapshots(source, output, expected)
    runner.bind_code_snapshots(source, output, expected)
    snapshot = output / "code_snapshot" / script.name
    assert snapshot.read_bytes() == script.read_bytes()
    snapshot.write_text("changed snapshot", encoding="utf-8")
    with pytest.raises(AssertionError):
        source.recheck()
    with pytest.raises(AssertionError):
        runner.bind_code_snapshots(source, output, expected)


def test_independent_review_pins_audits_before_loader(tmp_path):
    learner, engine = tmp_path / "learner.json", tmp_path / "engine.json"
    learner.write_text('{"status":"synthetic passed"}', encoding="utf-8")
    engine.write_text('{"status":"synthetic engine"}', encoding="utf-8")
    review = {
        "authorities": {
            "learner_audit_sha256": runner.sha(learner),
            "engine_audit_sha256": runner.sha(engine),
        }
    }
    runner.verify_review_authorities(review, learner, engine)
    learner.write_text('{"status":"coherent replacement"}', encoding="utf-8")
    with pytest.raises(ValueError, match="independently reviewed"):
        runner.verify_review_authorities(review, learner, engine)
    with pytest.raises(ValueError, match="independently reviewed"):
        runner.verify_review_authorities({}, learner, engine)


def test_exact_sample_weights_targets_join_and_completed_model_no_refit(tmp_path):
    source = Source(tmp_path)
    runner.validate_sample(source.sample, 6)
    checkpoints = runner.Checkpoints(tmp_path / "out", "frozen")
    fits, gates = [], []
    path = runner.fit_control_once(
        source, checkpoints, lambda: Model(fits), lambda: gates.append(True)
    )
    assert path.exists() and source.calls == 2 and len(fits) == len(gates) == 1
    np.testing.assert_array_equal(
        fits[0][1], source.sample.net_base / source.sample.ticker.map(source.scales)
    )
    np.testing.assert_array_equal(fits[0][2], source.sample.weight)
    assert fits[0][0].shape == (6, 152)
    runner.fit_control_once(
        source,
        checkpoints,
        lambda: pytest.fail("refit"),
        lambda: pytest.fail("gate on complete model"),
    )
    assert source.calls == 2
    source.path.write_text("changed input", encoding="utf-8")
    with pytest.raises(AssertionError):
        runner.fit_control_once(
            source, checkpoints, lambda: pytest.fail("refit"), lambda: None
        )


def test_completed_chunks_survive_matrix_interruption_without_reextract(
    tmp_path, monkeypatch
):
    source = Source(tmp_path)
    checkpoints = runner.Checkpoints(tmp_path / "out", "frozen")
    original = runner.np.lib.format.open_memmap
    monkeypatch.setattr(
        runner.np.lib.format,
        "open_memmap",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("power failure")),
    )
    with pytest.raises(RuntimeError, match="power"):
        runner.prepare_matrix(source, checkpoints)
    assert source.calls == 2 and not checkpoints.complete("matrix")
    monkeypatch.setattr(runner.np.lib.format, "open_memmap", original)
    runner.prepare_matrix(source, checkpoints)
    assert source.calls == 2 and checkpoints.complete("matrix")


def test_wrong_state_join_is_not_silently_converted_to_array_position(tmp_path):
    source = Source(tmp_path)
    source.sample.loc[0, "state_i"] = 61
    with pytest.raises(ValueError, match="does not match"):
        runner.prepare_matrix(source, runner.Checkpoints(tmp_path / "out", "frozen"))


def test_interrupted_fit_preserves_started_marker_and_refuses_automatic_refit(tmp_path):
    source = Source(tmp_path)
    checkpoints = runner.Checkpoints(tmp_path / "out", "frozen")
    with pytest.raises(RuntimeError, match="failure"):
        runner.fit_control_once(
            source,
            checkpoints,
            lambda: (_ for _ in ()).throw(RuntimeError("fit failure")),
            lambda: None,
        )
    assert (checkpoints.root / "fit_started.json").exists()
    assert not checkpoints.complete("model")
    with pytest.raises(ValueError, match="Interrupted fit"):
        runner.fit_control_once(
            source, checkpoints, lambda: pytest.fail("unexpected refit"), lambda: None
        )


def test_sample_order_and_missing_fill_targets_enforced(tmp_path):
    source = Source(tmp_path)
    changed = source.sample.copy()
    changed.loc[0, "sample_i"] = 2
    with pytest.raises(ValueError, match="order"):
        runner.validate_sample(changed, 6)
    changed = source.sample.copy()
    changed.loc[1, "net_base"] = 1
    with pytest.raises(ValueError, match="NO_FILL"):
        runner.validate_sample(changed, 6)


def test_ram_and_commit_gate_waits_for_both_without_real_resource_read(monkeypatch):
    values = iter(
        [
            (13 * 1024**3, 15 * 1024**3),
            (11 * 1024**3, 17 * 1024**3),
            (12 * 1024**3, 16 * 1024**3),
        ]
    )
    sleeps = []
    monkeypatch.setattr(runner, "resource_snapshot", lambda: next(values))
    monkeypatch.setattr(runner.time, "sleep", lambda seconds: sleeps.append(seconds))
    runner.wait_resources()
    assert sleeps == [30, 30]


def test_prediction_preserves_all_offers_and_fixed_scale_without_outcomes(tmp_path):
    source = Source(tmp_path)
    pack, ids, offered, _ = source.day("SPY/20230103")

    class Predictor:
        def num_feature(self):
            return 152

        def predict(self, x, num_threads):
            assert num_threads == 4
            return x[:, 0].astype(float) - 0.25

    pred = runner.predict_offered_day(Predictor(), pack, ids, offered, 100.0, block=2)
    np.testing.assert_array_equal(pred["action_id"], offered.action_id)
    np.testing.assert_array_equal(pred["state_i"], offered.state_i)
    assert pred["scores"].dtype == np.float64 and len(pred["scores"]) == 3
    assert set(pred) == {"action_id", "state_i", "scores"}
