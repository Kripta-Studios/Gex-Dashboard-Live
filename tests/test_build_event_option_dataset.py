from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from neural.jepa import build_event_option_dataset as builder


def _underlying(minutes: list[int]) -> pd.DataFrame:
    base = pd.Timestamp("2026-06-01")
    values = np.arange(len(minutes), dtype=float)
    return pd.DataFrame(
        {
            "dt": [base + pd.Timedelta(minutes=minute) for minute in minutes],
            "minute": minutes,
            "open": 100.0 + values,
            "high": 101.0 + values,
            "low": 99.0 + values,
            "close": 100.0 + values,
            "tick_count": 1.0,
        }
    )


def test_build_levels_requires_every_initial_balance_minute() -> None:
    complete = _underlying(list(range(570, 631)))
    levels = builder.build_levels(complete)
    assert levels["ib_high"] == pytest.approx(160.0)
    assert levels["ib_low"] == pytest.approx(99.0)

    missing_ib_minute = _underlying([minute for minute in range(570, 701) if minute != 600])
    assert builder.build_levels(missing_ib_minute) == {}


def test_manifest_row_with_incomplete_initial_balance_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    underlying = _underlying([minute for minute in range(570, 701) if minute != 600])
    monkeypatch.setattr(builder, "load_underlying", lambda _: underlying)

    def fail_if_chain_is_loaded(*_args, **_kwargs):
        raise AssertionError("an invalid day must be rejected before loading the option chain")

    monkeypatch.setattr(builder, "load_chain", fail_if_chain_is_loaded)
    result = builder.build_rows_for_manifest_row(
        {"underlying_path": "unused"},
        {"require_open_interest": True},
    )
    assert result.empty


def test_executable_contract_selection_rejects_invalid_bid_ask() -> None:
    snapshot = pd.DataFrame(
        {
            "right": ["CALL", "CALL"],
            "delta": [0.25, 0.27],
            "strike": [100.0, 101.0],
            "bid": [1.10, 0.95],
            "ask": [1.00, 1.05],
            "open_interest": [1000.0, 10.0],
            "opt_volume": [1000.0, 10.0],
        }
    )
    selected = builder.select_contract(snapshot, "CALL", 0.25, "executable_quote")
    assert selected is not None
    assert float(selected["strike"]) == pytest.approx(101.0)


def test_executable_chain_features_use_previous_completed_ohlc_bar(monkeypatch: pytest.MonkeyPatch) -> None:
    quote_ts = pd.Timestamp("2026-06-01 10:30:00")
    greeks = pd.DataFrame(
        {
            "timestamp": [quote_ts],
            "underlying_timestamp": [quote_ts],
            "strike": [100.0],
            "right": ["CALL"],
            "underlying_price": [100.0],
            "delta": [0.25],
            "implied_vol": [0.2],
            "theta": [-0.1],
            "vega": [0.1],
            "bid": [1.0],
            "ask": [1.1],
        }
    )
    oi = pd.DataFrame({"strike": [100.0], "right": ["CALL"], "open_interest": [10.0]})
    ohlc = pd.DataFrame(
        {
            "timestamp": [quote_ts - pd.Timedelta(minutes=1), quote_ts],
            "strike": [100.0, 100.0],
            "right": ["CALL", "CALL"],
            "open": [0.8, 9.8],
            "high": [1.0, 10.0],
            "low": [0.7, 9.7],
            "close": [0.9, 9.9],
            "volume": [3.0, 99.0],
            "count": [2.0, 99.0],
        }
    )

    def fake_read(path, _columns):
        return {"greeks": greeks, "oi": oi, "ohlc": ohlc}[str(path)]

    monkeypatch.setattr(builder, "safe_read_parquet", fake_read)
    chain, _ = builder.load_chain(
        pd.Series({"greeks_path": "greeks", "oi_path": "oi", "ohlc_path": "ohlc"}),
        require_open_interest=True,
        option_price_mode="executable_quote",
    )

    assert chain["opt_close"].iloc[0] == pytest.approx(0.9)
    assert chain["opt_volume"].iloc[0] == pytest.approx(3.0)
    assert chain["opt_count"].iloc[0] == pytest.approx(2.0)


