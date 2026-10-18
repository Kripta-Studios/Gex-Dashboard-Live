"""Synthetic fixed-session extraction and sealed-before-membership integration."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import features as f
import run_market_cue_diagnostic as r
from test_market_cues import inputs


def fixture(tmp_path):
    source = tmp_path / "sources"
    source.mkdir()
    v = inputs()
    state = {key: np.asarray([value]) for key, value in v.items() if key != "action"}
    np.savez(source / "features.npz", **state)
    np.savez(
        source / "action_features.npz",
        action_id=np.array([7, 8]),
        action_features=np.stack([v["action"], v["action"]]),
    )
    actions = pd.DataFrame({name: [0.0, 0.0] for name in f.ACTION_INPUT_NAMES})
    actions["action_id"], actions["state_i"] = [7, 8], [60, 60]
    actions.to_parquet(source / "actions.parquet", index=False)
    pd.DataFrame(dict(action_id=[7], net_base=[999999.0])).to_parquet(
        source / "oracle_ledger.parquet", index=False
    )
    pd.DataFrame(
        dict(
            ticker=["SPY", "QQQ"],
            date=["20250102", "20250102"],
            action_id=[8, 444],
            net_base=[-999999.0, 777777.0],
        )
    ).to_parquet(source / "model_ledger.parquet", index=False)
    schema = dict(
        base_names=list(f.BASE_NAMES),
        token_names=list(f.TOKEN_NAMES),
        action_names=list(f.ACTION_NAMES),
    )
    contract = dict(
        schema=schema,
        dependencies={"features.py": r.sha(Path(f.__file__))},
        outcomes_read=False,
    )
    r.write_json(source / "feature_contract.json", contract)
    meta_binding = dict(
        dependencies=contract["dependencies"],
        source_sha256="audited_cache",
        source_metadata_sha256="audited_cache_meta",
    )
    r.write_json(
        source / "features_metadata.json",
        dict(
            schema=schema,
            binding=meta_binding,
            sha256=r.sha(source / "features.npz"),
            outcomes_read=False,
        ),
    )
    action_digest = hashlib.sha256(
        actions[["action_id", *f.ACTION_INPUT_NAMES]].to_numpy(np.float64).tobytes()
    ).hexdigest()
    r.write_json(
        source / "action_metadata.json",
        dict(
            binding=dict(meta_binding, action_inputs_sha256=action_digest),
            action_names=list(f.ACTION_NAMES),
            sha256=r.sha(source / "action_features.npz"),
            outcomes_read=False,
        ),
    )
    (source / "published_authority.json").write_text(
        '{"synthetic":true}', encoding="utf-8"
    )
    names = {
        name: source
        / (
            name
            + (
                ".npz"
                if name in ("features", "action_features")
                else ".parquet"
                if name in ("actions", "oracle_ledger", "model_ledger")
                else ".json"
            )
        )
        for name in (*r.FEATURE_FILES, "oracle_ledger", "model_ledger")
    }
    binding = dict(
        kind="PREENTRY_CUE_INPUT_BINDING_V1",
        ticker="SPY",
        date="20250102",
        model_policy="gbt_net__0",
        cache_npz_sha256="audited_cache",
        cache_meta_sha256="audited_cache_meta",
        provenance={
            str(source / "published_authority.json"): r.sha(
                source / "published_authority.json"
            )
        },
        files={
            name: dict(path=str(path), sha256=r.sha(path))
            for name, path in names.items()
        },
    )
    binding_path = tmp_path / "binding.json"
    r.write_json(binding_path, binding)
    return binding_path, tmp_path / "diagnostic", names


def test_every_candidate_sealed_before_overlay_and_economic_columns_never_read(
    tmp_path, monkeypatch
):
    binding, output, files = fixture(tmp_path)
    original = r.pd.read_parquet
    calls = []

    def checked(path, columns=None, **kwargs):
        assert columns is not None and not {
            "net_base",
            "net_adverse",
            "exit_i",
            "status",
        }.intersection(columns)
        if Path(path) in (files["oracle_ledger"], files["model_ledger"]):
            seal = r.read_json(output / "features_seal.json")
            assert seal["candidates"] == 2 and not seal["oracle_membership_read"]
            assert (
                len((output / "all_candidate_cues.jsonl").read_text().splitlines()) == 2
            )
        calls.append(Path(path).name)
        return original(path, columns=columns, **kwargs)

    monkeypatch.setattr(r.pd, "read_parquet", checked)
    r.run(binding, output)
    assert calls == ["actions.parquet", "oracle_ledger.parquet", "model_ledger.parquet"]
    overlay = r.read_json(output / "membership_overlay.json")
    assert overlay["rows"] == [
        dict(action_id=7, oracle_selected=True, model_selected=False),
        dict(action_id=8, oracle_selected=False, model_selected=True),
    ]
    first = json.loads(
        (output / "all_candidate_cues.jsonl").read_text().splitlines()[0]
    )
    assert first["decision_nyse"].endswith("10:30:00-05:00")
    assert first["decision_utc"].endswith("15:30:00+00:00")
    assert "oracle_selected" not in first and "net_base" not in first
    assert r.read_json(output / "completion.json")["training_performed"] is False


def test_changed_bound_feature_rejected_before_output(tmp_path):
    binding, output, files = fixture(tmp_path)
    with files["features"].open("ab") as handle:
        handle.write(b"mutation")
    with pytest.raises(ValueError, match="authority"):
        r.run(binding, output)
    assert not output.exists()


def test_malformed_membership_preserves_complete_feature_seal_but_no_completion(
    tmp_path,
):
    binding, output, files = fixture(tmp_path)
    pd.DataFrame(dict(action_id=[999])).to_parquet(files["oracle_ledger"], index=False)
    values = r.read_json(binding)
    values["files"]["oracle_ledger"]["sha256"] = r.sha(files["oracle_ledger"])
    binding.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(ValueError, match="unoffered"):
        r.run(binding, output)
    assert (output / "features_seal.json").exists()
    assert not (output / "membership_overlay.json").exists()
    assert not (output / "completion.json").exists()


def test_code_change_during_extraction_detected_without_modifying_real_source(
    tmp_path, monkeypatch
):
    binding, output, files = fixture(tmp_path)
    original = r.sha
    observed = {"count": 0}

    def changed_code(path):
        if Path(path).name == "market_cues.py":
            observed["count"] += 1
            if observed["count"] > 1:
                return "synthetic_changed_implementation"
        return original(path)

    monkeypatch.setattr(r, "sha", changed_code)
    with pytest.raises(ValueError, match="implementation changed"):
        r.run(binding, output)
    assert not (output / "features_seal.json").exists()
    assert not (output / "membership_overlay.json").exists()
