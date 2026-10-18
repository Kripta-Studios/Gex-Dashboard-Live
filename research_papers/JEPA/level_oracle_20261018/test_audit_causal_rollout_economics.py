"""Independent synthetic fixtures; no market reads and no producer imports."""

import hashlib
import inspect
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import audit_causal_rollout_economics as a


def market():
    actions = pd.DataFrame(
        dict(action_id=[8, 2, 10, 20, 21, 30], state_i=[60, 60, 61, 64, 64, 70])
    )
    labels = pd.DataFrame(
        dict(
            action_id=[8, 2, 10, 20, 21, 30],
            status=["FILLED", "NO_FILL", "FILLED", "FILLED", "FILLED", "FILLED"],
            exit_i=[62, 61, 63, 66, 66, 385],
            net_base=[100.0, 0.0, -3.0, 90.0, 0.0, 5.0],
            net_adverse=[98.0, 0.0, -5.0, 88.0, -2.0, 3.0],
            reason=["TARGET", "NO_FILL", "STOP", "TARGET", "EOD", "EOD"],
            hold_minutes=[1, 0, 1, 1, 1, 314],
        )
    )
    scores = np.array(
        [
            [10.0, 10.0],
            [10.0, 10.0],
            [9.0, 9.0],
            [15.0, -5.0],
            [-1.0, 8.0],
            [10.0, 10.0],
        ]
    )
    return actions, labels, scores


def test_schedule_tie_no_fill_no_rescue_loss_switches_flag_and_strict_threshold():
    actions, labels, scores = market()
    attempted, trades = a.schedule(actions, labels, scores, 0)
    assert attempted.action_id.tolist() == [2, 10, 21, 30]
    assert attempted.has_filled_before.tolist() == [0, 0, 1, 1]
    assert trades.action_id.tolist() == [10, 21, 30]
    assert attempted.score.tolist() == [10.0, 9.0, 8.0, 10.0]
    assert trades.net_base.sum() == 2
    high, _ = a.schedule(actions, labels, scores, 10)
    assert high.action_id.tolist() == [20]  # exactly ten is rejected


def test_scheduler_label_row_order_invariance_and_no_outcome_ranking():
    actions, labels, scores = market()
    chosen = a.ranked_choices(actions, scores)
    changed = labels.copy()
    changed.loc[changed.status == "FILLED", "net_base"] *= -100
    np.testing.assert_array_equal(a.ranked_choices(actions, scores), chosen)
    first, _ = a.schedule(actions, labels, scores, 0)
    second, _ = a.schedule(actions, changed.iloc[::-1], scores, 0)
    assert first.action_id.tolist() == second.action_id.tolist()
    assert "labels" not in inspect.signature(a.ranked_choices).parameters


def test_economics_no_terminal_penalty_and_zero_fill_is_real_trade():
    actions, labels, scores = market()
    _, trades = a.schedule(actions, labels, scores, 0)
    metrics = a.economics(trades)
    assert metrics["trades"] == 3 and metrics["net_base"] == 2
    assert metrics["net_adverse"] == -4
    assert metrics["net_base_pf"] == pytest.approx(5 / 3)
    assert metrics["net_base_win_rate"] == pytest.approx(1 / 3)
    assert metrics["net_base_max_drawdown"] == 3
    assert metrics["net_adverse_max_drawdown"] == 7
    assert metrics["exit_reasons"]["EOD"]["trades"] == 2
    empty = a.economics(trades.iloc[:0])
    assert empty["net_base"] == 0 and empty["net_base_pf"] is None
    assert empty["net_base_pf_infinite"] is False


def test_fixed_policy_rollout_matches_explicit_forward_simulation_all_states():
    actions, labels, scores = market()
    choices = a.ranked_choices(actions, scores)
    values, residual = a.policy_returns(actions, labels, choices, 17.0)
    lookup = labels.set_index("action_id")
    for start in range(60, 377):
        for h in (0, 1):
            minute, flag, total = start, h, 0.0
            while minute <= 375:
                identity = choices[minute - 60, flag]
                if identity == -1 or lookup.loc[identity, "status"] == "NO_FILL":
                    minute += 1
                else:
                    total += lookup.loc[identity, "net_base"]
                    flag = 1
                    minute = int(lookup.loc[identity, "exit_i"]) + 1
            total -= 17 if flag == 0 else 0
            assert values[start - 60, h] == total
    np.testing.assert_array_equal(residual[1], [0, 0])
    # Last decision's immediate trade gains the unfilled-day penalty relative to waiting.
    lateactions = pd.DataFrame(dict(action_id=[0], state_i=[375]))
    latelabels = pd.DataFrame(
        dict(action_id=[0], status=["FILLED"], exit_i=[385], net_base=[-2.0])
    )
    wait = np.full((316, 2), -1, dtype=np.int64)
    latevalues, latetargets = a.policy_returns(lateactions, latelabels, wait, 10.0)
    np.testing.assert_array_equal(latevalues[-1], [-10, 0])
    np.testing.assert_array_equal(latetargets, [[8, -2]])


