"""Typed, entitlement-aware adapter for the documented ThetaData v3 routes.

The adapter deliberately has a small allow-list of routes which are supported by
the deployed Options STANDARD terminal.  It never calls direct index routes and
it never turns a provider exception into a user-facing string.  Consumers get
typed values, a safe error code and timestamped provenance instead.

This module is intentionally independent from the KING NODE engine.  That keeps
provider parsing, entitlement detection and market-session handling testable with
sanitised fixtures and prevents a failed provider refresh from contaminating a
previously sealed calculation artifact.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from enum import Enum
import hashlib
import json
import math
import random
import threading
import time as monotonic_time
from typing import Any, Callable, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

import httpx

from modules.volatility_indices import (
    ET,
    finite_number,
    flatten_theta_rows,
    iso_utc,
    parse_expiration,
    parse_timestamp,
)


THETA_PROVIDER = "ThetaData"
THETA_API_VERSION = "v3"
OPTIONS_STANDARD = "STANDARD"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_AGE_SECONDS = 180.0
DEFAULT_MAX_ATTEMPTS = 3


class ThetaRoute(str, Enum):
    """Documented v3 routes used by this application."""

    MDDS_STATUS = "terminal/mdds/status"
    FPSS_STATUS = "terminal/fpss/status"
    OPTION_EXPIRATIONS = "option/list/expirations"
    OPTION_QUOTE = "option/snapshot/quote"
    OPTION_FIRST_ORDER = "option/snapshot/greeks/first_order"
    OPTION_OPEN_INTEREST = "option/snapshot/open_interest"
    RATE_EOD = "interest_rate/history/eod"


class ErrorCode(str, Enum):
    """Stable, non-secret errors exposed across the producer/API boundary."""

    TERMINAL_UNREACHABLE = "TERMINAL_UNREACHABLE"
    TERMINAL_NOT_READY = "TERMINAL_NOT_READY"
    PROVIDER_DISCONNECTED = "PROVIDER_DISCONNECTED"
    ENTITLEMENT_DENIED = "ENTITLEMENT_DENIED"
    PROVIDER_NO_DATA = "PROVIDER_NO_DATA"
    INVALID_PROVIDER_REQUEST = "INVALID_PROVIDER_REQUEST"
    PROVIDER_THROTTLED = "PROVIDER_THROTTLED"
    PROVIDER_INTERNAL = "PROVIDER_INTERNAL"
    PROVIDER_SCHEMA_INVALID = "PROVIDER_SCHEMA_INVALID"
    STALE_INPUT = "STALE_INPUT"
    INPUT_INCOHERENT = "INPUT_INCOHERENT"
    CALENDAR_CLOSED = "CALENDAR_CLOSED"
    PROVIDER_CAPABILITY_MISSING = "PROVIDER_CAPABILITY_MISSING"


class ThetaDataError(RuntimeError):
    """A safe provider failure.  ``detail`` is retained only in process logs."""

    def __init__(
        self,
        code: ErrorCode,
        *,
        route: ThetaRoute | str | None = None,
        status_code: int | None = None,
        retryable: bool = False,
        detail: str | None = None,
    ) -> None:
        self.code = code
        self.route = route.value if isinstance(route, ThetaRoute) else route
        self.status_code = status_code
        self.retryable = retryable
        self.detail = detail
        super().__init__(code.value)

    def safe_dict(self, component: str = "thetadata") -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code.value,
            "component": component,
            "retryable": self.retryable,
        }
        if self.status_code is not None:
            result["provider_status"] = self.status_code
        if self.route:
            result["route"] = self.route
        return result


class SessionState(str, Enum):
    PREOPEN = "PREOPEN"
    LIVE_RTH = "LIVE_RTH"
    POST_CLOSE = "POST_CLOSE"
    WEEKEND = "WEEKEND"
    HOLIDAY = "HOLIDAY"


@dataclass(frozen=True)
class MarketSession:
    trading_date: str
    state: SessionState
    market_open: datetime | None
    market_close: datetime | None
    option_close: datetime | None
    is_half_day: bool
    calendar: str

    @property
    def live(self) -> bool:
        return self.state is SessionState.LIVE_RTH

    def to_dict(self) -> dict[str, Any]:
        return {
            "trading_date": self.trading_date,
            "state": self.state.value,
            "market_open": iso_utc(self.market_open) if self.market_open else None,
            "market_close": iso_utc(self.market_close) if self.market_close else None,
            "option_close": iso_utc(self.option_close) if self.option_close else None,
            "is_half_day": self.is_half_day,
            "calendar": self.calendar,
        }


class MarketCalendar:
    """Exchange-calendar backed clock for SPX/SPXW option-session decisions.

    XNYS supplies authoritative open/holiday/early-close days.  PM-settled SPXW
    options trade fifteen minutes past that cash close, including on early closes;
    the explicit offset makes that convention visible and testable instead of
    scattering a hard-coded 16:15 clock through volatility calculations.
    """

    def __init__(
        self,
        calendar_name: str = "XNYS",
        *,
        option_close_offset_minutes: int = 15,
        calendar: Any | None = None,
    ) -> None:
        self.calendar_name = calendar_name
        self.option_close_offset = timedelta(minutes=option_close_offset_minutes)
        if calendar is None:
            try:
                import exchange_calendars as xcals

                calendar = xcals.get_calendar(calendar_name)
            except Exception as exc:  # pragma: no cover - dependency/runtime guard
                raise RuntimeError("exchange calendar is unavailable") from exc
        self._calendar = calendar

    @staticmethod
    def _as_utc(value: Any) -> datetime:
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()
        if not isinstance(value, datetime):
            raise TypeError("calendar timestamp is not datetime-like")
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _schedule_for(self, day: date) -> tuple[datetime, datetime] | None:
        try:
            schedule = self._calendar.schedule.loc[str(day)]
        except Exception:
            return None
        try:
            # exchange_calendars 4.x exposes ``open``/``close`` while older
            # releases used ``market_open``/``market_close``.
            opened = schedule.get("market_open", schedule.get("open"))
            closed = schedule.get("market_close", schedule.get("close"))
            return self._as_utc(opened), self._as_utc(closed)
        except (KeyError, TypeError, ValueError):
            return None

    def session_at(self, now: datetime) -> MarketSession:
        now = now.astimezone(UTC)
        local_date = now.astimezone(ET).date()
        schedule = self._schedule_for(local_date)
        if schedule is None:
            state = (
                SessionState.WEEKEND
                if local_date.weekday() >= 5
                else SessionState.HOLIDAY
            )
            return MarketSession(
                trading_date=local_date.isoformat(),
                state=state,
                market_open=None,
                market_close=None,
                option_close=None,
                is_half_day=False,
                calendar=self.calendar_name,
            )
        market_open, market_close = schedule
        option_close = market_close + self.option_close_offset
        normal_cash_minutes = 390
        cash_minutes = (market_close - market_open).total_seconds() / 60.0
        is_half_day = cash_minutes < normal_cash_minutes
        if now < market_open:
            state = SessionState.PREOPEN
        elif now <= option_close:
            state = SessionState.LIVE_RTH
        else:
            state = SessionState.POST_CLOSE
        return MarketSession(
            trading_date=local_date.isoformat(),
            state=state,
            market_open=market_open,
            market_close=market_close,
            option_close=option_close,
            is_half_day=is_half_day,
            calendar=self.calendar_name,
        )

    def option_session_minutes_until(self, now: datetime, expiration: date) -> float:
        """Count tradable option minutes through the PM option close.

        This is used for short-horizon methodology diagnostics.  It honours early
        closes through the installed exchange calendar and returns zero for an
        already expired contract.
        """

        now = now.astimezone(UTC)
        local_day = now.astimezone(ET).date()
        if expiration < local_day:
            return 0.0
        total = 0.0
        cursor = local_day
        while cursor <= expiration:
            schedule = self._schedule_for(cursor)
            if schedule is not None:
                open_at, cash_close = schedule
                option_close = cash_close + self.option_close_offset
                start = max(now, open_at) if cursor == local_day else open_at
                if option_close > start:
                    total += (option_close - start).total_seconds() / 60.0
            cursor += timedelta(days=1)
        return max(0.0, total)

    def calendar_minutes_until(self, now: datetime, expiration: date) -> float:
        schedule = self._schedule_for(expiration)
        if schedule is None:
            return 0.0
        _, cash_close = schedule
        expiry = cash_close + self.option_close_offset
        return max(0.0, (expiry - now.astimezone(UTC)).total_seconds() / 60.0)


@dataclass(frozen=True)
class ProvenancedValue:
    value: float | None
    provenance: str
    methodology: str | None = None
    source_fields: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"value": self.value, "provenance": self.provenance}
        if self.methodology:
            result["methodology"] = self.methodology
        if self.source_fields:
            result["source_fields"] = list(self.source_fields)
        return result


@dataclass(frozen=True)
class NormalizedOptionInput:
    underlying_symbol: str
    option_root: str
    expiry: str
    strike: float
    right: str
    bid: float
    ask: float
    quote_timestamp: str
    underlying_price: float | None
    underlying_timestamp: str | None
    open_interest: float | None
    open_interest_source_date: str | None
    iv: float | None
    delta: float | None
    theta: float | None
    rate: float | None
    time_to_expiry: float | None
    advanced_greeks: Mapping[str, ProvenancedValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["advanced_greeks"] = {
            key: value.to_dict()
            for key, value in sorted(self.advanced_greeks.items())
        }
        return result


@dataclass(frozen=True)
class IndexResult:
    name: str
    value: float | None
    mode: str
    provider: str
    as_of: str | None
    session_date: str | None
    inputs_age_seconds: float | None
    methodology_version: str
    diagnostics: Mapping[str, Any]
    quality: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TerminalReadiness:
    mdds: str
    fpss: str
    checked_at: str

    @property
    def ready(self) -> bool:
        return self.mdds == "CONNECTED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"ready": self.ready}


@dataclass(frozen=True)
class Entitlements:
    stock: str = "FREE"
    options: str = OPTIONS_STANDARD
    index: str = "FREE"
    rate: str = "FREE"
    observed_at: str | None = None

    @property
    def supports_direct_index(self) -> bool:
        return self.index.upper() not in {"", "FREE", "NONE"}

    @property
    def supports_advanced_greeks(self) -> bool:
        return self.options.upper() == "PRO"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stock": self.stock,
            "options": self.options,
            "index": self.index,
            "rate": self.rate,
            "supports_direct_index": self.supports_direct_index,
            "supports_advanced_greeks": self.supports_advanced_greeks,
            "observed_at": self.observed_at,
        }


class RateLimiter:
    """Small deterministic limiter; injected clock/sleeper make it testable."""

    def __init__(
        self,
        minimum_interval_seconds: float = 0.26,
        *,
        clock: Callable[[], float] = monotonic_time.monotonic,
        sleeper: Callable[[float], None] = monotonic_time.sleep,
    ) -> None:
        self.minimum_interval_seconds = max(0.0, float(minimum_interval_seconds))
        self._clock = clock
        self._sleeper = sleeper
        self._lock = threading.Lock()
        self._next_at = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = self._clock()
            delay = max(0.0, self._next_at - now)
            if delay:
                self._sleeper(delay)
            now = self._clock()
            self._next_at = max(now, self._next_at) + self.minimum_interval_seconds


def _safe_route(route: ThetaRoute | str) -> str:
    value = route.value if isinstance(route, ThetaRoute) else str(route).strip("/")
    allowed = {item.value for item in ThetaRoute}
    if value not in allowed:
        raise ThetaDataError(
            ErrorCode.INVALID_PROVIDER_REQUEST,
            route=value,
            retryable=False,
        )
    return value


def _provider_error(
    status_code: int,
    route: str,
    detail: str | None = None,
) -> ThetaDataError:
    if status_code in {401, 403, 471}:
        code, retryable = ErrorCode.ENTITLEMENT_DENIED, False
    elif status_code in {429}:
        code, retryable = ErrorCode.PROVIDER_THROTTLED, True
    elif status_code in {404, 473, 475, 477}:
        code, retryable = ErrorCode.INVALID_PROVIDER_REQUEST, False
    elif status_code in {472}:
        code, retryable = ErrorCode.PROVIDER_NO_DATA, False
    elif status_code in {474}:
        code, retryable = ErrorCode.PROVIDER_DISCONNECTED, True
    elif status_code in {571}:
        code, retryable = ErrorCode.TERMINAL_NOT_READY, True
    elif status_code >= 500 or status_code in {470, 572}:
        code, retryable = ErrorCode.PROVIDER_INTERNAL, True
    else:
        code, retryable = ErrorCode.PROVIDER_SCHEMA_INVALID, False
    return ThetaDataError(
        code,
        route=route,
        status_code=status_code,
        retryable=retryable,
        detail=detail,
    )


def canonical_right(value: Any) -> str | None:
    raw = str(value or "").strip().upper()
    if raw in {"C", "CALL"}:
        return "CALL"
    if raw in {"P", "PUT"}:
        return "PUT"
    return None


def canonical_strike(value: Any, *, scale: float | None = None) -> float | None:
    parsed = finite_number(value)
    if parsed is None or parsed <= 0:
        return None
    if scale is not None:
        if scale <= 0:
            return None
        parsed /= scale
    elif abs(parsed) >= 100_000:
        # Theta routes normally return dollar strikes.  Some captured/vendor
        # fixtures represent strikes in mills; only values clearly outside index
        # strike ranges are scaled automatically.
        parsed /= 1_000.0
    return round(parsed, 8)


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _clean_number(value: Any) -> float | None:
    parsed = finite_number(value)
    return parsed if parsed is not None and math.isfinite(parsed) else None


def _source_day(value: datetime | None) -> str | None:
    return value.astimezone(ET).date().isoformat() if value else None


def derive_advanced_greeks(
    *,
    spot: float | None,
    strike: float,
    iv: float | None,
    rate: float | None,
    time_to_expiry: float | None,
) -> dict[str, ProvenancedValue]:
    """Black-Scholes analytic higher Greeks, explicitly model-derived.

    The function intentionally returns an empty mapping rather than a guessed
    number when inputs are insufficient.  Definitions assume zero dividends;
    that assumption is recorded in the field provenance name.
    """

    if (
        spot is None
        or iv is None
        or rate is None
        or time_to_expiry is None
        or spot <= 0
        or strike <= 0
        or iv <= 0
        or time_to_expiry <= 0
    ):
        return {}
    root_t = math.sqrt(time_to_expiry)
    sigma_root_t = iv * root_t
    if sigma_root_t <= 0:
        return {}
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * time_to_expiry) / sigma_root_t
    d2 = d1 - sigma_root_t
    phi = math.exp(-0.5 * d1 * d1) / math.sqrt(2.0 * math.pi)
    gamma = phi / (spot * sigma_root_t)
    vega = spot * phi * root_t
    vanna = -phi * d2 / iv
    vomma = vega * d1 * d2 / iv
    zomma = gamma * (d1 * d2 - 1.0) / iv
    speed = -gamma / spot * (d1 / sigma_root_t + 1.0)
    charm = -phi * (2.0 * rate * time_to_expiry - d2 * sigma_root_t) / (
        2.0 * time_to_expiry * sigma_root_t
    )
    # Per-contract one-percent gamma-notional proxy.  This is not an observed
    # dealer exposure: OI and multiplier are applied later by the engine.
    dgex = gamma * spot * spot * 0.01
    if not all(
        math.isfinite(item)
        for item in (gamma, zomma, vanna, vomma, vega, speed, charm, dgex)
    ):
        return {}
    methodology = "black_scholes_zero_dividend_analytic_v1"
    sources = ("underlying_price", "strike", "iv", "rate", "time_to_expiry")
    return {
        "gamma": ProvenancedValue(gamma, "model_derived", methodology, sources),
        "zomma": ProvenancedValue(zomma, "model_derived", methodology, sources),
        "vanna": ProvenancedValue(vanna, "model_derived", methodology, sources),
        "vomma": ProvenancedValue(vomma, "model_derived", methodology, sources),
        "vega": ProvenancedValue(vega, "model_derived", methodology, sources),
        "speed": ProvenancedValue(speed, "model_derived", methodology, sources),
        "charm": ProvenancedValue(charm, "model_derived", methodology, sources),
        "dgex": ProvenancedValue(
            dgex,
            "model_derived",
            "black_scholes_per_contract_one_percent_gamma_notional_v1",
            sources,
        ),
    }


def normalize_option_rows(
    quote_payload: Any,
    *,
    greek_payload: Any | None,
    open_interest_payload: Any | None,
    now: datetime,
    max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
    rate: float | None = None,
    time_to_expiry: Callable[[date], float | None] | None = None,
    default_symbol: str = "SPXW",
    default_expiry: date | None = None,
    strike_scale: float | None = None,
) -> list[NormalizedOptionInput]:
    """Normalize, validate and deterministically deduplicate Theta responses."""

    now = now.astimezone(UTC)

    def indexed(payload: Any | None) -> dict[tuple[str, str, float, str], Mapping[str, Any]]:
        values: dict[tuple[str, str, float, str], Mapping[str, Any]] = {}
        for row in flatten_theta_rows(payload):
            symbol = str(_first(row, "symbol", "root") or default_symbol).upper()
            expiry = parse_expiration(_first(row, "expiration", "expiry")) or default_expiry
            strike = canonical_strike(_first(row, "strike", "strike_price"), scale=strike_scale)
            right = canonical_right(_first(row, "right", "option_type"))
            if expiry is None or strike is None or right is None:
                continue
            key = (symbol, expiry.isoformat(), strike, right)
            timestamp = parse_timestamp(_first(row, "timestamp", "quote_timestamp", "underlying_timestamp"))
            previous = values.get(key)
            previous_ts = parse_timestamp(_first(previous or {}, "timestamp", "quote_timestamp", "underlying_timestamp"))
            if previous is None or (timestamp and (previous_ts is None or timestamp > previous_ts)):
                values[key] = row
        return values

    greeks = indexed(greek_payload)
    interests = indexed(open_interest_payload)
    selected: dict[tuple[str, str, float, str], NormalizedOptionInput] = {}
    for row in flatten_theta_rows(quote_payload):
        symbol = str(_first(row, "symbol", "root") or default_symbol).upper()
        expiry_date = parse_expiration(_first(row, "expiration", "expiry")) or default_expiry
        strike = canonical_strike(_first(row, "strike", "strike_price"), scale=strike_scale)
        right = canonical_right(_first(row, "right", "option_type"))
        bid = _clean_number(_first(row, "bid", "bid_price"))
        ask = _clean_number(_first(row, "ask", "ask_price"))
        quote_at = parse_timestamp(_first(row, "timestamp", "quote_timestamp"))
        if (
            expiry_date is None
            or strike is None
            or right is None
            or bid is None
            or ask is None
            or quote_at is None
            or bid < 0
            or ask < bid
        ):
            continue
        age = max(0.0, (now - quote_at).total_seconds())
        if age > max_age_seconds:
            continue
        key = (symbol, expiry_date.isoformat(), strike, right)
        greek = greeks.get(key, {})
        interest = interests.get(key, {})
        underlying_price = _clean_number(_first(greek, "underlying_price"))
        underlying_at = parse_timestamp(
            _first(greek, "underlying_timestamp", "timestamp")
        )
        if underlying_at and max(0.0, (now - underlying_at).total_seconds()) > max_age_seconds:
            underlying_price, underlying_at = None, None
        iv = _clean_number(_first(greek, "implied_vol", "iv", "implied_volatility"))
        delta = _clean_number(_first(greek, "delta"))
        theta = _clean_number(_first(greek, "theta"))
        oi = _clean_number(_first(interest, "open_interest", "oi"))
        oi_at = parse_timestamp(_first(interest, "timestamp", "created", "date"))
        expiry_time = time_to_expiry(expiry_date) if time_to_expiry else None
        advanced = derive_advanced_greeks(
            spot=underlying_price,
            strike=strike,
            iv=iv,
            rate=rate,
            time_to_expiry=expiry_time,
        )
        normalized = NormalizedOptionInput(
            underlying_symbol=symbol,
            option_root=symbol,
            expiry=expiry_date.isoformat(),
            strike=strike,
            right=right,
            bid=bid,
            ask=ask,
            quote_timestamp=iso_utc(quote_at),
            underlying_price=underlying_price,
            underlying_timestamp=iso_utc(underlying_at) if underlying_at else None,
            open_interest=oi,
            open_interest_source_date=_source_day(oi_at),
            iv=iv,
            delta=delta,
            theta=theta,
            rate=rate,
            time_to_expiry=expiry_time,
            advanced_greeks=advanced,
        )
        previous = selected.get(key)
        if previous is None or normalized.quote_timestamp > previous.quote_timestamp:
            selected[key] = normalized
    return [selected[key] for key in sorted(selected)]


def content_hash(payload: Any) -> str:
    """Stable hash for sealed artifacts and non-secret provenance."""

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ThetaDataV3Client:
    """Bounded v3 transport with safe errors and fixed route allow-list."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        limiter: RateLimiter | None = None,
        client: httpx.Client | None = None,
        jitter: Callable[[], float] = random.random,
        sleeper: Callable[[float], None] = monotonic_time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self.max_attempts = max(1, int(max_attempts))
        self.limiter = limiter or RateLimiter()
        self.client = client or httpx.Client(timeout=self.timeout_seconds)
        self._owns_client = client is None
        self._jitter = jitter
        self._sleeper = sleeper
        self.metrics: dict[str, int | float] = {
            "requests": 0,
            "provider_errors": 0,
            "retries": 0,
        }

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _request(
        self,
        route: ThetaRoute | str,
        *,
        params: Mapping[str, Any] | None = None,
        text: bool = False,
    ) -> Any:
        route_text = _safe_route(route)
        request_params = dict(params or {})
        if not text:
            request_params["format"] = "json"
        last_error: ThetaDataError | None = None
        for attempt in range(self.max_attempts):
            self.limiter.acquire()
            started = monotonic_time.monotonic()
            try:
                response = self.client.get(
                    f"{self.base_url}/{route_text}",
                    params=request_params,
                    headers={"Accept": "text/plain" if text else "application/json"},
                    timeout=self.timeout_seconds,
                )
            except httpx.RequestError as exc:
                last_error = ThetaDataError(
                    ErrorCode.TERMINAL_UNREACHABLE,
                    route=route_text,
                    retryable=True,
                    detail=type(exc).__name__,
                )
            else:
                self.metrics["requests"] = int(self.metrics["requests"]) + 1
                self.metrics["last_latency_ms"] = round(
                    (monotonic_time.monotonic() - started) * 1_000.0, 3
                )
                if response.status_code >= 400:
                    last_error = _provider_error(
                        response.status_code,
                        route_text,
                        response.text[:512],
                    )
                elif text:
                    return response.text.strip().upper()
                else:
                    try:
                        payload = response.json()
                    except (json.JSONDecodeError, ValueError) as exc:
                        last_error = ThetaDataError(
                            ErrorCode.PROVIDER_SCHEMA_INVALID,
                            route=route_text,
                            status_code=response.status_code,
                            retryable=False,
                            detail=type(exc).__name__,
                        )
                    else:
                        provider_code = None
                        if isinstance(payload, Mapping):
                            provider_code = payload.get("error_code")
                        if provider_code:
                            try:
                                numeric_code = int(provider_code)
                            except (TypeError, ValueError):
                                numeric_code = response.status_code
                            last_error = _provider_error(
                                numeric_code,
                                route_text,
                                str(payload.get("message", ""))[:512]
                                if isinstance(payload, Mapping)
                                else None,
                            )
                        else:
                            return payload
            assert last_error is not None
            self.metrics["provider_errors"] = int(self.metrics["provider_errors"]) + 1
            if not last_error.retryable or attempt + 1 >= self.max_attempts:
                raise last_error
            self.metrics["retries"] = int(self.metrics["retries"]) + 1
            self._sleeper(min(1.0, 0.1 * (2**attempt) + self._jitter() * 0.05))
        raise last_error or ThetaDataError(ErrorCode.PROVIDER_INTERNAL)

    def readiness(self, *, now: datetime | None = None) -> TerminalReadiness:
        checked = (now or datetime.now(UTC)).astimezone(UTC)
        mdds = self._request(ThetaRoute.MDDS_STATUS, text=True)
        fpss = self._request(ThetaRoute.FPSS_STATUS, text=True)
        return TerminalReadiness(mdds=mdds, fpss=fpss, checked_at=iso_utc(checked))

    def expirations(self, symbol: str) -> list[date]:
        payload = self._request(ThetaRoute.OPTION_EXPIRATIONS, params={"symbol": symbol.upper()})
        result = sorted(
            {
                parsed
                for row in flatten_theta_rows(payload)
                if (parsed := parse_expiration(_first(row, "expiration", "date", "value")))
                is not None
            }
        )
        if not result:
            raise ThetaDataError(
                ErrorCode.PROVIDER_NO_DATA,
                route=ThetaRoute.OPTION_EXPIRATIONS,
                retryable=False,
            )
        return result

    def option_snapshot(self, route: ThetaRoute, *, symbol: str, expiration: date) -> Any:
        if route not in {
            ThetaRoute.OPTION_QUOTE,
            ThetaRoute.OPTION_FIRST_ORDER,
            ThetaRoute.OPTION_OPEN_INTEREST,
        }:
            raise ThetaDataError(ErrorCode.INVALID_PROVIDER_REQUEST, route=route)
        params = {
            "symbol": symbol.upper(),
            "expiration": expiration.strftime("%Y%m%d"),
            "strike": "*",
            "right": "both",
        }
        if route is ThetaRoute.OPTION_FIRST_ORDER:
            params["version"] = "latest"
        return self._request(route, params=params)

    def option_chain(
        self,
        *,
        symbol: str,
        expiration: date,
        now: datetime,
        rate: float | None,
        calendar: MarketCalendar,
        max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
    ) -> list[NormalizedOptionInput]:
        quote = self.option_snapshot(ThetaRoute.OPTION_QUOTE, symbol=symbol, expiration=expiration)
        greeks = self.option_snapshot(
            ThetaRoute.OPTION_FIRST_ORDER, symbol=symbol, expiration=expiration
        )
        oi = self.option_snapshot(
            ThetaRoute.OPTION_OPEN_INTEREST, symbol=symbol, expiration=expiration
        )
        return normalize_option_rows(
            quote,
            greek_payload=greeks,
            open_interest_payload=oi,
            now=now,
            max_age_seconds=max_age_seconds,
            rate=rate,
            time_to_expiry=lambda expiry: calendar.calendar_minutes_until(now, expiry)
            / (365.0 * 24.0 * 60.0),
            default_symbol=symbol,
            default_expiry=expiration,
        )

    def sofr(self, *, now: datetime, lookback_days: int = 10) -> dict[str, Any]:
        local_day = now.astimezone(ET).date()
        payload = self._request(
            ThetaRoute.RATE_EOD,
            params={
                "symbol": "SOFR",
                "start_date": (local_day - timedelta(days=max(1, lookback_days))).strftime("%Y%m%d"),
                "end_date": local_day.strftime("%Y%m%d"),
            },
        )
        rows: list[tuple[datetime, float]] = []
        for row in flatten_theta_rows(payload):
            observed = parse_timestamp(_first(row, "created", "date", "timestamp"))
            value = _clean_number(_first(row, "rate", "value", "close"))
            if observed is not None and value is not None:
                rows.append((observed, value))
        if not rows:
            raise ThetaDataError(ErrorCode.PROVIDER_NO_DATA, route=ThetaRoute.RATE_EOD)
        observed, value = max(rows, key=lambda item: item[0])
        return {
            "symbol": "SOFR",
            "value_percent": value,
            "value_decimal": value / 100.0,
            "as_of": iso_utc(observed),
            "source_session_date": _source_day(observed),
            "provider": THETA_PROVIDER,
            "route": ThetaRoute.RATE_EOD.value,
        }


def safe_quality_error(error: Exception, *, component: str) -> dict[str, Any]:
    """Convert arbitrary failures to contract-safe diagnostic metadata."""

    if isinstance(error, ThetaDataError):
        return error.safe_dict(component)
    return {
        "code": ErrorCode.PROVIDER_INTERNAL.value,
        "component": component,
        "retryable": False,
    }


__all__ = [
    "DEFAULT_MAX_AGE_SECONDS",
    "Entitlements",
    "ErrorCode",
    "IndexResult",
    "MarketCalendar",
    "MarketSession",
    "NormalizedOptionInput",
    "OPTIONS_STANDARD",
    "ProvenancedValue",
    "RateLimiter",
    "SessionState",
    "TerminalReadiness",
    "THETA_API_VERSION",
    "THETA_PROVIDER",
    "ThetaDataError",
    "ThetaDataV3Client",
    "ThetaRoute",
    "canonical_right",
    "canonical_strike",
    "content_hash",
    "derive_advanced_greeks",
    "normalize_option_rows",
    "safe_quality_error",
]
