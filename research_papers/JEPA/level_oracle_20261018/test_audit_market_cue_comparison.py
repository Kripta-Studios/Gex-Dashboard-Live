import numpy as np
import pandas as pd
import pytest
import json

from audit_market_cue_comparison import (calibration_report, calibration_sums, coverage,
                                         digest, rehash_memo, schedule, verify_marker)


def actions_labels():
    actions = pd.DataFrame({"action_id": [4, 3, 8, 9], "state_i": [60, 60, 61, 65]})
    labels = pd.DataFrame({"action_id": [3, 4, 8, 9],
                           "status": ["NO_FILL", "FILLED", "FILLED", "FILLED"],
                           "exit_i": [61, 64, 64, 70],
                           "net_base": [0.0, 10.0, 20.0, 30.0],
                           "net_adverse": [0.0, 8.0, 18.0, 28.0]})
    return actions, labels


def test_scheduler_tie_lower_action_no_fill_retries_and_fill_blocks():
    actions, labels = actions_labels()
    _, attempts, ledger = schedule(actions, labels, [5.0, 5.0, 4.0, 6.0], 210)
    assert attempts.action_id.tolist() == [3, 8, 9]
    assert attempts.has_filled_before.tolist() == [0, 0, 1]
    assert ledger.action_id.tolist() == [8, 9]


def test_strict_zero_threshold_waits():
    actions, labels = actions_labels()
    _, attempts, _ = schedule(actions, labels, [0.0, -1.0, 0.0, -2.0], 210)
    assert attempts.empty


def test_full_clock_rejects_late_action_and_short_accepts_195():
    actions = pd.DataFrame({"action_id": [1], "state_i": [195]})
    labels = pd.DataFrame({"action_id": [1], "status": ["FILLED"], "exit_i": [205],
                           "net_base": [1.0], "net_adverse": [0.0]})
    _, attempts, _ = schedule(actions, labels, [1.0], 210)
    assert len(attempts) == 1
    with pytest.raises(AssertionError, match="Decision horizon"):
        schedule(pd.DataFrame({"action_id": [1], "state_i": [376]}), labels, [1.0], 390)


def test_calibration_fixed_bins_and_merge():
    rows = calibration_sums(np.array([-20.0, 0.0, 10.0]), np.array([-10.0, 5.0, 20.0]),
                            100.0, np.array([0.5, 1.0, 0.5]))
    assert sum(row["n"] for row in rows) == 3
    report = calibration_report([rows])
    assert sum(row["weight"] for row in report) == 2.0


def test_coverage_distinguishes_missing_and_zero_trade():
    rows = [{"ticker": "SPY", "date": "20260401", "source_status": "MISSING_SOURCE",
             "trades": 0, "net_base": 0.0, "net_adverse": 0.0},
            {"ticker": "QQQ", "date": "20260102", "source_status": "COMPLETE",
             "trades": 0, "net_base": 0.0, "net_adverse": 0.0}]
    result = coverage(rows)
    assert result["universal_daily_status"] == "NO_EVALUABLE"
    assert result["available_days_without_fill"] == 1


def test_marker_requires_consumed_members_and_final_rehash_detects_mutation(tmp_path):
    artifact = tmp_path / "used.txt"
    artifact.write_text("sealed", encoding="utf-8")
    marker = {"status": "COMPLETE", "binding": "freeze",
              "files": {"nested\\used.txt": digest(artifact)}, "extra": {"sources": {}}}
    nested = tmp_path / "nested"
    nested.mkdir()
    artifact.replace(nested / "used.txt")
    artifact = nested / "used.txt"
    marker["files"]["nested\\used.txt"] = digest(artifact)
    (tmp_path / "unit.complete.json").write_text(json.dumps(marker), encoding="utf-8")
    memo = {}
    with pytest.raises(AssertionError, match="Marker files"):
        verify_marker(tmp_path, "unit", "freeze", memo, ["required.txt"])
    verify_marker(tmp_path, "unit", "freeze", memo, ["nested/used.txt"])
    artifact.write_text("changed", encoding="utf-8")
    with pytest.raises(AssertionError, match="Consumed artifact changed"):
        rehash_memo(memo)
