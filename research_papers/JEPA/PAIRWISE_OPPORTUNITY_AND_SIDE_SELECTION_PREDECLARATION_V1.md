# PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_V1 — Predeclaration

**Status:** PREDECLARED — final preflight implementation ready; models not yet trained
**Date:** 2026-07-11  
**Author:** AI Agent (supervised)  
**Preparation baseline:** `b3c6af9a7fb54adecce6f6aff270d89cd52a42fe`

## Hashes and final preflight authority
- **Dataset SHA-256:** `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`
- **Feature Allowlist Hash:** `fa2057653ed0327b7f84a165c25f6e6d31e31b3b05c5591593e9c0bd3056d50e`

Los hashes de runner, walk-forward, tests y esta predeclaración se regeneran desde un
commit limpio con `HEAD == origin/main` mediante `-PreflightOnly`. El manifiesto
`pairwise_opportunity_side_v1_preflight/pairwise_preflight_manifest.json` es la
autoridad final; los hashes previos a ese commit no autorizan una ejecución.

## Hypothesis

Current absolute CALL/PUT return models exhibit direction instability. A hierarchical decomposition into:

1. **Opportunity classifier** — is there *any* profitable side?
2. **Side selector** — which side has *higher* return?

may resolve the call/put confusion by separating the "trade vs. abstain" decision from the "CALL vs. PUT" decision.

## Arms

| Arm | Description | Models |
|-----|-------------|--------|
| **C0** | **In-protocol nested absolute-head baseline** | LGBMClassifier call_win + put_win |
| **P1** | **Pairwise opportunity + side classifier** | LGBMClassifier opportunity + LGBMClassifier side |

C0 is NOT a frozen production artifact or a historical model. It is trained nested within each fold using exactly the same data, features, hyperparameters, scheduler, and protocol as P1.

## Labels

### C0 Baseline Labels
```text
call_win_label = 1 if call_return > 0 else 0
put_win_label  = 1 if put_return > 0 else 0
```

### P1 Pairwise Labels
```text
opportunity_label = 1 if max(call_return, put_return) > 0 else 0
side_advantage    = call_return - put_return
side_label        = 1 if side_advantage > 0 else 0
```
- Opportunity head is trained on all valid rows.
- Side head is trained only on rows where `opportunity_label == 1` and `abs(side_advantage) > 1e-9` (ties are excluded).

## Feature Allowlist (Closed & Identical for C0/P1)

### Common causal features
- `minute` (restricting entries to `minute > 630`, so first candidate is `minute == 635` / 10:35 ET)
- `ib_range_bps`, `dist_ib_high_bps`, `dist_ib_low_bps`
- `nearest_level_abs_bps`
- `ret_1m_bps`, `ret_5m_bps`, `ret_15m_bps`, `ret_30m_bps`

*Note: `dte_days`, `spot`, and `underlying_volume` are strictly excluded. The first allowed candidate is strictly 10:35 ET (`minute == 635`). `minute == 630` is strictly excluded.*

### Call-Put difference features (bucket D=25 for SPXW, D=35 for QQQ/SPY)
- `iv_diff`, `spread_pct_diff`, `volume_diff`, `oi_diff`, `abs_delta_diff`, `vega_diff`

### Backward-looking changes of differences (5m, 15m, 25m)
- `{metric}_diff_chg_5m`, `{metric}_diff_chg_15m`, `{metric}_diff_chg_25m`
  for metric in {iv, spread_pct, volume, abs_delta, vega}

*Note: OI differences changes (`oi_diff_chg_*`) are strictly excluded to avoid rollover noise.*

*Calculation Rule: Before computing shifts, sort by `minute` within each group. Shifts `shift(1/3/5)` are computed grouping by `(ticker, trade_date, bucket)` to prevent cross-session or cross-ticker contamination.*

## Walk-Forward Protocol

- **Dataset:** `event_option_dataset.parquet` filtered to 20220101..20251231 (excl. 2026)
- **Rolling train:** 12 months
- **Inner validation:** 3 months
- **Outer test:** 1 month
- **Total folds:** 33 (202304..202512)
- **Tickers:** SPXW (d25), QQQ (d35), SPY (d35)

## Model Configurations

### Primary: LightGBM Classifier
- `n_estimators = 300`, `learning_rate = 0.05`, `num_leaves = 31`, `min_child_samples = 20`, `subsample = 0.8`, `subsample_freq = 1`, `colsample_bytree = 0.8`, `reg_lambda = 1.0`.
- `n_jobs = 28`: un fold se ejecuta cada vez y LightGBM usa el Ryzen de 32 hilos dejando margen al sistema. No cambia la hipótesis ni el modelo estadístico.
- Deterministic flags: `deterministic = True`, `force_col_wise = True`, `verbose = -1`.
- Seeds (no python `hash()`):
  `base_seed = 42 + int(test_month) + ticker_offset`
  - SPXW offset = 100
  - QQQ offset = 200
  - SPY offset = 300
  
  Head seeds:
  - C0 CALL head seed = `base_seed + 1`
  - C0 PUT head seed = `base_seed + 2`
  - P1 opportunity head seed = `base_seed + 3`
  - P1 side head seed = `base_seed + 4`

### Diagnostic Control: Logistic Regression
- Scaling: `SimpleImputer(strategy="median")` and `StandardScaler()` fit strictly on train only.
- Hyperparameters: `penalty = 'l2'`, `C = 1.0`, `solver = 'lbfgs'`, `class_weight = None`, `max_iter = 1000`, `random_state = base_seed`.
- Rule: Logistic Regression is diagnostic only. It cannot generate trades, select thresholds, produce economic policies, or participate in ensembles.
- Reported metrics: ROC-AUC, PR-AUC, Balanced Accuracy (threshold=0.5), Spearman correlation.

