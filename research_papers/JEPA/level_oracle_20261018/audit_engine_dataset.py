"""Resumable two-worker independent audit of the full level-oracle dataset."""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import traceback

import exchange_calendars as xc
import pandas as pd

import audit_engine as audit

TICKERS = ("SPXW", "SPY", "QQQ")


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".partial")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)


def expected_cases():
    calendar = xc.get_calendar("XNYS").schedule.loc["2023-01-03":"2026-06-30"].copy()
    full = calendar.loc[(calendar.close - calendar.open) == pd.Timedelta(hours=6, minutes=30)]
    dates = full.index.strftime("%Y%m%d").tolist()
    audit.require(len(dates) == 867, "Expected 867 full sessions")
    return [(ticker, date) for ticker in TICKERS for date in dates]


def paths(cache_root, engine_root, audit_root, ticker, date):
    return {
        "cache": cache_root / ticker / f"{date}.npz",
        "engine": engine_root / ticker / date,
        "audit": audit_root / "days" / ticker / f"{date}.json",
    }


def input_identity(path_map):
    return {
        "cache_npz_sha256": audit.digest(path_map["cache"]),
        "cache_meta_sha256": audit.digest(path_map["cache"].with_suffix(".json")),
        "engine_summary_sha256": audit.digest(path_map["engine"] / "summary.json"),
        "causal_freeze_sha256": audit.digest(path_map["engine"] / "causal_freeze.json"),
    }


def audit_one(job):
    started = time.monotonic()
    ticker, date, cache_root, engine_root, audit_root, script_hash = job
    path_map = paths(Path(cache_root), Path(engine_root), Path(audit_root), ticker, date)
    identity = input_identity(path_map)
    try:
        result = audit.audit_case(ticker, date, path_map["cache"], path_map["engine"])
    except Exception as exc:
        raise AssertionError(f"{ticker} {date}: {exc}") from exc
    record = {"status": "PASS", **result, **identity,
              "audit_script_sha256": script_hash,
              "audit_wall_seconds": time.monotonic() - started,
              "finished_at_utc": now()}
    atomic_json(path_map["audit"], record)
    return record


def verify_existing(path_map, script_hash):
    path = path_map["audit"]
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    audit.require(record["status"] == "PASS", "Existing day audit not PASS")
    audit.require(record["audit_script_sha256"] == script_hash, "Auditor changed during resume")
    for key, expected in input_identity(path_map).items():
        audit.require(record[key] == expected, "Audited input changed: " + key)
    return record


