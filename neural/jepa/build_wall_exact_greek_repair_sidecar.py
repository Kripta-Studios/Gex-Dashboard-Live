"""Capture the frozen V1R2 exact-1s Greek repair sidecar without outcomes.

The scope is deliberately narrow: the positive-OI stored-Greek contract
intersection for QQQ/SPY on 2022-12-30.  One immutable raw response is retained
per contract.  Only the 48 predeclared decision timestamps are normalized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.build_wall_native_quote_sidecar import (  # noqa: E402
    canonical_json_bytes,
    local_terminal_process_evidence,
    sha256_bytes,
    sha256_file,
    unwrap_response,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402


ENDPOINT = "/option/history/greeks/first_order"
ENVIRONMENT_LOCK = PROJECT_ROOT / "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
PREDECLARATION = PROJECT_ROOT / "research_papers/JEPA/WALL_SURFACE_FLOW_V1R2_EXACT_SPOT_REPAIR_PREDECLARATION.md"
CANONICAL_MANIFEST_SHA256 = "5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88"
TARGET_DATE = "20221230"
TARGET_TICKERS = ("QQQ", "SPY")
EXPECTED_CONTRACTS_BY_TICKER = {"QQQ": 285, "SPY": 386}
EXPECTED_CONTRACTS = 671
EXPECTED_CONTRACT_KEY_SHA256 = "57c99891a37fcde939df4a88de7f45a7dffd5be544c8730046bae45e109846c0"
DECISION_TIMES = tuple(f"{minute // 60:02d}:{minute % 60:02d}:00" for minute in range(10 * 60 + 35, 14 * 60 + 31, 5))
EXPECTED_TIMESTAMPS = len(DECISION_TIMES)
SPOT_TOLERANCE_BPS = 0.001
BID_ASK_TOLERANCE = 1e-9
KEY_COLUMNS = ("symbol", "expiration", "trade_date", "timestamp", "strike", "right")
REQUIRED_RESPONSE_COLUMNS = (
    "symbol", "expiration", "strike", "right", "timestamp", "underlying_timestamp",
    "underlying_price", "implied_vol", "delta", "theta", "vega", "rho", "bid", "ask",
)
OPTIONAL_RESPONSE_COLUMNS = ("iv_error", "epsilon", "lambda")


def _day(value: Any) -> str:
    return "".join(ch for ch in str(value) if ch.isdigit())[:8]


def _right(value: Any, *, short: bool = False) -> str:
    normalized = str(value).strip().upper()
    mapping = {"C": "CALL", "CALL": "CALL", "P": "PUT", "PUT": "PUT"}
    if normalized not in mapping:
        raise ValueError(f"invalid option right: {value!r}")
    long_value = mapping[normalized]
    return long_value[0] if short else long_value


def decision_timestamps(day: str = TARGET_DATE) -> pd.DatetimeIndex:
    normalized = _day(day)
    if normalized != TARGET_DATE:
        raise AssertionError(f"exact Greek repair is frozen to {TARGET_DATE}")
    prefix = f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:]}"
    return pd.DatetimeIndex([pd.Timestamp(f"{prefix} {value}") for value in DECISION_TIMES])


def contract_key_hash(frame: pd.DataFrame) -> str:
    required = {"ticker", "trade_date", "strike", "right"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError(f"contract hash input missing columns: {missing}")
    ordered = frame.copy()
    ordered["ticker"] = ordered["ticker"].astype(str).str.upper()
    ordered["trade_date"] = ordered["trade_date"].map(_day)
    ordered["strike"] = pd.to_numeric(ordered["strike"], errors="coerce")
    ordered["right"] = ordered["right"].map(lambda value: _right(value, short=True))
    if ordered[["ticker", "trade_date", "strike", "right"]].isna().any().any():
        raise AssertionError("null/non-numeric contract key")
    ordered = ordered.sort_values(["ticker", "trade_date", "strike", "right"], kind="stable")
    payload = "".join(
        f"{row.ticker},{row.trade_date},{float(row.strike):.6f},{row.right}\n"
        for row in ordered[["ticker", "trade_date", "strike", "right"]].itertuples(index=False)
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalize_contract_keys(frame: pd.DataFrame, ticker: str, day: str, source: str) -> pd.DataFrame:
    required = {"strike", "right"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError(f"{source} missing contract columns: {missing}")
    out = frame.copy()
    if "symbol" in out:
        if not out["symbol"].astype(str).str.upper().eq(ticker).all():
            raise AssertionError(f"{source} symbol identity mismatch")
    if "expiration" in out:
        if not out["expiration"].map(_day).eq(day).all():
            raise AssertionError(f"{source} expiration identity mismatch")
    out["strike"] = pd.to_numeric(out["strike"], errors="coerce")
    out["right"] = out["right"].map(_right)
    if out[["strike", "right"]].isna().any().any() or not np.isfinite(out["strike"]).all():
        raise AssertionError(f"{source} has invalid contract keys")
    return out


def discover_contract_universe(
    manifest_path: str | Path,
    *,
    require_canonical_hash: bool = True,
    enforce_frozen: bool = True,
) -> pd.DataFrame:
    """Return only positive-OI contracts present in the stored Greek source."""
    manifest_path = Path(manifest_path)
    manifest_hash = sha256_file(manifest_path)
    if require_canonical_hash and manifest_hash != CANONICAL_MANIFEST_SHA256:
        raise AssertionError(f"canonical source manifest hash mismatch: {manifest_hash}")
    manifest = pd.read_csv(manifest_path, dtype=str)
    required = {
        "ticker", "trade_date", "expiration", "dte_days", "expiry_mode",
        "has_greeks", "has_oi", "has_underlying",
        "greeks_path", "oi_path", "underlying_path",
    }
    missing = sorted(required.difference(manifest.columns))
    if missing:
        raise KeyError(f"source manifest missing repair columns: {missing}")
    manifest["ticker"] = manifest["ticker"].astype(str).str.upper()
    manifest["trade_date"] = manifest["trade_date"].map(_day)
    manifest["expiration"] = manifest["expiration"].map(_day)
    dte = pd.to_numeric(manifest["dte_days"], errors="coerce")
    complete = pd.Series(True, index=manifest.index)
    for column in ("has_greeks", "has_oi", "has_underlying"):
        complete &= manifest[column].astype(str).str.strip().str.lower().isin({"true", "1"})
    target = manifest[
        manifest["ticker"].isin(TARGET_TICKERS)
        & manifest["trade_date"].eq(TARGET_DATE)
        & manifest["expiration"].eq(TARGET_DATE)
        & dte.eq(0)
        & manifest["expiry_mode"].astype(str).str.strip().str.lower().eq("zero_dte")
        & complete
    ].copy()
    if len(target) != 2 or target.duplicated(["ticker", "trade_date"]).any() or set(target["ticker"]) != set(TARGET_TICKERS):
        raise AssertionError("source manifest does not contain exactly the two frozen repair sessions")
    if not target["expiration"].eq(TARGET_DATE).all():
        raise AssertionError("repair requires expiration == trade_date")

    contracts: list[pd.DataFrame] = []
    for row in target.sort_values("ticker", kind="stable").itertuples(index=False):
        ticker = str(row.ticker)
        paths = {
            "greeks": Path(str(row.greeks_path)),
            "oi": Path(str(row.oi_path)),
            "underlying": Path(str(row.underlying_path)),
        }
        for label, path in paths.items():
            if not path.is_file():
                raise FileNotFoundError(f"missing {label} source: {path}")
        hashes_before = {label: sha256_file(path) for label, path in paths.items()}
        greek_columns = set(pq.ParquetFile(paths["greeks"]).schema_arrow.names)
        greek_read = [column for column in ("symbol", "expiration", "strike", "right") if column in greek_columns]
        greeks = _normalize_contract_keys(pd.read_parquet(paths["greeks"], columns=greek_read), ticker, TARGET_DATE, "Greeks")
        oi_columns = set(pq.ParquetFile(paths["oi"]).schema_arrow.names)
        oi_read = [column for column in ("symbol", "expiration", "strike", "right", "open_interest") if column in oi_columns]
        if "open_interest" not in oi_read:
            raise KeyError("OI source missing open_interest")
        oi = _normalize_contract_keys(pd.read_parquet(paths["oi"], columns=oi_read), ticker, TARGET_DATE, "OI")
        oi["open_interest"] = pd.to_numeric(oi["open_interest"], errors="coerce")
        oi = oi[np.isfinite(oi["open_interest"]) & oi["open_interest"].gt(0.0)].copy()
        oi = oi.groupby(["strike", "right"], observed=True, sort=True)["open_interest"].max().reset_index()
        greek_keys = greeks[["strike", "right"]].drop_duplicates()
        merged = greek_keys.merge(oi, on=["strike", "right"], how="inner", validate="one_to_one")
        if merged.empty:
            raise AssertionError(f"empty positive-OI/stored-Greek intersection: {ticker}")
        merged.insert(0, "ticker", ticker)
        merged.insert(1, "trade_date", TARGET_DATE)
        merged.insert(2, "expiration", TARGET_DATE)
        for label, path in paths.items():
            merged[f"{label}_path"] = str(path)
            merged[f"{label}_sha256"] = hashes_before[label]
            if sha256_file(path) != hashes_before[label]:
                raise AssertionError(f"{label} source changed while discovering contracts")
        merged["source_manifest_path"] = str(manifest_path)
        merged["source_manifest_sha256"] = manifest_hash
        contracts.append(merged)
    result = pd.concat(contracts, ignore_index=True).sort_values(
        ["ticker", "trade_date", "strike", "right"], kind="stable"
    ).reset_index(drop=True)
    if result.duplicated(["ticker", "trade_date", "strike", "right"]).any():
        raise AssertionError("duplicate frozen repair contracts")
    observed_hash = contract_key_hash(result)
    if enforce_frozen:
        counts = result.groupby("ticker", observed=True).size().astype(int).to_dict()
        if len(result) != EXPECTED_CONTRACTS or counts != EXPECTED_CONTRACTS_BY_TICKER or observed_hash != EXPECTED_CONTRACT_KEY_SHA256:
            raise AssertionError(
                f"frozen repair universe mismatch: rows={len(result)}/{EXPECTED_CONTRACTS} "
                f"counts={counts} hash={observed_hash}"
            )
    result.attrs["contract_key_sha256"] = observed_hash
    result.attrs["source_manifest_sha256"] = manifest_hash
    return result


def _flatten_first_order_response(raw: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in unwrap_response(raw):
        if not isinstance(item, dict):
            raise ValueError("first-order response item is not an object")
        if "contract" in item and "data" in item:
            if not isinstance(item["contract"], dict) or not isinstance(item["data"], list):
                raise ValueError("invalid contract/data first-order response")
            rows.extend({**item["contract"], **point} for point in item["data"] if isinstance(point, dict))
        else:
            rows.append(item)
    return pd.DataFrame(rows)


def normalize_exact_greeks(raw: Any, *, ticker: str, trade_date: str, strike: float, right: str) -> pd.DataFrame:
    ticker = str(ticker).upper()
    day = _day(trade_date)
    long_right = _right(right)
    if ticker not in TARGET_TICKERS or day != TARGET_DATE:
        raise AssertionError("exact Greek normalization is outside frozen QQQ/SPY 2022-12-30 scope")
    frame = _flatten_first_order_response(raw)
    missing = sorted(set(REQUIRED_RESPONSE_COLUMNS).difference(frame.columns))
    if missing:
        raise KeyError(f"first-order response missing columns: {missing}")
    columns = list(REQUIRED_RESPONSE_COLUMNS) + [column for column in OPTIONAL_RESPONSE_COLUMNS if column in frame]
    out = frame.loc[:, columns].copy()
    out.insert(2, "trade_date", day)
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out["expiration"] = out["expiration"].map(_day)
    out["right"] = out["right"].map(_right)
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    out["underlying_timestamp"] = pd.to_datetime(out["underlying_timestamp"], errors="coerce")
    numeric_columns = [
        "strike", "underlying_price", "implied_vol", "delta", "theta", "vega", "rho", "bid", "ask",
        *[column for column in OPTIONAL_RESPONSE_COLUMNS if column in out],
    ]
    for column in numeric_columns:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if out.empty or out[["symbol", "expiration", "right", "timestamp", "underlying_timestamp"]].isna().any().any():
        raise AssertionError("first-order response is empty or has invalid identity/timestamps")
    if (
        not out["symbol"].eq(ticker).all()
        or not out["expiration"].eq(day).all()
        or not out["right"].eq(long_right).all()
        or not np.isclose(out["strike"].to_numpy(float), float(strike), rtol=0.0, atol=1e-9).all()
    ):
        raise AssertionError("first-order response violates requested contract identity")
    if not out["timestamp"].eq(out["underlying_timestamp"]).all():
        raise AssertionError("exact first-order timestamp differs from underlying_timestamp")
    if not out["timestamp"].dt.strftime("%Y%m%d").eq(day).all():
        raise AssertionError("first-order response contains a timestamp outside the requested date")
    if out.duplicated(list(KEY_COLUMNS)).any() or not out["timestamp"].is_monotonic_increasing:
        raise AssertionError("first-order response contains duplicate/non-monotonic native keys")
    expected = decision_timestamps(day)
    exact = out[out["timestamp"].isin(expected)].copy()
    if len(exact) != EXPECTED_TIMESTAMPS or exact["timestamp"].nunique() != EXPECTED_TIMESTAMPS:
        missing_times = [value.isoformat() for value in expected.difference(pd.DatetimeIndex(exact["timestamp"]))]
        raise AssertionError(
            f"exact decision coverage differs from {EXPECTED_TIMESTAMPS}: rows={len(exact)} missing={missing_times[:5]}"
        )
    if exact.duplicated(list(KEY_COLUMNS)).any() or set(exact["timestamp"]) != set(expected):
        raise AssertionError("duplicate or unexpected exact decision keys")
    numeric = exact[numeric_columns].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise AssertionError("exact Greek rows contain non-finite values")
    if (
        not exact["strike"].gt(0.0).all()
        or not exact["underlying_price"].gt(0.0).all()
        or exact[["implied_vol", "bid", "ask"]].lt(0.0).any().any()
    ):
        raise AssertionError("exact Greek rows contain invalid price/IV values")
    return exact.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)


def validate_exact_rows_against_sources(
    exact: pd.DataFrame,
    *,
    greeks_path: str | Path,
    underlying_path: str | Path,
    bid_ask_tolerance: float = BID_ASK_TOLERANCE,
    spot_tolerance_bps: float = SPOT_TOLERANCE_BPS,
) -> dict[str, Any]:
    """Hard-check exact spot and bid/ask against frozen source artifacts."""
    ticker = str(exact["symbol"].iloc[0])
    day = str(exact["trade_date"].iloc[0])
    strike = float(exact["strike"].iloc[0])
    right = str(exact["right"].iloc[0])
    greek_path = Path(greeks_path)
    underlying_path = Path(underlying_path)
    hashes_before = {"greeks": sha256_file(greek_path), "underlying": sha256_file(underlying_path)}

    available = set(pq.ParquetFile(greek_path).schema_arrow.names)
    clock = "timestamp" if "timestamp" in available else "underlying_timestamp"
    required = {"symbol", "expiration", "strike", "right", clock, "bid", "ask"}
    missing = sorted(required.difference(available))
    if missing:
        raise KeyError(f"stored Greek source missing validation columns: {missing}")
    old = pd.read_parquet(greek_path, columns=sorted(required))
    old["symbol"] = old["symbol"].astype(str).str.upper()
    old["expiration"] = old["expiration"].map(_day)
    old["strike"] = pd.to_numeric(old["strike"], errors="coerce")
    old["right"] = old["right"].map(_right)
    old["timestamp"] = pd.to_datetime(old[clock], errors="coerce")
    old["bid"] = pd.to_numeric(old["bid"], errors="coerce")
    old["ask"] = pd.to_numeric(old["ask"], errors="coerce")
    old = old[
        old["symbol"].eq(ticker) & old["expiration"].eq(day) & old["right"].eq(right)
        & np.isclose(old["strike"].to_numpy(float), strike, rtol=0.0, atol=1e-9)
        & old["timestamp"].isin(decision_timestamps(day))
    ].copy()
    if len(old) != EXPECTED_TIMESTAMPS or old["timestamp"].nunique() != EXPECTED_TIMESTAMPS:
        raise AssertionError("stored Greek lacks exact 48-row bid/ask coverage")
    if old.duplicated("timestamp").any() or old[["bid", "ask"]].isna().any().any():
        raise AssertionError("stored Greek validation rows are duplicated or non-numeric")
    quote_check = exact[["timestamp", "bid", "ask"]].merge(
        old[["timestamp", "bid", "ask"]], on="timestamp", how="inner", validate="one_to_one", suffixes=("_exact", "_stored")
    )
    bid_diff = (quote_check["bid_exact"] - quote_check["bid_stored"]).abs()
    ask_diff = (quote_check["ask_exact"] - quote_check["ask_stored"]).abs()
    if not bid_diff.le(bid_ask_tolerance).all() or not ask_diff.le(bid_ask_tolerance).all():
        raise AssertionError(
            f"exact first-order bid/ask differs from frozen Greek: bid_max={bid_diff.max()} ask_max={ask_diff.max()}"
        )

    underlying = pd.read_parquet(underlying_path)
    required_underlying = {"symbol", "date", "timestamp", "open"}
    missing_underlying = sorted(required_underlying.difference(underlying.columns))
    if missing_underlying:
        raise KeyError(f"derived underlying missing columns: {missing_underlying}")
    underlying["symbol"] = underlying["symbol"].astype(str).str.upper()
    underlying["date"] = underlying["date"].map(_day)
    underlying["timestamp"] = pd.to_datetime(underlying["timestamp"], errors="coerce")
    underlying["open"] = pd.to_numeric(underlying["open"], errors="coerce")
    underlying = underlying[
        underlying["symbol"].eq(ticker) & underlying["date"].eq(day)
        & underlying["timestamp"].isin(decision_timestamps(day))
    ][["timestamp", "open"]].copy()
    if len(underlying) != EXPECTED_TIMESTAMPS or underlying["timestamp"].nunique() != EXPECTED_TIMESTAMPS:
        raise AssertionError("derived underlying lacks exact 48-row open coverage")
    if underlying.duplicated("timestamp").any() or underlying["open"].isna().any() or not underlying["open"].gt(0.0).all():
        raise AssertionError("derived underlying validation rows are duplicated or invalid")
    spot_check = exact[["timestamp", "underlying_price"]].merge(
        underlying, on="timestamp", how="inner", validate="one_to_one"
    )
    spot_diff_bps = (spot_check["underlying_price"] - spot_check["open"]).abs().div(spot_check["open"]).mul(1e4)
    if not spot_diff_bps.le(spot_tolerance_bps).all():
        raise AssertionError(f"exact first-order spot differs from derived open(t): max_bps={spot_diff_bps.max()}")
    if sha256_file(greek_path) != hashes_before["greeks"] or sha256_file(underlying_path) != hashes_before["underlying"]:
        raise AssertionError("frozen source changed during exact-Greek validation")
    return {
        "greeks_sha256": hashes_before["greeks"],
        "underlying_sha256": hashes_before["underlying"],
        "stored_greek_clock_source": clock,
        "exact_timestamp_rows": EXPECTED_TIMESTAMPS,
        "stored_bid_ask_exact": True,
        "max_bid_abs_difference": float(bid_diff.max()),
        "max_ask_abs_difference": float(ask_diff.max()),
        "max_spot_difference_bps": float(spot_diff_bps.max()),
    }


def assert_positive_oi_membership(
    *, ticker: str, trade_date: str, strike: float, right: str, oi_path: str | Path
) -> str:
    """Prove a requested contract belongs to the frozen positive-OI source set."""
    ticker = str(ticker).upper()
    day = _day(trade_date)
    path = Path(oi_path)
    digest_before = sha256_file(path)
    available = set(pq.ParquetFile(path).schema_arrow.names)
    columns = [column for column in ("symbol", "expiration", "strike", "right", "open_interest") if column in available]
    if "open_interest" not in columns:
        raise KeyError("OI source missing open_interest membership column")
    oi = _normalize_contract_keys(pd.read_parquet(path, columns=columns), ticker, day, "OI")
    oi["open_interest"] = pd.to_numeric(oi["open_interest"], errors="coerce")
    selected = oi[
        oi["right"].eq(_right(right))
        & np.isclose(oi["strike"].to_numpy(float), float(strike), rtol=0.0, atol=1e-9)
        & np.isfinite(oi["open_interest"])
        & oi["open_interest"].gt(0.0)
    ]
    if selected.empty:
        raise AssertionError("contract is absent from the stored strictly-positive-OI universe")
    if sha256_file(path) != digest_before:
        raise AssertionError("OI source changed during contract-membership validation")
    return digest_before


def validate_process_evidence(manifest: dict[str, Any]) -> None:
    evidence = manifest.get("terminal_process_evidence")
    if not isinstance(evidence, dict):
        raise AssertionError("missing active Terminal process evidence")
    required = {
        "process_id", "command_line", "executable_path", "executable_sha256",
        "local_address", "local_port", "terminal_jar_path", "terminal_jar_sha256",
    }
    missing = sorted(required.difference(evidence))
    if missing:
        raise AssertionError(f"incomplete active Terminal process evidence: {missing}")
    for field in ("executable_sha256", "terminal_jar_sha256"):
        value = str(evidence[field]).lower()
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise AssertionError(f"invalid process-evidence hash: {field}")
    if str(evidence["terminal_jar_sha256"]) != str(manifest["terminal_jar_sha256"]):
        raise AssertionError("process-evidence JAR hash differs from contract manifest")
    if int(evidence["process_id"]) <= 0 or int(evidence["local_port"]) <= 0:
        raise AssertionError("invalid process id or local port in Terminal evidence")


def contract_directory(root: str | Path, ticker: str, day: str, strike: float, right: str) -> Path:
    strike_token = f"{float(strike):.6f}".replace(".", "p")
    return Path(root) / str(ticker).upper() / _day(day) / f"{_right(right, short=True)}_{strike_token}"


def download_contract(
    *,
    ticker: str,
    trade_date: str,
    strike: float,
    right: str,
    greeks_path: str | Path,
    oi_path: str | Path,
    underlying_path: str | Path,
    source_manifest_path: str | Path,
    output_root: str | Path,
    base_url: str,
    terminal_jar: str | Path,
    timeout: float = 300.0,
    requester: Callable[..., Any] = requests.get,
    process_evidence_provider: Callable[[str, str | Path], dict[str, Any]] = local_terminal_process_evidence,
) -> dict[str, Any]:
    ticker = str(ticker).upper()
    day = _day(trade_date)
    long_right = _right(right)
    host = (urlparse(base_url).hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise AssertionError("authoritative exact-Greek capture requires a local frozen Theta Terminal")
    if ticker not in TARGET_TICKERS or day != TARGET_DATE:
        raise AssertionError("contract is outside the frozen exact-Greek repair scope")
    jar_path = Path(terminal_jar).resolve()
    if not jar_path.is_file():
        raise FileNotFoundError(f"Theta Terminal JAR not found: {jar_path}")
    source_paths = {
        "greeks": Path(greeks_path), "oi": Path(oi_path), "underlying": Path(underlying_path),
        "source_manifest": Path(source_manifest_path),
    }
    source_hashes = {name: sha256_file(path) for name, path in source_paths.items()}
    oi_membership_hash = assert_positive_oi_membership(
        ticker=ticker, trade_date=day, strike=strike, right=long_right, oi_path=oi_path
    )
    if oi_membership_hash != source_hashes["oi"]:
        raise AssertionError("OI source changed before exact-Greek request")
    process_evidence = process_evidence_provider(base_url, jar_path)
    jar_hash = sha256_file(jar_path)
    if str(process_evidence.get("terminal_jar_sha256", "")) != jar_hash:
        raise AssertionError("active Terminal process evidence does not match supplied JAR")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    build_commit = current_git_commit()
    params = {
        "symbol": ticker, "expiration": day, "strike": f"{float(strike):.6f}".rstrip("0").rstrip("."),
        "right": _right(long_right, short=True), "date": day, "interval": "1s", "format": "json",
    }
    headers = {"Accept-Encoding": "identity"}
    response = requester(f"{base_url.rstrip('/')}{ENDPOINT}", params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    raw_bytes = bytes(response.content)
    if not raw_bytes:
        raise AssertionError("ThetaData returned an empty exact-Greek response")
    exact = normalize_exact_greeks(json.loads(raw_bytes), ticker=ticker, trade_date=day, strike=strike, right=long_right)
    audit = validate_exact_rows_against_sources(
        exact, greeks_path=greeks_path, underlying_path=underlying_path
    )
    for name, path in source_paths.items():
        if sha256_file(path) != source_hashes[name]:
            raise AssertionError(f"{name} source changed during exact-Greek capture")

    final_dir = contract_directory(output_root, ticker, day, strike, long_right)
    staging_dir = final_dir.with_name(f"{final_dir.name}.staging")
    if final_dir.exists() or staging_dir.exists():
        raise FileExistsError(f"immutable exact-Greek contract already exists: {final_dir}")
    staging_dir.mkdir(parents=True, exist_ok=False)
    raw_path = staging_dir / "first_order_response.json"
    parquet_path = staging_dir / "exact_greeks.parquet"
    manifest_path = staging_dir / "manifest.json"
    raw_path.write_bytes(raw_bytes)
    exact.to_parquet(parquet_path, index=False)
    manifest = {
        "schema_version": 1,
        "schema": "wall_exact_greek_repair_contract_v1r2",
        "outcome_free": True,
        "holdout_2026_used": False,
        "ticker": ticker,
        "trade_date": day,
        "expiration": day,
        "strike": float(strike),
        "right": long_right,
        "endpoint": ENDPOINT,
        "base_url": base_url.rstrip("/"),
        "request_params": params,
        "request_headers": headers,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "http_status": int(getattr(response, "status_code", 200)),
        "response_headers": dict(sorted((str(k), str(v)) for k, v in getattr(response, "headers", {}).items())),
        "terminal_jar_path": str(jar_path),
        "terminal_jar_sha256": jar_hash,
        "terminal_process_evidence": process_evidence,
        "git_commit": build_commit,
        "builder_sha256": sha256_file(__file__),
        "predeclaration_path": str(PREDECLARATION),
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "raw_response_sha256": sha256_bytes(raw_bytes),
        "exact_greeks_sha256": sha256_file(parquet_path),
        "rows": int(len(exact)),
        "columns": list(exact.columns),
        **{f"source_{name}_path": str(path) for name, path in source_paths.items()},
        **{f"source_{name}_sha256": digest for name, digest in source_hashes.items()},
        **audit,
    }
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    staging_dir.rename(final_dir)
    return manifest


def validate_contract(
    contract_dir: str | Path,
    *,
    greeks_path: str | Path,
    oi_path: str | Path,
    underlying_path: str | Path,
    source_manifest_path: str | Path,
) -> dict[str, Any]:
    root = Path(contract_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("outcome_free") is not True or manifest.get("holdout_2026_used") is not False:
        raise AssertionError("invalid exact-Greek sidecar scope/provenance flags")
    if manifest.get("ticker") not in TARGET_TICKERS or _day(manifest.get("trade_date")) != TARGET_DATE:
        raise AssertionError("exact-Greek sidecar is outside frozen scope")
    if len(str(manifest.get("git_commit", ""))) != 40:
        raise AssertionError("exact-Greek sidecar is missing its build commit")
    if str(manifest.get("builder_sha256", "")) != sha256_file(__file__):
        raise AssertionError("exact-Greek sidecar builder hash mismatch")
    raw_path = root / "first_order_response.json"
    parquet_path = root / "exact_greeks.parquet"
    raw_bytes = raw_path.read_bytes()
    if sha256_bytes(raw_bytes) != manifest["raw_response_sha256"] or sha256_file(parquet_path) != manifest["exact_greeks_sha256"]:
        raise AssertionError("immutable exact-Greek sidecar hash mismatch")
    exact = normalize_exact_greeks(
        json.loads(raw_bytes), ticker=manifest["ticker"], trade_date=manifest["trade_date"],
        strike=float(manifest["strike"]), right=manifest["right"],
    )
    stored = pd.read_parquet(parquet_path)
    pd.testing.assert_frame_equal(stored, exact, check_dtype=True)
    expected_sources = {
        "greeks": Path(greeks_path), "oi": Path(oi_path), "underlying": Path(underlying_path),
        "source_manifest": Path(source_manifest_path),
    }
    for name, path in expected_sources.items():
        if str(Path(manifest[f"source_{name}_path"]).resolve()) != str(path.resolve()):
            raise AssertionError(f"{name} source path substitution")
        if sha256_file(path) != manifest[f"source_{name}_sha256"]:
            raise AssertionError(f"{name} source hash mismatch")
    assert_positive_oi_membership(
        ticker=manifest["ticker"], trade_date=manifest["trade_date"], strike=float(manifest["strike"]),
        right=manifest["right"], oi_path=oi_path,
    )
    audit = validate_exact_rows_against_sources(exact, greeks_path=greeks_path, underlying_path=underlying_path)
    if sha256_file(manifest["terminal_jar_path"]) != manifest["terminal_jar_sha256"]:
        raise AssertionError("Theta Terminal JAR hash mismatch")
    validate_process_evidence(manifest)
    if sha256_file(PREDECLARATION) != manifest["predeclaration_sha256"]:
        raise AssertionError("exact-spot repair predeclaration hash mismatch")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    if runtime["lock_sha256"] != manifest["runtime_lock_sha256"] or runtime["environment_sha256"] != manifest["runtime_environment_sha256"]:
        raise AssertionError("exact-Greek runtime provenance mismatch")
    result = dict(manifest)
    result.update(audit)
    return result


def current_git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def assert_committed_builder() -> str:
    relatives = (
        "neural/jepa/build_wall_exact_greek_repair_sidecar.py",
        "neural/jepa/build_wall_native_quote_sidecar.py",
        "neural/jepa/wall_surface_flow_environment.py",
        "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
        "research_papers/JEPA/WALL_SURFACE_FLOW_V1R2_EXACT_SPOT_REPAIR_PREDECLARATION.md",
    )
    for relative in relatives:
        subprocess.run(["git", "ls-files", "--error-unmatch", relative], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True)
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", relative], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
        if dirty:
            raise AssertionError(f"exact-Greek backfill requires committed clean code: {relative}: {dirty}")
    return current_git_commit()


def _record_from_manifest(manifest: dict[str, Any], contract_dir: Path) -> dict[str, Any]:
    manifest_path = contract_dir / "manifest.json"
    return {
        "ticker": manifest["ticker"], "trade_date": manifest["trade_date"], "strike": float(manifest["strike"]),
        "right": manifest["right"], "contract_dir": str(contract_dir),
        "exact_greeks_path": str(contract_dir / "exact_greeks.parquet"),
        "exact_greeks_sha256": manifest["exact_greeks_sha256"],
        "raw_response_path": str(contract_dir / "first_order_response.json"),
        "raw_response_sha256": manifest["raw_response_sha256"],
        "contract_manifest_path": str(manifest_path), "contract_manifest_sha256": sha256_file(manifest_path),
        "rows": int(manifest["rows"]), "stored_bid_ask_exact": bool(manifest["stored_bid_ask_exact"]),
        "git_commit": str(manifest["git_commit"]),
        "max_spot_difference_bps": float(manifest["max_spot_difference_bps"]),
        "source_greeks_sha256": manifest["source_greeks_sha256"],
        "source_oi_sha256": manifest["source_oi_sha256"],
        "source_underlying_sha256": manifest["source_underlying_sha256"],
        "terminal_jar_sha256": manifest["terminal_jar_sha256"],
        "terminal_process_id": int(manifest["terminal_process_evidence"]["process_id"]),
        "java_executable_sha256": manifest["terminal_process_evidence"]["executable_sha256"],
    }


def backfill_exact_greeks(
    *, manifest_path: str | Path, output_root: str | Path, base_url: str, terminal_jar: str | Path,
    workers: int = 1, timeout: float = 300.0,
) -> dict[str, Any]:
    if not 1 <= int(workers) <= 4:
        raise ValueError("exact-Greek backfill workers must be within 1..4")
    commit = assert_committed_builder()
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    universe = discover_contract_universe(manifest_path)
    universe_hash = contract_key_hash(universe)
    root = Path(output_root)
    seal = root / "_seal"
    seal_staging = root / "_seal.staging"
    if seal.exists() or seal_staging.exists():
        raise FileExistsError(f"immutable exact-Greek seal already exists: {seal}")
    jar_path = Path(terminal_jar).resolve()
    jar_hash_before = sha256_file(jar_path)

    def one(row: dict[str, Any]) -> dict[str, Any]:
        directory = contract_directory(root, row["ticker"], row["trade_date"], row["strike"], row["right"])
        kwargs = {
            "greeks_path": row["greeks_path"], "oi_path": row["oi_path"],
            "underlying_path": row["underlying_path"], "source_manifest_path": manifest_path,
        }
        if directory.exists():
            result = validate_contract(directory, **kwargs)
        else:
            result = download_contract(
                ticker=row["ticker"], trade_date=row["trade_date"], strike=row["strike"], right=row["right"],
                output_root=root, base_url=base_url, terminal_jar=jar_path, timeout=timeout, **kwargs,
            )
        return _record_from_manifest(result, directory)

    records = universe.to_dict("records")
    completed: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=int(workers)) as pool:
        futures = {pool.submit(one, row): row for row in records}
        for index, future in enumerate(as_completed(futures), start=1):
            row = futures[future]
            try:
                completed.append(future.result())
            except Exception as exc:
                errors.append({
                    "ticker": str(row["ticker"]), "strike": str(row["strike"]), "right": str(row["right"]),
                    "error": f"{type(exc).__name__}: {exc}",
                })
            if index % 25 == 0 or index == len(futures):
                print(f"[EXACT_GREEK] contracts={index}/{len(futures)} errors={len(errors)}", flush=True)
    if errors:
        raise AssertionError(f"exact-Greek backfill incomplete; no seal written: {errors[:10]}")
    index = pd.DataFrame(completed).sort_values(["ticker", "trade_date", "strike", "right"], kind="stable").reset_index(drop=True)
    counts = index.groupby("ticker", observed=True).size().astype(int).to_dict()
    if (
        len(index) != EXPECTED_CONTRACTS or counts != EXPECTED_CONTRACTS_BY_TICKER
        or contract_key_hash(index) != universe_hash or index.duplicated(["ticker", "trade_date", "strike", "right"]).any()
        or not index["rows"].eq(EXPECTED_TIMESTAMPS).all() or not index["stored_bid_ask_exact"].eq(True).all()
        or not index["max_spot_difference_bps"].le(SPOT_TOLERANCE_BPS).all()
        or set(index["terminal_jar_sha256"].astype(str)) != {jar_hash_before}
        or set(index["git_commit"].astype(str)) != {commit}
    ):
        raise AssertionError("exact-Greek backfill index failed frozen coverage/provenance gate")
    if sha256_file(jar_path) != jar_hash_before:
        raise AssertionError("Theta Terminal JAR changed during exact-Greek backfill")
    seal_staging.mkdir(parents=True, exist_ok=False)
    index_path = seal_staging / "exact_greek_index.csv"
    index.to_csv(index_path, index=False)
    payload = {
        "schema": "wall_exact_greek_repair_seal_v1r2", "status": "PASS_EXACT_GREEK_REPAIR_CAPTURE",
        "outcome_free": True, "holdout_2026_used": False, "production_modified": False,
        "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "git_commit": commit,
        "builder_sha256": sha256_file(__file__), "predeclaration_sha256": sha256_file(PREDECLARATION),
        "source_manifest_path": str(Path(manifest_path)), "source_manifest_sha256": sha256_file(manifest_path),
        "contracts": int(len(index)), "contracts_by_ticker": counts,
        "contract_key_sha256": universe_hash, "exact_rows": int(index["rows"].sum()),
        "timestamps_per_contract": EXPECTED_TIMESTAMPS, "decision_times": list(DECISION_TIMES),
        "max_spot_difference_bps": float(index["max_spot_difference_bps"].max()),
        "index_path": str(seal / index_path.name), "index_sha256": sha256_file(index_path),
        "base_url": base_url.rstrip("/"), "endpoint": ENDPOINT,
        "terminal_jar_path": str(jar_path), "terminal_jar_sha256": jar_hash_before,
        "terminal_process_ids": sorted(index["terminal_process_id"].astype(int).unique().tolist()),
        "java_executable_sha256": sorted(index["java_executable_sha256"].astype(str).unique().tolist()),
        "runtime_lock_sha256": runtime["lock_sha256"], "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"], "errors": [],
    }
    (seal_staging / "manifest.json").write_bytes(canonical_json_bytes(payload))
    seal_staging.rename(seal)
    return payload


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit-universe")
    audit.add_argument("--manifest", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--ticker", required=True, choices=TARGET_TICKERS)
    fetch.add_argument("--date", default=TARGET_DATE)
    fetch.add_argument("--strike", type=float, required=True)
    fetch.add_argument("--right", required=True, choices=("C", "P", "CALL", "PUT"))
    fetch.add_argument("--greeks", required=True); fetch.add_argument("--oi", required=True)
    fetch.add_argument("--underlying", required=True); fetch.add_argument("--manifest", required=True)
    fetch.add_argument("--output-root", required=True); fetch.add_argument("--terminal-jar", required=True)
    fetch.add_argument("--base-url", default="http://127.0.0.1:25503/v3"); fetch.add_argument("--timeout", type=float, default=300.0)
    check = sub.add_parser("validate")
    check.add_argument("--contract-dir", required=True); check.add_argument("--greeks", required=True)
    check.add_argument("--oi", required=True); check.add_argument("--underlying", required=True); check.add_argument("--manifest", required=True)
    batch = sub.add_parser("backfill")
    batch.add_argument("--manifest", required=True); batch.add_argument("--output-root", required=True)
    batch.add_argument("--terminal-jar", required=True); batch.add_argument("--base-url", default="http://127.0.0.1:25503/v3")
    batch.add_argument("--workers", type=int, default=1); batch.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "audit-universe":
        universe = discover_contract_universe(args.manifest)
        result = {"contracts": len(universe), "contracts_by_ticker": universe.groupby("ticker").size().to_dict(), "contract_key_sha256": contract_key_hash(universe)}
    elif args.command == "fetch":
        assert_committed_builder()
        result = download_contract(
            ticker=args.ticker, trade_date=args.date, strike=args.strike, right=args.right,
            greeks_path=args.greeks, oi_path=args.oi, underlying_path=args.underlying,
            source_manifest_path=args.manifest, output_root=args.output_root, base_url=args.base_url,
            terminal_jar=args.terminal_jar, timeout=args.timeout,
        )
    elif args.command == "validate":
        result = validate_contract(
            args.contract_dir, greeks_path=args.greeks, oi_path=args.oi,
            underlying_path=args.underlying, source_manifest_path=args.manifest,
        )
    else:
        result = backfill_exact_greeks(
            manifest_path=args.manifest, output_root=args.output_root, base_url=args.base_url,
            terminal_jar=args.terminal_jar, workers=args.workers, timeout=args.timeout,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
