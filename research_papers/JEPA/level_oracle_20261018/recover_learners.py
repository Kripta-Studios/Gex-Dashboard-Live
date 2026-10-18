"""Explicit stage continuation; never run beside the original learner process.

The producer and scientific plan remain immutable. Interrupted work is preserved.
This controller reuses complete GBTs and complete epoch pairs, and replays only
unfinished deterministic evaluation. It does not recover scientific failures.
"""

from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import inspect
import json
import os
from pathlib import Path
import subprocess
import time

import stage_recovery as recovery


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def summary_state(path):
    if not path.exists():
        return "absent"
    try:
        value = read(path)
    except (ValueError, OSError):
        return "partial"
    required = {
        "selected_policy",
        "provisional_gate",
        "validation_choices",
        "risk_scales_usd",
    }
    return (
        "complete"
        if isinstance(value, dict)
        and value.get("status") == "COMPLETED_CAUSAL_LEARNER_DEVELOPMENT"
        and required.issubset(value)
        else "partial"
    )


def freeze_state(path):
    if not path.exists():
        return "absent"
    try:
        value = read(path)
    except (ValueError, OSError):
        return "partial"
    required = {
        "artifacts",
        "selected_policy",
        "validation_choices",
        "feature_sources",
        "oracle_audit",
        "script_sha256",
        "plan_sha256",
        "engine_sha256",
        "scheduler_sha256",
        "protocol_sha256",
    }
    return (
        "complete"
        if isinstance(value, dict) and required.issubset(value)
        else "partial"
    )


@contextmanager
def output_lock(output):
    """OS byte lock; the kernel releases it even if the owner process dies."""
    import msvcrt

    path = output / "recovery.lock"
    with path.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise ValueError("Recovery output lock is already held") from error
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def guard_freeze_authority(output):
    state = freeze_state(output / "freeze.json")
    if state in ("absent", "partial") and (output / "test").exists():
        raise ValueError(
            "Missing or incomplete freeze with existing test requires diagnosis; cannot reconstruct authority"
        )
    return state


def fingerprint():
    import lightgbm
    import numpy
    import pandas
    import torch

    gpu = (
        subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,uuid,memory.total,driver_version,compute_cap",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.strip()
        .splitlines()
    )
    return {
        "torch": torch.__version__,
        "numpy": numpy.__version__,
        "lightgbm": lightgbm.__version__,
        "pandas": pandas.__version__,
        "cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "gpus": gpu,
        "python": os.sys.version,
    }


def capture_environment(runtime, target):
    import psutil

    started = read(runtime / "started.json")
    process = psutil.Process(started["pid"])
    command = process.cmdline()
    if not any("train_models.py" in part for part in command):
        raise ValueError("PID is not the original learner")
    record = {
        "utc": recovery.utc(),
        "pid": process.pid,
        "create_time": process.create_time(),
        "command": command,
        "environment": fingerprint(),
    }
    if target.exists():
        previous = read(target)
        for key in ("pid", "create_time", "command", "environment"):
            if previous[key] != record[key]:
                raise ValueError("Recovery environment/identity changed: " + key)
        return previous
    recovery.atomic_json(target, record)
    return record


def ensure_stopped(identity, output):
    import psutil

    try:
        process = psutil.Process(identity["pid"])
        if process.create_time() == identity["create_time"]:
            raise ValueError("Original learner process is still alive")
    except psutil.NoSuchProcess:
        pass
    # PID reuse does not authorize touching that process. Also reject a newer
    # continuation for this exact output, regardless of its PID.
    for process in psutil.process_iter(["pid", "cmdline"]):
        if process.pid == os.getpid():
            continue
        command = process.info["cmdline"] or []
        if not any(
            Path(p).name in ("train_models.py", "recover_learners.py") for p in command
        ):
            continue
        if "--output" in command:
            position = command.index("--output")
            if (
                position + 1 < len(command)
                and Path(command[position + 1]).resolve() == output.resolve()
            ):
                raise ValueError("Another learner owns this output")


