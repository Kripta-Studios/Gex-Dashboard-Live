from __future__ import annotations

import importlib.util
import json
import math
import copy
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("diagnose_weekly_ev_components.py")
SPEC = importlib.util.spec_from_file_location("diagnose_weekly_ev_components", MODULE_PATH)
assert SPEC and SPEC.loader
diagnostic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostic)


def means(value: float = 0.0) -> dict:
    return {
        "shrinkage": 20,
        "global": {"adverse": {str(k): value + k / 10 for k in range(5)}},
        "cells": {
            "adverse": {
                f"{ticker}:{right}": {
                    str(k): {"n": k + 1, "mean_y": value + k / 10}
                    for k in range(5)
                }
                for ticker in ("SPY", "QQQ", "SPXW")
                for right in ("CALL", "PUT")
            }
        },
    }


def candidate(**updates) -> dict:
    row = {
        "candidate_id": "SPY:20260102:20260109:CALL",
        "ticker": "SPY",
        "entry_date": "20260102",
        "exit_date": "20260106",
        "right": "CALL",
        "decision_ask": 2.0,
        "status": "OBSERVED_EXIT",
        "scenario": 2,
        "payoff_is_lower_bound": False,
        "net_adverse": 15.0,
        "label_available_at": "2026-01-06T10:35:00-05:00",
    }
    row.update(updates)
    if "label_available_at" not in updates:
        day = row["entry_date"] if row["status"] == "NO_FILL" else row["exit_date"]
        stamp = f"{day[:4]}-{day[4:6]}-{day[6:]}T10:35:00"
        row["label_available_at"] = stamp + ("-04:00" if day[4:6] in {"03", "04", "05", "06", "07", "08", "09", "10"} else "-05:00")
    return row


def state(**updates) -> dict:
    row = {
        "state_id": "S1",
        "creation_date": "20260102",
        "asof": "2026-01-02T00:00:00-05:00",
        "prior": [0.1, 0.2, 0.3, 0.2, 0.2],
        "calibration": {
            "formula": "(1-alpha)*p_model+alpha*p_train_prior",
            "selected_alpha": 0.25,
        },
        "conditional_means": means(),
    }
    row.update(updates)
    return row


def score(row: dict | None = None, **updates) -> dict:
    source = row or candidate()
    q = [0.2] * 5
    prior = state()["prior"]
    alpha = state()["calibration"]["selected_alpha"]
    item = {
        "policy": "MONTHLY_RAW",
        "candidate_id": source["candidate_id"],
        "model_id": "S1",
        "entry_date": source["entry_date"],
        "ticker": source["ticker"],
        "right": source["right"],
        "scenario": source["scenario"],
        "payoff_is_lower_bound": source["payoff_is_lower_bound"],
        "is_bridge": False,
        "p_model": q,
        "p_cal": [(1 - alpha) * q[k] + alpha * prior[k] for k in range(5)],
    }
    cell = state()["conditional_means"]["cells"]["adverse"][f"{source['ticker']}:{source['right']}"]
    item["ev_adverse"] = source["decision_ask"] * 100 * sum(item["p_cal"][k] * cell[str(k)]["mean_y"] for k in range(5))
    item.update(updates)
    return item


def component(**candidate_updates) -> dict:
    source = candidate(**candidate_updates)
    return diagnostic.component_row(score(source), source, state())


def empty_ledger() -> dict:
    return {"selected": set(), "filled": set(), "entries": {}, "exits": {}, "rows": []}


def test_component_identity_calibration_scale_and_signed_decomposition() -> None:
    row = component()
    assert row["scale_usd"] == 200.0
    assert row["p_cal"] == pytest.approx([0.175, 0.2, 0.225, 0.2, 0.2])
    assert row["error"] == pytest.approx(row["c_probability"] + row["c_payoff"])
    assert row["c_probability"] == pytest.approx(row["c_model"] + row["c_calibration"])
    assert row["c_probability"] == pytest.approx(sum(row["class_contributions"]))
    assert max(abs(value) for value in row["residuals"].values()) <= diagnostic.ABS_ROW_TOL


def test_decision_ask_not_entry_ask_is_the_scale() -> None:
    source = candidate(decision_ask=3.5, entry_ask=99.0)
    row = diagnostic.component_row(score(source), source, state())
    assert row["scale_usd"] == 350.0


