"""Independent economic audit given sealed learner prediction vectors."""
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
MODELS = ("gbt_net", "gbt_advantage", "tcn_teacher")
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


def select_policy(validation, scales):
    choices = [{"policy": "CASH", "model": None, "threshold": None,
                "selection_score": 0.0}]
    for model in MODELS:
        for threshold in THRESHOLDS:
            ident = policy_id(model, threshold)
            score = sum(validation[ident]["tickers"][ticker]["base_net_usd"] / scales[ticker]
                        for ticker in TICKERS)
            choices.append({"policy": ident, "model": model, "threshold": threshold,
                            "selection_score": float(score)})
    return max(choices, key=lambda choice: choice["selection_score"]), choices


def economic_gate(selected, test):
    if selected["policy"] == "CASH":
        return {"passes": False, "reason": "CASH_SELECTED_NOT_A_PROFITABLE_LEARNER",
                "tickers": {}}
    summary = test[selected["policy"]]
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


def audit_period(learner_root, index, calendar, name, lower, upper):
    root = learner_root / name
    manifest = load_json(root / "prediction_hashes.json")
    rows = index.loc[(index.status == "COMPLETE") & (index.date >= lower)
                     & (index.date < upper)].sort_values(["date", "ticker"])
    expected_files = {f"{row.ticker}_{row.date}.npz" for row in rows.itertuples(index=False)}
    require(set(manifest) == expected_files, name + " prediction manifest membership")
    require({path.name for path in root.glob("*.npz")} == expected_files,
            name + " prediction file membership")
    collected_attempts = {ident: [] for ident in policies()}
    collected_ledgers = {ident: [] for ident in policies()}
    prediction_rows = 0
    started = time.monotonic()
    for number, row in enumerate(rows.itertuples(index=False), start=1):
        prediction_path = root / f"{row.ticker}_{row.date}.npz"
        require(digest(prediction_path) == manifest[prediction_path.name], "Prediction hash")
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
        prediction_rows += len(actions)
        for model in MODELS:
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
        expected_daily = (
            ledger.groupby(["date", "ticker"]).net_base.sum().unstack(fill_value=0)
            if len(ledger) else pd.DataFrame()
        )
        period_calendar = calendar.loc[(calendar >= lower) & (calendar < upper)]
        expected_daily = expected_daily.reindex(index=period_calendar, columns=TICKERS,
                                                fill_value=0).fillna(0)
        actual_daily = pd.read_csv(root / f"{ident}_daily_net.csv", index_col=0)
        actual_daily.index = actual_daily.index.astype(str)
        require(actual_daily.index.tolist() == expected_daily.index.tolist(),
                name + " daily calendar " + ident)
        require(actual_daily.columns.tolist() == list(TICKERS), name + " daily columns")
        require(np.allclose(actual_daily.to_numpy(float), expected_daily.to_numpy(float),
                            rtol=0, atol=TOLERANCE), name + " daily values " + ident)
        summaries[ident] = summarize(ledger, months)
        attempts_count += len(attempts)
        ledger_count += len(ledger)
    producer_summary = load_json(root / "summary.json")
    compare_values(summaries, producer_summary, name + " summary")
    return summaries, {"prediction_rows": prediction_rows, "attempts": attempts_count,
                       "ledger_trades": ledger_count, "prediction_files": len(rows)}


