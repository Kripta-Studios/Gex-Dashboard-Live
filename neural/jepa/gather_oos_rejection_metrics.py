"""Gather OOS trade-level differences, candidate filtering, and rejected trade metrics."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import numpy as np

def main() -> int:
    base_dir = Path("research_papers/JEPA/results/_diagnostics")
    c0_path = base_dir / "regime_gate_ablation_c0_202601_202605_seed20260618_v1"
    r1_path = base_dir / "regime_gate_ablation_r1_ivskew_202601_202605_seed20260618_v1"
    
    t_c0 = pd.read_csv(c0_path / "event_option_profile_trades.csv")
    t_r1 = pd.read_csv(r1_path / "event_option_profile_trades.csv")
    
    qqq_c0 = t_c0[(t_c0["ticker"] == "QQQ") & (t_c0["month"] == 202602)].copy()
    qqq_r1 = t_r1[(t_r1["ticker"] == "QQQ") & (t_r1["month"] == 202602)].copy()
    
    print("=== QQQ 202602 DIFF ===")
    c0_keys = set(zip(qqq_c0["date"], qqq_c0["minute"], qqq_c0["action"]))
    r1_keys = set(zip(qqq_r1["date"], qqq_r1["minute"], qqq_r1["action"]))
    
    only_c0 = c0_keys - r1_keys
    only_r1 = r1_keys - c0_keys
    
    print("Trades only in C0 (rejected by R1 gate):")
    for key in only_c0:
        row = qqq_c0[(qqq_c0["date"] == key[0]) & (qqq_c0["minute"] == key[1]) & (qqq_c0["action"] == key[2])].iloc[0]
        print(f"  Date: {row['trade_date']} Min: {row['minute']} Action: {row['action']} Ret: {row['realized_return']:+.4f} Hold: {row['exit_minutes']}m")
        
    print("\nTrades only in R1 (triggered because previous trade got rejected/scheduled differently):")
    for key in only_r1:
        row = qqq_r1[(qqq_r1["date"] == key[0]) & (qqq_r1["minute"] == key[1]) & (qqq_r1["action"] == key[2])].iloc[0]
        print(f"  Date: {row['trade_date']} Min: {row['minute']} Action: {row['action']} Ret: {row['realized_return']:+.4f} Hold: {row['exit_minutes']}m")
        
    # Get threshold for QQQ 202602 R1
    # We can read the JSON policy from the fold policy artifacts
    policy_path = r1_path / "fold_policy_artifacts" / "fold_policy_202602.json"
    if policy_path.exists():
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        print("\nPolicy Artifact Details (QQQ 202602 R1):")
        for tp in policy.get("ticker_policies", []):
            if tp["ticker"] == "QQQ":
                print(f"  Profile: {tp['profile']}")
                print(f"  Deploy Config: {tp['deploy_config']}")
                print(f"  Direction Mode: {tp['direction_mode']}")
                # If there are any custom fields
                
    # Let's check R4 (IB Range) starvation metrics: how many candidates survive at different steps
    # We will load the prepared profile frames to count them
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
