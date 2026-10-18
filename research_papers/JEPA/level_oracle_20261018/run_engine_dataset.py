"""Bounded, resumable level-oracle dataset driver; economic engine stays frozen."""

from __future__ import annotations

import os
import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time
import traceback

for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
):
    os.environ[_name] = "1"

import numpy as np  # noqa: E402 -- limit native threads before numerical imports
import pandas as pd  # noqa: E402 -- limit native threads before numerical imports
import pyarrow as pa  # noqa: E402 -- limit native threads before numerical imports

import level_engine as engine  # noqa: E402 -- same native-thread requirement

CACHE_ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018/cache_v1")
OUTPUT_ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018/engine_v1")
TICKERS = ("SPXW", "SPY", "QQQ")
ARTIFACTS = ("states", "levels", "actions", "labels", "advantages", "oracle_ledger")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(
        json.dumps(data, indent=2, allow_nan=False, default=str), encoding="utf-8"
    )
    os.replace(temporary, path)


def split_for(date):
    return (
        "train"
        if date < "20250101"
        else ("validation" if date < "20260101" else "test")
    )


def initial_row(ticker, date, cache_root, output_root):
    return {
        "ticker": ticker,
        "date": date,
        "split": split_for(date),
        "status": "PENDING",
        "cache_path": str(cache_root / ticker / f"{date}.npz"),
        "day_root": str(output_root / ticker / date),
        "error": None,
        "actions_count": 0,
        "trades": 0,
        "net_base": 0.0,
        "net_adverse": 0.0,
        "eligible_fraction": None,
        "hold_min": None,
        "hold_median": None,
        "hold_max": None,
        **{
            f"{reason}_{field}": 0.0
            for reason in ("TARGET", "STOP", "EOD")
            for field in ("trades", "net_base", "net_adverse")
        },
    }


def initialize_worker():
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)


def verify_finished_day(cache_path, day_root, engine_hash, protocol_hash):
    source = engine.load_cache_module()
    metadata = source.read_day_metadata(cache_path)
    identity = json.loads((day_root / "identity.json").read_text(encoding="utf-8"))
    summary = json.loads((day_root / "summary.json").read_text(encoding="utf-8"))
    if (
        identity["engine_sha256"] != engine_hash
        or identity["protocol_sha256"] != protocol_hash
    ):
        raise ValueError("Existing day engine/protocol differs")
    if identity["metadata"] != metadata:
        raise ValueError("Existing day cache metadata differs")
    if (
        engine.file_sha(day_root / "level_engine.py") != engine_hash
        or engine.file_sha(day_root / "PROTOCOL.md") != protocol_hash
    ):
        raise ValueError("Existing day frozen code/spec mismatch")
    if summary["status"] != "COMPLETED_HINDSIGHT_ORACLE_DAY":
        raise ValueError("Existing day is not complete")
    for name, digest in summary["artifact_hashes"].items():
        if engine.file_sha(day_root / name) != digest:
            raise ValueError("Existing day artifact mismatch: " + name)
    source.load_day_cache(cache_path)  # Revalidate the sealed NPZ checksum on resume.
    return summary


