"""Isolated row-mixed TRAIN implementation. No inference/economic entry point."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd
import torch

import diagnose_tcn_memorization as common
import run_tcn_flags as flags

NAMES = ("base", "tokens", "maps", "action", "token_mask", "map_mask")
FLAGS_TRAIN_COMPLETE_SHA = (
    "bd17be758bdc9a5a430f48a162c6925dac5c89689ca506013b1548e53e76e18b"
)


class ReplayRNG:
    """Composite state works with the frozen checkpoint RNG adapter."""

    def __init__(self):
        self.schedule = np.random.default_rng(flags.SEED)
        self.mixed = np.random.default_rng(flags.SEED)

    @property
    def bit_generator(self):
        return self

    @property
    def state(self):
        return copy.deepcopy(
            dict(
                schedule=self.schedule.bit_generator.state,
                mixed=self.mixed.bit_generator.state,
            )
        )

    @state.setter
    def state(self, value):
        self.schedule.bit_generator.state = copy.deepcopy(value["schedule"])
        self.mixed.bit_generator.state = copy.deepcopy(value["mixed"])


def epoch_plan(sample, rng):
    groups = {k: r.index.to_numpy() for k, r in sample.groupby("day_key", sort=True)}
    sizes, original_order = [], []
    for key in rng.schedule.permutation(np.array(sorted(groups), dtype=object)):
        indices = rng.schedule.permutation(groups[key])
        for start in range(0, len(indices), 1024):
            part = indices[start : start + 1024]
            sizes.append(len(part))
            original_order.extend(part)
    return dict(
        sizes=np.asarray(sizes, np.int64),
        original_order=np.asarray(original_order, np.int64),
        mixed_order=rng.mixed.permutation(len(sample)).astype(np.int64),
    )


def persist_plan(out, epoch, plan, before, after):
    path = out / f"epoch{epoch:02}_plan.npz"
    meta = path.with_suffix(".json")
    flags.preserve_incomplete(
        out,
        list(out.glob(path.name + ".partial")) + list(out.glob(meta.name + ".partial")),
    )
    if path.exists() and not meta.exists():
        flags.preserve_incomplete(out, [path])
    if meta.exists():
        recorded = flags.read_json(meta)
        if (
            not path.exists()
            or flags.sha(path) != recorded["sha256"]
            or recorded["rng_before"] != before
            or recorded["rng_after"] != after
        ):
            raise ValueError("Epoch plan binding mismatch")
        with np.load(path, allow_pickle=False) as saved:
            if set(saved.files) != set(plan) or any(
                not np.array_equal(saved[k], v) for k, v in plan.items()
            ):
                raise ValueError("Epoch plan replay differs")
    else:
        partial = path.with_name(path.name + ".partial")
        with partial.open("wb") as handle:
            np.savez(handle, **plan)
        os.replace(partial, path)
        flags.atomic_json(
            meta,
            dict(
                epoch=epoch,
                sha256=flags.sha(path),
                rng_before=before,
                rng_after=after,
                updates=len(plan["sizes"]),
                rows=int(plan["sizes"].sum()),
            ),
        )
    return {str(p.resolve()): flags.sha(p) for p in (path, meta)}


def score_prepacked(model, inputs, state_keys):
    _, first, inverse = np.unique(state_keys, return_index=True, return_inverse=True)
    states = []
    for start in range(0, len(first), 256):
        selected = torch.as_tensor(first[start : start + 256], device=inputs[0].device)
        states.append(
            model.encode_state(
                inputs[0][selected],
                inputs[1][selected],
                inputs[2][selected],
                inputs[4][selected],
                inputs[5][selected],
            )
        )
    encoded = torch.cat(states)
    return model.score_actions(
        encoded[torch.as_tensor(inverse, device=encoded.device)], inputs[3]
    )


class RowCache:
    def __init__(self, root):
        self.root = Path(root)
        self.manifest = flags.read_json(self.root / "cache_complete.json")
        flags.verify_files(self.manifest["files"])
        self.arrays = {
            k: np.load(path, mmap_mode="r", allow_pickle=False)
            for k, path in self.manifest["arrays"].items()
        }
        self.config = self.manifest["model_config"]

    def inputs(self, indices, device):
        return tuple(
            torch.as_tensor(
                np.array(self.arrays[k][indices], copy=True, order="C"), device=device
            )
            for k in NAMES
        )

    def state_keys(self, indices):
        return np.asarray(self.arrays["state_key"][indices])


def check_training_authority(consumed, authority):
    for path, digest in consumed.items():
        if authority.get(str(Path(path).resolve())) != digest:
            raise ValueError("Source differs from FLAGS TRAIN authority: " + str(path))


def same_json(path, value):
    if path.exists():
        if flags.read_json(path) != value:
            raise ValueError("Existing cache binding/layout differs: " + str(path))
    else:
        flags.preserve_incomplete(path.parent, [path.with_name(path.name + ".partial")])
        flags.atomic_json(path, value)


def chunk_hashes(arrays, indices):
    result = []
    for start in range(0, len(indices), 256):
        rows = np.asarray(indices[start : start + 256], dtype=np.int64)
        entry = {
            "indices_sha256": hashlib.sha256(rows.tobytes()).hexdigest(),
            "count": len(rows),
            "arrays": {},
        }
        for name, array in arrays.items():
            values = np.ascontiguousarray(array[rows])
            digest = hashlib.sha256(
                json.dumps([values.dtype.str, list(values.shape)]).encode()
            )
            digest.update(values.tobytes())
            entry["arrays"][name] = digest.hexdigest()
        result.append(entry)
    return result


def verify_cached_day(path, arrays, indices, key, authority):
    record = flags.read_json(path)
    if record["day_key"] != key or record["chunks"] != chunk_hashes(arrays, indices):
        raise ValueError("Completed cache day changed")
    check_training_authority(record["source_files"], authority)
    flags.verify_files(record["source_files"])
    return record["source_files"]


def preserve_unfinished_day(folder, arrays, indices):
    starts = list(folder.glob("started_*.json"))
    if not starts:
        return
    recovery = folder / (
        "recovery_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    )
    recovery.mkdir(exist_ok=False)
    # Save only this unfinished day's rows, not a second 16 GB cache.
    for start in range(0, len(indices), 256):
        rows = np.asarray(indices[start : start + 256], dtype=np.int64)
        np.savez(
            recovery / f"rows_{start:06}.npz",
            indices=rows,
            **{k: np.asarray(v[rows]) for k, v in arrays.items()},
        )
    for path in starts:
        os.replace(path, recovery / path.name)
    flags.atomic_json(
        recovery / "preserved.json",
        {str(p.resolve()): flags.sha(p) for p in recovery.iterdir() if p.is_file()},
    )


def build_cache(args):
    torch.set_num_threads(4)
    out, root = args.output.resolve(), args.flags_root.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "cache_complete.json").exists():
        existing = RowCache(out)
        if Path(existing.manifest["flags_root"]).resolve() != root:
            raise ValueError("Existing cache belongs to another FLAGS root")
        return
    if flags.sha(flags.__file__) != common.FLAGS_SHA:
        raise ValueError("Frozen FLAGS producer changed")
    identity = flags.read_json(root / "identity.json")
    if flags.sha(root / "training_complete.json") != FLAGS_TRAIN_COMPLETE_SHA:
        raise ValueError("FLAGS64 completed TRAIN authority differs from declared run")
    training = flags.read_json(root / "training_complete.json")
    authority = {
        str(Path(p).resolve()): h for p, h in training["binding"]["files"].items()
    }
    learner = Path(identity["learner_root"])
    if flags.sha(learner / "train_models.py") != common.ORIGINAL_SHA:
        raise ValueError("Original model producer changed")
    sources = [
        Path(__file__),
        Path(flags.__file__),
        Path(common.__file__),
        Path(__file__).with_name("TCN_ROW_MIXED_DESIGN_DRAFT.md"),
        root / "identity.json",
        root / "training_complete.json",
        root / "training_sample.parquet",
        root / "normalizers.json",
        root / "feature_schema.json",
        Path(identity["engine_root"]) / "index.parquet",
        *[
            learner / n
            for n in (
                "train_models.py",
                "run_policy.py",
                "level_engine.py",
                "features.py",
                "build_cache.py",
            )
        ],
    ]
    files = {str(p.resolve()): flags.sha(p) for p in sources}
    for path in (
        root / "training_sample.parquet",
        root / "normalizers.json",
        root / "feature_schema.json",
        Path(identity["engine_root"]) / "index.parquet",
    ):
        if files[str(path.resolve())] != identity["files"][str(path.resolve())]:
            raise ValueError("Prepared TRAIN input changed")
        check_training_authority(
            {str(path.resolve()): files[str(path.resolve())]}, authority
        )
    sample = pd.read_parquet(root / "training_sample.parquet").reset_index(drop=True)
    if (
        len(sample) != 270377
        or not sample.day_key.astype(str).str[-8:].between("20230101", "20241231").all()
        or sample.duplicated(["day_key", "action_id"]).any()
    ):
        raise ValueError("Unexpected TRAIN sample")
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
    keys = sorted(sample.day_key.unique())
    first = sample[sample.day_key == keys[0]].iloc[:1]
    pack, ai, si = store.rows(keys[0], first.action_id)
    check_training_authority({**store.hashes, **seal.hashes}, authority)
    batch = original.neural_batch(pack, ai, si, norm["features"], "cpu")
    files.update(store.hashes)
    files.update(seal.hashes)
    working = out / "cache_working"
    working.mkdir(exist_ok=True)
    same_json(
        working / "source_binding.json",
        dict(files=files, rows=len(sample), chunk_rows=256),
    )
    shapes = {
        name: (len(sample), *tensor.shape[1:]) for name, tensor in zip(NAMES, batch)
    }
    shapes["state_key"] = (len(sample),)
    shape_records = {
        name: dict(
            shape=list(shape),
            dtype=np.dtype(np.int64 if name == "state_key" else np.float32).str,
        )
        for name, shape in shapes.items()
    }
    config = dict(
        base_dim=pack["base"].shape[-1],
        token_dim=pack["tokens"].shape[-1],
        action_dim=pack["action_features"].shape[-1],
        token_mask_dim=batch[4].shape[-1],
        map_mask_dim=batch[5].shape[-1],
    )
    required = sum(
        int(np.prod(v["shape"])) * np.dtype(v["dtype"]).itemsize
        for v in shape_records.values()
    )
    same_json(
        working / "layout.json",
        dict(
            arrays=shape_records,
            required_bytes=required,
            model_config=config,
            binding_sha256=flags.sha(working / "source_binding.json"),
        ),
    )
    arrays = {}
    for name, layout in shape_records.items():
        path = working / (name + ".npy")
        if path.exists():
            try:
                array = np.load(path, mmap_mode="r+", allow_pickle=False)
                if (
                    list(array.shape) != layout["shape"]
                    or array.dtype.str != layout["dtype"]
                ):
                    raise ValueError("Bad cache array layout")
                arrays[name] = array
                continue
            except (ValueError, OSError, EOFError):
                if list(working.glob("days/*/complete.json")):
                    raise ValueError("Array damaged after a completed day")
                flags.preserve_incomplete(working, [path])
        elif list(working.glob("days/*/complete.json")):
            raise ValueError("Array missing after a completed day")
        needed = int(np.prod(layout["shape"])) * np.dtype(layout["dtype"]).itemsize
        if shutil.disk_usage(out).free < needed + 1024**3:
            raise OSError("Insufficient disk for exact row cache")
        arrays[name] = np.lib.format.open_memmap(
            path,
            mode="w+",
            dtype=np.dtype(layout["dtype"]),
            shape=tuple(layout["shape"]),
        )
    for day_number, key in enumerate(keys):
        rows = sample[sample.day_key == key]
        indices_all = rows.index.to_numpy()
        folder = working / "days" / f"{day_number:04}"
        folder.mkdir(parents=True, exist_ok=True)
        done = folder / "complete.json"
        if done.exists():
            files.update(verify_cached_day(done, arrays, indices_all, key, authority))
            continue
        preserve_unfinished_day(folder, arrays, indices_all)
        before = set(store.hashes) | set(seal.hashes)
        started = folder / (
            "started_"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            + ".json"
        )
        flags.atomic_json(
            started,
            dict(
                day_key=key,
                binding_sha256=flags.sha(working / "source_binding.json"),
                indices_sha256=hashlib.sha256(
                    indices_all.astype(np.int64).tobytes()
                ).hexdigest(),
            ),
        )
        for start in range(0, len(rows), 256):
            chunk = rows.iloc[start : start + 256]
            pack, ai, si = store.rows(key, chunk.action_id)
            consumed = {
                p: h
                for p, h in {**store.hashes, **seal.hashes}.items()
                if p not in before
            }
            check_training_authority(consumed, authority)
            batch = original.neural_batch(pack, ai, si, norm["features"], "cpu")
            indices = chunk.index.to_numpy()
            for name, tensor in zip(NAMES, batch):
                values = tensor.numpy()
                arrays[name][indices] = values
                if not np.array_equal(arrays[name][indices], values):
                    raise ValueError("Normalized input cache differs")
            if np.any(si < 0) or np.any(si >= 391):
                raise ValueError("Unexpected state index")
            arrays["state_key"][indices] = day_number * 391 + si
        for array in arrays.values():
            array.flush()
        flags.verify_files(consumed)
        same_json(
            done,
            dict(
                day_key=key,
                source_files=consumed,
                chunks=chunk_hashes(arrays, indices_all),
                started_sha256=flags.sha(started),
            ),
        )
        files.update(consumed)
        if (day_number + 1) % 100 == 0:
            print(
                json.dumps(dict(stage="cache", days=day_number + 1, total=len(keys))),
                flush=True,
            )
    for array in arrays.values():
        array.flush()
    arrays.clear()
    files.update(
        {str(p.resolve()): flags.sha(p) for p in working.rglob("*") if p.is_file()}
    )
    flags.verify_files(files)
    flags.preserve_incomplete(out, [out / "cache_complete.json.partial"])
    flags.atomic_json(
        out / "cache_complete.json",
        dict(
            status="COMPLETE_TRAIN_ONLY_CACHE",
            files=files,
            arrays={
                name: str((working / (name + ".npy")).resolve())
                for name in shape_records
            },
            model_config=config,
            rows=len(sample),
            days=len(keys),
            flags_root=str(root),
            learner_root=str(learner),
            layout=shape_records,
        ),
    )


def cached_train_evaluation(model, sample, cache, scales, device):
    saved, mode = flags.rng_state(), model.training
    frames = []
    try:
        model.eval()
        with torch.inference_mode():
            for _, rows in sample.groupby("day_key", sort=True):
                idx = rows.index.to_numpy()
                pred, logit = score_prepacked(
                    model, cache.inputs(idx, device), cache.state_keys(idx)
                )
                frames.append(
                    pd.DataFrame(
                        dict(
                            ticker=rows.ticker.to_numpy(),
                            target=(rows.net_base / rows.ticker.map(scales)).to_numpy(
                                float
                            ),
                            teacher=rows.state_optimal_action.to_numpy(float),
                            weight=rows.weight.to_numpy(float),
                            pred=pred.cpu().numpy().astype(float),
                            logit=logit.cpu().numpy().astype(float),
                        )
                    )
                )
        frame = pd.concat(frames, ignore_index=True)
        result = {}
        for name, f in [("pooled", frame)] + list(frame.groupby("ticker", sort=True)):
            w, y, p = f.weight.to_numpy(), f.target.to_numpy(), f.pred.to_numpy()
            mu = float(np.average(y, weights=w))
            probability = float(np.average(f.teacher, weights=w))
            null_sse = float(np.sum(w * (y - mu) ** 2))
            sse = float(np.sum(w * (p - y) ** 2))
            bce = float(np.sum(w * (np.logaddexp(0, f.logit) - f.teacher * f.logit)))
            entropy = -(probability * np.log(probability) if probability else 0) - (
                (1 - probability) * np.log1p(-probability) if probability < 1 else 0
            )
            result[name] = dict(
                rows=len(f),
                target_mean=mu,
                weighted_mse=sse / w.sum(),
                weighted_bce=bce / w.sum(),
                fixed_loss=(sse + 0.1 * bce) / 1024,
                constant_fixed_loss=(null_sse + 0.1 * w.sum() * entropy) / 1024,
                weighted_r2=1 - sse / null_sse if null_sse else None,
                prediction_mean=float(np.average(p, weights=w)),
                prediction_std=float(
                    np.sqrt(np.average((p - np.average(p, weights=w)) ** 2, weights=w))
                ),
            )
        return result
    finally:
        model.train(mode)
        flags.restore_rng(saved)


def train_cached(
    original,
    sample,
    cache,
    scales,
    out,
    device,
    binding,
    resume=False,
    epochs=4,
    diagnostic=True,
):
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(flags.SEED)
    np.random.seed(flags.SEED)
    if device.startswith("cuda"):
        torch.cuda.manual_seed_all(flags.SEED)
        torch.backends.cudnn.benchmark = False
    model = original.LevelTCN(**cache.config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
    rng = ReplayRNG()
    first, history = 0, []
    if resume and flags.reconcile_checkpoints(out):
        state = flags.load_checkpoint(out, model, optimizer, rng, binding)
        first, history = state["epoch"], state["history"]
        binding["files"].update(state["binding"]["files"])
    elif list(out.glob("tcn_epoch*.pt")):
        raise ValueError("Existing checkpoints require explicit resume")
    model.train()
    for epoch in range(first, epochs):
        before = rng.state
        plan = epoch_plan(sample, rng)
        after = rng.state
        binding["files"].update(persist_plan(out, epoch + 1, plan, before, after))
        if len(sample) == 270377 and (
            len(plan["sizes"]) != 1491 or plan["sizes"].sum() != 270377
        ):
            raise ValueError("Original update budget changed")
        norms, loss_total, offset = [], 0.0, 0
        started = time.monotonic()
        for step, size in enumerate(plan["sizes"]):
            indices = plan["mixed_order"][offset : offset + size]
            offset += size
            rows = sample.iloc[indices]
            target = torch.tensor(
                (rows.net_base / rows.ticker.map(scales)).to_numpy(np.float32),
                device=device,
            )
            teacher = torch.tensor(
                rows.state_optimal_action.to_numpy(np.float32), device=device
            )
            weight = torch.tensor(rows.weight.to_numpy(np.float32), device=device)
            optimizer.zero_grad(set_to_none=True)
            predicted, logits = score_prepacked(
                model, cache.inputs(indices, device), cache.state_keys(indices)
            )
            loss = common.fixed_loss(predicted, logits, target, teacher, weight)
            if not torch.isfinite(loss):
                raise FloatingPointError("Nonfinite row-mixed loss")
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            norms.append(float(norm.detach().cpu()))
            loss_total += float(loss.detach().cpu())
            if (step + 1) % 100 == 0:
                print(
                    json.dumps(
                        dict(
                            stage="row_mixed_train",
                            epoch=epoch + 1,
                            updates=step + 1,
                            elapsed_seconds=time.monotonic() - started,
                        )
                    ),
                    flush=True,
                )
        record = dict(
            epoch=epoch + 1,
            updates=len(norms),
            summed_fixed_batch_loss=loss_total,
            gradient_norms_preclip=norms,
            clip_fraction=float(np.mean(np.asarray(norms) > 1)),
            gradient_quantiles=np.quantile(norms, [0, 0.5, 0.9, 0.99, 1]).tolist(),
            schedule_rng_after=after["schedule"],
            mixed_rng_after=after["mixed"],
        )
        if diagnostic:
            record["fixed_train"] = cached_train_evaluation(
                model, sample, cache, scales, device
            )
        history.append(record)
        flags.verify_files(binding["files"])
        flags.save_checkpoint(
            out, model, optimizer, rng, epoch + 1, history, copy.deepcopy(binding)
        )
    return model, optimizer, history


def train(args):
    out = args.output.resolve()
    cache = RowCache(out)
    root = Path(cache.manifest["flags_root"])
    if root.resolve() != args.flags_root.resolve():
        raise ValueError("Cache FLAGS root differs from CLI")
    learner = Path(cache.manifest["learner_root"])
    original = flags.load_original(learner)
    sample = pd.read_parquet(root / "training_sample.parquet").reset_index(drop=True)
    scales = flags.read_json(root / "normalizers.json")["risk_scales_usd"]
    sources = {
        str(p.resolve()): flags.sha(p)
        for p in [
            Path(__file__),
            Path(flags.__file__),
            Path(common.__file__),
            out / "cache_complete.json",
        ]
    }
    sources.update(cache.manifest["files"])
    binding = dict(
        files=sources,
        device=args.device,
        seed=flags.SEED,
        epochs=4,
        variant="row_mixed_original_batch_sizes",
        torch_version=torch.__version__,
    )
    flags.verify_files(binding["files"])
    if (out / "training_complete.json").exists():
        raise FileExistsError("Completed training cannot be repeated")
    snapshot = out / "run_tcn_row_mixed.executed.py"
    if snapshot.exists() and flags.sha(snapshot) != flags.sha(__file__):
        raise ValueError("Training source snapshot changed")
    if not snapshot.exists():
        shutil.copy2(__file__, snapshot)
    model, _, history = train_cached(
        original, sample, cache, scales, out, args.device, binding, args.resume
    )
    flags.export_final(out, model, history, binding)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("build-cache", "train"), required=True)
    parser.add_argument("--flags-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    with flags.output_lock(args.output.resolve()):
        if args.stage == "build-cache":
            build_cache(args)
        else:
            train(args)


if __name__ == "__main__":
    main()
