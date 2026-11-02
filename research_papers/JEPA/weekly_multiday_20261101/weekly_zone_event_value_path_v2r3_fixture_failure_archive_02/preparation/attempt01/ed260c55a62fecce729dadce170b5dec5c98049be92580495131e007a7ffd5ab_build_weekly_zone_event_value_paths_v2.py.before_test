"""Build outcome-free weekly option and cached-spot value paths.

This producer is intentionally self contained.  It does not import any closed
scientific producer and it never opens historical candidate or outcome files.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import importlib.util
import json
import math
import numbers
import os
import re
import shutil
import stat
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path, PureWindowsPath
from typing import Any, Callable, Iterable, Iterator, Mapping, MutableMapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


HERE = Path(__file__).absolute().parent
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
SOURCE_ROOT = Path(r"D:\ThetaData\data_options")
OUTPUT = BASE / "weekly_zone_event_value_paths_02"
OBSERVER = BASE / "weekly_zone_event_value_paths_observer_02"
OUTPUT_V1 = BASE / "weekly_zone_event_value_paths_01"
OBSERVER_V1 = BASE / "weekly_zone_event_value_paths_observer_01"
STAGE_A = BASE / "weekly_zone_event_source_plan_01"
STAGE_A_AUDIT = BASE / "weekly_zone_event_source_plan_audit_01"
STAGE_A_OBSERVER = BASE / "weekly_zone_event_source_plan_audit_observer_01"
CONTRACT = HERE / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2_CALENDAR_AMENDMENT_20261102.md"
ORIGINAL_CONTRACT = HERE / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md"
SPOT_MODULE = HERE / "weekly_zone_event_spot_paths.py"
RESOURCE_HELPER = HERE.parent / "level_oracle_20261018" / "launch_monthly_test_index_v2_audit_20261024.py"

CONTRACT_SHA256 = "65fd1aaef25ddea13957ce07e6c21285771adc889f097d603f93e00572cf1146"
ORIGINAL_CONTRACT_SHA256 = "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9"
RESOURCE_HELPER_SHA256 = "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"
STATUS = "COMPLETE_OUTCOME_FREE_VALUE_PATHS"
MIN_FREE = 2_000_000_000
TICKERS = ("SPY", "QQQ", "SPXW")
TICKER_ORDINAL = {value: index for index, value in enumerate(TICKERS)}
RIGHTS = ("CALL", "PUT")
RIGHT_ORDINAL = {value: index for index, value in enumerate(RIGHTS)}
ROLES = ("D", "D1", "H2")
ROLE_ORDINAL = {value: index for index, value in enumerate(ROLES)}
NY = ZoneInfo("America/New_York")
REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
ISO_CLOCK = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)

THREAD_VARS = (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS",
    "ARROW_NUM_THREADS", "POLARS_MAX_THREADS", "TBB_NUM_THREADS",
    "NUMBA_NUM_THREADS",
)

FLAGS = {
    "actions_read": False,
    "candidates_read": False,
    "context_feature_arrays_read": False,
    "economic_evaluation_performed": False,
    "fit_performed": False,
    "inference_performed": False,
    "labels_read": False,
    "models_read": False,
    "option_raw_values_read": True,
    "outcomes_read": False,
    "parquet_footers_read": True,
    "pnl_computed": False,
    "promotion_approved": False,
    "replay_performed": False,
    "risk_or_qty_computed": False,
    "selected_policy": None,
    "spot_cache_arrays_read": True,
    "technical_ready": False,
}

LIMITATIONS = [
    "Stored timestamps do not prove live receipt time.",
    "Underlying timestamp proxy has unknown age.",
    "Minute samples do not prove intraminute touches.",
    "Outcomes were not read.",
    "No economic evaluation was performed.",
]
SUMMARY_KEYS = {"schema", "status", "created_utc", "stage_a", "option_admission", "selector", "option_paths", "spot", "outputs", "flags", "limitations", "calendar_normalization"}
MANIFEST_KEYS = {"schema", "status", "created_utc", "implementation_pins", "authority_inputs", "admitted_option_sources", "admitted_spot_inputs", "outputs", "counts", "flags", "environment", "calendar_normalization"}
DATA_OUTPUT_NAMES = {"source_admission.jsonl", "decision_contracts.parquet", "option_quote_observations.parquet", "segment_coverage.parquet", "cache_admission.jsonl", "spot_paths.parquet", "spot_coverage.jsonl"}
CANONICAL_CALENDAR_BYTES = 137640
CANONICAL_CALENDAR_SHA256 = "13bc456a32c6dc711fffb71ef24375ecd5e455c11a9efedfb117b9ad903fb929"
RAW_CALENDAR_ORDER = "TICKER_MAJOR_QQQ_SPXW_SPY_DATE_ASC"
CANONICAL_CALENDAR_ORDER = "DATE_ASC_TICKER_ORDINAL_SPY_QQQ_SPXW"

PINNED_AUTHORITIES: dict[str, tuple[Path, int, str]] = {
    "stage_a_entry_plan": (STAGE_A / "entry_plan.jsonl", 1018910, "0db0065f2dcdd254122a4c4575ecb9c752318cab3a90666ad8215aef922d91bb"),
    "stage_a_weekly_sources": (STAGE_A / "weekly_sources.jsonl", 2367532, "59081a049d11a0403204ca06e62ef4661bb6de3cd042548e081c10f8eaddd1f7"),
    "stage_a_summary": (STAGE_A / "summary.json", 1398, "612ecf1abf18f973656aeda347f21efe563f5c84b9cc06f96e22383ed19b3b39"),
    "stage_a_manifest": (STAGE_A / "manifest.json", 5094, "a0a9d330992d7f5768550c5b60401a701e1c1b02caec4a0967de50b7c7f13161"),
    "stage_a_audit": (STAGE_A_AUDIT / "audit.json", 9071, "1b71077525d146cd7e2166076f987afd315fe46e27c15e51c4f7555be06299cd"),
    "stage_a_audit_manifest": (STAGE_A_AUDIT / "manifest.json", 8945, "49935941c89b67f2aef69272201d68d089d9499d0fca71838867b5457bf85ba7"),
    "stage_a_audit_exit": (STAGE_A_OBSERVER / "exit.json", 1337, "bfdf36bfb7f636f27a391ad0b0ed38be5306e69b0c5be144d0c0599de9d65362"),
    "h1_inventory": (BASE / "h2_dataset_v2_01/inventory.json", 5589855, "099dcf065a62705cbd88f2c1b90b2e4a9b99ff4d994ad703634101920c934b12"),
    "h1_inventory_manifest": (BASE / "h2_dataset_v2_01/inventory_manifest.json", 187, "c417e67f3499522d4ebd4a21bf28d1cba8ce249ef2d38a1352001216714bb899"),
    "h1_manifest": (BASE / "h2_dataset_v2_01/manifest.json", 1541, "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8"),
    "q3_inventory": (BASE / "h2_dataset_v2_extension_2026q3_partial_01/inventory.json", 327384, "f633d0ee192f28650698a4033ee7f6d2dc00dad07aa38239c40e9e2b5092ea5c"),
    "q3_inventory_manifest": (BASE / "h2_dataset_v2_extension_2026q3_partial_01/inventory_manifest.json", 197, "5b39e0796599fa72b5d74d029885a24fd57fada207f12989576737aa46d75b2f"),
    "q3_manifest": (BASE / "h2_dataset_v2_extension_2026q3_partial_01/manifest.json", 6184, "b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b"),
    "bridge_inventory": (BASE / "h2_boundary_bridge_01/inventory.json", 14721, "599ca400fecae12ce4098187a45af3ee0cf8c1b070e060d8c84e422ce92c6161"),
    "bridge_inventory_manifest": (BASE / "h2_boundary_bridge_01/inventory_manifest.json", 330, "0a7a5fab0f932d23fdf9a3140027f99eb85ccd958b79ef55152c53ab5ced70f2"),
    "bridge_manifest": (BASE / "h2_boundary_bridge_01/manifest.json", 4748, "9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86"),
    "unified_calendar": (BASE / "h2_boundary_bridge_01/unified_calendar.json", 232573, "be622bb24aca35448594743dfeb5236e6b2d08a4410109b20302891f8c1fa7d6"),
    "h1_context_inventory": (BASE / "h2_context_1030_01/inventory.json", 1829496, "b347523c8638825c822100cf78b5a03ab4f56fc948bc7aa23674b0b73866df5e"),
    "h1_context_inventory_manifest": (BASE / "h2_context_1030_01/inventory_manifest.json", 197, "a7547c375a4de723b168ce2983b84ba98a35dd70aef24c82ed08c1e3c5358ea8"),
    "h1_context_manifest": (BASE / "h2_context_1030_01/manifest.json", 612610, "77aaf00d60accc071ff1f58ec099cee72bc3a4150f89e4ad41a601821a74a38a"),
    "q3_context_inventory": (BASE / "h2_context_q3_1030_01/inventory.json", 1489911, "25da3398984c633a044eef4f20c5525c6224a1b076a5941d0311fae93eab68cf"),
    "q3_context_inventory_manifest": (BASE / "h2_context_q3_1030_01/inventory_manifest.json", 193, "2b74c18e98366670e77e3d2a4fc19e260cd404e6959fbd7e140f2e88fd5050be"),
    "q3_context_manifest": (BASE / "h2_context_q3_1030_01/manifest.json", 172889, "1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66"),
    "selector_builder_v2": (HERE / "build_weekly_h2_dataset_v2.py", 33142, "ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945"),
    "normalization_pilot": (HERE / "weekly_multiday_source_pilot.py", 31380, "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878"),
    "original_value_path_contract": (ORIGINAL_CONTRACT, 36466, ORIGINAL_CONTRACT_SHA256),
    "prior_producer_exit": (OBSERVER_V1 / "exit.json", 358, "48b635e9fbdeef729de7c1be0b24948e21655ceb6cf5a154c02809e8a8a951d3"),
    "prior_producer_failure": (OBSERVER_V1 / "failure_receipt.json", 305, "6ee1cb2ee3a29b74484c5ed54fe5049eb45da6e299c4fcd9ea8553bc809086fc"),
    "prior_producer_journal": (OBSERVER_V1 / "journal.jsonl", 6473, "a12c7f5d5e1171e220cc1bcefd9f3191caf6e414f5c5df1cdeb5b4bc8b36aa08"),
}

IDENTITY_COLUMNS = ("symbol", "expiration", "trade_date", "strike", "right")
VALUE_COLUMNS = (
    "timestamp", "underlying_timestamp", "interval_used", "underlying_price",
    "bid", "ask", "delta", "implied_vol", "gamma", "theta", "vega", "rho",
)
REQUIRED_VALUE_COLUMNS = (
    "underlying_timestamp", "underlying_price", "bid", "ask", "delta",
    "implied_vol", "theta", "vega", "rho",
)
FLOAT_COLUMNS = (
    "underlying_price", "bid", "ask", "delta", "implied_vol", "theta",
    "vega", "rho",
)


class ValuePathError(RuntimeError):
    """Closed failure for admission or causal path construction."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValuePathError(message)


