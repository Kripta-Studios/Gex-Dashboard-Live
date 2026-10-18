"""Pure synthetic prequential calibration fixtures; no real forecasts or fitting."""

import copy
import json

import pytest

import oof_maximum_calibration as core

HASH = "a" * 64
SCALES = dict(SPXW=680.0, SPY=81.0, QQQ=88.0)


def selection(
    ticker="SPY",
    day="20250102",
    procedure="expanding",
    actions=None,
    fit_stop_at="2025-01-01T00:00:00-05:00",
):
    return core.maximum_selection(
        procedure=procedure,
        ticker=ticker,
        day=day,
        close_i=390,
        fit_stop_at=fit_stop_at,
        model_sha256=HASH,
        prediction_sha256="b" * 64,
        actions=actions
        if actions is not None
        else [dict(action_id=1, state_i=60, score_usd=2.0)],
    )


def realized(tmp_path, ticker="SPY", day="20250102", residuals=(1.0,), available=None):
    actions = [
        dict(action_id=i + 1, state_i=60 + i, score_usd=2.0)
        for i in range(len(residuals))
    ]
    chosen = selection(ticker, day, actions=actions)
    path = tmp_path / (ticker + day + ".json")
    digest = core.publish(path, chosen)
    labels = [
        dict(action_id=i + 1, status="FILLED", net_base=2 + residual)
        for i, residual in enumerate(residuals)
    ]
    return core.realized_maxima(
        path,
        digest,
        lambda: labels,
        labels_sha256="c" * 64,
        outcome_available_at=available
        or f"{day[:4]}-{day[4:6]}-{day[6:]}T16:01:00-05:00",
        availability_semantics="SYNTHETIC_EOD_PLUS_ONE_MINUTE_NOT_RECEIPT",
    )


def records(tmp_path):
    return [realized(tmp_path, ticker) for ticker in core.TICKERS]


def estimate(days, **kwargs):
    return core.estimate_offsets(
        days,
        procedure="expanding",
        target_month="202601",
        common_scales=SCALES,
        scales_train_stop_at="2025-01-01T00:00:00-05:00",
        **kwargs,
    )


def test_selection_is_outcome_free_includes_negative_maxima_and_ties():
    result = selection(
        actions=[
            dict(action_id=9, state_i=60, score_usd=-2.0),
            dict(action_id=4, state_i=60, score_usd=-2.0),
            dict(action_id=5, state_i=61, score_usd=0.0),
        ]
    )
    assert [row["action_id"] for row in result["selected"]] == [4, 5]
    assert result["selected"][0]["score_usd"] == -2
    assert result["selected"][0]["offered_actions"] == 2
    with pytest.raises(ValueError, match="causal offered"):
        selection(actions=[dict(action_id=1, state_i=60, score_usd=2, net_base=99)])


@pytest.mark.parametrize(
    "cutoff",
    ["2025-01-02T00:00:00-05:00", "2026-01-01T00:00:00-05:00", "2025-01-01T00:00:00"],
)
def test_reject_insample_future_and_timezone_ambiguous_base_prediction(cutoff):
    with pytest.raises(ValueError):
        selection(fit_stop_at=cutoff)


def test_offsets_equal_days_then_states_not_rows(tmp_path):
    days = [
        realized(tmp_path, "SPY", "20250102", (1, 3, 5)),
        realized(tmp_path, "SPY", "20250103", (9,)),
        realized(tmp_path, "SPXW"),
        realized(tmp_path, "QQQ"),
    ]
    result = estimate(days)
    assert result["offsets_usd"]["SPY"] == 6
    assert result["offsets_usd"]["SPXW"] == result["offsets_usd"]["QQQ"] == 1
    assert result["diagnostics"]["SPY"]["selected_states"] == 4
    assert result["year2025_role"] == "CALIBRATOR_TRAIN_NOT_VALIDATION"
    assert result["winner_selected"] is None


def test_no_fill_zero_preserved_no_rescue(tmp_path):
    chosen = selection(
        actions=[
            dict(action_id=1, state_i=60, score_usd=10.0),
            dict(action_id=2, state_i=60, score_usd=9.0),
        ]
    )
    path = tmp_path / "chosen.json"
    digest = core.publish(path, chosen)

    def loader():
        assert path.exists() and core.file_sha(path) == digest
        return [
            dict(action_id=1, status="NO_FILL", net_base=0.0),
            dict(action_id=2, status="FILLED", net_base=1000.0),
        ]

    result = core.realized_maxima(
        path,
        digest,
        loader,
        labels_sha256=HASH,
        outcome_available_at="2025-01-02T16:01:00-05:00",
        availability_semantics="synthetic",
    )
    assert result["rows"][0]["action_id"] == 1 and result["rows"][0]["net_base"] == 0
    with pytest.raises(ValueError, match="zero net"):
        core.realized_maxima(
            path,
            digest,
            lambda: [dict(action_id=1, status="NO_FILL", net_base=1.0)],
            labels_sha256=HASH,
            outcome_available_at="2025-01-02T16:01:00-05:00",
            availability_semantics="synthetic",
        )


