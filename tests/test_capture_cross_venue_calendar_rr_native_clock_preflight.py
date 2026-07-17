from __future__ import annotations

from pathlib import Path
import json

import pandas as pd
import pytest

import neural.jepa.capture_cross_venue_calendar_rr_native_clock_preflight as mod


def spec(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "capture_id": "capture",
        "ticker": "SPY",
        "trade_date": "20240102",
        "role": "front",
        "expiration": "20240102",
        "greeks_path": "greeks.parquet",
        "greeks_sha256": "g",
        "iv_path": "iv.parquet",
        "iv_sha256": "i",
    }
    row.update(overrides)
    return row


def response_rows(*, revised: bool = False, extra: bool = False) -> dict:
    blocks = []
    for right, strike in (("CALL", 470.0), ("PUT", 469.0)):
        data = []
        for clock in ("10:30:00.000", "10:35:00.000"):
            data.append(
                {
                    "timestamp": f"2024-01-02 {clock}",
                    "bid": 1.1 if revised and right == "CALL" else 1.0,
                    "ask": 1.2,
                    "bid_size": 10,
                    "ask_size": 12,
                }
            )
        blocks.append(
            {
                "contract": {
                    "symbol": "SPY",
                    "expiration": "20240102",
                    "strike": strike,
                    "right": right,
                },
                "data": data,
            }
        )
    if extra:
        blocks.append(
            {
                "contract": {
                    "symbol": "SPY",
                    "expiration": "20240102",
                    "strike": 471.0,
                    "right": "CALL",
                },
                "data": [
                    {
                        "timestamp": "2024-01-02 10:30:00.000",
                        "bid": 0.5,
                        "ask": 0.6,
                        "bid_size": 1,
                        "ask_size": 2,
                    }
                ],
            }
        )
    return {"response": blocks}


def vintage_frame() -> pd.DataFrame:
    rows = []
    for right, strike in (("C", 470.0), ("P", 469.0)):
        for clock in ("10:30:00", "10:35:00"):
            rows.append(
                {
                    "symbol": "SPY",
                    "expiration": "20240102",
                    "trade_date": "20240102",
                    "timestamp": pd.Timestamp(f"2024-01-02 {clock}"),
                    "strike": strike,
                    "right": right,
                    "bid": 1.0,
                    "ask": 1.2,
                }
            )
    return pd.DataFrame(rows)


def test_real_frozen_sample_has_12_sessions_and_24_captures() -> None:
    specs = mod.discover_frozen_specs()
    assert len(specs) == 24
    assert specs[["ticker", "trade_date"]].drop_duplicates().shape[0] == 12
    assert set(specs["role"]) == {"front", "back"}
    assert not specs["trade_date"].str.startswith("2026").any()


def test_request_is_exact_six_minute_front_or_back() -> None:
    params = mod.request_params(spec(expiration="20240105", role="back"))
    assert params == {
        "symbol": "SPY",
        "expiration": "20240105",
        "date": "20240102",
        "strike": "*",
        "right": "both",
        "interval": "1m",
        "format": "json",
        "start_time": "10:30:00",
        "end_time": "10:35:00",
    }


def test_normalize_quote_response_preserves_exact_identity() -> None:
    frame = mod.normalize_quote_response(response_rows(), spec())
    assert len(frame) == 4
    assert set(frame["timestamp"].dt.strftime("%H:%M:%S")) == {
        "10:30:00",
        "10:35:00",
    }
    assert set(frame["right"]) == {"C", "P"}
    bad = response_rows()
    bad["response"][0]["contract"]["expiration"] = "20240105"
    with pytest.raises(AssertionError, match="invalid native quote"):
        mod.normalize_quote_response(bad, spec())


def test_read_vintage_targets_uses_underlying_clock_only_as_unproven_key(
    tmp_path: Path,
) -> None:
    rows = []
    for right, strike in (("CALL", 470.0), ("PUT", 469.0)):
        for clock in ("10:30:00.000", "10:35:00.000", "10:36:00.000"):
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
    path = tmp_path / "greeks.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)
    frame = mod.read_vintage_targets(path, spec(), "greeks")
    assert len(frame) == 4
    assert "underlying_timestamp" not in frame.columns
    assert set(frame["timestamp"].dt.strftime("%H:%M:%S")) == {
        "10:30:00",
        "10:35:00",
    }


def test_crosscheck_requires_coverage_but_archives_provider_extras() -> None:
    quotes = mod.normalize_quote_response(
        response_rows(revised=True, extra=True), spec()
    )
    vintage = vintage_frame()
    audit = mod.crosscheck_vintage(quotes, vintage, vintage.copy())
    assert audit["missing_vintage_key_rows"] == 0
    assert audit["native_extra_target_key_rows"] == 1
    assert audit["revised_bid_ask_rows"] == 2
    missing = quotes[
        ~((quotes["right"] == "P") & (quotes["timestamp"].dt.minute == 35))
    ]
    with pytest.raises(AssertionError, match="misses 1 vintage"):
        mod.crosscheck_vintage(missing, vintage, vintage.copy())


