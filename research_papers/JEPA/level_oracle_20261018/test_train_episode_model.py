"""Representation, free timing, hard daily constraint and technical resume fixtures."""

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
spec = importlib.util.spec_from_file_location(
    "train_episode_model", Path(__file__).with_name("train_episode_model.py")
)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def episodes():
    values = np.repeat(np.array([62.0, 60.0, 61.0])[:, None], 35, axis=1)
    valid = np.ones((3, 35), bool)
    valid[1, 7] = False
    values[1, 7] = 0
    return {"state_i": np.array([62, 60, 61]), "values": values, "valid": valid}


def test_episode_join_preserves_requested_action_order_and_masks():
    block = m.join_episodes(episodes(), [60, 62, 60, 61])
    assert block.shape == (4, 70) and block.dtype == np.float32
    np.testing.assert_array_equal(block[:, 0], [60, 62, 60, 61])
    np.testing.assert_array_equal(block[:, 42], [0, 1, 0, 1])
    assert block[0, 7] == 0 and block[0, 35] == 1


def test_episode_missing_and_duplicate_keys_fail():
    with pytest.raises(ValueError, match="Missing"):
        m.join_episodes(episodes(), [59])
    data = episodes()
    data["state_i"][0] = 60
    with pytest.raises(ValueError, match="Duplicate"):
        m.join_episodes(data, [60])


def test_episode_unknown_value_and_overflow_fail():
    data = episodes()
    data["values"][1, 7] = 2
    with pytest.raises(ValueError, match="missingness"):
        m.join_episodes(data, [60])
    data = episodes()
    data["values"][1, 0] = 1e300
    with np.errstate(over="ignore"), pytest.raises(ValueError, match="overflow"):
        m.join_episodes(data, [60])


def test_prefix_bit_identity_includes_nan_payload_and_signed_zero():
    original = np.zeros((2, 1954), np.float32)
    original.view(np.uint32)[0, 3] = 0x7FC00011
    original.view(np.uint32)[1, 4] = 0x80000000
    augmented = np.concatenate([original, np.ones((2, 70), np.float32)], axis=1)
    assert m.prefix_identical(augmented, original)
    augmented.view(np.uint32)[0, 3] = 0x7FC00012
    assert not m.prefix_identical(augmented, original)


def test_future_episode_perturbation_and_truncation_leave_past_matrix_scores_identical():
    source = episodes()
    state_keys = np.array([60, 61, 60])
    prefix = np.arange(3 * 1954, dtype=np.float32).reshape(3, 1954)
    full = np.concatenate([prefix, m.join_episodes(source, state_keys)], axis=1)
    future = {k: v.copy() for k, v in source.items()}
    future["values"][0] = 999999
    changed = np.concatenate([prefix, m.join_episodes(future, state_keys)], axis=1)
    cut = {k: v[1:] for k, v in source.items()}
    truncated = np.concatenate([prefix, m.join_episodes(cut, state_keys)], axis=1)
    np.testing.assert_array_equal(full.view(np.uint32), changed.view(np.uint32))
    np.testing.assert_array_equal(full.view(np.uint32), truncated.view(np.uint32))
    fixed_weights = np.linspace(-0.1, 0.1, 2024)
    np.testing.assert_array_equal(full @ fixed_weights, truncated @ fixed_weights)


def summaries(scores, viable):
    ids = [m.base.policy_id(model, t) for model in m.MODELS for t in m.THRESHOLDS]
    return {
        key: {
            "tickers": {ticker: {"base_net_usd": scores[i]} for ticker in m.TICKERS},
            "daily_compliance": {"viable": viable[i]},
        }
        for i, key in enumerate(ids)
    }


def test_daily_selection_rejects_profitable_infeasible_and_ties_control_lower_threshold():
    data = summaries(
        [100, -3, -3, -3, 200, 300], [False, True, True, True, False, False]
    )
    result = m.choices_and_selection(data, {t: 1 for t in m.TICKERS})
    assert result["selected_policy"]["policy"] == "gbt_net__5"
    assert result["diagnostic_policy"]["policy"] == "gbt_net_episode__10"


def test_no_daily_viable_policy_keeps_selection_null_and_diagnostic_frozen():
    result = m.choices_and_selection(
        summaries([0] * 6, [False] * 6), {t: 1 for t in m.TICKERS}
    )
    assert result["selection_status"] == "FAIL_NO_DAILY_COMPLIANT_POLICY"
    assert result["selected_policy"] is None and not result["approved"]
    assert result["diagnostic_policy"]["policy"] == "gbt_net__0"
    assert all(c["policy"] != "CASH" for c in result["choices"])


def test_compliance_distinguishes_zero_fill_and_unknown_source():
    calendar = ["20260102"]
    available = {("SPXW", "20260102"), ("SPY", "20260102")}
    ledger = pd.DataFrame({"date": ["20260102"], "ticker": ["SPXW"]})
    table, report = m.compliance(ledger, calendar, available)
    assert report["days_without_fill"] == 1 and report["no_evaluable_ticker_days"] == 1
    assert not report["minimum_daily_pass"] and not report["coverage_pass"]
    assert table.loc[table.ticker == "QQQ", "meets_minimum"].iloc[0] is None
    with pytest.raises(ValueError, match="NO_EVALUABLE"):
        m.compliance(
            pd.DataFrame({"date": ["20260102"], "ticker": ["QQQ"]}), calendar, available
        )


