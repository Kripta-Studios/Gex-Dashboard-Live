"""Build the sealed 2022-2025 per-strike GEX/DEX wall-state dataset."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from neural.jepa.wall_state_features import (
    add_wall_persistence,
    assert_wall_state_schema,
    compute_wall_states,
)


TICKERS = ("SPXW", "QQQ", "SPY")
PHYSICAL_END_DATE = "20251231"
MAX_WORKERS = 16
EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88"
)
EXPECTED_EVENT_VIEW_SHA256 = (
    "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408"
)
GREEK_COLUMNS = (
    "strike", "right", "underlying_price", "underlying_timestamp",
    "implied_vol", "timestamp",
)
OI_COLUMNS = ("strike", "right", "open_interest")
KEY_COLUMNS = ("ticker", "trade_date", "minute")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _available_parquet_columns(path: str | Path) -> set[str]:
    import pyarrow.parquet as pq

    return set(pq.ParquetFile(path).schema.names)


def read_required_parquet(
    path: str | Path,
    requested: Iterable[str],
    required: Iterable[str],
) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    available = _available_parquet_columns(path)
    missing = set(required).difference(available)
    if missing:
        raise KeyError(f"{path} missing required columns: {sorted(missing)}")
    columns = [column for column in requested if column in available]
    return pd.read_parquet(path, columns=columns)


def normalize_right(series: pd.Series) -> pd.Series:
    return series.astype(str).str.upper().str[0].map({"C": "CALL", "P": "PUT"})


def filter_manifest(
    manifest: pd.DataFrame,
    *,
    tickers: Iterable[str] = TICKERS,
    start_date: str = "20220101",
    end_date: str = PHYSICAL_END_DATE,
) -> pd.DataFrame:
    required = {
        "ticker", "trade_date", "expiration", "dte_days", "expiry_mode",
        "has_greeks", "has_oi", "greeks_path", "oi_path",
    }
    missing = required.difference(manifest.columns)
    if missing:
        raise KeyError(f"manifest missing columns: {sorted(missing)}")
    if str(end_date) > PHYSICAL_END_DATE:
        raise ValueError(f"end_date cannot exceed sealed cutoff {PHYSICAL_END_DATE}")
    out = manifest.copy()
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["trade_date"] = out["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(8)
    out["expiration"] = out["expiration"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(8)
    dte = pd.to_numeric(out["dte_days"], errors="coerce")
    allowed = {str(ticker).upper() for ticker in tickers}
    truthy_greeks = out["has_greeks"].astype(str).str.lower().isin({"true", "1"})
    truthy_oi = out["has_oi"].astype(str).str.lower().isin({"true", "1"})
    out = out[
        out["ticker"].isin(allowed)
        & out["trade_date"].between(str(start_date), str(end_date))
        & out["trade_date"].eq(out["expiration"])
        & dte.eq(0)
        & out["expiry_mode"].astype(str).eq("zero_dte")
        & truthy_greeks
        & truthy_oi
    ].copy()
    if out["trade_date"].str.startswith("2026").any():
        raise AssertionError("2026 entered filtered wall-state manifest")
    duplicates = out.duplicated(["ticker", "trade_date"], keep=False)
    if duplicates.any():
        keys = out.loc[duplicates, ["ticker", "trade_date"]].drop_duplicates().to_dict("records")
        raise AssertionError(f"duplicate ticker/session rows in manifest: {keys[:10]}")
    return out.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)


def select_preflight_sessions(manifest: pd.DataFrame) -> pd.DataFrame:
    selected = []
    for ticker in TICKERS:
        part = manifest[manifest["ticker"].eq(ticker)]
        if part.empty:
            raise AssertionError(f"no preflight session available for {ticker}")
        selected.append(part.iloc[len(part) // 2])
    return pd.DataFrame(selected).reset_index(drop=True)


def load_wall_chain(record: dict[str, Any] | pd.Series) -> pd.DataFrame:
    row = dict(record)
    greeks = read_required_parquet(
        row["greeks_path"],
        GREEK_COLUMNS,
        ("strike", "right", "underlying_price", "implied_vol"),
    )
    if "timestamp" in greeks:
        quote_dt = pd.to_datetime(greeks["timestamp"], errors="coerce")
        if "underlying_timestamp" in greeks:
            quote_dt = quote_dt.fillna(pd.to_datetime(greeks["underlying_timestamp"], errors="coerce"))
    elif "underlying_timestamp" in greeks:
        quote_dt = pd.to_datetime(greeks["underlying_timestamp"], errors="coerce")
    else:
        raise KeyError(f"{row['greeks_path']} has no observable timestamp")
    greeks = greeks.assign(quote_dt=quote_dt).dropna(subset=["quote_dt"]).copy()
    greeks["dt"] = greeks["quote_dt"].dt.floor("min")
    greeks["right"] = normalize_right(greeks["right"])
    greeks["strike"] = pd.to_numeric(greeks["strike"], errors="coerce")

    oi = read_required_parquet(row["oi_path"], OI_COLUMNS, OI_COLUMNS)
    oi["right"] = normalize_right(oi["right"])
    oi["strike"] = pd.to_numeric(oi["strike"], errors="coerce")
    oi["open_interest"] = pd.to_numeric(oi["open_interest"], errors="coerce")
    oi = oi.dropna(subset=["strike", "right", "open_interest"])
    oi = oi[oi["open_interest"] > 0.0]
    if oi.empty:
        raise AssertionError(f"no positive open interest in {row['oi_path']}")
    oi = oi.groupby(["strike", "right"], observed=True, sort=True)["open_interest"].max().reset_index()
    chain = greeks.merge(oi, on=["strike", "right"], how="inner", validate="many_to_one")
    if chain.empty:
        raise AssertionError(f"greeks/OI join empty for {row['ticker']} {row['trade_date']}")
    chain = chain.sort_values(["quote_dt", "strike", "right"], kind="stable")
    return chain[["dt", "strike", "right", "underlying_price", "implied_vol", "open_interest"]].reset_index(drop=True)


def build_session(record: dict[str, Any] | pd.Series) -> pd.DataFrame:
    row = dict(record)
    chain = load_wall_chain(row)
    states = compute_wall_states(chain)
    if states.empty:
        raise AssertionError(f"no wall states for {row['ticker']} {row['trade_date']}")
    states.insert(0, "ticker", str(row["ticker"]).upper())
    states.insert(1, "trade_date", str(row["trade_date"]))
    states = add_wall_persistence(states)
    assert_wall_state_schema(states)
    return states


def process_sessions(records: list[dict[str, Any]], workers: int) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    if not 1 <= int(workers) <= MAX_WORKERS:
        raise ValueError(f"workers must be within 1..{MAX_WORKERS}")
    frames: list[pd.DataFrame] = []
    errors: list[dict[str, str]] = []

    def keep_result(record: dict[str, Any], result: pd.DataFrame | Exception) -> None:
        if isinstance(result, Exception):
            errors.append({
                "ticker": str(record.get("ticker", "")),
                "trade_date": str(record.get("trade_date", "")),
                "error": f"{type(result).__name__}: {result}",
            })
        else:
            frames.append(result)

    if int(workers) == 1:
        for index, record in enumerate(records, start=1):
            try:
                keep_result(record, build_session(record))
            except Exception as exc:  # session failures are persisted in the manifest
                keep_result(record, exc)
            if index % 25 == 0 or index == len(records):
                print(f"[WALL_STATE] sessions={index}/{len(records)} rows={sum(map(len, frames)):,} errors={len(errors)}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=int(workers)) as pool:
            pending = {pool.submit(build_session, record): record for record in records}
            for index, future in enumerate(as_completed(pending), start=1):
                record = pending[future]
                try:
                    keep_result(record, future.result())
                except Exception as exc:
                    keep_result(record, exc)
                if index % 25 == 0 or index == len(pending):
                    print(f"[WALL_STATE] sessions={index}/{len(pending)} rows={sum(map(len, frames)):,} errors={len(errors)}", flush=True)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not out.empty:
        out = out.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)
        assert_wall_state_schema(out)
        if out.duplicated(list(KEY_COLUMNS)).any():
            raise AssertionError("duplicate wall-state keys")
    return out, errors


def audit_wall_frame(frame: pd.DataFrame, requested_sessions: int) -> dict[str, Any]:
    if frame.empty:
        raise AssertionError("wall-state build is empty")
    assert_wall_state_schema(frame)
    active_columns = [
        "wall_call_gamma_family_active_strikes", "wall_put_gamma_family_active_strikes",
        "wall_call_delta_family_active_strikes", "wall_put_delta_family_active_strikes",
    ]
    below_two = {column: int((pd.to_numeric(frame[column], errors="coerce") < 2).sum()) for column in active_columns}
    finite_spot = pd.to_numeric(frame["spot"], errors="coerce")
    expected_rows = int(requested_sessions) * 48
    result = {
        "rows": int(len(frame)),
        "sessions": int(frame[list(KEY_COLUMNS[:2])].drop_duplicates().shape[0]),
        "expected_grid_rows": expected_rows,
        "grid_coverage": float(len(frame) / expected_rows) if expected_rows else 0.0,
        "date_min": str(frame["trade_date"].min()),
        "date_max": str(frame["trade_date"].max()),
        "rows_by_ticker": frame.groupby("ticker", observed=True).size().astype(int).to_dict(),
        "finite_positive_spot": bool(np.isfinite(finite_spot).all() and finite_spot.gt(0.0).all()),
        "family_rows_below_two_active_strikes": below_two,
        "delta_gamma_same_wall_share": {
            side: float(np.isclose(
                frame[f"wall_{side}_delta_strike"], frame[f"wall_{side}_gamma_strike"],
                rtol=0.0, atol=1e-9, equal_nan=False,
            ).mean())
            for side in ("call", "put")
        },
        "unique_delta_wall_strikes": {
            side: int(frame[f"wall_{side}_delta_strike"].nunique(dropna=True))
            for side in ("call", "put")
        },
    }
    if not result["finite_positive_spot"]:
        raise AssertionError("non-finite/non-positive spot in wall-state output")
    return result


def audit_event_coverage(walls: pd.DataFrame, event_path: str | Path) -> dict[str, Any]:
    available = _available_parquet_columns(event_path)
    missing = set(KEY_COLUMNS).difference(available)
    if missing:
        raise KeyError(f"event view missing coverage keys: {sorted(missing)}")
    event_columns = list(KEY_COLUMNS) + (["spot"] if "spot" in available else [])
    events = pd.read_parquet(event_path, columns=event_columns)
    events["ticker"] = events["ticker"].astype(str).str.upper()
    events["trade_date"] = events["trade_date"].astype(str)
    events = events[
        events["ticker"].isin(TICKERS)
        & events["trade_date"].le(PHYSICAL_END_DATE)
    ].copy()
    aggregation = {"spot": "median"} if "spot" in events else {}
    event_keys = events.groupby(list(KEY_COLUMNS), observed=True, as_index=False).agg(aggregation)
    wall_keys = walls[list(KEY_COLUMNS) + ["spot"]].rename(columns={"spot": "wall_spot"})
    joined = event_keys.merge(wall_keys, on=list(KEY_COLUMNS), how="left", validate="one_to_one")
    joined["covered"] = joined["wall_spot"].notna()
    overall = float(joined["covered"].mean()) if len(joined) else 0.0
    by_ticker = joined.groupby("ticker", observed=True)["covered"].mean().astype(float).to_dict()
    result: dict[str, Any] = {
        "event_unique_keys": int(len(event_keys)),
        "covered_keys": int(joined["covered"].sum()),
        "coverage_overall": overall,
        "coverage_by_ticker": by_ticker,
    }
    if "spot" in joined:
        valid = joined["covered"] & joined["spot"].notna() & joined["spot"].gt(0.0)
        diff = ((joined.loc[valid, "wall_spot"] - joined.loc[valid, "spot"]).abs() / joined.loc[valid, "spot"] * 10_000.0)
        result["spot_compared_rows"] = int(valid.sum())
        result["spot_diff_bps_max"] = float(diff.max()) if len(diff) else None
        result["spot_diff_bps_p99"] = float(diff.quantile(0.99)) if len(diff) else None
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--event-view", default="")
    parser.add_argument("--start-date", default="20220101")
    parser.add_argument("--end-date", default=PHYSICAL_END_DATE)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--allow-input-hash-mismatch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest)
    source_sha = sha256_file(manifest_path)
    if not args.allow_input_hash_mismatch and source_sha != EXPECTED_SOURCE_MANIFEST_SHA256:
        raise AssertionError(f"source manifest hash mismatch: {source_sha}")
    event_sha = sha256_file(args.event_view) if args.event_view else None
    if args.event_view and not args.allow_input_hash_mismatch and event_sha != EXPECTED_EVENT_VIEW_SHA256:
        raise AssertionError(f"event view hash mismatch: {event_sha}")

    manifest = pd.read_csv(manifest_path, dtype={"trade_date": str, "expiration": str})
    filtered = filter_manifest(manifest, start_date=args.start_date, end_date=args.end_date)
    selected = select_preflight_sessions(filtered) if args.preflight else filtered
    walls, errors = process_sessions(selected.to_dict("records"), args.workers)
    audit = audit_wall_frame(walls, len(selected))
    coverage = audit_event_coverage(walls, args.event_view) if args.event_view else None

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / ("wall_state_preflight.parquet" if args.preflight else "wall_state.parquet")
    walls.to_parquet(output_path, index=False)
    metadata = {
        "schema": "wall_state_gex_dex_v1",
        "preflight": bool(args.preflight),
        "production_modified": False,
        "physical_cutoff": PHYSICAL_END_DATE,
        "source_manifest": str(manifest_path),
        "source_manifest_sha256": source_sha,
        "event_view": str(args.event_view) if args.event_view else None,
        "event_view_sha256": event_sha,
        "builder_sha256": sha256_file(__file__),
        "feature_module_sha256": sha256_file(Path(__file__).with_name("wall_state_features.py")),
        "output": str(output_path),
        "output_sha256": sha256_file(output_path),
        "requested_sessions": int(len(selected)),
        "errors": errors,
        "audit": audit,
        "event_coverage": coverage,
        "args": vars(args),
    }
    metadata_path = output_dir / ("preflight_manifest.json" if args.preflight else "manifest.json")
    metadata_path.write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(metadata, indent=2, allow_nan=False), flush=True)
    if errors:
        return 2
    if args.preflight:
        if audit["sessions"] != 3 or audit["grid_coverage"] < 0.98:
            return 3
        if any(count > 0 for count in audit["family_rows_below_two_active_strikes"].values()):
            return 4
    elif coverage:
        if coverage["coverage_overall"] < 0.99:
            return 5
        if min(coverage["coverage_by_ticker"].values(), default=0.0) < 0.98:
            return 6
        if coverage.get("spot_diff_bps_max") is not None and coverage["spot_diff_bps_max"] > 1.0:
            return 7
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
