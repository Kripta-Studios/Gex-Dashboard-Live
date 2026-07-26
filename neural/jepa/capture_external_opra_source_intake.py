"""Capture Massive OPRA shadow/REST sources under a precommitted source gate.

This module has no economic features or outcome clocks. Network execution
requires an explicit acknowledgement, a committed clean code closure and a
credential supplied only through MASSIVE_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time as time_module
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.external_opra_source_intake_common import (  # noqa: E402
    NEW_YORK,
    SENSORS,
    SUBSCRIPTION_DEADLINE,
    canonical_json_bytes,
    normalize_reference_pages,
    parse_session_date,
    read_json,
    session_bounds,
    session_bounds_ns,
    sha256_bytes,
    sha256_file,
    validate_preflight_universe,
    write_json,
)
from neural.jepa.wall_surface_flow_environment import (  # noqa: E402
    assert_runtime_lock,
)

REST_BASE_URL = "https://api.massive.com"
WEBSOCKET_URL = "wss://socket.massive.com/options"
DEFAULT_OUTPUT = Path("D:/ThetaData/external_opra_source_intake_massive_v1")
DEFAULT_UNIVERSE = PROJECT_ROOT / (
    "research_papers/JEPA/EXTERNAL_OPRA_SOURCE_INTAKE_PREFLIGHT_UNIVERSE.json"
)
PREDECLARATION = PROJECT_ROOT / (
    "research_papers/JEPA/EXTERNAL_OPRA_SOURCE_INTAKE_PREDECLARATION_20260726.md"
)
RUNTIME_LOCK = PROJECT_ROOT / (
    "research_papers/JEPA/requirements-external-opra-source-intake.txt"
)
EXPECTED_PREDECLARATION_SHA256 = (
    "cb6c4aa8a39dc50ae661f3e74856f725f325c3a30121e89a9a5e765705746f92"
)
CODE_CLOSURE = (
    "neural/jepa/external_opra_source_intake_common.py",
    "neural/jepa/capture_external_opra_source_intake.py",
    "neural/jepa/build_external_opra_source_intake_gate.py",
    "neural/jepa/audit_external_opra_source_intake_gate.py",
    "research_papers/JEPA/EXTERNAL_OPRA_SOURCE_INTAKE_PREDECLARATION_20260726.md",
    "research_papers/JEPA/requirements-external-opra-source-intake.txt",
)
NETWORK_ACKNOWLEDGEMENT = "I_AUTHORIZE_THIS_EXTERNAL_SOURCE_PREFLIGHT_CALL"
REFERENCE_PATH = "/v3/reference/options/contracts"
EVENT_PATHS = {
    "trade": "/v3/trades/{ticker}",
    "quote": "/v3/quotes/{ticker}",
}


def committed_code_state(
    paths: tuple[str, ...] = CODE_CLOSURE,
) -> tuple[str, dict[str, str]]:
    if sha256_file(PREDECLARATION) != EXPECTED_PREDECLARATION_SHA256:
        raise AssertionError("external source intake predeclaration hash mismatch")
    hashes: dict[str, str] = {}
    for relative in paths:
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", relative],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if dirty:
            raise AssertionError(f"source intake requires committed code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    origin = subprocess.run(
        ["git", "rev-parse", "origin/main"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != origin or branch != "main":
        raise AssertionError("source intake requires main with HEAD == origin/main")
    return head, hashes


def require_api_key() -> str:
    value = os.environ.get("MASSIVE_API_KEY", "")
    if not value or value.strip() != value or len(value) < 16:
        raise AssertionError("MASSIVE_API_KEY is absent or malformed")
    return value


def freeze_preflight_universe(
    *,
    start: str,
    output: Path,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Freeze five consecutive NYSE sessions without accessing market values."""
    if output.exists():
        raise AssertionError(f"immutable preflight universe exists: {output}")
    start_date = parse_session_date(start)
    created = now_utc or datetime.now(timezone.utc)
    if created.tzinfo is None:
        raise AssertionError("universe freeze timestamp must be timezone-aware")
    if start_date <= created.astimezone(NEW_YORK).date():
        raise AssertionError("preflight start must be a future New York date")
    import pandas_market_calendars as market_calendars

    calendar = market_calendars.get_calendar("NYSE")
    valid = calendar.valid_days(
        start_date=start_date,
        end_date=start_date + timedelta(days=14),
    )
    sessions = [value.strftime("%Y%m%d") for value in valid[:5]]
    if len(sessions) != 5 or sessions[0] != start:
        raise AssertionError("start must be the next intended NYSE session")
    value = {
        "contract": "EXTERNAL_OPRA_SOURCE_INTAKE_PREFLIGHT_V1",
        "created_at_utc": created.astimezone(timezone.utc).isoformat(),
        "sessions": sessions,
        "outcome_accessed": False,
        "market_value_accessed": False,
    }
    validate_preflight_universe(value)
    write_json(output, value)
    return value


