"""Read-only fitting/availability diagnostic on the frozen original TRAIN sample.

No fit, policy selection, validation/test data or economic replay. Feature gain
describes model use; it does not establish a causal market explanation.
"""

import os
from pathlib import Path
import json

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"

import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from inspect_training_signal import stats  # noqa: E402
from train_market_cue_control import Checkpoints, atomic_json, read_json, require, sha  # noqa: E402
from market_cue_vectors import COLUMN_NAMES, VALUE_NAMES  # noqa: E402


def main():
    root = Path("D:/GexResearchArtifacts/level_oracle_20261018")
    trained = root / "market_cue_control_v1"
    original = root / "learners_v1"
    output = root / "market_cue_train_diagnostic_v1"
    output.mkdir(exist_ok=False)
    contract = read_json(trained / "run_contract.json")
    checkpoint = Checkpoints(trained, sha(trained / "run_contract.json"))
    require(checkpoint.complete("matrix", ["train_x.npy", "targets.npz"]), "Matrix incomplete")
    require(checkpoint.complete("model", ["cue_net.txt", "fit_started.json", "matrix.complete.json"]), "Model incomplete")
    paths = [trained / name for name in ("run_contract.json", "matrix.complete.json", "model.complete.json", "train_x.npy", "targets.npz", "cue_net.txt")]
    paths += [original / "training_sample.parquet", original / "gbt_net.txt", root / "train_signal_diagnostic_v1" / "summary.json"]
    paths += [Path(__file__), Path(__file__).with_name("inspect_training_signal.py"), Path(__file__).with_name("market_cue_vectors.py")]
    sources = {str(path.resolve()): sha(path) for path in paths}
    for path in paths[6:8]:
        require(sources[str(path.resolve())] == contract["sources"][str(path.resolve())], "Original source changed")
    require(sources[str(Path(__file__).with_name("market_cue_vectors.py").resolve())] == contract["dependencies"]["market_cue_vectors.py"], "Vector schema changed")
    reference = read_json(paths[8])
    require(reference["status"] == "COMPLETE_READ_ONLY_TRAIN_DIAGNOSTIC", "Original diagnostic incomplete")
    for path in paths[6:8]:
        require(reference["sources"][str(path)] == sha(path), "Original comparison identity differs")
    sample = pd.read_parquet(paths[6], columns=["sample_i", "ticker", "date", "net_base", "weight"])
    require(np.array_equal(sample.sample_i, np.arange(270377)), "Wrong sample order")
    require(sample.date.astype(str).str[:4].isin(["2023", "2024"]).all(), "Outside TRAIN")
    with np.load(trained / "targets.npz", allow_pickle=False) as packed:
        y, weight = packed["y"], packed["weight"]
        require(np.array_equal(packed["sample_i"], sample.sample_i), "Target identity differs")
    require(np.array_equal(y, sample.net_base.to_numpy(float) / sample.ticker.map(contract["scales"]).to_numpy(float)), "Target differs")
    require(np.array_equal(weight, sample.weight.to_numpy(float)), "Weights differ")
    x = np.load(trained / "train_x.npy", mmap_mode="r")
    require(x.shape == (270377, 152), "Wrong matrix shape")
    model = lgb.Booster(model_file=str(trained / "cue_net.txt"))
    require(model.num_feature() == len(COLUMN_NAMES) == 152, "Wrong model width")
    predictions = np.empty(len(y), np.float64)
    available = np.zeros(len(VALUE_NAMES), np.float64)
    for start in range(0, len(y), 4096):
        stop = min(start + 4096, len(y))
        block = np.asarray(x[start:stop])
        masks = block[:, 1::2]
        require(np.isfinite(block).all() and np.isin(masks, [0, 1]).all(), "Invalid matrix/mask")
        require((block[:, ::2][masks == 0] == 0).all(), "Missing value not zero-masked")
        available += np.sum(masks * weight[start:stop, None], axis=0)
        predictions[start:stop] = model.predict(block, num_threads=2)
    result = stats(y, predictions, weight)
    by_period = {}
    for (ticker, year), indices in sample.groupby(["ticker", sample.date.astype(str).str[:4]]).indices.items():
        by_period[ticker + "_" + year] = stats(y[indices], predictions[indices], weight[indices])
    gain = model.feature_importance(importance_type="gain")
    record = dict(
        status="COMPLETE_READ_ONLY_MARKET_CUE_TRAIN_DIAGNOSTIC",
        scope="Exact exposed TRAIN sample; no policy PnL or generalization claim",
        new_fits=0,
        validation_test_read=False,
        original_scaled_pooled=reference["results"]["gbt_net"]["scaled_pooled"],
        cue_scaled_pooled=result,
        ticker_year=by_period,
        trees=model.num_trees(),
        weighted_valid_fraction=dict(zip(VALUE_NAMES, (available / weight.sum()).tolist())),
        top_feature_gain=[dict(name=COLUMN_NAMES[i], gain=float(gain[i])) for i in np.argsort(-gain, kind="stable")[:30]],
        feature_gain_interpretation="Association in this fitted model, not a causal attribution or evidence of profitability",
        sources=sources,
    )
    prediction_path = output / "scaled_train_predictions.npy"
    with prediction_path.open("xb") as stream:
        np.save(stream, predictions, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    require(all(sha(path) == digest for path, digest in sources.items()), "Source changed during diagnostic")
    record["prediction_sha256"] = sha(prediction_path)
    atomic_json(output / "summary.json", record)
    print(json.dumps(dict(status=record["status"], **result)), flush=True)


if __name__ == "__main__":
    main()
