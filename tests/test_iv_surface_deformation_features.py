from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from neural.jepa.iv_surface_deformation_features import (
    IV_SURFACE_ALLOWLIST,
    IV_SURFACE_FEATURES,
    attach_iv_surface_features,
    candidate_iv_surface_features,
    prepare_iv_surface_source,
)


DAY = "2024-01-02"
DECISION = pd.Timestamp("2024-01-02 10:35:00")
WALL = 100.0
STRIKES = np.array([98.8, 99.2, 99.6, 100.0, 100.4, 100.8, 101.2])


def _raw_surface(*, omit: tuple[str, float, int] | None = None) -> pd.DataFrame:
    rows = []
    coefficients = {
        "CALL": {0: (0.30, 0.04, 0.02), 1: (0.29, 0.03, 0.01), 5: (0.28, 0.02, 0.00), 15: (0.27, 0.01, -0.01)},
        "PUT": {0: (0.32, -0.02, 0.03), 1: (0.30, -0.01, 0.02), 5: (0.29, 0.00, 0.01), 15: (0.28, 0.01, 0.00)},
    }
    for right in ("CALL", "PUT"):
        for lag in (0, 1, 5, 15):
            timestamp = DECISION - pd.Timedelta(minutes=lag)
            a, b, c = coefficients[right][lag]
            for strike in STRIKES:
                if omit == (right, strike, lag):
                    continue
                x = np.log(strike / WALL) / 0.015
                rows.append(
                    {
                        "symbol": "SPY",
                        "expiration": DAY,
                        "trade_date": DAY,
                        "interval_used": "1m",
                        "timestamp": timestamp,
                        "underlying_timestamp": timestamp,
                        "right": right,
                        "strike": strike,
                        "implied_vol": a + b * x + c * x * x,
                        "iv_error": 0.0,
                        "bid": 1.0,
                        "ask": 1.1,
                    }
                )
    return pd.DataFrame(rows)


def _candidate() -> pd.Series:
    return pd.Series({"decision_dt": DECISION, "candidate_wall_strike": WALL, "spot": WALL})


def _prepared(raw: pd.DataFrame | None = None) -> pd.DataFrame:
    frame, _ = prepare_iv_surface_source(
        _raw_surface() if raw is None else raw,
        expected_ticker="SPY",
        expected_trade_date="20240102",
    )
    return frame


def test_exact_quadratic_changes_and_frozen_allowlist() -> None:
    values = candidate_iv_surface_features(_prepared(), _candidate())
    assert len(IV_SURFACE_FEATURES) == 18
    assert len(IV_SURFACE_ALLOWLIST) == 23
    assert list(values) == list(IV_SURFACE_ALLOWLIST)
    assert values["surface_call_valid"]
    assert values["surface_put_valid"]
    assert values["surface_both_valid"]
    assert values["surface_call_shared_strikes"] == 7
    assert values["surface_put_shared_strikes"] == 7
    assert values["surface_call_level_change_1m"] == pytest.approx(0.01)
    assert values["surface_call_skew_change_5m"] == pytest.approx(0.02)
    assert values["surface_call_curvature_change_15m"] == pytest.approx(0.06)
    assert values["surface_put_level_change_15m"] == pytest.approx(0.04)
    assert values["surface_put_skew_change_5m"] == pytest.approx(-0.02)
    assert values["surface_put_curvature_change_1m"] == pytest.approx(0.02)


def test_identical_shared_contract_set_is_required_at_all_four_clocks() -> None:
    raw = _raw_surface(omit=("CALL", 98.8, 5))
    values = candidate_iv_surface_features(_prepared(raw), _candidate())
    assert values["surface_call_shared_strikes"] == 6
    assert values["surface_call_valid"]
    # A replacement strike outside the frozen local set cannot restore count.
    extra = raw.iloc[[0]].copy()
    extra["strike"] = 102.0
    raw = pd.concat([raw, extra], ignore_index=True)
    values = candidate_iv_surface_features(_prepared(raw), _candidate())
    assert values["surface_call_shared_strikes"] == 6


