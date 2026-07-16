#!/usr/bin/env python3
"""Capture and seal one immutable official Cboe volatility-complex snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests


BASE_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices"
FILES = (
    "VIX1D_History.csv",
    "VIX9D_History.csv",
    "VIX_History.csv",
    "VIX3M_History.csv",
    "VIX6M_History.csv",
    "VIX1Y_History.csv",
    "VVIX_History.csv",
)
DEFAULT_OUTPUT = Path("D:/ThetaData/cboe_vol_complex_directional_v1_20260716")
REQUIRED_END_DATE = pd.Timestamp("2026-07-15")
REQUIRED_START_DATE = pd.Timestamp("2022-08-01")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def validate_payload(name: str, payload: bytes) -> dict:
    frame = pd.read_csv(BytesIO(payload))
    if "DATE" not in frame.columns:
        raise KeyError(f"{name}: DATE column missing")
    dates = pd.to_datetime(frame["DATE"], errors="coerce")
    if dates.isna().any() or dates.duplicated().any():
        raise AssertionError(f"{name}: invalid/duplicate dates")
    value_columns = [column for column in frame.columns if column != "DATE"]
    if not value_columns:
        raise AssertionError(f"{name}: no value columns")
    values = frame[value_columns].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(values).all().all() or not (values > 0.0).all().all():
        raise AssertionError(f"{name}: non-positive/non-finite values")
    if {"OPEN", "HIGH", "LOW", "CLOSE"}.issubset(values.columns):
        envelope = (
            (values["LOW"] <= values[["OPEN", "CLOSE"]].min(axis=1) + 1e-9)
            & (values["HIGH"] + 1e-9 >= values[["OPEN", "CLOSE"]].max(axis=1))
            & (values["HIGH"] >= values["LOW"])
        )
        if not envelope.all():
            raise AssertionError(f"{name}: OHLC envelope failure")
    if dates.min() > REQUIRED_START_DATE or dates.max() < REQUIRED_END_DATE:
        raise AssertionError(f"{name}: insufficient frozen date coverage {dates.min()}..{dates.max()}")
    return {
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "date_min": dates.min().strftime("%Y%m%d"),
        "date_max": dates.max().strftime("%Y%m%d"),
    }


def capture(output: Path, timeout_seconds: int = 60) -> dict:
    if output.exists():
        raise FileExistsError(f"immutable output already exists: {output}")
    captured: list[tuple[str, bytes, dict]] = []
    for name in FILES:
        url = f"{BASE_URL}/{name}"
        response = requests.get(url, timeout=timeout_seconds)
        if response.status_code != 200:
            raise AssertionError(f"{name}: HTTP {response.status_code}")
        payload = bytes(response.content)
        validation = validate_payload(name, payload)
        record = {
            "file": name,
            "url": url,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "etag": response.headers.get("etag"),
            "last_modified": response.headers.get("last-modified"),
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
            **validation,
        }
        captured.append((name, payload, record))
        print(json.dumps(record, sort_keys=True), flush=True)
    output.mkdir(parents=True, exist_ok=False)
    records: list[dict] = []
    for name, payload, record in captured:
        path = output / name
        path.write_bytes(payload)
        if sha256_file(path) != record["sha256"]:
            raise AssertionError(f"{name}: post-write hash mismatch")
        records.append(record)
    manifest = {
        "schema": "cboe_vol_complex_directional_v1_capture",
        "status": "PASS_CBOE_VOL_COMPLEX_CAPTURE",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "files": records,
        "required_start_date": REQUIRED_START_DATE.strftime("%Y%m%d"),
        "required_end_date": REQUIRED_END_DATE.strftime("%Y%m%d"),
        "outcome_free": True,
        "holdout_2026_outcomes_used": False,
        "production_modified": False,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    print(json.dumps({"manifest_sha256": sha256_file(manifest_path), **manifest}, indent=2), flush=True)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--timeout-seconds", type=int, default=60)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    capture(Path(args.output), args.timeout_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

