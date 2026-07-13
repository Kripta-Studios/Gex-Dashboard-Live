from __future__ import annotations

import pandas as pd
import pyarrow as pa
import pytest

import neural.jepa.capture_h_ibqdyn1_full as mod
import neural.jepa.seal_h_ibqdyn1_full_capture_v1r1 as seal_mod


def test_candidate_csv_is_deterministic_and_outcome_free() -> None:
    contracts = pd.DataFrame(
        [
            {
                "contract_id": "c1",
                "event_id": "e1",
                "ticker": "SPY",
                "trade_date": "20240102",
                "decision_dt": pd.Timestamp("2024-01-02 10:35:00"),
                "minute": 635,
                "nearest_level_name": "ib_low",
                "bucket": "d35",
                "right": "CALL",
                "strike": 472.0,
            }
        ]
    )
    first = mod.candidate_csv(contracts)
    second = mod.candidate_csv(contracts.copy())
    assert first == second
    assert "2024-01-02T10:35:00" in first
    assert not any(token in first for token in ("future", "opt_win", "exit_ret"))


class _NoDataResponse:
    status_code = 472
    content = seal_mod.NO_DATA_BODY
    headers = {"Date": "Mon, 13 Jul 2026 12:00:00 GMT"}


def _no_data_contract() -> dict[str, object]:
    contract_id = "311e42908cc0dc01befb5660"
    return {
        "contract_id": contract_id,
        **seal_mod.EXPECTED_NO_DATA_CONTRACTS[contract_id],
        "nearest_level_name": "ib_low",
        "bucket": "d35",
    }


def test_materialize_http472_preserves_raw_and_empty_schema(tmp_path) -> None:
    contract = _no_data_contract()
    schema = pa.schema([(column, pa.string()) for column in seal_mod.OUTPUT_COLUMNS])
    provenance = {
        "kind": "USER_SUPPLIED_REMOTE_THETA_TERMINAL",
        "base_url": "http://91.99.90.39:25503/v3",
        "status_endpoint": "/terminal/mdds/status",
        "status_value": "CONNECTED",
        "historical_provenance": "CONDITIONAL_REMOTE_TERMINAL_RECONSTRUCTION",
        "live_parity": "BLOCKED",
    }
    runtime = {
        "lock_sha256": "a" * 64,
        "environment_sha256": "b" * 64,
    }
    calls = []

    def requester(*args, **kwargs):
        calls.append((args, kwargs))
        return _NoDataResponse()

    row = seal_mod.materialize_no_data_contract(
        contract,
        root=tmp_path,
        base_url=provenance["base_url"],
        provenance=provenance,
        sealer_code_hashes={"sealer.py": "c" * 64},
        runtime=runtime,
        reference_schema=schema,
        timeout=1.0,
        requester=requester,
    )
    assert len(calls) == 3
    assert row["capture_kind"] == "HTTP_472_NO_DATA"
    assert row["rows"] == 0
    assert open(row["raw_path"], "rb").read() == seal_mod.NO_DATA_BODY
    assert pd.read_parquet(row["parquet_path"]).empty


def test_unapproved_missing_contract_is_rejected() -> None:
    contract = _no_data_contract()
    contract["strike"] = 420.0
    with pytest.raises(AssertionError, match="unapproved"):
        seal_mod.assert_expected_no_data_contract(contract)
