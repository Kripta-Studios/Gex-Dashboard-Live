"""Build the outcome-free ``WALL_SURFACE_FLOW_AT_TOUCH_V1`` feature dataset.

The builder reads the already sealed wall/event views and exact 0DTE ThetaData
option OHLC/Greeks files.  It never reads option outcomes or future underlying
prices.  Every raw file that can affect this dataset or its later physical
labels is content-hashed into a deterministic provenance inventory.
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

from neural.jepa.surface_flow_features import (  # noqa: E402
    CONTROL_FEATURES,
    END_DATE,
    FLOW_FEATURES,
    KEY_COLUMNS,
    START_DATE,
    attach_completed_underlying_controls,
    attach_flow_features,
    last_scheduled_decision_minute,
    make_touch_candidates,
    prepare_completed_bar_flow,
    validate_underlying_session,
)
from neural.jepa.build_wall_exact_greek_repair_artifacts import (  # noqa: E402
    apply_repair_overlay,
    load_repair_bundle,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402


TICKERS = ("SPXW", "QQQ", "SPY")
NATIVE_QUOTE_FIRST_MINUTE = 10 * 60 + 20
MAX_WORKERS = 16
EXPECTED_SESSION_COUNT = 2519
EXPECTED_SESSION_KEY_SHA256 = "ac7200fd96f2ef9afc2f9f09eff18804497a2f975a7454cccf5ed1c935653057"
EXPECTED_NATIVE_QUOTE_SESSIONS = 1441
EXPECTED_NATIVE_QUOTE_KEY_SHA256 = "4d4335005bb1ad29dd9f59a873a8902edcf17f1eb64c006792b29b57dea9a579"
EXPECTED_INPUT_HASHES = {
    "walls": "94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef",
    "events": "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408",
    "manifest": "5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88",
}
# The committed V1R2 bundle is indivisible.  An authoritative build binds all
# three immutable files rather than trusting hashes self-declared by a mutable
# repair manifest.
EXPECTED_EXACT_GREEK_REPAIR_HASHES = {
    "manifest": "47dffb255113a6604c33011e1dcd7c5e51301c3a4c61100099c8ed4f5a8aec5a",
    "wall_repair": "69a3d33080e5682b02070c6c1085ba6b1db7818cae8bd6f756994da139b9487d",
    "event_control_repair": "937aa95e4aadbc9f639a96a68f1390f118bcb22c01d259bba2ff88014340051e",
}
ENVIRONMENT_LOCK = PROJECT_ROOT / "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
GREEK_REQUIRED_COLUMNS = (
    "symbol", "expiration", "trade_date", "interval_used", "right", "strike", "bid", "ask",
)
GREEK_OPTIONAL_COLUMNS = ("timestamp", "underlying_timestamp")
NATIVE_QUOTE_COLUMNS = (
    "symbol", "expiration", "trade_date", "timestamp", "right", "strike", "bid", "ask",
)
OHLC_COLUMNS = (
    "timestamp", "right", "strike", "close", "volume", "count",
    "symbol", "expiration", "trade_date", "interval_used",
)
UNDERLYING_COLUMNS = ("symbol", "date", "timestamp", "open", "high", "low", "close", "tick_count")
EVENT_COLUMNS = (
    "ticker", "trade_date", "minute", "spot",
    "ret_1m_bps", "ret_5m_bps", "ret_15m_bps", "ret_30m_bps",
)


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def feature_hash(columns: tuple[str, ...] | list[str]) -> str:
    payload = json.dumps(list(columns), separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def session_key_hash(frame: pd.DataFrame) -> str:
    ordered = frame.sort_values(["ticker", "trade_date"], kind="stable")
    payload = "".join(
        f"{str(row.ticker)},{str(row.trade_date)}\n"
        for row in ordered[["ticker", "trade_date"]].itertuples(index=False)
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
        "neural/jepa/build_wall_surface_flow_dataset.py",
        "neural/jepa/build_wall_exact_greek_repair_artifacts.py",
        "neural/jepa/build_wall_exact_greek_repair_sidecar.py",
        "neural/jepa/surface_flow_features.py",
        "neural/jepa/wall_state_features.py",
        "neural/jepa/wall_surface_flow_environment.py",
        "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
        "research_papers/JEPA/WALL_SURFACE_FLOW_V1R2_EXACT_SPOT_REPAIR_PREDECLARATION.md",
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
            raise AssertionError(f"authoritative build requires committed clean code: {relative}: {dirty}")
    return current_git_commit()


def assert_committed_artifact(path: Path, label: str) -> None:
    try:
        relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError as exc:
        raise AssertionError(f"{label} must be copied into and committed in the repository: {path}") from exc
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
        raise AssertionError(f"{label} must be committed and clean: {dirty}")


def attach_exact_greek_repair_bundle(
    walls: pd.DataFrame,
    events: pd.DataFrame,
    manifest_path: str | Path,
    *,
    enforce_frozen: bool = True,
    require_committed: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Validate and apply the indivisible V1R2 exact-Greek repair bundle.

    The original wall/event files remain the frozen base inputs. Exactly 96 wall
    keys and the 47 executable event keys for QQQ/SPY 2022-12-30 are replaced in
    memory before touch candidates are constructed. No repaired file can expand
    the historical universe or alter any non-target row.
    """

    manifest_path = Path(manifest_path)
    wall_path = manifest_path.parent / "wall_repair.parquet"
    event_path = manifest_path.parent / "event_control_repair.parquet"
    observed_hashes = {
        "manifest": sha256_file(manifest_path),
        "wall_repair": sha256_file(wall_path),
        "event_control_repair": sha256_file(event_path),
    }
    frozen_hashes_match = observed_hashes == EXPECTED_EXACT_GREEK_REPAIR_HASHES
    if enforce_frozen and not frozen_hashes_match:
        raise AssertionError(
            "frozen exact-Greek repair bundle hash mismatch: "
            f"observed={observed_hashes} expected={EXPECTED_EXACT_GREEK_REPAIR_HASHES}"
        )
    repair_walls, repair_events, repair_manifest = load_repair_bundle(
        manifest_path,
        enforce_frozen=enforce_frozen,
        require_committed=require_committed,
    )
    if list(repair_walls.columns) != list(walls.columns):
        raise AssertionError("wall repair schema/order differs from the frozen base wall view")
    if list(repair_events.columns) != list(events.columns):
        raise AssertionError("event-control repair schema/order differs from the causal base event view")
    repaired_walls = apply_repair_overlay(walls, repair_walls, label="walls")
    repaired_events = apply_repair_overlay(events, repair_events, label="event controls")
    return repaired_walls, repaired_events, {
        "schema": str(repair_manifest.get("schema")),
        "status": str(repair_manifest.get("status")),
        "manifest_path": str(manifest_path),
        "manifest_sha256": observed_hashes["manifest"],
        "wall_repair_path": str(wall_path),
        "wall_repair_sha256": observed_hashes["wall_repair"],
        "event_control_repair_path": str(event_path),
        "event_control_repair_sha256": observed_hashes["event_control_repair"],
        "frozen_hashes_match": bool(frozen_hashes_match),
        "target_sessions": repair_manifest.get("target_sessions"),
        "wall_target_rows": int(repair_manifest.get("wall_target_rows", -1)),
        "full_control_grid_rows": int(repair_manifest.get("full_control_grid_rows", -1)),
        "event_target_rows": int(repair_manifest.get("event_target_rows", -1)),
        "event_target_rows_by_ticker": repair_manifest.get("event_target_rows_by_ticker"),
        "event_target_key_sha256": str(repair_manifest.get("event_target_key_sha256")),
        "build_git_commit": str(repair_manifest.get("git_commit")),
        "historical_provenance": str(repair_manifest.get("historical_provenance")),
        "input_sha256": repair_manifest.get("input_sha256"),
        "builder_sha256": str(repair_manifest.get("builder_sha256")),
        "sidecar_builder_sha256": str(repair_manifest.get("sidecar_builder_sha256")),
        "wall_feature_module_sha256": str(repair_manifest.get("wall_feature_module_sha256")),
        "predeclaration_sha256": str(repair_manifest.get("predeclaration_sha256")),
        "runtime_lock_sha256": str(repair_manifest.get("runtime_lock_sha256")),
        "runtime_environment_sha256": str(repair_manifest.get("runtime_environment_sha256")),
        "maximum_full_wall_control_spot_difference_bps": float(
            repair_manifest.get("maximum_full_wall_control_spot_difference_bps", np.nan)
        ),
        "maximum_event_wall_control_spot_difference_bps": float(
            repair_manifest.get("maximum_event_wall_control_spot_difference_bps", np.nan)
        ),
    }


