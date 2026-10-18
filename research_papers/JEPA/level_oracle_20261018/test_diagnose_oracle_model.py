import numpy as np
import pandas as pd
import pytest
import json

import diagnose_oracle_model as diagnostic


def fixture():
    actions = pd.DataFrame(
        [
            dict(
                action_id=i,
                state_i=minute,
                right=0,
                strike=100.0,
                selected_delta=0.5,
                delta_bucket=0.5,
                target_center=101.0,
                stop_center=99.0,
                band=0.05,
                target_source_mask=1,
                stop_source_mask=1,
            )
            for i, minute in enumerate((60, 60, 61, 62))
        ]
    )
    labels = pd.DataFrame(
        [
            dict(
                action_id=i,
                status=status,
                exit_i=exit_i,
                net_base=reward,
                hold_minutes=exit_i - minute,
            )
            for i, minute, status, exit_i, reward in (
                (0, 60, "FILLED", 63, 1.0),
                (1, 60, "FILLED", 61, -0.5),
                (2, 61, "NO_FILL", 62, 0.0),
                (3, 62, "FILLED", 63, 3.0),
            )
        ]
    )
    advantages = pd.DataFrame(
        dict(
            action_id=range(4),
            q_value=[1.0, 2.5, 3.0, 3.0],
            wait_value=[3.0, 3.0, 3.0, 0.0],
            dp_advantage=[-2.0, -0.5, 0.0, 3.0],
            state_optimal_action=[False, False, False, True],
            teacher_selected=[False, False, False, True],
        )
    )
    states = pd.DataFrame(dict(state_i=range(60, 376), spot=100.0, ib_range=1.0))
    return actions, labels, advantages, states


def test_reachable_cohorts_regret_decomposition_and_blocking():
    a, labels, adv, states = fixture()
    rows, timing = diagnostic.describe_day(
        a, labels, adv, states, np.array([4.0, 3.0, 5.0, 1.0])
    )
    at60 = rows.set_index("state_i").loc[60]
    assert at60.category == "MODEL_TRADE_ORACLE_WAIT"
    assert at60.regret == 2 and at60.immediate_gap == -1 and at60.continuation_gap == 3
    at62 = rows.set_index("state_i").loc[62]
    assert not at62.model_free and at62.oracle_free and at62.blocked_oracle_trade
    assert at62.blocking_action_id == 0
    exact = timing.loc[(timing.state_i == 60) & (timing.shift_minutes == 2)].iloc[0]
    assert exact.status == "EXACT_CONTRACT_AND_LEVELS" and exact.net_difference == 2
    assert rows.loc[rows.model_free & rows.model_filled, "model_net"].sum() == 1
    assert rows.loc[rows.oracle_free & rows.oracle_filled, "oracle_net"].sum() == 3
    assert rows.loc[rows.model_free, "regret"].sum() == 2


def test_no_fill_advances_one_minute_and_wait_wins_zero():
    a, labels, adv, states = fixture()
    rows, _ = diagnostic.describe_day(
        a, labels, adv, states, np.array([0.0, -1.0, 2.0, 3.0])
    )
    index = rows.set_index("state_i")
    assert index.loc[60, "model_action_id"] == -1
    assert index.loc[61, "model_action_id"] == 2 and not index.loc[61, "model_filled"]
    assert index.loc[62, "model_free"] and index.loc[62, "model_action_id"] == 3
    assert not index.loc[63, "model_free"] and index.loc[64, "model_free"]


def test_score_tie_is_action_id_not_input_row_order():
    a, labels, adv, _ = fixture()
    a = a.iloc[[1, 0, 2, 3]]
    _, _, choices, _, _ = diagnostic.prepare(
        a, labels, adv, np.array([4.0, 4.0, -1.0, 1.0])
    )
    assert choices[60] == 0


def test_exact_timing_matching_does_not_invent_shifted_level():
    a, labels, adv, states = fixture()
    a.loc[a.action_id == 3, "target_center"] = 101.001
    _, timing = diagnostic.describe_day(
        a, labels, adv, states, np.array([4.0, 3.0, -1.0, 1.0])
    )
    row = timing.loc[(timing.state_i == 60) & (timing.shift_minutes == 2)].iloc[0]
    assert row.status == "NO_IDENTICAL_LEVELS" and row.matched_action_id == -1
    assert timing.loc[timing.shift_minutes < 0, "status"].eq("NO_CANDIDATE_STATE").all()


def test_q_corruption_and_nonfinite_scores_rejected():
    a, labels, adv, _ = fixture()
    bad = adv.copy()
    bad.loc[0, "q_value"] = 2.0
    with pytest.raises(ValueError, match="decomposition"):
        diagnostic.prepare(a, labels, bad, np.ones(4))
    with pytest.raises(ValueError, match="finiteness"):
        diagnostic.prepare(a, labels, adv, np.array([np.nan, 1, 1, 1]))


def test_training_selection_is_exact_and_outcome_independent():
    index = pd.DataFrame(
        [
            dict(
                ticker=t,
                date=f"{year}{month:02d}{day:02d}",
                split="train",
                status="COMPLETE",
                net_base=day,
            )
            for t in ("SPXW", "SPY", "QQQ")
            for year in (2023, 2024)
            for month in (1, 4, 7, 10)
            for day in range(2, 10)
        ]
    )
    selected = diagnostic.select_training_days(index)
    changed = index.sample(frac=1, random_state=9).assign(net_base=-999)
    other = diagnostic.select_training_days(changed)
    assert len(selected) == 96
    assert selected.groupby(["ticker", "quarter"]).size().eq(4).all()
    assert selected[["ticker", "date", "selection_hash"]].equals(
        other[["ticker", "date", "selection_hash"]]
    )


def test_day_without_actions_preserves_wait_states():
    actions, labels, advantages, states = fixture()
    rows, timing = diagnostic.describe_day(
        actions.iloc[:0], labels.iloc[:0], advantages.iloc[:0], states, np.array([])
    )
    assert len(rows) == 316 and rows.model_free.all() and rows.oracle_free.all()
    assert rows.category.eq("BOTH_WAIT").all() and rows.regret.eq(0).all()
    assert not rows.has_actions.any() and timing.empty


def test_checkpoint_integrity_identity_and_incomplete_fail_closed(tmp_path):
    artifact = tmp_path / "states.parquet"
    artifact.write_bytes(b"synthetic completed states")
    source = tmp_path / "source"
    source.write_bytes(b"immutable source")
    marker = tmp_path / "day.complete.json"
    assert diagnostic.load_checkpoint(marker, "id", "SPY/20230103") is None
    record = dict(
        identity="id",
        day_key="SPY/20230103",
        artifacts={str(artifact): diagnostic.sha(artifact)},
        sources={str(source): diagnostic.sha(source)},
    )
    marker.write_text(json.dumps(record), encoding="utf-8")
    assert diagnostic.load_checkpoint(marker, "id", "SPY/20230103") == record
    with pytest.raises(ValueError, match="identity"):
        diagnostic.load_checkpoint(marker, "wrong", "SPY/20230103")
    artifact.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="content"):
        diagnostic.load_checkpoint(marker, "id", "SPY/20230103")
    marker.write_text('{"identity":', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        diagnostic.load_checkpoint(marker, "id", "SPY/20230103")
