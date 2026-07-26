from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
KING_NODE_JS = ROOT / "web" / "templates" / "js" / "king_node.js"


def test_king_node_admin_tab_uses_precomputed_admin_api() -> None:
    assert KING_NODE_JS.is_file()
    javascript = KING_NODE_JS.read_text(encoding="utf-8")
    auth = (ROOT / "web" / "templates" / "js" / "auth.js").read_text(
        encoding="utf-8"
    )
    tabs = (ROOT / "web" / "templates" / "js" / "tabs.js").read_text(
        encoding="utf-8"
    )
    dashboard = (
        ROOT / "web" / "templates" / "js" / "dashboard.js"
    ).read_text(encoding="utf-8")
    refresh = (ROOT / "web" / "templates" / "js" / "refresh.js").read_text(
        encoding="utf-8"
    )
    server = (ROOT / "services" / "servidor.py").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "templates" / "styles.css").read_text(
        encoding="utf-8"
    )

    assert '"js/king_node.js"' in auth
    assert "/api/king-node" in javascript
    assert "/get_latest?ticker=SPX&exp=0dte" not in javascript
    assert "call_gamma" not in javascript
    assert "call_open_int" not in javascript
    assert "mountKingNodeTab" in tabs
    assert "renderKingNodeDashboard" in dashboard
    assert "refreshKingNodeDashboard" in refresh
    assert '"js/king_node.js",' in server
    assert 'path_only == "/api/king-node"' in server
    assert 'auth_info.get("role") != "ADMIN"' in server
    assert '"Cache-Control", "no-store"' in server
    assert "@import url('./css/king_node.css');" in styles


