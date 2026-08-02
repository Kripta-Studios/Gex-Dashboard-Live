"""Real-time JSON service for the portable KING NODE dashboard.

VIX, VIX1D and VVIX are obtained with ThetaData Options STANDARD only:

* VIX spot is the robust median of ``underlying_price`` in VIX option Greeks;
* VIX1D is reconstructed from SPXW NBBO option chains;
* VVIX is reconstructed from VIX NBBO option chains.

No ThetaData direct index-price endpoint is used or required.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import hashlib
import inspect
import json
import logging
import math
import os
from pathlib import Path
import re
import signal
from statistics import median
import sys
import tempfile
import time
from typing import Any, Callable

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.king_node_engine import (  # noqa: E402
    KingNodeDataError,
    SCHEMA_VERSION,
    build_snapshot,
    initial_state,
)
from modules.king_node_contract import (  # noqa: E402
    INPUT_SCHEMA_VERSION,
    SCHEMA_VERSION as V2_SCHEMA_VERSION,
    KingNodeContractError,
    KingNodeInputError,
    KingNodeReferenceError,
    validate_normalized_input,
    validate_reference,
)
from modules.thetadata_adapter import (  # noqa: E402
    DEFAULT_MAX_AGE_SECONDS as V2_DEFAULT_MAX_AGE_SECONDS,
    Entitlements,
    ErrorCode,
    IndexResult,
    MarketCalendar,
    NormalizedOptionInput,
    SessionState,
    ThetaDataError,
    ThetaDataV3Client,
    ThetaRoute,
    content_hash,
    safe_quality_error,
)
from modules.volatility_indices import (  # noqa: E402
    ET,
    OptionQuote,
    VolatilityDataError,
    calculate_vix1d,
    calculate_vvix,
    choose_vix1d_expirations,
    choose_vvix_expirations,
    derive_underlying_price,
    finite_number,
    flatten_theta_rows,
    iso_utc,
    normalize_option_quotes,
    parse_expiration,
    parse_timestamp,
)

LOGGER = logging.getLogger("king_node_service")
DEFAULT_INTERVAL_SECONDS = 30
DEFAULT_TASTY_MAX_AGE_SECONDS = 900
DEFAULT_OPTION_MAX_AGE_SECONDS = 180
DEFAULT_EXPIRATION_CACHE_SECONDS = 21_600
DEFAULT_RATE_CACHE_SECONDS = 600
DEFAULT_MIN_UNDERLYING_OBSERVATIONS = 3
DEFAULT_MAX_UNDERLYING_DISPERSION_PCT = 0.10
DEFAULT_MIN_VALID_STRIKES = 8
FILENAME_TIMESTAMP = re.compile(r"_(\d{8})_(\d{6})\.json$", re.IGNORECASE)


def _timestamp_from_path(path: Path) -> datetime:
    match = FILENAME_TIMESTAMP.search(path.name)
    if match:
        try:
            local = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S").replace(
                tzinfo=ET
            )
            return local.astimezone(UTC)
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime, UTC)


def _age_seconds(timestamp: datetime | None, now: datetime) -> float | None:
    if timestamp is None:
        return None
    return max(0.0, (now.astimezone(UTC) - timestamp.astimezone(UTC)).total_seconds())


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _load_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def _load_state(path: Path, session_date: str) -> dict[str, Any]:
    if not path.exists():
        return initial_state(session_date)
    try:
        payload = _load_json_object(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        LOGGER.warning("Ignoring unreadable KING NODE state %s: %s", path, exc)
        return initial_state(session_date)
    return payload


def _load_reference(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return _load_json_object(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        LOGGER.warning("Ignoring unreadable workbook reference %s: %s", path, exc)
        return {}


def find_latest_tastytrade_json(data_dir: Path) -> Path:
    """Find the newest completed SPX 0DTE exposure JSON."""
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Tastytrade data directory does not exist: {data_dir}")
    candidates = [
        path
        for path in data_dir.glob("*.json")
        if "exposuredata" in path.name.lower()
        and "0dte" in path.name.lower()
        and path.name.lower().startswith("spx_")
        and not path.name.startswith(".")
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No SPX 0DTE Tastytrade exposure JSON found in {data_dir}"
        )
    return max(candidates, key=lambda path: (_timestamp_from_path(path), path.name))


def read_stable_json(path: Path) -> dict[str, Any]:
    """Read a producer file only when size/mtime are unchanged across the read."""
    before = path.stat()
    payload = _load_json_object(path)
    after = path.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise RuntimeError(f"Tastytrade JSON changed while it was being read: {path}")
    return payload


def _unavailable(
    name: str,
    method: str,
    input_symbol: str,
    error: Exception | str,
) -> dict[str, Any]:
    return {
        "value": None,
        "timestamp": None,
        "age_seconds": None,
        "status": "unavailable",
        "source": "ThetaData v3 option feed",
        "method": method,
        "input_symbol": input_symbol,
        "entitlement": "options_standard",
        "direct_index_subscription": False,
        "expirations": [],
        "quote_count": 0,
        "valid_strike_count": 0,
        "error": str(error),
    }


class ThetaOptionsVolatilityClient:
    """ThetaData v3 client restricted to Options STANDARD-compatible routes."""

    def __init__(
        self,
        base_url: str,
        *,
        max_age_seconds: int = DEFAULT_OPTION_MAX_AGE_SECONDS,
        expiration_cache_seconds: int = DEFAULT_EXPIRATION_CACHE_SECONDS,
        rate_cache_seconds: int = DEFAULT_RATE_CACHE_SECONDS,
        min_underlying_observations: int = DEFAULT_MIN_UNDERLYING_OBSERVATIONS,
        max_underlying_dispersion_pct: float = DEFAULT_MAX_UNDERLYING_DISPERSION_PCT,
        min_valid_strikes: int = DEFAULT_MIN_VALID_STRIKES,
        rate_symbol: str = "SOFR",
        rate_lookback_days: int = 10,
        risk_free_rate_percent: float | None = None,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_age_seconds = int(max_age_seconds)
        self.expiration_cache_seconds = int(expiration_cache_seconds)
        self.rate_cache_seconds = int(rate_cache_seconds)
        self.min_underlying_observations = int(min_underlying_observations)
        self.max_underlying_dispersion_pct = float(max_underlying_dispersion_pct)
        self.min_valid_strikes = int(min_valid_strikes)
        self.rate_symbol = rate_symbol.upper()
        self.rate_lookback_days = int(rate_lookback_days)
        self.risk_free_rate_percent = risk_free_rate_percent
        self.client = client or httpx.Client(
            timeout=timeout_seconds,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
        )
        self._owns_client = client is None
        self._cache: dict[str, tuple[datetime, Any]] = {}

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        if ("/" + "index/") in path:
            raise RuntimeError("ThetaData direct index endpoints are forbidden")
        endpoint = f"{self.base_url}/{path.lstrip('/')}"
        response = self.client.get(endpoint, params={**params, "format": "json"})
        if response.status_code == 403:
            raise PermissionError(
                f"ThetaData 403 for {path}; Options STANDARD entitlement is required: "
                f"{response.text.strip()}"
            )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error_code"):
            raise RuntimeError(str(payload.get("message") or payload["error_code"]))
        return payload

    def _cached(
        self,
        key: str,
        ttl_seconds: int,
        now: datetime,
        loader: Callable[[], Any],
    ) -> Any:
        cached = self._cache.get(key)
        if cached is not None:
            stored_at, value = cached
            if (now - stored_at).total_seconds() <= ttl_seconds:
                return value
        value = loader()
        self._cache[key] = (now, value)
        return value

    def list_expirations(self, symbol: str, now: datetime) -> list[date]:
        symbol = symbol.upper()

        def load() -> list[date]:
            payload = self._get("option/list/expirations", {"symbol": symbol})
            parsed = {
                expiration
                for row in flatten_theta_rows(payload)
                if (expiration := parse_expiration(row)) is not None
            }
            if not parsed:
                # Some list endpoints return scalar values rather than row objects.
                if isinstance(payload, list):
                    parsed.update(
                        expiration
                        for item in payload
                        if (expiration := parse_expiration(item)) is not None
                    )
            if not parsed:
                raise VolatilityDataError(f"ThetaData returned no {symbol} expirations")
            return sorted(parsed)

        return self._cached(
            f"expirations:{symbol}", self.expiration_cache_seconds, now, load
        )

    def fetch_quotes(self, symbol: str, expiration: date, now: datetime) -> list[Any]:
        payload = self._get(
            "option/snapshot/quote",
            {
                "symbol": symbol.upper(),
                "expiration": expiration.strftime("%Y%m%d"),
                "strike": "*",
                "right": "both",
            },
        )
        quotes = normalize_option_quotes(
            payload,
            now=now,
            max_age_seconds=self.max_age_seconds,
            default_expiration=expiration,
        )
        if not quotes:
            raise VolatilityDataError(
                f"ThetaData returned no fresh {symbol} quotes for {expiration}"
            )
        return quotes

    def fetch_underlying(self, symbol: str, expiration: date, now: datetime) -> Any:
        payload = self._get(
            "option/snapshot/greeks/first_order",
            {
                "symbol": symbol.upper(),
                "expiration": expiration.strftime("%Y%m%d"),
                "strike": "*",
                "right": "both",
                "strike_range": 4,
                "version": "latest",
            },
        )
        return derive_underlying_price(
            payload,
            now=now,
            max_age_seconds=self.max_age_seconds,
            min_observations=self.min_underlying_observations,
            max_dispersion_pct=self.max_underlying_dispersion_pct,
        )

    def fetch_holidays(self, now: datetime) -> set[date]:
        years = {now.astimezone(ET).year, (now + timedelta(days=10)).astimezone(ET).year}

        def load() -> set[date]:
            holidays: set[date] = set()
            for year in sorted(years):
                payload = self._get("calendar/year_holidays", {"year": year})
                for row in flatten_theta_rows(payload):
                    if str(row.get("type", "")).lower() != "full_close":
                        continue
                    parsed = parse_expiration(row.get("date"))
                    if parsed is not None:
                        holidays.add(parsed)
            return holidays

        return self._cached("holidays", 86_400, now, load)

    def fetch_rate(self, now: datetime) -> dict[str, Any]:
        def load() -> dict[str, Any]:
            end = now.astimezone(ET).date()
            start = end - timedelta(days=self.rate_lookback_days)
            try:
                payload = self._get(
                    "interest_rate/history/eod",
                    {
                        "symbol": self.rate_symbol,
                        "start_date": start.strftime("%Y%m%d"),
                        "end_date": end.strftime("%Y%m%d"),
                    },
                )
                candidates: list[tuple[datetime, float]] = []
                for row in flatten_theta_rows(payload):
                    rate = finite_number(
                        row.get("rate", row.get("close", row.get("value")))
                    )
                    timestamp = parse_timestamp(
                        row.get(
                            "created",
                            row.get("timestamp", row.get("date")),
                        ),
                        default_zone=ET,
                    )
                    if rate is not None and timestamp is not None:
                        candidates.append((timestamp, rate))
                if not candidates:
                    raise VolatilityDataError("ThetaData returned no recent SOFR rate")
                timestamp, percent = max(candidates, key=lambda item: item[0])
                return {
                    "value_percent": percent,
                    "value_decimal": percent / 100.0,
                    "timestamp": iso_utc(timestamp),
                    "status": "observed",
                    "source": "ThetaData v3 interest_rate/history/eod",
                    "symbol": self.rate_symbol,
                }
            except Exception as exc:
                fallback = finite_number(self.risk_free_rate_percent)
                if fallback is None:
                    raise VolatilityDataError(
                        f"risk-free rate unavailable and no explicit fallback set: {exc}"
                    ) from exc
                return {
                    "value_percent": fallback,
                    "value_decimal": fallback / 100.0,
                    "timestamp": iso_utc(now),
                    "status": "configured_fallback",
                    "source": "KING_NODE_RISK_FREE_RATE_PERCENT",
                    "symbol": self.rate_symbol,
                    "warning": str(exc),
                }

        return self._cached("risk_free_rate", self.rate_cache_seconds, now, load)

    def fetch_all(
        self,
        *,
        now: datetime | None = None,
        state: dict[str, Any] | None = None,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        state = state if isinstance(state, dict) else {}
        volatility_state = dict(state.get("volatility_state", {}))
        diagnostics: dict[str, Any] = {
            "provider": "ThetaData v3",
            "entitlement": "options_standard",
            "direct_index_subscription": False,
            "base_url": self.base_url,
        }

        try:
            spxw_expirations = self.list_expirations("SPXW", now)
            vix_expirations = self.list_expirations("VIX", now)
        except Exception as exc:
            unavailable = {
                "vix": _unavailable(
                    "VIX", "thetadata_option_first_order_underlying_median", "VIX", exc
                ),
                "vix1d": _unavailable(
                    "VIX1D", "cboe_vix1d_reconstruction_from_spxw_nbbo", "SPXW", exc
                ),
                "vvix": _unavailable(
                    "VVIX", "cboe_vvix_reconstruction_from_vix_nbbo", "VIX", exc
                ),
            }
            return unavailable, volatility_state, {**diagnostics, "error": str(exc)}

        try:
            holidays = self.fetch_holidays(now)
        except Exception as exc:
            # Holiday metadata improves expiration handling but must not suppress
            # VIX spot derived directly from VIX option Greeks.
            holidays = set()
            diagnostics["holidays"] = {"status": "unavailable", "error": str(exc)}

        rate: dict[str, Any] | None
        rate_error: Exception | None = None
        try:
            rate = self.fetch_rate(now)
        except Exception as exc:
            rate = None
            rate_error = exc
            diagnostics["rate"] = {"status": "unavailable", "error": str(exc)}

        rate_decimal = (
            float(rate["value_decimal"]) if isinstance(rate, dict) else None
        )
        results: dict[str, dict[str, Any]] = {}

        # SPX underlying is diagnostic/validation input. Tastytrade spot remains the
        # calculation authority so the exposure surface and spot stay synchronized.
        try:
            spx_exp = min(expiration for expiration in spxw_expirations if expiration >= now.astimezone(ET).date())
            spx_underlying = self.fetch_underlying("SPXW", spx_exp, now)
            diagnostics["spx_spot_from_options"] = {
                **spx_underlying.to_dict(),
                "method": "thetadata_option_first_order_underlying_median",
                "input_symbol": "SPXW",
                "expiration": spx_exp.isoformat(),
            }
        except Exception as exc:
            diagnostics["spx_spot_from_options"] = {"status": "unavailable", "error": str(exc)}

        try:
            live_vix_exp = min(
                expiration
                for expiration in vix_expirations
                if expiration > now.astimezone(ET).date()
            )
            underlying = self.fetch_underlying("VIX", live_vix_exp, now)
            stale = underlying.age_seconds > self.max_age_seconds
            results["vix"] = {
                **underlying.to_dict(),
                "status": "stale" if stale else "observed_from_option_feed",
                "source": "ThetaData v3 option/snapshot/greeks/first_order",
                "method": "thetadata_option_first_order_underlying_median",
                "input_symbol": "VIX",
                "entitlement": "options_standard",
                "direct_index_subscription": False,
                "expirations": [live_vix_exp.isoformat()],
                "quote_count": underlying.count,
                "valid_strike_count": underlying.count,
                "diagnostics": {
                    "mad": underlying.mad,
                    "dispersion_pct": underlying.dispersion_pct,
                },
            }
        except Exception as exc:
            results["vix"] = _unavailable(
                "VIX", "thetadata_option_first_order_underlying_median", "VIX", exc
            )

        try:
            if rate_decimal is None:
                raise VolatilityDataError(
                    f"risk-free rate unavailable: {rate_error}"
                )
            near_exp, next_exp = choose_vix1d_expirations(spxw_expirations, now)
            near_quotes = self.fetch_quotes("SPXW", near_exp, now)
            next_quotes = self.fetch_quotes("SPXW", next_exp, now)
            frozen = volatility_state.get("vix1d_near_term")
            frozen_term = (
                frozen
                if isinstance(frozen, dict)
                and frozen.get("expiration") == near_exp.isoformat()
                else None
            )
            value, details, persisted_term = calculate_vix1d(
                near_quotes,
                next_quotes,
                now=now,
                near_expiration=near_exp,
                next_expiration=next_exp,
                rate_decimal=rate_decimal,
                holidays=holidays,
                min_valid_strikes=self.min_valid_strikes,
                frozen_near_term=frozen_term,
            )
            volatility_state["vix1d_near_term"] = {
                **persisted_term,
                "expiration": near_exp.isoformat(),
                "updated_at": iso_utc(now),
            }
            newest = max(quote.timestamp for quote in [*near_quotes, *next_quotes])
            age = _age_seconds(newest, now) or 0.0
            valid_count = len(details["near"]["included_strikes"]) + len(
                details["next"]["included_strikes"]
            )
            results["vix1d"] = {
                "value": value,
                "timestamp": iso_utc(newest),
                "age_seconds": age,
                "status": "stale" if age > self.max_age_seconds else "reconstructed",
                "source": "ThetaData SPXW option NBBO",
                "method": "cboe_vix1d_reconstruction_from_spxw_nbbo",
                "input_symbol": "SPXW",
                "entitlement": "options_standard",
                "direct_index_subscription": False,
                "expirations": [near_exp.isoformat(), next_exp.isoformat()],
                "quote_count": len(near_quotes) + len(next_quotes),
                "valid_strike_count": valid_count,
                "rate": rate,
                "diagnostics": details,
            }
        except Exception as exc:
            results["vix1d"] = _unavailable(
                "VIX1D", "cboe_vix1d_reconstruction_from_spxw_nbbo", "SPXW", exc
            )

        try:
            if rate_decimal is None:
                raise VolatilityDataError(
                    f"risk-free rate unavailable: {rate_error}"
                )
            near_exp, next_exp = choose_vvix_expirations(vix_expirations, now)
            near_quotes = self.fetch_quotes("VIX", near_exp, now)
            next_quotes = self.fetch_quotes("VIX", next_exp, now)
            value, details = calculate_vvix(
                near_quotes,
                next_quotes,
                now=now,
                near_expiration=near_exp,
                next_expiration=next_exp,
                rate_decimal=rate_decimal,
                min_valid_strikes=self.min_valid_strikes,
            )
            newest = max(quote.timestamp for quote in [*near_quotes, *next_quotes])
            age = _age_seconds(newest, now) or 0.0
            valid_count = len(details["near"]["included_strikes"]) + len(
                details["next"]["included_strikes"]
            )
            results["vvix"] = {
                "value": value,
                "timestamp": iso_utc(newest),
                "age_seconds": age,
                "status": "stale" if age > self.max_age_seconds else "reconstructed",
                "source": "ThetaData VIX option NBBO",
                "method": "cboe_vvix_reconstruction_from_vix_nbbo",
                "input_symbol": "VIX",
                "entitlement": "options_standard",
                "direct_index_subscription": False,
                "expirations": [near_exp.isoformat(), next_exp.isoformat()],
                "quote_count": len(near_quotes) + len(next_quotes),
                "valid_strike_count": valid_count,
                "rate": rate,
                "diagnostics": details,
            }
        except Exception as exc:
            results["vvix"] = _unavailable(
                "VVIX", "cboe_vvix_reconstruction_from_vix_nbbo", "VIX", exc
            )

        if rate is not None:
            diagnostics["rate"] = rate
        diagnostics["spxw_expiration_count"] = len(spxw_expirations)
        diagnostics["vix_expiration_count"] = len(vix_expirations)
        return results, volatility_state, diagnostics

    def __enter__(self) -> "ThetaOptionsVolatilityClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class KingNodeService:
    def __init__(
        self,
        *,
        tasty_data_dir: Path,
        output_path: Path,
        state_path: Path,
        reference_path: Path | None,
        thetadata_url: str,
        tasty_max_age_seconds: int = DEFAULT_TASTY_MAX_AGE_SECONDS,
        option_max_age_seconds: int = DEFAULT_OPTION_MAX_AGE_SECONDS,
        expiration_cache_seconds: int = DEFAULT_EXPIRATION_CACHE_SECONDS,
        min_underlying_observations: int = DEFAULT_MIN_UNDERLYING_OBSERVATIONS,
        max_underlying_dispersion_pct: float = DEFAULT_MAX_UNDERLYING_DISPERSION_PCT,
        min_valid_strikes: int = DEFAULT_MIN_VALID_STRIKES,
        rate_symbol: str = "SOFR",
        rate_lookback_days: int = 10,
        risk_free_rate_percent: float | None = None,
        theta_enabled: bool = True,
        theta_client: ThetaOptionsVolatilityClient | None = None,
    ) -> None:
        self.tasty_data_dir = tasty_data_dir
        self.output_path = output_path
        self.state_path = state_path
        self.reference_path = reference_path
        self.tasty_max_age_seconds = int(tasty_max_age_seconds)
        self.theta_enabled = bool(theta_enabled)
        self.theta = theta_client or ThetaOptionsVolatilityClient(
            thetadata_url,
            max_age_seconds=option_max_age_seconds,
            expiration_cache_seconds=expiration_cache_seconds,
            min_underlying_observations=min_underlying_observations,
            max_underlying_dispersion_pct=max_underlying_dispersion_pct,
            min_valid_strikes=min_valid_strikes,
            rate_symbol=rate_symbol,
            rate_lookback_days=rate_lookback_days,
            risk_free_rate_percent=risk_free_rate_percent,
        )

    def close(self) -> None:
        self.theta.close()

    def run_once(self, now: datetime | None = None) -> dict[str, Any]:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        session_date = now.astimezone(ET).date().isoformat()
        tasty_path = find_latest_tastytrade_json(self.tasty_data_dir)
        tasty_payload = read_stable_json(tasty_path)
        tasty_timestamp = _timestamp_from_path(tasty_path)
        tasty_age = _age_seconds(tasty_timestamp, now)
        tasty_stale = tasty_age is not None and tasty_age > self.tasty_max_age_seconds
        source_meta = {
            "path": str(tasty_path.resolve()),
            "filename": tasty_path.name,
            "source_id": f"{tasty_path.name}:{tasty_path.stat().st_size}",
            "timestamp": iso_utc(tasty_timestamp),
            "age_seconds": tasty_age,
            "stale": tasty_stale,
            "max_age_seconds": self.tasty_max_age_seconds,
            "provider": "Tastytrade via services/gex_daemon.py",
        }
        state = _load_state(self.state_path, session_date)
        if self.theta_enabled:
            volatility, volatility_state, theta_meta = self.theta.fetch_all(
                now=now, state=state
            )
        else:
            volatility = {
                name: _unavailable(name.upper(), "disabled", "disabled", "ThetaData disabled by CLI")
                for name in ("vix", "vvix", "vix1d")
            }
            volatility_state = dict(state.get("volatility_state", {}))
            theta_meta = {"status": "disabled"}
        reference = _load_reference(self.reference_path)
        snapshot, next_state = build_snapshot(
            tasty_payload,
            volatility,
            state,
            source_meta=source_meta,
            reference=reference,
            generated_at=now,
            session_date=session_date,
            market_minute=now.astimezone(ET).hour * 60 + now.astimezone(ET).minute,
        )
        # The v1 engine intentionally keeps only common index fields. Restore the
        # full auditable provenance without changing the public schema version.
        snapshot.setdefault("source", {})["indices"] = volatility
        snapshot["source"]["theta_options"] = theta_meta
        warnings = snapshot.get("quality", {}).get("warnings", [])
        if isinstance(warnings, list):
            snapshot["quality"]["warnings"] = [
                str(item).replace(
                    "Observed volatility index values unavailable",
                    "Volatility inputs unavailable",
                )
                for item in warnings
            ]
        next_state["volatility_state"] = volatility_state
        _atomic_write_json(self.state_path, next_state)
        _atomic_write_json(self.output_path, snapshot)
        return snapshot

    def publish_error(
        self, exc: Exception, now: datetime | None = None
    ) -> dict[str, Any]:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "generated_at": iso_utc(now),
            "session_date": now.astimezone(ET).date().isoformat(),
            "quality": {
                "grade": "ERROR",
                "errors": [f"{type(exc).__name__}: {exc}"],
                "warnings": [],
            },
            "source": {},
            "rows": [],
        }
        _atomic_write_json(self.output_path, payload)
        return payload


@dataclass(frozen=True)
class V2ArtifactPaths:
    """Private artifact locations; never serialised into a snapshot."""

    current_attempt: Path
    live: Path
    last_completed: Path
    state: Path
    health: Path


def _v2_paths_from_environment() -> V2ArtifactPaths:
    root = Path(os.getenv("KING_NODE_ARTIFACT_DIR", "/var/lib/king-node"))
    live = Path(os.getenv("KING_NODE_LIVE_SNAPSHOT", os.getenv("KING_NODE_OUTPUT", root / "latest.json")))
    return V2ArtifactPaths(
        current_attempt=Path(os.getenv("KING_NODE_CURRENT_ATTEMPT", root / "current-attempt.json")),
        live=live,
        last_completed=Path(os.getenv("KING_NODE_LAST_COMPLETED_SNAPSHOT", root / "last-completed.json")),
        state=Path(os.getenv("KING_NODE_STATE_FILE", root / "state.json")),
        health=Path(os.getenv("KING_NODE_HEALTH_STATE", root / "health.json")),
    )


def _read_v2_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": "king-node.v2-state", "history": {}}
    try:
        payload = _load_json_object(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"schema_version": "king-node.v2-state", "history": {}}
    if payload.get("schema_version") != "king-node.v2-state":
        return {"schema_version": "king-node.v2-state", "history": {}}
    return payload


def _safe_error_code(exc: Exception, *, component: str) -> dict[str, Any]:
    if isinstance(exc, ThetaDataError):
        return exc.safe_dict(component)
    if isinstance(exc, (KingNodeContractError, VolatilityDataError)):
        return {
            "code": "INPUT_INCOHERENT",
            "component": component,
            "retryable": False,
        }
    return {"code": "PRODUCER_INTERNAL", "component": component, "retryable": False}


def _no_path_payload(value: Any) -> Any:
    """Reject host-path/error text before it can enter a sealed artifact."""
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if name.lower() in {"path", "source_path", "snapshot_path", "exception", "traceback", "stack"}:
                continue
            safe[name] = _no_path_payload(item)
        return safe
    if isinstance(value, list):
        return [_no_path_payload(item) for item in value]
    if isinstance(value, str) and (
        "file://" in value.lower()
        or "/home/" in value.lower()
        or "/etc/" in value.lower()
        or "/var/" in value.lower()
    ):
        return "[redacted]"
    return value


class KingNodeV2Service:
    """Theta-only v2 producer with atomic valid/live and completed-session paths.

    The class writes an attempt artifact for every cycle.  It only replaces the
    live artifact after provider, session, input, reference and engine validation
    all succeed.  A failed retry cannot overwrite a previous valid live artifact.
    """

    def __init__(
        self,
        *,
        thetadata_url: str,
        reference_path: Path,
        artifacts: V2ArtifactPaths | None = None,
        max_age_seconds: float = V2_DEFAULT_MAX_AGE_SECONDS,
        min_underlying_observations: int = DEFAULT_MIN_UNDERLYING_OBSERVATIONS,
        max_underlying_dispersion_pct: float = DEFAULT_MAX_UNDERLYING_DISPERSION_PCT,
        min_valid_strikes: int = DEFAULT_MIN_VALID_STRIKES,
        contract_multiplier: float = 100.0,
        theta_client: ThetaDataV3Client | None = None,
        calendar: MarketCalendar | None = None,
        entitlements: Entitlements | None = None,
        engine_builder: Callable[..., tuple[dict[str, Any], dict[str, Any]]] | None = None,
    ) -> None:
        self.artifacts = artifacts or _v2_paths_from_environment()
        self.reference_path = reference_path
        self.max_age_seconds = float(max_age_seconds)
        self.min_underlying_observations = int(min_underlying_observations)
        self.max_underlying_dispersion_pct = float(max_underlying_dispersion_pct)
        self.min_valid_strikes = int(min_valid_strikes)
        self.contract_multiplier = float(contract_multiplier)
        self.calendar = calendar or MarketCalendar()
        self.theta = theta_client or ThetaDataV3Client(thetadata_url)
        self._owns_theta = theta_client is None
        self.entitlements = entitlements or Entitlements(
            stock=os.getenv("KING_NODE_STOCK_TIER", "FREE"),
            options=os.getenv("KING_NODE_OPTIONS_TIER", "STANDARD"),
            index=os.getenv("KING_NODE_INDEX_TIER", "FREE"),
            rate=os.getenv("KING_NODE_RATE_TIER", "FREE"),
        )
        self.engine_builder = engine_builder
        if self.max_age_seconds <= 0 or self.contract_multiplier <= 0:
            raise ValueError("v2 freshness and contract multiplier must be positive")

    def close(self) -> None:
        if self._owns_theta:
            self.theta.close()

    def _read_reference(self):
        try:
            reference = _load_json_object(self.reference_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise KingNodeReferenceError("verified v2 reference is unavailable") from exc
        return validate_reference(reference)

    def _write_health(
        self,
        *,
        session: Any,
        readiness: Mapping[str, Any] | None,
        status: str,
        error: Mapping[str, Any] | None = None,
    ) -> None:
        payload = {
            "schema_version": V2_SCHEMA_VERSION,
            "process": {"status": status},
            "provider": readiness or {"status": "unknown"},
            "entitlement": self.entitlements.to_dict(),
            "refresh": {"status": status, "max_age_seconds": self.max_age_seconds},
            "session": session.to_dict(),
        }
        if error:
            payload["refresh"]["error"] = dict(error)
        _atomic_write_json(self.artifacts.health, _no_path_payload(payload))

    def _unavailable_snapshot(
        self,
        *,
        now: datetime,
        session: Any,
        error: Mapping[str, Any],
        readiness: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = iso_utc(now)
        return _no_path_payload(
            {
                "schema_version": V2_SCHEMA_VERSION,
                "status": "unavailable",
                "generated_at": timestamp,
                "calculation_at": timestamp,
                "publication_at": timestamp,
                "session": session.to_dict(),
                "freshness": {
                    "max_age_seconds": self.max_age_seconds,
                    "stale": True,
                    "oldest_observation_at": None,
                },
                "provenance": {
                    "provider": "ThetaData",
                    "api_version": "v3",
                    "entitlements": self.entitlements.to_dict(),
                    "readiness": readiness or {"status": "unknown"},
                },
                "reference": {"status": "unavailable"},
                "formula_coverage": {"status": "unavailable"},
                "quality": {"valid": False, "grade": "UNAVAILABLE", "errors": [dict(error)], "warnings": []},
                "inputs": {},
                "rows": [],
                "totals": {},
                "regime": {},
                "levels": {},
                "monitor": {},
                "directions": {},
                "presentation": {},
            }
        )

    @staticmethod
    def _rows_to_quotes(rows: Sequence[NormalizedOptionInput]) -> list[OptionQuote]:
        result: list[OptionQuote] = []
        for row in rows:
            try:
                timestamp = parse_timestamp(row.quote_timestamp)
                expiry = parse_expiration(row.expiry)
            except (TypeError, ValueError):
                timestamp, expiry = None, None
            if timestamp is not None and expiry is not None:
                result.append(
                    OptionQuote(
                        row.strike,
                        "C" if row.right == "CALL" else "P",
                        row.bid,
                        row.ask,
                        timestamp,
                        expiry,
                    )
                )
        return result

    def _validated_underlying(self, rows: Sequence[NormalizedOptionInput]) -> tuple[float, str]:
        observations: list[tuple[float, datetime]] = []
        for row in rows:
            if row.underlying_price is None or row.underlying_timestamp is None:
                continue
            timestamp = parse_timestamp(row.underlying_timestamp)
            if timestamp is not None:
                observations.append((row.underlying_price, timestamp))
        if len(observations) < self.min_underlying_observations:
            raise KingNodeInputError("insufficient fresh option underlying observations")
        values = [value for value, _ in observations]
        center = median(values)
        if center <= 0:
            raise KingNodeInputError("option underlying proxy is invalid")
        dispersion = (max(values) - min(values)) / center * 100.0
        if dispersion > self.max_underlying_dispersion_pct:
            raise KingNodeInputError("option underlying proxy dispersion is invalid")
        newest = max(timestamp for _, timestamp in observations)
        return float(center), iso_utc(newest)

    def _index_unavailable(self, name: str, reason: str) -> IndexResult:
        return IndexResult(
            name=name,
            value=None,
            mode="unavailable",
            provider="ThetaData",
            as_of=None,
            session_date=None,
            inputs_age_seconds=None,
            methodology_version="cboe-variance-v1",
            diagnostics={"reason": reason},
            quality={"valid": False, "reasons": [reason]},
        )

    def _reconstruct_indices(
        self,
        *,
        now: datetime,
        spxw_expirations: Sequence[date],
        spxw_current: Sequence[NormalizedOptionInput],
        rate: Mapping[str, Any],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        """Reconstruct all authorised volatility values or return explicit gaps."""
        details: dict[str, Any] = {}
        rate_decimal = float(rate["value_decimal"])
        result: dict[str, IndexResult] = {}
        try:
            vix_expirations = self.theta.expirations("VIX")
            eligible_vix = [expiry for expiry in vix_expirations if expiry > now.astimezone(ET).date()]
            if not eligible_vix:
                raise ThetaDataError(ErrorCode.PROVIDER_NO_DATA, route=ThetaRoute.OPTION_EXPIRATIONS)
            vix_near = eligible_vix[0]
            vix_rows = self.theta.option_chain(
                symbol="VIX", expiration=vix_near, now=now, rate=rate_decimal,
                calendar=self.calendar, max_age_seconds=self.max_age_seconds,
            )
            vix_value, vix_at = self._validated_underlying(vix_rows)
            result["vix"] = IndexResult(
                name="VIX", value=vix_value, mode="reconstructed", provider="ThetaData",
                as_of=vix_at, session_date=now.astimezone(ET).date().isoformat(),
                inputs_age_seconds=max(0.0, (now - parse_timestamp(vix_at)).total_seconds()),
                methodology_version="thetadata_option_underlying_proxy_median_v1",
                diagnostics={"expiration": vix_near.isoformat(), "quote_count": len(vix_rows)},
                quality={"valid": True, "reasons": []},
            )
            details["vix_rows"] = vix_rows
            details["vix_expirations"] = vix_expirations
        except Exception as exc:
            result["vix"] = self._index_unavailable("VIX", _safe_error_code(exc, component="vix")["code"])
            details["vix_rows"] = []
            details["vix_expirations"] = []

        try:
            near, next_expiry = choose_vix1d_expirations(spxw_expirations, now)
            if near != now.astimezone(ET).date():
                raise VolatilityDataError("VIX1D near expiration does not match current session")
            current = spxw_current if near == parse_expiration(spxw_current[0].expiry) else self.theta.option_chain(
                symbol="SPXW", expiration=near, now=now, rate=rate_decimal,
                calendar=self.calendar, max_age_seconds=self.max_age_seconds,
            )
            next_rows = self.theta.option_chain(
                symbol="SPXW", expiration=next_expiry, now=now, rate=rate_decimal,
                calendar=self.calendar, max_age_seconds=self.max_age_seconds,
            )
            value, diagnostics, persisted = calculate_vix1d(
                self._rows_to_quotes(current), self._rows_to_quotes(next_rows), now=now,
                near_expiration=near, next_expiration=next_expiry, rate_decimal=rate_decimal,
                min_valid_strikes=self.min_valid_strikes,
                session_clock=lambda clock_now, expiry: self.calendar.option_session_minutes_until(clock_now, expiry),
            )
            quote_times = [parse_timestamp(item.quote_timestamp) for item in [*current, *next_rows]]
            quote_times = [item for item in quote_times if item is not None]
            newest = max(quote_times)
            result["vix1d"] = IndexResult(
                name="VIX1D", value=value, mode="reconstructed", provider="ThetaData",
                as_of=iso_utc(newest), session_date=now.astimezone(ET).date().isoformat(),
                inputs_age_seconds=max(0.0, (now - newest).total_seconds()),
                methodology_version="cboe_vix1d_variance_replica_v1",
                diagnostics=diagnostics,
                quality={"valid": True, "reasons": []},
            )
            details["vix1d_persisted_term"] = persisted
        except Exception as exc:
            result["vix1d"] = self._index_unavailable("VIX1D", _safe_error_code(exc, component="vix1d")["code"])

        try:
            vix_expirations = details.get("vix_expirations", [])
            near_vvix, next_vvix = choose_vvix_expirations(vix_expirations, now)
            existing_vix = details.get("vix_rows", [])
            near_rows = existing_vix if existing_vix and parse_expiration(existing_vix[0].expiry) == near_vvix else self.theta.option_chain(
                symbol="VIX", expiration=near_vvix, now=now, rate=rate_decimal,
                calendar=self.calendar, max_age_seconds=self.max_age_seconds,
            )
            next_rows = self.theta.option_chain(
                symbol="VIX", expiration=next_vvix, now=now, rate=rate_decimal,
                calendar=self.calendar, max_age_seconds=self.max_age_seconds,
            )
            value, diagnostics = calculate_vvix(
                self._rows_to_quotes(near_rows), self._rows_to_quotes(next_rows), now=now,
                near_expiration=near_vvix, next_expiration=next_vvix,
                rate_decimal=rate_decimal, min_valid_strikes=self.min_valid_strikes,
            )
            quote_times = [parse_timestamp(item.quote_timestamp) for item in [*near_rows, *next_rows]]
            quote_times = [item for item in quote_times if item is not None]
            newest = max(quote_times)
            result["vvix"] = IndexResult(
                name="VVIX", value=value, mode="reconstructed", provider="ThetaData",
                as_of=iso_utc(newest), session_date=now.astimezone(ET).date().isoformat(),
                inputs_age_seconds=max(0.0, (now - newest).total_seconds()),
                methodology_version="cboe_vvix_variance_replica_v1",
                diagnostics=diagnostics,
                quality={"valid": True, "reasons": []},
            )
        except Exception as exc:
            result["vvix"] = self._index_unavailable("VVIX", _safe_error_code(exc, component="vvix")["code"])

        contract = {
            name: {
                "value": item.value,
                "provenance": item.mode,
                "timestamp": item.as_of,
                "methodology": item.methodology_version,
                "quality": "valid" if item.quality.get("valid") else "unavailable",
            }
            for name, item in result.items()
        }
        details["full"] = {name: item.to_dict() for name, item in result.items()}
        return contract, details

    def _normalized_input(
        self,
        *,
        now: datetime,
        session: Any,
        state: Mapping[str, Any],
        readiness: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not session.live:
            raise ThetaDataError(ErrorCode.CALENDAR_CLOSED, retryable=False)
        if readiness.get("mdds") != "CONNECTED":
            raise ThetaDataError(ErrorCode.PROVIDER_DISCONNECTED, retryable=True)
        expirations = self.theta.expirations("SPXW")
        session_date = now.astimezone(ET).date()
        if session_date not in expirations:
            raise ThetaDataError(ErrorCode.PROVIDER_NO_DATA, route=ThetaRoute.OPTION_EXPIRATIONS)
        rate = self.theta.sofr(now=now)
        spxw_rows = self.theta.option_chain(
            symbol="SPXW", expiration=session_date, now=now,
            rate=float(rate["value_decimal"]), calendar=self.calendar,
            max_age_seconds=self.max_age_seconds,
        )
        if not spxw_rows:
            raise ThetaDataError(ErrorCode.PROVIDER_NO_DATA, route=ThetaRoute.OPTION_QUOTE)
        spot, spot_at = self._validated_underlying(spxw_rows)
        previous_close = state.get("previous_close")
        previous_date = state.get("previous_close_session_date")
        if not isinstance(previous_close, (int, float)) or previous_close <= 0 or previous_date == session.trading_date:
            raise KingNodeInputError("validated previous completed-session spot is unavailable")
        expiry_minutes = self.calendar.calendar_minutes_until(now, session_date)
        time_to_expiry_years = expiry_minutes / (365.0 * 24.0 * 60.0)
        if time_to_expiry_years <= 0:
            raise KingNodeInputError("0DTE contract has no positive time remaining")
        indices, index_details = self._reconstruct_indices(
            now=now, spxw_expirations=expirations, spxw_current=spxw_rows, rate=rate
        )
        missing = [name for name, item in indices.items() if item["provenance"] == "unavailable"]
        if missing:
            raise KingNodeInputError("required authorised volatility inputs are unavailable")
        rows: list[dict[str, Any]] = []
        for item in spxw_rows:
            if (
                item.underlying_price is None
                or item.underlying_timestamp is None
                or item.open_interest is None
                or item.open_interest_source_date is None
                or item.iv is None
                or item.delta is None
                or item.theta is None
                or len(item.advanced_greeks) != 8
            ):
                continue
            rows.append(
                {
                    "symbol": "SPXW",
                    "root": "SPXW",
                    "expiry": item.expiry,
                    "strike": item.strike,
                    "right": item.right,
                    "bid": item.bid,
                    "ask": item.ask,
                    "provider_timestamp": item.quote_timestamp,
                    "open_interest": item.open_interest,
                    "oi_source_date": item.open_interest_source_date,
                    "iv": item.iv,
                    "delta": item.delta,
                    "theta": item.theta,
                    "underlying": item.underlying_price,
                    "underlying_timestamp": item.underlying_timestamp,
                    "rate": float(rate["value_decimal"]),
                    "time_to_expiry_years": time_to_expiry_years,
                    "greeks": {key: value.to_dict() for key, value in item.advanced_greeks.items()},
                }
            )
        if not rows:
            raise KingNodeInputError("no fully normalised eligible SPXW option rows")
        source = {
            "provider": "ThetaData",
            "api_version": "v3",
            "entitlements": self.entitlements.to_dict(),
            "readiness": dict(readiness),
            "underlying_provenance": "option_underlying_proxy",
            "routes": [
                ThetaRoute.OPTION_EXPIRATIONS.value,
                ThetaRoute.OPTION_QUOTE.value,
                ThetaRoute.OPTION_FIRST_ORDER.value,
                ThetaRoute.OPTION_OPEN_INTEREST.value,
                ThetaRoute.RATE_EOD.value,
            ],
            "input_hash": content_hash(rows),
        }
        raw = {
            "schema_version": INPUT_SCHEMA_VERSION,
            "as_of": iso_utc(now),
            "session_date": session.trading_date,
            "underlying": {
                "symbol": "SPXW",
                "root": "SPXW",
                "spot": spot,
                "previous_close": float(previous_close),
                "timestamp": spot_at,
            },
            "expiration": {
                "expiry": session_date.isoformat(),
                "time_to_expiry_years": time_to_expiry_years,
                "rate": float(rate["value_decimal"]),
                "contract_multiplier": self.contract_multiplier,
            },
            "option_rows": rows,
            "indices": indices,
            "state": dict(state),
            "source": source,
        }
        return validate_normalized_input(raw).as_dict(), index_details

    @staticmethod
    def _engine_v2_builder() -> Callable[..., tuple[dict[str, Any], dict[str, Any]]]:
        from modules import king_node_engine

        builder = getattr(king_node_engine, "build_snapshot", None)
        if not callable(builder):
            raise KingNodeContractError("v2 engine entrypoint is unavailable")
        parameters = inspect.signature(builder).parameters
        if "normalized_input" not in parameters:
            raise KingNodeContractError("v2 engine entrypoint is not installed")
        return builder

    def _build_live_snapshot(
        self,
        *,
        normalized_input: Mapping[str, Any],
        reference: Any,
        state: Mapping[str, Any],
        index_details: Mapping[str, Any],
        now: datetime,
        session: Any,
        readiness: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        builder = self.engine_builder or self._engine_v2_builder()
        result = builder(
            dict(normalized_input),
            volatility=None,
            state=dict(state),
            source_meta={"provider": "ThetaData", "input_hash": normalized_input["source"]["input_hash"]},
            reference=reference.raw,
            generated_at=now,
            session_date=session.trading_date,
            market_minute=now.astimezone(ET).hour * 60 + now.astimezone(ET).minute,
        )
        if not isinstance(result, tuple) or len(result) != 2:
            raise KingNodeContractError("v2 engine returned an invalid result")
        engine_snapshot, next_state = result
        if not isinstance(engine_snapshot, dict) or not isinstance(next_state, dict):
            raise KingNodeContractError("v2 engine returned invalid snapshot/state")
        quote_times = [parse_timestamp(row["provider_timestamp"]) for row in normalized_input["option_rows"]]
        oldest = min(item for item in quote_times if item is not None)
        age = max(0.0, (now - oldest).total_seconds())
        if age > self.max_age_seconds:
            raise ThetaDataError(ErrorCode.STALE_INPUT, retryable=True)
        timestamp = iso_utc(now)
        snapshot = dict(engine_snapshot)
        snapshot.update(
            {
                "schema_version": V2_SCHEMA_VERSION,
                "status": "live",
                "generated_at": timestamp,
                "calculation_at": timestamp,
                "publication_at": timestamp,
                "session": session.to_dict(),
                "freshness": {
                    "max_age_seconds": self.max_age_seconds,
                    "oldest_observation_at": iso_utc(oldest),
                    "oldest_age_seconds": age,
                    "stale": False,
                },
                "provenance": {
                    "provider": "ThetaData",
                    "api_version": "v3",
                    "entitlements": self.entitlements.to_dict(),
                    "readiness": dict(readiness),
                    "underlying": "option_underlying_proxy",
                    "input_hash": normalized_input["source"]["input_hash"],
                    "indices": index_details.get("full", {}),
                },
                "reference": {
                    "status": "verified",
                    "canonical_checksum": reference.checksum,
                    "workbook_sha256": reference.authority.get("workbook_sha256"),
                    "catalogue_sha256": reference.authority.get("catalogue_sha256"),
                },
                "formula_coverage": {
                    "status": "verified",
                    "checksum": reference.authority.get("formula_coverage_checksum"),
                },
                "inputs": {
                    "underlying": normalized_input["underlying"],
                    "expiration": normalized_input["expiration"],
                    "indices": normalized_input["indices"],
                },
            }
        )
        existing_quality = snapshot.get("quality") if isinstance(snapshot.get("quality"), dict) else {}
        engine_errors = existing_quality.get("errors", [])
        if engine_errors:
            raise KingNodeContractError("v2 engine reported invalid quality")
        snapshot["quality"] = {
            **existing_quality,
            "valid": True,
            "grade": "LIVE",
            "errors": [],
            "warnings": list(existing_quality.get("warnings", [])),
        }
        for required in ("rows", "totals", "regime", "levels", "monitor", "directions", "presentation"):
            if required not in snapshot or not isinstance(snapshot[required], (dict, list)):
                raise KingNodeContractError(f"v2 engine snapshot is missing {required}")
        snapshot = _no_path_payload(snapshot)
        snapshot["provenance"]["content_hash"] = content_hash(snapshot)
        return snapshot, next_state

    def _seal_completed_session(self, *, now: datetime, session: Any) -> dict[str, Any] | None:
        if session.state is not SessionState.POST_CLOSE:
            return None
        try:
            live = _load_json_object(self.artifacts.live)
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        if (
            live.get("schema_version") != V2_SCHEMA_VERSION
            or live.get("status") != "live"
            or live.get("session", {}).get("trading_date") != session.trading_date
            or live.get("quality", {}).get("valid") is not True
        ):
            return None
        sealed = _no_path_payload(dict(live))
        sealed["status"] = "last_completed_session"
        sealed["publication_at"] = iso_utc(now)
        sealed["session"] = {**dict(live.get("session", {})), "completed_session_date": session.trading_date}
        sealed["freshness"] = {
            **dict(live.get("freshness", {})),
            "kind": "sealed_completed_session",
            "stale": False,
            "sealed_at": iso_utc(now),
        }
        sealed.setdefault("provenance", {})["content_hash"] = content_hash(sealed)
        _atomic_write_json(self.artifacts.last_completed, sealed)
        spot = live.get("inputs", {}).get("underlying", {}).get("spot")
        if isinstance(spot, (int, float)) and not isinstance(spot, bool) and spot > 0:
            state = _read_v2_state(self.artifacts.state)
            state["previous_close"] = float(spot)
            state["previous_close_session_date"] = session.trading_date
            state["schema_version"] = "king-node.v2-state"
            _atomic_write_json(self.artifacts.state, _no_path_payload(state))
        return sealed

    def run_once(self, now: datetime | None = None) -> dict[str, Any]:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        session = self.calendar.session_at(now)
        readiness: Mapping[str, Any] | None = None
        if not session.live:
            sealed = self._seal_completed_session(now=now, session=session)
            error = {
                "code": ErrorCode.CALENDAR_CLOSED.value,
                "component": "session",
                "retryable": False,
            }
            attempt = self._unavailable_snapshot(now=now, session=session, error=error)
            _atomic_write_json(self.artifacts.current_attempt, attempt)
            self._write_health(session=session, readiness=None, status="closed", error=error)
            return sealed or attempt
        try:
            readiness = self.theta.readiness(now=now).to_dict()
            state = _read_v2_state(self.artifacts.state)
            normalized_input, index_details = self._normalized_input(
                now=now, session=session, state=state, readiness=readiness
            )
            reference = self._read_reference()
            snapshot, next_state = self._build_live_snapshot(
                normalized_input=normalized_input,
                reference=reference,
                state=state,
                index_details=index_details,
                now=now,
                session=session,
                readiness=readiness,
            )
            next_state = dict(next_state)
            next_state["schema_version"] = "king-node.v2-state"
            next_state["last_live_session_date"] = session.trading_date
            next_state["last_live_spot"] = normalized_input["underlying"]["spot"]
            _atomic_write_json(self.artifacts.current_attempt, snapshot)
            _atomic_write_json(self.artifacts.state, _no_path_payload(next_state))
            _atomic_write_json(self.artifacts.live, snapshot)
            self._write_health(session=session, readiness=readiness, status="ready")
            return snapshot
        except Exception as exc:
            error = _safe_error_code(exc, component="refresh")
            attempt = self._unavailable_snapshot(
                now=now, session=session, error=error, readiness=readiness
            )
            _atomic_write_json(self.artifacts.current_attempt, attempt)
            self._write_health(session=session, readiness=readiness, status="unavailable", error=error)
            return attempt


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _optional_float_env(name: str) -> float | None:
    value = os.getenv(name, "").strip()
    return float(value) if value else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ThetaData-only KING NODE v2 producer")
    parser.add_argument(
        "--interval",
        type=_positive_int,
        default=int(os.getenv("KING_NODE_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)),
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            os.getenv("KING_NODE_OUTPUT", PROJECT_ROOT / "runtime/king_node/latest.json")
        ),
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path(
            os.getenv(
                "KING_NODE_STATE_FILE", PROJECT_ROOT / "runtime/king_node/state.json"
            )
        ),
    )
    parser.add_argument(
        "--current-attempt",
        type=Path,
        default=Path(
            os.getenv(
                "KING_NODE_CURRENT_ATTEMPT",
                Path(os.getenv("KING_NODE_OUTPUT", "/var/lib/king-node/latest.json")).with_name("current-attempt.json"),
            )
        ),
    )
    parser.add_argument(
        "--last-completed",
        type=Path,
        default=Path(
            os.getenv(
                "KING_NODE_LAST_COMPLETED_SNAPSHOT",
                Path(os.getenv("KING_NODE_OUTPUT", "/var/lib/king-node/latest.json")).with_name("last-completed.json"),
            )
        ),
    )
    parser.add_argument(
        "--health-output",
        type=Path,
        default=Path(
            os.getenv(
                "KING_NODE_HEALTH_STATE",
                Path(os.getenv("KING_NODE_OUTPUT", "/var/lib/king-node/latest.json")).with_name("health.json"),
            )
        ),
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path(
            os.getenv(
                "KING_NODE_REFERENCE", PROJECT_ROOT / "config/king_node_reference.json"
            )
        ),
    )
    parser.add_argument(
        "--thetadata-url",
        default=os.getenv("THETADATA_URL", "http://127.0.0.1:25503/v3"),
    )
    parser.add_argument(
        "--option-max-age",
        type=_positive_int,
        default=int(os.getenv("KING_NODE_LIVE_MAX_AGE_SECONDS", V2_DEFAULT_MAX_AGE_SECONDS)),
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default=os.getenv("KING_NODE_LOG_LEVEL", "INFO").upper(),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    service = KingNodeV2Service(
        artifacts=V2ArtifactPaths(
            current_attempt=args.current_attempt,
            live=args.output,
            last_completed=args.last_completed,
            state=args.state_file,
            health=args.health_output,
        ),
        reference_path=args.reference,
        thetadata_url=args.thetadata_url,
        max_age_seconds=args.option_max_age,
        min_underlying_observations=int(
            os.getenv(
                "KING_NODE_THETA_MIN_UNDERLYING_OBSERVATIONS",
                DEFAULT_MIN_UNDERLYING_OBSERVATIONS,
            )
        ),
        max_underlying_dispersion_pct=float(
            os.getenv(
                "KING_NODE_THETA_MAX_UNDERLYING_DISPERSION_PCT",
                DEFAULT_MAX_UNDERLYING_DISPERSION_PCT,
            )
        ),
        min_valid_strikes=int(
            os.getenv(
                "KING_NODE_THETA_MIN_VALID_STRIKES_PER_TERM", DEFAULT_MIN_VALID_STRIKES
            )
        ),
    )
    running = True

    def stop(*_: Any) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)
    try:
        while running:
            cycle_started = time.monotonic()
            snapshot = service.run_once()
            LOGGER.info(
                "KING NODE v2 refresh status=%s quality=%s",
                snapshot.get("status"),
                snapshot.get("quality", {}).get("grade"),
            )
            if args.once:
                return 0 if snapshot.get("status") in {"live", "last_completed_session"} else 1
            deadline = max(0.0, args.interval - (time.monotonic() - cycle_started))
            while running and deadline > 0:
                wait = min(deadline, 1.0)
                time.sleep(wait)
                deadline -= wait
    finally:
        service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
