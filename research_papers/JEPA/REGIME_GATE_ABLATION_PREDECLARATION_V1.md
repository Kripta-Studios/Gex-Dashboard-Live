# Regime Gate Ablation — Predeclaration V1

**Date:** 2026-07-11 15:25 CEST
**Author:** Automated research agent
**Status:** PREDECLARED — ready for execution

## Hypothesis

The GBT payoff selector fails because the same model/threshold/direction applies uniformly to all market states. A regime gate that **abstains** from trading in unfavorable regimes—selected only on inner validation—should improve stability without requiring a better model.

## Experimental Arms

We execute exactly **five isolated arms** (1 control and 4 variants) to isolate the feature effects:

- **Arm C0 (Control):** Existing profile selector without any regime gate.
- **Arm R1 (IV Skew):** Option IV skew features (`phys_d25_iv_skew_put_minus_call` / `phys_d35_iv_skew_put_minus_call`). Direction: `any` (above or below).
- **Arm R2 (Spread - Primary):** Mean bid-ask spread features (`phys_d25_spread_mean` / `phys_d35_spread_mean`). Direction: `below` (trade only when spread is low).
- **Arm R3 (Abs Return):** Realized spot return feature (`phys_abs_ret_5m_bps`). Direction: `below` (trade only when volatility is low/moderate, avoiding high-variance periods).
- **Arm R4 (IB Range):** Initial Balance range feature (`ib_range_bps`). Direction: `any` (above or below).

## Physical Sealing of June 2026

To prevent any leakage, a physically sealed parquet dataset was generated containing only `trade_date <= 20260531`:
- **Path:** `tmp/event_option_dataset_execquote_causal1030_202501_202605_regime_v1.parquet`
- **SHA-256 Hash:** `a1970d2cbd7ef8f96a8b2d9fc092f4b323513c03895e73c2058f39b11c7cbef5`
- The selector script asserts that no row has a date > 20260531.

## Causal Safety & IB Range Handling

To prevent leakage from the incomplete Initial Balance range, whenever the feature `ib_range_bps` is evaluated as a regime gate (Arm R4), all candidates with `minute <= 630` (10:30 ET entry) are physically filtered out of the train, validation, and test datasets. Candidates can only enter starting at 10:35 ET.

## Lexicographical Selection Rank

Instead of maximizing a smooth return/drawdown score, the profile selector chooses the optimal configuration (direction_mode, deploy_config, regime_gate) on inner validation using a strict lexicographical ranking:
1. `passes_all_gates` (1 or 0): Must pass all core validation gates:
   - trades >= min_val_trades (45)
   - min_month_trades >= min_month_trades (18)
   - profit_factor >= min_val_pf (1.3)
   - win_rate >= min_val_win_rate (0.50)
   - call_rate in [min_call_rate, max_call_rate] ([0.15, 0.85])
   - positive_month_rate >= min_val_positive_month_rate (1.0 - all months positive)
2. `worst_month_pnl`: Maximize the PnL of the worst month in validation.
3. `worst_month_pf`: Maximize the profit factor of the worst month in validation.
4. `worst_month_wr`: Maximize the win rate of the worst month in validation.
5. `worst_month_trades`: Maximize the number of trades in the worst month.
6. `total_trades`: Maximize total validation trades.
7. `tie_breaker`: Prefer "no gate" over applying a gate, followed by deterministic alphabetical sorting of the gate config name.

If no configuration satisfies `passes_all_gates`, the fold **abstains** (0 trades test-month).

## Walk-Forward Configuration

- **Test months:** 202601..202605
- **Inner validation:** 3 months before each test month
- **Train:** all months before validation
- **Seed:** 20260618
- **Profiles:** d25-win (SPXW), d35-win (QQQ/SPY)
- **Caps/cooldowns:** SPXW 4/0m, QQQ 2/30m, SPY 1/0m
- **Features:** 277 live-observable, entry≥10:30 ET

## Advance Criteria

The regime gate passes if for **each** of SPXW, QQQ, SPY:
- PF ≥ 1.3 OOS
- WR ≥ 50% OOS
- ≥ 18 trades in each OOS month
- PnL > 0 in all OOS months
- hold ≥ 30m for every trade

Additionally, the variant must improve over control:
- More ticker×month cells passing full gates
- Bootstrap daily PnL difference positive with p < 0.05

## Script Hashes

- `neural/jepa/walkforward_event_option_profile_selector.py`: `D24FF4F15B6CB277A45A79412FBD24D5A07B91771BA68E504622C66737BA12EE`
- `tests/test_walkforward_event_option_regime_gate.py`: `6F2F3AF72CA2BA1DE0CF81544FCC334CFCB5316A2811FDD19C58B5DF71257A72`
- `run_regime_gate_ablation_v1.ps1`: `FF2735A41A6D7FF3BDDC420ED345695110AF6C6F18C08448972F3ABE81DA14F4`
- `neural/jepa/walkforward_event_option_regime_gate.py`: `AA74A1877DB88D9ACFE32A0A13EDACFE9B2AE2BBA74CE29C61ED847B70770B93`
- `neural/jepa/create_sealed_regime_dataset.py`: `5E16C820B1ED0286DD860E4C7F988ABB81F13F4D1CA2FB76A7856B0531484B29`
