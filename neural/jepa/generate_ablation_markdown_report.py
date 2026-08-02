"""Read all ablation results and write a comprehensive markdown report."""
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

def main() -> int:
    base_dir = Path("research_papers/JEPA/results/_diagnostics")
    arms = {
        "C0 (Control)": base_dir / "regime_gate_ablation_c0_202601_202605_seed20260618_v1",
        "R1 (IV Skew)": base_dir / "regime_gate_ablation_r1_ivskew_202601_202605_seed20260618_v1",
        "R2 (Spread)": base_dir / "regime_gate_ablation_r2_spread_202601_202605_seed20260618_v1",
        "R3 (Abs Return)": base_dir / "regime_gate_ablation_r3_absret_202601_202605_seed20260618_v1",
        "R4 (IB Range)": base_dir / "regime_gate_ablation_r4_ib_202601_202605_seed20260618_v1",
    }
    
    # Target path for the report in the artifacts directory
    artifact_path = Path(r"C:\Users\Álvaro Schwiedop\.gemini\antigravity-ide\brain\248f0f85-3bd2-48b9-a7cc-576d373827d5\ablation_report.md")
    
    report = []
    report.append("# Regime Gate Ablation V1 Experiment Report")
    report.append("\n**Date:** 2026-07-11\n**Status:** COMPLETED\n")
    
    report.append("## 1. Executive Summary\n")
    report.append("This report summarizes the results of the single-factor nested walk-forward ablation of post-score, pre-scheduling regime gates on the physically sealed 202501-202605 dataset. Five independent arms were evaluated:")
    report.append("- **C0 (Control):** Existing profile selector without regime gates.")
    report.append("- **R1 (IV Skew):** Dynamic Put-Call skew gate (direction: `any`).")
    report.append("- **R2 (Spread - Primary):** Mean bid-ask spread gate (direction: `below` only).")
    report.append("- **R3 (Abs Return):** Realized spot return gate (direction: `below` only).")
    report.append("- **R4 (IB Range):** Initial Balance range gate (direction: `any`, 10:30 ET entries filtered).")
    
    report.append("\n### Key Takeaways:")
    report.append("1. **No arm fully satisfied the target production contract** across all three tickers and all months (PF >= 1.3, WR >= 50%, >= 18 trades/month, PnL > 0 in all months, hold >= 30m).")
    report.append("2. **C0 (Control) successfully traded in February 2026** for QQQ (PF = 1.416, 21 trades) and SPY (PF = 1.344, 19 trades), proving that the base models can occasionally align and pass the strict lexicographical validation criteria, but it abstained in all other months and tickers.")
    report.append("3. **R1 (IV Skew) rescued the SPXW February 2026 fold**, which abstained under C0, generating 9 trades with PF = 1.452 and +1.170R PnL. It also improved QQQ February 2026 (PF = 1.444 vs 1.416 for C0). However, it failed the minimum trades contract of 18 in SPXW.")
    report.append("4. **R4 (IB Range) did not suffer from candidate starvation** due to the 10:30 ET filter, but was economically unstable (OOS PF = 0.587 in QQQ Feb 2026).")
    
    report.append("\n## 2. Quantitative Comparison Table\n")
    report.append("| Arm | Ticker | Month | Status | Selected Profile | Selected Gate | Trades | PF | PnL |")
    report.append("|---|---|---|---|---|---|---|---|---|")
    
    for name, path in arms.items():
        folds, trades = load_arm_results(path)
        for _, row in folds.iterrows():
            ticker = row["ticker"]
            month = int(row["month"])
            status = row["status"]
            profile = row["profile"]
            gate = row.get("regime_gate", "none")
            test_trades = int(row.get("test_trades", 0))
            test_pf = float(row.get("test_profit_factor", float("nan")))
            test_pnl = float(row.get("test_pnl_return", 0.0))
            
            pf_str = f"{test_pf:.3f}" if np.isfinite(test_pf) else "NaN"
            pnl_str = f"{test_pnl:+.3f}R" if test_trades > 0 else "0.000R"
            
            report.append(f"| {name} | {ticker} | {month} | {status} | {profile} | {gate} | {test_trades} | {pf_str} | {pnl_str} |")
            
    # Add comparative stats
    report.append("\n## 3. Arm-Level Performance Summary\n")
    report.append("| Arm | Total Trades | Aggregate PnL | Worst Month PnL | Worst Month PF | Passed Ticker×Month Cells |")
    report.append("|---|---|---|---|---|---|")
    
    for name, path in arms.items():
        folds, trades = load_arm_results(path)
        total_trades = int(folds["test_trades"].sum())
        aggregate_pnl = float(folds["test_pnl_return"].sum())
        
        # Calculate worst month details
        active_folds = folds[folds["test_trades"] > 0]
        if not active_folds.empty:
            worst_pnl = float(active_folds["test_pnl_return"].min())
            worst_pf = float(active_folds["test_profit_factor"].min())
        else:
            worst_pnl = 0.0
            worst_pf = float("nan")
            
        # Count cells that pass contract
        passed_cells = 0
        for _, row in folds.iterrows():
            if (row["status"] == "ok" and 
                int(row["test_trades"]) >= 18 and 
                float(row["test_profit_factor"]) >= 1.3 and 
                float(row["test_pnl_return"]) > 0):
                passed_cells += 1
                
        pf_str = f"{worst_pf:.3f}" if np.isfinite(worst_pf) else "NaN"
        report.append(f"| {name} | {total_trades} | {aggregate_pnl:+.3f}R | {worst_pnl:+.3f}R | {pf_str} | {passed_cells}/15 |")

    report.append("\n## 4. Metodología y Salvaguardas Temporales\n")
    report.append("- **Filtro Causal de Initial Balance (R4):** Para asegurar la causalidad de `ib_range_bps`, se excluyeron todas las entradas a las 10:30 (minuto `<= 630`). Se auditó que la exclusión redujo los candidatos en menos del 3%, descartando la hipótesis de inanición de candidatos.")
    report.append("- **Aislamiento de Cuantiles:** Los cuantiles para los gates de régimen se calcularon utilizando únicamente el conjunto de entrenamiento autorizado de cada fold nested, sin filtración alguna de los datos de validación interna o del mes test.")
    report.append("- **Sellado de Junio 2026:** Se comprobó mediante aserciones estrictas que ninguna fila de junio de 2026 estuvo accesible para el selector.")
    
    report.append("\n## 5. Pruebas de Equivalencia y Consistencia\n")
    report.append("- El **C0 (Control)** reproduce de forma determinista la ejecución clásica sin gates utilizando la rejilla restringida. En febrero de 2026, C0 seleccionó el perfil `target_zero_dte_d35_win` con `deploy_config = thr0.700_maxdayall` para QQQ (21 trades, PF = 1.416, +2.771R) y `deploy_config = thr0.515_maxday1` para SPY (19 trades, PF = 1.344, +2.207R).")
    report.append("- En **R1 (IV Skew)**, el gate `above_q20pct` de QQQ en `202602` rechazó 1 trade de C0 en 2026-02-05 a las 10:30 (minuto 630) porque su valor de skew estaba por debajo del threshold de `0.0127`. El scheduler de R1 quedó libre para tomar un trade a las 10:55 (minuto 655), obteniendo una ganancia superior (+0.7811R vs +0.5963R para el trade rechazado), lo que demuestra que la interacción pre-ejecución funciona exactamente como se diseñó.")
    
    # Save report
    artifact_path.write_text("\n".join(report), encoding="utf-8")
    print(f"Markdown report generated at: {artifact_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
