"""Synthetic independent short-session audit fixtures."""

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import audit_causal_short_economics as audit
from test_audit_causal_rollout_economics import market


def short_market():
    actions, labels, scores = market()
    labels.loc[labels.exit_i == 385, "exit_i"] = 205
    return actions, labels, scores


def test_h_transitions_ties_and_strict_threshold():
    actions, labels, scores = short_market()
    tried, ledger = audit.schedule(actions, labels.iloc[::-1], scores, 0)
    assert tried.action_id.tolist() == [2, 10, 21, 30]
    assert tried.has_filled_before.tolist() == [0, 0, 1, 1]
    assert ledger.action_id.tolist() == [10, 21, 30]
    high, _ = audit.schedule(actions, labels, scores, 10)
    assert high.action_id.tolist() == [20]


@pytest.mark.parametrize("column,value", [("state_i", 196), ("exit_i", 206)])
def test_short_bounds(column, value):
    actions, labels, scores = short_market()
    target = actions if column == "state_i" else labels
    target.loc[target.index[-1], column] = value
    with pytest.raises(AssertionError):
        audit.schedule(actions, labels, scores, 0)


def test_last_state_195_exits_205():
    actions = pd.DataFrame(dict(action_id=[0], state_i=[195]))
    labels = pd.DataFrame(
        dict(action_id=[0], status=["FILLED"], exit_i=[205], net_base=[-5.0])
    )
    tried, ledger = audit.schedule(actions, labels, np.array([[6.0, -1.0]]), 5)
    assert len(ledger) == 1 and tried.has_filled_before.tolist() == [0]


def test_cost_floor_and_no_fill():
    labels = pd.DataFrame(
        dict(
            status=["FILLED", "NO_FILL"],
            entry_ask=[1.0, np.nan],
            exit_bid=[0.0, np.nan],
            net_base=[-103.6, 0.0],
            net_adverse=[-104.6, 0.0],
        )
    )
    audit.check_costs(labels)
    labels.loc[0, "net_base"] -= 1
    with pytest.raises(AssertionError):
        audit.check_costs(labels)


def test_prediction_alignment_schema_and_nonfinite():
    actions, _, scores = short_market()
    packed = dict(
        action_id=actions.action_id.to_numpy(), state_i=actions.state_i.to_numpy()
    )
    for model, digest in audit.MODEL_SHA.items():
        packed[model], packed[model + "_sha256"] = scores.copy(), np.array(digest)
    audit.scores_checked(actions, packed)
    packed["action_id"] = packed["action_id"][::-1]
    with pytest.raises(AssertionError):
        audit.scores_checked(actions, packed)
    packed["action_id"] = actions.action_id.to_numpy()
    packed["net_control"][0, 0] = np.nan
    with pytest.raises(AssertionError):
        audit.scores_checked(actions, packed)


def test_marker_exact_members_and_corrupt(tmp_path):
    member = tmp_path / "a.json"
    member.write_text("{}")
    marker = dict(
        status="COMPLETE", binding="binding", files={"a.json": audit.sha(member)}
    )
    (tmp_path / "stage.complete.json").write_text(json.dumps(marker))
    audit.verify_marker(tmp_path, "stage", "binding", audit.Seal(), [member])
    with pytest.raises(AssertionError):
        audit.verify_marker(tmp_path, "stage", "binding", audit.Seal(), [])
    member.write_text('{"changed":true}')
    with pytest.raises(AssertionError):
        audit.verify_marker(tmp_path, "stage", "binding", audit.Seal(), [member])


def test_calendar_missing_duplicate():
    expected = {("SPY", "20250703")}
    frame = pd.DataFrame(
        [
            dict(policy=p, ticker="SPY", date="20250703", source_available=True)
            for p in audit.independent.POLICIES
        ]
    )
    audit.check_calendar(frame, expected)
    with pytest.raises(AssertionError):
        audit.check_calendar(frame.iloc[:-1], expected)
    with pytest.raises(AssertionError):
        audit.check_calendar(pd.concat([frame, frame.iloc[:1]]), expected)


def test_no_future_reward_in_choice():
    actions, labels, scores = short_market()
    before, _ = audit.schedule(actions, labels, scores, 0)
    labels.loc[labels.status == "FILLED", "net_base"] *= -1000
    after, _ = audit.schedule(actions, labels, scores, 0)
    assert before.action_id.tolist() == after.action_id.tolist()


def test_atomic_publication_preserves_failure(tmp_path, monkeypatch):
    path = tmp_path / "audit.json"

    def fail_replace(source, target):
        assert json.loads(Path(source).read_text()) == {"status": "PASS"}
        assert not Path(target).exists()
        raise OSError("synthetic interruption")

    with monkeypatch.context() as patch:
        patch.setattr(audit.os, "replace", fail_replace)
        with pytest.raises(OSError):
            audit.publish_json(path, {"status": "PASS"})
    assert not path.exists() and path.with_suffix(".json.tmp").exists()
    second = tmp_path / "second.json"
    audit.publish_json(second, {"status": "PASS"})
    assert json.loads(second.read_text()) == {"status": "PASS"}
    assert not second.with_suffix(".json.tmp").exists()
