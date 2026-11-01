"""Frozen equal-risk replay for H1 EVAL and partial Q3.

No model, transform, calibration, or source-data code is imported. Decisions and
scores are consumed from sealed artifacts; real execution requires an explicit flag.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
from typing import Any


BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
OUTPUT = BASE / "h2_equal_risk_frozen_01"
CONTRACT = Path(__file__).with_name("EQUAL_RISK_FROZEN_REPLAY_CONTRACT_20261101.md")
CONTRACT_SHA256 = "9c387e9bea74ba65777808b5ac5e5fccfdc2437645e7b301c15eab2d33bbeb7b"
BUDGET_CENTS = 500_000
STARTING_CASH = 100_000.0
COMMISSION = 1.30
TICKERS = ("SPY", "QQQ", "SPXW")
POLICIES = ("EV_TOP1_H2", "ALWAYS_CALL_H2", "ALWAYS_PUT_H2", "ALWAYS_ABSTAIN")
COSTS = ("base", "adverse")
BLOCKS = {
    "H1_EVAL": {
        "dataset": BASE / "h2_dataset_v2_01",
        "dataset_sha256": "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8",
        "scores": BASE / "h2_ev_v2_01",
        "scores_sha256": "54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96",
        "score_file": "candidate_scores.jsonl", "score_split": "EVAL",
        "first": "20260101", "last": "20260630", "last_entry": "20260630",
    },
    "Q3_PARTIAL": {
        "dataset": BASE / "h2_dataset_v2_extension_2026q3_partial_01",
        "dataset_sha256": "b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b",
        "scores": BASE / "h2_ev_frozen_extension_2026q3_partial_01",
        "scores_sha256": "7bd50a5a1fe5214df2c4281e785313f0fb016ca73d725d682788dcb78b283d8e",
        "score_file": "candidate_scores_extension.jsonl", "score_split": "Q3_PARTIAL_2026_SEEN_DEVELOPMENT",
        "first": "20260701", "last": "20260917", "last_entry": "20260915",
    },
}


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plain(path: Path, label: str, *, exists: bool = True) -> Path:
    path = Path(os.path.abspath(path))
    if exists:
        require(path.exists(), f"missing {label}")
    current = path if path.exists() else path.parent
    while True:
        if current.exists():
            attrs = getattr(current.lstat(), "st_file_attributes", 0)
            require(not current.is_symlink() and not attrs & 0x400, f"link/reparse {label}")
        if current.parent == current:
            break
        current = current.parent
    return path


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL {path}:{number}")
            row = json.loads(line)
            require(isinstance(row, dict), f"object required {path}:{number}")
            rows.append(row)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")


def verify(path: Path, pin: dict[str, Any], label: str) -> None:
    require(path.is_file() and path.stat().st_size == pin["bytes"] and sha256_file(path) == pin["sha256"], f"pin {label}")


def unit_risk_cents(ask: Any) -> int:
    value = (Decimal(str(ask)) + Decimal("0.02")) * Decimal(10_000) + Decimal(260)
    cents = int(value.to_integral_value(rounding=ROUND_CEILING))
    require(cents > 0, "non-positive unit risk")
    return cents


def fixed_quantity(decision_ask: Any) -> tuple[int, int]:
    risk = unit_risk_cents(decision_ask)
    return BUDGET_CENTS // risk, risk


def choose(rows: list[dict[str, Any]], policy: str) -> tuple[dict[str, Any] | None, str]:
    if policy == "ALWAYS_ABSTAIN":
        return None, "ABSTAIN"
    if policy in {"ALWAYS_CALL_H2", "ALWAYS_PUT_H2"}:
        right = "CALL" if policy == "ALWAYS_CALL_H2" else "PUT"
        matches = [row for row in rows if row["right"] == right]
        require(len(matches) <= 1, "multiple fixed-side candidates")
        return (matches[0], "FIXED_CONTROL") if matches else (None, "NO_SERIES")
    require(policy == "EV_TOP1_H2", "unknown policy")
    if not rows:
        return None, "NO_SERIES"
    best = max(float(row["_ev_adverse"]) for row in rows)
    matches = [row for row in rows if float(row["_ev_adverse"]) == best]
    if best <= 0:
        return None, "EV_NOT_POSITIVE"
    return (matches[0], "EV_TOP1") if len(matches) == 1 else (None, "EV_TIE_WAIT")


def paired_event(event: str, day: str, ticker: str, cost: str, **fields: Any) -> dict[str, Any]:
    return {"event": event, "date": day, "ticker": ticker, "cost": cost, **fields}


def replay_pair(
    rows: list[dict[str, Any]], coverage: dict[str, Any], sessions: list[str], last_entry: str,
    policy: str, *, starting_cash: float = STARTING_CASH,
) -> dict[str, list[dict[str, Any]]]:
    by_identity: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_identity[(row["entry_date"], row["ticker"])].append(row)
    cover = {(row["ticker"], row["entry_date"]): row for row in coverage["rows"]}
    opened: dict[str, tuple[dict[str, Any], int, int, int]] = {}
    cash = {cost: float(starting_cash) for cost in COSTS}
    premium_reserved = {cost: 0.0 for cost in COSTS}
    exit_fee_obligation = {cost: 0.0 for cost in COSTS}
    ledgers = {cost: [] for cost in COSTS}
    for day in sessions:
        for ticker in TICKERS:
            if ticker not in opened or opened[ticker][0]["exit_date"] != day:
                continue
            row, qty, decision_risk, entry_risk = opened.pop(ticker)
            bid = 0.0 if row["exit_bid"] is None else float(row["exit_bid"])
            for cost, slip in (("base", 0.01), ("adverse", 0.02)):
                principal = qty * (float(row["entry_ask"]) + slip) * 100
                credit = qty * (max(bid - slip, 0.0) * 100 - COMMISSION)
                cash[cost] += credit
                premium_reserved[cost] -= principal
                exit_fee_obligation[cost] -= qty * COMMISSION
                net = qty * float(row[f"net_{cost}"])
                require(math.isclose(credit - qty * float(row[f"entry_debit_{cost}"]), net, abs_tol=1e-6), "quantity net")
                ledgers[cost].append(paired_event(
                    "EXIT", day, ticker, cost, candidate_id=row["candidate_id"], right=row["right"],
                    status=row["status"], entry_date=row["entry_date"], quantity=qty,
                    decision_unit_risk_cents=decision_risk, entry_unit_risk_cents=entry_risk,
                    net_usd=net, cash=cash[cost], premium_reserved=premium_reserved[cost],
                    exit_fee_obligation=exit_fee_obligation[cost], equity_realized=cash[cost] + premium_reserved[cost],
                    realized_delta=net + qty * COMMISSION, principal=principal,
                ))
        for ticker in TICKERS:
            if day > last_entry:
                continue
            candidates = by_identity.get((day, ticker), [])
            if ticker in opened:
                for cost in COSTS:
                    ledgers[cost].append(paired_event("WAIT", day, ticker, cost, reason="OPEN_POSITION"))
                continue
            if not candidates:
                item = cover[(ticker, day)]
                for cost in COSTS:
                    ledgers[cost].append(paired_event("NO_OPPORTUNITY", day, ticker, cost, reason=item.get("reason") or item["status"]))
                continue
            if policy in {"ALWAYS_CALL_H2", "ALWAYS_PUT_H2"}:
                right = "CALL" if policy == "ALWAYS_CALL_H2" else "PUT"
                if not any(row["right"] == right for row in candidates):
                    for cost in COSTS:
                        ledgers[cost].append(paired_event("NO_OPPORTUNITY", day, ticker, cost, reason=f"{right}_SIDE_UNAVAILABLE"))
                    continue
            selected, reason = choose(candidates, policy)
            if selected is None:
                for cost in COSTS:
                    ledgers[cost].append(paired_event("WAIT", day, ticker, cost, reason=reason))
                continue
            qty, decision_risk = fixed_quantity(selected["decision_ask"])
            common = {"candidate_id": selected["candidate_id"], "quantity": qty, "decision_unit_risk_cents": decision_risk}
            if qty < 1:
                for cost in COSTS:
                    ledgers[cost].append(paired_event("NO_FILL", day, ticker, cost, reason="DECISION_RISK_BUDGET", **common))
                continue
            if selected["status"] == "NO_FILL":
                for cost in COSTS:
                    ledgers[cost].append(paired_event("NO_FILL", day, ticker, cost, reason="ENTRY_QUOTE", **common))
                continue
            entry_risk = unit_risk_cents(selected["entry_ask"])
            common["entry_unit_risk_cents"] = entry_risk
            if qty * entry_risk > BUDGET_CENTS:
                for cost in COSTS:
                    ledgers[cost].append(paired_event("NO_FILL", day, ticker, cost, reason="ENTRY_RISK_BUDGET", **common))
                continue
            debit = {cost: qty * float(selected[f"entry_debit_{cost}"]) for cost in COSTS}
            new_exit_fee = qty * COMMISSION
            affordable = all(cash[cost] - exit_fee_obligation[cost] >= debit[cost] + new_exit_fee for cost in COSTS)
            if not affordable:
                for cost in COSTS:
                    ledgers[cost].append(paired_event("CAPITAL_BLOCKED", day, ticker, cost, reason="CAPITAL", **common))
                continue
            opened[ticker] = (selected, qty, decision_risk, entry_risk)
            for cost, slip in (("base", 0.01), ("adverse", 0.02)):
                cash[cost] -= debit[cost]
                principal = qty * (float(selected["entry_ask"]) + slip) * 100
                premium_reserved[cost] += principal
                exit_fee_obligation[cost] += new_exit_fee
                ledgers[cost].append(paired_event(
                    "ENTRY", day, ticker, cost, candidate_id=selected["candidate_id"], right=selected["right"],
                    exit_date=selected["exit_date"], selection_reason=reason, quantity=qty,
                    decision_unit_risk_cents=decision_risk, decision_budget_used_cents=qty * decision_risk,
                    entry_unit_risk_cents=entry_risk, entry_budget_used_cents=qty * entry_risk,
                    ev_base=selected["_ev_base"], ev_adverse=selected["_ev_adverse"], cash=cash[cost],
                    premium_reserved=premium_reserved[cost], exit_fee_obligation=exit_fee_obligation[cost],
                    equity_realized=cash[cost] + premium_reserved[cost], realized_delta=-qty * COMMISSION,
                    principal=principal,
                ))
    require(not opened, "positions remain open")
    for cost in COSTS:
        require(abs(premium_reserved[cost]) <= 1e-7 and abs(exit_fee_obligation[cost]) <= 1e-7, f"reserves close {cost}")
        net = math.fsum(row["net_usd"] for row in ledgers[cost] if row["event"] == "EXIT")
        require(math.isclose(cash[cost], starting_cash + net, abs_tol=1e-6), f"cash reconciliation {cost}")
    return ledgers


def book_metrics(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    exits = [row for row in ledger if row["event"] == "EXIT"]
    entries = [row for row in ledger if row["event"] == "ENTRY"]
    values = [float(row["net_usd"]) for row in exits]
    gains = math.fsum(value for value in values if value > 0)
    losses = -math.fsum(value for value in values if value < 0)
    equity, peak, drawdown = STARTING_CASH, STARTING_CASH, 0.0
    months, tickers = defaultdict(float), {ticker: 0.0 for ticker in TICKERS}
    for row in ledger:
        if row["event"] in {"ENTRY", "EXIT"}:
            equity += float(row["realized_delta"])
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        if row["event"] == "EXIT":
            months[row["date"][:6]] += float(row["net_usd"])
            tickers[row["ticker"]] += float(row["net_usd"])
    quantities = [int(row["quantity"]) for row in entries]
    return {
        "trades": len(exits), "net_usd": math.fsum(values),
        "profit_factor": gains / losses if losses else (None if gains == 0 else "Infinity"),
        "realized_max_drawdown_usd": drawdown, "months_observed": len(months),
        "positive_months": sum(value > 0 for value in months.values()), "monthly_net_usd": dict(sorted(months.items())),
        "ticker_net_usd": tickers, "quantity_total": sum(quantities),
        "quantity_max": max(quantities) if quantities else None,
        "quantity_median": statistics.median(quantities) if quantities else None,
        "max_premium_reserved": max((float(row.get("premium_reserved", 0)) for row in ledger), default=0.0),
        "max_decision_budget_used_cents": max((int(row.get("decision_budget_used_cents", 0)) for row in entries), default=0),
        "max_entry_budget_used_cents": max((int(row.get("entry_budget_used_cents", 0)) for row in entries), default=0),
        "no_fill_by_reason": {reason: sum(row["event"] == "NO_FILL" and row["reason"] == reason for row in ledger) for reason in ("DECISION_RISK_BUDGET", "ENTRY_RISK_BUDGET", "ENTRY_QUOTE")},
        "capital_blocked": sum(row["event"] == "CAPITAL_BLOCKED" for row in ledger),
        "wait": sum(row["event"] == "WAIT" for row in ledger),
        "no_opportunity": sum(row["event"] == "NO_OPPORTUNITY" for row in ledger),
        "missing_exit": sum(row.get("status") in {"MISSING_EXIT_QUOTE", "MISSING_EXIT_SOURCE"} for row in exits),
        "capacity_assumption": "full fill at stored quote; no volume or partial-fill simulation",
    }


def join_scores(candidates: list[dict[str, Any]], scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    score_index = {row["candidate_id"]: row for row in scores}
    require(len(score_index) == len(scores), "duplicate score")
    output = []
    for candidate in candidates:
        score = score_index.get(candidate["candidate_id"])
        require(score is not None, "missing score")
        row = dict(candidate)
        row["_ev_base"], row["_ev_adverse"] = score["ev_base"], score["ev_adverse"]
        output.append(row)
    require(len(output) == len(scores), "candidate/score universe")
    return output


def filtered_calendar(coverage: dict[str, Any], first: str, last: str) -> tuple[dict[str, Any], list[str]]:
    calendar = [row for row in coverage["calendar"] if first <= row["date"] <= last]
    rows = [row for row in coverage["rows"] if first <= row["entry_date"] <= last]
    dates = {ticker: [row["date"] for row in calendar if row["ticker"] == ticker] for ticker in TICKERS}
    require(dates["SPY"] == sorted(set(dates["SPY"])) and all(dates[ticker] == dates["SPY"] for ticker in TICKERS), "common calendar")
    return {"calendar": calendar, "rows": rows}, dates["SPY"]


def load_block(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], list[str], dict[Path, dict[str, Any]]]:
    dataset_root, scores_root = plain(config["dataset"], "dataset"), plain(config["scores"], "scores")
    dataset_manifest_path, scores_manifest_path = dataset_root / "manifest.json", scores_root / "manifest.json"
    require(sha256_file(dataset_manifest_path) == config["dataset_sha256"], "dataset manifest")
    require(sha256_file(scores_manifest_path) == config["scores_sha256"], "scores manifest")
    dataset_manifest, scores_manifest = read_json(dataset_manifest_path), read_json(scores_manifest_path)
    candidates_path, coverage_path, score_path = dataset_root / "candidates.jsonl", dataset_root / "coverage.json", scores_root / config["score_file"]
    verify(candidates_path, dataset_manifest["files"]["candidates.jsonl"], "candidates")
    verify(coverage_path, dataset_manifest["files"]["coverage.json"], "coverage")
    verify(score_path, scores_manifest["outputs"][config["score_file"]], "scores")
    candidates, scores = read_jsonl(candidates_path), read_jsonl(score_path)
    if config["score_split"] == "EVAL":
        ids = {row["candidate_id"] for row in scores if row["split"] == "EVAL"}
        candidates, scores = [row for row in candidates if row["candidate_id"] in ids], [row for row in scores if row["candidate_id"] in ids]
    else:
        require(all(row["split"] == config["score_split"] for row in scores), "Q3 score split")
    coverage, sessions = filtered_calendar(read_json(coverage_path), config["first"], config["last"])
    payloads = {
        dataset_manifest_path: {"bytes": dataset_manifest_path.stat().st_size, "sha256": config["dataset_sha256"]},
        scores_manifest_path: {"bytes": scores_manifest_path.stat().st_size, "sha256": config["scores_sha256"]},
        candidates_path: dataset_manifest["files"]["candidates.jsonl"], coverage_path: dataset_manifest["files"]["coverage.json"],
        score_path: scores_manifest["outputs"][config["score_file"]],
    }
    return join_scores(candidates, scores), coverage, sessions, payloads


def execute(output: Path = OUTPUT) -> dict[str, Any]:
    require(sha256_file(CONTRACT) == CONTRACT_SHA256, "contract pin")
    output = plain(output, "output", exists=False)
    require(not output.exists(), "immutable output exists")
    all_ledgers, summary, payloads = {}, {}, {}
    for block, config in BLOCKS.items():
        rows, coverage, sessions, pins = load_block(config)
        payloads.update(pins)
        all_ledgers[block], summary[block] = {}, {}
        for policy in POLICIES:
            books = replay_pair(rows, coverage, sessions, config["last_entry"], policy)
            all_ledgers[block][policy] = books
            summary[block][policy] = {cost: book_metrics(books[cost]) for cost in COSTS}
    for path, pin in payloads.items():
        verify(path, pin, f"closing {path.name}")
    output.mkdir(parents=True, exist_ok=False)
    for block, policies in all_ledgers.items():
        for policy, books in policies.items():
            for cost, ledger in books.items():
                write_jsonl(output / f"ledger_equal_risk_{block.lower()}_{policy.lower()}_{cost}.jsonl", ledger)
    report = {
        "schema": "weekly_h2_equal_risk_frozen_replay_v1", "status": "COMPLETE_SEEN_DEVELOPMENT_DESCRIPTIVE",
        "budget_cents": BUDGET_CENTS, "blocks": summary,
        "comparison": "separate blocks only; no H1+Q3 combined book; no winner",
        "flags": {"fit_performed": False, "recalibration_performed": False, "selection_changed": False, "promotion_approved": False},
    }
    write_json(output / "summary.json", report)
    outputs = {path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in sorted(output.iterdir())}
    write_json(output / "manifest.json", {
        "schema": "weekly_h2_equal_risk_frozen_manifest_v1",
        "inputs": {block: {"dataset_manifest_sha256": config["dataset_sha256"], "scores_manifest_sha256": config["scores_sha256"]} for block, config in BLOCKS.items()},
        "implementation": {"replay_equal_risk_frozen.py": sha256_file(Path(__file__)), CONTRACT.name: CONTRACT_SHA256},
        "outputs": outputs, "flags": report["flags"],
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen equal-risk replay")
    parser.add_argument("--execute-reviewed-replay", action="store_true")
    args = parser.parse_args()
    if not args.execute_reviewed_replay:
        parser.error("execution requires --execute-reviewed-replay")
    execute()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
