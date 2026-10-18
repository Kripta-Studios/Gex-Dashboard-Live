"""Outcome-free fixtures for the independent learner economic auditor."""
import importlib.util
import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd

SPEC = importlib.util.spec_from_file_location(
    "audit_learner_economics_fixture", Path(__file__).with_name("audit_learner_economics.py")
)
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def frames():
    actions = pd.DataFrame([
        {"action_id": 10, "state_i": 60},
        {"action_id": 11, "state_i": 60},
        {"action_id": 20, "state_i": 61},
        {"action_id": 30, "state_i": 62},
        {"action_id": 40, "state_i": 66},
    ])
    labels = pd.DataFrame([
        {"action_id": 10, "status": "NO_FILL", "exit_i": 61, "net_base": 0.0,
         "net_adverse": 0.0},
        {"action_id": 11, "status": "FILLED", "exit_i": 65, "net_base": 20.0,
         "net_adverse": 18.0},
        {"action_id": 20, "status": "FILLED", "exit_i": 64, "net_base": 5.0,
         "net_adverse": 3.0},
        {"action_id": 30, "status": "FILLED", "exit_i": 63, "net_base": -2.0,
         "net_adverse": -4.0},
        {"action_id": 40, "status": "FILLED", "exit_i": 68, "net_base": 7.0,
         "net_adverse": 5.0},
    ])
    return actions, labels


def test_scheduler_tie_threshold_nofill_and_no_overlap():
    actions, labels = frames()
    scores = np.array([12.0, 12.0, 11.0, 10.0, 9.0])
    ranked = audit.rank_by_state(actions, scores)
    assert actions.iloc[ranked].action_id.tolist() == [10, 20, 30, 40]
    attempts, ledger = audit.schedule(actions, labels, scores, 10.0, ranked)
    # Lower ID wins state-60 tie and NO_FILL advances one state; score==10 WAITs.
    assert attempts.action_id.tolist() == [10, 20]
    assert ledger.action_id.tolist() == [20]
    # The filled action exits at 64, so state 66 remains eligible under a lower threshold.
    attempts, ledger = audit.schedule(actions, labels, scores, 5.0, ranked)
    assert attempts.action_id.tolist() == [10, 20, 40]
    assert ledger.action_id.tolist() == [20, 40]


def test_metrics_use_exit_order_realized_drawdown_and_both_costs():
    frame = pd.DataFrame({
        "net_base": [5.0, -8.0, 4.0], "net_adverse": [3.0, -10.0, 2.0],
        "reason": ["TARGET", "STOP", "EOD"], "hold_minutes": [3, 7, 5],
    })
    metrics = audit.economic_metrics(frame)
    assert metrics["base_net_usd"] == 1.0
    assert metrics["adverse_net_usd"] == -5.0
    assert metrics["base_pf"] == 9 / 8
    assert metrics["base_max_drawdown_usd"] == 8.0
    assert metrics["holding_minutes"] == {"min": 3.0, "median": 5.0, "max": 7.0}
    assert all(metrics["exit_reasons"][reason]["trades"] == 1
               for reason in ("TARGET", "STOP", "EOD"))


def blank_summary(net):
    return {"tickers": {ticker: {"base_net_usd": net} for ticker in audit.TICKERS}}


def test_cash_and_fixed_policy_order_selection():
    scales = {ticker: 100.0 for ticker in audit.TICKERS}
    validation = {ident: blank_summary(0.0) for ident in audit.policies()}
    winner, _ = audit.select_policy(validation, scales)
    assert winner["policy"] == "CASH"
    validation["gbt_net__0"] = blank_summary(10.0)
    validation["gbt_net__5"] = blank_summary(10.0)
    winner, _ = audit.select_policy(validation, scales)
    assert winner["policy"] == "gbt_net__0"


def test_gate_is_selected_policy_only_and_cash_fails():
    assert not audit.economic_gate({"policy": "CASH"}, {})["passes"]
    selected = {"policy": "gbt_net__0"}
    ticker_metrics = {
        "trades": 60, "base_net_usd": 10.0, "adverse_net_usd": 1.0,
        "base_pf": 1.2, "base_pf_infinite": False,
    }
    test = {"gbt_net__0": {
        "tickers": {ticker: ticker_metrics for ticker in audit.TICKERS},
        "months": {ticker: {f"20260{month}": {"base_net_usd": 1.0 if month <= 3 else -1.0}
                             for month in range(1, 7)} for ticker in audit.TICKERS},
    }}
    assert audit.economic_gate(selected, test)["passes"]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def write_synthetic_period(root, name, date, day_root, calendar):
    target = root / name
    target.mkdir()
    actions = pd.read_parquet(day_root / "actions.parquet")
    labels = pd.read_parquet(day_root / "labels.parquet")
    scores = {model: np.array([1.0]) for model in audit.MODELS}
    prediction = target / f"SPXW_{date}.npz"
    np.savez_compressed(prediction, action_ids=actions.action_id.to_numpy(), **scores)
    write_json(target / "prediction_hashes.json", {prediction.name: audit.digest(prediction)})
    summaries = {}
    lower, upper = (("20250101", "20260101") if name == "validation"
                    else ("20260101", "20260701"))
    months = pd.period_range(pd.Timestamp(lower), pd.Timestamp(upper) - pd.Timedelta(days=1),
                             freq="M").strftime("%Y%m")
    period_calendar = calendar.loc[(calendar >= lower) & (calendar < upper)]
    for model in audit.MODELS:
        ranked = audit.rank_by_state(actions, scores[model])
        for threshold in audit.THRESHOLDS:
            ident = audit.policy_id(model, threshold)
            attempts, ledger = audit.schedule(actions, labels, scores[model], threshold, ranked)
            for frame in (attempts, ledger):
                frame["ticker"], frame["date"], frame["policy"] = "SPXW", date, ident
            attempts.to_parquet(target / f"{ident}_attempts.parquet", index=False)
            ledger.to_parquet(target / f"{ident}_ledger.parquet", index=False)
            daily = pd.DataFrame(0.0, index=period_calendar, columns=audit.TICKERS)
            daily.to_csv(target / f"{ident}_daily_net.csv")
            summaries[ident] = audit.summarize(ledger, months)
    write_json(target / "summary.json", summaries)
    return summaries


