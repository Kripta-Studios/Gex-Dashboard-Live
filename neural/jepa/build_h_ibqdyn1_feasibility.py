"""Build the outcome-free H-IBQDYN1 universe and exact t-5m listing proof."""

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
from neural.jepa.surface_flow_features import (  # noqa: E402
    underlying_market_close_minute,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402

EXPECTED_SOURCE_SHA256 = (
    "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408"
)
EXPECTED_SOURCE_ROWS = 97_625
EXPECTED_EVENTS = 16_926
EXPECTED_BY_TICKER = {"QQQ": 5_408, "SPXW": 5_858, "SPY": 5_660}
EXPECTED_SESSIONS = 2_519
EXPECTED_SAMPLE = {
    ("QQQ", "2022"): ("20220801", 645),
    ("QQQ", "2023"): ("20230103", 635),
    ("QQQ", "2024"): ("20240102", 635),
    ("QQQ", "2025"): ("20250102", 665),
    ("SPXW", "2022"): ("20220801", 645),
    ("SPXW", "2023"): ("20230103", 635),
    ("SPXW", "2024"): ("20240102", 635),
    ("SPXW", "2025"): ("20250102", 635),
    ("SPY", "2022"): ("20220801", 645),
    ("SPY", "2023"): ("20230103", 635),
    ("SPY", "2024"): ("20240102", 635),
    ("SPY", "2025"): ("20250102", 635),
}
BUCKETS = {"SPXW": "d25", "QQQ": "d35", "SPY": "d35"}
CAPS = {"SPXW": 4, "QQQ": 2, "SPY": 1}
LEVELS = {
    "ib_high",
    "ib_low",
    "fib_127_up",
    "fib_161_up",
    "fib_200_up",
    "fib_127_dn",
    "fib_161_dn",
    "fib_200_dn",
}
SOURCE_COLUMNS = (
    "ticker",
    "trade_date",
    "expiration",
    "dte_days",
    "expiry_mode",
    "option_price_mode",
    "timestamp",
    "minute",
    "spot",
    "nearest_level_name",
    "nearest_level_abs_bps",
    "call_d25_available",
    "call_d25_strike",
    "put_d25_available",
    "put_d25_strike",
    "call_d35_available",
    "call_d35_strike",
    "put_d35_available",
    "put_d35_strike",
)
QUOTE_COLUMNS = ("symbol", "expiration", "timestamp", "strike", "right")
PREDECLARATION = "research_papers/JEPA/H_IBQDYN1_FEASIBILITY_PREDECLARATION.md"
RUNTIME_LOCK = "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
CODE_CLOSURE = (
    "neural/jepa/build_h_ibqdyn1_feasibility.py",
    "neural/jepa/build_wall_quote_size_pressure_dataset.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    "neural/jepa/build_wall_quote_size_complement_sidecar.py",
    "neural/jepa/surface_flow_features.py",
    "neural/jepa/wall_surface_flow_environment.py",
    PREDECLARATION,
    RUNTIME_LOCK,
)


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def line_hash(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def normalized_day(value: Any) -> str:
    return "".join(char for char in str(value) if char.isdigit())[:8]


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
            raise AssertionError(f"H-IBQDYN1 feasibility requires clean code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, hashes


def event_id(row: dict[str, Any]) -> str:
    identity = "|".join(
        (
            str(row["ticker"]).upper(),
            str(row["trade_date"]),
            pd.Timestamp(row["decision_dt"]).isoformat(),
            str(row["nearest_level_name"]),
            f"{float(row['call_strike']):.6f}",
            f"{float(row['put_strike']):.6f}",
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def _normalize_source_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(SOURCE_COLUMNS).difference(frame.columns))
    if missing:
        raise KeyError(f"H-IBQDYN1 source missing causal columns: {missing}")
    out = frame[list(SOURCE_COLUMNS)].copy()
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["trade_date"] = out["trade_date"].map(normalized_day)
    out["expiration"] = out["expiration"].map(normalized_day)
    out["decision_dt"] = pd.to_datetime(out.pop("timestamp"), errors="coerce")
    for column in (
        "dte_days",
        "minute",
        "spot",
        "nearest_level_abs_bps",
        "call_d25_strike",
        "put_d25_strike",
        "call_d35_strike",
        "put_d35_strike",
    ):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if (
        len(out) != EXPECTED_SOURCE_ROWS
        or out["decision_dt"].isna().any()
        or out["trade_date"].str.startswith("2026").any()
        or not out["ticker"].isin(BUCKETS).all()
        or not out["expiration"].eq(out["trade_date"]).all()
        or not out["dte_days"].eq(0).all()
        or not out["expiry_mode"].astype(str).eq("zero_dte").all()
        or not out["option_price_mode"].astype(str).eq("executable_quote").all()
        or not out["decision_dt"].dt.strftime("%Y%m%d").eq(out["trade_date"]).all()
        or not out["decision_dt"].dt.hour.mul(60).add(out["decision_dt"].dt.minute).eq(
            out["minute"]
        ).all()
    ):
        raise AssertionError("invalid sealed H-IBQDYN1 causal source")
    return out


def load_opportunity_universe(path: str | Path) -> pd.DataFrame:
    if sha256_file(path) != EXPECTED_SOURCE_SHA256:
        raise AssertionError("H-IBQDYN1 executable source hash mismatch")
    frame = _normalize_source_frame(pd.read_parquet(path, columns=list(SOURCE_COLUMNS)))
    frame = frame[
        frame["trade_date"].between("20220801", "20251231")
        & frame["minute"].ge(635)
    ].copy()
    frame["underlying_close_minute"] = [
        underlying_market_close_minute(day) for day in frame["trade_date"]
    ]
    latest = np.where(frame["underlying_close_minute"].eq(780), 750, 870)
    frame = frame[frame["minute"].le(latest)].copy()
    if (
        not frame["nearest_level_name"].astype(str).isin(LEVELS).all()
        or frame["nearest_level_abs_bps"].isna().any()
        or not frame["nearest_level_abs_bps"].le(20.0 + 1e-6).all()
        or not np.isfinite(frame["spot"]).all()
        or not frame["spot"].gt(0).all()
        or not frame["minute"].mod(5).eq(0).all()
    ):
        raise AssertionError("H-IBQDYN1 source violates fixed level/grid contract")
    frame["clock_block"] = ((frame["minute"] - 635) // 30).astype(int)
    frame = (
        frame.sort_values(["ticker", "trade_date", "minute"], kind="stable")
        .drop_duplicates(["ticker", "trade_date", "clock_block"], keep="first")
        .reset_index(drop=True)
    )
    frame["bucket"] = frame["ticker"].map(BUCKETS)
    frame["call_available"] = False
    frame["put_available"] = False
    frame["call_strike"] = np.nan
    frame["put_strike"] = np.nan
    for ticker, bucket in BUCKETS.items():
        mask = frame["ticker"].eq(ticker)
        frame.loc[mask, "call_available"] = frame.loc[
            mask, f"call_{bucket}_available"
        ].astype(bool)
        frame.loc[mask, "put_available"] = frame.loc[
            mask, f"put_{bucket}_available"
        ].astype(bool)
        frame.loc[mask, "call_strike"] = frame.loc[mask, f"call_{bucket}_strike"]
        frame.loc[mask, "put_strike"] = frame.loc[mask, f"put_{bucket}_strike"]
    if (
        len(frame) != EXPECTED_EVENTS
        or frame.groupby("ticker").size().astype(int).to_dict() != EXPECTED_BY_TICKER
        or not frame["call_available"].all()
        or not frame["put_available"].all()
        or not np.isfinite(frame[["call_strike", "put_strike"]]).all().all()
        or not frame[["call_strike", "put_strike"]].gt(0).all().all()
        or frame.duplicated(["ticker", "trade_date", "decision_dt"]).any()
    ):
        raise AssertionError("H-IBQDYN1 frozen opportunity universe changed")
    frame["subscription_dt"] = frame["decision_dt"] - pd.Timedelta(minutes=5)
    frame["event_id"] = [event_id(row) for row in frame.to_dict("records")]
    if frame["event_id"].duplicated().any():
        raise AssertionError("H-IBQDYN1 event-id collision")
    frame["year"] = frame["trade_date"].str[:4]
    sample = (
        frame.sort_values(["ticker", "year", "trade_date", "minute"], kind="stable")
        .drop_duplicates(["ticker", "year"], keep="first")
        .copy()
    )
    observed_sample = {
        (row.ticker, row.year): (row.trade_date, int(row.minute))
        for row in sample.itertuples(index=False)
    }
    if observed_sample != EXPECTED_SAMPLE:
        raise AssertionError("H-IBQDYN1 frozen preflight sample changed")
    sample_ids = set(sample["event_id"].astype(str))
    frame["preflight_sample"] = frame["event_id"].astype(str).isin(sample_ids)
    keep = (
        "event_id",
        "ticker",
        "trade_date",
        "year",
        "decision_dt",
        "subscription_dt",
        "minute",
        "clock_block",
        "spot",
        "nearest_level_name",
        "nearest_level_abs_bps",
        "bucket",
        "call_strike",
        "put_strike",
        "preflight_sample",
    )
    return frame[list(keep)].sort_values(
        ["ticker", "trade_date", "decision_dt"], kind="stable"
    ).reset_index(drop=True)


def frequency_capacity(frame: pd.DataFrame, *, eligible_only: bool) -> pd.DataFrame:
    work = frame.copy()
    if eligible_only:
        work = work[work["causal_subscription_eligible"].astype(bool)].copy()
    daily_rows: list[dict[str, Any]] = []
    for (ticker, day), part in work.groupby(["ticker", "trade_date"], sort=True):
        chosen: list[int] = []
        last = -10_000
        for minute in sorted(part["minute"].astype(int).unique()):
            if minute - last >= 30 and len(chosen) < CAPS[str(ticker)]:
                chosen.append(minute)
                last = minute
        daily_rows.append(
            {
                "ticker": str(ticker),
                "trade_date": str(day),
                "month": str(day)[:6],
                "candidate_events": int(len(part)),
                "max_trades_30m_cap": int(len(chosen)),
            }
        )
    daily = pd.DataFrame(daily_rows)
    if daily.empty:
        return pd.DataFrame(
            columns=[
                "ticker",
                "month",
                "candidate_events",
                "active_days",
                "max_trades_30m_cap",
            ]
        )
    return (
        daily.groupby(["ticker", "month"], as_index=False)
        .agg(
            candidate_events=("candidate_events", "sum"),
            active_days=("trade_date", "nunique"),
            max_trades_30m_cap=("max_trades_30m_cap", "sum"),
        )
        .sort_values(["ticker", "month"], kind="stable")
        .reset_index(drop=True)
    )


def _read_quote_listing(path: str | Path) -> pd.DataFrame:
    names = set(pq.ParquetFile(path).schema_arrow.names)
    missing = sorted(set(QUOTE_COLUMNS).difference(names))
    if missing:
        raise KeyError(f"native quote snapshot lacks H-IBQDYN1 fields: {missing}")
    frame = pd.read_parquet(path, columns=list(QUOTE_COLUMNS))
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    frame["expiration"] = frame["expiration"].map(normalized_day)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame["strike"] = pd.to_numeric(frame["strike"], errors="coerce")
    frame["right"] = (
        frame["right"].astype(str).str.upper().replace({"CALL": "C", "PUT": "P"})
    )
    if frame["timestamp"].isna().any():
        raise AssertionError("native quote snapshot has invalid H-IBQDYN1 clock")
    return frame


def audit_session(
    source: dict[str, Any], candidates: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if sha256_file(source["quotes_path"]) != str(source["quotes_sha256"]):
        raise AssertionError("native quote parquet hash mismatch")
    if sha256_file(source["session_manifest_path"]) != str(
        source["session_manifest_sha256"]
    ):
        raise AssertionError("native quote session-manifest hash mismatch")
    quotes = _read_quote_listing(source["quotes_path"])
    quotes = quotes[
        quotes["symbol"].eq(str(source["ticker"]))
        & quotes["expiration"].eq(str(source["trade_date"]))
        & quotes["right"].isin(["C", "P"])
        & np.isfinite(quotes["strike"])
    ][["timestamp", "strike", "right"]].drop_duplicates()
    records: list[dict[str, Any]] = []
    for row in candidates.itertuples(index=False):
        at_time = quotes[quotes["timestamp"].eq(row.subscription_dt)]
        listed = set(zip(at_time["strike"].astype(float), at_time["right"].astype(str)))
        call = (float(row.call_strike), "C") in listed
        put = (float(row.put_strike), "P") in listed
        covered = not at_time.empty
        eligible = call and put
        if eligible:
            reason = "eligible"
        elif not covered:
            reason = "subscription_timestamp_not_covered"
        elif not call and not put:
            reason = "both_execution_contracts_not_listed"
        elif not call:
            reason = "call_execution_contract_not_listed"
        else:
            reason = "put_execution_contract_not_listed"
        records.append(
            {
                "event_id": row.event_id,
                "ticker": row.ticker,
                "trade_date": row.trade_date,
                "year": row.year,
                "decision_dt": row.decision_dt,
                "subscription_dt": row.subscription_dt,
                "minute": int(row.minute),
                "nearest_level_name": row.nearest_level_name,
                "bucket": row.bucket,
                "call_strike": float(row.call_strike),
                "put_strike": float(row.put_strike),
                "preflight_sample": bool(row.preflight_sample),
                "subscription_timestamp_covered": covered,
                "full_chain_contracts_tminus5m": int(len(listed)),
                "exact_call_listed_tminus5m": call,
                "exact_put_listed_tminus5m": put,
                "causal_subscription_eligible": eligible,
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
        "quote_listing_rows": int(len(quotes)),
        "candidate_events": int(len(candidates)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True)
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
        raise ValueError("H-IBQDYN1 feasibility workers must be within 1..32")
    output = Path(args.output_dir)
    staging = output.with_name(output.name + ".staging")
    if output.exists() or staging.exists():
        raise FileExistsError("immutable H-IBQDYN1 feasibility output already exists")
    commit, code_hashes = committed_code_state()
    runtime = assert_runtime_lock(PROJECT_ROOT / RUNTIME_LOCK)
    candidates = load_opportunity_universe(args.events)
    source_frequency = frequency_capacity(candidates, eligible_only=False)
    combined, sidecar_provenance = load_combined_quote_index(
        args.fallback_index,
        args.fallback_seal,
        args.complement_index,
        args.complement_seal,
    )
    if len(combined) != EXPECTED_SESSIONS:
        raise AssertionError("H-IBQDYN1 requires all 2,519 native quote sessions")
    outputs: list[pd.DataFrame] = []
    inventories: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ProcessPoolExecutor(max_workers=int(args.workers)) as pool:
        futures = {}
        for source in combined.to_dict("records"):
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
                    f"[H-IBQDYN1_LISTING] sessions={count}/{len(futures)} "
                    f"errors={len(errors)}",
                    flush=True,
                )
    if errors:
        raise AssertionError(f"H-IBQDYN1 listing audit failed: {errors[:10]}")
    proof = pd.concat(outputs, ignore_index=True).sort_values(
        ["ticker", "trade_date", "decision_dt"], kind="stable"
    ).reset_index(drop=True)
    inventory = pd.DataFrame(inventories).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(proof) != EXPECTED_EVENTS
        or proof["event_id"].duplicated().any()
        or set(proof["event_id"]) != set(candidates["event_id"])
        or len(inventory) != EXPECTED_SESSIONS
        or inventory.duplicated(["ticker", "trade_date"]).any()
    ):
        raise AssertionError("H-IBQDYN1 proof cardinality changed")
    eligible_frequency = frequency_capacity(proof, eligible_only=True)
    outer = eligible_frequency[eligible_frequency["month"].between("202401", "202512")]
    frequency_minima = (
        outer.groupby("ticker")["max_trades_30m_cap"].min().astype(int).to_dict()
    )
    frequency_pass = (
        set(frequency_minima) == set(BUCKETS)
        and min(frequency_minima.values(), default=0) >= 18
    )
    sample = proof[proof["preflight_sample"].astype(bool)].copy()
    sample_listing_pass = len(sample) == 12 and sample[
        "causal_subscription_eligible"
    ].all()
    status = (
        "PASS_H_IBQDYN1_LISTING_FEASIBILITY"
        if frequency_pass and sample_listing_pass
        else "REJECTED_H_IBQDYN1_LISTING_FEASIBILITY"
    )
    staging.mkdir(parents=True, exist_ok=False)
    proof_path = staging / "subscription_listing_proof.parquet"
    inventory_path = staging / "source_inventory.csv"
    source_frequency_path = staging / "source_frequency_capacity.csv"
    eligible_frequency_path = staging / "eligible_frequency_capacity.csv"
    sample_path = staging / "preflight_sample.csv"
    proof.to_parquet(proof_path, index=False)
    inventory.to_csv(inventory_path, index=False)
    source_frequency.to_csv(source_frequency_path, index=False)
    eligible_frequency.to_csv(eligible_frequency_path, index=False)
    sample.to_csv(sample_path, index=False)
    eligible = proof[proof["causal_subscription_eligible"].astype(bool)]
    manifest = {
        "schema": "h_ibqdyn1_listing_feasibility_v1",
        "status": status,
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "code_hashes": code_hashes,
        "event_source_path": str(Path(args.events)),
        "event_source_sha256": sha256_file(args.events),
        "events": int(len(proof)),
        "events_by_ticker": proof.groupby("ticker").size().astype(int).to_dict(),
        "event_id_sha256": line_hash(proof["event_id"].astype(str).tolist()),
        "eligible_events": int(len(eligible)),
        "eligible_by_ticker": eligible.groupby("ticker").size().astype(int).to_dict(),
        "eligible_event_id_sha256": line_hash(
            eligible["event_id"].astype(str).tolist()
        ),
        "eligibility_reasons": proof["eligibility_reason"]
        .value_counts()
        .astype(int)
        .to_dict(),
        "preflight_sample_events": int(len(sample)),
        "preflight_sample_listing_pass": bool(sample_listing_pass),
        "frequency_minima_2024_2025": frequency_minima,
        "frequency_capacity_pass": bool(frequency_pass),
        "proof_path": str(output / proof_path.name),
        "proof_sha256": sha256_file(proof_path),
        "source_inventory_path": str(output / inventory_path.name),
        "source_inventory_sha256": sha256_file(inventory_path),
        "source_frequency_path": str(output / source_frequency_path.name),
        "source_frequency_sha256": sha256_file(source_frequency_path),
        "eligible_frequency_path": str(output / eligible_frequency_path.name),
        "eligible_frequency_sha256": sha256_file(eligible_frequency_path),
        "preflight_sample_path": str(output / sample_path.name),
        "preflight_sample_sha256": sha256_file(sample_path),
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
