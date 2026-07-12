from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neural.jepa.surface_flow_features import (
    FLOW_FEATURES,
    aggregate_candidate_flow,
    attach_completed_underlying_controls,
    last_scheduled_decision_minute,
    make_touch_candidates,
    option_market_close_minute,
    prepare_completed_bar_flow,
    underlying_market_close_minute,
    validate_underlying_session,
)


def _greeks(times: list[str], *, interval: str = "1m") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": "SPY",
            "expiration": "2024-01-02",
            "trade_date": "2024-01-02",
            "interval_used": interval,
            "timestamp": times,
            "underlying_timestamp": times,
            "right": "CALL",
            "strike": 100.0,
            "bid": 0.9,
            "ask": 1.1,
        }
    )


def _ohlc(times: list[str], closes: list[float], volumes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": "SPY",
            "expiration": "2024-01-02",
            "trade_date": "2024-01-02",
            "interval_used": "1m",
            "timestamp": times,
            "right": "CALL",
            "strike": 100.0,
            "close": closes,
            "volume": volumes,
            "count": volumes,
        }
    )


def _candidate() -> pd.Series:
    return pd.Series(
        {
            "decision_dt": pd.Timestamp("2024-01-02 10:35:00"),
            "candidate_wall_strike": 100.0,
            "candidate_right": "CALL",
            "spot": 100.0,
        }
    )


def test_completed_window_excludes_current_incomplete_bar_and_uses_bar_start_quote() -> None:
    times = ["2024-01-02 10:34:00", "2024-01-02 10:35:00"]
    flow, audit = prepare_completed_bar_flow(
        _greeks(times),
        _ohlc(times, [1.2, 2.0], [10.0, 999.0]),
        expected_ticker="SPY",
        expected_trade_date="20240102",
    )
    features = aggregate_candidate_flow(flow, _candidate())
    assert audit["unmatched_active_rows"] == 0
    assert features["surface_call_volume_w1m"] == 10.0
    assert features["surface_call_signed_volume_w1m"] == 10.0
    assert features["flow_latest_bar_start"] == pd.Timestamp("2024-01-02 10:34:00")
    assert features["flow_latest_bar_end"] == pd.Timestamp("2024-01-02 10:35:00")


def test_subminute_quote_cannot_sign_exact_minute_bar() -> None:
    flow, audit = prepare_completed_bar_flow(
        _greeks(["2024-01-02 10:34:30"]),
        _ohlc(["2024-01-02 10:34:00"], [1.2], [7.0]),
        expected_ticker="SPY",
        expected_trade_date="20240102",
    )
    features = aggregate_candidate_flow(flow, _candidate())
    assert audit["greeks_subminute_rows"] == 1
    assert audit["unmatched_active_rows"] == 1
    assert features["surface_call_volume_w1m"] == 7.0
    assert features["surface_call_signed_volume_w1m"] == 0.0
    assert features["surface_call_quote_volume_coverage_w1m"] == 0.0
    assert features["surface_call_signable_volume_coverage_w1m"] == 0.0


def test_nonpositive_close_stays_in_unsigned_denominator() -> None:
    flow, audit = prepare_completed_bar_flow(
        _greeks(["2024-01-02 10:34:00"]),
        _ohlc(["2024-01-02 10:34:00"], [0.0], [5.0]),
        expected_ticker="SPY",
        expected_trade_date="20240102",
    )
    features = aggregate_candidate_flow(flow, _candidate())
    assert audit["nonpositive_close_active_rows"] == 1
    assert audit["nonpositive_close_active_volume"] == 5.0
    assert features["surface_call_volume_w1m"] == 5.0
    assert features["surface_call_close_notional_w1m"] == 0.0
    assert features["surface_call_quote_volume_coverage_w1m"] == 1.0
    assert features["surface_call_price_volume_coverage_w1m"] == 0.0
    assert features["surface_call_signed_volume_w1m"] == 0.0


