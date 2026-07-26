from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
KING_NODE_JS = ROOT / "web" / "templates" / "js" / "king_node.js"


def test_king_node_admin_tab_is_wired_into_dashboard() -> None:
    assert KING_NODE_JS.is_file()

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
    daemon = (ROOT / "services" / "gex_daemon.py").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "templates" / "styles.css").read_text(
        encoding="utf-8"
    )

    assert '"js/king_node.js"' in auth
    assert "/get_latest?ticker=SPX&exp=0dte" in KING_NODE_JS.read_text(
        encoding="utf-8"
    )
    assert "mountKingNodeTab" in tabs
    assert "renderKingNodeDashboard" in dashboard
    assert "refreshKingNodeDashboard" in refresh
    assert '"js/king_node.js",' in server
    assert "@import url('./css/king_node.css');" in styles
    for field in (
        "total_delta",
        "total_gamma",
        "total_vanna",
        "total_zomma",
        "total_vega",
        "total_vomma",
        "total_speed",
    ):
        assert f'option_data["{field}"]' in daemon
    assert 'obj.to_dict(orient="split")' in daemon


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_king_node_model_aggregates_tastytrade_split_surface() -> None:
    columns = [
        "strike_price",
        "call_iv",
        "put_iv",
        "call_gex",
        "put_gex",
        "total_gamma",
        "total_delta",
        "total_vanna",
        "total_zomma",
        "total_vomma",
        "total_vega",
        "total_speed",
        "total_charm",
        "total_dgex",
    ]
    rows = []
    for index in range(55):
        strike = 5800 + index * 10
        gamma = (index - 27) / 100
        rows.append(
            [
                strike,
                0.18 + index / 10000,
                0.2 + index / 10000,
                abs(gamma) * 1e9,
                -abs(gamma) * 0.4e9,
                gamma,
                gamma * 2,
                gamma * -0.5,
                gamma * 0.25,
                gamma * -0.1,
                gamma * 0.75,
                gamma * 0.05,
                gamma * 0.15,
                gamma * 0.8,
            ]
        )

    fixture = {
        "spot_price": 6070,
        "prev_close_price": 6050,
        "zerogamma": 6035,
        "today_ddt_string": "fixture",
        "option_data": {"columns": columns, "data": rows},
    }
    node_program = """
const fs = require("fs");
const vm = require("vm");
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
const fixture = JSON.parse(process.argv[2]);
const model = globalThis.KingNodeWeb.buildKingNodeModel(fixture, 16.25);
process.stdout.write(JSON.stringify({
  windowSize: model.rows.length,
  firstStrike: model.rows[0].strike,
  lastStrike: model.rows[model.rows.length - 1].strike,
  zeroGamma: model.zeroGamma,
  vixSpot: model.vixSpot,
  quality: model.quality,
  gammaTotal: model.totals.gamma,
  expectedGamma: model.rows.reduce((sum, row) => sum + row.gamma, 0),
  kingNode: model.gammaNode.strike
}));
"""
    result = subprocess.run(
        ["node", "-e", node_program, str(KING_NODE_JS), json.dumps(fixture)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    parsed = json.loads(result.stdout)

    assert parsed["windowSize"] == 47
    assert parsed["firstStrike"] == 5840
    assert parsed["lastStrike"] == 6300
    assert parsed["zeroGamma"] == 6035
    assert parsed["vixSpot"] == 16.25
    assert parsed["quality"] == "COMPLETE"
    assert parsed["gammaTotal"] == pytest.approx(parsed["expectedGamma"])
    assert parsed["kingNode"] in {5840, 6300}
