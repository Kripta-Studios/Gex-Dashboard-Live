"""Analyze and compare the results of the 5 regime gate ablation arms."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import numpy as np

def load_arm_results(arm_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    folds_path = arm_dir / "selected_folds.csv"
    trades_path = arm_dir / "event_option_profile_trades.csv"
    
    folds = pd.read_csv(folds_path) if folds_path.exists() else pd.DataFrame()
    trades = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()
    return folds, trades

def get_rejected_trades_metrics(all_candidates_scored: pd.DataFrame, executed_trades: pd.DataFrame, gate_name: str) -> dict:
    if all_candidates_scored.empty:
        return {"pf": float("nan"), "pnl": 0.0, "count": 0}
    # Candidates that did not get executed but would have been executed under the base config if not for the gate
    # To identify rejected candidates: they are candidates that pass the model threshold but are filtered by the gate.
    return {}

def main() -> int:
    base_dir = Path("research_papers/JEPA/results/_diagnostics")
    arms = {
        "C0 (Control)": base_dir / "regime_gate_ablation_c0_202601_202605_seed20260618_v1",
        "R1 (IV Skew)": base_dir / "regime_gate_ablation_r1_ivskew_202601_202605_seed20260618_v1",
        "R2 (Spread - Primary)": base_dir / "regime_gate_ablation_r2_spread_202601_202605_seed20260618_v1",
        "R3 (Abs Return)": base_dir / "regime_gate_ablation_r3_absret_202601_202605_seed20260618_v1",
        "R4 (IB Range)": base_dir / "regime_gate_ablation_r4_ib_202601_202605_seed20260618_v1",
    }
    
    print("# REGIME GATE ABLATION V1 ANALYSIS\n")
    
    all_summary = []
    
    for name, path in arms.items():
        folds, trades = load_arm_results(path)
        if folds.empty:
            print(f"No fold files found for {name} in {path}")
            continue
            
        print(f"## Arm: {name}")
        
        # Summary table of selected folds
        summary_rows = []
        for _, row in folds.iterrows():
            ticker = row["ticker"]
            month = int(row["month"])
            profile = row["profile"]
            status = row["status"]
            
            # Extract test metrics
            test_trades = int(row.get("test_trades", 0))
            test_pf = float(row.get("test_profit_factor", float("nan")))
            test_pnl = float(row.get("test_pnl_return", 0.0))
            
            # Extract gate details from fold policy JSON if available
            gate_selected = row.get("regime_gate", "none")
            
            summary_rows.append({
                "Ticker": ticker,
                "Month": month,
                "Status": status,
                "Profile": profile,
                "Gate": gate_selected,
                "Trades": test_trades,
                "PF": f"{test_pf:.3f}" if np.isfinite(test_pf) else "NaN",
                "PnL": f"{test_pnl:+.3f}R" if test_trades > 0 else "0.000R"
            })
            
        summary_df = pd.DataFrame(summary_rows)
        # Manual markdown table printer
        headers = ["Ticker", "Month", "Status", "Profile", "Gate", "Trades", "PF", "PnL"]
        print("| " + " | ".join(headers) + " |")
        print("|" + "|".join(["---" for _ in headers]) + "|")
        for _, row in summary_df.iterrows():
            print("| " + " | ".join(str(row[h]) for h in headers) + " |")
        print("\n" + "="*80 + "\n")
        
        # Store for global comparison
        summary_df["Arm"] = name
        all_summary.append(summary_df)

    global_df = pd.concat(all_summary, ignore_index=True)
    
    # Check reproduction of C0 against base-congelado (which should all be abstain)
    c0_folds = global_df[global_df["Arm"] == "C0 (Control)"]
    c0_all_abstain = (c0_folds["Status"] == "invalid_validation").all() or (c0_folds["Status"] == "abstain_no_valid_profile").all()
    print(f"C0 validation check: All folds abstained = {c0_all_abstain}")
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
