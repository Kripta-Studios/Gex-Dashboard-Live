"""Build the sealed V1R2 wall/control repair artifacts without outcomes.

Only QQQ and SPY on 2022-12-30 are in scope.  The wall replacement is
recomputed from the exact-1s first-order Greek snapshots and the frozen daily
OI; the event-control replacement is independently reconstructed from causal
derived-underlying ``open(t)`` observations.  The original wall and event
artifacts are never modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.build_wall_exact_greek_repair_sidecar import (  # noqa: E402
    DECISION_TIMES,
    EXPECTED_CONTRACT_KEY_SHA256,
    EXPECTED_CONTRACTS,
    EXPECTED_CONTRACTS_BY_TICKER,
    EXPECTED_TIMESTAMPS,
    OPTIONAL_RESPONSE_COLUMNS,
    PREDECLARATION,
    REQUIRED_RESPONSE_COLUMNS,
    SPOT_TOLERANCE_BPS,
    TARGET_DATE,
    TARGET_TICKERS,
    contract_key_hash,
    decision_timestamps,
    discover_contract_universe,
)
from neural.jepa.build_wall_native_quote_sidecar import (  # noqa: E402
    canonical_json_bytes,
    sha256_file,
)
from neural.jepa.wall_state_features import (  # noqa: E402
    add_wall_persistence,
    assert_wall_state_schema,
    compute_wall_states,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402


ENVIRONMENT_LOCK = PROJECT_ROOT / "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
EXPECTED_BASE_HASHES = {
    "walls": "94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef",
    "events": "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408",
    "manifest": "5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88",
}
SEAL_SCHEMA = "wall_exact_greek_repair_seal_v1r2"
SEAL_STATUS = "PASS_EXACT_GREEK_REPAIR_CAPTURE"
OUTPUT_SCHEMA = "wall_exact_greek_repair_artifacts_v1r2"
OUTPUT_STATUS = "PASS_EXACT_GREEK_REPAIR_ARTIFACTS"
KEY_COLUMNS = ("ticker", "trade_date", "minute")
EVENT_COLUMNS = (
    "ticker", "trade_date", "minute", "spot",
    "ret_1m_bps", "ret_5m_bps", "ret_15m_bps", "ret_30m_bps",
)
RETURN_LAGS = (1, 5, 15, 30)
EXPECTED_REPAIR_ROWS = len(TARGET_TICKERS) * EXPECTED_TIMESTAMPS
FORBIDDEN_COLUMN_TOKENS = ("future", "outcome", "exit", "pnl", "return_label", "win_label")
INDEX_COLUMNS = (
    "ticker", "trade_date", "strike", "right", "contract_dir",
    "exact_greeks_path", "exact_greeks_sha256", "raw_response_path",
    "raw_response_sha256", "contract_manifest_path", "contract_manifest_sha256",
    "rows", "stored_bid_ask_exact", "git_commit", "max_spot_difference_bps",
    "source_greeks_sha256", "source_oi_sha256", "source_underlying_sha256",
    "terminal_jar_sha256", "terminal_process_id", "java_executable_sha256",
)
EXACT_BASE_COLUMNS = (
    "symbol", "expiration", "trade_date", "strike", "right", "timestamp",
    "underlying_timestamp", "underlying_price", "implied_vol", "delta",
    "theta", "vega", "rho", "bid", "ask",
)


def _day(value: Any) -> str:
    return "".join(character for character in str(value) if character.isdigit())[:8]


def _right(value: Any) -> str:
    normalized = str(value).strip().upper()
    mapping = {"C": "CALL", "CALL": "CALL", "P": "PUT", "PUT": "PUT"}
    if normalized not in mapping:
        raise AssertionError(f"invalid option right: {value!r}")
    return mapping[normalized]


def _strict_bool(value: Any, label: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise AssertionError(f"{label} is not a strict JSON/CSV boolean: {value!r}")


def _hash_sequence(values: Iterable[str]) -> str:
    payload = "".join(f"{value}\n" for value in values).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _schema_hash(frame: pd.DataFrame) -> str:
    payload = json.dumps(
        [{"name": str(column), "dtype": str(frame[column].dtype)} for column in frame.columns],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _assert_no_forbidden_columns(frame: pd.DataFrame, label: str) -> None:
    offenders = [
        str(column) for column in frame.columns
        if any(token in str(column).lower() for token in FORBIDDEN_COLUMN_TOKENS)
    ]
    if offenders:
        raise AssertionError(f"{label} contains outcome/future columns: {offenders}")
    if "trade_date" in frame and frame["trade_date"].astype(str).str.startswith("2026").any():
        raise AssertionError(f"2026 entered {label}")


def _normalize_keys(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    missing = sorted(set(KEY_COLUMNS).difference(frame.columns))
    if missing:
        raise KeyError(f"{label} missing repair keys: {missing}")
    out = frame.copy()
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["trade_date"] = out["trade_date"].map(_day)
    out["minute"] = pd.to_numeric(out["minute"], errors="coerce")
    if out[list(KEY_COLUMNS)].isna().any().any() or not np.isfinite(out["minute"]).all():
        raise AssertionError(f"{label} has invalid repair keys")
    out["minute"] = out["minute"].astype(np.int64)
    if out.duplicated(list(KEY_COLUMNS)).any():
        raise AssertionError(f"{label} has duplicate repair keys")
    return out


def expected_repair_keys() -> pd.DataFrame:
    minutes = [timestamp.hour * 60 + timestamp.minute for timestamp in decision_timestamps()]
    return pd.DataFrame(
        [(ticker, TARGET_DATE, minute) for ticker in TARGET_TICKERS for minute in minutes],
        columns=list(KEY_COLUMNS),
    ).sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)


def _assert_exact_repair_keys(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    out = _normalize_keys(frame, label)
    observed = out[list(KEY_COLUMNS)].sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)
    pd.testing.assert_frame_equal(observed, expected_repair_keys(), check_dtype=False, obj=f"{label} key scope")
    return out


def current_git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def assert_committed_code() -> str:
    relatives = (
        "neural/jepa/build_wall_exact_greek_repair_artifacts.py",
        "neural/jepa/build_wall_exact_greek_repair_sidecar.py",
        "neural/jepa/wall_state_features.py",
        "neural/jepa/wall_surface_flow_environment.py",
        "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
        "research_papers/JEPA/WALL_SURFACE_FLOW_V1R2_EXACT_SPOT_REPAIR_PREDECLARATION.md",
    )
    for relative in relatives:
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative], cwd=PROJECT_ROOT,
            check=True, capture_output=True, text=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", relative], cwd=PROJECT_ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        if dirty:
            raise AssertionError(f"repair build requires committed clean code: {relative}: {dirty}")
    return current_git_commit()


def assert_committed_artifact(path: Path, label: str) -> None:
    try:
        relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError as exc:
        raise AssertionError(f"{label} must be committed inside the repository: {path}") from exc
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative], cwd=PROJECT_ROOT,
        check=True, capture_output=True, text=True,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", relative], cwd=PROJECT_ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if dirty:
        raise AssertionError(f"{label} must be committed and clean: {dirty}")


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{label} is not a JSON object")
    return value


def _require_file_hash(path: Path, expected: Any, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")
    observed = sha256_file(path)
    if observed != str(expected):
        raise AssertionError(f"{label} hash mismatch: {observed} != {expected}")


def _validate_exact_snapshot(
    path: Path,
    *,
    ticker: str,
    strike: float,
    right: str,
    declared_columns: list[str],
) -> pd.DataFrame:
    schema_columns = list(pq.ParquetFile(path).schema_arrow.names)
    if schema_columns != declared_columns:
        raise AssertionError("exact-Greek parquet schema differs from its contract manifest")
    if tuple(schema_columns[:len(EXACT_BASE_COLUMNS)]) != EXACT_BASE_COLUMNS:
        raise AssertionError(f"exact-Greek parquet has an invalid base schema: {schema_columns}")
    extras = schema_columns[len(EXACT_BASE_COLUMNS):]
    if len(extras) != len(set(extras)) or not set(extras).issubset(set(OPTIONAL_RESPONSE_COLUMNS)):
        raise AssertionError(f"exact-Greek parquet has unexpected optional columns: {extras}")
    frame = pd.read_parquet(path)
    if len(frame) != EXPECTED_TIMESTAMPS:
        raise AssertionError(f"exact-Greek snapshot does not contain {EXPECTED_TIMESTAMPS} rows")
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    frame["expiration"] = frame["expiration"].map(_day)
    frame["trade_date"] = frame["trade_date"].map(_day)
    frame["right"] = frame["right"].map(_right)
    frame["strike"] = pd.to_numeric(frame["strike"], errors="coerce")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame["underlying_timestamp"] = pd.to_datetime(frame["underlying_timestamp"], errors="coerce")
    if (
        not frame["symbol"].eq(ticker).all()
        or not frame["expiration"].eq(TARGET_DATE).all()
        or not frame["trade_date"].eq(TARGET_DATE).all()
        or not frame["right"].eq(right).all()
        or not np.isclose(frame["strike"].to_numpy(float), strike, rtol=0.0, atol=1e-9).all()
    ):
        raise AssertionError("exact-Greek snapshot contract identity mismatch")
    if frame[["timestamp", "underlying_timestamp"]].isna().any().any():
        raise AssertionError("exact-Greek snapshot contains invalid timestamps")
    if not frame["timestamp"].eq(frame["underlying_timestamp"]).all():
        raise AssertionError("exact-Greek snapshot timestamp differs from underlying_timestamp")
    expected = decision_timestamps()
    observed = pd.DatetimeIndex(frame["timestamp"].sort_values(kind="stable"))
    if not observed.equals(expected) or frame.duplicated("timestamp").any():
        raise AssertionError("exact-Greek snapshot does not cover the exact 48 decision timestamps")
    numeric_columns = [
        "underlying_price", "implied_vol", "delta", "theta", "vega", "rho", "bid", "ask", *extras,
    ]
    numeric = frame[numeric_columns].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(numeric.to_numpy(float)).all():
        raise AssertionError("exact-Greek snapshot contains non-finite numeric values")
    if (
        not numeric["underlying_price"].gt(0.0).all()
        or numeric[["implied_vol", "bid", "ask"]].lt(0.0).any().any()
    ):
        raise AssertionError("exact-Greek snapshot contains invalid spot/IV/quotes")
    frame[numeric_columns] = numeric
    return frame.sort_values("timestamp", kind="stable").reset_index(drop=True)


def validate_sealed_sidecar(
    index_path: str | Path,
    seal_path: str | Path,
    canonical_manifest_path: str | Path,
    *,
    enforce_frozen: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Validate every sealed source hash and return exact rows plus OI universe."""
    index_path = Path(index_path)
    seal_path = Path(seal_path)
    manifest_path = Path(canonical_manifest_path)
    seal = _read_json(seal_path, "exact-Greek capture seal")
    if seal.get("schema") != SEAL_SCHEMA or seal.get("status") != SEAL_STATUS:
        raise AssertionError("exact-Greek sidecar is not a PASS V1R2 capture seal")
    if seal.get("outcome_free") is not True or seal.get("holdout_2026_used") is not False:
        raise AssertionError("exact-Greek capture seal violates outcome-free/pre-2026 scope")
    if str(seal.get("historical_provenance")) != "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION":
        raise AssertionError("exact-Greek capture seal has unexpected historical provenance")
    _require_file_hash(index_path, seal.get("index_sha256"), "exact-Greek capture index")
    _require_file_hash(manifest_path, seal.get("source_manifest_sha256"), "canonical source manifest")
    if enforce_frozen and sha256_file(manifest_path) != EXPECTED_BASE_HASHES["manifest"]:
        raise AssertionError("exact-Greek repair does not use the canonical frozen manifest")
    if str(seal.get("builder_sha256")) != sha256_file(PROJECT_ROOT / "neural/jepa/build_wall_exact_greek_repair_sidecar.py"):
        raise AssertionError("exact-Greek capture builder hash mismatch")
    if str(seal.get("predeclaration_sha256")) != sha256_file(PREDECLARATION):
        raise AssertionError("exact-Greek repair predeclaration hash mismatch")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    if (
        str(seal.get("runtime_lock_sha256")) != runtime["lock_sha256"]
        or str(seal.get("runtime_environment_sha256")) != runtime["environment_sha256"]
    ):
        raise AssertionError("exact-Greek capture runtime provenance mismatch")

    index = pd.read_csv(index_path, dtype={"trade_date": str})
    if tuple(index.columns) != INDEX_COLUMNS:
        raise AssertionError(f"exact-Greek capture index schema mismatch: {list(index.columns)}")
    index["ticker"] = index["ticker"].astype(str).str.upper()
    index["trade_date"] = index["trade_date"].map(_day)
    index["right"] = index["right"].map(_right)
    index["strike"] = pd.to_numeric(index["strike"], errors="coerce")
    if index[["ticker", "trade_date", "strike", "right"]].isna().any().any():
        raise AssertionError("exact-Greek capture index has invalid contract keys")
    if index.duplicated(["ticker", "trade_date", "strike", "right"]).any():
        raise AssertionError("exact-Greek capture index has duplicate contracts")
    if set(index["ticker"]) != set(TARGET_TICKERS) or not index["trade_date"].eq(TARGET_DATE).all():
        raise AssertionError("exact-Greek capture index is outside the frozen repair scope")
    counts = index.groupby("ticker", observed=True).size().astype(int).to_dict()
    observed_contract_hash = contract_key_hash(index)
    if enforce_frozen and (
        len(index) != EXPECTED_CONTRACTS
        or counts != EXPECTED_CONTRACTS_BY_TICKER
        or observed_contract_hash != EXPECTED_CONTRACT_KEY_SHA256
    ):
        raise AssertionError("exact-Greek capture index does not cover the frozen 671-contract universe")
    if (
        int(seal.get("contracts", -1)) != len(index)
        or {str(key): int(value) for key, value in seal.get("contracts_by_ticker", {}).items()} != counts
        or str(seal.get("contract_key_sha256")) != observed_contract_hash
        or int(seal.get("exact_rows", -1)) != len(index) * EXPECTED_TIMESTAMPS
        or int(seal.get("timestamps_per_contract", -1)) != EXPECTED_TIMESTAMPS
        or list(seal.get("decision_times", [])) != list(DECISION_TIMES)
    ):
        raise AssertionError("exact-Greek capture seal coverage differs from its index")
    rows = pd.to_numeric(index["rows"], errors="coerce")
    differences = pd.to_numeric(index["max_spot_difference_bps"], errors="coerce")
    strict_quote = index["stored_bid_ask_exact"].map(lambda value: _strict_bool(value, "stored_bid_ask_exact"))
    if (
        rows.isna().any() or not rows.eq(EXPECTED_TIMESTAMPS).all()
        or differences.isna().any() or not differences.le(SPOT_TOLERANCE_BPS).all()
        or not strict_quote.all()
    ):
        raise AssertionError("exact-Greek capture index failed its per-contract coverage gate")
    jar_hash = str(seal.get("terminal_jar_sha256", ""))
    if not jar_hash or set(index["terminal_jar_sha256"].astype(str)) != {jar_hash}:
        raise AssertionError("exact-Greek capture index has inconsistent Terminal JAR hashes")
    if set(index["git_commit"].astype(str)) != {str(seal.get("git_commit"))}:
        raise AssertionError("exact-Greek capture index has inconsistent build commits")
    process_ids = sorted(pd.to_numeric(index["terminal_process_id"], errors="coerce").dropna().astype(int).unique().tolist())
    java_hashes = sorted(index["java_executable_sha256"].astype(str).unique().tolist())
    if (
        process_ids != [int(value) for value in seal.get("terminal_process_ids", process_ids)]
        or java_hashes != [str(value) for value in seal.get("java_executable_sha256", java_hashes)]
        or seal.get("errors", []) != []
    ):
        raise AssertionError("exact-Greek capture process/error inventory differs from its index")
    terminal_jar_path = seal.get("terminal_jar_path")
    if terminal_jar_path is not None:
        _require_file_hash(Path(str(terminal_jar_path)), jar_hash, "captured Theta Terminal JAR")

    universe = discover_contract_universe(
        manifest_path,
        require_canonical_hash=enforce_frozen,
        enforce_frozen=enforce_frozen,
    )
    universe_keys = universe[["ticker", "trade_date", "strike", "right"]].copy()
    universe_keys["right"] = universe_keys["right"].map(_right)
    parity = index.merge(
        universe_keys,
        on=["ticker", "trade_date", "strike", "right"],
        how="outer", indicator=True, validate="one_to_one",
    )
    if len(parity) != len(index) or not parity["_merge"].eq("both").all():
        raise AssertionError("sealed exact-Greek contracts differ from positive-OI stored universe")
    universe_lookup = universe.assign(right=universe["right"].map(_right)).set_index(
        ["ticker", "trade_date", "strike", "right"]
    )
    if not universe_lookup.index.is_unique:
        raise AssertionError("canonical positive-OI universe has duplicate contracts")

    frames: list[pd.DataFrame] = []
    exact_schema: tuple[str, ...] | None = None
    for row in index.sort_values(["ticker", "strike", "right"], kind="stable").itertuples(index=False):
        key = (str(row.ticker), str(row.trade_date), float(row.strike), str(row.right))
        source = universe_lookup.loc[key]
        for source_name in ("greeks", "oi", "underlying"):
            indexed_hash = str(getattr(row, f"source_{source_name}_sha256"))
            if indexed_hash != str(source[f"{source_name}_sha256"]):
                raise AssertionError(f"{source_name} hash differs between index and canonical universe: {key}")
            _require_file_hash(Path(str(source[f"{source_name}_path"])), indexed_hash, f"source {source_name}")

        raw_path = Path(str(row.raw_response_path))
        exact_path = Path(str(row.exact_greeks_path))
        contract_manifest_path = Path(str(row.contract_manifest_path))
        _require_file_hash(raw_path, row.raw_response_sha256, "raw exact-Greek response")
        _require_file_hash(exact_path, row.exact_greeks_sha256, "exact-Greek snapshot")
        _require_file_hash(contract_manifest_path, row.contract_manifest_sha256, "exact-Greek contract manifest")
        contract = _read_json(contract_manifest_path, "exact-Greek contract manifest")
        if contract.get("schema") != "wall_exact_greek_repair_contract_v1r2":
            raise AssertionError("unexpected exact-Greek contract manifest schema")
        if contract.get("outcome_free") is not True or contract.get("holdout_2026_used") is not False:
            raise AssertionError("exact-Greek contract manifest violates outcome-free/pre-2026 scope")
        if (
            str(contract.get("ticker")) != key[0]
            or _day(contract.get("trade_date")) != key[1]
            or not np.isclose(float(contract.get("strike")), key[2], rtol=0.0, atol=1e-9)
            or _right(contract.get("right")) != key[3]
        ):
            raise AssertionError("exact-Greek contract manifest identity differs from index")
        manifest_pairs = {
            "raw_response_sha256": str(row.raw_response_sha256),
            "exact_greeks_sha256": str(row.exact_greeks_sha256),
            "source_greeks_sha256": str(row.source_greeks_sha256),
            "source_oi_sha256": str(row.source_oi_sha256),
            "source_underlying_sha256": str(row.source_underlying_sha256),
            "terminal_jar_sha256": jar_hash,
            "builder_sha256": str(seal.get("builder_sha256")),
            "predeclaration_sha256": str(seal.get("predeclaration_sha256")),
            "runtime_lock_sha256": str(seal.get("runtime_lock_sha256")),
            "runtime_environment_sha256": str(seal.get("runtime_environment_sha256")),
            "git_commit": str(seal.get("git_commit")),
        }
        if any(str(contract.get(name)) != value for name, value in manifest_pairs.items()):
            raise AssertionError("exact-Greek contract manifest provenance differs from sealed index")
        expected_source_paths = {
            "source_greeks_path": Path(str(source["greeks_path"])),
            "source_oi_path": Path(str(source["oi_path"])),
            "source_underlying_path": Path(str(source["underlying_path"])),
            "source_source_manifest_path": manifest_path,
        }
        for field, expected_path in expected_source_paths.items():
            if str(Path(str(contract.get(field, ""))).resolve()) != str(expected_path.resolve()):
                raise AssertionError(f"exact-Greek contract manifest source path substitution: {field}")
        if str(contract.get("source_source_manifest_sha256")) != sha256_file(manifest_path):
            raise AssertionError("exact-Greek contract manifest canonical-manifest hash mismatch")
        contract_dir = Path(str(row.contract_dir))
        expected_files = {
            raw_path: contract_dir / "first_order_response.json",
            exact_path: contract_dir / "exact_greeks.parquet",
            contract_manifest_path: contract_dir / "manifest.json",
        }
        if any(path.resolve() != expected.resolve() for path, expected in expected_files.items()):
            raise AssertionError("exact-Greek index substitutes a file outside its contract directory")
        if int(contract.get("rows", -1)) != EXPECTED_TIMESTAMPS:
            raise AssertionError("exact-Greek contract manifest row count mismatch")
        declared_columns = contract.get("columns")
        if not isinstance(declared_columns, list) or not all(isinstance(value, str) for value in declared_columns):
            raise AssertionError("exact-Greek contract manifest lacks an exact column schema")
        exact = _validate_exact_snapshot(
            exact_path, ticker=key[0], strike=key[2], right=key[3], declared_columns=declared_columns,
        )
        if exact_schema is None:
            exact_schema = tuple(exact.columns)
        elif tuple(exact.columns) != exact_schema:
            raise AssertionError("exact-Greek snapshots do not share one frozen schema")
        frames.append(exact)

    exact_rows = pd.concat(frames, ignore_index=True)
    if len(exact_rows) != len(index) * EXPECTED_TIMESTAMPS:
        raise AssertionError("exact-Greek snapshot concatenation lost rows")
    audit = {
        "seal_sha256": sha256_file(seal_path),
        "index_sha256": sha256_file(index_path),
        "contracts": int(len(index)),
        "contracts_by_ticker": counts,
        "contract_key_sha256": observed_contract_hash,
        "exact_rows": int(len(exact_rows)),
        "exact_schema": list(exact_schema or ()),
        "raw_response_hash_inventory_sha256": _hash_sequence(index["raw_response_sha256"].astype(str)),
        "contract_manifest_hash_inventory_sha256": _hash_sequence(index["contract_manifest_sha256"].astype(str)),
        "exact_snapshot_hash_inventory_sha256": _hash_sequence(index["exact_greeks_sha256"].astype(str)),
        "terminal_jar_sha256": jar_hash,
        "capture_git_commit": str(seal.get("git_commit")),
        "historical_provenance": str(seal.get("historical_provenance")),
    }
    return exact_rows, universe, audit


