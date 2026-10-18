"""One reviewed 424-feature TRAIN fit; exact frozen control targets/configuration."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import os
from pathlib import Path
import shutil
import uuid

import numpy as np
import pandas as pd

import common_greek_dynamics as dynamic
import train_market_cue_control as original

sha, read_json, require = original.sha, original.read_json, original.require
KEYS = ("sample_i", "day_key", "ticker", "date", "action_id", "state_i", "weight")


def sync(path):
    with Path(path).open("r+b") as handle:
        os.fsync(handle.fileno())


def separate(out, inputs):
    out = Path(out).resolve()
    for path in inputs:
        path = Path(path).resolve()
        require(
            not out.is_relative_to(path) and not path.is_relative_to(out),
            "Output overlaps input",
        )


class TrainingInputs:
    def __init__(self, features, cue, learner, authorities, expected_rows=270377):
        self.features, self.cue, self.learner = (
            Path(p).resolve() for p in (features, cue, learner)
        )
        self.hashes = {}
        for path, digest in authorities.items():
            self.verify(path, digest)
        required = [
            self.features / "run_contract.json",
            self.features / "matrix.complete.json",
            self.cue / "run_contract.json",
            self.cue / "matrix.complete.json",
            self.cue / "model.complete.json",
        ]
        require(
            all(str(p) in self.hashes for p in required),
            "Review omits mandatory authority",
        )
        feature_contract = read_json(required[0])
        require(
            feature_contract.get("train_only") is True
            and feature_contract.get("fit_authorized") is False
            and feature_contract.get("close_i") == 390
            and feature_contract.get("rows") == expected_rows,
            "Wrong TRAIN feature scope",
        )
        control = read_json(self.cue / "run_contract.json")
        for root in (self.features, self.cue):
            marker = read_json(root / "matrix.complete.json")
            consumed = (
                {"train_x.npy", "row_keys.npz", "coverage.json"}
                if root == self.features
                else {"train_x.npy", "targets.npz"}
            )
            require(
                consumed.issubset(marker["files"]),
                "Matrix marker omits consumed member",
            )
            require(
                marker["status"] == "COMPLETE"
                and marker["binding"] == sha(root / "run_contract.json"),
                "Matrix completion binding differs",
            )
            for rel, digest in marker["files"].items():
                path = (root / rel).resolve()
                require(path.is_relative_to(root), "Unsafe matrix member")
                self.verify(path, digest)
            source_key = "sources" if root == self.features else "source_hashes"
            for path, digest in marker["extra"][source_key].items():
                self.verify(path, digest)
        for path, digest in feature_contract["sources"].items():
            self.verify(path, digest)
        model = read_json(self.cue / "model.complete.json")
        require(
            {"cue_net.txt", "fit_started.json", "matrix.complete.json"}.issubset(
                model["files"]
            ),
            "Control model marker omits consumed member",
        )
        require(
            model["status"] == "COMPLETE"
            and model["binding"] == sha(self.cue / "run_contract.json"),
            "Control model binding differs",
        )
        for rel, digest in model["files"].items():
            path = (self.cue / rel).resolve()
            require(path.is_relative_to(self.cue), "Unsafe control model member")
            self.verify(path, digest)
        require(control["config"] == original.CONFIG, "Control config differs")
        self.scales = control["scales"]
        require(
            set(self.scales) == {"QQQ", "SPY", "SPXW"}
            and all(np.isfinite(v) and v > 0 for v in self.scales.values()),
            "Invalid scales",
        )
        self.columns = feature_contract["columns"]
        require(
            len(self.columns) == 424
            and self.columns[:152] == control["schema"]["column_names"],
            "Feature schema mismatch",
        )
        require(
            self.columns[152:] == list(dynamic.FEATURE_NAMES), "Dynamic schema differs"
        )
        sample_path = self.learner / "training_sample.parquet"
        require(str(sample_path) in self.hashes, "Original sample not bound")
        sample = pd.read_parquet(sample_path, columns=[*KEYS, "net_base"])
        sample["date"] = sample.date.astype(str)
        require(
            len(sample) == expected_rows
            and np.array_equal(sample.sample_i, np.arange(expected_rows))
            and sample.date.str[:4].isin(["2023", "2024"]).all()
            and sample.state_i.between(60, 375).all()
            and not sample.duplicated(["day_key", "action_id"]).any()
            and (sample.day_key == sample.ticker + "/" + sample.date).all(),
            "Invalid TRAIN identities",
        )
        with np.load(self.features / "row_keys.npz", allow_pickle=False) as keys:
            require(set(keys.files) == set(KEYS), "Unexpected row key schema")
            for name in KEYS:
                require(
                    np.array_equal(keys[name], sample[name].to_numpy()),
                    "Row key mismatch: " + name,
                )
        targets_path = self.cue / "targets.npz"
        require(
            str(targets_path) in self.hashes, "Targets not bound by control completion"
        )
        with np.load(targets_path, allow_pickle=False) as targets:
            require(
                set(targets.files) == {"y", "weight", "sample_i"},
                "Target schema differs",
            )
            require(
                np.array_equal(targets["sample_i"], sample.sample_i),
                "Target row mismatch",
            )
            self.y, self.weights = targets["y"].copy(), targets["weight"].copy()
        expected_y = sample.net_base.to_numpy(float) / sample.ticker.map(
            self.scales
        ).to_numpy(float)
        require(
            np.array_equal(self.y, expected_y)
            and np.array_equal(self.weights, sample.weight.to_numpy(float)),
            "Targets/IPW differ from original",
        )
        require(
            np.isfinite(self.y).all()
            and np.isfinite(self.weights).all()
            and (self.weights > 0).all()
            and np.isclose(self.weights.mean(), 1, atol=1e-12),
            "Invalid targets/IPW",
        )
        self.matrix = self.features / "train_x.npy"
        x, baseline = (
            np.load(p, mmap_mode="r", allow_pickle=False)
            for p in (self.matrix, self.cue / "train_x.npy")
        )
        require(
            x.shape == (expected_rows, 424)
            and x.dtype == np.float32
            and baseline.shape == (expected_rows, 152)
            and baseline.dtype == np.float32,
            "Matrix dtype/shape differs",
        )
        for start in range(0, expected_rows, 8192):
            chunk = np.asarray(x[start : start + 8192])
            require(
                np.isfinite(chunk).all()
                and np.array_equal(
                    chunk[:, :152].view(np.uint32),
                    baseline[start : start + 8192].view(np.uint32),
                ),
                "Prefix not bit-exact or nonfinite features",
            )
        del x, baseline

    def verify(self, path, digest):
        path = str(Path(path).resolve())
        require(
            sha(path) == digest and self.hashes.get(path, digest) == digest,
            "Source authority differs: " + path,
        )
        self.hashes[path] = digest

    def recheck(self):
        for path, digest in list(self.hashes.items()):
            self.verify(path, digest)


def readback(source, evidence):
    import lightgbm as lgb

    model = lgb.Booster(
        model_str=(evidence.root / "common_greek_net.txt").read_text(encoding="utf-8")
    )
    require(model.num_feature() == 424, "Export width differs")
    x = np.load(source.matrix, mmap_mode="r", allow_pickle=False)
    reference = np.load(
        evidence.root / "train_readback_predictions.npy",
        mmap_mode="r",
        allow_pickle=False,
    )
    require(
        reference.shape == (len(source.y),) and reference.dtype == np.float64,
        "Readback schema differs",
    )
    for start in range(0, len(source.y), 8192):
        prediction = np.asarray(
            model.predict(x[start : start + 8192], num_threads=4), np.float64
        )
        require(
            np.isfinite(prediction).all()
            and np.array_equal(prediction, reference[start : start + 8192]),
            "Saved model prediction differs from in-memory model",
        )
    del x, reference


def fit_once(
    source,
    evidence,
    factory=original.model_factory,
    resource_gate=original.wait_resources,
):
    members = [
        "common_greek_net.txt",
        "train_readback_predictions.npy",
        "fit_started.json",
        "run_contract.json",
    ]
    if evidence.complete("model", members + ["export.complete.json"]):
        source.recheck()
        readback(source, evidence)
        source.recheck()
        return
    if not evidence.complete("export", members):
        started = evidence.root / "fit_started.json"
        require(
            not started.exists()
            and not (evidence.root / "common_greek_net.txt").exists(),
            "Interrupted fit preserved; automatic refit forbidden",
        )
        resource_gate()
        source.recheck()
        original.atomic_json(
            started,
            dict(
                binding=evidence.binding,
                config=original.CONFIG,
                started_utc=datetime.now(timezone.utc).isoformat(),
                matrix_sha256=sha(source.matrix),
                rows=len(source.y),
                width=424,
            ),
        )
        x = np.load(source.matrix, mmap_mode="r", allow_pickle=False)
        model = factory()
        print(f"FIT_STARTED rows={len(source.y)} width=424", flush=True)
        model.fit(x, source.y, sample_weight=source.weights)
        require(model.booster_.num_feature() == 424, "Trained width differs")
        destination = evidence.root / "common_greek_net.txt"
        temporary = destination.with_name(
            destination.name + ".partial-" + uuid.uuid4().hex
        )
        # Python handles Unicode Windows paths; LightGBM's narrow path API may not.
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(model.booster_.model_to_string())
            handle.flush()
            os.fsync(handle.fileno())
        sync(temporary)
        os.replace(temporary, destination)
        destination = evidence.root / "train_readback_predictions.npy"
        temporary = destination.with_name(
            destination.name + ".partial-" + uuid.uuid4().hex
        )
        predictions = np.lib.format.open_memmap(
            temporary, mode="w+", dtype=np.float64, shape=(len(source.y),)
        )
        for start in range(0, len(source.y), 8192):
            predictions[start : start + 8192] = model.booster_.predict(
                x[start : start + 8192], num_threads=4
            )
        predictions.flush()
        del predictions, x, model
        sync(temporary)
        os.replace(temporary, destination)
        evidence.finish(
            "export", [evidence.root / p for p in members], dict(fit_completed=True)
        )
        print("FIT_EXPORTED; verifying exact TRAIN readback", flush=True)
    readback(source, evidence)
    source.recheck()
    evidence.finish(
        "model",
        [evidence.root / p for p in members + ["export.complete.json"]],
        dict(
            config=original.CONFIG,
            readback_exact=True,
            control_refitted=False,
            validation_test_evaluated=False,
            sources=source.hashes,
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("features", "cue", "learner", "review", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    separate(args.out, [args.features, args.cue, args.learner])
    review_sha = sha(args.review)
    review = read_json(args.review)
    require(
        sha(args.review) == review_sha
        and review["status"] == "PASS_COMMON_GREEK_TRAINER_REVIEW",
        "Exact trainer review required",
    )
    required_code = set(original.DEPENDENCIES) | {
        Path(__file__).name,
        "COMMON_GREEK_TRAINER_IMPLEMENTATION.md",
        "common_greek_dynamics.py",
        "level_engine.py",
        "COMMON_GREEK_DYNAMICS_V1_DESIGN.md",
        "COMMON_GREEK_DYNAMICS_V1_LEARNER_PLAN.md",
        "GREEK_UNITS_REVIEW.md",
    }
    require(
        required_code.issubset(review["files"]), "Review omits effective dependency"
    )
    for name, digest in review["files"].items():
        require(
            sha(Path(__file__).with_name(name)) == digest,
            "Unreviewed dependency: " + name,
        )
    with original.output_lock(args.out):
        source = TrainingInputs(
            args.features, args.cue, args.learner, review["authorities"]
        )
        source.verify(args.review, review_sha)
        for name, digest in review["files"].items():
            path = Path(__file__).with_name(name)
            source.verify(path, digest)
            snapshot = args.out / "code_snapshot" / name
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            if not snapshot.exists():
                temporary = snapshot.with_name(
                    snapshot.name + ".partial-" + uuid.uuid4().hex
                )
                shutil.copyfile(path, temporary)
                require(sha(temporary) == digest, "Snapshot changed")
                sync(temporary)
                os.replace(temporary, snapshot)
            source.verify(snapshot, digest)
        contract = dict(
            sources=source.hashes,
            config=original.CONFIG,
            scales=source.scales,
            schema=dict(column_names=source.columns),
            rows=len(source.y),
            train_only=True,
            control_model_refitted=False,
            packages={
                p: importlib.metadata.version(p)
                for p in ("numpy", "pandas", "lightgbm")
            },
        )
        path = args.out / "run_contract.json"
        if path.exists():
            require(read_json(path) == contract, "Run contract changed")
        else:
            original.atomic_json(path, contract)
        evidence = original.Checkpoints(args.out, sha(path))
        try:
            fit_once(source, evidence)
            print("COMPLETE_COMMON_GREEK_TRAIN_FIT", flush=True)
        except BaseException as error:
            original.atomic_json(
                args.out / ("failure_" + uuid.uuid4().hex + ".json"),
                dict(error=repr(error), utc=datetime.now(timezone.utc).isoformat()),
            )
            raise


if __name__ == "__main__":
    main()
