"""Check C0 (Control) equivalence and gather statistics for all arms."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import numpy as np

def main() -> int:
    c0_dir = Path("research_papers/JEPA/results/_diagnostics/regime_gate_ablation_c0_202601_202605_seed20260618_v1")
    folds_c0 = pd.read_csv(c0_dir / "selected_folds.csv")
    trades_c0 = pd.read_csv(c0_dir / "event_option_profile_trades.csv") if (c0_dir / "event_option_profile_trades.csv").exists() else pd.DataFrame()
    
    print("=== CONTROL C0 ANALYSIS ===")
    print("Selected Folds:")
    print(folds_c0[["ticker", "month", "status", "profile", "deploy_config", "test_trades", "test_pnl_return"]].to_string())
    print(f"Total C0 trades executed: {len(trades_c0)}")
    
    # Let's inspect the selected configurations of other arms in 202602
    print("\n=== SELECTED CONFIGURATIONS FOR FOLD 202602 ===")
    arms = ["c0_202601_202605_seed20260618_v1", "r1_ivskew_202601_202605_seed20260618_v1", "r2_spread_202601_202605_seed20260618_v1", "r3_absret_202601_202605_seed20260618_v1", "r4_ib_202601_202605_seed20260618_v1"]
    for arm in arms:
        path = Path("research_papers/JEPA/results/_diagnostics") / f"regime_gate_ablation_{arm}"
        if not path.exists():
            continue
        folds = pd.read_csv(path / "selected_folds.csv")
        row = folds[(folds["ticker"] == "QQQ") & (folds["month"] == 202602)].iloc[0]
        print(f"{arm[:15]:<15} QQQ 202602: profile={row.get('profile')} gate={row.get('regime_gate')} cfg={row.get('deploy_config')} test_trades={row.get('test_trades')} test_pf={row.get('test_profit_factor'):.3f} test_pnl={row.get('test_pnl_return'):+.3f}R")
        
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