def test_crosscheck_rejects_greek_iv_key_drift() -> None:
    quotes = mod.normalize_quote_response(response_rows(), spec())
    greeks = vintage_frame()
    iv = greeks.iloc[:-1].copy()
    with pytest.raises(AssertionError, match="key sets differ"):
        mod.crosscheck_vintage(quotes, greeks, iv)


def test_cost_projection_uses_full_3006_capture_universe() -> None:
    index = pd.DataFrame(
        {
            "rows": [100] * mod.EXPECTED_CAPTURES,
            "raw_bytes": [1_000] * mod.EXPECTED_CAPTURES,
            "parquet_bytes": [500] * mod.EXPECTED_CAPTURES,
        }
    )
    cost = mod.projected_cost(index)
    assert cost["full_sessions"] == 1_503
    assert cost["full_captures"] == 3_006
    assert cost["projected_rows"] == 300_600
    assert cost["cost_gate_pass"]


def test_source_provenance_rejects_unfrozen_remote() -> None:
    with pytest.raises(AssertionError, match="frozen local or exact remote"):
        mod.source_provenance(
            "http://example.com:25503/v3",
            terminal_jar=None,
            timeout=1.0,
        )


def test_terminal_status_shapes() -> None:
    assert mod.terminal_status_value(b"CONNECTED") == "CONNECTED"
    assert mod.terminal_status_value(b'{"status":"connected"}') == "CONNECTED"


def test_capture_base_hash_is_pinned_to_original_committed_code() -> None:
    hashes = mod.committed_blob_hashes(mod.CAPTURE_BASE_COMMIT, mod.CODE_CLOSURE)
    assert (
        hashes["neural/jepa/capture_cross_venue_calendar_rr_native_clock_preflight.py"]
        == "97d0a166e1d65f27cd1f044b0b5d402a3f9d8e5d80826760c56ee83b9d79dba7"
    )


def test_offline_validator_rebuilds_raw_and_vintage_without_network(
    tmp_path: Path,
) -> None:
    source = vintage_frame().rename(columns={"timestamp": "underlying_timestamp"})
    source["underlying_timestamp"] = source["underlying_timestamp"].dt.strftime(
        "%Y-%m-%dT%H:%M:%S.000"
    )
    greek_path = tmp_path / "greeks.parquet"
    iv_path = tmp_path / "iv.parquet"
    source.to_parquet(greek_path, index=False)
    source.to_parquet(iv_path, index=False)
    capture_spec = spec(
        greeks_path=str(greek_path),
        greeks_sha256=mod.sha256_file(greek_path),
        iv_path=str(iv_path),
        iv_sha256=mod.sha256_file(iv_path),
    )
    staging = tmp_path / "output.staging"
    directory = staging / "SPY" / "20240102" / "front"
    directory.mkdir(parents=True)
    raw = mod.canonical_bytes(response_rows())
    raw_path = directory / "response.json"
    parquet_path = directory / "quotes.parquet"
    raw_path.write_bytes(raw)
    quotes = mod.normalize_quote_response(json.loads(raw), capture_spec)
    quotes.to_parquet(parquet_path, index=False)
    greeks = mod.read_vintage_targets(greek_path, capture_spec, "greeks")
    iv = mod.read_vintage_targets(iv_path, capture_spec, "iv")
    audit = mod.crosscheck_vintage(quotes, greeks, iv)
    runtime = {
        "lock_sha256": "lock",
        "environment_sha256": "environment",
    }
    code_hashes = {"capture.py": "hash"}
    manifest = {
        "schema": "cross_venue_calendar_rr_native_clock_capture_v1",
        "status": "PASS_NATIVE_CLOCK_CAPTURE",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "capture_id": "capture",
        "ticker": "SPY",
        "trade_date": "20240102",
        "role": "front",
        "expiration": "20240102",
        "request_params": mod.request_params(capture_spec),
        "endpoint": mod.ENDPOINT,
        "source_provenance": {"kind": "test"},
        "greeks_path": str(greek_path),
        "greeks_sha256": mod.sha256_file(greek_path),
        "iv_path": str(iv_path),
        "iv_sha256": mod.sha256_file(iv_path),
        "raw_sha256": mod.sha256_file(raw_path),
        "parquet_sha256": mod.sha256_file(parquet_path),
        "rows": len(quotes),
        "runtime_lock_sha256": "lock",
        "runtime_environment_sha256": "environment",
        "code_hashes": code_hashes,
        **audit,
    }
    manifest_path = directory / "manifest.json"
    manifest_path.write_bytes(mod.canonical_bytes(manifest))
    row = mod.validate_existing_capture(
        capture_spec,
        staging=staging,
        capture_code_hashes=code_hashes,
        runtime=runtime,
    )
    assert row["rows"] == 4
    assert row["revised_bid_ask_rows"] == 0
