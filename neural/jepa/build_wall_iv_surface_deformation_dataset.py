"""Build the outcome-free H-IVSURF1 wall-touch feature dataset.

Only the sealed H-FLOW candidate keys/geometry/F0 controls are reused.  Failed
H-FLOW features, physical labels, option outcomes and 2026 rows are never read.
"""

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

from neural.jepa.build_wall_surface_flow_dataset import (  # noqa: E402
    EXPECTED_INPUT_HASHES,
    EXPECTED_SESSION_COUNT,
    EXPECTED_SESSION_KEY_SHA256,
    apply_native_quote_clock,
    attach_native_quote_index,
    feature_hash,
    filter_manifest,
    read_native_quotes,
    session_key_hash,
    sha256_file,
)
from neural.jepa.iv_surface_deformation_features import (  # noqa: E402
    IV_SURFACE_ALLOWLIST,
    IV_SURFACE_FEATURES,
    attach_iv_surface_features,
    prepare_iv_surface_source,
)
from neural.jepa.surface_flow_features import CONTROL_FEATURES, KEY_COLUMNS  # noqa: E402
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402


START_DATE = "20220801"
END_DATE = "20251231"
TICKERS = ("SPXW", "QQQ", "SPY")
EXPECTED_CANDIDATE_SHA256 = "6d27fdeb44422daa95aa79f777044e68276a2fe374c9bd847cd475d9dccfdb5b"
EXPECTED_CANDIDATE_ROWS = 10683
EXPECTED_CANDIDATE_MANIFEST_SCHEMA = "wall_surface_flow_at_touch_dataset_v1"
EXPECTED_EXACT_INDEX_SHA256 = "7e5475f36d2163e188d721ea2f015c9a636db5bfbfede41dd8d0065a9382100a"
EXPECTED_EXACT_SEAL_SHA256 = "3c267f83e5108c75c9f148624983b11f3f0708fde12cb58a8742278d194a8fc5"
EXPECTED_EXACT_CONTRACTS = 671
EXPECTED_EXACT_ROWS = 32208
EXPECTED_EXACT_SESSIONS = frozenset({("QQQ", "20221230"), ("SPY", "20221230")})
PREDECLARATION = Path("research_papers/JEPA/WALL_IV_SURFACE_DEFORMATION_AT_TOUCH_V1_PREDECLARATION.md")
RUNTIME_LOCK = Path("research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt")
AUTHORITATIVE_CODE = (
    "neural/jepa/build_wall_iv_surface_deformation_dataset.py",
    "neural/jepa/iv_surface_deformation_features.py",
    "research_papers/JEPA/WALL_IV_SURFACE_DEFORMATION_AT_TOUCH_V1_PREDECLARATION.md",
    "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
)

CANDIDATE_METADATA = (
    "ticker", "trade_date", "minute", "decision_dt", "wall_identity", "wall_role",
    "candidate_right", "candidate_wall_strike", "spot", "wall_alias_count",
    "episode_sequence", "episode_start_minute", "episode_id",
)
CANDIDATE_COLUMNS = tuple(dict.fromkeys((*CANDIDATE_METADATA, *CONTROL_FEATURES)))
GREEK_COLUMNS = (
    "symbol", "expiration", "trade_date", "timestamp", "underlying_timestamp",
    "right", "strike", "implied_vol", "iv_error", "bid", "ask", "interval_used",
)
FORBIDDEN_TOKENS = ("label", "outcome", "payoff", "pnl", "future", "exit_", "return_")


