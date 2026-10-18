"""Read-only static review of frozen oracle quote-quality controls."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compact_python(source: str) -> str:
    return re.sub(r"\s+", "", source.lower())


def classify(cache_source: str, engine_source: str, audit_source: str) -> dict:
    cache = compact_python(cache_source)
    engine = compact_python(engine_source)
    audit = compact_python(audit_source)
    basic = all(
        token in cache
        for token in ("np.isfinite(bid)", "np.isfinite(ask)", "(bid>=0)", "(ask>0)", "(bid<=ask)")
    ) and all(
        token in engine
        for token in ("np.isfinite(bid)", "np.isfinite(ask)", "(bid>=0)", "(ask>0)", "(bid<=ask)")
    )
    raw_fill = all(token in audit for token in ("raw_clock_and_fill_check", "validate_raw_ledger_fills"))
    paired_clock = all(token in audit for token in ("paired_clock_mismatch_rows", "native!=underlying"))
    spot_age = all(token in cache for token in ("ages>=0", "ages<=60000", "underlying_age_ms"))
    combined = cache + engine + audit
    return {
        "finite_nonnegative_noncrossed_bid_ask": basic,
        "selected_raw_fill_equality": raw_fill,
        "paired_stored_clock_comparison": paired_clock,
        "underlying_spot_age_0_to_60_seconds": spot_age,
        "option_intrinsic_value_check": any(token in combined for token in ("intrinsic", "spot-strike", "strike-spot")),
        "put_call_parity_check": any(token in combined for token in ("put_call_parity", "putcallparity", "parity_residual")),
        "option_quote_staleness_check": any(token in combined for token in ("option_quote_age", "max_quote_age", "stale_quote", "unchanged_quote_run")),
        "spread_width_check": any(token in combined for token in ("max_spread", "spread_ratio", "spread_width")),
        "cross_strike_or_calendar_arbitrage_check": any(token in combined for token in ("vertical_arbitrage", "calendar_arbitrage", "strike_monotonicity")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    base = Path(__file__).resolve().parent
    parser.add_argument("--cache-code", type=Path, default=base / "build_cache.py")
    parser.add_argument("--engine-code", type=Path, default=base / "level_engine.py")
    parser.add_argument("--audit-code", type=Path, default=base / "audit_engine.py")
    parser.add_argument("--protocol", type=Path, default=base / "PROTOCOL.md")
    parser.add_argument("--full-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    full = json.loads(args.full_audit.read_text(encoding="utf-8"))
    if full.get("status") != "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT":
        raise ValueError("Authoritative full oracle audit is not PASS")
    controls = classify(
        args.cache_code.read_text(encoding="utf-8"),
        args.engine_code.read_text(encoding="utf-8"),
        args.audit_code.read_text(encoding="utf-8"),
    )
    required_true = (
        "finite_nonnegative_noncrossed_bid_ask",
        "selected_raw_fill_equality",
        "paired_stored_clock_comparison",
        "underlying_spot_age_0_to_60_seconds",
    )
    if not all(controls[key] for key in required_true):
        raise AssertionError("Expected frozen basic control was not found")
    unsupported = (
        "option_intrinsic_value_check",
        "put_call_parity_check",
        "option_quote_staleness_check",
        "spread_width_check",
        "cross_strike_or_calendar_arbitrage_check",
    )
    if any(controls[key] for key in unsupported):
        raise AssertionError("Unexpected economic-plausibility control; requires manual review")

    paths = (args.cache_code, args.engine_code, args.audit_code, args.protocol, args.full_audit)
    result = {
        "status": "COMPLETE_READ_ONLY_ORACLE_QUOTE_QUALITY_CONTROL_REVIEW",
        "scope": "STATIC_CODE_AND_EXISTING_AUDIT_EVIDENCE_NO_NEW_RAW_VALUES",
        "files": {str(path.resolve()): sha256(path) for path in paths},
        "controls": controls,
        "interpretation": {
            "verified": "Structural validity, stored-clock identity/assumptions, underlying age, and selected raw fills.",
            "gap": "No option intrinsic, put-call parity, option staleness, spread-width, or surface-arbitrage control was part of the oracle admission/audit.",
            "effect": "The full audit proves faithful execution of the frozen rules; it does not prove that the clairvoyant oracle avoided economically anomalous option quotes.",
        },
        "no_trade_filter_added": True,
        "new_raw_values_read": False,
        "clock_proxy_assumptions_unchanged": True,
        "live_parity_verified": False,
        "technical_ready": False,
        "promotion_approved": False,
        "review_script_sha256": sha256(Path(__file__).resolve()),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()

