"""Outcome-free census of wall-state spot timestamp semantics.

The sealed wall-state view was built from option snapshots.  This audit checks
whether each stored wall ``spot`` denotes the derived-underlying minute open at
the wall timestamp, or the immediately preceding minute open.  It reads no
labels, returns, option payoffs, or post-decision prices.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.surface_flow_features import validate_underlying_session  # noqa: E402
from neural.jepa.wall_surface_flow_environment import (  # noqa: E402
    assert_runtime_lock,
    canonical_hash,
)


START_DATE = "20220801"
END_DATE = "20251231"
TICKERS = ("SPXW", "QQQ", "SPY")
SPOT_TOLERANCE_BPS = 0.001
MAX_WORKERS = 16
EXPECTED_INPUT_HASHES = {
    "walls": "94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef",
    "manifest": "5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88",
}
EXPECTED_MANIFEST_SESSIONS = 2519
EXPECTED_WALL_SESSIONS = 2518
EXPECTED_WALL_ROWS = 120864
EXPECTED_CLASS_COUNTS = {
    "exact_t": 2516,
    "hybrid_spot_tm1": 2,
    "unresolved": 0,
}
EXPECTED_HYBRID_KEYS = (("QQQ", "20221230"), ("SPY", "20221230"))
ENVIRONMENT_LOCK = PROJECT_ROOT / "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
WALL_COLUMNS = ("ticker", "trade_date", "dt", "minute", "spot")
UNDERLYING_COLUMNS = (
    "symbol", "date", "timestamp", "open", "high", "low", "close", "tick_count",
)
CENSUS_COLUMNS = (
    "ticker",
    "trade_date",
    "classification",
    "wall_rows",
    "exact_t_rows",
    "exact_tm1_rows",
    "exact_both_rows",
    "mismatched_t_rows",
    "mismatched_tm1_rows",
    "spot_diff_t_bps_max",
    "spot_diff_tm1_bps_max",
    "underlying_path",
    "underlying_sha256",
    "underlying_rows",
    "underlying_required_window_minutes",
    "expected_underlying_required_window_minutes",
    "underlying_min_research_tick_count",
    "underlying_out_of_scope_invalid_rows",
)


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def current_git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def assert_authoritative_code_state() -> str:
    tracked = (
        "neural/jepa/audit_wall_spot_semantics_v1.py",
        "neural/jepa/surface_flow_features.py",
        "neural/jepa/wall_surface_flow_environment.py",
        "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
    )
    for relative in tracked:
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
            raise AssertionError(f"authoritative census requires committed clean code: {relative}: {dirty}")
    return current_git_commit()


def _normalize_date(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\D", "", regex=True).str[:8]


def _strict_true(series: pd.Series, *, label: str) -> pd.Series:
    normalized = series.astype(str).str.strip().str.lower()
    allowed = {"true", "false", "1", "0"}
    invalid = ~normalized.isin(allowed)
    if bool(invalid.any()):
        raise AssertionError(f"{label} contains invalid boolean values")
    return normalized.isin({"true", "1"})


def read_wall_view(path: str | Path) -> pd.DataFrame:
    available = set(pq.ParquetFile(path).schema_arrow.names)
    missing = sorted(set(WALL_COLUMNS).difference(available))
    if missing:
        raise KeyError(f"wall view missing required columns: {missing}")
    walls = pd.read_parquet(path, columns=list(WALL_COLUMNS))
    walls["ticker"] = walls["ticker"].astype(str).str.upper()
    walls["trade_date"] = _normalize_date(walls["trade_date"])
    walls["dt"] = pd.to_datetime(walls["dt"], errors="coerce")
    walls["minute"] = pd.to_numeric(walls["minute"], errors="coerce")
    walls["spot"] = pd.to_numeric(walls["spot"], errors="coerce")
    if walls.empty:
        raise AssertionError("wall view is empty")
    if not set(walls["ticker"].unique()).issubset(TICKERS):
        raise AssertionError("wall view contains an unexpected ticker")
    if walls["trade_date"].gt(END_DATE).any() or walls["trade_date"].str.startswith("2026").any():
        raise AssertionError("wall view must not contain 2026")
    walls = walls[walls["trade_date"].between(START_DATE, END_DATE, inclusive="both")].copy()
    if walls.empty:
        raise AssertionError("wall view has no rows in the frozen 2022-08..2025-12 scope")
    if walls["dt"].isna().any() or not walls["dt"].dt.strftime("%Y%m%d").eq(walls["trade_date"]).all():
        raise AssertionError("wall timestamps are missing or disagree with trade_date")
    boundary = walls["dt"].dt.second.eq(0) & walls["dt"].dt.microsecond.eq(0)
    if not bool(boundary.all()):
        raise AssertionError("wall timestamps must be exact minute boundaries")
    expected_minute = walls["dt"].dt.hour * 60 + walls["dt"].dt.minute
    if walls["minute"].isna().any() or not walls["minute"].eq(expected_minute).all():
        raise AssertionError("wall minute disagrees with wall timestamp")
    if not np.isfinite(walls["spot"].to_numpy(dtype=float)).all() or walls["spot"].le(0.0).any():
        raise AssertionError("wall spot must be finite and positive")
    if walls.duplicated(["ticker", "trade_date", "dt"]).any():
        raise AssertionError("wall view contains duplicate ticker/date/timestamp keys")
    return walls.sort_values(["ticker", "trade_date", "dt"], kind="stable").reset_index(drop=True)


def select_manifest_sessions(path: str | Path) -> pd.DataFrame:
    required = {
        "ticker", "trade_date", "expiration", "dte_days", "expiry_mode",
        "has_underlying", "underlying_path",
    }
    manifest = pd.read_csv(path, dtype={"trade_date": str, "expiration": str})
    missing = sorted(required.difference(manifest.columns))
    if missing:
        raise KeyError(f"source manifest missing required columns: {missing}")
    work = manifest.copy()
    work["ticker"] = work["ticker"].astype(str).str.upper()
    work["trade_date"] = _normalize_date(work["trade_date"])
    work["expiration"] = _normalize_date(work["expiration"])
    work["dte_days"] = pd.to_numeric(work["dte_days"], errors="coerce")
    work["expiry_mode"] = work["expiry_mode"].astype(str).str.strip().str.lower()
    has_underlying = _strict_true(work["has_underlying"], label="has_underlying")
    scope = (
        work["ticker"].isin(TICKERS)
        & work["trade_date"].between(START_DATE, END_DATE, inclusive="both")
        & work["dte_days"].eq(0)
        & work["expiry_mode"].eq("zero_dte")
        & has_underlying
    )
    selected = work.loc[scope, ["ticker", "trade_date", "expiration", "underlying_path"]].copy()
    if selected.empty:
        raise AssertionError("source manifest has no in-scope 0DTE sessions")
    if not selected["expiration"].eq(selected["trade_date"]).all():
        raise AssertionError("selected sessions require expiration == trade_date")
    if selected["trade_date"].str.startswith("2026").any():
        raise AssertionError("selected manifest sessions must not include 2026")
    if selected.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("source manifest contains duplicate in-scope session keys")
    if selected["underlying_path"].isna().any() or selected["underlying_path"].astype(str).str.strip().eq("").any():
        raise AssertionError("selected manifest sessions require underlying_path")
    return selected.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)


def join_wall_sessions(walls: pd.DataFrame, sessions: pd.DataFrame) -> list[tuple[dict[str, Any], pd.DataFrame]]:
    wall_keys = walls[["ticker", "trade_date"]].drop_duplicates()
    joined = wall_keys.merge(
        sessions[["ticker", "trade_date", "underlying_path"]],
        on=["ticker", "trade_date"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if not joined["_merge"].eq("both").all() or joined["underlying_path"].isna().any():
        missing = joined.loc[joined["_merge"].ne("both"), ["ticker", "trade_date"]].to_dict("records")
        raise AssertionError(f"wall sessions are absent from the source manifest: {missing[:10]}")
    path_by_key = {
        (str(row.ticker), str(row.trade_date)): str(row.underlying_path)
        for row in joined.itertuples(index=False)
    }
    return [
        (
            {
                "ticker": str(ticker),
                "trade_date": str(trade_date),
                "underlying_path": path_by_key[(str(ticker), str(trade_date))],
            },
            part.copy(),
        )
        for (ticker, trade_date), part in walls.groupby(
            ["ticker", "trade_date"], observed=True, sort=True
        )
    ]


def read_underlying(path: str | Path) -> pd.DataFrame:
    available = set(pq.ParquetFile(path).schema_arrow.names)
    missing = sorted(set(UNDERLYING_COLUMNS).difference(available))
    if missing:
        raise KeyError(f"derived underlying missing required columns: {missing}")
    return pd.read_parquet(path, columns=list(UNDERLYING_COLUMNS))


def audit_session(record: dict[str, Any], walls: pd.DataFrame) -> dict[str, Any]:
    ticker = str(record["ticker"])
    trade_date = str(record["trade_date"])
    underlying_path = Path(str(record["underlying_path"]))
    source_hash = sha256_file(underlying_path)
    underlying = read_underlying(underlying_path)
    validated, validation = validate_underlying_session(
        underlying,
        expected_ticker=ticker,
        expected_trade_date=trade_date,
    )
    if sha256_file(underlying_path) != source_hash:
        raise AssertionError(f"derived underlying changed while being read: {underlying_path}")
    opens = validated.set_index("bar_start")["open"]
    wall_dt = pd.DatetimeIndex(walls["dt"])
    open_t = opens.reindex(wall_dt)
    open_tm1 = opens.reindex(wall_dt - pd.Timedelta(minutes=1))
    if open_t.isna().any() or open_tm1.isna().any():
        raise AssertionError("wall timestamp has no exact t or t-1 derived-underlying open")
    spot = walls["spot"].to_numpy(dtype=float)
    diff_t = np.abs(open_t.to_numpy(dtype=float) - spot) / spot * 10_000.0
    diff_tm1 = np.abs(open_tm1.to_numpy(dtype=float) - spot) / spot * 10_000.0
    if not np.isfinite(diff_t).all() or not np.isfinite(diff_tm1).all():
        raise AssertionError("spot semantic comparison produced a non-finite difference")
    exact_t = diff_t <= SPOT_TOLERANCE_BPS
    exact_tm1 = diff_tm1 <= SPOT_TOLERANCE_BPS
    if bool(exact_t.all()):
        classification = "exact_t"
    elif bool(exact_tm1.all()):
        classification = "hybrid_spot_tm1"
    else:
        classification = "unresolved"
    return {
        "ticker": ticker,
        "trade_date": trade_date,
        "classification": classification,
        "wall_rows": int(len(walls)),
        "exact_t_rows": int(exact_t.sum()),
        "exact_tm1_rows": int(exact_tm1.sum()),
        "exact_both_rows": int((exact_t & exact_tm1).sum()),
        "mismatched_t_rows": int((~exact_t).sum()),
        "mismatched_tm1_rows": int((~exact_tm1).sum()),
        "spot_diff_t_bps_max": float(diff_t.max()),
        "spot_diff_tm1_bps_max": float(diff_tm1.max()),
        "underlying_path": str(underlying_path),
        "underlying_sha256": source_hash,
        "underlying_rows": int(validation["underlying_rows"]),
        "underlying_required_window_minutes": int(validation["underlying_required_window_minutes"]),
        "expected_underlying_required_window_minutes": int(
            validation["expected_underlying_required_window_minutes"]
        ),
        "underlying_min_research_tick_count": float(validation["underlying_min_research_tick_count"]),
        "underlying_out_of_scope_invalid_rows": int(validation["underlying_out_of_scope_invalid_rows"]),
    }


def process_sessions(
    jobs: list[tuple[dict[str, Any], pd.DataFrame]],
    workers: int,
) -> pd.DataFrame:
    if not 1 <= int(workers) <= MAX_WORKERS:
        raise ValueError(f"workers must be within 1..{MAX_WORKERS}")
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    if workers == 1:
        for record, walls in jobs:
            try:
                rows.append(audit_session(record, walls))
            except Exception as exc:
                errors.append(
                    {
                        "ticker": str(record["ticker"]),
                        "trade_date": str(record["trade_date"]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(audit_session, record, walls): record
                for record, walls in jobs
            }
            for future in as_completed(futures):
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
    if errors:
        errors.sort(key=lambda row: (row["ticker"], row["trade_date"]))
        raise AssertionError(f"wall spot semantic source errors: {errors[:10]}")
    census = pd.DataFrame(rows, columns=list(CENSUS_COLUMNS))
    if census.empty or census.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("spot semantics census is empty or has duplicate session keys")
    return census.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)


def evaluate_contract(census: pd.DataFrame, *, manifest_sessions: int, wall_rows: int) -> dict[str, Any]:
    counts = {
        label: int(census["classification"].eq(label).sum())
        for label in EXPECTED_CLASS_COUNTS
    }
    unknown = sorted(set(census["classification"]).difference(EXPECTED_CLASS_COUNTS))
    hybrid_keys = sorted(
        (str(row.ticker), str(row.trade_date))
        for row in census.loc[
            census["classification"].eq("hybrid_spot_tm1"), ["ticker", "trade_date"]
        ].itertuples(index=False)
    )
    expected_hybrid_keys = sorted(EXPECTED_HYBRID_KEYS)
    grid_complete = census["underlying_required_window_minutes"].eq(
        census["expected_underlying_required_window_minutes"]
    ).all()
    census_wall_rows = int(census["wall_rows"].sum())
    passed = bool(
        manifest_sessions == EXPECTED_MANIFEST_SESSIONS
        and len(census) == EXPECTED_WALL_SESSIONS
        and wall_rows == EXPECTED_WALL_ROWS
        and census_wall_rows == wall_rows
        and not unknown
        and counts == EXPECTED_CLASS_COUNTS
        and hybrid_keys == expected_hybrid_keys
        and bool(grid_complete)
    )
    return {
        "passed": passed,
        "manifest_sessions": int(manifest_sessions),
        "expected_manifest_sessions": EXPECTED_MANIFEST_SESSIONS,
        "wall_sessions": int(len(census)),
        "expected_wall_sessions": EXPECTED_WALL_SESSIONS,
        "wall_rows": int(wall_rows),
        "census_wall_rows": census_wall_rows,
        "expected_wall_rows": EXPECTED_WALL_ROWS,
        "classification_counts": counts,
        "expected_classification_counts": EXPECTED_CLASS_COUNTS,
        "unknown_classifications": unknown,
        "hybrid_keys": [list(key) for key in hybrid_keys],
        "expected_hybrid_keys": [list(key) for key in expected_hybrid_keys],
        "underlying_grid_complete": bool(grid_complete),
    }


def _underlying_inventory_hash(census: pd.DataFrame) -> str:
    inventory = [
        {
            "ticker": str(row.ticker),
            "trade_date": str(row.trade_date),
            "path": str(row.underlying_path),
            "sha256": str(row.underlying_sha256),
        }
        for row in census.sort_values(["ticker", "trade_date"], kind="stable").itertuples(index=False)
    ]
    return canonical_hash(inventory)


def run_census(
    *,
    walls_path: str | Path,
    manifest_path: str | Path,
    output_dir: str | Path,
    workers: int,
    enforce_input_hashes: bool = True,
    enforce_clean_code: bool = True,
    enforce_expected_contract: bool = True,
) -> dict[str, Any]:
    walls_path = Path(walls_path)
    manifest_path = Path(manifest_path)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"immutable output target already exists: {output_dir}")
    staging_dir = output_dir.with_name(f"{output_dir.name}.staging")
    if staging_dir.exists():
        raise FileExistsError(f"staging target already exists; inspect manually: {staging_dir}")
    input_hashes = {
        "walls": sha256_file(walls_path),
        "manifest": sha256_file(manifest_path),
    }
    if enforce_input_hashes and input_hashes != EXPECTED_INPUT_HASHES:
        raise AssertionError(f"sealed input hash mismatch: {input_hashes}")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    build_commit = assert_authoritative_code_state() if enforce_clean_code else current_git_commit()
    walls = read_wall_view(walls_path)
    sessions = select_manifest_sessions(manifest_path)
    jobs = join_wall_sessions(walls, sessions)
    census = process_sessions(jobs, int(workers))
    observed_after_read = {
        "walls": sha256_file(walls_path),
        "manifest": sha256_file(manifest_path),
    }
    if observed_after_read != input_hashes:
        raise AssertionError("sealed wall or source-manifest input changed while being read")
    if enforce_clean_code and assert_authoritative_code_state() != build_commit:
        raise AssertionError("git commit changed while the authoritative census was running")
    gate = evaluate_contract(census, manifest_sessions=len(sessions), wall_rows=len(walls))
    if enforce_expected_contract and not gate["passed"]:
        raise AssertionError(f"frozen wall spot semantics contract failed: {gate}")
    staging_dir.mkdir(parents=True, exist_ok=False)
    census_path = staging_dir / "census.csv"
    manifest_out_path = staging_dir / "manifest.json"
    census.to_csv(census_path, index=False, lineterminator="\n")
    code_hashes = {
        "auditor": sha256_file(__file__),
        "underlying_validator": sha256_file(Path(__file__).with_name("surface_flow_features.py")),
        "runtime_validator": sha256_file(Path(__file__).with_name("wall_surface_flow_environment.py")),
    }
    manifest_out = {
        "schema": "wall_spot_semantics_census_v1",
        "status": "PASS_WALL_SPOT_SEMANTICS_CENSUS" if gate["passed"] else "REJECTED_WALL_SPOT_SEMANTICS_CENSUS",
        "outcome_free": True,
        "production_modified": False,
        "holdout_2026_used": False,
        "date_range": [START_DATE, END_DATE],
        "spot_tolerance_bps": SPOT_TOLERANCE_BPS,
        "git_commit": build_commit,
        "input_hashes": input_hashes,
        "code_hashes": code_hashes,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "underlying_source_files": int(len(census)),
        "underlying_source_inventory_sha256": _underlying_inventory_hash(census),
        "census": str(output_dir / census_path.name),
        "census_sha256": sha256_file(census_path),
        "census_rows": int(len(census)),
        "contract": gate,
        "args": {
            "walls": str(walls_path),
            "manifest": str(manifest_path),
            "output_dir": str(output_dir),
            "workers": int(workers),
        },
    }
    manifest_out_path.write_text(
        json.dumps(manifest_out, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    staging_dir.rename(output_dir)
    return manifest_out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--walls", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = run_census(
        walls_path=args.walls,
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        workers=int(args.workers),
    )
    print(json.dumps(manifest, indent=2, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
