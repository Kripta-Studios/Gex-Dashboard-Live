"""Build exact152+272 TRAIN features only; no fitting, outcomes or test loader."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

import common_greek_dynamics as dynamic
import run_market_cue_diagnostic as hash_source
import train_market_cue_control as checkpoint

PINNED = {
    "run_contract.json": "ea296e2de576b91594697579c3f642e251526224213a651fbf6fbb409addf534",
    "matrix.complete.json": "dc12c6a194c535e5c12ac3319ea592c6de6f03608e13a08919c4bb4440ae31e2",
    "model.complete.json": "9d5e0bbc5744fbdbf909e4f43c11796b9aa42c418cfcf7c0e85018a82783f97a",
}
KEY_COLUMNS = [
    "sample_i",
    "day_key",
    "ticker",
    "date",
    "action_id",
    "state_i",
    "weight",
]
RAW_KEYS = (
    "time_ns",
    "spot",
    "spot_valid",
    "strike",
    "right",
    "row_flags",
    "iv",
    "delta",
    "vega",
    "theta",
    "oi_contract_idx",
    "oi_available_ns",
    "oi_value",
    "oi_valid",
)
sha, read_json, require = checkpoint.sha, checkpoint.read_json, checkpoint.require


def sync_file(path):
    with Path(path).open("r+b") as handle:
        os.fsync(handle.fileno())


def separate_output(output, sources):
    output = Path(output).resolve()
    for path in sources:
        source = Path(path).resolve()
        require(
            not output.is_relative_to(source) and not source.is_relative_to(output),
            "Output must be separate from all source roots",
        )


class Inputs:
    def __init__(
        self,
        cue,
        learner,
        engine,
        cache,
        learner_audit,
        engine_audit,
        *,
        pins=None,
        expected_rows=270377,
    ):
        self.cue, self.learner, self.engine, self.cache = (
            Path(p).resolve() for p in (cue, learner, engine, cache)
        )
        self.hashes = {}
        for name, digest in (PINNED if pins is None else pins).items():
            self.verify(self.cue / name, digest)
        contract = read_json(self.cue / "run_contract.json")
        self.control_contract = contract
        self.contract_sha = sha(self.cue / "run_contract.json")
        matrix, model = (
            read_json(self.cue / name)
            for name in ("matrix.complete.json", "model.complete.json")
        )
        self.matrix_sources = matrix["extra"]["source_hashes"]
        for record in (matrix, model):
            require(
                record["status"] == "COMPLETE"
                and record["binding"] == self.contract_sha,
                "Control completion binding differs",
            )
        self.verify(self.cue / "train_x.npy", matrix["files"]["train_x.npy"])
        self.verify(self.cue / "cue_net.txt", model["files"]["cue_net.txt"])
        self.verify(
            self.cue / "matrix.complete.json", model["files"]["matrix.complete.json"]
        )
        for path, field in (
            (learner_audit, "learner_audit_sha256"),
            (engine_audit, "engine_audit_sha256"),
        ):
            self.verify(path, contract["authorities"][field])
        audit, oracle = read_json(learner_audit), read_json(engine_audit)
        require(
            audit["status"] == "PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT"
            and oracle["status"] == "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT",
            "Full original audits required",
        )
        require(
            Path(audit["binding"]["learner_root"]).resolve() == self.learner
            and Path(oracle["binding"]["engine_root"]).resolve() == self.engine,
            "Wrong authority root",
        )
        self.verify(self.learner / "freeze.json", audit["binding"]["freeze_sha256"])
        frozen = read_json(self.learner / "freeze.json")
        self.verify(
            self.learner / "training_sample.parquet",
            frozen["artifacts"]["training_sample.parquet"],
        )
        self.verify(self.engine / "index.parquet", oracle["binding"]["index_sha256"])
        for path in (
            self.learner / "training_sample.parquet",
            self.engine / "index.parquet",
        ):
            require(
                contract["sources"].get(str(path)) == self.hashes[str(path)],
                "Control refers to different sample/index",
            )
        self.sample = pd.read_parquet(
            self.learner / "training_sample.parquet", columns=KEY_COLUMNS
        )
        self.sample["date"] = self.sample.date.astype(str)
        require(
            len(self.sample) == expected_rows
            and np.array_equal(self.sample.sample_i, np.arange(expected_rows)),
            "Exact original sample order/count required",
        )
        require(
            not self.sample.duplicated(["day_key", "action_id"]).any(),
            "Duplicate action IDs",
        )
        require(
            self.sample.date.str[:4].isin(["2023", "2024"]).all()
            and self.sample.state_i.between(60, 375).all(),
            "Only complete-session TRAIN states allowed",
        )
        require(
            (self.sample.day_key == self.sample.ticker + "/" + self.sample.date).all(),
            "Sample day key mismatch",
        )
        require(
            np.isfinite(self.sample.weight).all()
            and (self.sample.weight > 0).all()
            and np.isclose(self.sample.weight.mean(), 1.0, atol=1e-12),
            "Original mean-one positive IPW required",
        )
        self.index = pd.read_parquet(
            self.engine / "index.parquet",
            columns=[
                "ticker",
                "date",
                "status",
                "cache_path",
                "cache_npz_sha256",
                "cache_meta_sha256",
            ],
        )
        self.index["date"] = self.index.date.astype(str)
        self.index = self.index.set_index(["ticker", "date"], verify_integrity=True)
        self.base = np.load(self.cue / "train_x.npy", mmap_mode="r", allow_pickle=False)
        require(
            self.base.shape == (expected_rows, 152) and self.base.dtype == np.float32,
            "Control matrix shape/dtype mismatch",
        )
        self.schema = contract["schema"]["column_names"]
        require(len(self.schema) == 152, "Control schema width differs")

    def verify(self, path, digest):
        path = Path(path).resolve()
        require(sha(path) == digest, "Source differs from authority: " + str(path))
        require(
            str(path) not in self.hashes or self.hashes[str(path)] == digest,
            "Source authority changed",
        )
        self.hashes[str(path)] = digest

    def recheck(self):
        for path, digest in list(self.hashes.items()):
            self.verify(path, digest)

    def day(self, key, rows):
        ticker, date = key.split("/")
        require(date[:4] in ("2023", "2024"), "Cannot read validation/test")
        record = self.index.loc[(ticker, date)]
        require(record.status == "COMPLETE", "Source day not complete")
        source = self.cache / ticker / (date + ".npz")
        require(Path(record.cache_path).resolve() == source, "Wrong raw cache path")
        metadata = source.with_suffix(".json")
        self.verify(source, record.cache_npz_sha256)
        self.verify(metadata, record.cache_meta_sha256)
        meta = read_json(metadata)
        require(
            meta["ticker"] == ticker
            and str(meta["date"]) == date
            and meta["sha256"] == record.cache_npz_sha256,
            "Cache identity mismatch",
        )
        marker = self.cue / ("chunks/" + key + ".complete.json")
        control_chunk = self.cue / ("chunks/" + key + ".npz")
        control = read_json(marker)
        require(
            control["status"] == "COMPLETE" and control["binding"] == self.contract_sha,
            "Control chunk binding differs",
        )
        relative = str(control_chunk.relative_to(self.cue))
        self.verify(control_chunk, control["files"][relative])
        # The source map must match prior authority; exact sample+sealed-matrix
        # equality below independently binds the consumed chunk values/order.
        for p, digest in control["extra"]["source_hashes"].items():
            require(
                self.matrix_sources.get(p) == digest,
                "Control chunk source differs from completed matrix",
            )
        with np.load(control_chunk, allow_pickle=False) as chunk:
            for name in ("sample_i", "action_id", "state_i"):
                require(
                    np.array_equal(chunk[name], rows[name].to_numpy()),
                    "Control chunk sample identity differs",
                )
            prefix = np.asarray(self.base[rows.sample_i.to_numpy()])
            require(
                np.array_equal(chunk["x"].view(np.uint32), prefix.view(np.uint32)),
                "Control prefix not byte-identical to original chunk",
            )
        with np.load(source, allow_pickle=False) as loaded:
            raw = {name: loaded[name] for name in RAW_KEYS}
        sources = {
            str(path): self.hashes[str(path)]
            for path in (source, metadata, control_chunk)
        }
        sources[str(marker)] = sha(marker)
        self.verify(marker, sources[str(marker)])
        return prefix, raw, sources


def prepare(source, evidence):
    if evidence.complete("matrix", ["train_x.npy", "row_keys.npz", "coverage.json"]):
        for path, digest in read_json(evidence.marker("matrix"))["extra"][
            "sources"
        ].items():
            source.verify(path, digest)
        return
    chunks = []
    for key, rows in source.sample.groupby("day_key", sort=True):
        name = "chunks/" + key
        destination = evidence.root / (name + ".npz")
        relative = str(destination.relative_to(evidence.root))
        if evidence.complete(name, [relative]):
            record = read_json(evidence.marker(name))
            for path, digest in record["extra"]["sources"].items():
                source.verify(path, digest)
        else:
            prefix, raw, sources = source.day(key, rows)
            day = dynamic.prepare_day(raw, close_i=390)
            added = dynamic.encode_states(day, rows.state_i.to_numpy())
            combined = dynamic.append_to_compact(prefix, added)
            evidence.preserve(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                np.savez_compressed(
                    handle,
                    sample_i=rows.sample_i.to_numpy(),
                    action_id=rows.action_id.to_numpy(),
                    state_i=rows.state_i.to_numpy(),
                    weight=rows.weight.to_numpy(),
                    x=combined,
                )
            sync_file(destination)
            evidence.finish(name, [destination], {"sources": sources})
        chunks.append((destination, rows))
        if len(chunks) % 100 == 0:
            print(f"Completed TRAIN feature days: {len(chunks)}", flush=True)
    matrix = evidence.root / "train_x.npy"
    evidence.preserve(matrix)
    x = np.lib.format.open_memmap(
        matrix, mode="w+", dtype=np.float32, shape=(len(source.sample), 424)
    )
    sums = {
        key: np.zeros(272, dtype=np.float64)
        for key in ("actions", "ipw", "unique_states")
    }
    denominators = dict(actions=0, ipw=0.0, unique_states=0)
    for path, rows in chunks:
        require(
            evidence.complete(
                "chunks/" + rows.day_key.iloc[0], [str(path.relative_to(evidence.root))]
            ),
            "Chunk changed during assembly",
        )
        with np.load(path, allow_pickle=False) as chunk:
            for field in ("sample_i", "action_id", "state_i", "weight"):
                require(
                    np.array_equal(chunk[field], rows[field].to_numpy()),
                    "Output chunk identity/IPW mismatch",
                )
            require(
                chunk["x"].shape == (len(rows), 424) and np.isfinite(chunk["x"]).all(),
                "Invalid feature shape",
            )
            require(
                np.array_equal(
                    chunk["x"][:, :152].view(np.uint32),
                    source.base[rows.sample_i.to_numpy()].view(np.uint32),
                ),
                "Original prefix changed",
            )
            x[rows.sample_i.to_numpy()] = chunk["x"]
            added = chunk["x"][:, 152:].astype(float)
            distinct = ~rows.duplicated("state_i").to_numpy()
            for label, weight in (
                ("actions", np.ones(len(rows))),
                ("ipw", rows.weight.to_numpy()),
                ("unique_states", distinct.astype(float)),
            ):
                sums[label] += (added * weight[:, None]).sum(axis=0)
                denominators[label] += weight.sum()
    x.flush()
    del x
    sync_file(matrix)
    keys = evidence.root / "row_keys.npz"
    evidence.preserve(keys)
    with keys.open("xb") as handle:
        np.savez_compressed(
            handle,
            **{
                name: source.sample[name].to_numpy(
                    dtype=str if name in ("ticker", "date", "day_key") else None
                )
                for name in KEY_COLUMNS
            },
        )
    sync_file(keys)
    coverage = evidence.root / "coverage.json"
    evidence.preserve(coverage)
    checkpoint.atomic_json(
        coverage,
        {
            "denominators": denominators,
            "includes_explicit_zero_placeholders": True,
            "means": {
                name: dict(
                    zip(dynamic.FEATURE_NAMES, (value / denominators[name]).tolist())
                )
                for name, value in sums.items()
            },
        },
    )
    source.recheck()
    evidence.finish(
        "matrix",
        [matrix, keys, coverage],
        {"sources": source.hashes, "new_fits": 0, "outcomes_read": False},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "cue",
        "learner",
        "engine",
        "cache",
        "learner-audit",
        "engine-audit",
        "review",
        "out",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    separate_output(args.out, [args.cue, args.learner, args.engine, args.cache])
    review_sha = sha(args.review)
    review = read_json(args.review)
    require(sha(args.review) == review_sha, "Review changed while reading")
    require(
        review["status"] == "PASS_COMMON_GREEK_TRAIN_BUILDER_REVIEW",
        "Exact implementation review required",
    )
    dependencies = [
        Path(__file__),
        Path(dynamic.__file__),
        Path(checkpoint.__file__),
        Path(hash_source.__file__),
        Path(dynamic.engine.__file__),
        Path(__file__).with_name("COMMON_GREEK_DYNAMICS_V1_DESIGN.md"),
        Path(__file__).with_name("COMMON_GREEK_TRAIN_BUILDER_SPEC.md"),
        Path(__file__).with_name("COMMON_GREEK_DYNAMICS_V1_LEARNER_PLAN.md"),
        Path(__file__).with_name("GREEK_UNITS_REVIEW.md"),
    ]
    for path in dependencies:
        require(
            review["files"].get(path.name) == sha(path),
            "Unreviewed implementation dependency: " + path.name,
        )
    with checkpoint.output_lock(args.out):
        source = Inputs(
            args.cue,
            args.learner,
            args.engine,
            args.cache,
            args.learner_audit,
            args.engine_audit,
        )
        for path in [*dependencies, args.review]:
            expected = review_sha if path == args.review else review["files"][path.name]
            prior = source.control_contract.get("sources", {}).get(str(path.resolve()))
            if prior is not None:
                require(
                    expected == prior,
                    "Original control dependency differs: " + path.name,
                )
            source.verify(path, expected)
            destination = args.out / (path.name + ".snapshot")
            if destination.exists():
                require(sha(destination) == expected, "Snapshot changed")
            else:
                temporary = destination.with_name(destination.name + ".partial")
                checkpoint.Checkpoints(args.out, "snapshot-only").preserve(temporary)
                shutil.copyfile(path, temporary)
                require(sha(temporary) == expected, "Snapshot copy differs")
                sync_file(temporary)
                temporary.replace(destination)
            source.verify(destination, expected)
        contract = {
            "sources": source.hashes,
            "columns": source.schema + list(dynamic.FEATURE_NAMES),
            "rows": len(source.sample),
            "fit_authorized": False,
            "train_only": True,
            "close_i": 390,
        }
        contract_path = args.out / "run_contract.json"
        if contract_path.exists():
            require(read_json(contract_path) == contract, "Run binding differs")
        else:
            checkpoint.atomic_json(contract_path, contract)
        prepare(source, checkpoint.Checkpoints(args.out, sha(contract_path)))


if __name__ == "__main__":
    main()