def _read_base_walls(path: Path, *, enforce_frozen: bool) -> pd.DataFrame:
    if enforce_frozen and sha256_file(path) != EXPECTED_BASE_HASHES["walls"]:
        raise AssertionError("base wall parquet hash mismatch")
    frame = pd.read_parquet(path)
    frame = _normalize_keys(frame, "base walls")
    assert_wall_state_schema(frame)
    _assert_no_forbidden_columns(frame, "base walls")
    target = frame.merge(expected_repair_keys(), on=list(KEY_COLUMNS), how="inner", validate="one_to_one")
    if len(target) != EXPECTED_REPAIR_ROWS:
        raise AssertionError("base walls do not contain the exact 96 repair keys")
    return frame


def _read_base_events(path: Path, *, enforce_frozen: bool) -> pd.DataFrame:
    if enforce_frozen and sha256_file(path) != EXPECTED_BASE_HASHES["events"]:
        raise AssertionError("base event parquet hash mismatch")
    available = set(pq.ParquetFile(path).schema_arrow.names)
    missing = sorted(set(EVENT_COLUMNS).difference(available))
    if missing:
        raise KeyError(f"base event parquet missing causal control columns: {missing}")
    # Deliberately do not read any other event columns; the source contains
    # option outcomes that are outside this pre-outcome repair stage.
    frame = pd.read_parquet(path, columns=list(EVENT_COLUMNS))
    frame = _normalize_keys(frame, "base event controls")
    _assert_no_forbidden_columns(frame, "base event controls")
    target = frame.merge(expected_repair_keys(), on=list(KEY_COLUMNS), how="inner", validate="one_to_one")
    if len(target) != EXPECTED_REPAIR_ROWS:
        raise AssertionError("base events do not contain the exact 96 repair keys")
    return frame


