"""Read-only verification of outcome-free monthly day-sample artifacts."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    run = ROOT / "monthly_walk_forward_v1"
    index_path = ROOT / "session_clock_dataset_v1/index.parquet"
    index = pd.read_parquet(index_path, columns=["ticker", "date", "status", "close_i"])
    binding = sha(run / "run_contract.json")
    samples = sorted((run / "day_samples").rglob("*.npz"))
    available = index[index.status == "COMPLETE"]
    expected = {
        (str(r.ticker), str(r.date)): int(r.close_i) for r in available.itertuples()
    }
    assert len(index) == 2625 and len(expected) == len(samples) == 2619
    assert {(p.parent.name, p.stem) for p in samples} == set(expected)
    assert len(list((run / "day_samples").rglob("*.complete.json"))) == len(samples)
    selected = population = short_days = 0
    maximum_weight_error = 0.0
    records = []
    for path in samples:
        ticker, date = path.parent.name, path.stem
        close_i = expected[ticker, date]
        marker_path = path.with_suffix(".complete.json")
        marker = json.loads(marker_path.read_text())
        digest = sha(path)
        assert marker["status"] == "COMPLETE" and marker["binding"] == binding
        assert marker["files"] == {str(path.relative_to(run)): digest}
        with np.load(path, allow_pickle=False) as z:
            assert set(z.files) == {
                "action_id",
                "state_i",
                "band_i",
                "identity_sha256",
                "weight",
                "population_by_band",
                "selected_by_band",
            }
            ids, states, bands = z["action_id"], z["state_i"], z["band_i"]
            pop, counts, weights = (
                z["population_by_band"],
                z["selected_by_band"],
                z["weight"],
            )
            n = len(ids)
            assert n > 0 and len(np.unique(ids)) == n
            assert np.all((states >= 60) & (states <= close_i - 15))
            assert np.array_equal(bands, (states - 60) // 79)
            assert np.array_equal(counts, np.minimum(pop, 32))
            assert np.array_equal(np.bincount(bands, minlength=4), counts)
            assert np.array_equal(weights, pop[bands] / (pop.sum() * counts[bands]))
            error = abs(float(weights.sum()) - 1.0)
            assert error < 1e-12
            maximum_weight_error = max(maximum_weight_error, error)
            digests = [
                hashlib.sha256(
                    json.dumps(
                        [20261018, ticker, date, int(s), int(a)],
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ).encode()
                ).hexdigest()
                for a, s in zip(ids, states)
            ]
            assert np.array_equal(np.asarray(digests), z["identity_sha256"])
            for band in range(4):
                subset = z["identity_sha256"][bands == band].tolist()
                assert subset == sorted(subset)
            if close_i == 210:
                short_days += 1
                assert np.all(pop[2:] == 0) and np.all(counts[2:] == 0)
            selected += n
            population += int(pop.sum())
        records.append(
            {"path": str(path), "sha256": digest, "marker_sha256": sha(marker_path)}
        )
    assert short_days == 24 and population == 15445024
    forbidden = [
        "models",
        "predictions",
        "matrices",
        "day_chunks",
        "feature_inputs",
        "reports",
        "validation_freeze.json",
    ]
    assert not any((run / name).exists() for name in forbidden)
    result = dict(
        status="PASS_MONTHLY_PREPARE_ARTIFACT_VERIFICATION",
        calendar_rows=len(index),
        available_days=len(samples),
        missing_days=6,
        full_days=len(samples) - short_days,
        short_days=short_days,
        selected_rows=selected,
        offered_population=population,
        maximum_day_weight_error=maximum_weight_error,
        labels_read=False,
        features_read=False,
        fits_started=False,
        verification_scope="Sample seals, stored identities, counts, weights and bounds; no rescan of unsampled source actions",
        run_contract_sha256=binding,
        source_index_sha256=sha(index_path),
        producer_sha256=sha(Path(__file__)),
        artifacts=records,
    )
    output = ROOT / "monthly_walk_forward_v1_prepare_verification.json"
    assert not output.exists(), "Preserve previous evidence"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "artifacts"}, indent=2))
    print("verification_sha256=" + sha(output))


if __name__ == "__main__":
    main()
