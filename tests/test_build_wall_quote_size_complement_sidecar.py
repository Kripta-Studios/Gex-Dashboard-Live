from __future__ import annotations

import pandas as pd
import pytest

from neural.jepa.build_wall_quote_size_complement_sidecar import (
    EXPECTED_COMPLEMENT_KEY_SHA256,
    EXPECTED_COMPLEMENT_SESSIONS,
    canonical_bytes,
)


def test_complement_contract_is_frozen() -> None:
    assert EXPECTED_COMPLEMENT_SESSIONS == 1078
    assert EXPECTED_COMPLEMENT_KEY_SHA256 == (
        "10665f9070736651ee0d04a63f01a28165b3cd818c42e711437f256be342e3dd"
    )


def test_canonical_seal_json_rejects_nan() -> None:
    left = canonical_bytes({"b": 2, "a": 1})
    right = canonical_bytes({"a": 1, "b": 2})
    assert left == right == b'{"a":1,"b":2}'
    with pytest.raises(ValueError):
        canonical_bytes({"bad": float("nan")})


def test_session_key_fields_do_not_depend_on_dataframe_index() -> None:
    frame = pd.DataFrame(
        {"ticker": ["QQQ", "SPY"], "trade_date": ["20220103", "20220103"]},
        index=[8, 4],
    )
    assert list(frame.columns) == ["ticker", "trade_date"]
