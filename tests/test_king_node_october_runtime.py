"""Regression checks for the supplied October equations, without broker or Excel."""

import ast
import inspect
import json
import math
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from modules import king_node_live_kernel, king_node_live_math
from modules.king_node_contract import validate_normalized_input, validate_reference
from modules.king_node_engine import KingNodeDataError, build_snapshot
from modules.king_node_formula_runtime import Workbook, is_error, parse
from modules.king_node_kernel_bridge import Kernel
from modules.king_node_workbook_adapter import surface_from_input

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def reference():
    return json.loads((ROOT / "config/king_node_reference.json").read_text())


@pytest.fixture
def payload():
    return json.loads(
        (ROOT / "tests/fixtures/king_node_v2/golden_input.json").read_text()
    )


def test_pure_source_functions_are_exact_copies():
    original = {}
    for file in ("replay_king_node.py", "live_king_node.py"):
        original.update(
            {
                n.name: ast.dump(n, include_attributes=False)
                for n in ast.parse((ROOT / file).read_text()).body
                if isinstance(n, ast.FunctionDef)
            }
        )
    for module in (king_node_live_kernel, king_node_live_math):
        nodes = ast.parse(Path(module.__file__).read_text()).body
        functions = [n for n in nodes if isinstance(n, ast.FunctionDef)]
        assert len(functions) >= 6
        for node in functions:
            assert ast.dump(node, include_attributes=False) == original[node.name], (
                node.name
            )


def test_live_and_replay_workbooks_have_identical_formulas():
    from scripts.audit_king_node_workbook import _read_xlsx_formulas

    live, _, _ = _read_xlsx_formulas(ROOT / "MASTER_KING_NODE_RECORD_V5.xlsx")
    replay, _, _ = _read_xlsx_formulas(ROOT / "MASTER_KING_NODE_RECORD_V5_REPLAY.xlsx")
    assert len(live) == len(replay) == 18302
    assert {k: v.formula for k, v in live.items()} == {
        k: v.formula for k, v in replay.items()
    }


def test_surface_equations_independent_black_scholes(payload):
    normalized = validate_normalized_input(payload)
    actual, hours = surface_from_input(normalized)
    assert hours == 6
    spot, years = normalized.underlying["spot"], 6 / (365 * 24)
    pairs = {}
    for r in normalized.option_rows:
        pairs.setdefault(r.strike, {})[r.right] = r
    for row in actual:
        call, put = pairs[row["strike"]]["CALL"], pairs[row["strike"]]["PUT"]
        sigma = call.iv
        d1 = (math.log(spot / call.strike) + (0.043 - 0.012 + sigma**2 / 2) * years) / (
            sigma * math.sqrt(years)
        )
        d2 = d1 - sigma * math.sqrt(years)
        density = math.exp(-(d1**2) / 2) / math.sqrt(2 * math.pi)
        gamma = math.exp(-0.012 * years) * density / (spot * sigma * math.sqrt(years))
        net = call.open_interest - put.open_interest
        total = call.open_interest + put.open_interest
        assert row["raw_gamma"] == pytest.approx(gamma * total)
        assert row["gex"] == pytest.approx(gamma * net * 0.1 * spot**2 * 0.01)
        assert row["gamma_gross"] == pytest.approx(gamma * total * 0.1 * spot**2 * 0.01)
        assert row["zomma"] == pytest.approx(
            gamma * (d1 * d2 - 1) / sigma * net * 0.1 * spot**2 * 0.01
        )
    # Put IV belongs to skew; it must not change the source's CALL-IV exposures.
    changed = deepcopy(payload)
    for r in changed["option_rows"]:
        if r["right"] == "PUT":
            r["iv"] *= 2
    altered, _ = surface_from_input(validate_normalized_input(changed))
    assert [r["gex"] for r in altered] == [r["gex"] for r in actual]


def test_excel_array_blank_and_lazy_error_semantics():
    w = Workbook(
        {
            "Sheet": {
                "A1": {"value": 2},
                "A2": {"value": 4},
                "A3": {"value": 8},
                "B1": {"formula": "=SUMPRODUCT((A1:A3>=4)*A1:A3)"},
                "B2": {"formula": "=INDEX(A1:A3,MATCH(4,A1:A3,0))"},
                "B3": {"formula": "=IF(FALSE,B3,IFERROR(1/0,7))"},
                "B4": {"formula": '=IF(C1="",N(C1)+1,99)'},
                "B5": {"formula": "=SUMPRODUCT(ROW(A1:A3)*A1:A3)"},
                "B6": {"formula": "=IFERROR(chr,17)"},
            }
        }
    )
    assert [w.get("Sheet", f"B{i}") for i in range(1, 7)] == [12, 4, 7, 1, 34, 17]
    w.set("Sheet", "A2", 10)
    assert w.get("Sheet", "B1") == 18
    assert w.get("Sheet", "B5") == 46


def test_reference_has_formulas_without_saved_market_caches(reference):
    for cells in reference["workbook_cells"].values():
        for record in cells.values():
            assert set(record) in ({"formula"}, {"value"})
            if "formula" in record:
                parse(record["formula"])
    w = Workbook(reference["workbook_cells"])
    assert "value" not in reference["workbook_cells"]["King Node Model"].get("B4", {})
    assert w.get("Level Engine", "KO8").startswith("gDexVannaLatch")
    assert w.get("Level Engine", "LO8").startswith("vexBreakLatch")
    assert w.get("Level Engine", "MB8").startswith("sandLock")
    assert w.get("Level Engine", "BF123").startswith(
        "(engine) MAX SPEED strike 1 cycle ago"
    )


