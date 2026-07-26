#!/usr/bin/env python3
"""Probe KING NODE's ThetaData Options STANDARD volatility inputs."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.king_node_service import ThetaOptionsVolatilityClient  # noqa: E402

EXIT_OK = 0
EXIT_MARKET_CLOSED_OR_EMPTY = 10
EXIT_FORBIDDEN = 20
EXIT_INSUFFICIENT_CHAIN = 21
EXIT_RATE_UNAVAILABLE = 22
EXIT_CALCULATION_FAILED = 23


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:25503/v3"
    )
    parser.add_argument("--json", action="store_true")
    return parser


def classify(report: dict[str, Any]) -> int:
    errors = " ".join(
        str(item.get("error", ""))
        for item in report.get("indices", {}).values()
        if isinstance(item, dict)
    ).lower()
    if all(
        isinstance(item, dict) and item.get("status") in {
            "observed_from_option_feed", "reconstructed"
        }
        for item in report.get("indices", {}).values()
    ):
        return EXIT_OK
    if "403" in errors or "forbidden" in errors or "entitlement" in errors:
        return EXIT_FORBIDDEN
    if "rate" in errors or "sofr" in errors:
        return EXIT_RATE_UNAVAILABLE
    if "no fresh" in errors or "no same-day" in errors or "no strike" in errors:
        return EXIT_MARKET_CLOSED_OR_EMPTY
    if "valid strikes" in errors or "bracket" in errors or "wing" in errors:
        return EXIT_INSUFFICIENT_CHAIN
    return EXIT_CALCULATION_FAILED


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    now = datetime.now(UTC)
    client = ThetaOptionsVolatilityClient(args.base_url)
    try:
        indices, _, diagnostics = client.fetch_all(now=now, state={})
    finally:
        client.close()
    report = {
        "timestamp": now.isoformat(),
        "base_url": args.base_url,
        "entitlement": "options_standard",
        "direct_index_subscription": False,
        "indices": indices,
        "diagnostics": diagnostics,
    }
    code = classify(report)
    report["exit_code"] = code
    report["ok"] = code == EXIT_OK
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    else:
        print(f"ThetaData Options STANDARD probe exit={code}")
        for name in ("vix", "vix1d", "vvix"):
            item = indices.get(name, {})
            print(
                f"{name.upper()}: status={item.get('status')} "
                f"value={item.get('value')} error={item.get('error')}"
            )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
