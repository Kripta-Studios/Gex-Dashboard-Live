import numpy as np
import pandas as pd

from diagnose_oracle_quote_anomalies import (
    contract_lookup,
    observation,
    relative_comparison,
    summarize,
)


def cache_fixture():
    bid = np.array([[2.0, 0.8], [2.0, 0.8], [2.0, 0.8], [2.1, 0.7]])
    ask = np.array([[2.2, 1.0], [2.2, 1.0], [2.2, 1.0], [2.3, 0.9]])
    return {
        "bid": bid, "ask": ask, "row_flags": np.full((4, 2), 3, dtype=np.uint8),
        "strike": np.array([100.0, 100.0]), "right": np.array([0, 1]),
        "spot": np.array([101.0, 101.0, 101.0, 101.0]),
        "spot_valid": np.ones(4, dtype=bool),
    }


def test_intrinsic_spread_repetition_and_parity_are_independent_metrics():
    cache = cache_fixture()
    row = observation(cache, contract_lookup(cache), "OFFERED_ENTRY", "ENTRY", 1, 2, 0)
    assert row["approx_intrinsic"] == 1.0
    assert np.isclose(row["ask_minus_intrinsic"], 1.2)
    assert row["repeated_observed_run"] == 3
    assert row["parity_pair_available"]
    # call_mid 2.1 - put_mid .9 - (101-100) = .2
    assert np.isclose(row["approx_parity_residual"], 0.2)


def test_put_intrinsic_and_ask_below_intrinsic_flag():
    cache = cache_fixture()
    cache["spot"][:] = 98.0
    row = observation(cache, contract_lookup(cache), "ORACLE_ENTRY", "ENTRY", 2, 0, 1)
    assert row["approx_intrinsic"] == 2.0
    assert row["ask_below_intrinsic"]


def test_invalid_quote_is_retained_with_missing_diagnostics():
    cache = cache_fixture()
    cache["ask"][1, 0] = 0.0
    row = observation(cache, contract_lookup(cache), "ORACLE_EXIT", "EXIT", 3, 1, 0)
    assert not row["quote_valid"]
    assert np.isnan(row["spread"])
    assert row["repeated_observed_run"] == 0


def test_population_summary_and_relative_rates_do_not_use_pnl():
    frame = pd.DataFrame([
        {"quote_valid": True, "spot_valid": True, "ask_below_intrinsic": False,
         "zero_bid": False, "spread_over_ask_ge_025": False,
         "spread_over_ask_ge_050": False, "repeated_observed_ge_3": True,
         "repeated_observed_ge_5": False, "parity_pair_available": True,
         "approx_parity_abs_ge_010": True, "approx_parity_abs_ge_025": False,
         "approx_parity_abs_ge_050": False, "ask_minus_intrinsic": 1.0,
         "bid_minus_intrinsic": .8, "spread": .2, "spread_over_ask": .1,
         "repeated_observed_run": 3, "approx_parity_residual": .2,
         "approx_parity_abs": .2},
    ])
    summaries = {"A": summarize(frame), "B": summarize(frame)}
    compared = relative_comparison(summaries, "A", "B")
    assert compared["repeated_observed_ge_3"]["rate_difference"] == 0
    assert compared["ask_below_intrinsic"]["rate_ratio"] is None
