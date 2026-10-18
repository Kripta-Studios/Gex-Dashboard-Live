"""Isolated prepare/fit control on the EXACT original training sample.

No validation/test evaluation, resampling, original model refit, or GPU work.
Both stages require an exact implementation review; this module is inert on import.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

import numpy as np
import pandas as pd

import features
import market_cue_vectors as vectors
import market_cue_vectors_fast as fast
from run_market_cue_diagnostic import sha, read_json

CONFIG = dict(
    objective="regression",
    n_estimators=200,
    num_leaves=31,
    max_depth=6,
    min_child_samples=100,
    learning_rate=0.04,
    reg_lambda=10.0,
    max_bin=63,
    random_state=20261018,
    n_jobs=4,
    deterministic=True,
    force_col_wise=True,
    verbosity=-1,
)
SAMPLE_COLUMNS = [
    "sample_i",
    "day_key",
    "ticker",
    "date",
    "action_id",
    "state_i",
    "net_base",
    "weight",
    "status",
]
DEPENDENCIES = (
    "train_market_cue_control.py",
    "market_cue_vectors.py",
    "market_cue_vectors_fast.py",
    "market_cues.py",
    "features.py",
    "run_market_cue_diagnostic.py",
    "MARKET_CUE_LEARNER_PLAN_DRAFT.md",
)


def require(value, message):
    if not bool(value):
        raise ValueError(message)


def dependencies():
    return {name: sha(Path(__file__).with_name(name)) for name in DEPENDENCIES}


def verify_review_authorities(review, learner_audit, engine_audit):
    expected = review.get("authorities", {})
    require(
        set(expected) == {"learner_audit_sha256", "engine_audit_sha256"}
        and sha(learner_audit) == expected["learner_audit_sha256"]
        and sha(engine_audit) == expected["engine_audit_sha256"],
        "Audit differs from independently reviewed authority",
    )


def bind_code_snapshots(source, output, expected):
    """Keep exact reviewed code and recheck it before every completion marker."""
    directory = Path(output) / "code_snapshot"
    directory.mkdir(parents=True, exist_ok=True)
    for name, digest in expected.items():
        original = Path(__file__).with_name(name)
        source.verify(original, digest)
        snapshot = directory / name
        if not snapshot.exists():
            temporary = snapshot.with_name(
                snapshot.name + ".partial-" + uuid.uuid4().hex
            )
            with original.open("rb") as incoming, temporary.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
                outgoing.flush()
                os.fsync(outgoing.fileno())
            require(sha(temporary) == digest, "Code changed during snapshot")
            os.replace(temporary, snapshot)
        source.verify(snapshot, digest)


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), "Never overwrite published evidence")
    temporary = path.with_name(path.name + ".partial-" + uuid.uuid4().hex)
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, sort_keys=True, allow_nan=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@contextmanager
def output_lock(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


class Checkpoints:
    def __init__(self, root, binding):
        self.root, self.binding = Path(root).resolve(), binding
        self.root.mkdir(parents=True, exist_ok=True)

    def marker(self, name):
        return self.root / (name + ".complete.json")

    def complete(self, name, required=()):
        if not self.marker(name).exists():
            return False
        record = read_json(self.marker(name))
        require(
            record.get("binding") == self.binding
            and record.get("status") == "COMPLETE",
            "Checkpoint binding differs",
        )
        files = record["files"]
        require(
            files and set(required).issubset(files), "Checkpoint omits consumed member"
        )
        for rel, digest in files.items():
            path = (self.root / rel).resolve()
            require(
                path.is_relative_to(self.root) and sha(path) == digest,
                "Changed checkpoint member",
            )
        return True

    def finish(self, name, paths, extra=None):
        require(not self.marker(name).exists(), "Never overwrite completed checkpoint")
        relative = [str(Path(path).resolve().relative_to(self.root)) for path in paths]
        atomic_json(
            self.marker(name),
            dict(
                status="COMPLETE",
                binding=self.binding,
                files={name: sha(self.root / name) for name in relative},
                extra=extra or {},
            ),
        )

    def preserve(self, path):
        path = Path(path).resolve()
        require(path.is_relative_to(self.root), "Cannot preserve source outside output")
        if path.exists():
            destination = (
                self.root
                / "preserved_orphans"
                / uuid.uuid4().hex
                / path.relative_to(self.root)
            )
            require(
                destination.resolve().is_relative_to(self.root),
                "Unsafe orphan destination",
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            path.rename(destination)


class OriginalInputs:
    """Hash authorities are existing audits/freeze; never baseline current feature bytes."""

    def __init__(self, original_root, engine_root, learner_audit, engine_audit):
        self.original, self.engine = (
            Path(original_root).resolve(),
            Path(engine_root).resolve(),
        )
        self.hashes = {}
        audit, oracle = read_json(learner_audit), read_json(engine_audit)
        require(
            audit["status"] == "PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT",
            "Original learner audit required",
        )
        require(
            oracle["status"] == "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT",
            "Original oracle audit required",
        )
        require(
            Path(audit["binding"]["learner_root"]).resolve() == self.original
            and Path(oracle["binding"]["engine_root"]).resolve() == self.engine,
            "Wrong authority root",
        )
        self.verify(learner_audit, sha(learner_audit))
        self.verify(engine_audit, audit["binding"]["oracle_full_audit_sha256"])
        self.verify(self.original / "freeze.json", audit["binding"]["freeze_sha256"])
        self.verify(self.engine / "index.parquet", oracle["binding"]["index_sha256"])
        frozen = read_json(self.original / "freeze.json")
        self.feature_hashes = {
            str(Path(p).resolve()): value
            for p, value in frozen["feature_sources"].items()
        }
        for name in (
            "training_sample.parquet",
            "normalizers.json",
            "gbt_net.txt",
            "sampling_manifest.json",
        ):
            self.verify(self.original / name, frozen["artifacts"][name])
        self.scales = read_json(self.original / "normalizers.json")["risk_scales_usd"]
        require(
            set(self.scales) == {"SPY", "QQQ", "SPXW"}
            and all(np.isfinite(x) and x > 0 for x in self.scales.values()),
            "Invalid original risk scales",
        )
        self.sample = pd.read_parquet(
            self.original / "training_sample.parquet", columns=SAMPLE_COLUMNS
        )
        self.sample["date"] = self.sample.date.astype(str)
        validate_sample(self.sample, 270377)
        self.index = pd.read_parquet(
            self.engine / "index.parquet",
            columns=[
                "ticker",
                "date",
                "status",
                "day_root",
                "actions_sha256",
                "cache_npz_sha256",
                "cache_meta_sha256",
            ],
        )
        self.index["date"] = self.index.date.astype(str)
        self.index = self.index.set_index(["ticker", "date"], verify_integrity=True)
        self.feature_root = self.original.parent / "features_v1"
        self.verify_feature(self.feature_root / "feature_contract.json")
        self.contract = read_json(self.feature_root / "feature_contract.json")
        require(
            self.contract.get("outcomes_read") is False, "Noncausal feature contract"
        )
        for name, digest in self.contract["dependencies"].items():
            require(Path(name).name == name, "Unsafe dependency name")
            self.verify(Path(__file__).with_name(name), digest)

    def verify(self, path, digest):
        path = Path(path).resolve()
        require(sha(path) == digest, "Source differs from authority: " + str(path))
        require(
            str(path) not in self.hashes or self.hashes[str(path)] == digest,
            "Source binding changed",
        )
        self.hashes[str(path)] = digest

    def verify_feature(self, path):
        path = Path(path).resolve()
        require(
            str(path) in self.feature_hashes,
            "Feature absent from original frozen authority",
        )
        self.verify(path, self.feature_hashes[str(path)])

    def recheck(self):
        for path, digest in list(self.hashes.items()):
            self.verify(path, digest)

    def day(self, key):
        ticker, date = key.split("/")
        record = self.index.loc[(ticker, date)]
        require(
            record.status == "COMPLETE" and date < "20250101",
            "Training loader cannot open validation/test",
        )
        directory = self.feature_root / ticker / date
        paths = [
            directory / name
            for name in ("features.npz", "features.json", "actions.npz", "actions.json")
        ]
        for path in paths:
            self.verify_feature(path)
        meta, ameta = read_json(paths[1]), read_json(paths[3])
        for metadata, array in ((meta, paths[0]), (ameta, paths[2])):
            require(
                metadata.get("outcomes_read") is False
                and metadata["sha256"] == self.feature_hashes[str(array.resolve())],
                "Invalid feature metadata",
            )
            require(
                metadata["binding"]["dependencies"] == self.contract["dependencies"]
                and metadata["binding"]["source_sha256"] == record.cache_npz_sha256
                and metadata["binding"]["source_metadata_sha256"]
                == record.cache_meta_sha256,
                "Feature cache binding differs",
            )
        for field, expected in (
            ("base_names", features.BASE_NAMES),
            ("token_names", features.TOKEN_NAMES),
            ("action_names", features.ACTION_NAMES),
        ):
            require(
                self.contract["schema"][field] == list(expected),
                "Feature whitelist differs",
            )
        require(
            meta["schema"] == self.contract["schema"]
            and ameta["action_names"] == list(features.ACTION_NAMES),
            "Day schema differs",
        )
        actions_path = Path(record.day_root) / "actions.parquet"
        self.verify(actions_path, record.actions_sha256)
        offered = pd.read_parquet(
            actions_path, columns=["action_id", *features.ACTION_INPUT_NAMES]
        )
        require(
            hashlib.sha256(offered.to_numpy(np.float64).tobytes()).hexdigest()
            == ameta["binding"]["action_inputs_sha256"],
            "Action inputs differ",
        )
        with np.load(paths[0], allow_pickle=False) as values:
            pack = {
                name: values[name]
                for name in (
                    "state_i",
                    "base",
                    "tokens",
                    "token_mask",
                    "bar_mask",
                    "bar_end_i",
                )
            }
        with np.load(paths[2], allow_pickle=False) as values:
            pack["action_features"], action_ids = (
                values["action_features"],
                values["action_id"],
            )
        for path in paths:
            self.verify_feature(path)
        self.verify(actions_path, record.actions_sha256)
        return (
            pack,
            action_ids,
            offered,
            {
                str(path.resolve()): self.hashes[str(path.resolve())]
                for path in [*paths, actions_path]
            },
        )


def validate_sample(sample, expected_rows):
    require(
        len(sample) == expected_rows
        and np.array_equal(sample.sample_i, np.arange(expected_rows)),
        "Exact original sample order/count required",
    )
    require(
        not sample.duplicated(["day_key", "action_id"]).any(),
        "Duplicate sampled action",
    )
    require(
        sample.date.astype(str).str[:4].isin(["2023", "2024"]).all(),
        "Sample outside TRAIN",
    )
    require(
        (sample.day_key == sample.ticker + "/" + sample.date.astype(str)).all(),
        "Sample day identity differs",
    )
    require(
        np.isfinite(sample.net_base).all()
        and np.isfinite(sample.weight).all()
        and (sample.weight > 0).all(),
        "Invalid targets/weights",
    )
    require(
        np.isclose(sample.weight.mean(), 1.0, atol=1e-12),
        "Original mean-one IPW required",
    )
    require(
        sample.status.isin(["FILLED", "NO_FILL"]).all()
        and (sample.loc[sample.status == "NO_FILL", "net_base"] == 0).all(),
        "NO_FILL semantics differ",
    )


def prepare_matrix(source, checkpoints, block=256):
    sample = source.sample
    n, width = len(sample), len(vectors.COLUMN_NAMES)
    marker, matrix = "matrix", checkpoints.root / "train_x.npy"
    if checkpoints.complete(marker, ["train_x.npy", "targets.npz"]):
        for path, digest in read_json(checkpoints.marker(marker))["extra"][
            "source_hashes"
        ].items():
            source.verify(path, digest)
        return matrix
    require(
        shutil.disk_usage(checkpoints.root).free >= n * width * 4 + 2 * 1024**3,
        "Insufficient matrix staging space",
    )
    chunks = []
    for key, rows in sample.groupby("day_key", sort=True):
        name = "chunks/" + key
        path = checkpoints.root / (name + ".npz")
        relative = str(path.relative_to(checkpoints.root))
        if checkpoints.complete(name, [relative]):
            for source_path, digest in read_json(checkpoints.marker(name))["extra"][
                "source_hashes"
            ].items():
                source.verify(source_path, digest)
        else:
            pack, ids, offered, day_hashes = source.day(key)
            output = np.empty((len(rows), width), np.float32)
            for start in range(0, len(rows), block):
                subset = rows.iloc[start : start + block]
                ai, si = vectors.join_action_rows(
                    reference_action_ids=subset.action_id.to_numpy(),
                    reference_state_i=subset.state_i.to_numpy(),
                    pack_action_ids=ids,
                    offered_action_ids=offered.action_id.to_numpy(),
                    offered_state_i=offered.state_i.to_numpy(),
                    pack_state_i=pack["state_i"],
                )
                output[start : start + len(subset)] = fast.vectorize_rows(
                    **pack, action_positions=ai, state_positions=si
                )
            checkpoints.preserve(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                np.savez_compressed(
                    handle,
                    sample_i=rows.sample_i.to_numpy(),
                    action_id=rows.action_id.to_numpy(),
                    state_i=rows.state_i.to_numpy(),
                    x=output,
                )
                handle.flush()
                os.fsync(handle.fileno())
            checkpoints.finish(name, [path], dict(source_hashes=day_hashes))
        chunks.append((path, rows))
    checkpoints.preserve(matrix)
    x = np.lib.format.open_memmap(matrix, mode="w+", dtype=np.float32, shape=(n, width))
    for path, rows in chunks:
        chunk_name = "chunks/" + rows.day_key.iloc[0]
        require(
            checkpoints.complete(chunk_name, [str(path.relative_to(checkpoints.root))]),
            "Chunk incomplete before assembly",
        )
        with np.load(path, allow_pickle=False) as values:
            require(
                np.array_equal(values["sample_i"], rows.sample_i)
                and np.array_equal(values["action_id"], rows.action_id)
                and np.array_equal(values["state_i"], rows.state_i),
                "Chunk identity differs from original sample",
            )
            require(
                values["x"].shape == (len(rows), width)
                and np.isfinite(values["x"]).all(),
                "Invalid feature chunk",
            )
            x[rows.sample_i.to_numpy()] = values["x"]
        require(
            checkpoints.complete(chunk_name, [str(path.relative_to(checkpoints.root))]),
            "Chunk changed during assembly",
        )
    x.flush()
    del x
    with matrix.open("r+b") as handle:
        os.fsync(handle.fileno())
    targets = checkpoints.root / "targets.npz"
    checkpoints.preserve(targets)
    divisor = sample.ticker.map(source.scales).to_numpy(float)
    with targets.open("xb") as handle:
        np.savez(
            handle,
            y=sample.net_base.to_numpy(float) / divisor,
            weight=sample.weight.to_numpy(float),
            sample_i=sample.sample_i.to_numpy(),
        )
        handle.flush()
        os.fsync(handle.fileno())
    source.recheck()
    checkpoints.finish(
        marker,
        [matrix, targets],
        dict(source_hashes=source.hashes, scales=source.scales),
    )
    return matrix


def resource_snapshot():
    import psutil

    available = psutil.virtual_memory().available
    if os.name != "nt":
        return available, available + psutil.swap_memory().free
    import ctypes
    from ctypes import wintypes

    class Performance(ctypes.Structure):
        _fields_ = (
            [("cb", wintypes.DWORD)]
            + [
                (key, ctypes.c_size_t)
                for key in (
                    "CommitTotal",
                    "CommitLimit",
                    "CommitPeak",
                    "PhysicalTotal",
                    "PhysicalAvailable",
                    "SystemCache",
                    "KernelTotal",
                    "KernelPaged",
                    "KernelNonpaged",
                    "PageSize",
                )
            ]
            + [
                (key, wintypes.DWORD)
                for key in ("HandleCount", "ProcessCount", "ThreadCount")
            ]
        )

    info = Performance()
    info.cb = ctypes.sizeof(info)
    require(
        ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb),
        "Cannot measure Windows commit",
    )
    return available, (info.CommitLimit - info.CommitTotal) * info.PageSize


def predict_offered_day(model, pack, action_ids, offered, scale, block=1024):
    """Feature-only adapter for a later sealed evaluation; never reads labels.

    Caller must bind source/model/scales and seal returned arrays before outcomes.
    All offered actions remain present, including those whose future fill is absent.
    """
    require(np.isfinite(scale) and scale > 0, "Fixed training risk scale required")
    require(
        model.num_feature() == len(vectors.COLUMN_NAMES),
        "Prediction model width differs",
    )
    require(not offered.action_id.duplicated().any(), "Duplicate offered action")
    scores = np.empty(len(offered), np.float64)
    for start in range(0, len(offered), block):
        rows = offered.iloc[start : start + block]
        ai, si = vectors.join_action_rows(
            reference_action_ids=rows.action_id.to_numpy(),
            reference_state_i=rows.state_i.to_numpy(),
            pack_action_ids=action_ids,
            offered_action_ids=offered.action_id.to_numpy(),
            offered_state_i=offered.state_i.to_numpy(),
            pack_state_i=pack["state_i"],
        )
        x = fast.vectorize_rows(**pack, action_positions=ai, state_positions=si)
        scores[start : start + len(rows)] = (
            np.asarray(model.predict(x, num_threads=4), np.float64) * scale
        )
    require(np.isfinite(scores).all(), "Nonfinite predicted net")
    return dict(
        action_id=offered.action_id.to_numpy().copy(),
        state_i=offered.state_i.to_numpy().copy(),
        scores=scores,
    )


def wait_resources():
    while True:
        ram, commit = resource_snapshot()
        if ram >= 12 * 1024**3 and commit >= 16 * 1024**3:
            return
        print(
            json.dumps(
                dict(stage="WAITING_RESOURCES", available_ram=ram, free_commit=commit)
            ),
            flush=True,
        )
        time.sleep(30)


def model_factory():
    import lightgbm as lgb

    return lgb.LGBMRegressor(**CONFIG)


def fit_control_once(
    source, checkpoints, factory=model_factory, resource_gate=wait_resources
):
    matrix = prepare_matrix(source, checkpoints)
    model_path, started = (
        checkpoints.root / "cue_net.txt",
        checkpoints.root / "fit_started.json",
    )
    if checkpoints.complete(
        "model", ["cue_net.txt", "fit_started.json", "matrix.complete.json"]
    ):
        source.recheck()
        return model_path
    require(
        not started.exists() and not model_path.exists(),
        "Interrupted fit preserved; no automatic refit/adoption",
    )
    resource_gate()
    source.recheck()
    atomic_json(
        started,
        dict(
            config=CONFIG,
            matrix_sha256=sha(matrix),
            targets_sha256=sha(checkpoints.root / "targets.npz"),
            started_utc=datetime.now(timezone.utc).isoformat(),
            width=len(vectors.COLUMN_NAMES),
            binding=checkpoints.binding,
        ),
    )
    x = np.load(matrix, mmap_mode="r")
    with np.load(checkpoints.root / "targets.npz", allow_pickle=False) as targets:
        y, weights = targets["y"], targets["weight"]
    model = factory()
    model.fit(x, y, sample_weight=weights)
    require(
        model.booster_.num_feature() == len(vectors.COLUMN_NAMES),
        "Trained model width differs",
    )
    temporary = model_path.with_name(model_path.name + ".partial-" + uuid.uuid4().hex)
    model.booster_.save_model(str(temporary))
    with temporary.open("r+b") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, model_path)
    source.recheck()
    checkpoints.finish(
        "model",
        [model_path, started, checkpoints.marker("matrix")],
        dict(
            config=CONFIG,
            original_control_model_refitted=False,
            cue_model_fit_completed=True,
        ),
    )
    return model_path


def main():
    parser = argparse.ArgumentParser()
    for name in (
        "original-root",
        "engine-root",
        "learner-audit",
        "engine-audit",
        "review",
        "out",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--stage", choices=("prepare", "fit"), default="prepare")
    args = parser.parse_args()
    code = dependencies()
    review = read_json(args.review)
    require(
        review.get("status") == "PASS_MARKET_CUE_CONTROL_IMPLEMENTATION_REVIEW"
        and review.get("dependencies") == code,
        "Exact implementation review required",
    )
    verify_review_authorities(review, args.learner_audit, args.engine_audit)
    output = args.out.resolve()
    require(
        not output.is_relative_to(args.original_root.resolve())
        and not output.is_relative_to(args.engine_root.resolve()),
        "Output must be separate from source roots",
    )
    with output_lock(output):
        source = OriginalInputs(
            args.original_root, args.engine_root, args.learner_audit, args.engine_audit
        )
        bind_code_snapshots(source, output, code)
        source.verify(args.review, sha(args.review))
        contract = dict(
            dependencies=code,
            authorities=review["authorities"],
            sources=source.hashes,
            config=CONFIG,
            schema=vectors.schema(),
            scales=source.scales,
            training_rows=len(source.sample),
            original_sample_reused=True,
            python=sys.version,
            packages={
                name: importlib.metadata.version(name)
                for name in ("numpy", "pandas", "lightgbm")
            },
        )
        path = output / "run_contract.json"
        if path.exists():
            require(read_json(path) == contract, "Run contract changed")
        else:
            atomic_json(path, contract)
        checkpoints = Checkpoints(output, sha(path))
        try:
            if args.stage == "fit":
                fit_control_once(source, checkpoints)
            else:
                prepare_matrix(source, checkpoints)
            source.recheck()
            require(dependencies() == code, "Implementation changed during stage")
            print(
                json.dumps(
                    dict(
                        status="COMPLETE_" + args.stage.upper(),
                        rows=len(source.sample),
                        width=len(vectors.COLUMN_NAMES),
                        validation_test_evaluated=False,
                    )
                ),
                flush=True,
            )
        except BaseException as error:
            atomic_json(
                output / ("failure_" + uuid.uuid4().hex + ".json"),
                dict(
                    stage=args.stage,
                    error=repr(error),
                    utc=datetime.now(timezone.utc).isoformat(),
                ),
            )
            raise


if __name__ == "__main__":
    main()
