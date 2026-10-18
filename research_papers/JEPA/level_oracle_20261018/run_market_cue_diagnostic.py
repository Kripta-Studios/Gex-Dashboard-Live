"""One preselected SPY 2025-01-02 illustration; seal ALL cues before membership.

The caller supplies an explicit hash binding extracted from already published
source/feature authorities. This runner neither selects a day nor reads PnL.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import features
import market_cues

TICKER, DATE = "SPY", "20250102"
FEATURE_FILES = (
    "features",
    "features_metadata",
    "action_features",
    "action_metadata",
    "feature_contract",
    "actions",
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(2**20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".partial")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(
            value, handle, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2
        )
        handle.flush()
        os.fsync(handle.fileno())
    if path.exists():
        raise ValueError("Refusing to overwrite diagnostic evidence")
    os.replace(temporary, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify(binding, names):
    for name in names:
        item = binding["files"][name]
        if sha(item["path"]) != item["sha256"]:
            raise ValueError("Input differs from explicit authority: " + name)


def run(binding_path, output):
    binding_path, output = Path(binding_path).resolve(), Path(output).resolve()
    binding = read_json(binding_path)
    code_hashes = {
        name: sha(Path(__file__).with_name(name))
        for name in ("market_cues.py", "run_market_cue_diagnostic.py")
    }

    def recheck_code():
        if any(
            sha(Path(__file__).with_name(name)) != digest
            for name, digest in code_hashes.items()
        ):
            raise ValueError("Diagnostic implementation changed during extraction")

    if binding.get("kind") != "PREENTRY_CUE_INPUT_BINDING_V1" or (
        binding.get("ticker"),
        binding.get("date"),
    ) != (TICKER, DATE):
        raise ValueError("Only the preselected SPY 20250102 illustration is authorized")
    if not binding.get("provenance") or binding.get("model_policy") != "gbt_net__0":
        raise ValueError("Published source/feature authority provenance required")
    for path, digest in binding["provenance"].items():
        if sha(path) != digest:
            raise ValueError("Published input authority changed")
    if output.exists() or any(
        output == Path(item["path"]).resolve()
        or output in Path(item["path"]).resolve().parents
        for item in binding["files"].values()
    ):
        raise ValueError("New separate output directory required")
    binding_hash = sha(binding_path)
    verify(binding, FEATURE_FILES)
    paths = {name: Path(item["path"]) for name, item in binding["files"].items()}
    contract, metadata, action_meta = (
        read_json(paths[name])
        for name in ("feature_contract", "features_metadata", "action_metadata")
    )
    expected_schema = dict(
        base_names=list(features.BASE_NAMES),
        token_names=list(features.TOKEN_NAMES),
        action_names=list(features.ACTION_NAMES),
    )
    if (
        any(contract["schema"][key] != value for key, value in expected_schema.items())
        or metadata["schema"] != contract["schema"]
    ):
        raise ValueError("Unexpected feature schema")
    for meta, array_name in ((metadata, "features"), (action_meta, "action_features")):
        if (
            meta.get("outcomes_read") is not False
            or meta["sha256"] != binding["files"][array_name]["sha256"]
            or meta["binding"]["dependencies"] != contract["dependencies"]
        ):
            raise ValueError("Invalid feature metadata binding")
        if (
            meta["binding"]["source_sha256"] != binding["cache_npz_sha256"]
            or meta["binding"]["source_metadata_sha256"] != binding["cache_meta_sha256"]
        ):
            raise ValueError("Feature cache differs from audited day")
    if contract.get("outcomes_read") is not False or action_meta[
        "action_names"
    ] != list(features.ACTION_NAMES):
        raise ValueError("Noncausal contract/action whitelist")
    for name, digest in contract["dependencies"].items():
        if Path(name).name != name or sha(Path(__file__).with_name(name)) != digest:
            raise ValueError("Feature producer code differs")
        code_hashes[name] = digest
    actions = pd.read_parquet(
        paths["actions"], columns=["action_id", *features.ACTION_INPUT_NAMES]
    )
    action_input_digest = hashlib.sha256(
        actions[["action_id", *features.ACTION_INPUT_NAMES]]
        .to_numpy(np.float64)
        .tobytes()
    ).hexdigest()
    if (
        action_input_digest != action_meta["binding"]["action_inputs_sha256"]
        or actions.action_id.duplicated().any()
    ):
        raise ValueError("Causal action inputs differ")
    with np.load(paths["features"], allow_pickle=False) as saved:
        pack = {
            key: saved[key]
            for key in (
                "state_i",
                "base",
                "tokens",
                "token_mask",
                "bar_mask",
                "bar_end_i",
            )
        }
    with np.load(paths["action_features"], allow_pickle=False) as saved:
        ids, vectors = saved["action_id"], saved["action_features"]
    if not np.array_equal(ids, actions.action_id) or len(
        np.unique(pack["state_i"])
    ) != len(pack["state_i"]):
        raise ValueError("Action/state identity mismatch")
    states = {int(value): index for index, value in enumerate(pack["state_i"])}
    output.mkdir(parents=True)
    cue_path = output / "all_candidate_cues.jsonl"
    with cue_path.open("x", encoding="utf-8") as handle:
        for position, row in enumerate(actions.itertuples(index=False)):
            index = states[int(row.state_i)]
            cues = market_cues.extract_market_cues(
                state_i=int(row.state_i),
                **{
                    key: pack[key][index]
                    for key in ("base", "tokens", "token_mask", "bar_mask", "bar_end_i")
                },
                action=vectors[position],
            )
            instant = datetime(
                2025, 1, 2, 9, 30, tzinfo=ZoneInfo("America/New_York")
            ) + timedelta(minutes=int(row.state_i))
            cues.update(
                action_id=int(row.action_id),
                ticker=TICKER,
                date=DATE,
                decision_nyse=instant.isoformat(),
                decision_utc=instant.astimezone(timezone.utc).isoformat(),
            )
            handle.write(json.dumps(cues, allow_nan=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    verify(binding, FEATURE_FILES)
    if sha(binding_path) != binding_hash:
        raise ValueError("Input authority changed")
    cue_hash = sha(cue_path)
    recheck_code()
    write_json(
        output / "features_seal.json",
        dict(
            status="ALL_CANDIDATE_CUES_SEALED_BEFORE_MEMBERSHIP",
            candidates=len(actions),
            cues_sha256=cue_hash,
            input_binding_sha256=binding_hash,
            source_files={name: binding["files"][name] for name in FEATURE_FILES},
            code_hashes=code_hashes,
            sealed_utc=datetime.now(timezone.utc).isoformat(),
            economic_sidecars_read=False,
            oracle_membership_read=False,
            model_membership_read=False,
        ),
    )

    # This is the only section that opens membership. It projects IDs, not PnL.
    verify(binding, ("oracle_ledger", "model_ledger"))
    oracle = pd.read_parquet(paths["oracle_ledger"], columns=["action_id"])
    model = pd.read_parquet(
        paths["model_ledger"], columns=["ticker", "date", "action_id"]
    )
    model = model.loc[(model.ticker == TICKER) & (model.date.astype(str) == DATE)]
    offered = set(map(int, ids))
    oracle_ids, model_ids = (
        set(map(int, oracle.action_id)),
        set(map(int, model.action_id)),
    )
    if (
        not oracle_ids <= offered
        or not model_ids <= offered
        or oracle.action_id.duplicated().any()
        or model.action_id.duplicated().any()
    ):
        raise ValueError("Membership includes duplicate or unoffered action")
    write_json(
        output / "membership_overlay.json",
        dict(
            ticker=TICKER,
            date=DATE,
            model_policy=binding["model_policy"],
            model_is_fixed_descriptive_control=True,
            rows=[
                dict(
                    action_id=int(value),
                    oracle_selected=int(value) in oracle_ids,
                    model_selected=int(value) in model_ids,
                )
                for value in ids
            ],
            cues_sha256=cue_hash,
            predictive_evidence=False,
            economic_values_read=False,
        ),
    )
    verify(binding, (*FEATURE_FILES, "oracle_ledger", "model_ledger"))
    recheck_code()
    for path, digest in binding["provenance"].items():
        if sha(path) != digest:
            raise ValueError("Published input authority changed during diagnostic")
    if sha(cue_path) != cue_hash or sha(binding_path) != binding_hash:
        raise ValueError("Sealed evidence changed")
    write_json(
        output / "completion.json",
        dict(
            status="COMPLETE_SINGLE_SESSION_DESCRIPTIVE_CUES",
            candidates=len(actions),
            predictive_evidence=False,
            training_performed=False,
            files={
                path.name: sha(path)
                for path in (
                    cue_path,
                    output / "features_seal.json",
                    output / "membership_overlay.json",
                )
            },
            source_files=binding["files"],
            input_binding_sha256=binding_hash,
        ),
    )
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.binding, args.out)


if __name__ == "__main__":
    main()
