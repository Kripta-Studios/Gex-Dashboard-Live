from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from neural.jepa.quote_size_pressure_features import (
    QSIZE_ALLOWLIST,
    QSIZE_FEATURES,
    attach_quote_size_features,
    candidate_quote_size_features,
    prepare_quote_size_source,
)


DAY = "20240102"
DECISION = pd.Timestamp("2024-01-02 10:35:00")
STRIKES = np.array([98.8, 99.2, 99.6, 100.0, 100.4, 100.8, 101.2])


def raw_quotes() -> pd.DataFrame:
    rows = []
    for right in ("C", "P"):
        for lag in (0, 1, 5, 15):
            for index, strike in enumerate(STRIKES):
                rows.append(
                    {
                        "symbol": "SPY",
                        "expiration": DAY,
                        "trade_date": DAY,
                        "timestamp": DECISION - pd.Timedelta(minutes=lag),
                        "right": right,
                        "strike": strike,
                        "bid": 1.0,
                        "ask": 1.1,
                        "bid_size": 10 + index + lag,
                        "ask_size": 5 + index,
                    }
                )
    return pd.DataFrame(rows)


def prepared(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    raw = raw_quotes() if frame is None else frame
    keys = raw[["timestamp", "expiration", "right", "strike"]].drop_duplicates()
    result, _ = prepare_quote_size_source(
        raw,
        expected_ticker="SPY",
        expected_trade_date=DAY,
        frozen_contract_keys=keys,
    )
    return result


def candidate() -> pd.Series:
    return pd.Series(
        {"decision_dt": DECISION, "candidate_wall_strike": 100.0, "spot": 100.0}
    )


def test_frozen_feature_count_and_exact_contract_changes() -> None:
    values = candidate_quote_size_features(prepared(), candidate())
    assert len(QSIZE_FEATURES) == 40
    assert len(QSIZE_ALLOWLIST) == 45
    assert values["qsize_both_valid"]
    assert values["qsize_call_shared_local_contracts"] == 7
    assert values["qsize_call_local_log_bid_depth_change_5m"] < 0
    assert np.isfinite(values["qsize_put_relative_qimb_change_15m"])


def test_crossed_and_zero_bid_are_invalid_without_reversal() -> None:
    raw = raw_quotes()
    mask = (
        raw["right"].eq("C")
        & raw["timestamp"].eq(DECISION)
        & raw["strike"].isin(STRIKES[:5])
    )
    raw.loc[mask, "bid"] = 0.0
    values = candidate_quote_size_features(prepared(raw), candidate())
    assert not values["qsize_call_valid"]
    assert np.isnan(values["qsize_call_local_qimb"])
    assert values["qsize_put_valid"]


def test_missing_contract_preserves_candidate_and_no_replacement() -> None:
    raw = raw_quotes()
    raw = raw[
        ~(
            raw["right"].eq("P")
            & raw["timestamp"].eq(DECISION - pd.Timedelta(minutes=5))
            & raw["strike"].isin(STRIKES[:3])
        )
    ]
    attached = attach_quote_size_features(pd.DataFrame([candidate()]), prepared(raw))
    assert len(attached) == 1
    assert attached.loc[0, "qsize_put_shared_local_contracts"] == 4
    assert not attached.loc[0, "qsize_put_valid"]


def test_exact_clock_duplicates_extras_and_2026_fail_closed() -> None:
    raw = raw_quotes()
    duplicate = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    with pytest.raises(AssertionError, match="duplicate"):
        prepared(duplicate)
    extra = raw.iloc[[0]].copy()
    extra["strike"] = 120.0
    source, audit = prepare_quote_size_source(
        pd.concat([raw, extra], ignore_index=True),
        expected_ticker="SPY",
        expected_trade_date=DAY,
        frozen_contract_keys=raw[
            ["timestamp", "expiration", "right", "strike"]
        ].drop_duplicates(),
    )
    assert audit["frozen_universe_extra_rows"] == 1
    assert 120.0 not in set(source["strike"])
    raw["trade_date"] = "20260102"
    raw["expiration"] = "20260102"
    with pytest.raises(AssertionError, match="forbidden"):
        prepare_quote_size_source(
            raw,
            expected_ticker="SPY",
            expected_trade_date="20260102",
            frozen_contract_keys=raw[
                ["timestamp", "expiration", "right", "strike"]
            ].drop_duplicates(),
        )


def test_contract_first_seen_later_cannot_enter_earlier_clock() -> None:
    raw = raw_quotes()
    keys = raw[["timestamp", "expiration", "right", "strike"]].drop_duplicates()
    keys = keys[
        ~(
            keys["right"].eq("C")
            & keys["timestamp"].eq(DECISION)
            & keys["strike"].eq(STRIKES[0])
        )
    ]
    source, audit = prepare_quote_size_source(
        raw,
        expected_ticker="SPY",
        expected_trade_date=DAY,
        frozen_contract_keys=keys,
    )
    assert audit["frozen_universe_extra_rows"] == 1
    assert not (
        source["right"].eq("CALL")
        & source["snapshot_dt"].eq(DECISION)
        & source["strike"].eq(STRIKES[0])
    ).any()
    assert (
        source["right"].eq("CALL")
        & source["snapshot_dt"].eq(DECISION - pd.Timedelta(minutes=1))
        & source["strike"].eq(STRIKES[0])
    ).any()