def web_snapshot_fixture() -> dict:
    rows = []
    for index in range(47):
        strike = 5800 + index * 10
        value = (index - 23) * 1_000_000
        rows.append(
            {
                "strike": strike,
                "raw_gamma": abs(value) / 1_000_000 + 1,
                "gamma_gross": abs(value),
                "gex": value,
                "zomma": value * 0.2,
                "dex": value * 2,
                "vex": -value,
                "vomma": value * 0.5,
                "vega": abs(value) * 0.25,
                "speed": value * 0.1,
            }
        )
    return {
        "schema_version": "king-node.v1",
        "status": "degraded",
        "generated_at": "2026-07-26T14:00:00Z",
        "delivery": {
            "age_seconds": 10,
            "max_age_seconds": 900,
            "stale": False,
        },
        "quality": {
            "grade": "DEGRADED",
            "warnings": ["<script>alert('no')</script>"],
            "errors": [],
            "strike_count": 47,
            "expected_strike_count": 47,
            "raw_gamma_coverage": 1,
            "profile_coverage": 1,
            "smooth_depth": 3,
        },
        "source": {
            "tastytrade": {
                "filename": "fixture.json",
                "age_seconds": 10,
                "provider": "Tastytrade",
            },
            "indices": {
                "vix": {
                    "value": 18,
                    "status": "observed",
                    "age_seconds": 1,
                },
                "vvix": {
                    "value": 95,
                    "status": "observed",
                    "age_seconds": 1,
                },
                "vix1d": {
                    "value": 15,
                    "status": "observed",
                    "age_seconds": 1,
                },
            },
        },
        "inputs": {
            "spot": 6030,
            "previous_close": 6020,
            "spot_change_pct": 0.16,
            "dte_hours": 4,
            "atm_iv": 0.18,
        },
        "directions": {
            "vix": "Down",
            "vvix": "Flat",
            "vix1d": "Up",
            "atm_iv": "Flat",
        },
        "regime": {
            "regime": "High IV · positive-gamma mean reversion",
            "dealer_action": "Sell strength and buy weakness",
            "tactical": "FADE EXTREMES",
            "dealer_is": "Long gamma",
            "phenomenon": "Gamma pin",
            "tilt": "aligned",
            "iv_raw": "HIGH",
            "iv_box": "High",
            "iv_intensity": 1.2,
            "dte_boost": 1.2,
            "matrix_key": "High|Pos|Pos|Pos|Pos|Pos|Pos|Pos",
            "box_key": "Positive|Down|Flat|Up",
            "reference_mode": "semantic_fallback",
            "signs": {
                "gamma": "Pos",
                "dex": "Pos",
                "vex": "Pos",
                "zomma": "Pos",
                "vomma": "Pos",
                "vega": "Pos",
                "speed": "Pos",
                "charm": "Pos",
            },
        },
        "totals": {
            "raw_gamma": 123.456,
            "gamma_gross": 10_000_000,
            "gex": 5_000_000,
            "dex": 3_000_000,
            "vex": 2_000_000,
            "zomma": 1_000_000,
            "vomma": 900_000,
            "vega": 800_000,
            "speed": 700_000,
            "charm": 600_000,
        },
        "levels": {
            "raw_gamma": {"strike": 6030, "value": 55},
            "king_gamma": {"strike": 6040, "value": 20_000_000},
            "max_gex": {"strike": 6050, "value": 15_000_000},
            "min_gex": {"strike": 6000, "value": -12_000_000},
            "gamma_flip": 6020,
            "zero_gamma": {
                "strike": 6010,
                "interpolated_strike": 6012.5,
            },
            "daemon_zero_gamma": 6013,
            "call_walls": [],
            "put_walls": [],
            "resistances": [],
            "supports": [],
        },
        "monitor": {
            "gex": {
                "sign": "POS",
                "per_15_minutes": 1_000_000,
                "flip_age_minutes": None,
            },
            "skew": {},
            "vomma": {"status": "warming up"},
            "vol_tension": {
                "label": "SLOW POS GAMMA",
                "expectation": "Levels hold",
                "ratio": 0.83,
            },
            "vix1d_extremes": {},
        },
        "rows": rows,
    }


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_renderer_accepts_backend_contract_and_escapes_source_warnings() -> None:
    node_program = """
const fs = require("fs");
const vm = require("vm");
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
const fixture = JSON.parse(process.argv[2]);
const model = globalThis.KingNodeWeb.normaliseSnapshot(fixture);
const html = globalThis.KingNodeWeb.renderModel(model);
process.stdout.write(JSON.stringify({
  schema: globalThis.KingNodeWeb.SCHEMA_VERSION,
  rowCount: model.rows.length,
  hasApiModel: html.includes("PORTABLE V5 ENGINE"),
  hasRawLevel: html.includes("RAW GAMMA LEVEL"),
  hasRawFormula: html.includes("(Γcall × OIcall) + (Γput × OIput)"),
  hasEscapedWarning: html.includes("&lt;script&gt;alert(&#039;no&#039;)&lt;/script&gt;"),
  hasUnsafeWarning: html.includes("<script>alert('no')</script>"),
  formatted: globalThis.KingNodeWeb.formatExposure(12500000)
}));
"""
    result = subprocess.run(
        [
            "node",
            "-e",
            node_program,
            str(KING_NODE_JS),
            json.dumps(web_snapshot_fixture()),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    parsed = json.loads(result.stdout)

    assert parsed == {
        "schema": "king-node.v1",
        "rowCount": 47,
        "hasApiModel": True,
        "hasRawLevel": True,
        "hasRawFormula": True,
        "hasEscapedWarning": True,
        "hasUnsafeWarning": False,
        "formatted": "+12.50M",
    }


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_renderer_rejects_error_or_empty_snapshot() -> None:
    node_program = """
const fs = require("fs");
const vm = require("vm");
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
let message = "";
try {
  globalThis.KingNodeWeb.normaliseSnapshot({
    schema_version: "king-node.v1",
    status: "error",
    quality: {errors: ["source unavailable"]},
    rows: []
  });
} catch (error) {
  message = error.message;
}
process.stdout.write(message);
"""
    result = subprocess.run(
        ["node", "-e", node_program, str(KING_NODE_JS)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "source unavailable"