def test_minimal_end_to_end_main_cash_nofill_and_bindings(tmp_path, monkeypatch):
    learner, oracle = tmp_path / "learner", tmp_path / "oracle"
    learner.mkdir()
    oracle.mkdir()
    dates = ("20250102", "20260102")
    index_rows = []
    for date in dates:
        day = oracle / "SPXW" / date
        day.mkdir(parents=True)
        pd.DataFrame([{"action_id": 1, "state_i": 60}]).to_parquet(
            day / "actions.parquet", index=False
        )
        pd.DataFrame([{"action_id": 1, "status": "NO_FILL", "exit_i": 61,
                       "net_base": 0.0, "net_adverse": 0.0}]).to_parquet(
            day / "labels.parquet", index=False
        )
        index_rows.append({
            "ticker": "SPXW", "date": date, "status": "COMPLETE", "day_root": str(day),
            "actions_sha256": audit.digest(day / "actions.parquet"),
            "labels_sha256": audit.digest(day / "labels.parquet"),
        })
    index_path = oracle / "index.parquet"
    pd.DataFrame(index_rows).to_parquet(index_path, index=False)
    (oracle / "completion.json").write_text("{}", encoding="utf-8")
    authority = tmp_path / "oracle_audit.json"
    write_json(authority, {
        "status": "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT",
        "binding": {"index_sha256": audit.digest(index_path)},
    })
    base_dates = [value for value in pd.bdate_range("2023-01-03", periods=900).strftime("%Y%m%d")
                  if value not in dates][:865]
    calendar = pd.Series(sorted([*base_dates, *dates]), name="date")
    assert len(calendar) == 867
    pd.DataFrame({"date": calendar}).to_csv(learner / "expected_full_calendar.csv", index=False)
    missing_rows = [{"ticker": "SPY", "date": date, "status": "MISSING_SOURCE",
                     "day_root": None, "actions_sha256": None, "labels_sha256": None}
                    for date in calendar if date not in dates]
    pd.concat([pd.DataFrame(index_rows), pd.DataFrame(missing_rows)], ignore_index=True).to_parquet(
        index_path, index=False
    )
    write_json(authority, {
        "status": "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT",
        "binding": {"index_sha256": audit.digest(index_path), "engine_root": str(oracle.resolve())},
    })
    validation = write_synthetic_period(learner, "validation", dates[0],
                                        Path(index_rows[0]["day_root"]), calendar)
    scales = {ticker: 100.0 for ticker in audit.TICKERS}
    write_json(learner / "normalizers.json", {"risk_scales_usd": scales})
    for name in ("train_models.py", "LEARNER_PLAN.md", "level_engine.py", "run_policy.py",
                 "PROTOCOL.md"):
        (learner / name).write_text(name, encoding="utf-8")
    selection, choices = audit.select_policy(validation, scales)
    artifacts = {
        name: audit.digest(learner / name)
        for name in ("normalizers.json", "validation/summary.json",
                     "validation/prediction_hashes.json")
    }
    freeze = {
        "selected_policy": selection, "validation_choices": choices, "artifacts": artifacts,
        "oracle_audit": {"sha256": audit.digest(authority),
                         "binding": {"engine_root": str(oracle.resolve())},
                         "verified_files": {str(authority): audit.digest(authority)}},
        "script_sha256": audit.digest(learner / "train_models.py"),
        "plan_sha256": audit.digest(learner / "LEARNER_PLAN.md"),
        "engine_sha256": audit.digest(learner / "level_engine.py"),
        "scheduler_sha256": audit.digest(learner / "run_policy.py"),
        "protocol_sha256": audit.digest(learner / "PROTOCOL.md"),
        "learner_test_economics_evaluated": False,
    }
    write_json(learner / "freeze.json", freeze)
    os.utime(learner / "freeze.json", (1, 1))
    test = write_synthetic_period(learner, "test", dates[1],
                                  Path(index_rows[1]["day_root"]), calendar)
    write_json(learner / "oracle_sources_final.json", {
        str(index_path): audit.digest(index_path)
    })
    write_json(learner / "feature_rehash.json", {"synthetic": True})
    write_json(learner / "summary.json", {
        "status": "COMPLETED_CAUSAL_LEARNER_DEVELOPMENT",
        "selected_policy": selection, "selected_test": None, "selected_cash_net_usd": 0,
        "provisional_gate": audit.economic_gate(selection, test),
        "validation_choices": choices, "risk_scales_usd": scales,
        "test_candidate_results_are_diagnostic_not_selection": True,
        "technical_ready": False, "promotion_approved": False,
    })
    output = tmp_path / "audit"
    monkeypatch.setattr(sys, "argv", ["audit", "--learner-root", str(learner),
                                     "--oracle-root", str(oracle), "--oracle-audit",
                                     str(authority), "--output", str(output)])
    audit.main()
    result = json.loads((output / "audit.json").read_text(encoding="utf-8"))
    assert result["status"] == "PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT"
    assert result["selected_policy"]["policy"] == "CASH"
    assert result["validation"]["attempts"] == 3  # threshold0, one per model, all NO_FILL.
