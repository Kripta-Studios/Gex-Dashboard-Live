from __future__ import annotations

import ast
import copy
import json
from datetime import date
from pathlib import Path

import pytest

import audit_weekly_h2_boundary_bridge as audit
import build_weekly_h2_boundary_bridge as producer
import test_build_weekly_h2_boundary_bridge as producer_test


@pytest.fixture
def artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    h1, q3 = tmp_path / "h1", tmp_path / "q3"
    producer_test._write_authority(
        h1, "weekly_h2_coverage_v2", producer_test._weekdays_ending(date(2026, 6, 30), 875), 3054, h1=True
    )
    producer_test._write_authority(
        q3, "weekly_h2_q3_partial_coverage_v1", producer_test._weekdays_starting(date(2026, 7, 1), 55), 180, h1=False
    )
    monkeypatch.setattr(producer, "H1_MANIFEST_SHA256", producer_test._sha(h1 / "manifest.json"))
    monkeypatch.setattr(producer, "Q3_MANIFEST_SHA256", producer_test._sha(q3 / "manifest.json"))
    source = tmp_path / "source"
    source.mkdir()
    for ticker in producer.TICKERS:
        producer_test._greek_file(
            source / "data_options" / ticker / "greeks" / "2026" / "06" / f"{ticker}_20260702_20260629_greeks.parquet",
            ticker, "20260629",
        )
    producer_test._greek_file(
        source / "data_options" / "SPXW" / "greeks" / "2026" / "07" / "SPXW_20260702_20260701_greeks.parquet",
        "SPXW", "20260701", exit_file=True,
    )
    bridge_root = tmp_path / "bridge"
    wrapper_sha = producer_test._sha(Path(producer.__file__))
    producer.build_reviewed_inventory(source, h1, q3, bridge_root, wrapper_sha)
    inventory = bridge_root / "inventory.json"
    producer.execute_reviewed_bridge(source, h1, q3, bridge_root, wrapper_sha, inventory, producer_test._sha(inventory))
    return {
        "root": bridge_root, "output": tmp_path / "audit", "wrapper": Path(producer.__file__),
        "source": source, "h1": h1, "q3": q3,
    }


def _run(paths: dict[str, Path]) -> dict[str, object]:
    root = paths["root"]
    return audit.run_audit(
        root,
        paths["output"],
        producer_test._sha(root / "manifest.json"),
        producer_test._sha(root / "inventory.json"),
        producer_test._sha(paths["wrapper"]),
        producer_test._sha(Path(audit.__file__)),
        expected_source_root=paths["source"], expected_h1_root=paths["h1"], expected_q3_root=paths["q3"],
    )


def test_audit_reproduces_bridge_and_reconciles_3234_ids(artifact: dict[str, Path]) -> None:
    result = _run(artifact)
    assert result["status"] == audit.STATUS
    assert result["counts"] == {
        "unified_calendar_rows": 2790, "overlay_rows": 6, "old_candidate_ids": 3234,
        "new_candidate_ids": 6, "sources_present": 4, "sources_missing": 2,
    }
    assert result["flags"]["fit_performed"] is False
    assert result["flags"]["economic_evaluation_performed"] is False
    saved = json.loads((artifact["output"] / "audit.json").read_text(encoding="utf-8"))
    assert saved == result
    assert set(result["inputs"]["producer_manifest"]) == {"path", "bytes", "sha256"}


def test_auditor_does_not_import_wrapper() -> None:
    tree = ast.parse(Path(audit.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "build_weekly_h2_boundary_bridge" not in imported


def test_external_manifest_binding_fails_before_output(artifact: dict[str, Path]) -> None:
    with pytest.raises(audit.AuditError, match="bridge manifest SHA-256 mismatch"):
        audit.run_audit(
            artifact["root"], artifact["output"], "0" * 64,
            producer_test._sha(artifact["root"] / "inventory.json"),
            producer_test._sha(artifact["wrapper"]), producer_test._sha(Path(audit.__file__)),
            expected_source_root=artifact["source"], expected_h1_root=artifact["h1"], expected_q3_root=artifact["q3"],
        )
    assert not artifact["output"].exists()


def test_overlay_tamper_fails_file_pin(artifact: dict[str, Path]) -> None:
    overlay = artifact["root"] / "coverage_overlay.json"
    overlay.write_bytes(overlay.read_bytes() + b"\n")
    with pytest.raises(audit.AuditError, match="coverage_overlay.json SHA-256 mismatch"):
        _run(artifact)
    assert not artifact["output"].exists()


def test_source_change_fails_before_reproduction(artifact: dict[str, Path]) -> None:
    inventory = json.loads((artifact["root"] / "inventory.json").read_text(encoding="utf-8"))
    source = Path(next(item["path"] for item in inventory["sources"] if item["status"] == "INVENTORIED"))
    source.write_bytes(source.read_bytes() + b"changed")
    with pytest.raises(audit.AuditError, match="source SHA-256 mismatch"):
        _run(artifact)
    assert not artifact["output"].exists()


def test_calendar_mixed_close_values_preserved(artifact: dict[str, Path]) -> None:
    calendar = json.loads((artifact["root"] / "unified_calendar.json").read_text(encoding="utf-8"))
    assert sum(row["close_i"] == 210 for row in calendar["rows"]) == 24
    assert sum(row["close_i"] == 390 for row in calendar["rows"]) == 2766


def test_occupied_audit_destination_fails(artifact: dict[str, Path]) -> None:
    artifact["output"].mkdir()
    with pytest.raises(audit.AuditError, match="immutable audit output exists"):
        _run(artifact)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("exit_date", "20260702", "June 29 bridge plan semantics"),
        ("expiration", "20260703", "June 29 bridge plan semantics"),
        ("status", "NO_SERIES", "June 29 bridge plan semantics"),
    ],
)
def test_plan_semantics_mutations_fail(artifact: dict[str, Path], field: str, value: object, message: str) -> None:
    inventory = json.loads((artifact["root"] / "inventory.json").read_text(encoding="utf-8"))
    changed = copy.deepcopy(inventory)
    next(row for row in changed["coverage_plan"] if row["entry_date"] == "20260629")[field] = value
    with pytest.raises(audit.AuditError, match=message):
        audit._validate_plan_and_sources(changed, artifact["source"])


