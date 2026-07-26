from __future__ import annotations

import importlib.util
import json
import sys
import types
import uuid
from pathlib import Path

import pytest

from tests.test_king_node_deployment import healthy_fixture


ROOT = Path(__file__).resolve().parents[1]


def load_server_module(
    monkeypatch: pytest.MonkeyPatch,
    snapshot: Path,
):
    qiskit = types.ModuleType("qiskit")
    qiskit.QuantumCircuit = object
    qiskit_aer = types.ModuleType("qiskit_aer")
    qiskit_aer.AerSimulator = lambda: object()
    monkeypatch.setitem(sys.modules, "qiskit", qiskit)
    monkeypatch.setitem(sys.modules, "qiskit_aer", qiskit_aer)
    monkeypatch.setenv("KING_NODE_SNAPSHOT", str(snapshot))
    monkeypatch.setenv("KING_NODE_WEB_MAX_AGE_SECONDS", "900")

    module_name = f"king_node_server_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        ROOT / "services" / "servidor.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_server_reads_schema_and_adds_delivery_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "latest.json"
    payload = healthy_fixture()
    snapshot.write_text(json.dumps(payload), encoding="utf-8")
    server = load_server_module(monkeypatch, snapshot)
    handler = server.ExposureDataHandler.__new__(server.ExposureDataHandler)

    response = handler._read_king_node_snapshot()

    assert response["schema_version"] == "king-node.v1"
    assert response["rows"] == payload["rows"]
    assert response["delivery"]["snapshot_path"] == "latest.json"
    assert response["delivery"]["stale"] is False
    assert 0 <= response["delivery"]["age_seconds"] < 30


def test_server_rejects_unsupported_snapshot_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "latest.json"
    snapshot.write_text(
        json.dumps({"schema_version": "king-node.v0"}),
        encoding="utf-8",
    )
    server = load_server_module(monkeypatch, snapshot)
    handler = server.ExposureDataHandler.__new__(server.ExposureDataHandler)

    with pytest.raises(ValueError, match="Unsupported KING NODE"):
        handler._read_king_node_snapshot()
