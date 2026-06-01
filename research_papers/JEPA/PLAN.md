# PLAN: Prove JEPA Latent Alpha, Then Promote to a Neural Trading Predictor

## 1. Objective

Build a controlled research path that answers two questions without breaking the current profitable pipeline:

1. Does a JEPA-style latent market state add out-of-sample alpha to the existing LightGBM entry model?
2. If yes, can the same JEPA encoder be promoted into a full neural predictor that replaces the current PPO/RL options decision layer and beats it in backtests?

## 2026-05-31 Addendum: Base+JEPA 180m Replacement Candidate

The original target/stop augmentation failed, but a narrower 180m terminal-direction hypothesis passed the first replacement screen.

Implemented artifacts:

- `neural/jepa/evaluate_180m_direction.py`
- `neural/jepa/run_jepa_180m_direction.ps1`
- `neural/jepa/train_backtest_180m_frozen.py`
- `neural/jepa/run_jepa_180m_frozen.ps1`
- `neural/jepa/compare_existing_signals_180m.py`
- `neural/jepa/jepa_180m_signal.py`
- `neural/jepa/backtest_jepa_180m.py`
- `neural/jepa/run_jepa_180m_standalone.ps1`

Main report:

- `research_papers/JEPA/results/jepa_180m_frozen_march/SUMMARY.md`

Strict frozen-candidate result:

- Train cutoff: 2026-03-31.
- Test start: 2026-04-01.
- Label: `spot_price(t+180m) > spot_price(t)`.
- Execution proxy: SPX/SPY/QQQ fixed 180m hold, 36-sample cooldown, $100k notional, 1 bps cost.
- `base_jepa` beat `base` on AUC (0.630 vs 0.622), PF (1.936 vs 1.389), win rate (68.3% vs 58.8%), and PnL (+9,044 vs +3,522).
- Existing current GBT target/stop entries repriced under the same fixed-180m proxy produced only PF 1.239 and +909.

Decision: keep the old target/stop JEPA augmentation rejected, but treat frozen `base_jepa` 180m as a credible entry-model replacement candidate. The next implementation step is production-style integration of this candidate behind a separate runner, not promotion into `neural/run_pipeline.ps1` yet.

Standalone inference path:

- Loads frozen per-ticker artifacts from `neural/models/jepa/jepa_180m_frozen_march/base_jepa/`.
- Scores rows through `Jepa180mSignalModel`.
- Produces `HOLD`, `LONG`, or `SHORT` using ticker-specific thresholds.
- Backtests fixed 180m hold with configurable cost, notional, and cooldown.

Cooldown policy:

- Default cooldown is 180m because the label and execution horizon are 180m.
- This avoids treating heavily overlapping 5-minute entries as independent trades.
- Sensitivity was run at 60/90/120/180m. 60m increases PnL but also increases correlated exposure and drawdown; 180m remains the conservative replacement-test setting.

The first objective is additive and low risk: train a small actionless Temporal Tabular LeJEPA, append frozen latent features to the current parquet, and rerun the existing walk-forward GBT/backtest discipline.

The second objective is a promotion path: reuse the proven JEPA encoder and add supervised trading heads for entry, direction, strike selection, exit timing, and expected value. This can replace PPO only if it beats both current baselines:

- GBT-only, because local logs show it is currently stronger than GBT+RL.
- GBT+RL, because that is the current architecture it would replace operationally.

## 2. Current Project Facts

These constraints must drive the implementation:

- The main orchestrator is `neural/run_pipeline.ps1`.
- Data collection writes `training_data/training_data_spx_qqq_spy.parquet`.
- The current March cutoff training file is `training_data/training_data_spx_qqq_spy_march_2026.parquet`.
- The current entry model is LightGBM in `neural/train_walkforward.py`.
- The feature list is `FEATURE_COLUMNS` in `neural/hybrid_model.py`, currently about 163 market features.
- `train_walkforward.py` currently selects only columns in `FEATURE_COLUMNS`; appending JEPA columns to the parquet is not enough by itself.
- `backtest/backtest_gbt_parquet.py` can use `normalizer.feature_names` from the saved model, which means GBT backtests can support expanded feature sets if training saves them correctly.
- RL state dimensions are hardcoded through `MARKET_FEATURE_DIM`, `TOTAL_STATE_DIM`, and related constants in `neural/rl/config.py`; RL cannot consume JEPA features safely until that is made feature-list driven.
- Existing full-data scale is manageable for a small sequence model: about 221k rows, 190 columns, 959 SPX dates, 924 QQQ/SPY dates, and 79 samples per ticker-day on a 5-minute grid.
- The label is event driven: LONG/SHORT only near support/resistance or vanna magnet context when target-before-stop occurs within a 180-minute lookahead; otherwise HOLD.