def _target_source_rows(manifest_path: Path) -> pd.DataFrame:
    manifest = pd.read_csv(manifest_path, dtype=str)
    required = {"ticker", "trade_date", "underlying_path", "oi_path", "greeks_path"}
    missing = sorted(required.difference(manifest.columns))
    if missing:
        raise KeyError(f"canonical manifest missing repair source columns: {missing}")
    manifest["ticker"] = manifest["ticker"].astype(str).str.upper()
    manifest["trade_date"] = manifest["trade_date"].map(_day)
    target = manifest[
        manifest["ticker"].isin(TARGET_TICKERS) & manifest["trade_date"].eq(TARGET_DATE)
    ].copy()
    if len(target) != len(TARGET_TICKERS) or target.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("canonical manifest does not have exactly two repair source sessions")
    return target.sort_values("ticker", kind="stable").reset_index(drop=True)


def build_event_control_repair(manifest_path: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    frames: list[pd.DataFrame] = []
    sources: list[dict[str, Any]] = []
    for row in _target_source_rows(Path(manifest_path)).itertuples(index=False):
        ticker = str(row.ticker)
        path = Path(str(row.underlying_path))
        source_hash = sha256_file(path)
        available = set(pq.ParquetFile(path).schema_arrow.names)
        required = {"symbol", "date", "timestamp", "open"}
        missing = sorted(required.difference(available))
        if missing:
            raise KeyError(f"derived underlying missing causal control columns: {missing}")
        underlying = pd.read_parquet(path, columns=sorted(required))
        underlying["symbol"] = underlying["symbol"].astype(str).str.upper()
        underlying["date"] = underlying["date"].map(_day)
        underlying["timestamp"] = pd.to_datetime(underlying["timestamp"], errors="coerce")
        underlying["open"] = pd.to_numeric(underlying["open"], errors="coerce")
        if (
            underlying.empty or not underlying["symbol"].eq(ticker).all()
            or not underlying["date"].eq(TARGET_DATE).all()
            or underlying[["timestamp", "open"]].isna().any().any()
            or not np.isfinite(underlying["open"]).all() or not underlying["open"].gt(0.0).all()
            or underlying.duplicated("timestamp").any()
        ):
            raise AssertionError("derived underlying violates exact symbol/date/grid/open semantics")
        lookup_frame = underlying.set_index("timestamp")
        if not lookup_frame.index.is_unique:
            raise AssertionError("derived underlying has duplicate timestamps")
        lookup = lookup_frame["open"]
        timestamps = decision_timestamps()
        needed = pd.DatetimeIndex(sorted({stamp - pd.Timedelta(minutes=lag) for stamp in timestamps for lag in (0, *RETURN_LAGS)}))
        missing_times = needed.difference(pd.DatetimeIndex(lookup.index))
        if len(missing_times):
            raise AssertionError(f"derived underlying lacks causal control timestamps: {missing_times[:5].tolist()}")
        current = lookup.reindex(timestamps).to_numpy(float)
        frame = pd.DataFrame({
            "ticker": ticker,
            "trade_date": TARGET_DATE,
            "minute": [stamp.hour * 60 + stamp.minute for stamp in timestamps],
            "spot": current,
        })
        for lag in RETURN_LAGS:
            prior = lookup.reindex(timestamps - pd.Timedelta(minutes=lag)).to_numpy(float)
            frame[f"ret_{lag}m_bps"] = (current / prior - 1.0) * 10_000.0
        if not np.isfinite(frame[["spot", *[f"ret_{lag}m_bps" for lag in RETURN_LAGS]]].to_numpy(float)).all():
            raise AssertionError("rebuilt event controls contain non-finite values")
        frames.append(frame)
        sources.append({"ticker": ticker, "path": str(path), "sha256": source_hash, "rows_read": int(len(underlying))})
    output = pd.concat(frames, ignore_index=True).sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)
    output = _assert_exact_repair_keys(output, "event control repair")
    output = output[list(EVENT_COLUMNS)]
    _assert_no_forbidden_columns(output, "event control repair")
    return output, {"underlying_sources": sources, "causal_return_formula": "(open(t)/open(t-lag)-1)*10000"}


