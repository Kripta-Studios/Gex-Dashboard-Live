from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
from typing import Any, Iterable


DATASET_ROOT = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101\h2_dataset_v2_01")
EVAL_ROOT = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101\h2_ev_v2_01")
OUTPUT_ROOT = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101\h2_ev_robustness_diagnostic_01")
DATASET_MANIFEST_SHA256 = "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8"
EVAL_MANIFEST_SHA256 = "54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96"
CONTRACT_SHA256 = "a9488cda35b1d50303113b041d7be80452d47b8d4d7fdbe6097a98d762aaf85c"
SPEC_SHA256 = "dcc1d1fdb22dbe3974da765f8b29b3dc9cd5d5e184c1b5ed5209578f9470ce28"
CONTRACT_PATH = Path(__file__).with_name("WEEKLY_H2_EV_ROBUSTNESS_DIAGNOSTIC_CONTRACT_20261101.md")
SPEC_PATH = Path(__file__).with_name("WEEKLY_H2_EV_ROBUSTNESS_DIAGNOSTIC_SPEC_20261101.md")
SLIPPAGE_POINTS = (0.02, 0.05, 0.10, 0.25, 0.50, 1.00)
COMMISSION_PER_SIDE = 1.30
STARTING_CASH = 100_000.0
TICKERS = ("SPY", "QQQ", "SPXW")
EVAL_START, EVAL_END = "20260101", "20260630"
BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES, BLOCK_LENGTH = 20261101, 10_000, 5


class DiagnosticError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosticError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_ids_sha256(ids: Iterable[str]) -> str:
    payload = "".join(f"{value}\n" for value in sorted(ids)).encode()
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL line {path}:{line_number}")
            row = json.loads(line)
            require(isinstance(row, dict), f"object required {path}:{line_number}")
            rows.append(row)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def verify_pin(path: Path, pin: dict[str, Any], label: str) -> None:
    require(path.is_file() and not path.is_symlink(), f"missing/non-plain {label}")
    require(path.stat().st_size == pin["bytes"] and sha256_file(path) == pin["sha256"], f"pin mismatch {label}")


def assert_plain_path(path: Path, label: str, *, must_exist: bool = True) -> Path:
    path = Path(os.path.abspath(path))
    if must_exist:
        require(path.exists(), f"missing {label}")
    current = path if path.exists() else path.parent
    while True:
        if current.exists():
            attributes = getattr(current.lstat(), "st_file_attributes", 0)
            require(not current.is_symlink() and not (attributes & 0x400), f"link/reparse in {label}")
        if current.parent == current:
            break
        current = current.parent
    return path


def exclusive_output_path(path: Path) -> Path:
    path = assert_plain_path(path, "output", must_exist=False)
    require(not path.exists(), f"immutable output exists: {path}")
    return path


def recompute_cash(candidate: dict[str, Any], slippage_points: float) -> dict[str, float]:
    require(slippage_points in SLIPPAGE_POINTS, "undeclared slippage point")
    ask = float(candidate["entry_ask"])
    exit_bid = 0.0 if candidate["exit_bid"] is None else float(candidate["exit_bid"])
    require(ask >= 0 and exit_bid >= 0, "negative quote")
    debit = 100.0 * (ask + slippage_points) + COMMISSION_PER_SIDE
    credit = 100.0 * max(exit_bid - slippage_points, 0.0) - COMMISSION_PER_SIDE
    return {"entry_debit": debit, "exit_credit": credit, "net_usd": credit - debit}


