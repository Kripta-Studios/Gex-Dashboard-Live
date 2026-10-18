"""Synthetic calendar and inference invariants; no historic sources or fits."""

from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import evaluate_causal_rollout_short_sessions as s


def fixture_frames():
    actions = pd.DataFrame(
        {"action_id": [0, 1, 2, 3, 4], "state_i": [60, 60, 61, 64, 195]}
    )
    labels = pd.DataFrame(
        {
            "action_id": [0, 1, 2, 3, 4],
            "status": ["NO_FILL", "FILLED", "FILLED", "FILLED", "FILLED"],
            "exit_i": [61, 62, 63, 66, 205],
            "net_base": [0.0, 999.0, -2.0, 4.0, 5.0],
            "net_adverse": [0.0, 997.0, -4.0, 2.0, 3.0],
            "reason": ["NO_FILL", "TARGET", "STOP", "TARGET", "EOD"],
            "hold_minutes": [0, 1, 1, 1, 9],
        }
    )
    scores = np.array([[10.0, 0.0], [10.0, 0.0], [3.0, 0.0], [0.0, 2.0], [0.0, 1.0]])
    return actions, labels, scores


def test_short_session_last_entry_h_and_no_same_minute_substitution():
    actions, labels, scores = fixture_frames()
    attempts, ledger = s.evaluate_policy(
        actions, labels, scores, 0, s.SessionClock(210)
    )
    assert list(attempts.action_id) == [0, 2, 3, 4]
    assert list(attempts.has_filled_before) == [0, 0, 1, 1]
    assert list(ledger.action_id) == [2, 3, 4]
    assert ledger.exit_i.max() == 205 and ledger.net_base.sum() == 7


@pytest.mark.parametrize(
    "change", ["late_state", "late_exit", "bad_nonfill", "too_early_exit"]
)
def test_reject_session_clock_violations(change):
    actions, labels, scores = fixture_frames()
    if change == "late_state":
        actions.loc[4, "state_i"] = 196
    elif change == "late_exit":
        labels.loc[4, "exit_i"] = 206
    elif change == "bad_nonfill":
        labels.loc[0, "exit_i"] = 62
    else:
        labels.loc[2, "exit_i"] = 62
    with pytest.raises(ValueError):
        s.evaluate_policy(actions, labels, scores, 0, s.SessionClock(210))


def test_explicit_clock_and_full_session_parity():
    actions, labels, scores = fixture_frames()
    with pytest.raises(ValueError, match="Explicit"):
        s.evaluate_policy(actions, labels, scores, 0, None)
    actual = s.evaluate_policy(actions, labels, scores, 0, s.SessionClock(390))
    expected = s.original.evaluate_flag_policy(actions, labels, scores, 0)
    for a, b in zip(actual, expected):
        pd.testing.assert_frame_equal(a, b)


def test_empty_day_and_wait_tie_are_retained():
    actions, labels, scores = fixture_frames()
    attempted, ledger = s.evaluate_policy(
        actions.iloc[:0], labels.iloc[:0], scores[:0], 0, s.SessionClock(210)
    )
    assert len(attempted) == len(ledger) == 0
    attempted, ledger = s.evaluate_policy(
        actions, labels, np.zeros_like(scores), 0, s.SessionClock(210)
    )
    assert len(attempted) == len(ledger) == 0


def test_fixed_day_population_requires_dates_tickers_and_close():
    days = {
        t + d: SimpleNamespace(
            ticker=t, date=d, close_i=210, status="COMPLETE", key=t + "/" + d
        )
        for t in s.original.TICKERS
        for d in s.DATES
    }
    source = SimpleNamespace(days=days)
    assert len(s.fixed_days(source)) == 9
    next(iter(days.values())).close_i = 390
    with pytest.raises(ValueError, match="Nine"):
        s.fixed_days(source)


