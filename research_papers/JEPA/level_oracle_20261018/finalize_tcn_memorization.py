"""Publish saved diagnostic outputs after NumPy scalar JSON failure; no fit."""

import argparse
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import torch

import diagnose_tcn_memorization as diagnostic
import run_tcn_flags as flags


def finish(out):
    if (out / "completion.json").exists() or (out / "summary.json").exists():
        raise FileExistsError("Already finalized")
    freeze = flags.read_json(out / "freeze_before_updates.json")
    flags.verify_files(freeze["files"])
    saved = torch.load(out / "final_model.pt", map_location="cpu", weights_only=False)
    if saved["update"] != 500 or not saved["optimizer"]["state"]:
        raise ValueError("500-update optimizer/model not available")
    metrics = pd.read_parquet(out / "metrics.parquet")
    if metrics["update"].tolist() != list(range(0, 501, 50)):
        raise ValueError("Incomplete diagnostic metrics")
    norms = np.load(out / "gradient_norms.npy", allow_pickle=False)
    if norms.shape != (500,) or not np.isfinite(norms).all():
        raise ValueError("Incomplete gradient norms")
    selected = pd.read_parquet(out / "selected_train_rows.parquet")
    duplicates = diagnostic.duplicate_diagnostics(
        selected.input_sha256,
        selected.normalized_target,
        selected.state_optimal_action,
        selected.weight.astype(np.float32),
    )
    duplicates = {
        k: v.item() if isinstance(v, np.generic) else v for k, v in duplicates.items()
    }
    files = {str(p.resolve()): flags.sha(p) for p in out.iterdir() if p.is_file()}
    shutil.copy2(__file__, out / "finalize_tcn_memorization.executed.py")
    flags.atomic_json(
        out / "publication_recovery.json",
        dict(
            reason="500 updates completed; summary JSON rejected numpy.float32 floor scalar",
            fit_repeated=False,
            inference_repeated=False,
            updates_performed=0,
            original_outputs=files,
            finalizer_sha256=flags.sha(__file__),
        ),
    )
    flags.atomic_json(
        out / "summary.json",
        dict(
            status="COMPLETE_TRAIN_CAPACITY_DIAGNOSTIC",
            selected_rows=128,
            updates=500,
            elapsed_seconds=None,
            elapsed_unavailable_reason="not persisted before JSON failure",
            duplicates=duplicates,
            metrics=metrics.to_dict("records"),
            clipped_fraction=float(np.mean(norms > 1)),
            gradient_quantiles=np.quantile(norms, [0, 0.5, 0.9, 0.99, 1]).tolist(),
            validation_or_test_read=False,
            policy_or_epoch_selection=False,
            publication_recovery="publication_recovery.json",
        ),
    )
    flags.verify_files(freeze["files"])
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
    parser.add_argument("--output", required=True, type=Path)
    finish(parser.parse_args().output)
