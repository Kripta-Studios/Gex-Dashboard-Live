"""Build the outcome-free Massive OPRA historical/live parity gate."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.external_opra_source_intake_common import (  # noqa: E402
    SENSORS,
    NEW_YORK,
    canonical_json_bytes,
    comparison_record,
    normalize_live_event,
    normalize_reference_pages,
    normalize_rest_event,
    parse_session_date,
    read_json,
    read_jsonl,
    sha256_bytes,
    sha256_file,
    strict_predecessor_audit,
    validate_preflight_universe,
    validate_event_sequence,
    write_json,
    write_jsonl,
)
from neural.jepa.wall_surface_flow_environment import (  # noqa: E402
    assert_runtime_lock,
)

DEFAULT_CAPTURE_ROOT = Path("D:/ThetaData/external_opra_source_intake_massive_v1")
DEFAULT_OUTPUT = Path(
    "D:/ThetaData/external_opra_source_intake_massive_gate_v1"
)
PREDECLARATION = PROJECT_ROOT / (
    "research_papers/JEPA/EXTERNAL_OPRA_SOURCE_INTAKE_PREDECLARATION_20260726.md"
)
RUNTIME_LOCK = PROJECT_ROOT / (
    "research_papers/JEPA/requirements-external-opra-source-intake.txt"
)
EXPECTED_PREDECLARATION_SHA256 = (
    "cb6c4aa8a39dc50ae661f3e74856f725f325c3a30121e89a9a5e765705746f92"
)
CODE_CLOSURE = (
    "neural/jepa/external_opra_source_intake_common.py",
    "neural/jepa/capture_external_opra_source_intake.py",
    "neural/jepa/build_external_opra_source_intake_gate.py",
    "neural/jepa/audit_external_opra_source_intake_gate.py",
    "research_papers/JEPA/EXTERNAL_OPRA_SOURCE_INTAKE_PREDECLARATION_20260726.md",
    "research_papers/JEPA/requirements-external-opra-source-intake.txt",
)


def committed_code_state() -> tuple[str, dict[str, str]]:
    if sha256_file(PREDECLARATION) != EXPECTED_PREDECLARATION_SHA256:
        raise AssertionError("source intake predeclaration hash mismatch")
    hashes: dict[str, str] = {}
    for relative in CODE_CLOSURE:
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", relative],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if dirty:
            raise AssertionError(f"source gate requires committed code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    origin = subprocess.run(
        ["git", "rev-parse", "origin/main"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != origin or branch != "main":
        raise AssertionError("source gate requires main with HEAD == origin/main")
    return head, hashes


def _verify_source_manifest(
    root: Path, expected_status: str, expected_code_hashes: Mapping[str, str] | None = None
) -> dict[str, Any]:
    manifest = read_json(root / "manifest.json")
    if manifest.get("status") != expected_status:
        raise AssertionError(f"unexpected source status: {root}")
    if manifest.get("outcome_accessed") is not False:
        raise AssertionError(f"source manifest opened outcomes: {root}")
    if (
        manifest.get("predeclaration_sha256") != EXPECTED_PREDECLARATION_SHA256
        or (
            expected_code_hashes is not None
            and manifest.get("code_hashes") != dict(expected_code_hashes)
        )
    ):
        raise AssertionError(f"source code/predeclaration closure mismatch: {root}")
    index = manifest.get("source_index")
    if not isinstance(index, list):
        raise AssertionError(f"source manifest lacks index: {root}")
    expected_index_sha = sha256_bytes(canonical_json_bytes(index))
    if expected_index_sha != manifest.get("source_index_sha256"):
        raise AssertionError(f"source index digest mismatch: {root}")
    indexed_paths: set[str] = set()
    for row in index:
        relative = str(row["path"])
        if relative in indexed_paths:
            raise AssertionError(f"duplicate source index path: {relative}")
        indexed_paths.add(relative)
        path = root / relative
        if (
            not path.is_file()
            or path.stat().st_size != int(row["size"])
            or sha256_file(path) != row["sha256"]
        ):
            raise AssertionError(f"source hash/size mismatch: {path}")
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual_paths != indexed_paths:
        raise AssertionError(f"unindexed source files: {root}")
    return manifest


def _load_committed_universe(path: Path) -> tuple[list[str], str]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise AssertionError("preflight universe must be inside repository") from exc
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", relative],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise AssertionError("preflight universe must be committed before gate")
    return validate_preflight_universe(read_json(path)), sha256_file(path)


def validate_correction_evidence(path: Path) -> dict[str, Any]:
    value = read_json(path)
    required = {
        "provider",
        "scope",
        "status",
        "source_url",
        "retrieved_at_utc",
        "historical_correction_field",
        "live_correction_semantics",
        "evidence_file",
        "evidence_sha256",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise AssertionError("correction evidence manifest schema mismatch")
    if (
        value["provider"] != "Massive"
        or value["scope"] != "OPTIONS_TRADES_WEBSOCKET_AND_REST"
        or value["status"] != "PROVIDER_CERTIFIED"
        or value["historical_correction_field"] != "correction"
        or value["live_correction_semantics"]
        not in {"EXPLICIT_FIELD", "REPLAYED_CORRECTED_EVENT_WITH_STABLE_ID"}
    ):
        raise AssertionError("correction evidence contract mismatch")
    parsed = urlsplit(str(value["source_url"]))
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or not (
            parsed.hostname == "massive.com"
            or parsed.hostname.endswith(".massive.com")
        )
    ):
        raise AssertionError("correction evidence is not an official Massive URL")
    retrieved = datetime.fromisoformat(
        str(value["retrieved_at_utc"]).replace("Z", "+00:00")
    )
    if retrieved.tzinfo is None:
        raise AssertionError("correction evidence timestamp lacks timezone")
    evidence_name = str(value["evidence_file"])
    if Path(evidence_name).name != evidence_name:
        raise AssertionError("correction evidence file must be a basename")
    evidence = path.parent / evidence_name
    if (
        not evidence.is_file()
        or evidence.stat().st_size == 0
        or sha256_file(evidence) != value["evidence_sha256"]
    ):
        raise AssertionError("correction evidence raw hash mismatch")
    return {
        "manifest_sha256": sha256_file(path),
        "evidence_sha256": sha256_file(evidence),
        "source_url": value["source_url"],
        "retrieved_at_utc": retrieved.isoformat(),
        "live_correction_semantics": value["live_correction_semantics"],
    }


def _read_paginated_pages(directory: Path) -> list[dict[str, Any]]:
    state = read_json(directory / "state.json")
    files = sorted(directory.glob("page_*.json"))
    if (
        state.get("complete") is not True
        or len(files) != int(state.get("pages_completed", -1))
        or not files
    ):
        raise AssertionError(f"incomplete paginated source: {directory}")
    pages = [json.loads(path.read_bytes()) for path in files]
    if any(not isinstance(page.get("results"), list) for page in pages):
        raise AssertionError(f"provider results missing: {directory}")
    return pages


def _reference(root: Path, session: str) -> list[dict[str, Any]]:
    pages = [
        page
        for sensor in SENSORS
        for page in _read_paginated_pages(root / "reference" / sensor)
    ]
    return normalize_reference_pages(pages, session=session)


def _shadow_events(root: Path, session: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for wrapper in read_jsonl(root / "events.jsonl"):
        payload = wrapper.get("payload")
        if not isinstance(payload, dict):
            raise AssertionError("shadow event wrapper lacks payload")
        rows.append(
            normalize_live_event(
                payload,
                session=session,
                arrival_timestamp_utc=str(wrapper.get("arrival_timestamp_utc", "")),
            )
        )
    validate_event_sequence(rows)
    return rows


def _rest_events(
    root: Path, session: str, contracts: Iterable[str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticker in sorted(contracts):
        contract_root = root / "contracts" / ticker.replace(":", "_")
        for event_kind in ("trade", "quote"):
            for page in _read_paginated_pages(contract_root / event_kind):
                rows.extend(
                    normalize_rest_event(
                        value,
                        event_kind=event_kind,
                        contract_ticker=ticker,
                        session=session,
                    )
                    for value in page["results"]
                )
    rows.sort(
        key=lambda row: (
            row["contract_ticker"],
            row["event_kind"],
            row["sequence_number"],
        )
    )
    validate_event_sequence(rows)
    return rows


def _counter(
    rows: Iterable[Mapping[str, Any]], *, correction_contract_present: bool
) -> Counter[bytes]:
    return Counter(
        canonical_json_bytes(
            comparison_record(
                row, correction_contract_present=correction_contract_present
            )
        )
        for row in rows
    )


def compare_session(
    *,
    capture_root: Path,
    session: str,
    correction_contract_present: bool,
    universe_sha256: str | None = None,
    expected_code_hashes: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    parse_session_date(session)
    shadow_root = capture_root / "shadow" / session
    rest_root = capture_root / "rest" / session
    shadow_manifest = _verify_source_manifest(
        shadow_root,
        "SHADOW_SOURCE_CAPTURED_OUTCOME_FREE",
        expected_code_hashes,
    )
    rest_manifest = _verify_source_manifest(
        rest_root,
        "REST_SOURCE_CAPTURED_OUTCOME_FREE",
        expected_code_hashes,
    )
    if shadow_manifest.get("session") != session or rest_manifest.get("session") != session:
        raise AssertionError(f"session manifest mismatch: {session}")
    if universe_sha256 is not None and (
        shadow_manifest.get("preflight_universe_sha256") != universe_sha256
        or rest_manifest.get("preflight_universe_sha256") != universe_sha256
    ):
        raise AssertionError(f"source universe hash mismatch: {session}")
    shadow_reference = _reference(shadow_root, session)
    rest_reference = _reference(rest_root, session)
    shadow_tickers = [row["ticker"] for row in shadow_reference]
    rest_tickers = [row["ticker"] for row in rest_reference]
    reference_equal = shadow_reference == rest_reference

    live = _shadow_events(shadow_root, session)
    rest = _rest_events(rest_root, session, set(shadow_tickers) | set(rest_tickers))
    live_counter = _counter(
        live, correction_contract_present=correction_contract_present
    )
    rest_counter = _counter(
        rest, correction_contract_present=correction_contract_present
    )
    live_only = live_counter - rest_counter
    rest_only = rest_counter - live_counter
    live_contracts = {row["contract_ticker"] for row in live}
    rest_contracts = {row["contract_ticker"] for row in rest}
    correction_values = sorted(
        {
            int(row["trade_correction"])
            for row in rest
            if row["event_kind"] == "trade" and row["trade_correction"] is not None
        }
    )
    predecessor_live = strict_predecessor_audit(live)
    predecessor_rest = strict_predecessor_audit(rest)
    live_counts = Counter(
        (str(row["underlying"]), str(row["event_kind"])) for row in live
    )
    rest_counts = Counter(
        (str(row["underlying"]), str(row["event_kind"])) for row in rest
    )
    required_groups = {
        (sensor, event_kind)
        for sensor in SENSORS
        for event_kind in ("quote", "trade")
    }
    live_manifest = shadow_manifest.get("live")
    if not isinstance(live_manifest, dict):
        raise AssertionError(f"shadow manifest lacks live audit: {session}")
    acknowledged = datetime.fromisoformat(
        str(live_manifest.get("acknowledged_at_utc", "")).replace("Z", "+00:00")
    )
    if acknowledged.tzinfo is None:
        raise AssertionError(f"shadow acknowledgement lacks timezone: {session}")
    session_day = parse_session_date(session)
    subscription_deadline = datetime.combine(
        session_day, time(9, 29, 30), NEW_YORK
    )
    live_arrival_causal = all(
        datetime.fromisoformat(str(row["arrival_timestamp_utc"])).astimezone(timezone.utc)
        >= datetime.fromtimestamp(
            int(row["sip_timestamp_ms"]) / 1000, tz=timezone.utc
        )
        for row in live
    )
    gates = {
        "reference_equal": reference_equal,
        "reference_nonempty_both_sensors": bool(shadow_reference)
        and {row["underlying"] for row in shadow_reference} == set(SENSORS),
        "contract_cap_pass": len(shadow_reference) <= 1000,
        "subscription_ack_before_deadline": acknowledged.astimezone(NEW_YORK)
        <= subscription_deadline,
        "subscription_count_exact": int(live_manifest.get("contracts", -1))
        == len(shadow_reference),
        "nonempty_quotes_and_trades_both_sensors": all(
            live_counts[group] > 0 and rest_counts[group] > 0
            for group in required_groups
        ),
        "live_arrival_not_before_event": live_arrival_causal,
        "correction_contract_present": correction_contract_present,
        "rest_corrections_zero_only": set(correction_values).issubset({0}),
        "event_multiset_equal": not live_only and not rest_only,
        "live_contract_subset_reference": live_contracts.issubset(set(shadow_tickers)),
        "rest_contract_subset_reference": rest_contracts.issubset(set(rest_tickers)),
        "strict_predecessor_census_equal": predecessor_live == predecessor_rest,
    }
    status = (
        "PASS_SESSION_HISTORICAL_LIVE_PARITY"
        if all(gates.values())
        else "FAILED_SESSION_HISTORICAL_LIVE_PARITY"
    )
    summary = {
        "session": session,
        "status": status,
        "gates": gates,
        "shadow_reference_contracts": len(shadow_reference),
        "rest_reference_contracts": len(rest_reference),
        "live_events": len(live),
        "rest_events": len(rest),
        "live_only_events": sum(live_only.values()),
        "rest_only_events": sum(rest_only.values()),
        "rest_correction_values": correction_values,
        "live_event_counts": {
            f"{sensor}_{kind}": live_counts[(sensor, kind)]
            for sensor, kind in sorted(required_groups)
        },
        "rest_event_counts": {
            f"{sensor}_{kind}": rest_counts[(sensor, kind)]
            for sensor, kind in sorted(required_groups)
        },
        "live_predecessor_audit": predecessor_live,
        "rest_predecessor_audit": predecessor_rest,
    }
    return summary, live, rest


def validate_sessions(sessions: Iterable[str]) -> list[str]:
    values = list(sessions)
    if len(values) != 5 or values != sorted(set(values)):
        raise AssertionError("preflight requires exactly five ordered unique sessions")
    dates = [parse_session_date(value) for value in values]
    if any(value.weekday() >= 5 for value in dates):
        raise AssertionError("preflight session cannot be a weekend")
    return values


def build_gate(
    *,
    capture_root: Path,
    output: Path,
    universe: Path,
    correction_evidence: Path,
) -> dict[str, Any]:
    head, code_hashes = committed_code_state()
    runtime = assert_runtime_lock(RUNTIME_LOCK)
    selected, universe_sha = _load_committed_universe(universe)
    correction = validate_correction_evidence(correction_evidence)
    if output.exists():
        raise AssertionError(f"immutable gate output already exists: {output}")
    staging = output.with_name(output.name + ".staging")
    if staging.exists():
        raise AssertionError(f"gate stager already exists: {staging}")
    staging.mkdir(parents=True)

    session_summaries: list[dict[str, Any]] = []
    all_live: list[dict[str, Any]] = []
    all_rest: list[dict[str, Any]] = []
    for session in selected:
        summary, live, rest = compare_session(
            capture_root=capture_root,
            session=session,
            correction_contract_present=True,
            universe_sha256=universe_sha,
            expected_code_hashes=code_hashes,
        )
        session_summaries.append(summary)
        all_live.extend(live)
        all_rest.extend(rest)
    status = (
        "PASS_OUTCOME_FREE_EXTERNAL_OPRA_SOURCE_GATE"
        if all(
            row["status"] == "PASS_SESSION_HISTORICAL_LIVE_PARITY"
            for row in session_summaries
        )
        else "FAILED_OUTCOME_FREE_EXTERNAL_OPRA_SOURCE_GATE"
    )
    write_jsonl(staging / "canonical_live_events.jsonl", all_live)
    write_jsonl(staging / "canonical_rest_events.jsonl", all_rest)
    write_json(staging / "session_summaries.json", session_summaries)
    artifacts = [
        path
        for path in sorted(staging.rglob("*"))
        if path.is_file() and path.name != "summary.json"
    ]
    artifact_index = [
        {
            "path": path.relative_to(staging).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in artifacts
    ]
    result = {
        "status": status,
        "provider": "Massive",
        "sessions": selected,
        "session_summaries": session_summaries,
        "preflight_universe_sha256": universe_sha,
        "correction_evidence": correction,
        "live_events": len(all_live),
        "rest_events": len(all_rest),
        "artifact_index": artifact_index,
        "artifact_index_sha256": sha256_bytes(canonical_json_bytes(artifact_index)),
        "git_commit": head,
        "code_hashes": code_hashes,
        "runtime": runtime,
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "outcome_accessed": False,
        "economic_features_created": False,
        "model_created": False,
    }
    write_json(staging / "summary.json", result)
    staging.replace(output)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-root", type=Path, default=DEFAULT_CAPTURE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--correction-evidence", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_gate(
        capture_root=args.capture_root,
        output=args.output,
        universe=args.universe,
        correction_evidence=args.correction_evidence,
    )
    print(json.dumps(result, sort_keys=True))
    if result["status"] != "PASS_OUTCOME_FREE_EXTERNAL_OPRA_SOURCE_GATE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