def check_failure(runtime, reason):
    if reason not in ("process_interruption", "resource_exhaustion", "io_interruption"):
        raise ValueError("Only explicit technical interruptions can be continued")
    text = "\n".join(
        (runtime / name).read_text(encoding="utf-8", errors="replace")
        for name in ("stdout.log", "stderr.log")
        if (runtime / name).exists()
    )
    forbidden = (
        "FloatingPointError",
        "Nonfinite",
        "nonfinite",
        "Changed frozen",
        "Resume input changed",
        "Feature source changed",
        "AssertionError",
    )
    if any(word in text for word in forbidden):
        raise ValueError(
            "Scientific/nonfinite/identity failure cannot be automatically recovered"
        )
    if "Traceback" in text and not any(
        word in text
        for word in (
            "MemoryError",
            "OutOfMemoryError",
            "CUDA out of memory",
            "OSError",
            "PermissionError",
            "KeyboardInterrupt",
            "WinError",
        )
    ):
        raise ValueError(
            "Unclassified failure requires diagnosis, not automatic continuation"
        )


def preserve(path, output, archive, reason):
    path, output, archive = path.resolve(), output.resolve(), archive.resolve()
    if (
        not path.is_relative_to(output)
        or path == output
        or not archive.is_relative_to(output)
    ):
        raise ValueError("Recovery move must stay within the explicit output root")
    if not path.exists():
        return
    destination = archive / path.name
    if destination.exists() or destination.is_relative_to(path):
        raise ValueError("Recovery archive cannot overwrite or recurse")
    files = sorted(path.rglob("*")) if path.is_dir() else [path]
    hashes = {str(p.relative_to(output)): recovery.sha(p) for p in files if p.is_file()}
    archive.mkdir(parents=True, exist_ok=True)
    recovery.atomic_json(
        archive / (path.name + ".preserved.json"),
        {
            "source": str(path),
            "destination": str(destination),
            "reason": reason,
            "hashes": hashes,
            "utc": recovery.utc(),
        },
    )
    path.rename(destination)


def restore_file(source, destination, expected, output, archive):
    if recovery.sha(source) != expected:
        raise ValueError("Recovery snapshot changed: " + str(source))
    if destination.exists() and recovery.sha(destination) != expected:
        preserve(
            destination,
            output,
            archive,
            "Incomplete or damaged output; immutable snapshot retained",
        )
    recovery.atomic_copy(source, destination)


def gbt_config(producer):
    tree = ast.parse(inspect.getsource(producer.train_gbts))
    for statement in tree.body[0].body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "config" for t in statement.targets
        ):
            call = statement.value
            if (
                not isinstance(call, ast.Call)
                or not isinstance(call.func, ast.Name)
                or call.func.id != "dict"
            ):
                break
            return {
                k.arg: producer.SEED
                if isinstance(k.value, ast.Name) and k.value.id == "SEED"
                else ast.literal_eval(k.value)
                for k in call.keywords
            }
    raise ValueError("Frozen GBT configuration cannot be read exactly")


def pending_models(completed):
    return [name for name in recovery.MODELS if name not in completed]


def fit_missing_gbts(producer, x, sample, scales, out, completed, after_model=None):
    config = gbt_config(producer)
    row_scale = sample.ticker.map(scales).to_numpy(float)
    for name in pending_models(completed):
        target = "net_base" if name == "gbt_net" else "dp_advantage"
        model = producer.lgb.LGBMRegressor(**config)
        model.fit(
            x,
            sample[target].to_numpy(float) / row_scale,
            sample_weight=sample.weight.to_numpy(float),
        )
        temporary = out / (name + ".recovery-partial.txt")
        model.booster_.save_model(str(temporary))
        os.replace(temporary, out / (name + ".txt"))
        if after_model is not None:
            after_model(name)
        print(
            json.dumps(
                {
                    "stage": "model_fit",
                    "model": name,
                    "rows": len(sample),
                    "recovery": True,
                }
            ),
            flush=True,
        )
    producer.write_json(out / "gbt_config.json", config)


