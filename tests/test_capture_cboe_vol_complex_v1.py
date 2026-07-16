from __future__ import annotations

from io import BytesIO

import pandas as pd
import pytest

from neural.jepa.capture_cboe_vol_complex_v1 import sha256_bytes, validate_payload


def payload(columns: dict[str, list]) -> bytes:
    frame = pd.DataFrame(columns)
    buffer = BytesIO()
    frame.to_csv(buffer, index=False)
    return buffer.getvalue()


def test_validate_ohlc_payload() -> None:
    raw = payload(
        {
            "DATE": ["01/03/2022", "07/15/2026"],
            "OPEN": [20.0, 18.0],
            "HIGH": [21.0, 19.0],
            "LOW": [19.0, 17.0],
            "CLOSE": [20.5, 18.5],
        }
    )
    result = validate_payload("VIX_History.csv", raw)
    assert result["rows"] == 2
    assert result["date_max"] == "20260715"
    assert len(sha256_bytes(raw)) == 64


def test_validate_single_value_payload() -> None:
    raw = payload({"DATE": ["01/03/2022", "07/15/2026"], "VVIX": [90.0, 95.0]})
    assert validate_payload("VVIX_History.csv", raw)["columns"] == ["DATE", "VVIX"]


def test_rejects_duplicate_date() -> None:
    raw = payload({"DATE": ["01/03/2022", "01/03/2022", "07/15/2026"], "VVIX": [90.0, 91.0, 95.0]})
    with pytest.raises(AssertionError, match="duplicate"):
        validate_payload("VVIX_History.csv", raw)


def test_rejects_invalid_ohlc_envelope() -> None:
    raw = payload(
        {
            "DATE": ["01/03/2022", "07/15/2026"],
            "OPEN": [20.0, 18.0],
            "HIGH": [19.0, 19.0],
            "LOW": [18.0, 17.0],
            "CLOSE": [20.5, 18.5],
        }
    )
    with pytest.raises(AssertionError, match="envelope"):
        validate_payload("VIX_History.csv", raw)