def canonical(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def canonical_key(path: Path | str) -> str:
    return os.path.normcase(os.path.normpath(str(canonical(path))))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pin(path: Path) -> dict[str, Any]:
    path = canonical(path)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def secure_pin(path: Path, physical_registry: MutableMapping[tuple[int, int], str] | None = None) -> dict[str, Any]:
    lexical = Path(path)
    require(lexical.is_absolute() and ".." not in lexical.parts, f"secure pin requires absolute lexical path: {path}")
    path = canonical(path)
    current = path
    while True:
        info = current.lstat()
        require(not stat.S_ISLNK(info.st_mode), f"linked metadata path forbidden: {current}")
        require(not bool(getattr(info, "st_file_attributes", 0) & REPARSE), f"reparse metadata path forbidden: {current}")
        parent = current.parent
        if parent == current:
            break
        current = parent
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and getattr(info, "st_nlink", 1) == 1, f"metadata must be an unaliased regular file: {path}")
    physical = (int(info.st_dev), int(info.st_ino))
    if physical_registry is not None:
        prior = physical_registry.get(physical)
        require(prior is None or canonical_key(prior) == canonical_key(path), f"metadata physical identity shared: {path} and {prior}")
        physical_registry[physical] = str(path)
    return pin(path)


def compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [json.loads(line) for line in handle if line]


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    count = 0
    with path.open("xb", buffering=0) as handle:
        for row in rows:
            handle.write((compact_json(dict(row)) + "\n").encode("utf-8"))
            count += 1
        os.fsync(handle.fileno())
    return count


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    raw = (compact_json(value) + "\n").encode("utf-8")
    with path.open("xb", buffering=0) as handle:
        handle.write(raw)
        os.fsync(handle.fileno())


def physical_stat(path: Path, *, expected_missing: bool = False) -> dict[str, Any]:
    path = canonical(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        require(expected_missing, f"unexpected missing path: {path}")
        return {"exists": False, "bytes": None, "mtime_ns": None, "physical_id": None}
    require(not expected_missing, f"expected missing source appeared: {path}")
    require(stat.S_ISREG(info.st_mode), f"not a regular file: {path}")
    require(not stat.S_ISLNK(info.st_mode), f"symlink forbidden: {path}")
    require(not bool(getattr(info, "st_file_attributes", 0) & REPARSE), f"reparse forbidden: {path}")
    require(getattr(info, "st_nlink", 1) == 1, f"hardlink ambiguity forbidden: {path}")
    return {
        "exists": True,
        "bytes": int(info.st_size),
        "mtime_ns": int(info.st_mtime_ns),
        "physical_id": [int(info.st_dev), int(info.st_ino)],
    }


def guard_path(
    path: Path,
    root: Path,
    *,
    expected_missing: bool = False,
    lstat_adapter: Callable[[Path], os.stat_result] | None = None,
) -> dict[str, Any]:
    lexical = Path(path)
    require(lexical.is_absolute() and ".." not in lexical.parts, f"noncanonical lexical path: {path}")
    path, root = canonical(path), canonical(root)
    require(os.path.commonpath((str(path), str(root))) == str(root), f"path outside root: {path}")
    inspect = lstat_adapter or (lambda value: value.lstat())
    current = path if path.exists() else path.parent
    while True:
        info = inspect(current)
        require(not stat.S_ISLNK(info.st_mode), f"linked ancestor forbidden: {current}")
        require(not bool(getattr(info, "st_file_attributes", 0) & REPARSE), f"reparse ancestor forbidden: {current}")
        parent = current.parent
        if parent == current:
            break
        current = parent
    return physical_stat(path, expected_missing=expected_missing)


def validate_nominal_source_path(raw: Any) -> Path:
    require(isinstance(raw, str), "nominal source path must be a string")
    lexical = PureWindowsPath(raw)
    require(lexical.is_absolute(), f"nominal source path is not absolute: {raw!r}")
    require(all(part not in (".", "..") for part in re.split(r"[\\/]", raw)), f"dot traversal forbidden: {raw!r}")
    path = canonical(raw)
    match = re.fullmatch(r"(SPY|QQQ|SPXW)_(\d{8})_(\d{8})_greeks\.parquet", lexical.name)
    require(match is not None, f"invalid nominal source filename: {raw!r}")
    expected = canonical(SOURCE_ROOT / match.group(1) / "greeks" / match.group(3)[:4] / match.group(3)[4:6] / lexical.name)
    require(canonical_key(path) == canonical_key(expected), f"noncanonical nominal source path: {raw!r}")
    return path


def guard_directory(path: Path) -> None:
    path = canonical(path)
    current = path
    while True:
        info = current.lstat()
        require(stat.S_ISDIR(info.st_mode), f"directory required: {current}")
        require(not stat.S_ISLNK(info.st_mode) and not bool(getattr(info, "st_file_attributes", 0) & REPARSE), f"linked/reparse directory forbidden: {current}")
        parent = current.parent
        if parent == current:
            break
        current = parent


_RESOURCE_HELPER_MODULE: Any | None = None


def _official_resource_helper() -> Any:
    global _RESOURCE_HELPER_MODULE
    if _RESOURCE_HELPER_MODULE is None:
        observed = secure_pin(RESOURCE_HELPER)
        require(observed["sha256"] == RESOURCE_HELPER_SHA256, "official resource helper pin mismatch")
        spec = importlib.util.spec_from_file_location("weekly_value_path_resource_helper", RESOURCE_HELPER)
        require(spec is not None and spec.loader is not None, "resource helper import spec")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        require(callable(getattr(module, "observation", None)) and callable(getattr(module, "gate", None)), "resource helper interface")
        _RESOURCE_HELPER_MODULE = module
    return _RESOURCE_HELPER_MODULE


def resource_gate(disk_root: Path = Path("D:/")) -> dict[str, int]:
    helper = _official_resource_helper()
    memory = dict(helper.observation())
    helper.gate(memory)
    disk = int(shutil.disk_usage(disk_root).free)
    result = {**memory, "disk_free_bytes": disk}
    require(all(value >= MIN_FREE for value in result.values()), "2GB RAM/commit/disk gate unmet")
    return result


class Journal:
    def __init__(self, path: Path, gate: Callable[[], Mapping[str, int]] = resource_gate):
        self.path = canonical(path)
        self.gate = gate

    def append(self, row: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab", buffering=0) as handle:
            handle.write((compact_json(dict(row)) + "\n").encode("utf-8"))
            os.fsync(handle.fileno())

    @contextlib.contextmanager
    def unit_context(self, kind: str, identity: str, paths: list[str]) -> Iterator[MutableMapping[str, Any]]:
        require(isinstance(kind, str) and isinstance(identity, str), "journal unit identity")
        require(isinstance(paths, list) and all(isinstance(item, str) for item in paths), "journal unit paths")
        gate = dict(self.gate())
        details: MutableMapping[str, Any] = {}
        self.append({"at_utc": datetime.now(timezone.utc).isoformat(), "event": "STARTED", "kind": kind, "identity": identity, "paths": paths, "gate": gate})
        try:
            yield details
        except BaseException as error:
            self.append({"at_utc": datetime.now(timezone.utc).isoformat(), "event": "ERROR", "kind": kind, "identity": identity, "paths": paths, "gate": gate, "details": details, "error_type": type(error).__name__, "error": str(error)})
            raise
        else:
            self.append({"at_utc": datetime.now(timezone.utc).isoformat(), "event": "COMPLETED", "kind": kind, "identity": identity, "paths": paths, "gate": gate, "details": details})


def parse_day_scalar(value: Any) -> str:
    if isinstance(value, datetime) or isinstance(value, bool) or isinstance(value, numbers.Number):
        raise ValuePathError(f"invalid day scalar: {value!r}")
    if isinstance(value, date):
        parsed = value
    elif isinstance(value, str) and re.fullmatch(r"(?:\d{8}|\d{4}-\d{2}-\d{2})", value):
        try:
            parsed = datetime.strptime(value, "%Y%m%d" if len(value) == 8 else "%Y-%m-%d").date()
        except ValueError as error:
            raise ValuePathError(f"invalid calendar day: {value!r}") from error
    else:
        raise ValuePathError(f"invalid day scalar: {value!r}")
    return parsed.strftime("%Y%m%d")


def normalize_right(value: Any) -> str:
    text = str(value).strip().upper()
    mapping = {"C": "CALL", "CALL": "CALL", "P": "PUT", "PUT": "PUT"}
    require(text in mapping, f"invalid right: {value!r}")
    return mapping[text]


def strike_decimal(value: Any) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValuePathError(f"invalid strike: {value!r}") from error
    require(number.is_finite(), f"invalid strike: {value!r}")
    return format(number.normalize(), "f")


def strict_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (numbers.Real, Decimal)):
        return None
    return float(value)


def valid_quote(bid_value: Any, ask_value: Any) -> bool:
    bid, ask = strict_float(bid_value), strict_float(ask_value)
    return bid is not None and ask is not None and math.isfinite(bid) and math.isfinite(ask) and bid >= 0 and ask > 0 and bid <= ask


def _roundtrip_naive(value: datetime, fold: int) -> datetime:
    aware = value.replace(tzinfo=NY, fold=fold)
    return aware.astimezone(timezone.utc).astimezone(NY).replace(tzinfo=None)


def parse_clock(value: Any, trade_date: str | None, *, fraction_nonzero: bool | None = None) -> tuple[datetime, bool]:
    if value is None or isinstance(value, (bool, numbers.Number, Decimal)) or isinstance(value, date) and not isinstance(value, datetime):
        raise ValuePathError(f"invalid snapshot clock: {value!r}")
    if isinstance(value, datetime):
        parsed = value
        intrinsic_fraction = bool(value.microsecond)
    elif isinstance(value, str):
        text = value
        require(text == text.strip() and ISO_CLOCK.fullmatch(text) is not None, f"incomplete ISO clock: {value!r}")
        match = re.search(r"\.(\d+)(?:Z|[+-]\d\d:\d\d)?$", text)
        require(match is None or len(match.group(1)) <= 9, "ISO clock precision exceeds nanoseconds")
        intrinsic_fraction = bool(match and any(char != "0" for char in match.group(1)))
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValuePathError(f"invalid ISO clock: {value!r}") from error
    else:
        raise ValuePathError(f"invalid snapshot clock type: {type(value).__name__}")
    if parsed.tzinfo is None:
        valid_folds = [fold for fold in (0, 1) if _roundtrip_naive(parsed, fold) == parsed]
        require(valid_folds, "nonexistent NY wall clock")
        offsets = {parsed.replace(tzinfo=NY, fold=fold).utcoffset() for fold in valid_folds}
        require(len(offsets) == 1, "ambiguous NY wall clock")
        local = parsed.replace(tzinfo=NY, fold=valid_folds[0])
    else:
        local = parsed.astimezone(NY)
    if trade_date is not None:
        require(local.strftime("%Y%m%d") == trade_date, "clock local date differs from trade_date")
    subminute = local.second != 0 or (intrinsic_fraction if fraction_nonzero is None else fraction_nonzero)
    return local, subminute


def iso_epoch_ns(value: str) -> int:
    require(ISO_CLOCK.fullmatch(value) is not None, f"invalid ISO clock: {value!r}")
    match = re.fullmatch(
        r"(?P<base>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})(?:\.(?P<fraction>\d+))?(?P<zone>Z|[+-]\d{2}:\d{2})?",
        value,
    )
    require(match is not None, f"invalid ISO clock: {value!r}")
    fraction = match.group("fraction") or ""
    require(len(fraction) <= 9, "ISO clock precision exceeds nanoseconds")
    nanoseconds = int(fraction.ljust(9, "0") or "0")
    zone = match.group("zone") or ""
    parsed = datetime.fromisoformat(match.group("base") + zone.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        local, _ = parse_clock(parsed, None, fraction_nonzero=bool(nanoseconds))
        seconds = int(local.astimezone(timezone.utc).timestamp())
    else:
        seconds = int(parsed.astimezone(timezone.utc).timestamp())
    return seconds * 1_000_000_000 + nanoseconds


def minute_index(local: datetime) -> int:
    return (local.hour * 60 + local.minute) - (9 * 60 + 30)


def interval_text(value: Any, arrow_type: pa.DataType) -> str | None:
    if value is None:
        return None
    if pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type):
        require(isinstance(value, str), "interval utf8 scalar mismatch")
        return value
    require(
        pa.types.is_integer(arrow_type) or pa.types.is_floating(arrow_type) or pa.types.is_decimal(arrow_type),
        f"unsupported interval_used type: {arrow_type}",
    )
    return str(value)


def arrow_fraction_nonzero(scalar: pa.Scalar, arrow_type: pa.DataType) -> bool | None:
    if not pa.types.is_timestamp(arrow_type):
        return None
    divisor = {"s": 1, "ms": 1_000, "us": 1_000_000, "ns": 1_000_000_000}[arrow_type.unit]
    return int(scalar.value) % divisor != 0


def timestamp_raw(scalar: pa.Scalar, arrow_type: pa.DataType) -> str | None:
    if not scalar.is_valid:
        return None
    value = scalar.as_py()
    if pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type):
        return value
    require(pa.types.is_timestamp(arrow_type), "underlying timestamp must be utf8 or timestamp")
    digits = {"s": 0, "ms": 3, "us": 6, "ns": 9}[arrow_type.unit]
    integer = int(scalar.value)
    scale = {"s": 1, "ms": 1_000, "us": 1_000_000, "ns": 1_000_000_000}[arrow_type.unit]
    seconds, remainder = divmod(integer, scale)
    if arrow_type.tz:
        dt = datetime.fromtimestamp(seconds, timezone.utc).astimezone(ZoneInfo(arrow_type.tz))
        suffix = dt.strftime("%z")
        suffix = suffix[:3] + ":" + suffix[3:]
    else:
        dt = datetime(1970, 1, 1) + timedelta(seconds=seconds)
        suffix = ""
    fraction = "" if digits == 0 else f".{remainder:0{digits}d}"
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + fraction + suffix


