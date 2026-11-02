"""Launch the reviewed B06/R3 value-path audit exactly once."""

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


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]


# Same retained-handle implementation exercised by the 136-PASS fixture05.
# https://learn.microsoft.com/windows/desktop/procthread/process-handles-and-identifiers
# https://learn.microsoft.com/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes
# https://learn.microsoft.com/windows/win32/api/winbase/nf-winbase-getprocessaffinitymask
KERNEL32.GetProcessTimes.argtypes = [ctypes.c_void_p, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)]
KERNEL32.GetProcessTimes.restype = ctypes.c_int
CURRENT_PROCESS = KERNEL32.GetCurrentProcess()
if not KERNEL32.SetProcessAffinityMask(CURRENT_PROCESS, ctypes.c_size_t(1)):
    raise ctypes.WinError(ctypes.get_last_error())

import datetime as dt
import hashlib
import importlib.util
import json
import math
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
PRODUCER = BASE / "weekly_zone_event_value_paths_02"
PRODUCER_EXIT = BASE / "weekly_zone_event_value_paths_observer_02" / "exit.json"
OUTPUT = BASE / "weekly_zone_event_value_paths_audit_06"
AUDIT_OBSERVER = BASE / "weekly_zone_event_value_paths_audit_observer_06"
OBSERVER = BASE / "weekly_zone_event_value_paths_audit_launcher_observer_06"
JOURNAL = OBSERVER / "journal.jsonl"
IMPLEMENTATION_PINS_JSON = OBSERVER / "implementation_pins.json"
BRANCH = "research/multiscale-v1r1-net-usd"
MINIMUM_BYTES = 2_000_000_000

BUILDER = WEEK / "audit_weekly_zone_event_value_paths_v2r3.py"
SPOT = WEEK / "weekly_zone_event_spot_paths.py"
BUILDER_TESTS = WEEK / "test_audit_weekly_zone_event_value_paths_v2r3.py"
FOCAL_TESTS = WEEK / "test_bounded_resource_wait.py"
SPOT_TESTS = WEEK / "test_weekly_zone_event_spot_paths.py"
CONTRACT = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_RESOURCE_WAIT_AMENDMENT_20261102.md"
CONTRACT_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_RESOURCE_WAIT_REVIEW_20261102.md"
BUILDER_FINAL_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R3_FINAL_IMPLEMENTATION_REVIEW_20261102.md"
SPOT_FINAL_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_SPOT_PATH_FINAL_REVIEW_20261102.md"
RUNTIME_BINDING = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_B06_AUDIT_RUNTIME_BINDING_20261102.md"
LAUNCHER = Path(__file__).resolve()
GATE_HELPER = LEVEL / "launch_monthly_test_index_v2_audit_20261024.py"
WAIT_HELPER = WEEK / "bounded_resource_wait.py"
WAIT_STATIC_REVIEW = WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R3_STATIC_REVIEW_20261102.md"