def test_invalid_geometry_preserves_candidate_with_nan_features() -> None:
    raw = _raw_surface()
    # Remove three CALL strikes from one clock, leaving invalid shared geometry.
    mask = (raw["right"] == "CALL") & (raw["timestamp"] == DECISION - pd.Timedelta(minutes=1)) & raw["strike"].isin(STRIKES[:3])
    surface = _prepared(raw.loc[~mask].copy())
    candidates = pd.DataFrame([_candidate(), _candidate()])
    attached = attach_iv_surface_features(candidates, surface)
    assert len(attached) == 2
    assert not attached["surface_call_valid"].any()
    assert attached["surface_put_valid"].all()
    assert attached["surface_call_shared_strikes"].eq(4).all()
    assert attached[[name for name in IV_SURFACE_FEATURES if "_call_" in name]].isna().all().all()


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("implied_vol", 0.0),
        ("implied_vol", 2.0),
        ("iv_error", 0.10001),
        ("bid", 0.0),
        ("ask", 0.5),
    ],
)
def test_frozen_validity_rules_apply_at_every_clock(column: str, value: float) -> None:
    raw = _raw_surface()
    mask = (raw.right == "CALL") & (raw.strike == 98.8) & (raw.timestamp == DECISION)
    raw.loc[mask, column] = value
    values = candidate_iv_surface_features(_prepared(raw), _candidate())
    assert values["surface_call_shared_strikes"] == 6


def test_exact_clock_duplicate_and_native_underlying_disagreement_fail_closed() -> None:
    raw = _raw_surface()
    subminute = raw.copy()
    subminute.loc[0, "timestamp"] += pd.Timedelta(seconds=1)
    with pytest.raises(AssertionError, match="non-boundary"):
        _prepared(subminute)
    duplicate = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    with pytest.raises(AssertionError, match="duplicate normalized"):
        _prepared(duplicate)
    disagreement = raw.copy()
    disagreement.loc[0, "underlying_timestamp"] += pd.Timedelta(minutes=1)
    with pytest.raises(AssertionError, match="differ"):
        _prepared(disagreement)
    missing_native = raw.drop(columns="timestamp")
    with pytest.raises(KeyError, match="timestamp"):
        _prepared(missing_native)


def test_frozen_contract_intersection_removes_source_extra_without_expansion() -> None:
    raw = _raw_surface()
    extra = raw.iloc[[0]].copy()
    extra["strike"] = 100.2
    raw = pd.concat([raw, extra], ignore_index=True)
    allowed = pd.DataFrame(
        [(DAY, right, strike) for right in ("CALL", "PUT") for strike in STRIKES],
        columns=["expiration", "right", "strike"],
    )
    surface, audit = prepare_iv_surface_source(
        raw,
        expected_ticker="SPY",
        expected_trade_date="20240102",
        frozen_contract_keys=allowed,
    )
    assert audit["frozen_universe_extra_rows"] == 1
    assert 100.2 not in set(surface.strike)


def test_future_rows_are_not_consumed_and_2026_fails_closed() -> None:
    surface = _prepared()
    baseline = candidate_iv_surface_features(surface, _candidate())
    future = surface.iloc[[0]].copy()
    future["snapshot_dt"] = DECISION + pd.Timedelta(minutes=1)
    future["implied_vol"] = 1.99
    changed = candidate_iv_surface_features(pd.concat([surface, future], ignore_index=True), _candidate())
    assert baseline == changed
    raw = _raw_surface()
    raw["trade_date"] = "2026-01-02"
    raw["expiration"] = "2026-01-02"
    raw["timestamp"] = pd.to_datetime(raw["timestamp"]) + pd.DateOffset(years=2)
    raw["underlying_timestamp"] = raw["timestamp"]
    with pytest.raises(AssertionError, match="2026"):
        prepare_iv_surface_source(raw, expected_ticker="SPY", expected_trade_date="20260102")