Observed baseline to preserve:

- GBT-only full backtest: about 3,545 trades, 49.6% win rate, PF about 1.305, PnL about +367k, max drawdown about -17k.
- Recent GBT+RL variants were weaker: PF about 1.08 to 1.15 and materially worse drawdown.

## 3. Core Architecture Decision

Do not port literal LeWorldModel MPC from pixels.

Use the transferable LeJEPA idea:

- Encode current market/options tabular sequence into a latent state `z_t`.
- Predict future latent states `z_{t+h}` over trading-relevant horizons.
- Apply SIGReg to prevent representation collapse.
- Export frozen latent state, latent dynamics, and prediction-surprise features.
- Let strict walk-forward backtests decide whether those features add alpha.

Do not condition the market-state predictor on our trading action in phase 1. Our action does not causally move SPX, QQQ, SPY, VIX, or the option chain. Trade actions affect PnL exposure, not the next market observation.

Action-conditioning may be used later only in a payoff model:

- market encoder: predicts exogenous market evolution without trade action.
- payoff/trade head: predicts expected option outcome conditional on action choice.

## 4. Success Gates

### Gate A: Latent Alpha Exists

Baseline:

- Current GBT-only model trained on existing `FEATURE_COLUMNS`.

Candidate:

- Same GBT code, same walk-forward settings, same thresholds, same backtest, but with JEPA features added.

Promotion criteria:

- Profit Factor improves by at least +0.05 absolute, or PnL improves by at least +10%.
- Trade count remains at least 90% of baseline unless PF improves by at least +0.10 absolute.
- Max drawdown does not worsen by more than 10%.
- April/May 2026 true OOS remains profitable.
- Improvement is not isolated to a single ticker unless a predeclared per-ticker gating rule is used.

If Gate A fails:

- Stop. Keep JEPA out of production.
- Record diagnostics in `research_papers/JEPA/results/`.
- Do not promote to a neural predictor.

### Gate B: JEPA Neural Predictor Beats Entry Baseline

Candidate:

- JEPA encoder plus neural heads that predict HOLD/LONG/SHORT, target-before-stop probability, expected value, and uncertainty.

Promotion criteria:

- Beats GBT-only on PF or PnL under the same true OOS backtest rules.
- Does not reduce trade count below useful operational volume.
- Shows stable ticker-level performance.
- Calibration is acceptable: higher predicted EV/confidence maps to higher realized EV.

If Gate B fails but Gate A passes:

- Keep JEPA as a frozen feature generator for LightGBM.
- Do not replace GBT entry.

### Gate C: JEPA Trading Policy Replaces PPO/RL

Candidate:

- JEPA encoder plus supervised/counterfactual trading heads for strike bucket and exit timing.

Promotion criteria:

- Beats GBT+RL and GBT-only in the final `backtest/backtest_rl.py` style evaluation.
- Improves PF without increasing max drawdown materially.
- Does not collapse into one strike bucket unless that bucket has demonstrably superior OOS EV.
- Exit timing improves realized payoff versus fixed exits and current PPO exits.

If Gate C fails:

- Keep the current RL layer or replace it only with simpler deterministic rules derived from the JEPA diagnostics.

## 5. Implementation Phases

### Phase 0: Baseline Lock

Purpose: freeze the reference numbers before introducing JEPA.

Actions:

1. Run the current GBT-only backtest with the existing `neural/run_pipeline.ps1` settings.
2. Run the current GBT+RL backtest if the latest RL checkpoint is available.
3. Save exact command lines, model paths, thresholds, and metrics in:
   - `research_papers/JEPA/results/baseline_gbt_only.md`
   - `research_papers/JEPA/results/baseline_gbt_rl.md`
4. Include per-ticker metrics:
   - trades
   - win rate
   - PF
   - PnL
   - max drawdown
   - average winner
   - average loser
   - long/short split
5. Save model feature list used by baseline:
   - `research_papers/JEPA/results/baseline_feature_columns.txt`

Acceptance:

- Baseline can be reproduced from recorded commands.
- No JEPA code is evaluated until baseline metrics are written.

### Phase 1: JEPA Package Skeleton

Add a new isolated package:

- `neural/jepa/__init__.py`
- `neural/jepa/config.py`
- `neural/jepa/dataset.py`
- `neural/jepa/model.py`
- `neural/jepa/sigreg.py`
- `neural/jepa/train_temporal_jepa.py`
- `neural/jepa/append_jepa_features.py`
- `neural/jepa/diagnose_jepa_features.py`
- `neural/jepa/evaluate_jepa_alpha.py`