REPO_PINS = {
    BUILDER: "effc36ce5cc496698f9aca1ea496046c89ca0d8e0deabe3f354dd892a94a5643",
    SPOT: "0953d344b28992da4b92c561daa7663bb48fe89ea309f6323f53b39c6a0dbd38",
    BUILDER_TESTS: "30686f927bfdd566ab1a355bd2c42ded7be181198320fe8ea51911d9d2966b83",
    FOCAL_TESTS: "330727ae60bac42ca89b623a1064a50bc0fade8ce52f9d61ec709fa5d6bd2678",
    SPOT_TESTS: "80d91442dafbf8b2beace31b46eb117913e410a1ccb820ee467f2d0c24d9d3eb",
    CONTRACT: "b4f9980897ee8834e296d025f8bdbf8d30e3a7bedb97d558e4ebc6ad8aa25dab",
    CONTRACT_REVIEW: "2a109c48cf6395a2b25b206c42694d8fdf6629a33030466f3ae755d206653e8d",
    BUILDER_FINAL_REVIEW: "756a8e9321c7ea728e2e9692cba5be2c5b3a8001aef249d79a3cef8e14a6b57f",
    SPOT_FINAL_REVIEW: "221004483dd77fb5112bbb05ca2ec44191c31cfb19a26815b2950c82e721a140",
    RUNTIME_BINDING: "a62ef18805190e0835b9388bef69a5974d26b61144c3d4a99ceafa384e60b54e",
    WAIT_HELPER: "33873bfab0549f390cd3973ab3d9af07a19d5df643f44d483bd17c74140c07a9",
    WAIT_STATIC_REVIEW: "e2a57018da8b02e1e33235a02f85db8fa3d07d6e5ee1c5faf426cab5459f476a",
    WEEK / "audit_weekly_zone_event_value_paths_v2r2.py": "414d80331301c82404f81e366a63682b029f4f51cc7c0d659e370d6c20886d83",
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_PROJECTION_AMENDMENT_20261102.md": "22be603919cc93b3d6c7342a7e373e62939f58b8b69efec98dc1e5f136ee260b",
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_PROJECTION_REVIEW_20261102.md": "8cc822668fabb5f51cfc0f114ff8dab7c932af69247eae6f346ab4c7604e1abb",
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_AUDITOR_FINAL_REVIEW_20261102.md": "0e3be7b719c8e7540630132414ae1ba4b29c9ccdc3bd22f962a25d2746c377d0",
    WEEK / "weekly_zone_event_value_path_v2r2_audit_failure_archive_01" / "archive_manifest.json": "5b4e28c746031ea3d0ab1240fe1a4d6cfa58b9d4ff65a0cade453eefb03f1a32",
    WEEK / "weekly_zone_event_value_path_v2r2_audit_failure_archive_01" / "archive_receipt.json": "aacda99f5a6e95b5320a7ef4c16bb3726fe7db4b1f4bc8bdf86ed728e89c0490",
    WEEK / "weekly_zone_event_value_path_audit05_fixture_archive_01" / "archive_manifest.json": "e30934352e3c497af7c42582d87f4dbd1b705b0d2861566a72771a36e4997476",
    WEEK / "weekly_zone_event_value_path_audit05_fixture_archive_01" / "archive_receipt.json": "9dac140e20caee1731605435e59be2527151075c5f7845ff2493011ba044704f",
    WEEK / "weekly_zone_event_value_path_audit05_fixture_archive_01" / "preparation" / "receipt.json": "a7386d32a0eb035ad6ea688cb0e9bc34e598cde0fb7817d6f32e3786b289933f",
    WEEK / "weekly_zone_event_value_path_v2r3_fixture_pass_archive_05" / "archive_manifest.json": "4aeecb54fde6345d14e07d3d39f56b5c994cd4e93fa8293f846a9712e835475f",
    WEEK / "weekly_zone_event_value_path_v2r3_fixture_pass_archive_05" / "archive_receipt.json": "8fd075c4f01ee205a0fe997593a0894bc60643007a2a5463943aa0f48232a757",
    WEEK / "weekly_zone_event_value_path_v2r3_fixture_pass_archive_05" / "preparation" / "receipt.json": "459771b5521b53af55f61cc221d4c81f1858f5db3eeb2d6013b69b71936ab541",
    WEEK / "weekly_zone_event_value_path_audit05_failure_archive_01" / "archive_manifest.json": "534cbdeb44bc9a72929bdc443d5322d59207592d7f7a40c43898b7cf65acb10c",
    WEEK / "weekly_zone_event_value_path_audit05_failure_archive_01" / "archive_receipt.json": "4e069ae21021203b31e39b112ada6a5bcbc565597ceb88dbe114220ee2942214",
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R1_AUDIT_ADMISSION_AMENDMENT_20261102.md": "2afce2d91e35393aad91e9dd65d6b9d9b6e156c0307ffd0f67823254032943d3",
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R1_ADMISSION_REVIEW_20261102.md": "886c0a83e25a65d8d63aef3ef26b530da984d224613d04139b590b78ac787a17",
    WEEK / "weekly_zone_event_value_path_v2r2_audit_fixture_archive_01" / "archive_manifest.json": "ea3da7c348d4490db2bcbf5a1de068b150b66ea5eedd4ca6b2b0ab9c4d6586b5",
    WEEK / "weekly_zone_event_value_path_v2r2_audit_fixture_archive_01" / "archive_receipt.json": "ecebe93f742bcb797a6658a914544f0d94de0827f9d5dd668d29147493ba3b9c",
    WEEK / "weekly_zone_event_value_path_v2r2_audit_fixture_archive_01" / "preparation" / "receipt.json": "13a684c979d6b6c2954a8809616d043837f4fbf82d2a2307ae098d0a746e8e85",
    WEEK / "weekly_zone_event_value_path_v2r1_audit_failure_archive_01" / "archive_manifest.json": "f859a148c7cb1a5237db1dff78b75cf05727036d69a3fbaf5a417aa028e7dda1",
    WEEK / "weekly_zone_event_value_path_v2r1_audit_failure_archive_01" / "archive_receipt.json": "0c6e6739858564b4aa1c34ea305f1dfba9ed00134b4cc2875a3c0440d36f1ab6",
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2_CALENDAR_AMENDMENT_20261102.md": "65fd1aaef25ddea13957ce07e6c21285771adc889f097d603f93e00572cf1146",
    WEEK / "weekly_zone_event_value_path_v2r1_audit_fixture_archive_01" / "archive_manifest.json": "553fa549a38ca5ce2e7c7e15d07d0b57b1d2ec2d9836e8649eb99e4ee565e431",
    WEEK / "weekly_zone_event_value_path_v2r1_audit_fixture_archive_01" / "archive_receipt.json": "30a6237620c9cc0b113bee5560548524ba626bed60e9225968c0acad4b2f7025",
    WEEK / "weekly_zone_event_value_path_v2r1_audit_fixture_archive_01" / "preparation" / "receipt.json": "1a0c2bb3595f4957dc47359a5ade399fa5a17dc75b653d0986a0463edb1037e4",
    WEEK / "weekly_zone_event_value_path_v2_audit_failure_archive_01" / "archive_manifest.json": "b8713683e1fdf2ab5402f9f12abea690bdce6d6d30a170547fcf9a591fe5fe7e",
    WEEK / "weekly_zone_event_value_path_v2_audit_failure_archive_01" / "archive_receipt.json": "28c0bbc28212cebe642b209c7859ef30c12ee5f7674e47cbff1144f4eb6b9e38",
    WEEK / "weekly_zone_event_value_path_v2_producer_closure_archive_01" / "archive_manifest.json": "2161419b29df6fff7cd2c3fccffc226070422ea4fff56f721f1f665f285d924c",
    WEEK / "weekly_zone_event_value_path_v2_producer_closure_archive_01" / "archive_receipt.json": "11448ef0f9b041a01b73c2182ad1c1e7c97d4d1b1727f7e489583c4d7cbdf780",
    WEEK / "weekly_zone_event_value_path_v2_fixture_archive_02" / "manifest.json": "0ddaddb71c93b3fba333046f980f04478c034e90e79bc6cbc2ec5384e1be6913",
    WEEK / "weekly_zone_event_value_path_v2_fixture_archive_02" / "receipt.json": "2d529e36702f270ec62834b8133233d355816be71b6ebc00a64e09311d39ef06",
    WEEK / "weekly_zone_event_value_path_v2_fixture_archive_02" / "preparation" / "receipt.json": "23fa4c3468a971596c3fe078246733b92676f5b70289f6eba56dc6622e8b66dd",
    WEEK / "build_weekly_h2_dataset_v2.py": "ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945",
    WEEK / "weekly_multiday_source_pilot.py": "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878",
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md": "e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9",
    GATE_HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
}
REPO_BYTES = {
    BUILDER: 120016,
    SPOT: 40814,
    BUILDER_TESTS: 52481,
    FOCAL_TESTS: 18115,
    SPOT_TESTS: 33144,
    CONTRACT: 14061,
    CONTRACT_REVIEW: 2531,
    BUILDER_FINAL_REVIEW: 3153,
    SPOT_FINAL_REVIEW: 1486,
    RUNTIME_BINDING: 4314,
    WAIT_HELPER: 17926,
    WAIT_STATIC_REVIEW: 2794,
    WEEK / "audit_weekly_zone_event_value_paths_v2r2.py": 116851,
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_PROJECTION_AMENDMENT_20261102.md": 5938,
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_PROJECTION_REVIEW_20261102.md": 1721,
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_AUDITOR_FINAL_REVIEW_20261102.md": 2674,
    WEEK / "weekly_zone_event_value_path_v2r2_audit_failure_archive_01" / "archive_manifest.json": 8250,
    WEEK / "weekly_zone_event_value_path_v2r2_audit_failure_archive_01" / "archive_receipt.json": 639,
    WEEK / "weekly_zone_event_value_path_audit05_fixture_archive_01" / "archive_manifest.json": 34834,
    WEEK / "weekly_zone_event_value_path_audit05_fixture_archive_01" / "archive_receipt.json": 865,
    WEEK / "weekly_zone_event_value_path_audit05_fixture_archive_01" / "preparation" / "receipt.json": 10223,
    WEEK / "weekly_zone_event_value_path_v2r3_fixture_pass_archive_05" / "archive_manifest.json": 49545,
    WEEK / "weekly_zone_event_value_path_v2r3_fixture_pass_archive_05" / "archive_receipt.json": 1661,
    WEEK / "weekly_zone_event_value_path_v2r3_fixture_pass_archive_05" / "preparation" / "receipt.json": 14440,
    WEEK / "weekly_zone_event_value_path_audit05_failure_archive_01" / "archive_manifest.json": 8182,
    WEEK / "weekly_zone_event_value_path_audit05_failure_archive_01" / "archive_receipt.json": 2001,
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R1_AUDIT_ADMISSION_AMENDMENT_20261102.md": 4291,
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2R1_ADMISSION_REVIEW_20261102.md": 1584,
    WEEK / "weekly_zone_event_value_path_v2r2_audit_fixture_archive_01" / "archive_manifest.json": 22326,
    WEEK / "weekly_zone_event_value_path_v2r2_audit_fixture_archive_01" / "archive_receipt.json": 904,
    WEEK / "weekly_zone_event_value_path_v2r2_audit_fixture_archive_01" / "preparation" / "receipt.json": 6177,
    WEEK / "weekly_zone_event_value_path_v2r1_audit_failure_archive_01" / "archive_manifest.json": 8246,
    WEEK / "weekly_zone_event_value_path_v2r1_audit_failure_archive_01" / "archive_receipt.json": 545,
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_V2_CALENDAR_AMENDMENT_20261102.md": 15276,
    WEEK / "weekly_zone_event_value_path_v2r1_audit_fixture_archive_01" / "archive_manifest.json": 19771,
    WEEK / "weekly_zone_event_value_path_v2r1_audit_fixture_archive_01" / "archive_receipt.json": 904,
    WEEK / "weekly_zone_event_value_path_v2r1_audit_fixture_archive_01" / "preparation" / "receipt.json": 4906,
    WEEK / "weekly_zone_event_value_path_v2_audit_failure_archive_01" / "archive_manifest.json": 8223,
    WEEK / "weekly_zone_event_value_path_v2_audit_failure_archive_01" / "archive_receipt.json": 543,
    WEEK / "weekly_zone_event_value_path_v2_producer_closure_archive_01" / "archive_manifest.json": 8727,
    WEEK / "weekly_zone_event_value_path_v2_producer_closure_archive_01" / "archive_receipt.json": 778,
    WEEK / "weekly_zone_event_value_path_v2_fixture_archive_02" / "manifest.json": 25384,
    WEEK / "weekly_zone_event_value_path_v2_fixture_archive_02" / "receipt.json": 978,
    WEEK / "weekly_zone_event_value_path_v2_fixture_archive_02" / "preparation" / "receipt.json": 3846,
    WEEK / "build_weekly_h2_dataset_v2.py": 33142,
    WEEK / "weekly_multiday_source_pilot.py": 31380,
    WEEK / "WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md": 36466,
    GATE_HELPER: 31463,
}