def completed_row(row, summary):
    day_root, cache_path = Path(row["day_root"]), Path(row["cache_path"])
    ledger = pd.read_parquet(day_root / "oracle_ledger.parquet")
    result = dict(row)
    result.update(
        {
            "status": "COMPLETE",
            "error": None,
            "cache_npz_sha256": engine.file_sha(cache_path),
            "cache_meta_sha256": engine.file_sha(cache_path.with_suffix(".json")),
            "summary_sha256": engine.file_sha(day_root / "summary.json"),
            "identity_sha256": engine.file_sha(day_root / "identity.json"),
            "causal_freeze_sha256": engine.file_sha(day_root / "causal_freeze.json"),
            "oracle_value_sha256": engine.file_sha(day_root / "oracle_value.npy"),
            "actions_count": summary["coverage"]["causal_actions"],
            "trades": summary["oracle"]["trades"],
            "net_base": summary["oracle"]["net_base"],
            "net_adverse": summary["oracle"]["net_adverse"],
            "eligible_fraction": summary["coverage"]["eligible_fraction"],
            "no_fill_actions": summary["oracle"]["no_fill_actions"],
            "missing_exit_trades": summary["oracle"].get("missing_exit_trades", 0),
            "missing_spot_trades": summary["oracle"].get("missing_spot_trades", 0),
        }
    )
    for name in ARTIFACTS:
        result[name + "_sha256"] = engine.file_sha(day_root / f"{name}.parquet")
    if len(ledger):
        result.update(
            {
                "hold_min": int(ledger.hold_minutes.min()),
                "hold_median": float(ledger.hold_minutes.median()),
                "hold_max": int(ledger.hold_minutes.max()),
            }
        )
    for reason in ("TARGET", "STOP", "EOD"):
        subset = ledger.loc[ledger.reason == reason]
        result[reason + "_trades"] = len(subset)
        for cost in ("net_base", "net_adverse"):
            result[reason + "_" + cost] = float(subset[cost].sum())
    return result


def process_one(job):
    row, engine_hash, protocol_hash = job
    out = Path(row["day_root"])
    cache_path = Path(row["cache_path"])
    try:
        if (
            engine.file_sha(engine.__file__) != engine_hash
            or engine.file_sha(Path(engine.__file__).with_name("PROTOCOL.md"))
            != protocol_hash
        ):
            raise ValueError("Engine/protocol changed while running")
        if out.exists():
            if not (out / "summary.json").exists():
                raise ValueError(
                    "Preserved incomplete day root; no overwrite or implicit retry"
                )
            summary = verify_finished_day(cache_path, out, engine_hash, protocol_hash)
        else:
            source = engine.load_cache_module()
            metadata = source.read_day_metadata(cache_path)
            cache = source.load_day_cache(cache_path)
            summary = engine.run_day(cache, metadata, out)
            source.load_day_cache(cache_path)  # Input integrity after construction.
        return completed_row(row, summary)
    except Exception as error:
        failed = dict(row)
        failed.update(
            {"status": "FAILED", "error": type(error).__name__ + ": " + str(error)}
        )
        failure_root = out.parents[1] / "failures"
        failure_root.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        atomic_json(
            failure_root / f"{row['ticker']}_{row['date']}_{stamp}.json",
            {"row": failed, "utc": utc_now(), "traceback": traceback.format_exc()},
        )
        return failed


def index_snapshot(records, root):
    frame = (
        pd.DataFrame(records)
        .sort_values(["ticker", "date"], kind="stable")
        .reset_index(drop=True)
    )
    temporary = root / "index.partial.parquet"
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, root / "index.parquet")
    temporary_csv = root / "index.partial.csv"
    frame.to_csv(temporary_csv, index=False)
    os.replace(temporary_csv, root / "index.csv")
    return frame


def aggregate(frame, include_holding=False):
    complete = frame.loc[frame.status == "COMPLETE"]
    result = {
        "calendar_rows": len(frame),
        "complete_days": len(complete),
        "missing_days": int((frame.status == "MISSING_SOURCE").sum()),
        "pending_days": int((frame.status == "PENDING").sum()),
        "failed_days": int((frame.status == "FAILED").sum()),
        "actions": int(complete.actions_count.sum()),
        "trades": int(complete.trades.sum()),
        "net_base": float(complete.net_base.sum()),
        "net_adverse": float(complete.net_adverse.sum()),
        "exit_reasons": {},
    }
    for reason in ("TARGET", "STOP", "EOD"):
        result["exit_reasons"][reason] = {
            "trades": int(complete[reason + "_trades"].sum()),
            "net_base": float(complete[reason + "_net_base"].sum()),
            "net_adverse": float(complete[reason + "_net_adverse"].sum()),
        }
    if len(complete):
        result["eligible_state_fraction_mean"] = float(
            complete.eligible_fraction.mean()
        )
    if include_holding:
        holding = []
        for day_root in complete.day_root:
            holding.extend(
                pd.read_parquet(
                    Path(day_root) / "oracle_ledger.parquet", columns=["hold_minutes"]
                ).hold_minutes.tolist()
            )
        result["holding_minutes"] = {
            "min": int(min(holding)) if holding else None,
            "median": float(np.median(holding)) if holding else None,
            "max": int(max(holding)) if holding else None,
        }
    return result