def summaries():
    return {
        key: dict(
            zero_fill_expected_days=1, tickers={t: {"net_base": 1e8} for t in a.TICKERS}
        )
        for key in a.POLICIES
    }


def test_null_selection_no_least_bad_rescue_and_tie_order():
    stats = summaries()
    scales = {t: 100.0 for t in a.TICKERS}
    selected = a.selection(stats, scales)
    assert selected["selected_policy"] is None
    assert selected["frozen_candidates"] == list(a.POLICIES)
    assert selected["status"] == "FAILED_DAILY_REQUIREMENT_VALIDATION"
    for key in a.POLICIES:
        stats[key]["zero_fill_expected_days"] = 0
        for ticker in a.TICKERS:
            stats[key]["tickers"][ticker]["net_base"] = -10.0
    selected = a.selection(stats, scales)
    assert selected["selected_policy"]["policy"] == "net_control__0"
    assert selected["selected_policy"]["score"] == pytest.approx(-0.3)


def test_missing_calendar_retained_separate_from_observed_zero():
    actions, labels, scores = market()
    attempts, ledger = a.schedule(actions, labels, scores, 0)
    attempts["ticker"], attempts["date"], attempts["policy"] = (
        "SPY",
        "20260401",
        "net_control__0",
    )
    ledger["ticker"], ledger["date"], ledger["policy"] = (
        "SPY",
        "20260401",
        "net_control__0",
    )
    expected = [("SPY", "20260401"), ("SPY", "20260402"), ("QQQ", "20260401")]
    stats, calendar = a.summarize_period(attempts, ledger, expected, set(expected[:2]))
    row = stats["net_control__0"]
    assert row["expected_ticker_days"] == 3 and row["observable_ticker_days"] == 2
    assert row["zero_fill_expected_days"] == 2 and row["zero_fill_observable_days"] == 1
    assert row["missing_source_days"] == 1
    missing = calendar.loc[
        (calendar.policy == "net_control__0") & ~calendar.source_available
    ]
    assert len(missing) == 1 and missing.ticker.iloc[0] == "QQQ"


@pytest.mark.parametrize(
    "kind", ["duplicate", "missing", "badexit", "nofillreward", "nan", "shape"]
)
def test_invalid_inputs_fail_closed(kind):
    actions, labels, scores = market()
    if kind == "duplicate":
        actions.loc[1, "action_id"] = 8
    elif kind == "missing":
        labels.loc[0, "action_id"] = 1000
    elif kind == "badexit":
        labels.loc[0, "exit_i"] = 61
    elif kind == "nofillreward":
        labels.loc[1, "net_base"] = 1
    elif kind == "nan":
        scores[0, 0] = np.nan
    else:
        scores = scores[:, 0]
    with pytest.raises(AssertionError):
        a.schedule(actions, labels, scores, 0)


def test_independent_sampling_bands_weights_and_exact_serialization():
    actions = pd.DataFrame(
        dict(action_id=np.arange(45), state_i=np.r_[np.full(40, 60), np.full(5, 297)])
    )
    rows, pop, selected = a.canonical_subset("SPY", "20230103", actions)
    np.testing.assert_array_equal(pop, [40, 0, 0, 5])
    np.testing.assert_array_equal(selected, [32, 0, 0, 5])
    assert len(rows) == 37 and sum(r[4] for r in rows) == pytest.approx(1)
    expected = sorted(
        (hashlib.sha256(f'[20261018,"SPY","20230103",60,{i}]'.encode()).hexdigest(), i)
        for i in range(40)
    )[:32]
    assert [(r[3], r[0]) for r in rows[:32]] == expected
    shuffled, _, _ = a.canonical_subset("SPY", "20230103", actions.iloc[::-1])
    assert rows == shuffled


