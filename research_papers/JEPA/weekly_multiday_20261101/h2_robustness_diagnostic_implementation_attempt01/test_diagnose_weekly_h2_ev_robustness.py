from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("weekly_h2_robustness", HERE / "diagnose_weekly_h2_ev_robustness.py")
assert SPEC and SPEC.loader
diag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diag)


def candidate(candidate_id: str, ticker: str, entry: str, exit_date: str, ask: float, bid: float | None, net: float | None = None) -> dict:
    base = {
        "candidate_id": candidate_id, "ticker": ticker, "right": "CALL",
        "entry_date": entry, "exit_date": exit_date, "entry_ask": ask, "exit_bid": bid,
        "status": "MISSING_EXIT_QUOTE" if bid is None else "OBSERVED_EXIT",
    }
    cash = diag.recompute_cash(base, 0.02)
    base["entry_debit_adverse"] = cash["entry_debit"]
    base["net_adverse"] = cash["net_usd"] if net is None else net
    return base


def fixed_fixture() -> tuple[list[dict], list[dict]]:
    candidates = [
        candidate("a", "SPY", "20260105", "20260107", 1.0, 1.5),
        candidate("b", "QQQ", "20260105", "20260107", 2.0, 1.0),
        candidate("c", "SPXW", "20260106", "20260108", 1.5, None),
    ]
    ledger = []
    for row in candidates:
        ledger.append({"event": "ENTRY", "candidate_id": row["candidate_id"], "date": row["entry_date"], "ticker": row["ticker"]})
    for row in candidates:
        ledger.append({
            "event": "EXIT", "candidate_id": row["candidate_id"], "date": row["exit_date"],
            "ticker": row["ticker"], "net_usd": row["net_adverse"],
        })
    return candidates, ledger


def test_slippage_points_are_premium_times_100_and_floor_exit() -> None:
    row = {"entry_ask": 1.0, "exit_bid": 0.03}
    cash = diag.recompute_cash(row, 0.02)
    assert cash == pytest.approx({"entry_debit": 103.30, "exit_credit": -0.30, "net_usd": -103.60})
    floored = diag.recompute_cash(row, 0.05)
    assert floored["entry_debit"] == pytest.approx(106.30)
    assert floored["exit_credit"] == pytest.approx(-1.30)
    with pytest.raises(diag.DiagnosticError, match="undeclared"):
        diag.recompute_cash(row, 0.03)


def test_fixed_trades_and_sweep_preserve_universe() -> None:
    candidates, ledger = fixed_fixture()
    trades, returned_ledger = diag.fixed_trades(candidates, ledger)
    assert [row["candidate_id"] for row in trades] == ["a", "b", "c"]
    rows = [diag.sweep_metrics(trades, returned_ledger, value) for value in diag.SLIPPAGE_POINTS]
    assert [row["slippage_points_per_option_per_side"] for row in rows] == list(diag.SLIPPAGE_POINTS)
    assert all(row["trades"] == 3 for row in rows)
    assert rows[0]["missing_exit_lower_bounds"] == 1
    assert rows[-1]["net_usd"] < rows[0]["net_usd"]


def test_equal_risk_uses_real_adverse_debit_and_equal_ticker_weight() -> None:
    candidates, ledger = fixed_fixture()
    trades, _ = diag.fixed_trades(candidates, ledger)
    result = diag.equal_risk_diagnostic(trades)
    expected = sum(result["tickers"][ticker]["aggregate_debit_compensated_return"] for ticker in diag.TICKERS) / 3
    assert result["equal_weight_ticker_average"] == pytest.approx(expected)
    assert result["executable_portfolio"] is False
    assert result["tickers"]["SPY"]["n"] == 1


def test_concentration_is_fixed_stable_and_has_six_months() -> None:
    candidates, ledger = fixed_fixture()
    trades, _ = diag.fixed_trades(candidates, ledger)
    result = diag.concentration_diagnostic(trades)
    assert [row["drop_count"] for row in result["drop_top_gains"]] == [1, 3, 5]
    assert result["drop_top_gains"][0]["removed_candidate_ids"] == ["a"]
    assert len(result["leave_one_exit_month_out"]) == 6
    assert sum(row["removed_trades"] for row in result["leave_one_exit_month_out"]) == 3


def test_bootstrap_aggregates_tickers_by_entry_date_includes_zeros_and_is_deterministic() -> None:
    candidates, ledger = fixed_fixture()
    trades, _ = diag.fixed_trades(candidates, ledger)
    sessions = ["20260105", "20260106", "20260107", "20260108", "20260109", "20260112"]
    first = diag.block_bootstrap(trades, sessions, seed=20261101, resamples=100, block_length=5)
    second = diag.block_bootstrap(trades, sessions, seed=20261101, resamples=100, block_length=5)
    assert first == second
    assert first["sessions"] == 6 and first["zero_pnl_sessions"] == 4
    assert first["p_value"] is None
    assert "not a null distribution" in first["interpretation"]
    assert first["empirical_percentile_interval_type7_usd"]["low_2_5"] <= first["empirical_percentile_interval_type7_usd"]["high_97_5"]


def test_fixed_trade_rejects_mutated_baseline_and_pair_mismatch() -> None:
    candidates, ledger = fixed_fixture()
    candidates[0]["net_adverse"] += 1
    with pytest.raises(diag.DiagnosticError, match="candidate baseline net"):
        diag.fixed_trades(candidates, ledger)
    candidates, ledger = fixed_fixture()
    ledger.pop()
    with pytest.raises(diag.DiagnosticError, match="universe mismatch"):
        diag.fixed_trades(candidates, ledger)


def test_type7_percentile_linear_interpolation() -> None:
    assert math.isclose(diag.percentile_type7([0.0, 10.0], 0.25), 2.5)