def verify_freeze(learner_root, validation, scales):
    freeze_path = learner_root / "freeze.json"
    freeze = load_json(freeze_path)
    for name, expected in freeze["artifacts"].items():
        require(digest(learner_root / name) == expected, "Freeze artifact " + name)
    for path, expected in freeze["oracle_audit"]["verified_files"].items():
        require(digest(path) == expected, "Freeze oracle authority " + path)
    for filename, key in (
        ("train_models.py", "script_sha256"),
        ("LEARNER_PLAN.md", "plan_sha256"),
        ("level_engine.py", "engine_sha256"),
        ("run_policy.py", "scheduler_sha256"),
        ("PROTOCOL.md", "protocol_sha256"),
    ):
        require(digest(learner_root / filename) == freeze[key], "Frozen source " + filename)
    selection, choices = select_policy(validation, scales)
    compare_values(selection, freeze["selected_policy"], "Frozen selection")
    compare_values(choices, freeze["validation_choices"], "Frozen choices")
    test_files = list((learner_root / "test").glob("*.npz"))
    require(test_files and freeze_path.stat().st_mtime <= min(path.stat().st_mtime for path in test_files),
            "Freeze must predate test predictions")
    require(freeze["learner_test_economics_evaluated"] is False, "Freeze test disclosure")
    return freeze, selection, choices


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--learner-root", type=Path, required=True)
    parser.add_argument("--oracle-root", type=Path, required=True)
    parser.add_argument("--oracle-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    index_path = args.oracle_root / "index.parquet"
    index = pd.read_parquet(index_path)
    index["date"] = index.date.astype(str)
    oracle_audit = load_json(args.oracle_audit)
    require(oracle_audit["status"] == "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT",
            "Full oracle audit status")
    require(digest(index_path) == oracle_audit["binding"]["index_sha256"], "Oracle index binding")
    summary_path = args.learner_root / "summary.json"
    summary = load_json(summary_path)
    require(summary["status"] == "COMPLETED_CAUSAL_LEARNER_DEVELOPMENT", "Learner completion")
    calendar = pd.read_csv(args.learner_root / "expected_full_calendar.csv", dtype={"date": str}).date
    require(len(calendar) == 867 and not calendar.duplicated().any(), "Expected calendar")
    require(set(calendar) == set(index.date), "Calendar/oracle-index date membership")
    validation, validation_counts = audit_period(
        args.learner_root, index, calendar, "validation", "20250101", "20260101"
    )
    scales = load_json(args.learner_root / "normalizers.json")["risk_scales_usd"]
    require(set(scales) == set(TICKERS) and all(float(value) > 0 for value in scales.values()),
            "Risk scales")
    freeze, selection, choices = verify_freeze(args.learner_root, validation, scales)
    require(freeze["oracle_audit"]["sha256"] == digest(args.oracle_audit),
            "Frozen oracle audit authority")
    require(Path(freeze["oracle_audit"]["binding"]["engine_root"]).resolve()
            == args.oracle_root.resolve(), "Frozen oracle engine root")
    test, test_counts = audit_period(
        args.learner_root, index, calendar, "test", "20260101", "20260701"
    )
    expected_test = None if selection["policy"] == "CASH" else test[selection["policy"]]
    compare_values(selection, summary["selected_policy"], "Final selected policy")
    compare_values(expected_test, summary["selected_test"], "Selected test")
    require(summary["selected_cash_net_usd"] == (0 if selection["policy"] == "CASH" else None),
            "Selected CASH accounting")
    compare_values(choices, summary["validation_choices"], "Final validation choices")
    compare_values(scales, summary["risk_scales_usd"], "Final risk scales")
    gate = economic_gate(selection, test)
    compare_values(gate, summary["provisional_gate"], "Provisional gate")
    require(summary["test_candidate_results_are_diagnostic_not_selection"] is True,
            "Test candidate disclosure")
    require(summary["technical_ready"] is False and summary["promotion_approved"] is False,
            "Promotion boundary")
    final_sources = load_json(args.learner_root / "oracle_sources_final.json")
    require(all(digest(path) == expected for path, expected in final_sources.items()),
            "Final oracle source rehash")
    feature_rehash = load_json(args.learner_root / "feature_rehash.json")
    require(feature_rehash and all(feature_rehash.values()), "Feature rehash")
    economic_outputs = {}
    for period in ("validation", "test"):
        for filename in ("summary.json", "prediction_hashes.json"):
            path = args.learner_root / period / filename
            economic_outputs[str(path.relative_to(args.learner_root))] = digest(path)
        for ident in policies():
            for suffix in ("attempts.parquet", "ledger.parquet", "daily_net.csv"):
                path = args.learner_root / period / f"{ident}_{suffix}"
                economic_outputs[str(path.relative_to(args.learner_root))] = digest(path)
    result = {
        "status": "PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT",
        "scope": "ECONOMIC_EXECUTION_GIVEN_SEALED_PREDICTIONS",
        "binding": {
            "learner_root": str(args.learner_root.resolve()),
            "learner_summary_sha256": digest(summary_path),
            "freeze_sha256": digest(args.learner_root / "freeze.json"),
            "validation_prediction_manifest_sha256": digest(
                args.learner_root / "validation" / "prediction_hashes.json"
            ),
            "test_prediction_manifest_sha256": digest(
                args.learner_root / "test" / "prediction_hashes.json"
            ),
            "oracle_index_sha256": digest(index_path),
            "oracle_completion_sha256": digest(args.oracle_root / "completion.json"),
            "oracle_full_audit_sha256": digest(args.oracle_audit),
            "audit_script_sha256": digest(__file__),
            "spec_sha256": digest(Path(__file__).with_name("LEARNER_ECONOMIC_AUDIT_SPEC.md")),
        },
        "validation": validation_counts,
        "test": test_counts,
        "verified_economic_outputs": economic_outputs,
        "selected_policy": selection,
        "provisional_gate": gate,
        "prediction_inference_reproduced": False,
        "model_training_reproduced": False,
        "feature_tensor_rebuilt": False,
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