Design defaults:

- Use PyTorch only; avoid adding new heavy dependencies.
- Use `argparse` for scripts so they work from `run_pipeline.ps1`.
- Save artifacts under `neural/models/jepa/<experiment_name>/`.
- Save all resolved config values to `config.json`.
- Save training metrics to `metrics.csv`.
- Save feature names to `jepa_feature_names.json`.

Artifact layout:

```text
neural/models/jepa/tabular_v1/
  config.json
  encoder.pt
  predictor.pt
  normalizer.json
  feature_columns.json
  jepa_feature_names.json
  metrics.csv
  diagnostics.json
```

### Phase 2: Dataset and Leakage Controls

Implement `neural/jepa/dataset.py`.

Input:

- `training_data/training_data_spx_qqq_spy_march_2026.parquet` for initial training.
- Use only columns from `FEATURE_COLUMNS` that exist in the parquet.
- Required grouping columns:
  - `ticker`
  - `date`
  - intraday time column used by the collector/backtests.

Sequence construction:

- Sort by ticker, date, and intraday time.
- Build one sequence per ticker-day.
- Expected length is 79 rows per ticker-day.
- Do not create windows that cross ticker-day boundaries.
- Initial context lengths:
  - 12 steps = 60 minutes
  - 24 steps = 120 minutes
- Initial prediction horizons:
  - 1 step = 5 minutes
  - 3 steps = 15 minutes
  - 6 steps = 30 minutes
  - 12 steps = 60 minutes
  - 24 steps = 120 minutes
  - 36 steps = 180 minutes

Normalization:

- Fit normalization on training split only.
- Use robust median/IQR or mean/std with clipping.
- Store normalizer stats in the JEPA artifact.
- Apply the same normalizer when appending features to train and full backtest parquets.
- Clip normalized inputs to a fixed range, initially `[-10, 10]`.

Leakage rules:

- No target labels are used in self-supervised JEPA pretraining.
- No rows after the JEPA training cutoff are used to fit encoder weights or input normalizer.
- When appending JEPA features to the full parquet, the model may encode future-dated rows, but weights and normalization must come only from the cutoff training data.
- For the stricter phase, train one JEPA model per walk-forward window so each GBT fold only receives latents from a JEPA model trained on that fold's training window.

### Phase 3: Temporal Tabular LeJEPA V1

Implement `neural/jepa/model.py`.

Initial encoder:

- Small GRU or Transformer encoder.
- Recommended default: GRU for v1 because the dataset is small and daily sequences are short.
- Input dimension: number of available `FEATURE_COLUMNS`.
- Hidden dimension: 128.
- Latent dimension: 32.
- Layers: 2.
- Dropout: 0.10.
- Output: `z_t` for the last context step.

Initial predictor:

- One MLP prediction head per horizon.
- Input: `z_t` plus optional horizon embedding.
- Output: predicted future latent `z_hat_{t+h}`.
- Hidden dimension: 128.
- Activation: GELU or SiLU.

Target latents:

- Encode the future context ending at `t+h` with the same encoder.
- Do not use stop-gradient in the LeJEPA/SIGReg variant unless diagnostics show instability.
- If training collapses, add a fallback flag for stop-gradient target latents but keep it disabled by default.

Loss:

```text
prediction_loss = mean_h MSE(z_hat_{t+h}, z_{t+h})
sigreg_loss = SIGReg(z_t and future target latents)
total_loss = prediction_loss + lambda_sigreg * sigreg_loss
```

Initial hyperparameters:

- `z_dim`: 32
- `context_len`: 24
- `horizons`: 1, 3, 6, 12, 24, 36
- `lambda_sigreg`: 0.05
- `batch_size`: 512 windows
- `epochs`: 50 maximum
- early stopping patience: 8 validation epochs
- optimizer: AdamW
- learning rate: 0.001
- weight decay: 0.01
- gradient clipping: 1.0
- device: CUDA when available

Small grid after v1 works:

- `z_dim`: 32, 64
- `context_len`: 12, 24
- `lambda_sigreg`: 0.03, 0.05, 0.10

### Phase 4: SIGReg Implementation

Implement `neural/jepa/sigreg.py`.

Goal:

- Encourage latent projections to match an isotropic Gaussian.
- Prevent collapsed or low-rank embeddings.

Implementation:

- Sample `k` random unit projection vectors of shape `[k, z_dim]`.
- Project embeddings: `p = z @ projections.T`.
- Compare each projected distribution to standard normal using a differentiable Epps-Pulley style characteristic-function statistic.
- Normalize embeddings before SIGReg only if needed for numerical stability.

