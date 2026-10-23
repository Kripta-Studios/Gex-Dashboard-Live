"""Independent audit of monthly V1 evidence given already sealed scores.

This module deliberately does not import the monthly producer, LightGBM, or its
calendar/selection modules.  It checks source and artifact bytes, reconstructs
training samples/targets, and reconstructs the scheduler and economics from the
sealed score vectors.  It does not refit models or repeat inference.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import uuid

import numpy as np
import pandas as pd


STATUS = "PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES"
REVIEW_STATUS = "PASS_MONTHLY_SEALED_SCORE_AUDITOR_IMPLEMENTATION_REVIEW"
VERSION = "MONTHLY_NET_WALK_FORWARD_V1"
MODES = ("static", "expanding", "rolling12")
TICKERS = ("SPXW", "SPY", "QQQ")
SEED = 20261018
BANDS = ((60, 138), (139, 217), (218, 296), (297, 375))
CAP_PER_BAND = 32
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


def require(ok, message):
    if not bool(ok):
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), "Refusing to replace existing audit result")
    temporary = path.with_name(path.name + ".partial-" + uuid.uuid4().hex)
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def month_shift(value, offset):
    require(type(value) is date and value.day == 1, "Invalid calendar month")
    ordinal = value.year * 12 + value.month - 1 + offset
    year, month0 = divmod(ordinal, 12)
    return date(year, month0 + 1, 1)


def window(mode, month):
    require(mode in MODES, "Unknown mode")
    start = month_shift(month, -12) if mode == "rolling12" else date(2023, 1, 1)
    stop = date(2025, 1, 1) if mode == "static" else month
    return start, stop, f"train_{start:%Y%m%d}_{stop:%Y%m%d}_exclusive"


def parse_utc(value):
    stamp = datetime.fromisoformat(value)
    require(stamp.tzinfo is not None and stamp.utcoffset() is not None, "Naive seal time")
    return stamp.astimezone(timezone.utc)


class Verifier:
    def __init__(self):
        self.files = {}
        self._flat = {}

    def file(self, category, path, expected=None):
        path = Path(path).resolve()
        old = self._flat.get(str(path))
        if old is not None:
            if expected is not None:
                require(old == str(expected), "Conflicting expected hash: " + str(path))
            self.files.setdefault(category, {})[str(path)] = old
            return old
        actual = sha(path)
        if expected is not None:
            require(actual == str(expected), "Hash mismatch: " + str(path))
        self._flat[str(path)] = actual
        self.files.setdefault(category, {})[str(path)] = actual
        return actual

    def recheck(self):
        for path, digest in self._flat.items():
            require(sha(path) == digest, "Verified file changed during audit: " + path)


class Evidence:
    def __init__(self, root, verifier, binding):
        self.root = Path(root).resolve()
        self.verifier, self.binding = verifier, binding

    def marker(self, name, category="artifacts"):
        path = self.root / (name + ".complete.json")
        self.verifier.file(category, path)
        record = read_json(path)
        require(
            record.get("status") == "COMPLETE" and record.get("binding") == self.binding,
            "Incomplete or wrongly bound checkpoint: " + name,
        )
        require(bool(record.get("files")), "Empty checkpoint: " + name)
        sealed = {}
        for relative, digest in record["files"].items():
            target = (self.root / relative).resolve()
            require(target.is_relative_to(self.root), "Checkpoint path escapes root")
            self.verifier.file(category, target, digest)
            sealed[str(target)] = digest
        parse_utc(record["completed_utc"])
        return record, sealed

    def member(self, name, path, category="artifacts"):
        record, sealed = self.marker(name, category)
        target = str(Path(path).resolve())
        require(target in sealed, "Required member absent from checkpoint: " + target)
        return record


def verify_executed_code(root, dependencies, verifier):
    root = Path(root).resolve()
    require(set(dependencies) == set(DEPENDENCIES), "Monthly dependency universe differs")
    code_root = (root / "executed_code").resolve()
    for name in DEPENDENCIES:
        require(Path(name).name == name, "Unsafe dependency name")
        snapshot = (code_root / name).resolve()
        require(snapshot.is_relative_to(code_root), "Executed-code path escapes root")
        verifier.file("root", snapshot, dependencies[name])


def recheck_hashes(paths, context):
    for path, digest in paths.items():
        require(sha(path) == digest, context + ": " + path)


def verify_implementation_review(path, verifier):
    review_path = Path(path).resolve()
    verifier.file("root", review_path)
    review = read_json(review_path)
    require(review.get("status") == REVIEW_STATUS, "Auditor implementation review required")
    require(review.get("auditor_sha256") == sha(__file__), "Reviewed auditor bytes differ")
    companion = Path(__file__).with_name("test_audit_monthly_walk_forward.py")
    contract_document = Path(__file__).with_name(
        "MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDIT_CONTRACT.md"
    )
    require(
        review.get("tests_sha256") == sha(companion)
        and review.get("contract_sha256") == sha(contract_document),
        "Reviewed fixtures/contract bytes differ",
    )
    return review


def canonical_identity(ticker, stamp, state_i, action_id):
    payload = json.dumps(
        [SEED, ticker, stamp, int(state_i), int(action_id)],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def independent_sample(ticker, stamp, actions):
    ids = actions.action_id.to_numpy()
    states = actions.state_i.to_numpy()
    require(
        ids.dtype.kind in "iu" and states.dtype.kind in "iu" and len(np.unique(ids)) == len(ids),
        "Invalid offered-action identities",
    )
    require(np.all((states >= 60) & (states <= 375)), "Action outside sampling bands")
    bands = (states - 60) // 79
    population = np.bincount(bands, minlength=4).astype(np.int64)
    digests = np.asarray(
        [canonical_identity(ticker, stamp, state, action) for action, state in zip(ids, states)],
        dtype="U64",
    )
    selected = []
    for band in range(4):
        rows = np.flatnonzero(bands == band).tolist()
        rows.sort(key=lambda j: (digests[j], SEED, ticker, stamp, int(states[j]), int(ids[j])))
        selected.extend(rows[:CAP_PER_BAND])
    ix = np.asarray(selected, dtype=np.int64)
    counts = np.minimum(population, CAP_PER_BAND)
    weight = np.asarray(
        [population[bands[j]] / (len(ids) * counts[bands[j]]) for j in selected],
        dtype=np.float64,
    )
    return dict(
        action_id=ids[ix], state_i=states[ix], band_i=bands[ix],
        identity_sha256=digests[ix], weight=weight,
        population_by_band=population, selected_by_band=counts,
    )


def arrays_equal(left, right):
    return set(left) == set(right) and all(
        np.array_equal(np.asarray(left[key]), np.asarray(right[key]), equal_nan=True)
        if np.asarray(left[key]).dtype.kind in "fc"
        else np.array_equal(np.asarray(left[key]), np.asarray(right[key]))
        for key in left
    )


def load_npz(path):
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


def equal_frames(actual, expected, context):
    try:
        pd.testing.assert_frame_equal(
            actual.reset_index(drop=True), expected.reset_index(drop=True),
            check_dtype=True, check_exact=True,
        )
    except AssertionError as exc:
        raise ValueError(context + ": " + str(exc)) from exc


def align_labels(close_i, actions, labels):
    require(
        not actions.action_id.duplicated().any() and not labels.action_id.duplicated().any(),
        "Duplicated action/label identity",
    )
    require(len(actions) == len(labels), "Action/label count differs")
    ix = pd.Index(labels.action_id).get_indexer(actions.action_id)
    require(np.all(ix >= 0), "Missing action outcome")
    aligned = labels.iloc[ix].reset_index(drop=True)
    states, exits = actions.state_i.to_numpy(), aligned.exit_i.to_numpy()
    fill = aligned.status.to_numpy() == "FILLED"
    require(
        actions.state_i.dtype.kind in "iu" and np.all((states >= 60) & (states <= close_i - 15)),
        "Invalid action clocks",
    )
    require(
        aligned.exit_i.dtype.kind in "iu" and aligned.status.isin(["FILLED", "NO_FILL"]).all(),
        "Invalid outcome clocks/status",
    )
    require(np.all((exits[fill] >= states[fill] + 2) & (exits[fill] <= close_i - 5)),
            "Filled exit outside session")
    require(np.all(exits[~fill] == states[~fill] + 1), "NO_FILL retry differs")
    for field in ("net_base", "net_adverse"):
        require(np.isfinite(aligned[field]).all() and np.all(aligned[field].to_numpy()[~fill] == 0),
                "Invalid economic payoff")
    return aligned


def schedule(close_i, actions, labels, scores):
    scores = np.asarray(scores)
    require(scores.shape == (len(actions),) and np.isfinite(scores).all(), "Invalid scores")
    order = np.lexsort((actions.action_id.to_numpy(), -scores, actions.state_i.to_numpy()))
    choices = {}
    for row in order:
        minute = int(actions.state_i.iloc[row])
        if minute not in choices:
            choices[minute] = int(row) if scores[row] > 0 else -1
    lab = align_labels(close_i, actions, labels)
    selected, before, minute, filled_before = [], [], 60, 0
    while minute <= close_i - 15:
        row = choices.get(minute, -1)
        if row < 0:
            minute += 1
            continue
        selected.append(row)
        before.append(filled_before)
        if lab.status.iloc[row] == "FILLED":
            filled_before = 1
            minute = int(lab.exit_i.iloc[row]) + 1
        else:
            minute += 1
    attempts = actions.iloc[selected].merge(lab.iloc[selected], on="action_id", validate="one_to_one")
    attempts["score"] = scores[selected]
    attempts["has_filled_before"] = before
    return attempts, attempts.loc[attempts.status == "FILLED"].copy()


def economic_summary(ledger):
    result = {"trades": len(ledger)}
    for field in ("net_base", "net_adverse"):
        values = ledger[field].to_numpy(float) if len(ledger) else np.array([], float)
        require(np.isfinite(values).all(), "Nonfinite economic reward")
        gains, losses = float(values[values > 0].sum()), float(-values[values < 0].sum())
        curve = np.r_[0.0, np.cumsum(values)]
        result[field] = float(values.sum())
        result[field + "_pf"] = gains / losses if losses else None
        result[field + "_pf_infinite"] = gains > 0 and losses == 0
        result[field + "_win_rate"] = float((values > 0).mean()) if len(values) else None
        result[field + "_max_drawdown"] = float(np.max(np.maximum.accumulate(curve) - curve))
    result["holding_minutes"] = {
        key: float(getattr(ledger.hold_minutes, key)()) if len(ledger) else None
        for key in ("min", "median", "max")
    }
    result["exit_reasons"] = (
        {
            reason: {
                "trades": int((ledger.reason == reason).sum()),
                "net_base": float(ledger.loc[ledger.reason == reason, "net_base"].sum()),
                "net_adverse": float(ledger.loc[ledger.reason == reason, "net_adverse"].sum()),
            }
            for reason in ("TARGET", "STOP", "EOD")
        }
        if len(ledger) else {}
    )
    return result


def json_equal(actual, expected, context):
    require(actual == expected, context)


@dataclass
class SourceDay:
    ticker: str
    stamp: str
    status: str
    close_i: int
    root: Path
    actions_sha256: str
    labels_sha256: str
    feature_paths: tuple[Path, Path, Path, Path]


class MonthlyAudit:
    def __init__(self, monthly_root, source_audit, implementation_review=None):
        self.root = Path(monthly_root).resolve()
        self.source_audit_path = Path(source_audit).resolve()
        self.v = Verifier()
        if implementation_review is not None:
            verify_implementation_review(implementation_review, self.v)
        contract_path = self.root / "run_contract.json"
        self.contract_hash = self.v.file("run_contract", contract_path)
        self.contract = read_json(contract_path)
        require(self.contract.get("version") == VERSION, "Wrong monthly version")
        require(self.contract.get("seed") == SEED and self.contract.get("features") == 1954,
                "Changed seed or feature width")
        verify_executed_code(self.root, self.contract.get("dependencies", {}), self.v)
        self.evidence = Evidence(self.root, self.v, self.contract_hash)
        self.source_audit_hash = self.v.file("source_index", self.source_audit_path)
        audit = read_json(self.source_audit_path)
        require(audit.get("status") == "PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT",
                "Independent session dataset audit required")
        require(self.contract.get("source_audit") == {
            "path": str(self.source_audit_path), "sha256": self.source_audit_hash,
            "binding": audit["binding"], "coverage": self.contract["source_audit"]["coverage"],
            "feature_contract_sha256": audit["binding"]["feature_contract_sha256"],
        }, "Run/source audit binding differs")
        binding = audit["binding"]
        self.session_root = Path(binding["engine_root"]).resolve()
        require(Path(binding["feature_root"]).resolve() == Path(self.contract["feature_root"]).resolve(),
                "Feature root differs")
        index_path = self.session_root / "index.parquet"
        self.index_hash = self.v.file("source_index", index_path, binding["index_sha256"])
        for name, field in (("dataset_contract.json", "dataset_contract_sha256"),
                            ("completion.json", "completion_sha256")):
            self.v.file("calendar", self.session_root / name, binding[field])
        self.v.file("calendar", Path(self.contract["feature_root"]) / "feature_contract.json",
                    binding["feature_contract_sha256"])
        index = pd.read_parquet(index_path)
        index["date"] = index.date.astype(str)
        require(not index.duplicated(["ticker", "date"]).any(), "Duplicated source calendar")
        self.index = index.set_index(["ticker", "date"], verify_integrity=True)
        require(len(index) == 2625 and int((index.status == "COMPLETE").sum()) == 2619,
                "Source calendar coverage differs")
        self.days = {}
        for row in index.itertuples(index=False):
            self.days[(row.ticker, row.date)] = SourceDay(
                row.ticker, row.date, row.status, int(row.close_i), Path(row.day_root).resolve(),
                row.actions_sha256, row.labels_sha256,
                (
                    Path(row.features_path).resolve(),
                    Path(row.features_meta_path).resolve(),
                    Path(row.action_features_path).resolve(),
                    Path(row.action_features_meta_path).resolve(),
                ),
            )
        self._validated_training_days = {}
        self.source_reads = {}

    def source_frame(self, day, filename, columns=None):
        expected = day.actions_sha256 if filename == "actions.parquet" else day.labels_sha256
        path = day.root / filename
        # Source bytes are anchored by the independently hashed index.  They are checked
        # here but intentionally omitted from verified_files to keep the adapter compact.
        require(sha(path) == expected, "Changed source sidecar: " + str(path))
        prior = self.source_reads.get(str(path.resolve()))
        require(prior is None or prior == expected, "Source sidecar index binding changed")
        self.source_reads[str(path.resolve())] = expected
        frame = pd.read_parquet(path, columns=columns)
        require(sha(path) == expected, "Source sidecar changed during read: " + str(path))
        return frame

    def validate_day_training(self, day):
        key = (day.ticker, day.stamp)
        if key in self._validated_training_days:
            return self._validated_training_days[key]
        actions = self.source_frame(day, "actions.parquet", ["action_id", "state_i"])
        labels = self.source_frame(day, "labels.parquet")
        aligned = align_labels(day.close_i, actions, labels)
        sample_name = "day_samples/" + day.ticker + "/" + day.stamp
        chunk_name = "day_chunks/" + day.ticker + "/" + day.stamp
        sample_path, chunk_path = self.root / (sample_name + ".npz"), self.root / (chunk_name + ".npz")
        self.evidence.member(sample_name, sample_path, "fit_inputs")
        self.evidence.member(chunk_name, chunk_path, "fit_inputs")
        sample, chunk = load_npz(sample_path), load_npz(chunk_path)
        expected = independent_sample(day.ticker, day.stamp, actions)
        require(arrays_equal(sample, expected), "Training sample differs")
        require(np.array_equal(chunk["action_id"], sample["action_id"]), "Chunk/sample identity differs")
        ix = pd.Index(actions.action_id).get_indexer(sample["action_id"])
        selected = aligned.iloc[ix]
        require(
            np.array_equal(chunk["net"], selected.net_base.to_numpy(float), equal_nan=True)
            and np.array_equal(chunk["premium"], selected.entry_ask.to_numpy(float) * 100, equal_nan=True)
            and np.array_equal(chunk["filled"], (selected.status == "FILLED").to_numpy())
            and np.array_equal(chunk["weight"], sample["weight"]),
            "Training chunk target/weight differs",
        )
        result = (sample, chunk)
        self._validated_training_days[key] = result
        return result

    def audit_fit(self, key, start, stop):
        info_path = self.root / "fits" / key / "inputs.json"
        self.evidence.member("fits/" + key + "/inputs", info_path, "fit_inputs")
        info = read_json(info_path)
        require(
            info["fit_key"] == key and info["train_start"] == start.isoformat()
            and info["train_stop_exclusive"] == stop.isoformat()
            and info["config"] == self.contract["config"],
            "Fit identity/config differs",
        )
        for path, digest in info["input_hashes"].items():
            self.v.file("fit_inputs", path, digest)
        model_path = self.root / "models" / (key + ".txt")
        model_record = self.evidence.member("models/" + key, model_path, "models")
        started_path = model_path.with_suffix(".fit_started.json")
        require(str(started_path.resolve()) in {
            str((self.root / p).resolve()) for p in model_record["files"]
        }, "Fit-start signature absent from model seal")
        started = read_json(started_path)
        self.v.file("models", started_path)
        require(started["binding"] == self.contract_hash and started["config"] == self.contract["config"],
                "Fit-start binding/config differs")
        targets_path = self.root / "fits" / key / "targets.npz"
        matrix_path = self.root / "fits" / key / "matrix.npy"
        self.evidence.member("fits/" + key + "/targets", targets_path, "fit_inputs")
        self.evidence.member("fits/" + key + "/matrix", matrix_path, "fit_inputs")
        targets = load_npz(targets_path)
        matrix = np.load(matrix_path, mmap_mode="r", allow_pickle=False)
        require(matrix.shape == tuple(started["shape"]) == (info["rows"], 1954), "Fit matrix shape")
        require(started["matrix_sha256"] == sha(matrix_path), "Fit-start matrix signature")
        require(started["target_sha256"] == hashlib.sha256(targets["target"].tobytes()).hexdigest(),
                "Fit-start target signature")
        require(started["weight_sha256"] == hashlib.sha256(targets["weight"].tobytes()).hexdigest(),
                "Fit-start weight signature")
        days = sorted(
            [day for day in self.days.values() if day.status == "COMPLETE"
             and start <= datetime.strptime(day.stamp, "%Y%m%d").date() < stop],
            key=lambda item: (item.ticker, item.stamp),
        )
        require(len(days) == info["ticker_days"], "Fit ticker-day count")
        nets, weights, premiums, filled, tickers = [], [], [], [], []
        offset = 0
        for day in days:
            sample, chunk = self.validate_day_training(day)
            expected_inputs = {
                str((day.root / "actions.parquet").resolve()),
                str((day.root / "labels.parquet").resolve()),
                *(str(path) for path in day.feature_paths),
            }
            for prefix in ("day_samples", "day_chunks", "feature_inputs"):
                artifact_name = prefix + "/" + day.ticker + "/" + day.stamp
                marker_path = self.root / (artifact_name + ".complete.json")
                expected_inputs.add(str(marker_path.resolve()))
                marker = read_json(marker_path)
                expected_inputs.update(
                    str((self.root / relative).resolve())
                    for relative in marker["files"]
                )
            require(
                expected_inputs.issubset(info["input_hashes"]),
                "Fit input closure omits a training-day dependency",
            )
            n = len(chunk["net"])
            require(np.array_equal(matrix[offset:offset + n], chunk["x"], equal_nan=True),
                    "Fit matrix/chunk differs")
            offset += n
            nets.append(chunk["net"])
            weights.append(sample["weight"])
            premiums.append(chunk["premium"])
            filled.append(chunk["filled"])
            tickers.append(np.full(n, day.ticker))
        net, weight, premium, fill, ticker = map(
            np.concatenate, (nets, weights, premiums, filled, tickers)
        )
        require(offset == info["rows"] and np.array_equal(targets["net"], net), "Fit net rows")
        scales = {}
        for symbol in TICKERS:
            mask = (ticker == symbol) & fill & np.isfinite(premium) & (premium > 0)
            require(mask.any(), "No valid scale rows")
            order = np.argsort(premium[mask], kind="stable")
            values, w = premium[mask][order], weight[mask][order]
            scales[symbol] = float(values[np.searchsorted(np.cumsum(w), w.sum() / 2, side="left")])
        require(scales == info["scales"], "Fit scales differ")
        fit_weight = weight * (len(weight) / len(days))
        target = net / np.asarray([scales[value] for value in ticker])
        require(
            np.array_equal(targets["target"], target)
            and np.array_equal(targets["weight"], fit_weight)
            and np.array_equal(targets["ticker"], ticker),
            "Fit targets/weights/tickers differ",
        )
        del matrix
        return info, self.v.file("models", model_path)

    def audit_month(self, stamp, fit_cache):
        month = datetime.strptime(stamp, "%Y%m").date().replace(day=1)
        require(date(2025, 1, 1) <= month < date(2026, 7, 1), "Month outside contract")
        folds = {}
        for mode in MODES:
            start, stop, key = window(mode, month)
            if key not in fit_cache:
                fit_cache[key] = self.audit_fit(key, start, stop)
            folds[mode] = (key, *fit_cache[key])
        expected_keys = sorted({value[0] for value in folds.values()})
        month_name = "months/" + stamp + "/predictions"
        month_marker, month_sealed = self.evidence.marker(
            month_name, "prediction_manifests"
        )
        require(month_marker["extra"].get("fit_keys") == expected_keys
                and month_marker["extra"].get("labels_read") is False,
                "Monthly prediction manifest differs")
        prediction_time = parse_utc(month_marker["completed_utc"])
        days = sorted([day for day in self.days.values() if day.stamp.startswith(stamp)],
                      key=lambda item: (item.ticker, item.stamp))
        require(days, "Empty evaluation month")
        feature_names = [
            "feature_inputs/" + day.ticker + "/" + day.stamp
            for day in days if day.status == "COMPLETE"
        ]
        require(
            month_marker["extra"].get("source_manifests")
            == sorted(name + ".json" for name in feature_names),
            "Monthly feature manifest universe differs",
        )
        for name in feature_names:
            manifest_path = self.root / (name + ".json")
            self.evidence.member(name, manifest_path, "prediction_manifests")
            require(
                str(manifest_path.resolve()) in month_sealed
                and str((self.root / (name + ".complete.json")).resolve()) in month_sealed,
                "Feature provenance absent from all-mode monthly seal",
            )
            for path, digest in read_json(manifest_path).items():
                self.v.file("prediction_manifests", path, digest)
        for key in expected_keys:
            for path in (
                self.root / "models" / (key + ".txt"),
                self.root / "models" / (key + ".complete.json"),
                self.root / "fits" / key / "inputs.json",
                self.root / "fits" / key / "inputs.complete.json",
            ):
                require(str(path.resolve()) in month_sealed,
                        "Fit evidence absent from all-mode monthly seal")
        daily, mode_ledgers = {mode: [] for mode in MODES}, {mode: [] for mode in MODES}
        daily_closure = {str((self.root / (month_name + ".complete.json")).resolve())}
        for day in days:
            if day.status != "COMPLETE":
                for mode in MODES:
                    daily[mode].append(dict(ticker=day.ticker, date=day.stamp,
                        source_status=day.status, trades=0, net_base=0.0, net_adverse=0.0))
                continue
            actions = self.source_frame(day, "actions.parquet")
            labels = self.source_frame(day, "labels.parquet")
            predictions = {}
            for key in expected_keys:
                pred_name = "predictions/" + stamp + "/" + key + "/" + day.ticker + "/" + day.stamp
                pred_path = self.root / (pred_name + ".npz")
                self.evidence.member(pred_name, pred_path, "prediction_manifests")
                require(str(pred_path.resolve()) in month_sealed,
                        "Prediction absent from all-mode monthly seal")
                pred = load_npz(pred_path)
                info, model_hash = fit_cache[key]
                require(
                    str(pred["model_sha256"]) == model_hash
                    and float(pred["scale"]) == info["scales"][day.ticker]
                    and np.array_equal(pred["action_id"], actions.action_id)
                    and np.array_equal(pred["state_i"], actions.state_i)
                    and np.isfinite(pred["scores"]).all(),
                    "Sealed prediction binding differs",
                )
                predictions[key] = (pred, pred_path)
            for mode in MODES:
                key = folds[mode][0]
                pred, pred_path = predictions[key]
                attempts, ledger = schedule(day.close_i, actions, labels, pred["scores"])
                for frame in (attempts, ledger):
                    frame["ticker"], frame["date"], frame["mode"], frame["fit_key"] = (
                        day.ticker, day.stamp, mode, key,
                    )
                prefix = "ledgers/" + stamp + "/" + mode + "/" + day.ticker + "/" + day.stamp
                marker, sealed = self.evidence.marker(prefix, "prediction_manifests")
                require(prediction_time < parse_utc(marker["completed_utc"]),
                        "Ledger sealed before all-mode monthly scores")
                require(marker["extra"].get("prediction_sha256") == sha(pred_path),
                        "Ledger/prediction hash differs")
                attempt_path = self.root / (prefix + "_attempts.parquet")
                ledger_path = self.root / (prefix + "_ledger.parquet")
                require(str(attempt_path.resolve()) in sealed and str(ledger_path.resolve()) in sealed,
                        "Ledger members absent")
                equal_frames(pd.read_parquet(attempt_path), attempts, "Attempts differ")
                equal_frames(pd.read_parquet(ledger_path), ledger, "Ledger differs")
                daily_closure.update(
                    {
                        str(attempt_path.resolve()),
                        str(ledger_path.resolve()),
                        str((self.root / (prefix + ".complete.json")).resolve()),
                    }
                )
                mode_ledgers[mode].append(ledger)
                daily[mode].append(dict(ticker=day.ticker, date=day.stamp,
                    source_status=day.status, trades=len(ledger),
                    net_base=float(ledger.net_base.sum()),
                    net_adverse=float(ledger.net_adverse.sum())))
        economics = {}
        for mode in MODES:
            full = pd.concat(mode_ledgers[mode], ignore_index=True) if mode_ledgers[mode] else pd.DataFrame(
                columns=["ticker", "date", "exit_i", "net_base", "net_adverse", "hold_minutes", "reason"])
            full = full.sort_values(["date", "exit_i", "ticker"], kind="stable")
            economics[mode] = dict(overall=economic_summary(full),
                tickers={ticker: economic_summary(full.loc[full.ticker == ticker]) for ticker in TICKERS})
        econ_name = "months/" + stamp + "/economics"
        econ_path = self.root / (econ_name + ".json")
        self.evidence.member(econ_name, econ_path, "prediction_manifests")
        json_equal(read_json(econ_path), economics, "Monthly economics differ")
        daily_closure.update(
            {
                str(econ_path.resolve()),
                str((self.root / (econ_name + ".complete.json")).resolve()),
            }
        )
        daily_name = "months/" + stamp + "/daily"
        daily_path = self.root / (daily_name + ".json")
        _, daily_sealed = self.evidence.marker(daily_name, "prediction_manifests")
        require(str(daily_path.resolve()) in daily_sealed, "Daily JSON absent from month seal")
        require(daily_closure.issubset(daily_sealed), "Monthly daily closure omits evidence")
        json_equal(read_json(daily_path), daily, "Monthly daily records differ")
        return daily

    def audit_period_report(self, year, records, selected_mode):
        require(year == 2025, "This auditor invocation is validation-only")

        def summarize(rows, ledger):
            available = [row for row in rows if row["source_status"] == "COMPLETE"]
            missing = len(rows) - len(available)
            active = sum(row["trades"] > 0 for row in available)
            zero = len(available) - active
            economy = economic_summary(ledger)
            require(
                economy["trades"] == sum(row["trades"] for row in available)
                and np.isclose(economy["net_base"], sum(row["net_base"] for row in available))
                and np.isclose(economy["net_adverse"], sum(row["net_adverse"] for row in available)),
                "Period ledger/daily mismatch",
            )
            return dict(
                expected_ticker_days=len(rows), available_ticker_days=len(available),
                missing_no_evaluable=missing, available_days_with_fill=active,
                available_days_without_fill=zero,
                observable_daily_pass=bool(available) and zero == 0,
                full_calendar_daily_status=(
                    "NO_EVALUABLE_MISSING_SOURCE" if missing else
                    "PASS" if available and zero == 0 else "FAIL_OBSERVED_ZERO"
                ),
                daily_requirement_satisfied=bool(available) and missing == 0 and zero == 0,
                available_economics=economy,
                net_base_per_available_day=economy["net_base"] / len(available)
                if available else None,
                missing_day_economics=None,
            )

        modes = {}
        columns = ["ticker", "date", "exit_i", "net_base", "net_adverse",
                   "hold_minutes", "reason"]
        for mode in MODES:
            frames = []
            for row in records[mode]:
                if row["source_status"] != "COMPLETE":
                    continue
                stamp = row["date"][:6]
                prefix = "ledgers/" + stamp + "/" + mode + "/" + row["ticker"] + "/" + row["date"]
                path = self.root / (prefix + "_ledger.parquet")
                frames.append(pd.read_parquet(path, columns=columns))
            ledger = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)
            ledger = ledger.sort_values(["date", "exit_i", "ticker"], kind="stable")
            modes[mode] = dict(
                overall=summarize(records[mode], ledger),
                tickers={
                    ticker: summarize(
                        [row for row in records[mode] if row["ticker"] == ticker],
                        ledger.loc[ledger.ticker == ticker],
                    )
                    for ticker in TICKERS
                },
            )
        expected = dict(
            year=year, modes=modes, selected_mode=selected_mode,
            selection_period=2025, development_seen=True, promotion_approved=False,
            missing_sources_are_not_observed_losses=True,
        )
        name = "reports/2025"
        path = self.root / (name + ".json")
        self.evidence.member(name, path, "calendar")
        require(read_json(path) == expected, "Validation period report differs")

    def audit_validation(self):
        months = [f"2025{month:02d}" for month in range(1, 13)]
        fit_cache, all_daily = {}, {mode: [] for mode in MODES}
        for stamp in months:
            values = self.audit_month(stamp, fit_cache)
            for mode in MODES:
                all_daily[mode].extend(values[mode])
        freeze_path = self.root / "validation_freeze.json"
        self.evidence.member("validation_freeze", freeze_path, "calendar")
        freeze = read_json(freeze_path)
        common_key = window("static", date(2025, 1, 1))[2]
        common_info = fit_cache[common_key][0]
        self.v.file("scales", self.root / "fits" / common_key / "inputs.json")
        expected_hashes = {
            str((self.root / "months" / stamp / "daily.json").resolve()):
            sha(self.root / "months" / stamp / "daily.json") for stamp in months
        }
        # Reconstruct the eligibility and score table independently.
        choices = []
        for mode in MODES:
            rows = all_daily[mode]
            missing = sum(row["source_status"] == "MISSING_SOURCE" for row in rows)
            no_fill = sum(row["source_status"] == "COMPLETE" and row["trades"] == 0 for row in rows)
            active = sum(row["trades"] > 0 for row in rows)
            net = math.fsum(row["net_base"] for row in rows)
            adverse = math.fsum(row["net_adverse"] for row in rows)
            score = math.fsum(
                row["net_base"] / common_info["scales"][row["ticker"]]
                for row in rows
            ) / len(rows)
            choices.append(dict(mode=mode, expected_ticker_days=len(rows), missing_no_evaluable=missing,
                available_days_without_fill=no_fill, active_ticker_days=active,
                daily_viable=(missing == 0 and no_fill == 0), trades=sum(row["trades"] for row in rows),
                net_base=net, net_adverse=adverse, common_scale_mean_daily_score=score,
                mean_active_day_net_base=net / active if active else None))
        eligible = [row for row in choices if row["daily_viable"]]
        winner = max(eligible, key=lambda row: row["common_scale_mean_daily_score"]) if eligible else None
        expected_freeze = dict(
            status="SELECTED_RESEARCH_MODE" if winner else "FAIL_NO_DAILY_COMPLIANT_MODE",
            selected_mode=winner["mode"] if winner else None,
            approved=False,
            common_scales=common_info["scales"],
            choices=choices,
            selection_period="2025",
            tie_break=list(MODES),
            common_scale_fit=common_key,
            validation_input_hashes=expected_hashes,
            update_rule="FROZEN_CALENDAR_STATIC_EXPANDING_ROLLING12",
            outcomes_2026_used_for_mode_selection=False,
        )
        require(freeze == expected_freeze, "Validation mode selection/freeze differs")
        self.audit_period_report(2025, all_daily, expected_freeze["selected_mode"])
        result = dict(
            status=STATUS,
            binding=dict(
                monthly_root=str(self.root), run_contract_sha256=self.contract_hash,
                session_root=str(self.session_root), session_audit_sha256=self.source_audit_hash,
                index_sha256=self.index_hash, completed_months=months,
            ),
            verified_files=self.v.files,
            audited=dict(months=12, modes=list(MODES), unique_fit_windows=len(fit_cache),
                calendar_ticker_days=sum(len(values) for values in all_daily.values()) // len(MODES),
                sampling_reconstructed=True, training_targets_weights_labels_reconstructed=True,
                fit_matrices_reconstructed_from_day_chunks=True,
                sealed_score_identity_model_scale_verified=True,
                scheduler_ledgers_economics_reconstructed=True,
                all_mode_monthly_score_seal_precedes_ledger_seals=True,
                validation_selection_reconstructed=True,
                validation_period_report_reconstructed=True),
            limitations=[
                "Models were not refit and score inference was not repeated; this PASS is conditional on the sealed score vectors.",
                "Artifact timestamps prove seal order, not historical publication at each information cutoff.",
                "Evaluation source sidecars were rehashed against the independently sealed index; the index binding compactly represents them in verified_files.",
                "This development replay does not establish prospective performance or authorize promotion.",
            ],
            development_seen=True, promotion_approved=False,
        )
        self.v.recheck()
        recheck_hashes(self.source_reads, "Source sidecar changed after audit read")
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--monthly-root", type=Path, required=True)
    parser.add_argument("--source-audit", type=Path, required=True)
    parser.add_argument("--implementation-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Use a new audit output directory")
    result = MonthlyAudit(
        args.monthly_root, args.source_audit, args.implementation_review
    ).audit_validation()
    args.output.mkdir(parents=True, exist_ok=False)
    result["audit_script_sha256"] = sha(__file__)
    atomic_json(args.output / "audit.json", result)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
