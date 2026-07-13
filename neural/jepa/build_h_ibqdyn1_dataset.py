"""Build the frozen outcome-free H-IBQDYN1 F0/F1 data-gate dataset."""

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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.build_h_ibqdyn1_feasibility import (  # noqa: E402
    EXPECTED_BY_TICKER,
    EXPECTED_EVENTS,
    EXPECTED_SOURCE_SHA256,
    load_opportunity_universe,
)
from neural.jepa.capture_h_ibqdyn1_tick_preflight import (  # noqa: E402
    EXPECTED_ELIGIBLE_EVENTS,
    EXPECTED_ELIGIBLE_ID_SHA256,
    EXPECTED_FULL_CONTRACTS,
    EXPECTED_PROOF_MANIFEST_SHA256,
    EXPECTED_PROOF_SHA256,
)
from neural.jepa.capture_h_ibqdyn1_full import CODE_CLOSURE as CAPTURE_CODE_CLOSURE  # noqa: E402
from neural.jepa.evaluate_wall_surface_flow_at_touch_v1 import (  # noqa: E402
    EXPECTED_SESSION_COUNT,
    assert_source_inventory,
)
from neural.jepa.h_ibqdyn1_features import ALPHA_FIELDS, event_features  # noqa: E402
from neural.jepa.surface_flow_features import (  # noqa: E402
    CONTROL_FEATURES,
    attach_completed_underlying_controls,
    validate_underlying_session,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402
from neural.jepa.build_wall_quote_tick_dynamics_sidecar import sha256_file  # noqa: E402

PREDECLARATION = "research_papers/JEPA/H_IBQDYN1_FEASIBILITY_PREDECLARATION.md"
FEATURE_CLARIFICATION = (
    "research_papers/JEPA/H_IBQDYN1_FEATURE_SEMANTICS_CLARIFICATION.md"
)
DATA_GATE_CONTRACT = "research_papers/JEPA/H_IBQDYN1_DATA_GATE_CONTRACT.md"
RUNTIME_LOCK = "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
PROOF_MANIFEST = (
    "research_papers/JEPA/results/_diagnostics/"
    "h_ibqdyn1_listing_feasibility_202208_202512_v1/manifest.json"
)
PROOF_PATH = (
    "research_papers/JEPA/results/_diagnostics/"
    "h_ibqdyn1_listing_feasibility_202208_202512_v1/"
    "subscription_listing_proof.parquet"
)
EXPECTED_UNDERLYING_INVENTORY_SHA256 = (
    "2a305a2910f83c42a3c32b455d9b3a93907c7d762c5168d0946f9ce1eae306e8"
)
MIN_ANNUAL_BOTH_VALID_COVERAGE = 0.80
MIN_TICKER_BOTH_VALID_COVERAGE = 0.85
LEVEL_DISTANCE_COLUMNS = {
    "ib_high": "dist_ib_high_bps",
    "ib_low": "dist_ib_low_bps",
    "fib_127_up": "dist_fib_127_up_bps",
    "fib_161_up": "dist_fib_161_up_bps",
    "fib_200_up": "dist_fib_200_up_bps",
    "fib_127_dn": "dist_fib_127_dn_bps",
    "fib_161_dn": "dist_fib_161_dn_bps",
    "fib_200_dn": "dist_fib_200_dn_bps",
}
RESISTANCE_LEVELS = frozenset(
    {"ib_high", "fib_127_up", "fib_161_up", "fib_200_up"}
)
SOURCE_CONTROL_COLUMNS = (
    "ticker",
    "trade_date",
    "timestamp",
    "minute",
    "spot",
    "nearest_level_name",
    "nearest_level_abs_bps",
    "ib_range_bps",
    "ret_1m_bps",
    "ret_5m_bps",
    "ret_15m_bps",
    "ret_30m_bps",
    *LEVEL_DISTANCE_COLUMNS.values(),
)
QUALITY_FIELDS = tuple(
    f"ibqdyn_{side}_{field}"
    for side in ("call", "put")
    for field in (
        "raw_rows",
        "raw_dedup_rows",
        "alpha_state_rows",
        "raw_exact_duplicate_rows",
        "condition_exchange_only_rows",
        "collision_rows",
        "ordered_pair_count",
        "valid",
    )
) + ("causal_subscription_eligible", "ibqdyn_both_valid")
OUTPUT_IDENTITY_COLUMNS = (
    "event_id",
    "ticker",
    "trade_date",
    "minute",
    "decision_dt",
    "clock_block",
    "nearest_level_name",
    "wall_identity",
    "wall_role",
    "candidate_right",
    "candidate_wall_strike",
    "spot",
    "bucket",
    "call_strike",
    "put_strike",
    "episode_id",
)
AUTHORITATIVE_CODE = (
    "neural/jepa/build_h_ibqdyn1_dataset.py",
    "neural/jepa/h_ibqdyn1_features.py",
    "neural/jepa/build_h_ibqdyn1_feasibility.py",
    "neural/jepa/capture_h_ibqdyn1_full.py",
    "neural/jepa/capture_h_ibqdyn1_tick_preflight.py",
    "neural/jepa/surface_flow_features.py",
    "neural/jepa/evaluate_wall_surface_flow_at_touch_v1.py",
    "neural/jepa/wall_surface_flow_environment.py",
    PREDECLARATION,
    FEATURE_CLARIFICATION,
    DATA_GATE_CONTRACT,
    PROOF_MANIFEST,
    RUNTIME_LOCK,
)


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def hash_list(values: tuple[str, ...] | list[str]) -> str:
    return hashlib.sha256(
        json.dumps(list(values), separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()


def line_hash(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def commit_is_ancestor(commit: str) -> bool:
    if len(str(commit)) != 40:
        return False
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", str(commit), "HEAD"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
        ).returncode
        == 0
    )


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
            raise AssertionError(f"H-IBQDYN1 data gate requires clean code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, hashes


def _normalized_day(values: pd.Series) -> pd.Series:
    return values.astype(str).str.replace(r"\D", "", regex=True).str[:8]


def load_control_universe(events_path: str | Path) -> pd.DataFrame:
    if sha256_file(events_path) != EXPECTED_SOURCE_SHA256:
        raise AssertionError("H-IBQDYN1 control source hash mismatch")
    identity = load_opportunity_universe(events_path)
    source = pd.read_parquet(events_path, columns=list(SOURCE_CONTROL_COLUMNS))
    source["ticker"] = source["ticker"].astype(str).str.upper()
    source["trade_date"] = _normalized_day(source["trade_date"])
    source["decision_dt"] = pd.to_datetime(source.pop("timestamp"), errors="coerce")
    for column in set(SOURCE_CONTROL_COLUMNS).difference(
        {"ticker", "trade_date", "timestamp", "nearest_level_name"}
    ):
        source[column] = pd.to_numeric(source[column], errors="coerce")
    keys = ["ticker", "trade_date", "decision_dt"]
    if source["decision_dt"].isna().any() or source.duplicated(keys).any():
        raise AssertionError("H-IBQDYN1 control source has ambiguous decision keys")
    controls = identity.merge(source, on=keys, how="left", suffixes=("", "_source"), validate="one_to_one")
    if len(controls) != EXPECTED_EVENTS:
        raise AssertionError("H-IBQDYN1 control universe cardinality changed")
    for column in ("minute", "spot", "nearest_level_name", "nearest_level_abs_bps"):
        other = f"{column}_source"
        if other in controls:
            if column == "nearest_level_name":
                equal = controls[column].astype(str).eq(controls[other].astype(str))
            else:
                equal = np.isclose(
                    pd.to_numeric(controls[column], errors="coerce"),
                    pd.to_numeric(controls[other], errors="coerce"),
                    rtol=0.0,
                    atol=1e-9,
                )
            if not bool(np.asarray(equal).all()):
                raise AssertionError(f"H-IBQDYN1 control/source mismatch: {column}")
            controls = controls.drop(columns=other)
    levels = controls["nearest_level_name"].astype(str)
    if not levels.isin(LEVEL_DISTANCE_COLUMNS).all():
        raise AssertionError("H-IBQDYN1 selected an unknown IB/Fibonacci level")
    distance = pd.Series(np.nan, index=controls.index, dtype=float)
    for level, column in LEVEL_DISTANCE_COLUMNS.items():
        mask = levels.eq(level)
        distance.loc[mask] = pd.to_numeric(controls.loc[mask, column], errors="coerce")
    numeric = controls[["spot", "nearest_level_abs_bps", "ret_1m_bps", "ret_5m_bps", "ret_15m_bps", "ret_30m_bps"]].apply(
        pd.to_numeric, errors="coerce"
    )
    if (
        not np.isfinite(numeric.to_numpy(dtype=float)).all()
        or not np.isfinite(distance.to_numpy(dtype=float)).all()
        or not np.allclose(
            distance.abs().to_numpy(dtype=float),
            numeric["nearest_level_abs_bps"].to_numpy(dtype=float),
            rtol=0.0,
            atol=1e-6,
        )
    ):
        raise AssertionError("H-IBQDYN1 selected-level geometry is not exact")
    controls["wall_identity"] = levels
    controls["wall_role"] = np.where(levels.isin(RESISTANCE_LEVELS), "resistance", "support")
    controls["candidate_right"] = np.where(controls["wall_role"].eq("resistance"), "CALL", "PUT")
    controls["candidate_distance_bps"] = distance
    controls["candidate_abs_distance_bps"] = distance.abs()
    controls["candidate_wall_strike"] = controls["spot"] * (1.0 - distance / 10_000.0)
    controls["role_resistance"] = controls["wall_role"].eq("resistance").astype(float)
    controls["minute_sin"] = np.sin(2.0 * np.pi * controls["minute"].astype(float) / 1440.0)
    controls["minute_cos"] = np.cos(2.0 * np.pi * controls["minute"].astype(float) / 1440.0)
    controls["spot_ret_1m_bps"] = numeric["ret_1m_bps"]
    controls["spot_abs_ret_1m_bps"] = numeric["ret_1m_bps"].abs()
    for lag in (5, 15, 30):
        ret = numeric[f"ret_{lag}m_bps"]
        prior_spot = controls["spot"] / (1.0 + ret / 10_000.0)
        prior_distance = (
            (prior_spot - controls["candidate_wall_strike"]) / controls["spot"] * 10_000.0
        )
        controls[f"spot_ret_{lag}m_bps"] = ret
        controls[f"candidate_distance_change_{lag}m_bps"] = distance - prior_distance
        controls[f"candidate_approach_{lag}m_bps"] = prior_distance.abs() - distance.abs()
    controls["episode_id"] = controls["event_id"].astype(str)
    return controls


def attach_realized_volatility(
    controls: pd.DataFrame, source_hashes_path: str | Path, workers: int
) -> pd.DataFrame:
    if sha256_file(source_hashes_path) != EXPECTED_UNDERLYING_INVENTORY_SHA256:
        raise AssertionError("H-IBQDYN1 underlying inventory hash mismatch")
    source_hashes = pd.read_csv(source_hashes_path, dtype={"trade_date": str})
    assert_source_inventory(source_hashes)
    underlying = source_hashes[source_hashes["source_kind"].astype(str).eq("underlying")].copy()
    if len(underlying) != EXPECTED_SESSION_COUNT or underlying.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("H-IBQDYN1 underlying session inventory changed")
    source_map = {
        (str(row.ticker).upper(), str(row.trade_date)): row._asdict()
        for row in underlying.itertuples(index=False)
    }
    tasks: list[tuple[pd.DataFrame, dict[str, Any]]] = []
    for key, part in controls.groupby(["ticker", "trade_date"], observed=True, sort=True):
        source = source_map.get((str(key[0]).upper(), str(key[1])))
        if source is None:
            raise AssertionError(f"missing H-IBQDYN1 underlying source: {key}")
        tasks.append((part.copy(), source))
    frames: list[pd.DataFrame] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_attach_session_rv, part, source): (part.iloc[0]["ticker"], part.iloc[0]["trade_date"]) for part, source in tasks}
        for count, future in enumerate(as_completed(futures), start=1):
            key = futures[future]
            try:
                frames.append(future.result())
            except Exception as exc:
                raise AssertionError(f"H-IBQDYN1 RV session failed {key}: {exc}") from exc
            if count % 100 == 0 or count == len(futures):
                print(f"[H-IBQDYN1_DATA:RV] sessions={count}/{len(futures)}", flush=True)
    out = pd.concat(frames, ignore_index=True).sort_values(
        ["ticker", "trade_date", "decision_dt"], kind="stable"
    ).reset_index(drop=True)
    if len(out) != EXPECTED_EVENTS or out["event_id"].duplicated().any():
        raise AssertionError("H-IBQDYN1 RV join changed event universe")
    return out


def _attach_session_rv(part: pd.DataFrame, source: dict[str, Any]) -> pd.DataFrame:
    path = Path(str(source["path"]))
    expected_hash = str(source["sha256"])
    if sha256_file(path) != expected_hash:
        raise AssertionError("underlying source hash mismatch before H-IBQDYN1 RV")
    raw = pd.read_parquet(path)
    validate_underlying_session(
        raw,
        expected_ticker=str(source["ticker"]),
        expected_trade_date=str(source["trade_date"]),
    )
    out = attach_completed_underlying_controls(
        part,
        raw,
        expected_trade_date=str(source["trade_date"]),
    )
    if sha256_file(path) != expected_hash:
        raise AssertionError("underlying source changed during H-IBQDYN1 RV")
    return out


def validate_capture(
    capture_root: str | Path, controls: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, Any]]:
    root = Path(capture_root)
    seal_path = root / "_seal" / "manifest.json"
    index_path = root / "_seal" / "contract_index.csv"
    candidate_path = root / "candidate_contracts.csv"
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    expected_capture_hashes = {
        relative: sha256_file(PROJECT_ROOT / relative) for relative in CAPTURE_CODE_CLOSURE
    }
    if (
        seal.get("schema") != "h_ibqdyn1_full_capture_seal_v1"
        or seal.get("status") != "PASS_H_IBQDYN1_FULL_CAPTURE"
        or seal.get("outcome_free") is not True
        or seal.get("holdout_2026_used") is not False
        or seal.get("production_modified") is not False
        or not commit_is_ancestor(str(seal.get("git_commit", "")))
        or seal.get("code_hashes") != expected_capture_hashes
        or seal.get("proof_manifest_sha256") != EXPECTED_PROOF_MANIFEST_SHA256
        or seal.get("proof_sha256") != EXPECTED_PROOF_SHA256
        or seal.get("eligible_event_id_sha256") != EXPECTED_ELIGIBLE_ID_SHA256
        or int(seal.get("eligible_events", -1)) != EXPECTED_ELIGIBLE_EVENTS
        or int(seal.get("contracts", -1)) != EXPECTED_FULL_CONTRACTS
        or seal.get("errors") != []
        or seal.get("candidate_contracts_sha256") != sha256_file(candidate_path)
        or seal.get("contract_index_sha256") != sha256_file(index_path)
    ):
        raise AssertionError("H-IBQDYN1 full capture seal contract mismatch")
    index = pd.read_csv(index_path, dtype={"trade_date": str})
    required = {
        "contract_id", "event_id", "ticker", "trade_date", "decision_dt",
        "right", "strike", "raw_path", "raw_sha256", "parquet_path",
        "parquet_sha256", "manifest_path", "manifest_sha256", "rows",
    }
    if required.difference(index.columns):
        raise KeyError(f"H-IBQDYN1 capture index missing: {sorted(required.difference(index.columns))}")
    index["ticker"] = index["ticker"].astype(str).str.upper()
    index["trade_date"] = _normalized_day(index["trade_date"])
    index["right"] = index["right"].astype(str).str.upper()
    index["decision_dt"] = pd.to_datetime(index["decision_dt"], errors="coerce")
    counts = index.groupby("event_id", observed=True)["right"].agg(lambda values: sorted(values.astype(str).tolist()))
    eligible_ids = controls.loc[controls["causal_subscription_eligible"].astype(bool), "event_id"].astype(str)
    if (
        len(index) != EXPECTED_FULL_CONTRACTS
        or index["contract_id"].duplicated().any()
        or index["decision_dt"].isna().any()
        or index["trade_date"].ge("20260101").any()
        or set(index["event_id"].astype(str)) != set(eligible_ids)
        or not counts.map(lambda rights: rights == ["CALL", "PUT"]).all()
        or line_hash(index["event_id"].astype(str).drop_duplicates().tolist()) != EXPECTED_ELIGIBLE_ID_SHA256
    ):
        raise AssertionError("H-IBQDYN1 capture index universe changed")
    return index, seal