Initial defaults:

- `num_projections`: 64
- `num_test_frequencies`: 16
- `sigma`: 1.0
- apply to both current and future latents.

Diagnostics:

- covariance eigenvalue spectrum
- effective rank
- per-dimension mean/std
- pairwise latent correlation
- percentage of dimensions with near-zero variance

Failure thresholds:

- effective rank below 40% of `z_dim`: reject run.
- more than 25% latent dimensions with std below 0.05: reject run.
- one principal component explaining more than 70% variance: reject run.

### Phase 5: Feature Export

Implement `neural/jepa/append_jepa_features.py`.

Inputs:

- source parquet
- JEPA artifact directory
- output parquet
- batch size
- device

Outputs:

- Original parquet columns unchanged.
- New JEPA columns appended.

Feature schema for `z_dim=32`:

```text
jepa_z_00 ... jepa_z_31
jepa_pred_5m_err
jepa_pred_15m_err
jepa_pred_30m_err
jepa_pred_60m_err
jepa_pred_120m_err
jepa_pred_180m_err
jepa_latent_velocity
jepa_latent_accel
jepa_pred_consistency_short
jepa_pred_consistency_long
jepa_context_valid
```

Definitions:

- `jepa_z_*`: encoder latent for the current row using only prior/current context.
- `jepa_pred_*_err`: realized latent prediction error for that horizon when the future row exists.
- `jepa_latent_velocity`: norm of `z_t - z_{t-1}`.
- `jepa_latent_accel`: norm of `(z_t - z_{t-1}) - (z_{t-1} - z_{t-2})`.
- `jepa_pred_consistency_short`: agreement between 5m/15m/30m predicted future latents.
- `jepa_pred_consistency_long`: agreement between 60m/120m/180m predicted future latents.
- `jepa_context_valid`: 1 when enough past context exists, otherwise 0.

Important leakage decision:

- `jepa_z_*`, velocity, accel, and predicted future latents are safe for live use.
- Realized future prediction errors are not live-safe at entry time if they require observing `t+h`.
- Therefore export two feature groups:
  - live-safe: `jepa_z_*`, `jepa_latent_velocity`, `jepa_latent_accel`, predicted latent norms/dispersion, context flag.
  - research-only diagnostics: realized `jepa_pred_*_err`.

For GBT alpha tests, use only live-safe columns by default.

Live-safe surprise alternative:

- Use predicted uncertainty/dispersion and current reconstruction-free consistency as live-safe risk features.
- For true prediction error, compute it lagged only after the horizon has elapsed:
  - at row `t`, `jepa_lagged_pred_30m_err` may use the prediction made at `t-30m` and the now-observed `z_t`.
  - this is live-safe and should be included.

Final live-safe v1 columns:

```text
jepa_z_00 ... jepa_z_31
jepa_latent_velocity
jepa_latent_accel
jepa_pred_norm_5m
jepa_pred_norm_30m
jepa_pred_norm_60m
jepa_pred_norm_180m
jepa_pred_dispersion_short
jepa_pred_dispersion_long
jepa_lagged_pred_30m_err
jepa_lagged_pred_60m_err
jepa_lagged_pred_180m_err
jepa_context_valid
```

### Phase 6: Feature-Column Integration

Modify the GBT training path so JEPA columns can be used deliberately.

Add a helper in a new or existing module:

```python
def get_model_feature_columns(df, include_jepa=False, jepa_feature_names_path=None):
    base = [c for c in FEATURE_COLUMNS if c in df.columns]
    if not include_jepa:
        return base
    jepa = load_feature_names(jepa_feature_names_path)
    return base + [c for c in jepa if c in df.columns]
```

Required changes:

- `neural/train_walkforward.py`
  - add CLI flag `--include-jepa-features`
  - add CLI arg `--jepa-feature-names`
  - use the expanded feature list instead of hardcoded `FEATURE_COLUMNS`
  - save expanded `normalizer.feature_names`
- `backtest/backtest_gbt_parquet.py`
  - verify it uses saved `normalizer.feature_names`; only add safeguards if needed.
- `neural/run_pipeline.ps1`
  - add optional flags for JEPA:
    - `-jepa`
    - `-jepaTrain`
    - `-jepaAppend`
  - add paths:
    - `JepaModelDir`
    - `TrainingDataMarchJepaPath`
    - `BacktestDataJepaPath`
    - `JepaFeatureNamesPath`

Do not modify `FEATURE_COLUMNS` globally for phase 1.

Reason:

