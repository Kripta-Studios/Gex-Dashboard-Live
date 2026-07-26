"""Independent raw reparse of the external OPRA historical/live source gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, time, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.wall_surface_flow_environment import (  # noqa: E402
    assert_runtime_lock,
)

TICKER = re.compile(r"^O:(QQQ|SPY)\d{6}[CP]\d{8}$")
SENSORS = {"QQQ", "SPY"}
NEW_YORK = ZoneInfo("America/New_York")
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
DEFAULT_CAPTURE_ROOT = Path("D:/ThetaData/external_opra_source_intake_massive_v1")
DEFAULT_GATE = Path("D:/ThetaData/external_opra_source_intake_massive_gate_v1")
DEFAULT_OUTPUT = Path(
    "D:/ThetaData/external_opra_source_intake_massive_gate_audit_v1"
)
COMPARISON_FIELDS = (
    "contract_ticker",
    "underlying",
    "trade_date",
    "event_kind",
    "sip_timestamp_ms",
    "sequence_number",
    "trade_price",
    "trade_size",
    "trade_exchange",
    "trade_conditions",
    "trade_correction",
    "bid_price",
    "ask_price",
    "bid_size",
    "ask_size",
    "bid_exchange",
    "ask_exchange",
    "quote_conditions",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def committed_code_state() -> tuple[str, dict[str, str]]:
    if _sha_file(PREDECLARATION) != EXPECTED_PREDECLARATION_SHA256:
        raise AssertionError("auditor predeclaration hash mismatch")
    hashes: dict[str, str] = {}
    for relative in CODE_CLOSURE:
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
            raise AssertionError(f"auditor requires committed code: {relative}")
        hashes[relative] = _sha_file(PROJECT_ROOT / relative)
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
        raise AssertionError("auditor requires main with HEAD == origin/main")
    return head, hashes


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical(value) + b"\n")
    temporary.replace(path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for number, raw in enumerate(handle, start=1):
            if not raw.strip():
                raise AssertionError(f"blank JSONL line: {path}:{number}")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise AssertionError(f"non-object JSONL line: {path}:{number}")
            rows.append(value)
    return rows


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise AssertionError(f"invalid {name}: {value!r}")
    return value


def _decimal(value: Any, name: str) -> str:
    if value is None or isinstance(value, bool):
        raise AssertionError(f"invalid {name}: {value!r}")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AssertionError(f"invalid {name}: {value!r}") from exc
    if not result.is_finite() or result < 0:
        raise AssertionError(f"invalid {name}: {value!r}")
    text = format(result.normalize(), "f")
    return "0" if text == "-0" else text


def _conditions(value: Any, name: str) -> list[int]:
    values = [] if value is None else value if isinstance(value, list) else [value]
    result = [_integer(item, name) for item in values]
    if len(result) != len(set(result)):
        raise AssertionError(f"duplicate {name}")
    return result


def _ticker(value: Any, session: str) -> tuple[str, str]:
    text = str(value).strip().upper()
    match = TICKER.fullmatch(text)
    if match is None or "20" + text.split(":")[1][3:9] != session:
        raise AssertionError(f"invalid option ticker/session: {value!r} {session}")
    return text, match.group(1)


def _inside(session: str, timestamp_ms: int) -> None:
    day = datetime.strptime(session, "%Y%m%d").date()
    start = datetime.combine(day, time(9, 30), NEW_YORK)
    end = datetime.combine(day, time(10, 35), NEW_YORK)
    value = datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc)
    if not start.astimezone(timezone.utc) <= value < end.astimezone(timezone.utc):
        raise AssertionError(f"event outside session source clocks: {timestamp_ms}")


def _empty(
    *,
    ticker: str,
    session: str,
    kind: str,
    raw_timestamp: int,
    timestamp_ms: int,
    participant: int | None,
    sequence: int,
    arrival: str | None,
    transport: str,
) -> dict[str, Any]:
    normalized, sensor = _ticker(ticker, session)
    _inside(session, timestamp_ms)
    row = {
        "contract_ticker": normalized,
        "underlying": sensor,
        "trade_date": session,
        "event_kind": kind,
        "sip_timestamp_raw": raw_timestamp,
        "sip_timestamp_ms": timestamp_ms,
        "participant_timestamp_raw": participant,
        "sequence_number": sequence,
        "trade_price": None,
        "trade_size": None,
        "trade_exchange": None,
        "trade_conditions": [],
        "trade_correction": None,
        "bid_price": None,
        "ask_price": None,
        "bid_size": None,
        "ask_size": None,
        "bid_exchange": None,
        "ask_exchange": None,
        "quote_conditions": [],
        "arrival_timestamp_utc": arrival,
        "source_transport": transport,
    }
    return row


def _normalize_live(wrapper: Mapping[str, Any], session: str) -> dict[str, Any]:
    payload = wrapper.get("payload")
    if not isinstance(payload, dict):
        raise AssertionError("live wrapper lacks payload")
    kind = {"T": "trade", "Q": "quote"}.get(str(payload.get("ev", "")).upper())
    if kind is None:
        raise AssertionError("unsupported live event")
    raw_timestamp = _integer(payload.get("t"), "t", 1)
    if not 1_000_000_000_000 <= raw_timestamp < 10_000_000_000_000:
        raise AssertionError("live timestamp is not milliseconds")
    arrival = datetime.fromisoformat(
        str(wrapper.get("arrival_timestamp_utc", "")).replace("Z", "+00:00")
    )
    if arrival.tzinfo is None:
        raise AssertionError("arrival lacks timezone")
    row = _empty(
        ticker=str(payload.get("sym")),
        session=session,
        kind=kind,
        raw_timestamp=raw_timestamp,
        timestamp_ms=raw_timestamp,
        participant=None,
        sequence=_integer(payload.get("q"), "q"),
        arrival=arrival.astimezone(timezone.utc).isoformat(),
        transport="websocket",
    )
    if kind == "trade":
        row.update(
            {
                "trade_price": _decimal(payload.get("p"), "p"),
                "trade_size": _integer(payload.get("s"), "s", 1),
                "trade_exchange": _integer(payload.get("x"), "x"),
                "trade_conditions": _conditions(payload.get("c"), "trade conditions"),
            }
        )
    else:
        row.update(
            {
                "bid_price": _decimal(payload.get("bp"), "bp"),
                "ask_price": _decimal(payload.get("ap"), "ap"),
                "bid_size": _integer(payload.get("bs"), "bs"),
                "ask_size": _integer(payload.get("as"), "as"),
                "bid_exchange": _integer(payload.get("bx"), "bx"),
                "ask_exchange": _integer(payload.get("ax"), "ax"),
                "quote_conditions": _conditions(
                    payload.get("c"), "quote conditions"
                ),
            }
        )
        if Decimal(row["bid_price"]) > Decimal(row["ask_price"]):
            raise AssertionError("crossed live quote")
    return row


def _normalize_rest(
    payload: Mapping[str, Any], session: str, ticker: str, kind: str
) -> dict[str, Any]:
    raw_timestamp = _integer(payload.get("sip_timestamp"), "sip_timestamp", 1)
    if raw_timestamp < 1_000_000_000_000_000:
        raise AssertionError("REST timestamp is not nanoseconds")
    participant_value = payload.get("participant_timestamp")
    participant = (
        None
        if participant_value is None
        else _integer(participant_value, "participant_timestamp", 1)
    )
    row = _empty(
        ticker=ticker,
        session=session,
        kind=kind,
        raw_timestamp=raw_timestamp,
        timestamp_ms=raw_timestamp // 1_000_000,
        participant=participant,
        sequence=_integer(payload.get("sequence_number"), "sequence_number"),
        arrival=None,
        transport="rest",
    )
    if kind == "trade":
        row.update(
            {
                "trade_price": _decimal(payload.get("price"), "price"),
                "trade_size": _integer(payload.get("size"), "size", 1),
                "trade_exchange": _integer(payload.get("exchange"), "exchange"),
                "trade_conditions": _conditions(
                    payload.get("conditions"), "trade conditions"
                ),
                "trade_correction": _integer(
                    payload.get("correction", 0), "correction"
                ),
            }
        )
    else:
        row.update(
            {
                "bid_price": _decimal(payload.get("bid_price"), "bid_price"),
                "ask_price": _decimal(payload.get("ask_price"), "ask_price"),
                "bid_size": _integer(payload.get("bid_size"), "bid_size"),
                "ask_size": _integer(payload.get("ask_size"), "ask_size"),
                "bid_exchange": _integer(
                    payload.get("bid_exchange"), "bid_exchange"
                ),
                "ask_exchange": _integer(
                    payload.get("ask_exchange"), "ask_exchange"
                ),
                "quote_conditions": _conditions(
                    payload.get("conditions"), "quote conditions"
                ),
            }
        )
        if Decimal(row["bid_price"]) > Decimal(row["ask_price"]):
            raise AssertionError("crossed REST quote")
    return row


def _pages(directory: Path) -> list[dict[str, Any]]:
    state = _read_json(directory / "state.json")
    files = sorted(directory.glob("page_*.json"))
    if (
        state.get("complete") is not True
        or len(files) != state.get("pages_completed")
        or not files
    ):
        raise AssertionError(f"incomplete pagination: {directory}")
    values = [json.loads(path.read_bytes()) for path in files]
    if any(not isinstance(value.get("results"), list) for value in values):
        raise AssertionError(f"missing page results: {directory}")
    return values


def _reference(root: Path, session: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    iso = datetime.strptime(session, "%Y%m%d").date().isoformat()
    for sensor in sorted(SENSORS):
        for page in _pages(root / "reference" / sensor):
            for payload in page["results"]:
                ticker, underlying = _ticker(payload.get("ticker"), session)
                contract_type = str(payload.get("contract_type", "")).lower()
                expected_type = "call" if ticker[-9] == "C" else "put"
                if (
                    underlying != sensor
                    or str(payload.get("underlying_ticker", "")).upper() != sensor
                    or payload.get("expiration_date") != iso
                    or contract_type != expected_type
                ):
                    raise AssertionError(f"invalid reference record: {ticker}")
                rows.append(
                    {
                        "ticker": ticker,
                        "underlying": underlying,
                        "trade_date": session,
                        "expiration_date": iso,
                        "contract_type": contract_type,
                        "strike_price": _decimal(
                            payload.get("strike_price"), "strike_price"
                        ),
                    }
                )
    rows.sort(key=lambda row: row["ticker"])
    tickers = [row["ticker"] for row in rows]
    if (
        not rows
        or len(tickers) != len(set(tickers))
        or {row["underlying"] for row in rows} != SENSORS
    ):
        raise AssertionError("invalid reference inventory")
    return rows


def _verify_manifest(
    root: Path,
    status: str,
    expected_code_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    manifest = _read_json(root / "manifest.json")
    if manifest.get("status") != status or manifest.get("outcome_accessed") is not False:
        raise AssertionError(f"source manifest invalid: {root}")
    if (
        manifest.get("predeclaration_sha256") != EXPECTED_PREDECLARATION_SHA256
        or (
            expected_code_hashes is not None
            and manifest.get("code_hashes") != dict(expected_code_hashes)
        )
    ):
        raise AssertionError(f"source closure mismatch: {root}")
    index = manifest.get("source_index")
    if (
        not isinstance(index, list)
        or _sha_bytes(_canonical(index)) != manifest.get("source_index_sha256")
    ):
        raise AssertionError(f"source index invalid: {root}")
    indexed: set[str] = set()
    for row in index:
        relative = str(row["path"])
        path = root / relative
        if (
            relative in indexed
            or not path.is_file()
            or path.stat().st_size != row["size"]
            or _sha_file(path) != row["sha256"]
        ):
            raise AssertionError(f"source file mismatch: {path}")
        indexed.add(relative)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual != indexed:
        raise AssertionError(f"source index coverage mismatch: {root}")
    return manifest


def _validate_universe(path: Path) -> tuple[list[str], str]:
    value = _read_json(path)
    required = {
        "contract",
        "created_at_utc",
        "sessions",
        "outcome_accessed",
        "market_value_accessed",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise AssertionError("independent universe schema mismatch")
    created = datetime.fromisoformat(
        str(value["created_at_utc"]).replace("Z", "+00:00")
    )
    sessions = value["sessions"] if isinstance(value["sessions"], list) else []
    if (
        value["contract"] != "EXTERNAL_OPRA_SOURCE_INTAKE_PREFLIGHT_V1"
        or created.tzinfo is None
        or len(sessions) != 5
        or sessions != sorted(set(sessions))
        or value["outcome_accessed"] is not False
        or value["market_value_accessed"] is not False
    ):
        raise AssertionError("independent universe contract mismatch")
    dates = [datetime.strptime(item, "%Y%m%d").date() for item in sessions]
    if (
        any(item.weekday() >= 5 for item in dates)
        or dates[0] <= created.astimezone(NEW_YORK).date()
    ):
        raise AssertionError("independent universe temporal mismatch")
    return list(sessions), _sha_file(path)


def _validate_correction_evidence(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    required = {
        "provider",
        "scope",
        "status",
        "source_url",
        "retrieved_at_utc",
        "historical_correction_field",
        "live_correction_semantics",
        "evidence_file",
        "evidence_sha256",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise AssertionError("independent correction evidence schema mismatch")
    parsed = urlsplit(str(value["source_url"]))
    retrieved = datetime.fromisoformat(
        str(value["retrieved_at_utc"]).replace("Z", "+00:00")
    )
    name = str(value["evidence_file"])
    raw = path.parent / name
    if (
        value["provider"] != "Massive"
        or value["scope"] != "OPTIONS_TRADES_WEBSOCKET_AND_REST"
        or value["status"] != "PROVIDER_CERTIFIED"
        or value["historical_correction_field"] != "correction"
        or value["live_correction_semantics"]
        not in {"EXPLICIT_FIELD", "REPLAYED_CORRECTED_EVENT_WITH_STABLE_ID"}
        or parsed.scheme != "https"
        or parsed.hostname is None
        or not (
            parsed.hostname == "massive.com"
            or parsed.hostname.endswith(".massive.com")
        )
        or retrieved.tzinfo is None
        or Path(name).name != name
        or not raw.is_file()
        or raw.stat().st_size == 0
        or _sha_file(raw) != value["evidence_sha256"]
    ):
        raise AssertionError("independent correction evidence mismatch")
    return {
        "manifest_sha256": _sha_file(path),
        "evidence_sha256": _sha_file(raw),
        "source_url": value["source_url"],
        "retrieved_at_utc": retrieved.isoformat(),
        "live_correction_semantics": value["live_correction_semantics"],
    }


def _validate_sequences(rows: Iterable[Mapping[str, Any]]) -> None:
    previous: dict[tuple[str, str], int] = {}
    identities: set[tuple[str, str, int, int]] = set()
    for row in rows:
        identity = (
            str(row["contract_ticker"]),
            str(row["event_kind"]),
            int(row["sip_timestamp_ms"]),
            int(row["sequence_number"]),
        )
        if identity in identities:
            raise AssertionError(f"duplicate event: {identity}")
        identities.add(identity)
        group = identity[:2]
        if group in previous and identity[3] <= previous[group]:
            raise AssertionError(f"non-increasing event sequence: {identity}")
        previous[group] = identity[3]


def _predecessors(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    quotes: defaultdict[str, list[int]] = defaultdict(list)
    trades: list[Mapping[str, Any]] = []
    for row in rows:
        if row["event_kind"] == "quote":
            quotes[str(row["contract_ticker"])].append(int(row["sip_timestamp_ms"]))
        else:
            trades.append(row)
    result = {
        "trades": len(trades),
        "with_strict_predecessor": 0,
        "without_strict_predecessor": 0,
        "same_millisecond_ties": 0,
    }
    for values in quotes.values():
        values.sort()
    for trade in trades:
        values = quotes[str(trade["contract_ticker"])]
        timestamp = int(trade["sip_timestamp_ms"])
        result["same_millisecond_ties"] += int(timestamp in values)
        if any(value < timestamp for value in values):
            result["with_strict_predecessor"] += 1
        else:
            result["without_strict_predecessor"] += 1
    return result


def _comparison(row: Mapping[str, Any]) -> bytes:
    value = {field: row.get(field) for field in COMPARISON_FIELDS}
    if value["event_kind"] == "trade":
        correction = value["trade_correction"]
        if correction in {None, 0}:
            value["trade_correction"] = 0
    return _canonical(value)


def reparse_session(
    capture_root: Path,
    session: str,
    universe_sha256: str | None = None,
    expected_code_hashes: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    shadow = capture_root / "shadow" / session
    rest = capture_root / "rest" / session
    shadow_manifest = _verify_manifest(
        shadow,
        "SHADOW_SOURCE_CAPTURED_OUTCOME_FREE",
        expected_code_hashes,
    )
    rest_manifest = _verify_manifest(
        rest, "REST_SOURCE_CAPTURED_OUTCOME_FREE", expected_code_hashes
    )
    if universe_sha256 is not None and (
        shadow_manifest.get("preflight_universe_sha256") != universe_sha256
        or rest_manifest.get("preflight_universe_sha256") != universe_sha256
    ):
        raise AssertionError("independent source universe hash mismatch")
    shadow_reference = _reference(shadow, session)
    rest_reference = _reference(rest, session)
    union = sorted(
        {row["ticker"] for row in shadow_reference}
        | {row["ticker"] for row in rest_reference}
    )
    live = [_normalize_live(row, session) for row in _read_jsonl(shadow / "events.jsonl")]
    rest_rows: list[dict[str, Any]] = []
    for ticker in union:
        root = rest / "contracts" / ticker.replace(":", "_")
        for kind in ("trade", "quote"):
            for page in _pages(root / kind):
                rest_rows.extend(
                    _normalize_rest(payload, session, ticker, kind)
                    for payload in page["results"]
                )
    rest_rows.sort(
        key=lambda row: (
            row["contract_ticker"],
            row["event_kind"],
            row["sequence_number"],
        )
    )
    _validate_sequences(live)
    _validate_sequences(rest_rows)
    live_counter = Counter(_comparison(row) for row in live)
    rest_counter = Counter(_comparison(row) for row in rest_rows)
    corrections = sorted(
        {
            row["trade_correction"]
            for row in rest_rows
            if row["event_kind"] == "trade"
        }
    )
    live_predecessor = _predecessors(live)
    rest_predecessor = _predecessors(rest_rows)
    live_counts = Counter(
        (str(row["underlying"]), str(row["event_kind"])) for row in live
    )
    rest_counts = Counter(
        (str(row["underlying"]), str(row["event_kind"])) for row in rest_rows
    )
    required_groups = {
        (sensor, kind) for sensor in SENSORS for kind in ("quote", "trade")
    }
    live_manifest = shadow_manifest.get("live")
    if not isinstance(live_manifest, dict):
        raise AssertionError("independent shadow manifest lacks live audit")
    acknowledged = datetime.fromisoformat(
        str(live_manifest.get("acknowledged_at_utc", "")).replace("Z", "+00:00")
    )
    if acknowledged.tzinfo is None:
        raise AssertionError("independent acknowledgement lacks timezone")
    session_day = datetime.strptime(session, "%Y%m%d").date()
    deadline = datetime.combine(session_day, time(9, 29, 30), NEW_YORK)
    live_arrival_causal = all(
        datetime.fromisoformat(str(row["arrival_timestamp_utc"])).astimezone(timezone.utc)
        >= datetime.fromtimestamp(
            int(row["sip_timestamp_ms"]) / 1000, tz=timezone.utc
        )
        for row in live
    )
    gates = {
        "reference_equal": shadow_reference == rest_reference,
        "reference_nonempty_both_sensors": bool(shadow_reference)
        and {row["underlying"] for row in shadow_reference} == SENSORS,
        "contract_cap_pass": len(shadow_reference) <= 1000,
        "subscription_ack_before_deadline": acknowledged.astimezone(NEW_YORK)
        <= deadline,
        "subscription_count_exact": int(live_manifest.get("contracts", -1))
        == len(shadow_reference),
        "nonempty_quotes_and_trades_both_sensors": all(
            live_counts[group] > 0 and rest_counts[group] > 0
            for group in required_groups
        ),
        "live_arrival_not_before_event": live_arrival_causal,
        "correction_contract_present": True,
        "rest_corrections_zero_only": set(corrections).issubset({0}),
        "event_multiset_equal": live_counter == rest_counter,
        "live_contract_subset_reference": {
            row["contract_ticker"] for row in live
        }.issubset({row["ticker"] for row in shadow_reference}),
        "rest_contract_subset_reference": {
            row["contract_ticker"] for row in rest_rows
        }.issubset({row["ticker"] for row in rest_reference}),
        "strict_predecessor_census_equal": live_predecessor == rest_predecessor,
    }
    status = (
        "PASS_SESSION_HISTORICAL_LIVE_PARITY"
        if all(gates.values())
        else "FAILED_SESSION_HISTORICAL_LIVE_PARITY"
    )
    summary = {
        "session": session,
        "status": status,
        "gates": gates,
        "shadow_reference_contracts": len(shadow_reference),
        "rest_reference_contracts": len(rest_reference),
        "live_events": len(live),
        "rest_events": len(rest_rows),
        "live_only_events": sum((live_counter - rest_counter).values()),
        "rest_only_events": sum((rest_counter - live_counter).values()),
        "rest_correction_values": corrections,
        "live_event_counts": {
            f"{sensor}_{kind}": live_counts[(sensor, kind)]
            for sensor, kind in sorted(required_groups)
        },
        "rest_event_counts": {
            f"{sensor}_{kind}": rest_counts[(sensor, kind)]
            for sensor, kind in sorted(required_groups)
        },
        "live_predecessor_audit": live_predecessor,
        "rest_predecessor_audit": rest_predecessor,
    }
    return summary, live, rest_rows


def audit_gate(
    *,
    capture_root: Path,
    gate: Path,
    universe: Path,
    correction_evidence: Path,
    output: Path,
) -> dict[str, Any]:
    _, code_hashes = committed_code_state()
    runtime = assert_runtime_lock(RUNTIME_LOCK)
    if output.exists():
        raise AssertionError(f"immutable audit output exists: {output}")
    summary = _read_json(gate / "summary.json")
    if summary.get("outcome_accessed") is not False:
        raise AssertionError("gate summary indicates outcome access")
    if summary.get("code_hashes") != code_hashes or summary.get("runtime") != runtime:
        raise AssertionError("gate/current code or runtime closure mismatch")
    artifact_index = summary.get("artifact_index")
    if (
        not isinstance(artifact_index, list)
        or _sha_bytes(_canonical(artifact_index))
        != summary.get("artifact_index_sha256")
    ):
        raise AssertionError("gate artifact index mismatch")
    for row in artifact_index:
        path = gate / row["path"]
        if (
            not path.is_file()
            or path.stat().st_size != row["size"]
            or _sha_file(path) != row["sha256"]
        ):
            raise AssertionError(f"gate artifact mismatch: {path}")
    sessions, universe_sha = _validate_universe(universe)
    if (
        sessions != summary.get("sessions")
        or universe_sha != summary.get("preflight_universe_sha256")
    ):
        raise AssertionError("gate preflight universe mismatch")
    correction = _validate_correction_evidence(correction_evidence)
    if correction != summary.get("correction_evidence"):
        raise AssertionError("gate correction evidence mismatch")

    session_summaries: list[dict[str, Any]] = []
    all_live: list[dict[str, Any]] = []
    all_rest: list[dict[str, Any]] = []
    for session in summary["sessions"]:
        result, live, rest = reparse_session(
            capture_root,
            session,
            universe_sha256=universe_sha,
            expected_code_hashes=code_hashes,
        )
        session_summaries.append(result)
        all_live.extend(live)
        all_rest.extend(rest)
    reproduced_status = (
        "PASS_OUTCOME_FREE_EXTERNAL_OPRA_SOURCE_GATE"
        if all(
            row["status"] == "PASS_SESSION_HISTORICAL_LIVE_PARITY"
            for row in session_summaries
        )
        else "FAILED_OUTCOME_FREE_EXTERNAL_OPRA_SOURCE_GATE"
    )
    stored_live = _read_jsonl(gate / "canonical_live_events.jsonl")
    stored_rest = _read_jsonl(gate / "canonical_rest_events.jsonl")
    exact = (
        session_summaries == summary["session_summaries"]
        and reproduced_status == summary["status"]
        and all_live == stored_live
        and all_rest == stored_rest
    )
    result = {
        "status": (
            "PASS_INDEPENDENT_EXTERNAL_OPRA_SOURCE_GATE_AUDIT"
            if exact
            else "FAILED_INDEPENDENT_EXTERNAL_OPRA_SOURCE_GATE_AUDIT"
        ),
        "gate_status": summary["status"],
        "reproduced_gate_status": reproduced_status,
        "sessions": list(summary["sessions"]),
        "session_summaries_exact": session_summaries == summary["session_summaries"],
        "canonical_live_exact": all_live == stored_live,
        "canonical_rest_exact": all_rest == stored_rest,
        "live_events": len(all_live),
        "rest_events": len(all_rest),
        "outcome_accessed": False,
        "economic_features_created": False,
        "model_created": False,
    }
    output.mkdir(parents=True)
    _write_json(output / "summary.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-root", type=Path, default=DEFAULT_CAPTURE_ROOT)
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--correction-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = audit_gate(
        capture_root=args.capture_root,
        gate=args.gate,
        universe=args.universe,
        correction_evidence=args.correction_evidence,
        output=args.output,
    )
    print(json.dumps(result, sort_keys=True))
    if result["status"] != "PASS_INDEPENDENT_EXTERNAL_OPRA_SOURCE_GATE_AUDIT":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