def read_parquet_columns(path: str | Path, required: tuple[str, ...]) -> pd.DataFrame:
    available = set(pq.ParquetFile(path).schema_arrow.names)
    missing = sorted(set(required).difference(available))
    if missing:
        raise KeyError(f"{path} missing required columns: {missing}")
    return pd.read_parquet(path, columns=list(required))


def read_greeks(path: str | Path) -> pd.DataFrame:
    available = set(pq.ParquetFile(path).schema_arrow.names)
    missing = sorted(set(GREEK_REQUIRED_COLUMNS).difference(available))
    if missing:
        raise KeyError(f"{path} missing required Greek columns: {missing}")
    timestamp_columns = [column for column in ("timestamp", "underlying_timestamp") if column in available]
    if not timestamp_columns:
        raise KeyError(f"{path} has no option or underlying timestamp")
    columns = [
        *[column for column in GREEK_OPTIONAL_COLUMNS if column in available],
        *GREEK_REQUIRED_COLUMNS,
    ]
    return pd.read_parquet(path, columns=list(dict.fromkeys(columns)))


def read_native_quotes(path: str | Path) -> pd.DataFrame:
    frame = read_parquet_columns(path, NATIVE_QUOTE_COLUMNS)
    frame = frame.copy()
    frame["interval_used"] = "1m"
    return frame


