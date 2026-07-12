"""Build the outcome-free H-QSIZE1 wall-touch feature dataset."""

from __future__ import annotations

import argparse
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

from neural.jepa.build_wall_native_quote_sidecar import (  # noqa: E402
    sha256_file,
)
from neural.jepa.build_wall_quote_size_complement_sidecar import (  # noqa: E402
    EXPECTED_COMPLEMENT_KEY_SHA256,
    EXPECTED_COMPLEMENT_SESSIONS,
)
from neural.jepa.build_wall_surface_flow_dataset import (  # noqa: E402
    EXPECTED_NATIVE_QUOTE_KEY_SHA256,
    EXPECTED_NATIVE_QUOTE_SESSIONS,
    EXPECTED_SESSION_COUNT,
    EXPECTED_SESSION_KEY_SHA256,
    feature_hash,
    session_key_hash,
)
from neural.jepa.quote_size_pressure_features import (  # noqa: E402
    QSIZE_ALLOWLIST,
    QSIZE_FEATURES,
    QSIZE_QUALITY_FIELDS,
    attach_quote_size_features,
    prepare_quote_size_source,
)
from neural.jepa.surface_flow_features import CONTROL_FEATURES, KEY_COLUMNS  # noqa: E402
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402


EXPECTED_CANDIDATE_SHA256 = "6d27fdeb44422daa95aa79f777044e68276a2fe374c9bd847cd475d9dccfdb5b"
EXPECTED_CANDIDATE_ROWS = 10683
EXPECTED_FALLBACK_INDEX_SHA256 = (
    "0abe0ac2f9dcccec4574ee10e4f10ef2904000c80a0cf5fb8f5a90ef333f754a"
)
EXPECTED_FALLBACK_SEAL_SHA256 = (
    "6c2ff5d6321bff5b62cbd19d2a503d05b69332bfa7b26d7c1f585bf617752eaa"
)
PREDECLARATION = "research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_PREDECLARATION.md"
CAUSAL_AMENDMENT = (
    "research_papers/JEPA/"
    "WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_CAUSAL_AMENDMENT.md"
)
RUNTIME_LOCK = "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
AUTHORITATIVE_CODE = (
    "neural/jepa/build_wall_quote_size_pressure_dataset.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    "neural/jepa/build_wall_quote_size_complement_sidecar.py",
    "neural/jepa/build_wall_surface_flow_dataset.py",
    "neural/jepa/quote_size_pressure_features.py",
    "neural/jepa/surface_flow_features.py",
    "neural/jepa/wall_surface_flow_environment.py",
    PREDECLARATION,
    CAUSAL_AMENDMENT,
    RUNTIME_LOCK,
)
CANDIDATE_METADATA = (
    "ticker",
    "trade_date",
    "minute",
    "decision_dt",
    "wall_identity",
    "wall_role",
    "candidate_right",
    "candidate_wall_strike",
    "spot",
    "wall_alias_count",
    "episode_sequence",
    "episode_start_minute",
    "episode_id",
)
CANDIDATE_COLUMNS = tuple(dict.fromkeys((*CANDIDATE_METADATA, *CONTROL_FEATURES)))
QUOTE_COLUMNS = (
    "symbol",
    "expiration",
    "trade_date",
    "timestamp",
    "right",
    "strike",
    "bid",
    "ask",
    "bid_size",
    "ask_size",
)
GREEK_KEY_COLUMNS = ("expiration", "right", "strike")
EXPECTED_TERMINAL_UNAVAILABLE_CANDIDATES = 88


