from pathlib import Path
import json

import numpy as np
import pandas as pd
import pytest

import train_common_greek_control as trainer


def fixture_inputs(tmp_path, *, bad_prefix=False, wrong_ids=False, bad_targets=False):
    features, cue, learner = [
        tmp_path / name for name in ("features", "cue", "learner")
    ]
    for path in (features, cue, learner):
        path.mkdir()
    n = 400
    rng = np.random.default_rng(7)
    x = rng.normal(size=(n, 424)).astype(np.float32)
    base = x[:, :152].copy()
    if bad_prefix:
        x[0, 0] += 1
    np.save(features / "train_x.npy", x)
    np.save(cue / "train_x.npy", base)
    sample = pd.DataFrame(
        dict(
            sample_i=np.arange(n),
            day_key=["SPY/20230103"] * n,
            ticker=["SPY"] * n,
            date=["20230103"] * n,
            action_id=np.arange(n) + 5,
            state_i=np.arange(n) % 316 + 60,
            weight=np.ones(n),
            net_base=rng.normal(size=n),
        )
    )
    sample.to_parquet(learner / "training_sample.parquet", index=False)
    keys = {
        name: sample[name].to_numpy(
            dtype=str if name in ("ticker", "date", "day_key") else None
        )
        for name in trainer.KEYS
    }
    if wrong_ids:
        keys["action_id"] = keys["action_id"][::-1]
    np.savez(features / "row_keys.npz", **keys)
    y = sample.net_base.to_numpy() / 81
    if bad_targets:
        y[0] += 1
    np.savez(cue / "targets.npz", y=y, weight=np.ones(n), sample_i=np.arange(n))
    columns = [f"f{i}" for i in range(152)] + list(trainer.dynamic.FEATURE_NAMES)
    trainer.original.atomic_json(features / "coverage.json", dict(fixture=True))
    sample_map = {
        str(learner / "training_sample.parquet"): trainer.sha(
            learner / "training_sample.parquet"
        )
    }
    for root, contract in (
        (
            cue,
            dict(
                config=trainer.original.CONFIG,
                scales=dict(SPY=81, QQQ=88, SPXW=680),
                schema=dict(column_names=columns[:152]),
            ),
        ),
        (
            features,
            dict(
                columns=columns,
                sources=sample_map,
                train_only=True,
                fit_authorized=False,
                close_i=390,
                rows=n,
            ),
        ),
    ):
        trainer.original.atomic_json(root / "run_contract.json", contract)
        binding = trainer.sha(root / "run_contract.json")
        members = (
            ["train_x.npy", "row_keys.npz", "coverage.json"]
            if root == features
            else ["train_x.npy", "targets.npz"]
        )
        trainer.original.Checkpoints(root, binding).finish(
            "matrix",
            [root / name for name in members],
            {"sources" if root == features else "source_hashes": sample_map},
        )
    (cue / "cue_net.txt").write_bytes(b"frozen control")
    trainer.original.atomic_json(cue / "fit_started.json", dict(fixture=True))
    trainer.original.Checkpoints(cue, trainer.sha(cue / "run_contract.json")).finish(
        "model",
        [cue / "cue_net.txt", cue / "matrix.complete.json", cue / "fit_started.json"],
    )
    authorities = {
        str(path): trainer.sha(path)
        for path in [
            features / "run_contract.json",
            features / "matrix.complete.json",
            cue / "run_contract.json",
            cue / "matrix.complete.json",
            cue / "model.complete.json",
        ]
    }
    return (features, cue, learner, authorities), n


def test_exact_training_sources_targets_ids_and_prefix(tmp_path):
    args, n = fixture_inputs(tmp_path)
    source = trainer.TrainingInputs(*args, expected_rows=n)
    assert len(source.columns) == 424
    assert source.scales == dict(SPY=81, QQQ=88, SPXW=680)
    assert source.y.shape == source.weights.shape == (n,)
    source.recheck()
    (args[1] / "cue_net.txt").write_bytes(b"mutated")
    with pytest.raises(ValueError, match="Source authority"):
        source.recheck()


