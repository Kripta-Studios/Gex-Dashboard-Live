"""Synthetic identity-only tests; never load market files or outcome arrays."""

from dataclasses import replace
import hashlib
import inspect

import numpy as np
import pytest

import rollout_sampling as sampling


def sample(date="20230103", ticker="SPY"):
    states = np.repeat([60, 139, 218, 297], [80, 7, 0, 45]).astype(np.int64)
    ids = np.arange(len(states), dtype=np.int64)
    return sampling.sample_day(ticker, date, ids, states)


def assert_sample_equal(a, b):
    for key in a.__dataclass_fields__:
        if isinstance(getattr(a, key), np.ndarray):
            np.testing.assert_array_equal(getattr(a, key), getattr(b, key))
        else:
            assert getattr(a, key) == getattr(b, key)


def test_canonical_golden_identity():
    raw = sampling.canonical_identity(20261018, "SPY", "20230103", 60, 7)
    assert raw == b'[20261018,"SPY","20230103",60,7]'
    assert (
        hashlib.sha256(raw).hexdigest()
        == "c994bff6fa2fcd7be4623f131412e90e0aebc53f769ce6616c317d777d61e1cb"
    )


def test_deterministic_order_invariant_lowest_digest_and_inputs_unchanged():
    ids = np.arange(316, dtype=np.int64)
    states = np.arange(60, 376, dtype=np.int64)
    before_ids, before_states = ids.copy(), states.copy()
    a = sampling.sample_day("QQQ", "20230103", ids, states)
    order = np.random.default_rng(1).permutation(len(ids))
    b = sampling.sample_day("QQQ", "20230103", ids[order], states[order])
    assert_sample_equal(a, b)
    assert_sample_equal(a, sampling.sample_day("QQQ", "20230103", ids, states))
    np.testing.assert_array_equal(ids, before_ids)
    np.testing.assert_array_equal(states, before_states)
    for band, (low, high) in enumerate(sampling.BANDS):
        candidates = [
            (
                hashlib.sha256(
                    sampling.canonical_identity(
                        20261018, "QQQ", "20230103", int(s), int(i)
                    )
                ).hexdigest(),
                i,
            )
            for i, s in zip(ids, states)
            if low <= s <= high
        ]
        expected = [i for _, i in sorted(candidates)[:32]]
        np.testing.assert_array_equal(a.action_id[a.band_i == band], expected)


def test_fixed_capacity_empty_bands_no_redistribution_ipw_mass():
    day = sample()
    np.testing.assert_array_equal(day.population_by_band, [80, 7, 0, 45])
    np.testing.assert_array_equal(day.selected_by_band, [32, 7, 0, 32])
    assert len(day.action_id) == 71
    assert day.weight.dtype == np.float64
    np.testing.assert_allclose(
        day.weight.sum(), 1, rtol=0, atol=4 * np.finfo(np.float64).eps
    )
    for b, m in enumerate([80, 7, 0, 45]):
        np.testing.assert_allclose(
            day.weight[day.band_i == b].sum(), m / 132, atol=2e-16
        )
    assert not day.weight.flags.writeable
    assert not day.action_id.flags.writeable


def test_empty_day_retained_as_counts_but_not_silently_dropped_from_fit():
    day = sampling.sample_day(
        "SPY", "20230103", np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    )
    assert len(day.action_id) == 0
    np.testing.assert_array_equal(day.population_by_band, np.zeros(4, dtype=np.int64))
    np.testing.assert_array_equal(day.selected_by_band, np.zeros(4, dtype=np.int64))
    with pytest.raises(ValueError, match="nonempty days"):
        sampling.prepare_fit_rows([day], role="teacher")


def test_teacher_unique_final_paired_weights_and_global_normalization():
    teacher = sampling.prepare_fit_rows(
        [sample(ticker="SPY"), sample(ticker="QQQ")], role="teacher"
    )
    assert teacher.has_filled_today is None
    assert len(teacher.action_id) == 142
    assert teacher.n_days == 2
    assert teacher.ticker[0] == "QQQ"
    np.testing.assert_allclose(teacher.weight.sum(), 2, atol=4e-16)
    np.testing.assert_allclose(teacher.fit_weight.mean(), 1, atol=4e-16)
    a, b = sample("20230703", "SPY"), sample("20240102", "QQQ")
    final = sampling.prepare_fit_rows([a, b], role="final")
    reverse = sampling.prepare_fit_rows([b, a], role="final")
    for name in (
        "ticker",
        "date",
        "action_id",
        "state_i",
        "band_i",
        "identity_sha256",
        "has_filled_today",
        "weight",
        "fit_weight",
    ):
        np.testing.assert_array_equal(getattr(final, name), getattr(reverse, name))
    assert len(final.action_id) == 284
    np.testing.assert_array_equal(final.action_id[::2], final.action_id[1::2])
    np.testing.assert_array_equal(final.has_filled_today[::2], 0)
    np.testing.assert_array_equal(final.has_filled_today[1::2], 1)
    np.testing.assert_array_equal(
        final.weight[::2], np.concatenate([b.weight, a.weight]) / 2
    )
    np.testing.assert_array_equal(final.weight[::2], final.weight[1::2])
    np.testing.assert_allclose(final.weight.sum(), 2, atol=4e-16)
    np.testing.assert_allclose(final.fit_weight.mean(), 1, atol=4e-16)


