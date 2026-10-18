"""Independent economic/target reconstruction given sealed scores; no refits."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import time
import traceback

import numpy as np
import pandas as pd

MODELS = ("net_control", "causal_residual")
TICKERS = ("SPXW", "SPY", "QQQ")
THRESHOLDS = (0.0, 5.0, 10.0)
TRAIN_LAYOUT = (("teacher", 372, 1954), ("final", 1119, 1955))
POLICIES = tuple(f"{m}__{int(t)}" for m in MODELS for t in THRESHOLDS)
MISSING = {(t, d) for t in ("SPY", "QQQ") for d in ("20260401", "20260409", "20260415")}
LABEL_COLUMNS = [
    "action_id",
    "status",
    "exit_i",
    "net_base",
    "net_adverse",
    "reason",
    "hold_minutes",
]


def require(condition, message):
    if not bool(condition):
        raise AssertionError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def array_sha(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def equal(a, b, context="value"):
    if isinstance(a, dict):
        require(isinstance(b, dict) and set(a) == set(b), context + " keys")
        for key in a:
            equal(a[key], b[key], context + "/" + key)
    elif isinstance(a, (list, tuple)):
        require(isinstance(b, (list, tuple)) and len(a) == len(b), context + " length")
        for i, (x, y) in enumerate(zip(a, b)):
            equal(x, y, context + f"/{i}")
    elif isinstance(a, (float, np.floating)):
        require(
            isinstance(b, (int, float, np.number))
            and np.isfinite(a)
            and np.isfinite(b)
            and np.isclose(a, b, rtol=1e-10, atol=1e-8),
            context + " numeric",
        )
    else:
        require(a == b, context + " differs")


def aligned(actions, labels):
    require(
        not actions.action_id.duplicated().any()
        and not labels.action_id.duplicated().any(),
        "Duplicate IDs",
    )
    require(len(actions) == len(labels), "Label count")
    lookup = pd.Index(labels.action_id).get_indexer(actions.action_id)
    require(np.all(lookup >= 0), "Label identity mismatch")
    lab = labels.iloc[lookup].reset_index(drop=True)
    state = actions.state_i.to_numpy()
    require(
        state.dtype.kind in "iu" and np.all((state >= 60) & (state <= 375)),
        "State bounds",
    )
    require(
        actions.action_id.dtype.kind in "iu" and np.all(actions.action_id >= 0),
        "Action identity type",
    )
    require(np.isin(lab.status, ["FILLED", "NO_FILL"]).all(), "Unknown fill status")
    require(lab.exit_i.dtype.kind in "iu", "Exit integer type")
    fill = lab.status.to_numpy() == "FILLED"
    require(
        np.all(
            (lab.exit_i.to_numpy()[fill] >= state[fill] + 2)
            & (lab.exit_i.to_numpy()[fill] <= 385)
        ),
        "Filled exit bounds",
    )
    require(
        np.all(lab.exit_i.to_numpy()[~fill] == state[~fill] + 1), "No-fill retry bounds"
    )
    require(
        np.isfinite(lab.net_base).all() and np.all(lab.net_base.to_numpy()[~fill] == 0),
        "Net/NO_FILL reward",
    )
    return lab


def ranked_choices(actions, scores, threshold=0.0):
    """Construct choices solely from scores/identities, before labels enter."""
    score = np.asarray(scores)
    require(
        score.shape == (len(actions), 2) and np.isfinite(score).all(),
        "Score shape/finiteness",
    )
    require(not actions.action_id.duplicated().any(), "Duplicate action ID")
    states, ids = actions.state_i.to_numpy(), actions.action_id.to_numpy()
    require(
        states.dtype.kind in "iu" and ids.dtype.kind in "iu", "Identity integer types"
    )
    require(
        np.all((states >= 60) & (states <= 375)) and np.all(ids >= 0), "Identity bounds"
    )
    choices = np.full((316, 2), -1, dtype=np.int64)
    for flag in (0, 1):
        order = np.lexsort((ids, -score[:, flag], states))
        used = set()
        for row in order:
            minute = int(states[row])
            if minute not in used:
                used.add(minute)
                if score[row, flag] > threshold:
                    choices[minute - 60, flag] = ids[row]
    return choices


def schedule(actions, labels, scores, threshold):
    choices = ranked_choices(actions, scores, threshold)
    lab = aligned(actions, labels)
    action = actions.reset_index(drop=True)
    lookup = {int(key): i for i, key in enumerate(action.action_id)}
    selected, flags, values = [], [], []
    minute, flag = 60, 0
    while minute <= 375:
        identity = int(choices[minute - 60, flag])
        if identity < 0:
            minute += 1
            continue
        row = lookup[identity]
        selected.append(row)
        flags.append(flag)
        values.append(float(scores[row, flag]))
        if lab.status.iloc[row] == "FILLED":
            flag = 1
            minute = int(lab.exit_i.iloc[row]) + 1
        else:
            minute += 1
    attempts = action.iloc[selected].merge(
        lab.iloc[selected], on="action_id", validate="one_to_one"
    )
    attempts["has_filled_before"] = np.asarray(flags, dtype=np.int64)
    attempts["score"] = np.asarray(values, dtype=np.float64)
    return attempts, attempts.loc[attempts.status == "FILLED"].copy()


def policy_returns(actions, labels, choices, penalty):
    """Memoized evaluation of fixed choices, never a maximum of outcomes."""
    lab = aligned(actions, labels)
    require(np.isfinite(penalty) and penalty > 0, "Risk scale positive")
    require(choices.shape == (316, 2) and choices.dtype.kind in "iu", "Choices shape")
    lookup = {int(key): i for i, key in enumerate(actions.action_id)}
    for offset, pair in enumerate(choices):
        for key in pair:
            require(
                key == -1
                or (
                    int(key) in lookup
                    and int(actions.state_i.iloc[lookup[int(key)]]) == offset + 60
                ),
                "Choice identity/state",
            )

    @lru_cache(None)
    def value(minute, flag):
        if minute > 375:
            return -float(penalty) if flag == 0 else 0.0
        key = int(choices[minute - 60, flag])
        if key == -1:
            return value(minute + 1, flag)
        row = lookup[key]
        if lab.status.iloc[row] == "NO_FILL":
            return value(minute + 1, flag)
        return float(lab.net_base.iloc[row]) + value(int(lab.exit_i.iloc[row]) + 1, 1)

    # Evaluate late states first, keeping recursion depth bounded even for WAIT.
    result = np.empty((317, 2), dtype=np.float64)
    for minute in range(376, 59, -1):
        result[minute - 60] = [value(minute, 0), value(minute, 1)]
    residual = np.zeros((len(actions), 2), dtype=np.float64)
    for row, state in enumerate(actions.state_i):
        if lab.status.iloc[row] == "FILLED":
            tail = value(int(lab.exit_i.iloc[row]) + 1, 1)
            for flag in (0, 1):
                residual[row, flag] = (
                    float(lab.net_base.iloc[row]) + tail - value(int(state) + 1, flag)
                )
    return result, residual


def economics(frame):
    out = {"trades": len(frame)}
    for field in ("net_base", "net_adverse"):
        arr = frame[field].to_numpy(dtype=np.float64)
        require(np.isfinite(arr).all(), "Nonfinite economic PnL")
        positive = float(np.sum(arr[arr > 0]))
        negative = float(-np.sum(arr[arr < 0]))
        wealth, peak, drawdown = 0.0, 0.0, 0.0
        for value in arr:
            wealth += float(value)
            peak = max(peak, wealth)
            drawdown = max(drawdown, peak - wealth)
        out.update(
            {
                field: float(arr.sum()),
                field + "_pf": positive / negative if negative else None,
                field + "_pf_infinite": positive > 0 and negative == 0,
                field + "_win_rate": float(np.count_nonzero(arr > 0) / len(arr))
                if len(arr)
                else None,
                field + "_max_drawdown": drawdown,
            }
        )
    holds = frame.hold_minutes.to_numpy(float)
    out["holding_minutes"] = dict(
        min=float(np.min(holds)) if len(holds) else None,
        median=float(np.median(holds)) if len(holds) else None,
        max=float(np.max(holds)) if len(holds) else None,
    )
    out["exit_reasons"] = (
        {
            reason: dict(
                trades=int((frame.reason == reason).sum()),
                net_base=float(frame.loc[frame.reason == reason, "net_base"].sum()),
                net_adverse=float(
                    frame.loc[frame.reason == reason, "net_adverse"].sum()
                ),
            )
            for reason in ("TARGET", "STOP", "EOD")
        }
        if len(frame)
        else {}
    )
    return out


def selection(summary, scales):
    eligible = []
    for model in MODELS:
        for threshold in THRESHOLDS:
            key = f"{model}__{int(threshold)}"
            if summary[key]["zero_fill_expected_days"] == 0:
                value = sum(
                    summary[key]["tickers"][t]["net_base"] / scales[t] for t in TICKERS
                )
                eligible.append(
                    dict(
                        policy=key, score=float(value), model=model, threshold=threshold
                    )
                )
    ordered = sorted(
        eligible, key=lambda x: (-x["score"], MODELS.index(x["model"]), x["threshold"])
    )
    return dict(
        status="SELECTED" if ordered else "FAILED_DAILY_REQUIREMENT_VALIDATION",
        selected_policy=ordered[0] if ordered else None,
        eligible=eligible,
        frozen_candidates=list(POLICIES),
        cash="REFERENCE_ONLY_FAILS_DAILY_REQUIREMENT",
    )


def summarize_period(attempts, ledger, expected, available):
    stats, calendar = {}, []
    for key in POLICIES:
        trade = ledger.loc[ledger.policy == key].sort_values(
            ["date", "exit_i", "ticker"], kind="stable"
        )
        tried = attempts.loc[attempts.policy == key]
        counts = trade.groupby(["ticker", "date"]).size().to_dict()
        counts = {pair: int(counts.get(pair, 0)) for pair in expected}
        result = economics(trade)
        result.update(
            attempts=len(tried),
            no_fill_attempts=int((tried.status == "NO_FILL").sum()),
            expected_ticker_days=len(expected),
            observable_ticker_days=len(available),
            zero_fill_expected_days=sum(n == 0 for n in counts.values()),
            zero_fill_observable_days=sum(counts[pair] == 0 for pair in available),
            missing_source_days=len(expected) - len(available),
        )
        result["tickers"] = {}
        for ticker in TICKERS:
            sub = trade.loc[trade.ticker == ticker]
            detail = economics(sub)
            months = sorted({date[:6] for symbol, date in expected if symbol == ticker})
            detail["months"] = {
                month: economics(sub.loc[sub.date.str.startswith(month)])
                for month in months
            }
            detail["positive_months"] = sum(
                month["net_base"] > 0 for month in detail["months"].values()
            )
            pf = detail["net_base_pf"]
            detail["economic_gate"] = bool(
                detail["net_base"] > 0
                and detail["net_adverse"] > 0
                and (detail["net_base_pf_infinite"] or (pf is not None and pf >= 1.2))
                and len(sub) >= 60
                and detail["positive_months"] >= 3
            )
            result["tickers"][ticker] = detail
        result["economic_gate_all_tickers"] = all(
            x["economic_gate"] for x in result["tickers"].values()
        )
        stats[key] = result
        for ticker, date in expected:
            sub = trade.loc[(trade.ticker == ticker) & (trade.date == date)]
            calendar.append(
                dict(
                    policy=key,
                    ticker=ticker,
                    date=date,
                    trades=counts[(ticker, date)],
                    source_available=(ticker, date) in available,
                    net_base=float(sub.net_base.sum()),
                    net_adverse=float(sub.net_adverse.sum()),
                )
            )
    return stats, pd.DataFrame(calendar)


def frame_equal(expected, actual, context):
    require(set(expected.columns) == set(actual.columns), context + " columns")
    keys = [k for k in ("policy", "ticker", "date", "action_id") if k in expected]
    if not keys:
        keys = list(expected.columns[:1])
    left = expected.sort_values(keys, kind="stable").reset_index(drop=True)
    right = actual.sort_values(keys, kind="stable").reset_index(drop=True)
    require(len(left) == len(right), context + " rows")
    for col in left:
        a, b = left[col].to_numpy(), right[col].to_numpy()
        if a.dtype.kind == "f":
            require(
                np.allclose(a, b, rtol=1e-10, atol=1e-8, equal_nan=True),
                context + " " + col,
            )
        else:
            require(np.array_equal(a, b), context + " " + col)


class Evidence:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.binding = sha(self.root / "run_contract.json")
        self.verified = {str(self.root / "run_contract.json"): self.binding}
        self.markers = {}

    def file(self, path, digest):
        path = Path(path).resolve()
        require(sha(path) == digest, "Hash mismatch: " + str(path))
        self.verified[str(path)] = digest

    def complete(self, name):
        path = self.root / (name + ".complete.json")
        item = read_json(path)
        require(
            item.get("status") == "COMPLETE" and item.get("binding") == self.binding,
            "Incomplete/binding: " + name,
        )
        require(bool(item.get("files")), "Empty completed artifact: " + name)
        if name.startswith("models/"):
            suffixes = (".txt", ".fit_started.json")
        elif name.startswith("matrices/"):
            suffixes = (".npy",)
        elif "/daily/" in name:
            suffixes = ("_attempts.parquet", "_ledger.parquet")
        elif name in ("validation/summary", "test/summary"):
            suffixes = (".json",)
        elif (
            name in ("risk_scales", "validation_freeze")
            or name.startswith("feature_inputs/")
            or name.endswith("/score_h_diagnostic")
        ):
            suffixes = (".json",)
        else:
            suffixes = (".npz",)
        expected = {str((self.root / (name + suffix)).resolve()) for suffix in suffixes}
        if name in ("validation/summary", "test/summary"):
            expected.add(
                str((self.root / name).with_name("daily_calendar.parquet").resolve())
            )
        elif name == "prepare":
            expected = {
                str((self.root / ("samples/" + role + ".npz")).resolve())
                for role in ("teacher", "final")
            }
        sealed = {str((self.root / relative).resolve()) for relative in item["files"]}
        require(
            expected.issubset(sealed),
            "Consumed artifact absent from checkpoint: " + name,
        )
        for relative, digest in item["files"].items():
            target = (self.root / relative).resolve()
            require(target.is_relative_to(self.root), "Artifact path escapes root")
            self.file(target, digest)
        self.markers[name] = item
        self.verified[str(path)] = sha(path)
        return item

    def npz(self, name):
        record = self.complete(name)
        path = self.root / (name + ".npz")
        require(str(path) in self.verified, "NPZ not included in checkpoint: " + name)
        with np.load(path, allow_pickle=False) as arrays:
            return {k: arrays[k] for k in arrays.files}, record


def before(first, second, context):
    a = datetime.fromisoformat(first["completed_utc"])
    b = datetime.fromisoformat(second["completed_utc"])
    require(
        a.tzinfo is not None and b.tzinfo is not None and a <= b,
        "Checkpoint order: " + context,
    )


def canonical_subset(ticker, date, actions):
    """Independent implementation of declared serialization/topK/IPW."""
    require(
        not actions.action_id.duplicated().any() and len(actions) > 0,
        "Nonempty unique population",
    )
    population, selected, rows = [], [], []
    total = len(actions)
    for band in range(4):
        low, high = 60 + 79 * band, 138 + 79 * band
        bucket = actions.loc[actions.state_i.between(low, high)]
        priority = []
        for action, state in bucket[["action_id", "state_i"]].itertuples(
            index=False, name=None
        ):
            identity = [20261018, ticker, date, int(state), int(action)]
            digest = hashlib.sha256(
                json.dumps(identity, separators=(",", ":"), ensure_ascii=True).encode(
                    "utf-8"
                )
            ).hexdigest()
            priority.append((digest, int(state), int(action)))
        priority.sort()
        n, k = len(priority), min(32, len(priority))
        population.append(n)
        selected.append(k)
        for digest, state, action in priority[:k]:
            rows.append((action, state, band, digest, n / (total * k)))
    require(sum(population) == total, "Sampling state population outside horizon")
    return (
        rows,
        np.array(population, dtype=np.int64),
        np.array(selected, dtype=np.int64),
    )


def groups(sample):
    result = {}
    for i, pair in enumerate(
        zip(sample["ticker"].astype(str), sample["date"].astype(str))
    ):
        result.setdefault(pair, []).append(i)
    return {pair: np.array(rows, dtype=np.int64) for pair, rows in result.items()}


def check_sampling(sample, ticker, date, actions, positions, role):
    unique, pop, selected = canonical_subset(ticker, date, actions)
    require(unique, "Empty selected day")
    ids, states, bands, digests, weights = map(np.asarray, zip(*unique))
    multiplicity = 1 if role == "teacher" else 2
    expected = dict(
        action_id=np.repeat(ids, multiplicity),
        state_i=np.repeat(states, multiplicity),
        band_i=np.repeat(bands, multiplicity),
        identity_sha256=np.repeat(digests, multiplicity),
        weight=np.repeat(weights / multiplicity, multiplicity),
    )
    if role == "final":
        expected["has_filled_today"] = np.tile(
            np.array([0, 1], dtype=np.int8), len(unique)
        )
    else:
        require("has_filled_today" not in sample, "Teacher must not duplicate h")
    for name, values in expected.items():
        require(
            np.array_equal(sample[name][positions], values),
            "Sampling mismatch: " + name,
        )
    pi = np.flatnonzero(
        (sample["population_ticker"] == ticker) & (sample["population_date"] == date)
    )
    require(len(pi) == 1, "Population metadata identity")
    require(
        np.array_equal(sample["population_by_band"][pi[0]], pop),
        "Population band counts",
    )
    require(
        np.array_equal(sample["selected_by_band"][pi[0]], selected),
        "Selected band counts",
    )


def read_source(evidence, index, pair, filename, columns=None):
    row = index.loc[pair]
    path = Path(row.day_root) / filename
    digest = row[Path(filename).stem + "_sha256"]
    evidence.file(path, digest)
    data = pd.read_parquet(path, columns=columns)
    require(sha(path) == digest, "Source changed during read")
    return data


def fit_signature(evidence, name, matrix_path, target, weights, shape, config):
    record = evidence.complete("models/" + name)
    item = read_json(evidence.root / ("models/" + name + ".fit_started.json"))
    require(item["binding"] == evidence.binding, "Fit binding")
    equal(item["config"], config, "Fit config")
    require(item["shape"] == list(shape), "Fit shape")
    require(item["matrix_sha256"] == sha(matrix_path), "Fit matrix hash")
    require(item["target_sha256"] == array_sha(target), "Fit target hash")
    require(item["weight_sha256"] == array_sha(weights), "Fit weight hash")
    require(
        datetime.fromisoformat(item["started_utc"])
        <= datetime.fromisoformat(record["completed_utc"]),
        "Fit chronology",
    )


def audit_training(evidence, index, scales, config):
    final_targets, _ = evidence.npz("final_targets")
    teacher_marker = evidence.complete("models/teacher")
    sample_counts = {}
    premiums, premium_weights = {t: [] for t in TICKERS}, {t: [] for t in TICKERS}
    for role, ndays, columns in TRAIN_LAYOUT:
        sample, _ = evidence.npz("samples/" + role)
        daygroups = groups(sample)
        require(
            list(daygroups) == sorted(daygroups), "Canonical global ticker/date order"
        )
        require(
            np.array_equal(
                np.concatenate(list(daygroups.values())),
                np.arange(len(sample["action_id"])),
            ),
            "Contiguous canonical day groups",
        )
        require(
            len(daygroups) == int(sample["n_days"]) == ndays, "Sample calendar count"
        )
        low, high = (
            ("20230101", "20230630") if role == "teacher" else ("20230701", "20241231")
        )
        expected_days = {pair for pair in index.index if low <= pair[1] <= high}
        require(set(daygroups) == expected_days, "Training sample calendar")
        require(
            float(sample["normalization_factor"]) == len(sample["action_id"]) / ndays,
            "Normalization scalar",
        )
        require(
            np.array_equal(
                sample["fit_weight"],
                sample["weight"] * (len(sample["action_id"]) / ndays),
            ),
            "Fit weights",
        )
        evidence.complete("matrices/" + role)
        matrix_path = evidence.root / ("matrices/" + role + ".npy")
        matrix = np.load(matrix_path, mmap_mode="r", allow_pickle=False)
        require(
            matrix.shape == (len(sample["action_id"]), columns)
            and matrix.dtype == np.float32,
            "Matrix schema",
        )
        net = np.empty(len(matrix), dtype=np.float64)
        residual = np.empty_like(net) if role == "final" else None
        for number, ((ticker, date), positions) in enumerate(daygroups.items(), 1):
            pair = (ticker, date)
            actions = read_source(
                evidence, index, pair, "actions.parquet", ["action_id", "state_i"]
            )
            check_sampling(sample, ticker, date, actions, positions, role)
            key = ticker + "/" + date
            chunk, _ = evidence.npz("chunks/" + role + "/" + key)
            require(
                np.array_equal(chunk["positions"], positions), "Chunk position identity"
            )
            require(
                chunk["x"].shape == (len(positions), columns)
                and chunk["x"].dtype == np.float32
                and np.isfinite(chunk["x"]).all(),
                "Chunk matrix shape/values",
            )
            require(np.array_equal(matrix[positions], chunk["x"]), "Matrix/chunk bytes")
            labels = read_source(
                evidence,
                index,
                pair,
                "labels.parquet",
                ["action_id", "status", "exit_i", "net_base", "entry_ask"],
            )
            lab = aligned(actions, labels)
            indices = pd.Index(actions.action_id).get_indexer(
                sample["action_id"][positions]
            )
            require(np.all(indices >= 0), "Training identity join")
            net[positions] = lab.net_base.to_numpy(float)[indices]
            if role == "teacher":
                premium = lab.entry_ask.to_numpy(float)[indices] * 100
                filled = lab.status.to_numpy()[indices] == "FILLED"
                require(
                    np.array_equal(chunk["net"], net[positions]), "Teacher net chunk"
                )
                require(
                    np.array_equal(chunk["premium"], premium, equal_nan=True)
                    and np.array_equal(chunk["filled"], filled),
                    "Teacher premium/status",
                )
                valid = filled & np.isfinite(premium) & (premium > 0)
                premiums[ticker].extend(premium[valid].tolist())
                premium_weights[ticker].extend(
                    sample["weight"][positions][valid].tolist()
                )
            else:
                require(
                    np.array_equal(
                        chunk["x"][:, -1], sample["has_filled_today"][positions]
                    ),
                    "Matrix agent flag",
                )
                require(
                    np.array_equal(chunk["x"][::2, :-1], chunk["x"][1::2, :-1]),
                    "Paired causal features",
                )
                choice, cm = evidence.npz("teacher_choices/" + key)
                before(teacher_marker, cm, "teacher before continuation")
                require(
                    str(choice["teacher_sha256"])
                    == sha(evidence.root / "models/teacher.txt"),
                    "Teacher model binding",
                )
                require(
                    str(choice["scale_sha256"])
                    == sha(evidence.root / "risk_scales.json"),
                    "Teacher scale binding",
                )
                require(
                    np.array_equal(choice["action_id"], actions.action_id)
                    and np.array_equal(choice["state_i"], actions.state_i),
                    "Teacher score identities",
                )
                require(
                    np.array_equal(choice["scores"][:, 0], choice["scores"][:, 1]),
                    "Teacher h-independent scores",
                )
                choices = ranked_choices(actions, choice["scores"])
                require(
                    np.array_equal(choices, choice["choices"]), "Fixed teacher choices"
                )
                values, advantage = policy_returns(
                    actions, lab, choices, scales[ticker]
                )
                target, tm = evidence.npz("rollouts/" + key)
                before(cm, tm, "choices before rollout targets")
                require(
                    str(target["choice_sha256"])
                    == sha(evidence.root / ("teacher_choices/" + key + ".npz")),
                    "Target choice binding",
                )
                require(
                    np.array_equal(target["positions"], positions), "Target positions"
                )
                require(
                    np.allclose(target["values"], values, rtol=1e-10, atol=1e-8),
                    "Independent policy returns",
                )
                expected = advantage[indices, sample["has_filled_today"][positions]]
                require(
                    np.allclose(target["residual"], expected, rtol=1e-10, atol=1e-8),
                    "Independent residual targets",
                )
                require(
                    np.array_equal(target["net"], net[positions]), "Rollout net targets"
                )
                residual[positions] = expected
            if number % 100 == 0:
                print(
                    json.dumps(
                        dict(
                            stage="audit_training",
                            role=role,
                            days=number,
                            total=len(daygroups),
                        )
                    ),
                    flush=True,
                )
        divisor = np.array([scales[str(t)] for t in sample["ticker"]], dtype=np.float64)
        if role == "teacher":
            for ticker in TICKERS:
                values, w = (
                    np.asarray(premiums[ticker]),
                    np.asarray(premium_weights[ticker]),
                )
                require(len(values) > 0, "No positive filled teacher premium")
                order = np.argsort(values, kind="stable")
                midpoint = np.searchsorted(
                    np.cumsum(w[order]), w.sum() / 2, side="left"
                )
                equal(
                    float(values[order[midpoint]]),
                    scales[ticker],
                    "H1 weighted risk scale",
                )
            fit_signature(
                evidence,
                "teacher",
                matrix_path,
                net / divisor,
                sample["fit_weight"],
                matrix.shape,
                config,
            )
        else:
            for name, values in (
                ("net", net),
                ("residual", residual),
                ("divisor", divisor),
                ("fit_weight", sample["fit_weight"]),
            ):
                match = (
                    np.allclose(final_targets[name], values, rtol=1e-10, atol=1e-8)
                    if name == "residual"
                    else np.array_equal(final_targets[name], values)
                )
                require(match, "Final target " + name)
            # Fit hashes bind the exact producer arrays, separately checked numerically above.
            for model, field in (
                ("net_control", "net"),
                ("causal_residual", "residual"),
            ):
                fit_signature(
                    evidence,
                    model,
                    matrix_path,
                    final_targets[field] / divisor,
                    sample["fit_weight"],
                    matrix.shape,
                    config,
                )
        sample_counts[role] = dict(days=ndays, rows=len(matrix), columns=columns)
        del matrix
    return sample_counts


def verify_feature_inputs(evidence, index, feature_root, feature_contract):
    names = [
        "state_i",
        "contract_i",
        "right",
        "strike",
        "selected_delta",
        "delta_bucket",
        "target_center",
        "target_source_mask",
        "stop_center",
        "stop_source_mask",
        "band",
    ]
    for number, ((ticker, date), source) in enumerate(index.iterrows(), 1):
        key = ticker + "/" + date
        evidence.complete("feature_inputs/" + key)
        paths = read_json(evidence.root / ("feature_inputs/" + key + ".json"))
        folder = feature_root / ticker / date
        expected = {
            str((folder / name).resolve())
            for name in ("features.npz", "features.json", "actions.npz", "actions.json")
        }
        require(set(paths) == expected, "Feature inputs file universe")
        for path, digest in paths.items():
            evidence.file(path, digest)
        for name in ("features", "actions"):
            meta = read_json(folder / (name + ".json"))
            require(meta.get("outcomes_read") is False, "Feature outcome-free metadata")
            require(
                meta["sha256"] == paths[str((folder / (name + ".npz")).resolve())],
                "Feature NPZ metadata",
            )
            require(
                meta["binding"]["source_sha256"] == source.cache_npz_sha256
                and meta["binding"]["source_metadata_sha256"]
                == source.cache_meta_sha256,
                "Feature audited cache binding",
            )
            equal(
                meta["binding"]["dependencies"],
                feature_contract["dependencies"],
                "Feature dependency binding",
            )
        action_meta = read_json(folder / "actions.json")
        actions = read_source(
            evidence, index, (ticker, date), "actions.parquet", ["action_id", *names]
        )
        require(
            array_sha(actions.to_numpy(dtype=np.float64))
            == action_meta["binding"]["action_inputs_sha256"],
            "Action input signature",
        )
        with np.load(folder / "actions.npz", allow_pickle=False) as packed:
            require(
                len(packed["action_id"]) == len(actions)
                and np.array_equal(
                    np.sort(packed["action_id"]), np.sort(actions.action_id)
                ),
                "Feature offered-action identity",
            )
        if number % 250 == 0:
            print(
                json.dumps(
                    dict(stage="audit_feature_hashes", days=number, total=len(index))
                ),
                flush=True,
            )


def audit_period(evidence, index, dates, period, model_hashes, freeze_marker):
    low, high = (
        ("20250101", "20251231") if period == "validation" else ("20260101", "20260630")
    )
    expected = [
        (ticker, date) for ticker in TICKERS for date in dates if low <= date <= high
    ]
    pairs = sorted(pair for pair in index.index if low <= pair[1] <= high)
    available = set(pairs)
    attempts_all, ledgers_all = [], []
    diagnostic = {model: dict(actions=0, score_h0_lt_h1=0) for model in MODELS}
    for number, pair in enumerate(pairs, 1):
        ticker, date = pair
        key = ticker + "/" + date
        predname = period + "/predictions/" + key
        pred, pm = evidence.npz(predname)
        before(
            evidence.markers["feature_inputs/" + key],
            pm,
            "feature seal before prediction",
        )
        if period == "test":
            before(freeze_marker, pm, "validation freeze before test scores")
        actions = read_source(evidence, index, pair, "actions.parquet")
        require(
            np.array_equal(pred["action_id"], actions.action_id)
            and np.array_equal(pred["state_i"], actions.state_i),
            "Prediction action identity",
        )
        for model in MODELS:
            before(evidence.markers["models/" + model], pm, "model before prediction")
            require(
                str(pred[model + "_sha256"]) == model_hashes[model],
                "Prediction model binding",
            )
            require(
                pred[model].shape == (len(actions), 2)
                and np.isfinite(pred[model]).all(),
                "Prediction shape/finite",
            )
            diagnostic[model]["actions"] += len(actions)
            diagnostic[model]["score_h0_lt_h1"] += int(
                np.sum(pred[model][:, 0] < pred[model][:, 1])
            )
        dailyname = period + "/daily/" + key
        daily = evidence.complete(dailyname)
        before(pm, daily, "prediction before economic daily checkpoint")
        require(
            daily["extra"]["prediction_sha256"]
            == sha(evidence.root / (predname + ".npz")),
            "Daily prediction hash",
        )
        labels = read_source(evidence, index, pair, "labels.parquet")
        per_attempt, per_ledger = [], []
        for model in MODELS:
            for threshold in THRESHOLDS:
                tried, trades = schedule(actions, labels, pred[model], threshold)
                for frame in (tried, trades):
                    frame["ticker"], frame["date"] = ticker, date
                    frame["policy"] = f"{model}__{int(threshold)}"
                per_attempt.append(tried)
                per_ledger.append(trades)
        tries, ledger = (
            pd.concat(per_attempt, ignore_index=True),
            pd.concat(per_ledger, ignore_index=True),
        )
        frame_equal(
            tries,
            pd.read_parquet(evidence.root / (dailyname + "_attempts.parquet")),
            "Daily attempts " + key,
        )
        frame_equal(
            ledger,
            pd.read_parquet(evidence.root / (dailyname + "_ledger.parquet")),
            "Daily ledger " + key,
        )
        # Retain only metrics fields after exact comparison; no all-action tables accumulate.
        metrics = ["ticker", "date", "policy", *LABEL_COLUMNS]
        attempts_all.append(tries[["ticker", "date", "policy", "status"]])
        ledgers_all.append(ledger[metrics])
        if number % 100 == 0:
            print(
                json.dumps(
                    dict(
                        stage="audit_economics",
                        period=period,
                        days=number,
                        total=len(pairs),
                    )
                ),
                flush=True,
            )
    attempts, ledger = (
        pd.concat(attempts_all, ignore_index=True),
        pd.concat(ledgers_all, ignore_index=True),
    )
    stats, calendar = summarize_period(attempts, ledger, expected, available)
    evidence.complete(period + "/summary")
    equal(
        stats,
        read_json(evidence.root / (period + "/summary.json")),
        period + " summary",
    )
    frame_equal(
        calendar,
        pd.read_parquet(evidence.root / (period + "/daily_calendar.parquet")),
        period + " daily calendar",
    )
    evidence.complete(period + "/score_h_diagnostic")
    actual_diag = read_json(evidence.root / (period + "/score_h_diagnostic.json"))
    equal(diagnostic, actual_diag["models"], "Score h diagnostic")
    require(
        actual_diag["adjustment"] == "NONE_DIAGNOSTIC_ONLY",
        "Unexpected score adjustment",
    )
    coverage = calendar.copy()
    coverage["observation_status"] = np.where(
        ~coverage.source_available,
        "NO_EVALUABLE_MISSING_SOURCE",
        np.where(coverage.trades > 0, "OBSERVED_FILLED", "OBSERVED_ZERO_FILLED"),
    )
    coverage["observed_trades"] = coverage.trades.where(coverage.source_available, None)
    gates = {}
    for key in POLICIES:
        block = coverage.loc[coverage.policy == key]
        unknown = int((~block.source_available).sum())
        zeros = int(((block.trades == 0) & block.source_available).sum())
        gates[key] = dict(
            expected=len(block),
            available=len(block) - unknown,
            missing_no_evaluable=unknown,
            observed_zero_days=zeros,
            observable_daily_pass=zeros == 0,
            full_calendar_daily_status="NO_EVALUABLE_MISSING_SOURCE"
            if unknown
            else ("PASS" if zeros == 0 else "FAIL_OBSERVED_ZERO"),
        )
    return stats, coverage, gates


def run_audit(root, out):
    start = time.perf_counter()
    evidence = Evidence(root)
    contract = read_json(root / "run_contract.json")
    require(
        contract["version"] == "CAUSAL_FIXED_POLICY_ROLLOUT_V1"
        and contract["seed"] == 20261018,
        "Run version/seed",
    )
    expected_config = dict(
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
    equal(contract["config"], expected_config, "Method config")
    # Completion admission happens before any daily labels are parsed.
    for name in (
        "prepare",
        "risk_scales",
        "models/teacher",
        "models/net_control",
        "models/causal_residual",
        "samples/teacher",
        "samples/final",
        "matrices/teacher",
        "matrices/final",
        "final_targets",
        "validation/summary",
        "validation/score_h_diagnostic",
        "validation_freeze",
        "test/summary",
        "test/score_h_diagnostic",
    ):
        evidence.complete(name)
    for name, digest in contract["dependencies"].items():
        evidence.file(root / "executed_code" / name, digest)
    engine = Path(contract["engine_root"])
    source_binding = contract["source_audit"]["binding"]
    require(
        Path(source_binding["engine_root"]).resolve() == engine.resolve(),
        "Engine audited root",
    )
    evidence.file(engine / "index.parquet", source_binding["index_sha256"])
    evidence.file(
        engine / "dataset_contract.json", source_binding["dataset_contract_sha256"]
    )
    evidence.file(engine / "completion.json", source_binding["completion_sha256"])
    columns = [
        "ticker",
        "date",
        "status",
        "day_root",
        "actions_sha256",
        "labels_sha256",
        "cache_npz_sha256",
        "cache_meta_sha256",
    ]
    rawindex = pd.read_parquet(engine / "index.parquet", columns=columns)
    rawindex["date"] = rawindex.date.astype(str)
    require(
        len(rawindex) == 2601 and not rawindex.duplicated(["ticker", "date"]).any(),
        "Full source universe",
    )
    require(
        rawindex.status.value_counts().to_dict()
        == {"COMPLETE": 2595, "MISSING_SOURCE": 6},
        "Source coverage counts",
    )
    require(
        set(
            rawindex.loc[
                rawindex.status == "MISSING_SOURCE", ["ticker", "date"]
            ].itertuples(index=False, name=None)
        )
        == MISSING,
        "Missing identities",
    )
    import exchange_calendars as xc

    schedule = xc.get_calendar("XNYS").schedule.loc["2023-01-03":"2026-06-30"]
    dates = (
        schedule.loc[
            (schedule.close - schedule.open) == pd.Timedelta(hours=6, minutes=30)
        ]
        .index.strftime("%Y%m%d")
        .tolist()
    )
    require(
        len(dates) == 867
        and set(rawindex[["ticker", "date"]].itertuples(index=False, name=None))
        == {(t, d) for t in TICKERS for d in dates},
        "Full calendar identities",
    )
    index = (
        rawindex.loc[rawindex.status == "COMPLETE"]
        .set_index(["ticker", "date"])
        .sort_index()
    )
    feature_root = Path(contract["feature_root"])
    evidence.file(
        feature_root / "feature_contract.json", contract["feature_contract_sha256"]
    )
    feature_contract = read_json(feature_root / "feature_contract.json")
    verify_feature_inputs(evidence, index, feature_root, feature_contract)
    scales = read_json(root / "risk_scales.json")
    require(
        set(scales) == set(TICKERS)
        and all(np.isfinite(x) and x > 0 for x in scales.values()),
        "Risk scales",
    )
    sample_counts = audit_training(evidence, index, scales, expected_config)
    model_hashes = {model: sha(root / ("models/" + model + ".txt")) for model in MODELS}
    freeze_marker = evidence.complete("validation_freeze")
    validation, val_calendar, val_gates = audit_period(
        evidence, index, dates, "validation", model_hashes, freeze_marker
    )
    expected_freeze = selection(validation, scales)
    expected_freeze.update(
        model_hashes=model_hashes,
        risk_scales_sha256=sha(root / "risk_scales.json"),
        validation_summary_sha256=sha(root / "validation/summary.json"),
    )
    equal(
        expected_freeze,
        read_json(root / "validation_freeze.json"),
        "Validation selection/null freeze",
    )
    before(
        evidence.markers["validation/summary"],
        freeze_marker,
        "validation summary before selection",
    )
    _, test_calendar, test_gates = audit_period(
        evidence, index, dates, "test", model_hashes, freeze_marker
    )
    coverage = pd.concat(
        [val_calendar.assign(period="validation"), test_calendar.assign(period="test")],
        ignore_index=True,
    )
    coverage.to_csv(out / "daily_coverage.csv", index=False)
    # Rehash the retained evidence once more at completion; no silent mid-audit mutation.
    for path, digest in evidence.verified.items():
        require(sha(path) == digest, "Evidence changed during audit: " + path)
    result = dict(
        status="PASS_INDEPENDENT_CAUSAL_ROLLOUT_ECONOMIC_AUDIT_GIVEN_SEALED_SCORES",
        scope="Independent sampling,targets,matrix-chunk/fit-signature verification and economics; no refits or prediction regeneration",
        refits=0,
        predictions_regenerated=False,
        raw_features_recomputed=False,
        calendar_expected=2601,
        available=2595,
        missing_no_evaluable=6,
        training=sample_counts,
        validation_gates=val_gates,
        test_gates=test_gates,
        selection=expected_freeze["selected_policy"],
        source_binding=source_binding,
        run_contract_sha256=evidence.binding,
        auditor_sha256=sha(Path(__file__)),
        verified_artifacts=evidence.verified,
        daily_coverage_sha256=sha(out / "daily_coverage.csv"),
        terminal_penalty_in_economic_pnl=False,
        wall_seconds=time.perf_counter() - start,
        completed_utc=datetime.now(timezone.utc).isoformat(),
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    require(
        not out.is_relative_to(root) and out != root, "Audit must use a separate root"
    )
    out.mkdir(parents=True, exist_ok=False)
    try:
        result = run_audit(root, out)
    except Exception:
        result = dict(
            status="FAILED_INDEPENDENT_CAUSAL_ROLLOUT_AUDIT",
            error=traceback.format_exc(),
            auditor_sha256=sha(Path(__file__)),
            completed_utc=datetime.now(timezone.utc).isoformat(),
        )
        (out / "audit.json").write_text(
            json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
        )
        raise
    (out / "audit.json").write_text(
        json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
    )
    (out / "audit_causal_rollout_economics.executed.py").write_bytes(
        Path(__file__).read_bytes()
    )
    print(
        json.dumps({k: v for k, v in result.items() if k != "verified_artifacts"}),
        flush=True,
    )


if __name__ == "__main__":
    main()
