from __future__ import annotations

import json

import pytest

from neural.jepa import capture_yahoo_futures_60m_v1 as module


def make_payload(symbol: str, bad_envelope: bool = False) -> bytes:
    count = 10_001
    timestamps = list(range(module.PERIOD1, module.PERIOD1 + 3600 * count, 3600))
    high = [101.0] * count
    if bad_envelope:
        high[-1] = 99.0
    result = {
        "chart": {
            "error": None,
            "result": [
                {
                    "meta": {
                        "symbol": symbol,
                        "instrumentType": "FUTURE",
                        "exchangeTimezoneName": "America/New_York",
                    },
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [
                            {
                                "open": [100.0] * count,
                                "high": high,
                                "low": [99.0] * count,
                                "close": [100.5] * count,
                                "volume": [10.0] * count,
                            }
                        ]
                    },
                }
            ],
        }
    }
    return json.dumps(result).encode()


def test_frozen_symbols_exclude_unavailable_vx() -> None:
    assert module.SYMBOLS == ("ES=F", "NQ=F", "YM=F", "RTY=F", "ZN=F", "GC=F", "CL=F")
    assert "VX=F" not in module.SYMBOLS


def test_payload_contract_accepts_complete_futures_source() -> None:
    audit = module.validate_payload(make_payload("ES=F"), "ES=F")
    assert audit["rows"] == 10_001
    assert audit["complete_ohlc_rows"] == 10_001
    assert audit["nonzero_volume_rows"] == 10_001


def test_payload_contract_rejects_bad_envelope() -> None:
    with pytest.raises(AssertionError, match="OHLC envelope"):
        module.validate_payload(make_payload("NQ=F", bad_envelope=True), "NQ=F")


def test_urls_freeze_period_and_interval() -> None:
    url = module.source_url("ES=F")
    assert f"period1={module.PERIOD1}" in url
    assert f"period2={module.PERIOD2}" in url
    assert "interval=60m" in url
