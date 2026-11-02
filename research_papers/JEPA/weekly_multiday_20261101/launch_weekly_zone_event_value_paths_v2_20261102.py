"""Launch the reviewed weekly zone-event value-path producer exactly once."""

from __future__ import annotations

import os
import sys


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

import ctypes


KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
KERNEL32.GetCurrentProcess.restype = ctypes.c_void_p
KERNEL32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
KERNEL32.SetProcessAffinityMask.restype = ctypes.c_int
KERNEL32.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
KERNEL32.GetProcessAffinityMask.restype = ctypes.c_int
CURRENT_PROCESS = KERNEL32.GetCurrentProcess()
if not KERNEL32.SetProcessAffinityMask(CURRENT_PROCESS, ctypes.c_size_t(1)):
    raise ctypes.WinError(ctypes.get_last_error())

import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import stat
import subprocess
import time
import traceback


PYTHON = Path(r"C:\Program Files\Python314\python.exe")
REPO = Path(r"C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live")
WEEK = REPO / "research_papers" / "JEPA" / "weekly_multiday_20261101"
LEVEL = REPO / "research_papers" / "JEPA" / "level_oracle_20261018"
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
OUTPUT = BASE / "weekly_zone_event_value_paths_02"
OBSERVER = BASE / "weekly_zone_event_value_paths_observer_02"
JOURNAL = OBSERVER / "journal.jsonl"
IMPLEMENTATION_PINS_JSON = OBSERVER / "implementation_pins.json"
BRANCH = "research/multiscale-v1r1-net-usd"
MINIMUM_BYTES = 2_000_000_000

BUILDER = WEEK / "build_weekly_zone_event_value_paths_v2.py"
SPOT = WEEK / "weekly_zone_event_spot_paths.py"
BUILDER_TESTS = WEEK / "test_build_weekly_zone_event_value_paths_v2.py"
SPOT_TESTS = WEEK / "test_weekly_zone_event_spot_paths.py"
CONTRACT = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2_CALENDAR_AMENDMENT_20261102.md"
CONTRACT_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2_CALENDAR_REVIEW_20261102.md"
BUILDER_FINAL_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2_BUILDER_FINAL_REVIEW_20261102.md"
SPOT_FINAL_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_SPOT_PATH_FINAL_REVIEW_20261102.md"
RUNTIME_BINDING = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2_RUNTIME_BINDING_20261102.md"
LAUNCHER = Path(__file__).resolve()
GATE_HELPER = LEVEL / "launch_monthly_test_index_v2_audit_20261024.py"

REPO_PINS = {
    BUILDER: "ed260c55a62fecce729dadce170b5dec5c98049be92580495131e007a7ffd5ab",
    SPOT: "0953d344b28992da4b92c561daa7663bb48fe89ea309f6323f53b39c6a0dbd38",
    BUILDER_TESTS: "5d92d42c65defa5030c2b8c20d6060b2cabc66d4855decdb2246b9a8a9413d14",
    SPOT_TESTS: "80d91442dafbf8b2beace31b46eb117913e410a1ccb820ee467f2d0c24d9d3eb",
    CONTRACT: "65fd1aaef25ddea13957ce07e6c21285771adc889f097d603f93e00572cf1146",
    CONTRACT_REVIEW: "b8b2080bb1f717f6f68be586cf3c28bd13cd3ea54ece3a427a2830bcdd52d60a",
    BUILDER_FINAL_REVIEW: "7a1c56c140b03f60cbfbc5ddffd72417d0408640822eca46e99644f16105f7f6",
    SPOT_FINAL_REVIEW: "221004483dd77fb5112bbb05ca2ec44191c31cfb19a26815b2950c82e721a140",
    RUNTIME_BINDING: "7b19ec6f51c03e8a2e0c249dbd3f8fcfabcdd32219c3adbc4443dfe2ab1f6cdf",
    WEEK / "weekly_zone_event_value_path_v2_fixture_archive_02" / "manifest.json": "0ddaddb71c93b3fba333046f980f04478c034e90e79bc6cbc2ec5384e1be6913",
    WEEK / "weekly_zone_event_value_path_v2_fixture_archive_02" / "receipt.json": "2d529e36702f270ec62834b8133233d355816be71b6ebc00a64e09311d39ef06",
    WEEK / "weekly_zone_event_value_path_v2_fixture_archive_02" / "preparation" / "receipt.json": "23fa4c3468a971596c3fe078246733b92676f5b70289f6eba56dc6622e8b66dd",
    WEEK / "build_weekly_h2_dataset_v2.py": "ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945",
    WEEK / "weekly_multiday_source_pilot.py": "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878",
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md": "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
}
REPO_BYTES = {
    BUILDER: 91830,
    SPOT: 40814,
    BUILDER_TESTS: 36127,
    SPOT_TESTS: 33144,
    CONTRACT: 15276,
    CONTRACT_REVIEW: 1677,
    BUILDER_FINAL_REVIEW: 1867,
    SPOT_FINAL_REVIEW: 1486,
    RUNTIME_BINDING: 3322,
    WEEK / "weekly_zone_event_value_path_v2_fixture_archive_02" / "manifest.json": 25384,
    WEEK / "weekly_zone_event_value_path_v2_fixture_archive_02" / "receipt.json": 978,
    WEEK / "weekly_zone_event_value_path_v2_fixture_archive_02" / "preparation" / "receipt.json": 3846,
    WEEK / "build_weekly_h2_dataset_v2.py": 33142,
    WEEK / "weekly_multiday_source_pilot.py": 31380,
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md": 36466,
    GATE_HELPER: 31463,
}