def test_same_future_month_availability_boundary_and_mixed_procedures_fail(tmp_path):
    days = records(tmp_path)
    for available in ("2026-01-01T05:00:00+00:00", "2026-02-01T00:00:00-05:00"):
        changed = copy.deepcopy(days)
        changed[0]["outcome_available_at"] = available
        with pytest.raises(ValueError, match="strictly before"):
            estimate(changed)
    changed = copy.deepcopy(days)
    changed[0]["selection"]["day"] = "20260102"
    changed[0]["selection_sha256"] = core.content_sha(changed[0]["selection"])
    with pytest.raises(ValueError, match="Same/future-month"):
        estimate(changed)
    changed = copy.deepcopy(days)
    changed[0]["selection"]["procedure"] = "rolling12"
    changed[0]["selection_sha256"] = core.content_sha(changed[0]["selection"])
    with pytest.raises(ValueError, match="Mixed"):
        estimate(changed)


def test_duplicate_or_changed_selection_and_future_scale_fail(tmp_path):
    days = records(tmp_path)
    with pytest.raises(ValueError, match="Duplicate calibration"):
        estimate([*days, days[0]])
    changed = copy.deepcopy(days)
    changed[0]["rows"][0]["action_id"] = 999
    with pytest.raises(ValueError, match="changed after labels"):
        estimate(changed)
    changed = copy.deepcopy(days)
    changed[0]["selection"]["selected"][0]["score_usd"] = 500
    with pytest.raises(ValueError, match="Unsealed"):
        estimate(changed)
    with pytest.raises(ValueError, match="precede2025"):
        core.estimate_offsets(
            days,
            procedure="expanding",
            target_month="202601",
            common_scales=SCALES,
            scales_train_stop_at="2025-02-01T00:00:00-05:00",
        )


def test_apply_freezes_before_test_labels_no_ranking_or_h_requirement(tmp_path):
    calibration = estimate(records(tmp_path))
    path = tmp_path / "calibration.json"
    digest = core.publish(path, calibration)
    chosen = selection(
        day="20260102",
        actions=[
            dict(action_id=1, state_i=60, score_usd=-0.5),
            dict(action_id=2, state_i=60, score_usd=-0.6),
        ],
    )
    selected_path = tmp_path / "next_month_selection.json"
    selected_sha = core.publish(selected_path, chosen)
    score_path = tmp_path / "corrected_scores.json"
    score_sha = core.apply_offsets_and_seal(
        score_path,
        calibration_path=path,
        calibration_sha256=digest,
        selection_path=selected_path,
        selection_sha256=selected_sha,
    )
    saved = json.loads(score_path.read_text())
    assert saved["rows"][0]["action_id"] == 1
    assert saved["rows"][0]["corrected_score_usd"] == 0.5
    assert not calibration["depends_on_has_filled"] and not saved["ranking_changed"]

    def labels():
        assert path.exists() and score_path.exists()
        return "future labels read after both seals"

    assert core.labels_after_score_seal(score_path, score_sha, labels).startswith(
        "future labels"
    )
    with pytest.raises(ValueError, match="overwrite"):
        core.publish(score_path, saved)
    score_path.write_text("changed")
    with pytest.raises(ValueError, match="hash differs"):
        core.labels_after_score_seal(
            score_path, score_sha, lambda: pytest.fail("must not read labels")
        )


def test_empty_offer_day_counted_not_fabricated(tmp_path):
    days = records(tmp_path)
    days.append(realized(tmp_path, "SPY", "20250103", ()))
    result = estimate(days)
    assert result["diagnostics"]["SPY"]["days_without_offers"] == 1
    assert result["offsets_usd"]["SPY"] == 1


def test_availability_after_physical_close_and_dst(tmp_path):
    chosen = selection(day="20250703")
    chosen["close_i"] = 210
    path = tmp_path / "short.json"
    digest = core.publish(path, chosen)
    assert core.session_close(chosen).isoformat() == "2025-07-03T13:00:00-04:00"
    for available in ("2025-07-03T12:00:00-04:00", "2025-07-03T17:00:00+00:00"):
        with pytest.raises(ValueError, match="strictly after"):
            core.realized_maxima(
                path,
                digest,
                lambda: pytest.fail("no early label read"),
                labels_sha256=HASH,
                outcome_available_at=available,
                availability_semantics="DECLARED_EOD_NOT_OBSERVED_RECEIPT",
            )
    result = core.realized_maxima(
        path,
        digest,
        lambda: [dict(action_id=1, status="NO_FILL", net_base=0)],
        labels_sha256=HASH,
        outcome_available_at="2025-07-03T17:01:00+00:00",
        availability_semantics="DECLARED_EOD_NOT_OBSERVED_RECEIPT",
    )
    assert result["rows"][0]["net_base"] == 0
    days = records(tmp_path)
    days[0]["outcome_available_at"] = "2025-01-02T10:00:00-05:00"
    with pytest.raises(ValueError, match="strictly after"):
        estimate(days)


def test_mutation_during_label_read_is_detected(tmp_path):
    path = tmp_path / "selection.json"
    digest = core.publish(path, selection())

    def mutate_selection():
        path.write_text("replaced", encoding="utf-8")
        return [dict(action_id=1, status="NO_FILL", net_base=0)]

    with pytest.raises(ValueError, match="hash differs"):
        core.realized_maxima(
            path,
            digest,
            mutate_selection,
            labels_sha256=HASH,
            outcome_available_at="2025-01-02T16:01:00-05:00",
            availability_semantics="synthetic",
        )
    score_path = tmp_path / "scores.json"
    score_sha = core.publish(
        score_path, dict(version=core.VERSION, outcomes_read=False)
    )

    def mutate_score():
        score_path.write_text("replaced", encoding="utf-8")

    with pytest.raises(ValueError, match="hash differs"):
        core.labels_after_score_seal(score_path, score_sha, mutate_score)