def fixed_trades(candidates: list[dict[str, Any]], ledger: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_index = {}
    for row in candidates:
        candidate_id = row.get("candidate_id")
        require(isinstance(candidate_id, str) and candidate_id not in candidate_index, "duplicate/invalid candidate")
        candidate_index[candidate_id] = row
    entries, exits = {}, {}
    for event in ledger:
        if event.get("event") not in {"ENTRY", "EXIT"}:
            continue
        candidate_id = event.get("candidate_id")
        target = entries if event["event"] == "ENTRY" else exits
        require(isinstance(candidate_id, str) and candidate_id not in target, f"duplicate {event['event']}")
        target[candidate_id] = event
    require(set(entries) == set(exits) and bool(entries), "ENTRY/EXIT universe mismatch")
    trades = []
    for candidate_id in sorted(entries):
        require(candidate_id in candidate_index, "ledger candidate absent")
        candidate, entry, exit_event = candidate_index[candidate_id], entries[candidate_id], exits[candidate_id]
        require(candidate.get("status") != "NO_FILL" and candidate.get("entry_ask") is not None, "non-filled fixed trade")
        require(entry.get("date") == candidate.get("entry_date") and exit_event.get("date") == candidate.get("exit_date"), "trade dates")
        require(entry.get("ticker") == exit_event.get("ticker") == candidate.get("ticker"), "trade ticker")
        baseline = recompute_cash(candidate, 0.02)
        require(math.isclose(baseline["net_usd"], float(candidate["net_adverse"]), abs_tol=1e-8), "candidate baseline net")
        require(math.isclose(baseline["net_usd"], float(exit_event["net_usd"]), abs_tol=1e-8), "ledger baseline net")
        require(math.isclose(baseline["entry_debit"], float(candidate["entry_debit_adverse"]), abs_tol=1e-8), "baseline debit")
        trades.append({
            "candidate_id": candidate_id, "ticker": candidate["ticker"], "right": candidate["right"],
            "entry_date": candidate["entry_date"], "exit_date": candidate["exit_date"],
            "entry_ask": candidate["entry_ask"], "exit_bid": candidate["exit_bid"],
            "status": candidate["status"], "entry_debit_adverse": candidate["entry_debit_adverse"],
            "net_adverse": candidate["net_adverse"],
        })
    return trades, ledger


def profit_factor(values: list[float]) -> float | str | None:
    gains = sum(value for value in values if value > 0)
    losses = -sum(value for value in values if value < 0)
    return gains / losses if losses else (None if gains == 0 else "Infinity")


def sweep_metrics(trades: list[dict[str, Any]], ledger: list[dict[str, Any]], slippage_points: float) -> dict[str, Any]:
    cash = {trade["candidate_id"]: recompute_cash(trade, slippage_points) for trade in trades}
    net_values = [cash[trade["candidate_id"]]["net_usd"] for trade in trades]
    ticker = {name: 0.0 for name in TICKERS}
    monthly = {f"2026{month:02d}": 0.0 for month in range(1, 7)}
    observed_months = set()
    for trade in trades:
        net = cash[trade["candidate_id"]]["net_usd"]
        ticker[trade["ticker"]] += net
        monthly[trade["exit_date"][:6]] += net
        observed_months.add(trade["exit_date"][:6])
    equity, curve = STARTING_CASH, [STARTING_CASH]
    for event in ledger:
        if event.get("event") == "ENTRY":
            equity -= COMMISSION_PER_SIDE
            curve.append(equity)
        elif event.get("event") == "EXIT":
            equity += cash[event["candidate_id"]]["net_usd"] + COMMISSION_PER_SIDE
            curve.append(equity)
    running_peak, max_drawdown = curve[0], 0.0
    for value in curve:
        running_peak = max(running_peak, value)
        max_drawdown = max(max_drawdown, running_peak - value)
    require(math.isclose(equity, STARTING_CASH + sum(net_values), abs_tol=1e-6), "sweep cash reconciliation")
    return {
        "slippage_points_per_option_per_side": slippage_points,
        "premium_cash_multiplier": 100,
        "trades": len(trades), "net_usd": sum(net_values),
        "gross_gains_usd": sum(value for value in net_values if value > 0),
        "gross_losses_usd": -sum(value for value in net_values if value < 0),
        "profit_factor": profit_factor(net_values), "realized_max_drawdown_usd": max_drawdown,
        "ticker_net_usd": ticker, "exit_month_net_usd": monthly,
        "missing_exit_lower_bounds": sum(trade["exit_bid"] is None for trade in trades),
        "months_observed": len(observed_months),
        "positive_months": sum(monthly[month] > 0 for month in observed_months),
    }


def equal_risk_diagnostic(trades: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, list[tuple[float, float]]] = {ticker: [] for ticker in TICKERS}
    for trade in trades:
        debit = float(trade["entry_debit_adverse"])
        require(debit > 0, "non-positive adverse debit")
        by_ticker[trade["ticker"]].append((float(trade["net_adverse"]) / debit, debit))
    result = {}
    for ticker, pairs in by_ticker.items():
        require(bool(pairs), f"ticker has no trades: {ticker}")
        returns = [pair[0] for pair in pairs]
        total_debit = sum(pair[1] for pair in pairs)
        total_net = sum(pair[0] * pair[1] for pair in pairs)
        result[ticker] = {
            "n": len(pairs), "mean_return_on_adverse_debit": statistics.fmean(returns),
            "median_return_on_adverse_debit": statistics.median(returns),
            "aggregate_debit_compensated_return": total_net / total_debit,
            "total_net_usd": total_net, "total_adverse_debit_usd": total_debit,
        }
    return {
        "denominator": "sealed_entry_debit_adverse_per_trade_s_0.02",
        "tickers": result,
        "equal_weight_ticker_average": statistics.fmean(
            result[ticker]["aggregate_debit_compensated_return"] for ticker in TICKERS
        ),
        "executable_portfolio": False,
        "limitation": "fractional sizing diagnostic; capital path ignored; no profitability claim",
    }


def concentration_diagnostic(trades: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(trades, key=lambda trade: (-float(trade["net_adverse"]), trade["exit_date"], trade["candidate_id"]))
    drop = []
    for count in (1, 3, 5):
        removed = ordered[:count]
        retained = ordered[count:]
        drop.append({
            "drop_count": count, "removed_candidate_ids": [trade["candidate_id"] for trade in removed],
            "removed_net_usd": sum(float(trade["net_adverse"]) for trade in removed),
            "remaining_trades": len(retained), "remaining_net_usd": sum(float(trade["net_adverse"]) for trade in retained),
        })
    leave_month = []
    for month in (f"2026{value:02d}" for value in range(1, 7)):
        removed = [trade for trade in trades if trade["exit_date"].startswith(month)]
        retained = [trade for trade in trades if not trade["exit_date"].startswith(month)]
        leave_month.append({
            "excluded_exit_month": month, "removed_trades": len(removed),
            "removed_candidate_ids": sorted(trade["candidate_id"] for trade in removed),
            "removed_net_usd": sum(float(trade["net_adverse"]) for trade in removed),
            "remaining_trades": len(retained), "remaining_net_usd": sum(float(trade["net_adverse"]) for trade in retained),
        })
    return {
        "drop_top_gains": drop, "leave_one_exit_month_out": leave_month,
        "interpretation": "mechanical sensitivity only; no reselection or alternative policy",
    }


def percentile_type7(sorted_values: list[float], probability: float) -> float:
    require(bool(sorted_values) and 0 <= probability <= 1, "percentile input")
    position = (len(sorted_values) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def block_bootstrap(
    trades: list[dict[str, Any]], sessions: list[str], *,
    seed: int = BOOTSTRAP_SEED, resamples: int = BOOTSTRAP_RESAMPLES, block_length: int = BLOCK_LENGTH,
) -> dict[str, Any]:
    require(sessions == sorted(set(sessions)) and bool(sessions), "ordered unique sessions")
    require(block_length > 0 and resamples > 0, "bootstrap configuration")
    daily = {session: 0.0 for session in sessions}
    for trade in trades:
        require(trade["entry_date"] in daily, "trade entry outside bootstrap calendar")
        daily[trade["entry_date"]] += float(trade["net_adverse"])
    values = [daily[session] for session in sessions]
    rng = random.Random(seed)
    totals = []
    for _ in range(resamples):
        sampled = []
        while len(sampled) < len(values):
            start = rng.randrange(len(values))
            sampled.extend(values[(start + offset) % len(values)] for offset in range(block_length))
        totals.append(sum(sampled[: len(values)]))
    ordered = sorted(totals)
    return {
        "status": "COMPLETE_EXPLORATORY_EMPIRICAL_BOOTSTRAP",
        "unit": "official_entry_session_all_tickers_aggregated", "zero_pnl_sessions_included": True,
        "sessions": len(sessions), "zero_pnl_sessions": sum(value == 0 for value in values),
        "block_method": "circular_moving_blocks", "block_length_sessions": block_length,
        "seed": seed, "resamples": resamples, "statistic": "total_h1_pnl_usd",
        "observed_total_usd": sum(values), "economic_zero_reference_usd": 0.0,
        "bootstrap_mean_usd": statistics.fmean(totals), "bootstrap_median_usd": statistics.median(totals),
        "empirical_percentile_interval_type7_usd": {
            "low_2_5": percentile_type7(ordered, 0.025), "high_97_5": percentile_type7(ordered, 0.975)
        },
        "assumptions": ["approximate stationarity", "relevant temporal dependence bounded by five sessions"],
        "interpretation": "exploratory empirical interval; not a null distribution or statistical test",
        "p_value": None,
    }


def common_eval_sessions(coverage: dict[str, Any]) -> list[str]:
    calendar = coverage.get("calendar")
    require(isinstance(calendar, list), "coverage calendar")
    by_ticker = {ticker: [] for ticker in TICKERS}
    for row in calendar:
        require(isinstance(row, dict) and row.get("ticker") in TICKERS, "calendar row")
        day = row.get("date")
        if isinstance(day, str) and EVAL_START <= day <= EVAL_END:
            by_ticker[row["ticker"]].append(day)
    for ticker, dates in by_ticker.items():
        require(dates == sorted(dates), f"unordered EVAL calendar {ticker}")
        require(len(dates) == len(set(dates)), f"duplicate EVAL calendar identity {ticker}")
    reference = by_ticker[TICKERS[0]]
    require(bool(reference) and all(by_ticker[ticker] == reference for ticker in TICKERS), "non-common EVAL calendars")
    return list(reference)


def bootstrap_or_omitted(trades: list[dict[str, Any]], coverage: dict[str, Any]) -> dict[str, Any]:
    try:
        sessions = common_eval_sessions(coverage)
    except DiagnosticError as exc:
        return {
            "status": "OMITTED_FAIL_CLOSED",
            "reason": str(exc),
            "interpretation": "calendar ambiguity was not replaced with independent-trade resampling",
            "p_value": None,
        }
    return block_bootstrap(trades, sessions)


def load_real_inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    require(sha256_file(CONTRACT_PATH) == CONTRACT_SHA256 and sha256_file(SPEC_PATH) == SPEC_SHA256, "local document pins")
    dataset_manifest_path = assert_plain_path(DATASET_ROOT / "manifest.json", "dataset manifest")
    eval_manifest_path = assert_plain_path(EVAL_ROOT / "manifest.json", "evaluation manifest")
    require(sha256_file(dataset_manifest_path) == DATASET_MANIFEST_SHA256, "dataset manifest external pin")
    require(sha256_file(eval_manifest_path) == EVAL_MANIFEST_SHA256, "evaluation manifest external pin")
    dataset_manifest, eval_manifest = read_json(dataset_manifest_path), read_json(eval_manifest_path)
    require(dataset_manifest.get("schema") == "weekly_h2_dataset_manifest_v2", "dataset manifest schema")
    require(eval_manifest.get("schema") == "weekly_h2_ev_manifest_v1", "eval manifest schema")
    require(eval_manifest["inputs"]["external_manifest_sha256"] == DATASET_MANIFEST_SHA256, "cross-manifest binding")
    candidate_path = assert_plain_path(DATASET_ROOT / "candidates.jsonl", "candidates")
    coverage_path = assert_plain_path(DATASET_ROOT / "coverage.json", "coverage")
    summary_path = assert_plain_path(EVAL_ROOT / "summary.json", "summary")
    ledger_name = "ledger_ev_top1_h2_eval_adverse.jsonl"
    ledger_path = assert_plain_path(EVAL_ROOT / ledger_name, "ledger")
    verify_pin(candidate_path, dataset_manifest["files"]["candidates.jsonl"], "candidates")
    verify_pin(coverage_path, dataset_manifest["files"]["coverage.json"], "coverage")
    verify_pin(summary_path, eval_manifest["outputs"]["summary.json"], "summary")
    verify_pin(ledger_path, eval_manifest["outputs"][ledger_name], "ledger")
    candidates = read_jsonl(candidate_path)
    coverage, summary, ledger = read_json(coverage_path), read_json(summary_path), read_jsonl(ledger_path)
    return candidates, ledger, coverage, summary, {
        "dataset_manifest": dataset_manifest, "eval_manifest": eval_manifest,
        "paths": {"candidates": candidate_path, "coverage": coverage_path, "summary": summary_path, "ledger": ledger_path},
    }


def build_diagnostic(
    candidates: list[dict[str, Any]], ledger: list[dict[str, Any]], coverage: dict[str, Any], summary: dict[str, Any]
) -> dict[str, Any]:
    trades, ledger = fixed_trades(candidates, ledger)
    baseline = sweep_metrics(trades, ledger, 0.02)
    expected = summary["economics"]["EV_TOP1_H2"]["EVAL"]["adverse"]["pooled"]
    require(baseline["trades"] == expected["trades"], "baseline trade count")
    require(math.isclose(baseline["net_usd"], float(expected["net_usd"]), abs_tol=1e-6), "baseline summary net")
    require(math.isclose(baseline["realized_max_drawdown_usd"], float(expected["realized_max_drawdown_usd"]), abs_tol=1e-6), "baseline summary drawdown")
    require(baseline["profit_factor"] == expected["profit_factor"] or math.isclose(float(baseline["profit_factor"]), float(expected["profit_factor"]), abs_tol=1e-12), "baseline PF")
    require(baseline["missing_exit_lower_bounds"] == expected["missing_exit"], "baseline missing exits")
    require(baseline["months_observed"] == expected["months_observed"], "baseline months observed")
    require(baseline["positive_months"] == expected["positive_months"], "baseline positive months")
    for ticker in TICKERS:
        ticker_expected = summary["economics"]["EV_TOP1_H2"]["EVAL"]["adverse"]["tickers"][ticker]
        require(math.isclose(baseline["ticker_net_usd"][ticker], float(ticker_expected["net_usd"]), abs_tol=1e-6), f"baseline ticker {ticker}")
    return {
        "schema": "weekly_h2_ev_robustness_diagnostic_v1",
        "status": "COMPLETE_EXPLORATORY_DIAGNOSTIC_NOT_INDEPENDENTLY_AUDITED",
        "scope": "EV_TOP1_H2_EVAL_2026H1_FIXED_DECISIONS",
        "fixed_trade_count": len(trades), "fixed_candidate_ids_sha256": canonical_ids_sha256(trade["candidate_id"] for trade in trades),
        "baseline_reconciliation": baseline,
        "slippage_sweep": [sweep_metrics(trades, ledger, value) for value in SLIPPAGE_POINTS],
        "equal_risk_diagnostic": equal_risk_diagnostic(trades),
        "concentration": concentration_diagnostic(trades),
        "block_bootstrap": bootstrap_or_omitted(trades, coverage),
        "limitations": [
            "fixed decisions; no reselection, refit, replay, ticker rescue, or threshold search",
            "equal-risk section is not an executable portfolio",
            "bootstrap interval is exploratory and assumes stationarity/dependence bounded by five sessions",
            "2026 H1 is seen development; missing exits remain total-loss lower bounds",
        ],
        "flags": {
            "descriptive_only": True, "development_seen": True, "selection_performed": False,
            "refit_performed": False, "independently_audited": False, "promotion_approved": False,
        },
    }


def execute() -> dict[str, Any]:
    output_root = exclusive_output_path(OUTPUT_ROOT)
    candidates, ledger, coverage, summary, authority = load_real_inputs()
    diagnostic = build_diagnostic(candidates, ledger, coverage, summary)
    # Rehash before the first write.
    dataset_manifest = authority["dataset_manifest"]
    eval_manifest = authority["eval_manifest"]
    verify_pin(authority["paths"]["candidates"], dataset_manifest["files"]["candidates.jsonl"], "closing candidates")
    verify_pin(authority["paths"]["coverage"], dataset_manifest["files"]["coverage.json"], "closing coverage")
    verify_pin(authority["paths"]["summary"], eval_manifest["outputs"]["summary.json"], "closing summary")
    verify_pin(authority["paths"]["ledger"], eval_manifest["outputs"]["ledger_ev_top1_h2_eval_adverse.jsonl"], "closing ledger")
    output_root.mkdir(parents=True, exist_ok=False)
    diagnostic_path = output_root / "diagnostic.json"
    write_json(diagnostic_path, diagnostic)
    # Rehash again after the diagnostic write, before publishing the manifest.
    require(sha256_file(DATASET_ROOT / "manifest.json") == DATASET_MANIFEST_SHA256, "dataset manifest changed")
    require(sha256_file(EVAL_ROOT / "manifest.json") == EVAL_MANIFEST_SHA256, "evaluation manifest changed")
    for name, path in authority["paths"].items():
        source = dataset_manifest["files"] if name in {"candidates", "coverage"} else eval_manifest["outputs"]
        key = {"candidates": "candidates.jsonl", "coverage": "coverage.json", "summary": "summary.json", "ledger": "ledger_ev_top1_h2_eval_adverse.jsonl"}[name]
        verify_pin(path, source[key], f"post-write {name}")
    manifest = {
        "schema": "weekly_h2_ev_robustness_manifest_v1",
        "status": "COMPLETE_EXPLORATORY_DIAGNOSTIC_NOT_INDEPENDENTLY_AUDITED",
        "inputs": {
            "dataset_manifest_sha256": DATASET_MANIFEST_SHA256, "evaluation_manifest_sha256": EVAL_MANIFEST_SHA256,
            "candidates.jsonl": dataset_manifest["files"]["candidates.jsonl"],
            "coverage.json": dataset_manifest["files"]["coverage.json"],
            "summary.json": eval_manifest["outputs"]["summary.json"],
            "ledger_ev_top1_h2_eval_adverse.jsonl": eval_manifest["outputs"]["ledger_ev_top1_h2_eval_adverse.jsonl"],
        },
        "implementation_pins": {
            "diagnose_weekly_h2_ev_robustness.py": sha256_file(Path(__file__)),
            CONTRACT_PATH.name: CONTRACT_SHA256, SPEC_PATH.name: SPEC_SHA256,
        },
        "outputs": {"diagnostic.json": {"bytes": diagnostic_path.stat().st_size, "sha256": sha256_file(diagnostic_path)}},
        "flags": diagnostic["flags"],
    }
    write_json(output_root / "manifest.json", manifest)
    return diagnostic


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen weekly H2 EV robustness diagnostic")
    parser.add_argument("--execute-reviewed-diagnostic", action="store_true")
    args = parser.parse_args()
    if not args.execute_reviewed_diagnostic:
        parser.error("execution requires --execute-reviewed-diagnostic after review/publication")
    execute()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
