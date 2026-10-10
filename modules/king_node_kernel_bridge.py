"""Isolated, JSON-persisted execution of source state machines without Excel/IBKR."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from types import FunctionType, SimpleNamespace
from zoneinfo import ZoneInfo

import schedula as sh

from modules import king_node_live_kernel as source
from modules.king_node_formula_runtime import col_label, coordinates, is_error, scalar


def encode(value):
    if isinstance(value, dict):
        return {"dict": [[encode(k), encode(v)] for k, v in value.items()]}
    if isinstance(value, deque):
        return {"deque": [encode(v) for v in value], "maxlen": value.maxlen}
    if isinstance(value, tuple):
        return {"tuple": [encode(v) for v in value]}
    if isinstance(value, set):
        return {"set": [encode(v) for v in sorted(value, key=repr)]}
    if isinstance(value, datetime):
        return {"datetime": value.isoformat()}
    if isinstance(value, date):
        return {"date": value.isoformat()}
    if isinstance(value, list):
        return [encode(v) for v in value]
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    raise TypeError(f"Non-persistable kernel state: {type(value).__name__}")


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    if "dict" in value:
        return {decode(k): decode(v) for k, v in value["dict"]}
    if "tuple" in value:
        return tuple(decode(v) for v in value["tuple"])
    if "set" in value:
        return {decode(v) for v in value["set"]}
    if "deque" in value:
        return deque((decode(v) for v in value["deque"]), maxlen=value["maxlen"])
    if "datetime" in value:
        return datetime.fromisoformat(value["datetime"])
    if "date" in value:
        return date.fromisoformat(value["date"])
    raise ValueError("Invalid kernel state")


def clean(value):
    value = scalar(value)
    if value is sh.EMPTY or is_error(value):
        return None
    return value


class Range:
    def __init__(self, workbook, sheet, address, writes):
        self.workbook, self.sheet, self.address, self.writes = (
            workbook,
            sheet,
            address,
            writes,
        )

    def bounds(self):
        parts = self.address.split(":")
        return coordinates(parts[0]), coordinates(parts[-1])

    @property
    def value(self):
        (c1, r1), (c2, r2) = self.bounds()
        data = [
            [
                clean(self.workbook.get(self.sheet, f"{col_label(c)}{r}"))
                for c in range(c1, c2 + 1)
            ]
            for r in range(r1, r2 + 1)
        ]
        if c1 == c2 and r1 == r2:
            return data[0][0]
        if r1 == r2:
            return data[0]
        if c1 == c2:
            return [r[0] for r in data]
        return data

    @value.setter
    def value(self, value):
        (c1, r1), (c2, r2) = self.bounds()
        if isinstance(value, (list, tuple)):
            values = [list(v) if isinstance(v, (list, tuple)) else [v] for v in value]
            r2, c2 = (
                r1 + len(values) - 1,
                c1 + max((len(v) for v in values), default=1) - 1,
            )
        else:
            values = [[value] * (c2 - c1 + 1) for _ in range(r2 - r1 + 1)]
        for r, row in enumerate(values, r1):
            for c, item in enumerate(row, c1):
                key = self.sheet, f"{col_label(c)}{r}"
                item = clean(item)
                self.workbook.set(*key, item)
                self.writes[key] = item


class Sheet:
    def __init__(self, workbook, name, writes):
        self.workbook, self.name, self.writes = workbook, name, writes

    def __getitem__(self, address):
        return Range(self.workbook, self.name, address, self.writes)

    range = __getitem__


class Kernel:
    def __init__(self, workbook, stored, now):
        self.state_keys = {
            k
            for k, v in vars(source).items()
            if k.startswith("_") and not k.startswith("__") and not callable(v)
        }
        namespace = {
            k: deepcopy(v)
            for k, v in vars(source).items()
            if k in self.state_keys or isinstance(v, (int, float, str, tuple, bool))
        }
        namespace.update(
            math=source.math,
            deque=deque,
            median=source.median,
            __builtins__=__builtins__,
            __name__=source.__name__,
        )
        self.writes, self.errors = {}, []

        class FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return (
                    now.astimezone(tz)
                    if tz
                    else now.astimezone(ZoneInfo("America/New_York")).replace(
                        tzinfo=None
                    )
                )

        namespace["datetime"] = SimpleNamespace(
            datetime=FixedDatetime, date=date, timedelta=timedelta, timezone=timezone
        )
        namespace.update(decode(stored) if stored else {})
        self.sheets = {
            name: Sheet(workbook, name, self.writes) for name in workbook.cells
        }
        namespace.update(
            sht=self.sheets["King Node Model"],
            sht_le=self.sheets["Level Engine"],
            sht_md=self.sheets["Master Dashboard"],
            wb=SimpleNamespace(sheets=self.sheets),
            et_now=lambda: now.astimezone(ZoneInfo("America/New_York")),
            time=SimpleNamespace(time=lambda: now.timestamp()),
            _recalc_full=lambda: None,
            print=lambda *args: self.errors.append(" ".join(map(str, args))),
        )
        for name, function in vars(source).items():
            if (
                isinstance(function, FunctionType)
                and function.__module__ == source.__name__
            ):
                namespace[name] = FunctionType(
                    function.__code__,
                    namespace,
                    name,
                    function.__defaults__,
                    function.__closure__,
                )
        self.ns = namespace

    def call(self, name, *args, **kwargs):
        return self.ns[name](*args, **kwargs)

    def persisted(self):
        return encode({k: self.ns[k] for k in self.state_keys})
