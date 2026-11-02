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

    def test_producer_closure_rejects_nonidentical_mirrors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = {name: write(root / name, name.encode("utf-8")) for name in wrapper.OUTPUT_NAMES}
            exit_value = {"exit_code": 0, "geometry_child_exit_code": 0}
            closure = {"manifest": pinned_json(root / "manifest.json", {"status": "C_GEOMETRY_1030_CLOSED"}), "journal": write(root / "journal.jsonl", b""), "wrapper_exit": pinned_json(root / "exit.json", exit_value), "wrapper_process": pinned_json(root / "process.json", {}), "mirror_exit": pinned_json(root / "mirror_exit.json", {"exit_code": 1}), "mirror_process": pinned_json(root / "mirror_process.json", {}), "review": write(root / "review.md", b"review"), "outputs": outputs}
            repository = {"c_producer_final_review": closure["review"], "producer": write(root / "producer.py", b"p")}
            plan = {"b_final": {"bundle": write(root / "bundle", b"b"), "review": write(root / "breview", b"r")}}
            binding = {"calendar": write(root / "calendar", b"c"), "cache_admission": write(root / "cache", b"d"), "implementation_pins": {name: write(root / name, b"e") for name in ("level_engine.py", "session_level_engine.py", "session_clock.py", "session_cache.py", "build_cache.py")}}
            with self.assertRaises(wrapper.LaunchError):
                wrapper.validate_producer_closure(FakePrimitives(), closure, repository, plan, binding)

    def test_synthetic_complete_producer_closure_admits_coverage_rows_none(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = {name: write(root / name, name.encode("utf-8")) for name in wrapper.OUTPUT_NAMES}
            producer = write(root / "producer.py", b"producer")
            bundle, b_review = write(root / "bundle.json", b"bundle"), write(root / "b_review.md", b"review")
            engines = {name: write(root / name, ("engine:" + name).encode("utf-8")) for name in ("level_engine.py", "session_level_engine.py", "session_clock.py", "session_cache.py", "build_cache.py")}
            calendar, cache = write(root / "calendar.json", b"calendar"), write(root / "cache.jsonl", b"cache")
            binding = {"calendar": calendar, "cache_admission": cache, "implementation_pins": engines}
            manifest = {"status": "C_GEOMETRY_1030_CLOSED", "contract": {}, "implementation": producer, "authorities": {"b_bundle": bundle, "b_review": b_review}, "authority_pins": {"calendar": calendar, "cache_admission": cache, "engines": engines}, "input_count": 1, "inputs_digest": "a" * 64, "outputs": {"geometry_states_1030.parquet": {**outputs["geometry_states_1030.parquet"], "rows": 2790}, "geometry_levels_1030.parquet": {**outputs["geometry_levels_1030.parquet"], "rows": 4}, "coverage.json": {**outputs["coverage.json"], "rows": None}}, "counts": {"level_rows": 4}, "journal_closure": {"prepublish_last_seq": 1, "prepublish_prefix_sha256": "b" * 64}, "resource_policy": {"minimum_bytes": 2_000_000_000, "cpu_affinity": [0], "threads": 1}, "created_at_utc": "2026-11-02T00:00:00+00:00", "no_events": True, "no_labels": True, "no_weekly_selection": True, "no_economics": True}
            manifest_pin = pinned_json(root / "manifest.json", manifest)
            retained = {"exit_code": 0, "geometry_child_exit_code": 0, "pid": 9, "creation_epoch": 1.0, "changed_pins": [], "metadata_error": None, "retry": False}
            exit_pin, process_pin = pinned_json(root / "exit.json", retained), pinned_json(root / "process.json", {"pid": 9, "creation_epoch": 1.0})
            journal_rows = [{"seq": 0, "utc": "2026-11-02T00:00:00+00:00", "kind": "PUBLISH_ROOT", "identity": "root", "phase": "START", "paths": [], "gate": {}, "details": {}}, {"seq": 1, "utc": "2026-11-02T00:00:00+00:00", "kind": "PUBLISH_ROOT", "identity": "root", "phase": "COMPLETE", "paths": [], "gate": {}, "details": {}}]
            journal = write(root / "journal.jsonl", ("\n".join(json.dumps(row, sort_keys=True) for row in journal_rows) + "\n").encode("utf-8"))
            review = write(root / "c_final.md", (wrapper.C_PRODUCER_FINAL_REVIEW_MARKER + "\n" + manifest_pin["sha256"] + "\n" + producer["sha256"] + "\n").encode("utf-8"))
            closure = {"manifest": manifest_pin, "journal": journal, "wrapper_exit": exit_pin, "wrapper_process": process_pin, "mirror_exit": exit_pin, "mirror_process": process_pin, "review": review, "outputs": outputs}
            repository = {"c_producer_final_review": review, "producer": producer}
            plan = {"b_final": {"bundle": bundle, "review": b_review}}
            wrapper.validate_producer_closure(FakePrimitives(), closure, repository, plan, binding)

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


if __name__ == "__main__":
    unittest.main()