- Global mutation would affect RL state dimensions, old hybrid code, diagnostics, and backtests.
- The first experiment should be opt-in and reproducible.

### Phase 7: Alpha Evaluation Script

Implement `neural/jepa/evaluate_jepa_alpha.py`.

Purpose:

- Compare baseline GBT-only metrics vs GBT+JEPA metrics from saved backtest logs or JSON outputs.

Inputs:

- baseline metrics file
- candidate metrics file
- optional per-trade CSV/parquet if available

Outputs:

- `research_papers/JEPA/results/jepa_alpha_report.md`
- `research_papers/JEPA/results/jepa_alpha_report.json`

Report sections:

- overall metrics delta
- per-ticker metrics delta
- long/short metrics delta
- monthly OOS metrics
- confidence bucket analysis
- drawdown comparison
- trade overlap analysis if trade logs exist
- whether Gate A passed

Gate A should be automatically computed and printed as PASS/FAIL.

### Phase 8: Diagnostics Before Any Promotion

Implement `neural/jepa/diagnose_jepa_features.py`.

Required diagnostics:

1. Embedding health
   - effective rank
   - covariance eigenvalues
   - per-dimension mean/std
   - latent correlation heatmap data

2. Temporal behavior
   - average latent velocity by ticker
   - average latent velocity by time of day
   - lagged prediction error by VIX regime
   - lagged prediction error before big wins/losses

3. Leakage checks
   - verify live-safe feature list excludes future-realized errors
   - verify first rows of each ticker-day have `jepa_context_valid=0` or padded context
   - verify no sequence crosses a date boundary

4. GBT usage
   - LightGBM feature importance for JEPA columns
   - SHAP optional, only if already available
   - ablation without `jepa_z_*` but with lagged surprise
   - ablation with `jepa_z_*` but without lagged surprise

5. Robustness
   - per-ticker uplift
   - per-month uplift
   - high-VIX vs low-VIX uplift
   - trend vs chop regime uplift

Reject the candidate if diagnostics show:

- collapsed latents
- clear leakage
- uplift only from non-live-safe prediction errors
- uplift only from time/ticker shortcuts
- massive degradation in one ticker that is hidden by aggregate PnL

## 6. Phase-1 Commands

Initial training:

```powershell
python -u neural/jepa/train_temporal_jepa.py `
  --data training_data/training_data_spx_qqq_spy_march_2026.parquet `
  --output-dir neural/models/jepa/tabular_v1 `
  --context-len 24 `
  --horizons 1,3,6,12,24,36 `
  --z-dim 32 `
  --lambda-sigreg 0.05 `
  --epochs 50 `
  --batch-size 512 `
  --device cuda
```

Append JEPA features to the March cutoff:

```powershell
python -u neural/jepa/append_jepa_features.py `
  --data training_data/training_data_spx_qqq_spy_march_2026.parquet `
  --model-dir neural/models/jepa/tabular_v1 `
  --output training_data/training_data_spx_qqq_spy_march_2026_jepa_tabular_v1.parquet `
  --live-safe-only `
  --device cuda
```

Append JEPA features to the full backtest file:

```powershell
python -u neural/jepa/append_jepa_features.py `
  --data training_data/training_data_spx_qqq_spy.parquet `
  --model-dir neural/models/jepa/tabular_v1 `
  --output training_data/training_data_spx_qqq_spy_jepa_tabular_v1.parquet `
  --live-safe-only `
  --device cuda
```

Train GBT with JEPA features:

```powershell
python -u neural/train_walkforward.py `
  --data training_data/training_data_spx_qqq_spy_march_2026_jepa_tabular_v1.parquet `
  --output neural/models/codex_exp/gbt_jepa_tabular_v1_march2026.joblib `
  --normalizer neural/models/codex_exp/gbt_jepa_tabular_v1_march2026_normalizer.npz `
  --include-jepa-features `
  --jepa-feature-names neural/models/jepa/tabular_v1/jepa_feature_names.json
```

Backtest candidate:

```powershell
python -u backtest/backtest_gbt_parquet.py `
  --data training_data/training_data_spx_qqq_spy_jepa_tabular_v1.parquet `
  --model neural/models/codex_exp/gbt_jepa_tabular_v1_march2026.joblib `
  --normalizer neural/models/codex_exp/gbt_jepa_tabular_v1_march2026_normalizer.npz