def _empty_measurements(eligible: bool) -> dict[str, Any]:
    values: dict[str, Any] = {field: np.nan for field in ALPHA_FIELDS}
    for field in QUALITY_FIELDS:
        if field.endswith("_valid") or field in {"causal_subscription_eligible", "ibqdyn_both_valid"}:
            values[field] = False
        elif field not in {"causal_subscription_eligible", "ibqdyn_both_valid"}:
            values[field] = 0
    values["causal_subscription_eligible"] = bool(eligible)
    return values


def _build_event_measurements(
    candidate: dict[str, Any], rows: list[dict[str, Any]], seal: dict[str, Any]
) -> dict[str, Any]:
    eligible = bool(candidate["causal_subscription_eligible"])
    if not eligible:
        if rows:
            raise AssertionError("ineligible H-IBQDYN1 event acquired capture rows")
        return {"event_id": str(candidate["event_id"]), **_empty_measurements(False)}
    if len(rows) != 2 or {str(row["right"]).upper() for row in rows} != {"CALL", "PUT"}:
        raise AssertionError("eligible H-IBQDYN1 event lacks exact two rights")
    tick_parts: dict[str, pd.DataFrame] = {}
    for row in rows:
        right = str(row["right"]).upper()
        expected_strike = float(candidate["call_strike" if right == "CALL" else "put_strike"])
        for path_field, hash_field in (
            ("raw_path", "raw_sha256"),
            ("parquet_path", "parquet_sha256"),
            ("manifest_path", "manifest_sha256"),
        ):
            if sha256_file(row[path_field]) != str(row[hash_field]):
                raise AssertionError(f"H-IBQDYN1 contract source hash mismatch: {path_field}")
        manifest = json.loads(Path(str(row["manifest_path"])).read_text(encoding="utf-8"))
        source = manifest.get("source_provenance", {})
        source_identity = seal.get("source_identity", {})
        if (
            manifest.get("status") != "PASS_H_IBQDYN1_PREFLIGHT_CONTRACT"
            or manifest.get("outcome_free") is not True
            or manifest.get("holdout_2026_used") is not False
            or manifest.get("production_modified") is not False
            or manifest.get("contract_id") != str(row["contract_id"])
            or manifest.get("event_id") != str(candidate["event_id"])
            or manifest.get("ticker") != str(candidate["ticker"])
            or manifest.get("trade_date") != str(candidate["trade_date"])
            or manifest.get("right") != right
            or float(manifest.get("strike", np.nan)) != expected_strike
            or pd.Timestamp(manifest.get("decision_dt")) != pd.Timestamp(candidate["decision_dt"])
            or manifest.get("raw_sha256") != str(row["raw_sha256"])
            or manifest.get("parquet_sha256") != str(row["parquet_sha256"])
            or manifest.get("code_hashes") != seal.get("code_hashes")
            or manifest.get("runtime_lock_sha256") != seal.get("runtime_lock_sha256")
            or manifest.get("runtime_environment_sha256") != seal.get("runtime_environment_sha256")
            or any(source.get(field) != source_identity.get(field) for field in source_identity)
        ):
            raise AssertionError("H-IBQDYN1 contract manifest mismatch")
        ticks = pd.read_parquet(row["parquet_path"])
        if (
            len(ticks) != int(row["rows"])
            or len(ticks) != int(manifest.get("rows", -1))
            or set(ticks["event_id"].astype(str).unique()) != {str(candidate["event_id"])}
            or set(ticks["ticker"].astype(str).str.upper().unique()) != {str(candidate["ticker"])}
            or set(ticks["right"].astype(str).str.upper().unique()) != {right}
            or set(pd.to_numeric(ticks["strike"], errors="coerce").unique()) != {expected_strike}
        ):
            raise AssertionError("H-IBQDYN1 contract parquet identity mismatch")
        tick_parts[right] = ticks
    values = event_features(
        tick_parts["CALL"], tick_parts["PUT"], pd.Timestamp(candidate["decision_dt"])
    )
    values["causal_subscription_eligible"] = True
    values["ibqdyn_both_valid"] = bool(
        values["ibqdyn_call_valid"] and values["ibqdyn_put_valid"]
    )
    return {"event_id": str(candidate["event_id"]), **values}


