"""Build the outcome-free H-QDYN1 wall-touch feature dataset.

This module intentionally contains no label, future-price or payoff code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.build_wall_quote_tick_dynamics_sidecar import (  # noqa: E402
    EXPECTED_CANDIDATES,
    EXPECTED_CANDIDATE_SHA256,
    EXPECTED_WALL_STATE_SHA256,
    event_id,
    sha256_file,
)
from neural.jepa.build_wall_surface_flow_dataset import feature_hash  # noqa: E402
from neural.jepa.surface_flow_features import CONTROL_FEATURES, KEY_COLUMNS  # noqa: E402
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402

PREDECLARATION = "research_papers/JEPA/WALL_QUOTE_TICK_DYNAMICS_AT_TOUCH_V1_PREDECLARATION.md"
CAUSAL_AMENDMENT = (
    "research_papers/JEPA/"
    "WALL_QUOTE_TICK_DYNAMICS_AT_TOUCH_V1R1_CAUSAL_AMENDMENT.md"
)
CAPTURE_CLARIFICATION = (
    "research_papers/JEPA/"
    "WALL_QUOTE_TICK_DYNAMICS_AT_TOUCH_V1R1R1_CAPTURE_CLARIFICATION.md"
)
RUNTIME_LOCK = "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
AUTHORITATIVE_CODE = (
    "neural/jepa/build_wall_quote_tick_dynamics_dataset.py",
    "neural/jepa/build_wall_qdyn_subscription_allowlist.py",
    "neural/jepa/build_wall_quote_tick_dynamics_sidecar.py",
    "neural/jepa/build_wall_surface_flow_dataset.py",
    "neural/jepa/surface_flow_features.py",
    "neural/jepa/wall_surface_flow_environment.py",
    PREDECLARATION,
    CAUSAL_AMENDMENT,
    CAPTURE_CLARIFICATION,
    RUNTIME_LOCK,
)
RIGHTS = ("CALL", "PUT")
MIN_DEDUP_ROWS = 20
MIN_UNAMBIGUOUS_PAIRS = 5


def _names() -> tuple[str, ...]:
    measurements = (
        "log_update_count",
        "log_unique_timestamp_count",
        "timestamp_collision_fraction",
        "update_acceleration_10s_vs_prior20s",
        "unambiguous_state_change_fraction",
        "unambiguous_price_change_fraction",
        "unambiguous_size_only_change_fraction",
        "log_bid_size_increase",
        "log_bid_size_decrease",
        "log_ask_size_increase",
        "log_ask_size_decrease",
        "bid_exchange_change_fraction",
        "ask_exchange_change_fraction",
        "log_last_update_age_ms",
    )
    return tuple(f"qdyn_{right.lower()}_{name}" for right in RIGHTS for name in measurements)


QDYN_FEATURES = _names()
QDYN_QUALITY_FIELDS = (
    *(f"qdyn_{right.lower()}_{name}" for right in RIGHTS for name in (
        "raw_rows", "dedup_rows", "exact_duplicate_rows", "collision_rows",
        "unambiguous_pair_count", "valid",
    )),
    "qdyn_both_valid",
    "causal_subscription_eligible",
)


def _sha256_text(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def committed_code_state() -> tuple[str, dict[str, str]]:
    hashes: dict[str, str] = {}
    for relative in AUTHORITATIVE_CODE:
        subprocess.run(["git", "ls-files", "--error-unmatch", relative], cwd=PROJECT_ROOT,
                       check=True, capture_output=True, text=True)
        dirty = subprocess.run(["git", "status", "--porcelain", "--", relative],
                               cwd=PROJECT_ROOT, check=True, capture_output=True,
                               text=True).stdout.strip()
        if dirty:
            raise AssertionError(f"authoritative H-QDYN1 build requires clean code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    return commit, hashes


def load_candidates(path: str | Path, manifest_path: str | Path) -> pd.DataFrame:
    if sha256_file(path) != EXPECTED_CANDIDATE_SHA256:
        raise AssertionError("H-QDYN1 candidate dataset hash mismatch")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if (manifest.get("status") != "PASS_DATA_GATE"
            or manifest.get("dataset_sha256") != EXPECTED_CANDIDATE_SHA256
            or manifest.get("holdout_2026_used") is not False
            or int(manifest.get("rows", -1)) != EXPECTED_CANDIDATES):
        raise AssertionError("H-QDYN1 candidate manifest is not frozen")
    required = [*KEY_COLUMNS, "decision_dt", "candidate_wall_strike", *CONTROL_FEATURES]
    names = set(pq.ParquetFile(path).schema_arrow.names)
    if set(required).difference(names):
        raise KeyError(f"candidate dataset missing fields: {sorted(set(required).difference(names))}")
    frame = pd.read_parquet(path, columns=list(dict.fromkeys(required)))
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["trade_date"] = frame["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    frame["decision_dt"] = pd.to_datetime(frame["decision_dt"], errors="coerce")
    if (len(frame) != EXPECTED_CANDIDATES or frame.duplicated(list(KEY_COLUMNS)).any()
            or frame["decision_dt"].isna().any() or frame["trade_date"].ge("20260101").any()
            or not frame["decision_dt"].dt.strftime("%Y%m%d").eq(frame["trade_date"]).all()
            or frame["decision_dt"].dt.second.ne(0).any()
            or frame["decision_dt"].dt.microsecond.ne(0).any()):
        raise AssertionError("H-QDYN1 candidate universe/clock changed")
    frame["event_id"] = [event_id(row) for row in frame.to_dict("records")]
    if frame["event_id"].duplicated().any():
        raise AssertionError("H-QDYN1 event-id collision")
    controls = frame[list(CONTROL_FEATURES)].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(controls.to_numpy(dtype=float)).all():
        raise AssertionError("H-QDYN1 F0 controls are not finite")
    return frame.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)


def load_subscription_proof(proof_path: str | Path, proof_manifest_path: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load a frozen t-5 listing proof; geometry alone is never eligibility."""
    proof_manifest = json.loads(Path(proof_manifest_path).read_text(encoding="utf-8"))
    if (proof_manifest.get("status") != "PASS_SUBSCRIPTION_ALLOWLIST_V1R1R1"
            or proof_manifest.get("outcome_free") is not True
            or proof_manifest.get("holdout_2026_used") is not False
            or proof_manifest.get("candidate_sha256") != EXPECTED_CANDIDATE_SHA256
            or proof_manifest.get("wall_state_sha256") != EXPECTED_WALL_STATE_SHA256
            or int(proof_manifest.get("candidates", -1)) != EXPECTED_CANDIDATES
            or proof_manifest.get("proof_sha256") != sha256_file(proof_path)
            or proof_manifest.get("errors") != []):
        raise AssertionError("H-QDYN1 subscription-listing proof contract mismatch")
    proof = pd.read_parquet(proof_path)
    required = {"event_id", "ticker", "trade_date", "wall_proximity_eligible_v1",
                "exact_call_listed_tminus5m", "exact_put_listed_tminus5m",
                "causal_subscription_eligible_v1r1"}
    if required.difference(proof.columns):
        raise KeyError(f"subscription proof missing: {sorted(required.difference(proof.columns))}")
    booleans = ("wall_proximity_eligible_v1", "exact_call_listed_tminus5m",
                "exact_put_listed_tminus5m", "causal_subscription_eligible_v1r1")
    for column in booleans:
        if not pd.api.types.is_bool_dtype(proof[column]) or proof[column].isna().any():
            raise AssertionError(f"subscription proof has non-boolean {column}")
    derived = (proof["wall_proximity_eligible_v1"] & proof["exact_call_listed_tminus5m"]
               & proof["exact_put_listed_tminus5m"])
    eligible_ids = proof.loc[derived, "event_id"].astype(str).tolist()
    if (len(proof) != EXPECTED_CANDIDATES or proof["event_id"].duplicated().any()
            or not proof["causal_subscription_eligible_v1r1"].eq(derived).all()
            or int(proof_manifest.get("eligible_events", -1)) != len(eligible_ids)
            or proof_manifest.get("eligible_event_id_sha256") != _sha256_text(eligible_ids)):
        raise AssertionError("H-QDYN1 subscription proof universe/derivation mismatch")
    return proof, proof_manifest