def test_artifact_hash_binding_tamper_and_chronology(tmp_path):
    (tmp_path / "run_contract.json").write_text("{}")
    evidence = a.Evidence(tmp_path)
    assert str(tmp_path / "run_contract.json") in evidence.verified
    target = tmp_path / "day.npz"
    np.savez(target, x=np.array([1.0, 2.0]))
    marker = dict(
        status="COMPLETE",
        binding=evidence.binding,
        files={"day.npz": a.sha(target)},
        completed_utc="2026-10-18T18:00:00+00:00",
    )
    (tmp_path / "day.complete.json").write_text(json.dumps(marker))
    pack, found = evidence.npz("day")
    np.testing.assert_array_equal(pack["x"], [1, 2])
    a.before(found, dict(completed_utc="2026-10-18T18:01:00+00:00"), "freeze")
    with pytest.raises(AssertionError, match="Checkpoint order"):
        a.before(found, dict(completed_utc="2026-10-18T17:59:00+00:00"), "freeze")
    with target.open("ab") as handle:
        handle.write(b"tamper")
    with pytest.raises(AssertionError, match="Hash mismatch"):
        evidence.npz("day")


@pytest.mark.parametrize(
    "name",
    [
        "risk_scales",
        "models/teacher",
        "matrices/final",
        "validation/summary",
        "validation/daily/SPY/20250102",
    ],
)
def test_complete_marker_cannot_omit_consumed_file(tmp_path, name):
    (tmp_path / "run_contract.json").write_text("{}")
    evidence = a.Evidence(tmp_path)
    unrelated = tmp_path / "unrelated.json"
    unrelated.write_text("{}")
    marker = dict(
        status="COMPLETE",
        binding=evidence.binding,
        files={"unrelated.json": a.sha(unrelated)},
        completed_utc="2026-10-18T18:00:00+00:00",
    )
    path = tmp_path / (name + ".complete.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(marker))
    with pytest.raises(AssertionError, match="Consumed artifact absent"):
        evidence.complete(name)


def test_full_ledger_comparison_detects_identity_flag_and_reward_changes():
    actions, labels, scores = market()
    attempts, _ = a.schedule(actions, labels, scores, 0)
    a.frame_equal(attempts, attempts.iloc[::-1], "fixture")
    for col in ("action_id", "has_filled_before", "net_base", "score"):
        changed = attempts.copy()
        changed.loc[0, col] += 1
        with pytest.raises(AssertionError):
            a.frame_equal(attempts, changed, "fixture")


def test_independence_no_producer_imports():
    source = Path(a.__file__).read_text()
    for forbidden in (
        "import train_causal_rollout",
        "import causal_rollout",
        "import rollout_sampling",
        "import train_models",
    ):
        assert forbidden not in source


def training_fixture(tmp_path, monkeypatch):
    """Two miniature training periods, all three tickers, physical matrix hashes."""
    monkeypatch.setattr(a, "TRAIN_LAYOUT", (("teacher", 3, 1954), ("final", 3, 1955)))
    config = {"synthetic_fixture": True}
    scales = {t: 100.0 for t in a.TICKERS}
    root = tmp_path
    (root / "models").mkdir()
    (root / "matrices").mkdir()
    (root / "models/teacher.txt").write_text("synthetic teacher")
    (root / "risk_scales.json").write_text(json.dumps(scales))
    packs = {}

    class Evidence:
        binding = "synthetic-binding"

        def __init__(self):
            self.root = root

        def complete(self, name):
            return dict(completed_utc="2026-10-18T18:00:00+00:00")

        def npz(self, name):
            return packs[name], dict(completed_utc="2026-10-18T18:01:00+00:00")

    evidence = Evidence()
    actions = pd.DataFrame(dict(action_id=[0], state_i=[60]))
    labels = pd.DataFrame(
        dict(
            action_id=[0],
            status=["FILLED"],
            exit_i=[62],
            net_base=[-2.0],
            entry_ask=[1.0],
        )
    )
    monkeypatch.setattr(
        a,
        "read_source",
        lambda evidence, index, pair, name, columns=None: (
            actions.copy() if name == "actions.parquet" else labels.copy()
        ),
    )
    tickers = sorted(a.TICKERS)
    pairs = []
    for role, date, columns, multiplicity in (
        ("teacher", "20230103", 1954, 1),
        ("final", "20240102", 1955, 2),
    ):
        pairs.extend((t, date) for t in tickers)
        n = 3 * multiplicity
        sample = dict(
            ticker=np.repeat(np.array(tickers), multiplicity),
            date=np.full(n, date),
            action_id=np.zeros(n, dtype=np.int64),
            state_i=np.full(n, 60, dtype=np.int64),
            band_i=np.zeros(n, dtype=np.int64),
            weight=np.full(n, 1 / multiplicity),
            fit_weight=np.ones(n),
            n_days=np.array(3),
            normalization_factor=np.array(multiplicity),
            population_ticker=np.array(tickers),
            population_date=np.full(3, date),
            population_by_band=np.tile([1, 0, 0, 0], (3, 1)),
            selected_by_band=np.tile([1, 0, 0, 0], (3, 1)),
            identity_sha256=np.repeat(
                [
                    hashlib.sha256(
                        f'[20261018,"{t}","{date}",60,0]'.encode()
                    ).hexdigest()
                    for t in tickers
                ],
                multiplicity,
            ),
        )
        if role == "final":
            sample["has_filled_today"] = np.tile([0, 1], 3).astype(np.int8)
        packs["samples/" + role] = sample
        matrix = np.ones((n, columns), dtype=np.float32)
        if role == "final":
            matrix[:, -1] = sample["has_filled_today"]
        matrix_path = root / ("matrices/" + role + ".npy")
        np.save(matrix_path, matrix)
        for i, ticker in enumerate(tickers):
            key = ticker + "/" + date
            positions = np.arange(i * multiplicity, (i + 1) * multiplicity)
            chunk = dict(positions=positions, x=matrix[positions].copy())
            if role == "teacher":
                chunk.update(
                    net=np.array([-2.0]),
                    premium=np.array([100.0]),
                    filled=np.array([True]),
                )
            else:
                # Independent expected all-WAIT tail after the state60 losing fill.
                choices = np.full((316, 2), -1, dtype=np.int64)
                choices[0] = 0
                choice = dict(
                    action_id=np.array([0]),
                    state_i=np.array([60]),
                    scores=np.ones((1, 2)),
                    choices=choices,
                    teacher_sha256=np.array(a.sha(root / "models/teacher.txt")),
                    scale_sha256=np.array(a.sha(root / "risk_scales.json")),
                )
                choice_path = root / ("teacher_choices/" + key + ".npz")
                choice_path.parent.mkdir(parents=True, exist_ok=True)
                np.savez(choice_path, **choice)
                packs["teacher_choices/" + key] = choice
                values = np.tile([-100.0, 0.0], (317, 1))
                values[0] = [-2.0, -2.0]
                packs["rollouts/" + key] = dict(
                    positions=positions,
                    values=values,
                    net=np.array([-2.0, -2.0]),
                    residual=np.array([98.0, -2.0]),
                    choice_sha256=np.array(a.sha(choice_path)),
                )
            packs["chunks/" + role + "/" + key] = chunk
        targets = (
            [("teacher", np.full(n, -0.02))]
            if role == "teacher"
            else [
                ("net_control", np.full(n, -0.02)),
                ("causal_residual", np.tile([0.98, -0.02], 3)),
            ]
        )
        for model, target in targets:
            record = dict(
                binding=evidence.binding,
                config=config,
                shape=[n, columns],
                matrix_sha256=a.sha(matrix_path),
                target_sha256=a.array_sha(target),
                weight_sha256=a.array_sha(np.ones(n)),
                started_utc="2026-10-18T17:59:00+00:00",
            )
            (root / ("models/" + model + ".fit_started.json")).write_text(
                json.dumps(record)
            )
    packs["final_targets"] = dict(
        net=np.full(6, -2.0),
        residual=np.tile([98.0, -2.0], 3),
        divisor=np.full(6, 100.0),
        fit_weight=np.ones(6),
    )
    index = pd.DataFrame(
        index=pd.MultiIndex.from_tuples(pairs, names=["ticker", "date"])
    )
    return evidence, index, scales, config, packs


def test_training_targets_matrices_sampling_and_fit_signature_end_to_end(
    tmp_path, monkeypatch
):
    evidence, index, scales, config, packs = training_fixture(tmp_path, monkeypatch)
    result = a.audit_training(evidence, index, scales, config)
    assert result == {
        "teacher": {"days": 3, "rows": 3, "columns": 1954},
        "final": {"days": 3, "rows": 6, "columns": 1955},
    }
    packs["final_targets"]["residual"][0] += 1
    with pytest.raises(AssertionError, match="Final target residual"):
        a.audit_training(evidence, index, scales, config)


def test_training_rejects_changed_causal_feature_chunk(tmp_path, monkeypatch):
    evidence, index, scales, config, packs = training_fixture(tmp_path, monkeypatch)
    packs["chunks/final/QQQ/20240102"]["x"][0, 0] += 1
    with pytest.raises(AssertionError, match="Matrix/chunk bytes"):
        a.audit_training(evidence, index, scales, config)
