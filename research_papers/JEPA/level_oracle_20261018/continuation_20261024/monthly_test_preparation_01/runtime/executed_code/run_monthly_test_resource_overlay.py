"""Resource-only entry to frozen monthly stage=test after audited validation.

No market execution is implied by importing this module. All output/runtime
authorities must be supplied and verified before calling the original main.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sys
import time

import run_monthly_walk_forward as monthly


shared = monthly.shared
ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018")
SCIENTIFIC_ROOT = ROOT / "monthly_walk_forward_v1"
HERE = Path(__file__).resolve().parent
RUN_CONTRACT_SHA = "7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f"
MIN_FREE_BYTES = 2_000_000_000
REVIEW_STATUS = "PASS_MONTHLY_TEST_RESOURCE_OVERLAY_REVIEW"
RUNTIME_STATUS = "PASS_MONTHLY_TEST_RESOURCE_RUNTIME_REVIEW"
AUDIT_STATUS = "PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES"
MODES = ("static", "expanding", "rolling12")
VALIDATION_MONTHS = tuple(f"2025{m:02d}" for m in range(1, 13))
TEST_MONTHS = tuple(f"2026{m:02d}" for m in range(1, 7))
SPEC = "MONTHLY_TEST_RESOURCE_OVERLAY_SPEC_20261023.md"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def parse_time(value):
    value = datetime.fromisoformat(value)
    require(value.tzinfo is not None and value.utcoffset() is not None, "Aware receipt clock required")
    return value.astimezone(timezone.utc)


def fit_keys(year):
    count = 12 if year == 2025 else 6
    return {f"train_{start}_{year}{month:02d}01_exclusive"
            for month in range(1, count + 1)
            for start in ("20230101", f"{year - 1}{month:02d}01")}


def resource_observation():
    return dict(available_ram_bytes=int(shared.psutil.virtual_memory().available),
                free_commit_bytes=int(shared.free_commit_bytes()), utc=utc())


def wait_resources(out, runtime_root):
    while True:
        observation = resource_observation()
        ready = all(observation[k] >= MIN_FREE_BYTES
                    for k in ("available_ram_bytes", "free_commit_bytes"))
        record = dict(stage="RESOURCE_OVERLAY_READY" if ready else "WAITING_RESOURCES_2GB",
            threshold_bytes=MIN_FREE_BYTES, scientific_root=str(Path(out).resolve()), **observation)
        shared.atomic_json(runtime_root / "observations" / f"{time.time_ns()}.json", record)
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


@contextmanager
def os_lock(path, *, create):
    """The scientific lock is opened without changing any of its bytes."""
    path = Path(path)
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        require(path.is_file() and path.stat().st_size > 0, "Existing nonempty scientific lock required")
    try:
        before = None if create else shared.sha(path)
    except OSError:
        raise RuntimeError("Another producer or test launcher holds the lock") from None
    with path.open("a+b" if create else "r+b") as handle:
        if create and path.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError("Another producer or test launcher holds the lock") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    if before is not None:
        require(shared.sha(path) == before, "Scientific lock bytes changed")


def original_argv():
    return ["--engine-root", str(ROOT / "session_clock_dataset_v1"),
            "--feature-root", str(ROOT / "session_clock_dataset_v1"),
            "--source-audit", str(ROOT / "session_clock_dataset_v1_audit/audit.json"),
            "--implementation-review", str(HERE / "MONTHLY_WALK_FORWARD_IMPLEMENTATION_REVIEW.json"),
            "--out", str(SCIENTIFIC_ROOT), "--stage", "test"]


def review_expectations():
    return dict(files={name: shared.sha(HERE / name) for name in (
        "run_monthly_test_resource_overlay.py", "test_monthly_test_resource_overlay.py", SPEC)},
        original_dependencies=monthly.dependency_hashes(), original_run_contract_sha256=RUN_CONTRACT_SHA,
        threshold_bytes=MIN_FREE_BYTES, scope="test", scientific_inputs_changed=False)


def verify_hashes(files):
    for name, digest in files.items():
        require(shared.sha(Path(name)) == digest, "Preserved evidence changed: " + name)


def absolute(value):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "Absolute bounded authority path required")
    return path.resolve()


def inside(path, roots):
    path = Path(path).resolve()
    return any(path == root or path.is_relative_to(root) for root in roots)


class Authorities:
    def __init__(self, roots):
        self.roots, self.files = roots, {}

    def file(self, path, digest=None):
        path = absolute(str(path))
        require(inside(path, self.roots), "Authority outside reviewed read roots")
        actual = shared.sha(path)
        require(digest is None or actual == digest, "Authority SHA256 differs: " + str(path))
        require(str(path) not in self.files or self.files[str(path)] == actual, "Conflicting authority hashes")
        self.files[str(path)] = actual
        return actual

    def member(self, spec, *, json=True):
        require(set(spec) == {"path", "sha256"}, "Exact path/hash authority required")
        path = absolute(spec["path"])
        self.file(path, spec["sha256"])
        value = shared.read_json(path) if json else None
        self.file(path, spec["sha256"])
        return value


def flattened(groups):
    require(isinstance(groups, dict) and bool(groups), "Audited file inventory required")
    result = {}
    for group in groups.values():
        require(isinstance(group, dict), "Invalid audited file group")
        for name, digest in group.items():
            name = str(absolute(name))
            require(name not in result or result[name] == digest, "Conflicting audited hashes")
            result[name] = digest
    return result


def option(command, name):
    require(command.count(name) == 1, "Receipt command option missing or duplicated")
    position = command.index(name)
    require(position + 1 < len(command), "Receipt command option lacks value")
    return command[position + 1]


def verify_process_chain(files, authorities, expected_runtime, *, validation):
    required = {"process_binding", "monitor_open", "monitored_exit", "monitor_code", "runtime_launch"}
    require(required.issubset(files), "Retained-handle receipt chain required")
    binding, opened, exited, launch = (authorities.member(files[k])
        for k in ("process_binding", "monitor_open", "monitored_exit", "runtime_launch"))
    authorities.member(files["monitor_code"], json=False)
    receipt_hash = files["process_binding"]["sha256"]
    pid = binding.get("pid")
    require(type(pid) is int and pid > 0 and pid != os.getpid(), "Invalid previous process identity")
    require(opened.get("status") == "PROCESS_HANDLE_RETAINED"
            and exited.get("status") == "PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE"
            and opened.get("process_receipt_sha256") == exited.get("process_receipt_sha256") == receipt_hash
            and opened.get("monitor_code_sha256") == files["monitor_code"]["sha256"]
            and opened.get("pid") == exited.get("pid") == launch.get("pid") == pid,
            "Retained-handle chain identity differs")
    creation = binding.get("creation_time")
    require(type(creation) in (int, float) and creation > 0
            and abs(opened.get("creation_time", 0) - creation) <= 0.001
            and abs(exited.get("creation_time", 0) - creation) <= 0.001,
            "Previous process creation time differs")
    require(opened.get("command") == binding.get("command") and isinstance(binding["command"], list),
            "Previous process command differs")
    require(Path(option(binding["command"], "--runtime-root")).resolve() == expected_runtime,
            "Receipt runtime root differs")
    script = HERE / ("run_monthly_resource_overlay.py" if validation else "run_monthly_test_resource_overlay.py")
    command_scripts = [Path(part).resolve() for part in binding["command"] if str(part).endswith(".py")]
    require(script.resolve() in command_scripts, "Receipt is not the declared monthly wrapper")
    require(parse_time(opened["monitor_started_utc"]) <= parse_time(exited["observed_utc"])
            and type(exited.get("exit_code")) is int, "Invalid process exit observation")
    normalized = ("source_launch_receipt_sha256" in binding
                  or binding.get("normalized_from_existing_receipt_with_live_command_and_creation_check") is True)
    require(not normalized or "source_launch" in files,
            "Normalized binding requires its source launch receipt")
    if "source_launch" in files:
        authorities.member(files["source_launch"])
        require(binding.get("source_launch_receipt_sha256") == files["source_launch"]["sha256"],
                "Normalized process binding lost source launch receipt")
    if validation:
        require(exited["exit_code"] == 0, "Validation must have observed exit zero")
        require(launch.get("status") == "MONTHLY_RESOURCE_OVERLAY_STARTED"
                and launch.get("original_argv") == [*original_argv()[:-1], "validation"],
                "Exit receipt belongs to another stage")
    else:
        require(launch.get("status") == "MONTHLY_TEST_RESOURCE_OVERLAY_STARTED"
                and launch.get("original_argv") == original_argv()
                and launch.get("original_run_contract_sha256") == RUN_CONTRACT_SHA
                and launch.get("scientific_inputs_changed") is False
                and launch.get("review", {}).get("original_dependencies") == monthly.dependency_hashes()
                and launch.get("review", {}).get("scope") == "test",
                "Previous test attempt stage/contract differs")
    require(not shared.psutil.pid_exists(pid), "Previous process PID still exists; preserve evidence")
    return launch, exited


def checkpoints(root):
    artifacts = monthly.Artifacts(root, RUN_CONTRACT_SHA)
    names = {p.name.removesuffix(".fit_started.json") for p in (root / "models").glob("*.fit_started.json")}
    allowed = fit_keys(2025) | fit_keys(2026)
    require(names.issubset(allowed), "Undeclared model window")
    for name in names:
        require(artifacts.complete("models/" + name), "Incomplete started fit preserved; automatic refit forbidden")
        artifacts.require_members("models/" + name, [root / f"models/{name}.txt", root / f"models/{name}.fit_started.json"])
    model_files = {p.name.removesuffix(".txt") for p in (root / "models").glob("*.txt")}
    closures = {p.name.removesuffix(".complete.json") for p in (root / "models").glob("*.complete.json")}
    require(names == model_files == closures, "Orphan model/start/closure identity differs")
    require(fit_keys(2025).issubset(names), "All twenty-four validation models required")
    files = set(root.rglob("*.complete.json"))
    files.update((root / "models").glob("*.txt"))
    files.update((root / "models").glob("*.fit_started.json"))
    files.update((root / "executed_code").glob("*"))
    files.add(root / "run_contract.json")
    return names, {str(p.resolve()): shared.sha(p) for p in sorted(files) if p.is_file()}


def test_evidence(root):
    """Exclude legitimate calendar/index/day_samples/feature_inputs preparation."""
    paths = set()
    for folder in ("predictions", "months", "ledgers"):
        for path in (root / folder).glob("2026*"):
            paths.update(p for p in path.rglob("*") if p.is_file())
            if path.is_file():
                paths.add(path)
    for folder in ("fits", "models"):
        for path in (root / folder).glob("train_*"):
            if re.match(r"train_\d{8}_2026\d{4}_exclusive", path.name):
                paths.update(p for p in path.rglob("*") if p.is_file())
                if path.is_file():
                    paths.add(path)
    # Unlike day_samples, chunks contain net targets/labels and are not outcome-free.
    paths.update(p for p in (root / "day_chunks").glob("*/2026*") if p.is_file())
    paths.update(p for p in (root / "reports").glob("2026*") if p.is_file())
    paths.update(p for p in root.glob("completion*.json") if p.is_file())
    return {str(p.resolve()): shared.sha(p) for p in sorted(paths)}


def admit(review_path, runtime_review_path, expected_audit_sha):
    expected = review_expectations()
    review = shared.read_json(review_path)
    require(review.get("status") == REVIEW_STATUS
            and all(review.get(k) == v for k, v in expected.items())
            and len(expected["original_dependencies"]) == 11, "Exact test overlay review required")
    runtime = shared.read_json(runtime_review_path)
    require(runtime.get("status") == RUNTIME_STATUS and runtime.get("scope") == "test"
            and runtime.get("implementation_review_sha256") == shared.sha(review_path)
            and runtime.get("review_expectations") == expected
            and runtime.get("original_run_contract_sha256") == RUN_CONTRACT_SHA
            and runtime.get("scientific_root") == str(SCIENTIFIC_ROOT.resolve()),
            "Exact external test runtime binding required")
    roots = tuple(absolute(p) for p in runtime.get("allowed_read_roots", []))
    require(roots and all(p.is_dir() and p != Path(p.anchor) for p in roots), "Bounded read roots required")
    authorities = Authorities(roots)
    authorities.file(review_path)
    authorities.file(runtime_review_path)
    contract_path = SCIENTIFIC_ROOT / "run_contract.json"
    authorities.file(contract_path, RUN_CONTRACT_SHA)
    contract = shared.read_json(contract_path)
    require(contract["dependencies"] == expected["original_dependencies"], "Scientific dependencies changed")
    for name, digest in expected["original_dependencies"].items():
        authorities.file(HERE / name, digest)
        authorities.file(SCIENTIFIC_ROOT / "executed_code" / name, digest)
    for name, digest in expected["files"].items():
        authorities.file(HERE / name, digest)
    validation = runtime["validation"]
    require(validation["audit"]["sha256"] == expected_audit_sha, "External validation audit hash differs")
    audit = authorities.member(validation["audit"])
    audited, binding = audit.get("audited", {}), audit.get("binding", {})
    require(audit.get("status") == AUDIT_STATUS and binding.get("completed_months") == list(VALIDATION_MONTHS)
            and audited.get("months") == 12 and audited.get("unique_fit_windows") == 24
            and audited.get("calendar_ticker_days") == 750 and audited.get("modes") == list(MODES)
            and audited.get("validation_selection_reconstructed") is True
            and audited.get("validation_period_report_reconstructed") is True,
            "Complete independent validation audit required")
    require(absolute(binding["monthly_root"]) == SCIENTIFIC_ROOT.resolve()
            and binding.get("run_contract_sha256") == RUN_CONTRACT_SHA
            and binding.get("session_audit_sha256") == contract["source_audit"]["sha256"]
            and absolute(binding["session_root"]) == Path(contract["engine_root"]).resolve()
            and binding.get("index_sha256") == contract["source_audit"]["binding"]["index_sha256"],
            "Validation scientific/source binding differs")
    audited_files = flattened(audit["verified_files"])
    for path, digest in audited_files.items():
        authorities.file(path, digest)
    freeze = authorities.member(validation["freeze"])
    freeze_path = SCIENTIFIC_ROOT / "validation_freeze.json"
    require(absolute(validation["freeze"]["path"]) == freeze_path.resolve()
            and audited_files.get(str(freeze_path.resolve())) == validation["freeze"]["sha256"],
            "Frozen selection absent from independent validation audit")
    artifacts = monthly.Artifacts(SCIENTIFIC_ROOT, RUN_CONTRACT_SHA)
    artifacts.require_members("validation_freeze", [freeze_path])
    mode = freeze.get("selected_mode")
    require((mode is None or mode in MODES) and freeze.get("status") == (
        "FAIL_NO_DAILY_COMPLIANT_MODE" if mode is None else "SELECTED_RESEARCH_MODE")
        and freeze.get("selection_period") == "2025" and freeze.get("approved") is False
        and freeze.get("outcomes_2026_used_for_mode_selection") is False,
        "Frozen mode/null semantics differ")
    for stamp in VALIDATION_MONTHS:
        for name in (f"months/{stamp}/daily", f"months/{stamp}/economics"):
            path = SCIENTIFIC_ROOT / (name + ".json")
            require(str(path.resolve()) in audited_files, "Validation month absent from audit")
            artifacts.require_members(name, [path])
        require(str((SCIENTIFIC_ROOT / f"months/{stamp}/predictions.complete.json").resolve()) in audited_files,
                "Validation prediction closure absent from audit")
    artifacts.require_members("reports/2025", [SCIENTIFIC_ROOT / "reports/2025.json"])
    validation_root = absolute(validation["runtime_root"])
    launch, exited = verify_process_chain(validation, authorities, validation_root, validation=True)
    completion = authorities.member(validation["runtime_completion"])
    require(completion.get("status") == "COMPLETE_MONTHLY_RESOURCE_OVERLAY_VALIDATION"
            and completion.get("original_run_contract_sha256") == RUN_CONTRACT_SHA
            and completion.get("scientific_inputs_changed") is False
            and launch.get("authority", {}).get("original_dependencies") == expected["original_dependencies"]
            and completion.get("runtime_review_sha256") == launch.get("runtime_review_sha256")
            and parse_time(launch["started_utc"]) < parse_time(completion["completed_utc"])
            <= parse_time(exited["observed_utc"]), "Validation runtime completion differs")
    require(absolute(validation["runtime_launch"]["path"]) == validation_root / "launch.json"
            and absolute(validation["runtime_completion"]["path"]) == validation_root / "completion.json",
            "Validation runtime receipt path differs")
    require(completion["runtime_members"].get(str(validation_root / "launch.json"))
            == validation["runtime_launch"]["sha256"], "Validation launch absent from runtime closure")
    for group in (completion["runtime_members"], completion["final_checkpoints"], completion["preserved_checkpoints"]):
        for path, digest in group.items():
            authorities.file(path, digest)
    names, preserved = checkpoints(SCIENTIFIC_ROOT)
    for key in fit_keys(2025):
        for suffix in (".txt", ".fit_started.json", ".complete.json"):
            path = str((SCIENTIFIC_ROOT / f"models/{key}{suffix}").resolve())
            require(audited_files.get(path) == preserved.get(path) and path in preserved,
                    "Validation model absent from audit or changed")
    evidence = test_evidence(SCIENTIFIC_ROOT)
    new_keys = names - fit_keys(2025)
    require(runtime.get("expected_completed_test_fit_keys") == sorted(new_keys),
            "Previously completed test model set differs")
    if runtime.get("mode") == "initial":
        require(not evidence and not new_keys and not runtime.get("prior_test_attempts"),
                "Initial test launch cannot adopt prior test evidence")
    elif runtime.get("mode") == "resume":
        require(runtime.get("expected_test_evidence") == evidence and runtime.get("prior_test_attempts"),
                "Resume requires externally reviewed prior test evidence")
        for prior in runtime["prior_test_attempts"]:
            prior_root = absolute(prior["runtime_root"])
            old_launch, _ = verify_process_chain(prior, authorities, prior_root, validation=False)
            require(old_launch.get("validation_audit_sha256") == expected_audit_sha,
                    "Previous attempt used another validation authority")
        require(not (SCIENTIFIC_ROOT / "completion.complete.json").exists(),
                "Test phase already complete; audit existing outputs")
    else:
        raise ValueError("Runtime mode must be initial or resume")
    verify_hashes(authorities.files)
    return dict(expectations=expected, runtime=runtime, authorities=authorities,
                preserved=preserved, freeze=freeze, validation_audit_sha256=expected_audit_sha)


def guard_runtime_root(runtime_root):
    resolved = runtime_root.resolve()
    for protected in (SCIENTIFIC_ROOT, ROOT / "session_clock_dataset_v1", HERE):
        protected = protected.resolve()
        require(not (resolved == protected or resolved.is_relative_to(protected)
                     or protected.is_relative_to(resolved)), "Runtime receipts require a separate directory")
    require(not runtime_root.exists(), "Use a new runtime attempt directory")


def finish_science(admitted):
    names, final = checkpoints(SCIENTIFIC_ROOT)
    require(names == fit_keys(2025) | fit_keys(2026), "Expected all thirty-six completed models")
    artifacts = monthly.Artifacts(SCIENTIFIC_ROOT, RUN_CONTRACT_SHA)
    for stamp in TEST_MONTHS:
        for kind in ("daily", "economics"):
            path = SCIENTIFIC_ROOT / f"months/{stamp}/{kind}.json"
            artifacts.require_members(f"months/{stamp}/{kind}", [path])
        require(artifacts.complete(f"months/{stamp}/predictions"), "Incomplete test predictions")
    for name in ("reports/2026", "completion"):
        artifacts.require_members(name, [SCIENTIFIC_ROOT / (name + ".json")])
    completion = shared.read_json(SCIENTIFIC_ROOT / "completion.json")
    require(completion.get("status") == "COMPLETE" and completion.get("evaluated_months") == 18
            and completion.get("unique_fit_windows") == 36
            and completion.get("selected_mode") == admitted["freeze"]["selected_mode"]
            and completion.get("promotion_approved") is False
            and completion.get("report_hashes") == {str(y): shared.sha(SCIENTIFIC_ROOT / f"reports/{y}.json")
                                                    for y in (2025, 2026)}, "Scientific completion differs")
    return final


def run(runtime_root, review_path, runtime_review_path, expected_audit_sha):
    runtime_root = runtime_root.resolve()
    guard_runtime_root(runtime_root)
    # A second launcher cannot validate a stale inventory while this launcher runs.
    with os_lock(ROOT / "monthly_test_resource_overlay.lock", create=True):
        # Keep the original lock during admission, then release before original main.
        with os_lock(SCIENTIFIC_ROOT / "run.lock", create=False):
            admitted = admit(review_path.resolve(), runtime_review_path.resolve(), expected_audit_sha)
        guard_runtime_root(runtime_root)
        runtime_root.mkdir(parents=True)
        snapshots = {}
        inputs = [(HERE / name, digest, "executed_code/" + name)
                  for name, digest in admitted["expectations"]["files"].items()]
        inputs.extend([(review_path.resolve(), shared.sha(review_path), "authorities/implementation_review.json"),
                       (runtime_review_path.resolve(), shared.sha(runtime_review_path), "authorities/runtime_review.json")])
        for path, digest, relative in inputs:
            destination = runtime_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".partial")
            with temporary.open("xb") as handle:
                handle.write(path.read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
            require(shared.sha(temporary) == digest, "Snapshot changed during publication")
            shared.durable_replace(temporary, destination)
            snapshots[str(destination)] = digest
        argv = original_argv()
        launch = dict(status="MONTHLY_TEST_RESOURCE_OVERLAY_STARTED", pid=os.getpid(), started_utc=utc(),
            original_runner=str(Path(monthly.__file__).resolve()), original_argv=argv,
            original_run_contract_sha256=RUN_CONTRACT_SHA, resources=resource_observation(),
            validation_audit_sha256=expected_audit_sha, review=admitted["expectations"],
            implementation_review_sha256=shared.sha(review_path), runtime_review_sha256=shared.sha(runtime_review_path),
            preserved_checkpoints=admitted["preserved"], snapshots=snapshots,
            scientific_inputs_changed=False, resource_function="train_causal_rollout.wait_resources only")
        shared.atomic_json(runtime_root / "launch.json", launch)
        started, old_argv = time.monotonic(), sys.argv
        try:
            sys.argv = [str(Path(monthly.__file__).resolve()), *argv]
            with resource_overlay(runtime_root):
                # Its unchanged run.lock fails closed if another producer won a race.
                monthly.main()
            with os_lock(SCIENTIFIC_ROOT / "run.lock", create=False):
                final = finish_science(admitted)
                verify_hashes(admitted["preserved"])
                verify_hashes(admitted["authorities"].files)
                verify_hashes(snapshots)
                require(review_expectations() == admitted["expectations"], "Overlay or scientific code changed")
                members = {str(p): shared.sha(p) for p in runtime_root.rglob("*") if p.is_file()}
                shared.atomic_json(runtime_root / "completion.json", dict(
                    status="COMPLETE_MONTHLY_TEST_RESOURCE_OVERLAY", completed_utc=utc(),
                    seconds=time.monotonic() - started, original_run_contract_sha256=RUN_CONTRACT_SHA,
                    validation_audit_sha256=expected_audit_sha, selected_mode=admitted["freeze"]["selected_mode"],
                    scientific_inputs_changed=False, preserved_checkpoints=admitted["preserved"],
                    final_checkpoints=final, runtime_members=members,
                    runtime_review_sha256=shared.sha(runtime_review_path)))
        except BaseException as exc:
            shared.atomic_json(runtime_root / "failure.json", dict(status="INTERRUPTED_OR_FAILED_PRESERVED",
                error=repr(exc), utc=utc(), seconds=time.monotonic() - started))
            raise
        finally:
            sys.argv = old_argv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--implementation-review", type=Path, required=True)
    parser.add_argument("--runtime-review", type=Path, required=True)
    parser.add_argument("--expected-validation-audit-sha256", required=True)
    args = parser.parse_args()
    run(args.runtime_root, args.implementation_review, args.runtime_review,
        args.expected_validation_audit_sha256)


if __name__ == "__main__":
    main()