EXTERNAL_PINS = {
    BASE / "weekly_zone_event_value_paths_observer_01" / "exit.json": "48b635e9fbdeef729de7c1be0b24948e21655ceb6cf5a154c02809e8a8a951d3",
    BASE / "weekly_zone_event_value_paths_observer_01" / "failure_receipt.json": "6ee1cb2ee3a29b74484c5ed54fe5049eb45da6e299c4fcd9ea8553bc809086fc",
    BASE / "weekly_zone_event_value_paths_observer_01" / "journal.jsonl": "a12c7f5d5e1171e220cc1bcefd9f3191caf6e414f5c5df1cdeb5b4bc8b36aa08",
    BASE / "weekly_zone_event_source_plan_01" / "entry_plan.jsonl": "0db0065f2dcdd254122a4c4575ecb9c752318cab3a90666ad8215aef922d91bb",
    BASE / "weekly_zone_event_source_plan_01" / "weekly_sources.jsonl": "59081a049d11a0403204ca06e62ef4661bb6de3cd042548e081c10f8eaddd1f7",
    BASE / "weekly_zone_event_source_plan_01" / "summary.json": "612ecf1abf18f973656aeda347f21efe563f5c84b9cc06f96e22383ed19b3b39",
    BASE / "weekly_zone_event_source_plan_01" / "manifest.json": "a0a9d330992d7f5768550c5b60401a701e1c1b02caec4a0967de50b7c7f13161",
    BASE / "weekly_zone_event_source_plan_audit_01" / "audit.json": "1b71077525d146cd7e2166076f987afd315fe46e27c15e51c4f7555be06299cd",
    BASE / "weekly_zone_event_source_plan_audit_01" / "manifest.json": "49935941c89b67f2aef69272201d68d089d9499d0fca71838867b5457bf85ba7",
    BASE / "weekly_zone_event_source_plan_audit_observer_01" / "exit.json": "bfdf36bfb7f636f27a391ad0b0ed38be5306e69b0c5be144d0c0599de9d65362",
    BASE / "h2_dataset_v2_01" / "inventory.json": "099dcf065a62705cbd88f2c1b90b2e4a9b99ff4d994ad703634101920c934b12",
    BASE / "h2_dataset_v2_01" / "inventory_manifest.json": "c417e67f3499522d4ebd4a21bf28d1cba8ce249ef2d38a1352001216714bb899",
    BASE / "h2_dataset_v2_01" / "manifest.json": "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8",
    BASE / "h2_dataset_v2_extension_2026q3_partial_01" / "inventory.json": "f633d0ee192f28650698a4033ee7f6d2dc00dad07aa38239c40e9e2b5092ea5c",
    BASE / "h2_dataset_v2_extension_2026q3_partial_01" / "inventory_manifest.json": "5b39e0796599fa72b5d74d029885a24fd57fada207f12989576737aa46d75b2f",
    BASE / "h2_dataset_v2_extension_2026q3_partial_01" / "manifest.json": "b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b",
    BASE / "h2_boundary_bridge_01" / "inventory.json": "599ca400fecae12ce4098187a45af3ee0cf8c1b070e060d8c84e422ce92c6161",
    BASE / "h2_boundary_bridge_01" / "inventory_manifest.json": "0a7a5fab0f932d23fdf9a3140027f99eb85ccd958b79ef55152c53ab5ced70f2",
    BASE / "h2_boundary_bridge_01" / "manifest.json": "9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86",
    BASE / "h2_boundary_bridge_01" / "unified_calendar.json": "be622bb24aca35448594743dfeb5236e6b2d08a4410109b20302891f8c1fa7d6",
    BASE / "h2_context_1030_01" / "inventory.json": "b347523c8638825c822100cf78b5a03ab4f56fc948bc7aa23674b0b73866df5e",
    BASE / "h2_context_1030_01" / "inventory_manifest.json": "a7547c375a4de723b168ce2983b84ba98a35dd70aef24c82ed08c1e3c5358ea8",
    BASE / "h2_context_1030_01" / "manifest.json": "77aaf00d60accc071ff1f58ec099cee72bc3a4150f89e4ad41a601821a74a38a",
    BASE / "h2_context_q3_1030_01" / "inventory.json": "25da3398984c633a044eef4f20c5525c6224a1b076a5941d0311fae93eab68cf",
    BASE / "h2_context_q3_1030_01" / "inventory_manifest.json": "2b74c18e98366670e77e3d2a4fc19e260cd404e6959fbd7e140f2e88fd5050be",
    BASE / "h2_context_q3_1030_01" / "manifest.json": "1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66",
}
EXTERNAL_BYTES = {
    BASE / "weekly_zone_event_value_paths_observer_01" / "exit.json": 358,
    BASE / "weekly_zone_event_value_paths_observer_01" / "failure_receipt.json": 305,
    BASE / "weekly_zone_event_value_paths_observer_01" / "journal.jsonl": 6473,
    BASE / "weekly_zone_event_source_plan_01" / "entry_plan.jsonl": 1018910,
    BASE / "weekly_zone_event_source_plan_01" / "weekly_sources.jsonl": 2367532,
    BASE / "weekly_zone_event_source_plan_01" / "summary.json": 1398,
    BASE / "weekly_zone_event_source_plan_01" / "manifest.json": 5094,
    BASE / "weekly_zone_event_source_plan_audit_01" / "audit.json": 9071,
    BASE / "weekly_zone_event_source_plan_audit_01" / "manifest.json": 8945,
    BASE / "weekly_zone_event_source_plan_audit_observer_01" / "exit.json": 1337,
    BASE / "h2_dataset_v2_01" / "inventory.json": 5589855,
    BASE / "h2_dataset_v2_01" / "inventory_manifest.json": 187,
    BASE / "h2_dataset_v2_01" / "manifest.json": 1541,
    BASE / "h2_dataset_v2_extension_2026q3_partial_01" / "inventory.json": 327384,
    BASE / "h2_dataset_v2_extension_2026q3_partial_01" / "inventory_manifest.json": 197,
    BASE / "h2_dataset_v2_extension_2026q3_partial_01" / "manifest.json": 6184,
    BASE / "h2_boundary_bridge_01" / "inventory.json": 14721,
    BASE / "h2_boundary_bridge_01" / "inventory_manifest.json": 330,
    BASE / "h2_boundary_bridge_01" / "manifest.json": 4748,
    BASE / "h2_boundary_bridge_01" / "unified_calendar.json": 232573,
    BASE / "h2_context_1030_01" / "inventory.json": 1829496,
    BASE / "h2_context_1030_01" / "inventory_manifest.json": 197,
    BASE / "h2_context_1030_01" / "manifest.json": 612610,
    BASE / "h2_context_q3_1030_01" / "inventory.json": 1489911,
    BASE / "h2_context_q3_1030_01" / "inventory_manifest.json": 193,
    BASE / "h2_context_q3_1030_01" / "manifest.json": 172889,
}
ACTIVE_EXPECTED: dict[Path, tuple[int, str]] = {}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def affinity_mask() -> int:
    process_mask = ctypes.c_size_t()
    system_mask = ctypes.c_size_t()
    if not KERNEL32.GetProcessAffinityMask(CURRENT_PROCESS, ctypes.byref(process_mask), ctypes.byref(system_mask)):
        raise ctypes.WinError(ctypes.get_last_error())
    return process_mask.value