def apply_native_quote_clock(greeks: pd.DataFrame, native_quotes: pd.DataFrame) -> pd.DataFrame:
    """Attach only the sealed native clock; retain original stored Greek bid/ask."""

    if "timestamp" in greeks:
        raise AssertionError("native quote sidecar is only allowed for Greek sources missing timestamp")
    if "underlying_timestamp" not in greeks:
        raise AssertionError("stored Greek source has no fallback clock to verify")
    left = greeks.copy()
    left["timestamp"] = pd.to_datetime(left["underlying_timestamp"], errors="coerce")
    right = native_quotes.copy()
    right["timestamp"] = pd.to_datetime(right["timestamp"], errors="coerce")
    for frame in (left, right):
        frame["symbol"] = frame["symbol"].astype(str).str.upper()
        frame["expiration"] = frame["expiration"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
        frame["trade_date"] = frame["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
        frame["right"] = frame["right"].astype(str).str.upper().replace({"C": "CALL", "P": "PUT"})
        frame["strike"] = pd.to_numeric(frame["strike"], errors="coerce")
    # The sealed sidecar intentionally contains only the frozen research window
    # (10:20..14:29, or 12:54 on half-days).  Assert the explicit scheduled grid
    # rather than deriving scope from observed min/max, which could silently
    # accept a missing first or last minute.
    if right["timestamp"].isna().any() or right.empty:
        raise AssertionError("sealed native quote clock is empty or invalid")
    ticker_values = sorted(right["symbol"].dropna().astype(str).unique().tolist())
    date_values = sorted(right["trade_date"].dropna().astype(str).unique().tolist())
    if len(ticker_values) != 1 or len(date_values) != 1:
        raise AssertionError("sealed native quote clock spans multiple sessions")
    final_minute = last_scheduled_decision_minute(ticker_values[0], date_values[0]) - 1
    day = pd.Timestamp(date_values[0])
    expected_clock = pd.date_range(
        day + pd.Timedelta(minutes=NATIVE_QUOTE_FIRST_MINUTE),
        day + pd.Timedelta(minutes=final_minute),
        freq="1min",
    )
    observed_clock = pd.DatetimeIndex(sorted(right["timestamp"].unique()))
    if not observed_clock.equals(expected_clock):
        raise AssertionError("sealed native quote clock does not cover the exact scheduled research grid")
    left = left[left["timestamp"].isin(expected_clock)].copy()
    keys = ["symbol", "expiration", "trade_date", "timestamp", "right", "strike"]
    if left[keys].isna().any().any() or right[keys].isna().any().any():
        raise AssertionError("native quote clock bridge contains missing normalized keys")
    if left.duplicated(keys).any() or right.duplicated(keys).any():
        raise AssertionError("native quote clock bridge contains duplicate keys")
    parity = left[keys].merge(right[keys], on=keys, how="left", indicator=True, validate="one_to_one")
    if len(parity) != len(left) or not parity["_merge"].eq("both").all():
        raise AssertionError("native quote clock bridge is missing stored Greek keys")
    # Restore the original metadata/price columns and add the verified native
    # clock.  Current-provider bid/ask is deliberately not copied.
    output = greeks.loc[left.index].copy()
    output["timestamp"] = left["timestamp"]
    return output


def _truthy(series: pd.Series) -> pd.Series:
    return series.map(
        lambda value: value
        if isinstance(value, (bool, np.bool_))
        else str(value).strip().lower() in {"1", "true", "yes", "y"}
    ).astype(bool)


def filter_manifest(
    manifest: pd.DataFrame,
    *,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    required = {
        "ticker", "trade_date", "dte_days", "expiry_mode", "has_greeks", "has_ohlc",
        "has_underlying", "greeks_path", "ohlc_path", "underlying_path",
    }
    missing = sorted(required.difference(manifest.columns))
    if missing:
        raise KeyError(f"source manifest missing columns: {missing}")
    work = manifest.copy()
    work["ticker"] = work["ticker"].astype(str).str.upper()
    work["trade_date"] = work["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    work = work[
        work["ticker"].isin(TICKERS)
        & work["trade_date"].between(start_date, end_date)
        & pd.to_numeric(work["dte_days"], errors="coerce").eq(0)
        & work["expiry_mode"].astype(str).str.lower().eq("zero_dte")
        & _truthy(work["has_greeks"])
        & _truthy(work["has_ohlc"])
        & _truthy(work["has_underlying"])
    ].copy()
    if work.empty:
        raise AssertionError("no complete 0DTE source sessions in requested range")
    if work.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("source manifest has duplicate ticker/session keys")
    if work["trade_date"].str.startswith("2026").any():
        raise AssertionError("2026 entered the surface-flow source manifest")
    expiration = work.get("expiration", pd.Series("", index=work.index)).astype(str).str.replace(r"\D", "", regex=True).str[:8]
    if "expiration" not in work or not expiration.eq(work["trade_date"]).all():
        raise AssertionError("source manifest must identify expiration == trade_date for every 0DTE session")
    for column in ("greeks_path", "ohlc_path", "underlying_path"):
        missing_paths = [str(path) for path in work[column] if not Path(path).is_file()]
        if missing_paths:
            raise FileNotFoundError(f"missing {column} files: {missing_paths[:5]}")
    return work.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)


def select_preflight_sessions(manifest: pd.DataFrame) -> pd.DataFrame:
    selected = []
    for ticker in TICKERS:
        part = manifest[manifest["ticker"].eq(ticker)]
        if part.empty:
            raise AssertionError(f"no preflight source session for {ticker}")
        selected.append(part.iloc[len(part) // 2])
    return pd.DataFrame(selected).reset_index(drop=True)


def attach_native_quote_index(
    sessions: pd.DataFrame,
    index_path: str | Path,
    seal_path: str | Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    seal = json.loads(Path(seal_path).read_text(encoding="utf-8"))
    if seal.get("schema") != "wall_native_quote_sidecar_seal_v1" or seal.get("status") != "PASS_NATIVE_TIMESTAMP_BACKFILL":
        raise AssertionError("native quote sidecar is not a PASS seal")
    if seal.get("holdout_2026_used") is not False or seal.get("outcome_free") is not True:
        raise AssertionError("native quote seal violates outcome-free/pre-2026 scope")
    if str(seal.get("source_manifest_sha256")) != EXPECTED_INPUT_HASHES["manifest"]:
        raise AssertionError("native quote seal was not built from the canonical source manifest")
    index_hash = sha256_file(index_path)
    if str(seal.get("index_sha256")) != index_hash:
        raise AssertionError("native quote index hash differs from its seal")
    index = pd.read_csv(index_path, dtype={"trade_date": str})
    required = {
        "ticker", "trade_date", "greeks_path", "greeks_sha256", "quotes_path",
        "quotes_sha256", "raw_response_path", "raw_response_sha256",
        "session_manifest_path", "session_manifest_sha256", "rows", "end_time",
        "terminal_jar_sha256", "key_set_exact", "stored_timestamp_key_coverage_exact",
        "missing_stored_key_rows", "native_extra_key_rows",
        "stored_bid_ask_exact", "stored_either_mismatch_rows", "stored_either_mismatch_rate",
    }
    missing = sorted(required.difference(index.columns))
    if missing:
        raise KeyError(f"native quote index missing columns: {missing}")
    index["ticker"] = index["ticker"].astype(str).str.upper()
    index["trade_date"] = index["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    index = index.sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    if (
        len(index) != EXPECTED_NATIVE_QUOTE_SESSIONS
        or index.duplicated(["ticker", "trade_date"]).any()
        or session_key_hash(index) != EXPECTED_NATIVE_QUOTE_KEY_SHA256
        or index["trade_date"].str.startswith("2026").any()
        or not _truthy(index["stored_timestamp_key_coverage_exact"]).all()
        or not pd.to_numeric(index["missing_stored_key_rows"], errors="coerce").eq(0).all()
    ):
        raise AssertionError("native quote index does not cover the frozen fallback universe exactly")
    if int(seal.get("fallback_sessions", -1)) != len(index) or str(seal.get("fallback_session_key_sha256")) != EXPECTED_NATIVE_QUOTE_KEY_SHA256:
        raise AssertionError("native quote seal session universe mismatch")
    terminal_jar_hash = str(seal.get("terminal_jar_sha256", ""))
    if not terminal_jar_hash or set(index["terminal_jar_sha256"].astype(str)) != {terminal_jar_hash}:
        raise AssertionError("native quote index Terminal JAR provenance differs from its seal")
    quote_rows = pd.to_numeric(index["rows"], errors="coerce")
    if quote_rows.isna().any() or quote_rows.le(0).any():
        raise AssertionError("native quote index contains empty/invalid captures")
    for path_column, hash_column, description in (
        ("raw_response_path", "raw_response_sha256", "raw native quote response"),
        ("session_manifest_path", "session_manifest_sha256", "native quote session manifest"),
    ):
        for path_value, expected_hash in index[[path_column, hash_column]].itertuples(index=False, name=None):
            evidence_path = Path(str(path_value))
            if not evidence_path.is_file():
                raise FileNotFoundError(f"missing {description}: {evidence_path}")
            if sha256_file(evidence_path) != str(expected_hash):
                raise AssertionError(f"{description} hash differs from sealed index: {evidence_path}")
    selected = sessions.merge(
        index.rename(
            columns={
                "quotes_path": "native_quote_path",
                "quotes_sha256": "expected_native_quote_sha256",
                "greeks_sha256": "expected_greeks_sha256",
            }
        )[
            [
                "ticker", "trade_date", "greeks_path", "expected_greeks_sha256",
                "native_quote_path", "expected_native_quote_sha256",
            ]
        ],
        on=["ticker", "trade_date", "greeks_path"],
        how="left",
        validate="one_to_one",
    )
    fallback_detected = []
    for row in selected.itertuples(index=False):
        columns = set(pq.ParquetFile(str(row.greeks_path)).schema_arrow.names)
        fallback_detected.append("timestamp" not in columns)
    selected["greeks_timestamp_fallback"] = fallback_detected
    needs_sidecar = selected["greeks_timestamp_fallback"].astype(bool)
    has_sidecar = selected["native_quote_path"].notna()
    if not needs_sidecar.equals(has_sidecar):
        raise AssertionError("native quote index coverage differs from actual missing-timestamp Greek sessions")
    for row in selected.loc[needs_sidecar].itertuples(index=False):
        quote_path = Path(str(row.native_quote_path))
        if not quote_path.is_file():
            raise FileNotFoundError(f"missing sealed native quote Parquet: {quote_path}")
    return selected, {
        "seal_sha256": sha256_file(seal_path),
        "index_sha256": index_hash,
        "sessions": int(len(index)),
        "session_key_sha256": session_key_hash(index),
        "terminal_jar_sha256": str(seal.get("terminal_jar_sha256")),
        "git_commit": str(seal.get("git_commit")),
    }


def _source_fingerprint(record: dict[str, Any], kind: str, column: str) -> dict[str, Any]:
    path = Path(record[column])
    parquet = pq.ParquetFile(path)
    schema_text = str(parquet.schema_arrow)
    return {
        "ticker": str(record["ticker"]),
        "trade_date": str(record["trade_date"]),
        "source_kind": kind,
        "path": str(path),
        "bytes": int(path.stat().st_size),
        "rows": int(parquet.metadata.num_rows),
        "schema_sha256": hashlib.sha256(schema_text.encode("utf-8")).hexdigest(),
        "sha256": sha256_file(path),
        "timestamp_min": "",
        "timestamp_max": "",
        "interval_values": "[]",
        "symbol_values": "[]",
        "expiration_values": "[]",
        "trade_date_values": "[]",
        "right_values": "[]",
        "distinct_strikes": 0,
    }


def _set_timestamp_range(inventory: dict[str, Any], frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    for column in columns:
        if column in frame:
            values = pd.to_datetime(frame[column], errors="coerce").dropna()
            if len(values):
                inventory["timestamp_min"] = values.min().isoformat()
                inventory["timestamp_max"] = values.max().isoformat()
                return


def _set_contract_metadata(inventory: dict[str, Any], frame: pd.DataFrame) -> None:
    mapping = {
        "interval_values": "interval_used",
        "symbol_values": "symbol",
        "expiration_values": "expiration",
        "trade_date_values": "trade_date",
        "right_values": "right",
    }
    for output, column in mapping.items():
        if column in frame:
            values = sorted(set(frame[column].dropna().astype(str)))
            inventory[output] = json.dumps(values, separators=(",", ":"))
    if "strike" in frame:
        inventory["distinct_strikes"] = int(pd.to_numeric(frame["strike"], errors="coerce").nunique(dropna=True))


def _assert_sources_unchanged(inventory: list[dict[str, Any]]) -> None:
    for row in inventory:
        if sha256_file(row["path"]) != row["sha256"]:
            raise AssertionError(f"source changed while being read: {row['path']}")


def build_session(
    record: dict[str, Any],
    candidates: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    inventory = [
        _source_fingerprint(record, "greeks", "greeks_path"),
        _source_fingerprint(record, "ohlc", "ohlc_path"),
        _source_fingerprint(record, "underlying", "underlying_path"),
    ]
    greeks = read_greeks(record["greeks_path"])
    native_quote_path = record.get("native_quote_path")
    use_native_sidecar = bool(native_quote_path) and not pd.isna(native_quote_path)
    if use_native_sidecar:
        native_inventory = _source_fingerprint(record, "native_quote", "native_quote_path")
        expected_native_hash = str(record.get("expected_native_quote_sha256", ""))
        if native_inventory["sha256"] != expected_native_hash:
            raise AssertionError("native quote Parquet hash differs from sealed index")
        if inventory[0]["sha256"] != str(record.get("expected_greeks_sha256", "")):
            raise AssertionError("stored Greek hash differs from native quote index")
        inventory.append(native_inventory)
        native_quotes = read_native_quotes(native_quote_path)
        quote_source = apply_native_quote_clock(greeks, native_quotes)
    else:
        quote_source = greeks
    ohlc = read_parquet_columns(record["ohlc_path"], OHLC_COLUMNS)
    underlying = read_parquet_columns(record["underlying_path"], UNDERLYING_COLUMNS)
    _set_timestamp_range(inventory[0], greeks, ("timestamp", "underlying_timestamp"))
    _set_timestamp_range(inventory[1], ohlc, ("timestamp",))
    _set_timestamp_range(inventory[2], underlying, ("timestamp",))
    _set_contract_metadata(inventory[0], greeks)
    _set_contract_metadata(inventory[1], ohlc)
    _set_contract_metadata(inventory[2], underlying)
    if use_native_sidecar:
        _set_timestamp_range(inventory[3], native_quotes, ("timestamp",))
        _set_contract_metadata(inventory[3], native_quotes)
    _assert_sources_unchanged(inventory)
    flow, audit = prepare_completed_bar_flow(
        quote_source,
        ohlc,
        expected_ticker=str(record["ticker"]),
        expected_trade_date=str(record["trade_date"]),
    )
    validated_underlying, underlying_audit = validate_underlying_session(
        underlying,
        expected_ticker=str(record["ticker"]),
        expected_trade_date=str(record["trade_date"]),
    )
    audit.update(underlying_audit)
    if not candidates.empty:
        opens = validated_underlying.set_index("bar_start")["open"].reindex(
            pd.to_datetime(candidates["decision_dt"], errors="coerce")
        )
        if opens.isna().any():
            raise AssertionError("candidate spot has no exact derived-underlying decision bar")
        event_spot = pd.to_numeric(candidates["spot"], errors="coerce").to_numpy(dtype=float)
        spot_diff = np.abs(opens.to_numpy(dtype=float) - event_spot) / event_spot * 10_000.0
        max_spot_diff = float(np.max(spot_diff)) if len(spot_diff) else 0.0
        if not np.isfinite(spot_diff).all() or max_spot_diff > 0.001:
            raise AssertionError(
                f"candidate/derived-underlying exact spot parity failed: max_bps={max_spot_diff}"
            )
        audit["candidate_underlying_spot_max_bps"] = max_spot_diff
    else:
        audit["candidate_underlying_spot_max_bps"] = 0.0
    controlled = attach_completed_underlying_controls(
        candidates,
        underlying,
        expected_trade_date=str(record["trade_date"]),
    )
    output = attach_flow_features(flow, controlled)
    audit.update(
        {
            "ticker": str(record["ticker"]),
            "trade_date": str(record["trade_date"]),
            "candidate_rows": int(len(output)),
            "candidate_decisions": int(output[["trade_date", "minute"]].drop_duplicates().shape[0]) if not output.empty else 0,
        }
    )
    return output, audit, inventory


def process_sessions(
    records: list[dict[str, Any]],
    candidates: pd.DataFrame,
    workers: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict[str, str]]]:
    if not 1 <= int(workers) <= MAX_WORKERS:
        raise ValueError(f"workers must be within 1..{MAX_WORKERS}")
    candidate_map = {
        (str(ticker), str(trade_date)): part.copy()
        for (ticker, trade_date), part in candidates.groupby(["ticker", "trade_date"], observed=True, sort=False)
    }
    frames: list[pd.DataFrame] = []
    audits: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    def candidate_part(record: dict[str, Any]) -> pd.DataFrame:
        return candidate_map.get((str(record["ticker"]), str(record["trade_date"])), candidates.iloc[0:0].copy())

    if workers == 1:
        for index, record in enumerate(records, start=1):
            try:
                frame, audit, inventory = build_session(record, candidate_part(record))
                if not frame.empty:
                    frames.append(frame)
                audits.append(audit)
                sources.extend(inventory)
            except Exception as exc:
                errors.append(
                    {
                        "ticker": str(record["ticker"]),
                        "trade_date": str(record["trade_date"]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            if index % 100 == 0 or index == len(records):
                print(f"[SURFACE_FLOW] sessions={index}/{len(records)} errors={len(errors)}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(build_session, record, candidate_part(record)): record
                for record in records
            }
            for index, future in enumerate(as_completed(futures), start=1):
                record = futures[future]
                try:
                    frame, audit, inventory = future.result()
                    if not frame.empty:
                        frames.append(frame)
                    audits.append(audit)
                    sources.extend(inventory)
                except Exception as exc:
                    errors.append(
                        {
                            "ticker": str(record["ticker"]),
                            "trade_date": str(record["trade_date"]),
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                if index % 100 == 0 or index == len(futures):
                    print(f"[SURFACE_FLOW] sessions={index}/{len(futures)} errors={len(errors)}", flush=True)
    dataset = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not dataset.empty:
        dataset = dataset.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)
    audit_frame = pd.DataFrame(audits).sort_values(["ticker", "trade_date"], kind="stable").reset_index(drop=True)
    source_frame = pd.DataFrame(sources).sort_values(["ticker", "trade_date", "source_kind"], kind="stable").reset_index(drop=True)
    return dataset, audit_frame, source_frame, errors


def build_coverage_profile(audit: pd.DataFrame) -> pd.DataFrame:
    work = audit.copy()
    work["month"] = work["trade_date"].astype(str).str[:6]
    grouped = work.groupby(["ticker", "month"], observed=True, sort=True)
    rows: list[dict[str, Any]] = []
    for (ticker, month), part in grouped:
        active_rows = float(part["active_rows"].sum())
        active_volume = float(part["active_volume"].sum())
        valid_rows = float(part["valid_quote_rows"].sum())
        valid_volume = float(part["valid_quote_volume"].sum())
        rows.append(
            {
                "ticker": str(ticker),
                "month": str(month),
                "sessions": int(len(part)),
                "candidate_rows": int(part["candidate_rows"].sum()),
                "active_rows": int(active_rows),
                "active_volume": active_volume,
                "valid_quote_rows": int(valid_rows),
                "valid_quote_volume": valid_volume,
                "quote_row_coverage": float(valid_rows / active_rows) if active_rows > 0 else 0.0,
                "quote_volume_coverage": float(valid_volume / active_volume) if active_volume > 0 else 0.0,
                "price_volume_coverage": float(part["priced_active_volume"].sum() / active_volume) if active_volume > 0 else 0.0,
                "signable_volume_coverage": float(part["signable_volume"].sum() / active_volume) if active_volume > 0 else 0.0,
                "greeks_subminute_rows": int(part["greeks_subminute_rows"].sum()),
                "unmatched_active_rows": int(part["unmatched_active_rows"].sum()),
                "zero_count_active_rows": int(part["zero_count_active_rows"].sum()),
                "nonpositive_close_active_rows": int(part["nonpositive_close_active_rows"].sum()),
                "nonpositive_close_active_volume": float(part["nonpositive_close_active_volume"].sum()),
            }
        )
    return pd.DataFrame(rows)


def build_feature_profile(dataset: pd.DataFrame) -> pd.DataFrame:
    work = dataset.copy()
    work["year"] = work["trade_date"].astype(str).str[:4]
    rows: list[dict[str, Any]] = []
    features = (*CONTROL_FEATURES, *FLOW_FEATURES)
    for (ticker, year), part in work.groupby(["ticker", "year"], observed=True, sort=True):
        for feature in features:
            values = pd.to_numeric(part[feature], errors="coerce")
            finite = values[np.isfinite(values)]
            rows.append(
                {
                    "ticker": str(ticker),
                    "year": str(year),
                    "feature": feature,
                    "rows": int(len(values)),
                    "missing_rate": float(1.0 - len(finite) / len(values)) if len(values) else 1.0,
                    "zero_rate": float((finite == 0.0).mean()) if len(finite) else 1.0,
                    "distinct_values": int(finite.nunique(dropna=True)),
                    "minimum": float(finite.min()) if len(finite) else None,
                    "maximum": float(finite.max()) if len(finite) else None,
                }
            )
    return pd.DataFrame(rows)


def schema_payload(dataset: pd.DataFrame) -> dict[str, Any]:
    return {
        "columns": [
            {"name": str(column), "dtype": str(dataset[column].dtype)}
            for column in dataset.columns
        ],
        "key_columns": list(KEY_COLUMNS),
        "control_features": list(CONTROL_FEATURES),
        "flow_features": list(FLOW_FEATURES),
        "control_feature_hash": feature_hash(CONTROL_FEATURES),
        "flow_feature_hash": feature_hash(FLOW_FEATURES),
    }


def evaluate_data_gate(
    audit: pd.DataFrame,
    profile: pd.DataFrame,
    *,
    authoritative_inputs: bool,
    authoritative_code: bool,
) -> dict[str, Any]:
    annual = audit.assign(year=audit["trade_date"].astype(str).str[:4]).groupby(
        ["ticker", "year"], observed=True, sort=True
    ).agg(
        active_rows=("active_rows", "sum"),
        active_volume=("active_volume", "sum"),
        valid_quote_rows=("valid_quote_rows", "sum"),
        valid_quote_volume=("valid_quote_volume", "sum"),
        priced_active_volume=("priced_active_volume", "sum"),
        signable_volume=("signable_volume", "sum"),
        sessions=("trade_date", "size"),
        candidates=("candidate_rows", "sum"),
    ).reset_index()
    annual["quote_row_coverage"] = annual["valid_quote_rows"] / annual["active_rows"].replace(0, np.nan)
    annual["quote_volume_coverage"] = annual["valid_quote_volume"] / annual["active_volume"].replace(0, np.nan)
    annual["price_volume_coverage"] = annual["priced_active_volume"] / annual["active_volume"].replace(0, np.nan)
    annual["signable_volume_coverage"] = annual["signable_volume"] / annual["active_volume"].replace(0, np.nan)
    coverage_pass = bool(
        len(annual) == 12
        and len(audit) == EXPECTED_SESSION_COUNT
        and audit["greeks_required_window_minutes"].eq(audit["expected_required_window_minutes"]).all()
        and audit["ohlc_required_window_minutes"].eq(audit["expected_required_window_minutes"]).all()
        and audit["underlying_required_window_minutes"].eq(
            audit["expected_underlying_required_window_minutes"]
        ).all()
        and audit["option_timestamp_fallback_used"].astype(bool).eq(False).all()
        and audit["active_rows"].gt(0).all()
        and audit["active_volume"].gt(0.0).all()
        and annual["active_rows"].gt(0).all()
        and annual["candidates"].gt(0).all()
        and annual["quote_row_coverage"].ge(0.75).all()
        and annual["quote_volume_coverage"].ge(0.90).all()
        and annual["price_volume_coverage"].ge(0.99).all()
        and annual["signable_volume_coverage"].ge(0.90).all()
    )
    core_features = {
        *[f"surface_directional_pressure_w{window}m" for window in (1, 5, 15)],
        *[f"role_break_pressure_w{window}m" for window in (1, 5, 15)],
    }
    core = profile[profile["feature"].isin(core_features)]
    distinctness_pass = bool(
        len(core) == 12 * len(core_features)
        and core["distinct_values"].ge(10).all()
        and core["zero_rate"].lt(0.995).all()
    )
    controls = profile[profile["feature"].isin({"realized_vol_5m_bps", "realized_vol_15m_bps"})]
    control_coverage_pass = bool(len(controls) == 24 and controls["missing_rate"].eq(0.0).all())
    passed = bool(
        authoritative_inputs
        and authoritative_code
        and coverage_pass
        and distinctness_pass
        and control_coverage_pass
    )
    return {
        "authoritative_inputs": bool(authoritative_inputs),
        "authoritative_code": bool(authoritative_code),
        "coverage_pass": coverage_pass,
        "distinctness_pass": distinctness_pass,
        "control_coverage_pass": control_coverage_pass,
        "annual_cells": int(len(annual)),
        "session_count": int(len(audit)),
        "expected_session_count": EXPECTED_SESSION_COUNT,
        "incomplete_greeks_grid_sessions": int(
            audit["greeks_required_window_minutes"].ne(audit["expected_required_window_minutes"]).sum()
        ),
        "incomplete_ohlc_grid_sessions": int(
            audit["ohlc_required_window_minutes"].ne(audit["expected_required_window_minutes"]).sum()
        ),
        "incomplete_underlying_grid_sessions": int(
            audit["underlying_required_window_minutes"].ne(
                audit["expected_underlying_required_window_minutes"]
            ).sum()
        ),
        "maximum_candidate_underlying_spot_bps": float(
            audit["candidate_underlying_spot_max_bps"].max()
        ),
        "underlying_out_of_scope_invalid_rows": int(
            audit["underlying_out_of_scope_invalid_rows"].sum()
        ),
        "minimum_underlying_research_tick_count": float(
            audit["underlying_min_research_tick_count"].min()
        ),
        "option_timestamp_fallback_sessions": int(audit["option_timestamp_fallback_used"].astype(bool).sum()),
        "zero_active_sessions": int(audit["active_rows"].le(0).sum()),
        "minimum_quote_row_coverage": float(annual["quote_row_coverage"].min()) if len(annual) else None,
        "minimum_quote_volume_coverage": float(annual["quote_volume_coverage"].min()) if len(annual) else None,
        "minimum_price_volume_coverage": float(annual["price_volume_coverage"].min()) if len(annual) else None,
        "minimum_signable_volume_coverage": float(annual["signable_volume_coverage"].min()) if len(annual) else None,
        "passed": passed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--walls", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--native-quote-index")
    parser.add_argument("--native-quote-seal")
    parser.add_argument(
        "--exact-greek-repair-manifest",
        help=(
            "Committed V1R2 bundle manifest; wall_repair.parquet and "
            "event_control_repair.parquet must be immutable siblings"
        ),
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-date", default=START_DATE)
    parser.add_argument("--end-date", default=END_DATE)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--allow-input-hash-mismatch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if str(args.end_date) > END_DATE or str(args.end_date).startswith("2026"):
        raise ValueError(f"end date must not exceed sealed physical cutoff {END_DATE}")
    if args.allow_input_hash_mismatch and not args.preflight:
        raise ValueError("--allow-input-hash-mismatch is restricted to non-authoritative preflight")
    if bool(args.native_quote_index) != bool(args.native_quote_seal):
        raise ValueError("--native-quote-index and --native-quote-seal must be supplied together")
    if not args.preflight and not args.native_quote_index:
        raise ValueError("authoritative full build requires the sealed native quote index")
    if not args.exact_greek_repair_manifest and not (
        args.preflight and args.allow_input_hash_mismatch
    ):
        raise ValueError(
            "the V1R2 exact-Greek repair bundle is required unless running a "
            "non-authoritative hash-mismatch preflight"
        )
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(f"immutable output target already exists: {output_dir}")
    staging_dir = output_dir.with_name(f"{output_dir.name}.staging")
    if staging_dir.exists():
        raise FileExistsError(f"staging target already exists; inspect manually: {staging_dir}")
    paths = {name: Path(getattr(args, name)) for name in ("walls", "events", "manifest")}
    input_hashes = {name: sha256_file(path) for name, path in paths.items()}
    if input_hashes != EXPECTED_INPUT_HASHES and not args.allow_input_hash_mismatch:
        raise AssertionError(f"sealed input hash mismatch: {input_hashes}")
    authoritative_base_inputs = bool(
        input_hashes == EXPECTED_INPUT_HASHES and not args.allow_input_hash_mismatch
    )
    authoritative_code = False
    build_commit = current_git_commit()
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    if not args.preflight:
        build_commit = assert_authoritative_code_state()
        authoritative_code = True
    walls = pd.read_parquet(paths["walls"])
    events = pd.read_parquet(paths["events"], columns=list(EVENT_COLUMNS))
    exact_greek_repair_provenance: dict[str, Any] | None = None
    if args.exact_greek_repair_manifest:
        walls, events, exact_greek_repair_provenance = attach_exact_greek_repair_bundle(
            walls,
            events,
            args.exact_greek_repair_manifest,
            enforce_frozen=not args.allow_input_hash_mismatch,
            require_committed=not args.preflight,
        )
    authoritative_inputs = bool(
        authoritative_base_inputs
        and exact_greek_repair_provenance is not None
        and exact_greek_repair_provenance["frozen_hashes_match"]
    )
    candidates, candidate_universe_audit = make_touch_candidates(walls, events, return_audit=True)
    manifest = pd.read_csv(paths["manifest"], dtype={"trade_date": str})
    selected = filter_manifest(manifest, start_date=str(args.start_date), end_date=str(args.end_date))
    native_quote_provenance: dict[str, Any] | None = None
    if args.native_quote_index:
        native_index_path = Path(args.native_quote_index)
        native_seal_path = Path(args.native_quote_seal)
        if not args.preflight:
            assert_committed_artifact(native_index_path, "native quote index")
            assert_committed_artifact(native_seal_path, "native quote seal")
        selected, native_quote_provenance = attach_native_quote_index(
            selected,
            native_index_path,
            native_seal_path,
        )
    selected_key_hash = session_key_hash(selected)
    if str(args.start_date) == START_DATE and str(args.end_date) == END_DATE:
        if len(selected) != EXPECTED_SESSION_COUNT or selected_key_hash != EXPECTED_SESSION_KEY_SHA256:
            raise AssertionError(
                "frozen session universe mismatch: "
                f"rows={len(selected)}/{EXPECTED_SESSION_COUNT} hash={selected_key_hash}"
            )
    if args.preflight:
        selected = select_preflight_sessions(selected)
        keys = set(zip(selected["ticker"].astype(str), selected["trade_date"].astype(str)))
        candidate_mask = [
            (str(ticker), str(trade_date)) in keys
            for ticker, trade_date in zip(candidates["ticker"], candidates["trade_date"])
        ]
        candidates = candidates[np.asarray(candidate_mask, dtype=bool)].copy()
    records = selected.to_dict("records")
    dataset, audit, source_hashes, errors = process_sessions(records, candidates, int(args.workers))
    if errors:
        raise AssertionError(f"surface-flow source errors: {errors[:10]}")
    if dataset.empty:
        raise AssertionError("surface-flow build produced no at-touch candidates")
    expected_candidates = candidates.merge(
        selected[["ticker", "trade_date"]],
        on=["ticker", "trade_date"],
        how="inner",
        validate="many_to_one",
    )
    if len(dataset) != len(expected_candidates):
        raise AssertionError(f"candidate coverage mismatch: {len(dataset)}/{len(expected_candidates)}")
    if dataset.duplicated(list(KEY_COLUMNS)).any():
        raise AssertionError("built surface-flow dataset contains duplicate keys")

    staging_dir.mkdir(parents=True, exist_ok=False)
    dataset_path = staging_dir / "wall_surface_flow_at_touch.parquet"
    audit_path = staging_dir / "session_audit.csv"
    source_hash_path = staging_dir / "source_file_hashes.csv"
    coverage_path = staging_dir / "coverage_by_month.csv"
    profile_path = staging_dir / "feature_profile.csv"
    schema_path = staging_dir / "schema.json"
    manifest_path = staging_dir / "manifest.json"
    dataset.to_parquet(dataset_path, index=False)
    audit.to_csv(audit_path, index=False)
    source_hashes.to_csv(source_hash_path, index=False)
    coverage = build_coverage_profile(audit)
    coverage.to_csv(coverage_path, index=False)
    profile = build_feature_profile(dataset)
    profile.to_csv(profile_path, index=False)
    schema_path.write_text(json.dumps(schema_payload(dataset), indent=2, allow_nan=False), encoding="utf-8")
    data_gate = evaluate_data_gate(
        audit,
        profile,
        authoritative_inputs=authoritative_inputs,
        authoritative_code=authoritative_code,
    )

    aggregate_active_rows = float(audit["active_rows"].sum())
    aggregate_active_volume = float(audit["active_volume"].sum())
    aggregate_valid_rows = float(audit["valid_quote_rows"].sum())
    aggregate_valid_volume = float(audit["valid_quote_volume"].sum())
    manifest_out = {
        "schema": "wall_surface_flow_at_touch_dataset_v1",
        "status": (
            "PREFLIGHT_COMPLETE"
            if args.preflight
            else "PASS_DATA_GATE" if data_gate["passed"] else "REJECTED_DATA_GATE"
        ),
        "preflight": bool(args.preflight),
        "git_commit": build_commit,
        "production_modified": False,
        "holdout_2026_used": False,
        "date_range": [str(dataset["trade_date"].min()), str(dataset["trade_date"].max())],
        "physical_cutoff": END_DATE,
        "input_hashes": input_hashes,
        "native_quote_provenance": native_quote_provenance,
        "exact_greek_repair_provenance": exact_greek_repair_provenance,
        "builder_sha256": sha256_file(__file__),
        "feature_module_sha256": sha256_file(Path(__file__).with_name("surface_flow_features.py")),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "dataset": str(output_dir / dataset_path.name),
        "dataset_sha256": sha256_file(dataset_path),
        "dataset_bytes": int(dataset_path.stat().st_size),
        "rows": int(len(dataset)),
        "columns": int(len(dataset.columns)),
        "rows_by_ticker": dataset.groupby("ticker", observed=True).size().astype(int).to_dict(),
        "rows_by_ticker_year": {
            f"{ticker}:{year}": int(len(part))
            for (ticker, year), part in dataset.assign(year=dataset["trade_date"].astype(str).str[:4]).groupby(
                ["ticker", "year"], observed=True, sort=True
            )
        },
        "requested_sessions": int(len(records)),
        "built_sessions": int(len(audit)),
        "full_session_universe_count": int(EXPECTED_SESSION_COUNT),
        "full_session_key_sha256": selected_key_hash,
        "source_files": int(len(source_hashes)),
        "source_file_hashes_sha256": sha256_file(source_hash_path),
        "session_audit_sha256": sha256_file(audit_path),
        "coverage_by_month_sha256": sha256_file(coverage_path),
        "feature_profile_sha256": sha256_file(profile_path),
        "schema_sha256": sha256_file(schema_path),
        "control_feature_hash": feature_hash(CONTROL_FEATURES),
        "flow_feature_hash": feature_hash(FLOW_FEATURES),
        "quote_row_coverage": float(aggregate_valid_rows / aggregate_active_rows) if aggregate_active_rows > 0 else 0.0,
        "quote_volume_coverage": float(aggregate_valid_volume / aggregate_active_volume) if aggregate_active_volume > 0 else 0.0,
        "price_volume_coverage": float(audit["priced_active_volume"].sum() / aggregate_active_volume) if aggregate_active_volume > 0 else 0.0,
        "signable_volume_coverage": float(audit["signable_volume"].sum() / aggregate_active_volume) if aggregate_active_volume > 0 else 0.0,
        "greeks_subminute_rows": int(audit["greeks_subminute_rows"].sum()),
        "option_timestamp_fallback_sessions": int(audit["option_timestamp_fallback_used"].astype(bool).sum()),
        "unmatched_active_rows": int(audit["unmatched_active_rows"].sum()),
        "nonpositive_close_active_rows": int(audit["nonpositive_close_active_rows"].sum()),
        "nonpositive_close_active_volume": float(audit["nonpositive_close_active_volume"].sum()),
        "underlying_out_of_scope_invalid_rows": int(
            audit["underlying_out_of_scope_invalid_rows"].sum()
        ),
        "data_gate": data_gate,
        "candidate_universe_audit": candidate_universe_audit,
        "errors": errors,
        "args": vars(args),
    }
    manifest_path.write_text(json.dumps(manifest_out, indent=2, allow_nan=False), encoding="utf-8")
    staging_dir.rename(output_dir)
    print(json.dumps(manifest_out, indent=2, allow_nan=False), flush=True)
    return 0 if args.preflight or data_gate["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