def test_map_precedes_raw_iv_and_fragile_survives_restart(reference):
    w = Workbook(reference["workbook_cells"])
    for c, v in {
        "A8": "Pos",
        "B5": 23,
        "D5": 100,
        "F5": 25,
        "P4": "Flat",
        "P5": "Flat",
        "P6": "Flat",
    }.items():
        w.set("King Node Model", c, v)
    assert w.get("King Node Model", "J5") == "HIGH"
    assert w.get("King Node Model", "L5") == "Low"
    now = datetime(2026, 10, 9, 14, tzinfo=UTC)
    k = Kernel(w, None, now)
    k.call("_write_fragile_hold", 500_000)
    assert w.get("Level Engine", "BG76") == 0

    k = Kernel(w, json.loads(json.dumps(k.persisted())), now + timedelta(seconds=30))
    k.call("_write_fragile_hold", 500_000)
    assert w.get("Level Engine", "BG76") == 1
    k.call("_write_fragile_hold", 3_000_000)
    assert w.get("Level Engine", "BG76") == 1
    k.call("_write_fragile_hold", 3_000_000)
    assert w.get("Level Engine", "BG76") == 0


def test_replay_rank_hold_and_speed_header_activate(reference):
    w = Workbook(reference["workbook_cells"])
    now = datetime(2026, 10, 9, 14, tzinfo=UTC)
    k = Kernel(w, None, now)
    w.set("Level Engine", "AA9", 6000)
    w.set("Level Engine", "AH9", 2)
    k.call("_write_grank", k.sheets["Level Engine"])
    assert w.get("Level Engine", "GK9") == 1
    w.set("Level Engine", "AH9", 4)
    k.call("_write_grank", k.sheets["Level Engine"])
    assert w.get("Level Engine", "GK9") == 1
    w.set("Level Engine", "AH9", 6)
    k.call("_write_grank", k.sheets["Level Engine"])
    assert w.get("Level Engine", "GK9") == 0
    rows = [[6000, 1, 1, 1, 1, 1, 1, 1, 5], [6005, 1, 1, 1, 1, 1, 1, 1, -5]]
    k.call("_write_spd_hold", rows)
    k = Kernel(w, json.loads(json.dumps(k.persisted())), now + timedelta(seconds=30))
    k.call("_write_spd_hold", rows)
    assert w.get("Level Engine", "BG123") == 6000
    assert w.get("Level Engine", "BG125") == 6005


def test_full_surface_restart_idempotence_and_negative_regime(payload, reference):
    # Negative gamma fixture activates the opposite ranking/UNSAFE branches.
    for r in payload["option_rows"]:
        r["open_interest"] = 1000 if r["right"] == "CALL" else 2000
    first, state = build_snapshot(payload, reference=reference)
    assert first["regime"]["signs"]["gamma"] == "Neg"
    assert not first["workbook_calculation"]["state_machine_errors"]
    repeated, state2 = build_snapshot(
        payload, state=json.loads(json.dumps(state)), reference=reference
    )
    assert repeated == first
    assert state2 == state
    assert all(not is_error(v) for v in first["totals"].values())
    payload["underlying"]["spot"] += 1
    with pytest.raises(KingNodeDataError, match="newer timestamp"):
        build_snapshot(payload, state=state, reference=reference)


def test_partial_ladder_fails_instead_of_silent_excel_defaults(payload, reference):
    payload["option_rows"] = payload["option_rows"][:-2]
    with pytest.raises(KingNodeDataError, match="47 contiguous"):
        build_snapshot(payload, reference=reference)


def test_missing_previous_close_is_display_only(payload, reference):
    payload["underlying"]["previous_close"] = None
    assert validate_normalized_input(payload).underlying["previous_close"] is None
    from services.king_node_service import KingNodeV2Service

    assert KingNodeV2Service._engine_v2_builder() is build_snapshot
    assert "normalized_input" in inspect.signature(build_snapshot).parameters


def test_service_publishes_real_october_engine_and_health_contract(
    payload, reference, tmp_path
):
    from modules.thetadata_adapter import MarketCalendar
    from scripts.check_king_node_health import inspect_snapshot
    from services.king_node_service import KingNodeV2Service

    now = datetime.fromisoformat(payload["as_of"])
    payload["source"]["input_hash"] = "synthetic-october-service"
    payload["underlying"]["previous_close"] = None
    service = KingNodeV2Service(
        thetadata_url="http://127.0.0.1:1",
        reference_path=tmp_path / "unused",
        theta_client=object(),
    )
    session = MarketCalendar().session_at(now)
    snapshot, state = service._build_live_snapshot(
        normalized_input=payload,
        reference=validate_reference(reference),
        state={},
        index_details={},
        now=now,
        session=session,
        readiness={"mdds": "CONNECTED"},
    )
    assert snapshot["status"] == "live"
    assert snapshot["quality"]["valid"] is True
    assert snapshot["inputs"]["dte_hours"] == 6
    assert snapshot["inputs"]["previous_close"] is None
    assert (
        snapshot["provenance"]["calculation_method"]
        == "live_king_node_20261010_call_iv_black_scholes"
    )
    assert inspect_snapshot(snapshot, now=now, max_age_seconds=180)["healthy"] is True
    assert state["workbook"]["kernel"]
