import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa.build_wall_exact_greek_repair_sidecar import (
    DECISION_TIMES,
    ENDPOINT,
    EXPECTED_CONTRACT_KEY_SHA256,
    backfill_exact_greeks,
    contract_key_hash,
    discover_contract_universe,
    download_contract,
    normalize_exact_greeks,
    validate_contract,
    validate_exact_rows_against_sources,
)


DAY = "20221230"


def exact_response(*, ticker="QQQ", strike=264.0, right="C", spot=264.0, bid=1.0, ask=1.05):
    data = []
    for index, time in enumerate(DECISION_TIMES):
        timestamp = f"2022-12-30 {time}"
        data.append(
            {
                "timestamp": timestamp,
                "underlying_timestamp": timestamp,
                "underlying_price": spot + index / 100.0,
                "implied_vol": 0.20 + index / 10000.0,
                "delta": 0.5,
                "theta": -0.01,
                "vega": 0.02,
                "rho": 0.001,
                "bid": bid,
                "ask": ask,
                "iv_error": 0.0,
                "epsilon": 0.0,
                "lambda": 1.0,
            }
        )
    return {
        "response": [
            {
                "contract": {
                    "symbol": ticker,
                    "expiration": DAY,
                    "strike": strike,
                    "right": right,
                },
                "data": data,
            }
        ]
    }


def write_sources(root: Path, *, ticker="QQQ", strike=264.0, right="CALL", bid=1.0, ask=1.05):
    timestamps = [f"2022-12-30 {time}" for time in DECISION_TIMES]
    greek = root / "greeks.parquet"
    pd.DataFrame(
        {
            "symbol": ticker,
            "expiration": DAY,
            "strike": strike,
            "right": right,
            "timestamp": timestamps,
            "underlying_timestamp": timestamps,
            "bid": bid,
            "ask": ask,
        }
    ).to_parquet(greek, index=False)
    oi = root / "oi.parquet"
    pd.DataFrame(
        [{"symbol": ticker, "expiration": DAY, "strike": strike, "right": right, "open_interest": 100}]
    ).to_parquet(oi, index=False)
    underlying = root / "underlying.parquet"
    pd.DataFrame(
        {
            "symbol": ticker,
            "date": DAY,
            "timestamp": timestamps,
            "open": [264.0 + index / 100.0 for index in range(len(timestamps))],
        }
    ).to_parquet(underlying, index=False)
    manifest = root / "manifest.csv"
    manifest.write_text("outcome_free_test_manifest\n", encoding="utf-8")
    return greek, oi, underlying, manifest


class FakeResponse:
    def __init__(self, payload):
        self.content = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.status_code = 200
        self.headers = {"content-type": "application/json"}

    def raise_for_status(self):
        return None


def fake_process_evidence(_base_url, jar):
    jar_path = Path(jar).resolve()
    digest = hashlib.sha256(jar_path.read_bytes()).hexdigest()
    return {
        "process_id": 1,
        "command_line": f"java -jar {jar_path}",
        "executable_path": "java",
        "executable_sha256": "0" * 64,
        "local_address": "127.0.0.1",
        "local_port": 25503,
        "terminal_jar_path": str(jar_path),
        "terminal_jar_sha256": digest,
    }


def test_contract_hash_uses_frozen_short_right_canonicalization():
    frame = pd.DataFrame(
        [
            {"ticker": "SPY", "trade_date": DAY, "strike": 380.0, "right": "PUT"},
            {"ticker": "QQQ", "trade_date": DAY, "strike": 264.0, "right": "CALL"},
        ]
    )
    payload = b"QQQ,20221230,264.000000,C\nSPY,20221230,380.000000,P\n"
    assert contract_key_hash(frame) == hashlib.sha256(payload).hexdigest()


def test_real_frozen_contract_universe_has_predeclared_count_and_hash():
    manifest = Path("tmp/event_option_dataset_execquote_causal1030_202201_202605_v1/filtered_manifest.csv")
    if not manifest.is_file():
        pytest.skip("canonical local source manifest is not present")
    universe = discover_contract_universe(manifest)
    assert universe.groupby("ticker").size().to_dict() == {"QQQ": 285, "SPY": 386}
    assert contract_key_hash(universe) == EXPECTED_CONTRACT_KEY_SHA256


def test_normalize_requires_all_48_exact_native_clock_rows():
    normalized = normalize_exact_greeks(
        exact_response(), ticker="QQQ", trade_date=DAY, strike=264.0, right="CALL"
    )
    assert len(normalized) == 48
    assert normalized["timestamp"].equals(normalized["underlying_timestamp"])
    assert normalized["implied_vol"].gt(0).all()

    missing = exact_response()
    missing["response"][0]["data"].pop()
    with pytest.raises(AssertionError, match="coverage differs from 48"):
        normalize_exact_greeks(missing, ticker="QQQ", trade_date=DAY, strike=264.0, right="C")

    duplicate = exact_response()
    duplicate["response"][0]["data"].append(dict(duplicate["response"][0]["data"][0]))
    with pytest.raises(AssertionError, match="duplicate/non-monotonic"):
        normalize_exact_greeks(duplicate, ticker="QQQ", trade_date=DAY, strike=264.0, right="C")

    shifted_clock = exact_response()
    shifted_clock["response"][0]["data"][0]["underlying_timestamp"] = "2022-12-30 10:34:59"
    with pytest.raises(AssertionError, match="differs from underlying_timestamp"):
        normalize_exact_greeks(shifted_clock, ticker="QQQ", trade_date=DAY, strike=264.0, right="C")

    reversed_rows = exact_response()
    reversed_rows["response"][0]["data"].reverse()
    with pytest.raises(AssertionError, match="non-monotonic"):
        normalize_exact_greeks(reversed_rows, ticker="QQQ", trade_date=DAY, strike=264.0, right="C")