def test_sampling_api_rejects_outcomes_and_projection_is_outcome_invariant():
    assert set(inspect.signature(sampling.sample_day).parameters) == {
        "ticker",
        "date",
        "action_id",
        "state_i",
        "seed",
    }
    causal = dict(
        ticker="SPY",
        date="20230103",
        action_id=np.arange(200),
        state_i=np.full(200, 60),
    )
    # Arbitrary synthetic future sidecars are never passed to this pure function.
    rows_a = dict(
        causal,
        net_base=np.arange(200),
        status=np.full(200, "FILLED"),
        oracle=np.ones(200),
    )
    rows_b = dict(
        causal,
        net_base=-np.arange(200),
        status=np.full(200, "NO_FILL"),
        oracle=np.zeros(200),
    )
    keys = ("ticker", "date", "action_id", "state_i")
    assert_sample_equal(
        sampling.sample_day(**{k: rows_a[k] for k in keys}),
        sampling.sample_day(**{k: rows_b[k] for k in keys}),
    )
    with pytest.raises(TypeError):
        sampling.sample_day(**rows_a)


@pytest.mark.parametrize(
    "ids,states",
    [
        ([1, 1], [60, 61]),
        ([1, 2], [60]),
        ([1.0], [60]),
        ([True], [60]),
        ([-1], [60]),
        ([1], [59]),
        ([1], [376]),
        ([[1]], [[60]]),
        (np.array([2**63], dtype=np.uint64), [60]),
        ([1], [60.0]),
    ],
)
def test_reject_invalid_identity_arrays(ids, states):
    with pytest.raises(ValueError):
        sampling.sample_day("SPY", "20230103", np.asarray(ids), np.asarray(states))


@pytest.mark.parametrize(
    "ticker,date,seed",
    [
        ("spy", "20230103", 20261018),
        ("SPY", "20230230", 20261018),
        ("SPY", "2023-01-03", 20261018),
        ("SPY", "20230103", 1),
        ("SPY", "20230103", 20261018.0),
    ],
)
def test_reject_noncanonical_day_and_seed(ticker, date, seed):
    with pytest.raises(ValueError):
        sampling.sample_day(ticker, date, np.array([1]), np.array([60]), seed=seed)


def test_fit_rejects_period_duplicates_and_tampering():
    h1 = sample()
    for samples, role in (
        ([h1, h1], "teacher"),
        ([h1], "final"),
        ([sample("20230703")], "teacher"),
        ([sample("20250102")], "final"),
        ([], "teacher"),
    ):
        with pytest.raises(ValueError):
            sampling.prepare_fit_rows(samples, role=role)
    for bad in (
        replace(h1, weight=h1.weight * 2),
        replace(h1, identity_sha256=np.full(len(h1.action_id), "a" * 64)),
        replace(h1, selected_by_band=np.array([31, 7, 0, 32])),
    ):
        with pytest.raises(ValueError):
            sampling.prepare_fit_rows([bad], role="teacher")


def test_all_identity_fields_affect_hash():
    baseline = sampling.canonical_identity(20261018, "SPY", "20230103", 60, 7)
    alternatives = [
        (20261019, "SPY", "20230103", 60, 7),
        (20261018, "QQQ", "20230103", 60, 7),
        (20261018, "SPY", "20230104", 60, 7),
        (20261018, "SPY", "20230103", 61, 7),
        (20261018, "SPY", "20230103", 60, 8),
    ]
    assert all(
        hashlib.sha256(sampling.canonical_identity(*args)).digest()
        != hashlib.sha256(baseline).digest()
        for args in alternatives
    )


def test_unequal_sample_counts_still_equal_day_mass():
    small = sampling.sample_day("QQQ", "20230103", np.array([100]), np.array([60]))
    big = sample()
    fit = sampling.prepare_fit_rows([small, big], role="teacher")
    assert len(fit.weight) == 72
    for ticker in ("QQQ", "SPY"):
        np.testing.assert_allclose(
            fit.weight[fit.ticker == ticker].sum(), 1, atol=5e-16
        )
        np.testing.assert_allclose(
            fit.fit_weight[fit.ticker == ticker].sum(), 36, atol=2e-14
        )


def test_digest_collision_uses_full_identity_tiebreak(monkeypatch):
    class ConstantHash:
        def hexdigest(self):
            return "0" * 64

    monkeypatch.setattr(sampling.hashlib, "sha256", lambda _: ConstantHash())
    ids = np.arange(40, dtype=np.int64)[::-1]
    states = np.full(40, 60, dtype=np.int64)
    day = sampling.sample_day("SPY", "20230103", ids, states)
    np.testing.assert_array_equal(day.action_id, np.arange(32))