def build_wall_repair(
    exact_rows: pd.DataFrame,
    universe: pd.DataFrame,
    base_walls: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    oi = universe[["ticker", "trade_date", "strike", "right", "open_interest"]].copy()
    oi["ticker"] = oi["ticker"].astype(str).str.upper()
    oi["trade_date"] = oi["trade_date"].map(_day)
    oi["right"] = oi["right"].map(_right)
    oi["strike"] = pd.to_numeric(oi["strike"], errors="coerce")
    oi["open_interest"] = pd.to_numeric(oi["open_interest"], errors="coerce")
    if oi.isna().any().any() or not np.isfinite(oi[["strike", "open_interest"]].to_numpy(float)).all():
        raise AssertionError("frozen OI universe contains invalid rows")
    if not oi["open_interest"].gt(0.0).all() or oi.duplicated(["ticker", "trade_date", "strike", "right"]).any():
        raise AssertionError("frozen OI universe is not a unique strictly-positive contract table")
    exact = exact_rows.copy()
    exact["ticker"] = exact["symbol"].astype(str).str.upper()
    exact["right"] = exact["right"].map(_right)
    exact["dt"] = pd.to_datetime(exact["timestamp"], errors="coerce")
    exact["strike"] = pd.to_numeric(exact["strike"], errors="coerce")
    exact["trade_date"] = exact["trade_date"].map(_day)
    chain = exact.merge(
        oi,
        on=["ticker", "trade_date", "strike", "right"],
        how="left", validate="many_to_one",
    )
    if chain["open_interest"].isna().any() or len(chain) != len(exact):
        raise AssertionError("exact-Greek/OI join lost a frozen positive-OI contract")
    frames: list[pd.DataFrame] = []
    active_rows: dict[str, int] = {}
    for ticker, part in chain.groupby("ticker", observed=True, sort=True):
        wall_chain = part[["dt", "strike", "right", "underlying_price", "implied_vol", "open_interest"]].copy()
        states = compute_wall_states(wall_chain)
        if len(states) != EXPECTED_TIMESTAMPS:
            raise AssertionError(f"repaired {ticker} wall does not contain exactly 48 snapshots")
        states.insert(0, "ticker", str(ticker))
        states.insert(1, "trade_date", TARGET_DATE)
        frames.append(states)
        active_rows[str(ticker)] = int((pd.to_numeric(wall_chain["implied_vol"], errors="coerce") > 0.0).sum())
    repair = pd.concat(frames, ignore_index=True)
    repair = add_wall_persistence(repair)
    repair = _assert_exact_repair_keys(repair, "wall repair")
    assert_wall_state_schema(repair)
    _assert_no_forbidden_columns(repair, "wall repair")
    if set(repair.columns) != set(base_walls.columns):
        missing = sorted(set(base_walls.columns).difference(repair.columns))
        extra = sorted(set(repair.columns).difference(base_walls.columns))
        raise AssertionError(f"wall repair schema differs from base walls: missing={missing} extra={extra}")
    repair = repair.reindex(columns=base_walls.columns)
    for column in repair.columns:
        try:
            repair[column] = repair[column].astype(base_walls[column].dtype)
        except (TypeError, ValueError) as exc:
            raise AssertionError(f"wall repair dtype cannot match base column {column}") from exc
    assert_wall_state_schema(repair)
    return repair.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True), {
        "positive_iv_exposure_rows_by_ticker": active_rows,
        "exposure_formula_module": "neural/jepa/wall_state_features.py",
    }