def test_duplicate_wrong_interval_and_timestamp_disagreement_fail_closed() -> None:
    greeks = _greeks(["2024-01-02 10:34:00"])
    bars = _ohlc(["2024-01-02 10:34:00"], [1.0], [1.0])
    with pytest.raises(AssertionError, match="duplicate exact quote"):
        prepare_completed_bar_flow(pd.concat([greeks, greeks], ignore_index=True), bars)
    with pytest.raises(AssertionError, match="interval_used=1m"):
        prepare_completed_bar_flow(_greeks(["2024-01-02 10:34:00"], interval="5m"), bars)
    disagreement = greeks.copy()
    disagreement["underlying_timestamp"] = "2024-01-02 10:34:01"
    with pytest.raises(AssertionError, match="differ"):
        prepare_completed_bar_flow(disagreement, bars)
    missing_clock = greeks.copy()
    missing_clock["timestamp"] = None
    with pytest.raises(AssertionError, match="both be complete"):
        prepare_completed_bar_flow(missing_clock, bars)
    unknown = greeks.copy()
    unknown["right"] = "X"
    with pytest.raises(AssertionError, match="unknown option rights"):
        prepare_completed_bar_flow(unknown, bars)
    with pytest.raises(AssertionError, match="duplicate OHLC"):
        prepare_completed_bar_flow(greeks, pd.concat([bars, bars], ignore_index=True))
    invalid_strike = greeks.copy()
    invalid_strike["strike"] = np.inf
    with pytest.raises(AssertionError, match="invalid normalized contract keys"):
        prepare_completed_bar_flow(invalid_strike, bars)


def test_option_timestamps_must_match_expected_session_date() -> None:
    greeks = _greeks(["2024-01-03 10:34:00"])
    bars = _ohlc(["2024-01-02 10:34:00"], [1.0], [1.0])
    with pytest.raises(AssertionError, match="greeks timestamps"):
        prepare_completed_bar_flow(
            greeks,
            bars,
            expected_ticker="SPY",
            expected_trade_date="20240102",
        )
    greeks = _greeks(["2024-01-02 10:34:00"])
    bars["timestamp"] = "2024-01-03 10:34:00"
    with pytest.raises(AssertionError, match="OHLC timestamps"):
        prepare_completed_bar_flow(
            greeks,
            bars,
            expected_ticker="SPY",
            expected_trade_date="20240102",
        )


def test_half_day_clocks_and_required_flow_grid_are_distinct() -> None:
    assert option_market_close_minute("SPXW", "20240703") == 780
    assert option_market_close_minute("SPY", "20240703") == 795
    assert option_market_close_minute("QQQ", "20240102") == 975
    assert underlying_market_close_minute("20240703") == 780
    assert last_scheduled_decision_minute("SPY", "20240703") == 775
    times = pd.date_range("2024-07-03 10:20:00", "2024-07-03 12:54:00", freq="1min").astype(str).tolist()
    greeks = _greeks(times)
    bars = _ohlc(times, [1.0] * len(times), [1.0] * len(times))
    for frame in (greeks, bars):
        frame["trade_date"] = "2024-07-03"
        frame["expiration"] = "2024-07-03"
    _, audit = prepare_completed_bar_flow(
        greeks,
        bars,
        expected_ticker="SPY",
        expected_trade_date="20240703",
    )
    assert audit["option_market_close_minute"] == 795
    assert audit["underlying_market_close_minute"] == 780
    assert audit["last_scheduled_decision_minute"] == 775
    assert audit["expected_required_window_minutes"] == 155
    assert audit["greeks_required_window_minutes"] == 155
    assert audit["ohlc_required_window_minutes"] == 155


def test_missing_count_keeps_volume_and_reduces_count_coverage() -> None:
    bars = _ohlc(["2024-01-02 10:34:00"], [1.2], [9.0])
    bars["count"] = np.nan
    flow, audit = prepare_completed_bar_flow(
        _greeks(["2024-01-02 10:34:00"]), bars,
        expected_ticker="SPY", expected_trade_date="20240102",
    )
    features = aggregate_candidate_flow(flow, _candidate())
    assert audit["active_volume"] == 9.0
    assert audit["missing_count_active_rows"] == 1
    assert features["surface_call_volume_w1m"] == 9.0
    assert features["surface_call_count_w1m"] == 0.0
    assert features["surface_call_count_volume_coverage_w1m"] == 0.0