def test_lower_bound_and_candidate_no_fill_semantics() -> None:
    lower = candidate(status="MISSING_EXIT_SOURCE", scenario=1, payoff_is_lower_bound=True, net_adverse=-202.6)
    diagnostic.validate_candidate(lower)
    result = diagnostic.component_row(score(lower), lower, state())
    assert result["payoff_is_lower_bound"] is True
    no_fill = candidate(status="NO_FILL", scenario=0, payoff_is_lower_bound=False, net_adverse=0.0)
    diagnostic.validate_candidate(no_fill)
    with pytest.raises(diagnostic.DiagnosticError, match="candidate NO_FILL"):
        diagnostic.validate_candidate({**no_fill, "net_adverse": 1.0})


def test_probability_and_stored_ev_drift_fail_closed() -> None:
    source = candidate()
    with pytest.raises(diagnostic.DiagnosticError, match="p_cal sum"):
        diagnostic.component_row(score(source, p_cal=[0.1] * 5), source, state())
    with pytest.raises(diagnostic.DiagnosticError, match="row identity"):
        diagnostic.component_row(score(source, ev_adverse=999.0), source, state())


def test_identity_state_and_flags_must_join_exactly() -> None:
    source = candidate()
    with pytest.raises(diagnostic.DiagnosticError, match="mismatch ticker"):
        diagnostic.component_row(score(source, ticker="QQQ"), source, state())
    with pytest.raises(diagnostic.DiagnosticError, match="state mismatch"):
        diagnostic.component_row(score(source), source, state(state_id="OTHER"))
    with pytest.raises(diagnostic.DiagnosticError, match="mismatch payoff_is_lower_bound"):
        diagnostic.component_row(score(source, payoff_is_lower_bound=True), source, state())


def test_temporal_guards_reject_future_state_or_late_label() -> None:
    source = candidate()
    with pytest.raises(diagnostic.DiagnosticError, match="future state"):
        diagnostic.component_row(
            score(source), source,
            state(creation_date="20260103", asof="2026-01-03T00:00:00-05:00"),
        )
    late = candidate(
        entry_date="20260915", exit_date="20260918",
        label_available_at="2026-09-18T10:35:00-04:00",
    )
    with pytest.raises(diagnostic.DiagnosticError, match="final cutoff"):
        diagnostic.validate_candidate(late)


def test_bridge_flag_must_match_candidate_source() -> None:
    source = candidate(_candidate_source="h2_boundary_bridge_01")
    with pytest.raises(diagnostic.DiagnosticError, match="bridge flag"):
        diagnostic.component_row(score(source, is_bridge=False), source, state())
    result = diagnostic.component_row(score(source, is_bridge=True), source, state())
    assert result["is_bridge"] is True


def test_missing_mean_cell_and_duplicate_index_fail_closed() -> None:
    bad = state()
    del bad["conditional_means"]["cells"]["adverse"]["SPY:CALL"]["4"]
    source = candidate()
    with pytest.raises(diagnostic.DiagnosticError, match="mean cell"):
        diagnostic.component_row(score(source), source, bad)
    with pytest.raises(diagnostic.DiagnosticError, match="duplicate synthetic"):
        diagnostic.index_unique([{"candidate_id": "X"}, {"candidate_id": "X"}], "candidate_id", "synthetic")


def test_ledger_candidate_no_fill_is_distinct_from_candidate_status() -> None:
    source = candidate(status="OBSERVED_EXIT")
    rows = [{
        "event": "NO_FILL", "policy": "MONTHLY_RAW", "cost": "adverse",
        "candidate_id": source["candidate_id"], "reason": "ENTRY_RISK_BUDGET",
    }]
    book = diagnostic.ledger_sets("MONTHLY_RAW", rows, {source["candidate_id"]: source})
    assert book["selected"] == {source["candidate_id"]}
    assert book["filled"] == set()


def test_ledger_entry_exit_quantity_and_net_reconcile() -> None:
    source = candidate(net_adverse=-7.5)
    rows = [
        {"event": "ENTRY", "policy": "MONTHLY_RAW", "cost": "adverse", "candidate_id": source["candidate_id"], "model_id": "S1", "quantity": 3},
        {"event": "EXIT", "policy": "MONTHLY_RAW", "cost": "adverse", "candidate_id": source["candidate_id"], "model_id": "S1", "quantity": 3, "net_usd": -22.5},
    ]
    book = diagnostic.ledger_sets("MONTHLY_RAW", rows, {source["candidate_id"]: source})
    assert book["selected"] == book["filled"] == {source["candidate_id"]}
    rows[1]["net_usd"] = -21.0
    with pytest.raises(diagnostic.DiagnosticError, match="ledger net"):
        diagnostic.ledger_sets("MONTHLY_RAW", rows, {source["candidate_id"]: source})


