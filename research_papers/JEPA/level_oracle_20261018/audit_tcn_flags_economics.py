"""Independent economic audit of TCN flags given sealed predictions."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import traceback

import numpy as np
import pandas as pd

TICKERS = ("SPXW", "SPY", "QQQ")
MODELS = ("control", "variant")
THRESHOLDS = (0.0, 5.0, 10.0)
FIRST_STATE = 60
TOLERANCE = 1e-8


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


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


def daily_gate(ledger, calendar, available):
    counts = ledger.groupby(["ticker", "date"]).size().to_dict()
    frame = pd.DataFrame(
        [
            {
                "ticker": ticker,
                "date": date,
                "filled": int(counts.get((ticker, date), 0)),
                "status": "OBSERVABLE" if (ticker, date) in available else "NO_EVALUABLE",
            }
            for date in calendar
            for ticker in TICKERS
        ]
    )
    observed = frame.status == "OBSERVABLE"
    result = {
        "passes": bool(observed.all() and (frame.filled >= 1).all()),
        "expected_days": len(frame),
        "no_evaluable_days": int((~observed).sum()),
        "observable_days": int(observed.sum()),
        "observable_days_with_trade": int((observed & (frame.filled >= 1)).sum()),
        "observable_daily_pass": bool(
            observed.any() and (frame.loc[observed, "filled"] >= 1).all()
        ),
    }
    return result, frame


def select_validation(summaries, scales):
    scores = {
        ident: sum(
            summaries[ident]["tickers"][ticker]["base_net_usd"] / scales[ticker]
            for ticker in TICKERS
        )
        for ident in policies()
    }
    ordered = policies()
    ranked = sorted(ordered, key=lambda ident: (-scores[ident], ordered.index(ident)))
    eligible = [ident for ident in ranked if summaries[ident]["daily_gate"]["passes"]]
    return {
        "selected_policy": eligible[0] if eligible else None,
        "diagnostic_best_not_approved": None if eligible else ranked[0],
        "scores": scores,
        "eligible": eligible,
        "best_per_arm_2025": {
            model: next(ident for ident in ranked if ident.startswith(model))
            for model in MODELS
        },
    }


def economic_gate(selected_policy, test):
    summary = test[selected_policy]
    flags = {}
    for ticker in TICKERS:
        metrics = summary["tickers"][ticker]
        positive_months = sum(
            month["base_net_usd"] > 0 for month in summary["months"][ticker].values()
        )
        passed = (
            metrics["base_net_usd"] > 0
            and metrics["adverse_net_usd"] > 0
            and (
                metrics.get("base_pf_infinite", False)
                or (metrics["base_pf"] is not None and metrics["base_pf"] >= 1.2)
            )
            and metrics["trades"] >= 60
            and positive_months >= 3
        )
        flags[ticker] = {"passes": bool(passed), "positive_months": positive_months, **metrics}
    return {"passes": all(value["passes"] for value in flags.values()), "tickers": flags}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_files(files, context):
    for path, expected in files.items():
        require(digest(path) == expected, context + " " + path)


def audit_period(root, original_root, index, calendar, name, lower, upper):
    period = root / name
    rows = index.loc[
        (index.status == "COMPLETE") & (index.date >= lower) & (index.date < upper)
    ].sort_values(["date", "ticker"])
    expected_days = {f"{row.ticker}_{row.date}.json" for row in rows.itertuples(index=False)}
    manifest = load_json(period / "prediction_manifest.json")
    require(set(manifest) == expected_days, name + " manifest membership")
    actual_days = {
        path.name
        for path in period.glob("*.json")
        if len(path.stem.split("_")) == 2 and path.stem.split("_")[1].isdigit()
    }
    require(actual_days == expected_days, name + " daily sidecar membership")
    available = {(row.ticker, row.date) for row in rows.itertuples(index=False)}
    ledgers = {ident: [] for ident in policies()}
    attempts = {ident: [] for ident in policies()}
    prediction_rows = 0
    for number, row in enumerate(rows.itertuples(index=False), start=1):
        stem = f"{row.ticker}_{row.date}"
        done_path = period / f"{stem}.json"
        require(digest(done_path) == manifest[done_path.name], name + " daily manifest hash")
        done = load_json(done_path)
        verify_files(done["files"], name + " day files")
        verify_files(done["feature_files"], name + " feature files")
        verify_files(done["oracle_files"], name + " oracle files")
        prediction_path = period / f"{stem}.npz"
        with np.load(prediction_path, allow_pickle=False) as stored:
            require(set(stored.files) == {"action_ids", *MODELS}, "Prediction NPZ keys")
            action_ids = stored["action_ids"]
            scores = {model: stored[model].copy() for model in MODELS}
        day_root = Path(row.day_root)
        require(digest(day_root / "actions.parquet") == row.actions_sha256, "Action seal")
        require(digest(day_root / "labels.parquet") == row.labels_sha256, "Label seal")
        actions = pd.read_parquet(day_root / "actions.parquet")
        labels = pd.read_parquet(day_root / "labels.parquet")
        require(np.array_equal(action_ids, actions.action_id.to_numpy()), "Action alignment")
        require(all(np.isfinite(value).all() for value in scores.values()), "Finite scores")
        original_path = original_root / name / f"{stem}.npz"
        with np.load(original_path, allow_pickle=False) as original:
            require(
                np.array_equal(original["action_ids"], action_ids)
                and np.array_equal(original["tcn_teacher"], scores["control"]),
                "Exact original TCN control",
            )
        prediction_rows += len(actions)
        for model in MODELS:
            ranked = rank_by_state(actions, scores[model])
            for threshold in THRESHOLDS:
                ident = policy_id(model, threshold)
                reconstructed, ledger = schedule(
                    actions, labels, scores[model], threshold, ranked
                )
                reconstructed["ticker"] = row.ticker
                reconstructed["date"] = row.date
                reconstructed["policy"] = ident
                shard = pd.read_parquet(period / f"{stem}_{ident}.parquet")
                compare_frames(
                    reconstructed,
                    shard,
                    ["state_i", "action_id"],
                    name + " shard " + stem + " " + ident,
                )
                attempts[ident].append(reconstructed)
                ledgers[ident].append(ledger.assign(ticker=row.ticker, date=row.date, policy=ident))
        if number % 100 == 0 or number == len(rows):
            print(json.dumps({"stage": name, "days": number, "total": len(rows)}), flush=True)
    months = sorted(
        set(calendar.loc[(calendar >= lower) & (calendar < upper)].str[:6].tolist())
    )
    period_calendar = calendar.loc[(calendar >= lower) & (calendar < upper)].tolist()
    summaries = {}
    total_attempts = total_trades = 0
    for ident in policies():
        attempted = pd.concat(attempts[ident], ignore_index=True)
        ledger = pd.concat(ledgers[ident], ignore_index=True).sort_values(
            ["date", "exit_i", "ticker", "state_i"], kind="stable"
        ).reset_index(drop=True)
        actual_attempts = pd.read_parquet(period / f"{ident}_attempts.parquet")
        actual_ledger = pd.read_parquet(period / f"{ident}_ledger.parquet")
        compare_frames(
            attempted,
            actual_attempts,
            ["date", "ticker", "state_i", "action_id"],
            name + " attempts " + ident,
        )
        compare_frames(
            ledger,
            actual_ledger,
            ["date", "ticker", "exit_i", "state_i", "action_id"],
            name + " ledger " + ident,
        )
        for _, frame in ledger.groupby(["ticker", "date"]):
            ordered = frame.sort_values(["state_i", "action_id"])
            require(
                np.all(ordered.state_i.to_numpy()[1:] > ordered.exit_i.to_numpy()[:-1]),
                name + " overlap " + ident,
            )
        gate, coverage = daily_gate(ledger, period_calendar, available)
        actual_coverage = pd.read_parquet(period / f"{ident}_daily_coverage.parquet")
        compare_frames(
            coverage,
            actual_coverage,
            ["date", "ticker"],
            name + " daily coverage " + ident,
        )
        basic = summarize(ledger, months)
        summaries[ident] = {"daily_gate": gate, **basic}
        total_attempts += len(attempted)
        total_trades += len(ledger)
    compare_values(summaries, load_json(period / "summary.json"), name + " summary")
    return summaries, {
        "prediction_files": len(rows),
        "prediction_rows": prediction_rows,
        "attempts": total_attempts,
        "ledger_trades": total_trades,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--original-root", type=Path, required=True)
    parser.add_argument("--oracle-root", type=Path, required=True)
    parser.add_argument("--oracle-audit", type=Path, required=True)
    parser.add_argument("--original-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    identity = load_json(args.root / "identity.json")
    verify_files(identity["files"], "Identity source")
    completion = load_json(args.root / "completion.json")
    require(completion["status"] == "COMPLETE", "Completion status")
    verify_files(completion["files"], "Completion file")
    compatibility = load_json(args.root / "evaluation_runtime.json")
    require(
        compatibility["status"] == "BOUND_BEFORE_FIRST_VALIDATION_PREDICTION"
        and compatibility["training_unchanged"] is True,
        "Compatibility runtime",
    )
    verify_files(compatibility["files"], "Compatibility runtime file")
    compatibility_completion = load_json(
        args.root / "evaluation_runtime_completion.json"
    )
    require(
        compatibility_completion["status"] == "COMPLETE"
        and compatibility_completion["runtime_sha256"]
        == digest(args.root / "evaluation_runtime.json")
        and compatibility_completion["economic_completion_sha256"]
        == digest(args.root / "completion.json")
        and compatibility_completion["summary_sha256"]
        == digest(args.root / "summary.json"),
        "Compatibility completion",
    )
    verify_files(compatibility_completion["files"], "Compatibility completion file")
    oracle_audit = load_json(args.oracle_audit)
    require(
        oracle_audit["status"] == "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT",
        "Full oracle audit",
    )
    index_path = args.oracle_root / "index.parquet"
    require(
        digest(index_path) == oracle_audit["binding"]["index_sha256"],
        "Oracle index binding",
    )
    original_audit = load_json(args.original_audit)
    require(
        original_audit["status"] == "PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT"
        and Path(original_audit["binding"]["learner_root"]).resolve()
        == args.original_root.resolve(),
        "Original learner audit",
    )
    index = pd.read_parquet(index_path)
    index["date"] = index.date.astype(str)
    calendar = pd.read_csv(args.root / "expected_full_calendar.csv", dtype=str).date
    require(
        len(calendar) == 867
        and not calendar.duplicated().any()
        and set(calendar) == set(index.date),
        "Full calendar",
    )
    validation, validation_counts = audit_period(
        args.root,
        args.original_root,
        index,
        calendar,
        "validation",
        "20250101",
        "20260101",
    )
    scales = load_json(args.original_root / "normalizers.json")["risk_scales_usd"]
    selection = select_validation(validation, scales)
    freeze_path = args.root / "freeze.json"
    freeze = load_json(freeze_path)
    compare_values(selection, freeze["selection"], "Frozen selection")
    require(freeze["test_evaluated"] is False, "Freeze test disclosure")
    verify_files(freeze["files"], "Freeze file")
    test_npz = list((args.root / "test").glob("*.npz"))
    require(
        test_npz and freeze_path.stat().st_mtime <= min(path.stat().st_mtime for path in test_npz),
        "Freeze predates test",
    )
    test, test_counts = audit_period(
        args.root,
        args.original_root,
        index,
        calendar,
        "test",
        "20260101",
        "20260701",
    )
    summary_path = args.root / "summary.json"
    summary = load_json(summary_path)
    require(summary["status"] == "COMPLETE", "Summary status")
    compare_values(selection, summary["selection"], "Final selection")
    selected = selection["selected_policy"]
    expected_test = test[selected] if selected else None
    compare_values(expected_test, summary["selected_test"], "Selected test")
    if selected is None:
        gate = {"passes": False, "reason": "NO_VALIDATION_DAILY_COMPLIANT_POLICY"}
    else:
        gate = economic_gate(selected, test)
        gate["daily_gate"] = test[selected]["daily_gate"]
        gate["passes"] = gate["passes"] and gate["daily_gate"]["passes"]
    compare_values(gate, summary["gate"], "Final gate")
    compare_values(test, summary["test"], "Final test summaries")
    paired = {
        str(int(threshold)): {
            "base_delta_usd": test[policy_id("variant", threshold)]["pooled"][
                "base_net_usd"
            ]
            - test[policy_id("control", threshold)]["pooled"]["base_net_usd"],
            "adverse_delta_usd": test[policy_id("variant", threshold)]["pooled"][
                "adverse_net_usd"
            ]
            - test[policy_id("control", threshold)]["pooled"]["adverse_net_usd"],
        }
        for threshold in THRESHOLDS
    }
    compare_values(paired, summary["paired_same_threshold_test"], "Paired test")
    require(
        summary["development_seen"] is True
        and summary["promotion_approved"] is False
        and summary["freeze_sha256"] == digest(freeze_path),
        "Development boundary",
    )
    verified = {}
    for period in ("validation", "test"):
        for filename in ("summary.json", "prediction_manifest.json"):
            path = args.root / period / filename
            verified[str(path.relative_to(args.root))] = digest(path)
        for ident in policies():
            for suffix in ("attempts.parquet", "ledger.parquet", "daily_coverage.parquet"):
                path = args.root / period / f"{ident}_{suffix}"
                verified[str(path.relative_to(args.root))] = digest(path)
    result = {
        "status": "PASS_INDEPENDENT_TCN_FLAGS_ECONOMIC_AUDIT",
        "scope": "ECONOMIC_EXECUTION_GIVEN_SEALED_CONTROL_AND_VARIANT_PREDICTIONS",
        "binding": {
            "root": str(args.root.resolve()),
            "summary_sha256": digest(summary_path),
            "completion_sha256": digest(args.root / "completion.json"),
            "freeze_sha256": digest(freeze_path),
            "validation_manifest_sha256": digest(
                args.root / "validation/prediction_manifest.json"
            ),
            "test_manifest_sha256": digest(args.root / "test/prediction_manifest.json"),
            "oracle_index_sha256": digest(index_path),
            "oracle_full_audit_sha256": digest(args.oracle_audit),
            "original_learner_audit_sha256": digest(args.original_audit),
            "compatibility_runtime_sha256": digest(
                args.root / "evaluation_runtime.json"
            ),
            "compatibility_completion_sha256": digest(
                args.root / "evaluation_runtime_completion.json"
            ),
            "audit_script_sha256": digest(__file__),
            "spec_sha256": digest(
                Path(__file__).with_name("TCN_FLAGS_ECONOMIC_AUDIT_SPEC.md")
            ),
        },
        "validation": validation_counts,
        "test": test_counts,
        "selection": selection,
        "gate": gate,
        "paired_same_threshold_test": paired,
        "verified_economic_outputs": verified,
        "training_reproduced": False,
        "gpu_inference_reproduced": False,
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
                    json.dumps(
                        {"status": "AUDIT_FAILED", "traceback": traceback.format_exc()},
                        indent=2,
                    ),
                    encoding="utf-8",
                )
        raise