def verify_final(engine_root, cache_root, records, missing):
    completion_path = engine_root / "completion.json"
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    audit.require(completion["status"] == "COMPLETE", "Producer dataset incomplete")
    audit.require(audit.digest(engine_root / "index.parquet") == completion["index_sha256"],
                  "Producer index seal")
    audit.require(audit.digest(engine_root / "summary.json") == completion["summary_sha256"],
                  "Producer summary seal")
    index = pd.read_parquet(engine_root / "index.parquet")
    audit.require(len(index) == 2601, "Producer calendar row count")
    audit.require(not index.duplicated(["ticker", "date"]).any(), "Producer index duplicates")
    expected = set(expected_cases())
    actual = set(zip(index.ticker, index.date.astype(str), strict=True))
    audit.require(actual == expected, "Producer index membership")
    audit.require(int((index.status == "COMPLETE").sum()) == 2595, "Producer complete days")
    audit.require(int((index.status == "MISSING_SOURCE").sum()) == 6, "Producer missing days")
    audit.require(set(zip(index.loc[index.status == "MISSING_SOURCE", "ticker"],
                          index.loc[index.status == "MISSING_SOURCE", "date"].astype(str), strict=True))
                  == missing, "Missing-day membership")
    by_key = {(record["ticker"], record["date"]): record for record in records}
    complete = index.loc[index.status == "COMPLETE"]
    for row in complete.itertuples(index=False):
        key = (row.ticker, str(row.date))
        audit.require(key in by_key, "Missing independent day audit")
        record = by_key[key]
        audit.require(record["cache_npz_sha256"] == row.cache_npz_sha256, "Index cache hash")
        audit.require(record["cache_meta_sha256"] == row.cache_meta_sha256, "Index metadata hash")
        audit.require(record["engine_summary_sha256"] == row.summary_sha256, "Index summary hash")
        audit.require(record["causal_freeze_sha256"] == row.causal_freeze_sha256, "Index freeze hash")
        audit.require(record["actions"] == row.actions_count, "Index action count")
        audit.require(record["oracle_trades"] == row.trades, "Index trade count")
        audit.close(record["oracle_net_base"], row.net_base, "Index base net")
        audit.close(record["oracle_net_adverse_same_path"], row.net_adverse, "Index adverse net")
    producer_summary = json.loads((engine_root / "summary.json").read_text(encoding="utf-8"))
    totals = {
        "actions": sum(record["actions"] for record in records),
        "oracle_trades": sum(record["oracle_trades"] for record in records),
        "oracle_net_base": float(sum(record["oracle_net_base"] for record in records)),
        "oracle_net_adverse_same_path": float(
            sum(record["oracle_net_adverse_same_path"] for record in records)
        ),
        "raw_oracle_fills_checked": sum(record["raw_oracle_fills_checked"] for record in records),
        "contracts_and_targets_checked": sum(
            record["contracts_and_targets_checked"] for record in records
        ),
    }
    audit.require(totals["actions"] == producer_summary["all"]["actions"], "Global actions")
    audit.require(totals["oracle_trades"] == producer_summary["all"]["trades"], "Global trades")
    audit.close(totals["oracle_net_base"], producer_summary["all"]["net_base"], "Global base", 1e-6)
    audit.close(totals["oracle_net_adverse_same_path"],
                producer_summary["all"]["net_adverse"], "Global adverse", 1e-6)
    cache_summary = json.loads((cache_root / "full_summary.json").read_text(encoding="utf-8"))
    audit.require(cache_summary["missing_sources"] == 6, "Cache missing coverage")
    return totals, completion


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--engine-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3, 4), default=2)
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    script_hash = audit.digest(Path(__file__).with_name("audit_engine.py"))
    runner_hash = audit.digest(Path(__file__))
    contract = {"version": "INDEPENDENT_LEVEL_ORACLE_DATASET_AUDIT_V1",
                "audit_engine_sha256": script_hash, "audit_runner_sha256": runner_hash,
                "cache_root": str(args.cache_root.resolve()),
                "engine_root": str(args.engine_root.resolve()),
                "expected_calendar_rows": 2601, "expected_complete_days": 2595,
                "expected_missing_days": 6, "full_feature_rebuild": False,
                "oracle_is_hindsight_upper_bound": True}
    contract_path = args.output / "audit_contract.json"
    if contract_path.exists():
        audit.require(json.loads(contract_path.read_text(encoding="utf-8")) == contract,
                      "Audit resume contract changed")
    else:
        atomic_json(contract_path, contract)
    all_cases = expected_cases()
    pending = set(all_cases)
    records = []
    missing = set()
    submitted = set()
    futures = {}
    last_progress = 0.0
    try:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            while pending or futures:
                cache_complete = (args.cache_root / "full_summary.json").exists()
                engine_complete = (args.engine_root / "completion.json").exists()
                if cache_complete:
                    coverage = pd.read_csv(args.cache_root / "full_coverage.csv", dtype={"date": str})
                    missing = set(zip(coverage.loc[coverage.status == "MISSING_SOURCE", "ticker"],
                                      coverage.loc[coverage.status == "MISSING_SOURCE", "date"], strict=True))
                    for key in list(pending & missing):
                        pending.remove(key)
                for ticker, date in sorted(pending):
                    if len(futures) >= args.workers * 2:
                        break
                    key = (ticker, date)
                    if key in submitted:
                        continue
                    path_map = paths(args.cache_root, args.engine_root, args.output, ticker, date)
                    if not (path_map["engine"] / "summary.json").exists():
                        continue
                    existing = verify_existing(path_map, script_hash)
                    if existing is not None:
                        records.append(existing)
                        pending.remove(key)
                        continue
                    job = (ticker, date, str(args.cache_root), str(args.engine_root),
                           str(args.output), script_hash)
                    future = pool.submit(audit_one, job)
                    futures[future] = key
                    submitted.add(key)
                if futures:
                    done, _ = wait(futures, timeout=2, return_when=FIRST_COMPLETED)
                    for future in done:
                        key = futures.pop(future)
                        records.append(future.result())
                        pending.remove(key)
                elif pending:
                    if engine_complete:
                        raise AssertionError("Producer complete with unavailable day audits")
                    time.sleep(args.poll_seconds)
                moment = time.monotonic()
                if moment - last_progress >= 15 or (not pending and not futures):
                    progress = {"status": "RUNNING", "utc": now(), "expected": 2601,
                                "audited": len(records), "missing": len(missing),
                                "pending": len(pending), "inflight": len(futures),
                                "cache_complete": cache_complete, "engine_complete": engine_complete,
                                "runtime_workers": args.workers}
                    if records:
                        progress["mean_audit_wall_seconds"] = float(
                            sum(record["audit_wall_seconds"] for record in records) / len(records)
                        )
                        progress["estimated_remaining_wall_seconds"] = float(
                            progress["mean_audit_wall_seconds"] * len(pending) / args.workers
                        )
                    atomic_json(args.output / "progress.json", progress)
                    print(json.dumps(progress), flush=True)
                    last_progress = moment
        audit.require(len(records) == 2595 and len(missing) == 6, "Final audit coverage")
        totals, producer_completion = verify_final(
            args.engine_root, args.cache_root, records, missing
        )
        dataset_contract = json.loads(
            (args.engine_root / "dataset_contract.json").read_text(encoding="utf-8")
        )
        binding = {"engine_root": str(args.engine_root.resolve()),
                   "engine_sha256": dataset_contract["engine_sha256"],
                   "engine_runner_sha256": dataset_contract["runner_sha256"],
                   "completion_sha256": audit.digest(args.engine_root / "completion.json"),
                   "index_sha256": producer_completion["index_sha256"],
                   "dataset_contract_sha256": audit.digest(args.engine_root / "dataset_contract.json"),
                   "cache_contract_sha256": dataset_contract["cache_contract_sha256"],
                   "cache_full_summary_sha256": producer_completion["cache_full_summary_sha256"],
                   "available_days": len(records), "missing_days": len(missing)}
        result = {"status": "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT",
                  "binding": binding, **binding,
                  "audited_days": len(records), "missing_source_days": len(missing),
                  "source_hash_mismatch": 0, **totals,
                  "audit_day_wall_seconds_sum": float(
                      sum(record["audit_wall_seconds"] for record in records)
                  ),
                  "audit_day_wall_seconds_mean": float(
                      sum(record["audit_wall_seconds"] for record in records) / len(records)
                  ),
                  "final_runtime_workers": args.workers,
                  "producer_completion_sha256": audit.digest(args.engine_root / "completion.json"),
                  "producer_index_sha256": producer_completion["index_sha256"],
                  "audit_engine_sha256": script_hash, "audit_runner_sha256": runner_hash,
                  "synthetic_bruteforce_passed_separately": True,
                  "full_feature_reconstruction": False,
                  "oracle_is_hindsight_upper_bound": True,
                  "causal_learner_profitability_evaluated": False,
                  "live_parity_verified": False, "original_receipt_verified": False,
                  "technical_ready": False, "promotion_approved": False,
                  "finished_at_utc": now()}
        atomic_json(args.output / "audit.json", result)
        print(json.dumps(result), flush=True)
    except BaseException:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        atomic_json(args.output / f"audit_failure_{stamp}.json",
                    {"status": "AUDIT_FAILED", "utc": now(),
                     "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    main()
