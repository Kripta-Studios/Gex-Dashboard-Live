"""Bounded causal learners; the frozen research contract is LEARNER_PLAN.md.

Only feature packs and causal action IDs enter prediction. Economic sidecars are
opened by separate fitting/evaluation functions. No market fit before oracle PASS.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import torch
from torch import nn
from torch.nn import functional as F

SEED = 20261018
TICKERS = ("SPXW", "SPY", "QQQ")
MODELS = ("gbt_net", "gbt_advantage", "tcn_teacher")
THRESHOLDS = (0.0, 5.0, 10.0)
STRATUM_CAP = 250_000
EPOCHS = 4
BATCH = 1024
FORBIDDEN_FEATURES = frozenset(
    (
        "net_base",
        "net_adverse",
        "exit_i",
        "entry_ask",
        "exit_bid",
        "hold_minutes",
        "trigger_i",
        "reason",
        "dp_advantage",
        "q_value",
        "wait_value",
        "teacher_selected",
        "state_optimal_action",
        "status",
        "contract_i",
        "action_id",
        "entry_level_id",
        "target_level_id",
        "stop_level_id",
        "n_contracts",
    )
)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2, allow_nan=False, default=str), encoding="utf-8"
    )


def import_sibling(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve their defining module through sys.modules.
    import sys

    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def row_priority(ticker, date, action_ids):
    """Vector SplitMix64 of day SHA256 xor action ID; independent of outcomes."""
    salt = int.from_bytes(
        hashlib.sha256(f"{SEED}|{ticker}|{date}".encode()).digest()[:8], "big"
    )
    with np.errstate(over="ignore"):
        x = np.asarray(action_ids, dtype=np.uint64) ^ np.uint64(salt)
        x = x + np.uint64(0x9E3779B97F4A7C15)
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        return x ^ (x >> np.uint64(31))


def bounded_lowest(frame, cap):
    if len(frame) <= cap:
        return frame
    values = frame.priority.to_numpy(np.uint64)
    chosen = np.argpartition(values, cap - 1)[:cap]
    boundary = values[chosen].max()
    strictly = np.flatnonzero(values < boundary)
    ties = frame.iloc[np.flatnonzero(values == boundary)].sort_values(
        ["day_key", "action_id"]
    )
    return pd.concat(
        [frame.iloc[strictly], ties.iloc[: cap - len(strictly)]], ignore_index=True
    )


def weighted_median(values, weights):
    values, weights = np.asarray(values, float), np.asarray(weights, float)
    valid = np.isfinite(values) & (values > 0) & np.isfinite(weights) & (weights > 0)
    if not valid.any():
        raise ValueError("No positive finite training risk scale observations")
    order = np.argsort(values[valid], kind="stable")
    v, w = values[valid][order], weights[valid][order]
    return float(v[np.searchsorted(np.cumsum(w), w.sum() / 2, side="left")])


@dataclass(frozen=True)
class Day:
    ticker: str
    date: str
    oracle: Path
    features: Path

    @property
    def key(self):
        return self.ticker + "/" + self.date


def discover_days(oracle_root, feature_root):
    result = []
    for ticker in TICKERS:
        for path in sorted((Path(oracle_root) / ticker).glob("*/actions.parquet")):
            date = path.parent.name
            if (
                len(date) != 8
                or not date.isdigit()
                or not "20230101" <= date < "20260701"
            ):
                continue
            result.append(
                Day(
                    ticker,
                    date,
                    path.parent,
                    Path(feature_root) / ticker / date / "features.npz",
                )
            )
    if not result:
        raise ValueError("No declared oracle days")
    return result


def verify_full_coverage(days, out):
    import exchange_calendars as xc

    calendar = xc.get_calendar("XNYS").schedule.loc["2023-01-01":"2026-06-30"]
    full = calendar.loc[
        (calendar["close"] - calendar["open"]) == pd.Timedelta(hours=6, minutes=30)
    ]
    dates = full.index.strftime("%Y%m%d").tolist()
    missing = {
        (ticker, date)
        for ticker in ("SPY", "QQQ")
        for date in ("20260401", "20260409", "20260415")
    }
    expected = {(ticker, date) for ticker in TICKERS for date in dates} - missing
    actual = {(d.ticker, d.date) for d in days}
    if len(days) != len(actual) or actual != expected:
        raise ValueError(
            f"Incomplete/different full declared learner universe: missing={sorted(expected - actual)[:20]}, extra={sorted(actual - expected)[:20]}"
        )
    unavailable_features = [
        str(d.features)
        for d in days
        if not all(
            (d.features.parent / name).exists()
            for name in ("features.npz", "features.json", "actions.npz", "actions.json")
        )
    ]
    if unavailable_features:
        raise ValueError(
            "Incomplete causal feature/action caches: "
            + repr(unavailable_features[:10])
        )
    pd.DataFrame({"date": dates}).to_csv(
        out / "expected_full_calendar.csv", index=False
    )
    write_json(
        out / "coverage.json",
        {
            "expected_full_days_per_ticker": len(dates),
            "processed_day_keys": len(days),
            "known_missing_greek_days": sorted(missing),
            "silent_other_exclusions": 0,
            "calendar_version": xc.__version__,
        },
    )


def require_oracle_pass(path, oracle_root):
    audit = json.loads(Path(path).read_text(encoding="utf-8"))
    if audit.get("status") != "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT":
        raise ValueError(
            "An exact independent FULL oracle PASS is required before market fitting"
        )
    root = Path(oracle_root).resolve()
    binding = audit["binding"]
    if Path(binding["engine_root"]).resolve() != root:
        raise ValueError("Full audit belongs to a different engine root")
    contract = json.loads((root / "dataset_contract.json").read_text(encoding="utf-8"))
    completion = json.loads((root / "completion.json").read_text(encoding="utf-8"))
    if completion["status"] != "COMPLETE":
        raise ValueError("Oracle dataset is not complete")
    cache_root = Path(contract["cache_root"]).resolve()
    files = {
        "completion_sha256": root / "completion.json",
        "index_sha256": root / "index.parquet",
        "dataset_contract_sha256": root / "dataset_contract.json",
        "cache_contract_sha256": cache_root / "cache_contract.json",
        "cache_full_summary_sha256": cache_root / "full_summary.json",
        "engine_sha256": Path(__file__).with_name("level_engine.py"),
        "engine_runner_sha256": Path(__file__).with_name("run_engine_dataset.py"),
    }
    verified = {str(Path(path).resolve()): sha(path)}
    for key, source in files.items():
        digest = sha(source)
        if binding.get(key) != digest:
            raise ValueError("Full audit binding mismatch: " + key)
        if key in completion and completion[key] != digest:
            raise ValueError("Completion binding mismatch: " + key)
        if key in contract and contract[key] != digest:
            raise ValueError("Dataset contract binding mismatch: " + key)
        if key == "engine_runner_sha256" and contract["runner_sha256"] != digest:
            raise ValueError("Dataset runner binding mismatch")
        verified[str(source.resolve())] = digest
    summary_path = root / "summary.json"
    if sha(summary_path) != completion["summary_sha256"]:
        raise ValueError("Completion summary mismatch")
    verified[str(summary_path)] = sha(summary_path)
    index = pd.read_parquet(root / "index.parquet")
    counts = index.status.value_counts().to_dict()
    if (
        len(index) != 2601
        or counts != {"COMPLETE": 2595, "MISSING_SOURCE": 6}
        or index.duplicated(["ticker", "date"]).any()
        or binding.get("available_days") != 2595
        or binding.get("missing_days") != 6
        or contract.get("expected_calendar_rows") != 2601
        or contract.get("expected_available_days") != 2595
        or contract.get("expected_missing_days") != 6
    ):
        raise ValueError("Full audit coverage/count mismatch")
    return {
        "path": str(path),
        "sha256": sha(path),
        "status": audit["status"],
        "binding": binding,
        "verified_files": verified,
    }


class SourceSeal:
    """Verify every consumed action/label sidecar against the audited final index."""

    def __init__(self, root):
        self.index = pd.read_parquet(Path(root) / "index.parquet")
        self.index["date"] = self.index.date.astype(str)
        self.index = self.index.set_index(["ticker", "date"], verify_integrity=True)
        self.hashes = {}

    def check(self, day, filename):
        record = self.index.loc[(day.ticker, day.date)]
        if (
            record.status != "COMPLETE"
            or Path(record.day_root).resolve() != day.oracle.resolve()
        ):
            raise ValueError("Unaudited or mismatched oracle day")
        path = day.oracle / filename
        digest = sha(path)
        if digest != record[Path(filename).stem + "_sha256"]:
            raise ValueError("Changed audited oracle sidecar: " + str(path))
        self.hashes[str(path)] = digest
        return digest

    def recheck(self):
        for path, digest in self.hashes.items():
            if sha(path) != digest:
                raise ValueError("Oracle sidecar changed after use: " + path)


def sample_training(days, out, cap=STRATUM_CAP, seal=None):
    pools = [pd.DataFrame(), pd.DataFrame()]
    populations = [0, 0]
    hashes = {}
    for number, day in enumerate(days):
        if day.date >= "20250101":
            continue
        if seal is not None:
            for filename in ("actions.parquet", "labels.parquet", "advantages.parquet"):
                seal.check(day, filename)
        actions = pd.read_parquet(
            day.oracle / "actions.parquet", columns=["action_id", "state_i"]
        )
        labels = pd.read_parquet(
            day.oracle / "labels.parquet",
            columns=["action_id", "net_base", "entry_ask", "status"],
        )
        advantage = pd.read_parquet(
            day.oracle / "advantages.parquet",
            columns=[
                "action_id",
                "dp_advantage",
                "teacher_selected",
                "state_optimal_action",
            ],
        )
        frame = actions.merge(labels, on="action_id", validate="one_to_one").merge(
            advantage, on="action_id", validate="one_to_one"
        )
        if len(frame) != len(actions):
            raise ValueError("Training sidecar universe mismatch")
        frame["day_key"], frame["ticker"], frame["date"] = day.key, day.ticker, day.date
        frame["priority"] = row_priority(day.ticker, day.date, frame.action_id)
        for stratum in (0, 1):
            subset = frame.loc[
                frame.teacher_selected.astype(bool) == bool(stratum)
            ].copy()
            subset["stratum"] = stratum
            populations[stratum] += len(subset)
            pools[stratum] = bounded_lowest(
                pd.concat([pools[stratum], subset], ignore_index=True), cap
            )
        for filename in ("actions.parquet", "labels.parquet", "advantages.parquet"):
            p = day.oracle / filename
            hashes[str(p)] = sha(p)
            if seal is not None and hashes[str(p)] != seal.hashes[str(p)]:
                raise ValueError("Training source changed while reading: " + str(p))
        if number % 100 == 0:
            print(
                json.dumps(
                    {
                        "stage": "training_sample",
                        "day": number,
                        "populations": populations,
                    }
                ),
                flush=True,
            )
    for stratum in (0, 1):
        pools[stratum]["weight"] = (
            populations[stratum] / len(pools[stratum]) if len(pools[stratum]) else 0.0
        )
    sample = (
        pd.concat(pools, ignore_index=True)
        .sort_values(["day_key", "action_id"], kind="stable")
        .reset_index(drop=True)
    )
    if not len(sample):
        raise ValueError("Empty training population")
    sample["weight"] /= sample.weight.mean()
    sample["sample_i"] = np.arange(len(sample), dtype=np.int64)
    sample.to_parquet(out / "training_sample.parquet", index=False)
    write_json(
        out / "sampling_manifest.json",
        {
            "seed": SEED,
            "cap_per_stratum": cap,
            "priority": "SHA256(day) xor action_id then SplitMix64",
            "populations": populations,
            "selected": [len(p) for p in pools],
            "sample_sha256": sha(out / "training_sample.parquet"),
            "sources": hashes,
        },
    )
    return sample


class FeatureStore:
    """At most sixteen daily packs. No economic sidecar is accepted here."""

    def __init__(self, days, capacity=4, seal=None):
        self.days = {d.key: d for d in days}
        self.capacity = min(int(capacity), 16)
        self.cache = OrderedDict()
        self.hashes = {}
        self.schema = None
        self.seal = seal
        contract_path = (
            next(iter(self.days.values())).features.parents[2] / "feature_contract.json"
        )
        self.contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if self.contract.get("outcomes_read") is not False:
            raise ValueError("Feature contract must be outcome-free")
        self.hashes[str(contract_path)] = sha(contract_path)
        if self.seal is not None:
            for filename, digest in self.contract["dependencies"].items():
                source = Path(__file__).with_name(filename)
                if sha(source) != digest:
                    raise ValueError("Feature producer differs from frozen contract")
                self.hashes[str(source)] = digest
            self.action_inputs = import_sibling("features").ACTION_INPUT_NAMES

    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        path = self.days[key].features
        with np.load(path, allow_pickle=False) as source:
            pack = {k: source[k] for k in source.files}
        metadata_path = path.with_suffix(".json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata["schema"] != self.contract["schema"]:
            raise ValueError("Day feature schema differs from fixed feature contract")
        if metadata["binding"]["dependencies"] != self.contract["dependencies"]:
            raise ValueError(
                "Day feature dependency version differs from fixed feature contract"
            )
        if (
            sha(path) != metadata["sha256"]
            or metadata.get("outcomes_read") is not False
        ):
            raise ValueError("Unverified or noncausal feature pack")
        action_path = path.with_name("actions.npz")
        action_metadata_path = action_path.with_suffix(".json")
        action_metadata = json.loads(action_metadata_path.read_text(encoding="utf-8"))
        if (
            action_metadata["action_names"] != self.contract["schema"]["action_names"]
            or action_metadata["binding"]["dependencies"]
            != self.contract["dependencies"]
        ):
            raise ValueError("Action feature whitelist/dependency mismatch")
        if (
            sha(action_path) != action_metadata["sha256"]
            or action_metadata.get("outcomes_read") is not False
        ):
            raise ValueError("Unverified or noncausal action feature pack")
        with np.load(action_path, allow_pickle=False) as source:
            pack["action_ids"] = source["action_id"]
            pack["action_features"] = source["action_features"]
        causal_path = self.days[key].oracle / "actions.parquet"
        if self.seal is not None:
            self.seal.check(self.days[key], "actions.parquet")
        causal = pd.read_parquet(causal_path, columns=["action_id", "state_i"])
        if self.seal is not None:
            day = self.days[key]
            record = self.seal.index.loc[(day.ticker, day.date)]
            for meta in (metadata, action_metadata):
                if (
                    meta["binding"]["source_sha256"] != record.cache_npz_sha256
                    or meta["binding"]["source_metadata_sha256"]
                    != record.cache_meta_sha256
                ):
                    raise ValueError(
                        "Feature pack belongs to a different audited cache"
                    )
            identity = pd.read_parquet(
                causal_path, columns=["action_id", *self.action_inputs]
            )
            digest = hashlib.sha256(
                identity.to_numpy(dtype=np.float64).tobytes()
            ).hexdigest()
            if digest != action_metadata["binding"]["action_inputs_sha256"]:
                raise ValueError(
                    "Action feature binding differs from audited causal inputs"
                )
        lookup = causal.set_index("action_id").state_i
        if set(lookup.index) != set(pack["action_ids"]):
            raise ValueError("Feature pack changed the offered causal action universe")
        pack["action_state_i"] = lookup.loc[pack["action_ids"]].to_numpy()
        for name in ("base_names", "token_names", "map_names"):
            pack[name] = np.asarray(metadata["schema"][name], dtype=str)
        pack["action_names"] = np.asarray(action_metadata["action_names"], dtype=str)
        pack["token_mask"] = np.stack((pack["token_mask"], pack["bar_mask"]), axis=-1)
        required = {
            "state_i",
            "base",
            "tokens",
            "maps",
            "token_mask",
            "map_mask",
            "action_ids",
            "action_features",
            "action_state_i",
        }
        if not required.issubset(pack):
            raise ValueError(f"Feature pack missing {required - set(pack)}: {path}")
        for name in ("base_names", "token_names", "map_names", "action_names"):
            if name not in pack:
                raise ValueError(
                    "Feature names are required for a frozen whitelist: " + name
                )
            if FORBIDDEN_FEATURES.intersection(str(v) for v in pack[name]):
                raise ValueError("Forbidden future/label feature name")
        schema = {
            k: pack[k].tolist()
            for k in ("base_names", "token_names", "map_names", "action_names")
        }
        if self.schema is None:
            self.schema = schema
        elif self.schema != schema:
            raise ValueError("Changing feature schema")
        if pack["tokens"].shape[1] != 20 or pack["maps"].shape[1:] != (20, 5, 64):
            raise ValueError("Incomplete candle/map tensor")
        if len(np.unique(pack["action_ids"])) != len(pack["action_ids"]):
            raise ValueError("Duplicate feature action IDs")
        pack["_action_index"] = pd.Index(pack["action_ids"])
        pack["_state_index"] = pd.Index(pack["state_i"])
        for source in (
            path,
            metadata_path,
            action_path,
            action_metadata_path,
            causal_path,
        ):
            digest = sha(source)
            if str(source) in self.hashes and self.hashes[str(source)] != digest:
                raise ValueError(
                    "Feature source changed between passes: " + str(source)
                )
            self.hashes[str(source)] = digest
        self.cache[key] = pack
        while len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
        return pack

    def rows(self, key, action_ids):
        p = self.get(key)
        ai = p["_action_index"].get_indexer(np.asarray(action_ids))
        if (ai < 0).any():
            raise ValueError("Offered action is missing from causal feature pack")
        si = p["_state_index"].get_indexer(p["action_state_i"][ai])
        if (si < 0).any():
            raise ValueError("Action references a missing state")
        return p, ai, si


def flatten_gbt(pack, ai, si):
    maps = np.asarray(pack["maps"][si], np.float32)
    # Exactly eight contiguous bins; all 64 original cells contribute.
    maps = maps.reshape(len(si), 20, 5, 8, 8).mean(axis=-1).reshape(len(si), -1)
    return np.concatenate(
        (
            pack["base"][si],
            pack["tokens"][si].reshape(len(si), -1),
            np.asarray(pack["token_mask"][si], np.float32).reshape(len(si), -1),
            maps,
            np.asarray(pack["map_mask"][si], np.float32).reshape(len(si), -1),
            pack["action_features"][ai],
        ),
        axis=1,
    ).astype(np.float32)


class Moments:
    def __init__(self, width):
        self.n = np.zeros(width, np.float64)
        self.s = np.zeros(width, np.float64)
        self.ss = np.zeros(width, np.float64)

    def update(self, values, weights):
        values = np.asarray(values, np.float64).reshape(-1, len(self.n))
        weights = np.broadcast_to(
            np.asarray(weights, np.float64).reshape(-1, 1), values.shape
        )
        valid = np.isfinite(values)
        safe = np.where(valid, values, 0)
        w = np.where(valid, weights, 0)
        self.n += w.sum(axis=0)
        self.s += (safe * w).sum(axis=0)
        self.ss += (safe * safe * w).sum(axis=0)

    def result(self):
        den = np.maximum(self.n, 1e-12)
        mean = self.s / den
        std = np.sqrt(np.maximum(self.ss / den - mean * mean, 0))
        std[std < 1e-6] = 1.0
        return {"mean": mean.tolist(), "std": std.tolist(), "weight": self.n.tolist()}


def build_training_matrix(sample, store, out):
    first = sample.iloc[0]
    p, ai, si = store.rows(first.day_key, [first.action_id])
    width = flatten_gbt(p, ai, si).shape[1]
    x = np.lib.format.open_memmap(
        out / "train_x.npy", mode="w+", dtype=np.float32, shape=(len(sample), width)
    )
    moments = {
        "base": Moments(p["base"].shape[-1]),
        "tokens": Moments(p["tokens"].shape[-1]),
        "maps": Moments(5),
        "action": Moments(p["action_features"].shape[-1]),
    }
    for key, rows in sample.groupby("day_key", sort=True):
        for offset in range(0, len(rows), 256):
            batch = rows.iloc[offset : offset + 256]
            pack, ai, si = store.rows(key, batch.action_id)
            x[batch.sample_i] = flatten_gbt(pack, ai, si)
            weights = batch.weight.to_numpy(float)
            moments["base"].update(pack["base"][si], weights)
            moments["tokens"].update(
                pack["tokens"][si].reshape(-1, pack["tokens"].shape[-1]),
                np.repeat(weights, 20),
            )
            m = np.asarray(pack["maps"][si]).transpose(0, 1, 3, 2).reshape(-1, 5)
            moments["maps"].update(m, np.repeat(weights, 20 * 64))
            moments["action"].update(pack["action_features"][ai], weights)
    x.flush()
    scales = {}
    for ticker in TICKERS:
        sub = sample.loc[(sample.ticker == ticker) & (sample.status == "FILLED")]
        scales[ticker] = weighted_median(sub.entry_ask * 100, sub.weight)
    normalizers = {k: v.result() for k, v in moments.items()}
    write_json(
        out / "normalizers.json",
        {
            "risk_scales_usd": scales,
            "features": normalizers,
            "fit_scope": "importance-weighted sampled 2023-2024 actions only",
            "gbt_columns": width,
        },
    )
    write_json(out / "feature_schema.json", store.schema)
    return x, scales, normalizers


class CausalBlock(nn.Module):
    def __init__(self, channels, dilation):
        super().__init__()
        self.pad = 2 * dilation
        self.conv = nn.Conv1d(channels, channels, 3, dilation=dilation)

    def forward(self, x):
        return F.relu(x + self.conv(F.pad(x, (self.pad, 0))))


class TemporalBranch(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.input = nn.Conv1d(channels, 32, 1)
        self.layers = nn.Sequential(CausalBlock(32, 1), CausalBlock(32, 2))

    def forward(self, x):
        x = self.layers(F.relu(self.input(x)))
        return torch.cat((x.mean(dim=-1), x[:, :, -1]), dim=-1)


class LevelTCN(nn.Module):
    def __init__(
        self, base_dim, token_dim, action_dim, token_mask_dim=1, map_mask_dim=5
    ):
        super().__init__()
        self.config = dict(
            base_dim=base_dim,
            token_dim=token_dim,
            action_dim=action_dim,
            token_mask_dim=token_mask_dim,
            map_mask_dim=map_mask_dim,
        )
        self.temporal5 = TemporalBranch(2 * token_dim + token_mask_dim)
        self.temporal15 = TemporalBranch(2 * token_dim + token_mask_dim)
        self.spatial = nn.Sequential(
            nn.Conv2d(10, 8, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(8, 16, 3, stride=(1, 2), padding=1),
            nn.ReLU(),
            nn.AvgPool2d((20, 4)),
            nn.Flatten(),
        )
        self.action = nn.Sequential(nn.Linear(2 * action_dim, 64), nn.ReLU())
        # Map masks are provided as five channel masks per token, independently
        # of cell finite-value masks already included in the spatial convolution.
        state_width = 2 * base_dim + 128 + 128 + 20 * map_mask_dim
        self.joint = nn.Sequential(
            nn.Linear(state_width + 64, 64), nn.ReLU(), nn.Linear(64, 32), nn.ReLU()
        )
        self.net = nn.Linear(32, 1)
        self.teacher = nn.Linear(32, 1)

    def encode_state(self, base, tokens, maps, token_mask, map_mask):
        t = torch.cat((tokens, token_mask), dim=-1).transpose(1, 2)
        temporal = torch.cat(
            (self.temporal5(t[:, :, :12]), self.temporal15(t[:, :, 12:])), dim=-1
        )
        spatial = self.spatial(maps.permute(0, 2, 1, 3))
        return torch.cat((base, temporal, spatial, map_mask.flatten(1)), dim=-1)

    def score_actions(self, state, action):
        context = torch.cat((state, self.action(action)), dim=-1)
        hidden = self.joint(context)
        return self.net(hidden).squeeze(-1), self.teacher(hidden).squeeze(-1)

    def forward(self, base, tokens, maps, action, token_mask, map_mask):
        return self.score_actions(
            self.encode_state(base, tokens, maps, token_mask, map_mask), action
        )


def normalized(values, stats):
    values = np.asarray(values, np.float32)
    mask = np.isfinite(values)
    numeric = np.where(
        mask,
        (values - np.asarray(stats["mean"], np.float32))
        / np.asarray(stats["std"], np.float32),
        0,
    )
    return np.concatenate((numeric, mask.astype(np.float32)), axis=-1)


def neural_batch(pack, ai, si, stats, device):
    base = normalized(pack["base"][si], stats["base"])
    tokens = normalized(pack["tokens"][si], stats["tokens"])
    maps = np.asarray(pack["maps"][si], np.float32).transpose(0, 1, 3, 2)
    maps = normalized(maps, stats["maps"]).transpose(0, 1, 3, 2)
    action = normalized(pack["action_features"][ai], stats["action"])
    token_mask = np.asarray(pack["token_mask"][si], np.float32).reshape(len(si), 20, -1)
    map_mask = np.asarray(pack["map_mask"][si], np.float32).reshape(len(si), 20, -1)
    return tuple(
        torch.as_tensor(np.ascontiguousarray(x), device=device)
        for x in (base, tokens, maps, action, token_mask, map_mask)
    )


def encode_unique_states(model, pack, state_indices, stats, device):
    values = []
    for start in range(0, len(state_indices), 256):
        states = state_indices[start : start + 256]
        inputs = neural_batch(
            pack, np.zeros(len(states), dtype=int), states, stats, device
        )
        values.append(
            model.encode_state(inputs[0], inputs[1], inputs[2], inputs[4], inputs[5])
        )
    return torch.cat(values, dim=0)


def neural_actions(model, pack, ai, si, stats, device):
    unique, inverse = np.unique(si, return_inverse=True)
    state = encode_unique_states(model, pack, unique, stats, device)
    action = torch.as_tensor(
        normalized(pack["action_features"][ai], stats["action"]), device=device
    )
    return model.score_actions(state[torch.as_tensor(inverse, device=device)], action)


def train_gbts(x, sample, scales, out):
    row_scale = sample.ticker.map(scales).to_numpy(float)
    config = dict(
        objective="regression",
        n_estimators=200,
        num_leaves=31,
        max_depth=6,
        min_child_samples=100,
        learning_rate=0.04,
        reg_lambda=10.0,
        max_bin=63,
        random_state=SEED,
        n_jobs=4,
        deterministic=True,
        force_col_wise=True,
        verbosity=-1,
    )
    for name, target in (("gbt_net", "net_base"), ("gbt_advantage", "dp_advantage")):
        model = lgb.LGBMRegressor(**config)
        model.fit(
            x,
            sample[target].to_numpy(float) / row_scale,
            sample_weight=sample.weight.to_numpy(float),
        )
        model.booster_.save_model(str(out / (name + ".txt")))
        print(
            json.dumps({"stage": "model_fit", "model": name, "rows": len(sample)}),
            flush=True,
        )
    write_json(out / "gbt_config.json", config)


def checkpoint_binding(out, device, feature_hashes):
    names = (
        "train_x.npy",
        "training_sample.parquet",
        "sampling_manifest.json",
        "normalizers.json",
        "feature_schema.json",
        "gbt_net.txt",
        "gbt_advantage.txt",
        "gbt_config.json",
        "run_identity.json",
    )
    files = {str((out / name).resolve()): sha(out / name) for name in names}
    files.update(feature_hashes)
    for name in ("train_models.py", "run_policy.py", "LEARNER_PLAN.md"):
        path = Path(__file__).with_name(name)
        files[str(path.resolve())] = sha(path)
    return {
        "output_root": str(out.resolve()),
        "device": device,
        "torch": torch.__version__,
        "numpy": np.__version__,
        "lightgbm": lgb.__version__,
        "files": files,
    }


def save_epoch_checkpoint(path, model, optimizer, rng, epoch, history, binding):
    if path.exists():
        raise ValueError("Never overwrite an existing neural epoch checkpoint")
    checkpoint = {
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "epoch": epoch,
        "history": history,
        "binding": binding,
        "generator_state": rng.bit_generator.state,
        "numpy_state": np.random.get_state(),
        "torch_state": torch.get_rng_state(),
        "cuda_states": torch.cuda.get_rng_state_all()
        if next(model.parameters()).is_cuda
        else [],
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    temporary = path.with_suffix(".partial-" + stamp)
    torch.save(checkpoint, temporary)
    os.replace(temporary, path)
    write_json(
        path.with_suffix(".json"),
        {
            "sha256": sha(path),
            "epoch": epoch,
            "binding": binding,
            "complete_epoch_boundary": True,
        },
    )


def restore_epoch_checkpoint(path, model, optimizer, rng, binding):
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if metadata["binding"] != binding or sha(path) != metadata["sha256"]:
        raise ValueError("Resume checkpoint identity mismatch")
    for source, digest in binding["files"].items():
        if sha(source) != digest:
            raise ValueError("Resume input changed: " + source)
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if checkpoint["binding"] != binding or checkpoint["epoch"] != metadata["epoch"]:
        raise ValueError("Resume checkpoint internal identity mismatch")
    model.load_state_dict(checkpoint["model"])
    optimizer.load_state_dict(checkpoint["optimizer"])
    rng.bit_generator.state = checkpoint["generator_state"]
    np.random.set_state(checkpoint["numpy_state"])
    torch.set_rng_state(checkpoint["torch_state"])
    if checkpoint["cuda_states"]:
        torch.cuda.set_rng_state_all(checkpoint["cuda_states"])
    return checkpoint["epoch"], checkpoint["history"]


def train_tcn(sample, store, scales, stats, out, device, resume=None):
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    if device.startswith("cuda"):
        torch.cuda.manual_seed_all(SEED)
        torch.backends.cudnn.benchmark = False
    first = sample.iloc[0]
    pack, ai, si = store.rows(first.day_key, [first.action_id])
    batch = neural_batch(pack, ai, si, stats, device)
    model = LevelTCN(
        pack["base"].shape[-1],
        pack["tokens"].shape[-1],
        pack["action_features"].shape[-1],
        batch[4].shape[-1],
        batch[5].shape[-1],
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
    groups = {k: r.index.to_numpy() for k, r in sample.groupby("day_key", sort=True)}
    keys = np.array(sorted(groups), dtype=object)
    rng = np.random.default_rng(SEED)
    history = []
    binding = checkpoint_binding(out, device, store.hashes)
    first_epoch = 0
    if resume is not None:
        # Reuse the original source set; every file is checked before restoration.
        previous = json.loads(resume.with_suffix(".json").read_text(encoding="utf-8"))
        for key in ("output_root", "device", "torch", "numpy", "lightgbm"):
            if previous["binding"][key] != binding[key]:
                raise ValueError("Resume environment differs: " + key)
        for source, digest in binding["files"].items():
            if previous["binding"]["files"].get(source) != digest:
                raise ValueError("Current training input differs from resume source")
        binding = previous["binding"]
        first_epoch, history = restore_epoch_checkpoint(
            resume, model, optimizer, rng, binding
        )
        store.hashes.update(
            {
                p: h
                for p, h in binding["files"].items()
                if p
                not in {
                    str((out / n).resolve())
                    for n in (
                        "train_x.npy",
                        "training_sample.parquet",
                        "sampling_manifest.json",
                        "normalizers.json",
                        "feature_schema.json",
                        "gbt_net.txt",
                        "gbt_advantage.txt",
                        "gbt_config.json",
                        "run_identity.json",
                    )
                }
            }
        )
    model.train()
    for epoch in range(first_epoch, EPOCHS):
        order = rng.permutation(keys)
        loss_total = 0.0
        for key in order:
            indices = rng.permutation(groups[key])
            for start in range(0, len(indices), BATCH):
                rows = sample.loc[indices[start : start + BATCH]]
                p, ai, si = store.rows(key, rows.action_id)
                target = torch.as_tensor(
                    (rows.net_base / rows.ticker.map(scales)).to_numpy(np.float32),
                    device=device,
                )
                teacher = torch.as_tensor(
                    rows.state_optimal_action.to_numpy(np.float32), device=device
                )
                weights = torch.as_tensor(
                    rows.weight.to_numpy(np.float32), device=device
                )
                optimizer.zero_grad(set_to_none=True)
                predicted, logits = neural_actions(model, p, ai, si, stats, device)
                per_row = (
                    predicted - target
                ).square() + 0.1 * F.binary_cross_entropy_with_logits(
                    logits, teacher, reduction="none"
                )
                loss = (weights * per_row).sum() / BATCH
                if not torch.isfinite(loss):
                    raise FloatingPointError(
                        "Nonfinite fixed neural loss; preserve attempt, do not silently retune"
                    )
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                loss_total += float(loss.detach().cpu())
        history.append({"epoch": epoch + 1, "summed_fixed_batch_loss": loss_total})
        save_epoch_checkpoint(
            out / f"tcn_epoch{epoch + 1:02}.pt",
            model,
            optimizer,
            rng,
            epoch + 1,
            history,
            binding,
        )
        print(json.dumps({"stage": "neural_epoch", **history[-1]}), flush=True)
    torch.save(
        {"state_dict": model.cpu().state_dict(), "config": model.config, "seed": SEED},
        out / "tcn_teacher.pt",
    )
    write_json(
        out / "neural_training.json",
        {
            "device": device,
            "torch": torch.__version__,
            "epochs": history,
            "loss": "weighted squared scaled net + .1 weighted per-state teacher BCE",
            "batch_denominator": BATCH,
        },
    )


def load_predictors(out, device):
    models = {
        name: lgb.Booster(model_file=str(out / (name + ".txt"))) for name in MODELS[:2]
    }
    checkpoint = torch.load(
        out / "tcn_teacher.pt", map_location="cpu", weights_only=True
    )
    network = LevelTCN(**checkpoint["config"])
    network.load_state_dict(checkpoint["state_dict"])
    models["tcn_teacher"] = network.to(device).eval()
    return models


def predict_day(day, store, models, scales, stats, device):
    # Opening actions is permitted; this function never opens labels/advantages.
    if store.seal is not None:
        store.seal.check(day, "actions.parquet")
    actions = pd.read_parquet(day.oracle / "actions.parquet")
    scores = {name: np.empty(len(actions), np.float64) for name in MODELS}
    if len(actions):
        pack, all_ai, all_si = store.rows(day.key, actions.action_id)
        unique, inverse = np.unique(all_si, return_inverse=True)
        with torch.inference_mode():
            neural_states = encode_unique_states(
                models["tcn_teacher"], pack, unique, stats, device
            )
    for start in range(0, len(actions), BATCH):
        subset = actions.iloc[start : start + BATCH]
        pack, ai, si = store.rows(day.key, subset.action_id)
        x = flatten_gbt(pack, ai, si)
        for name in MODELS[:2]:
            scores[name][start : start + len(subset)] = (
                models[name].predict(x, num_threads=4) * scales[day.ticker]
            )
        with torch.inference_mode():
            action = torch.as_tensor(
                normalized(pack["action_features"][ai], stats["action"]), device=device
            )
            prediction, _ = models["tcn_teacher"].score_actions(
                neural_states[
                    torch.as_tensor(inverse[start : start + len(subset)], device=device)
                ],
                action,
            )
        scores["tcn_teacher"][start : start + len(subset)] = (
            prediction.cpu().numpy() * scales[day.ticker]
        )
    if any(not np.isfinite(v).all() for v in scores.values()):
        raise FloatingPointError("Nonfinite causal scores")
    return actions, scores


def economic_metrics(frame):
    result = {"trades": len(frame)}
    result["exit_diagnostics_available"] = "reason" in frame
    result["exit_reasons"] = (
        {
            reason: {
                "trades": int((frame.reason == reason).sum()),
                "base_net_usd": float(
                    frame.loc[frame.reason == reason, "net_base"].sum()
                ),
                "adverse_net_usd": float(
                    frame.loc[frame.reason == reason, "net_adverse"].sum()
                ),
            }
            for reason in ("TARGET", "STOP", "EOD")
        }
        if "reason" in frame
        else {}
    )
    holding = (
        frame.hold_minutes.to_numpy(float) if "hold_minutes" in frame else np.array([])
    )
    result["holding_minutes"] = {
        "min": float(holding.min()) if len(holding) else None,
        "median": float(np.median(holding)) if len(holding) else None,
        "max": float(holding.max()) if len(holding) else None,
    }
    for field, prefix in (("net_base", "base"), ("net_adverse", "adverse")):
        values = frame[field].to_numpy(float) if len(frame) else np.array([], float)
        gains = float(values[values > 0].sum())
        losses = float(-values[values < 0].sum())
        result[prefix + "_net_usd"] = float(values.sum())
        result[prefix + "_pf"] = gains / losses if losses else None
        result[prefix + "_pf_infinite"] = bool(gains > 0 and losses == 0)
        result[prefix + "_win_rate"] = (
            float((values > 0).mean()) if len(values) else None
        )
        cumulative = np.r_[0.0, np.cumsum(values)]
        result[prefix + "_max_drawdown_usd"] = float(
            np.max(np.maximum.accumulate(cumulative) - cumulative)
        )
    return result


def policy_id(model, threshold):
    return f"{model}__{int(threshold)}"


def select_policy(validation, scales):
    choices = [
        {"policy": "CASH", "model": None, "threshold": None, "selection_score": 0.0}
    ]
    for model in MODELS:
        for threshold in THRESHOLDS:
            ident = policy_id(model, threshold)
            tickers = validation[ident]["tickers"]
            score = sum(tickers[t]["base_net_usd"] / scales[t] for t in TICKERS)
            choices.append(
                {
                    "policy": ident,
                    "model": model,
                    "threshold": threshold,
                    "selection_score": float(score),
                }
            )
    # Stable max leaves CASH first on exact score zero, then fixed model/threshold order.
    winner = max(choices, key=lambda c: c["selection_score"])
    return winner, choices


def evaluate_period(days, store, models, scales, stats, out, period, device, engine):
    lower, upper = (
        ("20250101", "20260101") if period == "validation" else ("20260101", "20260701")
    )
    target = out / period
    target.mkdir(exist_ok=False)
    ledgers = {policy_id(m, t): [] for m in MODELS for t in THRESHOLDS}
    attempts = {ident: [] for ident in ledgers}
    prediction_hashes = {}
    policy_module = import_sibling("run_policy")
    for number, day in enumerate(d for d in days if lower <= d.date < upper):
        actions, scores = predict_day(day, store, models, scales, stats, device)
        prediction_file = target / (day.ticker + "_" + day.date + ".npz")
        np.savez_compressed(
            prediction_file, action_ids=actions.action_id.to_numpy(), **scores
        )
        prediction_hashes[prediction_file.name] = sha(prediction_file)
        # Separate stage after predictions are saved: future fills/exit labels.
        if store.seal is not None:
            store.seal.check(day, "labels.parquet")
        labels = pd.read_parquet(day.oracle / "labels.parquet")
        view = policy_module.PolicyView(actions, labels)
        for model in MODELS:
            ranked = view.rank(scores[model])
            for threshold in THRESHOLDS:
                result = view.evaluate(scores[model], threshold, engine, ranked)
                attempted = result.attempts.copy()
                attempted["ticker"], attempted["date"] = day.ticker, day.date
                attempted["policy"] = policy_id(model, threshold)
                attempts[policy_id(model, threshold)].append(attempted)
                ledger = result.ledger.copy()
                ledger["ticker"], ledger["date"] = day.ticker, day.date
                ledger["policy"] = policy_id(model, threshold)
                ledgers[policy_id(model, threshold)].append(ledger)
        if number % 50 == 0:
            print(
                json.dumps(
                    {
                        "stage": period,
                        "day": number,
                        "date": day.date,
                        "ticker": day.ticker,
                    }
                ),
                flush=True,
            )
    summaries = {}
    months = pd.period_range(
        pd.Timestamp(lower), pd.Timestamp(upper) - pd.Timedelta(days=1), freq="M"
    ).strftime("%Y%m")
    for ident, frames in ledgers.items():
        ledger = (
            pd.concat(frames, ignore_index=True)
            if frames
            else pd.DataFrame(columns=["ticker", "date", "net_base", "net_adverse"])
        )
        ledger = ledger.sort_values(
            ["date", "exit_i", "ticker", "state_i"]
            if "exit_i" in ledger
            else ["date", "ticker"],
            kind="stable",
        )
        ledger.to_parquet(target / (ident + "_ledger.parquet"), index=False)
        pd.concat(attempts[ident], ignore_index=True).to_parquet(
            target / (ident + "_attempts.parquet"), index=False
        )
        calendar = pd.read_csv(
            out / "expected_full_calendar.csv", dtype={"date": str}
        ).date
        calendar = calendar.loc[(calendar >= lower) & (calendar < upper)]
        daily = (
            ledger.groupby(["date", "ticker"]).net_base.sum().unstack(fill_value=0)
            if len(ledger)
            else pd.DataFrame()
        )
        daily = daily.reindex(index=calendar, columns=TICKERS, fill_value=0).fillna(0)
        daily.to_csv(target / (ident + "_daily_net.csv"))
        summaries[ident] = {
            "pooled": economic_metrics(ledger),
            "tickers": {
                t: economic_metrics(ledger.loc[ledger.ticker == t]) for t in TICKERS
            },
            "months": {
                t: {
                    month: economic_metrics(
                        ledger.loc[
                            (ledger.ticker == t) & ledger.date.str.startswith(month)
                        ]
                    )
                    for month in months
                }
                for t in TICKERS
            },
        }
    write_json(target / "summary.json", summaries)
    write_json(target / "prediction_hashes.json", prediction_hashes)
    return summaries


def economic_gate(selected, summaries):
    if selected["policy"] == "CASH":
        return {
            "passes": False,
            "reason": "CASH_SELECTED_NOT_A_PROFITABLE_LEARNER",
            "tickers": {},
        }
    summary = summaries[selected["policy"]]
    flags = {}
    for ticker in TICKERS:
        m = summary["tickers"][ticker]
        positive_months = sum(
            v["base_net_usd"] > 0 for v in summary["months"][ticker].values()
        )
        passes = (
            m["base_net_usd"] > 0
            and m["adverse_net_usd"] > 0
            and (
                m.get("base_pf_infinite", False)
                or (m["base_pf"] is not None and m["base_pf"] >= 1.2)
            )
            and m["trades"] >= 60
            and positive_months >= 3
        )
        flags[ticker] = {
            "passes": bool(passes),
            "positive_months": positive_months,
            **m,
        }
    return {"passes": all(v["passes"] for v in flags.values()), "tickers": flags}


def freeze(out, selection, choices, store, oracle_audit):
    names = [
        "train_x.npy",
        "gbt_net.txt",
        "gbt_advantage.txt",
        "tcn_teacher.pt",
        "normalizers.json",
        "feature_schema.json",
        "sampling_manifest.json",
        "training_sample.parquet",
        "oracle_sources_before_test.json",
        "validation/summary.json",
        "validation/prediction_hashes.json",
    ]
    record = {
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "selected_policy": selection,
        "validation_choices": choices,
        "artifacts": {name: sha(out / name) for name in names},
        "feature_sources": dict(store.hashes),
        "oracle_audit": oracle_audit,
        "script_sha256": sha(__file__),
        "plan_sha256": sha(Path(__file__).with_name("LEARNER_PLAN.md")),
        "engine_sha256": sha(Path(__file__).with_name("level_engine.py")),
        "scheduler_sha256": sha(Path(__file__).with_name("run_policy.py")),
        "protocol_sha256": sha(Path(__file__).with_name("PROTOCOL.md")),
        "learner_test_economics_evaluated": False,
        "test_oracle_is_seen_descriptive": True,
    }
    write_json(out / "freeze.json", record)
    return record


def verify_freeze(out):
    record = json.loads((out / "freeze.json").read_text(encoding="utf-8"))
    for name, digest in record["artifacts"].items():
        if sha(out / name) != digest:
            raise ValueError("Changed learner freeze artifact: " + name)
    if (
        sha(__file__) != record["script_sha256"]
        or sha(Path(__file__).with_name("LEARNER_PLAN.md")) != record["plan_sha256"]
    ):
        raise ValueError("Changed frozen learner code/plan")
    if (
        sha(Path(__file__).with_name("level_engine.py")) != record["engine_sha256"]
        or sha(Path(__file__).with_name("PROTOCOL.md")) != record["protocol_sha256"]
    ):
        raise ValueError("Changed frozen execution engine/protocol")
    if sha(Path(__file__).with_name("run_policy.py")) != record["scheduler_sha256"]:
        raise ValueError("Changed frozen causal scheduler")
    for path, digest in record["oracle_audit"]["verified_files"].items():
        if sha(path) != digest:
            raise ValueError("Changed full oracle audit authority: " + path)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle-root", type=Path, required=True)
    parser.add_argument("--feature-root", type=Path, required=True)
    parser.add_argument("--oracle-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument(
        "--resume-tcn",
        type=Path,
        help="Resume latest complete epoch in the same output, before validation",
    )
    args = parser.parse_args()
    audit = require_oracle_pass(args.oracle_audit, args.oracle_root)
    out = args.output
    if args.resume_tcn is None:
        out.mkdir(parents=True, exist_ok=False)
        for name in (
            "train_models.py",
            "run_policy.py",
            "LEARNER_PLAN.md",
            "features.py",
            "build_cache.py",
            "level_engine.py",
            "run_engine_dataset.py",
            "PROTOCOL.md",
        ):
            shutil.copy2(Path(__file__).with_name(name), out / name)
    else:
        checkpoints = sorted(out.glob("tcn_epoch*.pt"))
        if (
            not checkpoints
            or args.resume_tcn.resolve() != checkpoints[-1].resolve()
            or any(
                (out / name).exists()
                for name in ("validation", "test", "freeze.json", "tcn_teacher.pt")
            )
        ):
            raise ValueError(
                "Resume requires latest epoch and no completed TCN/validation/test"
            )
        previous = json.loads((out / "run_identity.json").read_text(encoding="utf-8"))
        if previous["oracle_audit"] != audit or previous["device"] != args.device:
            raise ValueError("Resume audit/device differs from original attempt")
        for name in ("train_models.py", "run_policy.py", "LEARNER_PLAN.md"):
            if sha(out / name) != sha(Path(__file__).with_name(name)):
                raise ValueError("Resume producer/plan differs from original attempt")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        write_json(
            out / f"resume_{stamp}.json",
            {
                "checkpoint": str(args.resume_tcn),
                "checkpoint_sha256": sha(args.resume_tcn),
                "uncommitted_partial_epoch_replayed": True,
                "completed_epochs_replayed": False,
            },
        )
    start = time.monotonic()
    days = discover_days(args.oracle_root, args.feature_root)
    verify_full_coverage(days, out)
    if args.resume_tcn is None:
        write_json(
            out / "run_identity.json",
            {
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "days": [d.key for d in days],
                "oracle_audit": audit,
                "device": args.device,
                "torch": torch.__version__,
                "lightgbm": lgb.__version__,
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "source_policy": "LOCAL_ONLY",
            },
        )
    seal = SourceSeal(args.oracle_root)
    store = FeatureStore(days, seal=seal)
    if args.resume_tcn is None:
        sample = sample_training(days, out, seal=seal)
        print(
            json.dumps({"stage": "training_matrix_start", "sample_rows": len(sample)}),
            flush=True,
        )
        x, scales, stats = build_training_matrix(sample, store, out)
        print(
            json.dumps({"stage": "gbt_fits_start", "shape": list(x.shape)}), flush=True
        )
        train_gbts(x, sample, scales, out)
        del x
    else:
        for day in days:
            if day.date < "20250101":
                for name in ("actions.parquet", "labels.parquet", "advantages.parquet"):
                    seal.check(day, name)
        sample = pd.read_parquet(out / "training_sample.parquet")
        normalizers = json.loads((out / "normalizers.json").read_text(encoding="utf-8"))
        scales, stats = normalizers["risk_scales_usd"], normalizers["features"]
    print(json.dumps({"stage": "tcn_fit_start"}), flush=True)
    train_tcn(sample, store, scales, stats, out, args.device, args.resume_tcn)
    models = load_predictors(out, args.device)
    engine = import_sibling("level_engine")
    validation = evaluate_period(
        days, store, models, scales, stats, out, "validation", args.device, engine
    )
    selection, choices = select_policy(validation, scales)
    seal.recheck()
    write_json(out / "oracle_sources_before_test.json", seal.hashes)
    freeze(out, selection, choices, store, audit)
    verify_freeze(out)
    print("POLICY_FROZEN_BEFORE_LEARNER_TEST_ECONOMICS", flush=True)
    test = evaluate_period(
        days, store, models, scales, stats, out, "test", args.device, engine
    )
    verify_freeze(out)
    seal.recheck()
    write_json(out / "oracle_sources_final.json", seal.hashes)
    hashes = {path: sha(path) == digest for path, digest in store.hashes.items()}
    write_json(out / "feature_rehash.json", hashes)
    if not all(hashes.values()):
        raise ValueError("Feature source changed")
    result = {
        "status": "COMPLETED_CAUSAL_LEARNER_DEVELOPMENT",
        "selected_policy": selection,
        "selected_test": None
        if selection["policy"] == "CASH"
        else test[selection["policy"]],
        "selected_cash_net_usd": 0 if selection["policy"] == "CASH" else None,
        "provisional_gate": economic_gate(selection, test),
        "validation_choices": choices,
        "risk_scales_usd": scales,
        "seconds": time.monotonic() - start,
        "test_candidate_results_are_diagnostic_not_selection": True,
        "drawdown_convention": "realized trade net in exit-time order; not intratrade mark-to-market",
        "untouched_outer": False,
        "technical_ready": False,
        "promotion_approved": False,
    }
    write_json(out / "summary.json", result)
    print(result["status"], flush=True)


if __name__ == "__main__":
    main()
