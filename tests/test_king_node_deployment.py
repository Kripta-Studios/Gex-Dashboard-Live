from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess

from scripts.check_king_node_health import inspect_snapshot
from tests.test_king_node_web import web_snapshot_fixture

ROOT = Path(__file__).resolve().parents[1]


def _term() -> dict:
    return {
        "forward": 6000.0,
        "k0": 6000.0,
        "variance": 0.04,
        "minutes": 400.0,
        "included_strikes": [5980.0, 5990.0, 6000.0, 6010.0, 6020.0],
    }


def healthy_fixture() -> dict:
    fixture = web_snapshot_fixture()
    fixture["status"] = "ok"
    fixture["generated_at"] = datetime.now(UTC).isoformat()
    fixture["source"]["tastytrade"]["age_seconds"] = 5
    common = {
        "age_seconds": 1,
        "entitlement": "options_standard",
        "direct_index_subscription": False,
        "quote_count": 20,
        "valid_strike_count": 16,
        "rate": {"value_decimal": 0.0433, "status": "observed"},
    }
    fixture["source"]["indices"] = {
        "vix": {
            **common,
            "value": 18.0,
            "status": "observed_from_option_feed",
            "method": "thetadata_option_first_order_underlying_median",
            "input_symbol": "VIX",
            "expirations": ["2026-08-19"],
        },
        "vix1d": {
            **common,
            "value": 15.0,
            "status": "reconstructed",
            "method": "cboe_vix1d_reconstruction_from_spxw_nbbo",
            "input_symbol": "SPXW",
            "expirations": ["2026-07-27", "2026-07-28"],
            "diagnostics": {"near": _term(), "next": _term()},
        },
        "vvix": {
            **common,
            "value": 95.0,
            "status": "reconstructed",
            "method": "cboe_vvix_reconstruction_from_vix_nbbo",
            "input_symbol": "VIX",
            "expirations": ["2026-08-19", "2026-09-16"],
            "diagnostics": {"near": _term(), "next": _term()},
        },
    }
    fixture["source"]["theta_options"] = {
        "entitlement": "options_standard",
        "direct_index_subscription": False,
    }
    return fixture


def test_health_contract_accepts_options_standard_reconstructions() -> None:
    report = inspect_snapshot(healthy_fixture(), max_age_seconds=900)
    assert report["healthy"] is True
    assert report["strike_count"] == 47
    assert any("semantic fallback" in item for item in report["warnings"])


def test_health_contract_fails_missing_reconstruction_or_strict_reference() -> None:
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
    assert "KING_NODE_THETA_OPTION_MAX_AGE_SECONDS=180" in environment
    assert "KING_NODE_RATE_SYMBOL=SOFR" in environment
    assert "volatility_indices.py" in deploy
    assert "check_thetadata_options_standard.py" in deploy
    assert "systemctl restart king-node.service" in deploy
    assert "systemctl restart financial-server.service" in deploy
