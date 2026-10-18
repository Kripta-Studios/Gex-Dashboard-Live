"""Independent economic audit of the episode learner given sealed predictions."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

import numpy as np
import pandas as pd

TICKERS = ("SPXW", "SPY", "QQQ")
MODELS = ("gbt_net", "gbt_net_episode")
THRESHOLDS = (0.0, 5.0, 10.0)
FIRST_STATE = 60
TOLERANCE = 1e-8


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def cached_digest(cache, path):
    resolved = str(Path(path).resolve())
    if resolved not in cache:
        cache[resolved] = digest(path)
    return cache[resolved]


def require(condition, message):
    if not bool(condition):
        raise AssertionError(message)


def policy_id(model, threshold):
    return f"{model}__{int(threshold)}"


def policies():
    return [policy_id(model, threshold) for model in MODELS for threshold in THRESHOLDS]


def rank_by_state(actions, scores):
    scores = np.asarray(scores, dtype=float)
    require(scores.shape == (len(actions),), "Score/action shape")
    ids = actions.action_id.to_numpy(dtype=np.int64)
    states = actions.state_i.to_numpy(dtype=np.int64)
    valid = np.flatnonzero(np.isfinite(scores))
    order = valid[np.lexsort((ids[valid], -scores[valid], states[valid]))]
    if len(order) == 0:
        return order
    return order[np.r_[True, states[order][1:] != states[order][:-1]]]


def schedule(actions, labels, scores, threshold, ranked=None):
    require(not actions.action_id.duplicated().any(), "Duplicate action ID")
    require(not labels.action_id.duplicated().any(), "Duplicate label action ID")
    indexer = pd.Index(labels.action_id).get_indexer(actions.action_id)
    require(len(actions) == len(labels) and np.all(indexer >= 0), "Action/label universe")
    ordered_labels = labels.iloc[indexer].reset_index(drop=True)
    actions = actions.reset_index(drop=True)
    scores = np.asarray(scores, dtype=float)
    require(np.isfinite(scores).all(), "Nonfinite saved score")
    ranked = rank_by_state(actions, scores) if ranked is None else np.asarray(ranked, dtype=int)
    states = actions.state_i.to_numpy(dtype=int)
    filled = ordered_labels.status.to_numpy() == "FILLED"
    require(np.isin(ordered_labels.status, ("FILLED", "NO_FILL")).all(), "Label status")
    exits = ordered_labels.exit_i.to_numpy(dtype=int)
    selected = []
    next_state = FIRST_STATE
    for row in ranked:
        state = int(states[row])
        if state < next_state or scores[row] <= threshold:
            continue
        selected.append(int(row))
        next_state = int(exits[row]) + 1 if filled[row] else state + 1
    attempts = actions.iloc[selected].merge(
        ordered_labels.iloc[selected], on="action_id", how="left", validate="one_to_one"
    )
    attempts["score"] = scores[selected]
    return attempts, attempts.loc[attempts.status == "FILLED"].copy()


def economic_metrics(frame):
    result = {"trades": len(frame), "exit_diagnostics_available": "reason" in frame}
    result["exit_reasons"] = (
        {
            reason: {
                "trades": int((frame.reason == reason).sum()),
                "base_net_usd": float(frame.loc[frame.reason == reason, "net_base"].sum()),
                "adverse_net_usd": float(frame.loc[frame.reason == reason, "net_adverse"].sum()),
            }
            for reason in ("TARGET", "STOP", "EOD")
        }
        if "reason" in frame
        else {}
    )
    holding = frame.hold_minutes.to_numpy(float) if "hold_minutes" in frame else np.array([])
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
        result[prefix + "_win_rate"] = float((values > 0).mean()) if len(values) else None
        cumulative = np.r_[0.0, np.cumsum(values)]
        result[prefix + "_max_drawdown_usd"] = float(
            np.max(np.maximum.accumulate(cumulative) - cumulative)
        )
    return result


def summarize(ledger, months):
    return {
        "pooled": economic_metrics(ledger),
        "tickers": {
            ticker: economic_metrics(ledger.loc[ledger.ticker == ticker]) for ticker in TICKERS
        },
        "months": {
            ticker: {
                month: economic_metrics(
                    ledger.loc[(ledger.ticker == ticker) & ledger.date.str.startswith(month)]
                )
                for month in months
            }
            for ticker in TICKERS
        },
    }


def error_moments(predicted, observed):
    predicted = np.asarray(predicted, dtype=float)
    observed = np.asarray(observed, dtype=float)
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
        dtype=float,
    )


def error_report(moments):
    count, error, absolute, squared, total, squared_total = moments
    variation = squared_total - total * total / count if count else 0
    return {
        "rows": int(count),
        "bias_usd": error / count if count else None,
        "mae_usd": absolute / count if count else None,
        "rmse_usd": float(np.sqrt(squared / count)) if count else None,
        "r2": 1 - squared / variation if variation > 0 else None,
    }


def compare_values(actual, expected, context):
    if isinstance(actual, dict) and isinstance(expected, dict):
        require(set(actual) == set(expected), context + " keys")
        for key in actual:
            compare_values(actual[key], expected[key], context + "." + str(key))
    elif actual is None or expected is None:
        require(actual is expected, context)
    elif isinstance(actual, (int, float, bool)) and isinstance(expected, (int, float, bool)):
        require(np.isclose(float(actual), float(expected), rtol=0, atol=TOLERANCE), context)
    else:
        require(actual == expected, context)


def compare_frames(actual, expected, keys, context):
    require(set(actual.columns) == set(expected.columns), context + " columns")
    actual = actual.sort_values(keys, kind="stable").reset_index(drop=True)[expected.columns]
    expected = expected.sort_values(keys, kind="stable").reset_index(drop=True)
    require(len(actual) == len(expected), context + " length")
    for column in expected:
        if pd.api.types.is_numeric_dtype(expected[column]):
            require(np.allclose(actual[column].to_numpy(float), expected[column].to_numpy(float),
                                rtol=0, atol=TOLERANCE, equal_nan=True),
                    context + " " + column)
        else:
            require(actual[column].fillna("<NA>").equals(expected[column].fillna("<NA>")),
                    context + " " + column)


def daily_compliance(ledger, calendar, available):
    counts = (
        ledger.groupby(["date", "ticker"]).size()
        if len(ledger)
        else pd.Series(dtype=np.int64)
    )
    rows = []
    for date in calendar:
        for ticker in TICKERS:
            evaluable = (ticker, date) in available
            fills = int(counts.get((date, ticker), 0))
            rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "source_status": "EVALUABLE" if evaluable else "NO_EVALUABLE",
                    "fills": fills if evaluable else None,
                    "meets_minimum": fills >= 1 if evaluable else None,
                }
            )
    frame = pd.DataFrame(rows)
    evaluable = frame.source_status == "EVALUABLE"
    summary = {
        "expected_ticker_days": len(frame),
        "available_ticker_days": int(evaluable.sum()),
        "no_evaluable_ticker_days": int((~evaluable).sum()),
        "days_without_fill": int((frame.loc[evaluable, "fills"] < 1).sum()),
        "minimum_daily_pass": bool(frame.loc[evaluable, "meets_minimum"].all()),
        "coverage_pass": bool(evaluable.all()),
    }
    summary["viable"] = summary["minimum_daily_pass"] and summary["coverage_pass"]
    return frame, summary


def select_policy(validation, scales, models=MODELS):
    choices = []
    for model in models:
        for threshold in THRESHOLDS:
            ident = policy_id(model, threshold)
            score = sum(validation[ident]["tickers"][ticker]["base_net_usd"] / scales[ticker]
                        for ticker in TICKERS)
            choices.append(
                {
                    "policy": ident,
                    "model": model,
                    "threshold": threshold,
                    "selection_score": float(score),
                    "daily_viable": validation[ident]["daily_compliance"]["viable"],
                }
            )
    viable = [choice for choice in choices if choice["daily_viable"]]
    selected = max(viable, key=lambda choice: choice["selection_score"]) if viable else None
    diagnostic = max(choices, key=lambda choice: choice["selection_score"])
    return {
        "selection_status": (
            "DAILY_COMPLIANT_POLICY_SELECTED"
            if selected
            else "FAIL_NO_DAILY_COMPLIANT_POLICY"
        ),
        "selected_policy": selected,
        "diagnostic_policy": diagnostic,
        "approved": False,
        "choices": choices,
    }


def economic_gate(candidate, test):
    summary = test[candidate["policy"]]
    flags = {}
    for ticker in TICKERS:
        metrics = summary["tickers"][ticker]
        positive_months = sum(
            month["base_net_usd"] > 0 for month in summary["months"][ticker].values()
        )
        passed = (
            metrics["base_net_usd"] > 0 and metrics["adverse_net_usd"] > 0
            and (metrics.get("base_pf_infinite", False)
                 or (metrics["base_pf"] is not None and metrics["base_pf"] >= 1.2))
            and metrics["trades"] >= 60 and positive_months >= 3
        )
        flags[ticker] = {"passes": bool(passed), "positive_months": positive_months,
                         **metrics}
    return {"passes": all(value["passes"] for value in flags.values()), "tickers": flags}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def audit_period(learner_root, original_root, index, calendar, name, lower, upper):
    root = learner_root / name
    manifest = load_json(root / "prediction_hashes.json")
    rows = index.loc[(index.status == "COMPLETE") & (index.date >= lower)
                     & (index.date < upper)].sort_values(["date", "ticker"])
    available = {(row.ticker, row.date) for row in rows.itertuples(index=False)}
    expected_files = {f"{row.ticker}_{row.date}.npz" for row in rows.itertuples(index=False)}
    require(set(manifest) == expected_files, name + " prediction manifest membership")
    require({path.name for path in root.glob("*.npz")} == expected_files,
            name + " prediction file membership")
    original_manifest = load_json(original_root / name / "prediction_hashes.json")
    require(set(original_manifest) == expected_files, name + " original control membership")
    collected_attempts = {ident: [] for ident in policies()}
    collected_ledgers = {ident: [] for ident in policies()}
    errors = {(model, ticker): np.zeros(6) for model in MODELS for ticker in TICKERS}
    prediction_rows = 0
    started = time.monotonic()
    for number, row in enumerate(rows.itertuples(index=False), start=1):
        prediction_path = root / f"{row.ticker}_{row.date}.npz"
        require(digest(prediction_path) == manifest[prediction_path.name], "Prediction hash")
        prediction_marker = load_json(prediction_path.with_suffix(".complete.json"))
        require(
            prediction_marker["sha256"] == digest(prediction_path),
            "Prediction completion marker hash",
        )
        day_root = Path(row.day_root)
        require(digest(day_root / "actions.parquet") == row.actions_sha256, "Action seal")
        require(digest(day_root / "labels.parquet") == row.labels_sha256, "Label seal")
        actions = pd.read_parquet(day_root / "actions.parquet")
        labels = pd.read_parquet(day_root / "labels.parquet")
        with np.load(prediction_path, allow_pickle=False) as stored:
            require(set(stored.files) == {"action_ids", *MODELS}, "Prediction NPZ keys")
            action_ids = stored["action_ids"]
            require(np.array_equal(action_ids, actions.action_id.to_numpy()),
                    "Prediction/action alignment")
            scores = {model: stored[model].copy() for model in MODELS}
        original_path = original_root / name / prediction_path.name
        require(
            digest(original_path) == original_manifest[prediction_path.name],
            "Original control prediction hash",
        )
        with np.load(original_path, allow_pickle=False) as original:
            require(
                np.array_equal(original["action_ids"], action_ids)
                and np.array_equal(original["gbt_net"], scores["gbt_net"]),
                "Control prediction must be exact original",
            )
        label_indexer = pd.Index(labels.action_id).get_indexer(actions.action_id)
        require(np.all(label_indexer >= 0), "Prediction-error label universe")
        targets = labels.iloc[label_indexer].net_base.to_numpy(float)
        prediction_rows += len(actions)
        for model in MODELS:
            errors[model, row.ticker] += error_moments(scores[model], targets)
            ranked = rank_by_state(actions, scores[model])
            for threshold in THRESHOLDS:
                ident = policy_id(model, threshold)
                attempts, ledger = schedule(actions, labels, scores[model], threshold, ranked)
                for frame in (attempts, ledger):
                    frame["ticker"], frame["date"], frame["policy"] = (
                        row.ticker, row.date, ident
                    )
                collected_attempts[ident].append(attempts)
                collected_ledgers[ident].append(ledger)
        if number % 50 == 0 or number == len(rows):
            elapsed = time.monotonic() - started
            print(json.dumps({"stage": name, "days": number, "total_days": len(rows),
                              "seconds": elapsed, "days_per_second": number / elapsed}),
                  flush=True)
    months = pd.period_range(pd.Timestamp(lower), pd.Timestamp(upper) - pd.Timedelta(days=1),
                             freq="M").strftime("%Y%m")
    summaries = {}
    attempts_count = ledger_count = 0
    for ident in policies():
        attempts = pd.concat(collected_attempts[ident], ignore_index=True)
        ledger = pd.concat(collected_ledgers[ident], ignore_index=True)
        ledger = ledger.sort_values(["date", "exit_i", "ticker", "state_i"], kind="stable")
        producer_attempts = pd.read_parquet(root / f"{ident}_attempts.parquet")
        producer_ledger = pd.read_parquet(root / f"{ident}_ledger.parquet")
        compare_frames(attempts, producer_attempts,
                       ["date", "ticker", "state_i", "action_id"], name + " attempts " + ident)
        compare_frames(ledger, producer_ledger,
                       ["date", "ticker", "exit_i", "state_i", "action_id"],
                       name + " ledger " + ident)
        for ticker, frame in ledger.groupby(["ticker", "date"], sort=False):
            ordered = frame.sort_values(["state_i", "action_id"])
            require(np.all(ordered.state_i.to_numpy()[1:] > ordered.exit_i.to_numpy()[:-1]),
                    f"{name} overlap {ident} {ticker}")
        period_calendar = calendar.loc[(calendar >= lower) & (calendar < upper)]
        for field, suffix in (("net_base", "daily_net"), ("net_adverse", "daily_adverse")):
            expected_daily = (
                ledger.groupby(["date", "ticker"])[field].sum().unstack(fill_value=0)
                if len(ledger)
                else pd.DataFrame()
            )
            expected_daily = expected_daily.reindex(
                index=period_calendar, columns=TICKERS, fill_value=0
            ).fillna(0)
            actual_daily = pd.read_csv(root / f"{ident}_{suffix}.csv", index_col=0)
            actual_daily.index = actual_daily.index.astype(str)
            require(
                actual_daily.index.tolist() == expected_daily.index.tolist(),
                name + " daily calendar " + ident + " " + suffix,
            )
            require(
                actual_daily.columns.tolist() == list(TICKERS),
                name + " daily columns " + ident + " " + suffix,
            )
            require(
                np.allclose(
                    actual_daily.to_numpy(float),
                    expected_daily.to_numpy(float),
                    rtol=0,
                    atol=TOLERANCE,
                ),
                name + " daily values " + ident + " " + suffix,
            )
        compliance_frame, compliance_summary = daily_compliance(
            ledger, period_calendar.tolist(), available
        )
        actual_compliance = pd.read_csv(
            root / f"{ident}_daily_compliance.csv",
            dtype={"date": str, "ticker": str, "source_status": str},
        )
        compare_frames(
            compliance_frame,
            actual_compliance,
            ["date", "ticker"],
            name + " daily compliance " + ident,
        )
        basic = summarize(ledger, months)
        summaries[ident] = {
            "pooled": basic["pooled"],
            "attempts": len(attempts),
            "no_fill_attempts": int((attempts.status == "NO_FILL").sum()),
            "daily_compliance": compliance_summary,
            "tickers": {
                ticker: {
                    **basic["tickers"][ticker],
                    "attempts": int((attempts.ticker == ticker).sum()),
                    "no_fill_attempts": int(
                        ((attempts.ticker == ticker) & (attempts.status == "NO_FILL")).sum()
                    ),
                    "executed_prediction_error": error_report(
                        error_moments(
                            ledger.loc[ledger.ticker == ticker, "score"],
                            ledger.loc[ledger.ticker == ticker, "net_base"],
                        )
                    ),
                }
                for ticker in TICKERS
            },
            "months": basic["months"],
        }
        attempts_count += len(attempts)
        ledger_count += len(ledger)
    producer_summary = load_json(root / "summary.json")
    compare_values(summaries, producer_summary, name + " summary")
    prediction_errors = {
        model: {ticker: error_report(errors[model, ticker]) for ticker in TICKERS}
        for model in MODELS
    }
    compare_values(
        prediction_errors,
        load_json(root / "prediction_errors.json"),
        name + " prediction errors",
    )
    return summaries, {"prediction_rows": prediction_rows, "attempts": attempts_count,
                       "ledger_trades": ledger_count, "prediction_files": len(rows)}


def verify_freeze(learner_root, validation, scales):
    freeze_path = learner_root / "freeze.json"
    freeze = load_json(freeze_path)
    identity_sha = digest(learner_root / "identity.json")
    require(freeze["identity_sha256"] == identity_sha, "Frozen identity")
    require(
        freeze["model_sha256"] == digest(learner_root / "gbt_net_episode.txt"),
        "Frozen model",
    )
    require(
        freeze["validation_stage_sha256"]
        == digest(learner_root / "validation.complete.json"),
        "Frozen validation stage",
    )
    require(freeze["new_test_labels_opened"] is False, "Freeze test disclosure")
    selection = select_policy(validation, scales)
    compare_values(selection, freeze["selection"], "Frozen selection")
    arms = {model: select_policy(validation, scales, (model,)) for model in MODELS}
    compare_values(arms, freeze["arms"], "Frozen arm selections")
    marker = load_json(learner_root / "freeze.complete.json")
    require(marker["identity_sha256"] == identity_sha, "Freeze marker identity")
    require(
        marker["artifacts"] == {str(freeze_path.resolve()): digest(freeze_path)},
        "Freeze marker artifact",
    )
    for path, expected in marker["sources"].items():
        require(digest(path) == expected, "Freeze marker source " + path)
    test_files = list((learner_root / "test").glob("*.npz"))
    require(
        test_files
        and (learner_root / "freeze.complete.json").stat().st_mtime
        <= min(path.stat().st_mtime for path in test_files),
        "Freeze must predate test predictions",
    )
    return freeze, selection, arms


def verify_stage(learner_root, name, identity_sha, cache):
    record = load_json(learner_root / f"{name}.complete.json")
    require(record["identity_sha256"] == identity_sha, name + " stage identity")
    for group in ("artifacts", "sources"):
        for path, expected in record[group].items():
            actual = cached_digest(cache, path)
            require(actual == expected, name + " stage " + group + " " + path)
    return record


def audit_matrix_identity(learner_root, original_root, episode_root):
    require(
        digest(learner_root / "training_sample.parquet")
        == digest(original_root / "training_sample.parquet"),
        "Training sample identity",
    )
    sample = pd.read_parquet(learner_root / "training_sample.parquet")
    require(
        len(sample) == 270377
        and np.array_equal(sample.sample_i.to_numpy(), np.arange(len(sample))),
        "Training sample order",
    )
    matrix = np.load(learner_root / "train_x.npy", mmap_mode="r")
    original = np.load(original_root / "train_x.npy", mmap_mode="r")
    require(
        matrix.shape == (270377, 2024)
        and original.shape == (270377, 1954)
        and matrix.dtype == original.dtype == np.float32,
        "Training matrix shape/dtype",
    )
    for start in range(0, len(sample), 4096):
        left = np.ascontiguousarray(matrix[start : start + 4096, :1954]).view(np.uint32)
        right = np.ascontiguousarray(original[start : start + 4096]).view(np.uint32)
        require(np.array_equal(left, right), "Original training prefix bit identity")
    for (ticker, date), rows in sample.groupby(["ticker", "date"], sort=False):
        with np.load(
            episode_root / str(ticker) / str(date) / "episodes.npz", allow_pickle=False
        ) as stored:
            require(set(stored.files) == {"state_i", "values", "valid"}, "Episode schema")
            keys = stored["state_i"]
            values = stored["values"]
            valid = stored["valid"]
        require(len(np.unique(keys)) == len(keys), "Episode state uniqueness")
        positions = pd.Index(keys).get_indexer(rows.state_i.to_numpy())
        require(np.all(positions >= 0), "Episode state join")
        expected = np.concatenate(
            [values[positions].astype(np.float32), valid[positions].astype(np.float32)],
            axis=1,
        )
        require(
            np.array_equal(matrix[rows.sample_i.to_numpy(), 1954:], expected),
            "Episode training block identity",
        )
    return {
        "rows": len(sample),
        "columns": int(matrix.shape[1]),
        "prefix_columns_bit_identical": 1954,
        "episode_columns_exact": 70,
        "sample_sha256": digest(learner_root / "training_sample.parquet"),
        "matrix_sha256": digest(learner_root / "train_x.npy"),
    }


def audit_paired(learner_root, freeze, scales):
    def active(selection):
        return (selection["selected_policy"] or selection["diagnostic_policy"])["policy"]

    best_control = active(freeze["arms"]["gbt_net"])
    best_variant = active(freeze["arms"]["gbt_net_episode"])
    comparisons = [
        (
            f"same_threshold_{int(threshold)}",
            policy_id("gbt_net_episode", threshold),
            policy_id("gbt_net", threshold),
        )
        for threshold in THRESHOLDS
    ]
    comparisons += [
        ("best_variant_minus_control", best_variant, best_control),
        ("best_control_minus_zero", best_control, None),
        ("best_variant_minus_zero", best_variant, None),
        (
            "joint_selected_or_diagnostic_minus_zero",
            active(freeze["selection"]),
            None,
        ),
    ]
    output = {}
    verified = {}
    for name, left, right in comparisons:
        result = {"left": left, "right": right or "ZERO_REFERENCE_NOT_ELIGIBLE_POLICY"}
        for scenario, suffix in (("base", "daily_net"), ("adverse", "daily_adverse")):
            left_daily = pd.read_csv(
                learner_root / "test" / f"{left}_{suffix}.csv", dtype={"date": str}
            ).set_index("date")[list(TICKERS)]
            right_daily = (
                pd.read_csv(
                    learner_root / "test" / f"{right}_{suffix}.csv",
                    dtype={"date": str},
                ).set_index("date")[list(TICKERS)]
                if right
                else left_daily * 0
            )
            difference = left_daily - right_daily
            daily_path = learner_root / f"{name}_{scenario}_daily.csv"
            monthly_path = learner_root / f"{name}_{scenario}_monthly.csv"
            actual_daily = pd.read_csv(daily_path, dtype={"date": str}).set_index("date")
            actual_monthly = pd.read_csv(monthly_path, dtype={"date": str}).set_index("date")
            expected_monthly = difference.groupby(difference.index.str[:6]).sum()
            require(
                actual_daily.index.equals(difference.index)
                and actual_daily.columns.tolist() == list(TICKERS)
                and np.allclose(actual_daily, difference, rtol=0, atol=TOLERANCE),
                name + " paired daily " + scenario,
            )
            require(
                actual_monthly.index.equals(expected_monthly.index)
                and actual_monthly.columns.tolist() == list(TICKERS)
                and np.allclose(actual_monthly, expected_monthly, rtol=0, atol=TOLERANCE),
                name + " paired monthly " + scenario,
            )
            values = difference.to_numpy(float)
            rng = np.random.default_rng(20261018)
            totals = np.empty((10000, 4))
            scale = np.array([scales[ticker] for ticker in TICKERS])
            for start in range(0, 10000, 250):
                size = min(250, 10000 - start)
                indices = rng.integers(0, len(values), size=(size, len(values)))
                draws = values[indices].sum(axis=1)
                totals[start : start + size, :3] = draws
                totals[start : start + size, 3] = (draws / scale).sum(axis=1)
            result[scenario] = {
                "ticker_difference_usd": difference.sum().to_dict(),
                "normalized_difference": float((values.sum(axis=0) / scale).sum()),
                "ci95_tickers_then_normalized": np.quantile(
                    totals, [0.025, 0.975], axis=0
                ).tolist(),
            }
            verified[str(daily_path.relative_to(learner_root))] = digest(daily_path)
            verified[str(monthly_path.relative_to(learner_root))] = digest(monthly_path)
        output[name] = result
    compare_values(output, load_json(learner_root / "paired_comparisons.json"), "Paired results")
    return output, verified


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--learner-root", type=Path, required=True)
    parser.add_argument("--original-root", type=Path, required=True)
    parser.add_argument("--episode-root", type=Path, required=True)
    parser.add_argument("--oracle-root", type=Path, required=True)
    parser.add_argument("--oracle-audit", type=Path, required=True)
    parser.add_argument("--original-audit", type=Path, required=True)
    parser.add_argument("--repair-script", type=Path, required=True)
    parser.add_argument("--repair-runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    identity_path = args.learner_root / "identity.json"
    identity = load_json(identity_path)
    identity_sha = digest(identity_path)
    verified_source_hashes = {}
    for path, expected in identity["files"].items():
        actual = cached_digest(verified_source_hashes, path)
        require(actual == expected, "Experiment identity source " + path)
    for stage in ("matrix", "model", "validation", "freeze", "test", "completion"):
        verify_stage(args.learner_root, stage, identity_sha, verified_source_hashes)
    index_path = args.oracle_root / "index.parquet"
    index = pd.read_parquet(index_path)
    index["date"] = index.date.astype(str)
    oracle_audit = load_json(args.oracle_audit)
    require(oracle_audit["status"] == "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT",
            "Full oracle audit status")
    require(digest(index_path) == oracle_audit["binding"]["index_sha256"], "Oracle index binding")
    original_audit = load_json(args.original_audit)
    require(
        original_audit["status"] == "PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT"
        and Path(original_audit["binding"]["learner_root"]).resolve()
        == args.original_root.resolve(),
        "Original learner audit authority",
    )
    for name in (
        "training_sample.parquet",
        "normalizers.json",
        "gbt_config.json",
        "gbt_net.txt",
        "expected_full_calendar.csv",
    ):
        require(
            digest(args.learner_root / name) == digest(args.original_root / name),
            "Copied control artifact identity " + name,
        )
    summary_path = args.learner_root / "summary.json"
    summary = load_json(summary_path)
    require(
        summary["status"] == "COMPLETED_EPISODE_LEARNER_DEVELOPMENT",
        "Episode learner completion",
    )
    repair_root = args.learner_root / "technical_repairs" / "source_path_v1"
    repair = load_json(repair_root / "repair.json")
    repair_completion = load_json(repair_root / "completion.json")
    require(
        repair["status"] == "TECHNICAL_SOURCE_MANIFEST_PATH_REPAIR"
        and repair["repair_script_sha256"] == digest(args.repair_script)
        and repair["identity_sha256"] == identity_sha
        and repair["model_fits_permitted"] == 0,
        "Technical repair authority",
    )
    require(
        repair_completion["status"] == "TECHNICAL_CONTINUATION_COMPLETE_ZERO_REFITS"
        and repair_completion["repair_sha256"] == digest(repair_root / "repair.json")
        and repair_completion["model_sha256_after"]
        == digest(args.learner_root / "gbt_net_episode.txt")
        and repair_completion["summary_sha256"] == digest(summary_path)
        and repair_completion["scientific_completion_sha256"]
        == digest(args.learner_root / "completion.complete.json")
        and repair_completion["refits"] == 0,
        "Technical repair completion",
    )
    runtime = load_json(args.repair_runtime)
    require(
        runtime["status"] == "COMPLETE"
        and runtime["exit_code"] == 0
        and runtime["sources"]["resume_episode_pathfix.py"]
        == digest(args.repair_script)
        and runtime["technical_repair_files"]
        == {
            str((repair_root / "repair.json").resolve()): digest(
                repair_root / "repair.json"
            ),
            str((repair_root / "completion.json").resolve()): digest(
                repair_root / "completion.json"
            ),
        },
        "Repair runtime completion",
    )
    calendar = pd.read_csv(args.learner_root / "expected_full_calendar.csv", dtype={"date": str}).date
    require(len(calendar) == 867 and not calendar.duplicated().any(), "Expected calendar")
    require(set(calendar) == set(index.date), "Calendar/oracle-index date membership")
    matrix_identity = audit_matrix_identity(
        args.learner_root, args.original_root, args.episode_root
    )
    validation, validation_counts = audit_period(
        args.learner_root,
        args.original_root,
        index,
        calendar,
        "validation",
        "20250101",
        "20260101",
    )
    scales = load_json(args.learner_root / "normalizers.json")["risk_scales_usd"]
    require(set(scales) == set(TICKERS) and all(float(value) > 0 for value in scales.values()),
            "Risk scales")
    freeze, selection, arms = verify_freeze(args.learner_root, validation, scales)
    test, test_counts = audit_period(
        args.learner_root,
        args.original_root,
        index,
        calendar,
        "test",
        "20260101",
        "20260701",
    )
    for key, expected in selection.items():
        compare_values(expected, summary[key], "Final selection " + key)
    candidate = selection["selected_policy"] or selection["diagnostic_policy"]
    compare_values(
        test[candidate["policy"]], summary["candidate_test"], "Candidate test"
    )
    require(
        summary["candidate_test_is_diagnostic"]
        is (selection["selected_policy"] is None),
        "Diagnostic test disclosure",
    )
    gate = economic_gate(candidate, test)
    compare_values(gate, summary["economic_gate"], "Economic gate")
    day_gate = test[candidate["policy"]]["daily_compliance"]
    compare_values(day_gate, summary["daily_test_gate"], "Daily test gate")
    combined = bool(
        selection["selected_policy"] is not None
        and gate["passes"]
        and day_gate["viable"]
    )
    require(summary["combined_gate_passes"] is combined, "Combined gate")
    paired, paired_files = audit_paired(args.learner_root, freeze, scales)
    improvement = all(
        paired["best_variant_minus_control"][scenario]["normalized_difference"] > 0
        for scenario in ("base", "adverse")
    )
    require(
        summary["variant_improves_normalized_net_both_costs"] is improvement,
        "Variant improvement conclusion",
    )
    require(
        summary["new_fits"] == 1
        and summary["control_refits"] == 0
        and summary["untouched_outer"] is False
        and summary["promotion_approved"] is False,
        "Experiment boundary",
    )
    final_sources = load_json(args.learner_root / "final_source_hashes.json")
    for path, expected in final_sources.items():
        actual = cached_digest(verified_source_hashes, path)
        require(actual == expected, "Final oracle source rehash " + path)
    economic_outputs = {}
    for period in ("validation", "test"):
        for filename in ("summary.json", "prediction_hashes.json", "prediction_errors.json"):
            path = args.learner_root / period / filename
            economic_outputs[str(path.relative_to(args.learner_root))] = digest(path)
        for ident in policies():
            for suffix in (
                "attempts.parquet",
                "ledger.parquet",
                "daily_net.csv",
                "daily_adverse.csv",
                "daily_compliance.csv",
            ):
                path = args.learner_root / period / f"{ident}_{suffix}"
                economic_outputs[str(path.relative_to(args.learner_root))] = digest(path)
    economic_outputs.update(paired_files)
    result = {
        "status": "PASS_INDEPENDENT_EPISODE_LEARNER_ECONOMIC_AUDIT",
        "scope": "EPISODE_REPRESENTATION_IDENTITY_AND_ECONOMIC_EXECUTION_GIVEN_PREDICTIONS",
        "binding": {
            "learner_root": str(args.learner_root.resolve()),
            "learner_summary_sha256": digest(summary_path),
            "freeze_sha256": digest(args.learner_root / "freeze.json"),
            "identity_sha256": identity_sha,
            "completion_sha256": digest(args.learner_root / "completion.complete.json"),
            "validation_prediction_manifest_sha256": digest(
                args.learner_root / "validation" / "prediction_hashes.json"
            ),
            "test_prediction_manifest_sha256": digest(
                args.learner_root / "test" / "prediction_hashes.json"
            ),
            "oracle_index_sha256": digest(index_path),
            "oracle_completion_sha256": digest(args.oracle_root / "completion.json"),
            "oracle_full_audit_sha256": digest(args.oracle_audit),
            "original_learner_audit_sha256": digest(args.original_audit),
            "repair_script_sha256": digest(args.repair_script),
            "repair_record_sha256": digest(repair_root / "repair.json"),
            "repair_completion_sha256": digest(repair_root / "completion.json"),
            "repair_runtime_sha256": digest(args.repair_runtime),
            "audit_script_sha256": digest(__file__),
            "spec_sha256": digest(
                Path(__file__).with_name("EPISODE_LEARNER_ECONOMIC_AUDIT_SPEC.md")
            ),
        },
        "matrix_identity": matrix_identity,
        "validation": validation_counts,
        "test": test_counts,
        "verified_economic_outputs": economic_outputs,
        "selection": selection,
        "arms": arms,
        "candidate": candidate,
        "economic_gate": gate,
        "daily_test_gate": day_gate,
        "combined_gate_passes": combined,
        "prediction_inference_reproduced": False,
        "model_training_reproduced": False,
        "original_prefix_and_episode_join_rebuilt": True,
        "test_is_seen_development": True,
        "technical_ready": False,
        "promotion_approved": False,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (args.output / "audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        if "--output" in sys.argv:
            output = Path(sys.argv[sys.argv.index("--output") + 1])
            if output.exists():
                (output / "audit_failure.json").write_text(
                    json.dumps({"status": "AUDIT_FAILED", "traceback": traceback.format_exc()},
                               indent=2),
                    encoding="utf-8",
                )
        raise