EXTERNAL_PINS = {
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_05" / "exit.json": "23e44d041ecde9f5a01c319a15d88594c2e705f8d813e16635cbd07e2d1cc195",
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_05" / "failure_receipt.json": "668849cfce14c04083a9ec3db415991ddf9671c858252cb00ff573c8544c1724",
    BASE / "weekly_zone_event_value_paths_audit_observer_05" / "journal.jsonl": "f535e20b1a382a9a00ea8cc48c3f34f3fb4abb827600e43caea5772d45b6c8f3",
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_04" / "exit.json": "f1ac99c69196d1d0dac865763feacecc3561ad8c14bad8b3282010cbb1bb6505",
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_04" / "failure_receipt.json": "3f7dd8276e868a212d01dcce38e904084256e9b3fb9cef9dfb8e01559bb4d445",
    BASE / "weekly_zone_event_value_paths_audit_observer_04" / "journal.jsonl": "60fd1841fa621d82ecefdf8eebc7fd7472884c38839ab68be9cc142d3174ed98",
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_03" / "exit.json": "1c875a80a7265d39e331da010f26cb8cabaa6c767f42cdc673f5ce5e3f196776",
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_03" / "failure_receipt.json": "32b88636a1915b41beeb3541be245a02d2597bee79e477fb26a014367d6841c3",
    BASE / "weekly_zone_event_value_paths_audit_observer_03" / "journal.jsonl": "128ecab9a92c99a68382c45abc61b8c248b7df5e4c6ef51f64e4dbf583d09352",
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_02" / "exit.json": "a44f227b7f5b3767f8ec06c2462da0ee89102b17970889d848c6085f8abc214e",
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_02" / "failure_receipt.json": "ccf38442a9d0bb2ef1083c4b2839960746d622a67a1c24f1a2037fa89549a7bf",
    BASE / "weekly_zone_event_value_paths_audit_observer_02" / "journal.jsonl": "2cb784367246a9ef1f5aaa84a94d6f6995682a67782ecff962b45b547c8abdaf",
    PRODUCER / "manifest.json": "a30376cec17aa649b2869efe1bba8f4a19f901e3a10399942df70c7fe2a42f33",
    PRODUCER / "cache_admission.jsonl": "e0b4512791adbe70642d8ca83391dd4f0379037aae02f2af4888242bab3b0e14",
    PRODUCER / "decision_contracts.parquet": "5afe57e6ffe694afc0ae1526b5dc11456ed5de98a7940d384a29ab2a911e619e",
    PRODUCER / "option_quote_observations.parquet": "130028eb260989fb259a3b62a336863acc20b132662f8441ecb3bbdde7885123",
    PRODUCER / "segment_coverage.parquet": "cae4961ea80279374fe15ebd2575bd48d46ab75378d1a04b74664b5e97419a1a",
    PRODUCER / "source_admission.jsonl": "33f00a254d65b0d17194a67eb0b5971e9c73564050f6f343088a46b029fb9740",
    PRODUCER / "spot_coverage.jsonl": "2ed4a4b63a2f49f7bb6c1737fb6ae7ab4f5225f7c767185889f7fb591c78b972",
    PRODUCER / "spot_paths.parquet": "bc1beb6115187ef33733681b3ba21aade9b13356aa6f2f71bc98705719c11a72",
    PRODUCER / "summary.json": "3ffc6e0e3b972a97ef67135df22c41335211545aa6d0ab5d9250afa1cda0345b",
    PRODUCER_EXIT: "06af66e622ce1119f04c2c496b161660abd897a02ecdb902dd71d39b26eb2dc3",
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
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_05" / "exit.json": 352,
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_05" / "failure_receipt.json": 305,
    BASE / "weekly_zone_event_value_paths_audit_observer_05" / "journal.jsonl": 6023889,
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_04" / "exit.json": 358,
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_04" / "failure_receipt.json": 305,
    BASE / "weekly_zone_event_value_paths_audit_observer_04" / "journal.jsonl": 5421626,
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_03" / "exit.json": 357,
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_03" / "failure_receipt.json": 305,
    BASE / "weekly_zone_event_value_paths_audit_observer_03" / "journal.jsonl": 4636,
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_02" / "exit.json": 358,
    BASE / "weekly_zone_event_value_paths_audit_launcher_observer_02" / "failure_receipt.json": 305,
    BASE / "weekly_zone_event_value_paths_audit_observer_02" / "journal.jsonl": 349,
    PRODUCER / "manifest.json": 3134113,
    PRODUCER / "cache_admission.jsonl": 5104757,
    PRODUCER / "decision_contracts.parquet": 280184,
    PRODUCER / "option_quote_observations.parquet": 272229832,
    PRODUCER / "segment_coverage.parquet": 316213,
    PRODUCER / "source_admission.jsonl": 3964221,
    PRODUCER / "spot_coverage.jsonl": 1675844,
    PRODUCER / "spot_paths.parquet": 27388006,
    PRODUCER / "summary.json": 4009,
    PRODUCER_EXIT: 358,
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


def affinity_mask(handle: int | None = None) -> int:
    process_mask = ctypes.c_size_t()
    system_mask = ctypes.c_size_t()
    target = int(CURRENT_PROCESS) if handle is None else handle
    if not KERNEL32.GetProcessAffinityMask(ctypes.c_void_p(target), ctypes.byref(process_mask), ctypes.byref(system_mask)):
        raise ctypes.WinError(ctypes.get_last_error())
    return process_mask.value


def process_times(handle: int) -> dict[str, float | None]:
    creation, exited, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
    if not KERNEL32.GetProcessTimes(ctypes.c_void_p(handle), ctypes.byref(creation), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
        raise ctypes.WinError(ctypes.get_last_error())

    def ticks(value: FILETIME) -> int:
        return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)

    def unix_epoch(value: FILETIME) -> float | None:
        count = ticks(value)
        return None if count == 0 else (count - 116_444_736_000_000_000) / 10_000_000.0

    result = {"creation_epoch": unix_epoch(creation), "exit_epoch": unix_epoch(exited),
        "kernel_seconds": ticks(kernel) / 10_000_000.0, "user_seconds": ticks(user) / 10_000_000.0}
    if result["creation_epoch"] is None or not math.isfinite(result["creation_epoch"]):
        raise RuntimeError("retained process handle has no finite creation time")
    for key in ("kernel_seconds", "user_seconds"):
        if not math.isfinite(result[key]) or result[key] < 0.0:
            raise RuntimeError(f"retained process handle invalid {key}")
    if result["exit_epoch"] is not None and (
        not math.isfinite(result["exit_epoch"]) or result["exit_epoch"] < result["creation_epoch"]
    ):
        raise RuntimeError("retained process handle invalid exit time")
    return result


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


def close_resource_wait_evidence(wait_module: object) -> tuple[dict[str, object], list[dict[str, object]]]:
    pins: dict[str, object] = {"launcher": None, "audit_child": None}
    invalid: list[dict[str, object]] = []
    for key, path in {
        "launcher": OBSERVER / "resource_wait.jsonl",
        "audit_child": AUDIT_OBSERVER / "resource_wait.jsonl",
    }.items():
        if not os.path.lexists(path):
            continue
        try:
            if not path.is_file() or path.is_symlink():
                raise RuntimeError("resource wait evidence is not a plain file")
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise RuntimeError("resource wait evidence link or file type")
            current = path
            while True:
                attributes = getattr(os.lstat(current), "st_file_attributes", 0)
                if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                    raise RuntimeError("resource wait evidence reparse path")
                if current.parent == current:
                    break
                current = current.parent
            pins[key] = wait_module.resource_wait_pin(path)
        except Exception as error:
            evidence: dict[str, object] = {"path": str(path), "error": f"{type(error).__name__}: {error}"}
            try:
                evidence.update({"bytes": path.stat().st_size, "sha256": sha256(path)})
            except Exception as pin_error:
                evidence["pin_error"] = f"{type(pin_error).__name__}: {pin_error}"
            invalid.append(evidence)
    return pins, invalid


def main() -> int:
    global ACTIVE_EXPECTED
    require_finalized()
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"unexpected Python: {sys.executable}")
    if OUTPUT.exists() or AUDIT_OBSERVER.exists() or OBSERVER.exists():
        raise RuntimeError("contracted output or observer root already exists")
    commit = verify_publication()
    verify_external()
    before = snapshot_pins()
    ACTIVE_EXPECTED = {
        **{path: (REPO_BYTES[path], digest) for path, digest in REPO_PINS.items()},
        **{path: (EXTERNAL_BYTES[path], digest) for path, digest in EXTERNAL_PINS.items()},
        LAUNCHER: (before[str(LAUNCHER)]["bytes"], before[str(LAUNCHER)]["sha256"]),
    }
    # The initial admission gate is deliberately fail-fast and precedes creation
    # of every B06 observer, as required by the resource-wait amendment.
    specification = importlib.util.spec_from_file_location("official_gate", GATE_HELPER)
    if specification is None or specification.loader is None:
        raise RuntimeError("official resource helper unavailable")
    gate_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(gate_module)
    resources = gate_module.observation()
    disk_free = shutil.disk_usage(BASE).free
    process_state = actual_process_state()
    gate_module.gate(resources)
    if disk_free < MINIMUM_BYTES:
        raise RuntimeError(f"initial D: free bytes {disk_free} below {MINIMUM_BYTES}")

    OBSERVER.mkdir(parents=False, exist_ok=False)
    write_json(IMPLEMENTATION_PINS_JSON, implementation_pins())
    before = snapshot_pins()
    observation = {"utc": utc_now(), "resources": resources,
        "disk_free_bytes": disk_free, "minimum_bytes": MINIMUM_BYTES,
        **process_state, "publication_commit": commit, "pins": before,
        "initial_gate_before_observer": True}
    write_json(OBSERVER / "resource_observation.json", observation)

    wait_spec = importlib.util.spec_from_file_location("b06_bounded_resource_wait", WAIT_HELPER)
    if wait_spec is None or wait_spec.loader is None:
        raise RuntimeError("bounded resource wait helper unavailable")
    wait_module = importlib.util.module_from_spec(wait_spec)
    wait_spec.loader.exec_module(wait_module)
    waiter = wait_module.ResourceWaiter(
        observation=gate_module.observation,
        official_gate=gate_module.gate,
        disk_probe=lambda: shutil.disk_usage(BASE).free,
        evidence_path=OBSERVER / "resource_wait.jsonl",
    )

    try:
        accepted_resources = waiter.acquire("LAUNCH_AUDITOR_CHILD", "audit06")
    except (KeyboardInterrupt, InterruptedError) as error:
        wait_pins, invalid_wait = close_resource_wait_evidence(wait_module)
        changed = verify_closing(before)
        write_json(OBSERVER / "exit.json", {
            "exit_code": 130, "value_child_exit_code": None,
            "utc": utc_now(), "source": "bounded_wait_interrupted_before_child_no_process",
            "pid": None, "creation_epoch": None, "cpu_affinity": None,
            "metadata_error": f"{type(error).__name__}: {error}",
            "changed_pins": changed, "resource_wait_pins": wait_pins,
            "resource_wait_invalid_evidence": invalid_wait, "retry": False,
        })
        failure("BOUNDED_RESOURCE_WAIT_INTERRUPTED_BEFORE_AUDITOR_CHILD",
            error=f"{type(error).__name__}: {error}", child_created=False,
            resource_wait_pins=wait_pins, resource_wait_invalid_evidence=invalid_wait)
        raise
    except Exception as error:
        wait_pins, invalid_wait = close_resource_wait_evidence(wait_module)
        changed = verify_closing(before)
        exit_code = 5 if invalid_wait else 2
        write_json(OBSERVER / "exit.json", {
            "exit_code": exit_code, "value_child_exit_code": None,
            "utc": utc_now(), "source": "bounded_wait_before_child_no_process",
            "pid": None, "creation_epoch": None, "cpu_affinity": None,
            "metadata_error": f"{type(error).__name__}: {error}",
            "changed_pins": changed, "resource_wait_pins": wait_pins,
            "resource_wait_invalid_evidence": invalid_wait, "retry": False,
        })
        failure("BOUNDED_RESOURCE_WAIT_REJECTED_BEFORE_AUDITOR_CHILD",
            error=f"{type(error).__name__}: {error}", child_created=False,
            resource_wait_pins=wait_pins, resource_wait_invalid_evidence=invalid_wait)
        return exit_code
    pre_child_pins = snapshot_pins()
    pre_child_resources = {
        "available_ram_bytes": accepted_resources["available_ram_bytes"],
        "free_commit_bytes": accepted_resources["free_commit_bytes"],
    }
    pre_child_disk_free = accepted_resources["disk_free_bytes"]
    pre_child_state = actual_process_state()
    pre_child_roots = {
        "output_lexists": os.path.lexists(OUTPUT),
        "audit_observer_lexists": os.path.lexists(AUDIT_OBSERVER),
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
        if pre_child_roots != {
            "output_lexists": False,
            "audit_observer_lexists": False,
            "observer_lexists": True,
            "observer_is_directory": True,
            "observer_is_symlink": False,
        }:
            raise RuntimeError(f"runtime root state drift immediately before child: {pre_child_roots}")
    except Exception as error:
        wait_pins, invalid_wait = close_resource_wait_evidence(wait_module)
        changed = verify_closing(before)
        exit_code = 5 if invalid_wait else 2
        write_json(OBSERVER / "exit.json", {
            "exit_code": exit_code, "value_child_exit_code": None,
            "utc": utc_now(), "source": "pre_child_admission_no_process",
            "pid": None, "creation_epoch": None, "cpu_affinity": None,
            "metadata_error": f"{type(error).__name__}: {error}",
            "changed_pins": changed, "resource_wait_pins": wait_pins,
            "resource_wait_invalid_evidence": invalid_wait, "retry": False,
        })
        failure("RESOURCE_DISK_OR_ROOT_GATE_REJECTED_IMMEDIATELY_BEFORE_VALUE_CHILD",
            error=f"{type(error).__name__}: {error}", observation=pre_child_observation,
            child_created=False, resource_wait_pins=wait_pins,
            resource_wait_invalid_evidence=invalid_wait)
        return exit_code

    command = [
        str(PYTHON), "-X", "utf8", "-u", str(BUILDER),
        "--execute-reviewed-audit",
        "--producer-root", str(PRODUCER),
        "--producer-manifest-sha256", EXTERNAL_PINS[PRODUCER / "manifest.json"],
        "--producer-exit", str(PRODUCER_EXIT),
        "--producer-exit-sha256", EXTERNAL_PINS[PRODUCER_EXIT],
        "--auditor-sha256", REPO_PINS[BUILDER],
        "--tests-sha256", REPO_PINS[BUILDER_TESTS],
        "--review-path", str(BUILDER_FINAL_REVIEW),
        "--review-bytes", str(REPO_BYTES[BUILDER_FINAL_REVIEW]),
        "--review-sha256", REPO_PINS[BUILDER_FINAL_REVIEW],
        "--runtime-binding-path", str(RUNTIME_BINDING),
        "--runtime-binding-bytes", str(REPO_BYTES[RUNTIME_BINDING]),
        "--runtime-binding-sha256", REPO_PINS[RUNTIME_BINDING],
        "--launcher-path", str(LAUNCHER),
        "--launcher-bytes", str(LAUNCHER.stat().st_size),
        "--launcher-sha256", sha256(LAUNCHER),
        "--output", str(OUTPUT),
        "--observer", str(AUDIT_OBSERVER),
    ]
    write_json(OBSERVER / "admission.json", {"utc": utc_now(), "command": command, "publication_commit": commit, "observation": observation, "output": str(OUTPUT), "observer": str(OBSERVER), "journal": str(JOURNAL)})

    metadata_error = None
    creation_epoch = None
    child_mask = None
    final_times: dict[str, float | None] | None = None
    started = time.monotonic()
    started_utc = utc_now()
    with (OBSERVER / "stdout.log").open("wb") as stdout, (OBSERVER / "stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, cwd=str(WEEK), env=os.environ.copy(), stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            try:
                retained_handle = int(process._handle)
                initial_times = process_times(retained_handle)
                creation_epoch = initial_times["creation_epoch"]
                child_mask = affinity_mask(retained_handle)
                if child_mask != 1:
                    raise RuntimeError(f"child affinity mask {child_mask}, expected 1")
            except Exception as error:
                metadata_error = f"{type(error).__name__}: {error}"
            try:
                write_json(OBSERVER / "process.json", {"pid": process.pid, "creation_epoch": creation_epoch, "start_utc": started_utc, "command": command, "cpu_affinity": child_mask, "metadata_error": metadata_error, "handle_retained": True, "wait_pending": True})
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else f"{metadata_error}; {detail}"
        finally:
            child_exit = process.wait()
            try:
                final_times = process_times(int(process._handle))
                if final_times["creation_epoch"] != creation_epoch:
                    raise RuntimeError("retained process handle creation time drift")
                if final_times["exit_epoch"] is None:
                    raise RuntimeError("retained process handle missing post-wait exit time")
            except Exception as error:
                detail = f"{type(error).__name__}: {error}"
                metadata_error = detail if metadata_error is None else f"{metadata_error}; {detail}"

    resource_wait_pins, resource_wait_invalid_evidence = close_resource_wait_evidence(wait_module)
    changed = verify_closing(before)
    effective_exit = child_exit
    if metadata_error is not None and effective_exit == 0:
        effective_exit = 3
    if changed and effective_exit == 0:
        effective_exit = 4
    if resource_wait_invalid_evidence and effective_exit == 0:
        effective_exit = 5
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
            "process_times": final_times,
            "metadata_error": metadata_error,
            "changed_pins": changed,
            "resource_wait_pins": resource_wait_pins,
            "resource_wait_invalid_evidence": resource_wait_invalid_evidence,
            "retry": False,
        },
    )
    if effective_exit != 0 and not (OBSERVER / "failure_receipt.json").exists():
        failure("VALUE_CHILD_OR_CLOSURE_FAILED", exit_code=effective_exit, value_child_exit_code=child_exit,
            metadata_error=metadata_error, changed_pins=changed,
            resource_wait_pins=resource_wait_pins,
            resource_wait_invalid_evidence=resource_wait_invalid_evidence,
            partial_output_not_authorized_for_adoption=True)
    return int(effective_exit)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except InterruptedError:
        raise
    except Exception as error:
        if OBSERVER.is_dir() and not (OBSERVER / "failure_receipt.json").exists():
            failure("LAUNCHER_FAILED_CLOSED", error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
        raise

