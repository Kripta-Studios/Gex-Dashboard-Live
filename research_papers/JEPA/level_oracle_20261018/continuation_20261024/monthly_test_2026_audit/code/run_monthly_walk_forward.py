"""Monthly static/expanding/rolling replay. No market run is performed on import.

Requires the separately audited full+early-close dataset and implementation
review. Every month's predictions for all modes precede its outcome reads.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import shutil
import time
import uuid

import numpy as np
import pandas as pd

import train_causal_rollout as shared
import train_models as base
import rollout_sampling as sampling
import rolling_monthly_schedule as calendar
import monthly_policy_selection as selection

VERSION = "MONTHLY_NET_WALK_FORWARD_V1"
CONFIG = dict(shared.CONFIG)
TICKERS = calendar.TICKERS
DEPENDENCIES = (
    "run_monthly_walk_forward.py",
    "rolling_monthly_schedule.py",
    "monthly_policy_selection.py",
    "MONTHLY_WALK_FORWARD_PLAN.md",
    "rollout_sampling.py",
    "train_causal_rollout.py",
    "train_models.py",
    "features.py",
    "level_engine.py",
    "build_cache.py",
    "causal_rollout.py",
)
sha, read_json, atomic_json = shared.sha, shared.read_json, shared.atomic_json


def require(ok, message):
    if not bool(ok):
        raise ValueError(message)


def dependency_hashes():
    return {name: sha(Path(__file__).with_name(name)) for name in DEPENDENCIES}


def arrays_equal(left, right):
    return set(left) == set(right) and all(
        np.array_equal(left[k], right[k], equal_nan=True)
        if np.asarray(left[k]).dtype.kind in "fc"
        else np.array_equal(left[k], right[k])
        for k in left
    )


class Artifacts(shared.Artifacts):
    """Reject missing marker members and preserve unfinished derived artifacts."""

    def complete(self, name):
        if not super().complete(name):
            return False
        record = read_json(self.marker(name))
        require(bool(record["files"]), "Empty checkpoint")
        for relative in record["files"]:
            require(
                (self.root / relative).resolve().is_relative_to(self.root.resolve()),
                "Checkpoint path escapes output root",
            )
        for relative in record.get("extra", {}).get("source_manifests", []):
            require(
                (self.root / relative).resolve()
                in {(self.root / member).resolve() for member in record["files"]},
                "Unbound source manifest",
            )
            for path, digest in read_json(self.root / relative).items():
                require(
                    Path(path).is_absolute() and sha(path) == digest,
                    "Changed checkpoint source: " + path,
                )
        return True

    def require_members(self, name, paths):
        require(self.complete(name), "Incomplete checkpoint: " + name)
        record = read_json(self.marker(name))
        sealed = {(self.root / p).resolve() for p in record["files"]}
        require(
            {Path(p).resolve() for p in paths}.issubset(sealed),
            "Consumed file absent from checkpoint: " + name,
        )

    def preserve(self, name, paths):
        require(not self.marker(name).exists(), "Never move a completed checkpoint")
        root = self.root.resolve()
        for original in paths:
            original = Path(original).resolve()
            require(original.is_relative_to(root), "Orphan outside output root")
            if original.exists():
                destination = (
                    root
                    / "preserved_orphans"
                    / uuid.uuid4().hex
                    / original.relative_to(root)
                )
                require(
                    destination.resolve().is_relative_to(root),
                    "Preservation outside root",
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                original.rename(destination)

    def save_npz(self, name, arrays):
        path = self.root / (name + ".npz")
        if not self.complete(name):
            self.preserve(name, [path])
        result = super().save_npz(name, arrays)
        self.require_members(name, [result])
        return result

    def load_npz(self, name):
        self.require_members(name, [self.root / (name + ".npz")])
        return super().load_npz(name)

    def json(self, name, value=None):
        path = self.root / (name + ".json")
        if self.complete(name):
            self.require_members(name, [path])
            found = read_json(path)
            if value is not None:
                require(found == value, "Changed JSON checkpoint: " + name)
            return found
        require(value is not None, "Required JSON checkpoint absent: " + name)
        self.preserve(name, [path])
        atomic_json(path, value)
        self.finish(name, [path])
        return value


@dataclass(frozen=True)
class Day:
    ticker: str
    date: str
    oracle: Path
    features: Path
    close_i: int
    status: str
    feature_metadata: Path | None = None
    action_features: Path | None = None
    action_metadata: Path | None = None

    @property
    def feature_paths(self):
        return (
            self.features,
            self.feature_metadata or self.features.with_suffix(".json"),
            self.action_features or self.features.with_name("actions.npz"),
            self.action_metadata or self.features.with_name("actions.json"),
        )

    @property
    def key(self):
        return self.ticker + "/" + self.date

    @property
    def session(self):
        return calendar.Session(
            self.ticker,
            datetime.strptime(self.date, "%Y%m%d").date(),
            self.close_i,
            self.status,
        )


class Sources:
    """Read only action/label projections; never oracle values or trajectories."""

    def __init__(self, engine_root, feature_root, audit_path):
        self.root, self.feature_root = (
            Path(engine_root).resolve(),
            Path(feature_root).resolve(),
        )
        self.hashes = {}
        audit = read_json(audit_path)
        require(
            audit.get("status") == "PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT",
            "Full plus short-session independent dataset audit required",
        )
        binding = audit["binding"]
        require(
            Path(binding["engine_root"]).resolve() == self.root, "Wrong audited root"
        )
        for filename, field in (
            ("index.parquet", "index_sha256"),
            ("dataset_contract.json", "dataset_contract_sha256"),
            ("completion.json", "completion_sha256"),
        ):
            self.verify(self.root / filename, binding[field])
        require(
            read_json(self.root / "completion.json")["status"] == "COMPLETE",
            "Dataset incomplete",
        )
        require(
            binding["available_days"] == 2619 and binding["missing_days"] == 6,
            "Dataset audit excludes required sessions",
        )
        columns = [
            "ticker",
            "date",
            "status",
            "day_root",
            "close_i",
            "actions_sha256",
            "labels_sha256",
            "cache_npz_sha256",
            "cache_meta_sha256",
            "features_path",
            "features_meta_path",
            "action_features_path",
            "action_features_meta_path",
            "features_sha256",
            "features_meta_sha256",
            "action_features_sha256",
            "action_features_meta_sha256",
        ]
        raw = pd.read_parquet(self.root / "index.parquet", columns=columns)
        raw["date"] = raw.date.astype(str)
        self.index = raw.set_index(["ticker", "date"], verify_integrity=True)
        import exchange_calendars as xc

        schedule = xc.get_calendar("XNYS").schedule.loc["2023-01-03":"2026-06-30"]
        durations = (schedule.close - schedule.open) / pd.Timedelta(minutes=1)
        require(
            durations.isin([210, 390]).all() and len(schedule) == 875,
            "Unexpected session calendar",
        )
        expected_calendar = {
            stamp.date(): int(minutes) for stamp, minutes in durations.items()
        }
        self.days = {}
        for (ticker, day), record in self.index.iterrows():
            item = Day(
                ticker,
                day,
                Path(record.day_root)
                if record.status == "COMPLETE"
                else self.root / ticker / day,
                Path(record.features_path)
                if record.status == "COMPLETE"
                else self.feature_root / ticker / day / "features.npz",
                int(record.close_i),
                record.status,
                Path(record.features_meta_path)
                if record.status == "COMPLETE"
                else None,
                Path(record.action_features_path)
                if record.status == "COMPLETE"
                else None,
                Path(record.action_features_meta_path)
                if record.status == "COMPLETE"
                else None,
            )
            self.days[item.key] = item
        counts = calendar.require_session_universe(
            [d.session for d in self.days.values()],
            expected_calendar,
            date(2023, 1, 1),
            date(2026, 7, 1),
        )
        require(
            counts
            == dict(
                expected=2625,
                available=2619,
                missing_no_evaluable=6,
                early_close_ticker_days=24,
            ),
            "Full calendar counts differ",
        )
        missing = {
            (d.ticker, d.date)
            for d in self.days.values()
            if d.status == "MISSING_SOURCE"
        }
        require(
            missing
            == {
                (t, day)
                for t in ("SPY", "QQQ")
                for day in ("20260401", "20260409", "20260415")
            },
            "Missing calendar identities changed",
        )
        feature_contract = self.feature_root / "feature_contract.json"
        require(
            Path(binding["feature_root"]).resolve() == self.feature_root,
            "Wrong audited feature root",
        )
        self.verify(feature_contract, binding["feature_contract_sha256"])
        self.audit = dict(
            path=str(Path(audit_path).resolve()),
            sha256=sha(audit_path),
            binding=binding,
            coverage=counts,
            feature_contract_sha256=sha(feature_contract),
        )
        self.verify(Path(audit_path), self.audit["sha256"])

    def verify(self, path, digest):
        path = Path(path).resolve()
        require(sha(path) == digest, "Changed source: " + str(path))
        old = self.hashes.get(str(path))
        require(old is None or old == digest, "Source binding changed")
        self.hashes[str(path)] = digest

    def check(self, day, filename):
        require(
            filename in ("actions.parquet", "labels.parquet"),
            "Disallowed source sidecar",
        )
        row = self.index.loc[(day.ticker, day.date)]
        require(
            row.status == "COMPLETE"
            and Path(row.day_root).resolve() == day.oracle.resolve(),
            "Unavailable/mismatched source",
        )
        path = day.oracle / filename
        self.verify(path, row[Path(filename).stem + "_sha256"])
        return self.hashes[str(path.resolve())]

    def read(self, day, filename, columns=None):
        before = self.check(day, filename)
        frame = pd.read_parquet(day.oracle / filename, columns=columns)
        require(self.check(day, filename) == before, "Source changed during read")
        return frame

    def recheck(self):
        for path, digest in list(self.hashes.items()):
            self.verify(path, digest)


class Features(base.FeatureStore):
    """Reuse causal flattening; validate new-family dependency paths separately."""

    def __init__(self, source, artifacts):
        self.days = {d.key: d for d in source.days.values() if d.status == "COMPLETE"}
        self.cache, self.capacity = OrderedDict(), 2
        self.contract = read_json(source.feature_root / "feature_contract.json")
        require(
            self.contract.get("outcomes_read") is False,
            "Feature contract must be outcome-free",
        )
        self.source, self.artifacts = source, artifacts
        for name, digest in self.contract["dependencies"].items():
            producer = (Path(__file__).parent / name).resolve()
            require(
                producer.is_relative_to(Path(__file__).parent.resolve()),
                "Dependency escapes research family",
            )
            source.verify(producer, digest)
        import features

        self.action_inputs = features.ACTION_INPUT_NAMES
        expected = dict(
            base_names=list(features.BASE_NAMES),
            token_names=list(features.TOKEN_NAMES),
            map_names=list(features.MAP_NAMES),
            action_names=list(features.ACTION_NAMES),
        )
        require(
            all(
                self.contract["schema"][name] == values
                for name, values in expected.items()
            ),
            "Feature contract differs from exact causal whitelist",
        )

    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        day = self.days[key]
        self.source.check(day, "actions.parquet")
        files = day.feature_paths
        record = self.source.index.loc[(day.ticker, day.date)]
        fields = (
            "features_sha256",
            "features_meta_sha256",
            "action_features_sha256",
            "action_features_meta_sha256",
        )
        hashes = {str(p.resolve()): record[field] for p, field in zip(files, fields)}
        # The independent dataset audit binds these expected bytes before first use.
        for path, digest in hashes.items():
            require(sha(path) == digest, "Feature differs from audited index: " + path)
            self.source.verify(path, digest)
        self.artifacts.json("feature_inputs/" + key, hashes)
        for path in (files[1], files[3]):
            meta = read_json(path)
            require(
                meta.get("outcomes_read") is False
                and meta["binding"]["dependencies"] == self.contract["dependencies"],
                "Feature metadata is not bound to the causal producer",
            )
            require(
                meta["binding"]["source_sha256"] == record.cache_npz_sha256
                and meta["binding"]["source_metadata_sha256"]
                == record.cache_meta_sha256,
                "Feature cache source differs",
            )
        identity = self.source.read(
            day, "actions.parquet", ["action_id", *self.action_inputs]
        )
        digest = hashlib.sha256(
            identity.to_numpy(dtype=np.float64).tobytes()
        ).hexdigest()
        require(
            read_json(files[3])["binding"]["action_inputs_sha256"] == digest,
            "Action feature provenance differs",
        )
        metadata, action_metadata = read_json(files[1]), read_json(files[3])
        require(
            metadata["schema"] == self.contract["schema"]
            and action_metadata["action_names"]
            == self.contract["schema"]["action_names"],
            "Changing feature names/schema",
        )
        require(
            metadata["sha256"] == hashes[str(files[0].resolve())]
            and action_metadata["sha256"] == hashes[str(files[2].resolve())],
            "Feature arrays differ from metadata hashes",
        )
        with np.load(files[0], allow_pickle=False) as data:
            pack = {name: data[name] for name in data.files}
        with np.load(files[2], allow_pickle=False) as data:
            pack["action_ids"], pack["action_features"] = (
                data["action_id"],
                data["action_features"],
            )
        require(
            not identity.action_id.duplicated().any()
            and len(np.unique(pack["action_ids"])) == len(pack["action_ids"])
            and set(identity.action_id) == set(pack["action_ids"]),
            "Feature action universe changed",
        )
        lookup = identity.set_index("action_id").state_i
        pack["action_state_i"] = lookup.loc[pack["action_ids"]].to_numpy()
        for name in ("base_names", "token_names", "map_names", "action_names"):
            pack[name] = np.asarray(self.contract["schema"][name], dtype=str)
        pack["token_mask"] = np.stack((pack["token_mask"], pack["bar_mask"]), axis=-1)
        require(
            np.array_equal(pack["state_i"], np.arange(60, day.close_i - 14)),
            "Feature state horizon differs from session calendar",
        )
        require(
            pack["base"].shape[1] == 81
            and pack["tokens"].shape[1:] == (20, 45)
            and pack["maps"].shape[1:] == (20, 5, 64)
            and pack["map_mask"].shape[1:] == (20, 5)
            and pack["action_features"].shape[1] == 33,
            "Feature schema not B81/C45/A33",
        )
        pack["_action_index"] = pd.Index(pack["action_ids"])
        pack["_state_index"] = pd.Index(pack["state_i"])
        self.cache[key] = pack
        while len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
        return pack


def causal_sample(day, source, artifacts):
    actions = source.read(day, "actions.parquet", ["action_id", "state_i"])
    require(
        len(actions) > 0, "No offered actions: preserve day; do not silently exclude it"
    )
    require(
        actions.state_i.between(60, day.close_i - 15).all(),
        "Action outside day horizon",
    )
    sample = sampling.sample_day(
        day.ticker, day.date, actions.action_id.to_numpy(), actions.state_i.to_numpy()
    )
    arrays = {
        name: getattr(sample, name)
        for name in (
            "action_id",
            "state_i",
            "band_i",
            "identity_sha256",
            "weight",
            "population_by_band",
            "selected_by_band",
        )
    }
    name = "day_samples/" + day.key
    if artifacts.complete(name):
        require(arrays_equal(artifacts.load_npz(name), arrays), "Causal sample changed")
    else:
        artifacts.save_npz(name, arrays)
    return arrays


def aligned_labels(day, actions, labels):
    require(
        not actions.action_id.duplicated().any()
        and not labels.action_id.duplicated().any(),
        "Duplicated action/label identity",
    )
    require(len(actions) == len(labels), "Action/label count differs")
    indices = pd.Index(labels.action_id).get_indexer(actions.action_id)
    require(np.all(indices >= 0), "Missing action outcome")
    lab = labels.iloc[indices].reset_index(drop=True)
    states = actions.state_i.to_numpy()
    require(
        actions.state_i.dtype.kind in "iu"
        and np.all((states >= 60) & (states <= day.close_i - 15)),
        "Invalid action clocks",
    )
    require(
        lab.exit_i.dtype.kind in "iu" and lab.status.isin(["FILLED", "NO_FILL"]).all(),
        "Invalid outcome clocks/status",
    )
    fill = lab.status.to_numpy() == "FILLED"
    exits = lab.exit_i.to_numpy()
    require(
        np.all((exits[fill] >= states[fill] + 2) & (exits[fill] <= day.close_i - 5)),
        "Filled exit outside session",
    )
    require(np.all(exits[~fill] == states[~fill] + 1), "NO_FILL retry differs")
    for field in ("net_base", "net_adverse"):
        require(
            np.isfinite(lab[field]).all() and np.all(lab[field].to_numpy()[~fill] == 0),
            "Invalid economic payoff",
        )
    return lab


def training_chunk(day, fold, source, store, artifacts):
    require(
        fold.train_start <= day.session.day < fold.train_stop,
        "Training day outside window",
    )
    sample = causal_sample(day, source, artifacts)
    name = "day_chunks/" + day.key
    store.get(day.key)
    source.check(day, "labels.parquet")
    if artifacts.complete(name):
        chunk = artifacts.load_npz(name)
        require(
            np.array_equal(chunk["action_id"], sample["action_id"]),
            "Chunk identity changed",
        )
        return chunk, sample
    actions = source.read(day, "actions.parquet", ["action_id", "state_i"])
    labels = aligned_labels(day, actions, source.read(day, "labels.parquet"))
    ix = pd.Index(actions.action_id).get_indexer(sample["action_id"])
    selected = labels.iloc[ix]
    # Same-session physical exit bounds imply closure strictly before next-month cutoff.
    for state, exit_i, status in zip(
        sample["state_i"], selected.exit_i, selected.status
    ):
        calendar.require_training_row(
            fold,
            calendar.TrainingRowClock(
                day.session,
                day.session.clock(int(state)),
                day.session.clock(int(state)),
                day.session.clock(int(exit_i)),
                status,
            ),
        )
    x = shared.feature_rows(store, day.key, sample["action_id"])
    chunk = dict(
        action_id=sample["action_id"],
        x=x,
        net=selected.net_base.to_numpy(float),
        premium=selected.entry_ask.to_numpy(float) * 100,
        filled=(selected.status == "FILLED").to_numpy(),
        weight=sample["weight"],
    )
    artifacts.save_npz(name, chunk)
    return chunk, sample


def fit_window(fold, source, store, artifacts):
    key = fold.fit_key
    folder = artifacts.root / "fits" / key
    model_name = "models/" + key
    model_path = artifacts.root / (model_name + ".txt")
    info_name = "fits/" + key + "/inputs"
    if artifacts.complete(model_name):
        info = artifacts.json(info_name)
        require(
            info["fit_key"] == key and info["config"] == CONFIG,
            "Fit identity/config changed",
        )
        for path, digest in info["input_hashes"].items():
            source.verify(path, digest)
        artifacts.require_members(
            model_name, [model_path, model_path.with_suffix(".fit_started.json")]
        )
        booster = shared.lgb.Booster(model_file=str(model_path))
        require(booster.num_feature() == 1954, "Completed model width differs")
        return booster, info["scales"], sha(model_path)
    days = sorted(
        [
            d
            for d in source.days.values()
            if d.status == "COMPLETE"
            and fold.train_start <= d.session.day < fold.train_stop
        ],
        key=lambda d: d.key,
    )
    require(
        days and all(d.session.day < fold.evaluation_month for d in days),
        "Invalid training calendar",
    )
    chunk_info, weights, net, premium, filled, tickers = [], [], [], [], [], []
    for day in days:
        chunk, sample = training_chunk(day, fold, source, store, artifacts)
        chunk_info.append((day.key, len(chunk["net"])))
        weights.append(sample["weight"])
        net.append(chunk["net"])
        premium.append(chunk["premium"])
        filled.append(chunk["filled"])
        tickers.append(np.full(len(chunk["net"]), day.ticker))
    weights, net, premium, filled, tickers = map(
        np.concatenate, (weights, net, premium, filled, tickers)
    )
    require(
        np.isfinite(net).all() and np.isfinite(weights).all() and np.all(weights > 0),
        "Invalid targets/weights",
    )
    scales = {}
    for ticker in TICKERS:
        good = (tickers == ticker) & filled & np.isfinite(premium) & (premium > 0)
        require(good.any(), "No valid premium for training scale")
        scales[ticker] = base.weighted_median(premium[good], weights[good])
    fit_weight = weights * (len(weights) / len(days))
    target = net / np.array([scales[t] for t in tickers])
    arrays = dict(net=net, target=target, weight=fit_weight, ticker=tickers)
    arrays_name = "fits/" + key + "/targets"
    if artifacts.complete(arrays_name):
        require(
            arrays_equal(artifacts.load_npz(arrays_name), arrays),
            "Changed fit target arrays",
        )
    else:
        artifacts.save_npz(arrays_name, arrays)
    matrix_name = "fits/" + key + "/matrix"
    matrix_path = folder / "matrix.npy"
    if not artifacts.complete(matrix_name):
        artifacts.preserve(matrix_name, [matrix_path])
        folder.mkdir(parents=True, exist_ok=True)
        needed = len(net) * 1954 * 4 + 2 * 1024**3
        require(
            shutil.disk_usage(folder).free >= needed, "Insufficient matrix staging disk"
        )
        temp = matrix_path.with_name("matrix.partial-" + uuid.uuid4().hex)
        matrix = np.lib.format.open_memmap(
            temp, mode="w+", dtype=np.float32, shape=(len(net), 1954)
        )
        offset = 0
        for day_key, count in chunk_info:
            chunk = artifacts.load_npz("day_chunks/" + day_key)
            require(
                chunk["x"].shape == (count, 1954) and np.isfinite(chunk["x"]).all(),
                "Invalid matrix chunk",
            )
            matrix[offset : offset + count] = chunk["x"]
            offset += count
        matrix.flush()
        del matrix
        shared.durable_replace(temp, matrix_path)
        artifacts.finish(matrix_name, [matrix_path])
    artifacts.require_members(matrix_name, [matrix_path])
    matrix = np.load(matrix_path, mmap_mode="r", allow_pickle=False)
    require(
        matrix.shape == (len(net), 1954) and matrix.dtype == np.float32,
        "Matrix shape/precision",
    )
    # Bind only this fit's deterministic inputs, independent of previous runs/modes.
    input_hashes = {}
    for day in days:
        paths = [
            day.oracle / "actions.parquet",
            day.oracle / "labels.parquet",
            *day.feature_paths,
        ]
        for prefix in ("day_samples/", "day_chunks/", "feature_inputs/"):
            name = prefix + day.key
            marker = artifacts.marker(name)
            if marker.exists():
                require(artifacts.complete(name), "Training checkpoint incomplete")
                paths.append(marker)
                paths.extend(artifacts.root / p for p in read_json(marker)["files"])
        input_hashes.update({str(p.resolve()): sha(p) for p in paths})
    for name in (arrays_name, matrix_name):
        marker = artifacts.marker(name)
        input_hashes[str(marker.resolve())] = sha(marker)
        record = read_json(marker)
        input_hashes.update(
            {
                str((artifacts.root / p).resolve()): digest
                for p, digest in record["files"].items()
            }
        )
    info = dict(
        fit_key=key,
        train_start=fold.train_start.isoformat(),
        train_stop_exclusive=fold.train_stop.isoformat(),
        config=CONFIG,
        scales=scales,
        rows=len(net),
        ticker_days=len(days),
        input_hashes=input_hashes,
    )
    artifacts.json(info_name, info)
    model = shared.fit_once(key, matrix, target, fit_weight, artifacts)
    del matrix
    gc.collect()
    return model, scales, sha(model_path)


def rank_and_schedule(day, actions, labels, scores):
    require(
        np.asarray(scores).shape == (len(actions),) and np.isfinite(scores).all(),
        "Invalid scores",
    )
    order = np.lexsort(
        (actions.action_id.to_numpy(), -scores, actions.state_i.to_numpy())
    )
    choices = {}
    for row in order:
        minute = int(actions.state_i.iloc[row])
        if minute not in choices:
            choices[minute] = int(row) if scores[row] > 0 else -1
    lab = aligned_labels(day, actions, labels)
    selected, before = [], []
    minute, has_filled = 60, 0
    while minute <= day.close_i - 15:
        row = choices.get(minute, -1)
        if row < 0:
            minute += 1
            continue
        selected.append(row)
        before.append(has_filled)
        if lab.status.iloc[row] == "FILLED":
            has_filled = 1
            minute = int(lab.exit_i.iloc[row]) + 1
        else:
            minute += 1
    attempts = actions.iloc[selected].merge(
        lab.iloc[selected], on="action_id", validate="one_to_one"
    )
    attempts["score"] = scores[selected]
    attempts["has_filled_before"] = before
    return attempts, attempts.loc[attempts.status == "FILLED"].copy()


def predict_month(month, folds, fitted, source, store, artifacts):
    stamp = month.strftime("%Y%m")
    days = sorted(
        [d for d in source.days.values() if d.date.startswith(stamp)],
        key=lambda d: d.key,
    )
    require(days, "No calendar for evaluation month")
    keys = sorted({f.fit_key for f in folds})
    completed = []
    source_manifests = set()
    for key in keys:
        model, scales, model_hash = fitted[key]
        completed.extend(
            [
                artifacts.root / ("models/" + key + ".txt"),
                artifacts.marker("models/" + key),
                artifacts.root / ("fits/" + key + "/inputs.json"),
                artifacts.marker("fits/" + key + "/inputs"),
            ]
        )
        require(model.num_feature() == 1954, "Prediction model schema differs")
        for day in days:
            if day.status != "COMPLETE":
                continue
            name = "predictions/" + stamp + "/" + key + "/" + day.key
            actions = source.read(day, "actions.parquet", ["action_id", "state_i"])
            store.get(day.key)
            feature_name = "feature_inputs/" + day.key
            artifacts.json(feature_name)
            source_manifests.add(feature_name + ".json")
            completed.extend(
                [
                    artifacts.root / (feature_name + ".json"),
                    artifacts.marker(feature_name),
                ]
            )
            if artifacts.complete(name):
                pred = artifacts.load_npz(name)
                require(
                    str(pred["model_sha256"]) == model_hash
                    and float(pred["scale"]) == scales[day.ticker]
                    and np.array_equal(pred["action_id"], actions.action_id)
                    and np.array_equal(pred["state_i"], actions.state_i),
                    "Prediction binding changed",
                )
            else:
                scores = np.empty(len(actions), dtype=np.float64)
                for start in range(0, len(actions), 256):
                    ids = actions.action_id.iloc[start : start + 256].to_numpy()
                    x = shared.feature_rows(store, day.key, ids)
                    scores[start : start + len(ids)] = (
                        model.predict(x, num_threads=4) * scales[day.ticker]
                    )
                require(np.isfinite(scores).all(), "Nonfinite model prediction")
                artifacts.save_npz(
                    name,
                    dict(
                        action_id=actions.action_id.to_numpy(),
                        state_i=actions.state_i.to_numpy(),
                        scores=scores,
                        model_sha256=np.array(model_hash),
                        scale=np.array(scales[day.ticker]),
                    ),
                )
            completed.append(artifacts.root / (name + ".npz"))
    name = "months/" + stamp + "/predictions"
    if not artifacts.complete(name):
        artifacts.finish(
            name,
            completed,
            dict(
                fit_keys=keys,
                labels_read=False,
                source_manifests=sorted(source_manifests),
            ),
        )
    artifacts.require_members(name, completed)
    return days


def evaluate_month(month, folds, days, source, artifacts):
    stamp = month.strftime("%Y%m")
    require(
        artifacts.complete("months/" + stamp + "/predictions"),
        "All-mode monthly scores must be sealed first",
    )
    daily = {mode: [] for mode in calendar.MODES}
    economic, bound_paths = {}, [artifacts.marker("months/" + stamp + "/predictions")]
    for fold in folds:
        mode_ledgers = []
        for day in days:
            record = dict(
                ticker=day.ticker,
                date=day.date,
                source_status=day.status,
                trades=0,
                net_base=0.0,
                net_adverse=0.0,
            )
            if day.status == "COMPLETE":
                prefix = "ledgers/" + stamp + "/" + fold.mode + "/" + day.key
                attempt_path = artifacts.root / (prefix + "_attempts.parquet")
                ledger_path = artifacts.root / (prefix + "_ledger.parquet")
                if not artifacts.complete(prefix):
                    pred_name = (
                        "predictions/" + stamp + "/" + fold.fit_key + "/" + day.key
                    )
                    pred = artifacts.load_npz(pred_name)
                    actions = source.read(day, "actions.parquet")
                    require(
                        np.array_equal(pred["action_id"], actions.action_id),
                        "Prediction/action identity mismatch",
                    )
                    labels = source.read(day, "labels.parquet")
                    attempts, ledger = rank_and_schedule(
                        day, actions, labels, pred["scores"]
                    )
                    for frame in (attempts, ledger):
                        frame["ticker"], frame["date"], frame["mode"] = (
                            day.ticker,
                            day.date,
                            fold.mode,
                        )
                        frame["fit_key"] = fold.fit_key
                    artifacts.preserve(prefix, [attempt_path, ledger_path])
                    shared.save_parquet(attempt_path, attempts)
                    shared.save_parquet(ledger_path, ledger)
                    artifacts.finish(
                        prefix,
                        [attempt_path, ledger_path],
                        dict(
                            prediction_sha256=sha(artifacts.root / (pred_name + ".npz"))
                        ),
                    )
                artifacts.require_members(prefix, [attempt_path, ledger_path])
                ledger = pd.read_parquet(ledger_path)
                mode_ledgers.append(ledger)
                bound_paths.extend(
                    [attempt_path, ledger_path, artifacts.marker(prefix)]
                )
                record.update(
                    trades=len(ledger),
                    net_base=float(ledger.net_base.sum()),
                    net_adverse=float(ledger.net_adverse.sum()),
                )
            daily[fold.mode].append(record)
        full = (
            pd.concat(mode_ledgers, ignore_index=True)
            if mode_ledgers
            else pd.DataFrame(
                columns=[
                    "ticker",
                    "date",
                    "exit_i",
                    "net_base",
                    "net_adverse",
                    "hold_minutes",
                    "reason",
                ]
            )
        )
        full = full.sort_values(["date", "exit_i", "ticker"], kind="stable")
        economic[fold.mode] = dict(
            overall=shared.economic_summary(full),
            tickers={
                t: shared.economic_summary(full.loc[full.ticker == t]) for t in TICKERS
            },
        )
    economic_name = "months/" + stamp + "/economics"
    artifacts.json(economic_name, economic)
    daily_name = "months/" + stamp + "/daily"
    daily_path = artifacts.root / (daily_name + ".json")
    if artifacts.complete(daily_name):
        require(artifacts.json(daily_name) == daily, "Monthly daily data changed")
    else:
        artifacts.preserve(daily_name, [daily_path])
        atomic_json(daily_path, daily)
        bound_paths.extend(
            [
                daily_path,
                artifacts.root / (economic_name + ".json"),
                artifacts.marker(economic_name),
            ]
        )
        for relative in read_json(bound_paths[0])["files"]:
            bound_paths.append(artifacts.root / relative)
        artifacts.finish(
            daily_name,
            bound_paths,
            dict(
                source_manifests=read_json(bound_paths[0])["extra"]["source_manifests"]
            ),
        )
    return daily


def month_stage(month, source, store, artifacts):
    stamp = month.strftime("%Y%m")
    if month.year == 2026:
        artifacts.json("validation_freeze")
    name = "months/" + stamp + "/daily"
    folds = [f for f in calendar.build_schedule() if f.evaluation_month == month]
    if artifacts.complete(name):
        checked = set()
        for fold in folds:
            if fold.fit_key not in checked:
                require(
                    artifacts.complete("models/" + fold.fit_key),
                    "Completed month lost its model",
                )
                fit_window(fold, source, store, artifacts)
                checked.add(fold.fit_key)
        return artifacts.json(name)
    fitted = {}
    for fold in folds:
        if fold.fit_key not in fitted:
            fitted[fold.fit_key] = fit_window(fold, source, store, artifacts)
    days = predict_month(month, folds, fitted, source, store, artifacts)
    fitted.clear()
    gc.collect()
    return evaluate_month(month, folds, days, source, artifacts)


def freeze_validation(source, artifacts):
    common_key = calendar.build_schedule()[0].fit_key
    common_info = artifacts.json("fits/" + common_key + "/inputs")
    daily = {mode: [] for mode in calendar.MODES}
    inputs = {}
    for offset in range(12):
        month = calendar.month_shift(calendar.EVALUATION_START, offset)
        name = "months/" + month.strftime("%Y%m") + "/daily"
        values = artifacts.json(name)
        inputs[str(artifacts.root / (name + ".json"))] = sha(
            artifacts.root / (name + ".json")
        )
        for mode in calendar.MODES:
            daily[mode].extend(values[mode])
    expected = {
        (d.ticker, d.date) for d in source.days.values() if d.date.startswith("2025")
    }
    result = selection.select_monthly_mode(daily, expected, common_info["scales"])
    result.update(
        common_scale_fit=common_key,
        common_scales=common_info["scales"],
        validation_input_hashes=inputs,
        update_rule="FROZEN_CALENDAR_STATIC_EXPANDING_ROLLING12",
        outcomes_2026_used_for_mode_selection=False,
    )
    if not artifacts.complete("validation_freeze"):
        require(
            not any((artifacts.root / "predictions").glob("2026*")),
            "Test evidence exists without a verified selection freeze",
        )
    artifacts.json("validation_freeze", result)
    return result


def period_report(year, source, artifacts):
    """Observed economics and calendar coverage are separate research conclusions."""
    require(year in (2025, 2026), "Unexpected reporting period")
    expected = {
        (d.ticker, d.date): d
        for d in source.days.values()
        if d.date.startswith(str(year))
    }
    records = {mode: [] for mode in calendar.MODES}
    frames = {mode: [] for mode in calendar.MODES}
    columns = [
        "ticker",
        "date",
        "exit_i",
        "net_base",
        "net_adverse",
        "hold_minutes",
        "reason",
    ]
    for month in range(1, 13 if year == 2025 else 7):
        stamp = f"{year}{month:02d}"
        daily = artifacts.json("months/" + stamp + "/daily")
        for mode in calendar.MODES:
            records[mode].extend(daily[mode])
            for row in daily[mode]:
                if row["source_status"] == "COMPLETE":
                    prefix = (
                        "ledgers/"
                        + stamp
                        + "/"
                        + mode
                        + "/"
                        + row["ticker"]
                        + "/"
                        + row["date"]
                    )
                    path = artifacts.root / (prefix + "_ledger.parquet")
                    artifacts.require_members(prefix, [path])
                    frames[mode].append(pd.read_parquet(path, columns=columns))

    def summarize(rows, ledger):
        available = [row for row in rows if row["source_status"] == "COMPLETE"]
        missing = len(rows) - len(available)
        active = sum(row["trades"] > 0 for row in available)
        zero = len(available) - active
        economy = shared.economic_summary(ledger)
        require(
            economy["trades"] == sum(row["trades"] for row in available)
            and np.isclose(
                economy["net_base"], sum(row["net_base"] for row in available)
            )
            and np.isclose(
                economy["net_adverse"], sum(row["net_adverse"] for row in available)
            ),
            "Period ledger differs from daily records",
        )
        return dict(
            expected_ticker_days=len(rows),
            available_ticker_days=len(available),
            missing_no_evaluable=missing,
            available_days_with_fill=active,
            available_days_without_fill=zero,
            observable_daily_pass=bool(available) and zero == 0,
            full_calendar_daily_status=(
                "NO_EVALUABLE_MISSING_SOURCE"
                if missing
                else "PASS"
                if available and zero == 0
                else "FAIL_OBSERVED_ZERO"
            ),
            daily_requirement_satisfied=bool(available) and missing == 0 and zero == 0,
            available_economics=economy,
            net_base_per_available_day=economy["net_base"] / len(available)
            if available
            else None,
            missing_day_economics=None,
        )

    modes = {}
    for mode in calendar.MODES:
        rows = records[mode]
        keys = [(row["ticker"], row["date"]) for row in rows]
        require(
            len(keys) == len(set(keys)) and set(keys) == set(expected),
            "Period report omits or duplicates calendar identities",
        )
        require(
            all(
                row["source_status"] == expected[(row["ticker"], row["date"])].status
                for row in rows
            ),
            "Period report source status changed",
        )
        ledger = (
            pd.concat(frames[mode], ignore_index=True)
            if frames[mode]
            else pd.DataFrame(columns=columns)
        )
        ledger = ledger.sort_values(["date", "exit_i", "ticker"], kind="stable")
        modes[mode] = dict(
            overall=summarize(rows, ledger),
            tickers={
                ticker: summarize(
                    [row for row in rows if row["ticker"] == ticker],
                    ledger.loc[ledger.ticker == ticker],
                )
                for ticker in TICKERS
            },
        )
    result = dict(
        year=year,
        modes=modes,
        selected_mode=artifacts.json("validation_freeze")["selected_mode"],
        selection_period=2025,
        development_seen=True,
        promotion_approved=False,
        missing_sources_are_not_observed_losses=True,
    )
    return artifacts.json("reports/" + str(year), result)


def run_stages(stage, source, store, artifacts):
    if not artifacts.complete("validation_freeze"):
        require(
            not any((artifacts.root / "predictions").glob("2026*")),
            "Test evidence without verified validation freeze",
        )
    if stage == "prepare":
        for day in sorted(source.days.values(), key=lambda d: d.key):
            if day.status == "COMPLETE":
                causal_sample(day, source, artifacts)
        return
    if stage in ("validation", "all"):
        for offset in range(12):
            month_stage(
                calendar.month_shift(calendar.EVALUATION_START, offset),
                source,
                store,
                artifacts,
            )
        freeze_validation(source, artifacts)
        period_report(2025, source, artifacts)
    if stage in ("test", "all"):
        freeze_validation(
            source, artifacts
        )  # Reproduce only the frozen 2025 selection.
        for offset in range(12, 18):
            month_stage(
                calendar.month_shift(calendar.EVALUATION_START, offset),
                source,
                store,
                artifacts,
            )
        period_report(2025, source, artifacts)
        period_report(2026, source, artifacts)
        artifacts.json(
            "completion",
            dict(
                status="COMPLETE",
                modes=list(calendar.MODES),
                evaluated_months=18,
                unique_fit_windows=36,
                selected_mode=artifacts.json("validation_freeze")["selected_mode"],
                development_seen=True,
                promotion_approved=False,
                report_hashes={
                    str(year): sha(artifacts.root / ("reports/" + str(year) + ".json"))
                    for year in (2025, 2026)
                },
            ),
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-root", type=Path, required=True)
    parser.add_argument("--feature-root", type=Path, required=True)
    parser.add_argument("--source-audit", type=Path, required=True)
    parser.add_argument("--implementation-review", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--stage", choices=("prepare", "validation", "test", "all"), default="prepare"
    )
    args = parser.parse_args()
    args.out = args.out.resolve()
    require(
        args.out not in (args.engine_root.resolve(), args.feature_root.resolve())
        and not args.out.is_relative_to(args.engine_root.resolve())
        and not args.out.is_relative_to(args.feature_root.resolve()),
        "Use a separate output root",
    )
    args.out.mkdir(parents=True, exist_ok=True)
    with shared.exclusive_lock(args.out / "run.lock"):
        dependencies = dependency_hashes()
        if args.stage != "prepare":
            require(
                args.implementation_review is not None,
                "Implementation review required before outcomes/fits",
            )
            review = read_json(args.implementation_review)
            require(
                review.get("status")
                == "PASS_MONTHLY_WALK_FORWARD_IMPLEMENTATION_REVIEW"
                and review.get("dependencies") == dependencies,
                "Implementation review binding differs",
            )
        source = Sources(args.engine_root, args.feature_root, args.source_audit)
        contract = dict(
            version=VERSION,
            dependencies=dependencies,
            source_audit=source.audit,
            engine_root=str(args.engine_root.resolve()),
            feature_root=str(args.feature_root.resolve()),
            config=CONFIG,
            seed=20261018,
            threshold_usd=0.0,
            features=1954,
            common_ranking_scale="static_train_2023_2024",
            calendar_expected=2625,
            software=dict(
                numpy=np.__version__,
                pandas=pd.__version__,
                lightgbm=shared.lgb.__version__,
            ),
        )
        path = args.out / "run_contract.json"
        if path.exists():
            require(read_json(path) == contract, "Resume contract differs")
        else:
            atomic_json(path, contract)
        for name, digest in dependencies.items():
            snapshot = args.out / "executed_code" / name
            if snapshot.exists():
                require(sha(snapshot) == digest, "Executed code changed")
            else:
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                temporary = snapshot.with_name(
                    snapshot.name + ".partial-" + uuid.uuid4().hex
                )
                temporary.write_bytes(Path(__file__).with_name(name).read_bytes())
                require(sha(temporary) == digest, "Code changed while copying")
                shared.durable_replace(temporary, snapshot)
        artifacts = Artifacts(args.out, sha(path))
        store = Features(source, artifacts)
        started = time.monotonic()
        try:
            run_stages(args.stage, source, store, artifacts)
            source.recheck()
            require(
                dependency_hashes() == dependencies and sha(path) == artifacts.binding,
                "Dependencies/contract changed during replay",
            )
        except Exception as exc:
            atomic_json(
                args.out / ("failure_" + uuid.uuid4().hex + ".json"),
                dict(
                    error=repr(exc),
                    stage=args.stage,
                    utc=datetime.now(timezone.utc).isoformat(),
                ),
            )
            raise
        print(
            json.dumps(
                dict(
                    stage=args.stage,
                    status="COMPLETE",
                    seconds=time.monotonic() - started,
                )
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