def test_empty_cell_has_zero_sums_and_null_means() -> None:
    row = diagnostic.aggregate_cell([], {
        "policy": "MONTHLY_RAW", "universe": "ALL", "view": "conservative_all",
        "partition": "SCENARIO", "value": "4",
    }, empty_ledger())
    assert row["n"] == row["lower_bound_n"] == 0
    assert row["sum_ev"] == row["sum_error"] == 0.0
    assert row["mean_ev"] is None and row["mae_error"] is None
    assert row["sum_class_contributions"] == [0.0] * 5
    assert row["cell_n_min"] == [None] * 5


def test_without_lower_bounds_keeps_candidate_no_fill() -> None:
    observed = component()
    lower = component(
        candidate_id="SPY:20260202:20260209:CALL", entry_date="20260202",
        status="MISSING_EXIT_QUOTE", scenario=1, payoff_is_lower_bound=True,
    )
    no_fill = component(
        candidate_id="SPY:20260302:20260309:CALL", entry_date="20260302",
        status="NO_FILL", scenario=0, payoff_is_lower_bound=False, net_adverse=0.0,
    )
    rows = [observed, lower, no_fill]
    kept = [row for row in rows if not row["payoff_is_lower_bound"]]
    assert {row["status"] for row in kept} == {"OBSERVED_EXIT", "NO_FILL"}


def test_filled_aggregate_separates_contract_ev_from_quantity_pnl() -> None:
    row = component(net_adverse=4.0)
    candidate_id = row["candidate_id"]
    book = {
        "selected": {candidate_id}, "filled": {candidate_id},
        "entries": {candidate_id: {"quantity": 7}},
        "exits": {candidate_id: {"net_usd": 28.0}}, "rows": [],
    }
    result = diagnostic.aggregate_cell([row], {
        "policy": row["policy"], "universe": "FILLED", "view": "conservative_all",
        "partition": "TOTAL", "value": "ALL",
    }, book)
    assert result["sum_net"] == 4.0
    assert result["sum_quantity_net"] == result["exit_net_usd"] == 28.0
    assert result["sum_quantity_ev"] == pytest.approx(7 * row["ev"])


def test_all_partition_cardinality_is_27() -> None:
    assert sum(len(values) for _, values in diagnostic.PARTITIONS) == 27
    assert 27 * len(diagnostic.POLICIES) * len(diagnostic.UNIVERSES) * len(diagnostic.VIEWS) == 810


def test_closing_rehash_detects_mutation(tmp_path: Path) -> None:
    path = tmp_path / "sealed.json"
    path.write_text(json.dumps({"x": 1}), encoding="utf-8")
    snapshots = {str(path): diagnostic.pin(path)}
    diagnostic.closing_rehash(snapshots)
    path.write_text(json.dumps({"x": 2}), encoding="utf-8")
    with pytest.raises(diagnostic.DiagnosticError, match="input changed"):
        diagnostic.closing_rehash(snapshots)


def test_default_cli_is_descriptive_and_does_not_create_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "absent"
    assert diagnostic.main(["--output", str(output)]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["status"] == "READY_NOT_EXECUTED"
    assert not output.exists()


def test_probability_metrics_known_values() -> None:
    row = component()
    logloss, brier = diagnostic.probability_metrics([row])
    assert logloss == pytest.approx(-math.log(row["p_cal"][row["scenario"]]))
    expected = sum((row["p_cal"][k] - (1 if k == row["scenario"] else 0)) ** 2 for k in range(5))
    assert brier == pytest.approx(expected)


def test_probability_metrics_uses_published_1e_minus_12_clip() -> None:
    row = component()
    row["scenario"] = 0
    row["p_cal"] = [1e-20, 0.25, 0.25, 0.25, 0.25 - 1e-20]
    logloss, _ = diagnostic.probability_metrics([row])
    assert logloss == pytest.approx(-math.log(1e-12))


def test_all_policies_must_share_exact_candidate_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostic, "EXPECTED_PER_POLICY", 2)
    rows = [
        {"policy": policy, "candidate_id": candidate_id}
        for policy in diagnostic.POLICIES
        for candidate_id in ("A", "B")
    ]
    assert diagnostic.validate_common_score_ids(rows) == {"A", "B"}
    rows[-1]["candidate_id"] = "C"
    with pytest.raises(diagnostic.DiagnosticError, match="exact candidate IDs"):
        diagnostic.validate_common_score_ids(rows)


