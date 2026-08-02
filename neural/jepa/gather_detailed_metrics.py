"""Gather detailed metrics for reporting the ablation results."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import numpy as np

def main() -> int:
    base_dir = Path("research_papers/JEPA/results/_diagnostics")
    arms = {
        "C0": base_dir / "regime_gate_ablation_c0_202601_202605_seed20260618_v1",
        "R1": base_dir / "regime_gate_ablation_r1_ivskew_202601_202605_seed20260618_v1",
        "R2": base_dir / "regime_gate_ablation_r2_spread_202601_202605_seed20260618_v1",
        "R3": base_dir / "regime_gate_ablation_r3_absret_202601_202605_seed20260618_v1",
        "R4": base_dir / "regime_gate_ablation_r4_ib_202601_202605_seed20260618_v1",
    }

    # 1. Look at QQQ 202602 under R1 (IV Skew) and compile full stats
    print("=== DETAILS FOR QQQ / 202602 (R1 vs C0) ===")
    folds_r1 = pd.read_csv(arms["R1"] / "selected_folds.csv")
    row_r1 = folds_r1[(folds_r1["ticker"] == "QQQ") & (folds_r1["month"] == 202602)].iloc[0]
    
    folds_c0 = pd.read_csv(arms["C0"] / "selected_folds.csv")
    row_c0 = folds_c0[(folds_c0["ticker"] == "QQQ") & (folds_c0["month"] == 202602)].iloc[0]
    
    print(f"C0: status={row_c0.get('status')} trades={row_c0.get('test_trades')} PF={row_c0.get('test_profit_factor'):.3f} PnL={row_c0.get('test_pnl_return'):+.3f}R")
    print(f"R1: status={row_r1.get('status')} trades={row_r1.get('test_trades')} PF={row_r1.get('test_profit_factor'):.3f} PnL={row_r1.get('test_pnl_return'):+.3f}R gate={row_r1.get('regime_gate')}")
    
    # 2. Look at SPXW 202602 under R1
    print("\n=== DETAILS FOR SPXW / 202602 (R1 vs C0) ===")
    row_spxw_r1 = folds_r1[(folds_r1["ticker"] == "SPXW") & (folds_r1["month"] == 202602)].iloc[0]
    row_spxw_c0 = folds_c0[(folds_c0["ticker"] == "SPXW") & (folds_c0["month"] == 202602)].iloc[0]
    print(f"C0: status={row_spxw_c0.get('status')} trades={row_spxw_c0.get('test_trades')} PnL={row_spxw_c0.get('test_pnl_return'):+.3f}R")
    print(f"R1: status={row_spxw_r1.get('status')} trades={row_spxw_r1.get('test_trades')} PF={row_spxw_r1.get('test_profit_factor'):.3f} PnL={row_spxw_r1.get('test_pnl_return'):+.3f}R gate={row_spxw_r1.get('regime_gate')}")

    # Let's inspect candidate files or candidate_validation.csv to count candidates before/after gate
    print("\n=== CANDIDATE RETENTION ANALYSIS ===")
    # candidate_validation.csv contains candidate metrics for each profile + configuration in the validation inner loops
    for arm_name, path in arms.items():
        cand_path = path / "candidate_validation.csv"
        if cand_path.exists():
            cands = pd.read_csv(cand_path)
            # Filter to 202602 fold for QQQ
            qqq_cands = cands[(cands["ticker"] == "QQQ") & (cands["month"] == 202602)]
            print(f"Arm {arm_name}: QQQ 202602 validation candidates count = {len(qqq_cands)}")
            
    # Starvation audit for R4 (IB Range)
    print("\n=== STARVATION AUDIT FOR R4 (IB Range) ===")
    r4_cands_path = arms["R4"] / "candidate_validation.csv"
    if r4_cands_path.exists():
        r4_cands = pd.read_csv(r4_cands_path)
        print("R4 Candidate counts by Ticker and Month:")
        counts = r4_cands.groupby(["ticker", "month"]).size().reset_index(name="candidates")
        print(counts.to_string(index=False))

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