def test_source_validation_hard_fails_spot_and_bid_ask_mismatch(tmp_path):
    greeks, _oi, underlying, _manifest = write_sources(tmp_path)
    exact = normalize_exact_greeks(exact_response(), ticker="QQQ", trade_date=DAY, strike=264.0, right="C")
    audit = validate_exact_rows_against_sources(exact, greeks_path=greeks, underlying_path=underlying)
    assert audit["stored_bid_ask_exact"] is True
    assert audit["max_spot_difference_bps"] == 0.0

    revised = pd.read_parquet(greeks)
    revised.loc[0, "bid"] = 0.99
    revised.to_parquet(greeks, index=False)
    with pytest.raises(AssertionError, match="bid/ask differs"):
        validate_exact_rows_against_sources(exact, greeks_path=greeks, underlying_path=underlying)

    revised.loc[0, "bid"] = 1.0
    revised.to_parquet(greeks, index=False)
    shifted = pd.read_parquet(underlying)
    shifted.loc[0, "open"] = 263.0
    shifted.to_parquet(underlying, index=False)
    with pytest.raises(AssertionError, match=r"derived open\(t\)"):
        validate_exact_rows_against_sources(exact, greeks_path=greeks, underlying_path=underlying)


def test_download_request_raw_provenance_immutable_and_validatable(tmp_path):
    greeks, oi, underlying, source_manifest = write_sources(tmp_path)
    jar = tmp_path / "ThetaTerminal.jar"
    jar.write_bytes(b"frozen-terminal")
    calls = []

    def requester(url, params, headers, timeout):
        calls.append((url, params, headers, timeout))
        return FakeResponse(exact_response())

    result = download_contract(
        ticker="QQQ", trade_date=DAY, strike=264.0, right="CALL",
        greeks_path=greeks, oi_path=oi, underlying_path=underlying,
        source_manifest_path=source_manifest, output_root=tmp_path / "out",
        base_url="http://127.0.0.1:25503/v3", terminal_jar=jar,
        requester=requester, process_evidence_provider=fake_process_evidence,
    )
    assert calls[0][0].endswith(ENDPOINT)
    assert calls[0][1] == {
        "symbol": "QQQ", "expiration": DAY, "strike": "264", "right": "C",
        "date": DAY, "interval": "1s", "format": "json",
    }
    assert calls[0][2] == {"Accept-Encoding": "identity"}
    assert result["rows"] == 48 and result["stored_bid_ask_exact"] is True
    contract_dir = tmp_path / "out" / "QQQ" / DAY / "C_264p000000"
    validate_contract(
        contract_dir, greeks_path=greeks, oi_path=oi, underlying_path=underlying,
        source_manifest_path=source_manifest,
    )
    with pytest.raises(FileExistsError):
        download_contract(
            ticker="QQQ", trade_date=DAY, strike=264.0, right="C",
            greeks_path=greeks, oi_path=oi, underlying_path=underlying,
            source_manifest_path=source_manifest, output_root=tmp_path / "out",
            base_url="http://127.0.0.1:25503/v3", terminal_jar=jar,
            requester=requester, process_evidence_provider=fake_process_evidence,
        )
    (contract_dir / "first_order_response.json").write_bytes(b"{}")
    with pytest.raises(AssertionError, match="hash mismatch"):
        validate_contract(
            contract_dir, greeks_path=greeks, oi_path=oi, underlying_path=underlying,
            source_manifest_path=source_manifest,
        )


def test_download_rejects_contract_without_strictly_positive_stored_oi(tmp_path):
    greeks, oi, underlying, source_manifest = write_sources(tmp_path)
    oi_frame = pd.read_parquet(oi)
    oi_frame["open_interest"] = 0
    oi_frame.to_parquet(oi, index=False)
    jar = tmp_path / "ThetaTerminal.jar"
    jar.write_bytes(b"frozen-terminal")
    with pytest.raises(AssertionError, match="strictly-positive-OI"):
        download_contract(
            ticker="QQQ", trade_date=DAY, strike=264.0, right="C",
            greeks_path=greeks, oi_path=oi, underlying_path=underlying,
            source_manifest_path=source_manifest, output_root=tmp_path / "out",
            base_url="http://127.0.0.1:25503/v3", terminal_jar=jar,
            requester=lambda *args, **kwargs: FakeResponse(exact_response()),
            process_evidence_provider=fake_process_evidence,
        )


def test_remote_capture_and_more_than_four_workers_are_rejected(tmp_path):
    greeks, oi, underlying, source_manifest = write_sources(tmp_path)
    jar = tmp_path / "ThetaTerminal.jar"
    jar.write_bytes(b"frozen-terminal")
    with pytest.raises(AssertionError, match="local frozen"):
        download_contract(
            ticker="QQQ", trade_date=DAY, strike=264.0, right="C",
            greeks_path=greeks, oi_path=oi, underlying_path=underlying,
            source_manifest_path=source_manifest, output_root=tmp_path / "out",
            base_url="http://example.com/v3", terminal_jar=jar,
        )
    with pytest.raises(ValueError, match="1..4"):
        backfill_exact_greeks(
            manifest_path=source_manifest, output_root=tmp_path / "out",
            base_url="http://127.0.0.1:25503/v3", terminal_jar=jar, workers=5,
        )