def actual_process_state() -> dict[str, object]:
    affinity = affinity_mask()
    threads = {name: os.environ.get(name) for name in THREAD_ENV}
    cuda = os.environ.get("CUDA_VISIBLE_DEVICES")
    if affinity != 1 or any(value != "1" for value in threads.values()) or cuda != "-1":
        raise RuntimeError(f"parent process state drift: affinity={affinity}, threads={threads}, cuda={cuda}")
    return {"cpu_affinity_mask": affinity, "thread_variables": threads, "cuda_visible_devices": cuda}


def assert_plain_exact(path: Path, expected_bytes: int, expected_sha256: str) -> dict[str, object]:
    absolute = Path(os.path.abspath(path))
    if path != absolute or not path.is_file() or path.is_symlink():
        raise RuntimeError(f"pin path is absent, linked, or aliased: {path}")
    current = path
    while True:
        info = os.lstat(current)
        if getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise RuntimeError(f"reparse point in pin path: {current}")
        if current.parent == current:
            break
        current = current.parent
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RuntimeError(f"pin is not an unambiguous regular file: {path}")
    actual_sha256 = sha256(path)
    if info.st_size != expected_bytes or actual_sha256 != expected_sha256:
        raise RuntimeError(f"pin bytes/hash mismatch: {path}")
    return {"bytes": info.st_size, "sha256": actual_sha256}


