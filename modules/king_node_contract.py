"""Hash-pinned, pure-data contract for the KING NODE v2 calculation core.

This module deliberately contains no file, network, Excel, or HTML dependency.
Adapters may obtain data from ThetaData or a workbook export, but the calculation
core only receives the validated mappings produced here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
from typing import Any, Mapping


SCHEMA_VERSION = "king-node.v2"
INPUT_SCHEMA_VERSION = "king-node.v2-input"
REFERENCE_SCHEMA_VERSION = "king-node-reference.v2"
STATE_SCHEMA_VERSION = "king-node.v2-state"

WORKBOOK_SHA256 = "38fc80bddc0914e9b1ce6430a1ba822ca6f76693a4170ab407497109a02d4406"
CATALOGUE_SHA256 = "847a0a0675b6caf7296c45e9cafeb4ca8531de07471ee0a6a1bc6b1c19806d20"

ADVANCED_GREEKS = (
    "gamma",
    "zomma",
    "vanna",
    "vomma",
    "vega",
    "speed",
    "charm",
    "dgex",
)
INDEX_PROVENANCE = frozenset({"observed", "reconstructed", "unavailable"})
GREEK_PROVENANCE = frozenset({"observed", "model_derived"})


class FormulaClassification(str, Enum):
    """The only classifications permitted in the workbook coverage ledger."""

    RUNTIME_CALCULATION = "runtime_calculation"
    STATIC_REFERENCE_EXPORT = "static_reference_export"
    PRESENTATION_RULE = "presentation_rule"
    CONDITIONAL_FORMATTING = "conditional_formatting"
    INPUT_VALIDATION = "input_validation"
    HISTORICAL_LOG = "historical_log"
    NOT_RUNTIME_APPLICABLE = "not_runtime_applicable"


FORMULA_CLASSIFICATIONS = tuple(item.value for item in FormulaClassification)


class KingNodeContractError(ValueError):
    """Base error for a rejected v2 contract object."""


class KingNodeInputError(KingNodeContractError):
    """The normalized market input is incomplete or has invalid provenance."""


class KingNodeReferenceError(KingNodeContractError):
    """The static workbook reference is missing, altered, or incomplete."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return the deterministic JSON representation used for integrity hashes."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def canonical_reference_payload(reference: Mapping[str, Any]) -> dict[str, Any]:
    """Return the signed portion of a reference export.

    The checksum itself is intentionally excluded so a producer and consumer use
    the same fixed-point-free payload.
    """

    return {
        str(key): value
        for key, value in reference.items()
        if str(key) != "canonical_checksum"
    }


def canonical_reference_checksum(reference: Mapping[str, Any]) -> str:
    return sha256_json(canonical_reference_payload(reference))


