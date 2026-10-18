"""Read-only TRAIN optimization diagnostic; no fits, GPU, validation or test reads."""

# ruff: noqa: E402 -- thread limits must precede numerical imports.
import os

for _key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_key] = "1"

import importlib.util
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import torch


ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018")


def weighted_quantiles(values, weights, probabilities):
    order = np.argsort(values, kind="stable")
    return np.interp(
        probabilities, np.cumsum(weights[order]) / weights.sum(), values[order]
    ).tolist()


def target_summary(frame, scales):
    w = frame.weight.to_numpy(float)
    y = frame.net_base.to_numpy(float) / frame.ticker.map(scales).to_numpy(float)
    teacher = frame.state_optimal_action.to_numpy(float)
    mean = np.average(y, weights=w)
    p = np.average(teacher, weights=w)
    entropy = -(p * np.log(p) + (1 - p) * np.log(1 - p)) if 0 < p < 1 else 0.0
    residual = w * (y - mean) ** 2
    tail = np.argsort(np.abs(y - mean))
    return dict(
        rows=len(frame),
        weight=float(w.sum()),
        mean_target=float(mean),
        target_std=float(np.sqrt(residual.sum() / w.sum())),
        positive_net_share=float(np.average(y > 0, weights=w)),
        zero_net_share=float(np.average(y == 0, weights=w)),
        teacher_raw_share=float(teacher.mean()),
        teacher_weighted_share=float(p),
        trajectory_raw_share=float(frame.teacher_selected.mean()),
        trajectory_weighted_share=float(np.average(frame.teacher_selected, weights=w)),
        target_quantiles=weighted_quantiles(
            y, w, [0, 0.001, 0.01, 0.5, 0.99, 0.999, 1]
        ),
        zero_regression_sum=float(np.dot(w, y * y) / 1024),
        constant_regression_sum=float(residual.sum() / 1024),
        constant_bce_sum=float(w.sum() * entropy / 1024),
        constant_combined_sum=float((residual.sum() + 0.1 * w.sum() * entropy) / 1024),
        largest_one_percent_rows_sse_share=float(
            residual[tail[-max(1, len(y) // 100) :]].sum() / residual.sum()
        ),
        status_counts=frame.status.value_counts().to_dict(),
    )


def main():
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    learner = ROOT / "learners_v1"
    out = ROOT / "tcn_optimization_diagnostic_v2"
    out.mkdir(exist_ok=False)
    shutil.copy2(__file__, out / Path(__file__).name)
    source = learner / "train_models.py"
    spec = importlib.util.spec_from_file_location("frozen_tcn_training", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    sample = pd.read_parquet(learner / "training_sample.parquet")
    assert sample.date.astype(str).max() < "20250101"
    normalizers = json.loads((learner / "normalizers.json").read_text())
    scales, stats = normalizers["risk_scales_usd"], normalizers["features"]
    manifest = json.loads((learner / "sampling_manifest.json").read_text())
    assert module.sha(learner / "training_sample.parquet") == manifest["sample_sha256"]
    names = [
        "train_models.py",
        "training_sample.parquet",
        "sampling_manifest.json",
        "normalizers.json",
        "neural_training.json",
        "tcn_teacher.pt",
        *[f"tcn_epoch{i:02}.pt" for i in range(1, 5)],
    ]
    hashes = {name: module.sha(learner / name) for name in names}
    result = dict(
        status="RUNNING_TRAIN_ONLY",
        diagnostic_sha256=module.sha(__file__),
        sources=hashes,
        device="cpu",
        threads=4,
        models_changed=False,
        validation_or_test_read=False,
        population=manifest["populations"],
        sampled=manifest["selected"],
        pooled=target_summary(sample, scales),
        per_ticker={k: target_summary(v, scales) for k, v in sample.groupby("ticker")},
        weights={
            str(k): dict(rows=len(v), unique_weights=v.weight.unique().tolist())
            for k, v in sample.groupby("stratum")
        },
    )
    groups = sample.groupby("day_key", sort=True)
    result["daily_batch"] = dict(
        days=len(groups),
        rows_quantiles=groups.size().quantile([0, 0.1, 0.5, 0.9, 1]).to_dict(),
        weight_sum_over_1024_quantiles=(groups.weight.sum() / 1024)
        .quantile([0, 0.1, 0.5, 0.9, 1])
        .to_dict(),
        updates_per_epoch=int(np.ceil(groups.size() / 1024).sum()),
    )
    result["online_training_history"] = json.loads(
        (learner / "neural_training.json").read_text()
    )["epochs"]
    result["checkpoint_steps"] = {}
    for epoch in range(1, 5):
        name = f"tcn_epoch{epoch:02}.pt"
        meta = json.loads((learner / Path(name).with_suffix(".json")).read_text())
        assert hashes[name] == meta["sha256"]
        checkpoint = torch.load(learner / name, map_location="cpu", weights_only=False)
        steps = sorted(
            {int(v["step"].item()) for v in checkpoint["optimizer"]["state"].values()}
        )
        result["checkpoint_steps"][str(epoch)] = steps
        del checkpoint
    (out / "pre_inference.json").write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            dict(
                stage="train_baseline",
                pooled=result["pooled"],
                batches=result["daily_batch"],
            )
        ),
        flush=True,
    )
    days = [
        SimpleNamespace(
            key=key,
            features=ROOT / "features_v1" / key / "features.npz",
            oracle=ROOT / "engine_v1" / key,
        )
        for key in groups.groups
    ]
    store = module.FeatureStore(days, capacity=1)
    final = torch.load(
        learner / "tcn_teacher.pt", map_location="cpu", weights_only=True
    )
    model = module.LevelTCN(**final["config"])
    model.load_state_dict(final["state_dict"])
    model.eval()
    result["parameters"] = sum(p.numel() for p in model.parameters())
    predictions = np.empty(len(sample), np.float64)
    logits = np.empty(len(sample), np.float64)
    input_stats = {}
    with torch.inference_mode():
        for day_number, (key, rows) in enumerate(groups, 1):
            pack, ai, si = store.rows(key, rows.action_id)
            predicted, logit = module.neural_actions(model, pack, ai, si, stats, "cpu")
            predictions[rows.sample_i] = predicted.numpy()
            logits[rows.sample_i] = logit.numpy()
            # Count supplied mask availability and finite standardized numeric values,
            # once per sampled action (descriptive unweighted counts, not a refit).
            arrays = {
                "base": pack["base"][si],
                "tokens": pack["tokens"][si],
                "maps": pack["maps"][si].transpose(0, 1, 3, 2),
                "action": pack["action_features"][ai],
            }
            for name, values in arrays.items():
                finite = np.isfinite(values)
                z = (values - np.asarray(stats[name]["mean"])) / np.asarray(
                    stats[name]["std"]
                )
                acc = input_stats.setdefault(
                    name, dict(cells=0, finite=0, abs_z_gt10=0, max_abs_z=0.0)
                )
                acc["cells"] += values.size
                acc["finite"] += int(finite.sum())
                acc["abs_z_gt10"] += int((np.abs(z[finite]) > 10).sum())
                acc["max_abs_z"] = max(
                    acc["max_abs_z"], float(np.max(np.abs(z[finite])))
                )
            for name in ("token_mask", "map_mask"):
                values = pack[name][si]
                acc = input_stats.setdefault(name, dict(cells=0, true=0))
                acc["cells"] += values.size
                acc["true"] += int(np.count_nonzero(values))
            if day_number % 100 == 0:
                print(
                    json.dumps(dict(stage="train_final_inference", days=day_number)),
                    flush=True,
                )
    assert np.isfinite(predictions).all() and np.isfinite(logits).all()
    result["input_diagnostics"] = input_stats
    result["final_train_metrics"] = {}
    subsets = {"pooled": sample, **{k: v for k, v in sample.groupby("ticker")}}
    for key, rows in subsets.items():
        w = rows.weight.to_numpy(float)
        target = rows.net_base.to_numpy(float) / rows.ticker.map(scales).to_numpy(float)
        teacher = rows.state_optimal_action.to_numpy(float)
        pred = predictions[rows.sample_i]
        logit = logits[rows.sample_i]
        sq = (pred - target) ** 2
        bce = np.logaddexp(0, logit) - teacher * logit
        constant_sse = np.dot(w, (target - np.average(target, weights=w)) ** 2)
        result["final_train_metrics"][key] = dict(
            weighted_mse=float(np.average(sq, weights=w)),
            weighted_bce=float(np.average(bce, weights=w)),
            combined_sum=float(np.dot(w, sq + 0.1 * bce) / 1024),
            regression_sum=float(np.dot(w, sq) / 1024),
            auxiliary_sum=float(0.1 * np.dot(w, bce) / 1024),
            r2=float(1 - np.dot(w, sq) / constant_sse),
            mean_prediction=float(np.average(pred, weights=w)),
            prediction_std=float(
                np.sqrt(
                    np.average((pred - np.average(pred, weights=w)) ** 2, weights=w)
                )
            ),
            positive_score_share=float(np.average(pred > 0, weights=w)),
            mean_teacher_probability=float(
                np.average(1 / (1 + np.exp(-logit)), weights=w)
            ),
            teacher_probability_gt_half_share=float(np.average(logit > 0, weights=w)),
        )
    sample["train_prediction_scaled"] = predictions
    sample["train_teacher_logit"] = logits
    sample.to_parquet(out / "train_diagnostic_predictions.parquet", index=False)
    result["feature_sources"] = store.hashes
    for name, digest in hashes.items():
        assert module.sha(learner / name) == digest
    result["status"] = "COMPLETED_READ_ONLY_TRAIN_DIAGNOSTIC"
    result["prediction_sha256"] = module.sha(
        out / "train_diagnostic_predictions.parquet"
    )
    (out / "summary.json").write_text(json.dumps(result, indent=2))
    print(
        json.dumps(dict(status=result["status"], final=result["final_train_metrics"])),
        flush=True,
    )


if __name__ == "__main__":
    main()