def committed_code_state() -> tuple[str, dict[str, str]]:
    hashes: dict[str, str] = {}
    for relative in AUTHORITATIVE_CODE:
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
            raise AssertionError(f"authoritative H-QSIZE1 build requires clean code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, hashes


def read_columns(path: str | Path, columns: tuple[str, ...]) -> pd.DataFrame:
    names = set(pq.ParquetFile(path).schema_arrow.names)
    missing = sorted(set(columns).difference(names))
    if missing:
        raise KeyError(f"{path} missing columns: {missing}")
    return pd.read_parquet(path, columns=list(columns))


def load_candidates(path: str | Path, manifest_path: str | Path) -> pd.DataFrame:
    if sha256_file(path) != EXPECTED_CANDIDATE_SHA256:
        raise AssertionError("H-QSIZE1 candidate dataset hash mismatch")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if (
        manifest.get("status") != "PASS_DATA_GATE"
        or manifest.get("dataset_sha256") != EXPECTED_CANDIDATE_SHA256
        or manifest.get("holdout_2026_used") is not False
        or int(manifest.get("rows", -1)) != EXPECTED_CANDIDATE_ROWS
    ):
        raise AssertionError("H-QSIZE1 candidate manifest is not the frozen data gate")
    frame = pd.read_parquet(path, columns=list(CANDIDATE_COLUMNS))
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["trade_date"] = frame["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    frame["decision_dt"] = pd.to_datetime(frame["decision_dt"], errors="coerce")
    if (
        len(frame) != EXPECTED_CANDIDATE_ROWS
        or frame.duplicated(list(KEY_COLUMNS)).any()
        or frame["decision_dt"].isna().any()
        or frame["trade_date"].str.startswith("2026").any()
    ):
        raise AssertionError("H-QSIZE1 frozen candidate cardinality/clock changed")
    return frame.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)


def _normalize_index(frame: pd.DataFrame, origin: str) -> pd.DataFrame:
    required = {
        "ticker",
        "trade_date",
        "greeks_path",
        "greeks_sha256",
        "quotes_path",
        "quotes_sha256",
        "raw_response_path",
        "raw_response_sha256",
        "session_manifest_path",
        "session_manifest_sha256",
        "rows",
        "stored_timestamp_key_coverage_exact",
        "missing_stored_key_rows",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError(f"{origin} quote index missing fields: {missing}")
    out = frame.copy()
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["trade_date"] = out["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    out["origin"] = origin
    if (
        out.duplicated(["ticker", "trade_date"]).any()
        or out["trade_date"].str.startswith("2026").any()
        or not out["stored_timestamp_key_coverage_exact"].map(
            lambda value: value if isinstance(value, bool) else str(value).lower() == "true"
        ).all()
        or not pd.to_numeric(out["missing_stored_key_rows"], errors="coerce").eq(0).all()
    ):
        raise AssertionError(f"{origin} quote index violates exact coverage")
    return out


def load_combined_quote_index(
    fallback_index: str | Path,
    fallback_seal: str | Path,
    complement_index: str | Path,
    complement_seal: str | Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if (
        sha256_file(fallback_index) != EXPECTED_FALLBACK_INDEX_SHA256
        or sha256_file(fallback_seal) != EXPECTED_FALLBACK_SEAL_SHA256
    ):
        raise AssertionError("frozen fallback quote-size sidecar hash mismatch")
    fallback_manifest = json.loads(Path(fallback_seal).read_text(encoding="utf-8"))
    complement_manifest = json.loads(Path(complement_seal).read_text(encoding="utf-8"))
    if (
        fallback_manifest.get("status") != "PASS_NATIVE_TIMESTAMP_BACKFILL"
        or int(fallback_manifest.get("fallback_sessions", -1)) != EXPECTED_NATIVE_QUOTE_SESSIONS
        or fallback_manifest.get("fallback_session_key_sha256")
        != EXPECTED_NATIVE_QUOTE_KEY_SHA256
    ):
        raise AssertionError("fallback quote-size seal contract mismatch")
    if (
        complement_manifest.get("status") != "PASS_QSIZE_NATIVE_COMPLEMENT"
        or int(complement_manifest.get("sessions", -1)) != EXPECTED_COMPLEMENT_SESSIONS
        or complement_manifest.get("session_key_sha256") != EXPECTED_COMPLEMENT_KEY_SHA256
        or complement_manifest.get("historical_provenance")
        != "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION"
        or complement_manifest.get("index_sha256") != sha256_file(complement_index)
    ):
        raise AssertionError("H-QSIZE1 complement seal contract mismatch")
    fallback = _normalize_index(pd.read_csv(fallback_index, dtype={"trade_date": str}), "fallback")
    complement = _normalize_index(
        pd.read_csv(complement_index, dtype={"trade_date": str}), "native_complement"
    )
    if (
        len(fallback) != EXPECTED_NATIVE_QUOTE_SESSIONS
        or session_key_hash(fallback) != EXPECTED_NATIVE_QUOTE_KEY_SHA256
        or len(complement) != EXPECTED_COMPLEMENT_SESSIONS
        or session_key_hash(complement) != EXPECTED_COMPLEMENT_KEY_SHA256
    ):
        raise AssertionError("H-QSIZE1 component index universe mismatch")
    combined = pd.concat([fallback, complement], ignore_index=True).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(combined) != EXPECTED_SESSION_COUNT
        or combined.duplicated(["ticker", "trade_date"]).any()
        or session_key_hash(combined) != EXPECTED_SESSION_KEY_SHA256
    ):
        raise AssertionError("H-QSIZE1 combined 2,519-session universe mismatch")
    return combined, {
        "fallback_seal_sha256": sha256_file(fallback_seal),
        "fallback_index_sha256": sha256_file(fallback_index),
        "complement_seal_sha256": sha256_file(complement_seal),
        "complement_index_sha256": sha256_file(complement_index),
        "sessions": len(combined),
        "fallback_sessions": len(fallback),
        "complement_sessions": len(complement),
        "session_key_sha256": session_key_hash(combined),
        "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
    }


def verify_and_inventory(row: dict[str, Any]) -> dict[str, Any]:
    for path_field, hash_field in (
        ("greeks_path", "greeks_sha256"),
        ("quotes_path", "quotes_sha256"),
        ("raw_response_path", "raw_response_sha256"),
        ("session_manifest_path", "session_manifest_sha256"),
    ):
        if sha256_file(row[path_field]) != str(row[hash_field]):
            raise AssertionError(f"H-QSIZE1 source hash mismatch: {path_field}")
    return {
        "ticker": str(row["ticker"]),
        "trade_date": str(row["trade_date"]),
        "origin": str(row["origin"]),
        "greeks_path": str(row["greeks_path"]),
        "greeks_sha256": str(row["greeks_sha256"]),
        "quotes_path": str(row["quotes_path"]),
        "quotes_sha256": str(row["quotes_sha256"]),
        "raw_response_path": str(row["raw_response_path"]),
        "raw_response_sha256": str(row["raw_response_sha256"]),
        "session_manifest_path": str(row["session_manifest_path"]),
        "session_manifest_sha256": str(row["session_manifest_sha256"]),
        "rows": int(row["rows"]),
    }


def build_session(row: dict[str, Any], candidates: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    quotes = read_columns(row["quotes_path"], QUOTE_COLUMNS)
    greek_names = set(pq.ParquetFile(row["greeks_path"]).schema_arrow.names)
    clock_column = "timestamp" if "timestamp" in greek_names else "underlying_timestamp"
    greek_columns = [clock_column, *GREEK_KEY_COLUMNS]
    if set(GREEK_KEY_COLUMNS).difference(greek_names) or clock_column not in greek_names:
        raise KeyError("stored Greek source lacks frozen contract keys")
    frozen_keys = pd.read_parquet(row["greeks_path"], columns=greek_columns).rename(
        columns={clock_column: "timestamp"}
    ).drop_duplicates()
    source, audit = prepare_quote_size_source(
        quotes,
        expected_ticker=str(row["ticker"]),
        expected_trade_date=str(row["trade_date"]),
        frozen_contract_keys=frozen_keys,
    )
    output = attach_quote_size_features(candidates, source)
    if len(output) != len(candidates) or output.duplicated(list(KEY_COLUMNS)).any():
        raise AssertionError("H-QSIZE1 attachment changed frozen candidates")
    unavailable = pd.to_datetime(candidates["decision_dt"]).gt(source["snapshot_dt"].max())
    unavailable_features = output.loc[unavailable, list(QSIZE_FEATURES)].apply(
        pd.to_numeric, errors="coerce"
    )
    if (
        output.loc[unavailable, "qsize_call_valid"].astype(bool).any()
        or output.loc[unavailable, "qsize_put_valid"].astype(bool).any()
        or unavailable_features.notna().any().any()
    ):
        raise AssertionError("unavailable terminal quote created H-QSIZE1 measurements")
    audit["unavailable_terminal_candidates"] = int(unavailable.sum())
    return output, audit


def _numeric_profile_rows(
    work: pd.DataFrame, group_columns: list[str]
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group_key, part in work.groupby(group_columns, sort=True):
        keys = group_key if isinstance(group_key, tuple) else (group_key,)
        identity = dict(zip(group_columns, keys, strict=True))
        for feature in QSIZE_ALLOWLIST:
            values = pd.to_numeric(part[feature], errors="coerce")
            finite = values[np.isfinite(values)]
            rows.append(
                {
                    **identity,
                    "feature": feature,
                    "rows": len(part),
                    "finite": len(finite),
                    "missing_rate": float(1 - len(finite) / len(part)),
                    "zero_rate_finite": float(finite.eq(0).mean())
                    if len(finite)
                    else None,
                    "distinct_finite": int(finite.nunique()),
                    "minimum": float(finite.min()) if len(finite) else None,
                    "maximum": float(finite.max()) if len(finite) else None,
                }
            )
    return pd.DataFrame(rows)


def profile_dataset(
    dataset: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    work = dataset.copy()
    work["year"] = work["trade_date"].str[:4]
    work["month"] = work["trade_date"].str[:6]
    coverage = work.groupby(["ticker", "year", "month"], as_index=False).agg(
        rows=("minute", "size"),
        qsize_both_valid=("qsize_both_valid", "mean"),
        qsize_call_valid=("qsize_call_valid", "mean"),
        qsize_put_valid=("qsize_put_valid", "mean"),
    )
    return (
        coverage,
        _numeric_profile_rows(work, ["ticker", "year"]),
        _numeric_profile_rows(work, ["ticker", "year", "month"]),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--candidate-manifest", required=True)
    parser.add_argument("--fallback-index", required=True)
    parser.add_argument("--fallback-seal", required=True)
    parser.add_argument("--complement-index", required=True)
    parser.add_argument("--complement-seal", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=16)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= int(args.workers) <= 16:
        raise ValueError("H-QSIZE1 workers must be within 1..16")
    commit, code_hashes = committed_code_state()
    runtime = assert_runtime_lock(PROJECT_ROOT / RUNTIME_LOCK)
    candidates = load_candidates(args.candidates, args.candidate_manifest)
    combined, sidecar_provenance = load_combined_quote_index(
        args.fallback_index,
        args.fallback_seal,
        args.complement_index,
        args.complement_seal,
    )
    inventory_rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ProcessPoolExecutor(max_workers=int(args.workers)) as pool:
        futures = {
            pool.submit(verify_and_inventory, row): (row["ticker"], row["trade_date"])
            for row in combined.to_dict("records")
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                inventory_rows.append(future.result())
            except Exception as exc:
                errors.append(
                    {"ticker": key[0], "trade_date": key[1], "error": f"{type(exc).__name__}: {exc}"}
                )
    if errors:
        raise AssertionError(f"H-QSIZE1 source verification failed: {errors[:10]}")
    source_inventory = pd.DataFrame(inventory_rows).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    needed = combined.merge(
        candidates[["ticker", "trade_date"]].drop_duplicates(),
        on=["ticker", "trade_date"],
        how="inner",
        validate="one_to_one",
    )
    outputs: list[pd.DataFrame] = []
    audits: list[dict[str, Any]] = []
    errors = []
    with ProcessPoolExecutor(max_workers=int(args.workers)) as pool:
        futures = {}
        for row in needed.to_dict("records"):
            key = (str(row["ticker"]), str(row["trade_date"]))
            part = candidates[
                candidates["ticker"].eq(key[0]) & candidates["trade_date"].eq(key[1])
            ]
            futures[pool.submit(build_session, row, part)] = key
        for future in as_completed(futures):
            key = futures[future]
            try:
                output, audit = future.result()
                outputs.append(output)
                audits.append({"ticker": key[0], "trade_date": key[1], **audit})
            except Exception as exc:
                errors.append(
                    {"ticker": key[0], "trade_date": key[1], "error": f"{type(exc).__name__}: {exc}"}
                )
    if errors:
        raise AssertionError(f"H-QSIZE1 feature build failed: {errors[:10]}")
    dataset = pd.concat(outputs, ignore_index=True).sort_values(
        list(KEY_COLUMNS), kind="stable"
    ).reset_index(drop=True)
    if len(dataset) != EXPECTED_CANDIDATE_ROWS or dataset.duplicated(list(KEY_COLUMNS)).any():
        raise AssertionError("H-QSIZE1 final candidate universe changed")
    if sum(int(row["unavailable_terminal_candidates"]) for row in audits) != (
        EXPECTED_TERMINAL_UNAVAILABLE_CANDIDATES
    ):
        raise AssertionError("H-QSIZE1 terminal unavailable-candidate contract changed")
    coverage, feature_profile, monthly_feature_profile = profile_dataset(dataset)
    annual_source = dataset.assign(year=dataset["trade_date"].str[:4])
    annual = annual_source.groupby(["ticker", "year"], as_index=False).agg(
        qsize_both_valid=("qsize_both_valid", "mean")
    )
    overall = dataset.groupby("ticker")["qsize_both_valid"].mean()
    coverage_pass = bool(annual["qsize_both_valid"].ge(0.60).all() and overall.ge(0.70).all())
    distinctness_pass = bool(
        feature_profile[feature_profile["feature"].isin(QSIZE_FEATURES)]["distinct_finite"]
        .ge(2)
        .all()
    )
    controls = dataset[list(CONTROL_FEATURES)].apply(pd.to_numeric, errors="coerce")
    control_coverage_pass = bool(np.isfinite(controls.to_numpy(dtype=float)).all())
    data_gate_pass = bool(coverage_pass and distinctness_pass and control_coverage_pass)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    dataset_path = output_dir / "wall_quote_size_pressure_at_touch.parquet"
    source_path = output_dir / "quote_size_source_hashes.csv"
    dataset.to_parquet(dataset_path, index=False)
    source_inventory.to_csv(source_path, index=False)
    pd.DataFrame(audits).to_csv(output_dir / "session_audit.csv", index=False)
    coverage.to_csv(output_dir / "coverage_by_month.csv", index=False)
    feature_profile.to_csv(output_dir / "feature_profile.csv", index=False)
    monthly_feature_profile.to_csv(
        output_dir / "feature_profile_by_month.csv", index=False
    )
    origin_frame = dataset.merge(
        combined[["ticker", "trade_date", "origin"]],
        on=["ticker", "trade_date"],
        how="left",
        validate="many_to_one",
    ).assign(year=lambda frame: frame["trade_date"].str[:4])
    origin_profile = origin_frame.groupby(
        ["ticker", "year", "origin"], as_index=False
    ).agg(
        candidates=("minute", "size"),
        sessions=("trade_date", "nunique"),
        qsize_both_valid=("qsize_both_valid", "mean"),
    )
    origin_profile.to_csv(output_dir / "source_origin_profile.csv", index=False)
    schema = {"columns": [{"name": name, "dtype": str(dataset[name].dtype)} for name in dataset]}
    (output_dir / "schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    manifest = {
        "schema": "wall_quote_size_pressure_at_touch_dataset_v1",
        "status": "PASS_DATA_GATE" if data_gate_pass else "REJECTED_DATA_GATE",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "git_commit": commit,
        "code_hashes": code_hashes,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "rows": len(dataset),
        "columns": len(dataset.columns),
        "dataset": str(dataset_path),
        "dataset_sha256": sha256_file(dataset_path),
        "candidate_sha256": EXPECTED_CANDIDATE_SHA256,
        "source_inventory": str(source_path),
        "source_inventory_sha256": sha256_file(source_path),
        "sidecar_provenance": sidecar_provenance,
        "control_feature_hash": feature_hash(CONTROL_FEATURES),
        "qsize_feature_hash": feature_hash(QSIZE_FEATURES),
        "qsize_quality_hash": feature_hash(QSIZE_QUALITY_FIELDS),
        "predeclaration_sha256": sha256_file(PROJECT_ROOT / PREDECLARATION),
        "causal_amendment_sha256": sha256_file(PROJECT_ROOT / CAUSAL_AMENDMENT),
        "data_gate": {
            "authoritative_inputs": True,
            "authoritative_code": True,
            "coverage_pass": coverage_pass,
            "distinctness_pass": distinctness_pass,
            "control_coverage_pass": control_coverage_pass,
            "annual_cells": len(annual),
            "minimum_annual_both_valid": float(annual["qsize_both_valid"].min()),
            "minimum_ticker_both_valid": float(overall.min()),
            "passed": data_gate_pass,
        },
        "errors": [],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
