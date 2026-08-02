#!/usr/bin/env python3
"""Validate a published KING NODE snapshot without contacting providers."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SCHEMA = "king-node.v1"  # legacy fixture compatibility
V2_SCHEMA = "king-node.v2"
EXPECTED_STRIKES = 47
EXPECTED_INDEX_CONTRACT = {
    "vix": (
        "observed_from_option_feed",
        "thetadata_option_first_order_underlying_median",
        "VIX",
        1,
    ),
    "vix1d": (
        "reconstructed",
        "cboe_vix1d_reconstruction_from_spxw_nbbo",
        "SPXW",
        2,
    ),
    "vvix": (
        "reconstructed",
        "cboe_vvix_reconstruction_from_vix_nbbo",
        "VIX",
        2,
    ),
}


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _validate_term(name: str, term: Any, errors: list[str]) -> None:
    if not isinstance(term, dict):
        errors.append(f"{name} term diagnostics are missing")
        return
    for key in ("forward", "k0", "variance", "minutes"):
        if not _finite(term.get(key)) or float(term[key]) <= 0:
            errors.append(f"{name} term {key} is missing or invalid")
    strikes = term.get("included_strikes")
    if not isinstance(strikes, list) or len(strikes) < 3:
        errors.append(f"{name} term has insufficient included strikes")


def _contains_forbidden_public_value(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in {"path", "snapshot_path", "source_path", "exception", "traceback", "stack"}:
                return True
            if _contains_forbidden_public_value(item):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_forbidden_public_value(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return "file://" in lowered or "/home/" in lowered or "/etc/" in lowered
    return False


def _inspect_v2_snapshot(
    payload: dict[str, Any],
    *,
    max_age_seconds: int,
    now: datetime,
) -> dict[str, Any]:
    """Validate only an API-safe, sealed/live v2 artifact."""
    errors: list[str] = []
    warnings: list[str] = []
    status = payload.get("status")
    if status not in {"live", "last_completed_session"}:
        errors.append("v2 snapshot status is not deliverable")
    generated = _parse_utc(payload.get("generated_at"))
    age = None
    if generated is None:
        errors.append("generated_at is missing or invalid")
    else:
        age = max(0.0, (now - generated).total_seconds())
    session = payload.get("session")
    if not isinstance(session, dict) or not isinstance(session.get("trading_date"), str):
        errors.append("session metadata is missing")
    freshness = payload.get("freshness")
    if not isinstance(freshness, dict):
        errors.append("freshness metadata is missing")
    else:
        if freshness.get("stale") is True:
            errors.append("v2 snapshot is marked stale")
        if status == "live":
            limit = freshness.get("max_age_seconds", max_age_seconds)
            if not _finite(limit) or float(limit) <= 0:
                errors.append("live freshness limit is invalid")
            elif age is not None and age > min(float(limit), float(max_age_seconds)):
                errors.append("live snapshot exceeds freshness limit")
        elif freshness.get("kind") != "sealed_completed_session":
            errors.append("completed session is not sealed")
    quality = payload.get("quality")
    if not isinstance(quality, dict) or quality.get("valid") is not True:
        errors.append("quality.valid is not true")
    elif quality.get("errors"):
        errors.append("quality contains errors")
    for key in (
        "calculation_at",
        "publication_at",
        "provenance",
        "reference",
        "formula_coverage",
        "inputs",
        "rows",
        "totals",
        "regime",
        "levels",
        "monitor",
        "directions",
        "presentation",
    ):
        if key not in payload:
            errors.append(f"v2 snapshot is missing {key}")
    if not isinstance(payload.get("rows"), list) or not payload.get("rows"):
        errors.append("v2 snapshot has no rows")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("provider") != "ThetaData":
        errors.append("v2 provenance is not ThetaData")
    if isinstance(provenance, dict) and provenance.get("underlying") != "option_underlying_proxy":
        errors.append("v2 underlying provenance is not an option proxy")
    reference = payload.get("reference")
    if not isinstance(reference, dict) or reference.get("status") != "verified":
        errors.append("v2 reference is not verified")
    coverage = payload.get("formula_coverage")
    if not isinstance(coverage, dict) or coverage.get("status") != "verified":
        errors.append("v2 formula coverage is not verified")
    if _contains_forbidden_public_value(payload):
        errors.append("v2 snapshot contains forbidden path or exception metadata")
    return {
        "healthy": not errors,
        "schema_version": payload.get("schema_version"),
        "producer_status": status,
        "quality": quality.get("grade") if isinstance(quality, dict) else None,
        "generated_age_seconds": age,
        "strike_count": len(payload.get("rows", [])) if isinstance(payload.get("rows"), list) else 0,
        "reference_mode": "verified_v2",
        "errors": errors,
        "warnings": warnings,
    }


def inspect_snapshot(
    payload: Any,
    *,
    max_age_seconds: int,
    require_reference_export: bool = False,
    allow_missing_indices: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return an auditable health report for one parsed snapshot."""
    now = now or datetime.now(UTC)
    if isinstance(payload, dict) and payload.get("schema_version") == V2_SCHEMA:
        return _inspect_v2_snapshot(payload, max_age_seconds=max_age_seconds, now=now)
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return {
            "healthy": False,
            "errors": ["snapshot root must be an object"],
            "warnings": [],
        }
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        errors.append(f"schema_version must be {EXPECTED_SCHEMA}")
    if payload.get("status") == "error":
        detail = payload.get("quality", {}).get("errors", [])
        errors.append(f"producer status is error: {detail}")

    generated_at = _parse_utc(payload.get("generated_at"))
    generated_age: float | None = None
    if generated_at is None:
        errors.append("generated_at is missing or invalid")
    else:
        generated_age = max(0.0, (now - generated_at).total_seconds())
        if generated_age > max_age_seconds:
            errors.append(
                f"snapshot age {generated_age:.1f}s exceeds {max_age_seconds}s"
            )

    rows = payload.get("rows")
    if not isinstance(rows, list):
        errors.append("rows must be an array")
        rows = []
    if len(rows) != EXPECTED_STRIKES:
        errors.append(f"strike count is {len(rows)}, expected {EXPECTED_STRIKES}")

    quality = payload.get("quality")
    if not isinstance(quality, dict):
        quality = {}
        errors.append("quality must be an object")
    producer_errors = quality.get("errors")
    if isinstance(producer_errors, list) and producer_errors:
        errors.append(f"producer errors: {producer_errors}")
    producer_warnings = quality.get("warnings")
    if isinstance(producer_warnings, list):
        warnings.extend(str(item) for item in producer_warnings)

    delivery = payload.get("delivery")
    if isinstance(delivery, dict) and delivery.get("stale") is True:
        errors.append("web delivery marks the snapshot stale")

    source = payload.get("source")
    if not isinstance(source, dict):
        source = {}
        errors.append("source must be an object")
    tasty = source.get("tastytrade")
    if not isinstance(tasty, dict):
        errors.append("Tastytrade source metadata is missing")
    else:
        tasty_age = tasty.get("age_seconds")
        if not _finite(tasty_age):
            errors.append("Tastytrade age_seconds is missing or invalid")
        elif float(tasty_age) > max_age_seconds:
            errors.append(
                f"Tastytrade source age {float(tasty_age):.1f}s exceeds "
                f"{max_age_seconds}s"
            )

    indices = source.get("indices")
    if not isinstance(indices, dict):
        indices = {}
    for symbol, (expected_status, expected_method, input_symbol, expiration_count) in (
        EXPECTED_INDEX_CONTRACT.items()
    ):
        item = indices.get(symbol)
        item_errors: list[str] = []
        if not isinstance(item, dict):
            item_errors.append("metadata is missing")
        else:
            if item.get("status") != expected_status:
                item_errors.append(
                    f"status is {item.get('status')!r}, expected {expected_status!r}"
                )
            if not _finite(item.get("value")) or float(item.get("value", 0)) <= 0:
                item_errors.append("value is missing, non-finite or non-positive")
            if item.get("method") != expected_method:
                item_errors.append(
                    f"method is {item.get('method')!r}, expected {expected_method!r}"
                )
            if item.get("input_symbol") != input_symbol:
                item_errors.append(
                    f"input_symbol is {item.get('input_symbol')!r}, expected {input_symbol!r}"
                )
            if item.get("entitlement") != "options_standard":
                item_errors.append("entitlement is not options_standard")
            if item.get("direct_index_subscription") is not False:
                item_errors.append("direct_index_subscription must be false")
            age = item.get("age_seconds")
            if not _finite(age):
                item_errors.append("age_seconds is missing or invalid")
            else:
                item_limit = item.get("max_age_seconds", max_age_seconds)
                if not _finite(item_limit) or float(item_limit) <= 0:
                    item_limit = max_age_seconds
                if float(age) > float(item_limit):
                    item_errors.append(
                        f"age {float(age):.1f}s exceeds {float(item_limit):.1f}s"
                    )
            source_text = json.dumps(item, sort_keys=True).lower()
            if "/index/" in source_text or "index/snapshot" in source_text:
                item_errors.append("provenance contains a forbidden ThetaData index endpoint")
            expirations = item.get("expirations")
            if not isinstance(expirations, list) or len(expirations) < expiration_count:
                item_errors.append(
                    f"requires at least {expiration_count} expiration(s)"
                )
            if not _finite(item.get("quote_count")) or item.get("quote_count", 0) <= 0:
                item_errors.append("quote_count is missing or non-positive")
            if not _finite(item.get("valid_strike_count")) or item.get(
                "valid_strike_count", 0
            ) <= 0:
                item_errors.append("valid_strike_count is missing or non-positive")
            if symbol in {"vix1d", "vvix"}:
                rate = item.get("rate")
                if not isinstance(rate, dict) or not _finite(
                    rate.get("value_decimal")
                ):
                    item_errors.append("risk-free rate provenance is missing")
                diagnostics = item.get("diagnostics")
                if not isinstance(diagnostics, dict):
                    item_errors.append("reconstruction diagnostics are missing")
                else:
                    _validate_term(f"{symbol.upper()} near", diagnostics.get("near"), item_errors)
                    _validate_term(f"{symbol.upper()} next", diagnostics.get("next"), item_errors)

        if item_errors:
            message = f"{symbol.upper()} invalid: " + "; ".join(item_errors)
            if allow_missing_indices:
                warnings.append(message)
            else:
                errors.append(message)

    theta_options = source.get("theta_options")
    if isinstance(theta_options, dict):
        if theta_options.get("direct_index_subscription") is not False:
            errors.append("Theta options provenance does not explicitly disable index access")
        if theta_options.get("entitlement") not in {None, "options_standard"}:
            errors.append("Theta options provenance has an unexpected entitlement")

    regime = payload.get("regime")
    reference_mode = regime.get("reference_mode") if isinstance(regime, dict) else None
    if reference_mode != "workbook_static_export":
        message = (
            "Matrix/IV Regime reference uses semantic fallback instead of an "
            "audited workbook export"
        )
        if require_reference_export:
            errors.append(message)
        elif message not in warnings:
            warnings.append(message)

    return {
        "healthy": not errors,
        "schema_version": payload.get("schema_version"),
        "producer_status": payload.get("status"),
        "quality": quality.get("grade"),
        "generated_age_seconds": generated_age,
        "strike_count": len(rows),
        "reference_mode": reference_mode,
        "errors": errors,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path(
            os.getenv(
                "KING_NODE_SNAPSHOT",
                os.getenv(
                    "KING_NODE_OUTPUT",
                    PROJECT_ROOT / "runtime" / "king_node" / "latest.json",
                ),
            )
        ),
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=int(os.getenv("KING_NODE_WEB_MAX_AGE_SECONDS", "900")),
    )
    parser.add_argument("--require-reference-export", action="store_true")
    parser.add_argument(
        "--allow-missing-indices",
        action="store_true",
        help="Diagnostic only: warn instead of failing for missing VIX family",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_age <= 0:
        print("--max-age must be positive", file=sys.stderr)
        return 2
    try:
        payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        report = {
            "healthy": False,
            "errors": ["snapshot artifact is unreadable"],
            "warnings": [],
        }
    else:
        report = inspect_snapshot(
            payload,
            max_age_seconds=args.max_age,
            require_reference_export=args.require_reference_export,
            allow_missing_indices=args.allow_missing_indices,
        )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    else:
        label = "HEALTHY" if report["healthy"] else "UNHEALTHY"
        print(
            f"KING NODE {label} | snapshot={args.snapshot} | "
            f"strikes={report.get('strike_count', '—')} | "
            f"age={report.get('generated_age_seconds', '—')}"
        )
        for warning in report.get("warnings", []):
            print(f"WARNING: {warning}")
        for error in report.get("errors", []):
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
