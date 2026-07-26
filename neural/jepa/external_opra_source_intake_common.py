"""Pure, outcome-free normalization for external OPRA source admission."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping
from zoneinfo import ZoneInfo

SENSORS = ("QQQ", "SPY")
EVENT_KINDS = ("quote", "trade")
NEW_YORK = ZoneInfo("America/New_York")
OPTION_TICKER = re.compile(r"^O:(QQQ|SPY)\d{6}[CP]\d{8}$")
SESSION_START = time(9, 30)
SESSION_END = time(10, 35)
SUBSCRIPTION_DEADLINE = time(9, 29, 30)

CANONICAL_FIELDS = (
    "contract_ticker",
    "underlying",
    "trade_date",
    "event_kind",
    "sip_timestamp_raw",
    "sip_timestamp_ms",
    "participant_timestamp_raw",
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
    "arrival_timestamp_utc",
    "source_transport",
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


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(canonical_json_bytes(value) + b"\n")
    temporary.replace(target)


def write_jsonl(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> int:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    count = 0
    with temporary.open("wb") as handle:
        for row in rows:
            handle.write(canonical_json_bytes(dict(row)) + b"\n")
            count += 1
    temporary.replace(target)
    return count


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        for number, raw in enumerate(handle, start=1):
            if not raw.strip():
                raise AssertionError(f"blank JSONL line: {path}:{number}")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise AssertionError(f"non-object JSONL line: {path}:{number}")
            yield value


def parse_session_date(value: str) -> date:
    if not re.fullmatch(r"\d{8}", value):
        raise AssertionError(f"invalid session date: {value}")
    return datetime.strptime(value, "%Y%m%d").date()


def validate_preflight_universe(value: Mapping[str, Any]) -> list[str]:
    required = {
        "contract",
        "created_at_utc",
        "sessions",
        "outcome_accessed",
        "market_value_accessed",
    }
    if set(value) != required:
        raise AssertionError(f"preflight universe schema mismatch: {sorted(value)}")
    if value["contract"] != "EXTERNAL_OPRA_SOURCE_INTAKE_PREFLIGHT_V1":
        raise AssertionError("preflight universe contract mismatch")
    created = datetime.fromisoformat(
        str(value["created_at_utc"]).replace("Z", "+00:00")
    )
    if created.tzinfo is None:
        raise AssertionError("preflight universe timestamp lacks timezone")
    sessions = list(value["sessions"]) if isinstance(value["sessions"], list) else []
    if len(sessions) != 5 or sessions != sorted(set(sessions)):
        raise AssertionError("preflight requires exactly five ordered unique sessions")
    dates = [parse_session_date(item) for item in sessions]
    if any(item.weekday() >= 5 for item in dates):
        raise AssertionError("preflight universe includes a weekend")
    if dates[0] <= created.astimezone(NEW_YORK).date():
        raise AssertionError("preflight sessions were not future at freeze time")
    if value["outcome_accessed"] is not False or value["market_value_accessed"] is not False:
        raise AssertionError("preflight universe declares value/outcome access")
    return sessions


def session_bounds(session: str) -> tuple[datetime, datetime]:
    day = parse_session_date(session)
    return (
        datetime.combine(day, SESSION_START, NEW_YORK),
        datetime.combine(day, SESSION_END, NEW_YORK),
    )


def session_bounds_ns(session: str) -> tuple[int, int]:
    start, end = session_bounds(session)
    return (
        int(start.timestamp() * 1_000_000_000),
        int(end.timestamp() * 1_000_000_000),
    )


def session_contains_ms(session: str, timestamp_ms: int) -> bool:
    start, end = session_bounds(session)
    value = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    return start.astimezone(timezone.utc) <= value < end.astimezone(timezone.utc)


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise AssertionError(f"{field} cannot be bool")
    try:
        converted = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise AssertionError(f"invalid {field}: {value!r}") from exc
    if converted < minimum or converted != value:
        raise AssertionError(f"invalid {field}: {value!r}")
    return converted


def _optional_integer(value: Any, field: str, *, minimum: int = 0) -> int | None:
    if value is None:
        return None
    return _integer(value, field, minimum=minimum)


def _decimal_text(value: Any, field: str) -> str:
    if isinstance(value, bool) or value is None:
        raise AssertionError(f"invalid {field}: {value!r}")
    try:
        converted = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AssertionError(f"invalid {field}: {value!r}") from exc
    if not converted.is_finite() or converted < 0:
        raise AssertionError(f"invalid {field}: {value!r}")
    normalized = format(converted.normalize(), "f")
    return "0" if normalized in {"-0", ""} else normalized


def _conditions(value: Any, field: str) -> list[int]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    result = [_integer(item, field) for item in values]
    if len(result) != len(set(result)):
        raise AssertionError(f"duplicate {field}: {result}")
    return result


def normalize_contract_ticker(value: Any) -> tuple[str, str]:
    ticker = str(value).strip().upper()
    if not OPTION_TICKER.fullmatch(ticker):
        raise AssertionError(f"invalid QQQ/SPY 0DTE option ticker: {value!r}")
    return ticker, OPTION_TICKER.fullmatch(ticker).group(1)  # type: ignore[union-attr]


def contract_expiration(ticker: str) -> str:
    normalized, _ = normalize_contract_ticker(ticker)
    return "20" + normalized.split(":")[1][3:9]


def normalize_reference_record(
    value: Mapping[str, Any], *, session: str
) -> dict[str, Any]:
    ticker, underlying = normalize_contract_ticker(value.get("ticker"))
    expected_expiration = parse_session_date(session).isoformat()
    expiration = str(value.get("expiration_date", ""))
    if expiration != expected_expiration or contract_expiration(ticker) != session:
        raise AssertionError(
            f"reference expiry mismatch: ticker={ticker} value={expiration} "
            f"expected={expected_expiration}"
        )
    documented_underlying = str(value.get("underlying_ticker", "")).upper()
    if documented_underlying != underlying:
        raise AssertionError(
            f"reference underlying mismatch: {ticker} {documented_underlying}"
        )
    contract_type = str(value.get("contract_type", "")).lower()
    expected_type = "call" if ticker[-9] == "C" else "put"
    if contract_type != expected_type:
        raise AssertionError(f"reference put/call mismatch: {ticker} {contract_type}")
    return {
        "ticker": ticker,
        "underlying": underlying,
        "trade_date": session,
        "expiration_date": expiration,
        "contract_type": contract_type,
        "strike_price": _decimal_text(value.get("strike_price"), "strike_price"),
    }


def normalize_reference_pages(
    pages: Iterable[Mapping[str, Any]], *, session: str
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for page in pages:
        results = page.get("results")
        if not isinstance(results, list):
            raise AssertionError("reference page lacks results list")
        records.extend(
            normalize_reference_record(item, session=session) for item in results
        )
    records.sort(key=lambda row: row["ticker"])
    tickers = [row["ticker"] for row in records]
    if not records or len(tickers) != len(set(tickers)):
        raise AssertionError("empty or duplicate reference contract inventory")
    present = {row["underlying"] for row in records}
    if present != set(SENSORS):
        raise AssertionError(f"reference sensor inventory mismatch: {present}")
    return records


def _rest_timestamp_ms(value: Any, field: str) -> tuple[int, int]:
    raw = _integer(value, field, minimum=1)
    if raw < 1_000_000_000_000_000:
        raise AssertionError(f"{field} is not nanoseconds: {raw}")
    return raw, raw // 1_000_000


def _live_timestamp_ms(value: Any, field: str) -> tuple[int, int]:
    raw = _integer(value, field, minimum=1)
    if not 1_000_000_000_000 <= raw < 10_000_000_000_000:
        raise AssertionError(f"{field} is not milliseconds: {raw}")
    return raw, raw


def _empty_event(
    *,
    ticker: str,
    session: str,
    event_kind: str,
    sip_raw: int,
    sip_ms: int,
    participant_raw: int | None,
    sequence: int,
    arrival: str | None,
    transport: str,
) -> dict[str, Any]:
    _, underlying = normalize_contract_ticker(ticker)
    if event_kind not in EVENT_KINDS:
        raise AssertionError(f"invalid event kind: {event_kind}")
    if contract_expiration(ticker) != session:
        raise AssertionError(f"event expiry mismatch: {ticker} {session}")
    if not session_contains_ms(session, sip_ms):
        raise AssertionError(f"event outside source window: {ticker} {sip_ms}")
    row = {field: None for field in CANONICAL_FIELDS}
    row.update(
        {
            "contract_ticker": ticker,
            "underlying": underlying,
            "trade_date": session,
            "event_kind": event_kind,
            "sip_timestamp_raw": sip_raw,
            "sip_timestamp_ms": sip_ms,
            "participant_timestamp_raw": participant_raw,
            "sequence_number": sequence,
            "trade_conditions": [],
            "quote_conditions": [],
            "arrival_timestamp_utc": arrival,
            "source_transport": transport,
        }
    )
    return row


def normalize_rest_event(
    value: Mapping[str, Any],
    *,
    event_kind: str,
    contract_ticker: str,
    session: str,
) -> dict[str, Any]:
    ticker, _ = normalize_contract_ticker(contract_ticker)
    sip_raw, sip_ms = _rest_timestamp_ms(value.get("sip_timestamp"), "sip_timestamp")
    participant = _optional_integer(
        value.get("participant_timestamp"), "participant_timestamp", minimum=1
    )
    row = _empty_event(
        ticker=ticker,
        session=session,
        event_kind=event_kind,
        sip_raw=sip_raw,
        sip_ms=sip_ms,
        participant_raw=participant,
        sequence=_integer(value.get("sequence_number"), "sequence_number"),
        arrival=None,
        transport="rest",
    )
    if event_kind == "trade":
        row.update(
            {
                "trade_price": _decimal_text(value.get("price"), "price"),
                "trade_size": _integer(value.get("size"), "size", minimum=1),
                "trade_exchange": _integer(value.get("exchange"), "exchange"),
                "trade_conditions": _conditions(
                    value.get("conditions"), "trade_conditions"
                ),
                "trade_correction": _integer(
                    value.get("correction", 0), "trade_correction"
                ),
            }
        )
    else:
        row.update(
            {
                "bid_price": _decimal_text(value.get("bid_price"), "bid_price"),
                "ask_price": _decimal_text(value.get("ask_price"), "ask_price"),
                "bid_size": _integer(value.get("bid_size"), "bid_size"),
                "ask_size": _integer(value.get("ask_size"), "ask_size"),
                "bid_exchange": _integer(value.get("bid_exchange"), "bid_exchange"),
                "ask_exchange": _integer(value.get("ask_exchange"), "ask_exchange"),
                "quote_conditions": _conditions(
                    value.get("conditions"), "quote_conditions"
                ),
            }
        )
        if Decimal(row["bid_price"]) > Decimal(row["ask_price"]):
            raise AssertionError(f"crossed REST quote: {ticker} {sip_raw}")
    return row


def normalize_live_event(
    value: Mapping[str, Any], *, session: str, arrival_timestamp_utc: str
) -> dict[str, Any]:
    event_code = str(value.get("ev", "")).upper()
    event_kind = {"T": "trade", "Q": "quote"}.get(event_code)
    if event_kind is None:
        raise AssertionError(f"unsupported live event: {event_code!r}")
    ticker, _ = normalize_contract_ticker(value.get("sym"))
    sip_raw, sip_ms = _live_timestamp_ms(value.get("t"), "t")
    arrival = datetime.fromisoformat(arrival_timestamp_utc.replace("Z", "+00:00"))
    if arrival.tzinfo is None:
        raise AssertionError("live arrival timestamp must be timezone-aware")
    row = _empty_event(
        ticker=ticker,
        session=session,
        event_kind=event_kind,
        sip_raw=sip_raw,
        sip_ms=sip_ms,
        participant_raw=None,
        sequence=_integer(value.get("q"), "q"),
        arrival=arrival.astimezone(timezone.utc).isoformat(),
        transport="websocket",
    )
    if event_kind == "trade":
        row.update(
            {
                "trade_price": _decimal_text(value.get("p"), "p"),
                "trade_size": _integer(value.get("s"), "s", minimum=1),
                "trade_exchange": _integer(value.get("x"), "x"),
                "trade_conditions": _conditions(value.get("c"), "trade_conditions"),
                "trade_correction": None,
            }
        )
    else:
        row.update(
            {
                "bid_price": _decimal_text(value.get("bp"), "bp"),
                "ask_price": _decimal_text(value.get("ap"), "ap"),
                "bid_size": _integer(value.get("bs"), "bs"),
                "ask_size": _integer(value.get("as"), "as"),
                "bid_exchange": _integer(value.get("bx"), "bx"),
                "ask_exchange": _integer(value.get("ax"), "ax"),
                "quote_conditions": _conditions(value.get("c"), "quote_conditions"),
            }
        )
        if Decimal(row["bid_price"]) > Decimal(row["ask_price"]):
            raise AssertionError(f"crossed live quote: {ticker} {sip_raw}")
    return row


def event_identity(row: Mapping[str, Any]) -> tuple[str, str, int, int]:
    return (
        str(row["contract_ticker"]),
        str(row["event_kind"]),
        int(row["sip_timestamp_ms"]),
        int(row["sequence_number"]),
    )


def comparison_record(
    row: Mapping[str, Any], *, correction_contract_present: bool
) -> dict[str, Any]:
    value = {field: row.get(field) for field in COMPARISON_FIELDS}
    if row["event_kind"] == "trade" and correction_contract_present:
        correction = value["trade_correction"]
        if correction in {None, 0}:
            value["trade_correction"] = 0
    return value


def validate_event_sequence(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    previous: dict[tuple[str, str], int] = {}
    identities: set[tuple[str, str, int, int]] = set()
    counts: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        identity = event_identity(row)
        if identity in identities:
            raise AssertionError(f"duplicate canonical event: {identity}")
        identities.add(identity)
        group = (identity[0], identity[1])
        sequence = identity[3]
        if group in previous and sequence <= previous[group]:
            raise AssertionError(
                f"non-increasing sequence: {group} {previous[group]} -> {sequence}"
            )
        previous[group] = sequence
        counts[identity[1]] += 1
    return {"events": len(identities), **dict(sorted(counts.items()))}


def strict_predecessor_audit(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    quotes: defaultdict[str, list[int]] = defaultdict(list)
    trades: list[Mapping[str, Any]] = []
    for row in rows:
        if row["event_kind"] == "quote":
            quotes[str(row["contract_ticker"])].append(int(row["sip_timestamp_ms"]))
        else:
            trades.append(row)
    for values in quotes.values():
        values.sort()
    with_predecessor = 0
    without_predecessor = 0
    same_millisecond_ties = 0
    for trade in trades:
        ticker = str(trade["contract_ticker"])
        timestamp = int(trade["sip_timestamp_ms"])
        values = quotes[ticker]
        if timestamp in values:
            same_millisecond_ties += 1
        if any(value < timestamp for value in values):
            with_predecessor += 1
        else:
            without_predecessor += 1
    return {
        "trades": len(trades),
        "with_strict_predecessor": with_predecessor,
        "without_strict_predecessor": without_predecessor,
        "same_millisecond_ties": same_millisecond_ties,
    }


def ensure_finite_json(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise AssertionError("non-finite JSON value")
    if isinstance(value, dict):
        for item in value.values():
            ensure_finite_json(item)
    elif isinstance(value, list):
        for item in value:
            ensure_finite_json(item)
