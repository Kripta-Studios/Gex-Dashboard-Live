"""Pinned bounded resource-wait protocol for B06/R3 operational scheduling."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import hashlib
import math
import os
from pathlib import Path
import time
from typing import Any, Callable, Mapping


SCHEMA = "weekly_zone_event_value_path_resource_wait_v1"
THRESHOLD_BYTES = 2_000_000_000
WAIT_SECONDS = 600.0
SLEEP_SECONDS = 5.0
OBSERVATION_KEYS = {"available_ram_bytes", "free_commit_bytes"}
DECISION_FIELDS = ("available_ram_bytes", "disk_free_bytes", "free_commit_bytes")
ROW_KEYS = {
    "schema", "seq", "status", "stage", "identity", "attempt", "utc",
    "elapsed_monotonic_seconds", "remaining_monotonic_seconds",
    "threshold_bytes", "observation", "disk_free_bytes", "deficient_fields",
    "planned_sleep_seconds", "final_wait_seq", "interruption_type",
}


class ResourceWaitError(RuntimeError):
    """Fatal malformed observation, evidence failure, or timeout."""


class ResourceWaitTimeout(ResourceWaitError):
    """The exact monotonic wait budget expired."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResourceWaiter:
    def __init__(
        self,
        *,
        observation: Callable[[], Mapping[str, Any]],
        official_gate: Callable[[Mapping[str, Any]], Any],
        disk_probe: Callable[[], Any],
        evidence_path: Path,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], Any] = time.sleep,
        utc_now: Callable[[], str] = _utc_now,
        wait_seconds: float = WAIT_SECONDS,
        sleep_seconds: float = SLEEP_SECONDS,
    ) -> None:
        if wait_seconds != WAIT_SECONDS or sleep_seconds != SLEEP_SECONDS:
            raise ResourceWaitError("resource wait constants are immutable")
        self.observation = observation
        self.official_gate = official_gate
        self.disk_probe = disk_probe
        self.evidence_path = Path(evidence_path)
        self.monotonic = monotonic
        self.sleeper = sleeper
        self.utc_now = utc_now
        self._seq = 0

    def _append(self, row: Mapping[str, Any]) -> None:
        if set(row) != ROW_KEYS or row["seq"] != self._seq:
            raise ResourceWaitError("invalid resource wait row")
        payload = json.dumps(
            row, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8") + b"\n"
        with self.evidence_path.open("ab") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        self._seq += 1

    @staticmethod
    def _validate_observation(value: Any) -> dict[str, int]:
        if not isinstance(value, Mapping) or set(value) != OBSERVATION_KEYS:
            raise ResourceWaitError("malformed official resource observation schema")
        result = dict(value)
        if not all(type(result[key]) is int and result[key] >= 0 for key in OBSERVATION_KEYS):
            raise ResourceWaitError("malformed official resource observation values")
        return result

    @staticmethod
    def _validate_disk(value: Any) -> int:
        if type(value) is not int or value < 0:
            raise ResourceWaitError("malformed disk observation")
        return value

    def _row(
        self, *, status: str, stage: str, identity: str, attempt: int,
        started: float, now: float, deadline: float,
        observation: Mapping[str, int] | None, disk_free: int | None,
        deficient: list[str], planned_sleep: float | None,
        final_wait_seq: int | None, interruption_type: str | None,
    ) -> dict[str, Any]:
        return {
            "schema": SCHEMA, "seq": self._seq, "status": status,
            "stage": stage, "identity": identity, "attempt": attempt,
            "utc": self.utc_now(),
            "elapsed_monotonic_seconds": float(max(0.0, now - started)),
            "remaining_monotonic_seconds": float(max(0.0, deadline - now)),
            "threshold_bytes": THRESHOLD_BYTES,
            "observation": dict(observation) if observation is not None else None,
            "disk_free_bytes": disk_free, "deficient_fields": list(deficient),
            "planned_sleep_seconds": planned_sleep,
            "final_wait_seq": final_wait_seq,
            "interruption_type": interruption_type,
        }

    def _interrupted(
        self, *, stage: str, identity: str, attempt: int, started: float,
        deadline: float, last_observation: Mapping[str, int] | None,
        last_disk: int | None, last_deficient: list[str], last_wait_seq: int | None,
        error: BaseException,
    ) -> None:
        now = self.monotonic()
        self._append(self._row(
            status="INTERRUPTED", stage=stage, identity=identity,
            attempt=attempt, started=started, now=now, deadline=deadline,
            observation=last_observation, disk_free=last_disk,
            deficient=last_deficient, planned_sleep=None,
            final_wait_seq=last_wait_seq, interruption_type=type(error).__name__,
        ))

    def acquire(self, stage: str, identity: str) -> dict[str, int]:
        if not isinstance(stage, str) or not stage or not isinstance(identity, str) or not identity:
            raise ResourceWaitError("resource wait unit identity")
        started = self.monotonic()
        deadline = started + WAIT_SECONDS
        attempt = 0
        last_observation: dict[str, int] | None = None
        last_disk: int | None = None
        last_deficient: list[str] = []
        last_wait_seq: int | None = None
        while True:
            try:
                observed = self._validate_observation(self.observation())
                disk_free = self._validate_disk(self.disk_probe())
            except (KeyboardInterrupt, InterruptedError) as error:
                self._interrupted(
                    stage=stage, identity=identity, attempt=attempt,
                    started=started, deadline=deadline,
                    last_observation=last_observation, last_disk=last_disk,
                    last_deficient=last_deficient, last_wait_seq=last_wait_seq,
                    error=error,
                )
                raise
            deficient = sorted(
                key for key, value in {
                    **observed, "disk_free_bytes": disk_free,
                }.items() if value < THRESHOLD_BYTES
            )
            try:
                self.official_gate(observed)
            except (KeyboardInterrupt, InterruptedError) as error:
                self._interrupted(
                    stage=stage, identity=identity, attempt=attempt,
                    started=started, deadline=deadline,
                    last_observation=observed, last_disk=disk_free,
                    last_deficient=deficient, last_wait_seq=last_wait_seq,
                    error=error,
                )
                raise
            except Exception as error:
                expected_gate_error = (
                    type(error) is ValueError
                    and str(error) == "2GB RAM/commit gate unmet"
                    and any(key in deficient for key in OBSERVATION_KEYS)
                )
                if not expected_gate_error:
                    raise ResourceWaitError("official resource gate failed without numeric deficit") from error
            else:
                if not any(key in deficient for key in OBSERVATION_KEYS):
                    if not deficient:
                        return {**observed, "disk_free_bytes": disk_free}
            now = self.monotonic()
            remaining = max(0.0, deadline - now)
            planned = min(SLEEP_SECONDS, remaining)
            last_observation, last_disk, last_deficient = observed, disk_free, deficient
            last_wait_seq = self._seq
            self._append(self._row(
                status="WAIT", stage=stage, identity=identity, attempt=attempt,
                started=started, now=now, deadline=deadline,
                observation=observed, disk_free=disk_free, deficient=deficient,
                planned_sleep=float(planned), final_wait_seq=None,
                interruption_type=None,
            ))
            if remaining == 0.0:
                self._append(self._row(
                    status="TIMEOUT", stage=stage, identity=identity,
                    attempt=attempt, started=started, now=now, deadline=deadline,
                    observation=observed, disk_free=disk_free,
                    deficient=deficient, planned_sleep=0.0,
                    final_wait_seq=last_wait_seq, interruption_type=None,
                ))
                raise ResourceWaitTimeout("bounded resource wait timed out")
            try:
                self.sleeper(planned)
            except (KeyboardInterrupt, InterruptedError) as error:
                self._interrupted(
                    stage=stage, identity=identity, attempt=attempt,
                    started=started, deadline=deadline,
                    last_observation=last_observation, last_disk=last_disk,
                    last_deficient=last_deficient, last_wait_seq=last_wait_seq,
                    error=error,
                )
                raise
            attempt += 1


def validate_resource_wait_rows(rows: Any) -> None:
    if not isinstance(rows, list) or not rows:
        raise ResourceWaitError("resource wait evidence must contain rows")
    last_wait_by_unit: dict[tuple[str, str], int] = {}
    last_attempt_by_unit: dict[tuple[str, str], int] = {}
    last_elapsed_by_unit: dict[tuple[str, str], float] = {}
    last_remaining_by_unit: dict[tuple[str, str], float] = {}
    terminal_seen = False
    for seq, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != ROW_KEYS or type(row.get("seq")) is not int or row["seq"] != seq:
            raise ResourceWaitError("resource wait evidence row schema/sequence")
        if row.get("schema") != SCHEMA or row.get("status") not in {"WAIT", "TIMEOUT", "INTERRUPTED"}:
            raise ResourceWaitError("resource wait evidence identity")
        if type(row.get("attempt")) is not int or row["attempt"] < 0:
            raise ResourceWaitError("resource wait attempt")
        if type(row.get("threshold_bytes")) is not int or row["threshold_bytes"] != THRESHOLD_BYTES:
            raise ResourceWaitError("resource wait threshold")
        final_wait_seq = row.get("final_wait_seq")
        if final_wait_seq is not None and (type(final_wait_seq) is not int or final_wait_seq < 0):
            raise ResourceWaitError("resource wait final sequence type")
        deficient_value = row.get("deficient_fields")
        if (not isinstance(deficient_value, list)
                or any(not isinstance(key, str) or key not in DECISION_FIELDS for key in deficient_value)
                or deficient_value != sorted(set(deficient_value))):
            raise ResourceWaitError("resource wait deficient field schema")
        if not isinstance(row.get("utc"), str) or not row["utc"]:
            raise ResourceWaitError("resource wait utc")
        monotonic_values = (row.get("elapsed_monotonic_seconds"), row.get("remaining_monotonic_seconds"))
        if not all(type(value) is float and math.isfinite(value) and value >= 0.0 for value in monotonic_values):
            raise ResourceWaitError("resource wait monotonic fields")
        unit = (row.get("stage"), row.get("identity"))
        if not all(isinstance(item, str) and item for item in unit):
            raise ResourceWaitError("resource wait unit")
        if terminal_seen:
            raise ResourceWaitError("resource wait row after terminal status")
        elapsed, remaining = monotonic_values
        if not math.isclose(elapsed + remaining, WAIT_SECONDS, rel_tol=0.0, abs_tol=1e-9) and remaining != 0.0:
            raise ResourceWaitError("resource wait deadline relationship")
        if elapsed < last_elapsed_by_unit.get(unit, 0.0) or remaining > last_remaining_by_unit.get(unit, WAIT_SECONDS):
            raise ResourceWaitError("resource wait monotonic sequence")
        status = row["status"]
        if status == "WAIT":
            observation = ResourceWaiter._validate_observation(row.get("observation"))
            disk = ResourceWaiter._validate_disk(row.get("disk_free_bytes"))
            deficient = sorted(key for key, value in {**observation, "disk_free_bytes": disk}.items() if value < THRESHOLD_BYTES)
            if row.get("deficient_fields") != deficient or not deficient:
                raise ResourceWaitError("resource wait deficient fields")
            planned = row.get("planned_sleep_seconds")
            if type(planned) is not float or not math.isfinite(planned) or planned != min(SLEEP_SECONDS, remaining):
                raise ResourceWaitError("resource wait planned sleep")
            if row.get("final_wait_seq") is not None or row.get("interruption_type") is not None:
                raise ResourceWaitError("resource WAIT terminal fields")
            expected_attempt = last_attempt_by_unit.get(unit, -1) + 1
            if row["attempt"] != expected_attempt:
                raise ResourceWaitError("resource WAIT attempt sequence")
            last_wait_by_unit[unit] = seq
            last_attempt_by_unit[unit] = row["attempt"]
        elif status == "TIMEOUT":
            if row.get("final_wait_seq") != seq - 1 or last_wait_by_unit.get(unit) != seq - 1:
                raise ResourceWaitError("resource TIMEOUT reference")
            if type(row.get("planned_sleep_seconds")) is not float or row["planned_sleep_seconds"] != 0.0 or row.get("interruption_type") is not None:
                raise ResourceWaitError("resource TIMEOUT fields")
            previous = rows[seq - 1]
            if remaining != 0.0 or elapsed < WAIT_SECONDS or row["attempt"] != previous["attempt"]:
                raise ResourceWaitError("resource TIMEOUT timing/attempt")
            for key in ("observation", "disk_free_bytes", "deficient_fields"):
                if row.get(key) != previous.get(key):
                    raise ResourceWaitError("resource TIMEOUT last observation")
            terminal_seen = True
        else:
            if row.get("planned_sleep_seconds") is not None or not isinstance(row.get("interruption_type"), str) or not row["interruption_type"]:
                raise ResourceWaitError("resource INTERRUPTED fields")
            if row.get("final_wait_seq") != last_wait_by_unit.get(unit):
                raise ResourceWaitError("resource INTERRUPTED reference")
            final_wait = row.get("final_wait_seq")
            if final_wait is None:
                if row.get("observation") is None:
                    if row.get("disk_free_bytes") is not None or row.get("deficient_fields") != []:
                        raise ResourceWaitError("resource INTERRUPTED pre-observation fields")
                else:
                    observation = ResourceWaiter._validate_observation(row["observation"])
                    disk = ResourceWaiter._validate_disk(row.get("disk_free_bytes"))
                    deficient = sorted(key for key, value in {**observation, "disk_free_bytes": disk}.items() if value < THRESHOLD_BYTES)
                    if row.get("deficient_fields") != deficient:
                        raise ResourceWaitError("resource INTERRUPTED valid observation")
            else:
                observation = ResourceWaiter._validate_observation(row.get("observation"))
                disk = ResourceWaiter._validate_disk(row.get("disk_free_bytes"))
                deficient = sorted(key for key, value in {**observation, "disk_free_bytes": disk}.items() if value < THRESHOLD_BYTES)
                if row.get("deficient_fields") != deficient:
                    raise ResourceWaitError("resource INTERRUPTED last valid observation")
            previous_attempt = last_attempt_by_unit.get(unit)
            if previous_attempt is not None and row["attempt"] not in {previous_attempt, previous_attempt + 1}:
                raise ResourceWaitError("resource INTERRUPTED attempt")
            terminal_seen = True
        last_elapsed_by_unit[unit] = elapsed
        last_remaining_by_unit[unit] = remaining


def _decode_resource_wait(raw: bytes) -> list[dict[str, Any]]:
    try:
        text = raw.decode("utf-8", errors="strict")
        if not text.endswith("\n") or not text:
            raise ResourceWaitError("truncated resource wait evidence")
        lines = text.splitlines()
        if not lines or any(not line for line in lines):
            raise ResourceWaitError("blank resource wait evidence row")
        rows = [json.loads(line) for line in lines]
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ResourceWaitError("invalid resource wait evidence") from error
    validate_resource_wait_rows(rows)
    canonical = b"".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n"
        for row in rows
    )
    if canonical != raw:
        raise ResourceWaitError("non-canonical resource wait evidence")
    return rows


def load_resource_wait_rows(path: Path) -> list[dict[str, Any]]:
    try:
        raw = Path(path).read_bytes()
    except OSError as error:
        raise ResourceWaitError("invalid resource wait evidence") from error
    return _decode_resource_wait(raw)


def resource_wait_pin(path: Path) -> dict[str, Any]:
    target = Path(path)
    before = target.stat()
    raw = target.read_bytes()
    _decode_resource_wait(raw)
    after = target.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ResourceWaitError("resource wait evidence drift")
    return {"path": str(Path(path)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
