from __future__ import annotations

import math

import numpy as np
import pandas as pd

from neural.jepa.build_king_gex_manage30_v1 import (
    ACTION_IDS,
    DECISION_MAXIMUM,
    DECISION_MINIMUM,
    END_DATE,
    EXPECTED_EXECUTABLE_CANDIDATES,
    EXPECTED_SOURCE_CANDIDATES,
    FIRST_ENTRY_MINUTE,
    FROZEN_ENTRY_REJECTIONS,
    M0_FEATURES,
    M1_EXTRA_FEATURES,
    M1_FEATURES,
    PREDECLARATION,
    PREDECLARATION_SHA256,
    SNAPSHOT_CLARIFICATION,
    SNAPSHOT_CLARIFICATION_SHA256,
    LAST_ENTRY_MINUTE,
    START_DATE,
    _decision_features,
    _exact_snapshot_groups,
    _frozen_rejection_key,
    _missing_decision_features,
    _signed_log,
    _spot_return,
)
from neural.jepa.audit_existing_data_edge_join_inventory_v1 import sha256_file
from neural.jepa.evaluate_king_gex_exit_v1 import EXIT_CONFIGS


def _path(ts: pd.Timestamp, future_bid: float = 9.0) -> pd.DataFrame:
    rows = []
    for elapsed in range(1, 32):
        rows.append(
            {
                "quote_time": ts + pd.Timedelta(minutes=elapsed),
                "bid": 1.0 + elapsed / 100.0,
                "ask": 1.05 + elapsed / 100.0,
                "underlying_price": 100.0 + elapsed / 10.0,
                "delta": 0.25 + elapsed / 1000.0,
                "implied_vol": 0.20 + elapsed / 10_000.0,
                "theta": -0.10,
                "vega": 0.05,
            }
        )
    rows.append(
        {
            "quote_time": ts + pd.Timedelta(minutes=60),
            "bid": future_bid,
            "ask": future_bid + 0.05,
            "underlying_price": 200.0,
            "delta": 0.90,
            "implied_vol": 1.50,
            "theta": -9.0,
            "vega": 9.0,
        }
    )
    return pd.DataFrame(rows)


def _entry() -> dict[str, float]:
    return {
        "entry_spot": 100.0,
        "entry_delta": 0.25,
        "entry_iv": 0.20,
        "entry_theta": -0.10,
        "entry_vega": 0.05,
    }


def test_protocol_is_frozen_to_train_development_only() -> None:
    assert START_DATE == "20220101"
    assert END_DATE == "20231231"
    assert FIRST_ENTRY_MINUTE == 680
    assert LAST_ENTRY_MINUTE == 870
    assert sha256_file(PREDECLARATION) == PREDECLARATION_SHA256
    assert ACTION_IDS[-1] == "E30"
    assert len(ACTION_IDS) == 17
    assert EXPECTED_SOURCE_CANDIDATES == 22_273
    assert EXPECTED_EXECUTABLE_CANDIDATES == 22_272
    assert len(FROZEN_ENTRY_REJECTIONS) == 1
    assert sha256_file(SNAPSHOT_CLARIFICATION) == SNAPSHOT_CLARIFICATION_SHA256
    assert all(int(config["min_hold_minutes"]) == 30 for config in EXIT_CONFIGS)


def test_feature_contract_separates_path_and_synthetic_blocks() -> None:
    assert set(M0_FEATURES).issubset(M1_FEATURES)
    assert set(M1_EXTRA_FEATURES).isdisjoint(M0_FEATURES)
    assert len(M1_FEATURES) == len(set(M1_FEATURES))
    forbidden = ("outcome", "exit_reason", "realized_return", "future", "oracle")
    assert not [name for name in M1_FEATURES if any(token in name for token in forbidden)]


def test_decision_features_ignore_every_quote_after_first_legal_decision() -> None:
    ts = pd.Timestamp("2023-01-03 11:20:00")
    first, decision = _decision_features(_path(ts, future_bid=2.0), 1.0, _entry(), ts)
    second, decision2 = _decision_features(_path(ts, future_bid=20.0), 1.0, _entry(), ts)
    assert decision is not None and decision2 is not None
    assert first == second
    assert first["decision_elapsed"] == DECISION_MINIMUM
    assert first["path_quote_count"] == DECISION_MINIMUM
    assert np.isclose(first["decision_return"], 0.30)
    assert np.isclose(first["path_mfe"], 0.30)
    assert np.isclose(first["path_mae"], 0.01)


def test_decision_uses_first_quote_within_frozen_window() -> None:
    ts = pd.Timestamp("2023-01-03 11:20:00")
    path = _path(ts)
    path = path.loc[~path["quote_time"].eq(ts + pd.Timedelta(minutes=30))]
    features, decision = _decision_features(path, 1.0, _entry(), ts)
    assert decision is not None
    assert features["decision_elapsed"] == DECISION_MAXIMUM
    assert math.isnan(float(features["spot_return_1m_bps"]))


def test_missing_decision_is_explicit_and_not_asof_filled() -> None:
    ts = pd.Timestamp("2023-01-03 11:20:00")
    path = _path(ts)
    path = path.loc[
        ~path["quote_time"].isin(
            [ts + pd.Timedelta(minutes=30), ts + pd.Timedelta(minutes=31)]
        )
    ]
    features, decision = _decision_features(path, 1.0, _entry(), ts)
    assert decision is None
    assert features["decision_state_available"] == 0
    assert math.isnan(float(features["decision_bid"]))
    assert features == _missing_decision_features(ts)


def test_spot_return_requires_exact_lag_quote() -> None:
    ts = pd.Timestamp("2023-01-03 11:20:00")
    path = _path(ts)
    now = ts + pd.Timedelta(minutes=30)
    expected = (103.0 / 102.5 - 1.0) * 10_000.0
    assert np.isclose(_spot_return(path, 103.0, now, 5), expected)
    missing = path.loc[~path["quote_time"].eq(now - pd.Timedelta(minutes=5))]
    assert math.isnan(_spot_return(missing, 103.0, now, 5))


def test_signed_log_preserves_sign_and_zero() -> None:
    assert _signed_log(0.0) == 0.0
    assert _signed_log(10.0) > 0.0
    assert _signed_log(-10.0) < 0.0
    assert math.isnan(_signed_log(float("nan")))


def test_exact_snapshot_never_includes_later_quote_from_same_minute() -> None:
    stamp = pd.Timestamp("2022-06-17 13:55:00")
    later = stamp + pd.Timedelta(seconds=30)
    source = pd.DataFrame(
        {
            "quote_dt": [stamp, later],
            "strike": [277.0, 277.0],
            "ask": [0.71, 0.74],
        }
    )
    snapshots = _exact_snapshot_groups(source)
    assert snapshots[stamp]["ask"].tolist() == [0.71]
    assert snapshots[later]["ask"].tolist() == [0.74]


def test_only_frozen_train_entry_rejection_is_allowed() -> None:
    assert _frozen_rejection_key("SPXW", "20220222", 680, "PUT")
    assert not _frozen_rejection_key("SPXW", "20220222", 680, "CALL")
    assert not _frozen_rejection_key("SPXW", "20220222", 685, "PUT")
