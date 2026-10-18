"""FLAGS64 control versus row-mixed TCN; isolated, sealed economic evaluation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil

import numpy as np
import torch

import evaluate_tcn_flags_compat as compat
import run_tcn_flags as flags

COMPAT_SHA = "97836bb5a9a0364cf24888f55db0c1784268ed64575b71c4c76e1c03141d9aaf"
TRAIN_SHA = "5c4adfe01e2a51f3eb0f16c96479edb326e2f06ea1f66b3721313ccaa9ab7ab2"
CONTROL_AUDIT_SHA = "9911ed97caf16f18802366dd14cb30ddeef68bdbfe05a28f3dc6711dccadb53f"


def stable_json(path, value):
    if path.exists():
        if flags.read_json(path) != value:
            raise ValueError(f"Changed sealed metadata: {path}")
    else:
        flags.preserve_incomplete(
            path.parent, [path.with_suffix(path.suffix + ".partial")]
        )
        flags.atomic_json(path, value)


def copy_exact(source, destination):
    if destination.exists():
        if flags.sha(source) != flags.sha(destination):
            raise ValueError(f"Snapshot differs: {destination}")
    else:
        temporary = destination.with_name(destination.name + ".partial")
        flags.preserve_incomplete(destination.parent, [temporary])
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)


def verify_control(control, audit_path):
    if flags.sha(audit_path) != CONTROL_AUDIT_SHA:
        raise ValueError("Unexpected FLAGS64 economic audit")
    audit = flags.read_json(audit_path)
    if audit["status"] != "PASS_INDEPENDENT_TCN_FLAGS_ECONOMIC_AUDIT":
        raise ValueError("FLAGS64 control audit did not pass")
    bound = audit["binding"]
    if Path(bound["root"]).resolve() != control.resolve():
        raise ValueError("Wrong FLAGS64 control root")
    for name, key in (
        ("summary.json", "summary_sha256"),
        ("completion.json", "completion_sha256"),
        ("freeze.json", "freeze_sha256"),
        ("validation/prediction_manifest.json", "validation_manifest_sha256"),
        ("test/prediction_manifest.json", "test_manifest_sha256"),
        ("evaluation_runtime_completion.json", "compatibility_completion_sha256"),
    ):
        if flags.sha(control / name) != bound[key]:
            raise ValueError(f"Control authority changed: {name}")
    flags.verify_files(flags.read_json(control / "completion.json")["files"])
    return audit


def adapt_control_period(control, output, period, expected_names):
    """Transparent key adapter, not a model or recomputed control score."""
    if period not in ("validation", "test"):
        raise ValueError("Unknown period")
    if period == "test" and not (output / "freeze.json").exists():
        raise ValueError("Test control cannot be opened before validation freeze")
    if period == "test":
        flags.verify_files(flags.read_json(output / "freeze.json")["files"])
    source_dir = control / period
    manifest_path = source_dir / "prediction_manifest.json"
    manifest = flags.read_json(manifest_path)
    if set(manifest) != {Path(n).with_suffix(".json").name for n in expected_names}:
        raise ValueError("FLAGS64 control universe mismatch")
    target = output / "control_adapter" / period
    target.mkdir(parents=True, exist_ok=True)
    hashes, lineage = {}, {}
    source_files = {str(manifest_path): flags.sha(manifest_path)}
    for name in sorted(expected_names):
        source = source_dir / name
        sidecar = source.with_suffix(".json")
        if flags.sha(sidecar) != manifest[sidecar.name]:
            raise ValueError("Control sidecar changed")
        record = flags.read_json(sidecar)
        flags.verify_files(record["feature_files"])
        flags.verify_files(record["oracle_files"])
        sealed = record["files"]
        if sealed.get(str(source)) != flags.sha(source):
            raise ValueError("Control NPZ is not bound by its audited sidecar")
        source_files.update(record["feature_files"])
        source_files.update(record["oracle_files"])
        source_files.update(
            {str(source): flags.sha(source), str(sidecar): flags.sha(sidecar)}
        )
        with np.load(source, allow_pickle=False) as data:
            ids, scores = data["action_ids"].copy(), data["variant"].copy()
        if ids.ndim != 1 or scores.shape != ids.shape or not np.isfinite(scores).all():
            raise ValueError("Invalid FLAGS64 control scores")
        destination = target / name
        if destination.exists():
            with np.load(destination, allow_pickle=False) as data:
                if set(data.files) != {"action_ids", "tcn_teacher"}:
                    raise ValueError("Unexpected control adapter schema")
                if not np.array_equal(data["action_ids"], ids) or not np.array_equal(
                    data["tcn_teacher"], scores
                ):
                    raise ValueError("Control adapter differs from FLAGS64")
        else:
            temporary = destination.with_suffix(".partial.npz")
            flags.preserve_incomplete(output, [temporary])
            np.savez_compressed(temporary, action_ids=ids, tcn_teacher=scores)
            os.replace(temporary, destination)
        hashes[name] = flags.sha(destination)
        lineage[name] = {
            "source": str(source),
            "source_sha256": flags.sha(source),
            "sidecar": str(sidecar),
            "sidecar_sha256": flags.sha(sidecar),
            "adapter_sha256": hashes[name],
            "mapping": "FLAGS64.variant -> adapter.tcn_teacher -> evaluation.control",
        }
    stable_json(target / "prediction_hashes.json", hashes)
    stable_json(
        target / "adapter_lineage.json",
        {
            "manifest": str(manifest_path),
            "manifest_sha256": flags.sha(manifest_path),
            "days": lineage,
            "source_files": source_files,
        },
    )
    return target.parent


def bind(args):
    output, training_root, control = args.output, args.training_root, args.flags_root
    output.mkdir(parents=True, exist_ok=True)
    if flags.sha(flags.__file__) != compat.EXPECTED_RUNNER_SHA:
        raise ValueError("Frozen FLAGS runner changed")
    if flags.sha(compat.__file__) != COMPAT_SHA:
        raise ValueError("Frozen compatible inference changed")
    verify_control(control, args.control_audit)
    training = flags.read_json(training_root / "training_complete.json")
    flags.verify_files(training["binding"]["files"])
    if training["binding"]["variant"] != "row_mixed_original_batch_sizes":
        raise ValueError("Wrong training experiment")
    if flags.sha(training_root / "run_tcn_row_mixed.executed.py") != TRAIN_SHA:
        raise ValueError("Unexpected row-mixed training producer")
    if flags.sha(training_root / "tcn_variant.pt") != training["model_sha256"]:
        raise ValueError("Row-mixed final model changed")
    control_identity = flags.read_json(control / "identity.json")
    flags.verify_files(control_identity["files"])
    cache = flags.read_json(training_root / "cache_complete.json")
    if Path(cache["flags_root"]).resolve() != control.resolve():
        raise ValueError("Training normalizers belong to a different FLAGS64 control")
    for name in ("normalizers.json", "feature_schema.json", "training_sample.parquet"):
        if cache["files"].get(str(control / name)) != flags.sha(control / name):
            raise ValueError("Training/control feature preparation differs")
    if not (output / "identity.json").exists() and any(
        (output / name).exists() for name in ("validation", "test", "freeze.json")
    ):
        raise ValueError("Economic outputs exist without prior binding")
    copies = {
        Path(__file__).resolve(): "evaluate_tcn_row_mixed.executed.py",
        Path(__file__).with_name(
            "TCN_ROW_MIXED_EVALUATION_SPEC.md"
        ): "TCN_ROW_MIXED_EVALUATION_SPEC.md",
        training_root / "tcn_variant.pt": "tcn_variant.pt",
        training_root / "training_complete.json": "training_complete.json",
        control / "normalizers.json": "normalizers.json",
        control / "feature_schema.json": "feature_schema.json",
        control / "expected_full_calendar.csv": "expected_full_calendar.csv",
    }
    for source, name in copies.items():
        copy_exact(source, output / name)
    sources = [
        *copies,
        *(output / name for name in copies.values()),
        Path(flags.__file__),
        Path(compat.__file__),
        args.control_audit,
        control / "identity.json",
        control / "completion.json",
        control / "freeze.json",
        control / "validation/prediction_manifest.json",
        control / "test/prediction_manifest.json",
        training_root / "cache_complete.json",
        training_root / "run_tcn_row_mixed.executed.py",
    ]
    files = {str(path.resolve()): flags.sha(path) for path in sources}
    identity = {
        "files": files,
        "training_root": str(training_root),
        "control_root": str(control),
        "learner_root": control_identity["learner_root"],
        "engine_root": control_identity["engine_root"],
        "feature_root": control_identity["feature_root"],
        "control_score_key": "FLAGS64.variant",
        "variant": "row_mixed_original_batch_sizes",
    }
    stable_json(output / "identity.json", identity)
    return identity, training


def finish(output, identity, selection, test, original, store, seal):
    selected = selection["selected_policy"]
    gate = {"passes": False, "reason": "NO_VALIDATION_DAILY_COMPLIANT_POLICY"}
    if selected is not None:
        gate = original.economic_gate({"policy": selected}, test)
        gate["daily_gate"] = test[selected]["daily_gate"]
        gate["passes"] = gate["passes"] and gate["daily_gate"]["passes"]
    paired = {
        str(t): {
            f"{cost}_delta_usd": test[f"variant__{t}"]["pooled"][f"{cost}_net_usd"]
            - test[f"control__{t}"]["pooled"][f"{cost}_net_usd"]
            for cost in ("base", "adverse")
        }
        for t in (0, 5, 10)
    }
    flags.verify_files(identity["files"])
    flags.verify_files(flags.read_json(output / "freeze.json")["files"])
    flags.verify_files(store.hashes)
    seal.recheck()
    control_sources = {}
    for period in ("validation", "test"):
        path = output / "control_adapter" / period / "adapter_lineage.json"
        if path.exists():
            control_sources.update(flags.read_json(path)["source_files"])
    flags.verify_files(control_sources)
    stable_json(
        output / "summary.json",
        {
            "status": "COMPLETE",
            "selection": selection,
            "selected_test": test[selected] if selected else None,
            "gate": gate,
            "paired_same_threshold_test": paired,
            "test": test,
            "development_seen": True,
            "promotion_approved": False,
            "control": "FLAGS64",
            "variant": "row_mixed",
            "freeze_sha256": flags.sha(output / "freeze.json"),
        },
    )
    flags.preserve_incomplete(output, [output / "completion.json.partial"])
    complete_files = {
        str(path): flags.sha(path)
        for path in output.rglob("*")
        if path.is_file()
        and path.name not in ("completion.json", ".output.lock")
        and "recovery" not in path.relative_to(output).parts
    }
    complete_files.update(control_sources)
    stable_json(
        output / "completion.json", {"status": "COMPLETE", "files": complete_files}
    )


def evaluate(args):
    output = args.output
    identity, training = bind(args)
    if (output / "completion.json").exists():
        flags.verify_files(flags.read_json(output / "completion.json")["files"])
        return
    flags.require_prior_freeze(output)
    if (output / "control_adapter/test").exists() and not (
        output / "freeze.json"
    ).exists():
        raise ValueError("Test adapter exists without prior freeze")
    original = flags.load_original(Path(identity["learner_root"]))
    days = original.discover_days(
        Path(identity["engine_root"]), Path(identity["feature_root"])
    )
    seal = original.SourceSeal(Path(identity["engine_root"]))
    store = flags.CheckedStore(
        original.FeatureStore(days, capacity=2, seal=seal),
        flags.read_json(output / "feature_schema.json"),
    )
    normalizers = flags.read_json(output / "normalizers.json")
    stats, scales = normalizers["features"], normalizers["risk_scales_usd"]
    device = training["binding"]["device"]
    state = torch.load(output / "tcn_variant.pt", map_location="cpu", weights_only=True)
    if state["epoch"] != 4:
        raise ValueError("Only fixed fourth epoch may be evaluated")
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    if device.startswith("cuda"):
        torch.backends.cudnn.benchmark = False
    model = original.LevelTCN(**state["config"]).to(device)
    model.load_state_dict(state["state_dict"])
    flags.inference = compat.inference_exact
    selection = None
    for period, lower, upper in (
        ("validation", "20250101", "20260101"),
        ("test", "20260101", "20260701"),
    ):
        expected = {f"{d.ticker}_{d.date}.npz" for d in days if lower <= d.date < upper}
        adapter = adapt_control_period(args.flags_root, output, period, expected)
        summary = flags.evaluate_period(
            original, days, store, model, scales, stats, output, adapter, period, device
        )
        if period == "validation":
            selection = flags.select_validation(summary, scales)
            path = output / "freeze.json"
            if path.exists():
                if flags.read_json(path)["selection"] != selection:
                    raise ValueError("Frozen selection changed")
                flags.verify_files(flags.read_json(path)["files"])
            else:
                flags.preserve_incomplete(output, [output / "freeze.json.partial"])
                files = {
                    str(p): flags.sha(p)
                    for p in output.rglob("*")
                    if p.is_file()
                    and p.name != ".output.lock"
                    and "recovery" not in p.relative_to(output).parts
                }
                files.update(identity["files"])
                files.update(store.hashes)
                files.update(seal.hashes)
                files.update(
                    flags.read_json(adapter / "validation/adapter_lineage.json")[
                        "source_files"
                    ]
                )
                flags.atomic_json(
                    path,
                    {
                        "selection": selection,
                        "files": files,
                        "test_evaluated": False,
                        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
                    },
                )
        else:
            finish(output, identity, selection, summary, original, store, seal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-root", type=Path, required=True)
    parser.add_argument("--flags-root", type=Path, required=True)
    parser.add_argument("--control-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for name in ("training_root", "flags_root", "control_audit", "output"):
        setattr(args, name, getattr(args, name).resolve())
    with flags.output_lock(args.output):
        evaluate(args)


if __name__ == "__main__":
    main()
