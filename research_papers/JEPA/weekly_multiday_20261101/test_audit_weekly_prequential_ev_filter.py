from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path

import pytest

import audit_weekly_prequential_ev_filter as audit


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def dump_lines(path: Path, values: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n" for value in values), encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_pin(path: Path, *, with_path: bool = True) -> dict:
    result = {"bytes": path.stat().st_size, "sha256": digest(path)}
    return {"path": str(path), **result} if with_path else result


def intention(index: int, day: str, available: str, *, residual: float = -0.1, ev: float = 10.0, scale: float = 100.0) -> dict:
    return {
        "parent": "FROZEN_CONTEXT182", "candidate_id": f"C{index}", "entry_date": day,
        "ticker": audit.TICKERS[index % 3], "right": "CALL", "model_id": "M",
        "ev_base_raw": ev, "ev_adverse_raw": ev, "decision_ask": scale / 100,
        "scale_usd": scale, "net_base": ev + residual * scale, "net_adverse": ev + residual * scale,
        "status": "OBSERVED_EXIT", "scenario": 1,
        "label_available_at": f"{available[:4]}-{available[4:6]}-{available[6:]}T10:35:00-05:00",
        "payoff_is_lower_bound": False, "normalized_residual": residual,
    }


def weekdays(start: str, count: int) -> list[str]:
    value = datetime.strptime(start, "%Y%m%d")
    output = []
    while len(output) < count:
        if value.weekday() < 5:
            output.append(value.strftime("%Y%m%d"))
        value += timedelta(days=1)
    return output


def test_history_cutoff_is_strict_midnight_and_future_poison_has_no_effect() -> None:
    values = [
        intention(1, "20260102", "20260105"),
        intention(2, "20260105", "20260106", residual=-0.2),
        intention(3, "20260106", "20260107", residual=9.0),
    ]
    state = audit.filter_state("20260106", values)
    assert state["history_ids"] == ["C1"]
    assert audit.filter_state("20260106", values[:2]) == state
    assert audit.filter_state("20260107", values)["history_ids"] == ["C1", "C2"]


def test_n19_is_raw_and_n20_activates_shrunk_downward_filter() -> None:
    days = weekdays("20250102", 25)
    values = [intention(i, days[i], days[i + 1], residual=-0.2) for i in range(20)]
    state19 = audit.filter_state(days[20], values[:19])
    state20 = audit.filter_state(days[21], values)
    assert state19 == {**state19, "correction": 0.0, "buffer": 0.0, "state": "WARMUP_RAW"}
    assert state20["n"] == 20 and state20["state"] == "ACTIVE_FILTER"
    assert state20["correction"] == pytest.approx(-0.1)
    assert state20["buffer"] == pytest.approx(0.0)


def test_normalization_equalizes_different_premiums() -> None:
    low = intention(1, "20260102", "20260105", residual=-0.25, ev=10, scale=100)
    high = intention(2, "20260103", "20260106", residual=-0.25, ev=100, scale=1000)
    assert (low["net_adverse"] - low["ev_adverse_raw"]) / low["scale_usd"] == pytest.approx(-0.25)
    assert (high["net_adverse"] - high["ev_adverse_raw"]) / high["scale_usd"] == pytest.approx(-0.25)


def test_gate_only_decreases_and_never_rescues_nonpositive() -> None:
    state = {"n": 20, "state": "ACTIVE_FILTER", "correction": -0.1, "buffer": 0.05}
    accepted = audit.gate_intention(intention(1, "20260102", "20260105", ev=20, scale=100), state)
    rejected = audit.gate_intention(intention(2, "20260102", "20260105", ev=10, scale=100), state)
    assert accepted["ev_gate"] == pytest.approx(5) and accepted["accepted"]
    assert rejected["ev_gate"] == pytest.approx(-5) and not rejected["accepted"]
    zero = audit.gate_intention(intention(3, "20260102", "20260105", ev=0, scale=100), {**state, "correction": 0, "buffer": 0})
    assert not zero["accepted"]


def test_top1_unique_positive_only_and_no_rerank(monkeypatch: pytest.MonkeyPatch) -> None:
    candidates = []
    scores = []
    for right, ev in (("CALL", 4.0), ("PUT", 2.0)):
        cid = f"SPY:20260102:20260109:{right}"
        candidates.append({"candidate_id": cid, "decision_ask": 1.0, "net_base": 0.0, "net_adverse": 0.0, "status": "OBSERVED_EXIT", "scenario": 1, "label_available_at": "2026-01-06T10:35:00-05:00", "payoff_is_lower_bound": False})
        scores.append({"candidate_id": cid, "entry_date": "20260102", "ticker": "SPY", "right": right, "policy": "FROZEN_CONTEXT182", "model_id": "M", "ev_adverse": ev, "ev_base": ev})
    monkeypatch.setattr(audit, "EXPECTED_CANDIDATES", 2)
    selected = audit.raw_intentions("FROZEN_CONTEXT182", candidates, scores)
    assert [row["right"] for row in selected] == ["CALL"]
    scores[1]["ev_adverse"] = 4.0
    assert audit.raw_intentions("FROZEN_CONTEXT182", candidates, scores) == []


def test_monthly_gate_includes_zero_months_and_requires_strict_positive() -> None:
    ledger = [{"event": "EXIT", "date": "20260105", "net_usd": 1.0}, {"event": "EXIT", "date": "20260305", "net_usd": 2.0}]
    result = audit.monthly_full_gate(ledger)
    assert result["monthly_exit_net_usd"]["202602"] == 0
    assert not result["passes_8_of_8"] and result["completed_positive"] == 2


def test_lower_bound_and_no_fill_remain_history_observations() -> None:
    lower = intention(1, "20260102", "20260105", residual=-1)
    lower["payoff_is_lower_bound"] = True
    no_fill = intention(2, "20260103", "20260106", residual=-0.1)
    no_fill["net_adverse"] = 0.0
    no_fill["normalized_residual"] = (0.0 - no_fill["ev_adverse_raw"]) / no_fill["scale_usd"]
    state = audit.filter_state("20260107", [lower, no_fill])
    assert state["history_ids"] == ["C1", "C2"]


def test_source_has_no_estimator_or_producer_import() -> None:
    source = Path(audit.__file__).read_text(encoding="utf-8")
    assert "sklearn" not in source.lower() and ".fit(" not in source
    assert "import prequential_ev_filter" not in source
    assert "producer output schema binding is not published" not in source
    assert audit.PURE_AUDITOR_SHA256 == "3eb6b9795ad260971435259858f86d3c00111bcc141973faf986411d4a68ad99"


def test_filter_state_variance_uses_sample_denominator() -> None:
    days = weekdays("20250102", 25)
    values = [intention(i, days[i], days[i + 1], residual=float(i % 2)) for i in range(20)]
    state = audit.filter_state(days[21], values)
    assert state["s"] == pytest.approx(math.sqrt(5 / 19))


def test_diagnostics_have_full_216_cells_and_typed_empty_values() -> None:
    row = intention(1, "20260102", "20260105", residual=-0.25, ev=10, scale=100)
    decision = {
        "parent": row["parent"], "entry_date": row["entry_date"], "ticker": row["ticker"],
        "raw_winner_id": row["candidate_id"], "raw_reason": "EV_TOP1",
        "ev_gate": 5.0, "accepted": True,
    }
    result = audit.build_ev_diagnostics([row], [decision])
    assert len(result) == 216
    total = next(item for item in result if item["parent"] == row["parent"] and item["universe"] == "INTENTIONS" and item["view"] == "conservative_all" and item["partition"] == "TOTAL")
    assert total["value"] == "ALL" and total["n"] == 1
    assert total["bias_raw"] == pytest.approx(25.0)
    assert total["bias_gate"] == pytest.approx(20.0)
    empty = next(item for item in result if item["parent"] == "MONTHLY_RAW" and item["universe"] == "INTENTIONS" and item["partition"] == "TOTAL")
    assert empty["n"] == 0 and empty["lower_bound_n"] == 0
    assert all(empty[key] is None for key in ("mean_ev_raw", "mean_ev_gate", "mean_net", "bias_raw", "mae_raw", "bias_gate", "mae_gate"))


def test_duplicate_side_and_unknown_candidate_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = {"candidate_id": "C", "decision_ask": 1.0, "net_base": 0.0, "net_adverse": 0.0, "status": "OBSERVED_EXIT", "scenario": 1, "label_available_at": "2026-01-06T10:35:00-05:00", "payoff_is_lower_bound": False}
    score = {"candidate_id": "C", "entry_date": "20260102", "ticker": "SPY", "right": "CALL", "policy": "FROZEN_CONTEXT182", "model_id": "M", "ev_adverse": 4.0, "ev_base": 4.0}
    monkeypatch.setattr(audit, "EXPECTED_CANDIDATES", 2)
    with pytest.raises(audit.PrequentialAuditError, match="candidate IDs"):
        audit.raw_intentions("FROZEN_CONTEXT182", [candidate, dict(candidate)], [score, dict(score)])
    monkeypatch.setattr(audit, "EXPECTED_CANDIDATES", 1)
    with pytest.raises(audit.PrequentialAuditError, match="score universe"):
        audit.raw_intentions("FROZEN_CONTEXT182", [candidate], [{**score, "candidate_id": "UNKNOWN"}])


def test_prepare_filter_never_reranks_rejected_winner() -> None:
    candidates = [
        {"candidate_id": "A", "entry_date": "20260102", "ticker": "SPY"},
        {"candidate_id": "B", "entry_date": "20260102", "ticker": "SPY"},
    ]
    scores = [
        {"candidate_id": "A", "policy": "FROZEN_CONTEXT182", "ev_base": 9.0, "ev_adverse": 9.0},
        {"candidate_id": "B", "policy": "FROZEN_CONTEXT182", "ev_base": 8.0, "ev_adverse": 8.0},
    ]
    decisions = [{"entry_date": "20260102", "ticker": "SPY", "raw_winner_id": "A", "raw_reason": "EV_TOP1", "accepted": False, "ev_gate": -1.0}]
    rows, _ = audit.prepare_rows("FROZEN_CONTEXT182", "FILTER", candidates, scores, decisions)
    assert [row["_ev_adverse"] for row in rows] == [0.0, 0.0]


def test_recursive_comparison_rejects_summary_tamper() -> None:
    with pytest.raises(audit.PrequentialAuditError, match="summary/net numeric"):
        audit.compare_value({"net": 1.0}, {"net": 2.0}, "summary", tolerance=1e-6)
    with pytest.raises(audit.PrequentialAuditError, match="summary/count value"):
        audit.compare_value({"count": 2}, {"count": 2.0}, "summary", tolerance=1.0)


def test_history_prefix_and_discrete_quantity_are_exact() -> None:
    expected = [{"history_ids": ["A", "B"], "n": 2, "quantity": 47, "value": 1.0}]
    with pytest.raises(audit.PrequentialAuditError, match="history value history_ids"):
        audit.compare_rows([{"history_ids": ["A"], "n": 2, "quantity": 47, "value": 1.0}], expected, "history")
    with pytest.raises(audit.PrequentialAuditError, match="ledger value quantity"):
        audit.compare_rows([{"history_ids": ["A", "B"], "n": 2, "quantity": 48, "value": 1.0}], expected, "ledger")


def test_full_run_artificial_manifest_reconstructs_all_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "artifacts"
    adaptation = base / "h2_context_adaptation_01"
    h1 = base / "h2_dataset_v2_01"
    q3 = base / "h2_dataset_v2_extension_2026q3_partial_01"
    bridge = base / "h2_boundary_bridge_01"
    producer = base / "prequential_ev_filter_01"
    observer = base / "prequential_ev_filter_observer_01"
    for value in (adaptation, h1, q3, bridge, producer, observer):
        value.mkdir(parents=True)
    monkeypatch.setattr(audit, "BASE", base)
    monkeypatch.setattr(audit, "ADAPTATION_ROOT", adaptation)
    monkeypatch.setattr(audit, "DATASET_H1", h1)
    monkeypatch.setattr(audit, "DATASET_Q3", q3)
    monkeypatch.setattr(audit, "BRIDGE", bridge)
    monkeypatch.setattr(audit, "PRODUCER_ROOT", producer)
    monkeypatch.setattr(audit, "PRODUCER_OBSERVER", observer)
    monkeypatch.setattr(audit, "ADAPTATION_AUDIT", base / "h2_context_adaptation_audit_04" / "audit.json")
    monkeypatch.setattr(audit, "ADAPTATION_EXIT", base / "h2_context_adaptation_audit_observer_04" / "exit.json")
    monkeypatch.setattr(audit, "FIRST_DATE", "20260629")
    monkeypatch.setattr(audit, "LAST_DATE", "20260703")
    monkeypatch.setattr(audit, "LAST_ENTRY", "20260702")
    monkeypatch.setattr(audit, "EXPECTED_SESSIONS", 5)
    monkeypatch.setattr(audit, "EXPECTED_ALL_SESSIONS", 5)
    monkeypatch.setattr(audit, "EXPECTED_COVERAGE_IDENTITIES", 15)
    monkeypatch.setattr(audit, "EXPECTED_ALL_CANDIDATES", 18)
    monkeypatch.setattr(audit, "EXPECTED_CANDIDATES", 18)
    monkeypatch.setattr(audit, "EXPECTED_SCORES", 90)
    monkeypatch.setattr(audit, "EXPECTED_USED_SCORES", 54)
    monkeypatch.setattr(audit, "MIN_HISTORY", 3)

    def candidate(ticker: str, day: str, exit_day: str, right: str, *, losing: bool) -> dict:
        expiration = "20260710"
        exit_bid = 0.17 if losing else 1.20
        return {
            "candidate_id": f"{ticker}:{day}:{expiration}:{right}", "ticker": ticker,
            "entry_date": day, "exit_date": exit_day, "expiration": expiration,
            "strike": 100.0, "right": right, "features": [], "decision_ask": 1.0,
            "source_pins": {}, "entry_ask": 1.0, "exit_bid": exit_bid,
            "status": "OBSERVED_EXIT", "label_available_at": f"{exit_day[:4]}-{exit_day[4:6]}-{exit_day[6:]}T10:35:00-04:00",
            "scenario": 1, "payoff_is_lower_bound": False,
            "net_base": -87.6 if losing else 15.4, "net_adverse": -89.6 if losing else 13.4,
            "entry_debit_base": 102.3, "entry_debit_adverse": 103.3,
        }

    bridge_rows = [candidate(ticker, "20260629", "20260701", right, losing=True) for ticker in audit.TICKERS for right in audit.RIGHTS]
    q3_rows = [
        candidate(ticker, day, exit_day, right, losing=False)
        for day, exit_day in (("20260701", "20260702"), ("20260702", "20260703"))
        for ticker in audit.TICKERS for right in audit.RIGHTS
    ]
    dump_lines(h1 / "candidates.jsonl", [])
    dump_lines(q3 / "candidates.jsonl", q3_rows)
    dump_lines(bridge / "candidates.jsonl", bridge_rows)
    all_candidates = [*bridge_rows, *q3_rows]

    h1_dates, q3_dates = ("20260629", "20260630"), ("20260701", "20260702", "20260703")
    h1_coverage = {
        "calendar": [{"ticker": ticker, "date": day} for day in h1_dates for ticker in audit.TICKERS],
        "rows": [{"ticker": ticker, "entry_date": day, "status": "HORIZON_OUTSIDE_CALENDAR", "candidate_ids": []} for day in h1_dates for ticker in audit.TICKERS],
    }
    q3_coverage = {
        "calendar": [{"ticker": ticker, "date": day} for day in q3_dates for ticker in audit.TICKERS],
        "rows": [
            {"ticker": ticker, "entry_date": day, "status": "CANDIDATES_BUILT" if day != "20260703" else "NO_SERIES", "candidate_ids": [row["candidate_id"] for row in q3_rows if row["ticker"] == ticker and row["entry_date"] == day]}
            for day in q3_dates for ticker in audit.TICKERS
        ],
    }
    overlay = {"rows": [
        {"ticker": ticker, "entry_date": day, "exit_date": "20260701" if day == "20260629" else "20260702", "status": "CANDIDATES_BUILT" if day == "20260629" else "NO_SERIES", "candidate_ids": [row["candidate_id"] for row in bridge_rows if row["ticker"] == ticker] if day == "20260629" else []}
        for day in h1_dates for ticker in audit.TICKERS
    ]}
    dump(h1 / "coverage.json", h1_coverage)
    dump(q3 / "coverage.json", q3_coverage)
    dump(bridge / "coverage_overlay.json", overlay)
    coverage = audit.merge_coverage(h1_coverage, q3_coverage, overlay)
    sessions = audit.common_calendar(h1_coverage, q3_coverage)

    scores = []
    for policy in (*audit.PARENTS, "MONTHLY_GUARDED", "WEEKLY_GUARDED"):
        for row in all_candidates:
            ev = 10.0 if row["right"] == "CALL" else 5.0
            scores.append({
                "candidate_id": row["candidate_id"], "entry_date": row["entry_date"],
                "ev_adverse": ev, "ev_base": ev + 1.0, "is_bridge": row in bridge_rows,
                "model_id": f"{policy}:M", "p_cal": [0.2] * 5, "p_model": [0.2] * 5,
                "payoff_is_lower_bound": False, "policy": policy, "right": row["right"],
                "scenario": 1, "ticker": row["ticker"],
            })
    dump_lines(adaptation / "candidate_scores.jsonl", scores)
    dump(adaptation / "summary.json", {"sealed": True})
    parent_scores = {parent: [row for row in scores if row["policy"] == parent] for parent in audit.PARENTS}
    intentions, decisions = [], []
    for parent in audit.PARENTS:
        current = audit.raw_intentions(parent, all_candidates, parent_scores[parent])
        intentions.extend(current)
        decisions.extend(audit.reconstruct_decision_rows(parent, current, parent_scores[parent], sessions))
    helper = audit.import_pure_auditor()
    books = {}
    for parent in audit.PARENTS:
        parent_decisions = [row for row in decisions if row["parent"] == parent]
        for variant in audit.VARIANTS:
            replay_rows, _ = audit.prepare_rows(parent, variant, all_candidates, parent_scores[parent], parent_decisions)
            replayed = helper.replay_risk(replay_rows, coverage, sessions, audit.LAST_ENTRY)
            policy = f"{parent}_{variant}"
            for cost in audit.COSTS:
                decorated = audit.enrich_ledger(replayed[cost], parent, variant, parent_scores[parent], parent_decisions)
                books[(policy, cost)] = decorated
                dump_lines(producer / f"ledger_{parent.lower()}_{variant.lower()}_{cost}.jsonl", decorated)
                if variant == "CONTROL":
                    upstream = []
                    for event in replayed[cost]:
                        value = dict(event)
                        score = next((item for item in parent_scores[parent] if item["candidate_id"] == value.get("candidate_id")), None)
                        value.update({"policy": parent, "model_id": score["model_id"] if score else None})
                        upstream.append(value)
                    dump_lines(adaptation / f"ledger_{parent.lower()}_{cost}.jsonl", upstream)
    dump_lines(producer / "intentions.jsonl", intentions)
    dump_lines(producer / "decision_states.jsonl", decisions)
    diagnostics = audit.build_ev_diagnostics(intentions, decisions)
    dump_lines(producer / "ev_diagnostics.jsonl", diagnostics)
    summary = audit.expected_summary(sessions, intentions, decisions, books, helper)
    dump(producer / "summary.json", summary)

    payloads = [h1 / "candidates.jsonl", q3 / "candidates.jsonl", bridge / "candidates.jsonl", h1 / "coverage.json", q3 / "coverage.json", bridge / "coverage_overlay.json"]
    produced_upstream = [adaptation / "candidate_scores.jsonl", adaptation / "summary.json", *[adaptation / f"ledger_{parent.lower()}_{cost}.jsonl" for parent in audit.PARENTS for cost in audit.COSTS]]
    adaptation_manifest = {
        "schema": "weekly_context_adaptation_walkforward_v1",
        "status": "PASS_SEEN_DEVELOPMENT_GIVEN_BRIDGE_AND_FROZEN_AUTHORITIES",
        "flags": audit.ADAPTATION_FLAGS,
        "consumed_payloads": {str(path): file_pin(path) for path in payloads},
        "outputs": {path.name: file_pin(path, with_path=False) for path in produced_upstream},
    }
    dump(adaptation / "manifest.json", adaptation_manifest)
    monkeypatch.setattr(audit, "ADAPTATION_MANIFEST_SHA256", digest(adaptation / "manifest.json"))
    monkeypatch.setattr(audit, "ADAPTATION_MANIFEST_BYTES", (adaptation / "manifest.json").stat().st_size)
    upstream_audit = {"schema": "weekly_context_adaptation_audit_v1", "status": "PASS_INDEPENDENT_NUMERIC_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT", "flags": audit.ADAPTATION_AUDIT_FLAGS, "inputs": {"producer_manifest": file_pin(adaptation / "manifest.json")}}
    dump(audit.ADAPTATION_AUDIT, upstream_audit)
    dump(audit.ADAPTATION_EXIT, {"exit_code": 0})
    monkeypatch.setattr(audit, "ADAPTATION_AUDIT_SHA256", digest(audit.ADAPTATION_AUDIT))
    monkeypatch.setattr(audit, "ADAPTATION_EXIT_SHA256", digest(audit.ADAPTATION_EXIT))

    fake_code = tmp_path / "evaluate_weekly_prequential_ev_filter.py"
    fake_tests = tmp_path / "test_evaluate_weekly_prequential_ev_filter.py"
    fake_review = tmp_path / "review.md"
    for path in (fake_code, fake_tests, fake_review):
        path.write_text("sealed\n", encoding="utf-8")
    authorities = [adaptation / "manifest.json", audit.ADAPTATION_AUDIT, audit.ADAPTATION_EXIT, audit.DIAGNOSTIC, audit.ACCEPTANCE, audit.PRODUCER_REPLAY, audit.CONTRACT, fake_code, fake_tests, fake_review]
    all_inputs = [*authorities, *payloads, *produced_upstream]
    assert len(all_inputs) == 24
    outputs = {name: file_pin(producer / name, with_path=False) for name in audit.output_names()}
    producer_manifest = {"schema": "weekly_prequential_ev_filter_manifest_v1", "status": "COMPLETE_SEEN_DEVELOPMENT_NOT_PROMOTED", "inputs": {str(path): {"before": file_pin(path, with_path=False), "after": file_pin(path, with_path=False)} for path in all_inputs}, "outputs": outputs, "flags": audit.SUMMARY_FLAGS}
    dump(producer / "manifest.json", producer_manifest)
    dump(observer / "exit.json", {"exit_code": 0})
    result = audit.run(digest(producer / "manifest.json"), digest(observer / "exit.json"), digest(Path(audit.__file__)), tmp_path / "audit_output")
    assert result["status"] == "PASS_INDEPENDENT_PREQUENTIAL_EV_FILTER_RECONSTRUCTION"
    assert result["numeric"]["books_reconstructed"] == 12
    assert result["numeric"]["diagnostic_rows_reconstructed"] == 216
    assert any(not row["accepted"] and row["raw_winner_id"] for row in decisions)
    assert books[("FROZEN_CONTEXT182_CONTROL", "adverse")] != books[("FROZEN_CONTEXT182_FILTER", "adverse")]


def test_output_guard_rejects_input_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    producer = tmp_path / "producer"
    producer.mkdir()
    monkeypatch.setattr(audit, "PRODUCER_ROOT", producer)
    with pytest.raises(audit.PrequentialAuditError, match="nested in input root"):
        audit.guard_output(producer / "audit")
    observer = tmp_path / "observer"
    observer.mkdir()
    monkeypatch.setattr(audit, "PRODUCER_OBSERVER", observer)
    with pytest.raises(audit.PrequentialAuditError, match="nested in input root"):
        audit.guard_output(observer / "audit")


def test_bool_is_not_numeric_scenario_or_probability() -> None:
    candidate = {
        "candidate_id": "SPY:20260102:20260109:CALL", "ticker": "SPY", "entry_date": "20260102",
        "exit_date": "20260106", "expiration": "20260109", "strike": 100.0, "right": "CALL",
        "features": [], "decision_ask": 1.0, "source_pins": {}, "entry_ask": 1.0, "exit_bid": 1.0,
        "status": "OBSERVED_EXIT", "label_available_at": "2026-01-06T10:35:00-05:00",
        "scenario": True, "payoff_is_lower_bound": False, "net_base": 0.0, "net_adverse": 0.0,
        "entry_debit_base": 0.0, "entry_debit_adverse": 0.0,
    }
    with pytest.raises(audit.PrequentialAuditError, match="candidate scenario"):
        audit.normalize_candidate(candidate)
    candidate["scenario"] = 1
    score = {
        "candidate_id": candidate["candidate_id"], "entry_date": "20260102", "ev_adverse": 1.0,
        "ev_base": 1.0, "is_bridge": False, "model_id": "M", "p_cal": [True, 0.0, 0.0, 0.0, 0.0],
        "p_model": [0.2] * 5, "payoff_is_lower_bound": False, "policy": "FROZEN_CONTEXT182",
        "right": "CALL", "scenario": 1, "ticker": "SPY",
    }
    with pytest.raises(audit.PrequentialAuditError, match="finite p_cal value"):
        audit.normalize_score(score, candidate)