def schema_descriptor(schema: pa.Schema, projection: Sequence[str]) -> list[dict[str, str]]:
    return [{"name": name, "type": str(schema.field(name).type)} for name in projection]


def canonical_arrow_schema(schema: pa.Schema) -> dict[str, Any]:
    def metadata(value: Mapping[bytes, bytes] | None) -> list[dict[str, str]]:
        return [
            {"key_b64": base64.b64encode(key).decode("ascii"), "value_b64": base64.b64encode(item).decode("ascii")}
            for key, item in sorted((value or {}).items())
        ]
    return {
        "fields": [
            {"name": field.name, "type": str(field.type), "nullable": field.nullable, "metadata": metadata(field.metadata)}
            for field in schema
        ],
        "metadata": metadata(schema.metadata),
    }


def decision_id(plan_id: str, ticker: str, expiration: str, strike: str, right: str) -> str:
    return hashlib.sha256(compact_json([plan_id, ticker, expiration, strike, right]).encode("utf-8")).hexdigest()


def observation_id(path: str, ticker: str, expiration: str, strike: str, right: str, minute_i: int) -> str:
    return hashlib.sha256(compact_json([str(canonical(path)), ticker, expiration, strike, right, minute_i]).encode("utf-8")).hexdigest()


def choose_side(rows: Iterable[Mapping[str, Any]], right: str) -> dict[str, Any] | None:
    choices: list[tuple[tuple[float, float, float], dict[str, Any]]] = []
    for raw in rows:
        if normalize_right(raw["right"]) != right or not valid_quote(raw.get("bid"), raw.get("ask")):
            continue
        bid, ask = float(raw["bid"]), float(raw["ask"])
        spot, strike, delta = (strict_float(raw.get(name)) for name in ("underlying_price", "strike", "delta"))
        if spot is None or strike is None or delta is None or not all(math.isfinite(value) for value in (spot, strike, delta)):
            continue
        if spot <= 0 or ask > 49.95 or abs(delta) > 1 or right == "CALL" and delta <= 0 or right == "PUT" and delta >= 0:
            continue
        relative = (ask - bid) / ask
        row = dict(raw)
        row.update(_bid=bid, _ask=ask, _spot=spot, _strike=strike, _delta=delta, _relative=relative)
        choices.append(((abs(abs(delta) - 0.50), relative, strike), row))
    return min(choices, key=lambda item: item[0])[1] if choices else None


def missing_ranges(observed: set[int], close_i: int) -> list[dict[str, int]]:
    missing = [index for index in range(close_i + 1) if index not in observed]
    result: list[dict[str, int]] = []
    for value in missing:
        if not result or value != result[-1]["end_i"] + 1:
            result.append({"start_i": value, "end_i": value})
        else:
            result[-1]["end_i"] = value
    return result


def _source_projection(schema: pa.Schema) -> tuple[list[str], str, str, bool]:
    names = set(schema.names)
    require(set(IDENTITY_COLUMNS).issubset(names), "identity columns missing")
    require(set(REQUIRED_VALUE_COLUMNS).issubset(names), "required value columns missing")
    clock_column = "timestamp" if "timestamp" in names else "underlying_timestamp"
    clock_basis = "NATIVE_STORED_TIMESTAMP" if clock_column == "timestamp" else "UNDERLYING_TIMESTAMP_PROXY"
    for name in FLOAT_COLUMNS + (("gamma",) if "gamma" in names else ()):
        require(pa.types.is_float64(schema.field(name).type), f"{name} must be float64")
    if "interval_used" in names:
        interval_type = schema.field("interval_used").type
        require(
            pa.types.is_integer(interval_type) or pa.types.is_floating(interval_type)
            or pa.types.is_decimal(interval_type) or pa.types.is_string(interval_type)
            or pa.types.is_large_string(interval_type),
            f"unsupported interval_used type: {interval_type}",
        )
    projection = [name for name in (*IDENTITY_COLUMNS, *VALUE_COLUMNS) if name in names]
    return projection, clock_column, clock_basis, "gamma" in names


def _historical_sources(documents: Mapping[str, Any]) -> dict[str, list[tuple[str, Mapping[str, Any]]]]:
    result: dict[str, list[tuple[str, Mapping[str, Any]]]] = defaultdict(list)
    for authority, key in (("H1", "h1_inventory"), ("Q3", "q3_inventory"), ("BRIDGE", "bridge_inventory")):
        for row in documents[key]["sources"]:
            result[canonical_key(row["path"])].append((authority, row))
    return result


def _source_identity(row: Mapping[str, Any]) -> tuple[str, str, str]:
    path = Path(row["path"])
    match = re.fullmatch(r"(SPY|QQQ|SPXW)_(\d{8})_(\d{8})_greeks\.parquet", path.name)
    require(match is not None, f"invalid source filename: {path}")
    expected = canonical(SOURCE_ROOT / match.group(1) / "greeks" / match.group(3)[:4] / match.group(3)[4:6] / path.name)
    require(canonical_key(path) == canonical_key(expected), f"noncanonical source layout: {path}")
    return match.group(1), match.group(2), match.group(3)


