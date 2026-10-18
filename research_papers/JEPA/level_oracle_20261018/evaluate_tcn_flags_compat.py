"""Technical inference parity wrapper; training artifacts remain immutable."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
from datetime import datetime, timezone

import numpy as np
import torch

EXPECTED_RUNNER_SHA = "a76a3ee78b74568a77ad06bc85c3092dee606648c6b6ed54ad38818496ae06e5"
EXPECTED_ORIGINAL_SHA = (
    "a5192737abd1c0b3e4a6a6cd391117d97a014c06b6cd528201ba1f5df0ef6808"
)


def inference_exact(original, model, store, day, actions, stats, scale, device):
    """Exact neural branch of original predict_day, excluding unrelated GBT work."""
    scores = np.empty(len(actions), np.float64)
    if len(actions):
        pack, all_ai, all_si = store.rows(day.key, actions.action_id)
        unique, inverse = np.unique(all_si, return_inverse=True)
        with torch.inference_mode():
            neural_states = original.encode_unique_states(
                model, pack, unique, stats, device
            )
    for start in range(0, len(actions), original.BATCH):
        subset = actions.iloc[start : start + original.BATCH]
        pack, ai, si = store.rows(day.key, subset.action_id)
        with torch.inference_mode():
            action = torch.as_tensor(
                original.normalized(pack["action_features"][ai], stats["action"]),
                device=device,
            )
            prediction, _ = model.score_actions(
                neural_states[
                    torch.as_tensor(inverse[start : start + len(subset)], device=device)
                ],
                action,
            )
        scores[start : start + len(subset)] = prediction.cpu().numpy() * scale
    if not np.isfinite(scores).all():
        raise FloatingPointError("Nonfinite original-compatible causal scores")
    return scores


def load_runner(out):
    path = out / "run_tcn_flags.executed.py"
    spec = importlib.util.spec_from_file_location(
        "flags_frozen_evaluation_runtime", path
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if module.sha(path) != EXPECTED_RUNNER_SHA:
        raise ValueError("Unexpected frozen training runner")
    return module


def bind_runtime(runner, out):
    identity = runner.read_json(out / "identity.json")
    training = runner.read_json(out / "training_complete.json")
    runner.verify_files(identity["files"])
    runner.verify_files(training["binding"]["files"])
    model = out / "tcn_variant.pt"
    if runner.sha(model) != training["model_sha256"]:
        raise ValueError("Final fourth-epoch model hash mismatch")
    learner = Path(identity["learner_root"])
    if runner.sha(learner / "train_models.py") != EXPECTED_ORIGINAL_SHA:
        raise ValueError("Unexpected frozen original trainer")
    source = Path(__file__).resolve()
    note = source.with_name("TCN_FLAGS_EVALUATION_COMPATIBILITY.md")
    copies = {
        source: out / "evaluate_tcn_flags_compat.executed.py",
        note: out / note.name,
    }
    binding_path = out / "evaluation_runtime.json"
    if not binding_path.exists() and any(
        (out / name).exists() for name in ("validation", "test", "freeze.json")
    ):
        raise ValueError("Predictions/freeze exist without prior compatibility binding")
    for src, dst in copies.items():
        if dst.exists():
            if runner.sha(src) != runner.sha(dst):
                raise ValueError("Compatibility snapshot changed")
        else:
            shutil.copyfile(src, dst)
    sources = [
        source,
        note,
        *copies.values(),
        model,
        out / "training_complete.json",
        out / "identity.json",
        out / "normalizers.json",
        out / "feature_schema.json",
        out / "run_tcn_flags.executed.py",
        learner / "train_models.py",
    ]
    files = {str(p.resolve()): runner.sha(p) for p in sources}
    if binding_path.exists():
        previous = runner.read_json(binding_path)
        if previous["files"] != files:
            raise ValueError("Compatibility runtime binding differs")
        runner.verify_files(previous["files"])
    else:
        runner.atomic_json(
            binding_path,
            {
                "status": "BOUND_BEFORE_FIRST_VALIDATION_PREDICTION",
                "files": files,
                "training_unchanged": True,
                "operation": "original unique/inverse and float32 multiply then float64 assignment",
                "bound_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
    return identity, training, files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/GexResearchArtifacts/level_oracle_20261018/tcn_flags_v1"),
    )
    args = parser.parse_args(argv)
    out = args.output.resolve()
    runner = load_runner(out)
    with runner.output_lock(out):
        identity, training, files = bind_runtime(runner, out)
        runner.inference = inference_exact
        if not (out / "completion.json").exists():
            runner.execute(
                SimpleNamespace(
                    stage="evaluate",
                    output=out,
                    learner_root=Path(identity["learner_root"]),
                    engine_root=Path(identity["engine_root"]),
                    feature_root=Path(identity["feature_root"]),
                    device=training["binding"]["device"],
                    resume=True,
                )
            )
        finalize_runtime(runner, out, files)


def finalize_runtime(runner, out, files):
    """Recover an interrupted final certificate without replaying completed evaluation."""
    runner.verify_files(files)
    frozen = runner.read_json(out / "freeze.json")
    runner.verify_files(frozen["files"])
    if frozen["files"].get(str(out / "evaluation_runtime.json")) != runner.sha(
        out / "evaluation_runtime.json"
    ):
        raise ValueError("Economic freeze failed to bind compatibility runtime")
    completed = runner.read_json(out / "completion.json")
    if completed["status"] != "COMPLETE":
        raise ValueError("Economic producer did not complete")
    runner.verify_files(completed["files"])
    certificate = {
        "status": "COMPLETE",
        "runtime_sha256": runner.sha(out / "evaluation_runtime.json"),
        "economic_completion_sha256": runner.sha(out / "completion.json"),
        "summary_sha256": runner.sha(out / "summary.json"),
        "files": files,
    }
    path = out / "evaluation_runtime_completion.json"
    if path.exists():
        previous = runner.read_json(path)
        if any(previous.get(key) != value for key, value in certificate.items()):
            raise ValueError("Completed runtime certificate differs")
    else:
        runner.preserve_incomplete(
            out, list(out.glob("evaluation_runtime_completion.json.partial"))
        )
        runner.atomic_json(
            path,
            {**certificate, "finished_at_utc": datetime.now(timezone.utc).isoformat()},
        )


if __name__ == "__main__":
    main()
