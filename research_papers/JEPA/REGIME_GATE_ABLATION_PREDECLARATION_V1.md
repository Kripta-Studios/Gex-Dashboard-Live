# Regime Gate Ablation — Predeclaration V1

**Date:** 2026-07-11 15:18 CEST
**Author:** Automated research agent
**Status:** PREDECLARED — not yet executed

## Hypothesis

The GBT payoff selector fails because the same model/threshold/direction applies
uniformly to all market states. A regime gate that **abstains** from trading in
unfavorable regimes—selected only on inner validation—should improve stability
without requiring a better model.

## Single factor changed

**Control:** existing profile selector without any regime gate (--regime-gate-features empty).
**Variant:** same profile selector + regime gate from 4 predeclared features.

Everything else is identical: dataset, model, seed, folds, caps, cooldowns, gates.

## Predeclared regime features

| ID | Feature (SPXW) | Feature (QQQ/SPY) | Rationale |
|----|----------------|--------------------|-----------|
| R1 | `phys_d25_iv_skew_put_minus_call` | `phys_d35_iv_skew_put_minus_call` | IV skew = put/call demand imbalance |
| R2 | `phys_d25_spread_mean` | `phys_d35_spread_mean` | Spread = liquidity/uncertainty |
| R3 | `phys_abs_ret_5m_bps` | `phys_abs_ret_5m_bps` | Realized vol proxy |
| R4 | `ib_range_bps` | `ib_range_bps` | IB range = intraday vol regime |

All four are live-observable at 10:30+ and backward-looking.

## Gate mechanism

For each regime feature:
1. Compute percentiles on **train data only** (20th, 40th, 60th, 80th)
2. For each percentile × direction (above/below): apply to inner validation trades
3. Select the gate configuration that maximizes the selector's score on inner validation
4. If no configuration passes gates, abstain (identical to no-gate behavior)
5. Apply selected gate to test month

Total gate search space per fold: 4 features × 4 quantiles × 2 directions + 1 no-gate = 33.

## Walk-forward configuration

- **Dataset:** `tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet`
- **Test months:** 202601..202605
- **Inner validation:** 3 months before each test month
- **Train:** all months before validation
- **Seed:** 20260618
- **Profiles:** d25-win (SPXW), d35-win (QQQ/SPY)
- **Caps/cooldowns:** SPXW 4/0m, QQQ 2/30m, SPY 1/0m
- **Gates:** PF≥1.3, WR≥50%, ≥18 trades/month, all months positive, hold≥30m
- **Features:** 277 live-observable, entry≥10:30 ET

## Advance criteria

The regime gate passes if for **each** of SPXW, QQQ, SPY:
- PF ≥ 1.3 OOS
- WR ≥ 50% OOS
- ≥ 18 trades in each OOS month
- PnL > 0 in all OOS months
- hold ≥ 30m for every trade

Additionally, the variant must improve over control:
- More ticker×month cells passing full gates
- Bootstrap daily PnL difference positive with p < 0.05

If neither arm passes all gates for all tickers, both are rejected.
If variant passes but control doesn't, variant advances to further validation.
If both pass, paired comparison determines continuation.

## What this does NOT test

- New model architecture
- New features
- New direction mechanism
- Any change to production

## Sealed months

June 2026 remains sealed and excluded. --end-month=202605.

## Script hashes

Will be computed and recorded after predeclaration, before execution.
