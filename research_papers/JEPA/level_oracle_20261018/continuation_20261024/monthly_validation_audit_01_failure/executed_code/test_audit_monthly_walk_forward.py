"""Synthetic-only checks for the independent monthly sealed-score auditor."""

import ast
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import audit_monthly_walk_forward as audit


def test_auditor_does_not_import_monthly_producer_or_model_stack():
    tree = ast.parse(Path(audit.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "run_monthly_walk_forward" not in imported
    assert "rolling_monthly_schedule" not in imported
    assert "monthly_policy_selection" not in imported
    assert "lightgbm" not in imported


def test_windows_are_causal_and_static_shares_january_expanding():
    january = date(2025, 1, 1)
    static = audit.window("static", january)
    expanding = audit.window("expanding", january)
    rolling = audit.window("rolling12", january)
    assert static == expanding
    assert static[:2] == (date(2023, 1, 1), january)
    assert rolling[:2] == (date(2024, 1, 1), january)
    february = date(2025, 2, 1)
    assert audit.window("expanding", february)[:2] == (date(2023, 1, 1), february)
    assert audit.window("rolling12", february)[:2] == (date(2024, 2, 1), february)


def test_independent_sampling_exact_cap_identity_and_ipw():
    actions = pd.DataFrame(
        {"action_id": np.arange(40, dtype=np.int64), "state_i": np.full(40, 60, dtype=np.int64)}
    )
    sample = audit.independent_sample("SPY", "20240102", actions)
    assert len(sample["action_id"]) == 32
    np.testing.assert_array_equal(sample["population_by_band"], [40, 0, 0, 0])
    np.testing.assert_array_equal(sample["selected_by_band"], [32, 0, 0, 0])
    np.testing.assert_array_equal(sample["band_i"], np.zeros(32, dtype=np.int64))
    np.testing.assert_array_equal(sample["weight"], np.full(32, 1 / 32))
    expected = [
        audit.canonical_identity("SPY", "20240102", 60, action)
        for action in sample["action_id"]
    ]
    assert sample["identity_sha256"].tolist() == expected


def frames():
    actions = pd.DataFrame(
        {"action_id": [0, 1, 2, 3], "state_i": [60, 60, 61, 64]}
    )
    labels = pd.DataFrame(
        {
            "action_id": [0, 1, 2, 3],
            "status": ["FILLED", "NO_FILL", "FILLED", "FILLED"],
            "exit_i": [62, 61, 63, 66],
            "entry_ask": [1.0, np.nan, 1.0, 1.0],
            "net_base": [100.0, 0.0, -2.0, 3.0],
            "net_adverse": [98.0, 0.0, -4.0, 1.0],
            "hold_minutes": [1, 0, 1, 1],
            "reason": ["TARGET", "NO_FILL", "STOP", "TARGET"],
        }
    )
    return actions, labels


def test_scheduler_reconstructs_no_fill_and_physical_blocking():
    actions, labels = frames()
    attempts, ledger = audit.schedule(390, actions, labels, np.array([1.0, 2.0, 3.0, 4.0]))
    assert attempts.action_id.tolist() == [1, 2, 3]
    assert attempts.has_filled_before.tolist() == [0, 0, 1]
    assert ledger.action_id.tolist() == [2, 3]
    assert ledger.net_base.sum() == 1
    labels.loc[3, "exit_i"] = 386
    with pytest.raises(ValueError, match="outside session"):
        audit.schedule(390, actions, labels, np.ones(4))


def test_economics_exact_path_statistics():
    ledger = pd.DataFrame(
        {
            "net_base": [2.0, -1.0, 3.0],
            "net_adverse": [1.0, -2.0, 2.0],
            "hold_minutes": [2, 4, 6],
            "reason": ["TARGET", "STOP", "EOD"],
        }
    )
    result = audit.economic_summary(ledger)
    assert result["trades"] == 3
    assert result["net_base"] == 4
    assert result["net_base_pf"] == 5
    assert result["net_base_max_drawdown"] == 1
    assert result["holding_minutes"] == {"min": 2.0, "median": 4.0, "max": 6.0}
    assert result["exit_reasons"]["STOP"]["net_adverse"] == -2


def test_checkpoint_binding_members_and_mutation_detection(tmp_path):
    root = tmp_path / "monthly"
    root.mkdir()
    payload = root / "x.npz"
    payload.write_bytes(b"sealed")
    marker = root / "x.complete.json"
    marker.write_text(
        json.dumps(
            {
                "status": "COMPLETE",
                "binding": "contract",
                "files": {"x.npz": audit.sha(payload)},
                "extra": {},
                "completed_utc": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    verifier = audit.Verifier()
    evidence = audit.Evidence(root, verifier, "contract")
    evidence.member("x", payload)
    payload.write_bytes(b"changed")
    # Repeated references use the per-run digest ledger; the terminal recheck
    # prevents a successful audit if a byte changes after first verification.
    evidence.member("x", payload)
    with pytest.raises(ValueError, match="changed during audit"):
        verifier.recheck()


def test_declared_status_and_limits_are_explicit():
    assert audit.STATUS == "PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES"
    source = Path(audit.__file__).read_text(encoding="utf-8")
    assert "Models were not refit and score inference was not repeated" in source


def test_executed_code_dependency_universe_and_bytes(tmp_path):
    root = tmp_path / "monthly"
    code = root / "executed_code"
    code.mkdir(parents=True)
    dependencies = {}
    for name in audit.DEPENDENCIES:
        path = code / name
        path.write_text("snapshot " + name, encoding="utf-8")
        dependencies[name] = audit.sha(path)
    verifier = audit.Verifier()
    audit.verify_executed_code(root, dependencies, verifier)
    (code / audit.DEPENDENCIES[0]).write_text("mutated", encoding="utf-8")
    with pytest.raises(ValueError, match="changed during audit"):
        verifier.recheck()
    missing = dict(dependencies)
    missing.pop(audit.DEPENDENCIES[-1])
    with pytest.raises(ValueError, match="universe"):
        audit.verify_executed_code(root, missing, audit.Verifier())


def test_source_read_terminal_rehash_rejects_late_mutation(tmp_path):
    source = tmp_path / "actions.parquet"
    source.write_bytes(b"sealed-sidecar")
    reads = {str(source.resolve()): audit.sha(source)}
    audit.recheck_hashes(reads, "source")
    source.write_bytes(b"late mutation")
    with pytest.raises(ValueError, match="source"):
        audit.recheck_hashes(reads, "source")


def test_implementation_review_is_an_exact_byte_gate(tmp_path):
    review = tmp_path / "review.json"
    payload = {
        "status": audit.REVIEW_STATUS,
        "auditor_sha256": audit.sha(audit.__file__),
        "tests_sha256": audit.sha(__file__),
        "contract_sha256": audit.sha(
            Path(audit.__file__).with_name(
                "MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDIT_CONTRACT.md"
            )
        ),
    }
    review.write_text(json.dumps(payload), encoding="utf-8")
    audit.verify_implementation_review(review, audit.Verifier())
    payload["auditor_sha256"] = "0" * 64
    review.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="auditor bytes"):
        audit.verify_implementation_review(review, audit.Verifier())