def audit_exact_spot_against_controls(exact_rows: pd.DataFrame, controls: pd.DataFrame) -> dict[str, Any]:
    exact = exact_rows[["symbol", "trade_date", "timestamp", "underlying_price"]].copy()
    exact["ticker"] = exact.pop("symbol").astype(str).str.upper()
    exact["trade_date"] = exact["trade_date"].map(_day)
    exact["timestamp"] = pd.to_datetime(exact["timestamp"], errors="coerce")
    exact["minute"] = exact["timestamp"].dt.hour * 60 + exact["timestamp"].dt.minute
    exact["underlying_price"] = pd.to_numeric(exact["underlying_price"], errors="coerce")
    joined = exact.merge(
        controls[list(KEY_COLUMNS) + ["spot"]],
        on=list(KEY_COLUMNS), how="left", validate="many_to_one",
    )
    difference = (
        (joined["underlying_price"] - pd.to_numeric(joined["spot"], errors="coerce")).abs()
        / pd.to_numeric(joined["spot"], errors="coerce") * 10_000.0
    )
    if (
        len(joined) != len(exact) or joined["spot"].isna().any()
        or not np.isfinite(difference).all() or float(difference.max()) > SPOT_TOLERANCE_BPS
    ):
        raise AssertionError(f"exact-Greek rows differ from causal derived open(t): max_bps={difference.max()}")
    return {
        "rows_compared": int(len(joined)),
        "maximum_exact_greek_control_spot_difference_bps": float(difference.max()),
    }


