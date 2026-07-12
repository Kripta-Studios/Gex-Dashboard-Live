"""Download and validate an immutable, outcome-free ThetaData quote sidecar.

The sidecar is deliberately separate from the wall-flow dataset.  Each request
is one ticker/session, expiration equals the session (0DTE), and uses native
``/option/history/quote`` one-minute wildcard-chain data.  Existing session
artifacts are never overwritten.
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
from typing import Any, Callable
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import requests


TICKERS = ("SPXW", "QQQ", "SPY")
ENDPOINT = "/option/history/quote"
KEYS = ("symbol", "expiration", "trade_date", "timestamp", "strike", "right")
SOURCE_COLUMNS = ("symbol", "expiration", "timestamp", "underlying_timestamp", "strike", "right", "bid", "ask", "bid_size", "ask_size")
OUTPUT_COLUMNS = (*KEYS, "underlying_timestamp", "bid", "ask", "bid_size", "ask_size")
DEFAULT_START_TIME = "10:20:00"
DEFAULT_END_TIME = "14:29:00"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402
from neural.jepa.surface_flow_features import last_scheduled_decision_minute  # noqa: E402

ENVIRONMENT_LOCK = PROJECT_ROOT / "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
CANONICAL_MANIFEST_SHA256 = "5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88"
START_DATE = "20220801"
END_DATE = "20251231"
EXPECTED_FALLBACK_SESSIONS = 1441
EXPECTED_FALLBACK_KEY_SHA256 = "4d4335005bb1ad29dd9f59a873a8902edcf17f1eb64c006792b29b57dea9a579"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def current_git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def assert_committed_builder() -> str:
    for relative in (
        "neural/jepa/build_wall_native_quote_sidecar.py",
        "neural/jepa/surface_flow_features.py",
        "neural/jepa/wall_surface_flow_environment.py",
        "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
    ):
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", relative],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if dirty:
            raise AssertionError(f"native quote backfill requires committed clean code: {relative}: {dirty}")
    return current_git_commit()


def research_end_time(ticker: str, trade_date: str) -> str:
    minute = last_scheduled_decision_minute(ticker, trade_date) - 1
    return f"{minute // 60:02d}:{minute % 60:02d}:00"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def session_key_hash(frame: pd.DataFrame) -> str:
    ordered = frame.sort_values(["ticker", "trade_date"], kind="stable")
    payload = "".join(
        f"{row.ticker},{row.trade_date}\n"
        for row in ordered[["ticker", "trade_date"]].itertuples(index=False)
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def discover_fallback_sessions(
    manifest_path: str | Path,
    *,
    require_canonical_hash: bool = True,
) -> pd.DataFrame:
    path = Path(manifest_path)
    observed_hash = sha256_file(path)
    if require_canonical_hash and observed_hash != CANONICAL_MANIFEST_SHA256:
        raise AssertionError(f"canonical source manifest hash mismatch: {observed_hash}")
    manifest = pd.read_csv(path, dtype={"trade_date": str, "expiration": str})
    required = {
        "ticker", "trade_date", "expiration", "dte_days", "expiry_mode",
        "has_greeks", "greeks_path",
    }
    missing = sorted(required.difference(manifest.columns))
    if missing:
        raise KeyError(f"source manifest missing fallback-discovery columns: {missing}")
    work = manifest.copy()
    work["ticker"] = work["ticker"].astype(str).str.upper()
    for column in ("trade_date", "expiration"):
        work[column] = work[column].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    work = work[
        work["ticker"].isin(TICKERS)
        & work["trade_date"].between(START_DATE, END_DATE)
        & pd.to_numeric(work["dte_days"], errors="coerce").eq(0)
        & work["expiry_mode"].astype(str).str.lower().eq("zero_dte")
        & work["has_greeks"].map(_truthy)
    ].copy()
    if work.empty or work.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("canonical 0DTE Greek session universe is empty or duplicated")
    if not work["expiration"].eq(work["trade_date"]).all():
        raise AssertionError("fallback discovery requires expiration == trade_date")
    fallback_rows: list[dict[str, str]] = []
    for row in work.sort_values(["ticker", "trade_date"], kind="stable").itertuples(index=False):
        greeks_path = Path(str(row.greeks_path))
        if not greeks_path.is_file():
            raise FileNotFoundError(f"missing stored Greek source: {greeks_path}")
        columns = set(pq.ParquetFile(greeks_path).schema_arrow.names)
        if "timestamp" not in columns:
            if "underlying_timestamp" not in columns:
                raise AssertionError(f"Greek source has neither timestamp clock: {greeks_path}")
            fallback_rows.append(
                {
                    "ticker": str(row.ticker),
                    "trade_date": str(row.trade_date),
                    "greeks_path": str(greeks_path),
                }
            )
    fallback = pd.DataFrame(fallback_rows, columns=["ticker", "trade_date", "greeks_path"])
    if fallback["trade_date"].astype(str).str.startswith("2026").any():
        raise AssertionError("2026 entered native quote backfill scope")
    return fallback


def unwrap_response(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("response"), list):
        return raw["response"]
    raise ValueError("ThetaData response must be a list or {'response': [...]} wrapper")


def flatten_quote_response(raw: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in unwrap_response(raw):
        if not isinstance(item, dict):
            raise ValueError("quote response item is not an object")
        if "contract" in item and "data" in item:
            contract = item["contract"]
            if not isinstance(contract, dict) or not isinstance(item["data"], list):
                raise ValueError("invalid contract/data quote response")
            rows.extend({**contract, **row} for row in item["data"] if isinstance(row, dict))
        else:
            rows.append(item)
    return pd.DataFrame(rows)


def normalize_quotes(
    raw: Any,
    ticker: str,
    trade_date: str,
    *,
    start_time: str = DEFAULT_START_TIME,
    end_time: str = DEFAULT_END_TIME,
) -> pd.DataFrame:
    ticker = ticker.upper()
    day = "".join(ch for ch in str(trade_date) if ch.isdigit())[:8]
    if ticker not in TICKERS or len(day) != 8 or day >= "20260101":
        raise ValueError("only SPXW/QQQ/SPY pre-2026 sessions are allowed")
    frame = flatten_quote_response(raw)
    missing = sorted(set(SOURCE_COLUMNS).difference(frame.columns))
    if missing:
        raise KeyError(f"native quote response missing columns: {missing}")
    out = frame.loc[:, SOURCE_COLUMNS].copy()
    out.insert(2, "trade_date", day)
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out["right"] = out["right"].astype(str).str.upper().replace({"CALL": "C", "PUT": "P"})
    out["expiration"] = out["expiration"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    for column in ("timestamp", "underlying_timestamp"):
        out[column] = pd.to_datetime(out[column], errors="coerce")
    for column in ("strike", "bid", "ask", "bid_size", "ask_size"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if out.empty or out.isna().any().any():
        raise AssertionError("native quotes are empty or contain null/non-numeric required values")
    if not out["symbol"].eq(ticker).all() or not out["expiration"].eq(day).all():
        raise AssertionError("response violates requested symbol or expiration==trade_date")
    if not out["right"].isin(["C", "P"]).all():
        raise AssertionError("invalid option right")
    if not out["timestamp"].dt.strftime("%Y%m%d").eq(day).all():
        raise AssertionError("quote timestamp is outside requested session")
    if not out["underlying_timestamp"].dt.strftime("%Y%m%d").eq(day).all():
        raise AssertionError("underlying timestamp is outside requested session")
    if not out["timestamp"].eq(out["underlying_timestamp"]).all():
        raise AssertionError("native quote timestamp differs from underlying timestamp")
    if not (out["timestamp"].dt.second.eq(0) & out["timestamp"].dt.microsecond.eq(0)).all():
        raise AssertionError("quote timestamps are not exact minute boundaries")
    start = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {start_time}")
    end = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {end_time}")
    if end < start or not out["timestamp"].between(start, end, inclusive="both").all():
        raise AssertionError("quote response violates requested research window")
    if out.duplicated(list(KEYS)).any():
        raise AssertionError("duplicate exact native quote keys")
    numeric = out[["strike", "bid", "ask", "bid_size", "ask_size"]].to_numpy(dtype=float)
    if (
        not np.isfinite(numeric).all()
        or not (numeric[:, 0] > 0.0).all()
        or (numeric[:, 1:] < 0.0).any()
        or (out["ask"] < out["bid"]).any()
    ):
        raise AssertionError("invalid quote price/size values")
    return out.sort_values(list(KEYS), kind="stable").reset_index(drop=True)


def _normalize_greeks(
    greeks: pd.DataFrame,
    ticker: str,
    day: str,
    *,
    start_time: str,
    end_time: str,
) -> pd.DataFrame:
    required = {"symbol", "expiration", "right", "strike", "bid", "ask", "underlying_timestamp"}
    missing = sorted(required.difference(greeks.columns))
    if missing:
        raise KeyError(f"stored Greeks missing cross-check columns: {missing}")
    time_col = "timestamp" if "timestamp" in greeks else "underlying_timestamp"
    out = greeks.copy()
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out["expiration"] = out["expiration"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    out["trade_date"] = day
    out["right"] = out["right"].astype(str).str.upper().replace({"CALL": "C", "PUT": "P"})
    out["timestamp"] = pd.to_datetime(out[time_col], errors="coerce")
    out["underlying_timestamp"] = pd.to_datetime(out["underlying_timestamp"], errors="coerce")
    for column in ("strike", "bid", "ask"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out[out["symbol"].eq(ticker) & out["expiration"].eq(day)]
    start = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {start_time}")
    end = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {end_time}")
    out = out[out["timestamp"].between(start, end, inclusive="both")].copy()
    if out.empty or out.duplicated(list(KEYS)).any():
        raise AssertionError("stored Greeks cross-check keys are empty or duplicated")
    return out


def crosscheck_greeks(
    quotes: pd.DataFrame,
    greeks_path: str | Path,
    *,
    start_time: str = DEFAULT_START_TIME,
    end_time: str = DEFAULT_END_TIME,
    tolerance: float = 1e-9,
) -> dict[str, Any]:
    ticker = str(quotes["symbol"].iloc[0])
    day = str(quotes["expiration"].iloc[0])
    greeks_hash_before = sha256_file(greeks_path)
    available = set(pq.ParquetFile(greeks_path).schema_arrow.names)
    columns = [c for c in ("symbol", "expiration", "timestamp", "underlying_timestamp", "right", "strike", "bid", "ask") if c in available]
    greeks = _normalize_greeks(
        pd.read_parquet(greeks_path, columns=columns),
        ticker,
        day,
        start_time=start_time,
        end_time=end_time,
    )
    greeks_hash_after = sha256_file(greeks_path)
    if greeks_hash_after != greeks_hash_before:
        raise AssertionError("stored Greeks changed while cross-checking native quotes")
    merged = quotes.merge(greeks[list(KEYS) + ["underlying_timestamp", "bid", "ask"]], on=list(KEYS), suffixes=("_quote", "_greek"), how="inner")
    if len(merged) != len(quotes) or len(merged) != len(greeks):
        raise AssertionError(
            f"native quote/stored Greek exact key-set mismatch: shared={len(merged)} quotes={len(quotes)} greeks={len(greeks)}"
        )
    time_match = merged["underlying_timestamp_quote"].eq(merged["underlying_timestamp_greek"])
    bid_match = (merged["bid_quote"] - merged["bid_greek"]).abs().le(tolerance)
    ask_match = (merged["ask_quote"] - merged["ask_greek"]).abs().le(tolerance)
    if not (time_match & bid_match & ask_match).all():
        raise AssertionError("native quote versus stored Greek timestamp/bid/ask mismatch")
    return {
        "greek_rows": int(len(greeks)),
        "shared_exact_rows": int(len(merged)),
        "shared_exact_fraction": float(len(merged) / len(greeks)),
        "greeks_sha256": greeks_hash_before,
        "key_set_exact": True,
        "timestamp_bid_ask_exact": True,
    }


def download_session(*, ticker: str, trade_date: str, greeks_path: str | Path, output_root: str | Path,
                     base_url: str, terminal_jar: str | Path,
                     start_time: str = DEFAULT_START_TIME, end_time: str = DEFAULT_END_TIME,
                     timeout: float = 180.0,
                     requester: Callable[..., Any] = requests.get) -> dict[str, Any]:
    day = "".join(ch for ch in str(trade_date) if ch.isdigit())[:8]
    host = (urlparse(base_url).hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise AssertionError("authoritative native quote capture requires a local frozen Theta Terminal")
    jar_path = Path(terminal_jar).resolve()
    if not jar_path.is_file():
        raise FileNotFoundError(f"Theta Terminal JAR not found: {jar_path}")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    params = {
        "symbol": ticker.upper(), "expiration": day, "date": day,
        "strike": "*", "right": "both", "interval": "1m", "format": "json",
        "start_time": start_time, "end_time": end_time,
    }
    request_headers = {"Accept-Encoding": "identity"}
    response = requester(
        f"{base_url.rstrip('/')}{ENDPOINT}",
        params=params,
        headers=request_headers,
        timeout=timeout,
    )
    response.raise_for_status()
    raw_bytes = bytes(response.content)
    if not raw_bytes:
        raise AssertionError("ThetaData returned an empty raw response")
    raw = json.loads(raw_bytes)
    quotes = normalize_quotes(raw, ticker, day, start_time=start_time, end_time=end_time)
    audit = crosscheck_greeks(
        quotes,
        greeks_path,
        start_time=start_time,
        end_time=end_time,
    )
    session_dir = Path(output_root) / ticker.upper() / day
    staging_dir = session_dir.with_name(f"{session_dir.name}.staging")
    raw_path = session_dir / "quote_response.json"
    parquet_path = session_dir / "quotes.parquet"
    manifest_path = session_dir / "manifest.json"
    if session_dir.exists() or staging_dir.exists():
        raise FileExistsError(f"immutable sidecar session already exists: {session_dir}")
    staging_dir.mkdir(parents=True, exist_ok=False)
    raw_path = staging_dir / raw_path.name
    parquet_path = staging_dir / parquet_path.name
    manifest_path = staging_dir / manifest_path.name
    raw_path.write_bytes(raw_bytes)
    quotes.to_parquet(parquet_path, index=False)
    manifest = {
        "schema_version": 1, "outcome_free": True, "ticker": ticker.upper(), "trade_date": day,
        "expiration": day, "endpoint": ENDPOINT, "base_url": base_url.rstrip("/"),
        "request_params": params, "request_headers": request_headers,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "http_status": int(getattr(response, "status_code", 200)),
        "response_headers": dict(sorted((str(k), str(v)) for k, v in getattr(response, "headers", {}).items())),
        "terminal_jar_path": str(jar_path), "terminal_jar_sha256": sha256_file(jar_path),
        "builder_sha256": sha256_file(__file__),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "raw_response_sha256": sha256_bytes(raw_bytes), "quote_parquet_sha256": sha256_file(parquet_path),
        "rows": int(len(quotes)), "columns": list(quotes.columns), **audit,
    }
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    staging_dir.rename(session_dir)
    return manifest


def validate_session(session_dir: str | Path, greeks_path: str | Path) -> dict[str, Any]:
    root = Path(session_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("outcome_free") is not True or str(manifest.get("trade_date", "")) >= "20260101":
        raise AssertionError("invalid sidecar scope")
    raw_bytes = (root / "quote_response.json").read_bytes()
    parquet_path = root / "quotes.parquet"
    if sha256_bytes(raw_bytes) != manifest["raw_response_sha256"] or sha256_file(parquet_path) != manifest["quote_parquet_sha256"]:
        raise AssertionError("immutable sidecar hash mismatch")
    params = manifest["request_params"]
    quotes = normalize_quotes(
        json.loads(raw_bytes),
        manifest["ticker"],
        manifest["trade_date"],
        start_time=str(params["start_time"]),
        end_time=str(params["end_time"]),
    )
    stored = pd.read_parquet(parquet_path)
    pd.testing.assert_frame_equal(stored, quotes, check_dtype=True)
    crosscheck_greeks(
        stored,
        greeks_path,
        start_time=str(params["start_time"]),
        end_time=str(params["end_time"]),
    )
    if sha256_file(manifest["terminal_jar_path"]) != manifest["terminal_jar_sha256"]:
        raise AssertionError("Theta Terminal JAR hash mismatch")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    if runtime["lock_sha256"] != manifest["runtime_lock_sha256"] or runtime["environment_sha256"] != manifest["runtime_environment_sha256"]:
        raise AssertionError("sidecar runtime provenance mismatch")
    return manifest


def backfill_native_quotes(
    *,
    manifest_path: str | Path,
    output_root: str | Path,
    base_url: str,
    terminal_jar: str | Path,
    workers: int = 1,
    timeout: float = 180.0,
) -> dict[str, Any]:
    if not 1 <= int(workers) <= 4:
        raise ValueError("native quote backfill workers must be within 1..4")
    commit = assert_committed_builder()
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    fallback = discover_fallback_sessions(manifest_path)
    observed_key_hash = session_key_hash(fallback)
    if len(fallback) != EXPECTED_FALLBACK_SESSIONS or observed_key_hash != EXPECTED_FALLBACK_KEY_SHA256:
        raise AssertionError(
            "frozen fallback session universe mismatch: "
            f"rows={len(fallback)}/{EXPECTED_FALLBACK_SESSIONS} hash={observed_key_hash}"
        )
    root = Path(output_root)
    seal = root / "_seal"
    staging = root / "_seal.staging"
    if seal.exists() or staging.exists():
        raise FileExistsError(f"immutable quote-backfill seal already exists: {seal}")
    jar_path = Path(terminal_jar).resolve()
    jar_hash_before = sha256_file(jar_path)
    records = fallback.to_dict("records")

    def one(record: dict[str, str]) -> dict[str, Any]:
        ticker = str(record["ticker"])
        day = str(record["trade_date"])
        session_dir = root / ticker / day
        if session_dir.exists():
            manifest = validate_session(session_dir, record["greeks_path"])
        else:
            manifest = download_session(
                ticker=ticker,
                trade_date=day,
                greeks_path=record["greeks_path"],
                output_root=root,
                base_url=base_url,
                terminal_jar=jar_path,
                start_time=DEFAULT_START_TIME,
                end_time=research_end_time(ticker, day),
                timeout=timeout,
            )
        manifest_path_session = session_dir / "manifest.json"
        return {
            "ticker": ticker,
            "trade_date": day,
            "greeks_path": str(record["greeks_path"]),
            "greeks_sha256": str(manifest["greeks_sha256"]),
            "session_dir": str(session_dir),
            "quotes_path": str(session_dir / "quotes.parquet"),
            "quotes_sha256": str(manifest["quote_parquet_sha256"]),
            "raw_response_path": str(session_dir / "quote_response.json"),
            "raw_response_sha256": str(manifest["raw_response_sha256"]),
            "session_manifest_path": str(manifest_path_session),
            "session_manifest_sha256": sha256_file(manifest_path_session),
            "rows": int(manifest["rows"]),
            "end_time": str(manifest["request_params"]["end_time"]),
            "terminal_jar_sha256": str(manifest["terminal_jar_sha256"]),
            "key_set_exact": bool(manifest["key_set_exact"]),
            "timestamp_bid_ask_exact": bool(manifest["timestamp_bid_ask_exact"]),
        }

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    if workers == 1:
        for index, record in enumerate(records, start=1):
            try:
                rows.append(one(record))
            except Exception as exc:
                errors.append(
                    {
                        "ticker": str(record["ticker"]),
                        "trade_date": str(record["trade_date"]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            if index % 25 == 0 or index == len(records):
                print(f"[NATIVE_QUOTE] sessions={index}/{len(records)} errors={len(errors)}", flush=True)
    else:
        with ThreadPoolExecutor(max_workers=int(workers)) as pool:
            futures = {pool.submit(one, record): record for record in records}
            for index, future in enumerate(as_completed(futures), start=1):
                record = futures[future]
                try:
                    rows.append(future.result())
                except Exception as exc:
                    errors.append(
                        {
                            "ticker": str(record["ticker"]),
                            "trade_date": str(record["trade_date"]),
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                if index % 25 == 0 or index == len(futures):
                    print(f"[NATIVE_QUOTE] sessions={index}/{len(futures)} errors={len(errors)}", flush=True)
    if errors:
        raise AssertionError(f"native quote backfill incomplete; no seal written: {errors[:10]}")
    index = pd.DataFrame(rows).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    if (
        len(index) != EXPECTED_FALLBACK_SESSIONS
        or index.duplicated(["ticker", "trade_date"]).any()
        or not index["key_set_exact"].astype(bool).all()
        or not index["timestamp_bid_ask_exact"].astype(bool).all()
        or set(index["terminal_jar_sha256"].astype(str)) != {jar_hash_before}
    ):
        raise AssertionError("native quote backfill index failed exact-coverage gate")
    if sha256_file(jar_path) != jar_hash_before:
        raise AssertionError("Theta Terminal JAR changed during native quote backfill")
    staging.mkdir(parents=True, exist_ok=False)
    index_path = staging / "native_quote_index.csv"
    index.to_csv(index_path, index=False)
    payload = {
        "schema": "wall_native_quote_sidecar_seal_v1",
        "status": "PASS_NATIVE_TIMESTAMP_BACKFILL",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "builder_sha256": sha256_file(__file__),
        "source_manifest_path": str(Path(manifest_path)),
        "source_manifest_sha256": sha256_file(manifest_path),
        "fallback_sessions": int(len(index)),
        "fallback_session_key_sha256": observed_key_hash,
        "rows": int(index["rows"].sum()),
        "rows_by_ticker": index.groupby("ticker", observed=True)["rows"].sum().astype(int).to_dict(),
        "index_path": str(seal / index_path.name),
        "index_sha256": sha256_file(index_path),
        "base_url": base_url.rstrip("/"),
        "endpoint": ENDPOINT,
        "terminal_jar_path": str(jar_path),
        "terminal_jar_sha256": jar_hash_before,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "errors": [],
    }
    (staging / "manifest.json").write_bytes(canonical_json_bytes(payload))
    staging.rename(seal)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--ticker", required=True, choices=TICKERS)
    fetch.add_argument("--date", required=True)
    fetch.add_argument("--greeks", required=True)
    fetch.add_argument("--output-root", required=True)
    fetch.add_argument("--base-url", default="http://127.0.0.1:25503/v3")
    fetch.add_argument("--terminal-jar", required=True)
    fetch.add_argument("--start-time", default=DEFAULT_START_TIME)
    fetch.add_argument("--end-time", default=DEFAULT_END_TIME)
    fetch.add_argument("--timeout", type=float, default=180.0)
    check = sub.add_parser("validate")
    check.add_argument("--session-dir", required=True)
    check.add_argument("--greeks", required=True)
    audit = sub.add_parser("audit-fallback-universe")
    audit.add_argument("--manifest", required=True)
    batch = sub.add_parser("backfill")
    batch.add_argument("--manifest", required=True)
    batch.add_argument("--output-root", required=True)
    batch.add_argument("--base-url", default="http://127.0.0.1:25503/v3")
    batch.add_argument("--terminal-jar", required=True)
    batch.add_argument("--workers", type=int, default=1)
    batch.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    if args.command == "fetch":
        result = download_session(
            ticker=args.ticker, trade_date=args.date, greeks_path=args.greeks,
            output_root=args.output_root, base_url=args.base_url,
            terminal_jar=args.terminal_jar, start_time=args.start_time,
            end_time=args.end_time, timeout=args.timeout,
        )
    elif args.command == "validate":
        result = validate_session(args.session_dir, args.greeks)
    elif args.command == "audit-fallback-universe":
        frame = discover_fallback_sessions(args.manifest)
        result = {
            "sessions": int(len(frame)),
            "session_key_sha256": session_key_hash(frame),
            "by_ticker_year": {
                f"{ticker}:{year}": int(len(part))
                for (ticker, year), part in frame.assign(year=frame["trade_date"].str[:4]).groupby(
                    ["ticker", "year"], observed=True, sort=True
                )
            },
        }
    else:
        result = backfill_native_quotes(
            manifest_path=args.manifest,
            output_root=args.output_root,
            base_url=args.base_url,
            terminal_jar=args.terminal_jar,
            workers=args.workers,
            timeout=args.timeout,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