```

Exact CLI flags may need to match the current scripts; the implementation should preserve the existing defaults from `run_pipeline.ps1`.

## 7. Stricter Walk-Forward JEPA Mode

The initial v1 is cutoff-clean but not fold-perfect. If it passes Gate A, implement fold-perfect JEPA.

Goal:

- For each GBT walk-forward fold, train or load a JEPA encoder using only that fold's training months.
- Generate latents for the fold's train/test rows.
- Train/evaluate LightGBM with those fold-local latents.

Implementation approach:

- Add `--jepa-walkforward-mode strict` to `train_walkforward.py`.
- Cache fold JEPA artifacts under:

```text
neural/models/jepa/tabular_v1/folds/
  ticker_SPX_fold_000/
  ticker_SPX_fold_001/
  ticker_QQQ_fold_000/
  ...
```

Optimization:

- Start with shared all-ticker fold encoders.
- Only move to ticker-specific JEPA encoders if diagnostics show ticker-specific latent drift.

Acceptance:

- Fold-perfect mode must preserve most of the alpha from the simpler cutoff-clean mode.
- If alpha disappears, treat the first result as too optimistic.

## 8. Promotion to Full Neural Predictor

Only start this after Gate A passes.

Create:

- `neural/jepa/train_neural_predictor.py`
- `neural/jepa/neural_predictor.py`
- `neural/jepa/backtest_neural_predictor.py`

Architecture:

- Shared JEPA encoder initialized from the proven Temporal Tabular LeJEPA checkpoint.
- Optional fine-tuning with a low learning rate.
- Heads:
  - `entry_head`: trade/no-trade
  - `direction_head`: LONG/SHORT
  - `target_before_stop_head`: probability of target-before-stop within 180 minutes
  - `ev_head`: expected trade value under baseline option execution assumptions
  - `uncertainty_head`: uncertainty or abstention score

Training targets:

- Use existing `target` for HOLD/LONG/SHORT.
- Use target-before-stop labels already implied by the collector.
- Add realized forward return labels if available from existing backtest or option-cache logic.
- Use class-balanced sampling to prevent HOLD dominance.

Loss:

```text
loss = ce_entry
     + ce_direction
     + bce_target_before_stop
     + huber_ev
     + calibration_penalty
     + optional_jepa_prediction_aux_loss
```

Training discipline:

- Same chronological splits as GBT walk-forward.
- No random train/test split.
- Early stop on economic validation score, not accuracy alone.
- Report calibration curves by confidence bucket.

Candidate decision rule:

- Generate LONG/SHORT only when:
  - predicted trade probability exceeds threshold
  - predicted EV exceeds threshold
  - uncertainty is below threshold
- Thresholds must be selected on validation folds only.

Gate B backtest:

- Use the same execution assumptions as `backtest/backtest_gbt_parquet.py`.
- Compare to current GBT-only.
- Require PF/PnL/drawdown improvement before replacing GBT entry.

## 9. Promotion to RL Replacement

Only start this after Gate A passes. Gate B passing is preferred but not strictly required if the goal is only to replace PPO decisions after GBT signals.

The replacement should be a supervised/counterfactual options decision model, not a LeWorldModel-style MPC planner.

Create:

- `neural/jepa/train_option_decision_model.py`
- `neural/jepa/option_decision_model.py`
- `backtest/backtest_jepa_options.py`

Inputs:

- Current market `FEATURE_COLUMNS`.
- JEPA live-safe latent features.
- GBT signal context:
  - direction
  - confidence
  - margin
  - disagreement if available
- Option candidate features from the same cache used by RL:
  - strike bucket
  - moneyness/delta bucket
  - bid/ask or OHLC proxy
  - gamma/delta/theta/vega
  - spread/liquidity proxies
  - time to expiration
- Position state for exit decisions:
  - minutes held
  - unrealized return
  - max favorable excursion
  - max adverse excursion
  - current option mark

Outputs:

- `entry_skip_head`: take or skip the GBT signal.
- `strike_head`: choose strike bucket.
- `exit_head`: HOLD/EXIT at each minute after entry.
- `trade_value_head`: expected final trade PnL or return.
- `risk_head`: probability of stop, severe drawdown, or low-liquidity failure.

Training data:

- Use generated episode index from GBT signals.
- Use existing RL option cache to reconstruct candidate trades.
- For each signal, label multiple candidate strike buckets with realized outcome when feasible.
- For exits, create per-minute labels:
  - exit now return
  - best future return
  - stop/target outcome
  - time-to-best-exit

Loss:

```text
loss = ce_entry_skip
     + ce_strike_or_listwise_ranking_loss
     + bce_exit
     + huber_trade_value
     + bce_risk
