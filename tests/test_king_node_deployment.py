from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from scripts.check_king_node_health import inspect_snapshot
from tests.test_king_node_web import web_snapshot_fixture


ROOT = Path(__file__).resolve().parents[1]


def healthy_fixture() -> dict:
    fixture = web_snapshot_fixture()
    fixture["status"] = "ok"
    fixture["generated_at"] = datetime.now(UTC).isoformat()
    fixture["source"]["tastytrade"]["age_seconds"] = 5
    return fixture


def test_health_contract_accepts_live_sources_and_semantic_warning() -> None:
    report = inspect_snapshot(healthy_fixture(), max_age_seconds=900)

    assert report["healthy"] is True
    assert report["strike_count"] == 47
    assert report["reference_mode"] == "semantic_fallback"
    assert any("semantic fallback" in item for item in report["warnings"])


def test_health_contract_fails_missing_index_or_strict_reference() -> None:
    fixture = healthy_fixture()
    fixture["source"]["indices"]["vvix"]["status"] = "unavailable"

    report = inspect_snapshot(
        fixture,
        max_age_seconds=900,
        require_reference_export=True,
    )

    assert report["healthy"] is False
    assert any("VVIX" in item for item in report["errors"])
    assert any("workbook export" in item for item in report["errors"])


def test_health_cli_reports_json_and_exit_code(tmp_path: Path) -> None:
    snapshot = tmp_path / "latest.json"
    snapshot.write_text(json.dumps(healthy_fixture()), encoding="utf-8")
    environment = os.environ.copy()
    environment["KING_NODE_SNAPSHOT"] = str(snapshot)

    result = subprocess.run(
        ["python", "scripts/check_king_node_health.py", "--json"],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["healthy"] is True


def test_systemd_and_deploy_assets_share_snapshot_contract() -> None:
    unit = (ROOT / "systemd" / "king-node.service").read_text(encoding="utf-8")
    server_unit = (ROOT / "systemd" / "financial-server.service").read_text(
        encoding="utf-8"
    )
    environment = (ROOT / ".env.king-node.example").read_text(encoding="utf-8")
    deploy = (ROOT / "scripts" / "deploy_king_node_vps.sh").read_text(
        encoding="utf-8"
    )

    expected = "/var/lib/king-node/latest.json"
    assert f"KING_NODE_OUTPUT={expected}" in unit
    assert f"KING_NODE_SNAPSHOT={expected}" in unit
    assert f"KING_NODE_SNAPSHOT={expected}" in server_unit
    assert f"KING_NODE_OUTPUT={expected}" in environment
    assert f"KING_NODE_SNAPSHOT={expected}" in environment
    assert "EnvironmentFile=-/etc/kripta/king-node.env" in unit
    assert "EnvironmentFile=-/etc/kripta/king-node.env" in server_unit
    assert "systemctl restart king-node.service" in deploy
    assert "systemctl restart financial-server.service" in deploy
    assert (
        "check_king_node_health.py --snapshot "
        "/var/lib/king-node/latest.json"
    ) in deploy