def build_measurements(
    controls: pd.DataFrame, index: pd.DataFrame, seal: dict[str, Any], workers: int
) -> pd.DataFrame:
    grouped = {
        str(event): part.to_dict("records")
        for event, part in index.groupby("event_id", observed=True, sort=False)
    }
    outputs: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _build_event_measurements,
                row,
                grouped.get(str(row["event_id"]), []),
                seal,
            ): str(row["event_id"])
            for row in controls.to_dict("records")
        }
        for count, future in enumerate(as_completed(futures), start=1):
            event = futures[future]
            try:
                outputs.append(future.result())
            except Exception as exc:
                raise AssertionError(f"H-IBQDYN1 feature event failed {event}: {exc}") from exc
            if count % 100 == 0 or count == len(futures):
                print(f"[H-IBQDYN1_DATA:FEATURE] events={count}/{len(futures)}", flush=True)
    frame = pd.DataFrame(outputs)
    if len(frame) != EXPECTED_EVENTS or frame["event_id"].duplicated().any():
        raise AssertionError("H-IBQDYN1 measurement cardinality changed")
    return frame


def data_gate_profile(dataset: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    work = dataset.copy()
    work["year"] = work["trade_date"].astype(str).str[:4]
    coverage_rows: list[dict[str, Any]] = []
    for (ticker, year), part in work.groupby(["ticker", "year"], observed=True, sort=True):
        valid = part["ibqdyn_both_valid"].astype(bool)
        coverage_rows.append(
            {"scope": "ticker_year", "ticker": ticker, "year": year, "events": len(part), "eligible": int(part["causal_subscription_eligible"].sum()), "both_valid": int(valid.sum()), "coverage": float(valid.mean())}
        )
    for ticker, part in work.groupby("ticker", observed=True, sort=True):
        valid = part["ibqdyn_both_valid"].astype(bool)
        coverage_rows.append(
            {"scope": "ticker", "ticker": ticker, "year": "ALL", "events": len(part), "eligible": int(part["causal_subscription_eligible"].sum()), "both_valid": int(valid.sum()), "coverage": float(valid.mean())}
        )
    coverage = pd.DataFrame(coverage_rows)
    distinct_rows: list[dict[str, Any]] = []
    for (ticker, year), part in work.groupby(["ticker", "year"], observed=True, sort=True):
        valid_part = part[part["ibqdyn_both_valid"].astype(bool)]
        for feature in ALPHA_FIELDS:
            values = pd.to_numeric(valid_part[feature], errors="coerce")
            finite = values[np.isfinite(values)]
            distinct_rows.append(
                {"ticker": ticker, "year": year, "feature": feature, "both_valid_rows": len(valid_part), "finite": len(finite), "distinct_finite": int(finite.nunique()), "minimum": float(finite.min()) if len(finite) else np.nan, "maximum": float(finite.max()) if len(finite) else np.nan}
            )
    distinct = pd.DataFrame(distinct_rows)
    annual = coverage[coverage["scope"].eq("ticker_year")]
    ticker = coverage[coverage["scope"].eq("ticker")]
    f0 = work[list(CONTROL_FEATURES)].apply(pd.to_numeric, errors="coerce")
    alpha = work[list(ALPHA_FIELDS)].apply(pd.to_numeric, errors="coerce")
    finite_f0 = np.isfinite(f0.to_numpy(dtype=float)).all(axis=1)
    finite_alpha = np.isfinite(alpha.to_numpy(dtype=float)).all(axis=1)
    complete = work["ibqdyn_both_valid"].astype(bool).to_numpy()
    gate = {
        "rows_preserved": bool(len(work) == EXPECTED_EVENTS and not work["event_id"].duplicated().any()),
        "coverage_pass": bool(annual["coverage"].ge(MIN_ANNUAL_BOTH_VALID_COVERAGE).all() and ticker["coverage"].ge(MIN_TICKER_BOTH_VALID_COVERAGE).all()),
        "distinctness_pass": bool(len(distinct) == 12 * len(ALPHA_FIELDS) and distinct["distinct_finite"].ge(2).all()),
        "control_coverage_pass": bool(finite_f0.all()),
        "identical_complete_case_pass": bool(np.array_equal(complete, finite_f0 & finite_alpha)),
        "minimum_annual_both_valid_coverage": float(annual["coverage"].min()),
        "minimum_ticker_both_valid_coverage": float(ticker["coverage"].min()),
        "minimum_feature_distinctness": int(distinct["distinct_finite"].min()) if len(distinct) else 0,
    }
    gate["passed"] = bool(all(gate[name] for name in ("rows_preserved", "coverage_pass", "distinctness_pass", "control_coverage_pass", "identical_complete_case_pass")))
    return coverage, distinct, gate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True)
    parser.add_argument("--capture-root", required=True)
    parser.add_argument("--underlying-source-hashes", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=16)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= int(args.workers) <= 16:
        raise ValueError("H-IBQDYN1 data-gate workers must be within 1..16")
    output = Path(args.output_dir)
    staging = output.with_name(output.name + ".staging")
    if output.exists() or staging.exists():
        raise FileExistsError("immutable H-IBQDYN1 data-gate output exists")
    commit, code_hashes = committed_code_state()
    runtime = assert_runtime_lock(PROJECT_ROOT / RUNTIME_LOCK)
    controls = load_control_universe(args.events)
    proof = pd.read_parquet(PROJECT_ROOT / PROOF_PATH)
    proof["event_id"] = proof["event_id"].astype(str)
    proof["causal_subscription_eligible"] = proof["causal_subscription_eligible"].astype(bool)
    if (
        sha256_file(PROJECT_ROOT / PROOF_PATH) != EXPECTED_PROOF_SHA256
        or len(proof) != EXPECTED_EVENTS
        or proof["event_id"].duplicated().any()
        or set(proof["event_id"]) != set(controls["event_id"].astype(str))
    ):
        raise AssertionError("H-IBQDYN1 listing proof changed before data gate")
    controls = controls.drop(columns=["causal_subscription_eligible"], errors="ignore").merge(
        proof[["event_id", "causal_subscription_eligible"]],
        on="event_id",
        how="left",
        validate="one_to_one",
    )
    if controls["causal_subscription_eligible"].isna().any():
        raise AssertionError("H-IBQDYN1 proof eligibility join incomplete")
    controls = attach_realized_volatility(
        controls, args.underlying_source_hashes, int(args.workers)
    )
    index, seal = validate_capture(args.capture_root, controls)
    measurements = build_measurements(controls, index, seal, int(args.workers))
    dataset = controls.merge(measurements, on="event_id", how="left", validate="one_to_one")
    keep = [*OUTPUT_IDENTITY_COLUMNS, *CONTROL_FEATURES, *ALPHA_FIELDS, *QUALITY_FIELDS]
    missing = sorted(set(keep).difference(dataset.columns))
    if missing:
        raise KeyError(f"H-IBQDYN1 final dataset missing: {missing}")
    dataset = dataset[keep].sort_values(
        ["ticker", "trade_date", "decision_dt"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(dataset) != EXPECTED_EVENTS
        or dataset["event_id"].duplicated().any()
        or dataset["trade_date"].astype(str).str.startswith("2026").any()
        or dataset.groupby("ticker").size().astype(int).to_dict() != EXPECTED_BY_TICKER
    ):
        raise AssertionError("H-IBQDYN1 final outcome-free universe changed")
    coverage, distinct, gate = data_gate_profile(dataset)
    staging.mkdir(parents=True, exist_ok=False)
    dataset_path = staging / "h_ibqdyn1_features.parquet"
    coverage_path = staging / "coverage.csv"
    distinct_path = staging / "feature_profile.csv"
    source_path = staging / "contract_source_hashes.csv"
    schema_path = staging / "schema.json"
    dataset.to_parquet(dataset_path, index=False)
    coverage.to_csv(coverage_path, index=False)
    distinct.to_csv(distinct_path, index=False)
    index.to_csv(source_path, index=False)
    schema_path.write_bytes(
        canonical_bytes(
            {"columns": [{"name": name, "dtype": str(dtype)} for name, dtype in dataset.dtypes.items()]}
        )
    )
    manifest = {
        "schema": "h_ibqdyn1_outcome_free_dataset_v1",
        "status": "PASS_DATA_GATE" if gate["passed"] else "REJECTED_DATA_GATE",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "code_hashes": code_hashes,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "event_source_sha256": sha256_file(args.events),
        "proof_manifest_sha256": sha256_file(PROJECT_ROOT / PROOF_MANIFEST),
        "proof_sha256": sha256_file(PROJECT_ROOT / PROOF_PATH),
        "underlying_source_inventory_sha256": sha256_file(args.underlying_source_hashes),
        "capture_seal_sha256": sha256_file(Path(args.capture_root) / "_seal" / "manifest.json"),
        "capture_index_sha256": sha256_file(Path(args.capture_root) / "_seal" / "contract_index.csv"),
        "capture_git_commit": seal["git_commit"],
        "capture_code_hashes": seal["code_hashes"],
        "historical_provenance": seal["source_identity"]["historical_provenance"],
        "live_parity": seal["source_identity"]["live_parity"],
        "rows": int(len(dataset)),
        "columns": int(len(dataset.columns)),
        "rows_by_ticker": dataset.groupby("ticker").size().astype(int).to_dict(),
        "eligible_events": int(dataset["causal_subscription_eligible"].sum()),
        "both_valid_events": int(dataset["ibqdyn_both_valid"].sum()),
        "control_features": list(CONTROL_FEATURES),
        "control_feature_hash": hash_list(CONTROL_FEATURES),
        "alpha_features": list(ALPHA_FIELDS),
        "alpha_feature_hash": hash_list(ALPHA_FIELDS),
        "quality_fields": list(QUALITY_FIELDS),
        "quality_field_hash": hash_list(QUALITY_FIELDS),
        "dataset_path": str(output / dataset_path.name),
        "dataset_sha256": sha256_file(dataset_path),
        "coverage_sha256": sha256_file(coverage_path),
        "feature_profile_sha256": sha256_file(distinct_path),
        "source_inventory_sha256": sha256_file(source_path),
        "schema_sha256": sha256_file(schema_path),
        "data_gate": gate,
        "errors": [],
    }
    (staging / "manifest.json").write_bytes(canonical_bytes(manifest))
    staging.rename(output)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