```

Preferred strike objective:

- Use listwise or pairwise ranking over candidate strike buckets by realized risk-adjusted return.
- This avoids pretending there is only one correct strike when several strikes are profitable.

Preferred exit objective:

- Train exit as a value comparison:
  - exit now value
  - continue value
- Exit when `exit_now_value >= continue_value - cost_buffer`.

Why this can beat PPO:

- PPO currently learns from sparse/noisy rewards and can collapse strike/exit heads.
- Supervised counterfactual labels from historical option paths are denser.
- JEPA latents provide regime/state context before the decision heads.
- The model can be calibrated and thresholded like the GBT.

Gate C backtest:

- Compare against:
  - GBT-only
  - current GBT+RL
  - fixed strike/fixed exit heuristics
- Required report:
  - total trades
  - PF
  - PnL
  - max drawdown
  - per-ticker metrics
  - strike bucket distribution
  - average hold time
  - exit reason distribution
  - monthly OOS breakdown

## 10. RL Integration If Replacement Fails

If JEPA features help but the supervised options decision model does not beat PPO, integrate JEPA into the RL state instead.

Required changes:

- Make RL state construction feature-list driven instead of hardcoding `MARKET_FEATURE_DIM = 163`.
- Add `--market-feature-names` or load model `normalizer.feature_names`.
- Update:
  - `neural/rl/config.py`
  - `neural/rl/environment.py`
  - `neural/rl/integration.py`
  - `neural/rl/preprocess.py`
  - `backtest/backtest_rl.py`

Do not simply increase `MARKET_FEATURE_DIM` manually.

Reason:

- Manual dimension changes are brittle and can desync training, preprocessing, and backtesting.

RL JEPA features:

- `jepa_z_*`
- `jepa_latent_velocity`
- `jepa_latent_accel`
- `jepa_lagged_pred_*_err`
- predicted dispersion features

RL-specific tests:

- state dimension matches model checkpoint
- environment observation shape is stable
- episode cache includes JEPA columns
- `backtest_rl.py` uses the same feature order as training

## 11. Option Surface LeJEPA V2

Only build this if Tabular LeJEPA passes Gate A or diagnostics show that aggregate features are the bottleneck.

Purpose:

- Learn from richer option-chain structure that is compressed away by handcrafted aggregates.

Input tensor:

- per minute
- by ticker
- by expiry type: 0DTE daily and weekly
- by moneyness or delta bucket
- by call/put side
- channels:
  - IV
  - OI
  - volume
  - gamma
  - delta
  - vanna
  - charm
  - dgex
  - vega
  - vomma

Encoder:

- small set/curve encoder or 1D convolution over ordered moneyness buckets.
- combine with tabular market context.

Loss:

- same LeJEPA prediction plus SIGReg.

Export:

- `jepa_surface_z_*`
- `jepa_surface_velocity`
- `jepa_surface_lagged_pred_err_*`

Acceptance:

- Must beat Tabular LeJEPA after accounting for added complexity.
- If uplift is not materially better, keep the simpler tabular model.

## 12. Testing Plan

Unit tests:

- SIGReg returns finite gradients.
- Dataset windows never cross ticker/date boundaries.
- Normalizer fitted on train rows only.
- Feature export preserves row count and row order.
- Feature export writes expected column names.
- Live-safe feature list excludes future-realized errors.
- GBT feature selection includes JEPA columns only when requested.

Integration tests:

- Train JEPA for 1 epoch on a small date subset.
- Append features to a small parquet subset.
- Train LightGBM on the small augmented subset.
- Verify saved normalizer includes JEPA feature names.
- Run a tiny backtest smoke test.

Diagnostics tests:

- collapsed synthetic latents fail health checks.
- random non-collapsed latents pass basic shape/finite checks.
- lagged prediction error uses only past prediction timestamps.

Backtest acceptance tests:

- Baseline command reproduces expected order of magnitude metrics.
- Candidate command produces a complete metrics file.
- Alpha report computes PASS/FAIL deterministically.

## 13. Feature Competition and Ablation Protocol

This project already has many engineered features. Most candidate features will not matter. The JEPA test must explicitly handle the possibility that LightGBM ignores the added latent columns.

Required comparisons:

1. Baseline GBT
   - Use only the current `FEATURE_COLUMNS`.
   - This is the production reference.

2. GBT + JEPA live-safe features
   - Use `FEATURE_COLUMNS` plus live-safe JEPA features.
   - This answers whether JEPA adds incremental alpha to the existing feature set.

3. JEPA-only probe
   - Use only `jepa_z_*`, JEPA dynamics, lagged surprise, ticker, and minimal time/session context.
   - Do not include the full engineered feature set.
   - This answers whether the JEPA representation contains standalone tradable signal or is only useful through interactions with existing features.

4. Top-K JEPA compact model
   - Rank JEPA columns using out-of-fold feature importance, permutation importance, or a simple validation probe.
   - Keep only the top 4 to 12 JEPA columns.
   - Retrain GBT with `FEATURE_COLUMNS + top_k_jepa`.
   - This reduces noise and avoids shipping 30 to 70 latent columns if only a few are useful.

5. Group ablation
   - Train with all JEPA columns.
   - Retrain with the full JEPA group removed.
   - Retrain with only `jepa_z_*` removed.
   - Retrain with only lagged surprise/dynamics removed.
   - Judge by PF, PnL, drawdown, and trade count, not accuracy.

6. OOS permutation importance
   - On validation/backtest periods, permute only JEPA columns while keeping base features fixed.
   - If PF/PnL barely changes, the JEPA group is not contributing real signal.
   - Run permutation by group and by individual top JEPA columns.

7. Feature dilution check
   - Because the current LightGBM uses column subsampling, adding many weak JEPA columns can dilute split opportunities.
   - Compare the same candidate with:
     - all JEPA features
     - top-K JEPA features
     - smaller `z_dim`
     - adjusted `colsample_bytree` if needed
   - Do not accept a larger latent dimension unless it improves OOS economics.

Decision rules:

- If GBT + JEPA does not beat baseline and JEPA-only is weak, stop the JEPA path.
- If JEPA-only is strong but GBT + JEPA is flat, investigate feature dilution and top-K selection before rejecting.
- If GBT + JEPA improves but permutation OOS shows no sensitivity to JEPA columns, treat the uplift as noise.
- If only non-live-safe or future-realized error features help, reject the result for production.
- If top-K JEPA preserves most of the uplift, prefer top-K over all latent columns.

## 14. Experiment Matrix

Run the smallest matrix first:

| Experiment | z_dim | context | lambda | features used | Purpose |
| --- | ---: | ---: | ---: | --- | --- |
| tabular_v1_a | 32 | 24 | 0.05 | live-safe all | default candidate |
| tabular_v1_b | 32 | 12 | 0.05 | live-safe all | shorter context |
| tabular_v1_c | 64 | 24 | 0.05 | live-safe all | larger latent |
| tabular_v1_d | 32 | 24 | 0.03 | live-safe all | weaker SIGReg |
| tabular_v1_e | 32 | 24 | 0.10 | live-safe all | stronger SIGReg |

Ablations after one candidate works:

| Ablation | Description |
| --- | --- |
| no_z | lagged surprise and dynamics only |
| z_only | latent vector only |
| no_lagged_surprise | remove lagged prediction errors |
| per_ticker | train separate JEPA encoders by ticker |
| no_ticker_condition | prevent ticker shortcut |
| jepa_only_probe | use JEPA plus minimal ticker/time context only |
| top_k_jepa | use base features plus top 4 to 12 JEPA columns |
| permute_jepa_group | OOS permutation of the entire JEPA feature group |
| permute_top_jepa | OOS permutation of selected JEPA columns |

## 15. Reporting Format

Every experiment should produce:

```text
research_papers/JEPA/results/<experiment>/
  config.json
  jepa_training_metrics.csv
  jepa_diagnostics.json
  gbt_training_summary.md
  backtest_metrics.json
  alpha_report.md
  alpha_report.json