@pytest.mark.parametrize(
    "flag, message",
    [
        ("bad_prefix", "Prefix"),
        ("wrong_ids", "Row key"),
        ("bad_targets", "Targets/IPW"),
    ],
)
def test_invalid_join_or_values_rejected_even_when_resealed(tmp_path, flag, message):
    args, n = fixture_inputs(tmp_path, **{flag: True})
    with pytest.raises(ValueError, match=message):
        trainer.TrainingInputs(*args, expected_rows=n)


def test_real_export_readback_and_recovery_without_refit(tmp_path, monkeypatch):
    args, n = fixture_inputs(tmp_path)
    source = trainer.TrainingInputs(*args, expected_rows=n)
    out = tmp_path / "output"
    out.mkdir()
    trainer.original.atomic_json(out / "run_contract.json", dict(fixture=True))
    evidence = trainer.original.Checkpoints(out, trainer.sha(out / "run_contract.json"))
    finish = evidence.finish

    def injected(name, paths, extra=None):
        if name == "model":
            raise RuntimeError("after verified export")
        finish(name, paths, extra)

    monkeypatch.setattr(evidence, "finish", injected)
    with pytest.raises(RuntimeError, match="verified export"):
        trainer.fit_once(source, evidence, resource_gate=lambda: None)
    assert evidence.complete("export")
    before = trainer.sha(out / "common_greek_net.txt")
    monkeypatch.setattr(evidence, "finish", finish)

    def forbidden():
        raise AssertionError("No refit permitted")

    trainer.fit_once(source, evidence, factory=forbidden, resource_gate=forbidden)
    assert evidence.complete("model")
    trainer.fit_once(source, evidence, factory=forbidden, resource_gate=forbidden)
    assert trainer.sha(out / "common_greek_net.txt") == before
    predictions = np.load(out / "train_readback_predictions.npy")
    predictions[0] += 1
    np.save(out / "train_readback_predictions.npy", predictions)
    with pytest.raises(ValueError, match="prediction differs"):
        trainer.readback(source, evidence)
    with pytest.raises(ValueError, match="Changed checkpoint"):
        trainer.fit_once(source, evidence, factory=forbidden, resource_gate=forbidden)


def test_unfinished_fit_not_repeated_and_output_separate(tmp_path):
    args, n = fixture_inputs(tmp_path)
    source = trainer.TrainingInputs(*args, expected_rows=n)
    out = tmp_path / "output"
    out.mkdir()
    trainer.original.atomic_json(out / "fit_started.json", dict(interrupted=True))
    with pytest.raises(ValueError, match="automatic refit forbidden"):
        trainer.fit_once(source, trainer.original.Checkpoints(out, "binding"))
    for target in (args[0], args[0] / "subdir", tmp_path):
        with pytest.raises(ValueError, match="overlaps"):
            trainer.separate(target, [args[0]])
    trainer.separate(out, [Path(args[0])])


@pytest.mark.parametrize(
    "root_index, marker_name, omitted",
    [
        (0, "matrix.complete.json", "row_keys.npz"),
        (1, "matrix.complete.json", "targets.npz"),
        (1, "model.complete.json", "cue_net.txt"),
    ],
)
def test_manifest_must_include_consumed_member(
    tmp_path, root_index, marker_name, omitted
):
    args, n = fixture_inputs(tmp_path)
    marker = args[root_index] / marker_name
    record = trainer.read_json(marker)
    del record["files"][omitted]
    marker.write_text(json.dumps(record), encoding="utf-8")
    args[3][str(marker)] = trainer.sha(marker)
    with pytest.raises(ValueError, match="omits consumed"):
        trainer.TrainingInputs(*args, expected_rows=n)
