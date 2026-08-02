"""Compile exact detailed metrics and rejected trades for QQQ 202602 R1 and SPXW 202602 R1."""
from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "neural" / "jepa"))

def main() -> int:
    # Load dataset
    df = pd.read_parquet("tmp/event_option_dataset_execquote_causal1030_202501_202605_regime_v1.parquet")
    df["month"] = df["trade_date"].astype(str).str[:6]
    df["date"] = df["trade_date"].astype(str)
    
    # ── QQQ 202602 ──────────────────────────────────────────────────────────
    print("=== QQQ 202602 DETAILED SIGNAL ANALYSIS ===")
    
    # We will simulate the exact trade scheduling for QQQ 202602.
    # The selected profile is target_zero_dte_d35_win.
    # The selected deploy config is thr0.700_maxdayall (meaning model score threshold = 0.700, no daily cap).
    # Cooldown = 30 minutes.
    
    # Let's get the scored candidates for QQQ 202602 (test data)
    test_qqq = df[(df["ticker"] == "QQQ") & (df["month"] == "202602")].copy()
    
    # Let's read QQQ 202602 trades under C0 and R1 to confirm
    t_c0 = pd.read_csv("research_papers/JEPA/results/_diagnostics/regime_gate_ablation_c0_202601_202605_seed20260618_v1/event_option_profile_trades.csv")
    t_r1 = pd.read_csv("research_papers/JEPA/results/_diagnostics/regime_gate_ablation_r1_ivskew_202601_202605_seed20260618_v1/event_option_profile_trades.csv")
    
    qqq_c0_trades = t_c0[(t_c0["ticker"] == "QQQ") & (t_c0["month"] == 202602)]
    qqq_r1_trades = t_r1[(t_r1["ticker"] == "QQQ") & (t_r1["month"] == 202602)]
    
    print(f"C0 trades: {len(qqq_c0_trades)}")
    print(f"R1 trades: {len(qqq_r1_trades)}")
    
    # Let's inspect the QQQ 202602 test dataset candidates
    # In QQQ 202602 R1, the gate is rg_phys_d35_iv_skew_put_minus_call_above_q20pct (threshold = 0.0127)
    # Let's count how many total candidates are in test month before and after the gate
    print(f"Total test month rows for QQQ: {len(test_qqq)}")
    
    above_threshold_candidates = test_qqq[test_qqq["phys_d35_iv_skew_put_minus_call"] >= 0.0127]
    below_threshold_candidates = test_qqq[test_qqq["phys_d35_iv_skew_put_minus_call"] < 0.0127]
    
    print(f"Candidates with Skew >= 0.0127 (Admitted): {len(above_threshold_candidates)}")
    print(f"Candidates with Skew < 0.0127 (Rejected): {len(below_threshold_candidates)}")
    
    # Let's check R4 candidate counts and starvation audit
    print("\n=== R4 (IB Range) Starvation Audit ===")
    test_qqq_r4 = df[(df["ticker"] == "QQQ") & (df["month"] == "202602")].copy()
    # Filter out <= 10:30 (minute <= 630)
    test_qqq_r4_filtered = test_qqq_r4[test_qqq_r4["minute"].astype(int) > 630]
    print(f"QQQ 202602 total candidates: {len(test_qqq_r4)}")
    print(f"QQQ 202602 candidates after 10:30 filter: {len(test_qqq_r4_filtered)}")
    
    test_spxw_r4 = df[(df["ticker"] == "SPXW") & (df["month"] == "202602")].copy()
    test_spxw_r4_filtered = test_spxw_r4[test_spxw_r4["minute"].astype(int) > 630]
    print(f"SPXW 202602 total candidates: {len(test_spxw_r4)}")
    print(f"SPXW 202602 candidates after 10:30 filter: {len(test_spxw_r4_filtered)}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