```

Each `alpha_report.md` must include:

- baseline metrics
- candidate metrics
- deltas
- Gate A PASS/FAIL
- known caveats
- exact commands used
- git commit or dirty-worktree note

## 16. Rollback and Safety

Keep JEPA optional until it passes all gates.

Rules:

- Do not change the default pipeline behavior unless `-jepa` or equivalent flags are set.
- Do not mutate `FEATURE_COLUMNS` globally in phase 1.
- Do not replace existing model paths.
- Write candidate models to new names containing `jepa`.
- Keep original parquet files unchanged; write augmented parquets with `_jepa_<experiment>` suffix.
- Treat any result using non-live-safe future prediction errors as diagnostic only.

## 17. Final Recommendation

Build in this order:

1. Baseline lock.
2. Temporal Tabular LeJEPA v1.
3. Live-safe feature export.
4. Opt-in GBT feature-column integration.
5. GBT+JEPA strict OOS alpha report.
6. Fold-perfect JEPA validation if Gate A passes.
7. JEPA neural predictor for entry/direction/EV if Gate A remains valid.
8. JEPA supervised options decision model to replace PPO only if the neural predictor or JEPA features prove durable alpha.

The expected best first win is not full LeWorldModel replacement. The expected best first win is a compact predictive latent state that gives LightGBM better regime and sequence context while preserving the current pipeline's walk-forward discipline.
