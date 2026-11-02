"""Synthetic-only checks for the future C audit wrapper; no C/B runner or data."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("c_audit_wrapper_under_test", HERE / "launch_weekly_zone_geometry_1030_audit_20261102.py")
assert SPEC is not None and SPEC.loader is not None
wrapper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wrapper)


def write(path: Path, payload: bytes) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"path": str(path.resolve()), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def pinned_json(path: Path, value: object) -> dict[str, object]:
    return write(path, (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))


class FakePrimitives:
    def __init__(self, gates: list[object] | None = None) -> None:
        self.gates = list(gates or [({"available_ram_bytes": 2_000_000_000, "free_commit_bytes": 2_000_000_000}, 2_000_000_000)] * 2)
        self.waited = False

    @staticmethod
    def _pin(value: object, label: str = "pin") -> tuple[Path, dict[str, object], tuple[int, int]]:
        if not isinstance(value, dict):
            raise wrapper.LaunchError(label)
        path = Path(str(value["path"]))
        payload = path.read_bytes()
        if len(payload) != value["bytes"] or hashlib.sha256(payload).hexdigest() != value["sha256"]:
            raise wrapper.LaunchError(label)
        info = path.stat()
        return path, dict(value), (int(info.st_dev), int(info.st_ino))

    verify_pin = _pin

    def read_pinned_json(self, value: object, label: str) -> tuple[Path, dict[str, object], tuple[int, int]]:
        path, pin, identity = self._pin(value, label)
        return path, json.loads(path.read_text(encoding="utf-8")), identity

    @staticmethod
    def assert_no_physical_aliases(_records: object) -> None:
        return None

    @staticmethod
    def contains_pending(value: object) -> bool:
        return "PENDING" in repr(value).upper()

    @staticmethod
    def sha256_file(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def configure_parent() -> dict[str, object]:
        return {"cpu_affinity_mask": 1, "cuda_visible_devices": "-1"}

    @staticmethod
    def load_gate_helper() -> object:
        return object()

    def resource_gate(self, _helper: object) -> tuple[dict[str, int], int]:
        item = self.gates.pop(0)
        if isinstance(item, Exception):
            raise item
        return item  # type: ignore[return-value]

    @staticmethod
    def write_json_exclusive(path: Path, value: object) -> bytes:
        payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        path.write_bytes(payload)
        return payload

    @staticmethod
    def verify_closing(_before: object) -> list[object]:
        return []

    def process_times(self, _handle: int) -> dict[str, float | None]:
        return {"creation_epoch": 1.0, "exit_epoch": 2.0, "kernel_seconds": 0.0, "user_seconds": 0.0}

    @staticmethod
    def affinity_mask(_handle: int) -> int:
        return 1


class FakeProcess:
    pid = 81
    _handle = 91

    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.waited = False

    def wait(self) -> int:
        self.waited = True
        return self.exit_code


class AuditWrapperFocusedTests(unittest.TestCase):
    def test_exact_rejects_malformed_plan_sections(self) -> None:
        with self.assertRaises(wrapper.LaunchError):
            wrapper.exact({"schema": "x"}, {"schema", "status"}, "plan")

    def test_canonical_auditor_and_cli_are_fixed_without_journal(self) -> None:
        self.assertEqual(wrapper.PRODUCER_PIN[0], 73030)
        self.assertEqual(wrapper.AUDITOR_PIN[0], 93663)
        plan = {"audit_binding": {"binding": {"path": r"C:\binding.json", "bytes": 1, "sha256": "a" * 64}}}
        child = wrapper.command(plan)
        self.assertEqual(child[:4], [str(wrapper.PYTHON), "-X", "utf8", "-u"])
        self.assertIn("--observer-dir", child)
        self.assertNotIn("--journal", child)

    def test_fixture_receipt_rejects_metadata_drift_and_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            exit_pin = pinned_json(root / "exit.json", {"exit_code": 0, "pid": 7, "creation_epoch": 1.0, "metadata_error": "bad", "changed_pins": [], "retry": True})
            repository = {"launcher": write(root / "launcher.py", b"x"), "launcher_tests": write(root / "tests.py", b"y")}
            receipt_pin = pinned_json(root / "receipt.json", {"schema": wrapper.FIXTURE_SCHEMA, "status": wrapper.FIXTURE_STATUS, "launcher": repository["launcher"], "tests": repository["launcher_tests"], "compile_exit_code": 0, "ruff_exit_code": 0, "pytest_exit_code": 0, "pytest_exit": exit_pin})
            with self.assertRaises(wrapper.LaunchError):
                wrapper.validate_fixture(FakePrimitives(), receipt_pin, exit_pin, repository)

    def test_journal_requires_sequence_pairs_and_publish_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row = {"seq": 0, "utc": "2026-11-02T00:00:00+00:00", "kind": "PUBLISH_ROOT", "identity": "root", "phase": "START", "paths": [], "gate": {}, "details": {}}
            bad = write(root / "journal.jsonl", (json.dumps(row) + "\n").encode("utf-8"))
            with self.assertRaises(wrapper.LaunchError):
                wrapper.read_journal(FakePrimitives(), bad)

    def _complete_closure(self, root: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object], dict[str, object], dict[str, Path]]:
        producer_root, child_root, parent_root = root / "output", root / "child", root / "parent"
        producer_root.mkdir()
        child_root.mkdir()
        parent_root.mkdir()
        outputs = {name: write(producer_root / name, name.encode("utf-8")) for name in wrapper.OUTPUT_NAMES}
        producer = write(root / "producer.py", b"producer")
        bundle, b_review = write(root / "bundle.json", b"bundle"), write(root / "b_review.md", b"review")
        engines = {name: write(root / name, ("engine:" + name).encode("utf-8")) for name in ("level_engine.py", "session_level_engine.py", "session_clock.py", "session_cache.py", "build_cache.py")}
        authorities = {"contract": write(root / "contract.md", b"contract")}
        calendar, cache = write(root / "calendar.json", b"calendar"), write(root / "cache.jsonl", b"cache")
        manifest = {"status": "C_GEOMETRY_1030_CLOSED", "contract": {"contract.md": authorities["contract"]}, "implementation": producer, "authorities": {"b_bundle": bundle, "b_review": b_review}, "authority_pins": {"calendar": calendar, "cache_admission": cache, "engines": engines}, "input_count": 1, "inputs_digest": "a" * 64, "outputs": {"geometry_states_1030.parquet": {**outputs["geometry_states_1030.parquet"], "rows": 2790}, "geometry_levels_1030.parquet": {**outputs["geometry_levels_1030.parquet"], "rows": 4}, "coverage.json": {**outputs["coverage.json"], "rows": None}}, "counts": {"level_rows": 4}, "journal_closure": {"prepublish_last_seq": 1, "prepublish_prefix_sha256": "b" * 64}, "resource_policy": {"minimum_bytes": 2_000_000_000, "cpu_affinity": [0], "threads": 1}, "created_at_utc": "2026-11-02T00:00:00+00:00", "no_events": True, "no_labels": True, "no_weekly_selection": True, "no_economics": True}
        manifest_pin = pinned_json(producer_root / "manifest.json", manifest)
        retained = {"exit_code": 0, "geometry_child_exit_code": 0, "pid": 9, "creation_epoch": 1.0, "changed_pins": [], "metadata_error": None, "retry": False}
        wrapper_exit, wrapper_process = pinned_json(parent_root / "exit.json", retained), pinned_json(parent_root / "process.json", {"pid": 9, "creation_epoch": 1.0})
        mirror_exit, mirror_process = pinned_json(child_root / "exit.json", retained), pinned_json(child_root / "process.json", {"pid": 9, "creation_epoch": 1.0})
        rows = [{"seq": 0, "utc": "2026-11-02T00:00:00+00:00", "kind": "PUBLISH_ROOT", "identity": "root", "phase": "START", "paths": [], "gate": {}, "details": {}}, {"seq": 1, "utc": "2026-11-02T00:00:00+00:00", "kind": "PUBLISH_ROOT", "identity": "root", "phase": "COMPLETE", "paths": [], "gate": {}, "details": {}}]
        journal = write(child_root / "journal.jsonl", ("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n").encode("utf-8"))
        review = write(root / "c_final.md", (wrapper.C_PRODUCER_FINAL_REVIEW_MARKER + "\n" + manifest_pin["sha256"] + "\n" + producer["sha256"] + "\n").encode("utf-8"))
        closure = {"manifest": manifest_pin, "journal": journal, "wrapper_exit": wrapper_exit, "wrapper_process": wrapper_process, "mirror_exit": mirror_exit, "mirror_process": mirror_process, "review": review, "outputs": outputs}
        binding = {"producer_output_root": str(producer_root), "producer_observer_root": str(child_root), "producer_manifest": manifest_pin, "producer_journal": journal, "producer_exit": mirror_exit, "producer_process": mirror_process, "calendar": calendar, "cache_admission": cache, "implementation_pins": engines, "authority_pins": authorities}
        return closure, binding, {"c_producer_final_review": review, "producer": producer}, {"b_final": {"bundle": bundle, "review": b_review}}, {"calendar": calendar, "cache": cache}, {"parent": parent_root}

    def test_producer_closure_rejects_nonidentical_mirrors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            closure, binding, repository, plan, _proofs, paths = self._complete_closure(root)
            closure["mirror_exit"] = pinned_json(root / "child" / "exit-bad.json", {"exit_code": 0, "geometry_child_exit_code": 0, "pid": 8, "creation_epoch": 1.0, "changed_pins": [], "metadata_error": None, "retry": False})
            binding["producer_exit"] = closure["mirror_exit"]
            with mock.patch.object(wrapper, "PRODUCER_LAUNCHER_OBSERVER", paths["parent"]):
                with self.assertRaises(wrapper.LaunchError) as error:
                    wrapper.validate_producer_closure(FakePrimitives(), closure, repository, plan, binding)
            self.assertIn("byte-exact parent mirrors", str(error.exception))

    def test_synthetic_complete_producer_closure_admits_coverage_rows_none(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            closure, binding, repository, plan, _proofs, paths = self._complete_closure(Path(temporary))
            with mock.patch.object(wrapper, "PRODUCER_LAUNCHER_OBSERVER", paths["parent"]):
                wrapper.validate_producer_closure(FakePrimitives(), closure, repository, plan, binding)

    def test_synthetic_binding_admits_and_rejects_b_crosspin_or_canonical_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            producer_root, observer_root, audit_root, audit_observer = root / "producer", root / "observer", root / "audit", root / "audit-observer"
            for path in (producer_root, observer_root, audit_root, audit_observer):
                path.mkdir()
            authority_names = ("contract", "draft", "amendment", "amendment_review", "windows_note", "binding_note")
            authorities = {name: write(root / (name + ".txt"), name.encode("utf-8")) for name in authority_names}
            engine_names = ("level_engine.py", "session_level_engine.py", "session_clock.py", "session_cache.py", "build_cache.py")
            implementations = {name: write(root / name, name.encode("utf-8")) for name in engine_names}
            producer, auditor = write(root / "producer.py", b"producer"), write(root / "auditor.py", b"auditor")
            implementations |= {"resource_helper": write(root / "helper.py", b"helper"), "producer_tests": write(root / "producer_tests.py", b"pt"), "auditor_tests": write(root / "auditor_tests.py", b"at"), "producer": producer, "auditor": auditor}
            calendar, cache = write(root / "calendar.json", b"calendar"), write(root / "cache.jsonl", b"cache")
            b_bundle, b_review = write(root / "bundle.json", b"bundle"), write(root / "review.md", b"review")
            closure_pins = {name: write(observer_root / (name + ".json"), name.encode("utf-8")) for name in ("manifest", "journal", "exit", "process")}
            repository = {"producer": producer, "producer_tests": implementations["producer_tests"], "resource_helper": implementations["resource_helper"], "auditor": auditor, "auditor_tests": implementations["auditor_tests"], "c_admission_contract": authorities["contract"], "c_operational_draft": authorities["draft"], "c_parallel_amendment": authorities["amendment"], "c_parallel_review": authorities["amendment_review"], "c_binding_feasibility": authorities["binding_note"], "c_windows_feasibility": authorities["windows_note"], "level_engine": implementations["level_engine.py"], "session_level_engine": implementations["session_level_engine.py"], "session_clock": implementations["session_clock.py"], "session_cache": implementations["session_cache.py"], "build_cache": implementations["build_cache.py"]}
            bundle = {"calendar": {"raw_file_pin": calendar}, "producer": {"outputs": {"cache_admission.jsonl": cache}}}
            binding = {"schema": "c_geometry_1030_runtime_binding_v1", "status": "BOUND_REAL_C_GEOMETRY_1030", "producer_output_root": str(producer_root), "producer_observer_root": str(observer_root), "producer_manifest": closure_pins["manifest"], "producer_journal": closure_pins["journal"], "producer_exit": closure_pins["exit"], "producer_process": closure_pins["process"], "b_final_bundle": b_bundle, "b_final_review": b_review, "calendar": calendar, "cache_admission": cache, "authority_pins": authorities, "implementation_pins": implementations, "audit_output_root": str(audit_root), "audit_observer_root": str(audit_observer)}
            binding_pin = pinned_json(root / "binding.json", binding)
            plan = {"repository_pins": repository, "b_final": {"bundle": b_bundle, "review": b_review}}
            roots = {"output_dir": str(audit_root), "observer_dir": str(audit_observer), "launcher_observer_dir": "synthetic"}
            with mock.patch.multiple(wrapper, IMMUTABLE_AUTHORITIES=authorities, IMMUTABLE_IMPLEMENTATIONS={key: value for key, value in implementations.items() if key not in {"producer", "auditor"}}, PRODUCER=Path(producer["path"]), PRODUCER_PIN=(producer["bytes"], producer["sha256"]), AUDITOR=Path(auditor["path"]), AUDITOR_PIN=(auditor["bytes"], auditor["sha256"]), PRODUCER_OUTPUT=producer_root, PRODUCER_OBSERVER=observer_root, ROOTS=roots):
                self.assertEqual(wrapper.validate_binding(FakePrimitives(), binding_pin, plan, bundle), binding)
                bad_cache = dict(binding)
                bad_cache["cache_admission"] = write(root / "bad-cache.jsonl", b"bad")
                with self.assertRaises(wrapper.LaunchError):
                    wrapper.validate_binding(FakePrimitives(), pinned_json(root / "bad-cache-binding.json", bad_cache), plan, bundle)
                bad_calendar = dict(binding)
                bad_calendar["calendar"] = write(root / "bad-calendar.json", b"bad")
                with self.assertRaises(wrapper.LaunchError):
                    wrapper.validate_binding(FakePrimitives(), pinned_json(root / "bad-calendar-binding.json", bad_calendar), plan, bundle)
                bad_path = dict(binding)
                bad_path["producer_output_root"] = str(root / "wrong-producer-root")
                with self.assertRaises(wrapper.LaunchError):
                    wrapper.validate_binding(FakePrimitives(), pinned_json(root / "bad-path-binding.json", bad_path), plan, bundle)
                bad_engine = dict(binding)
                bad_engine["implementation_pins"] = dict(implementations)
                bad_engine["implementation_pins"]["level_engine.py"] = write(root / "bad-engine.py", b"bad")
                bad_plan = {"repository_pins": {**repository, "level_engine": bad_engine["implementation_pins"]["level_engine.py"]}, "b_final": plan["b_final"]}
                with self.assertRaises(wrapper.LaunchError):
                    wrapper.validate_binding(FakePrimitives(), pinned_json(root / "bad-engine-binding.json", bad_engine), bad_plan, bundle)

    def test_initial_gate_failure_persists_exit_before_popen(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observer, output, child = root / "observer", root / "output", root / "child"
            fake = FakePrimitives([RuntimeError("gate")])
            plan_path = root / "plan.json"
            plan_path.write_text("{}", encoding="utf-8")
            with mock.patch.multiple(wrapper, OBSERVER=observer, OUTPUT=output, CHILD_OBSERVER=child, PYTHON=Path(sys.executable)), mock.patch.object(wrapper, "bootstrap_parent", return_value={}), mock.patch.object(wrapper, "import_producer_primitives", return_value=fake), mock.patch.object(wrapper, "load_plan", return_value={}), mock.patch.object(wrapper, "verify_publication", return_value="commit"), mock.patch.object(wrapper, "authoritative_pins", return_value={}):
                with mock.patch("subprocess.Popen") as popen:
                    self.assertEqual(wrapper.run(plan_path, "a" * 64), 12)
                    popen.assert_not_called()
            self.assertFalse(observer.exists())
            self.assertFalse(output.exists())
            self.assertFalse(child.exists())

    def test_popen_failure_persists_exit_after_prechild_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observer, output, child = root / "observer", root / "output", root / "child"
            fake = FakePrimitives()
            plan_path = root / "plan.json"
            plan_path.write_text("{}", encoding="utf-8")
            plan = {"audit_binding": {"binding": {"path": "x", "bytes": 1, "sha256": "a" * 64}}}
            with mock.patch.multiple(wrapper, OBSERVER=observer, OUTPUT=output, CHILD_OBSERVER=child, PYTHON=Path(sys.executable)), mock.patch.object(wrapper, "bootstrap_parent", return_value={}), mock.patch.object(wrapper, "import_producer_primitives", return_value=fake), mock.patch.object(wrapper, "load_plan", return_value=plan), mock.patch.object(wrapper, "verify_publication", return_value="commit"), mock.patch.object(wrapper, "authoritative_pins", return_value={}):
                with mock.patch("subprocess.Popen", side_effect=OSError("no child")):
                    self.assertEqual(wrapper.run(plan_path, "a" * 64), 11)
            self.assertEqual(json.loads((observer / "exit.json").read_text(encoding="utf-8"))["stage"], "popen")

    def test_metadata_failure_waits_retained_child_and_is_effective_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observer, output, child = root / "observer", root / "output", root / "child"
            fake, process = FakePrimitives(), FakeProcess(0)
            plan_path = root / "plan.json"
            plan_path.write_text("{}", encoding="utf-8")
            plan = {"audit_binding": {"binding": {"path": "x", "bytes": 1, "sha256": "a" * 64}}}
            with mock.patch.multiple(wrapper, OBSERVER=observer, OUTPUT=output, CHILD_OBSERVER=child, PYTHON=Path(sys.executable)), mock.patch.object(wrapper, "bootstrap_parent", return_value={}), mock.patch.object(wrapper, "import_producer_primitives", return_value=fake), mock.patch.object(wrapper, "load_plan", return_value=plan), mock.patch.object(wrapper, "verify_publication", return_value="commit"), mock.patch.object(wrapper, "authoritative_pins", return_value={}), mock.patch.object(fake, "process_times", side_effect=RuntimeError("metadata")):
                with mock.patch("subprocess.Popen", return_value=process):
                    self.assertEqual(wrapper.run(plan_path, "a" * 64), 3)
            self.assertTrue(process.waited)
            self.assertEqual(json.loads((observer / "exit.json").read_text(encoding="utf-8"))["exit_code"], 3)

    def test_process_record_write_failure_waits_and_persists_final_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observer, output, child = root / "observer", root / "output", root / "child"
            fake, process = FakePrimitives(), FakeProcess(0)
            original_write = fake.write_json_exclusive
            def write_or_fail(path: Path, value: object) -> bytes:
                if path.name == "process.json":
                    raise OSError("synthetic process record failure")
                return original_write(path, value)
            plan_path = root / "plan.json"
            plan_path.write_text("{}", encoding="utf-8")
            plan = {"audit_binding": {"binding": {"path": "x", "bytes": 1, "sha256": "a" * 64}}}
            with mock.patch.multiple(wrapper, OBSERVER=observer, OUTPUT=output, CHILD_OBSERVER=child, PYTHON=Path(sys.executable)), mock.patch.object(wrapper, "bootstrap_parent", return_value={}), mock.patch.object(wrapper, "import_producer_primitives", return_value=fake), mock.patch.object(wrapper, "load_plan", return_value=plan), mock.patch.object(wrapper, "verify_publication", return_value="commit"), mock.patch.object(wrapper, "authoritative_pins", return_value={}), mock.patch.object(fake, "write_json_exclusive", side_effect=write_or_fail):
                with mock.patch("subprocess.Popen", return_value=process):
                    self.assertEqual(wrapper.run(plan_path, "a" * 64), 3)
            self.assertTrue(process.waited)
            exit_record = json.loads((observer / "exit.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_record["cpu_affinity"], 1)
            self.assertIsNotNone(exit_record["process_times"])
            self.assertIn("OSError", exit_record["metadata_error"])


if __name__ == "__main__":
    unittest.main()
