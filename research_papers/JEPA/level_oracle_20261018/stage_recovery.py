"""External recovery snapshots/plans. Never mutates the frozen learner producer."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import time


BASE_NAMES = (
    "train_x.npy",
    "training_sample.parquet",
    "sampling_manifest.json",
    "normalizers.json",
    "feature_schema.json",
    "run_identity.json",
    "train_models.py",
    "run_policy.py",
    "LEARNER_PLAN.md",
    "features.py",
    "build_cache.py",
    "level_engine.py",
    "run_engine_dataset.py",
    "PROTOCOL.md",
)
MODELS = ("gbt_net", "gbt_advantage")


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial-" + str(time.time_ns()))
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def atomic_copy(source, target):
    source, target = Path(source), Path(target)
    expected = sha(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha(target) != expected:
            raise ValueError(
                "Snapshot already exists with different bytes: " + str(target)
            )
        return expected
    temporary = target.with_name(target.name + ".partial-" + str(time.time_ns()))
    shutil.copyfile(source, temporary)
    if sha(temporary) != expected or sha(source) != expected:
        raise ValueError("Source changed during atomic snapshot")
    with temporary.open("rb+") as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, target)
    return expected


def completed_model_marker(log, name):
    prefix = []
    for line in Path(log).read_text(encoding="utf-8", errors="replace").splitlines():
        prefix.append(line)
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if (
            isinstance(item, dict)
            and item.get("stage") == "model_fit"
            and item.get("model") == name
        ):
            return item, "\n".join(prefix) + "\n"
    return None, None


def capture_base(output, recovery):
    target = recovery / "base"
    manifest_path = target / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, digest in manifest["artifacts"].items():
            if sha(output / name) != digest or sha(target / name) != digest:
                raise ValueError("Frozen recovery base changed: " + name)
        return manifest
    hashes = {name: atomic_copy(output / name, target / name) for name in BASE_NAMES}
    manifest = {
        "status": "COMPLETE_BASE_SNAPSHOT",
        "utc": utc(),
        "output_root": str(output.resolve()),
        "artifacts": hashes,
    }
    atomic_json(manifest_path, manifest)
    return manifest


def capture_gbt(output, runtime, recovery, name):
    marker, prefix = completed_model_marker(runtime / "stdout.log", name)
    if marker is None:
        return {"status": "INCOMPLETE_NO_COMPLETION_MARKER", "model": name}
    source = output / (name + ".txt")
    target = recovery / name
    manifest_path = target / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            sha(source) != manifest["model_sha256"]
            or sha(target / "model.txt") != manifest["model_sha256"]
        ):
            raise ValueError("Completed model snapshot changed")
        return manifest
    base = capture_base(output, recovery)
    import lightgbm as lgb

    booster = lgb.Booster(model_file=str(source))
    width = json.loads((output / "normalizers.json").read_text(encoding="utf-8"))[
        "gbt_columns"
    ]
    if booster.num_trees() != 200 or booster.num_feature() != width:
        raise ValueError("Parsed model differs from fixed tree count/feature width")
    digest = atomic_copy(source, target / "model.txt")
    atomic_json(target / "completion_marker.json", marker)
    (target / "stdout_through_completion.log").write_text(prefix, encoding="utf-8")
    manifest = {
        "status": "COMPLETE_GBT_SNAPSHOT",
        "model": name,
        "utc": utc(),
        "model_sha256": digest,
        "trees": booster.num_trees(),
        "features": booster.num_feature(),
        "completion_marker": marker,
        "log_prefix_sha256": sha(target / "stdout_through_completion.log"),
        "base_manifest_sha256": sha(recovery / "base" / "manifest.json"),
        "base_artifacts": base["artifacts"],
    }
    atomic_json(manifest_path, manifest)
    return manifest


def validate_epoch_pair(path, verify_inputs=True):
    path = Path(path)
    metadata_path = path.with_suffix(".json")
    if not path.is_file() or not metadata_path.is_file():
        raise ValueError("Incomplete checkpoint pair")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    epoch = metadata.get("epoch")
    if (
        metadata.get("complete_epoch_boundary") is not True
        or type(epoch) is not int
        or not 1 <= epoch <= 4
        or sha(path) != metadata.get("sha256")
    ):
        raise ValueError("Invalid checkpoint boundary or hash")
    if verify_inputs:
        for source, expected in metadata["binding"]["files"].items():
            if sha(source) != expected:
                raise ValueError("Changed checkpoint input: " + source)
    import torch

    state = torch.load(path, map_location="cpu", weights_only=False)
    required = {
        "model",
        "optimizer",
        "epoch",
        "history",
        "binding",
        "generator_state",
        "numpy_state",
        "torch_state",
        "cuda_states",
    }
    if (
        not required.issubset(state)
        or state["binding"] != metadata["binding"]
        or state["epoch"] != epoch
    ):
        raise ValueError("Checkpoint state/binding is incomplete")
    if (
        [item.get("epoch") for item in state["history"]] != list(range(1, epoch + 1))
        or not all(
            math.isfinite(item["summed_fixed_batch_loss"]) for item in state["history"]
        )
        or not state["model"]
        or not state["optimizer"].get("param_groups")
        or not isinstance(state["generator_state"], dict)
        or len(state["numpy_state"]) != 5
        or not torch.is_tensor(state["torch_state"])
    ):
        raise ValueError("Checkpoint history/optimizer/RNG is incomplete")
    return metadata


def capture_epoch(output, recovery, path):
    target = recovery / path.stem
    manifest_path = target / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, expected in manifest["artifacts"].items():
            if sha(target / name) != expected or sha(output / name) != expected:
                raise ValueError("Completed epoch snapshot changed")
        return manifest
    metadata = validate_epoch_pair(path)
    artifacts = {
        p.name: atomic_copy(p, target / p.name)
        for p in (path, path.with_suffix(".json"))
    }
    manifest = {
        "status": "COMPLETE_EPOCH_SNAPSHOT",
        "epoch": metadata["epoch"],
        "utc": utc(),
        "artifacts": artifacts,
        "binding": metadata["binding"],
        "base_manifest_sha256": sha(recovery / "base" / "manifest.json"),
    }
    atomic_json(manifest_path, manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--recovery", type=Path, required=True)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    for name in (
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "OMP_NUM_THREADS",
    ):
        os.environ[name] = "1"
    while True:
        for name in MODELS:
            result = capture_gbt(args.output, args.runtime, args.recovery, name)
            print(json.dumps({"status": result["status"], "model": name}), flush=True)
        for path in sorted(args.output.glob("tcn_epoch*.pt")):
            try:
                result = capture_epoch(args.output, args.recovery, path)
                print(
                    json.dumps({"status": result["status"], "epoch": result["epoch"]}),
                    flush=True,
                )
            except (ValueError, OSError, KeyError) as error:
                atomic_json(
                    args.recovery / (path.stem + "_pending_or_invalid.json"),
                    {
                        "status": "NOT_ADMITTED",
                        "path": str(path),
                        "reason": str(error),
                        "utc": utc(),
                    },
                )
                print(
                    json.dumps(
                        {
                            "status": "CHECKPOINT_NOT_ADMITTED",
                            "path": str(path),
                            "reason": str(error),
                        }
                    ),
                    flush=True,
                )
        if not args.watch or (args.runtime / "completion.json").exists():
            return
        time.sleep(30)


if __name__ == "__main__":
    main()
