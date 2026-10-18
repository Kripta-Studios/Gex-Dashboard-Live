"""One fixed TRAIN-only capacity diagnostic; no validation or policy selection."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

import run_tcn_flags as flags

SEED = 20261018
FLAGS_SHA = "a76a3ee78b74568a77ad06bc85c3092dee606648c6b6ed54ad38818496ae06e5"
ORIGINAL_SHA = "a5192737abd1c0b3e4a6a6cd391117d97a014c06b6cd528201ba1f5df0ef6808"


def select_rows(sample, count=128):
    if sample.duplicated(["day_key", "action_id"]).any():
        raise ValueError("Duplicate action identity")
    if not sample.day_key.astype(str).str[-8:].between("20230101", "20241231").all():
        raise ValueError("Non-TRAIN row")
    result = sample.copy()
    result["priority_sha256"] = [
        hashlib.sha256(f"{SEED}|{key}|{int(aid)}".encode()).hexdigest()
        for key, aid in zip(result.day_key, result.action_id)
    ]
    return (
        result.sort_values(["priority_sha256", "day_key", "action_id"])
        .head(count)
        .reset_index(drop=True)
    )


def input_hashes(inputs):
    arrays = [x.detach().cpu().numpy() for x in inputs]
    result = []
    for i in range(len(arrays[0])):
        digest = hashlib.sha256()
        for x in arrays:
            row = np.ascontiguousarray(x[i])
            digest.update(json.dumps([row.dtype.str, row.shape]).encode())
            digest.update(row.tobytes())
        result.append(digest.hexdigest())
    return result


def duplicate_diagnostics(hashes, target, teacher, weight):
    frame = pd.DataFrame(dict(h=hashes, y=target, t=teacher, w=weight))
    groups, conflicts, teacher_conflicts, residual = 0, 0, 0, 0.0
    for _, rows in frame.groupby("h", sort=True):
        groups += int(len(rows) > 1)
        conflicts += int(rows.y.nunique() > 1)
        teacher_conflicts += int(rows.t.nunique() > 1)
        center = np.average(rows.y, weights=rows.w)
        residual += float((rows.w * (rows.y - center) ** 2).sum())
    return dict(
        unique_inputs=frame.h.nunique(),
        duplicate_groups=groups,
        contradictory_net_groups=conflicts,
        contradictory_teacher_groups=teacher_conflicts,
        identical_input_weighted_mse_floor=residual / frame.w.sum(),
    )


def fixed_loss(pred, logits, target, teacher, weight):
    return (
        weight
        * (
            (pred - target).square()
            + 0.1
            * F.binary_cross_entropy_with_logits(logits, teacher, reduction="none")
        )
    ).sum() / 1024


def measure(model, inputs, target, teacher, weight, step):
    with torch.no_grad():
        predicted, logits = model(*inputs)
        p, y, w = [x.double().numpy() for x in (predicted, target, weight)]
        mse = float(np.average((p - y) ** 2, weights=w))
        constant = float(np.average((y - np.average(y, weights=w)) ** 2, weights=w))
        return dict(
            update=step,
            weighted_mse=mse,
            unweighted_mse=float(np.mean((p - y) ** 2)),
            constant_weighted_mse=constant,
            weighted_r2=1 - mse / constant if constant else None,
            prediction_mean=float(np.average(p, weights=w)),
            prediction_std=float(
                np.sqrt(np.average((p - np.average(p, weights=w)) ** 2, weights=w))
            ),
            fixed_loss=float(fixed_loss(predicted, logits, target, teacher, weight)),
            net_loss=float((weight * (predicted - target).square()).sum() / 1024),
            teacher_loss=float(
                (
                    weight
                    * 0.1
                    * F.binary_cross_entropy_with_logits(
                        logits, teacher, reduction="none"
                    )
                ).sum()
                / 1024
            ),
        )


def main(args):
    torch.set_num_threads(4)
    root, out = args.flags_root, args.output
    if out.exists():
        raise FileExistsError(out)
    if flags.sha(flags.__file__) != FLAGS_SHA:
        raise ValueError("Flags source changed")
    identity = flags.read_json(root / "identity.json")
    learner = Path(identity["learner_root"])
    if flags.sha(learner / "train_models.py") != ORIGINAL_SHA:
        raise ValueError("Original source changed")
    files = {
        str(p.resolve()): flags.sha(p)
        for p in [
            Path(__file__),
            Path(__file__).with_name("TCN_MEMORIZATION_DIAGNOSTIC_PLAN.md"),
            Path(flags.__file__),
            root / "identity.json",
            root / "training_sample.parquet",
            root / "feature_schema.json",
            root / "normalizers.json",
            learner / "train_models.py",
            learner / "run_policy.py",
            learner / "level_engine.py",
            learner / "features.py",
            learner / "build_cache.py",
            Path(identity["engine_root"]) / "index.parquet",
        ]
    }
    for name in ("training_sample.parquet", "feature_schema.json", "normalizers.json"):
        path = str((root / name).resolve())
        if files[path] != identity["files"][path]:
            raise ValueError("Prepared input changed: " + name)
    index_path = str((Path(identity["engine_root"]) / "index.parquet").resolve())
    if files[index_path] != identity["files"][index_path]:
        raise ValueError("Audited engine index changed")
    out.mkdir(parents=True)
    shutil.copy2(__file__, out / "diagnose_tcn_memorization.executed.py")
    shutil.copy2(Path(__file__).with_name("TCN_MEMORIZATION_DIAGNOSTIC_PLAN.md"), out)
    sample = select_rows(pd.read_parquet(root / "training_sample.parquet"))
    if len(sample) != 128:
        raise ValueError("Expected 128 rows")
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
    normalizers = flags.read_json(root / "normalizers.json")
    parts, positions = [[] for _ in range(6)], []
    config = None
    for key, rows in sample.groupby("day_key", sort=True):
        pack, ai, si = store.rows(key, rows.action_id)
        batch = original.neural_batch(pack, ai, si, normalizers["features"], "cpu")
        config = dict(
            base_dim=pack["base"].shape[-1],
            token_dim=pack["tokens"].shape[-1],
            action_dim=pack["action_features"].shape[-1],
            token_mask_dim=batch[4].shape[-1],
            map_mask_dim=batch[5].shape[-1],
        )
        for dest, tensor in zip(parts, batch):
            dest.append(tensor)
        positions.extend(rows.index)
    reorder = np.argsort(positions)
    inputs = tuple(torch.cat(part)[reorder] for part in parts)
    files.update(store.hashes)
    files.update(seal.hashes)
    flags.verify_files(files)
    flags.atomic_json(
        out / "freeze_before_updates.json",
        dict(files=files, count=128, updates=500, device="cpu", seed=SEED),
    )
    scales = normalizers["risk_scales_usd"]
    target = torch.tensor(
        (sample.net_base / sample.ticker.map(scales)).to_numpy(np.float32)
    )
    teacher = torch.tensor(sample.state_optimal_action.to_numpy(np.float32))
    weight = torch.tensor(sample.weight.to_numpy(np.float32))
    hashes = input_hashes(inputs)
    duplicates = duplicate_diagnostics(
        hashes, target.numpy(), teacher.numpy(), weight.numpy()
    )
    sample["input_sha256"] = hashes
    sample["normalized_target"] = target.numpy()
    sample.to_parquet(out / "selected_train_rows.parquet", index=False)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    model = original.LevelTCN(**config)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
    torch.save(dict(config=config, model=model.state_dict()), out / "initial_model.pt")
    started = time.monotonic()
    metrics, norms = [measure(model, inputs, target, teacher, weight, 0)], []
    for update in range(1, 501):
        optimizer.zero_grad(set_to_none=True)
        predicted, logits = model(*inputs)
        loss = fixed_loss(predicted, logits, target, teacher, weight)
        if not torch.isfinite(loss):
            raise FloatingPointError("Nonfinite diagnostic loss")
        loss.backward()
        norms.append(float(torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)))
        optimizer.step()
        if update % 50 == 0:
            metrics.append(measure(model, inputs, target, teacher, weight, update))
            print(json.dumps(metrics[-1]), flush=True)
    torch.save(
        dict(
            config=config,
            model=model.state_dict(),
            optimizer=optimizer.state_dict(),
            rng=torch.get_rng_state(),
            update=500,
        ),
        out / "final_model.pt",
    )
    pd.DataFrame(metrics).to_parquet(out / "metrics.parquet", index=False)
    np.save(out / "gradient_norms.npy", norms)
    flags.verify_files(files)
    summary = dict(
        status="COMPLETE_TRAIN_CAPACITY_DIAGNOSTIC",
        selected_rows=128,
        updates=500,
        elapsed_seconds=time.monotonic() - started,
        duplicates=duplicates,
        metrics=metrics,
        clipped_fraction=float(np.mean(np.array(norms) > 1)),
        gradient_quantiles=np.quantile(norms, [0, 0.5, 0.9, 0.99, 1]).tolist(),
        validation_or_test_read=False,
        policy_or_epoch_selection=False,
    )
    flags.atomic_json(out / "summary.json", summary)
    flags.atomic_json(
        out / "completion.json",
        dict(
            status="COMPLETE",
            files={
                str(p.resolve()): flags.sha(p) for p in out.iterdir() if p.is_file()
            },
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--flags-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
