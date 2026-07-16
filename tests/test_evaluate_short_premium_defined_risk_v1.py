from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa.evaluate_short_premium_defined_risk_v1 import (
    MAX_HOLD_MINUTES,
    ROUND_TRIP_FRICTION_POINTS,
    apply_exit_rule,
    assert_clock_coverage,
    build_structure,
    evaluate_gate,
    profit_factor,
    select_walkforward,
    valid_quotes,
)


def _entry() -> pd.DataFrame:
    rows = [
        ("C", 100.0, 0.50, 1.90, 2.00),
        ("P", 100.0, -0.50, 1.80, 1.95),
        ("C", 102.0, 0.25, 2.00, 2.10),
        ("P", 98.0, -0.25, 1.90, 2.00),
        ("C", 103.0, 0.15, 1.20, 1.30),
        ("P", 97.0, -0.15, 1.10, 1.20),
        ("C", 104.0, 0.08, 0.45, 0.55),
        ("P", 96.0, -0.08, 0.40, 0.50),
        ("C", 105.0, 0.04, 0.15, 0.25),
        ("P", 95.0, -0.04, 0.10, 0.20),
        ("C", 107.0, 0.01, 0.01, 0.05),
        ("P", 93.0, -0.01, 0.01, 0.05),
    ]
    return pd.DataFrame(rows, columns=["right", "strike", "delta", "bid", "ask"])


def test_valid_quotes_rejects_crossed_and_zero_short_bid() -> None:
    frame = pd.DataFrame({"bid": [1.0, 2.0, 0.0], "ask": [1.1, 1.9, 0.1]})
    assert valid_quotes(frame).tolist() == [True, False, True]
    assert valid_quotes(frame, short=True).tolist() == [True, False, False]


def test_clock_coverage_stops_at_sealed_half_day_end() -> None:
    greeks = pd.DataFrame(
        {
            "qdt": pd.to_datetime(["2025-07-03 12:54", "2025-07-03 12:55"]),
            "right": ["C", "C"],
            "strike": [100.0, 100.0],
        }
    )
    clock = greeks.iloc[[0]].copy()
    assert_clock_coverage(greeks, clock, "QQQ", "20250703")


def test_condor_uses_exact_fixed_wings_and_executable_credit() -> None:
    structure = build_structure(_entry(), "SPY", kind="IC", short_delta=0.25, width=5.0)
    assert structure is not None
    assert structure.short_call_strike == 102.0
    assert structure.short_put_strike == 98.0
    assert structure.long_call_strike == 107.0
    assert structure.long_put_strike == 93.0
    assert np.isclose(structure.entry_credit, 2.0 + 1.9 - 0.05 - 0.05)
    assert np.isclose(structure.max_risk_points, 5.0 - structure.entry_credit + ROUND_TRIP_FRICTION_POINTS)


def test_fly_requires_a_common_short_strike() -> None:
    structure = build_structure(_entry(), "SPY", kind="IF", short_delta=0.50, width=5.0)
    assert structure is not None
    assert structure.short_call_strike == structure.short_put_strike == 100.0
    assert structure.long_call_strike == 105.0
    assert structure.long_put_strike == 95.0


def test_exit_rule_uses_observed_gap_fill_after_min_hold() -> None:
    structure = build_structure(_entry(), "SPY", kind="IC", short_delta=0.25, width=5.0)
    assert structure is not None
    entry_dt = pd.Timestamp("2025-01-02 10:35")
    scheduled = entry_dt + pd.Timedelta(minutes=MAX_HOLD_MINUTES)
    path = pd.DataFrame(
        {
            "qdt": [entry_dt + pd.Timedelta(minutes=30), scheduled],
            "close_debit": [structure.entry_credit * 3.5, structure.entry_credit * 0.4],
        }
    )
    path["gross_pnl_points"] = structure.entry_credit - path["close_debit"]
    result = apply_exit_rule(path, structure, scheduled, "PT50_SL200")
    assert result is not None
    assert result["exit_reason"] == "stop"
    assert result["close_debit"] == structure.entry_credit * 3.5


def _candidate_ledger() -> pd.DataFrame:
    rows = []
    months = pd.period_range("2024-01", "2025-12", freq="M")
    for ticker in ("QQQ", "SPXW", "SPY"):
        for month_index, period in enumerate(months):
            month = str(period).replace("-", "")
            for profile, base in (("a", 0.05), ("b", -0.02)):
                for day in range(1, 14):
                    pnl = base if day % 3 else -base / 2
                    rows.append(
                        {
                            "ticker": ticker,
                            "month": month,
                            "trade_date": f"{month}{day:02d}",
                            "entry_dt": pd.Timestamp(period.start_time) + pd.Timedelta(days=day - 1),
                            "exit_dt": pd.Timestamp(period.start_time) + pd.Timedelta(days=day - 1, minutes=30),
                            "profile_id": profile,
                            "net_pnl_R": pnl + month_index * 0.0,
                        }
                    )
    return pd.DataFrame(rows)


def test_walkforward_never_uses_evaluation_month_for_selection() -> None:
    ledger = _candidate_ledger()
    selected, folds = select_walkforward(ledger, ["202501"])
    assert set(folds["train_start_month"]) == {"202401"}
    assert set(folds["train_end_month"]) == {"202412"}
    assert set(folds["profile_id"]) == {"a"}
    assert set(selected["month"]) == {"202501"}


def test_gate_is_strict_for_pf_wr_frequency_and_positive_months() -> None:
    ledger = _candidate_ledger()
    selected = ledger.loc[ledger["profile_id"].eq("a") & ledger["month"].eq("202501")].copy()
    monthly, gate = evaluate_gate(selected, ["202501"])
    assert len(monthly) == 3
    assert gate["joint_gate_pass"]
    selected.loc[selected.index[0], "net_pnl_R"] = -100.0
    _, failed = evaluate_gate(selected, ["202501"])
    assert not failed["joint_gate_pass"]
    assert profit_factor([1.0, -0.5]) == 2.0