def test_source_scope_and_missing_identity_mutations_fail(artifact: dict[str, Path]) -> None:
    inventory = json.loads((artifact["root"] / "inventory.json").read_text(encoding="utf-8"))
    changed = copy.deepcopy(inventory)
    changed["sources"][0]["path"] += ".extra"
    with pytest.raises(audit.AuditError, match="six nominal source paths"):
        audit._validate_plan_and_sources(changed, artifact["source"])
    changed = copy.deepcopy(inventory)
    spy_exit = next(row for row in changed["sources"] if Path(row["path"]).name.startswith("SPY_20260702_20260701"))
    spy_exit["status"] = "INVENTORIED"
    with pytest.raises(audit.AuditError, match="missing source identities"):
        audit._validate_plan_and_sources(changed, artifact["source"])
    with pytest.raises(audit.AuditError, match="source root differs"):
        audit._validate_plan_and_sources(inventory, artifact["source"].parent / "other")


def test_authority_pin_keys_and_roots_are_exact(artifact: dict[str, Path]) -> None:
    inventory = json.loads((artifact["root"] / "inventory.json").read_text(encoding="utf-8"))
    audit._validate_authority_pins(inventory, artifact["h1"], artifact["q3"])
    changed = copy.deepcopy(inventory)
    changed["authority_pins"]["extra"] = changed["authority_pins"]["h1_manifest"]
    with pytest.raises(audit.AuditError, match="key set"):
        audit._validate_authority_pins(changed, artifact["h1"], artifact["q3"])
    with pytest.raises(audit.AuditError, match="path mismatch"):
        audit._validate_authority_pins(inventory, artifact["h1"].parent / "other", artifact["q3"])
    changed = copy.deepcopy(inventory)
    changed["authority_pins"]["h1_manifest"]["bytes"] += 1
    with pytest.raises(audit.AuditError, match="byte count mismatch"):
        audit._validate_authority_pins(changed, artifact["h1"], artifact["q3"])


def test_implementation_pin_paths_shapes_and_files_are_exact(
    artifact: dict[str, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = json.loads((artifact["root"] / "manifest.json").read_text(encoding="utf-8"))
    pins = manifest["implementation_pins"]
    audit._validate_implementation_pins(pins, producer_test._sha(artifact["wrapper"]))
    changed = copy.deepcopy(pins)
    changed["h2_contract"]["path"] += ".other"
    with pytest.raises(audit.AuditError, match="implementation pin mismatch: h2_contract"):
        audit._validate_implementation_pins(changed, producer_test._sha(artifact["wrapper"]))
    changed = copy.deepcopy(pins)
    changed["clock_amendment"]["extra"] = True
    with pytest.raises(audit.AuditError, match="implementation pin shape mismatch: clock_amendment"):
        audit._validate_implementation_pins(changed, producer_test._sha(artifact["wrapper"]))
    h2_copy = tmp_path / "ECONOMIC_H2_CONTRACT.md"
    h2_copy.write_bytes(audit.H2_CONTRACT_PATH.read_bytes())
    monkeypatch.setattr(audit, "H2_CONTRACT_PATH", h2_copy)
    h2_copy.write_bytes(h2_copy.read_bytes() + b"changed")
    with pytest.raises(audit.AuditError, match="implementation h2_contract SHA-256 mismatch"):
        audit._validate_implementation_pins({**pins, "h2_contract": {"path": str(h2_copy), "sha256": audit.H2_CONTRACT_SHA256}}, producer_test._sha(artifact["wrapper"]))


def test_calendar_binding_manifest_closure_and_old_digest_focals(artifact: dict[str, Path]) -> None:
    root = artifact["root"]
    inventory = json.loads((root / "inventory.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    overlay = json.loads((root / "coverage_overlay.json").read_text(encoding="utf-8"))
    with pytest.raises(audit.AuditError, match="calendar binding"):
        audit._validate_overlay_binding(overlay, "0" * 64)
    changed = copy.deepcopy(manifest)
    changed["flags"]["development_seen"] = False
    with pytest.raises(audit.AuditError, match="manifest flags"):
        audit._validate_manifest_closure(changed, inventory, manifest["new_candidate_id_count"])
    with pytest.raises(audit.AuditError, match="old candidate ID digest"):
        audit._validate_old_ids_digest({**inventory, "old_candidate_ids_sha256": "0" * 64}, {"a", "b"})
