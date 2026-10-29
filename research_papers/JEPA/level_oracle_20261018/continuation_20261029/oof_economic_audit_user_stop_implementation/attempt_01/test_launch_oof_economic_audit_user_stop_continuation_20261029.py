"""Artificial two-process provenance; never execute the scientific auditor."""

import importlib.util
from pathlib import Path


def test_operational_adapter_exists_separately_from_frozen_supervisor():
    name = "launch_oof_economic_audit_user_stop_continuation_20261029"
    spec = importlib.util.find_spec(name)
    assert spec is not None, "A separate continuation audit supervisor is required"
    assert Path(spec.origin).name == name + ".py"
