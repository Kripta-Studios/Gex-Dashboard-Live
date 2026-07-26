from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

import neural.jepa.audit_external_opra_source_intake_gate as auditor
import neural.jepa.build_external_opra_source_intake_gate as builder
import neural.jepa.capture_external_opra_source_intake as capture
import neural.jepa.external_opra_source_intake_common as common

NEW_YORK = ZoneInfo("America/New_York")
SESSIONS = ("20260727", "20260728", "20260729", "20260730", "20260731")


def option_ticker(sensor: str, session: str) -> str:
    return f"O:{sensor}{session[2:]}C00500000"


def timestamp_ms(session: str, milliseconds: int) -> int:
    day = datetime.strptime(session, "%Y%m%d").date()
    value = datetime(
        day.year,
        day.month,
        day.day,
        9,
        30,
        0,
        milliseconds * 1000,
        tzinfo=NEW_YORK,
    )
    return int(value.timestamp() * 1000)


def reference(sensor: str, session: str) -> dict[str, Any]:
    return {
        "ticker": option_ticker(sensor, session),
        "underlying_ticker": sensor,
        "expiration_date": datetime.strptime(session, "%Y%m%d").date().isoformat(),
        "contract_type": "call",
        "strike_price": 500,
    }


def live_events(session: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sensor in common.SENSORS:
        ticker = option_ticker(sensor, session)
        rows.extend(
            [
                {
                    "arrival_timestamp_utc": datetime.fromtimestamp(
                        timestamp_ms(session, 110) / 1000, timezone.utc
                    ).isoformat(),
                    "payload": {
                        "ev": "Q",
                        "sym": ticker,
                        "t": timestamp_ms(session, 100),
                        "q": 1,
                        "bp": 1.0,
                        "ap": 1.2,
                        "bs": 10,
                        "as": 12,
                        "bx": 1,
                        "ax": 2,
                        "c": [],
                    },
                },
                {
                    "arrival_timestamp_utc": datetime.fromtimestamp(
                        timestamp_ms(session, 210) / 1000, timezone.utc
                    ).isoformat(),
                    "payload": {
                        "ev": "T",
                        "sym": ticker,
                        "t": timestamp_ms(session, 200),
                        "q": 1,
                        "p": 1.2,
                        "s": 3,
                        "x": 2,
                        "c": [12],
                    },
                },
            ]
        )
    return rows


def rest_event_pages(
    sensor: str, session: str, *, correction: int = 0
) -> dict[str, dict[str, Any]]:
    quote_ms = timestamp_ms(session, 100)
    trade_ms = timestamp_ms(session, 200)
    return {
        "quote": {
            "results": [
                {
                    "sip_timestamp": quote_ms * 1_000_000 + 123_456,
                    "participant_timestamp": quote_ms * 1_000_000,
                    "sequence_number": 1,
                    "bid_price": 1.0,
                    "ask_price": 1.2,
                    "bid_size": 10,
                    "ask_size": 12,
                    "bid_exchange": 1,
                    "ask_exchange": 2,
                    "conditions": [],
                }
            ]
        },
        "trade": {
            "results": [
                {
                    "sip_timestamp": trade_ms * 1_000_000 + 999_999,
                    "participant_timestamp": trade_ms * 1_000_000,
                    "sequence_number": 1,
                    "price": 1.2,
                    "size": 3,
                    "exchange": 2,
                    "conditions": [12],
                    "correction": correction,
                }
            ]
        },
    }


def write_page(directory: Path, payload: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    common.write_json(directory / "request.json", {"fixture": True})
    common.write_json(directory / "state.json", {"complete": True, "pages_completed": 1})
    common.write_json(directory / "page_000001.json", payload)


def seal_source(
    directory: Path, status: str, session: str, universe_sha: str | None = None
) -> None:
    files = sorted(path for path in directory.rglob("*") if path.is_file())
    index = [
        {
            "path": path.relative_to(directory).as_posix(),
            "size": path.stat().st_size,
            "sha256": common.sha256_file(path),
        }
        for path in files
    ]
    manifest = {
        "status": status,
        "session": session,
        "outcome_accessed": False,
        "predeclaration_sha256": builder.EXPECTED_PREDECLARATION_SHA256,
        "code_hashes": {"x": "y"},
        "source_index": index,
        "source_index_sha256": common.sha256_bytes(
            common.canonical_json_bytes(index)
        ),
    }
    if status == "SHADOW_SOURCE_CAPTURED_OUTCOME_FREE":
        manifest["live"] = {
            "acknowledged_at_utc": datetime(
                int(session[:4]),
                int(session[4:6]),
                int(session[6:8]),
                9,
                29,
                10,
                tzinfo=NEW_YORK,
            )
            .astimezone(timezone.utc)
            .isoformat(),
            "contracts": 2,
        }
    if universe_sha is not None:
        manifest["preflight_universe_sha256"] = universe_sha
    common.write_json(directory / "manifest.json", manifest)


def write_capture_session(
    root: Path,
    session: str,
    *,
    correction: int = 0,
    universe_sha: str | None = None,
) -> None:
    shadow = root / "shadow" / session
    rest = root / "rest" / session
    for sensor in common.SENSORS:
        payload = {"results": [reference(sensor, session)]}
        write_page(shadow / "reference" / sensor, payload)
        write_page(rest / "reference" / sensor, payload)
        ticker = option_ticker(sensor, session).replace(":", "_")
        pages = rest_event_pages(sensor, session, correction=correction)
        write_page(rest / "contracts" / ticker / "quote", pages["quote"])
        write_page(rest / "contracts" / ticker / "trade", pages["trade"])
    common.write_jsonl(shadow / "events.jsonl", live_events(session))
    common.write_jsonl(shadow / "control.jsonl", [{"status": "success"}])
    seal_source(
        shadow,
        "SHADOW_SOURCE_CAPTURED_OUTCOME_FREE",
        session,
        universe_sha,
    )
    seal_source(
        rest,
        "REST_SOURCE_CAPTURED_OUTCOME_FREE",
        session,
        universe_sha,
    )


def test_normalization_truncates_rest_ns_and_requires_strict_predecessor() -> None:
    session = SESSIONS[0]
    ticker = option_ticker("QQQ", session)
    pages = rest_event_pages("QQQ", session)
    quote = common.normalize_rest_event(
        pages["quote"]["results"][0],
        event_kind="quote",
        contract_ticker=ticker,
        session=session,
    )
    trade = common.normalize_rest_event(
        pages["trade"]["results"][0],
        event_kind="trade",
        contract_ticker=ticker,
        session=session,
    )
    assert quote["sip_timestamp_ms"] == timestamp_ms(session, 100)
    assert trade["sip_timestamp_ms"] == timestamp_ms(session, 200)
    assert common.strict_predecessor_audit([quote, trade]) == {
        "trades": 1,
        "with_strict_predecessor": 1,
        "without_strict_predecessor": 0,
        "same_millisecond_ties": 0,
    }
    tied = dict(quote)
    tied["sip_timestamp_ms"] = trade["sip_timestamp_ms"]
    assert common.strict_predecessor_audit([tied, trade]) == {
        "trades": 1,
        "with_strict_predecessor": 0,
        "without_strict_predecessor": 1,
        "same_millisecond_ties": 1,
    }


def test_paginated_capture_resumes_and_never_persists_api_key(tmp_path: Path) -> None:
    api_key = "secret-key-that-must-not-be-persisted"

    class Response:
        def __init__(self, payload: dict[str, Any]) -> None:
            self.content = json.dumps(payload).encode()

        def raise_for_status(self) -> None:
            return None

    class Client:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, *_args: Any, **_kwargs: Any) -> Response:
            self.calls += 1
            if self.calls == 1:
                return Response(
                    {
                        "results": [{"value": 1}],
                        "next_url": "https://api.massive.test/next?cursor=two",
                    }
                )
            return Response({"results": [{"value": 2}]})

    client = Client()
    output = tmp_path / "pages"
    state = capture.paginated_get(
        client=client,
        url="https://api.massive.test/start",
        params={"limit": 1000},
        output=output,
        api_key=api_key,
        timeout=1,
    )
    assert state == {"complete": True, "pages_completed": 2, "next_url": ""}
    assert client.calls == 2
    assert api_key not in b"".join(path.read_bytes() for path in output.iterdir()).decode()
    capture.paginated_get(
        client=client,
        url="https://api.massive.test/start",
        params={"limit": 1000},
        output=output,
        api_key=api_key,
        timeout=1,
    )
    assert client.calls == 2


def test_shadow_requires_premarket_ack_and_writes_no_credential(
    tmp_path: Path,
) -> None:
    session = SESSIONS[0]
    day = datetime.strptime(session, "%Y%m%d").date()
    times = iter(
        [
            datetime(day.year, day.month, day.day, 9, 29, tzinfo=NEW_YORK),
            datetime(day.year, day.month, day.day, 9, 29, 10, tzinfo=NEW_YORK),
            datetime(day.year, day.month, day.day, 10, 35, 1, tzinfo=NEW_YORK),
        ]
    )

    class Socket:
        def __init__(self) -> None:
            self.sent: list[str] = []
            self.received = iter(
                [
                    json.dumps(
                        [
                            {
                                "ev": "status",
                                "status": "auth_success",
                                "message": "authenticated",
                            }
                        ]
                    ),
                    json.dumps(
                        [
                            {
                                "ev": "status",
                                "status": "success",
                                "message": "subscribed to requested channels",
                            }
                        ]
                    ),
                ]
            )

        def send(self, value: str) -> None:
            self.sent.append(value)

        def recv(self) -> str:
            return next(self.received)

    socket = Socket()
    api_key = "live-secret-never-written"
    result = capture.capture_shadow_messages(
        websocket=socket,
        contracts=[option_ticker(sensor, session) for sensor in common.SENSORS],
        session=session,
        output=tmp_path,
        api_key=api_key,
        now_utc=lambda: next(times),
        monotonic=lambda: 0.0,
    )
    assert result["contracts"] == 2
    assert result["events"] == result["outside_window_events"] == 0
    assert api_key in "".join(socket.sent)
    assert api_key not in b"".join(path.read_bytes() for path in tmp_path.iterdir()).decode()


def test_session_parity_passes_and_nonzero_correction_fails_closed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "capture"
    write_capture_session(root, SESSIONS[0])
    summary, live, rest = builder.compare_session(
        capture_root=root,
        session=SESSIONS[0],
        correction_contract_present=True,
    )
    assert summary["status"] == "PASS_SESSION_HISTORICAL_LIVE_PARITY"
    assert len(live) == len(rest) == 4
    failing = tmp_path / "failing"
    write_capture_session(failing, SESSIONS[0], correction=1)
    failed, _, _ = builder.compare_session(
        capture_root=failing,
        session=SESSIONS[0],
        correction_contract_present=True,
    )
    assert failed["status"] == "FAILED_SESSION_HISTORICAL_LIVE_PARITY"
    assert failed["gates"]["rest_corrections_zero_only"] is False
    assert failed["gates"]["event_multiset_equal"] is False


def test_full_five_session_gate_and_independent_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    universe = tmp_path / "universe.json"
    common.write_json(
        universe,
        {
            "contract": "EXTERNAL_OPRA_SOURCE_INTAKE_PREFLIGHT_V1",
            "created_at_utc": "2026-07-26T08:00:00+00:00",
            "sessions": list(SESSIONS),
            "outcome_accessed": False,
            "market_value_accessed": False,
        },
    )
    universe_sha = common.sha256_file(universe)
    capture_root = tmp_path / "capture"
    for session in SESSIONS:
        write_capture_session(capture_root, session, universe_sha=universe_sha)
    evidence = tmp_path / "massive-correction-evidence.html"
    evidence.write_text("official-provider-correction-semantics", encoding="utf-8")
    correction_manifest = tmp_path / "correction_manifest.json"
    common.write_json(
        correction_manifest,
        {
            "provider": "Massive",
            "scope": "OPTIONS_TRADES_WEBSOCKET_AND_REST",
            "status": "PROVIDER_CERTIFIED",
            "source_url": "https://massive.com/docs/example",
            "retrieved_at_utc": "2026-07-26T08:00:00+00:00",
            "historical_correction_field": "correction",
            "live_correction_semantics": "EXPLICIT_FIELD",
            "evidence_file": evidence.name,
            "evidence_sha256": common.sha256_file(evidence),
        },
    )
    monkeypatch.setattr(builder, "committed_code_state", lambda: ("commit", {"x": "y"}))
    monkeypatch.setattr(builder, "assert_runtime_lock", lambda _path: {"runtime": "test"})
    monkeypatch.setattr(auditor, "committed_code_state", lambda: ("commit", {"x": "y"}))
    monkeypatch.setattr(auditor, "assert_runtime_lock", lambda _path: {"runtime": "test"})
    monkeypatch.setattr(
        builder,
        "_load_committed_universe",
        lambda _path: (list(SESSIONS), universe_sha),
    )
    gate = tmp_path / "gate"
    result = builder.build_gate(
        capture_root=capture_root,
        output=gate,
        universe=universe,
        correction_evidence=correction_manifest,
    )
    assert result["status"] == "PASS_OUTCOME_FREE_EXTERNAL_OPRA_SOURCE_GATE"
    assert result["live_events"] == result["rest_events"] == 20
    audit = auditor.audit_gate(
        capture_root=capture_root,
        gate=gate,
        universe=universe,
        correction_evidence=correction_manifest,
        output=tmp_path / "audit",
    )
    assert audit["status"] == "PASS_INDEPENDENT_EXTERNAL_OPRA_SOURCE_GATE_AUDIT"
    source = Path(auditor.__file__).read_text(encoding="utf-8")
    assert "import neural.jepa.build_external" not in source
    assert "import neural.jepa.external_opra_source_intake_common" not in source


def test_gate_requires_exactly_five_ordered_sessions() -> None:
    assert builder.validate_sessions(SESSIONS) == list(SESSIONS)
    with pytest.raises(AssertionError, match="exactly five"):
        builder.validate_sessions(SESSIONS[:4])
    with pytest.raises(AssertionError, match="exactly five"):
        builder.validate_sessions(reversed(SESSIONS))


def test_universe_freeze_uses_five_consecutive_exchange_sessions(
    tmp_path: Path,
) -> None:
    output = tmp_path / "universe.json"
    value = capture.freeze_preflight_universe(
        start="20260727",
        output=output,
        now_utc=datetime(2026, 7, 26, 8, tzinfo=timezone.utc),
    )
    assert value["sessions"] == list(SESSIONS)
    assert common.validate_preflight_universe(value) == list(SESSIONS)


def test_correction_evidence_rejects_local_note(tmp_path: Path) -> None:
    note = tmp_path / "note.txt"
    note.write_text("I think corrections are equivalent", encoding="utf-8")
    with pytest.raises((AssertionError, json.JSONDecodeError)):
        builder.validate_correction_evidence(note)