def test_prediction_commit_precedes_labels_and_resume_never_rescores(
    tmp_path, monkeypatch
):
    actions, labels, scores = fixture_frames()
    artifacts = s.Artifacts(tmp_path, "synthetic")
    day = SimpleNamespace(
        ticker="SPY", date=s.DATES[0], close_i=210, key="SPY/" + s.DATES[0]
    )
    calls = []

    class Source:
        def read(self, target, name):
            if name == "labels.parquet":
                assert artifacts.complete("predictions/" + day.key)
                calls.append("labels")
                return labels
            return actions

        def check(self, target, name):
            return "unchanged"

    def score(*args, **kwargs):
        calls.append("score")
        return scores

    monkeypatch.setattr(s.original, "score_actions", score)
    store = SimpleNamespace(get=lambda key: None)
    models = {name: object() for name in s.original.MODELS}
    s.evaluate_day(day, Source(), store, models, {"SPY": 1.0}, artifacts)
    assert calls == ["score", "score", "labels"]
    s.evaluate_day(day, Source(), store, models, {"SPY": 1.0}, artifacts)
    assert calls == ["score", "score", "labels"]
    loaded = pd.read_parquet(tmp_path / ("daily/" + day.key + "_ledger.parquet"))
    assert set(loaded.policy).issubset(s.POLICIES)
    assert "causal_residual__0" in set(loaded.policy)


def test_calendar_union_exact_750_and_old_day_consistency():
    actions, labels, scores = fixture_frames()
    attempts, ledger = s.evaluate_policy(
        actions, labels, scores, 0, s.SessionClock(210)
    )
    expected = [(t, f"2025{i:04}") for t in s.original.TICKERS for i in range(250)]
    for frame in (attempts, ledger):
        frame["ticker"], frame["date"], frame["policy"] = (
            expected[0][0],
            expected[0][1],
            s.SELECTED,
        )
    report, calendar = s.summarize(ledger, attempts, expected)
    assert len(calendar) == 750 * 6
    assert report[s.SELECTED]["zero_fill_expected_days"] == 749
    assert report[s.SELECTED]["net_base"] == 7
    assert report[s.SELECTED]["tickers"][expected[0][0]]["net_base"] == 7
    old_keys = set((t, f"2025{i:04}") for t in s.original.TICKERS for i in range(247))
    old = calendar.loc[
        [key in old_keys for key in zip(calendar.ticker, calendar.date)]
    ].copy()
    assert len(old) == 741 * 6
    s.require_same_old_calendar(old, calendar)
    changed = calendar.copy()
    changed.loc[0, "net_base"] += 1
    with pytest.raises(AssertionError):
        s.require_same_old_calendar(old, changed)
    with pytest.raises(ValueError, match="Duplicate"):
        s.summarize(ledger, attempts, expected + [expected[0]])


def make_original(tmp_path, monkeypatch):
    root = tmp_path / "original"
    root.mkdir()
    s.original.atomic_json(root / "run_contract.json", {"synthetic": True})
    monkeypatch.setattr(s, "RUN_SHA", s.sha(root / "run_contract.json"))
    art = s.Artifacts(root, s.RUN_SHA)
    art.json("risk_scales", {"SPY": 1.0})
    for name in ("validation/summary", "test/summary", "test/score_h_diagnostic"):
        art.json(name, {})
    calendar = root / "validation/daily_calendar.parquet"
    calendar.write_bytes(b"synthetic-unused-calendar")
    marker = s.read_json(art.marker("validation/summary"))
    marker["files"][str(calendar.relative_to(root))] = s.sha(calendar)
    art.marker("validation/summary").write_text(__import__("json").dumps(marker))
    model_hashes = {}
    for name in s.original.MODELS:
        path = root / ("models/" + name + ".txt")
        path.parent.mkdir(exist_ok=True)
        path.write_text(name)
        model_hashes[name] = s.sha(path)
        art.finish("models/" + name, [path])
    monkeypatch.setattr(s, "MODEL_SHA", model_hashes)
    art.json(
        "validation_freeze",
        dict(
            selected_policy={"policy": s.SELECTED},
            frozen_candidates=s.POLICIES,
            model_hashes=model_hashes,
            risk_scales_sha256=s.sha(root / "risk_scales.json"),
            validation_summary_sha256=s.sha(root / "validation/summary.json"),
        ),
    )
    monkeypatch.setattr(s, "FREEZE_SHA", s.sha(root / "validation_freeze.json"))
    audit = tmp_path / "audit.json"
    s.original.atomic_json(
        audit,
        dict(
            status="PASS_INDEPENDENT_CAUSAL_ROLLOUT_ECONOMIC_AUDIT_GIVEN_SEALED_SCORES",
            run_contract_sha256=s.RUN_SHA,
            verified_artifacts={
                str(p.resolve()): s.sha(p) for p in root.rglob("*") if p.is_file()
            },
        ),
    )
    return root, audit