def require_finalized() -> None:
    pending = [str(path) for path, value in REPO_PINS.items() if value.startswith("PENDING_") or not isinstance(REPO_BYTES[path], int)]
    if pending:
        raise RuntimeError(f"value-path launcher draft is not executable: {sorted(pending)}")


def git_bytes(commit: str, path: Path) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path.relative_to(REPO).as_posix()}"], cwd=REPO)


def verify_publication() -> str:
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip()
    if branch != BRANCH:
        raise RuntimeError(f"unexpected branch: {branch}")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    remote = subprocess.check_output(["git", "ls-remote", "origin", f"refs/heads/{BRANCH}"], cwd=REPO, text=True).split()[0]
    if commit != remote:
        raise RuntimeError("local HEAD is not published remote HEAD")
    for path, expected in REPO_PINS.items():
        assert_plain_exact(path, REPO_BYTES[path], expected)
        if git_bytes(commit, path) != path.read_bytes():
            raise RuntimeError(f"repository publication mismatch: {path}")
    launcher_info = LAUNCHER.stat()
    assert_plain_exact(LAUNCHER, launcher_info.st_size, sha256(LAUNCHER))
    if git_bytes(commit, LAUNCHER) != LAUNCHER.read_bytes():
        raise RuntimeError("launcher is not byte-exact at published HEAD")
    return commit


def verify_external() -> None:
    for path, expected in EXTERNAL_PINS.items():
        assert_plain_exact(path, EXTERNAL_BYTES[path], expected)


def snapshot_pins() -> dict[str, dict[str, object]]:
    values = {
        str(path): assert_plain_exact(path, REPO_BYTES[path], digest)
        for path, digest in REPO_PINS.items()
    }
    values.update({str(path): assert_plain_exact(path, EXTERNAL_BYTES[path], digest) for path, digest in EXTERNAL_PINS.items()})
    values[str(LAUNCHER)] = assert_plain_exact(LAUNCHER, LAUNCHER.stat().st_size, sha256(LAUNCHER))
    return values


