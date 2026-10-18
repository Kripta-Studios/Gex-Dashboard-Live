"""Synthetic source diagnostics around a 13:00 NYSE early close."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import inspect_short_session_sources as short


def inputs():
    clocks = pd.date_range("2023-07-03 09:30", periods=391, freq="min")
    spot = 400 + np.minimum(np.arange(391), 210) * 0.01
    greek = pd.DataFrame(
        dict(
            symbol="SPY",
            expiration="2023-07-03",
            trade_date="2023-07-03",
            strike=400.0,
            right="CALL",
            timestamp=clocks,
            underlying_timestamp=clocks,
            underlying_price=spot,
            bid=1.0,
            ask=1.1,
            delta=0.5,
            implied_vol=0.2,
            vega=0.01,
            theta=-0.1,
        )
    )
    oi = pd.DataFrame(
        dict(
            symbol=["SPY"] * 3,
            expiration=["2023-07-03"] * 3,
            trade_date=["2023-07-03"] * 3,
            strike=[400.0] * 3,
            right=["CALL"] * 3,
            timestamp=[
                "2023-07-03T09:00:00",
                "2023-07-03T10:00:00",
                "2023-07-03T13:01:00",
            ],
            open_interest=[20, 0, 30],
        )
    )
    return greek, oi


def test_positive_repeated_tail_counted_separately_from_core_window():
    greek, oi = inputs()
    per, summary = short.diagnostic(greek, oi, "SPY", "20230703")
    assert len(per) == 391 and summary["normalization_status"] == "PASS"
    assert summary["ib_valid_samples"] == 60
    tail = summary["windows"]["strict_after_close_1301_1600"]
    assert tail["slots"] == 180 and tail["valid_spot_minutes"] == 180
    assert tail["counts"]["positive_spot_equal_1300_same_contract"] == 180
    assert tail["counts"]["valid_quote_equal_1300_same_contract"] == 180
    assert summary["windows"]["close_1300"]["slots"] == 1
    assert summary["windows"]["tail_including_close_1300_1600"]["slots"] == 181
    assert summary["oi_availability"]["before_open"]["positive_valid_records"] == 1
    assert summary["oi_availability"]["during_ib"]["zero_valid_records"] == 1
    assert summary["oi_availability"]["after_1300"]["positive_valid_records"] == 1
    assert per.known_oi_positive_contracts.iloc[59] == 0
    assert per.known_oi_positive_contracts.iloc[211] == 1


def test_zero_tail_and_one_invalid_first_ib_sample_preserve_missingness():
    greek, oi = inputs()
    greek.loc[0, "underlying_price"] = 0
    greek.loc[211:, ["underlying_price", "bid", "ask"]] = 0
    per, summary = short.diagnostic(greek, oi, "SPY", "20230703")
    assert summary["ib_valid_samples"] == 59
    assert summary["technical_checks"]["ib_valid"]
    assert not per.spot_valid.iloc[0]
    assert not per.spot_valid.iloc[211:].any()
    tail = summary["windows"]["strict_after_close_1301_1600"]
    assert tail["counts"]["zero_raw_spot_rows"] == 180
    assert tail["counts"]["bid_ask_both_zero_rows"] == 180
    assert tail["minutes_with_valid_quote"] == 0


def test_native_age_rejects_stale_spot_but_does_not_rewrite_quotes():
    greek, oi = inputs()
    greek.loc[211:, "underlying_timestamp"] = pd.Timestamp("2023-07-03 13:00")
    per, summary = short.diagnostic(greek, oi, "SPY", "20230703")
    tail = summary["windows"]["strict_after_close_1301_1600"]
    assert tail["valid_spot_minutes"] == 1  # 13:01 age60s is accepted by original rule
    assert tail["minutes_with_valid_quote"] == 180
    assert tail["counts"]["age_over_60s_rows"] == 179
    assert summary["paired_clock_nonzero_age_rows"] == 180
    assert per.positive_spot_equal_1300_same_contract.iloc[212] == 1


def test_proxy_clock_is_assumption_and_duplicate_proxy_time_fails():
    greek, oi = inputs()
    proxy = greek.drop(columns="timestamp")
    oi = oi.iloc[[0]].drop(columns="timestamp")
    per, summary = short.diagnostic(proxy, oi, "SPY", "20230703")
    assert summary["clock_basis"] == "ASSUMED_UNDERLYING_SNAPSHOT_CLOCK"
    assert summary["paired_clock_rows"] is None
    assert summary["oi_clock_basis"] == "ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT"
    assert summary["oi_availability"]["at_open"]["positive_valid_records"] == 1
    assert per.known_oi_positive_contracts.iloc[0] == 1
    proxy.loc[211:, "underlying_timestamp"] = pd.Timestamp("2023-07-03 13:00")
    _, failed = short.diagnostic(proxy, oi, "SPY", "20230703")
    assert failed["normalization_status"] == "FAILED"
    assert failed["duplicate_greek_identity_clock_rows"] == 181
    assert not failed["future_short_session_candidate"]


def test_later_invalid_oi_invalidates_without_using_future_contract_denominator():
    greek, oi = inputs()
    oi = pd.concat([oi.iloc[:2], oi.iloc[[1]]], ignore_index=True)
    later = greek.iloc[[300]].copy()
    later["strike"] = 450.0
    expanded = pd.concat([greek, later], ignore_index=True)
    per, summary = short.diagnostic(expanded, oi, "SPY", "20230703")
    assert summary["oi_invalid_records"] == 2
    assert per.known_oi_valid_contracts.iloc[29] == 1
    assert per.known_oi_valid_contracts.iloc[30] == 0
    assert per.known_contracts.iloc[299] == 1
    assert per.known_contracts.iloc[300] == 2