def admit_option_sources(
    stage_sources: Sequence[Mapping[str, Any]],
    documents: Mapping[str, Any],
    journal: Journal,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    historical = _historical_sources(documents)
    rows: list[dict[str, Any]] = []
    admitted: dict[str, dict[str, Any]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    physical_seen: dict[tuple[int, int], str] = {}
    for stage in stage_sources:
        path = validate_nominal_source_path(stage["path"])
        ticker, expiration, trade_date = _source_identity(stage)
        bindings = historical.get(canonical_key(path), [])
        exists = bool(stage["observation"]["exists"])
        kind = "EXPECTED_MISSING" if not exists else "HISTORICAL" if bindings else "FIRST_AUTHORITY"
        with journal.unit_context("ADMIT_OPTION_FOOTERS", str(path), [str(path)]) as details:
            before = guard_path(path, SOURCE_ROOT, expected_missing=not exists)
            require(before == stage["observation"], f"Stage-A stat drift: {path}")
            base = {
                "path": str(path), "ticker": ticker, "trade_date": trade_date,
                "expiration": expiration, "stage_a_exists": exists,
                "admission_status": "PRESENT" if exists else "MISSING",
                "binding_kind": kind, "bytes": None, "sha256": None, "rows": None,
                "row_groups": None, "projected_schema": None, "full_schema": None,
                "clock_column": None, "clock_basis": None,
                "gamma_column_present": None,
                "expected_binding_authorities": sorted(authority for authority, _ in bindings),
                "before_stat": before, "after_stat": before,
                "ignored_reason": "EXPECTED_MISSING_STAGE_A" if not exists else None,
            }
            if not exists:
                require(not bindings or all(item[1]["status"] == "MISSING_SOURCE" for item in bindings), "missing binding disagreement")
                rows.append(base)
                details.update(status="EXPECTED_MISSING")
                continue
            require(before["bytes"] == stage["observation"]["bytes"], "Stage-A bytes drift")
            physical = tuple(before["physical_id"])
            require(physical not in physical_seen, f"physical identity shared: {path}")
            physical_seen[physical] = str(path)
            digest = sha256_file(path)
            parquet = pq.ParquetFile(path)
            projection, clock_column, clock_basis, gamma = _source_projection(parquet.schema_arrow)
            projected = schema_descriptor(parquet.schema_arrow, projection)
            if bindings:
                for _authority, binding in bindings:
                    require(binding["status"] == "INVENTORIED", f"present historical binding status: {path}")
                    require(binding["bytes"] == before["bytes"] and binding["sha256"] == digest, f"historical bytes/hash drift: {path}")
                    require(binding["rows"] == parquet.metadata.num_rows and binding["projected_schema"] == projected, f"historical footer drift: {path}")
                full = None
            else:
                full = canonical_arrow_schema(parquet.schema_arrow)
            after = guard_path(path, SOURCE_ROOT)
            require(after == before and sha256_file(path) == digest, f"source changed during admission: {path}")
            base.update(
                bytes=before["bytes"], sha256=digest, rows=parquet.metadata.num_rows,
                row_groups=parquet.metadata.num_row_groups,
                projected_schema=projected if bindings else None,
                full_schema=full, clock_column=clock_column, clock_basis=clock_basis,
                gamma_column_present=gamma, after_stat=after,
            )
            rows.append(base)
            admitted[str(path)] = {"path": str(path), "bytes": before["bytes"], "sha256": digest}
            metadata[str(path)] = base
            details.update(rows=parquet.metadata.num_rows, sha256=digest, clock_basis=clock_basis)
    rows.sort(key=lambda row: canonical_key(row["path"]))
    validate_admission_population(rows, admitted)
    return rows, admitted, metadata


def validate_admission_population(
    rows: Sequence[Mapping[str, Any]],
    admitted: Mapping[str, Any],
    *,
    total: int = 2784,
    present: int = 2768,
    kinds: Mapping[str, int] | None = None,
) -> None:
    expected_kinds = kinds or {"HISTORICAL": 2765, "FIRST_AUTHORITY": 3, "EXPECTED_MISSING": 16}
    require(len(rows) == total and len(admitted) == present, "option source admission population")
    require(Counter(row["binding_kind"] for row in rows) == dict(expected_kinds), "binding-kind population")


def _batch_identity_clock_codes(
    batch: pa.RecordBatch,
    source: Mapping[str, Any],
    strike_codes: MutableMapping[str, int],
) -> dict[str, Any]:
    clock_column = source["clock_column"]
    clock_array = batch.column(batch.schema.get_field_index(clock_column))
    unique_clocks = pc.unique(clock_array)
    minute_lookup: list[int] = []
    subminute_lookup: list[bool] = []
    local_lookup: list[datetime] = []
    for scalar in unique_clocks:
        require(scalar.is_valid, "null primary clock")
        local, subminute = parse_clock(scalar.as_py(), source["trade_date"], fraction_nonzero=arrow_fraction_nonzero(scalar, clock_array.type))
        local_lookup.append(local)
        minute_lookup.append(minute_index(local))
        subminute_lookup.append(subminute)
    clock_index = pc.index_in(clock_array, value_set=unique_clocks).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
    require(bool(np.all(clock_index >= 0)), "clock dictionary mapping")
    minute = np.asarray(minute_lookup, dtype=np.int16)[clock_index]
    subminute = np.asarray(subminute_lookup, dtype=np.bool_)[clock_index]

    for name, expected, normalizer in (
        ("symbol", source["ticker"], lambda value: str(value).strip().upper()),
        ("expiration", source["expiration"], parse_day_scalar),
        ("trade_date", source["trade_date"], parse_day_scalar),
    ):
        array = batch.column(batch.schema.get_field_index(name))
        values = pc.unique(array)
        require(all(scalar.is_valid and normalizer(scalar.as_py()) == expected for scalar in values), f"batch {name} identity mismatch")

    right_array = batch.column(batch.schema.get_field_index("right"))
    unique_rights = pc.unique(right_array)
    right_lookup = np.asarray([RIGHT_ORDINAL[normalize_right(scalar.as_py())] if scalar.is_valid else -1 for scalar in unique_rights], dtype=np.int8)
    require(bool(np.all(right_lookup >= 0)), "null/invalid right")
    right_index = pc.index_in(right_array, value_set=unique_rights).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
    require(bool(np.all(right_index >= 0)), "right dictionary mapping")
    right_codes = right_lookup[right_index]

    strike_array = batch.column(batch.schema.get_field_index("strike"))
    unique_strikes = pc.unique(strike_array)
    strike_lookup: list[int] = []
    strike_text_lookup: list[str] = []
    for scalar in unique_strikes:
        require(scalar.is_valid, "null strike")
        text = strike_decimal(scalar.as_py())
        strike_text_lookup.append(text)
        if text not in strike_codes:
            strike_codes[text] = len(strike_codes)
        strike_lookup.append(strike_codes[text])
    strike_index = pc.index_in(strike_array, value_set=unique_strikes).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
    require(bool(np.all(strike_index >= 0)), "strike dictionary mapping")
    strike_code_rows = np.asarray(strike_lookup, dtype=np.int64)[strike_index]
    strike_text_rows = np.asarray(strike_text_lookup, dtype=object)[strike_index]
    return {
        "clock_array": clock_array, "clock_index": clock_index,
        "local_lookup": local_lookup, "minute": minute, "subminute": subminute,
        "right_codes": right_codes, "strike_codes": strike_code_rows,
        "strike_text": strike_text_rows,
    }


def _require_no_exact_duplicates(parts: Sequence[np.ndarray], path: Path) -> None:
    exact = np.concatenate(parts, axis=0) if parts else np.empty((0, 3), dtype=np.int64)
    require(np.unique(exact, axis=0).shape[0] == exact.shape[0], f"duplicate exact-minute source/contract/minute: {path}")


def _selector_rows_1030(path: Path, source: Mapping[str, Any], plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    parquet = pq.ParquetFile(path)
    projection = [item["name"] for item in source["projected_schema"]] if source["projected_schema"] else [name for name in (*IDENTITY_COLUMNS, *VALUE_COLUMNS) if name in parquet.schema_arrow.names]
    selected_rows: list[dict[str, Any]] = []
    exact_parts: list[np.ndarray] = []
    strike_codes: dict[str, int] = {}
    for batch in parquet.iter_batches(batch_size=65536, columns=projection, use_threads=False):
        codes = _batch_identity_clock_codes(batch, source, strike_codes)
        clock_array = codes["clock_array"]
        underlying_array = batch.column(batch.schema.get_field_index("underlying_timestamp"))
        require(source["ticker"] == plan["ticker"] and source["trade_date"] == plan["date"] and source["expiration"] == plan["expiration"], "selector source/plan identity")
        exact_mask = ~codes["subminute"]
        exact_parts.append(np.column_stack((codes["strike_codes"][exact_mask], codes["right_codes"][exact_mask], codes["minute"][exact_mask])).astype(np.int64, copy=False))
        selected_indices = np.flatnonzero(exact_mask & (codes["minute"] == 60))
        for index in selected_indices.tolist():
            clock_scalar = clock_array[index]
            right = RIGHTS[int(codes["right_codes"][index])]
            strike = str(codes["strike_text"][index])
            row = {name: batch.column(batch.schema.get_field_index(name))[index].as_py() for name in projection}
            row.update(
                right=right, strike_decimal=strike,
                _primary_clock_scalar=clock_scalar, _primary_clock_type=clock_array.type,
                _underlying_timestamp_scalar=underlying_array[index],
                _underlying_timestamp_type=underlying_array.type,
            )
            selected_rows.append(row)
    _require_no_exact_duplicates(exact_parts, path)
    return selected_rows


def select_decisions(
    plans: Sequence[Mapping[str, Any]],
    source_metadata: Mapping[str, Mapping[str, Any]],
    journal: Journal,
    expected_count: int = 3240,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    decisions: list[dict[str, Any]] = []
    misses: Counter[str] = Counter()
    for plan in plans:
        if plan["status"] != "PLANNED":
            continue
        path = str(canonical(plan["entry_path"]))
        source = source_metadata.get(path)
        require(source is not None, f"entry source unavailable: {path}")
        with journal.unit_context("SELECT_1030", plan["plan_id"], [path]) as details:
            before_stat = guard_path(Path(path), SOURCE_ROOT)
            before_sha = sha256_file(Path(path))
            require(before_stat == source["after_stat"] and before_sha == source["sha256"], f"selector source drift before read: {path}")
            rows_1030 = _selector_rows_1030(Path(path), source, plan)
            for right in RIGHTS:
                chosen = choose_side(rows_1030, right)
                if chosen is None:
                    misses[f"NO_VALID_{right}"] += 1
                    continue
                strike = chosen["strike_decimal"]
                decisions.append({
                    "decision_id": decision_id(plan["plan_id"], plan["ticker"], plan["expiration"], strike, right),
                    "plan_id": plan["plan_id"], "source_authority": plan["source_authority"],
                    "ticker": plan["ticker"], "entry_date": plan["date"],
                    "expiration": plan["expiration"], "right": right,
                    "strike_decimal": strike, "decision_clock": "10:30",
                    "decision_minute_i": 60, "decision_bid": chosen["_bid"],
                    "decision_ask": chosen["_ask"], "decision_delta": chosen["_delta"],
                    "decision_underlying_price": chosen["_spot"],
                    "relative_spread": chosen["_relative"],
                    "selector_distance": abs(abs(chosen["_delta"]) - 0.50),
                    "source_path": path, "source_sha256": source["sha256"],
                    "clock_basis": source["clock_basis"], "receipt_time_status": "UNKNOWN",
                    "interval_used": interval_text(chosen.get("interval_used"), pq.ParquetFile(path).schema_arrow.field("interval_used").type) if "interval_used" in pq.ParquetFile(path).schema_arrow.names else None,
                    "gamma_column_present": source["gamma_column_present"],
                })
            after_stat = guard_path(Path(path), SOURCE_ROOT)
            after_sha = sha256_file(Path(path))
            require(after_stat == before_stat and after_sha == before_sha, f"selector source drift after read: {path}")
            details.update(source_reads=1, rows_1030=len(rows_1030), decisions=len(decisions), before_stat=before_stat, after_stat=after_stat, sha256_before=before_sha, sha256_after=after_sha)
    decisions.sort(key=lambda row: (row["entry_date"], TICKER_ORDINAL[row["ticker"]], RIGHT_ORDINAL[row["right"]]))
    if len(decisions) != expected_count or misses:
        raise ValuePathError(f"real comparison decision gate failed: decisions={len(decisions)} misses={dict(misses)}")
    if expected_count == 3240:
        require(Counter(row["source_authority"] for row in decisions) == {"H1": 3054, "Q3": 180, "BRIDGE": 6}, "decision authority partition")
        require(Counter(row["right"] for row in decisions) == {"CALL": 1620, "PUT": 1620}, "decision side partition")
        require(len({row["plan_id"] for row in decisions}) == 1620, "decision plan population")
    return decisions, misses


def _nullable_float(value: Any) -> float | None:
    if value is None:
        return None
    require(not isinstance(value, bool) and isinstance(value, (numbers.Real, Decimal)), f"non-numeric float scalar: {value!r}")
    return float(value)


def _underlying_age(row: Mapping[str, Any], primary: datetime, source: Mapping[str, Any], raw: str | None) -> tuple[float | None, str]:
    if source["clock_basis"] == "UNDERLYING_TIMESTAMP_PROXY":
        return None, "PROXY_UNKNOWN"
    if raw is None:
        return None, "MISSING_OR_MALFORMED"
    try:
        primary_scalar = row.get("_primary_clock_scalar")
        underlying_scalar = row.get("_underlying_timestamp_scalar")
        primary_type = row.get("_primary_clock_type")
        underlying_type = row.get("_underlying_timestamp_type")
        if (
            isinstance(primary_scalar, pa.Scalar) and isinstance(underlying_scalar, pa.Scalar)
            and primary_scalar.is_valid and underlying_scalar.is_valid
            and pa.types.is_timestamp(primary_type) and pa.types.is_timestamp(underlying_type)
        ):
            multiplier = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1_000, "ns": 1}
            def normalized_ns(scalar: pa.Scalar, arrow_type: pa.DataType) -> int:
                raw_value = int(scalar.value)
                unit_multiplier = multiplier[arrow_type.unit]
                if arrow_type.tz:
                    return raw_value * unit_multiplier
                units_per_second = 1_000_000_000 // unit_multiplier
                seconds, remainder = divmod(raw_value, units_per_second)
                naive = datetime(1970, 1, 1) + timedelta(seconds=seconds)
                local, _ = parse_clock(naive, None, fraction_nonzero=bool(remainder))
                utc_seconds = int(local.astimezone(timezone.utc).timestamp())
                return utc_seconds * 1_000_000_000 + remainder * unit_multiplier
            primary_ns = normalized_ns(primary_scalar, primary_type)
            underlying_ns = normalized_ns(underlying_scalar, underlying_type)
            return (primary_ns - underlying_ns) / 1_000_000.0, "NATIVE_DERIVED"
        primary_value = row.get(source["clock_column"])
        underlying_value = row.get("underlying_timestamp")
        if isinstance(primary_value, str) and isinstance(underlying_value, str):
            return (iso_epoch_ns(primary_value) - iso_epoch_ns(underlying_value)) / 1_000_000.0, "NATIVE_DERIVED"
        value = row.get("underlying_timestamp")
        parsed, _ = parse_clock(value, None)
    except ValuePathError:
        return None, "MISSING_OR_MALFORMED"
    return (primary - parsed).total_seconds() * 1000.0, "NATIVE_DERIVED"


def stream_option_paths(
    plans: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
    source_metadata: Mapping[str, Mapping[str, Any]],
    journal: Journal,
    observation_path: Path,
    *,
    expected_sources: int = 2784,
    expected_present: int = 2768,
) -> tuple[int, list[dict[str, Any]], dict[str, int]]:
    decisions_by_plan = defaultdict(list)
    for decision in decisions:
        decisions_by_plan[decision["plan_id"]].append(decision)
    requests: dict[str, set[tuple[str, str]]] = defaultdict(set)
    coverage_specs: list[tuple[Mapping[str, Any], str, str, str, int]] = []
    for plan in plans:
        if plan["status"] != "PLANNED":
            continue
        for decision in decisions_by_plan[plan["plan_id"]]:
            for role, day in zip(ROLES, (plan["session_dates"]["D"], plan["session_dates"]["D1"], plan["session_dates"]["D2"]), strict=True):
                path = str(canonical(SOURCE_ROOT / plan["ticker"] / "greeks" / day[:4] / day[4:6] / f"{plan['ticker']}_{plan['expiration']}_{day}_greeks.parquet"))
                requests[path].add((decision["strike_decimal"], decision["right"]))
                coverage_specs.append((decision, role, day, path, int(plan["close_i"] if role == "D" else next(item["close_i"] for item in plans if item["ticker"] == plan["ticker"] and item["date"] == day))))
    require(len(requests) == expected_sources and set(source_metadata).issubset(requests), "trajectory source universe")
    require(len(source_metadata) == expected_present, "trajectory present source population")
    coverage_by_path: dict[str, list[tuple[Mapping[str, Any], str, str, str, int]]] = defaultdict(list)
    for spec in coverage_specs:
        coverage_by_path[spec[3]].append(spec)
    decision_entry = {row["decision_id"]: row["entry_date"] for row in decisions}
    ignored: dict[tuple[str, str, str], dict[str, int]] = defaultdict(lambda: {"subminute": 0, "out": 0})
    coverage: list[dict[str, Any]] = []
    observation_count = 0

    def append_coverage(spec: tuple[Mapping[str, Any], str, str, str, int], observed: set[int]) -> None:
        decision, role, day, path, close_i = spec
        source = source_metadata.get(path)
        ignored_value = ignored[(path, decision["strike_decimal"], decision["right"])]
        ranges = missing_ranges(observed, close_i)
        coverage.append({
            "decision_id": decision["decision_id"], "plan_id": decision["plan_id"], "role": role,
            "ticker": decision["ticker"], "segment_date": day, "expiration": decision["expiration"],
            "right": decision["right"], "strike_decimal": decision["strike_decimal"], "source_path": path,
            "source_status": "PRESENT" if source else "MISSING", "source_sha256": source["sha256"] if source else None,
            "close_i": close_i, "expected_minute_count": close_i + 1,
            "observed_exact_minute_count": len(observed), "missing_minute_count": close_i + 1 - len(observed),
            "missing_ranges": ranges, "first_observed_i": min(observed) if observed else None,
            "last_observed_i": max(observed) if observed else None,
            "ignored_subminute_rows": ignored_value["subminute"], "ignored_out_of_session_rows": ignored_value["out"],
            "clock_basis": source["clock_basis"] if source else None,
            "gamma_column_present": source["gamma_column_present"] if source else None,
        })

    schema = parquet_metadata(OBSERVATION_SCHEMA)
    writer = pq.ParquetWriter(
        observation_path, schema, version="2.6", data_page_version="1.0",
        compression="zstd", compression_level=3, use_dictionary=True,
        write_statistics=True,
    )
    try:
        ordered_paths = sorted(
            source_metadata,
            key=lambda path: (
                source_metadata[path]["trade_date"],
                TICKER_ORDINAL[source_metadata[path]["ticker"]],
                source_metadata[path]["expiration"], canonical_key(path),
            ),
        )
        for path in ordered_paths:
            source = source_metadata[path]
            with journal.unit_context("STREAM_OPTION_PATHS", path, [path]) as details:
                before_stat = guard_path(Path(path), SOURCE_ROOT)
                before_sha = sha256_file(Path(path))
                require(before_stat == source["after_stat"] and before_sha == source["sha256"], f"trajectory source drift before read: {path}")
                parquet = pq.ParquetFile(path)
                underlying_type = parquet.schema_arrow.field("underlying_timestamp").type
                interval_type = parquet.schema_arrow.field("interval_used").type if "interval_used" in parquet.schema_arrow.names else None
                projection = [item["name"] for item in source["projected_schema"]] if source["projected_schema"] else [name for name in (*IDENTITY_COLUMNS, *VALUE_COLUMNS) if name in parquet.schema_arrow.names]
                exact_parts: list[np.ndarray] = []
                strike_codes: dict[str, int] = {}
                observed_by_contract: dict[tuple[str, str], set[int]] = defaultdict(set)
                source_observations: list[dict[str, Any]] = []
                close_i = coverage_by_path[path][0][4]
                for batch in parquet.iter_batches(batch_size=65536, columns=projection, use_threads=False):
                    codes = _batch_identity_clock_codes(batch, source, strike_codes)
                    exact_mask = ~codes["subminute"]
                    exact_parts.append(np.column_stack((codes["strike_codes"][exact_mask], codes["right_codes"][exact_mask], codes["minute"][exact_mask])).astype(np.int64, copy=False))
                    requested_mask = np.zeros(batch.num_rows, dtype=np.bool_)
                    for strike, right in requests[path]:
                        contract_mask = (codes["strike_text"] == strike) & (codes["right_codes"] == RIGHT_ORDINAL[right])
                        requested_mask |= contract_mask
                        ignored[(path, strike, right)]["subminute"] += int(np.count_nonzero(contract_mask & codes["subminute"]))
                        ignored[(path, strike, right)]["out"] += int(np.count_nonzero(contract_mask & exact_mask & ((codes["minute"] < 0) | (codes["minute"] > close_i))))
                    selected_mask = requested_mask & exact_mask & (codes["minute"] >= 0) & (codes["minute"] <= close_i)
                    underlying_array = batch.column(batch.schema.get_field_index("underlying_timestamp"))
                    for index in np.flatnonzero(selected_mask).tolist():
                        right = RIGHTS[int(codes["right_codes"][index])]
                        strike = str(codes["strike_text"][index])
                        minute_i = int(codes["minute"][index])
                        observed_by_contract[(strike, right)].add(minute_i)
                        row = {name: batch.column(batch.schema.get_field_index(name))[index].as_py() for name in projection}
                        clock_scalar = codes["clock_array"][index]
                        local = codes["local_lookup"][int(codes["clock_index"][index])]
                        row.update(
                            _primary_clock_scalar=clock_scalar,
                            _primary_clock_type=codes["clock_array"].type,
                            _underlying_timestamp_scalar=underlying_array[index],
                            _underlying_timestamp_type=underlying_array.type,
                        )
                        raw = timestamp_raw(underlying_array[index], underlying_type)
                        age, age_status = _underlying_age(row, local, source, raw)
                        source_observations.append({
                            "observation_id": observation_id(path, source["ticker"], source["expiration"], strike, right, minute_i),
                            "source_path": path, "source_sha256": source["sha256"], "ticker": source["ticker"],
                            "trade_date": source["trade_date"], "expiration": source["expiration"],
                            "right": right, "strike_decimal": strike, "minute_i": minute_i,
                            "clock_local": local.strftime("%H:%M"), "clock_basis": source["clock_basis"],
                            "receipt_time_status": "UNKNOWN",
                            "interval_used": interval_text(row.get("interval_used"), interval_type) if interval_type else None,
                            "bid": _nullable_float(row.get("bid")), "ask": _nullable_float(row.get("ask")),
                            "delta": _nullable_float(row.get("delta")), "implied_vol": _nullable_float(row.get("implied_vol")),
                            "gamma": _nullable_float(row.get("gamma")), "theta": _nullable_float(row.get("theta")),
                            "vega": _nullable_float(row.get("vega")), "rho": _nullable_float(row.get("rho")),
                            "underlying_price": _nullable_float(row.get("underlying_price")),
                            "underlying_timestamp_raw": raw, "underlying_age_ms": age,
                            "underlying_age_status": age_status, "quote_valid": valid_quote(row.get("bid"), row.get("ask")),
                        })
                _require_no_exact_duplicates(exact_parts, Path(path))
                source_observations.sort(key=lambda row: (RIGHT_ORDINAL[row["right"]], Decimal(row["strike_decimal"]), row["minute_i"]))
                if source_observations:
                    writer.write_table(pa.Table.from_pylist(source_observations, schema=schema), row_group_size=65536)
                observation_count += len(source_observations)
                for spec in coverage_by_path[path]:
                    decision = spec[0]
                    append_coverage(spec, observed_by_contract[(decision["strike_decimal"], decision["right"])])
                after_stat = guard_path(Path(path), SOURCE_ROOT)
                after_sha = sha256_file(Path(path))
                require(after_stat == before_stat and after_sha == before_sha, f"trajectory source drift after read: {path}")
                details.update(source_reads=1, observations=len(source_observations), ignored={"subminute": sum(ignored[(path, strike, right)]["subminute"] for strike, right in requests[path]), "out": sum(ignored[(path, strike, right)]["out"] for strike, right in requests[path])}, before_stat=before_stat, after_stat=after_stat, sha256_before=before_sha, sha256_after=after_sha)
    finally:
        writer.close()
    with observation_path.open("r+b") as handle:
        os.fsync(handle.fileno())

    for path in sorted(set(requests) - set(source_metadata), key=canonical_key):
        for spec in coverage_by_path[path]:
            append_coverage(spec, set())
    coverage.sort(key=lambda row: (decision_entry[row["decision_id"]], TICKER_ORDINAL[row["ticker"]], RIGHT_ORDINAL[row["right"]], ROLE_ORDINAL[row["role"]]))
    require(len(coverage) == len(decisions) * 3, "segment coverage cardinality")
    counts = {
        "ignored_subminute_rows": sum(value["subminute"] for value in ignored.values()),
        "ignored_out_of_session_rows": sum(value["out"] for value in ignored.values()),
        "missing_minutes": sum(row["missing_minute_count"] for row in coverage),
    }
    return observation_count, coverage, counts


def _field(name: str, value_type: pa.DataType, nullable: bool = False) -> pa.Field:
    return pa.field(name, value_type, nullable=nullable)


DECISION_SCHEMA = pa.schema([
    _field("decision_id", pa.string()), _field("plan_id", pa.string()), _field("source_authority", pa.string()),
    _field("ticker", pa.string()), _field("entry_date", pa.string()), _field("expiration", pa.string()),
    _field("right", pa.string()), _field("strike_decimal", pa.string()), _field("decision_clock", pa.string()),
    _field("decision_minute_i", pa.int16()), _field("decision_bid", pa.float64()), _field("decision_ask", pa.float64()),
    _field("decision_delta", pa.float64()), _field("decision_underlying_price", pa.float64()),
    _field("relative_spread", pa.float64()), _field("selector_distance", pa.float64()),
    _field("source_path", pa.string()), _field("source_sha256", pa.string()), _field("clock_basis", pa.string()),
    _field("receipt_time_status", pa.string()), _field("interval_used", pa.string(), True), _field("gamma_column_present", pa.bool_()),
])

OBSERVATION_SCHEMA = pa.schema([
    _field("observation_id", pa.string()), _field("source_path", pa.string()), _field("source_sha256", pa.string()),
    _field("ticker", pa.string()), _field("trade_date", pa.string()), _field("expiration", pa.string()),
    _field("right", pa.string()), _field("strike_decimal", pa.string()), _field("minute_i", pa.int16()),
    _field("clock_local", pa.string()), _field("clock_basis", pa.string()), _field("receipt_time_status", pa.string()),
    _field("interval_used", pa.string(), True), _field("bid", pa.float64(), True), _field("ask", pa.float64(), True),
    _field("delta", pa.float64(), True), _field("implied_vol", pa.float64(), True), _field("gamma", pa.float64(), True),
    _field("theta", pa.float64(), True), _field("vega", pa.float64(), True), _field("rho", pa.float64(), True),
    _field("underlying_price", pa.float64(), True), _field("underlying_timestamp_raw", pa.string(), True),
    _field("underlying_age_ms", pa.float64(), True), _field("underlying_age_status", pa.string()),
    _field("quote_valid", pa.bool_()),
])

COVERAGE_SCHEMA = pa.schema([
    _field("decision_id", pa.string()), _field("plan_id", pa.string()), _field("role", pa.string()),
    _field("ticker", pa.string()), _field("segment_date", pa.string()), _field("expiration", pa.string()),
    _field("right", pa.string()), _field("strike_decimal", pa.string()), _field("source_path", pa.string()),
    _field("source_status", pa.string()), _field("source_sha256", pa.string(), True), _field("close_i", pa.int16()),
    _field("expected_minute_count", pa.int16()), _field("observed_exact_minute_count", pa.int16()),
    _field("missing_minute_count", pa.int16()),
    _field("missing_ranges", pa.list_(pa.struct([_field("start_i", pa.int16()), _field("end_i", pa.int16())]))),
    _field("first_observed_i", pa.int16(), True), _field("last_observed_i", pa.int16(), True),
    _field("ignored_subminute_rows", pa.int64()), _field("ignored_out_of_session_rows", pa.int64()),
    _field("clock_basis", pa.string(), True), _field("gamma_column_present", pa.bool_(), True),
])


def parquet_metadata(schema: pa.Schema) -> pa.Schema:
    return schema.with_metadata({b"producer": b"weekly_zone_event_value_paths", b"schema_version": b"1"})


def write_parquet(path: Path, rows: Sequence[Mapping[str, Any]], schema: pa.Schema, *, group_key: Callable[[Mapping[str, Any]], Any] | None = None) -> int:
    schema = parquet_metadata(schema)
    writer = pq.ParquetWriter(
        path, schema, version="2.6", data_page_version="1.0", compression="zstd",
        compression_level=3, use_dictionary=True, write_statistics=True,
    )
    try:
        if group_key is None:
            for start in range(0, len(rows), 65536):
                writer.write_table(pa.Table.from_pylist(list(rows[start:start + 65536]), schema=schema), row_group_size=65536)
        else:
            group: list[Mapping[str, Any]] = []
            prior: Any = object()
            for row in rows:
                current = group_key(row)
                if group and current != prior:
                    writer.write_table(pa.Table.from_pylist(group, schema=schema), row_group_size=65536)
                    group = []
                group.append(row)
                prior = current
            if group:
                writer.write_table(pa.Table.from_pylist(group, schema=schema), row_group_size=65536)
    finally:
        writer.close()
    with path.open("r+b") as handle:
        os.fsync(handle.fileno())
    return len(rows)


def validate_stage_a(plans: Sequence[Mapping[str, Any]], sources: Sequence[Mapping[str, Any]], documents: Mapping[str, Any]) -> list[dict[str, Any]]:
    counts = Counter(row["status"] for row in plans)
    require(len(plans) == 2790 and counts == {"PLANNED": 1620, "NO_SERIES": 1164, "HORIZON_OUTSIDE_CALENDAR": 6}, "Stage-A plan counts")
    require(len(sources) == 2784 and sum(len(row["references"]) for row in sources) == 4860, "Stage-A source counts")
    require(documents["stage_a_summary"]["references"]["total"] == 4860, "Stage-A summary")
    audit = documents["stage_a_audit"]
    require(
        audit.get("checks") == {
            "all_entries_exact": True, "all_sources_and_references_exact": True,
            "authorities": 10, "bridge_overlay_rows": 6,
            "current_metadata_exact": True, "entry_plans": 2790,
            "source_references": 4860, "summary_exact": True,
            "unique_sources": 2784,
        },
        "Stage-A independent audit checks",
    )
    exit_doc = documents["stage_a_audit_exit"]
    require(exit_doc.get("exit_code") == 0 and exit_doc.get("audit_child_exit_code") == 0 and exit_doc.get("changed_pins") == [], "Stage-A audit exit")
    calendar = documents["unified_calendar"]["rows"]
    require(len(calendar) == 2790, "calendar count")
    return calendar


def normalize_calendar(
    document: Mapping[str, Any],
    raw_pin: Mapping[str, Any],
    journal: Journal,
    *,
    expected_sessions: int = 930,
    expected_short: int = 24,
    expected_full: int = 2766,
    expected_bytes: int = CANONICAL_CALENDAR_BYTES,
    expected_sha256: str = CANONICAL_CALENDAR_SHA256,
    expected_first: Mapping[str, Any] | None = None,
    expected_last: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with journal.unit_context("NORMALIZE_CALENDAR", "UNIFIED_CALENDAR", [raw_pin["path"]]) as details:
        require(set(document) == {"schema", "rows"}, "calendar top-level keys")
        require(document["schema"] == "weekly_h2_boundary_unified_calendar_v1", "calendar schema")
        rows = document["rows"]
        expected_rows = expected_sessions * len(TICKERS)
        require(isinstance(rows, list) and len(rows) == expected_rows, "calendar row count")
        triples: list[tuple[str, str, int]] = []
        by_ticker: dict[str, list[str]] = {ticker: [] for ticker in TICKERS}
        for row in rows:
            require(isinstance(row, dict) and set(row) == {"close_i", "date", "ticker"}, "calendar row keys")
            ticker, day, close_i = row["ticker"], row["date"], row["close_i"]
            require(ticker in TICKERS, "calendar ticker")
            require(isinstance(day, str) and re.fullmatch(r"\d{8}", day) is not None and parse_day_scalar(day) == day, "calendar date")
            require(type(close_i) is int and close_i in (210, 390), "calendar close_i")
            triples.append((ticker, day, close_i))
            by_ticker[ticker].append(day)
        require(len(set((ticker, day) for ticker, day, _close in triples)) == expected_rows, "calendar duplicate identity")
        require(all(len(days) == expected_sessions and days == sorted(days) for days in by_ticker.values()), "calendar ticker date order/count")
        require(set(by_ticker["SPY"]) == set(by_ticker["QQQ"]) == set(by_ticker["SPXW"]), "calendar ticker date sets")
        require(sum(close_i == 210 for _ticker, _day, close_i in triples) == expected_short and sum(close_i == 390 for _ticker, _day, close_i in triples) == expected_full, "calendar session-kind counts")
        require(triples == sorted(triples, key=lambda value: (value[0], value[1])), "calendar upstream order")
        canonical_rows = [
            {"ticker": ticker, "date": day, "close_i": close_i}
            for ticker, day, close_i in sorted(triples, key=lambda value: (value[1], TICKER_ORDINAL[value[0]]))
        ]
        require({(row["ticker"], row["date"], row["close_i"]) for row in canonical_rows} == set(triples), "calendar identity/close preservation")
        payload = "".join(compact_json(row) + "\n" for row in canonical_rows).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        require(len(payload) == expected_bytes and digest == expected_sha256, "canonical calendar digest")
        first = expected_first or {"ticker": "SPY", "date": "20230103", "close_i": 390}
        last = expected_last or {"ticker": "SPXW", "date": "20260917", "close_i": 390}
        require(canonical_rows[0] == dict(first) and canonical_rows[-1] == dict(last), "canonical calendar bounds")
        normalization = {
            "raw_pin": dict(raw_pin),
            "raw_order": RAW_CALENDAR_ORDER,
            "canonical_order": CANONICAL_CALENDAR_ORDER,
            "rows": expected_rows,
            "canonical_jsonl_bytes": expected_bytes,
            "canonical_jsonl_sha256": expected_sha256,
            "identity_set_preserved": True,
            "close_i_preserved": True,
        }
        details.update(
            raw_pin=dict(raw_pin), raw_schema=document["schema"], raw_rows=expected_rows,
            raw_order=RAW_CALENDAR_ORDER, canonical_order=CANONICAL_CALENDAR_ORDER,
            canonical_rows=expected_rows, canonical_jsonl_bytes=expected_bytes,
            canonical_jsonl_sha256=expected_sha256,
            identity_set_preserved=True, close_i_preserved=True,
        )
    return canonical_rows, normalization


def validate_prior_failure(documents: Mapping[str, Any]) -> None:
    exit_doc = documents["prior_producer_exit"]
    failure = documents["prior_producer_failure"]
    journal_rows = documents["prior_producer_journal"]
    require(exit_doc.get("exit_code") == 1 and exit_doc.get("value_child_exit_code") == 1 and exit_doc.get("retry") is False and exit_doc.get("changed_pins") == [], "prior producer exit evidence")
    require(failure.get("exit_code") == 1 and failure.get("value_child_exit_code") == 1 and failure.get("partial_output_not_authorized_for_adoption") is True and failure.get("retry") is False, "prior producer failure evidence")
    require(isinstance(journal_rows, list) and len(journal_rows) == 4, "prior producer journal cardinality")
    require([(row.get("kind"), row.get("identity"), row.get("event")) for row in journal_rows] == [
        ("ADMIT_AUTHORITIES", "IMPLEMENTATION_PINS", "STARTED"),
        ("ADMIT_AUTHORITIES", "IMPLEMENTATION_PINS", "COMPLETED"),
        ("ADMIT_AUTHORITIES", "PINNED_AUTHORITIES", "STARTED"),
        ("ADMIT_AUTHORITIES", "PINNED_AUTHORITIES", "COMPLETED"),
    ], "prior producer journal sequence")
    require(not any(row.get("event") == "ERROR" for row in journal_rows), "prior producer journal ERROR")


def validate_authority_crosspins(documents: Mapping[str, Any], pins: Mapping[str, Mapping[str, Any]]) -> None:
    stage_manifest = documents["stage_a_manifest"]
    require(stage_manifest.get("schema") == "weekly_zone_event_source_plan_manifest_v1" and stage_manifest.get("status") == "SOURCE_PLAN_NOT_VALUE_ADMISSION", "Stage-A manifest status")
    for output, key in (("entry_plan.jsonl", "stage_a_entry_plan"), ("weekly_sources.jsonl", "stage_a_weekly_sources"), ("summary.json", "stage_a_summary")):
        value = stage_manifest.get("outputs", {}).get(output, {})
        require(value.get("bytes") == pins[key]["bytes"] and value.get("sha256") == pins[key]["sha256"], f"Stage-A output crosspin: {output}")

    expected = (
        ("h1", "weekly_h2_source_inventory_v2_clock_filter", "weekly_h2_inventory_manifest_v1", "weekly_h2_dataset_manifest_v2", "COMPLETE_WEEKLY_H2_DATASET_NOT_EVALUATED"),
        ("q3", "weekly_h2_q3_partial_inventory_v1", "weekly_h2_q3_partial_inventory_manifest_v1", "weekly_h2_q3_partial_dataset_manifest_v1", "COMPLETE_WEEKLY_H2_Q3_PARTIAL_DATASET_NOT_EVALUATED"),
        ("bridge", "weekly_h2_boundary_bridge_inventory_v1", "weekly_h2_boundary_bridge_inventory_manifest_v1", "weekly_h2_boundary_bridge_manifest_v1", "COMPLETE_WEEKLY_H2_BOUNDARY_BRIDGE_NOT_EVALUATED"),
    )
    for prefix, inventory_schema, receipt_schema, manifest_schema, status in expected:
        inventory = documents[f"{prefix}_inventory"]
        receipt = documents[f"{prefix}_inventory_manifest"]
        manifest = documents[f"{prefix}_manifest"]
        require(inventory.get("schema") == inventory_schema, f"{prefix} inventory schema")
        require(receipt.get("schema") == receipt_schema, f"{prefix} receipt schema")
        require(manifest.get("schema") == manifest_schema and manifest.get("status") == status, f"{prefix} manifest status")
        inventory_pin = pins[f"{prefix}_inventory"]
        receipt_value = receipt.get("inventory.json", {})
        require(receipt_value.get("bytes") == inventory_pin["bytes"] and receipt_value.get("sha256") == inventory_pin["sha256"], f"{prefix} inventory receipt crosspin")
        manifest_value = manifest.get("files", {}).get("inventory.json", {})
        require(manifest_value.get("bytes") == inventory_pin["bytes"] and manifest_value.get("sha256") == inventory_pin["sha256"], f"{prefix} manifest inventory crosspin")
    require(len(documents["h1_inventory"].get("sources", [])) == 2619, "H1 inventory sources")
    require(len(documents["q3_inventory"].get("sources", [])) == 156, "Q3 inventory sources")
    require(len(documents["bridge_inventory"].get("sources", [])) == 6, "bridge inventory sources")


def load_authorities(journal: Journal) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    documents: dict[str, Any] = {}
    pins: dict[str, dict[str, Any]] = {}
    physical_registry: dict[tuple[int, int], str] = {}
    with journal.unit_context("ADMIT_AUTHORITIES", "PINNED_AUTHORITIES", [str(value[0]) for value in PINNED_AUTHORITIES.values()]) as details:
        for key, (path, size, digest) in PINNED_AUTHORITIES.items():
            resource_gate()
            observed = secure_pin(path, physical_registry)
            require(observed["bytes"] == size and observed["sha256"] == digest, f"authority pin mismatch: {key}")
            pins[key] = observed
            if key in ("stage_a_entry_plan", "stage_a_weekly_sources", "prior_producer_journal"):
                documents[key] = read_jsonl(path)
            elif path.suffix == ".json":
                documents[key] = json.loads(path.read_text(encoding="utf-8"))
        details.update(authorities=len(pins))
    return documents, pins


def import_spot_module(expected_pin: Mapping[str, Any]) -> Any:
    require(pin(SPOT_MODULE) == dict(expected_pin), "spot module runtime pin mismatch")
    spec = importlib.util.spec_from_file_location("weekly_zone_event_spot_paths_runtime", SPOT_MODULE)
    require(spec is not None and spec.loader is not None, "spot module import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(callable(getattr(module, "extract_spot_paths", None)), "spot interface missing")
    return module


def validate_spot_result(spot_result: Mapping[str, Any], staging: Path) -> None:
    require(set(spot_result) == {"outputs", "counts", "admitted_inputs"}, "spot result schema")
    require(set(spot_result["outputs"]) == {"cache_admission.jsonl", "spot_paths.parquet", "spot_coverage.jsonl"}, "spot output names")
    require(
        set(spot_result["counts"]) == {
            "identities", "available", "missing", "full", "short",
            "available_rows", "missing_rows", "path_rows", "valid_rows",
            "invalid_rows", "h1_available", "h1_missing", "q3_available",
            "q3_missing", "admitted_inputs",
        },
        "spot counts schema",
    )
    require(spot_result["counts"]["identities"] == 2790 and spot_result["counts"]["available"] == 2772 and spot_result["counts"]["missing"] == 18 and spot_result["counts"]["path_rows"] == 1086570, "spot counts")
    require(
        {key: spot_result["counts"][key] for key in ("full", "short", "available_rows", "missing_rows", "h1_available", "h1_missing", "q3_available", "q3_missing")}
        == {"full": 2766, "short": 24, "available_rows": 1079532, "missing_rows": 7038, "h1_available": 2619, "h1_missing": 6, "q3_available": 153, "q3_missing": 12},
        "spot structural counts",
    )
    require(spot_result["counts"]["valid_rows"] + spot_result["counts"]["invalid_rows"] == 1086570, "spot valid/invalid partition")
    require(spot_result["counts"]["admitted_inputs"] == 8163 and len(spot_result["admitted_inputs"]) == 8163, "spot admitted input population")
    for name, value in spot_result["outputs"].items():
        require(set(value) == {"path", "bytes", "sha256"}, f"spot output pin schema: {name}")
        require(canonical(value["path"]) == canonical(staging / name) and secure_pin(Path(value["path"])) == value, f"spot output pin mismatch: {name}")


def _output_pin(path: Path, rows: int, final_root: Path = OUTPUT) -> dict[str, Any]:
    observed = pin(path)
    observed["path"] = str(canonical(final_root / path.name))
    observed["rows"] = rows
    return observed


def validate_summary_document(value: Mapping[str, Any]) -> None:
    require(set(value) == SUMMARY_KEYS, "summary top-level keys")
    require(value.get("schema") == "weekly_zone_event_value_paths_summary_v2_calendar_normalized" and value.get("status") == STATUS, "summary identity")
    require(set(value.get("outputs", {})) == DATA_OUTPUT_NAMES, "summary output keys")
    require(value.get("flags") == FLAGS and value.get("limitations") == LIMITATIONS, "summary flags/limitations")
    validate_calendar_envelope(value.get("calendar_normalization"))


def validate_manifest_document(value: Mapping[str, Any]) -> None:
    require(set(value) == MANIFEST_KEYS, "manifest top-level keys")
    require(value.get("schema") == "weekly_zone_event_value_paths_manifest_v2_calendar_normalized" and value.get("status") == STATUS, "manifest identity")
    require(set(value.get("outputs", {})) == DATA_OUTPUT_NAMES | {"summary.json"}, "manifest output keys/no self-pin")
    require("manifest.json" not in value.get("outputs", {}) and value.get("flags") == FLAGS, "manifest self-pin/flags")
    validate_calendar_envelope(value.get("calendar_normalization"))


def validate_calendar_envelope(value: Any) -> None:
    require(isinstance(value, dict) and set(value) == {"raw_pin", "raw_order", "canonical_order", "rows", "canonical_jsonl_bytes", "canonical_jsonl_sha256", "identity_set_preserved", "close_i_preserved"}, "calendar normalization envelope")
    require(value["raw_order"] == RAW_CALENDAR_ORDER and value["canonical_order"] == CANONICAL_CALENDAR_ORDER, "calendar normalization orders")
    calendar_path, calendar_bytes, calendar_sha = PINNED_AUTHORITIES["unified_calendar"]
    require(value["raw_pin"] == {"path": str(canonical(calendar_path)), "bytes": calendar_bytes, "sha256": calendar_sha}, "calendar normalization raw pin")
    require(value["rows"] == 2790 and value["canonical_jsonl_bytes"] == CANONICAL_CALENDAR_BYTES and value["canonical_jsonl_sha256"] == CANONICAL_CALENDAR_SHA256, "calendar normalization digest/count")
    require(value["identity_set_preserved"] is True and value["close_i_preserved"] is True, "calendar normalization preservation")


def closing_rehash_file(
    journal: Journal,
    identity: str,
    expected: Mapping[str, Any],
    registry: MutableMapping[tuple[int, int], str],
    middle: Callable[[], None] | None = None,
) -> None:
    with journal.unit_context("CLOSING_REHASH", identity, [expected["path"]]) as details:
        before = secure_pin(Path(expected["path"]), registry)
        require(before == dict(expected), f"closing rehash drift: {identity}")
        if middle is not None:
            middle()
        after = secure_pin(Path(expected["path"]))
        require(after == before, f"input changed during closing rehash: {identity}")
        details.update(before=before, after=after)


def _verify_implementation_pins(value: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    expected = {"builder", "spot_module", "builder_tests", "spot_tests", "contract", "builder_final_review", "spot_final_review", "runtime_binding", "launcher", "resource_helper"}
    require(set(value) == expected, "implementation pin keys")
    result: dict[str, dict[str, Any]] = {}
    physical_registry: dict[tuple[int, int], str] = {}
    for key, item in value.items():
        require(set(item) == {"path", "bytes", "sha256"}, f"implementation pin schema: {key}")
        actual = secure_pin(Path(item["path"]), physical_registry)
        require(actual == item, f"implementation pin mismatch: {key}")
        result[key] = actual
    require(result["contract"]["sha256"] == CONTRACT_SHA256 and result["resource_helper"]["sha256"] == RESOURCE_HELPER_SHA256, "fixed implementation pin mismatch")
    return result


def execute_reviewed_builder(
    output_dir: Path,
    observer_dir: Path,
    journal_path: Path,
    implementation_pins_path: Path,
) -> None:
    output_dir, observer_dir, journal_path = canonical(output_dir), canonical(observer_dir), canonical(journal_path)
    require(output_dir == canonical(OUTPUT) and observer_dir == canonical(OBSERVER), "real output roots are frozen")
    require(journal_path == canonical(observer_dir / "journal.jsonl"), "journal path is frozen under observer")
    require(not output_dir.exists(), "immutable output already exists")
    require(not OUTPUT_V1.exists(), "failed producer 01 output root must remain absent")
    require(observer_dir.is_dir(), "observer must be prepared by launcher")
    guard_directory(output_dir.parent)
    guard_directory(observer_dir)
    guard_directory(SOURCE_ROOT)
    require(os.environ.get("CUDA_VISIBLE_DEVICES") == "-1" and all(os.environ.get(name) == "1" for name in THREAD_VARS), "thread environment not frozen")
    require(np.__version__ == "2.3.5" and pa.__version__ == "23.0.1", "runtime version mismatch")
    journal = Journal(journal_path)
    implementation_pins_path = canonical(implementation_pins_path)
    require(implementation_pins_path == canonical(observer_dir / "implementation_pins.json"), "implementation pins path is frozen under observer")
    with journal.unit_context("ADMIT_AUTHORITIES", "IMPLEMENTATION_PINS", [str(implementation_pins_path)]) as details:
        implementation_document_pin = secure_pin(implementation_pins_path)
        implementation_pins = json.loads(implementation_pins_path.read_text(encoding="utf-8"))
        require(isinstance(implementation_pins, dict), "implementation pins document")
        impl = _verify_implementation_pins(implementation_pins)
        details.update(pins=len(impl))
    documents, authority_pins = load_authorities(journal)
    require(len(authority_pins) == 29 and set(authority_pins) == set(PINNED_AUTHORITIES), "V2 authority population")
    validate_authority_crosspins(documents, authority_pins)
    validate_prior_failure(documents)
    plans = documents["stage_a_entry_plan"]
    stage_sources = documents["stage_a_weekly_sources"]
    validate_stage_a(plans, stage_sources, documents)
    calendar, calendar_normalization = normalize_calendar(documents["unified_calendar"], authority_pins["unified_calendar"], journal)
    resource_gate()
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        with journal.unit_context("ADMIT_OPTION_FOOTERS", "GLOBAL_PASS", [row["path"] for row in stage_sources]):
            admission, option_inputs, source_metadata = admit_option_sources(stage_sources, documents, journal)
        source_admission_path = staging / "source_admission.jsonl"
        with journal.unit_context("WRITE_OUTPUTS", "source_admission.jsonl", [str(source_admission_path)]) as details:
            source_admission_rows = write_jsonl(source_admission_path, admission)
            details.update(rows=source_admission_rows, pin=pin(source_admission_path))

        with journal.unit_context("SELECT_1030", "GLOBAL_PASS", [row["entry_path"] for row in plans if row["status"] == "PLANNED"]):
            decisions, _misses = select_decisions(plans, source_metadata, journal)
        decision_path = staging / "decision_contracts.parquet"
        with journal.unit_context("WRITE_OUTPUTS", "decision_contracts.parquet", [str(decision_path)]) as details:
            decision_rows = write_parquet(decision_path, decisions, DECISION_SCHEMA)
            details.update(rows=decision_rows, pin=pin(decision_path))

        observation_path = staging / "option_quote_observations.parquet"
        coverage_path = staging / "segment_coverage.parquet"
        with journal.unit_context("WRITE_OUTPUTS", "option_quote_observations.parquet", [str(observation_path)]) as details:
            with journal.unit_context("STREAM_OPTION_PATHS", "GLOBAL_PASS", sorted(source_metadata)):
                observation_rows, coverage, option_counts = stream_option_paths(plans, decisions, source_metadata, journal, observation_path)
            details.update(rows=observation_rows, pin=pin(observation_path))
        with journal.unit_context("WRITE_OUTPUTS", "segment_coverage.parquet", [str(coverage_path)]) as details:
            coverage_rows = write_parquet(coverage_path, coverage, COVERAGE_SCHEMA)
            details.update(rows=coverage_rows, pin=pin(coverage_path))

        spot_authority_keys = ("h1_context_inventory", "h1_context_inventory_manifest", "h1_context_manifest", "q3_context_inventory", "q3_context_inventory_manifest", "q3_context_manifest")
        spot_documents = {
            "h1_inventory": documents["h1_context_inventory"],
            "h1_inventory_manifest": documents["h1_context_inventory_manifest"],
            "h1_manifest": documents["h1_context_manifest"],
            "q3_inventory": documents["q3_context_inventory"],
            "q3_inventory_manifest": documents["q3_context_inventory_manifest"],
            "q3_manifest": documents["q3_context_manifest"],
        }
        spot_pins = dict(zip(spot_documents, (authority_pins[key] for key in spot_authority_keys), strict=True))
        spot_module = import_spot_module(impl["spot_module"])
        spot_result = spot_module.extract_spot_paths(calendar, staging, spot_documents, spot_pins, journal.unit_context)
        validate_spot_result(spot_result, staging)

        data_outputs = {
            "source_admission.jsonl": _output_pin(source_admission_path, source_admission_rows),
            "decision_contracts.parquet": _output_pin(decision_path, decision_rows),
            "option_quote_observations.parquet": _output_pin(observation_path, observation_rows),
            "segment_coverage.parquet": _output_pin(coverage_path, coverage_rows),
            **{
                name: {
                    "path": str(canonical(output_dir / name)),
                    "bytes": value["bytes"], "sha256": value["sha256"],
                    "rows": spot_result["counts"][{"cache_admission.jsonl": "identities", "spot_paths.parquet": "path_rows", "spot_coverage.jsonl": "identities"}[name]],
                }
                for name, value in spot_result["outputs"].items()
            },
        }
        summary = {
            "schema": "weekly_zone_event_value_paths_summary_v2_calendar_normalized", "status": STATUS,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "stage_a": {"sessions": 930, "ticker_days": 2790, "planned": 1620, "no_series": 1164, "terminal": 6, "references": 4860, "unique_sources": 2784},
            "option_admission": {
                "present": 2768, "missing": 16, "historical": 2765, "first_authority": 3,
                "native_historical": 1562, "proxy_historical": 1203,
                "native_new": sum(row["binding_kind"] == "FIRST_AUTHORITY" and row["clock_basis"] == "NATIVE_STORED_TIMESTAMP" for row in admission),
                "proxy_new": sum(row["binding_kind"] == "FIRST_AUTHORITY" and row["clock_basis"] == "UNDERLYING_TIMESTAMP_PROXY" for row in admission),
            },
            "selector": {"plans": 1620, "decisions": 3240, "h1": 3054, "q3": 180, "bridge": 6, "calls": 1620, "puts": 1620, "no_valid_call": 0, "no_valid_put": 0},
            "option_paths": {"segments": 9720, "observations": observation_rows, "selector_source_reads": 1620, "trajectory_source_reads": 2768, **option_counts},
            "spot": {key: spot_result["counts"][key] for key in ("identities", "available", "missing", "full", "short", "available_rows", "missing_rows", "path_rows", "valid_rows", "invalid_rows")},
            "outputs": data_outputs, "flags": FLAGS, "limitations": LIMITATIONS,
            "calendar_normalization": calendar_normalization,
        }
        validate_summary_document(summary)
        summary_path = staging / "summary.json"
        with journal.unit_context("WRITE_OUTPUTS", "summary.json", [str(summary_path)]) as details:
            write_json(summary_path, summary)
            details.update(rows=1, pin=pin(summary_path))
        summary_pin = _output_pin(summary_path, 1)
        manifest = {
            "schema": "weekly_zone_event_value_paths_manifest_v2_calendar_normalized", "status": STATUS,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "implementation_pins": impl, "authority_inputs": authority_pins,
            "admitted_option_sources": dict(sorted(option_inputs.items(), key=lambda item: canonical_key(item[0]))),
            "admitted_spot_inputs": dict(sorted(spot_result["admitted_inputs"].items(), key=lambda item: canonical_key(item[0]))),
            "outputs": {**data_outputs, "summary.json": summary_pin},
            "counts": {"option_sources": 2784, "decisions": 3240, "segments": 9720, "spot_identities": 2790, "spot_rows": 1086570},
            "flags": FLAGS,
            "environment": {"python": sys.version, "numpy": "2.3.5", "pyarrow": "23.0.1", "ruff": "0.15.20", "pytest": "9.0.2"},
            "calendar_normalization": calendar_normalization,
        }
        validate_manifest_document(manifest)
        manifest_path = staging / "manifest.json"
        with journal.unit_context("WRITE_OUTPUTS", "manifest.json", [str(manifest_path)]) as details:
            write_json(manifest_path, manifest)
            details.update(rows=1, pin=pin(manifest_path))
        all_inputs = {**authority_pins, **option_inputs, **spot_result["admitted_inputs"], **impl, "runtime_implementation_pins_document": implementation_document_pin}
        first_authority = {row["path"]: row for row in admission if row["binding_kind"] == "FIRST_AUTHORITY"}
        closing_registry: dict[tuple[int, int], str] = {}
        for name, expected in sorted(all_inputs.items(), key=lambda item: canonical_key(item[1]["path"])):
            row = first_authority.get(str(canonical(expected["path"])))

            def validate_first_authority() -> None:
                if row is not None:
                    parquet = pq.ParquetFile(row["path"])
                    require(parquet.metadata.num_rows == row["rows"] and parquet.metadata.num_row_groups == row["row_groups"] and canonical_arrow_schema(parquet.schema_arrow) == row["full_schema"], f"first-authority closing footer drift: {row['path']}")
            closing_rehash_file(journal, str(name), expected, closing_registry, validate_first_authority if row is not None else None)
        for row in (item for item in admission if item["binding_kind"] == "EXPECTED_MISSING"):
            with journal.unit_context("CLOSING_REHASH", f"EXPECTED_MISSING:{row['path']}", [row["path"]]) as details:
                missing_stat = guard_path(Path(row["path"]), SOURCE_ROOT, expected_missing=True)
                require(missing_stat == row["before_stat"], f"missing option source appeared at closing: {row['path']}")
                details.update(before=missing_stat, after=missing_stat)
        closing_outputs = {
            **{name: {"path": str(staging / name), "bytes": value["bytes"], "sha256": value["sha256"]} for name, value in data_outputs.items()},
            "summary.json": {"path": str(summary_path), "bytes": summary_pin["bytes"], "sha256": summary_pin["sha256"]},
            "manifest.json": pin(manifest_path),
        }
        output_registry: dict[tuple[int, int], str] = {}
        for name, expected in sorted(closing_outputs.items()):
            closing_rehash_file(journal, f"OUTPUT:{name}", expected, output_registry)
        resource_gate()
        require(not output_dir.exists(), "publication target appeared")
        os.replace(staging, output_dir)
    except BaseException as error:
        try:
            write_json(staging / "failure.json", {"status": "FAILED_PARTIAL_NOT_ADOPTABLE", "error_type": type(error).__name__, "error": str(error)})
        except BaseException:
            pass
        raise


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--execute-reviewed-builder", action="store_true", required=True)
    result.add_argument("--output-dir", required=True)
    result.add_argument("--observer-dir", required=True)
    result.add_argument("--journal", required=True)
    result.add_argument("--implementation-pins-json", required=True)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    execute_reviewed_builder(Path(args.output_dir), Path(args.observer_dir), Path(args.journal), Path(args.implementation_pins_json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