def _integral_components_and_ledgers() -> tuple[list[dict], dict[str, dict]]:
    prototypes = [
        component(
            candidate_id="SPY:20260102:20260109:CALL", entry_date="20260102",
            exit_date="20260106", status="OBSERVED_EXIT", scenario=2,
            payoff_is_lower_bound=False, net_adverse=4.0,
        ),
        component(
            candidate_id="QQQ:20260202:20260209:PUT", ticker="QQQ", right="PUT",
            entry_date="20260202", exit_date="20260204", status="MISSING_EXIT_SOURCE",
            scenario=1, payoff_is_lower_bound=True, net_adverse=-202.6,
        ),
        component(
            candidate_id="SPXW:20260701:20260708:CALL", ticker="SPXW",
            entry_date="20260701", exit_date="20260706", status="NO_FILL",
            scenario=0, payoff_is_lower_bound=False, net_adverse=0.0,
        ),
    ]
    components: list[dict] = []
    ledgers: dict[str, dict] = {}
    for policy in diagnostic.POLICIES:
        rows = copy.deepcopy(prototypes)
        for row in rows:
            row["policy"] = policy
        components.extend(rows)
        observed, lower = rows[0], rows[1]
        quantity = 2
        ledgers[policy] = {
            "selected": {observed["candidate_id"], lower["candidate_id"]},
            "filled": {observed["candidate_id"]},
            "entries": {observed["candidate_id"]: {"quantity": quantity}},
            "exits": {observed["candidate_id"]: {"net_usd": quantity * observed["net"]}},
            "rows": [],
        }
    return components, ledgers


def test_integral_810_cells_cover_distinct_no_fill_lower_bound_and_filled() -> None:
    components, ledgers = _integral_components_and_ledgers()
    aggregates = diagnostic.build_aggregates(components, ledgers)
    assert len(aggregates) == 810
    result = diagnostic.validate_partition_reconciliation(aggregates)
    assert result["families_checked"] == 5 * 3 * 2 * 5
    total = next(
        row for row in aggregates
        if row["policy"] == "FROZEN_CONTEXT182" and row["universe"] == "ALL"
        and row["view"] == "conservative_all" and row["partition"] == "TOTAL"
    )
    observed = next(
        row for row in aggregates
        if row["policy"] == "FROZEN_CONTEXT182" and row["universe"] == "ALL"
        and row["view"] == "without_lower_bounds" and row["partition"] == "TOTAL"
    )
    assert (total["n"], total["lower_bound_n"]) == (3, 1)
    assert (observed["n"], observed["lower_bound_n"]) == (2, 0)
    assert math.fsum(total["sum_class_contributions"]) == pytest.approx(total["sum_c_probability"])


def test_partition_reconciliation_detects_filled_quantity_or_cell_contribution_drift() -> None:
    components, ledgers = _integral_components_and_ledgers()
    aggregates = diagnostic.build_aggregates(components, ledgers)
    quantity_drift = copy.deepcopy(aggregates)
    cell = next(
        row for row in quantity_drift
        if row["policy"] == "FROZEN_CONTEXT182" and row["universe"] == "FILLED"
        and row["view"] == "conservative_all" and row["partition"] == "ENTRY_MONTH"
        and row["value"] == "202601"
    )
    cell["sum_quantity_net"] += 1.0
    with pytest.raises(diagnostic.DiagnosticError, match="partition sum ENTRY_MONTH/sum_quantity_net"):
        diagnostic.validate_partition_reconciliation(quantity_drift)
    contribution_drift = copy.deepcopy(aggregates)
    cell = next(
        row for row in contribution_drift
        if row["policy"] == "FROZEN_CONTEXT182" and row["universe"] == "ALL"
        and row["view"] == "conservative_all" and row["partition"] == "SCENARIO"
        and row["value"] == "2"
    )
    cell["sum_class_contributions"][0] += 1.0
    with pytest.raises(diagnostic.DiagnosticError, match="cell contribution"):
        diagnostic.validate_partition_reconciliation(contribution_drift)


def test_plain_file_guard_rejects_symlinked_ancestor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    ancestor = root / "linked"
    ancestor.mkdir(parents=True)
    payload = ancestor / "payload.json"
    payload.write_text("{}", encoding="utf-8")
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: True if self == ancestor else original(self))
    with pytest.raises(diagnostic.DiagnosticError, match="symlink ancestor"):
        diagnostic.guard_plain_file(payload.resolve(), (root.resolve(),))
