"""Run the reviewed synthetic B06/R3 bounded-resource-wait fixture suite."""

from __future__ import annotations

import os
import sys

THREAD_ENV = {name: "1" for name in (
    "ARROW_NUM_THREADS", "BLIS_NUM_THREADS", "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS", "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS", "POLARS_MAX_THREADS", "TBB_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)}
os.environ.update(THREAD_ENV)
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import argparse
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
import traceback

PYTHON = Path(r"C:\Program Files\Python314\python.exe")
REPO = Path(r"C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live")
WEEK = REPO / "research_papers" / "JEPA" / "weekly_multiday_20261101"
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
AUDITOR = WEEK / "audit_weekly_zone_event_value_paths_v2r2_attempt05.py"
AUDITOR_TESTS = WEEK / "test_audit_weekly_zone_event_value_paths_v2r2_attempt05.py"
BUILDER = WEEK / "build_weekly_zone_event_value_paths_v2.py"
BASELINE_AUDITOR = WEEK / "audit_weekly_zone_event_value_paths_v2r1.py"
BASELINE_TESTS = WEEK / "test_audit_weekly_zone_event_value_paths_v2r1.py"
BASELINE_R2_AUDITOR = WEEK / "audit_weekly_zone_event_value_paths_v2r2.py"
BASELINE_R2_TESTS = WEEK / "test_audit_weekly_zone_event_value_paths_v2r2.py"
BASELINE_V2_AUDITOR = WEEK / "audit_weekly_zone_event_value_paths_v2.py"
BASELINE_V2_TESTS = WEEK / "test_audit_weekly_zone_event_value_paths_v2.py"
BASELINE_V1_AUDITOR = WEEK / "audit_weekly_zone_event_value_paths.py"
BASELINE_V1_TESTS = WEEK / "test_audit_weekly_zone_event_value_paths.py"
CONTRACT = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md"
AMENDMENT = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2_CALENDAR_AMENDMENT_20261102.md"
R1_AMENDMENT = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R1_AUDIT_ADMISSION_AMENDMENT_20261102.md"
R1_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R1_ADMISSION_REVIEW_20261102.md"
R2_AMENDMENT = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_PROJECTION_AMENDMENT_20261102.md"
R2_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_PROJECTION_REVIEW_20261102.md"
AUDIT05_CONTRACT = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_AUDIT05_CONTINUATION_20261102.md"
AUDIT05_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_AUDIT05_CONTINUATION_REVIEW_20261102.md"
STATIC_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_AUDIT05_IMPLEMENTATION_REVIEW_20261102.md"
GATE_HELPER = REPO / "research_papers" / "JEPA" / "level_oracle_20261018" / "launch_monthly_test_index_v2_audit_20261024.py"
HARNESS = Path(__file__).resolve()
PREPARATION = BASE / "weekly_zone_event_value_path_audit05_fixtures_01"
ATTEMPT = PREPARATION / "attempt01"
MINIMUM_BYTES = 2_000_000_000
BRANCH = "research/multiscale-v1r1-net-usd"

PINS = {
    AUDITOR: "f1d21dc7eb877e03b186ae96dead70dd668e9b914bf078c2adae659d9b52e592",
    AUDITOR_TESTS: "d86e32cc07ee3204b454ebb0596a316008c2a1155fd519f6ca7cd93a80178472",
    BUILDER: "ed260c55a62fecce729dadce170b5dec5c98049be92580495131e007a7ffd5ab",
    BASELINE_AUDITOR: "ef2bdd340c3e87ce9edd7d9b45b256ece02208646fa7fe095f167b24127a8122",
    BASELINE_TESTS: "f291c190833dfe3eff4ccd086e3fe323374f21f582ab9c97aaaa45fca79fe82b",
    BASELINE_R2_AUDITOR: "414d80331301c82404f81e366a63682b029f4f51cc7c0d659e370d6c20886d83",
    BASELINE_R2_TESTS: "d02eba1fa017b46e0c22727b13153db6a36e08ed7bd99ff89f1397d232fa6eb4",
    BASELINE_V2_AUDITOR: "1ad942249d2eb160b2e8fe1ed902e577f9617dc4c11575e297cf5262f5aa61f2",
    BASELINE_V2_TESTS: "e7f7c6e7cd7f9b93a1763b969205478da87182247b1d284d7c9fd5b980112bf7",
    BASELINE_V1_AUDITOR: "d927bca9cd64d51792d68a425a021d9fff9c5cb1ff5dfef79f02dcdcc3c2d2e7",
    BASELINE_V1_TESTS: "ac5d0fbee457396e8d9e15d217089a17927f1ba73953d681ffa02f2fc4840deb",
    CONTRACT: "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9",
    AMENDMENT: "65fd1aaef25ddea13957ce07e6c21285771adc889f097d603f93e00572cf1146",
    R1_AMENDMENT: "2afce2d91e35393aad91e9dd65d6b9d9b6e156c0307ffd0f67823254032943d3",
    R1_REVIEW: "886c0a83e25a65d8d63aef3ef26b530da984d224613d04139b590b78ac787a17",
    R2_AMENDMENT: "22be603919cc93b3d6c7342a7e373e62939f58b8b69efec98dc1e5f136ee260b",
    R2_REVIEW: "8cc822668fabb5f51cfc0f114ff8dab7c932af69247eae6f346ab4c7604e1abb",
    AUDIT05_CONTRACT: "5c7a50f8fae9df5d720e63fd9274e6535d0bc179d24da25ea8e98896157bf831",
    AUDIT05_REVIEW: "3fa755f7f44d23e86419f14de8ffcda431f41dd58d377e14d2927ba109e32b89",
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_AUDITOR_FINAL_REVIEW_20261102.md": "0e3be7b719c8e7540630132414ae1ba4b29c9ccdc3bd22f962a25d2746c377d0",
    WEEK / "weekly_zone_event_value_path_v2r2_audit_fixture_archive_01" / "archive_manifest.json": "ea3da7c348d4490db2bcbf5a1de068b150b66ea5eedd4ca6b2b0ab9c4d6586b5",
    WEEK / "weekly_zone_event_value_path_v2r2_audit_fixture_archive_01" / "archive_receipt.json": "ecebe93f742bcb797a6658a914544f0d94de0827f9d5dd668d29147493ba3b9c",
    WEEK / "weekly_zone_event_value_path_v2r2_audit_fixture_archive_01" / "preparation" / "receipt.json": "13a684c979d6b6c2954a8809616d043837f4fbf82d2a2307ae098d0a746e8e85",
    WEEK / "weekly_zone_event_value_path_v2r2_audit_failure_archive_01" / "archive_manifest.json": "5b4e28c746031ea3d0ab1240fe1a4d6cfa58b9d4ff65a0cade453eefb03f1a32",
    WEEK / "weekly_zone_event_value_path_v2r2_audit_failure_archive_01" / "archive_receipt.json": "aacda99f5a6e95b5320a7ef4c16bb3726fe7db4b1f4bc8bdf86ed728e89c0490",
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_04" / "exit.json": "f1ac99c69196d1d0dac865763feacecc3561ad8c14bad8b3282010cbb1bb6505",
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_04" / "failure_receipt.json": "3f7dd8276e868a212d01dcce38e904084256e9b3fb9cef9dfb8e01559bb4d445",
    BASE / "weekly_zone_event_value_paths_audit_observer_04" / "journal.jsonl": "60fd1841fa621d82ecefdf8eebc7fd7472884c38839ab68be9cc142d3174ed98",
    STATIC_REVIEW: "dfc197102b4540a4834d20a932d67998a3c75abec2788068cf8869b3907858f3",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
}
PIN_BYTES = {AUDITOR: 116851, AUDITOR_TESTS: 4720, BUILDER: 91830,
    BASELINE_AUDITOR: 115418, BASELINE_TESTS: 41783,
    BASELINE_R2_AUDITOR: 116851, BASELINE_R2_TESTS: 51396,
    BASELINE_V2_AUDITOR: 112984, BASELINE_V2_TESTS: 36968,
    BASELINE_V1_AUDITOR: 96078, BASELINE_V1_TESTS: 21539, CONTRACT: 36466,
    AMENDMENT: 15276, R1_AMENDMENT: 4291, R1_REVIEW: 1584,
    R2_AMENDMENT: 5938, R2_REVIEW: 1721, AUDIT05_CONTRACT: 4553,
    AUDIT05_REVIEW: 1475,
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_AUDITOR_FINAL_REVIEW_20261102.md": 2674,
    WEEK / "weekly_zone_event_value_path_v2r2_audit_fixture_archive_01" / "archive_manifest.json": 22326,
    WEEK / "weekly_zone_event_value_path_v2r2_audit_fixture_archive_01" / "archive_receipt.json": 904,
    WEEK / "weekly_zone_event_value_path_v2r2_audit_fixture_archive_01" / "preparation" / "receipt.json": 6177,
    WEEK / "weekly_zone_event_value_path_v2r2_audit_failure_archive_01" / "archive_manifest.json": 8250,
    WEEK / "weekly_zone_event_value_path_v2r2_audit_failure_archive_01" / "archive_receipt.json": 639,
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_04" / "exit.json": 358,
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_04" / "failure_receipt.json": 305,
    BASE / "weekly_zone_event_value_paths_audit_observer_04" / "journal.jsonl": 5421626,
    STATIC_REVIEW: 3120, GATE_HELPER: 31463}

# B06/R3 authorities replace the inherited audit05 fixture set below.  Draft
# pins deliberately fail closed until the independent static reviews freeze.
AUDITOR = WEEK / "audit_weekly_zone_event_value_paths_v2r3.py"
AUDITOR_TESTS = WEEK / "test_audit_weekly_zone_event_value_paths_v2r3.py"
WAIT_HELPER = WEEK / "bounded_resource_wait.py"
WAIT_TESTS = WEEK / "test_bounded_resource_wait.py"
WAIT_AMENDMENT = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_RESOURCE_WAIT_AMENDMENT_20261102.md"
WAIT_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_RESOURCE_WAIT_REVIEW_20261102.md"
STATIC_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R3_STATIC_REVIEW_20261102.md"
LINT_CORRECTION_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R3_LINT_CORRECTION_REVIEW_20261102.md"
BASELINE_ATTEMPT05 = WEEK / "audit_weekly_zone_event_value_paths_v2r2_attempt05.py"
PRODUCER_V2 = WEEK / "build_weekly_zone_event_value_paths_v2.py"
BASELINE_V1 = WEEK / "audit_weekly_zone_event_value_paths.py"
BASELINE_V2 = WEEK / "audit_weekly_zone_event_value_paths_v2.py"
BASELINE_R1 = WEEK / "audit_weekly_zone_event_value_paths_v2r1.py"
BASELINE_R2 = WEEK / "audit_weekly_zone_event_value_paths_v2r2.py"
PREPARATION = BASE / "weekly_zone_event_value_path_v2r3_fixtures_02"
ATTEMPT = PREPARATION / "attempt01"
PINS = {
    AUDITOR: "effc36ce5cc496698f9aca1ea496046c89ca0d8e0deabe3f354dd892a94a5643",
    AUDITOR_TESTS: "1988d35201c102c9166bd1ed03ff4dde20c49cd1bdc89dc251beeeb8597a531d",
    WAIT_HELPER: "33873bfab0549f390cd3973ab3d9af07a19d5df643f44d483bd17c74140c07a9",
    WAIT_TESTS: "330727ae60bac42ca89b623a1064a50bc0fade8ce52f9d61ec709fa5d6bd2678",
    WAIT_AMENDMENT: "b4f9980897ee8834e296d025f8bdbf8d30e3a7bedb97d558e4ebc6ad8aa25dab",
    WAIT_REVIEW: "2a109c48cf6395a2b25b206c42694d8fdf6629a33030466f3ae755d206653e8d",
    STATIC_REVIEW: "e2a57018da8b02e1e33235a02f85db8fa3d07d6e5ee1c5faf426cab5459f476a",
    LINT_CORRECTION_REVIEW: "3a6e5e76da4b74ab93d5dcd36834988a31c480ae87b88abe595f9e42e8f98079",
    BASELINE_ATTEMPT05: "f1d21dc7eb877e03b186ae96dead70dd668e9b914bf078c2adae659d9b52e592",
    PRODUCER_V2: "ed260c55a62fecce729dadce170b5dec5c98049be92580495131e007a7ffd5ab",
    BASELINE_V1: "d927bca9cd64d51792d68a425a021d9fff9c5cb1ff5dfef79f02dcdcc3c2d2e7",
    BASELINE_V2: "1ad942249d2eb160b2e8fe1ed902e577f9617dc4c11575e297cf5262f5aa61f2",
    BASELINE_R1: "ef2bdd340c3e87ce9edd7d9b45b256ece02208646fa7fe095f167b24127a8122",
    BASELINE_R2: "414d80331301c82404f81e366a63682b029f4f51cc7c0d659e370d6c20886d83",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
}
PIN_BYTES = {
    AUDITOR: 120016, AUDITOR_TESTS: 51568, WAIT_HELPER: 17926, WAIT_TESTS: 18115,
    WAIT_AMENDMENT: 14061, WAIT_REVIEW: 2531,
    STATIC_REVIEW: 2794, LINT_CORRECTION_REVIEW: 1745, GATE_HELPER: 31463,
    BASELINE_ATTEMPT05: 116851, PRODUCER_V2: 91830,
    BASELINE_V1: 96078, BASELINE_V2: 112984,
    BASELINE_R1: 115418, BASELINE_R2: 116851,
}
# The reviewed tests execute admit_pins() against its compact metadata
# authorities.  Bind every file they read before Python can import the suite.
_TRANSITIVE = {
    BASE / "weekly_zone_event_source_plan_01/entry_plan.jsonl": (1018910, "0db0065f2dcdd254122a4c4575ecb9c752318cab3a90666ad8215aef922d91bb"),
    BASE / "weekly_zone_event_source_plan_01/weekly_sources.jsonl": (2367532, "59081a049d11a0403204ca06e62ef4661bb6de3cd042548e081c10f8eaddd1f7"),
    BASE / "weekly_zone_event_source_plan_01/summary.json": (1398, "612ecf1abf18f973656aeda347f21efe563f5c84b9cc06f96e22383ed19b3b39"),
    BASE / "weekly_zone_event_source_plan_01/manifest.json": (5094, "a0a9d330992d7f5768550c5b60401a701e1c1b02caec4a0967de50b7c7f13161"),
    BASE / "weekly_zone_event_source_plan_audit_01/audit.json": (9071, "1b71077525d146cd7e2166076f987afd315fe46e27c15e51c4f7555be06299cd"),
    BASE / "weekly_zone_event_source_plan_audit_01/manifest.json": (8945, "49935941c89b67f2aef69272201d68d089d9499d0fca71838867b5457bf85ba7"),
    BASE / "weekly_zone_event_source_plan_audit_observer_01/exit.json": (1337, "bfdf36bfb7f636f27a391ad0b0ed38be5306e69b0c5be144d0c0599de9d65362"),
    BASE / "h2_dataset_v2_01/inventory.json": (5589855, "099dcf065a62705cbd88f2c1b90b2e4a9b99ff4d994ad703634101920c934b12"),
    BASE / "h2_dataset_v2_01/inventory_manifest.json": (187, "c417e67f3499522d4ebd4a21bf28d1cba8ce249ef2d38a1352001216714bb899"),
    BASE / "h2_dataset_v2_01/manifest.json": (1541, "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8"),
    BASE / "h2_dataset_v2_extension_2026q3_partial_01/inventory.json": (327384, "f633d0ee192f28650698a4033ee7f6d2dc00dad07aa38239c40e9e2b5092ea5c"),
    BASE / "h2_dataset_v2_extension_2026q3_partial_01/inventory_manifest.json": (197, "5b39e0796599fa72b5d74d029885a24fd57fada207f12989576737aa46d75b2f"),
    BASE / "h2_dataset_v2_extension_2026q3_partial_01/manifest.json": (6184, "b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b"),
    BASE / "h2_boundary_bridge_01/inventory.json": (14721, "599ca400fecae12ce4098187a45af3ee0cf8c1b070e060d8c84e422ce92c6161"),
    BASE / "h2_boundary_bridge_01/inventory_manifest.json": (330, "0a7a5fab0f932d23fdf9a3140027f99eb85ccd958b79ef55152c53ab5ced70f2"),
    BASE / "h2_boundary_bridge_01/manifest.json": (4748, "9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86"),
    BASE / "h2_boundary_bridge_01/unified_calendar.json": (232573, "be622bb24aca35448594743dfeb5236e6b2d08a4410109b20302891f8c1fa7d6"),
    BASE / "h2_context_1030_01/inventory.json": (1829496, "b347523c8638825c822100cf78b5a03ab4f56fc948bc7aa23674b0b73866df5e"),
    BASE / "h2_context_1030_01/inventory_manifest.json": (197, "a7547c375a4de723b168ce2983b84ba98a35dd70aef24c82ed08c1e3c5358ea8"),
    BASE / "h2_context_1030_01/manifest.json": (612610, "77aaf00d60accc071ff1f58ec099cee72bc3a4150f89e4ad41a601821a74a38a"),
    BASE / "h2_context_q3_1030_01/inventory.json": (1489911, "25da3398984c633a044eef4f20c5525c6224a1b076a5941d0311fae93eab68cf"),
    BASE / "h2_context_q3_1030_01/inventory_manifest.json": (193, "2b74c18e98366670e77e3d2a4fc19e260cd404e6959fbd7e140f2e88fd5050be"),
    BASE / "h2_context_q3_1030_01/manifest.json": (172889, "1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66"),
    WEEK / "build_weekly_h2_dataset_v2.py": (33142, "ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945"),
    WEEK / "weekly_multiday_source_pilot.py": (31380, "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878"),
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md": (36466, "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9"),
    BASE / "weekly_zone_event_value_paths_observer_01/exit.json": (358, "48b635e9fbdeef729de7c1be0b24948e21655ceb6cf5a154c02809e8a8a951d3"),
    BASE / "weekly_zone_event_value_paths_observer_01/failure_receipt.json": (305, "6ee1cb2ee3a29b74484c5ed54fe5049eb45da6e299c4fcd9ea8553bc809086fc"),
    BASE / "weekly_zone_event_value_paths_observer_01/journal.jsonl": (6473, "a12c7f5d5e1171e220cc1bcefd9f3191caf6e414f5c5df1cdeb5b4bc8b36aa08"),
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R1_AUDIT_ADMISSION_AMENDMENT_20261102.md": (4291, "2afce2d91e35393aad91e9dd65d6b9d9b6e156c0307ffd0f67823254032943d3"),
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_PROJECTION_AMENDMENT_20261102.md": (5938, "22be603919cc93b3d6c7342a7e373e62939f58b8b69efec98dc1e5f136ee260b"),
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2_CALENDAR_AMENDMENT_20261102.md": (15276, "65fd1aaef25ddea13957ce07e6c21285771adc889f097d603f93e00572cf1146"),
}
for _path, (_bytes, _sha) in _TRANSITIVE.items():
    PINS[_path] = _sha
    PIN_BYTES[_path] = _bytes
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


def affinity_mask(handle: int) -> int:
    process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
    if not KERNEL32.GetProcessAffinityMask(ctypes.c_void_p(handle), ctypes.byref(process_mask), ctypes.byref(system_mask)):
        raise ctypes.WinError(ctypes.get_last_error())
    return process_mask.value


def actual_process_state() -> dict[str, object]:
    affinity = affinity_mask(int(CURRENT_PROCESS))
    threads = {name: os.environ.get(name) for name in THREAD_ENV}
    cuda = os.environ.get("CUDA_VISIBLE_DEVICES")
    if affinity != 1 or any(value != "1" for value in threads.values()) or cuda != "-1":
        raise RuntimeError(f"parent process state drift: affinity={affinity}, threads={threads}, cuda={cuda}")
    return {"cpu_affinity_mask": affinity, "thread_variables": threads, "cuda_visible_devices": cuda}


def assert_plain_exact(path: Path, expected_bytes: int, expected_sha256: str) -> dict[str, object]:
    if path != Path(os.path.abspath(path)) or not path.is_file() or path.is_symlink():
        raise RuntimeError(f"pin absent, linked, or aliased: {path}")
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
        raise RuntimeError(f"ambiguous pin: {path}")
    digest = sha256(path)
    if info.st_size != expected_bytes or digest != expected_sha256:
        raise RuntimeError(f"pin mismatch: {path}")
    return {"bytes": info.st_size, "sha256": digest}


def require_finalized(harness_sha256: str) -> dict[Path, tuple[int, str]]:
    expected = {path: (PIN_BYTES[path], digest) for path, digest in PINS.items()}
    expected[HARNESS] = (HARNESS.stat().st_size, harness_sha256.lower())
    for expected_bytes, digest in expected.values():
        if not isinstance(expected_bytes, int) or expected_bytes < 1:
            raise RuntimeError("V2 auditor fixture harness requires finalized byte pins")
        if len(digest) != 64 or digest != digest.lower() or any(character not in "0123456789abcdef" for character in digest):
            raise RuntimeError("V2 auditor fixture harness requires finalized lowercase SHA-256 pins")
    return expected


def snapshot(expected: dict[Path, tuple[int, str]]) -> dict[str, dict[str, object]]:
    return {str(path): assert_plain_exact(path, size, digest) for path, (size, digest) in expected.items()}


def verify_publication(expected: dict[Path, tuple[int, str]]) -> str:
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip()
    if branch != BRANCH:
        raise RuntimeError(f"unexpected branch: {branch}")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    remote = subprocess.check_output(["git", "ls-remote", "origin", f"refs/heads/{BRANCH}"], cwd=REPO, text=True).split()[0]
    if commit != remote:
        raise RuntimeError("local HEAD is not published remote HEAD")
    for path in expected:
        try:
            relative = path.relative_to(REPO).as_posix()
        except ValueError:
            continue
        published = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=REPO)
        if published != path.read_bytes():
            raise RuntimeError(f"publication mismatch: {path}")
    return commit


def best_effort_diff(expected: dict[Path, tuple[int, str]]) -> list[dict[str, object]]:
    differences = []
    for path, (size, digest) in expected.items():
        try:
            actual = assert_plain_exact(path, size, digest)
        except Exception as error:
            differences.append({"path": str(path), "expected": {"bytes": size, "sha256": digest}, "actual": {"error": f"{type(error).__name__}: {error}"}})
    return differences


def observe_and_gate(gate_module: object, stage: str, expected: dict[Path, tuple[int, str]]) -> None:
    pins = snapshot(expected)
    state = actual_process_state()
    resources = gate_module.observation()
    disk_free = shutil.disk_usage(BASE).free
    record = {"utc": utc_now(), "stage": stage, **state, "resources": resources,
        "disk_free_bytes": disk_free, "minimum_bytes": MINIMUM_BYTES, "pins": pins, "child_created": False}
    write_json(ATTEMPT / f"{stage}_resource_observation.json", record)
    gate_module.gate(resources)
    if disk_free < MINIMUM_BYTES:
        raise RuntimeError(f"D: free bytes {disk_free} below {MINIMUM_BYTES}")


def run_child(name: str, command: list[str]) -> dict[str, object]:
    started, metadata_error, creation_epoch, child_mask = utc_now(), None, None, None
    with (ATTEMPT / f"{name}_stdout.txt").open("wb") as stdout, (ATTEMPT / f"{name}_stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(command, cwd=str(WEEK), env=os.environ.copy(), stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            try:
                import psutil
                child = psutil.Process(process.pid)
                creation_epoch = child.create_time()
                child_mask = affinity_mask(int(process._handle))
                if child_mask != 1:
                    raise RuntimeError(f"child affinity mask {child_mask}, expected 1")
            except Exception as error:
                metadata_error = f"{type(error).__name__}: {error}"
            try:
                write_json(ATTEMPT / f"{name}_process.json", {"pid": process.pid, "creation_epoch": creation_epoch,
                    "start_utc": started, "command": command, "cpu_affinity_mask": child_mask,
                    "metadata_error": metadata_error, "handle_retained": True, "wait_pending": True})
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else f"{metadata_error}; {detail}"
        finally:
            exit_code = process.wait()
    result = {"pid": process.pid, "creation_epoch": creation_epoch, "start_utc": started, "end_utc": utc_now(),
        "command": command, "cpu_affinity_mask": child_mask, "metadata_error": metadata_error,
        "exit_code": exit_code, "handle_retained": True}
    write_json(ATTEMPT / f"{name}_exit.json", result)
    if metadata_error is not None:
        raise RuntimeError(metadata_error)
    return result


def failure(status: str, **extra: object) -> None:
    write_json(ATTEMPT / "failure_receipt.json", {"status": status, "attempt": "attempt01", "retry": False,
        "real_value_audit_executed": False, "utc": utc_now(), "closing_pin_differences": best_effort_diff(ACTIVE_EXPECTED), **extra})


def main() -> int:
    global ACTIVE_EXPECTED
    parser = argparse.ArgumentParser(description="Run reviewed V2 value-path auditor synthetic fixtures")
    parser.add_argument("--harness-sha256", required=True)
    args = parser.parse_args()
    expected = require_finalized(args.harness_sha256)
    ACTIVE_EXPECTED = expected
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"unexpected Python: {sys.executable}")
    if PREPARATION.exists() or ATTEMPT.exists():
        raise RuntimeError("V2 auditor fixture root already exists")
    snapshot(expected)
    publication_commit = verify_publication(expected)
    PREPARATION.mkdir(parents=False, exist_ok=False)
    ATTEMPT.mkdir(parents=False, exist_ok=False)
    for source, (_size, digest) in expected.items():
        shutil.copyfile(source, ATTEMPT / f"{digest}_{source.name}.before_test")
    write_json(ATTEMPT / "publication.json", {"commit": publication_commit, "branch": BRANCH, "verified_utc": utc_now()})

    specification = importlib.util.spec_from_file_location("official_gate", GATE_HELPER)
    if specification is None or specification.loader is None:
        raise RuntimeError("official gate import unavailable")
    gate_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    try:
        observe_and_gate(gate_module, "preflight", expected)
    except Exception as error:
        failure("RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_AUDITOR_FIXTURES", error=f"{type(error).__name__}: {error}", completed=[])
        return 2

    suite_files = [str(WAIT_HELPER), str(WAIT_TESTS), str(AUDITOR), str(AUDITOR_TESTS)]
    commands = [
        ("compile", [str(PYTHON), "-X", "utf8", "-m", "py_compile", *suite_files]),
        ("ruff", [str(PYTHON), "-X", "utf8", "-m", "ruff", "check", *suite_files]),
        ("pytest", [str(PYTHON), "-X", "utf8", "-m", "pytest", "-q", str(WAIT_TESTS), str(AUDITOR_TESTS)]),
    ]
    completed: list[dict[str, object]] = []
    for name, command in commands:
        try:
            observe_and_gate(gate_module, name, expected)
        except Exception as error:
            failure("RESOURCE_OR_DISK_GATE_REJECTED_BEFORE_AUDITOR_FIXTURE_CHILD", stage=name, completed=completed, error=f"{type(error).__name__}: {error}", child_created=False)
            return 2
        try:
            result = run_child(name, command)
        except Exception as error:
            failure("AUDITOR_FIXTURE_CHILD_LAUNCH_OR_OBSERVATION_FAILED", stage=name, completed=completed, error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
            return 3
        completed.append({"stage": name, "exit_code": result["exit_code"]})
        if result["exit_code"] != 0:
            failure("FORMAL_AUDITOR_FIXTURE_STAGE_FAILED", stage=name, completed=completed, exit_code=result["exit_code"])
            return int(result["exit_code"]) or 1
    closing = snapshot(expected)
    receipt = {"status": "PASS_FORMAL_SYNTHETIC_B06_R3_BOUNDED_RESOURCE_WAIT_FIXTURES02", "attempt": "attempt01",
        "stages": completed, "closing_sha256": closing, "real_value_audit_executed": False,
        "bounded_wait_synthetic_only": True, "real_resource_wait_performed": False,
        "fit_performed": False, "api_read": False, "broker_read": False, "retry": False, "closed_utc": utc_now()}
    write_json(ATTEMPT / "receipt.json", receipt)
    write_json(PREPARATION / "receipt.json", receipt)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        if ATTEMPT.is_dir():
            failure("AUDITOR_FIXTURE_HARNESS_FAILED_CLOSED", error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
        raise


