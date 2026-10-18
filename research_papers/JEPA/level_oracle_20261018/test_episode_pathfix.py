"""Repair proof: only source-manifest paths differ; predictions/actions unchanged."""

from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import train_episode_model as producer  # noqa: E402
import resume_episode_pathfix as repair  # noqa: E402


def test_four_path_repair_reproduces_original_predictions_with_correct_day_file(
    tmp_path, monkeypatch
):
    original, features, oracle, ep_root, out = [
        tmp_path / name
        for name in ("original", "features", "oracle", "episodes", "out")
    ]
    for path in (
        original / "validation",
        features,
        oracle,
        ep_root / "SPY/20250102",
        out,
        out / "old",
        out / "repaired",
    ):
        path.mkdir(parents=True, exist_ok=True)
    for name in ("features.npz", "features.json", "actions.npz", "actions.json"):
        (features / name).write_bytes(name.encode())
    for name in ("episodes.npz", "episodes.json"):
        (ep_root / "SPY/20250102" / name).write_bytes(name.encode())
    actions = pd.DataFrame({"action_id": [7, 3], "state_i": [61, 60]})
    actions.to_parquet(oracle / "actions.parquet", index=False)
    prediction = original / "validation/SPY_20250102.npz"
    np.savez_compressed(
        prediction,
        action_ids=actions.action_id.to_numpy(),
        gbt_net=np.array([2.0, 2.0]),
    )
    (out / "gbt_net_episode.txt").write_bytes(b"immutable model")
    pack = {"x": np.zeros((2, 1954), np.float32)}
    store = SimpleNamespace(
        seal=SimpleNamespace(check=lambda *_args: None),
        rows=lambda *_args: (pack, np.array([0, 1]), np.array([1, 0])),
    )
    arrays = {
        "state_i": np.array([60, 61]),
        "values": np.zeros((2, 35)),
        "valid": np.ones((2, 35), bool),
    }
    ep = SimpleNamespace(root=ep_root, get=lambda _day: arrays)
    models = {
        "gbt_net": SimpleNamespace(predict=lambda x, **_kwargs: np.ones(len(x)) * 2),
        "gbt_net_episode": SimpleNamespace(
            predict=lambda x, **_kwargs: np.ones(len(x)) * 4
        ),
    }
    monkeypatch.setattr(producer.base, "flatten_gbt", lambda p, ai, _si: p["x"][ai])
    old_day = SimpleNamespace(
        ticker="SPY",
        date="20250102",
        key="SPY/20250102",
        oracle=oracle,
        features=features,
    )
    actual_day = SimpleNamespace(
        **{**old_day.__dict__, "features": features / "features.npz"}
    )
    fn, original_source, fixed_source = repair.repaired_function(producer)
    assert fixed_source == original_source.replace(
        "day.features /", "day.features.parent /"
    )
    args = (
        "validation",
        store,
        ep,
        models,
        {"SPY": 1.0},
        original,
        {prediction.name: producer.sha(prediction)},
    )
    before = producer.predict_day(old_day, *args, out / "old", out, "identity")
    after = fn(actual_day, *args, out / "repaired", out, "identity")
    pd.testing.assert_frame_equal(before[0], after[0])
    for name in producer.MODELS:
        np.testing.assert_array_equal(before[1][name], after[1][name])
    assert before[2] == after[2]
    assert (
        producer.read(out / "old/SPY_20250102.complete.json")["binding"]
        == producer.read(out / "repaired/SPY_20250102.complete.json")["binding"]
    )


def test_technical_continuation_reuses_model_and_forbids_every_refit(
    tmp_path, monkeypatch
):
    out = tmp_path / "episode_learners_v1"
    out.mkdir()
    previous = tmp_path / "episode_learners_v1_runtime_v1"
    previous.mkdir()
    producer.write_json(
        previous / "completion.json", {"status": "FAILED", "exit_code": 1}
    )
    producer.write_json(out / "identity.json", {"synthetic": True})
    model = out / "gbt_net_episode.txt"
    model.write_bytes(b"completed immutable model")
    model_sha = producer.sha(model)
    stages = producer.Stages(out, producer.sha(out / "identity.json"))
    stages.publish("model", [model], {})
    monkeypatch.setattr(producer, "predict_day", producer.predict_day)
    original_predict_day = producer.predict_day
    monkeypatch.setattr(producer.lgb, "LGBMRegressor", producer.lgb.LGBMRegressor)
    calls = []

    def continued(args):
        assert args.resume
        assert producer.sha(model) == model_sha
        with pytest.raises(AssertionError, match="cannot fit"):
            producer.lgb.LGBMRegressor()
        calls.append("evaluation_only")
        producer.write_json(out / "summary.json", {"synthetic": True})
        producer.write_json(out / "completion.complete.json", {"synthetic": True})

    monkeypatch.setattr(producer, "run", continued)
    monkeypatch.setattr(
        sys,
        "argv",
        ["repair", "--root", str(tmp_path), "--output", str(out), "--resume"],
    )
    repair.main()
    assert calls == ["evaluation_only"]
    assert producer.sha(model) == model_sha
    result = producer.read(out / "technical_repairs/source_path_v1/completion.json")
    assert result["refits"] == 0
    marker = out / "technical_repairs/source_path_v1/repair.json"
    marker_sha = producer.sha(marker)
    producer.write_json(out / "failure_later.json", {"technical": True})
    # A fresh invocation imports the unchanged original function again.
    monkeypatch.setattr(producer, "predict_day", original_predict_day)
    repair.main()
    assert calls == ["evaluation_only", "evaluation_only"]
    assert producer.sha(marker) == marker_sha
    assert producer.sha(model) == model_sha
