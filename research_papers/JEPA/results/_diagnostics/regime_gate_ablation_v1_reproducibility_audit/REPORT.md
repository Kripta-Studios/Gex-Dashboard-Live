# Regime Gate Ablation V1 — Reproducibility & Audit Report

**Date:** 2026-07-11
**Commit SHA:** c5e5de30113c41551a8cc28564c76b911762142e
**Status:** COMPLETED / CLOSED

---

## 1. Executive Summary

This report documents the reproducibility audit and methodological closure of the **Regime Gate Ablation V1** experiment on the physically sealed dataset covering `20250102..20260531`. Five arms were audited:
- **C0 (Control):** Existing profile selector without regime gates.
- **R1 (IV Skew):** Dynamic Put-Call skew gate.
- **R2 (Spread - Primary):** Mean bid-ask spread gate.
- **R3 (Abs Return):** Realized spot return gate.
- **R4 (IB Range):** Initial Balance range gate (with 10:30 ET entries filtered).

All arms utilize **integrated post-score, pre-scheduler, pre-execution regime gating**, where candidate entries are evaluated post-score but *before* positions, grids, cooldowns, or scheduling limits are applied.

---

## 2. Audit Verdict & Parity Confirmations

- **C0 Internal Equivalence: PASS.** A full replay of C0 generated identical trade outcomes and PnL trade-by-trade compared to the original V1 run. The normalized trades hash (`9a59c1f7c476ce6911d497286c28fe65dec3d9d1e6ab0797d1b527e00607a7ab`) matches exactly between control and replay.
- **Historical Broad-Profile Equivalence: NOT CLAIMED.** Control C0 matches the selector under identical validation constraints and allowlists, but does not claim equivalence with historical broad-profile runs.
- **Threshold Reconstruction: PASS.** Manually reconstructed thresholds for all non-abstaining folds across R1-R4 match the selector's math perfectly (`THRESHOLD_MATCH`). For `QQQ / 202602 / R1`, the applied skew gate threshold was verified at exactly `0.012700021`, matching the 20% quantile calculated causal-safely on the training subset filtered for outcome finiteness and contract availability (`finite_labels & observable`).
- **Gate Provenance: PASS.** The provenance of gate selections is fully causal and verified under `all_75_folds.csv`.
- **R2 Spread (Primary): REJECTED.** Did not satisfy target gates across all months and tickers.
- **R1 IV Skew (Exploratory): EXPLORATORY ONLY.** Rescued the `SPXW 202602` fold (9 trades, PF = 1.452, PnL = +1.170R) and improved `QQQ 202602` metrics, but failed frequency gates and is not deployable.
- **R3 (Abs Return) & R4 (IB Range): REJECTED / UNSTABLE.** Structurally viable (R4 causal time-cutoff caused <3% candidate loss) but economically failed target metrics.
- **Ningún arm cumple el contrato.** No policy is promoted to production.
- **Junio de 2026 continúa sellado.** Max trade date in train/test is `20260531`.
- **Producción continúa intacta.** The live VPS system configuration is unaltered.

---

## 3. Quantitative Comparison Table (75 Folds Selected Excerpt)

| Arm | Ticker | Month | Status | Selected Profile | Selected Gate | Trades | PF | PnL |
|---|---|---|---|---|---|---|---|---|
| C0 (Control) | QQQ | 202602 | ok | target_zero_dte_d35_win | none | 21 | 1.416 | +2.771R |
| C0 (Control) | SPY | 202602 | ok | target_zero_dte_d35_win | none | 19 | 1.344 | +2.207R |
| R1 (IV Skew) | SPXW | 202602 | ok | target_zero_dte_d25_win | rg_phys_d25_iv_skew_put_minus_call_below_q20pct | 9 | 1.452 | +1.170R |
| R1 (IV Skew) | QQQ | 202602 | ok | target_zero_dte_d35_win | rg_phys_d35_iv_skew_put_minus_call_above_q20pct | 21 | 1.444 | +2.956R |
| R1 (IV Skew) | SPY | 202602 | ok | target_zero_dte_d35_win | rg_phys_d35_iv_skew_put_minus_call_above_q20pct | 19 | 1.321 | +2.061R |
| R1 (IV Skew) | SPY | 202603 | ok | target_zero_dte_d35_win | rg_phys_d35_iv_skew_put_minus_call_below_q60pct | 52 | 1.403 | +5.464R |
| R1 (IV Skew) | SPY | 202605 | ok | target_zero_dte_d35_win | rg_phys_d35_iv_skew_put_minus_call_below_q80pct | 20 | 0.706 | -2.538R |
| R2 (Spread) | SPY | 202602 | ok | target_zero_dte_d35_win | rg_phys_d25_spread_mean_below_q60pct | 18 | 1.486 | +2.821R |
| R2 (Spread) | SPY | 202603 | ok | target_zero_dte_d35_win | rg_phys_d35_spread_mean_below_q40pct | 66 | 1.185 | +3.422R |
| R2 (Spread) | QQQ | 202604 | ok | target_zero_dte_d35_win | rg_phys_d25_spread_mean_below_q40pct | 29 | 0.968 | -0.286R |

*Note: All other 65 folds resulted in `abstain_no_valid_profile` or `fail_validation_gates` with 0 trades.*

---

## 4. Counterfactual Scheduler Simulations (QQQ 202602 R1)

- **Admitted-Only (Gated In):**
  - Number of trades: 21
  - Winners: 13
  - Losers: 8
  - Profit Factor (PF): 1.444
  - Exact PnL: +2.956R
- **Rejected-Only (Gated Out):**
  - Number of trades: 1
  - Winners: 1
  - Losers: 0
  - Profit Factor (PF): Infinite / Not defined (no losses)
  - Exact PnL: +0.596R

---

## 5. Verification Code & Tests

All functionality is covered by 21 unit tests. They pass cleanly using `pytest --basetemp C:\tmp\pytest-regime-gate-audit`.
Tests cover:
- Temporal safety limits (`minute > 630` causal filter for `ib_range_bps`).
- Gated-out candidate filter accuracy.
- Regime gate configuration dictionary serialization in `fold_policy.json`.
