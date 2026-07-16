from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from neural.jepa import build_calendar_risk_reversal_pressure_v1 as subject


DAY = "20230103"
T0, T1 = subject.target_datetimes(DAY)


def _chain(expiration: str, front: bool) -> pd.DataFrame:
    rows: list[dict] = []
    specs = [
        ("CALL", 100.0, 0.25, 0.24, 0.20 if front else 0.18, 0.23 if front else 0.19),
        ("CALL", 101.0, 0.30, 0.29, 0.30, 0.31),
        ("PUT", 99.0, -0.25, -0.24, 0.24 if front else 0.21, 0.25 if front else 0.22),
        ("PUT", 98.0, -0.30, -0.29, 0.31, 0.32),
    ]
    for right, strike, delta0, delta1, mid0, mid1 in specs:
        for timestamp, delta, mid in ((T0, delta0, mid0), (T1, delta1, mid1)):
            rows.append(
                {
                    "symbol": "QQQ",
                    "expiration": expiration,
                    "trade_date": DAY,
                    "timestamp": timestamp,
                    "strike": strike,
                    "right": right,
                    "delta": delta,
                    "bid": 1.0,
                    "ask": 1.1,
                    "bid_implied_vol": mid - 0.01,
                    "ask_implied_vol": mid + 0.01,
                }
            )
    return pd.DataFrame(rows)


def test_fixed_t0_contracts_build_calendar_rr_pressure() -> None:
    result = subject.calculate_session_feature(
        ticker="QQQ",
        trade_date=DAY,
        front_expiration=DAY,
        back_expiration="20230106",
        spot_t0=100.0,
        spot_t1=100.5,
        front_chain=_chain(DAY, True),
        back_chain=_chain("20230106", False),
    )
    assert result["front_call_strike"] == 100.0
    assert result["front_put_strike"] == 99.0
    assert result["back_call_strike"] == 100.0
    assert result["back_put_strike"] == 99.0
    expected_t0 = (0.20 - 0.24) - (0.18 - 0.21)
    expected_t1 = (0.23 - 0.25) - (0.19 - 0.22)
    assert result["calendar_rr_t0"] == pytest.approx(expected_t0)
    assert result["calendar_rr_t1"] == pytest.approx(expected_t1)
    assert result["calendar_rr_pressure"] == pytest.approx(expected_t1 - expected_t0)


def test_contract_must_persist_to_t1_without_reselection() -> None:
    chain = _chain(DAY, True)
    chain = chain.loc[~(chain["timestamp"].eq(T1) & chain["strike"].eq(100.0))].copy()
    chosen = subject.select_fixed_contract(chain, right="CALL", spot_t0=100.0)
    assert chosen["strike"] == 101.0


def test_invalid_iv_or_quote_is_not_signable() -> None:
    chain = _chain(DAY, True)
    mask = chain["right"].eq("CALL") & chain["strike"].eq(100.0)
    chain.loc[mask, "bid_implied_vol"] = 0.0
    chosen = subject.select_fixed_contract(chain, right="CALL", spot_t0=100.0)
    assert chosen["strike"] == 101.0


def test_greek_iv_join_requires_identical_vintage_prices() -> None:
    greek = _chain(DAY, True).drop(columns=["bid_implied_vol", "ask_implied_vol"])
    iv = _chain(DAY, True).drop(columns=["delta"])
    joined = subject.join_greeks_iv(greek, iv)
    assert len(joined) == len(greek)
    iv.loc[0, "bid"] += 0.01
    with pytest.raises(AssertionError, match="vintage bid"):
        subject.join_greeks_iv(greek, iv)


def test_data_gate_strict_frequency_and_distinctness() -> None:
    rows: list[dict] = []
    for ticker_index, ticker in enumerate(subject.TICKERS):
        for month in range(1, 13):
            for day in range(1, 15):
                rows.append(
                    {
                        "ticker": ticker,
                        "trade_date": f"2023{month:02d}{day:02d}",
                        "month": f"2023{month:02d}",
                        "feature_valid": True,
                        "economic_clock_eligible": True,
                        "calendar_rr_pressure": ticker_index + month / 100 + day / 10000,
                    }
                )
    features = pd.DataFrame(rows)
    coverage, distinctness, gate = subject.evaluate_data_gate(features)
    assert coverage["coverage"].eq(1.0).all()
    assert distinctness["distinct_states"].ge(50).all()
    assert gate["frequency_pass"] is True
    assert gate["passed"] is True

    reduced = features.loc[~(
        features["ticker"].eq("QQQ")
        & features["month"].eq("202301")
        & features["trade_date"].str[-2:].astype(int).gt(12)
    )]
    _, _, failed = subject.evaluate_data_gate(reduced)
    assert failed["frequency_pass"] is False
    assert failed["passed"] is False


def test_nonfinite_pressure_is_rejected() -> None:
    chain = _chain(DAY, True)
    chain.loc[0, "bid_implied_vol"] = np.nan
    # The bad row is not selected; corrupt every CALL candidate to force rejection.
    chain.loc[chain["right"].eq("CALL"), "bid_implied_vol"] = np.nan
    with pytest.raises(AssertionError, match="no persistent signable CALL"):
        subject.select_fixed_contract(chain, right="CALL", spot_t0=100.0)


def test_cli_has_no_outcome_or_scope_arguments() -> None:
    args = subject.parse_args([])
    assert not hasattr(args, "end_date")
    assert not hasattr(args, "outcome")
    with pytest.raises(SystemExit):
        subject.parse_args(["--end-date", "20251231"])


def test_direct_cli_imports() -> None:
    script = Path(subject.__file__).resolve()
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=script.parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--options-root" in completed.stdout