def load_committed_universe(path: Path) -> tuple[list[str], str]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise AssertionError("preflight universe must be inside the repository") from exc
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", relative],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise AssertionError("preflight universe must be committed before capture")
    return validate_preflight_universe(read_json(path)), sha256_file(path)


def _url_without_key(value: str) -> str:
    parsed = urlsplit(value)
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in {"apikey", "api_key"}
    ]
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def _atomic_raw_write(path: Path, content: bytes, *, api_key: str) -> None:
    if api_key.encode("utf-8") in content:
        raise AssertionError("provider response contains credential; raw not written")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def paginated_get(
    *,
    client: Any,
    url: str,
    params: Mapping[str, Any],
    output: Path,
    api_key: str,
    timeout: float,
) -> dict[str, Any]:
    """Persist exact provider pages and resume without overwriting stored raw."""
    output.mkdir(parents=True, exist_ok=True)
    request_manifest = output / "request.json"
    sanitized = {
        "url": _url_without_key(url),
        "params": dict(sorted((str(k), v) for k, v in params.items())),
    }
    if request_manifest.exists():
        if read_json(request_manifest) != sanitized:
            raise AssertionError(f"request contract changed while resuming: {output}")
    else:
        write_json(request_manifest, sanitized)

    state_path = output / "state.json"
    state = (
        read_json(state_path)
        if state_path.exists()
        else {"complete": False, "pages_completed": 0, "next_url": url}
    )
    if state.get("complete"):
        return state

    next_url = str(state["next_url"])
    pages_completed = int(state["pages_completed"])
    while next_url:
        number = pages_completed + 1
        page_path = output / f"page_{number:06d}.json"
        if page_path.exists():
            content = page_path.read_bytes()
        else:
            request_params = dict(params) if number == 1 else {}
            request_params["apiKey"] = api_key
            response = client.get(
                next_url,
                params=request_params,
                timeout=timeout,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            content = bytes(response.content)
            _atomic_raw_write(page_path, content, api_key=api_key)
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"invalid provider JSON: {page_path}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise AssertionError(f"provider page lacks results: {page_path}")
        provider_next = payload.get("next_url")
        next_url = _url_without_key(str(provider_next)) if provider_next else ""
        pages_completed = number
        state = {
            "complete": not bool(next_url),
            "pages_completed": pages_completed,
            "next_url": next_url,
        }
        write_json(state_path, state)
    return state


def _read_pages(directory: Path) -> list[dict[str, Any]]:
    files = sorted(directory.glob("page_*.json"))
    if not files or not read_json(directory / "state.json").get("complete"):
        raise AssertionError(f"incomplete paginated source: {directory}")
    pages = [json.loads(path.read_bytes()) for path in files]
    if len(files) != int(read_json(directory / "state.json")["pages_completed"]):
        raise AssertionError(f"page count mismatch: {directory}")
    return pages


def capture_reference(
    *,
    client: Any,
    base_url: str,
    session: str,
    output: Path,
    api_key: str,
    historical: bool,
    timeout: float,
) -> list[dict[str, Any]]:
    iso_date = parse_session_date(session).isoformat()
    for sensor in SENSORS:
        paginated_get(
            client=client,
            url=base_url.rstrip("/") + REFERENCE_PATH,
            params={
                "underlying_ticker": sensor,
                "expiration_date": iso_date,
                "as_of": iso_date,
                "expired": str(historical).lower(),
                "limit": 1000,
                "sort": "ticker",
                "order": "asc",
            },
            output=output / "reference" / sensor,
            api_key=api_key,
            timeout=timeout,
        )
    pages = [
        page
        for sensor in SENSORS
        for page in _read_pages(output / "reference" / sensor)
    ]
    return normalize_reference_pages(pages, session=session)


def _runtime_manifest() -> dict[str, Any]:
    runtime = assert_runtime_lock(RUNTIME_LOCK)
    head, code_hashes = committed_code_state()
    return {
        "git_commit": head,
        "code_hashes": code_hashes,
        "runtime": runtime,
        "predeclaration_sha256": sha256_file(PREDECLARATION),
    }


def _finalize_session(
    staging: Path, final: Path, manifest: Mapping[str, Any]
) -> dict[str, Any]:
    if final.exists():
        raise AssertionError(f"immutable session already exists: {final}")
    files = sorted(
        path for path in staging.rglob("*") if path.is_file() and path.name != "manifest.json"
    )
    source_index = [
        {
            "path": path.relative_to(staging).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in files
    ]
    result = {**dict(manifest), "source_index": source_index}
    result["source_index_sha256"] = sha256_bytes(canonical_json_bytes(source_index))
    write_json(staging / "manifest.json", result)
    final.parent.mkdir(parents=True, exist_ok=True)
    staging.replace(final)
    return result


def _bind_staging(staging: Path, contract: Mapping[str, Any]) -> None:
    path = staging / "_execution_contract.json"
    if path.exists():
        if read_json(path) != dict(contract):
            raise AssertionError(f"stager belongs to a different code contract: {staging}")
    else:
        write_json(path, dict(contract))


def _status_success(value: Mapping[str, Any], expected: str) -> bool:
    return (
        str(value.get("ev", "")).lower() == "status"
        and str(value.get("status", "")).lower() in {"auth_success", "success"}
        and expected.lower() in str(value.get("message", "")).lower()
    )


def _receive_control(
    websocket: Any,
    *,
    expected: str,
    deadline_monotonic: float,
    clock: Callable[[], float] = time_module.monotonic,
) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []
    while clock() < deadline_monotonic:
        try:
            message = websocket.recv()
        except Exception as exc:
            if "timeout" in type(exc).__name__.lower():
                continue
            raise
        payload = json.loads(message)
        values = payload if isinstance(payload, list) else [payload]
        for value in values:
            if not isinstance(value, dict):
                raise AssertionError("non-object WebSocket control payload")
            seen.append(value)
            if _status_success(value, expected):
                return seen
    raise AssertionError(f"WebSocket {expected} acknowledgement timed out")


def capture_shadow_messages(
    *,
    websocket: Any,
    contracts: Iterable[str],
    session: str,
    output: Path,
    api_key: str,
    now_utc: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    monotonic: Callable[[], float] = time_module.monotonic,
) -> dict[str, Any]:
    """Authenticate, subscribe and persist raw live messages until 10:35 ET."""
    contract_list = sorted(set(contracts))
    if not contract_list or len(contract_list) > 1000:
        raise AssertionError(f"live contract cap failed: {len(contract_list)}")
    start, end = session_bounds(session)
    current = now_utc().astimezone(NEW_YORK)
    deadline = datetime.combine(start.date(), SUBSCRIPTION_DEADLINE, NEW_YORK)
    if current > deadline:
        raise AssertionError(f"subscription started after deadline: {current.isoformat()}")

    websocket.send(json.dumps({"action": "auth", "params": api_key}))
    control = _receive_control(
        websocket,
        expected="auth",
        deadline_monotonic=monotonic() + 30,
        clock=monotonic,
    )
    channels = [
        channel
        for ticker in contract_list
        for channel in (f"T.{ticker}", f"Q.{ticker}")
    ]
    for offset in range(0, len(channels), 100):
        websocket.send(
            json.dumps(
                {
                    "action": "subscribe",
                    "params": ",".join(channels[offset : offset + 100]),
                }
            )
        )
        control.extend(
            _receive_control(
                websocket,
                expected="subscribed",
                deadline_monotonic=monotonic() + 30,
                clock=monotonic,
            )
        )
    acknowledged_at = now_utc()
    if acknowledged_at.astimezone(NEW_YORK) > deadline:
        raise AssertionError("subscription acknowledgement missed 09:29:30")

    events_path = output / "events.jsonl"
    controls_path = output / "control.jsonl"
    outside_path = output / "outside_window.jsonl"
    output.mkdir(parents=True, exist_ok=True)
    event_count = 0
    control_count = len(control)
    outside_count = 0
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    with (
        events_path.open("wb") as events,
        controls_path.open("wb") as controls,
        outside_path.open("wb") as outside,
    ):
        for value in control:
            controls.write(canonical_json_bytes(value) + b"\n")
        while now_utc().astimezone(NEW_YORK) < end:
            try:
                message = websocket.recv()
            except Exception as exc:
                if "timeout" in type(exc).__name__.lower():
                    continue
                raise
            arrival = now_utc().astimezone(timezone.utc).isoformat()
            payload = json.loads(message)
            values = payload if isinstance(payload, list) else [payload]
            for value in values:
                if not isinstance(value, dict):
                    raise AssertionError("non-object WebSocket payload")
                if str(value.get("ev", "")).upper() in {"T", "Q"}:
                    wrapper = {
                        "arrival_timestamp_utc": arrival,
                        "payload": value,
                    }
                    timestamp_ms = value.get("t")
                    if (
                        isinstance(timestamp_ms, int)
                        and start_ms <= timestamp_ms < end_ms
                    ):
                        events.write(canonical_json_bytes(wrapper) + b"\n")
                        event_count += 1
                    else:
                        outside.write(canonical_json_bytes(wrapper) + b"\n")
                        outside_count += 1
                else:
                    controls.write(canonical_json_bytes(value) + b"\n")
                    control_count += 1
    return {
        "acknowledged_at_utc": acknowledged_at.astimezone(timezone.utc).isoformat(),
        "contracts": len(contract_list),
        "events": event_count,
        "outside_window_events": outside_count,
        "control_messages": control_count,
        "session_start": start.isoformat(),
        "session_end": end.isoformat(),
    }


def run_shadow(
    *,
    session: str,
    output: Path,
    universe: Path,
    base_url: str,
    websocket_url: str,
    timeout: float,
    websocket_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    parse_session_date(session)
    if base_url != REST_BASE_URL or websocket_url != WEBSOCKET_URL:
        raise AssertionError("shadow endpoints must match the frozen Massive endpoints")
    sessions, universe_sha = load_committed_universe(universe)
    pending = [value for value in sessions if not (output / "shadow" / value).exists()]
    if not pending or session != pending[0]:
        raise AssertionError(
            f"shadow must capture next frozen session: requested={session} pending={pending}"
        )
    today = datetime.now(NEW_YORK).date()
    if parse_session_date(session) != today:
        raise AssertionError("shadow capture requires today's New York session")
    api_key = require_api_key()
    runtime_manifest = _runtime_manifest()
    final = output / "shadow" / session
    staging = output / ".staging" / "shadow" / session
    if final.exists():
        raise AssertionError(f"immutable shadow already exists: {final}")
    staging.mkdir(parents=True, exist_ok=True)
    _bind_staging(
        staging,
        {
            **runtime_manifest,
            "mode": "shadow",
            "session": session,
            "preflight_universe_sha256": universe_sha,
        },
    )
    if any((staging / name).exists() for name in ("events.jsonl", "control.jsonl")):
        raise AssertionError("partial live capture cannot be resumed or overwritten")
    client = requests.Session()
    contracts = capture_reference(
        client=client,
        base_url=base_url,
        session=session,
        output=staging,
        api_key=api_key,
        historical=False,
        timeout=timeout,
    )
    if websocket_factory is None:
        import websocket as websocket_client

        websocket_factory = websocket_client.create_connection
    socket = websocket_factory(websocket_url, timeout=1)
    try:
        live = capture_shadow_messages(
            websocket=socket,
            contracts=[row["ticker"] for row in contracts],
            session=session,
            output=staging,
            api_key=api_key,
        )
    finally:
        socket.close()
    manifest = {
        "status": "SHADOW_SOURCE_CAPTURED_OUTCOME_FREE",
        "provider": "Massive",
        "transport": "websocket",
        "session": session,
        "preflight_universe_sha256": universe_sha,
        "reference_contracts": len(contracts),
        "live": live,
        "outcome_accessed": False,
        "economic_features_created": False,
        **runtime_manifest,
    }
    return _finalize_session(staging, final, manifest)


def capture_rest_contract(
    *,
    client: Any,
    base_url: str,
    session: str,
    ticker: str,
    output: Path,
    api_key: str,
    timeout: float,
) -> None:
    start_ns, end_ns = session_bounds_ns(session)
    safe_ticker = ticker.replace(":", "_")
    for event_kind, template in EVENT_PATHS.items():
        paginated_get(
            client=client,
            url=base_url.rstrip("/") + template.format(ticker=ticker),
            params={
                "timestamp.gte": start_ns,
                "timestamp.lt": end_ns,
                "limit": 50000,
                "sort": "timestamp",
                "order": "asc",
            },
            output=output / "contracts" / safe_ticker / event_kind,
            api_key=api_key,
            timeout=timeout,
        )


def _shadow_reference(output: Path, session: str) -> list[dict[str, Any]]:
    root = output / "shadow" / session
    manifest = read_json(root / "manifest.json")
    if manifest.get("status") != "SHADOW_SOURCE_CAPTURED_OUTCOME_FREE":
        raise AssertionError("invalid shadow manifest")
    pages = [
        page
        for sensor in SENSORS
        for page in _read_pages(root / "reference" / sensor)
    ]
    return normalize_reference_pages(pages, session=session)


def run_rest(
    *,
    session: str,
    output: Path,
    universe: Path,
    base_url: str,
    timeout: float,
) -> dict[str, Any]:
    day = parse_session_date(session)
    if base_url != REST_BASE_URL:
        raise AssertionError("REST endpoint must match the frozen Massive endpoint")
    sessions, universe_sha = load_committed_universe(universe)
    if session not in sessions:
        raise AssertionError("REST session is outside the frozen preflight universe")
    if day >= datetime.now(NEW_YORK).date():
        raise AssertionError("REST comparison requires a completed prior session")
    api_key = require_api_key()
    runtime_manifest = _runtime_manifest()
    shadow_contracts = _shadow_reference(output, session)
    shadow_manifest = read_json(output / "shadow" / session / "manifest.json")
    if shadow_manifest.get("preflight_universe_sha256") != universe_sha:
        raise AssertionError("shadow preflight universe hash mismatch")
    final = output / "rest" / session
    staging = output / ".staging" / "rest" / session
    if final.exists():
        raise AssertionError(f"immutable REST session already exists: {final}")
    staging.mkdir(parents=True, exist_ok=True)
    _bind_staging(
        staging,
        {
            **runtime_manifest,
            "mode": "rest",
            "session": session,
            "preflight_universe_sha256": universe_sha,
        },
    )
    client = requests.Session()
    rest_contracts = capture_reference(
        client=client,
        base_url=base_url,
        session=session,
        output=staging,
        api_key=api_key,
        historical=True,
        timeout=timeout,
    )
    union = sorted(
        {row["ticker"] for row in shadow_contracts}
        | {row["ticker"] for row in rest_contracts}
    )
    for ticker in union:
        capture_rest_contract(
            client=client,
            base_url=base_url,
            session=session,
            ticker=ticker,
            output=staging,
            api_key=api_key,
            timeout=timeout,
        )
    manifest = {
        "status": "REST_SOURCE_CAPTURED_OUTCOME_FREE",
        "provider": "Massive",
        "transport": "rest",
        "session": session,
        "preflight_universe_sha256": universe_sha,
        "shadow_reference_contracts": len(shadow_contracts),
        "rest_reference_contracts": len(rest_contracts),
        "contract_union": len(union),
        "outcome_accessed": False,
        "economic_features_created": False,
        **runtime_manifest,
    }
    return _finalize_session(staging, final, manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "shadow", "rest"))
    parser.add_argument("--session", help="YYYYMMDD New York session")
    parser.add_argument("--start", help="first future NYSE session for freeze mode")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--base-url", default=REST_BASE_URL)
    parser.add_argument("--websocket-url", default=WEBSOCKET_URL)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--acknowledge-external-call")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "freeze":
        if not args.start or args.session or args.acknowledge_external_call:
            raise AssertionError("freeze requires only --start and --universe")
        committed_code_state()
        result = freeze_preflight_universe(start=args.start, output=args.universe)
        print(json.dumps(result, sort_keys=True))
        return
    if args.acknowledge_external_call != NETWORK_ACKNOWLEDGEMENT:
        raise AssertionError("explicit external-call acknowledgement is required")
    if not args.session:
        raise AssertionError("network capture requires --session")
    if args.mode == "shadow":
        result = run_shadow(
            session=args.session,
            output=args.output,
            universe=args.universe,
            base_url=args.base_url,
            websocket_url=args.websocket_url,
            timeout=args.timeout,
        )
    else:
        result = run_rest(
            session=args.session,
            output=args.output,
            universe=args.universe,
            base_url=args.base_url,
            timeout=args.timeout,
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