def test_event_universe_collapses_aliases_and_repeated_touch_episode() -> None:
    walls = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY", "SPY"],
            "trade_date": ["20240102"] * 3,
            "minute": [635, 640, 645],
            "spot": [100.0, 100.01, 100.02],
            "wall_call_gamma_strike": [100.0] * 3,
            "wall_put_gamma_strike": [90.0] * 3,
            "wall_call_delta_strike": [100.0] * 3,
            "wall_put_delta_strike": [90.0] * 3,
        }
    )
    events = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY"],
            "trade_date": ["20240102", "20240102"],
            "minute": [635, 640],
            "spot": [100.0, 100.01],
            "ret_1m_bps": [1.0, 1.0],
            "ret_5m_bps": [2.0, 2.0],
            "ret_15m_bps": [3.0, 3.0],
            "ret_30m_bps": [4.0, 4.0],
        }
    )
    candidates = make_touch_candidates(walls, events)
    assert len(candidates) == 1
    row = candidates.iloc[0]
    assert row["wall_identity"] == "call_delta+call_gamma"
    assert row["wall_alias_count"] == 2
    assert row["minute"] == 635
    assert row["episode_start_minute"] == 635


def test_half_day_excludes_physical_candidates_at_or_after_cash_close() -> None:
    walls = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY"],
            "trade_date": ["20240703", "20240703"],
            "minute": [775, 780],
            "spot": [100.0, 100.0],
            "wall_call_gamma_strike": [100.0, 100.0],
            "wall_put_gamma_strike": [90.0, 90.0],
            "wall_call_delta_strike": [110.0, 110.0],
            "wall_put_delta_strike": [90.0, 90.0],
        }
    )
    events = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY"],
            "trade_date": ["20240703", "20240703"],
            "minute": [775, 780],
            "spot": [100.0, 100.0],
            "ret_1m_bps": [0.0, 0.0],
            "ret_5m_bps": [0.0, 0.0],
            "ret_15m_bps": [0.0, 0.0],
            "ret_30m_bps": [0.0, 0.0],
        }
    )
    candidates = make_touch_candidates(walls, events)
    assert candidates["minute"].tolist() == [775]


def test_simultaneous_support_and_resistance_at_same_level_is_excluded() -> None:
    walls = pd.DataFrame(
        {
            "ticker": ["SPY"], "trade_date": ["20240102"], "minute": [635], "spot": [100.0],
            "wall_call_gamma_strike": [100.0], "wall_put_gamma_strike": [100.0],
            "wall_call_delta_strike": [110.0], "wall_put_delta_strike": [90.0],
        }
    )
    events = pd.DataFrame(
        {
            "ticker": ["SPY"], "trade_date": ["20240102"], "minute": [635], "spot": [100.0],
            "ret_1m_bps": [0.0], "ret_5m_bps": [0.0], "ret_15m_bps": [0.0], "ret_30m_bps": [0.0],
        }
    )
    candidates, audit = make_touch_candidates(walls, events, return_audit=True)
    assert candidates.empty
    assert audit["ambiguous_opposite_role_levels"] == 1
    assert audit["ambiguous_opposite_role_rows_excluded"] == 2


def test_nonfinite_event_control_fails_closed() -> None:
    walls = pd.DataFrame(
        {
            "ticker": ["SPY"], "trade_date": ["20240102"], "minute": [635], "spot": [100.0],
            "wall_call_gamma_strike": [100.0], "wall_put_gamma_strike": [90.0],
            "wall_call_delta_strike": [110.0], "wall_put_delta_strike": [90.0],
        }
    )
    events = pd.DataFrame(
        {
            "ticker": ["SPY"], "trade_date": ["20240102"], "minute": [635], "spot": [100.0],
            "ret_1m_bps": [np.nan], "ret_5m_bps": [0.0], "ret_15m_bps": [0.0], "ret_30m_bps": [0.0],
        }
    )
    with pytest.raises(AssertionError, match="non-finite"):
        make_touch_candidates(walls, events)


def test_spot_alignment_uses_executable_spot_and_rejects_material_difference() -> None:
    walls = pd.DataFrame(
        {
            "ticker": ["SPY"], "trade_date": ["20240102"], "minute": [635], "spot": [100.0],
            "wall_call_gamma_strike": [100.0], "wall_put_gamma_strike": [90.0],
            "wall_call_delta_strike": [110.0], "wall_put_delta_strike": [90.0],
        }
    )
    events = pd.DataFrame(
        {
            "ticker": ["SPY"], "trade_date": ["20240102"], "minute": [635], "spot": [100.000005],
            "ret_1m_bps": [0.0], "ret_5m_bps": [0.0], "ret_15m_bps": [0.0], "ret_30m_bps": [0.0],
        }
    )
    candidates = make_touch_candidates(walls, events)
    assert candidates["spot"].iloc[0] == events["spot"].iloc[0]
    events["spot"] = 100.005
    with pytest.raises(AssertionError, match="exact-spot parity"):
        make_touch_candidates(walls, events)


