from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import neural.jepa.capture_cross_venue_calendar_rr_native_clock_full as full
import neural.jepa.capture_cross_venue_calendar_rr_native_clock_preflight as pre


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.content = pre.canonical_bytes(payload)
        self.status_code = 200
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        return None


def raw_response() -> dict:
    blocks = []
    for right, strike in (("CALL", 470.0), ("PUT", 469.0)):
        blocks.append(
            {
                "contract": {
                    "symbol": "SPY",
                    "expiration": "20240102",
                    "strike": strike,
                    "right": right,
                },
                "data": [
                    {
                        "timestamp": f"2024-01-02 {clock}.000",
                        "bid": 1.0,
                        "ask": 1.2,
                        "bid_size": 10,
                        "ask_size": 12,
                    }
                    for clock in ("10:30:00", "10:35:00")
                ],
            }
        )
    return {"response": blocks}


def logical_spec(tmp_path: Path) -> dict[str, str]:
    rows = []
    for right, strike in (("CALL", 470.0), ("PUT", 469.0)):
        for clock in ("10:30:00.000", "10:35:00.000"):
            rows.append(
                {
                    "symbol": "SPY",
                    "expiration": "20240102",
                    "trade_date": "20240102",
                    "underlying_timestamp": f"2024-01-02T{clock}",
                    "strike": strike,
                    "right": right,
                    "bid": 1.0,
                    "ask": 1.2,
                }
            )
    greeks = tmp_path / "greeks.parquet"
    iv = tmp_path / "iv.parquet"
    pd.DataFrame(rows).to_parquet(greeks, index=False)
    pd.DataFrame(rows).to_parquet(iv, index=False)
    return {
        "capture_id": "capture",
        "ticker": "SPY",
        "trade_date": "20240102",
        "role": "front",
        "expiration": "20240102",
        "greeks_path": str(greeks),
        "iv_path": str(iv),
    }


def test_real_full_universe_is_exactly_3012_captures() -> None:
    specs, audit = full.discover_full_specs()
    assert len(specs) == 3_012
    assert specs[["ticker", "trade_date"]].drop_duplicates().shape[0] == 1_506
    assert audit["sessions_per_ticker"] == {"QQQ": 502, "SPXW": 502, "SPY": 502}
    assert audit["capture_id_sha256"] == full.EXPECTED_CAPTURE_ID_SHA256
    assert audit["logical_inventory_sha256"] == full.EXPECTED_LOGICAL_INVENTORY_SHA256
    assert not specs["trade_date"].str.startswith("2026").any()


def test_tracked_preflight_evidence_is_pass() -> None:
    seal = full.validate_preflight_evidence()
    assert seal["status"] == "PASS_CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_PREFLIGHT"
    assert seal["missing_vintage_key_rows"] == 0


def test_capture_is_atomic_and_resumes_without_network(tmp_path: Path) -> None:
    spec = logical_spec(tmp_path)
    prepared = full.prepare_spec(spec)
    runtime = {"lock_sha256": "lock", "environment_sha256": "env"}
    code_hashes = {"full.py": "hash"}
    calls = 0

    def requester(*args: object, **kwargs: object) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse(raw_response())

    output = tmp_path / "output"
    row = pre.capture_one(
        prepared,
        staging=output,
        base_url="http://example/v3",
        provenance={"kind": "test"},
        runtime=runtime,
        code_hashes=code_hashes,
        timeout=1.0,
        requester=requester,
    )
    directory = output / "SPY" / "20240102" / "front"
    assert row["rows"] == 4
    assert directory.is_dir()
    assert not directory.with_name("front.staging").exists()
    resumed, was_resumed = full.capture_or_resume(
        spec,
        output=output,
        base_url="http://unreachable/v3",
        provenance={"kind": "test"},
        runtime=runtime,
        code_hashes=code_hashes,
        timeout=1.0,
    )
    assert resumed["rows"] == 4
    assert was_resumed
    assert calls == 1


def test_resume_fails_closed_on_partial_atomic_directory(tmp_path: Path) -> None:
    spec = logical_spec(tmp_path)
    partial = tmp_path / "output" / "SPY" / "20240102" / "front.staging"
    partial.mkdir(parents=True)
    with pytest.raises(AssertionError, match="requires audit"):
        full.capture_or_resume(
            spec,
            output=tmp_path / "output",
            base_url="http://unreachable/v3",
            provenance={"kind": "test"},
            runtime={"lock_sha256": "lock", "environment_sha256": "env"},
            code_hashes={"full.py": "hash"},
            timeout=1.0,
        )


def test_root_contract_is_immutable_across_resume(tmp_path: Path) -> None:
    specs = pd.DataFrame([logical_spec(tmp_path)])
    output = tmp_path / "full"
    payload = {"schema": "test", "universe_sha256": "u"}
    full.initialize_or_validate_root(
        output,
        specs=specs,
        payload=payload,
        status_raw=b"CONNECTED",
    )
    full.initialize_or_validate_root(
        output,
        specs=specs,
        payload=payload,
        status_raw=b"CONNECTED",
    )
    stored = json.loads((output / "_state/capture_contract.json").read_text())
    assert stored["schema"] == "test"
    changed = specs.copy()
    changed.loc[0, "expiration"] = "20240105"
    with pytest.raises(AssertionError, match="resume contract changed"):
        full.initialize_or_validate_root(
            output,
            specs=changed,
            payload=payload,
            status_raw=b"CONNECTED",
        )