def _mapping(value: Any, label: str, error_type: type[KingNodeContractError]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise error_type(f"{label} must be an object")
    return value


def _string(value: Any, label: str, error_type: type[KingNodeContractError]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise error_type(f"{label} must be a non-empty string")
    return value.strip()


def _finite_number(
    value: Any,
    label: str,
    error_type: type[KingNodeContractError],
    *,
    minimum: float | None = None,
) -> float:
    if isinstance(value, bool):
        raise error_type(f"{label} must be a finite number")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise error_type(f"{label} must be a finite number") from exc
    if not math.isfinite(parsed):
        raise error_type(f"{label} must be a finite number")
    if minimum is not None and parsed < minimum:
        raise error_type(f"{label} must be >= {minimum:g}")
    return parsed


def _iso_timestamp(value: Any, label: str, error_type: type[KingNodeContractError]) -> str:
    text = _string(value, label, error_type)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise error_type(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise error_type(f"{label} must include a timezone")
    return parsed.isoformat().replace("+00:00", "Z")


def _date(value: Any, label: str, error_type: type[KingNodeContractError]) -> str:
    text = _string(value, label, error_type)
    try:
        datetime.fromisoformat(f"{text}T00:00:00")
    except ValueError as exc:
        raise error_type(f"{label} must use YYYY-MM-DD") from exc
    return text


@dataclass(frozen=True)
class GreekValue:
    """A higher Greek whose provenance is explicit and inspectable."""

    value: float
    provenance: str
    methodology: str | None
    source_fields: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Any, label: str) -> "GreekValue":
        item = _mapping(value, label, KingNodeInputError)
        number = _finite_number(item.get("value"), f"{label}.value", KingNodeInputError)
        provenance = _string(
            item.get("provenance"), f"{label}.provenance", KingNodeInputError
        )
        if provenance not in GREEK_PROVENANCE:
            raise KingNodeInputError(
                f"{label}.provenance must be observed or model_derived"
            )
        methodology = item.get("methodology")
        if methodology is not None:
            methodology = _string(methodology, f"{label}.methodology", KingNodeInputError)
        raw_sources = item.get("source_fields", [])
        if not isinstance(raw_sources, list) or any(
            not isinstance(source, str) or not source for source in raw_sources
        ):
            raise KingNodeInputError(f"{label}.source_fields must be a string list")
        source_fields = tuple(raw_sources)
        if provenance == "model_derived" and (not methodology or not source_fields):
            raise KingNodeInputError(
                f"{label} model_derived values require methodology and source_fields"
            )
        return cls(number, provenance, methodology, source_fields)

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "value": self.value,
            "provenance": self.provenance,
        }
        if self.methodology is not None:
            result["methodology"] = self.methodology
        if self.source_fields:
            result["source_fields"] = list(self.source_fields)
        return result


@dataclass(frozen=True)
class OptionRow:
    """One Theta-sourced option leg in the normalised v2 surface."""

    symbol: str
    root: str
    expiry: str
    strike: float
    right: str
    bid: float
    ask: float
    provider_timestamp: str
    open_interest: float
    oi_source_date: str
    iv: float
    delta: float
    theta: float
    underlying: float
    underlying_timestamp: str
    rate: float
    time_to_expiry_years: float
    greeks: Mapping[str, GreekValue]

    @classmethod
    def from_mapping(cls, value: Any, index: int) -> "OptionRow":
        label = f"option_rows[{index}]"
        item = _mapping(value, label, KingNodeInputError)
        right = _string(item.get("right"), f"{label}.right", KingNodeInputError).upper()
        right = {"C": "CALL", "P": "PUT"}.get(right, right)
        if right not in {"CALL", "PUT"}:
            raise KingNodeInputError(f"{label}.right must be CALL or PUT")
        bid = _finite_number(item.get("bid"), f"{label}.bid", KingNodeInputError, minimum=0)
        ask = _finite_number(item.get("ask"), f"{label}.ask", KingNodeInputError, minimum=0)
        if ask < bid:
            raise KingNodeInputError(f"{label}.ask must be >= bid")
        greeks_raw = _mapping(item.get("greeks"), f"{label}.greeks", KingNodeInputError)
        missing = [name for name in ADVANCED_GREEKS if name not in greeks_raw]
        if missing:
            raise KingNodeInputError(
                f"{label}.greeks is missing: " + ", ".join(missing)
            )
        greeks = {
            name: GreekValue.from_mapping(greeks_raw[name], f"{label}.greeks.{name}")
            for name in ADVANCED_GREEKS
        }
        return cls(
            symbol=_string(item.get("symbol"), f"{label}.symbol", KingNodeInputError).upper(),
            root=_string(item.get("root"), f"{label}.root", KingNodeInputError).upper(),
            expiry=_date(item.get("expiry"), f"{label}.expiry", KingNodeInputError),
            strike=_finite_number(item.get("strike"), f"{label}.strike", KingNodeInputError, minimum=0.0000001),
            right=right,
            bid=bid,
            ask=ask,
            provider_timestamp=_iso_timestamp(item.get("provider_timestamp"), f"{label}.provider_timestamp", KingNodeInputError),
            open_interest=_finite_number(item.get("open_interest"), f"{label}.open_interest", KingNodeInputError, minimum=0),
            oi_source_date=_date(item.get("oi_source_date"), f"{label}.oi_source_date", KingNodeInputError),
            iv=_finite_number(item.get("iv"), f"{label}.iv", KingNodeInputError, minimum=0),
            delta=_finite_number(item.get("delta"), f"{label}.delta", KingNodeInputError),
            theta=_finite_number(item.get("theta"), f"{label}.theta", KingNodeInputError),
            underlying=_finite_number(item.get("underlying"), f"{label}.underlying", KingNodeInputError, minimum=0.0000001),
            underlying_timestamp=_iso_timestamp(item.get("underlying_timestamp"), f"{label}.underlying_timestamp", KingNodeInputError),
            rate=_finite_number(item.get("rate"), f"{label}.rate", KingNodeInputError),
            time_to_expiry_years=_finite_number(item.get("time_to_expiry_years"), f"{label}.time_to_expiry_years", KingNodeInputError, minimum=0),
            greeks=greeks,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "root": self.root,
            "expiry": self.expiry,
            "strike": self.strike,
            "right": self.right,
            "bid": self.bid,
            "ask": self.ask,
            "provider_timestamp": self.provider_timestamp,
            "open_interest": self.open_interest,
            "oi_source_date": self.oi_source_date,
            "iv": self.iv,
            "delta": self.delta,
            "theta": self.theta,
            "underlying": self.underlying,
            "underlying_timestamp": self.underlying_timestamp,
            "rate": self.rate,
            "time_to_expiry_years": self.time_to_expiry_years,
            "greeks": {name: greek.as_dict() for name, greek in self.greeks.items()},
        }


@dataclass(frozen=True)
class IndexTerm:
    value: float | None
    provenance: str
    timestamp: str | None
    methodology: str
    quality: str

    @classmethod
    def from_mapping(cls, value: Any, name: str) -> "IndexTerm":
        item = _mapping(value, f"indices.{name}", KingNodeInputError)
        provenance = _string(
            item.get("provenance"), f"indices.{name}.provenance", KingNodeInputError
        )
        if provenance not in INDEX_PROVENANCE:
            raise KingNodeInputError(
                f"indices.{name}.provenance must be observed, reconstructed, or unavailable"
            )
        raw_value = item.get("value")
        if provenance == "unavailable":
            if raw_value is not None:
                raise KingNodeInputError(f"indices.{name}.value must be null when unavailable")
            timestamp = None
        else:
            raw = _finite_number(raw_value, f"indices.{name}.value", KingNodeInputError, minimum=0)
            timestamp = _iso_timestamp(item.get("timestamp"), f"indices.{name}.timestamp", KingNodeInputError)
            return cls(
                raw,
                provenance,
                timestamp,
                _string(item.get("methodology"), f"indices.{name}.methodology", KingNodeInputError),
                _string(item.get("quality"), f"indices.{name}.quality", KingNodeInputError),
            )
        return cls(
            None,
            provenance,
            timestamp,
            _string(item.get("methodology"), f"indices.{name}.methodology", KingNodeInputError),
            _string(item.get("quality"), f"indices.{name}.quality", KingNodeInputError),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "provenance": self.provenance,
            "timestamp": self.timestamp,
            "methodology": self.methodology,
            "quality": self.quality,
        }


@dataclass(frozen=True)
class NormalizedInput:
    """Validated pure-data input accepted by :func:`build_snapshot`."""

    as_of: str
    session_date: str
    underlying: Mapping[str, Any]
    expiration: Mapping[str, Any]
    option_rows: tuple[OptionRow, ...]
    indices: Mapping[str, IndexTerm]
    state: Mapping[str, Any]
    source: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": INPUT_SCHEMA_VERSION,
            "as_of": self.as_of,
            "session_date": self.session_date,
            "underlying": dict(self.underlying),
            "expiration": dict(self.expiration),
            "option_rows": [row.as_dict() for row in self.option_rows],
            "indices": {name: term.as_dict() for name, term in self.indices.items()},
            "state": dict(self.state),
            "source": dict(self.source),
        }


