from __future__ import annotations

import json

import pandas as pd
import pytest

from neural.jepa import (
    audit_cross_venue_calendar_rr_leader_v4r1_2026_data_gate as audit,
)
from neural.jepa import (
    build_cross_venue_calendar_rr_leader_v4r1_2026_data_gate as build,
)
from neural.jepa import (
    capture_cross_venue_calendar_rr_leader_v4r1_2026_source_retry as capture,
)
from neural.jepa import cross_venue_calendar_rr_leader_v4r1_2026_common as common
from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v2 as v2
from neural.jepa import (
    reseal_cross_venue_calendar_rr_leader_v4r1_2026_source_retry as reseal,
)


class _Response:
    status_code = 200

    def __init__(self, payload: dict) -> None:
        self.content = json.dumps(payload).encode()


def _payload() -> dict:
    return {
        "response": [
            {
                "contract": {"right": "C", "strike": 600},
                "data": [
                    {
                        "underlying_timestamp": "2026-06-24T10:30:00",
                        "bid": 1.0,
                        "ask": 1.1,
                        "delta": 0.25,
                    },
                    {
                        "underlying_timestamp": "2026-06-24T10:35:00",
                        "bid": 1.0,
                        "ask": 1.1,
                        "delta": 0.24,
                    },
                ],
            }
        ]
    }


def test_metadata_universe_is_exact_and_outcome_free() -> None:
    universe = common.discover_universe()
    specs = common.retry_specs(universe)
    assert len(universe) == 266
    assert len(specs) == 5
    assert set(specs["capture_id"]) == set(common.RETRY_IDS)
    assert universe["trade_date"].min() == "20260102"
    assert universe["trade_date"].max() == "20260724"


def test_known_vintage_mismatches_reproduce_without_outcomes() -> None:
    specs = common.retry_specs(common.discover_universe())
    greek_only = 0
    iv_only = 0
    for spec in specs.to_dict(orient="records"):
        gate = common.target_pair_gate(
            spec["vintage_greeks_path"], spec["vintage_iv_path"], spec
        )
        assert gate["usable"] is False
        greek_only += int(gate["greek_only_rows"])
        iv_only += int(gate["iv_only_rows"])
    assert (greek_only, iv_only) == (92, 516)


def test_timestamp_typed_retry_pair_is_read_exactly(tmp_path) -> None:
    identity = {
        "symbol": "QQQ",
        "expiration": "20260624",
        "trade_date": "20260624",
        "strike": 600.0,
        "right": "CALL",
    }
    clocks = pd.to_datetime(["2026-06-24 10:30:00", "2026-06-24 10:35:00"])
    greeks = pd.DataFrame(
        [
            {
                **identity,
                "underlying_timestamp": clock,
                "delta": 0.25,
                "bid": 1.0,
                "ask": 1.1,
            }
            for clock in clocks
        ]
    )
    iv = pd.DataFrame(
        [
            {
                **identity,
                "underlying_timestamp": clock,
                "bid": 1.0,
                "ask": 1.1,
                "bid_implied_vol": 0.2,
                "ask_implied_vol": 0.21,
            }
            for clock in clocks
        ]
    )
    greek_path = tmp_path / "greeks.parquet"
    iv_path = tmp_path / "iv.parquet"
    greeks.to_parquet(greek_path, index=False)
    iv.to_parquet(iv_path, index=False)
    gate = common.target_pair_gate(
        greek_path,
        iv_path,
        {
            "ticker": "QQQ",
            "trade_date": "20260624",
            "expiration": "20260624",
        },
    )
    assert gate == {
        "usable": True,
        "greek_rows": 2,
        "iv_rows": 2,
        "shared_rows": 2,
        "greek_only_rows": 0,
        "iv_only_rows": 0,
        "reason": "",
    }


def test_request_uses_frozen_first_interval_and_identity() -> None:
    spec = {
        "ticker": "QQQ",
        "trade_date": "20260624",
        "expiration": "20260624",
    }
    calls = []

    def requester(url: str, **kwargs):
        calls.append((url, kwargs))
        return _Response(_payload())

    raw, interval, request_audit, status = capture.request_with_fallback(
        spec,
        "greeks",
        base_url=common.REMOTE_BASE_URL,
        timeout=1.0,
        requester=requester,
    )
    assert status == 200
    assert interval == "1m"
    assert len(request_audit) == 1
    assert len(calls) == 1
    normalized = common.normalize_response(
        json.loads(raw), spec, "greeks", interval
    )
    assert len(normalized) == 2
    assert normalized["trade_date"].eq("20260624").all()


def test_mapping_keeps_spy_sensor_for_spxw() -> None:
    sensor = pd.DataFrame(
        [
            {
                "ticker": "QQQ",
                "trade_date": "20260102",
                "calendar_rr_pressure": 0.1,
                "calendar_rr_t0": 0.2,
                "front_rr_t0": 0.3,
                "front_rr_t1": 0.4,
                "back_rr_t0": 0.1,
                "back_rr_t1": 0.2,
                "spot_t0": 100.0,
                "spot_t1": 101.0,
            },
            {
                "ticker": "SPY",
                "trade_date": "20260102",
                "calendar_rr_pressure": -0.1,
                "calendar_rr_t0": -0.2,
                "front_rr_t0": 0.2,
                "front_rr_t1": 0.1,
                "back_rr_t0": 0.1,
                "back_rr_t1": 0.1,
                "spot_t0": 100.0,
                "spot_t1": 99.0,
            },
        ]
    )
    targets = build.map_targets(sensor)
    mapping = targets.set_index("ticker")["sensor_ticker"].to_dict()
    assert mapping == {"QQQ": "QQQ", "SPXW": "SPY", "SPY": "SPY"}


def test_frequency_gate_requires_thirteen_each_cell() -> None:
    rows = []
    for ticker in v2.TICKERS:
        for month in common.EXPECTED_MONTH_COUNTS:
            rows.extend({"ticker": ticker, "month": month} for _ in range(13))
    counts = build.feature_counts(pd.DataFrame(rows))
    assert len(counts) == 21
    assert counts["frequency_pass"].all()
    with pytest.raises(AssertionError, match="frequency"):
        build.feature_counts(pd.DataFrame(rows[:-1]))


def test_auditor_comparison_detects_changed_feature() -> None:
    expected = pd.DataFrame({"ticker": ["QQQ"], "signal_pressure": [1.0]})
    changed = pd.DataFrame({"ticker": ["QQQ"], "signal_pressure": [2.0]})
    with pytest.raises(AssertionError, match="differs"):
        audit.compare_frames(expected, changed, ["ticker"], "feature")


def test_clis_do_not_expose_scientific_overrides() -> None:
    for args in (
        capture.parse_args([]),
        reseal.parse_args([]),
        build.parse_args([]),
        audit.parse_args([]),
    ):
        for forbidden in ("ticker", "date", "exclude", "intersection", "model"):
            assert not hasattr(args, forbidden)