## Policy Execution

### C0 Policy (In-protocol baseline)
1. `p_call_win = call_model.predict_proba(X)[:, 1]`
2. `p_put_win  = put_model.predict_proba(X)[:, 1]`
3. `trade_score = max(p_call_win, p_put_win)`
4. `side_gap    = abs(p_call_win - p_put_win)`
5. Sweep grid of `trade_threshold` and `side_margin`.
6. Trade if `trade_score >= trade_threshold` and `side_gap >= side_margin`:
   - CALL if `p_call_win > p_put_win`
   - PUT  if `p_put_win > p_call_win`
   - ABSTAIN if `side_gap <= 1e-12` (tie) or other conditions fail.

### P1 Policy (Pairwise)
1. `p_trade = opportunity_model.predict_proba(X)[:, 1]`
2. `p_call  = side_model.predict_proba(X)[:, 1]`
3. Sweep grid of `trade_threshold` and `side_margin`.
4. Trade if `p_trade >= trade_threshold`:
   - CALL if `p_call >= 0.5 + side_margin`
   - PUT  if `p_call <= 0.5 - side_margin`
   - ABSTAIN if `p_call` is in the central band `(0.5 - side_margin, 0.5 + side_margin)`.

### Swept Grid (Shared)
- `trade_threshold` ∈ {0.1, 0.2, ..., 0.9}
- `side_margin` ∈ {0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30}

## Validation Selection Criterion
Selected `(trade_threshold, side_margin)` maximizes validation PnL. Ties are broken lexicographically by:
1. highest minimum monthly PnL
2. highest minimum monthly PF
3. highest minimum monthly WR
4. highest minimum monthly trades
5. highest total PnL
6. highest total trades
7. highest side_margin
8. highest trade_threshold

## Scientific Success Criteria (Primary)
Evaluated across all 99 cells (3 tickers × 33 outer test months):
1. **Balanced Accuracy Delta (P1 vs C0) > 0** in at least 60% of cells.
2. **Median of Balanced Accuracy Delta > 0**.
3. **Spearman(p_call, side_advantage) > 0** in at least 60% of cells.
4. **Median of Spearman > 0**.
5. **Favorable evidence** (median delta > 0) in each year: 2023, 2024, and 2025.
6. A paired Wilcoxon signed-rank test on balanced accuracy deltas (excluding zero-deltas) will be reported for significance.

Side scores comparables:

```text
C0 side score = p_call_win - p_put_win
P1 side score = 2 * p_call - 1
```

Accuracy, balanced accuracy, ROC-AUC and Spearman are computed on one shared outer
mask: `opportunity_label == 1`, `abs(side_advantage) > 1e-9`, and finite labels plus
both scores. This function receives no policy threshold or executed-trade mask, so
model metrics remain available even when the economic policy abstains. A cell with
insufficient classes/rows or a non-finite required metric is recorded explicitly as
`SCIENTIFIC_CELL_DEGENERATE`, remains in the fixed denominator of 99 and counts as
not favorable. Inner validation pass rate is diagnostic only.

## Economic Success Criteria (Contract)
Valid for promotion only if every single ticker and outer month meets:
- **Profit Factor (PF) >= 1.3**
- **Win Rate (WR) >= 50%**
- **Trades >= 18**
- **PnL > 0**
- **Hold duration >= 30 minutes**

An outer abstention fails the monthly trade count (0 trades < 18).
Reports: pooled PF, worst-month PF (not averaged PF), worst-month PnL, minimum monthly trades, positive-month rate, maximum drawdown.

## Explicit runner modes and manifests

The runner accepts exactly one mode; no implicit default is allowed:

```powershell
pwsh -File run_pairwise_opportunity_side_v1.ps1 -PreflightOnly
pwsh -File run_pairwise_opportunity_side_v1.ps1 -Execute
```

`-PreflightOnly` reads only the sealed 2022–2025 parquet, compiles code, runs tests,
validates 33 folds/99 cells and writes configuration/manifests without calling
`run_fold` or fitting any model. Its isolated output is:

```text
research_papers/JEPA/results/_diagnostics/pairwise_opportunity_side_v1_preflight/
```

`-Execute` requires a matching PASS preflight and creates a new, previously absent:

```text
research_papers/JEPA/results/_diagnostics/pairwise_opportunity_side_v1/
```

The experiment hash scope contains only the walk-forward, its focused tests, the
PowerShell runner and this predeclaration. The preparation commit also contained
`backtest/backtest_gbt_parquet.py`; it is unrelated, must not be reverted or modified,
and `included_in_experiment_hash_scope = false`.

The real run produces `selected_folds.csv`, `selected_policies.json`,
`outer_metrics.csv`, `outer_trades.csv`, `diagnostic_metrics.csv`,
`class_prevalence.csv`, `threshold_grid_results.csv`, `feature_manifest.json`,
`fold_manifest.json`, `all_folds.csv`, `scientific_criteria.json`,
`economic_criteria.json`, `aggregate_report.json`, `run_manifest.json`, `REPORT.md`
and per-fold summaries/importances/trades.
Manifests contain:
- `feature_hash` per arm
- `model_label` definitions
- `model_seed` per head
- Preprocessing fit details
- First allowed minute = 635
- Selected thresholds and margins
- Scientific & Economic evaluation metrics.
