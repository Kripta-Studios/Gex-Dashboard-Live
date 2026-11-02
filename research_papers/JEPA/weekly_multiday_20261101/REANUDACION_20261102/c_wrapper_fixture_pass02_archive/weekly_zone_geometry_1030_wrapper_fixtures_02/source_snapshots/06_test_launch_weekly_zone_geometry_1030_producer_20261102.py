"""Focused synthetic wrapper checks.  They never import or run C/B science code."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("c_geometry_launcher_under_test", HERE / "launch_weekly_zone_geometry_1030_producer_20261102.py")
assert SPEC is not None and SPEC.loader is not None
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


def write(path: Path, payload: bytes) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"path": str(path.resolve()), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def json_pin(path: Path, value: object) -> dict[str, object]:
    return write(path, (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8"))


def synthetic_final_b_bundle(root: Path) -> tuple[dict[str, object], dict[str, object]]:
    """Metadata-only final-B closure fixture: no market files, raw values, or NPZ."""
    authorities = {name: write(root / "authorities" / f"{name}.txt", (name + "\n").encode("utf-8"))
                   for name in launcher.B_AUTHORITY_KEYS}
    outputs = {name: write(root / "producer" / name, (name + "\n").encode("utf-8")) for name in launcher.B_OUTPUT_NAMES}
    producer_exit = json_pin(root / "producer_observer" / "exit.json", {
        "exit_code": 0, "value_child_exit_code": 0, "changed_pins": [], "metadata_error": None,
        "retry": False, "pid": 101, "creation_epoch": 1.0,
    })
    producer_process = json_pin(root / "producer_observer" / "process.json", {"pid": 101, "creation_epoch": 1.0})
    producer_journal = write(root / "producer_observer" / "journal.jsonl", b'{"event":"STARTED","kind":"CLOSING_REHASH","identity":"all"}\n{"event":"COMPLETED","kind":"CLOSING_REHASH","identity":"all"}\n')
    semantic = {"bytes": 137640, "sha256": "a" * 64, "order": "DATE_ASC_TICKER_ORDINAL_SPY_QQQ_SPXW", "rows": 2790}
    calendar = {"raw_file_pin": authorities["unified_calendar"], "semantic_jsonl": semantic,
                "identity_set_preserved": True, "close_i_preserved": True}
    envelope = {"raw_pin": authorities["unified_calendar"], "canonical_jsonl_bytes": 137640,
                "canonical_jsonl_sha256": "a" * 64, "canonical_order": "DATE_ASC_TICKER_ORDINAL_SPY_QQQ_SPXW",
                "rows": 2790, "identity_set_preserved": True, "close_i_preserved": True,
                "raw_order": "TICKER_MAJOR_QQQ_SPXW_SPY_DATE_ASC"}
    flags = {name: (name in {"option_raw_values_read", "parquet_footers_read", "spot_cache_arrays_read"})
             for name in launcher.FINAL_B_FLAG_KEYS - {"selected_policy"}}
    flags["selected_policy"] = None
    manifest_outputs = {name: {**pin, "rows": 1} for name, pin in outputs.items()}
    producer_manifest = json_pin(root / "producer" / "manifest.json", {
        "schema": "weekly_zone_event_value_paths_manifest_v2_calendar_normalized", "status": "COMPLETE_OUTCOME_FREE_VALUE_PATHS",
        "outputs": manifest_outputs, "authority_inputs": authorities, "flags": flags, "calendar_normalization": envelope,
    })
    audit_exit = json_pin(root / "audit_observer" / "exit.json", {
        "exit_code": 0, "value_child_exit_code": 0, "changed_pins": [], "metadata_error": None,
        "retry": False, "pid": 202, "creation_epoch": 2.0,
    })
    audit_process = json_pin(root / "audit_observer" / "process.json", {"pid": 202, "creation_epoch": 2.0})
    audit_journal = write(root / "audit_observer" / "journal.jsonl", b'{"event":"STARTED","stage":"WRITE_AUDIT_OUTPUT","identity":"audit"}\n{"event":"COMPLETED","stage":"WRITE_AUDIT_OUTPUT","identity":"audit"}\n')
    audit = json_pin(root / "audit" / "audit.json", {
        "schema": "weekly_zone_event_value_paths_audit_v2_calendar_normalized", "status": "PASS",
        "producer": {"manifest": producer_manifest, "exit": producer_exit}, "flags": flags,
        "reconstruction": {"calendar_normalization": envelope},
    })
    audit_manifest = json_pin(root / "audit" / "manifest.json", {
        "schema": "weekly_zone_event_value_paths_audit_manifest_v2_calendar_normalized", "status": "PASS",
        "audit": audit, "producer_manifest": producer_manifest, "producer_exit": producer_exit,
        "authority_inputs": authorities, "flags": flags, "calendar_normalization": envelope,
    })
    bundle = {"schema": launcher.BUNDLE_SCHEMA, "status": launcher.BUNDLE_STATUS,
              "producer": {"manifest": producer_manifest, "outputs": outputs,
                           "observer": {"exit": producer_exit, "process": producer_process, "journal": producer_journal}},
              "auditor": {"audit": audit, "manifest": audit_manifest, "exit": audit_exit,
                          "process": audit_process, "journal": audit_journal},
              "authority_inputs": authorities, "calendar": calendar, "flags": flags, "data_scope": "SEEN_DEVELOPMENT"}
    return bundle, json_pin(root / "bundle.json", bundle)


class Helper:
    def observation(self) -> dict[str, int]:
        return {"available_ram_bytes": launcher.MINIMUM_BYTES, "free_commit_bytes": launcher.MINIMUM_BYTES}

    def gate(self, value: object) -> None:
        del value


@contextmanager
def synthetic_run_environment(root: Path, command: list[str], gate_side_effect: object, process_times_side_effect: object | None = None):
    output, child_observer, observer = root / "output", root / "child_observer", root / "launcher_observer"
    (root / "plan.json").write_text("{}\n", encoding="utf-8")
    roots = {"output_dir": str(output), "observer_dir": str(child_observer),
             "launcher_observer_dir": str(observer), "journal": str(child_observer / "journal.jsonl")}
    plan = {"repository_pins": {}, "b_final": {}, "runtime_binding": {}}
    patches = [
        mock.patch.object(launcher, "OUTPUT", output), mock.patch.object(launcher, "CHILD_OBSERVER", child_observer),
        mock.patch.object(launcher, "OBSERVER", observer), mock.patch.object(launcher, "BASE", root),
        mock.patch.object(launcher, "WEEK", root), mock.patch.object(launcher, "EXPECTED_ROOTS", roots),
        mock.patch.object(launcher, "PYTHON", Path(sys.executable)),
        mock.patch.object(launcher, "configure_parent", return_value={"cpu_affinity_mask": 1, "thread_variables": {}, "cuda_visible_devices": "-1"}),
        mock.patch.object(launcher, "load_plan", return_value=plan), mock.patch.object(launcher, "verify_publication", return_value="f" * 40),
        mock.patch.object(launcher, "authoritative_pins", return_value={}), mock.patch.object(launcher, "snapshot_pins", return_value={}),
        mock.patch.object(launcher, "verify_closing", return_value=[]), mock.patch.object(launcher, "load_gate_helper", return_value=Helper()),
        mock.patch.object(launcher, "resource_gate", side_effect=gate_side_effect), mock.patch.object(launcher, "child_command", return_value=command),
    ]
    if process_times_side_effect is not None:
        patches.append(mock.patch.object(launcher, "process_times", side_effect=process_times_side_effect))
    with ExitStack() as stack:
        for patch in patches:
            stack.enter_context(patch)
        yield output, child_observer, observer


class ProducerLauncherFocusedTests(unittest.TestCase):
    def test_publication_rejects_plan_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plan = Path(temporary) / "outside.json"
            pin = write(plan, b"{}\n")
            with self.assertRaises(launcher.LaunchError):
                launcher.verify_publication(plan, str(pin["sha256"]), {"repository_pins": {}})

    def test_actual_hardlink_is_rejected_as_physical_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.txt"
            second = root / "second.txt"
            pin = write(first, b"synthetic\n")
            os.link(first, second)
            with self.assertRaises(launcher.LaunchError):
                launcher.verify_pin(pin, "hardlinked synthetic pin")

    def test_exact_producer_child_cli_has_only_contractual_arguments(self) -> None:
        plan = {"repository_pins": {"c_producer": launcher.CANONICAL_C_PRODUCER_PIN},
                "runtime_binding": {"binding": {"path": r"C:\binding.json", "bytes": 1, "sha256": "a" * 64}}}
        roots = {"output_dir": r"D:\out", "observer_dir": r"D:\child", "launcher_observer_dir": r"D:\parent", "journal": r"D:\child\journal.jsonl"}
        with mock.patch.object(launcher, "PYTHON", Path(r"C:\Python\python.exe")), mock.patch.object(launcher, "EXPECTED_ROOTS", roots):
            actual = launcher.child_command(plan)
        self.assertEqual(actual, [r"C:\Python\python.exe", "-X", "utf8", "-u", launcher.CANONICAL_C_PRODUCER_PIN["path"],
                                  "--binding-json", r"C:\binding.json", "--binding-sha256", "a" * 64,
                                  "--output-dir", r"D:\out", "--observer-dir", r"D:\child", "--journal", r"D:\child\journal.jsonl"])

    def test_frozen_c_final_review_and_canonical_producer_admission_are_positive(self) -> None:
        self.assertEqual(launcher.CANONICAL_C_PRODUCER_PIN["path"], str(launcher.CANONICAL_C_PRODUCER))
        self.assertEqual(launcher.CANONICAL_C_PRODUCER_PIN["bytes"], 73030)
        launcher.validate_c_final_review_pin(launcher.C_FINAL_REVIEW_PIN)

    def test_pending_plan_and_invalid_hash_reject_before_any_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = root / "plan.json"
            pending = {"schema": launcher.PLAN_SCHEMA, "status": launcher.PLAN_STATUS, "branch": "PENDING_BRANCH",
                       "data_scope": "SEEN_DEVELOPMENT", "repository_pins": {}, "b_final": {}, "runtime_binding": {},
                       "runtime_roots": dict(launcher.EXPECTED_ROOTS)}
            pin = write(plan, json.dumps(pending, sort_keys=True).encode("utf-8"))
            with self.assertRaises(launcher.LaunchError):
                launcher.load_plan(plan, str(pin["sha256"]))
            with self.assertRaises(launcher.LaunchError):
                launcher.load_plan(plan, "0" * 64)
            self.assertFalse((root / "output").exists())

    def test_formal_fixture_receipt_must_be_pass_and_match_retained_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launcher_pin = write(root / "launcher.py", b"launcher\n")
            tests_pin = write(root / "tests.py", b"tests\n")
            clean_exit = {"exit_code": 0, "pid": 5, "creation_epoch": 1.0,
                          "metadata_error": None, "changed_pins": [], "retry": False}
            for name, changed in (("metadata", {"metadata_error": "synthetic"}), ("pins", {"changed_pins": ["drift"]}),
                                  ("retry", {"retry": True}), ("epoch", {"creation_epoch": float("inf")})):
                exit_value = {**clean_exit, **changed}
                exit_pin = write(root / f"pytest_exit_{name}.json", json.dumps(exit_value, sort_keys=True, allow_nan=True).encode("utf-8"))
                receipt = {"schema": launcher.FORMAL_FIXTURE_SCHEMA, "status": launcher.FORMAL_FIXTURE_STATUS,
                           "launcher": launcher_pin, "tests": tests_pin, "compile_exit_code": 0, "ruff_exit_code": 0,
                           "pytest_exit_code": 0, "pytest_exit": exit_pin}
                receipt_pin = write(root / f"receipt_{name}.json", json.dumps(receipt, sort_keys=True).encode("utf-8"))
                with self.assertRaises(launcher.LaunchError, msg=name):
                    launcher.validate_formal_fixture_closure(receipt_pin, exit_pin, {"launcher": launcher_pin, "launcher_tests": tests_pin})

    def test_synthetic_final_b_metadata_closure_rejects_calendar_envelope_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, bundle_pin = synthetic_final_b_bundle(root)
            self.assertEqual(launcher.validate_final_b_bundle(bundle_pin)["status"], launcher.BUNDLE_STATUS)
            altered = json.loads(json.dumps(bundle))
            altered["calendar"]["semantic_jsonl"]["order"] = "DRIFT"
            altered_pin = json_pin(root / "altered_bundle.json", altered)
            with self.assertRaises(launcher.LaunchError):
                launcher.validate_final_b_bundle(altered_pin)

    def test_initial_gate_failure_happens_before_observer_or_child(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with synthetic_run_environment(root, [sys.executable, "-c", "raise SystemExit(0)"], launcher.LaunchError("synthetic gate")) as (output, child, observer):
                with mock.patch.object(launcher.subprocess, "Popen") as popen:
                    with self.assertRaises(launcher.LaunchError):
                        launcher.run(root / "plan.json", "a" * 64)
            self.assertFalse(output.exists())
            self.assertFalse(child.exists())
            self.assertFalse(observer.exists())
            popen.assert_not_called()

    def test_actual_retained_windows_handle_for_harmless_child(self) -> None:
        child = subprocess.Popen([sys.executable, "-c", "raise SystemExit(0)"], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        initial = launcher.process_times(int(child._handle))
        affinity = launcher.affinity_mask(int(child._handle))
        self.assertIsInstance(initial["creation_epoch"], float)
        self.assertEqual(affinity, 1)  # The formal harness sets CPU0 before this wrapper-only test.
        self.assertEqual(child.wait(), 0)
        final = launcher.process_times(int(child._handle))
        self.assertEqual(final["creation_epoch"], initial["creation_epoch"])
        self.assertIsNotNone(final["exit_epoch"])

    def test_metadata_exception_still_waits_fast_child_and_is_effective_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            created: list[subprocess.Popen[bytes]] = []
            real_popen = subprocess.Popen

            def capture(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
                child = real_popen(*args, **kwargs)
                created.append(child)
                return child

            gates = [({"available_ram_bytes": launcher.MINIMUM_BYTES, "free_commit_bytes": launcher.MINIMUM_BYTES}, launcher.MINIMUM_BYTES)] * 2
            with synthetic_run_environment(root, [sys.executable, "-c", "raise SystemExit(0)"], gates,
                                           launcher.LaunchError("synthetic retained metadata failure")) as (_output, _child, observer):
                with mock.patch.object(launcher, "affinity_mask", return_value=1), mock.patch.object(launcher.subprocess, "Popen", side_effect=capture):
                    result = launcher.run(root / "plan.json", "a" * 64)
            self.assertEqual(result, 3)
            self.assertEqual(created[0].returncode, 0)
            exit_record = json.loads((observer / "exit.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_record["geometry_child_exit_code"], 0)
            self.assertEqual(exit_record["exit_code"], 3)
            self.assertIn("metadata", exit_record["metadata_error"])

    def test_nonzero_harmless_child_is_retained_and_propagated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            process_times = [
                {"creation_epoch": 1.0, "exit_epoch": None, "kernel_seconds": 0.0, "user_seconds": 0.0},
                {"creation_epoch": 1.0, "exit_epoch": 2.0, "kernel_seconds": 0.0, "user_seconds": 0.0},
            ]
            gates = [({"available_ram_bytes": launcher.MINIMUM_BYTES, "free_commit_bytes": launcher.MINIMUM_BYTES}, launcher.MINIMUM_BYTES)] * 2
            with synthetic_run_environment(root, [sys.executable, "-c", "raise SystemExit(7)"], gates, process_times) as (_output, _child, observer):
                with mock.patch.object(launcher, "affinity_mask", return_value=1):
                    result = launcher.run(root / "plan.json", "a" * 64)
            self.assertEqual(result, 7)
            record = json.loads((observer / "exit.json").read_text(encoding="utf-8"))
            self.assertEqual(record["geometry_child_exit_code"], 7)
            self.assertEqual(record["exit_code"], 7)

    def test_mirror_conflict_preserves_child_partial_and_wrapper_is_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            child_observer = root / "child_observer"
            code = ("from pathlib import Path; p=Path(r'%s'); p.mkdir(); "
                    "(p/'process.json').write_bytes(bytes([123,125,10]))" % str(child_observer))
            process_times = [
                {"creation_epoch": 1.0, "exit_epoch": None, "kernel_seconds": 0.0, "user_seconds": 0.0},
                {"creation_epoch": 1.0, "exit_epoch": 2.0, "kernel_seconds": 0.0, "user_seconds": 0.0},
            ]
            gates = [({"available_ram_bytes": launcher.MINIMUM_BYTES, "free_commit_bytes": launcher.MINIMUM_BYTES}, launcher.MINIMUM_BYTES)] * 2
            with synthetic_run_environment(root, [sys.executable, "-c", code], gates, process_times) as (_output, child, observer):
                with mock.patch.object(launcher, "affinity_mask", return_value=1):
                    result = launcher.run(root / "plan.json", "a" * 64)
            self.assertEqual(result, 5)
            self.assertEqual((child / "process.json").read_bytes(), b"{}\n")
            self.assertFalse((child / "exit.json").exists())
            exit_record = json.loads((observer / "exit.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_record["exit_code"], 5)
            self.assertEqual(exit_record["mirror"]["status"], "FAILED")

    def test_full_success_synthetic_run_has_byte_exact_parent_observed_mirrors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            child_observer = root / "child_observer"
            code = "from pathlib import Path; Path(r'%s').mkdir()" % str(child_observer)
            process_times = [
                {"creation_epoch": 1.0, "exit_epoch": None, "kernel_seconds": 0.0, "user_seconds": 0.0},
                {"creation_epoch": 1.0, "exit_epoch": 2.0, "kernel_seconds": 0.0, "user_seconds": 0.0},
            ]
            gates = [({"available_ram_bytes": launcher.MINIMUM_BYTES, "free_commit_bytes": launcher.MINIMUM_BYTES}, launcher.MINIMUM_BYTES)] * 2
            with synthetic_run_environment(root, [sys.executable, "-c", code], gates, process_times) as (_output, child, observer):
                with mock.patch.object(launcher, "affinity_mask", return_value=1):
                    result = launcher.run(root / "plan.json", "a" * 64)
            self.assertEqual(result, 0)
            self.assertEqual((observer / "process.json").read_bytes(), (child / "process.json").read_bytes())
            self.assertEqual((observer / "exit.json").read_bytes(), (child / "exit.json").read_bytes())
            exit_record = json.loads((observer / "exit.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_record["exit_code"], 0)
            self.assertEqual(exit_record["geometry_child_exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
