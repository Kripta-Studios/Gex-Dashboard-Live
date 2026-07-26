from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import httpx
import pytest

from modules.king_node_engine import (
    _apply_level_lock,
    aggregate_by_strike,
    build_snapshot,
    initial_state,
)
from services.king_node_service import (
    KingNodeService,
    ThetaIndexClient,
    find_latest_tastytrade_json,
)


def tasty_fixture(strike_count: int = 55) -> dict:
    columns = [
        "strike_price",
        "time_till_exp",
        "call_iv",
        "put_iv",
        "call_gamma",
        "put_gamma",
        "call_open_int",
        "put_open_int",
        "call_gex",
        "put_gex",
        "total_gamma",
        "total_zomma",
        "total_delta",
        "total_vanna",
        "total_vomma",
        "total_vega",
        "total_speed",
        "total_charm",
        "total_dgex",
    ]
    data = []
    for index in range(strike_count):
        strike = 5800 + index * 10
        signed = (index - strike_count // 2) * 0.025
        call_gamma = abs(signed) + 0.01
        put_gamma = abs(signed) + 0.02
        call_oi = 100 + index
        put_oi = 50 + index
        call_gex = (abs(signed) + 0.01) * 1_000_000
        put_gex = -(abs(signed) + 0.005) * 600_000
        gex = call_gex + put_gex
        data.append(
            [
                strike,
                4 / (365 * 24),
                0.18 + index / 10_000,
                0.20 + index / 10_000,
                call_gamma,
                put_gamma,
                call_oi,
                put_oi,
                call_gex,
                put_gex,
                gex / 1_000_000_000,
                signed * 0.30,
                signed * 1.20,
                signed * -0.50,
                signed * -0.20,
                abs(signed) * 0.40,
                signed * 0.10,
                signed * 0.15,
                signed * 0.80,
            ]
        )
    return {
        "spot_price": 6070,
        "prev_close_price": 6050,
        "zerogamma": 6035,
        "ticker": "SPX",
        "expir": "0dte",
        "today_ddt_string": "fixture",
        "option_data": {"columns": columns, "data": data},
    }


def observed_indices(timestamp: str = "2026-07-26T14:00:00Z") -> dict:
    return {
        "vix": {
            "value": 20.0,
            "timestamp": timestamp,
            "status": "observed",
            "age_seconds": 0,
        },
        "vvix": {
            "value": 115.0,
            "timestamp": timestamp,
            "status": "observed",
            "age_seconds": 0,
        },
        "vix1d": {
            "value": 23.0,
            "timestamp": timestamp,
            "status": "observed",
            "age_seconds": 0,
        },
    }


def test_raw_gamma_is_multiplied_per_leg_before_strike_aggregation() -> None:
    rows = [
        {
            "strike_price": 6000,
            "call_gamma": 1,
            "put_gamma": 2,
            "call_open_int": 10,
            "put_open_int": 20,
        },
        {
            "strike_price": 6000,
            "call_gamma": 3,
            "put_gamma": 4,
            "call_open_int": 5,
            "put_open_int": 7,
        },
    ]
    aggregate = aggregate_by_strike(rows)[0]

    assert aggregate["raw_call_gamma"] == 25
    assert aggregate["raw_put_gamma"] == 68
    assert aggregate["raw_gamma"] == 93


def test_build_snapshot_ports_core_catalog_contract() -> None:
    snapshot, state = build_snapshot(
        tasty_fixture(),
        observed_indices(),
        initial_state("2026-07-26"),
        generated_at="2026-07-26T14:00:00Z",
        session_date="2026-07-26",
        market_minute=10 * 60,
        source_meta={"source_id": "fixture-1", "stale": False},
    )

    assert snapshot["schema_version"] == "king-node.v1"
    assert len(snapshot["rows"]) == 47
    assert snapshot["quality"]["raw_gamma_coverage"] == 1
    assert snapshot["quality"]["profile_coverage"] == 1
    assert snapshot["levels"]["raw_gamma"]["strike"] in {
        row["strike"] for row in snapshot["rows"]
    }
    expected_raw = sum(row["raw_gamma"] for row in snapshot["rows"])
    assert snapshot["totals"]["raw_gamma"] == pytest.approx(expected_raw)
    assert snapshot["regime"]["iv_raw"] == "HIGH"
    assert snapshot["regime"]["iv_intensity"] == pytest.approx(1.4)
    assert snapshot["regime"]["dte_boost"] == pytest.approx(
        1 + 0.6 * (1 - 4 / 6.5)
    )
    assert snapshot["regime"]["matrix_key"].count("|") == 7
    assert snapshot["regime"]["box_key"] == "Positive|Flat|Flat|Flat"
    assert snapshot["regime"]["reference_mode"] == "semantic_fallback"
    assert len(snapshot["levels"]["call_walls"]) <= 3
    assert len(snapshot["levels"]["put_walls"]) <= 3
    assert len(snapshot["levels"]["resistances"]) <= 6
    assert len(snapshot["levels"]["supports"]) <= 6
    assert state["surface_source_ids"] == ["fixture-1"]


def test_directions_and_gex_history_persist_across_cycles() -> None:
    state = initial_state("2026-07-26")
    snapshot = None
    for index in range(4):
        timestamp = (
            datetime(2026, 7, 26, 14, tzinfo=timezone.utc)
            + timedelta(seconds=index * 30)
        ).isoformat().replace("+00:00", "Z")
        indices = observed_indices(timestamp)
        indices["vix"]["value"] += index
        indices["vvix"]["value"] += index
        indices["vix1d"]["value"] += index
        snapshot, state = build_snapshot(
            tasty_fixture(),
            indices,
            state,
            generated_at=timestamp,
            session_date="2026-07-26",
            source_meta={"source_id": f"fixture-{index}", "stale": False},
        )

    assert snapshot is not None
    assert snapshot["directions"]["vix"] == "Up"
    assert snapshot["directions"]["vvix"] == "Up"
    assert snapshot["directions"]["vix1d"] == "Up"
    assert snapshot["monitor"]["gex"]["samples"] == 4
    assert snapshot["quality"]["smooth_depth"] == 3


def test_level_challenger_must_hold_for_three_cycles() -> None:
    locked, pending = _apply_level_lock(
        [6100.0],
        {},
        [6110.0, 6100.0],
        6000.0,
        "resistance",
    )
    assert locked == [6100.0, 6110.0]
    locked, pending = _apply_level_lock(
        locked,
        pending,
        [6110.0, 6100.0],
        6000.0,
        "resistance",
    )
    assert locked == [6100.0, 6110.0]
    locked, pending = _apply_level_lock(
        locked,
        pending,
        [6110.0, 6100.0],
        6000.0,
        "resistance",
    )
    assert locked == [6110.0, 6100.0]
    assert pending == {}


def test_theta_index_client_reads_observed_price_and_marks_staleness() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/index/snapshot/price"
        assert request.url.params["symbol"] == "VIX"
        return httpx.Response(
            200,
            json=[
                {
                    "timestamp": "2026-07-26T09:59:00-04:00",
                    "symbol": "VIX",
                    "price": 17.25,
                }
            ],
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = ThetaIndexClient(
        "http://theta.test/v3",
        max_age_seconds=30,
        client=http_client,
    )
    result = client.fetch(
        "VIX",
        now=datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc),
    )

    assert result["value"] == 17.25
    assert result["age_seconds"] == 60
    assert result["status"] == "stale"
    http_client.close()


def test_service_one_shot_writes_atomic_snapshot_and_state(tmp_path: Path) -> None:
    data_dir = tmp_path / "json_data"
    data_dir.mkdir()
    old_path = data_dir / "SPX_0dte_ExposureData_20260726_095900.json"
    new_path = data_dir / "SPX_0dte_ExposureData_20260726_100000.json"
    old_path.write_text(json.dumps(tasty_fixture()), encoding="utf-8")
    new_path.write_text(json.dumps(tasty_fixture()), encoding="utf-8")

    assert find_latest_tastytrade_json(data_dir) == new_path

    output = tmp_path / "runtime" / "latest.json"
    state = tmp_path / "runtime" / "state.json"
    service = KingNodeService(
        tasty_data_dir=data_dir,
        output_path=output,
        state_path=state,
        reference_path=None,
        thetadata_url="http://theta.invalid/v3",
        theta_enabled=False,
        tasty_max_age_seconds=60,
    )
    try:
        snapshot = service.run_once(
            now=datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
        )
    finally:
        service.close()

    assert snapshot["status"] == "degraded"
    assert output.is_file()
    assert state.is_file()
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["levels"]["raw_gamma"]["strike"] == snapshot["levels"]["raw_gamma"]["strike"]
    assert list(output.parent.glob("*.tmp")) == []
