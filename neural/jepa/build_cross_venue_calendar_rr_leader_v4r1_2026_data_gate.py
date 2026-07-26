#!/usr/bin/env python3
"""Build the outcome-free V4R1 2026 feature gate after the exact source retry."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa import (  # noqa: E402
    build_calendar_risk_reversal_pressure_v1 as pressure,
)
from neural.jepa import build_cross_venue_calendar_rr_leader_v1 as v1_builder  # noqa: E402
from neural.jepa import (  # noqa: E402
    cross_venue_calendar_rr_leader_v4r1_2026_common as common,
)
from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v2 as v2  # noqa: E402
from neural.jepa.build_calendar_risk_reversal_pressure_v1 import (  # noqa: E402
    tracked_clean,
)


PROJECT_ROOT = SCRIPT_REPO_ROOT
CAPTURER = PROJECT_ROOT / (
    "neural/jepa/"
    "capture_cross_venue_calendar_rr_leader_v4r1_2026_source_retry.py"
)
AUDITOR = PROJECT_ROOT / (
    "neural/jepa/audit_cross_venue_calendar_rr_leader_v4r1_2026_data_gate.py"
)
RESEALER = PROJECT_ROOT / (
    "neural/jepa/"
    "reseal_cross_venue_calendar_rr_leader_v4r1_2026_source_retry.py"
)
DEFAULT_RETRY_ROOT = common.RETRY_RESEAL_ROOT
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v4r1_data_gate_202601_20260724_v1"
)
OUTPUT_FILES = (
    "universe.csv",
    "sensor_features.parquet",
    "feature_view.parquet",
    "feature_counts.csv",
    "source_inventory.csv",
    "sensor_feature_audit.csv",
    "cash_source_audit.csv",
    "exclusions.csv",
    "SUMMARY.md",
)
CODE_CLOSURE = (
    Path(__file__).resolve(),
    Path(common.__file__).resolve(),
    CAPTURER,
    RESEALER,
    AUDITOR,
    common.PREDECLARATION,
)


def current_git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def dataframe_digest(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return __import__("hashlib").sha256(payload).hexdigest()


def verify_code() -> dict[str, str]:
    if common.sha256_file(common.PREDECLARATION) != common.PREDECLARATION_SHA256:
        raise AssertionError("V4R1 predeclaration changed")
    hashes: dict[str, str] = {}
    for path in CODE_CLOSURE:
        tracked_clean(path, f"V4R1 data-gate closure {path.name}")
        hashes[path.relative_to(PROJECT_ROOT).as_posix()] = common.sha256_file(path)
    return hashes


def load_retry_gate(retry_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    paths = {
        name: retry_root / name
        for name in (
            "seal.json",
            "pair_gate.csv",
            "exclusions.csv",
            "request_index.csv",
            "source_rehash.csv",
        )
    }
    if not all(path.is_file() for path in paths.values()):
        raise FileNotFoundError(f"incomplete V4R1 retry root: {retry_root}")
    seal = json.loads(paths["seal.json"].read_text(encoding="utf-8"))
    if (
        seal.get("schema")
        != "cross_venue_calendar_rr_leader_v4r1_retry_offline_reseal_v2"
        or seal.get("status") != "PASS_OFFLINE_REPARSE_RETRY_GATE"
        or seal.get("logical_requests") != 10
        or seal.get("source_seal_sha256") != common.ORIGINAL_RETRY_SEAL_SHA256
        or seal.get("predeclaration_sha256") != common.PREDECLARATION_SHA256
        or seal.get("date_sha256") != common.DATE_SHA256
        or seal.get("capture_id_sha256") != common.CAPTURE_ID_SHA256
        or seal.get("outcome_free") is not True
        or seal.get("feature_2026_opened") is not False
        or seal.get("outcome_2026_accessed") is not False
        or seal.get("network_accessed") is not False
        or Path(str(seal.get("source_root"))) != common.RETRY_ROOT
        or common.sha256_file(common.RETRY_ROOT / "seal.json")
        != common.ORIGINAL_RETRY_SEAL_SHA256
        or common.sha256_file(paths["pair_gate.csv"]) != seal.get("pair_gate_sha256")
        or common.sha256_file(paths["exclusions.csv"]) != seal.get("exclusions_sha256")
        or common.sha256_file(paths["request_index.csv"])
        != seal.get("request_index_sha256")
        or common.sha256_file(paths["source_rehash.csv"])
        != seal.get("source_rehash_sha256")
    ):
        raise AssertionError("V4R1 retry seal changed")
    pair_gate = pd.read_csv(
        paths["pair_gate.csv"],
        dtype={
            "capture_id": str,
            "ticker": str,
            "trade_date": str,
            "expiration": str,
        },
    )
    pair_gate["usable"] = pair_gate["usable"].map(
        lambda value: str(value).strip().lower() in {"true", "1"}
    )
    exclusions = pd.read_csv(
        paths["exclusions.csv"],
        dtype={"sensor_ticker": str, "trade_date": str, "capture_id": str},
    )
    if (
        set(pair_gate["capture_id"]) != set(common.RETRY_IDS)
        or len(pair_gate) != 5
        or exclusions.duplicated(["sensor_ticker", "trade_date"]).any()
        or int(pair_gate["usable"].sum()) != int(seal["usable_pairs"])
        or len(exclusions) != int(seal["excluded_sensor_dates"])
    ):
        raise AssertionError("V4R1 retry pair/exclusion gate changed")
    return pair_gate, exclusions, seal


def underlying_path(ticker: str, day: str) -> Path:
    return (
        common.UNDERLYING_ROOT
        / ticker
        / day[:4]
        / day[4:6]
        / f"{ticker}_{day}.parquet"
    )


def role_paths(
    record: dict[str, Any],
    role: str,
    pair_lookup: dict[str, dict[str, Any]],
) -> tuple[Path, Path, str]:
    capture_id = (
        f"{record['ticker']}|{record['trade_date']}|{role}|"
        f"{record[role + '_expiration']}"
    )
    if capture_id in pair_lookup:
        pair = pair_lookup[capture_id]
        if not bool(pair["usable"]):
            raise AssertionError(f"excluded V4R1 capture reached builder: {capture_id}")
        return Path(str(pair["greeks_path"])), Path(str(pair["iv_path"])), "RETRY"
    return (
        Path(str(record[f"{role}_greeks_path"])),
        Path(str(record[f"{role}_iv_path"])),
        "VINTAGE",
    )


def process_sensor_session(
    record: dict[str, Any], pair_lookup: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    ticker = str(record["ticker"])
    day = str(record["trade_date"])
    spot_path = underlying_path(ticker, day)
    spot_t0, spot_t1 = v1_builder.read_target_spots(spot_path, ticker, day)
    chains: dict[str, pd.DataFrame] = {}
    audit: dict[str, Any] = {"ticker": ticker, "trade_date": day}
    inventory: list[dict[str, Any]] = []
    for role in ("front", "back"):
        expiration = str(record[f"{role}_expiration"])
        greeks_path, iv_path, generation = role_paths(record, role, pair_lookup)
        greeks = common.read_vintage_values_compatible(
            greeks_path,
            kind="greeks",
            ticker=ticker,
            trade_date=day,
            expiration=expiration,
        )
        iv = common.read_vintage_values_compatible(
            iv_path,
            kind="iv",
            ticker=ticker,
            trade_date=day,
            expiration=expiration,
        )
        chains[role] = v1_builder.join_greeks_iv(greeks, iv)
        audit.update(
            {
                f"{role}_generation": generation,
                f"{role}_greek_rows": int(len(greeks)),
                f"{role}_iv_rows": int(len(iv)),
            }
        )
        for kind, path in (("greeks", greeks_path), ("iv", iv_path)):
            inventory.append(
                {
                    "kind": f"option_{kind}",
                    "ticker": ticker,
                    "trade_date": day,
                    "role": role,
                    "path": str(path),
                    "size_bytes": int(path.stat().st_size),
                    "sha256": common.sha256_file(path),
                    "generation": generation,
                }
            )
    feature = pressure.calculate_session_feature(
        ticker=ticker,
        trade_date=day,
        front_expiration=str(record["front_expiration"]),
        back_expiration=str(record["back_expiration"]),
        spot_t0=spot_t0,
        spot_t1=spot_t1,
        front_chain=chains["front"],
        back_chain=chains["back"],
    )
    inventory.append(
        {
            "kind": "underlying_feature_clock",
            "ticker": ticker,
            "trade_date": day,
            "role": "",
            "path": str(spot_path),
            "size_bytes": int(spot_path.stat().st_size),
            "sha256": common.sha256_file(spot_path),
            "generation": "VINTAGE",
        }
    )
    return feature, audit, inventory


def build_sensor_features(
    universe: pd.DataFrame,
    pair_gate: pd.DataFrame,
    exclusions: pd.DataFrame,
    workers: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    excluded_keys = set(
        zip(exclusions["sensor_ticker"], exclusions["trade_date"], strict=True)
    )
    pair_lookup = {
        str(row["capture_id"]): row for row in pair_gate.to_dict(orient="records")
    }
    records = [
        row
        for row in universe.to_dict(orient="records")
        if (str(row["ticker"]), str(row["trade_date"])) not in excluded_keys
    ]
    features: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_sensor_session, row, pair_lookup): row
            for row in records
        }
        for future in as_completed(futures):
            feature, audit, sources = future.result()
            features.append(feature)
            audits.append(audit)
            inventory.extend(sources)
    feature_frame = pd.DataFrame(features).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    audit_frame = pd.DataFrame(audits).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    source_frame = pd.DataFrame(inventory).drop_duplicates("path").sort_values(
        ["kind", "ticker", "trade_date", "role"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(feature_frame) != len(universe) - len(exclusions)
        or feature_frame.duplicated(["ticker", "trade_date"]).any()
        or not np.isfinite(
            feature_frame[
                [
                    "front_rr_t0",
                    "front_rr_t1",
                    "back_rr_t0",
                    "back_rr_t1",
                    "calendar_rr_t0",
                    "calendar_rr_t1",
                    "calendar_rr_pressure",
                ]
            ].to_numpy(dtype=float)
        ).all()
    ):
        raise AssertionError("V4R1 sensor feature gate changed")
    return feature_frame, audit_frame, source_frame


def map_targets(sensor_features: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for sensor in sensor_features.to_dict(orient="records"):
        sensor_ticker = str(sensor["ticker"])
        targets = ("QQQ",) if sensor_ticker == "QQQ" else ("SPXW", "SPY")
        for ticker in targets:
            records.append(
                {
                    "ticker": ticker,
                    "trade_date": str(sensor["trade_date"]),
                    "month": str(sensor["trade_date"])[:6],
                    "sensor_ticker": sensor_ticker,
                    "signal_pressure": float(sensor["calendar_rr_pressure"]),
                    "abs_signal_pressure": abs(
                        float(sensor["calendar_rr_pressure"])
                    ),
                    "calendar_rr_t0": float(sensor["calendar_rr_t0"]),
                    "front_rr_t0": float(sensor["front_rr_t0"]),
                    "back_rr_t0": float(sensor["back_rr_t0"]),
                    "front_rr_change": float(sensor["front_rr_t1"])
                    - float(sensor["front_rr_t0"]),
                    "back_rr_change": float(sensor["back_rr_t1"])
                    - float(sensor["back_rr_t0"]),
                    "option_spot_return_5m_bps": float(
                        np.log(float(sensor["spot_t1"]) / float(sensor["spot_t0"]))
                        * 10_000.0
                    ),
                }
            )
    return pd.DataFrame(records).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)


def attach_cash_features(
    targets: pd.DataFrame, workers: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    needed: set[tuple[str, str]] = set()
    for row in targets.itertuples(index=False):
        needed.update({("QQQ", str(row.trade_date)), ("SPY", str(row.trade_date))})
        if str(row.ticker) == "SPXW":
            needed.add(("SPXW", str(row.trade_date)))
    records = []
    for ticker, day in sorted(needed):
        path = underlying_path(ticker, day)
        records.append(
            SimpleNamespace(
                ticker=ticker,
                trade_date=day,
                path=str(path),
                size_bytes=int(path.stat().st_size),
                sha256=common.sha256_file(path),
            )
        )
    cache: dict[tuple[str, str], dict[str, float]] = {}
    audits: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(v2.read_early_cash_source, row) for row in records]
        for future in as_completed(futures):
            key, features, audit = future.result()
            cache[key] = features
            audits.append(audit)
    audit_frame = pd.DataFrame(audits).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if (
        set(cache) != needed
        or int(audit_frame["original_invalid_open_rows"].sum()) != 0
    ):
        raise AssertionError("V4R1 early cash source gate failed")
    output = v2.attach_cash_features(targets, cache)
    inventory = audit_frame[
        ["ticker", "trade_date", "path", "size_bytes", "sha256"]
    ].copy()
    inventory.insert(0, "kind", "underlying_early_cash")
    inventory["role"] = ""
    inventory["generation"] = "VINTAGE"
    return output, audit_frame, inventory


def feature_counts(features: pd.DataFrame) -> pd.DataFrame:
    months = sorted(common.EXPECTED_MONTH_COUNTS)
    rows = []
    for ticker in v2.TICKERS:
        for month in months:
            count = int(
                (
                    features["ticker"].eq(ticker)
                    & features["month"].eq(month)
                ).sum()
            )
            rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "events": count,
                    "frequency_pass": count >= 13,
                    "month_complete": month <= "202606",
                    "july_mtd": month == "202607",
                }
            )
    output = pd.DataFrame(rows)
    if len(output) != 21 or not output["frequency_pass"].all():
        raise AssertionError("V4R1 target frequency gate failed")
    return output


def render_summary(summary: dict[str, Any], counts: pd.DataFrame) -> str:
    lines = [
        "# CROSS_VENUE_CALENDAR_RR_LEADER_V4R1 — outcome-free data gate 2026",
        "",
        f"Status: `{summary['status']}`.",
        "",
        "| Ticker | Jan | Feb | Mar | Apr | May | Jun | Jul MTD |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for ticker in v2.TICKERS:
        values = counts.loc[counts["ticker"].eq(ticker), "events"].tolist()
        lines.append(f"| {ticker} | " + " | ".join(str(value) for value in values) + " |")
    lines.extend(
        [
            "",
            "Features stop at 10:35. No open10:36/open13:36, return, label or PnL was read.",
            "July is MTD through 2026-07-24.",
        ]
    )
    return "\n".join(lines) + "\n"


def run(
    retry_root: Path, output_dir: Path, workers: int
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V4R1 data gate exists: {output_dir}")
    if not 1 <= workers <= 16:
        raise ValueError("workers must be in [1, 16]")
    code_hashes = verify_code()
    pair_gate, exclusions, retry_seal = load_retry_gate(retry_root)
    universe = common.discover_universe()
    sensor_features, sensor_audit, sensor_inventory = build_sensor_features(
        universe, pair_gate, exclusions, workers
    )
    targets = map_targets(sensor_features)
    feature_view, cash_audit, cash_inventory = attach_cash_features(targets, workers)
    feature_view = feature_view[
        ["ticker", "trade_date", "month", "sensor_ticker", *v2.FEATURE_COLUMNS]
    ].copy()
    counts = feature_counts(feature_view)
    inventory = pd.concat(
        [sensor_inventory, cash_inventory], ignore_index=True
    ).drop_duplicates("path").sort_values(
        ["kind", "ticker", "trade_date", "role"], kind="stable"
    ).reset_index(drop=True)
    if (
        feature_view.duplicated(["ticker", "trade_date"]).any()
        or not np.isfinite(
            feature_view[list(v2.FEATURE_COLUMNS)].to_numpy(dtype=float)
        ).all()
        or feature_view.columns.str.contains(
            "outcome|return_bps|10:36|13:36|label|pnl",
            case=False,
            regex=True,
        ).any()
    ):
        raise AssertionError("V4R1 feature view contains invalid/outcome fields")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        universe.to_csv(staging / "universe.csv", index=False, lineterminator="\n")
        sensor_features.to_parquet(staging / "sensor_features.parquet", index=False)
        feature_view.to_parquet(staging / "feature_view.parquet", index=False)
        counts.to_csv(staging / "feature_counts.csv", index=False, lineterminator="\n")
        inventory.to_csv(
            staging / "source_inventory.csv", index=False, lineterminator="\n"
        )
        sensor_audit.to_csv(
            staging / "sensor_feature_audit.csv", index=False, lineterminator="\n"
        )
        cash_audit.to_csv(
            staging / "cash_source_audit.csv", index=False, lineterminator="\n"
        )
        exclusions.to_csv(
            staging / "exclusions.csv", index=False, lineterminator="\n"
        )
        provisional = {
            "status": "PASS_OUTCOME_FREE_DATA_GATE",
        }
        (staging / "SUMMARY.md").write_text(
            render_summary(provisional, counts), encoding="utf-8", newline="\n"
        )
        summary = {
            "schema": "cross_venue_calendar_rr_leader_v4r1_2026_data_gate_v1",
            "status": "PASS_OUTCOME_FREE_DATA_GATE",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "execution_commit": current_git_commit(),
            "retry_seal_sha256": common.sha256_file(retry_root / "seal.json"),
            "retry_usable_pairs": int(retry_seal["usable_pairs"]),
            "excluded_sensor_dates": int(len(exclusions)),
            "universe_sensor_sessions": int(len(universe)),
            "sensor_feature_rows": int(len(sensor_features)),
            "target_feature_rows": int(len(feature_view)),
            "feature_count": len(v2.FEATURE_COLUMNS),
            "feature_columns": list(v2.FEATURE_COLUMNS),
            "mapping": v2.SENSOR_MAP,
            "monthly_counts": counts.to_dict(orient="records"),
            "date_sha256": common.DATE_SHA256,
            "capture_id_sha256": common.CAPTURE_ID_SHA256,
            "predeclaration_sha256": common.PREDECLARATION_SHA256,
            "code_hashes": code_hashes,
            "source_files_rehashed": int(len(inventory)),
            "source_hash_mismatches": 0,
            "outcome_clock_read": False,
            "feature_clock_last": "10:35:00",
            "open_1036_read": False,
            "open_1336_read": False,
            "outcome_2026_accessed": False,
            "production_modified": False,
            "live_or_systemd_modified": False,
            "output_sha256": {
                name: common.sha256_file(staging / name) for name in OUTPUT_FILES
            },
            "feature_view_recomputed_sha256": dataframe_digest(feature_view),
            "feature_counts_recomputed_sha256": dataframe_digest(counts),
            "source_inventory_recomputed_sha256": dataframe_digest(inventory),
        }
        (staging / "SUMMARY.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retry-root", type=Path, default=DEFAULT_RETRY_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(
        args.retry_root.resolve(), args.output_dir.resolve(), args.workers
    )
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
