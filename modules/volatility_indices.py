"""Reconstruct VIX-family inputs from ThetaData Options STANDARD.

The module contains no network code.  It accepts ThetaData option quote/Greek
rows and implements the variance-swap calculation used by Cboe volatility
indices.  The resulting values are replicas, not official Cboe index prints.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
import math
from statistics import median
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MINUTES_PER_YEAR = 365 * 24 * 60
VIX1D_SESSION_MINUTES = 405
VIX1D_MINUTES_PER_YEAR = 252 * VIX1D_SESSION_MINUTES
VVIX_TARGET_MINUTES = 30 * 24 * 60


class VolatilityDataError(ValueError):
    """Raised when an option surface cannot produce an auditable value."""


@dataclass(frozen=True)
class OptionQuote:
    strike: float
    right: str
    bid: float
    ask: float
    timestamp: datetime
    expiration: date | None = None

    @property
    def midpoint(self) -> float:
        return (self.bid + self.ask) / 2.0


@dataclass(frozen=True)
class TermVariance:
    expiration: str
    minutes: float
    time_years: float
    rate_decimal: float
    forward: float
    k0: float
    variance: float
    atm_strike: float
    included_strikes: tuple[float, ...]
    rejected_strikes: tuple[float, ...]
    call_count: int
    put_count: int
    quote_count: int
    max_quote_age_seconds: float

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["included_strikes"] = list(self.included_strikes)
        result["rejected_strikes"] = list(self.rejected_strikes)
        return result


@dataclass(frozen=True)
class UnderlyingObservation:
    value: float
    timestamp: datetime
    age_seconds: float
    count: int
    mad: float
    dispersion_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "timestamp": iso_utc(self.timestamp),
            "age_seconds": self.age_seconds,
            "count": self.count,
            "mad": self.mad,
            "dispersion_pct": self.dispersion_pct,
        }


def finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def parse_timestamp(value: Any, *, default_zone: ZoneInfo = ET) -> datetime | None:
    """Parse ISO strings and second/millisecond/microsecond/nanosecond epochs."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        raw = float(value)
        magnitude = abs(raw)
        if magnitude > 1e17:
            raw /= 1e9
        elif magnitude > 1e14:
            raw /= 1e6
        elif magnitude > 1e11:
            raw /= 1e3
        try:
            parsed = datetime.fromtimestamp(raw, UTC)
        except (OSError, OverflowError, ValueError):
            return None
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            for fmt in ("%Y%m%d%H%M%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    parsed = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            else:
                return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_zone)
    return parsed.astimezone(UTC)


def iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_expiration(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, Mapping):
        for key in ("expiration", "date", "value"):
            if key in value:
                parsed = parse_expiration(value[key])
                if parsed is not None:
                    return parsed
        return None
    text = str(value or "").strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def flatten_theta_rows(payload: Any) -> list[dict[str, Any]]:
    """Flatten v3 flat responses and contract/data nested responses."""
    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            rows.extend(flatten_theta_rows(item))
        return rows
    if not isinstance(payload, Mapping):
        return rows

    contract = payload.get("contract")
    data = payload.get("data")
    if isinstance(contract, Mapping) and isinstance(data, list):
        for item in data:
            if isinstance(item, Mapping):
                rows.append({**contract, **item})
        return rows

    row_markers = {
        "strike", "strike_price", "bid", "ask", "underlying_price",
        "expiration", "right", "timestamp", "underlying_timestamp", "rate", "date", "type",
    }
    if row_markers.intersection(payload):
        rows.append(dict(payload))

    for key in ("response", "result", "items", "rows"):
        if key in payload:
            rows.extend(flatten_theta_rows(payload[key]))
    if "data" in payload and not isinstance(contract, Mapping):
        rows.extend(flatten_theta_rows(payload["data"]))
    return rows