def load_sidecar(index_path: str | Path, seal_path: str | Path, proof: pd.DataFrame,
                 proof_manifest: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    seal = json.loads(Path(seal_path).read_text(encoding="utf-8"))
    if (seal.get("status") != "PASS_QDYN_CAPTURE" or seal.get("outcome_free") is not True
            or seal.get("holdout_2026_used") is not False
            or seal.get("candidate_dataset_sha256") != EXPECTED_CANDIDATE_SHA256
            or seal.get("wall_state_sha256") != EXPECTED_WALL_STATE_SHA256
            or int(seal.get("eligible_events", -1)) != int(proof_manifest["eligible_events"])
            or int(seal.get("ineligible_events", -1)) != EXPECTED_CANDIDATES - int(proof_manifest["eligible_events"])
            or seal.get("eligible_event_id_sha256") != proof_manifest["eligible_event_id_sha256"]
            or seal.get("subscription_proof_sha256") != proof_manifest["proof_sha256"]
            or seal.get("index_sha256") != sha256_file(index_path)
            or seal.get("historical_provenance") != "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION"
            or seal.get("errors") != []):
        raise AssertionError("H-QDYN1 sidecar seal contract mismatch")
    index = pd.read_csv(index_path, dtype={"trade_date": str})
    required_index = {"event_id", "ticker", "trade_date", "decision_dt", "wall_strike",
                      "raw_path", "raw_sha256", "parquet_path", "parquet_sha256",
                      "manifest_path", "manifest_sha256", "rows", "call_rows", "put_rows"}
    if required_index.difference(index.columns):
        raise KeyError(f"H-QDYN1 index missing: {sorted(required_index.difference(index.columns))}")
    expected_eligible = int(proof_manifest["eligible_events"])
    expected_hash = str(proof_manifest["eligible_event_id_sha256"])
    if (len(index) != expected_eligible or index["event_id"].duplicated().any()
            or _sha256_text(index["event_id"].astype(str).tolist()) != expected_hash):
        raise AssertionError("H-QDYN1 index event universe changed")
    return index, proof, seal


def _valid_rows(frame: pd.DataFrame) -> pd.Series:
    numeric = frame[["bid", "ask", "bid_size", "ask_size"]].apply(pd.to_numeric, errors="coerce")
    exchange_values = frame[["bid_exchange", "ask_exchange"]].apply(
        pd.to_numeric, errors="coerce"
    )
    exchanges = np.isfinite(exchange_values).all(axis=1)
    return (np.isfinite(numeric).all(axis=1) & numeric["bid"].gt(0)
            & numeric["ask"].ge(numeric["bid"]) & numeric["bid_size"].ge(0)
            & numeric["ask_size"].ge(0) & exchanges)


def right_features(rows: pd.DataFrame, decision_dt: pd.Timestamp, right: str) -> dict[str, Any]:
    prefix = f"qdyn_{right.lower()}"
    result: dict[str, Any] = {name: np.nan for name in QDYN_FEATURES if name.startswith(prefix)}
    part = rows[rows["right"].astype(str).str.upper().eq(right)].copy()
    part["timestamp"] = pd.to_datetime(part["timestamp"], errors="coerce")
    part["contract_ordinal"] = pd.to_numeric(part["contract_ordinal"], errors="coerce")
    start, split, end = decision_dt - pd.Timedelta(seconds=32), decision_dt - pd.Timedelta(seconds=12), decision_dt - pd.Timedelta(seconds=2)
    if (part["timestamp"].isna().any() or part["contract_ordinal"].isna().any()
            or len(part) and (part["timestamp"].lt(start).any() or part["timestamp"].ge(end).any())
            or part["contract_ordinal"].duplicated().any()):
        raise AssertionError("H-QDYN1 ticks violate completed guarded window/ordinal")
    part = part.sort_values("contract_ordinal", kind="stable").reset_index(drop=True)
    raw_rows = len(part)
    dedup_columns = [
        "timestamp", "bid", "ask", "bid_size", "ask_size", "bid_exchange",
        "ask_exchange", "bid_condition", "ask_condition",
    ]
    missing_state = sorted(set(dedup_columns).difference(part.columns))
    if missing_state:
        raise KeyError(f"H-QDYN1 tick state missing: {missing_state}")
    dedup = part.drop_duplicates(dedup_columns, keep="first")
    timestamp_counts = part["timestamp"].value_counts(dropna=False)
    collision_rows = int(part["timestamp"].map(timestamp_counts).gt(1).sum())
    dedup_timestamp_counts = dedup["timestamp"].value_counts(dropna=False)
    dedup_collision_rows = int(
        dedup["timestamp"].map(dedup_timestamp_counts).gt(1).sum()
    )
    quality = {
        f"{prefix}_raw_rows": raw_rows,
        f"{prefix}_dedup_rows": len(dedup),
        f"{prefix}_exact_duplicate_rows": raw_rows - len(dedup),
        f"{prefix}_collision_rows": collision_rows,
    }
    pairs: list[tuple[pd.Series, pd.Series]] = []
    valid = _valid_rows(part)
    for pos in range(1, len(part)):
        previous, current = part.iloc[pos - 1], part.iloc[pos]
        if (timestamp_counts[previous["timestamp"]] == 1
                and timestamp_counts[current["timestamp"]] == 1
                and current["timestamp"] > previous["timestamp"]
                and bool(valid.iloc[pos - 1]) and bool(valid.iloc[pos])):
            pairs.append((previous, current))
    quality[f"{prefix}_unambiguous_pair_count"] = len(pairs)
    is_valid = len(dedup) >= MIN_DEDUP_ROWS and len(pairs) >= MIN_UNAMBIGUOUS_PAIRS
    quality[f"{prefix}_valid"] = is_valid
    if not is_valid:
        return {**result, **quality}
    changes = []
    bid_inc = bid_dec = ask_inc = ask_dec = bid_ex = ask_ex = 0
    price_changes = size_only_changes = 0
    for previous, current in pairs:
        price_changed = previous["bid"] != current["bid"] or previous["ask"] != current["ask"]
        size_changed = previous["bid_size"] != current["bid_size"] or previous["ask_size"] != current["ask_size"]
        state_changed = price_changed or size_changed or previous["bid_exchange"] != current["bid_exchange"] or previous["ask_exchange"] != current["ask_exchange"]
        changes.append(state_changed)
        price_changes += int(price_changed)
        exchange_changed = (
            previous["bid_exchange"] != current["bid_exchange"]
            or previous["ask_exchange"] != current["ask_exchange"]
        )
        size_only_changes += int(
            size_changed and not price_changed and not exchange_changed
        )
        bid_ex += int(previous["bid_exchange"] != current["bid_exchange"])
        ask_ex += int(previous["ask_exchange"] != current["ask_exchange"])
        if previous["bid"] == current["bid"] and previous["bid_exchange"] == current["bid_exchange"]:
            bid_inc += int(current["bid_size"] > previous["bid_size"])
            bid_dec += int(current["bid_size"] < previous["bid_size"])
        if previous["ask"] == current["ask"] and previous["ask_exchange"] == current["ask_exchange"]:
            ask_inc += int(current["ask_size"] > previous["ask_size"])
            ask_dec += int(current["ask_size"] < previous["ask_size"])
    last10 = int(dedup["timestamp"].ge(split).sum())
    prior20 = int(dedup["timestamp"].lt(split).sum())
    denominator = len(pairs)
    result.update({
        f"{prefix}_log_update_count": float(np.log1p(len(dedup))),
        f"{prefix}_log_unique_timestamp_count": float(np.log1p(dedup["timestamp"].nunique())),
        f"{prefix}_timestamp_collision_fraction": float(dedup_collision_rows / len(dedup)),
        f"{prefix}_update_acceleration_10s_vs_prior20s": float(np.log((last10 + 1.0) / (prior20 / 2.0 + 1.0))),
        f"{prefix}_unambiguous_state_change_fraction": float(sum(changes) / denominator),
        f"{prefix}_unambiguous_price_change_fraction": float(price_changes / denominator),
        f"{prefix}_unambiguous_size_only_change_fraction": float(size_only_changes / denominator),
        f"{prefix}_log_bid_size_increase": float(np.log1p(bid_inc)),
        f"{prefix}_log_bid_size_decrease": float(np.log1p(bid_dec)),
        f"{prefix}_log_ask_size_increase": float(np.log1p(ask_inc)),
        f"{prefix}_log_ask_size_decrease": float(np.log1p(ask_dec)),
        f"{prefix}_bid_exchange_change_fraction": float(bid_ex / denominator),
        f"{prefix}_ask_exchange_change_fraction": float(ask_ex / denominator),
        f"{prefix}_log_last_update_age_ms": float(np.log1p((end - dedup["timestamp"].max()).total_seconds() * 1000.0)),
    })
    return {**result, **quality}


def build_event(row: dict[str, Any], candidate: pd.Series, seal: dict[str, Any]) -> dict[str, Any]:
    for path_field, hash_field in (("raw_path", "raw_sha256"), ("parquet_path", "parquet_sha256"), ("manifest_path", "manifest_sha256")):
        if sha256_file(row[path_field]) != str(row[hash_field]):
            raise AssertionError(f"H-QDYN1 source hash mismatch: {path_field}")
    manifest = json.loads(Path(row["manifest_path"]).read_text(encoding="utf-8"))
    if (manifest.get("status") != "PASS_QDYN_EVENT" or manifest.get("event_id") != row["event_id"]
            or manifest.get("outcome_free") is not True or manifest.get("holdout_2026_used") is not False
            or manifest.get("raw_sha256") != row["raw_sha256"]
            or manifest.get("parquet_sha256") != row["parquet_sha256"]
            or int(manifest.get("rows", -1)) != int(row["rows"])
            or manifest.get("ticker") != candidate["ticker"]
            or manifest.get("trade_date") != candidate["trade_date"]
            or pd.Timestamp(manifest.get("decision_dt")) != pd.Timestamp(candidate["decision_dt"])
            or float(manifest.get("wall_strike", np.nan)) != float(candidate["candidate_wall_strike"])
            or manifest.get("code_hashes") != seal.get("code_hashes")
            or manifest.get("runtime_lock_sha256") != seal.get("runtime_lock_sha256")
            or manifest.get("runtime_environment_sha256") != seal.get("runtime_environment_sha256")
            or manifest.get("terminal_process_evidence") != seal.get("terminal_process_evidence")):
        raise AssertionError("H-QDYN1 event manifest mismatch")
    ticks = pd.read_parquet(row["parquet_path"])
    decision = pd.Timestamp(candidate["decision_dt"])
    if (len(ticks) != int(row["rows"]) or set(ticks["event_id"].astype(str).unique()) != {row["event_id"]}
            or set(ticks["ticker"].astype(str).unique()) != {candidate["ticker"]}
            or set(pd.to_numeric(ticks["wall_strike"], errors="coerce").unique()) != {float(candidate["candidate_wall_strike"])}):
        raise AssertionError("H-QDYN1 parquet/candidate identity mismatch")
    result: dict[str, Any] = {}
    for right in RIGHTS:
        result.update(right_features(ticks, decision, right))
    result["qdyn_both_valid"] = bool(result["qdyn_call_valid"] and result["qdyn_put_valid"])
    return result


def index_events(index: pd.DataFrame) -> pd.DataFrame:
    """Index sealed event sources without dropping the identity being audited."""
    indexed = index.set_index("event_id", drop=False)
    if not indexed.index.is_unique:
        raise AssertionError("H-QDYN1 index has duplicate event_id")
    return indexed


def profile(dataset: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = dataset.assign(year=dataset["trade_date"].str[:4], month=dataset["trade_date"].str[:6])
    coverage = work.groupby(["ticker", "year", "month"], as_index=False).agg(
        rows=("event_id", "size"), eligible=("causal_subscription_eligible", "mean"),
        both_valid=("qdyn_both_valid", "mean"))
    rows = []
    eligible = work[work["causal_subscription_eligible"]]
    for (ticker, year), part in eligible.groupby(["ticker", "year"], sort=True):
        for name in QDYN_FEATURES:
            values = pd.to_numeric(part[name], errors="coerce")
            finite = values[np.isfinite(values)]
            rows.append({"ticker": ticker, "year": year, "feature": name, "rows": len(part),
                         "finite": len(finite), "distinct_finite": int(finite.nunique()),
                         "missing_rate": float(1 - len(finite) / len(part)),
                         "minimum": float(finite.min()) if len(finite) else None,
                         "maximum": float(finite.max()) if len(finite) else None})
    return coverage, pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--candidate-manifest", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--seal", required=True)
    parser.add_argument("--subscription-proof", required=True)
    parser.add_argument("--subscription-proof-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    commit, code_hashes = committed_code_state()
    runtime = assert_runtime_lock(PROJECT_ROOT / RUNTIME_LOCK)
    candidates = load_candidates(args.candidates, args.candidate_manifest)
    proof, proof_manifest = load_subscription_proof(
        args.subscription_proof, args.subscription_proof_manifest)
    index, eligibility, seal = load_sidecar(
        args.index, args.seal, proof, proof_manifest)
    eligibility = eligibility[["event_id", "causal_subscription_eligible_v1r1"]].rename(
        columns={"causal_subscription_eligible_v1r1": "causal_subscription_eligible"})
    dataset = candidates.merge(eligibility, on="event_id", how="left", validate="one_to_one")
    if dataset["causal_subscription_eligible"].isna().any():
        raise AssertionError("H-QDYN1 eligibility failed exact candidate join")
    index_by_id = index_events(index)
    feature_rows = []
    for _, candidate in dataset.iterrows():
        if candidate["causal_subscription_eligible"]:
            feature_rows.append({"event_id": candidate["event_id"], **build_event(
                index_by_id.loc[candidate["event_id"]].to_dict(), candidate, seal)})
        else:
            feature_rows.append({"event_id": candidate["event_id"],
                                 **{name: np.nan for name in QDYN_FEATURES},
                                 **{name: (False if name.endswith("valid") else 0) for name in QDYN_QUALITY_FIELDS if name != "causal_subscription_eligible"}})
    dataset = dataset.merge(pd.DataFrame(feature_rows), on="event_id", how="left", validate="one_to_one")
    if (len(dataset) != EXPECTED_CANDIDATES or dataset.duplicated(list(KEY_COLUMNS)).any()
            or int(dataset["causal_subscription_eligible"].sum()) != int(proof_manifest["eligible_events"])):
        raise AssertionError("H-QDYN1 final universe changed")
    ineligible = ~dataset["causal_subscription_eligible"]
    if (dataset.loc[ineligible, list(QDYN_FEATURES)].notna().any().any()
            or dataset.loc[ineligible, "qdyn_both_valid"].any()):
        raise AssertionError("ineligible event received H-QDYN1 measurements")
    coverage, feature_profile = profile(dataset)
    annual = dataset.assign(year=dataset["trade_date"].str[:4]).groupby(["ticker", "year"], as_index=False).agg(
        both_valid=("qdyn_both_valid", "mean"))
    ticker_valid = dataset.groupby("ticker")["qdyn_both_valid"].mean()
    coverage_pass = bool(annual["both_valid"].ge(.80).all() and ticker_valid.ge(.85).all())
    distinctness_pass = bool(feature_profile["distinct_finite"].ge(2).all())
    data_gate_pass = coverage_pass and distinctness_pass
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=False)
    dataset_path = out / "wall_quote_tick_dynamics_at_touch.parquet"
    dataset.to_parquet(dataset_path, index=False)
    coverage.to_csv(out / "coverage_by_month.csv", index=False)
    feature_profile.to_csv(out / "feature_profile.csv", index=False)
    source_inventory = index[["event_id", "ticker", "trade_date", "raw_path", "raw_sha256", "parquet_path", "parquet_sha256", "manifest_path", "manifest_sha256", "rows"]]
    source_inventory.to_csv(out / "source_hashes.csv", index=False)
    schema = {"columns": [{"name": name, "dtype": str(dataset[name].dtype)} for name in dataset]}
    (out / "schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    manifest = {
        "schema": "wall_quote_tick_dynamics_at_touch_dataset_v1r1r1",
        "status": "PASS_DATA_GATE" if data_gate_pass else "REJECTED_DATA_GATE",
        "outcome_free": True, "holdout_2026_used": False, "production_modified": False,
        "git_commit": commit, "code_hashes": code_hashes,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "rows": len(dataset), "columns": len(dataset.columns),
        "dataset": str(dataset_path), "dataset_sha256": sha256_file(dataset_path),
        "candidate_sha256": EXPECTED_CANDIDATE_SHA256,
        "sidecar_index_sha256": sha256_file(args.index), "sidecar_seal_sha256": sha256_file(args.seal),
        "subscription_proof_sha256": sha256_file(args.subscription_proof),
        "subscription_proof_manifest_sha256": sha256_file(args.subscription_proof_manifest),
        "eligible_event_id_sha256": proof_manifest["eligible_event_id_sha256"],
        "eligible_events": int(proof_manifest["eligible_events"]),
        "historical_provenance": seal["historical_provenance"], "live_parity": "BLOCKED",
        "control_feature_hash": feature_hash(CONTROL_FEATURES),
        "qdyn_feature_hash": feature_hash(QDYN_FEATURES),
        "qdyn_quality_hash": feature_hash(QDYN_QUALITY_FIELDS),
        "predeclaration_sha256": sha256_file(PROJECT_ROOT / PREDECLARATION),
        "causal_amendment_sha256": sha256_file(PROJECT_ROOT / CAUSAL_AMENDMENT),
        "capture_clarification_sha256": sha256_file(
            PROJECT_ROOT / CAPTURE_CLARIFICATION
        ),
        "source_inventory_sha256": sha256_file(out / "source_hashes.csv"),
        "data_gate": {"coverage_pass": coverage_pass, "distinctness_pass": distinctness_pass,
                      "minimum_annual_both_valid": float(annual["both_valid"].min()),
                      "minimum_ticker_both_valid": float(ticker_valid.min()), "passed": data_gate_pass},
        "errors": [],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