def validate_normalized_input(value: Any) -> NormalizedInput:
    """Validate a complete Theta-normalised input without performing I/O."""

    item = _mapping(value, "input", KingNodeInputError)
    if item.get("schema_version") != INPUT_SCHEMA_VERSION:
        raise KingNodeInputError(
            f"input.schema_version must be {INPUT_SCHEMA_VERSION!r}"
        )
    underlying_raw = _mapping(item.get("underlying"), "underlying", KingNodeInputError)
    symbol = _string(underlying_raw.get("symbol"), "underlying.symbol", KingNodeInputError).upper()
    root = _string(underlying_raw.get("root"), "underlying.root", KingNodeInputError).upper()
    underlying = {
        "symbol": symbol,
        "root": root,
        "spot": _finite_number(underlying_raw.get("spot"), "underlying.spot", KingNodeInputError, minimum=0.0000001),
        "previous_close": _finite_number(underlying_raw.get("previous_close"), "underlying.previous_close", KingNodeInputError, minimum=0.0000001),
        "timestamp": _iso_timestamp(underlying_raw.get("timestamp"), "underlying.timestamp", KingNodeInputError),
    }
    expiration_raw = _mapping(item.get("expiration"), "expiration", KingNodeInputError)
    expiration = {
        "expiry": _date(expiration_raw.get("expiry"), "expiration.expiry", KingNodeInputError),
        "time_to_expiry_years": _finite_number(
            expiration_raw.get("time_to_expiry_years"),
            "expiration.time_to_expiry_years",
            KingNodeInputError,
            minimum=0,
        ),
        "rate": _finite_number(expiration_raw.get("rate"), "expiration.rate", KingNodeInputError),
        "contract_multiplier": _finite_number(
            expiration_raw.get("contract_multiplier"),
            "expiration.contract_multiplier",
            KingNodeInputError,
            minimum=0.0000001,
        ),
    }
    raw_rows = item.get("option_rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise KingNodeInputError("option_rows must be a non-empty list")
    rows = tuple(OptionRow.from_mapping(row, index) for index, row in enumerate(raw_rows))
    for row in rows:
        if row.symbol != symbol or row.root != root:
            raise KingNodeInputError("each option row must match underlying.symbol and root")
        if row.expiry != expiration["expiry"]:
            raise KingNodeInputError("each option row must match expiration.expiry")
        if not math.isclose(row.time_to_expiry_years, expiration["time_to_expiry_years"], rel_tol=0.0, abs_tol=1e-12):
            raise KingNodeInputError("each option row must match expiration.time_to_expiry_years")
    indices_raw = _mapping(item.get("indices"), "indices", KingNodeInputError)
    missing_indices = [name for name in ("vix", "vvix", "vix1d") if name not in indices_raw]
    if missing_indices:
        raise KingNodeInputError("indices is missing: " + ", ".join(missing_indices))
    indices = {name: IndexTerm.from_mapping(indices_raw[name], name) for name in ("vix", "vvix", "vix1d")}
    state = _mapping(item.get("state", {}), "state", KingNodeInputError)
    source = _mapping(item.get("source", {}), "source", KingNodeInputError)
    return NormalizedInput(
        as_of=_iso_timestamp(item.get("as_of"), "as_of", KingNodeInputError),
        session_date=_date(item.get("session_date"), "session_date", KingNodeInputError),
        underlying=underlying,
        expiration=expiration,
        option_rows=rows,
        indices=indices,
        state=dict(state),
        source=dict(source),
    )


@dataclass(frozen=True)
class VerifiedReference:
    """Static Matrix and IV-regime values that passed the v2 integrity gate."""

    raw: Mapping[str, Any]
    matrix: Mapping[str, Mapping[str, Any]]
    iv_regime_map: Mapping[str, Mapping[str, Any]]
    checksum: str

    @property
    def authority(self) -> Mapping[str, Any]:
        return self.raw["authority"]


def validate_reference(value: Any) -> VerifiedReference:
    """Reject every non-v2, incomplete, or altered static reference export."""

    item = _mapping(value, "reference", KingNodeReferenceError)
    if item.get("schema_version") != REFERENCE_SCHEMA_VERSION:
        raise KingNodeReferenceError(
            f"reference.schema_version must be {REFERENCE_SCHEMA_VERSION!r}"
        )
    if item.get("status") != "verified":
        raise KingNodeReferenceError("reference.status must be verified")
    authority = _mapping(item.get("authority"), "reference.authority", KingNodeReferenceError)
    if authority.get("workbook_sha256") != WORKBOOK_SHA256:
        raise KingNodeReferenceError("reference workbook SHA256 does not match v2 authority")
    if authority.get("catalogue_sha256") != CATALOGUE_SHA256:
        raise KingNodeReferenceError("reference catalogue SHA256 does not match v2 authority")
    members = _mapping(authority.get("workbook_member_sha256"), "reference.authority.workbook_member_sha256", KingNodeReferenceError)
    required_members = {"xl/workbook.xml", "xl/worksheets/sheet5.xml", "xl/worksheets/sheet11.xml"}
    if not required_members.issubset(members):
        raise KingNodeReferenceError("reference is missing required workbook member hashes")
    matrix = _mapping(item.get("matrix"), "reference.matrix", KingNodeReferenceError)
    iv_map = _mapping(item.get("iv_regime_map"), "reference.iv_regime_map", KingNodeReferenceError)
    if not matrix or not iv_map:
        raise KingNodeReferenceError("reference Matrix and IV Regime Map must be non-empty")
    for key, entry in matrix.items():
        _string(key, "reference.matrix key", KingNodeReferenceError)
        _mapping(entry, f"reference.matrix[{key!r}]", KingNodeReferenceError)
    for key, entry in iv_map.items():
        _string(key, "reference.iv_regime_map key", KingNodeReferenceError)
        _mapping(entry, f"reference.iv_regime_map[{key!r}]", KingNodeReferenceError)
    integrity = _mapping(item.get("integrity"), "reference.integrity", KingNodeReferenceError)
    duplicates = integrity.get("duplicate_keys")
    if duplicates not in ([], (), None):
        raise KingNodeReferenceError("reference integrity reports duplicate keys")
    checksum = _string(item.get("canonical_checksum"), "reference.canonical_checksum", KingNodeReferenceError)
    actual = canonical_reference_checksum(item)
    if checksum != actual:
        raise KingNodeReferenceError("reference canonical checksum does not match payload")
    return VerifiedReference(
        raw=dict(item),
        matrix={str(key): dict(entry) for key, entry in matrix.items()},
        iv_regime_map={str(key): dict(entry) for key, entry in iv_map.items()},
        checksum=checksum,
    )


__all__ = [
    "ADVANCED_GREEKS",
    "CATALOGUE_SHA256",
    "FORMULA_CLASSIFICATIONS",
    "FormulaClassification",
    "GreekValue",
    "INPUT_SCHEMA_VERSION",
    "INDEX_PROVENANCE",
    "KingNodeContractError",
    "KingNodeInputError",
    "KingNodeReferenceError",
    "NormalizedInput",
    "OptionRow",
    "REFERENCE_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "STATE_SCHEMA_VERSION",
    "VerifiedReference",
    "WORKBOOK_SHA256",
    "canonical_json_bytes",
    "canonical_reference_checksum",
    "canonical_reference_payload",
    "sha256_json",
    "validate_normalized_input",
    "validate_reference",
]