def apply_repair_overlay(base: pd.DataFrame, repair: pd.DataFrame, *, label: str) -> pd.DataFrame:
    """Replace exactly the frozen 96 keys while preserving every other row."""
    base_normalized = _normalize_keys(base, f"base {label}")
    repair_normalized = _assert_exact_repair_keys(repair, f"{label} repair")
    if list(base_normalized.columns) != list(repair_normalized.columns):
        raise AssertionError(f"{label} overlay schema/order mismatch")
    target_keys = expected_repair_keys()
    target = base_normalized.merge(target_keys, on=list(KEY_COLUMNS), how="inner", validate="one_to_one")
    if len(target) != EXPECTED_REPAIR_ROWS:
        raise AssertionError(f"base {label} does not contain exactly the frozen 96 keys")
    marker = base_normalized[list(KEY_COLUMNS)].merge(
        target_keys.assign(_repair_target=True), on=list(KEY_COLUMNS), how="left", validate="one_to_one"
    )
    untouched = base_normalized.loc[marker["_repair_target"].isna()].copy()
    output = pd.concat([untouched, repair_normalized], ignore_index=True)
    output = output.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)
    if len(output) != len(base_normalized) or output.duplicated(list(KEY_COLUMNS)).any():
        raise AssertionError(f"{label} overlay changed row count or created duplicate keys")
    before = untouched.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)
    after = output.merge(
        target_keys.assign(_repair_target=True), on=list(KEY_COLUMNS), how="left", validate="one_to_one"
    )
    after = after[after["_repair_target"].isna()].drop(columns="_repair_target").reset_index(drop=True)
    pd.testing.assert_frame_equal(after, before, check_dtype=True, obj=f"untouched {label} rows")
    return output