def _right(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if text in {"C", "CALL"}:
        return "C"
    if text in {"P", "PUT"}:
        return "P"
    return None


def normalize_option_quotes(
    payload: Any,
    *,
    now: datetime,
    max_age_seconds: float,
    default_expiration: date | None = None,
) -> list[OptionQuote]:
    now = now.astimezone(UTC)
    output: list[OptionQuote] = []
    for row in flatten_theta_rows(payload):
        strike = finite_number(row.get("strike", row.get("strike_price")))
        bid = finite_number(row.get("bid", row.get("bid_price")))
        ask = finite_number(row.get("ask", row.get("ask_price")))
        right = _right(row.get("right", row.get("option_type")))
        timestamp = parse_timestamp(
            row.get("timestamp", row.get("quote_timestamp"))
        )
        if None in (strike, bid, ask, right, timestamp):
            continue
        assert strike is not None and bid is not None and ask is not None
        assert right is not None and timestamp is not None
        if strike <= 0 or bid < 0 or ask < bid:
            continue
        age = max(0.0, (now - timestamp).total_seconds())
        if age > max_age_seconds:
            continue
        expiration = parse_expiration(row.get("expiration")) or default_expiration
        output.append(OptionQuote(strike, right, bid, ask, timestamp, expiration))
    return output


def derive_underlying_price(
    payload: Any,
    *,
    now: datetime,
    max_age_seconds: float,
    min_observations: int = 3,
    max_dispersion_pct: float = 0.10,
) -> UnderlyingObservation:
    now = now.astimezone(UTC)
    observations: list[tuple[float, datetime]] = []
    for row in flatten_theta_rows(payload):
        value = finite_number(row.get("underlying_price"))
        timestamp = parse_timestamp(
            row.get("underlying_timestamp", row.get("timestamp"))
        )
        if value is None or value <= 0 or timestamp is None:
            continue
        age = max(0.0, (now - timestamp).total_seconds())
        if age <= max_age_seconds:
            observations.append((value, timestamp))
    if len(observations) < min_observations:
        raise VolatilityDataError(
            f"only {len(observations)} fresh underlying observations; "
            f"need {min_observations}"
        )
    values = [item[0] for item in observations]
    center = median(values)
    absolute_deviations = [abs(value - center) for value in values]
    mad = median(absolute_deviations)
    dispersion_pct = (max(values) - min(values)) / center * 100.0
    if dispersion_pct > max_dispersion_pct:
        raise VolatilityDataError(
            f"underlying dispersion {dispersion_pct:.6f}% exceeds "
            f"{max_dispersion_pct:.6f}%"
        )
    newest = max(timestamp for _, timestamp in observations)
    return UnderlyingObservation(
        value=center,
        timestamp=newest,
        age_seconds=max(0.0, (now - newest).total_seconds()),
        count=len(observations),
        mad=mad,
        dispersion_pct=dispersion_pct,
    )


def _latest_by_strike_right(quotes: Iterable[OptionQuote]) -> dict[float, dict[str, OptionQuote]]:
    chain: dict[float, dict[str, OptionQuote]] = {}
    for quote in quotes:
        current = chain.setdefault(quote.strike, {}).get(quote.right)
        if current is None or quote.timestamp > current.timestamp:
            chain[quote.strike][quote.right] = quote
    return chain


def _positive_quote(quote: OptionQuote | None) -> bool:
    return quote is not None and quote.bid > 0 and quote.ask > 0


def _business_day(day: date, holidays: set[date]) -> bool:
    return day.weekday() < 5 and day not in holidays


def business_minutes_to_spxw_expiration(
    now: datetime,
    expiration: date,
    *,
    holidays: set[date] | None = None,
) -> float:
    """Approximate the VIX1D 405-minute business clock through 16:15 ET."""
    holidays = holidays or set()
    local = now.astimezone(ET)
    session_open = time(9, 30)
    session_close = time(16, 15)
    if expiration < local.date():
        return 0.0
    total = 0.0
    cursor = local.date()
    while cursor <= expiration:
        if _business_day(cursor, holidays):
            if cursor == local.date():
                if local.time() >= session_close:
                    minutes = 0.0
                elif local.time() <= session_open:
                    minutes = float(VIX1D_SESSION_MINUTES)
                else:
                    close_dt = datetime.combine(cursor, session_close, ET)
                    minutes = max(0.0, (close_dt - local).total_seconds() / 60.0)
            else:
                minutes = float(VIX1D_SESSION_MINUTES)
            total += minutes
        cursor += timedelta(days=1)
    return total


def calendar_minutes_to_expiration(
    now: datetime,
    expiration: date,
    *,
    settlement_time: time,
) -> float:
    settlement = datetime.combine(expiration, settlement_time, ET).astimezone(UTC)
    return max(0.0, (settlement - now.astimezone(UTC)).total_seconds() / 60.0)


def calculate_term_variance(
    quotes: Sequence[OptionQuote],
    *,
    expiration: date,
    minutes_to_expiration: float,
    minutes_per_year: float,
    rate_decimal: float,
    min_valid_strikes: int = 8,
    as_of: datetime | None = None,
) -> TermVariance:
    if minutes_to_expiration <= 0:
        raise VolatilityDataError("expiration has no positive time remaining")
    if minutes_per_year <= 0:
        raise VolatilityDataError("minutes_per_year must be positive")
    if not math.isfinite(rate_decimal):
        raise VolatilityDataError("risk-free rate is invalid")
    time_years = minutes_to_expiration / minutes_per_year
    chain = _latest_by_strike_right(quotes)
    paired: list[tuple[float, OptionQuote, OptionQuote]] = []
    for strike, sides in chain.items():
        call = sides.get("C")
        put = sides.get("P")
        if _positive_quote(call) and _positive_quote(put):
            assert call is not None and put is not None
            paired.append((strike, call, put))
    if not paired:
        raise VolatilityDataError("no strike has valid call and put quotes")
    atm_strike, atm_call, atm_put = min(
        paired,
        key=lambda item: (abs(item[1].midpoint - item[2].midpoint), item[0]),
    )
    forward = atm_strike + math.exp(rate_decimal * time_years) * (
        atm_call.midpoint - atm_put.midpoint
    )
    strikes = sorted(chain)
    below = [strike for strike in strikes if strike <= forward]
    if not below:
        raise VolatilityDataError("no K0 strike exists below the implied forward")
    k0 = max(below)

    selected: dict[float, float] = {}
    rejected: list[float] = []
    call_count = 0
    put_count = 0

    k0_call = chain.get(k0, {}).get("C")
    k0_put = chain.get(k0, {}).get("P")
    if not (_positive_quote(k0_call) and _positive_quote(k0_put)):
        raise VolatilityDataError("K0 lacks positive call and put NBBO quotes")
    assert k0_call is not None and k0_put is not None
    selected[k0] = (k0_call.midpoint + k0_put.midpoint) / 2.0

    zero_run = 0
    for strike in sorted((value for value in strikes if value < k0), reverse=True):
        quote = chain[strike].get("P")
        if not _positive_quote(quote):
            rejected.append(strike)
            zero_run += 1
            if zero_run >= 2:
                break
            continue
        zero_run = 0
        assert quote is not None
        selected[strike] = quote.midpoint
        put_count += 1

    zero_run = 0
    for strike in (value for value in strikes if value > k0):
        quote = chain[strike].get("C")
        if not _positive_quote(quote):
            rejected.append(strike)
            zero_run += 1
            if zero_run >= 2:
                break
            continue
        zero_run = 0
        assert quote is not None
        selected[strike] = quote.midpoint
        call_count += 1

    included = sorted(selected)
    if len(included) < min_valid_strikes:
        raise VolatilityDataError(
            f"only {len(included)} valid strikes; need {min_valid_strikes}"
        )
    if call_count == 0 or put_count == 0:
        raise VolatilityDataError("both OTM wings are required")

    contribution = 0.0
    for index, strike in enumerate(included):
        if index == 0:
            delta_k = included[1] - included[0]
        elif index == len(included) - 1:
            delta_k = included[-1] - included[-2]
        else:
            delta_k = (included[index + 1] - included[index - 1]) / 2.0
        if delta_k <= 0:
            raise VolatilityDataError("non-positive delta K")
        contribution += (
            delta_k / (strike * strike)
            * math.exp(rate_decimal * time_years)
            * selected[strike]
        )
    variance = (
        2.0 / time_years * contribution
        - 1.0 / time_years * (forward / k0 - 1.0) ** 2
    )
    if not math.isfinite(variance) or variance <= 0:
        raise VolatilityDataError(f"term variance is not positive: {variance!r}")
    reference_time = (
        as_of.astimezone(UTC)
        if as_of is not None
        else max((quote.timestamp for quote in quotes), default=datetime.now(UTC))
    )
    max_age = (
        max(0.0, max((reference_time - quote.timestamp).total_seconds() for quote in quotes))
        if quotes
        else 0.0
    )
    return TermVariance(
        expiration=expiration.isoformat(),
        minutes=minutes_to_expiration,
        time_years=time_years,
        rate_decimal=rate_decimal,
        forward=forward,
        k0=k0,
        variance=variance,
        atm_strike=atm_strike,
        included_strikes=tuple(included),
        rejected_strikes=tuple(sorted(set(rejected))),
        call_count=call_count,
        put_count=put_count,
        quote_count=len(quotes),
        max_quote_age_seconds=max_age,
    )


def interpolate_constant_maturity(
    near: TermVariance,
    next_term: TermVariance,
    *,
    target_minutes: float,
    minutes_per_year: float,
) -> float:
    n1 = near.minutes
    n2 = next_term.minutes
    if not (0 < n1 <= target_minutes <= n2) or n2 <= n1:
        raise VolatilityDataError(
            f"target {target_minutes} minutes is not bracketed by {n1} and {n2}"
        )
    weighted = (
        near.time_years * near.variance * (n2 - target_minutes) / (n2 - n1)
        + next_term.time_years
        * next_term.variance
        * (target_minutes - n1)
        / (n2 - n1)
    )
    annualized_variance = weighted * minutes_per_year / target_minutes
    if not math.isfinite(annualized_variance) or annualized_variance <= 0:
        raise VolatilityDataError("interpolated variance is not positive")
    return 100.0 * math.sqrt(annualized_variance)


def _restore_frozen_term(
    payload: Mapping[str, Any],
    *,
    expiration: date,
    minutes: float,
    rate_decimal: float,
) -> TermVariance:
    required_numbers = ("variance", "forward", "k0", "atm_strike")
    numbers = {key: finite_number(payload.get(key)) for key in required_numbers}
    if any(value is None or value <= 0 for value in numbers.values()):
        raise VolatilityDataError("persisted VIX1D near-term diagnostics are invalid")
    included = tuple(float(value) for value in payload.get("included_strikes", []))
    if len(included) < 3:
        raise VolatilityDataError("persisted VIX1D near-term strikes are insufficient")
    return TermVariance(
        expiration=expiration.isoformat(),
        minutes=minutes,
        time_years=minutes / VIX1D_MINUTES_PER_YEAR,
        rate_decimal=rate_decimal,
        forward=float(numbers["forward"]),
        k0=float(numbers["k0"]),
        variance=float(numbers["variance"]),
        atm_strike=float(numbers["atm_strike"]),
        included_strikes=included,
        rejected_strikes=tuple(float(value) for value in payload.get("rejected_strikes", [])),
        call_count=int(payload.get("call_count", 0)),
        put_count=int(payload.get("put_count", 0)),
        quote_count=int(payload.get("quote_count", 0)),
        max_quote_age_seconds=float(payload.get("max_quote_age_seconds", 0.0)),
    )


def calculate_vix1d(
    near_quotes: Sequence[OptionQuote],
    next_quotes: Sequence[OptionQuote],
    *,
    now: datetime,
    near_expiration: date,
    next_expiration: date,
    rate_decimal: float,
    holidays: set[date] | None = None,
    min_valid_strikes: int = 8,
    frozen_near_term: Mapping[str, Any] | None = None,
) -> tuple[float, dict[str, Any], dict[str, Any]]:
    near_minutes = business_minutes_to_spxw_expiration(
        now, near_expiration, holidays=holidays
    )
    next_minutes = business_minutes_to_spxw_expiration(
        now, next_expiration, holidays=holidays
    )
    near_frozen = near_minutes < 60.0
    if near_frozen:
        if not isinstance(frozen_near_term, Mapping):
            raise VolatilityDataError(
                "near-term VIX1D variance must be frozen below 60 minutes, "
                "but no persisted term is available"
            )
        near = _restore_frozen_term(
            frozen_near_term,
            expiration=near_expiration,
            minutes=near_minutes,
            rate_decimal=rate_decimal,
        )
    else:
        near = calculate_term_variance(
            near_quotes,
            expiration=near_expiration,
            minutes_to_expiration=near_minutes,
            minutes_per_year=VIX1D_MINUTES_PER_YEAR,
            rate_decimal=rate_decimal,
            min_valid_strikes=min_valid_strikes,
            as_of=now,
        )
    persisted_term = near.to_dict()
    next_term = calculate_term_variance(
        next_quotes,
        expiration=next_expiration,
        minutes_to_expiration=next_minutes,
        minutes_per_year=VIX1D_MINUTES_PER_YEAR,
        rate_decimal=rate_decimal,
        min_valid_strikes=min_valid_strikes,
        as_of=now,
    )
    value = interpolate_constant_maturity(
        near,
        next_term,
        target_minutes=VIX1D_SESSION_MINUTES,
        minutes_per_year=VIX1D_MINUTES_PER_YEAR,
    )
    return value, {
        "methodology": "cboe_vix1d_variance_replica",
        "target_minutes": VIX1D_SESSION_MINUTES,
        "minutes_per_year": VIX1D_MINUTES_PER_YEAR,
        "near_variance_frozen": near_frozen,
        "near": near.to_dict(),
        "next": next_term.to_dict(),
    }, persisted_term


def calculate_vvix(
    near_quotes: Sequence[OptionQuote],
    next_quotes: Sequence[OptionQuote],
    *,
    now: datetime,
    near_expiration: date,
    next_expiration: date,
    rate_decimal: float,
    min_valid_strikes: int = 8,
) -> tuple[float, dict[str, Any]]:
    near_minutes = calendar_minutes_to_expiration(
        now, near_expiration, settlement_time=time(9, 30)
    )
    next_minutes = calendar_minutes_to_expiration(
        now, next_expiration, settlement_time=time(9, 30)
    )
    near = calculate_term_variance(
        near_quotes,
        expiration=near_expiration,
        minutes_to_expiration=near_minutes,
        minutes_per_year=MINUTES_PER_YEAR,
        rate_decimal=rate_decimal,
        min_valid_strikes=min_valid_strikes,
        as_of=now,
    )
    next_term = calculate_term_variance(
        next_quotes,
        expiration=next_expiration,
        minutes_to_expiration=next_minutes,
        minutes_per_year=MINUTES_PER_YEAR,
        rate_decimal=rate_decimal,
        min_valid_strikes=min_valid_strikes,
        as_of=now,
    )
    value = interpolate_constant_maturity(
        near,
        next_term,
        target_minutes=VVIX_TARGET_MINUTES,
        minutes_per_year=MINUTES_PER_YEAR,
    )
    return value, {
        "methodology": "cboe_vvix_variance_replica",
        "target_minutes": VVIX_TARGET_MINUTES,
        "minutes_per_year": MINUTES_PER_YEAR,
        "near": near.to_dict(),
        "next": next_term.to_dict(),
    }


def choose_vix1d_expirations(expirations: Sequence[date], now: datetime) -> tuple[date, date]:
    today = now.astimezone(ET).date()
    available = sorted(set(expirations))
    if today not in available:
        raise VolatilityDataError("SPXW has no same-day expiration for VIX1D")
    future = [expiration for expiration in available if expiration > today]
    if not future:
        raise VolatilityDataError("SPXW has no next expiration for VIX1D")
    return today, future[0]


def choose_vvix_expirations(expirations: Sequence[date], now: datetime) -> tuple[date, date]:
    candidates: list[tuple[float, date]] = []
    for expiration in sorted(set(expirations)):
        minutes = calendar_minutes_to_expiration(
            now, expiration, settlement_time=time(9, 30)
        )
        if minutes > 0:
            candidates.append((minutes, expiration))
    lower = [item for item in candidates if item[0] <= VVIX_TARGET_MINUTES]
    upper = [item for item in candidates if item[0] > VVIX_TARGET_MINUTES]
    if not lower or not upper:
        raise VolatilityDataError("VIX expirations do not bracket 30 calendar days")
    return max(lower)[1], min(upper)[1]


__all__ = [
    "ET",
    "MINUTES_PER_YEAR",
    "OptionQuote",
    "TermVariance",
    "UnderlyingObservation",
    "VIX1D_MINUTES_PER_YEAR",
    "VIX1D_SESSION_MINUTES",
    "VVIX_TARGET_MINUTES",
    "VolatilityDataError",
    "business_minutes_to_spxw_expiration",
    "calculate_term_variance",
    "calculate_vix1d",
    "calculate_vvix",
    "calendar_minutes_to_expiration",
    "choose_vix1d_expirations",
    "choose_vvix_expirations",
    "derive_underlying_price",
    "finite_number",
    "flatten_theta_rows",
    "interpolate_constant_maturity",
    "iso_utc",
    "normalize_option_quotes",
    "parse_expiration",
    "parse_timestamp",
]