def assert_authoritative_code_state() -> tuple[str, dict[str, str]]:
    hashes: dict[str, str] = {}
    for relative in AUTHORITATIVE_CODE:
        subprocess.run(["git", "ls-files", "--error-unmatch", relative], cwd=PROJECT_ROOT,
                       check=True, capture_output=True, text=True)
        dirty = subprocess.run(["git", "status", "--porcelain", "--", relative], cwd=PROJECT_ROOT,
                               check=True, capture_output=True, text=True).stdout.strip()
        if dirty:
            raise AssertionError(f"authoritative H-IVSURF1 build requires committed clean code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    return commit, hashes


def _read_columns(path: str | Path, wanted: tuple[str, ...]) -> pd.DataFrame:
    available = set(pq.ParquetFile(path).schema_arrow.names)
    required = set(wanted).difference({"timestamp", "underlying_timestamp", "interval_used"})
    missing = sorted(required.difference(available))
    if missing:
        raise KeyError(f"{path} missing required columns: {missing}")
    return pd.read_parquet(path, columns=[c for c in wanted if c in available])


def load_sealed_candidates(path: str | Path, manifest_path: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    path, manifest_path = Path(path), Path(manifest_path)
    if sha256_file(path) != EXPECTED_CANDIDATE_SHA256:
        raise AssertionError("candidate dataset differs from the frozen H-FLOW universe")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != EXPECTED_CANDIDATE_MANIFEST_SCHEMA
        or manifest.get("status") != "PASS_DATA_GATE"
        or manifest.get("holdout_2026_used") is not False
        or manifest.get("dataset_sha256") != EXPECTED_CANDIDATE_SHA256
        or int(manifest.get("rows", -1)) != EXPECTED_CANDIDATE_ROWS
        or int(manifest.get("full_session_universe_count", -1)) != EXPECTED_SESSION_COUNT
        or manifest.get("full_session_key_sha256") != EXPECTED_SESSION_KEY_SHA256
    ):
        raise AssertionError("candidate data manifest is not the frozen PASS_DATA_GATE artifact")
    frame = _read_columns(path, CANDIDATE_COLUMNS)
    if len(frame) != EXPECTED_CANDIDATE_ROWS or frame.duplicated(list(KEY_COLUMNS)).any():
        raise AssertionError("candidate cardinality/key uniqueness changed")
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["trade_date"] = frame["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    frame["decision_dt"] = pd.to_datetime(frame["decision_dt"], errors="coerce")
    if frame["decision_dt"].isna().any() or frame["trade_date"].str.startswith("2026").any():
        raise AssertionError("invalid/future candidate clock")
    return frame.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True), manifest


def validate_full_source_inventory(
    sessions: pd.DataFrame, source_hashes_path: str | Path, candidate_manifest: dict[str, Any]
) -> pd.DataFrame:
    """Bind all 2,519 Greek files to the already sealed full source inventory."""
    path = Path(source_hashes_path)
    if sha256_file(path) != str(candidate_manifest.get("source_file_hashes_sha256", "")):
        raise AssertionError("full source inventory differs from candidate manifest")
    inventory = pd.read_csv(path, dtype={"trade_date": str})
    greek = inventory[inventory["source_kind"].eq("greeks")].copy()
    greek["ticker"] = greek["ticker"].astype(str).str.upper()
    greek["trade_date"] = greek["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    if len(greek) != EXPECTED_SESSION_COUNT or greek.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("sealed inventory does not contain one Greek source per session")
    if session_key_hash(greek) != EXPECTED_SESSION_KEY_SHA256:
        raise AssertionError("Greek source session universe changed")
    joined = sessions.merge(
        greek[["ticker", "trade_date", "path", "sha256"]].rename(
            columns={"path": "sealed_greeks_path", "sha256": "sealed_greeks_sha256"}
        ), on=["ticker", "trade_date"], how="left", validate="one_to_one",
    )
    if joined["sealed_greeks_path"].isna().any():
        raise AssertionError("canonical manifest has a session absent from sealed inventory")
    for row in joined.itertuples(index=False):
        if Path(row.greeks_path).resolve() != Path(row.sealed_greeks_path).resolve():
            raise AssertionError("canonical Greek path differs from sealed inventory")
        if sha256_file(row.greeks_path) != str(row.sealed_greeks_sha256):
            raise AssertionError(f"Greek source hash changed: {row.greeks_path}")
    return joined


def load_exact_greek_repairs(index_path: str | Path, seal_path: str | Path) -> tuple[dict[tuple[str, str], pd.DataFrame], dict[str, Any]]:
    index_path, seal_path = Path(index_path), Path(seal_path)
    if sha256_file(index_path) != EXPECTED_EXACT_INDEX_SHA256 or sha256_file(seal_path) != EXPECTED_EXACT_SEAL_SHA256:
        raise AssertionError("exact-Greek repair index/seal hash mismatch")
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    if (
        seal.get("status") != "PASS_EXACT_GREEK_REPAIR_CAPTURE"
        or seal.get("outcome_free") is not True
        or seal.get("holdout_2026_used") is not False
        or int(seal.get("contracts", -1)) != EXPECTED_EXACT_CONTRACTS
        or int(seal.get("rows", seal.get("exact_rows", -1))) != EXPECTED_EXACT_ROWS
    ):
        raise AssertionError("exact-Greek repair is not the frozen outcome-free seal")
    index = pd.read_csv(index_path, dtype={"trade_date": str})
    if len(index) != EXPECTED_EXACT_CONTRACTS or index.duplicated(["ticker", "trade_date", "strike", "right"]).any():
        raise AssertionError("exact-Greek contract index cardinality changed")
    parts: dict[tuple[str, str], list[pd.DataFrame]] = {key: [] for key in EXPECTED_EXACT_SESSIONS}
    rows = 0
    for row in index.itertuples(index=False):
        key = (str(row.ticker).upper(), str(row.trade_date)[:8])
        if key not in parts or sha256_file(row.exact_greeks_path) != str(row.exact_greeks_sha256):
            raise AssertionError("exact-Greek repair path/hash/session mismatch")
        part = _read_columns(row.exact_greeks_path, GREEK_COLUMNS)
        parts[key].append(part)
        rows += len(part)
    if rows != EXPECTED_EXACT_ROWS:
        raise AssertionError("exact-Greek repair row count changed")
    return {key: pd.concat(value, ignore_index=True) for key, value in parts.items()}, {
        "index_sha256": EXPECTED_EXACT_INDEX_SHA256, "seal_sha256": EXPECTED_EXACT_SEAL_SHA256,
        "contracts": len(index), "rows": rows,
        "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
    }


def build_session(record: dict[str, Any], candidates: pd.DataFrame, exact: pd.DataFrame | None) -> tuple[pd.DataFrame, dict[str, Any]]:
    source = _read_columns(record["greeks_path"], GREEK_COLUMNS)
    if pd.isna(record.get("native_quote_path")) is False and record.get("native_quote_path"):
        quotes = read_native_quotes(record["native_quote_path"])
        source = apply_native_quote_clock(source, quotes)
    if exact is not None:
        source = exact
    frozen_keys = source[["expiration", "right", "strike"]].drop_duplicates()
    surface, audit = prepare_iv_surface_source(
        source, expected_ticker=str(record["ticker"]), expected_trade_date=str(record["trade_date"]),
        frozen_contract_keys=frozen_keys,
    )
    result = attach_iv_surface_features(candidates.copy(), surface)
    if len(result) != len(candidates) or result[list(KEY_COLUMNS)].duplicated().any():
        raise AssertionError("surface attachment changed candidate cardinality")
    return result, audit


def profile_dataset(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = frame.copy()
    work["year"] = work["trade_date"].str[:4]
    work["month"] = work["trade_date"].str[:6]
    coverage = work.groupby(["ticker", "year", "month"], as_index=False).agg(
        rows=("minute", "size"), surface_both_valid=("surface_both_valid", "mean"),
        surface_call_valid=("surface_call_valid", "mean"), surface_put_valid=("surface_put_valid", "mean"),
    )
    records = []
    for (ticker, year), part in work.groupby(["ticker", "year"], sort=True):
        for column in IV_SURFACE_ALLOWLIST:
            values = pd.to_numeric(part[column], errors="coerce")
            finite = values[np.isfinite(values)]
            records.append({"ticker": ticker, "year": year, "feature": column, "rows": len(part),
                            "finite": len(finite), "missing_rate": float(1-len(finite)/len(part)),
                            "distinct_finite": int(finite.nunique()), "minimum": float(finite.min()) if len(finite) else np.nan,
                            "maximum": float(finite.max()) if len(finite) else np.nan})
    return coverage, pd.DataFrame(records)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", required=True)
    p.add_argument("--candidate-manifest", required=True)
    p.add_argument("--source-hashes", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--native-quote-index", required=True)
    p.add_argument("--native-quote-seal", required=True)
    p.add_argument("--exact-greek-index", required=True)
    p.add_argument("--exact-greek-seal", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--workers", type=int, default=16)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    git_commit, code_hashes = assert_authoritative_code_state()
    runtime = assert_runtime_lock(PROJECT_ROOT / RUNTIME_LOCK)
    if sha256_file(args.manifest) != EXPECTED_INPUT_HASHES["manifest"]:
        raise AssertionError("canonical source manifest hash mismatch")
    candidates, candidate_manifest = load_sealed_candidates(args.candidates, args.candidate_manifest)
    sessions = filter_manifest(pd.read_csv(args.manifest), start_date=START_DATE, end_date=END_DATE)
    if len(sessions) != EXPECTED_SESSION_COUNT or session_key_hash(sessions) != EXPECTED_SESSION_KEY_SHA256:
        raise AssertionError("canonical 2,519-session universe changed")
    sessions = validate_full_source_inventory(sessions, args.source_hashes, candidate_manifest)
    sessions, native_provenance = attach_native_quote_index(sessions, args.native_quote_index, args.native_quote_seal)
    repairs, repair_provenance = load_exact_greek_repairs(args.exact_greek_index, args.exact_greek_seal)
    needed = sessions.merge(candidates[["ticker", "trade_date"]].drop_duplicates(), on=["ticker", "trade_date"], how="inner")
    outputs, audits, errors = [], [], []
    with ProcessPoolExecutor(max_workers=max(1, min(args.workers, 16))) as pool:
        futures = {}
        for row in needed.to_dict("records"):
            key = (str(row["ticker"]), str(row["trade_date"]))
            part = candidates[(candidates.ticker == key[0]) & (candidates.trade_date == key[1])]
            futures[pool.submit(build_session, row, part, repairs.get(key))] = key
        for future in as_completed(futures):
            key = futures[future]
            try:
                result, audit = future.result()
                outputs.append(result)
                audits.append({"ticker": key[0], "trade_date": key[1], **audit})
            except Exception as exc:
                errors.append({"ticker": key[0], "trade_date": key[1], "error": f"{type(exc).__name__}: {exc}"})
    if errors:
        raise AssertionError(f"H-IVSURF1 build failed in {len(errors)} sessions: {errors[:5]}")
    dataset = pd.concat(outputs, ignore_index=True).sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)
    if len(dataset) != EXPECTED_CANDIDATE_ROWS or dataset[list(KEY_COLUMNS)].duplicated().any():
        raise AssertionError("final dataset differs from frozen candidate universe")
    coverage, profile = profile_dataset(dataset)
    annual = coverage.groupby(["ticker", "year"], as_index=False).agg(surface_both_valid=("surface_both_valid", "mean"))
    overall = dataset.groupby("ticker")["surface_both_valid"].mean()
    coverage_pass = bool(annual.surface_both_valid.ge(.70).all() and overall.ge(.80).all())
    control_coverage_pass = bool(
        not dataset[list(CONTROL_FEATURES)].isna().any().any()
        and np.isfinite(
            dataset[list(CONTROL_FEATURES)].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        ).all()
    )
    numeric_profile = profile[profile.feature.isin(IV_SURFACE_FEATURES)]
    distinctness_pass = bool((numeric_profile.distinct_finite >= 2).all())
    authoritative_inputs = True
    authoritative_code = True
    data_gate_pass = bool(
        authoritative_inputs
        and authoritative_code
        and coverage_pass
        and distinctness_pass
        and control_coverage_pass
    )
    bundle_provenance = candidate_manifest.get("exact_greek_repair_provenance")
    if (
        not isinstance(bundle_provenance, dict)
        or bundle_provenance.get("status") != "PASS_EXACT_GREEK_REPAIR_ARTIFACTS"
        or bundle_provenance.get("frozen_hashes_match") is not True
        or bundle_provenance.get("historical_provenance")
        != "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION"
    ):
        raise AssertionError("candidate manifest exact-Greek repair bundle is incomplete")
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    dataset_path = output / "wall_iv_surface_deformation_at_touch.parquet"
    dataset.to_parquet(dataset_path, index=False)
    pd.DataFrame(audits).to_csv(output / "session_audit.csv", index=False)
    coverage.to_csv(output / "coverage_by_month.csv", index=False)
    profile.to_csv(output / "feature_profile.csv", index=False)
    schema = {"columns": [{"name": c, "dtype": str(dataset[c].dtype)} for c in dataset.columns]}
    (output / "schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    manifest = {
        "schema": "wall_iv_surface_deformation_at_touch_dataset_v1", "status": "PASS_DATA_GATE" if data_gate_pass else "REJECTED_DATA_GATE",
        "outcome_free": True, "holdout_2026_used": False, "production_modified": False,
        "date_range": [START_DATE, END_DATE], "rows": len(dataset), "columns": len(dataset.columns),
        "dataset": str(dataset_path), "dataset_sha256": sha256_file(dataset_path),
        "candidate_sha256": EXPECTED_CANDIDATE_SHA256, "candidate_rows": EXPECTED_CANDIDATE_ROWS,
        "canonical_manifest_sha256": EXPECTED_INPUT_HASHES["manifest"],
        "source_file_hashes_sha256": sha256_file(args.source_hashes),
        "full_session_universe_count": len(sessions), "full_session_key_sha256": session_key_hash(sessions),
        "native_quote_provenance": native_provenance,
        "exact_greek_repair_provenance": bundle_provenance,
        "exact_greek_capture_provenance": repair_provenance,
        "control_feature_hash": feature_hash(CONTROL_FEATURES), "iv_surface_feature_hash": feature_hash(IV_SURFACE_ALLOWLIST),
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "git_commit": git_commit, "code_hashes": code_hashes,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "data_gate": {
            "authoritative_inputs": authoritative_inputs,
            "authoritative_code": authoritative_code,
            "coverage_pass": coverage_pass,
            "distinctness_pass": distinctness_pass,
            "control_coverage_pass": control_coverage_pass,
            "annual_cells": len(annual),
            "minimum_annual_both_valid": float(annual.surface_both_valid.min()),
            "minimum_ticker_both_valid": float(overall.min()),
            "passed": data_gate_pass,
        },
        "errors": [],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
