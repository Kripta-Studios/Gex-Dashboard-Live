"""Run the bounded fifth synthetic suite for the value-path auditor.

The already reviewed attempt04 harness is used as a sealed implementation
library only after its bytes and SHA-256 have been verified.  This wrapper adds
attempt04 to the immutable evidence chain and owns only fresh attempt05.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import stat
import sys
import traceback


REPO = Path(r"C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live")
WEEK = REPO / "research_papers" / "JEPA" / "weekly_multiday_20261101"
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
SEALED_HARNESS = WEEK / "launch_weekly_zone_event_value_path_audit_fixtures_attempt04_20261102.py"
SEALED_HARNESS_BYTES = 24_709
SEALED_HARNESS_SHA256 = "c7b39c95f23c0cfd7ea12392d36df7e481b61197a65692402dd38ce5005da830"
ATTEMPT = BASE / "weekly_zone_event_value_path_audit_fixtures_01" / "attempt05"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bootstrap_sealed_harness() -> dict[str, object]:
    if SEALED_HARNESS != Path(os.path.abspath(SEALED_HARNESS)):
        raise RuntimeError("sealed harness path is not absolute nominal")
    current = SEALED_HARNESS
    while True:
        info = os.lstat(current)
        if getattr(info, "st_file_attributes", 0) & getattr(
            stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0
        ):
            raise RuntimeError(f"reparse in sealed harness path: {current}")
        if current.parent == current:
            break
        current = current.parent
    info = SEALED_HARNESS.stat()
    if (
        not stat.S_ISREG(info.st_mode)
        or SEALED_HARNESS.is_symlink()
        or info.st_nlink != 1
        or info.st_size != SEALED_HARNESS_BYTES
        or _sha256(SEALED_HARNESS) != SEALED_HARNESS_SHA256
    ):
        raise RuntimeError("sealed attempt04 harness pin mismatch")
    return runpy.run_path(str(SEALED_HARNESS), run_name="sealed_attempt04_harness")


BASE_MODULE = _bootstrap_sealed_harness()

AUDITOR = WEEK / "audit_weekly_zone_event_value_paths.py"
AUDITOR_TESTS = WEEK / "test_audit_weekly_zone_event_value_paths.py"
CONTRACT = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md"
CONTRACT_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_REVIEW_20261102.md"
AUDITOR_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_AUDITOR_IMPLEMENTATION_REVIEW_20261102.md"
GATE_HELPER = REPO / "research_papers" / "JEPA" / "level_oracle_20261018" / "launch_monthly_test_index_v2_audit_20261024.py"
HARNESS = Path(__file__).resolve()
PREPARATION = BASE / "weekly_zone_event_value_path_audit_fixtures_01"
ROOT_CONTROL_RECEIPT = BASE / "weekly_zone_event_value_path_root_control_01" / "audit_attempt02_cli_rejection_01.json"

ACTIVE_PINS = {
    AUDITOR: "d927bca9cd64d51792d68a425a021d9fff9c5cb1ff5dfef79f02dcdcc3c2d2e7",
    AUDITOR_TESTS: "ac5d0fbee457396e8d9e15d217089a17927f1ba73953d681ffa02f2fc4840deb",
    CONTRACT: "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9",
    CONTRACT_REVIEW: "ad118946f30d0681770c25840a4f40d89941030688882b74e23350d098b6b185",
    AUDITOR_REVIEW: "53e3e7bdfd830278effd32efbe34841f41d2414bb0001b089841031758779b9c",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
    SEALED_HARNESS: SEALED_HARNESS_SHA256,
}
ACTIVE_BYTES = {
    AUDITOR: 96_078,
    AUDITOR_TESTS: 21_539,
    CONTRACT: 36_466,
    CONTRACT_REVIEW: 2_340,
    AUDITOR_REVIEW: 3_811,
    GATE_HELPER: 31_463,
    SEALED_HARNESS: SEALED_HARNESS_BYTES,
}

ATTEMPT04_PINS = {
    "audit_weekly_zone_event_value_paths.py.before_test": (96078, "d927bca9cd64d51792d68a425a021d9fff9c5cb1ff5dfef79f02dcdcc3c2d2e7"),
    "compile_exit.json": (743, "89567b760f7c4611a9d391fc491e4605db176686c24442c4b9d7e5cda7f1d2e1"),
    "compile_process.json": (699, "f964113a439b11442d482bb917aa5958d2d41ccfff59af2de20dee608cbe7832"),
    "compile_resource_observation.json": (13733, "ad5c7e3231d51d7e3b36c06c800ff748bbf78f64ab832c0ee35abb2de936b37d"),
    "compile_stderr.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "compile_stdout.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "failure_receipt.json": (481, "bede2ca8409e7fccc4668572fe1fff51622555767a54767a8efc422b8a26856f"),
    "launch_monthly_test_index_v2_audit_20261024.py.before_test": (31463, "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"),
    "launch_weekly_zone_event_value_path_audit_fixtures_attempt04_20261102.py.before_test": (24709, "c7b39c95f23c0cfd7ea12392d36df7e481b61197a65692402dd38ce5005da830"),
    "preflight_resource_observation.json": (13735, "ac839e0e7e43cdbbdd1469be20851cfbe0fe2d4970d47e75be2f918d7c4872cb"),
    "preserved_prior_evidence_snapshot.json": (10353, "1598ddd40d4e445c25b506bde494e617f7ac75e5000b426c49276c65022d2add"),
    "pytest_exit.json": (576, "d18e02c48fd4970eab1a2f1519c2bf6dce985fc7d81f3d09bac63f4eee338d00"),
    "pytest_process.json": (532, "8936e289b4eb6aecd0ca14211992822f0450f041513ed15fbdfbef4533e6473d"),
    "pytest_resource_observation.json": (13732, "5c121f8002b45b2118a92fddf017e8b75c9e8819fb88d8a9f69beae97186e99f"),
    "pytest_stderr.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "pytest_stdout.txt": (5708, "1deb84aa88329d13a8a8d4b9903c90c58b4ac628ca27e1a130e79930f57d2244"),
    "ruff_exit.json": (751, "e427d728d5c95df76b3b225ad46ffe72a15522e16ead7d485d36204d448d9c32"),
    "ruff_process.json": (707, "27faa0f6b2f56d874dd6f5cefc401e38f5ab6860773212726e42061f45722436"),
    "ruff_resource_observation.json": (13730, "9db2dc69a98fba414c930d13ba5eda268ec198eb19e7d3119b87ae74e64e85d9"),
    "ruff_stderr.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "ruff_stdout.txt": (19, "82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18"),
    "test_audit_weekly_zone_event_value_paths.py.before_test": (21461, "b427ea0b6e73c9811ffc7cf18b00575f456000e95c904635f77ab38b90f842f5"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_AUDITOR_IMPLEMENTATION_REVIEW_20261102.md.before_test": (3407, "17ed9716132e6e9b4fe57c04793de39bc82809229f95565b1d8f3aa52efa4fe0"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md.before_test": (36466, "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_REVIEW_20261102.md.before_test": (2340, "ad118946f30d0681770c25840a4f40d89941030688882b74e23350d098b6b185"),
}

# Rebind the sealed implementation to the new active and evidence authorities.
BASE_MODULE["PINS"] = ACTIVE_PINS
BASE_MODULE["PIN_BYTES"] = ACTIVE_BYTES
BASE_MODULE["HARNESS"] = HARNESS
BASE_MODULE["AUDITOR"] = AUDITOR
BASE_MODULE["AUDITOR_TESTS"] = AUDITOR_TESTS
BASE_MODULE["AUDITOR_REVIEW"] = AUDITOR_REVIEW
BASE_MODULE["ATTEMPT"] = ATTEMPT
BASE_MODULE["ATTEMPTS"][4] = PREPARATION / "attempt04"
BASE_MODULE["PRIOR_PINS"][4] = ATTEMPT04_PINS


def _validate_all_prior(
    *, allow_attempt05: bool = False, allow_attempt04: bool = False
) -> dict[str, object]:
    base = BASE_MODULE
    base["_validate_pin_definitions"]()
    base["assert_plain_directory"](PREPARATION)
    allow_current = allow_attempt05 or allow_attempt04
    if (ATTEMPT.exists() and not allow_current) or (PREPARATION / "receipt.json").exists():
        raise RuntimeError("attempt05 or parent receipt already exists")
    snapshots = {
        f"attempt{number:02d}": base["_snapshot_directory"](
            base["ATTEMPTS"][number], base["PRIOR_PINS"][number]
        )
        for number in sorted(base["PRIOR_PINS"])
    }
    base["assert_plain_directory"](ROOT_CONTROL_RECEIPT.parent)
    control_pin = base["assert_plain_exact"](
        ROOT_CONTROL_RECEIPT, *base["ROOT_CONTROL_PIN"]
    )
    control = base["_read_json"](ROOT_CONTROL_RECEIPT)
    if control.get("phase") != "ARGPARSE_BEFORE_ATTEMPT_CREATION" or control.get("tool_reported_exit_code") != 1:
        raise RuntimeError("root-control CLI receipt mismatch")

    expected = {
        1: ("compile", {"compile": 1}),
        2: ("ruff", {"compile": 0, "ruff": 1}),
        3: ("pytest", {"compile": 0, "ruff": 0, "pytest": 1}),
        4: ("pytest", {"compile": 0, "ruff": 0, "pytest": 1}),
    }
    for number, (failed_stage, exits) in expected.items():
        directory = base["ATTEMPTS"][number]
        failure = base["_read_json"](directory / "failure_receipt.json")
        if (
            failure.get("status") != "FORMAL_AUDIT_FIXTURE_STAGE_FAILED"
            or failure.get("stage") != failed_stage
            or failure.get("exit_code") != 1
            or failure.get("retry") is not False
        ):
            raise RuntimeError(f"attempt{number:02d} failure semantics mismatch")
        for stage, exit_code in exits.items():
            closure = base["_read_json"](directory / f"{stage}_exit.json")
            if closure.get("exit_code") != exit_code or closure.get("metadata_error") is not None:
                raise RuntimeError(f"attempt{number:02d} {stage} closure mismatch")
    if "Found 6 errors." not in (base["ATTEMPTS"][2] / "ruff_stdout.txt").read_text(encoding="utf-8"):
        raise RuntimeError("attempt02 six-lint evidence mismatch")
    if "3 failed, 52 passed" not in (base["ATTEMPTS"][3] / "pytest_stdout.txt").read_text(encoding="utf-8"):
        raise RuntimeError("attempt03 pytest summary mismatch")
    if "1 failed, 55 passed" not in (base["ATTEMPTS"][4] / "pytest_stdout.txt").read_text(encoding="utf-8"):
        raise RuntimeError("attempt04 pytest summary mismatch")
    return {
        "artifact_counts": {
            f"attempt{number:02d}": len(base["PRIOR_PINS"][number])
            for number in sorted(base["PRIOR_PINS"])
        },
        "snapshots": snapshots,
        "root_control": control_pin,
    }


BASE_MODULE["validate_prior_evidence"] = _validate_all_prior


def _failure(status: str, **extra: object) -> None:
    base = BASE_MODULE
    base["write_json"](
        ATTEMPT / "failure_receipt.json",
        {
            "status": status,
            "attempt": "attempt05",
            "retry": False,
            "real_value_audit_executed": False,
            "recorded_utc": base["utc_now"](),
            "closing_pin_differences": base["best_effort_diff"](
                base["ACTIVE_EXPECTED"]
            ),
            **extra,
        },
    )


BASE_MODULE["failure"] = _failure


def main() -> int:
    base = BASE_MODULE
    args = base["parse_args"]()
    expected = base["require_finalized"](args.harness_sha256)
    base["ACTIVE_EXPECTED"] = expected
    if Path(sys.executable).resolve() != base["PYTHON"].resolve():
        raise RuntimeError(f"unexpected Python: {sys.executable}")
    base["exact_snapshot"](expected)
    prior = _validate_all_prior()
    ATTEMPT.mkdir(parents=False, exist_ok=False)
    for source in expected:
        base["shutil"].copyfile(source, ATTEMPT / f"{source.name}.before_test")
    base["write_json"](ATTEMPT / "preserved_prior_evidence_snapshot.json", prior)
    base["actual_process_state"]()
    specification = base["importlib"].util.spec_from_file_location(
        "official_gate", GATE_HELPER
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("official gate import unavailable")
    gate_module = base["importlib"].util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    try:
        base["observe_and_gate"](gate_module, "preflight", expected)
    except Exception as error:
        _failure(
            "RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_AUDIT_FIXTURES",
            error=f"{type(error).__name__}: {error}",
            stages_executed=[],
        )
        return 2
    files = [str(AUDITOR), str(AUDITOR_TESTS)]
    commands = [
        ("compile", [str(base["PYTHON"]), "-X", "utf8", "-m", "py_compile", *files]),
        ("ruff", [str(base["PYTHON"]), "-X", "utf8", "-m", "ruff", "check", *files]),
        ("pytest", [str(base["PYTHON"]), "-X", "utf8", "-m", "pytest", "-q", str(AUDITOR_TESTS)]),
    ]
    completed: list[dict[str, object]] = []
    for name, command in commands:
        try:
            base["observe_and_gate"](gate_module, name, expected)
        except Exception as error:
            _failure(
                "RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_AUDIT_FIXTURE_CHILD",
                stage=name,
                completed=completed,
                error=f"{type(error).__name__}: {error}",
                child_created=False,
            )
            return 2
        try:
            result = base["run_child"](name, command)
        except Exception as error:
            _failure(
                "AUDIT_FIXTURE_CHILD_LAUNCH_OR_OBSERVATION_FAILED",
                stage=name,
                completed=completed,
                error=f"{type(error).__name__}: {error}",
                traceback=traceback.format_exc(),
            )
            return 3
        completed.append({"stage": name, "exit_code": result["exit_code"]})
        if result["exit_code"] != 0:
            _failure(
                "FORMAL_AUDIT_FIXTURE_STAGE_FAILED",
                stage=name,
                completed=completed,
                exit_code=result["exit_code"],
            )
            return int(result["exit_code"]) or 1
    closing = base["exact_snapshot"](expected)
    final_prior = _validate_all_prior(allow_attempt05=True)
    receipt = {
        "status": "PASS_FORMAL_SYNTHETIC_WEEKLY_ZONE_EVENT_VALUE_PATH_AUDITOR_FIXTURES",
        "attempt": "attempt05",
        "preserved_failure_sha256": {
            f"attempt{number:02d}": base["PRIOR_PINS"][number]["failure_receipt.json"][1]
            for number in sorted(base["PRIOR_PINS"])
        },
        "prior_artifact_counts": final_prior["artifact_counts"],
        "root_control_receipt_sha256": base["ROOT_CONTROL_PIN"][1],
        "stages": completed,
        "closing_sha256": closing,
        "real_value_audit_executed": False,
        "fit_performed": False,
        "api_read": False,
        "broker_read": False,
        "retry": False,
        "closed_utc": base["utc_now"](),
    }
    base["write_json"](ATTEMPT / "receipt.json", receipt)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        if ATTEMPT.is_dir():
            _failure(
                "AUDIT_FIXTURE_HARNESS_FAILED_CLOSED",
                error=f"{type(error).__name__}: {error}",
                traceback=traceback.format_exc(),
            )
        raise
