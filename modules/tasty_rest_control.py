"""Cross-process pacing and backoff for Tastytrade REST requests.

All production services run as separate processes, so an in-memory semaphore is
not enough.  This module keeps the small amount of coordination state under
``/run/lock`` and protects it with ``flock``.  The state is intentionally
ephemeral: a reboot starts with a clean limiter.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
from pathlib import Path
import time
from typing import Callable


def _env_float(name: str, default: float, minimum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


class SharedRestGate:
    """Serialize request starts and share HTTP-429 cooldowns across processes."""

    def __init__(
        self,
        *,
        lock_path: str | Path,
        state_path: str | Path,
        min_interval_seconds: float,
        base_backoff_seconds: float,
        max_backoff_seconds: float,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.lock_path = Path(lock_path)
        self.state_path = Path(state_path)
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self.base_backoff_seconds = max(1.0, base_backoff_seconds)
        self.max_backoff_seconds = max(
            self.base_backoff_seconds, max_backoff_seconds
        )
        self._clock = clock
        self._sleep = sleeper

    @staticmethod
    def _default_state() -> dict[str, float | int]:
        return {
            "last_request_at": 0.0,
            "backoff_until": 0.0,
            "consecutive_429": 0,
            "last_429_at": 0.0,
        }

    def _read_state(self) -> dict[str, float | int]:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
            return self._default_state()

        state = self._default_state()
        for key in state:
            value = raw.get(key)
            if isinstance(value, (int, float)):
                state[key] = value
        return state

    def _write_state(self, state: dict[str, float | int]) -> None:
        temp_path = self.state_path.with_name(
            f".{self.state_path.name}.{os.getpid()}.tmp"
        )
        temp_path.write_text(
            json.dumps(state, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temp_path, self.state_path)

    def _with_locked_state(self, callback):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                state = self._read_state()
                result = callback(state)
                self._write_state(state)
                return result
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def wait(self) -> float:
        """Wait for the next globally permitted request start."""

        started = self._clock()
        while True:
            now = self._clock()

            def reserve(state):
                ready_at = max(
                    float(state["backoff_until"]),
                    float(state["last_request_at"]) + self.min_interval_seconds,
                )
                if now >= ready_at:
                    state["last_request_at"] = now
                    return 0.0
                return ready_at - now

            delay = float(self._with_locked_state(reserve))
            if delay <= 0:
                return max(0.0, self._clock() - started)
            self._sleep(min(delay, 1.0))

    def report_rate_limit(self) -> float:
        """Publish an exponential cooldown and return its duration."""

        now = self._clock()

        def update(state):
            failures = int(state["consecutive_429"]) + 1
            delay = min(
                self.max_backoff_seconds,
                self.base_backoff_seconds * (2 ** (failures - 1)),
            )
            state["consecutive_429"] = failures
            state["last_429_at"] = now
            state["backoff_until"] = max(
                float(state["backoff_until"]), now + delay
            )
            return delay

        return float(self._with_locked_state(update))

    def report_success(self) -> None:
        """Reset a completed cooldown after a successful REST response."""

        now = self._clock()

        def update(state):
            if now >= float(state["backoff_until"]):
                state["consecutive_429"] = 0
                state["backoff_until"] = 0.0

        self._with_locked_state(update)

    def snapshot(self) -> dict[str, float | int]:
        return self._with_locked_state(lambda state: dict(state))


REST_GATE = SharedRestGate(
    lock_path=os.getenv(
        "TASTY_REST_GATE_LOCK_PATH", "/run/lock/ogp-tastytrade-rest.lock"
    ),
    state_path=os.getenv(
        "TASTY_REST_GATE_STATE_PATH", "/run/lock/ogp-tastytrade-rest.json"
    ),
    min_interval_seconds=_env_float(
        "TASTY_REST_MIN_INTERVAL_SECONDS", 2.0, 0.0
    ),
    base_backoff_seconds=_env_float(
        "TASTY_REST_429_BASE_BACKOFF_SECONDS", 60.0, 1.0
    ),
    max_backoff_seconds=_env_float(
        "TASTY_REST_429_MAX_BACKOFF_SECONDS", 300.0, 1.0
    ),
)


def is_rate_limit_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "429" in text and "too many requests" in text


async def wait_for_rest_slot() -> float:
    return await asyncio.to_thread(REST_GATE.wait)


def report_rest_rate_limit() -> float:
    return REST_GATE.report_rate_limit()


def report_rest_success() -> None:
    REST_GATE.report_success()
