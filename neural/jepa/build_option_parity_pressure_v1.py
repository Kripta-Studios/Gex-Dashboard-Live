"""Build the outcome-free OPTION_PARITY_PRESSURE_V1 feature view."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from neural.jepa.build_wall_surface_flow_dataset import attach_native_quote_index
from neural.jepa.surface_flow_features import normalize_right, validate_underlying_session


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TICKERS = ("QQQ", "SPXW", "SPY")
CLOCKS = ("10:30:00", "10:35:00")
START_DATE = "20230101"
END_DATE = "20251231"
MONEYNESS_RADIUS_BPS = 100.0
MIN_COMMON_STRIKES = 3
MIN_ANNUAL_COVERAGE = 0.90
MIN_DISTINCT_STATES = 50
MAX_ZERO_FRACTION = 0.995
HALF_DAYS = frozenset(
    {
        "20230703",
        "20231124",
        "20240703",
        "20241129",
        "20241224",
        "20250703",
        "20251128",
        "20251224",
    }
)
CAPACITY_DIR = Path(
    "research_papers/JEPA/results/_diagnostics/option_parity_pressure_v1_capacity_202301_202512"
)
CAPACITY_HASHES = {
    "manifest.json": "eebdc7d9f31ff623aef95d3e1b5b93c0c3957ec8bad4950f1e1c61f7eab4f590",
    "monthly_capacity.csv": "e8dfc2e404adc0dee130e4d5bc81480b0df6ee697cd2e18aed04598d0485c5e7",
    "source_inventory.csv": "9c6ddb40dd1e90fdde5c89222103a0b3b6e446dbdb7b0e834e150ca6d009392d",
}
PREDECLARATION = Path("research_papers/JEPA/OPTION_PARITY_PRESSURE_V1_PREDECLARATION.md")
SCOPE_AMENDMENT = Path("research_papers/JEPA/OPTION_PARITY_PRESSURE_V1_SCOPE_AMENDMENT.md")
CAPACITY_RESULT = Path("research_papers/JEPA/OPTION_PARITY_PRESSURE_V1_CAPACITY_RESULT.md")
NATIVE_INDEX = Path(
    "D:/ThetaData/wall_native_quote_sidecar_202208_202512_v1r1/_seal/native_quote_index.csv"
)
NATIVE_SEAL = Path(
    "D:/ThetaData/wall_native_quote_sidecar_202208_202512_v1r1/_seal/manifest.json"
)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def current_git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def assert_committed_clean(relative_paths: tuple[Path, ...]) -> str:
    for path in relative_paths:
        relative = path.as_posix()
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
            raise AssertionError(f"authoritative input must be committed and clean: {dirty}")
    return current_git_commit()


def validate_capacity_artifacts() -> tuple[pd.DataFrame, dict[str, Any]]:
    for name, expected in CAPACITY_HASHES.items():
        path = CAPACITY_DIR / name
        if not path.is_file() or sha256_file(path) != expected:
            raise AssertionError(f"capacity artifact hash mismatch: {path}")
    manifest = json.loads((CAPACITY_DIR / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("status") != "PASS_FREQUENCY_CAPACITY"
        or manifest.get("outcome_accessed") is not False
        or manifest.get("quote_content_accessed") is not False
        or manifest.get("holdout_2026_opened") is not False
        or manifest.get("production_modified") is not False
        or int(manifest.get("exact_zero_dte_source_files", -1)) != 2256
    ):
        raise AssertionError("capacity manifest is not the frozen outcome-free PASS")
    inventory = pd.read_csv(
        CAPACITY_DIR / "source_inventory.csv",
        dtype={"trade_date": str, "month": str},
    )
    required = {
        "ticker",
        "trade_date",
        "month",
        "path",
        "bytes",
        "calendar_half_day",
        "eligible_fixed_180m_clock",
    }
    if required.difference(inventory.columns):
        raise KeyError("capacity inventory schema mismatch")
    inventory["ticker"] = inventory["ticker"].astype(str).str.upper()
    inventory["trade_date"] = inventory["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    if (
        len(inventory) != 2256
        or set(inventory["ticker"]) != set(TICKERS)
        or inventory.duplicated(["ticker", "trade_date"]).any()
        or not inventory["trade_date"].between(START_DATE, END_DATE).all()
        or inventory["trade_date"].str.startswith("2026").any()
    ):
        raise AssertionError("capacity inventory universe mismatch")
    for row in inventory.itertuples(index=False):
        path = Path(str(row.path))
        if not path.is_file() or path.stat().st_size != int(row.bytes):
            raise AssertionError(f"capacity source missing or size changed: {path}")
    return inventory.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True), manifest


def attach_source_paths(
    inventory: pd.DataFrame,
    underlying_root: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    sessions = inventory.rename(columns={"path": "greeks_path"}).copy()
    sessions["underlying_path"] = sessions.apply(
        lambda row: str(
            underlying_root
            / str(row["ticker"])
            / str(row["trade_date"])[:4]
            / str(row["trade_date"])[4:6]
            / f"{row['ticker']}_{row['trade_date']}.parquet"
        ),
        axis=1,
    )
    for path in sessions["underlying_path"]:
        if not Path(path).is_file():
            raise FileNotFoundError(f"missing derived-underlying source: {path}")
    attached, native_provenance = attach_native_quote_index(sessions, NATIVE_INDEX, NATIVE_SEAL)
    return attached, native_provenance


def normalize_option_keys(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["symbol"] = output["symbol"].astype(str).str.upper().str.strip()
    for column in ("expiration", "trade_date"):
        output[column] = output[column].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    output["right"] = normalize_right(output["right"])
    output["strike"] = pd.to_numeric(output["strike"], errors="coerce")
    for column in ("bid", "ask"):
        output[column] = pd.to_numeric(output[column], errors="coerce")
    return output


def target_datetimes(trade_date: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    day = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
    return tuple(pd.Timestamp(f"{day} {clock}") for clock in CLOCKS)  # type: ignore[return-value]


def read_target_greeks(record: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    greek_path = Path(str(record["greeks_path"]))
    schema = set(pq.ParquetFile(greek_path).schema_arrow.names)
    base_columns = ["symbol", "expiration", "trade_date", "strike", "right", "bid", "ask"]
    required = set(base_columns)
    if required.difference(schema):
        raise KeyError(f"Greek source missing parity columns: {sorted(required.difference(schema))}")
    trade_date = str(record["trade_date"])
    times = target_datetimes(trade_date)
    iso_times = [stamp.strftime("%Y-%m-%dT%H:%M:%S") for stamp in times]
    use_sidecar = bool(record.get("greeks_timestamp_fallback"))
    if use_sidecar:
        if "timestamp" in schema or "underlying_timestamp" not in schema:
            raise AssertionError("sidecar routing disagrees with Greek clock schema")
        greeks = pd.read_parquet(
            greek_path,
            columns=[*base_columns, "underlying_timestamp"],
            filters=[("underlying_timestamp", "in", iso_times)],
        )
        if greeks.empty:
            raise AssertionError("no stored Greek rows at target clocks")
        greeks = normalize_option_keys(greeks)
        greeks["timestamp"] = pd.to_datetime(greeks["underlying_timestamp"], errors="coerce")
        native_path = Path(str(record["native_quote_path"]))
        native = pd.read_parquet(
            native_path,
            columns=[*base_columns, "timestamp"],
            filters=[("timestamp", "in", [stamp.to_pydatetime() for stamp in times])],
        )
        native = normalize_option_keys(native)
        native["timestamp"] = pd.to_datetime(native["timestamp"], errors="coerce")
        keys = ["symbol", "expiration", "trade_date", "timestamp", "strike", "right"]
        if (
            greeks[keys].isna().any().any()
            or native[keys].isna().any().any()
            or greeks.duplicated(keys).any()
            or native.duplicated(keys).any()
        ):
            raise AssertionError("native clock bridge contains missing/duplicate keys")
        parity = greeks[keys].merge(native[keys], on=keys, how="left", indicator=True, validate="one_to_one")
        if len(parity) != len(greeks) or not parity["_merge"].eq("both").all():
            raise AssertionError("native sidecar does not cover target Greek keys exactly")
        # Deliberately retain Greek bid/ask. Native quote prices never enter output.
        output = greeks.drop(columns=["underlying_timestamp"])
        native_rows = int(len(native))
    else:
        if "timestamp" not in schema:
            raise AssertionError("native timestamp absent without sealed sidecar")
        output = pd.read_parquet(
            greek_path,
            columns=[*base_columns, "timestamp"],
            filters=[("timestamp", "in", iso_times)],
        )
        output = normalize_option_keys(output)
        output["timestamp"] = pd.to_datetime(output["timestamp"], errors="coerce")
        native_rows = 0
    if output.empty or output["timestamp"].isna().any():
        raise AssertionError("target native Greek timestamps are empty/invalid")
    expected_ticker = str(record["ticker"])
    if (
        set(output["symbol"]) != {expected_ticker}
        or not output["expiration"].eq(trade_date).all()
        or not output["trade_date"].eq(trade_date).all()
        or set(output["timestamp"].unique()) != set(times)
    ):
        raise AssertionError("target Greek metadata/clock mismatch")
    keys = ["timestamp", "strike", "right"]
    if output.duplicated(keys).any():
        raise AssertionError("target Greek rows contain duplicate contract keys")
    return output, {"used_native_sidecar": use_sidecar, "native_target_rows": native_rows}


def compute_parity_event(
    greeks: pd.DataFrame,
    spots: dict[pd.Timestamp, float],
    *,
    ticker: str,
    trade_date: str,
) -> dict[str, Any]:
    times = target_datetimes(trade_date)
    base: dict[str, Any] = {
        "ticker": ticker,
        "trade_date": trade_date,
        "year": trade_date[:4],
        "month": trade_date[:6],
        "calendar_half_day": trade_date in HALF_DAYS,
        "economic_clock_eligible": trade_date not in HALF_DAYS,
        "parity_valid": False,
        "invalid_reason": "",
    }
    prepared: dict[pd.Timestamp, pd.DataFrame] = {}
    quality: dict[str, int] = {}
    for label, timestamp in zip(("t0", "t1"), times, strict=True):
        part = greeks[greeks["timestamp"].eq(timestamp)].copy()
        spot = float(spots[timestamp])
        finite = np.isfinite(part[["strike", "bid", "ask"]].to_numpy(dtype=float)).all(axis=1)
        crossed = finite & part["ask"].lt(part["bid"])
        zero_bid = finite & part["bid"].le(0.0)
        signable = finite & part["bid"].gt(0.0) & part["ask"].ge(part["bid"])
        part["within_radius"] = (
            np.abs(np.log(pd.to_numeric(part["strike"], errors="coerce") / spot)) * 10_000.0
        ).le(MONEYNESS_RADIUS_BPS)
        prepared[timestamp] = part[signable & part["within_radius"]].copy()
        quality[f"{label}_raw_rows"] = int(len(part))
        quality[f"{label}_crossed_rows"] = int(crossed.sum())
        quality[f"{label}_zero_bid_rows"] = int(zero_bid.sum())
        quality[f"{label}_signable_radius_rows"] = int(len(prepared[timestamp]))
        base[f"spot_{label}"] = spot
    pivots: dict[pd.Timestamp, pd.DataFrame] = {}
    for timestamp in times:
        part = prepared[timestamp]
        bid = part.pivot(index="strike", columns="right", values="bid")
        ask = part.pivot(index="strike", columns="right", values="ask")
        if not {"CALL", "PUT"}.issubset(bid.columns) or not {"CALL", "PUT"}.issubset(ask.columns):
            pivots[timestamp] = pd.DataFrame()
            continue
        pivots[timestamp] = pd.DataFrame(
            {
                "call_bid": bid["CALL"],
                "call_ask": ask["CALL"],
                "put_bid": bid["PUT"],
                "put_ask": ask["PUT"],
            }
        ).dropna()
    common = pivots[times[0]].index.intersection(pivots[times[1]].index)
    base.update(quality)
    base["common_strikes"] = int(len(common))
    if len(common) < MIN_COMMON_STRIKES:
        base["invalid_reason"] = "INSUFFICIENT_COMMON_STRIKES"
        return base
    z_by_time: list[np.ndarray] = []
    basis_bps_by_time: list[np.ndarray] = []
    widths_by_time: list[np.ndarray] = []
    valid_common = np.ones(len(common), dtype=bool)
    strikes = common.to_numpy(dtype=float)
    for timestamp in times:
        view = pivots[timestamp].loc[common]
        call_mid = (view["call_bid"].to_numpy() + view["call_ask"].to_numpy()) / 2.0
        put_mid = (view["put_bid"].to_numpy() + view["put_ask"].to_numpy()) / 2.0
        width = (
            view["call_ask"].to_numpy()
            - view["call_bid"].to_numpy()
            + view["put_ask"].to_numpy()
            - view["put_bid"].to_numpy()
        ) / 2.0
        basis = strikes + call_mid - put_mid - float(spots[timestamp])
        valid = np.isfinite(basis) & np.isfinite(width) & (width > 0.0)
        valid_common &= valid
        z_by_time.append(np.divide(basis, width, out=np.full_like(basis, np.nan), where=valid))
        basis_bps_by_time.append(basis / float(spots[timestamp]) * 10_000.0)
        widths_by_time.append(width)
    base["valid_common_strikes"] = int(valid_common.sum())
    if int(valid_common.sum()) < MIN_COMMON_STRIKES:
        base["invalid_reason"] = "INSUFFICIENT_POSITIVE_SPREAD_STRIKES"
        return base
    z0 = z_by_time[0][valid_common]
    z1 = z_by_time[1][valid_common]
    difference = z1 - z0
    pressure = float(np.median(difference))
    if not np.isfinite(pressure):
        base["invalid_reason"] = "NONFINITE_PARITY_PRESSURE"
        return base
    base.update(
        {
            "parity_valid": True,
            "parity_pressure": pressure,
            "parity_z_t0_median": float(np.median(z0)),
            "parity_z_t1_median": float(np.median(z1)),
            "parity_change_iqr": float(np.quantile(difference, 0.75) - np.quantile(difference, 0.25)),
            "basis_t0_median_bps": float(np.median(basis_bps_by_time[0][valid_common])),
            "basis_t1_median_bps": float(np.median(basis_bps_by_time[1][valid_common])),
            "joint_half_spread_t0_median": float(np.median(widths_by_time[0][valid_common])),
            "joint_half_spread_t1_median": float(np.median(widths_by_time[1][valid_common])),
            "invalid_reason": "",
        }
    )
    return base


def source_fingerprint(path: Path, kind: str, ticker: str, trade_date: str) -> dict[str, Any]:
    before = path.stat()
    digest = sha256_file(path)
    after = path.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise AssertionError(f"source changed while being hashed: {path}")
    parquet = pq.ParquetFile(path)
    return {
        "ticker": ticker,
        "trade_date": trade_date,
        "source_kind": kind,
        "path": str(path),
        "bytes": int(after.st_size),
        "rows": int(parquet.metadata.num_rows),
        "sha256": digest,
        "schema_sha256": hashlib.sha256(str(parquet.schema_arrow).encode("utf-8")).hexdigest(),
    }


def process_session(record: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    ticker = str(record["ticker"])
    trade_date = str(record["trade_date"])
    greek_path = Path(str(record["greeks_path"]))
    underlying_path = Path(str(record["underlying_path"]))
    sources = [
        source_fingerprint(greek_path, "greeks_vintage", ticker, trade_date),
        source_fingerprint(underlying_path, "derived_underlying", ticker, trade_date),
    ]
    if bool(record.get("greeks_timestamp_fallback")):
        native_path = Path(str(record["native_quote_path"]))
        native_source = source_fingerprint(native_path, "native_timestamp_sidecar", ticker, trade_date)
        if native_source["sha256"] != str(record.get("expected_native_quote_sha256")):
            raise AssertionError("native quote sidecar hash differs from sealed index")
        if sources[0]["sha256"] != str(record.get("expected_greeks_sha256")):
            raise AssertionError("Greek vintage hash differs from sealed sidecar index")
        sources.append(native_source)
    underlying = pd.read_parquet(underlying_path)
    validated, underlying_audit = validate_underlying_session(
        underlying,
        expected_ticker=ticker,
        expected_trade_date=trade_date,
    )
    times = target_datetimes(trade_date)
    spot_series = validated.set_index("bar_start")["open"].reindex(list(times))
    if spot_series.isna().any() or not np.isfinite(spot_series.to_numpy(dtype=float)).all():
        raise AssertionError("derived underlying lacks finite exact target opens")
    spots = {timestamp: float(spot_series.loc[timestamp]) for timestamp in times}
    greeks, clock_audit = read_target_greeks(record)
    event = compute_parity_event(greeks, spots, ticker=ticker, trade_date=trade_date)
    audit = {
        "ticker": ticker,
        "trade_date": trade_date,
        **clock_audit,
        **underlying_audit,
        "parity_valid": bool(event["parity_valid"]),
        "invalid_reason": str(event["invalid_reason"]),
    }
    return event, sources, audit


def evaluate_data_gate(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    eligible_clock = events[events["economic_clock_eligible"].astype(bool)].copy()
    coverage_rows: list[dict[str, Any]] = []
    distinct_rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        for year in ("2023", "2024", "2025"):
            part = eligible_clock[eligible_clock["ticker"].eq(ticker) & eligible_clock["year"].eq(year)]
            valid = part[part["parity_valid"].astype(bool)]
            coverage = float(len(valid) / len(part)) if len(part) else 0.0
            values = pd.to_numeric(valid.get("parity_pressure"), errors="coerce")
            finite = values[np.isfinite(values)]
            distinct = int(finite.round(12).nunique())
            zero_fraction = float(finite.eq(0.0).mean()) if len(finite) else 1.0
            coverage_rows.append(
                {
                    "ticker": ticker,
                    "year": year,
                    "source_events": int(len(part)),
                    "valid_events": int(len(valid)),
                    "coverage": coverage,
                    "coverage_pass": coverage >= MIN_ANNUAL_COVERAGE,
                }
            )
            distinct_rows.append(
                {
                    "ticker": ticker,
                    "year": year,
                    "finite_events": int(len(finite)),
                    "distinct_states": distinct,
                    "zero_fraction": zero_fraction,
                    "missing_values": int(values.isna().sum()),
                    "distinctness_pass": bool(
                        len(finite) == len(valid)
                        and distinct >= MIN_DISTINCT_STATES
                        and zero_fraction < MAX_ZERO_FRACTION
                    ),
                }
            )
    month_rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        for month in sorted(events["month"].unique()):
            part = eligible_clock[eligible_clock["ticker"].eq(ticker) & eligible_clock["month"].eq(month)]
            valid_events = int(part["parity_valid"].astype(bool).sum())
            month_rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "source_events": int(len(part)),
                    "valid_events": valid_events,
                    "frequency_pass": valid_events > 12,
                }
            )
    coverage = pd.DataFrame(coverage_rows)
    distinctness = pd.DataFrame(distinct_rows)
    monthly = pd.DataFrame(month_rows)
    gate = {
        "coverage_pass": bool(coverage["coverage_pass"].all()),
        "minimum_annual_coverage": float(coverage["coverage"].min()),
        "distinctness_pass": bool(distinctness["distinctness_pass"].all()),
        "minimum_distinct_states": int(distinctness["distinct_states"].min()),
        "maximum_zero_fraction": float(distinctness["zero_fraction"].max()),
        "frequency_pass": bool(monthly["frequency_pass"].all()),
        "minimum_monthly_valid_events": int(monthly["valid_events"].min()),
    }
    gate["passed"] = bool(all(gate[key] for key in ("coverage_pass", "distinctness_pass", "frequency_pass")))
    return coverage, distinctness, {"summary": gate, "monthly": monthly}


def runtime_environment() -> dict[str, Any]:
    import importlib.metadata as metadata

    packages = {}
    for name in ("numpy", "pandas", "pyarrow", "scipy", "scikit-learn", "lightgbm"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": packages,
    }


def publish_output(
    output_dir: Path,
    events: pd.DataFrame,
    audits: pd.DataFrame,
    sources: pd.DataFrame,
    coverage: pd.DataFrame,
    distinctness: pd.DataFrame,
    monthly: pd.DataFrame,
    errors: pd.DataFrame,
    manifest: dict[str, Any],
) -> None:
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    staging = output_dir.with_name(f"{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        pq.write_table(pa.Table.from_pandas(events, preserve_index=False), staging / "parity_features.parquet")
        audits.to_csv(staging / "session_audit.csv", index=False, lineterminator="\n")
        sources.to_csv(staging / "source_inventory.csv", index=False, lineterminator="\n")
        coverage.to_csv(staging / "coverage.csv", index=False, lineterminator="\n")
        distinctness.to_csv(staging / "distinctness.csv", index=False, lineterminator="\n")
        monthly.to_csv(staging / "monthly_capacity.csv", index=False, lineterminator="\n")
        errors.to_csv(staging / "errors.csv", index=False, lineterminator="\n")
        output_hashes = {}
        for name in (
            "parity_features.parquet",
            "session_audit.csv",
            "source_inventory.csv",
            "coverage.csv",
            "distinctness.csv",
            "monthly_capacity.csv",
            "errors.csv",
        ):
            output_hashes[name] = sha256_file(staging / name)
        manifest["output_sha256"] = output_hashes
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging.replace(output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def run(underlying_root: Path, output_dir: Path, workers: int) -> dict[str, Any]:
    if not 1 <= workers <= 12:
        raise ValueError("workers must be within 1..12")
    git_commit = assert_committed_clean(
        (
            Path("neural/jepa/build_option_parity_pressure_v1.py"),
            PREDECLARATION,
            SCOPE_AMENDMENT,
            CAPACITY_RESULT,
            *(CAPACITY_DIR / name for name in CAPACITY_HASHES),
        )
    )
    capacity, capacity_manifest = validate_capacity_artifacts()
    sessions, native_provenance = attach_source_paths(capacity, underlying_root)
    records = sessions.to_dict(orient="records")
    events: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_session, record): record for record in records}
        for index, future in enumerate(as_completed(futures), start=1):
            record = futures[future]
            try:
                event, session_sources, audit = future.result()
                events.append(event)
                sources.extend(session_sources)
                audits.append(audit)
            except Exception as exc:
                errors.append(
                    {
                        "ticker": str(record["ticker"]),
                        "trade_date": str(record["trade_date"]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            if index % 100 == 0 or index == len(records):
                print(f"processed={index}/{len(records)} errors={len(errors)}", flush=True)
    event_frame = pd.DataFrame(events).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    audit_frame = pd.DataFrame(audits).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    source_frame = pd.DataFrame(sources).sort_values(
        ["ticker", "trade_date", "source_kind"], kind="stable"
    ).reset_index(drop=True)
    error_frame = pd.DataFrame(errors, columns=["ticker", "trade_date", "error"]).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if len(event_frame) != len(records) or len(audit_frame) != len(records) or not error_frame.empty:
        coverage = pd.DataFrame()
        distinctness = pd.DataFrame()
        monthly = pd.DataFrame()
        gate = {
            "passed": False,
            "coverage_pass": False,
            "distinctness_pass": False,
            "frequency_pass": False,
            "source_session_errors": int(len(error_frame)),
        }
    else:
        coverage, distinctness, evaluated = evaluate_data_gate(event_frame)
        monthly = evaluated["monthly"]
        gate = evaluated["summary"]
        gate["source_session_errors"] = 0
    environment = runtime_environment()
    manifest: dict[str, Any] = {
        "schema": "option_parity_pressure_v1_outcome_free_data_gate",
        "status": "PASS_DATA_GATE" if gate["passed"] else "REJECTED_DATA_GATE",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "git_commit": git_commit,
        "scope": {"start_date": START_DATE, "end_date": END_DATE, "sessions": len(records)},
        "tickers": list(TICKERS),
        "feature_contract": {
            "clocks": list(CLOCKS),
            "moneyness_radius_bps": MONEYNESS_RADIUS_BPS,
            "minimum_common_strikes": MIN_COMMON_STRIKES,
            "feature": "median_K(parity_z_1035-parity_z_1030)",
        },
        "data_gate": gate,
        "rows": int(len(event_frame)),
        "valid_rows": int(event_frame["parity_valid"].astype(bool).sum()) if not event_frame.empty else 0,
        "source_inventory_rows": int(len(source_frame)),
        "errors": errors,
        "outcome_accessed": False,
        "labels_built": False,
        "holdout_2026_opened": False,
        "production_modified": False,
        "capacity_manifest_sha256": CAPACITY_HASHES["manifest.json"],
        "capacity_manifest_payload_sha256": json_hash(capacity_manifest),
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "scope_amendment_sha256": sha256_file(SCOPE_AMENDMENT),
        "runner_sha256": sha256_file(__file__),
        "native_quote_provenance": native_provenance,
        "runtime_environment": environment,
        "runtime_environment_sha256": json_hash(environment),
    }
    publish_output(
        output_dir,
        event_frame,
        audit_frame,
        source_frame,
        coverage,
        distinctness,
        monthly,
        error_frame,
        manifest,
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--underlying-root",
        type=Path,
        default=Path("D:/ThetaData/data_underlying_derived"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = run(args.underlying_root, args.output_dir, args.workers)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