@pytest.mark.parametrize(
    "changed", ["models/net_control.txt", "validation_freeze.json", "risk_scales.json"]
)
def test_original_authority_requires_audit_and_rejects_mutation(
    tmp_path, monkeypatch, changed
):
    root, audit = make_original(tmp_path, monkeypatch)
    evidence = s.OriginalEvidence(root, audit)
    evidence.recheck()
    with (root / changed).open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(ValueError):
        s.OriginalEvidence(root, audit)
    with pytest.raises(ValueError):
        evidence.recheck()


def test_checkpoint_preserves_orphan_and_rejects_tampering(tmp_path):
    art = s.Artifacts(tmp_path, "synthetic")
    art.json("done", {"x": 1})
    with pytest.raises(ValueError, match="Changed JSON"):
        art.json("done", {"x": 2})
    (tmp_path / "orphan.json").write_text("preserve")
    with pytest.raises((RuntimeError, FileExistsError)):
        art.json("orphan", {"x": 3})
    assert (tmp_path / "orphan.json").read_text() == "preserve"


@pytest.mark.parametrize(
    "changed", ["prediction", "prediction_marker", "external_source"]
)
def test_global_closure_rehashes_exact_inventory_before_resume(tmp_path, changed):
    output = tmp_path / "output"
    output.mkdir()
    s.original.atomic_json(output / "run_contract.json", {"fixture": "global-close"})
    art = s.Artifacts(output, s.sha(output / "run_contract.json"))
    days = [
        SimpleNamespace(key=t + "/" + d) for t in s.original.TICKERS for d in s.DATES
    ]
    source = tmp_path / "input.txt"
    source.write_text("fixed input")
    art.json(
        "source_hashes",
        {"source": {str(source.resolve()): s.sha(source)}, "original": {}},
    )
    art.json("summary", {"selected_policy": s.SELECTED, "selection_recomputed": False})
    for name in ("short_daily_calendar", "combined_daily_calendar"):
        path = output / (name + ".parquet")
        s.original.save_parquet(path, pd.DataFrame({"synthetic": [1]}))
        art.finish(name, [path])
    for day in days:
        art.save_npz(
            "predictions/" + day.key, {"synthetic_score": np.array([1.0, 2.0])}
        )
        art.json("feature_inputs/" + day.key, {str(source.resolve()): s.sha(source)})
        paths = [
            output / ("daily/" + day.key + suffix)
            for suffix in ("_attempts.parquet", "_ledger.parquet")
        ]
        for path in paths:
            s.original.save_parquet(path, pd.DataFrame({"synthetic": [1]}))
        art.finish("daily/" + day.key, paths)
    assert not s.finalize_or_validate(art, days, publish=False)
    assert s.finalize_or_validate(art, days, publish=True)
    assert s.finalize_or_validate(art, days, publish=False)
    record = s.read_json(output / "completion.complete.json")
    assert len(record["files"]) == 73  # contract + 4*2 global + 9*(2+3+2) + completion.
    path = {
        "prediction": output / ("predictions/" + days[0].key + ".npz"),
        "prediction_marker": art.marker("predictions/" + days[0].key),
        "external_source": source,
    }[changed]
    with path.open("ab") as handle:
        handle.write(b"corrupt after completion")
    with pytest.raises(ValueError):
        s.finalize_or_validate(art, days, publish=False)
