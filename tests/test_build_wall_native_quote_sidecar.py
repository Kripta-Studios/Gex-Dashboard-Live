import json
import hashlib
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa.build_wall_native_quote_sidecar import (
    discover_fallback_sessions, download_session, normalize_quotes,
    research_end_time, validate_session,
)


def response(day="20240102", timestamp="2024-01-02 10:30:00"):
    return {"response": [{"contract": {"symbol": "SPY", "expiration": day, "strike": 470.0, "right": "C"}, "data": [{
        "timestamp": timestamp, "bid": 1.0, "ask": 1.1, "bid_size": 10, "ask_size": 12,
    }]}]}


def write_greeks(path: Path):
    pd.DataFrame([{
        "symbol": "SPY", "expiration": "20240102", "strike": 470.0, "right": "C",
        "timestamp": "2024-01-02 10:30:00", "underlying_timestamp": "2024-01-02 10:30:00",
        "bid": 1.0, "ask": 1.1,
    }]).to_parquet(path, index=False)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.content = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.status_code = 200
        self.headers = {"content-type": "application/json"}
    def raise_for_status(self): return None
    def json(self): return self.payload


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


def test_normalization_rejects_nonminute_duplicate_and_2026():
    assert len(normalize_quotes(response(), "SPY", "20240102")) == 1
    with pytest.raises(AssertionError, match="minute"):
        normalize_quotes(response(timestamp="2024-01-02 10:30:01"), "SPY", "20240102")
    duplicate = response(); duplicate["response"].append(duplicate["response"][0])
    with pytest.raises(AssertionError, match="duplicate"):
        normalize_quotes(duplicate, "SPY", "20240102")
    with pytest.raises(ValueError, match="pre-2026"):
        normalize_quotes(response(day="20260102"), "SPY", "20260102")


def test_download_is_immutable_and_validate_detects_raw_tamper(tmp_path):
    greeks = tmp_path / "greeks.parquet"; write_greeks(greeks)
    jar = tmp_path / "ThetaTerminal.jar"; jar.write_bytes(b"frozen-terminal")
    calls = []
    def requester(url, params, headers, timeout):
        calls.append((url, params, headers, timeout)); return FakeResponse(response())
    manifest = download_session(ticker="SPY", trade_date="20240102", greeks_path=greeks,
                                output_root=tmp_path / "out", base_url="http://127.0.0.1:25503/v3",
                                terminal_jar=jar, start_time="10:30:00", end_time="10:30:00",
                                requester=requester, process_evidence_provider=fake_process_evidence)
    session = tmp_path / "out" / "SPY" / "20240102"
    assert manifest["shared_exact_rows"] == 1
    assert calls[0][1]["interval"] == "1m" and calls[0][1]["strike"] == "*"
    assert calls[0][1]["right"] == "both" and calls[0][1]["expiration"] == "20240102"
    assert calls[0][2] == {"Accept-Encoding": "identity"}
    assert manifest["key_set_exact"] is True and manifest["timestamp_bid_ask_exact"] is True
    assert len(manifest["terminal_jar_sha256"]) == 64
    validate_session(session, greeks)
    with pytest.raises(FileExistsError):
        download_session(ticker="SPY", trade_date="20240102", greeks_path=greeks,
                         output_root=tmp_path / "out", base_url="http://127.0.0.1:25503/v3", terminal_jar=jar,
                         start_time="10:30:00", end_time="10:30:00", requester=requester,
                         process_evidence_provider=fake_process_evidence)
    (session / "quote_response.json").write_text(json.dumps({"response": []}), encoding="utf-8")
    with pytest.raises(AssertionError, match="hash mismatch"):
        validate_session(session, greeks)


