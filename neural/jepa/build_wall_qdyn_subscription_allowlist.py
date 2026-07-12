"""Build the outcome-free exact t-5m subscription proof for H-QDYN1R1."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.build_wall_native_quote_sidecar import sha256_file  # noqa: E402
from neural.jepa.build_wall_quote_size_pressure_dataset import (  # noqa: E402
    load_combined_quote_index,
)
from neural.jepa.build_wall_quote_tick_dynamics_sidecar import (  # noqa: E402
    EXPECTED_CANDIDATES,
    EXPECTED_CANDIDATE_SHA256,
    EXPECTED_WALL_STATE_SHA256,
    event_id,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402

AMENDMENT = (
    "research_papers/JEPA/"
    "WALL_QUOTE_TICK_DYNAMICS_AT_TOUCH_V1R1_CAUSAL_AMENDMENT.md"
)
PREDECLARATION = (
    "research_papers/JEPA/WALL_QUOTE_TICK_DYNAMICS_AT_TOUCH_V1_PREDECLARATION.md"
)
RUNTIME_LOCK = "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
CODE_CLOSURE = (
    "neural/jepa/build_wall_qdyn_subscription_allowlist.py",
    "neural/jepa/build_wall_quote_tick_dynamics_sidecar.py",
    "neural/jepa/build_wall_quote_size_pressure_dataset.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    "neural/jepa/build_wall_quote_size_complement_sidecar.py",
    "neural/jepa/build_wall_surface_flow_dataset.py",
    "neural/jepa/wall_surface_flow_environment.py",
    PREDECLARATION,
    AMENDMENT,
    RUNTIME_LOCK,
)
WALL_COLUMNS = (
    "wall_call_gamma_strike",
    "wall_put_gamma_strike",
    "wall_call_delta_strike",
    "wall_put_delta_strike",
)
QUOTE_COLUMNS = ("symbol", "expiration", "timestamp", "strike", "right")


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def line_hash(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def committed_code_state() -> tuple[str, dict[str, str]]:
    hashes: dict[str, str] = {}
    for relative in CODE_CLOSURE:
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
            raise AssertionError(f"H-QDYN1R1 allowlist requires clean code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, hashes


def load_candidate_proximity(
    candidate_path: str | Path, wall_state_path: str | Path
) -> pd.DataFrame:
    if sha256_file(candidate_path) != EXPECTED_CANDIDATE_SHA256:
        raise AssertionError("H-QDYN1R1 candidate hash mismatch")
    if sha256_file(wall_state_path) != EXPECTED_WALL_STATE_SHA256:
        raise AssertionError("H-QDYN1R1 wall-state hash mismatch")
    columns = ["ticker", "trade_date", "decision_dt", "candidate_wall_strike"]
    frame = pd.read_parquet(candidate_path, columns=columns)
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["trade_date"] = (
        frame["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    )
    frame["decision_dt"] = pd.to_datetime(frame["decision_dt"], errors="coerce")
    frame["candidate_wall_strike"] = pd.to_numeric(
        frame["candidate_wall_strike"], errors="coerce"
    )
    keys = ["ticker", "trade_date", "decision_dt", "candidate_wall_strike"]
    if (
        len(frame) != EXPECTED_CANDIDATES
        or frame.duplicated(keys).any()
        or frame["decision_dt"].isna().any()
        or frame["trade_date"].str.startswith("2026").any()
        or not frame["ticker"].isin(["QQQ", "SPXW", "SPY"]).all()
        or not np.isfinite(frame["candidate_wall_strike"]).all()
        or frame["candidate_wall_strike"].le(0).any()
        or not frame["decision_dt"].dt.strftime("%Y%m%d").eq(frame["trade_date"]).all()
    ):
        raise AssertionError("H-QDYN1R1 candidate universe changed")
    frame["event_id"] = [event_id(row) for row in frame.to_dict("records")]
    if frame["event_id"].duplicated().any():
        raise AssertionError("H-QDYN1R1 event-id collision")

    walls = pd.read_parquet(
        wall_state_path,
        columns=["ticker", "trade_date", "dt", "spot", *WALL_COLUMNS],
    )
    walls["ticker"] = walls["ticker"].astype(str).str.upper()
    walls["trade_date"] = (
        walls["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    )
    walls["decision_dt"] = pd.to_datetime(walls.pop("dt"), errors="coerce") + pd.Timedelta(
        minutes=5
    )
    walls = walls.rename(columns={"spot": "subscription_spot_tminus5m"})
    frame = frame.merge(
        walls,
        on=["ticker", "trade_date", "decision_dt"],
        how="left",
        validate="many_to_one",
    )
    distances = (
        np.abs(
            frame[list(WALL_COLUMNS)].to_numpy(dtype=float)
            - frame["candidate_wall_strike"].to_numpy(dtype=float)[:, None]
        )
        / frame["subscription_spot_tminus5m"].to_numpy(dtype=float)[:, None]
        * 10_000.0
    )
    minimum = np.full(len(frame), np.nan, dtype=float)
    valid = np.isfinite(distances).any(axis=1)
    minimum[valid] = np.nanmin(distances[valid], axis=1)
    frame["subscription_dt"] = frame["decision_dt"] - pd.Timedelta(minutes=5)
    frame["subscription_min_wall_distance_bps"] = minimum
    frame["wall_proximity_eligible_v1"] = pd.Series(minimum).le(150.0 + 1e-9)
    return frame.sort_values(keys, kind="stable").reset_index(drop=True)


def _read_quote_columns(path: str | Path) -> pd.DataFrame:
    names = set(pq.ParquetFile(path).schema_arrow.names)
    missing = sorted(set(QUOTE_COLUMNS).difference(names))
    if missing:
        raise KeyError(f"native quote snapshot lacks listing fields: {missing}")
    return pd.read_parquet(path, columns=list(QUOTE_COLUMNS))


def audit_session(
    source: dict[str, Any], candidates: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if sha256_file(source["quotes_path"]) != str(source["quotes_sha256"]):
        raise AssertionError("native quote parquet hash mismatch")
    if sha256_file(source["session_manifest_path"]) != str(
        source["session_manifest_sha256"]
    ):
        raise AssertionError("native quote session-manifest hash mismatch")
    quotes = _read_quote_columns(source["quotes_path"])
    quotes["symbol"] = quotes["symbol"].astype(str).str.upper()
    quotes["expiration"] = (
        quotes["expiration"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    )
    quotes["timestamp"] = pd.to_datetime(quotes["timestamp"], errors="coerce")
    quotes["strike"] = pd.to_numeric(quotes["strike"], errors="coerce")
    quotes["right"] = quotes["right"].astype(str).str.upper().replace(
        {"CALL": "C", "PUT": "P"}
    )
    bad_clock = quotes["timestamp"].isna().sum()
    if bad_clock:
        raise AssertionError("native quote snapshot has invalid timestamp")
    quotes = quotes[
        quotes["symbol"].eq(str(source["ticker"]))
        & quotes["expiration"].eq(str(source["trade_date"]))
        & quotes["right"].isin(["C", "P"])
        & np.isfinite(quotes["strike"])
    ][["timestamp", "strike", "right"]].drop_duplicates()

    records: list[dict[str, Any]] = []
    for row in candidates.itertuples(index=False):
        at_time = quotes[quotes["timestamp"].eq(row.subscription_dt)]
        at_contract = at_time[
            np.isclose(
                at_time["strike"].to_numpy(dtype=float),
                float(row.candidate_wall_strike),
                rtol=0.0,
                atol=1e-9,
            )
        ]
        rights = set(at_contract["right"].astype(str))
        call = "C" in rights
        put = "P" in rights
        covered = not at_time.empty
        listed = call and put
        proximity = bool(row.wall_proximity_eligible_v1)
        eligible = proximity and listed
        if eligible:
            reason = "eligible"
        elif not proximity:
            reason = "wall_not_in_tminus5_radius"
        elif not covered:
            reason = "subscription_timestamp_not_covered"
        elif not call and not put:
            reason = "exact_strike_not_listed"
        elif not call:
            reason = "call_not_listed"
        else:
            reason = "put_not_listed"
        records.append(
            {
                "event_id": row.event_id,
                "ticker": row.ticker,
                "trade_date": row.trade_date,
                "decision_dt": row.decision_dt,
                "subscription_dt": row.subscription_dt,
                "candidate_wall_strike": float(row.candidate_wall_strike),
                "subscription_min_wall_distance_bps": float(
                    row.subscription_min_wall_distance_bps
                )
                if np.isfinite(row.subscription_min_wall_distance_bps)
                else np.nan,
                "wall_proximity_eligible_v1": proximity,
                "subscription_timestamp_covered": covered,
                "exact_call_listed_tminus5m": call,
                "exact_put_listed_tminus5m": put,
                "exact_both_rights_listed_tminus5m": listed,
                "causal_subscription_eligible_v1r1": eligible,
                "eligibility_reason": reason,
            }
        )
    return pd.DataFrame(records), {
        "ticker": str(source["ticker"]),
        "trade_date": str(source["trade_date"]),
        "origin": str(source["origin"]),
        "quotes_path": str(source["quotes_path"]),
        "quotes_sha256": str(source["quotes_sha256"]),
        "session_manifest_path": str(source["session_manifest_path"]),
        "session_manifest_sha256": str(source["session_manifest_sha256"]),
        "quote_rows": int(len(quotes)),
        "candidate_rows": int(len(candidates)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--wall-state", required=True)
    parser.add_argument("--fallback-index", required=True)
    parser.add_argument("--fallback-seal", required=True)
    parser.add_argument("--complement-index", required=True)
    parser.add_argument("--complement-seal", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=16)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= int(args.workers) <= 32:
        raise ValueError("H-QDYN1R1 allowlist workers must be within 1..32")
    output = Path(args.output_dir)
    staging = output.with_name(output.name + ".staging")
    if output.exists() or staging.exists():
        raise FileExistsError("immutable H-QDYN1R1 allowlist output already exists")
    commit, code_hashes = committed_code_state()
    runtime = assert_runtime_lock(PROJECT_ROOT / RUNTIME_LOCK)
    candidates = load_candidate_proximity(args.candidates, args.wall_state)
    combined, sidecar_provenance = load_combined_quote_index(
        args.fallback_index,
        args.fallback_seal,
        args.complement_index,
        args.complement_seal,
    )
    needed = combined.merge(
        candidates[["ticker", "trade_date"]].drop_duplicates(),
        on=["ticker", "trade_date"],
        how="inner",
        validate="one_to_one",
    )
    if len(needed) != 2519:
        raise AssertionError("H-QDYN1R1 requires all 2,519 frozen sessions")

    outputs: list[pd.DataFrame] = []
    inventories: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ProcessPoolExecutor(max_workers=int(args.workers)) as pool:
        futures = {}
        for source in needed.to_dict("records"):
            part = candidates[
                candidates["ticker"].eq(source["ticker"])
                & candidates["trade_date"].eq(source["trade_date"])
            ].copy()
            futures[pool.submit(audit_session, source, part)] = (
                source["ticker"],
                source["trade_date"],
            )
        for count, future in enumerate(as_completed(futures), start=1):
            key = futures[future]
            try:
                rows, inventory = future.result()
                outputs.append(rows)
                inventories.append(inventory)
            except Exception as exc:
                errors.append(
                    {
                        "ticker": str(key[0]),
                        "trade_date": str(key[1]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            if count % 100 == 0 or count == len(futures):
                print(
                    f"[H-QDYN1R1_ALLOWLIST] sessions={count}/{len(futures)} "
                    f"errors={len(errors)}",
                    flush=True,
                )
    if errors:
        raise AssertionError(f"H-QDYN1R1 listing audit failed: {errors[:10]}")
    proof = pd.concat(outputs, ignore_index=True).sort_values(
        ["ticker", "trade_date", "decision_dt", "candidate_wall_strike"],
        kind="stable",
    ).reset_index(drop=True)
    inventory = pd.DataFrame(inventories).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(proof) != EXPECTED_CANDIDATES
        or proof["event_id"].duplicated().any()
        or set(proof["event_id"]) != set(candidates["event_id"])
        or len(inventory) != 2519
        or inventory.duplicated(["ticker", "trade_date"]).any()
    ):
        raise AssertionError("H-QDYN1R1 proof cardinality changed")

    staging.mkdir(parents=True, exist_ok=False)
    proof_path = staging / "subscription_allowlist.parquet"
    inventory_path = staging / "source_inventory.csv"
    coverage_path = staging / "coverage_by_ticker_month.csv"
    proof.to_parquet(proof_path, index=False)
    inventory.to_csv(inventory_path, index=False)
    coverage = (
        proof.assign(month=proof["trade_date"].str[:6])
        .groupby(["ticker", "month"], as_index=False)
        .agg(
            candidates=("event_id", "size"),
            wall_proximity=("wall_proximity_eligible_v1", "sum"),
            timestamp_covered=("subscription_timestamp_covered", "sum"),
            both_rights_listed=("exact_both_rights_listed_tminus5m", "sum"),
            eligible=("causal_subscription_eligible_v1r1", "sum"),
        )
    )
    coverage.to_csv(coverage_path, index=False)
    eligible = proof[proof["causal_subscription_eligible_v1r1"].astype(bool)]
    manifest = {
        "schema": "wall_qdyn_subscription_allowlist_v1r1",
        "status": "PASS_SUBSCRIPTION_ALLOWLIST_V1R1",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "code_hashes": code_hashes,
        "candidate_path": str(Path(args.candidates)),
        "candidate_sha256": sha256_file(args.candidates),
        "wall_state_path": str(Path(args.wall_state)),
        "wall_state_sha256": sha256_file(args.wall_state),
        "candidates": int(len(proof)),
        "wall_proximity_events": int(proof["wall_proximity_eligible_v1"].sum()),
        "exact_both_rights_listed_events": int(
            proof["exact_both_rights_listed_tminus5m"].sum()
        ),
        "eligible_events": int(len(eligible)),
        "eligible_event_id_sha256": line_hash(eligible["event_id"].astype(str).tolist()),
        "rows_by_ticker": proof.groupby("ticker").size().astype(int).to_dict(),
        "eligible_by_ticker": eligible.groupby("ticker").size().astype(int).to_dict(),
        "eligibility_reasons": proof["eligibility_reason"].value_counts().astype(int).to_dict(),
        "proof_path": str(output / proof_path.name),
        "proof_sha256": sha256_file(proof_path),
        "source_inventory_path": str(output / inventory_path.name),
        "source_inventory_sha256": sha256_file(inventory_path),
        "coverage_path": str(output / coverage_path.name),
        "coverage_sha256": sha256_file(coverage_path),
        "sidecar_provenance": sidecar_provenance,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "errors": [],
    }
    (staging / "manifest.json").write_bytes(canonical_bytes(manifest))
    staging.rename(output)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
