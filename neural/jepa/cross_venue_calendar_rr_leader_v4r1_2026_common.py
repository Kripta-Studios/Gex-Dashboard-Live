"""Shared outcome-free contracts for the user-authorized V4R1 2026 retry."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from neural.jepa import build_cross_venue_calendar_rr_leader_v1 as v1_builder
from neural.jepa.build_calendar_risk_reversal_pressure_v1 import canonical_date


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPTIONS_ROOT = Path("D:/ThetaData/data_options")
UNDERLYING_ROOT = Path("D:/ThetaData/data_underlying_derived")
RETRY_ROOT = Path("D:/ThetaData/cross_venue_calendar_rr_v4r1_source_retry_2026")
RETRY_RESEAL_ROOT = Path(
    "D:/ThetaData/cross_venue_calendar_rr_v4r1_source_retry_2026_offline_reseal_v2"
)
ORIGINAL_RETRY_SEAL_SHA256 = (
    "a18e086444598bae6e7d380bc82479b9818550932883835c083778d5c66758f0"
)
PREDECLARATION = PROJECT_ROOT / (
    "research_papers/JEPA/"
    "CROSS_VENUE_CALENDAR_RR_LEADER_V4R1_2026_SOURCE_RETRY_EXCLUSION_"
    "PREDECLARATION.md"
)
PREDECLARATION_SHA256 = (
    "7c4c500111774e3d7e72af840ff2660ec77518ab9c9eb0623f128ebc21bcee6b"
)
FIXED_EXCLUSION_CONTRACT = PROJECT_ROOT / (
    "research_papers/JEPA/"
    "CROSS_VENUE_CALENDAR_RR_LEADER_V4R2_2026_OUTCOME_FREE_FIXED_"
    "EXCLUSIONS_PREDECLARATION.md"
)
FIXED_EXCLUSION_CONTRACT_SHA256 = (
    "bf2fed43b1d58bd8e9bc0ba4bb4ab4a26b92ae66f4b3ec7c4845f34d27260fbf"
)
REMOTE_BASE_URL = "http://91.99.90.39:25503/v3"
INTERVALS = ("1m", "30s", "5m")
ENDPOINTS = {
    "greeks": "/option/history/greeks/first_order",
    "iv": "/option/history/greeks/implied_volatility",
}
EXPECTED_DATES = 133
EXPECTED_SENSOR_SESSIONS = 266
EXPECTED_CAPTURES = 532
EXPECTED_MONTH_COUNTS = {
    "202601": 20,
    "202602": 19,
    "202603": 22,
    "202604": 18,
    "202605": 20,
    "202606": 21,
    "202607": 13,
}
DATE_SHA256 = "7fb305c4d6905393d4ab23fcc3518550cd1be1bbd0cb1686dd2f75a82f2921c3"
CAPTURE_ID_SHA256 = (
    "5b2fb9eede8a7c620419edc16cf4e2bfabb1a6a9a1a79be09db8662cb2b1f6b1"
)
RETRY_IDS = (
    "QQQ|20260624|front|20260624",
    "QQQ|20260626|front|20260626",
    "SPY|20260624|front|20260624",
    "SPY|20260625|front|20260625",
    "SPY|20260626|front|20260626",
)
FIXED_OUTCOME_FREE_EXCLUSIONS = (
    {
        "sensor_ticker": "QQQ",
        "trade_date": "20260310",
        "capture_id": "QQQ|20260310|session|feature_contract",
        "reason": "no persistent signable CALL 25-delta contract",
    },
    {
        "sensor_ticker": "SPY",
        "trade_date": "20260319",
        "capture_id": "SPY|20260319|session|feature_contract",
        "reason": "no persistent signable PUT 25-delta contract",
    },
    {
        "sensor_ticker": "QQQ",
        "trade_date": "20260630",
        "capture_id": "QQQ|20260630|back|20260702",
        "reason": "Greek/IV vintage ask values differ",
    },
    {
        "sensor_ticker": "QQQ",
        "trade_date": "20260722",
        "capture_id": "QQQ|20260722|front|20260722",
        "reason": "Greek/IV exact key sets differ: Greek-only 92",
    },
)
KEY_COLUMNS = (
    "symbol",
    "expiration",
    "trade_date",
    "underlying_timestamp",
    "strike",
    "right",
)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def parse_option_path(path: Path, kind: str) -> tuple[str, str]:
    parts = path.stem.split("_")
    if len(parts) < 4 or parts[-1] != kind:
        raise ValueError(f"unexpected V4R1 option filename: {path}")
    return canonical_date(parts[-2]), canonical_date(parts[-3])


def option_map(options_root: Path, ticker: str, kind: str) -> dict[tuple[str, str], Path]:
    output: dict[tuple[str, str], Path] = {}
    for path in sorted((options_root / ticker / kind / "2026").glob("*/*.parquet")):
        day, expiration = parse_option_path(path, kind)
        key = (day, expiration)
        if key in output:
            raise AssertionError(f"duplicate V4R1 option source: {ticker} {kind} {key}")
        output[key] = path
    return output


def discover_universe(options_root: Path = OPTIONS_ROOT) -> pd.DataFrame:
    ticker_rows: dict[str, list[dict[str, Any]]] = {}
    ticker_dates: dict[str, set[str]] = {}
    for ticker in ("QQQ", "SPY"):
        greeks = option_map(options_root, ticker, "greeks")
        iv = option_map(options_root, ticker, "iv")
        common = set(greeks).intersection(iv)
        rows: list[dict[str, Any]] = []
        for day in sorted({key[0] for key in common}):
            expirations = sorted(
                expiration
                for trade_date, expiration in common
                if trade_date == day and expiration >= day
            )
            if day not in expirations:
                continue
            future = [expiration for expiration in expirations if expiration > day]
            if not future:
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "trade_date": day,
                    "month": day[:6],
                    "front_expiration": day,
                    "back_expiration": future[0],
                    "front_greeks_path": str(greeks[(day, day)]),
                    "front_iv_path": str(iv[(day, day)]),
                    "back_greeks_path": str(greeks[(day, future[0])]),
                    "back_iv_path": str(iv[(day, future[0])]),
                }
            )
        ticker_rows[ticker] = rows
        ticker_dates[ticker] = {str(row["trade_date"]) for row in rows}
    common_dates = sorted(ticker_dates["QQQ"].intersection(ticker_dates["SPY"]))
    output = pd.DataFrame(
        [
            row
            for ticker in ("QQQ", "SPY")
            for row in ticker_rows[ticker]
            if str(row["trade_date"]) in common_dates
        ]
    ).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    capture_ids = []
    for row in output.itertuples(index=False):
        for role in ("front", "back"):
            capture_ids.append(
                f"{row.ticker}|{row.trade_date}|{role}|"
                f"{getattr(row, role + '_expiration')}"
            )
    date_payload = "".join(f"{day}\n" for day in common_dates).encode()
    capture_payload = "".join(f"{value}\n" for value in sorted(capture_ids)).encode()
    monthly = (
        pd.Series(common_dates, dtype=str).str[:6].value_counts().sort_index().to_dict()
    )
    if (
        len(common_dates) != EXPECTED_DATES
        or len(output) != EXPECTED_SENSOR_SESSIONS
        or len(capture_ids) != EXPECTED_CAPTURES
        or monthly != EXPECTED_MONTH_COUNTS
        or hashlib.sha256(date_payload).hexdigest() != DATE_SHA256
        or hashlib.sha256(capture_payload).hexdigest() != CAPTURE_ID_SHA256
        or output.duplicated(["ticker", "trade_date"]).any()
    ):
        raise AssertionError("V4R1 metadata universe changed")
    return output


def retry_specs(universe: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, str]] = []
    lookup = universe.set_index(["ticker", "trade_date"])
    for capture_id in RETRY_IDS:
        ticker, day, role, expiration = capture_id.split("|")
        row = lookup.loc[(ticker, day)]
        if str(row[f"{role}_expiration"]) != expiration:
            raise AssertionError(f"V4R1 retry identity changed: {capture_id}")
        records.append(
            {
                "capture_id": capture_id,
                "ticker": ticker,
                "trade_date": day,
                "role": role,
                "expiration": expiration,
                "vintage_greeks_path": str(row[f"{role}_greeks_path"]),
                "vintage_iv_path": str(row[f"{role}_iv_path"]),
            }
        )
    return pd.DataFrame(records)


def request_params(spec: dict[str, Any], interval: str) -> dict[str, str]:
    return {
        "symbol": str(spec["ticker"]),
        "expiration": str(spec["expiration"]),
        "date": str(spec["trade_date"]),
        "strike": "*",
        "right": "both",
        "format": "json",
        "interval": interval,
    }


def parse_response(raw: Any) -> Any:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("response", [])
    return []


def flatten_response(raw: Any) -> pd.DataFrame:
    items = parse_response(raw)
    if not isinstance(items, list):
        raise AssertionError("V4R1 response payload is not a list")
    rows: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict) and "contract" in item and "data" in item:
            contract = item["contract"]
            if not isinstance(contract, dict) or not isinstance(item["data"], list):
                raise AssertionError("V4R1 contract/data response is malformed")
            rows.extend(
                {**contract, **data}
                for data in item["data"]
                if isinstance(data, dict)
            )
        elif isinstance(item, dict):
            rows.append(item)
    if not rows:
        raise AssertionError("V4R1 response contains no rows")
    return pd.DataFrame(rows)


def normalize_response(
    raw: Any, spec: dict[str, Any], kind: str, interval: str
) -> pd.DataFrame:
    frame = flatten_response(raw).copy()
    if "underlying_timestamp" not in frame.columns and "timestamp" in frame.columns:
        frame["underlying_timestamp"] = frame["timestamp"]
    required = {"underlying_timestamp", "strike", "right", "bid", "ask"}
    required.add("delta" if kind == "greeks" else "bid_implied_vol")
    if kind == "iv":
        required.add("ask_implied_vol")
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError(f"V4R1 {kind} response lacks fields: {missing}")
    frame["symbol"] = str(spec["ticker"])
    frame["expiration"] = str(spec["expiration"])
    frame["trade_date"] = str(spec["trade_date"])
    frame["data_type"] = kind
    frame["interval_used"] = interval
    frame["right"] = (
        frame["right"].astype(str).str.upper().replace({"C": "CALL", "P": "PUT"})
    )
    frame["underlying_timestamp"] = pd.to_datetime(
        frame["underlying_timestamp"], errors="coerce"
    )
    numeric = ["strike", "bid", "ask"]
    numeric.extend(["delta"] if kind == "greeks" else ["bid_implied_vol", "ask_implied_vol"])
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if (
        frame.empty
        or frame[list(KEY_COLUMNS)].isna().any().any()
        or not frame["right"].isin(["CALL", "PUT"]).all()
        or not np.isfinite(frame[numeric].to_numpy(dtype=float)).all()
    ):
        raise AssertionError(f"V4R1 invalid normalized {kind} response")
    leading = [
        "symbol",
        "expiration",
        "trade_date",
        "data_type",
        "interval_used",
    ]
    return frame[leading + [column for column in frame.columns if column not in leading]]


def target_pair_gate(
    greeks_path: Path, iv_path: Path, spec: dict[str, Any]
) -> dict[str, Any]:
    greeks = read_vintage_values_compatible(
        greeks_path,
        kind="greeks",
        ticker=str(spec["ticker"]),
        trade_date=str(spec["trade_date"]),
        expiration=str(spec["expiration"]),
    )
    iv = read_vintage_values_compatible(
        iv_path,
        kind="iv",
        ticker=str(spec["ticker"]),
        trade_date=str(spec["trade_date"]),
        expiration=str(spec["expiration"]),
    )
    comparison = greeks.loc[:, v1_builder.KEY_COLUMNS].merge(
        iv.loc[:, v1_builder.KEY_COLUMNS],
        on=list(v1_builder.KEY_COLUMNS),
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    greek_only = int(comparison["_merge"].eq("left_only").sum())
    iv_only = int(comparison["_merge"].eq("right_only").sum())
    shared = int(comparison["_merge"].eq("both").sum())
    if greek_only or iv_only:
        return {
            "usable": False,
            "greek_rows": int(len(greeks)),
            "iv_rows": int(len(iv)),
            "shared_rows": shared,
            "greek_only_rows": greek_only,
            "iv_only_rows": iv_only,
            "reason": "GREEK_IV_KEY_SET_MISMATCH",
        }
    try:
        v1_builder.join_greeks_iv(greeks, iv)
    except Exception as error:  # noqa: BLE001 - persisted fail-closed reason
        return {
            "usable": False,
            "greek_rows": int(len(greeks)),
            "iv_rows": int(len(iv)),
            "shared_rows": shared,
            "greek_only_rows": 0,
            "iv_only_rows": 0,
            "reason": f"{type(error).__name__}: {error}",
        }
    return {
        "usable": True,
        "greek_rows": int(len(greeks)),
        "iv_rows": int(len(iv)),
        "shared_rows": shared,
        "greek_only_rows": 0,
        "iv_only_rows": 0,
        "reason": "",
    }


def read_vintage_values_compatible(
    path: str | Path,
    *,
    kind: str,
    ticker: str,
    trade_date: str,
    expiration: str,
) -> pd.DataFrame:
    """Read vintage strings or retry timestamp columns under one exact contract."""
    source = Path(path)
    schema = pq.read_schema(source)
    timestamp_type = schema.field("underlying_timestamp").type
    if not pa.types.is_timestamp(timestamp_type):
        return v1_builder._read_vintage_values(
            source,
            kind=kind,
            ticker=ticker,
            trade_date=trade_date,
            expiration=expiration,
        )
    value_columns = (
        v1_builder.GREEK_VALUE_COLUMNS
        if kind == "greeks"
        else v1_builder.IV_VALUE_COLUMNS
    )
    columns = [
        "symbol",
        "expiration",
        "trade_date",
        "underlying_timestamp",
        "strike",
        "right",
        *value_columns,
    ]
    missing = sorted(set(columns).difference(schema.names))
    if missing:
        raise KeyError(f"V4R1 retry {kind} source lacks fields: {missing}")
    output = pd.read_parquet(source, columns=columns).rename(
        columns={"underlying_timestamp": "timestamp"}
    )
    output["symbol"] = output["symbol"].astype(str).str.upper().str.strip()
    output["expiration"] = output["expiration"].map(canonical_date)
    output["trade_date"] = output["trade_date"].map(canonical_date)
    output["timestamp"] = pd.to_datetime(output["timestamp"], errors="coerce")
    output["right"] = v1_builder.normalize_right(output["right"])
    for column in ("strike", *value_columns):
        output[column] = pd.to_numeric(output[column], errors="coerce")
    expected_times = set(v1_builder.target_datetimes(trade_date))
    output = output.loc[output["timestamp"].isin(expected_times)].copy()
    numeric = output[["strike", *value_columns]].to_numpy(dtype=float)
    if (
        output.empty
        or output[list(v1_builder.KEY_COLUMNS)].isna().any().any()
        or not output["symbol"].eq(ticker).all()
        or not output["trade_date"].eq(trade_date).all()
        or not output["expiration"].eq(expiration).all()
        or set(output["timestamp"].unique()) != expected_times
        or not output["right"].isin(["CALL", "PUT"]).all()
        or not np.isfinite(numeric).all()
        or output.duplicated(list(v1_builder.KEY_COLUMNS)).any()
    ):
        raise AssertionError(f"invalid V4R1 retry {kind} target rows: {source}")
    return output.sort_values(
        list(v1_builder.KEY_COLUMNS), kind="stable"
    ).reset_index(drop=True)