def test_crosscheck_rejects_bid_mismatch(tmp_path):
    greeks = tmp_path / "greeks.parquet"; write_greeks(greeks)
    jar = tmp_path / "ThetaTerminal.jar"; jar.write_bytes(b"frozen-terminal")
    frame = pd.read_parquet(greeks); frame.loc[0, "bid"] = 0.99; frame.to_parquet(greeks, index=False)
    with pytest.raises(AssertionError, match="mismatch"):
        download_session(ticker="SPY", trade_date="20240102", greeks_path=greeks,
                         output_root=tmp_path / "out", base_url="http://127.0.0.1:25503/v3", terminal_jar=jar,
                         start_time="10:30:00", end_time="10:30:00",
                         requester=lambda *a, **k: FakeResponse(response()),
                         process_evidence_provider=fake_process_evidence)


def test_crosscheck_requires_full_exact_key_set_and_native_clock_equality(tmp_path):
    greeks = tmp_path / "greeks.parquet"; write_greeks(greeks)
    jar = tmp_path / "ThetaTerminal.jar"; jar.write_bytes(b"frozen-terminal")
    frame = pd.read_parquet(greeks)
    extra = frame.copy(); extra["strike"] = 471.0
    pd.concat([frame, extra], ignore_index=True).to_parquet(greeks, index=False)
    with pytest.raises(AssertionError, match="key-set mismatch"):
        download_session(
            ticker="SPY", trade_date="20240102", greeks_path=greeks,
            output_root=tmp_path / "out", base_url="http://127.0.0.1:25503/v3", terminal_jar=jar,
            start_time="10:30:00", end_time="10:30:00",
            requester=lambda *a, **k: FakeResponse(response()),
            process_evidence_provider=fake_process_evidence,
        )
    native_mismatch = pd.read_parquet(greeks)
    native_mismatch["underlying_timestamp"] = "2024-01-02 10:29:00"
    native_mismatch.to_parquet(greeks, index=False)
    with pytest.raises(AssertionError, match="stored native Greek timestamp differs"):
        download_session(
            ticker="SPY", trade_date="20240102", greeks_path=greeks,
            output_root=tmp_path / "out2", base_url="http://127.0.0.1:25503/v3", terminal_jar=jar,
            start_time="10:30:00", end_time="10:30:00",
            requester=lambda *a, **k: FakeResponse(response()),
            process_evidence_provider=fake_process_evidence,
        )


def test_fallback_discovery_and_schedule_are_outcome_free(tmp_path):
    native = tmp_path / "native.parquet"
    fallback = tmp_path / "fallback.parquet"
    write_greeks(native)
    pd.read_parquet(native).drop(columns=["timestamp"]).to_parquet(fallback, index=False)
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {
                "ticker": "SPY", "trade_date": "20240102", "expiration": "20240102",
                "dte_days": 0, "expiry_mode": "zero_dte", "has_greeks": True,
                "greeks_path": str(native),
            },
            {
                "ticker": "QQQ", "trade_date": "20240103", "expiration": "20240103",
                "dte_days": 0, "expiry_mode": "zero_dte", "has_greeks": True,
                "greeks_path": str(fallback),
            },
        ]
    ).to_csv(manifest, index=False)
    discovered = discover_fallback_sessions(manifest, require_canonical_hash=False)
    assert discovered[["ticker", "trade_date"]].to_dict("records") == [
        {"ticker": "QQQ", "trade_date": "20240103"}
    ]
    assert research_end_time("SPY", "20240703") == "12:54:00"
    assert research_end_time("SPY", "20240103") == "14:29:00"


def test_authoritative_capture_rejects_remote_terminal(tmp_path):
    greeks = tmp_path / "greeks.parquet"; write_greeks(greeks)
    jar = tmp_path / "ThetaTerminal.jar"; jar.write_bytes(b"frozen-terminal")
    with pytest.raises(AssertionError, match="local frozen"):
        download_session(
            ticker="SPY", trade_date="20240102", greeks_path=greeks,
            output_root=tmp_path / "out", base_url="http://example.com/v3", terminal_jar=jar,
            start_time="10:30:00", end_time="10:30:00",
            requester=lambda *a, **k: FakeResponse(response()),
        )
