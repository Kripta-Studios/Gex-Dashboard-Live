"""One post-result episode representation variant; original producer is immutable."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import time
import uuid

for _name in (
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "OMP_NUM_THREADS",
):
    os.environ[_name] = "1"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import lightgbm as lgb  # noqa: E402
import train_models as base  # noqa: E402
import build_episode_features as episode_builder  # noqa: E402
import episode_features  # noqa: E402
import episode_policy  # noqa: E402

MODELS = ("gbt_net", "gbt_net_episode")
THRESHOLDS = (0.0, 5.0, 10.0)
sha = base.sha
TICKERS = base.TICKERS


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic(path, writer):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial-" + uuid.uuid4().hex)
    writer(temporary)
    with temporary.open("rb+") as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_json(path, value):
    atomic(
        path,
        lambda p: p.write_text(
            json.dumps(value, indent=2, allow_nan=False), encoding="utf-8"
        ),
    )


@contextmanager
def output_lock(out):
    import msvcrt

    with (out / "writer.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise ValueError("Episode learner root is already locked") from error
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def preserve(path, out, reason):
    path, out = Path(path).resolve(), Path(out).resolve()
    if not path.exists():
        return
    if path == out or not path.is_relative_to(out):
        raise ValueError("Preservation path escapes output")
    archive = out / "preserved" / uuid.uuid4().hex
    archive.mkdir(parents=True)
    destination = archive / path.name
    files = list(path.rglob("*")) if path.is_dir() else [path]
    hashes = {str(p.relative_to(out)): sha(p) for p in files if p.is_file()}
    write_json(
        archive / "manifest.json",
        {"reason": reason, "source": str(path), "hashes": hashes},
    )
    path.rename(destination)


def verify_hashes(hashes):
    for name, expected in hashes.items():
        if sha(name) != expected:
            raise ValueError("Sealed input/output changed: " + str(name))


class Stages:
    def __init__(self, out, identity):
        self.out = out
        self.identity = identity

    def load(self, name):
        path = self.out / (name + ".complete.json")
        if not path.exists():
            return None
        record = read(path)
        if record["identity_sha256"] != self.identity:
            raise ValueError("Stage identity differs")
        verify_hashes(record["artifacts"])
        verify_hashes(record["sources"])
        return record

    def publish(self, name, artifacts, sources, **extra):
        record = {
            "identity_sha256": self.identity,
            "artifacts": {str(Path(p).resolve()): sha(p) for p in artifacts},
            "sources": dict(sources),
            **extra,
        }
        verify_hashes(record["sources"])
        write_json(self.out / (name + ".complete.json"), record)
        return record


def join_episodes(arrays, states):
    keys = np.asarray(arrays["state_i"])
    if pd.Index(keys).has_duplicates:
        raise ValueError("Duplicate episode state key")
    indices = pd.Index(keys).get_indexer(np.asarray(states))
    if (indices < 0).any():
        raise ValueError("Missing causal episode state")
    values = arrays["values"][indices]
    masks = arrays["valid"][indices]
    if values.shape[1] != 35 or masks.shape != values.shape or masks.dtype != bool:
        raise ValueError("Episode dimensions/masks differ")
    if not np.isfinite(values).all() or np.any(values[~masks] != 0):
        raise ValueError("Invalid episode value/missingness")
    result = np.concatenate(
        [values.astype(np.float32), masks.astype(np.float32)], axis=1
    )
    if not np.isfinite(result).all():
        raise ValueError("Episode float32 overflow")
    return result


def prefix_identical(left, right, width=1954):
    if (
        left.shape[0] != right.shape[0]
        or left.dtype != np.float32
        or right.dtype != np.float32
    ):
        return False
    for start in range(0, len(left), 4096):
        a = np.ascontiguousarray(left[start : start + 4096, :width]).view(np.uint32)
        b = np.ascontiguousarray(right[start : start + 4096, :width]).view(np.uint32)
        if not np.array_equal(a, b):
            return False
    return True


class Episodes:
    def __init__(self, root, seal):
        self.root, self.seal, self.hashes = root, seal, {}
        self.contract = read(root / "contract.json")
        summary = read(root / "summary.json")
        if (
            summary["status"] != "PASS_PREPARED_CAUSAL_EPISODE_BUILD"
            or summary["days"] != 2595
            or summary["missing_days"] != 6
        ):
            raise ValueError("Episode coverage gate failed")
        for name in ("contract", "index"):
            if sha(root / (name + ".json")) != summary[name + "_sha256"]:
                raise ValueError("Episode global binding differs")
        self.index = {(r["ticker"], r["date"]): r for r in read(root / "index.json")}
        if len(self.index) != 2595:
            raise ValueError("Episode key coverage differs")
        self.hashes.update(
            {
                str((root / n).resolve()): sha(root / n)
                for n in ("contract.json", "index.json", "summary.json")
            }
        )

    def get(self, day):
        path = self.root / day.ticker / day.date / "episodes.npz"
        meta_path = path.with_suffix(".json")
        meta = read(meta_path)
        row = self.seal.index.loc[(day.ticker, day.date)]
        expected = {
            "contract": self.contract,
            "ticker": day.ticker,
            "date": day.date,
            "split": row["split"],
            "source_root": str(day.oracle),
            "states_sha256": row.states_sha256,
            "levels_sha256": row.levels_sha256,
        }
        if (
            meta["binding"] != expected
            or meta["names"] != list(episode_features.FEATURE_NAMES)
            or meta["outcomes_read"] is not False
        ):
            raise ValueError("Episode causal binding differs")
        if (
            sha(path) != self.index[(day.ticker, day.date)]["sha256"]
            or sha(path) != meta["sha256"]
        ):
            raise ValueError("Episode day hash differs")
        for name in ("states.parquet", "levels.parquet"):
            self.seal.check(day, name)
        with np.load(path, allow_pickle=False) as stored:
            arrays = {k: stored[k] for k in stored.files}
        episode_builder.validate_arrays(arrays)
        self.hashes.update({str(p.resolve()): sha(p) for p in (path, meta_path)})
        return arrays


def build_matrix(original, sample, days, episodes, out, stages):
    complete = stages.load("matrix")
    if complete:
        episodes.hashes.update(complete["sources"])
        return np.load(out / "train_x.npy", mmap_mode="r")
    target = out / "train_x.npy"
    preserve(target, out, "Uncommitted training matrix")
    old = np.load(original / "train_x.npy", mmap_mode="r")
    if (
        old.shape != (270377, 1954)
        or len(sample) != 270377
        or not np.array_equal(sample.sample_i, np.arange(len(sample)))
    ):
        raise ValueError("Frozen sample shape/order differs")
    if not (sample.date.astype(str) < "20250101").all():
        raise ValueError("Nontraining sample row")
    temporary = target.with_name(target.name + ".partial-" + uuid.uuid4().hex)
    matrix = np.lib.format.open_memmap(
        temporary, mode="w+", dtype=np.float32, shape=(len(sample), 2024)
    )
    for start in range(0, len(sample), 4096):
        matrix[start : start + 4096, :1954] = old[start : start + 4096]
    lookup = {d.key: d for d in days}
    for number, (key, rows) in enumerate(sample.groupby("day_key", sort=True)):
        day = lookup[key]
        if (
            not (rows.ticker == day.ticker).all()
            or not (rows.date.astype(str) == day.date).all()
        ):
            raise ValueError("Sample day key mismatch")
        episodes.seal.check(day, "actions.parquet")
        actions = pd.read_parquet(
            day.oracle / "actions.parquet", columns=["action_id", "state_i"]
        ).set_index("action_id")
        if not np.array_equal(
            actions.loc[rows.action_id, "state_i"].to_numpy(), rows.state_i.to_numpy()
        ):
            raise ValueError("Sample action/state key differs")
        matrix[rows.sample_i.to_numpy(), 1954:] = join_episodes(
            episodes.get(day), rows.state_i
        )
        if number % 100 == 0:
            print(json.dumps({"stage": "matrix", "day": number}), flush=True)
    matrix.flush()
    if not prefix_identical(matrix, old):
        raise ValueError("Original 1954 columns are not bit-identical")
    del matrix, old
    with temporary.open("rb+") as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, target)
    sources = {
        **episodes.hashes,
        **episodes.seal.hashes,
        str((original / "train_x.npy").resolve()): sha(original / "train_x.npy"),
        str((original / "training_sample.parquet").resolve()): sha(
            original / "training_sample.parquet"
        ),
    }
    stages.publish(
        "matrix",
        [target],
        sources,
        rows=270377,
        columns=2024,
        prefix_bit_identical=True,
    )
    return np.load(target, mmap_mode="r")


def fit_variant(matrix, sample, scales, config, out, stages):
    target = out / "gbt_net_episode.txt"
    if stages.load("model"):
        return lgb.Booster(model_file=str(target))
    preserve(target, out, "Uncommitted model publication")
    model = lgb.LGBMRegressor(**config)
    model.fit(
        matrix,
        sample.net_base.to_numpy(float) / sample.ticker.map(scales).to_numpy(float),
        sample_weight=sample.weight.to_numpy(float),
    )
    atomic(target, lambda p: model.booster_.save_model(str(p)))
    check = lgb.Booster(model_file=str(target))
    if check.num_trees() != 200 or check.num_feature() != 2024:
        raise ValueError("Variant model structure differs")
    stages.publish(
        "model",
        [target],
        {
            str((out / name).resolve()): sha(out / name)
            for name in (
                "matrix.complete.json",
                "training_sample.parquet",
                "normalizers.json",
                "gbt_config.json",
            )
        },
        new_fits=1,
    )
    print(json.dumps({"stage": "model_complete", "new_fits": 1}), flush=True)
    return check


def predict_day(
    day,
    period,
    store,
    episodes,
    models,
    scales,
    original,
    old_hashes,
    target,
    out,
    identity,
):
    store.seal.check(day, "actions.parquet")
    actions = pd.read_parquet(day.oracle / "actions.parquet")
    episode = episodes.get(day)
    pack, ai, si = store.rows(day.key, actions.action_id)
    old_path = original / period / (day.ticker + "_" + day.date + ".npz")
    if sha(old_path) != old_hashes[old_path.name]:
        raise ValueError("Original control predictions changed")
    with np.load(old_path, allow_pickle=False) as old:
        if not np.array_equal(old["action_ids"], actions.action_id):
            raise ValueError("Control action order differs")
        control = old["gbt_net"].copy()
    sources = {
        str(p.resolve()): sha(p)
        for p in (
            old_path,
            day.oracle / "actions.parquet",
            episodes.root / day.ticker / day.date / "episodes.npz",
            episodes.root / day.ticker / day.date / "episodes.json",
            day.features / "features.npz",
            day.features / "features.json",
            day.features / "actions.npz",
            day.features / "actions.json",
        )
    }
    binding = {
        "identity": identity,
        "sources": sources,
        "variant_sha256": sha(out / "gbt_net_episode.txt"),
    }
    path = target / old_path.name
    marker = path.with_suffix(".complete.json")
    if marker.exists():
        meta = read(marker)
        if meta["binding"] != binding or sha(path) != meta["sha256"]:
            raise ValueError("Completed prediction cache changed")
        with np.load(path, allow_pickle=False) as saved:
            if set(saved.files) != {"action_ids", *MODELS} or any(
                saved[m].shape != (len(actions),) or not np.isfinite(saved[m]).all()
                for m in MODELS
            ):
                raise ValueError("Cached prediction schema/finiteness differs")
            if not np.array_equal(
                saved["action_ids"], actions.action_id
            ) or not np.array_equal(saved["gbt_net"], control):
                raise ValueError("Cached prediction identity differs")
            return actions, {name: saved[name].copy() for name in MODELS}, sources
    preserve(path, out, "Uncommitted prediction cache")
    scores = {"gbt_net": control, "gbt_net_episode": np.empty(len(actions), np.float64)}
    for start in range(0, len(actions), base.BATCH):
        indices = slice(start, start + base.BATCH)
        x = base.flatten_gbt(pack, ai[indices], si[indices])
        reproduced = models["gbt_net"].predict(x, num_threads=4) * scales[day.ticker]
        if not np.array_equal(reproduced, control[indices]):
            raise ValueError("Existing control score reproduction failed")
        extra = join_episodes(episode, actions.state_i.to_numpy()[indices])
        augmented = np.concatenate([x, extra], axis=1)
        scores["gbt_net_episode"][indices] = (
            models["gbt_net_episode"].predict(augmented, num_threads=4)
            * scales[day.ticker]
        )
    if any(not np.isfinite(v).all() for v in scores.values()):
        raise FloatingPointError("Nonfinite episode predictions")

    def save(p):
        with p.open("wb") as stream:
            np.savez_compressed(
                stream, action_ids=actions.action_id.to_numpy(), **scores
            )

    atomic(path, save)
    write_json(
        marker,
        {"binding": binding, "sha256": sha(path), "control_reproduced_exactly": True},
    )
    return actions, scores, sources


def compliance(ledger, calendar, available):
    counts = (
        ledger.groupby(["date", "ticker"]).size()
        if len(ledger)
        else pd.Series(dtype=int)
    )
    if any((ticker, date) not in available for date, ticker in counts.index):
        raise ValueError("A fill cannot belong to a NO_EVALUABLE day")
    rows = []
    for date in calendar:
        for ticker in TICKERS:
            observed = (ticker, date) in available
            fills = int(counts.get((date, ticker), 0))
            rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "source_status": "EVALUABLE" if observed else "NO_EVALUABLE",
                    "fills": fills if observed else None,
                    "meets_minimum": fills >= 1 if observed else None,
                }
            )
    frame = pd.DataFrame(rows)
    observed = frame.source_status == "EVALUABLE"
    summary = {
        "expected_ticker_days": len(frame),
        "available_ticker_days": int(observed.sum()),
        "no_evaluable_ticker_days": int((~observed).sum()),
        "days_without_fill": int((frame.loc[observed, "fills"] < 1).sum()),
        "minimum_daily_pass": bool(frame.loc[observed, "meets_minimum"].all()),
        "coverage_pass": bool(observed.all()),
    }
    summary["viable"] = summary["minimum_daily_pass"] and summary["coverage_pass"]
    return frame, summary


def choices_and_selection(summaries, scales, models=MODELS):
    choices = []
    for model in models:
        for threshold in THRESHOLDS:
            ident = base.policy_id(model, threshold)
            entry = summaries[ident]
            choices.append(
                {
                    "policy": ident,
                    "model": model,
                    "threshold": threshold,
                    "selection_score": float(
                        sum(
                            entry["tickers"][t]["base_net_usd"] / scales[t]
                            for t in TICKERS
                        )
                    ),
                    "daily_viable": entry["daily_compliance"]["viable"],
                }
            )
    viable = [c for c in choices if c["daily_viable"]]
    selected = max(viable, key=lambda c: c["selection_score"]) if viable else None
    diagnostic = max(choices, key=lambda c: c["selection_score"])
    return {
        "selection_status": "DAILY_COMPLIANT_POLICY_SELECTED"
        if selected
        else "FAIL_NO_DAILY_COMPLIANT_POLICY",
        "selected_policy": selected,
        "diagnostic_policy": diagnostic,
        "approved": False,
        "choices": choices,
    }


def error_moments(predicted, observed):
    predicted, observed = np.asarray(predicted, float), np.asarray(observed, float)
    residual = predicted - observed
    return np.array(
        [
            len(observed),
            residual.sum(),
            np.abs(residual).sum(),
            np.square(residual).sum(),
            observed.sum(),
            np.square(observed).sum(),
        ],
        float,
    )


def error_report(moments):
    n, error, absolute, squared, y, yy = moments
    variation = yy - y * y / n if n else 0
    return {
        "rows": int(n),
        "bias_usd": error / n if n else None,
        "mae_usd": absolute / n if n else None,
        "rmse_usd": float(np.sqrt(squared / n)) if n else None,
        "r2": 1 - squared / variation if variation > 0 else None,
    }


def require_test_freeze(out, frozen_stage):
    if (out / "test").exists() and frozen_stage is None:
        raise ValueError("Test exists without complete freeze authority")


def combined_gate(selection, economic, day_gate):
    return bool(
        selection["selected_policy"] is not None
        and economic["passes"]
        and day_gate["viable"]
    )


def evaluate_period(
    days, store, episodes, models, scales, original, out, period, stages
):
    completed = stages.load(period)
    if completed:
        return read(out / period / "summary.json")
    lower, upper = (
        ("20250101", "20260101") if period == "validation" else ("20260101", "20260701")
    )
    target = out / period
    target.mkdir(exist_ok=True)
    for path in list(target.iterdir()):
        if path.suffix != ".npz" and not path.name.endswith(".complete.json"):
            preserve(path, out, "Rebuild uncommitted economic period from fixed scores")
    engine = base.import_sibling("level_engine")
    ids = [base.policy_id(m, t) for m in MODELS for t in THRESHOLDS]
    ledgers, attempts = {k: [] for k in ids}, {k: [] for k in ids}
    old_hashes = read(original / period / "prediction_hashes.json")
    sources, predictions = {}, {}
    errors = {(m, t): np.zeros(6) for m in MODELS for t in TICKERS}
    for number, day in enumerate(d for d in days if lower <= d.date < upper):
        actions, scores, hashes = predict_day(
            day,
            period,
            store,
            episodes,
            models,
            scales,
            original,
            old_hashes,
            target,
            out,
            stages.identity,
        )
        sources.update(hashes)
        path = target / (day.ticker + "_" + day.date + ".npz")
        predictions[path.name] = sha(path)
        # Future labels are accessed only after causal predictions are published.
        store.seal.check(day, "labels.parquet")
        labels = pd.read_parquet(day.oracle / "labels.parquet")
        targets = (
            labels.set_index("action_id")
            .loc[actions.action_id, "net_base"]
            .to_numpy(float)
        )
        for model in MODELS:
            errors[model, day.ticker] += error_moments(scores[model], targets)
            for threshold in THRESHOLDS:
                ident = base.policy_id(model, threshold)
                result = episode_policy.evaluate(
                    actions, labels, scores[model], threshold, engine
                )
                for collection, frame in (
                    (attempts, result.attempts),
                    (ledgers, result.ledger),
                ):
                    frame = frame.copy()
                    frame["ticker"], frame["date"], frame["policy"] = (
                        day.ticker,
                        day.date,
                        ident,
                    )
                    collection[ident].append(frame)
        if number % 50 == 0:
            print(
                json.dumps(
                    {
                        "stage": period,
                        "day": number,
                        "ticker": day.ticker,
                        "date": day.date,
                    }
                ),
                flush=True,
            )
    calendar = pd.read_csv(out / "expected_full_calendar.csv", dtype={"date": str}).date
    calendar = calendar[(calendar >= lower) & (calendar < upper)].tolist()
    months = pd.period_range(
        pd.Timestamp(lower), pd.Timestamp(upper) - pd.Timedelta(days=1), freq="M"
    ).strftime("%Y%m")
    available = {(d.ticker, d.date) for d in days if lower <= d.date < upper}
    summaries = {}
    for ident in ids:
        ledger = pd.concat(ledgers[ident], ignore_index=True).sort_values(
            ["date", "exit_i", "ticker", "state_i"], kind="stable"
        )
        attempted = pd.concat(attempts[ident], ignore_index=True)
        atomic(
            target / (ident + "_ledger.parquet"),
            lambda p: ledger.to_parquet(p, index=False),
        )
        atomic(
            target / (ident + "_attempts.parquet"),
            lambda p: attempted.to_parquet(p, index=False),
        )
        for field, suffix in (
            ("net_base", "daily_net"),
            ("net_adverse", "daily_adverse"),
        ):
            daily = (
                ledger.groupby(["date", "ticker"])[field].sum().unstack(fill_value=0)
                if len(ledger)
                else pd.DataFrame()
            )
            daily = daily.reindex(index=calendar, columns=TICKERS, fill_value=0).fillna(
                0
            )
            daily.index.name = "date"
            atomic(target / (ident + "_" + suffix + ".csv"), lambda p: daily.to_csv(p))
        day_table, day_summary = compliance(ledger, calendar, available)
        atomic(
            target / (ident + "_daily_compliance.csv"),
            lambda p: day_table.to_csv(p, index=False),
        )
        summaries[ident] = {
            "pooled": base.economic_metrics(ledger),
            "attempts": len(attempted),
            "no_fill_attempts": int((attempted.status == "NO_FILL").sum()),
            "daily_compliance": day_summary,
            "tickers": {
                t: {
                    **base.economic_metrics(ledger.loc[ledger.ticker == t]),
                    "attempts": int((attempted.ticker == t).sum()),
                    "no_fill_attempts": int(
                        (
                            (attempted.ticker == t) & (attempted.status == "NO_FILL")
                        ).sum()
                    ),
                    "executed_prediction_error": error_report(
                        error_moments(
                            ledger.loc[ledger.ticker == t, "score"],
                            ledger.loc[ledger.ticker == t, "net_base"],
                        )
                    ),
                }
                for t in TICKERS
            },
            "months": {
                t: {
                    month: base.economic_metrics(
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
    write_json(target / "prediction_hashes.json", predictions)
    write_json(
        target / "prediction_errors.json",
        {m: {t: error_report(errors[m, t]) for t in TICKERS} for m in MODELS},
    )
    sources.update(store.seal.hashes)
    sources.update(store.hashes)
    sources.update(episodes.hashes)
    stages.publish(period, [p for p in target.iterdir() if p.is_file()], sources)
    return summaries


def paired_results(out, frozen, scales):
    def active(selection):
        return (selection["selected_policy"] or selection["diagnostic_policy"])[
            "policy"
        ]

    best_control, best_variant = [active(frozen["arms"][m]) for m in MODELS]
    comparisons = [
        (
            f"same_threshold_{int(t)}",
            base.policy_id(MODELS[1], t),
            base.policy_id(MODELS[0], t),
        )
        for t in THRESHOLDS
    ]
    comparisons += [
        ("best_variant_minus_control", best_variant, best_control),
        ("best_control_minus_zero", best_control, None),
        ("best_variant_minus_zero", best_variant, None),
        ("joint_selected_or_diagnostic_minus_zero", active(frozen["selection"]), None),
    ]
    output = {}
    for name, left, right in comparisons:
        result = {"left": left, "right": right or "ZERO_REFERENCE_NOT_ELIGIBLE_POLICY"}
        for scenario, suffix in (("base", "daily_net"), ("adverse", "daily_adverse")):
            a = pd.read_csv(
                out / "test" / (left + "_" + suffix + ".csv"), dtype={"date": str}
            ).set_index("date")[list(TICKERS)]
            b = (
                pd.read_csv(
                    out / "test" / (right + "_" + suffix + ".csv"), dtype={"date": str}
                ).set_index("date")[list(TICKERS)]
                if right
                else a * 0
            )
            difference = a - b
            atomic(
                out / (name + "_" + scenario + "_daily.csv"),
                lambda p: difference.to_csv(p),
            )
            monthly = difference.groupby(difference.index.str[:6]).sum()
            atomic(
                out / (name + "_" + scenario + "_monthly.csv"),
                lambda p: monthly.to_csv(p),
            )
            values = difference.to_numpy(float)
            rng = np.random.default_rng(20261018)
            totals = np.empty((10000, 4))
            scale = np.array([scales[t] for t in TICKERS])
            for start in range(0, 10000, 250):
                indices = rng.integers(
                    0, len(values), size=(min(250, 10000 - start), len(values))
                )
                draws = values[indices].sum(axis=1)
                totals[start : start + len(draws), :3] = draws
                totals[start : start + len(draws), 3] = (draws / scale).sum(axis=1)
            result[scenario] = {
                "ticker_difference_usd": difference.sum().to_dict(),
                "normalized_difference": float((values.sum(axis=0) / scale).sum()),
                "ci95_tickers_then_normalized": np.quantile(
                    totals, [0.025, 0.975], axis=0
                ).tolist(),
            }
        output[name] = result
    write_json(out / "paired_comparisons.json", output)
    return output


def authority(args):
    root, original = args.root, args.root / "learners_v1"
    audit_path = root / "engine_v1_audit_v4/audit.json"
    audit = base.require_oracle_pass(audit_path, root / "engine_v1")
    base.verify_freeze(original)
    previous = read(root / "learners_v1_economic_audit/audit.json")
    binding = previous["binding"]
    if (
        previous["status"] != "PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT"
        or Path(binding["learner_root"]).resolve() != original.resolve()
    ):
        raise ValueError("Original learner audit authority differs")
    for key, path in (
        ("learner_summary_sha256", original / "summary.json"),
        ("freeze_sha256", original / "freeze.json"),
        (
            "validation_prediction_manifest_sha256",
            original / "validation/prediction_hashes.json",
        ),
        ("test_prediction_manifest_sha256", original / "test/prediction_hashes.json"),
        ("oracle_full_audit_sha256", audit_path),
    ):
        if sha(path) != binding[key]:
            raise ValueError("Original learner audit binding changed: " + key)
    source = Path(__file__).parent
    code_names = (
        "train_episode_model.py",
        "episode_policy.py",
        "EPISODE_LEARNER_PLAN.md",
        "train_models.py",
        "run_policy.py",
        "features.py",
        "build_cache.py",
        "level_engine.py",
        "run_engine_dataset.py",
        "PROTOCOL.md",
        "build_episode_features.py",
        "episode_features.py",
        "EPISODE_FEATURE_SPEC.md",
        "EPISODE_BUILD_SPEC.md",
    )
    files = [source / name for name in code_names]
    files += [
        original / name
        for name in (
            "train_x.npy",
            "training_sample.parquet",
            "normalizers.json",
            "gbt_net.txt",
            "gbt_config.json",
            "freeze.json",
            "summary.json",
            "expected_full_calendar.csv",
            "validation/prediction_hashes.json",
            "test/prediction_hashes.json",
        )
    ]
    files += [root / "learners_v1_economic_audit/audit.json"]
    files += [
        root / "episode_features_v1" / name
        for name in ("contract.json", "index.json", "summary.json")
    ]
    hashes = {str(p.resolve()): sha(p) for p in files}
    hashes.update(audit["verified_files"])
    identity = {
        "root": str(root.resolve()),
        "output": str(args.output.resolve()),
        "files": hashes,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "lightgbm": lgb.__version__,
        "new_model_budget": 1,
        "policy_semantics": "USER_FREE_TIMING_HARD_DAILY_FILL_CONSTRAINT",
        "data_state": "SEEN_DEVELOPMENT_POST_RESULT_VARIANT",
    }
    return identity, code_names


def run(args):
    started = time.monotonic()
    original = args.root / "learners_v1"
    identity, code_names = authority(args)
    out = args.output
    if args.resume:
        if read(out / "identity.json") != identity:
            raise ValueError("Resume identity differs")
        if (out / "summary.json").exists() and (
            out / "completion.complete.json"
        ).exists():
            raise ValueError("Completed episode experiment must not be rerun")
        failures = sorted(out.glob("failure_*.json"))
        if any(not read(p)["technical_interruption"] for p in failures):
            raise ValueError("Unclassified/scientific failure cannot be retried")
    else:
        if (out / "identity.json").exists():
            raise ValueError("Existing experiment requires explicit resume")
        write_json(out / "identity.json", identity)
        for name in code_names:
            atomic(
                out / "frozen_code" / name,
                lambda p, name=name: p.write_bytes(
                    Path(__file__).with_name(name).read_bytes()
                ),
            )
        for name in (
            "training_sample.parquet",
            "normalizers.json",
            "gbt_config.json",
            "gbt_net.txt",
            "expected_full_calendar.csv",
        ):
            atomic(
                out / name,
                lambda p, name=name: p.write_bytes((original / name).read_bytes()),
            )
    stages = Stages(out, sha(out / "identity.json"))
    # Check authority before any potentially missing training stage can run.
    frozen_stage = stages.load("freeze")
    require_test_freeze(out, frozen_stage)
    verify_hashes(identity["files"])
    for name in (
        "training_sample.parquet",
        "normalizers.json",
        "gbt_config.json",
        "gbt_net.txt",
        "expected_full_calendar.csv",
    ):
        if sha(out / name) != sha(original / name):
            raise ValueError("Frozen copied control artifact changed: " + name)
    config = read(out / "gbt_config.json")
    expected = dict(
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
    if config != expected:
        raise ValueError("Fixed GBT configuration differs")
    sample = pd.read_parquet(out / "training_sample.parquet")
    if sha(out / "training_sample.parquet") != sha(
        original / "training_sample.parquet"
    ):
        raise ValueError("Copied training sample differs")
    scales = read(out / "normalizers.json")["risk_scales_usd"]
    days = base.discover_days(args.root / "engine_v1", args.root / "features_v1")
    base.verify_full_coverage(days, out)
    seal = base.SourceSeal(args.root / "engine_v1")
    episodes = Episodes(args.root / "episode_features_v1", seal)
    if set(episodes.index) != {(d.ticker, d.date) for d in days}:
        raise ValueError("Episode/source day universe differs")
    store = base.FeatureStore(days, seal=seal)
    matrix = build_matrix(original, sample, days, episodes, out, stages)
    print(
        json.dumps({"stage": "fit_start", "rows": len(sample), "columns": 2024}),
        flush=True,
    )
    variant = fit_variant(matrix, sample, scales, config, out, stages)
    del matrix
    models = {
        "gbt_net": lgb.Booster(model_file=str(out / "gbt_net.txt")),
        "gbt_net_episode": variant,
    }
    validation = evaluate_period(
        days, store, episodes, models, scales, original, out, "validation", stages
    )
    if frozen_stage:
        frozen = read(out / "freeze.json")
    else:
        preserve(out / "freeze.json", out, "Uncommitted pre-test freeze")
        selection = choices_and_selection(validation, scales)
        arms = {m: choices_and_selection(validation, scales, (m,)) for m in MODELS}
        frozen = {
            "selection": selection,
            "arms": arms,
            "identity_sha256": stages.identity,
            "new_test_labels_opened": False,
            "model_sha256": sha(out / "gbt_net_episode.txt"),
            "validation_stage_sha256": sha(out / "validation.complete.json"),
        }
        write_json(out / "freeze.json", frozen)
        stages.publish(
            "freeze",
            [out / "freeze.json"],
            {
                str((out / n).resolve()): sha(out / n)
                for n in (
                    "identity.json",
                    "model.complete.json",
                    "validation.complete.json",
                )
            },
        )
    print(
        json.dumps(
            {
                "stage": "POLICY_FROZEN_BEFORE_EPISODE_TEST",
                "selection": frozen["selection"],
            }
        ),
        flush=True,
    )
    test = evaluate_period(
        days, store, episodes, models, scales, original, out, "test", stages
    )
    stages.load("freeze")
    paired = paired_results(out, frozen, scales)
    selection = frozen["selection"]
    candidate = selection["selected_policy"] or selection["diagnostic_policy"]
    economic = base.economic_gate(candidate, test)
    day_gate = test[candidate["policy"]]["daily_compliance"]
    passes = combined_gate(selection, economic, day_gate)
    sources = dict(identity["files"])
    for stage in ("matrix", "model", "validation", "freeze", "test"):
        record = stages.load(stage)
        sources.update(record["sources"])
    verify_hashes(sources)
    write_json(out / "final_source_hashes.json", sources)
    result = {
        "status": "COMPLETED_EPISODE_LEARNER_DEVELOPMENT",
        **selection,
        "candidate_test_is_diagnostic": selection["selected_policy"] is None,
        "candidate_test": test[candidate["policy"]],
        "economic_gate": economic,
        "daily_test_gate": day_gate,
        "combined_gate_passes": bool(passes),
        "variant_improves_normalized_net_both_costs": all(
            paired["best_variant_minus_control"][s]["normalized_difference"] > 0
            for s in ("base", "adverse")
        ),
        "seconds": time.monotonic() - started,
        "new_fits": 1,
        "control_refits": 0,
        "untouched_outer": False,
        "promotion_approved": False,
    }
    write_json(out / "summary.json", result)
    final_paths = [
        out / "summary.json",
        out / "final_source_hashes.json",
        out / "paired_comparisons.json",
    ]
    final_paths += list(out.glob("*_daily.csv")) + list(out.glob("*_monthly.csv"))
    stages.publish("completion", final_paths, sources)
    print(
        json.dumps(
            {
                "stage": "COMPLETE",
                "selection_status": selection["selection_status"],
                "combined_gate_passes": passes,
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    args.root, args.output = args.root.resolve(), args.output.resolve()
    if not args.resume:
        args.output.mkdir(parents=True, exist_ok=False)
    with output_lock(args.output):
        try:
            run(args)
        except BaseException as error:
            write_json(
                args.output / ("failure_" + str(time.time_ns()) + ".json"),
                {
                    "exception": type(error).__name__,
                    "message": str(error),
                    "technical_interruption": isinstance(
                        error, (MemoryError, OSError, KeyboardInterrupt)
                    ),
                },
            )
            raise


if __name__ == "__main__":
    main()
