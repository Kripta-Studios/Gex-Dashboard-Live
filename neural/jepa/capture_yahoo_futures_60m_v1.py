#!/usr/bin/env python3
"""Capture the immutable Yahoo 60m continuous-futures source bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


SYMBOLS = ("ES=F", "NQ=F", "YM=F", "RTY=F", "ZN=F", "GC=F", "CL=F")
PERIOD1 = 1_721_174_400
PERIOD2 = 1_784_160_000
DEFAULT_OUTPUT = Path("D:/ThetaData/futures_yahoo_60m_20240717_20260715_v1")
BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def source_url(symbol: str) -> str:
    encoded = urllib.parse.quote(symbol, safe="")
    return (
        f"{BASE_URL}/{encoded}?period1={PERIOD1}&period2={PERIOD2}"
        "&interval=60m&includePrePost=true&events=div%2Csplits"
    )


def validate_payload(payload: bytes, symbol: str) -> dict:
    document = json.loads(payload)
    chart = document.get("chart", {})
    if chart.get("error") is not None:
        raise AssertionError(f"{symbol}: Yahoo chart error {chart['error']}")
    results = chart.get("result") or []
    if len(results) != 1:
        raise AssertionError(f"{symbol}: expected one chart result")
    result = results[0]
    meta = result.get("meta", {})
    if str(meta.get("symbol")) != symbol or str(meta.get("instrumentType")) != "FUTURE":
        raise AssertionError(f"{symbol}: unexpected metadata")
    timestamps = [int(value) for value in result.get("timestamp") or []]
    if len(timestamps) < 10_000 or timestamps != sorted(set(timestamps)):
        raise AssertionError(f"{symbol}: invalid timestamp coverage")
    outside = [value for value in timestamps if value < PERIOD1 or value >= PERIOD2]
    # Yahoo currently includes the bar starting exactly at the exclusive period2
    # boundary. Preserve the raw response for provenance, audit that one known row,
    # and require every downstream consumer to filter to the frozen half-open range.
    if outside not in ([], [PERIOD2]):
        raise AssertionError(f"{symbol}: unexpected timestamp outside frozen interval")
    frozen_indexes = [
        index for index, value in enumerate(timestamps) if PERIOD1 <= value < PERIOD2
    ]
    if len(frozen_indexes) < 10_000:
        raise AssertionError(f"{symbol}: insufficient frozen timestamp coverage")
    quote_list = result.get("indicators", {}).get("quote") or []
    if len(quote_list) != 1:
        raise AssertionError(f"{symbol}: expected one quote array")
    quote = quote_list[0]
    for column in ("open", "high", "low", "close", "volume"):
        if len(quote.get(column) or []) != len(timestamps):
            raise AssertionError(f"{symbol}: {column} length mismatch")
    complete = 0
    nonzero_volume = 0
    for index in frozen_indexes:
        values = [quote[column][index] for column in ("open", "high", "low", "close")]
        if any(value is None for value in values):
            continue
        open_, high, low, close = (float(value) for value in values)
        if not (low > 0.0 and low <= min(open_, close) and high >= max(open_, close)):
            raise AssertionError(f"{symbol}: OHLC envelope failure at {index}")
        complete += 1
        volume = quote["volume"][index]
        nonzero_volume += int(volume is not None and float(volume) > 0.0)
    if complete < 10_000 or nonzero_volume < 9_000:
        raise AssertionError(f"{symbol}: insufficient complete OHLCV")
    return {
        "symbol": symbol,
        "rows": len(timestamps),
        "frozen_rows": len(frozen_indexes),
        "outside_frozen_rows": len(outside),
        "outside_frozen_timestamps": outside,
        "complete_ohlc_rows": complete,
        "nonzero_volume_rows": nonzero_volume,
        "timestamp_min": min(timestamps),
        "timestamp_max": max(timestamps),
        "exchange_timezone": str(meta.get("exchangeTimezoneName")),
    }


def fetch(symbol: str, timeout: float) -> tuple[bytes, str]:
    url = source_url(symbol)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if int(response.status) != 200:
            raise AssertionError(f"{symbol}: HTTP {response.status}")
        return response.read(), url


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def capture(output: Path, timeout: float) -> dict:
    if output.exists():
        raise FileExistsError(f"immutable futures capture exists: {output}")
    staging = output.with_name(output.name + ".staging")
    if staging.exists():
        raise FileExistsError(f"stale futures capture staging exists: {staging}")
    staging.mkdir(parents=True, exist_ok=False)
    rows = []
    try:
        for symbol in SYMBOLS:
            payload, url = fetch(symbol, timeout)
            audit = validate_payload(payload, symbol)
            filename = symbol.replace("=", "_") + ".json"
            atomic_write(staging / "raw" / filename, payload)
            rows.append(
                {
                    **audit,
                    "url": url,
                    "filename": f"raw/{filename}",
                    "bytes": len(payload),
                    "sha256": sha256_bytes(payload),
                }
            )
        manifest = {
            "schema": "yahoo_futures_60m_capture_v1",
            "status": "PASS_YAHOO_FUTURES_CAPTURE",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "period1": PERIOD1,
            "period2": PERIOD2,
            "symbols": list(SYMBOLS),
            "sources": rows,
            "outcome_free": True,
            "production_modified": False,
        }
        payload = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False).encode("utf-8")
        atomic_write(staging / "manifest.json", payload)
        os.replace(staging, output)
        print(json.dumps(manifest, indent=2, sort_keys=True), flush=True)
        return manifest
    except Exception:
        # Preserve failed staging for audit; never reinterpret it as a valid capture.
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    capture(Path(args.output), float(args.timeout))