def verify_closing(before: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    changed = []
    for name, expected in before.items():
        path = Path(name)
        try:
            actual = assert_plain_exact(path, int(expected["bytes"]), str(expected["sha256"]))
        except Exception as error:
            changed.append({"path": name, "before": expected, "after": {"error": f"{type(error).__name__}: {error}"}})
            continue
        if actual != expected:
            changed.append({"path": name, "before": expected, "after": actual})
    return changed


def best_effort_diff(expected: dict[Path, tuple[int, str]]) -> list[dict[str, object]]:
    differences = []
    for path, (expected_bytes, expected_sha256) in expected.items():
        try:
            actual = {"bytes": path.stat().st_size, "sha256": sha256(path)} if path.is_file() else {"bytes": None, "sha256": None}
        except Exception as error:
            actual = {"error": f"{type(error).__name__}: {error}"}
        wanted = {"bytes": expected_bytes, "sha256": expected_sha256}
        if actual != wanted:
            differences.append({"path": str(path), "expected": wanted, "actual": actual})
    return differences


def implementation_pins() -> dict[str, dict[str, object]]:
    paths = {
        "builder": BUILDER,
        "spot_module": SPOT,
        "builder_tests": BUILDER_TESTS,
        "spot_tests": SPOT_TESTS,
        "contract": CONTRACT,
        "builder_final_review": BUILDER_FINAL_REVIEW,
        "spot_final_review": SPOT_FINAL_REVIEW,
        "runtime_binding": RUNTIME_BINDING,
        "launcher": LAUNCHER,
        "resource_helper": GATE_HELPER,
    }
    return {key: {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)} for key, path in paths.items()}


def failure(status: str, **extra: object) -> None:
    write_json(OBSERVER / "failure_receipt.json", {"status": status, "retry": False, "utc": utc_now(), "closing_pin_differences": best_effort_diff(ACTIVE_EXPECTED), **extra})


