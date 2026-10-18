"""Synthetic regret identities; never read market data or learner artifacts."""

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location(
    "learner_regret", Path(__file__).with_name("analyze_learner_regret.py")
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    actions = pd.DataFrame(
        dict(
            action_id=np.arange(7),
            state_i=[0, 0, 0, 0, 1, 3, 1],
            right=[0, 0, 0, 1, 0, 0, 0],
            contract_i=[0, 0, 1, 2, 0, 0, 0],
            target_level_id=[0, 1, 0, 0, 0, 0, 1],
        )
    )
    labels = pd.DataFrame(
        dict(
            action_id=np.arange(7),
            status=["FILLED"] * 6 + ["NO_FILL"],
            exit_i=[2, 2, 2, 2, 3, 5, 2],
            net_base=[8.0, 6.0, 4.0, 2.0, 12.0, 3.0, 0.0],
        )
    )
    values = np.array([12.0, 12.0, 3.0, 3.0, 0.0, 0.0, 0.0, 0.0])
    return actions, labels, values


def attempts(actions, labels, ids):
    joined = actions.merge(labels, on="action_id")
    return (
        joined.loc[joined.action_id.isin(ids)]
        .sort_values("state_i")
        .reset_index(drop=True)
    )


@pytest.mark.parametrize(
    "choice,expected",
    [(1, (1.0, 0.0, 0.0, 2.0)), (2, (1.0, 0.0, 4.0, 0.0)), (3, (1.0, 6.0, 0.0, 0.0))],
)
def test_nested_attribution_and_skipping_busy_minutes(choice, expected):
    a, y, v = fixture()
    trace, summary = m.decompose_day(a, y, v, attempts(a, y, [choice]), first=0, last=4)
    assert trace.state_i.tolist() == [0, 3, 4]  # No double counting while open.
    row = trace.iloc[0]
    actual = tuple(
        row[k + "_regret_usd"] for k in ("entry_timing", "side", "contract", "target")
    )
    assert actual == expected
    assert summary["wait_regret_usd"] == 3
    assert summary["hindsight_gap_usd"] == 12 - y.loc[choice, "net_base"]
    assert summary["telescoping_error_usd"] == 0


def test_oracle_path_has_zero_gap_even_when_initially_waiting():
    a, y, v = fixture()
    trace, summary = m.decompose_day(a, y, v, attempts(a, y, [4]), first=0, last=4)
    assert trace.decision.tolist() == ["WAIT", "FILLED", "WAIT"]
    assert summary["learner_net_base"] == 12
    assert summary["hindsight_gap_usd"] == 0
    assert summary["filled_hindsight_optimal_count"] == 1


def test_no_fill_waits_one_minute_without_rescuing_another_action():
    a, y, v = fixture()
    trace, summary = m.decompose_day(a, y, v, attempts(a, y, [6, 5]), first=0, last=4)
    assert trace.state_i.tolist() == [0, 1, 2, 3]
    assert trace.decision.tolist() == ["WAIT", "NO_FILL", "WAIT", "FILLED"]
    assert summary["learner_net_base"] == 3
    assert summary["no_fill_regret_usd"] == 9
    assert summary["hindsight_gap_usd"] == 9


def test_cash_wait_gap_equals_entire_oracle_without_claiming_avoidable_loss():
    a, y, v = fixture()
    trace, summary = m.decompose_day(a, y, v, attempts(a, y, []), first=0, last=4)
    assert len(trace) == 5
    assert summary["learner_net_base"] == 0
    assert summary["wait_regret_usd"] == summary["hindsight_gap_usd"] == 12
    assert summary["positive_regret_waits"] == 2


def test_losing_chosen_trade_is_retained_in_full_gap():
    a, y, v = fixture()
    y.loc[y.action_id == 3, "net_base"] = -5.0
    _, summary = m.decompose_day(a, y, v, attempts(a, y, [3]), first=0, last=4)
    assert summary["learner_net_base"] == -5
    assert summary["hindsight_gap_usd"] == 17
    assert summary["side_regret_usd"] == 13


def test_empty_action_day_is_valid_zero_regret():
    a, y, _ = fixture()
    trace, summary = m.decompose_day(
        a.iloc[:0], y.iloc[:0], np.zeros(8), attempts(a, y, []), first=0, last=4
    )
    assert trace.offered_actions.sum() == 0
    assert summary["visited_states"] == 5
    assert summary["hindsight_gap_usd"] == 0


def test_changed_oracle_values_and_tampered_attempts_fail():
    a, y, v = fixture()
    wrong = v.copy()
    wrong[0] = 13
    with pytest.raises(ValueError, match="Bellman"):
        m.decompose_day(a, y, wrong, attempts(a, y, []), first=0, last=4)
    chosen = attempts(a, y, [1])
    chosen.loc[0, "net_base"] += 1
    with pytest.raises(ValueError, match="payoff"):
        m.decompose_day(a, y, v, chosen, first=0, last=4)


def test_attempt_during_open_position_is_not_silently_ignored():
    a, y, v = fixture()
    with pytest.raises(ValueError, match="busy"):
        m.decompose_day(a, y, v, attempts(a, y, [0, 4]), first=0, last=4)


def test_ledger_check_preserves_no_fill_but_excludes_it_from_filled_ledger():
    a, y, _ = fixture()
    chosen = attempts(a, y, [6, 5])
    m.check_ledger(chosen, chosen.loc[chosen.status == "FILLED"].copy())
    with pytest.raises(AssertionError):
        m.check_ledger(chosen, chosen)


def test_incomplete_learners_fail_before_opening_any_other_file(tmp_path):
    learner = tmp_path / "learner"
    learner.mkdir()
    (learner / "summary.json").write_text(json.dumps({"status": "RUNNING"}))
    with pytest.raises(ValueError, match="must finish"):
        m.load_authorities(learner, tmp_path / "does_not_exist")


@pytest.mark.parametrize("policy", ["gbt_net__0", "CASH"])
def test_completed_authority_binds_audit_files_and_selected_test(tmp_path, policy):
    learner, engine = tmp_path / "learner", tmp_path / "engine"
    (learner / "test").mkdir(parents=True)
    engine.mkdir()
    (engine / "index.parquet").write_bytes(b"synthetic index only hashed")
    authority = engine / "audit.json"
    authority.write_text("synthetic verified audit authority")
    digest = m.sha(authority)
    selected = {"policy": policy}
    metrics = {"gbt_net__0": {"base_net_usd": 3.0}}
    result = dict(
        status="COMPLETED_CAUSAL_LEARNER_DEVELOPMENT",
        selected_policy=selected,
        selected_test=None if policy == "CASH" else metrics[policy],
    )
    m.write_json(learner / "summary.json", result)
    m.write_json(learner / "test" / "summary.json", metrics)
    m.write_json(
        learner / "freeze.json",
        dict(
            selected_policy=selected,
            artifacts={},
            oracle_audit=dict(
                status="PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT",
                binding=dict(
                    engine_root=str(engine),
                    index_sha256=m.sha(engine / "index.parquet"),
                ),
                verified_files={str(authority): digest},
            ),
        ),
    )
    assert m.load_authorities(learner, engine)[0] == result
    authority.write_text("changed authority")
    with pytest.raises(ValueError, match="Changed full oracle audit authority"):
        m.load_authorities(learner, engine)
    authority.write_text("synthetic verified audit authority")
    result["selected_test"] = {"base_net_usd": 999.0}
    m.write_json(learner / "summary.json", result)
    with pytest.raises(ValueError, match="Selected test summary differs"):
        m.load_authorities(learner, engine)


def test_complete_synthetic_artifact_pipeline_with_missing_day(tmp_path, monkeypatch):
    learner, engine, output = (
        tmp_path / name for name in ("learner", "engine", "diagnostics")
    )
    learner.mkdir()
    engine.mkdir()
    selected = {"policy": "gbt_net__0", "model": "gbt_net", "threshold": 0.0}
    dates = {"validation": "20250103", "test": "20260105"}
    index, all_attempts = [], {}
    a, y, short_value = fixture()
    a["state_i"] += 60
    y["exit_i"] += 60
    value = np.zeros(387)
    value[60:68] = short_value
    for period, date in dates.items():
        all_attempts[period] = []
        for ticker in m.TICKERS:
            root = engine / ticker / date
            absent = ticker == "QQQ" and period == "test"
            record = dict(
                ticker=ticker,
                date=date,
                day_root=str(root),
                status="MISSING_SOURCE" if absent else "COMPLETE",
                net_base=0.0 if absent else 12.0,
            )
            if not absent:
                root.mkdir(parents=True)
                a.to_parquet(root / "actions.parquet", index=False)
                y.to_parquet(root / "labels.parquet", index=False)
                np.save(root / "oracle_value.npy", value, allow_pickle=False)
                for name in ("actions", "labels"):
                    record[name + "_sha256"] = m.sha(root / (name + ".parquet"))
                record["oracle_value_sha256"] = m.sha(root / "oracle_value.npy")
                picked = attempts(a, y, [6, 5])
                picked["ticker"], picked["date"], picked["policy"] = (
                    ticker,
                    date,
                    selected["policy"],
                )
                all_attempts[period].append(picked)
            index.append(record)
    pd.DataFrame(index).to_parquet(engine / "index.parquet", index=False)
    pd.DataFrame({"date": list(dates.values())}).to_csv(
        learner / "expected_full_calendar.csv", index=False
    )
    for period in dates:
        destination = learner / period
        destination.mkdir()
        picked = pd.concat(all_attempts[period], ignore_index=True)
        picked.to_parquet(destination / "gbt_net__0_attempts.parquet", index=False)
        picked.loc[picked.status == "FILLED"].to_parquet(
            destination / "gbt_net__0_ledger.parquet", index=False
        )
        metrics = {
            "gbt_net__0": {
                "tickers": {
                    ticker: {
                        "base_net_usd": 0.0
                        if ticker == "QQQ" and period == "test"
                        else 3.0,
                        "trades": 0 if ticker == "QQQ" and period == "test" else 1,
                    }
                    for ticker in m.TICKERS
                }
            }
        }
        m.write_json(destination / "summary.json", metrics)
    m.write_json(
        learner / "summary.json",
        dict(
            status="COMPLETED_CAUSAL_LEARNER_DEVELOPMENT",
            selected_policy=selected,
            selected_test=metrics[selected["policy"]],
        ),
    )
    m.write_json(
        learner / "freeze.json",
        dict(
            selected_policy=selected,
            artifacts={},
            oracle_audit=dict(
                status="PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT",
                binding=dict(
                    engine_root=str(engine),
                    index_sha256=m.sha(engine / "index.parquet"),
                ),
                verified_files={
                    str(engine / "index.parquet"): m.sha(engine / "index.parquet")
                },
            ),
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "regret",
            "--learner-root",
            str(learner),
            "--engine-root",
            str(engine),
            "--output",
            str(output),
        ],
    )
    m.main()
    summary = json.loads((output / "summary.json").read_text())
    assert summary["totals"]["test/QQQ"]["missing_source_days"] == 1
    assert summary["totals"]["test/SPY"]["hindsight_gap_usd"] == 9
    assert summary["maximum_daily_telescoping_error_usd"] == 0
    daily = pd.read_parquet(output / "daily_regret.parquet")
    events = pd.read_parquet(output / "visited_decisions.parquet")
    assert len(daily) == 6
    assert events.decision.eq("NO_FILL").sum() == 5
