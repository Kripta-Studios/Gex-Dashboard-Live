"""Real-time JSON service for the portable KING NODE dashboard.

VIX, VIX1D and VVIX are obtained with ThetaData Options STANDARD only:

* VIX spot is the robust median of ``underlying_price`` in VIX option Greeks;
* VIX1D is reconstructed from SPXW NBBO option chains;
* VVIX is reconstructed from VIX NBBO option chains.

No ThetaData direct index-price endpoint is used or required.
"""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta
import json
import logging
import os
from pathlib import Path
import re
import signal
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
from modules.volatility_indices import (  # noqa: E402
    ET,
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
                        row.get("timestamp", row.get("date")), default_zone=ET
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
            rate = self.fetch_rate(now)
            holidays = self.fetch_holidays(now)
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

        rate_decimal = float(rate["value_decimal"])
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
                "rate": rate,
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


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _optional_float_env(name: str) -> float | None:
    value = os.getenv(name, "").strip()
    return float(value) if value else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interval",
        type=_positive_int,
        default=int(os.getenv("KING_NODE_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)),
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--tasty-data-dir",
        type=Path,
        default=Path(os.getenv("KING_NODE_TASTY_DATA_DIR", PROJECT_ROOT / "json_data")),
    )
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
        "--tasty-max-age",
        type=_positive_int,
        default=int(os.getenv("KING_NODE_TASTY_MAX_AGE_SECONDS", DEFAULT_TASTY_MAX_AGE_SECONDS)),
    )
    parser.add_argument(
        "--option-max-age",
        type=_positive_int,
        default=int(os.getenv("KING_NODE_THETA_OPTION_MAX_AGE_SECONDS", DEFAULT_OPTION_MAX_AGE_SECONDS)),
    )
    parser.add_argument("--no-theta", action="store_true")
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
    service = KingNodeService(
        tasty_data_dir=args.tasty_data_dir,
        output_path=args.output,
        state_path=args.state_file,
        reference_path=args.reference,
        thetadata_url=args.thetadata_url,
        tasty_max_age_seconds=args.tasty_max_age,
        option_max_age_seconds=args.option_max_age,
        expiration_cache_seconds=int(
            os.getenv("KING_NODE_THETA_EXPIRATION_CACHE_SECONDS", DEFAULT_EXPIRATION_CACHE_SECONDS)
        ),
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
        rate_symbol=os.getenv("KING_NODE_RATE_SYMBOL", "SOFR"),
        rate_lookback_days=int(os.getenv("KING_NODE_RATE_LOOKBACK_DAYS", "10")),
        risk_free_rate_percent=_optional_float_env("KING_NODE_RISK_FREE_RATE_PERCENT"),
        theta_enabled=not args.no_theta,
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
            try:
                snapshot = service.run_once()
                LOGGER.info(
                    "Published KING NODE status=%s quality=%s strikes=%s raw_gamma_level=%s",
                    snapshot.get("status"),
                    snapshot.get("quality", {}).get("grade"),
                    snapshot.get("quality", {}).get("strike_count"),
                    snapshot.get("levels", {}).get("raw_gamma", {}).get("strike"),
                )
            except (
                KingNodeDataError,
                VolatilityDataError,
                FileNotFoundError,
                OSError,
                RuntimeError,
                ValueError,
            ) as exc:
                service.publish_error(exc)
                LOGGER.exception("KING NODE cycle failed closed")
                if args.once:
                    return 1
            if args.once:
                break
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
