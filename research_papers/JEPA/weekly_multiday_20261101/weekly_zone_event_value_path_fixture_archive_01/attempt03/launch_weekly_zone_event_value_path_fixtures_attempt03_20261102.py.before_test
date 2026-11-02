"""Run the one reviewed second corrective suite for value-path fixtures."""

from __future__ import annotations

import os


THREAD_ENV = {
    "ARROW_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "NUMBA_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "POLARS_MAX_THREADS": "1",
    "TBB_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}
os.environ.update(THREAD_ENV)
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import sys
import traceback


REPO = Path(r"C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live")
WEEK = REPO / "research_papers" / "JEPA" / "weekly_multiday_20261101"
BASE_HARNESS = WEEK / "launch_weekly_zone_event_value_path_fixtures_attempt02_20261102.py"
BASE_HARNESS_BYTES = 19318
BASE_HARNESS_SHA256 = "68df689b7c2e372c48c913b8dd401ed86a354d7ada338bdaaa59f910a5c4ea54"


def preimport_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_preimport_pin() -> None:
    if BASE_HARNESS != Path(os.path.abspath(BASE_HARNESS)) or not BASE_HARNESS.is_file() or BASE_HARNESS.is_symlink():
        raise RuntimeError("attempt02 harness is absent, linked, or aliased")
    current = BASE_HARNESS
    while True:
        info = os.lstat(current)
        if getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise RuntimeError(f"reparse point in attempt02 harness path: {current}")
        if current.parent == current:
            break
        current = current.parent
    info = BASE_HARNESS.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RuntimeError("attempt02 harness is not an unambiguous regular file")
    if info.st_size != BASE_HARNESS_BYTES or preimport_sha256(BASE_HARNESS) != BASE_HARNESS_SHA256:
        raise RuntimeError("attempt02 harness pre-import pin mismatch")


require_preimport_pin()
specification = importlib.util.spec_from_file_location("reviewed_attempt02_harness", BASE_HARNESS)
if specification is None or specification.loader is None:
    raise RuntimeError("reviewed attempt02 harness import unavailable")
runtime = importlib.util.module_from_spec(specification)
specification.loader.exec_module(runtime)

PYTHON = runtime.PYTHON
BASE = runtime.BASE
BUILDER = runtime.BUILDER
SPOT = runtime.SPOT
BUILDER_TESTS = runtime.BUILDER_TESTS
SPOT_TESTS = runtime.SPOT_TESTS
CONTRACT = runtime.CONTRACT
CONTRACT_REVIEW = runtime.CONTRACT_REVIEW
BUILDER_REVIEW = runtime.BUILDER_REVIEW
SPOT_REVIEW = runtime.SPOT_REVIEW
GATE_HELPER = runtime.GATE_HELPER
PREPARATION = runtime.PREPARATION
ATTEMPT01 = runtime.ATTEMPT01
ATTEMPT02 = PREPARATION / "attempt02"
ATTEMPT = PREPARATION / "attempt03"
ORIGINAL_HARNESS = WEEK / "launch_weekly_zone_event_value_path_fixtures_20261102.py"
HARNESS = Path(__file__).resolve()

PINS = {
    BUILDER: "b6528622bd9d39fd3a132b6665e7e7cee2e1b0208cd7d854a270093c95398afe",
    SPOT: "0953d344b28992da4b92c561daa7663bb48fe89ea309f6323f53b39c6a0dbd38",
    BUILDER_TESTS: "ea5c7d0b0848e3cc4dc8fc6a9ac0e59505bf9e5244cbd775308a81b682ae72aa",
    SPOT_TESTS: "80d91442dafbf8b2beace31b46eb117913e410a1ccb820ee467f2d0c24d9d3eb",
    CONTRACT: "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9",
    CONTRACT_REVIEW: "ad118946f30d0681770c25840a4f40d89941030688882b74e23350d098b6b185",
    BUILDER_REVIEW: "f2b2dc96747159ec0c89f1a71ebc6ed91d808243561269f85773c8780dc272ff",
    SPOT_REVIEW: "bb5d0e1223aabf357eba37ab7b380cc3f380757a3a7d691d3803bc5bdf035ebc",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
    ORIGINAL_HARNESS: "f684ac9d364d6eebc5e5130a791760edc3d51b2439fdbde492c7a07ee81bfc96",
    BASE_HARNESS: BASE_HARNESS_SHA256,
}
PIN_BYTES = {
    BUILDER: 83817,
    SPOT: 40814,
    BUILDER_TESTS: 28614,
    SPOT_TESTS: 33144,
    CONTRACT: 36466,
    CONTRACT_REVIEW: 2340,
    BUILDER_REVIEW: 2869,
    SPOT_REVIEW: 2365,
    GATE_HELPER: 31463,
    ORIGINAL_HARNESS: 14566,
    BASE_HARNESS: BASE_HARNESS_BYTES,
}

ATTEMPT02_PINS = {
    "build_weekly_zone_event_value_paths.py.before_test": (83817, "b6528622bd9d39fd3a132b6665e7e7cee2e1b0208cd7d854a270093c95398afe"),
    "compile_exit.json": (1082, "c1fb91f95972aceef1045b58eb9211a66c29607c9851d55671d9824b70756c88"),
    "compile_process.json": (1038, "f84926286774f8b0cf51f7adbabbf43effd7c34cfab016164ec148d5bfb641c3"),
    "compile_resource_observation.json": (7359, "67ab3b489bb9e963ec4837c32044753c74b1ce9717900cbe5481393284ce5683"),
    "compile_stderr.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "compile_stdout.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "failure_receipt.json": (477, "c07528fe27f0a774c85a3f2f88fcb6f3bcafd41e8a92ba00c3b41789b3c7cdfd"),
    "launch_monthly_test_index_v2_audit_20261024.py.before_test": (31463, "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046"),
    "launch_weekly_zone_event_value_path_fixtures_attempt02_20261102.py.before_test": (19318, BASE_HARNESS_SHA256),
    "preflight_resource_observation.json": (7361, "ff3160005993f4513abd67007b2584dc2f4b132a8ae233fbca5349e7310d865e"),
    "preserved_attempt01_snapshot.json": (3433, "c163f5c984306e27a59e813e6f1d5d782349a224cd44775960beddd9187bf1ee"),
    "pytest_exit.json": (747, "392478a96147df57c72377030de6f2bf0b582f0ee57d67218a9bbaba1fab2930"),
    "pytest_process.json": (703, "1385b5a69c3c3fd2ca9dfb9264e64646fce0d4a7bf89d7f6a7f0a2fe80fc4820"),
    "pytest_resource_observation.json": (7358, "e429acfe6327e1f348072ca9aff481ef7dc7c20c389da5d2f5a8650fb851e108"),
    "pytest_stderr.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "pytest_stdout.txt": (6508, "0996041265b944f40010d515c9bdba39bc514a06f4f959b95af9743d25171ebb"),
    "ruff_exit.json": (1089, "6467eb3df7cdcdec985148e2989dcb4bde5c9718350a7cafb645d620986726b5"),
    "ruff_process.json": (1045, "caae32a3ff4de975264e063abf70b7695482c36cccc0904aecd82c4f6b868f4a"),
    "ruff_resource_observation.json": (7356, "e38802191cf20678369869f62b07522592ff991f79d5f55a97d67623aa094ceb"),
    "ruff_stderr.txt": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "ruff_stdout.txt": (19, "82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18"),
    "test_build_weekly_zone_event_value_paths.py.before_test": (28367, "db5084abe4a751e77def095df7bc5fc92a78eae8c49f048892b6187bcae7499c"),
    "test_weekly_zone_event_spot_paths.py.before_test": (33144, "80d91442dafbf8b2beace31b46eb117913e410a1ccb820ee467f2d0c24d9d3eb"),
    "WEEKLY_ZONE_EVENT_SPOT_PATH_IMPLEMENTATION_REVIEW_20261102.md.before_test": (2365, "bb5d0e1223aabf357eba37ab7b380cc3f380757a3a7d691d3803bc5bdf035ebc"),
    "weekly_zone_event_spot_paths.py.before_test": (40814, "0953d344b28992da4b92c561daa7663bb48fe89ea309f6323f53b39c6a0dbd38"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_BUILDER_IMPLEMENTATION_REVIEW_20261102.md.before_test": (2404, "3c71635d40a322811dc1e1041320af79fac102e444ba30a6ebb793b61b4ebb5f"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md.before_test": (36466, "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9"),
    "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_REVIEW_20261102.md.before_test": (2340, "ad118946f30d0681770c25840a4f40d89941030688882b74e23350d098b6b185"),
}

runtime.HARNESS = HARNESS
runtime.ATTEMPT = ATTEMPT
runtime.PINS = PINS
runtime.PIN_BYTES = PIN_BYTES
runtime.ACTIVE_EXPECTED = {}
original_validate_attempt01 = runtime.validate_attempt01


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run reviewed second corrective value-path fixtures")
    parser.add_argument("--harness-sha256", required=True)
    return parser.parse_args()


def validate_history(*, allow_attempt02: bool = False) -> dict[str, object]:
    if (ATTEMPT.exists() and not allow_attempt02) or (PREPARATION / "receipt.json").exists():
        raise RuntimeError("attempt03 or parent receipt already exists")
    attempt01_snapshot = original_validate_attempt01(allow_attempt02=True)
    runtime.assert_plain_directory(ATTEMPT02)
    actual_names = {path.name for path in ATTEMPT02.iterdir()}
    if actual_names != set(ATTEMPT02_PINS):
        raise RuntimeError("preserved attempt02 member set mismatch")
    attempt02_snapshot = {
        name: runtime.assert_plain_exact(ATTEMPT02 / name, expected_bytes, expected_sha256)
        for name, (expected_bytes, expected_sha256) in ATTEMPT02_PINS.items()
    }
    compile_exit = json.loads((ATTEMPT02 / "compile_exit.json").read_text(encoding="utf-8"))
    ruff_exit = json.loads((ATTEMPT02 / "ruff_exit.json").read_text(encoding="utf-8"))
    pytest_exit = json.loads((ATTEMPT02 / "pytest_exit.json").read_text(encoding="utf-8"))
    failure_receipt = json.loads((ATTEMPT02 / "failure_receipt.json").read_text(encoding="utf-8"))
    if compile_exit.get("exit_code") != 0 or compile_exit.get("metadata_error") is not None:
        raise RuntimeError("preserved attempt02 compile closure mismatch")
    if ruff_exit.get("exit_code") != 0 or ruff_exit.get("metadata_error") is not None:
        raise RuntimeError("preserved attempt02 Ruff closure mismatch")
    if pytest_exit.get("exit_code") != 1 or pytest_exit.get("metadata_error") is not None:
        raise RuntimeError("preserved attempt02 pytest closure mismatch")
    if failure_receipt.get("status") != "FORMAL_FIXTURE_STAGE_FAILED" or failure_receipt.get("attempt") != "attempt02" or failure_receipt.get("stage") != "pytest" or failure_receipt.get("exit_code") != 1 or failure_receipt.get("retry") is not False:
        raise RuntimeError("preserved attempt02 failure receipt mismatch")
    return {"attempt01": attempt01_snapshot, "attempt02": attempt02_snapshot}


runtime.validate_attempt01 = validate_history


def failure(status: str, **extra: object) -> None:
    runtime.write_json(ATTEMPT / "failure_receipt.json", {"status": status, "attempt": "attempt03", "retry": False, "real_value_runtime_executed": False, "recorded_utc": runtime.utc_now(), "closing_pin_differences": runtime.best_effort_diff(runtime.ACTIVE_EXPECTED), **extra})


def main() -> int:
    args = parse_args()
    expected = runtime.require_finalized(args.harness_sha256)
    runtime.ACTIVE_EXPECTED = expected
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"unexpected Python: {sys.executable}")
    runtime.exact_snapshot(expected)
    preserved_history = validate_history()

    ATTEMPT.mkdir(parents=False, exist_ok=False)
    for source in expected:
        runtime.shutil.copyfile(source, ATTEMPT / f"{source.name}.before_test")
    runtime.write_json(ATTEMPT / "preserved_attempts_snapshot.json", preserved_history)
    runtime.actual_process_state()

    gate_specification = importlib.util.spec_from_file_location("official_gate", GATE_HELPER)
    if gate_specification is None or gate_specification.loader is None:
        raise RuntimeError("official gate import unavailable")
    gate_module = importlib.util.module_from_spec(gate_specification)
    gate_specification.loader.exec_module(gate_module)
    try:
        runtime.observe_and_gate(gate_module, "preflight", expected)
    except Exception as error:
        failure("RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_FIXTURES", error=f"{type(error).__name__}: {error}", stages_executed=[])
        return 2

    files = [str(BUILDER), str(SPOT), str(BUILDER_TESTS), str(SPOT_TESTS)]
    commands = [
        ("compile", [str(PYTHON), "-X", "utf8", "-m", "py_compile", *files]),
        ("ruff", [str(PYTHON), "-X", "utf8", "-m", "ruff", "check", *files]),
        ("pytest", [str(PYTHON), "-X", "utf8", "-m", "pytest", "-q", str(BUILDER_TESTS), str(SPOT_TESTS)]),
    ]
    completed: list[dict[str, object]] = []
    for name, command in commands:
        try:
            runtime.observe_and_gate(gate_module, name, expected)
        except Exception as error:
            failure("RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_FIXTURE_CHILD", stage=name, completed=completed, error=f"{type(error).__name__}: {error}", child_created=False)
            return 2
        try:
            result = runtime.run_child(name, command)
        except Exception as error:
            failure("CHILD_LAUNCH_OR_OBSERVATION_FAILED", stage=name, completed=completed, error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
            return 3
        completed.append({"stage": name, "exit_code": result["exit_code"]})
        if result["exit_code"] != 0:
            failure("FORMAL_FIXTURE_STAGE_FAILED", stage=name, completed=completed, exit_code=result["exit_code"])
            return int(result["exit_code"]) or 1

    closing = runtime.exact_snapshot(expected)
    validate_history(allow_attempt02=True)
    receipt = {
        "status": "PASS_FORMAL_SYNTHETIC_WEEKLY_ZONE_EVENT_VALUE_PATH_FIXTURES",
        "attempt": "attempt03",
        "preserved_attempt01_failure_sha256": runtime.ATTEMPT01_PINS["failure_receipt.json"][1],
        "preserved_attempt02_failure_sha256": ATTEMPT02_PINS["failure_receipt.json"][1],
        "stages": completed,
        "closing_sha256": closing,
        "real_value_runtime_executed": False,
        "fit_performed": False,
        "api_read": False,
        "broker_read": False,
        "retry": False,
        "closed_utc": runtime.utc_now(),
    }
    runtime.write_json(ATTEMPT / "receipt.json", receipt)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        if ATTEMPT.is_dir():
            failure("HARNESS_FAILED_CLOSED", error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
        raise