def test_executable_quote_label_enters_ask_and_exits_future_bid() -> None:
    ts = pd.Timestamp("2026-06-01 10:30:00")
    contract = pd.Series(
        {"strike": 100.0, "right": "CALL", "bid": 0.90, "ask": 1.00, "opt_close": 0.25}
    )
    quotes = pd.DataFrame(
        {
            "quote_dt": [
                ts,
                ts + pd.Timedelta(minutes=1),
                ts + pd.Timedelta(minutes=2),
            ],
            "strike": [100.0, 100.0, 100.0],
            "right": ["CALL", "CALL", "CALL"],
            # The crossed quote is not an executable future snapshot.
            "bid": [0.90, 5.00, 1.25],
            "ask": [1.00, 4.00, 1.30],
        }
    )
    label = builder.option_path_label(
        pd.DataFrame(),
        contract,
        ts,
        horizon_minutes=2,
        tp_pct=10.0,
        sl_pct=10.0,
        prefix="call_d25",
        option_price_mode="executable_quote",
        quotes=quotes,
    )
    assert label["call_d25_opt_status"] == 0
    assert label["call_d25_opt_exit_minutes"] == 2
    assert label["call_d25_opt_exit_ret"] == pytest.approx(0.25)
    assert label["call_d25_opt_max_ret"] == pytest.approx(0.25)
    assert label["call_d25_opt_min_ret"] == pytest.approx(0.25)


def test_executable_quote_stop_records_observed_bid_return() -> None:
    ts = pd.Timestamp("2026-06-01 10:30:00")
    contract = pd.Series({"strike": 100.0, "right": "PUT", "bid": 0.90, "ask": 1.00})
    quotes = pd.DataFrame(
        {
            "quote_dt": [ts + pd.Timedelta(minutes=1)],
            "strike": [100.0],
            "right": ["PUT"],
            "bid": [0.35],
            "ask": [0.40],
        }
    )
    label = builder.option_path_label(
        pd.DataFrame(),
        contract,
        ts,
        horizon_minutes=5,
        tp_pct=10.0,
        sl_pct=0.60,
        prefix="put_d25",
        option_price_mode="executable_quote",
        quotes=quotes,
    )
    assert label["put_d25_opt_status"] == -1
    assert label["put_d25_opt_exit_ret"] == pytest.approx(-0.65)


def test_executable_quote_zero_bid_is_a_valid_total_loss_mark() -> None:
    ts = pd.Timestamp("2026-06-01 10:30:00")
    contract = pd.Series({"strike": 100.0, "right": "PUT", "bid": 0.90, "ask": 1.00})
    quotes = pd.DataFrame(
        {
            "quote_dt": [ts + pd.Timedelta(minutes=30)],
            "strike": [100.0],
            "right": ["PUT"],
            "bid": [0.0],
            "ask": [0.05],
        }
    )

    label = builder.option_path_label(
        pd.DataFrame(),
        contract,
        ts,
        horizon_minutes=180,
        tp_pct=10.0,
        sl_pct=0.60,
        prefix="put_d25",
        min_hold_minutes=30,
        option_price_mode="executable_quote",
        quotes=quotes,
    )

    assert label["put_d25_opt_status"] == -1
    assert label["put_d25_opt_exit_minutes"] == 30
    assert label["put_d25_opt_exit_ret"] == pytest.approx(-1.0)


def test_executable_mode_never_falls_back_to_ohlc_close() -> None:
    ts = pd.Timestamp("2026-06-01 10:30:00")
    contract = pd.Series({"strike": 100.0, "right": "CALL", "bid": 0.90, "ask": 1.00, "opt_close": 0.10})
    ohlc = pd.DataFrame(
        {
            "dt": [ts + pd.Timedelta(minutes=1)],
            "strike": [100.0],
            "right": ["CALL"],
            "high": [2.00],
            "low": [1.00],
            "close": [2.00],
        }
    )
    label = builder.option_path_label(
        ohlc,
        contract,
        ts,
        horizon_minutes=5,
        tp_pct=0.50,
        sl_pct=0.60,
        prefix="call_d25",
        option_price_mode="executable_quote",
        quotes=None,
    )
    assert np.isnan(label["call_d25_opt_exit_ret"])


def test_low_before_high_does_not_arm_and_hit_trail_in_same_ohlc_bar() -> None:
    ts = pd.Timestamp("2026-06-01 10:30:00")
    contract = pd.Series(
        {"strike": 100.0, "right": "CALL", "opt_close": 1.00, "bid": 0.90, "ask": 1.10}
    )
    ohlc = pd.DataFrame(
        {
            "dt": [ts + pd.Timedelta(minutes=1)],
            "strike": [100.0],
            "right": ["CALL"],
            "high": [2.00],
            "low": [1.40],
            "close": [1.40],
        }
    )
    label = builder.option_path_label(
        ohlc,
        contract,
        ts,
        horizon_minutes=5,
        tp_pct=10.0,
        sl_pct=0.90,
        prefix="call_d25",
        exit_mode="trailing",
        trail_activation_pct=0.50,
        trail_drawdown_pct=0.25,
        option_price_mode="legacy_ohlc",
    )
    assert label["call_d25_opt_status"] == 0
    assert label["call_d25_opt_exit_ret"] == pytest.approx(0.40)
