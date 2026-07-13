from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa.h_ibqdyn1_features import ALPHA_FIELDS, event_features, right_stats


def ticks(right: str, *, offset: float = 0.0) -> pd.DataFrame:
    start = pd.Timestamp("2024-01-02 10:34:28")
    rows = []
    for index in range(25):
        bid = 1.0 + offset + (index % 4) * 0.01
        ask = bid + 0.10 + (index % 3) * 0.01
        rows.append(
            {
                "right": right,
                "timestamp": start + pd.Timedelta(seconds=index),
                "contract_ordinal": index,
                "bid": bid,
                "ask": ask,
                "bid_size": 10 + (index % 5),
                "ask_size": 15 - (index % 5),
                "bid_exchange": 1,
                "ask_exchange": 2,
                "bid_condition": 0,
                "ask_condition": 0,
            }
        )
    return pd.DataFrame(rows)


def test_event_feature_block_has_exactly_20_finite_alpha_fields() -> None:
    decision = pd.Timestamp("2024-01-02 10:35:00")
    result = event_features(ticks("CALL"), ticks("PUT", offset=0.2), decision)
    assert len(ALPHA_FIELDS) == 20
    assert set(ALPHA_FIELDS).issubset(result)
    assert np.isfinite([result[field] for field in ALPHA_FIELDS]).all()
    assert result["ibqdyn_call_valid"]
    assert result["ibqdyn_put_valid"]


def test_condition_exchange_only_reports_do_not_inflate_alpha_updates() -> None:
    frame = ticks("CALL")
    duplicate = frame.iloc[[5]].copy()
    duplicate["timestamp"] = duplicate["timestamp"] + pd.Timedelta(milliseconds=500)
    duplicate["contract_ordinal"] = 5.5
    duplicate["bid_exchange"] = 9
    duplicate["bid_condition"] = 7
    frame = pd.concat([frame.iloc[:6], duplicate, frame.iloc[6:]], ignore_index=True)
    frame["contract_ordinal"] = np.arange(len(frame))
    result = right_stats(frame, pd.Timestamp("2024-01-02 10:35:00"), "CALL")
    assert result["ibqdyn_call_raw_rows"] == 26
    assert result["ibqdyn_call_alpha_state_rows"] == 25
    assert result["ibqdyn_call_condition_exchange_only_rows"] >= 1


def test_same_millisecond_collision_is_not_an_ordered_pair() -> None:
    frame = ticks("CALL")
    collision = frame.iloc[[10]].copy()
    collision["bid"] = collision["bid"] + 0.02
    collision["contract_ordinal"] = 10.5
    frame = pd.concat([frame.iloc[:11], collision, frame.iloc[11:]], ignore_index=True)
    frame["contract_ordinal"] = np.arange(len(frame))
    result = right_stats(frame, pd.Timestamp("2024-01-02 10:35:00"), "CALL")
    assert result["ibqdyn_call_collision_rows"] == 2
    assert result["ibqdyn_call_ordered_pair_count"] < len(frame) - 1


def test_invalid_sparse_right_remains_missing() -> None:
    frame = ticks("PUT").iloc[:4].copy()
    result = right_stats(frame, pd.Timestamp("2024-01-02 10:35:00"), "PUT")
    assert not result["ibqdyn_put_valid"]
    assert np.isnan(result["ibqdyn_put_log_update_count"])
