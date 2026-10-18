"""Read-only diagnosis of completed GBT fits on their exact training sample.

No new fit, policy choice, test labels or feature construction. In-sample scores
diagnose fitting capacity; they are not evidence of economic generalization.
"""
import hashlib
import json
import os
from pathlib import Path

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"

import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stats(y, predicted, weights):
    y, predicted, weights = map(np.asarray, (y, predicted, weights))
    assert len(y) and np.isfinite(y).all() and np.isfinite(predicted).all()
    assert np.isfinite(weights).all() and (weights > 0).all()
    mean = np.average(y, weights=weights)
    variance = np.average((y - mean) ** 2, weights=weights)
    mse = np.average((predicted - y) ** 2, weights=weights)
    return dict(rows=len(y), target_mean=float(mean), prediction_mean=float(np.average(predicted, weights=weights)),
                target_std=float(np.sqrt(variance)), prediction_std=float(np.sqrt(np.average(
                    (predicted - np.average(predicted, weights=weights)) ** 2, weights=weights))),
                bias=float(np.average(predicted - y, weights=weights)),
                mse=float(mse), r2=float(1 - mse / variance) if variance else None,
                fraction_predicted_positive=float(np.average(predicted > 0, weights=weights)),
                fraction_target_positive=float(np.average(y > 0, weights=weights)))


def columns(schema, extra_width):
    names = ["base/" + name for name in schema["base_names"]]
    names += [f"candles/{slot}/{name}" for slot in range(20) for name in schema["token_names"]]
    names += [f"token_masks/{slot}/{mask}" for slot in range(20) for mask in ("valid", "exists")]
    names += [f"spatial/{slot}/{name}/{cell}" for slot in range(20) for name in schema["map_names"] for cell in range(8)]
    names += [f"map_masks/{slot}/{name}" for slot in range(20) for name in schema["map_names"]]
    names += ["action/" + name for name in schema["action_names"]]
    names += [f"episode/{index}" for index in range(extra_width)]
    return names


def main():
    out = ROOT / "train_signal_diagnostic_v1"
    out.mkdir(exist_ok=False)
    baseline = ROOT / "learners_v1"
    episode = ROOT / "episode_learners_v1"
    paths = [baseline / name for name in ("training_sample.parquet", "train_x.npy", "normalizers.json", "feature_schema.json", "gbt_net.txt", "gbt_advantage.txt")]
    paths += [episode / name for name in ("training_sample.parquet", "train_x.npy", "gbt_net_episode.txt")]
    hashes = {str(path): sha(path) for path in paths}
    sample = pd.read_parquet(baseline / "training_sample.parquet")
    other = pd.read_parquet(episode / "training_sample.parquet")
    pd.testing.assert_frame_equal(sample, other)
    assert (sample.date.astype(str) < "20250101").all()
    assert np.array_equal(sample.sample_i.to_numpy(), np.arange(len(sample)))
    scales = json.loads((baseline / "normalizers.json").read_text())["risk_scales_usd"]
    schema = json.loads((baseline / "feature_schema.json").read_text())
    row_scale = sample.ticker.map(scales).to_numpy(float)
    weights = sample.weight.to_numpy(float)
    results = {}
    for model_name, folder, target in (("gbt_net", baseline, "net_base"), ("gbt_advantage", baseline, "dp_advantage"), ("gbt_net_episode", episode, "net_base")):
        x = np.load(folder / "train_x.npy", mmap_mode="r")
        model = lgb.Booster(model_file=str(folder / (model_name + ".txt")))
        assert x.shape[0] == len(sample) and x.shape[1] == model.num_feature()
        names = columns(schema, 70 if folder == episode else 0)
        assert len(names) == x.shape[1]
        prediction = np.empty(len(sample), np.float64)
        for start in range(0, len(sample), 1024):
            stop = min(start + 1024, len(sample))
            prediction[start:stop] = model.predict(x[start:stop], num_threads=4)
        y = sample[target].to_numpy(float) / row_scale
        model_stats = {"target": target, "scaled_pooled": stats(y, prediction, weights), "ticker_year": {}}
        for (ticker, year), indices in sample.groupby(["ticker", sample.date.astype(str).str[:4]]).indices.items():
            model_stats["ticker_year"][ticker + "_" + year] = stats(y[indices], prediction[indices], weights[indices])
        order = np.argsort(prediction, kind="stable")
        # Weighted prediction deciles under original action-population IPW.
        cdf = (np.cumsum(weights[order]) - weights[order] / 2) / weights.sum()
        bins = np.minimum((cdf * 10).astype(int), 9)
        model_stats["prediction_deciles"] = [dict(decile=number, **stats(y[order[bins == number]], prediction[order[bins == number]], weights[order[bins == number]])) for number in range(10) if (bins == number).any()]
        gain = model.feature_importance(importance_type="gain")
        model_stats["top_feature_gain"] = [{"name": names[index], "gain": float(gain[index])} for index in np.argsort(-gain, kind="stable")[:30]]
        model_stats["group_gain"] = {group: float(sum(value for name, value in zip(names, gain, strict=True) if name.split("/")[0] == group)) for group in sorted({name.split("/")[0] for name in names})}
        model_stats["trees"] = model.num_trees()
        results[model_name] = model_stats
        np.save(out / (model_name + "_scaled_predictions.npy"), prediction)
        print(json.dumps({"model": model_name, **model_stats["scaled_pooled"]}), flush=True)
        del x, model
    assert all(sha(path) == expected for path, expected in hashes.items())
    report = dict(status="COMPLETE_READ_ONLY_TRAIN_DIAGNOSTIC", scope="In-sample only; no new fits; original IPW action population; not policy PnL", code_sha256=sha(__file__), sources=hashes, results=results)
    (out / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