def load_repair_bundle(
    manifest_path: str | Path,
    *,
    enforce_frozen: bool = True,
    require_committed: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Load and fail-closed validate a compact committed V1R2 repair bundle."""
    manifest_path = Path(manifest_path)
    manifest = _read_json(manifest_path, "exact-Greek repair artifact manifest")
    if manifest.get("schema") != OUTPUT_SCHEMA or manifest.get("status") != OUTPUT_STATUS:
        raise AssertionError("exact-Greek repair artifact bundle is not PASS V1R2")
    if (
        manifest.get("outcome_free") is not True
        or manifest.get("holdout_2026_used") is not False
        or manifest.get("production_modified") is not False
    ):
        raise AssertionError("exact-Greek repair bundle violates outcome-free/pre-2026/production scope")
    if str(manifest.get("historical_provenance")) != "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION":
        raise AssertionError("exact-Greek repair bundle has unexpected historical provenance")
    expected_sessions = [{"ticker": ticker, "trade_date": TARGET_DATE} for ticker in TARGET_TICKERS]
    if manifest.get("target_sessions") != expected_sessions or int(manifest.get("target_rows", -1)) != EXPECTED_REPAIR_ROWS:
        raise AssertionError("exact-Greek repair bundle target scope differs from the frozen 96 keys")
    if float(manifest.get("spot_tolerance_bps", np.nan)) != SPOT_TOLERANCE_BPS:
        raise AssertionError("exact-Greek repair bundle changes the frozen spot tolerance")
    input_hashes = manifest.get("input_sha256")
    if not isinstance(input_hashes, dict):
        raise AssertionError("exact-Greek repair bundle lacks its input hash inventory")
    if enforce_frozen and any(str(input_hashes.get(name)) != digest for name, digest in EXPECTED_BASE_HASHES.items()):
        raise AssertionError("exact-Greek repair bundle was not derived from the frozen base inputs")
    sidecar_audit = manifest.get("sidecar_audit")
    if not isinstance(sidecar_audit, dict):
        raise AssertionError("exact-Greek repair bundle lacks sealed-sidecar audit evidence")
    if enforce_frozen and (
        int(sidecar_audit.get("contracts", -1)) != EXPECTED_CONTRACTS
        or sidecar_audit.get("contracts_by_ticker") != EXPECTED_CONTRACTS_BY_TICKER
        or str(sidecar_audit.get("contract_key_sha256")) != EXPECTED_CONTRACT_KEY_SHA256
        or int(sidecar_audit.get("exact_rows", -1)) != EXPECTED_CONTRACTS * EXPECTED_TIMESTAMPS
    ):
        raise AssertionError("exact-Greek repair bundle lacks the frozen 671-contract sidecar coverage")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    code_hashes = {
        "builder_sha256": sha256_file(__file__),
        "sidecar_builder_sha256": sha256_file(PROJECT_ROOT / "neural/jepa/build_wall_exact_greek_repair_sidecar.py"),
        "wall_feature_module_sha256": sha256_file(PROJECT_ROOT / "neural/jepa/wall_state_features.py"),
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
    }
    if any(str(manifest.get(name)) != value for name, value in code_hashes.items()):
        raise AssertionError("exact-Greek repair bundle code/runtime provenance mismatch")

    # Bundles may be copied from their build directory into a tracked compact
    # diagnostics directory.  Resolve immutable artifacts as manifest siblings;
    # the original absolute build paths remain recorded only as provenance.
    wall_path = manifest_path.parent / "wall_repair.parquet"
    event_path = manifest_path.parent / "event_control_repair.parquet"
    if require_committed:
        for path, label in (
            (manifest_path, "repair manifest"),
            (wall_path, "wall repair"),
            (event_path, "event-control repair"),
        ):
            assert_committed_artifact(path, label)
    _require_file_hash(wall_path, manifest.get("wall_repair_sha256"), "wall repair")
    _require_file_hash(event_path, manifest.get("event_control_repair_sha256"), "event-control repair")
    walls = pd.read_parquet(wall_path)
    controls = pd.read_parquet(event_path)
    walls = _assert_exact_repair_keys(walls, "wall repair bundle")
    controls = _assert_exact_repair_keys(controls, "event-control repair bundle")
    assert_wall_state_schema(walls)
    _assert_no_forbidden_columns(walls, "wall repair bundle")
    _assert_no_forbidden_columns(controls, "event-control repair bundle")
    if list(controls.columns) != list(EVENT_COLUMNS):
        raise AssertionError("event-control repair bundle schema/order mismatch")
    if (
        int(manifest.get("wall_repair_rows", -1)) != len(walls)
        or int(manifest.get("event_control_repair_rows", -1)) != len(controls)
        or str(manifest.get("wall_repair_schema_sha256")) != _schema_hash(walls)
        or str(manifest.get("event_control_repair_schema_sha256")) != _schema_hash(controls)
    ):
        raise AssertionError("exact-Greek repair bundle row/schema manifest mismatch")
    joined = walls[list(KEY_COLUMNS) + ["spot"]].merge(
        controls[list(KEY_COLUMNS) + ["spot"]], on=list(KEY_COLUMNS),
        suffixes=("_wall", "_control"), validate="one_to_one",
    )
    difference = (
        (pd.to_numeric(joined["spot_wall"], errors="coerce") - pd.to_numeric(joined["spot_control"], errors="coerce")).abs()
        / pd.to_numeric(joined["spot_control"], errors="coerce") * 10_000.0
    )
    if not np.isfinite(difference).all() or float(difference.max()) > SPOT_TOLERANCE_BPS:
        raise AssertionError("exact-Greek repair bundle wall/control spot parity failed")
    if not np.isclose(
        float(manifest.get("maximum_wall_control_spot_difference_bps", np.nan)),
        float(difference.max()), rtol=0.0, atol=1e-15,
    ):
        raise AssertionError("exact-Greek repair bundle spot audit differs from its manifest")
    return walls, controls, manifest


def build_repair_artifacts(
    *,
    sidecar_index: str | Path,
    sidecar_seal: str | Path,
    base_walls: str | Path,
    base_events: str | Path,
    canonical_manifest: str | Path,
    output_dir: str | Path,
    enforce_frozen: bool = True,
    require_committed: bool = True,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    staging = output_dir.with_name(f"{output_dir.name}.staging")
    if output_dir.exists() or staging.exists():
        raise FileExistsError(f"immutable repair output already exists: {output_dir}")
    paths = {
        "sidecar_index": Path(sidecar_index), "sidecar_seal": Path(sidecar_seal),
        "walls": Path(base_walls), "events": Path(base_events), "manifest": Path(canonical_manifest),
    }
    for label, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"missing repair input {label}: {path}")
    input_hashes = {label: sha256_file(path) for label, path in paths.items()}
    if enforce_frozen:
        for label in ("walls", "events", "manifest"):
            if input_hashes[label] != EXPECTED_BASE_HASHES[label]:
                raise AssertionError(f"frozen {label} input hash mismatch")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    build_commit = assert_committed_code() if require_committed else current_git_commit()
    exact_rows, universe, sidecar_audit = validate_sealed_sidecar(
        paths["sidecar_index"], paths["sidecar_seal"], paths["manifest"], enforce_frozen=enforce_frozen,
    )
    walls = _read_base_walls(paths["walls"], enforce_frozen=enforce_frozen)
    events = _read_base_events(paths["events"], enforce_frozen=enforce_frozen)
    event_repair, control_audit = build_event_control_repair(paths["manifest"])
    exact_spot_audit = audit_exact_spot_against_controls(exact_rows, event_repair)
    wall_repair, wall_audit = build_wall_repair(exact_rows, universe, walls)
    event_repair = event_repair.astype({column: events[column].dtype for column in EVENT_COLUMNS})
    event_repair = _assert_exact_repair_keys(event_repair, "event control repair")[list(EVENT_COLUMNS)]
    joined = wall_repair[list(KEY_COLUMNS) + ["spot"]].merge(
        event_repair[list(KEY_COLUMNS) + ["spot"]],
        on=list(KEY_COLUMNS), suffixes=("_wall", "_control"), validate="one_to_one",
    )
    spot_diff = (
        (pd.to_numeric(joined["spot_wall"], errors="coerce") - pd.to_numeric(joined["spot_control"], errors="coerce")).abs()
        / pd.to_numeric(joined["spot_control"], errors="coerce") * 10_000.0
    )
    if len(joined) != EXPECTED_REPAIR_ROWS or not np.isfinite(spot_diff).all() or float(spot_diff.max()) > SPOT_TOLERANCE_BPS:
        raise AssertionError(f"repaired wall/control spot parity failed: max_bps={spot_diff.max()}")
    # Exercise the overlay invariant now, without writing a modified base file.
    wall_overlay = apply_repair_overlay(walls, wall_repair, label="walls")
    event_overlay = apply_repair_overlay(events[list(EVENT_COLUMNS)], event_repair, label="event controls")
    if len(wall_overlay) != len(walls) or len(event_overlay) != len(events):
        raise AssertionError("repair overlay changed a base row count")

    staging.mkdir(parents=True, exist_ok=False)
    wall_path = staging / "wall_repair.parquet"
    event_path = staging / "event_control_repair.parquet"
    wall_repair.to_parquet(wall_path, index=False)
    event_repair.to_parquet(event_path, index=False)
    payload = {
        "schema": OUTPUT_SCHEMA,
        "status": OUTPUT_STATUS,
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": build_commit,
        "target_sessions": [{"ticker": ticker, "trade_date": TARGET_DATE} for ticker in TARGET_TICKERS],
        "target_rows": EXPECTED_REPAIR_ROWS,
        "spot_tolerance_bps": SPOT_TOLERANCE_BPS,
        "maximum_wall_control_spot_difference_bps": float(spot_diff.max()),
        "input_paths": {label: str(path) for label, path in paths.items()},
        "input_sha256": input_hashes,
        "builder_sha256": sha256_file(__file__),
        "sidecar_builder_sha256": sha256_file(PROJECT_ROOT / "neural/jepa/build_wall_exact_greek_repair_sidecar.py"),
        "wall_feature_module_sha256": sha256_file(PROJECT_ROOT / "neural/jepa/wall_state_features.py"),
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "wall_repair_path": str(output_dir / wall_path.name),
        "wall_repair_sha256": sha256_file(wall_path),
        "wall_repair_rows": int(len(wall_repair)),
        "wall_repair_schema_sha256": _schema_hash(wall_repair),
        "event_control_repair_path": str(output_dir / event_path.name),
        "event_control_repair_sha256": sha256_file(event_path),
        "event_control_repair_rows": int(len(event_repair)),
        "event_control_repair_schema_sha256": _schema_hash(event_repair),
        "event_columns_read_from_base": list(EVENT_COLUMNS),
        "sidecar_audit": sidecar_audit,
        "wall_audit": wall_audit,
        "control_audit": control_audit,
        "exact_spot_audit": exact_spot_audit,
        "overlay_audit": {
            "wall_base_rows": int(len(walls)), "wall_overlay_rows": int(len(wall_overlay)),
            "event_base_rows": int(len(events)), "event_overlay_rows": int(len(event_overlay)),
            "non_target_rows_changed": 0,
        },
    }
    manifest_path = staging / "manifest.json"
    manifest_path.write_bytes(canonical_json_bytes(payload))
    staging.rename(output_dir)
    return payload


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar-index", required=True)
    parser.add_argument("--sidecar-seal", required=True)
    parser.add_argument("--walls", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_repair_artifacts(
        sidecar_index=args.sidecar_index,
        sidecar_seal=args.sidecar_seal,
        base_walls=args.walls,
        base_events=args.events,
        canonical_manifest=args.manifest,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
