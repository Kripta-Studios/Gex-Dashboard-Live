"""Isolated availability-normalization TCN experiment; no original artifact edits."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import platform
from pathlib import Path
import random
import shutil
import sys
import time
from datetime import datetime, timezone
from contextlib import contextmanager

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

SEED = 20261018
FRACTIONS = (
    "quote_valid_fraction",
    "iv_valid_fraction",
    "oi_known_fraction",
    "present_fraction",
    "delta_valid_fraction",
    "vega_valid_fraction",
    "theta_valid_fraction",
)
BASE_BITS = (
    "spot_valid",
    "ib_valid",
    "change_1m_valid",
    "change_5m_valid",
    "change_15m_valid",
) + tuple(
    f"{side}_{kind}_top{rank}_valid"
    for side in ("call", "put")
    for kind in ("oi", "gamma")
    for rank in (1, 2, 3)
)
ACTION_BITS = (
    "is_put",
    "quote_valid",
    "iv_valid",
    "greek_present",
    "delta_valid",
    "vega_valid",
    "theta_valid",
) + tuple(
    f"{role}_source_{kind}"
    for role in ("target", "stop")
    for kind in ("fib", "call_oi", "put_oi", "call_gamma", "put_gamma")
)
WHITELIST = {
    "base": BASE_BITS
    + ("ib_valid_fraction",)
    + tuple(f"current_{side}_{name}" for side in ("call", "put") for name in FRACTIONS),
    "tokens": ("spot_valid_fraction",)
    + tuple(f"{side}_{name}" for side in ("call", "put") for name in FRACTIONS),
    "action": ACTION_BITS,
    "maps": (),
}
SCHEMA_KEYS = {
    "base": "base_names",
    "tokens": "token_names",
    "action": "action_names",
    "maps": "map_names",
}
TICKERS = ("SPXW", "SPY", "QQQ")
POLICIES = tuple(
    f"{arm}__{threshold}" for arm in ("control", "variant") for threshold in (0, 5, 10)
)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@contextmanager
def output_lock(out):
    """Kernel-owned lock releases on process death; lock file is outside artifacts."""
    path = out.parent / ("." + out.name + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if path.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Output is already owned by another runner") from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError("Output is already owned by another runner") from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def atomic_json(path, value, replace=False):
    path = Path(path)
    if path.exists() and not replace:
        raise FileExistsError(path)
    temporary = path.with_name(path.name + ".partial")
    if temporary.exists():
        raise FileExistsError("Preserve partial artifact: " + str(temporary))
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)


def verify_files(files):
    for path, digest in files.items():
        if sha(path) != digest:
            raise ValueError("Changed bound source: " + path)


def load_original(root):
    path = Path(root) / "train_models.py"
    spec = importlib.util.spec_from_file_location("flags_original_train", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def override_stats(original, schema):
    """Name-based intervention only; no sampled values inform this transform."""
    adjusted = copy.deepcopy(original)
    changes = []
    for group, names in WHITELIST.items():
        axis = schema[SCHEMA_KEYS[group]]
        if len(axis) != len(set(axis)):
            raise ValueError("Duplicate schema name")
        for name in names:
            if axis.count(name) != 1:
                raise ValueError("Missing semantic channel: " + name)
            index = axis.index(name)
            adjusted["features"][group]["mean"][index] = 0.0
            adjusted["features"][group]["std"][index] = 1.0
            changes.append({"group": group, "name": name, "index": index})
    assert len(changes) == 64
    return adjusted, changes


def validate_pack(pack, schema):
    for group, names in WHITELIST.items():
        if not names:
            continue
        axis = schema[SCHEMA_KEYS[group]]
        values = pack["action_features" if group == "action" else group]
        for name in names:
            column = np.asarray(values[..., axis.index(name)])
            if not np.isfinite(column).all() or np.any((column < 0) | (column > 1)):
                raise ValueError("Invalid natural-range channel: " + name)
            if name in BASE_BITS + ACTION_BITS and not np.isin(column, [0, 1]).all():
                raise ValueError("Nonbinary flag: " + name)


class CheckedStore:
    def __init__(self, store, schema):
        self.store, self.schema, self.checked = store, schema, set()

    @property
    def hashes(self):
        return self.store.hashes

    @property
    def seal(self):
        return self.store.seal

    def rows(self, key, ids):
        result = self.store.rows(key, ids)
        if key not in self.checked:
            validate_pack(result[0], self.schema)
            if self.store.schema != self.schema:
                raise ValueError("Feature schema differs from original frozen schema")
            self.checked.add(key)
        return result


def rng_state(generator=None):
    return {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch": torch.get_rng_state(),
        "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else [],
        "generator": copy.deepcopy(generator.bit_generator.state)
        if generator is not None
        else None,
    }


def restore_rng(state, generator=None):
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch"])
    if state["cuda"]:
        torch.cuda.set_rng_state_all(state["cuda"])
    if generator is not None:
        generator.bit_generator.state = state["generator"]


def save_checkpoint(out, model, optimizer, generator, epoch, history, binding):
    path = out / f"tcn_epoch{epoch:02}.pt"
    if path.exists() or path.with_suffix(".json").exists():
        raise FileExistsError("Completed checkpoint is immutable")
    temporary = path.with_suffix(".partial")
    if temporary.exists():
        raise FileExistsError(temporary)
    torch.save(
        {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "rng": rng_state(generator),
            "epoch": epoch,
            "history": history,
            "binding": binding,
            "config": model.config,
        },
        temporary,
    )
    os.replace(temporary, path)
    metadata = {
        "epoch": epoch,
        "sha256": sha(path),
        "binding": binding,
        "complete_epoch_boundary": True,
    }
    atomic_json(path.with_suffix(".json"), metadata)
    atomic_json(
        out / "latest_checkpoint.json",
        {
            "file": path.name,
            "metadata_sha256": sha(path.with_suffix(".json")),
            "sha256": metadata["sha256"],
            "epoch": epoch,
        },
        replace=True,
    )


def preserve_incomplete(out, paths):
    paths = list(dict.fromkeys(p for p in paths if p.exists()))
    if not paths:
        return
    destination = (
        out / "recovery" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    )
    destination.mkdir(parents=True, exist_ok=False)
    record = {str(p): sha(p) for p in paths}
    for path in paths:
        os.replace(path, destination / path.name)
    atomic_json(destination / "preserved.json", record)


def reconcile_checkpoints(out):
    """Recover durable completed pairs; preserve unsealed files before repeating an epoch."""
    complete = []
    incomplete = list(out.glob("tcn_epoch*.partial")) + list(
        out.glob("tcn_epoch*.json.partial")
    )
    for path in sorted(out.glob("tcn_epoch*.pt")):
        metadata_path = path.with_suffix(".json")
        if not metadata_path.exists():
            incomplete.append(path)
            continue
        metadata = read_json(metadata_path)
        if (
            not metadata.get("complete_epoch_boundary")
            or sha(path) != metadata["sha256"]
        ):
            raise ValueError("Corrupted completed checkpoint")
        verify_files(metadata["binding"]["files"])
        complete.append((path, metadata_path, metadata))
    for path in out.glob("tcn_epoch*.json"):
        if not path.with_suffix(".pt").exists():
            raise ValueError("Completed checkpoint metadata lacks model")
    preserve_incomplete(
        out, incomplete + list(out.glob("latest_checkpoint.json.partial"))
    )
    if not complete:
        if (out / "latest_checkpoint.json").exists():
            raise ValueError("Pointer exists without completed checkpoint")
        return False
    epochs = [metadata["epoch"] for _, _, metadata in complete]
    if epochs != list(range(1, len(epochs) + 1)):
        raise ValueError("Completed epochs are not contiguous")
    path, metadata_path, metadata = complete[-1]
    latest = {
        "file": path.name,
        "metadata_sha256": sha(metadata_path),
        "sha256": metadata["sha256"],
        "epoch": metadata["epoch"],
    }
    pointer = out / "latest_checkpoint.json"
    if pointer.exists() and read_json(pointer) != latest:
        # Preserve the stale pointer before replacing it with a verified newer pair.
        preserve_incomplete(out, [pointer])
    if not pointer.exists():
        atomic_json(pointer, latest)
    return True


def load_checkpoint(out, model, optimizer, generator, binding):
    latest = read_json(out / "latest_checkpoint.json")
    path = out / latest["file"]
    metadata = read_json(path.with_suffix(".json"))
    completed = sorted(out.glob("tcn_epoch*.json"))
    if completed[-1] != path.with_suffix(".json"):
        raise ValueError("Latest pointer is not the newest completed checkpoint")
    if (
        sha(path) != latest["sha256"]
        or sha(path.with_suffix(".json")) != latest["metadata_sha256"]
        or metadata["sha256"] != latest["sha256"]
    ):
        raise ValueError("Checkpoint hash mismatch")
    prior = metadata["binding"]
    for key, value in binding.items():
        if key != "files" and prior[key] != value:
            raise ValueError("Checkpoint environment mismatch: " + key)
    for key, value in binding["files"].items():
        if prior["files"].get(key) != value:
            raise ValueError("Checkpoint base input mismatch")
    verify_files(prior["files"])
    state = torch.load(path, map_location="cpu", weights_only=False)
    if state["binding"] != prior or state["epoch"] != metadata["epoch"]:
        raise ValueError("Checkpoint inner binding mismatch")
    model.load_state_dict(state["model"])
    optimizer.load_state_dict(state["optimizer"])
    restore_rng(state["rng"], generator)
    return state


def fixed_train_evaluation(original, model, sample, store, scales, stats, device):
    saved, was_training = rng_state(), model.training
    arrays = []
    try:
        model.eval()
        with torch.inference_mode():
            for key, rows in sample.groupby("day_key", sort=True):
                p, ai, si = store.rows(key, rows.action_id)
                pred, logits = original.neural_actions(model, p, ai, si, stats, device)
                arrays.append(
                    pd.DataFrame(
                        {
                            "ticker": rows.ticker.to_numpy(),
                            "target": (
                                rows.net_base / rows.ticker.map(scales)
                            ).to_numpy(float),
                            "teacher": rows.state_optimal_action.to_numpy(float),
                            "weight": rows.weight.to_numpy(float),
                            "pred": pred.cpu().numpy().astype(float),
                            "logit": logits.cpu().numpy().astype(float),
                        }
                    )
                )
        frame = pd.concat(arrays, ignore_index=True)
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
            result[name] = {
                "rows": len(f),
                "target_mean": mu,
                "weighted_mse": sse / w.sum(),
                "weighted_bce": bce / w.sum(),
                "fixed_loss": (sse + 0.1 * bce) / 1024,
                "constant_fixed_loss": (null_sse + 0.1 * w.sum() * entropy) / 1024,
                "weighted_r2": 1 - sse / null_sse if null_sse else None,
                "prediction_mean": float(np.average(p, weights=w)),
                "prediction_std": float(
                    np.sqrt(np.average((p - np.average(p, weights=w)) ** 2, weights=w))
                ),
            }
        return result
    finally:
        model.train(was_training)
        restore_rng(saved)


def train_instrumented(
    original,
    sample,
    store,
    scales,
    stats,
    out,
    device,
    binding,
    resume=False,
    epochs=4,
    diagnostic=True,
):
    """Same optimizer steps as frozen train_tcn; extra work is observation only."""
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    if device.startswith("cuda"):
        torch.cuda.manual_seed_all(SEED)
        torch.backends.cudnn.benchmark = False
    first = sample.iloc[0]
    pack, ai, si = store.rows(first.day_key, [first.action_id])
    batch = original.neural_batch(pack, ai, si, stats, device)
    model = original.LevelTCN(
        pack["base"].shape[-1],
        pack["tokens"].shape[-1],
        pack["action_features"].shape[-1],
        batch[4].shape[-1],
        batch[5].shape[-1],
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
    groups = {k: r.index.to_numpy() for k, r in sample.groupby("day_key", sort=True)}
    keys = np.array(sorted(groups), dtype=object)
    generator = np.random.default_rng(SEED)
    first_epoch, history = 0, []
    if resume and reconcile_checkpoints(out):
        previous = load_checkpoint(out, model, optimizer, generator, binding)
        first_epoch, history = previous["epoch"], previous["history"]
        binding["files"].update(previous["binding"]["files"])
    model.train()
    for epoch in range(first_epoch, epochs):
        epoch_started = time.monotonic()
        norms, loss_total, net_total, teacher_total = [], 0.0, 0.0, 0.0
        for key in generator.permutation(keys):
            indices = generator.permutation(groups[key])
            for start in range(0, len(indices), 1024):
                rows = sample.loc[indices[start : start + 1024]]
                p, ai, si = store.rows(key, rows.action_id)
                target = torch.as_tensor(
                    (rows.net_base / rows.ticker.map(scales)).to_numpy(np.float32),
                    device=device,
                )
                teacher = torch.as_tensor(
                    rows.state_optimal_action.to_numpy(np.float32), device=device
                )
                weights = torch.as_tensor(
                    rows.weight.to_numpy(np.float32), device=device
                )
                optimizer.zero_grad(set_to_none=True)
                predicted, logits = original.neural_actions(
                    model, p, ai, si, stats, device
                )
                squared = (predicted - target).square()
                bce = F.binary_cross_entropy_with_logits(
                    logits, teacher, reduction="none"
                )
                loss = (weights * (squared + 0.1 * bce)).sum() / 1024
                if not torch.isfinite(loss):
                    raise FloatingPointError("Nonfinite fixed loss; no retuning")
                loss.backward()
                norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                norms.append(float(norm.detach().cpu()))
                loss_total += float(loss.detach().cpu())
                net_total += float((weights * squared).sum().detach().cpu()) / 1024
                teacher_total += (
                    float((weights * 0.1 * bce).sum().detach().cpu()) / 1024
                )
                if len(norms) % 100 == 0:
                    print(
                        json.dumps(
                            {
                                "stage": "training_progress",
                                "epoch": epoch + 1,
                                "updates": len(norms),
                                "elapsed_seconds": round(
                                    time.monotonic() - epoch_started, 2
                                ),
                            }
                        ),
                        flush=True,
                    )
        if not np.isfinite(norms).all():
            raise FloatingPointError("Nonfinite gradient norms")
        record = {
            "epoch": epoch + 1,
            "summed_fixed_batch_loss": loss_total,
            "online_net_loss": net_total,
            "online_teacher_loss": teacher_total,
            "updates": len(norms),
            "gradient_norms_preclip": norms,
            "clip_fraction": float(np.mean(np.asarray(norms) > 1)),
            "gradient_quantiles": np.quantile(norms, [0, 0.5, 0.9, 0.99, 1]).tolist(),
        }
        if diagnostic:
            record["fixed_train"] = fixed_train_evaluation(
                original, model, sample, store, scales, stats, device
            )
        history.append(record)
        binding["files"].update(store.hashes)
        if getattr(store, "seal", None) is not None:
            binding["files"].update(store.seal.hashes)
        save_checkpoint(
            out, model, optimizer, generator, epoch + 1, history, copy.deepcopy(binding)
        )
        print(
            json.dumps(
                {
                    "stage": "epoch",
                    "epoch": epoch + 1,
                    "clip_fraction": record["clip_fraction"],
                }
            ),
            flush=True,
        )
    return model, optimizer, history


def export_final(out, model, history, binding):
    """Idempotent fourth-epoch export, including a crash after model rename."""
    if len(history) != 4 or history[-1]["epoch"] != 4:
        raise ValueError("Final export requires four complete epochs")
    path = out / "tcn_variant.pt"
    preserve_incomplete(
        out,
        list(out.glob("tcn_variant.partial"))
        + list(out.glob("training_complete.json.partial")),
    )
    state = {
        "state_dict": model.cpu().state_dict(),
        "config": model.config,
        "epoch": 4,
        "seed": SEED,
    }
    if path.exists():
        previous = torch.load(path, map_location="cpu", weights_only=True)
        if (
            previous["config"] != state["config"]
            or previous["epoch"] != 4
            or previous["seed"] != SEED
        ):
            raise ValueError("Existing final model identity differs")
        if previous["state_dict"].keys() != state["state_dict"].keys() or any(
            not torch.equal(previous["state_dict"][k], value)
            for k, value in state["state_dict"].items()
        ):
            raise ValueError("Existing final model differs from fourth epoch")
    else:
        temporary = out / "tcn_variant.partial"
        torch.save(state, temporary)
        os.replace(temporary, path)
    completion = {"history": history, "model_sha256": sha(path), "binding": binding}
    if (out / "training_complete.json").exists():
        if read_json(out / "training_complete.json") != completion:
            raise ValueError("Final completion differs")
    else:
        atomic_json(out / "training_complete.json", completion)


def daily_gate(ledger, calendar, available):
    counts = ledger.groupby(["ticker", "date"]).size().to_dict()
    rows = [
        {
            "ticker": ticker,
            "date": date,
            "filled": int(counts.get((ticker, date), 0)),
            "status": "OBSERVABLE" if (ticker, date) in available else "NO_EVALUABLE",
        }
        for date in calendar
        for ticker in TICKERS
    ]
    frame = pd.DataFrame(rows)
    observed = frame.status == "OBSERVABLE"
    return {
        "passes": bool(observed.all() and (frame.filled >= 1).all()),
        "expected_days": len(frame),
        "no_evaluable_days": int((~observed).sum()),
        "observable_days": int(observed.sum()),
        "observable_days_with_trade": int((observed & (frame.filled >= 1)).sum()),
        "observable_daily_pass": bool(
            observed.any() and (frame.loc[observed, "filled"] >= 1).all()
        ),
    }, frame


def select_validation(summaries, scales):
    scores = {
        p: sum(summaries[p]["tickers"][t]["base_net_usd"] / scales[t] for t in TICKERS)
        for p in POLICIES
    }
    ranked = sorted(POLICIES, key=lambda p: (-scores[p], POLICIES.index(p)))
    eligible = [p for p in ranked if summaries[p]["daily_gate"]["passes"]]
    return {
        "selected_policy": eligible[0] if eligible else None,
        "diagnostic_best_not_approved": None if eligible else ranked[0],
        "scores": scores,
        "eligible": eligible,
        "best_per_arm_2025": {
            arm: next(p for p in ranked if p.startswith(arm))
            for arm in ("control", "variant")
        },
    }


def prepare(
    original, learner_root, engine_root, feature_root, out, audit_path, oracle_audit
):
    if out.exists():
        raise FileExistsError("New experiment requires an exclusive root")
    audit = read_json(audit_path)
    if audit["status"] != "PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT":
        raise ValueError("Original learner economics not audited")
    if Path(audit["binding"]["learner_root"]).resolve() != learner_root.resolve():
        raise ValueError("Wrong original learner root")
    binding_checks = {
        learner_root / "summary.json": "learner_summary_sha256",
        learner_root / "freeze.json": "freeze_sha256",
        learner_root
        / "validation/prediction_hashes.json": "validation_prediction_manifest_sha256",
        learner_root / "test/prediction_hashes.json": "test_prediction_manifest_sha256",
        engine_root / "index.parquet": "oracle_index_sha256",
        engine_root / "completion.json": "oracle_completion_sha256",
        oracle_audit: "oracle_full_audit_sha256",
    }
    for path, key in binding_checks.items():
        if sha(path) != audit["binding"][key]:
            raise ValueError("Original audit binding mismatch: " + key)
    freeze = read_json(learner_root / "freeze.json")
    verify_files({str(learner_root / p): h for p, h in freeze["artifacts"].items()})
    if sha(learner_root / "train_models.py") != freeze["script_sha256"]:
        raise ValueError("Wrong frozen original code")
    oracle = original.require_oracle_pass(oracle_audit, engine_root)
    schema = read_json(learner_root / "feature_schema.json")
    adjusted, changes = override_stats(
        read_json(learner_root / "normalizers.json"), schema
    )
    days = original.discover_days(engine_root, feature_root)
    out.mkdir(parents=True)
    original.verify_full_coverage(days, out)
    copied = (
        "training_sample.parquet",
        "sampling_manifest.json",
        "feature_schema.json",
    )
    for name in copied:
        shutil.copyfile(learner_root / name, out / name)
    shutil.copyfile(
        learner_root / "normalizers.json", out / "original_normalizers.json"
    )
    shutil.copyfile(__file__, out / "run_tcn_flags.executed.py")
    plan = Path(__file__).with_name("TCN_FLAGS_V1_PLAN.md")
    shutil.copyfile(plan, out / plan.name)
    atomic_json(out / "normalizers.json", adjusted)
    atomic_json(out / "normalization_intervention.json", changes)
    files = {str(path.resolve()): sha(path) for path in binding_checks}
    files.update(
        {
            str((learner_root / name).resolve()): sha(learner_root / name)
            for name in (
                *copied,
                "normalizers.json",
                "train_models.py",
                "run_policy.py",
                "level_engine.py",
                "features.py",
                "build_cache.py",
            )
        }
    )
    files.update({str(p.resolve()): sha(p) for p in (Path(__file__), plan, audit_path)})
    files.update(oracle["verified_files"])
    files.update({str(p.resolve()): sha(p) for p in out.iterdir() if p.is_file()})
    atomic_json(
        out / "identity.json",
        {
            "status": "PREPARED_NO_FIT",
            "seed": SEED,
            "learner_root": str(learner_root.resolve()),
            "engine_root": str(engine_root.resolve()),
            "feature_root": str(feature_root.resolve()),
            "files": files,
            "oracle_audit": oracle,
            "semantic_channels": len(changes),
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )


def inference(original, model, store, day, actions, stats, scale, device):
    if not len(actions):
        return np.empty(0, dtype=float)
    pack, ai, si = store.rows(day.key, actions.action_id)
    result = []
    with torch.inference_mode():
        states = original.encode_unique_states(
            model, pack, np.arange(len(pack["base"])), stats, device
        )
        for start in range(0, len(actions), 1024):
            take = slice(start, start + 1024)
            encoded = torch.as_tensor(
                original.normalized(pack["action_features"][ai[take]], stats["action"]),
                device=device,
            )
            predictions, _ = model.score_actions(
                states[torch.as_tensor(si[take], device=device)], encoded
            )
            result.append(predictions.cpu().numpy().astype(float) * scale)
    scores = np.concatenate(result)
    if not np.isfinite(scores).all():
        raise FloatingPointError("Nonfinite variant predictions")
    return scores


def evaluate_period(
    original, days, store, model, scales, stats, out, learner_root, period, device
):
    lower, upper = (
        ("20250101", "20260101") if period == "validation" else ("20260101", "20260701")
    )
    target = out / period
    target.mkdir(exist_ok=True)
    policy = original.import_sibling("run_policy")
    engine = original.import_sibling("level_engine")
    control_manifest = read_json(learner_root / period / "prediction_hashes.json")
    relevant = [d for d in days if lower <= d.date < upper]
    expected_names = {d.ticker + "_" + d.date + ".npz" for d in relevant}
    if set(control_manifest) != expected_names:
        raise ValueError("Control prediction universe mismatch")
    frames = {p: [] for p in POLICIES}
    attempts = {p: [] for p in POLICIES}
    manifests = {}
    model.eval()
    for number, day in enumerate(relevant):
        stem = day.ticker + "_" + day.date
        done = target / (stem + ".json")
        if done.exists():
            record = read_json(done)
            verify_files(record["files"])
            verify_files(record["feature_files"])
            verify_files(record["oracle_files"])
            store.hashes.update(record["feature_files"])
            store.seal.hashes.update(record["oracle_files"])
        else:
            store.seal.check(day, "actions.parquet")
            actions = pd.read_parquet(day.oracle / "actions.parquet")
            original_file = learner_root / period / (stem + ".npz")
            if sha(original_file) != control_manifest[original_file.name]:
                raise ValueError("Changed original control prediction")
            with np.load(original_file, allow_pickle=False) as data:
                if not np.array_equal(data["action_ids"], actions.action_id.to_numpy()):
                    raise ValueError("Control/action alignment mismatch")
                control = data["tcn_teacher"].copy()
            if not np.isfinite(control).all():
                raise FloatingPointError("Nonfinite original control")
            prediction_file = target / (stem + ".npz")
            # A crash after this immutable write may resume this score vector.
            prediction_seal = target / (stem + ".prediction.json")
            if prediction_seal.exists():
                prediction_record = read_json(prediction_seal)
                verify_files(prediction_record["files"])
                verify_files(prediction_record["feature_files"])
                store.hashes.update(prediction_record["feature_files"])
                with np.load(prediction_file, allow_pickle=False) as data:
                    if not np.array_equal(
                        data["action_ids"], actions.action_id.to_numpy()
                    ):
                        raise ValueError("Resumed prediction/action mismatch")
                    variant = data["variant"].copy()
            else:
                if prediction_file.exists():
                    raise FileExistsError(
                        "Unsealed prediction preserved: " + str(prediction_file)
                    )
                variant = inference(
                    original,
                    model,
                    store,
                    day,
                    actions,
                    stats,
                    scales[day.ticker],
                    device,
                )
                temporary = prediction_file.with_suffix(".partial.npz")
                if temporary.exists():
                    raise FileExistsError(temporary)
                np.savez_compressed(
                    temporary,
                    action_ids=actions.action_id.to_numpy(),
                    control=control,
                    variant=variant,
                )
                os.replace(temporary, prediction_file)
                atomic_json(
                    prediction_seal,
                    {
                        "files": {
                            str(prediction_file): sha(prediction_file),
                            str(out / "tcn_variant.pt"): sha(out / "tcn_variant.pt"),
                            str(original_file): sha(original_file),
                        },
                        "feature_files": {
                            p: h
                            for p, h in store.hashes.items()
                            if day.date in p or p.endswith("feature_contract.json")
                        },
                    },
                )
            # This access follows the sealed predictions, including on recovery.
            store.seal.check(day, "labels.parquet")
            labels = pd.read_parquet(day.oracle / "labels.parquet")
            view = policy.PolicyView(actions, labels)
            files = {
                str(prediction_file): sha(prediction_file),
                str(prediction_seal): sha(prediction_seal),
                str(original_file): sha(original_file),
            }
            for arm, scores in (("control", control), ("variant", variant)):
                ranked = view.rank(scores)
                for threshold in (0, 5, 10):
                    ident = f"{arm}__{threshold}"
                    result = view.evaluate(scores, threshold, engine, ranked)
                    frame = result.attempts.copy()
                    frame["ticker"], frame["date"], frame["policy"] = (
                        day.ticker,
                        day.date,
                        ident,
                    )
                    destination = target / (stem + "_" + ident + ".parquet")
                    # Incomplete day shards are deterministic but never overwritten.
                    if destination.exists():
                        pd.testing.assert_frame_equal(
                            pd.read_parquet(destination), frame, check_dtype=False
                        )
                    else:
                        frame.to_parquet(destination, index=False)
                    files[str(destination)] = sha(destination)
            record = {
                "files": files,
                "feature_files": dict(store.hashes),
                "oracle_files": dict(store.seal.hashes),
            }
            # Only sources of this day needed; avoid quadratic checkpoint metadata.
            record["feature_files"] = {
                p: h
                for p, h in record["feature_files"].items()
                if day.date in p or p.endswith("feature_contract.json")
            }
            record["oracle_files"] = {
                p: h for p, h in record["oracle_files"].items() if day.date in p
            }
            atomic_json(done, record)
        manifests[done.name] = sha(done)
        for ident in POLICIES:
            frame = pd.read_parquet(target / (stem + "_" + ident + ".parquet"))
            attempts[ident].append(frame)
            frames[ident].append(frame.loc[frame.status == "FILLED"])
        if number % 50 == 0:
            print(
                json.dumps({"stage": period, "completed_days": number + 1}), flush=True
            )
    calendar = pd.read_csv(out / "expected_full_calendar.csv", dtype=str).date
    calendar = calendar.loc[(calendar >= lower) & (calendar < upper)].tolist()
    available = {(d.ticker, d.date) for d in relevant}
    summaries = {}
    months = sorted({date[:6] for date in calendar})
    for ident in POLICIES:
        ledger = (
            pd.concat(frames[ident], ignore_index=True)
            .sort_values(["date", "exit_i", "ticker", "state_i"], kind="stable")
            .reset_index(drop=True)
        )
        gate, daily = daily_gate(ledger, calendar, available)
        summary = {
            "daily_gate": gate,
            "pooled": original.economic_metrics(ledger),
            "tickers": {
                t: original.economic_metrics(ledger.loc[ledger.ticker == t])
                for t in TICKERS
            },
            "months": {
                t: {
                    m: original.economic_metrics(
                        ledger.loc[(ledger.ticker == t) & ledger.date.str.startswith(m)]
                    )
                    for m in months
                }
                for t in TICKERS
            },
        }
        summaries[ident] = summary
        # Summaries are written only once after all deterministic daily shards.
        for name, frame in (
            ("ledger", ledger),
            ("attempts", pd.concat(attempts[ident], ignore_index=True)),
            ("daily_coverage", daily),
        ):
            destination = target / f"{ident}_{name}.parquet"
            if destination.exists():
                pd.testing.assert_frame_equal(
                    pd.read_parquet(destination), frame, check_dtype=False
                )
            else:
                frame.to_parquet(destination, index=False)
    for name, value in (
        ("summary.json", summaries),
        ("prediction_manifest.json", manifests),
    ):
        if (target / name).exists():
            if read_json(target / name) != value:
                raise ValueError("Resumed period summary mismatch")
        else:
            atomic_json(target / name, value)
    return summaries


def require_prior_freeze(out):
    if (out / "test").exists() and not (out / "freeze.json").exists():
        raise ValueError(
            "Test artifacts exist without prior freeze; refuse reconstruction"
        )
    if (out / "freeze.json").exists():
        verify_files(read_json(out / "freeze.json")["files"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parent = Path("D:/GexResearchArtifacts/level_oracle_20261018")
    parser.add_argument("--learner-root", type=Path, default=parent / "learners_v1")
    parser.add_argument("--engine-root", type=Path, default=parent / "engine_v1")
    parser.add_argument("--feature-root", type=Path, default=parent / "features_v1")
    parser.add_argument("--output", type=Path, default=parent / "tcn_flags_v1")
    parser.add_argument(
        "--audit", type=Path, default=parent / "learners_v1_economic_audit/audit.json"
    )
    parser.add_argument(
        "--oracle-audit", type=Path, default=parent / "engine_v1_audit_v4/audit.json"
    )
    parser.add_argument(
        "--stage", choices=("prepare", "train", "evaluate"), default="prepare"
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    with output_lock(args.output):
        execute(args)


def execute(args):
    original = load_original(args.learner_root)
    if args.stage == "prepare":
        prepare(
            original,
            args.learner_root,
            args.engine_root,
            args.feature_root,
            args.output,
            args.audit,
            args.oracle_audit,
        )
        return
    out = args.output
    identity = read_json(out / "identity.json")
    for key in ("learner_root", "engine_root", "feature_root"):
        if Path(identity[key]).resolve() != getattr(args, key).resolve():
            raise ValueError("Runtime root differs from prepared identity")
    verify_files(identity["files"])
    if args.stage == "evaluate":
        require_prior_freeze(out)
    days = original.discover_days(args.engine_root, args.feature_root)
    seal = original.SourceSeal(args.engine_root)
    store = CheckedStore(
        original.FeatureStore(days, capacity=2, seal=seal),
        read_json(out / "feature_schema.json"),
    )
    normalizers = read_json(out / "normalizers.json")
    stats, scales = normalizers["features"], normalizers["risk_scales_usd"]
    if args.stage == "train":
        if (out / "training_complete.json").exists():
            raise FileExistsError("Training already completed")
        if (out / "tcn_variant.pt").exists() and not args.resume:
            raise ValueError("Partial final export requires --resume")
        sample = pd.read_parquet(out / "training_sample.parquet")
        if (
            len(sample) != 270377
            or not sample.day_key.str.split("/")
            .str[-1]
            .between("20230101", "20241231")
            .all()
        ):
            raise ValueError("Original TRAIN sample mismatch")
        binding = {
            "files": {
                **identity["files"],
                str(out / "identity.json"): sha(out / "identity.json"),
            },
            "output_root": str(out.resolve()),
            "device": args.device,
            "torch": torch.__version__,
            "numpy": np.__version__,
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "cuda": torch.version.cuda,
            "cudnn": torch.backends.cudnn.version(),
            "device_name": torch.cuda.get_device_name()
            if args.device.startswith("cuda")
            else "CPU",
        }
        model, _, history = train_instrumented(
            original,
            sample,
            store,
            scales,
            stats,
            out,
            args.device,
            binding,
            resume=args.resume,
        )
        verify_files(binding["files"])
        export_final(out, model, history, binding)
        return
    if (out / "summary.json").exists():
        raise FileExistsError("Evaluation already completed")
    require_prior_freeze(out)
    training = read_json(out / "training_complete.json")
    verify_files(training["binding"]["files"])
    if sha(out / "tcn_variant.pt") != training["model_sha256"]:
        raise ValueError("Final model changed")
    state = torch.load(out / "tcn_variant.pt", map_location="cpu", weights_only=True)
    if state["epoch"] != 4:
        raise ValueError("Only fourth epoch allowed")
    if training["binding"]["device"] != args.device:
        raise ValueError("Inference device must match frozen training device")
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    if args.device.startswith("cuda"):
        torch.backends.cudnn.benchmark = False
    model = original.LevelTCN(**state["config"]).to(args.device)
    model.load_state_dict(state["state_dict"])
    validation = evaluate_period(
        original,
        days,
        store,
        model,
        scales,
        stats,
        out,
        args.learner_root,
        "validation",
        args.device,
    )
    selection = select_validation(validation, scales)
    freeze_path = out / "freeze.json"
    if freeze_path.exists():
        freeze = read_json(freeze_path)
        verify_files(freeze["files"])
        if freeze["selection"] != selection:
            raise ValueError("Frozen selection changed")
    else:
        files = {
            str(p): sha(p)
            for p in out.rglob("*")
            if p.is_file() and "test" not in p.relative_to(out).parts
        }
        files.update(store.hashes)
        files.update(seal.hashes)
        atomic_json(
            freeze_path,
            {
                "selection": selection,
                "files": files,
                "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
                "test_evaluated": False,
            },
        )
        freeze = read_json(freeze_path)
    test = evaluate_period(
        original,
        days,
        store,
        model,
        scales,
        stats,
        out,
        args.learner_root,
        "test",
        args.device,
    )
    selected = selection["selected_policy"]
    gate = {"passes": False, "reason": "NO_VALIDATION_DAILY_COMPLIANT_POLICY"}
    if selected is not None:
        gate = original.economic_gate({"policy": selected}, test)
        gate["daily_gate"] = test[selected]["daily_gate"]
        gate["passes"] = gate["passes"] and gate["daily_gate"]["passes"]
    paired = {
        str(t): {
            "base_delta_usd": test[f"variant__{t}"]["pooled"]["base_net_usd"]
            - test[f"control__{t}"]["pooled"]["base_net_usd"],
            "adverse_delta_usd": test[f"variant__{t}"]["pooled"]["adverse_net_usd"]
            - test[f"control__{t}"]["pooled"]["adverse_net_usd"],
        }
        for t in (0, 5, 10)
    }
    verify_files(freeze["files"])
    verify_files(store.hashes)
    seal.recheck()
    atomic_json(
        out / "summary.json",
        {
            "status": "COMPLETE",
            "selection": selection,
            "selected_test": test[selected] if selected else None,
            "gate": gate,
            "paired_same_threshold_test": paired,
            "test": test,
            "development_seen": True,
            "promotion_approved": False,
            "freeze_sha256": sha(freeze_path),
        },
    )
    atomic_json(
        out / "completion.json",
        {
            "status": "COMPLETE",
            "files": {
                str(out / name): sha(out / name)
                for name in (
                    "summary.json",
                    "freeze.json",
                    "training_complete.json",
                    "validation/summary.json",
                    "validation/prediction_manifest.json",
                    "test/summary.json",
                    "test/prediction_manifest.json",
                )
            },
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )


if __name__ == "__main__":
    main()