def test_realized_volatility_uses_only_completed_underlying_bars() -> None:
    candidate = pd.DataFrame(
        {
            "decision_dt": [pd.Timestamp("2024-01-02 10:35:00")],
        }
    )
    times = pd.date_range("2024-01-02 10:18:00", "2024-01-02 10:35:00", freq="1min")
    base = pd.DataFrame({"timestamp": times, "close": np.linspace(99.0, 101.0, len(times))})
    changed = base.copy()
    changed.loc[changed["timestamp"].eq(pd.Timestamp("2024-01-02 10:35:00")), "close"] = 10_000.0
    left = attach_completed_underlying_controls(candidate, base)
    right = attach_completed_underlying_controls(candidate, changed)
    assert left["realized_vol_5m_bps"].iloc[0] == right["realized_vol_5m_bps"].iloc[0]
    assert left["realized_vol_15m_bps"].iloc[0] == right["realized_vol_15m_bps"].iloc[0]
    assert np.isfinite(left[["realized_vol_5m_bps", "realized_vol_15m_bps"]].to_numpy()).all()


def test_underlying_control_timestamps_must_match_expected_session_date() -> None:
    candidate = pd.DataFrame({"decision_dt": [pd.Timestamp("2024-01-02 10:35:00")]})
    underlying = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-03 10:18:00", periods=18, freq="1min"),
            "close": np.linspace(100.0, 101.0, 18),
        }
    )
    with pytest.raises(AssertionError, match="underlying control timestamps"):
        attach_completed_underlying_controls(
            candidate,
            underlying,
            expected_trade_date="20240102",
        )


def test_derived_underlying_requires_exact_metadata_grid_and_envelope() -> None:
    times = pd.date_range("2024-01-02 09:30:00", "2024-01-02 15:59:00", freq="1min")
    source = pd.DataFrame(
        {
            "symbol": "SPY", "date": "2024-01-02", "timestamp": times,
            "open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0,
            "tick_count": 60,
        }
    )
    validated, audit = validate_underlying_session(
        source, expected_ticker="SPY", expected_trade_date="20240102"
    )
    assert len(validated) == 390
    assert audit["underlying_required_window_minutes"] == 390
    missing = source[source["timestamp"].ne(pd.Timestamp("2024-01-02 12:00:00"))]
    with pytest.raises(AssertionError, match="grid is incomplete"):
        validate_underlying_session(missing, expected_ticker="SPY", expected_trade_date="20240102")
    invalid = source.copy()
    invalid.loc[invalid["timestamp"].eq(pd.Timestamp("2024-01-02 10:20:00")), "high"] = 99.0
    with pytest.raises(AssertionError, match="invalid research-window rows"):
        validate_underlying_session(invalid, expected_ticker="SPY", expected_trade_date="20240102")
    early_only = source.copy(); early_only.loc[0, ["open", "high", "low", "close"]] = 0.0
    _, early_audit = validate_underlying_session(
        early_only, expected_ticker="SPY", expected_trade_date="20240102"
    )
    assert early_audit["underlying_out_of_scope_invalid_rows"] == 1


def test_derived_underlying_half_day_requires_only_cash_rth_grid() -> None:
    times = pd.date_range("2024-07-03 09:30:00", "2024-07-03 12:59:00", freq="1min")
    source = pd.DataFrame(
        {
            "symbol": "QQQ", "date": "2024-07-03", "timestamp": times,
            "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0,
            "tick_count": 1,
        }
    )
    _, audit = validate_underlying_session(
        source, expected_ticker="QQQ", expected_trade_date="20240703"
    )
    assert audit["expected_underlying_required_window_minutes"] == 210


def test_empty_candidate_session_keeps_control_schema() -> None:
    underlying = pd.DataFrame(
        {"timestamp": pd.date_range("2024-01-02 10:00:00", periods=2, freq="1min"), "close": [100.0, 100.1]}
    )
    output = attach_completed_underlying_controls(pd.DataFrame(columns=["decision_dt"]), underlying)
    assert output.empty
    assert {"realized_vol_5m_bps", "realized_vol_15m_bps"}.issubset(output.columns)


def test_flow_allowlist_contains_no_outcome_fields() -> None:
    forbidden = ("future", "label", "outcome", "pnl", "exit", "win")
    assert not [name for name in FLOW_FEATURES if any(token in name.lower() for token in forbidden)]
