from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from neural.jepa.build_cross_market_transmission_view_v1 import (
    CROSS_FEATURES,
    OUTPUT_ROOT,
    PAIR_FIELDS,
    _assert_output_path,
    _master_read_columns,
    cross_features_for_event,
    exact_completed_window,
    hash_ordered,
    pair_features,
)


def _day(scale: float = 1.0, drift: float = 0.001) -> pd.DataFrame:
    index = pd.date_range("2023-06-01 10:00:00", periods=40, freq="min")
    close = scale * np.exp(np.arange(40, dtype=float) * drift + np.sin(np.arange(40)) * 0.0001)
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "tick_count": 1.0}, index=index)


def test_allowlist_is_exactly_28_ordered_fields() -> None:
    assert len(PAIR_FIELDS) == 7
    assert len(CROSS_FEATURES) == 28
    assert hash_ordered(CROSS_FEATURES) == "5df3d817d12c5d938427eabeca145f1d4e59420e1283fa3cf3bdaeef6b112058"
    assert len(CROSS_FEATURES) == len(set(CROSS_FEATURES))


def test_master_projection_rejects_outcome_columns() -> None:
    schema = [
        "ticker", "trade_date", "timestamp", "minute", "ib_range_bps", "dist_ib_high_bps",
        "dist_ib_low_bps", "nearest_level_abs_bps", "ret_1m_bps", "ret_5m_bps", "ret_15m_bps",
        "ret_30m_bps", "call_d25_iv", "put_d25_iv", "call_d25_opt_exit_ret",
    ]
    projected = _master_read_columns(schema)
    assert "call_d25_opt_exit_ret" not in projected
    assert all("_opt_" not in column for column in projected)


def test_exact_window_never_uses_event_or_future_bar() -> None:
    day = _day()
    event = pd.Timestamp("2023-06-01 10:35:00")
    window = exact_completed_window(day, event)
    assert len(window) == 30
    assert window.index.min() == event - pd.Timedelta(minutes=30)
    assert window.index.max() == event - pd.Timedelta(minutes=1)
    other = exact_completed_window(_day(2.0, 0.0005), event)
    baseline = pair_features(window, other)
    changed = day.copy()
    changed.loc[changed.index >= event, "close"] *= 100.0
    assert pair_features(exact_completed_window(changed, event), other) == baseline


def test_exact_window_fails_closed_without_one_timestamp() -> None:
    day = _day().drop(pd.Timestamp("2023-06-01 10:12:00"))
    with pytest.raises(AssertionError, match="missing exact completed bars"):
        exact_completed_window(day, pd.Timestamp("2023-06-01 10:35:00"))


def test_exact_window_validates_only_consumed_rows_and_fails_closed_inside() -> None:
    event = pd.Timestamp("2023-06-01 10:35:00")
    outside = _day()
    outside.loc[pd.Timestamp("2023-06-01 10:00:00"), "close"] = np.nan
    assert len(exact_completed_window(outside, event)) == 30
    inside = _day()
    inside.loc[pd.Timestamp("2023-06-01 10:12:00"), "close"] = np.nan
    with pytest.raises(AssertionError, match="invalid OHLC in consumed exact window"):
        exact_completed_window(inside, event)


def test_pair_and_target_features_are_finite_and_ordered() -> None:
    event = pd.Timestamp("2023-06-01 10:35:00")
    windows = {
        "SPXW": exact_completed_window(_day(4000.0, 0.00020), event),
        "SPY": exact_completed_window(_day(400.0, 0.00018), event),
        "QQQ": exact_completed_window(_day(300.0, 0.00025), event),
        "TLT": exact_completed_window(_day(100.0, -0.00005), event),
    }
    features = cross_features_for_event(windows, target="QQQ")
    assert tuple(features) == CROSS_FEATURES
    assert np.isfinite(np.asarray(list(features.values()), dtype=float)).all()
    target_tlt = pair_features(windows["QQQ"], windows["TLT"])
    assert features["xmt__target_tlt__beta_30"] == target_tlt["beta_30"]


def test_pair_features_fail_closed_on_degenerate_denominators() -> None:
    event = pd.Timestamp("2023-06-01 10:35:00")
    varying = exact_completed_window(_day(100.0, 0.0002), event)
    constant = varying.copy()
    constant[["open", "high", "low", "close"]] = 100.0
    with pytest.raises(AssertionError, match="zero-variance beta denominator"):
        pair_features(varying, constant)


def test_output_is_restricted_to_authorized_tmp_root() -> None:
    _assert_output_path(OUTPUT_ROOT / "view.parquet")
    with pytest.raises(AssertionError):
        _assert_output_path(Path("research_papers/forbidden.parquet"))
