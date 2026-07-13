"""Repair frozen HTTP 472 windows and seal the full H-IBQDYN1 capture."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.build_wall_quote_tick_dynamics_sidecar import (  # noqa: E402
    sha256_file,
)
from neural.jepa.capture_h_ibqdyn1_full import (  # noqa: E402
    CODE_CLOSURE as LEGACY_CODE_CLOSURE,
    candidate_csv,
)
from neural.jepa.capture_h_ibqdyn1_tick_preflight import (  # noqa: E402
    EXPECTED_ELIGIBLE_EVENTS,
    EXPECTED_ELIGIBLE_ID_SHA256,
    EXPECTED_FULL_CONTRACTS,
    EXPECTED_PROOF_MANIFEST_SHA256,
    EXPECTED_PROOF_SHA256,
    EXPECTED_SAMPLE_SHA256,
    OUTPUT_COLUMNS,
    RUNTIME_LOCK,
    canonical_bytes,
    capture_contract,
    contract_index_row,
    load_frozen_contracts,
    request_params,
    sha256_bytes,
    source_provenance,
    validate_contract_directory,
)
from neural.jepa.wall_surface_flow_environment import (  # noqa: E402
    assert_runtime_lock,
)

SEALER_PATH = "neural/jepa/seal_h_ibqdyn1_full_capture_v1r1.py"
NO_DATA_AMENDMENT = "research_papers/JEPA/H_IBQDYN1_HTTP472_NO_DATA_AMENDMENT.md"
SEALER_CODE_CLOSURE = LEGACY_CODE_CLOSURE + (SEALER_PATH, NO_DATA_AMENDMENT)
NO_DATA_BODY = b"No data found for your request"
NO_DATA_BODY_SHA256 = "101a4aa84466574e08fbb09d1405a816323a4674fd107dc28f3f0d29e3e3708c"
FIRST_ATTEMPT_ERRORS_SHA256 = (
    "e4dc58192b18944778fe819a397d03c9e4e5fb2a29870b7de63ca1b500859af7"
)
EXPECTED_NO_DATA_ID_SHA256 = (
    "4a44551fde020af61174b9e70162122441b6c5736f3e274b988f6f66104238a7"
)
EXPECTED_NO_DATA_CONTRACTS: dict[str, dict[str, Any]] = {
    "ead903c57890cd8a477a2ac0": {
        "event_id": "60d8c2b0bec9c102a94d851b",
        "ticker": "SPXW",
        "trade_date": "20231025",
        "decision_dt": "2023-10-25T10:35:00",
        "right": "CALL",
        "strike": 4230.0,
    },
    "0832f62f2c76c32275bc5f36": {
        "event_id": "60d8c2b0bec9c102a94d851b",
        "ticker": "SPXW",
        "trade_date": "20231025",
        "decision_dt": "2023-10-25T10:35:00",
        "right": "PUT",
        "strike": 4185.0,
    },
    "311e42908cc0dc01befb5660": {
        "event_id": "f4a0e57699fbd8b67cee8937",
        "ticker": "SPY",
        "trade_date": "20231025",
        "decision_dt": "2023-10-25T10:35:00",
        "right": "CALL",
        "strike": 421.0,
    },
    "1785ce6e2835a5fa7abca84d": {
        "event_id": "f4a0e57699fbd8b67cee8937",
        "ticker": "SPY",
        "trade_date": "20231025",
        "decision_dt": "2023-10-25T10:35:00",
        "right": "PUT",
        "strike": 418.0,
    },
}
EXPECTED_LEGACY_CAPTURE_CODE_HASHES = {
    "neural/jepa/build_h_ibqdyn1_feasibility.py": (
        "e181d176ed62db688fcf9cab6857700193f882a5fac9c735e5434bafcecf1c35"
    ),
    "neural/jepa/build_wall_native_quote_sidecar.py": (
        "c729990f1b0e460ab13731040df20087d177ee4cbdb8aa33750d977563633f23"
    ),
    "neural/jepa/build_wall_quote_tick_dynamics_sidecar.py": (
        "3f694052c6fa7b2858f8114008c686727cd824c81f6e2e4cafc998119e9af733"
    ),
    "neural/jepa/capture_h_ibqdyn1_full.py": (
        "e05d176bc6583f1e8bf2ff03311fa2454648b29d8806e4d0e3c128f30d2c26c9"
    ),
    "neural/jepa/capture_h_ibqdyn1_tick_preflight.py": (
        "afb3330d5aa8a7daf2dc36f2472cba657f82c0dd54808e118679a104258994f1"
    ),
    "neural/jepa/h_ibqdyn1_features.py": (
        "84d49f2d8aabdcf95ac1628802406d43fd27e2107b70af56200e25a33dbb6fd4"
    ),
    "neural/jepa/wall_surface_flow_environment.py": (
        "b21a771a2982290d6c67513700f81d18de0e6c08c6ad9aba772d5305093d06ef"
    ),
    "research_papers/JEPA/H_IBQDYN1_2026_FINAL_FIT_AMENDMENT.md": (
        "a890100f8cd3b5f362421522edfda1b93b722a6b7c5b89005dad474a901dd82a"
    ),
    "research_papers/JEPA/H_IBQDYN1_FEASIBILITY_PREDECLARATION.md": (
        "4e1d025bba23ee98155b971490a6f80b71b49b440887271e76b9f5ca2def6b37"
    ),
    "research_papers/JEPA/H_IBQDYN1_FEATURE_SEMANTICS_CLARIFICATION.md": (
        "e6e516efdd6c977ebc352fae0e3fe1fde4a11560d3838911aebd273761cbc8fc"
    ),
    "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt": (
        "f026bfb512e17dfc1daaaecf998ba77a560aba83f1fdbf0c3a36136e33eeff7d"
    ),
    (
        "research_papers/JEPA/results/_diagnostics/"
        "h_ibqdyn1_listing_feasibility_202208_202512_v1/manifest.json"
    ): "2095c75dce813368ea13a9fcaf0170c3087db806eec13212b069884119c867e9",
}


def newline_hash(values: list[str]) -> str:
    payload = "".join(f"{value}\n" for value in sorted(values)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def committed_code_state() -> tuple[str, dict[str, str]]:
    hashes: dict[str, str] = {}
    for relative in SEALER_CODE_CLOSURE:
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
            raise AssertionError(
                f"H-IBQDYN1 V1R1 sealer requires clean code: {relative}"
            )
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    for relative, expected in EXPECTED_LEGACY_CAPTURE_CODE_HASHES.items():
        if (
            relative not in {SEALER_PATH, NO_DATA_AMENDMENT}
            and hashes.get(relative) != expected
        ):
            raise AssertionError(f"legacy H-IBQDYN1 capture code changed: {relative}")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, hashes


def contract_directory(root: Path, contract: dict[str, Any]) -> Path:
    return (
        root
        / str(contract["ticker"])
        / str(contract["trade_date"])
        / str(contract["event_id"])
        / str(contract["right"]).lower()
    )


def validate_candidate_contracts(path: Path, contracts: pd.DataFrame) -> None:
    stored = pd.read_csv(path, dtype={"trade_date": str}, keep_default_na=False)
    expected = pd.read_csv(
        io.StringIO(candidate_csv(contracts)),
        dtype={"trade_date": str},
        keep_default_na=False,
    )
    try:
        pd.testing.assert_frame_equal(stored, expected, check_exact=True)
    except AssertionError as exc:
        raise AssertionError("H-IBQDYN1 candidate contracts changed") from exc
    if (
        len(stored) != EXPECTED_FULL_CONTRACTS
        or stored["contract_id"].duplicated().any()
    ):
        raise AssertionError("H-IBQDYN1 candidate contract identity invalid")


def assert_expected_no_data_contract(contract: dict[str, Any]) -> None:
    contract_id = str(contract["contract_id"])
    expected = EXPECTED_NO_DATA_CONTRACTS.get(contract_id)
    observed = {
        "event_id": str(contract["event_id"]),
        "ticker": str(contract["ticker"]),
        "trade_date": str(contract["trade_date"]),
        "decision_dt": pd.Timestamp(contract["decision_dt"]).isoformat(),
        "right": str(contract["right"]),
        "strike": float(contract["strike"]),
    }
    if expected is None or observed != expected:
        raise AssertionError("unapproved H-IBQDYN1 missing contract")


def assert_first_attempt_errors(path: Path) -> bytes:
    if sha256_file(path) != FIRST_ATTEMPT_ERRORS_SHA256:
        raise AssertionError("H-IBQDYN1 first-attempt error file changed")
    raw = path.read_bytes()
    payload = json.loads(raw)
    errors = payload.get("errors")
    if not isinstance(errors, list):
        raise AssertionError("invalid H-IBQDYN1 first-attempt errors")
    ids = [str(item.get("contract_id", "")) for item in errors]
    if (
        len(ids) != len(EXPECTED_NO_DATA_CONTRACTS)
        or set(ids) != set(EXPECTED_NO_DATA_CONTRACTS)
        or newline_hash(ids) != EXPECTED_NO_DATA_ID_SHA256
        or any("472 Client Error" not in str(item.get("error", "")) for item in errors)
    ):
        raise AssertionError("H-IBQDYN1 first-attempt error inventory changed")
    return raw


def _stable_provenance_matches(stored: dict[str, Any], current: dict[str, Any]) -> bool:
    fields = (
        "kind",
        "base_url",
        "status_endpoint",
        "status_value",
        "historical_provenance",
        "live_parity",
    )
    return all(stored.get(field) == current.get(field) for field in fields)


def validate_no_data_directory(
    directory: Path,
    contract: dict[str, Any],
    *,
    base_url: str,
    provenance: dict[str, Any],
    sealer_code_hashes: dict[str, str],
    runtime: dict[str, Any],
    reference_schema: pa.Schema,
) -> dict[str, Any]:
    assert_expected_no_data_contract(contract)
    raw_path = directory / "response.txt"
    parquet_path = directory / "ticks.parquet"
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw = raw_path.read_bytes()
    stored_schema = pq.read_schema(parquet_path)
    schema_profile = [[field.name, str(field.type)] for field in reference_schema]
    if (
        manifest.get("schema") != "h_ibqdyn1_http472_no_data_contract_v1"
        or manifest.get("status") != "PASS_H_IBQDYN1_HTTP472_NO_DATA_CONTRACT"
        or manifest.get("capture_kind") != "HTTP_472_NO_DATA"
        or manifest.get("outcome_free") is not True
        or manifest.get("holdout_2026_used") is not False
        or manifest.get("production_modified") is not False
        or manifest.get("contract_id") != str(contract["contract_id"])
        or manifest.get("event_id") != str(contract["event_id"])
        or manifest.get("ticker") != str(contract["ticker"])
        or manifest.get("trade_date") != str(contract["trade_date"])
        or manifest.get("decision_dt")
        != pd.Timestamp(contract["decision_dt"]).isoformat()
        or manifest.get("right") != str(contract["right"])
        or float(manifest.get("strike", float("nan"))) != float(contract["strike"])
        or manifest.get("base_url") != base_url.rstrip("/")
        or manifest.get("request_params") != request_params(contract)
        or not _stable_provenance_matches(
            manifest.get("source_provenance", {}), provenance
        )
        or manifest.get("legacy_capture_code_hashes")
        != EXPECTED_LEGACY_CAPTURE_CODE_HASHES
        or manifest.get("sealer_code_hashes") != sealer_code_hashes
        or manifest.get("runtime_lock_sha256") != runtime["lock_sha256"]
        or manifest.get("runtime_environment_sha256") != runtime["environment_sha256"]
        or int(manifest.get("http_status", -1)) != 472
        or manifest.get("http_error_name") != "NO_DATA"
        or raw != NO_DATA_BODY
        or sha256_bytes(raw) != NO_DATA_BODY_SHA256
        or manifest.get("raw_sha256") != sha256_file(raw_path)
        or int(manifest.get("raw_bytes", -1)) != raw_path.stat().st_size
        or manifest.get("parquet_sha256") != sha256_file(parquet_path)
        or int(manifest.get("parquet_bytes", -1)) != parquet_path.stat().st_size
        or int(manifest.get("rows", -1)) != 0
        or manifest.get("response_schema") != schema_profile
        or manifest.get("response_schema_sha256")
        != sha256_bytes(canonical_bytes({"schema": schema_profile}))
        or stored_schema != reference_schema
    ):
        raise AssertionError("invalid immutable H-IBQDYN1 HTTP 472 capture")
    stored = pd.read_parquet(parquet_path)
    if len(stored) != 0 or list(stored.columns) != list(OUTPUT_COLUMNS):
        raise AssertionError("invalid H-IBQDYN1 HTTP 472 empty parquet")
    return manifest


def no_data_index_row(
    contract: dict[str, Any], directory: Path, manifest: dict[str, Any]
) -> dict[str, Any]:
    raw_path = directory / "response.txt"
    parquet_path = directory / "ticks.parquet"
    manifest_path = directory / "manifest.json"
    return {
        "contract_id": str(contract["contract_id"]),
        "event_id": str(contract["event_id"]),
        "ticker": str(contract["ticker"]),
        "trade_date": str(contract["trade_date"]),
        "decision_dt": pd.Timestamp(contract["decision_dt"]).isoformat(),
        "right": str(contract["right"]),
        "strike": float(contract["strike"]),
        "capture_kind": "HTTP_472_NO_DATA",
        "contract_dir": str(directory),
        "raw_path": str(raw_path),
        "raw_sha256": manifest["raw_sha256"],
        "parquet_path": str(parquet_path),
        "parquet_sha256": manifest["parquet_sha256"],
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "provenance_sha256": sha256_bytes(
            canonical_bytes(manifest["source_provenance"])
        ),
        "rows": 0,
        "raw_bytes": int(manifest["raw_bytes"]),
        "parquet_bytes": int(manifest["parquet_bytes"]),
    }


def _empty_table(schema: pa.Schema) -> pa.Table:
    return pa.Table.from_arrays(
        [pa.array([], type=field.type) for field in schema], schema=schema
    )


def materialize_no_data_contract(
    contract: dict[str, Any],
    *,
    root: Path,
    base_url: str,
    provenance: dict[str, Any],
    sealer_code_hashes: dict[str, str],
    runtime: dict[str, Any],
    reference_schema: pa.Schema,
    timeout: float,
    requester: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    assert_expected_no_data_contract(contract)
    directory = contract_directory(root, contract)
    if directory.exists():
        manifest = validate_no_data_directory(
            directory,
            contract,
            base_url=base_url,
            provenance=provenance,
            sealer_code_hashes=sealer_code_hashes,
            runtime=runtime,
            reference_schema=reference_schema,
        )
        return no_data_index_row(contract, directory, manifest)
    working = directory.with_name(directory.name + ".staging")
    if working.exists():
        raise FileExistsError(f"partial H-IBQDYN1 no-data staging exists: {working}")
    params = request_params(contract)
    responses = []
    for attempt in range(3):
        response = requester(
            base_url.rstrip("/") + "/option/history/quote",
            params=params,
            headers={"Accept-Encoding": "identity"},
            timeout=timeout,
        )
        if int(response.status_code) == 200:
            cached = lambda *args, **kwargs: response  # noqa: E731
            manifest = capture_contract(
                contract,
                staging_root=root,
                base_url=base_url,
                provenance=provenance,
                code_hashes=EXPECTED_LEGACY_CAPTURE_CODE_HASHES,
                runtime=runtime,
                timeout=timeout,
                requester=cached,
            )
            row = contract_index_row(contract, directory, manifest)
            row["capture_kind"] = "HTTP_200_TICKS"
            return row
        if int(response.status_code) != 472 or bytes(response.content) != NO_DATA_BODY:
            raise AssertionError(
                "H-IBQDYN1 frozen no-data request returned an unexpected response"
            )
        responses.append(response)
        if attempt < 2:
            time.sleep(1.0 + attempt)
    if len(responses) != 3:
        raise AssertionError("H-IBQDYN1 no-data retry count changed")
    response = responses[-1]
    working.mkdir(parents=True, exist_ok=False)
    raw_path = working / "response.txt"
    parquet_path = working / "ticks.parquet"
    raw_path.write_bytes(bytes(response.content))
    pq.write_table(_empty_table(reference_schema), parquet_path)
    schema_profile = [[field.name, str(field.type)] for field in reference_schema]
    manifest = {
        "schema": "h_ibqdyn1_http472_no_data_contract_v1",
        "status": "PASS_H_IBQDYN1_HTTP472_NO_DATA_CONTRACT",
        "capture_kind": "HTTP_472_NO_DATA",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "contract_id": str(contract["contract_id"]),
        "event_id": str(contract["event_id"]),
        "ticker": str(contract["ticker"]),
        "trade_date": str(contract["trade_date"]),
        "decision_dt": pd.Timestamp(contract["decision_dt"]).isoformat(),
        "nearest_level_name": str(contract["nearest_level_name"]),
        "bucket": str(contract["bucket"]),
        "right": str(contract["right"]),
        "strike": float(contract["strike"]),
        "base_url": base_url.rstrip("/"),
        "request_params": params,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_provenance": provenance,
        "legacy_capture_code_hashes": EXPECTED_LEGACY_CAPTURE_CODE_HASHES,
        "sealer_code_hashes": sealer_code_hashes,
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "http_status": 472,
        "http_error_name": "NO_DATA",
        "http_headers": dict(
            sorted((str(key), str(value)) for key, value in response.headers.items())
        ),
        "server_date": str(response.headers.get("Date", "")),
        "raw_sha256": sha256_file(raw_path),
        "raw_bytes": int(raw_path.stat().st_size),
        "parquet_sha256": sha256_file(parquet_path),
        "parquet_bytes": int(parquet_path.stat().st_size),
        "rows": 0,
        "first_timestamp": None,
        "last_timestamp": None,
        "response_schema": schema_profile,
        "response_schema_sha256": sha256_bytes(
            canonical_bytes({"schema": schema_profile})
        ),
    }
    manifest_path = working / "manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    manifest = validate_no_data_directory(
        working,
        contract,
        base_url=base_url,
        provenance=provenance,
        sealer_code_hashes=sealer_code_hashes,
        runtime=runtime,
        reference_schema=reference_schema,
    )
    directory.parent.mkdir(parents=True, exist_ok=True)
    working.rename(directory)
    return no_data_index_row(contract, directory, manifest)


def _regular_index_row(
    contract: dict[str, Any],
    directory: Path,
    *,
    base_url: str,
    provenance: dict[str, Any],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    manifest = validate_contract_directory(
        directory,
        contract,
        base_url=base_url,
        provenance=provenance,
        code_hashes=EXPECTED_LEGACY_CAPTURE_CODE_HASHES,
        runtime=runtime,
    )
    row = contract_index_row(contract, directory, manifest)
    row["capture_kind"] = "HTTP_200_TICKS"
    return row


def process_contract(
    contract: dict[str, Any],
    *,
    root: Path,
    base_url: str,
    provenance: dict[str, Any],
    sealer_code_hashes: dict[str, str],
    runtime: dict[str, Any],
    reference_schema: pa.Schema,
    timeout: float,
) -> dict[str, Any]:
    directory = contract_directory(root, contract)
    if directory.exists():
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("capture_kind") == "HTTP_472_NO_DATA":
            validated = validate_no_data_directory(
                directory,
                contract,
                base_url=base_url,
                provenance=provenance,
                sealer_code_hashes=sealer_code_hashes,
                runtime=runtime,
                reference_schema=reference_schema,
            )
            return no_data_index_row(contract, directory, validated)
        return _regular_index_row(
            contract,
            directory,
            base_url=base_url,
            provenance=provenance,
            runtime=runtime,
        )
    return materialize_no_data_contract(
        contract,
        root=root,
        base_url=base_url,
        provenance=provenance,
        sealer_code_hashes=sealer_code_hashes,
        runtime=runtime,
        reference_schema=reference_schema,
        timeout=timeout,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--terminal-jar")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= int(args.workers) <= 4:
        raise ValueError("H-IBQDYN1 V1R1 workers must be within 1..4")
    root = Path(args.output_root).resolve()
    seal = root / "_seal"
    seal_staging = root / "_seal.staging"
    if seal.exists() or seal_staging.exists():
        raise FileExistsError("immutable H-IBQDYN1 V1R1 seal target exists")
    commit, sealer_code_hashes = committed_code_state()
    runtime = assert_runtime_lock(PROJECT_ROOT / RUNTIME_LOCK)
    contracts = load_frozen_contracts(sample_only=False)
    if len(contracts) != EXPECTED_FULL_CONTRACTS:
        raise AssertionError("H-IBQDYN1 full contract universe changed")
    candidates_path = root / "candidate_contracts.csv"
    validate_candidate_contracts(candidates_path, contracts)
    first_attempt_raw = assert_first_attempt_errors(root / "errors_latest.json")
    provenance, status_raw = source_provenance(
        args.base_url,
        terminal_jar=args.terminal_jar,
        timeout=float(args.timeout),
    )
    regular_parquet = next(
        path
        for path in root.rglob("ticks.parquet")
        if "staging" not in str(path).lower()
    )
    reference_schema = pq.read_schema(regular_parquet)
    if list(reference_schema.names) != list(OUTPUT_COLUMNS):
        raise AssertionError("H-IBQDYN1 reference tick schema changed")
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=int(args.workers)) as pool:
        futures = {
            pool.submit(
                process_contract,
                contract,
                root=root,
                base_url=args.base_url,
                provenance=provenance,
                sealer_code_hashes=sealer_code_hashes,
                runtime=runtime,
                reference_schema=reference_schema,
                timeout=float(args.timeout),
            ): contract
            for contract in contracts.to_dict("records")
        }
        for count, future in enumerate(as_completed(futures), start=1):
            contract = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                errors.append(
                    {
                        "contract_id": str(contract["contract_id"]),
                        "ticker": str(contract["ticker"]),
                        "trade_date": str(contract["trade_date"]),
                        "right": str(contract["right"]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            if count % 100 == 0 or count == len(contracts):
                print(
                    f"[H-IBQDYN1_SEAL_V1R1] contracts={count}/{len(contracts)} "
                    f"errors={len(errors)}",
                    flush=True,
                )
    if errors or len(rows) != EXPECTED_FULL_CONTRACTS:
        raise AssertionError(f"H-IBQDYN1 V1R1 revalidation failed: {errors[:20]}")
    index = (
        pd.DataFrame(rows)
        .sort_values(
            ["ticker", "trade_date", "decision_dt", "event_id", "right"],
            kind="stable",
        )
        .reset_index(drop=True)
    )
    no_data = index["capture_kind"].eq("HTTP_472_NO_DATA")
    no_data_ids = index.loc[no_data, "contract_id"].astype(str).tolist()
    staging_dirs = [
        path
        for path in root.rglob("*")
        if path.is_dir() and "staging" in path.name.lower()
    ]
    if (
        len(index) != EXPECTED_FULL_CONTRACTS
        or index["contract_id"].duplicated().any()
        or index["event_id"].nunique() != EXPECTED_ELIGIBLE_EVENTS
        or index["rows"].lt(0).any()
        or set(index["capture_kind"]) != {"HTTP_200_TICKS", "HTTP_472_NO_DATA"}
        or set(no_data_ids) != set(EXPECTED_NO_DATA_CONTRACTS)
        or newline_hash(no_data_ids) != EXPECTED_NO_DATA_ID_SHA256
        or not index.loc[no_data, "rows"].eq(0).all()
        or int(index["rows"].eq(0).sum()) != len(EXPECTED_NO_DATA_CONTRACTS)
        or staging_dirs
    ):
        raise AssertionError("H-IBQDYN1 V1R1 final capture index invalid")
    seal_staging.mkdir(parents=True, exist_ok=False)
    index_path = seal_staging / "contract_index.csv"
    index.to_csv(index_path, index=False)
    (seal_staging / "first_attempt_errors.json").write_bytes(first_attempt_raw)
    if status_raw:
        (seal_staging / "remote_terminal_status.json").write_bytes(status_raw)
    manifest = {
        "schema": "h_ibqdyn1_full_capture_seal_v1r1",
        "status": "PASS_H_IBQDYN1_FULL_CAPTURE",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "git_commit": commit,
        "code_hashes": sealer_code_hashes,
        "legacy_capture_code_hashes": EXPECTED_LEGACY_CAPTURE_CODE_HASHES,
        "proof_manifest_sha256": EXPECTED_PROOF_MANIFEST_SHA256,
        "proof_sha256": EXPECTED_PROOF_SHA256,
        "sample_sha256": EXPECTED_SAMPLE_SHA256,
        "eligible_event_id_sha256": EXPECTED_ELIGIBLE_ID_SHA256,
        "eligible_events": EXPECTED_ELIGIBLE_EVENTS,
        "contracts": int(len(index)),
        "rows": int(index["rows"].sum()),
        "call_rows": int(index.loc[index["right"].eq("CALL"), "rows"].sum()),
        "put_rows": int(index.loc[index["right"].eq("PUT"), "rows"].sum()),
        "zero_row_contracts": int(index["rows"].eq(0).sum()),
        "no_data_contracts": int(no_data.sum()),
        "no_data_contract_ids_sha256": newline_hash(no_data_ids),
        "no_data_body_sha256": NO_DATA_BODY_SHA256,
        "unresolved_errors": 0,
        "raw_bytes": int(index["raw_bytes"].sum()),
        "parquet_bytes": int(index["parquet_bytes"].sum()),
        "candidate_contracts_sha256": sha256_file(candidates_path),
        "contract_index_sha256": sha256_file(index_path),
        "first_attempt_errors_sha256": FIRST_ATTEMPT_ERRORS_SHA256,
        "provenance_evidence_sha256": sorted(
            index["provenance_sha256"].astype(str).unique().tolist()
        ),
        "source_identity": {
            field: provenance.get(field)
            for field in (
                "kind",
                "base_url",
                "status_endpoint",
                "status_value",
                "historical_provenance",
                "live_parity",
            )
        },
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "errors": [],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (seal_staging / "manifest.json").write_bytes(canonical_bytes(manifest))
    seal_staging.rename(seal)
    (root / "errors_latest.json").unlink()
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
