"""Resource-only continuation of the frozen monthly validation runner."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import os
import sys
import time

import run_monthly_walk_forward as monthly

shared = monthly.shared
MIN_FREE_BYTES = 2_000_000_000
RUN_CONTRACT_SHA = "7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f"
ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018")
SCIENTIFIC_ROOT = ROOT / "monthly_walk_forward_v1"
HERE = Path(__file__).resolve().parent
STATUS = "PASS_MONTHLY_RESOURCE_OVERLAY_REVIEW"


def utc():
    return datetime.now(timezone.utc).isoformat()


def resource_observation():
    return dict(
        available_ram_bytes=int(shared.psutil.virtual_memory().available),
        free_commit_bytes=int(shared.free_commit_bytes()),
        utc=utc(),
    )


def wait_resources(out, runtime_root):
    """Real measurements; exactly decimal 2 GB for both resource constraints."""
    while True:
        observation = resource_observation()
        ready = (
            observation["available_ram_bytes"] >= MIN_FREE_BYTES
            and observation["free_commit_bytes"] >= MIN_FREE_BYTES
        )
        record = dict(
            stage="RESOURCE_OVERLAY_READY" if ready else "WAITING_RESOURCES_2GB",
            threshold_bytes=MIN_FREE_BYTES,
            scientific_root=str(Path(out).resolve()),
            **observation,
        )
        # A distinct immutable record per observation also preserves successful gates.
        destination = runtime_root / "observations" / (str(time.time_ns()) + ".json")
        shared.atomic_json(destination, record)
        print(record, flush=True)
        if ready:
            return
        time.sleep(30)


@contextmanager
def resource_overlay(runtime_root):
    original = shared.wait_resources
    shared.wait_resources = lambda out: wait_resources(out, runtime_root)
    try:
        yield
    finally:
        shared.wait_resources = original


def original_argv():
    return [
        "--engine-root",
        str(ROOT / "session_clock_dataset_v1"),
        "--feature-root",
        str(ROOT / "session_clock_dataset_v1"),
        "--source-audit",
        str(ROOT / "session_clock_dataset_v1_audit/audit.json"),
        "--implementation-review",
        str(HERE / "MONTHLY_WALK_FORWARD_IMPLEMENTATION_REVIEW.json"),
        "--out",
        str(SCIENTIFIC_ROOT),
        "--stage",
        "validation",
    ]


def review_expectations():
    names = (
        "run_monthly_resource_overlay.py",
        "test_monthly_resource_overlay.py",
        "MONTHLY_RESOURCE_OVERLAY_SPEC.md",
    )
    return dict(
        files={name: shared.sha(HERE / name) for name in names},
        original_dependencies=monthly.dependency_hashes(),
        original_run_contract_sha256=RUN_CONTRACT_SHA,
        threshold_bytes=MIN_FREE_BYTES,
        scope="validation",
        scientific_inputs_changed=False,
    )


def require_review(path):
    digest = shared.sha(path)
    review = shared.read_json(path)
    expected = review_expectations()
    if (
        review.get("status") != STATUS
        or any(review.get(key) != value for key, value in expected.items())
        or shared.sha(path) != digest
        or len(expected["original_dependencies"]) != 11
    ):
        raise ValueError("Exact resource-only review required")
    return expected, digest


def assert_stopped(previous_pid):
    if previous_pid <= 0 or previous_pid == os.getpid():
        raise ValueError("Invalid previous process identity")
    # Conservatively reject even an unrelated reused PID; operator resolves it.
    if shared.psutil.pid_exists(previous_pid):
        raise ValueError("Previous PID still exists; do not transition a live fit")


def existing_checkpoints(root, binding):
    artifacts = monthly.Artifacts(root, binding)
    for path in (root / "models").glob("*.fit_started.json"):
        name = path.name.removesuffix(".fit_started.json")
        if not artifacts.complete("models/" + name):
            raise ValueError(
                "Incomplete started fit preserved; automatic refit forbidden"
            )
    files = set(root.rglob("*.complete.json"))
    files.update((root / "models").glob("*.txt"))
    files.update((root / "models").glob("*.fit_started.json"))
    files.update((root / "executed_code").glob("*"))
    files.add(root / "run_contract.json")
    return {
        str(path.resolve()): shared.sha(path)
        for path in sorted(files)
        if path.is_file()
    }


def verify_hashes(hashes):
    for name, digest in hashes.items():
        if shared.sha(Path(name)) != digest:
            raise ValueError("Preserved evidence changed: " + name)


def guard_runtime_root(path):
    resolved = path.resolve()
    for protected in (SCIENTIFIC_ROOT, ROOT / "session_clock_dataset_v1", HERE):
        protected = protected.resolve()
        if (
            resolved == protected
            or resolved.is_relative_to(protected)
            or protected.is_relative_to(resolved)
        ):
            raise ValueError("Runtime receipts require a separate directory")


def run(runtime_root, review_path, previous_pid):
    guard_runtime_root(runtime_root)
    if runtime_root.exists():
        raise ValueError(
            "Use a new runtime attempt directory; preserve previous receipts"
        )
    assert_stopped(previous_pid)
    authority, review_hash = require_review(review_path)
    contract_path = SCIENTIFIC_ROOT / "run_contract.json"
    if shared.sha(contract_path) != RUN_CONTRACT_SHA:
        raise ValueError("Original monthly run contract differs")
    contract = shared.read_json(contract_path)
    if contract["dependencies"] != authority["original_dependencies"]:
        raise ValueError("Original dependencies differ")
    preserved = existing_checkpoints(SCIENTIFIC_ROOT, RUN_CONTRACT_SHA)
    runtime_root.mkdir(parents=True)
    # Own files are copied and checked before durable publication. Scientific snapshots
    # remain under the original runner's unchanged admission and resume checks.
    snapshots = {}
    for name, digest in authority["files"].items():
        destination = runtime_root / "executed_code" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".partial")
        temporary.write_bytes((HERE / name).read_bytes())
        if shared.sha(temporary) != digest:
            raise ValueError("Overlay code changed while copying")
        shared.durable_replace(temporary, destination)
        snapshots[str(destination.resolve())] = digest
    argv = original_argv()
    launch = dict(
        status="MONTHLY_RESOURCE_OVERLAY_STARTED",
        authority=authority,
        runtime_review_path=str(review_path.resolve()),
        runtime_review_sha256=review_hash,
        original_argv=argv,
        original_runner=str(Path(monthly.__file__).resolve()),
        original_pid=previous_pid,
        pid=os.getpid(),
        started_utc=utc(),
        resources=resource_observation(),
        preserved_checkpoints=preserved,
        snapshots=snapshots,
        scientific_inputs_changed=False,
        resource_function="train_causal_rollout.wait_resources only",
    )
    shared.atomic_json(runtime_root / "launch.json", launch)
    original_sys_argv = sys.argv
    started = time.monotonic()
    try:
        sys.argv = [str(Path(monthly.__file__)), *argv]
        with resource_overlay(runtime_root):
            monthly.main()
        verify_hashes(preserved)
        verify_hashes(snapshots)
        if review_expectations() != authority or shared.sha(review_path) != review_hash:
            raise ValueError("Overlay authority changed during execution")
        final = existing_checkpoints(SCIENTIFIC_ROOT, RUN_CONTRACT_SHA)
        members = dict(snapshots)
        members[str((runtime_root / "launch.json").resolve())] = shared.sha(
            runtime_root / "launch.json"
        )
        members.update(
            {
                str(p.resolve()): shared.sha(p)
                for p in sorted((runtime_root / "observations").glob("*.json"))
            }
        )
        shared.atomic_json(
            runtime_root / "completion.json",
            dict(
                status="COMPLETE_MONTHLY_RESOURCE_OVERLAY_VALIDATION",
                completed_utc=utc(),
                seconds=time.monotonic() - started,
                original_run_contract_sha256=RUN_CONTRACT_SHA,
                scientific_inputs_changed=False,
                preserved_checkpoints=preserved,
                final_checkpoints=final,
                runtime_members=members,
                runtime_review_sha256=review_hash,
            ),
        )
    except BaseException as exc:
        shared.atomic_json(
            runtime_root / "failure.json",
            dict(
                status="INTERRUPTED_OR_FAILED_PRESERVED",
                error=repr(exc),
                utc=utc(),
                seconds=time.monotonic() - started,
            ),
        )
        raise
    finally:
        sys.argv = original_sys_argv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--runtime-review", type=Path, required=True)
    parser.add_argument("--previous-pid", type=int, required=True)
    args = parser.parse_args()
    run(args.runtime_root, args.runtime_review, args.previous_pid)


if __name__ == "__main__":
    main()