def final_summary(frame, cache_root, root, started):
    summary = {
        "status": "COMPLETE"
        if (frame.status.isin(["COMPLETE", "MISSING_SOURCE"]).all())
        else "FAILED",
        "oracle_uses_future": True,
        "predictive_profitability_demonstrated": False,
        "unit": "USD per one option contract, multiplier100; not a funded account return",
        "adverse_uses_same_base_oracle_path": True,
        "seconds": time.monotonic() - started,
        "finished_utc": utc_now(),
        "all": aggregate(frame, True),
        "by_ticker": {},
        "by_split": {},
        "by_ticker_month": {},
    }
    for ticker, group in frame.groupby("ticker", sort=True):
        summary["by_ticker"][ticker] = aggregate(group, True)
    for split, group in frame.groupby("split", sort=True):
        summary["by_split"][split] = aggregate(group, True)
    for (ticker, month), group in frame.groupby(
        ["ticker", frame.date.str[:6]], sort=True
    ):
        summary["by_ticker_month"][ticker + "_" + month] = aggregate(group)
    cache_summary = json.loads(
        (cache_root / "full_summary.json").read_text(encoding="utf-8")
    )
    summary["cache_full_summary_sha256"] = engine.file_sha(
        cache_root / "full_summary.json"
    )
    summary["expected_shape_matches"] = bool(
        len(frame) == 2601
        and summary["all"]["complete_days"] == 2595
        and summary["all"]["missing_days"] == 6
        and cache_summary["missing_sources"] == 6
    )
    if not summary["expected_shape_matches"]:
        summary["status"] = "FAILED_COVERAGE_EXPECTATION"
    atomic_json(root / "summary.json", summary)
    atomic_json(
        root / "completion.json",
        {
            "status": summary["status"],
            "finished_utc": utc_now(),
            "index_sha256": engine.file_sha(root / "index.parquet"),
            "summary_sha256": engine.file_sha(root / "summary.json"),
            "dataset_contract_sha256": engine.file_sha(root / "dataset_contract.json"),
            "cache_full_summary_sha256": summary["cache_full_summary_sha256"],
        },
    )
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", type=Path, default=CACHE_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    args = parser.parse_args()
    initialize_worker()
    root, cache_root = args.output, args.cache_root
    root.mkdir(parents=True, exist_ok=True)
    calendar_path = cache_root / "expected_calendar.csv"
    calendar = pd.read_csv(calendar_path, dtype={"date": str})
    dates = calendar.loc[
        calendar.full_session.astype(str).str.lower() == "true", "date"
    ].tolist()
    if len(dates) != 867:
        raise ValueError("Expected fixed 867 full NYSE sessions")
    engine_hash = engine.file_sha(engine.__file__)
    protocol_path = Path(engine.__file__).with_name("PROTOCOL.md")
    protocol_hash = engine.file_sha(protocol_path)
    contract = {
        "version": "LEVEL_ORACLE_DATASET_V1",
        "engine_sha256": engine_hash,
        "runner_sha256": engine.file_sha(__file__),
        "protocol_sha256": protocol_hash,
        "cache_contract_sha256": engine.file_sha(cache_root / "cache_contract.json"),
        "expected_calendar_sha256": engine.file_sha(calendar_path),
        "cache_root": str(cache_root.resolve()),
        "tickers": list(TICKERS),
        "expected_calendar_rows": 2601,
        "expected_available_days": 2595,
        "expected_missing_days": 6,
        "workers": args.workers,
        "native_threads_per_worker": 1,
        "oracle_primary_cost": "base",
        "adverse_reoptimized": False,
        "engine_output_schema": {
            "causal": ["states", "levels", "actions"],
            "future_sidecars": [
                "labels",
                "advantages",
                "oracle_ledger",
                "oracle_value",
            ],
        },
    }
    if (root / "dataset_contract.json").exists():
        if (
            json.loads((root / "dataset_contract.json").read_text(encoding="utf-8"))
            != contract
        ):
            raise ValueError(
                "Resume contract changed; preserve this root and use a new version"
            )
    else:
        atomic_json(root / "dataset_contract.json", contract)
        shutil.copy2(__file__, root / "run_engine_dataset.executed.py")
        shutil.copy2(engine.__file__, root / "level_engine.executed.py")
        shutil.copy2(protocol_path, root / "PROTOCOL.md")
    records = [
        initial_row(ticker, date, cache_root, root)
        for ticker in TICKERS
        for date in dates
    ]
    submitted = set()
    started, last_snapshot = time.monotonic(), 0.0
    try:
        with ProcessPoolExecutor(
            max_workers=args.workers, initializer=initialize_worker
        ) as pool:
            futures = {}
            while True:
                cache_done = (cache_root / "full_summary.json").exists()
                missing = set()
                if cache_done:
                    coverage = pd.read_csv(
                        cache_root / "full_coverage.csv", dtype={"date": str}
                    )
                    missing = set(
                        zip(
                            coverage.loc[coverage.status == "MISSING_SOURCE", "ticker"],
                            coverage.loc[coverage.status == "MISSING_SOURCE", "date"],
                        )
                    )
                for idx, row in enumerate(records):
                    key = (row["ticker"], row["date"])
                    if key in submitted or row["status"] != "PENDING":
                        continue
                    if key in missing:
                        row["status"] = "MISSING_SOURCE"
                        continue
                    if len(futures) >= args.workers * 2:
                        break
                    path = Path(row["cache_path"])
                    if path.exists() and path.with_suffix(".json").exists():
                        future = pool.submit(
                            process_one, (dict(row), engine_hash, protocol_hash)
                        )
                        futures[future] = idx
                        submitted.add(key)
                    elif cache_done:
                        row.update(
                            {
                                "status": "FAILED",
                                "error": "Cache complete but expected sealed day absent",
                            }
                        )
                if futures:
                    done, _ = wait(futures, timeout=2.0, return_when=FIRST_COMPLETED)
                    for future in done:
                        idx = futures.pop(future)
                        records[idx] = future.result()
                elif not cache_done:
                    time.sleep(2.0)
                now = time.monotonic()
                pending = sum(row["status"] == "PENDING" for row in records)
                if now - last_snapshot >= 10 or (
                    cache_done and not pending and not futures
                ):
                    frame = index_snapshot(records, root)
                    progress = {
                        "status": "RUNNING",
                        "utc": utc_now(),
                        "expected": len(records),
                        "complete": int((frame.status == "COMPLETE").sum()),
                        "missing": int((frame.status == "MISSING_SOURCE").sum()),
                        "failed": int((frame.status == "FAILED").sum()),
                        "pending": pending,
                        "inflight": len(futures),
                        "cache_complete": cache_done,
                    }
                    atomic_json(root / "progress.json", progress)
                    print(json.dumps(progress), flush=True)
                    last_snapshot = now
                if cache_done and not pending and not futures:
                    break
        frame = index_snapshot(records, root)
        summary = final_summary(frame, cache_root, root, started)
        print(
            json.dumps({"status": summary["status"], "all": summary["all"]}), flush=True
        )
        if summary["status"] != "COMPLETE":
            raise RuntimeError("Dataset has preserved failures or unexpected coverage")
    except BaseException:
        index_snapshot(records, root)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        atomic_json(
            root / f"run_failure_{stamp}.json",
            {"utc": utc_now(), "traceback": traceback.format_exc()},
        )
        raise


if __name__ == "__main__":
    main()
