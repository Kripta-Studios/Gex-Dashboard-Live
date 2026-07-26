"""Real-time JSON service for the portable KING NODE dashboard.

The service combines the newest Tastytrade SPX 0DTE exposure JSON with observed
VIX/VVIX/VIX1D index prices from Theta Terminal, runs the pure calculation
engine, persists its hysteresis state, and atomically publishes one web
snapshot.

Typical VPS usage::

    python services/king_node_service.py --interval 30

One-shot validation::

    python services/king_node_service.py --once
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import signal
import sys
import tempfile
import time
from typing import Any
from zoneinfo import ZoneInfo

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


LOGGER = logging.getLogger("king_node_service")
ET = ZoneInfo("America/New_York")
DEFAULT_INTERVAL_SECONDS = 30
DEFAULT_TASTY_MAX_AGE_SECONDS = 900
DEFAULT_INDEX_MAX_AGE_SECONDS = 180
FILENAME_TIMESTAMP = re.compile(r"_(\d{8})_(\d{6})\.json$", re.IGNORECASE)


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and abs(parsed) != float("inf") else None


def _parse_timestamp(value: Any, *, default_zone: ZoneInfo = ET) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_zone)
    return parsed.astimezone(timezone.utc)


def _timestamp_from_path(path: Path) -> datetime:
    match = FILENAME_TIMESTAMP.search(path.name)
    if match:
        try:
            local = datetime.strptime(
                "".join(match.groups()),
                "%Y%m%d%H%M%S",
            ).replace(tzinfo=ET)
            return local.astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _age_seconds(timestamp: datetime | None, now: datetime) -> float | None:
    if timestamp is None:
        return None
    return max(0.0, (now - timestamp).total_seconds())


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
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
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise RuntimeError(f"Tastytrade JSON changed while it was being read: {path}")
    return payload


def _flatten_theta_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows: list[dict[str, Any]] = []
        for item in payload:
            rows.extend(_flatten_theta_rows(item))
        return rows
    if not isinstance(payload, dict):
        return []
    if "price" in payload:
        return [payload]
    rows = []
    for key in ("response", "data", "result", "items", "rows"):
        if key in payload:
            rows.extend(_flatten_theta_rows(payload[key]))
    return rows


class ThetaIndexClient:
    """Small client for ThetaData v3 ``index/snapshot/price``."""

    def __init__(
        self,
        base_url: str,
        *,
        max_age_seconds: int = DEFAULT_INDEX_MAX_AGE_SECONDS,
        timeout_seconds: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_age_seconds = int(max_age_seconds)
        self.client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def fetch(self, symbol: str, now: datetime | None = None) -> dict[str, Any]:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        endpoint = f"{self.base_url}/index/snapshot/price"
        try:
            response = self.client.get(
                endpoint,
                params={"symbol": symbol, "format": "json"},
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and (
                "error_code" in payload or "code" in payload and "price" not in payload
            ):
                raise RuntimeError(
                    str(
                        payload.get("error")
                        or payload.get("message")
                        or payload.get("error_code")
                        or payload.get("code")
                    )
                )
            rows = _flatten_theta_rows(payload)
            valid = []
            for row in rows:
                price = _finite_number(row.get("price"))
                row_symbol = str(row.get("symbol", symbol)).upper()
                if price is None or row_symbol != symbol.upper():
                    continue
                timestamp = _parse_timestamp(row.get("timestamp"))
                valid.append((timestamp or datetime.min.replace(tzinfo=timezone.utc), price))
            if not valid:
                raise RuntimeError("ThetaData returned no valid index price row")
            observed_at, price = max(valid, key=lambda item: item[0])
            if observed_at.year == 1:
                observed_at = now
            age = _age_seconds(observed_at, now)
            stale = age is not None and age > self.max_age_seconds
            return {
                "value": price,
                "timestamp": _iso_utc(observed_at),
                "age_seconds": age,
                "status": "stale" if stale else "observed",
                "source": "ThetaData v3 index/snapshot/price",
                "symbol": symbol.upper(),
                "endpoint": endpoint,
            }
        except Exception as exc:
            return {
                "value": None,
                "timestamp": None,
                "age_seconds": None,
                "status": "missing",
                "source": "ThetaData v3 index/snapshot/price",
                "symbol": symbol.upper(),
                "endpoint": endpoint,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def fetch_all(self, now: datetime | None = None) -> dict[str, dict[str, Any]]:
        return {
            symbol.lower(): self.fetch(symbol, now=now)
            for symbol in ("VIX", "VVIX", "VIX1D")
        }

    def __enter__(self) -> "ThetaIndexClient":
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
        index_max_age_seconds: int = DEFAULT_INDEX_MAX_AGE_SECONDS,
        theta_enabled: bool = True,
    ) -> None:
        self.tasty_data_dir = tasty_data_dir
        self.output_path = output_path
        self.state_path = state_path
        self.reference_path = reference_path
        self.tasty_max_age_seconds = int(tasty_max_age_seconds)
        self.theta_enabled = bool(theta_enabled)
        self.theta = ThetaIndexClient(
            thetadata_url,
            max_age_seconds=index_max_age_seconds,
        )

    def close(self) -> None:
        self.theta.close()

    def run_once(self, now: datetime | None = None) -> dict[str, Any]:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        session_date = now.astimezone(ET).date().isoformat()
        tasty_path = find_latest_tastytrade_json(self.tasty_data_dir)
        tasty_payload = read_stable_json(tasty_path)
        tasty_timestamp = _timestamp_from_path(tasty_path)
        tasty_age = _age_seconds(tasty_timestamp, now)
        tasty_stale = (
            tasty_age is not None and tasty_age > self.tasty_max_age_seconds
        )
        source_meta = {
            "path": str(tasty_path.resolve()),
            "filename": tasty_path.name,
            "source_id": f"{tasty_path.name}:{tasty_path.stat().st_size}",
            "timestamp": _iso_utc(tasty_timestamp),
            "age_seconds": tasty_age,
            "stale": tasty_stale,
            "max_age_seconds": self.tasty_max_age_seconds,
            "provider": "Tastytrade via services/gex_daemon.py",
        }
        volatility = (
            self.theta.fetch_all(now=now)
            if self.theta_enabled
            else {
                name: {
                    "value": None,
                    "status": "disabled",
                    "source": "ThetaData disabled by CLI",
                }
                for name in ("vix", "vvix", "vix1d")
            }
        )
        state = _load_state(self.state_path, session_date)
        reference = _load_reference(self.reference_path)
        snapshot, next_state = build_snapshot(
            tasty_payload,
            volatility,
            state,
            source_meta=source_meta,
            reference=reference,
            generated_at=now,
            session_date=session_date,
            market_minute=(
                now.astimezone(ET).hour * 60 + now.astimezone(ET).minute
            ),
        )
        _atomic_write_json(self.state_path, next_state)
        _atomic_write_json(self.output_path, snapshot)
        return snapshot

    def publish_error(self, exc: Exception, now: datetime | None = None) -> dict[str, Any]:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "generated_at": _iso_utc(now),
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interval",
        type=_positive_int,
        default=int(os.getenv("KING_NODE_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)),
        help="Seconds between cycles (default: 30)",
    )
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument(
        "--tasty-data-dir",
        type=Path,
        default=Path(os.getenv("KING_NODE_TASTY_DATA_DIR", PROJECT_ROOT / "json_data")),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            os.getenv(
                "KING_NODE_OUTPUT",
                PROJECT_ROOT / "runtime" / "king_node" / "latest.json",
            )
        ),
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path(
            os.getenv(
                "KING_NODE_STATE_FILE",
                PROJECT_ROOT / "runtime" / "king_node" / "state.json",
            )
        ),
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path(
            os.getenv(
                "KING_NODE_REFERENCE",
                PROJECT_ROOT / "config" / "king_node_reference.json",
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
        default=int(
            os.getenv(
                "KING_NODE_TASTY_MAX_AGE_SECONDS",
                DEFAULT_TASTY_MAX_AGE_SECONDS,
            )
        ),
    )
    parser.add_argument(
        "--index-max-age",
        type=_positive_int,
        default=int(
            os.getenv(
                "KING_NODE_INDEX_MAX_AGE_SECONDS",
                DEFAULT_INDEX_MAX_AGE_SECONDS,
            )
        ),
    )
    parser.add_argument(
        "--no-theta",
        action="store_true",
        help="Disable ThetaData calls (test/diagnostic mode; output degrades)",
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

    service = KingNodeService(
        tasty_data_dir=args.tasty_data_dir,
        output_path=args.output,
        state_path=args.state_file,
        reference_path=args.reference,
        thetadata_url=args.thetadata_url,
        tasty_max_age_seconds=args.tasty_max_age,
        index_max_age_seconds=args.index_max_age,
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
            except (KingNodeDataError, FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
                service.publish_error(exc)
                LOGGER.exception("KING NODE cycle failed closed")
                if args.once:
                    return 1
            if args.once:
                break
            elapsed = time.monotonic() - cycle_started
            deadline = max(0.0, args.interval - elapsed)
            while running and deadline > 0:
                wait = min(deadline, 1.0)
                time.sleep(wait)
                deadline -= wait
    finally:
        service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