def test_free_timing_never_forces_early_negative_score_or_replaces_no_fill():
    actions = pd.DataFrame({"action_id": [0, 1, 2, 3], "state_i": [60, 61, 61, 62]})
    labels = pd.DataFrame(
        {
            "action_id": [0, 1, 2, 3],
            "status": ["FILLED", "NO_FILL", "FILLED", "FILLED"],
            "exit_i": [62, 62, 63, 64],
            "net_base": [999, 0, 999, -3],
            "net_adverse": [997, 0, 997, -5],
        }
    )
    engine = SimpleNamespace(
        FIRST_STATE=60,
        ledger_summary=lambda _: {},
        PolicyResult=lambda attempted, ledger, summary: SimpleNamespace(
            attempts=attempted, ledger=ledger, summary=summary
        ),
    )
    result = m.episode_policy.evaluate(actions, labels, [-1, 2, 1, 1], 0, engine)
    assert result.attempts.action_id.tolist() == [1, 3]
    assert result.ledger.action_id.tolist() == [3]
    assert (
        len(m.episode_policy.evaluate(actions, labels, [-1] * 4, 0, engine).ledger) == 0
    )


def test_stage_resume_checks_identity_sources_and_artifacts(tmp_path):
    source, artifact = tmp_path / "source", tmp_path / "model"
    source.write_text("source")
    artifact.write_text("complete model")
    stages = m.Stages(tmp_path, "identity")
    stages.publish("model", [artifact], {str(source): m.sha(source)})
    assert stages.load("model") is not None
    with pytest.raises(ValueError, match="identity"):
        m.Stages(tmp_path, "other").load("model")
    source.write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        stages.load("model")
    source.write_text("source")
    artifact.write_text("truncated")
    with pytest.raises(ValueError, match="changed"):
        stages.load("model")


def test_model_resume_never_refits_completed_model(tmp_path, monkeypatch):
    model = tmp_path / "gbt_net_episode.txt"
    model.write_text("synthetic complete")
    stages = m.Stages(tmp_path, "identity")
    stages.publish("model", [model], {})

    def forbidden(**_kwargs):
        raise AssertionError("Completed model was refitted")

    monkeypatch.setattr(m.lgb, "LGBMRegressor", forbidden)
    monkeypatch.setattr(m.lgb, "Booster", lambda **_kwargs: "reloaded")
    assert m.fit_variant(None, None, None, None, tmp_path, stages) == "reloaded"


def test_freeze_absent_after_test_started_fails_closed(tmp_path):
    m.require_test_freeze(tmp_path, None)
    (tmp_path / "test").mkdir()
    with pytest.raises(ValueError, match="freeze"):
        m.require_test_freeze(tmp_path, None)


def test_atomic_interruption_preserves_prior_output_and_temporary(tmp_path):
    target = tmp_path / "model"
    target.write_bytes(b"prior complete")

    def broken(path):
        path.write_bytes(b"partial")
        raise OSError("interruption")

    with pytest.raises(OSError):
        m.atomic(target, broken)
    assert target.read_bytes() == b"prior complete"
    assert len(list(tmp_path.glob("model.partial-*"))) == 1


def test_stage_corrupt_marker_is_not_silently_rebuilt(tmp_path):
    (tmp_path / "model.complete.json").write_text('{"identity_sha256":')
    with pytest.raises(json.JSONDecodeError):
        m.Stages(tmp_path, "id").load("model")


def test_diagnostic_cannot_pass_even_with_positive_test_economics():
    selection = m.choices_and_selection(
        summaries([10] * 6, [False] * 6), {t: 1 for t in m.TICKERS}
    )
    assert not m.combined_gate(selection, {"passes": True}, {"viable": True})


def test_scheduler_exact_original_tie_strict_threshold_and_no_fill():
    actions = pd.DataFrame(
        {"action_id": [0, 2, 1, 3, 4, 5], "state_i": [60, 61, 61, 62, 63, 65]}
    )
    labels = pd.DataFrame(
        {
            "action_id": [0, 2, 1, 3, 4, 5],
            "status": ["FILLED", "FILLED", "NO_FILL", "FILLED", "FILLED", "FILLED"],
            "exit_i": [62, 63, 62, 64, 65, 67],
            "net_base": [10, 20, 0, -3, 100, 100],
            "net_adverse": [8, 18, 0, -5, 98, 98],
        }
    )
    engine = SimpleNamespace(
        FIRST_STATE=60,
        ledger_summary=lambda _: {},
        PolicyResult=lambda attempted, ledger, summary: SimpleNamespace(
            attempts=attempted, ledger=ledger, summary=summary
        ),
    )
    scores = np.array([5, 6, 6, 7, 100, 5.0])
    actual = m.episode_policy.evaluate(actions, labels, scores, 5, engine)
    expected = m.episode_policy.PolicyView(actions, labels).evaluate(scores, 5, engine)
    pd.testing.assert_frame_equal(actual.attempts, expected.attempts)
    pd.testing.assert_frame_equal(actual.ledger, expected.ledger)
    assert actual.attempts.action_id.tolist() == [1, 3]
