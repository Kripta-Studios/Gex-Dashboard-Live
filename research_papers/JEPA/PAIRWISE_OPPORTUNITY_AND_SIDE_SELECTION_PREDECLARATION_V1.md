# PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_V1 — Predeclaration

**Status:** PREDECLARED — not yet executed  
**Date:** 2026-07-11  
**Author:** AI Agent (supervised)  
**Commit (code):** to be filled after commit  

## Hypothesis

Current absolute CALL/PUT return models exhibit direction instability. A hierarchical decomposition into:

1. **Opportunity classifier** — is there *any* profitable side?
2. **Side selector** — which side has *higher* return?

may resolve the call/put confusion by separating the "trade vs. abstain" decision from the "CALL vs. PUT" decision.

## Arms

| Arm | Description | Models |
|-----|-------------|--------|
| C0 | Baseline frozen absolute model (current production logic) | LGBMClassifier call + put |
| P1 | Pairwise opportunity + side classifier | LGBMClassifier opportunity + LGBMClassifier side |

## Labels

```text
opportunity_label = 1 if max(call_return, put_return) > 0 else 0
side_label        = 1 if call_return > put_return else 0
side_advantage    = call_return - put_return  (diagnostic only)
```

Labels are computed from `call_d{D}_opt_exit_ret` and `put_d{D}_opt_exit_ret` columns.

## Feature Allowlist (Closed)

### Common causal features
- `dte_days`, `minute`, `spot`, `underlying_volume`
- `ib_range_bps`, `dist_ib_high_bps`, `dist_ib_low_bps`
- `nearest_level_abs_bps`
- `ret_1m_bps`, `ret_5m_bps`, `ret_15m_bps`, `ret_30m_bps`

### Call-Put difference features (bucket D=25 for SPXW, D=35 for QQQ/SPY)
- `iv_diff`, `spread_diff`, `volume_diff`, `oi_diff`, `delta_diff`, `vega_diff`

### Backward-looking changes of differences (5m, 15m, 25m)
- `{metric}_diff_chg_5m`, `{metric}_diff_chg_15m`, `{metric}_diff_chg_25m`
  for metric in {iv, spread, volume, oi, delta, vega}

### Excluded
- Gamma: not present in dataset
- No future data, no labels, no PnL, no high/low posterior columns

## Walk-Forward Protocol

- **Dataset:** `event_option_dataset.parquet` filtered to 20220101..20251231
- **Rolling train:** 12 months
- **Inner validation:** 3 months
- **Outer test:** 1 month
- **Total folds:** 33 (202304..202512)
- **Tickers:** SPXW (d25), QQQ (d35), SPY (d35)
- **Entry window:** minute > 630 (after 10:30 ET)

## Policy Execution

### C0 (Baseline)
Standard absolute model: predict call_return and put_return independently. Threshold sweep on validation. Deploy best config to test.

### P1 (Pairwise)
1. `p_trade = opportunity_model.predict_proba(X)[:, 1]`
2. `p_call = side_model.predict_proba(X)[:, 1]`
3. Grid sweep:
   - `trade_threshold` ∈ {0.1, 0.2, ..., 0.9}
   - `side_margin` ∈ {0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30}
4. Trade if `p_trade >= trade_threshold`:
   - CALL if `p_call >= 0.5 + side_margin`
   - PUT  if `p_call <= 0.5 - side_margin`
   - ABSTAIN otherwise

## Scheduling Constraints (Per Ticker)

| Ticker | Delta bucket | Max trades/day | Cooldown |
|--------|-------------|---------------:|----------|
| SPXW   | d25         | 4              | 0m       |
| QQQ    | d35         | 2              | 30m      |
| SPY    | d35         | 1              | 0m       |

## Validation Selection Criterion

Best `(trade_threshold, side_margin)` selected by maximum validation PnL (sum of R-units).
Ties broken lexicographically by `(lower trade_threshold, lower side_margin)`.

## Inner Validation Gates

A fold passes inner validation if:
- trades >= 18/month × val_months
- profit_factor >= 1.3
- win_rate >= 0.45
- 0.25 <= call_rate <= 0.75

## Success Criteria

P1 is considered a positive signal if across all 33 folds × 3 tickers:
1. Mean OOS PF > C0 mean OOS PF
2. Mean OOS WR > C0 mean OOS WR
3. Direction stability: lower variance in call_rate across folds
4. At least 60% of ticker-folds pass inner validation (vs C0 baseline)

## Diagnostics Exported

Per fold:
- `fold_summary.json`: metrics, selected params, model info
- `fold_trades.csv`: individual trades with timestamps, side, return
- `opportunity_model_importances.csv`
- `side_model_importances.csv`

Aggregate:
- `all_folds.csv`: summary across all folds
- `aggregate_report.json`: means, medians, pass rates
- `spearman_side_advantage.csv`: rank correlation of side_advantage predictions

## 2026 Seal

No data from 202601 onwards is used in any split. An assertion guards this.
