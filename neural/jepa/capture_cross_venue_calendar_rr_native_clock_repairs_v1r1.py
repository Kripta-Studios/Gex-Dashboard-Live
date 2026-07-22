#!/usr/bin/env python3
"""Capture the four frozen V1R1 calendar-RR native-clock repairs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa import (  # noqa: E402
    capture_cross_venue_calendar_rr_native_clock_preflight as pre,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402

DEFAULT_V1_ROOT = Path(
    "D:/ThetaData/cross_venue_calendar_rr_native_clock_2024_2025_v1"
)
DEFAULT_OUTPUT = Path(
    "D:/ThetaData/cross_venue_calendar_rr_native_clock_2024_2025_v1r1_repairs"
)
PREDECLARATION = PROJECT_ROOT / (
    "research_papers/JEPA/"
    "CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_V1R1_KEY_INTERSECTION_REPAIR_PREDECLARATION.md"
)
RUNTIME_LOCK = pre.RUNTIME_LOCK
EXPECTED_V1_STATE_SHA256 = {
    "capture_contract.json": "f40947b52dd8923e785eb4f3d65d2ff8c5fba1720418b94ba5d50b36a40ea623",
    "universe.csv": "98d416ea810c5bde657b6c23a9d7c599885d5eedfef3e332cd1885f6ddee45f4",
    "errors.json": "01c6c2f39d0dd5bab09284827aaafb9036c836127be0b28a31e17b44e22795f2",
}
V1_CONTRACT_COMMIT = "d013a299153ce6a4c611a7402c208fd2bf1b14a8"
EXPECTED_V1_CAPTURES = 3_008
EXPECTED_REPAIRS: dict[str, dict[str, Any]] = {
    "4b5b53cd7bce4944364d631d": {
        "ticker": "QQQ",
        "trade_date": "20250828",
        "role": "front",
        "expiration": "20250828",
        "unilateral_source": "iv_only",
        "right": "C",
        "strike": 650.0,
        "shared_key_rows": 406,
        "greeks_sha256": "fd412ffe1e9195e8961d270baed1363e635b80e20150c35d4a441e1b72345543",
        "iv_sha256": "a86f9bcf827e112c4790ce70bf243869383d696cc4e8d971faf28b4f7e38506c",
    },
    "839ad0588cc9ee1309cd8c6f": {
        "ticker": "QQQ",
        "trade_date": "20251121",
        "role": "back",
        "expiration": "20251128",
        "unilateral_source": "greek_only",
        "right": "P",
        "strike": 680.0,
        "shared_key_rows": 706,
        "greeks_sha256": "25024720550a7c1db8cab366ad0955eb9328d70e0a06ae8a0daaf17b22fc64f3",
        "iv_sha256": "dc5610e58d294e0fad5df3c929bb8b58d3439d59a139279ef931ae177227a5eb",
    },
    "207459dd60dbfe7dd06da8cf": {
        "ticker": "SPXW",
        "trade_date": "20240122",
        "role": "back",
        "expiration": "20240126",
        "unilateral_source": "iv_only",
        "right": "C",
        "strike": 4575.0,
        "shared_key_rows": 858,
        "greeks_sha256": "047024584067b13084ecf585a5aea62cee027ec182880ce9b370aefbbbf8cd13",
        "iv_sha256": "6784c792285f66067e2e514d355e68821553287587ca622f95d1e4e100dfd649",
    },
    "8993033a23f2068d7a25d3c2": {
        "ticker": "SPXW",
        "trade_date": "20250225",
        "role": "front",
        "expiration": "20250225",
        "unilateral_source": "iv_only",
        "right": "C",
        "strike": 6045.0,
        "shared_key_rows": 858,
        "greeks_sha256": "71402f2f18f1f0c0012dee27cfea7e4566d30e7fb0112bac1bb822056f97426c",
        "iv_sha256": "818ba8681ddec15af2754c48154b599160146b8ff183812c6e6485b4c63021b0",
    },
}
EXPECTED_REPAIR_IDS = frozenset(EXPECTED_REPAIRS)
CODE_CLOSURE = (
    "neural/jepa/capture_cross_venue_calendar_rr_native_clock_repairs_v1r1.py",
    "neural/jepa/capture_cross_venue_calendar_rr_native_clock_preflight.py",
    "neural/jepa/build_wall_native_quote_sidecar.py",
    "neural/jepa/wall_surface_flow_environment.py",
    "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_V1R1_KEY_INTERSECTION_REPAIR_PREDECLARATION.md",
    "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
)


def dataframe_sha256(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_v1_materialization(root: Path) -> None:
    for name, digest in EXPECTED_V1_STATE_SHA256.items():
        path = root / "_state" / name
        if not path.is_file() or pre.sha256_file(path) != digest:
            raise AssertionError(f"frozen V1 state changed: {name}")
    contract = json.loads((root / "_state/capture_contract.json").read_text())
    if (
        contract.get("git_commit") != V1_CONTRACT_COMMIT
        or contract.get("universe_audit", {}).get("captures") != 3_012
        or (root / "_seal").exists()
    ):
        raise AssertionError("frozen V1 root contract changed")
    manifests = list(root.glob("*/????????/*/manifest.json"))
    raws = list(root.glob("*/????????/*/response.json"))
    parquets = list(root.glob("*/????????/*/quotes.parquet"))
    stagers = list(root.glob("*/????????/*.staging"))
    if not (
        len(manifests) == len(raws) == len(parquets) == EXPECTED_V1_CAPTURES
        and not stagers
    ):
        raise AssertionError("frozen V1 atomic materialization changed")
    for capture_id, expected in EXPECTED_REPAIRS.items():
        missing = root / expected["ticker"] / expected["trade_date"] / expected["role"]
        if missing.exists():
            raise AssertionError(f"V1 repair target unexpectedly exists: {capture_id}")


def load_repair_specs(v1_root: Path = DEFAULT_V1_ROOT) -> pd.DataFrame:
    validate_v1_materialization(v1_root)
    universe = pd.read_csv(
        v1_root / "_state/universe.csv",
        dtype={"capture_id": str, "trade_date": str, "expiration": str},
    )
    selected = universe.loc[universe["capture_id"].isin(EXPECTED_REPAIR_IDS)].copy()
    if len(selected) != 4 or set(selected["capture_id"]) != EXPECTED_REPAIR_IDS:
        raise AssertionError("frozen repair IDs are absent from V1 universe")
    errors = json.loads((v1_root / "_state/errors.json").read_text())["errors"]
    if {str(row.get("capture_id")) for row in errors} != EXPECTED_REPAIR_IDS:
        raise AssertionError("V1 error set changed")
    for row in errors:
        if row.get("error") != "AssertionError: Greek/IV vintage target key sets differ":
            raise AssertionError("V1 failure reason changed")
    for index, row in selected.iterrows():
        expected = EXPECTED_REPAIRS[str(row["capture_id"])]
        for field in ("ticker", "trade_date", "role", "expiration"):
            if str(row[field]) != str(expected[field]):
                raise AssertionError(f"repair identity changed: {row['capture_id']}")
        for kind in ("greeks", "iv"):
            digest = pre.sha256_file(row[f"{kind}_path"])
            if digest != expected[f"{kind}_sha256"]:
                raise AssertionError(f"repair {kind} source changed: {row['capture_id']}")
            selected.loc[index, f"{kind}_sha256"] = digest
    return selected.sort_values(["ticker", "trade_date", "role"], kind="stable").reset_index(drop=True)


def audit_vintage_intersection(
    spec: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], pd.DataFrame]:
    capture_id = str(spec["capture_id"])
    if capture_id not in EXPECTED_REPAIRS:
        raise AssertionError("capture is not in the frozen V1R1 repair set")
    expected = EXPECTED_REPAIRS[capture_id]
    greeks = pre.read_vintage_targets(spec["greeks_path"], spec, "greeks")
    iv = pre.read_vintage_targets(spec["iv_path"], spec, "iv")
    outer = greeks.loc[:, pre.KEYS].merge(
        iv.loc[:, pre.KEYS], on=list(pre.KEYS), how="outer", indicator=True
    )
    shared = outer.loc[outer["_merge"].eq("both"), list(pre.KEYS)].copy()
    greek_only = outer.loc[outer["_merge"].eq("left_only"), list(pre.KEYS)].copy()
    iv_only = outer.loc[outer["_merge"].eq("right_only"), list(pre.KEYS)].copy()
    unilateral = greek_only if expected["unilateral_source"] == "greek_only" else iv_only
    other = iv_only if expected["unilateral_source"] == "greek_only" else greek_only
    target_times = {
        pd.Timestamp(
            f"{expected['trade_date'][:4]}-{expected['trade_date'][4:6]}-"
            f"{expected['trade_date'][6:]} {clock}"
        )
        for clock in pre.TARGET_TIMES
    }
    if (
        len(shared) != int(expected["shared_key_rows"])
        or len(unilateral) != 2
        or not other.empty
        or set(unilateral["timestamp"]) != target_times
        or not unilateral["right"].eq(expected["right"]).all()
        or not np.isclose(
            unilateral["strike"].to_numpy(dtype=float), float(expected["strike"])
        ).all()
    ):
        raise AssertionError(f"unfrozen Greek/IV discrepancy: {capture_id}")
    shared_greeks = greeks.merge(shared, on=list(pre.KEYS), how="inner")
    shared_iv = iv.merge(shared, on=list(pre.KEYS), how="inner")
    unilateral = unilateral.copy()
    unilateral.insert(0, "capture_id", capture_id)
    unilateral.insert(1, "unilateral_source", expected["unilateral_source"])
    audit = {
        "greek_rows": int(len(greeks)),
        "iv_rows": int(len(iv)),
        "shared_key_rows": int(len(shared)),
        "greek_only_key_rows": int(len(greek_only)),
        "iv_only_key_rows": int(len(iv_only)),
        "shared_key_sha256": dataframe_sha256(
            shared.sort_values(list(pre.KEYS), kind="stable").reset_index(drop=True)
        ),
        "unilateral_key_sha256": dataframe_sha256(
            unilateral.sort_values(list(pre.KEYS), kind="stable").reset_index(drop=True)
        ),
    }
    return shared_greeks, shared_iv, audit, unilateral


def crosscheck_shared_vintage(
    quotes: pd.DataFrame, spec: dict[str, Any]
) -> tuple[dict[str, Any], pd.DataFrame]:
    greeks, _iv, audit, unilateral = audit_vintage_intersection(spec)
    shared_keys = greeks.loc[:, pre.KEYS]
    native = quotes.loc[quotes["timestamp"].isin(greeks["timestamp"].unique())].copy()
    merged = greeks.merge(
        native,
        on=list(pre.KEYS),
        how="left",
        suffixes=("_vintage", "_native"),
        indicator=True,
    )
    missing = int(merged["_merge"].ne("both").sum())
    if missing:
        raise AssertionError(f"native quote misses {missing} shared vintage keys")
    extras = native.merge(shared_keys, on=list(pre.KEYS), how="left", indicator=True)
    bid_diff = (merged["bid_native"] - merged["bid_vintage"]).abs()
    ask_diff = (merged["ask_native"] - merged["ask_vintage"]).abs()
    return {
        **audit,
        "missing_shared_key_rows": 0,
        "native_extra_target_key_rows": int(extras["_merge"].ne("both").sum()),
        "revised_bid_ask_rows": int((bid_diff.gt(1e-9) | ask_diff.gt(1e-9)).sum()),
        "crossed_native_rows": int(native["bid"].gt(native["ask"]).sum()),
    }, unilateral


def capture_directory(root: Path, spec: dict[str, Any]) -> Path:
    return root / str(spec["ticker"]) / str(spec["trade_date"]) / str(spec["role"])


def capture_one(
    spec: dict[str, Any],
    *,
    output: Path,
    base_url: str,
    provenance: dict[str, Any],
    runtime: dict[str, Any],
    code_hashes: dict[str, str],
    timeout: float,
    requester: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    params = pre.request_params(spec)
    response = requester(
        base_url.rstrip("/") + pre.ENDPOINT,
        params=params,
        headers={"Accept-Encoding": "identity"},
        timeout=timeout,
    )
    response.raise_for_status()
    raw = bytes(response.content)
    if not raw:
        raise AssertionError("empty native quote repair response")
    quotes = pre.normalize_quote_response(json.loads(raw), spec)
    audit, unilateral = crosscheck_shared_vintage(quotes, spec)
    directory = capture_directory(output, spec)
    working = directory.with_name(directory.name + ".staging")
    if directory.exists() or working.exists():
        raise FileExistsError(f"immutable repair directory exists: {directory}")
    working.mkdir(parents=True)
    raw_path = working / "response.json"
    parquet_path = working / "quotes.parquet"
    unilateral_path = working / "unilateral_vintage_keys.csv"
    manifest_path = working / "manifest.json"
    raw_path.write_bytes(raw)
    quotes.to_parquet(parquet_path, index=False)
    unilateral.to_csv(unilateral_path, index=False, lineterminator="\n")
    manifest = {
        "schema": "cross_venue_calendar_rr_native_clock_repair_v1r1",
        "status": "PASS_NATIVE_CLOCK_KEY_INTERSECTION_REPAIR",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "capture_id": str(spec["capture_id"]),
        "ticker": str(spec["ticker"]),
        "trade_date": str(spec["trade_date"]),
        "role": str(spec["role"]),
        "expiration": str(spec["expiration"]),
        "request_params": params,
        "endpoint": pre.ENDPOINT,
        "source_provenance": provenance,
        "greeks_path": str(spec["greeks_path"]),
        "greeks_sha256": str(spec["greeks_sha256"]),
        "iv_path": str(spec["iv_path"]),
        "iv_sha256": str(spec["iv_sha256"]),
        "raw_sha256": pre.sha256_file(raw_path),
        "parquet_sha256": pre.sha256_file(parquet_path),
        "unilateral_keys_sha256": pre.sha256_file(unilateral_path),
        "rows": int(len(quotes)),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "code_hashes": code_hashes,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        **audit,
    }
    manifest_path.write_bytes(pre.canonical_bytes(manifest))
    rebuilt = pre.normalize_quote_response(json.loads(raw_path.read_bytes()), spec)
    pd.testing.assert_frame_equal(pd.read_parquet(parquet_path), rebuilt, check_dtype=True)
    working.rename(directory)
    return index_row(directory, manifest)


def index_row(directory: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        key: manifest[key]
        for key in (
            "capture_id",
            "ticker",
            "trade_date",
            "role",
            "expiration",
            "rows",
            "greek_rows",
            "iv_rows",
            "shared_key_rows",
            "greek_only_key_rows",
            "iv_only_key_rows",
            "missing_shared_key_rows",
            "native_extra_target_key_rows",
            "revised_bid_ask_rows",
            "crossed_native_rows",
            "raw_sha256",
            "parquet_sha256",
            "unilateral_keys_sha256",
        )
    } | {
        "raw_bytes": int((directory / "response.json").stat().st_size),
        "parquet_bytes": int((directory / "quotes.parquet").stat().st_size),
        "manifest_sha256": pre.sha256_file(directory / "manifest.json"),
    }


def validate_existing_repair(
    spec: dict[str, Any],
    *,
    output: Path,
    runtime: dict[str, Any],
    code_hashes: dict[str, str],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    directory = capture_directory(output, spec)
    paths = {
        name: directory / name
        for name in (
            "response.json",
            "quotes.parquet",
            "unilateral_vintage_keys.csv",
            "manifest.json",
        )
    }
    if not all(path.is_file() for path in paths.values()):
        raise FileNotFoundError(f"incomplete repair: {directory}")
    manifest = json.loads(paths["manifest.json"].read_text())
    identity = {
        "schema": "cross_venue_calendar_rr_native_clock_repair_v1r1",
        "status": "PASS_NATIVE_CLOCK_KEY_INTERSECTION_REPAIR",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "capture_id": str(spec["capture_id"]),
        "ticker": str(spec["ticker"]),
        "trade_date": str(spec["trade_date"]),
        "role": str(spec["role"]),
        "expiration": str(spec["expiration"]),
        "request_params": pre.request_params(spec),
        "endpoint": pre.ENDPOINT,
        "source_provenance": provenance,
        "greeks_path": str(spec["greeks_path"]),
        "greeks_sha256": str(spec["greeks_sha256"]),
        "iv_path": str(spec["iv_path"]),
        "iv_sha256": str(spec["iv_sha256"]),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "code_hashes": code_hashes,
    }
    if any(manifest.get(key) != value for key, value in identity.items()):
        raise AssertionError("existing repair identity changed")
    for file_key, digest_key in (
        ("response.json", "raw_sha256"),
        ("quotes.parquet", "parquet_sha256"),
        ("unilateral_vintage_keys.csv", "unilateral_keys_sha256"),
    ):
        if pre.sha256_file(paths[file_key]) != manifest.get(digest_key):
            raise AssertionError("existing repair hash changed")
    quotes = pre.normalize_quote_response(json.loads(paths["response.json"].read_bytes()), spec)
    pd.testing.assert_frame_equal(pd.read_parquet(paths["quotes.parquet"]), quotes, check_dtype=True)
    audit, unilateral = crosscheck_shared_vintage(quotes, spec)
    stored_unilateral = pd.read_csv(
        paths["unilateral_vintage_keys.csv"],
        dtype={"capture_id": str, "trade_date": str, "expiration": str},
        parse_dates=["timestamp"],
    )
    pd.testing.assert_frame_equal(stored_unilateral, unilateral, check_dtype=False)
    if any(manifest.get(key) != value for key, value in audit.items()):
        raise AssertionError("existing repair vintage audit changed")
    return index_row(directory, manifest)


def capture_or_resume(
    spec: dict[str, Any],
    *,
    output: Path,
    base_url: str,
    provenance: dict[str, Any],
    runtime: dict[str, Any],
    code_hashes: dict[str, str],
    timeout: float,
) -> tuple[dict[str, Any], bool]:
    directory = capture_directory(output, spec)
    working = directory.with_name(directory.name + ".staging")
    if working.exists():
        raise AssertionError(f"interrupted repair requires audit: {working}")
    if directory.exists():
        return validate_existing_repair(
            spec,
            output=output,
            runtime=runtime,
            code_hashes=code_hashes,
            provenance=provenance,
        ), True
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return capture_one(
                spec,
                output=output,
                base_url=base_url,
                provenance=provenance,
                runtime=runtime,
                code_hashes=code_hashes,
                timeout=timeout,
            ), False
        except requests.RequestException as exc:
            last_error = exc
            if directory.exists() or working.exists() or attempt == 2:
                break
            time.sleep(1.0 + attempt)
    raise RuntimeError(f"repair request failed after retries: {last_error}")


def initialize_or_validate_root(
    output: Path,
    *,
    specs: pd.DataFrame,
    contract: dict[str, Any],
    status_raw: bytes,
) -> None:
    state = output / "_state"
    specs_path = state / "repair_specs.csv"
    contract_path = state / "capture_contract.json"
    payload = specs.to_csv(index=False, lineterminator="\n").encode("utf-8")
    expected_contract = {**contract, "repair_specs_sha256": hashlib.sha256(payload).hexdigest()}
    if not output.exists():
        state.mkdir(parents=True)
        specs_path.write_bytes(payload)
        contract_path.write_bytes(pre.canonical_bytes(expected_contract))
        if status_raw:
            (state / "remote_terminal_status.json").write_bytes(status_raw)
        return
    if (
        not specs_path.is_file()
        or not contract_path.is_file()
        or specs_path.read_bytes() != payload
        or json.loads(contract_path.read_text()) != expected_contract
    ):
        raise AssertionError("repair root contract changed")


def seal_repairs(
    output: Path,
    rows: list[dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    index = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date", "role"], kind="stable"
    ).reset_index(drop=True)
    if len(index) != 4 or set(index["capture_id"]) != EXPECTED_REPAIR_IDS:
        raise AssertionError("cannot seal incomplete repair overlay")
    seal_dir = output / "_seal"
    staging = output / "_seal.staging"
    if seal_dir.exists() or staging.exists():
        raise FileExistsError("repair seal already exists")
    staging.mkdir()
    index_path = staging / "capture_index.csv"
    index.to_csv(index_path, index=False, lineterminator="\n")
    unilateral = pd.concat(
        [
            pd.read_csv(
                capture_directory(output, spec) / "unilateral_vintage_keys.csv",
                dtype={"capture_id": str, "trade_date": str, "expiration": str},
            )
            for spec in contract["repair_specs"]
        ],
        ignore_index=True,
    ).sort_values(["capture_id", "timestamp"], kind="stable")
    unilateral_path = staging / "unilateral_vintage_keys.csv"
    unilateral.to_csv(unilateral_path, index=False, lineterminator="\n")
    seal = {
        "schema": "cross_venue_calendar_rr_native_clock_repairs_v1r1_seal",
        "status": "PASS_CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_REPAIRS_V1R1",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "git_commit": contract["git_commit"],
        "code_hashes": contract["code_hashes"],
        "predeclaration_sha256": contract["predeclaration_sha256"],
        "v1_state_sha256": EXPECTED_V1_STATE_SHA256,
        "source_provenance": contract["source_provenance"],
        "captures": 4,
        "shared_key_rows": int(index["shared_key_rows"].sum()),
        "unilateral_key_rows": int(
            index["greek_only_key_rows"].sum() + index["iv_only_key_rows"].sum()
        ),
        "missing_shared_key_rows": int(index["missing_shared_key_rows"].sum()),
        "native_extra_target_key_rows": int(index["native_extra_target_key_rows"].sum()),
        "revised_bid_ask_rows": int(index["revised_bid_ask_rows"].sum()),
        "crossed_native_rows": int(index["crossed_native_rows"].sum()),
        "capture_index_sha256": pre.sha256_file(index_path),
        "unilateral_keys_sha256": pre.sha256_file(unilateral_path),
        "runtime_lock_sha256": contract["runtime_lock_sha256"],
        "runtime_environment_sha256": contract["runtime_environment_sha256"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (staging / "seal.json").write_bytes(pre.canonical_bytes(seal))
    staging.rename(seal_dir)
    return seal


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1-root", type=Path, default=DEFAULT_V1_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-url", default=pre.REMOTE_BASE_URL)
    parser.add_argument("--terminal-jar")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 1 <= args.workers <= 4:
        raise ValueError("workers must be within 1..4")
    commit, code_hashes = pre.committed_code_state(CODE_CLOSURE)
    runtime = assert_runtime_lock(RUNTIME_LOCK)
    specs = load_repair_specs(args.v1_root.resolve())
    provenance, status_raw = pre.source_provenance(
        args.base_url, terminal_jar=args.terminal_jar, timeout=args.timeout
    )
    contract = {
        "schema": "cross_venue_calendar_rr_native_clock_repairs_v1r1_contract",
        "status": "CAPTURE_IN_PROGRESS",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "git_commit": commit,
        "code_hashes": code_hashes,
        "predeclaration_sha256": pre.sha256_file(PREDECLARATION),
        "v1_root": str(args.v1_root.resolve()),
        "v1_state_sha256": EXPECTED_V1_STATE_SHA256,
        "repair_specs": specs.to_dict("records"),
        "source_provenance": provenance,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
    }
    output = args.output_root.resolve()
    initialize_or_validate_root(
        output, specs=specs, contract=contract, status_raw=status_raw
    )
    if (output / "_seal").exists():
        raise FileExistsError("repair overlay is already sealed")
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                capture_or_resume,
                spec,
                output=output,
                base_url=args.base_url,
                provenance=provenance,
                runtime=runtime,
                code_hashes=code_hashes,
                timeout=args.timeout,
            ): spec
            for spec in specs.to_dict("records")
        }
        for future in as_completed(futures):
            spec = futures[future]
            try:
                row, _resumed = future.result()
                rows.append(row)
            except Exception as exc:
                errors.append(
                    {
                        "capture_id": str(spec["capture_id"]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
    if errors:
        (output / "_state/errors.json").write_bytes(pre.canonical_bytes({"errors": errors}))
        raise AssertionError(f"V1R1 repair capture failed: {errors}")
    seal = seal_repairs(output, rows, contract)
    print(json.dumps(seal, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