def latest_valid_epoch(root):
    valid, rejected = [], []
    for path in sorted(root.glob("tcn_epoch*.pt")):
        try:
            meta = recovery.validate_epoch_pair(path)
            valid.append((meta["epoch"], path))
        except (ValueError, OSError, KeyError, RuntimeError) as error:
            rejected.append({"path": str(path), "reason": str(error)})
    return max(valid, default=(0, None)), rejected


def capture_final(output, snapshots):
    import torch

    epoch = output / "tcn_epoch04.pt"
    recovery.validate_epoch_pair(epoch)
    checkpoint = torch.load(epoch, map_location="cpu", weights_only=False)
    final = torch.load(output / "tcn_teacher.pt", map_location="cpu", weights_only=True)
    history = read(output / "neural_training.json")
    if (
        history["epochs"] != checkpoint["history"]
        or final["state_dict"].keys() != checkpoint["model"].keys()
    ):
        raise ValueError("Final TCN differs from completed epoch4")
    if not all(
        torch.equal(v, final["state_dict"][k]) for k, v in checkpoint["model"].items()
    ):
        raise ValueError("Final TCN parameters differ from completed epoch4")
    target = snapshots / "final_models"
    names = ("tcn_teacher.pt", "neural_training.json", "gbt_config.json")
    artifacts = {
        name: recovery.atomic_copy(output / name, target / name) for name in names
    }
    recovery.atomic_json(
        target / "manifest.json",
        {
            "status": "COMPLETE_FINAL_MODEL_SNAPSHOT",
            "artifacts": artifacts,
            "epoch4_sha256": recovery.sha(epoch),
            "environment_sha256": recovery.sha(snapshots / "environment.json"),
            "base_manifest_sha256": recovery.sha(snapshots / "base" / "manifest.json"),
            "utc": recovery.utc(),
        },
    )


def capture_freeze(output, snapshots):
    import train_models as producer

    producer.verify_freeze(output)
    names = (
        "freeze.json",
        "oracle_sources_before_test.json",
        "validation/prediction_hashes.json",
        "validation/summary.json",
    )
    target = snapshots / "frozen_evaluation"
    artifacts = {
        name: recovery.atomic_copy(output / name, target / name) for name in names
    }
    predictions = read(output / "validation" / "prediction_hashes.json")
    for name, digest in predictions.items():
        if recovery.sha(output / "validation" / name) != digest:
            raise ValueError("Validation prediction changed during freeze capture")
    recovery.atomic_json(
        target / "manifest.json",
        {
            "status": "COMPLETE_FROZEN_EVALUATION_SNAPSHOT",
            "artifacts": artifacts,
            "validation_prediction_hashes": predictions,
            "predictions_stored_in": str((output / "validation").resolve()),
            "base_manifest_sha256": recovery.sha(snapshots / "base" / "manifest.json"),
            "utc": recovery.utc(),
        },
    )


