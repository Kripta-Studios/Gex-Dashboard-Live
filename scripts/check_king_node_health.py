#!/usr/bin/env python3
"""Validate the published KING NODE snapshot without contacting providers."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SCHEMA = "king-node.v1"
EXPECTED_STRIKES = 47
REQUIRED_INDICES = ("vix", "vvix", "vix1d")


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


def inspect_snapshot(
    payload: Any,
    *,
    max_age_seconds: int,
    require_reference_export: bool = False,
    allow_missing_indices: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return an auditable health report for one parsed snapshot."""

    errors: list[str] = []
    warnings: list[str] = []
    now = now or datetime.now(UTC)
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
    for symbol in REQUIRED_INDICES:
        item = indices.get(symbol)
        observed = (
            isinstance(item, dict)
            and item.get("status") == "observed"
            and _finite(item.get("value"))
        )
        if not observed:
            message = f"{symbol.upper()} is not an observed ThetaData value"
            if allow_missing_indices:
                warnings.append(message)
            else:
                errors.append(message)

    regime = payload.get("regime")
    reference_mode = (
        regime.get("reference_mode") if isinstance(regime, dict) else None
    )
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
    parser.add_argument(
        "--require-reference-export",
        action="store_true",
        help="Fail while Matrix/IV Regime maps use the semantic fallback",
    )
    parser.add_argument(
        "--allow-missing-indices",
        action="store_true",
        help="Diagnostic only: warn instead of failing for missing VIX family",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report")
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
            "snapshot": str(args.snapshot),
            "errors": [f"{type(exc).__name__}: {exc}"],
            "warnings": [],
        }
    else:
        report = inspect_snapshot(
            payload,
            max_age_seconds=args.max_age,
            require_reference_export=args.require_reference_export,
            allow_missing_indices=args.allow_missing_indices,
        )
        report["snapshot"] = str(args.snapshot)

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