def main() -> int:
    global ACTIVE_EXPECTED
    require_finalized()
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"unexpected Python: {sys.executable}")
    if OUTPUT.exists() or OBSERVER.exists():
        raise RuntimeError("contracted output or observer root already exists")
    commit = verify_publication()
    verify_external()
    before = snapshot_pins()
    ACTIVE_EXPECTED = {
        **{path: (REPO_BYTES[path], digest) for path, digest in REPO_PINS.items()},
        **{path: (EXTERNAL_BYTES[path], digest) for path, digest in EXTERNAL_PINS.items()},
        LAUNCHER: (before[str(LAUNCHER)]["bytes"], before[str(LAUNCHER)]["sha256"]),
    }
    OBSERVER.mkdir(parents=False, exist_ok=False)
    write_json(IMPLEMENTATION_PINS_JSON, implementation_pins())
    actual_process_state()

    specification = importlib.util.spec_from_file_location("official_gate", GATE_HELPER)
    if specification is None or specification.loader is None:
        raise RuntimeError("official resource helper unavailable")
    gate_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    resources = gate_module.observation()
    disk_free = shutil.disk_usage(BASE).free
    process_state = actual_process_state()
    before = snapshot_pins()
    observation = {
        "utc": utc_now(),
        "resources": resources,
        "disk_free_bytes": disk_free,
        "minimum_bytes": MINIMUM_BYTES,
        **process_state,
        "publication_commit": commit,
        "pins": before,
    }
    write_json(OBSERVER / "resource_observation.json", observation)
    try:
        gate_module.gate(resources)
        if disk_free < MINIMUM_BYTES:
            raise RuntimeError(f"D: free bytes {disk_free} below {MINIMUM_BYTES}")
    except Exception as error:
        failure("RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_VALUE_CHILD", error=f"{type(error).__name__}: {error}", child_created=False, observation=observation)
        return 2

    pre_child_pins = snapshot_pins()
    pre_child_disk_free = shutil.disk_usage(BASE).free
    pre_child_state = actual_process_state()
    pre_child_resources = gate_module.observation()
    pre_child_roots = {
        "output_lexists": os.path.lexists(OUTPUT),
        "observer_lexists": os.path.lexists(OBSERVER),
        "observer_is_directory": OBSERVER.is_dir(),
        "observer_is_symlink": OBSERVER.is_symlink(),
    }
    pre_child_observation = {
        "utc": utc_now(),
        **pre_child_state,
        "resources": pre_child_resources,
        "pins": pre_child_pins,
        "disk_free_bytes": pre_child_disk_free,
        "minimum_bytes": MINIMUM_BYTES,
        "roots": pre_child_roots,
        "child_created": False,
    }
    write_json(OBSERVER / "pre_child_observation.json", pre_child_observation)
    try:
        gate_module.gate(pre_child_resources)
        if pre_child_disk_free < MINIMUM_BYTES:
            raise RuntimeError(f"D: free bytes {pre_child_disk_free} below {MINIMUM_BYTES}")
        if pre_child_roots != {
            "output_lexists": False,
            "observer_lexists": True,
            "observer_is_directory": True,
            "observer_is_symlink": False,
        }:
            raise RuntimeError(f"runtime root state drift immediately before child: {pre_child_roots}")
    except Exception as error:
        failure("RESOURCE_DISK_OR_ROOT_GATE_REJECTED_IMMEDIATELY_BEFORE_VALUE_CHILD", error=f"{type(error).__name__}: {error}", observation=pre_child_observation, child_created=False)
        return 2

    command = [
        str(PYTHON), "-X", "utf8", "-u", str(BUILDER),
        "--execute-reviewed-builder",
        "--output-dir", str(OUTPUT),
        "--observer-dir", str(OBSERVER),
        "--journal", str(JOURNAL),
        "--implementation-pins-json", str(IMPLEMENTATION_PINS_JSON),
    ]
    write_json(OBSERVER / "admission.json", {"utc": utc_now(), "command": command, "publication_commit": commit, "observation": observation, "output": str(OUTPUT), "observer": str(OBSERVER), "journal": str(JOURNAL)})

    metadata_error = None
    creation_epoch = None
    child_mask = None
    started = time.monotonic()
    started_utc = utc_now()
    with (OBSERVER / "stdout.log").open("wb") as stdout, (OBSERVER / "stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, cwd=str(WEEK), env=os.environ.copy(), stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            try:
                import psutil

                child = psutil.Process(process.pid)
                creation_epoch = child.create_time()
                child_mask = child.cpu_affinity()
                if child_mask != [0]:
                    raise RuntimeError(f"child affinity is not CPU[0]: {child_mask}")
            except Exception as error:
                metadata_error = f"{type(error).__name__}: {error}"
            try:
                write_json(OBSERVER / "process.json", {"pid": process.pid, "creation_epoch": creation_epoch, "start_utc": started_utc, "command": command, "cpu_affinity": child_mask, "metadata_error": metadata_error, "handle_retained": True, "wait_pending": True})
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else f"{metadata_error}; {detail}"
        finally:
            child_exit = process.wait()

    changed = verify_closing(before)
    effective_exit = child_exit
    if metadata_error is not None and effective_exit == 0:
        effective_exit = 3
    if changed and effective_exit == 0:
        effective_exit = 4
    write_json(
        OBSERVER / "exit.json",
        {
            "exit_code": effective_exit,
            "value_child_exit_code": child_exit,
            "utc": utc_now(),
            "source": "subprocess.Popen.wait_retained_handle",
            "elapsed_seconds": time.monotonic() - started,
            "pid": process.pid,
            "creation_epoch": creation_epoch,
            "cpu_affinity": child_mask,
            "metadata_error": metadata_error,
            "changed_pins": changed,
            "retry": False,
        },
    )
    if effective_exit != 0 and not (OBSERVER / "failure_receipt.json").exists():
        failure("VALUE_CHILD_OR_CLOSURE_FAILED", exit_code=effective_exit, value_child_exit_code=child_exit, metadata_error=metadata_error, changed_pins=changed, partial_output_not_authorized_for_adoption=True)
    return int(effective_exit)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        if OBSERVER.is_dir() and not (OBSERVER / "failure_receipt.json").exists():
            failure("LAUNCHER_FAILED_CLOSED", error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
        raise