def continue_run(args):
    out, snapshots, runtime = (
        args.output.resolve(),
        args.recovery.resolve(),
        args.runtime.resolve(),
    )
    identity = read(snapshots / "environment.json")
    ensure_stopped(identity, out)
    check_failure(runtime, args.reason)
    if fingerprint() != identity["environment"]:
        raise ValueError("Hardware/software differs; exact continuation rejected")
    summary_status = summary_state(out / "summary.json")
    if summary_status == "complete":
        frozen = read(out / "freeze.json")
        for name, digest in frozen["artifacts"].items():
            if recovery.sha(out / name) != digest:
                raise ValueError("Completed run integrity differs; no automatic replay")
        if not all(read(out / "feature_rehash.json").values()):
            raise ValueError("Completed run source check failed; no automatic replay")
        raise ValueError("Completed scientific run must not be replayed")
    for previous in sorted((out / "recovery_attempts").glob("*/failure.json")):
        failure = read(previous)
        if not failure.get("technical_interruption", False):
            raise ValueError("Previous recovery had an unclassified/scientific failure")
    stamp = str(time.time_ns())
    archive = out / "recovery_attempts" / stamp
    archive.mkdir(parents=True, exist_ok=False)
    args.active_recovery_archive = archive
    import psutil

    own_process = psutil.Process()
    recovery.atomic_json(
        archive / "authority.json",
        {
            "reason": args.reason,
            "original_process": identity,
            "controller_sha256": recovery.sha(__file__),
            "utc": recovery.utc(),
            "scientific_plan_changed": False,
            "recovery_process": {
                "pid": own_process.pid,
                "create_time": own_process.create_time(),
                "command": own_process.cmdline(),
            },
        },
    )
    if summary_status == "partial":
        preserve(
            out / "summary.json", out, archive, "Interrupted final summary publication"
        )
    frozen_marker = snapshots / "frozen_evaluation" / "manifest.json"
    if frozen_marker.exists():
        manifest = read(frozen_marker)
        if manifest["status"] != "COMPLETE_FROZEN_EVALUATION_SNAPSHOT" or manifest[
            "base_manifest_sha256"
        ] != recovery.sha(snapshots / "base" / "manifest.json"):
            raise ValueError("Frozen evaluation snapshot binding invalid")
        for name, digest in manifest["artifacts"].items():
            restore_file(
                frozen_marker.parent / name,
                out / name,
                digest,
                out,
                archive / "frozen_authority",
            )
    if guard_freeze_authority(out) == "partial":
        # Re-evaluate validation from fixed models before replacing a partial
        # pre-test freeze. No test value can enter this reconstruction.
        preserve(
            out / "freeze.json",
            out,
            archive,
            "Interrupted pre-test freeze; validation will be repeated",
        )
    base = read(snapshots / "base" / "manifest.json")
    if Path(base["output_root"]).resolve() != out:
        raise ValueError("Recovery base belongs to another output")
    for name, digest in base["artifacts"].items():
        restore_file(snapshots / "base" / name, out / name, digest, out, archive)
        if name.endswith(".py") or name in ("LEARNER_PLAN.md", "PROTOCOL.md"):
            if recovery.sha(Path(__file__).with_name(name)) != digest:
                raise ValueError("Frozen producer dependency changed: " + name)
    import train_models as producer

    audit = producer.require_oracle_pass(args.oracle_audit, args.oracle_root)
    original = read(out / "run_identity.json")
    if original["oracle_audit"] != audit or original["device"] != args.device:
        raise ValueError("Recovery audit/device differs")
    days = producer.discover_days(args.oracle_root, args.feature_root)
    if [d.key for d in days] != original["days"]:
        raise ValueError("Recovery day universe differs")
    producer.verify_full_coverage(days, out)
    seal = producer.SourceSeal(args.oracle_root)
    store = producer.FeatureStore(days, seal=seal)
    for day in days:
        if day.date < "20250101":
            for name in ("actions.parquet", "labels.parquet", "advantages.parquet"):
                seal.check(day, name)
    sample = producer.pd.read_parquet(out / "training_sample.parquet")
    normalizers = read(out / "normalizers.json")
    scales, stats = normalizers["risk_scales_usd"], normalizers["features"]
    completed = []
    for name in recovery.MODELS:
        marker = snapshots / name / "manifest.json"
        if not marker.exists():
            log_roots = [runtime] + [
                p.parent
                for p in sorted(
                    (out / "recovery_attempts").glob("*/model_completion/stdout.log")
                )
            ]
            for log_root in log_roots:
                if (
                    recovery.completed_model_marker(log_root / "stdout.log", name)[0]
                    is not None
                ):
                    recovery.capture_gbt(out, log_root, snapshots, name)
                    break
        if marker.exists():
            manifest = read(marker)
            if manifest["status"] != "COMPLETE_GBT_SNAPSHOT" or manifest[
                "base_manifest_sha256"
            ] != recovery.sha(snapshots / "base" / "manifest.json"):
                raise ValueError("GBT snapshot binding invalid")
            restore_file(
                marker.parent / "model.txt",
                out / (name + ".txt"),
                manifest["model_sha256"],
                out,
                archive,
            )
            model = producer.lgb.Booster(model_file=str(out / (name + ".txt")))
            if (
                model.num_trees() != 200
                or model.num_feature() != normalizers["gbt_columns"]
            ):
                raise ValueError("GBT snapshot structure invalid")
            completed.append(name)
        elif (out / (name + ".txt")).exists():
            preserve(
                out / (name + ".txt"),
                out,
                archive,
                "No complete verified model snapshot",
            )
    x = producer.np.load(out / "train_x.npy", mmap_mode="r")

    def snapshot_new_model(name):
        recovery_runtime = archive / "model_completion"
        recovery_runtime.mkdir(exist_ok=True)
        with (recovery_runtime / "stdout.log").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps({"stage": "model_fit", "model": name, "rows": len(sample)})
                + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())
        recovery.capture_gbt(out, recovery_runtime, snapshots, name)

    fit_missing_gbts(producer, x, sample, scales, out, completed, snapshot_new_model)
    del x
    for marker in sorted(snapshots.glob("tcn_epoch*/manifest.json")):
        manifest = read(marker)
        if manifest["status"] != "COMPLETE_EPOCH_SNAPSHOT" or manifest[
            "base_manifest_sha256"
        ] != recovery.sha(snapshots / "base" / "manifest.json"):
            raise ValueError("Epoch snapshot binding invalid")
        for name, digest in manifest["artifacts"].items():
            restore_file(marker.parent / name, out / name, digest, out, archive)
    (epoch, resume), rejected = latest_valid_epoch(out)
    if resume is not None:
        store.hashes.update(read(resume.with_suffix(".json"))["binding"]["files"])
    final_complete = False
    final_marker = snapshots / "final_models" / "manifest.json"
    if final_marker.exists():
        manifest = read(final_marker)
        if (
            manifest["status"] != "COMPLETE_FINAL_MODEL_SNAPSHOT"
            or manifest["base_manifest_sha256"]
            != recovery.sha(snapshots / "base" / "manifest.json")
            or manifest["environment_sha256"]
            != recovery.sha(snapshots / "environment.json")
            or epoch != 4
            or manifest["epoch4_sha256"] != recovery.sha(resume)
        ):
            raise ValueError("Final model snapshot binding invalid")
        for name, digest in manifest["artifacts"].items():
            restore_file(final_marker.parent / name, out / name, digest, out, archive)
        final_complete = True
    recovery.atomic_json(
        archive / "stage_plan.json",
        {
            "reused_gbts": completed,
            "fitted_gbts": pending_models(completed),
            "resume_epoch": epoch,
            "rejected_pairs": rejected,
            "partial_epoch_replayed": epoch < producer.EPOCHS,
        },
    )
    for path in sorted(out.glob("tcn_epoch*")):
        if (
            path.suffix in (".pt", ".json")
            and resume is not None
            and path.stem == resume.stem
        ):
            continue
        if (
            path.suffix in (".pt", ".json")
            and path.stem.removeprefix("tcn_epoch").isdigit()
            and int(path.stem.removeprefix("tcn_epoch")) <= epoch
        ):
            continue
        preserve(path, out, archive, "Uncommitted or invalid epoch output")
    # Export from the last verified epoch even when epoch=4: zero optimizer steps.
    # A partially written final model is never mistaken for a complete model.
    if (out / "freeze.json").exists():
        # A published freeze binds the final serialized bytes. Do not re-export
        # them: equivalent parameters need not serialize to identical bytes.
        producer.verify_freeze(out)
    elif not final_complete:
        for name in ("tcn_teacher.pt", "neural_training.json"):
            preserve(
                out / name, out, archive, "Re-export final model from verified epoch"
            )
        if resume is None:
            for key in sorted(sample.day_key.unique()):
                store.get(key)
        producer.train_tcn(sample, store, scales, stats, out, args.device, resume)
    models = producer.load_predictors(out, args.device)
    engine = producer.import_sibling("level_engine")
    if (out / "freeze.json").exists():
        frozen = producer.verify_freeze(out)
        for name, digest in read(out / "validation" / "prediction_hashes.json").items():
            if recovery.sha(out / "validation" / name) != digest:
                raise ValueError("Frozen validation prediction changed")
        selection, choices = frozen["selected_policy"], frozen["validation_choices"]
        store.hashes.update(frozen["feature_sources"])
        seal.hashes.update(read(out / "oracle_sources_before_test.json"))
    else:
        preserve(
            out / "validation",
            out,
            archive,
            "Replay incomplete validation with same models",
        )
        validation = producer.evaluate_period(
            days, store, models, scales, stats, out, "validation", args.device, engine
        )
        selection, choices = producer.select_policy(validation, scales)
        seal.recheck()
        producer.write_json(out / "oracle_sources_before_test.json", seal.hashes)
        producer.freeze(out, selection, choices, store, audit)
    producer.verify_freeze(out)
    preserve(out / "test", out, archive, "Replay incomplete test with frozen policy")
    test = producer.evaluate_period(
        days, store, models, scales, stats, out, "test", args.device, engine
    )
    producer.verify_freeze(out)
    seal.recheck()
    producer.write_json(out / "oracle_sources_final.json", seal.hashes)
    hashes = {
        path: recovery.sha(path) == digest for path, digest in store.hashes.items()
    }
    producer.write_json(out / "feature_rehash.json", hashes)
    if not all(hashes.values()):
        raise ValueError("Feature source changed")
    result = {
        "status": "COMPLETED_CAUSAL_LEARNER_DEVELOPMENT",
        "selected_policy": selection,
        "selected_test": None
        if selection["policy"] == "CASH"
        else test[selection["policy"]],
        "selected_cash_net_usd": 0 if selection["policy"] == "CASH" else None,
        "provisional_gate": producer.economic_gate(selection, test),
        "validation_choices": choices,
        "risk_scales_usd": scales,
        "recovery_attempt": str(archive),
        "test_candidate_results_are_diagnostic_not_selection": True,
        "drawdown_convention": "realized trade net in exit-time order; not intratrade mark-to-market",
        "untouched_outer": False,
        "technical_ready": False,
        "promotion_approved": False,
    }
    producer.write_json(out / "summary.json", result)
    recovery.atomic_json(
        archive / "completion.json",
        {
            "status": "COMPLETE_RECOVERY",
            "summary_sha256": recovery.sha(out / "summary.json"),
            "utc": recovery.utc(),
        },
    )


