from __future__ import annotations

import pandas as pd
import pytest

from neural.jepa.build_wall_quote_size_pressure_dataset import (
    _normalize_index,
    annual_both_valid_profile,
)


def test_quote_index_requires_exact_coverage() -> None:
    frame = pd.DataFrame(
        {
            "ticker": ["SPY"],
            "trade_date": ["20240102"],
            "greeks_path": ["g"],
            "greeks_sha256": ["0" * 64],
            "quotes_path": ["q"],
            "quotes_sha256": ["1" * 64],
            "raw_response_path": ["r"],
            "raw_response_sha256": ["2" * 64],
            "session_manifest_path": ["m"],
            "session_manifest_sha256": ["3" * 64],
            "rows": [10],
            "stored_timestamp_key_coverage_exact": [True],
            "missing_stored_key_rows": [0],
        }
    )
    out = _normalize_index(frame, "test")
    assert out.loc[0, "origin"] == "test"
    frame.loc[0, "missing_stored_key_rows"] = 1
    with pytest.raises(AssertionError, match="exact coverage"):
        _normalize_index(frame, "test")


def test_quote_index_rejects_2026() -> None:
    frame = pd.DataFrame(
        {
            "ticker": ["SPY"],
            "trade_date": ["20260102"],
            "greeks_path": ["g"],
            "greeks_sha256": ["0" * 64],
            "quotes_path": ["q"],
            "quotes_sha256": ["1" * 64],
            "raw_response_path": ["r"],
            "raw_response_sha256": ["2" * 64],
            "session_manifest_path": ["m"],
            "session_manifest_sha256": ["3" * 64],
            "rows": [10],
            "stored_timestamp_key_coverage_exact": [True],
            "missing_stored_key_rows": [0],
        }
    )
    with pytest.raises(AssertionError, match="exact coverage"):
        _normalize_index(frame, "test")


def test_annual_coverage_is_candidate_weighted_not_month_weighted() -> None:
    frame = pd.DataFrame(
        {
            "ticker": ["SPY"] * 10,
            "trade_date": ["20240102"] + ["20240201"] * 9,
            "qsize_both_valid": [True] + [False] * 9,
        }
    )
    annual = annual_both_valid_profile(frame)
    assert annual.loc[0, "qsize_both_valid"] == pytest.approx(0.1)
