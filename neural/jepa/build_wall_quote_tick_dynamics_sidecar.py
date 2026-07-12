"""Capture sealed predecision option NBBO ticks for H-QDYN1."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.build_wall_native_quote_sidecar import (  # noqa: E402
    local_terminal_process_evidence,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402

EXPECTED_CANDIDATE_SHA256 = "f4ed7b2360dd2ff3676a23ac2da297c73554ccfd0f5486314b85cc88d0ef6c49"
EXPECTED_CANDIDATES = 10683
EXPECTED_WALL_STATE_SHA256 = "94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef"
EXPECTED_ELIGIBLE_EVENTS = 9833
EXPECTED_ELIGIBLE_EVENT_ID_SHA256 = "f77dc2231f410679ad97737cc8a4af057e917224e31d2c5df3b6f1f8366a2eca"
EXPECTED_SUBSCRIPTION_PROOF_SHA256 = (
    "083a77f3a24225e9ad38b6c401b4382c17b8621f69b0af4563f1eadcf927623c"
)
EXPECTED_SUBSCRIPTION_PROOF_MANIFEST_SHA256 = (
    "2188a2cf6003c340a692220c24beeacc1be621aa171b88b2639d5a0593c021a5"
)
ENDPOINT = "/option/history/quote"
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
CODE_CLOSURE = (
    "neural/jepa/build_wall_quote_tick_dynamics_sidecar.py",
    "neural/jepa/build_wall_qdyn_subscription_allowlist.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    "neural/jepa/wall_surface_flow_environment.py",
    PREDECLARATION,
    CAUSAL_AMENDMENT,
    CAPTURE_CLARIFICATION,
    RUNTIME_LOCK,
)
OUTPUT_COLUMNS = (
    "ticker",
    "expiration",
    "trade_date",
    "event_id",
    "decision_dt",
    "wall_strike",
    "timestamp",
    "right",
    "contract_ordinal",
    "bid",
    "ask",
    "bid_size",
    "ask_size",
    "bid_exchange",
    "ask_exchange",
    "bid_condition",
    "ask_condition",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def event_id(row: dict[str, Any]) -> str:
    decision = pd.Timestamp(row["decision_dt"])
    identity = (
        f"{str(row['ticker']).upper()}|{str(row['trade_date'])}|"
        f"{decision.isoformat()}|{float(row['candidate_wall_strike']):.6f}"
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


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
            raise AssertionError(f"H-QDYN1 capture requires clean code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, hashes


def load_candidates(
    path: str | Path,
    wall_state_path: str | Path,
    proof_path: str | Path,
    proof_manifest_path: str | Path,
) -> pd.DataFrame:
    if sha256_file(path) != EXPECTED_CANDIDATE_SHA256:
        raise AssertionError("H-QDYN1 candidate dataset hash mismatch")
    columns = [
        "ticker",
        "trade_date",
        "decision_dt",
        "candidate_wall_strike",
    ]
    frame = pd.read_parquet(path, columns=columns)
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["trade_date"] = frame["trade_date"].astype(str)
    frame["decision_dt"] = pd.to_datetime(frame["decision_dt"], errors="coerce")
    frame["candidate_wall_strike"] = pd.to_numeric(
        frame["candidate_wall_strike"], errors="coerce"
    )
    keys = ["ticker", "trade_date", "decision_dt", "candidate_wall_strike"]
    if (
        len(frame) != EXPECTED_CANDIDATES
        or frame.duplicated(keys).any()
        or frame["decision_dt"].isna().any()
        or frame["decision_dt"].dt.second.ne(0).any()
        or frame["decision_dt"].dt.microsecond.ne(0).any()
        or frame["trade_date"].ge("20260101").any()
        or not frame["ticker"].isin(["SPXW", "QQQ", "SPY"]).all()
        or not np.isfinite(frame["candidate_wall_strike"]).all()
        or frame["candidate_wall_strike"].le(0).any()
        or not frame["decision_dt"].dt.strftime("%Y%m%d").eq(frame["trade_date"]).all()
    ):
        raise AssertionError("invalid H-QDYN1 frozen candidate universe")
    frame["event_id"] = [event_id(row) for row in frame.to_dict("records")]
    if frame["event_id"].duplicated().any():
        raise AssertionError("H-QDYN1 event id collision")
    if sha256_file(wall_state_path) != EXPECTED_WALL_STATE_SHA256:
        raise AssertionError("H-QDYN1 wall-state hash mismatch")
    wall_names = (
        "wall_call_gamma_strike",
        "wall_put_gamma_strike",
        "wall_call_delta_strike",
        "wall_put_delta_strike",
    )
    walls = pd.read_parquet(
        wall_state_path,
        columns=["ticker", "trade_date", "dt", "spot", *wall_names],
    )
    walls["decision_dt"] = pd.to_datetime(walls.pop("dt")) + pd.Timedelta(minutes=5)
    walls = walls.rename(columns={"spot": "subscription_spot_tminus5m"})
    frame = frame.merge(
        walls,
        on=["ticker", "trade_date", "decision_dt"],
        how="left",
        validate="many_to_one",
    )
    distances = (
        np.abs(
            frame[list(wall_names)].to_numpy(dtype=float)
            - frame["candidate_wall_strike"].to_numpy(dtype=float)[:, None]
        )
        / frame["subscription_spot_tminus5m"].to_numpy(dtype=float)[:, None]
        * 10_000.0
    )
    minimum_distance = np.full(len(frame), np.nan, dtype=float)
    finite_distance = np.isfinite(distances).any(axis=1)
    minimum_distance[finite_distance] = np.nanmin(
        distances[finite_distance], axis=1
    )
    frame["subscription_min_wall_distance_bps"] = minimum_distance
    frame["wall_proximity_eligible_v1"] = frame[
        "subscription_min_wall_distance_bps"
    ].le(150.0 + 1e-9)
    eligible_ids = sorted(
        frame.loc[frame["wall_proximity_eligible_v1"], "event_id"].astype(str)
    )
    eligible_hash = sha256_bytes("\n".join(eligible_ids).encode("utf-8"))
    if (
        len(eligible_ids) != EXPECTED_ELIGIBLE_EVENTS
        or eligible_hash != EXPECTED_ELIGIBLE_EVENT_ID_SHA256
    ):
        raise AssertionError("H-QDYN1 causal subscription allowlist changed")

    if (
        sha256_file(proof_path) != EXPECTED_SUBSCRIPTION_PROOF_SHA256
        or sha256_file(proof_manifest_path)
        != EXPECTED_SUBSCRIPTION_PROOF_MANIFEST_SHA256
    ):
        raise AssertionError("H-QDYN1R1 subscription proof hash mismatch")
    proof_manifest = json.loads(Path(proof_manifest_path).read_text(encoding="utf-8"))
    if (
        proof_manifest.get("status") != "PASS_SUBSCRIPTION_ALLOWLIST_V1R1R1"
        or proof_manifest.get("outcome_free") is not True
        or proof_manifest.get("holdout_2026_used") is not False
        or proof_manifest.get("candidate_sha256") != EXPECTED_CANDIDATE_SHA256
        or proof_manifest.get("wall_state_sha256") != EXPECTED_WALL_STATE_SHA256
        or proof_manifest.get("proof_sha256")
        != EXPECTED_SUBSCRIPTION_PROOF_SHA256
        or int(proof_manifest.get("candidates", -1)) != EXPECTED_CANDIDATES
        or int(proof_manifest.get("eligible_events", -1))
        != EXPECTED_ELIGIBLE_EVENTS
        or proof_manifest.get("eligible_event_id_sha256")
        != EXPECTED_ELIGIBLE_EVENT_ID_SHA256
        or proof_manifest.get("errors") != []
    ):
        raise AssertionError("H-QDYN1R1 subscription proof contract mismatch")
    proof = pd.read_parquet(proof_path)
    required = {
        "event_id",
        "ticker",
        "trade_date",
        "wall_proximity_eligible_v1",
        "exact_call_listed_tminus5m",
        "exact_put_listed_tminus5m",
        "causal_subscription_eligible_v1r1",
    }
    if required.difference(proof.columns):
        raise KeyError(
            f"H-QDYN1R1 subscription proof missing: {sorted(required.difference(proof.columns))}"
        )
    proof = proof[list(required)].copy()
    proof["ticker"] = proof["ticker"].astype(str).str.upper()
    proof["trade_date"] = (
        proof["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    )
    boolean_columns = (
        "wall_proximity_eligible_v1",
        "exact_call_listed_tminus5m",
        "exact_put_listed_tminus5m",
        "causal_subscription_eligible_v1r1",
    )
    for column in boolean_columns:
        if not pd.api.types.is_bool_dtype(proof[column]):
            raise AssertionError(f"H-QDYN1R1 proof has non-boolean {column}")
    derived = (
        proof["wall_proximity_eligible_v1"]
        & proof["exact_call_listed_tminus5m"]
        & proof["exact_put_listed_tminus5m"]
    )
    proof_ids = sorted(proof.loc[derived, "event_id"].astype(str))
    if (
        len(proof) != EXPECTED_CANDIDATES
        or proof["event_id"].duplicated().any()
        or not proof["causal_subscription_eligible_v1r1"].eq(derived).all()
        or len(proof_ids) != EXPECTED_ELIGIBLE_EVENTS
        or sha256_bytes("\n".join(proof_ids).encode("utf-8"))
        != EXPECTED_ELIGIBLE_EVENT_ID_SHA256
    ):
        raise AssertionError("H-QDYN1R1 subscription proof universe changed")
    frame = frame.merge(
        proof,
        on=["event_id", "ticker", "trade_date"],
        how="left",
        validate="one_to_one",
        suffixes=("", "_proof"),
    )
    if (
        frame["causal_subscription_eligible_v1r1"].isna().any()
        or not frame["wall_proximity_eligible_v1"].eq(
            frame["wall_proximity_eligible_v1_proof"]
        ).all()
    ):
        raise AssertionError("H-QDYN1R1 proof does not match frozen geometry")
    frame = frame.drop(columns=["wall_proximity_eligible_v1_proof"])
    frame["causal_subscription_eligible"] = frame[
        "causal_subscription_eligible_v1r1"
    ]
    return frame.sort_values(keys, kind="stable").reset_index(drop=True)


def normalize_tick_response(
    raw: dict[str, Any], candidate: dict[str, Any]
) -> pd.DataFrame:
    ticker = str(candidate["ticker"]).upper()
    day = str(candidate["trade_date"])
    decision = pd.Timestamp(candidate["decision_dt"])
    start = decision - pd.Timedelta(seconds=32)
    end = decision - pd.Timedelta(seconds=2, milliseconds=1)
    wall = float(candidate["candidate_wall_strike"])
    rows: list[dict[str, Any]] = []
    response = raw.get("response")
    if not isinstance(response, list):
        raise AssertionError("H-QDYN1 response lacks contract list")
    for block in response:
        contract = block.get("contract", {})
        symbol = str(contract.get("symbol", "")).upper()
        expiration = "".join(ch for ch in str(contract.get("expiration", "")) if ch.isdigit())[:8]
        right = str(contract.get("right", "")).upper()
        strike = float(contract.get("strike", np.nan))
        if (
            symbol != ticker
            or expiration != day
            or right not in {"CALL", "PUT"}
            or not np.isfinite(strike)
            or strike != wall
        ):
            raise AssertionError("H-QDYN1 response contract substitution")
        data = block.get("data", [])
        if not isinstance(data, list):
            raise AssertionError("H-QDYN1 contract data is not a list")
        for ordinal, value in enumerate(data):
            rows.append(
                {
                    "ticker": ticker,
                    "expiration": day,
                    "trade_date": day,
                    "event_id": str(candidate["event_id"]),
                    "decision_dt": decision,
                    "wall_strike": wall,
                    "timestamp": value.get("timestamp"),
                    "right": right,
                    "contract_ordinal": ordinal,
                    "bid": value.get("bid"),
                    "ask": value.get("ask"),
                    "bid_size": value.get("bid_size"),
                    "ask_size": value.get("ask_size"),
                    "bid_exchange": value.get("bid_exchange"),
                    "ask_exchange": value.get("ask_exchange"),
                    "bid_condition": value.get("bid_condition"),
                    "ask_condition": value.get("ask_condition"),
                }
            )
    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if frame.empty:
        return frame
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    for column in (
        "bid",
        "ask",
        "bid_size",
        "ask_size",
        "bid_exchange",
        "ask_exchange",
        "bid_condition",
        "ask_condition",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if (
        frame["timestamp"].isna().any()
        or not frame["timestamp"].ge(start).all()
        or not frame["timestamp"].le(end).all()
    ):
        raise AssertionError("H-QDYN1 response violates causal tick contract")
    for _, part in frame.groupby("right", sort=False):
        if not part["contract_ordinal"].eq(np.arange(len(part))).all():
            raise AssertionError("H-QDYN1 provider response order was not preserved")
    return frame.reset_index(drop=True)


def contract_block_audit(raw: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    response = raw.get("response")
    if not isinstance(response, list):
        raise AssertionError("H-QDYN1 response lacks contract list")
    counts = {"CALL": 0, "PUT": 0}
    for block in response:
        contract = block.get("contract", {})
        symbol = str(contract.get("symbol", "")).upper()
        expiration = "".join(
            char for char in str(contract.get("expiration", "")) if char.isdigit()
        )[:8]
        right = str(contract.get("right", "")).upper()
        strike = float(contract.get("strike", np.nan))
        if (
            symbol != str(candidate["ticker"]).upper()
            or expiration != str(candidate["trade_date"])
            or right not in counts
            or not np.isfinite(strike)
            or strike != float(candidate["candidate_wall_strike"])
        ):
            raise AssertionError("H-QDYN1 response contract substitution")
        counts[right] += 1
    if any(value > 1 for value in counts.values()):
        raise AssertionError("H-QDYN1 duplicate contract block")
    missing = [right for right, count in counts.items() if count == 0]
    return {
        "call_contract_blocks": int(counts["CALL"]),
        "put_contract_blocks": int(counts["PUT"]),
        "missing_rights": missing,
    }


def request_params(candidate: dict[str, Any]) -> dict[str, str]:
    decision = pd.Timestamp(candidate["decision_dt"])
    start = decision - pd.Timedelta(seconds=32)
    end = decision - pd.Timedelta(seconds=2, milliseconds=1)
    return {
        "symbol": str(candidate["ticker"]),
        "expiration": str(candidate["trade_date"]),
        "date": str(candidate["trade_date"]),
        "strike": f"{float(candidate['candidate_wall_strike']):.6f}",
        "right": "both",
        "interval": "tick",
        "format": "json",
        "start_time": start.strftime("%H:%M:%S.%f")[:-3],
        "end_time": end.strftime("%H:%M:%S.%f")[:-3],
    }


def validate_event_dir(
    path: Path,
    candidate: dict[str, Any],
    *,
    code_hashes: dict[str, str],
    terminal_evidence: dict[str, Any],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    manifest_path = path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_path, parquet_path = path / "response.json", path / "ticks.parquet"
    if (
        manifest.get("status") != "PASS_QDYN_EVENT"
        or manifest.get("event_id") != candidate["event_id"]
        or manifest.get("outcome_free") is not True
        or manifest.get("holdout_2026_used") is not False
        or manifest.get("raw_sha256") != sha256_file(raw_path)
        or manifest.get("parquet_sha256") != sha256_file(parquet_path)
        or manifest.get("request_params") != request_params(candidate)
        or manifest.get("code_hashes") != code_hashes
        or manifest.get("terminal_process_evidence") != terminal_evidence
        or manifest.get("runtime_lock_sha256") != runtime["lock_sha256"]
        or manifest.get("runtime_environment_sha256")
        != runtime["environment_sha256"]
    ):
        raise AssertionError(f"invalid immutable H-QDYN1 event: {path}")
    raw = json.loads(raw_path.read_bytes())
    block_audit = contract_block_audit(raw, candidate)
    if manifest.get("contract_block_audit") != block_audit:
        raise AssertionError("H-QDYN1 contract-block audit mismatch")
    stored = pd.read_parquet(parquet_path)
    rebuilt = normalize_tick_response(raw, candidate)
    try:
        pd.testing.assert_frame_equal(stored, rebuilt, check_dtype=True)
    except AssertionError as exc:
        raise AssertionError("H-QDYN1 raw/parquet reconstruction mismatch") from exc
    if len(stored) != int(manifest.get("rows", -1)):
        raise AssertionError("H-QDYN1 stored row count mismatch")
    end = pd.Timestamp(candidate["decision_dt"]) - pd.Timedelta(
        seconds=2, milliseconds=1
    )
    if len(stored) and pd.to_datetime(stored["timestamp"]).gt(end).any():
        raise AssertionError("stored H-QDYN1 future tick")
    return manifest


def capture_event(
    candidate: dict[str, Any],
    *,
    output_root: str | Path,
    base_url: str,
    terminal_evidence: dict[str, Any],
    runtime: dict[str, Any],
    code_hashes: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    path = (
        Path(output_root)
        / str(candidate["ticker"])
        / str(candidate["trade_date"])
        / str(candidate["event_id"])
    )
    if path.exists():
        return validate_event_dir(
            path,
            candidate,
            code_hashes=code_hashes,
            terminal_evidence=terminal_evidence,
            runtime=runtime,
        )
    staging = path.with_name(path.name + ".staging")
    if staging.exists():
        suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        quarantine = staging.with_name(staging.name + f".rejected-{suffix}")
        staging.rename(quarantine)
    decision = pd.Timestamp(candidate["decision_dt"])
    params = request_params(candidate)
    response = None
    raw_bytes = b""
    frame: pd.DataFrame | None = None
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(
                f"{base_url.rstrip('/')}{ENDPOINT}",
                params=params,
                headers={"Accept-Encoding": "identity"},
                timeout=timeout,
            )
            response.raise_for_status()
            raw_bytes = bytes(response.content)
            if not raw_bytes:
                raise AssertionError("empty H-QDYN1 raw response")
            raw = json.loads(raw_bytes)
            block_audit = contract_block_audit(raw, candidate)
            frame = normalize_tick_response(raw, candidate)
            break
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.0 + attempt)
    if response is None or not response.ok or frame is None:
        raise RuntimeError(f"H-QDYN1 request failed: {last_error}")
    staging.mkdir(parents=True, exist_ok=False)
    raw_path, parquet_path = staging / "response.json", staging / "ticks.parquet"
    raw_path.write_bytes(raw_bytes)
    frame.to_parquet(parquet_path, index=False)
    counts = frame["right"].value_counts().to_dict() if len(frame) else {}
    manifest = {
        "schema": "wall_quote_tick_dynamics_event_v1r1r1",
        "status": "PASS_QDYN_EVENT",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "event_id": str(candidate["event_id"]),
        "ticker": str(candidate["ticker"]),
        "trade_date": str(candidate["trade_date"]),
        "decision_dt": decision.isoformat(),
        "wall_strike": float(candidate["candidate_wall_strike"]),
        "request_params": params,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "terminal_process_evidence": terminal_evidence,
        "code_hashes": code_hashes,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "raw_sha256": sha256_file(raw_path),
        "parquet_sha256": sha256_file(parquet_path),
        "rows": len(frame),
        "call_rows": int(counts.get("CALL", 0)),
        "put_rows": int(counts.get("PUT", 0)),
        "contract_block_audit": block_audit,
        "max_timestamp": frame["timestamp"].max().isoformat() if len(frame) else None,
    }
    (staging / "manifest.json").write_bytes(canonical_bytes(manifest))
    path.parent.mkdir(parents=True, exist_ok=True)
    staging.rename(path)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--wall-state", required=True)
    parser.add_argument("--subscription-proof", required=True)
    parser.add_argument("--subscription-proof-manifest", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:25503/v3")
    parser.add_argument("--terminal-jar", required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.workers <= 4:
        raise ValueError("H-QDYN1 workers must be 1..4")
    if (urlparse(args.base_url).hostname or "").lower() not in {"127.0.0.1", "localhost", "::1"}:
        raise AssertionError("H-QDYN1 capture requires local Theta Terminal")
    output = Path(args.output_root)
    seal_dir = output / "_seal"
    if seal_dir.exists():
        raise FileExistsError(f"H-QDYN1 seal already exists: {seal_dir}")
    commit, code_hashes = committed_code_state()
    runtime = assert_runtime_lock(PROJECT_ROOT / RUNTIME_LOCK)
    jar = Path(args.terminal_jar).resolve()
    terminal_evidence = local_terminal_process_evidence(args.base_url, jar)
    if terminal_evidence.get("terminal_jar_sha256") != sha256_file(jar):
        raise AssertionError("active Terminal/JAR mismatch")
    candidates = load_candidates(
        args.candidates,
        args.wall_state,
        args.subscription_proof,
        args.subscription_proof_manifest,
    )
    eligibility_path = output / "candidate_subscription_eligibility.csv"
    eligibility_columns = [
        "ticker",
        "trade_date",
        "decision_dt",
        "candidate_wall_strike",
        "event_id",
        "subscription_spot_tminus5m",
        "wall_call_gamma_strike",
        "wall_put_gamma_strike",
        "wall_call_delta_strike",
        "wall_put_delta_strike",
        "subscription_min_wall_distance_bps",
        "wall_proximity_eligible_v1",
        "exact_call_listed_tminus5m",
        "exact_put_listed_tminus5m",
        "causal_subscription_eligible_v1r1",
        "causal_subscription_eligible",
    ]
    eligibility_csv = candidates[eligibility_columns].to_csv(index=False)
    if eligibility_path.exists():
        if eligibility_path.read_text(encoding="utf-8") != eligibility_csv:
            raise AssertionError("existing H-QDYN1 eligibility differs")
    else:
        eligibility_path.parent.mkdir(parents=True, exist_ok=True)
        eligibility_path.write_text(eligibility_csv, encoding="utf-8")
    capture_candidates = candidates[candidates["causal_subscription_eligible"]].copy()
    rows, errors = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                capture_event,
                row,
                output_root=output,
                base_url=args.base_url,
                terminal_evidence=terminal_evidence,
                runtime=runtime,
                code_hashes=code_hashes,
                timeout=args.timeout,
            ): row
            for row in capture_candidates.to_dict("records")
        }
        completed = 0
        for future in as_completed(futures):
            candidate = futures[future]
            try:
                manifest = future.result()
                event_path = (
                    output
                    / candidate["ticker"]
                    / candidate["trade_date"]
                    / candidate["event_id"]
                )
                rows.append(
                    {
                        "ticker": candidate["ticker"],
                        "trade_date": candidate["trade_date"],
                        "decision_dt": pd.Timestamp(candidate["decision_dt"]).isoformat(),
                        "wall_strike": float(candidate["candidate_wall_strike"]),
                        "event_id": candidate["event_id"],
                        "event_dir": str(event_path),
                        "raw_path": str(event_path / "response.json"),
                        "raw_sha256": manifest["raw_sha256"],
                        "parquet_path": str(event_path / "ticks.parquet"),
                        "parquet_sha256": manifest["parquet_sha256"],
                        "manifest_path": str(event_path / "manifest.json"),
                        "manifest_sha256": sha256_file(event_path / "manifest.json"),
                        "rows": int(manifest["rows"]),
                        "call_rows": int(manifest["call_rows"]),
                        "put_rows": int(manifest["put_rows"]),
                    }
                )
            except Exception as exc:
                errors.append(
                    {
                        "ticker": candidate["ticker"],
                        "trade_date": candidate["trade_date"],
                        "event_id": candidate["event_id"],
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            completed += 1
            if completed % 50 == 0 or completed == len(capture_candidates):
                print(
                    f"[H-QDYN1] events={completed}/{len(capture_candidates)} "
                    f"errors={len(errors)}",
                    flush=True,
                )
    if errors or len(rows) != EXPECTED_ELIGIBLE_EVENTS:
        raise AssertionError(f"H-QDYN1 capture incomplete: errors={errors[:20]}")
    index = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date", "decision_dt", "wall_strike"], kind="stable"
    )
    if index["event_id"].duplicated().any() or index["rows"].lt(0).any():
        raise AssertionError("H-QDYN1 final index invalid")
    revalidated_rows: list[dict[str, Any]] = []
    candidate_by_id = {
        str(row["event_id"]): row for row in capture_candidates.to_dict("records")
    }
    for row in index.to_dict("records"):
        candidate = candidate_by_id[str(row["event_id"])]
        manifest = validate_event_dir(
            Path(row["event_dir"]),
            candidate,
            code_hashes=code_hashes,
            terminal_evidence=terminal_evidence,
            runtime=runtime,
        )
        revalidated_rows.append(
            {
                "event_id": str(row["event_id"]),
                "raw_sha256": str(manifest["raw_sha256"]),
                "parquet_sha256": str(manifest["parquet_sha256"]),
            }
        )
    if len(revalidated_rows) != EXPECTED_ELIGIBLE_EVENTS:
        raise AssertionError("H-QDYN1 final integral revalidation incomplete")
    seal_dir.mkdir(parents=True, exist_ok=False)
    index_path = seal_dir / "quote_tick_dynamics_index.csv"
    index.to_csv(index_path, index=False)
    seal = {
        "schema": "wall_quote_tick_dynamics_seal_v1r1r1",
        "status": "PASS_QDYN_CAPTURE",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "git_commit": commit,
        "code_hashes": code_hashes,
        "candidate_dataset_sha256": EXPECTED_CANDIDATE_SHA256,
        "wall_state_sha256": EXPECTED_WALL_STATE_SHA256,
        "candidates": len(candidates),
        "eligible_events": len(index),
        "ineligible_events": int((~candidates["causal_subscription_eligible"]).sum()),
        "eligible_event_id_sha256": EXPECTED_ELIGIBLE_EVENT_ID_SHA256,
        "subscription_proof_sha256": sha256_file(args.subscription_proof),
        "subscription_proof_manifest_sha256": sha256_file(
            args.subscription_proof_manifest
        ),
        "eligibility_sha256": sha256_file(eligibility_path),
        "rows": int(index["rows"].sum()),
        "call_rows": int(index["call_rows"].sum()),
        "put_rows": int(index["put_rows"].sum()),
        "zero_call_events": int(index["call_rows"].eq(0).sum()),
        "zero_put_events": int(index["put_rows"].eq(0).sum()),
        "index_sha256": sha256_file(index_path),
        "terminal_process_evidence": terminal_evidence,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "historical_provenance": "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION",
        "errors": [],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (seal_dir / "manifest.json").write_bytes(canonical_bytes(seal))
    print(json.dumps(seal, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