def main():
    for name in (
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "OMP_NUM_THREADS",
    ):
        os.environ[name] = "1"
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--recovery", type=Path, required=True)
    parser.add_argument("--capture-environment-only", action="store_true")
    parser.add_argument("--capture-final-only", action="store_true")
    parser.add_argument("--capture-freeze-only", action="store_true")
    parser.add_argument(
        "--reason",
        choices=("process_interruption", "resource_exhaustion", "io_interruption"),
    )
    parser.add_argument("--oracle-root", type=Path)
    parser.add_argument("--feature-root", type=Path)
    parser.add_argument("--oracle-audit", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    args = parser.parse_args()
    if args.capture_freeze_only:
        capture_freeze(args.output, args.recovery)
    elif args.capture_final_only:
        capture_final(args.output, args.recovery)
    elif args.capture_environment_only:
        capture_environment(args.runtime, args.recovery / "environment.json")
    else:
        if any(
            getattr(args, name) is None
            for name in ("reason", "oracle_root", "feature_root", "oracle_audit")
        ):
            parser.error(
                "Continuation needs an explicit technical reason and bound roots/audit"
            )
        try:
            with output_lock(args.output.resolve()):
                continue_run(args)
        except BaseException as error:
            archive = getattr(args, "active_recovery_archive", None)
            if archive is not None:
                recovery.atomic_json(
                    archive / "failure.json",
                    {
                        "exception": type(error).__name__,
                        "message": str(error),
                        "technical_interruption": isinstance(
                            error, (MemoryError, OSError, KeyboardInterrupt)
                        )
                        or "out of memory" in str(error).lower(),
                        "utc": recovery.utc(),
                    },
                )
            raise


if __name__ == "__main__":
    main()
