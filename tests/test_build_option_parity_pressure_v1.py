import numpy as np
import pandas as pd
import pytest

from neural.jepa.build_option_parity_pressure_v1 import (
    CLOCKS,
    MIN_COMMON_STRIKES,
    compute_parity_event,
    evaluate_data_gate,
    normalize_option_keys,
    target_datetimes,
)


def parity_frame(trade_date: str, differences: tuple[float, float, float]) -> tuple[pd.DataFrame, dict[pd.Timestamp, float]]:
    times = target_datetimes(trade_date)
    spots = {times[0]: 100.0, times[1]: 100.0}
    rows = []
    for time_index, timestamp in enumerate(times):
        for strike_index, strike in enumerate((99.5, 100.0, 100.5)):
            width = 0.20
            z = 0.0 if time_index == 0 else differences[strike_index]
            basis = z * width
            put_mid = 1.0
            call_mid = 100.0 + basis - strike + put_mid
            for right, mid in (("CALL", call_mid), ("PUT", put_mid)):
                rows.append(
                    {
                        "symbol": "QQQ",
                        "expiration": trade_date,
                        "trade_date": trade_date,
                        "timestamp": timestamp,
                        "strike": strike,
                        "right": right,
                        "bid": mid - 0.10,
                        "ask": mid + 0.10,
                    }
                )
    return pd.DataFrame(rows), spots


def test_parity_pressure_is_median_same_strike_change() -> None:
    frame, spots = parity_frame("20230301", (1.0, 2.0, 9.0))
    event = compute_parity_event(frame, spots, ticker="QQQ", trade_date="20230301")
    assert event["parity_valid"] is True
    assert event["valid_common_strikes"] == MIN_COMMON_STRIKES
    assert event["parity_pressure"] == pytest.approx(2.0)


def test_crossed_quote_removes_strike_and_fails_minimum() -> None:
    frame, spots = parity_frame("20230301", (1.0, 2.0, 3.0))
    timestamp = target_datetimes("20230301")[1]
    mask = frame["timestamp"].eq(timestamp) & frame["strike"].eq(100.0) & frame["right"].eq("CALL")
    frame.loc[mask, "bid"] = 2.0
    frame.loc[mask, "ask"] = 1.0
    event = compute_parity_event(frame, spots, ticker="QQQ", trade_date="20230301")
    assert event["parity_valid"] is False
    assert event["invalid_reason"] == "INSUFFICIENT_COMMON_STRIKES"
    assert event["t1_crossed_rows"] == 1


def test_zero_bid_is_not_signable() -> None:
    frame, spots = parity_frame("20230301", (1.0, 2.0, 3.0))
    frame.loc[frame["strike"].eq(99.5), "bid"] = 0.0
    event = compute_parity_event(frame, spots, ticker="QQQ", trade_date="20230301")
    assert event["parity_valid"] is False
    assert event["t0_zero_bid_rows"] == 2
    assert event["t1_zero_bid_rows"] == 2


def test_normalize_option_keys_maps_sidecar_right_without_copying_prices() -> None:
    source = pd.DataFrame(
        {
            "symbol": ["qqq"],
            "expiration": ["2023-03-01"],
            "trade_date": ["2023-03-01"],
            "strike": [100.0],
            "right": ["C"],
            "bid": [1.25],
            "ask": [1.35],
        }
    )
    normalized = normalize_option_keys(source)
    assert normalized.loc[0, "right"] == "CALL"
    assert normalized.loc[0, "bid"] == 1.25
    assert normalized.loc[0, "ask"] == 1.35


def test_data_gate_passes_complete_nondegenerate_fixture() -> None:
    rows = []
    for ticker_index, ticker in enumerate(("QQQ", "SPXW", "SPY")):
        for year in (2023, 2024, 2025):
            for month in range(1, 13):
                for day in range(1, 15):
                    rows.append(
                        {
                            "ticker": ticker,
                            "trade_date": f"{year}{month:02d}{day:02d}",
                            "year": str(year),
                            "month": f"{year}{month:02d}",
                            "economic_clock_eligible": True,
                            "parity_valid": True,
                            "parity_pressure": ticker_index * 10_000 + year + month + day / 100,
                        }
                    )
    _, _, evaluated = evaluate_data_gate(pd.DataFrame(rows))
    assert evaluated["summary"]["passed"] is True
    assert evaluated["summary"]["minimum_monthly_valid_events"] == 14


def test_data_gate_rejects_twelve_events_and_degenerate_pressure() -> None:
    rows = []
    for ticker in ("QQQ", "SPXW", "SPY"):
        for year in (2023, 2024, 2025):
            for month in range(1, 13):
                for day in range(1, 13):
                    rows.append(
                        {
                            "ticker": ticker,
                            "trade_date": f"{year}{month:02d}{day:02d}",
                            "year": str(year),
                            "month": f"{year}{month:02d}",
                            "economic_clock_eligible": True,
                            "parity_valid": True,
                            "parity_pressure": 0.0,
                        }
                    )
    _, _, evaluated = evaluate_data_gate(pd.DataFrame(rows))
    assert evaluated["summary"]["passed"] is False
    assert evaluated["summary"]["frequency_pass"] is False
    assert evaluated["summary"]["distinctness_pass"] is False


def test_target_clocks_are_frozen() -> None:
    times = target_datetimes("20230301")
    assert tuple(timestamp.strftime("%H:%M:%S") for timestamp in times) == CLOCKS


def test_no_2026_constant_enters_builder_scope() -> None:
    import neural.jepa.build_option_parity_pressure_v1 as module

    assert module.END_DATE == "20251231"
    assert "2026" not in {str(value) for value in module.HALF_DAYS}
    assert np.isclose(module.MONEYNESS_RADIUS_BPS, 100.0)
