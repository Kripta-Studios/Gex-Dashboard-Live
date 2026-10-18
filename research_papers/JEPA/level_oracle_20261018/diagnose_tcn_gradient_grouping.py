"""Fixed epoch-four TRAIN gradient comparison; zero optimizer updates."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import torch

import diagnose_tcn_memorization as memory
import run_tcn_flags as flags


def select_block(sample):
    if not sample.day_key.astype(str).str[-8:].between("20230101", "20241231").all():
        raise ValueError("Non-TRAIN sample")
    keys = sorted(
        sample.day_key.unique(),
        key=lambda k: (hashlib.sha256(f"{memory.SEED}|{k}".encode()).hexdigest(), k),
    )[:16]
    if len(keys) != 16:
        raise ValueError("Need16 TRAIN days")
    groups = []
    for key in keys:
        rows = memory.select_rows(sample[sample.day_key == key], count=32)
        if len(rows) != 32:
            raise ValueError("Selected day has fewer than32 actions")
        groups.append(rows)
    return pd.concat(groups, ignore_index=True)


def partitions():
    daily = np.arange(512).reshape(16, 32)
    mixed = np.stack([daily[:, 2 * i : 2 * i + 2].reshape(-1) for i in range(16)])
    return daily, mixed


def gradients(model, inputs, target, teacher, weight, groups):
    result = []
    for rows in groups:
        predicted, logits = model(*(x[rows] for x in inputs))
        loss = memory.fixed_loss(
            predicted, logits, target[rows], teacher[rows], weight[rows]
        )
        grad = torch.autograd.grad(loss, tuple(model.parameters()))
        result.append(
            torch.cat([g.reshape(-1) for g in grad]).detach().double().numpy()
        )
    return np.stack(result)


def describe(values, weights):
    mean = values.mean(axis=0)
    norms = np.linalg.norm(values, axis=1)
    unit = values / np.maximum(norms[:, None], 1e-30)
    pair = unit @ unit.T
    off = pair[~np.eye(len(values), dtype=bool)]
    aligned = unit @ (mean / max(np.linalg.norm(mean), 1e-30))
    return dict(
        mean_gradient_norm=float(np.linalg.norm(mean)),
        mean_squared_deviation=float(np.mean(np.sum((values - mean) ** 2, axis=1))),
        norms=norms.tolist(),
        batch_weight_sums=weights.tolist(),
        norms_per_unit_weight=(norms / weights).tolist(),
        pair_cosine_mean=float(off.mean()),
        pair_negative_fraction=float(np.mean(off < 0)),
        cosine_to_mean=aligned.tolist(),
    )


def main(args):
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    root, out = args.flags_root, args.output
    if out.exists():
        raise FileExistsError(out)
    identity = flags.read_json(root / "identity.json")
    learner = Path(identity["learner_root"])
    if (
        flags.sha(flags.__file__) != memory.FLAGS_SHA
        or flags.sha(learner / "train_models.py") != memory.ORIGINAL_SHA
    ):
        raise ValueError("Frozen producer differs")
    checkpoint = root / "tcn_epoch04.pt"
    metadata = flags.read_json(root / "tcn_epoch04.json")
    if metadata["epoch"] != 4 or flags.sha(checkpoint) != metadata["sha256"]:
        raise ValueError("Epoch4 binding mismatch")
    files = {
        str(p.resolve()): flags.sha(p)
        for p in [
            Path(__file__),
            Path(__file__).with_name("TCN_GRADIENT_GROUPING_PLAN.md"),
            Path(memory.__file__),
            Path(flags.__file__),
            checkpoint,
            root / "tcn_epoch04.json",
            root / "identity.json",
            root / "feature_schema.json",
            root / "normalizers.json",
            root / "training_sample.parquet",
            Path(identity["engine_root"]) / "index.parquet",
            *[
                learner / name
                for name in (
                    "train_models.py",
                    "run_policy.py",
                    "level_engine.py",
                    "features.py",
                    "build_cache.py",
                )
            ],
        ]
    }
    for path in [
        root / "feature_schema.json",
        root / "normalizers.json",
        root / "training_sample.parquet",
        Path(identity["engine_root"]) / "index.parquet",
    ]:
        if files[str(path.resolve())] != identity["files"][str(path.resolve())]:
            raise ValueError("Changed prepared source")
    sample = select_block(pd.read_parquet(root / "training_sample.parquet"))
    original = flags.load_original(learner)
    days = [
        d
        for d in original.discover_days(
            Path(identity["engine_root"]), Path(identity["feature_root"])
        )
        if d.date < "20250101"
    ]
    seal = original.SourceSeal(Path(identity["engine_root"]))
    store = flags.CheckedStore(
        original.FeatureStore(days, capacity=1, seal=seal),
        flags.read_json(root / "feature_schema.json"),
    )
    norm = flags.read_json(root / "normalizers.json")
    parts, positions = [[] for _ in range(6)], []
    for key, rows in sample.groupby("day_key", sort=False):
        pack, ai, si = store.rows(key, rows.action_id)
        batch = original.neural_batch(pack, ai, si, norm["features"], "cpu")
        for dest, tensor in zip(parts, batch):
            dest.append(tensor)
        positions.extend(rows.index)
    inputs = tuple(torch.cat(part)[np.argsort(positions)] for part in parts)
    files.update(store.hashes)
    files.update(seal.hashes)
    flags.verify_files(files)
    out.mkdir(parents=True)
    shutil.copy2(__file__, out / "diagnose_tcn_gradient_grouping.executed.py")
    flags.atomic_json(
        out / "freeze_before_gradients.json",
        dict(files=files, updates=0, checkpoint_epoch=4, device="cpu"),
    )
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
    model = original.LevelTCN(**saved["config"])
    model.load_state_dict(saved["model"])
    model.eval()
    before = {k: v.clone() for k, v in model.state_dict().items()}
    target = torch.tensor(
        (sample.net_base / sample.ticker.map(norm["risk_scales_usd"])).to_numpy(
            np.float32
        )
    )
    teacher = torch.tensor(sample.state_optimal_action.to_numpy(np.float32))
    weight = torch.tensor(sample.weight.to_numpy(np.float32))
    daily, mixed = partitions()
    gd = gradients(model, inputs, target, teacher, weight, daily)
    gm = gradients(model, inputs, target, teacher, weight, mixed)
    difference = float(np.linalg.norm(gd.mean(axis=0) - gm.mean(axis=0)))
    relative = difference / max(float(np.linalg.norm(gd.mean(axis=0))), 1e-30)
    same = relative <= 1e-4 or difference <= 1e-7
    if any(not torch.equal(v, before[k]) for k, v in model.state_dict().items()):
        raise ValueError("Model mutated during diagnostic")
    sample["input_sha256"] = memory.input_hashes(inputs)
    sample.to_parquet(out / "selected_train_rows.parquet", index=False)
    np.savez(
        out / "gradients_and_partitions.npz",
        daily=gd,
        mixed=gm,
        daily_indices=daily,
        mixed_indices=mixed,
    )
    flags.verify_files(files)
    summary = dict(
        status="PASS_GRADIENT_PARTITION_INVARIANCE"
        if same
        else "FAILED_GRADIENT_PARTITION_INVARIANCE",
        rows=512,
        days=16,
        checkpoint_epoch=4,
        updates=0,
        mean_gradient_difference_l2=difference,
        mean_gradient_relative_difference_l2=relative,
        daily=describe(gd, weight.numpy()[daily].sum(axis=1)),
        mixed=describe(gm, weight.numpy()[mixed].sum(axis=1)),
        validation_or_test_read=False,
    )
    flags.atomic_json(out / "summary.json", summary)
    flags.atomic_json(
        out / "completion.json",
        dict(
            status=summary["status"],
            files={
                str(p.resolve()): flags.sha(p) for p in out.iterdir() if p.is_file()
            },
        ),
    )
    print(
        json.dumps({k: v for k, v in summary.items() if k not in ("daily", "mixed")}),
        flush=True,
    )
    if not same:
        raise ValueError("Do not interpret gradients: partition invariance failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--flags-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
